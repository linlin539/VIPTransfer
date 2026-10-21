"""主窗口"""
from __future__ import annotations

import os
import shutil
import traceback
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QPushButton, QProgressBar, QMessageBox, QSplitter, QFileDialog,
    QStatusBar, QTextEdit, QFrame, QDialog,
)

from src.app_config import AppConfig, VMConfig
from src.vmrun_client import VmrunClient, VmrunError
from src.workers import Worker
from src.ui.file_views import LocalFileView, GuestFileView


class MainWindow(QMainWindow):
    """WinSCP 风格双面板主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VMware VIP Transfer — 零 IP 文件传输")
        self.resize(1200, 750)

        self._app_config: AppConfig | None = None
        self._vmrun: VmrunClient | None = None
        self._current_vm: VMConfig | None = None

        self._build_ui()
        self._load_config()

    # ======================================================================
    # UI 构建
    # ======================================================================

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # --- 顶部 VM 选择栏 ---
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("<b>🖥️ 虚拟机:</b>"))
        self.vm_combo = QComboBox()
        self.vm_combo.setMinimumWidth(250)
        self.vm_combo.currentIndexChanged.connect(self._on_vm_selected)
        top_bar.addWidget(self.vm_combo)

        self.connect_btn = QPushButton("🔌 连接")
        self.connect_btn.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; padding: 8px 20px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0b5ed7; }"
            "QPushButton:disabled { background-color: #6c757d; }"
        )
        self.connect_btn.clicked.connect(self._connect_vm)
        top_bar.addWidget(self.connect_btn)

        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: #888;")
        top_bar.addWidget(self.status_label)

        top_bar.addStretch()

        # 批量模式
        self.batch_btn = QPushButton("🖥️ 批量下发到所有 VM")
        self.batch_btn.setToolTip("同时连接 config.yaml 里所有 VM，把选中的文件/目录下发到每台机器")
        self.batch_btn.setStyleSheet(
            "QPushButton { background-color: #6f42c1; color: white; padding: 6px 16px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #5a32a3; }"
        )
        self.batch_btn.clicked.connect(self._batch_deploy)
        top_bar.addWidget(self.batch_btn)

        self.refresh_vms_btn = QPushButton("🔄 刷新 VM 列表")
        self.refresh_vms_btn.clicked.connect(self._refresh_vm_list)
        top_bar.addWidget(self.refresh_vms_btn)

        main_layout.addLayout(top_bar)

        # --- 分隔线 ---
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        # --- 双面板 ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.local_view = LocalFileView()
        self.local_view.upload_requested.connect(self._handle_upload)
        splitter.addWidget(self.local_view)

        self.guest_view = GuestFileView()
        self.guest_view.download_requested.connect(self._handle_download)
        splitter.addWidget(self.guest_view)

        splitter.setSizes([600, 600])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 1)

        # --- 进度条 + 日志 ---
        bottom_bar = QVBoxLayout()

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        progress_row.addWidget(self.progress_bar, 1)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_current_op)
        progress_row.addWidget(self.cancel_btn)
        bottom_bar.addLayout(progress_row)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(120)
        self.log_view.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas, monospace; font-size: 12px; }"
        )
        bottom_bar.addWidget(self.log_view)

        main_layout.addLayout(bottom_bar)

        # --- 状态栏 ---
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪 — 选择 VM 后点「连接」")

    # ======================================================================
    # 配置加载 + VM 列表
    # ======================================================================

    def _load_config(self):
        try:
            self._app_config = AppConfig.load()
        except Exception as e:
            self._log(f"⚠️ 加载 config.yaml 失败: {e}")
            self._app_config = AppConfig(vms=[])
        self._refresh_vm_list()

    def _refresh_vm_list(self):
        self.vm_combo.clear()
        if self._app_config and self._app_config.vms:
            for vm in self._app_config.vms:
                self.vm_combo.addItem(f"{vm.name}  ({vm.vmx_path})", vm)
            self._log(f"已加载 {len(self._app_config.vms)} 个 VM 配置")
        else:
            # 试试自动发现 vmrun list
            self.vm_combo.addItem("(无配置 — 请在 config.yaml 添加 VM)", None)
            self._log("未找到 VM 配置，请在 config.yaml 里添加")

    def _on_vm_selected(self, index):
        data = self.vm_combo.itemData(index)
        if isinstance(data, VMConfig):
            self._current_vm = data
            self.status_label.setText(f"选中: {data.name}")
            self.status_label.setStyleSheet("color: #0d6efd;")
            # 切换 VM 时重置连接状态
            self._reset_connection()
        else:
            self._current_vm = None

    # ======================================================================
    # 连接 VM
    # ======================================================================

    def _connect_vm(self):
        if self._current_vm is None:
            QMessageBox.warning(self, "提示", "请先选择一个 VM")
            return

        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("连接中...")
        self.statusBar().showMessage(f"正在连接 {self._current_vm.name}...")

        def do_connect():
            client = VmrunClient(
                vmx_path=self._current_vm.vmx_path,
                guest_user=self._current_vm.guest_user,
                guest_password=self._current_vm.guest_password,
                vmrun_path=self._app_config.vmrun_path if self._app_config else None,
            )
            # 先测 tools state
            state = client.check_tools_state()
            ip = client.get_guest_ip() if state.strip().lower() == "running" else "N/A"
            return (client, state, ip)

        self._connect_worker = Worker(do_connect)
        self._connect_worker.signals.finished.connect(self._on_connect_done)
        self._connect_worker.signals.error.connect(self._on_connect_error)
        self._connect_worker.start()

    def _on_connect_done(self, result):
        client, state, ip = result
        self._vmrun = client
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("✅ 已连接")
        self.connect_btn.setStyleSheet(
            "QPushButton { background-color: #198754; color: white; padding: 8px 20px; border-radius: 4px; font-weight: bold; }"
        )
        self.status_label.setText(f"IP: {ip}  Tools: {state}")
        self.status_label.setStyleSheet("color: #198754; font-weight: bold;")
        self.guest_view.set_client(self._vmrun)
        self.guest_view.set_connected(True)
        self.statusBar().showMessage(f"已连接 {self._current_vm.name} — IP {ip}")
        self._log(f"✅ 已连接 {self._current_vm.name}")
        self._log(f"   Guest IP: {ip}  Tools: {state}")

        # 自动跳到 user 的 home 目录
        default_dir = self._current_vm.default_guest_dir or f"/home/{self._current_vm.guest_user}"
        self._log(f"   进入默认目录: {default_dir}")
        self.guest_view._current_path = default_dir
        self.guest_view.reload()

    def _on_connect_error(self, err: str):
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("🔌 连接")
        self.statusLabel.setText("连接失败")
        self.statusLabel.setStyleSheet("color: #dc3545;")
        self.statusBar().showMessage("连接失败")
        self._log(f"❌ 连接失败: {err}")
        QMessageBox.critical(self, "连接失败", err)

    def _reset_connection(self):
        """重置连接状态 —— 切换 VM 下拉时调用"""
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("🔌 连接")
        self.connect_btn.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; padding: 8px 20px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0b5ed7; }"
            "QPushButton:disabled { background-color: #6c757d; }"
        )
        self.status_label.setText("未连接")
        self.status_label.setStyleSheet("color: #888;")
        self._vmrun = None
        self.guest_view.set_client(None)
        self.guest_view.set_connected(False)
        self.guest_view._current_path = "/"
        self.guest_view.reload()
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("")

    # ======================================================================
    # 上传 / 下载
    # ======================================================================

    def _handle_upload(self, host_path: str, guest_target_dir: str):
        if self._vmrun is None:
            QMessageBox.warning(self, "提示", "请先连接 VM")
            return

        target_dir = guest_target_dir or self.guest_view.get_current_path()
        host_p = Path(host_path)
        if not host_p.exists():
            QMessageBox.warning(self, "提示", f"本地文件不存在: {host_path}")
            return

        if host_p.is_dir():
            QMessageBox.information(
                self, "提示",
                f"暂不支持直接上传目录。\n"
                f"请先把目录打包成 tar.gz 再上传，然后在 guest 里解压:\n"
                f"  tar -xzf {host_p.name}.tar.gz\n"
            )
            return

        guest_target = target_dir.rstrip("/") + "/" + host_p.name
        self._log(f"⬆️ 上传: {host_path} → {guest_target}")
        self._run_transfer("upload", host_path, guest_target)

    def _handle_download(self, guest_path: str, host_target_dir: str):
        if self._vmrun is None:
            QMessageBox.warning(self, "提示", "请先连接 VM")
            return

        guest_p = Path(guest_path)
        filename = guest_p.name

        # 下载目标 = 左侧当前目录（不弹窗）
        target_dir = self.local_view.get_current_path()
        host_target = os.path.join(target_dir, filename)

        # 避免覆盖
        if os.path.exists(host_target):
            ret = QMessageBox.question(
                self, "文件已存在",
                f"{host_target}\n\n已存在，是否覆盖?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                return

        self._log(f"⬇️ 下载: {guest_path} → {host_target}")
        self._run_transfer("download", guest_path, host_target)

    def _run_transfer(self, direction: str, src: str, dst: str):
        self.progress_bar.setVisible(True)
        self.cancel_btn.setVisible(True)
        self.statusBar().showMessage(f"{direction}: {Path(src).name} ...")

        def do_transfer():
            if direction == "upload":
                self._vmrun.copy_to_guest(src, dst)
            else:
                self._vmrun.copy_from_guest(src, dst)
            return dst

        self._transfer_worker = Worker(do_transfer)
        self._transfer_worker.signals.finished.connect(self._on_transfer_done)
        self._transfer_worker.signals.error.connect(self._on_transfer_error)
        self._transfer_worker.start()

    def _on_transfer_done(self, result):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.statusBar().showMessage(f"✅ 完成: {result}")
        self._log(f"✅ 完成 → {result}")
        # 刷新两边目录
        self.guest_view.reload()
        self.local_view._refresh()

    def _on_transfer_error(self, err: str):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.statusBar().showMessage("传输失败")
        self._log(f"❌ 传输失败: {err}")
        QMessageBox.warning(self, "传输失败", err)

    def _cancel_current_op(self):
        # vmrun subprocess 不支持中途取消，只能等它跑完
        self._log("⚠️ vmrun 不支持取消，正在等待当前操作完成...")

    # ======================================================================
    # 批量下发
    # ======================================================================

    def _batch_deploy(self):
        """把左侧选中的文件同时下发到所有已配置 VM"""
        if not self._app_config or not self._app_config.vms:
            QMessageBox.warning(self, "提示", "config.yaml 里没有 VM 配置")
            return

        # 从左侧拿选中的文件
        selected = self.local_view._get_selected_paths()
        if not selected:
            QMessageBox.information(
                self, "提示",
                "请先在左侧本地文件列表里选中要下发的文件。"
            )
            return

        files = [p for p in selected if os.path.isfile(p)]
        dirs = [p for p in selected if os.path.isdir(p)]

        if dirs:
            names = "\n".join(os.path.basename(d) for d in dirs)
            ret = QMessageBox.question(
                self, "目录下发",
                f"以下目录不能直接下发:\n{names}\n\n是否跳过这些目录，只下发文件?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                return

        if not files:
            QMessageBox.warning(self, "提示", "没有可下发的文件")
            return

        # 弹对话框让用户确认每台 VM 的目标目录
        from src.ui.batch_deploy_dialog import BatchDeployDialog
        from src.ui.guest_browser import GuestBrowserDialog
        dlg = BatchDeployDialog(self._app_config.vms, files, parent=self)

        def open_browser_for_vm(vm_cfg, path_label):
            client = VmrunClient(
                vmx_path=vm_cfg.vmx_path,
                guest_user=vm_cfg.guest_user,
                guest_password=vm_cfg.guest_password,
            )
            browser = GuestBrowserDialog(
                client,
                start_path=path_label.text().strip() or "/",
                vm_name=vm_cfg.name,
                parent=dlg,
            )
            if browser.exec() == QDialog.DialogCode.Accepted:
                selected = browser.get_selected_path()
                if selected:
                    path_label.setText(selected)

        dlg.set_browser_runner(open_browser_for_vm)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # 用户确认后的目标目录
        target_dirs = dlg.get_target_dirs()

        # 日志开头
        self._log(f"\n{'='*50}")
        self._log(f"🚀 开始批量下发 {len(files)} 个文件 → {len(self._app_config.vms)} 台 VM")
        for vm_name, dir_path in target_dirs.items():
            self._log(f"  📁 [{vm_name}] 目标目录: {dir_path}")

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def deploy_one(vm_cfg: VMConfig, host_path: str) -> tuple:
            """单个文件下发到单个 VM"""
            try:
                client = VmrunClient(
                    vmx_path=vm_cfg.vmx_path,
                    guest_user=vm_cfg.guest_user,
                    guest_password=vm_cfg.guest_password,
                )
                state = client.check_tools_state().strip().lower()
                if state != "running":
                    return (vm_cfg.name, host_path, False, f"Tools 状态: {state}")

                # 使用用户确认后的目标目录（不是 default_guest_dir）
                target_dir = target_dirs.get(vm_cfg.name) or f"/home/{vm_cfg.guest_user}"
                target = target_dir.rstrip("/") + "/" + os.path.basename(host_path)
                client.copy_to_guest(host_path, target)
                return (vm_cfg.name, target, True, "OK")
            except Exception as e:
                return (vm_cfg.name, host_path, False, str(e))

        results = []
        with ThreadPoolExecutor(max_workers=min(8, len(self._app_config.vms))) as pool:
            futures = []
            for vm_cfg in self._app_config.vms:
                for f in files:
                    futures.append(pool.submit(deploy_one, vm_cfg, f))
            for fut in as_completed(futures):
                results.append(fut.result())

        # 汇总
        self._log(f"\n📊 批量下发结果:")
        ok_count = sum(1 for r in results if r[2])
        fail_count = sum(1 for r in results if not r[2])
        for vm_name, target, success, msg in sorted(results):
            tag = "✅" if success else "❌"
            self._log(f"  {tag} [{vm_name}] → {target}  ({msg})")
        self._log(f"\n总计: {ok_count} 成功 / {fail_count} 失败")

        self.statusBar().showMessage(f"批量下发完成: {ok_count} OK, {fail_count} 失败")

    # ======================================================================
    # 日志
    # ======================================================================

    def _log(self, msg: str):
        self.log_view.append(msg)
        # 自动滚到底
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ======================================================================
    # 关闭
    # ======================================================================

    def closeEvent(self, event):
        if self._vmrun:
            try:
                self._log("断开 VM 连接...")
            except Exception:
                pass
        super().closeEvent(event)
