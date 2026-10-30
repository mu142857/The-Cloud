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


HOLE_LIT = None                  # 透灯的洞：从最暗的暖褐到灯芯（第一次用时再算，bm 的 WARM 要先 import 完）
HOLE_DARK = [(1, 1, 7), (2, 4, 13), (3, 7, 19), (5, 11, 25), (7, 16, 31), (10, 22, 38)]   # 和岩石同一路的靛色，最亮那档 ≈ 石头的暗面


def hole(cv, m, ox, oy, lit=True, door=False, src=None, pal=None, halo=True, reach=1.0, levels=None):
    """凿出来的洞（门 / 窗 / 拱洞），不平涂：
    透灯的 = 灯在洞里偏下（门在地上），离灯越远越暗，抖着过渡；上沿、左沿一道内壁的影（墙厚）；外面一圈暖光落到石头上、往外渐弱。
    不透灯的 = 近黑的靛色，月光从右下斜进来，下半截、右边亮一点；上沿最深。m 是洞的局部掩码，(ox, oy) 是它的左上角。"""
    global HOLE_LIT
    if HOLE_LIT is None:
        HOLE_LIT = [col(0.13, 0.03, 40)] + list(bm.WARM)
    h, w = m.shape
    yy, xx = np.mgrid[0:h, 0:w]
    if src is None:
        src = (w * 0.55, h * (0.86 if door else 0.66))
    sx, sy = src
    d = np.hypot((xx + 0.5 - sx) / (w * 0.62 * reach), (yy + 0.5 - sy) / (h * 0.7 * reach))
    bay = blobs(h, w, np.random.default_rng(ox * 7 + oy), 1.2, 1.6) - 0.5   # 档边一团团的，不是棋盘格
    left = m & ~np.roll(m, 1, 1)
    left[:, 0] = m[:, 0]
    top = m & ~np.roll(m, 1, 0)
    top[0] = m[0]
    top2 = m & ~np.roll(top | ~m, 1, 0) & ~top
    if lit:
        levels = HOLE_LIT
        v = (1 - d) * (len(levels) - 0.6) + bay * 0.9
        if door:
            v += np.clip((yy - h * 0.75) / (h * 0.25), 0, 1) * 1.2       # 门里的地上一层亮
    else:
        levels = levels or HOLE_DARK
        v = 0.9 + np.clip(1.1 - d, 0, 1) * 2.4 + np.clip((yy - h * 0.55) / (h * 0.45), 0, 1) * 1.2 \
            + np.clip((xx - w * 0.6) / (w * 0.4), 0, 1) * 0.6 + bay * 0.9
    v = np.where(left, v - 2.2, v)
    v = np.where(top, v - 3, np.where(top2, v - 1.4, v))
    idx = np.clip(np.floor(v), 0, len(levels) - 1).astype(int)
    for y, x in zip(*np.nonzero(m)):
        cv.put(ox + x, oy + y, levels[idx[y, x]])
    if lit and halo:
        r = max(w, h) * 0.75 + 7
        bm.glow(rc(cv), ox + sx, oy + sy, r)
    if pal is not None:                                                # 右沿、下沿的石唇受月光
        for y in range(h):
            row = np.nonzero(m[y])[0]
            if len(row) and y > h * 0.35:                              # 右沿的石唇：只有下半截受光（上半截在门楣的影里）
                cv.put(ox + row[-1] + 1, oy + y, pal[-2] if y > h * 0.6 else pal[-3])
        cols = np.nonzero(m.any(0))[0]
        cv.rect(ox + cols[0] - 1, oy + h, ox + cols[-1] + 1, oy + h, pal[-1])


