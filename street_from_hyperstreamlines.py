"""
论文街道生成：从超流线交点构建图 G=(V,E)
- 主/副超流线交替追踪（减少悬空边）
- 交点作为节点 V，超流线段作为边 E
- 支持二阶段：主路 → 分区 → 次路
"""

import math
from hyperstreamline import integrate_hyperstreamline


def _intersect_segments(a1, a2, b1, b2, tol=1e-6):
    """
    线段 a1-a2 与 b1-b2 求交。
    返回 (x, y) 或 None
    """
    x1, y1 = a1[0], a1[1]
    x2, y2 = a2[0], a2[1]
    x3, y3 = b1[0], b1[1]
    x4, y4 = b2[0], b2[1]
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < tol:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
    if 0 <= t <= 1 and 0 <= u <= 1:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def _line_to_segments(line):
    """超流线点列表转为线段列表"""
    segs = []
    for i in range(len(line) - 1):
        p1 = (line[i]["x"], line[i]["y"])
        p2 = (line[i + 1]["x"], line[i + 1]["y"])
        segs.append((p1, p2))
    return segs


def _find_intersections(major_lines, minor_lines):
    """主/副超流线交点"""
    intersections = []
    for mj_line in major_lines:
        mj_segs = _line_to_segments(mj_line)
        for mn_line in minor_lines:
            mn_segs = _line_to_segments(mn_line)
            for s1 in mj_segs:
                for s2 in mn_segs:
                    pt = _intersect_segments(s1[0], s1[1], s2[0], s2[1])
                    if pt:
                        intersections.append(pt)
    return intersections


def _expand_seeds_for_coverage(site_width, site_height, seed_points, min_seeds=6):
    """
    当种子点过少（1-2个）时，在场地上生成均匀分布的多种子，避免街道团成一团。
    单中心或双中心时，超流线易汇聚，需多种子分散覆盖。
    限制种子数以加速计算、避免卡死。
    """
    if seed_points and len(seed_points) >= min_seeds:
        return seed_points
    # 在场地上生成 2x3 或 3x2 网格种子，带边距，限制总数
    margin = 0.12
    n = 3  # 最多 3x3=9 个，通常 2x3=6 个
    seeds = []
    for i in range(n):
        for j in range(n):
            t = (i + 1) / (n + 1)
            s = (j + 1) / (n + 1)
            x = margin * site_width + (1 - 2 * margin) * site_width * t
            y = margin * site_height + (1 - 2 * margin) * site_height * s
            seeds.append((x, y))
    return seeds


def _merge_near_points(points, tol=2.0):
    """合并距离小于 tol 的点，用平方距离避免 sqrt"""
    if not points:
        return []
    tol_sq = tol * tol
    out = [points[0]]
    for p in points[1:]:
        merged = False
        px, py = p[0], p[1]
        for i, q in enumerate(out):
            dx = px - q[0]
            dy = py - q[1]
            if dx * dx + dy * dy < tol_sq:
                out[i] = ((px + q[0]) * 0.5, (py + q[1]) * 0.5)
                merged = True
                break
        if not merged:
            out.append(p)
    return out


