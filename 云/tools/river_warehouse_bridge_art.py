"""河流篇：水下仓库（warehouse）和南桥 + 货台（southbridge）两个房间的图和 room.json（10-30 重做）。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_warehouse_bridge_art.py [--preview 目录] [--only warehouse,southbridge]

输出 art/river_city/warehouse/*、art/river_city/southbridge/*（覆盖 tools/river_city_art.py 以前出的灰色大都市版）。之后跑一次 --headless --import。
约定见 docs/river_rooms_contract.md；markers 名字、objects 的 id 和状态名、rope、walk_when、viewfinder、portals、scripts 和旧版一样，坐标按新图。

底子用作者原来的两个场景，远景层直接引用原图（res://art/underwater/*、res://art/river/*），不重画：
- 仓库 = 泡在原来那片水底（tools/underwater_art.py：荒野海底、石头人头、海带林）里的一栋旧仓库。屋顶塌了几块，月光从水面照下来；
  后墙的破窗、塌口直接透出原来的水底层（人头层 x 偏移过，晨在箱子那一带时人头正好在塌口里）。
  匆忙搬迁：桌椅绑到房梁上、抽屉朝同一个方向敞着、一排贴圆字标签的箱子、破箱子（纽扣、空瓶、照片）；
  导绳沿 y=150 一路拉到泄水门，绳结挂小布条；出口灯是暖黄的（全屋最亮的暖色，比晨暗）。
  小游戏要点的东西（浮箱、倒下的柜子、家具、内门、设备柜、泄水门）在最亮的一档、轮廓清楚，周围压暗。
- 南桥 = 原来的蓝色月夜河岸（tools/river_art.py：天、月亮、对岸石柱、雾、伞树）。水退了：晨走在桥下的泥滩上，
  桥洞里透出原来的河和对岸。桥身的拱肩里嵌着几户小房子（暖黄的窗），它们的屋顶就是桥面——从上面看像栏杆的，
  是屋脊上的一排小石像（原文「从下面看，是别人家的屋顶」）。桥墩上一道旧水位线。灯柱、桥洞的擦痕、泥滩脚印。
  右边一道挡土墙，墙里是旧运输水道（revealed 时挡着的木板和水草没了），穿过去是废弃货台：航线图（会掉下来）、编号牌。
  房子不重叠、没有高楼和人群；中景（0.6）只有几尊立在浅水里的石像、系船桩和一盏浮灯。

规则（和原图一样）：1 倍像素，alpha 只有 0/255，不描边；颜色走 OKLCh（river_art.lch：暗处偏靛、亮处偏青银），
光从上（水下）/ 右上（月亮）来；暖黄只给灯和窗，小面积。所有随机固定 seed。

取景框 viewfinder.png：用南桥这几层在「镜头左边缘 = 352」（晨站 592、小游戏期间镜头正对晨）按引擎的视差公式合成，
再盖上影像里那时候的高水位、一串往中间桥洞歪的浮灯和一个灰影，压成影像的颜色。换了任何一层都要重出（这个脚本每次都重出）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.palette import from_lch  # noqa: E402
import river_art as RA  # noqa: E402
from river_art import lch, shade_rock, smooth1d  # noqa: E402
import river_bank_moon_art as bm  # noqa: E402  石头的画法（整块石头、粗石墙、凿洞）和河岸会话共用
import river_city_art as rca  # noqa: E402

ROOT = TOOLS.parent
OUT = ROOT / "art" / "river_city"
H = 270
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16


def col(L, C, h):
    """不走 hue_shift 的颜色（暖色、木头、纸用）。"""
    return tuple(int(v) for v in from_lch(float(L), float(C), float(h)))


def blue(L, C=None, h=254.0):
    return lch(L, C, h)


# 暖黄（灯、窗）：芯子 < 晨的白发；外圈很快沉回蓝里
WARM = col(0.78, 0.105, 82)
WARM2 = col(0.66, 0.10, 74)
WARM3 = col(0.50, 0.075, 66)
WARM4 = col(0.36, 0.045, 60)
TAG = col(0.60, 0.045, 80)          # 圆字标签纸（琥珀）
TAG_D = col(0.50, 0.040, 72)
PAPER = col(0.56, 0.016, 95)
PAPER_D = col(0.46, 0.014, 92)
INK = col(0.24, 0.02, 250)
MAP = col(0.43, 0.016, 95)         # 航线图的纸：比别的纸暗一档（墙上一大张，不能抢晨）
MAP_D = col(0.35, 0.014, 92)


class Cv:
    """一张 RGBA 画布（不绕回）。"""

    def __init__(self, w, h):
        self.a = np.zeros((h, w, 4), np.uint8)

    @property
    def w(self):
        return self.a.shape[1]

    @property
    def h(self):
        return self.a.shape[0]

    def put(self, x, y, c):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = tuple(c[:3]) + (255,)

    def rect(self, x0, y0, x1, y1, c):
        """含两端。"""
        x0, x1 = sorted((int(round(x0)), int(round(x1))))
        y0, y1 = sorted((int(round(y0)), int(round(y1))))
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.w - 1, x1), min(self.h - 1, y1)
        if x0 <= x1 and y0 <= y1:
            self.a[y0:y1 + 1, x0:x1 + 1] = tuple(c[:3]) + (255,)

    def clear(self, x0, y0, x1, y1):
        self.a[max(0, y0):y1 + 1, max(0, x0):x1 + 1] = 0

    def line(self, x0, y0, x1, y1, c):
        x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        e = dx + dy
        while True:
            self.put(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * e
            if e2 >= dy:
                e += dy
                x0 += sx
            if e2 <= dx:
                e += dx
                y0 += sy

    def mask_of_poly(self, pts):
        im = Image.new("L", (self.w, self.h), 0)
        ImageDraw.Draw(im).polygon([(float(x), float(y)) for x, y in pts], fill=255)
        return np.array(im) > 0

    def mask_of_ellipse(self, x0, y0, x1, y1):
        im = Image.new("L", (self.w, self.h), 0)
        ImageDraw.Draw(im).ellipse((x0, y0, x1, y1), fill=255)
        return np.array(im) > 0

    def fill(self, m, c):
        self.a[m] = tuple(c[:3]) + (255,)

    def poly(self, pts, c):
        self.fill(self.mask_of_poly(pts), c)

    def paste(self, img, x, y):
        h, w = img.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        src = img[y0 - y:y1 - y, x0 - x:x1 - x]
        m = src[..., 3] > 0
        self.a[y0:y1, x0:x1][m] = src[m]

    def save(self, path):
        Image.fromarray(self.a).save(path)


def rc(cv):
    """把我的 Cv 包成 river_city_art.Cv（共用同一块数组），好直接调河岸会话的石头函数。"""
    r = rca.Cv(cv.w, cv.h)
    r.a = cv.a
    return r


def stone_mass(cv, m, rng, pal, cracks=4, strata=3):
    """整块石头（bm.shade_mass）贴到掩码 m 上。"""
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    sub = m[y0:y1, x0:x1]
    img = bm.shade_mass(sub, rng, pal, cracks=cracks, strata=strata)
    cv.paste(img, x0, y0)


def rough_in(cv, m, rng, pal):
    """粗石垒的墙（bm.rough_wall）只画在掩码 m 里。"""
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return
    tmp = rca.Cv(cv.w, cv.h)
    bm.rough_wall(tmp, int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1, rng, pal)
    keep = m & (tmp.a[..., 3] > 0)
    cv.a[keep] = tmp.a[keep]


def dither_ramp(cv, x0, y0, x1, y1, c0, c1, horizontal=False, mask=None):
    """两色之间按 Bayer 抖出一条渐变（不用半透明）。"""
    for y in range(max(0, y0), min(cv.h, y1 + 1)):
        for x in range(max(0, x0), min(cv.w, x1 + 1)):
            if mask is not None and not mask[y, x]:
                continue
            t = (x - x0) / max(1, x1 - x0) if horizontal else (y - y0) / max(1, y1 - y0)
            cv.a[y, x] = tuple((c1 if t > BAYER[y % 4, x % 4] else c0)[:3]) + (255,)


def glow(cv, cx, cy, r, cols, keep=None):
    """一团硬边的光（同心几圈，外圈抖开）；只画在已有像素上（keep=None）或画在 keep 掩码上。"""
    n = len(cols)
    for y in range(int(cy - r), int(cy + r) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            if not (0 <= x < cv.w and 0 <= y < cv.h):
                continue
            if keep is None and cv.a[y, x, 3] == 0:
                continue
            if keep is not None and not keep[y, x]:
                continue
            d = np.hypot((x - cx) / r, (y - cy) / r)
            if d > 1:
                continue
            k = (1 - d) * n - BAYER[y % 4, x % 4] * 0.9
            i = int(np.clip(np.floor(k), -1, n - 1))
            if i >= 0:
                cv.a[y, x] = tuple(cols[i][:3]) + (255,)


def lighten(cv, m, amt, h=250.0):
    """在掩码里把已有像素往月光的青银推一档（OKLab 里加 L）。"""
    from oscarkit.palette import oklab_to_srgb, to_lab
    ys, xs = np.nonzero(m & (cv.a[..., 3] > 0))
    if len(ys) == 0:
        return
    rgb = cv.a[ys, xs, :3].astype(float)
    lab = np.array([to_lab(tuple(c)) for c in rgb])
    lab[:, 0] = np.clip(lab[:, 0] + amt, 0, 1)
    out = oklab_to_srgb(lab)
    cv.a[ys, xs, :3] = np.clip(out, 0, 255).astype(np.uint8)


# =========================================================================== 引擎的视差合成（预览 + 取景框）
def comp(layers, cam_left, w=480):
    """layers：[(rgba 数组, scroll, x, y, tile)]，按 room_stage.gd update() 的公式摆，返回 480×270。"""
    out = np.zeros((H, w, 4), np.uint8)
    cl = int(round(cam_left))
    for a, sc, lx, ly, tile in layers:
        ih, iw = a.shape[:2]
        if tile:
            sx = int(np.round(lx - cl * sc)) % iw - iw
            xs = range(sx, w, iw)
        else:
            xs = [int(round(lx + cl * (1.0 - sc))) - cl]
        for x in xs:
            x0, x1 = max(0, x), min(w, x + iw)
            y0, y1 = max(0, ly), min(H, ly + ih)
            if x0 >= x1 or y0 >= y1:
                continue
            src = a[y0 - ly:y1 - ly, x0 - x:x1 - x]
            m = src[..., 3] > 0
            out[y0:y1, x0:x1][m] = src[m]
    return out


def load(rel):
    return np.array(Image.open(ROOT / rel).convert("RGBA"))


def palette_decode(a, pal):
    """glints / surface 这种给 shader 的编码图，预览时按 R 查色。"""
    out = np.zeros_like(a)
    m = a[..., 3] > 0
    lv = np.clip(np.floor(a[..., 0] / 255 * 3 + 0.25), 0, 3).astype(int)
    p = np.array([RA.rgba(lch(*q)) for q in pal], np.uint8)
    out[m] = p[lv[m]]
    return out


def stand_in(img, x, gy):
    """预览里晨的替身：10×37 的浅色块（白发那一档）。"""
    img[gy - 37:gy + 1, x - 5:x + 5] = (205, 196, 190, 255)
    img[gy - 37:gy - 31, x - 5:x + 5] = (236, 236, 240, 255)


def big(a, k=2):
    return Image.fromarray(a).resize((a.shape[1] * k, a.shape[0] * k), Image.NEAREST)


# =========================================================================== 水下仓库
WH_W = 720
WH_FLOOR = 236
WH_ROPE_Y = 150                 # 导绳（rope.anchor 的 y；引擎在这一行画绳结）
WH_ROPE = "#7b8a8a"
ROPE_C = (0x7b, 0x8a, 0x8a)
ROOF_HOLES = [(118, 178), (366, 424), (606, 640)]
H1 = [(150, 172), (156, 120), (151, 84), (160, 52), (176, 40), (198, 46), (214, 36), (236, 44), (250, 64),
      (262, 70), (258, 104), (264, 140), (258, 168), (238, 174), (214, 170), (190, 176), (170, 170)]   # 后墙塌口
W0 = (66, 58, 110, 106)        # 左边的小窗
W2 = (318, 50, 394, 120)       # 箱子上面的大窗
PORT = (600, 78, 8)            # 内间的圆窗
PART = (544, 556)              # 内门所在的隔墙
INNER = (556, 636)             # 内间（设备柜）
SLUICE_WALL = 636

# 颜色：水下的灰泥、混凝土、木头、铁
WALL = [blue(v) for v in (0.105, 0.13, 0.155, 0.18, 0.205, 0.235)]
WROCK = RA.bramp(6, 0.085, 0.27, 258, 240)      # 仓库凿在水底巨石里：岩壁（和河岸的 STONE 同一路，水下暗一档）
WBLOCK = RA.bramp(6, 0.08, 0.26, 258, 242)     # 隔墙、泄水门那面墙：凿剩下的岩墙，比后墙近一点、亮一点
CONC = [blue(v, None, 250) for v in (0.09, 0.12, 0.16, 0.21, 0.27, 0.33)]
WOOD = [col(v, 0.018 + v * 0.02, 62 + v * 30) for v in (0.13, 0.17, 0.21, 0.26, 0.31, 0.37)]
IRON = [blue(v, 0.02, 246) for v in (0.12, 0.17, 0.23, 0.3, 0.38, 0.46)]
SILT = [col(v, 0.022, 210) for v in (0.12, 0.16, 0.2, 0.25)]
DARK = blue(0.065)


def wh_wall_mask():
    """后墙（含天花板、房梁）的实心部分。"""
    cv = Cv(WH_W, H)
    m = np.ones((H, WH_W), bool)
    m[WH_FLOOR + 1:] = False
    m &= ~cv.mask_of_poly(H1)
    x0, y0, x1, y1 = W0
    m[y0:y1 + 1, x0:x1 + 1] = False
    x0, y0, x1, y1 = W2
    m[y0:y1 + 1, x0:x1 + 1] = False
    m &= ~cv.mask_of_ellipse(PORT[0] - PORT[2], PORT[1] - PORT[2], PORT[0] + PORT[2], PORT[1] + PORT[2])
    rng = np.random.default_rng(31)
    for a, b in ROOF_HOLES:              # 屋顶的破洞：参差的边
        edge = smooth1d(b - a, rng, 12, 3.0)
        for i, x in enumerate(range(a, b)):
            d = int(16 + edge[i] + 4 * np.sin(np.pi * i / (b - a)))
            m[:max(0, d), x] = False
    return m


def wh_main():
    rng = np.random.default_rng(7)
    cv = Cv(WH_W, H)
    m = wh_wall_mask()
    # ---- 后墙 + 天花板：整块水底巨石里凿出来的大厅（不是砖、不是墙板）。整块石头的明暗起伏 + 裂缝 + 岩层缝，
    #      屋顶破洞下面一块楔形的亮（月光从水面照下来），往下沉进暗里
    stone_mass(cv, m, rng, WROCK, cracks=14, strata=8)
    yy = np.arange(H)[:, None]
    xx = np.arange(WH_W)[None, :]
    k = np.zeros((H, WH_W))
    for a, b in ROOF_HOLES:
        cx = (a + b) / 2
        spread = (b - a) / 2 + (yy - 16) * 0.35
        k = np.maximum(k, np.clip(1 - np.abs(xx - cx - (yy - 16) * 0.12) / np.maximum(spread, 1), 0, 1)
                       * np.clip(1 - (yy - 16) / 220.0, 0, 1))
    bay = BAYER[yy % 4, xx % 4]
    lighten(cv, m & (k * 1.6 > 0.35 + bay * 0.3), 0.03)
    lighten(cv, m & (k * 1.6 > 0.9 + bay * 0.3), 0.025)
    lighten(cv, m & (yy > 150) & ((yy - 150) / 90.0 > bay), -0.025)   # 往下沉进暗里
    # 内间更暗（没窗、在隔墙后面）
    inner = m.copy()
    inner[:, :INNER[0]] = False
    inner[:, INNER[1]:] = False
    lighten(cv, inner, -0.05)
    # 水渍（往下流的暗条）、墙脚的淤泥和一圈水草绒
    for _ in range(26):
        x = int(rng.integers(4, WH_W - 4))
        y0 = int(rng.integers(26, 150))
        ln = int(rng.integers(12, 70))
        for y in range(y0, min(WH_FLOOR, y0 + ln)):
            if m[y, x] and rng.random() < 0.8:
                cv.put(x, y, WROCK[0])
    for x in range(WH_W):                                          # 墙脚：淤泥线 + 水草绒
        top = WH_FLOOR - 6 - int(2 + 2 * np.sin(x / 7.0) + rng.integers(0, 3))
        for y in range(top, WH_FLOOR + 1):
            if m[y, x]:
                cv.put(x, y, SILT[1] if y > top + 1 else SILT[2])
        if rng.random() < 0.25:
            for k_ in range(int(rng.integers(2, 7))):
                cv.put(x, top - k_, SILT[2] if k_ < 3 else SILT[1])
    # 屋顶破洞的边：石唇受光，几块要掉不掉的碎石挂在边上
    for x in range(WH_W):
        ys = np.nonzero(m[:30, x])[0]
        if len(ys):
            top = ys.min()
            if top > 0:
                cv.put(x, top, WROCK[5])
                cv.put(x, top + 1, WROCK[4])
    for a, b in ROOF_HOLES:
        for x0 in (a + 2, b - 6):
            cv.rect(x0, 18, x0 + 3, 21, WROCK[2])
            cv.rect(x0, 18, x0 + 3, 18, WROCK[4])
    # ---- 窗：石头里凿出的洞，洞口左、上的内壁在影子里（墙厚），下沿的石唇受光
    for (x0, y0, x1, y1) in (W0, W2):
        cv.rect(x0, y0, x0 + 2, y1, WROCK[0])
        cv.rect(x0, y0, x1, y0 + 2, WROCK[0])
        cv.rect(x0 - 2, y1 + 1, x1 + 2, y1 + 2, WROCK[4])
        cv.rect(x0 - 2, y1 + 1, x1 + 2, y1 + 1, WROCK[5])
        cv.rect(x1 + 1, y0, x1 + 1, y1, WROCK[4])
    # 塌口的断边：边上一圈亮一档（石头的厚度）
    hole = ~cv.mask_of_poly(H1)
    edge = hole & ~np.roll(hole, 1, 1) | hole & ~np.roll(hole, -1, 0) | hole & ~np.roll(hole, 1, 0)
    edge &= m
    for y, x in zip(*np.nonzero(edge)):
        cv.put(x, y, WROCK[5] if y < 120 else WROCK[4])
    # 圆窗：凿出的圆洞，一圈石唇
    ring = cv.mask_of_ellipse(PORT[0] - PORT[2] - 2, PORT[1] - PORT[2] - 2, PORT[0] + PORT[2] + 2, PORT[1] + PORT[2] + 2)
    ring &= ~cv.mask_of_ellipse(PORT[0] - PORT[2], PORT[1] - PORT[2], PORT[0] + PORT[2], PORT[1] + PORT[2])
    cv.fill(ring, WROCK[1])
    for y, x in zip(*np.nonzero(ring)):
        if y > PORT[1] or x > PORT[0] + 3:
            cv.put(x, y, WROCK[4])
    # ---- 地面：混凝土楼板 + 一层淤泥，月光照到的地方亮
    for x in range(WH_W):
        lit = any(a - 10 <= x - 40 < b + 30 for a, b in ROOF_HOLES)
        cv.put(x, WH_FLOOR + 1, CONC[5] if lit else CONC[4])
        cv.rect(x, WH_FLOOR + 2, x, WH_FLOOR + 3, CONC[3] if lit else CONC[2])
        for y in range(WH_FLOOR + 4, H):
            t = (y - WH_FLOOR - 4) / (H - WH_FLOOR - 4)
            k = 2 - t * 2.2 + (BAYER[y % 4, x % 4] - 0.5) * 0.8
            cv.put(x, y, CONC[int(np.clip(np.floor(k), 0, 2))])
    for _ in range(90):                                            # 淤泥上的小碎块
        x, y = int(rng.integers(0, WH_W)), int(rng.integers(WH_FLOOR + 5, H - 2))
        cv.rect(x, y, x + int(rng.integers(1, 3)), y, CONC[3])
        cv.put(x, y + 1, CONC[0])
    # ---- 左边的入口：石头里凿的拱门洞（通往上面的斜坡），门里几级石阶；拴导绳的横杆、拴环
    door = np.zeros((H, WH_W), bool)
    dyy, dxx = np.mgrid[0:H, 0:WH_W]
    door |= (dxx >= 12) & (dxx <= 54) & (dyy >= 150) & (dyy <= WH_FLOOR)
    door |= ((dxx - 33) / 21.0) ** 2 + ((dyy - 150) / 14.0) ** 2 <= 1
    cv.fill(door, DARK)
    for i in range(10):                                            # 门里往上的台阶，一点点受光
        y = WH_FLOOR - i * 8
        cv.rect(14 + i * 2, y - 1, 30 + i * 2, y, blue(0.1 + i * 0.006))
    edge = door & ~(np.roll(door, -1, 1) & np.roll(door, 1, 0))
    cv.fill(edge & (dxx < 33), WROCK[0])
    rim = ~door & (np.roll(door, 1, 1) | np.roll(door, -1, 0)) & (dyy <= WH_FLOOR) & (dxx > 8) & (dxx < 60)
    cv.fill(rim, WROCK[4])
    cv.rect(12, 148, 54, 149, IRON[2])                             # 拴导绳的横杆
    cv.rect(31, 150, 35, 152, IRON[4])                             # 拴环（anchor 33,150）
    cv.put(33, 151, IRON[1])
    # ---- 导绳：沿 y=150 一路拉到泄水门（引擎在 knots 那里画小疙瘩），每隔一段一根从房梁垂下来的吊绳托着
    for x in range(36, 687):
        if PART[0] <= x <= PART[1]:
            continue
        sag = 1 if (x // 6) % 2 == 0 and False else 0
        cv.put(x, WH_ROPE_Y + sag, ROPE_C)
    for hx in (128, 286, 470, 612):
        cv.line(hx, 14, hx, WH_ROPE_Y - 1, blue(0.24, 0.015))
        cv.rect(hx - 1, 12, hx + 1, 14, IRON[3])                   # 打进岩顶的铁钩
        cv.rect(hx - 1, WH_ROPE_Y - 1, hx + 1, WH_ROPE_Y + 1, IRON[3])
        cv.rect(686, WH_ROPE_Y - 2, 688, WH_ROPE_Y + 2, IRON[4])      # 绳尾的环（end 686）
    return cv, m


def tied_table(cv, x0, y0, w, upside=True):
    """一张桌子四脚朝天绑在房梁上（匆忙搬迁）。"""
    th = 4
    cv.rect(x0, y0, x0 + w, y0 + th, WOOD[2])
    cv.rect(x0, y0, x0 + w, y0, WOOD[4])
    cv.rect(x0, y0 + th, x0 + w, y0 + th, WOOD[0])
    for lx in (x0 + 2, x0 + w - 4):
        cv.rect(lx, y0 - 14, lx + 2, y0 - 1, WOOD[1])
        cv.rect(lx + 2, y0 - 14, lx + 2, y0 - 1, WOOD[3])
    for rx in (x0 + 6, x0 + w - 6):                                # 绳子：从房梁斜着下来勒住桌面
        cv.line(rx, 14, rx + (3 if rx < x0 + w / 2 else -3), y0, ROPE_C)
        cv.rect(rx - 1 + (3 if rx < x0 + w / 2 else -3), y0 - 1, rx + 1 + (3 if rx < x0 + w / 2 else -3), y0 + th, blue(0.3, 0.012))


def tied_chair(cv, x0, y0, flip=False):
    """一把椅子倒挂（椅背朝下）。"""
    s = -1 if flip else 1
    cx = x0
    cv.rect(cx, y0, cx + 14, y0 + 2, WOOD[3])
    cv.rect(cx, y0, cx + 14, y0, WOOD[4])
    for lx in (cx + 1, cx + 12):
        cv.rect(lx, y0 - 12, lx + 1, y0 - 1, WOOD[1])
    bx = cx + (14 if s > 0 else 0)
    cv.rect(bx - 1, y0 + 3, bx, y0 + 16, WOOD[2])
    cv.rect(cx + 3, y0 + 9, cx + 12, y0 + 10, WOOD[1]) if not flip else None
    cv.line(cx + 7, 14, cx + 7, y0 - 1, ROPE_C)


def drawer_cabinet(cv, x0, w, h, cols_, rows_, pull=5):
    """一排矮抽屉柜，抽屉全朝右边敞着（同一个方向）。"""
    y0 = WH_FLOOR - h
    cv.rect(x0, y0, x0 + w, WH_FLOOR, WOOD[1])
    cv.rect(x0, y0, x0 + w, y0 + 1, WOOD[4])
    cv.rect(x0 + w, y0, x0 + w, WH_FLOOR, WOOD[2])
    cw = (w - 2) // cols_
    rh = (h - 4) // rows_
    for i in range(cols_):
        for j in range(rows_):
            dx = x0 + 2 + i * cw
            dy = y0 + 3 + j * rh
            cv.rect(dx, dy, dx + cw - 3, dy + rh - 3, DARK)         # 空掉的抽屉格
            # 拉出来的抽屉：往右错 pull 像素，看得见侧板和底
            px = dx + pull
            cv.rect(px, dy + 2, px + cw - 3, dy + rh - 3, WOOD[2])
            cv.rect(px, dy + 2, px + cw - 3, dy + 2, WOOD[4])
            cv.rect(px + cw - 3, dy + 2, px + cw - 2, dy + rh - 2, WOOD[3])   # 抽屉面板（朝右）
            cv.rect(px + cw - 1, dy + rh // 2, px + cw - 1, dy + rh // 2 + 1, IRON[4])   # 把手
            cv.rect(px + 1, dy + 4, px + cw - 5, dy + rh - 4, WOOD[0])          # 抽屉里空的
    cv.rect(x0, WH_FLOOR - 1, x0 + w + pull, WH_FLOOR, SILT[2])


def crate(cv, x0, y0, w, h, label=True, seed=0, lid_lit=True):
    rng = np.random.default_rng(seed)
    cv.rect(x0, y0, x0 + w, y0 + h, WOOD[2])
    for yy in range(y0 + 3, y0 + h, 5):
        cv.rect(x0 + 1, yy, x0 + w - 1, yy, WOOD[1])
    cv.rect(x0, y0, x0 + w, y0, WOOD[4] if lid_lit else WOOD[3])
    cv.rect(x0 + w, y0, x0 + w, y0 + h, WOOD[3])
    cv.rect(x0, y0, x0, y0 + h, WOOD[0])
    cv.rect(x0 + 2, y0 + 1, x0 + 3, y0 + h - 1, WOOD[1])
    cv.rect(x0 + w - 3, y0 + 1, x0 + w - 2, y0 + h - 1, WOOD[3])
    if label:                                                      # 圆字标签：圆角的琥珀小纸片，两行圆乎乎的字
        lw, lh = (10, 7) if w >= 18 else (7, 6)
        lx = x0 + (w - lw) // 2 + int(rng.integers(-1, 2))
        ly = y0 + (h - lh) // 2 + int(rng.integers(-1, 2))
        cv.rect(lx + 1, ly, lx + lw - 1, ly + lh, TAG)
        cv.rect(lx, ly + 1, lx + lw, ly + lh - 1, TAG)
        cv.rect(lx + lw, ly + 1, lx + lw, ly + lh - 1, TAG_D)
        for k, ry in enumerate((ly + 2, ly + 4)):
            n = lw - 3 - k * 2
            for i in range(n):
                if (i + k) % 3 != 2:
                    cv.put(lx + 2 + i, ry, INK)
            cv.put(lx + 2, ry - 1, INK) if k == 0 else None


def equip_cabinet(cv, x0, y0, w, h):
    """设备柜：铁皮高柜，5 格抽屉，每格一张小标签和一个拉手（小游戏要点它，所以轮廓最清楚）。"""
    cv.rect(x0, y0, x0 + w, WH_FLOOR, IRON[2])
    cv.rect(x0, y0, x0 + w, y0 + 1, IRON[5])
    cv.rect(x0 + w - 1, y0, x0 + w, WH_FLOOR, IRON[4])
    cv.rect(x0, y0, x0, WH_FLOOR, IRON[1])
    cv.rect(x0 + 2, y0 + 3, x0 + w - 3, y0 + 9, IRON[1])          # 顶上的铭牌
    cv.rect(x0 + 6, y0 + 5, x0 + w - 7, y0 + 7, PAPER_D)
    dh = (WH_FLOOR - y0 - 14) // 5
    for i in range(5):
        dy = y0 + 12 + i * dh
        cv.rect(x0 + 2, dy, x0 + w - 3, dy + dh - 2, IRON[3])
        cv.rect(x0 + 2, dy, x0 + w - 3, dy, IRON[4])
        cv.rect(x0 + 2, dy + dh - 2, x0 + w - 3, dy + dh - 2, IRON[1])
        cv.rect(x0 + 5, dy + 3, x0 + 14, dy + 6, TAG if i == 3 else PAPER_D)   # 标签（读取头那格的标签新一点）
        cv.rect(x0 + 6, dy + 4, x0 + 12, dy + 4, INK)
        cv.rect(x0 + w - 12, dy + dh // 2 - 1, x0 + w - 6, dy + dh // 2, IRON[5])
    cv.rect(x0 - 1, WH_FLOOR - 1, x0 + w + 1, WH_FLOOR, SILT[2])


def wh_props(cv):
    """主层上不会动的东西：吊着的桌椅、抽屉柜、箱子、隔墙、内间的设备柜、泄水门那面墙的管子。"""
    tied_table(cv, 70, 46, 54)
    tied_chair(cv, 194, 60)
    tied_chair(cv, 228, 54, flip=True)
    tied_chair(cv, 342, 40)
    tied_table(cv, 436, 40, 46)
    tied_chair(cv, 506, 58, flip=True)
    drawer_cabinet(cv, 64, 70, 44, 3, 3)
    drawer_cabinet(cv, 150, 58, 34, 2, 2)
    # 一排贴圆字标签的箱子（marker warehouse_boxes = 380），用绳子捆在一起
    seed = 0
    for (x, w, h, tiers) in ((314, 24, 22, 3), (340, 22, 20, 2), (364, 26, 22, 3), (392, 22, 20, 2), (416, 18, 16, 1)):
        y = WH_FLOOR
        for t in range(tiers):
            y -= h + 1
            crate(cv, x + (1 if t % 2 else 0), y, w, h, label=True, seed=seed)
            seed += 1
    cv.line(312, WH_FLOOR - 66, 392, WH_FLOOR - 66, ROPE_C)
    for x in (326, 378):
        cv.line(x, WH_FLOOR - 66, x, WH_FLOOR - 1, ROPE_C)
    # 隔墙（凿剩下的一道岩墙；内门在下面，内门本身是物件）
    a, b = PART
    rng = np.random.default_rng(41)
    pm = np.zeros((H, WH_W), bool)
    pm[10:WH_FLOOR + 1, a - 3:b + 4] = True
    stone_mass(cv, pm, rng, WBLOCK, cracks=3, strata=2)          # 凿大厅时留下的一道岩墙
    cv.rect(a + 1, 174, b - 1, WH_FLOOR, DARK)                     # 门洞（门关着时被物件盖住）
    cv.rect(a - 3, 171, b + 3, 173, WBLOCK[5])                    # 门楣：一条长石
    cv.rect(a - 3, 173, b + 3, 173, WBLOCK[1])
    cv.rect(a - 1, WH_ROPE_Y - 2, b + 1, WH_ROPE_Y + 2, DARK)
    for x in range(a - 1, b + 2):
        cv.put(x, WH_ROPE_Y, ROPE_C)
    # 内间：设备柜（marker warehouse_cabinet = 598）
    equip_cabinet(cv, 580, 150, 36, 86)
    # 右边：泄水门那面墙（岩壁 + 两根管子）；门本身是物件
    sm = np.zeros((H, WH_W), bool)
    sm[10:WH_FLOOR + 1, SLUICE_WALL:WH_W] = True
    stone_mass(cv, sm, np.random.default_rng(43), WBLOCK, cracks=4, strata=3)
    for py in (40, 52):
        cv.rect(SLUICE_WALL + 7, py, 711, py + 4, IRON[2])
        cv.rect(SLUICE_WALL + 7, py, 711, py, IRON[4])
        for bx in range(650, 712, 18):
            cv.rect(bx, py - 1, bx + 1, py + 5, IRON[3])
    cv.rect(700, 56, 703, 132, IRON[2])
    cv.rect(703, 56, 703, 132, IRON[4])


# ---------------------------------------------------------------- 仓库的物件（room 坐标先画在整张图上，再裁出各自的帧）
R_BOX = (420, 118, 146, 119)     # 浮箱 / 倒下的柜子 / 家具共用的一块（x, y, w, h），三样东西的帧在同一个坐标系里画
FLOAT_C = [col(0.34, 0.05, 62), col(0.44, 0.065, 68), col(0.54, 0.075, 76), col(0.62, 0.07, 82)]
CAB = [blue(v, 0.02, 246) for v in (0.13, 0.19, 0.26, 0.34, 0.43)]


def strip(frames):
    return np.concatenate(frames, axis=1)


def crop(cv, r):
    x, y, w, h = r
    return cv.a[y:y + h, x:x + w].copy()


def float_box(cv, x0, y0, rope_to=None):
    """浮箱：16×12 的圆角桶，赭黄（全屋第二显眼的东西），顶上一圈亮，中间一道箍；rope_to = 绳子拴到哪。"""
    if rope_to is not None:
        cv.line(x0 + 8, y0 + 12, rope_to[0], rope_to[1], ROPE_C)
    cv.rect(x0 + 1, y0, x0 + 14, y0 + 11, FLOAT_C[1])
    cv.rect(x0, y0 + 1, x0 + 15, y0 + 10, FLOAT_C[1])
    cv.rect(x0 + 1, y0 + 1, x0 + 13, y0 + 3, FLOAT_C[2])
    cv.rect(x0 + 2, y0, x0 + 12, y0, FLOAT_C[3])
    cv.rect(x0 + 13, y0 + 1, x0 + 15, y0 + 10, FLOAT_C[0])
    cv.rect(x0, y0 + 6, x0 + 15, y0 + 7, IRON[2])
    cv.rect(x0 + 6, y0 - 2, x0 + 9, y0 - 1, IRON[3])                # 提手


def tall_cabinet(cv, p_foot, p_top, thick=18):
    """倒下的高柜：从柜脚（底边中点）到柜顶（顶边中点）的一个斜长方体；顶面（朝上那面）受光；两头各一个拴环（亮）。"""
    fx, fy = p_foot
    tx, ty = p_top
    d = np.array([tx - fx, ty - fy], float)
    L = np.hypot(*d)
    u = d / L
    n = np.array([u[1], -u[0]])                                    # 朝左上的法线（柜子的一面）
    if n[1] > 0:
        n = -n
    a = np.array([fx, fy], float) - n * 0
    pts = [a, a + d, a + d + n * thick, a + n * thick]
    m = cv.mask_of_poly([tuple(p) for p in pts])
    cv.fill(m, CAB[2])
    # 抽屉缝 / 门缝：沿长度方向分 4 格
    for k in (0.27, 0.52, 0.77):
        p0 = a + d * k
        cv.line(*(p0 + n * 2), *(p0 + n * (thick - 2)), CAB[1])
    # 朝上的长边亮，底下的长边暗，两端面
    cv.line(*(a + n * thick), *(a + d + n * thick), CAB[4])
    cv.line(*(a + n * (thick - 1)), *(a + d + n * (thick - 1)), CAB[3])
    cv.line(*a, *(a + d), CAB[0])
    cv.line(*(a + d), *(a + d + n * thick), CAB[3])
    cv.line(*a, *(a + n * thick), CAB[1])
    # 两个拴环（铁环，最亮的铁色）：顶端那个在柜顶面上，脚那个在柜脚
    for p in (a + d - u * 3 + n * (thick + 1), a + u * 3 + n * (thick + 1)):
        x, y = int(round(p[0])), int(round(p[1]))
        cv.rect(x - 1, y - 2, x + 1, y, IRON[5])
        cv.put(x, y - 1, CAB[1])


def sideboard(cv, x0, dx=0):
    """堵着内门的家具：一只沉的木头矮柜（两扇门 + 一排小抽屉）。"""
    x0 += dx
    y0 = 202
    cv.rect(x0, y0, x0 + 30, WH_FLOOR, WOOD[2])
    cv.rect(x0, y0, x0 + 30, y0 + 1, WOOD[5])
    cv.rect(x0 + 30, y0, x0 + 30, WH_FLOOR, WOOD[3])
    cv.rect(x0, y0, x0, WH_FLOOR, WOOD[0])
    cv.rect(x0 + 2, y0 + 3, x0 + 28, y0 + 8, WOOD[1])
    for k in range(3):
        cv.rect(x0 + 4 + k * 9, y0 + 5, x0 + 6 + k * 9, y0 + 5, WOOD[4])
    cv.rect(x0 + 2, y0 + 11, x0 + 14, WH_FLOOR - 3, WOOD[3])
    cv.rect(x0 + 16, y0 + 11, x0 + 28, WH_FLOOR - 3, WOOD[3])
    cv.rect(x0 + 2, y0 + 11, x0 + 14, y0 + 11, WOOD[4])
    cv.rect(x0 + 16, y0 + 11, x0 + 28, y0 + 11, WOOD[4])
    cv.rect(x0 + 12, y0 + 20, x0 + 13, y0 + 22, IRON[4])
    cv.rect(x0 + 17, y0 + 20, x0 + 18, y0 + 22, IRON[4])
    cv.rect(x0 + 1, WH_FLOOR - 2, x0 + 29, WH_FLOOR, WOOD[0])


CAB_FALLEN = ((474, 236), (538, 200))         # 柜脚着地、柜顶压在家具上
CAB_LIFTED = ((484, 236), (484, 166))         # 浮箱把柜顶浮起来，柜子绕柜脚立起来了
CAB_TILT = ((492, 214), (540, 201))           # 拴错：柜脚被浮起来，柜顶压得更死
FU_X = 512


def wh_objects():
    """返回 {id: (x, y, frames, extra)}。"""
    out = {}
    rx, ry, rw, rh = R_BOX
    big_r = (rx, ry, rw, rh)

    def blank():
        return Cv(WH_W, H)

    # ---- 浮箱：idle（拴在地上一块压重上，浮着）/ tied_top / tied_foot / held（在晨手里：这里空）
    fr = []
    c = blank()
    c.rect(436, 230, 448, WH_FLOOR, CONC[3])
    c.rect(436, 230, 448, 230, CONC[4])
    float_box(c, 434, 206, rope_to=(442, 229))
    fr.append(crop(c, big_r))
    c = blank()
    float_box(c, 476, 132, rope_to=CAB_LIFTED[1])
    fr.append(crop(c, big_r))
    c = blank()
    float_box(c, 480, 174, rope_to=(CAB_TILT[0][0] + 2, CAB_TILT[0][1] - 18))
    fr.append(crop(c, big_r))
    fr.append(crop(blank(), big_r))
    out["warehouse_float"] = (rx, ry, fr, {"z": -1, "click": [430, 200, 24, 36],
                              "states": {"default": 0, "idle": 0, "tied_warehouse_cabinet_top": 1,
                                         "tied_warehouse_cabinet_foot": 2, "held": 3}})
    # ---- 倒下的柜子：fallen / lifted / tilt_wrong
    fr = []
    for pf, pt in (CAB_FALLEN, CAB_LIFTED, CAB_TILT):
        c = blank()
        tall_cabinet(c, pf, pt)
        fr.append(crop(c, big_r))
    out["warehouse_tall_cabinet"] = (rx, ry, fr, {"z": -2, "click": [470, 196, 74, 40],
                                     "states": {"default": 0, "fallen": 0, "lifted": 1, "tilt_wrong": 2}})
    # ---- 家具：pinned / wiggle（晃一下）/ loose / moved（拉到左边，门口空出来）
    fr = []
    for dx in (0, 1, 0, -16):
        c = blank()
        sideboard(c, FU_X, dx)
        fr.append(crop(c, big_r))
    out["warehouse_furniture"] = (rx, ry, fr, {"z": -3, "click": [508, 200, 38, 36],
                                  "states": {"default": 0, "pinned": 0, "wiggle": 1, "loose": 2, "moved": 3}})
    # ---- 内门：closed / open（门板转到铰链那一侧，只剩一条边）
    fr = []
    c = Cv(10, 62)
    c.rect(0, 0, 9, 61, WOOD[2])
    c.rect(0, 0, 9, 0, WOOD[4])
    c.rect(9, 0, 9, 61, WOOD[3])
    c.rect(2, 4, 7, 26, WOOD[1])
    c.rect(2, 32, 7, 57, WOOD[1])
    c.rect(1, 30, 2, 31, IRON[5])
    fr.append(c.a.copy())
    c = Cv(10, 62)
    c.rect(7, 0, 9, 61, WOOD[3])
    c.rect(9, 0, 9, 61, WOOD[4])
    fr.append(c.a.copy())
    out["warehouse_inner_door"] = (545, 174, fr, {"z": -2, "states": {"default": 0, "closed": 0, "open": 1}})
    # ---- 出口灯：暖黄的小灯箱，一明一暗（900ms）
    fr = []
    for lit in (True, False):
        c = Cv(16, 8)
        c.rect(0, 0, 15, 7, IRON[1])
        c.rect(1, 1, 14, 6, WARM if lit else WARM3)
        c.rect(1, 6, 14, 6, WARM2 if lit else WARM4)
        for i in range(3):                                         # 往左（门口）的箭头
            c.rect(4 + i, 3 - i, 4 + i, 4 + i, IRON[0])
        c.rect(7, 3, 11, 4, IRON[0])
        fr.append(c.a.copy())
    out["warehouse_exit_light"] = (25, 134, fr, {"ms": 900, "states": {"default": [0, 1], "on": [0, 1]}})
    # ---- 破箱子：default（侧板裂开）/ spilled（纽扣、空瓶、照片撒在淤泥上）
    fr = []
    for spilled in (False, True):
        c = Cv(56, 30)
        x0, y0 = 6, 10
        c.rect(x0, y0, x0 + 26, 29, WOOD[2])
        for yy in range(y0 + 3, 29, 5):
            c.rect(x0 + 1, yy, x0 + 25, yy, WOOD[1])
        c.rect(x0, y0, x0 + 26, y0, WOOD[4])
        c.rect(x0 + 26, y0, x0 + 26, 29, WOOD[3])
        c.poly([(x0 + 14, y0 + 2), (x0 + 27, y0 + 4), (x0 + 27, 29), (x0 + 18, 29)], DARK)   # 裂开的侧板
        c.line(x0 + 27, y0 + 4, x0 + 35, 22, WOOD[3])               # 掉下来的木板
        c.line(x0 + 27, y0 + 5, x0 + 35, 23, WOOD[1])
        c.rect(x0 + 3, y0 + 6, x0 + 11, y0 + 11, TAG)                # 圆字标签
        c.rect(x0 + 5, y0 + 8, x0 + 9, y0 + 8, INK)
        # 里面看得见的东西
        c.rect(x0 + 19, y0 + 12, x0 + 21, y0 + 18, blue(0.42, 0.02, 220))     # 瓶子
        c.put(x0 + 20, y0 + 11, blue(0.5, 0.02, 220))
        if spilled:
            c.rect(x0 + 19, y0 + 12, x0 + 21, y0 + 18, DARK)
            for bx, by in ((36, 27), (40, 28), (45, 27), (38, 28)):           # 纽扣：亮的小圆点
                c.rect(bx, by, bx + 1, by, PAPER)
                c.put(bx, by + 1, PAPER_D)
            c.rect(42, 24, 49, 25, blue(0.42, 0.02, 220))                       # 空瓶躺着
            c.rect(50, 24, 51, 24, blue(0.5, 0.02, 220))
            c.put(43, 24, blue(0.55, 0.02, 220))
            c.rect(30, 26, 35, 29, PAPER)                                         # 照片（背面朝上，一角翘起）
            c.rect(31, 27, 34, 28, PAPER_D)
            c.put(35, 25, PAPER)
        fr.append(c.a.copy())
    out["warehouse_broken_box"] = (258, 207, fr, {"states": {"default": 0, "spilled": 1}})
    # ---- 绳结（导绳上两个）：平时挂一小条暗布；lit = 绳结边的反光带亮一下（剧本 prop lit）
    for k, kx in (("warehouse_knot_1", 230), ("warehouse_knot_2", 420)):
        fr = []
        for lit in (False, True):
            c = Cv(9, 14)
            c.rect(3, 3, 5, 10, TAG_D if lit else blue(0.3, 0.015))
            c.rect(4, 3, 4, 12, TAG if lit else blue(0.34, 0.015))
            if lit:
                for (x, y) in ((1, 1), (7, 1), (0, 6), (8, 6), (1, 11), (7, 11)):
                    c.put(x, y, WARM3)
                c.rect(3, 4, 5, 6, WARM)
            fr.append(c.a.copy())
        out[k] = (kx - 4, WH_ROPE_Y + 1 - 3, fr, {"states": {"default": 0, "lit": 1}})
    # ---- 泄水门 + 操作记录：log（夹板挂在门上，纸亮）/ signatures（翻到最后一页，几行签名）/ taken（只剩钩子）
    fr = []
    for st in ("log", "signatures", "taken"):
        c = Cv(70, 112)
        x0, y0 = 4, 8
        c.rect(x0, y0, x0 + 60, 111, IRON[2])
        c.rect(x0, y0, x0 + 60, y0 + 1, IRON[4])
        c.rect(x0 + 60, y0, x0 + 60, 111, IRON[3])
        c.rect(x0, y0, x0, 111, IRON[0])
        for ry in range(y0 + 6, 111, 14):                           # 铆钉横带
            c.rect(x0 + 1, ry, x0 + 59, ry + 1, IRON[1])
            for rxx in range(x0 + 4, x0 + 58, 8):
                c.put(rxx, ry, IRON[4])
        # 手轮
        cx, cy, r = x0 + 36, 62, 11
        ring = Cv(70, 112)
        mo = ring.mask_of_ellipse(cx - r, cy - r, cx + r, cy + r) & ~ring.mask_of_ellipse(cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2)
        c.fill(mo, IRON[3])
        for y, x in zip(*np.nonzero(mo)):
            if y < cy and x > cx - 2:
                c.put(x, y, IRON[5])
        c.line(cx - r + 1, cy, cx + r - 1, cy, IRON[3])
        c.line(cx, cy - r + 1, cx, cy + r - 1, IRON[3])
        c.rect(cx - 1, cy - 1, cx + 1, cy + 1, IRON[5])
        # 水位刻度（门边一条竖着的尺）
        for k in range(0, 90, 6):
            c.rect(x0 + 56, y0 + 8 + k, x0 + 58, y0 + 8 + k, PAPER_D if k % 18 == 0 else IRON[4])
        # 操作记录的钩子 + 夹板
        c.rect(x0 + 10, y0 + 18, x0 + 11, y0 + 20, IRON[5])
        if st != "taken":
            c.rect(x0 + 4, y0 + 21, x0 + 18, y0 + 40, WOOD[2])
            c.rect(x0 + 4, y0 + 21, x0 + 18, y0 + 21, WOOD[4])
            c.rect(x0 + 8, y0 + 20, x0 + 14, y0 + 22, IRON[4])
            c.rect(x0 + 5, y0 + 23, x0 + 17, y0 + 39, PAPER)
            c.rect(x0 + 17, y0 + 23, x0 + 17, y0 + 39, PAPER_D)
            if st == "log":
                for ly in range(y0 + 26, y0 + 38, 3):               # 一行一行的记录
                    c.rect(x0 + 7, ly, x0 + 15 - (ly % 4), ly, INK)
                c.rect(x0 + 7, y0 + 35, x0 + 12, y0 + 37, PAPER_D)   # 底下压着的手绘图露一角
            else:
                c.rect(x0 + 5, y0 + 15, x0 + 17, y0 + 21, PAPER_D)   # 前面几页翻上去了
                for i, ly in enumerate(range(y0 + 26, y0 + 38, 3)):  # 签名：歪歪扭扭的几笔
                    for j in range(9 - i):
                        c.put(x0 + 7 + j, ly + (j + i) % 2, INK)
        fr.append(c.a.copy())
    out["warehouse_sluice_door"] = (640, 124, fr, {"states": {"default": 0, "log": 0, "signatures": 1, "taken": 2}})
    return out


def wh_shafts():
    """月光：从三个屋顶破洞斜着照下来（不透明的浅色像素，层 alpha 压到很淡；越往下越稀）。"""
    cv = Cv(WH_W, H)
    c = blue(0.66, 0.03, 236)
    for a, b in ROOF_HOLES:
        for y in range(10, WH_FLOOR + 2):
            t = (y - 10) / (WH_FLOOR - 10)
            half = (b - a) / 2 * (0.7 + 0.9 * t)
            cx = (a + b) / 2 + 0.16 * (y - 10)
            for x in range(int(cx - half), int(cx + half) + 1):
                if not 0 <= x < WH_W:
                    continue
                e = 1 - abs(x - cx) / max(half, 1)
                dens = min(1.0, e * 1.6) * (1 - 0.75 * t)
                if dens > BAYER[y % 4, x % 4]:
                    cv.put(x, y, c)
    return cv


def wh_front():
    """前景（1.2）：画面最上沿垂下来的断电线和几缕海带、最下沿两堆碎块，都是近黑的剪影，不挡中间玩的那一条。"""
    w = 480 + int((WH_W - 480) * 1.2) + 8
    cv = Cv(w, H)
    rng = np.random.default_rng(12)
    dk = [blue(0.05), blue(0.075), blue(0.1)]
    for x0 in (60, 330, 610):                                     # 断电线：从上沿垂下一条弧
        ln = int(rng.integers(30, 60))
        for k in range(ln):
            x = x0 + int(10 * np.sin(k / ln * np.pi) * (1 if x0 % 2 else -1))
            cv.rect(x, k, x + 1, k, dk[1])
        cv.rect(x0 - 2, ln, x0 + 3, ln + 3, dk[0])
    for x0 in (180, 520, 700):                                     # 海带：从上面的破口垂进来
        y = 0
        x = float(x0)
        for k in range(int(rng.integers(40, 70))):
            x += np.sin(k / 9.0) * 0.6
            cv.rect(int(x), y + k, int(x) + 2, y + k, dk[2] if k % 7 else dk[1])
            if k % 9 == 4:
                cv.rect(int(x) + 3, y + k, int(x) + 6, y + k + 1, dk[1])
    for x0, wdt in ((120, 70), (470, 90), (760, 60)):              # 下沿的碎块堆
        prof = smooth1d(wdt, rng, 20, 4)
        for i in range(wdt):
            hgt = int(8 + 7 * np.sin(np.pi * i / wdt) + prof[i])
            cv.rect(x0 + i, H - hgt, x0 + i, H - 1, dk[0])
            cv.put(x0 + i, H - hgt, dk[2])
    return cv


UW = "res://art/underwater/"
HEAD_X = -215                    # 人头层整体左挪：晨在箱子一带（镜头左边缘 ~100）时，石头人头正好在后墙塌口里


def wh_layers():
    """room.json 的 layers（远景直接用原来的水底图）。"""
    return [
        {"id": "deep", "img": UW + "deep.png", "scroll": 0.0, "y": 0},
        {"id": "distant", "img": UW + "distant.png", "scroll": 0.05, "y": 0, "tile": True},
        {"id": "far", "img": UW + "far.png", "scroll": 0.08, "y": 0, "tile": True},
        {"id": "midfar", "img": UW + "midfar.png", "scroll": 0.17, "y": 0, "tile": True},
        {"id": "head", "img": UW + "head.png", "scroll": 0.3, "x": HEAD_X, "y": 0, "tile": True},
        {"id": "headweeds", "img": UW + "headweeds.png", "scroll": 0.3, "x": HEAD_X, "y": 182, "tile": True,
         "shader": "sway", "shader_params": {"amp": 2.0, "speed": 0.55, "wavelength": 120.0, "power": 1.4, "bend": 0.12}},
        {"id": "kelp", "img": UW + "kelp.png", "scroll": 0.52, "y": 20, "tile": True,
         "shader": "sway", "shader_params": {"amp": 4.0, "speed": 0.5, "wavelength": 160.0, "power": 1.7, "bend": 0.05}},
        {"id": "main", "img": "main.png", "scroll": 1.0, "y": 0},
        {"id": "shafts", "img": "shafts.png", "scroll": 1.0, "y": 0, "alpha": 0.1, "z": -15},
        {"id": "front", "img": "front.png", "scroll": 1.2, "y": 0, "front": True},
    ]


def alpha_over(dst, src, k):
    """半透明层（alpha < 1）按 k 混上去。"""
    m = src[..., 3] > 0
    d = dst[..., :3].astype(float)
    d[m] = d[m] * (1 - k) + src[..., :3][m].astype(float) * k
    dst[..., :3] = d.astype(np.uint8)
    return dst


def comp_room(la, layers, cl, front):
    """按 room.json 的顺序合成（alpha < 1 的层按 alpha 混）；front 选人前 / 人后的层。"""
    out = np.zeros((H, 480, 4), np.uint8)
    for l, L in zip(la, layers):
        if bool(L.get("front")) != front:
            continue
        a = comp([l], cl)
        k = float(L.get("alpha", 1.0))
        if k < 1:
            alpha_over(out, a, k)
        else:
            over(out, a)
    return out


def layer_arrays(layers, folder):
    """把 room.json 的 layers 读成 comp() 要的 [(数组, scroll, x, y, tile)]（shader 编码图按调色板解）。"""
    out = []
    for L in layers:
        img = L["img"]
        p = img[len("res://"):] if img.startswith("res://") else str((folder / img).relative_to(ROOT))
        a = load(p)
        if L.get("shader_params", {}).get("palette_mode", False) or (L.get("shader") == "water" and "palette_mode" not in L.get("shader_params", {})):
            a = palette_decode(a, RA.GLINT_PAL)
        out.append((a, float(L.get("scroll", 1.0)), int(L.get("x", 0)), int(L.get("y", 0)), bool(L.get("tile", False))))
    return out


def obj_overlay(objs, states, cam_left, front=False):
    """物件按状态画到屏幕上（预览 / 取景框用）。"""
    out = np.zeros((H, 480, 4), np.uint8)
    for oid, (x, y, frames, ex) in objs.items():
        st = states.get(oid, "default")
        idx = ex["states"].get(st, 0)
        if isinstance(idx, list):
            idx = idx[0]
        a = frames[idx]
        sx = x - cam_left
        cvs = Cv(480, H)
        cvs.paste(a, sx, y)
        m = cvs.a[..., 3] > 0
        out[m] = cvs.a[m]
    return out


def over(dst, src):
    m = src[..., 3] > 0
    dst[m] = src[m]
    return dst


def write_room(folder, cfg, objs):
    folder.mkdir(parents=True, exist_ok=True)
    ob = {}
    for oid, (x, y, frames, ex) in objs.items():
        Image.fromarray(strip(frames)).save(folder / f"{oid}.png")
        h, w = frames[0].shape[:2]
        d = {"x": int(x), "y": int(y), "w": int(w), "h": int(h), "frames": len(frames)}
        d.update(ex)
        ob[oid] = d
    cfg["objects"] = ob
    (folder / "room.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n")


def build_warehouse(prev=None):
    folder = OUT / "warehouse"
    folder.mkdir(parents=True, exist_ok=True)
    main, _ = wh_main()
    wh_props(main)
    main.save(folder / "main.png")
    wh_shafts().save(folder / "shafts.png")
    wh_front().save(folder / "front.png")
    for old in ("back.png", "back.png.import"):                    # 旧版的后墙层不用了
        if (folder / old).exists():
            (folder / old).unlink()
    for old in ("warehouse_cabinet.png", "warehouse_cabinet.png.import"):   # 设备柜画在主层上（旧版留下的没用的图）
        if (folder / old).exists():
            (folder / old).unlink()
    objs = wh_objects()
    layers = wh_layers()
    cfg = {
        "_note": "tools/river_warehouse_bridge_art.py 生成，别手改。约定见 docs/river_rooms_contract.md。远景层是原来的水底（art/underwater）。",
        "size": [WH_W, H],
        "env": "underwater",
        "bg": ["#16242b", "#0d161b"],
        "layers": layers,
        "ground": WH_FLOOR,
        "markers": {
            "warehouse_cabinet_top": 534, "warehouse_cabinet_foot": 478, "warehouse_entry": 40, "warehouse_niff": 72,
            "warehouse_rope": 40, "warehouse_boxes": 368, "warehouse_broken_box": 284, "warehouse_float": 442,
            "warehouse_tall_cabinet": 500, "warehouse_furniture": 527, "warehouse_inner_door": 550,
            "warehouse_cabinet": 598, "warehouse_sluice_door": 664, "warehouse_exit_light": 33,
            "warehouse_knot_1": 230, "warehouse_knot_2": 420,
        },
        "walk": [24, 690],
        "rope": {"prop": "warehouse_rope", "on": "on", "anchor": [33, WH_ROPE_Y], "end": 686, "color": WH_ROPE,
                 "knots": [230, 420]},
        "portals": [{"to": "oldstreet", "at": "oldstreet_warehouse_entry", "kind": "pan_up", "x": 33}],
        "ambient": [{"name": "underwater", "db": -8}],
        "scripts": [{"script": "res://scripts/underwater_motes.gd", "x": 0, "y": 0, "z": -12,
                     "params": {"count": 40, "area": [0, 40, WH_W, 190]}}],
    }
    write_room(folder, cfg, objs)
    if prev:
        la = layer_arrays(layers, folder)
        shots = {
            "wh_enter": (0, 60, {}),
            "wh_boxes": (120, 330, {"warehouse_broken_box": "spilled"}),
            "wh_cabinet": (240, 470, {}),
            "wh_lifted": (240, 520, {"warehouse_tall_cabinet": "lifted", "warehouse_float": "tied_warehouse_cabinet_top",
                                     "warehouse_furniture": "loose", "warehouse_knot_2": "lit"}),
            "wh_moved": (240, 600, {"warehouse_tall_cabinet": "lifted", "warehouse_float": "tied_warehouse_cabinet_top",
                                    "warehouse_furniture": "moved", "warehouse_inner_door": "open"}),
            "wh_tilt": (240, 450, {"warehouse_tall_cabinet": "tilt_wrong", "warehouse_float": "tied_warehouse_cabinet_foot"}),
        }
        for name, (cl, chx, st) in shots.items():
            img = comp_room(la, layers, cl, False)
            img = over(img, obj_overlay(objs, st, cl))
            stand_in(img, chx - cl, WH_FLOOR)
            img = over(img, comp_room(la, layers, cl, True))
            big(img, 2).save(Path(prev) / f"{name}.png")
    return objs


# =========================================================================== 南桥 + 货台
SB_W = 1500
SB_G = 228                       # 泥滩（桥下）
DOCK_Y = 196                     # 货台台面
SB_GROUND = [[0, 212], [60, 212], [120, 228], [1186, 228], [1194, 220], [1202, 212], [1210, 204], [1218, 196], [1500, 196]]
DECK = 58                        # 桥面（= 拱肩里那几户的屋顶）
SPRING = 150                     # 拱脚
ARCHES = [(310, 120, 72), (590, 120, 72), (850, 100, 68)]   # (中心 x, 半跨, 矢高)
RING = 9                         # 券石那一圈的厚度
PIERS = [(150, 190), (430, 470), (710, 750), (950, 990)]
BRIDGE = (130, 1030)
OLD_WATER = 176                  # 影像里那时候的水位（桥墩上一道水线）
LAMPS = [244, 522, 800]          # 桥面上的灯柱（522 = 影像里挂浮灯的那根，marker southbridge_lamp_post）
VIEW_CAM = 352                   # 取景框：镜头左边缘
VIEW_SPOT = 592

STONE = [blue(v, None, 256) for v in (0.075, 0.095, 0.12, 0.145, 0.175, 0.21, 0.26, 0.32)]
PLAST = [col(v, 0.016, 236) for v in (0.15, 0.185, 0.215, 0.245, 0.29)]
ROOF = [blue(v, 0.02, 262) for v in (0.1, 0.14, 0.19, 0.25)]
MUD = [blue(v, 0.03, 262) for v in (0.06, 0.08, 0.1, 0.125, 0.16, 0.22)]
GLASS = blue(0.16, 0.03, 250)
MOSS = [col(v, 0.03, 190) for v in (0.12, 0.17, 0.22)]


def sb_ground(x):
    xs = [p[0] for p in SB_GROUND]
    ys = [p[1] for p in SB_GROUND]
    return int(round(np.interp(x, xs, ys)))


def arch_open(cx, hs, rise, w=SB_W):
    """拱洞里空的那一块（拱脚以下一直到地面）。"""
    yy, xx = np.mgrid[0:H, 0:w]
    t = (xx - cx) / hs
    top = SPRING - rise * np.sqrt(np.clip(1 - t * t, 0, 1))
    return (np.abs(t) < 1) & (yy >= top)


def ring_mask(cx, hs, rise, t, w=SB_W):
    """拱圈（券石那一圈）：拱洞外 t 像素厚，拱脚以上。"""
    yy, xx = np.mgrid[0:H, 0:w]
    inner = ((xx - cx) / hs) ** 2 + ((yy - SPRING) / rise) ** 2
    outer = ((xx - cx) / (hs + t)) ** 2 + ((yy - SPRING) / (rise + t)) ** 2
    return (inner >= 1) & (outer < 1) & (yy <= SPRING)


SPAL = bm.STONE                  # 桥、人家：河岸会话的「住处的石头」（比码头亮一点、往青灰偏）
RPAL = bm.ROCK                   # 河堤、挡土墙、货台：码头那种暗石头


def sb_main():
    rng = np.random.default_rng(5)
    cv = Cv(SB_W, H)
    yy, xx = np.mgrid[0:H, 0:SB_W]
    a0, a1 = BRIDGE
    holes = np.zeros((H, SB_W), bool)
    rings = np.zeros((H, SB_W), bool)
    for cx, hs, rise in ARCHES:
        holes |= arch_open(cx, hs, rise)
        rings |= ring_mask(cx, hs, rise, RING)
    body = (xx >= a0) & (xx < a1) & (yy >= DECK + 6) & (yy <= SB_G) & ~holes
    # 桥墩（拱脚以下）：一根根整石，底下 30 像素往外扩成分水尖
    piers = np.zeros_like(body)
    for p0, p1 in PIERS:
        widen = np.clip((yy - (SB_G - 30)) / 7.0, 0, 4).astype(int)
        pm = (xx >= p0 - widen) & (xx <= p1 + widen) & (yy > SPRING) & (yy <= SB_G)
        piers |= pm
        stone_mass(cv, pm, rng, RPAL, cracks=3, strata=2)
    for pm in ((xx >= a0) & (xx < PIERS[0][0]) & (yy > SPRING) & (yy <= SB_G),
               (xx > PIERS[-1][1]) & (xx < a1) & (yy > SPRING) & (yy <= SB_G)):
        piers |= pm
        stone_mass(cv, pm, rng, RPAL, cracks=3, strata=2)
    body |= piers
    # 拱肩：一整块大石头里凿出来的人家（每一块各自上色，边上受光），门窗是凿的洞
    spand = body & ~rings & (yy <= SPRING) & (yy > DECK + 6)
    lab, n = RA.components(spand)
    for k in range(1, n + 1):
        stone_mass(cv, lab == k, rng, SPAL, cracks=3, strata=2)
    for i, (p0, p1) in enumerate(PIERS):
        house_in_spandrel(cv, (p0 + p1) // 2, i, rng, spand)
    # 拱圈：一圈放射的大块券石（每块 15°，宽窄、深浅不一），右上半边（迎着月亮）亮；擦痕刻在这圈石沿上（物件）
    pal = np.array([RA.rgba(c) for c in SPAL], np.uint8)
    for cx, hs, rise in ARCHES:
        rm = ring_mask(cx, hs, rise, RING)
        ang = np.degrees(np.arctan2(-(yy - SPRING) / (rise + RING / 2), (xx - cx) / (hs + RING / 2)))
        jit = np.array([0, 3, -2, 4, -3, 1, 2, -4, 3, 0, -2, 4, 1])
        seg = np.floor((ang + jit[np.clip((ang // 15).astype(int), 0, 12)]) / 15).astype(int)
        seam = np.abs(np.diff(seg, axis=1, prepend=seg[:, :1])) > 0
        r_in = ((xx - cx) / hs) ** 2 + ((yy - SPRING) / rise) ** 2
        lit = ang < 85
        tone = (seg * 7) % 3
        lv = np.where(lit, 3, 2) + (tone == 0) * 1 - (tone == 2) * 1
        lv = np.where(r_in < 1.05, lv + 1, lv)
        lv = lv + (BAYER[yy % 4, xx % 4] - 0.5) * 0.6
        lv = np.where(seam, 0, lv)
        idx = np.clip(np.round(lv), 0, len(SPAL) - 1).astype(int)
        cv.a[rm] = pal[idx[rm]]
        outer = ((xx - cx) / (hs + RING)) ** 2 + ((yy - SPRING) / (rise + RING)) ** 2
        cv.fill(rm & (outer > 0.93) & ~lit, SPAL[0])               # 券石外沿的缝
        sh = arch_open(cx, hs, rise) & (r_in > 0.955) & (r_in < 1.0) & (yy < SPRING - 2)
        cv.fill(sh, SPAL[0])                                       # 拱腹里贴着石沿的一条影
    # 桥墩上的旧水位线：线以下深一档、挂着干水草，线上一道发白的泥壳
    below = piers & (yy > OLD_WATER)
    lighten(cv, below, -0.03)
    for x in range(a0, a1):
        if piers[OLD_WATER, x]:
            cv.put(x, OLD_WATER, col(0.3, 0.018, 95))
            cv.put(x, OLD_WATER + 1, col(0.22, 0.016, 90))
            if rng.random() < 0.35:
                for k in range(int(rng.integers(1, 6))):
                    if piers[OLD_WATER + 2 + k, x]:
                        cv.put(x, OLD_WATER + 2 + k, MOSS[1] if k < 2 else MOSS[0])
    for p0, p1 in PIERS:                                           # 墩子顶上压一条长石（拱脚）
        cv.rect(p0 - 3, SPRING + 1, p1 + 3, SPRING + 3, SPAL[3])
        cv.rect(p0 - 3, SPRING + 1, p1 + 3, SPRING + 1, SPAL[5])
        cv.rect(p0 - 3, SPRING + 4, p1 + 3, SPRING + 4, SPAL[0])
    # 桥面：一整条厚石板（挑出去一点，顶上长苔）——它就是拱肩里这几户的屋顶；屋脊上一排小石像，远看像栏杆
    r = rc(cv)
    for x in range(a0 - 6, a1 + 6):
        y0 = DECK - 1 + int(round(0.6 * np.sin(x / 11.0)))
        for d in range(8):
            k = 4 if d == 0 else (3 if d < 2 else (2 if d < 6 else (1 if d < 7 else 0)))
            cv.put(x, y0 + d, SPAL[k])
        if rng.random() < 0.45:
            cv.put(x, y0 - 1, bm.MOSS[1 if rng.random() < 0.6 else 2])
        if rng.random() < 0.06:
            for d in range(1, int(rng.integers(2, 6))):
                cv.put(x, y0 + 7 + d, bm.MOSS[0])
    for x in range(a0 + 4, a1 - 3, 12):
        figure(cv, x, DECK - 1, rng)
    for lx in LAMPS:
        lamp_post(cv, lx, DECK - 1)
    # ---- 左岸：粗石河堤 + 台阶（往回走 = 旧街）、一盏石灯笼
    lm = np.zeros((H, SB_W), bool)
    for x in range(0, 136):
        g = sb_ground(x)
        if x >= a0 and g >= SB_G:
            continue
        lm[g:, x] = True
    stone_mass(cv, lm, rng, RPAL, cracks=3, strata=2)
    for x in range(0, 136):
        g = sb_ground(x)
        if lm[g, x]:
            cv.put(x, g, RPAL[4])
    for i in range(6):
        sx = 60 + i * 10
        g = sb_ground(sx)
        cv.rect(sx, g, sx + 9, g + 1, RPAL[3])
        cv.rect(sx, g, sx + 9, g, RPAL[4])
    bm.stone_lantern(r, 96, sb_ground(96))
    # ---- 右边：挡土墙（整块岩壁）+ 旧运输水道的石拱洞口（洞口是物件 southbridge_waterway）+ 墙头一块凿出来的巨石屋
    wall = (xx >= a1) & (xx < 1186) & (yy >= 132) & (yy <= SB_G)
    stone_mass(cv, wall, rng, RPAL, cracks=5, strata=3)
    tunnel = arch_open(1100, 40, 34) & (yy <= SB_G) & (yy >= 100)
    cv.fill(tunnel, blue(0.05))
    rm = ring_mask(1100, 40, 34, 7)
    ang = np.degrees(np.arctan2(-(yy - SPRING), (xx - 1100)))
    seg = np.floor(ang / 20).astype(int)
    seam = np.abs(np.diff(seg, axis=1, prepend=seg[:, :1])) > 0
    lv = np.where(ang < 85, 4, 2) + (seg % 2) * 0.6 + (BAYER[yy % 4, xx % 4] - 0.5) * 0.5
    lv = np.where(seam, 0, lv)
    idx = np.clip(np.round(lv), 0, len(SPAL) - 1).astype(int)
    cv.a[rm] = pal[idx[rm]]
    cv.rect(1056, SPRING, 1059, SB_G, RPAL[1])
    cv.rect(1141, SPRING, 1144, SB_G, RPAL[3])
    low_house(cv, 1028, rng)
    # ---- 货台：粗石台阶和台面、背后一间长的石屋（大块粗石墙 + 压顶的厚石板）、石系船桩、一盏还亮着的灯
    dm = np.zeros((H, SB_W), bool)
    for x in range(1186, SB_W):
        dm[sb_ground(x):, x] = True
    stone_mass(cv, dm, rng, RPAL, cracks=4, strata=3)
    for x in range(1186, SB_W):
        g = sb_ground(x)
        cv.put(x, g, RPAL[4])
    for i in range(4):
        sx = 1186 + i * 8
        cv.rect(sx, sb_ground(sx + 4) + 1, sx, sb_ground(sx + 4) + 8, RPAL[0])
    dock_shed(cv, rng)
    # ---- 泥滩（蓝黑，和河岸的地一路）：上沿一条被月光擦亮的湿泥，往下很快沉进黑
    for x in range(120, 1186):
        g = SB_G
        for y in range(g + 1, H):
            t = (y - g) / (H - g)
            k = 3.0 - t * 3.6 + (BAYER[y % 4, x % 4] - 0.5) * 0.9
            cv.put(x, y, MUD[int(np.clip(np.floor(k), 0, 4))])
        cv.put(x, g, MUD[5])
        cv.put(x, g + 1, MUD[4])
    for _ in range(46):                                              # 积水的小水洼（映着天，亮一档）
        x = int(rng.integers(130, 1170))
        y = int(rng.integers(SB_G + 7, H - 6))
        w = int(rng.integers(8, 30))
        cv.rect(x, y, x + w, y, blue(0.17, 0.035, 252))
        cv.rect(x + 2, y + 1, x + w - 3, y + 1, blue(0.13, 0.035, 256))
        if rng.random() < 0.4:
            cv.rect(x + w // 3, y, x + w // 3 + 2, y, blue(0.27, 0.035, 248))
    for _ in range(140):                                             # 卵石：顶上一点亮
        x = int(rng.integers(120, 1186))
        y = int(rng.integers(SB_G + 3, H - 2))
        cv.rect(x, y, x + 1, y, MUD[4])
        cv.put(x, y + 1, MUD[0])
    fallen_float_lamp(cv, 474, SB_G)
    return cv, holes


def house_in_spandrel(cv, cx, i, rng, spand):
    """拱肩这块大石头里凿出来的一户：两扇拱窗（有的透暖黄）、一扇小门洞、门口凿出的一条窄台阶；窗下一根晾衣绳。"""
    r = rc(cv)
    lit = [(i % 2 == 0), (i != 1)]
    wy = DECK + 14
    inner = 0 < i < len(PIERS) - 1
    xs = (cx - 14, cx + 6) if inner else (cx - 4,)
    for j, wx in enumerate(xs):
        if not spand[wy - 1:wy + 14, wx - 1:wx + 10].all():
            continue
        bm.carve(r, wx, wy, 8, 12, "arch", lit[j % 2], False, pal=SPAL)
    if inner:
        dy = wy + 36
        if spand[dy:dy + 16, cx - 5:cx + 6].all():
            bm.carve(r, cx - 4, dy, 8, 14, "arch", i == 2, True, pal=SPAL)
            cv.rect(cx - 9, dy + 14, cx + 9, dy + 15, SPAL[4])         # 门口凿出的一条窄台
            cv.rect(cx - 9, dy + 14, cx + 9, dy + 14, SPAL[5])
        ly = wy + 22
        x0, x1 = cx - 26, cx + 26
        while not spand[ly, x0]:
            x0 += 1
        while not spand[ly, x1]:
            x1 -= 1
        cv.line(x0, ly, x1, ly + 1, ROPE_C)
        for bx, bw, bc in ((cx - 12, 6, col(0.3, 0.03, 20)), (cx + 4, 5, col(0.32, 0.03, 195))):
            cv.rect(bx, ly + 1, bx + bw, ly + 6, bc)


def figure(cv, x, base, rng):
    """屋脊上的小石像（蹲着的兽 / 坐着的小人 / 圆顶小石柱）：5×7 的剪影，右边一条亮边。"""
    kind = int(rng.integers(0, 3))
    c, cl, cd = SPAL[3], SPAL[5], SPAL[1]
    cv.rect(x - 1, base - 1, x + 3, base, cd)
    if kind == 0:
        cv.rect(x - 1, base - 5, x + 2, base - 2, c)
        cv.rect(x, base - 7, x + 2, base - 6, c)
        cv.put(x + 3, base - 7, c)
    elif kind == 1:
        cv.rect(x, base - 5, x + 2, base - 2, c)
        cv.rect(x, base - 8, x + 1, base - 7, c)
    else:
        cv.rect(x, base - 6, x + 2, base - 2, c)
        cv.put(x + 1, base - 7, c)
    for y in range(base - 8, base - 1):
        for xx in range(x + 3, x - 2, -1):
            if cv.a[y, xx, 3] and tuple(cv.a[y, xx, :3]) == tuple(c[:3]):
                cv.put(xx, y, cl)
                break


def lamp_post(cv, x, base):
    """桥上的灯柱：一根细石柱（方座、柱身、宽顶石），柱头凿空成灯室，四面小窗透暖黄；右边伸出一个挂浮灯绳的石钩。"""
    top = 18
    cv.rect(x - 3, base - 4, x + 4, base, SPAL[2])
    cv.rect(x - 3, base - 4, x + 4, base - 4, SPAL[4])
    cv.rect(x - 1, top + 10, x + 2, base - 4, SPAL[2])
    cv.rect(x + 2, top + 10, x + 2, base - 4, SPAL[4])
    cv.rect(x - 1, top + 10, x - 1, base - 4, SPAL[1])
    cv.rect(x - 3, top + 1, x + 4, top + 9, SPAL[2])
    cv.rect(x - 2, top + 3, x + 3, top + 7, bm.WARM[3])
    cv.rect(x, top + 4, x + 1, top + 6, bm.WARM[4])
    cv.rect(x + 4, top + 1, x + 4, top + 9, SPAL[4])
    cv.poly([(x - 5, top + 1), (x + 1, top - 4), (x + 6, top + 1)], SPAL[3])
    cv.line(x + 1, top - 4, x + 6, top + 1, SPAL[5])
    cv.rect(x + 3, top + 11, x + 5, top + 12, SPAL[4])                # 石钩
    cv.put(x + 5, top + 13, SPAL[4])
    bm.glow(rc(cv), x + 0.5, top + 5, 9)


def low_house(cv, cx, rng):
    """右桥头（挡土墙上）一块凿出来的巨石屋：一扇亮着的拱窗、一扇门洞；石头顶上一排小石像离地面近（marker southbridge_ornament）。"""
    r = rc(cv)
    x0, y0 = bm.boulder_house(r, cx, 131, 64, 46, 77,
                              openings=[("arch", 14, 16, 9, 13, True, False), ("arch", 38, 0, 10, 18, False, True)], pal=SPAL)
    for k in range(5):
        fx = x0 + 10 + k * 11
        col_ = cv.a[:, fx, 3]
        ys = np.nonzero(col_[y0:132])[0]
        if len(ys):
            big_figure(cv, fx, y0 + ys[0] - 1, k)


def big_figure(cv, x, base, k):
    c, cl, cd = SPAL[3], SPAL[5], SPAL[1]
    cv.rect(x - 2, base - 1, x + 3, base, cd)
    if k % 2 == 0:   # 蹲兽：耳朵、背、尾巴卷
        cv.rect(x - 2, base - 6, x + 2, base - 2, c)
        cv.rect(x - 1, base - 9, x + 2, base - 7, c)
        cv.put(x - 1, base - 10, c)
        cv.put(x + 2, base - 10, c)
        cv.rect(x + 3, base - 5, x + 3, base - 3, c)
        cv.rect(x + 2, base - 9, x + 2, base - 7, cl)
        cv.put(x, base - 8, cd)
    else:            # 小人：抱着膝盖
        cv.rect(x - 1, base - 6, x + 2, base - 2, c)
        cv.rect(x - 1, base - 9, x + 1, base - 7, c)
        cv.rect(x + 2, base - 6, x + 2, base - 2, cl)
        cv.put(x + 1, base - 9, cl)


def fallen_float_lamp(cv, x, g):
    """泥里歪着一盏不亮的浮灯：小木托 + 一根杆 + 玻璃罩。"""
    cv.rect(x, g - 2, x + 12, g, WOOD[2])
    cv.rect(x, g - 2, x + 12, g - 2, WOOD[4])
    cv.line(x + 6, g - 3, x + 10, g - 12, IRON[2])
    cv.rect(x + 9, g - 16, x + 13, g - 12, GLASS)
    cv.rect(x + 9, g - 16, x + 13, g - 16, IRON[4])
    cv.put(x + 11, g - 14, WARM4)


def dock_shed(cv, rng):
    """货台背后一整块岩体，凿出来的货棚：顶是起伏的石头（长苔、几缕垂叶），一个凿出的大拱门洞（里面黑），
    航线图贴着的那一块磨平的石面、编号牌那一条凿进去的暗槽、门边一盏还亮着的挂灯、石头系船桩。"""
    r = rc(cv)
    x0, x1 = 1226, SB_W
    m = np.zeros((H, SB_W), bool)
    prof = smooth1d(x1 - x0, np.random.default_rng(91), 60, 5.0)
    for i, x in enumerate(range(x0, x1)):
        u = min(1.0, (x - x0) / 26.0)
        top = int(74 + prof[i] + 26 * (1 - np.sqrt(max(0.0, 1 - (1 - u) ** 2))))
        m[top:DOCK_Y + 1, x] = True
    stone_mass(cv, m, rng, SPAL, cracks=7, strata=4)
    for x in range(x0, x1):                                           # 顶上一层苔
        ys = np.nonzero(m[:, x])[0]
        if len(ys) and rng.random() < 0.55:
            cv.put(x, ys[0], bm.MOSS[2] if rng.random() < 0.4 else bm.MOSS[1])
            if rng.random() < 0.15:
                for d in range(1, int(rng.integers(2, 8))):
                    cv.put(x, ys[0] + d, bm.MOSS[0])
    bm.carve(r, 1236, 132, 44, 64, "arch", False, True, pal=SPAL)    # 大门洞
    cv.rect(1290, 86, 1412, 188, SPAL[1])                             # 航线图原来贴着的一块（磨平的石面）
    cv.rect(1291, 87, 1411, 187, SPAL[2])
    cv.rect(1414, 102, 1474, 126, SPAL[0])                            # 编号牌那一条（凿进去的暗槽）
    cv.rect(1414, 126, 1474, 126, SPAL[4])
    for px in (1420, 1440, 1460):
        cv.rect(px - 1, 104, px, 105, IRON[4])
    bm.lantern(r, 1484, 100, "hang", r=10)
    for bx in (1240, 1330, 1450):                                     # 石系船桩
        cv.rect(bx, DOCK_Y - 9, bx + 6, DOCK_Y, RPAL[2])
        cv.rect(bx - 1, DOCK_Y - 11, bx + 7, DOCK_Y - 9, RPAL[3])
        cv.rect(bx - 1, DOCK_Y - 11, bx + 7, DOCK_Y - 11, RPAL[4])
        cv.rect(bx + 6, DOCK_Y - 9, bx + 6, DOCK_Y, RPAL[4])


MID_W = 1100
MID_BANK = 200                   # 中景：对面那条泥岸的上沿（桥洞里看过去，河在它后面）


def statue_mask(w, h, kind, rng):
    """立在浅水里的石像（和水底的石头人头一路）：披袍的人 / 抱膝坐着的 / 只剩一颗头。脚底在最底一行。"""
    cv = Cv(w, h)
    cx = w // 2
    if kind == "robe":
        hr = w * 0.16
        cv.fill(cv.mask_of_ellipse(cx - hr, 2, cx + hr, 2 + hr * 2.3), (1, 1, 1))
        cv.poly([(cx - w * 0.22, 2 + hr * 2.1), (cx + w * 0.24, 2 + hr * 2.1), (cx + w * 0.42, h - 1), (cx - w * 0.4, h - 1)], (1, 1, 1))
    elif kind == "sit":
        hr = w * 0.15
        cv.fill(cv.mask_of_ellipse(cx - hr + 3, 4, cx + hr + 3, 4 + hr * 2.2), (1, 1, 1))
        cv.fill(cv.mask_of_ellipse(cx - w * 0.38, h * 0.3, cx + w * 0.36, h + 6), (1, 1, 1))
    else:   # head
        cv.fill(cv.mask_of_ellipse(4, 2, w - 4, h + h * 0.2), (1, 1, 1))
        cv.poly([(w - 6, h * 0.45), (w - 1, h * 0.55), (w - 5, h * 0.62)], (1, 1, 1))   # 鼻子
    m = cv.a[..., 3] > 0
    m[h - 1:, :] |= False
    return m


def sb_mid():
    rng = np.random.default_rng(17)
    cv = Cv(MID_W, H)
    # 对面的泥岸（桥洞里看得见的那一条）：上沿受光，往下沉进暗里
    prof = smooth1d(MID_W, rng, 80, 2.0)
    for x in range(MID_W):
        top = int(MID_BANK + prof[x])
        cv.put(x, top, MUD[4])
        cv.put(x, top + 1, MUD[3])
        for y in range(top + 2, H):
            t = (y - top) / 30
            k = 2.6 - t * 2.5 + (BAYER[y % 4, x % 4] - 0.5) * 0.8
            cv.put(x, y, MUD[int(np.clip(np.floor(k), 0, 3))])
    # 石像：立在河里（脚下一圈水线），互相隔得很开
    pal = [blue(v, None, 256) for v in (0.1, 0.14, 0.19, 0.25, 0.31, 0.38)]
    for sx, w, h, kind, seed in ((250, 26, 64, "robe", 1), (452, 30, 78, "robe", 2), (660, 34, 40, "head", 3), (860, 30, 52, "sit", 4)):
        r = np.random.default_rng(seed)
        m = statue_mask(w, h, kind, r)
        img = shade_rock(m, r, pal, cracks=(1, 3), seams=False)
        base = MID_BANK - 6
        cv.paste(img, sx - w // 2, base - h + 1)
        for x in range(sx - w // 2 - 3, sx + w // 2 + 4):          # 水线：一道亮的小涟漪
            if (x + seed) % 3:
                cv.put(x, base + 1, blue(0.36, 0.03, 246))
    # 石系船桩 + 柱头上一盏暖灯；一条小船
    for px in (360, 760):
        cv.rect(px - 1, MID_BANK - 22, px + 3, MID_BANK, pal[2])
        cv.rect(px + 3, MID_BANK - 22, px + 3, MID_BANK, pal[4])
        cv.rect(px - 2, MID_BANK - 24, px + 4, MID_BANK - 22, pal[3])
        cv.rect(px, MID_BANK - 29, px + 2, MID_BANK - 25, WARM2)
        cv.put(px + 1, MID_BANK - 28, WARM)
    bx = 556
    cv.poly([(bx, MID_BANK - 6), (bx + 34, MID_BANK - 6), (bx + 28, MID_BANK - 1), (bx + 5, MID_BANK - 1)], WOOD[1])
    cv.line(bx, MID_BANK - 6, bx + 34, MID_BANK - 6, WOOD[4])
    cv.line(bx + 34, MID_BANK - 6, bx + 46, MID_BANK - 24, ROPE_C)
    return cv


def sb_front():
    """前景（1.3）：画面最下沿几丛近黑的芦苇 / 香蒲和一根歪的木桩，稀稀拉拉。"""
    w = 480 + int((SB_W - 480) * 1.3) + 8
    cv = Cv(w, H)
    rng = np.random.default_rng(23)
    dk = [blue(0.045), blue(0.065), blue(0.085)]
    for x0 in (40, 330, 700, 1020, 1380, 1700):
        n = int(rng.integers(5, 10))
        for k in range(n):
            x = x0 + int(rng.integers(-14, 14))
            hgt = int(rng.integers(18, 52))
            lean = rng.uniform(-0.25, 0.25)
            for t in range(hgt):
                cv.rect(int(x + lean * t), H - 1 - t, int(x + lean * t), H - 1 - t, dk[1])
            if rng.random() < 0.35:                                   # 香蒲头
                tx = int(x + lean * hgt)
                cv.rect(tx - 1, H - hgt - 6, tx + 1, H - hgt, dk[2])
        cv.rect(x0 - 18, H - 6, x0 + 18, H - 1, dk[0])
    cv.poly([(560, H), (566, H - 70), (572, H - 70), (574, H)], dk[0])   # 歪木桩
    cv.rect(564, H - 72, 573, H - 69, dk[2])
    return cv


DIGITS = {"0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
          "2": ["111", "001", "111", "100", "111"], "7": ["111", "001", "010", "010", "010"]}


def sb_objects():
    out = {}
    # ---- 中间桥洞的擦痕 + 勾在石头上的粗毛（scratches）
    cx, hs, rise = ARCHES[1]
    fr = [Cv(124, 40).a.copy()]
    c = Cv(124, 40)
    ox, oy = cx - 62, SPRING - rise - 12
    for k in range(48, 133, 7):                                       # 券石上一道道发白的擦痕（离地这么高）
        ang = np.radians(k)
        for r in (1, 3, 5):
            x = cx + (hs + r) * np.cos(ang) - ox
            y = SPRING - (rise + r) * np.sin(ang) - oy
            c.put(x, y, col(0.5, 0.012, 90))
            c.put(x + 1, y, col(0.42, 0.012, 90))
    for k, ln in ((70, 6), (96, 8), (112, 5)):                        # 粗毛：几根灰黑的长毛挂下来
        ang = np.radians(k)
        x = int(cx + hs * np.cos(ang) - ox)
        y = int(SPRING - rise * np.sin(ang) - oy) + 1
        for t in range(ln):
            c.put(x + (t // 3) % 2, y + t, col(0.3, 0.01, 60))
    fr.append(c.a.copy())
    out["southbridge_arch"] = (ox, oy, fr, {"states": {"default": 0, "scratches": 1}, "click": [560, 100, 60, 128]})
    # ---- 泥滩脚印：default 只是几块浅坑；seen = 坑里积着水，边上一圈亮（看得出是脚印）
    fr = []
    for seen in (False, True):
        c = Cv(150, 14)
        for i, px in enumerate(range(8, 146, 30)):
            py = 3 if i % 2 else 7
            c.fill(c.mask_of_ellipse(px - 6, py - 2, px + 6, py + 3), MUD[1] if not seen else blue(0.17, 0.03, 250))
            if seen:
                c.fill(c.mask_of_ellipse(px - 4, py - 1, px + 4, py + 2), blue(0.24, 0.03, 248))
                c.rect(px - 5, py - 3, px + 5, py - 3, MUD[5])
                for t in (-4, 0, 4):                                    # 趾印
                    c.rect(px + t, py + 4, px + t + 1, py + 4, MUD[0])
            else:
                c.rect(px - 5, py - 3, px + 5, py - 3, MUD[3])
        fr.append(c.a.copy())
    out["southbridge_footprints"] = (520, SB_G + 1, fr, {"states": {"default": 0, "seen": 1}})
    # ---- 旧运输水道：default 洞口堆着塌下来的石块、上面垂着一帘干水草；revealed = 石块挪到两边，里面很远有一点暖光（货台的灯）
    fr = []
    for rev in (False, True):
        c = Cv(100, 92)
        ox, oy = 1050, 138
        r = np.random.default_rng(8)
        if not rev:
            for (bx, by, bw, bh) in ((1062, 196, 26, 32), (1086, 190, 30, 38), (1114, 200, 24, 28), (1074, 170, 22, 24),
                                     (1100, 168, 20, 24), (1088, 152, 18, 18)):
                m = bm.blob_mask(bw, bh, r)
                c.paste(bm.shade_mass(m, r, RPAL, cracks=1, strata=0), bx - ox, by - oy)
            for x in range(1062, 1140, 2):                              # 垂下来的干水草
                ln = int(r.integers(4, 22))
                for t in range(ln):
                    c.put(x - ox + (t // 5) % 2, 150 - oy + t, MOSS[1] if t < 6 else MOSS[0])
        else:
            for (bx, by, bw, bh) in ((1050, 204, 16, 24), (1134, 206, 16, 22)):
                m = bm.blob_mask(bw, bh, r)
                c.paste(bm.shade_mass(m, r, RPAL, cracks=1, strata=0), bx - ox, by - oy)
            c.rect(1099 - ox, 196 - oy, 1101 - ox, 198 - oy, WARM2)
            c.put(1100 - ox, 197 - oy, WARM)
            for x in range(1066, 1136):                                 # 水道底：一条暗的水
                c.put(x - ox, 226 - oy, blue(0.16, 0.03, 250))
        fr.append(c.a.copy())
    out["southbridge_waterway"] = (1050, 138, fr, {"states": {"default": 0, "revealed": 1}, "click": [1060, 150, 80, 78]})
    # ---- 航线图：default 贴在墙上（一张大纸，几条航线，最右一条通到云层星）；fallen = 掉在台面上卷着
    fr = []
    for fallen in (False, True):
        c = Cv(130, 116)
        ox, oy = 1286, 84
        if not fallen:
            c.rect(1294 - ox, 90 - oy, 1408 - ox, 182 - oy, MAP)
            c.rect(1408 - ox, 90 - oy, 1408 - ox, 182 - oy, MAP_D)
            c.rect(1294 - ox, 182 - oy, 1408 - ox, 182 - oy, MAP_D)
            c.poly([(1400 - ox, 182 - oy), (1408 - ox, 174 - oy), (1408 - ox, 182 - oy)], MAP_D)   # 卷起的一角
            c.rect(1298 - ox, 94 - oy, 1340 - ox, 97 - oy, INK)
            pts = [(1302, 160), (1330, 150), (1356, 128), (1380, 120), (1398, 104)]
            for (a, b), (cc, d) in zip(pts, pts[1:]):
                c.line(a - ox, b - oy, cc - ox, d - oy, INK)
            for a, b in pts[:-1]:
                c.rect(a - ox - 1, b - oy - 1, a - ox + 1, b - oy + 1, INK)
            c.fill(c.mask_of_ellipse(1393 - ox, 99 - oy, 1404 - ox, 110 - oy), TAG)     # 终点：云层星（琥珀色的圆）
            c.line(1302 - ox, 160 - oy, 1340 - ox, 176 - oy, MAP_D)
            c.line(1302 - ox, 160 - oy, 1320 - ox, 128 - oy, MAP_D)
            for nx in (1296, 1406):
                c.rect(nx - ox, 92 - oy, nx + 1 - ox, 93 - oy, IRON[4])
        else:
            c.poly([(1300 - ox, 196 - oy), (1312 - ox, 170 - oy), (1340 - ox, 176 - oy), (1360 - ox, 196 - oy)], MAP_D)
            c.poly([(1312 - ox, 170 - oy), (1340 - ox, 176 - oy), (1332 - ox, 186 - oy), (1316 - ox, 182 - oy)], MAP)
            c.rect(1340 - ox, 193 - oy, 1400 - ox, 196 - oy, MAP)
            c.rect(1340 - ox, 196 - oy, 1400 - ox, 196 - oy, MAP_D)
            c.line(1344 - ox, 194 - oy, 1390 - ox, 194 - oy, INK)
            for nx in (1296, 1406):
                c.rect(nx - ox, 92 - oy, nx + 1 - ox, 93 - oy, IRON[4])
                c.put(nx - ox, 94 - oy, MAP)
        fr.append(c.a.copy())
    out["southbridge_routemap"] = (1286, 84, fr, {"states": {"default": 0, "fallen": 1}, "click": [1292, 88, 118, 108]})
    # ---- 编号牌 07 / 12 / 21：held = 取下来了（墙上只剩钉子）；back = 挂回去
    for num, px in (("07", 1420), ("12", 1440), ("21", 1460)):
        fr = []
        c = Cv(16, 14)
        c.rect(1, 2, 14, 13, PAPER)
        c.rect(14, 2, 14, 13, PAPER_D)
        c.rect(1, 13, 14, 13, PAPER_D)
        c.rect(1, 2, 14, 2, IRON[3])
        c.rect(7, 0, 8, 1, IRON[4])
        for d, ch in enumerate(num):
            for yy_, row in enumerate(DIGITS[ch]):
                for xx_, b in enumerate(row):
                    if b == "1":
                        c.put(3 + d * 5 + xx_, 5 + yy_, INK)
        fr.append(c.a.copy())
        fr.append(Cv(16, 14).a.copy())
        out[f"southbridge_plate_{num}"] = (px - 8, 105, fr, {"states": {"default": 0, "back": 0, "held": 1}})
    return out


RV = "res://art/river/"


def sb_layers():
    return [
        {"id": "sky", "img": RV + "sky.png", "scroll": 0.0, "y": 0},
        {"id": "ridge", "img": RV + "ridge.png", "scroll": 0.05, "y": 0, "tile": True},
        {"id": "mist", "img": RV + "mist.png", "scroll": 0.1, "y": 0, "tile": True},
        {"id": "shore", "img": RV + "shore.png", "scroll": 0.16, "y": 0, "tile": True},
        {"id": "ripples", "img": RV + "ripples.png", "scroll": 0.3, "y": 151, "tile": True, "shader": "water",
         "shader_params": {"palette_mode": False, "speed": 0.7, "wobble": 2.0, "flicker": 0.0, "show": 0.62}},
        {"id": "glints", "img": RV + "glints.png", "scroll": 0.0, "y": 155, "shader": "water",
         "shader_params": {"palette_mode": True, "speed": 1.0, "wobble": 2.0, "flicker": 0.9, "show": 0.6}},
        {"id": "water", "img": RV + "water.png", "scroll": 0.42, "y": 0, "tile": True},
        {"id": "mid", "img": "mid.png", "scroll": 0.6, "y": 0},
        {"id": "main", "img": "main.png", "scroll": 1.0, "y": 0},
        {"id": "front", "img": "front.png", "scroll": 1.3, "y": 0, "front": True},
    ]


def footage(img, rng):
    """把一帧合成图压成「影像」：那时候的高水位（线以下换成水、映着上面）、一串往中间桥洞歪的浮灯、一个灰影；
    偏冷的褪色、隔行暗一点、四角取景框。"""
    out = img.copy()
    wl = OLD_WATER
    lamp_sx = LAMPS[1] - VIEW_CAM
    arch_sx = ARCHES[1][0] - VIEW_CAM
    # 灰影：中间桥洞下半露出水面的一个大圆背（大象），很淡
    gm = Cv(480, H).mask_of_ellipse(arch_sx - 30, wl - 18, arch_sx + 22, wl + 14)
    gm |= Cv(480, H).mask_of_ellipse(arch_sx + 12, wl - 13, arch_sx + 32, wl + 5)
    yy, xx = np.mgrid[0:H, 0:480]
    gm &= yy < wl
    out[gm] = RA.rgba(blue(0.25, 0.01, 240))
    top = gm & ~np.roll(gm, 1, 0)
    out[top] = RA.rgba(blue(0.34, 0.01, 236))
    # 水：线以下 = 上面倒过来的影子压暗 + 水面的横纹
    for y in range(wl, H):
        src = 2 * wl - y - 1
        if src < 0:
            src = 0
        row = img[src].astype(float) * 0.45 + np.array(RA.rgba(blue(0.2, 0.03, 250)), float) * 0.55
        out[y, :, :3] = row[:, :3].astype(np.uint8)
        if (y - wl) % 5 == 0:
            for x in range(480):
                if (x * 7 + y * 3) % 11 < 6:
                    out[y, x, :3] = RA.rgba(blue(0.3, 0.03, 246))[:3]
    for x in range(480):
        out[wl, x, :3] = RA.rgba(blue(0.42, 0.03, 244))[:3]
    cv = Cv(480, H)
    cv.a = out
    # 浮灯：一串从灯柱上的小钩垂下来、漂向中间桥洞，每盏都往右（桥洞那边）歪
    hx, hy = lamp_sx + 5, 29
    pts = []
    for i in range(6):
        t = i / 5
        pts.append((int(lamp_sx + 14 + t * (arch_sx - 8 - lamp_sx - 14)), wl + int(round(1.5 * np.sin(t * 3.1)))))
    x0, y0 = pts[0]
    for k in range(41):                                               # 垂下来的那段绳（下垂的弧）
        t = k / 40
        x = hx + (x0 - hx) * t
        y = hy + (y0 - 6 - hy) * t ** 1.8
        cv.put(x, y, ROPE_C)
    for i, (x, y) in enumerate(pts):
        if i:
            px, py = pts[i - 1]
            cv.line(px + 3, py - 1, x - 4, y - 1, ROPE_C)
        cv.rect(x - 4, y - 1, x + 3, y, WOOD[3])                       # 小木托
        cv.rect(x - 4, y - 1, x + 3, y - 1, WOOD[4])
        cv.line(x - 1, y - 2, x + 3, y - 8, IRON[4])                   # 往右歪的杆
        for k in range(7):                                             # 灯罩跟着杆一起斜（每往上一行往右挪半格）
            cx_ = x + 3 + (k + 1) // 2
            cy_ = y - 9 - k
            cv.rect(cx_ - 1, cy_, cx_ + 1, cy_, IRON[2] if k in (0, 6) else WARM2)
            if 2 <= k <= 4:
                cv.put(cx_, cy_, WARM)
        for k in range(1, 4):                                          # 灯在水里的倒影
            cv.put(x + 5 + (k % 2), y + 1 + k * 2, WARM3)
    out = cv.a
    # 褪色 + 偏冷 + 隔行
    f = out[..., :3].astype(float)
    lum = f @ np.array([0.3, 0.55, 0.15])
    f = f * 0.55 + lum[..., None] * 0.45
    f = f * np.array([0.92, 0.98, 1.06]) + 6
    f[::2] *= 0.88
    out[..., :3] = np.clip(f, 0, 255).astype(np.uint8)
    out[..., 3] = 255
    cv.a = out
    br = blue(0.7, 0.01, 240)
    for (x, y, dx, dy) in ((8, 8, 1, 1), (471, 8, -1, 1), (8, 261, 1, -1), (471, 261, -1, -1)):
        cv.line(x, y, x + 14 * dx, y, br)
        cv.line(x, y, x, y + 10 * dy, br)
    return out


def build_southbridge(prev=None):
    folder = OUT / "southbridge"
    folder.mkdir(parents=True, exist_ok=True)
    main, holes = sb_main()
    main.save(folder / "main.png")
    sb_mid().save(folder / "mid.png")
    sb_front().save(folder / "front.png")
    for old in ("shafts", "water", "ripples"):                       # 旧版的层（城市的光柱、前景水）不用了
        for ext in (".png", ".png.import"):
            if (folder / (old + ext)).exists():
                (folder / (old + ext)).unlink()
    objs = sb_objects()
    layers = sb_layers()
    la = layer_arrays(layers, folder)
    # 取景框：镜头左边缘 = VIEW_CAM 时的画面（不画人、不画前景层）→ 影像
    base = comp_room(la, layers, VIEW_CAM, False)
    base = over(base, obj_overlay(objs, {}, VIEW_CAM))
    vf = footage(base, np.random.default_rng(1))
    Image.fromarray(vf).save(folder / "viewfinder.png")
    cfg = {
        "_note": "tools/river_warehouse_bridge_art.py 生成，别手改。约定见 docs/river_rooms_contract.md。远景层是原来的蓝色月夜河岸（art/river）。",
        "size": [SB_W, H],
        "env": "river",
        "bg": ["#0b1424", "#06101c"],
        "layers": layers,
        "ground": SB_GROUND,
        "markers": {
            "southbridge_entry": 24, "southbridge_back": 14, "southbridge_niff": 60, "southbridge_lamp_post": LAMPS[1],
            "southbridge_ornament": 1028, "southbridge_arch_wrong": ARCHES[0][0], "southbridge_arch": ARCHES[1][0],
            "southbridge_footprints": 596, "southbridge_waterway": 1100, "southbridge_dock": 1262,
            "southbridge_routemap": 1350, "southbridge_dock_step": 1210, "southbridge_plates": 1450,
            "southbridge_arch_far": ARCHES[2][0], "southbridge_view_spot": VIEW_SPOT,
            "southbridge_plate_07": 1420, "southbridge_plate_12": 1440, "southbridge_plate_21": 1460,
        },
        "walk": [12, 1486],
        "walk_when": [{"not": ["river_waterway_open"], "walk": [12, 1054]}],
        "portals": [{"edge": "left", "to": "oldstreet", "at": "oldstreet_to_south", "kind": "walk_fade"}],
        "ambient": [{"name": "river_flow", "db": -14}],
        "scripts": [],
        "viewfinder": {"img": "viewfinder.png", "cam_x": VIEW_CAM, "chen_x": VIEW_SPOT,
                       "note": "镜头左边缘 = cam_x 时对齐；用这几层按引擎视差公式合成后压成影像（tools/river_warehouse_bridge_art.py 每次重出）"},
    }
    write_room(folder, cfg, objs)
    if prev:
        shots = {
            "sb_entry": (0, 40, {}),
            "sb_view_off": (200, 440, {}),
            "sb_view_on": (VIEW_CAM, VIEW_SPOT, {}),
            "sb_arch": (VIEW_CAM, 600, {"southbridge_arch": "scratches", "southbridge_footprints": "seen", "southbridge_waterway": "revealed"}),
            "sb_waterway": (820, 1040, {}),
            "sb_dock": (1020, 1262, {"southbridge_waterway": "revealed"}),
            "sb_dock_fallen": (1020, 1300, {"southbridge_waterway": "revealed", "southbridge_routemap": "fallen", "southbridge_plate_12": "held"}),
        }
        for name, (cl, chx, st) in shots.items():
            img = comp_room(la, layers, cl, False)
            img = over(img, obj_overlay(objs, st, cl))
            stand_in(img, chx - cl, sb_ground(chx))
            img = over(img, comp_room(la, layers, cl, True))
            big(img, 2).save(Path(prev) / f"{name}.png")
        # 取景框叠在场景上（alpha 0.7）：对上 / 没对上
        for name, cl in (("sb_vf_on", VIEW_CAM), ("sb_vf_off", 300)):
            img = comp_room(la, layers, cl, False)
            img = over(img, obj_overlay(objs, {}, cl))
            stand_in(img, cl + 240 - cl, sb_ground(cl + 240))
            img = over(img, comp_room(la, layers, cl, True))
            alpha_over(img, vf, 0.7)
            big(img, 2).save(Path(prev) / f"{name}.png")
        big(vf, 2).save(Path(prev) / "sb_viewfinder.png")
    return objs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="合成预览（放大 2 倍）存到这个目录")
    ap.add_argument("--only", default="warehouse,southbridge")
    args = ap.parse_args()
    if args.preview:
        Path(args.preview).mkdir(parents=True, exist_ok=True)
    only = args.only.split(",")
    if "warehouse" in only:
        build_warehouse(args.preview)
    if "southbridge" in only and "build_southbridge" in globals():
        build_southbridge(args.preview)
    print("ok")
