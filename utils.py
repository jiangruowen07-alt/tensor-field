"""
通用工具函数
"""

import math

# Perlin 噪声置换表
_PERM = list(range(256))
_random = __import__("random")
_random.Random(42).shuffle(_PERM)
_PERM = _PERM * 2


# 预计算梯度表，避免列表索引
_GRAD = ((1, 1), (-1, 1), (1, -1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1))


def _grad2(h, x, y):
    """2D 梯度向量与 (x,y) 的点积"""
    g = _GRAD[h & 7]
    return g[0] * x + g[1] * y


def perlin_noise(x, y, scale=0.01, seed=0):
    """
    Perlin 噪声标量场，返回值约 [-1, 1]。
    论文 5.3：用于旋转场 R1/R2/R3，产生有机街道模式。
    scale: 空间尺度，越小变化越平滑
    """
    x, y = x * scale, y * scale
    xi = int(x) & 255
    yi = int(y) & 255
    xf = x - int(x)
    yf = y - int(y)
    # 平滑步函数 f(t)=t*t*(3-2*t)，内联展开
    u = xf * xf * (3.0 - 2.0 * xf)
    v = yf * yf * (3.0 - 2.0 * yf)
    s = seed & 255
    p = _PERM
    aa = p[p[xi + s] + yi] & 7
    ab = p[p[xi + s] + yi + 1] & 7
    ba = p[p[xi + 1 + s] + yi] & 7
    bb = p[p[xi + 1 + s] + yi + 1] & 7
    v1 = _grad2(aa, xf, yf) + u * (_grad2(ba, xf - 1, yf) - _grad2(aa, xf, yf))
    v2 = _grad2(ab, xf, yf - 1) + u * (_grad2(bb, xf - 1, yf - 1) - _grad2(ab, xf, yf - 1))
    return (v1 + v * (v2 - v1)) * 0.5


def lerp(a, b, t):
    """线性插值"""
    return a + (b - a) * t


def safe_float(val, default):
    """安全转换为 float"""
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


def safe_int(val, default):
    """安全转换为 int"""
    try:
        return int(float(val)) if val else default
    except (ValueError, TypeError):
        return default
