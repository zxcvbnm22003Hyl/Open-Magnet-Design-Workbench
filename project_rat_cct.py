import json
import re
import sys
from pathlib import Path


def get_runtime_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


WORKSPACE_ROOT = get_runtime_root()
CCT_WORKBENCH_ROOT = WORKSPACE_ROOT / "cct-workbench"
RAT_MODELS_INCLUDE = (WORKSPACE_ROOT / "rat-models" / "include").resolve().as_posix()


CCT_PROFILES = {
    "mini_cct": {
        "label": "默认 CCT（单谐波）",
        "summary": "支持直线 CCT 的多层线圈建模。基础参数作为默认值使用，层数增加后可用“每层列表”分别覆盖各层匝数、匝间距、倾角和电流。",
        "project_name": "mini_cct_study",
        "source_name": "mini_cct_gui.cpp",
        "executable_name": "mini_cct_gui",
        "fields": [
            {"key": "num_poles", "label": "谐波阶数", "type": "int", "default": 1},
            {"key": "num_layers", "label": "层数", "type": "int", "default": 2},
            {"key": "num_turns", "label": "默认每层匝数", "type": "int", "default": 10},
            {"key": "layer_turns_csv", "label": "每层匝数列表", "type": "text", "default": "", "placeholder": "例如: 10, 10, 12, 12"},
            {"key": "radius", "label": "孔径半径 [m]", "type": "float", "default": 0.025},
            {"key": "layer_radius_csv", "label": "每层中心半径列表 [m]", "type": "text", "default": "", "placeholder": "留空时按骨架厚度与层间距自动推算"},
            {"key": "delta", "label": "默认匝间距 [m]", "type": "float", "default": 0.0005},
            {"key": "layer_delta_csv", "label": "每层匝间距列表 [m]", "type": "text", "default": "", "placeholder": "留空时使用默认匝间距"},
            {"key": "alpha_deg", "label": "默认倾角 [deg]", "type": "float", "default": 30.0},
            {"key": "layer_alpha_deg_csv", "label": "每层倾角列表 [deg]", "type": "text", "default": "", "placeholder": "例如: 30, 30, 28, 28"},
            {"key": "frame_twist_deg", "label": "附加截面扭转 [deg]", "type": "float", "default": 0.0},
            {"key": "layer_frame_twist_deg_csv", "label": "每层附加截面扭转列表 [deg]", "type": "text", "default": "", "placeholder": "留空时使用统一扭转"},
            {"key": "dformer", "label": "骨架厚度 [m]", "type": "float", "default": 0.002},
            {"key": "dradial", "label": "层间距 [m]", "type": "float", "default": 0.0003},
            {"key": "num_nodes_per_turn", "label": "每匝路径节点数", "type": "int", "default": 180},
            {"key": "element_size", "label": "单元尺寸 [m]", "type": "float", "default": 0.002},
            {"key": "operating_current", "label": "默认运行电流 [A]", "type": "float", "default": 400.0},
            {"key": "layer_current_csv", "label": "每层电流列表 [A]", "type": "text", "default": "", "placeholder": "留空时使用默认运行电流"},
            {"key": "operating_temperature", "label": "运行温度 [K]", "type": "float", "default": 4.5},
            {"key": "nd", "label": "电缆厚向股数", "type": "int", "default": 2},
            {"key": "nw", "label": "电缆宽向股数", "type": "int", "default": 5},
            {"key": "dstr", "label": "裸线直径 [m]", "type": "float", "default": 0.000825},
            {"key": "ddstr", "label": "含绝缘线径 [m]", "type": "float", "default": 0.001},
            {"key": "fcu2sc", "label": "铜超比", "type": "float", "default": 1.9},
        ],
    },
    "custom_cct": {
        "label": "自定义 CCT（组合功能）",
        "summary": "支持二极与四极叠加、弯转半径、层数与节距设定，并可用“每层列表”分别覆盖各层半径、节距、谐波与电流。可选 Frenet-Serret 坐标系来定义截面取向。",
        "project_name": "custom_cct_study",
        "source_name": "custom_cct_gui.cpp",
        "executable_name": "custom_cct_gui",
        "fields": [
            {"key": "num_turns", "label": "总匝数", "type": "float", "default": 40.0},
            {"key": "layer_turns_csv", "label": "每层总匝数列表", "type": "text", "default": "", "placeholder": "留空时各层沿用总匝数"},
            {"key": "radius", "label": "内半径 [m]", "type": "float", "default": 0.025},
            {"key": "layer_radius_csv", "label": "每层中心半径列表 [m]", "type": "text", "default": "", "placeholder": "留空时按内半径与层间增量自动推算"},
            {"key": "dradius", "label": "层间半径增量 [m]", "type": "float", "default": 0.007},
            {"key": "omega", "label": "节距 [m]", "type": "float", "default": 0.006},
            {"key": "layer_omega_csv", "label": "每层节距列表 [m]", "type": "text", "default": "", "placeholder": "留空时各层沿用统一节距"},
            {"key": "frame_twist_deg", "label": "附加截面扭转 [deg]", "type": "float", "default": 0.0},
            {"key": "layer_frame_twist_deg_csv", "label": "每层附加截面扭转列表 [deg]", "type": "text", "default": "", "placeholder": "留空时各层沿用统一扭转"},
            {"key": "use_frenet_serret", "label": "使用 Frenet-Serret 坐标系", "type": "bool", "default": False},
            {"key": "use_binormal", "label": "使用副法线作为横向方向", "type": "bool", "default": False},
            {"key": "num_layers", "label": "层数", "type": "int", "default": 2},
            {"key": "num_nodes_per_turn", "label": "每匝路径节点数", "type": "int", "default": 120},
            {"key": "num_sect_per_turn", "label": "每匝截面分段数", "type": "int", "default": 8},
            {"key": "dipole_amplitude", "label": "二极振幅 [m]", "type": "float", "default": 0.03},
            {"key": "layer_dipole_csv", "label": "每层二极振幅列表 [m]", "type": "text", "default": "", "placeholder": "留空时各层沿用统一二极振幅"},
            {"key": "quadrupole_amplitude", "label": "四极振幅 [m]", "type": "float", "default": 0.007},
            {"key": "layer_quadrupole_csv", "label": "每层四极振幅列表 [m]", "type": "text", "default": "", "placeholder": "留空时各层沿用统一四极振幅"},
            {"key": "quadrupole_offset", "label": "四极偏置 [m]", "type": "float", "default": 0.0022},
            {"key": "layer_quadrupole_offset_csv", "label": "每层四极偏置列表 [m]", "type": "text", "default": "", "placeholder": "留空时各层沿用统一四极偏置"},
            {"key": "bend_radius", "label": "弯转半径 [m]，0 为直线", "type": "float", "default": 0.15},
            {"key": "element_size", "label": "单元尺寸 [m]", "type": "float", "default": 0.002},
            {"key": "operating_current", "label": "运行电流 [A]", "type": "float", "default": 480.0},
            {"key": "layer_current_csv", "label": "每层电流列表 [A]", "type": "text", "default": "", "placeholder": "留空时各层沿用统一电流"},
            {"key": "operating_temperature", "label": "运行温度 [K]", "type": "float", "default": 4.5},
            {"key": "nd", "label": "电缆厚向股数", "type": "int", "default": 2},
            {"key": "nw", "label": "电缆宽向股数", "type": "int", "default": 5},
            {"key": "dstr", "label": "裸线直径 [m]", "type": "float", "default": 0.000825},
            {"key": "ddstr", "label": "含绝缘线径 [m]", "type": "float", "default": 0.001},
            {"key": "fcu2sc", "label": "铜超比", "type": "float", "default": 1.9},
        ],
    },
    "cos_theta": {
        "label": "Cosine-Theta 线圈",
        "summary": "基于 RAT 的 PathCosTheta / CosThetaBlock 生成 cosine-theta 双层块线圈，并按极阶自动复制成完整多极磁体，可直接输出导体表面磁场、二维切片和谐波采样结果。",
        "project_name": "cos_theta_study",
        "source_name": "cos_theta_gui.cpp",
        "executable_name": "cos_theta_gui",
        "fields": [
            {"key": "num_poles", "label": "极数", "type": "int", "default": 1},
            {"key": "num_layers", "label": "层数", "type": "int", "default": 2},
            {"key": "element_size", "label": "单元尺寸 [m]", "type": "float", "default": 0.002},
            {"key": "cross_num_thickness", "label": "截面厚向分段数", "type": "int", "default": 4},
            {"key": "cross_num_width", "label": "截面宽向分段数", "type": "int", "default": 24},
            {"key": "operating_current", "label": "默认运行电流 [A]", "type": "float", "default": 8000.0},
            {"key": "layer_current_csv", "label": "每层电流列表 [A]", "type": "text", "default": "8000, 8000", "placeholder": "例如: 8000, 8000"},
            {"key": "operating_temperature", "label": "运行温度 [K]", "type": "float", "default": 1.9},
            {"key": "layer_radius_csv", "label": "每层中心半径列表 [m]", "type": "text", "default": "0.028, 0.044", "placeholder": "例如: 0.028, 0.044"},
            {"key": "layer_dinner_csv", "label": "每层内厚列表 [m]", "type": "text", "default": "0.001736, 0.001362", "placeholder": "例如: 0.001736, 0.001362"},
            {"key": "layer_douter_csv", "label": "每层外厚列表 [m]", "type": "text", "default": "0.002064, 0.001598", "placeholder": "例如: 0.002064, 0.001598"},
            {"key": "layer_wcable_csv", "label": "每层线圈宽度列表 [m]", "type": "text", "default": "0.0151, 0.0151", "placeholder": "例如: 0.0151, 0.0151"},
            {"key": "layer_dinsu_csv", "label": "每层绝缘偏移列表 [m]", "type": "text", "default": "0.000115, 0.0001", "placeholder": "例如: 0.000115, 0.0001"},
            {"key": "layer_reflect_yz_csv", "label": "每层 YZ 镜像列表", "type": "text", "default": "0, 1", "placeholder": "0=否, 1=是"},
            {"key": "layer_reverse_csv", "label": "每层反向绕制列表", "type": "text", "default": "0, 1", "placeholder": "0=否, 1=是"},
            {
                "key": "layer1_blocks",
                "label": "第 1 层块定义",
                "type": "multiline",
                "default": "5, 0, 0, 0.26, 50\n5, 22, 25, 0.24, 60\n3, 48, 48, 0.22, 70\n2, 67, 68, 0.20, 80",
                "placeholder": "每行: cables, phi_deg, alpha_deg, zend_m, beta_deg",
            },
            {
                "key": "layer2_blocks",
                "label": "第 2 层块定义",
                "type": "multiline",
                "default": "9, 0, 0, 0.25, 50\n16, 22, 25, 0.20, 60",
                "placeholder": "每行: cables, phi_deg, alpha_deg, zend_m, beta_deg",
            },
        ],
    },
}


