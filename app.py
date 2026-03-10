"""
城市线驱动向量场生成器 - 主应用
基于 Seed Curve 的非中心式扩张
"""

import tkinter as tk
from tkinter import ttk, filedialog
import math
import random
import threading
import queue

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
from i18n import T, RUN_MODE_OPTS, BASIS_TYPE_OPTS, SPACING_MODE_OPTS
from i18n import set_language, get_language
from i18n import BTN_RESET, BTN_GENERATE
from i18n import LINE_SPACING_SHORT, POS_NEG, SPACING_MODE_SHORT
from i18n import BASIS_BLEND_FACTOR
from i18n import RIVER_BOUNDARY_TITLE, USE_RIVER_BOUNDARY, BOUNDARY_DECAY, BOUNDARY_BLEND
from i18n import TENSOR_CENTER_TITLE, TENSOR_CENTER_X, TENSOR_CENTER_Y, BTN_ADD_CENTER, BTN_CLEAR_CENTERS, TENSOR_CENTER_HINT
from i18n import BTN_DRAW_RIVER, BTN_DONE_DRAWING, BTN_CLEAR
from i18n import HEIGHT_FIELD_TITLE, USE_HEIGHT_FIELD, BTN_LOAD_HEIGHT, BTN_CLEAR_HEIGHT, HEIGHT_BLEND
from i18n import SPACING_SCALE_SHORT, CROSS_SPACING_SHORT, NOISE_ENABLED, ROADS_PERP
from i18n import ROAD_HIERARCHY, ADAPTIVE_CROSS, CURVATURE_WEIGHT, ATTRACTOR_WEIGHT, VALUE_WEIGHT
from i18n import PARCEL_FRONTAGE_BASED, PARCEL_BLOCK_BY_BLOCK, PARCEL_CORNER_SEPARATE, PARCEL_PERTURBATION
from i18n import PARCEL_PERTURBATION_STR
from i18n import HYPERSTREAMLINE_TITLE, HYPERSTREAMLINE_MAJOR, HYPERSTREAMLINE_MINOR, HYPERSTREAMLINE_BOTH
from i18n import BTN_ADD_SEED, BTN_CLEAR_SEEDS, HYPER_STEP_SIZE, HYPER_MAX_LENGTH, HYPER_ANGLE_STOP
from i18n import PAPER_OPTIONS, STREET_GEN_MODE, STREET_PARAM, STREET_HYPER, TWO_STAGE
from i18n import PERLIN_ROTATION, PERLIN_STRENGTH, LAPLACIAN_SMOOTH, LAPLACIAN_ITERS
from i18n import BTN_DRAW_BRUSH, BTN_CLEAR_BRUSH, BRUSH_HINT
from parcel_subdivision import subdivide_blocks, rule_based_parcels
from tensor_field import (
    sample_tensor_field_grid,
    generate_streets_from_tensor_field,
    create_tensor_field_fn,
    create_smoothed_tensor_fn,
    BASIS_GRID,
    BASIS_RADIAL,
    BASIS_BLEND,
    BASIS_BOUNDARY,
    BASIS_BOUNDARY_BLEND,
    BASIS_HEIGHT,
    BASIS_HEIGHT_BLEND,
)
from street_from_hyperstreamlines import (
    generate_streets_from_hyperstreamlines,
    two_stage_street_generation,
)
from boundary_field import extract_boundary_from_curve, extract_boundary_from_image
from height_field import build_height_field_from_image
from hyperstreamline import integrate_hyperstreamlines_from_seeds


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
        self.drag_center_idx = None  # index into tensor_centers when dragging
        self.tensor_center_add_mode = False  # click on canvas to add center
        self._canvas_custom_bound = False
        self._curve_list_frame = None
        self._export_geometry = {"polylines": [], "parcels": []}
        self._generate_after_id = None
        self._debounce_ms = 280
        self._gen_queue = queue.Queue()
        self._gen_thread = None
        self._gen_polling = False
        self._river_mask_image = None
        self._height_image = None
        self._height_gradient_fn = None
        self.hyperstreamline_seeds = []
        self.hyperstreamline_seed_mode = False
        self.tensor_centers = [(600, 100)]
        self.brush_strokes = []
        self.brush_draw_mode = False
        self._current_brush_stroke = []

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

        self._hyperstreamline_frame = tk.Frame(panel, bg="#141414")
        self._hyperstreamline_frame.pack(fill=tk.X, pady=(0, 8))

        self._section_labels.append(self._section_title(panel, T["section_field_logic"]))
        self._label_group(panel, T["basis_type"], t_key="basis_type")
        self.controls["basisType"] = ttk.Combobox(panel, values=BASIS_TYPE_OPTS, state="readonly", width=36)
        self.controls["basisType"].set(BASIS_TYPE_OPTS[0])
        self.controls["basisType"].pack(fill=tk.X, pady=(0, 4))
        self.controls["basisType"].bind("<<ComboboxSelected>>", lambda e: self._on_basis_change())
        self._basis_params_frame = tk.Frame(panel, bg="#141414")
        self._basis_params_frame.pack(fill=tk.X, pady=(0, 8))
        self._river_boundary_frame = tk.Frame(panel, bg="#141414")
        self._river_boundary_frame.pack(fill=tk.X, pady=(0, 8))
        self._height_field_frame = tk.Frame(panel, bg="#141414")
        self._height_field_frame.pack(fill=tk.X, pady=(0, 16))
        self._on_basis_change()

        self._section_labels.append(self._section_title(panel, TENSOR_CENTER_TITLE))
        center_btn_row = tk.Frame(panel, bg="#141414")
        center_btn_row.pack(fill=tk.X, pady=(0, 4))
        self.controls["btnAddCenter"] = tk.Button(center_btn_row, text=BTN_ADD_CENTER, command=self._toggle_tensor_center_add_mode,
                                                  bg="#2a4a3a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnAddCenter"].pack(side=tk.LEFT, padx=(0, 4))
        self.controls["btnClearCenters"] = tk.Button(center_btn_row, text=BTN_CLEAR_CENTERS, command=self._clear_tensor_centers,
                                                     bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnClearCenters"].pack(side=tk.LEFT)
        self._label_group(panel, TENSOR_CENTER_HINT, "", t_key="tensor_center_hint")
        tk.Label(panel, text="", bg="#141414", font=("Inter", 4)).pack()

        self._section_labels.append(self._section_title(panel, PAPER_OPTIONS))
        self._label_group(panel, STREET_GEN_MODE, t_key="street_gen_mode")
        self.controls["streetGenMode"] = ttk.Combobox(panel, values=[STREET_PARAM, STREET_HYPER], state="readonly", width=24)
        self.controls["streetGenMode"].set(STREET_PARAM)
        self.controls["streetGenMode"].pack(fill=tk.X, pady=(0, 4))
        self.controls["twoStage"] = tk.BooleanVar(value=False)
        tk.Checkbutton(panel, text=TWO_STAGE, variable=self.controls["twoStage"], command=self.update_state,
                      bg="#141414", fg="#e0e0e0", selectcolor="#1a1a1a", activebackground="#141414",
                      activeforeground="#e0e0e0", font=("Inter", 9)).pack(anchor="w", pady=(0, 4))
        self._label_group(panel, PERLIN_ROTATION, "0.2", right_key="perlinStrVal", t_key="perlin_strength")
        self.controls["perlinStrength"] = tk.Scale(panel, from_=0, to=1, resolution=0.05, orient=tk.HORIZONTAL,
                                                  bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                  highlightthickness=0, showvalue=False, command=lambda v: self.update_state())
        self.controls["perlinStrength"].set(0.2)
        self.controls["perlinStrength"].pack(fill=tk.X, pady=(0, 4))
        self.controls["laplacianSmooth"] = tk.BooleanVar(value=False)
        tk.Checkbutton(panel, text=LAPLACIAN_SMOOTH, variable=self.controls["laplacianSmooth"], command=self.update_state,
                      bg="#141414", fg="#e0e0e0", selectcolor="#1a1a1a", activebackground="#141414",
                      activeforeground="#e0e0e0", font=("Inter", 9)).pack(anchor="w", pady=(0, 4))
        self._label_group(panel, LAPLACIAN_ITERS, "3", right_key="smoothItersVal", t_key="smooth_iters")
        self.controls["smoothIters"] = tk.Scale(panel, from_=1, to=10, orient=tk.HORIZONTAL,
                                                bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                highlightthickness=0, showvalue=False, command=lambda v: self.update_state())
        self.controls["smoothIters"].set(3)
        self.controls["smoothIters"].pack(fill=tk.X, pady=(0, 4))
        brush_row = tk.Frame(panel, bg="#141414")
        brush_row.pack(fill=tk.X, pady=(0, 4))
        self.controls["btnDrawBrush"] = tk.Button(brush_row, text=BTN_DRAW_BRUSH, command=self._toggle_brush_mode,
                                                  bg="#2a4a3a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnDrawBrush"].pack(side=tk.LEFT, padx=(0, 4))
        self.controls["btnClearBrush"] = tk.Button(brush_row, text=BTN_CLEAR_BRUSH, command=self._clear_brush,
                                                    bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnClearBrush"].pack(side=tk.LEFT)
        self._label_group(panel, BRUSH_HINT, "", t_key="brush_hint")
        tk.Label(panel, text="", bg="#141414", font=("Inter", 4)).pack()

        self._section_labels.append(self._section_title(panel, T["section_expansion"]))
        self._label_group(panel, T["line_spacing"], "65", right_key="spacingVal", t_key="line_spacing")
        self.controls["lineSpacing"] = tk.Scale(panel, from_=20, to=120, orient=tk.HORIZONTAL,
                                                bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                highlightthickness=0, showvalue=False)
        self.controls["lineSpacing"].set(65)
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
        if "A" in val or ("Flow" in val and "Hyper" not in val):
            return "A"
        if "C" in val or "Parcel" in val:
            return "C"
        if "D" in val or "Hyper" in val or "超流线" in val:
            return "D"
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
        if "Boundary+Grid" in val or "边界+网格" in val:
            return BASIS_BOUNDARY_BLEND
        if "Boundary" in val or "边界" in val:
            return BASIS_BOUNDARY
        if "Height+Grid" in val or "高程+网格" in val:
            return BASIS_HEIGHT_BLEND
        if "Height" in val or "高程" in val:
            return BASIS_HEIGHT
        return BASIS_GRID

    def _on_basis_change(self):
        """Show params when basis is Blend or Boundary"""
        for w in self._basis_params_frame.winfo_children():
            w.destroy()
        basis = self._get_basis_type()
        if basis == BASIS_BLEND:
            self._label_group(self._basis_params_frame, BASIS_BLEND_FACTOR, "0.5", right_key="basisBlendVal", t_key="BASIS_BLEND_FACTOR")
            self.controls["basisBlendFactor"] = tk.Scale(
                self._basis_params_frame, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL,
                bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                highlightthickness=0, showvalue=False,
                command=lambda v: self._update_basis_blend_label())
            self.controls["basisBlendFactor"].set(0.5)
            self.controls["basisBlendFactor"].pack(fill=tk.X, pady=(0, 4))
            self._bind_recursive(self._basis_params_frame, self.update_state)
        elif basis in (BASIS_BOUNDARY, BASIS_BOUNDARY_BLEND):
            self._label_group(self._basis_params_frame, BOUNDARY_DECAY, "150", right_key="boundaryDecayVal", t_key="BOUNDARY_DECAY")
            self.controls["boundaryDecay"] = tk.Scale(
                self._basis_params_frame, from_=50, to=400, orient=tk.HORIZONTAL,
                bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                highlightthickness=0, showvalue=False,
                command=lambda v: self._update_boundary_labels())
            self.controls["boundaryDecay"].set(150)
            self.controls["boundaryDecay"].pack(fill=tk.X, pady=(0, 4))
            if basis == BASIS_BOUNDARY_BLEND:
                self._label_group(self._basis_params_frame, BOUNDARY_BLEND, "0.5", right_key="boundaryBlendVal", t_key="BOUNDARY_BLEND")
                self.controls["boundaryBlendFactor"] = tk.Scale(
                    self._basis_params_frame, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL,
                    bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                    highlightthickness=0, showvalue=False,
                    command=lambda v: self._update_boundary_labels())
                self.controls["boundaryBlendFactor"].set(0.5)
                self.controls["boundaryBlendFactor"].pack(fill=tk.X, pady=(0, 4))
            self._bind_recursive(self._basis_params_frame, self.update_state)
        elif basis in (BASIS_HEIGHT, BASIS_HEIGHT_BLEND):
            if basis == BASIS_HEIGHT_BLEND:
                self._label_group(self._basis_params_frame, HEIGHT_BLEND, "0.5", right_key="heightBlendVal", t_key="HEIGHT_BLEND")
                self.controls["heightBlendFactor"] = tk.Scale(
                    self._basis_params_frame, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL,
                    bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                    highlightthickness=0, showvalue=False,
                    command=lambda v: self._update_height_blend_label())
                self.controls["heightBlendFactor"].set(0.5)
                self.controls["heightBlendFactor"].pack(fill=tk.X, pady=(0, 4))
            self._bind_recursive(self._basis_params_frame, self.update_state)
        self._build_river_boundary_ui()
        self._build_height_field_ui()
        self.update_state()

    def _build_river_boundary_ui(self):
        """River / Boundary 输入区"""
        for w in self._river_boundary_frame.winfo_children():
            w.destroy()
        basis = self._get_basis_type()
        if basis not in (BASIS_BOUNDARY, BASIS_BOUNDARY_BLEND):
            return
        tk.Label(self._river_boundary_frame, text=RIVER_BOUNDARY_TITLE, fg="#e0e0e0", bg="#141414",
                 font=("Inter", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.controls["useRiverBoundary"] = tk.BooleanVar(value=True)
        tk.Checkbutton(self._river_boundary_frame, text=USE_RIVER_BOUNDARY, variable=self.controls["useRiverBoundary"],
                       command=self.update_state, bg="#141414", fg="#e0e0e0", selectcolor="#1a1a1a",
                       activebackground="#141414", activeforeground="#e0e0e0", wraplength=350).pack(anchor="w", pady=(0, 4))
        btn_row = tk.Frame(self._river_boundary_frame, bg="#141414")
        btn_row.pack(fill=tk.X, pady=(0, 4))
        self.controls["btnLoadRiverMask"] = tk.Button(btn_row, text="Load Mask (GIF)", command=self._load_river_mask,
                                                      bg="#2a3a4a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnLoadRiverMask"].pack(side=tk.LEFT, padx=(0, 4))
        self.controls["btnClearRiverMask"] = tk.Button(btn_row, text="Clear", command=self._clear_river_mask,
                                                       bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnClearRiverMask"].pack(side=tk.LEFT)
        draw_row = tk.Frame(self._river_boundary_frame, bg="#141414")
        draw_row.pack(fill=tk.X, pady=(8, 4))
        self.controls["btnDrawRiver"] = tk.Button(draw_row, text=BTN_DRAW_RIVER, command=self._toggle_draw_mode,
                                                  bg="#2a4a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnDrawRiver"].pack(side=tk.LEFT, padx=(0, 4))
        self.controls["btnClearRiver"] = tk.Button(draw_row, text=BTN_CLEAR, command=self._clear_river_curve,
                                                   bg="#1a1a1a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnClearRiver"].pack(side=tk.LEFT)
        self._bind_recursive(self._river_boundary_frame, self.update_state)

    def _build_height_field_ui(self):
        """Height / Elevation 输入区"""
        for w in self._height_field_frame.winfo_children():
            w.destroy()
        basis = self._get_basis_type()
        if basis not in (BASIS_HEIGHT, BASIS_HEIGHT_BLEND):
            return
        tk.Label(self._height_field_frame, text=HEIGHT_FIELD_TITLE, fg="#e0e0e0", bg="#141414",
                 font=("Inter", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.controls["useHeightField"] = tk.BooleanVar(value=True)
        tk.Checkbutton(self._height_field_frame, text=USE_HEIGHT_FIELD, variable=self.controls["useHeightField"],
                       command=self.update_state, bg="#141414", fg="#e0e0e0", selectcolor="#1a1a1a",
                       activebackground="#141414", activeforeground="#e0e0e0", wraplength=350).pack(anchor="w", pady=(0, 4))
        btn_row = tk.Frame(self._height_field_frame, bg="#141414")
        btn_row.pack(fill=tk.X, pady=(0, 4))
        self.controls["btnLoadHeight"] = tk.Button(btn_row, text=BTN_LOAD_HEIGHT, command=self._load_height_image,
                                                    bg="#2a4a3a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnLoadHeight"].pack(side=tk.LEFT, padx=(0, 4))
        self.controls["btnClearHeight"] = tk.Button(btn_row, text=BTN_CLEAR_HEIGHT, command=self._clear_height_image,
                                                    bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnClearHeight"].pack(side=tk.LEFT)
        self._bind_recursive(self._height_field_frame, self.update_state)

    def _build_hyperstreamline_ui(self):
        """Hyperstreamline 参数区，仅 Mode D 时显示"""
        for w in self._hyperstreamline_frame.winfo_children():
            w.destroy()
        if self._get_run_mode() != "D":
            return
        tk.Label(self._hyperstreamline_frame, text=HYPERSTREAMLINE_TITLE, fg="#e0e0e0", bg="#141414",
                 font=("Inter", 10, "bold")).pack(anchor="w", pady=(0, 4))
        row1 = tk.Frame(self._hyperstreamline_frame, bg="#141414")
        row1.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row1, text="Type", fg="#888888", bg="#141414", font=("Inter", 9)).pack(side=tk.LEFT, padx=(0, 8))
        self.controls["hyperType"] = ttk.Combobox(row1, values=[HYPERSTREAMLINE_MAJOR, HYPERSTREAMLINE_MINOR, HYPERSTREAMLINE_BOTH],
                                                 state="readonly", width=12)
        self.controls["hyperType"].set(HYPERSTREAMLINE_MAJOR)
        self.controls["hyperType"].pack(side=tk.LEFT)
        btn_row = tk.Frame(self._hyperstreamline_frame, bg="#141414")
        btn_row.pack(fill=tk.X, pady=(0, 4))
        self.controls["btnAddSeed"] = tk.Button(btn_row, text=BTN_ADD_SEED, command=self._toggle_hyper_seed_mode,
                                                bg="#2a4a3a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnAddSeed"].pack(side=tk.LEFT, padx=(0, 4))
        self.controls["btnClearSeeds"] = tk.Button(btn_row, text=BTN_CLEAR_SEEDS, command=self._clear_hyper_seeds,
                                                   bg="#2a2a2a", fg="#e0e0e0", relief=tk.SOLID, bd=1, font=("JetBrains Mono", 9))
        self.controls["btnClearSeeds"].pack(side=tk.LEFT)
        self._label_group(self._hyperstreamline_frame, HYPER_STEP_SIZE, "2", right_key="hyperStepVal", t_key="hyper_step")
        self.controls["hyperStepSize"] = tk.Scale(self._hyperstreamline_frame, from_=0.5, to=8, resolution=0.5, orient=tk.HORIZONTAL,
                                                  bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                  highlightthickness=0, showvalue=False)
        self.controls["hyperStepSize"].set(2)
        self.controls["hyperStepSize"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(self._hyperstreamline_frame, HYPER_MAX_LENGTH, "0", right_key="hyperMaxLenVal", t_key="hyper_max_len")
        self.controls["hyperMaxLength"] = tk.Entry(self._hyperstreamline_frame, bg="#1a1a1a", fg="#e0e0e0",
                                                   insertbackground="#e0e0e0", relief=tk.SOLID, bd=1, width=8)
        self.controls["hyperMaxLength"].insert(0, "0")
        self.controls["hyperMaxLength"].pack(fill=tk.X, pady=(0, 4))
        self._label_group(self._hyperstreamline_frame, HYPER_ANGLE_STOP, "0.3", right_key="hyperAngleVal", t_key="hyper_angle")
        self.controls["hyperAngleStop"] = tk.Scale(self._hyperstreamline_frame, from_=0.1, to=1, resolution=0.05, orient=tk.HORIZONTAL,
                                                   bg="#141414", fg="#e0e0e0", troughcolor="#2a2a2a",
                                                   highlightthickness=0, showvalue=False)
        self.controls["hyperAngleStop"].set(0.3)
        self.controls["hyperAngleStop"].pack(fill=tk.X, pady=(0, 8))
        self._bind_recursive(self._hyperstreamline_frame, self.update_state)

    def _toggle_hyper_seed_mode(self):
        self.hyperstreamline_seed_mode = not self.hyperstreamline_seed_mode
        if self.hyperstreamline_seed_mode and "btnAddSeed" in self.controls:
            self.controls["btnAddSeed"].config(text="Done", bg="#3a5a3a")
            self.status_label.config(text="Click on canvas to add seed points")
        else:
            if "btnAddSeed" in self.controls:
                self.controls["btnAddSeed"].config(text=BTN_ADD_SEED, bg="#2a4a3a")
            self.status_label.config(text=T["status_default"])
        self.update_state()

    def _clear_hyper_seeds(self):
        self.hyperstreamline_seeds.clear()
        self.update_state()

    def _update_height_blend_label(self):
        if "heightBlendVal" in self.controls and "heightBlendFactor" in self.controls:
            self.controls["heightBlendVal"].config(text=f"{self.controls['heightBlendFactor'].get():.1f}")
        self.update_state()

    def _load_height_image(self):
        filetypes = [("Image", "*.png *.jpg *.jpeg *.gif *.bmp"), ("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg"), ("GIF", "*.gif"), ("All", "*")]
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            try:
                use_pil = path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))
                if use_pil:
                    try:
                        from PIL import Image
                        img = Image.open(path)
                        self._height_image = img
                        self._height_gradient_fn = None  # 将在 update_state 时重建
                    except ImportError:
                        from tkinter import PhotoImage
                        self._height_image = PhotoImage(file=path)
                        self._height_gradient_fn = None
                else:
                    from tkinter import PhotoImage
                    self._height_image = PhotoImage(file=path)
                    self._height_gradient_fn = None
                self.update_state()
            except Exception as e:
                self.status_label.config(text=f"Load failed: {e}")

    def _clear_height_image(self):
        self._height_image = None
        self._height_gradient_fn = None
        self.update_state()

    def _get_height_gradient_fn(self):
        """获取高程梯度函数，用于 height 基底"""
        use_var = self.controls.get("useHeightField")
        if use_var is None or not use_var.get():
            return None
        if not self._height_image:
            return None
        w, h = self.state.get("siteWidth", 1200), self.state.get("siteHeight", 200)
        if self._height_gradient_fn is None or getattr(self, "_last_height_site", (0, 0)) != (w, h):
            _, grad_fn = build_height_field_from_image(self._height_image, w, h, use_pil=hasattr(self._height_image, "size"))
            self._height_gradient_fn = grad_fn
            self._last_height_site = (w, h)
        return self._height_gradient_fn

    def _load_river_mask(self):
        path = filedialog.askopenfilename(filetypes=[("GIF", "*.gif"), ("All", "*")])
        if path:
            try:
                from tkinter import PhotoImage
                self._river_mask_image = PhotoImage(file=path)
                self.update_state()
            except Exception as e:
                self.status_label.config(text=f"Load failed: {e}")

    def _clear_river_mask(self):
        self._river_mask_image = None
        self.update_state()

    def _toggle_tensor_center_add_mode(self):
        self.tensor_center_add_mode = not self.tensor_center_add_mode
        if self.tensor_center_add_mode and "btnAddCenter" in self.controls:
            self.controls["btnAddCenter"].config(text="Done", bg="#3a5a3a")
            self.status_label.config(text="Click on canvas to add tensor center")
        else:
            if "btnAddCenter" in self.controls:
                self.controls["btnAddCenter"].config(text=BTN_ADD_CENTER, bg="#2a4a3a")
            self.status_label.config(text=T["status_default"])
        self.update_state()

    def _clear_tensor_centers(self):
        w = safe_float(self.controls["siteWidth"].get(), 1200)
        h = safe_float(self.controls["siteHeight"].get(), 200)
        self.tensor_centers = [(w / 2, h / 2)]
        self.update_state()

    def _toggle_brush_mode(self):
        self.brush_draw_mode = not self.brush_draw_mode
        if self.brush_draw_mode:
            self._current_brush_stroke = []
            if "btnDrawBrush" in self.controls:
                self.controls["btnDrawBrush"].config(text=BTN_DONE_DRAWING, bg="#3a5a3a")
            self.status_label.config(text="Draw brush: click to add points")
        else:
            if len(self._current_brush_stroke) >= 2:
                self.brush_strokes.append(list(self._current_brush_stroke))
            self._current_brush_stroke = []
            if "btnDrawBrush" in self.controls:
                self.controls["btnDrawBrush"].config(text=BTN_DRAW_BRUSH, bg="#2a4a3a")
            self.status_label.config(text=T["status_default"])
        self.update_state()

    def _clear_brush(self):
        self.brush_strokes = []
        self._current_brush_stroke = []
        self.update_state()

    def _update_boundary_labels(self):
        if "boundaryDecayVal" in self.controls and "boundaryDecay" in self.controls:
            self.controls["boundaryDecayVal"].config(text=str(int(self.controls["boundaryDecay"].get())))
        if "boundaryBlendVal" in self.controls and "boundaryBlendFactor" in self.controls:
            self.controls["boundaryBlendVal"].config(text=f"{self.controls['boundaryBlendFactor'].get():.1f}")
        self.update_state()

    def _get_boundary(self):
        """获取边界数据：来自曲线或图像"""
        use_var = self.controls.get("useRiverBoundary")
        if use_var is None or not use_var.get():
            return None
        w, h = self.state.get("siteWidth", 1200), self.state.get("siteHeight", 200)
        if self._river_mask_image:
            return extract_boundary_from_image(self._river_mask_image, w, h)
        if self.custom_seed_curves:
            pts = self._get_curve_points(self.custom_seed_curves[0])
            if len(pts) >= 2:
                return extract_boundary_from_curve(pts)
        return None

    def _update_basis_blend_label(self):
        if "basisBlendVal" in self.controls and "basisBlendFactor" in self.controls:
            self.controls["basisBlendVal"].config(text=f"{self.controls['basisBlendFactor'].get():.1f}")
        self.update_state()

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
            "lineSpacing": safe_float(self.controls["lineSpacing"].get(), 65),
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

    def _add_river_curve(self):
        """Add or start editing the single river curve (for boundary mode)"""
        if not self.custom_seed_curves:
            self.custom_seed_curves.append({"points": [], "params": self._get_curve_params_defaults()})
        self.editing_curve_index = 0
        self.draw_mode = True
        if "btnDrawRiver" in self.controls:
            self.controls["btnDrawRiver"].config(text=BTN_DONE_DRAWING, bg="#3a5a3a")
        self.status_label.config(text="Draw river boundary: click to add points, drag to move")
        self.update_state()

    def _refresh_curve_list(self):
        """No-op: curve list UI removed"""
        for i, curve in enumerate(self.custom_seed_curves):
            if isinstance(curve, list):
                self.custom_seed_curves[i] = {"points": curve, "params": self._get_curve_params_defaults()}

    def _clear_river_curve(self):
        self.custom_seed_curves.clear()
        self.editing_curve_index = -1
        if self.draw_mode:
            self._exit_draw_mode()
        self.update_state()

    def _toggle_draw_mode(self):
        if self.draw_mode:
            self._exit_draw_mode()
        else:
            self._add_river_curve()
        self.update_state()

    def _exit_draw_mode(self):
        self.draw_mode = False
        self.editing_curve_index = -1
        if "btnDrawRiver" in self.controls and self.controls["btnDrawRiver"].winfo_exists():
            self.controls["btnDrawRiver"].config(text=BTN_DRAW_RIVER, bg="#2a4a2a")
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

    def _find_center_at(self, canvas_x, canvas_y, radius=15):
        """Return index of center near (canvas_x, canvas_y), or -1"""
        best_i, best_d = -1, radius * radius
        for i, (cx, cy) in enumerate(self.tensor_centers):
            px, py = self._pad(cx, cy)
            d = (canvas_x - px) ** 2 + (canvas_y - py) ** 2
            if d < best_d:
                best_d, best_i = d, i
        return best_i

    def _on_canvas_click(self, event):
        lx, ly = self._unpad(event.x, event.y)
        w, h = self.state.get("siteWidth", 1200), self.state.get("siteHeight", 200)
        if self.tensor_center_add_mode:
            if 0 <= lx <= w and 0 <= ly <= h:
                self.tensor_centers.append((lx, ly))
                self.update_state()
            return
        if self.brush_draw_mode:
            if 0 <= lx <= w and 0 <= ly <= h:
                self._current_brush_stroke.append((lx, ly))
                self.update_state()
            return
        if self.hyperstreamline_seed_mode and self._get_run_mode() == "D":
            if 0 <= lx <= w and 0 <= ly <= h:
                self.hyperstreamline_seeds.append((lx, ly))
                self.update_state()
            return
        if self.draw_mode:
            if self.editing_curve_index >= 0 and self.editing_curve_index < len(self.custom_seed_curves):
                ci, pi = self._find_point_at(event.x, event.y)
                if ci >= 0 and pi >= 0:
                    self.drag_curve_idx = ci
                    self.drag_point_idx = pi
                else:
                    self._get_curve_points(self.custom_seed_curves[self.editing_curve_index]).append((lx, ly))
                    self._refresh_curve_list()
                    self.update_state()
            return
        idx = self._find_center_at(event.x, event.y)
        if idx >= 0:
            self.drag_center_idx = idx

    def _on_canvas_drag(self, event):
        if self.drag_center_idx is not None:
            lx, ly = self._unpad(event.x, event.y)
            w, h = self.state.get("siteWidth", 1200), self.state.get("siteHeight", 200)
            lx = max(0, min(w, lx))
            ly = max(0, min(h, ly))
            if 0 <= self.drag_center_idx < len(self.tensor_centers):
                self.tensor_centers[self.drag_center_idx] = (lx, ly)
                self.update_state(immediate=True)
            return
        if self.drag_curve_idx is not None and self.drag_point_idx is not None:
            pts = self._get_curve_points(self.custom_seed_curves[self.drag_curve_idx])
            if 0 <= self.drag_point_idx < len(pts):
                lx, ly = self._unpad(event.x, event.y)
                pts[self.drag_point_idx] = (lx, ly)
                self._refresh_curve_list()
                self.update_state(immediate=True)

    def _on_canvas_release(self, event):
        self.drag_curve_idx = None
        self.drag_point_idx = None
        self.drag_center_idx = None

    def update_state(self, immediate=False):
        if "lineSpacing" not in self.controls:
            return
        self.state["runMode"] = self._get_run_mode()
        self.state["fieldType"] = self._get_field_type()
        self.state["basisType"] = self._get_basis_type()
        self.state["basisBlendFactor"] = safe_float(
            self.controls["basisBlendFactor"].get(), 0.5) if "basisBlendFactor" in self.controls and self.controls["basisBlendFactor"].winfo_exists() else 0.5
        self.state["boundaryDecay"] = safe_float(
            self.controls["boundaryDecay"].get(), 150) if "boundaryDecay" in self.controls and self.controls["boundaryDecay"].winfo_exists() else 150
        self.state["boundaryBlendFactor"] = safe_float(
            self.controls["boundaryBlendFactor"].get(), 0.5) if "boundaryBlendFactor" in self.controls and self.controls["boundaryBlendFactor"].winfo_exists() else 0.5
        self.state["heightBlendFactor"] = safe_float(
            self.controls["heightBlendFactor"].get(), 0.5) if "heightBlendFactor" in self.controls and self.controls["heightBlendFactor"].winfo_exists() else 0.5
        self.state["siteWidth"] = safe_float(self.controls["siteWidth"].get(), 1200)
        self.state["siteHeight"] = safe_float(self.controls["siteHeight"].get(), 200)
        self.state["tensorCenters"] = list(self.tensor_centers)
        self.state["brushStrokes"] = [list(s) for s in self.brush_strokes]
        try:
            self.state["streetGenMode"] = self.controls["streetGenMode"].get() if "streetGenMode" in self.controls else STREET_PARAM
            self.state["twoStage"] = self.controls["twoStage"].get() if "twoStage" in self.controls else False
        except Exception:
            self.state["streetGenMode"] = STREET_PARAM
            self.state["twoStage"] = False
        self.state["perlinStrength"] = safe_float(self.controls["perlinStrength"].get(), 0.2) if "perlinStrength" in self.controls else 0
        self.state["laplacianSmooth"] = self.controls["laplacianSmooth"].get() if "laplacianSmooth" in self.controls else False
        self.state["smoothIters"] = safe_int(self.controls["smoothIters"].get(), 3) if "smoothIters" in self.controls else 3
        self.state["lineSpacing"] = safe_float(self.controls["lineSpacing"].get(), 65)
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
        self.controls["spacingVal"].config(text=str(self.state["lineSpacing"]))
        self.controls["scaleVal"].config(text=f"{self.state['spacingScale']:.1f}")
        self.controls["noiseScaleVal"].config(text=str(self.state["noiseScale"]))
        self.controls["noiseStrVal"].config(text=str(int(self.state["noiseStrength"])))
        self.controls["crossVal"].config(text=str(int(self.state["crossSpacing"])))
        for k, v in [("curvWeightVal", "curvatureWeight"), ("attrWeightVal", "attractorWeight"), ("valWeightVal", "valueWeight")]:
            if k in self.controls and v in self.state:
                self.controls[k].config(text=f"{self.state[v]:.1f}")
        if "hyperStepVal" in self.controls and "hyperStepSize" in self.controls:
            self.controls["hyperStepVal"].config(text=f"{self.controls['hyperStepSize'].get():.1f}")
        if "hyperAngleVal" in self.controls and "hyperAngleStop" in self.controls:
            self.controls["hyperAngleVal"].config(text=f"{self.controls['hyperAngleStop'].get():.1f}")

        self._refresh_curve_list()
        if not self._canvas_custom_bound:
            self.canvas.bind("<Button-1>", self._on_canvas_click)
            self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
            self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
            self._canvas_custom_bound = True
        run_mode = self._get_run_mode()
        if run_mode == "D":
            if len(self._hyperstreamline_frame.winfo_children()) == 0:
                self._build_hyperstreamline_ui()
        else:
            for w in self._hyperstreamline_frame.winfo_children():
                w.destroy()
        self.resize_canvas()
        if immediate:
            if self._generate_after_id:
                self.root.after_cancel(self._generate_after_id)
                self._generate_after_id = None
            self.generate()
        else:
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

    def _draw_hyper_street_graph(self, graph):
        """B/C + use_hyper: 直接绘制 graph edges，不调用 sorted_lines/classify/get_line_at_t/adaptive_cross"""
        main_color, main_w = "#e0e0e0", 2
        edge_pts = graph.get("edge_pts", [])
        for pts in edge_pts:
            if len(pts) >= 2:
                self._export_geometry["polylines"].append(pts)
                for i in range(len(pts) - 1):
                    self._draw_line_segment(pts[i], pts[i + 1], main_color, main_w)
        s = self.state
        basis = s.get("basisType", BASIS_GRID)
        if basis in (BASIS_RADIAL, BASIS_BLEND, BASIS_BOUNDARY, BASIS_BOUNDARY_BLEND):
            centers_draw = s.get("tensorCenters", self.tensor_centers)
            if not centers_draw:
                centers_draw = [(s["siteWidth"] / 2, s["siteHeight"] / 2)]
            for cx, cy in centers_draw:
                px, py = self._pad(cx, cy)
                self.canvas.create_oval(px - 8, py - 8, px + 8, py + 8, fill="#ff6600", outline="#ffffff", width=2)

    def _show_calculating(self):
        """在画布上显示计算中提示"""
        pw, ph = self.state.get("siteWidth", 1200), self.state.get("siteHeight", 200)
        self.canvas.delete("all")
        self.canvas.create_rectangle(DRAW_PADDING, DRAW_PADDING, DRAW_PADDING + pw, DRAW_PADDING + ph,
                                     outline="#555555", width=2, dash=(4, 4))
        cx, cy = DRAW_PADDING + pw / 2, DRAW_PADDING + ph / 2
        self.canvas.create_text(cx, cy, text="Calculating...", fill="#888888", font=("Inter", 14))
        self.canvas.update_idletasks()

    def _apply_gen_result(self, result):
        """在主线程应用生成结果"""
        if result is None:
            return
        if result.get("kind") == "error":
            self.canvas.delete("all")
            pw, ph = self.state.get("siteWidth", 1200), self.state.get("siteHeight", 200)
            self.canvas.create_rectangle(DRAW_PADDING, DRAW_PADDING, DRAW_PADDING + pw, DRAW_PADDING + ph,
                                         outline="#555555", width=2, dash=(4, 4))
            cx, cy = DRAW_PADDING + pw / 2, DRAW_PADDING + ph / 2
            self.canvas.create_text(cx, cy, text="Error: " + result.get("msg", "?"), fill="#cc6666", font=("Inter", 10))
            return
        kind = result.get("kind")
        if kind == "D":
            self.draw_result(lines_by_curve=result["lines_by_curve"], hyperstreamline_mode=True)
        elif kind == "hyper_street":
            self.draw_result(hyper_street_graph=result["hyper_street_graph"])
        elif kind == "B":
            self.draw_result(
                lines_by_curve=result["lines_by_curve"],
                cross_spacings=result["cross_spacings"],
                curve_arrays_by_curve=result["curve_arrays_by_curve"],
            )
        elif kind == "A":
            self.draw_result(mode_a_data=result["mode_a_data"])

    def _poll_gen_queue(self):
        """轮询后台生成结果"""
        if not self._gen_polling:
            return
        try:
            result = self._gen_queue.get_nowait()
            self._gen_polling = False
            self._apply_gen_result(result)
            return
        except queue.Empty:
            pass
        self.root.after(80, self._poll_gen_queue)

    def _run_generate_worker(self, data):
        """后台线程执行的重计算逻辑"""
        try:
            result = self._do_generate(data)
            self._gen_queue.put(result)
        except Exception as e:
            self._gen_queue.put({"kind": "error", "msg": str(e)})

    def _do_generate(self, data):
        """纯计算逻辑，可在线程中运行。data 为预捕获的参数字典"""
        s = data["state"]
        basis = s.get("basisType", BASIS_GRID)
        centers = data["centers"]
        blend = s.get("basisBlendFactor", 0.5)
        boundary = data["boundary"]
        boundary_decay = s.get("boundaryDecay", 150)
        boundary_blend = s.get("boundaryBlendFactor", 0.5)
        height_gradient_fn = data["height_gradient_fn"]
        height_blend = s.get("heightBlendFactor", 0.5)
        perlin_str = data["perlin_str"]
        brush_strokes = data["brush_strokes"]

        if s.get("runMode") == "A":
            samples = sample_tensor_field_grid(
                s["siteWidth"], s["siteHeight"],
                basis, centers, blend_factor=blend, grid_step=40,
                boundary=boundary, boundary_decay=boundary_decay, boundary_blend=boundary_blend,
                height_gradient_fn=height_gradient_fn, height_blend=height_blend,
                brush_strokes=brush_strokes, brush_decay=80,
                perlin_rotation_scale=0.005, perlin_rotation_strength=perlin_str,
            )
            return {"kind": "A", "mode_a_data": {"samples": samples, "basis": basis, "centers": centers, "brush_strokes": brush_strokes}}

        _base_tensor_fn = create_tensor_field_fn(
            basis, centers, blend,
            boundary=boundary, boundary_decay=boundary_decay, boundary_blend=boundary_blend,
            height_gradient_fn=height_gradient_fn, height_blend=height_blend,
            brush_strokes=brush_strokes, brush_decay=80,
            perlin_rotation_scale=0.005, perlin_rotation_strength=perlin_str,
            perlin_r1=True, perlin_r2=False, perlin_r3=False,
        )

        if s.get("runMode") == "D":
            tensor_fn = _base_tensor_fn
            if data.get("laplacian_smooth"):
                tensor_fn = create_smoothed_tensor_fn(
                    _base_tensor_fn, s["siteWidth"], s["siteHeight"],
                    grid_step=30, smooth_iterations=data.get("smooth_iters", 2),
                )
            seeds = data["hyper_seeds"]
            step_size = data.get("step_size", 2.5)
            max_length = data.get("max_length")
            angle_stop = data.get("angle_stop", 0.3)
            use_major = data.get("use_major", True)
            use_minor = data.get("use_minor", False)
            bounds = (0, 0, s["siteWidth"], s["siteHeight"])
            lines_by_curve = []
            if use_major:
                major_lines = integrate_hyperstreamlines_from_seeds(
                    tensor_fn, seeds, use_major=True, step_size=step_size,
                    max_length=max_length, bounds=bounds, angle_threshold=angle_stop, max_steps=220)
                lines_by_curve.extend(major_lines)
            if use_minor:
                minor_lines = integrate_hyperstreamlines_from_seeds(
                    tensor_fn, seeds, use_major=False, step_size=step_size,
                    max_length=max_length, bounds=bounds, angle_threshold=angle_stop, max_steps=220)
                lines_by_curve.extend(minor_lines)
            if not lines_by_curve:
                lines_by_curve = [[]]
            return {"kind": "D", "lines_by_curve": lines_by_curve}

        line_spacing = s.get("lineSpacing", 65)
        pos_count = s.get("posCount", 10)
        neg_count = s.get("negCount", 10)
        cross_spacing = s.get("crossSpacing", 80)
        use_hyper = data.get("use_hyper", False)
        two_stage = data.get("two_stage", False)

        tensor_fn = _base_tensor_fn
        if data.get("laplacian_smooth"):
            tensor_fn = create_smoothed_tensor_fn(
                _base_tensor_fn, s["siteWidth"], s["siteHeight"],
                grid_step=30, smooth_iterations=data.get("smooth_iters", 2),
            )

        if use_hyper:
            seeds = data.get("hyper_seeds") or list(centers)
            d_sep = line_spacing
            angle_stop = data.get("angle_stop", 0.3)
            if two_stage:
                hyper_graph, xs, ys = two_stage_street_generation(
                    tensor_fn, s["siteWidth"], s["siteHeight"],
                    seed_points=seeds, major_d_sep=d_sep, minor_d_sep=d_sep * 0.6, step_size=2.5,
                    angle_threshold=angle_stop)
            else:
                hyper_graph, xs, ys = generate_streets_from_hyperstreamlines(
                    tensor_fn, s["siteWidth"], s["siteHeight"],
                    seed_points=seeds, d_sep=d_sep, step_size=2.5, angle_threshold=angle_stop)
            return {"kind": "hyper_street", "hyper_street_graph": hyper_graph}
        else:
            lines, xs, ys = generate_streets_from_tensor_field(
                s["siteWidth"], s["siteHeight"],
                basis, centers, blend_factor=blend,
                line_spacing=line_spacing, pos_count=pos_count, neg_count=neg_count,
                cross_spacing=cross_spacing,
                boundary=boundary, boundary_decay=boundary_decay, boundary_blend=boundary_blend,
                height_gradient_fn=height_gradient_fn, height_blend=height_blend,
            )
            return {
                "kind": "B",
                "lines_by_curve": [lines] if lines else [],
                "cross_spacings": [cross_spacing],
                "curve_arrays_by_curve": [(xs, ys)],
            }

    def generate(self):
        if self._generate_after_id:
            self.root.after_cancel(self._generate_after_id)
            self._generate_after_id = None
        if "lineSpacing" not in self.controls:
            return
        s = self.state
        basis = s.get("basisType", BASIS_GRID)
        centers = s.get("tensorCenters", self.tensor_centers)
        if not centers:
            centers = [(s["siteWidth"] / 2, s["siteHeight"] / 2)]
        boundary = self._get_boundary()
        height_gradient_fn = self._get_height_gradient_fn()
        perlin_str = safe_float(self.controls["perlinStrength"].get(), 0.2) if "perlinStrength" in self.controls else 0.2

        data = {
            "state": dict(s),
            "centers": list(centers),
            "boundary": boundary,
            "height_gradient_fn": height_gradient_fn,
            "perlin_str": perlin_str,
            "brush_strokes": [list(st) for st in self.brush_strokes],
            "laplacian_smooth": self.controls.get("laplacianSmooth") and self.controls["laplacianSmooth"].get(),
            "smooth_iters": safe_int(self.controls.get("smoothIters", tk.Scale()).get(), 2) if "smoothIters" in self.controls else 2,
            "use_hyper": "streetGenMode" in self.controls and self.controls["streetGenMode"].get() == STREET_HYPER,
            "two_stage": "twoStage" in self.controls and self.controls["twoStage"].get(),
            "angle_stop": safe_float(self.controls.get("hyperAngleStop", tk.Scale()).get(), 0.3) if "hyperAngleStop" in self.controls else 0.3,
        }
        if s.get("runMode") == "D":
            data["hyper_seeds"] = self.hyperstreamline_seeds if self.hyperstreamline_seeds else list(centers)
            data["step_size"] = safe_float(self.controls["hyperStepSize"].get(), 2.5) if "hyperStepSize" in self.controls else 2.5
            max_len = safe_float(self.controls["hyperMaxLength"].get(), 0) if "hyperMaxLength" in self.controls else 0
            data["max_length"] = max_len if max_len > 0 else None
            hyper_type = self.controls["hyperType"].get() if "hyperType" in self.controls else HYPERSTREAMLINE_MAJOR
            data["use_major"] = hyper_type in (HYPERSTREAMLINE_MAJOR, HYPERSTREAMLINE_BOTH)
            data["use_minor"] = hyper_type in (HYPERSTREAMLINE_MINOR, HYPERSTREAMLINE_BOTH)
        else:
            data["hyper_seeds"] = self.hyperstreamline_seeds if self.hyperstreamline_seeds else list(centers)

        self._show_calculating()
        self._gen_polling = True
        self._gen_thread = threading.Thread(target=self._run_generate_worker, args=(data,), daemon=True)
        self._gen_thread.start()
        self.root.after(80, self._poll_gen_queue)

    def draw_result(self, lines_by_curve=None, cross_spacings=None, curve_arrays_by_curve=None,
                    hyperstreamline_mode=False, hyper_street_graph=None, mode_a_data=None):
        s = self.state
        cross_spacings = cross_spacings or [s["crossSpacing"]]
        curve_arrays_by_curve = curve_arrays_by_curve or []
        lines_by_curve = lines_by_curve or []
        self._export_geometry = {"polylines": [], "parcels": []}

        pw, ph = s["siteWidth"], s["siteHeight"]
        self.canvas.create_rectangle(DRAW_PADDING, DRAW_PADDING, DRAW_PADDING + pw, DRAW_PADDING + ph,
                                     outline="#555555", width=2, dash=(4, 4))
        curve_colors = ["#ff6600", "#66ff00", "#0066ff", "#ff00ff", "#00ffff"]
        perp = s.get("roadsPerpendicular", True)
        use_hierarchy = s.get("roadHierarchy", True)
        use_adaptive = s.get("adaptiveCross", True)
        main_color, main_w = "#e0e0e0", 2
        cross_color, cross_w = "#888888", 1

        # Mode A 预计算数据（来自后台线程）
        if mode_a_data is not None:
            for (x, y, ux, uy, vx, vy) in mode_a_data["samples"]:
                self._draw_cross_glyph(x, y, ux, uy, vx, vy, half_len=12, fill="#66aaff", width=2)
            basis = mode_a_data.get("basis", BASIS_GRID)
            centers = mode_a_data.get("centers", [])
            if basis in (BASIS_RADIAL, BASIS_BLEND, BASIS_BOUNDARY, BASIS_BOUNDARY_BLEND):
                for cx, cy in centers:
                    px, py = self._pad(cx, cy)
                    self.canvas.create_oval(px - 8, py - 8, px + 8, py + 8, fill="#ff6600", outline="#ffffff", width=2)
            for stroke in mode_a_data.get("brush_strokes", []):
                for i in range(len(stroke) - 1):
                    ax, ay = self._pad(stroke[i][0], stroke[i][1])
                    bx, by = self._pad(stroke[i + 1][0], stroke[i + 1][1])
                    self.canvas.create_line(ax, ay, bx, by, fill="#00aa66", width=2, dash=(2, 2))
            if self.brush_draw_mode and self._current_brush_stroke:
                for i in range(len(self._current_brush_stroke) - 1):
                    ax, ay = self._pad(self._current_brush_stroke[i][0], self._current_brush_stroke[i][1])
                    bx, by = self._pad(self._current_brush_stroke[i + 1][0], self._current_brush_stroke[i + 1][1])
                    self.canvas.create_line(ax, ay, bx, by, fill="#00ff88", width=2)
            return

        # B/C + use_hyper: 直接绘制 graph edges，不经过 offset 逻辑
        if hyper_street_graph is not None:
            self._draw_hyper_street_graph(hyper_street_graph)
            return

        # Mode D: 超流线
        if hyperstreamline_mode:
            hyper_type = self.controls["hyperType"].get() if "hyperType" in self.controls else HYPERSTREAMLINE_MAJOR
            use_both = hyper_type == HYPERSTREAMLINE_BOTH
            for idx, line in enumerate(lines_by_curve):
                if not line:
                    continue
                color = "#ff6600" if (use_both and idx < len(lines_by_curve) // 2) else "#0066ff"
                pts = [(p["x"], p["y"]) for p in line]
                self._export_geometry["polylines"].append(pts)
                for i in range(len(pts) - 1):
                    self._draw_line_segment(pts[i], pts[i + 1], color, 2)
            for sx, sy in self.hyperstreamline_seeds:
                px, py = self._pad(sx, sy)
                self.canvas.create_oval(px - 6, py - 6, px + 6, py + 6, fill="#00ff00", outline="#ffffff", width=2)
            return

        # Mode A 由 mode_a_data 分支处理，此处为 B/C
        if s["runMode"] in ("B", "C"):
            for curve_idx, lines in enumerate(lines_by_curve):
                if not lines:
                    continue
                curve_color = curve_colors[curve_idx % len(curve_colors)] if len(lines_by_curve) > 1 else "#ff3300"
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
                cent = (s["siteWidth"] / 2, s["siteHeight"] / 2)
                if s.get("tensorCenters"):
                    pts = s["tensorCenters"]
                    cent = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
                if use_adaptive and xs and ys:
                    t_positions = adaptive_cross_t_positions(
                        xs, ys, sorted_lines,
                        base_spacing=cs,
                        curvature_weight=s.get("curvatureWeight", 0.4),
                        attractor_weight=s.get("attractorWeight", 0.3),
                        value_weight=s.get("valueWeight", 0.2),
                        attractor_x=cent[0],
                        attractor_y=cent[1],
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

                basis = s.get("basisType", BASIS_GRID)
                if basis in (BASIS_RADIAL, BASIS_BLEND, BASIS_BOUNDARY, BASIS_BOUNDARY_BLEND):
                    centers_draw = s.get("tensorCenters", self.tensor_centers)
                    if not centers_draw:
                        centers_draw = [(s["siteWidth"] / 2, s["siteHeight"] / 2)]
                    for cx, cy in centers_draw:
                        px, py = self._pad(cx, cy)
                        self.canvas.create_oval(px - 8, py - 8, px + 8, py + 8, fill="#ff6600", outline="#ffffff", width=2)

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
                            seed=hash(str(s.get("tensorCenters", [(0, 0)]))),
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

        if self.custom_seed_curves:
            colors = ["#ff6600", "#66ff00", "#0066ff", "#ff00ff", "#00ffff"]
            for ci, curve in enumerate(self.custom_seed_curves):
                pts = self._get_curve_points(curve)
                if len(pts) < 2:
                    for x, y in pts:
                        px, py = self._pad(x, y)
                        self.canvas.create_oval(px - 5, py - 5, px + 5, py + 5, fill="#ff3300", outline="#ffffff")
                    continue
                color = colors[ci % len(colors)]
                curve_pts = sample_curve(pts)
                for i in range(len(curve_pts) - 1):
                    self._draw_line_segment(curve_pts[i], curve_pts[i + 1], color, 2)
                for x, y in pts:
                    px, py = self._pad(x, y)
                    self.canvas.create_oval(px - 5, py - 5, px + 5, py + 5, fill=color, outline="#ffffff")

    def _bind_events(self):
        for key, ctrl in self.controls.items():
            if key in ("spacingVal", "scaleVal", "noiseScaleVal", "noiseStrVal", "crossVal",
                       "curvWeightVal", "attrWeightVal", "valWeightVal"):
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
        idx_spacing = SPACING_MODE_OPTS.index(self.controls["spacingMode"].get()) if self.controls["spacingMode"].get() in SPACING_MODE_OPTS else 0
        set_language(lang)
        self._refresh_ui_texts(idx_run, idx_basis, idx_spacing)
        self._update_lang_buttons_state()

    def _update_lang_buttons_state(self):
        """Highlight active language button."""
        is_en = get_language() == "en"
        self.controls["btnLangEN"].config(bg="#3a5a3a" if is_en else "#2a2a2a")
        self.controls["btnLangZH"].config(bg="#3a5a3a" if not is_en else "#2a2a2a")

    def _refresh_ui_texts(self, idx_run=1, idx_basis=0, idx_spacing=0):
        """Refresh all UI text after language change."""
        self.root.title(i18n.T["title"])
        self._title_label.config(text=i18n.T["title"])
        self._subtitle_label.config(text=i18n.T["subtitle"])
        section_texts = [i18n.T["section_run_mode"], i18n.T["section_field_logic"], i18n.TENSOR_CENTER_TITLE,
                        i18n.T["section_expansion"], i18n.T["section_noise"], i18n.T["section_street"]]
        for i, text in enumerate(section_texts):
            if i < len(self._section_labels):
                self._section_labels[i].config(text=text)
        if hasattr(self, "_label_refs"):
            for widget, key in self._label_refs:
                if widget.winfo_exists():
                    text = i18n.T[key] if key in i18n.T else getattr(i18n, key.upper().replace(" ", "_"), key)
                    widget.config(text=text)
        self.controls["runMode"].config(values=i18n.RUN_MODE_OPTS)
        self.controls["runMode"].set(i18n.RUN_MODE_OPTS[min(idx_run, len(i18n.RUN_MODE_OPTS) - 1)])
        self.controls["basisType"].config(values=i18n.BASIS_TYPE_OPTS)
        self.controls["basisType"].set(i18n.BASIS_TYPE_OPTS[min(idx_basis, len(i18n.BASIS_TYPE_OPTS) - 1)])
        self._on_basis_change()
        self.controls["spacingMode"].config(values=i18n.SPACING_MODE_OPTS)
        self.controls["spacingMode"].set(i18n.SPACING_MODE_OPTS[min(idx_spacing, len(i18n.SPACING_MODE_OPTS) - 1)])
        self.controls["btnReset"].config(text=i18n.BTN_RESET)
        self.controls["btnGenerate"].config(text=i18n.BTN_GENERATE)
        self._noise_cb.config(text=i18n.NOISE_ENABLED)
        if "btnDrawRiver" in self.controls:
            self.controls["btnDrawRiver"].config(text=i18n.BTN_DRAW_RIVER if not self.draw_mode else i18n.BTN_DONE_DRAWING)
        if "btnClearRiver" in self.controls:
            self.controls["btnClearRiver"].config(text=i18n.BTN_CLEAR)
        if "btnAddCenter" in self.controls and not self.tensor_center_add_mode:
            self.controls["btnAddCenter"].config(text=i18n.BTN_ADD_CENTER)
        if "btnClearCenters" in self.controls:
            self.controls["btnClearCenters"].config(text=i18n.BTN_CLEAR_CENTERS)
        if "btnLoadHeight" in self.controls:
            self.controls["btnLoadHeight"].config(text=i18n.BTN_LOAD_HEIGHT)
        if "btnClearHeight" in self.controls:
            self.controls["btnClearHeight"].config(text=i18n.BTN_CLEAR_HEIGHT)
        if "btnAddSeed" in self.controls and not self.hyperstreamline_seed_mode:
            self.controls["btnAddSeed"].config(text=i18n.BTN_ADD_SEED)
        if "btnClearSeeds" in self.controls:
            self.controls["btnClearSeeds"].config(text=i18n.BTN_CLEAR_SEEDS)
        self._export_label.config(text=i18n.T["export_rhino"])
        self.controls["btnExportRhino"].config(text=i18n.T["export_py"])
        self.controls["btnExportDxf"].config(text=i18n.T["export_dxf"])
        self._footer_label.config(text=i18n.T["footer"])
        self._refresh_curve_list()
        status = i18n.T["status_default"]
        if self.draw_mode:
            status = "Draw river boundary"
        elif self.brush_draw_mode:
            status = "Draw brush stroke"
        self.status_label.config(text=status)
        self.update_state()

    def _reset(self):
        w, h = safe_float(self.controls["siteWidth"].get(), 1200), safe_float(self.controls["siteHeight"].get(), 200)
        self.tensor_centers = [(w / 2, h / 2)]
        self.brush_strokes = []
        self._current_brush_stroke = []
        self.controls["lineSpacing"].set(65)
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
