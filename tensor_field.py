"""
张量场 / Tensor Field
基于论文 "Interactive Procedural Street Modeling" (Chen et al., SIGGRAPH 2008)
使用 2×2 对称无迹矩阵表示，RBF 加权组合设计元素，支持旋转场。
"""

import math

BASIS_GRID = "grid"
BASIS_RADIAL = "radial"
BASIS_BLEND = "blend"
BASIS_BOUNDARY = "boundary"
BASIS_BOUNDARY_BLEND = "boundary_blend"
BASIS_HEIGHT = "height"
BASIS_HEIGHT_BLEND = "height_blend"

# RBF 衰减常数：论文 T(p) = Σ exp(-d||p-pi||²) Ti(p)
# d 越大衰减越快，用 1/decay² 使距离 decay 时权重≈exp(-1)
_DEFAULT_DECAY = 150


def _normalize(ux, uy):
    """归一化向量"""
    L = math.sqrt(ux * ux + uy * uy) or 1e-10
    return ux / L, uy / L


def _orthogonal(ux, uy):
    """返回与 (ux, uy) 垂直的单位向量"""
    return _normalize(-uy, ux)


# ---------------------------------------------------------------------------
# 论文式张量：2×2 对称无迹矩阵 T = R * [[cos 2θ, sin 2θ], [sin 2θ, -cos 2θ]]
# 存储为 (a, b)，矩阵为 [[a, b], [b, -a]]，其中 a=R*cos(2θ), b=R*sin(2θ)
# ---------------------------------------------------------------------------


def _tensor_from_direction(ux, uy, scale=1.0):
    """
    论文 Eq.(1) Grid/Regular 基底：方向 (ux, uy)，l=||(ux,uy)||, θ=atan2(uy,ux)
    T = l * [[cos 2θ, sin 2θ], [sin 2θ, -cos 2θ]]
    返回 (a, b) 即矩阵 [[a,b],[b,-a]]
    """
    l = math.sqrt(ux * ux + uy * uy) or 1e-10
    theta = math.atan2(uy, ux)
    c2 = math.cos(2 * theta)
    s2 = math.sin(2 * theta)
    R = l * scale
    return R * c2, R * s2


def _tensor_radial(x, y):
    """
    论文 Eq.(2) Radial 基底：x=xp-x0, y=yp-y0
    T = [[y²-x², -2xy], [-2xy, -(y²-x²)]]
    返回 (a, b)，矩阵 [[a,b],[b,-a]]，a=y²-x², b=-2xy
    """
    xx = x * x
    yy = y * y
    xy = x * y
    a = yy - xx
    b = -2 * xy
    return a, b


def _tensor_height(gx, gy):
    """
    论文 Heightfield：minor eigenvector 匹配梯度，θ = atan2(gy,gx) + π/2
    R = ||∇H||, T = R * [[cos 2θ, sin 2θ], [sin 2θ, -cos 2θ]]
    """
    R = math.sqrt(gx * gx + gy * gy)
    if R < 1e-10:
        return None
    theta = math.atan2(gy, gx) + math.pi / 2
    c2 = math.cos(2 * theta)
    s2 = math.sin(2 * theta)
    return R * c2, R * s2


def _tensor_add(ta, tb, wa=1.0, wb=1.0):
    """矩阵加权相加：T = wa*Ta + wb*Tb，返回 (a, b)"""
    if ta is None:
        return (wb * tb[0], wb * tb[1]) if tb else None
    if tb is None:
        return (wa * ta[0], wa * ta[1])
    return wa * ta[0] + wb * tb[0], wa * ta[1] + wb * tb[1]


def _tensor_to_eigenvectors(a, b):
    """
    从对称无迹矩阵 [[a,b],[b,-a]] 提取主/副特征向量。
    特征值 λ = ±sqrt(a²+b²)，主特征向量对应 λ=+sqrt(a²+b²)。
    返回 (ux, uy, vx, vy) 单位向量，退化时返回 None。
    """
    norm_sq = a * a + b * b
    if norm_sq < 1e-20:
        return None
    lam = math.sqrt(norm_sq)
    # 主特征向量 (b, lam-a)；当 b≈0 时 (b, lam-a)=(0,0)，需特殊处理
    if abs(b) < 1e-10:
        if a > 0:
            return 1.0, 0.0, 0.0, 1.0
        return 0.0, 1.0, -1.0, 0.0
    ux, uy = b, lam - a
    L = math.sqrt(ux * ux + uy * uy) or 1e-10
    ux, uy = ux / L, uy / L
    vx, vy = _orthogonal(ux, uy)
    return ux, uy, vx, vy


