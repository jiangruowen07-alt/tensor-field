"""
城市线驱动向量场生成器
核心逻辑：基于 Seed Curve 的非中心式扩张
Python 重写版本 - 逻辑完全一致
优化版：预计算、缓存、减少冗余运算
"""

import tkinter as tk
from tkinter import ttk, filedialog
import math
import random

# 采样步长：t 从 0 到 1 的步进，固定为 1/50 以支持直接索引
T_STEP = 0.02
T_COUNT = 51  # int(1 / T_STEP) + 1


def lerp(a, b, t):
    return a + (b - a) * t


def noise(x, y):
    """简易噪声函数 (Lattice Noise)"""
    return (math.sin(x * 0.01) * math.cos(y * 0.01) + math.sin(x * 0.02 + y * 0.015)) * 0.5


def _inside(p, xmin, ymin, xmax, ymax):
    """点是否在矩形内"""
    return xmin <= p[0] <= xmax and ymin <= p[1] <= ymax


def _clip_segment_to_rect(p0, p1, xmin, ymin, xmax, ymax):
    """Cohen-Sutherland 线段裁剪，返回裁剪后的线段 [(x,y),(x,y)] 或 None，顺序与 p0->p1 一致"""
    x0, y0 = p0
    x1, y1 = p1
    orig_p0 = p0
    LEFT, RIGHT, BOTTOM, TOP = 1, 2, 4, 8

    def code(x, y):
        c = 0
        if x < xmin:
            c |= LEFT
        elif x > xmax:
            c |= RIGHT
        if y < ymin:
            c |= BOTTOM
        elif y > ymax:
            c |= TOP
        return c

    c0, c1 = code(x0, y0), code(x1, y1)
    while True:
        if c0 == 0 and c1 == 0:
            a, b = (x0, y0), (x1, y1)
            # 保证顺序与 p0->p1 一致（a 靠近 p0）
            d_a = (a[0] - orig_p0[0]) ** 2 + (a[1] - orig_p0[1]) ** 2
            d_b = (b[0] - orig_p0[0]) ** 2 + (b[1] - orig_p0[1]) ** 2
            if d_a > d_b:
                a, b = b, a
            return [a, b]
        if c0 & c1:
            return None
        if c0 == 0:
            x0, y0, x1, y1, c0, c1 = x1, y1, x0, y0, c1, c0
        c = c0
        if c & LEFT:
            y0 = y0 + (y1 - y0) * (xmin - x0) / (x1 - x0) if x1 != x0 else y0
            x0 = xmin
        elif c & RIGHT:
            y0 = y0 + (y1 - y0) * (xmax - x0) / (x1 - x0) if x1 != x0 else y0
            x0 = xmax
        elif c & BOTTOM:
            x0 = x0 + (x1 - x0) * (ymin - y0) / (y1 - y0) if y1 != y0 else x0
            y0 = ymin
        elif c & TOP:
            x0 = x0 + (x1 - x0) * (ymax - y0) / (y1 - y0) if y1 != y0 else x0
            y0 = ymax
        c0 = code(x0, y0)


def _same_pt(a, b, tol=1e-10):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def _clip_polyline_to_rect(pts, xmin, ymin, xmax, ymax):
    """折线裁剪到矩形，返回裁剪后的折线列表（可能被裁成多段）"""
    if len(pts) < 2:
        return []
    result = []
    current = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        seg = _clip_segment_to_rect(p0, p1, xmin, ymin, xmax, ymax)
        if seg is None:
            if current:
                result.append(current)
                current = []
            continue
        a, b = seg[0], seg[1]
        if not current:
            current = [a]
        elif not _same_pt(a, current[-1]):
            result.append(current)
            current = [a]
        if not _same_pt(b, a):
            current.append(b)
        if not _inside(p1, xmin, ymin, xmax, ymax):
            result.append(current)
            current = []
    if current:
        result.append(current)
    return [p for p in result if len(p) >= 2]


def _clip_polygon_to_rect(pts, xmin, ymin, xmax, ymax):
    """Sutherland-Hodgman 多边形裁剪到矩形，返回裁剪后的多边形列表"""
    if len(pts) < 3:
        return []

    def cross_inside(px, py, x1, y1, x2, y2):
        """点 (px,py) 在边 (x1,y1)->(x2,y2) 的 inside 侧（左侧）"""
        return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1) >= 0

    def intersect(p, q, x1, y1, x2, y2):
        """线段 PQ 与边 (x1,y1)->(x2,y2) 的交点"""
        px, py = p
        qx, qy = q
        dx, dy = qx - px, qy - py
        ex, ey = x2 - x1, y2 - y1
        denom = ex * dy - ey * dx
        if abs(denom) < 1e-12:
            return (px, py)
        t = (ex * (y1 - py) - ey * (x1 - px)) / denom
        t = max(0, min(1, t))
        return (px + t * dx, py + t * dy)

    def clip_edge(subject, x1, y1, x2, y2):
        out = []
        for i in range(len(subject)):
            v1 = subject[i]
            v0 = subject[(i - 1) % len(subject)]
            inside_v0 = cross_inside(v0[0], v0[1], x1, y1, x2, y2)
            inside_v1 = cross_inside(v1[0], v1[1], x1, y1, x2, y2)
            if inside_v0 and inside_v1:
                out.append(v1)
            elif inside_v0 and not inside_v1:
                out.append(intersect(v0, v1, x1, y1, x2, y2))
            elif not inside_v0 and inside_v1:
                out.append(intersect(v0, v1, x1, y1, x2, y2))
                out.append(v1)
        return out

    poly = list(pts)
    for (x1, y1, x2, y2) in [(xmin, ymin, xmax, ymin), (xmax, ymin, xmax, ymax),
                             (xmax, ymax, xmin, ymax), (xmin, ymax, xmin, ymin)]:
        poly = clip_edge(poly, x1, y1, x2, y2)
        if not poly:
            return []
    return [poly] if len(poly) >= 3 else []


