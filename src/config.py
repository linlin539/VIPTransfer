"""配置加载模块"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml


def _search_config_paths(explicit_path: str | None = None) -> list[Path]:
    """返回按优先级排序的配置文件搜索路径列表。
    
    优先级:
      1. explicit_path（如果传了）
      2. exe 所在目录（PyInstaller 打包后最重要，用户改的 config.yaml 放这）
      3. 当前工作目录
      4. 用户目录 ~/.vip-transfer/config.yaml
      5. PyInstaller _MEIPASS 临时目录（打包时内嵌的默认 config.yaml）
    """
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path))

    # 2. exe / 脚本 所在目录 —— 打包后用户改的 config.yaml 应该和 exe 放一起
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后 sys.executable 是 exe 路径
        exe_dir = Path(sys.executable).parent
    else:
        # 开发模式：main.py 所在目录的上级（即 vmware-vip-transfer/）
        exe_dir = Path(__file__).resolve().parent.parent
    candidates.append(exe_dir / "config.yaml")
    candidates.append(exe_dir / "config.example.yaml")

    # 3. 当前工作目录（exe 可能被快捷方式从别的目录启动）
    cwd = Path.cwd()
    if cwd != exe_dir:
        candidates.append(cwd / "config.yaml")

    # 4. 用户目录
    home = Path.home()
    candidates.append(home / ".vip-transfer" / "config.yaml")

    # 5. PyInstaller _MEIPASS（打包内嵌的默认配置，优先级最低）
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "config.yaml")

    # 去重
    seen = set()
    unique = []
    for p in candidates:
        sp = str(p.resolve())
        if sp not in seen:
            seen.add(sp)
            unique.append(p)
    return unique


def load_config(path: str | None = None) -> dict[str, Any]:
    """加载 yaml 配置文件，返回 dict。找不到抛 FileNotFoundError。"""
    candidates = _search_config_paths(path)
    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            cfg["_config_path"] = str(p)
            _validate_config(cfg)
            return cfg
    raise FileNotFoundError(
        f"找不到 config.yaml，已搜索:\n  "
        + "\n  ".join(str(p) for p in candidates)
        + "\n请复制 config.example.yaml 为 config.yaml 后修改"
    )


def _validate_config(cfg: dict[str, Any]) -> None:
    """基本校验"""
    vms = cfg.get("vms")
    if not vms or not isinstance(vms, list):
        raise ValueError("config.yaml 必须包含 vms 列表")
    for i, vm in enumerate(vms):
        if not vm.get("name"):
            raise ValueError(f"vms[{i}] 缺少 name")
        if not vm.get("vmx_path"):
            raise ValueError(f"vms[{i}] ({vm.get('name')}) 缺少 vmx_path")
        if not Path(vm["vmx_path"]).exists():
            raise FileNotFoundError(
                f"vms[{i}] ({vm['name']}) 的 vmx_path 不存在: {vm['vmx_path']}"
            )
