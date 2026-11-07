#!/usr/bin/env python3
"""大象那张纸的背面：星球航线图（art/forest_story/paper_map.png，190×110，paper_view.gd 翻面显示，放大 2 倍）。

11-06 作者：「大象背后的地图不应该是简笔画，而是不同星球的地图，森林星、河流星、母星、芦苇之类的，全部加上。」
正面（drawing_closeup.png，妹妹画的大象）不动。

- 纸 = 正面那张纸左右镜像（elephant_drawing_art.paper()），折痕、折角、深浅都在一个位置；颜料乘纸色，折痕从星球上穿过去。
- 五颗星：母星（灰色鸽子笼 + 高架列车）→ 森林星（一层层树冠、雾带、树屋一点灯）→ 绕开碎石带 → 河流星（月夜水道、石桥、黄灯）
  → 云层星（云海、云上的大象，云海里立着小镇的紫色尖塔）→ 分叉点分三路：小镇（就在云层星上）/ 芦苇星（亮色湿地、大蒲公英）/ 沿纸底回母星。
  11-07 作者：「小镇我以为属于云层星」→ 小镇不再单独成星；「芦苇地为什么不叫 xx 星」→ 芦苇星（占位名，等作者定）。配色取自各章场景。
- 航线红褐虚线（和驾驶舱里那张小航图 cockpit_map 同色）；被碎石封住的旧航线是铅笔细线，打了个叉（飞行一「旧航线中断」）。
- 地名不画进图里，由 paper_view.gd 用游戏字体叠上去（中英文跟设置走），坐标见 LABELS（和 paper_view.gd 的 BACK_LABELS 保持一致）。

用法：python tools/paper_map_art.py [--preview 目录] [--cockpit]
  --preview  存 4 倍图（只有图 / 叠上地名），不用开游戏
  --cockpit  顺带重出驾驶舱的小航图 art/cockpit/cockpit_map.png（tools/cockpit_final_art.py 的 travel_map）
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import elephant_drawing_art as eda  # noqa: E402  只借 paper()

OUT = ROOT / "art/forest_story/paper_map.png"
HAND = ROOT / "art/手改清单.json"
W, H = 190, 110

INK = (58, 70, 140)          # 和正面大象同一支蓝圆珠笔
INK_D = (40, 48, 104)
ROUTE = (122, 66, 50)
ROUTE_D = (92, 48, 38)
PENCIL = (136, 128, 116)
REF = np.array([206.0, 197.0, 178.0])    # 颜料「乘纸色」的基准：纸的中间一档，浅的一片颜料亮一点，暗的一片暗一点

# 星球：cx, cy, r（11-07 作者：小镇在云层星上，不单独成星；芦苇地是一颗独立的星）
HOME = (26, 80, 15)
FOREST = (58, 40, 19)
RIVER = (101, 72, 19)
CLOUD = (149, 34, 20)
REED = (163, 80, 16)
FORK = (149, 58)             # 云层星底下的分叉点：小镇（就在云层星上）/ 芦苇星 / 回母星
TOWN_TAG = (179, 41)         # 「小镇」地名：在云层星右边，一条短点线引到云上的尖塔

# 地名（paper_view.gd 的 BACK_LABELS 同步）：中心 x、上沿 y，纸上坐标（游戏里 ×2）
# 「芦苇星」是占位名，等作者定了再换字
LABELS = [
    ("母星", "Home", 26, 97),
    ("森林星", "Forest", 58, 3),
    ("河流星", "River", 101, 93),
    ("云层星", "Clouds", 149, 5),
    ("小镇", "Town", 179, 37),
    ("芦苇星", "Reeds", 163, 98),
]


class Cv:
    """纸上的画布。颜料乘纸色；clip 给了就只画在这个遮罩里。"""

    def __init__(self):
        self.P = eda.paper()[:, ::-1].astype(float)
        self.rgb = self.P[..., :3].copy()
        self.alpha = self.P[..., 3].copy()
        self.tone = self.P[..., :3] / REF
        self.clip = None

    def px(self, x, y, col, k=1.0):
        x, y = int(round(x)), int(round(y))
        if not (0 <= x < W and 0 <= y < H) or self.alpha[y, x] == 0:
            return
        if self.clip is not None and not self.clip[y, x]:
            return
        c = np.array(col, float) * self.tone[y, x]
        self.rgb[y, x] = self.rgb[y, x] * (1 - k) + np.clip(c, 0, 255) * k

    def rect(self, x, y, w, h, col, k=1.0):
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                self.px(xx, yy, col, k)

    def line(self, x0, y0, x1, y1, col, k=1.0):
        for x, y in line_pts(x0, y0, x1, y1):
            self.px(x, y, col, k)

    def blob(self, cx, cy, r, col):
        ri = int(r + 1)
        for y in range(-ri, ri + 1):
            for x in range(-ri, ri + 1):
                if x * x + y * y <= r * r + 0.5:
                    self.px(cx + x, cy + y, col)

    def image(self):
        out = np.zeros((H, W, 4), np.uint8)
        out[..., :3] = np.clip(self.rgb, 0, 255).round()
        out[..., 3] = self.alpha
        return Image.fromarray(out, "RGBA")


def line_pts(x0, y0, x1, y1):
    x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    e = dx + dy
    pts = []
    while True:
        pts.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return pts
        e2 = 2 * e
        if e2 >= dy:
            e += dy
            x0 += sx
        if e2 <= dx:
            e += dx
            y0 += sy


def bezier(p0, p1, p2, p3):
    """三次贝塞尔 → 1 像素路径（去掉 L 形拐角）。"""
    pts = []
    for i in range(240):
        t = i / 239
        u = 1 - t
        x = u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0]
        y = u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]
        q = (int(round(x)), int(round(y)))
        if not pts or pts[-1] != q:
            pts.append(q)
    out = []
    for i, q in enumerate(pts):
        if 0 < i < len(pts) - 1 and out:
            a, b = out[-1], pts[i + 1]
            if abs(a[0] - b[0]) == 1 and abs(a[1] - b[1]) == 1:
                continue
        out.append(q)
    return out


def disc_mask(cx, cy, r, seed):
    """手画的圆：半径带一点低频的抖。"""
    rng = np.random.default_rng(seed)
    a, b = rng.uniform(0, 6.28, 2)
    ys, xs = np.mgrid[0:H, 0:W]
    th = np.arctan2(ys - cy, xs - cx)
    rr = r + 0.55 * np.sin(2 * th + a) + 0.3 * np.sin(5 * th + b)
    return np.hypot(xs - cx, ys - cy) <= rr


def edge(mask):
    m = mask.copy()
    inner = m.copy()
    inner[1:] &= m[:-1]
    inner[:-1] &= m[1:]
    inner[:, 1:] &= m[:, :-1]
    inner[:, :-1] &= m[:, 1:]
    inner[0] = inner[-1] = False
    inner[:, 0] = inner[:, -1] = False
    return m & ~inner


def lit(cx, cy, r, x, y):
    """月光从右上来：-1（背光）～ 1（迎光）。"""
    nx, ny = (x - cx) / r, (y - cy) / r
    return nx * 0.62 - ny * 0.78


def ramp_px(ramp, v, x, y):
    """v 0..1 取色板，档和档之间窄窄一条棋盘格。"""
    f = max(0.0, min(0.999, v)) * (len(ramp) - 1)
    i = int(f)
    t = f - i
    if 0.38 < t < 0.62:
        return ramp[i + 1] if (x + y) % 2 == 0 else ramp[i]
    return ramp[i + 1] if t >= 0.62 else ramp[i]


def base_disc(cv, cx, cy, r, ramp, seed, gain=0.42, mid=0.5):
    mask = disc_mask(cx, cy, r, seed)
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):
        cv.px(x, y, ramp_px(ramp, mid + gain * lit(cx, cy, r, x, y), x, y))
    return mask


def finish_disc(cv, mask, cx, cy, r, rim=None):
    """边上一圈迎光的亮边 + 墨线。"""
    cv.clip = None
    e = edge(mask)
    if rim is not None:
        ee = edge(mask & ~e)
        ys, xs = np.nonzero(ee)
        for y, x in zip(ys, xs):
            if lit(cx, cy, r, x, y) > 0.72:
                cv.px(x, y, rim, 0.75)
    ys, xs = np.nonzero(e)
    for y, x in zip(ys, xs):
        cv.px(x, y, INK_D)


def crown(cv, x, y, r, ramp, cx, cy, R, rng):
    """一棵树冠：圆团，右上亮、左下暗，顶上几个亮点。"""
    ri = int(r + 1)
    for dy in range(-ri, ri + 1):
        for dx in range(-ri, ri + 1):
            if dx * dx + dy * dy <= r * r + 0.3:
                v = 0.42 + 0.34 * (dx * 0.62 - dy * 0.78) / r + 0.22 * lit(cx, cy, R, x + dx, y + dy)
                cv.px(x + dx, y + dy, ramp_px(ramp, v, x + dx, y + dy))
    cv.px(x + int(r * 0.4), y - int(r * 0.7), ramp[-1])


def conifer(cv, x, base, h, col, col2):
    for i in range(h):
        w = int((i + 2) * 0.42) if i % 3 else int((i + 2) * 0.28)
        cv.rect(x - w, base - h + i, 2 * w + 1, 1, col)
        if w > 0:
            cv.px(x + w, base - h + i, col2)


def draw_forest(cv):
    cx, cy, r = FOREST
    ramp = [(14, 34, 34), (22, 54, 48), (34, 78, 62), (56, 106, 76), (98, 142, 96)]
    mask = base_disc(cv, cx, cy, r, ramp[:3], 3, gain=0.35, mid=0.35)
    cv.clip = mask
    rng = np.random.default_rng(11)
    # 一层层树冠（木星一样横着成带），后面的暗、前面的亮一点
    for row, yy in enumerate(range(cy - r + 3, cy + r + 2, 5)):
        off = rng.integers(0, 5)
        for xx in range(cx - r - 2 + off, cx + r + 3, 6):
            crown(cv, xx + rng.integers(-1, 2), yy + rng.integers(-1, 2), rng.choice([3, 3, 4]), ramp, cx, cy, r, rng)
        if row % 2 == 1:
            for xx in range(cx - r, cx + r, 3):                # 两层之间的深缝
                cv.px(xx + rng.integers(0, 2), yy + 3, ramp[0])
    # 雾带：一条横着的青灰雾，断断续续
    for dy, xa, xb, k in ((-3, -17, 6, 0.55), (-2, -9, 13, 0.7), (-1, 2, 18, 0.4), (9, -15, -2, 0.45), (10, -7, 9, 0.55)):
        for x in range(cx + xa, cx + xb):
            if (x * 3 + dy) % 7 != 0:
                cv.px(x, cy + dy, (160, 190, 172), k)
    # 树屋：一点暖灯
    cv.rect(cx + 6, cy + 3, 3, 2, (40, 34, 30))
    cv.px(cx + 7, cy + 2, (40, 34, 30))
    cv.px(cx + 7, cy + 3, (246, 196, 92))
    cv.px(cx + 7, cy + 5, (40, 34, 30))
    cv.px(cx + 7, cy + 6, (40, 34, 30))
    finish_disc(cv, mask, cx, cy, r, rim=(140, 176, 120))
    # 探出轮廓的几棵杉树（第一章那种高杉），才不像一个圆球
    for dx, dy, h in ((-13, -11, 9), (-8, -15, 8), (-2, -17, 9), (6, -17, 8)):
        conifer(cv, cx + dx, cy + dy + 1, h, (24, 54, 48), (56, 100, 76))


def draw_river(cv):
    cx, cy, r = RIVER
    land = [(14, 22, 44), (20, 32, 60), (32, 48, 80), (48, 70, 100)]
    mask = base_disc(cv, cx, cy, r, land, 5, gain=0.36, mid=0.42)
    cv.clip = mask
    # 水道：S 形一条大河 + 两条支流，岸边一行亮
    water = [(58, 92, 134), (86, 124, 164), (132, 168, 198)]
    main = bezier((cx - 22, cy - 7), (cx - 9, cy + 15), (cx + 5, cy + 7), (cx + 22, cy - 5))
    sub1 = bezier((cx - 14, cy), (cx - 9, cy - 7), (cx - 3, cy - 12), (cx - 1, cy - 21))
    sub2 = bezier((cx + 10, cy + 3), (cx + 11, cy + 8), (cx + 7, cy + 14), (cx + 8, cy + 21))
    for path, w in ((main, 3), (sub1, 1), (sub2, 1)):
        for x, y in path:
            for dy in range(-w, w + 1):
                for dx in range(-w, w + 1):
                    if dx * dx + dy * dy <= w * w:
                        cv.px(x + dx, y + dy, ramp_px(water, 0.45 + 0.28 * lit(cx, cy, r, x + dx, y + dy), x + dx, y + dy))
    for x, y in main[8::9]:                                   # 月光碎片
        cv.rect(x - 1, y, 3, 1, (222, 230, 240))
    # 石柱 + 黄灯（河岸月夜那种黄灯石像小镇）
    stone = (40, 54, 72)
    stone2 = (84, 104, 122)
    for dx, dy, h in ((-13, -7, 7), (-13, 12, 6), (-4, 15, 6), (6, -5, 8), (13, -8, 6), (14, 13, 5)):
        cv.rect(cx + dx, cy + dy - h, 2, h, stone)
        cv.rect(cx + dx + 1, cy + dy - h, 1, h, stone2)
        cv.px(cx + dx, cy + dy - h - 1, (246, 196, 92))
        cv.px(cx + dx + 1, cy + dy - h - 1, (250, 220, 130))
    # 南桥：一道石拱桥跨过大河（三个拱洞透出水）
    bx, by = cx - 2, cy + 3
    cv.rect(bx - 7, by - 1, 15, 1, (176, 186, 192))
    cv.rect(bx - 7, by, 15, 2, (112, 126, 140))
    for i in (-7, -2, 3, 7):
        cv.rect(bx + i, by + 2, 1, 3, (112, 126, 140))
        cv.px(bx + i + 1 if i < 7 else bx + i - 1, by + 2, (112, 126, 140))
        cv.px(bx + i - 1 if i > -7 else bx + i + 1, by + 2, (112, 126, 140))
    cv.rect(bx - 7, by - 2, 1, 1, (176, 186, 192))
    cv.rect(bx + 7, by - 2, 1, 1, (176, 186, 192))
    finish_disc(cv, mask, cx, cy, r, rim=(126, 156, 186))


def draw_home(cv):
    cx, cy, r = HOME
    sky = [(92, 94, 102), (118, 120, 126), (148, 150, 154), (172, 174, 176)]
    mask = base_disc(cv, cx, cy, r, sky, 7, gain=0.4, mid=0.55)
    cv.clip = mask
    rng = np.random.default_rng(21)
    # 雨：细斜线
    for _ in range(14):
        x, y = rng.integers(cx - r, cx + r), rng.integers(cy - r, cy + 3)
        cv.line(x, y, x - 1, y + 2, (196, 198, 200), 0.6)
    # 鸽子笼：后排浅、前排深，窗户一格一格，零星亮着
    for layer, (dark, lightc, wnd, step, hmin, hmax) in enumerate((
            ((96, 98, 106), (118, 120, 128), (72, 74, 82), 5, 14, 24),
            ((64, 66, 76), (88, 90, 100), (44, 46, 54), 6, 7, 17))):
        x = cx - r - 1
        while x < cx + r + 1:
            w = step + rng.integers(0, 2)
            h = rng.integers(hmin, hmax)
            top = cy + r - h
            cv.rect(x, top, w, h + 1, dark)
            cv.rect(x + w - 1, top, 1, h + 1, lightc)
            cv.rect(x, top, w, 1, lightc)
            for yy in range(top + 2, cy + r, 2):
                for xx in range(x + 1, x + w - 1, 2):
                    on = rng.random() < 0.07
                    cv.px(xx, yy, (232, 222, 170) if on else wnd)
            x += w
    # 高架：一道轨道 + 一节亮窗的车厢
    yy = cy + 5
    cv.rect(cx - r, yy, 2 * r + 1, 1, (38, 40, 48))
    for x in range(cx - r, cx + r, 8):
        cv.rect(x, yy + 1, 1, r, (46, 48, 56))
    cv.rect(cx - 6, yy - 3, 11, 3, (52, 54, 64))
    cv.rect(cx - 6, yy - 3, 11, 1, (120, 122, 130))
    for x in range(cx - 5, cx + 4, 2):
        cv.px(x, yy - 2, (236, 226, 176))
    finish_disc(cv, mask, cx, cy, r, rim=(206, 208, 208))


ELEPHANT = [
    "......XXXXXXXXXXXXX......",
    "....XXXXXXXXXXXXXXXXX....",
    "...XXXXXXXXXXXXXOOXXXXX..",
    "..XXXXXXXXXXXXXXOOOXXeXX.",
    "..XXXXXXXXXXXXXXOOOXXXXX.",
    ".XXXXXXXXXXXXXXXXOOXXXXXX",
    ".XXXXXXXXXXXXXXXXXXXXt.XX",
    ".X.XXXXXXXXXXXXXXXXX...XX",
    "...XXX..XXX.....XXX.XXX.X",
    "...XXX..XXX.....XXX.XXX..",
    "...XXX..XXX.....XXX.XXX..",
]


def draw_cloud(cv):
    cx, cy, r = CLOUD
    sky = [(112, 96, 156), (134, 116, 172), (156, 138, 186)]
    mask = base_disc(cv, cx, cy, r, sky, 9, gain=0.22, mid=0.45)
    cv.clip = mask
    rng = np.random.default_rng(31)
    for dx, dy in ((-11, -11), (-3, -18), (8, -16), (14, -10), (-14, -5)):
        cv.px(cx + dx, cy + dy, (236, 228, 218))
    # 云层里的大象：头朝右（和正面妹妹画的一样），身子埋在云里，颜色压成云影
    ex, ey = cx - 13, cy - 15
    for j, row in enumerate(ELEPHANT):
        for i, ch in enumerate(row):
            c = {"X": (52, 46, 88), "O": (94, 86, 128), "e": (236, 228, 218), "T": (52, 46, 88), "t": (236, 228, 214)}.get(ch)
            if c is not None:
                cv.px(ex + i, ey + j, c)
    for i, ch in enumerate(ELEPHANT[0]):                      # 背上一条迎光的边
        if ch == "X":
            cv.px(ex + i, ey, (128, 118, 160))
    for x_, y_ in ((ex + 18, ey), (ex + 20, ey + 1), (ex + 22, ey + 2), (ex + 23, ey + 3), (ex + 24, ey + 5)):
        cv.px(x_, y_, (128, 118, 160))
    # 云海：一排排云团，后面紫、前面亮奶油，迎光面高光
    cl = [(124, 106, 162), (160, 142, 186), (200, 184, 208), (234, 222, 222), (252, 246, 232)]
    for row, (yy, base, spread) in enumerate(((cy - 1, 0.2, 5), (cy + 3, 0.36, 6), (cy + 7, 0.52, 7), (cy + 12, 0.68, 7), (cy + 18, 0.82, 8))):
        if row == 4:
            draw_cloud_town(cv)                                # 小镇立在云海里：最前一排云盖住塔脚
        x = cx - r - 3 + rng.integers(0, 4)
        while x < cx + r + 4:
            rr = rng.integers(3, spread)
            ri = int(rr + 1)
            for dy in range(-ri, ri + 1):
                for dx in range(-ri, ri + 1):
                    if dx * dx + dy * dy <= rr * rr + 0.3:
                        v = base + 0.24 * (dx * 0.62 - dy * 0.78) / rr + 0.1 * lit(cx, cy, r, x + dx, yy + dy)
                        cv.px(x + dx, yy + dy, ramp_px(cl, v, x + dx, yy + dy))
            x += rr + rng.integers(2, 5)
    finish_disc(cv, mask, cx, cy, r, rim=(244, 236, 226))
    # 云漫出轮廓：左下、右边各鼓出几团，才不是一个圆球
    for x0, y0, rr in ((cx - 21, cy + 6, 3), (cx - 18, cy + 9, 4), (cx - 13, cy + 15, 3), (cx + 20, cy + 3, 3), (cx + 17, cy + 8, 4), (cx + 14, cy + 13, 3)):
        puff = np.zeros((H, W), bool)
        ys, xs = np.ogrid[:H, :W]
        puff[(xs - x0) ** 2 + (ys - y0) ** 2 <= rr * rr + 0.3] = True
        pys, pxs = np.nonzero(puff)
        for y, x in zip(pys, pxs):
            v = 0.62 + 0.3 * ((x - x0) * 0.62 - (y - y0) * 0.78) / rr
            cv.px(x, y, ramp_px(cl, v, x, y))
        eys, exs = np.nonzero(edge(puff))
        for y, x in zip(eys, exs):
            if not mask[y, x]:
                cv.px(x, y, INK_D)


def draw_reed(cv):
    cx, cy, r = REED
    mask = disc_mask(cx, cy, r, 13)
    cv.clip = mask
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):                                   # 天：亮蓝往下发白
        t = (y - (cy - r)) / (2 * r)
        c = (150, 204, 234) if t < 0.2 else (184, 222, 240) if t < 0.34 else (222, 240, 240)
        cv.px(x, y, c)
    # 远山
    for x in range(cx - r, cx + r + 1):
        h1 = 5.0 + 3.0 * math.sin((x - cx) * 0.35 + 1.0)
        h2 = 2.5 + 2.2 * math.sin((x - cx) * 0.52 + 3.2)
        for y in range(int(cy - h1), cy + 1):
            cv.px(x, y, (186, 212, 230))
        for y in range(int(cy + 1 - h2), cy + 1):
            cv.px(x, y, (206, 226, 232))
    # 水
    cv.rect(cx - r, cy + 1, 2 * r + 1, r, (150, 214, 204))
    cv.rect(cx - r, cy + 8, 2 * r + 1, r, (118, 194, 190))
    for dx, dy in ((-8, 3), (-1, 4), (6, 3), (-5, 10), (3, 11)):
        cv.rect(cx + dx, cy + dy, 3, 1, (232, 248, 240))
    # 芦苇丛：黄绿一撮撮，穗子亮黄
    rng = np.random.default_rng(41)
    for x0, base, n in ((-11, 6, 5), (-3, 8, 6), (6, 7, 5), (-7, 12, 5), (2, 13, 6)):
        for k in range(n):
            x = cx + x0 + k + rng.integers(-1, 2)
            h = rng.integers(4, 8)
            col = (112, 164, 104) if k % 2 else (156, 192, 110)
            cv.rect(x, cy + base - h, 1, h, col)
            cv.px(x, cy + base - h - 1, (244, 222, 116))
            cv.px(x, cy + base - h - 2, (250, 238, 158))
    # 大蒲公英：黄杆 + 绒球（芦苇地最认得出的东西）：外圈天蓝、里面白、右上最亮
    sx, sy = cx - 3, cy - 6
    cv.line(cx - 1, cy + 7, sx, sy + 4, (232, 190, 72))
    for dy in range(-6, 7):
        for dx in range(-6, 7):
            d = dx * dx + dy * dy
            if d <= 30 and not (d > 24 and (dx + dy) % 2):
                c = (112, 176, 224) if d > 20 else (196, 226, 244) if (dx - 1) ** 2 + (dy + 1) ** 2 > 9 else (252, 252, 246)
                cv.px(sx + dx, sy + dy, c)
    cv.px(sx, sy + 1, (246, 214, 120))
    # 是一颗星，不是一扇窗：背光那半边压暗（和别的星球一样月光从右上来），档间棋盘格
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):
        l = lit(cx, cy, r, x, y)
        f = 1.0
        if l < -0.62 or (l < -0.48 and (x + y) % 2 == 0):
            f = 0.66
        elif l < -0.28 or (l < -0.14 and (x + y) % 2 == 0):
            f = 0.82
        cv.rgb[y, x] *= f
    finish_disc(cv, mask, cx, cy, r, rim=(250, 252, 236))


def draw_cloud_town(cv):
    """云层星上的小镇（art/cloud_town 那种）：紫色尖塔、木筋小楼立在云上，亮着几扇黄窗，塔尖一点金。"""
    cx, cy, _ = CLOUD
    wall, wall2, roof, roof2 = (54, 40, 76), (96, 74, 112), (66, 44, 86), (118, 82, 122)
    win, tip = (252, 214, 118), (214, 170, 110)
    base = cy + 14
    # (dx, 宽, 塔身高, 类型)  spire = 细塔 + 尖顶；house = 两层小楼 + 人字顶
    for dx, w, h, kind in ((-6, 3, 7, "spire"), (-2, 4, 5, "house"), (3, 3, 10, "spire"), (7, 4, 6, "house"), (12, 3, 6, "spire")):
        x = cx + dx
        y0 = base - h
        cv.rect(x, y0, w, h + 1, wall)
        cv.rect(x + w - 1, y0, 1, h + 1, wall2)
        if kind == "spire":
            m = x + 1                                          # 塔身 3 格宽，尖顶 1/3/3/5 往下放宽，顶上一点金
            for i, hw in enumerate((0, 1, 1, 2)):
                for xx in range(m - hw, m + hw + 1):
                    cv.px(xx, y0 - 4 + i, roof2 if xx > m or (xx == m and i == 0) else roof)
            cv.px(m, y0 - 5, tip)
            cv.px(m, y0 + 2, win)
        else:
            for i in range(3):                                 # 人字顶
                xa, xb = x + 1 - i, x + w - 2 + i
                for xx in range(xa, xb + 1):
                    cv.px(xx, y0 - 3 + i, roof2 if xx >= x + w / 2.0 else roof)
            cv.px(x + 1, y0 + 1, win)
            cv.px(x + 2, y0 + 1, win)
            if h > 5:
                cv.px(x + 1, y0 + 3, win)


def draw_chart(cv):
    """底下的铅笔：几道大弧（星图的轨道线）、刻度。"""
    for R, gap in ((120, 5), (150, 7), (182, 5), (214, 7)):
        for i in range(0, 900):
            a = math.radians(i * 0.1 - 90)
            x = -20 + R * math.cos(a)
            y = 128 + R * math.sin(a)
            if i % (gap * 4) < gap * 2:
                cv.px(x, y, PENCIL, 0.28)
    for x in range(12, 180, 28):                               # 边上的刻度
        cv.line(x, 3, x, 5, PENCIL, 0.4)
        cv.line(x, H - 6, x, H - 4, PENCIL, 0.4)
    for y in range(20, 100, 20):
        cv.line(3, y, 5, y, PENCIL, 0.4)
        cv.line(W - 6, y, W - 4, y, PENCIL, 0.4)


def draw_stars(cv):
    rng = np.random.default_rng(61)
    keep = np.ones((H, W), bool)
    for (cx, cy, r) in (HOME, FOREST, RIVER, CLOUD, REED):
        ys, xs = np.ogrid[:H, :W]
        keep &= (xs - cx) ** 2 + (ys - cy) ** 2 > (r + 5) ** 2
    for row in LABELS:
        keep[max(0, row[3] - 2):row[3] + 10, max(0, row[2] - 26):row[2] + 26] = False
    for pts in route_paths().values():                          # 航线两边各让 4 格
        for x, y in pts:
            keep[max(0, y - 4):y + 5, max(0, x - 4):x + 5] = False
    ys, xs = np.ogrid[:H, :W]
    keep &= np.abs((xs - 67) * 36 + (ys - 76) * 28) / math.hypot(36, 28) > 9      # 碎石带一条
    n = 0
    while n < 30:
        x, y = rng.integers(8, W - 8), rng.integers(6, H - 6)
        if not keep[y, x]:
            continue
        n += 1
        if n % 6 == 0:
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.px(x + dx, y + dy, INK, 0.75)
        else:
            cv.px(x, y, INK, 0.65)


def draw_compass(cv, cx, cy):
    """右下角不够，放左上：一个手画的小罗盘（四个尖，朝上那个涂黑）。"""
    for i in range(1, 7):
        cv.px(cx, cy - i, INK_D)
        if i < 5:
            cv.px(cx, cy + i, INK)
            cv.px(cx - i, cy, INK)
            cv.px(cx + i, cy, INK)
    cv.px(cx - 1, cy - 2, INK_D)
    cv.px(cx + 1, cy - 2, INK_D)
    cv.px(cx - 1, cy - 1, INK_D)
    cv.px(cx + 1, cy - 1, INK_D)
    for dx, dy in ((-1, 1), (1, 1)):
        cv.px(cx + dx, cy + dy, INK)
    for a in range(0, 360, 30):
        x, y = cx + 4 * math.cos(math.radians(a)), cy + 4 * math.sin(math.radians(a))
        cv.px(x, y, INK, 0.55)


def dash(cv, pts, col, on=3, off=2, k=1.0, start=0):
    for i, (x, y) in enumerate(pts):
        if (i + start) % (on + off) < on:
            cv.px(x, y, col, k)


def arrow(cv, x, y, dx, dy, col):
    """小箭头：尖 + 两翼各 3 格，往回斜 40 度（dx, dy 单位方向）。"""
    n = math.hypot(dx, dy)
    dx, dy = dx / n, dy / n
    for deg in (140, -140):
        c, sn = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        cv.line(x, y, x + 3 * (dx * c - dy * sn), y + 3 * (dx * sn + dy * c), col)


def rock(cv, x, y, r):
    """一块碎石：不规则的小块，右上亮、左下暗，墨色压边。"""
    base, hi, lo = (112, 100, 96), (172, 156, 138), (60, 52, 58)
    cells = {(0, 0)}
    if r >= 1:
        cells |= {(1, 0), (0, -1), (1, -1)}
    if r >= 2:
        cells |= {(-1, 0), (-1, -1), (0, 1), (1, 1), (2, -1), (0, -2), (1, -2)}
    for dx, dy in cells:
        c = base
        if (dx + 1, dy) not in cells or (dx, dy - 1) not in cells:
            c = hi
        if (dx - 1, dy) not in cells or (dx, dy + 1) not in cells:
            c = lo
        cv.px(x + dx, y + dy, c)


XMARK = (79, 59)


def draw_debris(cv):
    """碎石带：一道斜着的碎石，封住森林到河流的旧航线（一块块分开，不粘成一团）。"""
    rng = np.random.default_rng(72)
    (x0, y0), (x1, y1) = (67, 76), (95, 40)
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = (y1 - y0) / L, -(x1 - x0) / L
    t = 0.0
    while t <= 1.0:
        off = rng.uniform(-4.5, 4.5)
        x = x0 + (x1 - x0) * t + nx * off
        y = y0 + (y1 - y0) * t + ny * off
        if math.hypot(x - XMARK[0], y - XMARK[1]) > 6:             # 让出旧航线打叉的地方
            rock(cv, int(round(x)), int(round(y)), int(rng.choice([0, 0, 1, 1, 2])))
        t += rng.uniform(0.035, 0.07)


def route_paths():
    """所有航线的像素路径（画线和让星星都用这一份）。"""
    fx, fy = FORK
    home_back = (bezier((fx - 1, fy + 2), (140, 80), (142, 103), (124, 103))
                 + line_pts(123, 103, 54, 103)
                 + bezier((53, 103), (45, 103), (42, 98), (40, 92)))
    return {
        "home_forest": bezier((35, 66), (37, 63), (39, 61), (41, 58)),
        "old1": bezier((70, 54), (72, 55), (74, 56), (75, 57)),
        "old2": bezier((83, 61), (83, 61), (84, 62), (84, 62)),
        "detour": bezier((77, 33), (92, 20), (113, 24), (106, 43)),
        "river_fork": bezier((120, 66), (128, 63), (135, 60), (141, 59)),
        "town": line_pts(fx, fy - 2, fx, fy - 9),
        "town_tag": line_pts(169, TOWN_TAG[1], 163, TOWN_TAG[1]),
        "reed": bezier((fx + 2, fy), (156, 58), (159, 59), (160, 61)),
        "home_back": home_back,
    }


def draw_routes(cv):
    rp = route_paths()
    # 母星 → 森林星
    dash(cv, rp["home_forest"], ROUTE)
    arrow(cv, 44, 55, 1, -1, ROUTE)
    # 旧航线：铅笔细线穿过碎石带，打叉
    dash(cv, rp["old1"], PENCIL, 2, 1, 0.95)
    dash(cv, rp["old2"], PENCIL, 2, 1, 0.6)
    for i in range(-2, 3):
        cv.px(XMARK[0] + i, XMARK[1] + i, ROUTE_D)
        cv.px(XMARK[0] + i, XMARK[1] - i, ROUTE_D)
    # 绕路：从森林星右上出来，翻过碎石带顶上，再下到河流星
    dash(cv, rp["detour"], ROUTE)
    arrow(cv, 105, 48, -0.15, 1, ROUTE)
    # 河流星 → 云层星底下的分叉点
    dash(cv, rp["river_fork"], ROUTE)
    arrow(cv, 145, 58, 1, -0.15, ROUTE)


def draw_branches(cv):
    """分叉点分三路（细墨点线）：往上进云层星的小镇；往右下芦苇星；往下沿纸底回母星。画在星球之后，压在云上。"""
    rp = route_paths()
    fx, fy = FORK
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):        # 分叉点：一个小墨圈
        cv.px(fx + dx, fy + dy, INK_D)
    for key, step in (("town", 2), ("reed", 3), ("home_back", 3), ("town_tag", 2)):
        for i, (x, y) in enumerate(rp[key]):
            if i % step == 0:
                cv.px(x, y, INK_D if key in ("town", "town_tag") else INK)
    arrow(cv, 160, 63, 0.1, 1, INK)
    arrow(cv, 40, 90, -0.15, -1, INK)


def build():
    if str(OUT.relative_to(ROOT)) in json.loads(HAND.read_text())["files"]:
        raise SystemExit("手改清单里的图不许覆盖：" + str(OUT))
    cv = Cv()
    draw_chart(cv)
    draw_stars(cv)
    draw_debris(cv)
    draw_routes(cv)
    draw_home(cv)
    draw_river(cv)
    draw_cloud(cv)
    draw_reed(cv)
    draw_forest(cv)
    cv.clip = None
    draw_branches(cv)
    draw_compass(cv, 14, 29)
    img = cv.image()
    img.save(OUT)
    return img


def preview(img, d: Path):
    d.mkdir(parents=True, exist_ok=True)
    img.resize((W * 4, H * 4), Image.NEAREST).save(d / "paper_map_4x.png")
    # 照 paper_view.gd：480×270 里放大 2 倍居中，四周压暗，地名用游戏字体 14 号
    v = Image.new("RGBA", (480, 270), (12, 16, 20, 255))
    v.alpha_composite(img.resize((W * 2, H * 2), Image.NEAREST), (50, 19))
    dr = ImageDraw.Draw(v)
    font = ImageFont.truetype(str(ROOT / "fonts/PixelFont_ui.ttf"), 14)
    for lang in (0, 1):
        vv = v.copy()
        dr = ImageDraw.Draw(vv)
        for row in LABELS:
            t = row[lang]
            tw = dr.textlength(t, font=font)
            x, y = 50 + row[2] * 2 - tw / 2, 19 + row[3] * 2
            dr.text((x, y), t, font=font, fill=INK_D + (255,))
        vv.resize((480 * 3, 270 * 3), Image.NEAREST).save(d / ("paper_view_%s_3x.png" % ("zh" if lang == 0 else "en")))


def cockpit_map():
    """驾驶舱小航图：用 cockpit_final_art.py 的 travel_map（也是这次改的），只写这一张。"""
    import cockpit_final_art as cf
    cf.NEW_OBJ.clear()
    cf.travel_map()
    cf.save(cf.strip(cf.NEW_OBJ["cockpit_map"]["frames"]), cf.CK / "cockpit_map.png")
    print("写了", cf.WROTE)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview")
    ap.add_argument("--cockpit", action="store_true")
    a = ap.parse_args()
    im = build()
    if a.preview:
        preview(im, Path(a.preview))
    if a.cockpit:
        cockpit_map()
