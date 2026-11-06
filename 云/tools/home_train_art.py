#!/usr/bin/env python3
"""终章尾声最后一段「回家的列车」home_train 的图（art/home_train/）。

11-05 作者实机：「背景的城市和人跟之前闪回的不一样，电车和之前追逐的也不一样，按照之前改一改，统一画风」。所以这一版全部照母星城市和闪回：
- 窗外的城：不画，scripts/home_train.gd 直接用作者的 res://art/city/{ridge,far,midfar,mid}.png（一样的视差比例）。
  这里只画出城以后才露出来的东西：雾里的日轮（叠在作者 art/city/sky.png 的一份拷贝上）、远山、一排树，都用城市那套近黑偏冷的灰。
- 电车：就是闪回追逐那节车（tools/flashback_train_art.py，art/flashback/train_car.png）的剖面。一样的尺寸和坐标（图里的 y + 110 = 这里的 y，
  x + 10 = 这里的 x，所以门的位置、窗的大小和间距都对得上）：车顶那几行直接取它的像素，门扇直接用 train_door_l/r.png（窗挖空），
  颜色全从 fb.C 取：车里琥珀色的灯、从上往下一档一档暗、吊环、扶杆、座椅、窗框黑胶条、窗上的斜反光、腰带的青灰。
- 人：城市街上的兜帽人。站着的直接是 city_art.person_frame（同一套比例、大衣、围巾、手机、灰度档），坐着的取它腰以上那半截，
  腿照同样的灰度档补（城里的人比晨高近一倍，在这里也一样）。灰度档按 city_crowd_ramp.gdshader 的公式上色。
- 太阳的光束、膝上的太阳、车晃都还在（home_train.gd）。晨身后那段墙是车厢里最暗的档，晨还是对比最高的东西。
- 纹理最多暗一档、零星出现；没有虚线点线；细线都连着实物。

出图：art/home_train/*.png + occlusion.json。--preview 目录：Python 拼的 2 倍预览。--compare 文件 --before 改前图：改前 / 改后 / 闪回参考并排。
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
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import city_art as CA                                  # 作者城市的人物、配色（只读，不跑它的 main）
import flashback_train_art as FB                       # 闪回那节车的颜色、尺寸（只读，不跑它的 main）

OUT = os.path.join(ROOT, "art", "home_train")
CITY = os.path.join(ROOT, "art", "city")
FLASH = os.path.join(ROOT, "art", "flashback")
W, H = 480, 270
TW = 960
C = FB.C

# ------------------------------------------------------------------ 车厢的尺寸（闪回那节车的图坐标 + (10, 110)）
OX, OY = 10, 110
ROOF = OY                      # 车顶第一行
CEIL = OY + FB.ROOF            # 122，车厢里第一行
FLOOR = 228                    # 晨的脚底
RAIL_Y = CEIL + 4
DOOR_Y, DOOR_W, DOOR_H = FB.DOOR[1] + OY, FB.DOOR[2], FB.DOOR[3]
DOOR1_X = FB.DOOR[0] + OX      # 34..70，中间 52 = train_door
DOOR2_X = FB.DOOR2[0] + OX     # 328..364
WIN_Y, WIN_W, WIN_H = FB.WIN_Y + OY, FB.WIN_W, FB.WIN_H     # 140..168
WINS = [x + OX for x in FB.WINS[:5]] + [382, 428, 474]      # 前五扇和闪回一样，第二扇门后面接着排
BELT_Y = FB.BELT + OY
POLES = [78, 370]
SEATS = [96, 160, 224, 288, 378, 442]                       # 椅背左边；288 = 空座位（train_seat 305）
EMPTY_SEAT = 288
SEAT_BEAM = 4                                               # 空座位上的太阳从第几扇窗来
CUSHION_Y = 192                                             # 座垫上沿
BACK_TOP = WIN_Y + WIN_H - 7                                # 椅背顶：闪回从窗外看到的「窗底 7 行是靠背」
SUN = (96, 66)
SUN_DX = 0.5
TRAIN_SEAT_X, TRAIN_DOOR_X = 305, 52
WARM = (255, 204, 138)


def hx(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def col(c, a=255):
    if isinstance(c, str):
        return hx(c, a)
    return tuple(c[:3]) + (a if len(c) < 4 else c[3],)


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
        a[y0:y1 + 1, x0:x1 + 1] = col(c)


def put(a, x, y, c):
    hh, ww = a.shape[:2]
    if 0 <= x < ww and 0 <= y < hh:
        a[int(y), int(x)] = col(c)


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


def disc(cx, cy, r, w=W, h=H):
    yy, xx = np.mgrid[0:h, 0:w]
    return (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r + r * 0.6


def over(dst, src, x=0, y=0):
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


def add_light(dst, src, x=0, y=0, k=1.0):
    hh, ww = src.shape[:2]
    s = src.astype(float)
    d = dst[y:y + hh, x:x + ww].astype(float)
    d[..., :3] += s[..., :3] * (s[..., 3:4] / 255.0) * k
    dst[y:y + hh, x:x + ww, :3] = np.clip(d[..., :3] + 0.5, 0, 255).astype(np.uint8)
    return dst


def load(path):
    return np.array(Image.open(path).convert("RGBA"))


# ================================================================== 天空：作者的 sky.png + 雾里一个淡的日轮（城里被楼挡着，出了城才看得到）
def sky():
    a = load(os.path.join(CITY, "sky.png")).copy()
    cx, cy = SUN
    for r, d in [(24, 5), (17, 10), (12, 18)]:
        m = disc(cx, cy, r)
        a[m, 0] = np.minimum(a[m, 0].astype(int) + d + 2, 255)
        a[m, 1] = np.minimum(a[m, 1].astype(int) + d + 1, 255)
        a[m, 2] = np.minimum(a[m, 2].astype(int) + d, 255)
    a[disc(cx, cy, 8)] = col((122, 122, 108))
    a[disc(cx, cy, 6)] = col((186, 180, 154))
    return a


# ================================================================== 出了城：雾里的远山（城市那套灰）
def far_land():
    a = new(TW)
    for x in range(TW):
        t = 2 * math.pi * x / TW
        h1 = 142 - 7 * math.sin(t * 2 + 0.6) - 3 * math.sin(t * 5 + 1.3) - 2 * math.sin(t * 9)
        h2 = 158 - 3 * math.sin(t * 3 + 2.0) - 2 * math.sin(t * 7 + 0.4)
        a[int(round(h1)):, x] = col((44, 53, 54))
        a[int(round(h1)), x] = col((62, 72, 72))
        a[int(round(h2)):, x] = col((27, 34, 35))
    return a


# ================================================================== 一排树：近黑偏冷，顶上一道雾光的冷边，枝丫露出来（不是圆球）
T_DARK, T_MID, T_LIT, T_RIM, T_TRUNK = (13, 18, 18), (20, 27, 27), (31, 40, 39), (76, 90, 88), (11, 14, 15)


def trees():
    a = new(TW)
    rng = random.Random(29)
    yy, xx = np.mgrid[0:H, 0:TW]
    x = 26
    while x < TW - 50:
        top = rng.randint(14, 44)
        spread = rng.randint(22, 36)
        base = rng.randint(92, 106)
        lean = rng.choice([-1, 1]) * rng.randint(0, 5)
        # 树干和几根枝：连着的线，从地上一直长进树冠
        rect(a, x - 1, base, x + 1, H - 1, T_TRUNK)
        blobs = []
        n = rng.randint(14, 19)
        for k in range(n):                             # 上窄下宽地叠很多团，连成一整棵，边上留几个小缺口
            t = k / max(1, n - 1)
            bx = x + lean + int(rng.uniform(-spread, spread) * (0.4 + 0.6 * math.sin(math.pi * min(1.0, t * 0.8 + 0.1))))
            by = int(top + (base - top - 10) * t + rng.randint(-4, 4))
            blobs.append((bx, by, rng.randint(10, 17), rng.randint(9, 14)))
        for (bx, by, _, _) in blobs[-5:]:
            for px, py in line_pts(x, min(base + 2, by + 18), bx, by):
                put(a, px % TW, py, T_TRUNK)
                put(a, (px + 1) % TW, py, T_TRUNK)
        cells = np.array([[rng.random() for _ in range(TW // 3 + 2)] for _ in range(H // 3 + 2)])
        lumpy = cells[yy // 3, xx // 3] * 0.5 - 0.22
        owner = np.full((H, TW), -1)
        best = np.full((H, TW), 9.0)
        for i, (bx, by, rx, ry) in enumerate(blobs):
            d = ((xx - bx) / rx) ** 2 + ((yy - by) / ry) ** 2 - lumpy
            m = (d <= 1.0) & (d < best)
            owner[m] = i
            best[m] = d[m]
        mask = owner >= 0
        ys, xs = np.nonzero(mask)
        for y, xp in zip(ys, xs):
            bx, by, rx, ry = blobs[owner[y, xp]]
            lit = -(0.3 * (xp - bx) / rx + 0.95 * (y - by) / ry)      # 光从背后上方来，和城里的人一样
            c = T_LIT if lit > 0.62 else (T_MID if lit > 0.05 else T_DARK)
            a[y, xp % TW] = col(c)
        for y, xp in zip(ys, xs):
            if y > 0 and not mask[y - 1, xp]:
                bx, by, rx, ry = blobs[owner[y, xp]]
                if -(0.3 * (xp - bx) / rx + 0.95 * (y - by) / ry) > 0.45:
                    a[y, xp % TW] = col(T_RIM)
        x += rng.randint(74, 116)
    return a


# ================================================================== 铁路边的路灯（作者城市的路灯：2 像素的杆、一条横臂、扁灯头、冷白的灯），跑得最快
def poles():
    a = new(W)
    dark = CA.mat(0.12, 0.006, CA.H_COOL, dL=0.03)
    lx, top = 300, 70
    rect(a, lx, top, lx + 2, H - 1, dark[2])
    rect(a, lx + 1, top, lx + 2, H - 1, dark[4])
    rect(a, lx, top, lx + 12, top + 1, dark[3])
    hx0 = lx + 10
    rect(a, hx0 - 4, top + 1, hx0 + 5, top + 4, dark[2])
    rect(a, hx0 - 4, top + 1, hx0 + 5, top + 2, dark[5])
    rect(a, hx0 - 3, top + 4, hx0 + 4, top + 5, CA.COLD_L(0.66, 0.02, 205))
    rect(a, hx0 - 2, top + 5, hx0 + 3, top + 6, CA.COLD_L(0.5, 0.02, 205))
    return a


# ================================================================== 高架桥面：近黑的湿面，零星几道伸缩缝（跟路灯一样快）
def deck():
    a = new(W)
    rect(a, 0, 259, W - 1, 259, C["skirt_hi"])
    rect(a, 0, 260, W - 1, H - 1, C["under"])
    for sx in (41, 157, 289, 398):
        rect(a, sx, 261, sx, H - 1, C["plat_lo"])
    return a


# ================================================================== 车厢（闪回那节车的剖面）
def wall_color(y):
    """车里：顶上一条灯，往下一档一档暗（整行一档，不抖）。和闪回 interior() 一个做法；晨身后那段（腰以下）压到最暗的两档"""
    if y < 146:
        return C["in_hi"]
    if y < 170:
        return C["in"]
    if y < 192:
        return C["in_lo"]
    return C["in_dk"]


def glass_holes():
    hs = []
    for x in WINS:
        hs.append((x, WIN_Y, min(x + WIN_W - 1, W - 1), WIN_Y + WIN_H - 1))
    for dx in (DOOR1_X, DOOR2_X):                # 两片门扇各一扇窄窗（train_door_l/r.png 里的位置）
        hs.append((dx + 3, DOOR_Y + 10, dx + 12, DOOR_Y + 45))
        hs.append((dx + 18 + 5, DOOR_Y + 10, dx + 18 + 14, DOOR_Y + 45))
    return hs


def cut_hole(a, x0, y0, x1, y1, frame=True):
    rect(a, x0, y0, x1, y1, (0, 0, 0, 0))
    if frame:
        for (cx, cy) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):      # 圆角：和闪回一样四个角各挖一格
            put(a, cx, cy, C["frame"])


def door(a, x):
    """门：和闪回 door_frame 一样的暗框、黑胶条、受光的唇边、门楣上关着的灯；门扇就是它的 PNG，窄窗挖空（里面看出去是窗外）"""
    y, w, h = DOOR_Y, DOOR_W, DOOR_H
    rect(a, x - 4, y - 4, x + w + 3, FLOOR - 2, C["frame"])
    rect(a, x - 2, y - 2, x + w + 1, FLOOR - 2, C["rubber"])
    rect(a, x - 4, y - 5, x + w + 3, y - 5, C["lip"])
    rect(a, x + w + 4, y - 4, x + w + 4, FLOOR - 2, C["lip"])
    rect(a, x + w // 2 - 3, y - 8, x + w // 2 + 2, y - 7, C["lamp_off"])
    for name, dx in (("train_door_l.png", 0), ("train_door_r.png", w // 2)):
        over(a, load(os.path.join(FLASH, name)), x + dx, y)
    rect(a, x - 4, FLOOR - 2, x + w + 3, FLOOR - 2, C["lip"])           # 门槛
    for (x0, y0, x1, y1) in glass_holes():
        if x <= x0 < x + w:
            cut_hole(a, x0, y0, x1, y1)


def seat(a, b):
    """朝右的座位（侧面）：闪回的 seat 色，靠背顶上受光（in_lo）。靠背顶 = 窗底往上 7 行，和从车外看到的一样"""
    for y in range(BACK_TOP, CUSHION_Y + 6):
        o = (y - BACK_TOP) // 11
        l, r = b + 1 + o, b + 7 + o
        rect(a, l, y, r, y, C["seat"])
        put(a, r, y, C["in_dk"])
    rect(a, b + 2, BACK_TOP, b + 7, BACK_TOP, C["in_lo"])
    rect(a, b + 1, BACK_TOP + 1, b + 8, BACK_TOP + 1, C["in_lo"])
    rect(a, b + 1, BACK_TOP + 2, b + 1, BACK_TOP + 4, C["in_lo"])
    x1 = b + 36
    # 座垫比后面那段墙（in_dk）暗一档才读得出来：身子 strap、上沿两行 seat + in_lo、前沿一道受光
    rect(a, b + 8, CUSHION_Y, x1, CUSHION_Y + 6, C["strap"])
    rect(a, b + 8, CUSHION_Y, x1 - 1, CUSHION_Y, C["in_lo"])
    rect(a, b + 8, CUSHION_Y + 1, x1 - 1, CUSHION_Y + 1, C["seat"])
    rect(a, x1, CUSHION_Y + 1, x1, CUSHION_Y + 5, C["seat"])
    put(a, x1, CUSHION_Y, wall_color(CUSHION_Y))
    put(a, x1, CUSHION_Y + 6, wall_color(CUSHION_Y + 6))
    rect(a, b + 16, CUSHION_Y + 7, b + 19, 225, C["strap"])             # 底座
    rect(a, b + 16, CUSHION_Y + 7, b + 16, 225, C["seat"])
    rect(a, b + 12, 225, b + 23, 226, C["strap"])


def car():
    a = new()
    fb = load(os.path.join(FLASH, "train_car.png"))
    # 车顶：直接取闪回那节车的像素（设备箱也是它的），去掉两头的圆角，接着铺
    strip = fb[:FB.ROOF, 8:392]
    for x in range(-40, W, strip.shape[1]):
        over(a, strip, x, ROOF)
    # 墙：一行一档
    for y in range(CEIL, 227):
        rect(a, 0, y, W - 1, y, wall_color(y))
    rect(a, 0, CEIL + 1, W - 1, CEIL + 1, C["in_lamp"])
    rect(a, 0, RAIL_Y, W - 1, RAIL_Y, C["in_dk"])                       # 吊环的横杆，和闪回一样在灯下面第四行
    # 腰带：车身外面那道青灰，里面也走一圈（一样的高度）
    rect(a, 0, BELT_Y, W - 1, BELT_Y + 2, C["belt"])
    rect(a, 0, BELT_Y, W - 1, BELT_Y, C["belt_hi"])
    # 竖的板缝：闪回那几道的位置，只比旁边暗一档
    for sx in (FB.DOOR[0] - 8 + OX, 160 + OX, 252 + OX, 366 + OX):
        for y in range(CEIL + 6, 226):
            if WIN_Y - 3 <= y <= WIN_Y + WIN_H + 2 and any(w - 3 <= sx <= w + WIN_W + 3 for w in WINS):
                continue
            if BELT_Y <= y <= BELT_Y + 2:
                continue
            c = wall_color(y)
            put(a, sx, y, tuple(int(v * 0.86) for v in c))
    # 窗：和闪回 window() 一样的黑框、上沿和右边一道受光
    for x in WINS:
        rect(a, x - 2, WIN_Y - 2, x + WIN_W + 1, WIN_Y + WIN_H + 1, C["frame"])
        rect(a, x - 2, WIN_Y - 3, x + WIN_W + 1, WIN_Y - 3, C["lip"])
        rect(a, x + WIN_W + 2, WIN_Y - 2, x + WIN_W + 2, WIN_Y + WIN_H + 1, C["lip"])
        rect(a, x - 2, WIN_Y + WIN_H + 2, x + WIN_W + 2, WIN_Y + WIN_H + 2, C["in_hi"])   # 窗台被灯照亮
        cut_hole(a, x, WIN_Y, min(x + WIN_W - 1, W - 1), WIN_Y + WIN_H - 1)
    door(a, DOOR1_X)
    door(a, DOOR2_X)
    # 第三节车厢的牌子：门左边墙上，车身的灰底，字是暗的
    rect(a, 11, 148, 25, 161, C["body"])
    rect(a, 11, 148, 25, 148, C["rim"])
    rect(a, 25, 149, 25, 161, C["body_hi"])
    rect(a, 11, 161, 25, 161, C["body_lo"])
    for (gx, gy) in [(16, 151), (17, 151), (18, 151), (19, 151), (20, 151), (20, 152), (20, 153), (20, 154),
                     (18, 154), (19, 154), (20, 155), (20, 156), (20, 157), (16, 158), (17, 158), (18, 158),
                     (19, 158), (20, 158)]:
        put(a, gx, gy, C["roof_hi"])
    # 扶杆：闪回的杆子色（上接横杆、下到地板）
    for px in POLES:
        rect(a, px, CEIL + 2, px, 226, C["pole"])
        rect(a, px + 1, CEIL + 2, px + 1, 226, C["in_lo"])
        rect(a, px - 1, 225, px + 2, 226, C["in_lo"])
    for b in SEATS:
        seat(a, b)
    # 地板：闪回的 in_dk，上沿 in_lo；再往下是切开的车身断面
    rect(a, 0, 227, W - 1, 235, C["in_dk"])
    rect(a, 0, 227, W - 1, 227, C["in_lo"])
    rect(a, 0, 235, W - 1, 235, C["lip"])
    for (sx, sy, sl) in [(140, 231, 9), (262, 233, 6), (437, 230, 7)]:   # 磨痕：零星、暗一档
        rect(a, sx, sy, sx + sl, sy, C["strap"])
    for (fx, fy) in [(84, 231), (94, 233), (106, 231)]:                   # 门口进来的湿脚印（外面的雨）
        rect(a, fx, fy, fx + 2, fy, C["strap"])
    # 第五个座位旁边靠着一把收起来的湿伞（和城里那种黑伞一个颜色），底下一小摊水
    b = 378 + 54
    for y in range(190, 226):
        k = (y - 190) // 12
        rect(a, b + (y - 190) // 12, y, b + 3 - k + (y - 190) // 12, y, C["body_dk"])
    rect(a, b, 190, b, 208, C["body_lo"])
    rect(a, b + 3, 226, b + 3, 226, C["body_dk"])
    rect(a, b - 2, 186, b + 1, 186, C["body_hi"])                        # 弯把
    put(a, b - 2, 187, C["body_hi"])
    put(a, b + 1, 187, C["body_hi"])
    put(a, b + 1, 188, C["body_hi"])
    put(a, b + 1, 189, C["body_hi"])
    rect(a, b - 2, 228, b + 9, 228, C["far_hi"])
    rect(a, b - 1, 229, b + 7, 229, C["far"])
    put(a, b + 4, 228, C["lip"])
    # 车下：断面、裙板和底架（直接取闪回那节车的像素，车轮藏在里面）、钢轨
    rect(a, 0, 236, W - 1, 239, C["body_dk"])
    rect(a, 0, 236, W - 1, 236, C["seam"])
    under = fb[FB.SKIRT:FB.PLAT, 8:392]
    for x in range(-40, W, under.shape[1]):
        over(a, under, x, 240)
    rect(a, 0, 240 + under.shape[0], W - 1, 256, C["under"])
    rect(a, 0, 257, W - 1, 257, C["lip"])
    rect(a, 0, 258, W - 1, 258, C["plat_lo"])
    # 湿桥面上车窗的暖光倒影：很暗的几条竖的（城里街面就是这样）
    for x in WINS:
        for (y0, y1, ins, al) in ((260, 263, 0, 90), (264, 266, 5, 60), (267, 269, 11, 34)):
            rect(a, x + ins, y0, min(x + WIN_W - 1 - ins, W - 1), y1, col(C["in_dk"], al))
    return a


# ================================================================== 玻璃：闪回 window() 的斜反光（从右上往左下）+ 雨留下的水珠
def glass():
    a = new()
    rng = random.Random(3)
    gl = C["glare"]
    for i, (x0, y0, x1, y1) in enumerate(glass_holes()):
        w, h = x1 - x0 + 1, y1 - y0 + 1
        k = 6 + ((i + 3) * 7) % 12
        for t in range(h):
            gy = y1 - t
            if gy <= y0 + 2:
                continue
            for gx in (x0 + k + t, x0 + k + t + 1, x0 + k + t + 8):
                if x0 < gx < x1:
                    a[gy, gx] = col(gl, 86)
        if w < 12:
            continue
        for _ in range(rng.choice([0, 1, 1, 2])):        # 车在开：水珠被风吹得往后、往下，身后拖一道斜痕（连着的线）
            dx = rng.randint(x0 + 2, max(x0 + 2, x1 - 12))
            dy = rng.randint(y0 + 8, y1 - 3)
            tl = rng.randint(4, 9)
            for (px, py) in line_pts(dx, dy, dx + tl, dy - tl // 2)[1:]:
                if x0 <= px <= x1 and y0 <= py <= y1:
                    a[py, px] = (170, 182, 182, 54)
            a[dy, dx] = (205, 214, 212, 150)
    return a


# ================================================================== 乘客：城市街上的兜帽人（city_art.person_frame，灰度档）
HH = 94
LO, HI, RIM_, GLOW = (5, 7, 8), (64, 67, 73), (146, 146, 140), (97, 125, 134)     # CrowdMid 的一段，车里灯亮，hi、rim 抬一点
STEPS = [40, 58, 76, 94, 112, 130, 148, 166]
NFR = 16


def sway(f, phase=0.0, amp=0.75):
    return int(round(amp * math.sin(2 * math.pi * f / NFR + phase)))


def ramp_rgba(g):
    """灰度档 → 颜色：scripts/city_crowd_ramp.gdshader 的公式"""
    out = np.zeros(g.shape[:2] + (4,), np.uint8)
    on = g[..., 3] > 0
    v = g[..., 0].astype(float)
    lo, hi, rm, gw = (np.array(c, float) for c in (LO, HI, RIM_, GLOW))
    t = np.clip((v - 30.0) / 146.0, 0, 1)[..., None]
    c = lo + (hi - lo) * t
    c[v > 190] = hi + (rm - hi) * 0.5
    c[v > 225] = gw
    c[v > 248] = rm
    out[..., :3] = np.clip(c + 0.5, 0, 255).astype(np.uint8)
    out[..., 3] = np.where(on, 255, 0)
    return out


def stand_frame(type_i, hh=HH):
    im, fw = CA.person_frame(hh, CA.HOOD_TYPES[type_i], 0.0, stand=True)
    return im.copy()


def seated_figure(type_i):
    """坐着的人（灰度档）：腰以上取城市人物的站姿，腿照同样的灰度档补：大腿往前平放，大衣下摆盖到小腿，鞋。
    返回 (图, 坐骨在图里的 (x, y))"""
    tp = CA.HOOD_TYPES[type_i]
    hh = HH
    st = stand_frame(type_i)
    fw = st.shape[1]
    H_ = hh * tp["s"]
    cx = int(fw * 0.47)
    hip = int(round(hh - (1 - tp["hip"]) * H_))
    cw = fw + 44
    legs_h = FLOOR - CUSHION_Y + 2
    g = np.zeros((hip + legs_h + 2, cw, 4), np.uint8)
    # 大腿（大衣盖着）：从胯往前，上沿受光
    knee = cx + 21
    thigh = pmask([(cx - 4, hip - 12), (cx + 8, hip - 11), (knee, hip - 9), (knee + 5, hip - 6), (knee + 5, hip + 1),
                   (cx - 4, hip + 1)], cw, g.shape[0])
    # 小腿外面的大衣下摆，再往下一小截小腿、鞋
    y_floor = hip + (FLOOR - CUSHION_Y)
    hem = hip + int((FLOOR - CUSHION_Y) * 0.74)       # 长大衣盖到小腿，只露一小截小腿和鞋（作者：腿不能细）
    coat = pmask([(knee - 8, hip - 7), (knee + 5, hip - 7), (knee + 7, hip + 6), (knee + 9, hem), (knee + 2, hem + 1),
                  (knee - 10, hem), (knee - 9, hip + 3)], cw, g.shape[0])
    shin = pmask([(knee - 4, hem), (knee + 3, hem), (knee + 3, y_floor - 3), (knee - 4, y_floor - 3)], cw, g.shape[0])
    shoe = pmask([(knee - 5, y_floor - 3), (knee + 4, y_floor - 3), (knee + 11, y_floor - 1), (knee + 11, y_floor),
                  (knee - 5, y_floor)], cw, g.shape[0])

    def paint(m, v):
        g[m] = (v, v, v, 255)
    paint(shin, STEPS[1])
    paint(shoe, STEPS[1])
    top = shoe & ~np.roll(shoe, 1, 0)
    paint(top, STEPS[4])
    ys, xs = np.nonzero(coat)
    for y, x in zip(ys, xs):
        k = (y - (hip - 2)) / max(1, hem - hip + 2)
        v = STEPS[3] if k < 0.25 else (STEPS[2] if k < 0.7 else STEPS[1])
        g[y, x] = (v, v, v, 255)
    ys, xs = np.nonzero(thigh)
    for y, x in zip(ys, xs):
        k = (y - (hip - 12)) / 13.0
        v = STEPS[5] if k < 0.3 else (STEPS[4] if k < 0.6 else STEPS[3])
        g[y, x] = (v, v, v, 255)
    # 斜的衣褶：一道暗楔、朝光那侧亮一档
    for (p, q) in (((cx + 8, hip - 8), (knee - 2, hip)), ((knee - 3, hip + 5), (knee - 6, hem - 1)),
                   ((knee + 3, hip + 8), (knee + 4, hem - 1))):
        for x, y in line_pts(*p, *q):
            if g[y, x, 3]:
                g[y, x] = (STEPS[0],) * 3 + (255,)
                if g[y - 1, x, 3]:
                    g[y - 1, x] = (STEPS[4],) * 3 + (255,)
    # 大腿上沿：轮廓光 / 湿的反光（朝上的边）
    up = np.zeros_like(thigh)
    up[1:] = thigh[:-1]
    edge = thigh & ~up
    for y, x in zip(*np.nonzero(edge)):
        v = 255 if x < cx + 16 else 200
        g[y, x] = (v, v, v, 255)
    # 上半身盖在上面
    upper = st[:hip + 2]
    m = upper[..., 3] > 0
    g[:hip + 2, :fw][m] = upper[m]
    # 拿拐杖的那位：拐杖接到地上
    if tp["item"] == "cane":
        row = np.nonzero((upper[hip + 1, :, 0] == STEPS[5]) & (upper[hip + 1, :, 3] > 0))[0]
        x0 = int(row.max()) if row.size else knee
        for px, py in line_pts(x0, hip + 1, knee + 13, y_floor):
            g[py, px] = (STEPS[5],) * 3 + (255,)
    return g, (cx, hip)


# 哪个座位坐谁：HOOD_TYPES 的序号（1 长斗篷看手机、4 驼背拐杖、7 缩肩看手机、0 立领看表、5 抱纸箱）
SEATED = [(96, 1), (160, 4), (224, 7), (378, 0), (442, 5)]
STANDING = [(92, 3, 0.4), (346, 6, 2.1)]               # (x, 种类, 晃的相位)：门边站着的两个（公文包、背包）
P_Y0, P_H = 128, 104
_people = {}


def passengers_frame(f):
    a = new()
    if not _people:
        _people["seat"] = [seated_figure(t) for (_, t) in SEATED]
        _people["stand"] = [stand_frame(t) for (_, t, _) in STANDING]
    for (b, t), (g, (cx, hip)) in zip(SEATED, _people["seat"]):
        fig = g.copy()
        if CA.HOOD_TYPES[t]["item"] == "cane" and f in (5, 6, 13):     # 打瞌睡的头点一下
            r = int(HH * 0.17)
            fig[:r] = np.roll(fig[:r], 1, 1)
        scr = fig[..., 0] == 240
        if scr.any() and f % 8 in (3, 4):                               # 屏幕上划一下：一行暗下去
            ys, xs = np.nonzero(scr)
            fig[ys.min(), xs[ys == ys.min()]] = (STEPS[1],) * 3 + (255,)
        over(a, ramp_rgba(fig), b + 20 - cx, CUSHION_Y - hip)
    for (x, t, ph), g in zip(STANDING, _people["stand"]):
        over(a, ramp_rgba(g), x + sway(f, ph) - g.shape[1] // 2, 227 - g.shape[0] + 1)
    return a[P_Y0:P_Y0 + P_H]


# ================================================================== 吊环：闪回 interior() 的样子（一根带、一个小环，环中间透光），跟着车晃
STRAPS = [90, 108, 128, 150, 168, 192, 214, 232, 258, 276, 298, 320, 384, 402, 424, 446, 466]
S_Y0, S_H = RAIL_Y + 1, 14


def straps_frame(f):
    a = new(W, S_H)
    for k, sx in enumerate(STRAPS):
        d = sway(f, k * 0.9 + (0.0 if k % 2 else 0.5))
        for yy in range(0, 3):
            put(a, sx, yy, C["strap"])
        for yy in range(3, 6):
            put(a, sx + d, yy, C["strap"])
        if d != 0:
            put(a, sx + d, 2, C["strap"])                # 拐弯处边相邻
        rect(a, sx + d - 1, 6, sx + d + 1, 8, C["strap"])
        put(a, sx + d, 7, C["in_hi"])                    # 环中间透光
    return a


# ================================================================== 光束（加法，每扇窗一张）：照在座垫、地板上；人挡住的地方只剩三分之一
def beam(x0, x1, top, bot):
    a = new()
    poly = [(x0, top), (x1, top), (x1 + (FLOOR - 1 - top) * SUN_DX, FLOOR - 1),
            (x0 + (FLOOR - 1 - bot) * SUN_DX, FLOOR - 1), (x0, bot)]
    m = pmask(poly)
    m[:bot + 3, :] = False                             # 玻璃、窗台上不加
    a[m] = WARM + (11,)
    for sb in SEATS:
        for x in range(sb + 8, sb + 36):
            if m[CUSHION_Y, x]:
                a[CUSHION_Y, x] = WARM + (56,)
                if sb == EMPTY_SEAT:                   # 空座位：太阳落在整个座垫上面（剧本：落在靠窗的空座位上）
                    a[CUSHION_Y, x] = WARM + (96,)
                    a[CUSHION_Y + 1, x] = WARM + (60,)
                    a[CUSHION_Y + 2, x] = WARM + (30,)
    fl0 = int(round(x0 + (FLOOR - 1 - bot) * SUN_DX))
    fl1 = int(round(x1 + (FLOOR - 1 - top) * SUN_DX))
    for y in range(227, 235):
        o = (y - 227) // 2
        for x in range(fl0 + o, fl1 + o + 1):
            if 0 <= x < W:
                a[y, x] = WARM + (40,)
    for (b, _) in SEATED:
        for y in range(WIN_Y + WIN_H + 2, 235):
            s0 = b + 10 + int((y - WIN_Y - WIN_H) * SUN_DX)
            s1 = b + 50 + int((y - WIN_Y - WIN_H) * SUN_DX)
            for x in range(max(s0, 0), min(s1, W)):
                a[y, x, 3] = a[y, x, 3] // 3
    ys, xs = np.nonzero(a[..., 3])
    if len(xs) == 0:
        return None, None, None
    bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max(), ys.max()
    return a[by0:by1 + 1, bx0:bx1 + 1], (int(bx0), int(by0)), (fl0, fl1 + 4)


def knees():
    a = new(26, 24)
    for y in range(24):
        for x in range(26):
            u = x - y * SUN_DX * 0.6
            if 2 <= u <= 21:
                core = 6 <= u <= 17 and 4 <= y <= 19
                a[y, x] = WARM + (66 if core else 30,)
    return a


KNEES_AT = (TRAIN_SEAT_X - 13, 201)


def occlusion(img, rows):
    al = img[rows[0]:rows[1] + 1, :, 3] > 0
    return [1 if al[:, x].any() else 0 for x in range(img.shape[1])]


def solid(img):
    """每一列有没有楼：作者的层里有几行是横穿整张图的（高架、雾带），所以按「这一列大部分是不透明的」算"""
    return [1 if (img[:, x, 3] > 0).mean() > 0.25 else 0 for x in range(img.shape[1])]


def save(a, name):
    Image.fromarray(a, "RGBA").save(os.path.join(OUT, name))


def main():
    os.makedirs(OUT, exist_ok=True)
    L = {"sky": sky(), "far_land": far_land(), "trees": trees(), "poles": poles(), "deck": deck(),
         "car": car(), "glass": glass()}
    for k, v in L.items():
        save(v, k + ".png")
    save(np.concatenate([passengers_frame(f) for f in range(NFR)], axis=1), "passengers.png")
    save(np.concatenate([straps_frame(f) for f in range(NFR)], axis=1), "straps.png")
    save(np.zeros((1, 1, 4), np.uint8), "empty.png")
    save(knees(), "knees.png")
    for old in ("far_city", "mid", "near", "beam_door0", "beam_door1", "beam_door2", "beam_door3") + \
            tuple("beam_%d" % i for i in range(12)):
        for ext in (".png", ".png.import"):
            p = os.path.join(OUT, old + ext)
            if os.path.exists(p):
                os.remove(p)
    beams = []
    for i, x in enumerate(WINS):
        img, at, flr = beam(x, min(x + WIN_W - 1, W - 1), WIN_Y + 1, WIN_Y + WIN_H - 1)
        if img is None:
            continue
        save(img, "beam_%d.png" % i)
        beams.append({"img": "beam_%d.png" % i, "at": list(at), "win": x + WIN_W // 2, "floor": list(flr)})
    city = {n: load(os.path.join(CITY, n + ".png")) for n in ("midfar", "mid")}
    data = {"_note": "tools/home_train_art.py 生成。occ_*：窗外层每一列挡不挡太阳（1 = 挡）；solid_*：这一列有没有楼（0 = 楼缝，出城从这里断开）。",
            "beams": beams, "seat_beam": SEAT_BEAM, "knees_at": list(KNEES_AT),
            "occ_mid": occlusion(city["mid"], (50, 58)), "occ_midfar": occlusion(city["midfar"], (60, 70)),
            "occ_trees": occlusion(L["trees"], (60, 80)),
            "solid_mid": solid(city["mid"]), "solid_midfar": solid(city["midfar"])}
    with open(os.path.join(OUT, "occlusion.json"), "w") as fp:
        json.dump(data, fp, ensure_ascii=False, separators=(",", ":"))
    print("wrote", OUT, "beams", len(beams))
    if "--preview" in sys.argv:
        d = sys.argv[sys.argv.index("--preview") + 1]
        os.makedirs(d, exist_ok=True)
        for name, phase, cx, f, s in (("city", "city", TRAIN_SEAT_X, 0, 140), ("trees", "trees", TRAIN_SEAT_X, 4, 300),
                                      ("door", "city", TRAIN_DOOR_X, 6, 500)):
            a = compose(phase, cx, phase == "trees", f, s)
            Image.fromarray(a).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(d, "home_train_%s_2x.png" % name))
    if "--compare" in sys.argv:
        compare(sys.argv[sys.argv.index("--compare") + 1], sys.argv[sys.argv.index("--before") + 1])


def chen_frame(i=7):
    return load(os.path.join(ROOT, "art/characters/chen/chen_oscar.png"))[:, i * 68:(i + 1) * 68]


def tile(img, off):
    w = img.shape[1]
    t = np.concatenate([img, img], axis=1)
    off %= w
    return t[:, off:off + W]


def compose(phase, chen_x, knees_on, f=0, s=140):
    """Python 拼一帧（和 home_train.gd 的层序一样）。s = 总平移（像素，近似「走了多远」）"""
    out = load(os.path.join(OUT, "sky.png")).copy()
    if phase == "city":
        for n, k in (("ridge", 0.06), ("far", 0.18), ("midfar", 0.38), ("mid", 0.62)):
            over(out, tile(load(os.path.join(CITY, n + ".png")), int(s * k)))
    else:
        over(out, tile(load(os.path.join(OUT, "far_land.png")), int(s * 0.06)))
        over(out, tile(load(os.path.join(OUT, "trees.png")), int(s * 1.2)))
    over(out, tile(load(os.path.join(OUT, "poles.png")), int(s * 2.4)))
    over(out, tile(load(os.path.join(OUT, "deck.png")), int(s * 2.4)))
    over(out, load(os.path.join(OUT, "car.png")))
    over(out, load(os.path.join(OUT, "glass.png")))
    data = json.load(open(os.path.join(OUT, "occlusion.json")))
    for bm in data["beams"]:
        add_light(out, load(os.path.join(OUT, bm["img"])), *bm["at"])
    st = load(os.path.join(OUT, "straps.png"))
    fw = st.shape[1] // NFR
    over(out, st[:, f * fw:(f + 1) * fw], 0, S_Y0)
    pp = load(os.path.join(OUT, "passengers.png"))
    fw = pp.shape[1] // NFR
    over(out, pp[:, f * fw:(f + 1) * fw], 0, P_Y0)
    if chen_x is not None:
        over(out, chen_frame(), chen_x - 28, FLOOR - 56)
    if knees_on:
        add_light(out, knees(), *KNEES_AT)
    return out


def reference():
    """闪回参考（Python 拼，不是截图）：作者的城市层 + 追逐段那节车 + 街上的兜帽人 + 晨"""
    global LO, HI, RIM_
    out = load(os.path.join(CITY, "sky.png")).copy()
    for n, k in (("ridge", 0.06), ("far", 0.18), ("midfar", 0.38), ("mid", 0.62)):
        over(out, tile(load(os.path.join(CITY, n + ".png")), int(140 * k)))
    main_l = load(os.path.join(CITY, "main.png"))
    over(out, main_l[111:270, :W], 0, 111)
    fb = load(os.path.join(FLASH, "train_car.png"))
    over(out, fb, 150, 100)
    for dx, name in ((0, "train_door_l.png"), (18, "train_door_r.png")):
        over(out, load(os.path.join(FLASH, name)), 150 + 24 + dx, 122)
    saved = LO, HI, RIM_
    LO, HI, RIM_ = (0, 1, 1), (54, 56, 60), (114, 117, 121)      # 街上 CrowdMid 的值
    for x, t in ((58, 1), (108, 7), (440, 3)):
        g = stand_frame(t, 100)
        over(out, ramp_rgba(g), x - g.shape[1] // 2, 227 - 99)
    LO, HI, RIM_ = saved
    over(out, chen_frame(), 44, 172)
    return out


def compare(path, before):
    """改前 / 改后 / 闪回参考三张并排（每张 2 倍），改后出城那张放在下面一行"""
    font = None
    for fp in ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"):
        if os.path.exists(fp):
            font = ImageFont.truetype(fp, 26)
            break
    a0 = Image.open(before).convert("RGB")
    a1 = Image.fromarray(compose("city", TRAIN_SEAT_X, False, 0, 140)).convert("RGB").resize((W * 2, H * 2), Image.NEAREST)
    a2 = Image.fromarray(compose("trees", TRAIN_SEAT_X, True, 4, 300)).convert("RGB").resize((W * 2, H * 2), Image.NEAREST)
    a3 = Image.fromarray(reference()).convert("RGB").resize((W * 2, H * 2), Image.NEAREST)
    gap, head = 12, 44
    canvas = Image.new("RGB", (W * 2 * 3 + gap * 4, (H * 2 + head) * 2 + gap * 3), (18, 18, 20))
    dr = ImageDraw.Draw(canvas)
    for i, (im, label) in enumerate(((a0, "改前（作者试玩的那版）"), (a1, "改后：城里（作者的楼 + 追逐那节车的剖面 + 城里的人）"),
                                     (a3, "闪回参考（Python 拼：城市层 + 追逐那节车 + 街上的人）"))):
        x = gap + i * (W * 2 + gap)
        dr.text((x, gap), label, fill=(226, 226, 220), font=font)
        canvas.paste(im, (x, gap + head))
    x = gap + (W * 2 + gap)
    y2 = gap * 2 + head + H * 2
    dr.text((x, y2), "改后：出城（trees_passing，膝上有太阳）", fill=(226, 226, 220), font=font)
    canvas.paste(a2, (x, y2 + head))
    canvas.save(path)
    print("compare", path)


if __name__ == "__main__":
    main()
