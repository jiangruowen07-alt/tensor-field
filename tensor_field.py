"""
张量场 / Tensor Field
每个点有两组互相垂直的方向 (u, v)，用于生成城市道路网格。
支持三种基底：grid, radial, blend
"""

import math

BASIS_GRID = "grid"
BASIS_RADIAL = "radial"
BASIS_BLEND = "blend"


def _normalize(ux, uy):
    """归一化向量"""
    L = math.sqrt(ux * ux + uy * uy) or 1e-10
    return ux / L, uy / L


def _orthogonal(ux, uy):
    """返回与 (ux, uy) 垂直的单位向量"""
    return _normalize(-uy, ux)


def tensor_field_at(x, y, basis, center_x, center_y, blend_factor=0.5):
    """
    在 (x, y) 处计算张量场，返回两组互相垂直的单位方向。

    Returns:
        (ux, uy, vx, vy): u 和 v 为互相垂直的单位向量
    """
    if basis == BASIS_GRID:
        # 网格基底：u=(1,0), v=(0,1)
        return 1.0, 0.0, 0.0, 1.0

    if basis == BASIS_RADIAL:
        # 径向基底：u=径向(向外), v=切向(逆时针)
        dx = x - center_x
        dy = y - center_y
        r = math.sqrt(dx * dx + dy * dy) or 1e-10
        ux, uy = dx / r, dy / r
        vx, vy = _orthogonal(ux, uy)
        return ux, uy, vx, vy

    if basis == BASIS_BLEND:
        # 混合：在 grid 与 radial 之间插值
        # blend_factor: 0=纯 grid, 1=纯 radial
        t = max(0, min(1, blend_factor))

        # grid
        g_ux, g_uy = 1.0, 0.0
        g_vx, g_vy = 0.0, 1.0

        # radial
        dx = x - center_x
        dy = y - center_y
        r = math.sqrt(dx * dx + dy * dy) or 1e-10
        r_ux, r_uy = dx / r, dy / r
        r_vx, r_vy = _orthogonal(r_ux, r_uy)

        # 插值后重新正交化：对 u 插值，v 取 u 的垂直
        ux = (1 - t) * g_ux + t * r_ux
        uy = (1 - t) * g_uy + t * r_uy
        ux, uy = _normalize(ux, uy)
        vx, vy = _orthogonal(ux, uy)
        return ux, uy, vx, vy

    # 默认 grid
    return 1.0, 0.0, 0.0, 1.0


def sample_tensor_field_grid(site_width, site_height, basis, center_x, center_y,
                             blend_factor=0.5, grid_step=25):
    """
    在场地内均匀采样张量场，返回 (x, y, ux, uy, vx, vy) 列表。
    """
    samples = []
    x = grid_step / 2
    while x < site_width:
        y = grid_step / 2
        while y < site_height:
            ux, uy, vx, vy = tensor_field_at(x, y, basis, center_x, center_y, blend_factor)
            samples.append((x, y, ux, uy, vx, vy))
            y += grid_step
        x += grid_step
    return samples


def generate_streets_from_tensor_field(site_width, site_height, basis, center_x, center_y,
                                       blend_factor=0.5, line_spacing=40, pos_count=10, neg_count=10,
                                       cross_spacing=80):
    """
    从张量场生成街道网络线，返回与 offset 引擎兼容的格式。
    Returns: (lines, xs, ys) - lines 为纵向线列表，xs/ys 为中线用于自适应横街
    """
    from config import T_COUNT, T_STEP

    lines = []
    # 纵向线：沿 u 方向偏移
    for side in range(2):
        count = pos_count if side == 1 else neg_count
        start_i = 1 if side == 0 else 0
        for i in range(start_i, count + 1):
            offset_dist = (-i if side == 0 else i) * line_spacing
            line_pts = []
            for ti in range(T_COUNT):
                t = ti * T_STEP
                # 沿中线参数 t：从一端到另一端
                if basis == BASIS_GRID:
                    # 纵向 = 水平线，t 沿 x
                    x = t * site_width
                    y = center_y + offset_dist
                elif basis == BASIS_RADIAL:
                    # 纵向 = 径向射线，offset 为角度偏移
                    angle_spacing = 0.015
                    angle = offset_dist * angle_spacing
                    r = (0.05 + t * 0.95) * min(site_width, site_height) * 0.55
                    x = center_x + r * math.cos(angle)
                    y = center_y + r * math.sin(angle)
                else:
                    # Blend: 近似为 grid
                    x = t * site_width
                    y = center_y + offset_dist
                line_pts.append({"x": x, "y": y, "t": t, "offset": offset_dist})
            lines.append(line_pts)

    # 中线 (xs, ys) 用于自适应横街
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