def _apply_rotation(ux, uy, vx, vy, r1=0, r2=0, r3=0):
    """
    论文 5.3 旋转场：R1 同时旋转主副（反向），R2 仅主，R3 仅副。
    角度单位为弧度。
    """
    if abs(r1) < 1e-10 and abs(r2) < 1e-10 and abs(r3) < 1e-10:
        return ux, uy, vx, vy
    c1, s1 = math.cos(r1), math.sin(r1)
    c2, s2 = math.cos(r2), math.sin(r2)
    c3, s3 = math.cos(r3), math.sin(r3)
    # R1: 主 +r1, 副 -r1
    ux2 = ux * c1 - uy * s1
    uy2 = ux * s1 + uy * c1
    vx2 = vx * c1 + vy * s1
    vy2 = -vx * s1 + vy * c1
    # R2: 仅主
    ux2, uy2 = ux2 * c2 - uy2 * s2, ux2 * s2 + uy2 * c2
    # R3: 仅副
    vx2, vy2 = vx2 * c3 - vy2 * s3, vx2 * s3 + vy2 * c3
    return ux2, uy2, vx2, vy2


def _rbf_weight(dist_sq, decay):
    """RBF 权重 exp(-d * dist²)，d = 1/decay²"""
    d = 1.0 / (decay * decay) if decay > 0 else 0.01
    return math.exp(-d * dist_sq)


def _normalize_centers(centers):
    """centers: list of (x,y) or single (x,y) -> list of (x,y)"""
    if not centers:
        return [(0, 0)]
    if isinstance(centers[0], (int, float)):
        return [tuple(centers)]
    return list(centers)


