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



# ============================================================ 颜色：向量化的 sRGB <-> OKLab（整张图换色用）
def _lin(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _gam(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


def rgb2lab(rgb):
    r, g, b = np.moveaxis(_lin(np.asarray(rgb, float)), -1, 0)
    l = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return np.stack([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                     1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                     0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s], -1)


def lab2rgb(lab):
    L, a, b = np.moveaxis(np.asarray(lab, float), -1, 0)
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = np.stack([4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
                    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
                    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s], -1)
    return (_gam(rgb) * 255).round().astype(np.uint8)


def renight(a, L_of, h_dark, h_lit, L_lo=.08, L_hi=.30, c_k=0.45, c_max=0.034):
    """作者的图整张换色：亮度按 L_of 映射（保住明暗结构、一档一档的台阶也照旧），色相按新亮度在 h_dark..h_lit 之间走，
    色度乘 c_k、封顶 c_max。只换颜色，不动一个像素的位置。"""
    out = a.copy()
    m = a[..., 3] > 0
    cols, inv = np.unique(a[m][:, :3], axis=0, return_inverse=True)
    lab = rgb2lab(cols)
    L2 = L_of(lab[:, 0])
    C2 = np.minimum(np.hypot(lab[:, 1], lab[:, 2]) * c_k, c_max)
    t = np.clip((L2 - L_lo) / (L_hi - L_lo), 0, 1)
    h = np.radians(h_dark + (h_lit - h_dark) * t)
    new = lab2rgb(np.stack([L2, C2 * np.cos(h), C2 * np.sin(h)], -1))
    out[m, :3] = new[inv.ravel()]
    return out


SKY_PAD = 48           # 整屏的天（不 tile）四边各多画这么多：引擎的背景比屏幕每边大 SKY_M = 48，镜头抖不露出底色的色带


def widen(a, pad=SKY_PAD):
    """480×270 的天往四边镜像出 pad 像素（镜像不会把星星拉成线）。用的时候 x = y = -pad。"""
    return np.pad(a, ((pad, pad), (pad, pad), (0, 0)), mode="symmetric")


def pad_foot(a, n):
    """图下面再接 n 行最后一行（层往上挪时下沿不露缝）。"""
    return np.concatenate([a, np.repeat(a[-1:], n, axis=0)], axis=0)


def crop_rows(a, pad=1):
    r = np.nonzero(a[..., 3].any(1))[0]
    y0 = max(0, r.min() - pad)
    return a[y0:r.max() + 1 + pad], int(y0)


# ============================================================ 云（穿云、云海、碎石带、加速）：作者的云海场景（scenes/cloud_test.tscn）
# 10-30 作者：「可以但是细节处理的不好」，原来的云是扁椭圆 + 三档平涂，没有体积。现在：
# - 天：就是作者云海场景的天（art/cloud/sky.png：余晖在地平线左边、扇形光芒、星、银河），整张换成月夜的青绿（renight）。
#   余晖在机头前方（往那边飞），是第一眼的焦点；最亮压到 L≈.31（比舱壁亮的部分暗）。
# - 高云：作者的 high.png（几条被余晖从下面照亮的薄云）同样换色。
# - 云海：直接调 tools/cloud_art.py 的 Field / sea_row / sea_layer2（球堆 + 菜花小球、朝光走几步出团来分明暗），
#   远 / 中远 / 中三层的参数照作者的 build_far / build_midfar / build_mid 抄（云山也在；云象不放——那是最后一站的）。
#   只把色阶换成月夜：暗端深青（h 206）、受光往青绿（h 172），不是作者那颗星的玫瑰紫。
# - cloud_deck（穿云 + 脚下最近的云海）：同一套画法，团顶照作者的 build_near，肚子里再几排更近更暗的菜花团，
#   下沿是一排垂下来的云底：穿云时一团团往下掠，不是一整块平涂。
# - wisps：近处掠过的小云团也是菜花球（不是扁椭圆），下半截暗一档，有体积。
sys.path.insert(0, str(ROOT / "tools"))
import cloud_art as CA  # noqa: E402

CL_HUE = (206, 172)    # 云：暗端色相、受光端色相


def cl_pal(lo, hi, n, c_lo=.018, c_hi=.036):
    return CA.cloud_pal(lo, hi, n, C_lo=c_lo, C_hi=c_hi, h_lo=CL_HUE[0], h_hi=CL_HUE[1])


def _sky_L(L):
    return np.clip(.078 + .44 * (L - .06), .07, .33)


_CSKY = {}


def cloud_sky_full():
    """作者云海场景的天，换成月夜青绿，四边镜像出 SKY_PAD。"""
    if "a" not in _CSKY:
        a = np.array(Image.open(CA.OUT / "sky.png").convert("RGBA"))
        _CSKY["a"] = widen(renight(a, _sky_L, 214, 168, L_lo=.07, L_hi=.30, c_k=.5, c_max=.036))
    return _CSKY["a"]


def sky_row(y):
    """云海场景里第 y 行天的颜色（余晖右边那一段的平均）：远处的云往这个色里褪。"""
    a = cloud_sky_full()[y + SKY_PAD, SKY_PAD + 260:SKY_PAD + 480, :3]
    lab = rgb2lab(a).mean(0)
    return tuple(int(v) for v in lab2rgb(lab[None])[0])


def cloud_high():
    """作者的 high.png（余晖右边几条被从下面照亮的薄云）换色；只留有东西的那几行。"""
    a = np.array(Image.open(CA.OUT / "high.png").convert("RGBA"))
    a = renight(a, _sky_L, 214, 168, L_lo=.07, L_hi=.30, c_k=.5, c_max=.036)
    a, y0 = crop_rows(a)
    return a, y0


def cloud_sea(which):
    """远 / 中远 / 中三层云海：作者 build_far / build_midfar / build_mid 的参数，月夜色阶。返回 (960×(270+120), 0)。"""
    if which == "far":
        rows = [dict(base=146, z=0, scale=4, sq=0.36, fog=0.36, n=14, h=(1, 5), w=(14, 36), deck=1.0, wave=2.0, big=0.1,
                     rmin=1.2, depth=1),
                dict(base=153, z=20, scale=5.5, sq=0.4, fog=0.24, n=14, h=(2, 8), w=(20, 46), deck=1.5, wave=4.5,
                     big=0.35, rmin=1.4, depth=1),
                dict(base=162, z=40, scale=7, sq=0.44, fog=0.12, n=11, h=(3, 10), w=(26, 56), deck=2.0, wave=5.5,
                     big=0.35, rmin=1.6, depth=2)]
        lay = CA.sea_layer2(rows, cl_pal(.20, .345, 6, .02, .036), sky_row(147), 21, body=2, rim=(1.0, 2.0),
                            crease=1.0, bands=(1.3,), run_bands=(3,), rim_lv=(3, 2))
    elif which == "midfar":
        flats = ((250, 45, 5), (700, 40, 4))
        rows = [dict(base=166, z=0, scale=8, sq=0.5, fog=0.24, n=10, h=(3, 11), w=(26, 70), deck=2, wave=6, big=0.2,
                     rmin=1.6, flats=flats),
                dict(base=177, z=30, scale=11, sq=0.54, fog=0.12, n=8, h=(4, 13), w=(36, 80), deck=2.5, wave=6,
                     big=0.15, rmin=1.8, flats=flats)]
        bigs = (dict(x=560, base=170, h=24, w=70, z=4, sq=0.55, fog=0.18, lean=4, tiers=3),)
        lay = CA.sea_layer2(rows, cl_pal(.17, .325, 6, .02, .036), sky_row(160), 31, bigs=bigs,
                            big_pal=cl_pal(.175, .335, 6, .02, .038), big_kw=dict(rim=(1.5, 3.5), gap=2.0, shadow=3.0,
                                                                                    dark_y=178),
                            body=2, rim=(1.0, 2.5), crease=1.5, bands=(1.0, 2.2), run_bands=(3, 8), rim_lv=(3, 2))
    else:
        flats = ((120, 70, 9), (560, 55, 8), (905, 45, 7))
        rows = [dict(base=190, z=0, scale=15, sq=0.62, fog=0.12, n=6, h=(4, 12), w=(50, 100), deck=3, wave=5.5,
                     big=0.0, kids=(2, 4), ks=(0.35, 0.6), flats=flats),
                dict(base=203, z=40, scale=19, sq=0.66, fog=0.0, n=5, h=(4, 11), w=(60, 120), deck=3, wave=4, big=0.0,
                     kids=(2, 4), ks=(0.35, 0.6), dark=0.12, flats=flats)]
        bigs = (dict(x=335, base=189, h=58, w=100, z=6, sq=0.72, fog=0.06, lean=8, tiers=4, seed=4),
                dict(x=760, base=192, h=41, w=70, z=6, sq=0.7, fog=0.06, lean=4, tiers=4, seed=8))
        lay = CA.sea_layer2(rows, cl_pal(.125, .29, 6, .018, .034), sky_row(190), 41, bigs=bigs,
                            big_pal=cl_pal(.13, .32, 7, .018, .038),
                            big_kw=dict(rim=(2.5, 5.0), gap=4.0, shadow=4.0, dark_y=177, ramp=12, w_lit=(0.55, 1.05)),
                            body=2, rim=(1.5, 3.0), crease=2.0, bands=(0.7, 1.5, 2.6), run_bands=(5, 12, 22),
                            rim_lv=(2, 1))
    return pad_foot(lay.a, 120)


DECK_H = 330           # cloud_deck 的高
DECK_TOP = 40          # 团顶大概在第几行


def cloud_deck():
    """整块云层（穿云 + 脚下最近的云海）：上面是作者 build_near 那样的大团云顶（受光边一小块一小块），
    肚子里三排更近、更暗的菜花团（穿云时一团团往下掠），最下面一排垂下来的云底。"""
    F = CA.Field(TW, DECK_H)
    rng = np.random.default_rng(211)
    CA.sea_row(F, rng, DECK_TOP + 6, 0, 24, 0.72, 0.0, 4, (6, 16), (80, 150), 3, depth=2, wave=4, big=0.1,
               kids=(2, 4), ks=(0.35, 0.58), rmin=3.0)
    CA.sea_row(F, rng, DECK_TOP + 17, 50, 26, 0.75, 0.0, 4, (4, 10), (80, 150), 4, depth=1, wave=3,
               kids=(2, 4), ks=(0.35, 0.58), rmin=3.0)
    for k, (dy, dark, n, rr) in enumerate(((58, 0.6, 14, (16, 30)), (118, 1.2, 12, (18, 34)), (178, 1.8, 11, (20, 36)))):
        for cx in np.sort(rng.uniform(0, TW, n)):
            r = rng.uniform(*rr)
            F.new_group()
            F.row = 10 + k
            top = DECK_TOP + dy + rng.uniform(-8, 8)
            F.cauli(cx, top + r * 0.6 * rng.uniform(0.4, 0.9), r, 100 + 40 * k, rng, sq=0.6, depth=2, kids=(2, 4),
                    ks=(0.32, 0.55), dark=dark, rmin=3.0, spread=(-165, -15), ref=top, unit=10)
    pal = cl_pal(.11, .285, 6, .016, .034)
    a = F.render(pal, body=2, rim=(1.5, 3.0), crease=2.0, bands=(0.8, 1.8), run_bands=(6, 15))
    # 云底：另画一排云顶、上下翻过来，接在最下面 UH 行：垂下来的一团团，受光边翻到了下沿 = 被下面的云海映亮的一圈
    UH = 46
    U = CA.Field(TW, UH)
    ru = np.random.default_rng(212)
    CA.sea_row(U, ru, UH - 4, 0, 13, 0.6, 0.0, 9, (3, 10), (34, 80), 2, depth=2, wave=3, kids=(2, 4), rmin=2.0)
    ua = U.render(cl_pal(.11, .19, 4, .016, .026), body=0, rim=(1.0, 2.0), crease=1.5, bands=(), run_bands=())[::-1]
    a[DECK_H - UH:] = 0
    m = ua[..., 3] > 0
    a[DECK_H - UH:][m] = ua[m]
    a[DECK_H - UH:DECK_H - UH + 6][a[DECK_H - UH:DECK_H - UH + 6, :, 3] == 0] = tuple(pal[0]) + (255,)
    return a


def wisps():
    """近处掠过的小云团：一串菜花球（不连到底），下半截暗一档。多放在船的上下两条（船挡着中间）。"""
    F = CA.Field(TW, 270)
    rng = np.random.default_rng(204)
    bands = [(10, 50)] * 6 + [(216, 262)] * 6 + [(62, 200)] * 3
    order = rng.permutation(len(bands))
    for i, bi in enumerate(order):
        y0, y1 = bands[bi]
        x = i * TW / len(bands) + rng.uniform(-30, 30)
        y = rng.uniform(y0, y1)
        ln = rng.uniform(36, 100)
        r0 = rng.uniform(5, 9)
        F.new_group()
        F.row += 1
        k = int(ln / (r0 * 1.3)) + 1
        for j in range(k):
            u = (j / (k - 1) * 2 - 1) if k > 1 else 0.0
            r = r0 * (1 - 0.45 * abs(u)) * rng.uniform(0.8, 1.2)
            F.cauli(x + u * ln / 2, y + abs(u) * r0 * 0.5, r, (1 - abs(u)) * 4 + rng.uniform(0, 2), rng, sq=0.55,
                    depth=1, kids=(2, 3), ks=(0.35, 0.55), body=False, rmin=1.6, spread=(-160, -20), core=True)
    return F.render(cl_pal(.15, .31, 5, .016, .032), body=2, rim=(1.0, 2.5), crease=1.5, bands=(), lower=0.25)


def streaks():
    """加速时的速度线：1 像素的虚线，很稀；一头亮一头淡（往后拖）。"""
    L = Layer(TW, 270)
    rng = np.random.default_rng(205)
    for i in range(34):
        y = int(rng.integers(2, 268))
        if 64 < y < 206 and rng.random() < 0.6:           # 船挡着的中间那条少放
            continue
        x0 = int(rng.integers(0, TW))
        ln = int(rng.integers(16, 50))
        for x in range(x0, x0 + ln):
            k = (x - x0) / ln
            if (x - x0) % 7 < 5 and not (k > 0.7 and (x - x0) % 2):
                L.a[y, x % TW, :3] = col(.30 - .06 * k, .016, 172)
                L.a[y, x % TW, 3] = 255
    return L


# ============================================================ 碎石：有棱有面的石头（光从左上，按面分明暗）
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


LIGHT3 = np.array([-0.55, -0.6, 0.58]) / np.linalg.norm([-0.55, -0.6, 0.58])


def facet_rock(rng, w, h, tones, rim, m=None):
    """有体积的碎石：从一个偏心的「顶点」往外切成 4~6 个面，每个面一个朝向，按光（左上偏前）分档；
    朝光的外沿一道亮边，背光的下沿最暗。tones 从暗到亮。返回 RGBA。"""
    m = rock_mask(rng, w, h) if m is None else m
    yy, xx = np.mgrid[0:h, 0:w]
    ax = (w - 1) / 2 + rng.uniform(-0.18, 0.18) * w
    ay = (h - 1) / 2 + rng.uniform(-0.18, 0.18) * h
    n = int(rng.integers(4, 7))
    a0 = rng.uniform(0, 2 * math.pi)
    sec = (((np.arctan2(yy - ay, xx - ax) - a0) % (2 * math.pi)) // (2 * math.pi / n)).astype(int)
    mids = a0 + (np.arange(n) + 0.5) * 2 * math.pi / n + rng.uniform(-0.3, 0.3, n)
    tilt = rng.uniform(0.6, 0.85, n)
    nx, ny = np.cos(mids) * tilt, np.sin(mids) * tilt
    nz = np.sqrt(1 - tilt ** 2)
    lam = (nx * LIGHT3[0] + ny * LIGHT3[1] + nz * LIGHT3[2])[sec]
    # 离中心越远越朝外（边上更暗或更亮），让面不是一块平的
    r = np.hypot((xx - ax) / (w / 2), (yy - ay) / (h / 2))
    lam = lam * (0.75 + 0.35 * np.clip(r, 0, 1))
    q = np.clip(np.digitize(lam, [-0.15, 0.2, 0.5]), 0, len(tones) - 1)
    a = np.zeros((h, w, 4), np.uint8)
    for i, c in enumerate(tones):
        a[m & (q == i), :3] = c[:3]
    a[m, 3] = 255
    pad = np.pad(m, 1)
    edge_lit = m & (~pad[:-2, 1:-1] | ~pad[1:-1, :-2])          # 上面或左边是空的
    edge_dark = m & (~pad[2:, 1:-1] | ~pad[1:-1, 2:])            # 下面或右边是空的
    a[edge_dark & (q <= 1), :3] = tones[0][:3]
    a[edge_lit & (lam > 0.0), :3] = rim[:3]
    return a


def stamp(L, a, x, y):
    h, w = a.shape[:2]
    for yy in range(h):
        if not 0 <= y + yy < L.h:
            continue
        for xx in range(w):
            if a[yy, xx, 3]:
                L.a[y + yy, (x + xx) % TW] = a[yy, xx]


def debris_belt():
    """远处的碎石墙：一条横穿天空的带。三种大小（密的小碎粒、中块、少数几块有棱有面的大块），
    一团团扎堆、不匀；小的往天色里褪（远），带子中间一层稀疏抖动的尘。"""
    L = Layer(TW, 120)
    rng = np.random.default_rng(301)
    fogc = col(.15, .014, 190)
    cen = 60 + 9 * pnoise(TW, 31, 1, 4)
    clump = 0.5 + 0.5 * pnoise(TW, 32, 2, 9)                  # 0..1，扎堆的地方密
    # 尘：两档、Bayer 稀疏抖动，中间密两头稀
    dust = [col(.155, .012, 120), col(.17, .012, 100)]
    for x in range(TW):
        for y in range(int(cen[x]) - 20, int(cen[x]) + 21):
            d = abs(y - cen[x]) / 13
            dens = math.exp(-d * d) * (0.35 + 0.65 * clump[x]) * 0.42
            r = rng.random()
            if r < dens * 0.5:
                L.a[y, x, :3] = dust[1 if r < dens * 0.12 else 0]
                L.a[y, x, 3] = 255

    def pick_x():
        while True:
            x = int(rng.integers(0, TW))
            if rng.random() < 0.25 + 0.75 * clump[x]:
                return x
    far_t = [col(.15, .008, R_HUE + 10), col(.17, .009, R_HUE), col(.19, .010, R_HUE - 5)]
    for i in range(900):                                      # 小碎粒（1~3 像素），一半往雾里褪
        x = pick_x()
        y = int(cen[x] + rng.normal(0, 13))
        s = int(rng.integers(1, 4))
        c = far_t[int(rng.integers(0, 3))]
        if rng.random() < 0.5:
            c = tuple(int(v) for v in CA.mix(tuple(c[:3]), fogc, 0.45))
        for yy in range(s if s < 3 else 2):
            for xx in range(s):
                if 0 <= y + yy < L.h:
                    L.a[y + yy, (x + xx) % TW, :3] = c[:3]
                    L.a[y + yy, (x + xx) % TW, 3] = 255
    mid_t = [col(.12, .008, R_HUE + 10), col(.155, .009, R_HUE), col(.19, .010, R_HUE - 5), col(.225, .011, R_HUE - 8)]
    for i in range(170):                                      # 中块 4~7
        x = pick_x()
        s = int(rng.integers(4, 8))
        stamp(L, facet_rock(rng, s, max(3, int(s * rng.uniform(0.6, 0.95))), mid_t, col(.29, .02, 165)),
              x, int(cen[x] + rng.normal(0, 11)) - s // 2)
    big_t = [col(.11, .008, R_HUE + 10), col(.15, .009, R_HUE), col(.19, .011, R_HUE - 5), col(.235, .012, R_HUE - 8)]
    for i in range(22):                                       # 大块 9~15，几块就够
        x = int(i * TW / 22 + rng.integers(0, 30))
        s = int(rng.integers(9, 16))
        stamp(L, facet_rock(rng, s, max(6, int(s * rng.uniform(0.6, 0.85))), big_t, col(.33, .022, 165)),
              x, int(cen[x] + rng.normal(0, 8)) - s // 2)
    return L


def debris_near():
    """碎石墙前面零星漂过的几块中号碎石（10~18 像素，有棱有面），每块后面跟两三粒小碎屑。"""
    L = Layer(TW, 270)
    rng = np.random.default_rng(302)
    tones = [col(.12, .008, R_HUE + 10), col(.16, .009, R_HUE), col(.20, .011, R_HUE - 5), col(.24, .012, R_HUE - 8)]
    rim = col(.36, .022, 165)                                 # 亮边是余晖 / 月光的青绿
    for i in range(12):
        x = int(i * TW / 12 + rng.integers(0, 40))
        y = int(rng.choice([rng.integers(6, 66), rng.integers(214, 252)]))
        s = int(rng.integers(10, 19))
        a = facet_rock(rng, s, max(7, int(s * rng.uniform(0.6, 0.85))), tones, rim)
        stamp(L, a, x, y)
        for k in range(int(rng.integers(2, 4))):
            ss = int(rng.integers(2, 4))
            stamp(L, facet_rock(rng, ss + 1, ss, tones, rim), x + s + 4 + k * int(rng.integers(5, 10)),
                  y + int(rng.integers(0, s)))
    return L


# ============================================================ 星空和河流星球
P_HUE = 250


def space_sky():
    """太空：整屏的天（576×366，不 tile，x = y = -48），盖住引擎那 10 条底色带。上暗下略亮，
    两档之间只在交界留 2 行稀疏抖动；一道很淡的星河斜着过；星分三档，几颗带十字。"""
    Wd, Hd = SW + 2 * SKY_PAD, SH + 2 * SKY_PAD
    a = np.zeros((Hd, Wd, 4), np.uint8)
    a[..., 3] = 255
    xs = np.arange(Wd)
    Ls = np.interp(np.arange(Hd), [0, Hd * 0.6, Hd], [.06, .085, .105])
    STEP = .008
    rng = np.random.default_rng(401)
    yy, xx = np.mgrid[0:Hd, 0:Wd]
    band = np.exp(-(((yy - 0.55 * xx - 40) / 46.0) ** 2))         # 斜的星河
    lumps = np.zeros_like(band)
    for _ in range(40):
        cx, cy, r = rng.uniform(0, Wd), rng.uniform(0, Hd), rng.uniform(10, 40)
        lumps += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r))
    mw = band * np.clip(lumps / lumps.max() * 1.6, 0, 1) * .022
    cache = {}
    for y in range(Hd):
        L = Ls[y] + mw[y]
        lo = np.floor(L / STEP)
        idx = lo + (CA.BAYER[y % 4, xs % 4] < (L / STEP - lo) * (np.abs(L / STEP - lo - 0.5) > 0.3))
        for x in range(Wd):
            k = int(idx[x])
            if k not in cache:
                cache[k] = col(k * STEP, .012, 200)
            a[y, x, :3] = cache[k]
    for i in range(420):
        x, y = int(rng.integers(0, Wd)), int(rng.integers(0, Hd))
        if rng.random() > 0.25 + 3 * mw[y, x] / .022:
            continue
        L = float(rng.choice([.17, .21, .26, .32], p=[.45, .3, .17, .08]))
        a[y, x, :3] = col(L, .014, 180 if rng.random() < .7 else 60)
    for x, y in ((40, 30), (150, 70), (420, 40), (530, 90), (300, 20), (80, 300), (500, 320)):
        a[y, x, :3] = col(.42, .014, 170)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a[y + dy, x + dx, :3] = col(.25, .014, 175)
    return a


# ---------- 飞行一结尾（10-30 作者：「往前一冲，冲入黑色的星空，场景渐暗，第一章就结束了」）
STAR_SEED = 411


def void_sky():
    """黑色星空的底：整屏（576×366，x = y = -48），几乎是黑的（L .03 → .045，上下只差一档、交界两行稀疏抖动），
    零星几颗极暗的远星（不动）。前面的星点 / 星线是 tile 的层，往右卷。"""
    Wd, Hd = SW + 2 * SKY_PAD, SH + 2 * SKY_PAD
    a = np.zeros((Hd, Wd, 4), np.uint8)
    a[..., 3] = 255
    lo, hi = col(.03, .006, 200), col(.042, .008, 200)
    edge = int(Hd * 0.55)
    xs = np.arange(Wd)
    for y in range(Hd):
        c = lo if y < edge else hi
        a[y, :, :3] = c[:3]
        if edge - 2 <= y < edge:
            a[y, CA.BAYER[y % 4, xs % 4] < 0.25, :3] = hi[:3]
    rng = np.random.default_rng(STAR_SEED - 1)
    for _ in range(160):
        x, y = int(rng.integers(0, Wd)), int(rng.integers(0, Hd))
        a[y, x, :3] = col(float(rng.choice([.09, .12, .15])), .01, 190)[:3]
    return a


def _star_list():
    """前景的星（tile 层）：位置、亮度。星点和星线用同一张表，换层时星还在原来的地方。"""
    rng = np.random.default_rng(STAR_SEED)
    out = []
    for _ in range(260):
        x, y = int(rng.integers(0, TW)), int(rng.integers(0, SH + 2 * SKY_PAD))
        L = float(rng.choice([.30, .38, .47, .58], p=[.4, .3, .2, .1]))
        out.append((x, y, L))
    return out


def star_layer(stretch):
    """星点（stretch = 0）或拉长的星线：机头朝左往前冲，星往右飞，尾巴拖在左边——头亮、往左一档档变暗、末端隔点断开。
    越亮的星拖得越长（近）。tile，960 × 366，y = -48。"""
    L_ = Layer(TW, SH + 2 * SKY_PAD)
    for x, y, L in _star_list():
        n = 0 if stretch == 0 else int(round(stretch * (0.45 + 1.4 * (L - .30) / .28)))
        for k in range(n, -1, -1):
            t = k / max(1, n)
            if k > 0 and t > 0.7 and k % 2:
                continue
            c = col(.16 + (L - .16) * (1 - t) ** 1.1, .014, 175)
            L_.a[y, (x - k) % TW, :3] = c
            L_.a[y, (x - k) % TW, 3] = 255
        if stretch == 0 and L >= .58:                        # 最亮的几颗带个小十字
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if 0 <= y + dy < L_.h:
                    L_.a[y + dy, (x + dx) % TW, :3] = col(.28, .014, 175)
                    L_.a[y + dy, (x + dx) % TW, 3] = 255
    return L_.a


def planet(d, seed, rivers=True):
    """河流星球（夜里的那一面朝着我们）：深蓝的海、暗青的陆，亮的河弯弯曲曲，月光从左上照着一弯；
    右下大半在夜里，夜里那半边陆地上零星几点暖的灯（小镇）。左上一圈大气亮边。"""
    pad = 2
    n = d + 2 * pad
    a = np.zeros((n, n, 4), np.uint8)
    yy, xx = np.mgrid[0:n, 0:n]
    c = (n - 1) / 2
    r = d / 2
    dist = np.hypot(xx - c, yy - c)
    disc = dist <= r - 0.3
    rng = np.random.default_rng(seed)
    land = np.zeros_like(disc)
    for _ in range(max(3, d // 7)):
        lx, ly = rng.uniform(c - r * 0.8, c + r * 0.8), rng.uniform(c - r * 0.7, c + r * 0.7)
        lr = rng.uniform(r * 0.18, r * 0.42)
        land |= (np.hypot((xx - lx) * 0.8, yy - ly) < lr)
    land &= disc
    nx, ny = (xx - c) / r, (yy - c) / r
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))
    lam = -0.62 * nx - 0.55 * ny + 0.55 * nz
    q = np.digitize(lam, [0.0, 0.35, 0.7])                          # 0 夜 / 1 暗 / 2 中 / 3 亮
    sea = [col(.13, .03, P_HUE + 6), col(.18, .045, P_HUE + 2), col(.235, .05, P_HUE - 2), col(.29, .045, P_HUE - 8)]
    gnd = [col(.12, .016, 200), col(.16, .022, 190), col(.20, .026, 180), col(.245, .028, 175)]
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
            dr.line(pts, fill=(255, 0, 255, 255), width=1)
        b = np.array(img)
        rv = (b[..., :3] == (255, 0, 255)).all(-1) & land
        a[rv & (q >= 2), :3] = col(.34, .04, 235)
        a[rv & (q == 1), :3] = col(.26, .04, 240)
        a[rv & (q == 0), :3] = col(.17, .03, 245)
        # 夜里那半边：陆地上几点暖的灯
        night = disc & land & (q == 0) & ~rv
        ys, xs_ = np.nonzero(night)
        for i in rng.choice(len(ys), min(len(ys), d // 6), replace=False):
            a[ys[i], xs_[i], :3] = col(.42, .08, 75)
    a[disc, 3] = 255
    ring = (dist > r - 0.3) & (dist <= r + 0.9)
    lit_side = (-(xx - c) - (yy - c)) > -r * 0.2
    a[ring & lit_side, :3] = col(.30, .04, 225)
    a[ring & lit_side, 3] = 255
    inner = disc & (dist > r - 1.4) & lit_side & (lam > 0.3)
    a[inner, :3] = col(.34, .04, 222)
    ys, xs = np.nonzero(a[..., 3])
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


# ============================================================ 河流星：月夜的水上小镇（作者的蓝色月夜河岸 scenes/river_test.tscn）
# 10-30：降落几段原来是灰蓝白天的鸽子笼城市。河流篇按作者的蓝色月夜河岸重做（满月、石柱、垂枝树、雾、水面碎光），
# 风格是月夜里的水上小镇——石像、暖黄的灯、小房子分开不重叠，不是灰色大都市。所以：
# - 天 / 远岸石柱 / 雾 / 近岸的怪树：直接用作者的 art/river/sky.png、ridge.png、mist.png、shore.png（月亮在屏幕 x≈338）。
# - 月亮在水里碎成的亮纹（moon_glint）：作者 river_art.glints() 那道，按 GLINT_PAL 直接上色（船外背景没有 shader，不闪）。
# - 自己画的：河面（ground）、远处一排小镇（city_far）、近处的水上小镇（city_mid）、钟楼、水道和停着的小船（canal）、
#   近水（water_near）、水花、木箱、起飞离开时的一排屋子（river_row）。
# - 落水卡进窄水道那两屏（channel_mid / channel_bank）直接是河岸开场那一屏（bank_mid / bank_main），和第二章开场接上。
#   颜色照 river_art：亮面偏青银、暗面偏深蓝（river_art.lch 按亮度转色相），光从右上（月亮）来，
#   亮度压在驾驶舱以下；只有窗、灯是暖黄的小点（和水里的倒影）。
import river_art as RA  # noqa: E402
import river_bank_moon_art as RB  # noqa: E402

WARM_HI = col(.66, .085, 78)        # 亮着的窗 / 灯芯（和 river_bank_moon_art 的 WARM 同一套，最亮 .66 比晨暗）
WARM = col(.58, .09, 70)
WARM_LO = col(.48, .085, 64)        # 窗框里暗一点的那格、远处的灯
WARM_REF = col(.34, .06, 60)        # 水里的暖倒影
DARK_WIN = RA.lch(.10, .02, 258)


def rl(L, C=None, h=256.0):
    """河流星的颜色（river_art.lch：按亮度转色相，暗的偏靛、亮的偏青银）。"""
    return RA.lch(L, C, h)


def river_sky():
    return widen(np.array(Image.open(RA.OUT / "sky.png").convert("RGBA")))


def river_layer(name):
    return np.array(Image.open(RA.OUT / f"{name}.png").convert("RGBA"))


def moon_glint():
    """月亮在河面上碎成的那道亮纹（作者 glints()，R 是亮度档）：480×60，贴在屏幕 y = 155。"""
    g = RA.glints()
    out = np.zeros_like(g)
    m = g[..., 3] > 0
    tone = g[..., 0] / 255.0
    pal = [from_lch(*p) for p in RA.GLINT_PAL]
    idx = np.clip(np.round(tone * 3), 0, 3).astype(int)
    for i, c in enumerate(pal):
        sel = m & (idx == i) & (tone > 0.12)
        out[sel, :3] = c[:3]
        out[sel, 3] = 255
    return out


class Px:
    """直接点像素的画布（左右绕回）。"""

    def __init__(self, w, h, tile=True):
        self.w, self.h, self.tile = w, h, tile
        self.a = np.zeros((h, w, 4), np.uint8)

    def put(self, x, y, c):
        x, y = int(round(x)), int(round(y))
        if self.tile:
            x %= self.w
        if 0 <= y < self.h and 0 <= x < self.w:
            self.a[y, x, :3] = c[:3]
            self.a[y, x, 3] = 255

    def fill(self, x0, y0, x1, y1, c):
        x0, x1 = int(round(x0)), int(round(x1))
        y0, y1 = max(0, int(round(y0))), min(self.h - 1, int(round(y1)))
        if y1 < y0 or x1 < x0:
            return
        xs = np.arange(x0, x1 + 1)
        if self.tile:
            xs %= self.w
        else:
            xs = xs[(xs >= 0) & (xs < self.w)]
        self.a[y0:y1 + 1, xs, :3] = c[:3]
        self.a[y0:y1 + 1, xs, 3] = 255

    def paste(self, img, x, y):
        h, w = img.shape[:2]
        for yy in range(h):
            if not 0 <= y + yy < self.h:
                continue
            m = img[yy, :, 3] > 0
            xs = np.arange(x, x + w)[m]
            if self.tile:
                xs %= self.w
            else:
                keep = (xs >= 0) & (xs < self.w)
                xs, m2 = xs[keep], np.nonzero(m)[0][keep]
                self.a[y + yy, xs] = img[yy, m2]
                continue
            self.a[y + yy, xs] = img[yy, m]


def house(P, x, base, w, h, rng, s=1.0, lit_p=0.55, stilts=0, wall=None):
    """一栋小房子：墙、坡屋顶（人字 / 单坡 / 平顶带烟囱）、门、一两扇窗（多半亮着暖黄的灯）。
    光从右上：墙的右边一列亮一档，屋顶右坡和屋脊亮；左边一列暗。stilts > 0 = 底下几根桩子插进水里。"""
    wall = wall if wall is not None else rl(rng.choice([.15, .17, .19]) * 1.0, .02, rng.choice([250, 256, 262]))
    wall_lit = tuple(int(v) for v in CA.mix(tuple(wall[:3]), tuple(rl(.30, .02, 246)[:3]), 0.35))
    wall_dk = tuple(int(v) for v in CA.mix(tuple(wall[:3]), (6, 9, 16), 0.3))
    roof = rl(rng.choice([.105, .12]), .02, 258)
    roof_lit = rl(.27, .02, 246)
    top = base - h
    P.fill(x, top, x + w - 1, base, wall)
    P.fill(x + w - 1, top, x + w - 1, base, wall_lit)
    P.fill(x, top, x, base, wall_dk)
    kind = rng.choice(["gable", "gable", "shed", "flat"])
    if kind == "gable":
        rh = max(3, int(round(w * rng.uniform(0.35, 0.5))))
        for k in range(rh + 1):
            y = top - k
            x0 = x - 1 + k * (w + 1) / (2 * rh)
            x1 = x + w - k * (w + 1) / (2 * rh)
            P.fill(x0, y, x1, y, roof)
            P.put(x1, y, roof_lit)
            if k == rh:
                P.fill(x0, y, x1, y, roof_lit)
        P.fill(x - 1, top, x + w, top, roof)
    elif kind == "shed":                                     # 单坡：左高右低
        rh = max(2, int(round(w * 0.3)))
        for k in range(rh + 1):
            x1 = x - 1 + int((w + 1) * (1 - k / (rh + 1)))
            P.fill(x - 1, top - k, x1, top - k, roof)
            P.put(x1, top - k, roof_lit)
        P.fill(x - 1, top - rh, x - 1 + int((w + 1) / (rh + 1)), top - rh, roof_lit)
    else:
        P.fill(x - 1, top - 1, x + w, top, roof)
        P.fill(x - 1, top - 1, x + w, top - 1, roof_lit)
        cx = x + int(rng.integers(1, max(2, w - 3)))
        P.fill(cx, top - 4, cx + 1, top - 2, roof)
        P.put(cx + 1, top - 4, roof_lit)
    # 窗：2×2（远的小房子 1×1），多半亮着
    ww = 1 if w < 9 else 2
    wy = top + max(2, int(h * 0.3))
    nwin = max(1, (w - 2) // (ww + 3))
    for i in range(nwin):
        wx = x + 2 + i * (ww + 3) + (1 if w >= 9 else 0)
        if wx + ww > x + w - 2:
            break
        lit = rng.random() < lit_p
        if lit:
            P.fill(wx, wy, wx + ww - 1, wy + ww - 1, WARM)
            P.put(wx + ww - 1, wy, WARM_HI)
            if ww == 2 and rng.random() < 0.5:
                P.fill(wx, wy + ww - 1, wx + ww - 1, wy + ww - 1, WARM_LO)
        else:
            P.fill(wx, wy, wx + ww - 1, wy + ww - 1, DARK_WIN)
    if h >= 8 and w >= 7:                                   # 门
        dx = x + int(rng.integers(1, w - 3))
        lit = rng.random() < 0.3
        P.fill(dx, base - min(5, h - 3), dx + 1, base - 1, WARM_LO if lit else rl(.09, .02, 258))
    for k in range(stilts):                                  # 桩子
        sx = x + 1 + k * (w - 3) // max(1, stilts - 1)
        P.fill(sx, base + 1, sx, base + 4, rl(.11, .018, 258))
    return top


def statue(P, x, base, h, rng, kind=None):
    """石像：台座上一个披袍的人形（站着 / 举着灯 / 坐着的大石头头像）。石头青灰，右边受月光一道亮边；举灯的那尊手里一点暖光。"""
    pal = [rl(.11, .018, 258), rl(.15, .02, 254), rl(.20, .02, 250), rl(.30, .02, 246)]
    kind = kind or rng.choice(["robe", "lamp", "head"])
    pw = max(4, int(h * 0.28))
    ph = max(2, int(h * 0.16))
    P.fill(x - pw // 2, base - ph, x + pw // 2, base, pal[1])
    P.fill(x - pw // 2 - 1, base - ph, x + pw // 2 + 1, base - ph, pal[2])
    P.fill(x + pw // 2, base - ph, x + pw // 2, base, pal[2])
    top = base - ph
    if kind == "head":
        r = max(3, int(h * 0.32))
        cy = top - r
        for yy in range(-r, r + 1):
            hw = int(round(r * math.sqrt(max(0, 1 - (yy / r) ** 2)) * (0.85 if yy < 0 else 1.0)))
            P.fill(x - hw, cy + yy, x + hw, cy + yy, pal[1])
            P.put(x + hw, cy + yy, pal[3] if yy < r * 0.4 else pal[2])
            P.put(x - hw, cy + yy, pal[0])
        P.fill(x - 1, cy - 1, x - 1, cy, pal[0])                     # 闭着的眼
        P.fill(x + 2, cy - 1, x + 2, cy, pal[0])
        P.fill(x, cy + r // 2, x + 2, cy + r // 2, pal[0])
        return
    bh = h - ph
    hr = max(1, int(round(bh * 0.09)))
    for k in range(bh - 2 * hr):                                      # 袍子：上窄下宽
        t = k / max(1, bh - 2 * hr)
        hw = 1 + int(round((pw * 0.45) * t))
        y = top - k
        P.fill(x - hw + (0 if t > 0.2 else 1), y, x + hw - 1, y, pal[1])
        P.put(x + hw - 1, y, pal[3] if k > 2 else pal[2])
        P.put(x - hw + (0 if t > 0.2 else 1), y, pal[0])
    hy = top - (bh - 2 * hr) - hr
    for yy in range(-hr, hr + 1):
        P.fill(x - hr, hy + yy, x + hr - 1, hy + yy, pal[1])
        P.put(x + hr - 1, hy + yy, pal[3])
    if kind == "lamp":                                                # 举起一只手，托一盏小灯
        ax = x + hr + 1
        for k in range(int(bh * 0.45)):
            P.put(ax + k // 4, top - int(bh * 0.5) - k, pal[2])
        lx, ly = ax + int(bh * 0.45) // 4, top - int(bh * 0.5) - int(bh * 0.45)
        P.fill(lx - 1, ly - 2, lx, ly - 1, WARM)
        P.put(lx, ly - 2, WARM_HI)


def lamp_post(P, x, base, h):
    P.fill(x, base - h, x, base, rl(.10, .018, 258))
    P.put(x + 1, base - h, rl(.10, .018, 258))
    P.fill(x + 1, base - h + 1, x + 2, base - h + 2, WARM)
    P.put(x + 2, base - h + 1, WARM_HI)


def reflect_down(P, wl, length, rng, water_c, warm=True, gaps=0.35):
    """水线 wl 以上的东西倒过来画到下面：往水色里褪、一行行左右晃、越往下越碎；暖的灯在水里拉成一条条竖的亮痕。"""
    src = P.a.copy()
    W_ = P.w
    xs = np.arange(W_)
    wl_lab = rgb2lab(np.array(water_c[:3]))
    for r in range(length):
        sy, dy = wl - 1 - r, wl + 1 + r
        if sy < 0 or dy >= P.h:
            break
        f = r / length
        row = np.roll(src[sy], int(round(math.sin(r * 1.37) * (0.5 + 1.5 * f))), axis=0)
        m = (row[:, 3] > 0) & (rng.random(W_) > gaps * (0.4 + 1.2 * f))
        if r % 2:
            m &= rng.random(W_) > 0.35
        if not m.any():
            continue
        lab = rgb2lab(row[m, :3])
        warm_px = (lab[:, 0] > .4) & warm
        t = np.where(warm_px, 0.35 + 0.4 * f, 0.55 + 0.4 * f)
        new = lab * (1 - t[:, None]) + wl_lab[None] * t[:, None]
        P.a[dy, xs[m], :3] = lab2rgb(new)
        P.a[dy, xs[m], 3] = 255


def water_rows(P, y0, y1, L0, L1, rng, glint=0.0, warm_p=0.0, h=252):
    """一片水：从 L0 渐到 L1（分档 + 交界两行稀疏抖动），上面一道道月光的横向亮痕（越近越长越稀）。"""
    xs = np.arange(P.w)
    STEP = .012
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(1, y1 - y0)
        L = L0 + (L1 - L0) * t
        lo = np.floor(L / STEP)
        fr = L / STEP - lo
        idx = lo + (CA.BAYER[y % 4, xs % 4] < fr) * (abs(fr - 0.5) > 0.32)
        for k in np.unique(idx):
            sel = idx == k
            P.a[y, sel, :3] = rl(k * STEP, None, h)[:3]
        P.a[y, :, 3] = 255
    for _ in range(int(glint * P.w * (y1 - y0) / 400)):
        y = int(rng.integers(y0 + 1, y1 + 1))
        t = (y - y0) / max(1, y1 - y0)
        ln = int(rng.integers(2, 5) + 10 * t * rng.random())
        x = int(rng.integers(0, P.w))
        L = L0 + (L1 - L0) * t + rng.choice([.05, .08, .12])
        P.fill(x, y, x + ln, y, rl(L, .03, 250))


# ---------- 远处：地平线下的河面（从高处往下看：宽的河、几道暗的沙洲，洲上零星的小镇灯火）
def ground():
    P = Px(TW, 130)
    rng = np.random.default_rng(601)
    # 水：作者 river_art 的水色（WATER_L：贴着地平线亮、越近越暗），屏幕 y = 151 + 行号
    for y in range(P.h):
        Lw = RA.base_L(151 + min(y * 0.9, 118))
        P.fill(0, y, TW - 1, y, rl(float(RA.quant_L(Lw)), None, RA.WATER_H))
    # 沙洲 / 对岸：越近越厚、越暗；上沿一行受月光
    for i, (y, th, amp) in enumerate(((10, 1, 1), (18, 2, 2), (30, 3, 3), (48, 4, 5), (74, 6, 7), (108, 8, 9))):
        n = pnoise(TW, 610 + i, 1, 5)
        on = pnoise(TW, 620 + i, 2, 7) > (0.1 - 0.05 * i)
        Ll = .135 - .006 * i
        for x in range(TW):
            if not on[x]:
                continue
            yy = int(y + amp * n[x])
            P.fill(x, yy, x, yy + th, rl(Ll, .018, 200))
            P.put(x, yy, rl(Ll + .05, .02, 210))
        # 洲上的小镇：一小撮暖的点（越近越大）
        for _ in range(4 + i):
            x = int(rng.integers(0, TW))
            if not on[x]:
                continue
            yy = int(y + amp * n[x])
            for k in range(int(rng.integers(2, 6))):
                px = x + int(rng.integers(-3 - i, 4 + i))
                if 0 <= px < TW and on[px % TW]:
                    P.put(px, yy - (1 if i > 2 else 0), WARM_LO if i < 3 or rng.random() < 0.6 else WARM)
                    if i >= 3:
                        P.put(px, yy - 2, rl(Ll + .02, .018, 210))
    # 远处的雾：两三团贴水面的淡雾
    for _ in range(14):
        x, y, ln = int(rng.integers(0, TW)), int(rng.integers(2, 40)), int(rng.integers(20, 60))
        for k in range(ln):
            if (x + k + y) % 2 or abs(k - ln / 2) < ln * 0.3:
                P.put(x + k, y, rl(float(RA.quant_L(RA.base_L(151 + y) + .03)), None, RA.WATER_H))
    return P.a


# ---------- 远处一排小镇：贴着水的小房子（分开）、石像、灯、伞树；水里的倒影
def city_far():
    P = Px(TW, 64)
    rng = np.random.default_rng(701)
    WL = 46
    bank = rl(.13, .018, 256)
    x = int(rng.integers(0, 8))
    while x < TW - 14:
        r = rng.random()
        if r < 0.62:
            w, h = int(rng.integers(6, 13)), int(rng.integers(4, 10))
            P.fill(x - 1, WL - 1, x + w, WL, bank)
            house(P, x, WL - 2, w, h, rng, lit_p=0.6, stilts=0)
            x += w + int(rng.integers(4, 14))
        elif r < 0.78:
            statue(P, x + 3, WL - 1, int(rng.integers(10, 16)), rng, kind=rng.choice(["robe", "lamp"]))
            x += 9
        elif r < 0.9:
            lamp_post(P, x, WL - 1, int(rng.integers(5, 8)))
            x += 6
        else:
            tmp = RA.Layer(TW, 64)
            RA.strange_tree(tmp, x + 5, WL - 1, int(rng.integers(10, 16)), int(rng.integers(8, 13)),
                            int(rng.integers(0, 999)), RA.bramp(3, .11, .16, 258, 248),
                            rng.choice(["umbrella", "young", "weeping"]))
            P.paste(tmp.a, 0, 0)
            x += 14
    P.fill(0, WL + 1, TW - 1, P.h - 1, (0, 0, 0))
    P.a[WL + 1:, :, 3] = 0
    water = rl(.20, None, RA.WATER_H)
    reflect_down(P, WL + 1, P.h - WL - 2, rng, water, gaps=0.45)
    # 远的整层往水 / 雾色里褪一点
    m = P.a[..., 3] > 0
    lab = rgb2lab(P.a[m][:, :3])
    fog = rgb2lab(np.array(rl(.24, None, 254)[:3]))
    warm = lab[:, 0] > .4
    lab = np.where(warm[:, None], lab * 0.85 + fog * 0.15, lab * 0.7 + fog * 0.3)
    P.a[m, :3] = lab2rgb(lab)
    return P.a


CITY_WL = 120          # city_mid 的水线（行号）


def city_mid():
    """近处的水上小镇：一栋栋小房子（分开、不重叠，有的立在石头基座上、有的插着桩子站在水里），
    之间是石像、路灯、伞树和下到水边的石阶；暖黄的窗；下面一片水，倒影里灯拉成竖的亮痕。"""
    P = Px(TW, 168)
    rng = np.random.default_rng(702)
    WL = CITY_WL
    stone = [rl(.12, .018, 258), rl(.16, .02, 254), rl(.24, .02, 248)]
    x = 6
    gap_items = ["statue", "lamp", "tree", "stairs", "statue", "tree", "lamp"]
    gi = 0
    while x < TW - 40:
        w = int(rng.integers(16, 30))
        h = int(rng.integers(12, 26))
        on_stilts = rng.random() < 0.35
        if on_stilts:
            base = WL - int(rng.integers(5, 9))
            house(P, x, base, w, h, rng, lit_p=0.6, stilts=int(rng.integers(3, 5)))
            for k in range(base + 1, WL + 1):
                pass
        else:
            bh = int(rng.integers(4, 10))                      # 石头基座：一块块砌起来，上沿受光
            P.fill(x - 2, WL - bh, x + w + 1, WL, stone[1])
            P.fill(x - 2, WL - bh, x + w + 1, WL - bh, stone[2])
            P.fill(x + w + 1, WL - bh, x + w + 1, WL, stone[2])
            for yy in range(WL - bh + 3, WL + 1, 3):
                off = 0 if (yy // 3) % 2 else 3
                for xx in range(x - 2 + off, x + w + 1, 6):
                    P.put(xx, yy, stone[0])
            P.fill(x - 2, WL - 1, x + w + 1, WL, rl(.10, .02, 220))   # 水线上的苔
            house(P, x, WL - bh - 1, w, h, rng, lit_p=0.6)
        x += w + 4
        # 房子之间的空：放一样东西，再空一点
        item = gap_items[gi % len(gap_items)]
        gi += 1
        if item == "statue":
            sh = int(rng.integers(30, 46))
            P.fill(x - 1, WL - 3, x + 13, WL, stone[1])
            P.fill(x - 1, WL - 3, x + 13, WL - 3, stone[2])
            statue(P, x + 6, WL - 4, sh, rng)
            x += 18
        elif item == "lamp":
            lamp_post(P, x + 2, WL - 1, int(rng.integers(12, 18)))
            x += 8
        elif item == "tree":
            tmp = RA.Layer(TW, 168)
            RA.strange_tree(tmp, x + 10, WL - 1, int(rng.integers(26, 40)), int(rng.integers(16, 24)),
                            int(rng.integers(0, 999)), RA.bramp(3, .10, .17, 258, 248),
                            rng.choice(["umbrella", "weeping", "mushroom", "lean"]))
            P.paste(tmp.a, 0, 0)
            P.fill(x + 2, WL - 1, x + 18, WL, stone[1])
            x += 22
        else:
            for k in range(6):                                 # 下到水边的石阶
                P.fill(x + k * 2, WL - 6 + k, x + 12, WL - 6 + k, stone[1] if k % 2 else stone[2])
            x += 14
        x += int(rng.integers(6, 16))
    # 水
    P.a[WL + 1:] = 0
    water_c = rl(.17, None, RA.WATER_H)
    reflect_down(P, WL + 1, P.h - WL - 2, rng, water_c, gaps=0.35)
    W2 = Px(TW, P.h)
    water_rows(W2, WL + 1, P.h - 1, .175, .13, rng, glint=1.2)
    under = P.a[..., 3] == 0
    P.a[under] = W2.a[under]
    P.fill(0, WL + 1, TW - 1, WL + 1, rl(.22, .02, 250))
    return P.a


def clocktower():
    """钟楼：老石头方塔，顶上尖顶；钟面亮着暖黄的灯（整个镇上最亮的一块，但比晨暗），指针停着；
    右边受月光一道亮边，几扇窄窗里一点暖光。"""
    w, h = 32, 210
    P = Px(w, h, tile=False)
    pal = [rl(.10, .018, 258), rl(.14, .02, 255), rl(.18, .02, 252), rl(.29, .02, 246)]
    P.fill(8, 46, 23, h - 1, pal[1])
    P.fill(23, 46, 23, h - 1, pal[3])
    P.fill(22, 46, 22, h - 1, pal[2])
    P.fill(8, 46, 8, h - 1, pal[0])
    for y in range(50, h, 6):                                       # 石缝（错开）
        P.fill(9, y, 21, y, pal[0])
        for x in range(10 + (3 if (y // 6) % 2 else 0), 22, 6):
            P.put(x, y + 3, pal[0])
    for i, y in enumerate(range(78, h - 20, 26)):                   # 窄窗
        P.fill(15, y, 16, y + 6, WARM_LO if i % 3 == 1 else DARK_WIN)
        if i % 3 == 1:
            P.put(16, y, WARM)
    P.fill(6, 27, 25, 46, pal[1])                                    # 钟室
    P.fill(25, 27, 25, 46, pal[3])
    P.fill(6, 27, 6, 46, pal[0])
    P.fill(5, 46, 26, 47, pal[2])                                    # 檐
    P.fill(26, 46, 26, 47, pal[3])
    P.fill(5, 26, 26, 26, pal[2])
    face = WARM_LO
    for yy in range(-6, 7):
        hw = int(round(math.sqrt(max(0, 36.5 - yy * yy))))
        P.fill(15.5 - hw, 36 + yy, 15.5 + hw, 36 + yy, face)
    for yy in range(-5, 6):
        hw = int(round(math.sqrt(max(0, 25.5 - yy * yy))))
        P.fill(15.5 - hw, 36 + yy, 15.5 + hw, 36 + yy, WARM)
    for yy in range(-3, 1):
        P.put(19 + yy // 2, 33 + yy, WARM_HI)
    for dx, dy in ((0, -4), (4, 0), (0, 4), (-4, 0)):
        P.put(15 + dx, 36 + dy, WARM_LO)
    for k in range(5):                                               # 指针：停在一个时间
        P.put(15, 36 - k, rl(.13, .02, 60))
    for k in range(4):
        P.put(15 + k, 36 + k // 2, rl(.13, .02, 60))
    for k in range(21):                                              # 尖顶：左半暗、右半受光
        hw = k * 11.5 / 20
        y = 6 + k
        P.fill(15.5 - hw, y, 15.5 + hw, y, pal[0])
        P.fill(15.5, y, 15.5 + hw, y, pal[1])
        P.put(15.5 + hw, y, pal[3])
    P.fill(15, 0, 15, 6, pal[2])
    P.fill(14, 1, 16, 1, pal[2])
    return P.a


def canal():
    """当跑道的那条宽水道：远岸是一道石砌的堤（河岸那套石头、一盏盏石灯笼），堤下系着一排小木船
    （两头翘的船壳、有的搭着篷、篷边挂一盏暖的小灯），水面一道道月光的亮痕、灯在水里拉成竖的碎倒影。"""
    cv = RB.Cv(TW, 74, wrap=True)
    rng = np.random.default_rng(801)
    Q, SURF = 16, 24                                                 # 堤顶、水面
    for y in range(Q, SURF + 1):
        for x in range(TW):
            cv.px(x, y, RB.ROCK[1] if (x // 6 + y // 3) % 2 else RB.ROCK[2])
    cv.hline(0, TW, Q, RB.ROCK[3])
    for y in range(Q + 3, SURF + 1, 3):
        cv.hline(0, TW, y, RB.ROCK[0])
    lamps = list(range(40, TW, 120))
    for x in lamps:
        RB.stone_lantern(cv, x, Q)
    P = Px(TW, cv.h)
    P.a = cv.a
    water_rows(P, SURF + 1, P.h - 1, .17, .125, rng, glint=2.0)
    P.fill(0, SURF + 1, TW - 1, SURF + 1, rl(.23, .02, 250))
    cv.a = P.a
    WOOD = RB.WOOD
    refl = []
    x = 14
    while x < TW - 40:
        bw = int(rng.integers(22, 34))
        wl = SURF + 2
        for xx in range(x, x + bw):                                  # 船壳：两头翘
            t = (xx - x) / bw
            top = wl - 4 - int(round(3 * (abs(t - 0.5) * 2) ** 2.2))
            for y in range(top, wl + 2):
                cv.px(xx, y, WOOD[1] if y > top else WOOD[3])
        cv.hline(x + 3, x + bw - 3, wl - 3, WOOD[0])
        if rng.random() < 0.65:                                      # 篷 + 挂灯
            cw = int(rng.integers(9, 14))
            cx = x + int(rng.integers(4, bw - cw - 3))
            for k in range(5):
                cv.hline(cx + (1 if k == 0 else 0), cx + cw - (1 if k == 0 else 0), wl - 9 + k, RB.B(.13, .03, 230))
            cv.hline(cx + 1, cx + cw - 1, wl - 9, RB.B(.24, .03, 222))
            if rng.random() < 0.7:
                lx = cx + cw + 1
                cv.vline(lx, wl - 13, wl - 4, WOOD[2])
                cv.rect(lx + 1, wl - 12, lx + 3, wl - 9, RB.WARM[3])
                cv.px(lx + 1, wl - 11, RB.WARM[4])
                refl.append(lx + 2)
        else:                                                        # 没篷的：船上一卷绳、一只桶
            cv.rect(x + bw // 2, wl - 6, x + bw // 2 + 4, wl - 3, WOOD[2])
            cv.hline(x + bw // 2, x + bw // 2 + 4, wl - 6, WOOD[4])
        cv.hline(x + 2, x + bw - 2, wl + 2, rl(.10, .02, 258))      # 船底下的影
        x += bw + int(rng.integers(20, 48))
    for lx in refl + [x_ + 1 for x_ in lamps]:                       # 灯在水里拉成竖的碎倒影
        for k in range(3, 22, 2):
            if rng.random() < 0.25:
                continue
            off = int(rng.integers(-1 - k // 8, 2 + k // 8))
            cv.hline(lx + off, lx + off + 1 + int(rng.integers(0, 2)), SURF + k, RB.WARM_REF[1] if k < 10 else RB.WARM_REF[0])
    return cv.a


def water_near():
    """近处的水面（擦水滑行、落水后）：一条受月光的水线，下面越来越暗；一道道月光的横亮痕（近处长）、
    零星几条暖的倒影。"""
    P = Px(TW, 90)
    rng = np.random.default_rng(802)
    water_rows(P, 0, P.h - 1, .165, .105, rng, glint=2.4)
    P.fill(0, 0, TW - 1, 0, rl(.27, .02, 248))
    P.fill(0, 1, TW - 1, 2, rl(.20, None, 252))
    for _ in range(26):
        x, y = int(rng.integers(0, TW)), int(rng.integers(4, 40))
        P.fill(x, y, x + int(rng.integers(1, 3)), y, WARM_REF)
    return P.a


def spray():
    """擦水时往后溅的水花：一串串斜的亮点（月光照着，偏青银），只在 skid 用，飞得很快。"""
    P = Px(TW, 50)
    rng = np.random.default_rng(803)
    for i in range(22):
        x = int(i * TW / 22 + rng.integers(0, 30))
        y = int(rng.integers(16, 44))
        ln = int(rng.integers(6, 16))
        for k in range(ln):
            c = rl(.40, .02, 246) if k < ln - 3 else rl(.30, .025, 250)
            px, py = x + k * 2, y - k // 2
            P.put(px, py, c)
            if k % 3 == 0:
                P.put(px, py + 1, rl(.27, .025, 250))
    return P.a


def channel_layers():
    """落水卡进窄水道：就是河流篇开场河岸（tools/river_bank_moon_art.py，镜头在最左边时）那一屏——
    中景一排高脚屋、几根中景石柱（bank_mid），近处左边那根一直下到水里的大石柱、卵石滩、垂枝树、第一间小屋（bank_main）。
    两张都裁 0..528（多 48 给镜头抖），不 tile、不卷动（船卡住了）。"""
    mid = RB.bank_mid().a[:, :SW + SKY_PAD]
    main = RB.bank_main().a[:, :SW + SKY_PAD].copy()
    main[RB.WL + 1:] = 0                                            # 水下那截（旧一层的地板）交给 water_near 盖住
    return mid, main


def crate():
    """漂着的木箱：画里少有的暖色（但不亮），月光照着顶面和右边；下面几行泡在水里。"""
    w, h = 22, 18
    P = Px(w, h, tile=False)
    WOOD, LIT, SH_, LINE = col(.25, .035, 62), col(.32, .03, 75), col(.19, .03, 55), col(.17, .028, 52)
    P.fill(0, 0, w - 1, h - 1, WOOD)
    P.fill(0, 0, w - 1, 0, LIT)
    P.fill(w - 2, 0, w - 1, h - 1, rl(.26, .02, 246))
    P.fill(0, 0, 0, h - 1, SH_)
    for y in (5, 10):
        P.fill(1, y, w - 3, y, LINE)
    for k in range(w - 6):
        P.put(2 + k, 2 + k * (h - 9) / (w - 6), LINE)
    for x in (3, w - 5):
        P.put(x, 2, col(.15, .01, 60))
    wet = np.zeros((h, w), bool)
    wet[h - 5:] = True
    wl = rgb2lab(P.a[wet][:, :3])
    P.a[wet, :3] = lab2rgb(wl * 0.6 + rgb2lab(np.array(rl(.15, None, 252)[:3]))[None] * 0.4)
    P.fill(0, h - 5, w - 1, h - 5, rl(.28, .02, 248))               # 吃水线
    return P.a


def river_row():
    """起飞离开河流星（原文 152「飞机升高，河岸的屋子缩小成一排挨着水的色块」）：一排小屋子，每栋只是一块颜色
    （月光下的蓝灰、旧白、褪色的红和绿，压得很暗），屋顶一道受月光的亮边，零星几扇暖黄的窗；之间有空，
    中间立着一两尊石像。底下一条水，暖窗在水里拉成竖的亮痕。妮芙家那块（x≈300）比旁边的高一点、窗都亮。"""
    P = Px(TW, 70)
    rng = np.random.default_rng(1501)
    SURF = 50
    tones = [rl(.17, .02, 252), rl(.20, .015, 240), rl(.16, .025, 262), col(.17, .025, 30), col(.17, .02, 160),
             col(.20, .015, 85), rl(.15, .02, 256)]
    x = 2
    while x < TW - 12:
        w = int(rng.integers(8, 18))
        top = SURF - int(rng.integers(8, 20))
        niff = 290 <= x <= 312
        if niff:
            top = SURF - 26
        c = tones[int(rng.integers(0, len(tones)))]
        P.fill(x, top, x + w - 1, SURF, c)
        P.fill(x, top, x + w - 1, top, rl(.28, .02, 246))
        P.fill(x + w - 1, top, x + w - 1, SURF, tuple(int(v) for v in CA.mix(tuple(c[:3]), tuple(rl(.3, .02, 246)[:3]), .3)))
        for wy in range(top + 3, SURF - 2, 5):
            for wx in range(x + 2, x + w - 3, 4):
                lit = rng.random() < 0.3 or niff
                P.fill(wx, wy, wx + 1, wy + 1, WARM if lit else DARK_WIN)
        x += w + int(rng.integers(2, 7))
        if rng.random() < 0.12:
            statue(P, x + 3, SURF, int(rng.integers(12, 18)), rng, kind="robe")
            x += 9
    rest = P.a[SURF + 1:, :, 3] == 0
    P.a[SURF + 1:][rest] = 0
    reflect_down(P, SURF + 1, P.h - SURF - 2, rng, rl(.17, None, 252), gaps=0.4)
    W2 = Px(TW, P.h)
    water_rows(W2, SURF + 1, P.h - 1, .18, .14, rng, glint=1.5)
    under = (P.a[..., 3] == 0) & (np.arange(P.h)[:, None] > SURF)
    P.a[under] = W2.a[under]
    P.fill(0, SURF + 1, TW - 1, SURF + 1, rl(.25, .02, 248))
    return P.a


# ---- 躲碎石时船外飞过的碎石小图（art/cockpit/debris_*.png；只有 --debris 才重写）
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


# ============================================================ sky.json
BG = {
    # 起飞几段：整屏都被 forest_bg（关卡的雾带 + 往上接的天）盖住，底色只在它上沿露出来 → 用它最上面那档的颜色
    "forest": [F_BG, F_BG],
    # 云海以后每段都有一张整屏的天（cloud_sky / stars / river_sky，比屏幕每边大 48）盖住引擎画的 10 条底色带；
    # 底色只在换状态、两张天交叉淡入淡出的那一下透出来一点 → 取和那几张天上下两端差不多的颜色
    "clouds": ["#0b1517", "#1d2b2a"],
    "debris": ["#0b1517", "#1d2b2a"],
    "space": ["#070d0e", "#0d1515"],
    "void": ["#040707", "#060a0a"],
    "city": ["#0f1626", "#1b2433"],
    "channel": ["#0f1626", "#1b2433"],
}

P = -SKY_PAD          # 整屏的天：左上角在 (-48, -48)

LAYERS = {   # 从后往前（draw order）
    "forest_bg": {"img": "forest_bg.png", "tile": True},
    "stars": {"img": "stars.png"},
    "cloud_sky": {"img": "cloud_sky.png"},
    "river_sky": {"img": "river_sky.png"},
    "void": {"img": "void.png"},
    "star_pts": {"img": "star_pts.png", "tile": True},
    "star_mid": {"img": "star_mid.png", "tile": True},
    "star_long": {"img": "star_long.png", "tile": True},
    "planet_s": {"img": "planet_s.png"},
    "planet_m": {"img": "planet_m.png"},
    "cloud_high": {"img": "cloud_high.png", "tile": True},
    "forest_ridge": {"img": "forest_ridge.png", "tile": True},
    "forest_far": {"img": "forest_far.png", "tile": True},
    "forest_midfar": {"img": "forest_midfar.png", "tile": True},
    "forest_mid": {"img": "forest_mid.png", "tile": True},
    "forest_main": {"img": "forest_main.png", "tile": True},
    "cloud_far": {"img": "cloud_far.png", "tile": True},
    "cloud_midfar": {"img": "cloud_midfar.png", "tile": True},
    "debris_belt": {"img": "debris_belt.png", "tile": True},
    "cloud_mid": {"img": "cloud_mid.png", "tile": True},
    "cloud_deck": {"img": "cloud_deck.png", "tile": True},
    "ground": {"img": "ground.png", "tile": True},
    "moon_glint": {"img": "moon_glint.png"},
    "river_ridge": {"img": "river_ridge.png", "tile": True},
    "river_mist": {"img": "river_mist.png", "tile": True},
    "river_shore": {"img": "river_shore.png", "tile": True},
    "city_far": {"img": "city_far.png", "tile": True},
    "clocktower": {"img": "clocktower.png"},
    "city_mid": {"img": "city_mid.png", "tile": True},
    "canal": {"img": "canal.png", "tile": True},
    "channel_mid": {"img": "channel_mid.png"},
    "channel_bank": {"img": "channel_bank.png"},
    "water_near": {"img": "water_near.png", "tile": True},
    "crate": {"img": "crate.png"},
    "river_row": {"img": "river_row.png", "tile": True},
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


# 云海：作者场景里各层的 y 就是图的 y（地平线 141）。sink = 整片云海比作者的构图低多少（往上爬 = 云海往下沉）。
# 横向速度按作者场景各层的 scroll_scale（far .08 / midfar .18 / mid .36 / near .6），v = 主层（最近那层）的速度。
CL_SCROLL = {"cloud_high": .03, "cloud_far": .08, "cloud_midfar": .18, "cloud_mid": .36, "cloud_deck": .6}
CL_SINK = {"cloud_sky": .0, "cloud_high": .15, "cloud_far": .45, "cloud_midfar": .6, "cloud_mid": .8, "cloud_deck": 1.0}
DECK_Y = 196           # 停在云海上时 cloud_deck 的团顶在屏幕上的高度（和作者 near 那排差不多）


def clouds_at(sink, v, alpha=None, drop=(), deck=True):
    """云海各层的关键帧：比作者构图低 sink 像素、主层横向 v 像素/秒。"""
    out = []
    for k, f in CL_SINK.items():
        if k in drop or (k == "cloud_deck" and not deck):
            continue
        if k == "cloud_sky":
            out.append(S(k, P + round(sink * f), 0, 0, x=P))
        elif k == "cloud_high":
            out.append(S(k, HIGH_Y + round(sink * f), round(v * CL_SCROLL[k], 2), 0))
        elif k == "cloud_deck":
            out.append(S(k, DECK_Y - DECK_TOP + round(sink * f), round(v * CL_SCROLL[k], 2), 0))
        else:
            out.append(S(k, round(sink * f), round(v * CL_SCROLL[k], 2), 0))
    if alpha:
        out = [dict(e, alpha=alpha.get(e["id"], 1.0)) if e["id"] in alpha else e for e in out]
    return out


HIGH_Y = 0             # build() 里按 cloud_high 裁掉的行数填


# 河流星：作者河岸场景里 HORIZON = 150（天、远岸石柱、雾、近岸怪树都按这个对齐）；降落时视线一直平着，地平线不动，
# 近处的东西（小镇、钟楼、水道、水面）从画面下面升上来 = 往下降。
def river_back(alpha=1.0, mist=True, shore=True):
    out = [S("river_sky", P, 0, 0, alpha, x=P), S("ground", 151, 2, 0, alpha), S("moon_glint", 155, 0, 0, alpha, x=0),
           S("river_ridge", 0, 1, 0, alpha)]
    if mist:
        out.append(S("river_mist", 0, 3, 0, alpha))
    if shore:
        out.append(S("river_shore", 0, 4, 0, alpha))
    return out


def states():
    st = {}
    # ---------- 起飞：就是森林关卡那片林子（forest_layers），镜头一路往上升，各层往下沉（近的沉得快）
    # forest_canopy：刚离地，还在树干之间：上面是林冠的黑，船底下是关卡里那条雾带，地面刚沉到画面下沿
    st["forest_canopy"] = {"blend": 1.0, "bg": BG["forest"], "layers": forest_at(40, 10, 8)}
    # canopy_fall：穿过林冠，近处大树的枝一层层从窗边掉下去。停在这一段的时间看对白长短（7～20 秒），
    # 爬升 8 像素/秒：停 20 秒也到不了 forest_below 的高度，不会倒回去
    st["canopy_fall"] = {"blend": 1.0, "bg": BG["forest"], "layers": forest_at(190, 14, 8)}
    # forest_below：出了林冠，主层的树尖沉到画面下沿以下，远处几层的树梢在船底下；
    # 天上的高云条淡入、跟着往下压（往上爬的感觉）；云层的云底在画面上面（还没露头）
    st["forest_below"] = {"blend": 1.5, "bg": BG["forest"], "layers": [
        *forest_at(380, 20, 6)[:1], S("cloud_high", HIGH_Y - 90, 2, 6, 0.5), *forest_at(380, 20, 6)[1:],
        S("cloud_deck", -DECK_H - 20, 10, 0)]}
    st["forest_far"] = {"blend": 1.2, "bg": BG["forest"], "layers": [
        *forest_at(470, 24, 6, drop=("forest_main",))[:1], S("cloud_high", HIGH_Y - 60, 3, 8, 0.75),
        *forest_at(470, 24, 6, drop=("forest_main",))[1:], S("cloud_deck", -DECK_H + 20, 10, 4)]}
    # turning：转向巡航，横向一下快起来；森林只剩画面下沿的远处树梢；云层垂下来的云底从上面压下来
    st["turning"] = {"blend": 1.0, "bg": BG["forest"], "layers": [
        *forest_at(560, 40, 8, drop=("forest_main",))[:1], S("cloud_high", HIGH_Y - 30, 8, 6),
        *forest_at(560, 40, 8, drop=("forest_main",))[1:], S("cloud_deck", -DECK_H + 90, 18, 10),
        S("wisps", -150, 40, 0)]}
    # clouds：云层整块扫过船（一团团菜花往下掠），变成脚下的云海；后面露出作者云海场景的天和远中近三层云海。
    # 森林的天（forest_bg）不列 → 4 档淡出（被扫过来的云层盖着）；最远两层树梢沉出画面
    st["clouds"] = {"blend": 1.8, "bg": BG["clouds"], "layers": [
        *clouds_at(0, 46)[:2], *forest_at(900, 48, 0, drop=("forest_bg", "forest_midfar", "forest_mid", "forest_main")),
        *clouds_at(0, 46)[2:], S("wisps", 0, 46, 0)]}
    # debris_wall：云海上方远处，一条碎石带横在航线上；前面零星几块中号碎石漂过。云海略沉（再爬高一点）
    st["debris_wall"] = {"blend": 2.5, "bg": BG["debris"], "layers": [
        *clouds_at(10, 30)[:4], S("debris_belt", 30, 5, 0), *clouds_at(10, 30)[4:],
        S("debris_near", 0, 20, 0), S("wisps", 0, 30, 0, 0.5)]}
    # clouds_fast：烧完纪念品加速；远处河流星球第一次露头（很小、半透，在余晖那边）
    st["clouds_fast"] = {"blend": 1.5, "bg": BG["clouds"], "layers": [
        *clouds_at(4, 90)[:1], S("planet_s", 92, 0, 0, 0.5, x=34), *clouds_at(4, 90)[1:],
        S("wisps", 0, 150, 0), S("streaks", 0, 260, 0)]}
    # ---------- 飞行一结尾（10-30 作者：「往前一冲，冲入黑色的星空，场景渐暗，第一章就结束了」；降落河流星挪到河流篇开头）。
    # cockpit_dash.gd 按顺序设这三个状态：
    # starfield：往上爬出云海——云海整片往下沉、淡掉，天换成黑色星空，星点慢慢往右走
    st["starfield"] = {"blend": 2.6, "bg": BG["void"], "layers": [
        S("void", P, 0, 0, x=P), S("star_pts", P, 8, 0),
        *clouds_at(330, 30, drop=("cloud_sky",), alpha={k: 0.0 for k in CL_SINK})]}
    # dash_go → dash：往前一冲——星点先拉成短线（dash_go），再拉成长线（dash），横向速度一路平滑涨到很快（先缓后急）
    st["dash_go"] = {"blend": 0.8, "bg": BG["void"], "layers": [
        S("void", P, 0, 0, x=P), S("star_mid", P, 150, 0)]}
    st["dash"] = {"blend": 1.0, "bg": BG["void"], "layers": [
        S("void", P, 0, 0, x=P), S("star_long", P, 1300, 0)]}
    # dash_end：冲出去以后收住——长线缩回星点、速度慢下来（船已经冲出画面，只剩黑色星空），接着整屏渐暗
    st["dash_end"] = {"blend": 1.6, "bg": BG["void"], "layers": [
        S("void", P, 0, 0, x=P), S("star_pts", P, 14, 0)]}
    # ---------- 到站（河流篇开头用；飞行一结尾不再降落）：云海沉下去，天换成星空，星球从小换成中
    st["river_planet"] = {"blend": 2.0, "bg": BG["space"], "layers": [
        S("stars", P, 0, 0, x=P), S("planet_s", 92, 0, 0, 0.0, x=34), S("planet_m", 64, 0, 0, x=16),
        *clouds_at(300, 30, drop=("cloud_sky", "cloud_high")), S("wisps", 160, 60, 0, 0.0)]}
    # river_city：进了河流星的夜：作者河岸的天（满月）淡入盖住星空，远岸的石柱、雾、怪树，地平线下一大片河面，
    # 月亮在水里碎成一道亮纹；远处一排小镇贴着水。星球淡出。
    st["river_city"] = {"blend": 2.0, "bg": BG["city"], "layers": [
        S("stars", P, 0, 0, 0.25, x=P), *river_back()[:1], S("planet_m", 40, 0, 0, 0.0, x=16), *river_back()[1:],
        S("city_far", 122, 4, -0.6), S("clocktower", 270, 0, 0, 0.0, x=88), S("city_mid", 290, 8, 0)]}
    # clocktower：水上小镇升上来，钟楼在机头前面（从窗里也看得到它亮着的钟面）
    st["clocktower"] = {"blend": 1.5, "bg": BG["city"], "layers": [
        *river_back(), S("city_far", 112, 5, -1), S("clocktower", 40, 0, -1, x=88),
        S("city_mid", 96, 10, -1)]}
    # boats：再低一点，停着小船的宽水道升到船下，小镇在它后面
    st["boats"] = {"blend": 1.5, "bg": BG["city"], "layers": [
        *river_back(), S("city_far", 104, 6, -1), S("clocktower", 2, 0, -1, x=88),
        S("city_mid", 60, 14, -1), S("canal", 186, 20, -1)]}
    # tilt：一歪，水道猛地近了
    st["tilt"] = {"blend": 0.6, "bg": BG["city"], "layers": [
        *river_back(shore=False), S("city_far", 98, 8, 0), S("clocktower", -18, 0, 0, x=88),
        S("city_mid", 44, 22, 0), S("canal", 164, 40, 0)]}
    # skid：擦着水面滑：水面到了船腰，小船一排排往后掠，水花往后溅
    st["skid"] = {"blend": 0.8, "bg": BG["city"], "layers": [
        *river_back(shore=False), S("city_far", 94, 10, 0), S("clocktower", -30, 0, 0, x=88),
        S("city_mid", 36, 30, 0), S("canal", 146, 120, 0), S("water_near", 190, 170, 0),
        S("spray", 158, 230, 0)]}
    # ---------- 落水：漂进窄水道，卡在一根下到水里的大石柱边上——就是河流篇开场河岸那一屏（同一根石柱、同一排高脚屋）。
    # 整个画面比降落时低 22（河岸房间的水面在 218，这里 196，船浮在水里）；船卡住了，都不卷动
    D = -22
    bank = [S("river_sky", P + D, 0, 0, x=P), S("moon_glint", 155 + D, 0, 0, x=0), S("river_ridge", D, 0, 0),
            S("river_mist", D, 2, 0), S("river_shore", D, 0, 0), S("channel_mid", D, 0, 0, x=0),
            S("channel_bank", D, 0, 0, x=0)]
    st["channel"] = {"blend": 1.0, "bg": BG["channel"], "layers": [*bank, S("water_near", 218 + D, 3, 0)]}
    st["crate"] = {"blend": 1.2, "bg": BG["channel"], "layers": [
        *bank, S("water_near", 218 + D, 2, 0), S("crate", 218 + D - 13, 0, 0, x=46)]}
    # ---------- 第二章结尾：从河岸起飞（原文 152）。河岸的屋子缩成一排挨着水的色块，慢慢沉下去；远处小镇在后面也沉
    st["river_leave"] = {"blend": 2.0, "bg": BG["city"], "layers": [
        S("river_sky", P, 0, 0, x=P), S("ground", 151, 2, 3), S("moon_glint", 155, 0, 3, x=0), S("river_ridge", 0, 1, 3),
        S("river_mist", 0, 3, 3), S("city_far", 140, 3, 5), S("river_row", 192, 6, 7)]}
    return st


ORDER = ["forest_canopy", "canopy_fall", "forest_below", "forest_far", "turning", "clouds", "debris_wall",
         "clouds_fast", "starfield", "dash_go", "dash", "dash_end", "river_planet", "river_city", "clocktower", "boats", "tilt", "skid", "channel", "crate",
         "river_leave"]


def build(only=None, debris=False):
    """only = 只写这几张图（加上 sky.json 总是重写）。debris = 也重写 art/cockpit/debris_*.png（躲碎石的碎石小图，
    不在 sky/ 里；平时不碰，免得盖掉别人改过的）。"""
    global HIGH_Y
    high, HIGH_Y = cloud_high()
    arrs = {
        "cloud_sky": cloud_sky_full(), "cloud_high": high,
        "cloud_far": cloud_sea("far"), "cloud_midfar": cloud_sea("midfar"), "cloud_mid": cloud_sea("mid"),
        "cloud_deck": cloud_deck(), "wisps": wisps(), "streaks": streaks().a,
        "debris_belt": debris_belt().a, "debris_near": debris_near().a, "stars": space_sky(),
        "void": void_sky(), "star_pts": star_layer(0), "star_mid": star_layer(6), "star_long": star_layer(26),
        "river_sky": river_sky(), "river_ridge": river_layer("ridge"), "river_mist": river_layer("mist"),
        "river_shore": river_layer("shore"), "moon_glint": moon_glint(),
        "ground": ground(), "city_far": city_far(), "city_mid": city_mid(), "clocktower": clocktower(),
        "canal": canal(), "water_near": water_near(), "spray": spray(),
        "crate": crate(), "river_row": river_row(),
    }
    arrs["channel_mid"], arrs["channel_bank"] = channel_layers()
    arrs.update(forest_layers())
    arrs["planet_s"] = planet(20, 451, rivers=False)
    arrs["planet_m"] = planet(56, 452)
    OUT.mkdir(parents=True, exist_ok=True)
    for k, a in arrs.items():
        assert (a[..., 3] == 0).sum() + (a[..., 3] == 255).sum() == a[..., 3].size, k   # 只有全透 / 全不透
        if LAYERS[k].get("tile"):
            assert a.shape[1] >= SW, k
        if only is None or k in only:
            Image.fromarray(a, "RGBA").save(OUT / f"{k}.png")
    if debris:
        for n, a in debris_sprites().items():
            Image.fromarray(a, "RGBA").save(DEBRIS_OUT / f"{n}.png")
    st = states()
    for s in ORDER:
        assert s in st, s
        for e in st[s]["layers"]:
            assert e["id"] in LAYERS, (s, e["id"])
    doc = {
        "_note": "tools/sky_art.py 生成，别手改。约定见 docs/flight_sky_contract.md。顶层 layers 的顺序就是从后往前的画的顺序；"
                 "每个状态里的层也按这个顺序列。不 tile 的图（整屏的天 stars / cloud_sky / river_sky、planet_s/m、moon_glint、"
                 "clocktower、channel_mid / channel_bank、crate）用 x 定位，x 在用到它的各状态里不变，只改 y / alpha，所以引擎插不插值 x 都一样。",
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
    ap.add_argument("--only", default=None, help="只写这几张图（逗号分开，sky.json 总是重写），比如 --only=city_far,city_mid")
    ap.add_argument("--debris", action="store_true", help="也重写 art/cockpit/debris_*.png（平时不碰）")
    args = ap.parse_args()
    arrs, doc = build(args.only.split(",") if args.only else None, args.debris)
    if args.preview:
        preview(args.preview, arrs, doc)
