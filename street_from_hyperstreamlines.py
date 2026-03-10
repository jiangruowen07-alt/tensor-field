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


def _lines_to_segments_cache(lines):
    """批量缓存线段，避免重复计算"""
    return [_line_to_segments(ln) for ln in lines]


def _find_intersections(major_segs, minor_segs):
    """主/副超流线交点，接收预计算的 segments"""
    intersections = []
    for mj_segs in major_segs:
        for mn_segs in minor_segs:
            for s1 in mj_segs:
                for s2 in mn_segs:
                    pt = _intersect_segments(s1[0], s1[1], s2[0], s2[1])
                    if pt:
                        intersections.append(pt)
    return intersections


def _polyline_length(line):
    """折线总长度"""
    if len(line) < 2:
        return 0.0
    total = 0.0
    for i in range(len(line) - 1):
        a = (line[i]["x"], line[i]["y"])
        b = (line[i + 1]["x"], line[i + 1]["y"])
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        total += math.sqrt(dx * dx + dy * dy)
    return total


def _expand_seeds_for_coverage(site_width, site_height, seed_points, min_seeds=6):
    """
    Keep original seeds. If there are too few, add extra coverage seeds
    instead of replacing the originals.
    """
    seeds = list(seed_points) if seed_points else []

    if len(seeds) >= min_seeds:
        return seeds

    margin = 0.12
    n = 3
    extra = []

    for i in range(n):
        for j in range(n):
            tx = (i + 1) / (n + 1)
            ty = (j + 1) / (n + 1)
            x = margin * site_width + (1.0 - 2.0 * margin) * site_width * tx
            y = margin * site_height + (1.0 - 2.0 * margin) * site_height * ty
            extra.append((x, y))

    merged = seeds + extra

    # simple dedupe: avoid adding points that are almost the same
    out = []
    min_dist2 = 25.0  # 5 px radius
    for p in merged:
        px, py = p
        too_close = False
        for qx, qy in out:
            dx = px - qx
            dy = py - qy
            if dx * dx + dy * dy < min_dist2:
                too_close = True
                break
        if not too_close:
            out.append((px, py))

    return out


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
    major_d_sep=65,
    minor_d_sep=35,
    step_size=2.0,
    max_steps=700,
    max_length=None,
    bounds=None,
    angle_threshold=0.3,
    use_euler=False,
):
    """
    论文 6.1 交替追踪：主→副→主→副...，减少悬空边。
    major 与 minor 使用不同 d_sep：major 更疏，minor 更密。
    沿 major line 用 major_d_sep 添加种子，沿 minor line 用 minor_d_sep 添加种子。
    Returns: (major_lines, minor_lines)
    """
    def _trace_one(x0, y0, use_major, existing, d_sep):
        pts = integrate_hyperstreamline(
            tensor_fn, x0, y0,
            use_major=use_major,
            bidirectional=True,
            step_size=step_size,
            max_steps=max_steps,
            max_length=max_length,
            bounds=bounds,
            angle_threshold=angle_threshold,
            use_euler=use_euler,
            existing_lines=existing,
            d_sep=d_sep,
        )
        return pts

    major_lines = []
    minor_lines = []
    used_seeds = set()

    def _seed_key(x, y):
        return (round(x / 2), round(y / 2))

    queue = [(x, y, True) for x, y in seed_points]
    max_total = 110  # 限制总超流线数量，避免卡死
    min_line_len = max(12, step_size * 4)
    while queue and (len(major_lines) + len(minor_lines)) < max_total:
        x0, y0, do_major = queue.pop(0)
        key = _seed_key(x0, y0)
        if key in used_seeds:
            continue
        used_seeds.add(key)

        d_sep = major_d_sep if do_major else minor_d_sep
        existing = major_lines if do_major else minor_lines
        line = _trace_one(x0, y0, do_major, existing, d_sep)
        if len(line) < 2:
            continue
        if _polyline_length(line) < min_line_len:
            continue

        if do_major:
            major_lines.append(line)
        else:
            minor_lines.append(line)

        # 沿超流线添加种子：major 用 major_d_sep，minor 用 minor_d_sep
        seed_spacing = max(10.0, d_sep * 0.85)
        total = 0
        next_seed_dist = seed_spacing
        for i in range(len(line) - 1):
            dx = line[i + 1]["x"] - line[i]["x"]
            dy = line[i + 1]["y"] - line[i]["y"]
            seg_len = math.sqrt(dx * dx + dy * dy)
            while total + seg_len >= next_seed_dist:
                t = (next_seed_dist - total) / seg_len if seg_len > 0 else 0
                nx = line[i]["x"] + t * dx
                ny = line[i]["y"] + t * dy
                if len(queue) <= 300:
                    queue.append((nx, ny, not do_major))
                next_seed_dist += seed_spacing
            total += seg_len

    return major_lines, minor_lines


