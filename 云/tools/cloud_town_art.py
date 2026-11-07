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
            if a[y, x, 3] > 0:
                op = [c for c in cand if (c & 0xff) > 0]
                cand = op or cand                                # 同上：轮廓上的点不换成透明
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
    if "hw" in T:                                       # 第四轮的圆锥顶：每行的半宽是画的时候记下来的
        return T["hw"].get(int(round(y)), 0) + 1.0
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
    """预览里放一帧晨（奥斯卡画的 chen_oscar.png，待机第 7 帧；帧 68×60，脚底在帧里 (28, 56)）：只为看比例和看不看得清，
    正式图不画晨。游戏里晨还吃 env cloud 的暖色和左边的亮边，这里是原色。"""
    im = np.asarray(Image.open(ROOT / "art/characters/chen/chen_oscar.png").convert("RGBA"))[:, 7 * 68:8 * 68]
    L = Layer(68, im.shape[0])
    L.a[:] = im
    return L, x - 28, foot - 56


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


# ======================================================================= 材质（11-01 作者：「建筑缺乏质感」→ 风车 + 欧洲尖顶城堡）
#   每栋房子先算一张「明暗档」图 idx（光一律从左边低处来：左亮右暗，屋檐下、塔脚暗），
#   再往 idx 上叠材质：石砌（一层层错开的石块，灰缝暗一档，个别石块整块亮 / 暗一档）、瓦片（一层层，每层上沿压一道影子）、
#   木框架（深色木梁）；亮着的窗把周围一圈墙照暖（换一套暖色，不是半透明）。最后按 idx 查色。
#   11-01 作者看了第二版：「城堡过于抢眼，砖块黑色缝隙是最大的败笔」→ 不画灰缝网格；整套建筑色阶压暗、降饱和，
#   最亮的墙面也比晨的白头发暗一大截（晨要一直是画面里对比最高的），亮的只留窗里的暖光。
BWALL = lch_ramp(0.25, 0.60, 0.022, 0.032, 292, 338, 7)     # 房子的石墙（喷泉、长椅那些还用原来的 WALL）
BRIM = "#%02x%02x%02x" % CA.from_lch(0.64, 0.04, 20)        # 朝余晖那条边：只比墙亮一点
TERRA = lch_ramp(0.26, 0.58, 0.04, 0.06, 12, 52, 7)         # 陶瓦：暗端玫瑰褐 → 亮端灰杏
SLATE = lch_ramp(0.24, 0.56, 0.025, 0.04, 278, 255, 7)      # 石板瓦：暗端靛灰 → 亮端灰蓝
TIMBER = lch_ramp(0.17, 0.38, 0.02, 0.035, 340, 380, 5)     # 半木结构的木梁、门框：深玫瑰褐
PLASTER = lch_ramp(0.30, 0.64, 0.02, 0.03, 330, 380, 7)     # 灰泥墙：比石头暖一点
DOOR = lch_ramp(0.28, 0.52, 0.035, 0.045, 280, 252, 4)      # 门、百叶：灰蓝


def _mix_hex(a, b, t):
    a, b = hexc(a).astype(float), hexc(b).astype(float)
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in a * (1 - t) + b * t)


WALL_W = [_mix_hex(c, LAMP[1], 0.26) for c in BWALL]         # 灯照着的石墙
PLASTER_W = [_mix_hex(c, LAMP[1], 0.24) for c in PLASTER]
ROOF_PAL = {"slate": SLATE, "terra": TERRA}


def _xy(L):
    return np.floor(L.xx).astype(int), np.floor(L.yy).astype(int)


def masonry(L: Layer, m, idx, seed, y0, course=4, blen=(4, 8), var=0.10, edges=None):
    """石头的暗示（不画灰缝、不成网格）：墙面是按受光分面的平涂，只撒零星几块石头 —— 每块是一个比底色亮一档或暗一档的
    小方块（course−1 行高、blen 长，没有描边），按「层」排，同一层的石块之间至少隔开一块的长度、上下两层不重叠。
    var = 大概多少面积有石块；edges = 再多撒石块的地方（墙角、门窗边上露出来的石头），在那里密度翻三倍。"""
    if not m.any():
        return idx
    rng = np.random.default_rng(seed)
    X, Y = _xy(L)
    cy = (Y - y0) // course
    ry = (Y - y0) % course
    out = idx.copy()
    x0, x1 = X[m].min(), X[m].max()
    prev = []
    for c in np.unique(cy[m]):
        row = m & (cy == c) & (ry < course - 1)
        if not row.any():
            continue
        cur = []
        x = x0 + int(rng.integers(0, blen[1]))
        while x <= x1:
            bl = int(rng.integers(blen[0], blen[1] + 1))
            blk = row & (X >= x) & (X < x + bl)
            p = var
            if edges is not None and (blk & edges).any():
                p = var * 3
            free = not any(a_ < x + bl + 1 and x < b_ + 1 for (a_, b_) in prev)
            if free and blk.sum() >= bl * (course - 1) * 0.7 and rng.random() < p:
                out[blk] = idx[blk] + (1 if rng.random() < 0.45 else -1)
                cur.append((x, x + bl))
                x += bl + int(rng.integers(bl, 2 * bl + 1))
            else:
                x += bl
        prev = cur
    return out


def tiles(L: Layer, m, idx, seed, y0, course=3, tlen=(3, 5), var=0.12):
    """瓦顶：不画每层瓦下面的深线，只撒少量亮一档 / 暗一档的瓦片（和石头一样的画法，小一号）"""
    return masonry(L, m, idx, seed, y0, course=course, blen=(tlen[0] + 1, tlen[1] + 2), var=var)


def paint(L: Layer, m, idx, pal, warm=None, glow=None):
    idx = np.clip(idx, 0, len(pal) - 1)
    for k in range(len(pal)):
        sel = m & (idx == k)
        if glow is not None and warm is not None:
            L.put(sel & ~glow, pal[k])
            L.put(sel & glow, warm[k])
        else:
            L.put(sel, pal[k])


def glow_of(L: Layer, wins, m):
    """亮着的窗把周围一圈墙照暖：窗框外 3 像素的一个圆角框（边不贴着窗框走，不和窗框挤出一条一格一格的竖线）"""
    g = np.zeros(m.shape, bool)
    for (x, y, w, h, lit) in wins:
        if lit:
            dx = np.abs(L.xx - (x + w / 2.0)) - (w / 2.0 + 1)
            dy = np.abs(L.yy - (y + h / 2.0 + 1)) - (h / 2.0 + 1)
            g |= (dx < 3) & (dy < 3) & ~((dx > 1) & (dy > 1) & (np.hypot(dx - 1, dy - 1) > 2.0))   # 离窗框 3 像素的圆角框
    return g & m


def cyl_idx(L: Layer, cx, half, top, base, lift=0):
    """圆柱的明暗档：左边亮、往右一档档暗，塔脚那截再暗"""
    u = (L.xx - cx) / np.maximum(half, 0.5)
    idx = 5 - band(u, (-0.62, -0.1, 0.42, 0.78)) + lift
    v = (L.yy - top) / max(base - top, 1)
    return idx - (v > 0.8)


def flat_cyl_idx(L: Layer, cx, half, hi=4):
    """明暗档少的圆柱（晨住的那座：离镜头最近、体量最大，要收着）：只分三面 hi / hi−1 / hi−2"""
    u = (L.xx - cx) / np.maximum(half, 0.5)
    return hi - band(u, (-0.4, 0.5))


def stone_edges(L: Layer, m, cx, half, wins=(), door=None):
    """墙角（塔身左右边上 3 像素）和门窗四周 3 像素：这些地方多露几块石头"""
    e = m & ((half - np.abs(L.xx - cx)) < 3)
    for (x, y, w, h, lit) in wins:
        e |= m & (L.xx >= x - 3) & (L.xx < x + w + 3) & (L.yy >= y - 3) & (L.yy < y + h + 4)
    if door is not None:
        x, base, w, h = door
        e |= m & (L.xx >= x - 4) & (L.xx < x + w + 4) & (L.yy >= base - h - 4)
    return e


def rim_light(L: Layer, m, col, upto=None, skip=None):
    """朝余晖的左边一道亮边（边按整个 m 找；skip = 不描的地方，比如被窗照暖的那块）"""
    e = m & ~np.roll(m, 1, axis=1)
    if upto is not None:
        e &= L.yy < upto
    if skip is not None:
        e &= ~skip
    L.put(e, col)


