import os
import subprocess
import sys
from pathlib import Path


def get_runtime_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


WORKSPACE_ROOT = get_runtime_root()
QT_APP_SCRIPT = WORKSPACE_ROOT / "project_rat_gui_qt.py"
QT_ENV_CANDIDATES = (
    WORKSPACE_ROOT / ".qt-conda-env" / "python.exe",
    WORKSPACE_ROOT / ".qt-venv" / "Scripts" / "python.exe",
)

PYTHON_ENV_KEYS_TO_CLEAR = (
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "PYTHONEXECUTABLE",
    "__PYVENV_LAUNCHER__",
)


def get_qt_env_python():
    for candidate in QT_ENV_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def get_qt_env_root(python_path: Path) -> Path:
    if python_path.parent.name.lower() == "scripts":
        return python_path.parent.parent
    return python_path.parent


def build_qt_child_env(python_path: Path):
    env = os.environ.copy()
    for key in PYTHON_ENV_KEYS_TO_CLEAR:
        env.pop(key, None)

    qt_env_root = get_qt_env_root(python_path)
    env["PYTHONNOUSERSITE"] = "1"
    path_entries = [
        str(qt_env_root),
        str(qt_env_root / "Scripts"),
        str(qt_env_root / "Library" / "bin"),
        env.get("PATH", ""),
    ]
    env["PATH"] = os.pathsep.join(entry for entry in path_entries if entry)
    return env


def configure_frozen_runtime():
    internal_root = WORKSPACE_ROOT / "_internal"
    dll_dirs = [
        internal_root,
        internal_root / "PySide6",
        internal_root / "PySide6" / "plugins",
        internal_root / "shiboken6",
        internal_root / "vtk.libs",
        internal_root / "numpy.libs",
        WORKSPACE_ROOT,
    ]

    path_entries = [str(path) for path in dll_dirs if path.exists()]
    existing_path = os.environ.get("PATH", "")
    if existing_path:
        path_entries.append(existing_path)
    os.environ["PATH"] = os.pathsep.join(path_entries)

    if hasattr(os, "add_dll_directory"):
        for path in dll_dirs:
            if path.exists():
                os.add_dll_directory(str(path))

    plugin_root = internal_root / "PySide6" / "plugins"
    qml_root = internal_root / "PySide6" / "qml"
    if plugin_root.exists():
        os.environ["QT_PLUGIN_PATH"] = str(plugin_root)
        platform_root = plugin_root / "platforms"
        if platform_root.exists():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_root)
    if qml_root.exists():
        os.environ["QML2_IMPORT_PATH"] = str(qml_root)


def main():
    if getattr(sys, "frozen", False):
        configure_frozen_runtime()
        from project_rat_gui_qt import main as qt_main

        return qt_main()

    qt_env_python = get_qt_env_python()
    if not qt_env_python:
        print(
            "Qt runtime was not found. Run Run-Project-RAT.bat or "
            "scripts\\setup_project_rat_runtime.ps1 first.",
            file=sys.stderr,
        )
        return 1

    if not QT_APP_SCRIPT.exists():
        print(f"Qt GUI entry script was not found: {QT_APP_SCRIPT}", file=sys.stderr)
        return 1

    env = build_qt_child_env(qt_env_python)
    return subprocess.call(
        [str(qt_env_python), str(QT_APP_SCRIPT), *sys.argv[1:]],
        cwd=str(WORKSPACE_ROOT),
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
