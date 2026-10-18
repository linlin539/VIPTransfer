"""VIX SDK ctypes 绑定层

直接用 ctypes 加载 vix.dll，声明函数签名。
所有 VIX 异步函数都有 VixEventProc* callbackProc 参数。
ctypes 传 null callback 时直接用 c_void_p(0) 最简洁，
所以 argtypes 里 callbackProc 统一声明为 c_void_p。
"""
from __future__ import annotations

import ctypes
from ctypes import c_int, c_char_p, c_uint64, c_uint32, POINTER, c_void_p
from pathlib import Path
from typing import Any

from .errors import VixError


# =============================================================================
# 基础类型定义
# =============================================================================

VixHandle = c_uint64
VixError = c_uint32
VixPropertyID = c_int
VixServiceProvider = c_int

VIX_INVALID_HANDLE = 0xFFFFFFFFFFFFFFFF
VIX_OK = 0
VIX_SERVICEPROVIDER_VMWARE_WORKSTATION = 2  # local Workstation

VIX_PROPERTY_NONE = 0
VIX_PROPERTY_VM_TOOLS_STATE = 152
VIX_PROPERTY_VM_POWER_STATE = 129
VIX_PROPERTY_JOB_RESULT_ERROR_CODE = 3000
VIX_PROPERTY_JOB_RESULT_HANDLE = 3010
VIX_PROPERTY_JOB_RESULT_GUEST_OBJECT_EXISTS = 3011
VIX_PROPERTY_JOB_RESULT_COMMAND_OUTPUT = 3005
VIX_PROPERTY_JOB_RESULT_EXIT_CODE = 3004

# =============================================================================
# 全局 DLL 句柄
# =============================================================================

_vix_dll: ctypes.CDLL | None = None


def _null_cb() -> c_void_p:
    """返回 null callback 指针"""
    return c_void_p(0)


def load_vix(dll_path_hint: str | None = None) -> ctypes.CDLL:
    """加载 vix.dll 并设置好所有函数签名。返回 ctypes.CDLL。"""
    global _vix_dll
    if _vix_dll is not None:
        return _vix_dll

    candidates: list[Path] = []
    if dll_path_hint:
        candidates.append(Path(dll_path_hint))

    # 相对当前文件
    here = Path(__file__).resolve().parent
    candidates.append(here.parent.parent / "dll" / "vix.dll")
    candidates.append(here.parent.parent.parent / "dll" / "vix.dll")

    # PyInstaller 解压目录
    import sys
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.append(base / "vix.dll")
        candidates.append(Path(sys.executable).parent / "vix.dll")

    for p in candidates:
        if p.exists():
            try:
                import os
                dll_dir = str(p.parent)
                os.add_dll_directory(dll_dir)
                _vix_dll = ctypes.CDLL(str(p))
                _setup_signatures(_vix_dll)
                return _vix_dll
            except Exception:
                _vix_dll = None
                continue

    raise FileNotFoundError(
        f"找不到 vix.dll，已搜索:\n  " + "\n  ".join(str(c) for c in candidates)
    )


