# VMware VIP Transfer — 零 IP 文件传输

> 基于 VMware VIX SDK 的双面板文件传输工具。
> 不用记 IP，不用 SSH，双击连接，即刻传输。

[![EN](https://img.shields.io/badge/EN-English-2ea44f)](./README.md)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-blue)](https://shields.io/)
[![Requires](https://img.shields.io/badge/Requires-VMware%20Workstation%20Pro-orange)](https://shields.io/)
[![Guest](https://img.shields.io/badge/Guest-Ubuntu%20%7C%20CentOS%20%7C%20Debian-green)](https://shields.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](https://shields.io/)

👉 [English Version / 英文版](./README.md)

---

## ✨ 功能亮点

- **零 IP 传输** —— 完全不依赖 DHCP、SSH 端口或网络配置。直接通过 VMware VIX SDK 与虚拟机通讯。
- **双面板 GUI** —— 左侧本地文件树，右侧 Guest 文件树，所见即所得。
- **一键连接** —— 下拉框选择 VM → 点 🔌 连接 → 自动进入 `/home/<user>/`。
- **上传 / 下载** —— 双击文件或用 ⬆️ / ⬇️ 按钮，下载直接存到左侧当前目录。
- **Guest 目录浏览** —— 完整目录树，支持返回上级、新建目录、刷新。
- **批量下发到多 VM** —— 一键把文件同时推送到 config.yaml 里配置的每台 VM（并发执行）。
- **智能类型识别** —— Guest 面板里 📁 目录 / 📄 文件 清晰区分（directoryExistsInGuest 并行探测）。
- **通用 Guest 支持** —— Ubuntu 20.04+、22.04+、24.04+、CentOS 7+、RHEL 8+、Debian 11+ —— 只要装了 `open-vm-tools` 都能用。

---

## 📦 前置条件

| 组件 | 版本 | 说明 |
|---|---|---|
| **VMware Workstation Pro** | 16+ | 本项目在 17.6.2 上测试通过 |
| **VMware Guest Tools** | `open-vm-tools` + `open-vm-tools-desktop` | 每台 Guest VM 里都要装 |
| **Windows 宿主机** | Windows 10 / 11，x64 | `.exe` 在宿主机上运行 |
| **Guest VM 操作系统** | Ubuntu 20.04+, CentOS 7+, Debian 11+ | 任何装了 open-vm-tools 的 Linux |
| **VM 必须处于运行状态** | — | Guest Tools 需在运行中才能通讯 |

### Guest VM 初始化（Ubuntu 示例）

```bash
sudo apt update
sudo apt install -y open-vm-tools open-vm-tools-desktop
sudo reboot
```

验证 Tools 运行状态：
```bash
vmware-toolbox-cmd -v          # 打印版本号 = 已启用
vmtoolsd --version             # 同上
```

---

## 🚀 快速开始

### 方式 A：使用预编译 EXE

直接把 `dist/VIPTransfer.exe` 拷出来双击运行。**无需安装 Python，无需 pip install。**

### 方式 B：从源码构建

```bash
git clone <本仓库地址>
cd vmware-vip-transfer
pip install PyQt6 PyYAML pyinstaller
pyinstaller --noconfirm --onefile --windowed --name VIPTransfer ^
    --icon icon.ico ^
    --add-data "dll;dll" ^
    --add-data "icon.ico;." ^
    --add-data "config.example.yaml;." ^
    --paths src ^
    src/main.py
# 产物: dist/VIPTransfer.exe
```

### 方式 C：开发者模式（直接跑源码）

```bash
pip install PyQt6 PyYAML
python src/main.py
```

---

### 配置你的 VM 列表

复制 `config.example.yaml` 为 `config.yaml`（**放在 exe 同级目录**）：

```yaml
# config.yaml —— 放在 VIPTransfer.exe 旁边

# vmrun_path: 如果留空会自动搜索 VMware Workstation 默认安装目录
vmrun_path: "C:/VMware/VMware Workstation/vmrun.exe"

vms:
  - name: "Master"                                        # GUI 下拉框显示的名字
    vmx_path: "C:/Virtual Machines/master1/master.vmx"    # .vmx 文件完整路径
    guest_user: "your_guest_name"                          # Guest 里的登录用户名
    guest_password: "your_guest_password"                  # Guest 用户密码（和 SSH 用的一样）
    default_guest_dir: "/home/your_guest_name"             # 可选：连接后默认进入的目录

  - name: "Slave1"
    vmx_path: "C:/Virtual Machines/slave1/slave1.vmx"
    guest_user: "your_guest_name"
    guest_password: "your_guest_password"

  - name: "Clave2"
    vmx_path: "C:/Virtual Machines/slave2/slave2.vmx"
    guest_user: "your_guest_name"
    guest_password: "your_guest_password"
```

### 操作指南

1. **启动** `VIPTransfer.exe`
2. **下拉选择** 一台 VM（比如 Master）
3. **点击 🔌 连接** —— 顶部变绿 `IP: 192.168.x.x  Tools: running`，右侧 Guest 面板自动加载 `/home/your_guest_name/`
4. **⬆️ 上传** —— 左侧选中本地文件 → 点 "上传选中项"
5. **⬇️ 下载** —— 右侧双击 Guest 文件（或选中后点 "下载选中项"）→ 自动保存到左侧当前目录
6. **🖥️ 批量下发** —— 左侧选中文件 → 点顶部紫色 "批量下发到所有 VM" 按钮 → 并发推送到每台 VM

---

## 🎯 典型使用场景

### Hadoop 集群课程搭建

```
Master (NameNode + ResourceManager)
  ├── hadoop-3.5.0.tar.gz   ← VIP Transfer 上传
  ├── hive-site.xml
  └── slaves 配置文件

Slave1 (DataNode + NodeManager)
Slave2 (DataNode + NodeManager)
  ↑ 同一个 tarball，一次批量下发覆盖所有 slave
```

### 日常 DevOps
- 重启前把最新 `.jar` 推到 3 节点集群
- 把所有 slave 的测试日志拉到本地
- Python 脚本同步到每台 VM

---

## 🔧 技术原理

```
┌────────────────────── Windows 宿主机 ──────────────────────┐
│                                                             │
│   VIPTransfer.exe   ──subprocess──▶  vmrun.exe              │
│    (PyQt6 GUI)                         (VIX SDK CLI 封装)    │
│                                        │                    │
│                                        │  VIX 专有 socket    │
│                                        │  (不走 SSH 端口)    │
│                                        ▼                    │
│                         VMware Workstation (宿主进程)        │
│                                        │                    │
│                                        │  Guest Tools       │
│                                        ▼                    │
│   ┌──────────────── Guest VM (Ubuntu) ───────────────┐     │
│   │  open-vm-tools (vmtoolsd)                         │     │
│   │  ├── listDirectoryInGuest      → ls              │     │
│   │  ├── CopyFileFromHostToGuest   → scp host→guest   │     │
│   │  ├── CopyFileFromGuestToHost   → scp guest→host   │     │
│   │  ├── directoryExistsInGuest    → test -d          │     │
│   │  └── runProgramInGuest         → guest 内执行命令  │     │
│   └───────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

**核心思想**：VMware Guest Tools 在 Guest VM **内部**运行，并保持一条回宿主机的持久连接。VIX SDK 通过这条隧道直接通讯 —— 你永远不需要知道 Guest 的 IP 地址。这就是 DHCP 漂移不影响使用的原因。

---

## 📋 兼容性矩阵

| 场景 | 支持 | 备注 |
|---|---|---|
| Win10 x64 + VMware WS 17 | ✅ | 主要测试平台 |
| Win11 x64 + VMware WS 16/17 | ✅ | |
| Ubuntu 20.04 / 22.04 / 24.04 guest | ✅ | 需要 open-vm-tools |
| CentOS 7 / RHEL 8 / Rocky 9 guest | ✅ | `yum install open-vm-tools` |
| Debian 11 / 12 guest | ✅ | `apt install open-vm-tools` |
| 单 exe 管理多台 VM | ✅ | config.yaml 任意条目数 |
| 每台 VM 独立用户名 | ✅ | 各 VM 配自己的 `guest_user` |
| 每台 VM 独立默认目录 | ✅ | 用 `default_guest_dir` |
| 宿主机断网 | ❌ | VIX 需要 VMware Workstation 服务 |
| 远程宿主机上的 VM | ❌ | 目前只支持本地 VMware Workstation |
| VMware Player（免费版）| ⚠️ | 未测试，要看 Player 是否带 VIX SDK |
| VMware ESXi / vSphere | ❌ | 完全不同的 API，需要 vSphere SDK |

---

## 🗂️ 项目结构

```
vmware-vip-transfer/
├── src/
│   ├── main.py                # 应用入口点
│   ├── app_config.py          # VMConfig / AppConfig 数据类
│   ├── config.py              # YAML 加载器（含 PyInstaller _MEIPASS 支持）
│   ├── vmrun_client.py        # vmrun.exe subprocess 封装 ⭐ 核心
│   ├── workers.py             # QThread 后台任务
│   ├── ui/
│   │   ├── main_window.py     # 主窗口：连接、进度条、日志
│   │   └── file_views.py      # LocalFileView + GuestFileView（双面板）
│   └── vix/                   # 已弃用的 VIX ctypes 绑定（备用）
├── dll/
│   ├── vix.dll                # VIX SDK 17.6.2
│   ├── iconv.dll
│   ├── libssl-3-x64.dll
│   ├── libcrypto-3-x64.dll
│   ├── libxml2.dll
│   └── zlib1.dll
├── dist/
│   └── VIPTransfer.exe        # 最终交付物：单文件 exe
├── config.example.yaml        # 配置模板 —— 复制为 config.yaml
├── requirements.txt           # PyYAML（运行时）+ PyQt6/PyInstaller（构建时）
├── icon.ico                   # 应用图标
└── README.md / README_ZH.md   # 本文件
```

---

## ❓ 常见问题

### Q: 为什么用 vmrun subprocess 而不是 VIX C API 直接绑？
VIX SDK 提供 `vix.dll` 和 C 头文件。我们试过 ctypes 绑定 —— `VixHost_Connect()` **直接让 Python 进程崩溃，没有任何异常抛出**。CLI 封装器 `vmrun.exe` 是 VMware 官方推荐的接口，subprocess 调用稳定可靠。代价是每次调用有几百 ms 的进程启动开销。

### Q: 为什么 `list_dir` 扫描目录要 6 秒？
vmrun 的 `listDirectoryInGuest` 不区分文件/目录，所以需要对每个条目再调一次 `directoryExistsInGuest`。每个 vmrun subprocess 冷启动 ~800ms。我们用 8 线程并行，27 个条目 = ceil(27/8) × 800ms ≈ 2.7s + 开销 ≈ 6s。目录浏览场景可以接受。

### Q: 为什么 `runProgramInGuest` 抓不到 stdout？
VIX SDK 是异步 Job 模式 —— 你需要 `VixJob_Wait` 后再调 `Vix_GetProperties(job, VIX_PROPERTY_JOB_RESULT_GUEST_PROGRAM_EXIT_CODE)`。vmrun.exe 捕获的是 **它自己的 CLI** 的输出，不是 Guest 里程序的 stdout。如果要抓 Guest 输出，得在 Guest 里重定向到临时文件，再 `CopyFileFromGuestToHost` 下载回来。

### Q: VMware Player（免费版）能用吗？
未测试。历史上 Player 砍掉了 VIX SDK 支持。如果新版 Player 又带了 `vmrun.exe` 和 VIX DLLs，理论上能用。**确认支持的目标是 VMware Workstation Pro。**

### Q: Linux 宿主机能用吗？
不能。`vmrun.exe` + PyInstaller `--onefile` (Windows) 只能在 Windows 上跑。Linux 上 VIX SDK 的 CLI 叫 `vmrun`（没有 .exe），路径探测逻辑要改。欢迎 PR。

### Q: config.yaml 放哪里？
**放在 VIPTransfer.exe 旁边。** 这是第一个搜索路径。如果没找到，依次 fallback 到 PyInstaller `_MEIPASS`（内嵌默认）、`~/.vip-transfer/config.yaml`。

### Q: VM 换了 IP / DHCP 变了，需要更新配置吗？
**完全不需要。** 这就是本工具的核心价值 —— 你永远不输入 IP 地址。VIX SDK 只通过 `.vmx` 路径连接。

---

## 🐛 已知限制

1. **传输进度不可见** —— vmrun 没有进度回调，进度条只能在完成瞬间跳满。
2. **subprocess 启动开销** —— 每次 `vmrun` 调用都 spawn 一个新进程（冷启动 ~800ms）。`list_dir` 用并行化缓解了这个问题。
3. **无法中途取消** —— vmrun subprocess 必须跑完，我们显示一个警告提示。
4. **大目录扫描** —— 200+ 条目 = 200 次 `directoryExistsInGuest` 调用，即使并行也要 ~20s。
5. **Guest 文件大小显示 `-`** —— vmrun 不返回文件大小，GuestFileView 的 size 列全是占位。
6. **Windows 路径陷阱** —— GuestFileView 的 `_go_parent` 必须用 `str.rsplit("/")`，**绝对不能用 `pathlib.Path.parent`**。`Path("/home/user").parent` 在 Windows 上返回 `\home`（反斜杠！），vmrun 收到这个就报 "该对象不是一个目录"。

---

## 🤝 欢迎贡献

PR 欢迎！以下方向还需要人做：

- [ ] 真正的传输进度条（需要监控临时文件大小增长）
- [ ] 批量下发支持目录递归（Guest 内 tar 打包）
- [ ] ESXi / vSphere 支持（需要 vSphere SDK）
- [ ] VMware Player 兼容性测试
- [ ] Linux 宿主机移植

---

## 📄 许可证

MIT License —— 见 `LICENSE` 文件。

---

## 🙏 致谢

- [VMware VIX SDK](https://developer.vmware.com/apis/1218/vix) —— 本工具的魔法内核
- [PyQt6](https://www.riverbankcomputing.com/static/Docs/PyQt6/) —— GUI 框架
- [PyInstaller](https://pyinstaller.org/) —— 单文件 exe 打包
