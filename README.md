# Rat-Workbench
<img width="1918" height="1016" alt="屏幕截图 2026-04-03 131545" src="https://github.com/user-attachments/assets/ffef6f6d-13fc-41c4-b0f4-72e33ace46ab" />
<img width="1919" height="1014" alt="屏幕截图 2026-04-03 092740" src="https://github.com/user-attachments/assets/640ee836-1f73-448a-8114-2f155d37b72d" />

`Rat-Workbench` is a Windows-first helper repository for working with the open-source Project-Rat ecosystem.

This repository tracks the workspace helper layer only:

- the desktop GUI launcher
- PowerShell bootstrap and build scripts
- the portable packaging workflow
- documentation for setting up a fresh machine

It does not vendor the upstream Project-Rat repositories, Python virtual environments, tool caches, or local build artifacts. Those are created locally by the bootstrap scripts.

## What Is In This Repository

- `project_rat_gui.py`: Python launcher that selects the local GUI runtime
- `project_rat_gui_qt.py`: Qt desktop GUI
- `project_rat_cct.py`: CCT-related helper logic used by the GUI
- `scripts/setup_project_rat_runtime.ps1`: creates a lightweight Python runtime for the GUI
- `scripts/bootstrap_project_rat_workspace.ps1`: clones upstream repositories and downloads portable tools
- `scripts/project_rat_manager.ps1`: workspace management, vcpkg bootstrap, builds, and examples
- `workspace-overlays/rat-vcpkg/ports/*`: local overlay ports and compatibility overrides synced into `rat-vcpkg`
- `.github/workflows/build-portable.yml`: GitHub Actions workflow for building a portable package

## One-Click Start

On a fresh Windows machine, clone this repository and double-click:

```powershell
.\Run-Project-RAT.bat
```

That entry point will:

1. create `.qt-venv` if it does not exist
2. install the GUI dependencies from `requirements-gui.txt`
3. launch the desktop GUI

The GUI runtime uses:

- `PySide6`
- `vtk`

If Python is missing and `winget` is available, the runtime setup script will attempt to install Python 3.12 in user scope first.

## Workspace Bootstrap

If you want the full Project-Rat workspace on a new machine, run:

```powershell
.\Bootstrap-Workspace.bat
```

That script will:

- clone the upstream open-source repositories into the workspace root
- sync the repository's local `rat-vcpkg` overlay snapshot into the cloned `rat-vcpkg`
- clone `vcpkg`
- download portable `ninja` and `cmake`
- download the Visual Studio Build Tools installer bootstrapper to `tools\vs_BuildTools.exe`

After that, if you want local C++ builds, install Visual Studio Build Tools with the `Desktop development with C++` workload and then run:

```powershell
.\scripts\project_rat_manager.ps1 -Action bootstrap-vcpkg
```

## Common Commands

Check workspace status:

```powershell
.\scripts\project_rat_manager.ps1 -Action status
```

Install Project-Rat libraries with the NL solver:

```powershell
.\scripts\project_rat_manager.ps1 -Action install-rat-models
```

Install Project-Rat libraries without the NL solver:

```powershell
.\scripts\project_rat_manager.ps1 -Action install-rat-models-no-nl
```

Build an example:

```powershell
.\scripts\project_rat_manager.ps1 -Action build-example -Example dmshyoke1
```

Build the `pyrat` wheel:

```powershell
.\scripts\project_rat_manager.ps1 -Action build-pyrat-wheel
```

## Proxy Behavior

Build and bootstrap commands no longer force a local proxy.

Default behavior:

