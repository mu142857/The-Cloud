#!/usr/bin/env python3
"""终章尾声最后一段「回家的列车」home_train 的图（art/home_train/）。

剧本（data/story_final.json epi_home*，剧情姐 10-30 改的）：母星那班熟悉的车，下午的太阳照进这节车厢、落在靠窗的空座位上，
窗外那排树一棵棵往后退。prop：train_window（afternoon_sun → trees_passing）、train_seat（sun_on_knees）。
前一段是作者的雨夜城市（art/city），这里接着：同一座灰色鸽子笼城市，雨停了，第二天下午。

画法：
- 一屏 480×270，正侧面、无透视。车厢是一张剖面（近侧那面墙切掉）：中间一条是车厢里面，上面露出车顶、受电弓、接触网，
  再上面是窗外的城市和天空；下面是转向架、钢轨、高架桥面。窗外的东西（天空、远处的城、田野、楼、树、电线杆、桥面）
  全是单独的层，scripts/home_train.gd 让它们往左平移（车往右开），换状态时城市走完、树从右边进来。
- 太阳在左上、楼后面（逆光）：楼和树都是暗的剪影，只有朝太阳那一侧一道暖边；乘客也是逆光的剪影。
  阳光从远侧的窗斜着落进来（往右下），照在座位、地板和晨身上：晨是画面里对比最高的东西。
- 兜帽乘客：低头看手机，谁也不看谁（冷漠，不是焦虑）。一个靠着窗睡着，一个抱着湿伞——昨晚的雨。
- 纹理（地板的磨痕、楼的阳台、窗洞）最多暗一档、零星出现；没有虚线点线；细线都连着实物。

出图：art/home_train/*.png + occlusion.json（光束被楼 / 树挡住的程度，给 home_train.gd 用）。
--preview 目录：拼三张 2 倍预览（下午城市、出城以后的树，晨站在空座位前；晨在门口、空座位晒着太阳）。

跑：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/home_train_art.py --preview <目录>
  之后 gt.sh 120 LOG --headless --import（--import 前面不加 --）
"""
import json
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "home_train")
W, H = 480, 270
TW = 960                      # 窗外层的图宽（左右无缝）

# ------------------------------------------------------------------ 车厢的尺寸（room.json、home_train.gd 都按这些）
ROOF = 122                    # 车顶最上面一行
CEIL = 138                    # 车厢顶棚
RAIL_Y = 147                  # 扶手杆
WIN_T, WIN_B = 158, 199       # 窗框上下
GLASS_T, GLASS_B = 160, 197   # 玻璃
FLOOR = 228                   # 晨的脚底（地面）
BAY0, BAY = 92, 64            # 第一扇窗的左边、一个座位间距
NBAY = 6
EMPTY_BAY = 3                 # 有太阳的那个空座位
DOOR = (28, 74)
DOOR_GLASS = [(33, 47), (55, 69)]
POLE_X = 80
WIRE_Y = 99                   # 接触网
SUN = (96, 54)
SUN_DX = 0.5                  # 阳光往下走 1 像素、往右走多少（从左上斜着照进来）
TRAIN_SEAT_X = 96 + BAY * EMPTY_BAY + 17      # 305
TRAIN_DOOR_X = 52


def hx(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def new(w=W, h=H):
    return np.zeros((h, w, 4), np.uint8)


def pmask(pts, w=W, h=H):
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).polygon([(float(x), float(y)) for x, y in pts], fill=255)
    return np.array(im) > 0


def rect(a, x0, y0, x1, y1, c):
    """包含两端"""
    hh, ww = a.shape[:2]
    x0, y0 = max(int(x0), 0), max(int(y0), 0)
    x1, y1 = min(int(x1), ww - 1), min(int(y1), hh - 1)
    if x1 >= x0 and y1 >= y0:
        a[y0:y1 + 1, x0:x1 + 1] = hx(c) if isinstance(c, str) else c


def put(a, x, y, c):
    hh, ww = a.shape[:2]
    if 0 <= x < ww and 0 <= y < hh:
        a[int(y), int(x)] = hx(c) if isinstance(c, str) else c


def line_pts(x0, y0, x1, y1):
    pts = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
    return pts


def line(a, x0, y0, x1, y1, c):
    for x, y in line_pts(x0, y0, x1, y1):
        put(a, x, y, c)


def fill(a, m, c):
    a[m] = hx(c) if isinstance(c, str) else c


