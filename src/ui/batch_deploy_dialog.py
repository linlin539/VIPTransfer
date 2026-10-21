"""批量下发目标目录确认对话框 —— 每台 VM 单独设置保存位置"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDialogButtonBox, QScrollArea, QWidget, QFrame,
)

from .guest_browser import GuestBrowserDialog


class BatchDeployDialog(QDialog):
    """批量下发目标目录对话框

    对 config.yaml 里的每台 VM 显示一行，让用户确认/修改 guest 端目标目录。
    """

    def __init__(self, vms: list, files: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("🖥️ 批量下发 — 确认保存位置")
        self.setMinimumSize(520, 440)

        self._vms = vms
        self._files = files

        # 每台 VM 的目标目录标签: vm_name -> QLabel
        self._path_labels: dict[str, QLabel] = {}
        self._browser_callback = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 顶部说明
        file_names = [os.path.basename(f) for f in self._files]
        file_list_str = "\n".join(f"  · {n}" for n in file_names[:5])
        more = "" if len(file_names) <= 5 else f"\n  ... 等 {len(file_names)} 个文件"

        header = QLabel(
            f"即将下发 <b>{len(self._files)}</b> 个文件到 <b>{len(self._vms)}</b> 台 VM：\n"
            f"<pre style='color:#666'>{file_list_str}{more}</pre>\n"
            f"请确认每台 VM 上的保存目标目录（留空则用默认值）："
        )
        header.setWordWrap(True)
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # VM 列表区域（带滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)

        for vm in self._vms:
            vm_row = QHBoxLayout()

            # VM 名称
            vm_name_label = QLabel(f"<b>{vm.name}</b>")
            vm_name_label.setMinimumWidth(90)
            vm_name_label.setToolTip(f"VMX: {vm.vmx_path}")
            vm_row.addWidget(vm_name_label)

            # guest 目录标签
            vm_row.addWidget(QLabel("📁"))

            default_dir = vm.default_guest_dir or f"/home/{vm.guest_user}"

            path_label = QLabel(default_dir)
            path_label.setStyleSheet(
                "QLabel { background: #eef; padding: 5px 8px; border: 1px solid #ccd; border-radius: 4px; "
                "font-family: monospace; color: #444; }"
            )
            path_label.setCursor(Qt.CursorShape.PointingHandCursor)
            path_label.setToolTip("点击 Browse 选择目录")
            vm_row.addWidget(path_label, 1)

            browse_btn = QPushButton("📁 浏览...")
            browse_btn.setStyleSheet(
                "QPushButton { padding: 5px 10px; border: 1px solid #aaa; border-radius: 4px; }"
                "QPushButton:hover { background: #f0f0f0; }"
            )
            vm_cfg = vm
            def _browse(_checked, v=vm_cfg, lbl=path_label):
                # _checked = clicked 信号传的 bool（忽略）
                if self._browser_callback:
                    self._browser_callback(v, lbl)
            browse_btn.clicked.connect(_browse)
            vm_row.addWidget(browse_btn)

            self._path_labels[vm.name] = path_label

            scroll_layout.addLayout(vm_row)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # 快捷按钮
        shortcut_bar = QHBoxLayout()
        use_home_btn = QPushButton("全部设为 /home/<user>")
        use_home_btn.clicked.connect(self._use_home_for_all)
        shortcut_bar.addWidget(use_home_btn)

        use_config_btn = QPushButton("恢复 config.yaml 默认值")
        use_config_btn.clicked.connect(self._restore_config_defaults)
        shortcut_bar.addWidget(use_config_btn)

        shortcut_bar.addStretch()
        layout.addLayout(shortcut_bar)

        # 按钮
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("🚀 开始下发")
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(
            "QPushButton { background-color: #6f42c1; color: white; padding: 8px 20px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #5a32a3; }"
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _use_home_for_all(self):
        """快捷：所有 VM 设为 /home/<guest_user>"""
        for vm in self._vms:
            lbl = self._path_labels[vm.name]
            lbl.setText(f"/home/{vm.guest_user}")

    def _restore_config_defaults(self):
        """快捷：恢复 config.yaml 里的 default_guest_dir"""
        for vm in self._vms:
            lbl = self._path_labels[vm.name]
            lbl.setText(vm.default_guest_dir or f"/home/{vm.guest_user}")

    def set_browser_runner(self, runner):
        """Inject callable (vm_cfg, path_label) → opens GuestBrowserDialog
        and updates path_label.setText(selected_path) on accept.
        """
        self._browser_callback = runner

    def get_target_dirs(self) -> dict[str, str]:
        """返回每台 VM 的目标目录: {vm_name: guest_dir}"""
        result = {}
        for vm in self._vms:
            lbl = self._path_labels[vm.name]
            text = lbl.text().strip()
            if not text:
                text = vm.default_guest_dir or f"/home/{vm.guest_user}"
            result[vm.name] = text.rstrip("/")
        return result
