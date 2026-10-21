"""Guest 目录浏览器 —— 批量下发时选目标文件夹用的小模态窗口"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeView, QMessageBox, QApplication,
)

from src.vmrun_client import VmrunClient


class GuestBrowserDialog(QDialog):
    """浏览 guest 文件系统并选择一个目录（同步加载，2秒级）"""

    def __init__(self, vmrun_client: VmrunClient, start_path: str = "/",
                 vm_name: str = "", parent=None):
        super().__init__(parent)
        self.vm = vmrun_client
        self._selected_path: str | None = None

        title = f"选择 {vm_name} 的目标目录" if vm_name else "选择 Guest 目录"
        self.setWindowTitle(title)
        self.resize(480, 520)

        layout = QVBoxLayout(self)

        # 当前路径
        self.path_label = QLabel(start_path)
        self.path_label.setStyleSheet(
            "background: #f0f0f0; padding: 6px 10px; border-radius: 4px; "
            "font-family: monospace; color: #333;"
        )
        self._current_path = start_path
        layout.addWidget(self.path_label)

        # 树视图
        self.tree = QTreeView()
        self.tree.setHeaderHidden(True)
        self.tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.tree.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tree, 1)

        # 底部按钮
        btn_row = QHBoxLayout()

        self.back_btn = QPushButton("⬅️ 返回上级")
        self.back_btn.clicked.connect(self._go_parent)
        btn_row.addWidget(self.back_btn)

        btn_row.addStretch()

        self.select_btn = QPushButton("🗂️ 选此目录")
        self.select_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 6px 16px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #218838; }"
        )
        self.select_btn.clicked.connect(self._select_current)
        btn_row.addWidget(self.select_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

        # 初始加载（同步，vmrun 2秒级）
        self.reload()

    # --- 树数据绑定（同步）---

    def reload(self):
        """同步加载当前目录内容 —— 不卡 GUI（用 processEvents 保持响应）"""
        self.path_label.setText(f"{self._current_path}  (加载中...)")
        self.tree.setEnabled(False)
        QApplication.processEvents()

        try:
            entries = self.vm.list_dir(self._current_path)
            self._populate_tree(entries)
        except Exception as err:
            self.path_label.setText(f"{self._current_path}  (加载失败)")
            QMessageBox.warning(self, "加载失败", str(err))

    def _populate_tree(self, entries: list):
        self.tree.setEnabled(True)
        self.path_label.setText(self._current_path)

        model = QStandardItemModel()
        for e in entries:
            icon = "📁" if e.is_dir else "📄"
            item = QStandardItem(f"{icon}  {e.name}")
            item.setData(e, Qt.ItemDataRole.UserRole)
            item.setEditable(False)
            model.appendRow(item)

        self.tree.setModel(model)

    # --- 导航 ---

    def _on_double_click(self, index):
        model = self.tree.model()
        if not model:
            return
        item = model.itemFromIndex(index)
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if data and data.is_dir:
            self._current_path = data.full_path
            self.reload()

    def _go_parent(self):
        if self._current_path == "/":
            return
        parent = self._current_path.rsplit("/", 1)[0]
        self._current_path = parent if parent else "/"
        self.reload()

    def _select_current(self):
        self._selected_path = self._current_path
        self.accept()

    def get_selected_path(self) -> str | None:
        return self._selected_path