def _find_nearest_idx(pt, vertices, tol=5):
    """找最近顶点索引，用平方距离"""
    best = -1
    best_d2 = tol * tol
    ptx, pty = pt[0], pt[1]
    for i, v in enumerate(vertices):
        dx, dy = ptx - v[0], pty - v[1]
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_d2 = d2
            best = i
    return best


def project_point_onto_polyline_segment(pt, line):
    """
    将点 pt 投影到折线 line 的最近线段上。
    返回 (segment_index, t_param, projected_x, projected_y) 或 None。
    t_param: 沿该线段的参数 [0,1]，0=起点，1=终点
    """
    if len(line) < 2:
        return None
    best_seg = -1
    best_t = 0.0
    best_pt = None
    best_d2 = float("inf")
    px, py = pt[0], pt[1]
    for i in range(len(line) - 1):
        a = (line[i]["x"], line[i]["y"])
        b = (line[i + 1]["x"], line[i + 1]["y"])
        ax, ay = a[0], a[1]
        bx, by = b[0], b[1]
        dx, dy = bx - ax, by - ay
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 1e-20:
            t = 0.0
            proj = a
        else:
            t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
            t = max(0, min(1, t))
            proj = (ax + t * dx, ay + t * dy)
        d2 = (px - proj[0]) ** 2 + (py - proj[1]) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_seg = i
            best_t = t
            best_pt = proj
    if best_pt is None:
        return None
    return (best_seg, best_t, best_pt[0], best_pt[1])


def split_polyline_at_intersections(line, intersection_points, tol=1e-6):
    """
    在折线的交点处切分折线。
    对每个 intersection，投影到折线上得到插入位置。
    返回: [(pts, start_node, end_node), ...]
    每个元素是一条切分后的段（完整路径点列表）及其起止节点坐标。
    """
    if len(line) < 2:
        return []
    line_pts = [(p["x"], p["y"]) for p in line]
    inserts = []
    for pt in intersection_points:
        proj = project_point_onto_polyline_segment(pt, line)
        if proj is None:
            continue
        seg_idx, t_param, px, py = proj
        inserts.append((seg_idx, t_param, (px, py)))
    inserts.sort(key=lambda x: (x[0], x[1]))
    seen = set()
    unique_inserts = []
    for seg_idx, t_param, pt in inserts:
        key = (round(pt[0] / tol) * tol, round(pt[1] / tol) * tol)
        if key not in seen:
            seen.add(key)
            unique_inserts.append((seg_idx, t_param, pt))
    if not unique_inserts:
        return [([line_pts[0], line_pts[-1]], line_pts[0], line_pts[-1])]
    segments = []
    cur_seg_idx = 0
    cur_pt = line_pts[0]
    for seg_idx, t_param, ins_pt in unique_inserts:
        seg_pts = [cur_pt]
        for i in range(cur_seg_idx, seg_idx):
            seg_pts.append(line_pts[i + 1])
        seg_pts.append(ins_pt)
        segments.append((seg_pts, cur_pt, ins_pt))
        cur_pt = ins_pt
        cur_seg_idx = seg_idx
    seg_pts = [cur_pt]
    for i in range(cur_seg_idx, len(line_pts) - 1):
        seg_pts.append(line_pts[i + 1])
    segments.append((seg_pts, cur_pt, line_pts[-1]))
    return segments