class UrbanFieldGenerator:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Line-Driven Urban Field Generator")
        self.root.configure(bg="#0a0a0a")
        self.root.geometry("1400x900")

        # State
        self.state = {}
        self.controls = {}
        self.custom_seed_curves = []  # [{"points": [(x,y),...], "params": {...}}, ...]
        self.selected_curve_for_params = -1  # 当前编辑向量参数的母线索引
        self.editing_curve_index = -1  # 当前编辑的母线索引，-1 表示未选择
        self.draw_mode = False
        self.drag_curve_idx = None  # 正在拖动的控制点所属母线索引
        self.drag_point_idx = None  # 正在拖动的控制点索引
        self._canvas_custom_bound = False
        self._curve_list_frame = None  # 母线列表容器，用于动态刷新
        self._export_geometry = {"polylines": [], "parcels": []}  # 用于导出到 Rhino/DXF

        self._build_ui()
        self._bind_events()
        self.update_state()

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg="#0a0a0a")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Control Panel (scrollable)
        panel_outer = tk.Frame(main_frame, width=320, bg="#141414")
        panel_outer.pack(side=tk.LEFT, fill=tk.Y)
        panel_outer.pack_propagate(False)

        # Canvas + Scrollbar for vertical scrolling
        panel_canvas = tk.Canvas(panel_outer, bg="#141414", highlightthickness=0)
        panel_scrollbar = ttk.Scrollbar(panel_outer, orient=tk.VERTICAL, command=panel_canvas.yview)

        panel = tk.Frame(panel_canvas, bg="#141414", padx=24, pady=24)
        panel_window = panel_canvas.create_window((0, 0), window=panel, anchor="nw")

        panel_canvas.configure(yscrollcommand=panel_scrollbar.set)
        panel_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        panel_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_panel_configure(event):
            panel_canvas.configure(scrollregion=panel_canvas.bbox("all"))

        def _on_canvas_configure(event):
            panel_canvas.itemconfig(panel_window, width=event.width)

        def _on_mousewheel(event):
            panel_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        panel.bind("<Configure>", _on_panel_configure)
        panel_canvas.bind("<Configure>", _on_canvas_configure)
        # 鼠标进入控制面板时启用滚轮，离开时禁用，避免影响画布区域
        def _bind_mousewheel(event):
            panel_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mousewheel(event):
            panel_canvas.unbind_all("<MouseWheel>")
        panel_canvas.bind("<Enter>", _bind_mousewheel)
        panel_canvas.bind("<Leave>", _unbind_mousewheel)

        # Title
        tk.Label(panel, text="URBAN FIELD GEN", font=("Inter", 20, "bold"),
                 fg="#ffffff", bg="#141414").pack(anchor="w")
        tk.Label(panel, text="V.1.0 LINE-DRIVEN ENGINE", font=("JetBrains Mono", 10),
                 fg="#888888", bg="#141414").pack(anchor="w")

        # RUN MODE & SITE
        self._section_title(panel, "RUN MODE & SITE")
        self._label_group(panel, "Run Mode")
        self.controls["runMode"] = ttk.Combobox(panel, values=["A - Flow Lines", "B - Street Network", "C - Parcel Blocks"],
                                                state="readonly", width=28)
        self.controls["runMode"].set("B - Street Network")
        self.controls["runMode"].pack(fill=tk.X, pady=(0, 16))

        site_frame = tk.Frame(panel, bg="#141414")
        site_frame.pack(fill=tk.X, pady=(0, 16))
        self._label_group(panel, "Site Width")
        self.controls["siteWidth"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                             insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["siteWidth"].insert(0, "1200")
        self.controls["siteWidth"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, "Site Height")
        self.controls["siteHeight"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                               insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["siteHeight"].insert(0, "200")
        self.controls["siteHeight"].pack(fill=tk.X, pady=(0, 16))

        # FIELD LOGIC
        self._section_title(panel, "FIELD LOGIC")
        self._label_group(panel, "Field Type")
        field_opts = ["1. Parallel Offset", "2. Curve Tangent", "3. Curve Normal", "4. Distance Contour",
                     "5. Strip Growth", "6. Hybrid Tangent-Normal", "7. Noise-Modified Line Field"]
        self.controls["fieldType"] = ttk.Combobox(panel, values=field_opts, state="readonly", width=28)
        self.controls["fieldType"].set("1. Parallel Offset")
        self.controls["fieldType"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, "Seed Line Type")
        self.controls["seedType"] = ttk.Combobox(panel, values=["Straight Line", "Sine Wave", "Arc / Curve", "Custom (Hand-drawn)"],
                                                 state="readonly", width=28)
        self.controls["seedType"].set("Straight Line")
        self.controls["seedType"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, "Seed Rotation", "0°", right_key="rotVal")
        self.controls["seedRotation"] = tk.Scale(panel, from_=0, to=360, orient=tk.HORIZONTAL,
                                                  bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                  highlightthickness=0, showvalue=False)
        self.controls["seedRotation"].set(0)
        self.controls["seedRotation"].pack(fill=tk.X, pady=(0, 16))

        # 母线位置与形状
        self._section_title(panel, "SEED LINE (母线)")
        self._label_group(panel, "Seed X Offset", "0", right_key="seedXVal")
        self.controls["seedXOffset"] = tk.Scale(panel, from_=-500, to=500, orient=tk.HORIZONTAL,
                                                bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                highlightthickness=0, showvalue=False)
        self.controls["seedXOffset"].set(0)
        self.controls["seedXOffset"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, "Seed Y Offset", "0", right_key="seedYVal")
        self.controls["seedYOffset"] = tk.Scale(panel, from_=-200, to=200, orient=tk.HORIZONTAL,
                                                bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                highlightthickness=0, showvalue=False)
        self.controls["seedYOffset"].set(0)
        self.controls["seedYOffset"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, "Seed Length", "0.8", right_key="seedLenVal")
        self.controls["seedLength"] = tk.Scale(panel, from_=0.2, to=1.0, resolution=0.05, orient=tk.HORIZONTAL,
                                               bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                               highlightthickness=0, showvalue=False)
        self.controls["seedLength"].set(0.8)
        self.controls["seedLength"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, "Sine Amplitude")
        self.controls["seedSineAmp"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                                insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["seedSineAmp"].insert(0, "50")
        self.controls["seedSineAmp"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, "Arc Curvature")
        self.controls["seedArcCurv"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                                insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["seedArcCurv"].insert(0, "200")
        self.controls["seedArcCurv"].pack(fill=tk.X, pady=(0, 8))

        # 多条手绘母线
        self._section_title(panel, "MULTI SEED LINES (多条母线)")
        tk.Label(panel, text="选择 Custom 后可添加多条母线，每条均可手绘", fg="#666666", bg="#141414",
                 font=("Inter", 9)).pack(anchor="w", pady=(0, 8))
        self._curve_list_frame = tk.Frame(panel, bg="#141414")
        self._curve_list_frame.pack(fill=tk.X, pady=(0, 8))
        draw_btn_frame = tk.Frame(panel, bg="#141414")
        draw_btn_frame.pack(fill=tk.X, pady=(0, 8))
        self.controls["btnAddCurve"] = tk.Button(draw_btn_frame, text="+ Add Curve", command=self._add_new_curve,
                                                 bg="#2a4a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                                 font=("JetBrains Mono", 10))
        self.controls["btnAddCurve"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.controls["btnDraw"] = tk.Button(draw_btn_frame, text="Draw / Edit", command=self._toggle_draw_mode,
                                             bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                             font=("JetBrains Mono", 10))
        self.controls["btnDraw"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 2))
        self.controls["btnClear"] = tk.Button(draw_btn_frame, text="Clear All", command=self._clear_all_curves,
                                              bg="#1a1a1a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                              font=("JetBrains Mono", 10))
        self.controls["btnClear"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # 母线向量参数（画完后可修改）
        self._section_title(panel, "CURVE VECTOR PARAMS (母线向量参数)")
        self._curve_params_frame = tk.Frame(panel, bg="#141414")
        self._curve_params_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(self._curve_params_frame, text="选择母线后调整其向量位置、疏密等", fg="#666666", bg="#141414",
                 font=("Inter", 9)).pack(anchor="w", pady=(0, 8))
        self._curve_params_inner = tk.Frame(self._curve_params_frame, bg="#141414")
        self._curve_params_inner.pack(fill=tk.X)
        # 动态创建控件，由 _build_curve_params_ui 填充

        # EXPANSION PARAMETERS
        self._section_title(panel, "EXPANSION PARAMETERS")
        self._label_group(panel, "Line Spacing", "40", right_key="spacingVal")
        self.controls["lineSpacing"] = tk.Scale(panel, from_=10, to=100, orient=tk.HORIZONTAL,
                                                bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                highlightthickness=0, showvalue=False)
        self.controls["lineSpacing"].set(40)
        self.controls["lineSpacing"].pack(fill=tk.X, pady=(0, 16))

        count_frame = tk.Frame(panel, bg="#141414")
        count_frame.pack(fill=tk.X, pady=(0, 16))
        self._label_group(panel, "Pos. Count")
        self.controls["posCount"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                             insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["posCount"].insert(0, "10")
        self.controls["posCount"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, "Neg. Count")
        self.controls["negCount"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                             insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["negCount"].insert(0, "10")
        self.controls["negCount"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, "Spacing Mode")
        self.controls["spacingMode"] = ttk.Combobox(panel, values=["Linear", "Exponential Expansion", "Fibonacci Series"],
                                                    state="readonly", width=28)
        self.controls["spacingMode"].set("Linear")
        self.controls["spacingMode"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, "Spacing Scale", "1.0", right_key="scaleVal")
        self.controls["spacingScale"] = tk.Scale(panel, from_=0.5, to=2.0, resolution=0.1, orient=tk.HORIZONTAL,
                                                 bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                 highlightthickness=0, showvalue=False)
        self.controls["spacingScale"].set(1.0)
        self.controls["spacingScale"].pack(fill=tk.X, pady=(0, 24))

        # NOISE & DISTORTION
        self._section_title(panel, "NOISE & DISTORTION")
        self.controls["noiseEnabled"] = tk.BooleanVar(value=False)
        noise_cb = tk.Checkbutton(panel, text="Enable Noise Distortion", variable=self.controls["noiseEnabled"],
                                  command=self.update_state,
                                  bg="#141414", fg="#e0e0e0", selectcolor="#1a1a1a", activebackground="#141414",
                                  activeforeground="#e0e0e0")
        noise_cb.pack(anchor="w", pady=(0, 16))

        self._label_group(panel, "Noise Scale", "0.005", right_key="noiseScaleVal")
        self.controls["noiseScale"] = tk.Scale(panel, from_=0.001, to=0.02, resolution=0.001, orient=tk.HORIZONTAL,
                                               bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                               highlightthickness=0, showvalue=False)
        self.controls["noiseScale"].set(0.005)
        self.controls["noiseScale"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, "Noise Strength", "20", right_key="noiseStrVal")
        self.controls["noiseStrength"] = tk.Scale(panel, from_=0, to=100, orient=tk.HORIZONTAL,
                                                  bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                  highlightthickness=0, showvalue=False)
        self.controls["noiseStrength"].set(20)
        self.controls["noiseStrength"].pack(fill=tk.X, pady=(0, 24))

        # STREET & PARCEL (B/C)
        self._section_title(panel, "STREET & PARCEL (B/C)")
        self.controls["roadsPerpendicular"] = tk.BooleanVar(value=True)
        perp_cb = tk.Checkbutton(panel, text="Roads Perpendicular to Vector Lines (路网⊥向量线)",
                                 variable=self.controls["roadsPerpendicular"],
                                 command=self.update_state,
                                 bg="#141414", fg="#e0e0e0", selectcolor="#1a1a1a", activebackground="#141414",
                                 activeforeground="#e0e0e0")
        perp_cb.pack(anchor="w", pady=(0, 16))
        self._label_group(panel, "Cross Road Spacing", "80", right_key="crossVal")
        self.controls["crossSpacing"] = tk.Scale(panel, from_=40, to=300, orient=tk.HORIZONTAL,
                                                 bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                 highlightthickness=0, showvalue=False)
        self.controls["crossSpacing"].set(80)
        self.controls["crossSpacing"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, "Parcel Min")
        self.controls["pMin"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                         insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["pMin"].insert(0, "15")
        self.controls["pMin"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, "Parcel Max")
        self.controls["pMax"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                         insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["pMax"].insert(0, "45")
        self.controls["pMax"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, "Parcel Depth Offset")
        self.controls["pDepth"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                          insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["pDepth"].insert(0, "10")
        self.controls["pDepth"].pack(fill=tk.X, pady=(0, 32))

        # Buttons
        btn_frame = tk.Frame(panel, bg="#141414")
        btn_frame.pack(fill=tk.X)
        btn_reset = tk.Button(btn_frame, text="Reset", command=self._reset,
                             bg="#1a1a1a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                             font=("JetBrains Mono", 10),
                             activebackground="#ffffff", activeforeground="#0a0a0a")
        btn_reset.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        btn_gen = tk.Button(btn_frame, text="Generate", command=self.generate,
                           bg="#ffffff", fg="#0a0a0a", relief=tk.SOLID, bd=1,
                           font=("JetBrains Mono", 10, "bold"),
                           activebackground="#ffffff", activeforeground="#0a0a0a")
        btn_gen.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # Export buttons
        export_frame = tk.Frame(panel, bg="#141414")
        export_frame.pack(fill=tk.X, pady=(16, 0))
        tk.Label(export_frame, text="Export for Rhino:", fg="#888888", bg="#141414",
                 font=("Inter", 10)).pack(anchor="w")
        exp_btn_frame = tk.Frame(export_frame, bg="#141414")
        exp_btn_frame.pack(fill=tk.X, pady=(4, 0))
        btn_export_rhino = tk.Button(exp_btn_frame, text="Export .py (RhinoScript)", command=self._export_rhino,
                                    bg="#2a4a6a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                    font=("JetBrains Mono", 10))
        btn_export_rhino.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        btn_export_dxf = tk.Button(exp_btn_frame, text="Export DXF", command=self._export_dxf,
                                  bg="#2a4a6a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                  font=("JetBrains Mono", 10))
        btn_export_dxf.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        tk.Label(panel, text="Non-Radial Field Generator\nUrban Morphology Study Tool",
                 fg="#888888", bg="#141414", font=("Inter", 9)).pack(pady=(32, 0))

        # Canvas Area
        canvas_frame = tk.Frame(main_frame, bg="#050505")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=32, pady=32)

        self.canvas = tk.Canvas(canvas_frame, bg="#050505", highlightthickness=0)
        self.canvas.pack(expand=True)

        self.status_label = tk.Label(canvas_frame, text="COORD_SYSTEM: CARTESIAN\nEXPANSION_VECTOR: LINE_LOCAL_NORMAL\nSTATUS: REALTIME_CALCULATION",
                                    fg="#4d4d4d", bg="#050505", font=("JetBrains Mono", 10),
                                    justify=tk.RIGHT)
        self.status_label.place(relx=1.0, rely=1.0, anchor="se", x=-32, y=-32)

    def _section_title(self, parent, text):
        tk.Label(parent, text=text, font=("Inter", 12, "bold"), fg="#ffffff", bg="#141414").pack(anchor="w", pady=(24, 8))

    def _label_group(self, parent, left, right=None, right_key=None):
        frame = tk.Frame(parent, bg="#141414")
        frame.pack(fill=tk.X)
        tk.Label(frame, text=left, fg="#888888", bg="#141414", font=("Inter", 11)).pack(side=tk.LEFT)
        if right_key:
            lbl = tk.Label(frame, text=right or "", fg="#888888", bg="#141414", font=("Inter", 11))
            lbl.pack(side=tk.RIGHT)
            self.controls[right_key] = lbl
        elif right is not None:
            tk.Label(frame, text=right, fg="#888888", bg="#141414", font=("Inter", 11)).pack(side=tk.RIGHT)

    def _get_run_mode(self):
        val = self.controls["runMode"].get()
        if "A" in val or "Flow" in val:
            return "A"
        if "C" in val or "Parcel" in val:
            return "C"
        return "B"

    def _get_field_type(self):
        val = self.controls["fieldType"].get()
        return val[0] if val else "1"

    def _get_seed_type(self):
        val = self.controls["seedType"].get()
        if "Sine" in val:
            return "sine"
        if "Arc" in val:
            return "arc"
        if "Custom" in val or "Hand" in val:
            return "custom"
        return "straight"

    def _get_spacing_mode(self):
        val = self.controls["spacingMode"].get()
        if "Exponential" in val:
            return "exponential"
        if "Fibonacci" in val:
            return "fibonacci"
        return "linear"

    def _safe_float(self, val, default):
        try:
            return float(val) if val else default
        except (ValueError, TypeError):
            return default

    def _safe_int(self, val, default):
        try:
            return int(float(val)) if val else default
        except (ValueError, TypeError):
            return default

    def _get_curve_params_defaults(self):
        """从全局控件获取默认母线向量参数"""
        return {
            "lineSpacing": self._safe_float(self.controls["lineSpacing"].get(), 40),
            "posCount": self._safe_int(self.controls["posCount"].get(), 10),
            "negCount": self._safe_int(self.controls["negCount"].get(), 10),
            "spacingMode": self._get_spacing_mode(),
            "spacingScale": self._safe_float(self.controls["spacingScale"].get(), 1.0),
            "offsetX": 0,
            "offsetY": 0,
            "crossSpacing": self._safe_float(self.controls["crossSpacing"].get(), 80),
        }

    def _get_curve_points(self, curve):
        """获取母线控制点列表（兼容旧 list 格式）"""
        if isinstance(curve, dict):
            return curve["points"]
        return curve

    def _ensure_curve_dict(self, curve):
        """兼容旧格式：若为 list 则转为 dict 并迁移"""
        if isinstance(curve, list):
            return {"points": curve, "params": self._get_curve_params_defaults()}
        return curve

    def _add_new_curve(self):
        """添加一条新母线并进入绘制模式"""
        self.controls["seedType"].set("Custom (Hand-drawn)")
        self.custom_seed_curves.append({"points": [], "params": self._get_curve_params_defaults()})
        self.editing_curve_index = len(self.custom_seed_curves) - 1
        self.draw_mode = True
        self.controls["btnDraw"].config(text="Done Drawing", bg="#3a5a3a")
        self.status_label.config(text=f"DRAW MODE: Curve {self.editing_curve_index + 1} - Click to add points, drag to move")
        self._refresh_curve_list()
        self.update_state()

    def _edit_curve(self, idx):
        """编辑指定母线"""
        if 0 <= idx < len(self.custom_seed_curves):
            self.controls["seedType"].set("Custom (Hand-drawn)")
            self.editing_curve_index = idx
            self.draw_mode = True
            self.controls["btnDraw"].config(text="Done Drawing", bg="#3a5a3a")
            self.status_label.config(text=f"DRAW MODE: Curve {idx + 1} - Click to add points, drag to move")
            self._refresh_curve_list()
            self.update_state()

    def _select_curve_params(self, idx):
        """选择母线以编辑其向量参数"""
        if 0 <= idx < len(self.custom_seed_curves):
            self.selected_curve_for_params = idx
            self._build_curve_params_ui()
            self.update_state()

    def _build_curve_params_ui(self):
        """构建选中母线的向量参数控件"""
        if not hasattr(self, "_curve_params_inner") or self._curve_params_inner is None:
            return
        for w in self._curve_params_inner.winfo_children():
            w.destroy()
        if self.selected_curve_for_params < 0 or self.selected_curve_for_params >= len(self.custom_seed_curves):
            tk.Label(self._curve_params_inner, text="(点击列表中的 Params 选择母线)", fg="#555555", bg="#141414",
                     font=("Inter", 9)).pack(anchor="w")
            return
        curve = self.custom_seed_curves[self.selected_curve_for_params]
        if isinstance(curve, list):
            return
        p = curve.setdefault("params", self._get_curve_params_defaults())
        idx = self.selected_curve_for_params

        def _on_change(key, val):
            p[key] = val
            self.update_state()

        tk.Label(self._curve_params_inner, text=f"Curve {idx + 1} 向量参数", fg="#e0e0e0", bg="#141414",
                 font=("Inter", 10, "bold")).pack(anchor="w", pady=(0, 8))
        # Line Spacing
        row = tk.Frame(self._curve_params_inner, bg="#141414")
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="线间距", fg="#888888", bg="#141414", font=("Inter", 10), width=10, anchor="w").pack(side=tk.LEFT)
        sp = tk.Scale(row, from_=10, to=100, orient=tk.HORIZONTAL, bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                      highlightthickness=0, showvalue=False, command=lambda v: _on_change("lineSpacing", float(v)))
        sp.set(p.get("lineSpacing", 40))
        sp.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(row, text=str(int(p.get("lineSpacing", 40))), fg="#888888", bg="#141414", font=("Inter", 9), width=4).pack(side=tk.RIGHT)
        # Pos / Neg Count
        row2 = tk.Frame(self._curve_params_inner, bg="#141414")
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="正向 / 负向", fg="#888888", bg="#141414", font=("Inter", 10), width=10, anchor="w").pack(side=tk.LEFT)
        pe = tk.Entry(row2, bg="#1a1a1a", fg="#e0e0e0", width=8)
        pe.insert(0, str(p.get("posCount", 10)))
        pe.pack(side=tk.LEFT, padx=2)
        ne = tk.Entry(row2, bg="#1a1a1a", fg="#e0e0e0", width=8)
        ne.insert(0, str(p.get("negCount", 10)))
        ne.pack(side=tk.LEFT)
        def _apply_counts():
            try:
                p["posCount"] = int(float(pe.get()))
                p["negCount"] = int(float(ne.get()))
                self.update_state()
            except Exception:
                pass
        pe.bind("<KeyRelease>", lambda e: _apply_counts())
        ne.bind("<KeyRelease>", lambda e: _apply_counts())
        # Offset X / Y (向量位置)
        row3 = tk.Frame(self._curve_params_inner, bg="#141414")
        row3.pack(fill=tk.X, pady=2)
        tk.Label(row3, text="偏移 X/Y", fg="#888888", bg="#141414", font=("Inter", 10), width=10, anchor="w").pack(side=tk.LEFT)
        ox = tk.Scale(row3, from_=-100, to=100, orient=tk.HORIZONTAL, bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                      highlightthickness=0, showvalue=False, command=lambda v: _on_change("offsetX", float(v)))
        ox.set(p.get("offsetX", 0))
        ox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        oy = tk.Scale(row3, from_=-100, to=100, orient=tk.HORIZONTAL, bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                      highlightthickness=0, showvalue=False, command=lambda v: _on_change("offsetY", float(v)))
        oy.set(p.get("offsetY", 0))
        oy.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # Spacing Mode
        row4a = tk.Frame(self._curve_params_inner, bg="#141414")
        row4a.pack(fill=tk.X, pady=2)
        tk.Label(row4a, text="间距模式", fg="#888888", bg="#141414", font=("Inter", 10), width=10, anchor="w").pack(side=tk.LEFT)
        _sm_map = {"Linear": "linear", "Exponential": "exponential", "Fibonacci": "fibonacci"}
        _sm_rev = {v: k for k, v in _sm_map.items()}
        sm_combo = ttk.Combobox(row4a, values=list(_sm_map.keys()), state="readonly", width=12)
        sm_combo.set(_sm_rev.get(p.get("spacingMode", "linear"), "Linear"))
        sm_combo.pack(side=tk.LEFT)
        sm_combo.bind("<<ComboboxSelected>>", lambda e: _on_change("spacingMode", _sm_map.get(sm_combo.get(), "linear")))
        # Spacing Scale
        row4 = tk.Frame(self._curve_params_inner, bg="#141414")
        row4.pack(fill=tk.X, pady=2)
        tk.Label(row4, text="间距缩放", fg="#888888", bg="#141414", font=("Inter", 10), width=10, anchor="w").pack(side=tk.LEFT)
        sc = tk.Scale(row4, from_=0.5, to=2.0, resolution=0.1, orient=tk.HORIZONTAL, bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                      highlightthickness=0, showvalue=False, command=lambda v: _on_change("spacingScale", float(v)))
        sc.set(p.get("spacingScale", 1.0))
        sc.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Label(row4, text=f"{p.get('spacingScale', 1.0):.1f}", fg="#888888", bg="#141414", font=("Inter", 9), width=4).pack(side=tk.RIGHT)
        # 道路疏密 (Cross Road Spacing)：值越小横向道路越密
        row5 = tk.Frame(self._curve_params_inner, bg="#141414")
        row5.pack(fill=tk.X, pady=2)
        tk.Label(row5, text="道路疏密", fg="#888888", bg="#141414", font=("Inter", 10), width=10, anchor="w").pack(side=tk.LEFT)
        lbl_cross = tk.Label(row5, text=str(int(p.get("crossSpacing", 80))), fg="#888888", bg="#141414", font=("Inter", 9), width=4)
        def _on_cross(v):
            _on_change("crossSpacing", float(v))
            lbl_cross.config(text=str(int(float(v))))
        cross_sp = tk.Scale(row5, from_=20, to=300, orient=tk.HORIZONTAL, bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                           highlightthickness=0, showvalue=False, command=_on_cross)
        cross_sp.set(p.get("crossSpacing", 80))
        cross_sp.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        lbl_cross.pack(side=tk.RIGHT)

    def _delete_curve(self, idx):
        """删除指定母线"""
        if 0 <= idx < len(self.custom_seed_curves):
            del self.custom_seed_curves[idx]
            if self.selected_curve_for_params == idx:
                self.selected_curve_for_params = -1
                self._build_curve_params_ui()
            elif self.selected_curve_for_params > idx:
                self.selected_curve_for_params -= 1
            if self.editing_curve_index == idx:
                self.editing_curve_index = -1
                self.draw_mode = False
                self._exit_draw_mode()
            elif self.editing_curve_index > idx:
                self.editing_curve_index -= 1
            self._refresh_curve_list()
            self.update_state()

    def _refresh_curve_list(self):
        """刷新母线列表 UI"""
        for i, curve in enumerate(self.custom_seed_curves):
            if isinstance(curve, list):
                self.custom_seed_curves[i] = {"points": curve, "params": self._get_curve_params_defaults()}
        for w in self._curve_list_frame.winfo_children():
            w.destroy()
        for i, curve in enumerate(self.custom_seed_curves):
            pts = self._get_curve_points(curve)
            n = len(pts)
            row = tk.Frame(self._curve_list_frame, bg="#141414")
            row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=f"Curve {i + 1} ({n} pts)", fg="#888888", bg="#141414", font=("Inter", 10))
            lbl.pack(side=tk.LEFT)
            btn_params = tk.Button(row, text="Params", command=lambda idx=i: self._select_curve_params(idx),
                                   bg="#2a3a4a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
            btn_params.pack(side=tk.RIGHT, padx=2)
            btn_edit = tk.Button(row, text="Edit", command=lambda idx=i: self._edit_curve(idx),
                                 bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
            btn_edit.pack(side=tk.RIGHT, padx=2)
            btn_del = tk.Button(row, text="Del", command=lambda idx=i: self._delete_curve(idx),
                                bg="#4a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
            btn_del.pack(side=tk.RIGHT)
        if not self.custom_seed_curves:
            tk.Label(self._curve_list_frame, text="(No curves yet. Click + Add Curve)", fg="#555555", bg="#141414",
                     font=("Inter", 9)).pack(anchor="w")

    def _toggle_draw_mode(self):
        """切换绘制模式。若已有母线则需先选择要编辑的母线"""
        if self.draw_mode:
            self._exit_draw_mode()
        else:
            if not self.custom_seed_curves:
                self._add_new_curve()
                return
            if self.editing_curve_index < 0:
                self.editing_curve_index = 0
            self.controls["seedType"].set("Custom (Hand-drawn)")
            self.draw_mode = True
            self.controls["btnDraw"].config(text="Done Drawing", bg="#3a5a3a")
            self.status_label.config(text=f"DRAW MODE: Curve {self.editing_curve_index + 1} - Click to add points, drag to move")
        self.update_state()

    def _exit_draw_mode(self):
        self.draw_mode = False
        self.editing_curve_index = -1
        self.controls["btnDraw"].config(text="Draw / Edit", bg="#2a2a2a")
        self.status_label.config(text="COORD_SYSTEM: CARTESIAN\nEXPANSION_VECTOR: LINE_LOCAL_NORMAL\nSTATUS: REALTIME_CALCULATION")
        self._refresh_curve_list()

    def _find_point_at(self, x, y, radius=10):
        """返回 (curve_idx, point_idx)，若未找到则返回 (-1, -1)"""
        best_ci, best_pi, best_d = -1, -1, radius * radius
        for ci, curve in enumerate(self.custom_seed_curves):
            pts = self._get_curve_points(curve)
            for pi, (px, py) in enumerate(pts):
                d = (x - px) ** 2 + (y - py) ** 2
                if d < best_d:
                    best_d, best_ci, best_pi = d, ci, pi
        return (best_ci, best_pi)

    def _on_canvas_click(self, event):
        if self.state.get("seedType") != "custom":
            return
        ci, pi = self._find_point_at(event.x, event.y)
        if ci >= 0 and pi >= 0:
            self.drag_curve_idx = ci
            self.drag_point_idx = pi
        elif self.draw_mode and self.editing_curve_index >= 0 and self.editing_curve_index < len(self.custom_seed_curves):
            self._get_curve_points(self.custom_seed_curves[self.editing_curve_index]).append((event.x, event.y))
            self._refresh_curve_list()
            self.update_state()

    def _on_canvas_drag(self, event):
        if self.drag_curve_idx is not None and self.drag_point_idx is not None:
            pts = self._get_curve_points(self.custom_seed_curves[self.drag_curve_idx])
            if 0 <= self.drag_point_idx < len(pts):
                pts[self.drag_point_idx] = (event.x, event.y)
                self._refresh_curve_list()
                self.update_state()

    def _on_canvas_release(self, event):
        self.drag_curve_idx = None
        self.drag_point_idx = None

    def _clear_all_curves(self):
        self.custom_seed_curves.clear()
        self.editing_curve_index = -1
        if self.draw_mode:
            self._toggle_draw_mode()
        self._refresh_curve_list()
        self.update_state()

    def _catmull_rom_point(self, p0, p1, p2, p3, t):
        """Catmull-Rom 样条：t∈[0,1] 为 p1 到 p2 之间的插值"""
        t2, t3 = t * t, t * t * t
        x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t +
                   (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                   (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
        y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t +
                   (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                   (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
        return (x, y)

    def _sample_curve(self, points, num_samples=80):
        """将控制点通过 Catmull-Rom 样条采样为平滑曲线点"""
        if not points:
            return []
        if len(points) == 1:
            return [points[0]]
        if len(points) == 2:
            return [(lerp(points[0][0], points[1][0], i / max(num_samples - 1, 1)),
                     lerp(points[0][1], points[1][1], i / max(num_samples - 1, 1))) for i in range(num_samples)]
        # 虚拟端点使首尾段自然延伸
        p0 = (2 * points[0][0] - points[1][0], 2 * points[0][1] - points[1][1])
        pn = (2 * points[-1][0] - points[-2][0], 2 * points[-1][1] - points[-2][1])
        extended = [p0] + list(points) + [pn]
        sampled = []
        n_per_seg = max(1, num_samples // (len(points) - 1))
        for i in range(len(points) - 1):
            for j in range(n_per_seg):
                t = j / n_per_seg
                pt = self._catmull_rom_point(extended[i], extended[i + 1], extended[i + 2], extended[i + 3], t)
                sampled.append(pt)
        sampled.append(points[-1])
        return sampled

    def _interpolate_curve(self, points, t):
        """t from 0 to 1, 沿 Catmull-Rom 曲线弧长均匀插值"""
        if not points:
            return None
        if len(points) == 1:
            return {"x": points[0][0], "y": points[0][1]}
        sampled = self._sample_curve(points)
        if len(sampled) < 2:
            return {"x": points[0][0], "y": points[0][1]}
        lengths, total = [], 0
        for i in range(len(sampled) - 1):
            dx = sampled[i + 1][0] - sampled[i][0]
            dy = sampled[i + 1][1] - sampled[i][1]
            seg_len = math.sqrt(dx * dx + dy * dy)
            lengths.append(seg_len)
            total += seg_len
        if total < 1e-10:
            return {"x": sampled[0][0], "y": sampled[0][1]}
        target = t * total
        acc = 0
        for i, seg_len in enumerate(lengths):
            if acc + seg_len >= target:
                local_t = (target - acc) / seg_len if seg_len > 0 else 0
                x = lerp(sampled[i][0], sampled[i + 1][0], local_t)
                y = lerp(sampled[i][1], sampled[i + 1][1], local_t)
                return {"x": x, "y": y}
            acc += seg_len
        return {"x": sampled[-1][0], "y": sampled[-1][1]}

    def _interpolate_polyline(self, points, t):
        """t from 0 to 1, 沿折线均匀插值（保留用于兼容）"""
        if not points:
            return None
        if len(points) == 1:
            return {"x": points[0][0], "y": points[0][1]}
        lengths = []
        total = 0
        for i in range(len(points) - 1):
            dx = points[i + 1][0] - points[i][0]
            dy = points[i + 1][1] - points[i][1]
            seg_len = math.sqrt(dx * dx + dy * dy)
            lengths.append(seg_len)
            total += seg_len
        if total < 1e-10:
            return {"x": points[0][0], "y": points[0][1]}
        target = t * total
        acc = 0
        for i, seg_len in enumerate(lengths):
            if acc + seg_len >= target:
                local_t = (target - acc) / seg_len if seg_len > 0 else 0
                x = lerp(points[i][0], points[i + 1][0], local_t)
                y = lerp(points[i][1], points[i + 1][1], local_t)
                return {"x": x, "y": y}
            acc += seg_len
        return {"x": points[-1][0], "y": points[-1][1]}

    def _precompute_parametric_arrays(self):
        """预计算参数化母线在 t=0..1 的种子点与向量，返回 (xs, ys, nxs, nys, txs, tys)"""
        s = self.state
        xs, ys = [0.0] * T_COUNT, [0.0] * T_COUNT
        nxs, nys = [0.0] * T_COUNT, [0.0] * T_COUNT
        txs, tys = [0.0] * T_COUNT, [0.0] * T_COUNT
        length_ratio = s["seedLength"]
        half_span = s["siteWidth"] * length_ratio * 0.5
        rad = s["seedRotation"] * math.pi / 180
        cx = s["siteWidth"] / 2 + s["seedXOffset"]
        cy = s["siteHeight"] / 2 + s["seedYOffset"]
        seed_type = s["seedType"]
        amp = s["seedSineAmp"]
        curv = s["seedArcCurv"]
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        for i in range(T_COUNT):
            t = i * T_STEP
            x = (t - 0.5) * 2 * half_span
            y = 0.0
            if seed_type == "sine":
                y = math.sin(t * math.pi * 2) * amp
            elif seed_type == "arc":
                y = ((t - 0.5) ** 2) * curv
            rx = x * cos_r - y * sin_r
            ry = x * sin_r + y * cos_r
            xs[i] = rx + cx
            ys[i] = ry + cy
        # 向量：用相邻点差分
        for i in range(T_COUNT):
            i0 = max(0, i - 1)
            i1 = min(T_COUNT - 1, i + 1)
            dx = xs[i1] - xs[i0]
            dy = ys[i1] - ys[i0]
            L = math.sqrt(dx * dx + dy * dy) or 1e-10
            txs[i] = dx / L
            tys[i] = dy / L
            nxs[i] = -tys[i]
            nys[i] = txs[i]
        return (xs, ys, nxs, nys, txs, tys)

    def _precompute_custom_curve_arrays(self, points):
        """预计算自定义母线在 t=0..1 的种子点与向量"""
        if not points or len(points) < 2:
            return None
        sampled = self._sample_curve(points, num_samples=80)
        if len(sampled) < 2:
            return None
        lengths, total = [], 0.0
        for i in range(len(sampled) - 1):
            dx = sampled[i + 1][0] - sampled[i][0]
            dy = sampled[i + 1][1] - sampled[i][1]
            seg = math.sqrt(dx * dx + dy * dy)
            lengths.append(seg)
            total += seg
        if total < 1e-10:
            return None
        xs, ys = [0.0] * T_COUNT, [0.0] * T_COUNT
        nxs, nys = [0.0] * T_COUNT, [0.0] * T_COUNT
        txs, tys = [0.0] * T_COUNT, [0.0] * T_COUNT
        acc, idx = 0.0, 0
        for i in range(T_COUNT):
            target = (i * T_STEP) * total
            while idx < len(lengths) and acc + lengths[idx] < target:
                acc += lengths[idx]
                idx += 1
            if idx >= len(lengths):
                xs[i], ys[i] = sampled[-1][0], sampled[-1][1]
            else:
                local_t = (target - acc) / lengths[idx] if lengths[idx] > 0 else 0
                xs[i] = lerp(sampled[idx][0], sampled[idx + 1][0], local_t)
                ys[i] = lerp(sampled[idx][1], sampled[idx + 1][1], local_t)
            i0, i1 = max(0, idx - 1), min(len(sampled) - 1, idx + 1)
            dx = sampled[i1][0] - sampled[i0][0]
            dy = sampled[i1][1] - sampled[i0][1]
            L = math.sqrt(dx * dx + dy * dy) or 1e-10
            txs[i] = dx / L
            tys[i] = dy / L
            nxs[i] = -tys[i]
            nys[i] = txs[i]
        return (xs, ys, nxs, nys, txs, tys)

    def update_state(self):
        self.state["runMode"] = self._get_run_mode()
        self.state["fieldType"] = self._get_field_type()
        self.state["siteWidth"] = self._safe_float(self.controls["siteWidth"].get(), 1200)
        self.state["siteHeight"] = self._safe_float(self.controls["siteHeight"].get(), 200)
        self.state["seedType"] = self._get_seed_type()
        self.state["seedRotation"] = self._safe_float(self.controls["seedRotation"].get(), 0)
        self.state["seedXOffset"] = self._safe_float(self.controls["seedXOffset"].get(), 0)
        self.state["seedYOffset"] = self._safe_float(self.controls["seedYOffset"].get(), 0)
        self.state["seedLength"] = self._safe_float(self.controls["seedLength"].get(), 0.8)
        self.state["seedSineAmp"] = self._safe_float(self.controls["seedSineAmp"].get(), 50)
        self.state["seedArcCurv"] = self._safe_float(self.controls["seedArcCurv"].get(), 200)
        self.state["lineSpacing"] = self._safe_float(self.controls["lineSpacing"].get(), 40)
        self.state["posCount"] = self._safe_int(self.controls["posCount"].get(), 10)
        self.state["negCount"] = self._safe_int(self.controls["negCount"].get(), 10)
        self.state["spacingMode"] = self._get_spacing_mode()
        self.state["spacingScale"] = self._safe_float(self.controls["spacingScale"].get(), 1.0)
        self.state["noiseEnabled"] = self.controls["noiseEnabled"].get()
        self.state["noiseScale"] = self._safe_float(self.controls["noiseScale"].get(), 0.005)
        self.state["noiseStrength"] = self._safe_float(self.controls["noiseStrength"].get(), 20)
        self.state["crossSpacing"] = self._safe_float(self.controls["crossSpacing"].get(), 80)
        self.state["roadsPerpendicular"] = self.controls["roadsPerpendicular"].get()
        self.state["pMin"] = self._safe_float(self.controls["pMin"].get(), 15)
        self.state["pMax"] = self._safe_float(self.controls["pMax"].get(), 45)
        self.state["pDepth"] = self._safe_float(self.controls["pDepth"].get(), 10)

        # 更新显示数值
        self.controls["rotVal"].config(text=f"{self.state['seedRotation']}°")
        self.controls["seedXVal"].config(text=str(int(self.state["seedXOffset"])))
        self.controls["seedYVal"].config(text=str(int(self.state["seedYOffset"])))
        self.controls["seedLenVal"].config(text=f"{self.state['seedLength']:.2f}")
        self.controls["spacingVal"].config(text=str(self.state["lineSpacing"]))
        self.controls["scaleVal"].config(text=f"{self.state['spacingScale']:.1f}")
        self.controls["noiseScaleVal"].config(text=str(self.state["noiseScale"]))
        self.controls["noiseStrVal"].config(text=str(int(self.state["noiseStrength"])))
        self.controls["crossVal"].config(text=str(int(self.state["crossSpacing"])))

        if self.draw_mode and self.state["seedType"] != "custom":
            self._exit_draw_mode()
        if self.state["seedType"] == "custom" and self._curve_list_frame:
            self._refresh_curve_list()
        # 母线手绘模式：绑定/解绑画布交互
        if self.state["seedType"] == "custom":
            if not self._canvas_custom_bound:
                self.canvas.bind("<Button-1>", self._on_canvas_click)
                self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
                self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
                self._canvas_custom_bound = True
        else:
            if self._canvas_custom_bound:
                self.canvas.unbind("<Button-1>")
                self.canvas.unbind("<B1-Motion>")
                self.canvas.unbind("<ButtonRelease-1>")
                self._canvas_custom_bound = False
        self.resize_canvas()
        self.generate()

    def resize_canvas(self):
        """原逻辑：canvas 物理尺寸 = siteWidth x siteHeight"""
        w = int(self.state["siteWidth"])
        h = int(self.state["siteHeight"])
        self.canvas.config(width=w, height=h)

    def _get_seed_point_for_curve(self, t, points):
        """对单条母线插值，t from 0 to 1"""
        if not points:
            return None
        if len(points) == 1:
            return {"x": points[0][0], "y": points[0][1]}
        pt = self._interpolate_curve(points, t)
        return pt

    def _get_line_vectors_for_curve(self, t, points):
        """获取单条母线上点的切向和法向"""
        if not points or len(points) < 2:
            return {"tangent": {"x": 1, "y": 0}, "normal": {"x": 0, "y": 1}}
        p1 = self._get_seed_point_for_curve(max(0, t - 0.01), points)
        p2 = self._get_seed_point_for_curve(min(1, t + 0.01), points)
        if not p1 or not p2:
            return {"tangent": {"x": 1, "y": 0}, "normal": {"x": 0, "y": 1}}
        dx = p2["x"] - p1["x"]
        dy = p2["y"] - p1["y"]
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            length = 1e-10
        tangent = {"x": dx / length, "y": dy / length}
        normal = {"x": -tangent["y"], "y": tangent["x"]}
        return {"tangent": tangent, "normal": normal}

    def get_seed_point(self, t):
        """t from 0 to 1，母线局部坐标先算形状，再旋转，最后平移到中心+偏移（单母线/非custom 用）"""
        s = self.state

        if s["seedType"] == "custom" and self.custom_seed_curves:
            # 多母线时由 generate 直接调用 _get_seed_point_for_curve
            curve = self.custom_seed_curves[0]
            pts = self._get_curve_points(curve)
            if len(pts) >= 2:
                pt = self._get_seed_point_for_curve(t, pts)
                return pt if pt else self._fallback_seed_point(t)

        length_ratio = s["seedLength"]
        half_span = s["siteWidth"] * length_ratio * 0.5
        x = (t - 0.5) * 2 * half_span
        y = 0.0

        if s["seedType"] == "sine":
            y = math.sin(t * math.pi * 2) * s["seedSineAmp"]
        elif s["seedType"] == "arc":
            y = ((t - 0.5) ** 2) * s["seedArcCurv"]

        # 旋转
        rad = s["seedRotation"] * math.pi / 180
        rx = x * math.cos(rad) - y * math.sin(rad)
        ry = x * math.sin(rad) + y * math.cos(rad)

        # 平移到场地中心 + 用户偏移
        cx = s["siteWidth"] / 2 + s["seedXOffset"]
        cy = s["siteHeight"] / 2 + s["seedYOffset"]
        return {"x": rx + cx, "y": ry + cy}

    def _fallback_seed_point(self, t):
        """custom 无点时回退到直线"""
        s = self.state
        cx = s["siteWidth"] / 2 + s["seedXOffset"]
        cy = s["siteHeight"] / 2 + s["seedYOffset"]
        half = s["siteWidth"] * 0.4
        x = (t - 0.5) * 2 * half + cx
        return {"x": x, "y": cy}

    def get_line_vectors(self, t):
        """获取线上点的切向和法向"""
        p1 = self.get_seed_point(t - 0.01)
        p2 = self.get_seed_point(t + 0.01)
        dx = p2["x"] - p1["x"]
        dy = p2["y"] - p1["y"]
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            length = 1e-10
        tangent = {"x": dx / length, "y": dy / length}
        normal = {"x": -tangent["y"], "y": tangent["x"]}
        return {"tangent": tangent, "normal": normal}

    def _generate_lines_for_curve(self, curve):
        """对单条母线生成扩张线，使用预计算数组避免重复采样"""
        s = self.state
        points = self._get_curve_points(curve)
        arr = self._precompute_custom_curve_arrays(points)
        if arr is None:
            return []
        xs, ys, nxs, nys, txs, tys = arr
        if isinstance(curve, dict) and "params" in curve:
            p = curve["params"]
        else:
            p = self._get_curve_params_defaults()
        ox, oy = p.get("offsetX", 0), p.get("offsetY", 0)
        ft = s["fieldType"]
        noise_on = s["noiseEnabled"]
        ns = s["noiseScale"] * 100
        nstr = s["noiseStrength"]
        sp, sc = p.get("lineSpacing", 40), p.get("spacingScale", 1.0)
        sm = p.get("spacingMode", "linear")
        lines = []
        for side in range(2):
            count = p.get("posCount", 10) if side == 1 else p.get("negCount", 10)
            start_i = 1 if side == 0 else 0
            for i in range(start_i, count + 1):
                actual_index = -i if side == 0 else i
                if sm == "linear":
                    offset_dist = actual_index * sp * sc
                elif sm == "exponential":
                    offset_dist = (1 if actual_index >= 0 else -1) * (abs(actual_index) ** 1.5) * sp * sc * 0.5
                else:
                    offset_dist = actual_index * sp * (1 + abs(actual_index) * 0.1) * sc
                line_points = []
                for ti in range(T_COUNT):
                    t = ti * T_STEP
                    px = xs[ti] + ox
                    py = ys[ti] + oy
                    nx, ny = nxs[ti], nys[ti]
                    tx, ty = txs[ti], tys[ti]
                    if ft == "1":
                        px += nx * offset_dist
                        py += ny * offset_dist
                    elif ft == "2":
                        px += tx * offset_dist * 0.2
                        py += ny * offset_dist
                    elif ft == "3":
                        factor = math.sin(t * math.pi)
                        px += nx * offset_dist * factor
                        py += ny * offset_dist * factor
                    elif ft == "4":
                        px += nx * offset_dist
                        py += ny * offset_dist
                        bulge = math.sin(t * math.pi) * (offset_dist * 0.3)
                        px += nx * bulge
                        py += ny * bulge
                    elif ft == "5":
                        px += nx * offset_dist
                        py += ny * offset_dist
                        if i % 2 == 0:
                            px += tx * 20
                    elif ft == "6":
                        mix = math.cos(t * math.pi * 2)
                        px += (nx * (1 - mix) + tx * mix) * offset_dist
                        py += (ny * (1 - mix) + ty * mix) * offset_dist
                    else:
                        px += nx * offset_dist
                        py += ny * offset_dist
                    if noise_on:
                        n = noise(px * ns, py * ns)
                        px += n * nstr
                        py += n * nstr
                    line_points.append({"x": px, "y": py, "t": t, "offset": offset_dist})
                lines.append(line_points)
        return lines

    def generate(self):
        self.canvas.delete("all")
        lines = []
        s = self.state

        lines_by_curve = []  # 每条母线单独一组 [[line1, line2, ...], [line1, line2, ...], ...]
        cross_spacings = []
        if s["seedType"] == "custom":
            if self.custom_seed_curves:
                for curve in self.custom_seed_curves:
                    if len(self._get_curve_points(curve)) >= 2:
                        lines_by_curve.append(self._generate_lines_for_curve(curve))
                        p = curve.get("params", self._get_curve_params_defaults()) if isinstance(curve, dict) else {}
                        cross_spacings.append(p.get("crossSpacing", s["crossSpacing"]))
        else:
            # 单母线或参数化母线：使用预计算数组
            arr = self._precompute_parametric_arrays()
            xs, ys, nxs, nys, txs, tys = arr
            ft = s["fieldType"]
            noise_on = s["noiseEnabled"]
            ns = s["noiseScale"] * 100
            nstr = s["noiseStrength"]
            sp, sc = s["lineSpacing"], s["spacingScale"]
            sm = s["spacingMode"]
            lines = []
            for side in range(2):
                count = s["negCount"] if side == 0 else s["posCount"]
                start_i = 1 if side == 0 else 0
                for i in range(start_i, count + 1):
                    actual_index = -i if side == 0 else i
                    if sm == "linear":
                        offset_dist = actual_index * sp * sc
                    elif sm == "exponential":
                        offset_dist = (1 if actual_index >= 0 else -1) * (abs(actual_index) ** 1.5) * sp * sc * 0.5
                    else:
                        offset_dist = actual_index * sp * (1 + abs(actual_index) * 0.1) * sc
                    line_points = []
                    for ti in range(T_COUNT):
                        t = ti * T_STEP
                        px, py = xs[ti], ys[ti]
                        nx, ny = nxs[ti], nys[ti]
                        tx, ty = txs[ti], tys[ti]
                        if ft == "1":
                            px += nx * offset_dist
                            py += ny * offset_dist
                        elif ft == "2":
                            px += tx * offset_dist * 0.2
                            py += ny * offset_dist
                        elif ft == "3":
                            factor = math.sin(t * math.pi)
                            px += nx * offset_dist * factor
                            py += ny * offset_dist * factor
                        elif ft == "4":
                            px += nx * offset_dist
                            py += ny * offset_dist
                            bulge = math.sin(t * math.pi) * (offset_dist * 0.3)
                            px += nx * bulge
                            py += ny * bulge
                        elif ft == "5":
                            px += nx * offset_dist
                            py += ny * offset_dist
                            if i % 2 == 0:
                                px += tx * 20
                        elif ft == "6":
                            mix = math.cos(t * math.pi * 2)
                            px += (nx * (1 - mix) + tx * mix) * offset_dist
                            py += (ny * (1 - mix) + ty * mix) * offset_dist
                        else:
                            px += nx * offset_dist
                            py += ny * offset_dist
                        if noise_on:
                            n = noise(px * ns, py * ns)
                            px += n * nstr
                            py += n * nstr
                        line_points.append({"x": px, "y": py, "t": t, "offset": offset_dist})
                    lines.append(line_points)
            lines_by_curve = [lines] if lines else []
            cross_spacings = [s["crossSpacing"]] if lines else []

        if not cross_spacings:
            cross_spacings = [s["crossSpacing"]]

        self.draw_result(lines_by_curve, cross_spacings)

    def draw_result(self, lines_by_curve, cross_spacings=None):
        """lines_by_curve: 每条母线一组 [[line1, line2, ...], ...]；cross_spacings: 每条母线的道路疏密(值越小越密)"""
        s = self.state
        cross_spacings = cross_spacings or [s["crossSpacing"]]
        # 重置导出几何数据
        self._export_geometry = {"polylines": [], "parcels": []}

        # 绘制场地边界（1:6 横向矩形）
        self.canvas.create_rectangle(0, 0, s["siteWidth"], s["siteHeight"],
                                     outline="#555555", width=2, dash=(4, 4))
        curve_colors = ["#ff6600", "#66ff00", "#0066ff", "#ff00ff", "#00ffff"]
        perp = s.get("roadsPerpendicular", True)
        main_color, main_w = "#b3b3b3", 1
        cross_color, cross_w = "#4d4d4d", 0.5

        for curve_idx, lines in enumerate(lines_by_curve):
            if not lines:
                continue
            curve_color = curve_colors[curve_idx % len(curve_colors)] if len(lines_by_curve) > 1 else "#ff3300"

            if s["runMode"] == "A":
                # FLOW LINES：每条母线单独绘制流线
                for idx, line in enumerate(lines):
                    color = curve_color if idx == 0 else "#999999"
                    width = 2 if idx == 0 else 0.5
                    pts = [(p["x"], p["y"]) for p in line]
                    self._export_geometry["polylines"].append(pts)
                    for i in range(len(pts) - 1):
                        self.canvas.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                                               fill=color, width=width)
            elif s["runMode"] in ("B", "C"):
                # STREET NETWORK：每条母线单独计算纵向线、横向连接、地块
                # 1. Longitudinal lines (∥向量线)
                for line in lines:
                    pts = [(p["x"], p["y"]) for p in line]
                    self._export_geometry["polylines"].append(pts)
                    fill, w = (cross_color, cross_w) if perp else (main_color, main_w)
                    for i in range(len(pts) - 1):
                        self.canvas.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                                               fill=fill, width=w)

                # 2. Cross Streets (⊥向量线)：仅连接同一条母线的扩张线
                sorted_lines = sorted(lines, key=lambda ln: ln[0]["offset"])
                # 道路疏密：crossSpacing 越小越密，num_sections = 1600/crossSpacing，范围 3~51
                cs = cross_spacings[curve_idx] if curve_idx < len(cross_spacings) else s["crossSpacing"]
                num_sections = max(3, min(51, int(1600 / max(cs, 10))))
                for j in range(num_sections):
                    t = j / max(num_sections - 1, 1) if num_sections > 1 else 0
                    idx = 0 if t <= 0 else min(int(t / T_STEP) + 1, T_COUNT - 1)
                    cross_pts = []
                    for line in sorted_lines:
                        p = line[idx]
                        cross_pts.append((p["x"], p["y"]))
                    self._export_geometry["polylines"].append(cross_pts)
                    fill, w = (main_color, main_w) if perp else (cross_color, cross_w)
                    for i in range(len(cross_pts) - 1):
                        self.canvas.create_line(cross_pts[i][0], cross_pts[i][1], cross_pts[i + 1][0], cross_pts[i + 1][1],
                                               fill=fill, width=w)

                # 3. PARCELS (Mode C)：每条母线单独划分地块
                if s["runMode"] == "C":
                    segments = 15
                    for i in range(len(sorted_lines) - 1):
                        line_a = sorted_lines[i]
                        line_b = sorted_lines[i + 1]
                        for seg in range(segments):
                            t_start = seg / segments
                            t_end = (seg + 0.8) / segments
                            idx_s = 0 if t_start <= 0 else min(int(t_start / T_STEP) + 1, T_COUNT - 1)
                            idx_e = 0 if t_end <= 0 else min(int(t_end / T_STEP) + 1, T_COUNT - 1)

                            p1, p2 = line_a[idx_s], line_b[idx_s]
                            p3, p4 = line_b[idx_e], line_a[idx_e]
                            parcel_pts = [(p1["x"], p1["y"]), (p2["x"], p2["y"]), (p3["x"], p3["y"]), (p4["x"], p4["y"])]
                            self._export_geometry["parcels"].append(parcel_pts)

                            if random.random() > 0.15:
                                gray = int(255 * (0.05 + random.random() * 0.1))
                                fill_color = f"#{gray:02x}{gray:02x}{gray:02x}"
                                self.canvas.create_polygon(
                                    p1["x"], p1["y"], p2["x"], p2["y"], p3["x"], p3["y"], p4["x"], p4["y"],
                                    fill=fill_color, outline="#1a1a1a")

        # 多条手绘母线：绘制 Catmull-Rom 曲线与控制点
        if s["seedType"] == "custom" and self.custom_seed_curves:
            colors = ["#ff6600", "#66ff00", "#0066ff", "#ff00ff", "#00ffff"]
            for ci, curve in enumerate(self.custom_seed_curves):
                pts = self._get_curve_points(curve)
                if len(pts) < 2:
                    for x, y in pts:
                        self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill="#ff3300", outline="#ffffff")
                    continue
                color = colors[ci % len(colors)]
                curve_pts = self._sample_curve(pts)
                for i in range(len(curve_pts) - 1):
                    x1, y1 = curve_pts[i]
                    x2, y2 = curve_pts[i + 1]
                    self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
                for x, y in pts:
                    self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline="#ffffff")

    def _bind_events(self):
        def on_change(*args):
            self.update_state()

        for key, ctrl in self.controls.items():
            if key in ("rotVal", "spacingVal", "scaleVal", "noiseScaleVal", "noiseStrVal", "crossVal",
                       "seedXVal", "seedYVal", "seedLenVal"):
                continue
            if isinstance(ctrl, tk.Scale):
                ctrl.config(command=lambda v, k=key: self.update_state())
            elif isinstance(ctrl, (ttk.Combobox, tk.Entry)):
                ctrl.bind("<<ComboboxSelected>>" if isinstance(ctrl, ttk.Combobox) else "<KeyRelease>", lambda e: self.update_state())
            elif isinstance(ctrl, tk.BooleanVar):
                pass  # 通过 Reset 和按钮处理

        # 绑定所有控件的变更
        for w in self.root.winfo_children():
            self._bind_recursive(w, self.update_state)

    def _bind_recursive(self, widget, callback):
        if isinstance(widget, tk.Scale):
            widget.config(command=lambda v: callback())
        elif isinstance(widget, ttk.Combobox):
            widget.bind("<<ComboboxSelected>>", lambda e: callback())
        elif isinstance(widget, tk.Entry):
            widget.bind("<KeyRelease>", lambda e: callback())
        elif isinstance(widget, tk.Checkbutton):
            pass  # 需在创建时绑定
        for child in widget.winfo_children():
            self._bind_recursive(child, callback)

    def _get_clipped_geometry(self):
        """以场地矩形为边界裁剪几何体，仅保留内部部分"""
        xmin, ymin = 0, 0
        xmax = self.state.get("siteWidth", 1200)
        ymax = self.state.get("siteHeight", 200)
        polylines = []
        for pts in self._export_geometry["polylines"]:
            polylines.extend(_clip_polyline_to_rect(pts, xmin, ymin, xmax, ymax))
        parcels = []
        for pts in self._export_geometry["parcels"]:
            parcels.extend(_clip_polygon_to_rect(pts, xmin, ymin, xmax, ymax))
        return {"polylines": polylines, "parcels": parcels}

    def _export_rhino(self):
        """导出 RhinoScript (.py)，可在 Rhino 的 Python 编辑器中运行"""
        if not self._export_geometry["polylines"] and not self._export_geometry["parcels"]:
            self.status_label.config(text="No geometry to export. Generate first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python script", "*.py"), ("All files", "*.*")],
            title="Export for Rhino"
        )
        if not path:
            return
        geo = self._get_clipped_geometry()
        if not geo["polylines"] and not geo["parcels"]:
            self.status_label.config(text="No geometry inside boundary after clip.")
            return
        lines = []
        lines.append('"""Strip Field Export - Run in Rhino Python Editor (EditPythonScript)"""')
        lines.append("import rhinoscriptsyntax as rs")
        lines.append("")
        lines.append("# Clipped to site boundary rectangle")
        lines.append("")
        for pts in geo["polylines"]:
            if len(pts) < 2:
                continue
            pts_str = ", ".join(f"({p[0]:.4f}, {p[1]:.4f}, 0)" for p in pts)
            lines.append(f"rs.AddCurve([{pts_str}])")
        for pts in geo["parcels"]:
            if len(pts) < 3:
                continue
            closed_pts = pts + [pts[0]]
            pts_str = ", ".join(f"({p[0]:.4f}, {p[1]:.4f}, 0)" for p in closed_pts)
            lines.append(f"rs.AddCurve([{pts_str}], 1)  # parcel (closed)")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.status_label.config(text=f"Exported to {path}")
        except Exception as e:
            self.status_label.config(text=f"Export failed: {e}")

    def _export_dxf(self):
        """导出 DXF，Rhino 可直接导入"""
        if not self._export_geometry["polylines"] and not self._export_geometry["parcels"]:
            self.status_label.config(text="No geometry to export. Generate first.")
            return
        try:
            import ezdxf
        except ImportError:
            self.status_label.config(text="DXF export requires: pip install ezdxf")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".dxf",
            filetypes=[("DXF file", "*.dxf"), ("All files", "*.*")],
            title="Export DXF"
        )
        if not path:
            return
        geo = self._get_clipped_geometry()
        if not geo["polylines"] and not geo["parcels"]:
            self.status_label.config(text="No geometry inside boundary after clip.")
            return
        try:
            doc = ezdxf.new("R2010")
            msp = doc.modelspace()
            for pts in geo["polylines"]:
                if len(pts) < 2:
                    continue
                msp.add_lwpolyline([(p[0], p[1]) for p in pts])
            for pts in geo["parcels"]:
                if len(pts) < 3:
                    continue
                msp.add_lwpolyline([(p[0], p[1]) for p in pts], close=True)
            doc.saveas(path)
            self.status_label.config(text=f"Exported to {path}")
        except Exception as e:
            self.status_label.config(text=f"Export failed: {e}")

    def _reset(self):
        self.controls["seedRotation"].set(0)
        self.controls["seedXOffset"].set(0)
        self.controls["seedYOffset"].set(0)
        self.controls["seedLength"].set(0.8)
        self.controls["seedSineAmp"].delete(0, tk.END)
        self.controls["seedSineAmp"].insert(0, "50")
        self.controls["seedArcCurv"].delete(0, tk.END)
        self.controls["seedArcCurv"].insert(0, "200")
        self.controls["lineSpacing"].set(40)
        self.controls["posCount"].delete(0, tk.END)
        self.controls["posCount"].insert(0, "10")
        self.controls["negCount"].delete(0, tk.END)
        self.controls["negCount"].insert(0, "10")
        self.controls["noiseEnabled"].set(False)
        self.update_state()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = UrbanFieldGenerator()
    app.run()
