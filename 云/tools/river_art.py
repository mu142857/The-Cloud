"""河流星球视差（第二颗星）。以后改河流的图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_art.py [--preview 目录]

输出 art/river/*.png（1 倍）。

画面：深蓝的夜。月亮在右上（屏幕 x≈338），雾里的对岸立着一排巨大的石柱（越远越淡、根部化进雾里），
石柱前是一道低低的近岸，长着伞一样的怪树和挂着垂荚的细秆植物；中间一条很宽很慢的河，
越近越暗（近处的水映的是头顶最暗的天，远处映的是地平线上的雾光）。月亮在水里碎成一道亮纹（Godot 里的
glints 层，shader 让它闪）——这是第一眼的焦点，和晨（屏幕 x≈204）隔开一百多像素，晨面朝它。
晨走的是近岸：一条被月光照亮顶面的卵石线，下面很快沉进黑泥；岸上一棵歪向河的枯树、一根冲上岸的带根浮木、几丛芦苇。
最前景是近黑的芦苇 / 香蒲把画面框住。

规则（和森林一样）：480×270 屏幕，1 倍像素，alpha 只有 0/255，不描边；光从右上（月亮）来，
亮面略偏青灰、暗面偏深蓝（不偏绿、不偏紫：OKLCh 色相 246~258）。背景最亮（月亮、水里的亮纹）L≈0.67，
明显低于晨的身体（L≈0.8）。晨身后那条（地面往上 ~40 像素，y 186~226）是近处的暗水，几乎没有杂点。
除了 sky / glints（屏幕固定，480 宽），每层宽 960、左右无缝，Godot 里用 Parallax2D 横向重复。
所有随机都固定 seed。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.palette import from_lch, oklab_to_srgb, to_lab  # noqa: E402

W, H = 960, 270
SW = 480                 # 屏幕宽
GROUND = 226             # 主层地面的平均高度
HORIZON = 150            # 远岸 / 水面开始的那一行
MX, MY, MR = 338, 56, 11  # 月亮（屏幕坐标）和半径
OUT = Path(__file__).resolve().parents[1] / "art" / "river"

# 层名 -> 跟镜头的比例（Godot 场景里的 scroll_scale 照这个填）
SCROLL = {"sky": 0.0, "ridge": 0.05, "mist": 0.1, "shore": 0.16, "ripples": 0.3, "glints": 0.0,
          "water": 0.42, "main": 1.0, "front": 1.4}
GLINT_Y = HORIZON + 5    # glints.png 贴在屏幕的这一行（近对岸的岸线下面）
GLINT_H = 60
RIPPLE_Y = HORIZON + 1
RIPPLE_H = 74

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16


# ---------------------------------------------------------------- 颜色

def lch(L, C=None, h=256.0):
    """OKLCh -> sRGB 元组。C 不给就按亮度给一个克制的色度（暗处略饱和一点，像夜里的蓝）。"""
    if C is None:
        C = 0.022 + 0.07 * min(L, 0.45)
    return tuple(int(v) for v in from_lch(float(L), float(C), float(h)))


def bramp(n, L0, L1, h_dark=258.0, h_lit=248.0, C0=None, C1=None):
    """一条蓝色窄色阶（暗 -> 亮）：暗端更蓝更深，亮端往青灰偏一点（月光下的「暖」）。"""
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        L = L0 + (L1 - L0) * t
        C = None if C0 is None else C0 + ((C1 if C1 is not None else C0) - C0) * t
        out.append(lch(L, C, h_dark + (h_lit - h_dark) * t))
    return out


def mix(c, d, t):
    a, b = to_lab(c), to_lab(d)
    return tuple(int(v) for v in oklab_to_srgb((a + (b - a) * t)[None])[0])


def rgba(c):
    return tuple(int(v) for v in c) + (255,)


class Layer:
    """一层图：RGBA 数组，贴东西 / 点像素时左右绕回（无缝）。"""

    def __init__(self, w=W, h=H):
        self.a = np.zeros((h, w, 4), np.uint8)

    @property
    def w(self):
        return self.a.shape[1]

    def put(self, x, y, c, over=True):
        x, y = int(round(x)) % self.w, int(round(y))
        if 0 <= y < self.a.shape[0] and (over or self.a[y, x, 3] == 0):
            self.a[y, x] = rgba(c)

    def paste(self, img, x, y):
        h, w = img.shape[:2]
        W_ = self.w
        for px in (x - W_, x, x + W_):
            x0, y0 = max(0, px), max(0, y)
            x1, y1 = min(W_, px + w), min(self.a.shape[0], y + h)
            if x0 >= x1 or y0 >= y1:
                continue
            src = img[y0 - y:y1 - y, x0 - px:x1 - px]
            m = src[..., 3] > 0
            self.a[y0:y1, x0:x1][m] = src[m]

    def copy(self):
        o = Layer(self.a.shape[1], self.a.shape[0])
        o.a = self.a.copy()
        return o

    def save(self, name):
        Image.fromarray(self.a).save(OUT / f"{name}.png")


def smooth1d(n, rng, period, amp=1.0):
    """周期为 n 的平滑噪声（几条正弦叠起来），左右无缝。"""
    xs = np.arange(n)
    v = np.zeros(n)
    for k in range(1, 6):
        f = max(1, int(round(n / period * k)))
        v += rng.uniform(0.3, 1.0) / k * np.sin(2 * np.pi * f * xs / n + rng.uniform(0, 6.28))
    return v / np.abs(v).max() * amp


# ---------------------------------------------------------------- 天和水的底色（随高度 + 月光）

SKY_L = [(0, .098), (40, .108), (70, .126), (92, .148), (106, .172), (118, .205), (128, .24),
         (136, .278), (142, .315), (147, .345), (149, .355)]
WATER_L = [(150, .305), (153, .282), (158, .255), (165, .228), (174, .2), (185, .175),
           (197, .155), (210, .14), (226, .13), (270, .12)]
SKY_H, WATER_H = 257.0, 252.0
L_STEP = 0.018


def base_L(y):
    tab = SKY_L if y < HORIZON else WATER_L
    ys, ls = zip(*tab)
    return float(np.interp(y, ys, ls))


def glow(x, y):
    """月光把背景提亮多少（L）。x 是屏幕坐标，可以是数组。"""
    x = np.asarray(x, float)
    if y < HORIZON:
        d = np.hypot(x - MX, (y - MY) * 1.1)
        g = 0.12 * np.exp(-(d / 22) ** 2) + 0.075 * np.exp(-(d / 60) ** 2) + 0.035 * np.exp(-(d / 140) ** 2)
        g += 0.05 * np.exp(-((x - MX) / 85) ** 2) * np.exp(-((y - 147) / 9) ** 2)   # 月亮正下方的雾更亮
        return g
    # 水里：月亮下面一道很宽很淡的反光柱，往近处收掉
    return 0.045 * np.exp(-((x - MX) / 34) ** 2) * np.exp(-(y - HORIZON) / 22)


def bg_L(x, y):
    return base_L(y) + glow(x, y)


def L_color(L, y):
    return lch(L, None, SKY_H if y < HORIZON else WATER_H)


def quant_L(L):
    return np.round(np.asarray(L) / L_STEP) * L_STEP


def vnoise(h, w, cy, cx, rng):
    """平滑的值噪声（0..1），格子 cy×cx。"""
    gh, gw = int(h / cy) + 3, int(w / cx) + 3
    g = rng.random((gh, gw))
    ys, xs = np.arange(h) / cy, np.arange(w) / cx
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = ys - y0, xs - x0
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a, b = g[y0][:, x0], g[y0][:, x0 + 1]
    c, d = g[y0 + 1][:, x0], g[y0 + 1][:, x0 + 1]
    top, bot = a + (b - a) * fx[None], c + (d - c) * fx[None]
    return top + (bot - top) * fy[:, None]


def fbm(h, w, cy, cx, rng, octaves=4):
    v, amp, tot = np.zeros((h, w)), 1.0, 0.0
    for _ in range(octaves):
        v += amp * vnoise(h, w, cy, cx, rng)
        tot += amp
        amp, cy, cx = amp * 0.5, max(1.0, cy / 2), max(1.0, cx / 2)
    return v / tot


# 星河：从左上角斜着往月亮那边流下来，快到月亮时被月光吃掉（视线顺着它滑到月亮、再掉进水里的亮纹）
MW_P0, MW_P1 = np.array([-30.0, -14.0]), np.array([318.0, 96.0])


def milky_way_field():
    """返回 (提亮量 ΔL[H_sky, SW], 星河里星的密度权重)。很淡：最亮处只比天高 ~0.05。"""
    hs = HORIZON
    rng = np.random.default_rng(17)
    yy, xx = np.mgrid[0:hs, 0:SW].astype(float)
    d = MW_P1 - MW_P0
    ln = np.hypot(*d)
    t = ((xx - MW_P0[0]) * d[0] + (yy - MW_P0[1]) * d[1]) / ln ** 2         # 沿带 0..1
    s = ((xx - MW_P0[0]) * -d[1] + (yy - MW_P0[1]) * d[0]) / ln              # 横过带（像素，带符号）
    s = s + 6.0 * np.sin(t * 5.2 + 0.8) + 3.0 * np.sin(t * 13.0)             # 带子轻轻蜿蜒
    width = 32 - 12 * t
    core = np.exp(-(s / width) ** 2)
    n1 = fbm(hs, SW, 14, 22, rng)                                            # 一团团的星云
    n2 = fbm(hs, SW, 5, 8, rng, 3)
    lum = core * (0.35 + 1.1 * np.clip(n1 - 0.32, 0, 1)) * (0.75 + 0.5 * n2)
    lane = np.exp(-((s - 3 + 4 * np.sin(t * 9)) / (4.5 - 2 * t)) ** 2) * np.clip(n1 * 1.6 - 0.35, 0, 1)
    lum = lum * (1 - 0.85 * lane)                                            # 中间一条断续的暗尘带
    fade_end = np.clip((0.97 - t) / 0.3, 0, 1) * np.clip((t + 0.05) / 0.2, 0, 1)
    dm = np.hypot(xx - MX, (yy - MY) * 1.1)
    fade_moon = np.clip((dm - 30) / 70, 0, 1)                                # 月光把星河洗掉
    lum = lum * fade_end * fade_moon
    dl = 0.14 * lum * np.clip(1.25 - yy / 150, 0, 1)
    return dl, core * fade_end * fade_moon * (0.4 + n2)


# 月光照亮边的云带：(中心 x, 中心 y, 半长, 厚, 斜率, seed)。月亮下面一条长的压在月亮下半边，
# 往左下方一条条拉开、变暗（顺着它也看向月亮）。
CLOUDS = [
    (404, 72, 96, 11, -0.06, 61),
    (296, 88, 62, 8, -0.13, 62),
    (206, 104, 54, 7, -0.1, 63),
    (458, 38, 40, 6, 0.05, 64),
    (110, 117, 46, 5, -0.05, 65),
    (24, 100, 30, 4, 0.0, 67),
]


def cloud_mask():
    """不规则的长条云：一串大小不一的扁鼓包连起来，底边被切得比较平；两头的鼓包变小、断开。
    边上用细噪声啃一啃（不是光滑椭圆）。返回 bool[HORIZON, SW]。"""
    m = np.zeros((HORIZON, SW), bool)
    yy, xx = np.mgrid[0:HORIZON, 0:SW].astype(float)
    rough = vnoise(HORIZON, SW, 2.0, 3.0, np.random.default_rng(66))
    for cx, cy, hl, th, sl, sd in CLOUDS:
        rng = np.random.default_rng(sd)
        x = cx - hl
        f = np.zeros((HORIZON, SW))
        while x < cx + hl:
            u = (x - cx) / hl
            env = max(0.0, 1 - u * u) ** 0.7
            rx = (5 + 9 * env) * rng.uniform(0.7, 1.3)
            ry = th * (0.45 + 0.75 * env) * rng.uniform(0.75, 1.25)
            if rng.random() < 0.85 or abs(u) < 0.5:
                yc = cy + sl * (x - cx)
                e = ((xx - x) / rx) ** 2 + ((yy - (yc - ry * 0.35)) / ry) ** 2
                bottom = yy > yc + th * 0.3 * env + 0.6 + 1.3 * np.sin(xx * 0.11 + sd)   # 底边基本平，轻轻起伏
                f = np.maximum(f, np.where(bottom, 0, 1 - e))
            x += rx * rng.uniform(0.6, 1.1)
        m |= (f > 0) & (f + 0.28 * (rough - 0.5) > 0.06)
    for x in range(MX - MR - 3, MX + MR + 4):                                 # 月亮下半边：云的上沿是一条干净的弧
        u = (x - MX) / (MR + 3)
        y0 = int(round(MY + 5 + 2.5 * u * u + 0.8 * np.sin(x * 0.9)))
        m[y0:78, x] = True
    for _ in range(2):                                                        # 补掉一像素宽的缝
        h_ = np.zeros_like(m)
        h_[:, 1:-1] = m[:, :-2] & m[:, 2:]
        v_ = np.zeros_like(m)
        v_[1:-1] = m[:-2] & m[2:]
        m |= h_ | v_
    return m


def sky():
    """背景：天（月亮、光晕、一道淡星河、月光照边的云带、星）+ 水的底色。亮度场按 L_STEP 一档一档地 Bayer 抖动。"""
    lay = Layer(SW, H)
    xs = np.arange(SW)
    mw, mw_w = milky_way_field()
    cm = cloud_mask()
    cache = {}

    def paint_row(y, L):
        lo = np.floor(L / L_STEP)
        idx = lo + (BAYER[y % 4, xs % 4] < (L / L_STEP - lo))
        for x in range(SW):
            k = (int(idx[x]), y < HORIZON)
            if k not in cache:
                cache[k] = rgba(L_color(k[0] * L_STEP, y))
            lay.a[y, x] = cache[k]

    for y in range(H):
        L = bg_L(xs, y)
        if y < HORIZON:
            L = L + mw[y]
        paint_row(y, L)
    rng = np.random.default_rng(3)
    # 星：大多很暗；星河里密很多（多是 1 档的小点），避开月亮附近和云
    for _ in range(1800):
        x, y = int(rng.uniform(0, SW)), int(rng.uniform(1, 128))
        w_ = mw_w[y, x]
        if rng.random() > 0.05 + 1.1 * w_ ** 1.3 or np.hypot(x - MX, y - MY) < 52:
            continue
        L = bg_L(x, y) + mw[y, x] + rng.uniform(0.04, 0.1) + (0.07 if rng.random() < 0.08 else 0)
        L -= 0.025 * np.clip(1 - (128 - y) / 40, 0, 1)                    # 贴近地平线的雾里看不太清
        lay.a[y, x] = rgba(lch(L, 0.03, 250))
    # 几颗亮一点的星，带十字（只有很少几颗）
    for x, y in ((62, 18), (186, 9), (446, 104), (22, 76)):
        L = bg_L(x, y) + mw[y, x] + 0.2
        for dx, dy, k in ((0, 0, 1.0), (1, 0, .45), (-1, 0, .45), (0, 1, .45), (0, -1, .45)):
            lay.a[y + dy, x + dx] = rgba(lch(bg_L(x, y) + (L - bg_L(x, y)) * k, 0.03, 250))
    moon(lay)
    # 云：本体是天色加一点（离月亮近的被照亮、远的几乎和天一样暗，把星河 / 星挡掉），
    # 朝月亮那一边（左下的云是右上边，月亮下面的云是顶边）一条亮边，背光的底边暗一档。
    yy, xx = np.nonzero(cm)
    for y, x in zip(yy, xx):
        dx, dy = MX - x, MY - y
        dd = max(1e-6, np.hypot(dx, dy))
        ux, uy = dx / dd, dy / dd
        g = float(glow(x, y))
        L = bg_L(x, y) + 0.014 + 0.6 * g
        lit = False
        for k in (1, 2):                                                    # 朝月亮方向 1~2 格就出云：亮边
            qx, qy = int(round(x + ux * k)), int(round(y + uy * k))
            if not (0 <= qy < HORIZON and 0 <= qx < SW) or not cm[qy, qx]:
                L += (0.045 if k == 1 else 0.028) + 1.0 * g
                lit = True
                break
        if not lit:
            qx, qy = int(round(x - ux * 1.5)), int(round(y - uy * 1.5))
            if not (0 <= qy < HORIZON and 0 <= qx < SW) or not cm[qy, qx]:
                L -= 0.016                                                  # 背光的那条边
        L = min(L, 0.6)
        Lq = float(np.floor(L / L_STEP + (BAYER[y % 4, x % 4] < (L / L_STEP) % 1)) * L_STEP)
        lay.a[y, x] = rgba(L_color(Lq, y))
    return lay


def moon(lay):
    """满月，偏青灰，比晨暗得多（最亮 L≈0.68）。右上受光的一弯亮一档，左下边暗一档，两块很淡的月海。"""
    body, lit, dark, spot = lch(.64, .016, 250), lch(.68, .013, 246), lch(.6, .02, 254), lch(.605, .018, 254)
    spots = [(-3, -3, 3.4), (3, 2, 2.6), (-2, 5, 1.8)]
    for y in range(MY - MR - 1, MY + MR + 2):
        for x in range(MX - MR - 1, MX + MR + 2):
            dx, dy = x - MX, y - MY
            if np.hypot(dx, dy) > MR + 0.35:
                continue
            c = body
            for sx, sy, sr in spots:
                if np.hypot(dx - sx, dy - sy) < sr:
                    c = spot
            if np.hypot(dx + 2.2, dy - 2.2) > MR + 0.3:       # 右上：一弯亮边
                c = lit
            if np.hypot(dx - 1.6, dy + 1.6) > MR + 0.3:       # 左下：一弯暗边
                c = dark
            lay.a[y, x] = rgba(c)


# ---------------------------------------------------------------- 远处：往背景色里褪

_MIX = {}


def fade(lay, t_of_y, steps=6, shift=0):
    """把每个像素往「同一位置的背景色」推 t(y)。t 按 1/steps 分档，两档之间 Bayer 抖动（不出横向台阶）。
    shift：这一层在镜头 ≈240 时相对屏幕的偏移（层坐标 - shift = 屏幕坐标），用来对上月光。"""
    a = lay.a
    ww = a.shape[1]
    xs = np.arange(ww)
    for y in range(a.shape[0]):
        m = a[y, :, 3] > 0
        if not m.any():
            continue
        tc = float(np.clip(t_of_y(y), 0, 1)) * steps
        lo = np.floor(tc)
        fr = tc - lo
        tq = (lo + (BAYER[y % 4, xs % 4] < fr)) / steps
        sx = (xs - shift) % ww
        tgtL = quant_L(np.where(sx < SW, bg_L(np.minimum(sx, SW - 1), y), base_L(y)))
        for x in np.nonzero(m)[0]:
            t = tq[x]
            if t <= 0:
                continue
            src = tuple(int(v) for v in a[y, x, :3])
            key = (src, float(tgtL[x]), y < HORIZON, float(t))
            if key not in _MIX:
                _MIX[key] = mix(src, L_color(float(tgtL[x]), y), min(1.0, t))
            a[y, x, :3] = _MIX[key]


def reflect(lay, waterline, length, seed, base_mix=0.45, end_mix=0.95, x_range=None, shift=0, gaps=0.3):
    """把水线以上的东西倒过来画到水线下面：越往下越往水色褪、越碎（一条条横向的缺口），每行左右错 0~2 像素。
    只画在空的地方；倒影只到 waterline+length。"""
    rng = np.random.default_rng(seed)
    a = lay.a
    ww = a.shape[1]
    xs = np.arange(ww)
    src = a.copy()
    cells = rng.random((length + 1, ww // 3 + 2))
    for r in range(length):
        sy = waterline - 1 - r
        dy = waterline + r
        if sy < 0 or dy >= H:
            break
        f = r / length
        wob = int(round(np.sin(r * 1.37 + seed) * (0.4 + 1.6 * f)))
        row = np.roll(src[sy], wob, axis=0)
        m = (row[:, 3] > 0) & (a[dy, :, 3] == 0)
        if x_range is not None:
            m &= (xs >= x_range[0]) & (xs < x_range[1])
        m &= cells[r, xs // 3] > (gaps * 0.5 + gaps * 1.6 * f)     # 横向的碎缝，越远越碎
        if r % 3 == 2:
            m &= cells[r, (xs + 1) // 2 % (ww // 3)] > 0.5          # 每三行一条稀的
        t = base_mix + (end_mix - base_mix) * f
        tq = np.floor(t * 4 + (BAYER[dy % 4, xs % 4] < (t * 4 % 1))) / 4
        for x in np.nonzero(m)[0]:
            sx = (x - shift) % ww
            tgt = float(quant_L(bg_L(min(sx, SW - 1), dy) if sx < SW else base_L(dy)))
            s = tuple(int(v) for v in row[x, :3])
            key = (s, tgt, False, float(tq[x]))
            if key not in _MIX:
                _MIX[key] = mix(s, L_color(tgt, dy), min(1.0, tq[x]))
            a[dy, x] = rgba(_MIX[key])


# ---------------------------------------------------------------- 石柱（远岸）

def _walk(rng, n, step=0.35, amp=1.0):
    """一维随机游走（平滑一下），给边缘的风化起伏用。"""
    v = np.cumsum(rng.normal(0, step, n))
    v -= np.linspace(v[0], v[-1], n)
    k = np.ones(3) / 3
    v = np.convolve(np.pad(v, 1, mode="edge"), k, mode="valid")
    return v / max(1e-6, np.abs(v).max()) * amp


def pillar_mask(w, h, rng, kind, broken):
    """石柱的形（bool[ih, iw]），柱脚在最底一行正中。每根的斜、弯、鼓肚、缺口、断顶都从 rng 来。"""
    pad = 14
    iw, ih = int(w * 2.6) + 2 * pad, h + 10
    top = 10
    cx = iw / 2
    m = np.zeros((ih, iw), bool)
    yv = np.arange(h)
    f = yv / max(1, h - 1)
    top_off = rng.uniform(-0.09, 0.09) * h                       # 整根歪
    bend = rng.uniform(-0.05, 0.05) * h                          # 中间弯
    cen = cx + top_off * (1 - f) + bend * np.sin(np.pi * f)
    eL = _walk(rng, h, amp=0.16) + 0.07 * np.sin(yv / rng.uniform(5, 9) + rng.uniform(0, 6))
    eR = _walk(rng, h, amp=0.16) + 0.07 * np.sin(yv / rng.uniform(5, 9) + rng.uniform(0, 6))
    cutL, cutR = np.zeros(h), np.zeros(h)
    for _ in range(int(rng.integers(3, 8))):                      # 风化出来的缺口：上沿切得深，往下斜着长回来
        y0, ln, dep = int(rng.integers(2, max(3, h - 8))), int(rng.integers(3, 13)), rng.uniform(1.0, 2.2 + w * 0.08)
        side = cutL if rng.random() < 0.5 else cutR
        for k in range(ln):
            if y0 + k < h:
                side[y0 + k] = max(side[y0 + k], dep * (1 - k / ln) ** 0.7)
    if kind == "spire":
        prof = 0.16 + 0.84 * f ** rng.uniform(0.5, 0.9)
    elif kind == "hoodoo":
        prof = rng.uniform(0.42, 0.6) + 0.42 * f ** 1.3
    elif kind == "twin":
        prof = rng.uniform(0.85, 1.0) + 0.15 * f
    else:
        prof = rng.uniform(0.74, 0.9) + 0.2 * f + rng.uniform(-0.12, 0.12) * np.sin(np.pi * f)
    if kind == "stack":                                          # 几块大石头摞起来，每块宽窄、左右错开都不一样
        nb = int(rng.integers(2, 5))
        cuts = np.sort(rng.uniform(0.12, 0.8, nb - 1))
        bounds = [0] + [int(c * h) for c in cuts] + [h]
        for b in range(nb):
            a0, a1 = bounds[b], bounds[b + 1]
            wf, dx = rng.uniform(0.62, 1.12), rng.uniform(-0.14, 0.14) * w
            for yy in range(a0, a1):
                g = (yy - a0) / max(1, a1 - a0 - 1)
                prof[yy] = wf * (0.86 + 0.14 * np.sin(np.pi * g) ** 0.5) * (0.75 if yy in (a0, a1 - 1) else 1)
                cen[yy] += dx
    hw = w / 2 * prof
    hw = hw + np.maximum(0, f - 0.85) / 0.15 * w * rng.uniform(0.25, 0.5)     # 脚下摊开（碎石坡）
    split = int(h * rng.uniform(0.18, 0.42)) if kind == "twin" else -1
    twin_top = int(split * rng.uniform(0.2, 0.6)) if kind == "twin" else 0
    for yy in range(h):
        y = top + yy
        l = cen[yy] - hw[yy] * (1 + eL[yy]) + cutL[yy]
        r = cen[yy] + hw[yy] * (1 + eR[yy]) - cutR[yy]
        if yy < 3 and kind != "spire":
            sh = (3 - yy) * 0.12 * (r - l)
            l, r = l + sh * rng.uniform(0.3, 1.0), r - sh * rng.uniform(0.3, 1.0)
        if yy < split:                                            # 两根指头：中间裂开，越往上缝越宽
            gap = 1 + (split - yy) / split * hw[yy] * 0.5
            mid = (l + r) / 2 + hw[yy] * 0.1
            spans = [(l, mid - gap / 2)] + ([(mid + gap / 2, r)] if yy >= twin_top else [])
        else:
            spans = [(l, r)]
        for a, b in spans:
            x0, x1 = int(round(a)), int(round(b))
            m[y, max(0, x0):min(iw, max(x0 + 1, x1))] = True
    if kind == "hoodoo":                                          # 帽石：比脖子宽很多、往一边歪着压在上面
        capH = max(4, int(h * rng.uniform(0.1, 0.2)))
        rx = w / 2 * rng.uniform(1.0, 1.5)
        ox = rng.uniform(-0.25, 0.25) * w
        tilt = rng.uniform(-0.22, 0.22)
        ccx, ccy = cen[0] + ox, top + capH * 0.45
        nz = smooth1d(iw, rng, 6, 1.0)
        for y in range(top - 6, top + capH + 2):
            for x in range(iw):
                dx = (x - ccx) / rx
                dy = (y - ccy - tilt * (x - ccx)) / (capH * 0.55)
                e = abs(dx) ** 2.6 + (abs(dy) ** 2.2 if dy < 0 else abs(dy) ** 4)
                if e < 1 + 0.12 * nz[x] and 0 <= y < ih:
                    m[y, x] = True
    if broken:                                                    # 断顶：一刀斜着、带锯齿
        yc = top + rng.uniform(0.04, 0.16) * h
        sl = rng.choice([-1, 1]) * rng.uniform(0.25, 0.7)
        jag = np.cumsum(rng.integers(-1, 2, iw))
        for x in range(iw):
            cut = yc + sl * (x - cx) + 0.6 * jag[x] % 3
            m[:max(0, int(cut)), x] = False
    # 柱脚的碎石：几块小圆石靠在脚边
    for _ in range(int(rng.integers(2, 6))):
        bx = cen[-1] + rng.choice([-1, 1]) * (hw[-1] + rng.uniform(-2, 4))
        bw, bh = rng.uniform(1.5, 3.5 + w * 0.06), rng.uniform(1.2, 3.0)
        for y in range(ih - 1 - int(bh) - 1, ih):
            for x in range(int(bx - bw) - 1, int(bx + bw) + 2):
                if 0 <= x < iw and ((x - bx) / bw) ** 2 + ((y - (ih - 1)) / bh) ** 2 < 1:
                    m[y, x] = True
    return m, top


def shade_rock(m, rng, pal, cracks=(2, 6), seams=True):
    """按形状上色（光从右上的月亮来）：竖着三个切面，右边一条亮边，顶面亮；
    被自己挡住月光的地方（帽石下面、缺口里）落进最暗的影子；几条往下爬的裂缝（暗一档，裂缝右唇亮一档），
    几条不横贯全宽的岩层缝，几个风蚀的小洞。返回 RGBA。"""
    ih, iw = m.shape
    n = len(pal)
    v = np.full((ih, iw), -1.0)
    fac1 = 0.3 + 0.07 * np.sin(np.arange(ih) / rng.uniform(5, 9) + rng.uniform(0, 6))
    fac2 = 0.63 + 0.07 * np.sin(np.arange(ih) / rng.uniform(4, 8) + rng.uniform(0, 6))
    for y in range(ih):
        row = m[y]
        if not row.any():
            continue
        xs_ = np.nonzero(row)[0]
        runs = np.split(xs_, np.nonzero(np.diff(xs_) > 1)[0] + 1)
        for run in runs:
            a, b = run[0], run[-1]
            for x in run:
                u = (x - a) / max(1, b - a)
                vv = (n - 1) * (0.08 if u < fac1[y] else (0.3 if u < fac2[y] else 0.55))
                if b - a >= 3:
                    if x == b:
                        vv = n - 1
                    elif x == b - 1:
                        vv = max(vv, n - 2)
                    elif x == a:
                        vv = 0
                elif x == b:
                    vv = n - 2
                if y == 0 or not m[y - 1, x]:
                    vv = n - 1 if u > 0.3 else n - 2               # 朝上的面
                v[y, x] = vv
    # 自己的影子：往月亮方向（右上）走，出了石头又撞回石头 = 被挡住
    for y, x in zip(*np.nonzero(m)):
        out = False
        for k in range(1, 16):
            qy, qx = y - k, int(round(x + 0.6 * k))
            if qy < 0 or qx >= iw:
                break
            if not m[qy, qx]:
                out = True
            elif out:
                v[y, x] = min(v[y, x], 0.0 if k < 9 else 0.6)
                break
    # 岩层缝：从一边伸进去一截，不横贯
    if seams:
        rows = np.nonzero(m.any(1))[0]
        for _ in range(int(rng.integers(2, 6))):
            y = int(rng.choice(rows[3:-6])) if len(rows) > 12 else None
            if y is None:
                break
            xs_ = np.nonzero(m[y])[0]
            a, b = xs_[0], xs_[-1]
            ln = int((b - a) * rng.uniform(0.3, 0.85))
            from_left = rng.random() < 0.5
            yy = y
            for k in range(ln):
                x = a + k if from_left else b - k
                if rng.random() < 0.15:
                    yy += rng.choice([-1, 1])
                if 0 <= yy < ih and m[yy, x]:
                    v[yy, x] = min(v[yy, x], 0.6)
                    if yy + 1 < ih and m[yy + 1, x] and x > (a + b) / 2:
                        v[yy + 1, x] = max(v[yy + 1, x], n - 2)    # 缝下面的岩檐受光
    # 竖着往下爬的裂缝
    pts = np.argwhere(m)
    for _ in range(int(rng.integers(*cracks))):
        y, x = pts[int(rng.integers(0, len(pts) // 2))]
        ln = int(rng.uniform(0.15, 0.55) * ih)
        for k in range(ln):
            if rng.random() < 0.3:
                x += rng.choice([-1, 1])
            y += 1
            if not (0 <= y < ih and 0 <= x < iw) or not m[y, x]:
                break
            if 0 < x < iw - 1 and m[y, x - 1] and m[y, x + 1]:
                v[y, x] = max(0, v[y, x] - 1.6)
                if v[y, x + 1] < n - 2 and rng.random() < 0.6:
                    v[y, x + 1] = v[y, x + 1] + 1
    # 风蚀小洞：一两个暗的小坑，坑口右上一点亮
    for _ in range(int(rng.integers(0, 4))):
        y, x = pts[int(rng.integers(0, len(pts)))]
        for dy, dx in ((0, 0), (0, 1), (1, 0), (1, 1)):
            if 0 <= y + dy < ih and 0 <= x + dx < iw and m[y + dy, x + dx]:
                v[y + dy, x + dx] = 0
    img = np.zeros((ih, iw, 4), np.uint8)
    for y, x in zip(*np.nonzero(m)):
        img[y, x] = rgba(pal[int(np.clip(round(v[y, x]), 0, n - 1))])
    return img


def pillar(w, h, seed, pal, crown=None, kind="tower", broken=False):
    """一根巨大的石柱（像张家界、像风蚀的石笋）。kind：tower 直上直下 / spire 越往上越尖 /
    hoodoo 细脖子顶一块歪着的帽石 / stack 几块大石摞起来 / twin 顶上裂成两根指头。broken = 断顶。
    crown = 顶上长的垂叶植物的色阶。返回 RGBA，柱脚在图的底边正中。"""
    rng = np.random.default_rng(seed)
    m, top = pillar_mask(w, h, rng, kind, broken)
    img = shade_rock(m, rng, pal, cracks=(1 + w // 14, 3 + w // 7))
    ih, iw = m.shape
    if crown is not None:   # 顶上一丛垂下来的怪植物：几根往两边弯下的叶片，挂过柱顶的边
        ys, xs_ = np.nonzero(m)
        ty = ys.min()
        tx = xs_[ys == ty].mean()
        nc = len(crown)
        for i in range(int(rng.integers(3, 8))):
            side = -1 if rng.random() < 0.5 else 1
            ln = rng.uniform(w * 0.3, w * 0.9)
            px, py = tx + rng.uniform(-w * 0.25, w * 0.25), ty + 1.0
            ang = rng.uniform(-1.9, -1.2)
            steps = int(ln * 1.6)
            turn = rng.uniform(1.4, 2.3) / max(1, steps)              # 一片叶子总共只弯过 80~130 度，不打卷
            for s_ in range(steps):
                ang += turn
                px += np.cos(ang) * side * 0.6
                py += np.sin(ang) * 0.6
                xi, yi = int(round(px)), int(round(py))
                if 0 <= xi < iw and 0 <= yi < ih:
                    img[yi, xi] = rgba(crown[min(nc - 1, 1 if side > 0 else 0)])
    return keep_attached(img, ih - 1)


def components(mask, wrap=False):
    """8 连通区域标号（wrap = 左右绕回）。返回 (labels, n)，0 = 空。"""
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


def keep_attached(img, base_row):
    """只留和 base_row 那一行连着的像素（扔掉画飞了的碎叶）。"""
    m = img[..., 3] > 0
    lab, n = components(m)
    if n <= 1:
        return img
    keep = set(lab[base_row][lab[base_row] > 0].tolist())
    if not keep:
        return img
    img = img.copy()
    img[~np.isin(lab, list(keep)) & m] = 0
    return img


def ridge():
    """远岸的两排石柱：后排更矮、更淡；前排高，有几根顶上长着垂叶。柱脚都化进地平线上的雾里。
    月亮在屏幕 338：前排 390 那根正好立在月亮右下，月亮挂在它旁边。"""
    lay = Layer()
    back = bramp(4, .19, .26, 258, 250)
    front = bramp(5, .12, .25, 258, 246)
    crown = bramp(2, .12, .15, 258, 252)
    shore_c = bramp(3, .14, .17, 258, 252)
    # (x, 宽, 高, 形, 断顶, 顶上长垂叶)：每根都不一样——歪的、弯的、摞起来的、裂成两指的、断了顶的
    rows = [
        (back, [(40, 18, 56, "stack", False, False), (98, 11, 44, "spire", True, False),
                (228, 24, 66, "hoodoo", False, False), (300, 13, 52, "spire", False, False),
                (468, 22, 60, "twin", False, False), (612, 30, 80, "tower", True, False),
                (690, 12, 40, "spire", False, False), (818, 20, 62, "hoodoo", False, False),
                (905, 15, 46, "stack", True, False)]),
        (front, [(148, 32, 124, "twin", False, True), (186, 13, 66, "spire", True, False),
                 (432, 24, 96, "stack", False, True), (540, 42, 136, "tower", True, False),
                 (588, 17, 78, "spire", False, False), (762, 22, 90, "hoodoo", False, True),
                 (872, 30, 112, "tower", False, True), (14, 13, 52, "spire", True, False)]),
    ]
    for r_i, (pal, cols) in enumerate(rows):
        for i, (x, w, h, kind, brk, cr) in enumerate(cols):
            img = pillar(w, h, 100 * r_i + i + 7, pal, crown=crown if cr else None, kind=kind, broken=brk)
            lay.paste(img, x - img.shape[1] // 2, HORIZON + 1 - img.shape[0])
        if r_i == 0:   # 后排褪得更多一点
            fade(lay, lambda y: 0.32 + 0.55 * np.clip((y - 96) / 54, 0, 1) ** 1.3, shift=12)
    # 远岸：一条贴着地平线的低岸，几簇很小的灌木
    rng = np.random.default_rng(7)
    noise = smooth1d(W, rng, 40, 1.0)
    for x in range(W):
        hgt = 1 + int(round(1.2 + noise[x] * 1.3))
        for d in range(hgt):
            lay.put(x, HORIZON - d, shore_c[1 if d == hgt - 1 else 0])
    # 整层往雾里褪：顶上褪一点（离得远），柱脚褪成雾
    fade(lay, lambda y: 0.08 + 0.75 * np.clip((y - 104) / 46, 0, 1) ** 1.5, shift=12)
    return lay


# ---------------------------------------------------------------- 近一点的对岸：怪树和垂荚

def _canopy(lay, cx, cy, cw, rng, pal, tilt=0.0, thick=4.0, dome=2.5, drip=1.0, ragged=0.0, gap=None, drip_len=1.0):
    """一片扁伞冠：上沿一个个小鼓包（右半边受光），下沿平、略往两边垂；冠沿挂下一缕缕长短不一的须，
    有的须末端坠一颗小珠。tilt = 冠面斜率；ragged = 冠沿被扯掉的比例；gap = (u0, u1) 冠上缺的一段（断冠）。"""
    n = len(pal)
    half = cw / 2
    lumps = smooth1d(64, rng, 9, 1.0)
    for j in range(-int(half), int(half) + 1):
        u = j / half
        if gap is not None and gap[0] < u < gap[1]:
            continue
        if abs(u) > 0.6 and rng.random() < ragged:
            continue
        env = max(0.0, 1 - u * u)
        th = max(1, int(round(thick * env ** 0.45 + 0.8 * lumps[int((u + 1) * 31)])))
        yt = cy - int(round(dome * env + 1.0 * max(0.0, lumps[int((u + 1) * 31)]))) + int(round(tilt * j))
        droop = int(round(1.6 * abs(u) ** 3))
        for k in range(th + droop):
            v = 0
            if k == 0:
                v = n - 1 if u > -0.35 + 0.15 * lumps[int((u + 1) * 31)] else 1
            elif k == 1 and u > 0.3:
                v = 1
            lay.put(cx + j, yt + k, pal[v])
        if abs(u) > 0.15 and rng.random() < 0.5 * drip:                 # 须：一簇簇，长短很不一样
            ln = int(rng.integers(1, 3 + int(9 * abs(u) * min(drip, 1.3))) * drip_len)
            if rng.random() < 0.12:
                ln += int(rng.integers(4, 9) * drip_len)
            wob = rng.choice([-1, 0, 0, 1])
            for k in range(ln):
                lay.put(cx + j + (wob if k > ln * 0.6 else 0), yt + th + droop + k, pal[0])
            if ln > 5 and rng.random() < 0.35:
                lay.put(cx + j + wob, yt + th + droop + ln, pal[1])


def strange_tree(lay, x, base, h, cw, seed, pal, kind="umbrella"):
    """对岸的怪树。每棵都不一样：
    umbrella = 细干顶一片伞冠（干会弯、冠会斜）；lean = 被风压歪的；weeping = 薄冠、帘子一样的长须；
    mushroom = 厚圆顶、几乎没须；tiered = 主冠下面再从干上斜伸出一小片冠；
    fork = 干分两杈，各顶一片大小不同的冠；broken = 干在半截折断，上半截连着半片冠倒挂下来；
    dead = 只剩一根歪干和几根断枝，枝上挂着几缕干须；young = 矮的小伞。"""
    rng = np.random.default_rng(seed)
    n = len(pal)

    def trunk(x0, y0, x1, y1, wd, bow):
        """二次曲线的干，根部宽、往上细；返回沿途的点。"""
        pts = []
        mx, my = (x0 + x1) / 2 + bow, (y0 + y1) / 2
        steps = int(abs(y1 - y0) + abs(x1 - x0)) + 2
        for i in range(steps + 1):
            t = i / steps
            px = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1
            py = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1
            pts.append((px, py))
            w_ = wd * (1 - 0.5 * t)
            lay.put(px, py, pal[0])
            if w_ >= 1.5:
                lay.put(px + 1, py, pal[1])
        return pts

    lean = rng.uniform(-0.3, 0.3) * h
    bow = rng.uniform(-0.25, 0.25) * h
    wd = 2.0 if h > 26 else 1.0
    for d in (-2, -1, 1, 2):                                          # 根脚
        if abs(d) == 1 or h > 30:
            lay.put(x + d, base, pal[0])
    tilt = rng.uniform(-0.12, 0.12)
    if kind == "lean":                                               # 被风压歪的：干斜得厉害，冠顺着歪
        lean = rng.choice([-1, 1]) * rng.uniform(0.45, 0.6) * h
        bow = -lean * 0.35
        tilt = 0.1 * np.sign(lean)
    if kind in ("umbrella", "young", "tiered", "lean", "weeping", "mushroom"):
        pts = trunk(x, base, x + lean, base - h, wd, bow)
        tx, ty = pts[-1]
        if kind == "weeping":                                        # 薄薄一片冠，垂须像帘子一样长
            _canopy(lay, tx, ty, cw, rng, pal, tilt=tilt, thick=2.0, dome=1.2, drip=1.9, drip_len=2.0,
                    ragged=0.1)
        elif kind == "mushroom":                                     # 厚的圆顶，像一朵蘑菇，几乎没有须
            _canopy(lay, tx, ty + 1, cw, rng, pal, tilt=tilt * 0.5, thick=rng.uniform(5.5, 7), dome=rng.uniform(3.5, 5),
                    drip=0.35)
        else:
            _canopy(lay, tx, ty, cw, rng, pal, tilt=tilt, thick=rng.uniform(3, 5), dome=rng.uniform(1.5, 3.5),
                    drip=rng.uniform(0.6, 1.3), ragged=rng.uniform(0, 0.25))
        if kind == "tiered":
            px, py = pts[int(len(pts) * rng.uniform(0.45, 0.6))]
            side = rng.choice([-1, 1])
            ex, ey = px + side * cw * 0.35, py - h * 0.12
            trunk(px, py, ex, ey, 1, 0)
            _canopy(lay, ex, ey, cw * rng.uniform(0.4, 0.55), rng, pal, tilt=-side * 0.15, thick=2.5, dome=1.2)
    elif kind == "fork":
        pts = trunk(x, base, x + lean * 0.4, base - h * 0.55, wd, bow * 0.5)
        fx, fy = pts[-1]
        for side, hk, ck in ((-1, rng.uniform(0.3, 0.45), rng.uniform(0.55, 0.75)), (1, rng.uniform(0.4, 0.6), 1.0)):
            p2 = trunk(fx, fy, fx + side * cw * 0.28, fy - h * hk, 1, side * 2)
            _canopy(lay, p2[-1][0], p2[-1][1], cw * ck, rng, pal, tilt=side * 0.08 + tilt,
                    thick=rng.uniform(2.5, 4), dome=rng.uniform(1, 2.5), drip=rng.uniform(0.6, 1.2))
    elif kind == "broken":
        hb = h * rng.uniform(0.5, 0.7)
        pts = trunk(x, base, x + lean * 0.5, base - hb, wd, bow * 0.5)
        bx, by = pts[-1]
        side = rng.choice([-1, 1])
        lay.put(bx + side, by - 1, pal[n - 1])                       # 断口：一两格露出来的白茬
        lay.put(bx, by - 2, pal[1])
        p2 = trunk(bx, by, bx + side * h * 0.25, by + h * 0.2, 1, side * 3)     # 上半截倒挂下来
        _canopy(lay, p2[-1][0], p2[-1][1] + 2, cw * 0.6, rng, pal, tilt=side * 0.45, thick=2.5, dome=1.0,
                drip=1.4, ragged=0.35, gap=(-0.2, 0.3) if rng.random() < 0.5 else None)
    else:  # dead
        pts = trunk(x, base, x + lean, base - h, wd, bow)
        for frac in sorted(rng.uniform(0.45, 0.95, int(rng.integers(2, 5)))):
            px, py = pts[int(frac * (len(pts) - 1))]
            side = rng.choice([-1, 1])
            ln = rng.uniform(3, cw * 0.4)
            ang = rng.uniform(-1.2, -0.3)
            qx, qy = px, py
            for k in range(int(ln)):
                ang += 0.12
                qx += np.cos(ang) * side
                qy += np.sin(ang)
                lay.put(qx, qy, pal[0])
            for k in range(int(rng.integers(0, 6))):                  # 枝头挂一缕干须
                lay.put(qx, qy + 1 + k, pal[0])
        tx, ty = pts[-1]
        lay.put(tx, ty - 1, pal[1])


def pod_reeds(lay, x, base, h, seed, pal, k=5):
    """一丛挂垂荚的细秆：每根秆弯上去，梢头像问号一样勾回来，挂一颗泪滴形的荚。"""
    rng = np.random.default_rng(seed)
    n = len(pal)
    for i in range(k):
        hh = h * rng.uniform(0.55, 1.0)
        bend = rng.uniform(-0.35, 0.35)
        px, py = x + rng.uniform(-4, 4), float(base)
        for s in range(int(hh)):
            t = s / hh
            px += bend * t * 1.4
            py -= 1
            lay.put(px, py, pal[0])
        side = 1 if bend >= 0 else -1      # 梢头往弯的那边勾下来
        for s in range(3):
            lay.put(px + side * (s + 1) * 0.8, py + s * 0.6, pal[0])
        hx, hy = px + side * 2.4, py + 2
        for dy in range(4):                # 荚
            wdt = (1, 2, 2, 1)[dy]
            for dx in range(wdt):
                c = pal[n - 1] if (dx == wdt - 1 and dy < 2) else pal[1]
                lay.put(hx + dx - (wdt == 2) * (side < 0), hy + dy, c)


def shore():
    """近一点的对岸：贴着 y=153 的低岸，岸上一丛丛伞树和垂荚的细秆，剪影比石柱暗。"""
    lay = Layer()
    pal = bramp(3, .115, .175, 258, 248)
    bank = bramp(3, .11, .16, 258, 250)
    base = HORIZON + 3
    rng = np.random.default_rng(21)
    noise = smooth1d(W, rng, 60, 1.0)
    for x in range(W):
        hgt = 2 + int(round(1.2 + 1.4 * noise[x]))
        for d in range(hgt):
            lay.put(x, base - d + 1, bank[2 if d == hgt - 1 and noise[x] > -0.2 else (1 if d >= hgt - 2 else 0)])
    trees = [(70, 30, 24, "tiered"), (112, 17, 11, "young"), (262, 44, 34, "weeping"), (298, 24, 16, "broken"),
             (382, 26, 18, "mushroom"), (470, 38, 30, "fork"), (508, 22, 10, "dead"), (560, 13, 9, "young"),
             (662, 46, 26, "lean"), (708, 30, 20, "dead"), (842, 36, 30, "fork"), (930, 20, 14, "mushroom"),
             (166, 34, 22, "umbrella"), (604, 28, 20, "weeping")]
    for i, (x, h, cw, kind) in enumerate(trees):
        tmp = Layer()
        strange_tree(tmp, x, base - 1, h, cw, 40 + i, pal, kind)
        lay.paste(keep_attached(tmp.a, base - 1), 0, 0)               # 被扯断的冠沿碎块不要
    for i, (x, h) in enumerate([(30, 16), (180, 22), (348, 18), (418, 14), (585, 24), (760, 20), (890, 16)]):
        pod_reeds(lay, x, base - 1, h, 60 + i, pal, k=int(rng.integers(3, 7)))
    fade(lay, lambda y: 0.12 + 0.35 * np.clip((y - 128) / 26, 0, 1), shift=38)
    return lay


# ---------------------------------------------------------------- 河里：几块石头、一根枯枝

def rock_in_water(lay, x, wl, w, h, seed, pal, foam):
    """露出水面的圆石：右上受光，左边暗，贴水线一行碎的亮边（水在拍它）。"""
    rng = np.random.default_rng(seed)
    n = len(pal)
    for j in range(-w // 2, w // 2 + 1):
        u = j / (w / 2)
        top = int(round(h * max(0.0, 1 - u * u) ** 0.55 + rng.uniform(-0.3, 0.3)))
        for k in range(top + 1):
            y = wl - k
            v = (n - 1) * (0.25 + 0.35 * (u + 1) / 2 + 0.4 * k / max(1, top))
            if k == top and u > -0.4:
                v = n - 1
            lay.put(x + j, y, pal[int(np.clip(round(v), 0, n - 1))])
        if rng.random() < 0.6:
            lay.put(x + j, wl + 1, foam)


def snag(lay, x, wl, h, seed, pal):
    """水里戳出来的一根枯枝：弯着往右上，两根细杈。"""
    rng = np.random.default_rng(seed)
    px, py = float(x), float(wl)
    pts = []
    for i in range(h):
        t = i / h
        px += 0.25 + 0.5 * t
        py -= 1
        pts.append((px, py))
        lay.put(px, py, pal[0])
        if t < 0.45:
            lay.put(px + 1, py, pal[1])
    for start, ln, dx, dy in ((0.45, 9, -0.7, -0.75), (0.7, 7, 0.9, -0.45)):
        qx, qy = pts[int(start * h)]
        for k in range(ln):
            qx += dx
            qy += dy + 0.05 * k
            lay.put(qx, qy, pal[0])
    _ = rng


def water_layer():
    lay = Layer()
    rock = bramp(4, .115, .19, 258, 248)
    foam = lch(.26, .035, 250)
    for x, wl, w, h, sd in ((250, 181, 18, 6, 1), (268, 183, 8, 3, 2), (700, 177, 12, 4, 3), (905, 185, 10, 4, 4)):
        rock_in_water(lay, x, wl, w, h, sd, rock, foam)
    snag(lay, 470, 184, 26, 5, rock)
    solid = lay.copy()
    for x0, x1, wl in ((236, 278, 182), (690, 712, 178), (896, 916, 186), (466, 500, 185)):
        reflect(lay, wl + 1, 9, wl, base_mix=0.55, end_mix=0.95, x_range=(x0, x1), shift=100)
    return lay, solid


# ---------------------------------------------------------------- 主层：晨走的近岸

def ground_y(x):
    """主层地面高度（卵石线最上面一行），左右无缝。Godot 里 river_test.gd 用同一个公式。"""
    return GROUND + 1.5 * np.sin(2 * np.pi * x * 2 / W) + 1.0 * np.sin(2 * np.pi * x * 5 / W + 2.0)


def dead_tree(lay, x, gy, pal, seed):
    """岸边一棵歪向河面的枯树：粗干往右上斜，分两三次杈，枝梢细而弯（光从右上来：右边一条亮）。"""
    rng = np.random.default_rng(seed)
    n = len(pal)

    def branch(px, py, ang, ln, th, depth):
        for s in range(int(ln * 2)):
            t = s / (ln * 2)
            ang += rng.normal(0, 0.035) + 0.004 * (1 if ang < -1.2 else -1)
            px += np.cos(ang) * 0.5
            py += np.sin(ang) * 0.5
            w_ = max(1.0, th * (1 - 0.6 * t))
            for k in range(int(round(w_))):
                c = pal[n - 1] if (k == int(round(w_)) - 1 and w_ >= 2) else pal[0 if k < w_ / 2 else 1]
                lay.put(px + k - w_ / 2, py, c)
            if depth > 0 and s > 6 and rng.random() < (0.035 if depth > 1 else 0.05):
                branch(px, py, ang + rng.choice([-1, 1]) * rng.uniform(0.45, 0.9), ln * rng.uniform(0.35, 0.55),
                       max(1, th * 0.5), depth - 1)
        return px, py

    px, py = branch(x, gy + 2, -1.25, 120, 7, 3)
    # 根：贴地往两边伸
    for side in (-1, 1):
        for k in range(2):
            ln = int(rng.uniform(6, 13))
            for i in range(ln):
                hh = max(1, int(round(2.5 * (1 - i / ln))) - k)
                for d in range(hh):
                    lay.put(x - 2 + side * (3 + i + k * 2), gy + 1 - d, pal[1 if d == hh - 1 and side > 0 else 0])


def driftwood(lay, x, gy_of, pal, seed):
    """冲上岸的浮木：一根被水泡白（最亮只到 L≈0.34）、拧着长的树干斜躺在卵石上，
    树皮上一条条螺旋的纹（拧出来的），两个疤、几根断掉的枝桩；右端是撕裂的断口（几根长短不一的木刺，
    断面露出更亮的木头）；左端一团朝天、朝两边张开的根，根互相缠着、越往外越细，有几根扎进地里。
    gy_of(x) = 这一列的地面高度。"""
    rng = np.random.default_rng(seed)
    n = len(pal)
    ln = 96
    # 中心线：左端被根撑起来一点，中段贴地，右端略翘；整根轻轻 S 弯
    th0, th1 = 12.0, 7.0
    cols = []
    for i in range(ln + 8):
        t = min(1.0, i / ln)
        th = th0 + (th1 - th0) * t ** 0.8 + 0.8 * np.sin(i * 0.21 + 1.3)
        lift = 3.0 * (1 - t) ** 3 + 1.2 * t ** 4 + 0.7 * np.sin(np.pi * t * 1.6)
        bot = gy_of(x + i) - lift + 1
        cols.append((th, bot))
    # 断口：每一行（离上沿 k）木头伸到 ln + jag[k]，几根长刺
    jag = {}
    for k in range(int(th1) + 2):
        jag[k] = int(rng.integers(-5, 3)) + (int(rng.integers(3, 8)) if rng.random() < 0.3 else 0)
    twist = rng.uniform(0.32, 0.45)
    grain_ph = rng.uniform(0, 10)
    knots = [(int(rng.uniform(18, 40)), rng.uniform(0.3, 0.6)), (int(rng.uniform(52, 75)), rng.uniform(0.2, 0.5))]
    for i, (th, bot) in enumerate(cols):
        tt = int(round(th))
        top = int(round(bot - tt))
        for k in range(tt):
            if i >= ln + jag.get(min(k, int(th1) + 1), 0):
                continue
            q = k / max(1, tt - 1)                                     # 0 = 上沿（受光），1 = 贴地
            v = (n - 1) * (0.95 - 0.72 * q ** 0.9)
            # 拧着的纹：一条条斜线（暗一档），朝光的上半截纹边上亮一点
            g = (i * twist + k * 1.0 + grain_ph) % 4.3
            if g < 0.9 and 0 < k < tt - 1:
                v -= 1.1
            elif g < 1.6 and q < 0.4:
                v += 0.4
            # 树皮上的短裂
            if rng.random() < 0.05 and 0 < k < tt - 1:
                v -= 1
            # 断口那一两列：露出来的新木头更亮
            end = ln + jag.get(min(k, int(th1) + 1), 0)
            if i >= end - 2 and q < 0.75:
                v = n - 1 if i == end - 1 else n - 2
            lay.put(x + i, top + k, pal[int(np.clip(round(v), 0, n - 1))])
    # 疤：暗的椭圆，右上一圈亮
    for ki, q in knots:
        th, bot = cols[ki]
        ky = bot - th * (1 - q)
        for dy in range(-1, 2):
            for dx in range(-2, 2):
                if abs(dx + 0.5) / 2 + abs(dy) / 1.5 < 1.0:
                    lay.put(x + ki + dx, ky + dy, pal[0])
        lay.put(x + ki + 1, ky - 1, pal[n - 1])
        lay.put(x + ki, ky - 2, pal[n - 2])
    # 断掉的枝桩：从上沿伸出一小截，往右上或左上，桩头斜着断、亮一点
    for si in (int(rng.uniform(28, 38)), int(rng.uniform(60, 70)), int(rng.uniform(80, 88))):
        th, bot = cols[si]
        px, py = x + si, bot - th
        side = rng.choice([-1, 1]) if si < 70 else 1
        sl = int(rng.integers(3, 8))
        for k in range(sl):
            px += 0.55 * side
            py -= 0.85
            lay.put(px, py, pal[1])
            lay.put(px + 1, py, pal[n - 2 if k < sl - 1 else n - 1])
    # 根盘：从左端的截面往外张开，根很多、弯着缠着，越往外越细；往下的扎进地里就停
    th, bot = cols[0]
    cy = bot - th / 2
    for j, a0 in enumerate(np.linspace(-3.4, -0.9, 13)):
        px, py = x + 1.0 + rng.uniform(-1, 1), cy + rng.uniform(-th / 2.5, th / 2.5)
        ang = a0 + rng.uniform(-0.15, 0.15)
        L = rng.uniform(10, 26) * (0.6 if j % 3 == 1 else 1.0)
        w0 = 3.2 if j % 2 == 0 else 2.0
        curl = rng.uniform(-0.09, 0.09)
        for s in range(int(L * 2)):
            t = s / (L * 2)
            ang += curl + rng.normal(0, 0.07)
            px += np.cos(ang) * 0.5
            py += np.sin(ang) * 0.5
            if py > gy_of(px) + 1:
                break
            wd = max(1, int(round(w0 * (1 - t))))
            lit = np.sin(ang) < -0.2 and np.cos(ang) > -0.6
            for d in range(wd):
                lay.put(px, py + d, pal[(n - 2 if lit else 2) if d == 0 else 1])
        if rng.random() < 0.5:                                          # 根梢分一根细须
            qx, qy = px, py
            a2 = ang + rng.choice([-1, 1]) * 0.8
            for s in range(int(rng.integers(3, 8))):
                qx += np.cos(a2) * 0.7
                qy += np.sin(a2) * 0.7
                if qy > gy_of(qx) + 1:
                    break
                lay.put(qx, qy, pal[0])
    # 截面（根盘中心）暗、一圈年轮亮边
    for dy in range(-int(th / 2) + 1, int(th / 2)):
        lay.put(x, cy + dy, pal[0])
        lay.put(x - 1, cy + dy, pal[1 if dy < 0 else 0])


def reeds(lay, x, gy, h, seed, pal, k=7, cattail=None):
    """一丛芦苇：细叶从根部散开、往一边弯；可选几根香蒲（棒头）。叶子右边沿一格亮（月光）。"""
    rng = np.random.default_rng(seed)
    n = len(pal)
    for i in range(k):
        hh = h * rng.uniform(0.45, 1.0)
        lean = rng.uniform(-0.5, 0.5)
        px, py = x + rng.uniform(-3, 3), float(gy)
        for s in range(int(hh)):
            t = s / hh
            px += lean * t * 0.9
            py -= 1
            lit = rng.random() < 0.35 and t > 0.3
            lay.put(px, py, pal[n - 1 if lit else 0])
            if t < 0.5 and hh > h * 0.7:
                lay.put(px + 1, py, pal[1 if t < 0.25 else 0])
    if cattail:
        for i in range(int(rng.integers(1, 3))):
            hh = int(h * rng.uniform(1.0, 1.3))
            px = x + rng.uniform(-2, 2)
            lean = rng.uniform(-0.12, 0.12)
            for s in range(hh + 12):                         # 秆一直通到棒头上面的细尖
                lay.put(px + lean * s, gy - s, pal[0])
            hx, top = px + lean * hh, gy - hh
            for s in range(2, 10):                           # 棒头：两像素宽，右边亮一档
                lay.put(hx + 1, top - s, cattail[1] if s < 8 else cattail[0])
                lay.put(hx, top - s, cattail[0])


def main_layer():
    """能走的近岸。上沿是一条被月光照亮顶面的卵石线（能走的边），往下两三行湿沙，再往下是近黑的泥，
    里面埋着几乎看不见的大石头和水草根。岸上：一棵歪向河的枯树、一根浮木、两三丛芦苇（都是暗剪影）。"""
    lay = Layer()
    rng = np.random.default_rng(5)
    stone = bramp(5, .17, .33, 258, 246)
    sand = bramp(3, .125, .165, 258, 250)
    mud = bramp(4, .1, .135, 260, 254)
    bark = bramp(3, .085, .15, 258, 248)
    wood = bramp(5, .12, .34, 258, 246)
    reed = bramp(3, .07, .13, 258, 250)
    cat = bramp(2, .09, .14, 262, 255)
    xs = np.arange(W)
    gys = np.round(ground_y(xs)).astype(int)
    noise = rng.random((H, W))
    for x in range(W):
        gy = gys[x]
        for y in range(gy, H):
            d = y - gy
            if d == 0:
                c = stone[1 + (noise[y, x] > 0.55) + (noise[y, x] > 0.85)]
            elif d == 1:
                c = stone[1] if noise[y, x] > 0.45 else sand[2]
            elif d < 5:
                c = sand[int(np.clip(round(2 - d * 0.45 + (noise[y, x] - 0.5)), 0, 2))]
            else:
                f = min(1.0, (d - 5) / 22)
                c = mud[int(np.clip(round(3 - 3.2 * f + (noise[y, x] - 0.5) * 0.8), 0, 3))]
            lay.a[y, x] = rgba(c)
    # 卵石：一颗颗半露在线上，右上受光；有几颗大一点、冒出地面一两行
    for _ in range(150):
        x = int(rng.uniform(0, W))
        gy = gys[x]
        w = int(rng.choice([2, 3, 3, 4, 5, 6, 8]))
        hgt = 1 if w < 4 else (2 if w < 7 else 3)
        sink = int(rng.integers(0, 2)) if w >= 4 else 0
        for j in range(w):
            u = (j - (w - 1) / 2) / max(1, (w / 2))
            top = int(round(hgt * max(0.0, 1 - u * u) ** 0.5))
            for k in range(top + 1 + 1):
                y = gy - top + k + sink
                v = 2 + (1 if u > -0.2 else 0) - (k > 0) - (k > 1) - (u < -0.6)
                lay.put(x + j, y, stone[int(np.clip(v + (k == 0 and u > 0.1), 0, 4))])
    # 泥里的东西：半埋的石头、碎卵石、树根、水草根、湿泥上的一点反光。越往下越少、越暗，
    # 最亮的也只比周围的泥亮一档（不抢亮度；晨脚下那条卵石线仍然是这一层最亮的东西）。
    def mud_L(d):
        return .135 - .035 * min(1.0, max(0, d - 5) / 22)

    def mc(d, dl, h=257.0):
        return lch(mud_L(d) + 1.35 * dl * (1 - 0.5 * min(1.0, d / 44)), None, h)

    def free(x, y):
        return 0 <= y < H

    for _ in range(84):                                               # 半埋的石头：露出一个圆顶，右上一条亮边，脚下一道影
        x = int(rng.uniform(0, W))
        d = int(6 + rng.random() ** 1.5 * 36)
        w = int(rng.choice([3, 4, 5, 6, 7, 9, 11, 14, 18]))
        ht = max(1, int(round(w * rng.uniform(0.22, 0.42))))
        y = gys[x % W] + d
        sk = rng.uniform(-0.3, 0.3)
        for j in range(w):
            u = (j - (w - 1) / 2) / max(1, w / 2)
            top = int(round(ht * max(0.0, 1 - u * u) ** 0.6 + sk * u))
            for k in range(max(1, top + 1)):
                yy = y - top + k
                c = mc(d, 0.013)
                if k == 0:
                    c = mc(d, 0.03) if u > -0.25 else mc(d, 0.02)
                elif u < -0.55:
                    c = mc(d, 0.004)
                lay.put(x + j, yy, c)
            lay.put(x + j, y + 1, mc(d, -0.016, 260))
    for _ in range(320):                                              # 碎卵石：一两个像素，越深越稀
        x = int(rng.uniform(0, W))
        d = int(5 + rng.random() ** 2.2 * 44)
        y = gys[x % W] + d
        w = int(rng.choice([1, 1, 2, 2, 3]))
        for j in range(w):
            lay.put(x + j, y, mc(d, 0.016 if j < w - 1 else 0.026))
        if w >= 2:
            lay.put(x, y + 1, mc(d, -0.012, 260))

    def root(px, py, ang, ln, w0):
        for s_ in range(int(ln)):
            t = s_ / ln
            ang += rng.normal(0, 0.12) + 0.03 * (np.pi / 2 - ang)      # 慢慢往下长
            px += np.cos(ang)
            py += np.sin(ang) * 0.8
            d = py - gys[int(px) % W]
            if d < 3:
                continue
            wd = max(1, int(round(w0 * (1 - t))))
            for k in range(wd):
                lay.put(px, py + k, mc(d, 0.02 if k == 0 else 0.008))
            if rng.random() < 0.06 and w0 > 1:
                root(px, py, ang + rng.choice([-1, 1]) * 0.9, ln * (1 - t) * 0.5, 1)

    for a0, ln, w0 in ((2.6, 46, 3), (2.2, 30, 2), (1.3, 22, 2), (0.5, 40, 3), (0.9, 26, 2), (2.9, 24, 2)):
        root(128 + rng.uniform(-3, 3), gys[128] + 2, a0, ln, w0)          # 枯树的根
    for a0, ln, w0 in ((2.4, 22, 2), (1.9, 16, 1), (2.9, 18, 1)):
        root(560, gys[560] + 2, a0, ln, w0)                               # 浮木根扎进泥里的那几根
    for rx in (44, 352, 760, 836, 220, 470, 640, 905):                     # 水草根：一束细须往下垂
        for _ in range(int(rng.integers(5, 11))):
            px, py = rx + rng.uniform(-5, 5), gys[rx % W] + 3
            for s_ in range(int(rng.uniform(4, 15))):
                py += 1
                px += rng.choice([-1, 0, 0, 0, 1]) * 0.7
                lay.put(px, py, mc(py - gys[int(px) % W], 0.012))
    for _ in range(70):                                               # 湿泥反光：很短的横的一两格，偏冷
        x = int(rng.uniform(0, W))
        d = int(5 + rng.random() ** 1.8 * 26)
        y = gys[x % W] + d
        for j in range(int(rng.integers(1, 5))):
            lay.put(x + j, y, mc(d, 0.03, 250))

    def gy_at(x):
        return gys[int(x) % W]

    dead_tree(lay, 128, gy_at(128), bark, 3)
    driftwood(lay, 560, lambda xx: gy_at(xx) - 1, wood, 4)
    for x, h, sd, ct in ((44, 26, 1, True), (352, 18, 2, False), (760, 30, 3, True), (836, 16, 4, False)):
        reeds(lay, x, gy_at(x) + 1, h, sd, reed, k=int(rng.integers(5, 9)), cattail=cat if ct else None)
    return lay


# ---------------------------------------------------------------- 前景

def blade(lay, x, gy, h, lean, width, pal, lit_side=1):
    """一片宽叶（水草 / 菖蒲）：从根部往上、往一边弯垂，越往上越细；右边沿亮一档。"""
    px, py = float(x), float(gy)
    ang = -np.pi / 2 + lean * 0.4
    for s in range(int(h * 1.2)):
        t = s / (h * 1.2)
        ang += lean * 0.012 * (1 + 2 * t)
        px += np.cos(ang) * 0.85
        py += np.sin(ang) * 0.85
        wd = max(1, int(round(width * (1 - t ** 2.2))))
        for k in range(wd):
            c = pal[-1] if (k == wd - 1 and wd > 1 and lit_side > 0) else pal[0]
            lay.put(px + k - wd // 2, py, c)


def front_layer():
    """最前景：近黑的宽叶水草、芦苇和香蒲从底边长上来，几丛高的把画面左右框住；底边一溜矮草。
    天不压：开阔的夜空就是这颗星的样子（森林是封顶的林冠，这里反过来）。"""
    lay = Layer()
    dark = bramp(3, .04, .08, 262, 255)
    cat = bramp(2, .05, .075, 262, 258)
    rng = np.random.default_rng(9)
    # (x, 高, 芦苇根数, 宽叶片数, seed)：只有 772 那丛是高的。前景 scroll 1.4，镜头左边缘在 0 / 240 / 520 / 820 时
    # 它落在屏幕 772 / 436 / 44 / 584：要么出画、要么在画面两边框住，不压在晨（≈204）、枯树和月亮的亮纹上。
    # （第一版 460 那丛高的在镜头 820 时正好叠在枯树前、紧挨着晨，改成矮的。）其余都矮。
    for x, h, k, nb, sd in ((470, 54, 3, 9, 1), (100, 50, 3, 8, 2), (250, 40, 2, 6, 3), (772, 136, 7, 22, 4),
                            (600, 46, 2, 7, 5), (900, 58, 3, 9, 6)):
        reeds(lay, x, H - 1 + 6, h, 100 + sd, dark, k=k, cattail=cat if h > 100 else None)
        for j in range(nb * 2):   # 一丛密的宽叶：大多数短、往外撇，叠成一团实的暗块，上沿是一圈叶尖
            f = rng.random() ** 1.6
            off = rng.normal(0, 7 + 3 * (1 - f))
            blade(lay, x + off, H + 4, h * (0.3 + 0.62 * f), off / 14 + rng.uniform(-0.4, 0.4),
                  rng.choice([3, 3, 4, 5]), dark)
    # 底边矮草
    for x in range(W):
        if np.sin(x * 0.011 + 1.3) + 0.6 * np.sin(x * 0.037) > 0.0:
            hh = int(rng.integers(2, 10))
            lean = rng.choice([-1, 0, 1])
            for s in range(hh):
                lay.put(x + (lean if s > hh * 0.6 else 0), H - 1 - s, dark[0])
    return lay


# ---------------------------------------------------------------- 会动的那几层（Godot 里 shader 让它们闪）

def glints():
    """月亮在水里碎成的一道亮纹：480×GLINT_H，贴在屏幕 y=GLINT_Y（不随镜头动——月亮的倒影总在你和月亮之间）。
    R = 亮度档（0..1），G = 闪烁相位，B = 闪烁快慢；Godot 的 river_water.gdshader 用 R 查调色板、G/B 让它闪。
    贴着地平线：一根很窄、很亮、几乎连成一片的竖柱（月亮自己的倒影）；往近处：亮纹变长、变稀、变暗、
    往两边散开；到晨身后（y≥192）只剩零星几条最暗的。"""
    rng = np.random.default_rng(31)
    img = np.zeros((GLINT_H, SW, 4), np.uint8)
    for r in range(GLINT_H):
        d = r / (GLINT_H - 1)
        if r > 3 and rng.random() < 0.85 * d ** 0.6:
            continue                                         # 越近越多空行（透视）
        hw = (MR + 2 if r < 8 else 7) + 40 * d ** 0.85
        base = 1.1 - 0.72 * d ** 0.9
        x = MX - hw * 1.2 - rng.uniform(0, 3)
        while x < MX + hw * 1.2:
            ln = 2 + int(rng.integers(0, 2 + int(9 * d)))
            u = (x + ln / 2 - MX) / hw
            tone = base * (1 - 0.6 * min(1.0, u * u)) + rng.normal(0, 0.1)
            if r < 8 and abs(u) < 0.8:
                tone = max(tone, 0.92)                       # 月亮自己的倒影
            keep = rng.random() < (0.95 - 0.55 * min(1.0, abs(u))) * (1.0 if r < 8 else 0.85)
            if tone > 0.05 and keep:
                ph, sp = rng.integers(0, 256), rng.integers(0, 256)
                for k in range(ln):
                    xi = int(round(x)) + k
                    if 0 <= xi < SW:
                        img[r, xi] = (int(np.clip(tone, 0, 1) * 255), ph, sp, 255)
            x += ln + (1 if r < 8 else 1 + rng.integers(0, 2 + int(5 * d)))
    return img


GLINT_PAL = [(.35, .032, 252), (.46, .032, 250), (.565, .028, 248), (.665, .02, 246)]


def ripples():
    """整条河上很淡的横向水纹：960×RIPPLE_H，贴在层坐标 y=RIPPLE_Y，scroll 0.3。
    像素存的就是颜色（比同一高度的水亮一两档），shader 只让它们左右晃、一会儿有一会儿没有。"""
    rng = np.random.default_rng(41)
    img = np.zeros((RIPPLE_H, W, 4), np.uint8)
    for r in range(RIPPLE_H):
        y = RIPPLE_Y + r
        d = r / (RIPPLE_H - 1)
        if r % (1 + int(d * 3)) and r > 4:
            continue
        L = base_L(y) + (0.032 if d < 0.5 else 0.022) + (0.018 if rng.random() < 0.3 else 0)
        c = rgba(L_color(float(quant_L(L)), y))
        x = rng.uniform(0, 30)
        while x < W:
            ln = 2 + int(rng.integers(0, 4 + int(10 * d)))
            if rng.random() < 0.42 - 0.3 * d:
                for k in range(ln):
                    img[r, (int(x) + k) % W] = c
            x += ln + rng.integers(4, 18 + int(30 * d))
    return img


def mist():
    """地平线上贴着水面的雾：一团团扁的雾堆（上沿起伏、下沿平，几个像素厚，两头用棋盘格点收掉），
    不是 1 像素的横线（那样叠在石柱脚上像扫描线）。比雾带亮一档，Godot 里 autoscroll 慢慢往左漂。"""
    lay = Layer()
    rng = np.random.default_rng(51)
    dens = smooth1d(W, rng, 160, 1.0)
    lumps = smooth1d(W, rng, 11, 1.0)
    for _ in range(46):
        x = int(rng.uniform(0, W))
        if rng.random() > 0.3 + 0.55 * dens[x]:
            continue
        yb = int(np.clip(rng.normal(149, 3.5), 140, 158))           # 雾堆的底
        ln = int(rng.uniform(18, 70))
        hh = rng.uniform(2.0, 5.5)
        L = base_L(yb) + 0.03 + (0.016 if rng.random() < 0.3 else 0)
        c = L_color(float(quant_L(L)), yb)
        c2 = L_color(float(quant_L(L - L_STEP)), yb)
        for k in range(ln):
            u = (k - ln / 2) / (ln / 2)
            top = hh * (1 - u * u) ** 0.6 * (0.75 + 0.35 * lumps[(x + k) % W])
            t = int(round(top))
            for d in range(t + 1):
                y = yb - d
                if (abs(u) > 0.7 or d == t) and (x + k + y) % 2:
                    continue                                       # 两头和上沿：隔一个点
                lay.put(x + k, y, c if d < t else c2)
    return lay


# ---------------------------------------------------------------- 组装、检查、预览

def build():
    OUT.mkdir(parents=True, exist_ok=True)
    rid = ridge()
    rid_solid = rid.copy()
    reflect(rid, HORIZON + 1, 40, 11, base_mix=0.16, end_mix=0.8, shift=12, gaps=0.22)
    sh = shore()
    sh_solid = sh.copy()
    reflect(sh, HORIZON + 4, 26, 12, base_mix=0.22, end_mix=0.85, shift=38, gaps=0.26)
    wat, wat_solid = water_layer()
    g = Layer(SW, GLINT_H)
    g.a = glints()
    rp = Layer(W, RIPPLE_H)
    rp.a = ripples()
    layers = {"sky": sky(), "ridge": rid, "mist": mist(), "shore": sh, "ripples": rp, "glints": g,
              "water": wat, "main": main_layer(), "front": front_layer()}
    for k, v in layers.items():
        v.save(k)
    solids = {"ridge": rid_solid, "shore": sh_solid, "water": wat_solid, "main": layers["main"],
              "front": layers["front"]}
    return layers, solids


SIZES = {"sky": (H, SW), "glints": (GLINT_H, SW), "ripples": (RIPPLE_H, W)}


def check_alpha(layers):
    for k, v in layers.items():
        u = set(np.unique(v.a[..., 3]).tolist())
        assert u <= {0, 255}, (k, u)
        assert v.a.shape[:2] == SIZES.get(k, (H, W)), (k, v.a.shape)


# 每层「站在哪」：不透明团块要碰到这一行（往上 floor_tol 像素以内），或者（只限 front）从上沿挂下来
GROUND_LINE = {"ridge": HORIZON, "shore": HORIZON + 3, "water": 177, "front": H - 1}
HANG_MAX = 80     # 前景从上沿挂下来的东西最低到这一行


def check_floating(solids, verbose=True):
    """自检（倒影、水纹、雾、亮纹不算：它们本来就是一片片的）：每层不透明像素 8 连通（左右绕回），
    找出既不落到这层地面、也不碰上沿的团块。"""
    bad = {}
    xs = np.arange(W)
    for k, lay in solids.items():
        lab, n = components(lay.a[..., 3] > 0, wrap=True)
        gl = np.round(ground_y(xs)).astype(int) if k == "main" else np.full(W, GROUND_LINE[k])
        floor = gl - 2
        out = []
        for i in range(1, n + 1):
            yy, xx = np.nonzero(lab == i)
            if (yy >= floor[xx]).any() or (yy.min() == 0 and (k == "front" and yy.max() <= HANG_MAX)):
                continue
            out.append((len(yy), int(xx.min()), int(xx.max()), int(yy.min()), int(yy.max())))
        bad[k] = sorted(out, reverse=True)
        if verbose:
            print(f"  {k:7s} 连通区域 {n:4d}，悬空 {len(out)}", out[:6] if out else "")
    return bad


def glint_rgb(a):
    """预览用：亮纹按 R 查 GLINT_PAL（不闪）。"""
    out = np.zeros_like(a)
    m = a[..., 3] > 0
    lv = np.clip(np.floor(a[..., 0] / 255 * 3 + 0.25), 0, 3).astype(int)
    pal = np.array([rgba(lch(*p)) for p in GLINT_PAL], np.uint8)
    out[m] = pal[lv[m]]
    return out


def preview(layers, cam_x, path, stand_in=False):
    """按 Godot 里的视差比例合成一张 480×270（镜头左边缘在 cam_x），放大 3 倍。
    stand_in：在晨的位置（屏幕 x≈204）放一个 10×37 的浅色块当主角替身。"""
    out = np.zeros((H, SW, 4), np.uint8)
    for k in SCROLL:
        a = layers[k].a
        if k == "glints":
            a = glint_rgb(a)
        y0 = {"glints": GLINT_Y, "ripples": RIPPLE_Y}.get(k, 0)
        if a.shape[1] == SW:
            src = a
        else:
            off = int(round(cam_x * SCROLL[k])) % a.shape[1]
            src = np.roll(a, -off, axis=1)[:, :SW]
        if k == "front" and stand_in:
            gy = int(round(ground_y((204 + cam_x) % W)))
            out[gy - 37:gy + 1, 199:209] = (205, 196, 190, 255)
        m = src[..., 3] > 0
        out[y0:y0 + src.shape[0]][m] = src[m]
    Image.fromarray(out).resize((SW * 3, H * 3), Image.NEAREST).save(path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="把几张合成预览存到这个目录")
    args = ap.parse_args()
    ls, solid = build()
    check_alpha(ls)
    print("悬空自检：")
    floating = check_floating(solid)
    if args.preview:
        d = Path(args.preview)
        d.mkdir(parents=True, exist_ok=True)
        for cx in (0, 240, 520):
            preview(ls, cx, d / f"river_{cx}.png", stand_in=True)
    print("ok", {k: v.a.shape for k, v in ls.items()})
    n_bad = sum(len(v) for v in floating.values())
    if n_bad:
        sys.exit(f"有 {n_bad} 块悬空的东西，见上面的列表")
