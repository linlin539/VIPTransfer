"""VIP Transfer — 主入口点"""
import os
import sys
from pathlib import Path

# 保证 PyInstaller 打包后能找到资源
if getattr(sys, "frozen", False):
    # PyInstaller 打包后：资源在 _MEIPASS，工作目录是 exe 所在目录
    _APP_DIR = Path(sys.executable).parent
    _MEIPASS = Path(getattr(sys, "_MEIPASS", str(_APP_DIR)))
else:
    _APP_DIR = Path(__file__).resolve().parent.parent
    _MEIPASS = _APP_DIR

# 两者都加进 path 找 icon
for p in (_APP_DIR, _MEIPASS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _find_icon() -> str:
    """在 exe 同目录、_MEIPASS、或源码目录找 icon.ico"""
    candidates = [
        _APP_DIR / "icon.ico",
        _MEIPASS / "icon.ico",
        Path(__file__).resolve().parent / "icon.ico",  # fallback
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return ""


from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("VMware VIP Transfer")
    app.setOrganizationName("VIPTransfer")

    # 加载应用图标 —— 同时影响任务栏和窗口标题栏
    icon_path = _find_icon()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.resize(1100, 700)
    if icon_path:
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
