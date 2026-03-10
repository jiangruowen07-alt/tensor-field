"""
UI strings - 中英文双语 / Bilingual (Chinese & English)
"""

# Current language: "en" or "zh"
_current_lang = "en"


def get_language():
    return _current_lang


def set_language(lang):
    """Switch language. Call _refresh_ui_texts() in app after this."""
    global _current_lang, T, RUN_MODE_OPTS, ENGINE_OPTS, FIELD_TYPE_OPTS, BASIS_TYPE_OPTS, SEED_TYPE_OPTS
    global SPACING_MODE_OPTS, CURVE_SPACING_MODES, INTEGRATE_METHOD_OPTS
    global BTN_ADD_CURVE, BTN_DRAW, BTN_DONE_DRAWING, BTN_CLEAR, BTN_RESET, BTN_GENERATE
    global BTN_PARAMS, BTN_EDIT, BTN_DEL
    global BLEND_PARAMS_TITLE, BLEND_TANGENT, BLEND_NORMAL, BLEND_DECAY, BLEND_RADIUS, BLEND_HINT
    global SCALAR_PARAMS_TITLE, SCALAR_METHOD, SCALAR_STEP, SCALAR_COUNT
    global SCALAR_CENTER_X, SCALAR_CENTER_Y, SCALAR_SIGMA
    global OFFSET_HINT, MULTI_SEED_HINT, CURVE_PARAMS_HINT, CURVE_SELECT_HINT
    global LINE_SPACING_SHORT, POS_NEG, OFFSET_XY, SPACING_MODE_SHORT, SPACING_SCALE_SHORT, CROSS_SPACING_SHORT
    global NOISE_ENABLED, ROADS_PERP, ROAD_HIERARCHY, ADAPTIVE_CROSS
    global BASIS_BLEND_FACTOR, RIVER_BOUNDARY_TITLE, USE_RIVER_BOUNDARY, BOUNDARY_DECAY, BOUNDARY_BLEND
    global TENSOR_CENTER_TITLE, TENSOR_CENTER_X, TENSOR_CENTER_Y, BTN_DRAW_RIVER
    global BTN_ADD_CENTER, BTN_CLEAR_CENTERS, TENSOR_CENTER_HINT
    global HEIGHT_FIELD_TITLE, USE_HEIGHT_FIELD, BTN_LOAD_HEIGHT, BTN_CLEAR_HEIGHT, HEIGHT_BLEND
    global HYPERSTREAMLINE_TITLE, HYPERSTREAMLINE_MAJOR, HYPERSTREAMLINE_MINOR, HYPERSTREAMLINE_BOTH
    global BTN_ADD_SEED, BTN_CLEAR_SEEDS, HYPER_STEP_SIZE, HYPER_MAX_LENGTH, HYPER_ANGLE_STOP
    global PAPER_OPTIONS, STREET_GEN_MODE, STREET_PARAM, STREET_HYPER, TWO_STAGE
    global PERLIN_ROTATION, PERLIN_STRENGTH, LAPLACIAN_SMOOTH, LAPLACIAN_ITERS
    global BTN_DRAW_BRUSH, BTN_CLEAR_BRUSH, BRUSH_HINT
    global CURVATURE_WEIGHT, ATTRACTOR_WEIGHT, VALUE_WEIGHT
    global PARCEL_FRONTAGE_BASED, PARCEL_BLOCK_BY_BLOCK, PARCEL_CORNER_SEPARATE
    global PARCEL_PERTURBATION, PARCEL_PERTURBATION_STR
    global NO_CURVES_YET, DRAW_MODE_STATUS

    _current_lang = "zh" if lang in ("zh", "zh-CN", "cn") else "en"
    d = _LANG_ZH if _current_lang == "zh" else _LANG_EN

    T.update(d["T"])
    RUN_MODE_OPTS[:] = d["RUN_MODE_OPTS"]
    ENGINE_OPTS[:] = d["ENGINE_OPTS"]
    FIELD_TYPE_OPTS[:] = d["FIELD_TYPE_OPTS"]
    BASIS_TYPE_OPTS[:] = d["BASIS_TYPE_OPTS"]
    SEED_TYPE_OPTS[:] = d["SEED_TYPE_OPTS"]
    SPACING_MODE_OPTS[:] = d["SPACING_MODE_OPTS"]
    CURVE_SPACING_MODES.clear()
    CURVE_SPACING_MODES.update(d["CURVE_SPACING_MODES"])
    INTEGRATE_METHOD_OPTS[:] = d["INTEGRATE_METHOD_OPTS"]

    # Scalar vars
    globals()["BTN_ADD_CURVE"] = d["BTN_ADD_CURVE"]
    globals()["BTN_DRAW"] = d["BTN_DRAW"]
    globals()["BTN_DONE_DRAWING"] = d["BTN_DONE_DRAWING"]
    globals()["BTN_CLEAR"] = d["BTN_CLEAR"]
    globals()["BTN_RESET"] = d["BTN_RESET"]
    globals()["BTN_GENERATE"] = d["BTN_GENERATE"]
    globals()["BTN_PARAMS"] = d["BTN_PARAMS"]
    globals()["BTN_EDIT"] = d["BTN_EDIT"]
    globals()["BTN_DEL"] = d["BTN_DEL"]
    globals()["BLEND_PARAMS_TITLE"] = d["BLEND_PARAMS_TITLE"]
    globals()["BLEND_TANGENT"] = d["BLEND_TANGENT"]
    globals()["BLEND_NORMAL"] = d["BLEND_NORMAL"]
    globals()["BLEND_DECAY"] = d["BLEND_DECAY"]
    globals()["BLEND_RADIUS"] = d["BLEND_RADIUS"]
    globals()["BLEND_HINT"] = d["BLEND_HINT"]
    globals()["SCALAR_PARAMS_TITLE"] = d["SCALAR_PARAMS_TITLE"]
    globals()["SCALAR_METHOD"] = d["SCALAR_METHOD"]
    globals()["SCALAR_STEP"] = d["SCALAR_STEP"]
    globals()["SCALAR_COUNT"] = d["SCALAR_COUNT"]
    globals()["SCALAR_CENTER_X"] = d["SCALAR_CENTER_X"]
    globals()["SCALAR_CENTER_Y"] = d["SCALAR_CENTER_Y"]
    globals()["SCALAR_SIGMA"] = d["SCALAR_SIGMA"]
    globals()["OFFSET_HINT"] = d["OFFSET_HINT"]
    globals()["MULTI_SEED_HINT"] = d["MULTI_SEED_HINT"]
    globals()["CURVE_PARAMS_HINT"] = d["CURVE_PARAMS_HINT"]
    globals()["CURVE_SELECT_HINT"] = d["CURVE_SELECT_HINT"]
    globals()["LINE_SPACING_SHORT"] = d["LINE_SPACING_SHORT"]
    globals()["POS_NEG"] = d["POS_NEG"]
    globals()["OFFSET_XY"] = d["OFFSET_XY"]
    globals()["SPACING_MODE_SHORT"] = d["SPACING_MODE_SHORT"]
    globals()["SPACING_SCALE_SHORT"] = d["SPACING_SCALE_SHORT"]
    globals()["CROSS_SPACING_SHORT"] = d["CROSS_SPACING_SHORT"]
    globals()["NOISE_ENABLED"] = d["NOISE_ENABLED"]
    globals()["ROADS_PERP"] = d["ROADS_PERP"]
    globals()["ROAD_HIERARCHY"] = d["ROAD_HIERARCHY"]
    globals()["ADAPTIVE_CROSS"] = d["ADAPTIVE_CROSS"]
    globals()["CURVATURE_WEIGHT"] = d["CURVATURE_WEIGHT"]
    globals()["ATTRACTOR_WEIGHT"] = d["ATTRACTOR_WEIGHT"]
    globals()["VALUE_WEIGHT"] = d["VALUE_WEIGHT"]
    globals()["PARCEL_FRONTAGE_BASED"] = d["PARCEL_FRONTAGE_BASED"]
    globals()["PARCEL_BLOCK_BY_BLOCK"] = d["PARCEL_BLOCK_BY_BLOCK"]
    globals()["PARCEL_CORNER_SEPARATE"] = d["PARCEL_CORNER_SEPARATE"]
    globals()["PARCEL_PERTURBATION"] = d["PARCEL_PERTURBATION"]
    globals()["PARCEL_PERTURBATION_STR"] = d["PARCEL_PERTURBATION_STR"]
    globals()["NO_CURVES_YET"] = d["NO_CURVES_YET"]
    globals()["DRAW_MODE_STATUS"] = d["DRAW_MODE_STATUS"]
    globals()["BASIS_BLEND_FACTOR"] = d["BASIS_BLEND_FACTOR"]
    globals()["RIVER_BOUNDARY_TITLE"] = d["RIVER_BOUNDARY_TITLE"]
    globals()["USE_RIVER_BOUNDARY"] = d["USE_RIVER_BOUNDARY"]
    globals()["BOUNDARY_DECAY"] = d["BOUNDARY_DECAY"]
    globals()["BOUNDARY_BLEND"] = d["BOUNDARY_BLEND"]
    globals()["TENSOR_CENTER_TITLE"] = d["TENSOR_CENTER_TITLE"]
    globals()["TENSOR_CENTER_X"] = d["TENSOR_CENTER_X"]
    globals()["TENSOR_CENTER_Y"] = d["TENSOR_CENTER_Y"]
    globals()["BTN_DRAW_RIVER"] = d["BTN_DRAW_RIVER"]
    globals()["BTN_ADD_CENTER"] = d["BTN_ADD_CENTER"]
    globals()["BTN_CLEAR_CENTERS"] = d["BTN_CLEAR_CENTERS"]
    globals()["TENSOR_CENTER_HINT"] = d["TENSOR_CENTER_HINT"]
    globals()["HEIGHT_FIELD_TITLE"] = d["HEIGHT_FIELD_TITLE"]
    globals()["USE_HEIGHT_FIELD"] = d["USE_HEIGHT_FIELD"]
    globals()["BTN_LOAD_HEIGHT"] = d["BTN_LOAD_HEIGHT"]
    globals()["BTN_CLEAR_HEIGHT"] = d["BTN_CLEAR_HEIGHT"]
    globals()["HEIGHT_BLEND"] = d["HEIGHT_BLEND"]
    globals()["HYPERSTREAMLINE_TITLE"] = d["HYPERSTREAMLINE_TITLE"]
    globals()["HYPERSTREAMLINE_MAJOR"] = d["HYPERSTREAMLINE_MAJOR"]
    globals()["HYPERSTREAMLINE_MINOR"] = d["HYPERSTREAMLINE_MINOR"]
    globals()["HYPERSTREAMLINE_BOTH"] = d["HYPERSTREAMLINE_BOTH"]
    globals()["BTN_ADD_SEED"] = d["BTN_ADD_SEED"]
    globals()["BTN_CLEAR_SEEDS"] = d["BTN_CLEAR_SEEDS"]
    globals()["HYPER_STEP_SIZE"] = d["HYPER_STEP_SIZE"]
    globals()["HYPER_MAX_LENGTH"] = d["HYPER_MAX_LENGTH"]
    globals()["HYPER_ANGLE_STOP"] = d["HYPER_ANGLE_STOP"]
    globals()["PAPER_OPTIONS"] = d["PAPER_OPTIONS"]
    globals()["STREET_GEN_MODE"] = d["STREET_GEN_MODE"]
    globals()["STREET_PARAM"] = d["STREET_PARAM"]
    globals()["STREET_HYPER"] = d["STREET_HYPER"]
    globals()["TWO_STAGE"] = d["TWO_STAGE"]
    globals()["PERLIN_ROTATION"] = d["PERLIN_ROTATION"]
    globals()["PERLIN_STRENGTH"] = d["PERLIN_STRENGTH"]
    globals()["LAPLACIAN_SMOOTH"] = d["LAPLACIAN_SMOOTH"]
    globals()["LAPLACIAN_ITERS"] = d["LAPLACIAN_ITERS"]
    globals()["BTN_DRAW_BRUSH"] = d["BTN_DRAW_BRUSH"]
    globals()["BTN_CLEAR_BRUSH"] = d["BTN_CLEAR_BRUSH"]
    globals()["BRUSH_HINT"] = d["BRUSH_HINT"]