WRAPPER_PROFILE_IDS = {
    "solenoid",
    "racetrack",
    "rectangle",
    "trapezoid",
    "dshape",
    "flared",
    "clover",
    "plasma_ring",
}


CCT_PROFILES.update(
    {
        "solenoid": {
            "kind": "wrapper",
            "label": "标准螺线管",
            "summary": "基于 RAT 官方 ModelSolenoid wrapper，适合快速生成轴对称螺线管并查看导体磁场与二维场切片。",
            "note": "该类型直接调用 RAT 内置 ModelSolenoid。几何不是手写路径，而是官方 wrapper 自动生成。",
            "project_name": "solenoid_study",
            "source_name": "solenoid_gui.cpp",
            "executable_name": "solenoid_gui",
            "expected_outputs": ["coil_field_mesh*.vtu", "space_field_slice*.vti"],
            "fields": [
                {"key": "inner_radius", "label": "内半径 [m]", "type": "float", "default": 0.04},
                {"key": "dcoil", "label": "线圈厚度 [m]", "type": "float", "default": 0.01},
                {"key": "height", "label": "线圈高度 [m]", "type": "float", "default": 0.012},
                {"key": "num_sections", "label": "分段数", "type": "int", "default": 4},
                {"key": "element_size", "label": "单元尺寸 [m]", "type": "float", "default": 0.001},
                {"key": "num_turns", "label": "匝数", "type": "int", "default": 100},
                {"key": "operating_current", "label": "运行电流 [A]", "type": "float", "default": 200.0},
                {"key": "operating_temperature", "label": "运行温度 [K]", "type": "float", "default": 4.5},
            ],
        },
        "racetrack": {
            "kind": "wrapper",
            "label": "Racetrack 线圈",
            "summary": "基于 RAT 官方 ModelRacetrack wrapper，适合快速生成直边加圆弧端部的 racetrack 线圈。",
            "note": "该类型直接调用 ModelRacetrack。参数对应官方 wrapper 的圆弧半径、直段长度和线圈包尺寸。",
            "project_name": "racetrack_study",
            "source_name": "racetrack_gui.cpp",
            "executable_name": "racetrack_gui",
            "expected_outputs": ["coil_field_mesh*.vtu", "space_field_slice*.vti"],
            "fields": [
                {"key": "arc_radius", "label": "圆弧半径 [m]", "type": "float", "default": 0.04},
                {"key": "length", "label": "直段长度 [m]", "type": "float", "default": 0.1},
                {"key": "coil_thickness", "label": "线圈厚度 [m]", "type": "float", "default": 0.0012},
                {"key": "coil_width", "label": "线圈宽度 [m]", "type": "float", "default": 0.012},
                {"key": "element_size", "label": "单元尺寸 [m]", "type": "float", "default": 0.002},
                {"key": "num_turns", "label": "匝数", "type": "int", "default": 10},
                {"key": "operating_current", "label": "运行电流 [A]", "type": "float", "default": 200.0},
                {"key": "operating_temperature", "label": "运行温度 [K]", "type": "float", "default": 4.5},
            ],
        },
        "rectangle": {
            "kind": "wrapper",
            "label": "矩形线圈",
            "summary": "基于 RAT 官方 ModelRectangle wrapper，适合快速生成圆角矩形磁体线圈。",
            "note": "该类型使用 ModelRectangle，主要参数是圆角、长边、短边和线圈包尺寸。",
            "project_name": "rectangle_study",
            "source_name": "rectangle_gui.cpp",
            "executable_name": "rectangle_gui",
            "expected_outputs": ["coil_field_mesh*.vtu", "space_field_slice*.vti"],
            "fields": [
                {"key": "arc_radius", "label": "圆角半径 [m]", "type": "float", "default": 0.02},
                {"key": "length", "label": "长度 [m]", "type": "float", "default": 0.25},
                {"key": "width", "label": "宽度 [m]", "type": "float", "default": 0.1},
                {"key": "coil_thickness", "label": "线圈厚度 [m]", "type": "float", "default": 0.01},
                {"key": "coil_width", "label": "线圈宽度 [m]", "type": "float", "default": 0.01},
                {"key": "element_size", "label": "单元尺寸 [m]", "type": "float", "default": 0.002},
                {"key": "num_turns", "label": "匝数", "type": "int", "default": 20},
                {"key": "operating_current", "label": "运行电流 [A]", "type": "float", "default": 400.0},
                {"key": "operating_temperature", "label": "运行温度 [K]", "type": "float", "default": 4.5},
            ],
        },
        "trapezoid": {
            "kind": "wrapper",
            "label": "梯形线圈",
            "summary": "基于 RAT 官方 ModelTrapezoid wrapper，适合快速生成梯形窗口磁体线圈。",
            "note": "该类型使用 ModelTrapezoid，主要参数是两段长度、宽度和圆角半径。",
            "project_name": "trapezoid_study",
            "source_name": "trapezoid_gui.cpp",
            "executable_name": "trapezoid_gui",
            "expected_outputs": ["coil_field_mesh*.vtu", "space_field_slice*.vti"],
            "fields": [
                {"key": "arc_radius", "label": "圆角半径 [m]", "type": "float", "default": 0.005},
                {"key": "length_1", "label": "长边 [m]", "type": "float", "default": 0.3},
                {"key": "length_2", "label": "短边 [m]", "type": "float", "default": 0.2},
                {"key": "width", "label": "宽度 [m]", "type": "float", "default": 0.1},
                {"key": "coil_thickness", "label": "线圈厚度 [m]", "type": "float", "default": 0.01},
                {"key": "coil_width", "label": "线圈宽度 [m]", "type": "float", "default": 0.01},
                {"key": "element_size", "label": "单元尺寸 [m]", "type": "float", "default": 0.002},
                {"key": "num_turns", "label": "匝数", "type": "int", "default": 20},
                {"key": "operating_current", "label": "运行电流 [A]", "type": "float", "default": 400.0},
                {"key": "operating_temperature", "label": "运行温度 [K]", "type": "float", "default": 4.5},
            ],
        },
        "dshape": {
            "kind": "wrapper",
            "label": "D 形线圈",
            "summary": "基于 RAT 官方 ModelDShape wrapper，适合快速生成 D 形磁体线圈。",
            "note": "该类型使用 ModelDShape，参数对应 D 形线圈的高度、宽度以及线圈包尺寸。",
            "project_name": "dshape_study",
            "source_name": "dshape_gui.cpp",
            "executable_name": "dshape_gui",
            "expected_outputs": ["coil_field_mesh*.vtu", "space_field_slice*.vti"],
            "fields": [
                {"key": "ell1", "label": "D 形高度 [m]", "type": "float", "default": 0.3},
                {"key": "ell2", "label": "D 形宽度 [m]", "type": "float", "default": 0.2},
                {"key": "coil_thickness", "label": "线圈厚度 [m]", "type": "float", "default": 0.02},
                {"key": "coil_width", "label": "线圈宽度 [m]", "type": "float", "default": 0.012},
                {"key": "element_size", "label": "单元尺寸 [m]", "type": "float", "default": 0.002},
                {"key": "num_turns", "label": "匝数", "type": "int", "default": 20},
                {"key": "operating_current", "label": "运行电流 [A]", "type": "float", "default": 400.0},
                {"key": "operating_temperature", "label": "运行温度 [K]", "type": "float", "default": 4.5},
            ],
        },
        "flared": {
            "kind": "wrapper",
            "label": "Flared 端部线圈",
            "summary": "基于 RAT 官方 ModelFlared wrapper，适合快速生成带外张端部的 block/racetrack 风格线圈。",
            "note": "该类型使用 ModelFlared。弯曲角使用角度输入，内部会转换成 RAT 需要的弧度值。",
            "project_name": "flared_study",
            "source_name": "flared_gui.cpp",
            "executable_name": "flared_gui",
            "expected_outputs": ["coil_field_mesh*.vtu", "space_field_slice*.vti"],
            "fields": [
                {"key": "ell1", "label": "直段长度 [m]", "type": "float", "default": 0.1},
                {"key": "ell2", "label": "斜段长度 [m]", "type": "float", "default": 0.15},
                {"key": "arcl_deg", "label": "端部弯曲角 [deg]", "type": "float", "default": -15.0},
                {"key": "radius1", "label": "硬弯半径 [m]", "type": "float", "default": 0.2},
                {"key": "radius2", "label": "软弯半径 [m]", "type": "float", "default": 0.05},
                {"key": "coil_thickness", "label": "线圈厚度 [m]", "type": "float", "default": 0.0012},
                {"key": "coil_width", "label": "线圈宽度 [m]", "type": "float", "default": 0.012},
                {"key": "element_size", "label": "单元尺寸 [m]", "type": "float", "default": 0.002},
                {"key": "num_turns", "label": "匝数", "type": "int", "default": 12},
                {"key": "operating_current", "label": "运行电流 [A]", "type": "float", "default": 4000.0},
                {"key": "operating_temperature", "label": "运行温度 [K]", "type": "float", "default": 4.5},
            ],
        },
        "clover": {
            "kind": "wrapper",
            "label": "Cloverleaf 线圈",
            "summary": "基于 RAT 官方 ModelClover wrapper，适合快速生成 cloverleaf 端部与桥接几何，并可按中平面镜像生成上下对称双线圈。",
            "note": "该类型使用 ModelClover。参数直接对应 RAT 的 cloverleaf wrapper，包括桥高、过渡段和桥接角；启用中平面镜像后会自动生成关于 z=0 中平面对称的第二个线圈。",
            "project_name": "clover_study",
            "source_name": "clover_gui.cpp",
            "executable_name": "clover_gui",
            "expected_outputs": ["coil_field_mesh*.vtu", "space_field_slice*.vti"],
            "fields": [
                {"key": "ellstr1", "label": "主直段长度 [m]", "type": "float", "default": 0.164},
                {"key": "ellstr2", "label": "副直段长度 [m]", "type": "float", "default": 0.084},
                {"key": "height", "label": "桥高 [m]", "type": "float", "default": 0.02},
                {"key": "dpack", "label": "线圈包厚度 [m]", "type": "float", "default": 0.008},
                {"key": "ell_trans", "label": "过渡段长度 [m]", "type": "float", "default": 0.0},
                {"key": "str12", "label": "控制强度 1-2 [m]", "type": "float", "default": 0.01295},
                {"key": "str34", "label": "控制强度 3-4 [m]", "type": "float", "default": 0.00518},
                {"key": "bending_radius", "label": "弯转半径 [m]", "type": "float", "default": 0.0},
                {"key": "bridge_angle_deg", "label": "桥接角 [deg]", "type": "float", "default": 14.0},
                {"key": "planar_winding", "label": "平面绕制 (0/1)", "type": "int", "default": 1},
                {"key": "mirror_midplane", "label": "启用中平面镜像", "type": "bool", "default": True},
                {"key": "midplane_offset", "label": "中平面半间隔 [m]", "type": "float", "default": 0.008},
                {"key": "coil_thickness", "label": "线圈厚度 [m]", "type": "float", "default": 0.012},
                {"key": "coil_width", "label": "线圈宽度 [m]", "type": "float", "default": 0.012},
                {"key": "element_size", "label": "单元尺寸 [m]", "type": "float", "default": 0.004},
                {"key": "num_turns", "label": "匝数", "type": "int", "default": 40},
                {"key": "operating_current", "label": "运行电流 [A]", "type": "float", "default": 2000.0},
                {"key": "operating_temperature", "label": "运行温度 [K]", "type": "float", "default": 20.0},
            ],
        },
        "plasma_ring": {
            "kind": "wrapper",
            "label": "Plasma Ring 线圈",
            "summary": "基于 RAT 官方 ModelPlasma wrapper，适合快速生成托卡马克风格等离子体环形线圈截面。",
            "note": "该类型使用 ModelPlasma。截面由等离子体参数 r0/a/delta/kappa 自动生成，不需要手写截面网格。",
            "project_name": "plasma_ring_study",
            "source_name": "plasma_ring_gui.cpp",
            "executable_name": "plasma_ring_gui",
            "expected_outputs": ["coil_field_mesh*.vtu", "space_field_slice*.vti"],
            "fields": [
                {"key": "r0", "label": "主半径 r0 [m]", "type": "float", "default": 0.2},
                {"key": "a", "label": "次半径 a [m]", "type": "float", "default": 0.15},
                {"key": "delta", "label": "三角度 delta", "type": "float", "default": 0.4},
                {"key": "kappa", "label": "伸长率 kappa", "type": "float", "default": 1.9},
                {"key": "num_sections", "label": "环向分段数", "type": "int", "default": 8},
                {"key": "element_size", "label": "单元尺寸 [m]", "type": "float", "default": 0.02},
                {"key": "num_turns", "label": "匝数", "type": "int", "default": 40},
                {"key": "operating_current", "label": "运行电流 [A]", "type": "float", "default": 500000.0},
                {"key": "operating_temperature", "label": "运行温度 [K]", "type": "float", "default": 4.5},
            ],
        },
    }
)


