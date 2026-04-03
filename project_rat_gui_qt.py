import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QListView,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from project_rat_cct import (
    CCT_WORKBENCH_ROOT,
    get_cct_profiles,
    parse_cos_theta_blocks,
    sanitize_project_name,
    write_cct_project,
)


def get_runtime_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


WORKSPACE_ROOT = get_runtime_root()
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "project_rat_manager.ps1"
TOOLS_ROOT = WORKSPACE_ROOT / "tools"
EXAMPLES_ROOT = WORKSPACE_ROOT / "rat-vcpkg" / "examples" / "rat" / "models"
VIEWABLE_EXTENSIONS = (".vtu", ".vtp", ".vtk", ".vts", ".vti", ".vtm", ".stl", ".ply", ".obj")
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

REPOSITORIES = {
    "rat-common": WORKSPACE_ROOT / "rat-common",
    "rat-math": WORKSPACE_ROOT / "rat-math",
    "rat-distmesh-cpp": WORKSPACE_ROOT / "rat-distmesh-cpp",
    "materials-cpp": WORKSPACE_ROOT / "materials-cpp",
    "rat-mlfmm": WORKSPACE_ROOT / "rat-mlfmm",
    "rat-nl": WORKSPACE_ROOT / "rat-nl",
    "rat-models": WORKSPACE_ROOT / "rat-models",
    "rat-documentation": WORKSPACE_ROOT / "rat-documentation",
    "pyrat": WORKSPACE_ROOT / "pyrat",
    "rat-vcpkg": WORKSPACE_ROOT / "rat-vcpkg",
    "vcpkg": WORKSPACE_ROOT / "vcpkg",
}

DOC_FILES = {
    "Windows 安装指南": WORKSPACE_ROOT / "rat-documentation" / "installation" / "wininstall.md",
    "RAT 文档总览": WORKSPACE_ROOT / "rat-documentation" / "README.md",
    "rat-vcpkg README": WORKSPACE_ROOT / "rat-vcpkg" / "README.md",
    "pyrat README": WORKSPACE_ROOT / "pyrat" / "README.md",
}

EXAMPLE_METADATA = {
    "dmshyoke1": {
        "title": "铁轭网格模型",
        "summary": "生成铁轭网格模型，并导出 VTK 结果文件。",
        "output_dir": "dmshyoke1",
        "expected": ["VTK 网格", "times.csv"],
    },
    "dmshyoke2": {
        "title": "带铁轭三叶线圈",
        "summary": "运行线圈加铁轭模型，并导出网格结果与 JSON 模型文件。",
        "output_dir": "dmshyoke2",
        "expected": ["VTK 网格", "model.json"],
    },
    "saddle_df": {
        "title": "鞍形线圈谐波分析",
        "summary": "运行鞍形线圈示例，并将谐波分析结果导出为 CSV。",
        "output_dir": "saddle",
        "expected": ["harmonics.csv", "model.json"],
    },
}