- if your current environment already has `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, or `NO_PROXY`, the script inherits them
- if no proxy environment variables are present, commands run direct

You can also override that behavior explicitly:

```powershell
.\scripts\project_rat_manager.ps1 -Action bootstrap-vcpkg -ProxyUrl http://127.0.0.1:7897
.\scripts\project_rat_manager.ps1 -Action bootstrap-vcpkg -DisableProxy
```

To inspect the effective mode on a machine, run:

```powershell
.\scripts\project_rat_manager.ps1 -Action status
```

## Portable Package

This repository includes a GitHub Actions workflow that builds a Windows portable package.

Workflow:

- `.github/workflows/build-portable.yml`

It produces a zip artifact containing the packaged GUI and the supporting scripts. You can also build it locally with:

```powershell
.\scripts\build_portable_bundle.ps1 -WorkspaceRoot $PWD -BundleProfile AppOnly -Clean
```

Available bundle profiles:

- `AppOnly`: packaged GUI plus helper scripts
- `WorkspaceFull`: packaged GUI plus the local workspace contents that are present on disk

## Repository Scope

This repository intentionally ignores:

- local virtual environments such as `.qt-venv`, `.qt-conda-env`, and `.venv`
- upstream cloned repositories such as `rat-common`, `rat-models`, `pyrat`, and `vcpkg`
- downloaded tool caches under `tools`
- local logs, artifacts, archives, and scratch data

The one exception is `workspace-overlays/rat-vcpkg/ports`, which is intentionally versioned here so the bootstrap path can reproduce the local overlay and CPU-only compatibility changes.

That keeps the GitHub repository small and makes the bootstrap path reproducible.

## 中文安装与环境配置说明

### 1. 仅启动图形界面

如果你只是想把 Rat-Workbench 的 GUI 启动起来，不需要先手动配置完整的 C++ 编译环境。

步骤：

1. 从 GitHub 下载或克隆本仓库
2. 在 Windows 下双击 `Run-Project-RAT.bat`
3. 脚本会自动执行以下操作：
   - 检测本机 Python
   - 如有需要，创建 `.qt-venv`
   - 安装 GUI 所需依赖 `PySide6` 和 `vtk`
   - 启动 Rat-Workbench 图形界面

说明：

- 如果本机没有 Python，且系统可用 `winget`，脚本会尝试自动安装 Python 3.12
- 这条路径适合只体验 GUI、查看工作区状态、使用脚本入口
- 仅下载本 GitHub 仓库时，完整的上游 `Project-Rat` 源码仓库默认并不会一起带下来

### 2. 配置完整工作区

如果你需要构建 `Project-Rat` 相关库、安装 `rat-models`、编译示例、构建 `pyrat` wheel，那么还需要初始化完整工作区。

步骤：

1. 先克隆本 GitHub 仓库
2. 双击 `Bootstrap-Workspace.bat`
3. 或手动执行：

```powershell
.\scripts\bootstrap_project_rat_workspace.ps1
```

这个脚本会自动：

- 克隆上游开源仓库，例如 `rat-common`、`rat-models`、`pyrat`、`rat-vcpkg`
- 克隆 `vcpkg`
- 同步本仓库内保存的 `workspace-overlays/rat-vcpkg/ports` 覆盖层
- 下载便携版 `cmake`、`ninja`
- 下载 `Visual Studio Build Tools` 安装引导程序到 `tools\vs_BuildTools.exe`

### 3. 本地编译环境

如果要执行本地构建，建议安装：

1. Visual Studio Build Tools 2022
2. 组件选择 `Desktop development with C++`
3. Windows SDK

安装完成后，执行：

```powershell
.\scripts\project_rat_manager.ps1 -Action bootstrap-vcpkg
```

然后可以继续执行：

```powershell
.\scripts\project_rat_manager.ps1 -Action install-rat-models
.\scripts\project_rat_manager.ps1 -Action build-example -Example dmshyoke1
.\scripts\project_rat_manager.ps1 -Action build-pyrat-wheel
```

### 4. 代理说明

当前脚本默认不再强制使用固定代理。

行为如下：

- 如果系统环境变量里已经设置了 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY`，脚本会自动继承
- 如果没有设置代理环境变量，就直接联网
- 如果你需要显式指定代理，可以手动传参
- 如果你想强制关闭代理，也可以手动传参

示例：

```powershell
.\scripts\project_rat_manager.ps1 -Action status
.\scripts\project_rat_manager.ps1 -Action bootstrap-vcpkg -ProxyUrl http://127.0.0.1:7897
.\scripts\project_rat_manager.ps1 -Action bootstrap-vcpkg -DisableProxy
```

### 5. 使用建议

- 只想启动界面：运行 `Run-Project-RAT.bat`
- 想下载完整依赖工作区：运行 `Bootstrap-Workspace.bat`
- 想做本地编译：安装 Visual Studio Build Tools 后执行 `bootstrap-vcpkg`
- 如果网络环境访问 GitHub 或上游仓库较慢，再按需配置代理