def _setup_signatures(vix: ctypes.CDLL) -> None:
    """声明所有用到的 VIX 函数签名"""

    # VixHandle VixHost_Connect(int apiVersion, VixServiceProvider hostType,
    #   const char *hostName, int hostPort, const char *userName, const char *password,
    #   VixHostOptions options, VixHandle propertyListHandle,
    #   VixEventProc *callbackProc, void *clientData);
    vix.VixHost_Connect.restype = VixHandle
    vix.VixHost_Connect.argtypes = [
        c_int,         # apiVersion (-1 = latest)
        VixServiceProvider,
        c_char_p,      # hostName
        c_int,         # hostPort
        c_char_p,      # userName
        c_char_p,      # password
        c_uint32,      # options
        VixHandle,     # propertyListHandle
        c_void_p,      # callbackProc (null = 0)
        c_void_p,      # clientData (null = 0)
    ]

    vix.VixHost_Disconnect.restype = None
    vix.VixHost_Disconnect.argtypes = [VixHandle]

    # VixHandle VixVM_Open(VixHandle hostHandle, const char *vmxFilePathName,
    #   VixEventProc *callbackProc, void *clientData);
    vix.VixVM_Open.restype = VixHandle
    vix.VixVM_Open.argtypes = [VixHandle, c_char_p, c_void_p, c_void_p]

    # VixHandle VixVM_WaitForToolsInGuest(VixHandle vmHandle, int timeoutInSeconds,
    #   VixEventProc *callbackProc, void *clientData);
    vix.VixVM_WaitForToolsInGuest.restype = VixHandle
    vix.VixVM_WaitForToolsInGuest.argtypes = [VixHandle, c_int, c_void_p, c_void_p]

    # VixHandle VixVM_LoginInGuest(VixHandle vmHandle, const char *userName,
    #   const char *password, int options, VixEventProc *callbackProc, void *clientData);
    vix.VixVM_LoginInGuest.restype = VixHandle
    vix.VixVM_LoginInGuest.argtypes = [
        VixHandle, c_char_p, c_char_p, c_int, c_void_p, c_void_p,
    ]

    # VixHandle VixVM_LogoutFromGuest(VixHandle vmHandle, VixEventProc *callbackProc, void *clientData);
    vix.VixVM_LogoutFromGuest.restype = VixHandle
    vix.VixVM_LogoutFromGuest.argtypes = [VixHandle, c_void_p, c_void_p]

    # VixHandle VixVM_CopyFileFromHostToGuest(VixHandle vmHandle, const char *hostPathName,
    #   const char *guestPathName, int options, VixHandle propertyListHandle,
    #   VixEventProc *callbackProc, void *clientData);
    vix.VixVM_CopyFileFromHostToGuest.restype = VixHandle
    vix.VixVM_CopyFileFromHostToGuest.argtypes = [
        VixHandle, c_char_p, c_char_p, c_int, VixHandle, c_void_p, c_void_p,
    ]

    # VixHandle VixVM_CopyFileFromGuestToHost(...)
    vix.VixVM_CopyFileFromGuestToHost.restype = VixHandle
    vix.VixVM_CopyFileFromGuestToHost.argtypes = [
        VixHandle, c_char_p, c_char_p, c_int, VixHandle, c_void_p, c_void_p,
    ]

    # VixHandle VixVM_ListDirectoryInGuest(...)
    vix.VixVM_ListDirectoryInGuest.restype = VixHandle
    vix.VixVM_ListDirectoryInGuest.argtypes = [
        VixHandle, c_char_p, c_int, c_void_p, c_void_p,
    ]

    # VixHandle VixVM_FileExistsInGuest(...)
    vix.VixVM_FileExistsInGuest.restype = VixHandle
    vix.VixVM_FileExistsInGuest.argtypes = [VixHandle, c_char_p, c_void_p, c_void_p]

    # VixHandle VixVM_DirectoryExistsInGuest(...)
    vix.VixVM_DirectoryExistsInGuest.restype = VixHandle
    vix.VixVM_DirectoryExistsInGuest.argtypes = [VixHandle, c_char_p, c_void_p, c_void_p]

    # VixHandle VixVM_CreateDirectoryInGuest(...)
    vix.VixVM_CreateDirectoryInGuest.restype = VixHandle
    vix.VixVM_CreateDirectoryInGuest.argtypes = [
        VixHandle, c_char_p, VixHandle, c_void_p, c_void_p,
    ]

    # VixHandle VixVM_DeleteFileInGuest(...)
    vix.VixVM_DeleteFileInGuest.restype = VixHandle
    vix.VixVM_DeleteFileInGuest.argtypes = [VixHandle, c_char_p, c_void_p, c_void_p]

    # VixHandle VixVM_DeleteDirectoryInGuest(...)
    vix.VixVM_DeleteDirectoryInGuest.restype = VixHandle
    vix.VixVM_DeleteDirectoryInGuest.argtypes = [VixHandle, c_char_p, c_void_p, c_void_p]

    # VixHandle VixVM_RunProgramInGuest(VixHandle vmHandle, const char *guestProgramName,
    #   const char *commandLineArgs, int options, VixHandle propertyListHandle,
    #   VixEventProc *callbackProc, void *clientData);
    vix.VixVM_RunProgramInGuest.restype = VixHandle
    vix.VixVM_RunProgramInGuest.argtypes = [
        VixHandle, c_char_p, c_char_p, c_int, VixHandle, c_void_p, c_void_p,
    ]

    # VixHandle VixVM_PowerOn(...)
    vix.VixVM_PowerOn.restype = VixHandle
    vix.VixVM_PowerOn.argtypes = [VixHandle, c_int, VixHandle, c_void_p, c_void_p]

    # VixError VixJob_Wait(VixHandle jobHandle, VixPropertyID firstPropertyID, ...);
    # varargs 函数在 ctypes 中需要单独设置
    vix.VixJob_Wait.restype = VixError
    vix.VixJob_Wait.argtypes = [VixHandle]

    # VixError VixJob_GetError(VixHandle jobHandle);
    vix.VixJob_GetError.restype = VixError
    vix.VixJob_GetError.argtypes = [VixHandle]

    # int VixJob_GetNumProperties(VixHandle jobHandle, int resultPropertyID);
    vix.VixJob_GetNumProperties.restype = c_int
    vix.VixJob_GetNumProperties.argtypes = [VixHandle, c_int]

    # VixError Vix_GetProperties(VixHandle handle, VixPropertyID firstPropertyID, ...);
    vix.Vix_GetProperties.restype = VixError
    vix.Vix_GetProperties.argtypes = [VixHandle, c_int]

    # void Vix_ReleaseHandle(VixHandle handle);
    vix.Vix_ReleaseHandle.restype = None
    vix.Vix_ReleaseHandle.argtypes = [VixHandle]

    # const char *Vix_GetErrorText(VixError err, const char *locale);
    vix.Vix_GetErrorText.restype = c_char_p
    vix.Vix_GetErrorText.argtypes = [VixError, c_char_p]


