"""
城市线驱动向量场生成器 - 主应用
基于 Seed Curve 的非中心式扩张
"""

import tkinter as tk
from tkinter import ttk, filedialog
import math
import random

from config import T_COUNT, T_STEP, DRAW_PADDING
from utils import safe_float, safe_int
from curve import sample_curve
from exporter import export_rhino, export_dxf
from geom import split_segment_inside_outside
from street_network import (
    adaptive_cross_t_positions,
    classify_longitudinal_hierarchy,
    get_line_at_t,
    hierarchy_style,
)
import i18n
from i18n import T, RUN_MODE_OPTS, BASIS_TYPE_OPTS, SEED_TYPE_OPTS, SPACING_MODE_OPTS
from i18n import set_language, get_language
from i18n import BTN_ADD_CURVE, BTN_DRAW, BTN_DONE_DRAWING, BTN_CLEAR, BTN_RESET, BTN_GENERATE
from i18n import BTN_PARAMS, BTN_EDIT, BTN_DEL, MULTI_SEED_HINT, CURVE_PARAMS_HINT
from i18n import CURVE_SELECT_HINT, LINE_SPACING_SHORT, POS_NEG, OFFSET_XY, SPACING_MODE_SHORT
from i18n import BASIS_BLEND_FACTOR
from i18n import SPACING_SCALE_SHORT, CROSS_SPACING_SHORT, NOISE_ENABLED, ROADS_PERP, NO_CURVES_YET
from i18n import ROAD_HIERARCHY, ADAPTIVE_CROSS, CURVATURE_WEIGHT, ATTRACTOR_WEIGHT, VALUE_WEIGHT
from i18n import PARCEL_FRONTAGE_BASED, PARCEL_BLOCK_BY_BLOCK, PARCEL_CORNER_SEPARATE, PARCEL_PERTURBATION
from i18n import PARCEL_PERTURBATION_STR, DRAW_MODE_STATUS, CURVE_SPACING_MODES, SEED_TYPE_OPTS, curve_n_params, curve_n_pts
from parcel_subdivision import subdivide_blocks, rule_based_parcels
from tensor_field import (
    sample_tensor_field_grid,
    generate_streets_from_tensor_field,
    BASIS_GRID,
    BASIS_RADIAL,
    BASIS_BLEND,
)


