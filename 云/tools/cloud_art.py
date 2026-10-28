"""云层视差（第三颗星球，最后一站）。以后改云层图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/cloud_art.py [--preview 目录]

输出 art/cloud/*.png（1 倍）。做法照 tools/forest_art.py（函数是拷过来的，没有 import 它）。

画面：晨走在一片高处的云顶上，太阳刚落下去。
- 天：顶上近黑的靛紫，往下变紫、变玫瑰紫，地平线（y≈141）左边剩一团余晖（GLOW，屏幕坐标固定，第一眼的焦点），
  天上已经出星星（结局的伏笔）。sky 层不随镜头动。
- 高空：几条被余晖从下面照亮的薄云，慢慢漂，挡住后面的星星。
- 远处：几根从云海里冒出来的石针，逆着余晖是剪影，朝光那边一条玫瑰色的边；右边一座很高的积雨云柱，
  身体几乎融进夜空，里面偶尔一闪冷紫的闪电（flash.png，Godot 里开关）。
- 云海：四层一团团的云顶从地平线往下铺开（far / midfar / mid / near），越远越亮、越淡（贴着余晖），
  越近越暗（已经进了夜里）。晨身后那条（y 186~226）只剩很暗的近处云海。
- main：能走的云顶。上沿一条受光边就是地面，往下一层层更暗的云团沉进黑里。地面高度 = 每列第一个不透明像素，
  Godot 里也是这样从图里读出来的（scripts/cloud_test.gd），不用两边各写一遍公式。
- front：最前面几团近黑的云，从底边把画面框住。
光全场从左边低处来（余晖那边）：云团左上受光，右下背光；亮面偏暖（玫瑰），暗面偏冷（蓝紫）。
除了天，每层宽 960、左右无缝。所有随机都固定 seed。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.palette import from_hex, oklab_to_srgb, ramp, to_lab  # noqa: E402

W, H = 960, 270
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "cloud"
CHEN = ROOT / "art" / "characters" / "chen" / "chen.png"

# 层名 -> 跟镜头的比例；DRIFT = Godot 里 Parallax2D.autoscroll.x（像素 / 秒，负 = 往左漂）
SCROLL = {"sky": 0.0, "high": 0.02, "spires": 0.04, "far": 0.08, "midfar": 0.18, "mid": 0.36, "near": 0.6,
          "main": 1.0, "front": 1.4}
DRIFT = {"high": -1.5, "far": -0.8, "midfar": -1.6, "mid": -2.6, "near": -4.0}
HORIZON = 141

# 光从左上来（余晖在地平线左边）。指向光源的方向，屏幕坐标 y 朝下。
_L = np.array([-0.82, -0.57])
LIGHT = _L / np.linalg.norm(_L)
# 像素云的明暗：一个像素离「朝光那边的边」有多远（沿光的方向走几步出团）决定它亮几档，
# 所以亮面是贴着左上轮廓的一道道月牙，宽度按像素算（不随团的大小变）；离右下的边近的一条月牙暗一档。
LIT_BANDS = (1.6, 3.6, 7.5)       # 出团距离 < 这些像素：亮 3 / 2 / 1 档
SHADE_BAND = 2.6                  # 离背光的边 < 这么多像素：暗一档


# ---------------------------------------------------------------- 颜色 / 基础（拷自 forest_art.py）

def mix(c, d, t):
    """OKLab 里从 c 往 d 走 t。"""
    a, b = to_lab(c), to_lab(d)
    return tuple(int(v) for v in oklab_to_srgb((a + (b - a) * t)[None])[0])


class Layer:
    """一层图：RGBA 数组，贴东西时左右绕回（无缝）。"""

    def __init__(self, w=W, h=H):
        self.a = np.zeros((h, w, 4), np.uint8)

    def save(self, name):
        Image.fromarray(self.a).save(OUT / f"{name}.png")


def components(mask, wrap=False):
    """8 连通区域标号（wrap = 左右绕回，给无缝图层用）。返回 (labels, n)，0 = 空。"""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        st = [(y0, x0)]
        while st:
            y, x = st.pop()
            for yy in (y - 1, y, y + 1):
                if not 0 <= yy < h:
                    continue
                for xx in (x - 1, x, x + 1):
                    if wrap:
                        xx %= w
                    elif not 0 <= xx < w:
                        continue
                    if mask[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n
                        st.append((yy, xx))
    return lab, n


BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16


# ---------------------------------------------------------------- 背景色（随高度）

# 从上往下：近黑的靛紫夜空 → 紫 → 玫瑰紫，地平线（141）最亮；地平线以下是云海上的暗紫雾，越往下越暗。
# 远处的东西往「同一高度的这一档」里褪。
BANDS = [
    (0, "#06050b"), (22, "#08060f"), (44, "#0a0814"), (64, "#0e0b1a"), (80, "#120e20"), (94, "#181227"),
    (106, "#1f1730"), (116, "#281d39"), (124, "#332342"), (131, "#3f294a"), (137, "#4d3152"), (141, "#5a3858"),
    (145, "#563659"), (151, "#4c3153"), (159, "#412a4a"), (169, "#35223f"), (181, "#291b33"), (195, "#1d1426"),
    (211, "#140e1c"), (230, "#0e0a15"),
]
SAT = 1.3                       # 整体再饱和一点（OKLab 色度乘这个数）：紫要紫，别灰


def sat(c, k=SAT):
    lab = to_lab(c).copy()
    lab[1:] *= k
    return tuple(int(v) for v in np.clip(oklab_to_srgb(lab[None])[0], 0, 255))


BAND_Y = np.array([b[0] for b in BANDS])
BAND_C = [sat(from_hex(b[1])) for b in BANDS]


def band_of(y):
    return int(np.searchsorted(BAND_Y, y, side="right") - 1)


def band_frac(y):
    i = band_of(y)
    if i + 1 >= len(BANDS):
        return i, 0.0
    return i, (y - BAND_Y[i]) / (BAND_Y[i + 1] - BAND_Y[i])


def band_color(y):
    """y 这一行背景色（不抖动，取两档插值），给画东西挑颜色用。"""
    i, f = band_frac(y)
    if f <= 0 or i + 1 >= len(BANDS):
        return BAND_C[i]
    return mix(BAND_C[i], BAND_C[i + 1], f)


# 余晖：屏幕坐标固定（sky 不随镜头动），在地平线左边；把背景往 GLOW_C 推 0~3 档。
GLOW_X, GLOW_HW = 112, 250
GLOW_Y = (58, HORIZON, 147)          # 从 58 开始亮，141 最亮，147 收掉（再往下被远处云海挡住）
GLOW_C = from_hex("#e0977e")         # 贴着地平线：暖的玫瑰橙（明显低于近白）
GLOW_HI = from_hex("#9c4f7c")        # 往上：洋红紫。余晖从下往上由橙转紫，再进夜空
GLOW_STEP = 0.125
GLOW_LEVELS = 6


def glow_level(x, y):
    x = np.asarray(x, float)
    y0, yc, y1 = GLOW_Y
    if y <= y0 or y >= y1:
        return np.zeros_like(x)
    vy = (y - y0) / (yc - y0) if y <= yc else (y1 - y) / (y1 - yc)
    vy = vy ** 1.35
    d = (x - GLOW_X) / GLOW_HW
    v = np.clip(1 - d * d, 0, 1) ** 1.5 * vy
    if y < HORIZON - 3:
        # 余晖里几道很淡的光芒（从太阳沉下去的那一点往上扇开），只在天上；明暗只差一档左右
        ang = np.arctan2(x - GLOW_X, HORIZON + 14 - y)
        ray = 0.5 * np.sin(ang * 23 + 0.7) + 0.35 * np.sin(ang * 37 + 2.1) + 0.25 * np.sin(ang * 61 + 4.0)
        v = v * (1 + 0.16 * ray * np.clip((HORIZON - y) / 30, 0, 1))
    return v


def glow_target(y):
    """余晖在 y 这一行往什么颜色推（分 4 档，免得色数爆）。"""
    f = np.clip((y - 92) / 46, 0, 1)
    f = np.floor(f * 4) / 4
    return mix(GLOW_HI, GLOW_C, f)


_GC = {}


def glow_color(band, level, y=HORIZON):
    tgt = glow_target(y)
    key = (band, level, tgt)
    if key not in _GC:
        _GC[key] = mix(BAND_C[band], tgt, GLOW_STEP * level) if level else BAND_C[band]
    return _GC[key]


_MIX = {}


def aerial(layer, t_of_y, steps=8):
    """把每个像素往同一高度的背景色里推 t(y)，相邻档之间 Bayer 抖动（拷自 forest_art.py，去掉了光斑）。"""
    a = layer.a
    ww = a.shape[1]
    xs = np.arange(ww)
    for y in range(a.shape[0]):
        tc = min(1.0, max(0.0, t_of_y(y)))
        lo = np.floor(tc * steps + 1e-6)
        fr = tc * steps - lo
        if fr < 0.2:
            fr = 0.0
        elif fr > 0.8:
            lo, fr = lo + 1, 0.0
        if lo <= 0 and fr == 0:
            continue
        m = a[y, :, 3] > 0
        if not m.any():
            continue
        t_px = (lo + (BAYER[y % 4, xs % 4] < fr)) / steps
        i, bf = band_frac(y)
        b_px = i + (BAYER[(y + 2) % 4, (xs + 1) % 4] < bf)
        keys = np.stack([t_px * steps, b_px], 1)
        out = a[y, :, :3].copy()
        for tt, bb in np.unique(keys[m], axis=0):
            sel = m & (keys[:, 0] == tt) & (keys[:, 1] == bb)
            t = tt / steps
            if t <= 0:
                continue
            tgt = BAND_C[min(int(bb), len(BAND_C) - 1)]
            cols, inv = np.unique(a[y, sel, :3], axis=0, return_inverse=True)
            new = []
            for c in cols:
                key = (tuple(int(v) for v in c), tgt, t)
                if key not in _MIX:
                    _MIX[key] = mix(key[0], tgt, min(1.0, t))
                new.append(_MIX[key])
            out[sel] = np.array(new, np.uint8)[inv.ravel()]
        a[y, :, :3] = out


# ---------------------------------------------------------------- 云团

class Puffs:
    """一层云团的「明暗」缓冲：一个个椭圆云团（下半截一直延伸到图底 = 云的身体）从后往前画，
    后画的盖住先画的。每个像素记一个明暗值（-1 暗 .. 1 亮）和它属于哪一团，最后按色阶量化。"""

    def __init__(self, w=W, h=H, bands=LIT_BANDS, shade_band=SHADE_BAND):
        self.w, self.h = w, h
        self.bands, self.shade_band = bands, shade_band
        self.tone = np.full((h, w), np.nan)
        self.pid = np.full((h, w), -1, np.int32)
        self.n = 0

    def puff(self, cx, cy, rx, ry, dark=0.0, sink=0.5, tail=True, wrap=True, light=LIGHT, bands=None,
             shade_band=None):
        """cx, cy 椭圆中心，rx, ry 半宽半高。tail = 下半截一直延伸到图底（云的身体）。
        dark = 整团压暗多少；sink = 椭圆中心往下每一个 ry 暗多少。明暗值 1 = 亮边 .. 0 = 身体 .. 负 = 背光 / 底下。"""
        x0, x1 = int(np.floor(cx - rx)) - 1, int(np.ceil(cx + rx)) + 1
        y0 = max(0, int(np.floor(cy - ry)) - 1)
        y1 = self.h if tail else min(self.h, int(np.ceil(cy + ry)) + 1)
        if y0 >= y1:
            return
        X, Y = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1))
        px, py = X + 0.5 - cx, Y + 0.5 - cy
        nx, ny = px / rx, py / ry
        r2 = nx * nx + ny * ny
        m = r2 <= 1.0
        if tail:
            m |= (ny > 0) & (np.abs(nx) <= 1.0)
        if not wrap:
            m &= (X >= 0) & (X < self.w)
        if not m.any():
            return

        def exit_dist(dx, dy):
            # 从像素沿 (dx, dy)（像素单位）走多远出椭圆：解 |(nx, ny) + t (dx/rx, dy/ry)|² = 1
            a = (dx / rx) ** 2 + (dy / ry) ** 2
            b = 2 * (nx * dx / rx + ny * dy / ry)
            c = r2 - 1
            disc = np.clip(b * b - 4 * a * c, 0, None)
            return (-b + np.sqrt(disc)) / (2 * a)

        bands = bands or self.bands
        shade_band = shade_band or self.shade_band
        t_lit = exit_dist(light[0], light[1])
        t_sh = exit_dist(-light[0], -light[1])
        b1, b2, b3 = bands
        bright = np.where(t_lit < b1, 1.0, np.where(t_lit < b2, 0.66, np.where(t_lit < b3, 0.33, 0.0)))
        bright = np.where(r2 <= 1.0, bright, 0.0)
        shade = np.where((r2 <= 1.0) & (t_sh < shade_band) & (ny > -0.6), 0.33, 0.0)
        depth = np.clip(ny, 0, None)
        tone = bright - shade - sink * depth - 0.1 * depth ** 2 - dark
        xs = X[m] % self.w if wrap else X[m]
        self.tone[Y[m], xs] = tone[m]
        self.pid[Y[m], xs] = self.n
        self.n += 1

    def cumulus(self, cx, cy, rx, ry, rng, bumps=3, dark=0.0, sink=0.32, tail=True, wrap=True, light=LIGHT):
        """一团带鼓包的积云：先画大团，再沿它的上沿（偏左上，朝光那边多）长几个小鼓包。
        小鼓包的下半截落在大团身上，压出一道暗弧：一圈圈菜花一样的轮廓就是这么来的。"""
        self.puff(cx, cy, rx, ry, dark=dark, sink=sink, tail=tail, wrap=wrap, light=light)
        if rx < 14:
            return
        for _ in range(bumps):
            a = np.radians(rng.uniform(-168, -24))
            brx = rx * rng.uniform(0.32, 0.46)
            bry = brx * rng.uniform(0.7, 0.9)
            bx = cx + np.cos(a) * rx * 0.78
            by = cy + np.sin(a) * ry * 0.78
            self.puff(bx, by + bry * 0.25, brx, bry, dark=dark, sink=0.55, tail=False, wrap=wrap, light=light)

    def render(self, pal, lo=-0.5, hi=1.0, rim=0, rim_min=0.5, top_cap=None):
        """明暗值线性映射到色阶（lo -> 0 档，hi -> 最亮档）。每团的上沿（上面一格不是自己）且不太背光的地方
        再亮 rim 档：一团团的受光边。top_cap = 最亮能用到第几档（默认最后一档留给上沿）。"""
        n = len(pal)
        filled = self.pid >= 0
        idx = np.clip(np.round((self.tone - lo) / (hi - lo) * (n - 1)), 0, n - 1)
        idx = np.where(filled, idx, 0)
        cap = n - 1 if top_cap is None else top_cap
        idx = np.minimum(idx, cap)
        above = np.full_like(self.pid, -2)
        above[1:] = self.pid[:-1]
        edge = filled & (above != self.pid)
        idx = np.where(edge & (self.tone > rim_min), np.minimum(idx + rim, n - 1), idx)
        out = np.zeros((self.h, self.w, 4), np.uint8)
        pal_a = np.array([tuple(c) + (255,) for c in pal], np.uint8)
        out[filled] = pal_a[idx[filled].astype(int)]
        return out


def puff_rows(pf, rows, seed, wrap=True):
    """rows = [(top_y, top_jitter, rx 范围, 扁度 ry/rx 范围, 平均间距, dark), ...]，从后往前（从上往下）。
    每排沿 x 均匀撒云团（左右绕回），团顶在 top_y ± jitter。"""
    rng = np.random.default_rng(seed)
    for top, jit, rxr, kr, sp, dark in rows:
        n = max(2, int(round(pf.w / sp)))
        xs = (np.arange(n) + rng.uniform(-0.35, 0.35, n)) * pf.w / n
        order = rng.permutation(n)
        for i in order:
            rx = rng.uniform(*rxr)
            ry = rx * rng.uniform(*kr)
            t = top + rng.uniform(-jit, jit)
            pf.puff(xs[i], t + ry, rx, ry, dark=dark, wrap=wrap)


def heap_row(pf, base, n_heaps, hh_r, ww_r, rx_r, k_r, seed, dark=0.0, fill_rx=(30, 50), fill_k=(0.2, 0.3),
             sink=0.5, bumps=3):
    """一排积云堆：n_heaps 个云堆从一层低而扁的云「甲板」（团顶在 base）里鼓出来。
    每个云堆是一摞带鼓包的云团：团顶落在一条拱形上（中间高 hh、两边低），高的先画、低的后画（在前面），
    前面的团盖住后面大团的下半截，上沿一圈圈受光。最后铺甲板，把云堆往下直直的两边盖住。"""
    rng = np.random.default_rng(seed)
    w = pf.w
    centers = (np.arange(n_heaps) + rng.uniform(-0.3, 0.3, n_heaps)) * w / n_heaps
    for c in centers:
        hh = rng.uniform(*hh_r)
        ww = rng.uniform(*ww_r)
        m = int(max(3, ww / np.mean(rx_r) * 2.0))
        items = []
        for _ in range(m):
            u = rng.uniform(-1, 1)
            rx = rng.uniform(*rx_r) * (1 - 0.35 * abs(u))
            ry = rx * rng.uniform(*k_r)
            top = base - hh * max(0.0, 1 - u * u) ** 0.7 + rng.uniform(-1.5, 1.5)
            items.append((top, c + u * ww / 2, rx, ry))
        for top, x, rx, ry in sorted(items):        # 高的先画，低的（前面的）后画
            pf.cumulus(x, top + ry, rx, ry, rng, bumps=bumps, dark=dark, sink=sink)
    n = max(2, int(round(w / np.mean(fill_rx) / 1.2)))
    for x in (np.arange(n) + rng.uniform(-0.3, 0.3, n)) * w / n:
        rx = rng.uniform(*fill_rx)
        ry = rx * rng.uniform(*fill_k)
        pf.cumulus(x, base + rng.uniform(-1, 2) + ry, rx, ry, rng, bumps=max(0, bumps - 1), dark=dark + 0.1, sink=sink)


def ramp_hex(hexc, n, span, hue=14):
    return ramp(sat(from_hex(hexc)), n=n, L_span=span, hue_shift=hue)


# ---------------------------------------------------------------- 天

STAR_C = from_hex("#cfc4ea")


MW_C = from_hex("#4a3a6a")      # 银河往这个色推（冷紫）
MW_W = 26                       # 银河半宽


def mw_x(y):
    """银河中线：从右上（x≈470, y=0）斜到（x≈250, y=128）。"""
    return 470 - y * 1.72


def sky():
    """背景：BANDS 两档之间 Bayer 抖动连续过渡；地平线左边一团余晖（GLOW）；上面一片暗星。"""
    lay = Layer(480, H)
    xs = np.arange(480)
    for y in range(H):
        i, f = band_frac(y)
        idx = i + (BAYER[y % 4, xs % 4] < f)
        lv = glow_level(xs, y) * GLOW_LEVELS
        lo = np.floor(lv)
        lvl = (lo + (BAYER[(y + 1) % 4, (xs + 3) % 4] < (lv - lo))).astype(int)
        for x in range(480):
            lay.a[y, x] = tuple(glow_color(int(idx[x]), int(lvl[x]), y)) + (255,)
    # 地平线上余晖最亮的那一截：一条 1 像素的暖线（只在中间），像太阳刚沉下去的地方
    for x in range(GLOW_X - 46, GLOW_X + 40):
        d = abs(x - GLOW_X + 3) / 43
        if d < 1 and (d < 0.6 or (x % 2 == 0)):
            lay.a[HORIZON, x] = tuple(mix(BAND_C[band_of(HORIZON)], GLOW_C, 0.78)) + (255,)
            if d < 0.3:
                lay.a[HORIZON - 1, x] = tuple(mix(BAND_C[band_of(HORIZON - 1)], GLOW_C, 0.66)) + (255,)
    # 银河：一条从右上斜下来的淡带（过那颗亮星旁边），一块块的，往 MW_C 推一两档（抖动）；带里星星更密
    rng = np.random.default_rng(3)
    patch = np.repeat(np.repeat(rng.random((H // 6 + 2, 480 // 6 + 2)), 6, 0), 6, 1)[:H, :480]
    patch = 0.6 * patch + 0.4 * np.repeat(np.repeat(rng.random((H // 3 + 2, 480 // 3 + 2)), 3, 0), 3, 1)[:H, :480]
    mw = np.zeros((H, 480))
    for y in range(0, 128):
        d = (xs - mw_x(y)) / MW_W
        v = np.exp(-d * d) * (0.35 + 0.9 * patch[y]) * np.clip(1 - y / 128, 0, 1) ** 0.6
        v *= 1 - np.clip(glow_level(xs, y) * 4, 0, 1)
        mw[y] = v
        lv = np.clip(v * 2.2 - 0.25, 0, 2)
        lo = np.floor(lv)
        k = (lo + (BAYER[(y + 3) % 4, (xs + 1) % 4] < lv - lo)).astype(int)
        for x in np.nonzero(k)[0]:
            base = tuple(int(t) for t in lay.a[y, x, :3])
            lay.a[y, x] = tuple(mix(base, MW_C, 0.16 * k[x])) + (255,)
    # 暗星：越往上越密，余晖里没有，银河里更密；大多数只比夜空亮一点点，少数亮一档
    for _ in range(900):
        x = int(rng.uniform(0, 480))
        y = int(130 * rng.random() ** 1.5)
        if glow_level(np.array([x]), y)[0] > 0.04 or rng.random() > (1 - y / 135) ** 0.7:
            continue
        if rng.random() > 0.45 + 0.9 * mw[y, x]:
            continue
        r = rng.random()
        s = 0.22 if r < 0.62 else (0.36 if r < 0.9 else 0.55)
        base = tuple(int(v) for v in lay.a[y, x, :3])
        lay.a[y, x] = tuple(mix(base, STAR_C, s)) + (255,)
    return lay


# 余晖照在云海上：一张屏幕坐标固定的「叠加」图（Godot 里 blend add，放在 mid 和 near 之间、scroll 0）。
# 云海各层在漂、在跟镜头动，余晖不能烘焙进它们；叠加图不动，所以余晖底下那片云顶永远亮一点。
# 像素只有 0 / 255 alpha，亮几档用 Bayer 抖动，不是平滑渐变。
WASH_C = np.array([13, 7, 6])        # 每一档加多少（RGB）
WASH_LEVELS = 3
WASH_Y = (HORIZON + 1, 26)           # 从地平线往下，衰减的距离（像素）


def wash():
    lay = Layer(480, H)
    xs = np.arange(480)
    d = (xs - GLOW_X) / (GLOW_HW * 0.8)
    vx = np.clip(1 - d * d, 0, 1) ** 1.6
    for y in range(WASH_Y[0], H):
        dy = y - WASH_Y[0]
        cone = np.exp(-((xs - GLOW_X) / (14 + dy * 1.1)) ** 2) * np.exp(-dy / 46) * 0.55
        lv = np.clip(vx * np.exp(-dy / WASH_Y[1]) + cone, 0, 1) * WASH_LEVELS
        lo = np.floor(lv)
        fr = lv - lo
        # 只在两档交界的那一窄条抖动（0.3~0.7），其余整片同一档：云上不要满屏的棋盘格
        fr = np.where(fr < 0.3, 0.0, np.where(fr > 0.7, 1.0, (fr - 0.3) / 0.4))
        k = (lo + (BAYER[y % 4, (xs + 2) % 4] < fr)).astype(int)
        for x in np.nonzero(k)[0]:
            lay.a[y, x] = (*(WASH_C * k[x]).tolist(), 255)
    return lay


def high_clouds():
    """高空的几条云：又长又扁、上沿起伏，下沿被下面的余晖照亮（两档玫瑰色），身体比同高度的天暗一点（剪影）。
    这层是漂着的云，本来就悬在空中，自检只查有没有特别小的碎块。"""
    lay = Layer()
    rng = np.random.default_rng(12)
    specs = ((40, 108, 170, 9), (330, 82, 130, 8), (590, 116, 240, 11), (820, 94, 150, 9))
    for x, y, ln, th in specs:
        pf = Puffs()
        k = int(rng.integers(6, 10))
        for j in range(k):
            u = (j - (k - 1) / 2) / ((k - 1) / 2)
            cx = x + u * ln / 2 * rng.uniform(0.85, 1.0)
            rx = ln / k * rng.uniform(0.8, 1.3)
            ry = th * (1 - 0.5 * u * u) * rng.uniform(0.75, 1.1)
            pf.puff(cx, y - ry * 0.3 + rng.uniform(-1, 1), rx, max(1.5, ry), tail=False)
        m = pf.pid >= 0
        if not m.any():
            continue
        below = np.zeros_like(m)
        below[:-1] = m[1:]
        below2 = np.zeros_like(m)
        below2[:-2] = m[2:]
        bc = band_color(y)
        tgt = glow_target(y + 10)
        body = mix(bc, from_hex("#0a0711"), 0.35)
        top = mix(bc, from_hex("#0a0711"), 0.15)
        rim1 = mix(bc, tgt, 0.42)
        rim2 = mix(bc, tgt, 0.18)
        for yy, xx in np.argwhere(m):
            c = body
            if not below[yy, xx]:
                c = rim1
            elif not below2[yy, xx]:
                c = rim2
            elif pf.tone[yy, xx] > 0.6:
                c = top
            lay.a[yy, xx] = tuple(c) + (255,)
    return lay


# ---------------------------------------------------------------- 远处：石针和云柱

SPIRE_BASE = 176


def spire(lay, x, top, w0, seed, lean=0.0):
    """一根从云海里冒出来的石针：越往上越细，一节一节的岩层（每节宽度突变、节顶左边一个亮点），
    左边一条受光边（玫瑰），右边背光。底在 SPIRE_BASE（藏在远处云海后面）。"""
    rng = np.random.default_rng(seed)
    pal = [from_hex(h) for h in ("#100b17", "#181120", "#22182b", "#3a2440", "#5e3a58")]
    h = SPIRE_BASE - top
    y = top
    seg_w = 0.0
    while y < SPIRE_BASE:
        seg = int(rng.integers(6, 15))
        f0 = (y - top) / h
        seg_w = max(seg_w, w0 * f0 ** 0.75 + rng.uniform(-0.6, 1.4))
        for yy in range(y, min(SPIRE_BASE + 30, y + seg) if y + seg >= SPIRE_BASE else y + seg):
            f = min(1.0, (yy - top) / h)
            half = max(0.5, max(seg_w, w0 * f ** 0.75) / 2)
            off = lean * (1 - f) ** 1.5
            xa, xb = int(round(x + off - half)), int(round(x + off + half))
            xb = max(xa + 1, xb)
            for xx in range(xa, xb):
                u = (xx - xa) / max(1, xb - xa - 1)
                if xx == xa and xb - xa >= 2:
                    c = pal[4] if yy > top + 2 else pal[3]
                elif u < 0.3 and xb - xa >= 4:
                    c = pal[3] if (xx == xa + 1 and yy % 5 != 0) else pal[2]
                elif u > 0.75:
                    c = pal[0]
                else:
                    c = pal[1]
                if yy == y and xx < xa + (xb - xa) * 0.5 and yy > top + 3:
                    c = pal[4]     # 每节节顶受光
                lay.a[yy, xx % W] = tuple(c) + (255,)
        y += seg
    # 尖顶
    lay.a[top - 1, int(round(x + lean)) % W] = tuple(pal[3]) + (255,)


def tower(lay, cx, seed):
    """一座很高的积雨云柱：一摞一摞的云团从云海里往上长（每一层左右各鼓出一两团，轮廓是一圈圈的鼓包），
    越往上越窄、被高空的风往右推；顶上是往右伸的平顶（砧）。身体几乎融进夜空，只有朝余晖的左上沿亮一点。"""
    rng = np.random.default_rng(seed)
    pf = Puffs(bands=(1.3, 2.8, 5.5))
    items = []
    y = 168.0
    while y > 66:
        f = (168 - y) / 102                    # 0 底 .. 1 顶
        half = 40 - 14 * f                     # 柱身半宽
        sh = 22 * f ** 1.4                     # 往右偏
        for k in range(3):
            u = (k - 1) + rng.uniform(-0.35, 0.35)
            rx = half * rng.uniform(0.5, 0.72)
            ry = rx * rng.uniform(0.62, 0.8)
            items.append((y - ry, cx + sh + u * half * 0.62, rx, ry))
        y -= rng.uniform(13, 18)
    # 砧：又宽又扁，往右伸得远，左边短
    for k in range(6):
        rx = rng.uniform(26, 40)
        items.append((44 + rng.uniform(-3, 3) + k * 0.6, cx + 10 + k * 26 + rng.uniform(-5, 5), rx, rx * rng.uniform(0.2, 0.28)))
    # 高的先画；同一高度里随机
    for top, x, rx, ry in sorted(items, key=lambda t: t[0] + rng.uniform(-4, 4)):
        pf.cumulus(x, top + ry, rx, ry, rng, bumps=1 if ry > 12 else 0, tail=top + ry > 150, sink=0.45)
    return pf


def spires_layer():
    lay = Layer()
    # 云柱（在石针后面）：暗紫，几乎融进夜空
    pf = tower(lay, 392, 77)
    tpal = [from_hex(h) for h in ("#0d0a14", "#130e1b", "#1c1425", "#2e1f3a", "#52334f")]
    img = pf.render(tpal)
    m = img[..., 3] > 0
    lay.a[m] = img[m]
    flash = flash_layer(pf)
    # 石针：焦点那根在余晖右边一点（屏幕 ~176），逆光的剪影；其余高矮错开
    for x, top, w0, sd, lean in ((176, 70, 15, 1, -3), (191, 104, 9, 2, 2), (36, 112, 10, 3, 0), (282, 118, 8, 4, 2),
                                 (300, 128, 6, 5, 0), (468, 108, 11, 6, -2), (640, 86, 13, 7, 3),
                                 (655, 120, 7, 8, 0), (790, 116, 10, 9, -1), (905, 98, 12, 10, 2)):
        spire(lay, x, top, w0, sd, lean)
    # 往同一高度的天色里褪：越往下（越贴近地平线的雾）褪得越多；云柱上面褪一点
    aerial(lay, lambda y: 0.12 + 0.55 * max(0.0, (y - 100) / 70) ** 1.3)
    return lay, flash


def flash_layer(pf):
    """闪电：云柱里中间偏下的几团从里面亮起来（冷的灰紫，不是纯蓝）。每团亮多少随机（有的亮、有的只透一点），
    团和团之间的缝暗；越往外越暗，最外面一圈就不亮了。只比云柱平时亮几档，不抢晨。
    Godot 里这张图叠在 spires 上，平时隐藏，闪的时候显示一两下（scripts/cloud_lightning.gd）。"""
    out = np.zeros((H, W, 4), np.uint8)
    fpal = [from_hex(h) for h in ("#1f1830", "#2a2140", "#382d53", "#4a3e68")]
    cx, cy, rx, ry = 410, 118, 30, 40
    rng = np.random.default_rng(8)
    gain = rng.uniform(0.35, 1.25, pf.n + 1)
    ys, xs = np.nonzero(pf.pid >= 0)
    d = ((xs + 0.5 - cx) / rx) ** 2 + ((ys + 0.5 - cy) / ry) ** 2
    sel = d < 1.0
    ys, xs, d = ys[sel], xs[sel], d[sel]
    pid = pf.pid
    for y, x, dd in zip(ys, xs, d):
        edge = 0
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W and pid[yy, xx] != pid[y, x]:
                edge = 1
        v = (1 - dd) * 3.6 * gain[pid[y, x]] - edge * 1.2 + pf.tone[y, x] * 0.6
        if v < 0.6:
            continue
        out[y, x] = tuple(fpal[int(np.clip(round(v), 0, len(fpal) - 1))]) + (255,)
    lay = Layer()
    lay.a = out
    return lay


# ---------------------------------------------------------------- 云海（第二版：一颗颗球堆出来的积云）
#
# 第一版的云是一个个扁椭圆、每团三道月牙 → 像枕头、像果冻。第二版：
# - 每团云 = 很多大小不一的球（椭球）挤在一起，记 z（离观众多近），近的盖住远的（z-buffer），
#   球的上半圈再长一圈小球、小球再长更小的球（菜花）：上沿是一串起伏的圆弧，团与团之间有缝；
# - 明暗按球面法线算（光从左上、余晖那边来），再加两样东西做「缝」：
#   投影（朝光的方向走几步，被更近的云挡住 = 在影子里）和 AO（周围有更近的云 = 缝里，压暗）；
# - 只分 4~6 档，档和档之间不抖动（硬边色块）；最后把孤立的单个像素抹掉，免得碎成噪点；
# - 远近：同一层里每一排云有自己的雾（整团一起褪色，不按屏幕 y 一行行褪，否则会切出横纹）。

L3 = np.array([-0.70, -0.62, 0.36])
L3 = L3 / np.linalg.norm(L3)


def from_lch(L, C, h):
    h = np.radians(h)
    return tuple(int(v) for v in oklab_to_srgb(np.array([[L, C * np.cos(h), C * np.sin(h)]]))[0])


def cloud_pal(L_lo, L_hi, n, C_lo=0.035, C_hi=0.06, h_lo=300, h_hi=350, gamma=1.0):
    """云的色阶：暗端冷（蓝紫 ~300°），亮端暖（玫瑰 ~350°），中间是紫。OKLCh，不会出绿、不会出纯蓝。"""
    out = []
    for i in range(n):
        t = (i / (n - 1)) ** gamma
        out.append(from_lch(L_lo + (L_hi - L_lo) * t, C_lo + (C_hi - C_lo) * t, h_lo + (h_hi - h_lo) * t))
    return out


def shift(a, ox, oy, fill):
    """q[y, x] = a[y + oy, x + ox]（x 左右绕回，y 出界填 fill）。"""
    b = np.roll(a, -ox, axis=1)
    if oy == 0:
        return b
    out = np.full_like(a, fill)
    if oy < 0:
        out[-oy:] = b[:oy]
    else:
        out[:-oy] = b[oy:]
    return out


class Field:
    """一层云的「球堆」：每个像素记最前面那颗球的 z、法线、编号、压暗、身体深度、雾。"""

    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.z = np.full((h, w), -1e9)
        self.n = np.zeros((h, w, 3))
        self.sid = np.full((h, w), -1, np.int32)
        self.dark = np.zeros((h, w))
        self.dep = np.zeros((h, w))
        self.fog = np.zeros((h, w))
        self.vin = np.zeros((h, w))       # 在自己这颗球里的竖直位置（-1 顶 .. 1 底，身体 > 1）
        self.core = np.zeros((h, w), bool)  # 这个像素属于有身体的核心球
        self.grp = np.full((h, w), -1, np.int32)  # 属于哪一团（一堆积云 / 一排甲板）
        self.g = 0
        self.rowid = np.full((h, w), -1, np.int32)  # 属于哪一排
        self.row = 0
        self.k = 0

    def new_group(self):
        self.g += 1
        return self.g

    def below_envelope(self, smooth=31):
        """每个像素在自己这一排的「天际线」下面几个像素。天际线 = 这一排每列最上面的像素，再左右平滑 smooth 像素：
        明暗顺着这一排云大的起伏往下变暗（不按一个个小团画同心圈，也不是一条条水平线）。"""
        out = np.zeros(self.z.shape)
        ys = np.arange(self.h)[:, None]
        for r in np.unique(self.rowid[self.rowid >= 0]):
            m = self.rowid == r
            has = m.any(0)
            top = np.where(has, m.argmax(0), np.nan).astype(float)
            xs = np.arange(self.w)
            if (~has).any():
                top[~has] = np.interp(xs[~has], xs[has], top[has], period=self.w)
            k = np.ones(smooth) / smooth
            env = np.convolve(np.r_[top[-smooth:], top, top[:smooth]], k, "same")[smooth:-smooth]
            out = np.where(m, ys - env[None, :], out)
        return out

    def run_from_top(self):
        """每个像素离自己这一团（grp）的上沿往下几个像素：明暗顺着云团的轮廓往下变暗，不切横线。"""
        run = np.zeros(self.grp.shape)
        for y in range(1, self.h):
            same = (self.grp[y] == self.grp[y - 1]) & (self.grp[y] >= 0)
            run[y] = np.where(same, run[y - 1] + 1, 0)
        return run

    def ball(self, cx, cy, rx, ry, z0, rz=None, dark=0.0, body=True, fog=0.0, wrap=True, ref=None, unit=None):
        """椭球：中心 (cx, cy)，半轴 rx / ry（屏幕上）/ rz（朝观众）。body = 下半截变成竖直的柱子一直到图底（云的身体）。
        ref / unit：身体从屏幕 y = ref 往下每 unit 像素暗一档（同一堆云共用一个 ref：并排的团在同一高度一样暗，
        不会切出一道道竖缝）。不给就用自己的球心和 ry。"""
        rz = rx if rz is None else rz
        ref = cy if ref is None else ref
        unit = ry if unit is None else unit
        x0, x1 = int(np.floor(cx - rx)) - 1, int(np.ceil(cx + rx)) + 1
        y0 = max(0, int(np.floor(cy - ry)) - 1)
        y1 = self.h if body else min(self.h, int(np.ceil(cy + ry)) + 1)
        if y0 >= y1 or rx < 0.6 or ry < 0.4:
            return
        X, Y = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1))
        u = (X + 0.5 - cx) / rx
        v = (Y + 0.5 - cy) / ry
        r2 = u * u + v * v
        cyl = (v > 0) & (np.abs(u) <= 1) if body else np.zeros_like(r2, bool)
        m = (r2 <= 1) | cyl
        if not wrap:
            m &= (X >= 0) & (X < self.w)
        wq = np.where(cyl, np.sqrt(np.clip(1 - u * u, 0, None)), np.sqrt(np.clip(1 - r2, 0, None)))
        zz = z0 + rz * wq
        # 身体（柱子）那截的法线朝着观众：平平的一片，只随深度变暗，不要竖着的明暗条（会像石头柱子）
        nx = np.where(cyl, 0.25 * u / rx, u / rx)
        ny = np.where(cyl, 0.0, v / ry)
        nz = np.where(cyl, 1.0 / rz, wq / rz + 1e-4)
        nn = np.sqrt(nx * nx + ny * ny + nz * nz)
        xs = X % self.w if wrap else np.clip(X, 0, self.w - 1)
        upd = m & (zz > self.z[Y, xs])
        if not upd.any():
            return
        Yu, Xu = Y[upd], xs[upd]
        self.z[Yu, Xu] = zz[upd]
        self.n[Yu, Xu] = np.stack([nx[upd], ny[upd], nz[upd]], -1) / nn[upd][:, None]
        self.sid[Yu, Xu] = self.k
        self.dark[Yu, Xu] = dark
        self.dep[Yu, Xu] = np.clip((Yu + 0.5 - ref) / unit, 0, None)
        self.fog[Yu, Xu] = fog
        self.vin[Yu, Xu] = v[upd]
        self.core[Yu, Xu] = body
        self.grp[Yu, Xu] = self.g
        self.rowid[Yu, Xu] = self.row
        self.k += 1

    def cauli(self, cx, cy, r, z0, rng, sq=1.0, depth=2, kids=(3, 6), ks=(0.3, 0.55), dark=0.0, body=True, fog=0.0,
              spread=(-172, -8), rmin=2.0, ref=None, unit=None):
        """一颗球，上半圈再长几颗小球（小球再长更小的）：菜花一样的轮廓。sq = 竖直压扁（远处更扁）。"""
        if ref is None:
            ref, unit = cy - r * sq, r * sq * 2
        self.ball(cx, cy, r, r * sq, z0, dark=dark, body=body, fog=fog, ref=ref, unit=unit)
        if depth <= 0 or r < rmin * 1.8:
            return
        n = int(rng.integers(kids[0], kids[1] + 1))
        angs = np.sort(rng.uniform(*spread, n))
        for a in np.radians(angs):
            rr = r * rng.uniform(*ks)
            if rr < rmin:
                continue
            px = cx + np.cos(a) * r * rng.uniform(0.72, 0.92)
            py = cy + np.sin(a) * r * sq * rng.uniform(0.72, 0.92)
            zc = z0 + r * 0.5 - rr * rng.uniform(0.35, 0.7)
            self.cauli(px, py + rr * sq * 0.25, rr, zc, rng, sq, depth - 1, kids, ks, dark, False, fog, spread, rmin,
                       ref, unit)

    def heap(self, cx, base, width, height, z0, rng, sq=1.0, r_core=None, depth=2, dark=0.0, fog=0.0, kids=(3, 6),
             ks=(0.3, 0.55), rmin=2.0, unit=None, ref=None):
        """一堆积云：几颗核心球顶在一条拱上（中间高、两边低），低的（前面的）z 大、盖住高的下半截；
        每颗核心球长一圈菜花。底在 base（被前面一排吞掉）。"""
        self.new_group()
        r_core = r_core or max(rmin * 2, min(width * 0.32, height * 0.9 / max(sq, 0.2)))
        k = max(1, int(round(width / (r_core * 1.15))))
        us = np.linspace(-1, 1, k) if k > 1 else np.array([0.0])
        us = us + rng.uniform(-0.18, 0.18, k) * (k > 1)
        items = []
        for u in us:
            r = r_core * rng.uniform(0.75, 1.15) * (1 - 0.35 * abs(u))
            top = base - height * max(0.0, 1 - u * u) ** 0.65 - rng.uniform(0, 1.5)
            cy = top + r * sq
            items.append((cy, cx + u * width / 2, r))
        if ref is None:
            ref = min(cy - r * sq for cy, x, r in items)
        unit = unit or max(3.0, (base - ref) * 0.7)
        for cy, x, r in sorted(items):
            zc = z0 + (cy - base) * 0.6 + rng.uniform(-1, 1)
            self.cauli(x, cy, r, zc, rng, sq, depth, kids, ks, dark, True, fog, rmin=rmin, ref=ref, unit=unit)

    def render(self, pal, body=2, rim=(1.0, 3.0), crease=1.5, deep=0.0, bands=(), dark_lv=1.0, fog_c=None,
               fog_steps=(), light=(-0.62, -0.78), cleanup=True, top_only=0.35, cz=5.0, lower=0.45, cz_rim=3.0,
               run_bands=(), env_smooth=31):
        """像素云的明暗（分档，不按法线算渐变：按法线量化出来是一块块多边形，像石头）：
        - 每个像素朝光（左上）走，直到走出自己这一团（z 差 < cz_rim 的相邻小球算同一团，接着走）：
          落到明显更远的云 / 空上（= 这一团露在外面、朝光的上沿），走了 < rim[0] 像素 → 亮 2 档，< rim[1] → 亮 1 档；
          落到明显更近（z 差 > cz）的云的「球」那截上（= 前面一团云的上沿压在自己身上，缝）且 < crease 像素 → 暗 1 档
          （deep 以内再暗 1 档）。同一团里的小鼓包 z 差小，不压缝（否则满身裂纹，像石头）；柱子（身体）的竖边也不压。
        - 身体：从这堆云的 ref 往下，每过 bands 里的一个门槛（单位 = unit）暗 1 档。dark 每 1.0 暗 dark_lv 档。
          给了 run_bands 就改成：在自己这一排平滑过的天际线下面每过一个门槛（像素）暗 1 档。
        - top_only：受光边只给球心以上（v < top_only）的部分：底下那半圈朝光也不亮（被下面的云挡着）。
        - lower：每颗「核心」球（有身体的）自己下半截（v > lower，含身体）暗 1 档：一团团读得出是圆鼓鼓的。
          菜花小球不算（不然满身一道道暗弧）。
        档 = body 起算，夹在 0..len(pal)-1。"""
        f = self.sid >= 0
        s = np.hypot(*light)
        dx, dy = light[0] / s, light[1] / s
        INF = 99.0
        tl = np.full(self.z.shape, INF)
        tc = np.full(self.z.shape, INF)
        n_steps = int(max(rim[1], crease, deep) * 2) + 2
        for i in range(1, n_steps + 1):
            t = i * 0.5
            ox, oy = int(round(dx * t)), int(round(dy * t))
            if ox == 0 and oy == 0:
                continue
            qs = shift(self.sid, ox, oy, -1)
            qz = shift(self.z, ox, oy, -1e9)
            qv = shift(self.vin, ox, oy, 0.0)
            open_ = (qs != self.sid) & (tl == INF) & (tc == INF)
            tl = np.where(open_ & (qz < self.z - cz_rim), t, tl)
            tc = np.where(open_ & (qz > self.z + cz), np.where(qv <= 1.0, t, INF - 1), tc)
        lv = np.full(self.z.shape, float(body))
        upper = self.vin < top_only
        lv += np.where(upper & (tl < rim[0]), 2, np.where(upper & (tl < rim[1]), 1, 0))
        lv -= np.where(tc < crease, 1, 0) + np.where(tc < deep, 1, 0)
        if lower is not None:
            lv -= self.core & (self.vin > lower)
        dep = self.below_envelope(env_smooth) if run_bands else self.dep
        for b in (run_bands or bands):
            lv -= dep >= b
        lv -= np.round(self.dark * dark_lv)
        idx = np.clip(lv, 0, len(pal) - 1).astype(int)
        idx = np.where(f, idx, -1)
        if cleanup:
            idx = despeckle(idx)
        out = np.zeros((self.h, self.w, 4), np.uint8)
        if fog_c is None or not len(fog_steps):
            pal_a = np.array([tuple(c) + (255,) for c in pal], np.uint8)
            out[f] = pal_a[idx[f]]
            return out
        fs = np.asarray(fog_steps)
        fi = np.abs(self.fog[..., None] - fs[None, None]).argmin(-1)
        for j, t in enumerate(fs):
            pal_a = np.array([tuple(mix(c, fog_c, t)) + (255,) for c in pal], np.uint8)
            sel = f & (fi == j)
            out[sel] = pal_a[idx[sel]]
        return out


def despeckle(idx, passes=2):
    """孤立的单个像素（上下左右四个邻居都和它不同、而且它们里多数是同一档）改成那一档：不碎成噪点。"""
    for _ in range(passes):
        nb = np.stack([shift(idx, 1, 0, -1), shift(idx, -1, 0, -1), shift(idx, 0, 1, -1), shift(idx, 0, -1, -1)])
        same = (nb == idx[None]).sum(0)
        lone = (same == 0) & (idx >= 0)
        if not lone.any():
            break
        # 邻居里出现最多的那档（-1 = 空不算）
        best = np.full_like(idx, -1)
        bestc = np.zeros_like(idx)
        for k in range(4):
            c = (nb == nb[k][None]).sum(0) * (nb[k] >= 0)
            better = c > bestc
            best = np.where(better, nb[k], best)
            bestc = np.where(better, c, bestc)
        idx = np.where(lone & (best >= 0), best, idx)
    return idx


def sea_row(F, rng, base, z0, scale, sq, fog, n_heaps, h_range, w_range, deck_h, dark=0.0, depth=2, wave=0.0,
            big=0.0, rmin=2.0, kids=(3, 6), ks=(0.3, 0.55)):
    """一排云：先铺一层矮的云甲板（团顶在 base - deck_h 上下，带菜花），再在上面撒 n_heaps 堆大小不一的积云
    （高度 h_range，偶尔一堆特别高：big = 概率）。wave = 这一排的底沿随 x 起伏多少像素（云丘 / 云谷）。"""
    w = F.w
    ph = rng.uniform(0, 2 * np.pi, 5)
    fr = rng.choice([6, 7, 8, 9, 11, 13], 2, replace=False)

    def b_at(x):
        # 云丘 / 云谷：几个低频 + 两个中频的起伏（频率是整数：左右无缝）
        t = 2 * np.pi * x / w
        return base + wave * (0.5 * np.sin(2 * t + ph[0]) + 0.35 * np.sin(3 * t + ph[1]) + 0.25 * np.sin(5 * t + ph[2])
                              + 0.3 * np.sin(fr[0] * t + ph[3]) + 0.2 * np.sin(fr[1] * t + ph[4]))

    # 甲板：一串中等的团，间距不匀
    F.new_group()
    F.row += 1
    x = rng.uniform(0, w)
    end = x + w
    while x < end:
        r = scale * rng.uniform(0.55, 1.45)
        F.cauli(x % w, b_at(x) - deck_h + r * sq, r, z0 + rng.uniform(-1, 1), rng, sq, depth=max(1, depth - 1),
                kids=kids, ks=ks, dark=dark + 0.05, fog=fog, rmin=rmin, ref=b_at(x) - deck_h, unit=scale * sq * 1.6)
        x += r * rng.uniform(1.1, 1.9)
    # 积云堆：位置不匀（有的挤在一起，有的隔很远）
    xs = np.sort(rng.uniform(0, w, n_heaps))
    for cx in xs:
        hh = rng.uniform(*h_range)
        if rng.random() < big:
            hh *= rng.uniform(1.6, 2.3)
        ww = rng.uniform(*w_range) * (0.8 + 0.25 * hh / max(h_range[1], 1))
        F.heap(cx, b_at(cx) - deck_h * 0.5, ww, hh, z0 + 2 + rng.uniform(0, 2), rng, sq=sq, depth=depth, dark=dark,
               fog=fog, rmin=rmin, kids=kids, ks=ks, ref=b_at(cx) - deck_h, unit=scale * sq * 1.6)


FOG_STEPS = (0.0, 0.12, 0.24, 0.36, 0.5, 0.64)


def sea_layer2(rows, pal, fog_c, seed, **kw):
    """rows = [dict(base, z, scale, sq, fog, n, h, w, deck, ...)]，从远到近。kw 给 Field.render。"""
    F = Field()
    rng = np.random.default_rng(seed)
    for r in rows:
        r = dict(r)
        sea_row(F, rng, r.pop("base"), r.pop("z"), r.pop("scale"), r.pop("sq"), r.pop("fog"), r.pop("n"), r.pop("h"),
                r.pop("w"), r.pop("deck"), **r)
    lay = Layer()
    lay.a = F.render(pal, fog_c=fog_c, fog_steps=FOG_STEPS, **kw)
    return lay


def build_far():
    """贴着地平线（143~176）：最远，所以最扁（sq 0.36~0.44）、最密、最淡；每排的底沿高高低低（云丘 / 云谷），
    排和排交叉，不是平行线；偶尔一堆远处的积云鼓得很高。"""
    pal = cloud_pal(0.27, 0.56, 6, C_lo=0.04, C_hi=0.07, h_lo=308, h_hi=368)
    rows = [
        dict(base=146, z=0, scale=4, sq=0.36, fog=0.36, n=12, h=(1, 5), w=(14, 36), deck=1.0, wave=2.0, big=0.3,
             rmin=1.2, depth=1),
        dict(base=153, z=20, scale=5.5, sq=0.4, fog=0.24, n=10, h=(2, 6), w=(20, 46), deck=1.5, wave=3.0, big=0.3,
             rmin=1.4, depth=1),
        dict(base=162, z=40, scale=7, sq=0.44, fog=0.12, n=8, h=(2, 8), w=(26, 56), deck=2.0, wave=3.5, big=0.3,
             rmin=1.6, depth=2),
    ]
    return sea_layer2(rows, pal, band_color(147), 21, body=3, rim=(1.0, 2.0), crease=1.0, bands=(1.3,), run_bands=(3,))


def build_midfar():
    pal = cloud_pal(0.22, 0.48, 6, C_lo=0.04, C_hi=0.065, h_lo=305, h_hi=362)
    rows = [
        dict(base=166, z=0, scale=8, sq=0.5, fog=0.24, n=8, h=(3, 11), w=(26, 70), deck=2, wave=4, big=0.25, rmin=1.6),
        dict(base=177, z=30, scale=11, sq=0.54, fog=0.12, n=6, h=(4, 13), w=(36, 80), deck=2.5, wave=4, big=0.2,
             rmin=1.8),
    ]
    return sea_layer2(rows, pal, band_color(160), 31, body=3, rim=(1.0, 2.5), crease=1.5, bands=(1.0, 2.2), run_bands=(3, 8))


def build_mid():
    pal = cloud_pal(0.13, 0.36, 6, C_lo=0.035, C_hi=0.06, h_lo=300, h_hi=352)
    rows = [
        dict(base=190, z=0, scale=14, sq=0.62, fog=0.12, n=5, h=(8, 18), w=(50, 100), deck=3, wave=4, big=0.2),
        dict(base=203, z=40, scale=17, sq=0.66, fog=0.0, n=4, h=(6, 14), w=(60, 110), deck=3, wave=4, big=0.1,
             dark=0.12),
    ]
    return sea_layer2(rows, pal, band_color(190), 41, body=2, rim=(1.5, 3.0), crease=2.0, bands=(0.7, 1.5, 2.6), run_bands=(5, 12, 22))


def build_near():
    """晨身后那条（196~245）：很暗、干净；团大，菜花只到一级，只有上沿一小块一小块亮一点。"""
    pal = cloud_pal(0.10, 0.25, 5, C_lo=0.03, C_hi=0.05, h_lo=298, h_hi=338)
    rows = [
        dict(base=213, z=0, scale=22, sq=0.72, fog=0.0, n=4, h=(6, 16), w=(70, 130), deck=3, wave=4, big=0.1,
             depth=2, ks=(0.32, 0.5), rmin=3.0),
        dict(base=224, z=50, scale=26, sq=0.75, fog=0.0, n=3, h=(4, 10), w=(80, 140), deck=3, wave=3, big=0.0,
             depth=1, rmin=3.0),
    ]
    return sea_layer2(rows, pal, None, 51, body=2, rim=(1.5, 3.0), crease=2.0, bands=(0.8, 1.8), run_bands=(6, 15))


# ---------------------------------------------------------------- 能走的云顶

GROUND = 226


def main_layer():
    """能走的那一层：上沿是一片很宽、很缓的云顶（大扁球，起伏几像素），顶上一串小鼓包（1~2 像素高）把受光边
    碎成一小块一小块；地面 = 每列第一个不透明像素，晨走过去只轻轻起伏。下面是这片云的正面：几排更低、
    更近的菜花云团挂下来，一排比一排暗，团和团之间深缝，最后沉进黑里（被 front 盖住）。"""
    F = Field()
    rng = np.random.default_rng(5)
    # 顶：一串中等的圆顶（rx 12~24，高 4~7），团顶落在一条很缓的地形线上，相邻两团接缝只凹 1~2 像素：
    # 读得出是一团团云，晨走过去只轻轻起伏。两处地形鼓起来一点（300、742）。
    def terrain(x):
        t = 2 * np.pi * x / W
        hill = -6 * np.exp(-(((x - 300 + W / 2) % W - W / 2) / 60) ** 2) - 4 * np.exp(-(((x - 742 + W / 2) % W - W / 2) / 50) ** 2)
        return GROUND + 1.2 * np.sin(3 * t + 0.4) + 0.8 * np.sin(7 * t + 2.0) + hill

    F.new_group()
    x = 0.0
    while x < W:
        rx = rng.uniform(12, 24)
        ry = rx * rng.uniform(0.26, 0.34)
        top = terrain(x) + rng.uniform(-0.6, 0.8)
        F.ball(x, top + ry, rx, ry, rng.uniform(0, 2), rz=rx * 0.5, ref=GROUND, unit=8)
        x += rx * rng.uniform(1.15, 1.45)
    # 圆顶上偶尔再鼓一个小包（1 像素高）：受光边碎成一小块一小块
    gl0 = np.argmax(F.sid >= 0, 0)
    x = rng.uniform(0, 10)
    while x < W:
        rx = rng.uniform(4, 8)
        ry = rng.uniform(1.4, 2.2)
        g = gl0[int(x) % W]
        F.ball(x, g + ry - rng.uniform(0.5, 1.1), rx, ry, 3.0 + rng.uniform(0, 1), rz=rx * 0.4, ref=GROUND, unit=8)
        x += rx * rng.uniform(2.0, 4.0)
    # 正面：几排菜花云团，越往下越近（z 大）、越暗
    for k, (dy, dark, n, rr) in enumerate(((7, 0.0, 22, (12, 22)), (17, 0.0, 18, (14, 26)), (29, 0.0, 14, (16, 30)))):
        xs = np.sort(rng.uniform(0, W, n))
        for cx in xs:
            r = rng.uniform(*rr)
            F.new_group()
            F.row = 10 + k
            F.cauli(cx, GROUND + dy + r * 0.6 * rng.uniform(0.4, 0.9), r, 20 + 30 * k, rng, sq=0.6, depth=2,
                    kids=(3, 5), ks=(0.3, 0.5), dark=dark, rmin=2.5, spread=(-165, -15), ref=GROUND, unit=8)
    pal = cloud_pal(0.10, 0.42, 7, C_lo=0.03, C_hi=0.06, h_lo=296, h_hi=352)
    lay = Layer()
    lay.a = F.render(pal, body=4, rim=(1.5, 3.0), crease=2.0, bands=(0.6, 1.5, 2.6, 3.6), run_bands=(4, 10, 18, 28))
    # 走的那条边：每列最上面一个像素至少亮到 WALK 档（读得出「能踩」）
    gl = ground_line(lay)
    walk = np.array(tuple(pal[5]) + (255,), np.uint8)
    wl = to_lab(tuple(int(t) for t in walk[:3]))[0]
    for x in range(W):
        y = gl[x]
        if to_lab(tuple(int(t) for t in lay.a[y, x, :3]))[0] < wl:
            lay.a[y, x] = walk
    return lay


def ground_line(lay):
    """每列第一个不透明像素 = 地面（晨脚底那一行）。"""
    m = lay.a[..., 3] > 0
    return m.argmax(0)


def front_layer():
    """前景：底边几堆近黑的菜花云把画面框住，上沿一点极暗的受光。团顶都在 236 以下：不挡晨的脚。"""
    F = Field()
    rng = np.random.default_rng(9)
    for cx, top, rr in ((40, 240, 46), (130, 252, 30), (420, 254, 38), (610, 243, 42), (700, 256, 28), (880, 247, 36)):
        # 一簇：中间高、两边低的几颗球，前面（低）的盖住后面（高）的
        k = int(rr / 9) + 2
        F.new_group()
        for j, u in enumerate(sorted(rng.uniform(-1, 1, k), key=abs)):
            r = rr * rng.uniform(0.35, 0.55) * (1 - 0.3 * abs(u))
            t = top + abs(u) * rr * 0.35 + rng.uniform(0, 3)
            F.cauli(cx + u * rr, t + r * 0.65, r, 10 * abs(u) + rng.uniform(0, 2), rng, sq=0.65, depth=2, kids=(2, 4),
                    ks=(0.3, 0.5), rmin=3.0, spread=(-160, -20), ref=top, unit=rr * 0.4)
    pal = cloud_pal(0.06, 0.17, 4, C_lo=0.025, C_hi=0.04, h_lo=298, h_hi=330)
    lay = Layer()
    lay.a = F.render(pal, body=1, rim=(1.5, 2.5), crease=1.5, bands=(1.0,), run_bands=(6,))
    lay.a[:236] = 0
    return lay



# ---------------------------------------------------------------- 组装 / 检查 / 预览

def build():
    OUT.mkdir(parents=True, exist_ok=True)
    sp, flash = spires_layer()
    layers = {
        "sky": sky(),
        "high": high_clouds(),
        "spires": sp,
        "far": build_far(),
        "midfar": build_midfar(),
        "mid": build_mid(),
        "near": build_near(),
        "main": main_layer(),
        "front": front_layer(),
    }
    for k, v in layers.items():
        v.save(k)
    flash.save("flash")
    wash().save("wash")
    return layers, flash


def check_alpha(layers):
    for k, v in layers.items():
        u = set(np.unique(v.a[..., 3]).tolist())
        assert u <= {0, 255}, (k, u)
        assert v.a.shape[:2] == ((H, 480) if k == "sky" else (H, W)), (k, v.a.shape)


def check_seams(layers):
    """左右无缝：最左一列和最右一列要像同一片东西的两边（不透明的位置差不多）。"""
    for k, v in layers.items():
        if k == "sky":
            continue
        l, r = v.a[:, 0, 3] > 0, v.a[:, -1, 3] > 0
        diff = int((l != r).sum())
        if diff > 6:
            print(f"  ! {k} 左右边不透明的行差 {diff} 行")


# 每层的东西要「落」在哪：云海 / 主层 / 前景的每一团都要连到图的底边（云的身体）；石针、云柱连到 SPIRE_BASE；
# 高空的薄云本来就漂着，只查有没有特别小的碎块（< MIN_BIT 像素）。
MIN_BIT = 12


def check_floating(layers, verbose=True):
    bad = {}
    for k, lay in layers.items():
        if k == "sky":
            continue
        lab, n = components(lay.a[..., 3] > 0, wrap=True)
        out = []
        for i in range(1, n + 1):
            yy, xx = np.nonzero(lab == i)
            if k == "high":
                if len(yy) < MIN_BIT:
                    out.append((len(yy), int(xx.min()), int(xx.max()), int(yy.min()), int(yy.max()), "碎块"))
                continue
            floor = SPIRE_BASE - 2 if k == "spires" else H - 1
            if yy.max() < floor:
                out.append((len(yy), int(xx.min()), int(xx.max()), int(yy.min()), int(yy.max()), "悬空"))
        bad[k] = out
        if verbose:
            print(f"  {k:7s} 连通区域 {n:4d}，有问题 {len(out)}")
            for b in out[:8]:
                print("     ", b)
    return bad


def check_brightness(layers):
    """背景最亮处要明显低于晨（晨身上大块的米白 #c7bdb8，OKLab L≈0.80）。"""
    worst = 0.0
    for k, v in layers.items():
        m = v.a[..., 3] > 0
        cols = np.unique(v.a[m][:, :3], axis=0)
        L = max(float(to_lab(tuple(int(t) for t in c))[0]) for c in cols)
        worst = max(worst, L)
        print(f"  {k:7s} 最亮 L={L:.3f}，{len(cols)} 色")
    assert worst < 0.68, f"背景太亮了：L={worst:.3f}"