# --- English ---
_LANG_EN = {
    "T": {
        "title": "Urban Field Gen",
        "subtitle": "V.1.0 LINE-DRIVEN ENGINE",
        "section_run_mode": "RUN MODE & SITE",
        "section_field_logic": "FIELD LOGIC",
        "section_seed_line": "SEED LINE",
        "section_multi_seed": "MULTI SEED LINES",
        "section_curve_params": "CURVE VECTOR PARAMS",
        "section_expansion": "EXPANSION PARAMETERS",
        "section_noise": "NOISE & DISTORTION",
        "section_street": "STREET & PARCEL (B/C)",
        "run_mode": "Run Mode",
        "site_width": "Site Width",
        "site_height": "Site Height",
        "engine": "Engine",
        "field_type": "Field Type",
        "basis_type": "Tensor Basis",
        "seed_type": "Seed Line Type",
        "seed_rotation": "Seed Rotation",
        "seed_x_offset": "Seed X Offset",
        "seed_y_offset": "Seed Y Offset",
        "seed_length": "Seed Length",
        "sine_amplitude": "Sine Amplitude",
        "arc_curvature": "Arc Curvature",
        "line_spacing": "Line Spacing",
        "pos_count": "Pos. Count",
        "neg_count": "Neg. Count",
        "spacing_mode": "Spacing Mode",
        "spacing_scale": "Spacing Scale",
        "noise_scale": "Noise Scale",
        "noise_strength": "Noise Strength",
        "cross_spacing": "Cross Road Spacing",
        "parcel_min": "Min Frontage",
        "parcel_max": "Max Frontage",
        "parcel_min_area": "Min Area",
        "parcel_max_depth": "Max Depth",
        "parcel_depth": "Parcel Depth Offset",
        "export_rhino": "Export for Rhino",
        "export_py": "Export .py (RhinoScript)",
        "export_dxf": "Export DXF",
        "footer": "Non-Radial Field Generator\nUrban Morphology Study Tool",
        "status_default": "COORD_SYSTEM: CARTESIAN\nEXPANSION_VECTOR: LINE_LOCAL_NORMAL\nSTATUS: REALTIME_CALCULATION",
        "status_view_hint": "Scroll: zoom | Right-drag: pan | Double-click: reset view",
        "status_narrow_radial_hint": "Narrow site + Radial: many lines get clipped. Use Blend or smaller lineSpacing for more visible lines.",
    },
    "RUN_MODE_OPTS": ["A - Flow Lines", "B - Street Network", "C - Parcel Blocks", "D - Hyperstreamlines"],
    "ENGINE_OPTS": ["A. Offset", "B. Blended", "C. Scalar+Streamline"],
    "FIELD_TYPE_OPTS": [
        "1. Parallel Offset", "2. Curve Tangent", "3. Curve Normal", "4. Distance Contour",
        "5. Strip Growth", "6. Hybrid Tangent-Normal", "7. Noise-Modified Line Field",
    ],
    "BASIS_TYPE_OPTS": ["Grid Basis", "Radial Basis", "Blend", "Boundary", "Boundary+Grid", "Height", "Height+Grid"],
    "SEED_TYPE_OPTS": ["Straight Line", "Sine Wave", "Arc / Curve", "Custom (Hand-drawn)"],
    "SPACING_MODE_OPTS": ["Linear", "Exponential Expansion", "Fibonacci Series"],
    "CURVE_SPACING_MODES": {"Linear": "linear", "Exponential Expansion": "exponential", "Fibonacci Series": "fibonacci"},
    "INTEGRATE_METHOD_OPTS": ["Euler", "RK4"],
    "BTN_ADD_CURVE": "+ Add Curve",
    "BTN_DRAW": "Draw / Edit",
    "BTN_DONE_DRAWING": "Done Drawing",
    "BTN_CLEAR": "Clear All",
    "BTN_RESET": "Reset",
    "BTN_GENERATE": "Generate",
    "BTN_PARAMS": "Params",
    "BTN_EDIT": "Edit",
    "BTN_DEL": "Del",
    "BLEND_PARAMS_TITLE": "Blended Params",
    "BLEND_TANGENT": "Tangent Weight",
    "BLEND_NORMAL": "Normal Weight",
    "BLEND_DECAY": "Distance Decay",
    "BLEND_RADIUS": "Decay Radius",
    "BLEND_HINT": "Select Custom and add multiple curves",
    "SCALAR_PARAMS_TITLE": "Scalar Streamline Params",
    "SCALAR_METHOD": "Integration Method",
    "SCALAR_STEP": "Step Size",
    "SCALAR_COUNT": "Streamline Count",
    "SCALAR_CENTER_X": "Land Price Center X",
    "SCALAR_CENTER_Y": "Land Price Center Y",
    "SCALAR_SIGMA": "Land Price Spread σ",
    "OFFSET_HINT": "Use Field Type below for offset mode",
    "BASIS_BLEND_FACTOR": "Blend Factor (0=Grid, 1=Radial)",
    "RIVER_BOUNDARY_TITLE": "River / Boundary",
    "USE_RIVER_BOUNDARY": "Use River Boundary",
    "RIVER_FROM_CURVE": "From first curve",
    "RIVER_FROM_IMAGE": "Load mask image",
    "BOUNDARY_DECAY": "Boundary Decay",
    "BOUNDARY_BLEND": "Boundary Blend (0=Grid, 1=Boundary)",
    "TENSOR_CENTER_TITLE": "Tensor Center",
    "TENSOR_CENTER_X": "Center X",
    "TENSOR_CENTER_Y": "Center Y",
    "BTN_ADD_CENTER": "Add Center",
    "BTN_CLEAR_CENTERS": "Clear Centers",
    "TENSOR_CENTER_HINT": "Click to add, drag to move",
    "BTN_DRAW_RIVER": "Draw River",
    "HEIGHT_FIELD_TITLE": "Height / Elevation",
    "USE_HEIGHT_FIELD": "Use Height Map",
    "BTN_LOAD_HEIGHT": "Load Height Map",
    "BTN_CLEAR_HEIGHT": "Clear",
    "HEIGHT_BLEND": "Height Blend (0=Grid, 1=Height)",
    "MULTI_SEED_HINT": "Select Custom to add multiple curves, each can be hand-drawn",
    "CURVE_PARAMS_HINT": "Select a curve in list to adjust its vector params",
    "CURVE_SELECT_HINT": "(Click Params in list to select curve)",
    "LINE_SPACING_SHORT": "Line Spacing",
    "POS_NEG": "Pos. / Neg.",
    "OFFSET_XY": "Offset X/Y",
    "SPACING_MODE_SHORT": "Spacing Mode",
    "SPACING_SCALE_SHORT": "Spacing Scale",
    "CROSS_SPACING_SHORT": "Road Density",
    "NOISE_ENABLED": "Enable Noise Distortion",
    "ROADS_PERP": "Roads ⊥ Vector Lines",
    "ROAD_HIERARCHY": "Road Hierarchy (Primary/Secondary/Local)",
    "ADAPTIVE_CROSS": "Adaptive Cross Streets",
    "CURVATURE_WEIGHT": "Curvature Weight",
    "ATTRACTOR_WEIGHT": "Attractor Weight",
    "VALUE_WEIGHT": "Value Weight",
    "PARCEL_FRONTAGE_BASED": "Frontage-based Subdivision",
    "PARCEL_BLOCK_BY_BLOCK": "Block-by-Block",
    "PARCEL_CORNER_SEPARATE": "Corner Parcels Separate",
    "PARCEL_PERTURBATION": "Irregular Perturbation",
    "PARCEL_PERTURBATION_STR": "Perturbation Strength",
    "NO_CURVES_YET": "(No curves yet. Click + Add Curve)",
    "DRAW_MODE_STATUS": "DRAW MODE: Curve {} - Click to add points, drag to move",
    "HYPERSTREAMLINE_TITLE": "Hyperstreamlines",
    "HYPERSTREAMLINE_MAJOR": "Major (u)",
    "HYPERSTREAMLINE_MINOR": "Minor (v)",
    "HYPERSTREAMLINE_BOTH": "Both",
    "BTN_ADD_SEED": "Add Seed Points",
    "BTN_CLEAR_SEEDS": "Clear Seeds",
    "HYPER_STEP_SIZE": "Step Size",
    "HYPER_MAX_LENGTH": "Max Length (0=off)",
    "HYPER_ANGLE_STOP": "Angle Stop (cos)",
    "PAPER_OPTIONS": "Paper-Style Options",
    "STREET_GEN_MODE": "Street Gen",
    "STREET_PARAM": "Parametric",
    "STREET_HYPER": "Hyperstreamline",
    "TWO_STAGE": "Two-Stage (Major→Minor)",
    "PERLIN_ROTATION": "Perlin Rotation",
    "PERLIN_STRENGTH": "Perlin Strength",
    "LAPLACIAN_SMOOTH": "Laplacian Smooth",
    "LAPLACIAN_ITERS": "Smooth Iterations",
    "BTN_DRAW_BRUSH": "Draw Brush",
    "BTN_CLEAR_BRUSH": "Clear Brush",
    "BRUSH_HINT": "Draw curves to orient tensor",
}