def cluster_points(points, tol=2.0):
    """
    合并距离小于 tol 的点，返回去重后的点列表。
    每个簇用其质心表示。
    """
    if not points:
        return []
    tol_sq = tol * tol
    n = len(points)
    parent = list(range(n))

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(a, b):
        pa, pb = find(a), find(b)
        if pa != pb:
            parent[pa] = pb

    for i in range(n):
        for j in range(i + 1, n):
            dx = points[i][0] - points[j][0]
            dy = points[i][1] - points[j][1]
            if dx * dx + dy * dy < tol_sq:
                union(i, j)

    clusters = {}
    for i in range(n):
        r = find(i)
        if r not in clusters:
            clusters[r] = []
        clusters[r].append(points[i])

    out = []
    for pts in clusters.values():
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        out.append((cx, cy))
    return out


def hyperstreamlines_to_street_graph(
    major_lines,
    minor_lines,
    bounds=None,
):
    """
    从主/副超流线构建街道图 G=(V,E)。
    节点仅来自：交点 + 切分后的真实端点。
    边仅来自：相邻节点之间的长段（intersection-to-intersection 或 endpoint-to-intersection）。
    Returns: {"vertices": [(x,y),...], "edges": [(i,j),...], "edge_pts": [[(x,y),...],...]}
    """
    if bounds:
        xmin, ymin, xmax, ymax = bounds
    else:
        xmin = ymin = 0
        xmax = ymax = 1e9

    major_segs = _lines_to_segments_cache(major_lines)
    minor_segs = _lines_to_segments_cache(minor_lines)
    intersections = []
    for pt in _find_intersections(major_segs, minor_segs):
        if xmin <= pt[0] <= xmax and ymin <= pt[1] <= ymax:
            intersections.append(pt)

    all_nodes = list(intersections)
    all_segments = []

    for line in major_lines + minor_lines:
        if len(line) < 2:
            continue
        segs = split_polyline_at_intersections(line, intersections)
        for pts, start_node, end_node in segs:
            if len(pts) < 2:
                continue
            all_nodes.append(start_node)
            all_nodes.append(end_node)
            all_segments.append((pts, start_node, end_node))

    vertices = cluster_points(all_nodes, tol=3.0)
    if not vertices:
        return {"vertices": [], "edges": [], "edge_pts": []}

    edges = []
    edge_pts = []
    for pts, start_node, end_node in all_segments:
        ia = _find_nearest_idx(start_node, vertices, 8)
        ib = _find_nearest_idx(end_node, vertices, 8)
        if ia >= 0 and ib >= 0 and ia != ib:
            dx = end_node[0] - start_node[0]
            dy = end_node[1] - start_node[1]
            if dx * dx + dy * dy > 4:
                edges.append((ia, ib))
                edge_pts.append(pts)

    return {"vertices": vertices, "edges": edges, "edge_pts": edge_pts}