def chen_frame(i=3):
    a = np.array(Image.open(CHEN).convert("RGBA"))
    return a[:, i * 40:(i + 1) * 40]


def compose(layers, cam_x, chen_sx=204, flash=None):
    """按 Godot 的视差比例合成一张 480×270（镜头左边缘在 cam_x），晨站在屏幕 chen_sx。"""
    out = np.zeros((H, 480, 4), np.uint8)
    gl = ground_line(layers["main"])
    for k in SCROLL:
        a = layers[k].a
        if k == "spires" and flash is not None:
            a = a.copy()
            fm = flash.a[..., 3] > 0
            a[fm] = flash.a[fm]
        if a.shape[1] == 480:
            src = a
        else:
            off = int(round(cam_x * SCROLL[k])) % a.shape[1]
            src = np.roll(a, -off, axis=1)[:, :480]
        if k == "front" and chen_sx is not None:
            fr = chen_frame()
            gy = int(gl[(chen_sx + cam_x) % W])
            y0, x0 = gy - 41, chen_sx - 20
            m = fr[..., 3] > 0
            sub = out[y0:y0 + 42, x0:x0 + 40]
            sub[m] = fr[m]
        m = src[..., 3] > 0
        out[m] = src[m]
        if k == "mid":
            wm = WASH.a[..., 3] > 0
            out[wm, :3] = np.clip(out[wm, :3].astype(int) + WASH.a[wm, :3], 0, 255).astype(np.uint8)
        if k == "sky":
            sx, sy = STAR_XY
            for dx, dy, c in STAR_SHAPE:
                out[sy + dy, sx + dx, :3] = c
    return out