def _build_design_elements(basis, centers, blend_factor,
                          boundary, boundary_decay, boundary_blend,
                          height_gradient_fn, height_blend):
    """
    从当前 UI 参数构建设计元素列表。
    centers: list of (x,y) 支持多个张量中心
    每个元素: {"type": str, "pos": (x,y), "tensor_fn": (x,y)->(a,b) or None, "tensor_const": (a,b), "weight": float, "rbf_decay": float}
    """
    elements = []
    decay = boundary_decay if boundary_decay > 0 else _DEFAULT_DECAY
    centers = _normalize_centers(centers)
    cx0, cy0 = centers[0]  # 首个中心用于 grid/fallback

    if basis == BASIS_GRID:
        t = _tensor_from_direction(1.0, 0.0)
        elements.append({"type": "grid", "pos": (cx0, cy0), "tensor_const": t, "weight": 1.0, "rbf_decay": 0})

    elif basis == BASIS_RADIAL:
        for cx, cy in centers:
            def radial_fn(px, py, cxx=cx, cyy=cy):
                dx = px - cxx
                dy = py - cyy
                return _tensor_radial(dx, dy)
            elements.append({"type": "radial", "pos": (cx, cy), "tensor_fn": radial_fn, "weight": 1.0, "rbf_decay": decay})

    elif basis == BASIS_BLEND:
        bf = max(0, min(1, blend_factor))
        t_grid = _tensor_from_direction(1.0, 0.0)
        elements.append({"type": "grid", "pos": (cx0, cy0), "tensor_const": t_grid, "weight": 1.0 - bf, "rbf_decay": 0})
        for cx, cy in centers:
            def radial_fn(px, py, cxx=cx, cyy=cy):
                dx = px - cxx
                dy = py - cyy
                return _tensor_radial(dx, dy)
            elements.append({"type": "radial", "pos": (cx, cy), "tensor_fn": radial_fn, "weight": bf, "rbf_decay": decay})

    elif basis == BASIS_BOUNDARY:
        if boundary:
            for bx, by, tx, ty in boundary:
                t = _tensor_from_direction(tx, ty)
                elements.append({"type": "boundary", "pos": (bx, by), "tensor_const": t, "weight": 1.0, "rbf_decay": decay})
        if not elements:
            t = _tensor_from_direction(1.0, 0.0)
            elements.append({"type": "grid", "pos": (cx0, cy0), "tensor_const": t, "weight": 1.0, "rbf_decay": 0})

    elif basis == BASIS_BOUNDARY_BLEND:
        bb = max(0, min(1, boundary_blend))
        t_grid = _tensor_from_direction(1.0, 0.0)
        elements.append({"type": "grid", "pos": (cx0, cy0), "tensor_const": t_grid, "weight": (1.0 - bb), "rbf_decay": 0})
        if boundary:
            for bx, by, tx, ty in boundary:
                t = _tensor_from_direction(tx, ty)
                elements.append({"type": "boundary", "pos": (bx, by), "tensor_const": t, "weight": bb, "rbf_decay": decay})

    elif basis == BASIS_HEIGHT:
        if height_gradient_fn:
            def height_fn(px, py):
                gx, gy = height_gradient_fn(px, py)
                return _tensor_height(gx, gy)
            elements.append({"type": "height", "pos": (cx0, cy0), "tensor_fn": height_fn, "weight": 1.0, "rbf_decay": 0})
        if not elements:
            t = _tensor_from_direction(1.0, 0.0)
            elements.append({"type": "grid", "pos": (cx0, cy0), "tensor_const": t, "weight": 1.0, "rbf_decay": 0})

    elif basis == BASIS_HEIGHT_BLEND:
        hb = max(0, min(1, height_blend))
        t_grid = _tensor_from_direction(1.0, 0.0)
        elements.append({"type": "grid", "pos": (cx0, cy0), "tensor_const": t_grid, "weight": (1.0 - hb), "rbf_decay": 0})
        if height_gradient_fn:
            def height_fn(px, py):
                gx, gy = height_gradient_fn(px, py)
                return _tensor_height(gx, gy)
            elements.append({"type": "height", "pos": (cx0, cy0), "tensor_fn": height_fn, "weight": hb, "rbf_decay": 0})

    else:
        t = _tensor_from_direction(1.0, 0.0)
        elements.append({"type": "grid", "pos": (cx0, cy0), "tensor_const": t, "weight": 1.0, "rbf_decay": 0})

    return elements


def _compute_tensor_at(x, y, elements):
    """
    论文 Eq.(3) 组合：T(p) = Σ exp(-d||p-pi||²) * weight_i * Ti(p)
    返回 (a, b) 或 None（全退化）
    """
    total_a, total_b = 0.0, 0.0
    total_w = 0.0

    for el in elements:
        px, py = el["pos"]
        dist_sq = (x - px) ** 2 + (y - py) ** 2
        rbf = 1.0 if el["rbf_decay"] <= 0 else _rbf_weight(dist_sq, el["rbf_decay"])
        w = el["weight"] * rbf
        if w < 1e-6:
            continue

        if "tensor_const" in el:
            ta, tb = el["tensor_const"]
        else:
            t = el["tensor_fn"](x, y)
            if t is None:
                continue
            ta, tb = t

        total_a += w * ta
        total_b += w * tb
        total_w += w

    if total_w < 1e-10:
        return None
    # 论文式直接求和，不归一化（特征向量与缩放无关）
    return total_a, total_b


def tensor_field_at(x, y, basis, centers, blend_factor=0.5,
                    boundary=None, boundary_decay=150, boundary_blend=0.5,
                    height_gradient_fn=None, height_blend=0.5,
                    r1=0, r2=0, r3=0):
    """
    在 (x, y) 处计算张量场，返回两组互相垂直的单位方向。
    采用论文逻辑：2×2 对称无迹矩阵 + RBF 组合 + 可选旋转场。

    Args:
        centers: list of (x,y) 张量中心，支持多个；或 (center_x, center_y) 单中心
        boundary: list of (x, y, tx, ty) from extract_boundary_from_curve
        boundary_decay: 边界 RBF 衰减距离
        boundary_blend: boundary_blend 模式下与 grid 的混合 (0=纯grid, 1=纯boundary)
        height_gradient_fn: callable (x,y)->(gx,gy) 用于 height/height_blend 基底
        height_blend: height_blend 模式下与 grid 的混合 (0=纯grid, 1=纯height)
        r1, r2, r3: 旋转场弧度，默认 0

    Returns:
        (ux, uy, vx, vy): u 和 v 为互相垂直的单位向量
    """
    elements = _build_design_elements(
        basis, centers, blend_factor,
        boundary, boundary_decay, boundary_blend,
        height_gradient_fn, height_blend,
    )
    t = _compute_tensor_at(x, y, elements)
    if t is None:
        return 1.0, 0.0, 0.0, 1.0
    uv = _tensor_to_eigenvectors(t[0], t[1])
    if uv is None:
        return 1.0, 0.0, 0.0, 1.0
    ux, uy, vx, vy = uv
    ux, uy, vx, vy = _apply_rotation(ux, uy, vx, vy, r1, r2, r3)
    return ux, uy, vx, vy