def sanitize_project_name(name):
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "cct_project"


def get_cct_profiles():
    return CCT_PROFILES


def get_profile_defaults(profile_id):
    profile = CCT_PROFILES[profile_id]
    return {field["key"]: field["default"] for field in profile["fields"]}


def parse_series_values(raw_value, caster):
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        tokens = [token.strip() for token in re.split(r"[,\s;]+", raw_value) if token.strip()]
    elif isinstance(raw_value, (list, tuple)):
        tokens = list(raw_value)
    else:
        tokens = [raw_value]
    return [caster(token) for token in tokens]


def normalize_series(raw_value, count, default_value, caster):
    values = parse_series_values(raw_value, caster)
    if not values:
        values = [caster(default_value)]
    if len(values) < count:
        values.extend([values[-1]] * (count - len(values)))
    return values[:count]


def parse_bool_token(value):
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Unsupported boolean token: {value}")


def normalize_bool_series(raw_value, count, default_value):
    values = parse_series_values(raw_value, parse_bool_token)
    if not values:
        values = [bool(default_value)]
    if len(values) < count:
        values.extend([values[-1]] * (count - len(values)))
    return values[:count]


def parse_cos_theta_blocks(raw_value):
    lines = [line.strip() for line in re.split(r"[;\r\n]+", str(raw_value or "")) if line.strip()]
    blocks = []
    for line in lines:
        tokens = [token.strip() for token in re.split(r"[,\s]+", line) if token.strip()]
        if len(tokens) < 5:
            raise ValueError("Cosine-theta 块定义格式错误。每行必须是: cables, phi_deg, alpha_deg, zend_m, beta_deg")
        blocks.append(
            {
                "num_cables": max(1, int(float(tokens[0]))),
                "phi_deg": float(tokens[1]),
                "alpha_deg": float(tokens[2]),
                "zend": max(1.0e-6, float(tokens[3])),
                "beta_deg": float(tokens[4]),
            }
        )
    return blocks


def normalize_params(profile_id, params):
    normalized = dict(params)
    num_layers = max(1, int(params.get("num_layers", 2)))
    normalized["num_layers"] = num_layers

    if profile_id == "mini_cct":
        wcable = int(params["nw"]) * float(params["ddstr"])
        default_layer_radii = [
            float(params["radius"]) + (index + 1) * float(params["dformer"]) + index * (wcable + float(params["dradial"]))
            for index in range(num_layers)
        ]
        raw_layer_radii = parse_series_values(params.get("layer_radius_csv", ""), float)
        if raw_layer_radii:
            if len(raw_layer_radii) < num_layers:
                raw_layer_radii.extend([raw_layer_radii[-1]] * (num_layers - len(raw_layer_radii)))
            normalized["layer_radius"] = [max(1.0e-6, float(value)) for value in raw_layer_radii[:num_layers]]
        else:
            normalized["layer_radius"] = default_layer_radii

        normalized["layer_turns"] = [
            max(1, int(value))
            for value in normalize_series(params.get("layer_turns_csv", ""), num_layers, int(params["num_turns"]), int)
        ]
        normalized["layer_delta"] = [
            max(1.0e-6, float(value))
            for value in normalize_series(params.get("layer_delta_csv", ""), num_layers, float(params["delta"]), float)
        ]
        normalized["layer_alpha_deg"] = [
            max(0.1, float(value))
            for value in normalize_series(params.get("layer_alpha_deg_csv", ""), num_layers, float(params["alpha_deg"]), float)
        ]
        normalized["layer_frame_twist_deg"] = [
            float(value)
            for value in normalize_series(
                params.get("layer_frame_twist_deg_csv", ""),
                num_layers,
                float(params["frame_twist_deg"]),
                float,
            )
        ]
        normalized["layer_current"] = [
            float(value)
            for value in normalize_series(
                params.get("layer_current_csv", ""),
                num_layers,
                float(params["operating_current"]),
                float,
            )
        ]
        return normalized

    if profile_id == "custom_cct":
        default_layer_radii = [
            float(params["radius"]) + index * float(params["dradius"])
            for index in range(num_layers)
        ]
        raw_layer_radii = parse_series_values(params.get("layer_radius_csv", ""), float)
        if raw_layer_radii:
            if len(raw_layer_radii) < num_layers:
                raw_layer_radii.extend([raw_layer_radii[-1]] * (num_layers - len(raw_layer_radii)))
            normalized["layer_radius"] = [max(1.0e-6, float(value)) for value in raw_layer_radii[:num_layers]]
        else:
            normalized["layer_radius"] = default_layer_radii

        normalized["layer_turns"] = [
            max(1.0, float(value))
            for value in normalize_series(params.get("layer_turns_csv", ""), num_layers, float(params["num_turns"]), float)
        ]
        normalized["layer_omega"] = [
            max(1.0e-6, float(value))
            for value in normalize_series(params.get("layer_omega_csv", ""), num_layers, float(params["omega"]), float)
        ]
        normalized["layer_frame_twist_deg"] = [
            float(value)
            for value in normalize_series(
                params.get("layer_frame_twist_deg_csv", ""),
                num_layers,
                float(params["frame_twist_deg"]),
                float,
            )
        ]
        normalized["layer_current"] = [
            float(value)
            for value in normalize_series(
                params.get("layer_current_csv", ""),
                num_layers,
                float(params["operating_current"]),
                float,
            )
        ]
        normalized["layer_dipole"] = [
            float(value)
            for value in normalize_series(
                params.get("layer_dipole_csv", ""),
                num_layers,
                float(params["dipole_amplitude"]),
                float,
            )
        ]
        normalized["layer_quadrupole"] = [
            float(value)
            for value in normalize_series(
                params.get("layer_quadrupole_csv", ""),
                num_layers,
                float(params["quadrupole_amplitude"]),
                float,
            )
        ]
        normalized["layer_quadrupole_offset"] = [
            float(value)
            for value in normalize_series(
                params.get("layer_quadrupole_offset_csv", ""),
                num_layers,
                float(params["quadrupole_offset"]),
                float,
            )
        ]
        normalized["use_frenet_serret"] = parse_bool_token(params.get("use_frenet_serret", False))
        normalized["use_binormal"] = parse_bool_token(params.get("use_binormal", False))
        return normalized

    if profile_id == "cos_theta":
        num_layers = min(2, max(1, int(params.get("num_layers", 2))))
        normalized["num_layers"] = num_layers
        normalized["layer_current"] = [
            float(value)
            for value in normalize_series(
                params.get("layer_current_csv", ""),
                num_layers,
                float(params["operating_current"]),
                float,
            )
        ]
        normalized["layer_radius"] = [
            max(1.0e-6, float(value))
            for value in normalize_series(params.get("layer_radius_csv", ""), num_layers, 0.028, float)
        ]
        normalized["layer_dinner"] = [
            max(1.0e-6, float(value))
            for value in normalize_series(params.get("layer_dinner_csv", ""), num_layers, 0.0015, float)
        ]
        normalized["layer_douter"] = [
            max(1.0e-6, float(value))
            for value in normalize_series(params.get("layer_douter_csv", ""), num_layers, 0.0017, float)
        ]
        normalized["layer_wcable"] = [
            max(1.0e-6, float(value))
            for value in normalize_series(params.get("layer_wcable_csv", ""), num_layers, 0.015, float)
        ]
        normalized["layer_dinsu"] = [
            max(0.0, float(value))
            for value in normalize_series(params.get("layer_dinsu_csv", ""), num_layers, 0.0, float)
        ]
        normalized["layer_reflect_yz"] = normalize_bool_series(
            params.get("layer_reflect_yz_csv", ""),
            num_layers,
            False,
        )
        normalized["layer_reverse"] = normalize_bool_series(
            params.get("layer_reverse_csv", ""),
            num_layers,
            False,
        )
        normalized["layer_blocks"] = []
        for layer_index in range(num_layers):
            blocks = parse_cos_theta_blocks(params.get(f"layer{layer_index + 1}_blocks", ""))
            if not blocks:
                raise ValueError(f"第 {layer_index + 1} 层没有有效的 cosine-theta 块定义。")
            normalized["layer_blocks"].append(blocks)
        return normalized

    if profile_id in WRAPPER_PROFILE_IDS:
        normalized["num_layers"] = 1
        return normalized

    return normalized


