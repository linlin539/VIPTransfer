"""Qt Worker 线程 — 把耗时的 vmrun 调用放后台，不卡 GUI"""
from __future__ import annotations

import traceback
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.vmrun_client import VmrunClient, VmrunError, FileEntry


# ======================================================================
# 通用 Worker（跑任意 callable）
# ======================================================================

class WorkerSignals(QObject):
    finished = pyqtSignal(object)        # 返回值
    error = pyqtSignal(str)              # 错误消息
    progress = pyqtSignal(str)           # 进度文字


class Worker(QThread):
    """通用后台线程，执行 target(*args, **kwargs)"""

    def __init__(self, target, *args, **kwargs):
        super().__init__()
        self._target = target
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self._target(*self._args, **self._kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            tb = traceback.format_exc()
            self.signals.error.emit(f"{e}\n\n{tb}")
