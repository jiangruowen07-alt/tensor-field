"""
城市线驱动向量场生成器
核心逻辑：基于 Seed Curve 的非中心式扩张
Python 重写版本 - 逻辑完全一致
"""

import tkinter as tk
from tkinter import ttk
import math
import random


def lerp(a, b, t):
    return a + (b - a) * t


def noise(x, y):
    """简易噪声函数 (Lattice Noise)"""
    return (math.sin(x * 0.01) * math.cos(y * 0.01) + math.sin(x * 0.02 + y * 0.015)) * 0.5


class UrbanFieldGenerator:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Line-Driven Urban Field Generator")
        self.root.configure(bg="#0a0a0a")
        self.root.geometry("1400x900")

        # State
        self.state = {}
        self.controls = {}
        self.custom_seed_points = []  # 手绘母线控制点 [(x,y), ...]
        self.draw_mode = False
        self.drag_index = None  # 正在拖动的控制点索引
        self._canvas_custom_bound = False

        self._build_ui()
        self._bind_events()
        self.update_state()

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg="#0a0a0a")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Control Panel
        panel = tk.Frame(main_frame, width=320, bg="#141414", padx=24, pady=24)
        panel.pack(side=tk.LEFT, fill=tk.Y)
        panel.pack_propagate(False)

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

        # 手绘母线
        draw_btn_frame = tk.Frame(panel, bg="#141414")
        draw_btn_frame.pack(fill=tk.X, pady=(0, 24))
        self.controls["btnDraw"] = tk.Button(draw_btn_frame, text="Draw Seed Line", command=self._toggle_draw_mode,
                                             bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                             font=("JetBrains Mono", 10))
        self.controls["btnDraw"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.controls["btnClear"] = tk.Button(draw_btn_frame, text="Clear", command=self._clear_custom_seed,
                                              bg="#1a1a1a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                              font=("JetBrains Mono", 10))
        self.controls["btnClear"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

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

    def _toggle_draw_mode(self):
        self.draw_mode = not self.draw_mode
        if self.draw_mode:
            self.controls["seedType"].set("Custom (Hand-drawn)")
            self.controls["btnDraw"].config(text="Done Drawing", bg="#3a5a3a")
            self.status_label.config(text="DRAW MODE: Click to add points, drag to move")
        else:
            self._exit_draw_mode()
        self.update_state()

    def _exit_draw_mode(self):
        self.draw_mode = False
        self.controls["btnDraw"].config(text="Draw Seed Line", bg="#2a2a2a")
        self.status_label.config(text="COORD_SYSTEM: CARTESIAN\nEXPANSION_VECTOR: LINE_LOCAL_NORMAL\nSTATUS: REALTIME_CALCULATION")

    def _find_point_at(self, x, y, radius=10):
        """返回距离 (x,y) 最近的控制点索引，若超出 radius 则返回 -1"""
        best_i, best_d = -1, radius * radius
        for i, (px, py) in enumerate(self.custom_seed_points):
            d = (x - px) ** 2 + (y - py) ** 2
            if d < best_d:
                best_d, best_i = d, i
        return best_i

    def _on_canvas_click(self, event):
        if self.state.get("seedType") != "custom":
            return
        idx = self._find_point_at(event.x, event.y)
        if idx >= 0:
            self.drag_index = idx
        elif self.draw_mode:
            self.custom_seed_points.append((event.x, event.y))
            self.update_state()

    def _on_canvas_drag(self, event):
        if self.drag_index is not None and 0 <= self.drag_index < len(self.custom_seed_points):
            self.custom_seed_points[self.drag_index] = (event.x, event.y)
            self.update_state()

    def _on_canvas_release(self, event):
        self.drag_index = None

    def _clear_custom_seed(self):
        self.custom_seed_points.clear()
        if self.draw_mode:
            self._toggle_draw_mode()
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

    def get_seed_point(self, t):
        """t from 0 to 1，母线局部坐标先算形状，再旋转，最后平移到中心+偏移"""
        s = self.state

        if s["seedType"] == "custom" and len(self.custom_seed_points) >= 2:
            pt = self._interpolate_curve(self.custom_seed_points, t)
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

    def generate(self):
        self.canvas.delete("all")
        lines = []
        s = self.state

        # 生成扩张线
        for side in range(2):
            count = s["negCount"] if side == 0 else s["posCount"]
            direction = -1 if side == 0 else 1

            start_i = 1 if side == 0 else 0
            for i in range(start_i, count + 1):
                line_points = []
                actual_index = -i if side == 0 else i

                # 计算偏移距离
                if s["spacingMode"] == "linear":
                    offset_dist = actual_index * s["lineSpacing"] * s["spacingScale"]
                elif s["spacingMode"] == "exponential":
                    offset_dist = (1 if actual_index >= 0 else -1) * (abs(actual_index) ** 1.5) * s["lineSpacing"] * s["spacingScale"] * 0.5
                else:
                    # Fibonacci 模拟
                    offset_dist = actual_index * s["lineSpacing"] * (1 + abs(actual_index) * 0.1) * s["spacingScale"]

                t = 0
                while t <= 1:
                    seed_p = self.get_seed_point(t)
                    vecs = self.get_line_vectors(t)

                    px = seed_p["x"]
                    py = seed_p["y"]

                    # 根据场类型应用逻辑
                    ft = s["fieldType"]
                    if ft == "1":  # Parallel Offset
                        px += vecs["normal"]["x"] * offset_dist
                        py += vecs["normal"]["y"] * offset_dist
                    elif ft == "2":  # Tangent expansion
                        px += vecs["tangent"]["x"] * offset_dist * 0.2
                        py += vecs["normal"]["y"] * offset_dist
                    elif ft == "3":  # Normal focus
                        factor = math.sin(t * math.pi)
                        px += vecs["normal"]["x"] * offset_dist * factor
                        py += vecs["normal"]["y"] * offset_dist * factor
                    elif ft == "4":  # Contour
                        px += vecs["normal"]["x"] * offset_dist
                        py += vecs["normal"]["y"] * offset_dist
                        bulge = math.sin(t * math.pi) * (offset_dist * 0.3)
                        px += vecs["normal"]["x"] * bulge
                        py += vecs["normal"]["y"] * bulge
                    elif ft == "5":  # Strip
                        px += vecs["normal"]["x"] * offset_dist
                        py += vecs["normal"]["y"] * offset_dist
                        if i % 2 == 0:
                            px += vecs["tangent"]["x"] * 20
                    elif ft == "6":  # Hybrid
                        mix = math.cos(t * math.pi * 2)
                        px += (vecs["normal"]["x"] * (1 - mix) + vecs["tangent"]["x"] * mix) * offset_dist
                        py += (vecs["normal"]["y"] * (1 - mix) + vecs["tangent"]["y"] * mix) * offset_dist
                    elif ft == "7":  # Noise
                        px += vecs["normal"]["x"] * offset_dist
                        py += vecs["normal"]["y"] * offset_dist

                    # 应用全局噪声
                    if s["noiseEnabled"]:
                        n = noise(px * s["noiseScale"] * 100, py * s["noiseScale"] * 100)
                        px += n * s["noiseStrength"]
                        py += n * s["noiseStrength"]

                    line_points.append({"x": px, "y": py, "t": t, "offset": offset_dist})
                    t += 0.02

                lines.append(line_points)

        self.draw_result(lines)

    def draw_result(self, lines):
        s = self.state
        # 绘制场地边界（1:6 横向矩形）
        self.canvas.create_rectangle(0, 0, s["siteWidth"], s["siteHeight"],
                                     outline="#555555", width=2, dash=(4, 4))
        if s["runMode"] == "A":
            # FLOW LINES
            for idx, line in enumerate(lines):
                color = "#ff3300" if idx == 0 else "#999999"  # rgba(255,255,255,0.4) 近似
                width = 2 if idx == 0 else 0.5
                pts = [(p["x"], p["y"]) for p in line]
                for i in range(len(pts) - 1):
                    self.canvas.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                                           fill=color, width=width)
        elif s["runMode"] in ("B", "C"):
            # STREET NETWORK - 1. Draw Longitudinal lines (Main Streets)
            for line in lines:
                pts = [(p["x"], p["y"]) for p in line]
                for i in range(len(pts) - 1):
                    self.canvas.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                                           fill="#b3b3b3", width=1)  # rgba(255,255,255,0.7) 近似

            # 2. Draw Cross Streets (Lateral connection)
            t = 0
            while t <= 1:
                sorted_lines = sorted(lines, key=lambda ln: ln[0]["offset"])
                cross_pts = []
                for line in sorted_lines:
                    p = next((lp for lp in line if lp["t"] >= t), line[-1])
                    cross_pts.append((p["x"], p["y"]))
                for i in range(len(cross_pts) - 1):
                    self.canvas.create_line(cross_pts[i][0], cross_pts[i][1], cross_pts[i + 1][0], cross_pts[i + 1][1],
                                           fill="#4d4d4d", width=0.5)  # rgba(255,255,255,0.3) 近似
                t += 0.05

            # 3. PARCELS (Mode C)
            if s["runMode"] == "C":
                sorted_lines = sorted(lines, key=lambda ln: ln[0]["offset"])
                segments = 15
                for i in range(len(sorted_lines) - 1):
                    line_a = sorted_lines[i]
                    line_b = sorted_lines[i + 1]
                    for seg in range(segments):
                        t_start = seg / segments
                        t_end = (seg + 0.8) / segments

                        p1 = next((p for p in line_a if p["t"] >= t_start), line_a[-1])
                        p2 = next((p for p in line_b if p["t"] >= t_start), line_b[-1])
                        p3 = next((p for p in line_b if p["t"] >= t_end), line_b[-1])
                        p4 = next((p for p in line_a if p["t"] >= t_end), line_a[-1])

                        if random.random() > 0.15:
                            # rgba(255,255,255, 0.05~0.15) 在黑色背景上的近似灰度
                            gray = int(255 * (0.05 + random.random() * 0.1))
                            fill_color = f"#{gray:02x}{gray:02x}{gray:02x}"
                            self.canvas.create_polygon(
                                p1["x"], p1["y"], p2["x"], p2["y"], p3["x"], p3["y"], p4["x"], p4["y"],
                                fill=fill_color, outline="#1a1a1a")  # rgba(255,255,255,0.1) 近似

        # 手绘母线：绘制 Catmull-Rom 曲线与控制点
        if s["seedType"] == "custom" and self.custom_seed_points:
            curve_pts = self._sample_curve(self.custom_seed_points)
            for i in range(len(curve_pts) - 1):
                x1, y1 = curve_pts[i]
                x2, y2 = curve_pts[i + 1]
                self.canvas.create_line(x1, y1, x2, y2, fill="#ff6600", width=2)
            for x, y in self.custom_seed_points:
                self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill="#ff3300", outline="#ffffff")

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