def deep_window(L: Layer, x, y, w, h, lit=True, shutters=False, sill=True, frame_pal=None, cross=True):
    """有厚度的窗：浅色石头窗套（左上亮、右下暗）、窗洞里左边一列是窗套的影子、玻璃（亮着 = 暖黄上亮下暗 + 十字窗棂；
    没亮 = 映着天的暗玻璃）、下面一条突出的窗台，窗台在墙上投一行影子。shutters = 两边打开的淡蓝木百叶。"""
    fp = frame_pal or BWALL
    w, h = int(w), int(h)
    r = w / 2.0
    m = (L.xx >= x) & (L.xx < x + w) & (L.yy >= y + r) & (L.yy < y + h)
    m |= ellipse(L, x + r, y + r, r, r) & (L.yy < y + r + 0.5)
    ring = (np.roll(m, 1, 0) | np.roll(m, -1, 1) | np.roll(m, 1, 1) | np.roll(m, -1, 0)) & ~m
    ring |= (np.roll(ring, 1, 1) & (L.xx >= x + w + 1) & (L.xx < x + w + 2))     # 右边（背光那边）的窗套两像素宽
    ring &= L.yy < y + h
    L.put(ring, fp[5])
    L.put(ring & (L.xx >= x + w), fp[3])
    if shutters:
        sw = max(2, w // 2)
        for (sx, side) in ((x - 1 - sw, -1), (x + w + 1, 1)):
            sm = (L.xx >= sx) & (L.xx < sx + sw) & (L.yy >= y + 1) & (L.yy < y + h)
            L.put(sm, DOOR[2] if side < 0 else DOOR[1])
            L.put(sm & (L.yy < y + 2), DOOR[3])
            L.put(sm & (np.abs(L.yy - (y + h / 2.0)) < 0.6), DOOR[0])
    if lit:
        L.put(m, LAMP[2])
        L.put(m & (L.yy < y + r + 1), LAMP[3])
        L.put(m & (L.yy >= y + h - 2), LAMP[1])
        L.put(m & (L.xx < x + 1), LAMP[1])
        if cross and w >= 5 and h >= 8:
            L.put(m & (np.abs(L.xx - (x + w / 2.0)) < 0.5), TIMBER[1])
            L.put(m & (np.abs(L.yy - (y + r + (h - r) * 0.35)) < 0.5), TIMBER[1])
    else:
        L.put(m, BWALL[1])
        L.put(m & (L.yy < y + r + 1), SLATE[2])
        L.put(m & (L.xx < x + 1), BWALL[0])
        if w >= 4:
            L.px(x + w - 2, y + r, SLATE[3])
            L.px(x + w - 2, y + r + 1, SLATE[3])
    if sill:
        L.rect(x - 1, y + h, x + w + 1, y + h + 1, fp[6])
        L.rect(x - 1, y + h + 1, x + w + 1, y + h + 2, fp[2])
    return m


def stone_door(L: Layer, x, base, w, h, lit=False, step=True, pal=None):
    """拱门：一圈石块砌的门套（拱顶的石块一块块分开）、淡蓝木门板（竖的板缝、两道铁箍、门环），亮着的门开一条缝漏暖光；
    门口一级石台阶"""
    pal = pal or BWALL
    r = w / 2.0
    cx = x + r
    m = (L.xx >= x) & (L.xx < x + w) & (L.yy >= base - h + r) & (L.yy < base)
    m |= ellipse(L, cx, base - h + r, r, r) & (L.yy < base - h + r + 0.5)
    outer = (L.xx >= x - 2) & (L.xx < x + w + 2) & (L.yy >= base - h + r) & (L.yy < base)
    outer |= ellipse(L, cx, base - h + r, r + 2, r + 2) & (L.yy < base - h + r + 0.5)
    ring = outer & ~m
    ang = np.degrees(np.arctan2(L.yy - (base - h + r), L.xx - cx))
    seg = np.floor((ang + 180) / 30)
    tone = np.where((seg % 2 == 0) | (L.yy >= base - h + r), 5, 4) - (L.xx > cx + 0.5)   # 拱上一块块分开，门边两条是整的
    paint(L, ring, tone, pal)
    L.put(ring & (L.yy < base - h + r) & (np.abs(L.xx - cx) < 1.0) & (L.yy < base - h + 1.5), pal[6])   # 拱心石
    L.put(m, DOOR[2])
    L.put(m & (L.xx < x + 1.5), DOOR[1])                         # 门洞里左边是门套的影子
    for sx in np.arange(x + 3, x + w - 1, 3):                    # 板缝（停在台阶上面两行）
        L.put(m & (np.abs(L.xx - sx - 0.5) < 0.5) & (L.yy > base - h + 2) & (L.yy < base - 4), DOOR[1])
    for by in (base - h * 0.62, base - h * 0.28):
        L.put(m & (np.abs(L.yy - by) < 0.6), TIMBER[0])
    L.rect(cx + 1, base - h * 0.45, cx + 3, base - h * 0.45 + 2, WHEAT[4])
    if lit:
        gap = m & (L.xx >= x + w - 3) & (L.xx < x + w - 1) & (L.yy > base - h + r)
        L.put(gap, LAMP[2])
        L.put(gap & (L.xx >= x + w - 2), LAMP[3])
    if step:
        L.rect(x - 3, base - 2, x + w + 3, base, STONE[3])
        L.rect(x - 3, base - 2, x + w + 3, base - 1, STONE[4])
        L.rect(x + w + 2, base - 2, x + w + 3, base, STONE[1])
    return m


def cone_roof(L: Layer, cx, eave_y, half, cap_h, pal, seed, flare=2.5, expo=1.7, flat=False):
    """圆锥尖顶（瓦）：两边微微内凹收到一个尖，檐口比墙宽 flare、有两行厚（上面亮的檐边，下面一行暗的檐底）。
    返回 (尖 x, 尖 y, mask)。"""
    rw = half + flare
    pts = []
    n = 18
    for i in range(n + 1):
        t = i / n
        pts.append((cx - rw * (1 - t) ** expo, eave_y + 2 - (cap_h + 2) * t))
    for i in range(n, -1, -1):
        t = i / n
        pts.append((cx + rw * (1 - t) ** expo + 0.01, eave_y + 2 - (cap_h + 2) * t))
    m = poly_mask(L, pts)
    u = (L.xx - cx) / rw
    idx = (4 - band(u, (-0.35, 0.45))) if flat else (5 - band(u, (-0.5, -0.05, 0.42, 0.75)))
    idx = tiles(L, m, idx, seed, eave_y + 1, course=3)
    paint(L, m, idx, pal)
    rim_light(L, m, pal[5] if flat else pal[6])
    fas = m & (L.yy >= eave_y)
    L.put(fas, pal[1])
    L.put(fas & (L.yy < eave_y + 1), pal[4])
    L.put(fas & (L.yy < eave_y + 1) & (u < -0.4), pal[5])
    return cx, eave_y - cap_h, m


def flagpole(L: Layer, x, tip_y, length):
    """尖上竖一根细旗杆，顶上一颗麦黄的小球（旗子是动画）"""
    L.rect(x, tip_y - length, x + 1, tip_y + 2, TIMBER[2])
    L.rect(x - 1, tip_y - length - 2, x + 2, tip_y - length, WHEAT[4])
    L.px(x - 1, tip_y - length - 2, WHEAT[5])
    return x, tip_y - length


def plinth(L: Layer, cx, base, half, h=9, seed=0, pal=None):
    """塔脚的石基：比塔身宽 2 像素、上沿斜着收进去的一圈大石块，往下一直埋进云里（base 以下再多画 6 行，给云盖住）"""
    pal = pal or BWALL
    yt = base - h
    hh = half + 2 - 2 * np.clip((yt + 3 - L.yy) / 3.0, 0, 1)
    m = (np.abs(L.xx - cx) < hh) & (L.yy >= yt) & (L.yy < base + 6)
    idx = cyl_idx(L, cx, hh, yt, base + 6) - 1
    idx = masonry(L, m, idx, seed, yt, course=5, blen=(6, 11), var=0.3)
    paint(L, m, idx, pal)
    L.put(m & (L.yy < yt + 1), pal[5])
    L.put(m & (L.yy < yt + 1) & (L.xx > cx + half * 0.4), pal[3])
    rim_light(L, m, pal[6], upto=base)
    return m


def stains(L: Layer, m, idx, wins, seed):
    """窗台下面淌下来的水渍（窗台下一两条暗一档的竖道）"""
    rng = np.random.default_rng(seed)
    out = idx.copy()
    X, Y = _xy(L)
    for (x, y, w, h, lit) in wins:
        for k in range(int(rng.integers(1, 3))):
            sx = int(x + rng.integers(0, max(w, 1)))
            ln = int(rng.integers(3, 7))
            s = m & (X == sx) & (Y >= y + h + 2) & (Y < y + h + 2 + ln)
            out[s] -= 1
    return out


def moss(L: Layer, m, base, seed, n=3):
    """塔脚背光那边几小团青苔"""
    rng = np.random.default_rng(seed)
    X, Y = _xy(L)
    xs = X[m & (Y == base - 2)]
    if len(xs) == 0:
        return
    for _ in range(n):
        x = int(rng.integers(int(np.percentile(xs, 45)), xs.max() + 1))
        y = base - int(rng.integers(3, 8))
        blob = m & (np.abs(L.xx - x - 0.5) <= rng.uniform(1.6, 2.6)) & (np.abs(L.yy - y - 0.5) <= 1.5)
        L.put(blob, LEAF[1])
        L.put(blob & (L.yy < y), LEAF[2])


# ----------------------------------------------------------------------- 建筑
def stone_tower(L: Layer, cx, base, w, h, cap_h, roof="slate", wins=(), door=None, taper=2, seed=0, crenel=False,
                plain=False):
    """石砌圆塔：塔脚一圈石基，塔身一层层的石块，屋檐下一道影子，有厚度的窗和拱门；
    roof 尖顶（slate 石板 / terra 陶瓦）；crenel = 顶上一圈带雉堞的护墙（下面一排托石），尖顶从护墙后面长出来（城堡塔）。
    wins = [(从塔顶往下 dy, 宽, 高, 亮不亮), …]；door = (宽, 高, 亮不亮)。plain = 远处的：不画石缝（太小，画了是噪点）。"""
    top = base - h
    t = np.clip((base - L.yy) / h, 0, 1)
    half = w / 2.0 - taper * t
    m = (np.abs(L.xx - cx) < half) & (L.yy >= top) & (L.yy < base)
    wl = []
    for (dy, ww, wh, lit) in wins:
        wl.append((int(round(cx - ww / 2.0)), top + dy, ww, wh, lit))
    idx = cyl_idx(L, cx, half, top, base)
    if not plain:
        dr = None if door is None else (int(round(cx - door[0] / 2.0)), base, door[0], door[1])
        idx = masonry(L, m, idx, seed, top, course=4, blen=(4, 7), edges=stone_edges(L, m, cx, half, wl, dr))
        idx = stains(L, m, idx, wl, seed + 1)
    eave = 4 if not crenel else 3
    idx = idx - 2 * (L.yy < top + eave) - 1 * ((L.yy >= top + eave) & (L.yy < top + eave + 2))
    glow = glow_of(L, wl, m)
    paint(L, m, idx, BWALL, WALL_W, glow)
    rim_light(L, m, BRIM, upto=base - 10, skip=glow)
    if not plain:
        moss(L, m, base, seed + 5)
    for (x, y, ww, wh, lit) in wl:
        deep_window(L, x, y, ww, wh, lit, shutters=(lit and ww >= 6 and not plain), cross=not plain)
    if door is not None:
        dw, dh, lit = door
        stone_door(L, int(round(cx - dw / 2.0)), base, dw, dh, lit)
    ht = w / 2.0 - taper
    if crenel:
        hp = ht + 2
        X, Y = _xy(L)
        # 托石（一排小牛腿，伸出塔身）
        cb = (np.abs(L.xx - cx) < hp) & (L.yy >= top - 1) & (L.yy < top + 2)
        cb &= ~((np.abs(L.xx - cx) >= ht) & (np.mod(X - int(cx - hp), 4) >= 2))
        cb &= ~((np.abs(L.xx - cx) >= ht) & (L.yy >= top + 1) & (np.abs(L.xx - cx) >= ht + 1))
        paint(L, cb, cyl_idx(L, cx, hp, top - 10, base) - 2, BWALL)
        # 护墙 + 雉堞
        pw = (np.abs(L.xx - cx) < hp) & (L.yy >= top - 8) & (L.yy < top - 1)
        notch = (L.yy < top - 5) & (np.mod(X - int(cx - hp) - 2, 5) >= 3)
        pw &= ~notch
        pidx = cyl_idx(L, cx, hp, top - 10, base)
        pidx = masonry(L, pw, pidx, seed + 7, top - 8, course=3, blen=(3, 6), var=0.15) if not plain else pidx
        paint(L, pw, pidx, BWALL)
        L.put(pw & ~np.roll(pw, 1, axis=0), BWALL[6])
        L.put(pw & ~np.roll(pw, 1, axis=0) & (L.xx > cx + hp * 0.4), BWALL[4])
        rim_light(L, pw, BRIM)
        P = Layer(L.w, L.h, L.ox, L.oy)
        tx, ty, rm = cone_roof(P, cx, top - 5, ht, cap_h, ROOF_PAL[roof], seed + 3, flare=1.0)
        under = P.a[..., 3] > 0
        keep = L.a[..., 3] > 0
        L.a[under & ~(keep & (L.yy >= top - 8))] = P.a[under & ~(keep & (L.yy >= top - 8))]
    else:
        tx, ty, rm = cone_roof(L, cx, top, ht, cap_h, ROOF_PAL[roof], seed + 3)
    if crenel:
        return {"cx": cx, "top": top - 5, "base": base, "tip": (tx, ty), "rw": ht + 1.0, "cap_h": cap_h, "w": w}
    return {"cx": cx, "top": top, "base": base, "tip": (tx, ty), "rw": ht + 2.5, "cap_h": cap_h, "w": w}


def timber_house(L: Layer, cx, base, w, floors=2, roof_h=22, roof="terra", seed=0, lit=(True, False, True), plain=False,
                 door_lit=False):
    """半木结构的窄房子（山墙朝外）：底层石砌带拱门，上面每层灰泥墙 + 深色木框架（立柱、横梁、斜撑），每层往外挑出 1 像素
    （下面一排梁头的影子），窗带淡蓝百叶；山墙也是木框架，尖上开一扇小圆窗；两条坡上露出三行厚的瓦边（屋顶的厚度）。"""
    rng = np.random.default_rng(seed)
    g_h = 16
    f_h = 15
    x0 = int(round(cx - w / 2.0))
    X, Y = _xy(L)
    # 底层：石砌
    m0 = (L.xx >= x0) & (L.xx < x0 + w) & (L.yy >= base - g_h) & (L.yy < base)
    idx = 4 - (L.xx >= x0 + w - 3) - (L.yy >= base - 4)
    idx = masonry(L, m0, idx, seed, base - g_h, course=4, blen=(4, 8)) if not plain else idx
    paint(L, m0, idx, BWALL)
    rim_light(L, m0, BRIM)
    top = base - g_h
    xa, xb = x0, x0 + w
    wins = []
    for f in range(floors):
        xa, xb = xa - 1, xb + 1
        yb, ya = top, top - f_h
        mf = (L.xx >= xa) & (L.xx < xb) & (L.yy >= ya) & (L.yy < yb)
        win = []
        nw = 2 if (xb - xa) >= 26 else 1
        for k in range(nw):
            wx = int(xa + (xb - xa) * (k + 1) / (nw + 1) - 2.5)
            win.append((wx, ya + 4, 5, 8, bool(lit[(f + k) % len(lit)])))
        idx = 5 - (L.xx >= xb - 3)
        glow = glow_of(L, win, mf)
        paint(L, mf, idx, PLASTER, PLASTER_W, glow)
        # 木框架：两头立柱、上下横梁、窗两边的柱子、窗下的短斜撑
        tm = mf & ((L.xx < xa + 2) | (L.xx >= xb - 2) | (L.yy >= yb - 2) | (L.yy < ya + 1))
        for (wx, wy, ww, wh, l_) in win:
            tm |= mf & (((L.xx >= wx - 3) & (L.xx < wx - 1)) | ((L.xx >= wx + ww + 1) & (L.xx < wx + ww + 3)))
        if not plain:
            for (sx, sgn) in ((xa + 2, 1), (xb - 3, -1)):
                for (px_, py_) in line4(sx, yb - 3, sx + sgn * 5, ya + 2):
                    tm |= mf & (X == px_) & (Y == py_)
                    tm |= mf & (X == px_ + sgn) & (Y == py_)
        L.put(tm, TIMBER[2])
        L.put(tm & (L.xx >= xb - 2), TIMBER[1])
        L.put(tm & (L.yy >= yb - 1), TIMBER[1])
        L.put(tm & (L.xx < xa + 1), TIMBER[3])
        L.rect(xa, yb, xb, yb + 1, TIMBER[0])                     # 挑出去的楼层下面一行梁头的影子
        for (wx, wy, ww, wh, l_) in win:
            deep_window(L, wx, wy, ww, wh, l_, shutters=not plain, sill=False, frame_pal=PLASTER, cross=False)
        wins += win
        top = ya
    # 山墙
    rw = (xb - xa) / 2.0
    ccx = (xa + xb) / 2.0
    gm = poly_mask(L, [(xa, top + 0.01), (xb, top + 0.01), (ccx, top - roof_h)])
    gidx = 5 - (L.xx >= ccx + rw * 0.6)
    paint(L, gm, gidx, PLASTER)
    tm = gm & ((np.abs(L.xx - ccx) < 1.0) | (L.yy >= top - 2))
    L.put(tm, TIMBER[2])
    if roof_h >= 16:
        ow = ellipse(L, ccx, top - roof_h * 0.45, 2.6, 2.6)
        L.put(ow, LAMP[2] if lit[0] else BWALL[1])
        L.put(ow & (L.yy < top - roof_h * 0.45 - 0.5), LAMP[3] if lit[0] else SLATE[2])
    # 两条坡上的瓦边（三行厚）+ 封檐板
    pal = ROOF_PAL[roof]
    outer = poly_mask(L, [(xa - 3, top + 2), (ccx, top - roof_h - 3.5), (xb + 3, top + 2)])
    inner = poly_mask(L, [(xa + 0.5, top + 2), (ccx, top - roof_h + 0.5), (xb - 0.5, top + 2)])
    rm = outer & ~inner
    ridx = 5 - (L.xx >= ccx) - (L.xx >= ccx + rw * 0.5)
    ridx = tiles(L, rm, ridx, seed + 2, top - roof_h - 4, course=3, tlen=(2, 4))
    paint(L, rm, ridx, pal)
    edge_in = rm & np.roll(inner, -1, 0)
    L.put(edge_in, TIMBER[1])
    rim_light(L, rm, pal[6])
    # 烟囱（一侧坡上）
    chx = int(ccx + rw * 0.45)
    cy0 = int(top - roof_h * 0.45 - 6)
    ch = (L.xx >= chx) & (L.xx < chx + 4) & (L.yy >= cy0) & (L.yy < top - roof_h * 0.2)
    ch &= ~inner | (L.yy < top - roof_h * 0.45)
    paint(L, ch, np.full(ch.shape, 3) - (L.xx >= chx + 3), BWALL)
    L.rect(chx - 1, cy0 - 1, chx + 5, cy0 + 1, BWALL[5])
    L.rect(chx - 1, cy0, chx + 5, cy0 + 1, BWALL[2])
    # 门
    if not plain:
        moss(L, m0, base, seed + 4, n=2)
    dx = int(cx - 5 + (rng.integers(-3, 4) if w > 24 else 0))
    stone_door(L, dx, base, 10, 14, door_lit)
    return {"cx": ccx, "top": top - roof_h, "base": base, "tip": (ccx, top - roof_h - 3), "rw": rw, "cap_h": roof_h, "w": w,
            "chimney": (chx, cy0)}


def dutch_mill(L: Layer, cx, base, wb, wt, h, seed=0, stage=0.45, wins=(), door=(11, 22, True)):
    """荷兰式的塔式风车（静的部分）：往上收的八角塔身（三个面：左亮、中、右暗，竖的棱线），石砌；腰上一圈木头的收帆台
    （平台 + 斜撑 + 扶手），顶上船底形的木帽（瓦），帽前伸出风轴的轴头（叶片是动画，转在轴头上）。返回轴头位置。"""
    top = base - h
    t = np.clip((base - L.yy) / h, 0, 1)
    half = wb / 2.0 - (wb - wt) / 2.0 * t
    m = (np.abs(L.xx - cx) < half) & (L.yy >= top) & (L.yy < base)
    u = (L.xx - cx) / np.maximum(half, 0.5)
    idx = 5 - band(u, (-0.55, 0.5)) * 1 - (u > 0.5) * 1
    idx = idx - ((L.yy - top) / h > 0.82)
    wl = [(int(round(cx - ww / 2.0)), top + dy, ww, wh, lit) for (dy, ww, wh, lit) in wins]
    dr = None if door is None else (int(round(cx - door[0] / 2.0)), base, door[0], door[1])
    idx = masonry(L, m, idx, seed, top, course=4, blen=(3, 6), edges=stone_edges(L, m, cx, half, wl, dr))
    idx = stains(L, m, idx, wl, seed + 1)
    idx = idx - 2 * (L.yy < top + 3)
    glow = glow_of(L, wl, m)
    paint(L, m, idx, BWALL, WALL_W, glow)
    rim_light(L, m, BRIM, upto=base - 10, skip=glow)
    for (x, y, ww, wh, lit) in wl:
        deep_window(L, x, y, ww, wh, lit, shutters=False)
    if door is not None:
        stone_door(L, int(round(cx - door[0] / 2.0)), base, door[0], door[1], door[2])
    # 收帆台
    sy = int(round(base - h * stage))
    hs = wb / 2.0 - (wb - wt) / 2.0 * stage
    pw = hs + 6
    L.rect(cx - pw, sy, cx + pw, sy + 2, WHEAT[2])
    L.rect(cx - pw, sy, cx + pw, sy + 1, WHEAT[4])
    L.rect(cx - pw, sy - 6, cx + pw, sy - 5, WHEAT[3])
    for px_ in (cx - pw, cx - pw + 3, cx + pw - 4, cx + pw - 1):
        L.rect(px_, sy - 5, px_ + 1, sy, WHEAT[2])
    for sgn in (-1, 1):
        for (px_, py_) in line4(cx + sgn * (pw - 1), sy + 2, cx + sgn * (hs - 1), sy + 9):
            L.px(px_, py_, TIMBER[2])
            L.px(px_, py_ + 1, TIMBER[1])
    # 木帽
    cw = wt / 2.0 + 3
    cap = ellipse(L, cx, top + 1, cw, 9) & (L.yy < top + 2)
    cidx = 5 - band((L.xx - cx) / cw, (-0.5, 0.0, 0.5))
    cidx = tiles(L, cap, cidx, seed + 3, top - 9, course=3, tlen=(3, 5))
    paint(L, cap, cidx, TERRA)
    rim_light(L, cap, TERRA[6])
    L.rect(cx - cw, top + 1, cx + cw, top + 3, TIMBER[1])
    L.rect(cx - cw, top + 1, cx + cw, top + 2, TIMBER[3])
    hub = (cx, top - 2)
    L.put(ellipse(L, hub[0], hub[1], 3.2, 3.2), TIMBER[1])
    return hub, {"cx": cx, "top": top - 9, "base": base, "tip": (cx, top - 9), "rw": cw, "cap_h": 9, "w": wb}


def dutch_sails(L: Layer, cx, cy, r, ang, haze=0.0, lattice=True):
    """荷兰风车的四片叶片：一根木头的叶杆，杆的一侧是木格子框（外边一根长条、横档一根根），框里绷着帆布；
    帆布朝余晖（左边）的那几片亮一档。"""
    sw = max(3.0, r * 0.26)
    for i in range(4):
        a = ang + i * math.pi / 2
        ca, sa = math.cos(a), math.sin(a)
        nx, ny = -sa, ca                                    # 帆框在叶杆的这一侧（逆着转的方向）
        r0, r1 = r * 0.2, r
        P = [(cx + ca * r0, cy + sa * r0), (cx + ca * r1, cy + sa * r1),
             (cx + ca * r1 + nx * sw, cy + sa * r1 + ny * sw), (cx + ca * r0 + nx * sw * 0.8, cy + sa * r0 + ny * sw * 0.8)]
        cm = poly_mask(L, P)
        facing = (ca + nx * 0.5) < -0.1
        L.put(cm, SAIL[3] if facing else SAIL[2], 235)
        L.put(cm & (((L.xx - cx) * ca + (L.yy - cy) * sa) > r * 0.62), SAIL[4] if facing else SAIL[3], 235)
        # 木格子：外边一根长条 + 横档
        for (px_, py_) in line4(cx + ca * r0 + nx * (sw - 0.5), cy + sa * r0 + ny * (sw - 0.5), cx + ca * r1 + nx * (sw - 0.5),
                                cy + sa * r1 + ny * (sw - 0.5)):
            L.px(px_, py_, WHEAT[2])
        if lattice:
            step = 4.0 if r >= 20 else 3.5
            s = r0 + step
            while s < r1 - 1:
                for (px_, py_) in line4(cx + ca * s, cy + sa * s, cx + ca * s + nx * (sw - 0.5), cy + sa * s + ny * (sw - 0.5)):
                    L.px(px_, py_, WHEAT[2])
                s += step
        L.px(cx + ca * r1 + nx * (sw - 0.5), cy + sa * r1 + ny * (sw - 0.5), WHEAT[3])
    for i in range(4):                                       # 叶杆（压在帆布上）
        a = ang + i * math.pi / 2
        ca, sa = math.cos(a), math.sin(a)
        for (px_, py_) in line4(cx - 0.5 + ca * 2, cy - 0.5 + sa * 2, cx - 0.5 + ca * (r + 1), cy - 0.5 + sa * (r + 1)):
            L.px(px_, py_, TIMBER[2])
            if r >= 20:
                L.px(px_ + (1 if abs(sa) > 0.7 else 0), py_ + (1 if abs(sa) <= 0.7 else 0), TIMBER[1])
    hm = ellipse(L, cx, cy, 2.6 if r >= 20 else 1.8, 2.6 if r >= 20 else 1.8)
    L.put(hm, WHEAT[3])
    L.put(hm & (L.xx < cx), WHEAT[5])
    if haze:
        hazed(L, haze)


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


# 后面那排（在晨后面，跟地面一起动）。种类：
#   spire = 石砌细塔 + 尖顶 + 旗；keep = 城堡塔（雉堞护墙，尖顶从里面长出来）+ 旗；
#   house = 半木结构的窄房子（山墙朝外）；mill = 荷兰塔式风车（叶片是动画）
BACK = [
    ("keep", 22, 213, dict(w=22, h=72, cap_h=40, roof="slate", flag=True)),
    ("spire", 62, 209, dict(w=14, h=112, cap_h=44, roof="terra", flag=True)),
    ("house", 150, 214, dict(w=30, floors=2, roof_h=22, roof="terra")),
    ("spire", 202, 210, dict(w=12, h=92, cap_h=36, roof="slate")),
    ("mill", 262, 214, dict(wb=26, wt=17, h=74, r=22)),
    ("house", 386, 214, dict(w=26, floors=2, roof_h=20, roof="slate")),
    ("keep", 424, 210, dict(w=20, h=100, cap_h=44, roof="terra", flag=True)),
    ("spire", 470, 210, dict(w=14, h=126, cap_h=46, roof="slate", flag=True)),
    ("house", 522, 214, dict(w=32, floors=3, roof_h=24, roof="terra")),
    ("mill", 594, 213, dict(wb=24, wt=16, h=82, r=20)),
    ("house", 648, 214, dict(w=28, floors=2, roof_h=22, roof="slate")),
    ("spire", 738, 208, dict(w=16, h=106, cap_h=40, roof="terra", flag=True)),
    ("house", 794, 214, dict(w=26, floors=2, roof_h=20, roof="slate")),
    ("house", 1160, 214, dict(w=30, floors=3, roof_h=24, roof="terra")),
    ("keep", 1210, 213, dict(w=22, h=68, cap_h=40, roof="slate", flag=True)),
    ("spire", 1254, 208, dict(w=14, h=118, cap_h=44, roof="terra", flag=True)),
    ("house", 1314, 214, dict(w=28, floors=2, roof_h=20, roof="terra")),
    ("spire", 1412, 210, dict(w=14, h=102, cap_h=40, roof="slate", flag=True)),
    ("mill", 1670, 214, dict(wb=24, wt=16, h=78, r=20)),
    ("spire", 1710, 208, dict(w=14, h=122, cap_h=44, roof="slate", flag=True)),
    ("house", 1748, 214, dict(w=26, floors=2, roof_h=20, roof="terra")),
]
MILL = (1084, 210, 40, 26, 104, 46)   # 广场后面的大风车：(x, 塔脚, 底宽, 顶宽, 高, 叶片半径)
ROPES = [(6, 7, 10, 30, 8), (14, 15, 8, 28, 8)]   # 两座塔之间的彩旗绳：(左, 右, 左边离尖多远, 右边离尖多远, 下垂)


def tower_wins(h, rng, lit_p=0.6, big=6):
    out = []
    dy = 14
    while dy < h - 36:
        out.append((dy, big, 10 if big == 6 else 8, bool(rng.random() < lit_p)))
        dy += int(rng.integers(26, 32))
    return out


def draw_building(L, kind, x, base, o, rng, seed, plain=False):
    if kind in ("spire", "keep"):
        wins = o.get("wins") or tower_wins(o["h"], rng, big=6 if o["w"] >= 16 else 5)
        if plain:
            wins = [(dy, 3, 4, lit) for (dy, ww, wh, lit) in wins]
        door = None if plain else (10, 20, bool(rng.random() < 0.5))
        return cyl_tower_v2(L, x, base, o["w"], o["h"], o["cap_h"], roof=o["roof"], wins=wins, door=door, seed=seed,
                            crenel=(kind == "keep"), plain=plain)
    if kind == "house":
        return house_v2(L, x, base, o["w"], o["floors"], o["roof_h"], o["roof"], seed,
                        lit=tuple(bool(rng.random() < 0.72) for _ in range(3)), plain=plain,
                        door_lit=bool(rng.random() < 0.4))
    if kind == "mill":
        h = o["h"]
        wins = [(int(h * 0.28), 5, 8, True), (int(h * 0.72), 5, 8, bool(rng.random() < 0.5))]
        if plain:
            wins = [(dy, 3, 4, lit) for (dy, ww, wh, lit) in wins]
        hub, info = mill_v2(L, x, base, o["wb"], o["wt"], h, seed, wins=wins, door=None if plain else (10, 20, True),
                            plain=plain)
        info["hub"] = hub
        return info


def feet_of(kind, x, base, o):
    w = o.get("w") or o.get("wb")
    return (x, base, w + 4)


# ======================================================================= 远处那排（视差 0.72）
def build_far():
    rng = np.random.default_rng(77)
    items = []
    x = 10.0
    while x < FAR_W - 6:
        k = rng.choice(["spire", "spire", "keep", "house", "mill"])
        base = int(rng.uniform(202, 207))
        if k == "spire":
            h = int(rng.uniform(34, 70))
            o = dict(w=int(rng.choice([8, 9, 10])), h=h, cap_h=int(h * rng.uniform(0.38, 0.5)), roof=str(rng.choice(["slate", "terra"])))
        elif k == "keep":
            h = int(rng.uniform(30, 48))
            o = dict(w=12, h=h, cap_h=int(h * 0.45), roof=str(rng.choice(["slate", "terra"])))
        elif k == "house":
            o = dict(w=int(rng.choice([16, 18])), floors=int(rng.choice([1, 2])), roof_h=14, roof=str(rng.choice(["slate", "terra"])))
        else:
            o = dict(wb=14, wt=9, h=int(rng.uniform(36, 48)), r=11)
        items.append((str(k), x, base, o))
        x += rng.uniform(40, 80)
    heaps = [(ix, b + 6, (o.get("w") or o["wb"]) * 2.4 + 12, max(4, 10 + rng.uniform(-2, 3))) for (k, ix, b, o) in items]
    F = Layer(FAR_W, H)
    F.over(mound_cloud(FAR_W, heaps, 3, deck=207, lift=0.03))
    feet = []
    for i, (k, x, base, o) in enumerate(items):
        P = piece(x - 30, base - 140, x + 30, base + 8)
        info = draw_building(P, k, x, base, o, rng, 900 + i, plain=True)
        F.over(hazed(P, 0.4))
        feet.append(feet_of(k, x, base, o))
        if k == "mill":
            hx, hy = info["hub"]
            r = o["r"]
            anim(f"far_mill_{i}", "town_far", (hx - r - 4, hy - r - 4, hx + r + 5, hy + r + 5), 16,
                 lambda L, kk, hx=hx, hy=hy, r=r: dutch_sails(L, hx, hy, r, 0.3 + (math.pi / 2) * kk / 16, haze=0.4,
                                                             lattice=False), off=int(rng.integers(0, 16)))
    F.over(foot_tufts(FAR_W, feet, 4, lift=0.03))
    despeckle(F)
    return F


# ======================================================================= 后面那排（视差 1，在晨后面）
def build_back():
    rng = np.random.default_rng(31)
    B = Layer(W, H)
    heaps = []
    for (k, x, base, o) in BACK:
        w = o.get("w") or o.get("wb")
        heaps.append((x, 218, w * 2.4 + 16, max(5, 218 - base + 8)))
    heaps.append((MILL[0], 218, 100, 18))
    B.over(mound_cloud(W, heaps, 1, deck=212))
    info = []
    feet = []
    for i, (k, x, base, o) in enumerate(BACK):
        P = piece(x - 40, base - 190, x + 40, base + 8)
        T = draw_building(P, k, x, base, o, rng, 100 + i * 7)
        B.over(P)
        info.append(T)
        feet.append(feet_of(k, x, base, o))
        if o.get("flag"):
            fx, fy = int(T["tip"][0]), int(T["tip"][1])
            P = piece(fx - 3, fy - 18, fx + 4, fy + 3)
            px_, py_ = flagpole(P, fx, fy, 12)
            B.over(P)
            ln = int(rng.integers(12, 17))
            anim(f"flag_{i}", "town_back", (px_, py_ - 2, px_ + ln + 6, py_ + 12), 12,
                 lambda L, kk, px_=px_, py_=py_, ln=ln: pennant(L, px_, py_ + 1, ln, 5, kk, 12), off=int(rng.integers(0, 12)))
        if k == "mill":
            hx, hy = T["hub"]
            r = o["r"]
            anim(f"mill_{i}", "town_back", (hx - r - 4, hy - r - 4, hx + r + 5, hy + r + 5), 16,
                 lambda L, kk, hx=hx, hy=hy, r=r: dutch_sails(L, hx, hy, r, 0.4 + (math.pi / 2) * kk / 16),
                 off=int(rng.integers(0, 16)))
    # 广场后面的大风车
    mx_, mb, wb, wt, mh, mr = MILL
    P = piece(mx_ - 60, mb - mh - 40, mx_ + 60, mb + 8)
    hub, M = mill_v2(P, mx_, mb, wb, wt, mh, 79, stage=0.42,
                     wins=[(22, 6, 10, True), (50, 6, 10, False), (80, 6, 9, True)], door=(12, 24, True))
    B.over(P)
    M["hub"] = hub
    feet.append((mx_, mb, wb + 4))
    anim("mill_rotor", "town_back", (hub[0] - mr - 5, hub[1] - mr - 5, hub[0] + mr + 6, hub[1] + mr + 6), 24,
         lambda L, k: dutch_sails(L, hub[0], hub[1], mr, 0.25 + (math.pi / 2) * k / 24))
    # 彩旗绳
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
#   11-01 改：下截石砌圆塔是住的那层（剖开看得到屋里），上面挑出一层半木结构的楼（灰泥 + 深色木框架，下面一排托梁），
#   再上面石板瓦的尖顶（开一扇小老虎窗），尖上挂旗（房屋物件 townroom_flag，100ms 一帧）。
L_CX = LW // 2
L_BODY = (22, 122)        # 下截石塔的左右
L_TAPER = 0
L_ROOF = 136              # 下截的上沿（上面一层从这里挑出去）
L_UP = (16, 128, 110)     # 上面那层：左右、上沿
L_CEIL = (146, 151)       # 剖开的天花板（楼板）
L_FLOOR = LH - 1
L_WALL = 5
L_DESK = (58, 88)
L_BED = (92, 118)
L_WIN = (63, 81, 160, 186)


def lodging_exterior():
    E = Layer(LW, LH)
    x0, x1 = L_BODY
    base = LH
    half = (x1 - x0) / 2.0
    plinth(E, L_CX, base, half, h=9, seed=301)
    m = (np.abs(E.xx - L_CX) < half) & (E.yy >= L_ROOF) & (E.yy < base - 9)
    wins = [(46, 160, 8, 14, True), (90, 160, 8, 14, True)]
    idx = flat_cyl_idx(E, L_CX, half, hi=4)
    door_r = (L_DOOR - 7, base, 14, 30)
    idx = masonry(E, m, idx, 303, L_ROOF, course=4, blen=(5, 8), var=0.06, edges=stone_edges(E, m, L_CX, half, wins, door_r))
    idx = stains(E, m, idx, wins, 304)
    idx = idx - 1 * (E.yy < L_ROOF + 4)
    glow = glow_of(E, wins, m)
    paint(E, m, idx, BWALL, WALL_W, glow)
    rim_light(E, m, BWALL[5], skip=glow)
    moss(E, (np.abs(E.xx - L_CX) < half + 2) & (E.yy >= base - 9), base, 305, n=2)
    for (x, y, w, h, lit) in wins:
        deep_window(E, x, y, w, h, lit, shutters=True, sill=False)
        flower_box(E, x, y + h, w)
    stone_door(E, L_DOOR - 7, base, 14, 30, True)
    # 门上的条纹雨棚 + 门边的灯
    aw = poly_mask(E, [(L_DOOR - 11, base - 35), (L_DOOR + 11, base - 35), (L_DOOR + 13, base - 31), (L_DOOR + 8, base - 29),
                       (L_DOOR + 2, base - 30), (L_DOOR - 4, base - 29), (L_DOOR - 10, base - 31)])
    stripe = (np.floor((E.xx - (L_DOOR - 11)) / 3).astype(int) % 2) == 0
    E.put(aw, SAIL[3])
    E.put(aw & stripe, BWALL[6])
    E.put(aw & (E.xx > L_DOOR + 6), SAIL[2])
    E.put(aw & stripe & (E.xx > L_DOOR + 6), BWALL[4])
    E.rect(L_DOOR - 12, base - 36, L_DOOR + 12, base - 35, TIMBER[2])
    lamp_post_hang(E, L_DOOR + 13, base - 38)
    # 托梁：一排小木托从石塔边上伸出去，托住上面那层
    ux0, ux1, uy = L_UP
    X, Y = _xy(E)
    dist = np.abs(E.xx - L_CX) - half
    cb = (dist > 0) & (E.xx >= ux0) & (E.xx < ux1) & (E.yy >= L_ROOF) & (E.yy < L_ROOF + 3 - dist / 2.5) & (np.mod(X - ux0, 4) < 2)
    E.put(cb, TIMBER[2])
    E.put(cb & (E.yy < L_ROOF + 1), TIMBER[3])
    # 上面那层：灰泥 + 木框架（圆的，灰泥也左亮右暗）
    um = (E.xx >= ux0) & (E.xx < ux1) & (E.yy >= uy) & (E.yy < L_ROOF)
    uh = (ux1 - ux0) / 2.0
    uwins = [(30, uy + 7, 6, 10, True), (69, uy + 7, 6, 10, False), (100, uy + 7, 6, 10, True)]
    uidx = flat_cyl_idx(E, L_CX, uh, hi=4)
    uidx = uidx - 1 * (E.yy < uy + 3)
    uglow = glow_of(E, uwins, um)
    paint(E, um, uidx, PLASTER, PLASTER_W, uglow)
    tm = um & ((E.yy >= L_ROOF - 2) | (E.yy < uy + 1) | (E.xx < ux0 + 2) | (E.xx >= ux1 - 2))
    for (wx, wy, ww, wh, l_) in uwins:
        tm |= um & (((E.xx >= wx - 3) & (E.xx < wx - 1)) | ((E.xx >= wx + ww + 1) & (E.xx < wx + ww + 3)))
    for (sx, ex) in ((ux0 + 12, ux0 + 20), (L_CX - 6, L_CX + 2), (L_CX + 14, L_CX + 22), (ux1 - 12, ux1 - 20)):
        for (px_, py_) in line4(sx, L_ROOF - 3, ex, uy + 2):
            tm |= um & (X == px_) & (Y == py_)
            tm |= um & (X == px_ + 1) & (Y == py_)
    tidx = flat_cyl_idx(E, L_CX, uh, hi=3)
    paint(E, tm, tidx, TIMBER)
    E.rect(ux0, L_ROOF - 1, ux1, L_ROOF, TIMBER[0])
    for (wx, wy, ww, wh, l_) in uwins:
        deep_window(E, wx, wy, ww, wh, l_, shutters=True, sill=False, frame_pal=PLASTER)
    # 尖顶（石板瓦）+ 老虎窗 + 旗杆
    R = Layer(LW, LH)
    tx, ty, rm = cone_roof(R, L_CX, uy, uh, 82, SLATE, 307, flare=3.0, expo=1.55, flat=True)
    dx, dy = L_CX + 16, uy - 30                            # 老虎窗：一小间带三角顶的窗，从坡上伸出来
    dm = (R.xx >= dx) & (R.xx < dx + 10) & (R.yy >= dy) & (R.yy < dy + 11)
    paint(R, dm, np.full(dm.shape, 4) - (R.xx >= dx + 8), PLASTER)
    deep_window(R, dx + 3, dy + 2, 4, 7, True, sill=False, frame_pal=PLASTER, cross=False)
    gr = poly_mask(R, [(dx - 2, dy + 1), (dx + 5, dy - 6), (dx + 12, dy + 1)])
    paint(R, gr, np.full(gr.shape, 4) - (R.xx >= dx + 5), SLATE)
    R.put(gr & ~np.roll(gr, 1, axis=0), SLATE[6])
    R.rect(dx - 1, dy + 11, dx + 11, dy + 12, SLATE[1])
    E.over(R)
    fx, fy = flagpole(E, int(tx), int(ty), 12)
    return E, (fx, fy)


def lodging():
    E, flag = lodging_exterior()
    back = Layer(LW, LH)
    back.a[:] = E.a
    front = Layer(LW, LH)
    front.a[:] = E.a
    front.a[front.yy < L_CEIL[0]] = 0
    x0, x1 = L_BODY
    base = LH
    half = (x1 - x0) / 2.0
    body = ((np.abs(back.xx - L_CX) < half) & (back.yy >= L_ROOF) & (back.yy < base))
    # ---- 屋里（back 的剖面那一块）
    ix0, ix1 = x0 + L_WALL, x1 - L_WALL
    inner = (back.xx >= ix0) & (back.xx < ix1) & (back.yy >= L_CEIL[1]) & (back.yy < base)
    cut_w = body & (back.yy >= L_CEIL[0]) & ~inner
    # 剖开的墙：石块的切面（一样砌着石缝）；天花板是上面那层的木楼板（板 + 一根根搁栅的头）
    cw = cut_w & (back.yy >= L_CEIL[1])
    cidx = masonry(back, cw, np.full(cw.shape, 5), 311, L_CEIL[1], course=4, blen=(3, 5), var=0.3)
    paint(back, cw, cidx, BWALL)
    edge_in = cw & (np.roll(inner, 1, 1) | np.roll(inner, -1, 1))
    back.put(edge_in, BWALL[2])
    ceil = cut_w & (back.yy < L_CEIL[1])
    back.put(ceil, WHEAT[2])
    back.put(ceil & (back.yy < L_CEIL[0] + 1), WHEAT[4])
    back.put(ceil & (back.yy >= L_CEIL[1] - 1), WHEAT[1])
    X_, Y_ = _xy(back)
    back.put(ceil & (np.mod(X_ - x0, 9) < 3) & (back.yy >= L_CEIL[0] + 2), TIMBER[2])
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
    # 墙裙：下半截一圈竖的木板（板缝长短不一地错开），上沿一根亮的压条；离灯近的板亮一档
    ws = inner & (back.yy >= base - 26) & (back.yy < base - 9)
    widx = np.where(d < 34, 2, 1)                                  # 比桌子、床暗两档（家具要跳出来）
    X_, Y_ = _xy(back)
    rng_w = np.random.default_rng(313)
    sx = ix0 + 2
    while sx < ix1 - 2:
        widx = np.where(ws & (X_ == sx), widx - 1, widx)
        sx += int(rng_w.integers(5, 9))
    paint(back, ws, widx, WHEAT)
    back.put(ws & (back.yy < base - 25), WHEAT[3])
    back.put(ws & (back.yy >= base - 25) & (back.yy < base - 24), WHEAT[1])
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
    back.rect(dx0 + 6, dt - 1, dx0 + 18, dt, BWALL[6])                # 摊开的纸
    back.rect(dx0 + 9, dt - 2, dx0 + 20, dt - 1, BWALL[5])
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
    back.put(q, BWALL[5])
    back.put(q & (back.yy < bt + 1), BWALL[6])
    back.put(q & (back.yy >= bt + 5), BWALL[3])
    back.put(q & (np.abs(back.xx - (bx0 + 10.5)) < 1.6) & (back.yy >= bt + 1), DOOR[3])
    pl = ellipse(back, bx1 - 9, bt - 1, 5, 2.6)
    back.put(pl, BWALL[6])
    back.put(pl & (back.yy > bt - 0.5), BWALL[4])
    # 床上面一块搁板：三个罐子；窗边挂一束晒干的麦穗
    sy = 174
    back.rect(bx0 + 2, sy, bx1 - 3, sy + 2, WHEAT[3])
    back.rect(bx0 + 2, sy, bx1 - 3, sy + 1, WHEAT[5])
    for (jx, jw, jh, col) in ((bx0 + 4, 5, 7, DOOR[2]), (bx0 + 11, 4, 5, WHEAT[4]), (bx0 + 17, 5, 8, FLOWER[0])):
        back.rect(jx, sy - jh, jx + jw, sy, col)
        back.rect(jx, sy - jh, jx + 1, sy, BWALL[6])
        back.rect(jx + 1, sy - jh - 1, jx + jw - 1, sy - jh, WHEAT[2])
    back.rect(49, L_CEIL[1], 50, 160, WHEAT[2])
    back.put(poly_mask(back, [(47, 160), (52, 160), (54, 172), (45, 172)]), WHEAT[4])
    back.put(poly_mask(back, [(49.5, 160), (52, 160), (54, 172), (50, 172)]), WHEAT[3])
    # ---- 光：桌上油灯的暖光（两圈固定的半透明，只在屋里）
    light = Layer(LW, LH)
    dl = np.hypot((light.xx - lamp[0]) / 1.35, light.yy - (dt - 6))
    light.put(inner & (dl < 46), LAMP[2], 26)
    light.put(inner & (dl < 22), LAMP[2], 44)
    tufts = foot_tufts(LW, [(L_CX, base - 1, x1 - x0 + 2)], 8, lift=0.0)
    back.over(tufts)
    despeckle(back)
    despeckle(front)
    # 尖上的旗（房屋物件，100ms 一帧）
    fx, fy = flag
    fl = []
    for k in range(12):
        Lf = piece(fx, fy - 2, fx + 22, fy + 12)
        pennant(Lf, fx, fy + 1, 18, 6, k, 12)
        despeckle(Lf)
        fl.append(Lf)
    return back, front, light, view, fl


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
    over = {after: {"id": f"cloud_{src}_over", "img": f"res://art/cloud_town/cloud_{src}_over.png", "scroll": sc, "y": 0,
                    "tile": True, "drift": drift} for (after, src, dy, sc, drift) in INTERLEAVE}
    dk = deck_layers()
    layers += [{"id": "town_far", "img": "res://art/cloud_town/town_far.png", "scroll": FAR_SC, "y": 0}, dk["town_far"], over["town_far"],
               dk["cloud_midfar_over"],
               {"id": "town_back", "img": "res://art/cloud_town/town_back.png", "scroll": 1.0, "y": 0}, dk["town_back"], over["town_back"],
               {"id": "town_main", "img": "res://art/cloud_town/town_main.png", "scroll": 1.0, "y": 0}, dk["town_main"],
               {"id": "front", "img": "res://art/cloud/front.png", "scroll": 1.4, "y": 0, "tile": True, "front": True}]
    hx0 = LODGE - LW // 2
    return {
        "size": [ROOM_W, H], "origin": list(ORIGIN), "env": "cloud", "bg": ["#1d1530", "#4a3550"],
        "layers": layers,
        "ground": GROUND, "walk": [16, W - 16], "cam": [0, W],
        "walk_when": [{"need": ["final_e3_walk"], "not": ["final_e3_seed_todo", "final_e3_seed_done"],
                       "walk": [16, DECK_WALK_END], "cam": [0, ROOM_W],
                       "_note": "云台（小镇右边那一屏）只在结局三「走一圈」那天开放：之前和之后晨走不过去、镜头也不往那边看"}],
        "markers": {
            "town_landing": 262, "town_helper": 304, "town_basket": 598, "town_plaza_side": 862, "town_fountain": FOUNTAIN,
            "town_back_side": 1052, "town_crowd": 1116, "town_bench": BENCHES[1] + 15, "town_far_side": 1250,
            "town_bed": BED_X + 30, "town_lodging": hx0 + L_DOOR, "town_deck": PIER[0] - 40, "town_deck_end": DECK_END,
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


LODGE_FLAG = [0, 0]


def room_json():
    return {
        "kind": "house", "host": "town", "x": LODGE, "size": [LW, LH],
        "back": "res://art/cloud_town/lodge_back.png", "front": "res://art/cloud_town/lodge_front.png",
        "light": "res://art/cloud_town/lodge_light.png", "view": "res://art/cloud_town/lodge_view.png",
        "floor": L_FLOOR, "walk": [L_BODY[0] + L_WALL + 6, L_BODY[1] - L_WALL - 6], "door": L_DOOR,
        "markers": {"townroom_desk": 48, "townroom_door": L_DOOR},
        "objects": {"townroom_flag": {"img": "res://art/cloud_town/anim/lodge_flag.png", "x": LODGE_FLAG[0], "y": LODGE_FLAG[1],
                                      "frames": 12, "states": {"wave": [0, 11]}, "default": "wave"}},
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
        return sx + cl - int(round(cl * (1 - sc))) - int(c.get("x", 0))

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
            if a[y, x, 3] > 0 and any(c[3] > 0 for c in nb):
                nb = [c for c in nb if c[3] > 0]                # 不透明的点只换成旁边不透明的颜色：轮廓不会被啃掉一格
            keys = [tuple(int(v) for v in c) for c in nb]
            best = max(set(keys), key=keys.count)
            a[y, x] = best
    return a


# ======================================================================= 晨和身后墙的亮度差
def _lum(c):
    return c[..., 0] * 0.299 + c[..., 1] * 0.587 + c[..., 2] * 0.114


def chen_hair():
    """晨头发的像素（帧里最上面 20 行、最亮的那些：白头发）和它们的平均亮度"""
    C, _, _ = chen_ref(0)
    a = C.a.astype(np.float32)
    lm = _lum(a)
    op = a[..., 3] > 0
    top = np.zeros(op.shape, bool)
    top[:24] = True
    sel = op & top & (lm >= np.percentile(lm[op & top], 60))
    return sel, float(lm[sel].mean())


CONTRAST_SPOTS = {"住处的塔": lambda: LODGE - 20, "广场的大风车": lambda: MILL[0], "半木房": lambda: 1160}
NAMES = {"spire": "尖塔", "keep": "城堡塔", "house": "半木房", "mill": "风车"}
for _i, (_k, _x, _b, _o) in enumerate(BACK):                     # 第四轮：每栋都量（晨站在那栋正前面）
    CONTRAST_SPOTS[f"{_i:02d} {NAMES[_k]} x{_x}"] = (lambda x=_x: int(np.clip(x, 16, W - 16)))


def contrast(S: "Scene"):
    """晨站在三栋房子跟前：头发的平均亮度 − 头发正后面那块墙（不画晨时）的平均亮度"""
    sel, hl = chen_hair()
    out = {}
    for name, fx in CONTRAST_SPOTS.items():
        x = int(fx())
        cl = int(np.clip(x - 240, 0, W - 480))
        img = S.render(cl).astype(np.float32)
        ox, oy = x - cl - 28, GROUND - 56
        ys, xs = np.nonzero(sel)
        wall = _lum(img[ys + oy, xs + ox]).mean()
        out[name] = (hl, float(wall), hl - float(wall))
    return out


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
    lb, lf, ll, lv, lrot = lodging_v4()                              # s7 定稿的住处：圆柱塔身 + 圆锥顶 + 塔脚的云和雾
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
    dfar = build_deck_far(far)                                       # 云台（小镇右边加的一屏）：接在三张原图右边
    DECK_FAR_X[0] = dfar.ox
    sv(dfar, "art/cloud_town/deck_far.png")
    sv(build_deck_back(back[0]), "art/cloud_town/deck_back.png")
    sv(build_deck_main(main), "art/cloud_town/deck_main.png")
    sv(build_deck_dim(), "art/cloud_town/deck_dim.png", fix=False)
    sv(build_title_descent(), "art/cloud_town/title_descent.png", fix=False)
    sv(ship_img(), "art/cloud_town/ship_parked.png", fix=False)        # 作者的飞船原图，一个像素都不动
    bed = np.concatenate([flower_bed(0).a, flower_bed(1).a], 1)
    sv(bed, "art/cloud_town/town_bed.png")
    sv(np.zeros((1, 1, 4), np.uint8), "art/cloud_town/empty.png")
    sv(lb, "art/cloud_town/lodge_back.png")
    sv(lf, "art/cloud_town/lodge_front.png")
    sv(ll, "art/cloud_town/lodge_light.png")
    sv(lv, "art/cloud_town/lodge_view.png")
    for (after, src, dy, sc, drift) in INTERLEAVE:                    # 插在建筑层之间的云：作者原图水平翻过来、往下挪 dy 行（原图不动）
        im = np.asarray(Image.open(ROOT / "art" / "cloud" / (src + ".png")).convert("RGBA"))[:, ::-1]
        sh = np.zeros_like(im)
        sh[dy:] = im[:im.shape[0] - dy]
        sv(sh, f"art/cloud_town/cloud_{src}_over.png", fix=False)
    sv(np.concatenate([j.a for j in lrot], 1), "art/cloud_town/anim/lodge_flag.png")
    LODGE_FLAG[:] = [lrot[0].ox, lrot[0].oy]
    for a in ANIMS:
        sv(np.concatenate([f.a for f in a["_frames"]], 1), f"art/cloud_town/anim/{a['_name']}.png")
    save_json(town_json(ANIMS), "art/town/room.json",
              "结局三 · 云层上的风帆小镇。tools/cloud_town_art.py 生成，别手改。天和云是作者 art/cloud/ 的原图（照 scenes/cloud_test.tscn 的视差和漂移），"
              "小镇（远塔、塔、地面）在 art/cloud_town/。风车、帆、水车、喷泉的动画由 scripts/cloud_town.gd 挂到层上播（100ms 一帧）。"
              "从左到右：木停机台（飞船）→ 石头路（倒了的篮子）→ 湿石台广场（喷泉、水车、大风车、长椅）→ 花圃和龙头 → 晨住的塔（town_room）→ 云台（纯云 + 木栈桥，结局三走一圈那天才开放，见 walk_when / cam）。")
    save_json(room_json(), "art/town_room/room.json",
              "结局三 · 晨在云层小镇暂住的屋子（剖面小屋，在 town 里；前墙进屋淡出）。tools/cloud_town_art.py 生成，别手改。"
              "一座风车塔：下截是住的那层（左边门、中间书桌，窗在桌子上面透出外面的天和云、右边床），淡蓝裙檐上一截细塔 + 尖顶，小风车是动的。")
    print("写好", len(out), "张图")
    check(out)
    return out


# ======================================================================= 第三轮样稿（11-01）：只做晨住的塔
#   作者：「墙仍然没有质感」「整个小镇都没有融入背景的氛围感」。主对话：墙像贴纸、颜色和天脱节、塔脚硬切。
#   做法照小奥斯卡色块派：色块是光照切出来的。先算一张连续的光（天光从上面来、冷紫；云的反光从下面来、偏粉；
#   地平线的粉光从左边低处来；窗里的灯往外晕、往下照窗台），放到三角网格上分段线性（块边是直线段，像剪纸），
#   再按 OKLab 一档档量化（亮度一档 STEP_L，色相一档 8°）。颜色全从作者天和云里取：阴面是天的深紫蓝，亮面是偏粉的灰紫。
#   材质不画缝：墙面中部是抹灰，墙角、窗边、门边、墙脚和几处剥落的地方露出石头 —— 石头是不规则的成片色块（各块只比
#   抹灰暗一档或一样），窗台下拖着淡淡的雨痕。塔脚前面压一排云团，贴地一层薄雾。
#   这一版只出样稿给作者看（--sample），不写 art/、不改 room.json；过了再推到别的房子。
sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.light import polygonal, smooth_noise   # noqa: E402
from oscarkit.palette import oklab_to_srgb            # noqa: E402
from oscarkit.measure import srgb_to_oklab            # noqa: E402

STEP_L = 0.032          # 光一档
MAT_STEP = 0.05         # 材质（石块、雨痕）一档：比光的档大一点，石头才读得出来
HUE_STEP = 8.0


def lch_rgb(L, C, h):
    hr = np.radians(h)
    lab = np.stack([L, C * np.cos(hr), C * np.sin(hr)], -1)
    return oklab_to_srgb(lab.reshape(-1, 3)).reshape(np.shape(L) + (3,))


def lch_hex(L, C, h):
    return "#%02x%02x%02x" % tuple(int(v) for v in lch_rgb(np.array(L), np.array(C), np.array(h)))


# 塔的颜色（OKLCh，色相是 OKLab 的角度：天顶 −72°、云 −76° ~ −22°、地平线粉 −3°）
PW = [lch_hex(0.20 + 0.055 * i, 0.045 + 0.003 * i, -62 + 7 * i) for i in range(7)]   # 窗套、门套、窗台
TIMBER4 = [lch_hex(0.16 + 0.045 * i, 0.032, -40 + 4 * i) for i in range(5)]          # 木梁：深紫褐，不是黑
PINK_RIM = lch_hex(0.54, 0.075, -8)                                                  # 朝地平线那条边


def stone_cells(L: Layer, seed, sx=(4, 9), sy=(3, 5), aniso=1.7, coords=None):
    """不规则的石块：一行行错开撒点（行高、点距都随机），按「横向压扁」的距离分成泰森多边形，每块一个编号。
    coords = (横, 竖) 两张坐标图（圆柱上用展开的横坐标和「同一圈」的高度：石块靠两边变窄、层是弯的）；不给就用画布坐标"""
    XX, YY = (L.xx, L.yy) if coords is None else coords
    rng = np.random.default_rng(seed)
    pts = []
    y = YY.min() - rng.uniform(0, sy[1])
    while y < YY.max() + sy[1]:
        x = XX.min() - rng.uniform(0, sx[1])
        while x < XX.max() + sx[1]:
            pts.append((x + rng.uniform(-1, 1), y + rng.uniform(-0.8, 0.8)))
            x += rng.uniform(*sx)
        y += rng.uniform(*sy)
    P = np.array(pts)
    best = np.full(L.xx.shape, 1e9)
    cid = np.zeros(L.xx.shape, int)
    for i, (px_, py_) in enumerate(P):
        d = ((XX - px_) / aniso) ** 2 + (YY - py_) ** 2
        upd = d < best
        best[upd] = d[upd]
        cid[upd] = i
    return cid, len(P)


def atmos_paint(L: Layer, m, Lf, Cf, hf, k, cell=(16, 14), seed=0):
    """把连续的光（Lf 亮度、Cf 彩度、hf 色相）放到三角网格上分段线性，再一档档量化，加上材质的档 k，涂到 m 上"""
    if not m.any():
        return
    Lp = polygonal(Lf, cell[0], cell[1], seed=seed)
    hp = polygonal(hf, cell[0], cell[1], seed=seed + 1)
    Lq = np.round(Lp / STEP_L) * STEP_L + k * MAT_STEP
    hq = np.round(hp / HUE_STEP) * HUE_STEP
    Cq = np.round(Cf / 0.01) * 0.01
    rgb = lch_rgb(Lq[m], Cq[m], hq[m])
    L.a[m, :3] = rgb
    L.a[m, 3] = 255


def wall_light(L: Layer, cx, half, top, base, L0=0.36, h0=-46, glows=(), seed=0):
    """圆塔外墙的光：左边接地平线的粉光（亮、偏粉），右边背光（深紫蓝）；上面接天光（偏冷偏紫）、檐下一道影；
    下面靠近云，被云反光照得偏粉、亮一点；窗里的灯在窗洞周围晕开、往下照窗台。返回 (亮度, 彩度, 色相) 三张图。"""
    u = np.clip((L.xx - cx) / np.maximum(half, 0.5), -1, 1)
    v = np.clip((L.yy - top) / max(base - top, 1), 0, 1)
    hor = np.clip(-u * 0.85 + 0.15, 0, 1) ** 1.3                    # 地平线粉光（左边低处）
    sky = (1 - v) ** 1.6                                             # 天光（上面）
    bnc = v ** 2.2                                                   # 云的反光（下面）
    eave = np.clip(1 - (L.yy - top) / 6.0, 0, 1)                     # 檐下的影
    br = smooth_noise(L.h, L.w, 8, 26, seed=seed) * 0.5              # 很淡的竖向笔触：块边不是一条条直竖线
    Lf = L0 + 0.08 * hor - 0.025 * sky + 0.06 * bnc - 0.07 * eave - 0.03 * np.clip(u - 0.3, 0, 1) + br * STEP_L * 0.3
    hf = h0 + 24 * hor - 16 * sky * (1 - hor) + 16 * bnc
    Cf = 0.046 + 0.016 * hor + 0.008 * bnc
    for (x, y, w, h, lit) in glows:
        if not lit:
            continue
        d = np.hypot((L.xx - (x + w / 2.0)) / (w / 2.0 + 5.5), (L.yy - (y + h * 0.62)) / (h / 2.0 + 6.5))
        g = np.clip(1 - d, 0, 1) ** 0.8
        Lf = Lf + 0.075 * g
        hf = hf * (1 - np.clip(g * 1.6, 0, 1)) + 38 * np.clip(g * 1.6, 0, 1)
        Cf = Cf + 0.03 * g
    return Lf, Cf, hf


def stone_texture(L: Layer, m, stone_m, seed, sx=(6, 12), sy=(4, 6), p_dark=0.55, coords=None):
    """露出石头的地方：每块石头只比抹灰暗一档或一样，不画缝。相邻两块尽量一深一浅（按邻居挑），形状靠明暗分开，
    不会连成一大片斑。"""
    cid, n = stone_cells(L, seed, sx, sy, coords=coords)
    rng = np.random.default_rng(seed + 9)
    sel = m & stone_m
    nb = [set() for _ in range(n)]
    for (a_, b_) in ((cid[:, :-1], cid[:, 1:]), (cid[:-1, :], cid[1:, :])):
        s_ = sel[:, :-1] & sel[:, 1:] if a_.shape[1] < cid.shape[1] else sel[:-1, :] & sel[1:, :]
        pa, pb = a_[s_ & (a_ != b_)], b_[s_ & (a_ != b_)]
        for i, j in set(zip(pa.tolist(), pb.tolist())):
            nb[i].add(j)
            nb[j].add(i)
    tone = np.zeros(n, int)
    done = np.zeros(n, bool)
    for i in rng.permutation(n):
        dk = sum(1 for j in nb[i] if done[j] and tone[j] == -1)
        lt = sum(1 for j in nb[i] if done[j] and tone[j] == 0)
        if dk < lt or (dk == lt and rng.random() < p_dark):
            tone[i] = -1
        done[i] = True
    k = np.zeros(L.xx.shape)
    k[sel] = tone[cid[sel]]
    return k


def blob(L: Layer, cx, cy, rx, ry, seed, rough=0.35):
    """一块不规则的斑（剥落、露石的地方）：椭圆的边被低频噪声推来推去"""
    n = smooth_noise(L.h, L.w, 4, 4, seed=seed)
    d = np.hypot((L.xx - cx) / rx, (L.yy - cy) / ry)
    return d + rough * n < 1


def rain_streaks(L: Layer, m, wins, seed):
    """窗台下面往下拖的雨痕：一两条一像素宽、长短不一、比墙暗一档的竖道"""
    rng = np.random.default_rng(seed)
    k = np.zeros(L.xx.shape)
    X, Y = _xy(L)
    for (x, y, w, h, lit) in wins:
        for _ in range(int(rng.integers(1, 3))):
            sx = int(x + rng.integers(0, max(w, 1)))
            ln = int(rng.integers(6, 15))
            k[m & (X == sx) & (Y >= y + h + 2) & (Y < y + h + 2 + ln)] = -1
    return k


# ---- s7（11-01）：作者「屋顶是圆锥，塔身还是平的，像一个圆筒盖在一张纸片上」。塔身也当圆柱画，和屋顶共用一套形体明暗：
#   竖向色带按方位切（u = 离轴距离 / 这一截自己的半径），屋顶、上层、下截用同一组分界 → 每条色带边从檐口沿同一条方位线
#   接着往下走（半径小一截，边就往里收几格，正好藏在檐下的影里）；横的一圈圈（瓦行、檐口、石块层、上层的底梁、塔脚）
#   都是同一个下弯比例的弧。不是透视：没有消失点，塔身上下一样粗。
CYL_CUTS = (-0.55, -0.15, 0.25, 0.62)      # 竖向色带的分界（按方位 u）
CYL_SAG = 4.5 / 63.0                       # 一圈往下弯多深：弧深 / 半径（屋顶檐口半径 63、弯 4.5）
CYL_DL = (0.08, 0.04, 0.0, -0.04, -0.075)  # 每条色带比中间那条亮 / 暗多少（和屋顶的色带一样一档一档）
CYL_DH = (24, 12, 0, -10, -16)             # 色相：左边偏地平线的粉，右边偏夜空的紫蓝
CYL_C = (0.062, 0.054, 0.048, 0.046, 0.045)


def cyl_coords(L: Layer, cx, r):
    """圆柱上的坐标：u = 方位（−1 左边沿 … 1 右边沿）、ring = 同一圈的高度（一条下弯的弧上 ring 相同）、
    s = 绕着圆柱展开的横坐标、arc = √(1−u²)"""
    u = np.clip((L.xx - cx) / r, -1, 1)
    arc = np.sqrt(1 - u * u)
    return u, L.yy - CYL_SAG * r * arc, r * np.arcsin(u), arc


def cyl_light(L: Layer, cx, r, top, base, L0, h0, glows=(), gpad=(5.5, 6.5)):
    """圆柱墙的光：竖向色带（CYL_*）+ 一圈圈的上下变化（上面接天光暗一档偏冷、下面接云的反光亮两档偏粉）+ 亮窗在墙上晕开。
    每一项先各自量化成整档再相加，块边只有两种：竖的色带边、横的弧。返回 (亮度, 彩度, 色相)。"""
    u, ring, s, _ = cyl_coords(L, cx, r)
    bi = band(u, CYL_CUTS)
    v = np.clip((ring - top) / max(base - top, 1), 0, 1)
    vq = np.round((-0.025 * (1 - v) ** 1.6 + 0.06 * v ** 2.2) / STEP_L)
    gq = np.zeros(L.xx.shape)
    r0 = float(np.min(r))
    for (x, y, w, h, lit, uw, w0) in glows:
        if not lit:
            continue
        sc = r0 * math.asin(uw)
        rc = y + h * 0.62 - CYL_SAG * r0 * math.sqrt(1 - uw * uw)
        d = np.hypot((s - sc) / (w0 / 2.0 + gpad[0]), (ring - rc) / (h / 2.0 + gpad[1]))
        gq = np.maximum(gq, np.round(0.075 * np.clip(1 - d, 0, 1) ** 0.8 / STEP_L))
    g = np.clip(gq / 2.0, 0, 1)
    Lf = L0 + np.array(CYL_DL)[bi] + (vq + gq) * STEP_L
    hf = (h0 + np.array(CYL_DH)[bi] + vq * HUE_STEP) * (1 - g) + 38 * g
    Cf = np.array(CYL_C)[bi] + 0.015 * g
    return Lf, Cf, np.round(hf / HUE_STEP) * HUE_STEP


def cyl_paint(L: Layer, m, Lf, Cf, hf, k):
    if m.any():
        L.a[m, :3] = lch_rgb(Lf[m] + k[m] * MAT_STEP, Cf[m], hf[m])
        L.a[m, 3] = 255


def shade(L: Layer, m, dL=-0.035, dh=-6.0):
    """投影：m 里已经画好的颜色整体暗一档、往冷那边偏一点（墙、木头、窗框一起压暗，不另起颜色）"""
    if not m.any():
        return
    lab = srgb_to_oklab(L.a[m, :3])
    lab[:, 0] += dL
    c, s_ = math.cos(math.radians(dh)), math.sin(math.radians(dh))
    lab[:, 1], lab[:, 2] = lab[:, 1] * c - lab[:, 2] * s_, lab[:, 1] * s_ + lab[:, 2] * c
    L.a[m, :3] = oklab_to_srgb(lab)


def conn4(m):
    """一像素宽的弧：斜着错一格的地方，把上面那格也补进来，让相邻两格有边相连（不只是角碰角）"""
    o = m.copy()
    o[:-1, 1:] |= m[:-1, :-1] & m[1:, 1:] & ~m[1:, :-1] & ~m[:-1, 1:]
    o[:-1, :-1] |= m[:-1, 1:] & m[1:, :-1] & ~m[1:, 1:] & ~m[:-1, :-1]
    return o


def conn4_in(m, inside):
    """和 conn4 一样补斜着错一格的地方，但补的那格要落在 inside 里（先试上面那格，不行就补下面那格）"""
    o = m.copy()
    for (a, b, up, lo) in (((slice(None, -1), slice(None, -1)), (slice(1, None), slice(1, None)),
                            (slice(None, -1), slice(1, None)), (slice(1, None), slice(None, -1))),
                           ((slice(None, -1), slice(1, None)), (slice(1, None), slice(None, -1)),
                            (slice(None, -1), slice(None, -1)), (slice(1, None), slice(1, None)))):
        d = m[a] & m[b] & ~m[up] & ~m[lo]
        o[up] |= d & inside[up]
        o[lo] |= d & ~inside[up] & inside[lo]
    return o


def cyl_win(cx, r, xc, y, w, h, lit):
    """圆柱上一扇窗的位置：中心在 xc，越靠两边越窄（宽 × √(1−u²)）。返回 (x, y, 投影宽, h, lit, u, 原宽)"""
    u = (xc - cx) / r
    wp = max(3, int(round(w * math.sqrt(1 - u * u))))
    return (int(math.floor(xc - wp / 2.0 + 0.5)), y, wp, h, lit, u, w)


def draw_cyl_window(L: Layer, r, win, sill=True, depth=4, box=False):
    """圆柱上的窗：窗洞朝圆柱的法线开进去，靠外那边的窗洞里露出墙的厚度（窗套的侧面，宽 depth × |u|；左边那扇的侧面
    背着地平线暗一档，右边那扇的侧面朝着光亮一档），玻璃跟着窄；两扇百叶靠外的那扇转得多、窄一点"""
    x, y, wp, h, lit, u, w0 = win
    m = deep_window(L, x, y, wp, h, lit, shutters=False, sill=sill, frame_pal=PW)
    jw = min(int(round(depth * abs(u))), wp - 3)
    rv = m & ((L.xx < x + jw) if u < 0 else (L.xx >= x + wp - jw)) if jw > 0 else np.zeros(m.shape, bool)
    gx0, gw = (x + jw, wp - jw) if u < 0 else (x, wp - jw)
    glass = m & ~rv
    rr = wp / 2.0
    if lit:
        L.put(glass, LAMP[2])
        L.put(glass & (L.yy < y + rr + 1), LAMP[3])
        L.put(glass & (L.yy >= y + h - 2), LAMP[1])
        L.put(glass & (L.xx < gx0 + 1), LAMP[1])
        if gw >= 5 and h >= 8:
            L.put(glass & (np.abs(L.xx - (gx0 + gw / 2.0 + 0.5)) < 0.5), TIMBER[1])
            L.put(glass & (np.abs(L.yy - (y + rr + (h - rr) * 0.35)) < 0.5), TIMBER[1])
    L.put(rv, PW[3] if u < 0 else PW[4])
    L.put(rv & (L.yy < y + 2), PW[2] if u < 0 else PW[3])         # 窗洞顶那一截在拱的影里
    sw = max(2, w0 // 2)
    for side in (-1, 1):
        us = np.clip(u + side * (wp / 2.0 + 1 + sw / 2.0) / r, -1, 1)
        swp = max(2, int(round(sw * math.sqrt(1 - us * us))))
        sx = x - 1 - swp if side < 0 else x + wp + 1
        sm = (L.xx >= sx) & (L.xx < sx + swp) & (L.yy >= y + 1) & (L.yy < y + h)
        L.put(sm, DOOR[2] if side < 0 else DOOR[1])
        L.put(sm & (L.yy < y + 2), DOOR[3])
        L.put(sm & (np.abs(L.yy - (y + h / 2.0)) < 0.6), DOOR[0])
    if box:
        flower_box(L, x, y + h + 2, wp)
    return glass if lit else np.zeros(m.shape, bool)


def lodging_exterior_v4():
    E = Layer(LW, LH)
    x0, x1 = L_BODY
    base = LH
    half = (x1 - x0) / 2.0
    ux0, ux1, uy = L_UP
    uh = (ux1 - ux0) / 2.0
    eave_y = uy + 1
    roof_r = int(round(uh + 1.0 + 4.5)) + 1.0                         # 檐口的半径（和下面尖顶的 hw_of[eave_y] + 1 一样）
    X, Y = _xy(E)
    # ---- 上下两截的分界：上层的底圈（两边在 floor_u，中间往下弯到 L_ROOF）
    u_u, ring_u, s_u, arc_u = cyl_coords(E, L_CX, uh)
    sag_u = CYL_SAG * uh
    floor_u = L_ROOF - sag_u
    top_b = floor_u + sag_u * arc_u                                   # 下截的上沿（同一条弧）
    # ---- 下截圆塔：墙脚往外撇一点（石头砌的根）；塔脚那一圈也是弧（中间压到图底，两边抬起 sag_b）
    sag_b = CYL_SAG * half
    _, ring0, _, _ = cyl_coords(E, L_CX, half)
    foot = base - sag_b
    flare = 2.4 * np.clip(1 - (foot - ring0) / 10.0, 0, 1) ** 1.5
    hh = half + flare
    u, ring, s, arc = cyl_coords(E, L_CX, hh)
    m = (np.abs(E.xx - L_CX) < hh) & (E.yy >= top_b) & (ring0 < foot)
    wins = [cyl_win(L_CX, half, xc, 160, 8, 14, True) for xc in (50, 94)]
    Lf, Cf, hf = cyl_light(E, L_CX, hh, L_ROOF, base, 0.345, -46, glows=wins)   # 比 s6 低一点点：晨身后那条色带亮了一档
    nz = smooth_noise(E.h, E.w, 6, 6, seed=402)
    stone_m = ring0 >= foot - 12 + 3 * nz                                       # 墙脚那几圈
    stone_m |= (np.abs(u) + 0.10 * nz) > 0.80                                   # 圆塔的两边（转过去的地方）
    for (wx, wy, wp, wh, _l, uw, w0) in wins:                                   # 窗边（在展开的坐标里是圆的）
        d = np.hypot((s - half * math.asin(uw)) / (w0 / 2.0 + 5),
                     (ring - (wy + wh / 2.0 - sag_b * math.sqrt(1 - uw * uw))) / (wh / 2.0 + 5))
        stone_m |= (d + 0.25 * nz) < 1.0
    ud = (L_DOOR - L_CX) / half                                                 # 门边
    d = np.hypot((s - half * math.asin(ud)) / 12.0, (ring - (base - 18 - sag_b * math.sqrt(1 - ud * ud))) / 21.0)
    stone_m |= (d + 0.2 * nz) < 1.0
    peel = np.zeros(m.shape, bool)                                              # 两处剥落
    for (px_, py_, rx, ry, sd) in ((L_CX + 20, L_ROOF + 46, 9, 6, 403), (L_CX - 18, L_ROOF + 18, 7, 5, 404)):
        up = (px_ - L_CX) / half
        n_ = smooth_noise(E.h, E.w, 4, 4, seed=sd)
        peel |= np.hypot((s - half * math.asin(up)) / rx, (ring - (py_ - sag_b * math.sqrt(1 - up * up))) / ry) + 0.35 * n_ < 1
    stone_m |= peel
    k = stone_texture(E, m, stone_m, 405, coords=(s, ring))
    low = m & (ring0 >= foot - 10)
    k[low] = np.minimum(k[low], stone_texture(E, m, stone_m, 408, sx=(8, 14), sy=(5, 6), coords=(s, ring))[low])
    k[conn4((k < 0) & m) & m] = -1                                              # 靠两边压窄的石块斜着碰角的地方连上
    k[conn4((k == 0) & m) & m & (np.roll(k, 1, 0) == 0)] = 0
    k += rain_streaks(E, m & ~stone_m, [w_[:5] for w_ in wins], 406)
    lip = m & ~peel & (np.roll(peel, -1, 0) | np.roll(peel, 1, 1)) & ~stone_m   # 剥落处抹灰的断口亮一档（抹灰有厚度）
    k[lip] += 1
    cyl_paint(E, m, Lf, Cf, hf, k)
    E.put(m & ~np.roll(m, 1, axis=1) & (E.yy > L_ROOF + 4) & (ring0 < foot - 12), PINK_RIM)
    lit_glass = np.zeros(m.shape, bool)
    for w_ in wins:
        lit_glass |= draw_cyl_window(E, half, w_, sill=True, depth=4, box=True)
    # 门：在 u≈−0.76 的地方，也跟着转（窄一点），门洞左边露出墙的厚度
    dw = int(round(18.5 * math.sqrt(1 - ud * ud)))
    door_x = int(math.floor(L_DOOR - dw / 2.0 + 0.5))
    dm = stone_door(E, door_x, base, dw, 30, True, pal=PW)
    E.put(dm & (E.xx < door_x + 2), PW[2])
    f = dw / 14.0
    aw = poly_mask(E, [(L_DOOR + o * f, base + dy) for (o, dy) in
                       ((-11, -35), (11, -35), (13, -31), (8, -29), (2, -30), (-4, -29), (-10, -31))])
    stripe = (np.floor((E.xx - (L_DOOR - 11 * f)) / 2).astype(int) % 2) == 0
    E.put(aw, lch_hex(0.50, 0.04, -75))
    E.put(aw & stripe, PW[5])
    E.put(aw & (E.xx > L_DOOR + 6 * f), lch_hex(0.42, 0.04, -75))
    E.put(aw & stripe & (E.xx > L_DOOR + 6 * f), PW[4])
    E.rect(L_DOOR - 12 * f, base - 36, L_DOOR + 12 * f, base - 35, TIMBER4[1])
    lamp_post_hang(E, int(round(L_DOOR + 13 * f)), base - 38)
    # ---- 上面那层：抹灰 + 木框架，同一套色带（按这一截的半径 uh 切）
    um = (np.abs(E.xx - L_CX) < uh) & (E.yy >= uy) & (E.yy < top_b)
    uwins = [cyl_win(L_CX, uh, xc, int(round(116 + sag_u * math.sqrt(1 - ((xc - L_CX) / uh) ** 2))), 7, 9, l_)
             for (xc, l_) in ((33, True), (72, False), (103, True))]
    Lf, Cf, hf = cyl_light(E, L_CX, uh, uy, L_ROOF + 40, 0.40, -34, glows=uwins)
    cyl_paint(E, um, Lf, Cf, hf, np.zeros(E.xx.shape))
    tm = um & (ring_u >= floor_u - 2)                                           # 底梁：两行厚的一圈弧
    for (wx, wy, wp, wh, l_, uw, w0) in uwins:
        tm |= um & (((E.xx >= wx - 3) & (E.xx < wx - 1)) | ((E.xx >= wx + wp + 1) & (E.xx < wx + wp + 3)))
    for (sb, st) in ((-30, -16), (12, 21), (56, 46)):             # 斜撑：在展开的坐标里是直的，转过去就弯
        pts = []
        for t in np.linspace(0, 1, 9):
            ss = sb + (st - sb) * t
            rr_ = (floor_u - 2) + (uy - 2 - (floor_u - 2)) * t
            pts.append((L_CX + uh * math.sin(ss / uh) - 0.5, rr_ + sag_u * math.cos(ss / uh) - 0.5))
        for (px_, py_) in curve4(pts):
            tm |= um & ((X == px_) | (X == px_ + 1)) & (Y == py_)
    tidx = np.array([3, 2, 1, 1, 0])[band(u_u, CYL_CUTS)]
    tidx = tidx - (conn4(um & (ring_u >= floor_u - 1)) & um)                    # 底梁下面一行是梁底，暗一档
    paint(E, tm, tidx, TIMBER4)
    E.put(um & ~np.roll(um, 1, axis=1) & ~tm, PINK_RIM)
    for w_ in uwins:
        lit_glass |= draw_cyl_window(E, uh, w_, sill=False, depth=3)
    # ---- 托梁（上层挑出下截的那一圈底下）
    dist = np.abs(E.xx - L_CX) - half
    cb = (dist > 0) & (dist < 4) & (E.yy >= top_b) & (E.yy < top_b + np.maximum(2, 3 - dist / 2.5)) & (np.mod(X - ux0, 4) < 2)
    E.put(cb, TIMBER4[2])
    E.put(cb & (E.yy < top_b + 1), TIMBER4[3])
    # ---- 檐下的影：屋檐在上层投一圈弯的影（檐口底边那条弧往下再 2~5 行，右边背光、影深一点），
    #      上层挑出来的那一圈也在下截的顶上投一圈影 —— 两道影把屋顶、上层、下截扣在一起
    u_r = np.clip((E.xx - L_CX) / roof_r, -1, 1)
    eave_bot = eave_y + 2 + 4.5 * np.sqrt(1 - u_r * u_r)
    shade(E, um & (E.yy < eave_bot + 3 + 3 * np.clip((u_u + 1) / 2, 0, 1)) & ~lit_glass, dh=-10.0)
    shade(E, m & (E.yy < top_b + 2 + 2 * np.clip((u + 1) / 2, 0, 1)) & ~lit_glass)
    # ---- 尖顶（11-01 第三版样稿：作者「这个三角形感觉不像屋顶」）。参考作者自己画的尖顶房子（Phage 和沐子之家）：
    #   上段直的圆锥、下段钟形往外翻；明暗是几道竖的色带（左边接地平线粉光，往右一档档暗进夜空的深紫蓝，带一点弧）；
    #   一圈圈瓦行是往下弯的弧（越近塔尖越短越密），行与行之间只暗一档、是连着的弧线；檐口有三行厚、本身也是同样的弧，
    #   底下在墙上投一道影；尖上一个金属尖帽 + 小球，旗杆从球上插出去；老虎窗有自己的两坡小屋顶和侧面。
    R = Layer(LW, LH)
    RH, rw_s, flare_px, sag = 84, uh + 1.0, 4.5, 4.5
    eave_y = uy + 1
    tip_y = eave_y - RH
    hw_of = {}
    for yy in range(tip_y, eave_y + 1):
        t = (yy - tip_y) / RH
        hw_of[yy] = int(round(rw_s * t + flare_px * np.clip((t - 0.76) / 0.24, 0, 1) ** 2))
    hwe = hw_of[eave_y]
    X, Y = _xy(R)
    HW = np.full((LH, LW), -1.0)
    for yy, hw in hw_of.items():
        HW[yy] = hw
    HW[eave_y:] = hwe
    dxc = np.abs(R.xx - (L_CX + 0.0))                                 # 左右对称：中心在 L_CX−0.5 和 L_CX 之间的两格尖
    halfw = np.where(HW >= 0, HW + 1.0, -1)
    u = np.clip((R.xx - L_CX) / np.maximum(halfw, 1), -1, 1)
    arc = np.sqrt(np.clip(1 - u * u, 0, 1))
    eave_bot = eave_y + 2 + sag * arc                                 # 檐口底边：往下弯的弧
    rm = (Y >= tip_y) & (HW >= 0) & (X >= L_CX - 1 - HW) & (X < L_CX + 1 + HW) & (R.yy < eave_bot + 0.5)
    t_ = np.clip((R.yy - tip_y) / RH, 0, 1)
    # 竖向色带：u 加一点随高度变的偏移，色带边是略带弧的斜线，往塔尖收
    ub = u + 0.10 * (1 - t_) * (1 - u * u)
    band_i = band(ub, CYL_CUTS)                                       # 0 = 最左（亮）… 4 = 最右（暗）；和塔身同一组分界
    Lb = np.array([0.47, 0.425, 0.385, 0.345, 0.305])[band_i]
    hb = np.array([-30, -44, -56, -66, -72])[band_i]
    Cb = np.array([0.065, 0.058, 0.052, 0.048, 0.046])[band_i]
    Lb = Lb + 0.03 * (t_ < 0.25)                                       # 尖上那截映着天，亮一点
    k = np.zeros((LH, LW))
    # 瓦行：往下弯的弧，越近塔尖越密、弧越浅
    rng = np.random.default_rng(431)
    yr = float(eave_y - 3)
    rows = []
    while yr > tip_y + 6:
        tr = (yr - tip_y) / RH
        rows.append((yr, tr))
        yr -= 2.0 + 3.0 * tr
    for (yr, tr) in rows:
        hw = hw_of[int(round(yr))]
        if hw < 4:
            continue
        pts = []
        for xx in np.linspace(L_CX - 1 - hw + 0.5, L_CX + hw + 0.5, max(8, int(hw * 2 / 3))):
            uu = (xx - L_CX) / (hw + 1.0)
            pts.append((xx, yr + sag * tr * math.sqrt(max(0.0, 1 - uu * uu))))
        for (px_, py_) in curve4(pts):
            if 0 <= py_ < LH and 0 <= px_ < LW and rm[py_, px_]:
                k[py_, px_] = -1
    # 个别瓦片亮一档（贴着某一行瓦线下面的一小块）
    for _ in range(9):
        yr, tr = rows[int(rng.integers(1, len(rows) - 2))]
        hw = hw_of[int(round(yr))]
        if hw < 8:
            continue
        xx = int(L_CX + rng.uniform(-0.8, 0.8) * hw)
        uu = (xx - L_CX) / (hw + 1.0)
        yy = int(round(yr + sag * tr * math.sqrt(max(0.0, 1 - uu * uu)))) + 1
        tile = rm & (X >= xx) & (X < xx + 3) & (Y >= yy) & (Y < yy + 2) & (k == 0)
        k[tile] = 1
    Lq = Lb + k * 0.035
    rgb = lch_rgb(Lq[rm], Cb[rm], hb[rm])
    R.a[rm, :3] = rgb
    R.a[rm, 3] = 255
    # 檐口：三行厚的弧形檐边（上面一行接光亮一档、下面两行是檐底的暗面）
    fas = rm & (R.yy >= eave_bot - 2.5)
    R.put(fas, lch_hex(0.26, 0.045, -66))
    top_f = fas & ~np.roll(fas, 1, axis=0)
    R.a[top_f, :3] = lch_rgb(Lb[top_f] + 0.035, Cb[top_f], hb[top_f])
    # 左边坡沿的粉色轮廓光：一条连着的线（每行从这一行的边画到上一行的边），从塔尖往下渐强
    prev = None
    for yy in range(tip_y, eave_y):
        a_ = L_CX - 1 - hw_of[yy]
        b_ = a_ if prev is None else max(a_, prev)
        col = PINK_RIM if (yy - tip_y) > RH * 0.35 else lch_hex(0.46, 0.06, -22)
        for xx in range(a_, b_ + 1):
            if xx < L_CX - 1:
                R.px(xx, yy, col)
        prev = a_
    # 老虎窗：正面（抹灰，亮着窗）+ 右边一条侧面 + 两坡小屋顶（左坡亮、右坡暗，檐挑出一格）+ 在大屋顶上投的一小块影
    dx, dy = L_CX + 15, eave_y - 33
    sh = rm & (X >= dx + 11) & (X < dx + 15) & (Y >= dy - 2) & (Y < dy + 12) | rm & (X >= dx) & (X < dx + 13) & (Y >= dy + 11) & (Y < dy + 13)
    R.a[sh, :3] = lch_rgb(Lb[sh] - 0.035, Cb[sh], hb[sh])
    face = (R.xx >= dx) & (R.xx < dx + 10) & (R.yy >= dy) & (R.yy < dy + 11)
    paint(R, face, np.full(face.shape, 4), PW)
    side = (R.xx >= dx + 10) & (R.xx < dx + 12) & (R.yy >= dy + 1) & (R.yy < dy + 11)
    paint(R, side, np.full(side.shape, 2), PW)
    R.rect(dx, dy, dx + 10, dy + 1, PW[2])                            # 小屋顶底下的影
    deep_window(R, dx + 3, dy + 3, 4, 7, True, sill=False, frame_pal=PW, cross=False)
    R.rect(dx + 2, dy + 10, dx + 8, dy + 11, PW[5])                   # 窗台
    gl = poly_mask(R, [(dx - 3, dy + 2), (dx + 5, dy - 8), (dx + 5.5, dy + 2)])          # 两坡小屋顶，两边各挑出 3 格
    gr_ = poly_mask(R, [(dx + 5, dy - 8), (dx + 14, dy + 2), (dx + 5, dy + 2)])
    R.put(gl, lch_hex(0.50, 0.065, -34))
    R.put(gr_, lch_hex(0.34, 0.05, -62))
    R.put((gl | gr_) & (R.yy >= dy + 1), lch_hex(0.26, 0.045, -66))    # 小屋顶的檐底（两行厚）
    R.put(gl & ~np.roll(gl, 1, axis=1) & (R.yy < dy + 1), PINK_RIM)
    R.rect(dx + 4, dy - 9, dx + 6, dy - 7, WHEAT[3])                   # 屋脊头上一个小尖饰
    # 塔尖：金属尖帽（两格宽、三行高，左亮右暗）+ 上面一颗小球，旗杆从球上插出去
    R.rect(L_CX - 2, tip_y - 1, L_CX + 2, tip_y + 3, WHEAT[2])
    R.rect(L_CX - 2, tip_y - 1, L_CX, tip_y + 3, WHEAT[4])
    R.rect(L_CX - 3, tip_y + 2, L_CX + 3, tip_y + 3, WHEAT[1])
    R.rect(L_CX - 1, tip_y - 4, L_CX + 1, tip_y - 1, WHEAT[3])
    R.rect(L_CX - 1, tip_y - 4, L_CX, tip_y - 2, WHEAT[5])
    E.over(R)
    fx, fy = flagpole(E, L_CX - 1, tip_y - 4, 11)
    return E, (fx, fy)


def foot_cloud_and_mist(base=LH):
    """塔脚前面压的一排云团（和能走的云一条色阶，盖住塔脚最下面几行，门口那段矮一点）+ 贴地一层薄雾（固定半透明两档）"""
    F = CA.Field(LW + 2 * PAD, LH)
    rng = np.random.default_rng(431)
    x = 2.0
    while x < LW - 2:
        near_door = abs(x - L_DOOR) < 12
        corner = min(abs(x - L_BODY[0]), abs(x - L_BODY[1])) < 12          # 塔身两边转角：云团大、往上盖得高，像绕过塔脚
        right = abs(x - L_BODY[1]) < 12                                      # 右边转角（离门和晨远）再高一截
        r = rng.uniform(3.0, 4.2) if near_door else (rng.uniform(10.0, 13.0) if right else
                                                      rng.uniform(7.5, 10.0) if corner else rng.uniform(4.5, 7.0))
        F.new_group()
        F.cauli(x + PAD, base - r * (0.95 if corner else 0.7) + (3.0 if near_door else rng.uniform(-1.0, 1.0)), r, 20, rng,
                sq=0.62, depth=2,
                kids=(2, 3), ks=(0.32, 0.55), rmin=2.0, spread=(-165, -15), ref=base - r * 1.4, unit=4)
        x += r * rng.uniform(0.9, 1.35)
    pal = CA.cloud_pal(0.14, 0.50, 7, C_lo=0.05, C_hi=0.085, h_lo=286, h_hi=352)    # 前面的云朝光那面亮一点
    T = render_field(F, LW, pal, body=4, rim=(1.5, 3.2), crease=2.0, run_bands=(4, 8))
    M = Layer(LW, LH)
    n = smooth_noise(LH, LW, 14, 4, seed=432)
    top1 = base - 14 + 2.5 * n
    top2 = base - 8 + 1.5 * n
    side = np.clip(np.minimum(M.xx - 2, LW - 2 - M.xx) / 10.0, 0, 1)
    ub = np.clip((M.xx - L_CX) / ((L_BODY[1] - L_BODY[0]) / 2.0), -1, 1)       # s7：雾绕着塔脚是一圈弧（中间低、两边高）
    lift = CYL_SAG * (L_BODY[1] - L_BODY[0]) / 2.0 * (1 - np.sqrt(1 - ub * ub))
    top1, top2 = top1 - lift, top2 - lift
    mist = lch_rgb(np.array(0.46), np.array(0.065), np.array(-24))
    M.put((M.yy >= top1 + (1 - side) * 6), mist, 80)
    M.put((M.yy >= top2 + (1 - side) * 6), mist, 135)
    return T, M


def lodging_v4():
    """样稿：新的外墙 + 原来的屋里（剖面、家具、窗光照旧），前墙下面压云团、贴一层薄雾"""
    global lodging_exterior
    old = lodging_exterior
    lodging_exterior = lodging_exterior_v4
    try:
        back, front, light, view, fl = lodging()
    finally:
        lodging_exterior = old
    T, M = foot_cloud_and_mist()
    front.over(M)
    front.over(T)
    return back, front, light, view, fl


INTERLEAVE = [
    # (插在哪一层后面, 用作者哪张云, 往下挪几行, 视差, 漂移)：作者 art/cloud/ 的原图，水平翻过来用（和背景里同一张图的形状错开）
    ("town_far", "midfar", 28, 0.80, -2.0),    # 远处那排塔前面：薄薄一层，塔脚到塔腰被盖住
    ("town_back", "mid", 4, 1.0, -1.2),        # 后排房子前面、地面后面：房子下段埋在云里，高低不一（路和广场在它前面，不会被盖）
]


def interleave_clouds(S: "Scene"):
    """样稿：把作者的云插到建筑层之间（只在预览里叠，room.json 还没改）"""
    ids = [c["id"] for c, _ in S.layers]
    if any(i.startswith("cloud_") and i.endswith("_over") for i in ids):    # 第四轮起 room.json 里已经有了
        return
    for (after, src, dy, sc, drift) in reversed(INTERLEAVE):
        im = _rgba(ROOT / "art" / "cloud" / (src + ".png"))[:, ::-1].copy()
        sh = np.zeros_like(im)
        if dy >= 0:
            sh[dy:] = im[:im.shape[0] - dy]
        else:
            sh[:dy] = im[-dy:]
        c = {"id": f"cloud_{src}_over_{after}", "scroll": sc, "tile": True, "drift": drift}
        S.layers.insert(ids.index(after) + 1, (c, sh))


def sample(d: Path):
    """样稿：只换住处，叠出「现在」和「样稿」两张 3 倍图（带晨）、一张并排对比、塔脚 6 倍局部；量晨和墙的亮度差"""
    d.mkdir(parents=True, exist_ok=True)
    S = Scene(0.0)
    cl = int(np.clip(LODGE - 240, 0, W - 480))
    chen = (LODGE - 20, GROUND)
    now = S.render(cl, chen=chen)
    before_c = contrast(S)["住处的塔"]
    b, f, l, v, fl = lodging_v4()
    for Lr in (b, f):
        fix_speckles(Lr.a)
    S.hback, S.hfront = b.a.astype(np.float32), f.a.astype(np.float32)
    S.hlight, S.hview = l.a.astype(np.float32), v.a[..., 3] > 0
    S.hobjs = [(fl[0].a.astype(np.float32), fl[0].ox, fl[0].oy)]
    interleave_clouds(S)
    new = S.render(cl, chen=chen)
    after_c = contrast(S)["住处的塔"]
    x0, x1 = 140, 380
    for name, im in (("lodging_now", now), ("lodging_sample", new)):
        Image.fromarray(im[:, x0:x1]).resize(((x1 - x0) * 3, 810), Image.NEAREST).save(d / f"{name}_x3.png")
    pair = np.concatenate([now[:, x0:x1], np.zeros((270, 4, 3), np.uint8), new[:, x0:x1]], 1)
    Image.fromarray(pair).resize((pair.shape[1] * 3, 810), Image.NEAREST).save(d / "lodging_now_vs_sample_x3.png")
    hx = S.hx0 - cl
    fx0, fx1, fy0, fy1 = hx + 64, hx + LW + 14, 194, 238              # 塔的右半边（晨站在左边门口），一直到塔外
    Image.fromarray(new[fy0:fy1, fx0:fx1]).resize(((fx1 - fx0) * 6, (fy1 - fy0) * 6), Image.NEAREST).save(d / "lodging_foot_x6.png")
    hy = GROUND + 1 - LH                                               # 塔身和屋顶交界（檐口、上层、下截的顶）
    jx0, jx1, jy0, jy1 = hx + 6, hx + LW - 6, hy + L_UP[2] - 18, hy + L_ROOF + 16
    Image.fromarray(new[jy0:jy1, jx0:jx1]).resize(((jx1 - jx0) * 6, (jy1 - jy0) * 6), Image.NEAREST).save(d / "junction_x6.png")
    for (n_, a_) in (("back", b.a), ("front", f.a)):
        Image.fromarray(a_).save(d / f"sample_lodge_{n_}.png")
    print("亮度差（住处的塔）：现在 头发 %.0f 墙 %.0f 差 %.0f；样稿 头发 %.0f 墙 %.0f 差 %.0f" % (before_c + after_c))
    print("样稿:", d)


# ======================================================================= 第四轮（11-01）：s4–s7 的做法推到全镇
#   作者看了 s7：「可以，推全镇」。每栋房子都照晨住的那座塔画：
#   - 颜色从天和云里取（OKLCh：墙是天的灰紫、左边接地平线的粉、右边沉进夜空的紫蓝）；
#   - 墙面不画缝：抹灰为主，墙角、窗边、门边、墙脚露出成片的石块（只比抹灰暗一档、零星）；
#   - 圆塔 = 圆柱：竖向色带按方位切（CYL_CUTS，和屋顶同一组分界），窗、石块绕着转过去，横的一圈圈都是同一个下弯比例的弧；
#   - 圆锥瓦顶：竖向色带、往下弯的瓦行（越近尖越密）、钟形外翻带厚度的檐口、金属尖帽 + 小球，檐下在塔身上投一圈弯的影；
#   - 不是圆塔的房子按自己的形体分面受光：半木房的正面一个面、右边露一条侧墙暗两档，右坡的屋面压在侧墙上（屋顶读得出厚度）；
#     风车是八角塔，四个看得到的面一档一档暗下去，收帆台是一圈弯的木台，帽子也是圆锥瓦顶；
#   - 塔脚往下画进云里，后排前面插一层作者的云（room.json 的 cloud_*_over 层）。
#   晨要一直是画面里对比最高的：每栋前面量晨头发和身后的亮度差，都要 ≥ 150（CONTRAST_MIN）。
CONTRAST_MIN = 150
ROOF_KIND = {
    #        亮度（左 → 右五条色带）                 色相                       彩度                          檐底
    "slate": ((0.47, 0.425, 0.385, 0.345, 0.305), (-30, -44, -56, -66, -72), (0.065, 0.058, 0.052, 0.048, 0.046), (0.26, 0.045, -66)),
    "terra": ((0.46, 0.415, 0.375, 0.335, 0.295), (-2, -12, -22, -32, -42), (0.075, 0.068, 0.060, 0.054, 0.050), (0.26, 0.05, -36)),
}
WALL_L0 = 0.33          # 后排石塔的墙（比住处的 0.345 再收一点：后排的塔脚离晨的头更近，云的反光照得亮）
PLASTER_L0 = 0.35       # 半木房的灰泥
HOUSE_STONE_L0 = 0.31   # 半木房的石砌底层



def rim_left(L: Layer, m, col, y0=-1e9, y1=1e9):
    """朝地平线那边（左边）一条连着的轮廓光：每行画在这一行最左那格；边错开一格的地方，把上一行补到下一行的边上，
    让相邻两格有边相连（斜边、收分的塔身也不会断成一格一格角碰角的点）。只画 y0 ≤ y < y1 的行。"""
    c = hexc(col) if isinstance(col, str) else np.asarray(col)
    has = m.any(axis=1)
    first = np.argmax(m, axis=1)
    rows = L.yy[:, 0]
    prev = None
    for r in range(m.shape[0]):
        if not has[r] or not (y0 <= rows[r] < y1):
            prev = None
            continue
        a = int(first[r])
        b = a if prev is None else max(a, prev)
        seg = np.nonzero(m[r, a:b + 1])[0] + a
        L.a[r, seg, :3] = c
        L.a[r, seg, 3] = 255
        if prev is not None and prev < a:
            seg = np.nonzero(m[r - 1, prev:a + 1])[0] + prev
            L.a[r - 1, seg, :3] = c
            L.a[r - 1, seg, 3] = 255
        prev = a

def cone_roof_v2(L: Layer, cx, eave_y, r_wall, RH, kind="slate", seed=0, plain=False, flare=None, finial=True, rim=True):
    """圆锥瓦顶（照住处 s6 那顶）：上段直的圆锥、下段钟形外翻；五条竖向色带（CYL_CUTS）；往下弯的瓦行（越近尖越密，暗一档、
    连着的弧）；个别瓦片亮一档；檐口 2~3 行厚（上面一行接光亮一档、下面是檐底的暗面），本身也是弧；左坡一条连着的粉色轮廓光；
    尖上金属尖帽 + 小球。cx 要是整数（左右对称）。返回 {tip: 旗杆脚 (x, y), eave_bot: 檐口底边那条弧（整张图的数组）,
    hw: {行: 半宽}, R: 外半径, mask}。plain = 远处的：不画瓦行和亮瓦。"""
    cx = int(cx)
    Ls, hs, Cs, fas_c = ROOF_KIND[kind]
    rw_s = r_wall + 1.0
    if flare is None:
        flare = float(np.clip(0.08 * r_wall + 0.5, 1.0, 4.5))
    tip_y = int(eave_y - RH)
    hw_of = {}
    for yy in range(tip_y, int(eave_y) + 1):
        t = (yy - tip_y) / RH
        hw_of[yy] = int(round(rw_s * t + flare * np.clip((t - 0.76) / 0.24, 0, 1) ** 2))
    hwe = hw_of[int(eave_y)]
    Rr = hwe + 1.0
    sag = CYL_SAG * Rr
    X, Y = _xy(L)
    HW = np.full(X.shape, -1.0)
    for yy, hw in hw_of.items():
        HW[Y == yy] = hw
    HW[Y > eave_y] = hwe
    halfw = np.where(HW >= 0, HW + 1.0, 1.0)
    u = np.clip((L.xx - cx) / halfw, -1, 1)
    arc = np.sqrt(np.clip(1 - u * u, 0, 1))
    ue = np.clip((L.xx - cx) / Rr, -1, 1)
    eave_bot = eave_y + 2 + sag * np.sqrt(1 - ue * ue)
    rm = (Y >= tip_y) & (HW >= 0) & (X >= cx - 1 - HW) & (X < cx + 1 + HW) & (L.yy < eave_bot + 0.5)
    if not rm.any():
        return {"tip": (cx - 1, tip_y - 4), "eave_bot": eave_bot, "hw": hw_of, "R": Rr, "mask": rm, "tip_y": tip_y}
    t_ = np.clip((L.yy - tip_y) / RH, 0, 1)
    ub = u + 0.10 * (1 - t_) * (1 - u * u)
    bi = band(ub, CYL_CUTS)
    bi = np.where(HW < 3, np.where(L.xx < cx, 1, 3), bi)              # 最尖那几行只有两三格宽：干脆左亮右暗两块，不来回跳
    Lb = np.array(Ls)[bi] + 0.03 * (t_ < 0.25)
    hb, Cb = np.array(hs)[bi], np.array(Cs)[bi]
    k = np.zeros(X.shape)
    rng = np.random.default_rng(seed)
    rows = []
    yr = float(eave_y - 3)
    while yr > tip_y + 6:
        tr = (yr - tip_y) / RH
        rows.append((yr, tr))
        yr -= 2.0 + 3.0 * tr
    if not plain:
        for (yr, tr) in rows:
            hw = hw_of[int(round(yr))]
            if hw < 4:
                continue
            pts = []
            for xx in np.linspace(cx - 1 - hw + 0.5, cx + hw + 0.5, max(8, int(hw * 2 / 3))):
                uu = (xx - cx) / (hw + 1.0)
                pts.append((xx, yr + sag * tr * math.sqrt(max(0.0, 1 - uu * uu))))
            for (px_, py_) in curve4(pts):
                sel = rm & (X == px_) & (Y == py_)
                k[sel] = -1
        for _ in range(max(0, int(hwe / 7))):
            if len(rows) < 4:
                break
            yr, tr = rows[int(rng.integers(1, len(rows) - 2))]
            hw = hw_of[int(round(yr))]
            if hw < 8:
                continue
            xx = int(cx + rng.uniform(-0.8, 0.8) * hw)
            uu = (xx - cx) / (hw + 1.0)
            yy = int(round(yr + sag * tr * math.sqrt(max(0.0, 1 - uu * uu)))) + 1
            tile = rm & (X >= xx) & (X < xx + 3) & (Y >= yy) & (Y < yy + 2) & (k == 0)
            k[tile] = 1
    Lq = Lb + k * 0.035
    L.a[rm, :3] = lch_rgb(Lq[rm], Cb[rm], hb[rm])
    L.a[rm, 3] = 255
    fas = rm & (L.yy >= eave_bot - (2.5 if hwe >= 14 else 1.5))
    L.put(fas, lch_hex(*fas_c))
    top_f = conn4_in(fas & ~np.roll(fas, 1, axis=0), fas)              # 檐口上沿那条弧：台阶处补成四邻接
    L.a[top_f, :3] = lch_rgb(Lb[top_f] + 0.035, Cb[top_f], hb[top_f])
    if rim:
        prev = None
        for yy in range(tip_y, int(eave_y)):
            a_ = cx - 1 - hw_of[yy]
            b_ = a_ if prev is None else max(a_, prev)
            col = PINK_RIM if (yy - tip_y) > RH * 0.35 else lch_hex(0.46, 0.06, -22)
            for xx in range(a_, b_ + 1):
                if xx < cx - 1:
                    L.px(xx, yy, col)
            prev = a_
    if finial:
        if hwe >= 16:
            L.rect(cx - 2, tip_y - 1, cx + 2, tip_y + 3, WHEAT[2])
            L.rect(cx - 2, tip_y - 1, cx, tip_y + 3, WHEAT[4])
            L.rect(cx - 3, tip_y + 2, cx + 3, tip_y + 3, WHEAT[1])
        else:
            L.rect(cx - 1, tip_y - 1, cx + 1, tip_y + 3, WHEAT[2])
            L.rect(cx - 1, tip_y - 1, cx, tip_y + 3, WHEAT[4])
            L.rect(cx - 2, tip_y + 2, cx + 2, tip_y + 3, WHEAT[1])
        L.rect(cx - 1, tip_y - 4, cx + 1, tip_y - 1, WHEAT[3])
        L.rect(cx - 1, tip_y - 4, cx, tip_y - 2, WHEAT[5])
    return {"tip": (cx - 1, tip_y - 4), "eave_bot": eave_bot, "hw": hw_of, "R": Rr, "mask": rm, "tip_y": tip_y}


def plain_window(L: Layer, x, y, w, h, lit):
    """远处的小窗：一块亮的暖黄（上面一行更亮）或者映着天的暗玻璃"""
    if lit:
        L.rect(x, y, x + w, y + h, LAMP[2])
        L.rect(x, y, x + w, y + 1, LAMP[3])
    else:
        L.rect(x, y, x + w, y + h, lch_hex(0.24, 0.04, -60))


def wall_stones(L: Layer, m, u, s, ring, foot, wins_sr, door_sr, seed, small=False):
    """墙面上露出来的石块：墙脚那几圈、两边转过去的地方、窗边、门边，再加一两处剥落 —— 在 (s, ring) 坐标里切，
    所以靠两边变窄、层是弯的。返回材质档 k（−1 = 暗一档）"""
    nz = smooth_noise(L.h, L.w, 6, 6, seed=seed)
    sm = ring >= foot - 10 + 3 * nz
    sm |= (np.abs(u) + 0.10 * nz) > 0.80
    for (sc, rc, rx, ry) in wins_sr + door_sr:
        sm |= (np.hypot((s - sc) / rx, (ring - rc) / ry) + 0.25 * nz) < 1.0
    sx, sy = ((3, 7), (3, 4)) if small else ((5, 10), (3, 5))
    k = stone_texture(L, m, sm, seed + 1, sx=sx, sy=sy, coords=(s, ring))
    k[conn4((k < 0) & m) & m] = -1
    return k, sm


def cyl_tower_v2(L: Layer, cx, base, w, h, cap_h, roof="slate", wins=(), door=None, seed=0, crenel=False, plain=False,
                 L0=None):
    """石砌圆塔（照住处那座）：圆柱塔身 + 圆锥瓦顶；crenel = 城堡塔：顶上一圈带雉堞的护墙（雉堞绕着转、靠两边变窄），
    下面一圈托石，尖顶从护墙里面长出来。wins = [(从塔顶往下 dy, 宽, 高, 亮不亮), …]，窗左右错开（绕着圆柱转过去）；
    door = (宽, 高, 亮不亮)。塔脚往下多画 6 行埋进云里。"""
    cx = int(cx)
    L0 = WALL_L0 if L0 is None else L0
    half = w / 2.0
    top = base - h
    sag_b = CYL_SAG * half
    _, ring0, _, _ = cyl_coords(L, cx, half)
    foot = base + 6 - sag_b
    flare = (1.0 if plain else 2.0) * np.clip(1 - (foot - ring0) / 10.0, 0, 1) ** 1.5
    hh = half + flare
    u, ring, s, arc = cyl_coords(L, cx, hh)
    m = (np.abs(L.xx - cx) < hh) & (L.yy >= top) & (ring0 < foot)
    offs = (-0.36, 0.34, -0.2, 0.3) if half >= 8 else (0.0,)
    wl = []
    for i, (dy, ww, wh, lit) in enumerate(wins):
        xc = cx + offs[i % len(offs)] * half
        wl.append(cyl_win(cx, half, xc, top + dy, ww, wh, lit))
    Lf, Cf, hf = cyl_light(L, cx, hh, top, base, L0, -46, glows=[] if plain else wl,
                           gpad=(3.0, 3.5) if half < 9 else (4.5, 5.5))      # 细塔上窗光晕小一圈
    k = np.zeros(L.xx.shape)
    if not plain:
        wsr = [(half * math.asin(uw), wy + wh / 2.0 - sag_b * math.sqrt(1 - uw * uw), w0 / 2.0 + 4, wh / 2.0 + 4)
               for (wx, wy, wp, wh, _l, uw, w0) in wl]
        dsr = [] if door is None else [(0.0, base - door[1] / 2.0 - sag_b, door[0] / 2.0 + 5, door[1] / 2.0 + 4)]
        k, sm = wall_stones(L, m, u, s, ring, foot, wsr, dsr, seed, small=half < 9)
        k += rain_streaks(L, m & ~sm, [w_[:5] for w_ in wl], seed + 2)
    cyl_paint(L, m, Lf, Cf, hf, k)
    rim_left(L, m & (ring0 < foot - 12), PINK_RIM, y0=top + 4)
    glass = np.zeros(m.shape, bool)
    for w_ in wl:
        if plain:
            plain_window(L, w_[0], w_[1], w_[2], w_[3], w_[4])
        else:
            glass |= draw_cyl_window(L, half, w_, sill=True, depth=3)
    if door is not None and not plain:
        dw, dh, dlit = door
        stone_door(L, int(round(cx - dw / 2.0)), base, dw, dh, dlit, pal=PW)
    if crenel:
        hp = half + 2
        sag_p = CYL_SAG * hp
        up, ringp, sp, arcp = cyl_coords(L, cx, hp)
        # 护墙在塔身顶上投一圈影（托石下面）
        shade(L, m & (ring < top + 4 + 2 * np.clip((u + 1) / 2, 0, 1)) & ~glass, dh=-10.0)
        # 尖顶从护墙里面长出来（先画，护墙压在它前面）；比护墙窄一圈，雉堞的缺口里看得到后面的檐口和天
        Rf = cone_roof_v2(L, cx, top - 9, half - 3, cap_h, roof, seed + 3, plain=plain, flare=1.0)
        # 托石：护墙下面一圈小石块（绕着转，靠两边变窄），块和块之间是暗的缝隙（护墙挑出去的底面）
        band_ = (np.abs(L.xx - cx) < hp) & (ringp >= top - 2) & (ringp < top + 1)
        cb = band_ & (np.mod(sp + 1.0, 4) < 2)
        cyl_paint(L, band_ & ~cb, *cyl_light(L, cx, hp, top - 10, base, L0 - 0.07, -56), np.zeros(m.shape))
        cyl_paint(L, cb, *cyl_light(L, cx, hp, top - 10, base, L0 - 0.02, -50), np.zeros(m.shape))
        # 护墙 + 雉堞（雉堞 4 行高、缺口 2 格，绕着转过去）
        pw = (np.abs(L.xx - cx) < hp) & (ringp >= top - 10) & (ringp < top - 2)
        notch = pw & (ringp < top - 6) & (np.mod(sp + 1.5, 5) >= 3)
        pw &= ~notch
        # 缺口里看到的是对面那圈护墙的里侧（背光，暗两档）；最两边的缺口外面就是天，不画
        walk = (np.abs(L.xx - cx) < hp - 1.5) & (ringp >= top - 11) & (ringp < top - 10)   # 雉堞后面一行：对面护墙的顶（背光）
        cyl_paint(L, (notch | walk) & (np.abs(L.xx - cx) < hp - 1.5), *cyl_light(L, cx, hp, top - 12, base, L0 - 0.07, -58),
                  np.zeros(m.shape))
        kp = np.zeros(m.shape)
        kp[pw & ~np.roll(pw, 1, axis=0)] = 1.0                       # 雉堞顶面接着天光，亮一档
        cyl_paint(L, pw, *cyl_light(L, cx, hp, top - 12, base, L0 + 0.035, -46), kp)
        rim_left(L, pw, PINK_RIM)                                     # 只描最左边那条轮廓（不描每个雉堞）
        return {"cx": cx, "top": Rf["tip_y"] + 4, "base": base, "tip": Rf["tip"], "rw": Rf["R"], "cap_h": cap_h, "w": w,
                "hw": Rf["hw"]}
    Rf = cone_roof_v2(L, cx, top + 1, half, cap_h, roof, seed + 3, plain=plain)
    shade(L, m & (L.yy < Rf["eave_bot"] + 2 + 3 * np.clip((u + 1) / 2, 0, 1)) & ~glass & ~Rf["mask"], dh=-10.0)
    Rf = cone_roof_v2(L, cx, top + 1, half, cap_h, roof, seed + 3, plain=plain)     # 影压完再盖一次屋顶（影不压到檐口上）
    return {"cx": cx, "top": Rf["tip_y"] + 4, "base": base, "tip": Rf["tip"], "rw": Rf["R"], "cap_h": cap_h, "w": w,
            "hw": Rf["hw"]}


def plane_light(L: Layer, top, base, L0, h0, glows=()):
    """平的一面墙（朝着镜头）：整面一个光，只有上下的变化（上面接天光暗一档偏冷，下面接云的反光亮一档偏粉）+ 亮窗晕开"""
    v = np.clip((L.yy - top) / max(base - top, 1), 0, 1)
    vq = np.round((-0.025 * (1 - v) ** 1.6 + 0.045 * v ** 2.2) / STEP_L)
    gq = np.zeros(L.xx.shape)
    for (x, y, w, h, lit) in glows:
        if lit:
            d = np.hypot((L.xx - (x + w / 2.0)) / (w / 2.0 + 5.0), (L.yy - (y + h * 0.62)) / (h / 2.0 + 5.5))
            gq = np.maximum(gq, np.round(0.07 * np.clip(1 - d, 0, 1) ** 0.8 / STEP_L))
    g = np.clip(gq / 2.0, 0, 1)
    Lf = L0 + (vq + gq) * STEP_L
    hf = (h0 + vq * HUE_STEP) * (1 - g) + 38 * g
    Cf = 0.05 + 0.006 * vq + 0.015 * g
    return Lf, Cf, np.round(hf / HUE_STEP) * HUE_STEP


def house_v2(L: Layer, cx, base, w, floors=2, roof_h=22, roof="terra", seed=0, lit=(True, False, True), plain=False,
             door_lit=False):
    """半木结构的窄房子（山墙朝外），按自己的形体分面受光：正面一个面（石砌底层 + 每层灰泥木框架，每层往外挑 1 格、
    挑出去的那层在下面一层墙上投两行影）；右边露一条侧墙（暗两档、偏冷），右坡的屋面从屋脊斜着压到侧墙上（屋顶有厚度）；
    山墙前沿是三行厚的瓦边（上面一行亮、下面暗），瓦边在山墙上投一道斜的影。"""
    rng = np.random.default_rng(seed)
    g_h, f_h = 16, 15
    sd = 0 if plain else 4
    x0 = int(round(cx - w / 2.0))
    X, Y = _xy(L)
    top_all = base - g_h - floors * f_h
    # ---- 底层（石砌）
    m0 = (L.xx >= x0) & (L.xx < x0 + w) & (L.yy >= base - g_h) & (L.yy < base + 6)
    dx = int(cx - 5 + (rng.integers(-3, 4) if w > 24 else 0))
    Lf, Cf, hf = plane_light(L, top_all, base, HOUSE_STONE_L0, -46)
    k = np.zeros(X.shape)
    if not plain:
        nz = smooth_noise(L.h, L.w, 6, 6, seed=seed + 1)
        sm = (np.minimum(L.xx - x0, x0 + w - L.xx) + 1.5 * nz < 4) | (L.yy + 2 * nz >= base - 4)
        sm |= (np.abs(L.xx - (dx + 5)) < 9 + 2 * nz) & (L.yy >= base - 19)
        k = stone_texture(L, m0, sm, seed + 2, sx=(4, 8), sy=(3, 4))
        k[conn4((k < 0) & m0) & m0] = -1
    cyl_paint(L, m0, Lf, Cf, hf, k)
    rim_left(L, m0, PINK_RIM, y1=base - 2)
    side_rows = [(x0 + w, base - g_h, base + 6)]
    shadows = []
    top = base - g_h
    xa, xb = x0, x0 + w
    wins = []
    for f in range(floors):
        xa, xb = xa - 1, xb + 1
        yb, ya = top, top - f_h
        mf = (L.xx >= xa) & (L.xx < xb) & (L.yy >= ya) & (L.yy < yb)
        win = []
        nw = 2 if (xb - xa) >= 26 else 1
        for kk in range(nw):
            wx = int(xa + (xb - xa) * (kk + 1) / (nw + 1) - 2.5)
            win.append((wx, ya + 4, 5, 8, bool(lit[(f + kk) % len(lit)])))
        Lf, Cf, hf = plane_light(L, top_all, base, PLASTER_L0, -34, glows=[] if plain else win)
        cyl_paint(L, mf, Lf, Cf, hf, np.zeros(X.shape))
        tm = mf & ((L.xx < xa + 2) | (L.xx >= xb - 2) | (L.yy >= yb - 2) | (L.yy < ya + 1))
        for (wx, wy, ww, wh, l_) in win:
            tm |= mf & (((L.xx >= wx - 3) & (L.xx < wx - 1)) | ((L.xx >= wx + ww + 1) & (L.xx < wx + ww + 3)))
        if not plain:
            for (sx, sgn) in ((xa + 2, 1), (xb - 3, -1)):
                for (px_, py_) in line4(sx, yb - 3, sx + sgn * 5, ya + 2):
                    tm |= mf & ((X == px_) | (X == px_ + sgn)) & (Y == py_)
        tidx = np.full(X.shape, 2) - (L.yy >= yb - 1)
        paint(L, tm, tidx, TIMBER4)
        L.put(tm & (L.xx < xa + 1) & (L.yy < yb - 1), TIMBER4[3])
        for (wx, wy, ww, wh, l_) in win:
            if plain:
                plain_window(L, wx, wy + 2, 3, 4, l_)
            else:
                deep_window(L, wx, wy, ww, wh, l_, shutters=True, sill=False, frame_pal=PW, cross=False)
        L.rect(xa, yb, xb, yb + 1, TIMBER4[0])                          # 挑出去的楼层下面一行梁头
        shadows.append((L.xx >= xa + 1) & (L.xx < xb - 1) & (L.yy >= yb + 1) & (L.yy < yb + 3))   # 在下面一层墙上投两行影
        side_rows.append((xb, ya, yb))
        wins += win
        top = ya
    # ---- 山墙
    rw = (xb - xa) / 2.0
    ccx = (xa + xb) / 2.0
    apex = top - roof_h
    gm = poly_mask(L, [(xa, top + 0.01), (xb, top + 0.01), (ccx, apex)])
    Lf, Cf, hf = plane_light(L, top_all, base, PLASTER_L0, -34)
    cyl_paint(L, gm, Lf, Cf, hf, np.zeros(X.shape))
    L.put(gm & ((np.abs(L.xx - ccx) < 1.0) | (L.yy >= top - 2)), TIMBER4[2])
    if roof_h >= 16 and not plain:
        ow = ellipse(L, ccx, top - roof_h * 0.45, 2.6, 2.6)
        L.put(ow, LAMP[2] if lit[0] else lch_hex(0.24, 0.04, -60))
        L.put(ow & (L.yy < top - roof_h * 0.45 - 0.5), LAMP[3] if lit[0] else lch_hex(0.30, 0.04, -60))
    # ---- 右边的侧墙：每一截跟着那一层的右沿，暗两档、偏冷
    if sd:
        for (xr, y0_, y1_) in side_rows:
            sm_ = (L.xx >= xr) & (L.xx < xr + sd) & (L.yy >= y0_) & (L.yy < y1_)
            sm_ &= L.a[..., 3] == 0
            Lf, Cf, hf = plane_light(L, top_all, base, (HOUSE_STONE_L0 if y1_ > base - 1 else PLASTER_L0) - 0.07, -58)
            cyl_paint(L, sm_, Lf, Cf * 0.9, hf, np.zeros(X.shape))
    for sh_ in shadows:
        shade(L, sh_ & (L.a[..., 3] > 0))
    # ---- 屋顶：右坡的屋面（从屋脊往右压到侧墙上）+ 山墙前沿三行厚的瓦边
    Ls, hs, Cs, fas_c = ROOF_KIND[roof]
    ap = apex - 3.5
    if sd:
        plane = poly_mask(L, [(ccx, ap), (ccx + sd, ap), (xb + 3 + sd, top + 2), (xb + 3, top + 2)])
        L.put(plane, lch_hex(Ls[3], Cs[3], hs[3]))
        L.put(plane & (L.yy < ap + 1.5), lch_hex(Ls[2], Cs[2], hs[2]))           # 屋脊那一行接着天光
        L.put(plane & (L.yy >= top), lch_hex(*fas_c))
        # 屋面压在侧墙上投一道影
        shade(L, (L.xx >= xb) & (L.xx < xb + sd) & (L.yy >= top + 2) & (L.yy < top + 4) & (L.a[..., 3] > 0) & ~plane)
    outer = poly_mask(L, [(xa - 3, top + 2), (ccx, ap), (xb + 3, top + 2)])
    inner = poly_mask(L, [(xa + 0.5, top + 2), (ccx, apex + 0.5), (xb - 0.5, top + 2)])
    rm = outer & ~inner
    # 瓦边在山墙上投一道斜的影（沿着两条坡、往里两格）
    inner2 = poly_mask(L, [(xa + 3.5, top + 2), (ccx, apex + 3.5), (xb - 3.5, top + 2)])
    shade(L, gm & inner & ~inner2 & (L.yy < top - 2))
    left = L.xx < ccx
    L.put(rm & left, lch_hex(Ls[1], Cs[1], hs[1]))
    L.put(rm & ~left, lch_hex(Ls[3], Cs[3], hs[3]))
    edge_in = conn4_in(rm & np.roll(inner, -1, 0), rm)                # 瓦边的底面（贴着山墙那一行）：檐底的暗面，斜着也连成线
    L.put(edge_in, lch_hex(*fas_c))
    L.put(conn4_in(rm & ~np.roll(rm, 1, axis=0) & left, rm & left) & ~edge_in, lch_hex(Ls[0], Cs[0], hs[0]))      # 左坡上沿接着光
    rim_left(L, rm, PINK_RIM, y0=ap + 3)
    # 烟囱：立在右坡的屋面上，自己也有一条侧面
    chx = int(ccx + rw * 0.45)
    cy0 = int(top - roof_h * 0.45 - 6)
    ch = (L.xx >= chx) & (L.xx < chx + 4) & (L.yy >= cy0) & (L.yy < top - roof_h * 0.2) & ~(inner & (L.yy >= top - roof_h * 0.45))
    Lf, Cf, hf = plane_light(L, top_all, base, HOUSE_STONE_L0 + 0.02, -46)
    cyl_paint(L, ch, Lf, Cf, hf, np.zeros(X.shape))
    if sd:
        chs = (L.xx >= chx + 4) & (L.xx < chx + 6) & (L.yy >= cy0 + 1) & (L.yy < top - roof_h * 0.2 + 2) & ~(inner & (L.yy >= top - roof_h * 0.45))
        cyl_paint(L, chs, Lf - 0.07, Cf, hf - 12, np.zeros(X.shape))
    L.rect(chx - 1, cy0 - 1, chx + 5 + (1 if sd else 0), cy0 + 1, PW[4])
    L.rect(chx - 1, cy0, chx + 5 + (1 if sd else 0), cy0 + 1, PW[2])
    if not plain:
        stone_door(L, dx, base, 10, 14, door_lit, pal=PW)
    return {"cx": ccx, "top": apex, "base": base, "tip": (ccx, apex - 3), "rw": rw, "cap_h": roof_h, "w": w,
            "chimney": (chx, cy0)}


def mill_v2(L: Layer, cx, base, wb, wt, h, seed=0, stage=0.45, wins=(), door=(11, 22, True), plain=False, cap_h=None):
    """荷兰式八角风车塔（静的部分）：往上收的八角塔身，四个看得到的面一档一档暗下去（面和面之间是竖的棱，不是色带渐变）；
    抹灰为主、露几处石块；腰上一圈收帆台是往下弯的木台（栏杆、立柱跟着转过去）；帽子是圆锥瓦顶（钟形檐、尖帽），
    檐下投一圈弯的影；帽前伸出风轴的轴头。返回 (轴头, info)。"""
    cx = int(cx)
    top = base - h
    t = np.clip((base - L.yy) / h, 0, 1)
    half = wb / 2.0 - (wb - wt) / 2.0 * t
    m = (np.abs(L.xx - cx) < half) & (L.yy >= top) & (L.yy < base + 6)
    u = np.clip((L.xx - cx) / np.maximum(half, 0.5), -1, 1)
    face = band(u, (-0.707, 0.0, 0.707))
    v = np.clip((L.yy - top) / h, 0, 1)
    vq = np.round((-0.025 * (1 - v) ** 1.6 + 0.045 * v ** 2.2) / STEP_L)
    wl = []
    for i, (dy, ww, wh, lit) in enumerate(wins):
        if door is not None and top + dy + wh > base - door[1] - 3:      # 撞上门的那扇不开
            continue
        xc = cx + (-0.36 if i % 2 == 0 else 0.36) * (wb / 2.0)
        wp = max(3, int(round(ww * 0.92)))
        wl.append((int(math.floor(xc - wp / 2.0 + 0.5)), top + dy, wp, wh, lit))
    gq = np.zeros(L.xx.shape)
    for (x, y, w_, h_, lit) in wl:
        if lit and not plain:
            d = np.hypot((L.xx - (x + w_ / 2.0)) / (w_ / 2.0 + 3.5), (L.yy - (y + h_ * 0.62)) / (h_ / 2.0 + 4.0))
            gq = np.maximum(gq, np.round(0.07 * np.clip(1 - d, 0, 1) ** 0.8 / STEP_L))
    g = np.clip(gq / 2.0, 0, 1)
    Lf = WALL_L0 + 0.01 + np.array([0.07, 0.025, -0.02, -0.065])[face] + (vq + gq) * STEP_L
    hf = (-44 + np.array([20, 6, -6, -16])[face] + vq * HUE_STEP) * (1 - g) + 38 * g
    hf = np.round(hf / HUE_STEP) * HUE_STEP
    Cf = np.array([0.06, 0.052, 0.047, 0.045])[face] + 0.015 * g
    k = np.zeros(L.xx.shape)
    if not plain:
        hb_ = wb / 2.0
        uu, ring, s, _ = cyl_coords(L, cx, half)
        wsr = [(hb_ * math.asin(np.clip((x + w_ / 2.0 - cx) / hb_, -1, 1)), y + h_ / 2.0, w_ / 2.0 + 4, h_ / 2.0 + 4) for (x, y, w_, h_, l_) in wl]
        dsr = [] if door is None else [(0.0, base - door[1] / 2.0, door[0] / 2.0 + 5, door[1] / 2.0 + 4)]
        k, sm = wall_stones(L, m, u, s, ring, base + 6, wsr, dsr, seed, small=wb < 30)
        k += rain_streaks(L, m & ~sm, wl, seed + 2)
    cyl_paint(L, m, Lf, Cf, hf, k)
    rim_left(L, m, PINK_RIM, y0=top + 4, y1=base - 8)
    glass = np.zeros(m.shape, bool)
    for (x, y, w_, h_, lit) in wl:
        if plain:
            plain_window(L, x, y, w_, h_, lit)
        else:
            glass |= deep_window(L, x, y, w_, h_, lit, shutters=False, frame_pal=PW) & lit
    if door is not None and not plain:
        stone_door(L, int(round(cx - door[0] / 2.0)), base, door[0], door[1], door[2], pal=PW)
    # 收帆台：一圈往下弯的木台（台面两行、前沿亮一行）+ 栏杆（一圈弯的扶手 + 绕着转的立柱）+ 两根斜撑
    if not plain:
        sy = int(round(base - h * stage))
        hs = wb / 2.0 - (wb - wt) / 2.0 * stage
        pw = hs + 6
        ud, ringd, sdd, _ = cyl_coords(L, cx, pw)
        inside = np.abs(L.xx - cx) < pw
        deckm = inside & (ringd >= sy) & (ringd < sy + 2)
        rail = conn4(inside & (ringd >= sy - 6) & (ringd < sy - 5)) & inside
        for sg in (-1, 1):
            for (px_, py_) in line4(cx + sg * (pw - 1) - (1 if sg > 0 else 0), sy + 2, cx + sg * (hs - 1), sy + 9):
                L.px(px_, py_, TIMBER4[2])
                L.px(px_ + 1, py_, TIMBER4[2])                       # 两格宽的一根（不拼两种颜色的斜台阶）
        nposts = int(math.pi * pw / 4)
        for q in range(nposts + 1):
            a = -math.pi / 2 + math.pi * q / nposts
            px_ = int(math.floor(cx + pw * math.sin(a) - (0.5 if a > 0 else 0)))
            px_ = min(max(px_, int(cx - pw)), int(cx + pw) - 1)
            ar = math.sqrt(max(0.0, 1 - ((px_ + 0.5 - cx) / pw) ** 2))
            y0_ = int(round(sy - 5 + CYL_SAG * pw * ar))
            L.rect(px_, y0_, px_ + 1, int(round(sy + CYL_SAG * pw * ar)), WHEAT[2])
        L.put(rail, WHEAT[3])
        deckm = inside & (ringd >= sy) & (ringd < sy + 3)                  # 三行：前沿亮、中间、底面暗（弧的台阶处补成四邻接）
        top_r = conn4_in(deckm & ~np.roll(deckm, 1, axis=0), deckm)
        bot_r = conn4_in(deckm & ~np.roll(deckm, -1, axis=0), deckm) & ~top_r
        L.put(deckm, WHEAT[2])
        L.put(top_r, WHEAT[4])
        L.put(bot_r, WHEAT[1])
        shade(L, m & (ringd >= sy + 2) & (ringd < sy + 4) & ~glass)
    # 帽子：圆锥瓦顶（低一点、钟形檐），檐下一圈影
    cap_h = cap_h or int(round(wt * 0.75 + 4))
    Rf = cone_roof_v2(L, cx, top + 1, wt / 2.0, cap_h, "terra", seed + 3, plain=plain)
    uu = np.clip((L.xx - cx) / np.maximum(half, 0.5), -1, 1)
    shade(L, m & (L.yy < Rf["eave_bot"] + 2 + 3 * np.clip((uu + 1) / 2, 0, 1)) & ~glass & ~Rf["mask"], dh=-10.0)
    Rf = cone_roof_v2(L, cx, top + 1, wt / 2.0, cap_h, "terra", seed + 3, plain=plain)
    hub = (cx, top - int(cap_h * 0.35))
    L.put(ellipse(L, hub[0], hub[1], 3.2 if wb >= 30 else 2.4, 3.2 if wb >= 30 else 2.4), TIMBER4[1])
    return hub, {"cx": cx, "top": Rf["tip_y"] + 4, "base": base, "tip": Rf["tip"], "rw": Rf["R"], "cap_h": cap_h, "w": wb,
                 "hw": Rf["hw"]}


# ======================================================================= 云台（11-02，结局三「走一圈」那天才开放）
#   广场再往外、住处那头的尽头：一屏纯云，没有建筑和人。平的云面往前铺，尽头一段木栈桥伸出去，桥下是更低的云海。
#   小镇原来的四张图（town_far / back / main）一像素不动：云台是另外三张图，接在它们右边（room.json 里层带 x）。
#   接缝：地面和远处那排用「缝合」——新图左边先盖一段和原图一样的像素，再沿颜色差最小的一条竖缝（每行最多挪一格）
#   换成新画的云，看不出缝；后排房子 x1748 那栋在原图边上被切了一半，用一大团暗面朝外的积云把它和接缝一起埋住。
#   晨要比背景亮：云台这段没有房子挡着，作者那层飘过来的 midfar 云（cloud_midfar_over，亮粉）会正好飘到晨头后面
#   （量出来最低 149）→ 在它前面、后排云丘后面盖一张 deck_dim：小镇天里最深的那个靛紫，透明度从 1760 往右 120 像素
#   慢慢加到 DECK_DIM_A（约压暗一档），天、远处的云、飘过来的云一起暗一档；晨、地面、栈桥、后排云丘不受影响。
DECK_X0 = W                               # 小镇原图到这里为止
ROOM_W = W + 480                          # 加一屏
PIER = (2028, 2204)                       # 栈桥（晨能走到 2190）
DECK_WALK_END = 2190
DECK_END = 2176                           # 走到这里触发 e3_round
DECK_DIM_A = 0.16                         # 压暗一档：盖一层深靛紫的透明度
DECK_DIM_RAMP = 120                       # 从小镇边上往右多少像素慢慢加满（不是一条硬边）
SEAM = 56                                 # 缝合区多宽


def stitch(A, B):
    """A、B 是同一块区域（h×w×4）：返回 mask，True = 用 A。沿 |A−B| 最小的一条竖缝切（每行最多左右挪一格，缝左边用 A）。
    最左一列一定是 A、最右一列一定是 B。"""
    d = np.abs(A.astype(np.int32) - B.astype(np.int32)).sum(-1).astype(np.float64)
    h, w = d.shape
    d[:, 0] = d[:, -1] = 1e9
    acc = d.copy()
    for y in range(1, h):
        p = acc[y - 1]
        best = np.minimum(p, np.minimum(np.r_[np.inf, p[:-1]], np.r_[p[1:], np.inf]))
        acc[y] += best
    seam = np.zeros(h, int)
    seam[-1] = int(np.argmin(acc[-1]))
    for y in range(h - 2, -1, -1):
        x = seam[y + 1]
        lo, hi = max(x - 1, 1), min(x + 2, w - 1)
        seam[y] = lo + int(np.argmin(acc[y, lo:hi]))
    return np.arange(w)[None, :] < seam[:, None]


def stitch_into(new: Layer, old_arr, old_x0, n=SEAM):
    """new（ox = 大图里的起点）和 old_arr（大图里的整张）在 old_x0 起的 n 列里缝起来；old_x0 左边整段照抄原图。
    缝只量缝上的颜色差，不管缝左边丢掉了什么：缝合区里别有原图的房子（远处那排只留最后 14 列）。"""
    A = old_arr[:, old_x0:old_x0 + n]
    c0 = old_x0 - new.ox
    B = new.a[:, c0:c0 + n].copy()
    m = stitch(A, B)
    B[m] = A[m]
    new.a[:, c0:c0 + n] = B
    new.a[:, :c0] = old_arr[:, new.ox:old_x0]


def deck_terrain(x):
    """云台的云面：照小镇的起伏接过来，到栈桥前慢慢沉下去（桥伸到更低的云海上）"""
    y = 226 + 0.9 * math.sin(x / 41.0) + 0.5 * math.sin(x / 13.0 + 1.0)
    t = np.clip((x - (PIER[0] + 20)) / 70.0, 0, 1)
    return y + 20 * t * t * (3 - 2 * t)


def build_deck_main(town_main):
    x0 = DECK_X0 - SEAM
    w = ROOM_W - x0
    D = Layer(w, H, x0, 0)
    G = ground_cloud(w, lambda x: deck_terrain(x + x0), 41, flats=[(0, PIER[0] - x0 + 30)])
    G.ox = x0
    D.over(G)
    # 栈桥：和停机台同一种木台（台面一块块木板、前沿一道亮、正面横梁、木桩插进云里），只是窄长，尽头两根系船桩
    deck(D, PIER[0], PIER[1], 221, GROUND, 256, 17)
    bollard(D, PIER[1] - 8, 222)
    lip = lip_cloud(w, PIER[0] - 10 - x0, PIER[0] + 26 - x0, 229, 19, r=(4, 7))   # 桥头压在云面里（不是搁在云上的一块板）
    lip.ox = x0
    D.over(lip)
    sea = lip_cloud(w, PIER[0] + 14 - x0, w + 8, 247, 23, r=(6, 11))     # 桥身下面那层更低的云海，木桩没进去
    sea.ox = x0
    D.over(sea)
    stitch_into(D, town_main.a, DECK_X0 - SEAM)
    despeckle(D)
    return D


def build_deck_back(town_back):
    """后排（视差 1）：把 build_back 在加宽的画布上重跑一遍（房子、云丘的随机数和原来一样，只是画布往右多了一屏），
    右边那截就是同一片云丘接着往前铺、没有房子；x1748 那栋在原图边上被切掉的半边也就补全了。再和原图缝合。"""
    global W
    w0, saved = W, list(ANIMS)
    W = ROOM_W
    try:
        wide = build_back()[0]
    finally:
        W = w0
        ANIMS[:] = saved
    x0 = DECK_X0 - SEAM
    B = Layer(ROOM_W - x0, H, x0, 0)
    B.a[:] = wide.a[:, x0:]
    stitch_into(B, town_back.a, x0)
    return B


def build_deck_far(town_far):
    """远处那排（视差 FAR_SC）：接着 town_far 的云丘往右，没有房子（暗一档由 deck_dim 统一压）。"""
    x0 = town_far.w - SEAM - 4
    w = int(math.ceil(480 + (ROOM_W - 480) * FAR_SC)) + 4 - x0
    rng = np.random.default_rng(61)
    heaps = []
    x = 18.0
    while x < w:
        heaps.append((x, 213, rng.uniform(30, 60), rng.uniform(4, 11)))
        x += rng.uniform(34, 60)
    F = Layer(w, H, x0, 0)
    M = mound_cloud(w, heaps, 7, deck=207, lift=0.03)
    M.ox = x0
    F.over(M)
    # town_far 云丘下面那截深色（和原图同一个颜色往下铺满），不然露出后面作者的云
    col = town_far.a[:, -1]
    for y in range(H):
        if col[y, 3] == 255 and y > 200:
            m = F.a[y, :, 3] < 255
            F.a[y, m] = col[y]
    stitch_into(F, town_far.a, town_far.w - 14, 14)
    despeckle(F)
    return F


def build_deck_dim():
    w = ROOM_W - DECK_X0
    t = np.clip((np.arange(w) + 0.5) / DECK_DIM_RAMP, 0, 1)
    a = np.zeros((H, w, 4), np.uint8)
    a[..., :3] = hexc("#1d1530")
    a[..., 3] = np.round(255 * DECK_DIM_A * t * t * (3 - 2 * t))[None, :]
    return a


def deck_layers():
    """room.json 里云台那三层（插在小镇对应的层后面）"""
    return {
        "town_far": {"id": "deck_far", "img": "res://art/cloud_town/deck_far.png", "scroll": FAR_SC, "y": 0, "x": DECK_FAR_X[0]},
        "cloud_midfar_over": {"id": "deck_dim", "img": "res://art/cloud_town/deck_dim.png", "scroll": 1.0, "y": 0, "x": DECK_X0},
        "town_back": {"id": "deck_back", "img": "res://art/cloud_town/deck_back.png", "scroll": 1.0, "y": 0, "x": DECK_X0 - SEAM},
        "town_main": {"id": "deck_main", "img": "res://art/cloud_town/deck_main.png", "scroll": 1.0, "y": 0, "x": DECK_X0 - SEAM},
    }


DECK_FAR_X = [0]


# ======================================================================= 开始界面的下落（11-06 作者：点开始后画面往下移、到黑、再移就到了森林）
#   标题的背景就是这个小镇（scripts/title_cloud.gd 建一份 town 的 room_stage）。点开始以后镜头往下：小镇往上走，这张图接在
#   小镇底下（y = 270 往下）跟着上来：一排排云团，一排比一排暗（颜色还是小镇云那条色阶）→ 全黑 → 云底：几层波浪边的半透明，
#   从黑转成森林最上面那种深青绿，透出下面的森林。一张竖长图，title_cloud.gd 用同样的数（TD_* 也写在那边）。
TD_W = 600              # 比一屏宽（标题镜头左右漂 ±18）
TD_OVER = 20            # 第一排的云顶比小镇图底边高多少（盖住接缝）
TD_ROWS = 5
TD_ROW_GAP = 54
TD_BLACK = 96           # 全黑那一段多高
TD_UNDER = 90           # 云底那几层多高（透出森林）
TD_H = TD_OVER + TD_ROWS * TD_ROW_GAP + 34 + TD_BLACK + TD_UNDER
TD_LIT = 30             # 每排云顶下面多少行有明暗，再往下就是这排最暗的颜色


def build_title_descent():
    L = Layer(TD_W, TD_H)
    black = np.array(CA.from_lch(0.03, 0.012, 300), np.uint8)
    y_end = TD_OVER + TD_ROWS * TD_ROW_GAP + 34
    for k in range(TD_ROWS):
        u = k / (TD_ROWS - 1.0)
        rng = np.random.default_rng(910 + k)
        y0 = TD_OVER + k * TD_ROW_GAP
        F = cloud_field(TD_W, TD_H)
        x = -PAD + rng.uniform(0, 12)
        while x < TD_W + PAD:
            r = rng.uniform(22, 40)
            F.new_group()
            F.row = k
            F.cauli(x + PAD, y0 + r * 0.72 + rng.uniform(-5, 5), r, 20 + rng.uniform(0, 8), rng, sq=0.72, depth=2, kids=(3, 6),
                    ks=(0.28, 0.5), dark=0.0, rmin=3.0, spread=(-170, -10), ref=y0, unit=14)
            x += r * rng.uniform(0.85, 1.2)
        pal = CA.cloud_pal(0.09 - 0.06 * u, 0.36 - 0.29 * u, 7, C_lo=0.045 - 0.025 * u, C_hi=0.08 - 0.05 * u, h_lo=286, h_hi=348)
        R = render_field(F, TD_W, pal, body=4, rim=(1.5, 3.0), crease=2.0, bands=(0.6, 1.5, 2.6, 3.6), run_bands=(4, 10, 18, 28))
        # 11-06 作者：「视差问题」。原来每排的身体切了底、团和团之间有缝，透出后面走得慢的层，像小云块在乱飘；团的身体是竖直的柱子，留下竖线和竖崖。
        # 现在：云顶一列一列量出来，相邻两列最多差 3 行（竖崖变成缓坡），顶下 TD_LIT 行以内是原来的明暗，再往下一直到图底都是这排最暗的颜色（不透明、没有竖线）。
        has = (R.a[..., 3] > 0).any(0)
        top = np.where(has, np.argmax(R.a[..., 3] > 0, 0), TD_H).astype(np.int64)
        for c in range(1, TD_W):
            top[c] = min(top[c], top[c - 1] + 3)
        for c in range(TD_W - 2, -1, -1):
            top[c] = min(top[c], top[c + 1] + 3)
        dark0 = np.array(pal[0], np.uint8)
        rim = np.array(pal[3], np.uint8)
        for c in range(TD_W):
            t = int(top[c])
            col = R.a[:, c]
            miss = (col[t:, 3] < 255)
            col[t:][miss, :3] = rim
            col[t:, 3] = 255
            col[t + TD_LIT:, :3] = dark0
        L.over(R)
    L.a[y_end:, :, :3] = black
    L.a[y_end:, :, 3] = 255
    # 云底：几层波浪边，一层比一层透、一层比一层偏森林的深青绿；每层是整块平色（没有抖动、没有点）
    under = np.array(CA.from_lch(0.13, 0.022, 170), np.float32)
    top = TD_H - TD_UNDER
    xs = np.arange(TD_W, dtype=np.float32)
    n = 7
    L.a[top:] = 0
    L.a[top:, :, :3] = black
    L.a[top:, :, 3] = 255
    for i in range(n):
        k = (i + 1.0) / n
        wave = 5.5 * np.sin(xs / (37.0 + 5 * i) + 1.7 * i) + 3.0 * np.sin(xs / (13.0 + 2 * i) + 0.9 * i)
        y = np.round(top + TD_UNDER * (i + 0.6) / n + wave).astype(int)
        col = np.round(black * (1 - k) + under * k).astype(np.uint8)
        a = int(round(255 * (1.0 - k) ** 0.9))
        for c in range(TD_W):
            L.a[y[c]:, c, :3] = col
            L.a[y[c]:, c, 3] = a
    despeckle(L)
    fix_speckles(L.a)
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    ap.add_argument("--only-preview", action="store_true")
    ap.add_argument("--sample", default="", help="只出晨住的塔的样稿（不写 art/）")
    ap.add_argument("--title-descent", action="store_true", help="只重画开始界面下落那张图（art/cloud_town/title_descent.png）")
    args = ap.parse_args()
    if args.title_descent:
        save_png(build_title_descent().a, "art/cloud_town/title_descent.png")
        return
    if args.sample:
        sample(Path(args.sample))
        return
    if not args.only_preview:
        build()
    if args.preview:
        preview(Path(args.preview))


if __name__ == "__main__":
    main()