def _cpp_flt(value):
    return f"RAT_CONST({float(value):.16g})"


def _cpp_uword(value):
    return f"{max(1, int(value))}u"


def _cpp_bool(value):
    return "true" if bool(value) else "false"


def _cpp_deg(value):
    return f"RAT_CONST({float(value):.16g}) * arma::Datum<rat::fltp>::pi / RAT_CONST(180.0)"


WRAPPER_RENDER_SPECS = {
    "solenoid": {
        "header": "modelsolenoid.hh",
        "class_name": "ModelSolenoid",
        "model_name": "Solenoid",
        "locals": [
            ("inner_radius", "inner_radius", "float"),
            ("dcoil", "dcoil", "float"),
            ("height", "height", "float"),
            ("num_sections", "num_sections", "uword"),
            ("element_size", "element_size", "float"),
            ("num_turns", "num_turns", "float"),
            ("operating_current", "operating_current", "float"),
            ("operating_temperature", "operating_temperature", "float"),
        ],
        "setters": [
            ("set_inner_radius", "inner_radius"),
            ("set_dcoil", "dcoil"),
            ("set_height", "height"),
            ("set_num_sections", "num_sections"),
            ("set_element_size", "element_size"),
            ("set_number_turns", "num_turns"),
            ("set_operating_current", "operating_current"),
            ("set_operating_temperature", "operating_temperature"),
        ],
        "extent_expr": "std::max(inner_radius + dcoil, height / RAT_CONST(2.0))",
    },
    "racetrack": {
        "header": "modelracetrack.hh",
        "class_name": "ModelRacetrack",
        "model_name": "Racetrack",
        "locals": [
            ("arc_radius", "arc_radius", "float"),
            ("length", "length", "float"),
            ("coil_thickness", "coil_thickness", "float"),
            ("coil_width", "coil_width", "float"),
            ("element_size", "element_size", "float"),
            ("num_turns", "num_turns", "float"),
            ("operating_current", "operating_current", "float"),
            ("operating_temperature", "operating_temperature", "float"),
        ],
        "setters": [
            ("set_arc_radius", "arc_radius"),
            ("set_length", "length"),
            ("set_coil_thickness", "coil_thickness"),
            ("set_coil_width", "coil_width"),
            ("set_element_size", "element_size"),
            ("set_number_turns", "num_turns"),
            ("set_operating_current", "operating_current"),
            ("set_operating_temperature", "operating_temperature"),
        ],
        "extent_expr": "std::max(length / RAT_CONST(2.0) + arc_radius + coil_thickness, coil_width / RAT_CONST(2.0) + arc_radius)",
    },
    "rectangle": {
        "header": "modelrectangle.hh",
        "class_name": "ModelRectangle",
        "model_name": "Rectangle",
        "locals": [
            ("arc_radius", "arc_radius", "float"),
            ("length", "length", "float"),
            ("width", "width", "float"),
            ("coil_thickness", "coil_thickness", "float"),
            ("coil_width", "coil_width", "float"),
            ("element_size", "element_size", "float"),
            ("num_turns", "num_turns", "float"),
            ("operating_current", "operating_current", "float"),
            ("operating_temperature", "operating_temperature", "float"),
        ],
        "setters": [
            ("set_arc_radius", "arc_radius"),
            ("set_length", "length"),
            ("set_width", "width"),
            ("set_coil_thickness", "coil_thickness"),
            ("set_coil_width", "coil_width"),
            ("set_element_size", "element_size"),
            ("set_number_turns", "num_turns"),
            ("set_operating_current", "operating_current"),
            ("set_operating_temperature", "operating_temperature"),
        ],
        "extent_expr": "std::max(length, width) / RAT_CONST(2.0) + arc_radius + std::max(coil_thickness, coil_width)",
    },
    "trapezoid": {
        "header": "modeltrapezoid.hh",
        "class_name": "ModelTrapezoid",
        "model_name": "Trapezoid",
        "locals": [
            ("arc_radius", "arc_radius", "float"),
            ("length_1", "length_1", "float"),
            ("length_2", "length_2", "float"),
            ("width", "width", "float"),
            ("coil_thickness", "coil_thickness", "float"),
            ("coil_width", "coil_width", "float"),
            ("element_size", "element_size", "float"),
            ("num_turns", "num_turns", "float"),
            ("operating_current", "operating_current", "float"),
            ("operating_temperature", "operating_temperature", "float"),
        ],
        "setters": [
            ("set_arc_radius", "arc_radius"),
            ("set_length_1", "length_1"),
            ("set_length_2", "length_2"),
            ("set_width", "width"),
            ("set_coil_thickness", "coil_thickness"),
            ("set_coil_width", "coil_width"),
            ("set_element_size", "element_size"),
            ("set_number_turns", "num_turns"),
            ("set_operating_current", "operating_current"),
            ("set_operating_temperature", "operating_temperature"),
        ],
        "extent_expr": "std::max(std::max(length_1, length_2), width) / RAT_CONST(2.0) + arc_radius + std::max(coil_thickness, coil_width)",
    },
    "dshape": {
        "header": "modeldshape.hh",
        "class_name": "ModelDShape",
        "model_name": "D-Shape",
        "locals": [
            ("ell1", "ell1", "float"),
            ("ell2", "ell2", "float"),
            ("coil_thickness", "coil_thickness", "float"),
            ("coil_width", "coil_width", "float"),
            ("element_size", "element_size", "float"),
            ("num_turns", "num_turns", "float"),
            ("operating_current", "operating_current", "float"),
            ("operating_temperature", "operating_temperature", "float"),
        ],
        "setters": [
            ("set_ell1", "ell1"),
            ("set_ell2", "ell2"),
            ("set_coil_thickness", "coil_thickness"),
            ("set_coil_width", "coil_width"),
            ("set_element_size", "element_size"),
            ("set_number_turns", "num_turns"),
            ("set_operating_current", "operating_current"),
            ("set_operating_temperature", "operating_temperature"),
        ],
        "extent_expr": "std::max(ell1, ell2) / RAT_CONST(2.0) + std::max(coil_thickness, coil_width)",
    },
    "flared": {
        "header": "modelflared.hh",
        "class_name": "ModelFlared",
        "model_name": "Flared",
        "locals": [
            ("ell1", "ell1", "float"),
            ("ell2", "ell2", "float"),
            ("arcl", "arcl_deg", "deg"),
            ("radius1", "radius1", "float"),
            ("radius2", "radius2", "float"),
            ("coil_thickness", "coil_thickness", "float"),
            ("coil_width", "coil_width", "float"),
            ("element_size", "element_size", "float"),
            ("num_turns", "num_turns", "float"),
            ("operating_current", "operating_current", "float"),
            ("operating_temperature", "operating_temperature", "float"),
        ],
        "setters": [
            ("set_ell1", "ell1"),
            ("set_ell2", "ell2"),
            ("set_arcl", "arcl"),
            ("set_radius1", "radius1"),
            ("set_radius2", "radius2"),
            ("set_coil_thickness", "coil_thickness"),
            ("set_coil_width", "coil_width"),
            ("set_element_size", "element_size"),
            ("set_number_turns", "num_turns"),
            ("set_operating_current", "operating_current"),
            ("set_operating_temperature", "operating_temperature"),
        ],
        "extent_expr": "std::max(std::max(ell1, ell2) + std::abs(radius1 * arcl), radius2) + std::max(coil_thickness, coil_width)",
    },
    "clover": {
        "header": "modelclover.hh",
        "class_name": "ModelClover",
        "model_name": "Cloverleaf",
        "locals": [
            ("ellstr1", "ellstr1", "float"),
            ("ellstr2", "ellstr2", "float"),
            ("height", "height", "float"),
            ("dpack", "dpack", "float"),
            ("ell_trans", "ell_trans", "float"),
            ("str12", "str12", "float"),
            ("str34", "str34", "float"),
            ("bending_radius", "bending_radius", "float"),
            ("bridge_angle", "bridge_angle_deg", "deg"),
            ("planar_winding", "planar_winding", "bool"),
            ("mirror_midplane", "mirror_midplane", "bool"),
            ("midplane_offset", "midplane_offset", "float"),
            ("coil_thickness", "coil_thickness", "float"),
            ("coil_width", "coil_width", "float"),
            ("element_size", "element_size", "float"),
            ("num_turns", "num_turns", "float"),
            ("operating_current", "operating_current", "float"),
            ("operating_temperature", "operating_temperature", "float"),
        ],
        "setters": [
            ("set_ellstr1", "ellstr1"),
            ("set_ellstr2", "ellstr2"),
            ("set_height", "height"),
            ("set_dpack", "dpack"),
            ("set_ell_trans", "ell_trans"),
            ("set_str12", "str12"),
            ("set_str34", "str34"),
            ("set_bending_radius", "bending_radius"),
            ("set_bridge_angle", "bridge_angle"),
            ("set_planar_winding", "planar_winding"),
            ("set_coil_thickness", "coil_thickness"),
            ("set_coil_width", "coil_width"),
            ("set_element_size", "element_size"),
            ("set_number_turns", "num_turns"),
            ("set_operating_current", "operating_current"),
            ("set_operating_temperature", "operating_temperature"),
        ],
        "extent_expr": "std::max(ellstr1, ellstr2) + height + dpack + std::max(coil_thickness, coil_width)",
    },
    "plasma_ring": {
        "header": "modelplasma.hh",
        "class_name": "ModelPlasma",
        "model_name": "Plasma Ring",
        "locals": [
            ("r0", "r0", "float"),
            ("a", "a", "float"),
            ("delta", "delta", "float"),
            ("kappa", "kappa", "float"),
            ("num_sections", "num_sections", "uword"),
            ("element_size", "element_size", "float"),
            ("num_turns", "num_turns", "float"),
            ("operating_current", "operating_current", "float"),
            ("operating_temperature", "operating_temperature", "float"),
        ],
        "setters": [
            ("set_r0", "r0"),
            ("set_a", "a"),
            ("set_delta", "delta"),
            ("set_kappa", "kappa"),
            ("set_num_sections", "num_sections"),
            ("set_element_size", "element_size"),
            ("set_number_turns", "num_turns"),
            ("set_operating_current", "operating_current"),
            ("set_operating_temperature", "operating_temperature"),
        ],
        "extent_expr": "r0 + a + RAT_CONST(5e-3)",
    },
}


