"""双面板文件视图 — 本地 + Guest"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, QDir, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QFileSystemModel
from PyQt6.QtWidgets import (
    QTreeView, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QInputDialog, QMessageBox, QMenu, QHeaderView, QComboBox,
)

from src.workers import Worker


class LocalFileView(QWidget):
    """左侧本地文件浏览"""

    # 双击上传信号：(host_path, guest_target_dir)
    upload_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._current_path = os.path.expanduser("~")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 标题 + 当前路径
        header = QHBoxLayout()
        header.addWidget(QLabel("💻 本地文件"))
        header.addStretch()
        self.path_label = QLabel()
        self.path_label.setStyleSheet("color: #666; font-size: 11px;")
        header.addWidget(self.path_label)
        layout.addLayout(header)

        # 模型 + 视图
        self.model = QFileSystemModel()
        self.model.setRootPath("")
        self.model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot
        )
        self.model.setReadOnly(True)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(False)
        self.tree.setRootIndex(self.model.index(""))
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.hideColumn(3)  # 隐藏修改时间列，太占空间
        self.tree.doubleClicked.connect(self._on_double_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.tree)

        # 工具按钮栏
        btn_bar = QHBoxLayout()

        # 返回上级
        self.back_btn = QPushButton("⬅️ 返回上级")
        self.back_btn.clicked.connect(self._go_parent)
        btn_bar.addWidget(self.back_btn)

        # 驱动器下拉
        btn_bar.addWidget(QLabel("🗂️"))
        self.drive_combo = QComboBox()
        self.drive_combo.setMinimumWidth(90)
        self._populate_drives()
        self.drive_combo.currentIndexChanged.connect(self._on_drive_changed)
        btn_bar.addWidget(self.drive_combo)

        self.home_btn = QPushButton("🏠 家目录")
        self.home_btn.clicked.connect(self._go_home)
        btn_bar.addWidget(self.home_btn)

        self.root_btn = QPushButton("💻 此电脑")
        self.root_btn.clicked.connect(self._go_root)
        btn_bar.addWidget(self.root_btn)

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self._refresh)
        btn_bar.addWidget(self.refresh_btn)

        self.upload_btn = QPushButton("⬆️ 上传选中项 →")
        self.upload_btn.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; padding: 6px 12px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #0b5ed7; }"
        )
        self.upload_btn.clicked.connect(self._upload_selected)
        btn_bar.addWidget(self.upload_btn)

        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        # 初始定位到家目录
        self._go_home()

    def _populate_drives(self):
        """列出所有 Windows 驱动器"""
        import string
        drives = []
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.exists(root):
                try:
                    label = os.path.basename(os.path.abspath(root))
                    drives.append((letter, root))
                except Exception:
                    drives.append((letter, root))
        for letter, root in drives:
            self.drive_combo.addItem(f"{letter}:", root)

    def _on_drive_changed(self, index):
        root = self.drive_combo.itemData(index)
        if root:
            self._navigate_to(root)

    def _go_home(self):
        home = os.path.expanduser("~")
        self._navigate_to(home)
        self._select_drive_for(home)

    def _go_root(self):
        """跳到'此电脑'（所有驱动器列表）"""
        self._navigate_to("")  # QFileSystemModel root
        self.path_label.setText("此电脑")

    def _go_parent(self):
        """返回上一级目录"""
        if self._current_path in ("", "/"):
            return
        parent = os.path.dirname(self._current_path)
        if parent == self._current_path:  # 已经在驱动器根 (C:\)
            self._go_root()
        else:
            self._navigate_to(parent)
        self._select_drive_for(self._current_path)

    def _select_drive_for(self, path: str):
        """根据路径自动选中对应的驱动器下拉项"""
        if len(path) >= 2 and path[1] == ":":
            drive_letter = path[0].upper()
            for i in range(self.drive_combo.count()):
                if self.drive_combo.itemText(i) == f"{drive_letter}:":
                    self.drive_combo.setCurrentIndex(i)
                    break

    def _go_home(self):
        home = os.path.expanduser("~")
        self._navigate_to(home)

    def _navigate_to(self, path: str):
        index = self.model.index(path)
        self.tree.setRootIndex(index)
        self._current_path = path
        self.path_label.setText(path)

    def _refresh(self):
        self._navigate_to(self._current_path)

    def _on_double_click(self, index):
        path = self.model.filePath(index)
        if self.model.isDir(index):
            self._navigate_to(path)
        else:
            # 文件双击 = 发送上传请求
            self.upload_requested.emit(path, "")

    def _get_selected_paths(self) -> list[str]:
        paths = []
        for index in self.tree.selectedIndexes():
            if index.column() == 0:  # 只取第一列，避免重复
                paths.append(self.model.filePath(index))
        return paths

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        upload_act = QAction("⬆️ 上传到 guest", self)
        upload_act.triggered.connect(self._upload_selected)
        menu.addAction(upload_act)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _upload_selected(self):
        paths = self._get_selected_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先选择要上传的文件或目录")
            return
        for p in paths:
            self.upload_requested.emit(p, "")

    # --- 外部接口 ---
    def get_current_path(self) -> str:
        return self._current_path


class GuestFileView(QWidget):
    """右侧 guest 文件浏览 — 基于 vmrun listDirectoryInGuest"""

    download_requested = pyqtSignal(str, str)  # (guest_path, host_target_dir)
    path_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vmrun = None  # VmrunClient，由外部 set_client 注入
        self._current_path = "/"
        self._loading = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 标题 + 路径栏
        header = QHBoxLayout()
        header.addWidget(QLabel("🖥️ Guest 文件"))
        header.addStretch()
        self.path_label = QLabel()
        self.path_label.setStyleSheet("color: #666; font-size: 11px;")
        header.addWidget(self.path_label)
        layout.addLayout(header)

        # 树视图
        self.tree = QTreeView()
        self.tree.setHeaderHidden(False)
        self.tree.setModel(GuestTreeModel(self))
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.doubleClicked.connect(self._on_double_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.tree)

        # 工具按钮
        btn_bar = QHBoxLayout()
        self.connect_btn = QPushButton("🔌 连接 VM")
        self.connect_btn.clicked.connect(self._request_connect)
        btn_bar.addWidget(self.connect_btn)

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.reload)
        btn_bar.addWidget(self.refresh_btn)

        self.mkdir_btn = QPushButton("📁 新建目录")
        self.mkdir_btn.clicked.connect(self._make_dir)
        btn_bar.addWidget(self.mkdir_btn)

        self.back_btn = QPushButton("⬅️ 返回上级")
        self.back_btn.clicked.connect(self._go_parent)
        btn_bar.addWidget(self.back_btn)

        self.download_btn = QPushButton("⬇️ ⬅️ 下载选中项")
        self.download_btn.setStyleSheet(
            "QPushButton { background-color: #198754; color: white; padding: 6px 12px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #157347; }"
        )
        self.download_btn.clicked.connect(self._download_selected)
        btn_bar.addWidget(self.download_btn)

        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        self.path_label.setText(self._current_path)
        self._set_connected(False)

    # ======================================================================
    # 外部接口
    # ======================================================================

    def set_client(self, vmrun_client):
        """设置 VmrunClient 实例"""
        self._vmrun = vmrun_client

    def reload(self):
        """异步重新加载当前目录"""
        if self._vmrun is None or self._loading:
            return
        self._loading = True
        self.tree.setEnabled(False)
        self.path_label.setText(f"{self._current_path}  (加载中...)")

        self._worker = Worker(self._vmrun.list_dir, self._current_path)
        self._worker.signals.finished.connect(self._on_list_done)
        self._worker.signals.error.connect(self._on_list_error)
        self._worker.start()

    def _set_connected(self, connected: bool):
        self._connected = connected
        for btn in [self.refresh_btn, self.mkdir_btn, self.back_btn, self.download_btn]:
            btn.setEnabled(connected)
        if connected:
            self.connect_btn.setText("🔌 已连接")
            self.connect_btn.setEnabled(False)

    def set_connected(self, connected: bool):
        self._set_connected(connected)

    def _request_connect(self):
        """请求主窗口切换/连接 VM — 通过回调查主窗口"""
        if hasattr(self, "on_connect_requested"):
            self.on_connect_requested()

    # ======================================================================
    # list 结果回调
    # ======================================================================

    def _on_list_done(self, entries: list):
        self._loading = False
        self.tree.setEnabled(True)
        model: GuestTreeModel = self.tree.model()
        model.load_entries(self._current_path, entries)
        self.path_label.setText(self._current_path)
        self.path_changed.emit(self._current_path)

    def _on_list_error(self, err: str):
        self._loading = False
        self.tree.setEnabled(True)
        self.path_label.setText(f"{self._current_path}  (加载失败)")
        QMessageBox.warning(self, "加载失败", err)

    # ======================================================================
    # 交互
    # ======================================================================

    def _on_double_click(self, index):
        model: GuestTreeModel = self.tree.model()
        entry = model.entry_at(index)
        if entry and entry.is_dir:
            self._current_path = entry.full_path
            self.reload()
        elif entry:
            # 文件双击 = 下载
            self.download_requested.emit(entry.full_path, "")

    def _get_selected_entries(self) -> list:
        entries = []
        seen = set()
        for index in self.tree.selectedIndexes():
            if index.column() == 0:
                model: GuestTreeModel = self.tree.model()
                entry = model.entry_at(index)
                if entry and id(entry) not in seen:
                    seen.add(id(entry))
                    entries.append(entry)
        return entries

    def _go_parent(self):
        if self._current_path == "/":
            return
        # 用 rsplit("/") 而不是 pathlib.Path —— Windows 上 Path 会把 / 转成 \
        parent = self._current_path.rsplit("/", 1)[0]
        self._current_path = parent if parent else "/"
        self.reload()

    def _make_dir(self):
        name, ok = QInputDialog.getText(self, "新建目录", f"在 {self._current_path} 下创建目录:")
        if not ok or not name.strip():
            return
        path = self._current_path.rstrip("/") + "/" + name.strip()
        self._worker = Worker(self._vmrun.make_dir, path)
        self._worker.signals.finished.connect(lambda _: self.reload())
        self._worker.signals.error.connect(lambda err: QMessageBox.warning(self, "创建失败", err))
        self._worker.start()

    def _download_selected(self):
        entries = self._get_selected_entries()
        if not entries:
            QMessageBox.information(self, "提示", "请先选择要下载的文件或目录")
            return
        # 多个下载时只 emit 第一个所在目录作为 target hint
        target_dir = os.path.expanduser("~")
        for e in entries:
            self.download_requested.emit(e.full_path, target_dir)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        dl_act = QAction("⬇️ 下载到本地", self)
        dl_act.triggered.connect(self._download_selected)
        menu.addAction(dl_act)
        menu.addSeparator()
        del_act = QAction("🗑️ 删除", self)
        del_act.triggered.connect(self._delete_selected)
        menu.addAction(del_act)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _delete_selected(self):
        entries = self._get_selected_entries()
        if not entries:
            return
        names = "\n".join(e.name for e in entries[:5])
        more = f"\n... (等共 {len(entries)} 项)" if len(entries) > 5 else ""
        ret = QMessageBox.question(
            self, "确认删除",
            f"确认从 guest 删除以下条目?\n\n{names}{more}\n\n此操作不可撤销!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        def do_delete():
            for e in entries:
                if e.is_dir:
                    self._vmrun.delete_dir(e.full_path)
                else:
                    self._vmrun.delete_file(e.full_path)

        self._worker = Worker(do_delete)
        self._worker.signals.finished.connect(lambda _: self.reload())
        self._worker.signals.error.connect(lambda err: QMessageBox.warning(self, "删除失败", err))
        self._worker.start()

    # --- 外部: 上传时 guest target dir 应该是当前目录 ---
    def get_current_path(self) -> str:
        return self._current_path


# ======================================================================
# Guest Tree Model
# ======================================================================

from PyQt6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PyQt6.QtGui import QIcon


class GuestTreeModel(QAbstractItemModel):
    """把 listDirectoryInGuest 的 FileEntry 列表显示成三列 Tree"""

    COLUMNS = ["名称", "大小", "类型"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list = []  # FileEntry
        self._path = "/"

    def load_entries(self, path: str, entries: list):
        self.beginResetModel()
        self._path = path
        self._entries = sorted(
            entries,
            key=lambda e: (not e.is_dir, e.name.lower())  # 目录排前面
        )
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(self, parent=QModelIndex()):
        return 3

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return entry.name
            elif col == 1:
                return self._fmt_size(entry.size)
            elif col == 2:
                if entry.is_dir:
                    return "目录"
                elif entry.is_symlink:
                    return "符号链接"
                else:
                    return "文件"
        elif role == Qt.ItemDataRole.DecorationRole and col == 0:
            if entry.is_dir:
                return QIcon.fromTheme("folder")
            else:
                return QIcon.fromTheme("text-x-generic")
        elif role == Qt.ItemDataRole.ToolTipRole:
            return entry.full_path
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]
        return None

    def index(self, row, column, parent=QModelIndex()):
        if parent.isValid() or row >= len(self._entries):
            return QModelIndex()
        return self.createIndex(row, column, self._entries[row])

    def parent(self, index):
        return QModelIndex()  # 扁平列表，无父子

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def entry_at(self, index: QModelIndex):
        """从 model index 里取 FileEntry 对象"""
        if not index.isValid():
            return None
        ptr = index.internalPointer()
        return ptr

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size <= 0:
            return "-"
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
