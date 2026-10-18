"""vmrun subprocess 封装层

vmrun 是 VIX SDK 的官方命令行封装，功能覆盖我们需要的所有 guest 操作。
用 subprocess 调 vmrun 比自己绑 ctypes 更稳、开发更快。
VIX ctypes 实现保留在 src/vix/ 里，以后可作为更快的后端切换。
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class FileEntry:
    """guest 端目录条目"""
    name: str
    full_path: str
    size: int = 0
    is_dir: bool = False
    is_symlink: bool = False
    mod_time: datetime | None = None


class VmrunError(Exception):
    """vmrun 调用失败"""
    def __init__(self, cmd: list[str], stdout: str, stderr: str, returncode: int):
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        super().__init__(f"vmrun failed (rc={returncode}): {stderr.strip() or stdout.strip()}")


class VmrunClient:
    """vmrun 命令行客户端"""

    def __init__(
        self,
        vmx_path: str,
        guest_user: str = "",
        guest_password: str = "",
        vmrun_path: str | None = None,
        timeout: int = 300,
    ):
        self._vmx = vmx_path
        self._user = guest_user
        self._pass = guest_password
        self._vmrun = vmrun_path or self._find_vmrun()
        self._timeout = timeout
        if not Path(self._vmrun).exists():
            raise FileNotFoundError(f"vmrun.exe 不存在: {self._vmrun}")
        if not Path(vmx_path).exists():
            raise FileNotFoundError(f".vmx 不存在: {vmx_path}")

    @staticmethod
    def _find_vmrun() -> str:
        candidates = [
            r"G:\VMware\VMware Workstation\vmrun.exe",
            r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
            r"C:\Program Files\VMware\VMware Workstation\vmrun.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                return c
        # PATH 里找
        import shutil
        found = shutil.which("vmrun")
        if found:
            return found
        raise FileNotFoundError("找不到 vmrun.exe，请在 config.yaml 里指定 vmrun_path")

    # ======================================================================
    # 基础调用
    # ======================================================================

    def _run(self, *args: str, timeout: int | None = None) -> str:
        """执行 vmrun 命令，返回 stdout（去掉尾部换行）。失败抛 VmrunError。"""
        cmd = [self._vmrun, "-T", "ws"]
        if self._user:
            cmd += ["-gu", self._user]
        if self._pass:
            cmd += ["-gp", self._pass]
        cmd += list(args)

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout or self._timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            # 手动解码，errors=replace 避免 GBK 解码失败
            stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise VmrunError(cmd, stdout, stderr, -2)

        if result.returncode != 0:
            raise VmrunError(cmd, stdout, stderr, result.returncode)
        return stdout.rstrip("\r\n")

    def _run_noguest(self, *args: str, timeout: int | None = None) -> str:
        """执行不需要 guest auth 的 vmrun 命令（不带 -gu / -gp）"""
        cmd = [self._vmrun, "-T", "ws"] + list(args)
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout or self._timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise VmrunError(cmd, stdout, stderr, -2)

        if result.returncode != 0:
            raise VmrunError(cmd, stdout, stderr, result.returncode)
        return stdout.rstrip("\r\n")

    # ======================================================================
    # Tools / 状态检查
    # ======================================================================

    def check_tools_state(self) -> str:
        """返回 'running' / 'notRunning' / 'unknown'"""
        # checkToolsState 返回的值可能走 stderr，且 rc 不一定 0
        cmd = [self._vmrun, "-T", "ws", "checkToolsState", self._vmx]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self._timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
        out = (stdout + stderr).strip()
        # vmrun 在 tools 未装时 stderr 会有额外报错信息
        # 提取关键字
        for keyword in ("running", "notRunning", "unknown", "installed", "vmware tools"):
            if keyword.lower() in out.lower():
                if keyword.lower() == "running":
                    return "running"
                elif keyword.lower() == "notrunning":
                    return "notRunning"
                elif keyword.lower() == "unknown":
                    return "unknown"
        return out or "unknown"

    def is_tools_ready(self) -> bool:
        return self.check_tools_state().strip().lower() == "running"

    def get_guest_ip(self, wait: bool = False) -> str:
        """获取 guest IP"""
        args = ["getGuestIPAddress", self._vmx]
        if wait:
            args.append("-wait")
        return self._run_noguest(*args)

    def list_running_vms(self) -> list[str]:
        """列出所有运行中的 VM (.vmx 路径列表)"""
        out = self._run_noguest("list")
        lines = out.split("\n")
        vms = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("Total running"):
                vms.append(line)
        return vms

    # ======================================================================
    # Guest 文件操作
    # ======================================================================

    def list_dir(self, guest_path: str) -> list[FileEntry]:
        """列出 guest 目录内容，区分文件/目录。
        
        步骤:
          1. 用 listDirectoryInGuest 拿所有条目名（快）
          2. 并行用 directoryExistsInGuest 探测类型
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Step 1: 拿名字
        raw = self._run("listDirectoryInGuest", self._vmx, guest_path)
        names: list[str] = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("directory list"):
                continue
            if line in (".", ".."):
                continue
            names.append(line)

        # Step 2: 并行探测类型 —— 每个 vmrun subprocess ~800ms，并行 8 个一起跑
        def check_is_dir(name: str):
            full = guest_path.rstrip("/") + "/" + name
            try:
                return (name, self._run_check_exists("directoryExistsInGuest", full))
            except Exception:
                return (name, False)

        entries_by_name: dict[str, bool] = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(check_is_dir, n): n for n in names}
            for fut in as_completed(futures):
                name, is_dir = fut.result()
                entries_by_name[name] = is_dir

        entries: list[FileEntry] = []
        for name in names:
            is_dir = entries_by_name.get(name, False)
            full = guest_path.rstrip("/") + "/" + name
            entries.append(FileEntry(
                name=name,
                full_path=full,
                size=0,
                is_dir=is_dir,
                is_symlink=False,
                mod_time=None,
            ))
        return entries

    def _run_check_exists(self, vmrun_cmd: str, guest_path: str) -> bool:
        """directoryExistsInGuest / fileExistsInGuest 的原始调用。
        返回 True 表示存在，False 表示不存在，抛异常表示其他错误。
        """
        from .vmrun_client import VmrunError as _VE
        try:
            self._run(vmrun_cmd, self._vmx, guest_path)
            return True
        except VmrunError as e:
            msg = (e.stderr + " " + e.stdout).lower()
            if any(kw in msg for kw in ["does not exist", "not found", "no such file", "no such directory"]):
                return False
            raise

    def file_exists(self, guest_path: str) -> bool:
        try:
            self._run("fileExistsInGuest", self._vmx, guest_path)
            return True
        except VmrunError as e:
            # "does not exist" / "not found" / "No such file" → False
            msg = (e.stderr + " " + e.stdout).lower()
            if any(kw in msg for kw in ["does not exist", "not found", "no such file", "no such directory"]):
                return False
            raise

    def dir_exists(self, guest_path: str) -> bool:
        try:
            self._run("directoryExistsInGuest", self._vmx, guest_path)
            return True
        except VmrunError as e:
            msg = (e.stderr + " " + e.stdout).lower()
            if any(kw in msg for kw in ["does not exist", "not found", "no such file", "no such directory"]):
                return False
            raise

    def make_dir(self, guest_path: str) -> None:
        self._run("createDirectoryInGuest", self._vmx, guest_path)

    def delete_file(self, guest_path: str) -> None:
        self._run("deleteFileInGuest", self._vmx, guest_path)

    def delete_dir(self, guest_path: str) -> None:
        self._run("deleteDirectoryInGuest", self._vmx, guest_path)

    def copy_to_guest(self, host_path: str, guest_path: str) -> None:
        """上传 host 文件到 guest"""
        if not Path(host_path).exists():
            raise FileNotFoundError(f"host 文件不存在: {host_path}")
        self._run("CopyFileFromHostToGuest", self._vmx, host_path, guest_path)

    def copy_from_guest(self, guest_path: str, host_path: str) -> None:
        """从 guest 下载文件到 host"""
        self._run("CopyFileFromGuestToHost", self._vmx, guest_path, host_path)

    # ======================================================================
    # Guest 进程 / 脚本
    # ======================================================================

    def run_program(self, program: str, args: str = "", no_wait: bool = False, ignore_rc: bool = True) -> None:
        """在 guest 里运行程序。ignore_rc=True 时 guest 程序返回非零退出码不报错。"""
        cmd = ["runProgramInGuest", self._vmx]
        if no_wait:
            cmd.append("-noWait")
        cmd += [program]
        if args:
            cmd.append(args)
        try:
            self._run(*cmd)
        except VmrunError as e:
            if ignore_rc and "Guest program exited with non-zero exit code" in str(e):
                return
            raise

    def run_script(self, interpreter: str, script_text: str, no_wait: bool = False) -> None:
        cmd = ["runScriptInGuest", self._vmx]
        if no_wait:
            cmd.append("-noWait")
        cmd += [interpreter, script_text]
        self._run(*cmd)

    # ======================================================================
    # Shared Folders 管理
    # ======================================================================

    def enable_shared_folders(self, runtime: bool = False) -> None:
        cmd = ["enableSharedFolders", self._vmx]
        if runtime:
            cmd.append("runtime")
        self._run_noguest(*cmd)

    def add_shared_folder(self, share_name: str, host_path: str) -> None:
        self._run_noguest("addSharedFolder", self._vmx, share_name, host_path)

    def remove_shared_folder(self, share_name: str) -> None:
        self._run_noguest("removeSharedFolder", self._vmx, share_name)

    # ======================================================================
    # 电源操作
    # ======================================================================

    def power_on(self, gui: bool = False) -> None:
        mode = "gui" if gui else "nogui"
        self._run_noguest("start", self._vmx, mode)

    def power_off(self, hard: bool = False) -> None:
        mode = "hard" if hard else "soft"
        self._run_noguest("stop", self._vmx, mode)

    # ======================================================================
    # 内部: 解析 listDirectoryInGuest 输出
    # ======================================================================

def quick_test(vmx_path: str, user: str, password: str = "") -> None:
    """快速连通性测试"""
    print(f"[*] vmrun path: {VmrunClient._find_vmrun()}")
    c = VmrunClient(vmx_path, user, password)

    print(f"[*] Tools state: {c.check_tools_state()}")
    if not c.is_tools_ready():
        print("[!] VMware Tools 未运行，请在 Ubuntu 里执行:")
        print("    sudo apt install open-vm-tools open-vm-tools-desktop -y")
        print("    sudo reboot")
        return

    print(f"[*] Guest IP: {c.get_guest_ip()}")
    print(f"[*] 列出 /home:")
    entries = c.list_dir("/home")
    for e in entries:
        tag = "DIR " if e.is_dir else "FILE"
        print(f"  [{tag}] {e.name}")
    print(f"\n[OK] vmrun + guest tools 工作正常！")
