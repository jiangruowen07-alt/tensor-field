"""
地块划分：frontage-based、block-by-block、转角地块、不规则扰动
- 基于临街面划分
- 按 block 逐块切分
- 转角地块单独处理
- 最小面积、最小面宽、最大进深控制
"""

import math
import random

from config import T_COUNT, T_STEP


def polygon_area(pts):
    """多边形面积（Shoelace）"""
    if len(pts) < 3:
        return 0.0
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def segment_length(p0, p1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    return math.sqrt(dx * dx + dy * dy)


def polygon_frontage(pts):
    """临街面（四边形取较短的两条对边中较短者，作为典型面宽）"""
    if len(pts) < 4:
        return segment_length(pts[0], pts[-1]) if len(pts) >= 2 else 0.0
    # 四边形：边0-1, 1-2, 2-3, 3-0
    e0 = segment_length(pts[0], pts[1])
    e1 = segment_length(pts[1], pts[2])
    e2 = segment_length(pts[2], pts[3])
    e3 = segment_length(pts[3], pts[0])
    # 前边(0-1)与后边(2-3)为一对，左边(3-0)与右边(1-2)为另一对
    front_back = min(e0, e2)  # 临街面通常较短
    left_right = min(e1, e3)
    return min(front_back, left_right)


def polygon_depth(pts):
    """进深（与面宽垂直方向的平均尺寸）"""
    if len(pts) < 4:
        return 0.0
    area = polygon_area(pts)
    frontage = polygon_frontage(pts)
    if frontage < 1e-10:
        return 0.0
    return area / frontage


def lerp_point(p0, p1, t):
    return (
        p0[0] + t * (p1[0] - p0[0]),
        p0[1] + t * (p1[1] - p0[1]),
    )


def get_block_corners(line_a, line_b, t_start, t_end):
    """获取 block 四角：line_a 在 t_start, t_end，line_b 在 t_start, t_end"""
    idx_s = 0 if t_start <= 0 else min(int(t_start / T_STEP) + 1, T_COUNT - 1)
    idx_e = 0 if t_end <= 0 else min(int(t_end / T_STEP) + 1, T_COUNT - 1)
    idx_s = min(idx_s, len(line_a) - 1, len(line_b) - 1)
    idx_e = min(idx_e, len(line_a) - 1, len(line_b) - 1)
    p1 = (line_a[idx_s]["x"], line_a[idx_s]["y"])
    p2 = (line_b[idx_s]["x"], line_b[idx_s]["y"])
    p3 = (line_b[idx_e]["x"], line_b[idx_e]["y"])
    p4 = (line_a[idx_e]["x"], line_a[idx_e]["y"])
    return [p1, p2, p3, p4]


def subdivide_block_frontage_based(
    corners,
    min_frontage,
    max_frontage,
):
    """
    前边(p1-p2)为临街面，沿该面切分。
    返回子地块列表，每个为 [(x,y),...]
    """
    p1, p2, p3, p4 = corners
    frontage_len = segment_length(p1, p2)
    if frontage_len < 1e-10:
        return [corners] if polygon_area(corners) > 1e-12 else []

    # 按 max_frontage 切分，确保每块面宽在 min_frontage ~ max_frontage
    target = max(min_frontage, (min_frontage + max_frontage) / 2)
    n = max(1, min(50, int(math.ceil(frontage_len / max(target, 1)))))

    parcels = []
    for i in range(n):
        t0 = i / n
        t1 = (i + 1) / n
        a = lerp_point(p1, p2, t0)
        b = lerp_point(p1, p2, t1)
        c = lerp_point(p4, p3, t1)
        d = lerp_point(p4, p3, t0)
        parcel_pts = [a, b, c, d]
        if polygon_area(parcel_pts) > 1e-12:
            parcels.append(parcel_pts)
    return parcels


def is_corner_block(t_start, t_end, t_positions):
    """是否为转角 block（在 t=0 或 t=1 附近）"""
    tol = 0.05
    return t_start < tol or t_end > (1 - tol)


def subdivide_corner_block(corners, min_frontage, max_frontage):
    """
    转角 block：L 形或三角形，可切为 1~2 个地块
    简化：转角处保持单块，或按最小面宽切分
    """
    area = polygon_area(corners)
    if area < 1e-12:
        return []
    frontage = polygon_frontage(corners)
    if frontage < min_frontage:
        return [corners]  # 太小不切
    return subdivide_block_frontage_based(corners, min_frontage, max_frontage)


def apply_perturbation(pts, strength=0.02, seed=None):
    """对顶点施加不规则扰动"""
    if strength <= 0 or len(pts) < 3:
        return pts
    rng = random.Random(seed)
    result = []
    for i, (x, y) in enumerate(pts):
        dx = (rng.random() - 0.5) * 2 * strength
        dy = (rng.random() - 0.5) * 2 * strength
        result.append((x + dx, y + dy))
    return result


def filter_parcels_by_constraints(
    parcels,
    min_area=0,
    min_frontage=0,
    max_depth=1e9,
):
    """按最小面积、最小面宽、最大进深过滤（一次计算 area/frontage 复用）"""
    if not min_area and not min_frontage and max_depth >= 1e8:
        return parcels
    result = []
    for p in parcels:
        area = polygon_area(p)
        if area < min_area:
            continue
        frontage = polygon_frontage(p)
        if frontage < min_frontage:
            continue
        depth = area / frontage if frontage > 1e-10 else 0
        if depth <= max_depth:
            result.append(p)
    return result


def subdivide_blocks(
    sorted_lines,
    t_positions,
    min_frontage=15,
    max_frontage=45,
    min_area=50,
    max_depth=1e9,
    use_frontage_based=True,
    use_block_by_block=True,
    corner_parcels_separate=True,
    perturbation_strength=0,
    seed=None,
):
    """
    主入口：按 block 划分地块，支持 frontage-based、转角、扰动、约束。
    """
    parcels = []
    rng = random.Random(seed)

    for i in range(len(sorted_lines) - 1):
        line_a = sorted_lines[i]
        line_b = sorted_lines[i + 1]

        for j in range(len(t_positions) - 1):
            t_start = t_positions[j]
            t_end = t_positions[j + 1]

            corners = get_block_corners(line_a, line_b, t_start, t_end)
            if polygon_area(corners) < 1e-12:
                continue

            is_corner = is_corner_block(t_start, t_end, t_positions)

            if corner_parcels_separate and is_corner:
                block_parcels = subdivide_corner_block(
                    corners, min_frontage, max_frontage
                )
            elif use_frontage_based:
                block_parcels = subdivide_block_frontage_based(
                    corners, min_frontage, max_frontage
                )
            else:
                # 规则切片（fallback）
                block_parcels = [corners]

            for p in block_parcels:
                if perturbation_strength > 0:
                    p = apply_perturbation(
                        p, perturbation_strength, seed=rng.random()
                    )
                parcels.append(p)

    return filter_parcels_by_constraints(
        parcels, min_area=min_area, min_frontage=min_frontage, max_depth=max_depth
    )


def rule_based_parcels(sorted_lines, segments=15):
    """
    原有规则切片逻辑（兼容旧行为）
    """
    parcels = []
    for i in range(len(sorted_lines) - 1):
        line_a = sorted_lines[i]
        line_b = sorted_lines[i + 1]
        for seg in range(segments):
            t_start = seg / segments
            t_end = (seg + 0.8) / segments
            idx_s = 0 if t_start <= 0 else min(int(t_start / T_STEP) + 1, T_COUNT - 1)
            idx_e = 0 if t_end <= 0 else min(int(t_end / T_STEP) + 1, T_COUNT - 1)
            p1 = line_a[idx_s]
            p2 = line_b[idx_s]
            p3 = line_b[idx_e]
            p4 = line_a[idx_e]
            parcel_pts = [
                (p1["x"], p1["y"]),
                (p2["x"], p2["y"]),
                (p3["x"], p3["y"]),
                (p4["x"], p4["y"]),
            ]
            parcels.append(parcel_pts)
    return parcels