def carve2(cv, x, y, w, h, kind="arch", lit=True, door=False, pal=None):
    """凿门窗洞：用河岸会话第四版的 bm.carve（墙厚、门楣受光、窗台石板、洞口磨损、光往外渐弱），整章统一。"""
    bm.carve(rc(cv), x, y, w, h, kind, lit, door, pal=pal if pal is not None else SPAL, seed=x * 31 + y)


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
    gone = ~cv.mask_of_poly(H1)
    edge = gone & ~np.roll(gone, 1, 1) | gone & ~np.roll(gone, -1, 0) | gone & ~np.roll(gone, 1, 0)
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
    ys, xs = np.nonzero(door)
    # 门洞里不平涂：通往上面的斜坡，水面的月光从洞里右上斜着漏下来，往下、往左越来越深
    hole(cv, door[ys.min():ys.max() + 1, xs.min():xs.max() + 1], xs.min(), ys.min(), lit=False,
         src=(30, 4), reach=1.4, levels=HOLE_DARK[:3] + WROCK[2:5])
    for i in range(1, 9):                                          # 洞里往上的坡道：几道被月光擦亮的石沿，越往里越暗
        y = WH_FLOOR - i * 9
        cv.rect(16 + i * 3, y, 34 + i * 2, y, HOLE_DARK[min(4, 1 + i // 2)])
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
    dm_ = np.ones((WH_FLOOR - 174 + 1, b - a - 1), bool)           # 门洞（门关着时被物件盖住）：里间暗，圆窗那边一点冷光
    hole(cv, dm_, a + 1, 174, lit=False, src=(b - a - 1, 10), reach=1.2)
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
SX = 260                         # 开头一段空的河堤（从旧街过来，先只有月亮、河、一盏石灯笼，再到桥）
GAP = 240                        # 桥和水道 / 货台之间再空一段泥滩
D0 = SX + GAP                    # 水道、货台那一组整体往右挪多少（下面写成 D0 + 原来的 x）
SB_W = 1500 + SX + GAP
SB_G = 228                       # 泥滩（桥下）
DOCK_Y = 196                     # 货台台面
SB_GROUND = [[0, 212], [SX + 44, 212], [SX + 64, 213], [SX + 84, 217], [SX + 104, 223], [SX + 124, 228],
             [D0 + 1180, 228], [D0 + 1192, 225], [D0 + 1204, 216], [D0 + 1216, 204], [D0 + 1228, 197], [D0 + 1238, 196], [SB_W, 196]]
DECK = 58                        # 桥面（= 拱肩里那几户的屋顶）
SPRING = 150                     # 拱脚
ARCHES = [(SX + 310, 120, 72), (SX + 590, 120, 72), (SX + 850, 100, 68)]   # (中心 x, 半跨, 矢高)
RING = 9                         # 券石那一圈的厚度
PIERS = [(SX + a, SX + b) for a, b in ((150, 190), (430, 470), (710, 750), (950, 990))]
BRIDGE = (SX + 130, SX + 1030)
OLD_WATER = 176                  # 影像里那时候的水位（桥墩上一道水线）
LAMPS = [SX + 244, SX + 522, SX + 800]   # 桥面上的灯柱（中间那根 = 影像里挂浮灯的，marker southbridge_lamp_post）
VIEW_CAM = SX + 352              # 取景框：镜头左边缘
VIEW_SPOT = SX + 592
HOUSE_X = SX + 1002              # 右桥头那块凿出来的巨石屋（marker southbridge_ornament）
TUNNEL_X = D0 + 1100             # 旧运输水道的石拱洞口

STONE = [blue(v, None, 256) for v in (0.075, 0.095, 0.12, 0.145, 0.175, 0.21, 0.26, 0.32)]
PLAST = [col(v, 0.016, 236) for v in (0.15, 0.185, 0.215, 0.245, 0.29)]
ROOF = [blue(v, 0.02, 262) for v in (0.1, 0.14, 0.19, 0.25)]
MUD = [blue(v, 0.03, 262) for v in (0.06, 0.08, 0.1, 0.125, 0.16, 0.22)]
GLASS = blue(0.16, 0.03, 250)
MOSS = [col(v, 0.03, 190) for v in (0.12, 0.17, 0.22)]


def rock(cv, m, rng, pal, face=False):
    """石头：河岸会话第四版的 bm.stone_shade（整章统一的料：柱状节理切面、小色团、右沿冷亮边、底部暗、苔、水渍）。
    face=True 的是很宽的一横条（河堤、货台台面、挡土岩），切面放宽、岩层台少一点。
    桥墩的旧水位不交给 stone_shade（它会把线以下压成一片死黑），由 water_mark 另外画。"""
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    img = bm.stone_shade(m[y0:y1, x0:x1], rng, pal, facet_w=40.0 if face else 11.0, ledges=0.4 if face else 0.8)
    cv.paste(img, x0, y0)

def walk_top(cv, x0, x1, rng):
    """走的那一层石面（晨的脚就踩在这上面，不然看着像浮着）：最上一行冷亮边、下面两行受月光的路面
    （一团团深浅，偶尔一道缝、一撮苔），再下一行是路面挑出来的影。跟着 sb_ground 走。"""
    nz = blobs(1, x1 - x0 + 1, rng, 1, 4)[0]
    for x in range(x0, x1):
        g = sb_ground(x)
        u = nz[x - x0]
        cv.put(x, g, SPAL[5] if u > 0.25 else SPAL[4])
        cv.put(x, g + 1, RPAL[4] if u > 0.4 else RPAL[3])
        cv.put(x, g + 2, RPAL[3] if u > 0.55 else RPAL[2])
        cv.put(x, g + 3, RPAL[0])
        if rng.random() < 0.04:                                          # 路面上一道缝
            cv.put(x, g + 1, RPAL[1])
            cv.put(x, g + 2, RPAL[0])
        if u < 0.12 and rng.random() < 0.5:
            cv.put(x, g, bm.MOSS[1])


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
        rock(cv, pm, rng, RPAL)
    for pm in ((xx >= a0) & (xx < PIERS[0][0]) & (yy > SPRING) & (yy <= SB_G),
               (xx > PIERS[-1][1]) & (xx < a1) & (yy > SPRING) & (yy <= SB_G)):
        piers |= pm
        rock(cv, pm, rng, RPAL)
    body |= piers
    # 拱肩：一整块大石头里凿出来的人家（每一块各自上色，边上受光），门窗是凿的洞
    spand = body & ~rings & (yy <= SPRING) & (yy > DECK + 6)
    lab, n = RA.components(spand)
    for k in range(1, n + 1):
        rock(cv, lab == k, rng, SPAL)
    for i, (p0, p1) in enumerate(PIERS):
        house_in_spandrel(cv, (p0 + p1) // 2, i, rng, spand)
    # 拱圈：一圈放射的大块券石，每块有体积（见 voussoirs）；擦痕刻在这圈石沿上（物件）
    for k, (cx, hs, rise) in enumerate(ARCHES):
        voussoirs(cv, cx, hs, rise, np.random.default_rng(60 + k))
    # 桥墩上的旧水位线：线以下更深、更湿（一道湿亮的冷边、往下的水渍），线上一层发灰的泥壳；不用黄色
    water_mark(cv, piers, rng)
    for p0, p1 in PIERS:                                           # 墩子顶上压一条长石（拱脚）：顶面受光、正面、底下一道影
        imposts(cv, p0 - 3, p1 + 3, SPRING + 1, rng)
    # 桥面：一整条厚石板（挑出去一点，顶上长苔）——它就是拱肩里这几户的屋顶；屋脊上一排小石像，远看像栏杆
    r = rc(cv)
    deck_slab(cv, a0 - 6, a1 + 6, rng)
    ornament_row(cv, a0 + 2, a1 - 2, DECK - 1, np.random.default_rng(71))
    for lx in LAMPS:
        lamp_post(cv, lx, DECK - 1)
    # ---- 左岸：一长段石砌河堤（空的，只有一盏石灯笼），坡下到泥滩（不砌台阶，一道缓坡）
    lm = np.zeros((H, SB_W), bool)
    prof = smooth1d(SX + 140, np.random.default_rng(33), 50, 1.5)
    for x in range(0, SX + 140):
        g = sb_ground(x)
        if x >= a0 and g >= SB_G:
            continue
        lm[g + int(max(0, prof[x])) // 2:, x] = True
    rock(cv, lm, rng, RPAL, face=True)
    walk_top(cv, 0, SX + 124, np.random.default_rng(55))
    for bx, bw, bh in ((SX + 70, 14, 9), (SX + 98, 10, 6), (SX + 30, 8, 5)):   # 坡上几块滚下来的圆石
        mm = bm.blob_mask(bw, bh, rng)
        cv.paste(bm.stone_shade(mm, rng, RPAL, facet_w=8.0, ledges=0.3), bx, sb_ground(bx + bw // 2) - bh + 2)
    bm.stone_lantern(r, 148, sb_ground(148))
    # ---- 右桥头：一块凿出来的巨石屋（压在桥头上，底下一块石头墩着）；石头顶上一排小石像离地面近
    pm = np.zeros((H, SB_W), bool)
    for x in range(a1 - 8, a1 + 22):
        u = (x - (a1 - 8)) / 30.0
        pm[int(124 + 30 * u * u):SB_G + 1, x] = True
    rock(cv, pm, rng, RPAL)
    low_house(cv, HOUSE_X, rng)
    # ---- 中间那段空泥滩：一根石桩，桩头一盏小灯；几块石头
    mooring_lamp(cv, a1 + 128, SB_G)
    lamp_string(cv, (HOUSE_X + 30, 104), (a1 + 128, SB_G - 30), 14, 5, np.random.default_rng(81))   # 桥头巨石屋到石桩一串小灯
    for bx, bw, bh in ((a1 + 60, 12, 7), (a1 + 176, 18, 10), (a1 + 190, 8, 5)):
        mm = bm.blob_mask(bw, bh, rng)
        cv.paste(bm.stone_shade(mm, rng, RPAL, facet_w=8.0, ledges=0.3), bx, SB_G - bh + 3)
    # ---- 右边：一段挡土的岩体（顶上起伏）+ 旧运输水道的石拱洞口（洞口是物件 southbridge_waterway）
    wall = np.zeros((H, SB_W), bool)
    wp = smooth1d(160, np.random.default_rng(41), 40, 6.0)
    for i, x in enumerate(range(D0 + 1040, D0 + 1200)):
        u = min(1.0, (x - (D0 + 1040)) / 22.0)
        top = int(128 + wp[i] + 40 * (1 - np.sqrt(max(0.0, 1 - (1 - u) ** 2))))
        wall[top:SB_G + 1, x] = True
    rock(cv, wall, rng, RPAL, face=True)
    for x in range(D0 + 1040, D0 + 1200):
        ys = np.nonzero(wall[:, x])[0]
        if len(ys) and rng.random() < 0.5:
            cv.put(x, ys[0], bm.MOSS[1 if rng.random() < 0.6 else 2])
    tunnel = arch_open(TUNNEL_X, 40, 34) & (yy <= SB_G) & (yy >= 100)
    ys, xs = np.nonzero(tunnel)
    tx0, ty0 = xs.min(), ys.min()
    hole(cv, tunnel[ty0:ys.max() + 1, tx0:xs.max() + 1], tx0, ty0, lit=False, src=(40, 120), reach=1.3)
    for k, sc in enumerate((0.8, 0.62, 0.46)):                       # 洞里往深处一圈圈小下去的拱（看得出深）：右半边被月光擦亮
        spr = SPRING + (1 - sc) * 46
        t_ = (xx - TUNNEL_X) / (40 * sc)
        top_ = spr - 34 * sc * np.sqrt(np.clip(1 - t_ * t_, 0, 1))
        inner = (np.abs(t_) < 1) & (yy >= top_) & (yy <= SB_G - 4)
        edge = inner & ~np.roll(inner, 1, 0)
        edge |= inner & (~np.roll(inner, -1, 1) | ~np.roll(inner, 1, 1))
        edge &= tunnel
        cv.fill(edge & (xx > TUNNEL_X - 4), HOLE_DARK[4 - k])
        cv.fill(edge & (xx <= TUNNEL_X - 4), HOLE_DARK[3 - k])
    for x in range(TUNNEL_X - 36, TUNNEL_X + 37):                    # 洞底一条暗的水，映一点月光
        cv.put(x, SB_G - 3, blue(0.1, 0.03, 250))
        if (x * 5) % 7 < 3:
            cv.put(x, SB_G - 3, blue(0.16, 0.03, 248))
    voussoirs(cv, TUNNEL_X, 40, 34, np.random.default_rng(77), t_=7)
    cv.rect(TUNNEL_X - 44, SPRING, TUNNEL_X - 41, SB_G, RPAL[1])
    cv.rect(TUNNEL_X + 41, SPRING, TUNNEL_X + 44, SB_G, RPAL[3])
    # ---- 货台：一道缓坡上去，台面是整块的石头；背后一块凿出货棚的巨石、贴航线图的石面、挂编号牌的石门框
    dm = np.zeros((H, SB_W), bool)
    for x in range(D0 + 1176, SB_W):
        g = sb_ground(x)
        if g < SB_G or x >= D0 + 1186:
            dm[g:, x] = True
    rock(cv, dm, rng, RPAL, face=True)
    walk_top(cv, D0 + 1180, SB_W, np.random.default_rng(56))
    dock_shed(cv, rng)
    # ---- 泥滩（蓝黑，和河岸的地一路）：上沿一条被月光擦亮的湿泥，往下很快沉进黑
    m0, m1 = SX + 120, D0 + 1186
    mb = blobs(H, SB_W, np.random.default_rng(5), 1.5, 6.0)
    for x in range(m0, m1):
        g = SB_G
        if dm[g + 1:, x].any():
            continue
        for y in range(g + 1, H):
            t = (y - g) / (H - g)
            k = 3.0 - t * 3.6 + (mb[y, x] - 0.5) * 1.6
            cv.put(x, y, MUD[int(np.clip(np.floor(k), 0, 4))])
        cv.put(x, g, MUD[5])
        cv.put(x, g + 1, MUD[4])
    for _ in range(64):                                              # 积水的小水洼（映着天，亮一档）
        x = int(rng.integers(m0 + 10, m1 - 30))
        y = int(rng.integers(SB_G + 7, H - 6))
        w = int(rng.integers(8, 30))
        cv.rect(x, y, x + w, y, blue(0.17, 0.035, 252))
        cv.rect(x + 2, y + 1, x + w - 3, y + 1, blue(0.13, 0.035, 256))
        if rng.random() < 0.4:
            cv.rect(x + w // 3, y, x + w // 3 + 2, y, blue(0.27, 0.035, 248))
    for _ in range(190):                                             # 卵石：顶上一点亮
        x = int(rng.integers(m0, m1))
        y = int(rng.integers(SB_G + 3, H - 2))
        cv.rect(x, y, x + 1, y, MUD[4])
        cv.put(x, y + 1, MUD[0])
    fallen_float_lamp(cv, SX + 474, SB_G)
    # 泥里一盏还亮着的浮灯（空泥滩那段，水洼里一点暖的倒影）
    lx = a1 + 210
    cv.rect(lx, SB_G - 2, lx + 10, SB_G, WOOD[2])
    cv.rect(lx, SB_G - 2, lx + 10, SB_G - 2, WOOD[4])
    cv.line(lx + 5, SB_G - 3, lx + 6, SB_G - 9, IRON[3])
    bm.lantern(r, lx + 6, SB_G - 12, "post", r=11)
    for k in range(1, 4):
        cv.put(lx + 5 + (k % 2), SB_G + 2 + k * 2, bm.WARM[1])
    return cv, holes



def blobs(h, w, rng, sy=3.0, sx=4.0):
    """手画感的小色团用的低频噪声（0~1）：代替 Bayer 棋盘格，档边是一团团的，不是点点。"""
    return RA.vnoise(h, w, sy, sx, rng) * 0.65 + RA.vnoise(h, w, sy * 2.5, sx * 2.5, rng) * 0.35


def lv_to(cv, m, lv, pal, ox=0, oy=0):
    """局部掩码 m 里按档位 lv（浮点）上色，四舍五入到 pal 的档。"""
    idx = np.clip(np.round(lv), 0, len(pal) - 1).astype(int)
    for y, x in zip(*np.nonzero(m)):
        cv.put(ox + x, oy + y, pal[idx[y, x]])


def voussoirs(cv, cx, hs, rise, rng, t_=RING):
    """一圈券石。月光从右上来：每块石头朝光的那条边（外沿、一侧的接缝边）亮一档，背光的边暗一档，
    拱腹（内沿）一律暗；块与块之间一道暗缝，外沿的角有几处磕掉；块面上 2~3 色的小色团（不是棋盘格）；
    从拱脚往上一段越来越湿、发暗、长苔，几道水渍顺着拱腹往下挂；外沿迎光的一侧一道断断续续的冷亮边。"""
    x0, x1 = int(cx - hs - t_ - 2), int(cx + hs + t_ + 3)
    y0, y1 = int(SPRING - rise - t_ - 2), SPRING + 1
    h, w = y1 - y0, x1 - x0
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dx, dy = (xx - cx + 0.5), (yy - SPRING + 0.5)
    ri = np.sqrt((dx / hs) ** 2 + (dy / rise) ** 2)
    ro = np.sqrt((dx / (hs + t_)) ** 2 + (dy / (rise + t_)) ** 2)
    ring = (ri >= 1) & (ro < 1) & (yy <= SPRING)
    tt = (ri - 1) / np.maximum((ri - 1) + (1 - ro), 1e-6)          # 0 = 内沿，1 = 外沿
    a = np.degrees(np.arctan2(-dy / (rise + t_ / 2), dx / (hs + t_ / 2)))
    # 每块的角度边界：宽 11°~17°，拱顶石宽一点
    edges = [0.0]
    while edges[-1] < 180:
        nxt = edges[-1] + rng.uniform(11, 17)
        if abs((edges[-1] + nxt) / 2 - 90) < 9:
            nxt = edges[-1] + 19
        edges.append(min(180.0, nxt) if 180 - nxt > 8 else 180.0)
    edges = np.array(edges)
    blk = np.clip(np.searchsorted(edges, a, side="right") - 1, 0, len(edges) - 2)
    lo, hi = edges[blk], edges[blk + 1]
    arc_px = np.radians(hi - lo) * (hs + t_ / 2)                     # 这块沿弧长有多少像素
    s = (a - lo) / np.maximum(hi - lo, 1e-6)                          # 0 = 小角度那边，1 = 大角度那边
    base = 3.1 + np.array([rng.choice([-0.45, 0, 0, 0.35]) for _ in range(len(edges))])[blk]
    ar = np.radians(a)
    L = np.array([0.7071, -0.7071])                                   # 月光方向（右上）
    ext = np.cos(ar) * L[0] - np.sin(ar) * L[1]                       # 外沿法线 · 光
    tan_hi = (-np.sin(ar)) * L[0] + (-np.cos(ar)) * L[1]              # 大角度那条缝边的法线 · 光
    lv = base + 0.5 * np.clip(ext, -1, 1)
    lv += (blobs(h, w, rng, 2.0, 3.0) - 0.5) * 0.9                    # 小色团
    edge_px = 1.0 / max(1.0, t_)
    lv = np.where(tt > 1 - 1.3 * edge_px, lv + 1.5 * np.clip(ext, -0.4, 1), lv)                 # 外沿那条边
    lv = np.where(tt < 1.4 * edge_px, lv - 1.6, lv)                                              # 内沿（拱腹那条边）背光
    sw = 1.2 / np.maximum(arc_px, 1)
    lv = np.where(s > 1 - sw, lv + 1.3 * tan_hi, lv)                                             # 两条缝边，一亮一暗
    lv = np.where(s < sw, lv - 1.3 * tan_hi, lv)
    wet = np.clip(1 - np.minimum(a, 180 - a) / 32.0, 0, 1)             # 拱脚往上一段：湿、暗
    lv -= wet * 1.3
    seam = (np.diff(blk, axis=1, prepend=blk[:, :1]) != 0) | (np.diff(blk, axis=0, prepend=blk[:1]) != 0)
    lv = np.where(seam, 0, lv)
    loc = ring.copy()
    lv_to(cv, loc, lv, SPAL, x0, y0)
    mos = ring & (wet > 0.15) & (blobs(h, w, rng, 1.5, 2.0) < wet * 0.75)
    for y, x in zip(*np.nonzero(mos)):
        cv.put(x0 + x, y0 + y, bm.MOSS[0] if lv[y, x] < 1.6 else bm.MOSS[1])
    # 外沿磕掉的角：缝和外沿相交处，挖一个 2~3 像素的小缺口（缺口里暗，下唇受光）
    rad = hs + t_ / 2
    for b in range(1, len(edges) - 1):
        if rng.random() < 0.45:
            side = rng.choice([-1, 1])
            for k in (1, 2)[: int(rng.integers(1, 3))]:
                ang = np.radians(edges[b] + side * np.degrees(k / rad))
                px = cx + (hs + t_ - 0.6) * np.cos(ang)
                py = SPRING - (rise + t_ - 0.6) * np.sin(ang)
                ix, iy = int(px - x0), int(py - y0)
                if 0 <= iy < h and 0 <= ix < w and ring[iy, ix]:
                    cv.put(px, py, SPAL[1])
                    px2 = cx + (hs + t_ - 1.8) * np.cos(ang)
                    py2 = SPRING - (rise + t_ - 1.8) * np.sin(ang)
                    cv.put(px2, py2, SPAL[4] if np.cos(ang) > -0.3 else SPAL[2])
    # 一两处大一点的缺口（一块券石崩掉一角）
    for _ in range(int(rng.integers(1, 3))):
        ang = rng.uniform(40, 140)
        ar_ = np.radians(ang)
        px = cx + (hs + t_ * 0.75) * np.cos(ar_)
        py = SPRING - (rise + t_ * 0.75) * np.sin(ar_)
        for k in range(int(rng.integers(3, 6))):
            cv.put(px + k % 3, py + k // 3, SPAL[0] if k < 3 else SPAL[1])
    # 外沿迎光那半边一道断断续续的冷亮边
    for y, x in zip(*np.nonzero(ring & (tt > 1 - edge_px * 1.1) & (ext > 0.35) & ~seam)):
        if (x * 7 + y * 3) % 9 < 6:
            cv.put(x0 + x, y0 + y, SPAL[5])
    # 拱腹（桥的厚度）：洞里贴着石沿一条 3 像素的暗带，越往拱脚越窄；几道水渍从这里往下挂
    inside = (ri < 1) & (ri > 0.93 - 0.05 * (np.sin(ar) > 0.5)) & (yy < SPRING - 6)
    lvs = 0.6 + (blobs(h, w, rng, 1.5, 3.0) - 0.5) * 1.2 + (ri - 0.95) * 10
    lv_to(cv, inside, lvs, SPAL, x0, y0)
    for _ in range(int(rng.integers(3, 6))):
        ang = rng.uniform(35, 145)
        ar_ = np.radians(ang)
        px = int(cx + hs * 0.94 * np.cos(ar_))
        py = int(SPRING - rise * 0.94 * np.sin(ar_))
        for k in range(int(rng.integers(3, 9))):
            if cv.a[py + k, px, 3]:
                cv.put(px, py + k, SPAL[0] if k % 3 else bm.MOSS[0])


def water_mark(cv, piers, rng):
    """桥墩上的旧水位：线以下深一档、湿（偶尔一点湿亮的冷边），线上一层发灰的薄泥壳（冷灰，不是黄），
    线下挂几缕长短不一的干水草和往下的水渍。"""
    below = piers & (np.arange(H)[:, None] > OLD_WATER)
    lighten(cv, below, -0.025)
    wet = piers & (np.arange(H)[:, None] > OLD_WATER) & (np.arange(H)[:, None] < OLD_WATER + 5)
    lighten(cv, wet, -0.015)
    xs = np.nonzero(piers[OLD_WATER])[0]
    crust = blue(0.24, 0.012, 230)
    run = 0
    for x in xs:
        run = run - 1 if run > 0 else (int(rng.integers(3, 9)) if rng.random() < 0.12 else 0)
        if run:                                                         # 线断开的地方（泥壳掉了）
            continue
        if rng.random() < 0.7:
            cv.put(x, OLD_WATER - 1, crust)
        cv.put(x, OLD_WATER, SPAL[0])
        if rng.random() < 0.25:
            cv.put(x, OLD_WATER + 1, SPAL[3])                         # 一点湿亮
        if rng.random() < 0.12:
            for k in range(int(rng.integers(2, 9))):
                if piers[OLD_WATER + 1 + k, x]:
                    cv.put(x, OLD_WATER + 1 + k, bm.MOSS[0] if k < 3 else SPAL[0])


def imposts(cv, x0, x1, y, rng):
    """拱脚压的一条长石：顶面一道受光（右边更亮）、正面、底下一道影；两头的角磕圆了。"""
    for x in range(x0, x1 + 1):
        u = (x - x0) / max(1, x1 - x0)
        cv.put(x, y, SPAL[4] if u > 0.35 or (x % 3) else SPAL[3])
        cv.put(x, y + 1, SPAL[3])
        cv.put(x, y + 2, SPAL[2] if rng.random() < 0.8 else SPAL[3])
        cv.put(x, y + 3, SPAL[0])
    cv.put(x0, y, SPAL[2])
    cv.put(x1, y, SPAL[5])
    cv.put(x1, y + 1, SPAL[4])


def deck_slab(cv, x0, x1, rng):
    """桥面：一长条厚石板，一段段长短不一（18~44 像素）。顶面受月光、正面中间暗、下沿挑出一道影；
    接缝处顶角磕圆；顶上一层苔（一团一团，不均匀）；下沿偶尔挂几缕苔、几道水渍。"""
    x = x0
    k = 0
    while x < x1:
        ln = int(rng.integers(18, 45))
        xe = min(x1, x + ln)
        tone = rng.choice([-0.4, 0, 0, 0.35])
        for xx in range(x, xe):
            y0 = DECK - 1 + int(round(0.6 * np.sin(xx / 11.0)))
            u = (xx - x) / max(1, xe - x)
            for d in range(8):
                lv = (4.1 if d == 0 else 3.2 if d == 1 else 2.2 if d < 5 else 1.6 if d < 7 else 0.2) + tone
                lv += 0.5 * (u > 0.8) * (d < 2) - 0.6 * (u < 0.08) * (0 < d < 7)
                cv.put(xx, y0 + d, SPAL[int(np.clip(round(lv), 0, 5))])
            if xx == x:                                                 # 接缝
                for d in range(1, 7):
                    cv.put(xx, y0 + d, SPAL[0])
                cv.put(xx, y0, SPAL[2])
        x = xe
        k += 1
    mz = blobs(1, x1 - x0 + 1, rng, 1, 5)[0]
    for xx in range(x0, x1):
        y0 = DECK - 1 + int(round(0.6 * np.sin(xx / 11.0)))
        m = mz[xx - x0]
        if m > 0.45:
            cv.put(xx, y0 - 1, bm.MOSS[1] if m < 0.7 else bm.MOSS[2])
            if m > 0.72:
                cv.put(xx, y0 - 2, bm.MOSS[1])
        if m > 0.62:
            cv.put(xx, y0, bm.MOSS[0])
        if rng.random() < 0.035:
            for d in range(1, int(rng.integers(3, 9))):
                cv.put(xx, y0 + 7 + d, bm.MOSS[0] if d < 3 else SPAL[0])


def ornament_row(cv, x0, x1, base, rng):
    """屋脊上一排小石像（远看像栏杆）：大小、种类不一（蹲兽、抱膝小人、圆顶小柱、断了只剩一截的），
    间距有疏有密、偶尔缺一个；每个左暗右亮（月光右上），右沿一道冷亮边，脚下一点影。"""
    x = x0 + int(rng.integers(0, 6))
    while x < x1 - 4:
        x += int(rng.integers(9, 17))
        if x >= x1 - 4 or rng.random() < 0.13:
            continue
        kind = rng.choice(["beast", "sit", "post", "post", "stump", "beast", "sit"])
        k = rng.choice([0.8, 1.0, 1.0, 1.2, 1.4])
        c = Cv(14, 14)
        cxl = 6
        if kind == "beast":
            hb = int(5 * k)
            c.fill(c.mask_of_ellipse(cxl - 3 * k, 13 - hb, cxl + 3 * k, 13), (1, 1, 1))
            c.fill(c.mask_of_ellipse(cxl - 1 * k, 13 - hb - 3 * k, cxl + 2.5 * k, 13 - hb + 1), (1, 1, 1))
            c.put(cxl, 13 - hb - 3 * k, (1, 1, 1))
            c.put(cxl + 2 * k, 13 - hb - 3 * k, (1, 1, 1))
        elif kind == "sit":
            c.fill(c.mask_of_ellipse(cxl - 2.5 * k, 13 - 5 * k, cxl + 2.5 * k, 13), (1, 1, 1))
            c.fill(c.mask_of_ellipse(cxl - 1.5 * k, 13 - 8 * k, cxl + 1.5 * k, 13 - 5 * k), (1, 1, 1))
        elif kind == "post":
            c.rect(cxl - 1, 13 - int(6 * k), cxl + 1, 13, (1, 1, 1))
            c.fill(c.mask_of_ellipse(cxl - 2, 13 - int(6 * k) - 3, cxl + 2, 13 - int(6 * k) + 1), (1, 1, 1))
        else:
            c.rect(cxl - 1, 13 - int(rng.integers(2, 4)), cxl + 2, 13, (1, 1, 1))
            c.a[13 - 3, cxl + 2] = 0                                      # 断口缺一角
        m = c.a[..., 3] > 0
        if not m.any():
            continue
        ys, xs = np.nonzero(m)
        lvm = np.zeros(m.shape)
        for y in set(ys):
            row = np.nonzero(m[y])[0]
            for xx in row:
                u = (xx - row[0]) / max(1, row[-1] - row[0])
                lvm[y, xx] = 1.6 + 1.6 * u + (0.6 if y == ys.min() else 0)
            lvm[y, row[-1]] = 4.6                                       # 右沿冷亮边
        if rng.random() < 0.3:                                         # 有的长了苔
            lvm[ys.max() - 1:, :] -= 1.0
        lv_to(cv, m, lvm, SPAL, x - cxl, base - 13)
        cv.put(x - 2, base + 1, SPAL[0])
        cv.put(x - 1, base + 1, SPAL[0])


def house_in_spandrel(cv, cx, i, rng, spand):
    """拱肩这块大石头里凿出来的一户：两三扇窗（大小、形状、亮不亮都不一样，有的是暗的）、一扇小门洞，
    门口凿出的一条窄石台（台面受光、下面一道影）。不挂晾晒的东西。"""
    r = np.random.default_rng(300 + i)
    inner = 0 < i < len(PIERS) - 1
    wy = DECK + 13
    slots = [(cx - 15, wy + int(r.integers(0, 4))), (cx + 6, wy + int(r.integers(-1, 3)))] if inner else [(cx - 5, wy + 2)]
    if inner and r.random() < 0.6:
        slots.append((cx + int(r.integers(-6, 4)), wy + 22 + int(r.integers(0, 4))))
    for j, (wx, y) in enumerate(slots):
        kind = r.choice(["arch", "arch", "round", "rect"])
        ww = int(r.choice([6, 7, 8, 9])) if kind != "round" else int(r.choice([6, 7]))
        wh = ww if kind == "round" else ww + int(r.integers(3, 7))
        if not spand[y - 2:y + wh + 3, wx - 2:wx + ww + 3].all():
            continue
        lit = r.random() < 0.6
        carve2(cv, wx, y, ww, wh, kind, lit, False, pal=SPAL)
        if lit and r.random() < 0.5:                                   # 有的窗里一根石棂
            for yy in range(y + ww // 2, y + wh):
                cv.put(wx + ww // 2, yy, bm.WARM[0])
        cv.rect(wx - 1, y + wh + 1, wx + ww, y + wh + 1, SPAL[2])       # 窗台下一道影
    if inner:
        dy = wy + 36 + int(r.integers(-2, 3))
        dw = int(r.choice([8, 9, 10]))
        if spand[dy:dy + 18, cx - 6:cx + 7].all():
            carve2(cv, cx - dw // 2, dy, dw, dw + 6, "arch", r.random() < 0.6, True, pal=SPAL)
            ly = dy + dw + 6
            for x in range(cx - 8, cx + 9):                              # 门口一条窄石台：台面受光、下面一道影，边上磕了
                if x in (cx - 8, cx + 8) and r.random() < 0.5:
                    continue
                cv.put(x, ly, SPAL[4] if x > cx - 4 else SPAL[3])
                cv.put(x, ly + 1, SPAL[2])
                cv.put(x, ly + 2, SPAL[0])


def lamp_string(cv, p0, p1, sag, n, rng):
    """两点之间一根下垂的旧绳，挂一串小灯（灯挂在绳下 2~3 像素，亮度不一，有一盏不亮），每盏一小圈暖光往外渐弱。"""
    (xa, ya), (xb, yb) = p0, p1
    rope = col(0.2, 0.012, 250)
    steps = int(max(abs(xb - xa), abs(yb - ya)) * 1.5) + 1
    pts = []
    for k in range(steps + 1):
        t = k / steps
        x = xa + (xb - xa) * t
        y = ya + (yb - ya) * t + sag * 4 * t * (1 - t)
        cv.put(x, y, rope)
        pts.append((x, y))
    dark = int(rng.integers(0, n))
    for i in range(n):
        t = (i + 0.5 + rng.uniform(-0.15, 0.15)) / n
        x, y = pts[int(t * steps)]
        x, y = int(round(x)), int(round(y))
        hang = int(rng.integers(2, 4))
        for d in range(1, hang):
            cv.put(x, y + d, rope)
        ly = y + hang
        if i == dark:
            cv.rect(x - 1, ly, x + 1, ly + 2, SPAL[1])
            cv.put(x, ly + 1, bm.WARM[0])
            continue
        br = rng.choice([3, 4, 4])
        cv.rect(x - 1, ly, x + 1, ly + 2, bm.WARM[br - 1])
        cv.put(x, ly + 1, bm.WARM[br])
        cv.put(x - 1, ly, bm.WARM[0])
        for ddx, ddy in ((-2, 1), (2, 1), (0, -1), (0, 4), (-2, 3), (2, -1)):    # 一小圈暖光（只在空处点几颗，往外很快没了）
            xx_, yy_ = x + ddx, ly + ddy
            if 0 <= xx_ < cv.w and 0 <= yy_ < cv.h and cv.a[yy_, xx_, 3] == 0 and (xx_ + yy_) % 2 == 0:
                cv.put(xx_, yy_, bm.WARM[0])


def lamp_post(cv, x, base):
    """桥上的灯柱：一根细石柱（方座、两段柱身、宽顶石），柱头凿空成灯室，凿出的拱口里透暖光（里亮外暗、光落到灯室的石头上），
    左暗右亮、右沿冷亮边；右边伸出一个挂浮灯绳的石钩（取景框里的绳从这里垂下）。
    每根的顶和磕掉的角都有点不一样。"""
    rng = np.random.default_rng(x)
    top = 18
    for xx in range(x - 3, x + 5):                                      # 方座
        u = (xx - (x - 3)) / 7
        for yy in range(base - 4, base + 1):
            cv.put(xx, yy, SPAL[1 if u < 0.25 else 2 if u < 0.7 else 3])
        cv.put(xx, base - 4, SPAL[4] if u > 0.3 else SPAL[3])
    if rng.random() < 0.5:
        cv.put(x + 4, base - 4, SPAL[1])                                  # 磕掉的角
    jy = (top + 10 + base - 4) // 2 + int(rng.integers(-3, 4))
    for yy in range(top + 10, base - 4):                                 # 柱身：左暗、中、右亮、右沿冷边；中间一道接缝
        cv.put(x - 1, yy, SPAL[1])
        cv.put(x, yy, SPAL[2])
        cv.put(x + 1, yy, SPAL[3])
        cv.put(x + 2, yy, SPAL[4] if yy % 5 else SPAL[3])
    for xx in range(x - 1, x + 3):
        cv.put(xx, jy, SPAL[0])
        cv.put(xx, jy + 1, SPAL[3] if xx > x - 1 else SPAL[2])
    for xx in range(x - 3, x + 5):                                      # 灯室
        u = (xx - (x - 3)) / 7
        for yy in range(top + 1, top + 10):
            cv.put(xx, yy, SPAL[1 if u < 0.2 else 2 if u < 0.75 else 4])
        cv.put(xx, top + 9, SPAL[3] if u > 0.3 else SPAL[2])
    carve2(cv, x - 1, top + 2, 4, 7, "arch", True, False, pal=SPAL)
    if rng.random() < 0.5:                                               # 顶：尖的 / 平一点的
        cv.poly([(x - 5, top + 1), (x + 1, top - 4), (x + 6, top + 1)], SPAL[2])
        cv.line(x + 1, top - 4, x + 6, top + 1, SPAL[5])
        cv.line(x - 5, top + 1, x, top - 3, SPAL[1])
    else:
        cv.rect(x - 4, top - 1, x + 5, top, SPAL[2])
        cv.rect(x - 2, top - 3, x + 3, top - 2, SPAL[2])
        cv.rect(x + 1, top - 3, x + 3, top - 3, SPAL[4])
        cv.rect(x + 2, top - 1, x + 5, top - 1, SPAL[5])
    cv.put(x + 1, top - 5, SPAL[3])
    cv.rect(x + 3, top + 11, x + 5, top + 12, SPAL[4])                # 石钩
    cv.put(x + 3, top + 12, SPAL[2])
    cv.put(x + 5, top + 13, SPAL[4])


def low_house(cv, cx, rng):
    """右桥头一块凿出来的巨石屋（和桥同一种石头料）：一扇亮着的拱窗、一扇透光的门洞；顶上一层苔。
    marker southbridge_ornament 在这里：晨在这儿抬头看桥面那排小石像（「从下面看，是别人家的屋顶」）。
    屋顶上原来也摆了一排小石像，贴着后面的桥身看不清、像石头上的划痕，去掉了。"""
    r = np.random.default_rng(77)
    w, h, base = 64, 46, 131
    m = bm.blob_mask(w, h, r)
    x0, y0 = int(cx - w // 2), int(base - h + 1)
    cv.paste(bm.stone_shade(m, r, SPAL, facet_w=12.0), x0, y0)
    for xx in range(w):
        ys = np.nonzero(m[:, xx])[0]
        if len(ys) and r.random() < 0.5:
            cv.put(x0 + xx, y0 + ys[0], bm.MOSS[2] if r.random() < 0.4 else bm.MOSS[1])
            if r.random() < 0.2:
                for d in range(1, int(r.integers(2, 6))):
                    cv.put(x0 + xx, y0 + ys[0] + d, bm.MOSS[0])
    for (kind, ox, oy, ow, oh, lit, door) in (("arch", 14, 16, 9, 13, True, False), ("arch", 38, 0, 10, 18, True, True)):
        carve2(cv, x0 + ox, base - oy - oh + 1, ow, oh, kind, lit, door, pal=SPAL)


def fallen_float_lamp(cv, x, g):
    """泥里歪着一盏不亮的浮灯：小木托 + 一根杆 + 玻璃罩。"""
    cv.rect(x, g - 2, x + 12, g, WOOD[2])
    cv.rect(x, g - 2, x + 12, g - 2, WOOD[4])
    cv.line(x + 6, g - 3, x + 10, g - 12, IRON[2])
    cv.rect(x + 9, g - 16, x + 13, g - 12, GLASS)
    cv.rect(x + 9, g - 16, x + 13, g - 16, IRON[4])
    cv.put(x + 11, g - 14, WARM4)


def mooring_lamp(cv, x, base):
    """空泥滩上一根石系船桩，桩头一盏小方灯（暖光往外渐弱），桩脚缠一圈旧绳。"""
    cv.rect(x - 2, base - 26, x + 3, base, RPAL[2])
    cv.rect(x + 3, base - 26, x + 3, base, RPAL[4])
    cv.rect(x - 2, base - 26, x - 2, base, RPAL[1])
    cv.rect(x - 3, base - 28, x + 4, base - 26, RPAL[3])
    cv.rect(x - 3, base - 28, x + 4, base - 28, RPAL[4])
    cv.rect(x - 2, base - 12, x + 3, base - 11, col(0.2, 0.012, 250))     # 桩脚缠的旧绳（暗，不发白）
    cv.put(x + 3, base - 12, RPAL[3])
    bm.lantern(rc(cv), x, base - 32, "post", r=13)


MAP_R = (D0 + 1252, 116, 58, 44)   # 航线图（x, y, w, h）：贴在货棚巨石的正面，一张不大的纸
PLATE_XS = (D0 + 1372, D0 + 1392, D0 + 1412)   # 编号牌 07 / 12 / 21 挂在石门框横梁底下
LINTEL = (D0 + 1356, D0 + 1428, 92)           # 石门框：两根石柱 + 一条横梁（x0, x1, 梁顶 y）


def stone_post(cv, x0, top, base, w, rng):
    """一根石柱（几段鼓石摞起来）：左暗右亮，右沿一道冷亮边；鼓石之间的缝高低不一、角磕掉；
    面上 2~3 色的小色团；柱脚一段暗（和地面交接的影）、长一点苔。"""
    h = base - top + 1
    m = np.zeros((h, w + 2), bool)
    for y in range(h):
        sh = 1 if (y // 9) % 3 == 1 else 0
        m[y, sh:sh + w] = True
    nz = blobs(h, w + 2, rng, 2.0, 2.0)
    yy, xx = np.mgrid[0:h, 0:w + 2]
    lv = 2.0 + 2.0 * (xx / (w + 1)) + (nz - 0.5) * 1.0
    joints = sorted(set(int(v) for v in rng.integers(8, h - 6, size=max(1, h // 22))))
    for j in joints:
        lv[j, :] = 0.2
        lv[j + 1, :] += 0.8                                            # 缝下面那段石头的顶边受光
        if rng.random() < 0.6:
            lv[j - 1, w - 1:] = 0.4
    lv[0, :] += 1.0
    lv[:, -1] += 0
    for y in range(h):
        row = np.nonzero(m[y])[0]
        lv[y, row[-1]] = 4.4 if (y + int(x0)) % 5 else 3.6             # 右沿冷亮边
        lv[y, row[0]] = min(lv[y, row[0]], 1.0)
    lv -= np.clip((yy - (h - 6)) / 6.0, 0, 1) * 1.4                    # 柱脚的影
    lv_to(cv, m, lv, RPAL + [SPAL[5]], x0, top)
    for y in range(h - 5, h):
        for x in range(w):
            if nz[y, x] < 0.35:
                cv.put(x0 + x, top + y, bm.MOSS[0])


def dock_shed(cv, rng):
    """货台背后：一块凿出货棚的巨石（门洞里暗、往里渐深，正面一块磨平的石面贴航线图），右边一个孤零零的石门框
    （两根石柱 + 一条横梁，编号牌挂在梁底下，梁头挂一盏还亮着的灯），门框里、头顶上都透着月夜；石系船桩。"""
    r = rc(cv)
    bx0, bw, bh = D0 + 1214, 128, 104
    m = bm.blob_mask(bw, bh, rng, p=2.2, lump=0.1)
    img = bm.stone_shade(m, rng, SPAL, facet_w=8.0, ledges=0.3)
    cv.paste(img, bx0, DOCK_Y - bh + 1)
    for xx in range(bw):                                              # 顶上一层苔、几缕垂下来
        ys = np.nonzero(m[:, xx])[0]
        if len(ys) and rng.random() < 0.55:
            cv.put(bx0 + xx, DOCK_Y - bh + 1 + ys[0], bm.MOSS[2] if rng.random() < 0.4 else bm.MOSS[1])
            if rng.random() < 0.18:
                for d in range(1, int(rng.integers(2, 9))):
                    cv.put(bx0 + xx, DOCK_Y - bh + 1 + ys[0] + d, bm.MOSS[0])
    carve2(cv, D0 + 1222, DOCK_Y - 47, 22, 48, "arch", True, True, pal=SPAL)       # 货棚门洞：里面深处还点着一盏，光贴着地往外渐弱
    carve2(cv, D0 + 1226, DOCK_Y - 82, 7, 9, "arch", True, False, pal=SPAL)        # 门上一扇小窗，还透一点灯
    mx, my, mw, mh = MAP_R
    pm = np.zeros((H, SB_W), bool)                                    # 磨平的那块石面：只比周围平一点、亮一点，纹理照旧
    pm[my - 1:my + mh + 1, mx - 1:mx + mw + 1] = True
    lighten(cv, pm, 0.018)
    cv.rect(mx - 2, my + mh + 2, mx + mw + 1, my + mh + 2, SPAL[1])
    for nx in (mx + 3, mx + mw - 3):
        cv.put(nx, my + 3, SPAL[0])
    x0, x1, ty = LINTEL                                                # 石门框
    for k, px in enumerate((x0, x1 - 6)):
        stone_post(cv, px, ty + 6, DOCK_Y, 7, np.random.default_rng(90 + k))
    lm = bm.blob_mask(x1 - x0 + 8, 9, rng, p=4.0, lump=0.04)
    cv.paste(bm.stone_shade(lm, rng, SPAL, facet_w=8.0, ledges=0.3), x0 - 4, ty)
    cv.rect(x0 - 3, ty + 8, x1 + 3, ty + 8, SPAL[0])
    for px in PLATE_XS:
        cv.rect(px - 1, ty + 9, px, ty + 10, IRON[4])
    cv.rect(x1 + 1, ty + 9, x1 + 2, ty + 12, IRON[3])
    bm.lantern(r, x1 + 2, ty + 18, "hang", r=12)
    for bx in (D0 + 1268, D0 + 1330, D0 + 1462):                       # 石系船桩
        cv.rect(bx, DOCK_Y - 9, bx + 6, DOCK_Y, RPAL[2])
        cv.rect(bx - 1, DOCK_Y - 11, bx + 7, DOCK_Y - 9, RPAL[3])
        cv.rect(bx - 1, DOCK_Y - 11, bx + 7, DOCK_Y - 11, RPAL[4])
        cv.rect(bx + 6, DOCK_Y - 9, bx + 6, DOCK_Y, RPAL[4])


MID_W = 480 + int((SB_W - 480) * 0.6) + 8
MID_DX = int(SX * 0.6)            # 桥整体右挪 SX，中景跟着挪 0.6 倍，桥洞里框住的东西不变
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
    mbk = blobs(H, MID_W, rng, 1.5, 5.0)
    for x in range(MID_W):
        top = int(MID_BANK + prof[x])
        cv.put(x, top, MUD[4])
        cv.put(x, top + 1, MUD[3])
        for y in range(top + 2, H):
            t = (y - top) / 30
            k = 2.6 - t * 2.5 + (mbk[y, x] - 0.5) * 1.4
            cv.put(x, y, MUD[int(np.clip(np.floor(k), 0, 3))])
    # 石像：立在河里（脚下一圈水线），互相隔得很开
    pal = [blue(v, None, 256) for v in (0.1, 0.14, 0.19, 0.25, 0.31, 0.38)]
    for sx, w, h, kind, seed in ((250, 26, 64, "robe", 1), (452, 30, 78, "robe", 2), (860, 30, 52, "sit", 4)):
        sx += MID_DX
        r = np.random.default_rng(seed)
        m = statue_mask(w, h, kind, r)
        img = bm.stone_shade(m, r, pal, facet_w=8.0, ledges=0.2, moss=0.3)
        base = MID_BANK - 6
        cv.paste(img, sx - w // 2, base - h + 1)
        for x in range(sx - w // 2 - 3, sx + w // 2 + 4):          # 水线：一道亮的小涟漪
            if (x + seed) % 3:
                cv.put(x, base + 1, blue(0.36, 0.03, 246))
    # 石系船桩 + 柱头上一盏暖灯；一条小船
    for px in (360 + MID_DX, 760 + MID_DX):
        cv.rect(px - 1, MID_BANK - 22, px + 3, MID_BANK, pal[2])
        cv.rect(px + 3, MID_BANK - 22, px + 3, MID_BANK, pal[4])
        cv.rect(px - 2, MID_BANK - 24, px + 4, MID_BANK - 22, pal[3])
        cv.rect(px, MID_BANK - 29, px + 2, MID_BANK - 25, WARM2)
        cv.put(px + 1, MID_BANK - 28, WARM)
    # 河里几盏浮灯，隔得很远（小木托、一根杆、灯罩，水里一道暖的倒影）
    for fx in (90, 230 + MID_DX, 1040 + MID_DX, 1270):
        fy = MID_BANK - 3
        cv.rect(fx - 3, fy, fx + 3, fy, WOOD[2])
        cv.put(fx, fy - 1, IRON[3])
        cv.rect(fx - 1, fy - 5, fx + 1, fy - 2, WARM2)
        cv.put(fx, fy - 4, WARM)
        cv.put(fx, fy - 6, IRON[2])
        for k in range(1, 4):
            cv.put(fx + (k % 2), fy + 1 + k * 2, WARM3)
    return cv


def sb_front():
    """前景（1.3）：画面最下沿几丛近黑的芦苇 / 香蒲和一根歪的木桩，稀稀拉拉。"""
    w = 480 + int((SB_W - 480) * 1.3) + 8
    cv = Cv(w, H)
    rng = np.random.default_rng(23)
    dk = [blue(0.045), blue(0.065), blue(0.085)]
    for x0 in (40, 330, 700, 1020, 1380, 1700, 2050, 2380):
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


def sb_objects(main):
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
    out["southbridge_arch"] = (ox, oy, fr, {"states": {"default": 0, "scratches": 1}, "click": [cx - 30, 100, 60, 128]})
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
    out["southbridge_footprints"] = (SX + 520, SB_G + 1, fr, {"states": {"default": 0, "seen": 1}})
    # ---- 旧运输水道：default 洞口堆着塌下来的石块、上面垂着一帘干水草；
    #      revealed = 石块挪到两边，洞里很深的地方一点暖光（货台的灯），光顺着洞壁、水面往外一层层弱下去
    fr = []
    ox, oy = TUNNEL_X - 50, 138
    for rev in (False, True):
        r = np.random.default_rng(8)
        if not rev:
            c = Cv(100, 92)
            for (bx, by, bw, bh) in ((12, 196, 26, 32), (36, 190, 30, 38), (64, 200, 24, 28), (24, 170, 22, 24),
                                     (50, 168, 20, 24), (38, 152, 18, 18)):
                m = bm.blob_mask(bw, bh, r)
                c.paste(bm.stone_shade(m, r, RPAL, facet_w=8.0, ledges=0.3), bx, by - oy)
            for x in (17, 23, 31, 44, 58, 66, 79):                       # 洞顶垂下来几缕干水草：长短不一、颜色压到接近石头
                ln = int(r.integers(4, 19))
                for t in range(ln):
                    c.put(x + (t // 6) % 2 * (1 if x % 2 else -1), 150 - oy + t, bm.MOSS[0] if t < ln - 2 else SPAL[1])
        else:
            c = Cv(100, 92)
            c.a[:] = main.a[oy:oy + 92, ox:ox + 100]
            yy, xx = np.mgrid[0:92, 0:100]
            tun = arch_open(50, 40, 34, w=100)[oy:oy + 92] & (yy + oy <= SB_G - 4)
            fm = bm.opening_mask(16, 20, "arch")                       # 洞的那一头：一个小小的亮拱
            fx0, fy0 = 42, SB_G - 4 - 20 - oy
            far = np.zeros((92, 100), bool)
            far[fy0:fy0 + 20, fx0:fx0 + 16] = fm
            hole(c, fm, fx0, fy0, lit=True, halo=False)
            d = np.hypot((xx - 50) / 34.0, (yy + oy - (SB_G - 12)) / 30.0)       # 暖光沿着洞壁往外渐弱
            k = (1 - d) * 3.2 - (BAYER[yy % 4, xx % 4] - 0.5) * 0.9
            for y, x in zip(*np.nonzero(tun & ~far & (k > 0.6))):
                cc = tuple(int(v) for v in c.a[y, x, :3])
                c.a[y, x, :3] = bm.mixc(cc, bm.WARM[0] if k[y, x] < 1.6 else bm.WARM[1], min(0.8, 0.25 * k[y, x]))
            for x in range(16, 85):                                     # 水面上一道长长的暖倒影
                if abs(x - 50) < 14 - (abs(x - 50) > 8) * 4 and (x * 3) % 5 < 3:
                    c.put(x, SB_G - 3 - oy, bm.WARM[1] if abs(x - 50) < 6 else bm.WARM[0])
            for (bx, by, bw, bh) in ((0, 204, 16, 24), (84, 206, 16, 22)):
                m = bm.blob_mask(bw, bh, r)
                c.paste(bm.stone_shade(m, r, RPAL, facet_w=8.0, ledges=0.3), bx, by - oy)
        fr.append(c.a.copy())
    out["southbridge_waterway"] = (ox, oy, fr, {"states": {"default": 0, "revealed": 1}, "click": [ox + 10, 150, 80, 78]})
    # ---- 航线图：default 贴在货棚巨石磨平的那块石面上（几条航线，最右一条通到云层星）；fallen = 掉在台面上卷着
    mx, my, mw, mh = MAP_R
    fr = []
    for fallen in (False, True):
        c = Cv(mw + 12, DOCK_Y - my + 2)
        if not fallen:
            c.rect(2, 2, mw - 1, mh - 1, MAP)
            c.rect(mw - 1, 2, mw - 1, mh - 1, MAP_D)
            c.rect(2, mh - 1, mw - 1, mh - 1, MAP_D)
            c.poly([(mw - 7, mh - 1), (mw - 1, mh - 7), (mw - 1, mh - 1)], MAP_D)   # 卷起的一角
            c.rect(4, 4, 22, 5, INK)
            wear = blobs(mh, mw, np.random.default_rng(12), 2.5, 3.5)         # 受潮的旧纸：一团团发暗的水渍、边上磨毛
            for yy_ in range(3, mh - 1):
                for xx_ in range(3, mw - 1):
                    if wear[yy_, xx_] < 0.12 + 0.22 * max(0.0, yy_ / mh - 0.55) / 0.45:
                        c.put(xx_, yy_, MAP_D)
            for xx_ in range(2, mw):
                if (xx_ * 5) % 7 == 0:
                    c.a[2, xx_] = 0
            c.rect(2, 2, 2, mh - 1, MAP_D)
            pts = [(7, 34), (20, 30), (31, 21), (41, 17), (48, 10)]
            for (a_, b_), (cc, d_) in zip(pts, pts[1:]):
                c.line(a_, b_, cc, d_, INK)
            for a_, b_ in pts[:-1]:
                c.rect(a_ - 1, b_ - 1, a_ + 1, b_ + 1, INK)
            c.fill(c.mask_of_ellipse(45, 5, 52, 12), TAG)                # 终点：云层星（琥珀色的圆）
            c.line(7, 34, 24, 40, MAP_D)
            c.line(7, 34, 15, 20, MAP_D)
            for nx in (3, mw - 3):
                c.rect(nx, 3, nx + 1, 4, IRON[4])
        else:
            fy = DOCK_Y - my
            c.poly([(6, fy), (14, fy - 18), (34, fy - 14), (46, fy)], MAP_D)
            c.poly([(14, fy - 18), (34, fy - 14), (28, fy - 7), (17, fy - 10)], MAP)
            c.rect(34, fy - 3, mw + 6, fy, MAP)
            c.rect(34, fy, mw + 6, fy, MAP_D)
            c.line(38, fy - 2, mw + 2, fy - 2, INK)
            for nx in (3, mw - 3):
                c.rect(nx, 3, nx + 1, 4, IRON[4])
                c.put(nx, 5, MAP)
        fr.append(c.a.copy())
    out["southbridge_routemap"] = (mx, my, fr, {"states": {"default": 0, "fallen": 1}, "click": [mx, my, mw, DOCK_Y - my]})
    # ---- 编号牌 07 / 12 / 21：held = 取下来了（梁底下只剩钉子）；back = 挂回去
    for num, px in zip(("07", "12", "21"), PLATE_XS):
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
        out[f"southbridge_plate_{num}"] = (px - 8, LINTEL[2] + 10, fr, {"states": {"default": 0, "back": 0, "held": 1}})
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
    objs = sb_objects(main)
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
            "southbridge_ornament": HOUSE_X, "southbridge_arch_wrong": ARCHES[0][0], "southbridge_arch": ARCHES[1][0],
            "southbridge_footprints": SX + 596, "southbridge_waterway": TUNNEL_X, "southbridge_dock": D0 + 1250,
            "southbridge_routemap": MAP_R[0] + MAP_R[2] // 2, "southbridge_dock_step": D0 + 1204, "southbridge_plates": PLATE_XS[1],
            "southbridge_arch_far": ARCHES[2][0], "southbridge_view_spot": VIEW_SPOT,
            "southbridge_plate_07": PLATE_XS[0], "southbridge_plate_12": PLATE_XS[1], "southbridge_plate_21": PLATE_XS[2],
        },
        "walk": [12, SB_W - 14],
        "walk_when": [{"not": ["river_waterway_open"], "walk": [12, D0 + 1054]}],
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
            "sb_bank": (SX - 120, SX + 40, {}),
            "sb_view_off": (SX + 200, SX + 440, {}),
            "sb_view_on": (VIEW_CAM, VIEW_SPOT, {}),
            "sb_arch": (VIEW_CAM, SX + 600, {"southbridge_arch": "scratches", "southbridge_footprints": "seen", "southbridge_waterway": "revealed"}),
            "sb_gap": (SX + 960, SX + 1180, {}),
            "sb_waterway": (D0 + 820, D0 + 1040, {}),
            "sb_waterway_open": (D0 + 900, D0 + 1100, {"southbridge_waterway": "revealed"}),
            "sb_dock": (SB_W - 480, D0 + 1250, {"southbridge_waterway": "revealed"}),
            "sb_dock_fallen": (SB_W - 480, D0 + 1300, {"southbridge_waterway": "revealed", "southbridge_routemap": "fallen", "southbridge_plate_12": "held"}),
        }
        for name, (cl, chx, st) in shots.items():
            img = comp_room(la, layers, cl, False)
            img = over(img, obj_overlay(objs, st, cl))
            stand_in(img, chx - cl, sb_ground(chx))
            img = over(img, comp_room(la, layers, cl, True))
            big(img, 2).save(Path(prev) / f"{name}.png")
        # 取景框叠在场景上（alpha 0.7）：对上 / 没对上
        for name, cl in (("sb_vf_on", VIEW_CAM), ("sb_vf_off", VIEW_CAM - 52)):
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
    ap.add_argument("--only", default="southbridge",
                    help="默认只出南桥。仓库已交给 river-underwater 会话重做（10-30），别再用 warehouse 覆盖它的图")
    args = ap.parse_args()
    if args.preview:
        Path(args.preview).mkdir(parents=True, exist_ok=True)
    only = args.only.split(",")
    if "warehouse" in only:
        build_warehouse(args.preview)
    if "southbridge" in only and "build_southbridge" in globals():
        build_southbridge(args.preview)
    print("ok")