def _render_wrapper_local(local_name, value, kind):
    if kind == "float":
        literal = _cpp_flt(value)
        ctype = "rat::fltp"
    elif kind == "uword":
        literal = _cpp_uword(value)
        ctype = "arma::uword"
    elif kind == "bool":
        literal = _cpp_bool(int(value))
        ctype = "bool"
    elif kind == "deg":
        literal = _cpp_deg(value)
        ctype = "rat::fltp"
    else:
        raise ValueError(f"Unsupported wrapper local kind: {kind}")
    return f"    const {ctype} {local_name} = {literal};"


def render_wrapper_source(profile_id, params):
    profile = CCT_PROFILES[profile_id]
    spec = WRAPPER_RENDER_SPECS[profile_id]
    local_lines = [
        _render_wrapper_local(local_name, params[param_key], kind)
        for local_name, param_key, kind in spec["locals"]
    ]
    setter_lines = [f"    coil->{setter_name}({local_name});" for setter_name, local_name in spec["setters"]]
    local_block = "\n".join(local_lines)
    setter_block = "\n".join(setter_lines)
    extra_includes = []
    if profile_id == "clover":
        extra_includes.append('#include "modelmirror.hh"')
    extra_include_block = ("\n" + "\n".join(extra_includes)) if extra_includes else ""
    if profile_id == "clover":
        model_block = f"""    coil->set_name("{profile['project_name']}_single");

    const rat::mdl::ShModelGroupPr model = rat::mdl::ModelGroup::create();
    model->set_name("{spec['model_name']}");
    if (mirror_midplane) {{
        coil->add_translation(RAT_CONST(0.0), RAT_CONST(0.0), midplane_offset);
        const rat::mdl::ShModelMirrorPr mirrored = rat::mdl::ModelMirror::create(coil, true);
        mirrored->set_name("{spec['model_name']} Pair");
        mirrored->set_reflection_xy();
        mirrored->set_anti_mirror(true);
        model->add_model(mirrored);
    }} else {{
        model->add_model(coil);
    }}"""
    else:
        model_block = f"""    coil->set_name("{profile['project_name']}");

    const rat::mdl::ShModelGroupPr model = rat::mdl::ModelGroup::create();
    model->set_name("{spec['model_name']}");
    model->add_model(coil);"""
    return f"""#include <algorithm>
#include <armadillo>
#include <boost/filesystem.hpp>
#include <cmath>
#include <string>

#include "rat/common/log.hh"
#include "rat/common/opera.hh"

#include "{spec['header']}"
#include "modelgroup.hh"{extra_include_block}
#include "calcmesh.hh"
#include "calcgrid.hh"

int main(int argc, char** argv) {{
    const boost::filesystem::path output_dir = "./output/";
    boost::filesystem::create_directories(output_dir);
    const auto copy_grid_output = [&](const std::string& prefix) {{
        const boost::filesystem::path grid_pvd = output_dir / "grid.pvd";
        const boost::filesystem::path grid_vti = output_dir / "gridpt00000tm00000.vti";
        const boost::filesystem::path target_pvd = output_dir / (prefix + ".pvd");
        const boost::filesystem::path target_vti = output_dir / (prefix + "pt00000tm00000.vti");
        if (boost::filesystem::exists(grid_pvd)) {{
            if (boost::filesystem::exists(target_pvd)) {{
                boost::filesystem::remove(target_pvd);
            }}
            boost::filesystem::copy_file(grid_pvd, target_pvd);
        }}
        if (boost::filesystem::exists(grid_vti)) {{
            if (boost::filesystem::exists(target_vti)) {{
                boost::filesystem::remove(target_vti);
            }}
            boost::filesystem::copy_file(grid_vti, target_vti);
        }}
    }};
{render_opera_arg_helpers()}

{local_block}

    const auto coil = rat::mdl::{spec['class_name']}::create();
{setter_block}
{model_block}
{render_opera_export_block()}

    const rat::cmn::ShLogPr log = rat::cmn::Log::create(rat::cmn::Log::LogoType::RAT);
    const rat::mdl::ShCalcMeshPr mesh = rat::mdl::CalcMesh::create(model);
    mesh->set_name("coil_field_mesh");
    mesh->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);

    const rat::fltp max_extent = {spec['extent_expr']};
    const rat::fltp grid_radius = max_extent + RAT_CONST(12e-3);
    const rat::mdl::ShCalcGridPr grid = rat::mdl::CalcGrid::create(
        model,
        2 * grid_radius,
        2 * grid_radius,
        std::max(RAT_CONST(1e-3), element_size / RAT_CONST(2.0)),
        201u,
        201u,
        1u);
    grid->set_name("space_field_slice");
    grid->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);
    copy_grid_output("space_field_slice");

    return 0;
}}
"""


def render_cmake(executable_name, source_name):
    return f"""cmake_minimum_required(VERSION 3.20)
project(ProjectRatCCTWorkbench LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${{CMAKE_CURRENT_BINARY_DIR}}/bin)

find_package(RatModels REQUIRED)

add_executable({executable_name}
    {source_name}
)
target_include_directories({executable_name} PRIVATE "{RAT_MODELS_INCLUDE}")
target_link_libraries({executable_name} PRIVATE Rat::Models)
"""


def render_opera_arg_helpers():
    return """    const auto has_flag = [&](const std::string& flag) {
        for (int arg_index = 1; arg_index < argc; ++arg_index) {
            if (std::string(argv[arg_index]) == flag) {
                return true;
            }
        }
        return false;
    };
    const bool export_opera = has_flag("--export-opera");
"""


def render_opera_export_block(model_name="model"):
    return f"""    if (export_opera) {{
        {model_name}->export_opera(rat::cmn::Opera::create(output_dir / "opera.cond"));
    }}
"""


