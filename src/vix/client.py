"""高层 VIX 客户端

把 ctypes bindings 封装成干净的 Python API，对 GUI 暴露:
  - open_host / open_vm / login_guest
  - list_dir / copy_to_guest / copy_from_guest
  - file_exists / dir_exists / make_dir / delete_file
  - power_on / wait_tools

所有异步 VIX 调用通过 wait_job_sync 同步等待结果。
支持 context manager: with VixClient(...) as c:
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .bindings import (
    VixHandle, VIX_INVALID_HANDLE, VIX_OK, VIX_SERVICEPROVIDER_VMWARE_WORKSTATION,
    _to_cstr, _to_null_handle, _null, load_vix,
    wait_job_sync, release_handle,
    VIX_PROPERTY_JOB_RESULT_GUEST_OBJECT_EXISTS,
    VIX_PROPERTY_JOB_RESULT_HANDLE,
)
from .errors import VixError


@dataclass
class FileEntry:
    """guest 端目录条目的数据类"""
    name: str
    full_path: str
    size: int = 0
    is_dir: bool = False
    is_symlink: bool = False
    mod_time: datetime | None = None


class VixClient:
    """单 VM 上下文的 VIX 客户端"""

    def __init__(self, vmx_path: str | None = None, dll_path: str | None = None):
        self._vmx_path = vmx_path
        self._dll_path = dll_path
        self._vix: ctypes.CDLL | None = None
        self._host_handle = VixHandle(VIX_INVALID_HANDLE)
        self._vm_handle = VixHandle(VIX_INVALID_HANDLE)
        self._connected = False

    # ======================================================================
    # context manager
    # ======================================================================

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    # ======================================================================
    # 连接 / 断开
    # ======================================================================

    def open_host(self) -> None:
        """连接本地 VMware Workstation host"""
        if self._connected:
            return
        self._vix = load_vix(self._dll_path)
        host = self._vix.VixHost_Connect(
            -1,                                    # apiVersion = 最新
            VIX_SERVICEPROVIDER_VMWARE_WORKSTATION,
            _to_cstr(None),                        # hostName
            0,                                     # hostPort
            _to_cstr(None),                        # userName
            _to_cstr(None),                        # password
            0,                                     # options
            _to_null_handle(),                     # propertyListHandle
            _null(),                               # callbackProc
            _null(),                               # clientData
        )
        if int(host) == VIX_INVALID_HANDLE:
            raise VixError(3005, "VixHost_Connect 返回 INVALID_HANDLE (VMware Workstation 可能没运行)")
        self._host_handle = host
        self._connected = True

    def open_vm(self, vmx_path: str | None = None) -> None:
        """打开指定 .vmx 文件对应的 VM"""
        path = vmx_path or self._vmx_path
        if not path:
            raise ValueError("必须提供 vmx_path")
        if not Path(path).exists():
            raise FileNotFoundError(f".vmx 文件不存在: {path}")
        self._vmx_path = path

        job = self._vix.VixVM_Open(
            self._host_handle,
            _to_cstr(path),
            _null(),
            _null(),
        )
        wait_job_sync(job)
        # 从 job 里拿真实 vm handle
        self._vm_handle = self._get_job_result_handle(job)
        if int(self._vm_handle) == VIX_INVALID_HANDLE:
            raise VixError(4000, f"打开 VM 失败: {path}")

    def wait_tools(self, timeout_sec: int = 30) -> None:
        """等待 guest VMware Tools 就绪"""
        job = self._vix.VixVM_WaitForToolsInGuest(
            self._vm_handle, ctypes.c_int(timeout_sec), _null(), _null(),
        )
        wait_job_sync(job)

    def login_guest(self, user: str, password: str = "") -> None:
        """通过 guest tools 登录 guest（不是 SSH）"""
        self.wait_tools()
        job = self._vix.VixVM_LoginInGuest(
            self._vm_handle,
            _to_cstr(user),
            _to_cstr(password if password else None),
            0, _null(), _null(),
        )
        wait_job_sync(job)

    def disconnect(self) -> None:
        """断开连接并释放所有 handle"""
        try:
            if int(self._vm_handle) != VIX_INVALID_HANDLE:
                release_handle(self._vm_handle)
                self._vm_handle = VixHandle(VIX_INVALID_HANDLE)
            if int(self._host_handle) != VIX_INVALID_HANDLE:
                self._vix.VixHost_Disconnect(self._host_handle)
                self._host_handle = VixHandle(VIX_INVALID_HANDLE)
        except Exception:
            pass
        self._connected = False

    # ======================================================================
    # Guest 文件 / 目录操作
    # ======================================================================

    def list_dir(self, guest_path: str) -> list[FileEntry]:
        """列出 guest 端指定目录内容。
        内部用 /bin/bash + ls -la 再解析输出（VIX 原生 ListDirectory API 在 1.17 上不稳定）。
        """
        return self._list_dir_via_ls(guest_path)

    def file_exists(self, guest_path: str) -> bool:
        job = self._vix.VixVM_FileExistsInGuest(
            self._vm_handle, _to_cstr(guest_path), _null(), _null(),
        )
        wait_job_sync(job)
        return self._get_job_int_property(job, VIX_PROPERTY_JOB_RESULT_GUEST_OBJECT_EXISTS) != 0

    def dir_exists(self, guest_path: str) -> bool:
        job = self._vix.VixVM_DirectoryExistsInGuest(
            self._vm_handle, _to_cstr(guest_path), _null(), _null(),
        )
        wait_job_sync(job)
        return self._get_job_int_property(job, VIX_PROPERTY_JOB_RESULT_GUEST_OBJECT_EXISTS) != 0

    def make_dir(self, guest_path: str) -> None:
        job = self._vix.VixVM_CreateDirectoryInGuest(
            self._vm_handle, _to_cstr(guest_path), _to_null_handle(), _null(), _null(),
        )
        wait_job_sync(job)

    def delete_file(self, guest_path: str) -> None:
        job = self._vix.VixVM_DeleteFileInGuest(
            self._vm_handle, _to_cstr(guest_path), _null(), _null(),
        )
        wait_job_sync(job)

    # ======================================================================
    # 上传 / 下载
    # ======================================================================

    def copy_to_guest(self, host_path: str, guest_path: str) -> None:
        """上传 host 文件到 guest"""
        if not Path(host_path).exists():
            raise FileNotFoundError(f"host 文件不存在: {host_path}")
        job = self._vix.VixVM_CopyFileFromHostToGuest(
            self._vm_handle,
            _to_cstr(host_path),
            _to_cstr(guest_path),
            0, _to_null_handle(), _null(), _null(),
        )
        wait_job_sync(job)

    def copy_from_guest(self, guest_path: str, host_path: str) -> None:
        """从 guest 下载文件到 host"""
        job = self._vix.VixVM_CopyFileFromGuestToHost(
            self._vm_handle,
            _to_cstr(guest_path),
            _to_cstr(host_path),
            0, _to_null_handle(), _null(), _null(),
        )
        wait_job_sync(job)

    # ======================================================================
    # 电源操作
    # ======================================================================

    def power_on(self) -> None:
        job = self._vix.VixVM_PowerOn(
            self._vm_handle, 0, _to_null_handle(), _null(), _null(),
        )
        wait_job_sync(job)

    # ======================================================================
    # 内部辅助
    # ======================================================================

    def _get_job_result_handle(self, job_handle: VixHandle | int) -> VixHandle:
        """从 VixVM_Open 的 job 中提取真实的 vm handle"""
        out = VixHandle(VIX_INVALID_HANDLE)
        err = self._vix.Vix_GetProperties(
            VixHandle(job_handle),
            VIX_PROPERTY_JOB_RESULT_HANDLE,
            ctypes.byref(out),
        )
        release_handle(job_handle)
        if int(err) != VIX_OK:
            raise VixError(int(err), f"取 VIX_PROPERTY_JOB_RESULT_HANDLE 失败")
        return out

    def _get_job_int_property(self, job_handle: VixHandle | int, prop_id: int) -> int:
        """从 job 取一个 uint64 属性值，然后释放 job"""
        out = ctypes.c_uint64(0)
        err = self._vix.Vix_GetProperties(
            VixHandle(job_handle), prop_id, ctypes.byref(out),
        )
        release_handle(job_handle)
        if int(err) != VIX_OK:
            raise VixError(int(err), f"取属性 {prop_id} 失败")
        return int(out.value)

    def _list_dir_via_ls(self, guest_path: str) -> list[FileEntry]:
        """用 ls -la --time-style=full-iso 列出 guest 目录，解析输出"""
        import re
        import tempfile

        tmp_file = "/tmp/vip_transfer_ls.tmp"
        cmd = f"ls -la --time-style=full-iso {guest_path} > {tmp_file} 2>&1"
        # 通过 /bin/bash -c 执行
        job = self._vix.VixVM_RunProgramInGuest(
            self._vm_handle,
            _to_cstr("/bin/bash"),
            _to_cstr(f"-c '{cmd}'"),
            0, _to_null_handle(), _null(), _null(),
        )
        wait_job_sync(job)

        # 下载到 host 临时文件
        host_tmp = Path(tempfile.gettempdir()) / "vip_transfer_ls.tmp"
        self.copy_from_guest(tmp_file, str(host_tmp))

        # 删除 guest 端临时文件
        try:
            self.delete_file(tmp_file)
        except Exception:
            pass

        # 解析
        entries: list[FileEntry] = []
        LS_PATTERN = re.compile(
            r'^([ldrbcs-])([rwx-]{9})\s+'     # 类型 + 权限
            r'(\d+)\s+'                        # 硬链接数
            r'(\S+)\s+'                        # owner
            r'(\S+)\s+'                        # group
            r'(\d+)\s+'                        # size
            r'(\d{4}-\d{2}-\d{2})\s+'          # date YYYY-MM-DD
            r'(\d{2}:\d{2}:\d{2})\s+'          # time HH:MM:SS
            r'(.+)$'                           # name (可能含空格)
        )
        try:
            with open(host_tmp, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.rstrip("\n")
                    m = LS_PATTERN.match(line)
                    if not m:
                        continue
                    ftype = m.group(1)
                    size = int(m.group(6))
                    d = datetime.strptime(f"{m.group(7)} {m.group(8)}", "%Y-%m-%d %H:%M:%S")
                    name = m.group(9)
                    full = guest_path.rstrip("/") + "/" + name
                    entries.append(FileEntry(
                        name=name,
                        full_path=full,
                        size=size,
                        is_dir=(ftype == "d"),
                        is_symlink=(ftype == "l"),
                        mod_time=d,
                    ))
        finally:
            try:
                host_tmp.unlink()
            except Exception:
                pass

        return entries


def quick_test(vmx_path: str, user: str, password: str = "") -> None:
    """快速连通性测试 — 打印 guest /home 下的文件列表"""
    print(f"[*] 连接 VMware host...")
    with VixClient(vmx_path=vmx_path) as c:
        c.open_host()
        print(f"[*] 打开 VM: {vmx_path}")
        c.open_vm()
        print(f"[*] 等待 guest tools 就绪...")
        c.wait_tools()
        print(f"[*] 登录 guest ({user})...")
        c.login_guest(user, password)
        print(f"[*] 列出 /home 目录:")
        entries = c.list_dir("/home")
        for e in entries:
            tag = "DIR " if e.is_dir else ("LNK " if e.is_symlink else "FILE")
            print(f"  [{tag}] {e.name:<30s} {e.size:>10d}B  {e.mod_time}")
        print(f"\n[OK] 连通性验证通过！guest tools 工作正常。")