def disc(cx, cy, r, w=W, h=H):
    yy, xx = np.mgrid[0:h, 0:w]
    return (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r + r * 0.6


def over(dst, src, x=0, y=0):
    """src 盖到 dst 上（不透明像素直接盖；半透明按 alpha 混）"""
    hh, ww = src.shape[:2]
    H2, W2 = dst.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + ww, W2), min(y + hh, H2)
    if x1 <= x0 or y1 <= y0:
        return dst
    s = src[y0 - y:y1 - y, x0 - x:x1 - x].astype(float)
    d = dst[y0:y1, x0:x1].astype(float)
    sa = s[..., 3:4] / 255.0
    da = d[..., 3:4] / 255.0
    oa = sa + da * (1 - sa)
    rgb = (s[..., :3] * sa + d[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6)
    dst[y0:y1, x0:x1, :3] = np.clip(rgb + 0.5, 0, 255).astype(np.uint8)
    dst[y0:y1, x0:x1, 3] = np.clip(oa[..., 0] * 255 + 0.5, 0, 255).astype(np.uint8)
    return dst


def add_light(dst, src, x=0, y=0):
    """加法混合（光束、膝上的太阳）：src 的颜色 × alpha 加到 dst 上"""
    hh, ww = src.shape[:2]
    s = src.astype(float)
    d = dst[y:y + hh, x:x + ww].astype(float)
    d[..., :3] += s[..., :3] * (s[..., 3:4] / 255.0)
    dst[y:y + hh, x:x + ww, :3] = np.clip(d[..., :3] + 0.5, 0, 255).astype(np.uint8)
    return dst


def wrap_rect(a, x0, y0, x1, y1, c, tw=TW):
    """左右无缝的层：跨过右边界的部分绕回左边"""
    for k in (-tw, 0, tw):
        rect(a, x0 + k, y0, x1 + k, y1, c)


def wrap_put(a, x, y, c, tw=TW):
    put(a, x % tw, y, c)


# ================================================================== 天空（不动）
SKY_BANDS = [(0, "4f5452"), (24, "555a57"), (46, "5c605c"), (66, "636660"), (86, "6b6c65"),
             (104, "74736a"), (122, "7c796e"), (142, "847f72"), (160, "8a8475")]   # 越往下越暖一点（下午）


def sky_band_color(y, x):
    """雾霾天的下午：一条条平的色带，边界是很缓的波（一格一格的台阶）"""
    c = SKY_BANDS[0][1]
    for i, (y0, col) in enumerate(SKY_BANDS):
        wob = round(1.4 * math.sin(x / 61.0 + i * 1.7) + 0.8 * math.sin(x / 23.0 + i))
        if y >= y0 + (wob if i > 0 else 0):
            c = col
    return c


def lighten(c, d):
    r, g, b, a = hx(c) if isinstance(c, str) else c
    return (min(r + d, 255), min(g + d - 1, 255), min(b + d - 3, 255), a)


def sky():
    a = new()
    for y in range(H):
        for x in range(W):
            a[y, x] = hx(sky_band_color(y, x))
    # 两缕很淡的长云（左头离太阳近，亮一档）
    for (yy, xa, xb) in [(36, 150, 392), (37, 168, 410), (38, 214, 330), (92, 262, 470), (93, 290, 452)]:
        for x in range(xa, xb):
            a[yy, x] = lighten(a[yy, x], 5 if x > xa + 40 else 8)
    # 太阳：一圈一圈平的光晕（Linger 那种分档），中间一个淡的日轮
    cx, cy = SUN
    for r, d in [(30, 4), (21, 9), (14, 18)]:
        m = disc(cx, cy, r)
        for y, x in zip(*np.nonzero(m)):
            a[y, x] = lighten(hx(sky_band_color(y, x)), d)
    fill(a, disc(cx, cy, 8), "c2b393")
    fill(a, disc(cx, cy, 6), "dfd0ab")
    return a


# ================================================================== 远处的城（逆光的灰楼，几乎化进雾里）
def far_city():
    a = new(TW)
    rng = random.Random(11)
    x = 0
    while x < TW:
        w = rng.randint(24, 60)
        top = rng.randint(64, 104)
        face, lit = "60625d", "6d6c64"
        wrap_rect(a, x, top, x + w - 1, H - 1, face)
        if rng.random() < 0.45:                       # 楼顶退一截
            sx = x + rng.randint(4, max(5, w // 2))
            wrap_rect(a, sx, top - rng.randint(5, 10), sx + rng.randint(6, 12), top - 1, face)
        if rng.random() < 0.35:                       # 天线（从楼顶长出来，连着）
            ax = x + rng.randint(3, w - 4)
            for yy in range(top - rng.randint(5, 9), top):
                wrap_put(a, ax, yy, face)
        for yy in range(top, H):                      # 朝太阳的左边一道亮边
            wrap_put(a, x, yy, lit)
        x += w + rng.randint(-6, 14)
    return a


# ================================================================== 远处的田野（出了城以后）
def far_land():
    a = new(TW)
    for x in range(TW):
        t = 2 * math.pi * x / TW
        h1 = 150 - 6 * math.sin(t * 2 + 0.6) - 3 * math.sin(t * 5 + 1.3) - 2 * math.sin(t * 9)
        h2 = 166 - 3 * math.sin(t * 3 + 2.0) - 2 * math.sin(t * 7 + 0.4)
        for y in range(int(round(h1)), H):
            a[y, x] = hx("70716a")
        for y in range(int(round(h2)), H):
            a[y, x] = hx("676a62")
        a[int(round(h1)), x] = hx("7a796f")           # 坡顶一线受光
    rng = random.Random(5)                            # 远处零星几棵树、一间小屋（剪影）
    for _ in range(7):
        tx = rng.randrange(TW)
        ty = int(round(166 - 3 * math.sin(2 * math.pi * tx / TW * 3 + 2.0)))
        r = rng.randint(2, 4)
        for y in range(ty - 2 * r, ty + 1):
            for x in range(tx - r, tx + r + 1):
                if (x - tx) ** 2 + ((y - (ty - r)) * 0.9) ** 2 <= r * r + 1:
                    wrap_put(a, x, y, "5e625b")
    return a


# ================================================================== 中景：鸽子笼高楼（逆光剪影）
MID_FACE, MID_SHADE, MID_RIM, MID_TOP = "3d4140", "393d3c", "625e55", "56544d"
MID_BAL, MID_WIN = "434746", "373b3a"


def mid_towers():
    a = new(TW)
    rng = random.Random(7)
    x = 6
    spans = []
    while x < TW - 20:
        w = rng.randint(40, 84)
        if x + w > TW - 8:
            w = TW - 8 - x
        if w < 30:
            break
        top = rng.choice([rng.randint(16, 44), rng.randint(42, 86)])
        spans.append((x, w, top))
        x += w + rng.randint(16, 50)
    for (x, w, top) in spans:
        rect(a, x, top, x + w - 1, H - 1, MID_FACE)
        # 楼梯间那一竖条暗一档（只有一些楼有）
        if rng.random() < 0.5:
            cx = x + rng.randint(w // 3, 2 * w // 3)
            rect(a, cx, top + 3, cx + 2, H - 1, MID_SHADE)
        # 阳台：零星几层、只占一段宽度，亮一档
        for fy in range(top + 6, H, 8):
            if rng.random() < 0.32:
                xa = x + rng.randint(2, w // 2)
                xb = min(x + w - 3, xa + rng.randint(8, w // 2 + 6))
                rect(a, xa, fy, xb, fy, MID_BAL)
                if rng.random() < 0.4:                # 阳台底下挂一件晾着的衣服 / 一个空调外机
                    px = rng.randint(xa, max(xa, xb - 3))
                    rect(a, px, fy + 1, px + 1, fy + 2, MID_BAL)
            if rng.random() < 0.18:                   # 黑着的窗：暗一档，一两个
                wx = x + rng.randint(3, w - 6)
                rect(a, wx, fy + 2, wx + 2, fy + 4, MID_WIN)
        # 楼顶：受光的一线、水箱、天线
        rect(a, x, top, x + w - 1, top, MID_TOP)
        if rng.random() < 0.6:
            tx = x + rng.randint(4, w - 14)
            rect(a, tx, top - 6, tx + 8, top - 3, MID_FACE)
            rect(a, tx, top - 6, tx + 8, top - 6, MID_TOP)
            for lx in (tx + 1, tx + 7):               # 水箱的腿踩在楼顶上
                rect(a, lx, top - 2, lx, top - 1, MID_FACE)
        if rng.random() < 0.55:
            ax = x + rng.randint(2, w - 3)
            ah = rng.randint(7, 16)
            rect(a, ax, top - ah, ax, top - 1, MID_FACE)
            if rng.random() < 0.6:
                rect(a, ax - 2, top - ah + 3, ax + 2, top - ah + 3, MID_FACE)
        # 朝太阳的左边：一道暖边（楼顶那一截是两格）
        rect(a, x, top, x, H - 1, MID_RIM)
        rect(a, x + 1, top, x + 1, top + 14, MID_RIM)
    return a


# ================================================================== 近景：铁路边的矮楼顶（比中景快、更暗）
NEAR_FACE, NEAR_RIM, NEAR_TOP = "323635", "57544c", "45453f"


def near_blocks():
    a = new(TW)
    rng = random.Random(31)
    x = 20
    while x < TW - 40:
        w = rng.randint(34, 76)
        if x + w > TW - 10:
            break
        top = rng.randint(86, 110)
        rect(a, x, top, x + w - 1, H - 1, NEAR_FACE)
        rect(a, x, top, x + w - 1, top, NEAR_TOP)
        rect(a, x, top, x, H - 1, NEAR_RIM)
        # 楼顶的东西：一圈栏杆（连着的横线，两头立柱踩在楼顶上）、楼梯间、空调箱、晾衣杆
        if rng.random() < 0.6:
            ry = top - 4
            rect(a, x + 2, ry, x + w - 3, ry, NEAR_FACE)
            for px in (x + 2, x + w - 3):
                rect(a, px, ry, px, top - 1, NEAR_FACE)
            put(a, x + 2, ry, NEAR_RIM)
        if rng.random() < 0.55:
            hx0 = x + rng.randint(3, max(4, w - 16))
            rect(a, hx0, top - 9, hx0 + 11, top - 1, NEAR_FACE)
            rect(a, hx0, top - 9, hx0 + 11, top - 9, NEAR_TOP)
            rect(a, hx0, top - 9, hx0, top - 1, NEAR_RIM)
            rect(a, hx0 + 7, top - 6, hx0 + 9, top - 1, "2c302f")       # 楼梯间的门
        for _ in range(rng.randint(0, 2)):
            bx = x + rng.randint(3, w - 8)
            rect(a, bx, top - 3, bx + 4, top - 1, NEAR_FACE)
            rect(a, bx, top - 3, bx + 4, top - 3, NEAR_TOP)
        if rng.random() < 0.35:                       # 晾衣绳：两根杆子之间一根连着的线，挂两件衣服
            p0 = x + rng.randint(4, w // 2)
            p1 = min(x + w - 4, p0 + rng.randint(12, 22))
            rect(a, p0, top - 8, p0, top - 1, NEAR_FACE)
            rect(a, p1, top - 8, p1, top - 1, NEAR_FACE)
            rect(a, p0, top - 8, p1, top - 8, "3a3e3c")
            for cx in (p0 + 3, p0 + 3 + (p1 - p0) // 2):
                rect(a, cx, top - 7, cx + 3, top - 4, "3f4240")
        x += w + rng.randint(28, 96)
    return a


# ================================================================== 一排树（出了城，铁路边）
TREE_DARK, TREE_MID, TREE_LIT, TREE_RIM = "27322d", "2e3a34", "3c473e", "5b6050"
TRUNK, TRUNK_LIT = "262b28", "3a3d36"


def trees():
    a = new(TW)
    rng = random.Random(23)
    xs = []
    x = 30
    while x < TW - 40:
        xs.append(x)
        x += rng.randint(82, 112)
    for tx in xs:
        cy = rng.randint(80, 94)
        rx = rng.randint(20, 28)
        ry = rng.randint(30, 38)
        # 树冠：几团叠在一起
        blobs = [(tx, cy, rx, ry)]
        for _ in range(rng.randint(3, 5)):
            bx = tx + rng.randint(-rx + 4, rx - 4)
            by = cy + rng.randint(-ry + 6, ry - 8)
            blobs.append((bx, by, rng.randint(9, 15), rng.randint(9, 14)))
        yy, xx = np.mgrid[0:H, 0:TW]
        owner = np.full((H, TW), -1)
        best = np.full((H, TW), 9.0)
        # 树冠的边不是光滑的椭圆：按 3 像素一格的随机起伏，鼓出 / 缺进一小簇叶子
        cells = np.array([[rng.random() for _ in range(TW // 3 + 2)] for _ in range(H // 3 + 2)])
        lumpy = cells[yy // 3, xx // 3] * 0.32 - 0.12
        for i, (bx, by, bxr, byr) in enumerate(blobs):
            d = ((xx - bx) / bxr) ** 2 + ((yy - by) / byr) ** 2 - lumpy
            m = (d <= 1.0) & (d < best)
            owner[m] = i
            best[m] = d[m]
        mask = owner >= 0
        # 树干先画（树冠盖在上面）
        top = cy + ry - 8
        rect(a, tx - 1, top, tx + 1, H - 1, TRUNK)
        rect(a, tx - 1, top, tx - 1, H - 1, TRUNK_LIT)
        bx2 = tx + rng.choice([-1, 1]) * rng.randint(6, 10)
        for px, py in line_pts(tx, top + 10, bx2, cy + 6):
            put(a, px % TW, py, TRUNK)
            put(a, px % TW, py + 1, TRUNK)
        # 树冠：每团按自己朝左上的那面受光（逆光，大部分是暗的）
        for y, x in zip(*np.nonzero(mask)):
            bx, by, bxr, byr = blobs[owner[y, x]]
            nx, ny = (x - bx) / bxr, (y - by) / byr
            lit = -(0.6 * nx + 0.8 * ny)
            c = TREE_DARK
            if lit > 0.75:
                c = TREE_LIT
            elif lit > 0.2:
                c = TREE_MID
            a[y, x % TW] = hx(c)
        for y, x in zip(*np.nonzero(mask)):          # 朝太阳的边：上面或左边是空的
            if (y > 0 and not mask[y - 1, x]) or (x > 0 and not mask[y, x - 1]):
                bx, by, bxr, byr = blobs[owner[y, x]]
                if -(0.6 * (x - bx) / bxr + 0.8 * (y - by) / byr) > 0.1:
                    a[y, x % TW] = hx(TREE_RIM)
    # 路基上的矮灌木一条（只在窗的下沿露一点）
    for x in range(TW):
        yt = 192 + round(1.5 * math.sin(x / 17.0) + math.sin(x / 7.3))
        for y in range(yt, H):
            if a[y, x, 3] == 0:
                a[y, x] = hx("29322e")
        if a[yt, x, 3] == 0 or tuple(a[yt, x]) == hx("29322e"):
            a[yt, x] = hx("36403a")
    return a


# ================================================================== 接触网的杆子（铁路边，跑得最快）
def poles():
    a = new(W)
    px = 300
    rect(a, px, WIRE_Y - 5, px + 2, H - 1, "2b2e2e")
    rect(a, px, WIRE_Y - 5, px, H - 1, "4e4d47")
    rect(a, px - 1, WIRE_Y - 6, px + 3, WIRE_Y - 6, "333636")      # 杆顶
    rect(a, px + 3, WIRE_Y - 3, px + 9, WIRE_Y - 3, "2b2e2e")      # 腕臂
    line(a, px + 3, WIRE_Y + 4, px + 9, WIRE_Y - 2, "2b2e2e")      # 斜撑，接在腕臂头上
    rect(a, px + 8, WIRE_Y - 2, px + 8, WIRE_Y - 1, "2b2e2e")      # 吊弦落到接触网上
    rect(a, px + 4, WIRE_Y - 4, px + 5, WIRE_Y - 4, "5a5a53")      # 绝缘子
    return a


# ================================================================== 高架桥面（车下面，跟杆子一样快）
def deck():
    a = new(W)
    rect(a, 0, 259, W - 1, 259, "4b4c48")
    rect(a, 0, 260, W - 1, 261, "3d3f3c")
    rect(a, 0, 262, W - 1, H - 1, "363836")
    for sx in (41, 157, 289, 398):                    # 伸缩缝：零星、暗一档
        rect(a, sx, 261, sx, H - 1, "313331")
    rect(a, 210, 265, 236, 265, "3a3c3a")             # 一道补过的痕
    return a


# ================================================================== 车厢（剖面）
C_ROOF_TOP, C_ROOF_HI, C_ROOF, C_ROOF_LO, C_CUT = "66645b", "4c504e", "444847", "3a3e3e", "2a2d2e"
C_CEIL, C_STRIP, C_COVE = "2c2f30", "3a3c39", "313435"
C_WALL, C_WALL_LO, C_KICK, C_JOIN = "383c3c", "343838", "2f3233", "292c2c"
C_FRAME, C_SILL, C_REVEAL, C_HEAD = "464a49", "6a665a", "55544d", "3e4241"
C_FLOOR, C_FLOOR_SCUFF, C_FLOOR_EDGE, C_SLAB = "393b3a", "343635", "262828", "2e3030"
C_SEAT, C_SEAT_LIT, C_SEAT_TOP, C_SEAT_SH = "33403c", "3f4c47", "4a5650", "2b3633"
C_METAL, C_METAL_LIT = "454846", "6d6e68"


def glass_holes():
    """[(x0, y0, x1, y1)] 玻璃（含两端），四个角各缺一格（圆角）"""
    hs = [(BAY0 + BAY * i + 2, GLASS_T, min(BAY0 + BAY * i + 50, W - 1), GLASS_B) for i in range(NBAY + 1)]
    hs += [(a, 161, b, 196) for (a, b) in DOOR_GLASS]
    return hs


def cut_hole(a, x0, y0, x1, y1):
    rect(a, x0, y0, x1, y1, (0, 0, 0, 0))
    for (cx, cy) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        put(a, cx, cy, C_FRAME)


def seat(a, b):
    """一个朝右的座位（侧面）：b = 椅背左边"""
    for y in range(189, 213):
        o = (y - 189) // 8
        l, r = b + 1 + o, b + 6 + o
        if y == 189:
            l, r = b + 2, b + 5
        rect(a, l, y, r, y, C_SEAT)
        put(a, l, y, C_SEAT_LIT)
        put(a, r, y, C_SEAT_SH)
    rect(a, b + 2, 189, b + 5, 189, C_SEAT_TOP)
    rect(a, b + 1, 190, b + 1, 192, C_SEAT_TOP)
    rect(a, b + 7, 208, b + 29, 213, C_SEAT)
    rect(a, b + 7, 208, b + 28, 208, C_SEAT_TOP)
    rect(a, b + 7, 213, b + 29, 213, C_SEAT_SH)
    put(a, b + 29, 208, (0, 0, 0, 0))
    put(a, b + 29, 213, (0, 0, 0, 0))
    rect(a, b + 29, 209, b + 29, 212, C_SEAT_LIT)
    rect(a, b + 13, 214, b + 16, 225, "2c2f30")       # 底座
    rect(a, b + 13, 214, b + 13, 225, "3c3f3f")
    rect(a, b + 10, 225, b + 19, 226, "333636")


def car():
    a = new()
    # 车顶（远侧的车顶从侧面看是一条，最上面一线晒着太阳）
    rect(a, 0, ROOF, W - 1, CEIL - 1, C_ROOF)
    rect(a, 0, ROOF, W - 1, ROOF, C_ROOF_TOP)
    rect(a, 0, ROOF + 1, W - 1, ROOF + 1, C_ROOF_HI)
    rect(a, 0, ROOF + 8, W - 1, CEIL - 2, C_ROOF_LO)
    rect(a, 0, CEIL - 1, W - 1, CEIL - 1, C_CUT)
    for gx in (130, 262, 394):                         # 车顶板的接缝：零星三道、暗一档
        rect(a, gx, ROOF + 2, gx, ROOF + 7, "404443")
    # 空调机组
    rect(a, 331, 114, 397, ROOF - 1, "454948")
    rect(a, 332, 114, 396, 114, "615f57")
    put(a, 331, 114, (0, 0, 0, 0))
    put(a, 397, 114, (0, 0, 0, 0))
    rect(a, 331, 115, 331, ROOF - 1, "57564f")
    rect(a, 352, 117, 360, 118, "3e4241")
    rect(a, 371, 117, 379, 118, "3e4241")
    # 受电弓：底座 + 两个绝缘子 + 单臂，弓头顶着接触网
    for ix in (200, 230):
        rect(a, ix, ROOF - 4, ix + 2, ROOF - 1, "5a5b55")
        rect(a, ix, ROOF - 4, ix + 2, ROOF - 4, "6c6a61")
    rect(a, 199, ROOF - 5, 233, ROOF - 5, "2f3232")
    line(a, 205, ROOF - 6, 229, 108, "2c2f2f")
    line(a, 206, ROOF - 6, 230, 108, "2c2f2f")
    line(a, 229, 108, 214, WIRE_Y + 2, "2c2f2f")
    rect(a, 207, WIRE_Y + 1, 221, WIRE_Y + 1, "3a3c3a")
    rect(a, 207, WIRE_Y + 1, 207, WIRE_Y + 2, "3a3c3a")
    rect(a, 221, WIRE_Y + 1, 221, WIRE_Y + 2, "3a3c3a")
    # 接触网：一条连着的线，横穿整屏
    rect(a, 0, WIRE_Y, W - 1, WIRE_Y, "2a2d2d")
    # 顶棚、灯带（白天没开）、扶手杆
    rect(a, 0, CEIL, W - 1, 145, C_CEIL)
    rect(a, 0, 140, W - 1, 141, C_STRIP)
    rect(a, 0, 145, W - 1, 145, C_COVE)
    rect(a, 0, 146, W - 1, WIN_T - 1, C_WALL)
    rect(a, POLE_X, RAIL_Y, W - 1, RAIL_Y, "5f625f")
    rect(a, POLE_X, RAIL_Y + 1, W - 1, RAIL_Y + 1, "414443")
    for bx in (140, 268, 396):
        put(a, bx, 146, "4a4d4b")
    # 墙：窗带、窗下的墙、踢脚、和地板的交线
    rect(a, 0, WIN_T, W - 1, WIN_B, C_WALL)
    rect(a, 0, WIN_B + 1, W - 1, 225, C_WALL_LO)
    rect(a, 0, 222, W - 1, 225, C_KICK)
    rect(a, 0, 226, W - 1, 226, C_JOIN)
    # 窗
    for i in range(NBAY + 1):
        x0 = BAY0 + BAY * i
        rect(a, x0, WIN_T, x0 + 52, WIN_B, C_FRAME)
        cut_hole(a, x0 + 2, GLASS_T, x0 + 50, GLASS_B)
        rect(a, x0 + 2, GLASS_T - 1, x0 + 50, GLASS_T - 1, C_HEAD)
        rect(a, x0 + 2, GLASS_B + 1, x0 + 50, GLASS_B + 1, C_SILL)       # 窗台晒着
        rect(a, x0 + 51, GLASS_T, x0 + 51, GLASS_B, C_REVEAL)
    # 门（第三节车厢）
    rect(a, DOOR[0], 148, DOOR[1], 226, "424645")
    rect(a, DOOR[0], 148, DOOR[1], 149, "4a4d4b")
    rect(a, 30, 151, 50, 225, "3b3f3f")
    rect(a, 52, 151, 72, 225, "3b3f3f")
    rect(a, 51, 151, 51, 225, "2a2d2d")
    rect(a, 30, 151, 30, 225, "444847")
    rect(a, 52, 151, 52, 225, "444847")
    for (g0, g1) in DOOR_GLASS:
        rect(a, g0, 160, g1, 160, C_HEAD)
        cut_hole(a, g0, 161, g1, 196)
        rect(a, g0, 197, g1, 197, C_SILL)
        rect(a, g1 + 1, 161, g1 + 1, 196, C_REVEAL)
    rect(a, DOOR[0], 226, DOOR[1], 226, "57554e")     # 门槛
    # 车厢号「3」：门上面顶棚边上的小牌子
    rect(a, 45, 139, 57, 145, "565954")
    rect(a, 45, 139, 57, 139, "64665f")
    for (gx, gy) in [(49, 140), (50, 140), (51, 140), (51, 141), (50, 142), (51, 142), (51, 143),
                     (49, 144), (50, 144), (51, 144)]:
        put(a, gx, gy, "262929")
    # 门边的立杆（上接顶棚、下到地板，扶手杆从它往右）
    rect(a, POLE_X - 1, CEIL, POLE_X + 2, CEIL + 1, "4f514e")
    rect(a, POLE_X, CEIL, POLE_X, 226, C_METAL_LIT)
    rect(a, POLE_X + 1, CEIL, POLE_X + 1, 226, C_METAL)
    rect(a, POLE_X - 1, 225, POLE_X + 2, 226, "4f514e")
    # 座位
    for i in range(NBAY):
        seat(a, 96 + BAY * i)
    # 地板（侧面看是窄窄的一条，近侧切开的断面在下面）
    rect(a, 0, 227, W - 1, 235, C_FLOOR)
    rect(a, 0, 235, W - 1, 235, "3f413f")
    rect(a, 0, 236, W - 1, 236, C_FLOOR_EDGE)
    rect(a, 0, 237, W - 1, 239, C_SLAB)
    for (sx, sy, sl) in [(140, 231, 9), (262, 233, 6), (437, 230, 7)]:   # 磨痕：零星、暗一档
        rect(a, sx, sy, sx + sl, sy, C_FLOOR_SCUFF)
    for (fx, fy) in [(86, 231), (95, 233), (106, 231)]:                   # 门口进来的湿脚印，快干了
        rect(a, fx, fy, fx + 2, fy, C_FLOOR_SCUFF)
    # 4 号座位的人带了一把湿伞：靠在膝前，尖底下一小摊水
    b = 96 + BAY * 4
    for y in range(207, 226):
        k = (y - 207) // 7
        rect(a, b + 33 + (y - 207) // 9, y, b + 35 - k + (y - 207) // 9, y, "2b3532")
    rect(a, b + 33, 207, b + 33, 213, "3a4643")
    put(a, b + 35, 226, "2b3532")
    rect(a, b + 32, 204, b + 34, 204, "4c4840")       # 伞把（弯钩）
    put(a, b + 32, 205, "4c4840")
    put(a, b + 34, 205, "4c4840")
    put(a, b + 34, 206, "4c4840")
    rect(a, b + 31, 227, b + 41, 228, "434745")       # 水：亮一档，一个暖色的反光
    put(a, b + 37, 227, "6e6a5c")
    # 车下：裙板、设备箱、转向架、车轮、钢轨
    rect(a, 0, 240, W - 1, 245, "2c2f30")
    rect(a, 0, 240, W - 1, 240, "3a3d3d")
    rect(a, 0, 246, W - 1, 256, "202323")
    for (e0, e1) in ((150, 230), (252, 330)):
        rect(a, e0, 246, e1, 253, "282b2c")
        rect(a, e0, 246, e1, 246, "323535")
    for c in (70, 410):
        rect(a, c - 34, 246, c + 34, 249, "2a2d2d")
        for wx in (c - 22, c + 22):
            m = disc(wx, 251, 5)
            fill(a, m, "1d2020")
            for y, x in zip(*np.nonzero(m)):
                ang = math.atan2(y - 251, x - wx)
                edge = (x - wx) ** 2 + (y - 251) ** 2 >= 16
                if edge and -2.6 < ang < -0.9:
                    a[y, x] = hx("3d3f3c")
            put(a, wx, 251, "4a4b47")
    rect(a, 0, 257, W - 1, 257, "5d5d57")
    rect(a, 0, 258, W - 1, 258, "2f3130")
    return a


# ================================================================== 玻璃：很淡的反光 + 雨停以后留在玻璃上的水珠
def glass():
    a = new()
    rng = random.Random(3)
    for (x0, y0, x1, y1) in glass_holes():
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if (x - x0 - (y - y0) * 0.7) % 61 < 5:
                    a[y, x] = (235, 232, 220, 16)
        if x1 - x0 < 12:
            continue
        # 车在往右开：玻璃上的水珠被风往后（左）、往下吹，身后拖一道往右上的斜痕（连着的线）
        for _ in range(rng.choice([0, 1, 1, 2])):
            dx = rng.randint(x0 + 2, max(x0 + 2, x1 - 12))
            dy = rng.randint(y0 + 10, y1 - 4)
            tl = rng.randint(5, 11)
            for (px, py) in line_pts(dx, dy, dx + tl, dy - tl // 2)[1:]:
                if x0 <= px <= x1 and y0 <= py <= y1:
                    a[py, px] = (196, 196, 184, 40)
            a[dy, dx] = (226, 218, 196, 130)
            a[dy + 1, dx] = (190, 190, 180, 70)
        if rng.random() < 0.6:                           # 一颗还没被吹动的小水珠，太阳在上面一点
            a[rng.randint(y0 + 3, y1 - 3), rng.randint(x0 + 3, x1 - 3)] = (240, 228, 200, 120)
    return a


# ================================================================== 兜帽乘客（逆光剪影，低头看手机）
P_RAMP = ["1e2021", "25282a", "2c2f31", "34373a", "3d4043", "474a4d"]
P_RIM, P_RIM2, P_SHOE, P_PHONE, P_GLOW = "6b6457", "857b68", "1b1d1e", "26292b", "93a8a3"
NFR = 16


def sway(f, phase=0.0, amp=0.75):
    return int(round(amp * math.sin(2 * math.pi * f / NFR + phase)))


def tint(ramp, d):
    """袍子的灰各人不一样：整条色阶偏一点点（暖灰、冷灰、带一点绿）"""
    out = []
    for c in ramp:
        r, g, b, _ = hx(c)
        out.append("%02x%02x%02x" % tuple(max(0, min(255, v + dv)) for v, dv in zip((r, g, b), d)))
    return out


def shade_figure(a, m, top_y, bot_y, folds=(), dark_face=None, ramp=P_RAMP, rim_max_x=None):
    """逆光的人：大部分暗，上面和左边（朝窗、朝太阳）一道暖边；越往下越暗一点；褶子是斜的暗楔。
    rim_max_x：头顶的暖边只画到这一列（太阳在左后方，帽兜右半边照不到）"""
    ys, xs = np.nonzero(m)
    for y, x in zip(ys, xs):
        t = (y - top_y) / max(1, bot_y - top_y)
        k = 3 if t < 0.25 else (2 if t < 0.7 else 1)
        a[y, x] = hx(ramp[k])
    for (p, q) in folds:
        for x, y in line_pts(*p, *q):
            if m[y, x]:
                a[y, x] = hx(ramp[1])
            if x - 1 >= 0 and m[y, x - 1] and m[y, x]:
                a[y, x - 1] = hx(ramp[4])             # 褶子朝光那侧亮一档的棱
    for y, x in zip(ys, xs):
        up = y == 0 or not m[y - 1, x]
        left = x == 0 or not m[y, x - 1]
        if up and y < bot_y - 6 and (rim_max_x is None or x <= rim_max_x):
            a[y, x] = hx(P_RIM2 if y < top_y + 6 else P_RIM)
        elif left and y < top_y + 9:                # 只有帽兜那一截有侧边的暖光，身子不描
            a[y, x] = hx(P_RIM)
    if dark_face is not None:
        fill(a, dark_face & m, ramp[0])


def seated(a, b, kind, f, ramp=P_RAMP):
    """b = 椅背左边。kind: phone / low（头更低、戴着耳机线）/ sleep（仰头靠着窗睡着了）/ bag"""
    bob = 1 if kind == "sleep" and f in (5, 6, 13) else 0
    low = 2 if kind == "low" else 0
    hy = 180 + low + bob
    if kind == "sleep":
        hy = 178 + bob
        hood = [(b + 2, 186 + bob), (b + 2, 182 + bob), (b + 4, 179 + bob), (b + 8, 178 + bob), (b + 11, 179 + bob),
                (b + 13, 182 + bob), (b + 14, 186 + bob), (b + 13, 189), (b + 11, 191), (b + 6, 191), (b + 3, 189)]
        face = [(b + 9, 180 + bob), (b + 12, 181 + bob), (b + 13, 184 + bob), (b + 11, 185 + bob), (b + 9, 183 + bob)]
    else:
        hood = [(b + 7, 184 + low), (b + 8, 181 + low), (b + 9, hy - 1), (b + 13, hy), (b + 16, hy + 1),
                (b + 18, hy + 3), (b + 19, hy + 6), (b + 18, hy + 9), (b + 15, 191), (b + 9, 191), (b + 7, 188)]
        face = [(b + 15, hy + 4), (b + 18, hy + 5), (b + 18, hy + 8), (b + 15, hy + 9)]
    torso = [(b + 8, 189), (b + 16, 189), (b + 19, 192), (b + 19, 199), (b + 18, 207), (b + 9, 208), (b + 8, 200)]
    lap = [(b + 9, 201), (b + 18, 200), (b + 28, 201), (b + 29, 203), (b + 29, 207), (b + 10, 207)]
    shin = [(b + 24, 203), (b + 29, 203), (b + 30, 208), (b + 31, 222), (b + 31, 225), (b + 25, 225), (b + 25, 210)]
    m = pmask(hood) | pmask(torso) | pmask(lap) | pmask(shin)
    if kind == "sleep":
        arm = [(b + 12, 199), (b + 20, 199), (b + 24, 201), (b + 23, 203), (b + 12, 203)]     # 手叠在腿上
    else:
        py = 192 + low
        arm = [(b + 13, 194), (b + 16, 193), (b + 22, py), (b + 23, py + 2), (b + 17, 197), (b + 13, 197)]
    arm_m = pmask(arm)
    fm = pmask(face)
    shade_figure(a, m, hy - 1, 225, folds=[((b + 12, 193), (b + 10, 206)), ((b + 20, 202), (b + 27, 205))],
                 dark_face=fm, ramp=ramp, rim_max_x=b + (10 if kind == "sleep" else 13))
    # 袖子在身体前面：亮一档，上沿一道暖边
    for y, x in zip(*np.nonzero(arm_m)):
        a[y, x] = hx(ramp[3])
        if not arm_m[y - 1, x]:
            a[y, x] = hx(ramp[4])
    rect(a, b + 26, 225, b + 33, 226, P_SHOE)
    put(a, b + 26, 225, ramp[2])
    if kind == "low":                                # 耳机线：从帽兜里垂下来，绕到手机上（连着的一根）
        py = 192 + low
        for (p0, p1) in (((b + 16, hy + 9), (b + 17, 197)), ((b + 17, 197), (b + 19, 199)),
                         ((b + 19, 199), (b + 23, py + 1))):
            line(a, *p0, *p1, "686b67")
    if kind == "bag":                                # 腿上一个包
        rect(a, b + 15, 197, b + 25, 201, "3a3a37")
        rect(a, b + 15, 197, b + 25, 197, "55534b")
        line(a, b + 17, 196, b + 20, 193, "3a3a37")
    if kind != "sleep":
        py = 192 + low
        rect(a, b + 22, py - 1, b + 24, py, P_PHONE)
        # 手机屏的冷光：一格亮在屏上，一格淡淡地照在帽兜开口的下沿
        scroll = (kind == "phone" and f in (8, 9)) or (kind == "bag" and f in (3, 4, 11))
        put(a, b + 23 + (1 if scroll else 0), py - 1, P_GLOW)
        put(a, b + 17, hy + 8, "4a5654")
    else:
        put(a, b + 10, 181 + bob, ramp[1])


def standing(a, x, f, ramp=P_RAMP):
    """门边的立杆旁边站着一个，一只手抓着杆子，一只手看手机；车晃，身子跟着挪一格"""
    s = sway(f, 0.4)
    hx0 = x + s
    hood = [(hx0 + 1, 182), (hx0 + 2, 179), (hx0 + 4, 177), (hx0 + 8, 177), (hx0 + 11, 179), (hx0 + 12, 182),
            (hx0 + 11, 186), (hx0 + 8, 188), (hx0 + 2, 188)]
    face = [(hx0 + 9, 181), (hx0 + 12, 182), (hx0 + 11, 185), (hx0 + 9, 185)]
    body = [(hx0 + 1, 187), (hx0 + 10, 187), (hx0 + 12, 192), (hx0 + 12, 204), (x + 13, 215), (x + 14, 225),
            (x + 1, 225), (x + 1, 214), (hx0 + 1, 200)]
    m = pmask(hood) | pmask(body)
    shade_figure(a, m, 177, 225, folds=[((hx0 + 5, 192), (x + 3, 222)), ((hx0 + 9, 200), (x + 10, 223))],
                 dark_face=pmask(face), ramp=ramp, rim_max_x=hx0 + 6)
    # 抓杆子的那只手：袖子从肩膀伸到杆子上（手一直握在杆上，不跟着晃）
    sh = (hx0 + 3, 190)
    hand = (POLE_X + 2, 183)
    arm = pmask([(sh[0], sh[1] - 1), (sh[0] + 2, sh[1]), (hand[0] + 1, hand[1] + 2), (hand[0], hand[1] + 1),
                 (hand[0], hand[1] - 1)])
    for y, xx in zip(*np.nonzero(arm)):
        a[y, xx] = hx(ramp[3] if arm[y - 1, xx] else P_RIM)
    rect(a, hand[0], hand[1] - 1, hand[0] + 1, hand[1] + 1, "4d4a46")
    # 另一只手拿着手机在胸前
    rect(a, hx0 + 8, 194, hx0 + 12, 196, ramp[3])
    rect(a, hx0 + 11, 192, hx0 + 13, 193, P_PHONE)
    put(a, hx0 + 12, 192, P_GLOW)
    put(a, hx0 + 10, 185, "4a5654")
    rect(a, x + 2, 225, x + 7, 226, P_SHOE)
    rect(a, x + 9, 225, x + 15, 226, P_SHOE)


PASSENGERS = [(0, "phone", (0, 0, 0)), (1, "sleep", (3, 1, -2)), (2, "low", (-1, 0, 3)), (4, "phone", (-2, -2, -1)),
              (5, "bag", (-1, 2, 0))]
STAND_X = 84
P_Y0, P_H = 168, 64                                    # 乘客那张图在房间里的位置、高度


def passengers_frame(f):
    a = new()
    for (i, kind, d) in PASSENGERS:
        seated(a, 96 + BAY * i, kind, f, tint(P_RAMP, d))
    standing(a, STAND_X, f, tint(P_RAMP, (2, 2, 2)))
    return a[P_Y0:P_Y0 + P_H]


# ================================================================== 吊环（跟着车晃）
STRAPS = [104, 125, 170, 189, 233, 254, 297, 318, 361, 380, 425, 446]
S_Y0, S_H = 148, 16


def straps_frame(f):
    a = new(W, S_H)
    for k, sx in enumerate(STRAPS):
        d = sway(f, k * 0.9 + (0.0 if k % 2 else 0.5))
        y = 0                                            # 第 0 行 = 房间 148（扶手杆下面一行）
        for yy in range(0, 4):
            put(a, sx, yy, "4b4e4c")
        for yy in range(4, 8):
            put(a, sx + d, yy, "4b4e4c")
        if d != 0:
            put(a, sx + d, 3, "4b4e4c")                # 拐弯处边相邻
        rx = sx + d - 1
        ring = [".##.", "#..#", "#..#", "#..#", ".##."]
        for ry, row in enumerate(ring):
            for rxx, ch in enumerate(row):
                if ch == "#":
                    put(a, rx + rxx, 8 + ry, "6a6c67")
        put(a, rx + 1, 8, "7f7d73")
    return a


# ================================================================== 光束（加法混合，每扇窗一张，home_train.gd 按楼 / 树挡住的程度调亮暗）
WARM = (255, 214, 160)


def beam(x0, x1, top, bot_glass, occupied_by=None):
    """窗的玻璃 [x0, x1]×[top, bot_glass] 照进来的光：空气里很淡的一束、座垫上一线、地板上一块（斜的）。
    返回 (图, 左上角, 地板上亮块的 [左, 右])"""
    a = new()
    poly = [(x0, top), (x1, top), (x1 + (FLOOR - 1 - top) * SUN_DX, FLOOR - 1),
            (x0 + (FLOOR - 1 - bot_glass) * SUN_DX, FLOOR - 1), (x0, bot_glass)]
    m = pmask(poly)
    m[:bot_glass + 1, :] = False                     # 玻璃上不加（窗外的亮度已经画在层里）
    a[m] = WARM + (12,)
    # 照到的座垫上沿、椅背顶上：只在真的有座位的地方
    for i in range(NBAY):
        sb = 96 + BAY * i
        for x in range(sb + 7, sb + 29):
            if m[208, x]:
                a[208, x] = WARM + (48,)
        for x in range(sb + 2, sb + 6):
            if m[189, x]:
                a[189, x] = WARM + (30,)
    # 地板：近处的行再往右挪一点（斜的）
    fl0 = int(round(x0 + (FLOOR - 1 - bot_glass) * SUN_DX))
    fl1 = int(round(x1 + (FLOOR - 1 - top) * SUN_DX))
    for y in range(227, 236):
        o = (y - 227) // 2
        for x in range(fl0 + o, fl1 + o + 1):
            if 0 <= x < W:
                a[y, x] = WARM + (40 if y < 235 else 28,)
    if occupied_by is not None:                       # 坐着的人挡掉一段：影子里只剩三分之一的光（天光还在）
        b = occupied_by
        for y in range(200, 236):
            sh0 = b + 14 + (y - 200) // 2
            sh1 = b + 32 + (y - 200) // 2
            for x in range(max(0, sh0), min(W, sh1)):
                a[y, x, 3] = a[y, x, 3] // 3
    ys, xs = np.nonzero(a[..., 3])
    bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max(), ys.max()
    return a[by0:by1 + 1, bx0:bx1 + 1], (int(bx0), int(by0)), (fl0, fl1 + 4)


def knees():
    """sun_on_knees：落在晨膝上的那块太阳（加法，在晨前面）。图的左上角放在 KNEES_AT"""
    a = new(26, 24)
    for y in range(24):
        for x in range(26):
            u = x - y * SUN_DX * 0.6
            v = y
            if 2 <= u <= 21 and 0 <= v <= 23:
                core = 6 <= u <= 17 and 4 <= v <= 19
                a[y, x] = WARM + (70 if core else 34,)
    return a


KNEES_AT = (TRAIN_SEAT_X - 13, 201)


# ================================================================== 遮挡曲线（给 home_train.gd）
def occlusion(img, rows):
    """每一列：这几行里有没有不透明像素（1 = 挡住太阳）"""
    al = img[rows[0]:rows[1] + 1, :, 3] > 0
    return [1 if al[:, x].any() else 0 for x in range(img.shape[1])]


def save(a, name):
    Image.fromarray(a, "RGBA").save(os.path.join(OUT, name))


def main():
    prev = None
    if "--preview" in sys.argv:
        prev = sys.argv[sys.argv.index("--preview") + 1]
        os.makedirs(prev, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    L = {"sky": sky(), "far_city": far_city(), "far_land": far_land(), "mid": mid_towers(), "near": near_blocks(), "trees": trees(),
         "poles": poles(), "deck": deck(), "car": car(), "glass": glass()}
    for k, v in L.items():
        save(v, k + ".png")
    pf = [passengers_frame(f) for f in range(NFR)]
    save(np.concatenate(pf, axis=1), "passengers.png")
    sf = [straps_frame(f) for f in range(NFR)]
    save(np.concatenate(sf, axis=1), "straps.png")
    save(np.zeros((1, 1, 4), np.uint8), "empty.png")
    save(knees(), "knees.png")
    beams = []
    occ_bays = {i: 96 + BAY * i for (i, _, _) in PASSENGERS}
    for i in range(NBAY + 1):
        x0 = BAY0 + BAY * i
        img, at, flr = beam(x0 + 2, x0 + 50, GLASS_T, GLASS_B, occ_bays.get(i))
        save(img, "beam_%d.png" % i)
        beams.append({"img": "beam_%d.png" % i, "at": list(at), "win": x0 + 26, "floor": list(flr)})
    for j, (g0, g1) in enumerate(DOOR_GLASS):
        img, at, flr = beam(g0, g1, 161, 196)
        save(img, "beam_door%d.png" % j)
        beams.append({"img": "beam_door%d.png" % j, "at": list(at), "win": (g0 + g1) // 2, "floor": list(flr)})
    data = {"_note": "tools/home_train_art.py 生成。occ_*：窗外层每一列挡不挡太阳（1 = 挡），home_train.gd 按这个调光束。",
            "beams": beams, "knees_at": list(KNEES_AT), "empty_bay_floor": beams[EMPTY_BAY]["floor"],
            "occ_mid": occlusion(L["mid"], (50, 58)), "occ_near": occlusion(L["near"], (88, 100)), "occ_trees": occlusion(L["trees"], (84, 100)),
            "solid_mid": occlusion(L["mid"], (0, H - 1)), "solid_near": occlusion(L["near"], (0, H - 1))}
    with open(os.path.join(OUT, "occlusion.json"), "w") as fp:
        json.dump(data, fp, ensure_ascii=False, separators=(",", ":"))
    print("wrote", OUT, "mid occ %.2f trees occ %.2f" % (np.mean(data["occ_mid"]), np.mean(data["occ_trees"])))
    if prev:
        preview(L, pf, sf, beams, prev)


def chen_frame(i=7):
    sheet = np.array(Image.open(os.path.join(ROOT, "art/characters/chen/chen_oscar.png")).convert("RGBA"))
    return sheet[:, i * 68:(i + 1) * 68]


def compose(L, pf, sf, beams, phase, chen_x, knees_on, f=0, s=(0, 0, 0, 0)):
    """phase: city / trees。s = 各层平移量 (far, mid/trees, poles)"""
    out = np.zeros((H, W, 4), np.uint8)
    out[..., 3] = 255
    over(out, L["sky"])

    def tile(img, off, tw):
        t = np.concatenate([img, img], axis=1)
        return t[:, off % tw:off % tw + W]
    if phase == "city":
        over(out, tile(L["far_city"], s[0], TW))
        over(out, tile(L["mid"], s[1], TW))
        over(out, tile(L["near"], s[1] * 2, TW))
    else:
        over(out, tile(L["far_land"], s[0], TW))
        over(out, tile(L["trees"], s[1], TW))
    over(out, tile(L["poles"], s[2], W))
    over(out, tile(L["deck"], s[2], W))
    over(out, L["car"])
    over(out, L["glass"])
    for bm in beams:
        img = np.array(Image.open(os.path.join(OUT, bm["img"])).convert("RGBA"))
        add_light(out, img, *bm["at"])
    st = np.zeros((H, W, 4), np.uint8)
    st[S_Y0:S_Y0 + S_H] = sf[f]
    over(out, st)
    pp = np.zeros((H, W, 4), np.uint8)
    pp[P_Y0:P_Y0 + P_H] = pf[f]
    over(out, pp)
    if chen_x is not None:
        ch = chen_frame()
        over(out, ch, chen_x - 28, FLOOR - 56)
    if knees_on:
        add_light(out, knees(), *KNEES_AT)
    return out


def preview(L, pf, sf, beams, d):
    a = compose(L, pf, sf, beams, "city", TRAIN_SEAT_X, False, 0, (40, 120, 60))
    Image.fromarray(a).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(d, "home_train_city_2x.png"))
    b = compose(L, pf, sf, beams, "trees", TRAIN_SEAT_X, True, 4, (300, 70, 200))
    Image.fromarray(b).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(d, "home_train_trees_2x.png"))
    c = compose(L, pf, sf, beams, "city", TRAIN_DOOR_X, False, 6, (40, 300, 160))
    Image.fromarray(c).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(d, "home_train_door_2x.png"))
    print("preview", d)


if __name__ == "__main__":
    main()