# scenes/cloud_test.tscn 里每层的 Sprite2D 只画有东西的那几行（region），透明的上半截不画：
# 手机网页版按全分辨率填像素，十层全屏图 → 大约三层的量。改了图重跑这个脚本，场景里的数自动跟着改。
SCENE = ROOT / "scenes" / "cloud_test.tscn"
SCENE_NODES = {"high": "High", "spires": "Spires", "far": "Far", "midfar": "MidFar", "mid": "Mid", "near": "Near",
               "main": "Main", "front": "Front", "wash": "Wash", "flash": "Spires/Flash"}
REGION_CAP = {"spires": 180}     # 石针和云柱 180 以下全被远处云海挡住


def sync_scene():
    import re
    if not SCENE.exists():
        return
    txt = SCENE.read_text()
    for f, node in SCENE_NODES.items():
        a = np.array(Image.open(OUT / f"{f}.png"))[..., 3] > 0
        r = np.nonzero(a.any(1))[0]
        y0, y1 = max(0, int(r.min()) - 1), min(int(r.max()), REGION_CAP.get(f, H))
        if "/" in node:
            par, name = node.split("/")
            hdr = f'[node name="{name}" type="Sprite2D" parent="{par}"]'
        else:
            hdr = f'[node name="Sprite" type="Sprite2D" parent="{node}"]'
        i = txt.index(hdr)
        j = txt.find("\n[", i + 1)
        j = len(txt) if j < 0 else j
        block = txt[i:j]
        block = re.sub(r"position = Vector2\(0, \d+\)", f"position = Vector2(0, {y0})", block)
        block = re.sub(r"region_rect = Rect2\(0, \d+, (\d+), \d+\)", lambda m: f"region_rect = Rect2(0, {y0}, {m.group(1)}, {y1 - y0 + 1})", block)
        txt = txt[:i] + block + txt[j:]
    SCENE.write_text(txt)


