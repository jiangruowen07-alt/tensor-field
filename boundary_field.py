"""
Boundary Field - 从 river mask / 曲线提取边界，构造沿边界的局部张量
"""

import math

from curve import sample_curve


def extract_boundary_from_image(photo_image, site_width, site_height, river_threshold=200):
    """
    从 river mask 图像提取边界点。
    photo_image: tkinter.PhotoImage，白色/亮色=河流
    Returns: list of (x, y, tx, ty) 或 []（无 PIL 时仅支持 GIF）
    """
    try:
        w, h = photo_image.width(), photo_image.height()
    except Exception:
        return []
    if w < 2 or h < 2:
        return []
    # 缩放坐标到 site
    scale_x = site_width / max(w - 1, 1)
    scale_y = site_height / max(h - 1, 1)
    boundary_pts = []
    for py in range(h):
        for px in range(w):
            try:
                rgb = photo_image.get(px, py)
            except Exception:
                continue
            if isinstance(rgb, str):
                rgb = (int(rgb[1:3], 16), int(rgb[3:5], 16), int(rgb[5:7], 16))
            elif isinstance(rgb, (list, tuple)) and len(rgb) >= 3:
                rgb = tuple(rgb[:3])
            else:
                continue
            bright = sum(rgb) / 3 if isinstance(rgb, (tuple, list)) else 0
            is_river = bright >= river_threshold
            if not is_river:
                continue
            # 检查邻域是否有非河流 -> 边界点
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = px + dx, py + dy
                if 0 <= nx < w and 0 <= ny < h:
                    try:
                        nrgb = photo_image.get(nx, ny)
                    except Exception:
                        continue
                    if isinstance(nrgb, str):
                        nrgb = (int(nrgb[1:3], 16), int(nrgb[3:5], 16), int(nrgb[5:7], 16))
                    nbright = sum(nrgb[:3]) / 3 if isinstance(nrgb, (tuple, list)) else 0
                    if nbright < river_threshold:
                        x = px * scale_x
                        y = py * scale_y
                        tx = -dy
                        ty = dx
                        boundary_pts.append((x, y, tx, ty))
                        break
    return boundary_pts


def extract_boundary_from_curve(points, num_samples=120):
    """
    从曲线点提取边界：采样点 + 每点切向。
    Returns: list of (x, y, tx, ty) - 位置与单位切向
    """
    if not points or len(points) < 2:
        return []
    sampled = sample_curve(points, num_samples=num_samples)
    if len(sampled) < 2:
        return []
    boundary = []
    n = len(sampled)
    for i in range(n):
        x, y = sampled[i][0], sampled[i][1]
        i0 = (i - 1) % n
        i1 = (i + 1) % n
        dx = sampled[i1][0] - sampled[i0][0]
        dy = sampled[i1][1] - sampled[i0][1]
        L = math.sqrt(dx * dx + dy * dy) or 1e-10
        tx, ty = dx / L, dy / L
        boundary.append((x, y, tx, ty))
    return boundary


def nearest_on_boundary(x, y, boundary):
    """
    求 (x,y) 到边界的最短距离点。
    Returns: (bx, by, tx, ty, d2) 或 None，d2 为平方距离
    """
    if not boundary:
        return None
    best = None
    best_d2 = 1e30
    for i in range(len(boundary)):
        bx, by, tx, ty = boundary[i][0], boundary[i][1], boundary[i][2], boundary[i][3]
        dx, dy = x - bx, y - by
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_d2 = d2
            best = (bx, by, tx, ty, d2)
    return best


def boundary_tensor_at(x, y, boundary, decay=150):
    """
    在 (x,y) 处根据边界计算张量：u=边界切向，v=法向。
    距离衰减：越近边界影响越强。
    """
    if not boundary:
        return None
    nn = nearest_on_boundary(x, y, boundary)
    if nn is None:
        return None
    bx, by, tx, ty, d2 = nn
    decay_sq = decay * decay
    w = math.exp(-d2 / decay_sq)
    if w < 0.01:
        return None  # 太远，不贡献
    ux, uy = tx, ty
    vx, vy = -ty, tx  # 法向
    return (ux, uy, vx, vy, w)