# --- 中文 ---
_LANG_ZH = {
    "T": {
        "title": "城市线驱动向量场生成器",
        "subtitle": "V.1.0 线驱动引擎",
        "section_run_mode": "运行模式与场地",
        "section_field_logic": "场逻辑",
        "section_seed_line": "种子线",
        "section_multi_seed": "多种子线",
        "section_curve_params": "曲线向量参数",
        "section_expansion": "扩张参数",
        "section_noise": "噪声与扰动",
        "section_street": "街道与地块 (B/C)",
        "run_mode": "运行模式",
        "site_width": "场地宽度",
        "site_height": "场地高度",
        "engine": "引擎",
        "field_type": "场类型",
        "basis_type": "张量基底",
        "seed_type": "种子线类型",
        "seed_rotation": "种子旋转",
        "seed_x_offset": "种子 X 偏移",
        "seed_y_offset": "种子 Y 偏移",
        "seed_length": "种子长度",
        "sine_amplitude": "正弦振幅",
        "arc_curvature": "弧线曲率",
        "line_spacing": "线间距",
        "pos_count": "正向数量",
        "neg_count": "负向数量",
        "spacing_mode": "间距模式",
        "spacing_scale": "间距缩放",
        "noise_scale": "噪声尺度",
        "noise_strength": "噪声强度",
        "cross_spacing": "横街间距",
        "parcel_min": "最小面宽",
        "parcel_max": "最大面宽",
        "parcel_min_area": "最小面积",
        "parcel_max_depth": "最大进深",
        "parcel_depth": "地块进深偏移",
        "export_rhino": "导出到 Rhino",
        "export_py": "导出 .py (RhinoScript)",
        "export_dxf": "导出 DXF",
        "footer": "非径向向量场生成器\n城市形态学研究工具",
        "status_default": "坐标系: 笛卡尔\n扩张向量: 线局部法向\n状态: 实时计算",
        "status_view_hint": "滚轮: 缩放 | 右键拖动: 平移 | 双击: 重置视图",
        "status_narrow_radial_hint": "窄场地+纯径向基底会导致很多线被裁剪，若想得到更多可见线，建议使用 Blend 或减小 lineSpacing。",
    },
    "RUN_MODE_OPTS": ["A - 流线", "B - 街道网络", "C - 地块", "D - 超流线"],
    "ENGINE_OPTS": ["A. 偏移", "B. 混合", "C. 标量+流线"],
    "FIELD_TYPE_OPTS": [
        "1. 平行偏移", "2. 曲线切向", "3. 曲线法向", "4. 距离等高线",
        "5. 条带生长", "6. 混合切向-法向", "7. 噪声修正线场",
    ],
    "BASIS_TYPE_OPTS": ["网格基底", "径向基底", "混合", "边界", "边界+网格", "高程", "高程+网格"],
    "SEED_TYPE_OPTS": ["直线", "正弦波", "弧线/曲线", "自定义（手绘）"],
    "SPACING_MODE_OPTS": ["线性", "指数扩张", "斐波那契"],
    "CURVE_SPACING_MODES": {"线性": "linear", "指数扩张": "exponential", "斐波那契": "fibonacci"},
    "INTEGRATE_METHOD_OPTS": ["Euler", "RK4"],
    "BTN_ADD_CURVE": "+ 添加曲线",
    "BTN_DRAW": "绘制 / 编辑",
    "BTN_DONE_DRAWING": "完成绘制",
    "BTN_CLEAR": "清空全部",
    "BTN_RESET": "重置",
    "BTN_GENERATE": "生成",
    "BTN_PARAMS": "参数",
    "BTN_EDIT": "编辑",
    "BTN_DEL": "删除",
    "BLEND_PARAMS_TITLE": "混合参数",
    "BLEND_TANGENT": "切向权重",
    "BLEND_NORMAL": "法向权重",
    "BLEND_DECAY": "距离衰减",
    "BLEND_RADIUS": "衰减半径",
    "BLEND_HINT": "选择自定义并添加多条曲线",
    "SCALAR_PARAMS_TITLE": "标量流线参数",
    "SCALAR_METHOD": "积分方法",
    "SCALAR_STEP": "步长",
    "SCALAR_COUNT": "流线数量",
    "SCALAR_CENTER_X": "地价中心 X",
    "SCALAR_CENTER_Y": "地价中心 Y",
    "SCALAR_SIGMA": "地价扩散 σ",
    "OFFSET_HINT": "偏移模式请使用下方场类型",
    "BASIS_BLEND_FACTOR": "混合因子 (0=网格, 1=径向)",
    "RIVER_BOUNDARY_TITLE": "河流 / 边界",
    "USE_RIVER_BOUNDARY": "使用河流边界",
    "RIVER_FROM_CURVE": "来自首条曲线",
    "RIVER_FROM_IMAGE": "加载遮罩图像",
    "BOUNDARY_DECAY": "边界衰减",
    "BOUNDARY_BLEND": "边界混合 (0=网格, 1=边界)",
    "TENSOR_CENTER_TITLE": "张量中心",
    "TENSOR_CENTER_X": "中心 X",
    "TENSOR_CENTER_Y": "中心 Y",
    "BTN_ADD_CENTER": "添加中心",
    "BTN_CLEAR_CENTERS": "清除中心",
    "TENSOR_CENTER_HINT": "点击添加，拖动移动",
    "BTN_DRAW_RIVER": "绘制河流",
    "HEIGHT_FIELD_TITLE": "高程 / 地形",
    "USE_HEIGHT_FIELD": "使用高程图",
    "BTN_LOAD_HEIGHT": "加载高程图",
    "BTN_CLEAR_HEIGHT": "清除",
    "HEIGHT_BLEND": "高程混合 (0=网格, 1=高程)",
    "MULTI_SEED_HINT": "选择自定义以添加多条曲线，可手绘",
    "CURVE_PARAMS_HINT": "在列表中选中曲线以调整其向量参数",
    "CURVE_SELECT_HINT": "（点击列表中参数按钮选择曲线）",
    "LINE_SPACING_SHORT": "线间距",
    "POS_NEG": "正向 / 负向",
    "OFFSET_XY": "偏移 X/Y",
    "SPACING_MODE_SHORT": "间距模式",
    "SPACING_SCALE_SHORT": "间距缩放",
    "CROSS_SPACING_SHORT": "道路密度",
    "NOISE_ENABLED": "启用噪声扰动",
    "ROADS_PERP": "道路 ⊥ 向量线",
    "ROAD_HIERARCHY": "道路等级（主/次/支）",
    "ADAPTIVE_CROSS": "自适应横街",
    "CURVATURE_WEIGHT": "曲率权重",
    "ATTRACTOR_WEIGHT": "吸引子权重",
    "VALUE_WEIGHT": "价值权重",
    "PARCEL_FRONTAGE_BASED": "临街面切分",
    "PARCEL_BLOCK_BY_BLOCK": "按块切分",
    "PARCEL_CORNER_SEPARATE": "转角地块单独",
    "PARCEL_PERTURBATION": "不规则扰动",
    "PARCEL_PERTURBATION_STR": "扰动强度",
    "NO_CURVES_YET": "（暂无曲线，点击 + 添加曲线）",
    "DRAW_MODE_STATUS": "绘制模式：曲线 {} - 点击添加点，拖动移动",
    "BASIS_BLEND_FACTOR": "混合因子 (0=网格, 1=径向)",
    "HYPERSTREAMLINE_TITLE": "超流线",
    "HYPERSTREAMLINE_MAJOR": "主 (u)",
    "HYPERSTREAMLINE_MINOR": "副 (v)",
    "HYPERSTREAMLINE_BOTH": "主+副",
    "BTN_ADD_SEED": "添加种子点",
    "BTN_CLEAR_SEEDS": "清除种子",
    "HYPER_STEP_SIZE": "步长",
    "HYPER_MAX_LENGTH": "最大长度 (0=不限)",
    "HYPER_ANGLE_STOP": "角度停止 (cos)",
    "PAPER_OPTIONS": "论文式选项",
    "STREET_GEN_MODE": "街道生成",
    "STREET_PARAM": "参数化",
    "STREET_HYPER": "超流线",
    "TWO_STAGE": "二阶段 (主路→次路)",
    "PERLIN_ROTATION": "Perlin 旋转",
    "PERLIN_STRENGTH": "Perlin 强度",
    "LAPLACIAN_SMOOTH": "Laplacian 平滑",
    "LAPLACIAN_ITERS": "平滑迭代",
    "BTN_DRAW_BRUSH": "绘制笔刷",
    "BTN_CLEAR_BRUSH": "清除笔刷",
    "BRUSH_HINT": "绘制曲线设定张量方向",
}