def interleaved_hyperstreamlines(
    tensor_fn,
    seed_points,
    d_sep=65,
    step_size=2.0,
    max_steps=220,
    max_length=None,
    bounds=None,
    angle_threshold=0.3,
):
    """
    论文 6.1 交替追踪：主→副→主→副...，减少悬空边。
    从种子开始，沿主方向追踪一条，在 d_sep 处取新种子沿副方向追踪，如此交替。
    Returns: (major_lines, minor_lines)
    """
    def _trace_one(x0, y0, use_major):
        pts = integrate_hyperstreamline(
            tensor_fn, x0, y0,
            use_major=use_major,
            bidirectional=True,
            step_size=step_size,
            max_steps=max_steps,
            max_length=max_length,
            bounds=bounds,
            angle_threshold=angle_threshold,
        )
        return pts

    major_lines = []
    minor_lines = []
    used_seeds = set()

    def _seed_key(x, y):
        return (round(x / 2), round(y / 2))

    queue = [(x, y, True) for x, y in seed_points]
    max_total = 80  # 限制总超流线数量，避免卡死
    while queue and (len(major_lines) + len(minor_lines)) < max_total:
        x0, y0, do_major = queue.pop(0)
        key = _seed_key(x0, y0)
        if key in used_seeds:
            continue
        used_seeds.add(key)

        line = _trace_one(x0, y0, do_major)
        if len(line) < 2:
            continue

        if do_major:
            major_lines.append(line)
        else:
            minor_lines.append(line)

        # 沿超流线每 d_sep 距离添加新种子（论文：交替追踪）
        total = 0
        next_seed_dist = d_sep
        for i in range(len(line) - 1):
            dx = line[i + 1]["x"] - line[i]["x"]
            dy = line[i + 1]["y"] - line[i]["y"]
            seg_len = math.sqrt(dx * dx + dy * dy)
            while total + seg_len >= next_seed_dist:
                t = (next_seed_dist - total) / seg_len if seg_len > 0 else 0
                nx = line[i]["x"] + t * dx
                ny = line[i]["y"] + t * dy
                queue.append((nx, ny, not do_major))
                next_seed_dist += d_sep
            total += seg_len

    return major_lines, minor_lines


def _find_nearest_idx(pt, vertices, tol=5):
    """找最近顶点索引，用平方距离"""
    best = -1
    best_d2 = tol * tol
    ptx, pty = pt[0], pt[1]
    for i, v in enumerate(vertices):
        d2 = (ptx - v[0]) ** 2 + (pty - v[1]) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best = i
    return best


def hyperstreamlines_to_street_graph(
    major_lines,
    minor_lines,
    bounds=None,
):
    """
    从主/副超流线构建街道图 G=(V,E)。
    Returns: {"vertices": [(x,y),...], "edges": [(i,j),...], "edge_pts": [[(x,y),...],...]}
    """
    from geom import clip_segment_to_rect

    if bounds:
        xmin, ymin, xmax, ymax = bounds
    else:
        xmin = ymin = 0
        xmax = ymax = 1e9

    # 收集交点
    intersections = []
    for mj in major_lines:
        mj_segs = _line_to_segments(mj)
        for mn in minor_lines:
            mn_segs = _line_to_segments(mn)
            for s1 in mj_segs:
                for s2 in mn_segs:
                    pt = _intersect_segments(s1[0], s1[1], s2[0], s2[1])
                    if pt and xmin <= pt[0] <= xmax and ymin <= pt[1] <= ymax:
                        intersections.append(pt)

    # 收集所有线段端点
    all_pts = list(intersections)
    for line in major_lines + minor_lines:
        for p in line:
            pt = (p["x"], p["y"])
            if xmin <= pt[0] <= xmax and ymin <= pt[1] <= ymax:
                all_pts.append(pt)

    vertices = _merge_near_points(all_pts, tol=3.0)
    if not vertices:
        return {"vertices": [], "edges": [], "edge_pts": []}

    edges = []
    edge_pts = []

    for line in major_lines + minor_lines:
        for i in range(len(line) - 1):
            p1 = (line[i]["x"], line[i]["y"])
            p2 = (line[i + 1]["x"], line[i + 1]["y"])
            clipped = clip_segment_to_rect(p1, p2, xmin, ymin, xmax, ymax)
            if clipped and len(clipped) == 2:
                a, b = clipped[0], clipped[1]
                d = math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)
                if d > 2:
                    ia = _find_nearest_idx(a, vertices, 8)
                    ib = _find_nearest_idx(b, vertices, 8)
                    if ia >= 0 and ib >= 0 and ia != ib:
                        edges.append((ia, ib))
                        edge_pts.append([a, b])
                    else:
                        edge_pts.append([a, b])

    return {"vertices": vertices, "edges": edges, "edge_pts": edge_pts}


