"""飞行段：船外一整屏的连续背景（长镜头）+ 避碎石用的碎石小图。以后改这些图只改这个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/sky_art.py [--preview 目录]

约定见 docs/flight_sky_contract.md。输出：
- art/cockpit/sky/*.png   各层图（tile 的横向无缝，宽 960）
- art/cockpit/sky/sky.json  层 + 飞行一的 16 个状态（关键帧）
- art/cockpit/debris_a..e.png  躲碎石时在船外飞过的碎石（13～28 像素，暗色、左上一道亮边）；debris_f / g 跟着飞的小碎屑（< 8 像素）

镜头（机头朝左，景物往右走；往上飞 = 景物往下沉，往下降 = 景物往上升）：
  起飞：就是森林关卡那片林子（forest_*：tools/forest_art.py 同一套函数、同一组 seed 画的，往上加高露出树梢）——
        镜头往上升，近处的主层先沉下去，中景、远景跟着慢慢沉，最后成了脚下地平线上的一条；
  穿云：一整块云层（cloud_deck）从屏幕上面压下来、整个扫过船、最后变成脚下的云海；
  碎石墙：云海上方远处一条碎石带淡入；加速：近处云丝、速度线变快；
  到站：云沉下去，星星淡入，远处的河流星球从小（planet_s，加速段就露头）换成中（planet_m）；
  降落：地面和远城从下面升上来，鸽子笼高楼（city_mid）、钟楼一起往上升，停着船的水道升到船下；
  落水：对岸一面灰楼墙，水面在船腰，箱子漂在机头前。

全部硬边、不透明像素；配色是森林的暗青绿 / 灰绿，没有蓝；亮度都压在驾驶舱（舱壁 OKLab L≈0.21～0.36）以下
（例外：起飞开头船底下那条雾带是森林关卡原样的亮度，认得出是同一片林子更要紧）。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

AIO = Path("/Users/jiamulin/Desktop/程序programs/AI Oscar")
sys.path.insert(0, str(AIO))
from oscarkit.palette import from_lch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "cockpit" / "sky"
DEBRIS_OUT = ROOT / "art" / "cockpit"
TW = 960                                   # tile 宽
SW, SH = 480, 270                          # 屏幕


def col(L, C, h):
    return from_lch(L, C, h)


def hexc(c):
    return "#%02x%02x%02x" % tuple(c[:3])


# ============================================================ 画布：tile 的图形在左右边界自动折回去（无缝）
class Layer:
    PAD = 200

    def __init__(self, w, h, tile=True):
        self.w, self.h, self.tile = w, h, tile
        self.a = np.zeros((h, w, 4), np.uint8)

    # ---- 形状 → 布尔 mask
    def _fold(self, big):
        P, W = self.PAD, self.w
        m = big[:, P:P + W].copy()
        if self.tile:
            m[:, W - P:] |= big[:, :P]
            m[:, :P] |= big[:, P + W:]
        return m

    def _draw(self, fn):
        im = Image.new("1", (self.w + 2 * self.PAD, self.h), 0)
        fn(ImageDraw.Draw(im), self.PAD)
        return self._fold(np.array(im, bool))

    def poly(self, pts):
        return self._draw(lambda d, P: d.polygon([(x + P, y) for x, y in pts], fill=1, outline=1))

    def ellipse(self, cx, cy, rx, ry):
        return self._draw(lambda d, P: d.ellipse([cx - rx + P, cy - ry, cx + rx + P, cy + ry], fill=1))

    def rect(self, x0, y0, x1, y1):
        return self._draw(lambda d, P: d.rectangle([x0 + P, y0, x1 + P, y1], fill=1))

    def line(self, pts):
        return self._draw(lambda d, P: d.line([(x + P, y) for x, y in pts], fill=1, width=1))

    # ---- 上色
    def paint(self, m, c):
        self.a[m, :3] = c[:3]
        self.a[m, 3] = 255

    @property
    def mask(self):
        return self.a[..., 3] > 0

    def save(self, name, out=OUT):
        out.mkdir(parents=True, exist_ok=True)
        Image.fromarray(self.a, "RGBA").save(out / f"{name}.png")


def up(m):
    """该像素上面那格（越界算空）。"""
    o = np.zeros_like(m)
    o[1:] = m[:-1]
    return o


def down(m):
    o = np.zeros_like(m)
    o[:-1] = m[1:]
    return o


def left(m, wrap=True):
    return np.roll(m, 1, axis=1) if wrap else np.pad(m, ((0, 0), (1, 0)))[:, :-1]


def right(m, wrap=True):
    return np.roll(m, -1, axis=1) if wrap else np.pad(m, ((0, 0), (0, 1)))[:, 1:]


def pnoise(w, seed, kmin=1, kmax=8, falloff=1.0):
    """周期为 w 的一维噪声（整数频率的正弦叠加），[-1, 1]。"""
    rng = np.random.default_rng(seed)
    x = np.arange(w)
    out = np.zeros(w)
    tot = 0
    for k in range(kmin, kmax + 1):
        a = 1.0 / k ** falloff
        out += a * np.sin(2 * math.pi * k * x / w + rng.uniform(0, 2 * math.pi))
        tot += a
    return out / tot * 1.6


def spaced(rng, w, gmin, gmax, start=0):
    xs, x = [], start + int(rng.integers(0, gmax))
    while x < w + start:
        xs.append(x)
        x += int(rng.integers(gmin, gmax + 1))
    return xs


# ============================================================ 森林（起飞）：就是森林关卡那片林子（tools/forest_art.py 画的）
# 玩家刚从森林关卡飞出来，窗外必须是同一片林子：同样的树、同样的颜色、同样的雾。所以不另画，直接调 forest_art 的
# 同一套函数、同一组 seed 再画一遍各层（sky / ridge / far / midfar / mid / main；front 是挡在晨前面的近黑前景，这里不用）。
# forest_art 的每层只有 270 高，树冠伸出画面上沿；这里把画布往上加高 F_TOP 像素：forest_art 直接写 lay.a 的地方照旧落在
# 下面 270 行，只有 paste（贴树）能贴到上面去 → 下面 270 行和 art/forest/*.png 逐像素一样（build 里断言），
# 上面多出来的就是那些树冠的上半截和树尖。起飞时镜头往上升，森林往下沉，露出来的正是这片树的树梢。
# 树冠上半截照 forest_art 的规矩往「同一高度的背景色」里褪（aerial）：林冠以上的背景不再是黑的林冠，而是往上延伸的天
# （F_SKY：林冠的黑 → 地平线一带最亮 → 往上暗回去），越往树尖褪得越少一点，远层的树尖淡、近层的黑，一层层分得开。
sys.path.insert(0, str(ROOT / "tools"))
import forest_art as FA  # noqa: E402

F_TOP = 150            # 树层图的第 0 行 = 森林关卡里的 y = -150（最高的树尖在 -142）
F_BG_TOP = 420         # 背景层（雾带 + 天）往上延伸得更高：第 0 行 = 关卡里的 y = -420
F_BG_FADE = 48         # 背景层最上面这几行用 Bayer 抖动一点点变透明：穿云时它整张沉下去，上沿不是一刀硬边
F_BG_FOOT = 60         # sky.png 底下再接这么多行它最后一行的颜色：画面外那圈边（SKY_M）也盖住
F_LAYERS = (("forest_ridge", "ridge", FA.ridge), ("forest_far", "far", FA.build_far),
            ("forest_midfar", "midfar", FA.build_midfar), ("forest_mid", "mid", FA.build_mid),
            ("forest_main", "main", FA.main_layer))
# 林冠以上的天（关卡里的 y, 颜色），接在 sky.png 第 0 行（#050c0a，林冠的黑）上面；两档之间用 forest_art 一样的 Bayer 抖动过渡。
# 地平线一带 L≈.30（和原来起飞段的天一样，仍比舱壁大部分暗），往上暗回 .19（= 起飞几段的底色 F_BG，接缝看不出来）
F_SKY = [(-420, col(.19, .018, 165)), (-330, col(.215, .019, 163)), (-250, col(.25, .02, 161)),
         (-190, col(.285, .02, 160)), (-150, col(.30, .02, 160)), (-120, col(.28, .02, 161)),
         (-90, col(.245, .019, 163)), (-60, col(.21, .018, 165)), (-30, col(.175, .017, 166)),
         (0, FA.from_hex(FA.BANDS[0][1]))]
F_BG = hexc(F_SKY[0][1])
F_TIP_CLEAR = 0.7      # 树尖比林冠底少褪多少（0 = 和关卡里 y=0 那一行一样褪）：远层在天前面也要是读得出的树梢剪影，不是一片鬼影
F_TIP_SPAN = 100       # 从关卡 y=0 往上这么多行里褪的程度慢慢减到树尖那一档


class _FBands:
    """临时把 forest_art 的背景色档（BANDS）换成 F_SKY（行号 = 关卡 y + shift），出来时换回去。"""

    def __init__(self, shift):
        self.shift = shift

    def __enter__(self):
        self.saved = FA.BANDS, FA.BAND_Y, FA.BAND_C
        FA.BANDS = [(y + self.shift, hexc(c)) for y, c in F_SKY]
        FA.BAND_Y = np.array([b[0] for b in FA.BANDS])
        FA.BAND_C = [tuple(c[:3]) for _, c in F_SKY]
        FA._POOLC.clear()

    def __exit__(self, *exc):
        FA.BANDS, FA.BAND_Y, FA.BAND_C = self.saved
        FA._POOLC.clear()


def forest_tall(fn):
    """用 forest_art 的 fn 画一层，画布往上加高 F_TOP → (F_TOP + 270, 960) RGBA，下面 270 行 = art/forest 那张。"""
    calls = []

    class Tall(FA.Layer):
        def __init__(self, w=FA.W, h=FA.H):
            self.big = np.zeros((h + F_TOP, w, 4), np.uint8)
            self.a = self.big[F_TOP:]

        def paste(self, img, x, y, wrap=True):
            h, w = img.shape[:2]
            H_, W_ = self.big.shape[:2]
            y += F_TOP
            for px in ([x - W_, x, x + W_] if wrap else [x]):
                x0, y0, x1, y1 = max(0, px), max(0, y), min(W_, px + w), min(H_, y + h)
                if x0 >= x1 or y0 >= y1:
                    continue
                src = img[y0 - y:y1 - y, x0 - px:x1 - px]
                m = src[..., 3] > 0
                self.big[y0:y1, x0:x1][m] = src[m]

    def aerial(layer, t_of_y, steps=8, pool=None):
        calls.append((t_of_y, steps))
        orig_aerial(layer, t_of_y, steps, pool)

    orig_layer, orig_aerial = FA.Layer, FA.aerial
    FA.Layer, FA.aerial = Tall, aerial
    try:
        lay = fn()
    finally:
        FA.Layer, FA.aerial = orig_layer, orig_aerial
    t_of_y, steps = calls[-1]
    t0 = t_of_y(0)
    top = type("Top", (), {})()
    top.a = lay.big[:F_TOP]
    with _FBands(F_TOP):
        orig_aerial(top, lambda r: t0 * (1 - F_TIP_CLEAR * min(1.0, (F_TOP - r) / F_TIP_SPAN)), steps)
    return lay.big


def forest_bg():
    """背景：上面 F_BG_TOP 行是林冠以上的天（F_SKY），下面接 art/forest/sky.png 原图（林冠的黑、雾带、光斑）。
    sky.png 宽 480、左右能接（光斑都在中间，Bayer 周期 4），横着铺两遍成 960 的 tile。"""
    sky = np.array(Image.open(FA.OUT / "sky.png").convert("RGBA"))
    a = np.zeros((F_BG_TOP + FA.H + F_BG_FOOT, TW, 4), np.uint8)
    xs = np.arange(TW)
    with _FBands(F_BG_TOP):
        for r in range(F_BG_TOP):
            i, f = FA.band_frac(r)
            idx = i + (FA.BAYER[r % 4, xs % 4] < f)
            a[r, :, :3] = np.array(FA.BAND_C)[np.minimum(idx, len(FA.BAND_C) - 1)]
    a[:F_BG_TOP, :, 3] = 255
    for r in range(F_BG_FADE):
        a[r, FA.BAYER[r % 4, xs % 4] >= (r + 1) / (F_BG_FADE + 1), 3] = 0
    a[F_BG_TOP:F_BG_TOP + FA.H] = np.concatenate([sky, sky], axis=1)
    a[F_BG_TOP + FA.H:] = a[F_BG_TOP + FA.H - 1]
    return a


def forest_layers():
    out = {"forest_bg": forest_bg()}
    for k, name, fn in F_LAYERS:
        a = forest_tall(fn)
        orig = np.array(Image.open(FA.OUT / f"{name}.png").convert("RGBA"))
        assert (a[F_TOP:] == orig).all(), f"{k} 下面 270 行和 art/forest/{name}.png 不一样（forest_art.py 改过、没重跑？）"
        out[k] = a
    return out


# ============================================================ 云（穿云、云海、碎石带、加速）
C_HUE = 165


def bumps(L: Layer, rng, y0, rmin, rmax, gmin, gmax, ry_k=0.75, sign=-1, ynoise=None):
    """一排鼓包（椭圆的并），sign=-1 往上鼓（云顶），+1 往下垂（云底）。"""
    m = np.zeros((L.h, L.w), bool)
    for x in spaced(rng, TW, gmin, gmax):
        r = int(rng.integers(rmin, rmax + 1))
        yy = y0 + (ynoise[x % TW] if ynoise is not None else 0)
        m |= L.ellipse(x, yy + sign * r * 0.25, r, r * ry_k)
    return m


def contour_bands(m, top_line, steps):
    """按离云顶多深分档：steps = [(深度上限, 颜色), ...]，返回 [(mask, 颜色)]。"""
    H = m.shape[0]
    depth = np.arange(H)[:, None] - top_line[None, :]
    out = []
    lo = -10 ** 9
    for hi, c in steps:
        out.append((m & (depth >= lo) & (depth < hi), c))
        lo = hi
    return out


def first_row(m):
    """每列最上面那个实心像素的行号（空列给 H）。"""
    H = m.shape[0]
    has = m.any(0)
    return np.where(has, m.argmax(0), H)


def cloud_deck():
    """整块云层：上面是鼓鼓的受光云顶，下面是垂下来的暗云底。穿云时它从屏幕上面整个扫下来，最后变成云海。"""
    L = Layer(TW, 300)
    rng = np.random.default_rng(201)
    top_n = 6 * pnoise(TW, 11, 1, 6)
    bot_n = 6 * pnoise(TW, 12, 1, 6)
    m = np.zeros((L.h, L.w), bool)
    m[34:270] = True
    m |= bumps(L, rng, 34, 10, 30, 14, 30, 0.7, -1, top_n)
    m |= bumps(L, rng, 262, 8, 22, 12, 26, 0.6, +1, bot_n)
    # 云底的边可以超过画布，裁掉
    top = first_row(m)
    for mm, c in contour_bands(m, top, [(2, col(.265, .016, 150)), (9, col(.235, .018, 158)),
                                        (26, col(.215, .018, C_HUE)), (70, col(.20, .018, C_HUE)),
                                        (10 ** 6, col(.19, .017, C_HUE + 4))]):
        L.paint(mm, c)
    # 云顶里一团团的分界（鼓包的右下沿暗一档）
    for x in spaced(rng, TW, 22, 46):
        r = int(rng.integers(10, 22))
        yy = 34 + top_n[x % TW] + int(rng.integers(6, 20))
        e = L.ellipse(x, yy, r, r * 0.6)
        edge = e & ~up(e) & m & ~right(e)
        edge = e & ~down(e)
        L.paint(edge & m & (np.arange(L.h)[:, None] > top[None, :] + 3), col(.205, .018, C_HUE))
    # 云底：下沿往上 6 像素暗一档、最下沿再暗
    bot_line = L.h - 1 - first_row(m[::-1])
    depth_b = bot_line[None, :] - np.arange(L.h)[:, None]
    L.paint(m & (depth_b < 7) & (depth_b >= 0), col(.175, .016, C_HUE + 6))
    L.paint(m & (depth_b < 2) & (depth_b >= 0), col(.165, .015, C_HUE + 8))
    return L


def cloud_far():
    """远处的云海（地平线上那一层），小鼓包、对比很低。"""
    L = Layer(TW, 110)
    rng = np.random.default_rng(202)
    n = 3 * pnoise(TW, 21, 1, 7)
    m = np.zeros((L.h, L.w), bool)
    m[12:] = True
    m |= bumps(L, rng, 12, 3, 10, 5, 13, 0.6, -1, n)
    top = first_row(m)
    for mm, c in contour_bands(m, top, [(1, col(.245, .016, 152)), (6, col(.225, .017, 160)),
                                        (30, col(.21, .017, C_HUE)), (10 ** 6, col(.20, .017, C_HUE + 4))]):
        L.paint(mm, c)
    # 远处一两道云缝
    for y, amp in ((24, 2), (44, 3), (70, 3)):
        nn = pnoise(TW, 22 + y, 2, 9)
        for x in range(TW):
            if nn[x] > 0.35:
                L.a[int(y + amp * nn[x]), x, :3] = col(.195, .017, C_HUE + 4)
    return L


def cloud_high():
    """高空的薄云条（扁长、稀），在天上很慢地走。"""
    L = Layer(TW, 100)
    rng = np.random.default_rng(203)
    for _ in range(16):
        x = int(rng.integers(0, TW))
        y = int(rng.integers(8, 92))
        rx = int(rng.integers(30, 110))
        ry = int(rng.integers(2, 5))
        e = L.ellipse(x, y, rx, ry)
        e |= L.ellipse(x + rx * 0.35, y - ry * 0.6, rx * 0.45, ry)
        L.paint(e, col(.225, .016, C_HUE))            # 比起飞段的天（.20～.31）亮一点，爬升时看得出云在往下压
        L.paint(e & ~up(e), col(.255, .016, 158))
    return L


def wisps():
    """近处掠过的云丝：扁长的小团，飞得快，给速度感。多放在船的上下两条（船挡着中间）。"""
    L = Layer(TW, 270)
    rng = np.random.default_rng(204)
    bands = [(4, 56)] * 6 + [(208, 266)] * 6 + [(60, 205)] * 3
    for i, (y0, y1) in enumerate(bands):
        x = int(i * TW / len(bands) + rng.integers(-30, 30))
        y = int(rng.integers(y0, y1))
        rx = int(rng.integers(26, 72))
        ry = int(rng.integers(3, 7))
        e = L.ellipse(x, y, rx, ry)
        for k in range(int(rng.integers(1, 3))):
            e |= L.ellipse(x + int(rng.integers(-rx // 2, rx // 2)), y - ry + int(rng.integers(0, 3)),
                           int(rx * rng.uniform(0.25, 0.5)), ry)
        e |= L.ellipse(x + rx * 0.9, y + 1, rx * 0.5, max(1, ry // 3))      # 往后拖的尾巴
        L.paint(e, col(.215, .016, C_HUE))
        L.paint(e & ~up(e), col(.25, .016, 155))
        L.paint(e & ~down(e), col(.195, .016, C_HUE + 4))
    return L


def streaks():
    """加速时的速度线：1 像素的虚线，很稀。"""
    L = Layer(TW, 270)
    rng = np.random.default_rng(205)
    for i in range(34):
        y = int(rng.integers(2, 268))
        x0 = int(rng.integers(0, TW))
        ln = int(rng.integers(14, 46))
        c = col(.25 if i % 3 else .28, .014, 160)
        for x in range(x0, x0 + ln):
            if (x - x0) % 7 < 5:
                L.a[y, x % TW, :3] = c
                L.a[y, x % TW, 3] = 255
    return L


# ============================================================ 碎石
R_HUE = 55


def rock_mask(rng, w, h):
    """一块不规则的石头：多边形，半径带抖动，偶尔一个缺口。"""
    n = int(rng.integers(7, 11))
    cx, cy = (w - 1) / 2, (h - 1) / 2
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n + rng.uniform(-0.25, 0.25)
        k = rng.uniform(0.72, 1.0)
        pts.append((cx + math.cos(a) * (w / 2) * k, cy + math.sin(a) * (h / 2) * k))
    im = Image.new("1", (w, h), 0)
    ImageDraw.Draw(im).polygon(pts, fill=1, outline=1)
    m = np.array(im, bool)
    if w >= 12 and rng.random() < 0.6:                       # 一个崩掉的角
        a = rng.uniform(0, 2 * math.pi)
        r = min(w, h) * 0.28
        yy, xx = np.mgrid[0:h, 0:w]
        m &= np.hypot(xx - (cx + math.cos(a) * w / 2), yy - (cy + math.sin(a) * h / 2)) > r
    return m


def shade_rock(m, tones, rim, seed=0, facets=True):
    """光从左上：按位置投到光的方向分 3 档（切面），左上外沿一道亮边。返回 RGBA。"""
    h, w = m.shape
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = (w - 1) / 2, (h - 1) / 2
    d = ((cx - xx) * 0.7 + (cy - yy) * 0.7) / max(w, h) * 2           # 越朝左上越大
    if facets:                                                         # 两条斜的切面线，让它像有棱的石头
        d = d + 0.35 * np.sign((xx - cx) * rng.uniform(-1, 1) + (yy - cy) * rng.uniform(-1, 1))
    a = np.zeros((h, w, 4), np.uint8)
    q = np.digitize(d, [-0.25, 0.35])                                  # 0 暗 / 1 中 / 2 亮
    for i, c in enumerate(tones):
        a[m & (q == i), :3] = c[:3]
    a[m, 3] = 255
    edge = m & (~np.pad(m, ((1, 0), (0, 0)))[:-1] | ~np.pad(m, ((0, 0), (1, 0)))[:, :-1])
    lit = edge & (d > -0.1)
    a[lit, :3] = rim[:3]
    return a


def debris_sprites():
    """5 块碎石：躲碎石时从左往右飞过船，12～28 像素。暗色身子 + 左上一道亮边，在云上看得清。"""
    # 10-29 验收：原来 10～26 像素、亮边 L .42，在暗云上只看得见一个小点 → 加大到 16～28、亮边提到 .52（仍比晨暗得多）
    tones = [col(.13, .010, R_HUE + 10), col(.18, .012, R_HUE), col(.23, .014, R_HUE - 5)]
    rim = col(.52, .018, 85)
    out = {}
    for name, (w, h), seed in (("debris_a", (25, 19), 501), ("debris_b", (28, 22), 502), ("debris_c", (22, 17), 503),
                               ("debris_d", (19, 15), 504), ("debris_e", (16, 13), 505)):
        rng = np.random.default_rng(seed)
        m = rock_mask(rng, w, h)
        a = shade_rock(m, tones, rim, seed)
        # 一两道裂纹（暗）
        if w >= 18:
            c = Image.fromarray(a)
            d = ImageDraw.Draw(c)
            x0 = int(w * rng.uniform(0.3, 0.5))
            d.line([(x0, int(h * 0.3)), (x0 + 3, int(h * 0.55)), (x0 + 2, int(h * 0.8))], fill=tuple(tones[0]) + (255,))
            a2 = np.array(c)
            a2[~m] = 0
            a = a2
        ys, xs = np.nonzero(a[..., 3])
        out[name] = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    # 跟着大块飞的小碎屑（< 8 像素，cockpit_debris.gd 当碎屑、不算碰撞；没有它们时引擎画的占位点是粉的，不对）
    for name, (w, h), seed in (("debris_f", (5, 4), 506), ("debris_g", (4, 3), 507)):
        rng = np.random.default_rng(seed)
        m = rock_mask(rng, w, h)
        m[h // 2, w // 2] = True
        out[name] = shade_rock(m, tones, rim, seed, facets=False)
    return out


def debris_belt():
    """远处的碎石墙：一条横穿天空的密带，中间最密。"""
    L = Layer(TW, 110)
    rng = np.random.default_rng(301)
    tones = [col(.13, .010, R_HUE + 10), col(.15, .011, R_HUE), col(.17, .012, R_HUE)]
    rim = col(.25, .014, 80)
    cen = 55 + 10 * pnoise(TW, 31, 1, 4)
    for i in range(900):
        x = int(rng.integers(0, TW))
        y = int(cen[x] + rng.normal(0, 16))
        s = int(rng.integers(2, 6)) if rng.random() < 0.85 else int(rng.integers(6, 10))
        m = rock_mask(rng, s, max(2, int(s * rng.uniform(0.6, 1.0))))
        a = shade_rock(m, tones, rim, i, facets=False)
        h, w = m.shape
        for yy in range(h):
            for xx in range(w):
                if a[yy, xx, 3] and 0 <= y + yy < L.h:
                    L.a[y + yy, (x + xx) % TW] = a[yy, xx]
    # 带子里的尘：一层更暗的薄带（稀疏横点）
    for x in range(TW):
        for k in range(-6, 7, 3):
            y = int(cen[x] + k)
            if (x * 7 + k * 13) % 5 == 0 and not L.a[y, x, 3]:
                L.a[y, x, :3] = col(.165, .012, 120)
                L.a[y, x, 3] = 255
    return L


def debris_near():
    """碎石墙前面零星漂过的几块中号碎石。"""
    L = Layer(TW, 270)
    rng = np.random.default_rng(302)
    tones = [col(.13, .010, R_HUE + 10), col(.16, .012, R_HUE), col(.19, .013, R_HUE)]
    rim = col(.32, .015, 80)
    for i in range(12):
        x = int(i * TW / 12 + rng.integers(0, 40))
        y = int(rng.choice([rng.integers(6, 80), rng.integers(212, 262)]))
        s = int(rng.integers(6, 13))
        m = rock_mask(rng, s, max(4, int(s * rng.uniform(0.6, 0.9))))
        a = shade_rock(m, tones, rim, 700 + i)
        h, w = m.shape
        for yy in range(h):
            for xx in range(w):
                if a[yy, xx, 3]:
                    L.a[y + yy, (x + xx) % TW] = a[yy, xx]
    return L


# ============================================================ 星空和河流星球
P_HUE = 178


def stars():
    L = Layer(TW, 200)
    rng = np.random.default_rng(401)
    for i in range(80):
        x, y = int(rng.integers(0, TW)), int(rng.integers(0, 200))
        c = col(float(rng.choice([.27, .30, .34])), .012, 150)
        L.a[y, x, :3] = c
        L.a[y, x, 3] = 255
    for i in range(7):
        x, y = int(rng.integers(2, TW - 2)), int(rng.integers(2, 198))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            L.a[y + dy, x + dx, :3] = col(.26, .012, 150)
            L.a[y + dy, x + dx, 3] = 255
        L.a[y, x, :3] = col(.40, .014, 140)
    return L


def planet(d, seed, rivers=True):
    """河流星球：青绿的海（不是蓝）、暗绿的陆，亮的河弯弯曲曲；光从左上，右下一弯暗；左上一圈大气亮边。"""
    pad = 2
    n = d + 2 * pad
    a = np.zeros((n, n, 4), np.uint8)
    yy, xx = np.mgrid[0:n, 0:n]
    c = (n - 1) / 2
    r = d / 2
    dist = np.hypot(xx - c, yy - c)
    disc = dist <= r - 0.3
    rng = np.random.default_rng(seed)
    # 陆地：几团圆的并
    land = np.zeros_like(disc)
    for _ in range(max(3, d // 7)):
        lx, ly = rng.uniform(c - r * 0.8, c + r * 0.8), rng.uniform(c - r * 0.7, c + r * 0.7)
        lr = rng.uniform(r * 0.18, r * 0.42)
        land |= (np.hypot((xx - lx) * 0.8, yy - ly) < lr)
    land &= disc
    # 光：法线点乘左上
    nx, ny = (xx - c) / r, (yy - c) / r
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))
    lam = -0.55 * nx - 0.5 * ny + 0.67 * nz
    q = np.digitize(lam, [0.05, 0.45, 0.8])                          # 0 夜 / 1 暗 / 2 中 / 3 亮
    sea = [col(.17, .018, P_HUE + 6), col(.21, .026, P_HUE), col(.245, .032, P_HUE - 2), col(.27, .034, P_HUE - 6)]
    gnd = [col(.16, .016, 140), col(.19, .022, 135), col(.215, .026, 130), col(.24, .028, 125)]
    for i in range(4):
        a[disc & ~land & (q == i), :3] = sea[i]
        a[disc & land & (q == i), :3] = gnd[i]
    if rivers and d >= 30:
        img = Image.fromarray(a)
        dr = ImageDraw.Draw(img)
        for k in range(2):
            pts = []
            x0 = c - r * 0.6 + k * r * 0.5
            for t in range(0, int(r * 1.3), 3):
                pts.append((x0 + t * 0.7 + 2.5 * math.sin(t / 3 + k), c - r * 0.6 + t * 0.85 + 2 * math.cos(t / 4 + k)))
            dr.line(pts, fill=tuple(col(.31, .034, 172)) + (255,), width=1)
        b = np.array(img)
        rv = (b[..., :3] != a[..., :3]).any(-1) & land & (q >= 1)
        a[rv, :3] = col(.31, .034, 172)
        a[rv & (q <= 1), :3] = col(.25, .030, 175)
    a[disc, 3] = 255
    # 大气：亮的一侧外沿一圈
    ring = (dist > r - 0.3) & (dist <= r + 0.9)
    lit_side = (-(xx - c) - (yy - c)) > -r * 0.3
    a[ring & lit_side, :3] = col(.30, .030, 168)
    a[ring & lit_side, 3] = 255
    inner = disc & (dist > r - 1.4) & lit_side & (lam > 0.3)
    a[inner, :3] = col(.33, .032, 165)
    ys, xs = np.nonzero(a[..., 3])
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


# ============================================================ 河流城市（灰绿的清晨；灰色鸽子笼高楼，冷漠）
G_HUE = 155


def ground():
    """远处平原到地平线：灰绿的地，河道一条条横着（越近越宽、越弯），地平线上一道薄雾。"""
    L = Layer(TW, 140)
    L.a[..., 3] = 255
    for y in range(L.h):
        Lv = .215 - 0.035 * min(1, y / 120)
        L.a[y, :, :3] = col(Lv - (Lv * 1000 % 7) * 0, .012, G_HUE)
    L.a[0:2, :, :3] = col(.245, .012, 150)
    L.a[2:4, :, :3] = col(.23, .012, 152)
    # 分档（硬边）
    for y0, Lv in ((4, .215), (22, .205), (50, .195), (90, .185)):
        L.a[y0:, :, :3] = col(Lv, .013, G_HUE)
    WATER, WLIT = col(.25, .022, P_HUE), col(.275, .022, 172)
    rng = np.random.default_rng(601)
    for i, (y, th, amp) in enumerate(((7, 1, 1), (12, 1, 1.5), (19, 1, 2), (29, 2, 3), (43, 2, 4), (63, 3, 6),
                                      (90, 4, 8), (124, 5, 10))):
        n = pnoise(TW, 610 + i, 1, 5)
        for x in range(TW):
            yy = int(y + amp * n[x])
            L.a[yy:yy + th, x, :3] = WATER
            if th > 1 and (x + i * 5) % 9 < 3:
                L.a[yy, x, :3] = WLIT
    # 地上散着的小镇（灰点、短横）
    for _ in range(140):
        x, y = int(rng.integers(0, TW)), int(rng.integers(5, 135))
        w = 1 + y // 30 + int(rng.integers(0, 3))
        if (L.a[y, x, :3] == WATER).all():
            continue
        L.a[y, x:x + w, :3] = col(.235, .006, 120)
    return L


def towers_row(L: Layer, rng, y_top_range, w_range, gap_range, tone_fn, cell, lit_c, shade_c, roof_c, gap_c,
               balcony=0.0, base=None):
    """一排紧挨着的方楼，立面是一格一格的小窗（鸽子笼）。cell=(cw, ch, ww, wh)。返回 (楼 mask, 楼列表)。"""
    x = int(rng.integers(0, 10))
    allm = np.zeros((L.h, L.w), bool)
    blds = []
    while x < TW:
        w = int(rng.integers(*w_range))
        top = int(rng.integers(*y_top_range))
        body, win = tone_fn(rng)
        m = L.rect(x, top, x + w - 1, L.h - 1)
        L.paint(m, body)
        cw, ch, ww, wh = cell
        bal = rng.random() < balcony
        for yy in range(top + 3, L.h, ch):
            for xx in range(x + 2, x + w - ww - 1, cw):
                L.paint(L.rect(xx, yy, xx + ww - 1, yy + wh - 1), win)
            if bal:
                L.paint(L.rect(x + 1, yy + wh, x + w - 2, yy + wh), lit_c)
        L.paint(L.rect(x, top, x, L.h - 1), lit_c)                    # 朝左（天光）那条边亮
        L.paint(L.rect(x + w - 1, top, x + w - 1, L.h - 1), shade_c)
        L.paint(L.rect(x, top, x + w - 1, top), roof_c)
        if rng.random() < 0.5:                                         # 楼顶的水箱 / 天线
            tx = x + int(rng.integers(2, max(3, w - 6)))
            if rng.random() < 0.5:
                L.paint(L.rect(tx, top - 4, tx + 3, top - 1), body)
                L.paint(L.rect(tx, top - 4, tx + 3, top - 4), roof_c)
            else:
                L.paint(L.rect(tx, top - int(rng.integers(4, 10)), tx, top - 1), shade_c)
        allm |= m
        blds.append((x, top, w))
        g = int(rng.integers(*gap_range))
        if g > 0:
            L.paint(L.rect(x + w, top + 6, x + w + g - 1, L.h - 1), gap_c)
        x += w + g
    return allm, blds


def city_far():
    """远处的城：地平线上一排挤得密密的小楼。"""
    L = Layer(TW, 56)
    rng = np.random.default_rng(701)
    tones = [col(.205, .006, G_HUE), col(.215, .005, 140), col(.198, .006, 165)]

    def tone(r):
        b = tones[int(r.integers(0, 3))]
        return b, col(.185, .006, G_HUE)
    towers_row(L, rng, (8, 44), (3, 9), (0, 2), tone, (2, 3, 1, 1), col(.235, .006, 140), col(.19, .006, 165),
               col(.23, .006, 140), col(.18, .006, 165))
    return L


def city_mid():
    """鸽子笼高楼：灰色方楼一栋挨一栋，一格一格的小窗，几乎没有灯。"""
    L = Layer(TW, 240)
    rng = np.random.default_rng(702)
    tones = [(col(.20, .006, G_HUE), col(.155, .007, 170)), (col(.215, .005, 120), col(.165, .006, 160)),
             (col(.19, .007, 165), col(.15, .007, 175)), (col(.205, .004, 90), col(.16, .006, 160))]

    def tone(r):
        return tones[int(r.integers(0, len(tones)))]
    m, blds = towers_row(L, rng, (0, 110), (22, 46), (1, 4), tone, (4, 4, 2, 2), col(.235, .006, 140),
                         col(.17, .006, 165), col(.24, .006, 130), col(.13, .008, 170), balcony=0.35)
    # 极少几格亮着的窗（冷的灰绿，不暖）
    for _ in range(14):
        x0, top, w = blds[int(rng.integers(0, len(blds)))]
        xx = x0 + 2 + 4 * int(rng.integers(0, max(1, (w - 4) // 4)))
        yy = top + 3 + 4 * int(rng.integers(0, 30))
        if yy + 1 < L.h:
            L.paint(L.rect(xx, yy, xx + 1, yy + 1), col(.27, .014, 140))
    return L


def clocktower():
    """钟楼：老石头方塔，比鸽子笼楼暖一点点；钟面浅灰，指针停着。"""
    w, h = 30, 200
    L = Layer(w, h, tile=False)
    STONE, LIT, SH_, DARK = col(.215, .012, 70), col(.25, .012, 75), col(.18, .010, 60), col(.13, .008, 60)
    L.paint(L.rect(7, 44, 22, h - 1), STONE)                       # 塔身
    L.paint(L.rect(7, 44, 7, h - 1), LIT)
    L.paint(L.rect(21, 44, 22, h - 1), SH_)
    for y in range(48, h, 6):                                       # 石缝
        L.paint(L.rect(8, y, 20, y), SH_)
    for y in range(76, h - 20, 26):                                 # 窄窗
        L.paint(L.rect(14, y, 15, y + 6), DARK)
    L.paint(L.rect(5, 26, 24, 44), STONE)                           # 钟室
    L.paint(L.rect(5, 26, 5, 44), LIT)
    L.paint(L.rect(23, 26, 24, 44), SH_)
    L.paint(L.rect(4, 44, 25, 45), LIT)                             # 檐
    L.paint(L.rect(4, 25, 25, 25), LIT)
    face = L.ellipse(14.5, 35, 6.5, 6.5)
    L.paint(face, col(.25, .008, 90))
    L.paint(L.ellipse(14.5, 35, 5.5, 5.5), col(.33, .008, 95))
    for dx, dy in ((0, -4), (4, 0), (0, 4), (-4, 0)):
        L.a[35 + dy, 14 + dx, :3] = col(.22, .008, 80)
    L.paint(L.line([(14, 35), (14, 31)]), col(.17, .008, 70))       # 指针：停在一个时间
    L.paint(L.line([(14, 35), (17, 37)]), col(.17, .008, 70))
    L.paint(L.poly([(14.5, 6), (26, 25), (3, 25)]), col(.17, .010, 60))   # 尖顶
    L.paint(L.poly([(14.5, 6), (3, 25), (8, 25)]), col(.20, .010, 65))
    L.paint(L.rect(14, 0, 14, 6), SH_)
    L.a[0, 13:16, :3] = SH_
    L.a[0, 13:16, 3] = 255
    return L


def canal():
    """河道（当跑道用的那条）：水下还看得见旧跑道的虚线，水面上一排停着的小船。"""
    L = Layer(TW, 64)
    rng = np.random.default_rng(801)
    SURF = 14
    WATER = col(.20, .020, P_HUE)
    L.paint(L.rect(0, SURF, TW - 1, L.h - 1), WATER)
    L.paint(L.rect(0, SURF, TW - 1, SURF), col(.26, .020, 172))
    L.paint(L.rect(0, SURF + 18, TW - 1, L.h - 1), col(.19, .019, P_HUE + 2))
    for x in range(0, TW, 40):                                        # 水下的跑道虚线
        L.paint(L.rect(x, SURF + 9, x + 17, SURF + 10), col(.225, .016, 160))
    for _ in range(60):                                               # 水面亮痕
        x, y = int(rng.integers(0, TW)), int(rng.integers(SURF + 2, L.h - 2))
        L.paint(L.rect(x, y, x + int(rng.integers(2, 6)), y), col(.235, .020, 170))
    HULL, HLIT, CAB, CLIT = col(.19, .018, 55), col(.245, .018, 65), col(.22, .010, 90), col(.26, .010, 95)
    x = 12
    while x < TW - 10:
        bw = int(rng.integers(18, 30))
        hh = int(rng.integers(4, 6))
        y1 = SURF + 1
        hull = L.poly([(x, y1 - hh), (x + bw, y1 - hh), (x + bw - 3, y1 + 1), (x + 3, y1 + 1)])
        L.paint(hull, HULL)
        L.paint(L.rect(x, y1 - hh, x + bw, y1 - hh), HLIT)
        cw = int(rng.integers(6, 11))
        cx = x + int(rng.integers(3, bw - cw - 2))
        L.paint(L.rect(cx, y1 - hh - 4, cx + cw, y1 - hh - 1), CAB)
        L.paint(L.rect(cx, y1 - hh - 4, cx + cw, y1 - hh - 4), CLIT)
        L.paint(L.rect(cx + 2, y1 - hh - 3, cx + 3, y1 - hh - 2), col(.14, .008, 170))
        if rng.random() < 0.5:
            mx = x + bw // 2 + int(rng.integers(-3, 4))
            L.paint(L.rect(mx, y1 - hh - 11, mx, y1 - hh - 1), HULL)
        L.paint(L.rect(x + 3, y1 + 2, x + bw - 3, y1 + 2), col(.16, .016, P_HUE + 4))   # 船底下的影
        x += bw + int(rng.integers(26, 60))
    return L


def water_near():
    """近处的水面（擦水滑行、落水后）：一条亮的水线 + 一道道往后拖的亮痕。"""
    L = Layer(TW, 90)
    rng = np.random.default_rng(802)
    L.paint(L.rect(0, 0, TW - 1, L.h - 1), col(.19, .020, P_HUE))
    L.paint(L.rect(0, 0, TW - 1, 0), col(.27, .020, 170))
    L.paint(L.rect(0, 1, TW - 1, 2), col(.22, .020, 174))
    L.paint(L.rect(0, 30, TW - 1, L.h - 1), col(.175, .019, P_HUE + 2))
    L.paint(L.rect(0, 60, TW - 1, L.h - 1), col(.16, .018, P_HUE + 4))
    for _ in range(90):
        x, y = int(rng.integers(0, TW)), int(rng.integers(4, L.h - 2))
        ln = int(rng.integers(3, 12)) + (8 if y < 30 else 0)
        L.paint(L.rect(x, y, x + ln, y), col(.235 if y < 30 else .21, .020, 170))
    return L


def spray():
    """擦水时往后溅的水花：一串串斜的亮点（很稀），只在 skid 用，飞得很快。"""
    L = Layer(TW, 50)
    rng = np.random.default_rng(803)
    for i in range(22):
        x = int(i * TW / 22 + rng.integers(0, 30))
        y = int(rng.integers(16, 44))
        ln = int(rng.integers(6, 16))
        for k in range(ln):
            c = col(.32, .016, 165) if k < ln - 3 else col(.27, .018, 170)
            px, py = (x + k * 2) % TW, y - k // 2
            if 0 <= py < L.h:
                L.a[py, px, :3] = c
                L.a[py, px, 3] = 255
                if k % 3 == 0 and py + 1 < L.h:
                    L.a[py + 1, px, :3] = col(.25, .018, 170)
                    L.a[py + 1, px, 3] = 255
    return L


def wall_channel():
    """落水后的窄水道：对岸是一面灰楼的墙，一格一格的窗，水线以下长着暗绿的苔。"""
    L = Layer(TW, 236)
    rng = np.random.default_rng(901)
    WALL = col(.19, .006, G_HUE)
    L.paint(L.rect(0, 0, TW - 1, L.h - 1), WALL)
    x = 0
    while x < TW:                                                      # 一栋栋楼（宽 70~130），之间一道暗缝
        bw = int(rng.integers(70, 130))
        tone = [col(.19, .006, G_HUE), col(.20, .005, 120), col(.182, .007, 165)][int(rng.integers(0, 3))]
        L.paint(L.rect(x, 0, x + bw - 1, L.h - 1), tone)
        for yy in range(6, 200, 18):
            for xx in range(x + 5, x + bw - 12, 14):
                L.paint(L.rect(xx, yy, xx + 7, yy + 9), col(.145, .007, 170))
                L.paint(L.rect(xx, yy + 10, xx + 8, yy + 10), col(.22, .006, 130))   # 窗台
                if rng.random() < 0.2:                                   # 拉着帘子
                    L.paint(L.rect(xx + 1, yy + 1, xx + 6, yy + 4), col(.17, .008, 150))
                if rng.random() < 0.25:                                  # 窗下一道水渍
                    L.paint(L.rect(xx + 2, yy + 11, xx + 2, yy + 11 + int(rng.integers(3, 8))), col(.17, .006, 150))
        L.paint(L.rect(x, 0, x, L.h - 1), col(.215, .006, 130))
        L.paint(L.rect(x + bw - 2, 0, x + bw - 1, L.h - 1), col(.15, .007, 170))
        px = x + int(rng.integers(10, bw - 10))                          # 落水管
        L.paint(L.rect(px, 0, px + 1, L.h - 1), col(.165, .008, 160))
        L.paint(L.rect(px, 0, px, L.h - 1), col(.205, .008, 140))
        x += bw
    L.paint(L.rect(0, 200, TW - 1, L.h - 1), col(.155, .016, 140))     # 水线以下的苔
    n = pnoise(TW, 902, 3, 20)
    for x in range(TW):
        L.a[200 - int(2 + 2 * n[x]):200, x, :3] = col(.165, .014, 135)
    return L


def crate():
    """漂着的木箱：画里唯一一点暖色，面积很小；下面几行泡在水里。"""
    w, h = 22, 18
    L = Layer(w, h, tile=False)
    WOOD, LIT, SH_, LINE = col(.29, .030, 62), col(.33, .030, 70), col(.235, .026, 55), col(.215, .024, 52)
    L.paint(L.rect(0, 0, w - 1, h - 1), WOOD)
    L.paint(L.rect(0, 0, w - 1, 0), LIT)
    L.paint(L.rect(0, 0, 0, h - 1), LIT)
    L.paint(L.rect(w - 2, 0, w - 1, h - 1), SH_)
    for y in (5, 10):
        L.paint(L.rect(1, y, w - 3, y), LINE)
    L.paint(L.line([(2, 2), (w - 4, h - 7)]), LINE)
    for x in (3, w - 5):
        L.a[2, x, :3] = col(.20, .010, 60)
    wet = np.zeros((h, w), bool)
    wet[h - 5:] = True
    L.a[wet, :3] = (L.a[wet, :3] * 0.72 + np.array(col(.20, .02, P_HUE)) * 0.28).astype(np.uint8)
    L.a[h - 5, :, :3] = col(.28, .020, 170)                              # 吃水线
    return L


# ============================================================ sky.json
BG = {
    # 10-29 验收：起飞两段的天原来 #07100d→#17251f，近处树冠（L≈.11）和中远林线（.16～.19）贴在上面几乎看不出来，
    # 屏幕下半又被黑边盖住一截 → 天往亮提一点（地平线那头亮），林子当剪影读得出来；仍比舱壁（L≈.22～.36）暗
    # 起飞几段：整屏都被 forest_bg（关卡的雾带 + 往上接的天）盖住，底色只在它上沿露出来 → 用它最上面那档的颜色
    "forest": [F_BG, F_BG],
    "clouds": ["#09120f", "#1a2622"],
    "debris": ["#08100e", "#171f1c"],
    "space": ["#050b09", "#101b17"],
    "city": ["#0d1412", "#212b27"],
    "channel": ["#111917", "#1d2623"],
}

LAYERS = {   # 从后往前（draw order）
    "forest_bg": {"img": "forest_bg.png", "tile": True},
    "stars": {"img": "stars.png", "tile": True},
    "planet_s": {"img": "planet_s.png"},
    "planet_m": {"img": "planet_m.png"},
    "cloud_high": {"img": "cloud_high.png", "tile": True},
    "forest_ridge": {"img": "forest_ridge.png", "tile": True},
    "forest_far": {"img": "forest_far.png", "tile": True},
    "forest_midfar": {"img": "forest_midfar.png", "tile": True},
    "forest_mid": {"img": "forest_mid.png", "tile": True},
    "forest_main": {"img": "forest_main.png", "tile": True},
    "cloud_far": {"img": "cloud_far.png", "tile": True},
    "debris_belt": {"img": "debris_belt.png", "tile": True},
    "cloud_deck": {"img": "cloud_deck.png", "tile": True},
    "ground": {"img": "ground.png", "tile": True},
    "city_far": {"img": "city_far.png", "tile": True},
    "clocktower": {"img": "clocktower.png"},
    "city_mid": {"img": "city_mid.png", "tile": True},
    "canal": {"img": "canal.png", "tile": True},
    "wall_channel": {"img": "wall_channel.png", "tile": True},
    "water_near": {"img": "water_near.png", "tile": True},
    "crate": {"img": "crate.png"},
    "debris_near": {"img": "debris_near.png", "tile": True},
    "wisps": {"img": "wisps.png", "tile": True},
    "spray": {"img": "spray.png", "tile": True},
    "streaks": {"img": "streaks.png", "tile": True},
}


def S(id, y, speed=0, vy=0, alpha=1.0, x=None):
    d = {"id": id, "y": y, "speed": speed, "vy": vy}
    if alpha != 1.0:
        d["alpha"] = alpha
    if x is not None:
        d["x"] = x
    return d


# 起飞：镜头比森林关卡里高 h 像素时，关卡里 y=0 那一行在屏幕上的 y = h × F_SINK（近的沉得快、远的沉得慢）。
# 关卡里镜头竖直不动、各层 y 对齐；这里 h 从 40（刚离地、还在树干之间）升到 560（森林成了脚下地平线上的一条）。
F_SINK = {"forest_bg": .55, "forest_ridge": .6, "forest_far": .7, "forest_midfar": .8, "forest_mid": .9, "forest_main": 1.0}
# 横向：和森林关卡里各层的 scroll_scale 一样（tools/forest_art.py 的 SCROLL），往左飞 v 像素/秒 = 主层往右卷 v
F_SCROLL = {"forest_bg": FA.SCROLL["sky"], "forest_ridge": FA.SCROLL["ridge"], "forest_far": FA.SCROLL["far"],
            "forest_midfar": FA.SCROLL["midfar"], "forest_mid": FA.SCROLL["mid"], "forest_main": FA.SCROLL["main"]}


def forest_at(h, v, climb, drop=()):
    """镜头比关卡高 h、往左飞 v 像素/秒、还在以 climb 像素/秒往上爬时，森林各层的关键帧（drop 里的层不列）。"""
    out = []
    for k in F_SINK:
        if k in drop:
            continue
        top = F_BG_TOP if k == "forest_bg" else F_TOP
        out.append(S(k, round(h * F_SINK[k]) - top, round(v * F_SCROLL[k], 2), round(climb * F_SINK[k], 1)))
    return out


def states():
    st = {}
    # ---------- 起飞：就是森林关卡那片林子（forest_layers），镜头一路往上升，各层往下沉（近的沉得快）
    # forest_canopy：刚离地，还在树干之间：上面是林冠的黑，船底下是关卡里那条雾带，地面刚沉到画面下沿
    st["forest_canopy"] = {"blend": 1.0, "bg": BG["forest"], "layers": forest_at(40, 10, 8)}
    # canopy_fall：穿过林冠，近处大树的枝一层层从窗边掉下去。停在这一段的时间看对白长短（7～20 秒），
    # 爬升 8 像素/秒：停 20 秒也到不了 forest_below 的高度，不会倒回去
    st["canopy_fall"] = {"blend": 1.0, "bg": BG["forest"], "layers": forest_at(190, 14, 8)}
    # forest_below：出了林冠，主层的树尖沉到画面下沿以下，远处几层的树梢在船底下、地平线一带的天最亮；
    # 天上的高云条淡入、跟着往下压（往上爬的感觉）
    st["forest_below"] = {"blend": 1.5, "bg": BG["forest"], "layers": [
        *forest_at(380, 20, 6)[:1], S("cloud_high", -40, 2, 6, 0.5), *forest_at(380, 20, 6)[1:],
        S("cloud_deck", -330, 10, 0)]}
    st["forest_far"] = {"blend": 1.2, "bg": BG["forest"], "layers": [
        *forest_at(470, 24, 6, drop=("forest_main",))[:1], S("cloud_high", -10, 3, 8, 0.75),
        *forest_at(470, 24, 6, drop=("forest_main",))[1:], S("cloud_deck", -300, 10, 4)]}
    # turning：转向巡航，横向一下快起来；森林只剩画面下沿的远处树梢；云层从上面压下来
    st["turning"] = {"blend": 1.0, "bg": BG["forest"], "layers": [
        *forest_at(560, 40, 8, drop=("forest_main",))[:1], S("cloud_high", 20, 8, 6),
        *forest_at(560, 40, 8, drop=("forest_main",))[1:], S("cloud_deck", -240, 18, 10), S("wisps", -150, 40, 0)]}
    # clouds：云层整块扫过船，变成脚下的云海；远处地平线上一层远云，天上几条高云，近处云丝飞过。
    # 森林的天（forest_bg）不列 → 4 档淡出成云里的底色；最远两层树梢沉出画面
    st["clouds"] = {"blend": 1.8, "bg": BG["clouds"], "layers": [
        S("cloud_high", 6, 3, 0), *forest_at(900, 48, 0, drop=("forest_bg", "forest_midfar", "forest_mid", "forest_main")),
        S("cloud_far", 146, 5, 0), S("cloud_deck", 176, 14, 0), S("wisps", 0, 46, 0)]}
    # debris_wall：云海上方远处，一条碎石带横在航线上；前面零星几块中号碎石漂过
    st["debris_wall"] = {"blend": 2.5, "bg": BG["debris"], "layers": [
        S("cloud_high", 0, 2, 0, 0.5), S("cloud_far", 150, 4, 0), S("debris_belt", 28, 5, 0),
        S("cloud_deck", 184, 10, 0), S("debris_near", 0, 20, 0), S("wisps", 0, 30, 0, 0.5)]}
    # clouds_fast：烧完纪念品加速；远处河流星球第一次露头（很小、半透）
    st["clouds_fast"] = {"blend": 1.5, "bg": BG["clouds"], "layers": [
        S("planet_s", 92, 0, 0, 0.5, x=34), S("cloud_high", 6, 12, 0), S("cloud_far", 146, 16, 0),
        S("cloud_deck", 180, 48, 0), S("wisps", 0, 150, 0), S("streaks", 0, 260, 0)]}
    # ---------- 到站：云沉下去，星星淡入，星球从小换成中
    st["river_planet"] = {"blend": 2.0, "bg": BG["space"], "layers": [
        S("stars", 0, 1, 0), S("planet_s", 92, 0, 0, 0.0, x=34), S("planet_m", 64, 0, 0, x=16),
        S("cloud_far", 300, 10, 0), S("cloud_deck", 300, 24, 0), S("wisps", 160, 60, 0, 0.0),
        S("ground", 290, 2, 0), S("city_far", 290, 2, 0)]}
    # river_city：星球淡出，地面和远城从下面升上来（往下降）
    st["river_city"] = {"blend": 2.0, "bg": BG["city"], "layers": [
        S("stars", 0, 1, 0, 0.25), S("planet_m", 40, 0, 0, 0.0, x=16),
        S("ground", 152, 3, -0.6), S("city_far", 112, 4, -0.6), S("clocktower", 240, 0, 0, 0.0, x=88),
        S("city_mid", 290, 8, 0)]}
    # clocktower：鸽子笼高楼升上来，钟楼在机头前面（从窗里也看得到它的上半截）
    st["clocktower"] = {"blend": 1.5, "bg": BG["city"], "layers": [
        S("ground", 142, 4, -1), S("city_far", 100, 5, -1), S("clocktower", 46, 0, -1, x=88),
        S("city_mid", 112, 10, -1)]}
    # boats：再低一点，停着船的水道升到船下
    st["boats"] = {"blend": 1.5, "bg": BG["city"], "layers": [
        S("ground", 132, 5, -1), S("city_far", 86, 6, -1), S("clocktower", 4, 0, -1, x=88),
        S("city_mid", 70, 14, -1), S("canal", 200, 20, -1)]}
    # tilt：一歪，水道猛地近了
    st["tilt"] = {"blend": 0.6, "bg": BG["city"], "layers": [
        S("ground", 124, 6, 0), S("city_far", 76, 8, 0), S("clocktower", -18, 0, 0, x=88),
        S("city_mid", 52, 22, 0), S("canal", 176, 40, 0)]}
    # skid：擦着水面滑：水面到了船腰，船一排排往后掠，水花往后溅
    st["skid"] = {"blend": 0.8, "bg": BG["city"], "layers": [
        S("ground", 120, 8, 0), S("city_far", 70, 10, 0), S("clocktower", -30, 0, 0, x=88),
        S("city_mid", 44, 30, 0), S("canal", 160, 120, 0), S("water_near", 190, 170, 0),
        S("spray", 158, 230, 0)]}
    # ---------- 落水：漂进窄水道，对岸一面灰楼墙
    st["channel"] = {"blend": 1.0, "bg": BG["channel"], "layers": [
        S("city_mid", 44, 6, 0), S("wall_channel", -10, 5, 0), S("water_near", 190, 6, 0)]}
    st["crate"] = {"blend": 1.2, "bg": BG["channel"], "layers": [
        S("wall_channel", -10, 3, 0), S("water_near", 190, 4, 0), S("crate", 177, 0, 0, x=42)]}
    return st


ORDER = ["forest_canopy", "canopy_fall", "forest_below", "forest_far", "turning", "clouds", "debris_wall",
         "clouds_fast", "river_planet", "river_city", "clocktower", "boats", "tilt", "skid", "channel", "crate"]


def build():
    imgs = {
        "cloud_deck": cloud_deck(), "cloud_far": cloud_far(), "cloud_high": cloud_high(), "wisps": wisps(),
        "streaks": streaks(), "debris_belt": debris_belt(), "debris_near": debris_near(), "stars": stars(),
        "ground": ground(), "city_far": city_far(), "city_mid": city_mid(), "clocktower": clocktower(),
        "canal": canal(), "water_near": water_near(), "spray": spray(), "wall_channel": wall_channel(),
        "crate": crate(),
    }
    arrs = {k: v.a for k, v in imgs.items()}
    arrs.update(forest_layers())
    arrs["planet_s"] = planet(20, 451, rivers=False)
    arrs["planet_m"] = planet(56, 452)
    OUT.mkdir(parents=True, exist_ok=True)
    for k, a in arrs.items():
        assert (a[..., 3] == 0).sum() + (a[..., 3] == 255).sum() == a[..., 3].size, k   # 只有全透 / 全不透
        if LAYERS[k].get("tile"):
            assert a.shape[1] >= SW, k
        Image.fromarray(a, "RGBA").save(OUT / f"{k}.png")
    for n, a in debris_sprites().items():
        Image.fromarray(a, "RGBA").save(DEBRIS_OUT / f"{n}.png")
    st = states()
    for s in ORDER:
        assert s in st, s
        for e in st[s]["layers"]:
            assert e["id"] in LAYERS, (s, e["id"])
    doc = {
        "_note": "tools/sky_art.py 生成，别手改。约定见 docs/flight_sky_contract.md。顶层 layers 的顺序就是从后往前的画的顺序；"
                 "每个状态里的层也按这个顺序列。不 tile 的图（planet_s/m、clocktower、crate）用 x 定位，"
                 "x 在用到它的各状态里不变，只改 y / alpha，所以引擎插不插值 x 都一样。",
        "size": [SW, SH],
        "default_blend": 2.0,
        "layers": LAYERS,
        "states": {k: st[k] for k in ORDER},
    }
    (OUT / "sky.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    return arrs, doc


# ============================================================ 预览：按约定的插值规则模拟引擎
def _hex2rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def bg_img(bg):
    a, b = np.array(_hex2rgb(bg[0]), float), np.array(_hex2rgb(bg[1]), float)
    t = np.linspace(0, 1, SH)[:, None]
    rows = (a * (1 - t) + b * t).round().astype(np.uint8)
    return np.repeat(rows[:, None, :], SW, axis=1)


def q4(a):
    return round(a * 4) / 4


def render(arrs, doc, entries, bgcols, back=None, ship_dy=0):
    """entries: {id: (y, xoff, alpha)} → 480×270 RGB。"""
    im = bg_img(bgcols).astype(float)
    for lid, info in doc["layers"].items():
        if lid not in entries:
            continue
        y, xoff, alpha, x = entries[lid]
        alpha = q4(alpha)
        if alpha <= 0:
            continue
        a = arrs[lid]
        h, w = a.shape[:2]
        y = int(round(y))
        if info.get("tile"):
            xo = int(round(xoff)) % w
            strip = np.concatenate([a, a], axis=1)[:, w - xo:w - xo + SW] if xo else a[:, :SW]
            if strip.shape[1] < SW:
                strip = np.concatenate([strip, a], axis=1)[:, :SW]
            src, x0 = strip, 0
        else:
            src, x0 = a, int(round(x or 0))
        sh, sw = src.shape[:2]
        ys0, ys1 = max(0, y), min(SH, y + sh)
        xs0, xs1 = max(0, x0), min(SW, x0 + sw)
        if ys1 <= ys0 or xs1 <= xs0:
            continue
        s = src[ys0 - y:ys1 - y, xs0 - x0:xs1 - x0]
        m = (s[..., 3] > 0)[..., None] * alpha
        im[ys0:ys1, xs0:xs1] = im[ys0:ys1, xs0:xs1] * (1 - m) + s[..., :3] * m
    out = Image.fromarray(im.round().astype(np.uint8), "RGB").convert("RGBA")
    if back is not None:
        out.alpha_composite(back, ((SW - back.width) // 2, (SH - back.height) // 2 + ship_dy))
    return out


def settled(doc, state, t=0.0):
    e = {}
    for L in doc["states"][state]["layers"]:
        e[L["id"]] = (L["y"] + L.get("vy", 0) * t, L.get("speed", 0) * (t + 8), L.get("alpha", 1.0), L.get("x"))
    return e


def lerp_c(c0, c1, p):
    a, b = np.array(_hex2rgb(c0), float), np.array(_hex2rgb(c1), float)
    return "#%02x%02x%02x" % tuple((a * (1 - p) + b * p).round().astype(int))


def transition_frames(doc, s0, s1, n=5, t0=1.0):
    """s0 停了 t0 秒之后切到 s1，按 blend 抽 n 帧（含首尾）。"""
    A = {L["id"]: L for L in doc["states"][s0]["layers"]}
    B = {L["id"]: L for L in doc["states"][s1]["layers"]}
    blend = doc["states"][s1].get("blend", doc["default_blend"])
    frames = []
    for i in range(n):
        p = i / (n - 1)
        t = p * blend
        e = {}
        for lid in set(A) | set(B):
            a, b = A.get(lid), B.get(lid)
            if a and b:
                ya = a["y"] + a.get("vy", 0) * t0
                sp_a, sp_b = a.get("speed", 0), b.get("speed", 0)
                xoff = sp_a * (t0 + 8) + sp_a * t + (sp_b - sp_a) * t * p / 2
                e[lid] = (ya + (b["y"] - ya) * p, xoff, a.get("alpha", 1) + (b.get("alpha", 1) - a.get("alpha", 1)) * p, b.get("x"))
            elif b:
                e[lid] = (b["y"], b.get("speed", 0) * (t + 8), b.get("alpha", 1) * p, b.get("x"))
            else:
                e[lid] = (a["y"] + a.get("vy", 0) * (t0 + t), a.get("speed", 0) * (t0 + 8 + t), a.get("alpha", 1) * (1 - p), a.get("x"))
        bg = [lerp_c(doc["states"][s0]["bg"][k], doc["states"][s1]["bg"][k], p) for k in (0, 1)]
        frames.append((e, bg, f"{s0}→{s1} {t:.1f}s"))
    return frames


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 6 * len(text) + 4, 10], fill=(0, 0, 0, 255))
    d.text((2, 0), text, fill=(200, 200, 200, 255))
    return im


def preview(dirpath, arrs, doc):
    dirpath = Path(dirpath)
    dirpath.mkdir(parents=True, exist_ok=True)
    back = Image.open(ROOT / "art/cockpit/cockpit_back.png").convert("RGBA")
    tiles = []
    for s in ORDER:
        st = doc["states"][s]
        tiles.append(label(render(arrs, doc, settled(doc, s, 0.0), st["bg"], back), s))
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * (SW + 4), rows * (SH + 4)), (0, 0, 0, 255))
    for i, t in enumerate(tiles):
        sheet.alpha_composite(t, ((i % cols) * (SW + 4), (i // cols) * (SH + 4)))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(dirpath / "sheet.png")
    for k, (s0, s1, t0) in enumerate((("forest_canopy", "canopy_fall", 1.5), ("canopy_fall", "forest_below", 4.0),
                                      ("forest_far", "turning", 0.5), ("turning", "clouds", 1.0),
                                      ("clouds_fast", "river_planet", 3.0), ("river_planet", "river_city", 2.0),
                                      ("river_city", "clocktower", 3.0), ("boats", "tilt", 2.0),
                                      ("skid", "channel", 1.5))):
        fr = transition_frames(doc, s0, s1, 5, t0)
        strip = Image.new("RGBA", (5 * (SW + 4), SH), (0, 0, 0, 255))
        for i, (e, bg, name) in enumerate(fr):
            strip.alpha_composite(label(render(arrs, doc, e, bg, back), name), (i * (SW + 4), 0))
        strip.save(dirpath / f"trans_{k}_{s0}_{s1}.png")
    # 碎石：在云和碎石墙背景上，船上下沿各飞一块（看清不清楚）
    rocks = debris_sprites()
    for s in ("clouds", "debris_wall"):
        im = render(arrs, doc, settled(doc, s), doc["states"][s]["bg"], back)
        x = 20
        for i, (n, r) in enumerate(rocks.items()):
            im.alpha_composite(Image.fromarray(r), (x, 50 if i % 2 else 208))
            x += 90
        im.resize((SW * 2, SH * 2), Image.NEAREST).save(dirpath / f"debris_on_{s}.png")
    # 每张图本身（tile 横着接两遍看接缝）
    for k, a in arrs.items():
        im = Image.fromarray(a)
        if doc["layers"][k].get("tile"):
            im2 = Image.new("RGBA", (im.width * 2, im.height), (255, 0, 255, 255))
            im2.alpha_composite(im, (0, 0))
            im2.alpha_composite(im, (im.width, 0))
            im = im2
        im.save(dirpath / f"layer_{k}.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default=None, help="预览图写到这个目录")
    args = ap.parse_args()
    arrs, doc = build()
    if args.preview:
        preview(args.preview, arrs, doc)