# Initialize with English
T = dict(_LANG_EN["T"])
RUN_MODE_OPTS = list(_LANG_EN["RUN_MODE_OPTS"])
ENGINE_OPTS = list(_LANG_EN["ENGINE_OPTS"])
FIELD_TYPE_OPTS = list(_LANG_EN["FIELD_TYPE_OPTS"])
BASIS_TYPE_OPTS = list(_LANG_EN["BASIS_TYPE_OPTS"])
SEED_TYPE_OPTS = list(_LANG_EN["SEED_TYPE_OPTS"])
SPACING_MODE_OPTS = list(_LANG_EN["SPACING_MODE_OPTS"])
CURVE_SPACING_MODES = dict(_LANG_EN["CURVE_SPACING_MODES"])
INTEGRATE_METHOD_OPTS = list(_LANG_EN["INTEGRATE_METHOD_OPTS"])

BTN_ADD_CURVE = _LANG_EN["BTN_ADD_CURVE"]
BTN_DRAW = _LANG_EN["BTN_DRAW"]
BTN_DONE_DRAWING = _LANG_EN["BTN_DONE_DRAWING"]
BTN_CLEAR = _LANG_EN["BTN_CLEAR"]
BTN_RESET = _LANG_EN["BTN_RESET"]
BTN_GENERATE = _LANG_EN["BTN_GENERATE"]
BTN_PARAMS = _LANG_EN["BTN_PARAMS"]
BTN_EDIT = _LANG_EN["BTN_EDIT"]
BTN_DEL = _LANG_EN["BTN_DEL"]
BLEND_PARAMS_TITLE = _LANG_EN["BLEND_PARAMS_TITLE"]
BLEND_TANGENT = _LANG_EN["BLEND_TANGENT"]
BLEND_NORMAL = _LANG_EN["BLEND_NORMAL"]
BLEND_DECAY = _LANG_EN["BLEND_DECAY"]
BLEND_RADIUS = _LANG_EN["BLEND_RADIUS"]
BLEND_HINT = _LANG_EN["BLEND_HINT"]
SCALAR_PARAMS_TITLE = _LANG_EN["SCALAR_PARAMS_TITLE"]
SCALAR_METHOD = _LANG_EN["SCALAR_METHOD"]
SCALAR_STEP = _LANG_EN["SCALAR_STEP"]
SCALAR_COUNT = _LANG_EN["SCALAR_COUNT"]
SCALAR_CENTER_X = _LANG_EN["SCALAR_CENTER_X"]
SCALAR_CENTER_Y = _LANG_EN["SCALAR_CENTER_Y"]
SCALAR_SIGMA = _LANG_EN["SCALAR_SIGMA"]
OFFSET_HINT = _LANG_EN["OFFSET_HINT"]
BASIS_BLEND_FACTOR = _LANG_EN["BASIS_BLEND_FACTOR"]
RIVER_BOUNDARY_TITLE = _LANG_EN["RIVER_BOUNDARY_TITLE"]
USE_RIVER_BOUNDARY = _LANG_EN["USE_RIVER_BOUNDARY"]
BOUNDARY_DECAY = _LANG_EN["BOUNDARY_DECAY"]
BOUNDARY_BLEND = _LANG_EN["BOUNDARY_BLEND"]
TENSOR_CENTER_TITLE = _LANG_EN["TENSOR_CENTER_TITLE"]
TENSOR_CENTER_X = _LANG_EN["TENSOR_CENTER_X"]
TENSOR_CENTER_Y = _LANG_EN["TENSOR_CENTER_Y"]
BTN_DRAW_RIVER = _LANG_EN["BTN_DRAW_RIVER"]
BTN_ADD_CENTER = _LANG_EN["BTN_ADD_CENTER"]
BTN_CLEAR_CENTERS = _LANG_EN["BTN_CLEAR_CENTERS"]
TENSOR_CENTER_HINT = _LANG_EN["TENSOR_CENTER_HINT"]
HEIGHT_FIELD_TITLE = _LANG_EN["HEIGHT_FIELD_TITLE"]
USE_HEIGHT_FIELD = _LANG_EN["USE_HEIGHT_FIELD"]
BTN_LOAD_HEIGHT = _LANG_EN["BTN_LOAD_HEIGHT"]
BTN_CLEAR_HEIGHT = _LANG_EN["BTN_CLEAR_HEIGHT"]
HEIGHT_BLEND = _LANG_EN["HEIGHT_BLEND"]
HYPERSTREAMLINE_TITLE = _LANG_EN["HYPERSTREAMLINE_TITLE"]
HYPERSTREAMLINE_MAJOR = _LANG_EN["HYPERSTREAMLINE_MAJOR"]
HYPERSTREAMLINE_MINOR = _LANG_EN["HYPERSTREAMLINE_MINOR"]
HYPERSTREAMLINE_BOTH = _LANG_EN["HYPERSTREAMLINE_BOTH"]
BTN_ADD_SEED = _LANG_EN["BTN_ADD_SEED"]
BTN_CLEAR_SEEDS = _LANG_EN["BTN_CLEAR_SEEDS"]
HYPER_STEP_SIZE = _LANG_EN["HYPER_STEP_SIZE"]
HYPER_MAX_LENGTH = _LANG_EN["HYPER_MAX_LENGTH"]
HYPER_ANGLE_STOP = _LANG_EN["HYPER_ANGLE_STOP"]
PAPER_OPTIONS = _LANG_EN["PAPER_OPTIONS"]
STREET_GEN_MODE = _LANG_EN["STREET_GEN_MODE"]
STREET_PARAM = _LANG_EN["STREET_PARAM"]
STREET_HYPER = _LANG_EN["STREET_HYPER"]
TWO_STAGE = _LANG_EN["TWO_STAGE"]
PERLIN_ROTATION = _LANG_EN["PERLIN_ROTATION"]
PERLIN_STRENGTH = _LANG_EN["PERLIN_STRENGTH"]
LAPLACIAN_SMOOTH = _LANG_EN["LAPLACIAN_SMOOTH"]
LAPLACIAN_ITERS = _LANG_EN["LAPLACIAN_ITERS"]
BTN_DRAW_BRUSH = _LANG_EN["BTN_DRAW_BRUSH"]
BTN_CLEAR_BRUSH = _LANG_EN["BTN_CLEAR_BRUSH"]
BRUSH_HINT = _LANG_EN["BRUSH_HINT"]
MULTI_SEED_HINT = _LANG_EN["MULTI_SEED_HINT"]
CURVE_PARAMS_HINT = _LANG_EN["CURVE_PARAMS_HINT"]
CURVE_SELECT_HINT = _LANG_EN["CURVE_SELECT_HINT"]
LINE_SPACING_SHORT = _LANG_EN["LINE_SPACING_SHORT"]
POS_NEG = _LANG_EN["POS_NEG"]
OFFSET_XY = _LANG_EN["OFFSET_XY"]
SPACING_MODE_SHORT = _LANG_EN["SPACING_MODE_SHORT"]
SPACING_SCALE_SHORT = _LANG_EN["SPACING_SCALE_SHORT"]
CROSS_SPACING_SHORT = _LANG_EN["CROSS_SPACING_SHORT"]
NOISE_ENABLED = _LANG_EN["NOISE_ENABLED"]
ROADS_PERP = _LANG_EN["ROADS_PERP"]
ROAD_HIERARCHY = _LANG_EN["ROAD_HIERARCHY"]
ADAPTIVE_CROSS = _LANG_EN["ADAPTIVE_CROSS"]
CURVATURE_WEIGHT = _LANG_EN["CURVATURE_WEIGHT"]
ATTRACTOR_WEIGHT = _LANG_EN["ATTRACTOR_WEIGHT"]
VALUE_WEIGHT = _LANG_EN["VALUE_WEIGHT"]
PARCEL_FRONTAGE_BASED = _LANG_EN["PARCEL_FRONTAGE_BASED"]
PARCEL_BLOCK_BY_BLOCK = _LANG_EN["PARCEL_BLOCK_BY_BLOCK"]
PARCEL_CORNER_SEPARATE = _LANG_EN["PARCEL_CORNER_SEPARATE"]
PARCEL_PERTURBATION = _LANG_EN["PARCEL_PERTURBATION"]
PARCEL_PERTURBATION_STR = _LANG_EN["PARCEL_PERTURBATION_STR"]
NO_CURVES_YET = _LANG_EN["NO_CURVES_YET"]
DRAW_MODE_STATUS = _LANG_EN["DRAW_MODE_STATUS"]


def curve_n_params(n):
    if _current_lang == "zh":
        return f"曲线 {n} 向量参数"
    return f"Curve {n} Vector Params"


def curve_n_pts(i, n):
    if _current_lang == "zh":
        return f"曲线 {i}（{n} 点）"
    return f"Curve {i} ({n} pts)"
