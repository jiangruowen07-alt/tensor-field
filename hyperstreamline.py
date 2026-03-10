"""
Hyperstreamline - 从张量场追踪主/副超流线
Major: 沿 u 方向积分
Minor: 沿 v 方向积分
停止条件: 边界、最大步数、最大长度、奇点（方向突变）、接近已有同族流线
"""

import math


def point_segment_distance(pt, a, b):
    """
    点到线段的距离。
    a, b: (x, y) 线段端点
    pt: (x, y) 点
    """
    px, py = pt[0], pt[1]
    ax, ay = a[0], a[1]
    bx, by = b[0], b[1]
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-20:
        return math.sqrt((px - ax) ** 2 + (py - ay) ** 2)
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
    t = max(0, min(1, t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)


def point_polyline_distance(pt, line):
    """
    点到折线的最小距离。
    line: list of dicts with "x", "y" 或 list of (x,y)
    """
    if len(line) < 2:
        return float("inf")
    best = float("inf")
    px, py = pt[0], pt[1]
    for i in range(len(line) - 1):
        a = (line[i]["x"], line[i]["y"]) if isinstance(line[i], dict) else line[i]
        b = (line[i + 1]["x"], line[i + 1]["y"]) if isinstance(line[i + 1], dict) else line[i + 1]
        d = point_segment_distance((px, py), a, b)
        if d < best:
            best = d
    return best


def too_close_to_existing(pt, existing_lines, d_sep):
    """
    检查点 pt 是否与 existing_lines 中任意折线距离 < d_sep。
    existing_lines: [line1, line2, ...] 每条 line 为 [{"x","y"}, ...]
    """
    if not existing_lines or d_sep <= 0:
        return False
    px, py = pt[0], pt[1]
    d_sep_sq = d_sep * d_sep
    for line in existing_lines:
        if len(line) < 2:
            continue
        for i in range(len(line) - 1):
            a = (line[i]["x"], line[i]["y"])
            b = (line[i + 1]["x"], line[i + 1]["y"])
            d_sq = _point_segment_distance_sq((px, py), a, b)
            if d_sq < d_sep_sq:
                return True
    return False


def _point_segment_distance_sq(pt, a, b):
    """点到线段的平方距离，避免 sqrt 以加速"""
    px, py = pt[0], pt[1]
    ax, ay = a[0], a[1]
    bx, by = b[0], b[1]
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-20:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
    t = max(0, min(1, t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return (px - proj_x) ** 2 + (py - proj_y) ** 2


def _get_direction(tensor_fn, x, y, use_major, prev_dx, prev_dy):
    """获取与前一方向一致的单位方向。prev_dx, prev_dy 为 None 时取正向。"""
    ux, uy, vx, vy = tensor_fn(x, y)
    dx, dy = (ux, uy) if use_major else (vx, vy)
    L = math.sqrt(dx * dx + dy * dy) or 1e-10
    dx, dy = dx / L, dy / L
    if prev_dx is not None and (prev_dx * dx + prev_dy * dy) < 0:
        dx, dy = -dx, -dy
    return dx, dy


def _rk4_step(tensor_fn, x, y, use_major, prev_dx, prev_dy, dt):
    """RK4 单步，保持方向一致性"""
    def dir_at(px, py):
        return _get_direction(tensor_fn, px, py, use_major, None, None)

    d1x, d1y = _get_direction(tensor_fn, x, y, use_major, prev_dx, prev_dy)
    k1x, k1y = d1x * dt, d1y * dt

    d2x, d2y = dir_at(x + 0.5 * k1x, y + 0.5 * k1y)
    if prev_dx is not None and (d2x * prev_dx + d2y * prev_dy) < 0:
        d2x, d2y = -d2x, -d2y
    k2x, k2y = d2x * dt, d2y * dt

    d3x, d3y = dir_at(x + 0.5 * k2x, y + 0.5 * k2y)
    if prev_dx is not None and (d3x * prev_dx + d3y * prev_dy) < 0:
        d3x, d3y = -d3x, -d3y
    k3x, k3y = d3x * dt, d3y * dt

    d4x, d4y = dir_at(x + k3x, y + k3y)
    if prev_dx is not None and (d4x * prev_dx + d4y * prev_dy) < 0:
        d4x, d4y = -d4x, -d4y
    k4x, k4y = d4x * dt, d4y * dt

    return x + (k1x + 2 * k2x + 2 * k3x + k4x) / 6, y + (k1y + 2 * k2y + 2 * k3y + k4y) / 6


def _euler_step(tensor_fn, x, y, use_major, prev_dx, prev_dy, dt):
    """Euler 单步，仅 1 次 tensor_fn 调用，比 RK4 快约 4 倍"""
    dx, dy = _get_direction(tensor_fn, x, y, use_major, prev_dx, prev_dy)
    return x + dx * dt, y + dy * dt


def integrate_hyperstreamline(
    tensor_fn,
    x0, y0,
    use_major=True,
    bidirectional=True,
    step_size=2.0,
    max_steps=700,
    max_length=None,
    bounds=None,
    angle_threshold=0.18,
    use_euler=False,
    existing_lines=None,
    d_sep=40,
):
    """
    从 (x0, y0) 追踪一条超流线。

    Args:
        tensor_fn: (x, y) -> (ux, uy, vx, vy)
        use_major: True=主超流线(沿u), False=副超流线(沿v)
        bidirectional: 是否双向积分
        step_size: 积分步长
        max_steps: 单方向最大步数
        max_length: 单方向最大长度，None 表示不限制
        bounds: (xmin, ymin, xmax, ymax)，超出则停止
        angle_threshold: 方向突变阈值，dot < angle_threshold 时停止（0.3≈72°，更宽松以延长流线）
        use_euler: True 用 Euler 积分（快 4 倍，精度略降）
        existing_lines: 已有同族流线列表，新点距其 < d_sep 时停止
        d_sep: 与已有流线的最小间距，小于此值则停止

    Returns:
        list of {"x", "y", "t"} 按积分顺序
    """
    def _integrate_one_dir(x0, y0, sign):
        pts = []
        x, y = x0, y0
        prev_dx, prev_dy = None, None
        pts.append({"x": x, "y": y, "t": 0})
        total_len = 0.0
        dt = sign * step_size

        for i in range(max_steps - 1):
            dx, dy = _get_direction(tensor_fn, x, y, use_major, prev_dx, prev_dy)
            if sign < 0:
                dx, dy = -dx, -dy
            if use_euler:
                x_new, y_new = _euler_step(tensor_fn, x, y, use_major, prev_dx, prev_dy, dt)
            else:
                x_new, y_new = _rk4_step(tensor_fn, x, y, use_major, prev_dx, prev_dy, dt)
            dx_new, dy_new = _get_direction(tensor_fn, x_new, y_new, use_major, dx, dy)
            if sign < 0:
                dx_new, dy_new = -dx_new, -dy_new
            dot = dx * dx_new + dy * dy_new
            if dot < angle_threshold:
                break
            dx, dy = x_new - x, y_new - y
            seg_len = math.sqrt(dx * dx + dy * dy)
            total_len += seg_len
            if max_length is not None and total_len > max_length:
                break
            if bounds:
                xmin, ymin, xmax, ymax = bounds
                if x_new < xmin or x_new > xmax or y_new < ymin or y_new > ymax:
                    break
            local_sep = max(6.0, d_sep * 0.80)
            if existing_lines and d_sep > 0 and too_close_to_existing((x_new, y_new), existing_lines, local_sep):
                break
            pts.append({"x": x_new, "y": y_new, "t": sign * (i + 1) * step_size})
            x, y = x_new, y_new
            prev_dx, prev_dy = dx_new, dy_new
        return pts

    if bidirectional:
        fwd = _integrate_one_dir(x0, y0, 1)
        bwd = _integrate_one_dir(x0, y0, -1)
        if len(bwd) > 1:
            bwd = bwd[1:]
        bwd.reverse()
        for i, p in enumerate(bwd):
            p["t"] = -(len(bwd) - i) * step_size
        return bwd + fwd
    return _integrate_one_dir(x0, y0, 1)


def integrate_hyperstreamlines_from_seeds(
    tensor_fn,
    seed_points,
    use_major=True,
    bidirectional=True,
    step_size=2.0,
    max_steps=700,
    max_length=None,
    bounds=None,
    angle_threshold=0.5,
    use_euler=False,
):
    """
    从多个种子点追踪超流线。
    seed_points: [(x, y), ...]
    use_euler: True 时用 Euler 积分，约快 3 倍
    Returns: [line1, line2, ...] 每条 line 为 [{"x","y","t"}, ...]
    """
    lines = []
    for x0, y0 in seed_points:
        pts = integrate_hyperstreamline(
            tensor_fn, x0, y0,
            use_major=use_major,
            bidirectional=bidirectional,
            step_size=step_size,
            max_steps=max_steps,
            max_length=max_length,
            bounds=bounds,
            angle_threshold=angle_threshold,
            use_euler=use_euler,
        )
        lines.append(pts)
    return lines
