"""
张量场 / Tensor Field
基于论文 "Interactive Procedural Street Modeling" (Chen et al., SIGGRAPH 2008)
使用 2×2 对称无迹矩阵表示，RBF 加权组合设计元素，支持旋转场、笔刷、Laplacian 平滑。
"""

import math

from utils import perlin_noise
from curve import sample_curve

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


def _rbf_weight_fast(dist_sq, d_inv):
    """RBF 权重，d_inv 已预计算"""
    return math.exp(-d_inv * dist_sq)


def _normalize_centers(centers):
    """centers: list of (x,y) or single (x,y) -> list of (x,y)"""
    if not centers:
        return [(0, 0)]
    if isinstance(centers[0], (int, float)):
        return [tuple(centers)]
    return list(centers)


def brush_strokes_to_elements(brush_strokes, brush_decay=80):
    """
    论文 5.2 笔刷：将用户绘制的曲线转为设计元素。
    brush_strokes: list of [(x,y), ...] 每条笔刷折线
    返回设计元素列表
    """
    elements = []
    if not brush_strokes:
        return elements
    brush_d_inv = 1.0 / (brush_decay * brush_decay) if brush_decay > 0 else 0.01
    for stroke in brush_strokes:
        if len(stroke) < 2:
            continue
        sampled = sample_curve(stroke, num_samples=60)
        n = len(sampled)
        for i in range(n):
            x, y = sampled[i][0], sampled[i][1]
            i0, i1 = max(0, i - 1), min(n - 1, i + 1)
            dx = sampled[i1][0] - sampled[i0][0]
            dy = sampled[i1][1] - sampled[i0][1]
            L = math.sqrt(dx * dx + dy * dy) or 1e-10
            tx, ty = dx / L, dy / L
            t = _tensor_from_direction(tx, ty)
            elements.append({"type": "brush", "pos": (x, y), "tensor_const": t, "weight": 1.0, "rbf_decay": brush_decay, "rbf_d_inv": brush_d_inv})
    return elements


def _build_design_elements(basis, centers, blend_factor,
                          boundary, boundary_decay, boundary_blend,
                          height_gradient_fn, height_blend,
                          brush_strokes=None, brush_decay=80):
    """
    从当前 UI 参数构建设计元素列表。
    centers: list of (x,y) 支持多个张量中心
    brush_strokes: list of [(x,y),...] 笔刷折线，论文 5.2
    每个元素: {"type": str, "pos": (x,y), "tensor_fn": (x,y)->(a,b) or None, "tensor_const": (a,b), "weight": float, "rbf_decay": float}
    """
    elements = []
    decay = boundary_decay if boundary_decay > 0 else _DEFAULT_DECAY
    decay_sq_inv = 1.0 / (decay * decay) if decay > 0 else 0.01
    centers = _normalize_centers(centers)
    cx0, cy0 = centers[0]  # 首个中心用于 grid/fallback

    if basis == BASIS_GRID:
        t = _tensor_from_direction(1.0, 0.0)
        elements.append({"type": "grid", "pos": (cx0, cy0), "tensor_const": t, "weight": 1.0, "rbf_decay": 0})

    elif basis == BASIS_RADIAL:
        # 径向基底：不让 radial 独占全局，自动加入更强的 grid 分量。
        # grid 主导全局，radial 作为局部扰动，避免窄场地内大量线被裁剪。
        t_grid = _tensor_from_direction(1.0, 0.0)
        elements.append({"type": "grid", "pos": (cx0, cy0), "tensor_const": t_grid, "weight": 0.55, "rbf_decay": 0})
        for cx, cy in centers:
            def radial_fn(px, py, cxx=cx, cyy=cy):
                dx = px - cxx
                dy = py - cyy
                return _tensor_radial(dx, dy)
            elements.append({"type": "radial", "pos": (cx, cy), "tensor_fn": radial_fn, "weight": 1.0, "rbf_decay": decay, "rbf_d_inv": decay_sq_inv})

    elif basis == BASIS_BLEND:
        bf = max(0, min(1, blend_factor))
        t_grid = _tensor_from_direction(1.0, 0.0)
        elements.append({"type": "grid", "pos": (cx0, cy0), "tensor_const": t_grid, "weight": 1.0 - bf, "rbf_decay": 0})
        for cx, cy in centers:
            def radial_fn(px, py, cxx=cx, cyy=cy):
                dx = px - cxx
                dy = py - cyy
                return _tensor_radial(dx, dy)
            elements.append({"type": "radial", "pos": (cx, cy), "tensor_fn": radial_fn, "weight": bf, "rbf_decay": decay, "rbf_d_inv": decay_sq_inv})

    elif basis == BASIS_BOUNDARY:
        if boundary:
            for bx, by, tx, ty in boundary:
                t = _tensor_from_direction(tx, ty)
                elements.append({"type": "boundary", "pos": (bx, by), "tensor_const": t, "weight": 1.0, "rbf_decay": decay, "rbf_d_inv": decay_sq_inv})
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
                elements.append({"type": "boundary", "pos": (bx, by), "tensor_const": t, "weight": bb, "rbf_decay": decay, "rbf_d_inv": decay_sq_inv})

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

    # 论文 5.2 笔刷：叠加笔刷设计元素
    if brush_strokes:
        elements.extend(brush_strokes_to_elements(brush_strokes, brush_decay))

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
        dx = x - px
        dy = y - py
        dist_sq = dx * dx + dy * dy
        rbf = 1.0 if el["rbf_decay"] <= 0 else _rbf_weight_fast(dist_sq, el["rbf_d_inv"])
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


