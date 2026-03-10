"""
几何工具：矩形裁剪、点/线段/折线/多边形裁剪
"""


def inside(p, xmin, ymin, xmax, ymax):
    """点是否在矩形内"""
    return xmin <= p[0] <= xmax and ymin <= p[1] <= ymax


def clip_segment_to_rect(p0, p1, xmin, ymin, xmax, ymax):
    """
    Cohen-Sutherland 线段裁剪
    返回裁剪后的线段 [(x,y),(x,y)] 或 None，顺序与 p0->p1 一致
    """
    x0, y0 = p0
    x1, y1 = p1
    orig_p0 = p0
    LEFT, RIGHT, BOTTOM, TOP = 1, 2, 4, 8

    def code(x, y):
        c = 0
        if x < xmin:
            c |= LEFT
        elif x > xmax:
            c |= RIGHT
        if y < ymin:
            c |= BOTTOM
        elif y > ymax:
            c |= TOP
        return c

    c0, c1 = code(x0, y0), code(x1, y1)
    while True:
        if c0 == 0 and c1 == 0:
            a, b = (x0, y0), (x1, y1)
            da0, da1 = a[0] - orig_p0[0], a[1] - orig_p0[1]
            db0, db1 = b[0] - orig_p0[0], b[1] - orig_p0[1]
            d_a = da0 * da0 + da1 * da1
            d_b = db0 * db0 + db1 * db1
            if d_a > d_b:
                a, b = b, a
            return [a, b]
        if c0 & c1:
            return None
        if c0 == 0:
            x0, y0, x1, y1, c0, c1 = x1, y1, x0, y0, c1, c0
        c = c0
        if c & LEFT:
            y0 = y0 + (y1 - y0) * (xmin - x0) / (x1 - x0) if x1 != x0 else y0
            x0 = xmin
        elif c & RIGHT:
            y0 = y0 + (y1 - y0) * (xmax - x0) / (x1 - x0) if x1 != x0 else y0
            x0 = xmax
        elif c & BOTTOM:
            x0 = x0 + (x1 - x0) * (ymin - y0) / (y1 - y0) if y1 != y0 else x0
            y0 = ymin
        elif c & TOP:
            x0 = x0 + (x1 - x0) * (ymax - y0) / (y1 - y0) if y1 != y0 else x0
            y0 = ymax
        c0 = code(x0, y0)


def same_pt(a, b, tol=1e-10):
    """两点是否相同（在容差内）"""
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def clip_polyline_to_rect(pts, xmin, ymin, xmax, ymax):
    """折线裁剪到矩形，返回裁剪后的折线列表（可能被裁成多段）"""
    if len(pts) < 2:
        return []
    result = []
    current = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        seg = clip_segment_to_rect(p0, p1, xmin, ymin, xmax, ymax)
        if seg is None:
            if current:
                result.append(current)
                current = []
            continue
        a, b = seg[0], seg[1]
        if not current:
            current = [a]
        elif not same_pt(a, current[-1]):
            result.append(current)
            current = [a]
        if not same_pt(b, a):
            current.append(b)
        if not inside(p1, xmin, ymin, xmax, ymax):
            result.append(current)
            current = []
    if current:
        result.append(current)
    return [p for p in result if len(p) >= 2]


def split_segment_inside_outside(p0, p1, xmin, ymin, xmax, ymax):
    """
    将线段按矩形边界分割为内部/外部部分。
    返回 [(inside, [(x,y),(x,y)]), (outside, [(x,y),(x,y)]), ...]
    """
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0

    def inside(px, py):
        return xmin <= px <= xmax and ymin <= py <= ymax

    t_values = [0.0, 1.0]
    if abs(dx) > 1e-12:
        for x in (xmin, xmax):
            t = (x - x0) / dx
            if 0 < t < 1:
                py = y0 + t * dy
                if ymin <= py <= ymax:
                    t_values.append(t)
    if abs(dy) > 1e-12:
        for y in (ymin, ymax):
            t = (y - y0) / dy
            if 0 < t < 1:
                px = x0 + t * dx
                if xmin <= px <= xmax:
                    t_values.append(t)
    t_values = sorted(set(t_values))

    result = []
    for i in range(len(t_values) - 1):
        ta, tb = t_values[i], t_values[i + 1]
        mid_t = (ta + tb) / 2
        mx = x0 + mid_t * dx
        my = y0 + mid_t * dy
        seg = [(x0 + ta * dx, y0 + ta * dy), (x0 + tb * dx, y0 + tb * dy)]
        if inside(mx, my):
            result.append(("inside", seg))
        else:
            result.append(("outside", seg))
    return result


def clip_polygon_to_rect(pts, xmin, ymin, xmax, ymax):
    """Sutherland-Hodgman 多边形裁剪到矩形，返回裁剪后的多边形列表"""
    if len(pts) < 3:
        return []

    def cross_inside(px, py, x1, y1, x2, y2):
        return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1) >= 0

    def intersect(p, q, x1, y1, x2, y2):
        px, py = p
        qx, qy = q
        dx, dy = qx - px, qy - py
        ex, ey = x2 - x1, y2 - y1
        denom = ex * dy - ey * dx
        if abs(denom) < 1e-12:
            return (px, py)
        t = (ex * (y1 - py) - ey * (x1 - px)) / denom
        t = max(0, min(1, t))
        return (px + t * dx, py + t * dy)

    def clip_edge(subject, x1, y1, x2, y2):
        out = []
        for i in range(len(subject)):
            v1 = subject[i]
            v0 = subject[(i - 1) % len(subject)]
            inside_v0 = cross_inside(v0[0], v0[1], x1, y1, x2, y2)
            inside_v1 = cross_inside(v1[0], v1[1], x1, y1, x2, y2)
            if inside_v0 and inside_v1:
                out.append(v1)
            elif inside_v0 and not inside_v1:
                out.append(intersect(v0, v1, x1, y1, x2, y2))
            elif not inside_v0 and inside_v1:
                out.append(intersect(v0, v1, x1, y1, x2, y2))
                out.append(v1)
        return out

    poly = list(pts)
    for (x1, y1, x2, y2) in [(xmin, ymin, xmax, ymin), (xmax, ymin, xmax, ymax),
                             (xmax, ymax, xmin, ymax), (xmin, ymax, xmin, ymin)]:
        poly = clip_edge(poly, x1, y1, x2, y2)
        if not poly:
            return []
    return [poly] if len(poly) >= 3 else []