WASH = None
# 那颗特别亮的星（cloud_stars.gd 里画、慢慢呼吸；这里只给预览用）
STAR_XY = (318, 34)
STAR_SHAPE = [(0, 0, (214, 204, 236)), (-1, 0, (120, 104, 150)), (1, 0, (120, 104, 150)), (0, -1, (120, 104, 150)),
              (0, 1, (120, 104, 150)), (-2, 0, (58, 48, 80)), (2, 0, (58, 48, 80)), (0, -2, (58, 48, 80)),
              (0, 2, (58, 48, 80))]


def preview(layers, cam_x, path, flash=None):
    Image.fromarray(compose(layers, cam_x, flash=flash)).resize((1440, 810), Image.NEAREST).save(path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="把几张合成预览存到这个目录")
    args = ap.parse_args()
    ls, fl = build()
    WASH = wash()
    sync_scene()
    check_alpha(ls)
    check_alpha({"flash": fl})
    check_seams(ls)
    print("亮度：")
    check_brightness(ls)
    print("悬空自检：")
    floating = check_floating(ls)
    gl = ground_line(ls["main"])
    print(f"地面：{gl.min()}..{gl.max()}，相邻列最大落差 {int(np.abs(np.diff(np.r_[gl, gl[0]])).max())}")
    if args.preview:
        d = Path(args.preview)
        d.mkdir(parents=True, exist_ok=True)
        for cx in (0, 300, 620):
            preview(ls, cx, d / f"cloud_{cx}.png")
        preview(ls, 0, d / "cloud_0_flash.png", flash=fl)
    print("ok", {k: v.a.shape[1] for k, v in ls.items()})
    n_bad = sum(len(v) for v in floating.values())
    if n_bad:
        sys.exit(f"有 {n_bad} 块悬空 / 碎块，见上面的列表")