def render_mini_source(params):
    turns_cpp = ", ".join(f"{int(value)}u" for value in params["layer_turns"])
    radius_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_radius"])
    delta_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_delta"])
    alpha_cpp = ", ".join(
        f"RAT_CONST({float(value):.16g}) * arma::Datum<rat::fltp>::pi / 180.0" for value in params["layer_alpha_deg"]
    )
    twist_cpp = ", ".join(
        f"RAT_CONST({float(value):.16g}) * arma::Datum<rat::fltp>::pi / 180.0" for value in params["layer_frame_twist_deg"]
    )
    current_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_current"])
    return f"""#include <algorithm>
#include <armadillo>
#include <boost/filesystem.hpp>
#include <cmath>
#include <string>
#include <vector>

#include "rat/common/log.hh"
#include "rat/common/opera.hh"
#include "rat/mat/database.hh"
#include "rat/mat/rutherfordcable.hh"

#include "crossrectangle.hh"
#include "modelcoil.hh"
#include "pathcct.hh"
#include "modelgroup.hh"
#include "pathaxis.hh"
#include "calcmesh.hh"
#include "calcgrid.hh"
#include "calcharmonics.hh"

int main(int argc, char** argv) {{
    const boost::filesystem::path output_dir = "./output/";
    boost::filesystem::create_directories(output_dir);
    const auto copy_grid_output = [&](const std::string& prefix) {{
        const boost::filesystem::path grid_pvd = output_dir / "grid.pvd";
        const boost::filesystem::path grid_vti = output_dir / "gridpt00000tm00000.vti";
        const boost::filesystem::path target_pvd = output_dir / (prefix + ".pvd");
        const boost::filesystem::path target_vti = output_dir / (prefix + "pt00000tm00000.vti");
        if (boost::filesystem::exists(grid_pvd)) {{
            if (boost::filesystem::exists(target_pvd)) {{
                boost::filesystem::remove(target_pvd);
            }}
            boost::filesystem::copy_file(grid_pvd, target_pvd);
        }}
        if (boost::filesystem::exists(grid_vti)) {{
            if (boost::filesystem::exists(target_vti)) {{
                boost::filesystem::remove(target_vti);
            }}
            boost::filesystem::copy_file(grid_vti, target_vti);
        }}
    }};
{render_opera_arg_helpers()}

    const arma::uword num_poles = {int(params["num_poles"])}u;
    const arma::uword num_layers = {int(params["num_layers"])}u;
    const arma::uword num_nodes_per_turn = {int(params["num_nodes_per_turn"])}u;
    const arma::uword nd = {int(params["nd"])}u;
    const arma::uword nw = {int(params["nw"])}u;

    const rat::fltp frame_twist = RAT_CONST({float(params["frame_twist_deg"]):.16g}) * arma::Datum<rat::fltp>::pi / 180.0;
    const rat::fltp radius = RAT_CONST({float(params["radius"]):.16g});
    const rat::fltp dradial = RAT_CONST({float(params["dradial"]):.16g});
    const rat::fltp dformer = RAT_CONST({float(params["dformer"]):.16g});
    const rat::fltp element_size = RAT_CONST({float(params["element_size"]):.16g});
    const rat::fltp operating_temperature = RAT_CONST({float(params["operating_temperature"]):.16g});
    const rat::fltp dstr = RAT_CONST({float(params["dstr"]):.16g});
    const rat::fltp ddstr = RAT_CONST({float(params["ddstr"]):.16g});
    const rat::fltp fcu2sc = RAT_CONST({float(params["fcu2sc"]):.16g});

    // Default CCT slot convention follows the upstream RAT example:
    // dcable = slot width along the former tangent, wcable = slot depth along the former normal.
    const rat::fltp dcable = nd * ddstr;
    const rat::fltp wcable = nw * ddstr;
    const rat::fltp num_strands = nd * nw;
    const std::vector<rat::fltp> layer_radii = {{{radius_cpp}}};
    const std::vector<arma::uword> layer_turns = {{{turns_cpp}}};
    const std::vector<rat::fltp> layer_deltas = {{{delta_cpp}}};
    const std::vector<rat::fltp> layer_alphas = {{{alpha_cpp}}};
    const std::vector<rat::fltp> layer_twists = {{{twist_cpp}}};
    const std::vector<rat::fltp> layer_currents = {{{current_cpp}}};
    const rat::fltp coil_outer_radius = layer_radii.back() + wcable;
    rat::fltp max_axial_span = RAT_CONST(0.0);
    for (arma::uword layer_index = 0; layer_index < num_layers; ++layer_index) {{
        const rat::fltp layer_alpha = layer_alphas.at(layer_index);
        const rat::fltp layer_pitch = (dcable + layer_deltas.at(layer_index)) / std::sin(layer_alpha);
        const rat::fltp layer_span = layer_turns.at(layer_index) * layer_pitch + 2 * coil_outer_radius;
        max_axial_span = std::max(max_axial_span, layer_span);
    }}

    const rat::mat::ShRutherfordCablePr cable = rat::mat::RutherfordCable::create();
    cable->set_strand(rat::mat::Database::nbti_wire_lhc(dstr, fcu2sc));
    cable->set_num_strands(nd * nw);
    cable->set_width(wcable);
    cable->set_thickness(dcable);
    cable->set_keystone(0);
    cable->set_pitch(0);
    cable->set_dinsu(0);
    cable->set_fcabling(1.0);
    cable->setup();

    const rat::mdl::ShCrossRectanglePr cross = rat::mdl::CrossRectangle::create(
        -dcable / 2, dcable / 2, 0, wcable, dcable / nd, wcable / nw);

    const rat::mdl::ShModelGroupPr model = rat::mdl::ModelGroup::create();
    model->set_name("Mini CCT");
    for (arma::uword layer_index = 0; layer_index < num_layers; ++layer_index) {{
        const rat::fltp coil_radius = layer_radii.at(layer_index);
        const rat::fltp layer_alpha = layer_alphas.at(layer_index);
        const rat::fltp layer_delta = layer_deltas.at(layer_index);
        const rat::fltp a = coil_radius / (num_poles * std::tan(layer_alpha));
        const rat::fltp omega = (dcable + layer_delta) / std::sin(layer_alpha);

        const rat::mdl::ShPathCCTPr layer_path = rat::mdl::PathCCT::create(
            num_poles, coil_radius, a, omega, layer_turns.at(layer_index), num_nodes_per_turn);
        if ((layer_index % 2u) == 1u) {{
            layer_path->set_is_reverse(true);
        }}
        if (layer_twists.at(layer_index) != RAT_CONST(0.0)) {{
            layer_path->set_twist(layer_twists.at(layer_index));
        }} else if (frame_twist != RAT_CONST(0.0)) {{
            layer_path->set_twist(frame_twist);
        }}

        const rat::mdl::ShModelCoilPr coil = rat::mdl::ModelCoil::create(layer_path, cross, cable);
        coil->set_name("layer" + std::to_string(layer_index + 1));
        coil->set_operating_temperature(operating_temperature);
        coil->set_operating_current(layer_currents.at(layer_index));
        coil->set_number_turns(num_strands);
        model->add_model(coil);
    }}
{render_opera_export_block()}

    const rat::mdl::ShPathAxisPr axis = rat::mdl::PathAxis::create('z', 'y', 0.4, 0, 0, 0, element_size);
    const rat::cmn::ShLogPr log = rat::cmn::Log::create(rat::cmn::Log::LogoType::RAT);

    const rat::mdl::ShCalcHarmonicsPr harmonics = rat::mdl::CalcHarmonics::create(
        model, axis, RAT_CONST(10e-3), true);
    harmonics->set_name("field_harmonics");
    harmonics->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);

    const rat::mdl::ShCalcMeshPr mesh = rat::mdl::CalcMesh::create(model);
    mesh->set_name("coil_field_mesh");
    mesh->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);

    const rat::fltp grid_radius = coil_outer_radius + RAT_CONST(5e-3);
    const rat::mdl::ShCalcGridPr grid = rat::mdl::CalcGrid::create(
        model, 2 * grid_radius, 2 * grid_radius, element_size / 2, 181u, 181u, 1u);
    grid->set_name("space_field_slice");
    grid->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);
    copy_grid_output("space_field_slice");

    const rat::fltp volume_xy = 2 * (coil_outer_radius + RAT_CONST(8e-3));
    const rat::fltp volume_z = std::max(volume_xy, max_axial_span + RAT_CONST(12e-3));
    const rat::mdl::ShCalcGridPr grid_volume = rat::mdl::CalcGrid::create(
        model, volume_xy, volume_xy, volume_z, 61u, 61u, 61u);
    grid_volume->set_name("space_field_volume");
    grid_volume->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);
    copy_grid_output("space_field_volume");
    return 0;
}}
"""


