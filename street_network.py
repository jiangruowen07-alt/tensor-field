"""
街道网络：道路等级、自适应横街
- 道路等级：primary / secondary / local
- 横街不再固定 t 采样，由曲率、密度、价值、吸引子距离决定
"""

import math

from config import T_COUNT, T_STEP

# 道路等级
ROAD_PRIMARY = "primary"
ROAD_SECONDARY = "secondary"
ROAD_LOCAL = "local"


def curvature_at_index(xs, ys, i):
    """离散曲率：三点 (i-1, i, i+1) 的 Menger 曲率近似"""
    i0 = max(0, i - 1)
    i1 = i
    i2 = min(len(xs) - 1, i + 1)
    if i0 == i1 or i1 == i2:
        return 0.0
    x0, y0 = xs[i0], ys[i0]
    x1, y1 = xs[i1], ys[i1]
    x2, y2 = xs[i2], ys[i2]
    cross = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
    dx1, dy1 = x1 - x0, y1 - y0
    dx2, dy2 = x2 - x1, y2 - y1
    dx3, dy3 = x2 - x0, y2 - y0
    L1 = math.sqrt(dx1 * dx1 + dy1 * dy1) or 1e-10
    L2 = math.sqrt(dx2 * dx2 + dy2 * dy2) or 1e-10
    L3 = math.sqrt(dx3 * dx3 + dy3 * dy3) or 1e-10
    k = 2 * abs(cross) / (L1 * L2 * L3)
    return min(k * 500, 2.0)  # 归一化到合理范围


def curvature_along_curve(xs, ys):
    """沿曲线采样曲率，返回与 xs 同长的列表"""
    n = len(xs)
    curv = [0.0] * n
    if n <= 1:
        return curv
    for i in range(1, n - 1):
        curv[i] = curvature_at_index(xs, ys, i)
    curv[0] = curv[1]
    curv[-1] = curv[-2]
    return curv


def attractor_influence(x, y, center_x, center_y, sigma):
    """吸引子影响：越近中心值越高，0~1"""
    if sigma <= 0:
        return 0.0
    dx, dy = x - center_x, y - center_y
    d2 = dx * dx + dy * dy
    return math.exp(-d2 / (2 * sigma * sigma))


def value_at_point(x, y, value_field):
    """标量场价值：若有 value_field 则调用，否则 0"""
    if value_field is None:
        return 0.0
    try:
        v = value_field(x, y)
        return max(0.0, min(1.0, v))
    except Exception:
        return 0.0


def t_to_index(t):
    """t ∈ [0,1] 转为数组索引"""
    return max(0, min(T_COUNT - 1, int(t / T_STEP)))


def adaptive_cross_t_positions(
    xs,
    ys,
    lines,
    base_spacing=80,
    curvature_weight=0.4,
    attractor_weight=0.3,
    value_weight=0.2,
    attractor_x=None,
    attractor_y=None,
    attractor_sigma=200,
    value_field=None,
    site_width=1200,
    site_height=200,
):
    """
    根据曲率、吸引子、价值计算自适应横街 t 位置。
    返回 t 值列表，不再等距。
    """
    if not lines or not xs or not ys or len(xs) < 2:
        return _fallback_t_positions(base_spacing)

    ax = attractor_x if attractor_x is not None else site_width / 2
    ay = attractor_y if attractor_y is not None else site_height / 2
    curv = curvature_along_curve(xs, ys)
    n_pts = len(xs)
    # 预计算价值与吸引子，避免重复调用
    value_cache = [value_at_point(xs[i], ys[i], value_field) for i in range(n_pts)] if value_field else [0.0] * n_pts
    attr_cache = [attractor_influence(xs[i], ys[i], ax, ay, attractor_sigma) for i in range(n_pts)]

    n_fine = 51
    factors = []
    for i in range(n_fine):
        t = i / max(n_fine - 1, 1)
        idx = t_to_index(t)
        idx = min(idx, n_pts - 1)
        c = curv[idx] if idx < len(curv) else 0
        curv_f = 1 + curvature_weight * c
        attr_f = 1 + attractor_weight * (attr_cache[idx] if idx < len(attr_cache) else 0)
        val_f = 1 + value_weight * (value_cache[idx] if idx < len(value_cache) else 0)
        f = (curv_f + attr_f + val_f) / 3
        factors.append(max(0.3, min(2.5, f)))

    # 累积有效距离
    dt = 1.0 / (n_fine - 1)
    cumulative = [0.0]
    for i in range(1, n_fine):
        avg_f = (factors[i - 1] + factors[i]) / 2
        cumulative.append(cumulative[-1] + dt * avg_f)
    total = cumulative[-1]
    if total < 1e-10:
        return _fallback_t_positions(base_spacing)

    # 目标横街数量：由 base_spacing 换算（原逻辑约 1600/cross_spacing 段）
    num_target = max(3, min(80, int(1600 / max(base_spacing, 20))))
    step = total / max(num_target - 1, 1)

    t_positions = [0.0]
    for k in range(1, num_target):
        target_s = k * step
        # 二分查找 t 使得 cumulative 对应
        lo, hi = 0, n_fine - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if cumulative[mid] < target_s:
                lo = mid
            else:
                hi = mid
        # 线性插值
        s_lo, s_hi = cumulative[lo], cumulative[hi]
        frac = (target_s - s_lo) / (s_hi - s_lo) if s_hi > s_lo else 0
        t = (lo + frac * (hi - lo)) / (n_fine - 1)
        t = max(0, min(1, t))
        t_positions.append(t)
    t_positions.append(1.0)

    # 去重并排序
    seen = set()
    unique = []
    for t in sorted(t_positions):
        key = round(t, 4)
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique


def _fallback_t_positions(base_spacing):
    """固定采样回退"""
    num = max(3, min(51, int(1600 / max(base_spacing, 10))))
    return [j / max(num - 1, 1) for j in range(num)]


def classify_longitudinal_hierarchy(lines):
    """
    纵向线道路等级：按 offset 距离主骨架的远近。
    primary: 主骨架（offset 最接近 0 的 1 条）
    secondary: 紧邻主骨架（offset 次近的 2~4 条）
    local: 其余
    返回 [(line_idx, level), ...]
    """
    if not lines:
        return []
    sorted_by_offset = sorted(enumerate(lines), key=lambda x: abs(x[1][0].get("offset", 0)))
    result = []
    for rank, (idx, line) in enumerate(sorted_by_offset):
        if rank == 0:
            result.append((idx, ROAD_PRIMARY))
        elif rank <= 3:
            result.append((idx, ROAD_SECONDARY))
        else:
            result.append((idx, ROAD_LOCAL))
    return result


def get_line_at_t(lines, t, perp=True):
    """
    在 t 处从各条纵向线采样点，构成横街。
    lines 已按 offset 排序。
    """
    idx = t_to_index(t)
    pts = []
    for line in lines:
        if idx < len(line):
            p = line[idx]
            pts.append((p["x"], p["y"]))
    return pts


def hierarchy_style(level):
    """道路等级对应的线宽、颜色"""
    if level == ROAD_PRIMARY:
        return 2.5, "#e8e8e8"
    if level == ROAD_SECONDARY:
        return 1.5, "#b3b3b3"
    return 0.8, "#666666"
