# VMware VIP Transfer — Zero-IP File Transfer

> A dual-panel file transfer tool for VMware virtual machines on Windows.  
> No DHCP. No SSH. No IP addresses. Click **Connect** and transfer files.

[![中文](https://img.shields.io/badge/中文-Chinese-2ea44f)](./README_ZH.md)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-blue)](https://shields.io/)
[![Requires](https://img.shields.io/badge/Requires-VMware%20Workstation%20Pro-orange)](https://shields.io/)
[![Guest](https://img.shields.io/badge/Guest-Ubuntu%20%7C%20CentOS%20%7C%20Debian-green)](https://shields.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](https://shields.io/)

👉 [中文版本 / Chinese Version](./README_ZH.md)

---

## ✨ Features

- **Zero-IP Transfer** — No DHCP, no SSH ports, no network config required. Communicates directly with VMware VIX SDK.
- **Dual-Panel GUI** — Local filesystem on the left, Guest filesystem on the right. What you see is what you transfer.
- **One-Click Connect** — Select VM from dropdown → click 🔌 Connect → auto-lands in `/home/<user>/`.
- **Upload / Download** — Double-click files or use ⬆️ / ⬇️ buttons. Downloads go straight to the left panel's current directory.
- **Guest File Browsing** — Full directory tree with back-to-parent, create folder, refresh.
- **Multi-VM Batch Deploy** — One click to push files to **ALL** VMs in `config.yaml` simultaneously (parallel execution).
- **Smart Type Detection** — Guest panel clearly distinguishes 📁 directories from 📄 files (parallel `directoryExistsInGuest` probing).
- **Universal Guest Support** — Ubuntu 20.04+/22.04+/24.04+, CentOS 7+, RHEL 8+, Debian 11+ — anything with `open-vm-tools`.

---

## 📦 Prerequisites

| Component | Version | Notes |
|---|---|---|
| **VMware Workstation Pro** | 16+ | Tested on 17.6.2 |
| **VMware Guest Tools** | `open-vm-tools` + `open-vm-tools-desktop` | Install inside **every** guest VM |
| **Windows Host** | Windows 10 / 11, x64 | Where the `.exe` runs |
| **Guest VM OS** | Ubuntu 20.04+, CentOS 7+, Debian 11+ | Any Linux with open-vm-tools |
| **VM Must Be Running** | — | Guest Tools must be active |

### Guest VM Setup (Ubuntu example)

```bash
sudo apt update
sudo apt install -y open-vm-tools open-vm-tools-desktop
sudo reboot
```

Verify tools are running:
```bash
vmware-toolbox-cmd -v          # prints version = working
vmtoolsd --version             # same
```

---

## 🚀 Quick Start

### Option A — Use Pre-built EXE

Just grab `dist/VIPTransfer.exe` and double-click. **No Python needed. No pip install.**

### Option B — Build from Source

```bash
git clone <this-repo-url>
cd vmware-vip-transfer
pip install PyQt6 PyYAML pyinstaller
pyinstaller --noconfirm --onefile --windowed --name VIPTransfer ^
    --icon icon.ico ^
    --add-data "dll;dll" ^
    --add-data "icon.ico;." ^
    --add-data "config.example.yaml;." ^
    --paths src ^
    src/main.py
# Output: dist/VIPTransfer.exe
```

### Option C — Developer Mode (run from source)

```bash
pip install PyQt6 PyYAML
python src/main.py
```

---

### Configure Your VMs

Copy `config.example.yaml` to `config.yaml` (**place it next to the exe**):

```yaml
# config.yaml — place THIS file next to VIPTransfer.exe

# vmrun_path: omitted → auto-searches VMware Workstation install dirs
vmrun_path: "C:/VMware/VMware Workstation/vmrun.exe"

vms:
  - name: "Master"                                        # Display name in dropdown
    vmx_path: "C:/Virtual Machines/master1/master.vmx"    # Full path to .vmx file
    guest_user: "your_guest_name"                          # Guest OS login user
    guest_password: "your_guest_password"                  # Same password you SSH with
    default_guest_dir: "/home/your_guest_name"             # Optional: lands here after connect

  - name: "Slave1"
    vmx_path: "C:/Virtual Machines/slave1/slave1.vmx"
    guest_user: "your_guest_name"
    guest_password: "your_guest_password"

  - name: "Slave2"
    vmx_path: "C:/Virtual Machines/slave2/slave2.vmx"
    guest_user: "your_guest_name"
    guest_password: "your_guest_password"
```

### How to Use

1. **Launch** `VIPTransfer.exe`
2. **Select** a VM from the dropdown (e.g., Master)
3. **Click 🔌 Connect** — top bar turns green `IP: 192.168.x.x  Tools: running`, right panel auto-loads `/home/your_guest_name/`
4. **⬆️ Upload** — select local file on the left → click "Upload Selected"
5. **⬇️ Download** — double-click guest file on the right (or select + "Download Selected") → saves to left panel's current directory
6. **🖥️ Batch Deploy** — select files on the left → click the purple "Batch Deploy to All VMs" button → pushes to every VM in parallel

---

## 🎯 Use Cases

### Hadoop Cluster Setup (the original motivation)

```
Master (NameNode + ResourceManager)
  ├── hadoop-3.5.0.tar.gz   ← uploaded via VIP Transfer
  ├── hive-site.xml
  └── slaves config

Slave1 (DataNode + NodeManager)
Slave2 (DataNode + NodeManager)
  ↑ Same tarball pushed to ALL slaves with ONE batch click
```

### Daily DevOps
- Push updated `.jar` to a 3-node cluster before rolling restart
- Pull test logs from all slaves to a local folder
- Sync Python scripts to every VM in the fleet

---

## 🔧 How It Works

```
┌────────────────────── Windows Host ──────────────────────┐
│                                                           │
│   VIPTransfer.exe   ──subprocess──▶  vmrun.exe            │
│    (PyQt6 GUI)                         (VIX SDK CLI)       │
│                                        │                  │
│                                        │  VIX proprietary  │
│                                        │  socket (no SSH) │
│                                        ▼                  │
│                         VMware Workstation (host process)  │
│                                        │                  │
│                                        │  Guest Tools      │
│                                        ▼                  │
│   ┌──────────────── Guest VM (Ubuntu) ───────────────┐   │
│   │  open-vm-tools (vmtoolsd)                         │   │
│   │  ├── listDirectoryInGuest      → ls              │   │
│   │  ├── CopyFileFromHostToGuest   → scp host→guest   │   │
│   │  ├── CopyFileFromGuestToHost   → scp guest→host   │   │
│   │  ├── directoryExistsInGuest    → test -d          │   │
│   │  └── runProgramInGuest         → exec in guest    │   │
│   └───────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
```

**Key insight**: VMware Guest Tools runs **inside the guest VM** and maintains a persistent tunnel back to the host. VIX SDK talks over that tunnel directly — you never see an IP address. That's why DHCP drift doesn't matter.

---

## 📋 Compatibility Matrix

| Scenario | Works? | Notes |
|---|---|---|
| Win10 x64 + VMware WS 17 | ✅ | Primary target |
| Win11 x64 + VMware WS 16/17 | ✅ | |
| Ubuntu 20.04 / 22.04 / 24.04 guest | ✅ | Requires open-vm-tools |
| CentOS 7 / RHEL 8 / Rocky 9 guest | ✅ | `yum install open-vm-tools` |
| Debian 11 / 12 guest | ✅ | `apt install open-vm-tools` |
| Single exe managing multiple VMs | ✅ | `config.yaml` takes any count |
| Different guest users per VM | ✅ | Each VM has its own `guest_user` |
| Different default directories | ✅ | Per-VM `default_guest_dir` |
| Network-disconnected host | ❌ | VIX needs VMware Workstation service |
| VMs on remote hosts | ❌ | Local VMware Workstation only |
| VMware Player (free) | ⚠️ | Untested; depends on VIX SDK inclusion |
| VMware ESXi / vSphere | ❌ | Entirely different API — needs vSphere SDK |

---

## 🗂️ Project Structure

```
vmware-vip-transfer/
├── src/
│   ├── main.py                # App entry point
│   ├── app_config.py          # VMConfig / AppConfig dataclasses
│   ├── config.py              # YAML loader with PyInstaller _MEIPASS support
│   ├── vmrun_client.py        # vmrun.exe subprocess wrapper ⭐ core
│   ├── workers.py             # QThread background tasks
│   ├── ui/
│   │   ├── main_window.py     # MainWindow: connect + progress + log
│   │   └── file_views.py      # LocalFileView + GuestFileView (dual panel)
│   └── vix/                   # Abandoned VIX ctypes bindings (fallback)
├── dll/
│   ├── vix.dll                # VIX SDK 17.6.2
│   ├── iconv.dll
│   ├── libssl-3-x64.dll
│   ├── libcrypto-3-x64.dll
│   ├── libxml2.dll
│   └── zlib1.dll
├── dist/
│   └── VIPTransfer.exe        # Final deliverable: single-file exe
├── config.example.yaml        # Template — copy to config.yaml
├── requirements.txt           # PyYAML (runtime) + PyQt6/PyInstaller (build-time)
├── icon.ico                   # App icon
└── README.md / README_ZH.md   # This file
```

---

## ❓ FAQ

### Q: Why vmrun subprocess instead of VIX C API directly?
VIX SDK ships as `vix.dll` and C headers. We tried ctypes bindings — `VixHost_Connect()` **crashes the Python process with no exception**. The CLI wrapper `vmrun.exe` is VIX's officially supported interface and works reliably as a subprocess. Tradeoff: slightly higher overhead (~800ms cold start per call).

### Q: Why does `list_dir` take ~6 seconds?
vmrun's `listDirectoryInGuest` doesn't distinguish files from directories, so we probe each entry with `directoryExistsInGuest`. Each vmrun subprocess cold-starts in ~800ms. We parallelize 8 at once, so 27 entries = ceil(27/8) × 800ms ≈ 2.7s + overhead ≈ 6s. Acceptable for directory browsing.

### Q: Why doesn't `runProgramInGuest` return stdout?
VIX SDK has async job semantics — you poll with `VixJob_Wait` then call `Vix_GetProperties(job, VIX_PROPERTY_JOB_RESULT_GUEST_PROGRAM_EXIT_CODE)`. vmrun.exe captures stdout of **its own CLI**, not the guest program's. If you need guest output, redirect inside the guest to a temp file then `CopyFileFromGuestToHost`.

### Q: Can I use this with VMware Player?
Untested. Player historically stripped VIX SDK support. If a modern Player ships `vmrun.exe` and VIX DLLs, it should work. **Confirmed target: VMware Workstation Pro.**

### Q: Does it work with Linux host?
No. `vmrun.exe` + PyInstaller `--onefile` (Windows mode) is Windows-only. The VIX SDK CLI is `vmrun` on Linux too, but you'd need VMware Workstation for Linux and path detection adjustments. PRs welcome.

### Q: Where do I put config.yaml?
**Next to VIPTransfer.exe.** That's the first path searched. Fallbacks: PyInstaller's `_MEIPASS` (embedded default), then `~/.vip-transfer/config.yaml`.

### Q: My VM got a new IP from DHCP — do I need to update anything?
**No.** That's the whole point. You never enter an IP address. VIX SDK connects by `.vmx` path only.

---

## 🐛 Known Limitations

1. **No progress reporting on transfers** — vmrun gives no progress callback, so the progress bar fills instantly on completion.
2. **Subprocess spawn overhead** — Each `vmrun` call is a new process (~800ms cold). Parallelism mitigates this for `list_dir`.
3. **Can't cancel mid-transfer** — vmrun subprocess must run to completion. We show a warning instead.
4. **Large directory listing** — 200+ entries = 200 `directoryExistsInGuest` calls, even in parallel takes ~20s.
5. **No file sizes** — GuestFileView shows `-` in size column (vmrun doesn't return it).
6. **Windows path gotcha** — GuestFileView's `_go_parent` must use `str.rsplit("/")`, **NOT** `pathlib.Path.parent`. `Path("/home/user").parent` on Windows returns `\home`, not `/home`.

---

## 🤝 Contributing

PRs welcome! Areas that need work:

- [ ] Actual progress bar for file transfers (monitor temp file size growth)
- [ ] Recursive directory batch deploy (tar inside guest)
- [ ] ESXi / vSphere support (vSphere SDK)
- [ ] VMware Player compatibility testing
- [ ] Linux host port

---

## 📄 License

MIT License — see `LICENSE` file.

---

## 🙏 Acknowledgments

- [VMware VIX SDK](https://developer.vmware.com/apis/1218/vix) — the magic behind this tool
- [PyQt6](https://www.riverbankcomputing.com/static/Docs/PyQt6/) — the GUI framework
- [PyInstaller](https://pyinstaller.org/) — for the single-file exe