def render_custom_source(params):
    turns_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_turns"])
    radius_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_radius"])
    omega_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_omega"])
    twist_cpp = ", ".join(
        f"RAT_CONST({float(value):.16g}) * arma::Datum<rat::fltp>::pi / 180.0" for value in params["layer_frame_twist_deg"]
    )
    current_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_current"])
    dipole_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_dipole"])
    quadrupole_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_quadrupole"])
    quadrupole_offset_cpp = ", ".join(
        f"RAT_CONST({float(value):.16g})" for value in params["layer_quadrupole_offset"]
    )
    return f"""#include <algorithm>
#include <armadillo>
#include <boost/filesystem.hpp>
#include <string>

#include "rat/common/extra.hh"
#include "rat/common/log.hh"
#include "rat/common/opera.hh"
#include "rat/mat/database.hh"
#include "rat/mat/rutherfordcable.hh"

#include "driveac.hh"
#include "drivedc.hh"
#include "driveinterp.hh"
#include "pathcctcustom.hh"
#include "crossrectangle.hh"
#include "modelcoil.hh"
#include "modelgroup.hh"
#include "transbend.hh"
#include "calcmesh.hh"
#include "calcgrid.hh"
#include "calcharmonics.hh"
#include "pathaxis.hh"

int main(int argc, char** argv) {{
    const boost::filesystem::path output_dir = "./output/";
    boost::filesystem::create_directories(output_dir);
    const auto copy_grid_output = [&](const std::string& prefix) {{
        const boost::filesystem::path grid_pvd = output_dir / "grid.pvd";
        const boost::filesystem::path grid_vti = output_dir / "gridpt00000tm00000.vti";
        const boost::filesystem::path target_pvd = output_dir / (prefix + ".pvd");
        const boost::filesystem::path target_vti = output_dir / (prefix + "pt00000tm00000.vti");
        if (boost::filesystem::exists(grid_pvd)) {{
            if (boost::filesystem::exists(target_pvd)) {{
                boost::filesystem::remove(target_pvd);
            }}
            boost::filesystem::copy_file(grid_pvd, target_pvd);
        }}
        if (boost::filesystem::exists(grid_vti)) {{
            if (boost::filesystem::exists(target_vti)) {{
                boost::filesystem::remove(target_vti);
            }}
            boost::filesystem::copy_file(grid_vti, target_vti);
        }}
    }};
{render_opera_arg_helpers()}

    const rat::fltp nt = RAT_CONST({float(params["num_turns"]):.16g});
    const rat::fltp radius = RAT_CONST({float(params["radius"]):.16g});
    const rat::fltp dradius = RAT_CONST({float(params["dradius"]):.16g});
    const rat::fltp omega = RAT_CONST({float(params["omega"]):.16g});
    const rat::fltp frame_twist = RAT_CONST({float(params["frame_twist_deg"]):.16g}) * arma::Datum<rat::fltp>::pi / 180.0;
    const bool use_frenet_serret = {_cpp_bool(params.get("use_frenet_serret", False))};
    const bool use_binormal = {_cpp_bool(params.get("use_binormal", False))};
    const arma::uword num_layers = {int(params["num_layers"])}u;
    const arma::uword num_nodes_per_turn = {int(params["num_nodes_per_turn"])}u;
    const arma::uword num_sect_per_turn = {int(params["num_sect_per_turn"])}u;
    const rat::fltp dipole_amplitude = RAT_CONST({float(params["dipole_amplitude"]):.16g});
    const rat::fltp quadrupole_amplitude = RAT_CONST({float(params["quadrupole_amplitude"]):.16g});
    const rat::fltp quadrupole_offset = RAT_CONST({float(params["quadrupole_offset"]):.16g});
    const rat::fltp bend_radius = RAT_CONST({float(params["bend_radius"]):.16g});
    const rat::fltp element_size = RAT_CONST({float(params["element_size"]):.16g});
    const rat::fltp operating_current = RAT_CONST({float(params["operating_current"]):.16g});
    const rat::fltp operating_temperature = RAT_CONST({float(params["operating_temperature"]):.16g});
    const rat::fltp dstr = RAT_CONST({float(params["dstr"]):.16g});
    const rat::fltp ddstr = RAT_CONST({float(params["ddstr"]):.16g});
    const rat::fltp fcu2sc = RAT_CONST({float(params["fcu2sc"]):.16g});
    const arma::uword nd = {int(params["nd"])}u;
    const arma::uword nw = {int(params["nw"])}u;

    // Default CCT slot convention follows the upstream RAT example:
    // dcable = slot width along the former tangent, wcable = slot depth along the former normal.
    const rat::fltp dcable = nd * ddstr;
    const rat::fltp wcable = nw * ddstr;
    const rat::fltp num_strands = nd * nw;
    const std::vector<rat::fltp> layer_turns = {{{turns_cpp}}};
    const std::vector<rat::fltp> layer_radii = {{{radius_cpp}}};
    const std::vector<rat::fltp> layer_omegas = {{{omega_cpp}}};
    const std::vector<rat::fltp> layer_twists = {{{twist_cpp}}};
    const std::vector<rat::fltp> layer_currents = {{{current_cpp}}};
    const std::vector<rat::fltp> layer_dipoles = {{{dipole_cpp}}};
    const std::vector<rat::fltp> layer_quadrupoles = {{{quadrupole_cpp}}};
    const std::vector<rat::fltp> layer_quadrupole_offsets = {{{quadrupole_offset_cpp}}};
    const rat::fltp coil_outer_radius = layer_radii.back() + wcable;
    rat::fltp max_axial_span = RAT_CONST(0.0);
    for (arma::uword layer_index = 0; layer_index < num_layers; ++layer_index) {{
        const rat::fltp layer_span = layer_turns.at(layer_index) * layer_omegas.at(layer_index) + 2 * coil_outer_radius;
        max_axial_span = std::max(max_axial_span, layer_span);
    }}

    const rat::mdl::ShPathAxisPr axis = rat::mdl::PathAxis::create('z', 'y', 0.5, 0, 0, 0, element_size);
    if (bend_radius > RAT_CONST(0.0)) {{
        axis->add_transformation(rat::mdl::TransBend::create(
            rat::cmn::Extra::unit_vec('y'),
            rat::cmn::Extra::unit_vec('x'),
            bend_radius));
    }}

    const rat::mdl::ShCrossRectanglePr cross = rat::mdl::CrossRectangle::create(
        -dcable / 2, dcable / 2, 0, wcable, element_size / 2);

    const rat::mat::ShRutherfordCablePr cable = rat::mat::RutherfordCable::create();
    cable->set_strand(rat::mat::Database::nbti_wire_lhc(dstr, fcu2sc));
    cable->set_num_strands(nd * nw);
    cable->set_width(wcable);
    cable->set_thickness(dcable);
    cable->set_keystone(0);
    cable->set_pitch(0);
    cable->set_dinsu(0);
    cable->set_fcabling(1.0);
    cable->setup();

    const rat::mdl::ShModelGroupPr model = rat::mdl::ModelGroup::create();
    model->set_name("Custom CCT");
    for (arma::uword layer_index = 0; layer_index < num_layers; ++layer_index) {{
        const rat::fltp layer_turns_value = layer_turns.at(layer_index);
        const rat::mdl::ShPathCCTCustomPr path = rat::mdl::PathCCTCustom::create();
        path->set_range(-layer_turns_value / 2, layer_turns_value / 2);
        path->set_rho(layer_radii.at(layer_index));
        path->set_omega(layer_omegas.at(layer_index));
        path->set_num_nodes_per_turn(num_nodes_per_turn);
        path->set_num_sect_per_turn(num_sect_per_turn);
        path->set_num_layers(1u);
        path->set_rho_increment(RAT_CONST(0.0));
        path->set_use_frenet_serret(use_frenet_serret);
        path->set_use_binormal(use_binormal);
        // PathCCTCustom flips odd layers internally when num_layers > 1.
        // In the GUI workbench we model each layer as an independent path so
        // we must restore the alternating winding direction explicitly.
        if ((layer_index % 2u) == 1u) {{
            path->set_is_reverse(true);
        }}
        if (layer_twists.at(layer_index) != RAT_CONST(0.0)) {{
            path->set_twist(rat::mdl::DriveDC::create(layer_twists.at(layer_index)));
        }} else if (frame_twist != RAT_CONST(0.0)) {{
            path->set_twist(rat::mdl::DriveDC::create(frame_twist));
        }}

        const rat::mdl::ShCCTHarmonicPr dipole = rat::mdl::CCTHarmonicDrive::create(
            1, false, rat::mdl::DriveInterp::create(
                {{-layer_turns_value / 2, layer_turns_value / 2}},
                {{-layer_dipoles.at(layer_index), -layer_dipoles.at(layer_index)}}), false);
        dipole->set_normalize_length(false);
        path->add_harmonic(dipole);

        const rat::mdl::ShCCTHarmonicPr quadrupole = rat::mdl::CCTHarmonicDrive::create(
            2, false, rat::mdl::DriveAC::create(
                layer_quadrupoles.at(layer_index), 1, 0.0, layer_quadrupole_offsets.at(layer_index)), false);
        quadrupole->set_normalize_length(true);
        path->add_harmonic(quadrupole);

        if (bend_radius > RAT_CONST(0.0)) {{
            path->set_use_radius();
            path->set_bending_radius(bend_radius);
        }}

        const rat::mdl::ShModelCoilPr coil = rat::mdl::ModelCoil::create(path, cross, cable);
        coil->set_name("layer" + std::to_string(layer_index + 1));
        coil->set_number_turns(num_strands);
        coil->set_operating_current(layer_currents.at(layer_index));
        coil->set_operating_temperature(operating_temperature);
        model->add_model(coil);
    }}
{render_opera_export_block()}

    const rat::cmn::ShLogPr log = rat::cmn::Log::create(rat::cmn::Log::LogoType::RAT);
    const rat::mdl::ShCalcMeshPr mesh = rat::mdl::CalcMesh::create(model);
    mesh->set_name("coil_field_mesh");
    mesh->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);

    const rat::mdl::ShCalcHarmonicsPr harmonics = rat::mdl::CalcHarmonics::create(
        model, axis, 2 * radius / 3, true);
    harmonics->set_name("field_harmonics");
    harmonics->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);

    const rat::mdl::ShCalcGridPr grid = rat::mdl::CalcGrid::create(
        model, 2 * (coil_outer_radius + RAT_CONST(5e-3)), 2 * (coil_outer_radius + RAT_CONST(5e-3)), element_size / 2, 181u, 181u, 1u);
    if (bend_radius > RAT_CONST(0.0)) {{
        grid->set_offset({{-bend_radius, RAT_CONST(0.0), RAT_CONST(0.0)}});
    }}
    grid->set_name("space_field_slice");
    grid->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);
    copy_grid_output("space_field_slice");

    const rat::fltp volume_margin = coil_outer_radius + RAT_CONST(12e-3);
    const rat::fltp volume_x = bend_radius > RAT_CONST(0.0)
        ? 2 * (std::abs(bend_radius) + volume_margin)
        : std::max(2 * volume_margin, max_axial_span + RAT_CONST(12e-3));
    const rat::fltp volume_y = 2 * volume_margin;
    const rat::fltp volume_z = bend_radius > RAT_CONST(0.0)
        ? 2 * (std::abs(bend_radius) + volume_margin)
        : std::max(2 * volume_margin, max_axial_span + RAT_CONST(12e-3));
    const rat::mdl::ShCalcGridPr grid_volume = rat::mdl::CalcGrid::create(
        model, volume_x, volume_y, volume_z, 61u, 61u, 61u);
    if (bend_radius > RAT_CONST(0.0)) {{
        grid_volume->set_offset({{-bend_radius, RAT_CONST(0.0), RAT_CONST(0.0)}});
    }}
    grid_volume->set_name("space_field_volume");
    grid_volume->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);
    copy_grid_output("space_field_volume");
    return 0;
}}
"""


def render_cos_theta_blocks_cpp(layer_blocks):
    rendered_layers = []
    for blocks in layer_blocks:
        rendered_blocks = []
        for block in blocks:
            rendered_blocks.append(
                "{"
                f"{int(block['num_cables'])}u, "
                f"RAT_CONST({float(block['phi_deg']):.16g}), "
                f"RAT_CONST({float(block['alpha_deg']):.16g}), "
                f"RAT_CONST({float(block['zend']):.16g}), "
                f"RAT_CONST({float(block['beta_deg']):.16g})"
                "}"
            )
        rendered_layers.append("{\n        " + ",\n        ".join(rendered_blocks) + "\n    }")
    return ",\n    ".join(rendered_layers)