def _perlin_rotation_at(x, y, scale, strength, which="r1"):
    """论文 5.3：Perlin 噪声生成旋转场，范围 [-π/2, π/2] * strength"""
    n = perlin_noise(x, y, scale=scale)
    angle = n * strength * (math.pi / 2)
    return angle


def create_tensor_field_fn(basis, centers, blend_factor=0.5,
                           boundary=None, boundary_decay=150, boundary_blend=0.5,
                           height_gradient_fn=None, height_blend=0.5,
                           brush_strokes=None, brush_decay=80,
                           perlin_rotation_scale=0.005, perlin_rotation_strength=0,
                           perlin_r1=True, perlin_r2=False, perlin_r3=False):
    """
    创建带缓存设计元素的张量场函数，避免每点重建 elements。
    返回 (x, y) -> (ux, uy, vx, vy)
    """
    elements = _build_design_elements(
        basis, centers, blend_factor,
        boundary, boundary_decay, boundary_blend,
        height_gradient_fn, height_blend,
        brush_strokes=brush_strokes, brush_decay=brush_decay,
    )
    half_pi = math.pi / 2
    pscale = perlin_rotation_scale
    pstr = perlin_rotation_strength

    def fn(x, y):
        t = _compute_tensor_at(x, y, elements)
        if t is None:
            return 1.0, 0.0, 0.0, 1.0
        uv = _tensor_to_eigenvectors(t[0], t[1])
        if uv is None:
            return 1.0, 0.0, 0.0, 1.0
        ux, uy, vx, vy = uv
        pr1 = pr2 = pr3 = 0.0
        if pstr > 0:
            if perlin_r1:
                pr1 = perlin_noise(x, y, scale=pscale) * pstr * half_pi
            if perlin_r2:
                pr2 = perlin_noise(x, y + 1000, scale=pscale) * pstr * half_pi
            if perlin_r3:
                pr3 = perlin_noise(x + 500, y, scale=pscale) * pstr * half_pi
        ux, uy, vx, vy = _apply_rotation(ux, uy, vx, vy, pr1, pr2, pr3)
        return ux, uy, vx, vy

    return fn


