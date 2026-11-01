"""第三章 · 结局三：云层星的风帆小镇 town + 晨暂住的小屋 town_room。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/cloud_town_art.py --sketch 目录   # 广场那一屏的草图
    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/cloud_town_art.py [--preview 目录]

背景不画：天、余晖、石针、积雨云柱、四层云海、前景云都是作者的 art/cloud/ 原图（room.json 直接引用，原样的视差 / 漂移），
一张都不改。这里只画坐在它上面的小镇：能踩的云台（用 tools/cloud_art.py 同一套 Field 球堆画法、同一条色阶，和作者的云融在一起）、
房子、风车、帆、喷泉、长椅、花圃。

10-31 作者看了第一轮草图：「怎么是蒙古包」「天空场景是建立在之前最开始做的粉色天空上的，没叫你新画」。
所以：不要圆顶；房子往上长、细高，和云里的石针呼应；风车和帆是主角。光照跟作者的云层一样：太阳刚落，光从左边低处来
（余晖），朝光的边是玫瑰色，背光偏靛紫；窗里亮着暖黄的灯（这里的人是热情的）。
所有随机固定 seed；alpha 只有 0/255，布帆和水是固定的半透明（SAIL_A / WATER_A）。不碰 art/手改清单.json 里的文件。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "cloud_town"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cloud_art as CA  # noqa: E402  作者云层的画法（Field 球堆、cloud_pal 色阶）；只 import，不改


# ======================================================================= 颜色（OKLCh 取，和作者的云一个色相家族）
def hexc(s):
    if not isinstance(s, str):
        return np.array(s[:3], np.uint8)
    s = s.lstrip("#")
    return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], np.uint8)


def lch_ramp(L0, L1, C0, C1, h0, h1, n):
    out = []
    for i in range(n):
        t = i / (n - 1)
        out.append("#%02x%02x%02x" % CA.from_lch(L0 + (L1 - L0) * t, C0 + (C1 - C0) * t, h0 + (h1 - h0) * t))
    return out


# 下面的色阶都是 暗 → 亮
CLOUD = ["#%02x%02x%02x" % c for c in CA.cloud_pal(0.10, 0.42, 7, C_lo=0.045, C_hi=0.08, h_lo=286, h_hi=348)]   # = 作者 main 层
WALL = lch_ramp(0.30, 0.86, 0.035, 0.05, 288, 352, 7)        # 白墙在黄昏里：背光靛紫 → 朝光玫瑰白
WALL_RIM = "#%02x%02x%02x" % CA.from_lch(0.92, 0.055, 32)     # 贴着余晖那条边
WHEAT = lch_ramp(0.36, 0.86, 0.05, 0.10, 350, 432, 6)         # 草顶、木头：暗端玫瑰棕 → 亮端麦黄
SAIL = lch_ramp(0.42, 0.86, 0.05, 0.06, 285, 245, 5)         # 布帆：暗端蓝紫 → 亮端淡蓝
SAIL_A = 210
STONE = lch_ramp(0.22, 0.50, 0.03, 0.05, 292, 338, 5)        # 广场石砖（湿、暗）
WATER = lch_ramp(0.50, 0.92, 0.06, 0.04, 262, 235, 4)
WATER_A = 215
LAMP = ["#c9805e", "#eba765", "#fbcf86", "#fff0c2"]          # 窗里的暖灯：暗 → 亮
DOOR = lch_ramp(0.36, 0.70, 0.05, 0.07, 280, 250, 4)         # 淡蓝门
FLOWER = ["#e88fae", "#f6b8c9", "#f2c56f", "#fbe3a0"]
LEAF = lch_ramp(0.30, 0.62, 0.04, 0.06, 200, 150, 4)
SOIL = lch_ramp(0.22, 0.40, 0.03, 0.04, 330, 380, 3)

GLOW_DIR = np.array([-0.82, -0.57])                          # 光从左边低处来（和 tools/cloud_art.py 的 LIGHT 一样）


# ======================================================================= 画布
class Layer:
    """RGBA 画布。ox / oy = 这张画布左上角在大图里的位置：画图函数一律用大图坐标，小画布只算自己那一块（快）。"""

    def __init__(self, w, h, ox=0, oy=0):
        self.w, self.h, self.ox, self.oy = w, h, ox, oy
        self.a = np.zeros((h, w, 4), np.uint8)
        yy, xx = np.mgrid[0:h, 0:w]
        self.yy = yy + oy + 0.5
        self.xx = xx + ox + 0.5

    def put(self, mask, col, alpha=255):
        if isinstance(col, str):
            col = hexc(col)
        self.a[mask, :3] = col
        self.a[mask, 3] = alpha

    def px(self, x, y, col, alpha=255):
        x, y = math.floor(x) - self.ox, math.floor(y) - self.oy
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x, :3] = hexc(col) if isinstance(col, str) else col
            self.a[y, x, 3] = alpha

    def rect(self, x0, y0, x1, y1, col, alpha=255):
        x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
        x0, x1, y0, y1 = x0 - self.ox, x1 - self.ox, y0 - self.oy, y1 - self.oy
        x0, y0 = max(x0, 0), max(y0, 0)
        if x1 > x0 and y1 > y0:
            self.a[y0:y1, x0:x1, :3] = hexc(col) if isinstance(col, str) else col
            self.a[y0:y1, x0:x1, 3] = alpha

    def over(self, other: "Layer", dx=None, dy=None):
        """other 叠在上面（other 的不透明像素盖住；半透明的照 alpha 混）。不给 dx / dy 就按两张的 ox / oy 对齐。"""
        dx = other.ox - self.ox if dx is None else dx
        dy = other.oy - self.oy if dy is None else dy
        h, w = other.h, other.w
        x0, y0 = max(dx, 0), max(dy, 0)
        x1, y1 = min(dx + w, self.w), min(dy + h, self.h)
        if x1 <= x0 or y1 <= y0:
            return
        src = other.a[y0 - dy:y1 - dy, x0 - dx:x1 - dx].astype(np.float32)
        dst = self.a[y0:y1, x0:x1].astype(np.float32)
        sa = src[..., 3:4] / 255.0
        da = dst[..., 3:4] / 255.0
        oa = sa + da * (1 - sa)
        rgb = np.where(oa > 0, (src[..., :3] * sa + dst[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6), 0)
        self.a[y0:y1, x0:x1, :3] = np.round(rgb).astype(np.uint8)
        self.a[y0:y1, x0:x1, 3] = np.round(oa[..., 0] * 255).astype(np.uint8)


def piece(x0, y0, x1, y1):
    """大图里 (x0, y0)–(x1, y1) 这一块的小画布"""
    x0, y0 = math.floor(x0), math.floor(y0)
    return Layer(math.ceil(x1) - x0, math.ceil(y1) - y0, x0, y0)


def ellipse(L: Layer, cx, cy, rx, ry):
    return ((L.xx - cx) / rx) ** 2 + ((L.yy - cy) / ry) ** 2 <= 1.0


def poly_mask(L: Layer, pts):
    """多边形（偶奇规则，像素中心取样）"""
    pts = np.asarray(pts, np.float64)
    x, y = L.xx, L.yy
    inside = np.zeros((L.h, L.w), bool)
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        cond = ((yi > y) != (yj > y))
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
        inside ^= cond & (x < xint)
        j = i
    return inside


def line4(x0, y0, x1, y1):
    """四邻接的一像素线（拐角处补一格，错位时有边相连，不只是角碰角）"""
    x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x1 > x0 else -1
    sy = 1 if y1 > y0 else -1
    x, y, ix, iy = x0, y0, 0, 0
    out = [(x, y)]
    while ix < dx or iy < dy:                              # 每一步只走一个方向 → 四邻接
        if dy == 0 or (dx > 0 and ix < dx and (0.5 + ix) / dx < (0.5 + iy) / dy):
            x += sx
            ix += 1
        else:
            y += sy
            iy += 1
        out.append((x, y))
    return out


def curve4(pts):
    """折线点串 → 四邻接像素（相邻点之间 line4）"""
    out = []
    for (a, b) in zip(pts[:-1], pts[1:]):
        seg = line4(a[0], a[1], b[0], b[1])
        if out and out[-1] == seg[0]:
            seg = seg[1:]
        out.extend(seg)
    return out


def stroke(L: Layer, pix, col, width=1, alpha=255):
    c = hexc(col) if isinstance(col, str) else col
    for (x, y) in pix:
        for k in range(width):
            L.px(x + k, y, c, alpha)


def band(v, cuts):
    """v 按 cuts（升序）分档：返回档号 0..len(cuts)"""
    return np.searchsorted(np.asarray(cuts), v)


def noise2(h, w, sx, sy, seed):
    """平滑噪声（双线性插值的随机格点），-1..1"""
    rng = np.random.default_rng(seed)
    gh, gw = int(h / sy) + 3, int(w / sx) + 3
    g = rng.uniform(-1, 1, (gh, gw))
    yy, xx = np.mgrid[0:h, 0:w]
    fy, fx = yy / sy, xx / sx
    y0, x0 = fy.astype(int), fx.astype(int)
    ty, tx = fy - y0, fx - x0
    ty = ty * ty * (3 - 2 * ty)
    tx = tx * tx * (3 - 2 * tx)
    a = g[y0, x0] * (1 - tx) + g[y0, x0 + 1] * tx
    b = g[y0 + 1, x0] * (1 - tx) + g[y0 + 1, x0 + 1] * tx
    return a * (1 - ty) + b * ty


# ======================================================================= 杂点清理
def despeckle(L: Layer, passes=3):
    """孤立的单像素（和上下左右四格颜色都不一样）→ 改成周围最多的那个颜色；孤立的不透明点 / 透明洞也补掉。"""
    a = L.a
    for _ in range(passes):
        key = (a[..., 0].astype(np.int64) << 24) | (a[..., 1].astype(np.int64) << 16) | (a[..., 2].astype(np.int64) << 8) | a[..., 3]
        k = np.pad(key, 1, mode="edge")
        c = k[1:-1, 1:-1]
        nb = [k[:-2, 1:-1], k[2:, 1:-1], k[1:-1, :-2], k[1:-1, 2:]]
        alone = np.ones_like(c, bool)
        for q in nb:
            alone &= q != c
        ys, xs = np.nonzero(alone)
        if len(ys) == 0:
            break
        P = np.pad(a, ((1, 1), (1, 1), (0, 0)), mode="edge")
        for y, x in zip(ys, xs):
            cand = [k[y, x + 1], k[y + 2, x + 1], k[y + 1, x], k[y + 1, x + 2]]
            vals, cnt = np.unique(cand, return_counts=True)
            best = vals[np.argmax(cnt)]
            for (yy, xx) in ((y, x + 1), (y + 2, x + 1), (y + 1, x), (y + 1, x + 2)):
                if k[yy, xx] == best:
                    a[y, x] = P[yy, xx]
                    break
    return L


def find_speckles(a):
    key = (a[..., 0].astype(np.int64) << 24) | (a[..., 1].astype(np.int64) << 16) | (a[..., 2].astype(np.int64) << 8) | a[..., 3]
    k = np.pad(key, 1, mode="constant", constant_values=-1)
    c = k[1:-1, 1:-1]
    alone = (a[..., 3] > 0)
    for q in (k[:-2, 1:-1], k[2:, 1:-1], k[1:-1, :-2], k[1:-1, 2:]):
        alone &= q != c
    return list(zip(*np.nonzero(alone)))




# ======================================================================= 云（作者的 Field 画法）
PAD = 48


def cloud_field(w, h=270):
    """CA.Field 两头各多留 PAD 像素（它的球会左右绕回，宽图两头不能互相漏），render 完再裁掉"""
    return CA.Field(w + 2 * PAD, h)


def render_field(F, w, pal, **kw):
    a = F.render(pal, **kw)
    L = Layer(w, a.shape[0])
    L.a[:] = a[:, PAD:PAD + w]
    return L


def ground_cloud(w, terrain, seed, flats=(), front_rows=((7, 1.0, (13, 24)), (17, 2.0, (15, 28)), (29, 3.0, (17, 32)))):
    """能走的云顶（照 tools/cloud_art.py 的 main_layer）：一串宽扁的圆顶落在 terrain(x) 上，顶上偶尔鼓个 1 像素的小包，
    正面几排菜花云团一排比一排暗。flats = [(x0, x1), …] 这几段不鼓小包（广场、空地：地平）。"""
    F = cloud_field(w)
    rng = np.random.default_rng(seed)
    ref = float(np.mean([terrain(x) for x in range(0, w, 7)]))
    F.new_group()
    x = -PAD + 0.0
    while x < w + PAD:
        rx = rng.uniform(12, 24)
        ry = rx * rng.uniform(0.26, 0.34)
        top = terrain(min(max(x, 0), w - 1)) + rng.uniform(-0.6, 0.8)
        F.ball(x + PAD, top + ry, rx, ry, rng.uniform(0, 2), rz=rx * 0.5, ref=ref, unit=8, wrap=False)
        x += rx * rng.uniform(1.15, 1.45)
    gl0 = np.argmax(F.sid >= 0, 0)
    x = rng.uniform(0, 10)
    while x < w:
        rx = rng.uniform(4, 8)
        ry = rng.uniform(1.4, 2.2)
        if not any(a - 8 <= x <= b + 8 for a, b in flats):
            g = gl0[int(x) + PAD]
            F.ball(x + PAD, g + ry - rng.uniform(0.5, 1.1), rx, ry, 3.0 + rng.uniform(0, 1), rz=rx * 0.4, ref=ref, unit=8,
                   wrap=False)
        x += rx * rng.uniform(2.0, 4.0)
    for k, (dy, dark, rr) in enumerate(front_rows):
        n = int(w / 960 * (20 - 4 * k)) + 2
        for cx in np.sort(rng.uniform(-20, w + 20, n)):
            r = rng.uniform(*rr)
            F.new_group()
            F.row = 10 + k
            F.cauli(cx + PAD, ref + dy + r * 0.6 * rng.uniform(0.4, 0.9), r, 20 + 30 * k, rng, sq=0.6, depth=2,
                    kids=(2, 4), ks=(0.32, 0.55), dark=dark, rmin=3.0, spread=(-165, -15), ref=ref, unit=8)
    pal = CA.cloud_pal(0.10, 0.42, 7, C_lo=0.045, C_hi=0.08, h_lo=286, h_hi=348)
    L = render_field(F, w, pal, body=4, rim=(1.5, 3.0), crease=2.0, bands=(0.6, 1.5, 2.6, 3.6), run_bands=(4, 10, 18, 28))
    # 走的那条边：每列最上面一个像素至少亮到第 5 档（读得出能踩），和作者的 main 一样
    walk = hexc("#%02x%02x%02x" % pal[5])
    gl = np.argmax(L.a[..., 3] > 0, 0)
    for xx in range(w):
        y = gl[xx]
        if L.a[y, xx, 3] and int(L.a[y, xx, :3].astype(int).sum()) < int(walk.astype(int).sum()):
            L.a[y, xx, :3] = walk
    return L


def mound_cloud(w, heaps, seed, deck=None, lift=0.1):
    """房子脚下的云丘（在晨后面一层）：几堆积云（作者 heap 的画法），顶比作者的 near 亮一点（小镇在上面，暖一点）。
    heaps = [(cx, 底, 宽, 高), …]；deck = 底下一层扁云甲板的团顶 y。"""
    F = cloud_field(w)
    rng = np.random.default_rng(seed)
    for (cx, base, wd, ht) in heaps:
        F.heap(cx + PAD, base, wd, ht, 0, rng, sq=0.62, depth=2, kids=(2, 4), ks=(0.3, 0.55), rmin=2.5)
    if deck is not None:
        F.new_group()
        x = -PAD + 0.0
        while x < w + PAD:
            r = rng.uniform(18, 30)
            F.cauli(x + PAD, deck + r * 0.3, r, 40, rng, sq=0.32, depth=1, kids=(1, 3), ks=(0.3, 0.5), rmin=3.0,
                    spread=(-160, -20))
            x += r * rng.uniform(1.2, 1.6)
    pal = CA.cloud_pal(0.12 + lift, 0.46 + lift, 7, C_lo=0.045, C_hi=0.08, h_lo=288, h_hi=350)
    return render_field(F, w, pal, body=4, rim=(1.5, 3.2), crease=2.0, run_bands=(5, 12, 22, 34))


# ======================================================================= 房子：细高的白塔
def shade_cyl(L: Layer, m, cx, half, top, base, rim=True, lift=0):
    """圆柱（塔身）的明暗：光从左边低处来 —— 左边一道玫瑰色的亮边，往右一档档进靛紫；下半截再暗一档（贴着云的地方没光）。
    lift < 0 = 整体暗几档（远处的塔）"""
    u = (L.xx - cx) / np.maximum(half, 0.5)
    idx = 5 - band(u, (-0.62, -0.05, 0.5, 0.82)) + lift
    v = (L.yy - top) / max(base - top, 1)
    idx = idx - (v > 0.72) - (v > 0.9)
    idx = np.clip(idx, max(1 + lift, 0), 6)
    for k in range(7):
        L.put(m & (idx == k), WALL[k])
    if rim:
        edge = m & ~np.roll(m, 1, axis=1) & (v < 0.85)
        L.put(edge, WALL_RIM if lift == 0 else WALL[6 + lift])


def spire_cap(L: Layer, cx, top, half, cap_h, flare=1.5, pal=None, dim=0):
    """尖顶：细长的草顶，两边是微微内凹的弧线收到一个尖（和云里的石针一个味道），檐口比塔身宽 flare，往下弯一点。
    pal = 草顶（WHEAT）或刷了漆的淡蓝木顶（CAPB）。返回尖的位置。"""
    pal = pal or WHEAT
    pts = []
    n = 16
    rw = half + flare
    for i in range(n + 1):                                  # 左边：从檐口到尖，内凹
        t = i / n
        pts.append((cx - rw * (1 - t) ** 2.2, top + 1.5 - (cap_h + 1.5) * t))
    for i in range(n, -1, -1):
        t = i / n
        pts.append((cx + rw * (1 - t) ** 2.2 + 0.01, top + 1.5 - (cap_h + 1.5) * t))
    pts.append((cx + rw - 1, top + 2.6))
    pts.append((cx - rw + 1, top + 2.6))
    m = poly_mask(L, pts)
    u = (L.xx - cx) / rw
    idx = np.clip(4 - band(u, (-0.45, 0.05, 0.5)) - dim, 0, 5)
    for k in range(6):
        L.put(m & (idx == k), pal[k])
    L.put(m & ~np.roll(m, 1, axis=1), pal[5 - dim])        # 朝光的边
    L.put(m & (L.yy >= top + 1.5), pal[max(1 - dim, 0)])   # 檐口下沿的影子
    return cx, top - cap_h


def cap_half(T, y):
    """塔 T 的尖顶在高度 y 处的半宽（绳子系在尖顶的边上用）"""
    t = np.clip((T["top"] + 1.5 - y) / (T["cap_h"] + 1.5), 0, 1)
    return T["rw"] * (1 - t) ** 2.2


def lamp_window(L: Layer, x, y, w, h, lit=True):
    """拱窗：亮着灯的是暖黄（上亮下暗一档、中间一根竖棂），没亮的是映着天的暗紫玻璃（一道斜的亮）。不是实心色块。"""
    w, h = int(w), int(h)
    r = w / 2.0
    m = (L.xx >= x) & (L.xx < x + w) & (L.yy >= y + r) & (L.yy < y + h)
    m |= ellipse(L, x + r, y + r, r, r) & (L.yy < y + r + 0.5)
    rim = (np.roll(m, -1, axis=0) | np.roll(m, -1, axis=1) | np.roll(m, 1, axis=1)) & ~m
    L.put(rim, WALL[2])
    if lit:
        L.put(m, LAMP[2])
        L.put(m & (L.yy < y + r + 1), LAMP[3])
        L.put(m & (L.yy >= y + h - 2), LAMP[1])
        if w >= 4:
            mid = int(x + w // 2) - L.ox
            col = m[:, mid] & (L.yy[:, 0] >= y + 1)
            L.a[col, mid, :3] = hexc(LAMP[0])
    else:
        L.put(m, WALL[1])
        L.put(m & (L.yy < y + r + 1), SAIL[1])
        L.px(x + 1, y + r, SAIL[2])
        L.px(x + 1, y + r + 1, SAIL[2])
    return m


def arch_door(L: Layer, x, base, w, h, lit=False):
    """拱门：淡蓝的门板（亮着的门：门缝漏出暖光），门洞上沿和右边深一档"""
    m = (L.xx >= x) & (L.xx < x + w) & (L.yy >= base - h + w / 2.0) & (L.yy < base)
    m |= ellipse(L, x + w / 2.0, base - h + w / 2.0, w / 2.0, w / 2.0) & (L.yy < base - h + w / 2.0 + 0.5)
    L.put(m, DOOR[2])
    L.put(m & (L.xx < x + 1.5), DOOR[3])
    top_sh = m & ~np.roll(m, 1, axis=0)
    L.put(top_sh | (np.roll(top_sh, 1, axis=0) & m), DOOR[1])
    L.put(m & ~np.roll(m, -1, axis=1), DOOR[0])
    if lit:                                               # 门开着一条缝，里面的暖光
        gap = m & (L.xx >= x + w - 3) & (L.xx < x + w - 1) & (L.yy > base - h + w / 2.0)
        L.put(gap, LAMP[2])
    else:
        mid = int(x + w // 2) - L.ox
        col = m[:, mid] & (L.yy[:, 0] > base - h + w / 2.0 + 1)
        L.a[col, mid, :3] = hexc(DOOR[1])
    L.px(int(x + w // 2) + 1, base - h // 2 + 1, WHEAT[4])
    return m


def flower_box(L: Layer, x, y, w):
    """窗下的花箱：两行木箱，上面一行叶子，两头各一小团粉花"""
    L.rect(x - 1, y + 1, x + w + 1, y + 3, WHEAT[2])
    L.rect(x - 1, y + 2, x + w + 1, y + 3, WHEAT[1])
    L.rect(x - 1, y, x + w + 1, y + 1, LEAF[1])
    L.rect(x - 1, y - 1, x + 1, y + 1, FLOWER[0])
    L.rect(x + w - 1, y - 1, x + w + 1, y + 1, FLOWER[1])
    L.px(x - 1, y - 1, FLOWER[1])


def balcony(L: Layer, cx, y, half):
    """塔腰上一圈小木阳台，栏杆上搭着一块淡蓝的布（帆布的意思）：一条托梁 + 布，布下沿两个圆角"""
    x0, x1 = int(round(cx - half - 2)), int(round(cx + half + 2))
    L.rect(x0, y + 4, x1, y + 6, WHEAT[2])
    L.rect(x0, y + 4, x1, y + 5, WHEAT[4])
    m = (L.xx >= x0) & (L.xx < x1) & (L.yy >= y) & (L.yy < y + 4)
    m &= ~(((L.xx < x0 + 1) | (L.xx >= x1 - 1)) & (L.yy < y + 1))
    u = (L.xx - x0) / max(x1 - x0, 1)
    L.put(m, SAIL[3], 255)
    L.put(m & (u > 0.55), SAIL[2], 255)
    L.put(m & (u < 0.18), SAIL[4], 255)
    L.put(m & (L.yy < y + 1), SAIL[4], 255)


def tower_house(L: Layer, cx, base, w, h, cap_h, windows=(), door=None, taper=2, cap=None, dim=0, box=False, balc=None):
    """细高的白塔屋：圆塔身（往上收 taper 像素，每好几行才收一格，边是缓坡）+ 尖顶。
    windows = [(dy 从塔顶往下, 宽, 高, 亮不亮, dx), …]；door = (宽, 高, 亮不亮)；box = 亮着的窗下挂花箱；balc = 阳台在塔顶往下几行。
    dim = 远处的塔暗几档。返回塔的几何（尖、塔顶、尖顶半宽…）。"""
    top = base - h
    t = np.clip((base - L.yy) / h, 0, 1)
    flare = 2.2 * np.clip(1 - (base - L.yy) / 7.0, 0, 1) ** 2         # 塔脚往外撇一点（不是台阶）：稳稳坐在云里
    half = w / 2.0 - taper * t + flare
    m = (np.abs(L.xx - cx) < half) & (L.yy >= top) & (L.yy < base)
    shade_cyl(L, m, cx, half, top, base, lift=-dim)
    if balc is not None:
        balcony(L, cx, top + balc, w / 2.0 - taper * (h - balc) / h)
    for (dy, ww, wh, lit, dx) in windows:
        wx = int(round(cx - ww / 2.0 + dx))
        lamp_window(L, wx, top + dy, ww, wh, lit)
        if box and lit and dim == 0:
            flower_box(L, wx, top + dy + wh, ww)
    if door is not None:
        dw, dh, lit = door
        arch_door(L, int(round(cx - dw / 2.0)), base, dw, dh, lit)
    tx, ty = spire_cap(L, cx, top, w / 2.0 - taper, cap_h, pal=cap, dim=dim)
    return {"cx": cx, "top": top, "base": base, "tip": (tx, ty), "rw": w / 2.0 - taper + 1.5, "cap_h": cap_h, "w": w}


def finial_mast(L: Layer, x, tip, length):
    """尖顶上再伸出去的一根细杆（挂帆用），顶上一颗小麦黄的球"""
    L.rect(x, tip - length, x + 1, tip + 1, WHEAT[2])
    L.rect(x - 1, tip - length - 2, x + 2, tip - length, WHEAT[4])
    L.px(x - 1, tip - length - 2, WHEAT[5])
    return x, tip - length


def mast(L: Layer, x, top, bot, w=2):
    L.rect(x, top, x + w, bot, WHEAT[2])
    L.rect(x, top, x + 1, bot, WHEAT[4])
    L.rect(x - 1, top - 2, x + w + 1, top, WHEAT[4])


# ======================================================================= 布帆
def jib(L: Layer, mx, top, bot, reach, bulge, lift=2, alpha=SAIL_A, dark=0):
    """杆上的三角帆，顺风往右鼓：前缘贴着杆（mx 右边一列），帆脚往右，后缘外凸。迎着余晖那半亮，兜风的肚子暗一档。"""
    head = np.array([mx + 1.0, top])
    tack = np.array([mx + 1.0, bot])
    clew = np.array([mx + 1.0 + reach, bot - lift])
    pts = [tuple(tack), tuple(head)]
    d = clew - head
    nrm = np.array([d[1], -d[0]]) / (np.linalg.norm(d) + 1e-9)
    for t in np.linspace(0, 1, 16)[1:]:
        pts.append(tuple(head + d * t + nrm * bulge * math.sin(math.pi * t)))
    for t in np.linspace(0, 1, 6)[1:-1]:
        pts.append(tuple(clew + (tack - clew) * t + np.array([0, 1.2 * math.sin(math.pi * t)])))
    m = poly_mask(L, pts) & (L.xx > mx + 1)
    u = (L.xx - (mx + 1)) / max(reach + bulge, 1)
    v = (L.yy - top) / max(bot - top, 1)
    idx = np.clip(4 - band(u * 0.85 + v * 0.4, (0.3, 0.62, 0.95)) - dark, 0, 4)
    for k in range(5):
        L.put(m & (idx == k), SAIL[k], alpha)
    return m


def rope_sails(L: Layer, x0, y0, x1, y1, sag, panels, swing, alpha=SAIL_A):
    """两个尖顶之间一条下垂的绳子，绳上挂一排长方的小帆（下摆被风往右吹，左边亮右边暗）。panels = [(位置 0..1, 宽, 长), …]；
    swing = 下摆往右吹出去多少（一个数，或者每面帆一个）"""
    def rope_y(x):
        return y0 + (y1 - y0) * (x - x0) / (x1 - x0) + sag * math.sin(math.pi * (x - x0) / (x1 - x0))

    for i, (t, pw, ph) in enumerate(panels):
        px0 = x0 + (x1 - x0) * t
        px1 = px0 + pw
        ya, yb = rope_y(px0) + 1, rope_y(px1) + 1
        sw = (swing[i] if isinstance(swing, (list, tuple)) else swing) * ph / 14.0
        pts = [(px0, ya)]
        for k in range(1, 7):
            f = k / 6
            pts.append((px0 + sw * f * f + 1.0 * math.sin(math.pi * f), ya + ph * f))
        for k in range(1, 6):
            f = k / 5
            pts.append((px0 + sw + pw * f, ya + ph + (yb - ya) * f + 0.8 * math.sin(math.pi * f)))
        for k in range(1, 7):
            f = 1 - k / 6
            pts.append((px1 + sw * f * f + 1.4 * math.sin(math.pi * f), yb + ph * f))
        m = poly_mask(L, pts)
        u = (L.xx - px0 - sw * np.clip((L.yy - ya) / ph, 0, 1) ** 2) / pw
        idx = np.clip(4 - band(u, (0.3, 0.68)), 2, 4)
        for k in range(5):
            L.put(m & (idx == k), SAIL[k], alpha)
    xs = np.linspace(x0, x1, 40)
    rope = curve4([(x, rope_y(x)) for x in xs])
    stroke(L, rope, WHEAT[1])
    return rope


# ======================================================================= 风车转子、水车、喷泉、长椅
def rotor(size, ang, arms=8, r=None, hub=2, sail_frac=(0.16, 0.97), alpha=SAIL_A):
    """风车的转子（正对着看）：arms 根木条，每根一侧挂一面三角布帆（Mykonos 风车那种）。返回 Layer。"""
    L = Layer(size, size)
    c = size / 2.0
    r = r or (size / 2.0 - 1)
    step = 2 * math.pi / arms

    def pol(a, f):
        return (c + math.cos(a) * r * f, c + math.sin(a) * r * f)

    ang_px = np.arctan2(L.yy - c, L.xx - c)
    for i in range(arms):
        a = ang + i * step
        m = poly_mask(L, [pol(a, sail_frac[0]), pol(a, sail_frac[1]), pol(a + step * 0.52, 0.9), pol(a + step * 0.3, 0.3)])
        da = np.mod(ang_px - a, 2 * math.pi)
        # 帆朝着余晖（左边）的那几面亮一档
        facing = math.cos(a + step * 0.26) < -0.2
        hi, lo = (4, 3) if facing else (3, 2)
        L.put(m & (da < step * 0.24), SAIL[hi], alpha)
        L.put(m & (da >= step * 0.24), SAIL[lo], alpha)
    for i in range(arms):
        a = ang + i * step
        for (x, y) in line4(c - 0.5, c - 0.5, c - 0.5 + math.cos(a) * r, c - 0.5 + math.sin(a) * r):
            L.px(x, y, WHEAT[2])
            if r > 20:
                L.px(x + (1 if abs(math.sin(a)) > 0.7 else 0), y + (1 if abs(math.sin(a)) <= 0.7 else 0), WHEAT[1])
    hm = ellipse(L, c, c, hub + 0.6, hub + 0.6)
    L.put(hm, WHEAT[3])
    L.put(hm & (L.xx < c), WHEAT[5])
    return L


def waterwheel(size, ang, spokes=8):
    L = Layer(size, size)
    c = size / 2.0
    r = size / 2.0 - 2.5
    ring = ellipse(L, c, c, r, r) & ~ellipse(L, c, c, r - 2, r - 2)
    L.put(ring, WHEAT[2])
    L.put(ring & (L.xx < c - r * 0.3), WHEAT[4])
    for i in range(spokes):
        a = ang + i * 2 * math.pi / spokes
        ca, sa = math.cos(a), math.sin(a)
        for (x, y) in line4(c - 0.5, c - 0.5, c - 0.5 + ca * (r - 1), c - 0.5 + sa * (r - 1)):
            L.px(x, y, WHEAT[1])
        bx, by = c + ca * (r + 1), c + sa * (r + 1)
        bm = (((L.xx - bx) * ca + (L.yy - by) * sa) ** 2 <= 2.3 ** 2) & (((L.xx - bx) * -sa + (L.yy - by) * ca) ** 2 <= 2.0 ** 2)
        L.put(bm, WHEAT[3] if ca < 0.2 else WHEAT[2])
    L.put(ellipse(L, c, c, 2.6, 2.6), WHEAT[1])
    L.put(ellipse(L, c - 0.6, c - 0.6, 1.4, 1.4), WHEAT[4])
    return L


def fountain(L: Layer, cx, base, bw=110, bh=14, col_h=26, bowl_w=44):
    """喷泉（侧面看）：白石池壁 + 池口一圈很扁的椭圆（石唇 + 水面）+ 中间一根柱子托着浅碗。返回 (碗沿 y, 池沿 y)。"""
    x0 = cx - bw / 2.0
    rim_y = base - bh
    m = (L.xx >= x0) & (L.xx < x0 + bw) & (L.yy >= rim_y) & (L.yy < base)
    m &= ~((L.xx < x0 + 3) & (L.yy >= base - 3) & ((L.xx - (x0 + 3)) ** 2 + (L.yy - (base - 3)) ** 2 > 9))
    m &= ~((L.xx > x0 + bw - 3) & (L.yy >= base - 3) & ((L.xx - (x0 + bw - 3)) ** 2 + (L.yy - (base - 3)) ** 2 > 9))
    u = (L.xx - cx) / (bw / 2.0)
    idx = np.clip(4 - band(u, (-0.7, -0.1, 0.55)), 1, 5)
    for k in range(7):
        L.put(m & (idx == k), WALL[k])
    L.put(m & ~np.roll(m, 1, axis=1), WALL_RIM)
    L.put(m & (L.yy < rim_y + 2), WALL[2])
    L.put(m & (L.yy >= base - 3), WALL[2])
    tile = m & (L.yy >= base - 9) & (L.yy < base - 6)               # 池壁中间一圈淡蓝的瓷砖带
    L.put(tile, SAIL[3])
    L.put(tile & (u > 0.55), SAIL[2])
    L.put(tile & (u < -0.7), SAIL[4])
    L.put(tile & (L.yy >= base - 7), SAIL[2])
    lip = ellipse(L, cx, rim_y, bw / 2.0 + 1, 3.6)
    L.put(lip, WALL[5])
    L.put(lip & (u < -0.6), WALL[6])
    L.put(lip & (u > 0.5) & (L.yy >= rim_y), WALL[4])
    pool = ellipse(L, cx, rim_y - 0.3, bw / 2.0 - 3, 2.2)
    L.put(pool, WATER[1])
    L.put(pool & (L.yy < rim_y - 0.5), WATER[2])
    cm = (np.abs(L.xx - cx) < 3.5) & (L.yy >= rim_y - col_h) & (L.yy < rim_y)
    L.put(cm, WALL[3])
    L.put(cm & (L.xx < cx - 1), WALL[5])
    L.put(cm & (L.xx > cx + 1.5), WALL[2])
    by = rim_y - col_h
    bm = ellipse(L, cx, by, bowl_w / 2.0, 6) & (L.yy >= by)
    bm |= (np.abs(L.xx - cx) < 4.5) & (L.yy >= by + 5) & (L.yy < by + 9)
    u = (L.xx - cx) / (bowl_w / 2.0)
    idx = np.clip(4 - band(u, (-0.6, 0.0, 0.6)) - (L.yy > by + 3), 1, 6)
    for k in range(7):
        L.put(bm & (idx == k), WALL[k])
    L.put(bm & (L.yy < by + 1.5), WALL[6])
    return by, rim_y


def water_curtain(L: Layer, cx, top_y, rim_y, bowl_w, phase=0.0, alpha=WATER_A):
    """碗沿两边落下的水帘 + 碗顶冒起的一小股；phase 0..1 让亮的那几段往下流"""
    hw = bowl_w / 2.0
    for side in (-1, 1):
        po, pi_ = [], []
        for k in range(16):
            f = k / 15
            yv = top_y + (rim_y - top_y) * f
            po.append((cx + side * (hw + 2 + 9 * math.sqrt(f)), yv))
            pi_.append((cx + side * (hw - 2 + 5 * math.sqrt(f)), yv))
        m = poly_mask(L, po + pi_[::-1])
        f = (L.xx - (cx + side * (hw - 2))) * side
        L.put(m, WATER[2], alpha)
        L.put(m & (f < 1.6 + 2.0 * np.sqrt(np.clip((L.yy - top_y) / max(rim_y - top_y, 1), 0, 1))), WATER[1], alpha)
        outer = m & ~np.roll(m, -side, axis=1)
        L.put(outer, WATER[3], alpha)
        s_ = (L.yy - top_y) / max(rim_y - top_y, 1) * 1.7 - phase
        fr = s_ - np.floor(s_)
        L.put(m & (fr < 0.22) & (f >= 1.6) & ~outer, WATER[3], alpha)
        L.put(ellipse(L, cx + side * (hw + 6.0), rim_y - 1.0, 4.2, 1.8), WATER[3], alpha)
    L.put((np.abs(L.xx - cx) < hw - 1) & (L.yy >= top_y - 1) & (L.yy < top_y + 1), WATER[2], alpha)
    hh = 10 + 1.5 * math.sin(phase * 2 * math.pi)                 # 碗中间冒起的一股水，顶上散开一圈水花
    jm = ellipse(L, cx, top_y - hh / 2.0, 2.6, hh / 2.0 + 0.5)
    L.put(jm, WATER[3], alpha)
    L.put(jm & (L.xx > cx + 0.8), WATER[2], alpha)
    cr = ellipse(L, cx, top_y - hh, 4.2, 1.8)
    L.put(cr, WATER[3], alpha)
    L.put(cr & (L.xx > cx + 1.5), WATER[2], alpha)


def bench(L: Layer, x, base, w=30):
    """长椅（侧面）：麦黄木条座面 + 靠背，两条白石腿"""
    seat = base - 12
    for lx in (x + 3, x + w - 6):
        L.rect(lx, seat + 2, lx + 3, base, WALL[3])
        L.rect(lx, seat + 2, lx + 1, base, WALL[5])
    L.rect(x, seat, x + w, seat + 2, WHEAT[3])
    L.rect(x, seat, x + w, seat + 1, WHEAT[5])
    for lx in (x + 4, x + w - 5):
        L.rect(lx, seat - 8, lx + 1, seat, WHEAT[2])
    L.rect(x + 1, seat - 9, x + w - 1, seat - 6, WHEAT[3])
    L.rect(x + 1, seat - 9, x + w - 1, seat - 8, WHEAT[5])


# ======================================================================= 广场：湿石台
def terrace(L: Layer, x0, x1, top, walk, bot, seed):
    """广场是一块铺在云上的石台：上面一条薄薄的台面（top..walk，湿的，能看到砖缝和倒影），正面一截石壁（walk..bot），
    两头圆角收进云里。晨的脚踩在 walk 那一行。返回台面的 mask。"""
    rng = np.random.default_rng(seed)
    m = (L.yy >= top) & (L.yy < bot)
    rr = 4
    for (cx_, sgn) in ((x0 + rr, -1), (x1 - rr, 1)):
        m &= ~(((L.xx - cx_) * sgn > 0) & (((L.xx - cx_) ** 2 + (L.yy - (top + rr)) ** 2) > rr * rr) & (L.yy < top + rr))
    m &= (L.xx >= x0) & (L.xx < x1)
    surf = m & (L.yy < walk)
    face = m & (L.yy >= walk)
    # 台面：两排砖（前面一排高一点），砖缝暗一档
    L.put(surf, STONE[3])
    rows = [(top, top + 4), (top + 5, walk)]
    for (ya, yb) in rows:
        x = x0 - rng.uniform(0, 12)
        while x < x1:
            wd = rng.uniform(12, 22)
            k = rng.choice([2, 3, 3, 4])
            L.put(surf & (L.yy >= ya) & (L.yy < yb) & (L.xx >= x) & (L.xx < x + wd - 1), STONE[k])
            L.put(surf & (L.yy >= ya) & (L.yy < yb) & (L.xx >= x + wd - 1) & (L.xx < x + wd), STONE[1])
            x += wd
        L.put(surf & (L.yy >= yb) & (L.yy < yb + 1), STONE[1])
    # 台面最前沿一道亮（石台的棱，晨踩的那条线）
    L.put(m & (L.yy >= walk - 1) & (L.yy < walk), STONE[4])
    # 正面：一层大石块，左亮右暗
    L.put(face, STONE[2])
    L.put(face & (L.yy >= walk + 5), STONE[1])
    x = x0 + rng.uniform(4, 16)
    while x < x1 - 4:
        L.put(face & (L.xx >= x) & (L.xx < x + 1), STONE[0])
        x += rng.uniform(16, 30)
    L.put(face & ~np.roll(m, 1, axis=1), STONE[4])
    return surf


def reflect_onto(L: Layer, area, objs, seed, depth=10):
    """湿台面：objs = [(Layer, 底边 y), …] 按底边倒过来映在台面上。倒影按东西的颜色分类直接换色（不混出碎色）：
    灯 → 暖黄、帆 / 水 → 淡蓝、朝光的墙 → 玫瑰，越往下越稀（横向拉长的噪声切开，不是等距的条）。"""
    H, W = L.h, L.w
    cls = np.zeros((H, W), np.int8)
    wob = np.round(noise2(H, 1, 1, 3, seed)[:, 0] * 1.2).astype(int)
    nz = noise2(H, W, 12, 1.4, seed + 1)
    lamp = np.array([hexc(c) for c in LAMP]).astype(int)
    for (O, base) in objs:
        oa = O.a.astype(int)
        r, g, b, al = oa[..., 0], oa[..., 1], oa[..., 2], oa[..., 3]
        lum = r * 0.3 + g * 0.59 + b * 0.11
        oc = np.zeros((H, W), np.int8)
        oc[(al > 0) & (lum > 150)] = 3                                    # 亮的墙、石唇
        oc[(al > 0) & (b > r + 10) & (lum > 120)] = 2                     # 帆、水
        isl = np.zeros((H, W), bool)
        for c in lamp[1:]:
            isl |= (np.abs(oa[..., :3] - c).sum(-1) < 6)
        oc[(al > 0) & isl] = 1                                            # 灯
        for y in range(int(base), min(H, int(base) + depth)):
            sy = int(2 * base - y - 1)
            if sy < 0:
                continue
            f = (y - base) / depth
            keep = nz[y] > (-0.8 + 1.4 * f)
            row = np.roll(oc[sy], wob[y])
            put = (row > 0) & keep
            cls[y][put] = row[put]
    sel = area & (cls > 0)
    L.put(sel & (cls == 1), LAMP[1])
    L.put(sel & (cls == 2), SAIL[2])
    L.put(sel & (cls == 3), WALL[3])


# ======================================================================= 作者的云层（原图，只读）
AUTHOR = [("sky", 0.0, 0, 270, "n"), ("high", 0.02, 64, 38, "n"), ("streaks", 0.02, 93, 27, "a"), ("spires", 0.04, 43, 138, "n"),
          ("far", 0.08, 136, 134, "n"), ("midfar", 0.18, 146, 124, "n"), ("mid", 0.36, 126, 144, "n"),
          ("wash", 0.0, 141, 63, "a"), ("near", 0.6, 194, 76, "n"), ("main", 1.0, 218, 52, "n"), ("front", 1.4, 242, 28, "n")]
DRIFT = {"streaks": -1.5, "far": -0.8, "midfar": -1.6, "mid": -2.6, "near": -4.0}


def author_layers(camx, names, t=0.0):
    """按 scenes/cloud_test.tscn 的样子把作者的层叠出来（region 只取那几行；streaks、wash 是叠加混合）。返回 480×270 RGB 浮点。"""
    c = np.zeros((270, 480, 3), np.float32)
    for (n, sc, y, h, mode) in AUTHOR:
        if n not in names:
            continue
        a = np.asarray(Image.open(ROOT / "art" / "cloud" / (n + ".png")).convert("RGBA")).astype(np.float32)
        w = a.shape[1]
        xs = (np.arange(480) + int(round(camx * sc - DRIFT.get(n, 0.0) * t))) % w
        sub = np.zeros((270, 480, 4), np.float32)
        sub[y:y + h] = a[y:y + h][:, xs]
        al = sub[..., 3:4] / 255
        c = np.clip(c + sub[..., :3] * al, 0, 255) if mode == "a" else c * (1 - al) + sub[..., :3] * al
    return c


def over_rgb(c, L: Layer, dx=0):
    a = L.a.astype(np.float32)
    sub = a[:, dx:dx + 480] if L.w >= dx + 480 else a
    al = sub[..., 3:4] / 255
    return c * (1 - al) + sub[..., :3] * al


def deck_cloud(w, x0, x1, top, seed, lift=0.13, r=(10, 18)):
    """一层云台（叠屋用）：x0..x1 一排扁的菜花云团，团顶在 top 附近，身体一直到图底，两头圆圆地收掉"""
    F = cloud_field(w)
    rng = np.random.default_rng(seed)
    F.new_group()
    x = x0
    while x < x1:
        rr = rng.uniform(*r)
        edge = min(x - x0, x1 - x) / 30.0
        dy = (1 - min(edge, 1)) * 6
        F.cauli(x + PAD, top + dy + rr * 0.5, rr, rng.uniform(0, 3), rng, sq=0.55, depth=2, kids=(2, 4), ks=(0.3, 0.5),
                rmin=2.5, spread=(-165, -15), ref=top, unit=9)
        x += rr * rng.uniform(1.0, 1.4)
    pal = CA.cloud_pal(0.12 + lift, 0.46 + lift, 7, C_lo=0.045, C_hi=0.08, h_lo=288, h_hi=350)
    return render_field(F, w, pal, body=5, rim=(1.5, 3.2), crease=2.0, run_bands=(5, 12, 22, 34))


def chen_ref(x, foot=228):
    """草图里放一帧晨（只为看比例和看不看得清；正式图不画晨）"""
    im = np.asarray(Image.open(ROOT / "art/characters/chen/chen.png").convert("RGBA"))[:, 0:40]
    L = Layer(40, im.shape[0])
    L.a[:] = im
    return L, x - 20, foot - im.shape[0] + 1




def lip_cloud(w, x0, x1, top, seed, r=(5, 9)):
    """石台 / 木台下沿压着的一排小云团（台子陷在云里，不是摆在云上的一块板）：颜色和能走的云一条色阶"""
    F = cloud_field(w)
    rng = np.random.default_rng(seed)
    F.new_group()
    x = x0 + rng.uniform(0, 4)
    while x < x1:
        rr = rng.uniform(*r)
        F.cauli(x + PAD, top + rr * 0.45 + rng.uniform(-0.6, 1.2), rr, rng.uniform(0, 3), rng, sq=0.55, depth=1,
                kids=(1, 3), ks=(0.3, 0.5), rmin=2.5, spread=(-160, -20), ref=top, unit=8)
        x += rr * rng.uniform(1.1, 1.6)
    pal = CA.cloud_pal(0.10, 0.42, 7, C_lo=0.045, C_hi=0.08, h_lo=286, h_hi=348)
    return render_field(F, w, pal, body=4, rim=(1.5, 3.0), crease=2.0, run_bands=(4, 9, 16))


# ======================================================================= 小镇的布局（房间坐标，x 从左到右）
W, H = 1760, 270
GROUND = 228                      # 晨脚底那一行（整个小镇一样平）
ORIGIN = (0, 1620)                # 芦苇地 (0,1080)、城市 (0,1350) 再往下一屏
FAR_SC = 0.72                     # 远处那排塔的视差
FAR_W = int(math.ceil(480 + (W - 480) * FAR_SC)) + 4
LANDING = (26, 424)               # 木停机台
PLAZA = (704, 1282)               # 湿石台广场
FOUNTAIN = 982
WHEEL = (896, 200)                # 水车轴心
SHIP_X = 92                       # 飞船图左上角 x
BENCHES = (748, 1166)
BED_X = 1318                      # 花圃（物件）左上角 x
TAP_X = 1394
LODGE = 1546                      # 晨住的那座塔（town_room）底边中点
LW, LH = 144, 226                 # 住处的图
L_DOOR = 34                       # 住处的门（图里的 x）
CAPB = lch_ramp(0.34, 0.84, 0.05, 0.06, 282, 248, 6)        # 刷了淡蓝漆的木尖顶
ROOMC = lch_ramp(0.30, 0.86, 0.035, 0.06, 8, 64, 7)         # 屋里被灯照着的灰泥墙：暗玫瑰 → 暖奶油

# 后面那排塔（在晨后面，跟地面一起动）：(x, 塔脚 y, 宽, 高, 尖顶高, 顶, 附加)
#   附加：rotor = 风车半径；jib = 尖顶上伸出的帆杆长；box = 花箱；balc = 阳台；taper；door；wins = 窗
BACK_TOWERS = [
    (20, 212, 18, 80, 32, "w", {"rotor": 11, "door": (9, 20, True)}),
    (60, 208, 14, 114, 44, "b", {"jib": 14}),
    (196, 210, 12, 92, 36, "w", {}),
    (244, 213, 16, 64, 28, "b", {}),
    (380, 212, 16, 76, 30, "w", {"rotor": 10, "door": (9, 20, False)}),
    (414, 208, 20, 100, 38, "b", {"balc": 40, "box": True}),
    (468, 210, 14, 126, 46, "w", {"jib": 15}),
    (520, 214, 20, 66, 28, "b", {"rotor": 12, "door": (10, 21, True)}),
    (592, 210, 16, 94, 36, "w", {"box": True}),
    (644, 214, 24, 60, 26, "w", {"balc": 22, "door": (10, 22, False)}),
    (736, 208, 16, 106, 40, "w", {"jib": 14, "box": True}),
    (790, 212, 14, 80, 32, "b", {"door": (8, 19, True)}),
    (1162, 210, 16, 96, 38, "w", {"box": True}),
    (1206, 214, 22, 64, 30, "b", {"rotor": 12, "door": (10, 21, True)}),
    (1252, 208, 14, 118, 44, "w", {"jib": 15}),
    (1310, 212, 18, 74, 30, "w", {"balc": 30}),
    (1410, 210, 14, 102, 40, "b", {"jib": 13, "box": True}),
    (1668, 212, 18, 86, 34, "w", {"rotor": 11, "door": (9, 20, True)}),
    (1706, 208, 14, 122, 44, "b", {"jib": 14}),
    (1748, 214, 20, 68, 28, "w", {"box": True}),
]
MILL = (1084, 210, 30, 108, 36)   # 广场后面的大风车塔：(x, 塔脚, 宽, 高, 尖顶高)，转子半径 40
ROPES = [(0, 1, 9, 26, 6), (5, 6, 6, 28, 8), (10, 11, 8, 24, 6), (12, 14, 8, 30, 9), (17, 18, 8, 28, 7)]   # 两座塔之间的绳帆：(左塔, 右塔, 左边离尖多远, 右边离尖多远, 下垂)


def default_windows(w, h, rng, lit_p=0.6):
    """塔身上一列窗：从上往下每 26~30 行一扇，最下面那扇离塔脚至少 34 行（门的位置）"""
    out = []
    dy = 12
    ww = 6 if w >= 16 else 5
    while dy < h - 34:
        out.append((dy, ww, 9 if ww == 6 else 8, bool(rng.random() < lit_p), 0))
        dy += int(rng.integers(26, 31))
    return out


def deck(L: Layer, x0, x1, top, walk, bot, seed):
    """木停机台：上面一条台面（top..walk，一块块木板，板缝暗一档），正面一根横梁，每隔一段一根木桩插进云里。
    晨踩 walk 那一行。"""
    rng = np.random.default_rng(seed)
    m = (L.xx >= x0) & (L.xx < x1) & (L.yy >= top) & (L.yy < walk + 6)
    m &= ~(((L.xx < x0 + 1) | (L.xx >= x1 - 1)) & (L.yy < top + 1))       # 两头的角削掉一格
    surf = m & (L.yy < walk)
    L.put(surf, WHEAT[3])
    x = x0 - rng.uniform(0, 8)
    while x < x1:
        wd = rng.uniform(16, 30)
        k = int(rng.choice([2, 2, 3]))
        L.put(surf & (L.xx >= x) & (L.xx < x + wd - 1), WHEAT[k])
        L.put(surf & (L.xx >= x + wd - 1) & (L.xx < x + wd), WHEAT[1])
        x += wd
    L.put(surf & (L.yy < top + 1), WHEAT[3])                                # 后沿
    L.put(m & (L.yy >= walk - 1) & (L.yy < walk), WHEAT[4])               # 前沿一道亮（踩的那条线）
    beam = m & (L.yy >= walk)
    L.put(beam, WHEAT[1])
    L.put(beam & (L.yy < walk + 1), WHEAT[2])
    L.put(beam & ~np.roll(m, 1, axis=1), WHEAT[3])
    x = x0 + 8
    while x < x1 - 6:                                                     # 木桩
        L.rect(x, walk + 6, x + 4, bot, WHEAT[1])
        L.rect(x, walk + 6, x + 1, bot, WHEAT[2])
        L.rect(x + 3, walk + 6, x + 4, bot, WHEAT[0])
        x += rng.uniform(44, 60)
    return surf


def bollard(L: Layer, x, base):
    """系船的矮木桩：顶上一个圆帽"""
    L.rect(x, base - 7, x + 4, base, WHEAT[2])
    L.rect(x, base - 7, x + 1, base, WHEAT[4])
    L.rect(x + 3, base - 7, x + 4, base, WHEAT[1])
    L.rect(x - 1, base - 9, x + 5, base - 7, WHEAT[3])
    L.rect(x - 1, base - 9, x + 5, base - 8, WHEAT[5])


def lamp_post(L: Layer, x, base, h):
    """路灯：细木杆，顶上一盏小灯笼（暖光，上亮下暗，不是实心块），灯笼上一个小尖帽"""
    L.rect(x, base - h, x + 2, base, WHEAT[2])
    L.rect(x, base - h, x + 1, base, WHEAT[4])
    L.rect(x - 1, base - 3, x + 3, base, WHEAT[1])
    L.rect(x - 1, base - 3, x, base, WHEAT[3])
    ly = base - h - 8
    L.rect(x - 2, ly, x + 4, ly + 8, WHEAT[1])
    L.rect(x - 1, ly + 1, x + 3, ly + 7, LAMP[2])
    L.rect(x - 1, ly + 1, x + 3, ly + 3, LAMP[3])
    L.rect(x - 1, ly + 6, x + 3, ly + 7, LAMP[1])
    for i, (a, b) in enumerate(((x - 2, x + 4), (x - 1, x + 3), (x, x + 2))):
        L.rect(a, ly - 1 - i, b, ly - i, WHEAT[3] if i < 2 else WHEAT[4])


def stepping_stones(L: Layer, x0, x1, y, seed):
    """路上嵌在云里的扁石头：一块块椭圆，上沿亮一行"""
    rng = np.random.default_rng(seed)
    x = x0
    while x < x1:
        rx = rng.uniform(6, 10)
        m = ellipse(L, x + rx, y + 0.5, rx, 2.4)
        L.put(m, STONE[2])
        L.put(m & (L.yy < y), STONE[4])
        L.put(m & (L.yy >= y + 1.5), STONE[1])
        x += 2 * rx + rng.uniform(5, 11)


def basket(L: Layer, x, base):
    """倒在地上的空篮子（侧躺，口朝右）：一头小一头大的圆筒，编纹是一行行错开的短块，口是一圈亮的藤边、里面是暗的；
    提手掉在旁边地上"""
    bw = 22
    t = np.clip((L.xx - x) / bw, 0, 1)
    half = 4.4 + 2.6 * t                                    # 篮底小、篮口大
    cy = base - half
    m = (L.xx >= x + 2) & (L.xx < x + bw) & (np.abs(L.yy - cy) < half)
    m |= ellipse(L, x + 3, base - 4.6, 2.6, 4.4)            # 圆圆的篮底
    v = np.clip((L.yy - (cy - half)) / (2 * half), 0, 0.999)
    row = (v * 5).astype(int)
    shade = np.array([4, 3, 3, 2, 1])[row]
    for k in range(1, 5):
        L.put(m & (shade == k), WHEAT[k])
    seam = m & (np.mod(L.xx - x + 2.5 * row, 5) < 1) & (L.xx > x + 3)
    L.put(seam, WHEAT[1])
    L.put(seam & (row >= 3), WHEAT[0])
    L.put(m & ~np.roll(m, 1, axis=1), WHEAT[4])
    mh = 7.0
    mo = ellipse(L, x + bw, base - mh, 3.4, mh)
    L.put(mo, WHEAT[4])
    L.put(mo & (L.xx > x + bw + 1.5), WHEAT[3])
    L.put(mo & (L.yy < base - mh * 2 + 1.5), WHEAT[5])
    inner = ellipse(L, x + bw + 0.6, base - mh, 2.0, mh - 1.6)
    L.put(inner, SOIL[0])
    L.put(inner & (L.yy > base - 4), SOIL[1])
    for (px_, py_) in curve4([(x + bw + 6, base - 1), (x + bw + 7, base - 4), (x + bw + 10, base - 6), (x + bw + 14, base - 5),
                              (x + bw + 16, base - 2), (x + bw + 16, base - 1)]):
        L.px(px_, py_, WHEAT[3])
        L.px(px_, py_ + 1, WHEAT[1]) if py_ < base - 1 else None


def tap(L: Layer, x, base):
    """取水的龙头：白石小柱（顶是圆的），左边伸出一个麦黄的铜龙头，龙头下挂着一个木桶"""
    m = (L.xx >= x) & (L.xx < x + 6) & (L.yy >= base - 30) & (L.yy < base)
    m &= ~((L.yy < base - 27) & (((L.xx - (x + 3)) ** 2 + (L.yy - (base - 27)) ** 2) > 9.5))
    L.put(m, WALL[3])
    L.put(m & (L.xx < x + 1.5), WALL_RIM)
    L.put(m & (L.xx >= x + 1.5) & (L.xx < x + 3), WALL[5])
    L.put(m & (L.xx >= x + 5), WALL[2])
    L.put(m & (L.yy >= base - 4), WALL[2])
    L.rect(x - 1, base - 4, x + 7, base, WALL[2])
    L.rect(x - 1, base - 4, x + 7, base - 3, WALL[4])
    # 龙头：一截横管 + 往下弯的出水口 + 顶上的小转把
    L.rect(x - 6, base - 22, x, base - 19, WHEAT[3])
    L.rect(x - 6, base - 22, x, base - 21, WHEAT[5])
    L.rect(x - 7, base - 22, x - 4, base - 15, WHEAT[3])
    L.rect(x - 7, base - 22, x - 6, base - 15, WHEAT[5])
    L.rect(x - 4, base - 19, x - 3, base - 15, WHEAT[1])
    L.rect(x - 3, base - 26, x - 2, base - 22, WHEAT[2])
    L.rect(x - 5, base - 27, x, base - 26, WHEAT[4])
    L.rect(x - 7, base - 15, x - 4, base - 14, WATER[3], WATER_A)
    # 木桶
    b = (L.xx >= x - 12) & (L.xx < x - 1) & (L.yy >= base - 10) & (L.yy < base)
    b &= ~((L.yy >= base - 1) & ((L.xx < x - 11) | (L.xx >= x - 2)))
    L.put(b, WHEAT[2])
    L.put(b & (L.xx < x - 10), WHEAT[4])
    L.put(b & (L.xx >= x - 3), WHEAT[1])
    L.put(b & ((np.abs(L.yy - (base - 3.5)) < 0.6) | (np.abs(L.yy - (base - 7.5)) < 0.6)), WHEAT[0])
    L.rect(x - 12, base - 10, x - 1, base - 9, WHEAT[4])
    L.rect(x - 11, base - 9, x - 2, base - 8, WATER[1])
    for (px_, py_) in curve4([(x - 12, base - 10), (x - 11, base - 13), (x - 9, base - 15), (x - 5, base - 15), (x - 3, base - 13),
                              (x - 2, base - 10)]):
        L.px(px_, py_, WHEAT[1])


def flower_bed(phase):
    """花圃（物件 town_bed）：木箱子 + 黑土，两头开着粉的、黄的花，中间空着一块；planted = 中间多一个湿土包 + 一棵小芽"""
    w, h = 60, 26
    L = Layer(w, h)
    by = h - 9
    L.rect(1, by, w - 1, h, WHEAT[2])
    L.rect(1, by, w - 1, by + 1, WHEAT[4])
    L.rect(1, h - 3, w - 1, h, WHEAT[1])
    L.rect(1, by, 2, h, WHEAT[4])
    L.rect(w - 2, by, w - 1, h, WHEAT[1])
    for xx in (20, 40):
        L.rect(xx, by + 1, xx + 1, h - 3, WHEAT[1])
    L.rect(2, by - 2, w - 2, by, SOIL[1])
    L.rect(4, by - 3, w - 4, by - 2, SOIL[2])

    def flower(x, top, col):
        """一枝花：茎、一片叶子、一朵小花（上面尖一格，亮的那一角是一整块 L 形，不留单独的点）"""
        L.rect(x, top + 3, x + 1, by - 2, LEAF[1])
        lx = x + 1 if (x + top) % 2 else x - 2
        L.rect(lx, top + 6, lx + 2, top + 7, LEAF[2])
        L.rect(x - 1, top + 1, x + 2, top + 3, FLOWER[col])
        L.rect(x, top, x + 1, top + 1, FLOWER[col + 1])
        L.rect(x - 1, top + 1, x + 1, top + 2, FLOWER[col + 1])

    for (fx, ft, c) in ((5, 4, 0), (9, 1, 2), (13, 5, 0), (17, 2, 0), (43, 3, 2), (47, 0, 0), (51, 5, 0), (55, 2, 2)):
        flower(fx, ft, c)
    if phase == 1:
        mm = ellipse(L, 30, by - 2, 7, 2.2)
        L.put(mm, SOIL[0])
        L.put(mm & (L.yy < by - 3), SOIL[1])
        L.rect(30, by - 7, 31, by - 3, LEAF[2])
        L.rect(27, by - 8, 30, by - 7, LEAF[3])
        L.rect(31, by - 9, 34, by - 8, LEAF[3])
        L.rect(28, by - 9, 30, by - 8, LEAF[2])
    return L


# ======================================================================= 动画（逐帧图，房间脚本挂到层上播：100ms 一帧）
ANIMS = []          # [{"layer", "img", "x", "y", "w", "frames", "off", "_frames": [Layer…]}]


def anim(name, layer, box, frames, draw, off=0):
    """box = (x0, y0, x1, y1) 层图里的坐标；draw(L, k) 画第 k 帧。帧横排成一张图。"""
    x0, y0, x1, y1 = box
    fr = []
    for k in range(frames):
        L = piece(x0, y0, x1, y1)
        draw(L, k)
        despeckle(L)
        fr.append(L)
    ANIMS.append({"layer": layer, "img": f"res://art/cloud_town/anim/{name}.png", "x": fr[0].ox, "y": fr[0].oy,
                  "w": fr[0].w, "frames": frames, "off": off, "_frames": fr, "_name": name})


HAZE = np.array(CA.cloud_pal(0.15, 0.49, 7, C_lo=0.045, C_hi=0.08, h_lo=288, h_hi=350)[3], np.float32)   # 远处那层云的中间色


def hazed(L: Layer, k=0.3):
    """远处的东西往云的颜色里退一点（每个颜色一对一地换，不混出新的碎色）"""
    op = L.a[..., 3] > 0
    L.a[op, :3] = np.round(L.a[op, :3].astype(np.float32) * (1 - k) + HAZE * k).astype(np.uint8)
    return L


def rotor_into(L: Layer, cx, cy, r, ang, arms=8, haze=0.0):
    R = rotor(2 * int(r) + 2, ang, arms=arms, r=r)
    if haze:
        hazed(R, haze)
    L.over(R, int(round(cx - r - 1)) - L.ox, int(round(cy - r - 1)) - L.oy)


def pennant(L: Layer, x, y, length, wid, k, n):
    """长条旗（风向袋）：从杆上往右飘，越往外摆得越大，一个周期 n 帧"""
    ph = 2 * math.pi * k / n
    top, bot = [], []
    for i in range(13):
        s = i / 12
        wave = 2.2 * s * math.sin(2 * math.pi * s * 0.9 - ph)
        half = wid * (1 - s) * 0.5 + 0.6
        cx_, cy_ = x + 1 + length * s, y + wid * 0.5 + wave + 1.2 * s
        top.append((cx_, cy_ - half))
        bot.append((cx_, cy_ + half))
    m = poly_mask(L, top + bot[::-1]) & (L.xx > x + 1)
    v = L.yy - np.interp(L.xx, [p[0] for p in top], [p[1] for p in top])
    L.put(m, SAIL[3], SAIL_A)
    L.put(m & (v < 1.4), SAIL[4], SAIL_A)
    L.put(m & (v > wid * 0.55), SAIL[2], SAIL_A)


def foot_tufts(w, feet, seed, lift=0.1):
    """塔脚两边各一两团小云，压住塔脚（房子坐在云里，不是立在云上的一根柱子）。feet = [(x, 塔脚 y, 塔宽), …]"""
    F = cloud_field(w)
    rng = np.random.default_rng(seed)
    for (x, base, tw) in feet:
        for side in (-1, 1):
            F.new_group()
            r = rng.uniform(3.2, 5.0)
            F.cauli(x + side * (tw / 2.0 + rng.uniform(0.5, 2.5)) + PAD, base + r * 0.2, r, 30, rng, sq=0.6, depth=1, kids=(1, 2),
                    ks=(0.35, 0.55), rmin=2.0, spread=(-160, -20), ref=base - r * 0.6, unit=5)
    pal = CA.cloud_pal(0.12 + lift, 0.46 + lift, 7, C_lo=0.045, C_hi=0.08, h_lo=288, h_hi=350)
    L = render_field(F, w, pal, body=4, rim=(1.5, 3.2), crease=2.0, run_bands=(4, 9))
    L.a[np.arange(H)[:, None].repeat(w, 1) > max(b for _, b, _ in feet) + 8] = 0
    return L


# ======================================================================= 远处那排塔（视差 0.72）
def build_far():
    rng = np.random.default_rng(77)
    towers = []
    x = 8.0
    while x < FAR_W - 4:
        w = int(rng.choice([8, 9, 10, 10, 12]))
        h = int(rng.uniform(32, 70))
        base = int(rng.uniform(202, 207))
        towers.append((x, base, w, h, int(h * rng.uniform(0.36, 0.48)), "b" if rng.random() < 0.35 else "w",
                       rng.random() < 0.38))
        x += rng.uniform(40, 82)
    heaps = [(tx, b + 6, tw * 2.4 + 12, max(4, 10 + rng.uniform(-2, 3))) for (tx, b, tw, *_r) in towers]
    F = Layer(FAR_W, H)
    F.over(mound_cloud(FAR_W, heaps, 3, deck=207, lift=0.03))
    feet = []
    for (tx, base, w, h, cap_h, cap, rot) in towers:
        P = piece(tx - w - 4, base - h - cap_h - 3, tx + w + 4, base + 1)
        wins = []
        dy = 8
        while dy < h - 12:
            wins.append((dy, 3, 4, bool(rng.random() < 0.55), 0))
            dy += int(rng.integers(14, 19))
        T = tower_house(P, tx, base, w, h, cap_h, wins, taper=1, cap=CAPB if cap == "b" else WHEAT, dim=0)
        F.over(hazed(P, 0.4))
        feet.append((tx, base, w))
        if rot:
            r = 6.0
            hx, hy = tx, T["top"] + 4
            anim(f"far_rotor_{len(ANIMS)}", "town_far", (hx - r - 1, hy - r - 1, hx + r + 2, hy + r + 2), 8,
                 lambda L, k, hx=hx, hy=hy: rotor_into(L, hx, hy, r, 0.3 + (math.pi / 3) * k / 8, arms=6, haze=0.4),
                 off=int(rng.integers(0, 8)))
    F.over(foot_tufts(FAR_W, feet, 4, lift=0.03))
    despeckle(F)
    return F


# ======================================================================= 后面那排塔（视差 1，在晨后面）
def build_back():
    rng = np.random.default_rng(31)
    B = Layer(W, H)
    heaps = [(tx, 217, tw * 2.6 + 14, max(4, 217 - b + 7)) for (tx, b, tw, *_r) in BACK_TOWERS]
    heaps.append((MILL[0], 217, 90, 16))
    B.over(mound_cloud(W, heaps, 1, deck=212))
    info = []
    feet = []
    for i, (tx, base, w, h, cap_h, cap, ex) in enumerate(BACK_TOWERS):
        P = piece(tx - w - 8, base - h - cap_h - 4, tx + w + 8, base + 1)
        wins = ex.get("wins") or default_windows(w, h, rng)
        T = tower_house(P, tx, base, w, h, cap_h, wins, door=ex.get("door"), taper=ex.get("taper", 2),
                        cap=CAPB if cap == "b" else WHEAT, box=ex.get("box", False), balc=ex.get("balc"))
        B.over(P)
        info.append(T)
        feet.append((tx, base, w))
        if "jib" in ex:
            n = ex["jib"]
            P = piece(T["tip"][0] - 3, T["tip"][1] - n - 4, T["tip"][0] + 4, T["tip"][1] + 2)
            mx, my = finial_mast(P, int(T["tip"][0]), int(T["tip"][1]), n)
            B.over(P)
            reach, bulge = n * 0.72, n * 0.17
            ph0 = rng.uniform(0, 2 * math.pi)
            anim(f"jib_{i}", "town_back", (mx - 1, my - 2, mx + reach + bulge + 6, my + n + 2), 20,
                 lambda L, k, mx=mx, my=my, n=n, reach=reach, bulge=bulge, ph0=ph0:
                 jib(L, mx, my + 1, my + n - 2, reach + 0.8 * math.sin(2 * math.pi * k / 20 + ph0 + 0.7),
                     bulge * (1 + 0.4 * math.sin(2 * math.pi * k / 20 + ph0))))
        if "rotor" in ex:
            r = float(ex["rotor"])
            hx, hy = tx, T["top"] + 7
            a0 = rng.uniform(0, 1)
            anim(f"rotor_{i}", "town_back", (hx - r - 1, hy - r - 1, hx + r + 2, hy + r + 2), 8,
                 lambda L, k, hx=hx, hy=hy, r=r, a0=a0: rotor_into(L, hx, hy, r, a0 + (math.pi / 4) * k / 8))
    # 大风车塔：塔脚有门，腰上一扇亮窗，转子 84 像素
    mx_, mb, mw, mh, mc = MILL
    P = piece(mx_ - mw - 8, mb - mh - mc - 4, mx_ + mw + 8, mb + 1)
    M = tower_house(P, mx_, mb, mw, mh, mc, [(30, 7, 10, True, 0), (58, 6, 9, False, -3)], door=(11, 24, True), taper=4,
                    box=True)
    B.over(P)
    feet.append((mx_, mb, mw))
    hub = (mx_, M["top"] + 12)
    anim("mill_rotor", "town_back", (hub[0] - 42, hub[1] - 42, hub[0] + 43, hub[1] + 43), 16,
         lambda L, k: rotor_into(L, hub[0], hub[1], 40, 0.2 + (math.pi / 4) * k / 16))
    # 绳帆
    for (i, j, da, db, sag) in ROPES:
        A, Bt = info[i], info[j]
        ya, yb = A["tip"][1] + da, Bt["tip"][1] + db
        xa = A["cx"] + float(cap_half(A, ya)) - 0.5
        xb = Bt["cx"] - float(cap_half(Bt, yb)) + 0.5
        n = max(2, int((xb - xa) / 15))
        panels = [((q + 0.25) / n, int(rng.integers(7, 10)), int(rng.integers(10, 15))) for q in range(n)]
        ph0 = rng.uniform(0, 2 * math.pi)
        y0 = min(ya, yb) - 2
        y1 = max(ya, yb) + sag + 16
        anim(f"rope_{i}_{j}", "town_back", (xa - 2, y0, xb + 9, y1), 20,
             lambda L, k, xa=xa, ya=ya, xb=xb, yb=yb, sag=sag, panels=panels, ph0=ph0, n=n:
             rope_sails(L, xa, ya, xb, yb, sag, panels,
                        [3.0 + 1.6 * math.sin(2 * math.pi * k / 20 + ph0 + q * 0.9) for q in range(n)]))
    B.over(foot_tufts(W, feet, 2))
    despeckle(B)
    return B, info, M


# ======================================================================= 地面（视差 1：停机台、路、广场、花圃前的云）
SHIP_Y = None


def ship_img():
    im = np.asarray(Image.open(ROOT / "art/level1/ship_lift.png").convert("RGBA"))[:, 17 * 204:18 * 204][0:120]
    im = im[23:77, 32:174].copy()
    return im


def build_main(back):
    global SHIP_Y
    M = Layer(W, H)

    def terrain(x):
        return 226 + 0.9 * math.sin(x / 41.0) + 0.5 * math.sin(x / 13.0 + 1.0)

    M.over(ground_cloud(W, terrain, 5, flats=[LANDING, PLAZA, (LODGE - 90, LODGE + 90), (BED_X - 10, TAP_X + 14)]))
    # ---- 停机台：木台 + 木桩，飞船架在两块垫木上，两根缆绳系在矮桩上
    deck(M, LANDING[0], LANDING[1], 221, GROUND, 248, 3)
    M.over(lip_cloud(W, LANDING[0] - 6, LANDING[1] + 6, 240, 11))
    ship = ship_img()
    sh, sw = ship.shape[:2]
    SHIP_Y = 216 - (sh - 1)
    low = np.array([np.max(np.nonzero(ship[:, c, 3])[0]) if ship[:, c, 3].any() else -1 for c in range(sw)])
    for fx in (0.3, 0.72):
        c = int(sw * fx)
        top = SHIP_Y + low[c - 5:c + 5].min() + 1
        m = poly_mask(M, [(SHIP_X + c - 5, top), (SHIP_X + c + 5, top), (SHIP_X + c + 7, 222), (SHIP_X + c - 7, 222)])
        M.put(m, WHEAT[2])
        M.put(m & (M.xx < SHIP_X + c - 3), WHEAT[4])
        M.put(m & (M.xx >= SHIP_X + c + 4), WHEAT[1])
        M.put(m & (M.yy < top + 1), WHEAT[3])
    for (sx, sy, bx) in ((20, 46, -16), (126, 48, sw + 12)):
        bollard(M, SHIP_X + bx, 224)
        ax, ay = SHIP_X + sx, SHIP_Y + sy
        tx_, ty_ = SHIP_X + bx + 2, 216
        pts = [(ax + (tx_ - ax) * f, ay + (ty_ - ay) * f + 2.0 * math.sin(math.pi * f)) for f in np.linspace(0, 1, 14)]
        stroke(M, curve4(pts), WHEAT[1])
    # 风向旗杆 + 停机台两头的灯
    mast(M, 338, 132, 224, w=2)
    anim("windsock", "town_main", (339, 128, 372, 146), 12, lambda L, k: pennant(L, 339, 133, 28, 7, k, 12))
    lamp_post(M, LANDING[0] + 6, 222, 22)
    lamp_post(M, LANDING[1] - 10, 222, 22)
    # ---- 路：嵌在云里的扁石头、路灯、倒了的篮子
    stepping_stones(M, LANDING[1] + 6, PLAZA[0] - 6, 226, 13)
    lamp_post(M, 556, 228, 30)
    basket(M, 586, 228)
    # ---- 广场：湿石台、喷泉、水车、长轴、长椅、路灯
    surf = terrace(M, PLAZA[0], PLAZA[1], 219, GROUND, 238, 9)
    M.over(lip_cloud(W, PLAZA[0] - 6, PLAZA[1] + 6, 236, 12))
    G = Layer(W, H)
    ax0, ax1 = WHEEL[0], back[2]["cx"] - back[2]["w"] / 2.0 + 3
    G.rect(ax0, WHEEL[1] - 1, ax1, WHEEL[1] + 1, WHEAT[2])
    G.rect(ax0, WHEEL[1] - 1, ax1, WHEEL[1], WHEAT[4])
    sp = 1046                                                           # 长轴中间一个木架子撑着（不悬空）
    G.put(poly_mask(G, [(sp - 1, WHEEL[1] + 1), (sp + 2, WHEEL[1] + 1), (sp + 6, 221), (sp + 3, 221)]), WHEAT[1])
    G.put(poly_mask(G, [(sp - 1, WHEEL[1] + 1), (sp + 2, WHEEL[1] + 1), (sp - 3, 221), (sp - 6, 221)]), WHEAT[2])
    G.rect(sp - 3, WHEEL[1] - 2, sp + 4, WHEEL[1] + 2, WHEAT[3])
    G.rect(sp - 3, WHEEL[1] - 2, sp + 4, WHEEL[1] - 1, WHEAT[5])
    top_y, rim_y = fountain(G, FOUNTAIN, 226, bw=110, bh=14, col_h=26, bowl_w=44)
    wx, wy = WHEEL[0] + 8, WHEEL[1] - 24
    bx = FOUNTAIN - 18
    trough = poly_mask(G, [(wx, wy), (bx, top_y - 1), (bx, top_y + 3), (wx, wy + 4)])
    G.put(trough, WHEAT[3])
    G.put(trough & (G.yy > wy + (G.xx - wx) * ((top_y - 1 - wy) / max(bx - wx, 1)) + 1.6), WHEAT[1])
    G.put(poly_mask(G, [(wx + 1, wy - 1), (bx + 1, top_y - 2), (bx + 1, top_y - 0.5), (wx + 1, wy + 0.5)]), WATER[2], WATER_A)
    # 木槽在水车那头有一根支柱落到台面上
    G.put(poly_mask(G, [(wx + 10, wy + 5), (wx + 13, wy + 5), (wx + 15, 221), (wx + 12, 221)]), WHEAT[2])
    G.put(poly_mask(G, [(wx + 10, wy + 5), (wx + 11, wy + 5), (wx + 13, 221), (wx + 12, 221)]), WHEAT[4])
    M.over(G)
    anim("fountain_water", "town_main", (FOUNTAIN - 40, top_y - 16, FOUNTAIN + 41, rim_y + 2), 8,
         lambda L, k: water_curtain(L, FOUNTAIN, top_y, rim_y, 44, phase=k / 8.0))
    anim("waterwheel", "town_main", (WHEEL[0] - 24, WHEEL[1] - 24, WHEEL[0] + 24, WHEEL[1] + 24), 12,
         lambda L, k: L.over(waterwheel(48, 0.2 + (math.pi / 4) * k / 12), WHEEL[0] - 24 - L.ox, WHEEL[1] - 24 - L.oy))
    objs = [(G, 226)]
    for bx_ in BENCHES:
        Bn = Layer(W, H)
        bench(Bn, bx_, 227)
        M.over(Bn)
        objs.append((Bn, 227))
    for lx in (PLAZA[0] + 10, PLAZA[1] - 12):
        lamp_post(M, lx, 222, 34)
    # ---- 广场外：花圃（物件）旁边的龙头、住处门口的路灯
    tap(M, TAP_X, 228)
    lamp_post(M, LODGE - LW // 2 - 14, 228, 30)
    reflect_onto(M, surf, [(back[0], 219)] + objs, 21)
    despeckle(M)
    return M


# ======================================================================= 晨暂住的塔（town_room：剖面小屋，前墙进屋淡出）
#   下面一截宽一点的圆塔是住的那层（剖开看得到屋里），塔顶一圈淡蓝漆的裙檐，裙檐里再长出一截细塔 + 尖顶 + 一架小风车：
#   就是一座风车塔，和镇上别的塔一个样子（不是圆顶帐篷，也不是方盒子）。风车是房屋物件 townroom_rotor（100ms 一帧）。
L_CX = LW // 2
L_BODY = (22, 122)        # 下面那截的左右（塔脚）
L_TAPER = 3
L_ROOF = 136              # 下截的檐口
L_CEIL = (146, 151)       # 剖开的天花板（石板）
L_FLOOR = LH - 1          # 屋里晨踩的那一行（= 图底 = 小镇的地面）
L_WALL = 5                # 剖开的墙厚
L_DESK = (58, 88)
L_BED = (92, 118)
L_WIN = (63, 81, 160, 186)
L_ROTOR = (L_CX, 71, 13.0)


def skirt(L: Layer, cx, y_bot, rw_bot, y_top, rw_top, pal):
    """裙檐：从檐口往上收到细塔腰上的一圈内凹的斜顶（和尖顶一个画法，只是没收到尖）"""
    pts = []
    n = 14
    for i in range(n + 1):
        s_ = i / n
        pts.append((cx - (rw_top + (rw_bot - rw_top) * (1 - s_) ** 1.9), y_bot - (y_bot - y_top) * s_))
    for i in range(n, -1, -1):
        s_ = i / n
        pts.append((cx + (rw_top + (rw_bot - rw_top) * (1 - s_) ** 1.9) + 0.01, y_bot - (y_bot - y_top) * s_))
    pts.append((cx + rw_bot - 1, y_bot + 1.2))
    pts.append((cx - rw_bot + 1, y_bot + 1.2))
    m = poly_mask(L, pts)
    u = (L.xx - cx) / rw_bot
    idx = np.clip(4 - band(u, (-0.45, 0.05, 0.5)), 1, 5)
    for k in range(6):
        L.put(m & (idx == k), pal[k])
    L.put(m & ~np.roll(m, 1, axis=1), pal[5])
    L.put(m & (L.yy >= y_bot), pal[1])
    return m


def lodging():
    back = Layer(LW, LH)
    front = Layer(LW, LH)
    x0, x1 = L_BODY
    base = LH
    # ---- 外面：下截圆塔身（back、front 用同一套明暗，前墙淡回来时严丝合缝）
    t = np.clip((base - back.yy) / (base - L_ROOF), 0, 1)
    flare = 2.2 * np.clip(1 - (base - back.yy) / 7.0, 0, 1) ** 2
    half = (x1 - x0) / 2.0 - L_TAPER * t + flare
    body = (np.abs(back.xx - L_CX) < half) & (back.yy >= L_ROOF) & (back.yy < base)
    for Lr in (back, front):
        shade_cyl(Lr, body, L_CX, half, L_ROOF, base)
    front.a[front.yy < L_CEIL[0]] = 0
    # 上截细塔 + 尖顶（淡蓝漆，晨住的这座好认）+ 一扇亮窗；塔脚埋在裙檐里
    P = Layer(LW, LH)
    tower_house(P, L_CX, L_ROOF - 14, 34, 58, 50, [(14, 6, 9, True, 0), (36, 5, 8, False, 0)], taper=2, cap=CAPB)
    back.over(P)
    skirt(back, L_CX, L_ROOF + 1, (x1 - x0) / 2.0 - L_TAPER + 3, L_ROOF - 22, 18, CAPB)
    # ---- 屋里（back 的剖面那一块）
    ix0, ix1 = x0 + L_WALL, x1 - L_WALL
    inner = (back.xx >= ix0) & (back.xx < ix1) & (back.yy >= L_CEIL[1]) & (back.yy < base)
    cut_w = body & (back.yy >= L_CEIL[0]) & ~inner
    # 剖开的墙和天花板：白石的切面，朝里那一圈暗一档
    back.put(cut_w, WALL[5])
    back.put(cut_w & (back.yy < L_CEIL[1]), WALL[4])
    edge_in = cut_w & (np.roll(inner, 1, 1) | np.roll(inner, -1, 1) | np.roll(inner, -1, 0))
    back.put(edge_in, WALL[3])
    back.put(cut_w & (back.yy < L_CEIL[0] + 1), WALL[6])
    # 灰泥后墙：灯在桌上（右边），离灯越远越暗一档；墙脚一条踢脚板
    lamp = (L_DESK[1] - 5, 192)
    d = np.hypot((back.xx - lamp[0]) / 1.3, back.yy - lamp[1])
    k = 5 - band(d, (16, 34, 56, 80))
    back.put(inner, ROOMC[3])
    for q in range(7):
        back.put(inner & (k == q), ROOMC[max(q, 1)])
    back.put(inner & (back.yy < L_CEIL[1] + 2), ROOMC[1])
    for bx in (ix0 + 14, ix0 + 44, ix0 + 74):                       # 天花板下的木梁头
        back.rect(bx, L_CEIL[1], bx + 6, L_CEIL[1] + 3, WHEAT[2])
        back.rect(bx, L_CEIL[1], bx + 6, L_CEIL[1] + 1, WHEAT[3])
    back.rect(ix0, base - 9, ix1, base - 7, WHEAT[1])
    # 地板：一条看得到上面的木板（板缝暗一档）
    fl = inner & (back.yy >= base - 7)
    back.put(fl, WHEAT[3])
    back.put(fl & (back.yy >= base - 2), WHEAT[2])
    for sx in (ix0 + 11, ix0 + 37, ix0 + 60, ix0 + 88):
        back.put(fl & (np.abs(back.xx - sx - 0.5) < 0.6), WHEAT[1])
    back.put(fl & (back.yy < base - 6), WHEAT[4])
    # 门口的地垫（门在前墙上，前墙淡掉以后看得到门口铺的垫子）
    back.rect(L_DOOR - 6, base - 3, L_DOOR + 8, base - 1, FLOWER[0])
    back.rect(L_DOOR - 5, base - 3, L_DOOR + 7, base - 2, FLOWER[1])
    # 窗：后墙上一扇拱窗，玻璃挖空（view.png 透出外面的天和云），十字窗棂，窗台上一小盆花
    wx0, wx1, wy0, wy1 = L_WIN
    r = (wx1 - wx0) / 2.0
    wm = (back.xx >= wx0) & (back.xx < wx1) & (back.yy >= wy0 + r) & (back.yy < wy1)
    wm |= ellipse(back, wx0 + r, wy0 + r, r, r) & (back.yy < wy0 + r + 0.5)
    frame = (np.roll(wm, 1, 0) | np.roll(wm, -1, 0) | np.roll(wm, 1, 1) | np.roll(wm, -1, 1)) & ~wm
    frame |= (np.roll(frame, 1, 1) & ~wm)
    back.put(frame, WHEAT[2])
    back.put(frame & ~np.roll(frame | wm, 1, 1), WHEAT[4])
    mull = wm & ((np.abs(back.xx - (wx0 + r)) < 1.0) | (np.abs(back.yy - (wy0 + r + 4)) < 1.0))
    back.put(mull, WHEAT[3])
    glass = wm & ~mull
    back.a[glass] = 0
    back.rect(wx0 - 3, wy1, wx1 + 3, wy1 + 2, WHEAT[4])
    back.rect(wx0 - 3, wy1 + 1, wx1 + 3, wy1 + 2, WHEAT[2])
    back.rect(wx1 - 6, wy1 - 4, wx1 - 1, wy1, SOIL[2])
    back.rect(wx1 - 6, wy1 - 4, wx1 - 1, wy1 - 3, WHEAT[3])
    back.rect(wx1 - 5, wy1 - 7, wx1 - 2, wy1 - 4, LEAF[2])
    back.rect(wx1 - 6, wy1 - 9, wx1 - 4, wy1 - 7, FLOWER[0])
    back.rect(wx1 - 3, wy1 - 8, wx1 - 1, wy1 - 6, FLOWER[1])
    view = Layer(LW, LH)
    view.put(glass, "#ffffff")
    # 桌子 + 凳子 + 桌上的纸、墨水、油灯
    dx0, dx1 = L_DESK
    dt = base - 30
    back.rect(dx0, dt, dx1, dt + 3, WHEAT[3])
    back.rect(dx0, dt, dx1, dt + 1, WHEAT[5])
    back.rect(dx0 + 2, dt + 3, dx1 - 2, dt + 8, WHEAT[2])
    back.rect(dx0 + 2, dt + 7, dx1 - 2, dt + 8, WHEAT[1])
    back.rect(dx0 + 14, dt + 5, dx0 + 22, dt + 6, WHEAT[4])
    for lx in (dx0 + 2, dx1 - 5):
        back.rect(lx, dt + 8, lx + 3, base - 2, WHEAT[2])
        back.rect(lx, dt + 8, lx + 1, base - 2, WHEAT[4])
    back.rect(dx0 + 6, dt - 1, dx0 + 18, dt, WALL[6])                # 摊开的纸
    back.rect(dx0 + 9, dt - 2, dx0 + 20, dt - 1, WALL[5])
    back.rect(dx0 + 22, dt - 4, dx0 + 25, dt, DOOR[0])                # 墨水瓶
    back.rect(dx0 + 22, dt - 4, dx0 + 23, dt - 1, DOOR[2])
    back.rect(lamp[0] - 3, dt - 2, lamp[0] + 3, dt, WHEAT[2])        # 油灯：底座、灯罩、火
    back.rect(lamp[0] - 2, dt - 9, lamp[0] + 2, dt - 2, LAMP[2])
    back.rect(lamp[0] - 2, dt - 9, lamp[0] - 1, dt - 2, LAMP[3])
    back.rect(lamp[0] - 1, dt - 7, lamp[0] + 1, dt - 4, LAMP[3])
    back.rect(lamp[0] - 2, dt - 10, lamp[0] + 2, dt - 9, WHEAT[3])
    sx0 = 43                                                           # 凳子
    back.rect(sx0, base - 16, sx0 + 11, base - 13, WHEAT[3])
    back.rect(sx0, base - 16, sx0 + 11, base - 15, WHEAT[5])
    for lx in (sx0 + 1, sx0 + 8):
        back.rect(lx, base - 13, lx + 2, base - 2, WHEAT[2])
    # 床：麦黄木床架，粉白被子带一道淡蓝条，枕头靠右墙
    bx0, bx1 = L_BED
    bt = base - 20
    back.rect(bx1 - 3, bt - 10, bx1, base - 2, WHEAT[2])              # 床头板
    back.rect(bx1 - 3, bt - 10, bx1 - 2, base - 2, WHEAT[4])
    back.rect(bx1 - 3, bt - 11, bx1, bt - 10, WHEAT[4])
    back.rect(bx0, bt + 6, bx1 - 3, bt + 9, WHEAT[2])
    back.rect(bx0, bt + 6, bx1 - 3, bt + 7, WHEAT[3])
    back.rect(bx0, bt + 9, bx0 + 3, base - 2, WHEAT[2])
    back.rect(bx0, bt + 9, bx0 + 1, base - 2, WHEAT[4])
    q = (back.xx >= bx0) & (back.xx < bx1 - 3) & (back.yy >= bt) & (back.yy < bt + 7)
    q &= ~((back.xx < bx0 + 2) & (back.yy < bt + 2) & (((back.xx - (bx0 + 2)) ** 2 + (back.yy - (bt + 2)) ** 2) > 4))
    back.put(q, WALL[5])
    back.put(q & (back.yy < bt + 1), WALL[6])
    back.put(q & (back.yy >= bt + 5), WALL[3])
    back.put(q & (np.abs(back.xx - (bx0 + 10.5)) < 1.6) & (back.yy >= bt + 1), DOOR[3])
    pl = ellipse(back, bx1 - 9, bt - 1, 5, 2.6)
    back.put(pl, WALL[6])
    back.put(pl & (back.yy > bt - 0.5), WALL[4])
    # 床上面一块搁板：三个罐子；窗边挂一束晒干的麦穗
    sy = 174
    back.rect(bx0 + 2, sy, bx1 - 3, sy + 2, WHEAT[3])
    back.rect(bx0 + 2, sy, bx1 - 3, sy + 1, WHEAT[5])
    for (jx, jw, jh, col) in ((bx0 + 4, 5, 7, DOOR[2]), (bx0 + 11, 4, 5, WHEAT[4]), (bx0 + 17, 5, 8, FLOWER[0])):
        back.rect(jx, sy - jh, jx + jw, sy, col)
        back.rect(jx, sy - jh, jx + 1, sy, WALL[6])
        back.rect(jx + 1, sy - jh - 1, jx + jw - 1, sy - jh, WHEAT[2])
    back.rect(49, L_CEIL[1], 50, 160, WHEAT[2])
    back.put(poly_mask(back, [(47, 160), (52, 160), (54, 172), (45, 172)]), WHEAT[4])
    back.put(poly_mask(back, [(49.5, 160), (52, 160), (54, 172), (50, 172)]), WHEAT[3])
    # ---- 光：桌上油灯的暖光（两圈固定的半透明，只在屋里）
    light = Layer(LW, LH)
    dl = np.hypot((light.xx - lamp[0]) / 1.35, light.yy - (dt - 6))
    light.put(inner & (dl < 46), LAMP[2], 26)
    light.put(inner & (dl < 22), LAMP[2], 44)
    # ---- 前墙：两扇亮窗（下挂花箱）、淡蓝拱门（门缝漏暖光）、门上一小片三角帆布雨棚、门边挂一盏灯
    for wxx in (50, 88):
        lamp_window(front, wxx, 160, 8, 14, True)
        flower_box(front, wxx, 174, 8)
    arch_door(front, L_DOOR - 7, base, 14, 30, True)
    aw = poly_mask(front, [(L_DOOR - 11, base - 34), (L_DOOR + 11, base - 34), (L_DOOR + 13, base - 30), (L_DOOR + 8, base - 28),
                           (L_DOOR + 2, base - 29), (L_DOOR - 4, base - 28), (L_DOOR - 10, base - 30)])
    stripe = (np.floor((front.xx - (L_DOOR - 11)) / 3).astype(int) % 2) == 0      # 粉白、淡蓝相间的条纹篷
    front.put(aw, SAIL[3])
    front.put(aw & stripe, WALL[6])
    front.put(aw & (front.xx > L_DOOR + 6), SAIL[2])
    front.put(aw & stripe & (front.xx > L_DOOR + 6), WALL[4])
    front.rect(L_DOOR - 12, base - 35, L_DOOR + 12, base - 34, WHEAT[2])
    trim = body & (front.yy >= L_CEIL[0]) & (front.yy < L_CEIL[0] + 2)            # 前墙上沿一圈木条（盖住剖开的那道缝）
    front.put(trim, WHEAT[2])
    front.put(trim & (front.yy < L_CEIL[0] + 1), WHEAT[4])
    front.put(trim & ~np.roll(body, 1, axis=1), WHEAT[5])
    lamp_post_hang(front, L_DOOR + 13, base - 37)
    tufts = foot_tufts(LW, [(L_CX, base - 1, x1 - x0 + 2)], 8, lift=0.0)
    back.over(tufts)
    despeckle(back)
    despeckle(front)
    # 细塔上的小风车（房屋物件，100ms 一帧，45° 八帧匀速转）
    rx, ry, rr = L_ROTOR
    rot = []
    for k in range(8):
        Lr = piece(rx - rr - 1, ry - rr - 1, rx + rr + 2, ry + rr + 2)
        rotor_into(Lr, rx, ry, rr, 0.5 + (math.pi / 4) * k / 8)
        despeckle(Lr)
        rot.append(Lr)
    return back, front, light, view, rot


def lamp_post_hang(L: Layer, x, y):
    """门边墙上伸出来的一根小铁钩，挂一盏灯笼"""
    L.rect(x - 2, y, x + 3, y + 1, WHEAT[1])
    L.rect(x + 2, y, x + 3, y + 3, WHEAT[1])
    L.rect(x, y + 3, x + 5, y + 9, WHEAT[1])
    L.rect(x + 1, y + 4, x + 4, y + 8, LAMP[2])
    L.rect(x + 1, y + 4, x + 4, y + 5, LAMP[3])
    L.rect(x + 1, y + 7, x + 4, y + 8, LAMP[1])


# ======================================================================= 存图 + room.json
HAND = set(json.loads((ROOT / "art" / "手改清单.json").read_text(encoding="utf-8")).get("files", {}))


def save_png(arr, rel):
    if rel in HAND:
        print("跳过（作者手改过，见 art/手改清单.json）:", rel)
        return
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, "RGBA").save(p)


def save_json(obj, rel, comment):
    if rel in HAND:
        print("跳过（作者手改过）:", rel)
        return
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"_comment": comment, **obj}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cloud_layers():
    """作者 art/cloud/ 的原图，照 scenes/cloud_test.tscn 的视差 / 漂移（room_stage 没有 region：每张图本来就只在那几行有东西，
    石针图 181 行以下的那截由 scripts/cloud_town.gd 裁掉；streaks、wash 的叠加混合也由它设）"""
    out = []
    for (n, sc, y, h, mode) in AUTHOR:
        c = {"id": n, "img": f"res://art/cloud/{n}.png", "scroll": sc, "y": 0}
        if n not in ("sky", "wash"):
            c["tile"] = True
        if n in DRIFT:
            c["drift"] = DRIFT[n]
        out.append(c)
    return out


def town_json(anims):
    layers = cloud_layers()
    layers += [{"id": "town_far", "img": "res://art/cloud_town/town_far.png", "scroll": FAR_SC, "y": 0},
               {"id": "town_back", "img": "res://art/cloud_town/town_back.png", "scroll": 1.0, "y": 0},
               {"id": "town_main", "img": "res://art/cloud_town/town_main.png", "scroll": 1.0, "y": 0},
               {"id": "front", "img": "res://art/cloud/front.png", "scroll": 1.4, "y": 0, "tile": True, "front": True}]
    hx0 = LODGE - LW // 2
    return {
        "size": [W, H], "origin": list(ORIGIN), "env": "cloud", "bg": ["#1d1530", "#4a3550"],
        "layers": layers,
        "ground": GROUND, "walk": [16, W - 16],
        "markers": {
            "town_landing": 262, "town_helper": 304, "town_basket": 598, "town_plaza_side": 862, "town_fountain": FOUNTAIN,
            "town_back_side": 1052, "town_crowd": 1116, "town_bench": BENCHES[1] + 15, "town_far_side": 1250,
            "town_bed": BED_X + 30, "town_lodging": hx0 + L_DOOR,
        },
        "objects": {
            "town_ship": {"img": "res://art/cloud_town/ship_parked.png", "x": SHIP_X, "y": SHIP_Y},
            "town_bed": {"img": "res://art/cloud_town/town_bed.png", "x": BED_X, "y": GROUND + 1 - 26, "w": 60, "h": 26, "frames": 2,
                         "states": {"empty": 0, "planted": 1}, "default": "empty"},
            "town_toolbag": {"img": "res://art/cloud_town/empty.png", "x": 0, "y": 0, "w": 1, "h": 1,
                             "states": {"on_seat": 0}, "_note": "纯剧情状态（工具包放在驾驶座上），画面上没有东西"},
        },
        "ambient": [],
        "scripts": [{"script": "res://scripts/cloud_town.gd", "x": 0, "y": 0, "z": 0,
                     "params": {"anims": [{k: v for k, v in a.items() if not k.startswith("_")} for a in anims]}}],
    }


def room_json():
    return {
        "kind": "house", "host": "town", "x": LODGE, "size": [LW, LH],
        "back": "res://art/cloud_town/lodge_back.png", "front": "res://art/cloud_town/lodge_front.png",
        "light": "res://art/cloud_town/lodge_light.png", "view": "res://art/cloud_town/lodge_view.png",
        "floor": L_FLOOR, "walk": [L_BODY[0] + L_WALL + 6, L_BODY[1] - L_WALL - 6], "door": L_DOOR,
        "markers": {"townroom_desk": 48, "townroom_door": L_DOOR},
        "objects": {"townroom_rotor": {"img": "res://art/cloud_town/anim/lodge_rotor.png", "x": int(L_ROTOR[0] - L_ROTOR[2] - 1),
                                       "y": int(L_ROTOR[1] - L_ROTOR[2] - 1), "frames": 8, "states": {"spin": [0, 7]},
                                       "default": "spin"}},
    }


# ======================================================================= 预览：照 room.json 把各层叠出来（不开 Godot）
def _rgba(p):
    return np.asarray(Image.open(p).convert("RGBA")).astype(np.float32)


class Scene:
    def __init__(self, t=0.0):
        self.t = t
        js = json.loads((ROOT / "art/town/room.json").read_text(encoding="utf-8"))
        self.js = js
        self.layers = []
        frame_of = {}
        for a in js["scripts"][0]["params"]["anims"]:
            frame_of.setdefault(a["layer"], []).append(a)
        for c in js["layers"]:
            im = _rgba(ROOT / c["img"].replace("res://", "")).copy()
            if c["id"] == "spires":
                im[181:] = 0
            for a in frame_of.get(c["id"], []):
                sheet = _rgba(ROOT / a["img"].replace("res://", ""))
                k = (int(t * 10) + a.get("off", 0)) % a["frames"]
                fr = sheet[:, k * a["w"]:(k + 1) * a["w"]]
                _blend_into(im, fr, a["x"], a["y"])
            self.layers.append((c, im))
        rj = json.loads((ROOT / "art/town_room/room.json").read_text(encoding="utf-8"))
        self.room = rj
        self.hx0, self.hy0 = int(round(rj["x"] - LW / 2.0)), GROUND + 1 - LH
        self.hback = _rgba(ROOT / rj["back"].replace("res://", ""))
        self.hfront = _rgba(ROOT / rj["front"].replace("res://", ""))
        self.hlight = _rgba(ROOT / rj["light"].replace("res://", ""))
        self.hview = _rgba(ROOT / rj["view"].replace("res://", ""))[..., 3] > 0
        self.hobjs = []
        for oid, o in rj["objects"].items():
            sheet = _rgba(ROOT / o["img"].replace("res://", ""))
            w = sheet.shape[1] // o.get("frames", 1)
            k = int(t * 10) % o.get("frames", 1)
            self.hobjs.append((sheet[:, k * w:(k + 1) * w], o["x"], o["y"]))
        self.objs = []
        for oid, o in js["objects"].items():
            sheet = _rgba(ROOT / o["img"].replace("res://", ""))
            fr = o.get("frames", 1)
            st = o.get("default", "")
            k = o.get("states", {}).get(st, 0) if isinstance(o.get("states", {}).get(st, 0), int) else 0
            w = sheet.shape[1] // fr
            self.objs.append((sheet[:, k * w:(k + 1) * w], o["x"], o["y"]))

    def layer_px(self, c, w, cl):
        sc = float(c.get("scroll", 1.0))
        sx = np.arange(480)
        if c.get("tile"):
            return (sx + int(round(cl * sc - float(c.get("drift", 0.0)) * self.t))) % w
        return sx + cl - int(round(cl * (1 - sc)))

    def render(self, cl, front_alpha=1.0, chen=None, house=True, only_far=False, planted=False):
        img = np.zeros((270, 480, 3), np.float32)
        img[:] = (29, 21, 48)
        for (c, im) in self.layers:
            if c.get("front") or (only_far and float(c.get("scroll", 1)) >= 1.0):
                continue
            xs = self.layer_px(c, im.shape[1], cl)
            ok = (xs >= 0) & (xs < im.shape[1])
            sub = np.zeros((270, 480, 4), np.float32)
            sub[:, ok] = im[:, xs[ok]]
            al = sub[..., 3:4] / 255.0
            if c["id"] in ("streaks", "wash"):
                img = np.clip(img + sub[..., :3] * al, 0, 255)
            else:
                img = img * (1 - al) + sub[..., :3] * al
        if only_far:
            return img
        if house:
            far = self.render(cl, only_far=True)
            hx, hy = self.hx0 - cl, self.hy0
            img = _over_screen(img, self.hback, hx, hy)
            vm = np.zeros((270, 480), bool)
            _paste_mask(vm, self.hview, hx, hy)
            img[vm] = far[vm]
            for (fr, ox, oy) in self.hobjs:
                img = _over_screen(img, fr, hx + ox, hy + oy)
            img = _over_screen(img, self.hlight, hx, hy)
            if front_alpha > 0:
                f = self.hfront.copy()
                f[..., 3] *= front_alpha
                img = _over_screen(img, f, hx, hy)
        for (fr, ox, oy) in self.objs:
            if planted and fr.shape[1] == 60:
                pass
            img = _over_screen(img, fr, ox - cl, oy)
        if chen is not None:
            C, cx, cy = chen_ref(chen[0] - cl, chen[1])
            img = _over_screen(img, C.a.astype(np.float32), cx, cy)
        for (c, im) in self.layers:
            if not c.get("front"):
                continue
            xs = self.layer_px(c, im.shape[1], cl)
            sub = im[:, xs]
            al = sub[..., 3:4] / 255.0
            img = img * (1 - al) + sub[..., :3] * al
        return np.clip(img, 0, 255).astype(np.uint8)


def _blend_into(dst, src, x, y):
    h, w = src.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    d = dst[y0:y1, x0:x1]
    sa = s[..., 3:4] / 255.0
    da = d[..., 3:4] / 255.0
    oa = sa + da * (1 - sa)
    d[..., :3] = np.where(oa > 0, (s[..., :3] * sa + d[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6), 0)
    d[..., 3:4] = oa * 255


def _over_screen(img, src, x, y):
    h, w = src.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, 480), min(y + h, 270)
    if x1 <= x0 or y1 <= y0:
        return img
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    al = s[..., 3:4] / 255.0
    img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - al) + s[..., :3] * al
    return img


def _paste_mask(dst, m, x, y):
    h, w = m.shape
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x1 > x0 and y1 > y0:
        dst[y0:y1, x0:x1] = m[y0 - y:y1 - y, x0 - x:x1 - x]


def preview(d: Path, t=0.0):
    d.mkdir(parents=True, exist_ok=True)
    S = Scene(t)
    # 整条街（每一列取「镜头正对着这一列」时的画面：视差层按真实镜头位置）
    pano = np.zeros((270, W, 3), np.uint8)
    for cl in range(0, W, 480):                 # 一屏一屏接起来（镜头在 0、480、960…，最后一屏贴右边）
        c2 = min(cl, W - 480)
        im = S.render(c2)
        pano[:, cl:min(cl + 480, W)] = im[:, cl - c2:cl - c2 + min(480, W - cl)]
    Image.fromarray(pano).save(d / "town_full_1x.png")
    shots = {"landing": (0, (262, GROUND)), "road": (380, (520, GROUND)), "plaza": (FOUNTAIN - 240, (940, GROUND)),
             "lodging": (W - 480, (1480, GROUND))}
    for n, (cl, ch) in shots.items():
        im = S.render(cl, chen=ch)
        Image.fromarray(im).save(d / f"town_{n}.png")
        if n == "plaza":
            Image.fromarray(im).resize((1440, 810), Image.NEAREST).save(d / "town_plaza_x3.png")
    cl = int(np.clip(LODGE - 240, 0, W - 480))
    im = S.render(cl, front_alpha=0.0, chen=(S.hx0 + 48, GROUND))
    Image.fromarray(im).save(d / "town_room.png")
    hx = S.hx0 - cl
    crop = im[:, max(hx - 40, 0):hx + LW + 40]
    Image.fromarray(crop).resize((crop.shape[1] * 3, 810), Image.NEAREST).save(d / "town_room_x3.png")
    print("预览:", d)


def fix_speckles(a, passes=4):
    """图边上的孤立点（despeckle 的边是按自己补的，查不到）：换成图里那几个邻居里最多的颜色"""
    for _ in range(passes):
        sp = find_speckles(a)
        if not sp:
            break
        h, w = a.shape[:2]
        for (y, x) in sp:
            nb = [a[yy, xx] for (yy, xx) in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)) if 0 <= yy < h and 0 <= xx < w]
            keys = [tuple(int(v) for v in c) for c in nb]
            best = max(set(keys), key=keys.count)
            a[y, x] = best
    return a


# ======================================================================= 自查：孤立单像素
def check(paths):
    bad = 0
    for p in paths:
        a = np.asarray(Image.open(p).convert("RGBA"))
        sp = find_speckles(a)
        if len(sp):
            bad += len(sp)
            print(f"  孤立像素 {len(sp):3d}  {p.relative_to(ROOT)}  例: {[(int(x), int(y)) for y, x in sp[:6]]}")
    print("孤立像素合计:", bad)


def build():
    ANIMS.clear()
    far = build_far()
    back = build_back()
    main = build_main(back)
    lb, lf, ll, lv, lrot = lodging()
    out = []

    def sv(L, rel, fix=True):
        arr = L.a if isinstance(L, Layer) else L
        if fix:
            fix_speckles(arr)
        save_png(arr, rel)
        out.append(ROOT / rel)

    sv(far, "art/cloud_town/town_far.png")
    sv(back[0], "art/cloud_town/town_back.png")
    sv(main, "art/cloud_town/town_main.png")
    sv(ship_img(), "art/cloud_town/ship_parked.png", fix=False)        # 作者的飞船原图，一个像素都不动
    bed = np.concatenate([flower_bed(0).a, flower_bed(1).a], 1)
    sv(bed, "art/cloud_town/town_bed.png")
    sv(np.zeros((1, 1, 4), np.uint8), "art/cloud_town/empty.png")
    sv(lb, "art/cloud_town/lodge_back.png")
    sv(lf, "art/cloud_town/lodge_front.png")
    sv(ll, "art/cloud_town/lodge_light.png")
    sv(lv, "art/cloud_town/lodge_view.png")
    sv(np.concatenate([j.a for j in lrot], 1), "art/cloud_town/anim/lodge_rotor.png")
    for a in ANIMS:
        sv(np.concatenate([f.a for f in a["_frames"]], 1), f"art/cloud_town/anim/{a['_name']}.png")
    save_json(town_json(ANIMS), "art/town/room.json",
              "结局三 · 云层上的风帆小镇。tools/cloud_town_art.py 生成，别手改。天和云是作者 art/cloud/ 的原图（照 scenes/cloud_test.tscn 的视差和漂移），"
              "小镇（远塔、塔、地面）在 art/cloud_town/。风车、帆、水车、喷泉的动画由 scripts/cloud_town.gd 挂到层上播（100ms 一帧）。"
              "从左到右：木停机台（飞船）→ 石头路（倒了的篮子）→ 湿石台广场（喷泉、水车、大风车、长椅）→ 花圃和龙头 → 晨住的塔（town_room）。")
    save_json(room_json(), "art/town_room/room.json",
              "结局三 · 晨在云层小镇暂住的屋子（剖面小屋，在 town 里；前墙进屋淡出）。tools/cloud_town_art.py 生成，别手改。"
              "一座风车塔：下截是住的那层（左边门、中间书桌，窗在桌子上面透出外面的天和云、右边床），淡蓝裙檐上一截细塔 + 尖顶，小风车是动的。")
    print("写好", len(out), "张图")
    check(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    ap.add_argument("--only-preview", action="store_true")
    args = ap.parse_args()
    if not args.only_preview:
        build()
    if args.preview:
        preview(Path(args.preview))


if __name__ == "__main__":
    main()