def generate_streets_from_hyperstreamlines(
    tensor_fn,
    site_width,
    site_height,
    seed_points=None,
    d_sep=65,
    step_size=2.0,
    max_length=None,
    angle_threshold=0.3,
):
    """
    论文式街道生成：超流线交替追踪 → 交点图。
    步骤1：追踪 major_lines / minor_lines
    步骤2：根据 major/minor 交点构建 street graph
    Returns: (graph, xs, ys) 其中 graph = {"vertices", "edges", "edge_pts"}
    """
    bounds = (0, 0, site_width, site_height)
    if not seed_points:
        seed_points = [(site_width / 2, site_height / 2)]
    seed_points = _expand_seeds_for_coverage(site_width, site_height, seed_points)

    # 步骤1：追踪主/副超流线
    major_lines, minor_lines = interleaved_hyperstreamlines(
        tensor_fn, seed_points,
        d_sep=d_sep,
        step_size=step_size,
        max_length=max_length,
        bounds=bounds,
        angle_threshold=angle_threshold,
    )

    # 步骤2：根据 major/minor 交点构建 street graph
    graph = hyperstreamlines_to_street_graph(major_lines, minor_lines, bounds=bounds)

    cx = site_width / 2
    cy = site_height / 2
    return graph, [cx], [cy]


def partition_by_major_roads(major_lines, site_width, site_height):
    """
    论文 6.2：主路将区域划分成子区域，用于次路生成。
    major_lines: 主超流线列表
    Returns: list of (polygon, center) 每个子区域的近似多边形和中心
    """
    # 简化：用主路网格划分，返回网格单元
    # 完整实现需要多边形裁剪，这里返回整个场地作为单区域
    return [([(0, 0), (site_width, 0), (site_width, site_height), (0, site_height)],
             (site_width / 2, site_height / 2))]


def generate_minor_roads_in_region(
    tensor_fn,
    region_polygon,
    region_center,
    d_sep=40,
    step_size=2.0,
    bounds=None,
    angle_threshold=0.3,
):
    """
    在子区域内生成次路。可用不同的张量场（局部）。
    """
    if bounds:
        xmin, ymin, xmax, ymax = bounds
        w, h = xmax - xmin, ymax - ymin
        seeds = _expand_seeds_for_coverage(w, h, [region_center], min_seeds=4)
        seeds = [(xmin + x, ymin + y) for x, y in seeds]
    else:
        seeds = [region_center]
    major_lines, minor_lines = interleaved_hyperstreamlines(
        tensor_fn, seeds,
        d_sep=d_sep,
        step_size=step_size,
        bounds=bounds,
        angle_threshold=angle_threshold,
    )
    return major_lines + minor_lines


def two_stage_street_generation(
    tensor_fn,
    site_width,
    site_height,
    seed_points=None,
    major_d_sep=65,
    minor_d_sep=40,
    step_size=2.0,
    angle_threshold=0.3,
):
    """
    论文 6.1+6.2 二阶段：主路 → 分区 → 次路。
    步骤1：追踪 major_lines，再在子区域追踪 minor_lines
    步骤2：根据 major/minor 交点构建 street graph
    Returns: (graph, xs, ys) 其中 graph = {"vertices", "edges", "edge_pts"}
    """
    bounds = (0, 0, site_width, site_height)
    if not seed_points:
        seed_points = [(site_width / 2, site_height / 2)]
    seed_points = _expand_seeds_for_coverage(site_width, site_height, seed_points)

    # 步骤1：追踪主路
    major_lines, _ = interleaved_hyperstreamlines(
        tensor_fn, seed_points,
        d_sep=major_d_sep,
        step_size=step_size,
        bounds=bounds,
        angle_threshold=angle_threshold,
    )

    # 步骤1：在子区域追踪次路
    regions = partition_by_major_roads(major_lines, site_width, site_height)
    minor_lines = []
    for poly, center in regions:
        lines = generate_minor_roads_in_region(
            tensor_fn, poly, center,
            d_sep=minor_d_sep,
            step_size=step_size,
            bounds=bounds,
            angle_threshold=angle_threshold,
        )
        minor_lines.extend(lines)

    # 步骤2：根据 major/minor 交点构建 street graph
    graph = hyperstreamlines_to_street_graph(major_lines, minor_lines, bounds=bounds)

    return graph, [site_width / 2], [site_height / 2]
