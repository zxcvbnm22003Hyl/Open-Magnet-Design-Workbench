# Rat-Workbench

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
