"""
Height Field - 从灰度高程图生成张量场
输入灰度高程图 -> 求梯度 -> 生成 tensor basis (u=等高线方向, v=梯度方向)
"""

import math

# 尝试导入 PIL，用于 PNG/JPG；无则仅支持 GIF (PhotoImage)
try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


def _normalize(ux, uy):
    L = math.sqrt(ux * ux + uy * uy) or 1e-10
    return ux / L, uy / L


def _orthogonal(ux, uy):
    return _normalize(-uy, ux)


def _photoimage_to_grid(photo_image, site_width, site_height):
    """从 tkinter PhotoImage 提取灰度高程网格。支持 GIF。"""
    try:
        w, h = photo_image.width(), photo_image.height()
    except Exception:
        return None, 0, 0
    if w < 2 or h < 2:
        return None, 0, 0
    grid = []
    for py in range(h):
        row = []
        for px in range(w):
            try:
                rgb = photo_image.get(px, py)
            except Exception:
                row.append(0)
                continue
            if isinstance(rgb, str):
                rgb = (int(rgb[1:3], 16), int(rgb[3:5], 16), int(rgb[5:7], 16))
            elif isinstance(rgb, (list, tuple)) and len(rgb) >= 3:
                rgb = tuple(rgb[:3])
            else:
                row.append(0)
                continue
            bright = sum(rgb) / 3
            row.append(bright)
        grid.append(row)
    return grid, w, h


def _pil_to_grid(pil_image, site_width, site_height):
    """从 PIL Image 提取灰度高程网格。"""
    if pil_image is None:
        return None, 0, 0
    gray = pil_image.convert("L")
    w, h = gray.size
    if w < 2 or h < 2:
        return None, 0, 0
    grid = []
    px_data = gray.load()
    for py in range(h):
        row = []
        for px in range(w):
            row.append(float(px_data[px, py]))
        grid.append(row)
    return grid, w, h


def build_height_field_from_image(image, site_width, site_height, use_pil=True):
    """
    从图像构建高度场。
    image: tkinter.PhotoImage (GIF) 或 PIL.Image (PNG/JPG)
    Returns: (height_at, gradient_at) 或 (None, None) 若失败
    """
    grid = None
    img_w, img_h = 0, 0

    if use_pil and _HAS_PIL and hasattr(image, "size"):
        # PIL Image
        grid, img_w, img_h = _pil_to_grid(image, site_width, site_height)
    elif hasattr(image, "width") and hasattr(image, "get"):
        # tkinter PhotoImage
        grid, img_w, img_h = _photoimage_to_grid(image, site_width, site_height)
    else:
        return None, None

    if grid is None or img_w < 2 or img_h < 2:
        return None, None

    scale_x = (img_w - 1) / max(site_width, 1)
    scale_y = (img_h - 1) / max(site_height, 1)

    def _px_py(x, y):
        px = max(0, min(img_w - 1, x * scale_x))
        py = max(0, min(img_h - 1, y * scale_y))
        return int(px), int(py)

    def height_at(x, y):
        px, py = _px_py(x, y)
        return grid[py][px]

    def gradient_at(x, y):
        """中心差分求梯度 (gx, gy)。梯度指向高程增加方向。"""
        px, py = _px_py(x, y)
        # 边界用单边差分
        if px <= 0:
            gx = grid[py][min(1, img_w - 1)] - grid[py][0]
        elif px >= img_w - 1:
            gx = grid[py][img_w - 1] - grid[py][max(0, img_w - 2)]
        else:
            gx = (grid[py][px + 1] - grid[py][px - 1]) / 2.0

        if py <= 0:
            gy = grid[min(1, img_h - 1)][px] - grid[0][px]
        elif py >= img_h - 1:
            gy = grid[img_h - 1][px] - grid[max(0, img_h - 2)][px]
        else:
            gy = (grid[py + 1][px] - grid[py - 1][px]) / 2.0

        # 图像 y 向下，逻辑 y 向上，取反
        return (gx, -gy)

    return height_at, gradient_at


def height_tensor_at(x, y, gradient_at_fn):
    """
    在 (x,y) 处根据梯度生成张量基底。
    u = 等高线方向（垂直于梯度）
    v = 梯度方向（上坡）
    Returns: (ux, uy, vx, vy) 或 None（平坦区回退到 grid）
    """
    gx, gy = gradient_at_fn(x, y)
    L = math.sqrt(gx * gx + gy * gy)
    if L < 1e-6:
        return None  # 平坦区
    # u = 等高线方向 = 垂直于梯度（逆时针旋转90°）
    ux, uy = _normalize(-gy, gx)
    vx, vy = _orthogonal(ux, uy)  # v = 梯度方向
    return ux, uy, vx, vy