def find_vs_installation():
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    vswhere = program_files_x86 / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere.exists():
        return None
    try:
        result = subprocess.run(
            [
                str(vswhere),
                "-latest",
                "-products",
                "*",
                "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property",
                "installationPath",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return None
    path = result.stdout.strip()
    return Path(path) if path else None


def find_workspace_tool(*patterns):
    for pattern in patterns:
        matches = sorted(TOOLS_ROOT.glob(pattern))
        if matches:
            return str(matches[-1])
    return None


def find_cl_executable():
    from_path = shutil.which("cl")
    if from_path:
        return from_path

    local_matches = sorted((TOOLS_ROOT / "msvc-local" / "VC" / "Tools" / "MSVC").glob("*/bin/Hostx64/x64/cl.exe"))
    if local_matches:
        return str(local_matches[-1])

    vs_install = find_vs_installation()
    if vs_install:
        matches = sorted((vs_install / "VC" / "Tools" / "MSVC").glob("*/bin/Hostx64/x64/cl.exe"))
        if matches:
            return str(matches[-1])

    for root in (Path(r"C:\Program"), Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")):
        matches = sorted((root / "VC" / "Tools" / "MSVC").glob("*/bin/Hostx64/x64/cl.exe"))
        if matches:
            return str(matches[-1])

    return None


def find_examples():
    if not EXAMPLES_ROOT.exists():
        return []
    return sorted(item.name for item in EXAMPLES_ROOT.iterdir() if item.is_dir())


def get_example_metadata(name):
    metadata = EXAMPLE_METADATA.get(name, {}).copy()
    metadata.setdefault("title", name or "未选择示例")
    metadata.setdefault("summary", "构建并运行已安装的 RAT 示例。")
    metadata.setdefault("output_dir", name or "")
    metadata.setdefault("expected", [])
    return metadata


def get_example_root(name):
    return EXAMPLES_ROOT / name if name else None


def get_example_source_path(name):
    example_root = get_example_root(name)
    if not example_root or not example_root.exists():
        return None
    candidates = sorted(example_root.glob("*.cpp"))
    return candidates[0] if candidates else None


def get_example_output_dir(name):
    example_root = get_example_root(name)
    if not example_root:
        return None
    return example_root / get_example_metadata(name)["output_dir"]


def find_project_executable(project_root, executable_name):
    if not project_root or not executable_name:
        return None
    candidates = [
        project_root / "build" / "Release" / "bin" / f"{executable_name}.exe",
        project_root / "build" / "bin" / f"{executable_name}.exe",
        project_root / "build" / "Release" / f"{executable_name}.exe",
        project_root / "build" / f"{executable_name}.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def list_output_files(output_dir):
    if not output_dir or not output_dir.exists():
        return []
    files = sorted(path for path in output_dir.rglob("*") if path.is_file())
    file_names = {path.name for path in files}
    alias_prefixes = {
        "grid": "space_field_slice",
        "coilmesh": "coil_field_mesh",
        "harmonics": "field_harmonics",
    }
    filtered = []
    for path in files:
        name = path.name
        lower_name = name.lower()
        skip = False
        for legacy_prefix, alias_prefix in alias_prefixes.items():
            if lower_name.startswith(legacy_prefix):
                aliased_name = re.sub(rf"^{legacy_prefix}", alias_prefix, name, flags=re.IGNORECASE)
                if aliased_name in file_names:
                    skip = True
                    break
        if not skip:
            filtered.append(path)
    return filtered


def collect_status():
    tools = {
        "git": shutil.which("git"),
        "python": sys.executable,
        "cl": find_cl_executable(),
        "cmake": shutil.which("cmake") or find_workspace_tool("cmake-*/cmake-*-windows-x86_64/bin/cmake.exe"),
        "ninja": shutil.which("ninja") or find_workspace_tool("ninja-*/ninja.exe"),
        "uv": shutil.which("uv"),
        "nvcc": shutil.which("nvcc"),
    }
    local_vcpkg = WORKSPACE_ROOT / "vcpkg" / "vcpkg.exe"
    tools["vcpkg"] = str(local_vcpkg) if local_vcpkg.exists() else shutil.which("vcpkg")

    repos = {
        name: {"exists": path.exists(), "git": (path / ".git").exists(), "path": str(path)}
        for name, path in REPOSITORIES.items()
    }
    docs = {name: path.exists() for name, path in DOC_FILES.items()}

    notes = []
    if not tools["nvcc"]:
        notes.append("当前环境按 CPU 优先方式准备，可直接先做磁体几何与场计算学习。")
    notes.append("图形界面使用本地 .qt-conda-env 环境运行。")

    return {
        "workspace": str(WORKSPACE_ROOT),
        "tools": tools,
        "repos": repos,
        "docs": docs,
        "vs_install": str(find_vs_installation() or ""),
        "examples": find_examples(),
        "notes": notes,
    }


def format_status_report(status):
    lines = [f"工作区: {status['workspace']}", "", "仓库状态:"]
    for name, repo_status in status["repos"].items():
        state = "已存在" if repo_status["exists"] else "缺失"
        git_state = "git" if repo_status["git"] else "非 git"
        lines.append(f"  [{state}] {name} ({git_state})")

    lines.extend(["", "工具链状态:"])
    for name, value in status["tools"].items():
        lines.append(f"  {name:8} : {value or '缺失'}")
    lines.append(f"  {'vs':8} : {status['vs_install'] or '缺失'}")

    lines.extend(["", "文档状态:"])
    for name, exists in status["docs"].items():
        lines.append(f"  [{'已存在' if exists else '缺失'}] {name}")

    lines.extend(["", "内置示例:", "  " + (", ".join(status["examples"]) if status["examples"] else "未找到示例"), "", "说明:"])
    for note in status["notes"]:
        lines.append(f"  - {note}")
    return "\n".join(lines)


def open_path(path):
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(str(target))
    os.startfile(str(target))


class ProjectRatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RAT User Interface")
        self.resize(1720, 1000)

        self.process = None
        self.process_title = ""
        self.process_finished_callback = None
        self.output_paths = []
        self.current_visual_path = None
        self.current_pipeline = []
        self.current_actor = None
        self.current_outline_actor = None
        self.current_scalar_bar = None
        self.current_coil_layer_actors = {}
        self.current_coil_layer_paths = []
        self.current_coil_visual_mode = "magnetic_flux_density"
        self.scalar_bar_position = "right"
        self._populating_coil_layer_list = False
        self._populating_model_tree = False
        self.model_tree_layer_items = {}
        self.model_tree_page_items = {}
        self.model_tree_view_items = {}
        self.current_editor_page_key = "summary"
        self.example_names = find_examples()
        self.busy_widgets = []
        self.busy_actions = []
        self._param_group_states = {}
        self._inspector_requested_visible = True
        self._editor_requested_visible = True
        self._log_requested_visible = False
        self._last_splitter_sizes = {
            "left": 300,
            "center": 1180,
            "right": 320,
            "left_tree": 820,
            "left_log": 220,
        }

        self.cct_profiles = get_cct_profiles()
        self.cct_field_widgets = {}
        self.active_context = None
        self.active_cct_project = None

        self.vcpkg_root_edit = QLineEdit(str(WORKSPACE_ROOT / "vcpkg"))
        self.triplet_edit = QLineEdit("x64-windows-release")

        self.example_combo = QComboBox()
        self.example_combo.setView(QListView())
        self.example_combo.addItems(self.example_names or [""])
        self.example_combo.currentTextChanged.connect(self.on_example_changed)

        self.summary_kind = QLabel("当前对象")
        self.summary_kind.setStyleSheet("font-size: 12px; color: #5d6778;")
        self.summary_title = QLabel("Project RAT")
        self.summary_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.summary_summary = QLabel("")
        self.summary_summary.setWordWrap(True)
        self.summary_paths = QLabel("")
        self.summary_paths.setWordWrap(True)
        self.summary_paths.setTextFormat(Qt.RichText)

        self.output_list = QListWidget()
        self.output_list.currentItemChanged.connect(self.on_output_selection_changed)
        self.coil_layer_list = QListWidget()
        self.coil_layer_list.itemChanged.connect(self.on_coil_layer_visibility_changed)
        self.coil_layer_list.setMaximumHeight(132)
        self.coil_layer_list.setMinimumWidth(0)
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.status_text = QPlainTextEdit()
        self.status_text.setReadOnly(True)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.help_text = QPlainTextEdit()
        self.help_text.setReadOnly(True)

        self.viewer_mesh_label = QLabel("未加载结果")
        self.viewer_mesh_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.viewer_info_label = QLabel("在左侧选择结果或从模型树切换视图。")
        self.viewer_info_label.setWordWrap(True)

        self.profile_combo = QComboBox()
        self.profile_combo.setView(QListView())
        for profile_id, profile in self.cct_profiles.items():
            self.profile_combo.addItem(profile["label"], profile_id)
        self.profile_combo.currentTextChanged.connect(self.on_profile_changed)
        self.project_name_edit = QLineEdit()
        self.cct_profile_summary = QLabel("")
        self.cct_profile_summary.setWordWrap(True)
        self.cct_orientation_note = QLabel("")
        self.cct_orientation_note.setWordWrap(True)
        self.cct_orientation_note.setStyleSheet("color: #5d6778;")
        self.cct_form_widget = QWidget()
        self.cct_form_widget.setObjectName("MagnetDesignScrollContents")
        self.cct_form_widget.setAutoFillBackground(True)
        self.cct_form_layout = QVBoxLayout(self.cct_form_widget)
        self.cct_form_layout.setContentsMargins(0, 0, 0, 0)
        self.cct_form_layout.setSpacing(10)

        self.vtk_widget = None
        self.vtk_renderer = None
        self.orientation_widget = None

        self._build_central_viewer()
        self._build_left_dock()
        self._build_right_dock()
        self._build_log_dock()
        self._build_main_layout()
        self._build_panel_toggle_actions()
        self._build_view_actions()
        self._build_toolbar()
        self._build_menu_bar()
        self.setStatusBar(QStatusBar())
        self._apply_rat_theme()
        self._apply_combo_popup_theme()
        self.restore_default_layout()

        self.refresh_status()
        self.rebuild_cct_form()
        if self.example_names:
            self.activate_example_context(self.example_combo.currentText())
        else:
            self.refresh_results()

    def _build_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setObjectName("ProjectRatMainToolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.main_toolbar = toolbar
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        actions = [
            ("刷新结果", self.refresh_results),
            ("恢复面板", self.restore_default_layout),
        ]
        for label, callback in actions:
            action = QAction(label, self)
            action.triggered.connect(callback)
            toolbar.addAction(action)
            self.busy_actions.append(action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        toolbar.addWidget(QLabel("内置示例"))
        self.example_combo.setMinimumWidth(180)
        toolbar.addWidget(self.example_combo)

    def _build_view_actions(self):
        self.show_mesh_edges_action = QAction("网格线", self)
        self.show_mesh_edges_action.setCheckable(True)
        self.show_mesh_edges_action.setChecked(False)
        self.show_mesh_edges_action.triggered.connect(self.update_view_preferences)

        self.show_outline_action = QAction("包围盒", self)
        self.show_outline_action.setCheckable(True)
        self.show_outline_action.setChecked(False)
        self.show_outline_action.triggered.connect(self.update_view_preferences)

        self.show_scalar_bar_action = QAction("色标", self)
        self.show_scalar_bar_action.setCheckable(True)
        self.show_scalar_bar_action.setChecked(True)
        self.show_scalar_bar_action.triggered.connect(self.update_view_preferences)

        self.show_coil_overlay_action = QAction("切片叠加线圈", self)
        self.show_coil_overlay_action.setCheckable(True)
        self.show_coil_overlay_action.setChecked(True)
        self.show_coil_overlay_action.triggered.connect(self.update_view_preferences)

    def _build_menu_bar(self):
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)

        def make_action(label, callback, checkable=False, checked=False):
            action = QAction(label, self)
            action.setCheckable(checkable)
            if checkable:
                action.setChecked(checked)
            action.triggered.connect(callback)
            return action

        home_menu = menu_bar.addMenu("Home")
        home_menu.addAction(make_action("当前对象", lambda: self.show_editor_page("summary")))
        home_menu.addAction(make_action("磁体设计", lambda: self.show_editor_page("design")))
        home_menu.addAction(make_action("输出文件", lambda: self.show_editor_page("outputs")))

        view_menu = menu_bar.addMenu("View")
        view_menu.addAction(make_action("导体磁场", self.load_coil_magnetic_field_visualization))
        view_menu.addAction(make_action("线圈电流密度", self.load_coil_current_density_visualization))
        view_menu.addAction(make_action("线圈网格", self.load_coil_mesh_visualization))
        view_menu.addAction(make_action("二维切片", self.load_slice_visualization))
        view_menu.addSeparator()
        view_menu.addAction(make_action("重置视角", self.reset_camera))
        view_menu.addAction(make_action("前视", lambda: self.apply_camera_preset("front")))
        view_menu.addAction(make_action("侧视", lambda: self.apply_camera_preset("side")))
        view_menu.addAction(make_action("顶视", lambda: self.apply_camera_preset("top")))
        view_menu.addAction(make_action("等轴测", lambda: self.apply_camera_preset("iso")))
        view_menu.addSeparator()
        view_menu.addAction(self.show_mesh_edges_action)
        view_menu.addAction(self.show_outline_action)
        view_menu.addAction(self.show_scalar_bar_action)
        view_menu.addAction(self.show_coil_overlay_action)
        view_menu.addSeparator()
        scalar_position_menu = view_menu.addMenu("色标位置")
        self.scalar_bar_position_group = QActionGroup(self)
        self.scalar_bar_position_group.setExclusive(True)
        self.scalar_bar_left_action = QAction("靠左", self, checkable=True)
        self.scalar_bar_left_action.triggered.connect(lambda checked=False: self.set_scalar_bar_position("left"))
        self.scalar_bar_right_action = QAction("靠右", self, checkable=True)
        self.scalar_bar_right_action.triggered.connect(lambda checked=False: self.set_scalar_bar_position("right"))
        self.scalar_bar_position_group.addAction(self.scalar_bar_left_action)
        self.scalar_bar_position_group.addAction(self.scalar_bar_right_action)
        scalar_position_menu.addAction(self.scalar_bar_left_action)
        scalar_position_menu.addAction(self.scalar_bar_right_action)
        self._sync_scalar_bar_position_actions()

        tools_menu = menu_bar.addMenu("Tools")
        tools_menu.addAction(make_action("构建当前", self.build_current))
        tools_menu.addAction(make_action("运行当前", self.run_current))
        tools_menu.addAction(make_action("构建并运行", self.build_and_run_current))
        tools_menu.addAction(make_action("导出 OPERA .cond", self.export_current_opera))
        tools_menu.addAction(make_action("刷新结果", self.refresh_results))
        tools_menu.addSeparator()
        tools_menu.addAction(make_action("打开源文件", self.open_current_source))
        tools_menu.addAction(make_action("打开输出目录", self.open_output_folder))
        tools_menu.addAction(make_action("打开 OPERA .cond", self.open_current_opera))

        settings_menu = menu_bar.addMenu("Settings")
        settings_menu.addAction(make_action("环境与工具", lambda: self.show_editor_page("environment")))
        settings_menu.addAction(make_action("恢复默认布局", self.restore_default_layout))

        window_menu = menu_bar.addMenu("Window")
        window_menu.addAction(self.toggle_inspector_action())
        window_menu.addAction(self.toggle_editor_action())
        window_menu.addAction(self.toggle_log_action())

        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction(make_action("使用说明", self.open_help))
        help_menu.addAction(make_action("打开工作区 README", lambda: self.safe_open(WORKSPACE_ROOT / "README.md")))

    def _apply_rat_theme(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background: #182328;
                color: #d7e2e6;
            }
            QMenuBar {
                background: #1a2329;
                color: #d7e2e6;
                border-bottom: 1px solid #304047;
                padding: 2px 6px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 10px;
                margin: 2px 2px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background: #24323a;
                color: #7be6d2;
            }
            QMenu {
                background: #1f2a30;
                color: #d7e2e6;
                border: 1px solid #33454d;
                padding: 6px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #29414a;
                color: #8ef1dc;
            }
            QToolBar#ProjectRatMainToolbar {
                background: #1c262c;
                border: none;
                border-bottom: 1px solid #304047;
                spacing: 4px;
                padding: 6px;
            }
            QWidget#ViewerInfoBar, QWidget#ViewerTextPanel, QWidget#LayerPanel, QWidget#ResultSidebarPanel {
                background: #1b252b;
                border: 1px solid #304047;
                border-radius: 8px;
            }
            QScrollArea#MagnetDesignScrollArea {
                background: #1d282f;
                border: 1px solid #33454d;
                border-radius: 8px;
            }
            QWidget#MagnetDesignScrollViewport,
            QWidget#MagnetDesignScrollContents {
                background: #1d282f;
                color: #d7e2e6;
                border: none;
            }
            QFrame#ParamGroupFrame {
                background: #1a252b;
                border: 1px solid #304047;
                border-radius: 8px;
            }
            QToolButton#ParamGroupHeader {
                background: #223038;
                color: #e3f1f3;
                border: none;
                border-bottom: 1px solid #304047;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 8px 12px;
                font-weight: 700;
                text-align: left;
            }
            QToolButton#ParamGroupHeader:hover {
                background: #273840;
                color: #f6ffff;
            }
            QWidget#ParamGroupBody {
                background: transparent;
                border: none;
            }
            QWidget#MagnetDesignScrollContents QLabel {
                color: #d7e2e6;
            }
            QToolButton {
                background: #243039;
                color: #d7e2e6;
                border: 1px solid #33454d;
                border-radius: 5px;
                padding: 6px 10px;
            }
            QToolButton:hover, QToolButton:checked {
                background: #2b3c45;
                border-color: #67d9c9;
                color: #f5ffff;
            }
            QWidget#ProjectRatInspectorDock, QWidget#ProjectRatEditorDock, QWidget#ProjectRatLogDock {
                background: #182328;
                border: 1px solid #304047;
                border-radius: 8px;
            }
            QLabel#PanelTitle {
                background: #1b252b;
                border: 1px solid #304047;
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 15px;
                font-weight: 700;
            }
            QSplitter::handle {
                background: #33454d;
            }
            QSplitter::handle:horizontal {
                width: 8px;
                margin: 4px 0;
                border-radius: 3px;
            }
            QSplitter::handle:vertical {
                height: 8px;
                margin: 0 4px;
                border-radius: 3px;
            }
            QSplitter::handle:hover {
                background: #67d9c9;
            }
            QWidget {
                color: #d7e2e6;
            }
            QLabel {
                color: #d7e2e6;
            }
            QTreeWidget, QListWidget, QPlainTextEdit, QLineEdit, QAbstractSpinBox, QComboBox, QScrollArea, QStackedWidget {
                background: #202c33;
                color: #d7e2e6;
                border: 1px solid #33454d;
                border-radius: 6px;
                selection-background-color: #29414a;
                selection-color: #f2fdff;
            }
            QTreeWidget::item, QListWidget::item {
                padding: 4px 6px;
            }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background: #2a424b;
                color: #f2fdff;
            }
            QPlainTextEdit, QLineEdit, QAbstractSpinBox, QComboBox {
                padding: 4px 6px;
            }
            QComboBox::drop-down {
                border: none;
                width: 22px;
            }
            QComboBox QAbstractItemView {
                background: #1f2a30;
                color: #d7e2e6;
                border: 1px solid #33454d;
                selection-background-color: #29414a;
                selection-color: #f2fdff;
                outline: 0;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 26px;
                padding: 4px 8px;
            }
            QPushButton {
                background: #243039;
                color: #d7e2e6;
                border: 1px solid #33454d;
                border-radius: 6px;
                padding: 7px 12px;
            }
            QPushButton:hover {
                background: #2a3a43;
                border-color: #67d9c9;
            }
            QPushButton:pressed {
                background: #223138;
            }
            QCheckBox {
                color: #d7e2e6;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #48616b;
                background: #223138;
            }
            QCheckBox::indicator:checked {
                background: #2fa89d;
                border-color: #74e8d6;
            }
            QTabWidget::pane {
                border: 1px solid #33454d;
                background: #1d282f;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #1b252b;
                color: #a8b7bf;
                padding: 8px 12px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #24323a;
                color: #7be6d2;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: #182328;
                border: none;
                margin: 0px;
            }
            QScrollBar:vertical {
                width: 12px;
            }
            QScrollBar:horizontal {
                height: 12px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #3a4d56;
                border-radius: 5px;
                min-height: 20px;
                min-width: 20px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
                background: #54717d;
            }
            QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {
                background: transparent;
                border: none;
            }
            QStatusBar {
                background: #1a2329;
                color: #91a4ad;
                border-top: 1px solid #304047;
            }
            """
        )

    def _apply_combo_popup_theme(self):
        popup_style = """
            QListView {
                background: #1f2a30;
                color: #d7e2e6;
                border: 1px solid #33454d;
                outline: 0;
                selection-background-color: #29414a;
                selection-color: #f2fdff;
                padding: 4px;
            }
            QListView::item {
                min-height: 26px;
                padding: 4px 8px;
            }
            QListView::item:selected {
                background: #29414a;
                color: #f2fdff;
            }
        """
        self.example_combo.view().setStyleSheet(popup_style)
        self.profile_combo.view().setStyleSheet(popup_style)

    def _build_central_viewer(self):
        container = QWidget()
        container.setObjectName("CentralViewerContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.vtk_widget = QVTKRenderWindowInteractor(container)
        self.vtk_widget.setMinimumSize(320, 260)
        layout.addWidget(self.vtk_widget, 1)
        self.viewer_panel = container

        render_window = self.vtk_widget.GetRenderWindow()
        render_window.SetAlphaBitPlanes(1)
        render_window.SetMultiSamples(0)
        self.vtk_renderer = vtk.vtkRenderer()
        self.vtk_renderer.SetBackground(0.08, 0.11, 0.13)
        self.vtk_renderer.SetBackground2(0.15, 0.20, 0.22)
        self.vtk_renderer.GradientBackgroundOn()
        self.vtk_renderer.UseDepthPeelingOn()
        self.vtk_renderer.SetMaximumNumberOfPeels(16)
        self.vtk_renderer.SetOcclusionRatio(0.12)
        render_window.AddRenderer(self.vtk_renderer)

        interactor = render_window.GetInteractor()
        interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
        self.vtk_widget.Initialize()
        self.vtk_widget.Start()

        axes_actor = vtk.vtkAxesActor()
        self.orientation_widget = vtk.vtkOrientationMarkerWidget()
        self.orientation_widget.SetOrientationMarker(axes_actor)
        self.orientation_widget.SetInteractor(interactor)
        self.orientation_widget.SetViewport(0.0, 0.0, 0.14, 0.14)
        self.orientation_widget.SetEnabled(1)
        self.orientation_widget.InteractiveOff()

    def _build_left_dock(self):
        container = QWidget()
        container.setObjectName("ProjectRatInspectorDock")
        container.setMinimumWidth(160)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("模型浏览器")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.model_tree = QTreeWidget()
        self.model_tree.setObjectName("ModelTree")
        self.model_tree.setHeaderHidden(True)
        self.model_tree.currentItemChanged.connect(self.on_model_tree_selection_changed)
        self.model_tree.itemChanged.connect(self.on_model_tree_item_changed)
        layout.addWidget(self.model_tree, 1)

        self.inspector_dock = container

    def _build_right_dock(self):
        container = QWidget()
        container.setObjectName("ProjectRatEditorDock")
        container.setMinimumWidth(220)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.editor_title = QLabel("节点编辑器")
        self.editor_title.setObjectName("PanelTitle")
        self.editor_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.editor_subtitle = QLabel("左侧模型树用于切换当前对象、参数页和结果视图。")
        self.editor_subtitle.setWordWrap(True)
        self.editor_subtitle.setStyleSheet("color: #5d6778;")
        layout.addWidget(self.editor_title)
        self.editor_subtitle.hide()

        self.editor_stack = QStackedWidget()
        self.editor_pages = {
            "summary": self._build_summary_tab(),
            "design": self._build_cct_tab(),
            "outputs": self._build_outputs_tab(),
            "preview": self._build_preview_tab(),
            "environment": self._build_environment_tab(),
            "help": self._build_help_tab(),
        }
        for page in self.editor_pages.values():
            self.editor_stack.addWidget(page)
        layout.addWidget(self.editor_stack, 1)

        self.editor_dock = container
        self.show_editor_page("summary")

    def _build_log_dock(self):
        container = QWidget()
        container.setObjectName("ProjectRatLogDock")
        container.setMinimumHeight(120)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        title = QLabel("日志")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        layout.addWidget(self.log_text, 1)
        self.log_dock = container

    def _build_main_layout(self):
        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.setObjectName("ProjectRatLeftSplitter")
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.setOpaqueResize(True)
        self.left_splitter.setHandleWidth(10)
        self.left_splitter.setMinimumWidth(220)
        self.left_splitter.addWidget(self.inspector_dock)
        self.left_splitter.addWidget(self.log_dock)
        self.left_splitter.setStretchFactor(0, 1)
        self.left_splitter.setStretchFactor(1, 0)
        self.left_splitter.splitterMoved.connect(self._remember_left_splitter_sizes)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setObjectName("ProjectRatMainSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setOpaqueResize(True)
        self.main_splitter.setHandleWidth(10)
        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(self.viewer_panel)
        self.main_splitter.addWidget(self.editor_dock)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.splitterMoved.connect(self._remember_main_splitter_sizes)
        self.setCentralWidget(self.main_splitter)

    def _build_panel_toggle_actions(self):
        self.inspector_toggle_action = QAction("模型树", self)
        self.inspector_toggle_action.setCheckable(True)
        self.inspector_toggle_action.setChecked(True)
        self.inspector_toggle_action.toggled.connect(self.set_inspector_visible)

        self.editor_toggle_action = QAction("属性面板", self)
        self.editor_toggle_action.setCheckable(True)
        self.editor_toggle_action.setChecked(True)
        self.editor_toggle_action.toggled.connect(self.set_editor_visible)

        self.log_toggle_action = QAction("日志", self)
        self.log_toggle_action.setCheckable(True)
        self.log_toggle_action.setChecked(False)
        self.log_toggle_action.toggled.connect(self.set_log_visible)

    def _sync_toggle_action(self, action_name, visible):
        action = getattr(self, action_name, None)
        if action is None:
            return
        action.blockSignals(True)
        action.setChecked(bool(visible))
        action.blockSignals(False)

    def _remember_main_splitter_sizes(self, *_args):
        if not hasattr(self, "main_splitter"):
            return
        sizes = self.main_splitter.sizes()
        if len(sizes) < 3:
            return
        if sizes[0] > 120:
            self._last_splitter_sizes["left"] = sizes[0]
        if sizes[1] > 240:
            self._last_splitter_sizes["center"] = sizes[1]
        if sizes[2] > 180:
            self._last_splitter_sizes["right"] = sizes[2]

    def _remember_left_splitter_sizes(self, *_args):
        if not hasattr(self, "left_splitter"):
            return
        sizes = self.left_splitter.sizes()
        if len(sizes) < 2:
            return
        if sizes[0] > 120:
            self._last_splitter_sizes["left_tree"] = sizes[0]
        if sizes[1] > 60:
            self._last_splitter_sizes["left_log"] = sizes[1]

    def _set_main_splitter_sizes(self, left=None, center=None, right=None):
        if not hasattr(self, "main_splitter"):
            return
        sizes = self.main_splitter.sizes()
        if len(sizes) < 3:
            return
        total = max(sum(sizes), 1000)
        left_size = sizes[0] if left is None else max(0, int(left))
        right_size = sizes[2] if right is None else max(0, int(right))
        center_size = sizes[1] if center is None else max(0, int(center))
        if center is None:
            center_size = max(420, total - left_size - right_size)
        self.main_splitter.setSizes([left_size, center_size, right_size])

    def _update_left_panel_visibility(self):
        inspector_requested = self._inspector_requested_visible
        log_requested = self._log_requested_visible
        self.inspector_dock.setHidden(not inspector_requested)
        self.log_dock.setHidden(not log_requested)
        any_visible = inspector_requested or log_requested
        if hasattr(self, "left_splitter"):
            self.left_splitter.setVisible(any_visible)
            if inspector_requested and log_requested:
                self.left_splitter.setSizes(
                    [max(520, self._last_splitter_sizes["left_tree"]), max(160, self._last_splitter_sizes["left_log"])]
                )
            elif inspector_requested:
                self.left_splitter.setSizes([max(760, self._last_splitter_sizes["left_tree"]), 0])
            elif log_requested:
                self.left_splitter.setSizes([0, max(180, self._last_splitter_sizes["left_log"])])
        if any_visible:
            if hasattr(self, "main_splitter"):
                sizes = self.main_splitter.sizes()
                if len(sizes) >= 3 and (sizes[0] < 220 or self.left_splitter.width() < 180):
                    right = max(260, sizes[2])
                    total = max(sum(sizes), 1000)
                    left = max(280, self._last_splitter_sizes["left"])
                    center = max(520, total - left - right)
                    self.main_splitter.setSizes([left, center, right])
        else:
            self._set_main_splitter_sizes(left=0)

    def set_inspector_visible(self, visible):
        visible = bool(visible)
        self._inspector_requested_visible = visible
        self._sync_toggle_action("inspector_toggle_action", visible)
        self._update_left_panel_visibility()

    def ensure_editor_panel_visible(self, minimum_width=300):
        self._editor_requested_visible = True
        self.editor_dock.setVisible(True)
        self._sync_toggle_action("editor_toggle_action", True)
        if hasattr(self, "main_splitter"):
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 3 and sizes[2] < minimum_width:
                right = max(minimum_width, self._last_splitter_sizes["right"])
                left = sizes[0]
                if self.inspector_dock.isVisible():
                    left = max(180, left, self._last_splitter_sizes["left"])
                total = max(sum(sizes), left + right + 500)
                center = max(500, total - left - right)
                self.main_splitter.setSizes([left, center, right])

    def set_editor_visible(self, visible):
        visible = bool(visible)
        self._editor_requested_visible = visible
        self.editor_dock.setVisible(visible)
        self._sync_toggle_action("editor_toggle_action", visible)
        if visible:
            self.ensure_editor_panel_visible()

    def set_log_visible(self, visible):
        visible = bool(visible)
        self._log_requested_visible = visible
        if hasattr(self, "log_toggle_action"):
            self.log_toggle_action.blockSignals(True)
            self.log_toggle_action.setChecked(visible)
            self.log_toggle_action.blockSignals(False)
        self._update_left_panel_visibility()

    def _build_summary_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        button_row = QHBoxLayout()
        open_project = QPushButton("打开工程")
        open_project.clicked.connect(self.open_current_project)
        open_source = QPushButton("打开源文件")
        open_source.clicked.connect(self.open_current_source)
        open_output = QPushButton("打开输出")
        open_output.clicked.connect(self.open_output_folder)
        for button in (open_project, open_source, open_output):
            self._register_busy_widget(button)
            button_row.addWidget(button)

        layout.addWidget(self.summary_kind)
        layout.addWidget(self.summary_title)
        layout.addWidget(self.summary_summary)
        layout.addLayout(button_row)
        layout.addWidget(self.summary_paths)
        layout.addStretch(1)
        return widget

    def _build_help_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        button_row = QHBoxLayout()
        open_readme = QPushButton("打开工作区 README")
        open_readme.clicked.connect(lambda: self.safe_open(WORKSPACE_ROOT / "README.md"))
        open_docs = QPushButton("打开 RAT 文档")
        open_docs.clicked.connect(lambda: self.safe_open(REPOSITORIES["rat-documentation"]))
        for button in (open_readme, open_docs):
            self._register_busy_widget(button)
            button_row.addWidget(button)

        layout.addLayout(button_row)
        layout.addWidget(self.help_text, 1)
        return widget

    def _group_fields_for_profile(self, profile_id, fields):
        fields_by_key = {field["key"]: field for field in fields}
        ordered_keys = [field["key"] for field in fields]

        def collect(title, keys, expanded):
            group_fields = [fields_by_key[key] for key in keys if key in fields_by_key]
            return {"title": title, "fields": group_fields, "expanded": expanded}

        if profile_id == "mini_cct":
            sections = [
                collect(
                    "几何与分层",
                    [
                        "num_poles",
                        "num_layers",
                        "radius",
                        "layer_radius_csv",
                        "dformer",
                        "dradial",
                    ],
                    True,
                ),
                collect(
                    "绕制参数",
                    [
                        "num_turns",
                        "layer_turns_csv",
                        "delta",
                        "layer_delta_csv",
                        "alpha_deg",
                        "layer_alpha_deg_csv",
                        "frame_twist_deg",
                        "layer_frame_twist_deg_csv",
                        "num_nodes_per_turn",
                    ],
                    True,
                ),
                collect(
                    "网格与求解",
                    [
                        "element_size",
                    ],
                    False,
                ),
                collect(
                    "导体与工况",
                    [
                        "operating_current",
                        "layer_current_csv",
                        "operating_temperature",
                        "nd",
                        "nw",
                        "dstr",
                        "ddstr",
                        "fcu2sc",
                    ],
                    False,
                ),
            ]
        elif profile_id == "custom_cct":
            sections = [
                collect(
                    "几何与路径",
                    [
                        "num_layers",
                        "radius",
                        "layer_radius_csv",
                        "dradius",
                        "num_turns",
                        "layer_turns_csv",
                        "omega",
                        "layer_omega_csv",
                        "bend_radius",
                        "num_nodes_per_turn",
                        "num_sect_per_turn",
                    ],
                    True,
                ),
                collect(
                    "谐波与取向",
                    [
                        "dipole_amplitude",
                        "layer_dipole_csv",
                        "quadrupole_amplitude",
                        "layer_quadrupole_csv",
                        "quadrupole_offset",
                        "layer_quadrupole_offset_csv",
                        "frame_twist_deg",
                        "layer_frame_twist_deg_csv",
                        "use_frenet_serret",
                        "use_binormal",
                    ],
                    True,
                ),
                collect(
                    "导体与工况",
                    [
                        "element_size",
                        "operating_current",
                        "layer_current_csv",
                        "operating_temperature",
                        "nd",
                        "nw",
                        "dstr",
                        "ddstr",
                        "fcu2sc",
                    ],
                    False,
                ),
            ]
        elif profile_id == "cos_theta":
            sections = [
                collect(
                    "多极与分层",
                    [
                        "num_poles",
                        "num_layers",
                        "layer_radius_csv",
                        "layer_dinner_csv",
                        "layer_douter_csv",
                        "layer_wcable_csv",
                        "layer_dinsu_csv",
                        "layer_reflect_yz_csv",
                        "layer_reverse_csv",
                    ],
                    True,
                ),
                collect(
                    "块定义",
                    [
                        "layer1_blocks",
                        "layer2_blocks",
                    ],
                    True,
                ),
                collect(
                    "网格与工况",
                    [
                        "element_size",
                        "cross_num_thickness",
                        "cross_num_width",
                        "operating_current",
                        "layer_current_csv",
                        "operating_temperature",
                    ],
                    False,
                ),
            ]
        else:
            geometry_keys = []
            winding_keys = []
            condition_keys = []
            for key in ordered_keys:
                if key in {"operating_current", "operating_temperature"}:
                    condition_keys.append(key)
                elif key in {"element_size", "num_turns", "num_sections", "mirror_midplane", "midplane_offset", "planar_winding"}:
                    winding_keys.append(key)
                else:
                    geometry_keys.append(key)
            sections = [
                collect("几何参数", geometry_keys, True),
                collect("绕制与网格", winding_keys, True),
                collect("工况", condition_keys, False),
            ]

        used_keys = {field["key"] for section in sections for field in section["fields"]}
        remaining = [field for field in fields if field["key"] not in used_keys]
        if remaining:
            sections.append({"title": "其他参数", "fields": remaining, "expanded": False})
        return [section for section in sections if section["fields"]]

    def _set_param_group_expanded(self, group_key, header, body, expanded):
        header.blockSignals(True)
        header.setChecked(bool(expanded))
        header.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        header.blockSignals(False)
        body.setVisible(bool(expanded))
        self._param_group_states[group_key] = bool(expanded)

    def _create_param_group(self, profile_id, title, expanded):
        group_key = f"{profile_id}:{title}"

        frame = QFrame()
        frame.setObjectName("ParamGroupFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        header = QToolButton()
        header.setObjectName("ParamGroupHeader")
        header.setText(title)
        header.setCheckable(True)
        header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        body = QWidget()
        body.setObjectName("ParamGroupBody")
        body_layout = QFormLayout(body)
        body_layout.setContentsMargins(12, 10, 12, 12)
        body_layout.setSpacing(8)

        def on_toggled(checked):
            self._set_param_group_expanded(group_key, header, body, checked)

        header.toggled.connect(on_toggled)
        frame_layout.addWidget(header)
        frame_layout.addWidget(body)

        remembered = self._param_group_states.get(group_key, expanded)
        self._set_param_group_expanded(group_key, header, body, remembered)
        return frame, body_layout

    def _build_cct_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        form = QFormLayout()
        form.addRow("磁体类型", self.profile_combo)
        form.addRow("工程名称", self.project_name_edit)
        layout.addLayout(form)

        scroll = QScrollArea()
        scroll.setObjectName("MagnetDesignScrollArea")
        scroll.setWidgetResizable(True)
        scroll.viewport().setObjectName("MagnetDesignScrollViewport")
        scroll.viewport().setAutoFillBackground(True)
        scroll.setWidget(self.cct_form_widget)
        layout.addWidget(scroll, 1)

        grid = QGridLayout()
        buttons = [
            ("生成工程", self.generate_cct_project),
            ("编译磁体", self.build_cct_project),
            ("运行磁体", self.run_cct_project),
            ("编译并运行", self.build_and_run_cct_project),
            ("导出 OPERA .cond", self.export_current_opera),
            ("打开 OPERA .cond", self.open_current_opera),
            ("打开工程目录", self.open_active_cct_project),
            ("打开磁体输出", self.open_active_cct_output),
        ]
        for index, (label, callback) in enumerate(buttons):
            button = QPushButton(label)
            button.clicked.connect(callback)
            self._register_busy_widget(button)
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)
        return widget

    def _build_outputs_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        button_row = QHBoxLayout()
        open_selected = QPushButton("打开选中文件")
        open_selected.clicked.connect(self.open_selected_result)
        open_folder = QPushButton("打开输出目录")
        open_folder.clicked.connect(self.open_output_folder)
        open_opera = QPushButton("打开 OPERA .cond")
        open_opera.clicked.connect(self.open_current_opera)
        export_opera = QPushButton("导出 OPERA .cond")
        export_opera.clicked.connect(self.export_current_opera)
        load_selected = QPushButton("加载网格")
        load_selected.clicked.connect(self.load_selected_visualization)
        for button in (open_selected, open_folder, open_opera, export_opera, load_selected):
            self._register_busy_widget(button)
            button_row.addWidget(button)

        layout.addLayout(button_row)
        layout.addWidget(self.output_list, 1)
        note = QLabel("从模型树或结果列表可以快速切换导体磁场、电流密度和线圈网格视图。")
        note.setWordWrap(True)
        note.setStyleSheet("color: #5d6778;")
        layout.addWidget(note)
        return widget

    def _build_preview_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.preview_text)
        return widget

    def _build_environment_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        form = QFormLayout()
        form.addRow("VCPKG 根目录", self.vcpkg_root_edit)
        form.addRow("Triplet", self.triplet_edit)
        layout.addLayout(form)

        grid = QGridLayout()
        buttons = [
            ("刷新状态", self.refresh_status),
            ("引导 vcpkg", self.bootstrap_vcpkg),
            ("安装 RAT + NL", lambda: self.install_rat(True)),
            ("安装 RAT（无 NL）", lambda: self.install_rat(False)),
            ("构建 pyRat Wheel", self.build_pyrat),
            ("打开工作区", lambda: self.safe_open(WORKSPACE_ROOT)),
            ("打开 RAT 文档", lambda: self.safe_open(REPOSITORIES["rat-documentation"])),
            ("打开 Windows 指南", lambda: self.safe_open(DOC_FILES["Windows 安装指南"])),
            ("打开磁体工作区", lambda: self.safe_open(CCT_WORKBENCH_ROOT)),
        ]
        for index, (label, callback) in enumerate(buttons):
            button = QPushButton(label)
            button.clicked.connect(callback)
            self._register_busy_widget(button)
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)

        layout.addWidget(self.status_text, 1)
        return widget

    def toggle_inspector_action(self):
        return self.inspector_toggle_action

    def toggle_editor_action(self):
        return self.editor_toggle_action

    def toggle_log_action(self):
        return self.log_toggle_action

    def restore_default_layout(self, _checked=False):
        self.set_inspector_visible(True)
        self.set_editor_visible(True)
        self.set_log_visible(False)
        self.inspector_toggle_action.setChecked(True)
        self.editor_toggle_action.setChecked(True)
        self.log_toggle_action.setChecked(False)
        if hasattr(self, "main_splitter"):
            self.main_splitter.setSizes([320, 1220, 360])
        if hasattr(self, "left_splitter"):
            self.left_splitter.setSizes([820, 0])
        self.statusBar().showMessage("已恢复默认面板布局", 3000)

    def show_editor_page(self, key):
        page = getattr(self, "editor_pages", {}).get(key)
        if page is None:
            return
        self.editor_stack.setCurrentWidget(page)
        self.current_editor_page_key = key
        titles = {
            "summary": ("当前对象", "显示当前示例或工程的摘要与入口路径。"),
            "design": ("参数配置", "在这里修改磁体建模参数。"),
            "outputs": ("输出文件", "选择结果文件并切换导体磁场、网格或切片视图。"),
            "preview": ("文本预览", "查看输出文件内容、CSV 片段和元数据。"),
            "environment": ("环境与工具", "查看工具链状态，执行安装、构建与工作区操作。"),
            "help": ("使用说明", "查看当前磁体类型说明和界面使用提示。"),
        }
        title, subtitle = titles.get(key, ("节点编辑器", "左侧模型树用于切换当前对象、参数页和结果视图。"))
        self.editor_title.setText(title)
        self.editor_subtitle.setText(subtitle)
        self.ensure_editor_panel_visible()
        target_item = getattr(self, "model_tree_page_items", {}).get(key)
        if target_item is not None and hasattr(self, "model_tree") and self.model_tree.currentItem() is not target_item:
            self.model_tree.blockSignals(True)
            self.model_tree.setCurrentItem(target_item)
            self.model_tree.blockSignals(False)

    def _make_tree_nav_item(self, parent, label, kind=None, value=None, selectable=True):
        item = QTreeWidgetItem(parent, [label])
        if selectable and kind is not None:
            item.setData(0, Qt.UserRole, kind)
            item.setData(0, Qt.UserRole + 1, value)
        else:
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        return item

    def _append_output_nodes(self, parent, checked_paths):
        output_group = self._make_tree_nav_item(parent, "输出与结果", selectable=False)
        output_page = self._make_tree_nav_item(output_group, "输出文件", kind="page", value="outputs")
        preview_page = self._make_tree_nav_item(output_group, "文本预览", kind="page", value="preview")
        self.model_tree_page_items["outputs"] = output_page
        self.model_tree_page_items["preview"] = preview_page

        view_group = self._make_tree_nav_item(output_group, "结果视图", selectable=False)
        for key, label in (
            ("coil_magnetic", "导体磁场"),
            ("coil_current", "线圈电流密度"),
            ("coil_mesh", "线圈网格"),
            ("slice", "二维切片"),
        ):
            item = self._make_tree_nav_item(view_group, label, kind="view", value=key)
            self.model_tree_view_items[key] = item

        layer_group = self._make_tree_nav_item(output_group, "线圈层显示", selectable=False)
        if self.current_coil_layer_paths:
            for index, path in enumerate(self.current_coil_layer_paths, start=1):
                item = QTreeWidgetItem(layer_group, [f"第 {index} 层 | {path.name}"])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                item.setData(0, Qt.UserRole, "layer")
                item.setData(0, Qt.UserRole + 1, str(path))
                item.setCheckState(0, Qt.Checked if str(path) in checked_paths else Qt.Unchecked)
                self.model_tree_layer_items[str(path)] = item
        else:
            placeholder = QTreeWidgetItem(layer_group, ["当前结果暂无可切换线圈层"])
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsSelectable)

        return output_group

    def _append_active_model_nodes(self, parent, checked_paths):
        model_node = self._make_tree_nav_item(parent, "当前模型", selectable=False)
        if self.active_context is None:
            self._make_tree_nav_item(model_node, "尚未选择示例或工程", selectable=False)
            calc_group = self._make_tree_nav_item(model_node, "计算与设置", selectable=False)
            self.model_tree_page_items["environment"] = self._make_tree_nav_item(calc_group, "环境", kind="page", value="environment")
            self.model_tree_page_items["help"] = self._make_tree_nav_item(calc_group, "使用说明", kind="page", value="help")
            return

        context = self.active_context
        if context["kind"] == "example":
            example_node = self._make_tree_nav_item(
                model_node,
                f"示例 | {context['name']}",
                kind="page",
                value="summary",
            )
            self.model_tree_page_items["summary"] = example_node
            info_group = self._make_tree_nav_item(example_node, "信息与设置", selectable=False)
            self._make_tree_nav_item(info_group, f"标题 | {context['title']}", kind="page", value="summary")
            self.model_tree_page_items["environment"] = self._make_tree_nav_item(info_group, "环境", kind="page", value="environment")
            self.model_tree_page_items["help"] = self._make_tree_nav_item(info_group, "使用说明", kind="page", value="help")
            self._append_output_nodes(example_node, checked_paths)
            return

        project_info = self.active_cct_project or {}
        profile_id = project_info.get("profile_id", self.current_profile_id())
        params = project_info.get("params") or self.collect_cct_values()

        project_node = self._make_tree_nav_item(
            model_node,
            f"{context['title']} | {context['name']}",
            kind="page",
            value="summary",
        )
        self.model_tree_page_items["summary"] = project_node
        profile_label = self.cct_profiles.get(profile_id, {}).get("label", profile_id)
        geometry_group = self._make_tree_nav_item(project_node, "几何结构", selectable=False)
        self._make_tree_nav_item(geometry_group, f"类型 | {profile_label}", kind="page", value="design")

        layer_count = max(1, int(params.get("num_layers", 1)))
        geometry_node = self._make_tree_nav_item(
            geometry_group,
            f"几何层 | {layer_count} 层",
            kind="page",
            value="design",
        )

        if profile_id == "cos_theta":
            for layer_index in range(1, layer_count + 1):
                layer_node = self._make_tree_nav_item(
                    geometry_node,
                    f"第 {layer_index} 层 Cosine-Theta",
                    kind="page",
                    value="design",
                )
                raw_blocks = params.get(f"layer{layer_index}_blocks", "")
                try:
                    blocks = parse_cos_theta_blocks(raw_blocks)
                except ValueError:
                    blocks = []
                if not blocks:
                    self._make_tree_nav_item(layer_node, "未定义 block", kind="page", value="design")
                    continue
                for block_index, block in enumerate(blocks, start=1):
                    label = (
                        f"Block {block_index} | cables={block['num_cables']} "
                        f"phi={block['phi_deg']:.1f}° alpha={block['alpha_deg']:.1f}°"
                    )
                    self._make_tree_nav_item(layer_node, label, kind="page", value="design")
        else:
            for layer_index in range(1, layer_count + 1):
                self._make_tree_nav_item(
                    geometry_node,
                    f"第 {layer_index} 层线圈",
                    kind="page",
                    value="design",
                )

        calculation_group = self._make_tree_nav_item(project_node, "计算与设置", selectable=False)
        self.model_tree_page_items["design"] = self._make_tree_nav_item(calculation_group, "参数配置", kind="page", value="design")
        self.model_tree_page_items["environment"] = self._make_tree_nav_item(calculation_group, "环境", kind="page", value="environment")
        self.model_tree_page_items["help"] = self._make_tree_nav_item(calculation_group, "使用说明", kind="page", value="help")

        self._append_output_nodes(project_node, checked_paths)

    def refresh_model_browser_tree(self):
        if not hasattr(self, "model_tree"):
            return

        current_item = self.model_tree.currentItem()
        selected_kind = current_item.data(0, Qt.UserRole) if current_item is not None else None
        selected_value = current_item.data(0, Qt.UserRole + 1) if current_item is not None else None
        checked_paths = {str(path) for path in self.visible_coil_layer_paths()}

        self._populating_model_tree = True
        self.model_tree.clear()
        self.model_tree_page_items = {}
        self.model_tree_view_items = {}
        self.model_tree_layer_items = {}

        model_root = QTreeWidgetItem(["模型结构"])
        model_root.setFlags(model_root.flags() & ~Qt.ItemIsSelectable)
        self.model_tree.addTopLevelItem(model_root)

        self._append_active_model_nodes(model_root, checked_paths)

        self.model_tree.expandAll()
        self._populating_model_tree = False

        target_item = None
        preferred_page = self.current_editor_page_key
        if preferred_page and preferred_page != "outputs":
            target_item = self.model_tree_page_items.get(preferred_page)
        if target_item is None:
            if selected_kind == "page":
                target_item = self.model_tree_page_items.get(selected_value)
            elif selected_kind == "view":
                target_item = self.model_tree_view_items.get(selected_value)
            elif selected_kind == "layer":
                target_item = self.model_tree_layer_items.get(selected_value)
        if target_item is None:
            target_item = self.model_tree_page_items.get(self.current_editor_page_key, self.model_tree_page_items.get("summary"))
        if target_item is not None:
            self.model_tree.blockSignals(True)
            self.model_tree.setCurrentItem(target_item)
            self.model_tree.blockSignals(False)

    def on_model_tree_selection_changed(self, current, _previous):
        if self._populating_model_tree or current is None:
            return
        kind = current.data(0, Qt.UserRole)
        value = current.data(0, Qt.UserRole + 1)
        if kind == "page":
            self.show_editor_page(value)
            return
        if kind == "view":
            self.show_editor_page("outputs")
            if value == "coil_magnetic":
                self.load_coil_magnetic_field_visualization()
            elif value == "coil_current":
                self.load_coil_current_density_visualization()
            elif value == "coil_mesh":
                self.load_coil_mesh_visualization()
            elif value == "slice":
                self.load_slice_visualization()
            return
        if kind == "layer":
            self.show_editor_page("outputs")

    def on_model_tree_item_changed(self, item, _column):
        if self._populating_model_tree:
            return
        if item.data(0, Qt.UserRole) != "layer":
            return
        layer_path = item.data(0, Qt.UserRole + 1)
        checked = item.checkState(0) == Qt.Checked
        self._populating_coil_layer_list = True
        for index in range(self.coil_layer_list.count()):
            list_item = self.coil_layer_list.item(index)
            if list_item.data(Qt.UserRole) == layer_path:
                list_item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                break
        self._populating_coil_layer_list = False
        self.apply_coil_layer_visibility()

    def open_help(self, _checked=False):
        self.show_editor_page("help")

    def update_help_panel(self):
        profile_id = self.current_profile_id() or "mini_cct"
        profile = self.cct_profiles.get(profile_id, {})
        lines = [
            "界面使用说明",
            "",
            "1. 左侧用于模型树浏览与按层勾选线圈显示。",
            "2. View 菜单中可切换导体磁场、电流密度、线圈网格、二维切片，以及前视/侧视/顶视/等轴测。",
            "3. 网格线、包围盒、色标和切片叠加线圈，也统一放在 View 菜单里。",
            "4. 右侧保留给参数配置与工程操作。",
            "5. 左下日志可通过 Window 菜单按需显示。",
            "6. 只点“编译磁体”不会生成结果文件；结果请用“运行磁体”或“编译并运行”。",
            "",
            f"当前磁体类型：{profile.get('label', profile_id)}",
            "",
            profile.get("summary", "").strip(),
            "",
            self.cct_orientation_note.text().strip(),
        ]
        self.help_text.setPlainText("\n".join(line for line in lines if line).strip())

    def update_view_preferences(self, _checked=False):
        if self.current_actor is not None:
            self.current_actor.GetProperty().SetEdgeVisibility(1 if self.show_mesh_edges_action.isChecked() else 0)
        for actor in self.current_coil_layer_actors.values():
            actor.GetProperty().SetEdgeVisibility(1 if self.show_mesh_edges_action.isChecked() else 0)
        if self.current_outline_actor is not None:
            self.current_outline_actor.SetVisibility(1 if self.show_outline_action.isChecked() else 0)
        if self.current_scalar_bar is not None:
            self.current_scalar_bar.SetVisibility(1 if self.show_scalar_bar_action.isChecked() else 0)
            self._apply_scalar_bar_layout(self.current_scalar_bar)
        self.apply_coil_layer_visibility()
        if self.vtk_widget is not None:
            self.vtk_widget.GetRenderWindow().Render()

    def _sync_scalar_bar_position_actions(self):
        left_action = getattr(self, "scalar_bar_left_action", None)
        right_action = getattr(self, "scalar_bar_right_action", None)
        if left_action is None or right_action is None:
            return
        left_action.blockSignals(True)
        right_action.blockSignals(True)
        left_action.setChecked(self.scalar_bar_position == "left")
        right_action.setChecked(self.scalar_bar_position == "right")
        left_action.blockSignals(False)
        right_action.blockSignals(False)

    def set_scalar_bar_position(self, position):
        position = "left" if position == "left" else "right"
        self.scalar_bar_position = position
        self._sync_scalar_bar_position_actions()
        if self.current_scalar_bar is not None:
            self._apply_scalar_bar_layout(self.current_scalar_bar)
            if self.vtk_widget is not None:
                self.vtk_widget.GetRenderWindow().Render()

    def _register_busy_widget(self, widget):
        self.busy_widgets.append(widget)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def set_busy(self, busy):
        for widget in self.busy_widgets:
            widget.setEnabled(not busy)
        for action in self.busy_actions:
            action.setEnabled(not busy)
        self.example_combo.setEnabled(not busy)
        self.profile_combo.setEnabled(not busy)
        self.project_name_edit.setEnabled(not busy)
        for widget in self.cct_field_widgets.values():
            widget.setEnabled(not busy)

    def append_log(self, text):
        cleaned = ANSI_RE.sub("", text.rstrip("\r\n"))
        self.log_text.appendPlainText(cleaned)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_status_text(self, content):
        self.status_text.setPlainText(content)

    def set_preview_text(self, content):
        self.preview_text.setPlainText(content)

    def show_warning(self, title, message):
        QMessageBox.warning(self, title, message)

    def show_error(self, title, message):
        QMessageBox.critical(self, title, message)

    def safe_open(self, path):
        try:
            open_path(path)
        except FileNotFoundError as exc:
            self.show_error("加载结果失败", str(exc))

    def current_example(self):
        return self.example_combo.currentText().strip()

    def current_profile_id(self):
        return (self.profile_combo.currentData() or self.profile_combo.currentText()).strip()

    def current_output_dir(self):
        if self.active_context is None:
            return None
        return self.active_context.get("output_dir")

    def selected_output_path(self):
        item = self.output_list.currentItem()
        if item is None:
            return None
        data = item.data(Qt.UserRole)
        return Path(data) if data else None

    def find_coil_layer_paths(self):
        layer_paths = []
        for path in self.output_paths:
            name = path.name.lower()
            if (
                path.suffix.lower() == ".vtu"
                and (
                    "coil_field_mesh" in name
                    or name.startswith("coilmesh")
                )
            ):
                candidate = self.resolve_visualization_target(path)
                if candidate is not None and candidate.suffix.lower() == ".vtu":
                    layer_paths.append(candidate)
        return sorted(layer_paths)

    def refresh_coil_layer_list(self):
        previous_states = {}
        for index in range(self.coil_layer_list.count()):
            item = self.coil_layer_list.item(index)
            previous_states[item.data(Qt.UserRole)] = item.checkState() == Qt.Checked

        self._populating_coil_layer_list = True
        self.coil_layer_list.clear()
        self.current_coil_layer_paths = self.find_coil_layer_paths()
        for index, path in enumerate(self.current_coil_layer_paths, start=1):
            item = QListWidgetItem(f"第 {index} 层 | {path.name}")
            item.setData(Qt.UserRole, str(path))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            checked = previous_states.get(str(path), True)
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            self.coil_layer_list.addItem(item)
        self._populating_coil_layer_list = False
        layer_count = self.coil_layer_list.count()
        if hasattr(self, "layer_panel_label"):
            if layer_count > 0:
                self.layer_panel_label.setText(f"线圈层显示（{layer_count} 层）")
            else:
                self.layer_panel_label.setText("线圈层显示（当前无结果）")
        for button_name in ("show_all_layers_button", "hide_all_layers_button"):
            button = getattr(self, button_name, None)
            if button is not None:
                button.setEnabled(layer_count > 0)
        if hasattr(self, "layer_panel"):
            self.layer_panel.setVisible(True)
        self.refresh_model_browser_tree()

    def visible_coil_layer_paths(self):
        selected = []
        for index in range(self.coil_layer_list.count()):
            item = self.coil_layer_list.item(index)
            if item.checkState() == Qt.Checked:
                path = item.data(Qt.UserRole)
                if path:
                    selected.append(Path(path))
        return selected

    def show_all_coil_layers(self):
        self._set_all_coil_layer_checks(True)

    def hide_all_coil_layers(self):
        self._set_all_coil_layer_checks(False)

    def _set_all_coil_layer_checks(self, checked):
        if self.coil_layer_list.count() == 0:
            return
        self._populating_coil_layer_list = True
        for index in range(self.coil_layer_list.count()):
            item = self.coil_layer_list.item(index)
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self._populating_coil_layer_list = False
        self.apply_coil_layer_visibility()

    def on_coil_layer_visibility_changed(self, _item):
        if self._populating_coil_layer_list:
            return
        self._populating_model_tree = True
        for path_str, item in self.model_tree_layer_items.items():
            should_check = False
            for index in range(self.coil_layer_list.count()):
                list_item = self.coil_layer_list.item(index)
                if list_item.data(Qt.UserRole) == path_str:
                    should_check = list_item.checkState() == Qt.Checked
                    break
            item.setCheckState(0, Qt.Checked if should_check else Qt.Unchecked)
        self._populating_model_tree = False
        self.apply_coil_layer_visibility()

    def apply_coil_layer_visibility(self):
        checked_paths = {str(path) for path in self.visible_coil_layer_paths()}
        show_layers = True if self.current_visual_path and self.is_coil_mesh_target(self.current_visual_path) else self.show_coil_overlay_action.isChecked()
        for path_str, actor in self.current_coil_layer_actors.items():
            if self.coil_layer_list.count() > 0:
                visible = show_layers and path_str in checked_paths
            else:
                visible = show_layers
            actor.SetVisibility(1 if visible else 0)
        if self.vtk_widget is not None:
            self.vtk_widget.GetRenderWindow().Render()

    def find_first_result_target(self, *tokens):
        lowered_tokens = tuple(token.lower() for token in tokens)
        candidates = []
        for path in self.output_paths:
            name = path.name.lower()
            if any(token in name or name.startswith(token) for token in lowered_tokens):
                target = self.resolve_visualization_target(path)
                if target is not None:
                    candidates.append(target)
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: item.name.lower())[0]

    def select_output_for_target(self, target):
        if target is None:
            return False
        target = Path(target)
        for index, path in enumerate(self.output_paths):
            if self.resolve_visualization_target(path) == target:
                if self.output_list.currentRow() == index:
                    return self.load_visualization(target, quiet=False)
                self.output_list.setCurrentRow(index)
                return True
        return False

    def load_result_family(self, *tokens):
        target = self.find_first_result_target(*tokens)
        if target is None:
            self.show_warning("结果不存在", "当前结果目录中还没有对应的可视化文件。")
            return False
        if not self.select_output_for_target(target):
            return self.load_visualization(target, quiet=False)
        return True

    def load_volume_visualization(self):
        return self.load_slice_visualization()

    def load_slice_visualization(self):
        return self.load_result_family("space_field_slice", "grid")

    def load_coil_visualization(self):
        return self.load_coil_magnetic_field_visualization()

    def load_coil_magnetic_field_visualization(self):
        self.current_coil_visual_mode = "magnetic_flux_density"
        return self.load_result_family("coil_field_mesh", "coilmesh")

    def load_coil_current_density_visualization(self):
        self.current_coil_visual_mode = "current_density"
        return self.load_result_family("coil_field_mesh", "coilmesh")

    def load_coil_mesh_visualization(self):
        self.current_coil_visual_mode = "mesh"
        if not self.show_mesh_edges_action.isChecked():
            self.show_mesh_edges_action.setChecked(True)
        return self.load_result_family("coil_field_mesh", "coilmesh")

    def make_example_context(self, name):
        if not name:
            return None
        metadata = get_example_metadata(name)
        project_dir = get_example_root(name)
        output_dir = get_example_output_dir(name)
        return {
            "kind": "example",
            "name": name,
            "title": metadata["title"],
            "summary": metadata["summary"],
            "project_dir": project_dir,
            "source_path": get_example_source_path(name),
            "output_dir": output_dir,
            "expected": metadata["expected"],
            "executable_name": name,
            "executable": find_project_executable(project_dir, name) if project_dir else None,
            "label": f"内置示例 / {name}",
        }

    def make_cct_context(self, project_info):
        project_dir = Path(project_info["project_dir"])
        output_dir = Path(project_info["output_dir"])
        executable_name = project_info["executable_name"]
        return {
            "kind": "cct",
            "name": project_info["project_name"],
            "title": project_info["profile_label"],
            "summary": self.cct_profiles.get(project_info["profile_id"], {}).get(
                "summary", "适合快速搭建磁体工程，并在结果页面查看线圈和场分布。"
            ),
            "project_dir": project_dir,
            "source_path": Path(project_info["source_path"]),
            "output_dir": output_dir,
            "expected": project_info.get(
                "expected_outputs",
                ["coil_field_mesh*.vtu", "space_field_slice*.vti", "field_harmonics*.vtu", "space_field_volume*.vti"],
            ),
            "executable_name": executable_name,
            "executable": find_project_executable(project_dir, executable_name),
            "label": f"磁体工程 / {project_info['project_name']}",
            "meta_path": Path(project_info["meta_path"]),
        }

    def activate_example_context(self, name):
        context = self.make_example_context(name)
        if context is None:
            return
        self.active_context = context
        self.refresh_results()

    def activate_cct_context(self, project_info):
        self.active_cct_project = project_info
        self.active_context = self.make_cct_context(project_info)
        profile_index = self.profile_combo.findData(project_info["profile_id"])
        if profile_index >= 0:
            self.profile_combo.blockSignals(True)
            self.profile_combo.setCurrentIndex(profile_index)
            self.profile_combo.blockSignals(False)
        self.rebuild_cct_form()
        self.project_name_edit.setText(project_info["project_name"])
        profile = self.cct_profiles.get(project_info["profile_id"], {})
        params = project_info.get("params", {})
        for field in profile.get("fields", []):
            widget = self.cct_field_widgets.get(field["key"])
            if widget is None or field["key"] not in params:
                continue
            value = params[field["key"]]
            if field["type"] == "int":
                widget.setValue(int(value))
            elif field["type"] == "bool":
                widget.setChecked(bool(value))
            elif field["type"] == "multiline":
                widget.setPlainText(str(value))
            elif field["type"] == "text":
                widget.setText(str(value))
            else:
                widget.setValue(float(value))
        self.refresh_results()

    def update_summary_panel(self, context):
        self.summary_kind.setText(context["label"])
        self.summary_title.setText(context["title"])
        self.summary_summary.setText(context["summary"])

        expected = " / ".join(context.get("expected", [])) or "暂无输出说明"
        source_text = str(context.get("source_path") or "未找到源文件")
        exe_text = str(context.get("executable") or "尚未构建")
        project_text = str(context.get("project_dir") or "未设置")
        output_text = str(context.get("output_dir") or "未设置")
        self.summary_paths.setText(
            "<b>工程目录</b><br>"
            + project_text
            + "<br><br><b>源文件</b><br>"
            + source_text
            + "<br><br><b>可执行文件</b><br>"
            + exe_text
            + "<br><br><b>输出目录</b><br>"
            + output_text
            + "<br><br><b>预期输出</b><br>"
            + expected
        )

    def read_preview(self, path):
        try:
            stat = path.stat()
        except OSError as exc:
            return f"读取文件属性失败：{exc}"

        lines = [f"文件: {path.name}", f"路径: {path}", f"大小: {stat.st_size} 字节", ""]
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                snippet = handle.read(8000)
        except OSError as exc:
            return "\n".join(lines + [f"读取文件内容失败：{exc}"])

        if not snippet.strip():
            snippet = "<文件为空或暂时没有可预览文本>"
        elif len(snippet) >= 8000:
            snippet += "\n...\n<内容已截断>"
        return "\n".join(lines + [snippet.strip()])

    def format_output_label(self, path, base_dir):
        try:
            relative = path.relative_to(base_dir)
        except ValueError:
            relative = path

        name = path.name
        lower_name = name.lower()
        alias = None
        if lower_name.startswith("space_field_volume"):
            alias = "三维空间场"
        elif lower_name.startswith("space_field_slice") or lower_name.startswith("grid"):
            alias = "二维切片"
        elif lower_name.startswith("coil_field_mesh") or lower_name.startswith("coilmesh"):
            alias = "导体磁场 / 电流密度 / 线圈网格"
        elif lower_name.startswith("field_harmonics") or lower_name.startswith("harmonics"):
            alias = "谐波采样面"
        elif path.suffix.lower() == ".cond":
            alias = "OPERA 导体文件"

        if alias is None:
            return str(relative)

        time_match = re.search(r"pt(\d+)tm(\d+)", lower_name)
        suffix = path.suffix.lower()
        if time_match:
            point_index = int(time_match.group(1))
            time_index = int(time_match.group(2))
            return f"{alias} [{suffix[1:].upper()} | 采样 {point_index} | 时刻 {time_index}]"
        if suffix == ".pvd":
            return f"{alias} [索引]"
        return f"{alias} [{suffix[1:].upper()}]"

    def refresh_status(self):
        status = collect_status()
        self.set_status_text(format_status_report(status))

        current_example = self.current_example()
        current_cct = self.active_context if self.active_context and self.active_context.get("kind") == "cct" else None
        example_names = status["examples"] or [""]

        self.example_combo.blockSignals(True)
        self.example_combo.clear()
        self.example_combo.addItems(example_names)
        if current_example in example_names:
            self.example_combo.setCurrentText(current_example)
        elif example_names:
            self.example_combo.setCurrentIndex(0)
        self.example_combo.blockSignals(False)

        self.example_names = example_names
        if current_cct is not None:
            self.active_context = current_cct
        elif example_names and example_names[0]:
            self.active_context = self.make_example_context(self.example_combo.currentText())

        self.refresh_results()

    def refresh_results(self):
        if self.active_context is None:
            self.output_paths = []
            self.output_list.clear()
            self.refresh_coil_layer_list()
            self.set_preview_text("当前没有可预览的文件。")
            self.clear_visualization("未加载结果", "请先选择一个示例或磁体工程。")
            self.refresh_model_browser_tree()
            return

        if self.active_context["kind"] == "example":
            self.active_context = self.make_example_context(self.active_context["name"])
        else:
            self.active_context["executable"] = find_project_executable(
                self.active_context["project_dir"], self.active_context["executable_name"]
            )

        self.update_summary_panel(self.active_context)

        output_dir = self.active_context.get("output_dir")
        self.output_paths = list_output_files(output_dir)
        self.output_list.clear()
        self.refresh_coil_layer_list()
        if not self.output_paths:
            target_name = "当前磁体工程" if self.active_context["kind"] == "cct" else "当前示例"
            self.set_preview_text(f"结果 {target_name} 目录下还没有生成可视化文件。")
            self.clear_visualization("未加载结果", f"结果 {target_name} 目录下还没有可加载的 VTK 文件。")
            self.refresh_model_browser_tree()
            return

        base_dir = output_dir if output_dir else WORKSPACE_ROOT
        for path in self.output_paths:
            label = self.format_output_label(path, base_dir)
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, str(path))
            self.output_list.addItem(item)

        preferred = self.find_default_visualization_path()
        selected_row = 0
        if preferred is not None:
            for index, path in enumerate(self.output_paths):
                if self.resolve_visualization_target(path) == preferred:
                    selected_row = index
                    break
        self.output_list.blockSignals(True)
        self.output_list.setCurrentRow(selected_row)
        self.output_list.blockSignals(False)
        current_item = self.output_list.item(selected_row)
        if current_item is not None:
            self.on_output_selection_changed(current_item, None)
        self.refresh_model_browser_tree()

    def on_example_changed(self, name):
        if not name:
            return
        self.activate_example_context(name)

    def on_profile_changed(self, _profile_id):
        self.show_editor_page("design")
        self.rebuild_cct_form()

    def create_field_widget(self, field):
        if field["type"] == "int":
            widget = QSpinBox()
            widget.setRange(-1_000_000, 1_000_000)
            widget.setSingleStep(1)
            widget.setValue(int(field["default"]))
            return widget

        if field["type"] == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(field.get("default", False)))
            return widget

        if field["type"] == "multiline":
            widget = QPlainTextEdit(str(field.get("default", "")))
            widget.setPlaceholderText(field.get("placeholder", ""))
            widget.setMinimumHeight(96)
            widget.setMaximumHeight(156)
            return widget

        if field["type"] == "text":
            widget = QLineEdit(str(field.get("default", "")))
            widget.setPlaceholderText(field.get("placeholder", ""))
            return widget

        widget = QDoubleSpinBox()
        widget.setDecimals(8)
        widget.setRange(-1_000_000_000.0, 1_000_000_000.0)
        widget.setSingleStep(0.001 if abs(float(field["default"])) < 1 else 0.1)
        widget.setValue(float(field["default"]))
        return widget

    def rebuild_cct_form(self):
        profile_id = self.current_profile_id() or "mini_cct"
        profile = self.cct_profiles[profile_id]

        self._clear_layout(self.cct_form_layout)
        self.cct_field_widgets = {}
        self.cct_profile_summary.setText(profile["summary"])
        note = profile.get("note")
        if note:
            self.cct_orientation_note.setText(note)
        elif profile_id == "mini_cct":
            self.cct_orientation_note.setText(
                "默认截面方向：dcable 为沿骨架切向的槽宽，wcable 为沿骨架法向的槽深。"
                " 直线 CCT 默认附加截面扭转为 0°。"
                " 层数增加后，可用每层列表分别覆盖匝数、匝间距、倾角和电流。"
                " 适合快速搭建多层 mini CCT。"
                " 如需 Frenet-Serret 坐标系，请切换到 custom CCT。"
            )
        elif profile_id == "custom_cct":
            self.cct_orientation_note.setText(
                "默认截面方向：dcable 为沿骨架切向的槽宽，wcable 为沿骨架法向的槽深。"
                " custom CCT 支持弯转半径、二极/四极叠加和多层路径。"
                " 可用每层列表分别覆盖半径、节距、谐波、电流和附加扭转。"
                " 勾选 Frenet-Serret 后，PathCCTCustom 会按 RAT 原生 Frenet-Serret 坐标系生成截面取向。"
            )
        else:
            self.cct_orientation_note.setText(
                "Cosine-theta 模块基于 PathCosTheta / CosThetaBlock。"
                " 每层块定义中的每一行格式为: cables, phi_deg, alpha_deg, zend_m, beta_deg。"
                " 默认第 1 层直出，第 2 层采用 YZ 镜像并反向绕制，用来快速搭建双层 cos-theta 端部线圈。"
                " 块角度会按极数自动缩放到对应扇区，二极模板可直接扩展到四极、六极。"
                " 如果导体块看起来粗糙，优先减小“单元尺寸”，再增大“截面厚向分段数”和“截面宽向分段数”。"
                " 如果想让一个扇区里出现更多物理 block，则继续在“每层块定义”里增加行数。"
                " 极数 1=二极，2=四极，3=六极；界面生成时会自动复制成完整多极装配，不再只保留单个线圈。"
            )
        self.project_name_edit.setText(profile["project_name"])
        self.update_help_panel()

        sections = self._group_fields_for_profile(profile_id, profile["fields"])
        for section in sections:
            frame, form_layout = self._create_param_group(profile_id, section["title"], section["expanded"])
            for field in section["fields"]:
                widget = self.create_field_widget(field)
                self.cct_field_widgets[field["key"]] = widget
                form_layout.addRow(field["label"], widget)
            self.cct_form_layout.addWidget(frame)
        self.cct_form_layout.addStretch(1)
        self.refresh_model_browser_tree()

    def collect_cct_values(self):
        values = {}
        for field in self.cct_profiles[self.current_profile_id()]["fields"]:
            widget = self.cct_field_widgets[field["key"]]
            if field["type"] == "int":
                values[field["key"]] = int(widget.value())
            elif field["type"] == "bool":
                values[field["key"]] = bool(widget.isChecked())
            elif field["type"] == "multiline":
                values[field["key"]] = widget.toPlainText().strip()
            elif field["type"] == "text":
                values[field["key"]] = widget.text().strip()
            else:
                values[field["key"]] = float(widget.value())
        return values

    def current_cct_signature(self):
        profile_id = self.current_profile_id()
        profile = self.cct_profiles[profile_id]
        project_name = sanitize_project_name(self.project_name_edit.text().strip() or profile["project_name"])
        return {
            "profile_id": profile_id,
            "project_name": project_name,
            "params": self.collect_cct_values(),
        }

    def is_cct_design_active(self):
        return self.current_editor_page_key == "design"

    def cct_form_has_pending_changes(self):
        if self.active_cct_project is None:
            return True
        signature = self.current_cct_signature()
        return (
            self.active_cct_project.get("profile_id") != signature["profile_id"]
            or self.active_cct_project.get("project_name") != signature["project_name"]
            or self.active_cct_project.get("params") != signature["params"]
        )

    def ensure_cct_project_current(self):
        if self.cct_form_has_pending_changes():
            self.generate_cct_project()
        return self.active_cct_context()

    def generate_cct_project(self):
        self.show_editor_page("design")
        profile_id = self.current_profile_id()
        project_name = self.project_name_edit.text().strip()
        params = self.collect_cct_values()
        project_info = write_cct_project(profile_id, project_name, params)
        self.append_log("")
        self.append_log(f"### 生成磁体工程: {project_info['project_name']}")
        self.append_log(str(project_info["project_dir"]))
        self.activate_cct_context(project_info)
        self.statusBar().showMessage(f"已生成磁体工程：{project_info['project_name']}", 4000)
        return project_info

    def active_cct_context(self):
        if self.active_context and self.active_context.get("kind") == "cct":
            return self.active_context
        if self.active_cct_project:
            self.active_context = self.make_cct_context(self.active_cct_project)
            return self.active_context
        return None

    def open_active_cct_project(self):
        context = self.active_cct_context()
        if context is None:
            self.show_warning("无磁体工程", "当前还没有生成磁体工程。")
            return
        self.safe_open(context["project_dir"])

    def open_active_cct_output(self):
        context = self.active_cct_context()
        if context is None:
            self.show_warning("无磁体工程", "当前还没有生成磁体工程。")
            return
        if not context["output_dir"].exists():
            self.show_warning("输出不存在", "该磁体工程还没有输出目录。")
            return
        self.safe_open(context["output_dir"])

    def current_opera_path(self):
        output_dir = self.current_output_dir()
        if not output_dir or not output_dir.exists():
            return None
        matches = sorted(output_dir.glob("*.cond"))
        return matches[0] if matches else None

    def open_current_opera(self):
        opera_path = self.current_opera_path()
        if opera_path is None:
            self.show_warning("未找到 OPERA 文件", "当前输出目录下还没有生成 .cond 导体文件。")
            return
        self.safe_open(opera_path)

    def export_current_opera(self):
        if not self.is_cct_design_active() and (self.active_context is None or self.active_context.get("kind") != "cct"):
            self.show_warning("仅支持磁体工程", "请先进入磁体设计页或选择一个磁体工程，再导出 OPERA .cond。")
            return

        project_info = self.generate_cct_project()
        context = self.make_cct_context(project_info)
        self.run_manager_action(
            f"构建并导出 OPERA .cond {context['name']}",
            "build-export-cct-opera",
            project_dir=context["project_dir"],
            executable_name=context["executable_name"],
            finished_callback=self.make_refresh_cct_callback(context["name"]),
        )

    def on_output_selection_changed(self, current, _previous):
        if current is None:
            self.set_preview_text("未选中输出文件。")
            return

        output_path = self.selected_output_path()
        if output_path is None:
            return

        self.set_preview_text(self.read_preview(output_path))
        visual_target = self.resolve_visualization_target(output_path)
        if visual_target is not None:
            self.load_visualization(visual_target, quiet=True)

    def open_current_project(self):
        if self.active_context is None or not self.active_context.get("project_dir"):
            self.show_warning("无工程上下文", "当前没有可打开的工程目录。")
            return
        self.safe_open(self.active_context["project_dir"])

    def open_current_source(self):
        if self.active_context is None or not self.active_context.get("source_path"):
            self.show_warning("无源文件", "当前没有可打开的源文件。")
            return
        self.safe_open(self.active_context["source_path"])

    def open_output_folder(self):
        output_dir = self.current_output_dir()
        if not output_dir or not output_dir.exists():
            self.show_warning("输出不存在", "当前没有可打开的输出目录。")
            return
        self.safe_open(output_dir)

    def open_selected_result(self):
        path = self.selected_output_path()
        if path is None:
            self.show_warning("未选中文件", "请先选择一个输出文件。")
            return
        self.safe_open(path)

    def start_process(self, title, program, arguments, working_directory=None, finished_callback=None):
        if self.process is not None and self.process.state() != QProcess.NotRunning:
            self.show_warning("任务正在运行", "请等待当前进程结束后再次执行。")
            return

        self.process_title = title
        self.process_finished_callback = finished_callback
        self.append_log("")
        self.append_log(f"### {title}")
        self.append_log("$ " + " ".join([program, *arguments]))
        self.statusBar().showMessage(title)
        self.set_busy(True)

        process = QProcess(self)
        process.setProgram(program)
        process.setArguments(arguments)
        if working_directory:
            process.setWorkingDirectory(str(working_directory))
        process.readyReadStandardOutput.connect(self.on_process_stdout)
        process.readyReadStandardError.connect(self.on_process_stderr)
        process.finished.connect(self.on_process_finished)
        self.process = process
        process.start()

    def on_process_stdout(self):
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            for line in data.splitlines():
                self.append_log(line)

    def on_process_stderr(self):
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        if data:
            for line in data.splitlines():
                self.append_log(line)

    def on_process_finished(self, exit_code, _exit_status):
        title = self.process_title or "任务"
        success = exit_code == 0
        self.append_log(f"[{'完成' if success else '失败'}] {title}")
        self.statusBar().showMessage(f"{title}{'完成' if success else '失败'}", 4000)
        self.set_busy(False)

        callback = self.process_finished_callback
        self.process = None
        self.process_finished_callback = None
        self.refresh_status()
        if callback is not None:
            callback(success)

    def manager_arguments(self, action, project_dir=None, executable_name=None):
        arguments = [
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT_PATH),
            "-Action",
            action,
            "-WorkspaceRoot",
            str(WORKSPACE_ROOT),
            "-VcpkgRoot",
            self.vcpkg_root_edit.text().strip(),
            "-Triplet",
            self.triplet_edit.text().strip(),
            "-Example",
            self.current_example(),
        ]
        if project_dir is not None:
            arguments.extend(["-ProjectDir", str(project_dir)])
        if executable_name is not None:
            arguments.extend(["-ExecutableName", executable_name])
        return arguments

    def run_manager_action(self, title, action, project_dir=None, executable_name=None, finished_callback=None):
        self.start_process(
            title,
            "powershell.exe",
            self.manager_arguments(action, project_dir=project_dir, executable_name=executable_name),
            WORKSPACE_ROOT,
            finished_callback=finished_callback,
        )

    def make_refresh_cct_callback(self, project_name=None, keep_page=None, compile_only=False):
        def _callback(success):
            if self.active_cct_project is not None:
                if project_name and self.active_cct_project.get("project_name") != project_name:
                    return
                self.active_context = self.make_cct_context(self.active_cct_project)
            self.refresh_results()
            if self.current_coil_layer_paths:
                self.load_coil_magnetic_field_visualization()
            else:
                self.load_default_visualization(quiet=True)
            if keep_page:
                self.set_editor_visible(True)
                self.show_editor_page(keep_page)
                self.ensure_editor_panel_visible()
            if compile_only and success and not self.output_paths:
                self.set_preview_text("已完成编译，但当前输出目录还没有结果文件。\n请点击“运行磁体”或“编译并运行”生成线圈和场分布结果。")
                self.statusBar().showMessage("已完成编译；请继续运行磁体以生成结果文件。", 6000)

        return _callback

    def bootstrap_vcpkg(self):
        self.run_manager_action("引导 vcpkg", "bootstrap-vcpkg")

    def install_rat(self, enable_nl):
        if enable_nl:
            self.run_manager_action("安装 RAT + NL", "install-rat-models")
        else:
            self.run_manager_action("安装 RAT（无 NL）", "install-rat-models-no-nl")

    def build_pyrat(self):
        self.run_manager_action("构建 pyRat Wheel", "build-pyrat-wheel")

    def build_current(self):
        if self.is_cct_design_active():
            self.build_cct_project()
            return
        if self.active_context is None:
            self.show_warning("没有可构建对象", "请先选择一个内置示例或先生成磁体工程。")
            return
        if self.active_context["kind"] == "example":
            self.run_manager_action(f"构建示例 {self.active_context['name']}", "build-example")
        else:
            self.run_manager_action(
                f"构建磁体工程 {self.active_context['name']}",
                "build-cct-project",
                project_dir=self.active_context["project_dir"],
                executable_name=self.active_context["executable_name"],
                finished_callback=self.make_refresh_cct_callback(self.active_context["name"]),
            )

    def run_current(self):
        if self.is_cct_design_active():
            self.run_cct_project()
            return
        if self.active_context is None:
            self.show_warning("没有可运行对象", "请先选择一个内置示例或先生成磁体工程。")
            return
        if self.active_context["kind"] == "example":
            self.run_manager_action(f"运行示例 {self.active_context['name']}", "run-example")
        else:
            self.run_manager_action(
                f"运行磁体工程 {self.active_context['name']}",
                "run-cct-project",
                project_dir=self.active_context["project_dir"],
                executable_name=self.active_context["executable_name"],
                finished_callback=self.make_refresh_cct_callback(self.active_context["name"]),
            )

    def build_and_run_current(self):
        if self.is_cct_design_active():
            self.build_and_run_cct_project()
            return
        if self.active_context is None:
            self.show_warning("没有可运行对象", "请先选择一个内置示例或先生成磁体工程。")
            return
        if self.active_context["kind"] == "example":
            self.run_manager_action(f"构建并运行示例 {self.active_context['name']}", "build-run-example")
        else:
            self.run_manager_action(
                f"构建并运行磁体工程 {self.active_context['name']}",
                "build-run-cct-project",
                project_dir=self.active_context["project_dir"],
                executable_name=self.active_context["executable_name"],
                finished_callback=self.make_refresh_cct_callback(self.active_context["name"]),
            )

    def build_cct_project(self):
        self.show_editor_page("design")
        context = self.ensure_cct_project_current()
        self.run_manager_action(
            f"编译磁体工程 {context['name']}",
            "build-cct-project",
            project_dir=context["project_dir"],
            executable_name=context["executable_name"],
            finished_callback=self.make_refresh_cct_callback(context["name"], keep_page="design", compile_only=True),
        )

    def run_cct_project(self):
        self.show_editor_page("design")
        had_pending_changes = self.cct_form_has_pending_changes()
        context = self.ensure_cct_project_current()
        if context is None:
            self.show_warning("无磁体工程", "请先生成磁体工程。")
            return

        executable = find_project_executable(context["project_dir"], context["executable_name"])
        if had_pending_changes or executable is None:
            self.run_manager_action(
                f"构建并运行磁体工程 {context['name']}",
                "build-run-cct-project",
                project_dir=context["project_dir"],
                executable_name=context["executable_name"],
                finished_callback=self.make_refresh_cct_callback(context["name"], keep_page="design"),
            )
            return

        self.run_manager_action(
            f"运行磁体工程 {context['name']}",
            "run-cct-project",
            project_dir=context["project_dir"],
            executable_name=context["executable_name"],
            finished_callback=self.make_refresh_cct_callback(context["name"], keep_page="design"),
        )

    def build_and_run_cct_project(self):
        self.show_editor_page("design")
        context = self.ensure_cct_project_current()
        self.run_manager_action(
            f"构建并运行磁体工程 {context['name']}",
            "build-run-cct-project",
            project_dir=context["project_dir"],
            executable_name=context["executable_name"],
            finished_callback=self.make_refresh_cct_callback(context["name"], keep_page="design"),
        )

    def resolve_visualization_target(self, path):
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix in VIEWABLE_EXTENSIONS:
            return path
        if suffix == ".pvd":
            stem = path.stem
            for pattern in (
                f"{stem}*.vti",
                f"{stem}*.vtu",
                f"{stem}*.vtp",
                f"{stem}*.vtk",
                f"{stem}*.vts",
                f"{stem}*.vtm",
            ):
                matches = sorted(path.parent.glob(pattern))
                if matches:
                    return matches[0]
            for pattern in ("*.vti", "*.vtu", "*.vtp", "*.vtk", "*.vts", "*.vtm"):
                matches = sorted(path.parent.glob(pattern))
                if matches:
                    return matches[0]
        return None

    def find_default_visualization_path(self):
        def priority(path):
            name = path.name.lower()
            if "coil_field_mesh" in name or "coilmesh" in name:
                return 0
            if "space_field_slice" in name or "grid" in name:
                return 1
            if "field_harmonics" in name or "harmonics" in name:
                return 2
            if "space_field_volume" in name:
                return 3
            return 3

        for path in sorted(self.output_paths, key=priority):
            candidate = self.resolve_visualization_target(path)
            if candidate is not None:
                return candidate
        return None

    def is_field_result_target(self, path):
        name = Path(path).name.lower()
        return (
            "space_field_volume" in name
            or name.startswith("space_field_volume")
            or "space_field_slice" in name
            or name.startswith("space_field_slice")
            or name.startswith("grid")
            or "field_harmonics" in name
            or name.startswith("harmonics")
        )

    def is_harmonics_target(self, path):
        name = Path(path).name.lower()
        return "field_harmonics" in name or name.startswith("harmonics")

    def is_coil_mesh_target(self, path):
        name = Path(path).name.lower()
        return "coil_field_mesh" in name or name.startswith("coilmesh")

    def make_vtk_reader(self, path):
        suffix = path.suffix.lower()
        if suffix == ".vtu":
            reader = vtk.vtkXMLUnstructuredGridReader()
        elif suffix == ".vtp":
            reader = vtk.vtkXMLPolyDataReader()
        elif suffix == ".vtk":
            reader = vtk.vtkDataSetReader()
        elif suffix == ".vts":
            reader = vtk.vtkXMLStructuredGridReader()
        elif suffix == ".vti":
            reader = vtk.vtkXMLImageDataReader()
        elif suffix == ".vtm":
            reader = vtk.vtkXMLMultiBlockDataReader()
        elif suffix == ".stl":
            reader = vtk.vtkSTLReader()
        elif suffix == ".ply":
            reader = vtk.vtkPLYReader()
        elif suffix == ".obj":
            reader = vtk.vtkOBJReader()
        else:
            return None
        reader.SetFileName(str(path))
        reader.Update()
        return reader

    def extract_polydata(self, data_object):
        pipeline = []
        if isinstance(data_object, vtk.vtkMultiBlockDataSet):
            geometry = vtk.vtkCompositeDataGeometryFilter()
            geometry.SetInputDataObject(data_object)
            geometry.Update()
            polydata = geometry.GetOutput()
            pipeline.append(geometry)
            return polydata, pipeline
        if isinstance(data_object, vtk.vtkImageData):
            extent = data_object.GetExtent()
            geometry = vtk.vtkImageDataGeometryFilter()
            geometry.SetInputData(data_object)
            if data_object.GetDimensions()[2] > 1:
                mid_z = (extent[4] + extent[5]) // 2
                geometry.SetExtent(extent[0], extent[1], extent[2], extent[3], mid_z, mid_z)
            else:
                geometry.SetExtent(extent[0], extent[1], extent[2], extent[3], extent[4], extent[5])
            geometry.Update()
            polydata = geometry.GetOutput()
            pipeline.append(geometry)
            return polydata, pipeline
        if isinstance(data_object, vtk.vtkPolyData):
            return data_object, pipeline
        if isinstance(data_object, vtk.vtkDataSet):
            geometry = vtk.vtkGeometryFilter()
            geometry.SetInputData(data_object)
            geometry.Update()
            polydata = geometry.GetOutput()
            pipeline.append(geometry)
            return polydata, pipeline
        raise ValueError("当前文件不是可读取的 VTK 数据")

    def format_bounds(self, bounds):
        if not bounds:
            return "未知"
        return f"x[{bounds[0]:.3f}, {bounds[1]:.3f}] y[{bounds[2]:.3f}, {bounds[3]:.3f}] z[{bounds[4]:.3f}, {bounds[5]:.3f}]"

    def choose_preferred_array(self, data, preferred_tokens=None):
        if data is None or data.GetNumberOfArrays() <= 0:
            return None

        arrays = [data.GetArray(index) for index in range(data.GetNumberOfArrays())]
        arrays = [array for array in arrays if array is not None]
        if not arrays:
            return None

        preferred_tokens = preferred_tokens or (
            "current density",
            "flux density",
            "magnetic field",
            "vector potential",
            "magnetisation",
        )
        for token in preferred_tokens:
            for array in arrays:
                name = (array.GetName() or "").lower()
                if token in name:
                    return array
        return arrays[0]

    def create_lookup_table(self, scalar_range):
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(256)
        lut.SetRange(scalar_range)
        lut.SetHueRange(0.66, 0.0)
        lut.SetSaturationRange(1.0, 1.0)
        lut.SetValueRange(1.0, 1.0)
        lut.Build()
        return lut

    def format_scalar_bar_title(self, title):
        text = (title or "").strip()
        lowered = text.lower()
        if "flux density" in lowered or "magnetic flux density" in lowered:
            return "B [T]"
        if "current density" in lowered:
            return "J"
        if "current" in lowered:
            return "I"
        return text if len(text) <= 12 else text[:12]

    def _apply_scalar_bar_layout(self, scalar_bar):
        if scalar_bar is None:
            return
        scalar_bar.SetOrientationToVertical()
        scalar_bar.SetWidth(0.024)
        scalar_bar.SetHeight(0.52)
        if self.scalar_bar_position == "left":
            scalar_bar.SetPosition(0.035, 0.14)
        else:
            scalar_bar.SetPosition(0.905, 0.14)

    def create_scalar_bar(self, lookup_table, title):
        scalar_bar = vtk.vtkScalarBarActor()
        scalar_bar.SetLookupTable(lookup_table)
        scalar_bar.SetTitle(self.format_scalar_bar_title(title))
        scalar_bar.SetNumberOfLabels(4)
        scalar_bar.SetTextPad(6)
        scalar_bar.UnconstrainedFontSizeOn()
        self._apply_scalar_bar_layout(scalar_bar)

        label_prop = vtk.vtkTextProperty()
        label_prop.SetColor(0.96, 0.98, 1.0)
        label_prop.SetFontSize(20)
        label_prop.SetBold(True)
        label_prop.SetShadow(False)
        scalar_bar.SetLabelTextProperty(label_prop)

        title_prop = vtk.vtkTextProperty()
        title_prop.SetColor(0.96, 0.98, 1.0)
        title_prop.SetFontSize(20)
        title_prop.SetBold(True)
        title_prop.SetItalic(False)
        title_prop.SetShadow(False)
        scalar_bar.SetTitleTextProperty(title_prop)
        scalar_bar.SetVisibility(1 if self.show_scalar_bar_action.isChecked() else 0)
        return scalar_bar

    def build_surface_scene(self, path, data_object, polydata, pipeline, preferred_tokens=None):
        if polydata is None or polydata.GetNumberOfPoints() == 0:
            raise ValueError(f"{path.name} 中没有可用的标量数组")

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        mapper.ScalarVisibilityOff()
        pipeline.append(mapper)

        scalar_label = ""
        point_data = polydata.GetPointData() if polydata.GetPointData() else None
        cell_data = polydata.GetCellData() if polydata.GetCellData() else None
        array = self.choose_preferred_array(point_data, preferred_tokens)
        use_point_data = True
        if array is None:
            array = self.choose_preferred_array(cell_data, preferred_tokens)
            use_point_data = False

        if array is not None:
            if array.GetNumberOfComponents() == 1:
                if use_point_data and point_data is not None and point_data.GetArray(array.GetName()) is not None:
                    point_data.SetActiveScalars(array.GetName())
                    mapper.SetScalarModeToUsePointData()
                elif cell_data is not None and cell_data.GetArray(array.GetName()) is not None:
                    cell_data.SetActiveScalars(array.GetName())
                    mapper.SetScalarModeToUseCellData()
                mapper.ScalarVisibilityOn()
                mapper.SetScalarRange(array.GetRange())
                mapper.SetLookupTable(self.create_lookup_table(array.GetRange()))
                scalar_label = array.GetName() or "鏍囬噺"
            elif array.GetNumberOfComponents() in (2, 3) and use_point_data and point_data is not None:
                point_data.SetActiveVectors(array.GetName())
                vector_norm = vtk.vtkVectorNorm()
                vector_norm.SetInputData(polydata)
                vector_norm.Update()
                polydata = vector_norm.GetOutput()
                mapper.SetInputData(polydata)
                mapper.ScalarVisibilityOn()
                mapper.SetScalarModeToUsePointData()
                scalar_range = polydata.GetPointData().GetScalars().GetRange()
                mapper.SetScalarRange(scalar_range)
                mapper.SetLookupTable(self.create_lookup_table(scalar_range))
                scalar_label = (array.GetName() or "电流密度") + " 模长"
                pipeline.append(vector_norm)

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetInterpolationToPhong()
        actor.GetProperty().SetEdgeVisibility(1 if self.show_mesh_edges_action.isChecked() else 0)
        actor.GetProperty().SetEdgeColor(0.18, 0.18, 0.22)
        if isinstance(data_object, vtk.vtkImageData):
            actor.GetProperty().SetOpacity(0.34)
        elif scalar_label:
            actor.GetProperty().SetOpacity(0.94)
        else:
            actor.GetProperty().SetOpacity(0.90)
            actor.GetProperty().SetColor(0.78, 0.84, 0.93)

        outline = vtk.vtkOutlineFilter()
        outline.SetInputData(polydata)
        outline_mapper = vtk.vtkPolyDataMapper()
        outline_mapper.SetInputConnection(outline.GetOutputPort())
        outline_actor = vtk.vtkActor()
        outline_actor.SetMapper(outline_mapper)
        outline_actor.GetProperty().SetColor(0.94, 0.94, 0.98)
        outline_actor.GetProperty().SetLineWidth(1.2)
        outline_actor.SetVisibility(1 if self.show_outline_action.isChecked() else 0)
        pipeline.extend([actor, outline, outline_mapper, outline_actor])

        scalar_bar = self.create_scalar_bar(mapper.GetLookupTable(), scalar_label) if scalar_label else None
        if scalar_bar is not None:
            pipeline.append(scalar_bar)

        info = (
            f"{path.name} | 点数={polydata.GetNumberOfPoints():,} | 单元数={polydata.GetNumberOfCells():,} "
            f"| 鑼冨洿={self.format_bounds(polydata.GetBounds())}"
        )
        if scalar_label:
            info += f" | 鏍囬噺={scalar_label}"
        return actor, outline_actor, scalar_bar, info, pipeline, {}

    def build_volume_streamline_scene(self, path, image_data, pipeline):
        point_data = image_data.GetPointData() if image_data.GetPointData() else None
        vector_array = self.choose_preferred_array(point_data, ("flux density", "magnetic field", "vector potential"))
        if vector_array is None or vector_array.GetNumberOfComponents() < 3:
            raise ValueError(f"{path.name} 缺少可用的空间场矢量数据")

        point_data.SetActiveVectors(vector_array.GetName())
        bounds = image_data.GetBounds()
        span_x = max(bounds[1] - bounds[0], 1.0e-6)
        span_y = max(bounds[3] - bounds[2], 1.0e-6)
        span_z = max(bounds[5] - bounds[4], 1.0e-6)
        max_span = max(span_x, span_y, span_z)
        min_span = min(span_x, span_y, span_z)
        center = (
            (bounds[0] + bounds[1]) / 2.0,
            (bounds[2] + bounds[3]) / 2.0,
            (bounds[4] + bounds[5]) / 2.0,
        )

        seed = vtk.vtkPointSource()
        seed.SetCenter(*center)
        seed.SetRadius(max(min_span * 0.18, max_span * 0.06))
        seed.SetNumberOfPoints(240)

        integrator = vtk.vtkRungeKutta4()
        tracer = vtk.vtkStreamTracer()
        tracer.SetInputData(image_data)
        tracer.SetSourceConnection(seed.GetOutputPort())
        tracer.SetIntegrator(integrator)
        tracer.SetIntegrationDirectionToBoth()
        tracer.SetMaximumPropagation(max_span * 12.0)
        tracer.SetInitialIntegrationStep(max_span / 250.0)
        tracer.SetMinimumIntegrationStep(max_span / 4000.0)
        tracer.SetMaximumIntegrationStep(max_span / 30.0)
        tracer.SetTerminalSpeed(1.0e-8)

        vector_norm = vtk.vtkVectorNorm()
        vector_norm.SetInputConnection(tracer.GetOutputPort())

        tube = vtk.vtkTubeFilter()
        tube.SetInputConnection(vector_norm.GetOutputPort())
        tube.SetRadius(max(max_span * 0.0032, 3.0e-4))
        tube.SetNumberOfSides(14)
        tube.CappingOn()
        tube.Update()

        streamline_poly = tube.GetOutput()
        if streamline_poly is None or streamline_poly.GetNumberOfPoints() == 0:
            raise ValueError(f"{path.name} 中没有可显示的线圈标量数据")

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(tube.GetOutputPort())
        mapper.ScalarVisibilityOn()
        mapper.SetScalarModeToUsePointData()
        scalar_range = streamline_poly.GetPointData().GetScalars().GetRange()
        mapper.SetLookupTable(self.create_lookup_table(scalar_range))
        mapper.SetScalarRange(scalar_range)

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetOpacity(0.96)

        outline = vtk.vtkOutlineFilter()
        outline.SetInputData(image_data)
        outline_mapper = vtk.vtkPolyDataMapper()
        outline_mapper.SetInputConnection(outline.GetOutputPort())
        outline_actor = vtk.vtkActor()
        outline_actor.SetMapper(outline_mapper)
        outline_actor.GetProperty().SetColor(0.94, 0.94, 0.98)
        outline_actor.GetProperty().SetLineWidth(1.2)
        outline_actor.SetVisibility(1 if self.show_outline_action.isChecked() else 0)

        scalar_label = (vector_array.GetName() or "磁场") + " 模长"
        scalar_bar = self.create_scalar_bar(mapper.GetLookupTable(), scalar_label)
        pipeline.extend([seed, integrator, tracer, vector_norm, tube, mapper, actor, outline, outline_mapper, outline_actor, scalar_bar])

        dims = image_data.GetDimensions()
        info = (
            f"{path.name} | 流线条数={streamline_poly.GetNumberOfCells():,} | 切片尺寸={dims[0]}x{dims[1]}x{dims[2]} "
            f"| 鑼冨洿={self.format_bounds(bounds)} | 鏍囬噺={scalar_label}"
        )
        return actor, outline_actor, scalar_bar, info, pipeline, {}

    def build_coil_scene(self, layer_paths, mode="magnetic_flux_density"):
        if not layer_paths:
            raise ValueError("线圈文件中没有可用的点数据")

        palette = [
            (0.99, 0.74, 0.22),
            (0.22, 0.86, 0.98),
            (0.97, 0.45, 0.74),
            (0.59, 0.93, 0.36),
            (0.75, 0.63, 0.99),
        ]
        layer_datasets = []
        pipeline = []
        global_min = None
        global_max = None
        scene_title = "导体表面磁场"
        preferred_tokens = ("flux density", "magnetic field")
        use_scalars = True
        if mode == "current_density":
            scene_title = "线圈电流密度"
            preferred_tokens = ("current density",)
        elif mode == "mesh":
            scene_title = "线圈网格"
            preferred_tokens = ()
            use_scalars = False
        scalar_label = ""

        for path in layer_paths:
            reader = self.make_vtk_reader(path)
            if reader is None:
                continue
            data_object = reader.GetOutputDataObject(0)
            refs = [reader]
            polydata, geometry_pipeline = self.extract_polydata(data_object)
            refs.extend(geometry_pipeline)
            if polydata is None or polydata.GetNumberOfPoints() == 0:
                continue

            point_data = polydata.GetPointData() if polydata.GetPointData() else None
            array = self.choose_preferred_array(point_data, preferred_tokens) if use_scalars else None
            display_polydata = polydata
            if array is not None and array.GetNumberOfComponents() in (2, 3) and point_data is not None:
                point_data.SetActiveVectors(array.GetName())
                vector_norm = vtk.vtkVectorNorm()
                vector_norm.SetInputData(polydata)
                vector_norm.Update()
                display_polydata = vector_norm.GetOutput()
                refs.append(vector_norm)
                scalar_label = (array.GetName() or "Current Density") + " 模长"
            elif array is not None and array.GetNumberOfComponents() == 1 and point_data is not None:
                point_data.SetActiveScalars(array.GetName())
                scalar_label = array.GetName() or "Current Density"
            elif use_scalars:
                raise ValueError(f"{path.name} 缺少 {scene_title} 所需的标量或矢量数据")

            active_scalars = display_polydata.GetPointData().GetScalars() if use_scalars else None
            if active_scalars is not None:
                scalar_range = active_scalars.GetRange()
                global_min = scalar_range[0] if global_min is None else min(global_min, scalar_range[0])
                global_max = scalar_range[1] if global_max is None else max(global_max, scalar_range[1])

            layer_datasets.append((path, display_polydata, refs))

        if not layer_datasets:
            raise ValueError("当前没有可用于显示的线圈层数据")

        scalar_range = (global_min if global_min is not None else 0.0, global_max if global_max is not None else 1.0)
        lookup_table = self.create_lookup_table(scalar_range) if use_scalars else None
        actor_map = {}
        append_filter = vtk.vtkAppendPolyData()
        pipeline.append(append_filter)
        actors = []
        total_points = 0
        total_cells = 0

        for layer_index, (path, polydata, refs) in enumerate(layer_datasets):
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(polydata)
            if use_scalars:
                mapper.ScalarVisibilityOn()
                mapper.SetScalarModeToUsePointData()
                mapper.SetLookupTable(lookup_table)
                mapper.SetScalarRange(scalar_range)
                mapper.InterpolateScalarsBeforeMappingOn()
            else:
                mapper.ScalarVisibilityOff()

            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetOpacity(0.95 if use_scalars else 0.88)
            actor.GetProperty().SetAmbient(0.20 if use_scalars else 0.28)
            actor.GetProperty().SetDiffuse(0.80 if use_scalars else 0.72)
            actor.GetProperty().SetSpecular(0.18 if use_scalars else 0.12)
            actor.GetProperty().SetSpecularPower(12.0)
            actor.GetProperty().SetInterpolationToPhong()
            actor.GetProperty().SetEdgeVisibility(1 if self.show_mesh_edges_action.isChecked() else 0)
            actor.GetProperty().SetEdgeColor(0.10, 0.10, 0.14)
            if not use_scalars:
                actor.GetProperty().SetColor(*palette[layer_index % len(palette)])

            actor_map[str(path)] = actor
            actors.append(actor)
            append_filter.AddInputData(polydata)
            total_points += polydata.GetNumberOfPoints()
            total_cells += polydata.GetNumberOfCells()
            pipeline.extend(refs)
            pipeline.extend([mapper, actor])

        append_filter.Update()
        clean_filter = vtk.vtkCleanPolyData()
        clean_filter.SetInputConnection(append_filter.GetOutputPort())
        clean_filter.Update()

        outline = vtk.vtkOutlineFilter()
        outline.SetInputConnection(clean_filter.GetOutputPort())
        outline_mapper = vtk.vtkPolyDataMapper()
        outline_mapper.SetInputConnection(outline.GetOutputPort())
        outline_actor = vtk.vtkActor()
        outline_actor.SetMapper(outline_mapper)
        outline_actor.GetProperty().SetColor(0.94, 0.94, 0.98)
        outline_actor.GetProperty().SetLineWidth(1.2)
        outline_actor.SetVisibility(1 if self.show_outline_action.isChecked() else 0)

        scalar_bar = self.create_scalar_bar(lookup_table, scalar_label) if use_scalars else None
        pipeline.extend([clean_filter, outline, outline_mapper, outline_actor])
        if scalar_bar is not None:
            pipeline.append(scalar_bar)

        bounds = clean_filter.GetOutput().GetBounds()
        info = (
            f"{scene_title} | 线圈层数={len(layer_datasets)} | 总点数={total_points:,} | 总单元数={total_cells:,} "
            f"| 范围={self.format_bounds(bounds)}"
        )
        if scalar_label:
            info += f" | 标量={scalar_label}"
        return actors[0], outline_actor, scalar_bar, info, pipeline, actor_map

    def build_vtk_scene(self, path):
        reader = self.make_vtk_reader(path)
        if reader is None:
            raise ValueError(f"不支持的三维格式：{path.suffix}")

        data_object = reader.GetOutputDataObject(0)
        pipeline = [reader]
        polydata, geometry_pipeline = self.extract_polydata(data_object)
        pipeline.extend(geometry_pipeline)
        return self.build_surface_scene(path, data_object, polydata, pipeline)

    def build_overlay_actor(self, path, layer_index):
        palette = [
            (0.99, 0.74, 0.22),
            (0.22, 0.86, 0.98),
            (0.97, 0.45, 0.74),
            (0.59, 0.93, 0.36),
            (0.75, 0.63, 0.99),
        ]
        reader = self.make_vtk_reader(path)
        if reader is None:
            raise ValueError(f"不支持的叠加网格格式：{path.suffix}")

        data_object = reader.GetOutputDataObject(0)
        pipeline = [reader]
        polydata, geometry_pipeline = self.extract_polydata(data_object)
        pipeline.extend(geometry_pipeline)
        if polydata is None or polydata.GetNumberOfPoints() == 0:
            raise ValueError(f"{path.name} 中没有可叠加显示的网格")

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        mapper.ScalarVisibilityOff()

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*palette[layer_index % len(palette)])
        actor.GetProperty().SetOpacity(0.28)
        actor.GetProperty().SetAmbient(0.34)
        actor.GetProperty().SetDiffuse(0.72)
        actor.GetProperty().SetSpecular(0.28)
        actor.GetProperty().SetSpecularPower(16.0)
        actor.GetProperty().SetInterpolationToPhong()
        actor.GetProperty().SetEdgeVisibility(1 if self.show_mesh_edges_action.isChecked() else 0)
        actor.GetProperty().SetEdgeColor(0.08, 0.08, 0.12)
        actor.SetVisibility(1 if self.show_coil_overlay_action.isChecked() else 0)
        pipeline.extend([mapper, actor])
        return actor, pipeline, polydata

    def clear_visualization(self, title, detail):
        self.current_visual_path = None
        self.current_pipeline = []
        self.current_actor = None
        self.current_outline_actor = None
        self.current_scalar_bar = None
        self.current_coil_layer_actors = {}
        self.current_coil_layer_paths = []
        self.viewer_mesh_label.setText(title)
        self.viewer_info_label.setText(detail)
        self.vtk_renderer.RemoveAllViewProps()
        self.vtk_widget.GetRenderWindow().Render()

    def load_visualization(self, path, quiet=False):
        target = self.resolve_visualization_target(path)
        if target is None:
            if not quiet:
                self.show_warning("缺少可视化文件", "当前输出中没有可加载的 VTK 结果。")
            return False

        layer_paths = self.current_coil_layer_paths or self.find_coil_layer_paths()
        try:
            if self.is_coil_mesh_target(target) and layer_paths:
                actor, outline_actor, scalar_bar, info, pipeline, layer_actor_map = self.build_coil_scene(
                    layer_paths,
                    mode=self.current_coil_visual_mode,
                )
            else:
                actor, outline_actor, scalar_bar, info, pipeline, layer_actor_map = self.build_vtk_scene(target)
        except Exception as exc:  # noqa: BLE001
            self.clear_visualization("网格加载失败", str(exc))
            if not quiet:
                self.show_error("可视化加载失败", str(exc))
            return False

        self.vtk_renderer.RemoveAllViewProps()
        overlay_pipeline = []
        overlay_note = ""
        overlay_point_total = 0

        if self.is_coil_mesh_target(target) and layer_actor_map:
            for layer_actor in layer_actor_map.values():
                self.vtk_renderer.AddActor(layer_actor)
            overlay_note = f" | 线圈层数={len(layer_actor_map)}"
        else:
            self.vtk_renderer.AddActor(actor)
            if self.is_field_result_target(target):
                for layer_index, layer_path in enumerate(layer_paths):
                    if layer_path == target:
                        continue
                    try:
                        overlay_actor, overlay_refs, overlay_polydata = self.build_overlay_actor(layer_path, layer_index)
                    except Exception:
                        continue
                    self.vtk_renderer.AddActor(overlay_actor)
                    layer_actor_map[str(layer_path)] = overlay_actor
                    overlay_pipeline.extend(overlay_refs)
                    overlay_point_total += overlay_polydata.GetNumberOfPoints()
            if self.is_harmonics_target(target):
                overlay_note += " | 当前结果是谐波采样面，不代表真实线圈几何"

        self.vtk_renderer.AddActor(outline_actor)
        if scalar_bar is not None:
            self.vtk_renderer.AddViewProp(scalar_bar)

        self.current_pipeline = pipeline + overlay_pipeline
        self.current_actor = actor
        self.current_outline_actor = outline_actor
        self.current_scalar_bar = scalar_bar
        self.current_visual_path = target
        self.current_coil_layer_actors = layer_actor_map
        self.current_coil_layer_paths = layer_paths

        if self.is_field_result_target(target) and layer_actor_map:
            overlay_note = (
                f" | 叠加线圈层数={len(layer_actor_map)} | 线圈总点数={overlay_point_total:,}"
                f" | 可在左侧模型树中按层显示或隐藏"
            )

        self.viewer_mesh_label.setText(target.name)
        self.viewer_info_label.setText(info + overlay_note)
        self.update_view_preferences()
        self.apply_camera_preset("iso")
        return True

    def load_selected_visualization(self):
        path = self.selected_output_path()
        if path is None:
            self.show_warning("未选中文件", "请先从输出列表选择一个文件。")
            return
        self.load_visualization(path, quiet=False)

    def load_default_visualization(self, quiet=False):
        target = self.find_default_visualization_path()
        if target is None:
            if not quiet:
                self.show_warning("无可显示结果", "当前输出目录里还没有可加载的 VTK 可视化文件。")
            return False
        return self.load_visualization(target, quiet=quiet)

    def reset_camera(self):
        self.vtk_renderer.ResetCamera()
        self.vtk_renderer.ResetCameraClippingRange()
        self.vtk_widget.GetRenderWindow().Render()

    def apply_camera_preset(self, preset):
        if self.current_visual_path is None:
            return
        bounds = self.vtk_renderer.ComputeVisiblePropBounds()
        if not bounds or bounds[0] > bounds[1]:
            return

        center = (
            (bounds[0] + bounds[1]) / 2.0,
            (bounds[2] + bounds[3]) / 2.0,
            (bounds[4] + bounds[5]) / 2.0,
        )
        span = max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4], 1.0)
        distance = span * 2.5
        camera = self.vtk_renderer.GetActiveCamera()

        if preset == "front":
            position = (center[0], center[1] - distance, center[2])
            view_up = (0.0, 0.0, 1.0)
        elif preset == "side":
            position = (center[0] + distance, center[1], center[2])
            view_up = (0.0, 0.0, 1.0)
        elif preset == "top":
            position = (center[0], center[1], center[2] + distance)
            view_up = (0.0, 1.0, 0.0)
        else:
            position = (center[0] + distance, center[1] - distance, center[2] + distance)
            view_up = (0.0, 0.0, 1.0)

        camera.SetFocalPoint(*center)
        camera.SetPosition(*position)
        camera.SetViewUp(*view_up)
        self.vtk_renderer.ResetCameraClippingRange()
        self.vtk_widget.GetRenderWindow().Render()

    def closeEvent(self, event):
        try:
            if self.orientation_widget is not None:
                self.orientation_widget.SetEnabled(0)
        except Exception:
            pass
        super().closeEvent(event)


def main():
    parser = argparse.ArgumentParser(description="Project RAT Qt 图形界面")
    parser.add_argument("--check", action="store_true", help="仅输出当前环境与工作区状态")
    args = parser.parse_args()

    if args.check:
        print(format_status_report(collect_status()))
        return 0

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationDisplayName("Project RAT")
    window = ProjectRatWindow()
    window.show()
    exit_after_ms = os.environ.get("PROJECT_RAT_QT_EXIT_AFTER_MS", "").strip()
    if exit_after_ms:
        try:
            delay = max(0, int(exit_after_ms))
        except ValueError:
            delay = 0
        QTimer.singleShot(delay, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