def generate_streets_from_hyperstreamlines(
    tensor_fn,
    site_width,
    site_height,
    seed_points=None,
    major_d_sep=60,
    minor_d_sep=14,
    step_size=2.0,
    max_length=None,
    angle_threshold=0.3,
    use_euler=False,
):
    """
    论文式街道生成：超流线交替追踪 → 交点图。
    major_d_sep 与 minor_d_sep 分离：minor 更密，生成更多 minor 线。
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
        major_d_sep=major_d_sep,
        minor_d_sep=minor_d_sep,
        step_size=step_size,
        max_length=max_length,
        bounds=bounds,
        angle_threshold=angle_threshold,
        use_euler=use_euler,
    )

    # 步骤2：根据 major/minor 交点构建 street graph
    graph = hyperstreamlines_to_street_graph(major_lines, minor_lines, bounds=bounds)

    cx = site_width / 2
    cy = site_height / 2
    return graph, [cx], [cy]


def partition_by_major_roads(major_lines, site_width, site_height):
    """
    论文 6.2：主路将区域划分成子区域，用于次路生成。
    取最长的 2~4 条 major lines，按其空间分布生成若干 bbox region。
    major_lines: 主超流线列表
    Returns: list of (polygon, center) 每个子区域的 bbox 多边形和中心
    """
    if not major_lines:
        return [([(0, 0), (site_width, 0), (site_width, site_height), (0, site_height)],
                 (site_width / 2, site_height / 2))]
    sorted_lines = sorted(major_lines, key=lambda ln: sum(
        math.sqrt((ln[i+1]["x"]-ln[i]["x"])**2 + (ln[i+1]["y"]-ln[i]["y"])**2)
        for i in range(len(ln)-1)), reverse=True)
    n = min(4, max(2, len(sorted_lines)))
    top_lines = sorted_lines[:n]
    centroids = []
    for ln in top_lines:
        cx = sum(p["x"] for p in ln) / len(ln)
        cy = sum(p["y"] for p in ln) / len(ln)
        centroids.append((cx, cy))
    dominant_x = site_width >= site_height
    sort_coord = 0 if dominant_x else 1
    site_dim = site_width if dominant_x else site_height
    ordered = sorted(range(len(centroids)), key=lambda i: centroids[i][sort_coord])
    boundaries = [0.0]
    for i in ordered:
        boundaries.append(centroids[i][sort_coord])
    boundaries.append(float(site_dim))
    boundaries = sorted(set(boundaries))
    regions = []
    for i in range(len(boundaries) - 1):
        lo, hi = boundaries[i], boundaries[i + 1]
        if hi - lo < 20:
            continue
        mid = (lo + hi) / 2
        if dominant_x:
            xmin, xmax = lo, hi
            ymin, ymax = 0, site_height
        else:
            xmin, xmax = 0, site_width
            ymin, ymax = lo, hi
        poly = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
        center = ((xmin + xmax) / 2, (ymin + ymax) / 2)
        regions.append((poly, center))
    if not regions:
        return [([(0, 0), (site_width, 0), (site_width, site_height), (0, site_height)],
                 (site_width / 2, site_height / 2))]
    return regions


def _trace_minor_lines_in_region(
    tensor_fn,
    region_bbox,
    d_sep,
    step_size,
    angle_threshold,
    use_euler=False,
    max_steps=700,
    max_length=None,
):
    """
    在 region bbox 内仅追踪 minor 超流线。
    region_bbox: (xmin, ymin, xmax, ymax)
    每步若跑出 bbox 则停止（由 integrate_hyperstreamline bounds 实现）。
    Returns: list of minor lines
    """
    xmin, ymin, xmax, ymax = region_bbox
    w, h = xmax - xmin, ymax - ymin
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2
    seeds = _expand_seeds_for_coverage(w, h, [(cx, cy)], min_seeds=4)
    seeds = [(xmin + x, ymin + y) for x, y in seeds]
    seeds = [(x, y) for x, y in seeds if xmin <= x <= xmax and ymin <= y <= ymax]
    if not seeds:
        seeds = [(cx, cy)]
    bounds = region_bbox
    minor_lines = []
    used_seeds = set()

    def _seed_key(x, y):
        return (round(x / 2), round(y / 2))

    queue = [(x, y) for x, y in seeds]
    max_total = 55
    min_line_len = max(12, step_size * 4)
    while queue and len(minor_lines) < max_total:
        x0, y0 = queue.pop(0)
        key = _seed_key(x0, y0)
        if key in used_seeds:
            continue
        used_seeds.add(key)
        if not (xmin <= x0 <= xmax and ymin <= y0 <= ymax):
            continue
        pts = integrate_hyperstreamline(
            tensor_fn, x0, y0,
            use_major=False,
            bidirectional=True,
            step_size=step_size,
            max_steps=max_steps,
            max_length=max_length,
            bounds=bounds,
            angle_threshold=angle_threshold,
            use_euler=use_euler,
            existing_lines=minor_lines,
            d_sep=d_sep,
        )
        if len(pts) < 2:
            continue
        if _polyline_length(pts) < min_line_len:
            continue
        minor_lines.append(pts)
        seed_spacing = max(10.0, d_sep * 0.85)
        total = 0
        next_seed_dist = seed_spacing
        for i in range(len(pts) - 1):
            dx = pts[i + 1]["x"] - pts[i]["x"]
            dy = pts[i + 1]["y"] - pts[i]["y"]
            seg_len = math.sqrt(dx * dx + dy * dy)
            while total + seg_len >= next_seed_dist:
                t = (next_seed_dist - total) / seg_len if seg_len > 0 else 0
                nx = pts[i]["x"] + t * dx
                ny = pts[i]["y"] + t * dy
                if xmin <= nx <= xmax and ymin <= ny <= ymax and len(queue) <= 300:
                    queue.append((nx, ny))
                next_seed_dist += seed_spacing
            total += seg_len
    return minor_lines


def generate_minor_roads_in_region(
    tensor_fn,
    region_polygon,
    region_center,
    d_sep=45,
    step_size=2.0,
    max_length=None,
    bounds=None,
    angle_threshold=0.3,
):
    """
    在子区域内生成次路。仅追踪 minor 超流线，seeds 在 region 内，tracing 出 bbox 即停。
    """
    if not region_polygon or len(region_polygon) < 3:
        return []
    xs = [p[0] for p in region_polygon]
    ys = [p[1] for p in region_polygon]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    region_bbox = (xmin, ymin, xmax, ymax)
    return _trace_minor_lines_in_region(
        tensor_fn,
        region_bbox,
        d_sep=d_sep,
        step_size=step_size,
        max_length=max_length,
        angle_threshold=angle_threshold,
    )


def two_stage_street_generation(
    tensor_fn,
    site_width,
    site_height,
    seed_points=None,
    major_d_sep=65,
    minor_d_sep=35,
    step_size=2.0,
    max_length=None,
    angle_threshold=0.3,
    use_euler=False,
):
    """
    论文 6.1+6.2 二阶段：主路 → 分区 → 次路。
    步骤1：追踪 major_lines
    步骤2：partition_by_major_roads 得到若干 bbox region
    步骤3：对每个 region 单独生成 minor_lines（seeds 在 region 内，tracing 出 bbox 即停）
    步骤4：合并 major + all region minor，构建 street graph
    Returns: (graph, xs, ys) 其中 graph = {"vertices", "edges", "edge_pts"}
    """
    bounds = (0, 0, site_width, site_height)
    if not seed_points:
        seed_points = [(site_width / 2, site_height / 2)]
    seed_points = _expand_seeds_for_coverage(site_width, site_height, seed_points)

    # 步骤1：追踪主路
    major_lines, _ = interleaved_hyperstreamlines(
        tensor_fn, seed_points,
        major_d_sep=major_d_sep,
        minor_d_sep=minor_d_sep,
        step_size=step_size,
        max_length=max_length,
        bounds=bounds,
        angle_threshold=angle_threshold,
        use_euler=use_euler,
    )

    # 步骤2：分区
    regions = partition_by_major_roads(major_lines, site_width, site_height)

    # 步骤3：每个 region 单独生成 minor
    minor_lines = []
    for poly, center in regions:
        lines = generate_minor_roads_in_region(
            tensor_fn, poly, center,
            d_sep=minor_d_sep,
            step_size=step_size,
            max_length=max_length,
            bounds=bounds,
            angle_threshold=angle_threshold,
        )
        minor_lines.extend(lines)

    # 步骤4：合并 major + minor，构建 graph
    graph = hyperstreamlines_to_street_graph(major_lines, minor_lines, bounds=bounds)

    return graph, [site_width / 2], [site_height / 2]