class UrbanFieldGenerator:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(T["title"])
        self.root.configure(bg="#0a0a0a")
        self.root.geometry("1400x900")

        self.state = {}
        self.controls = {}
        self.custom_seed_curves = []
        self.selected_curve_for_params = -1
        self.editing_curve_index = -1
        self.draw_mode = False
        self.drag_curve_idx = None
        self.drag_point_idx = None
        self._canvas_custom_bound = False
        self._curve_list_frame = None
        self._export_geometry = {"polylines": [], "parcels": []}
        self._generate_after_id = None
        self._debounce_ms = 120

        self._build_ui()
        self._bind_events()
        self.update_state()

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg="#0a0a0a")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Language switcher bar at top
        lang_bar = tk.Frame(main_frame, bg="#0a0a0a", height=40)
        lang_bar.pack(side=tk.TOP, fill=tk.X)
        lang_bar.pack_propagate(False)
        lang_inner = tk.Frame(lang_bar, bg="#0a0a0a")
        lang_inner.pack(side=tk.RIGHT, padx=24, pady=8)
        self.controls["btnLangEN"] = tk.Button(
            lang_inner, text="EN", width=4,
            command=lambda: self._switch_language("en"),
            bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
            font=("JetBrains Mono", 9),
            activebackground="#3a3a3a", activeforeground="#ffffff")
        self.controls["btnLangEN"].pack(side=tk.LEFT, padx=2)
        self.controls["btnLangZH"] = tk.Button(
            lang_inner, text="中文", width=4,
            command=lambda: self._switch_language("zh"),
            bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
            font=("JetBrains Mono", 9),
            activebackground="#3a3a3a", activeforeground="#ffffff")
        self.controls["btnLangZH"].pack(side=tk.LEFT, padx=2)
        self._update_lang_buttons_state()

        panel_outer = tk.Frame(main_frame, width=400, bg="#141414")
        panel_outer.pack(side=tk.LEFT, fill=tk.Y)
        panel_outer.pack_propagate(False)

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

        def _bind_mousewheel(event):
            panel_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            panel_canvas.unbind_all("<MouseWheel>")

        panel_canvas.bind("<Enter>", _bind_mousewheel)
        panel_canvas.bind("<Leave>", _unbind_mousewheel)

        self._title_label = tk.Label(panel, text=T["title"], font=("Inter", 18, "bold"),
                 fg="#ffffff", bg="#141414", wraplength=350, justify=tk.LEFT)
        self._title_label.pack(anchor="w")
        self._subtitle_label = tk.Label(panel, text=T["subtitle"], font=("JetBrains Mono", 9),
                 fg="#888888", bg="#141414", wraplength=350, justify=tk.LEFT)
        self._subtitle_label.pack(anchor="w")

        self._section_labels = []
        self._section_labels.append(self._section_title(panel, T["section_run_mode"], wraplength=350))
        self._label_group(panel, T["run_mode"], t_key="run_mode")
        self.controls["runMode"] = ttk.Combobox(panel, values=RUN_MODE_OPTS, state="readonly", width=36)
        self.controls["runMode"].set(RUN_MODE_OPTS[1])
        self.controls["runMode"].pack(fill=tk.X, pady=(0, 10))

        self._label_group(panel, T["site_width"], t_key="site_width")
        self.controls["siteWidth"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                             insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["siteWidth"].insert(0, "1200")
        self.controls["siteWidth"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, T["site_height"], t_key="site_height")
        self.controls["siteHeight"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                               insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["siteHeight"].insert(0, "200")
        self.controls["siteHeight"].pack(fill=tk.X, pady=(0, 10))

        self._section_labels.append(self._section_title(panel, T["section_field_logic"]))
        self._label_group(panel, T["basis_type"], t_key="basis_type")
        self.controls["basisType"] = ttk.Combobox(panel, values=BASIS_TYPE_OPTS, state="readonly", width=36)
        self.controls["basisType"].set(BASIS_TYPE_OPTS[0])
        self.controls["basisType"].pack(fill=tk.X, pady=(0, 4))
        self.controls["basisType"].bind("<<ComboboxSelected>>", lambda e: self._on_basis_change())
        self._basis_params_frame = tk.Frame(panel, bg="#141414")
        self._basis_params_frame.pack(fill=tk.X, pady=(0, 16))
        self._on_basis_change()

        self._label_group(panel, T["seed_type"], t_key="seed_type")
        self.controls["seedType"] = ttk.Combobox(panel, values=SEED_TYPE_OPTS, state="readonly", width=36)
        self.controls["seedType"].set(SEED_TYPE_OPTS[0])
        self.controls["seedType"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, T["seed_rotation"], "0°", right_key="rotVal", t_key="seed_rotation")
        self.controls["seedRotation"] = tk.Scale(panel, from_=0, to=360, orient=tk.HORIZONTAL,
                                                  bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                  highlightthickness=0, showvalue=False)
        self.controls["seedRotation"].set(0)
        self.controls["seedRotation"].pack(fill=tk.X, pady=(0, 16))

        self._section_labels.append(self._section_title(panel, T["section_seed_line"]))
        self._label_group(panel, T["seed_x_offset"], "0", right_key="seedXVal", t_key="seed_x_offset")
        self.controls["seedXOffset"] = tk.Scale(panel, from_=-500, to=500, orient=tk.HORIZONTAL,
                                                bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                highlightthickness=0, showvalue=False)
        self.controls["seedXOffset"].set(0)
        self.controls["seedXOffset"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, T["seed_y_offset"], "0", right_key="seedYVal", t_key="seed_y_offset")
        self.controls["seedYOffset"] = tk.Scale(panel, from_=-200, to=200, orient=tk.HORIZONTAL,
                                                bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                highlightthickness=0, showvalue=False)
        self.controls["seedYOffset"].set(0)
        self.controls["seedYOffset"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, T["seed_length"], "0.8", right_key="seedLenVal", t_key="seed_length")
        self.controls["seedLength"] = tk.Scale(panel, from_=0.2, to=1.0, resolution=0.05, orient=tk.HORIZONTAL,
                                               bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                               highlightthickness=0, showvalue=False)
        self.controls["seedLength"].set(0.8)
        self.controls["seedLength"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, T["sine_amplitude"], t_key="sine_amplitude")
        self.controls["seedSineAmp"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                                insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["seedSineAmp"].insert(0, "50")
        self.controls["seedSineAmp"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, T["arc_curvature"], t_key="arc_curvature")
        self.controls["seedArcCurv"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                                insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["seedArcCurv"].insert(0, "200")
        self.controls["seedArcCurv"].pack(fill=tk.X, pady=(0, 8))

        self._section_labels.append(self._section_title(panel, T["section_multi_seed"]))
        self._multi_seed_hint = tk.Label(panel, text=MULTI_SEED_HINT, fg="#666666", bg="#141414",
                                         font=("Inter", 9), wraplength=350, justify=tk.LEFT)
        self._multi_seed_hint.pack(anchor="w", pady=(0, 8))
        self._curve_list_frame = tk.Frame(panel, bg="#141414")
        self._curve_list_frame.pack(fill=tk.X, pady=(0, 8))
        draw_btn_frame = tk.Frame(panel, bg="#141414")
        draw_btn_frame.pack(fill=tk.X, pady=(0, 8))
        self.controls["btnAddCurve"] = tk.Button(draw_btn_frame, text=BTN_ADD_CURVE, command=self._add_new_curve,
                                                 bg="#2a4a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                                 font=("JetBrains Mono", 10))
        self.controls["btnAddCurve"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.controls["btnDraw"] = tk.Button(draw_btn_frame, text=BTN_DRAW, command=self._toggle_draw_mode,
                                             bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                             font=("JetBrains Mono", 10))
        self.controls["btnDraw"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 2))
        self.controls["btnClear"] = tk.Button(draw_btn_frame, text=BTN_CLEAR, command=self._clear_all_curves,
                                              bg="#1a1a1a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                              font=("JetBrains Mono", 10))
        self.controls["btnClear"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        self._section_labels.append(self._section_title(panel, T["section_curve_params"]))
        self._curve_params_frame = tk.Frame(panel, bg="#141414")
        self._curve_params_frame.pack(fill=tk.X, pady=(0, 8))
        self._curve_params_hint = tk.Label(self._curve_params_frame, text=CURVE_PARAMS_HINT, fg="#666666", bg="#141414",
                                          font=("Inter", 9), wraplength=350, justify=tk.LEFT)
        self._curve_params_hint.pack(anchor="w", pady=(0, 8))
        self._curve_params_inner = tk.Frame(self._curve_params_frame, bg="#141414")
        self._curve_params_inner.pack(fill=tk.X)

        self._section_labels.append(self._section_title(panel, T["section_expansion"]))
        self._label_group(panel, T["line_spacing"], "40", right_key="spacingVal", t_key="line_spacing")
        self.controls["lineSpacing"] = tk.Scale(panel, from_=10, to=100, orient=tk.HORIZONTAL,
                                                bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                highlightthickness=0, showvalue=False)
        self.controls["lineSpacing"].set(40)
        self.controls["lineSpacing"].pack(fill=tk.X, pady=(0, 10))

        self._label_group(panel, T["pos_count"], t_key="pos_count")
        self.controls["posCount"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                             insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["posCount"].insert(0, "10")
        self.controls["posCount"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, T["neg_count"], t_key="neg_count")
        self.controls["negCount"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                             insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["negCount"].insert(0, "10")
        self.controls["negCount"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, T["spacing_mode"], t_key="spacing_mode")
        self.controls["spacingMode"] = ttk.Combobox(panel, values=SPACING_MODE_OPTS, state="readonly", width=36)
        self.controls["spacingMode"].set(SPACING_MODE_OPTS[0])
        self.controls["spacingMode"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, T["spacing_scale"], "1.0", right_key="scaleVal", t_key="spacing_scale")
        self.controls["spacingScale"] = tk.Scale(panel, from_=0.5, to=2.0, resolution=0.1, orient=tk.HORIZONTAL,
                                                 bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                 highlightthickness=0, showvalue=False)
        self.controls["spacingScale"].set(1.0)
        self.controls["spacingScale"].pack(fill=tk.X, pady=(0, 14))

        self._section_labels.append(self._section_title(panel, T["section_noise"]))
        self.controls["noiseEnabled"] = tk.BooleanVar(value=False)
        self._noise_cb = tk.Checkbutton(panel, text=NOISE_ENABLED, variable=self.controls["noiseEnabled"],
                                       command=self.update_state,
                                       bg="#141414", fg="#e0e0e0", selectcolor="#1a1a1a", activebackground="#141414",
                                       activeforeground="#e0e0e0", wraplength=350, justify=tk.LEFT)
        self._noise_cb.pack(anchor="w", pady=(0, 8))

        self._label_group(panel, T["noise_scale"], "0.005", right_key="noiseScaleVal", t_key="noise_scale")
        self.controls["noiseScale"] = tk.Scale(panel, from_=0.001, to=0.02, resolution=0.001, orient=tk.HORIZONTAL,
                                               bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                               highlightthickness=0, showvalue=False)
        self.controls["noiseScale"].set(0.005)
        self.controls["noiseScale"].pack(fill=tk.X, pady=(0, 16))

        self._label_group(panel, T["noise_strength"], "20", right_key="noiseStrVal", t_key="noise_strength")
        self.controls["noiseStrength"] = tk.Scale(panel, from_=0, to=100, orient=tk.HORIZONTAL,
                                                  bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                  highlightthickness=0, showvalue=False)
        self.controls["noiseStrength"].set(20)
        self.controls["noiseStrength"].pack(fill=tk.X, pady=(0, 12))

        self._section_labels.append(self._section_title(panel, T["section_street"]))
        cb_row = tk.Frame(panel, bg="#141414")
        cb_row.pack(fill=tk.X, pady=(0, 4))
        self.controls["roadsPerpendicular"] = tk.BooleanVar(value=True)
        tk.Checkbutton(cb_row, text="⊥", variable=self.controls["roadsPerpendicular"], command=self.update_state,
                      bg="#141414", fg="#e0e0e0", selectcolor="#1a1a1a", activebackground="#141414",
                      activeforeground="#e0e0e0", font=("Inter", 9)).pack(side=tk.LEFT, padx=(0, 8))
        self.controls["roadHierarchy"] = tk.BooleanVar(value=True)
        tk.Checkbutton(cb_row, text="Hierarchy", variable=self.controls["roadHierarchy"], command=self.update_state,
                      bg="#141414", fg="#e0e0e0", selectcolor="#1a1a1a", activebackground="#141414",
                      activeforeground="#e0e0e0", font=("Inter", 9)).pack(side=tk.LEFT, padx=(0, 8))
        self.controls["adaptiveCross"] = tk.BooleanVar(value=True)
        tk.Checkbutton(cb_row, text="Adaptive", variable=self.controls["adaptiveCross"], command=self.update_state,
                      bg="#141414", fg="#e0e0e0", selectcolor="#1a1a1a", activebackground="#141414",
                      activeforeground="#e0e0e0", font=("Inter", 9)).pack(side=tk.LEFT)
        self._label_group(panel, T["cross_spacing"], "80", right_key="crossVal", t_key="cross_spacing")
        self.controls["crossSpacing"] = tk.Scale(panel, from_=40, to=300, orient=tk.HORIZONTAL,
                                                 bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                 highlightthickness=0, showvalue=False)
        self.controls["crossSpacing"].set(80)
        self.controls["crossSpacing"].pack(fill=tk.X, pady=(0, 4))
        adapt_row = tk.Frame(panel, bg="#141414")
        adapt_row.pack(fill=tk.X, pady=(0, 8))
        adapt_row.columnconfigure((0, 1, 2), weight=1)
        for col, (key, lbl, default) in enumerate([
            ("curvatureWeight", "Curv", 0.4), ("attractorWeight", "Attr", 0.3), ("valueWeight", "Value", 0.2)
        ]):
            f = tk.Frame(adapt_row, bg="#141414")
            f.grid(row=0, column=col, sticky="ew", padx=2)
            tk.Label(f, text=lbl, fg="#666", bg="#141414", font=("Inter", 8)).pack(anchor="w")
            s = tk.Scale(f, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL,
                        bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a", highlightthickness=0, showvalue=False,
                        command=lambda v, k=key: self._update_adaptive_labels())
            s.set(default)
            s.pack(fill=tk.X)
            self.controls[key] = s
            val_key = {"curvatureWeight": "curvWeightVal", "attractorWeight": "attrWeightVal", "valueWeight": "valWeightVal"}[key]
            vl = tk.Label(f, text=str(default), fg="#888", bg="#141414", font=("Inter", 8))
            vl.pack(anchor="e")
            self.controls[val_key] = vl

        self._label_group(panel, T["parcel_min"], t_key="parcel_min")
        self.controls["pMin"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                         insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["pMin"].insert(0, "15")
        self.controls["pMin"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, T["parcel_max"], t_key="parcel_max")
        self.controls["pMax"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                         insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["pMax"].insert(0, "45")
        self.controls["pMax"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, T["parcel_min_area"], t_key="parcel_min_area")
        self.controls["pMinArea"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                             insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["pMinArea"].insert(0, "50")
        self.controls["pMinArea"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(panel, T["parcel_max_depth"], t_key="parcel_max_depth")
        self.controls["pMaxDepth"] = tk.Entry(panel, bg="#1a1a1a", fg="#e0e0e0",
                                              insertbackground="#e0e0e0", relief=tk.SOLID, bd=1)
        self.controls["pMaxDepth"].insert(0, "200")
        self.controls["pMaxDepth"].pack(fill=tk.X, pady=(0, 8))

        parcel_cb_frame = tk.Frame(panel, bg="#141414")
        parcel_cb_frame.pack(fill=tk.X, pady=(0, 4))
        parcel_cb_frame.columnconfigure((0, 1), weight=1)
        for row, col, (key, lbl) in [
            (0, 0, ("parcelFrontageBased", "Frontage")), (0, 1, ("parcelBlockByBlock", "Block")),
            (1, 0, ("parcelCornerSeparate", "Corner")), (1, 1, ("parcelPerturbation", "Perturb"))
        ]:
            self.controls[key] = tk.BooleanVar(value=(key != "parcelPerturbation"))
            tk.Checkbutton(parcel_cb_frame, text=lbl, variable=self.controls[key], command=self.update_state,
                          bg="#141414", fg="#e0e0e0", selectcolor="#1a1a1a", activebackground="#141414",
                          activeforeground="#e0e0e0", font=("Inter", 9)).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=2)
        self._label_group(panel, PARCEL_PERTURBATION_STR, "0.02", right_key="pertStrVal", t_key="PARCEL_PERTURBATION_STR")
        self.controls["parcelPerturbationStr"] = tk.Scale(panel, from_=0, to=0.1, resolution=0.005,
                                                        orient=tk.HORIZONTAL, bg="#141414", fg="#e0e0e0",
                                                        troughcolor="#2a2a2a", highlightthickness=0, showvalue=False,
                                                        command=lambda v: self.update_state())
        self.controls["parcelPerturbationStr"].set(0.02)
        self.controls["parcelPerturbationStr"].pack(fill=tk.X, pady=(0, 16))

        btn_frame = tk.Frame(panel, bg="#141414")
        btn_frame.pack(fill=tk.X)
        self.controls["btnReset"] = tk.Button(btn_frame, text=BTN_RESET, command=self._reset,
                                             bg="#1a1a1a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                             font=("JetBrains Mono", 10),
                                             activebackground="#ffffff", activeforeground="#0a0a0a")
        self.controls["btnReset"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.controls["btnGenerate"] = tk.Button(btn_frame, text=BTN_GENERATE, command=self.generate,
                                                bg="#ffffff", fg="#0a0a0a", relief=tk.SOLID, bd=1,
                                                font=("JetBrains Mono", 10, "bold"),
                                                activebackground="#ffffff", activeforeground="#0a0a0a")
        self.controls["btnGenerate"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        export_frame = tk.Frame(panel, bg="#141414")
        export_frame.pack(fill=tk.X, pady=(16, 0))
        self._export_label = tk.Label(export_frame, text=T["export_rhino"], fg="#888888", bg="#141414",
                                      font=("Inter", 10), wraplength=350, justify=tk.LEFT)
        self._export_label.pack(anchor="w")
        exp_btn_frame = tk.Frame(export_frame, bg="#141414")
        exp_btn_frame.pack(fill=tk.X, pady=(4, 0))
        self.controls["btnExportRhino"] = tk.Button(exp_btn_frame, text=T["export_py"], command=self._export_rhino,
                                                   bg="#2a4a6a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                                   font=("JetBrains Mono", 10))
        self.controls["btnExportRhino"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.controls["btnExportDxf"] = tk.Button(exp_btn_frame, text=T["export_dxf"], command=self._export_dxf,
                                                  bg="#2a4a6a", fg="#e0e0e0", relief=tk.SOLID, bd=1,
                                                  font=("JetBrains Mono", 10))
        self.controls["btnExportDxf"].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        self._footer_label = tk.Label(panel, text=T["footer"],
                                      fg="#888888", bg="#141414", font=("Inter", 9), wraplength=350, justify=tk.LEFT)
        self._footer_label.pack(pady=(32, 0))

        canvas_frame = tk.Frame(main_frame, bg="#050505")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=32, pady=32)
        self.canvas = tk.Canvas(canvas_frame, bg="#050505", highlightthickness=0)
        self.canvas.pack(expand=True)
        self.status_label = tk.Label(canvas_frame, text=T["status_default"],
                                    fg="#4d4d4d", bg="#050505", font=("JetBrains Mono", 9),
                                    justify=tk.RIGHT, wraplength=280)
        self.status_label.place(relx=1.0, rely=1.0, anchor="se", x=-32, y=-32)

    def _section_title(self, parent, text, wraplength=350):
        lbl = tk.Label(parent, text=text, font=("Inter", 11, "bold"), fg="#ffffff", bg="#141414",
                       wraplength=wraplength, justify=tk.LEFT)
        lbl.pack(anchor="w", pady=(14, 4))
        return lbl

    def _label_group(self, parent, left, right=None, right_key=None, t_key=None):
        frame = tk.Frame(parent, bg="#141414")
        frame.pack(fill=tk.X)
        left_lbl = tk.Label(frame, text=left, fg="#888888", bg="#141414", font=("Inter", 10), wraplength=320, justify=tk.LEFT)
        left_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if t_key:
            if not hasattr(self, "_label_refs"):
                self._label_refs = []
            self._label_refs.append((left_lbl, t_key))
        if right_key:
            lbl = tk.Label(frame, text=right or "", fg="#888888", bg="#141414", font=("Inter", 10))
            lbl.pack(side=tk.RIGHT)
            self.controls[right_key] = lbl
        elif right is not None:
            tk.Label(frame, text=right, fg="#888888", bg="#141414", font=("Inter", 10)).pack(side=tk.RIGHT)

    def _get_run_mode(self):
        val = self.controls["runMode"].get()
        if "A" in val or "Flow" in val:
            return "A"
        if "C" in val or "Parcel" in val:
            return "C"
        return "B"

    def _update_adaptive_labels(self):
        for k, ctrl in [("curvWeightVal", "curvatureWeight"), ("attrWeightVal", "attractorWeight"), ("valWeightVal", "valueWeight")]:
            if k in self.controls and ctrl in self.controls and self.controls[ctrl].winfo_exists():
                self.controls[k].config(text=f"{self.controls[ctrl].get():.1f}")
        self.update_state()

    def _get_field_type(self):
        """For offset engine (B/C): default to parallel"""
        return "1"

    def _get_basis_type(self):
        val = self.controls["basisType"].get()
        if "Radial" in val or "径向" in val:
            return BASIS_RADIAL
        if "Blend" in val or "混合" in val:
            return BASIS_BLEND
        return BASIS_GRID

    def _on_basis_change(self):
        """Show blend factor when basis is Blend"""
        for w in self._basis_params_frame.winfo_children():
            w.destroy()
        if self._get_basis_type() == BASIS_BLEND:
            self._label_group(self._basis_params_frame, BASIS_BLEND_FACTOR, "0.5", right_key="basisBlendVal", t_key="BASIS_BLEND_FACTOR")
            self.controls["basisBlendFactor"] = tk.Scale(
                self._basis_params_frame, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL,
                bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                highlightthickness=0, showvalue=False,
                command=lambda v: self._update_basis_blend_label())
            self.controls["basisBlendFactor"].set(0.5)
            self.controls["basisBlendFactor"].pack(fill=tk.X, pady=(0, 4))
            self._bind_recursive(self._basis_params_frame, self.update_state)
        if "seedType" in self.controls:
            self.update_state()

    def _update_basis_blend_label(self):
        if "basisBlendVal" in self.controls and "basisBlendFactor" in self.controls:
            self.controls["basisBlendVal"].config(text=f"{self.controls['basisBlendFactor'].get():.1f}")
        self.update_state()

    def _get_seed_type(self):
        val = self.controls["seedType"].get()
        if "Sine" in val or "正弦" in val:
            return "sine"
        if "Arc" in val or "弧" in val:
            return "arc"
        if "Custom" in val or "Hand" in val or "自定义" in val or "手绘" in val:
            return "custom"
        return "straight"

    def _get_spacing_mode(self):
        val = self.controls["spacingMode"].get()
        if "Exponential" in val:
            return "exponential"
        if "Fibonacci" in val:
            return "fibonacci"
        return "linear"

    def _get_curve_params_defaults(self):
        return {
            "fieldType": self._get_field_type(),
            "lineSpacing": safe_float(self.controls["lineSpacing"].get(), 40),
            "posCount": safe_int(self.controls["posCount"].get(), 10),
            "negCount": safe_int(self.controls["negCount"].get(), 10),
            "spacingMode": self._get_spacing_mode(),
            "spacingScale": safe_float(self.controls["spacingScale"].get(), 1.0),
            "offsetX": 0,
            "offsetY": 0,
            "crossSpacing": safe_float(self.controls["crossSpacing"].get(), 80),
        }

    def _get_curve_points(self, curve):
        if isinstance(curve, dict):
            return curve["points"]
        return curve

    def _ensure_curve_dict(self, curve):
        if isinstance(curve, list):
            return {"points": curve, "params": self._get_curve_params_defaults()}
        return curve

    def _add_new_curve(self):
        self.controls["seedType"].set(SEED_TYPE_OPTS[3])
        self.custom_seed_curves.append({"points": [], "params": self._get_curve_params_defaults()})
        self.editing_curve_index = len(self.custom_seed_curves) - 1
        self.draw_mode = True
        self.controls["btnDraw"].config(text=BTN_DONE_DRAWING, bg="#3a5a3a")
        self.status_label.config(text=DRAW_MODE_STATUS.format(self.editing_curve_index + 1))
        self._refresh_curve_list()
        self.update_state()

    def _edit_curve(self, idx):
        if 0 <= idx < len(self.custom_seed_curves):
            self.controls["seedType"].set(SEED_TYPE_OPTS[3])
            self.editing_curve_index = idx
            self.draw_mode = True
            self.controls["btnDraw"].config(text=BTN_DONE_DRAWING, bg="#3a5a3a")
            self.status_label.config(text=DRAW_MODE_STATUS.format(idx + 1))
            self._refresh_curve_list()
            self.update_state()

    def _select_curve_params(self, idx):
        if 0 <= idx < len(self.custom_seed_curves):
            self.selected_curve_for_params = idx
            self._build_curve_params_ui()
            self.update_state()

    def _build_curve_params_ui(self):
        if not hasattr(self, "_curve_params_inner") or self._curve_params_inner is None:
            return
        for w in self._curve_params_inner.winfo_children():
            w.destroy()
        if self.selected_curve_for_params < 0 or self.selected_curve_for_params >= len(self.custom_seed_curves):
            tk.Label(self._curve_params_inner, text=CURVE_SELECT_HINT, fg="#555555", bg="#141414",
                     font=("Inter", 9), wraplength=350, justify=tk.LEFT).pack(anchor="w")
            return
        curve = self.custom_seed_curves[self.selected_curve_for_params]
        if isinstance(curve, list):
            return
        p = curve.setdefault("params", self._get_curve_params_defaults())
        idx = self.selected_curve_for_params

        def _on_change(key, val):
            p[key] = val
            self.update_state()

        tk.Label(self._curve_params_inner, text=curve_n_params(idx + 1), fg="#e0e0e0", bg="#141414",
                 font=("Inter", 10, "bold")).pack(anchor="w", pady=(0, 8))
        row = tk.Frame(self._curve_params_inner, bg="#141414")
        row.pack(fill=tk.X, pady=2)
        row.columnconfigure(1, weight=1)
        tk.Label(row, text=LINE_SPACING_SHORT, fg="#888888", bg="#141414", font=("Inter", 9), wraplength=140, justify=tk.LEFT).grid(row=0, column=0, sticky="w", padx=(0, 8))
        sp = tk.Scale(row, from_=10, to=100, orient=tk.HORIZONTAL, bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                      highlightthickness=0, showvalue=False, command=lambda v: _on_change("lineSpacing", float(v)))
        sp.set(p.get("lineSpacing", 40))
        sp.grid(row=0, column=1, sticky="ew")
        tk.Label(row, text=str(int(p.get("lineSpacing", 40))), fg="#888888", bg="#141414", font=("Inter", 9)).grid(row=0, column=2, padx=(4, 0))
        row2 = tk.Frame(self._curve_params_inner, bg="#141414")
        row2.pack(fill=tk.X, pady=2)
        row2.columnconfigure(1, weight=1)
        tk.Label(row2, text=POS_NEG, fg="#888888", bg="#141414", font=("Inter", 9), wraplength=140, justify=tk.LEFT).grid(row=0, column=0, sticky="w", padx=(0, 8))
        pe = tk.Entry(row2, bg="#1a1a1a", fg="#e0e0e0", width=6)
        pe.insert(0, str(p.get("posCount", 10)))
        pe.grid(row=0, column=1, sticky="w", padx=(0, 4))
        ne = tk.Entry(row2, bg="#1a1a1a", fg="#e0e0e0", width=6)
        ne.insert(0, str(p.get("negCount", 10)))
        ne.grid(row=0, column=2, sticky="w")

        def _apply_counts():
            try:
                p["posCount"] = int(float(pe.get()))
                p["negCount"] = int(float(ne.get()))
                self.update_state()
            except Exception:
                pass

        pe.bind("<KeyRelease>", lambda e: _apply_counts())
        ne.bind("<KeyRelease>", lambda e: _apply_counts())
        row3 = tk.Frame(self._curve_params_inner, bg="#141414")
        row3.pack(fill=tk.X, pady=2)
        row3.columnconfigure(1, weight=1)
        tk.Label(row3, text=OFFSET_XY, fg="#888888", bg="#141414", font=("Inter", 9), wraplength=140, justify=tk.LEFT).grid(row=0, column=0, sticky="w", padx=(0, 8))
        ox = tk.Scale(row3, from_=-100, to=100, orient=tk.HORIZONTAL, bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                      highlightthickness=0, showvalue=False, command=lambda v: _on_change("offsetX", float(v)))
        ox.set(p.get("offsetX", 0))
        ox.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        oy = tk.Scale(row3, from_=-100, to=100, orient=tk.HORIZONTAL, bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                      highlightthickness=0, showvalue=False, command=lambda v: _on_change("offsetY", float(v)))
        oy.set(p.get("offsetY", 0))
        oy.grid(row=0, column=2, sticky="ew")
        row4a = tk.Frame(self._curve_params_inner, bg="#141414")
        row4a.pack(fill=tk.X, pady=2)
        row4a.columnconfigure(1, weight=1)
        tk.Label(row4a, text=SPACING_MODE_SHORT, fg="#888888", bg="#141414", font=("Inter", 9), wraplength=140, justify=tk.LEFT).grid(row=0, column=0, sticky="w", padx=(0, 8))
        _sm_map = CURVE_SPACING_MODES
        _sm_rev = {v: k for k, v in _sm_map.items()}
        sm_combo = ttk.Combobox(row4a, values=list(_sm_map.keys()), state="readonly", width=18)
        sm_combo.set(_sm_rev.get(p.get("spacingMode", "linear"), list(_sm_map.keys())[0]))
        sm_combo.grid(row=0, column=1, sticky="ew")
        sm_combo.bind("<<ComboboxSelected>>", lambda e: _on_change("spacingMode", _sm_map.get(sm_combo.get(), "linear")))
        row4 = tk.Frame(self._curve_params_inner, bg="#141414")
        row4.pack(fill=tk.X, pady=2)
        row4.columnconfigure(1, weight=1)
        tk.Label(row4, text=SPACING_SCALE_SHORT, fg="#888888", bg="#141414", font=("Inter", 9), wraplength=140, justify=tk.LEFT).grid(row=0, column=0, sticky="w", padx=(0, 8))
        sc = tk.Scale(row4, from_=0.5, to=2.0, resolution=0.1, orient=tk.HORIZONTAL, bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                      highlightthickness=0, showvalue=False, command=lambda v: _on_change("spacingScale", float(v)))
        sc.set(p.get("spacingScale", 1.0))
        sc.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        tk.Label(row4, text=f"{p.get('spacingScale', 1.0):.1f}", fg="#888888", bg="#141414", font=("Inter", 9)).grid(row=0, column=2, padx=(4, 0))
        row5 = tk.Frame(self._curve_params_inner, bg="#141414")
        row5.pack(fill=tk.X, pady=2)
        row5.columnconfigure(1, weight=1)
        tk.Label(row5, text=CROSS_SPACING_SHORT, fg="#888888", bg="#141414", font=("Inter", 9), wraplength=140, justify=tk.LEFT).grid(row=0, column=0, sticky="w", padx=(0, 8))
        lbl_cross = tk.Label(row5, text=str(int(p.get("crossSpacing", 80))), fg="#888888", bg="#141414", font=("Inter", 9), width=4)

        def _on_cross(v):
            _on_change("crossSpacing", float(v))
            lbl_cross.config(text=str(int(float(v))))

        cross_sp = tk.Scale(row5, from_=20, to=300, orient=tk.HORIZONTAL, bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                           highlightthickness=0, showvalue=False, command=_on_cross)
        cross_sp.set(p.get("crossSpacing", 80))
        cross_sp.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        lbl_cross.grid(row=0, column=2, padx=(4, 0))

    def _delete_curve(self, idx):
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
            lbl = tk.Label(row, text=curve_n_pts(i + 1, n), fg="#888888", bg="#141414", font=("Inter", 10))
            lbl.pack(side=tk.LEFT)
            btn_params = tk.Button(row, text=BTN_PARAMS, command=lambda idx=i: self._select_curve_params(idx),
                                   bg="#2a3a4a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
            btn_params.pack(side=tk.RIGHT, padx=2)
            btn_edit = tk.Button(row, text=BTN_EDIT, command=lambda idx=i: self._edit_curve(idx),
                                 bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
            btn_edit.pack(side=tk.RIGHT, padx=2)
            btn_del = tk.Button(row, text=BTN_DEL, command=lambda idx=i: self._delete_curve(idx),
                                bg="#4a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
            btn_del.pack(side=tk.RIGHT)
        if not self.custom_seed_curves:
            tk.Label(self._curve_list_frame, text=NO_CURVES_YET, fg="#555555", bg="#141414",
                     font=("Inter", 9), wraplength=350, justify=tk.LEFT).pack(anchor="w")

    def _toggle_draw_mode(self):
        if self.draw_mode:
            self._exit_draw_mode()
        else:
            if not self.custom_seed_curves:
                self._add_new_curve()
                return
            if self.editing_curve_index < 0:
                self.editing_curve_index = 0
            self.controls["seedType"].set(SEED_TYPE_OPTS[3])
            self.draw_mode = True
            self.controls["btnDraw"].config(text=BTN_DONE_DRAWING, bg="#3a5a3a")
            self.status_label.config(text=DRAW_MODE_STATUS.format(self.editing_curve_index + 1))
        self.update_state()

    def _exit_draw_mode(self):
        self.draw_mode = False
        self.editing_curve_index = -1
        self.controls["btnDraw"].config(text=BTN_DRAW, bg="#2a2a2a")
        self.status_label.config(text=T["status_default"])
        self._refresh_curve_list()

    def _find_point_at(self, canvas_x, canvas_y, radius=10):
        lx, ly = self._unpad(canvas_x, canvas_y)
        best_ci, best_pi, best_d = -1, -1, radius * radius
        for ci, curve in enumerate(self.custom_seed_curves):
            pts = self._get_curve_points(curve)
            for pi, (px, py) in enumerate(pts):
                d = (lx - px) ** 2 + (ly - py) ** 2
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
            lx, ly = self._unpad(event.x, event.y)
            self._get_curve_points(self.custom_seed_curves[self.editing_curve_index]).append((lx, ly))
            self._refresh_curve_list()
            self.update_state()

    def _on_canvas_drag(self, event):
        if self.drag_curve_idx is not None and self.drag_point_idx is not None:
            pts = self._get_curve_points(self.custom_seed_curves[self.drag_curve_idx])
            if 0 <= self.drag_point_idx < len(pts):
                lx, ly = self._unpad(event.x, event.y)
                pts[self.drag_point_idx] = (lx, ly)
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

    def update_state(self):
        self.state["runMode"] = self._get_run_mode()
        self.state["fieldType"] = self._get_field_type()
        self.state["basisType"] = self._get_basis_type()
        self.state["basisBlendFactor"] = safe_float(
            self.controls["basisBlendFactor"].get(), 0.5) if "basisBlendFactor" in self.controls and self.controls["basisBlendFactor"].winfo_exists() else 0.5
        self.state["siteWidth"] = safe_float(self.controls["siteWidth"].get(), 1200)
        self.state["siteHeight"] = safe_float(self.controls["siteHeight"].get(), 200)
        self.state["seedType"] = self._get_seed_type()
        self.state["seedRotation"] = safe_float(self.controls["seedRotation"].get(), 0)
        self.state["seedXOffset"] = safe_float(self.controls["seedXOffset"].get(), 0)
        self.state["seedYOffset"] = safe_float(self.controls["seedYOffset"].get(), 0)
        self.state["seedLength"] = safe_float(self.controls["seedLength"].get(), 0.8)
        self.state["seedSineAmp"] = safe_float(self.controls["seedSineAmp"].get(), 50)
        self.state["seedArcCurv"] = safe_float(self.controls["seedArcCurv"].get(), 200)
        self.state["lineSpacing"] = safe_float(self.controls["lineSpacing"].get(), 40)
        self.state["posCount"] = safe_int(self.controls["posCount"].get(), 10)
        self.state["negCount"] = safe_int(self.controls["negCount"].get(), 10)
        self.state["spacingMode"] = self._get_spacing_mode()
        self.state["spacingScale"] = safe_float(self.controls["spacingScale"].get(), 1.0)
        self.state["noiseEnabled"] = self.controls["noiseEnabled"].get()
        self.state["noiseScale"] = safe_float(self.controls["noiseScale"].get(), 0.005)
        self.state["noiseStrength"] = safe_float(self.controls["noiseStrength"].get(), 20)
        self.state["crossSpacing"] = safe_float(self.controls["crossSpacing"].get(), 80)
        self.state["roadsPerpendicular"] = self.controls["roadsPerpendicular"].get()
        self.state["roadHierarchy"] = self.controls["roadHierarchy"].get() if "roadHierarchy" in self.controls else True
        self.state["adaptiveCross"] = self.controls["adaptiveCross"].get() if "adaptiveCross" in self.controls else True
        self.state["curvatureWeight"] = safe_float(self.controls["curvatureWeight"].get(), 0.4) if "curvatureWeight" in self.controls else 0.4
        self.state["attractorWeight"] = safe_float(self.controls["attractorWeight"].get(), 0.3) if "attractorWeight" in self.controls else 0.3
        self.state["valueWeight"] = safe_float(self.controls["valueWeight"].get(), 0.2) if "valueWeight" in self.controls else 0.2
        self.state["pMin"] = safe_float(self.controls["pMin"].get(), 15)
        self.state["pMax"] = safe_float(self.controls["pMax"].get(), 45)
        self.state["pMinArea"] = safe_float(self.controls["pMinArea"].get(), 50) if "pMinArea" in self.controls else 50
        self.state["pMaxDepth"] = safe_float(self.controls["pMaxDepth"].get(), 200) if "pMaxDepth" in self.controls else 200
        self.state["pDepth"] = safe_float(self.controls["pDepth"].get(), 10) if "pDepth" in self.controls else 10
        self.state["parcelFrontageBased"] = self.controls["parcelFrontageBased"].get() if "parcelFrontageBased" in self.controls else True
        self.state["parcelBlockByBlock"] = self.controls["parcelBlockByBlock"].get() if "parcelBlockByBlock" in self.controls else True
        self.state["parcelCornerSeparate"] = self.controls["parcelCornerSeparate"].get() if "parcelCornerSeparate" in self.controls else True
        self.state["parcelPerturbation"] = self.controls["parcelPerturbation"].get() if "parcelPerturbation" in self.controls else False
        self.state["parcelPerturbationStr"] = safe_float(self.controls["parcelPerturbationStr"].get(), 0.02) if "parcelPerturbationStr" in self.controls else 0.02

        if "pertStrVal" in self.controls and "parcelPerturbationStr" in self.state:
            self.controls["pertStrVal"].config(text=f"{self.state['parcelPerturbationStr']:.3f}")
        self.controls["rotVal"].config(text=f"{self.state['seedRotation']}°")
        self.controls["seedXVal"].config(text=str(int(self.state["seedXOffset"])))
        self.controls["seedYVal"].config(text=str(int(self.state["seedYOffset"])))
        self.controls["seedLenVal"].config(text=f"{self.state['seedLength']:.2f}")
        self.controls["spacingVal"].config(text=str(self.state["lineSpacing"]))
        self.controls["scaleVal"].config(text=f"{self.state['spacingScale']:.1f}")
        self.controls["noiseScaleVal"].config(text=str(self.state["noiseScale"]))
        self.controls["noiseStrVal"].config(text=str(int(self.state["noiseStrength"])))
        self.controls["crossVal"].config(text=str(int(self.state["crossSpacing"])))
        for k, v in [("curvWeightVal", "curvatureWeight"), ("attrWeightVal", "attractorWeight"), ("valWeightVal", "valueWeight")]:
            if k in self.controls and v in self.state:
                self.controls[k].config(text=f"{self.state[v]:.1f}")

        if self.draw_mode and self.state["seedType"] != "custom":
            self._exit_draw_mode()
        if self.state["seedType"] == "custom" and self._curve_list_frame:
            self._refresh_curve_list()
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
        self._schedule_generate()

    def _schedule_generate(self):
        """Debounce: 仅在实际生成前等待最后一次变更"""
        if self._generate_after_id:
            self.root.after_cancel(self._generate_after_id)
        self._generate_after_id = self.root.after(self._debounce_ms, self._do_scheduled_generate)

    def _do_scheduled_generate(self):
        self._generate_after_id = None
        self.generate()

    def resize_canvas(self):
        w = int(self.state["siteWidth"])
        h = int(self.state["siteHeight"])
        self.canvas.config(width=w + 2 * DRAW_PADDING, height=h + 2 * DRAW_PADDING)

    def _pad(self, x, y):
        """逻辑坐标转画布坐标"""
        return x + DRAW_PADDING, y + DRAW_PADDING

    def _unpad(self, cx, cy):
        """画布坐标转逻辑坐标"""
        return cx - DRAW_PADDING, cy - DRAW_PADDING

    def _draw_cross_glyph(self, x, y, ux, uy, vx, vy, half_len=8, fill="#888888", width=1):
        """在 (x,y) 绘制十字短线方向纹理：沿 u 和 v 方向各一条短线"""
        ax, ay = self._pad(x, y)
        # u 方向短线
        p1x = x + ux * half_len
        p1y = y + uy * half_len
        m1x = x - ux * half_len
        m1y = y - uy * half_len
        a1x, a1y = self._pad(p1x, p1y)
        b1x, b1y = self._pad(m1x, m1y)
        self.canvas.create_line(a1x, a1y, b1x, b1y, fill=fill, width=width)
        # v 方向短线
        p2x = x + vx * half_len
        p2y = y + vy * half_len
        m2x = x - vx * half_len
        m2y = y - vy * half_len
        a2x, a2y = self._pad(p2x, p2y)
        b2x, b2y = self._pad(m2x, m2y)
        self.canvas.create_line(a2x, a2y, b2x, b2y, fill=fill, width=width)

    def _draw_line_segment(self, p0, p1, fill, width, dashed_outside=True):
        """绘制线段，矩形内实线、矩形外虚线。全在内则直接绘制以加速"""
        w, h = self.state["siteWidth"], self.state["siteHeight"]
        x0, y0, x1, y1 = p0[0], p0[1], p1[0], p1[1]
        in0 = 0 <= x0 <= w and 0 <= y0 <= h
        in1 = 0 <= x1 <= w and 0 <= y1 <= h
        if in0 and in1:
            ax, ay = self._pad(x0, y0)
            bx, by = self._pad(x1, y1)
            self.canvas.create_line(ax, ay, bx, by, fill=fill, width=width)
            return
        parts = split_segment_inside_outside(p0, p1, 0, 0, w, h)
        for kind, seg in parts:
            a, b = seg[0], seg[1]
            ax, ay = self._pad(a[0], a[1])
            bx, by = self._pad(b[0], b[1])
            dash = (4, 4) if (kind == "outside" and dashed_outside) else ()
            self.canvas.create_line(ax, ay, bx, by, fill=fill, width=width, dash=dash)

    def generate(self):
        if self._generate_after_id:
            self.root.after_cancel(self._generate_after_id)
            self._generate_after_id = None
        self.canvas.delete("all")
        s = self.state
        basis = s.get("basisType", BASIS_GRID)
        cx = s["siteWidth"] / 2
        cy = s["siteHeight"] / 2
        blend = s.get("basisBlendFactor", 0.5)
        line_spacing = s.get("lineSpacing", 40)
        pos_count = s.get("posCount", 10)
        neg_count = s.get("negCount", 10)
        cross_spacing = s.get("crossSpacing", 80)

        lines, xs, ys = generate_streets_from_tensor_field(
            s["siteWidth"], s["siteHeight"],
            basis, cx, cy, blend_factor=blend,
            line_spacing=line_spacing, pos_count=pos_count, neg_count=neg_count,
            cross_spacing=cross_spacing,
        )
        lines_by_curve = [lines] if lines else []
        cross_spacings = [cross_spacing]
        curve_arrays_by_curve = [(xs, ys)]

        self.draw_result(lines_by_curve, cross_spacings, curve_arrays_by_curve)

    def draw_result(self, lines_by_curve, cross_spacings=None, curve_arrays_by_curve=None):
        s = self.state
        cross_spacings = cross_spacings or [s["crossSpacing"]]
        curve_arrays_by_curve = curve_arrays_by_curve or []
        self._export_geometry = {"polylines": [], "parcels": []}

        pw, ph = s["siteWidth"], s["siteHeight"]
        self.canvas.create_rectangle(DRAW_PADDING, DRAW_PADDING, DRAW_PADDING + pw, DRAW_PADDING + ph,
                                     outline="#555555", width=2, dash=(4, 4))
        curve_colors = ["#ff6600", "#66ff00", "#0066ff", "#ff00ff", "#00ffff"]
        perp = s.get("roadsPerpendicular", True)
        use_hierarchy = s.get("roadHierarchy", True)
        use_adaptive = s.get("adaptiveCross", True)
        main_color, main_w = "#b3b3b3", 1
        cross_color, cross_w = "#4d4d4d", 0.5

        # Mode A: 张量场十字短线可视化
        if s["runMode"] == "A":
            # 绘制张量场十字/短线方向纹理
            basis = s.get("basisType", BASIS_GRID)
            cx = s["siteWidth"] / 2
            cy = s["siteHeight"] / 2
            blend = s.get("basisBlendFactor", 0.5)
            samples = sample_tensor_field_grid(
                s["siteWidth"], s["siteHeight"],
                basis, cx, cy, blend_factor=blend, grid_step=25
            )
            for (x, y, ux, uy, vx, vy) in samples:
                self._draw_cross_glyph(x, y, ux, uy, vx, vy, half_len=10, fill="#66aaff", width=1)
        else:
            for curve_idx, lines in enumerate(lines_by_curve):
                if not lines:
                    continue
                curve_color = curve_colors[curve_idx % len(curve_colors)] if len(lines_by_curve) > 1 else "#ff3300"
                if s["runMode"] in ("B", "C"):
                    sorted_lines = sorted(lines, key=lambda ln: abs(ln[0].get("offset", 0)))
                    hierarchy = classify_longitudinal_hierarchy(lines) if use_hierarchy else []
                    line_level = {idx: level for idx, level in hierarchy}

                    for line_idx, line in enumerate(lines):
                        pts = [(p["x"], p["y"]) for p in line]
                        self._export_geometry["polylines"].append(pts)
                        if use_hierarchy and line_idx in line_level:
                            w, fill = hierarchy_style(line_level[line_idx])
                        else:
                            fill, w = (cross_color, cross_w) if perp else (main_color, main_w)
                        for i in range(len(pts) - 1):
                            self._draw_line_segment(pts[i], pts[i + 1], fill, w)

                    cs = cross_spacings[curve_idx] if curve_idx < len(cross_spacings) else s["crossSpacing"]
                    xs, ys = ([], [])
                    if curve_idx < len(curve_arrays_by_curve):
                        xs, ys = curve_arrays_by_curve[curve_idx]
                    value_field = None
                    if use_adaptive and xs and ys:
                        t_positions = adaptive_cross_t_positions(
                            xs, ys, sorted_lines,
                            base_spacing=cs,
                            curvature_weight=s.get("curvatureWeight", 0.4),
                            attractor_weight=s.get("attractorWeight", 0.3),
                            value_weight=s.get("valueWeight", 0.2),
                            attractor_x=s["siteWidth"] / 2,
                            attractor_y=s["siteHeight"] / 2,
                            attractor_sigma=200,
                            value_field=value_field,
                            site_width=s["siteWidth"],
                            site_height=s["siteHeight"],
                        )
                    else:
                        num_sections = max(3, min(51, int(1600 / max(cs, 10))))
                        t_positions = [j / max(num_sections - 1, 1) for j in range(num_sections)]

                    for t in t_positions:
                        idx = 0 if t <= 0 else min(int(t / T_STEP), T_COUNT - 1)
                        cross_pts = get_line_at_t(sorted_lines, t, perp=True)
                        if len(cross_pts) < 2:
                            continue
                        self._export_geometry["polylines"].append(cross_pts)
                        fill, w = (main_color, main_w) if perp else (cross_color, cross_w)
                        for i in range(len(cross_pts) - 1):
                            self._draw_line_segment(cross_pts[i], cross_pts[i + 1], fill, w)

                    if s["runMode"] == "C":
                        use_frontage = s.get("parcelFrontageBased", True)
                        use_block = s.get("parcelBlockByBlock", True)
                        use_corner = s.get("parcelCornerSeparate", True)
                        use_pert = s.get("parcelPerturbation", False)
                        pert_str = s.get("parcelPerturbationStr", 0.02) if use_pert else 0
                        min_f = s.get("pMin", 15)
                        max_f = s.get("pMax", 45)
                        min_a = s.get("pMinArea", 50)
                        max_d = s.get("pMaxDepth", 200)

                        if use_frontage and use_block:
                            parcel_list = subdivide_blocks(
                                sorted_lines, t_positions,
                                min_frontage=min_f, max_frontage=max_f,
                                min_area=min_a, max_depth=max_d,
                                use_frontage_based=True,
                                use_block_by_block=True,
                                corner_parcels_separate=use_corner,
                                perturbation_strength=pert_str,
                                seed=hash(str(s.get("seedRotation", 0))),
                            )
                        else:
                            parcel_list = rule_based_parcels(sorted_lines, segments=15)

                        for parcel_pts in parcel_list:
                            self._export_geometry["parcels"].append(parcel_pts)
                            if random.random() > 0.15:
                                gray = int(255 * (0.05 + random.random() * 0.1))
                                fill_color = f"#{gray:02x}{gray:02x}{gray:02x}"
                                pad_pts = [self._pad(x, y) for x, y in parcel_pts]
                                flat = [c for p in pad_pts for c in p]
                                self.canvas.create_polygon(
                                    *flat, fill=fill_color, outline="#1a1a1a")

        if s["seedType"] == "custom" and self.custom_seed_curves:
            colors = ["#ff6600", "#66ff00", "#0066ff", "#ff00ff", "#00ffff"]
            for ci, curve in enumerate(self.custom_seed_curves):
                pts = self._get_curve_points(curve)
                if len(pts) < 2:
                    for x, y in pts:
                        cx, cy = self._pad(x, y)
                        self.canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="#ff3300", outline="#ffffff")
                    continue
                color = colors[ci % len(colors)]
                curve_pts = sample_curve(pts)
                for i in range(len(curve_pts) - 1):
                    self._draw_line_segment(curve_pts[i], curve_pts[i + 1], color, 2)
                for x, y in pts:
                    cx, cy = self._pad(x, y)
                    self.canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill=color, outline="#ffffff")

    def _bind_events(self):
        for key, ctrl in self.controls.items():
            if key in ("rotVal", "spacingVal", "scaleVal", "noiseScaleVal", "noiseStrVal", "crossVal",
                       "seedXVal", "seedYVal", "seedLenVal", "curvWeightVal", "attrWeightVal", "valWeightVal"):
                continue
            if isinstance(ctrl, tk.Scale):
                ctrl.config(command=lambda v, k=key: self.update_state())
            elif isinstance(ctrl, (ttk.Combobox, tk.Entry)):
                ctrl.bind("<<ComboboxSelected>>" if isinstance(ctrl, ttk.Combobox) else "<KeyRelease>", lambda e: self.update_state())
        for w in self.root.winfo_children():
            self._bind_recursive(w, self.update_state)

    def _bind_recursive(self, widget, callback):
        if isinstance(widget, tk.Scale):
            widget.config(command=lambda v: callback())
        elif isinstance(widget, ttk.Combobox):
            widget.bind("<<ComboboxSelected>>", lambda e: callback())
        elif isinstance(widget, tk.Entry):
            widget.bind("<KeyRelease>", lambda e: callback())
        for child in widget.winfo_children():
            self._bind_recursive(child, callback)

    def _export_rhino(self):
        def status_cb(msg):
            self.status_label.config(text=msg)
        export_rhino(self._export_geometry, self.state["siteWidth"], self.state["siteHeight"], status_cb)

    def _export_dxf(self):
        def status_cb(msg):
            self.status_label.config(text=msg)
        export_dxf(self._export_geometry, self.state["siteWidth"], self.state["siteHeight"], status_cb)

    def _switch_language(self, lang):
        """Switch language and refresh all UI text."""
        if lang == get_language():
            return
        # Save combobox indices before switching
        idx_run = RUN_MODE_OPTS.index(self.controls["runMode"].get()) if self.controls["runMode"].get() in RUN_MODE_OPTS else 1
        idx_basis = BASIS_TYPE_OPTS.index(self.controls["basisType"].get()) if self.controls["basisType"].get() in BASIS_TYPE_OPTS else 0
        idx_seed = SEED_TYPE_OPTS.index(self.controls["seedType"].get()) if self.controls["seedType"].get() in SEED_TYPE_OPTS else 0
        idx_spacing = SPACING_MODE_OPTS.index(self.controls["spacingMode"].get()) if self.controls["spacingMode"].get() in SPACING_MODE_OPTS else 0
        set_language(lang)
        self._refresh_ui_texts(idx_run, idx_basis, idx_seed, idx_spacing)
        self._update_lang_buttons_state()

    def _update_lang_buttons_state(self):
        """Highlight active language button."""
        is_en = get_language() == "en"
        self.controls["btnLangEN"].config(bg="#3a5a3a" if is_en else "#2a2a2a")
        self.controls["btnLangZH"].config(bg="#3a5a3a" if not is_en else "#2a2a2a")

    def _refresh_ui_texts(self, idx_run=1, idx_basis=0, idx_seed=0, idx_spacing=0):
        """Refresh all UI text after language change."""
        self.root.title(i18n.T["title"])
        self._title_label.config(text=i18n.T["title"])
        self._subtitle_label.config(text=i18n.T["subtitle"])
        section_keys = ["section_run_mode", "section_field_logic", "section_seed_line", "section_multi_seed",
                        "section_curve_params", "section_expansion", "section_noise", "section_street"]
        for i, key in enumerate(section_keys):
            if i < len(self._section_labels):
                self._section_labels[i].config(text=i18n.T[key])
        if hasattr(self, "_label_refs"):
            for widget, key in self._label_refs:
                if widget.winfo_exists():
                    text = i18n.T[key] if key in i18n.T else getattr(i18n, key, "")
                    widget.config(text=text)
        self.controls["runMode"].config(values=i18n.RUN_MODE_OPTS)
        self.controls["runMode"].set(i18n.RUN_MODE_OPTS[min(idx_run, len(i18n.RUN_MODE_OPTS) - 1)])
        self.controls["basisType"].config(values=i18n.BASIS_TYPE_OPTS)
        self.controls["basisType"].set(i18n.BASIS_TYPE_OPTS[min(idx_basis, len(i18n.BASIS_TYPE_OPTS) - 1)])
        self._on_basis_change()
        self.controls["seedType"].config(values=i18n.SEED_TYPE_OPTS)
        self.controls["seedType"].set(i18n.SEED_TYPE_OPTS[min(idx_seed, len(i18n.SEED_TYPE_OPTS) - 1)])
        self.controls["spacingMode"].config(values=i18n.SPACING_MODE_OPTS)
        self.controls["spacingMode"].set(i18n.SPACING_MODE_OPTS[min(idx_spacing, len(i18n.SPACING_MODE_OPTS) - 1)])
        self.controls["btnAddCurve"].config(text=i18n.BTN_ADD_CURVE)
        self.controls["btnDraw"].config(text=i18n.BTN_DRAW if not self.draw_mode else i18n.BTN_DONE_DRAWING)
        self.controls["btnClear"].config(text=i18n.BTN_CLEAR)
        self.controls["btnReset"].config(text=i18n.BTN_RESET)
        self.controls["btnGenerate"].config(text=i18n.BTN_GENERATE)
        self._noise_cb.config(text=i18n.NOISE_ENABLED)
        self._multi_seed_hint.config(text=i18n.MULTI_SEED_HINT)
        self._curve_params_hint.config(text=i18n.CURVE_PARAMS_HINT)
        self._export_label.config(text=i18n.T["export_rhino"])
        self.controls["btnExportRhino"].config(text=i18n.T["export_py"])
        self.controls["btnExportDxf"].config(text=i18n.T["export_dxf"])
        self._footer_label.config(text=i18n.T["footer"])
        if self.selected_curve_for_params >= 0:
            self._build_curve_params_ui()
        self._refresh_curve_list()
        self.status_label.config(text=i18n.T["status_default"] if not self.draw_mode else
                                 i18n.DRAW_MODE_STATUS.format(self.editing_curve_index + 1))
        self.update_state()

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
        if "pMinArea" in self.controls:
            self.controls["pMinArea"].delete(0, tk.END)
            self.controls["pMinArea"].insert(0, "50")
        if "pMaxDepth" in self.controls:
            self.controls["pMaxDepth"].delete(0, tk.END)
            self.controls["pMaxDepth"].insert(0, "200")
        if "parcelFrontageBased" in self.controls:
            self.controls["parcelFrontageBased"].set(True)
        if "parcelBlockByBlock" in self.controls:
            self.controls["parcelBlockByBlock"].set(True)
        if "parcelCornerSeparate" in self.controls:
            self.controls["parcelCornerSeparate"].set(True)
        if "parcelPerturbation" in self.controls:
            self.controls["parcelPerturbation"].set(False)
        if "parcelPerturbationStr" in self.controls:
            self.controls["parcelPerturbationStr"].set(0.02)
        self.update_state()

    def run(self):
        self.root.mainloop()