def tensor_field_at(x, y, basis, centers, blend_factor=0.5,
                    boundary=None, boundary_decay=150, boundary_blend=0.5,
                    height_gradient_fn=None, height_blend=0.5,
                    r1=0, r2=0, r3=0,
                    brush_strokes=None, brush_decay=80,
                    perlin_rotation_scale=0.005, perlin_rotation_strength=0,
                    perlin_r1=True, perlin_r2=False, perlin_r3=False):
    """
    在 (x, y) 处计算张量场，返回两组互相垂直的单位方向。
    采用论文逻辑：2×2 对称无迹矩阵 + RBF 组合 + 可选旋转场 + 笔刷 + Perlin 噪声。

    Args:
        brush_strokes: list of [(x,y),...] 笔刷折线
        perlin_rotation_scale: Perlin 空间尺度
        perlin_rotation_strength: 旋转强度 [0,1]，0 表示关闭
        perlin_r1/r2/r3: 是否对 R1/R2/R3 应用 Perlin
    """
    elements = _build_design_elements(
        basis, centers, blend_factor,
        boundary, boundary_decay, boundary_blend,
        height_gradient_fn, height_blend,
        brush_strokes=brush_strokes, brush_decay=brush_decay,
    )
    t = _compute_tensor_at(x, y, elements)
    if t is None:
        return 1.0, 0.0, 0.0, 1.0
    uv = _tensor_to_eigenvectors(t[0], t[1])
    if uv is None:
        return 1.0, 0.0, 0.0, 1.0
    ux, uy, vx, vy = uv

    # 论文 5.3 Perlin 旋转
    pr1, pr2, pr3 = r1, r2, r3
    if perlin_rotation_strength > 0:
        if perlin_r1:
            pr1 += _perlin_rotation_at(x, y, perlin_rotation_scale, perlin_rotation_strength, "r1")
        if perlin_r2:
            pr2 += _perlin_rotation_at(x, y, perlin_rotation_scale, perlin_rotation_strength, "r2")
        if perlin_r3:
            pr3 += _perlin_rotation_at(x, y, perlin_rotation_scale, perlin_rotation_strength, "r3")
    ux, uy, vx, vy = _apply_rotation(ux, uy, vx, vy, pr1, pr2, pr3)
    return ux, uy, vx, vy


def laplacian_smooth_tensor_grid(grid_a, grid_b, nx, ny, iterations=3):
    """
    论文 5.2：对网格上的张量场做 Laplacian 平滑。
    双缓冲避免每轮深拷贝，*0.25 替代 /4
    """
    if iterations <= 0:
        return grid_a, grid_b
    # 双缓冲
    buf_a = [row[:] for row in grid_a]
    buf_b = [row[:] for row in grid_b]
    src_a, src_b = grid_a, grid_b
    dst_a, dst_b = buf_a, buf_b
    q = 0.25
    for _ in range(iterations):
        for j in range(1, ny - 1):
            for i in range(1, nx - 1):
                dst_a[j][i] = (src_a[j-1][i] + src_a[j+1][i] + src_a[j][i-1] + src_a[j][i+1]) * q
                dst_b[j][i] = (src_b[j-1][i] + src_b[j+1][i] + src_b[j][i-1] + src_b[j][i+1]) * q
        src_a, dst_a = dst_a, src_a
        src_b, dst_b = dst_b, src_b
    return src_a, src_b


def create_tensor_grid_fn(tensor_fn, site_width, site_height, grid_step=40):
    """
    预计算张量场网格，用双线性插值替代每次完整计算。
    用于超流线加速：一次采样 ~(w/step)*(h/step) 点，之后每次查询 O(1)。
    """
    nx = max(2, int(site_width / grid_step) + 1)
    ny = max(2, int(site_height / grid_step) + 1)
    inv_nx = 1.0 / max(nx - 1, 1)
    inv_ny = 1.0 / max(ny - 1, 1)
    grid_a = [[0.0] * nx for _ in range(ny)]
    grid_b = [[0.0] * nx for _ in range(ny)]
    for j in range(ny):
        for i in range(nx):
            x = i * inv_nx * site_width
            y = j * inv_ny * site_height
            ux, uy, vx, vy = tensor_fn(x, y)
            theta = math.atan2(uy, ux)
            theta2 = 2 * theta
            grid_a[j][i] = math.cos(theta2)
            grid_b[j][i] = math.sin(theta2)

    inv_w = 1.0 / site_width if site_width > 0 else 0
    inv_h = 1.0 / site_height if site_height > 0 else 0
    nx1, ny1 = nx - 1, ny - 1

    def grid_fn(x, y):
        xi = x * inv_w * nx1
        yi = y * inv_h * ny1
        i0 = max(0, min(nx - 2, int(xi)))
        j0 = max(0, min(ny - 2, int(yi)))
        u, v = xi - i0, yi - j0
        omu, omv = 1 - u, 1 - v
        a = omu * omv * grid_a[j0][i0] + omu * v * grid_a[j0+1][i0] + u * omv * grid_a[j0][i0+1] + u * v * grid_a[j0+1][i0+1]
        b = omu * omv * grid_b[j0][i0] + omu * v * grid_b[j0+1][i0] + u * omv * grid_b[j0][i0+1] + u * v * grid_b[j0+1][i0+1]
        return _tensor_to_eigenvectors(a, b) or (1.0, 0.0, 0.0, 1.0)

    return grid_fn