def sample_tensor_field_grid(site_width, site_height, basis, centers,
                             blend_factor=0.5, grid_step=25,
                             boundary=None, boundary_decay=150, boundary_blend=0.5,
                             height_gradient_fn=None, height_blend=0.5):
    """
    在场地内均匀采样张量场，返回 (x, y, ux, uy, vx, vy) 列表。
    centers: list of (x,y) 或 (center_x, center_y)
    """
    samples = []
    x = grid_step / 2
    while x < site_width:
        y = grid_step / 2
        while y < site_height:
            ux, uy, vx, vy = tensor_field_at(
                x, y, basis, centers, blend_factor,
                boundary=boundary, boundary_decay=boundary_decay,
                boundary_blend=boundary_blend,
                height_gradient_fn=height_gradient_fn, height_blend=height_blend,
            )
            samples.append((x, y, ux, uy, vx, vy))
            y += grid_step
        x += grid_step
    return samples


def _centroid(centers):
    """多中心时取质心"""
    centers = _normalize_centers(centers)
    n = len(centers)
    cx = sum(p[0] for p in centers) / n
    cy = sum(p[1] for p in centers) / n
    return cx, cy


def generate_streets_from_tensor_field(site_width, site_height, basis, centers,
                                       blend_factor=0.5, line_spacing=40, pos_count=10, neg_count=10,
                                       cross_spacing=80,
                                       boundary=None, boundary_decay=150, boundary_blend=0.5,
                                       height_gradient_fn=None, height_blend=0.5):
    """
    从张量场生成街道网络线，返回与 offset 引擎兼容的格式。
    centers: list of (x,y) 或 (center_x, center_y)，多中心时用质心
    Returns: (lines, xs, ys) - lines 为纵向线列表，xs/ys 为中线用于自适应横街
    """
    from config import T_COUNT, T_STEP

    center_x, center_y = _centroid(centers)

    lines = []
    for side in range(2):
        count = pos_count if side == 1 else neg_count
        start_i = 1 if side == 0 else 0
        for i in range(start_i, count + 1):
            offset_dist = (-i if side == 0 else i) * line_spacing
            line_pts = []
            for ti in range(T_COUNT):
                t = ti * T_STEP
                if basis == BASIS_GRID:
                    x = t * site_width
                    y = center_y + offset_dist
                elif basis == BASIS_RADIAL:
                    angle_spacing = 0.015
                    angle = offset_dist * angle_spacing
                    r = (0.05 + t * 0.95) * min(site_width, site_height) * 0.55
                    x = center_x + r * math.cos(angle)
                    y = center_y + r * math.sin(angle)
                elif basis == BASIS_BOUNDARY and boundary:
                    x = t * site_width
                    y = center_y + offset_dist
                elif basis in (BASIS_HEIGHT, BASIS_HEIGHT_BLEND):
                    x = t * site_width
                    y = center_y + offset_dist
                else:
                    x = t * site_width
                    y = center_y + offset_dist
                line_pts.append({"x": x, "y": y, "t": t, "offset": offset_dist})
            lines.append(line_pts)

    xs, ys = [], []
    for ti in range(T_COUNT):
        t = ti * T_STEP
        if basis == BASIS_GRID:
            xs.append(t * site_width)
            ys.append(center_y)
        else:
            xs.append(center_x + t * site_width * 0.5)
            ys.append(center_y)
    return lines, xs, ys
