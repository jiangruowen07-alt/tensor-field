"""
Hyperstreamline - 从张量场追踪主/副超流线
Major: 沿 u 方向积分
Minor: 沿 v 方向积分
停止条件: 边界、最大步数、最大长度、奇点（方向突变）
"""

import math


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


def integrate_hyperstreamline(
    tensor_fn,
    x0, y0,
    use_major=True,
    bidirectional=True,
    step_size=2.0,
    max_steps=500,
    max_length=None,
    bounds=None,
    angle_threshold=0.3,
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

    Returns:
        list of {"x", "y", "t"} 按积分顺序
    """
    def _integrate_one_dir(x0, y0, sign):
        pts = []
        x, y = x0, y0
        prev_dx, prev_dy = None, None
        pts.append({"x": x, "y": y, "t": 0})
        total_len = 0.0

        for i in range(max_steps - 1):
            dx, dy = _get_direction(tensor_fn, x, y, use_major, prev_dx, prev_dy)
            if sign < 0:
                dx, dy = -dx, -dy
            x_new, y_new = _rk4_step(tensor_fn, x, y, use_major, prev_dx, prev_dy, sign * step_size)
            dx_new, dy_new = _get_direction(tensor_fn, x_new, y_new, use_major, dx, dy)
            if sign < 0:
                dx_new, dy_new = -dx_new, -dy_new
            dot = dx * dx_new + dy * dy_new
            if dot < angle_threshold:
                break
            seg_len = math.sqrt((x_new - x) ** 2 + (y_new - y) ** 2)
            total_len += seg_len
            if max_length is not None and total_len > max_length:
                break
            if bounds:
                xmin, ymin, xmax, ymax = bounds
                if x_new < xmin or x_new > xmax or y_new < ymin or y_new > ymax:
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
    max_steps=500,
    max_length=None,
    bounds=None,
    angle_threshold=0.5,
):
    """
    从多个种子点追踪超流线。
    seed_points: [(x, y), ...]
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
        )
        lines.append(pts)
    return lines
