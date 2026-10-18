"""VIX 错误定义"""
from __future__ import annotations


# 常用 VIX 错误码
VIX_ERRORS: dict[int, str] = {
    0: "OK",
    1: "Generic error",
    3000: "Host not found or unreachable",
    3001: "Host already connected",
    3002: "Cannot connect to local host",
    3003: "Permission denied on host",
    3004: "Host connection lost",
    3005: "Host connection refused (VMware not running?)",
    4000: "VM not found",
    4001: "VM already running",
    4002: "VM not running",
    4003: "VM not powered on",
    5000: "Guest operations unavailable (VMware Tools not ready)",
    5001: "Guest login failed (wrong username/password?)",
    5002: "Guest command execution failed",
    5003: "Guest command timeout",
    5004: "Guest cannot create temp file",
    6000: "File not found in guest",
    6001: "File already exists",
    6002: "Permission denied (guest)",
    6003: "Cannot open file (guest)",
    9000: "VIX version unsupported",
    10000: "Out of memory",
}


class VixError(Exception):
    """VIX SDK 操作异常"""

    def __init__(self, code: int, msg: str = ""):
        self.code = int(code)
        self.msg = msg or VIX_ERRORS.get(self.code, f"Unknown VIX error {code}")
        super().__init__(f"VixError[{self.code}]: {self.msg}")
