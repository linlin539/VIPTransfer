"""全局配置 + 连接信息"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import load_config


@dataclass
class VMConfig:
    """单个 VM 的配置"""
    name: str
    vmx_path: str
    guest_user: str
    guest_password: str = ""
    default_guest_dir: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VMConfig":
        return cls(
            name=data.get("name") or Path(data["vmx_path"]).parent.name,
            vmx_path=data["vmx_path"],
            guest_user=data.get("guest_user", "root"),
            guest_password=data.get("guest_password", ""),
            default_guest_dir=data.get("default_guest_dir", ""),
        )


@dataclass
class AppConfig:
    """全局配置"""
    vms: list[VMConfig] = field(default_factory=list)
    vmrun_path: str | None = None

    @classmethod
    def load(cls, path: str | None = None) -> "AppConfig":
        data = load_config(path)
        vms_data = data.get("vms", [])
        vms = [VMConfig.from_dict(v) for v in vms_data]
        return cls(
            vms=vms,
            vmrun_path=data.get("vmrun_path"),
        )