# =============================================================================
# 工具函数
# =============================================================================

def _to_cstr(s: str | None) -> c_char_p:
    """Python str / None → c_char_p (null terminated bytes 或 NULL)"""
    if s is None or s == "":
        return c_char_p(None)
    return s.encode("utf-8")


def _to_null_handle() -> VixHandle:
    return VixHandle(VIX_INVALID_HANDLE)


def _null() -> c_void_p:
    """返回 null 指针给 callbackProc 参数"""
    return c_void_p(0)


def _check(err: int | VixError) -> int:
    """检查 VIX 返回值是否为 VIX_OK，否则抛 VixError"""
    code = int(err)
    if code != VIX_OK:
        raise VixError(code)
    return code


# =============================================================================
# Job 同步等待辅助
# =============================================================================

def wait_job_sync(job_handle: VixHandle | int) -> None:
    """同步等待异步 Job 完成，成功返回，失败抛 VixError。"""
    if not job_handle or int(job_handle) == VIX_INVALID_HANDLE:
        raise VixError(1, "Invalid job handle returned from VIX call")
    vix = load_vix()
    # VixJob_Wait(jobHandle, VIX_PROPERTY_NONE); // 等完成但不取属性
    err = vix.VixJob_Wait(VixHandle(job_handle), c_int(VIX_PROPERTY_NONE))
    _check(err)
    # 再取 job 自己的错误码
    job_err = vix.VixJob_GetError(VixHandle(job_handle))
    release_handle(job_handle)
    if int(job_err) != VIX_OK:
        raise VixError(int(job_err))


def release_handle(handle: VixHandle | int) -> None:
    """安全释放 handle"""
    if handle is None:
        return
    h = VixHandle(handle)
    if int(h) != VIX_INVALID_HANDLE:
        try:
            vix = load_vix()
            vix.Vix_ReleaseHandle(h)
        except Exception:
            pass