def render_cos_theta_source(params):
    current_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_current"])
    radius_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_radius"])
    dinner_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_dinner"])
    douter_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_douter"])
    wcable_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_wcable"])
    dinsu_cpp = ", ".join(f"RAT_CONST({float(value):.16g})" for value in params["layer_dinsu"])
    reflect_cpp = ", ".join("true" if value else "false" for value in params["layer_reflect_yz"])
    reverse_cpp = ", ".join("true" if value else "false" for value in params["layer_reverse"])
    blocks_cpp = render_cos_theta_blocks_cpp(params["layer_blocks"])
    return f"""#include <algorithm>
#include <armadillo>
#include <boost/filesystem.hpp>
#include <list>
#include <string>
#include <vector>

#include "rat/common/log.hh"
#include "rat/common/opera.hh"

#include "pathcostheta.hh"
#include "crosswedge.hh"
#include "modelcoil.hh"
#include "modelgroup.hh"
#include "modeltoroid.hh"
#include "calcmesh.hh"
#include "calcgrid.hh"
#include "calcharmonics.hh"
#include "pathaxis.hh"

namespace {{
struct BlockSpec {{
    arma::uword num_cables;
    rat::fltp phi_deg;
    rat::fltp alpha_deg;
    rat::fltp zend;
    rat::fltp beta_deg;
}};
}}

int main(int argc, char** argv) {{
    const boost::filesystem::path output_dir = "./output/";
    boost::filesystem::create_directories(output_dir);
    const auto copy_grid_output = [&](const std::string& prefix) {{
        const boost::filesystem::path grid_pvd = output_dir / "grid.pvd";
        const boost::filesystem::path grid_vti = output_dir / "gridpt00000tm00000.vti";
        const boost::filesystem::path target_pvd = output_dir / (prefix + ".pvd");
        const boost::filesystem::path target_vti = output_dir / (prefix + "pt00000tm00000.vti");
        if (boost::filesystem::exists(grid_pvd)) {{
            if (boost::filesystem::exists(target_pvd)) {{
                boost::filesystem::remove(target_pvd);
            }}
            boost::filesystem::copy_file(grid_pvd, target_pvd);
        }}
        if (boost::filesystem::exists(grid_vti)) {{
            if (boost::filesystem::exists(target_vti)) {{
                boost::filesystem::remove(target_vti);
            }}
            boost::filesystem::copy_file(grid_vti, target_vti);
        }}
    }};
{render_opera_arg_helpers()}

    const arma::uword num_poles = {int(params["num_poles"])}u;
    const arma::uword num_layers = {int(params["num_layers"])}u;
    const rat::fltp requested_element_size = RAT_CONST({float(params["element_size"]):.16g});
    const rat::fltp element_size = std::max(requested_element_size, RAT_CONST(5e-4));
    const arma::uword cross_num_thickness = std::max<arma::uword>(2u, {int(params["cross_num_thickness"])}u);
    const arma::uword cross_num_width = std::max<arma::uword>(4u, {int(params["cross_num_width"])}u);
    const rat::fltp operating_temperature = RAT_CONST({float(params["operating_temperature"]):.16g});
    const std::vector<rat::fltp> layer_currents = {{{current_cpp}}};
    const std::vector<rat::fltp> layer_radii = {{{radius_cpp}}};
    const std::vector<rat::fltp> layer_dinner = {{{dinner_cpp}}};
    const std::vector<rat::fltp> layer_douter = {{{douter_cpp}}};
    const std::vector<rat::fltp> layer_wcable = {{{wcable_cpp}}};
    const std::vector<rat::fltp> layer_dinsu = {{{dinsu_cpp}}};
    const std::vector<bool> layer_reflect = {{{reflect_cpp}}};
    const std::vector<bool> layer_reverse = {{{reverse_cpp}}};
    const std::vector<std::vector<BlockSpec>> layer_blocks = {{
        {blocks_cpp}
    }};

    const auto degree_to_rad = [](const rat::fltp degrees) {{
        return degrees * arma::Datum<rat::fltp>::pi / RAT_CONST(180.0);
    }};
    const auto block_angle_to_rad = [num_poles, &degree_to_rad](const rat::fltp degrees) {{
        return degree_to_rad(degrees / std::max<rat::fltp>(RAT_CONST(1.0), static_cast<rat::fltp>(num_poles)));
    }};

    rat::fltp max_radius = RAT_CONST(0.0);
    rat::fltp max_zend = RAT_CONST(0.0);
    const rat::mdl::ShModelGroupPr layer_stack = rat::mdl::ModelGroup::create();
    layer_stack->set_name("Cosine-Theta Layers");

    for (arma::uword layer_index = 0; layer_index < num_layers; ++layer_index) {{
        std::list<rat::mdl::ShCosThetaBlockPr> blocks;
        for (const auto& block : layer_blocks.at(layer_index)) {{
            blocks.push_back(rat::mdl::CosThetaBlock::create(
                num_poles,
                block.num_cables,
                layer_radii.at(layer_index),
                block_angle_to_rad(block.phi_deg),
                block_angle_to_rad(block.alpha_deg),
                layer_dinner.at(layer_index),
                layer_douter.at(layer_index),
                layer_wcable.at(layer_index),
                block.zend,
                degree_to_rad(block.beta_deg),
                layer_dinsu.at(layer_index)));
            max_zend = std::max(max_zend, block.zend);
        }}

        const rat::mdl::ShPathCosThetaPr path = rat::mdl::PathCosTheta::create(blocks, element_size);
        if (layer_reflect.at(layer_index)) {{
            path->add_reflect_yz();
        }}
        if (layer_reverse.at(layer_index)) {{
            path->add_reverse();
        }}

        const rat::mdl::ShCrossWedgePr cross = rat::mdl::CrossWedge::create(
            layer_dinner.at(layer_index),
            layer_douter.at(layer_index),
            -layer_wcable.at(layer_index),
            RAT_CONST(0.0),
            cross_num_thickness,
            cross_num_width);
        cross->set_surface_offset(layer_dinsu.at(layer_index));

        const rat::mdl::ShModelCoilPr coil = rat::mdl::ModelCoil::create(path, cross);
        coil->set_name("layer" + std::to_string(layer_index + 1));
        coil->set_number_turns(1);
        coil->set_operating_current(layer_currents.at(layer_index));
        coil->set_operating_temperature(operating_temperature);
        layer_stack->add_model(coil);

        max_radius = std::max(max_radius, layer_radii.at(layer_index) + layer_wcable.at(layer_index));
    }}
    const arma::uword magnet_pole_count = std::max<arma::uword>(2u, 2u * num_poles);
    const rat::mdl::ShModelToroidPr pole_array = rat::mdl::ModelToroid::create(layer_stack, magnet_pole_count);
    pole_array->set_name("Cosine-Theta Multipole");
    pole_array->set_coil_azymuth('y');
    pole_array->set_coil_radial('x');
    pole_array->set_toroid_axis('z');
    pole_array->set_toroid_radial('x');
    pole_array->set_alternate(true);

    const rat::mdl::ShModelGroupPr model = rat::mdl::ModelGroup::create();
    model->set_name("Cosine-Theta Coil");
    model->add_model(pole_array);
{render_opera_export_block()}

    const rat::cmn::ShLogPr log = rat::cmn::Log::create(rat::cmn::Log::LogoType::RAT);
    const rat::mdl::ShCalcMeshPr mesh = rat::mdl::CalcMesh::create(model);
    mesh->set_name("coil_field_mesh");
    mesh->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);

    const rat::fltp axis_length = std::max(RAT_CONST(0.45), 2 * max_zend + RAT_CONST(0.12));
    const rat::mdl::ShPathAxisPr axis = rat::mdl::PathAxis::create('z', 'y', axis_length, 0, 0, 0, element_size);
    const rat::mdl::ShCalcHarmonicsPr harmonics = rat::mdl::CalcHarmonics::create(
        model,
        axis,
        std::max(RAT_CONST(8e-3), layer_radii.front() * RAT_CONST(0.6)),
        true);
    harmonics->set_name("field_harmonics");
    harmonics->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);

    const rat::fltp grid_radius = max_radius + RAT_CONST(12e-3);
    const rat::mdl::ShCalcGridPr grid = rat::mdl::CalcGrid::create(
        model,
        2 * grid_radius,
        2 * grid_radius,
        std::max(RAT_CONST(1e-3), element_size / 2),
        221u,
        221u,
        1u);
    grid->set_name("space_field_slice");
    grid->calculate_write({{RAT_CONST(0.0)}}, output_dir, log);
    copy_grid_output("space_field_slice");

    return 0;
}}
"""


def render_source(profile_id, params):
    if profile_id == "mini_cct":
        return render_mini_source(params)
    if profile_id == "custom_cct":
        return render_custom_source(params)
    if profile_id == "cos_theta":
        return render_cos_theta_source(params)
    if profile_id in WRAPPER_PROFILE_IDS:
        return render_wrapper_source(profile_id, params)
    raise KeyError(f"Unsupported magnet profile: {profile_id}")


def write_cct_project(profile_id, project_name, params):
    profile = CCT_PROFILES[profile_id]
    clean_name = sanitize_project_name(project_name or profile["project_name"])
    merged_params = get_profile_defaults(profile_id)
    merged_params.update(params)
    normalized_params = normalize_params(profile_id, merged_params)
    project_dir = CCT_WORKBENCH_ROOT / clean_name
    project_dir.mkdir(parents=True, exist_ok=True)

    source_path = project_dir / profile["source_name"]
    cmake_path = project_dir / "CMakeLists.txt"
    output_dir = project_dir / "output"
    build_dir = project_dir / "build"
    meta_path = project_dir / "project_meta.json"

    output_dir.mkdir(parents=True, exist_ok=True)
    expected_outputs = list(
        profile.get(
            "expected_outputs",
            ["coil_field_mesh*.vtu", "space_field_slice*.vti", "field_harmonics*.vtu", "space_field_volume*.vti"],
        )
    )
    if "opera.cond" not in expected_outputs:
        expected_outputs.append("opera.cond")

    source_path.write_text(render_source(profile_id, normalized_params), encoding="utf-8")
    cmake_path.write_text(render_cmake(profile["executable_name"], profile["source_name"]), encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "profile_id": profile_id,
                "profile_label": profile["label"],
                "profile_note": profile.get("note", ""),
                "project_name": clean_name,
                "source_name": profile["source_name"],
                "executable_name": profile["executable_name"],
                "expected_outputs": expected_outputs,
                "params": merged_params,
                "normalized_params": normalized_params,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return {
        "profile_id": profile_id,
        "profile_label": profile["label"],
        "project_name": clean_name,
        "params": merged_params,
        "normalized_params": normalized_params,
        "profile_note": profile.get("note", ""),
        "project_dir": project_dir,
        "source_path": source_path,
        "cmake_path": cmake_path,
        "output_dir": output_dir,
        "build_dir": build_dir,
        "meta_path": meta_path,
        "executable_name": profile["executable_name"],
        "expected_outputs": expected_outputs,
    }