def create_smoothed_tensor_fn(tensor_fn, site_width, site_height, grid_step=20, smooth_iterations=3):
    """
    创建经过 Laplacian 平滑的张量场采样函数。
    在网格上采样、平滑、双线性插值。
    """
    nx = max(2, int(site_width / grid_step) + 1)
    ny = max(2, int(site_height / grid_step) + 1)
    inv_nx = 1.0 / max(nx - 1, 1)
    inv_ny = 1.0 / max(ny - 1, 1)
    grid_a = [[0.0] * nx for _ in range(ny)]
    grid_b = [[0.0] * nx for _ in range(ny)]
    for j in range(ny):
        for i in range(nx):
            x = i * inv_nx * site_width
            y = j * inv_ny * site_height
            ux, uy, vx, vy = tensor_fn(x, y)
            theta = math.atan2(uy, ux)
            theta2 = 2 * theta
            grid_a[j][i] = math.cos(theta2)
            grid_b[j][i] = math.sin(theta2)
    grid_a, grid_b = laplacian_smooth_tensor_grid(grid_a, grid_b, nx, ny, smooth_iterations)

    inv_w = 1.0 / site_width if site_width > 0 else 0
    inv_h = 1.0 / site_height if site_height > 0 else 0
    nx1 = nx - 1
    ny1 = ny - 1

    def smoothed_fn(x, y):
        xi = x * inv_w * nx1
        yi = y * inv_h * ny1
        i0 = max(0, min(nx - 2, int(xi)))
        j0 = max(0, min(ny - 2, int(yi)))
        u = xi - i0
        v = yi - j0
        omu, omv = 1 - u, 1 - v
        a = omu * omv * grid_a[j0][i0] + omu * v * grid_a[j0+1][i0] + u * omv * grid_a[j0][i0+1] + u * v * grid_a[j0+1][i0+1]
        b = omu * omv * grid_b[j0][i0] + omu * v * grid_b[j0+1][i0] + u * omv * grid_b[j0][i0+1] + u * v * grid_b[j0+1][i0+1]
        return _tensor_to_eigenvectors(a, b) or (1.0, 0.0, 0.0, 1.0)

    return smoothed_fn


def sample_tensor_field_grid(site_width, site_height, basis, centers,
                             blend_factor=0.5, grid_step=25,
                             boundary=None, boundary_decay=150, boundary_blend=0.5,
                             height_gradient_fn=None, height_blend=0.5,
                             brush_strokes=None, brush_decay=80,
                             perlin_rotation_scale=0.005, perlin_rotation_strength=0):
    """
    在场地内均匀采样张量场，返回 (x, y, ux, uy, vx, vy) 列表。
    使用缓存的 design elements 加速。
    """
    tensor_fn = create_tensor_field_fn(
        basis, centers, blend_factor,
        boundary=boundary, boundary_decay=boundary_decay, boundary_blend=boundary_blend,
        height_gradient_fn=height_gradient_fn, height_blend=height_blend,
        brush_strokes=brush_strokes, brush_decay=brush_decay,
        perlin_rotation_scale=perlin_rotation_scale,
        perlin_rotation_strength=perlin_rotation_strength,
    )
    samples = []
    half_step = grid_step * 0.5
    x = half_step
    while x < site_width:
        y = half_step
        while y < site_height:
            ux, uy, vx, vy = tensor_fn(x, y)
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
