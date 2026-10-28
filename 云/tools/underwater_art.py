"""水星 · 水底视差（晨从河岸潜下去以后）。以后改水底的图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/underwater_art.py [--preview 目录]

输出 art/underwater/*.png（1 倍）。

画面：同一个夜、同一个月亮（屏幕 x≈338，和河岸一样在右上），只是现在在水下往上看：
最上面是水面的「天花板」，月亮在里面碎成一团晃动的亮斑（surface 层，Godot 里闪）；从它往左下斜着散开几道
月光光柱（Godot 里的 shader 画，整像素、分档抖动）。越往下水越暗，河床几乎是黑的。
远处是河岸那排石柱沉在水里的脚和一片片远的巨藻林（往水色里褪得很厉害，只剩剪影，朝月亮那条边亮一档），
一道塌了一半的天然石拱；再远（distant 层）是一片几乎看不见的巨藻林和第二座更小更淡的沉没雕像（一个仰头望月的胸像），
一头很大的鲸慢慢从上面游过（whale.png 存的是「乘多少」，Godot 里乘法混合，只把水压暗一两成），
左上那片空水里还有一群小鱼在兜圈（scripts/underwater_school.gd）。中景一颗巨大的石头头像竖着埋到脖子，脸朝右、微微仰着望向水面上的月亮，
侧脸（额头、眉骨、闭着的眼、鼻梁、嘴唇、下巴）朝光那一圈亮、后脑沉进暗里；头上箍着一道和晨一样的头环，
头环额前的凹槽里卡着一颗从岸上掉下来的发光果荚（全画面最显眼的那一点暖色，Godot 里呼吸）。
光柱正好落在它额头上：这是第一眼的焦点，和晨（屏幕 x≈204）隔开八十多像素，晨面朝它。
同一层的另一半，一个巨大的石环竖着半埋在沙里。
再近一点是一丛丛很高的巨藻和带状长水草（kelp 层，Godot 里按行摆）；晨走的是河床：顶上一条被焦散照亮的细沙线，
几块大圆石、一截横躺的石柱段、螺壳、一丛丛矮水草，下面很快沉进黑泥。最前景是几片近黑的大叶子和圆石框住画面（也在摆）。

规则：480×270 屏幕，1 倍像素，alpha 只有 0/255，不描边；光从水面上方（偏右，月亮）来。
水星的身份色是蓝：暗部往靛蓝走、亮部往青银走（OKLCh 色相约 222~275，跨度 ~50°；不偏绿、不偏紫）。
背景最亮（水面里的月亮）L≈0.62，明显低于晨（身体 L 中位数 0.63、亮部 0.8）。
晨身后那条（地面往上 ~45 像素，y 181~226）是很暗的深水，只有远处剪影，没有杂点。
除了 deep / surface（屏幕固定，480 宽），每层宽 960、左右无缝，Godot 里用 Parallax2D 横向重复。
会摆的层（kelp、bedweeds、front、headweeds）：贴图最下面一行就是根，shader 按「离底多高」左右错整像素。
所有随机都固定 seed。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from oscarkit.palette import from_lch, oklab_to_srgb, to_lab  # noqa: E402
from river_art import _walk, components, keep_attached, pillar_mask, shade_rock, smooth1d  # noqa: E402

W, H = 960, 270
SW = 480
GROUND = 226             # 河床（主层地面）平均高度，和 scripts/underwater_test.gd 一样
MX, MY = 338, 7          # 水面里的月亮（屏幕坐标），和河岸的月亮同一个 x
CEIL = 22                # 水面「天花板」往下化进水里的那一行
OUT = Path(__file__).resolve().parents[1] / "art" / "underwater"

# 层名 -> 跟镜头的比例（Godot 场景里的 scroll_scale 照这个填）
SCROLL = {"deep": 0.0, "surface": 0.0, "distant": 0.05, "far": 0.08, "midfar": 0.17, "head": 0.3, "headweeds": 0.3,
          "kelp": 0.52, "main": 1.0, "bedweeds": 1.0, "front": 1.4}
# 会摆的贴图贴在层坐标的哪一行（贴图顶边）；贴图最下面一行 = 根
SURF_H = 26
KELP_Y, KELP_H = 20, 202          # kelp.png：y 20..221，根在 221（被河床挡住）
BED_Y, BED_H = 196, 33            # bedweeds.png：y 196..228，根在河床里
FRONT_Y, FRONT_H = 40, 230        # front.png：y 40..269
HEAD_X, HEAD_BASE = 345, 214      # 头像（head 层坐标）：中线 x、沙面那一行
RING_X = 790                      # 石环（head 层坐标）
POD_X = 612                       # 河床上那颗发光果荚（主层 x）
HEADLIGHT = None
HW_Y, HW_H = 182, 40               # headweeds.png：head 层 y 182..221，根在沙丘里

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16


# ---------------------------------------------------------------- 颜色（和河岸同一套：暗偏靛、亮偏青银）

def hue_shift(L):
    t = float(np.clip((L - 0.06) / 0.44, 0, 1))
    t = t * t * (3 - 2 * t)
    return 17.0 - 43.0 * t


def lch(L, C=None, h=254.0):
    if C is None:
        C = 0.024 + 0.075 * min(L, 0.42)
    return tuple(int(v) for v in from_lch(float(L), float(C), float(h) + hue_shift(float(L))))


def bramp(n, L0, L1, h_dark=258.0, h_lit=248.0, C0=None, C1=None):
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        C = None if C0 is None else C0 + ((C1 if C1 is not None else C0) - C0) * t
        out.append(lch(L0 + (L1 - L0) * t, C, h_dark + (h_lit - h_dark) * t))
    return out


def mix(c, d, t):
    a, b = to_lab(c), to_lab(d)
    return tuple(int(v) for v in oklab_to_srgb((a + (b - a) * t)[None])[0])


def rgba(c):
    return tuple(int(v) for v in c) + (255,)


class Layer:
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


# ---------------------------------------------------------------- 水的底色（随深度 + 月光）

WATER_L = [(0, .33), (6, .315), (14, .292), (22, .27), (34, .25), (52, .228), (80, .203), (115, .178),
           (150, .152), (185, .122), (210, .108), (226, .1), (270, .09)]
WATER_H = 254.0
L_STEP = 0.016


def base_L(y):
    ys, ls = zip(*WATER_L)
    return float(np.interp(y, ys, ls))


def glow(x, y):
    """月光把水提亮多少。水面那几行（天花板）亮斑压扁；往下是一大团很淡的、跟着光柱往左下斜的光。"""
    x = np.asarray(x, float)
    d = np.hypot(x - MX, (y - MY) * 2.4)
    g = 0.2 * np.exp(-(d / 18) ** 2) + 0.09 * np.exp(-(d / 60) ** 2) + 0.045 * np.exp(-(d / 180) ** 2)
    # 光柱扫过的那一大片（往左下斜，越深越淡）：Godot 里的光柱叠在它上面
    cx = MX + 30 - 0.36 * (y + 60)
    g = g + 0.075 * np.exp(-((x - cx) / (60 + 0.3 * y)) ** 2) * np.exp(-y / 150)
    return g


def bg_L(x, y):
    return base_L(y) + glow(x, y)


def L_color(L, h=WATER_H):
    return lch(L, None, h)


def quant_L(L):
    return np.round(np.asarray(L) / L_STEP) * L_STEP


def vnoise(h, w, cy, cx, rng):
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


def deep():
    """屏幕固定的底：水的颜色（上亮下暗，Bayer 一档档抖动）+ 水面天花板（几条压扁的波纹带，月亮附近亮）
    + 水面里的月亮本体（一团压扁、边缘破碎的亮斑；最亮的碎光在 surface 层里闪）。"""
    lay = Layer(SW, H)
    xs = np.arange(SW)
    rng = np.random.default_rng(2)
    wave = vnoise(CEIL + 4, SW, 2.2, 15, rng)
    cache = {}
    for y in range(H):
        L = bg_L(xs, y)
        if y < CEIL:
            # 天花板：横着拉长的波纹，越往下（越远）越细、越淡
            f = 1 - y / CEIL
            near = np.exp(-((xs - MX) / 110) ** 2)
            L = L + (0.012 + 0.05 * near) * f * (wave[y] - 0.45) * 2.2 + 0.012 * f
        lo = np.floor(L / L_STEP)
        idx = lo + (BAYER[y % 4, xs % 4] < (L / L_STEP - lo))
        for x in range(SW):
            k = int(idx[x])
            if k not in cache:
                cache[k] = rgba(L_color(k * L_STEP))
            lay.a[y, x] = cache[k]
    # 月亮：水面下看上去是压扁的一团，边缘被波纹啃得参差
    core, body, rim = lch(.6, .022, 246), lch(.54, .028, 247), lch(.45, .034, 250)
    edge = smooth1d(SW, rng, 5, 1.0)
    for y in range(0, 16):
        for x in range(MX - 24, MX + 25):
            dx, dy = (x - MX) / 18.0, (y - MY) / 5.6
            r = np.hypot(dx, dy) + 0.12 * edge[x] + 0.07 * np.sin(y * 2.1 + x * 0.3)
            if r < 0.5:
                lay.a[y, x] = rgba(core)
            elif r < 0.8:
                lay.a[y, x] = rgba(body)
            elif r < 1.0:
                lay.a[y, x] = rgba(rim)
    return lay


def surface():
    """水面里会闪的碎光：480×SURF_H，屏幕固定贴在 y=0。R = 亮度档、G = 闪烁相位、B = 闪烁快慢
    （和河岸 glints 一样的编码，Godot 的 underwater_surface.gdshader 查色、每行左右晃）。
    月亮那一团里又密又亮；往两边是很稀、很暗的一小段一小段（天花板上的波纹反光）。"""
    rng = np.random.default_rng(31)
    img = np.zeros((SURF_H, SW, 4), np.uint8)
    for r in range(SURF_H):
        d = r / (SURF_H - 1)
        x = rng.uniform(0, 4)
        while x < SW:
            ln = 2 + int(rng.integers(0, 3 + int(8 * (1 - d))))
            u = (x + ln / 2 - MX) / (22 + 30 * d)
            in_moon = abs(u) < 0.85 and abs(r - MY) < 6
            tone = 0.95 - 0.5 * min(1.0, abs(u)) - 0.35 * d + rng.normal(0, 0.08)
            if in_moon:
                tone = max(tone, 0.9)
            p = (0.85 if in_moon else 0.5 * np.exp(-u * u / 6) + 0.07) * (1 - 0.6 * d)
            if tone > 0.02 and rng.random() < p:
                ph, sp = rng.integers(0, 256), rng.integers(0, 256)
                for k in range(ln):
                    xi = int(round(x)) + k
                    if 0 <= xi < SW:
                        img[r, xi] = (int(np.clip(tone, 0, 1) * 255), ph, sp, 255)
            x += ln + 1 + int(rng.integers(0, 3 + int(14 * min(1.0, abs(u) / 3))))
        if r > 10 and r % 2:
            img[r] = 0                       # 越远越稀：隔行
    return img


SURF_PAL = [(.36, .035, 250), (.45, .034, 248), (.54, .03, 246), (.63, .022, 244)]


# ---------------------------------------------------------------- 往水里褪

_MIX = {}


def fade(lay, t_of_y, steps=6, shift=0, x_t=None):
    """把每个像素往「同一高度的水色」推 t(y)（水下没有地平线，远处的东西只是被水吃掉）。
    t 按 1/steps 分档，两档之间 Bayer 抖动。shift：这一层在镜头 ≈240 时相对屏幕的偏移，用来对上月光。"""
    a = lay.a
    ww = a.shape[1]
    xs = np.arange(ww)
    for y in range(a.shape[0]):
        m = a[y, :, 3] > 0
        if not m.any():
            continue
        tc = np.clip(t_of_y(y) + (x_t(xs) if x_t else 0), 0, 1) * steps
        lo = np.floor(tc)
        tq = (lo + (BAYER[y % 4, xs % 4] < (tc - lo))) / steps
        sx = (xs - shift) % ww
        tgtL = quant_L(np.where(sx < SW, bg_L(np.minimum(sx, SW - 1), y), base_L(y)))
        for x in np.nonzero(m)[0]:
            t = float(tq[x])
            if t <= 0:
                continue
            src = tuple(int(v) for v in a[y, x, :3])
            key = (src, float(tgtL[x]), t)
            if key not in _MIX:
                _MIX[key] = mix(src, L_color(float(tgtL[x])), min(1.0, t))
            a[y, x, :3] = _MIX[key]


def drop_floating(lay, floor):
    """扔掉碰不到 floor 这一行的碎块（石柱的崩口、塌掉的拱会切出几个飞着的小块）。"""
    lab, n = components(lay.a[..., 3] > 0, wrap=True)
    for i in range(1, n + 1):
        yy, xx = np.nonzero(lab == i)
        if yy.max() < floor:
            lay.a[yy, xx] = 0


def rim_light(lay, pm, shift, gain, over, y0, y1):
    """月光从右上来：石头朝右、朝上的那条边（pm 里右边 / 上边挨着空的那一格）亮一档，
    越往上越亮（y0 以上满强度，到 y1 没了，晨身后那条不动）。最亮不超过同一高度的水 + over。
    右边再往里一格亮半档，让轮廓读得出来但不像描边。"""
    a = lay.a
    ww = a.shape[1]
    xs = np.arange(ww)
    vis = pm & (a[..., 3] > 0)
    right = vis & ~np.roll(pm, -1, axis=1)
    top = vis & ~np.roll(pm, 1, axis=0)
    right2 = vis & np.roll(right, -1, axis=1) & ~right & ~top
    for y in range(a.shape[0]):
        s = float(np.clip((y1 - y) / max(1, y1 - y0), 0, 1))
        if s <= 0:
            continue
        sx = (xs - shift) % ww
        wL = np.where(sx < SW, bg_L(np.minimum(sx, SW - 1), y), base_L(y))
        for mask, k in ((right, 1.0), (top, 0.8), (right2, 0.45)):
            for x in np.nonzero(mask[y])[0]:
                cur = float(to_lab(a[y, x, :3].astype(float)[None])[0, 0])
                L = min(cur + gain * s * k, float(wL[x]) + over * s)
                if L > cur + 0.004:
                    a[y, x, :3] = L_color(float(quant_L(L)))


def statue_mask():
    """远处第二座雕像：一个站着的人像，只露出胸口以上，头往后仰望着月亮（侧脸就是大头像那张脸缩小，
    头上也箍着那道头环的凸起）。肩膀往下斜，胸口往沙里收。整个人往左歪一点（沉下去的时候歪了），
    左肩崩掉一块。返回 bool[ih, iw]，最底一行 = 埋进沙里。"""
    sc = 0.3
    hp = np.array(HEAD_PTS, float) * sc
    ih, iw = 112, 76
    m = np.zeros((ih, iw), bool)
    ox, oy = 26, 4
    c = hp.mean(0)
    ca, sa = np.cos(HEAD_TILT - 0.12), np.sin(HEAD_TILT - 0.12)
    rp = hp - c
    rp = np.stack([rp[:, 0] * ca - rp[:, 1] * sa, rp[:, 0] * sa + rp[:, 1] * ca], -1) + c + (ox, oy)
    m |= poly_mask(rp, ih, iw)
    # 肩膀和胸口：从脖子往两边斜下去，右肩（朝月亮那边）略高；往下慢慢收进沙里
    nb = oy + 46
    body = [(ox - 16, nb + 12), (ox - 6, nb + 4), (ox + 6, nb), (ox + 22, nb), (ox + 34, nb + 5),
            (ox + 42, nb + 13), (ox + 43, nb + 26), (ox + 39, nb + 40), (ox + 40, ih), (ox - 14, ih),
            (ox - 16, nb + 40), (ox - 20, nb + 26)]
    m |= poly_mask(body, ih, iw)
    # 左肩崩掉一块
    m &= ~poly_mask([(ox - 22, nb + 6), (ox - 9, nb + 6), (ox - 12, nb + 13), (ox - 6, nb + 19), (ox - 22, nb + 24)],
                    ih, iw)
    # 整个往左歪
    out = np.zeros_like(m)
    for y in range(ih):
        dx = int(round((ih - 1 - y) * 0.08))
        if dx:
            out[y, :-dx] = m[y, dx:]
        else:
            out[y] = m[y]
    return out


def distant():
    """最远的一层（scroll 0.05，和大鱼同一层，在所有石柱后面）：一片褪得几乎看不见的巨藻林（很高，顶快到水面），
    和远处第二座更小更淡的沉没雕像。只比同一高度的水暗一两档，让深处有「还有更多」的感觉，又不抢头像。
    东西集中在左边那半（开场镜头左上那片空水），右边月亮、头像那块留空。"""
    lay = Layer()
    pal = bramp(5, .07, .15, 264, 252)
    rng = np.random.default_rng(141)
    base = 206
    img = np.zeros((H, W, 4), np.uint8)
    for cx, k, hmax in ((12, 3, 176), (58, 2, 140), (150, 3, 186), (196, 2, 120), (246, 2, 150),
                        (600, 2, 130), (690, 3, 170), (790, 2, 150), (890, 3, 180)):
        for i in range(k):
            giant_kelp(img, cx + rng.uniform(-10, 10), base, hmax * rng.uniform(0.6, 1.0), rng, pal)
    lay.paste(img, 0, 0)
    noise = smooth1d(W, rng, 120, 1.0)
    for x in range(W):
        top = int(round(199 + 3 * noise[x]))
        for y in range(top, H):
            lay.put(x, y, pal[1 if y == top else 0])
    fade(lay, lambda y: 0.8 + 0.14 * np.clip((y - 90) / 110, 0, 1), steps=10, shift=12)
    # 雕像比巨藻林近一点、褪得少一点（它是这一层里唯一要读得出形的东西）
    sl = Layer()
    m = statue_mask()
    st = shade_rock(m, np.random.default_rng(142), pal, cracks=(1, 2), seams=False)
    sl.paste(st, 108 - st.shape[1] // 2, base + 1 - st.shape[0])
    fade(sl, lambda y: 0.66 + 0.24 * np.clip((y - 120) / 80, 0, 1), steps=10, shift=12)
    pm = sl.a[..., 3] > 0
    rim_light(sl, pm, shift=12, gain=0.03, over=0.0, y0=100, y1=170)
    lay.paste(sl.a, 0, 0)
    return lay


# ---------------------------------------------------------------- 远处：沉在水里的石柱（河岸那排石柱的脚）

def far():
    """最远一排：石柱从看不见的深处长上来，顶在水里（有的断了顶），整片往水色里褪（剪影，顶上略深）。
    地面是一条很缓的远沙坡。"""
    lay = Layer()
    pal = bramp(4, .09, .17, 262, 252)
    rng = np.random.default_rng(71)
    cols = [(30, 26, 150, "tower", True), (118, 14, 104, "spire", False), (205, 34, 172, "twin", False),
            (300, 16, 120, "spire", True), (395, 22, 96, "hoodoo", False), (520, 40, 188, "tower", True),
            (604, 14, 112, "spire", False), (690, 28, 140, "stack", False), (802, 20, 118, "hoodoo", False),
            (880, 30, 160, "tower", False)]
    base = 206
    for i, (x, w, h, kind, brk) in enumerate(cols):
        m, top = pillar_mask(w, h, np.random.default_rng(500 + i), kind, brk)
        img = shade_rock(m, np.random.default_rng(600 + i), pal, cracks=(1, 3))
        lay.paste(img, x - img.shape[1] // 2, base + 1 - img.shape[0])
    pm = lay.a[..., 3] > 0
    for cx, k, hmax in ((90, 6, 120), (250, 4, 80), (430, 7, 140), (650, 5, 100), (760, 6, 150), (930, 4, 90)):
        img = np.zeros((H, W, 4), np.uint8)
        for i in range(k):
            ribbon(img, cx + rng.uniform(-14, 14), base, hmax * rng.uniform(0.4, 1.0), rng, pal, w0=rng.uniform(1.5, 2.6))
        lay.paste(img, 0, 0)
    noise = smooth1d(W, rng, 90, 1.0)
    for x in range(W):
        top = int(round(196 + 5 * noise[x]))
        for y in range(top, base + 2):
            lay.put(x, y, pal[1 if y == top else 0])
    drop_floating(lay, 200)
    fade(lay, lambda y: 0.56 + 0.32 * np.clip((y - 110) / 100, 0, 1), steps=8, shift=19)
    rim_light(lay, pm, shift=19, gain=0.075, over=0.03, y0=70, y1=178)
    return lay


def midfar():
    """近一点的一排：粗一些的石柱、一道塌了一半的天然石拱（光柱从拱里穿过去），褪得少一点。"""
    lay = Layer()
    pal = bramp(5, .075, .19, 262, 250)
    rng = np.random.default_rng(81)
    base = 212
    cols = [(70, 30, 128, "stack", False), (250, 22, 92, "spire", True), (430, 46, 176, "tower", True),
            (640, 34, 118, "hoodoo", False), (720, 18, 84, "spire", False), (905, 26, 140, "twin", True)]
    for i, (x, w, h, kind, brk) in enumerate(cols):
        m, top = pillar_mask(w, h, np.random.default_rng(700 + i), kind, brk)
        img = shade_rock(m, np.random.default_rng(800 + i), pal, cracks=(2, 4))
        lay.paste(img, x - img.shape[1] // 2, base + 1 - img.shape[0])
    # 石拱：两条腿 + 一道厚的弧，右腿断了一截（弧从断口垂下来）
    ax, ay, R0, R1 = 545, base - 70, 58, 74
    m = np.zeros((H, W), bool)
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.hypot((xx - ax) * 1.0, (yy - ay) * 1.15)
    edge = _walk(np.random.default_rng(3), 720, amp=1.0)
    ang = (np.degrees(np.arctan2(yy - ay, xx - ax)) % 360).astype(int)
    arc = (rr > R0 + 2.5 * edge[ang]) & (rr < R1 + 2.5 * edge[(ang + 200) % 720]) & (yy <= ay)
    arc &= ~((xx > ax + 30) & (yy < ay - 30) & (yy > ay - 52) & (xx - ax > 48 - (ay - yy) * 0.3))   # 右上塌掉一截
    m |= arc
    for lx, w in ((ax - 66, 18), (ax + 66, 16)):
        top = ay - 2 if lx < ax else ay + 8
        for y in range(top, base + 1):
            sw = w / 2 + 0.06 * (y - top)
            m[y, int(lx - sw):int(lx + sw)] = True
    ys, xs_ = np.nonzero(m)
    y0, x0 = ys.min(), xs_.min()
    sub = m[y0:base + 1, x0:xs_.max() + 1]
    img = shade_rock(sub, np.random.default_rng(9), pal, cracks=(3, 6))
    lay.paste(img, x0, y0)
    pm = lay.a[..., 3] > 0
    for cx, k, hmax in ((10, 5, 140), (150, 4, 96), (330, 6, 120), (600, 6, 160), (820, 5, 130)):
        img = np.zeros((H, W, 4), np.uint8)
        for i in range(k):
            ribbon(img, cx + rng.uniform(-12, 12), base, hmax * rng.uniform(0.4, 1.0), rng, pal, w0=rng.uniform(1.8, 3.0))
        lay.paste(img, 0, 0)
    noise = smooth1d(W, rng, 70, 1.0)
    for x in range(W):
        top = int(round(203 + 4 * noise[x]))
        for y in range(top, base + 3):
            lay.put(x, y, pal[1 if y == top else 0])
    drop_floating(lay, 205)
    fade(lay, lambda y: 0.44 + 0.3 * np.clip((y - 130) / 80, 0, 1), steps=8, shift=40)
    rim_light(lay, pm, shift=40, gain=0.058, over=0.014, y0=80, y1=172)
    return lay


# ---------------------------------------------------------------- 中景：沉睡的石头头像 + 掉下来的石环

def blur(a, sigma):
    """可分离的高斯模糊（没有 scipy）。"""
    r = int(3 * sigma) + 1
    k = np.exp(-(np.arange(-r, r + 1) / sigma) ** 2 / 2)
    k /= k.sum()
    p = np.pad(a.astype(float), r)
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 0, p)
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 1, p)
    return p[r:-r, r:-r]


def poly_mask(pts, h, w):
    """多边形填充（偶奇规则，按像素中心）。"""
    m = np.zeros((h, w), bool)
    pts = np.asarray(pts, float)
    n = len(pts)
    for y in range(h):
        yc = y + 0.5
        xs_ = []
        for i in range(n):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
            if (y0 <= yc < y1) or (y1 <= yc < y0):
                xs_.append(x0 + (yc - y0) / (y1 - y0) * (x1 - x0))
        xs_.sort()
        for a, b in zip(xs_[::2], xs_[1::2]):
            x0, x1 = max(0, int(np.ceil(a - 0.5))), min(w, int(np.floor(b - 0.5)) + 1)
            if x1 > x0:
                m[y, x0:x1] = True
    return m


LIGHT = np.array([0.5, -0.72, 0.48])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def relief(hf, mask, pal, ambient=0.12, gain=1.0, cuts=None, dither=0.0, rng=None):
    """高度场 -> 色阶：法线 = (-dh/dx, -dh/dy, 1)，光从右上偏前来（LIGHT），Lambert 按 cuts 分档
    （色块边就是等亮线，顺着形体走）。返回 int 档位数组（-1 = 空）。"""
    hy, hx = np.gradient(hf)
    n = np.stack([-hx, -hy, np.ones_like(hf)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    lam = np.clip((n * LIGHT).sum(-1), 0, 1) * gain + ambient
    if dither and rng is not None:
        lam = lam + (rng.random(lam.shape) - 0.5) * dither
    k = len(pal)
    if cuts is None:
        cuts = np.linspace(0.25, 1.05, k)[1:]
    idx = np.searchsorted(np.asarray(cuts), lam)
    idx = np.clip(idx, 0, k - 1)
    return np.where(mask, idx, -1), lam


def gbump(shape, cx, cy, sx, sy, amp, ang=0.0):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]].astype(float)
    ca, sa = np.cos(ang), np.sin(ang)
    u = (xx - cx) * ca + (yy - cy) * sa
    v = -(xx - cx) * sa + (yy - cy) * ca
    return amp * np.exp(-(u / sx) ** 2 - (v / sy) ** 2)


def line_bump(shape, pts, width, amp):
    """沿一条折线的脊（amp>0）或槽（amp<0），截面是高斯。"""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]].astype(float)
    d = np.full(shape, 1e9)
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        vx, vy = x1 - x0, y1 - y0
        L2 = vx * vx + vy * vy
        t = np.clip(((xx - x0) * vx + (yy - y0) * vy) / max(L2, 1e-9), 0, 1)
        d = np.minimum(d, np.hypot(xx - x0 - t * vx, yy - y0 - t * vy))
    return amp * np.exp(-(d / width) ** 2)


# 侧脸（脸朝右），不歪的坐标，y 朝下。从头顶顺时针：额头→眉骨→鼻根→鼻尖→人中→嘴唇→下巴→脖子→后脑。
HEAD_PTS = [(40, 0), (58, 2), (72, 8), (82, 18), (88, 30), (91, 40), (94, 47), (93, 51), (89, 55),
            (92, 60), (97, 68), (103, 76), (104, 79), (100, 81), (94, 82), (95, 86), (97, 88), (93, 90),
            (96, 93), (95, 96), (89, 99), (91, 103), (94, 108), (91, 114), (84, 117), (72, 118),
            (66, 124), (68, 175), (14, 175), (14, 118), (8, 104), (2, 86), (0, 66), (3, 44), (10, 26),
            (22, 10)]
HEAD_TILT = -0.28       # 弧度：往后仰，脸朝着右上的月亮


def stone_head():
    """沉睡的巨大石头头像：竖着埋到脖子，脸朝右、往后仰着望向水面上的月亮（侧脸的剪影一眼能认出来）。
    用高度场打光：整颗头先是一个圆鼓鼓的体（mask 模糊），再加眉骨、眼窝、闭着的眼睑、颧骨、鼻翼、嘴角、下颌线、
    耳朵（一圈凸起 + 中间凹）、头环（一条凸起的带，额前一个圆凹槽，果荚卡在里面）。光从右上来：
    额头、鼻梁、上唇、下巴朝着月亮的那一圈最亮，后脑沉进暗里。再加几道裂缝、崩掉的一块后脑。
    返回 (RGBA, 额前凹槽坐标, 每列顶边)。"""
    rng = np.random.default_rng(17)
    pad = 6
    pts = np.array(HEAD_PTS, float)
    c = pts.mean(0)
    ca, sa = np.cos(HEAD_TILT), np.sin(HEAD_TILT)

    def rot(p):
        p = np.asarray(p, float) - c
        return np.stack([p[..., 0] * ca - p[..., 1] * sa, p[..., 0] * sa + p[..., 1] * ca], -1)

    rp = rot(pts)
    off = -rp.min(0) + pad
    rp = rp + off

    def R(x, y):
        return tuple(rot(np.array([x, y], float)) + off)

    iw, ih = int(rp[:, 0].max()) + pad + 1, int(rp[:, 1].max()) + 1
    m = poly_mask(rp, ih, iw)
    # 后脑崩掉一块（不规则的缺口）
    m &= ~poly_mask([R(-4, 14), R(14, 13), R(19, 19), R(12, 27), R(16, 33), R(4, 38), R(-6, 36)], ih, iw)
    hf = blur(m.astype(float), 7.0) * 26
    hf += blur(m.astype(float), 2.2) * 5
    S = m.shape
    # 眉骨、眼窝、闭眼、颧骨
    hf += line_bump(S, [R(76, 44), R(86, 46), R(92, 48)], 2.0, 1.3)
    ex, ey = R(83, 54)
    hf += gbump(S, ex, ey, 6, 4, -3.2, HEAD_TILT)
    hf += line_bump(S, [R(77, 53), R(81, 55.5), R(86, 56), R(89, 55)], 0.9, 1.6)      # 闭着的上眼睑
    hf += line_bump(S, [R(78, 58), R(84, 59.5), R(88, 59)], 1.1, -1.2)                # 眼睑下的缝
    hf += gbump(S, *R(76, 68), 8, 5, 2.4, HEAD_TILT + 0.4)                             # 颧骨
    hf += line_bump(S, [R(94, 80), R(90, 78), R(88, 74)], 1.3, -1.6)                  # 鼻翼的沟
    hf += line_bump(S, [R(92, 90), R(86, 92)], 1.0, -1.6)                              # 嘴角
    hf += line_bump(S, [R(80, 116), R(68, 113), R(56, 104)], 2.4, 0.9)                # 下颌线（很淡）
    # 耳朵：一圈凸起的 C，中间凹
    ecx, ecy = R(40, 70)
    for t in np.linspace(-1.9, 1.9, 24):
        px, py = ecx - 6.5 * np.cos(t) + 0 * ecy, ecy + 11 * np.sin(t)
        hf += gbump(S, *R(40 - 6.5 * np.cos(t), 70 + 10.5 * np.sin(t)), 1.6, 1.6, 0.7)
    hf += gbump(S, ecx, ecy, 3.5, 7, -2.2, HEAD_TILT)
    # 头环：从额头前面斜着绕到后脑，一条凸带，上沿亮；额前一个圆凹槽
    band = [R(90, 33), R(70, 34), R(48, 38), R(26, 44), R(6, 52)]
    hf += line_bump(S, band, 2.6, 2.6)
    hf += line_bump(S, [R(90, 37), R(70, 38.5), R(48, 42.5), R(26, 48.5), R(6, 56)], 1.0, -1.3)
    sx_, sy_ = R(86, 34)
    hf += gbump(S, sx_, sy_, 2.4, 2.4, -3.0)
    socket = (int(round(sx_)), int(round(sy_)))
    pal = bramp(8, .06, .44, 262, 250)
    cuts = [0.30, 0.42, 0.52, 0.62, 0.72, 0.82, 0.92]
    idx, lam = relief(hf, m, pal, ambient=0.08, gain=1.0, cuts=cuts)
    # 裂缝：从顶边往下爬几条（暗两档，右唇亮一档）
    tops = np.array([np.nonzero(m[:, x])[0].min() if m[:, x].any() else ih for x in range(iw)])
    for _ in range(7):
        x = int(rng.uniform(0.1, 0.8) * iw)
        y = tops[x] + 2
        for k in range(int(rng.uniform(10, 34))):
            if rng.random() < 0.4:
                x += rng.choice([-1, 1])
            y += 1
            if not (0 < x < iw - 1 and y < ih) or not m[y, x]:
                break
            idx[y, x] = max(0, idx[y, x] - 2)
            if m[y, x + 1] and rng.random() < 0.6:
                idx[y, x + 1] = min(7, idx[y, x + 1] + 1)
    # 朝上的面落了一层细沙：顶边一格亮一档（只在受光那半）
    for x in range(iw):
        y = tops[x]
        if y < ih and idx[y, x] >= 3:
            idx[y, x] = min(7, idx[y, x] + 1)
    img = np.zeros((ih, iw, 4), np.uint8)
    pal_a = np.array([rgba(p) for p in pal], np.uint8)
    img[m] = pal_a[idx[m]]
    chin = R(86, 116)
    return img, socket, tops, (int(round(chin[0])), int(round(chin[1])))


def stone_ring():
    """竖着半埋在沙里的大石环：圆环管子的高度场打光（外圈上半亮、内圈底下朝上的那段亮），
    一圈刻出来的凹点，左上崩掉一块。返回 RGBA，底边 = 沙面（埋掉下面约四分之一）。"""
    R0, r0 = 33, 8.5
    iw = int(2 * (R0 + r0)) + 6
    cx, cy = iw / 2, R0 + r0 + 3
    ih = int(cy + R0 * 0.55)
    yy, xx = np.mgrid[0:ih, 0:iw].astype(float)
    d = np.hypot(xx - cx, (yy - cy) * 1.04)
    ang = np.arctan2(yy - cy, xx - cx)
    rr = r0 + 0.7 * np.sin(ang * 5 + 1) + 0.5 * np.sin(ang * 11)
    t = np.clip(1 - ((d - R0) / rr) ** 2, 0, 1)
    m = t > 0
    m &= ~((ang < -1.9) & (ang > -2.7) & (d > R0 - 2 + 3 * np.sin(ang * 9)))      # 崩掉一块
    hf = np.sqrt(t) * r0 * 1.1
    for a in np.linspace(-np.pi, np.pi, 22, endpoint=False):                     # 刻纹：一圈小凹点
        hf += gbump(m.shape, cx + R0 * np.cos(a), cy + R0 * np.sin(a) / 1.04, 1.3, 1.3, -2.2)
    pal = bramp(7, .06, .38, 262, 250)
    idx, _ = relief(hf, m, pal, ambient=0.08, cuts=[0.3, 0.42, 0.54, 0.66, 0.78, 0.9])
    img = np.zeros((ih, iw, 4), np.uint8)
    pal_a = np.array([rgba(p) for p in pal], np.uint8)
    img[m] = pal_a[idx[m]]
    return img


def head_layer():
    """中景（scroll 0.3）：头像竖着埋在一道缓沙丘里；另一半是竖着的石环；中间几块碎石。整层略往水里褪。"""
    lay = Layer()
    rng = np.random.default_rng(91)
    sand = bramp(4, .075, .2, 262, 250)
    rockp = bramp(5, .07, .26, 264, 246)
    noise = smooth1d(W, rng, 60, 1.0)
    dune = np.zeros(W)
    for x in range(W):
        bump = 7 * np.exp(-((x - HEAD_X) / 90) ** 2) + 5 * np.exp(-((x - RING_X) / 60) ** 2)
        dune[x] = HEAD_BASE + 3 + 2.2 * noise[x] - bump
    img, socket, tops, chin = stone_head()
    hx0 = HEAD_X - img.shape[1] // 2
    hy0 = int(round(dune[hx0 + chin[0]])) - 20 - chin[1]         # 下巴底下还露出一截脖子
    lay.paste(img, hx0, hy0)
    ring = stone_ring()
    lay.paste(ring, RING_X - ring.shape[1] // 2, int(round(dune[RING_X])) + 3 - ring.shape[0])
    # 沙丘：顶上一条亮的细沙，往下暗
    for x in range(W):
        t0 = int(round(dune[x]))
        for y in range(t0, H):
            dd = y - t0
            cc = sand[3] if dd == 0 else (sand[2] if dd == 1 else (sand[1] if dd < 6 else sand[0]))
            lay.put(x, y, cc)
    # 碎石：从头像上掉下来的几块
    for i, (x, w, h) in enumerate(((190, 14, 8), (232, 7, 4), (452, 11, 7), (470, 6, 4), (600, 22, 11),
                                   (655, 9, 6), (905, 16, 9), (40, 8, 5))):
        rr = np.random.default_rng(300 + i)
        yb = int(dune[x]) + 2
        sk = rr.uniform(-0.25, 0.25)
        for j in range(w):
            u = j / max(1, w - 1)
            t = int(round(h * (0.75 + 0.25 * np.sin(np.pi * u)) + sk * (j - w / 2)))
            for k in range(t):
                y = yb - t + k
                c = rockp[4] if k == 0 and u > 0.25 else (rockp[3] if k <= 1 and u > 0.4 else
                                                         rockp[2] if u > 0.55 else rockp[1])
                if u < 0.12:
                    c = rockp[0] if k else rockp[2]
                lay.put(x + j, y, c)
    fade(lay, lambda y: 0.14 + 0.3 * np.clip((y - 185) / 35, 0, 1), steps=8, shift=72)
    # 焦散遮罩：受光最亮的那几档（额头、鼻梁、石环上沿、沙丘顶）
    a = lay.a
    Lm = np.zeros(a.shape[:2])
    m = a[..., 3] > 0
    Lm[m] = to_lab(a[m][:, :3].astype(float))[:, 0]
    hl = np.zeros_like(a)
    sel = m & (Lm > 0.235)
    # 朝上的那一圈（头顶、额头、肩、沙丘顶）吃得最多，往下（脸、耳朵）慢慢少，免得整张脸像罩了一张网
    tops_ = np.where(m.any(0), m.argmax(0), H)
    d = np.arange(H)[:, None] - tops_[None, :]
    up = np.clip(1.0 - (d - 8) / 22.0, 0.3, 1.0)
    hl[sel, 0] = np.clip((Lm[sel] - 0.17) / 0.2 * 255 * up[sel], 40, 255).astype(np.uint8)
    hl[sel, 3] = 255
    global HEADLIGHT
    HEADLIGHT = hl
    return lay, (hx0 + socket[0], hy0 + socket[1]), (hx0, hy0, tops), dune


def head_weeds(dune):
    """headweeds.png：960×HW_H，贴在 head 层 y=HW_Y，底边 = HW_Y+HW_H-1（比沙丘最低的根还低一点）。
    沙丘上、头像脖子两边、石环脚下几小丛矮的带状水草（会摆）。"""
    rng = np.random.default_rng(61)
    pal = bramp(3, .08, .19, 262, 248)
    img = np.zeros((HW_H, W, 4), np.uint8)
    roots = [HEAD_X - 66, HEAD_X - 58, HEAD_X - 49, HEAD_X + 52, HEAD_X + 61, HEAD_X + 90, 150, 158, 520,
             RING_X - 50, RING_X - 42, RING_X + 49, RING_X + 58, 900]
    for x in roots:
        ry = int(round(dune[x])) + 1 - HW_Y
        for _ in range(int(rng.integers(3, 7))):
            ribbon(img, x + rng.uniform(-3, 3), ry, rng.uniform(6, 22), rng, pal, w0=rng.uniform(1.0, 2.2))
    lay = Layer(W, HW_H)
    lay.a = img
    return lay


# ---------------------------------------------------------------- 长水草（带状，会摆）

def ribbon(img, x, base, h, rng, pal, w0=2.5, current=-1.0, bend=None, taper=0.55, ruffle=0.0):
    """一根带状长水草（像苦草 / 大叶藻）：从根往上，慢慢被水流压向一边（current：-1 往左），
    带子会拧：拧到正面时宽、亮一档，拧到侧面时只剩一格宽、暗；朝光（右）的那条边亮一档。
    逐 0.4 格采样画横段，保证连着。"""
    ih, iw = img.shape[:2]
    n = len(pal)
    bend = rng.uniform(0.15, 0.45) if bend is None else bend
    ph = rng.uniform(0, 6.28)
    amp = rng.uniform(1.0, 3.5)
    tw_rate = rng.uniform(2.0, 5.0)
    tw_ph = rng.uniform(0, 6.28)
    s = 0.0
    while s < h:
        f = s / h
        cx = x + current * bend * h * f ** 2.2 + amp * np.sin(f * 3.0 + ph) * f
        cy = base - s * (1 - 0.35 * bend * f ** 2)
        tw = np.cos(f * tw_rate + tw_ph)
        wd = max(1.0, w0 * (1 - taper * f) * (0.3 + 0.7 * abs(tw)) * (1 + ruffle * np.sin(s * 0.9 + ph)))
        if f > 0.93:
            wd = 1.0
        x0 = int(round(cx - wd / 2))
        x1 = max(x0 + 1, int(round(cx + wd / 2)))
        yi = int(round(cy))
        if 0 <= yi < ih:
            for xi in range(x0, x1):
                face = 1 + (tw > 0) + (f > 0.55)
                if xi == x1 - 1 and x1 - x0 >= 2:
                    face += 1
                if x1 - x0 == 1 and abs(tw) < 0.35:
                    face = 1
                img[yi, xi % iw] = rgba(pal[int(np.clip(face, 0, n - 1))])
        s += 0.4


def blade(img, x0, y0, ang, ln, wmax, curl, pal, peak=0.35, rib=True, stem=0.0, stem_w=2.0):
    """一片叶子 / 一条宽叶带：从 (x0, y0) 出发，方向 ang（弧度，-pi/2 = 正上），一路按 curl 慢慢转弯；
    宽度从根部窄、到 peak 处最宽、再收成尖。上沿（朝光）亮一档、下沿暗一档、中间一条叶脉亮半档。
    stem > 0：前 stem 那一截只是一根 stem_w 宽的细茎（巨藻的柄），叶片从那以后才展开（peak 按剩下那截算）。
    沿中线 0.4 格一步、横向 0.5 格一步地填，保证连着、没有洞。"""
    ih, iw = img.shape[:2]
    n = len(pal)
    px, py = float(x0), float(y0)
    steps = int(ln / 0.4)
    for i in range(steps):
        f = i / steps
        a = ang + curl * f
        px += np.cos(a) * 0.4
        py += np.sin(a) * 0.4
        if f < stem:
            w = stem_w
        else:
            g = (f - stem) / (1 - stem)
            w = wmax * (np.sin(np.pi * min(1.0, g / (2 * peak))) if g < peak else (1 - (g - peak) / (1 - peak)) ** 0.8)
            w = max(stem_w if (stem > 0 and g < 0.15) else 0.6, w)
        nx, ny = -np.sin(a), np.cos(a)                 # 法线（指向叶片「下」侧，若叶子朝右上）
        up = -1 if ny > 0 else 1                       # 法线负方向朝上的那一边是受光边
        k = -w / 2
        while k <= w / 2:
            xi, yi = int(round(px + nx * k)), int(round(py + ny * k))
            if 0 <= yi < ih:
                edge_up = (k * up > w / 2 - 0.9) and w > 1.6
                edge_dn = (k * up < -w / 2 + 0.9) and w > 2.6
                c = 1
                if edge_up:
                    c = 3
                elif edge_dn:
                    c = 0
                elif rib and abs(k) < 0.4 and w > 3:
                    c = 2
                img[yi, xi % iw] = rgba(pal[min(n - 1, c)])
            k += 0.5


def giant_kelp(img, x, base, h, rng, pal, current=-1.0):
    """一株巨藻：一根细茎（微微 S 形、被水流压向一边）往上长，两边交替长出窄长的叶片（往上、顺水流斜），
    叶根一颗小气囊。顶上一束叶子拖向水流方向。"""
    ih, iw = img.shape[:2]
    ph = rng.uniform(0, 6.28)
    amp = rng.uniform(1.5, 4.0)
    bend = rng.uniform(0.04, 0.16)
    pts = []
    s = 0.0
    while s < h:
        f = s / h
        cx = x + current * bend * h * f ** 2 + amp * np.sin(f * 3.2 + ph) * f
        cy = base - s
        pts.append((cx, cy, f))
        for k in range(2 if f < 0.4 else 1):
            xi, yi = int(round(cx)) + k, int(round(cy))
            if 0 <= yi < ih:
                img[yi, xi % iw] = rgba(pal[1 + k])
        s += 0.5
    side = 1 if rng.random() < 0.5 else -1
    s = rng.uniform(6, 12)
    while s < h - 3:
        cx, cy, f = pts[int(s / 0.5)]
        ln = rng.uniform(11, 21) * (1.05 - 0.35 * f)
        ang = -np.pi / 2 + side * rng.uniform(0.35, 0.75) + current * 0.3
        blade(img, cx, cy, ang, ln, rng.uniform(2.2, 3.6), -side * rng.uniform(0.1, 0.4) + current * 0.35, pal,
              peak=0.35, rib=False)
        bx, by = int(round(cx + side * 1.0)), int(round(cy))
        if 0 <= by < ih:
            img[by, bx % iw] = rgba(pal[3])
        side = -side
        s += rng.uniform(6, 11)
    cx, cy, f = pts[-1]
    for _ in range(3):                                  # 顶上一束拖向水流的叶子
        blade(img, cx, cy, -np.pi / 2 + current * rng.uniform(0.6, 1.3), rng.uniform(10, 18), 2.4,
              current * rng.uniform(0.3, 0.9), pal, peak=0.35, rib=False)


def kelp():
    """kelp.png：960×KELP_H，贴在层坐标 y=KELP_Y，底边 = 根（被河床挡住）。一丛一丛的巨藻（细茎 + 交替的窄叶），
    中间夹几条宽叶带；都被水流压向左边。晨开场那一段（层坐标 ~60..180 附近）只有很矮的。"""
    img = np.zeros((KELP_H, W, 4), np.uint8)
    pal = bramp(5, .06, .2, 264, 248)
    rng = np.random.default_rng(13)
    clumps = [(16, 3, 190), (128, 1, 64), (446, 3, 196), (520, 2, 120), (650, 2, 160), (770, 4, 200),
              (880, 2, 130)]
    for cx, k, hmax in clumps:
        for i in range(k):
            giant_kelp(img, cx + rng.uniform(-12, 12), KELP_H - 1, hmax * rng.uniform(0.55, 1.0), rng, pal)
        for i in range(k):
            ribbon(img, cx + rng.uniform(-14, 14), KELP_H - 1, hmax * rng.uniform(0.25, 0.6), rng, pal,
                   w0=rng.uniform(3.0, 5.0), bend=rng.uniform(0.1, 0.4), taper=0.4, ruffle=0.15)
    lay = Layer(W, KELP_H)
    lay.a = img
    fade(lay, lambda y: 0.1 + 0.12 * np.clip((y - 150) / 40, 0, 1), steps=6, shift=125)
    return lay


# ---------------------------------------------------------------- 主层：晨走的河床

def ground_y(x):
    x = np.asarray(x, float) % W
    return GROUND + 1.5 * np.sin(2 * np.pi * x * 2 / W + 0.5) + 1.0 * np.sin(2 * np.pi * x * 5 / W + 1.3)


def boulder(w, h, seed, pal, ambient=0.06):
    """一块圆鼓鼓的大石头（高度场打光，光从右上来）：形状是被噪声啃过的超椭圆，顶上几道浅沟。返回 RGBA，底边 = 埋进地里的那一行。"""
    rng = np.random.default_rng(seed)
    ih, iw = h + 4, w + 4
    yy, xx = np.mgrid[0:ih, 0:iw].astype(float)
    cx, cy = iw / 2, ih - 1
    ang = np.arctan2(yy - cy, xx - cx)
    edge = 1 + 0.08 * np.sin(ang * rng.integers(3, 6) + rng.uniform(0, 6)) + 0.05 * np.sin(ang * 9 + rng.uniform(0, 6))
    e = np.abs((xx - cx) / (w / 2)) ** 2.4 + np.abs((yy - cy) / h) ** 2.0
    m = e < edge
    hf = blur(m.astype(float), max(2.0, h / 3)) * h * 0.9 + vnoise(ih, iw, 4, 6, rng) * 2.5
    for _ in range(int(rng.integers(1, 4))):
        x0 = rng.uniform(0.2, 0.8) * iw
        hf += line_bump(m.shape, [(x0, cy - h), (x0 + rng.uniform(-6, 6), cy - h * 0.3)], 1.0, -1.5)
    idx, _ = relief(hf, m, pal, ambient=ambient, cuts=np.linspace(0.3, 0.95, len(pal))[:-1])
    img = np.zeros((ih, iw, 4), np.uint8)
    pal_a = np.array([rgba(p) for p in pal], np.uint8)
    img[m] = pal_a[idx[m]]
    return img


def main_layer():
    """能走的河床。上沿一条细沙线（顶上一行受光，沙纹让它一格一格起伏），往下两三行湿沙，再往下是近黑的淤泥，
    里面埋着几乎看不见的石头。沙面上：卵石、几只螺壳、一截半埋的石柱段、一块头像掉下来的碎石。
    返回 (Layer, 焦散遮罩)：遮罩只在朝上、受光的那几行（Godot 的焦散只画在那里）。"""
    lay = Layer()
    lit = np.zeros((H, W), np.uint8)
    rng = np.random.default_rng(5)
    sand = bramp(5, .1, .26, 258, 246)
    mud = bramp(4, .055, .1, 262, 256)
    stone = bramp(5, .09, .27, 262, 246)
    shell = bramp(3, .16, .34, 250, 236)
    xs = np.arange(W)
    gys = np.round(ground_y(xs)).astype(int)
    noise = rng.random((H, W))
    for x in range(W):
        gy = gys[x]
        for y in range(gy, H):
            d = y - gy
            if d == 0:
                c = sand[3 + (noise[y, x] > 0.8)]
                lit[y, x] = 255
            elif d == 1:
                c = sand[2] if noise[y, x] > 0.3 else sand[3]
                lit[y, x] = 150
            elif d < 5:
                c = sand[int(np.clip(round(2 - d * 0.4 + (noise[y, x] - 0.5)), 0, 2))]
                lit[y, x] = 70 if d < 4 else 0
            else:
                f = min(1.0, (d - 5) / 20)
                c = mud[int(np.clip(round(3 - 3.2 * f + (noise[y, x] - 0.5) * 0.8), 0, 3))]
            lay.a[y, x] = rgba(c)
    # 沙纹：每 7~11 格一个一格高的小鼓包（顶亮），让上沿不是一条直线
    x = 0
    while x < W:
        w = int(rng.integers(3, 6))
        for j in range(w):
            xx = (x + j) % W
            lay.put(xx, gys[xx] - 1, sand[3] if j < w - 1 else sand[2])
            lit[gys[xx] - 1, xx] = 255
        x += w + int(rng.integers(4, 9))
    # 卵石：半露，顶亮
    for _ in range(110):
        x = int(rng.uniform(0, W))
        gy = gys[x]
        w = int(rng.choice([2, 3, 3, 4, 5, 6, 8]))
        hgt = 1 if w < 4 else (2 if w < 7 else 3)
        for j in range(w):
            u = (j - (w - 1) / 2) / max(1, w / 2)
            t = int(round(hgt * max(0.0, 1 - u * u) ** 0.5))
            for k in range(t + 2):
                y = gy - t + k
                v = 2 + (u > -0.2) - (k > 0) - (k > 1) - (u < -0.6)
                lay.put(x + j, y, stone[int(np.clip(v + (k == 0), 0, 4))])
                if k == 0:
                    lit[y, (x + j) % W] = 255
    # 螺壳：几只小小的旋涡壳（3×3 / 4×3），一格亮点
    shells = ["..#.", ".##+", "###.", ]
    for sx in (90, 270, 333, 488, 702, 870):
        gy = gys[sx]
        flip = rng.random() < 0.5
        for r, row in enumerate(shells):
            for c_, ch in enumerate(row[::-1] if flip else row):
                if ch == ".":
                    continue
                lay.put(sx + c_, gy - 3 + r, shell[2] if ch == "+" else (shell[1] if r < 2 else shell[0]))
    # 半埋的一截石柱段（横躺），和一块头像的碎石
    def slab(x0, w, h, seed):
        rr = np.random.default_rng(seed)
        for j in range(w):
            u = j / (w - 1)
            gy = gys[(x0 + j) % W]
            t = int(round(h * (0.8 + 0.2 * np.sin(np.pi * u)) + rr.uniform(-0.4, 0.4)))
            for k in range(t + 2):
                y = gy - t + k
                c = stone[4] if k == 0 else (stone[3] if k == 1 else (stone[2] if u > 0.5 else stone[1]))
                if u < 0.06 or u > 0.94:
                    c = stone[1] if k else stone[3]
                if k > 1 and (j % 9 == 4):
                    c = stone[0]                       # 柱段上的一道道刻槽
                lay.put(x0 + j, y, c)
                if k == 0:
                    lit[y, (x0 + j) % W] = 255
    slab(560, 46, 6, 1)
    slab(780, 13, 5, 2)
    # 几块大石头（半埋）：晨开场那一段（~150..260）没有
    bpal = bramp(6, .06, .3, 262, 248)
    for i, (x, w, h) in enumerate(((52, 34, 15), (78, 14, 7), (452, 22, 9), (720, 46, 20), (752, 16, 8),
                                   (905, 20, 8))):
        img = boulder(w, h, 40 + i, bpal)
        gy = int(round(float(ground_y(x))))
        y0 = gy + 3 - img.shape[0]
        lay.paste(img, x - img.shape[1] // 2, y0)
        mm = img[..., 3] > 0
        for yy_, xx_ in zip(*np.nonzero(mm)):
            X = (x - img.shape[1] // 2 + xx_) % W
            lit[y0 + yy_, X] = 0
            if yy_ == 0 or not mm[yy_ - 1, xx_]:
                lit[y0 + yy_, X] = 255            # 石头顶上一格也吃焦散
    # 泥里的东西：半埋的石头、碎卵石，都很暗
    for _ in range(70):
        x = int(rng.uniform(0, W))
        d = int(7 + rng.random() ** 1.5 * 34)
        w = int(rng.choice([3, 4, 5, 7, 9, 12, 16]))
        y = gys[x] + d
        dl = 0.018 * (1 - 0.6 * min(1.0, d / 40))
        for j in range(w):
            u = (j - (w - 1) / 2) / max(1, w / 2)
            t = int(round(max(1, w * 0.3) * max(0.0, 1 - u * u) ** 0.6))
            for k in range(t + 1):
                L0 = .085 - .03 * min(1.0, d / 40)
                lay.put(x + j, y - t + k, lch(L0 + (dl * 1.6 if k == 0 and u > -0.3 else dl * 0.5), None, 260))
    for _ in range(200):
        x = int(rng.uniform(0, W))
        d = int(6 + rng.random() ** 2 * 40)
        L0 = .085 - .03 * min(1.0, d / 40)
        lay.put(x, gys[x] + d, lch(L0 + 0.02, None, 258))
    return lay, lit


def bed_weeds():
    """bedweeds.png：河床上一丛丛矮水草（会摆），贴在主层 y=BED_Y，底边 = 河床里的根。
    晨开场站的那一段（主层 ~170..250）不长，别的地方一丛丛的；比晨暗很多，只有尖上一格偏亮。"""
    img = np.zeros((BED_H, W, 4), np.uint8)
    pal = bramp(4, .07, .2, 262, 248)
    rng = np.random.default_rng(29)
    for cx in (20, 40, 92, 118, 300, 318, 352, 420, 474, 505, 640, 668, 700, 744, 830, 862, 930):
        for _ in range(int(rng.integers(3, 9))):
            x = cx + rng.uniform(-6, 6)
            root = int(round(ground_y(x))) + 2 - BED_Y
            hgt = rng.uniform(5, 30)
            lean = rng.uniform(-0.3, 0.3)
            bend = rng.uniform(-3, 3)
            for s in range(int(hgt)):
                f = s / hgt
                xi = int(round(x + lean * s + bend * f * f)) % W
                yi = root - s
                if 0 <= yi < BED_H:
                    c = pal[3] if f > 0.85 else (pal[2] if f > 0.5 else (pal[1] if f > 0.15 else pal[0]))
                    img[yi, xi] = rgba(c)
    lay = Layer(W, BED_H)
    lay.a = img
    return lay


# ---------------------------------------------------------------- 前景（scroll 1.4，近黑，会摆）

def front_layer():
    """前景：几处近黑的大水草（宽叶，从画面底下长上来）和几块圆石，把画面框住。只有朝上的边亮一档。
    晨开场那一段（前景层 ~150..400）空着。贴图在层坐标 y=FRONT_Y，底边 = 屏幕底。
    前景 scroll 1.4，比晨快 0.4 倍地滑过去，所以每一处高叶子迟早都会从晨面前经过：
    高的只有两丛（944 / 840），位置挑在镜头 x=0 / 300 / 620 / 1100 时都落在画面边上、朝外弯，
    而且叶子窄（经过晨的时候只挡一条，不会整个盖住）；别的地方只有贴着画面底边的矮叶子和圆石（顶在 y≈236 以下，
    比晨的脚还低）。晨脚下（前景层 x = 204 + 1.4·镜头）：镜头 0→204、300→624、620→112、1100→784。"""
    img = np.zeros((FRONT_H, W, 4), np.uint8)
    pal = bramp(4, .035, .1, 266, 256)
    rng = np.random.default_rng(37)
    ih = FRONT_H
    # 圆石：贴着底边
    for cx, rw, rh in ((30, 40, 22), (470, 26, 10), (640, 50, 18), (880, 30, 12)):
        for x in range(cx - rw, cx + rw + 1):
            u = (x - cx) / rw
            t = int(round(rh * max(0.0, 1 - u * u) ** 0.55))
            for k in range(t):
                y = ih - t + k
                c = pal[2] if k == 0 and u > -0.4 else (pal[1] if k < 3 and u > -0.1 else pal[0])
                img[y, x % W] = rgba(c)
    # 宽叶：几片很大的暗叶子从画面底下伸上来，往外弯（框住画面），上沿一条亮一档的边、中间一条叶脉
    # 高的：细茎从底下上来，叶片在晨头顶（y≈185）以上才展开，所以从晨面前滑过时只挡一根细茎
    for cx, k, hmax, lean, wmax, stem in ((944, 2, 220, 0.2, 12, 0.5), (840, 2, 180, 0.26, 9, 0.6)):
        for i in range(k):
            x = cx + rng.uniform(-8, 8)
            ang = -np.pi / 2 + lean + (i - (k - 1) / 2) * 0.3 + rng.uniform(-0.08, 0.08)
            curl = (1 if lean > 0 else -1) * rng.uniform(0.15, 0.4)
            blade(img, x, ih + 2, ang, hmax * rng.uniform(0.75, 1.0), rng.uniform(wmax - 3, wmax), curl, pal,
                  peak=0.3, stem=stem, stem_w=2.5)
    # 矮叶子：贴着底边，尖最高到 ~y236（层坐标 ih-34），比晨的脚低
    # 开场镜头右下角那一丛（470）宽、低，往左弯
    for i, (dx, ang, ln, wd) in enumerate(((-6, -0.95, 62, 13), (4, -0.55, 46, 11), (14, 0.7, 40, 10))):
        blade(img, 470 + dx, ih + 2, -np.pi / 2 + ang, ln, wd, np.sign(ang) * 0.45, pal, peak=0.3)
    for cx, k in ((60, 3), (150, 2), (300, 2), (560, 3), (650, 3), (720, 2), (780, 3), (900, 2)):
        for i in range(k):
            x = cx + rng.uniform(-14, 14)
            lean = rng.choice([-1, 1]) * rng.uniform(0.6, 1.1)
            blade(img, x, ih + 2, -np.pi / 2 + lean, rng.uniform(22, 40), rng.uniform(5, 9),
                  np.sign(lean) * rng.uniform(0.3, 0.7), pal, peak=0.3)
    lay = Layer(W, FRONT_H)
    lay.a = img
    return lay


# ---------------------------------------------------------------- Godot 用的小贴图

def caustic_tile():
    """焦散图案（64×64，左右上下无缝）：Voronoi 格子的边（R = 0..255 越靠边越亮）。
    shader 用两份不同方向滚动的叠起来，就是水底那种一张网一样慢慢扭的光纹。"""
    rng = np.random.default_rng(3)
    n = 64
    pts = rng.random((14, 2)) * n
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    ds = []
    for px, py in pts:
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                ds.append(np.hypot(xx - px - ox, yy - py - oy))
    ds = np.sort(np.stack(ds), axis=0)
    e = ds[1] - ds[0]                         # 离格子边多远
    v = np.clip(1 - e / 5.0, 0, 1) ** 1.5
    img = np.zeros((n, n, 4), np.uint8)
    img[..., 0] = (v * 255).astype(np.uint8)
    img[..., 3] = 255
    return img


WHALE_FW, WHALE_FH, WHALE_N = 232, 78, 12

# 鲸的贴图不是颜色，是「乘多少」：Godot 里用乘法混合（scripts/underwater_shadow.gdshader）盖在最远的水上，
# 所以它永远是「同一片水再暗一点」，跟着背后的水色渐变、抖动和月光走，不会变成一块实心的剪影。
WHALE_MUL = {"back": (240, 243, 247), "body": (224, 229, 235), "belly": (216, 222, 230), "fin": (219, 225, 232),
             "groove": (230, 234, 240)}


def whale():
    """远处游过的一头鲸（剪影，朝左游）：圆钝的大头、长长的身子往后收成细尾柄，背后三分之二处一个小背鳍，
    一片很长的胸鳍（座头鲸那种，约身长三分之一）往后下方垂着、慢慢扇，尾巴是横着的宽尾鳍（从侧下方看，
    两片往后上、后下张开，后缘中间一个缺口）。WHALE_N 帧：身子后半截按列整像素上下错（鲸的尾巴是上下摆的），
    尾鳍跟着翘。颜色见 WHALE_MUL：背上一条暗得最少（月光），肚子最暗，喉咙下几道浅浅的腹褶。"""
    fw, fh, nfr = WHALE_FW, WHALE_FH, WHALE_N
    sheet = np.zeros((fh, fw * nfr, 4), np.uint8)
    L = 176                    # 吻尖到尾柄
    T = 34.0                   # 最粗处
    cy = 21
    x0 = 3
    # 背线、肚线（离中线多少个 T），按 u = 0 吻尖 .. 1 尾柄
    U = [0.0, 0.012, 0.03, 0.07, 0.14, 0.25, 0.4, 0.52, 0.64, 0.76, 0.86, 0.94, 1.0]
    TOP = [0.02, 0.1, 0.16, 0.23, 0.3, 0.36, 0.4, 0.38, 0.3, 0.19, 0.11, 0.07, 0.06]
    BOT = [0.1, 0.2, 0.28, 0.38, 0.5, 0.58, 0.57, 0.5, 0.36, 0.21, 0.12, 0.07, 0.06]
    FLUKE = [(0, -2.5), (5, -5), (11, -8.5), (18, -11.5), (26, -13.5), (33, -14), (35, -13), (31, -9.5),
             (25, -5.5), (20, -2), (18, 0), (20, 2), (25, 5.5), (31, 9.5), (35, 13), (33, 14), (26, 13.5),
             (18, 11.5), (11, 8.5), (5, 5), (0, 2.5)]
    for fi in range(nfr):
        ph = fi / nfr * 2 * np.pi

        def wave(u):
            return 4.5 * np.sin(ph - u * 2.2) * max(0.0, u - 0.38) ** 1.7

        body = np.zeros((fh, fw), bool)
        cen = {}
        for x in range(L):
            u = (x + 0.5) / L
            off = wave(u)
            t0 = int(round(cy - T * np.interp(u, U, TOP) + off))
            b0 = int(round(cy + T * np.interp(u, U, BOT) + off))
            body[max(0, t0):b0 + 1, x0 + x] = True
            cen[x] = (t0, b0, cy + off)
        # 背鳍：三分之二处一个往后斜的小三角
        dx0 = int(0.66 * L)
        for k in range(10):
            t0 = cen[dx0 + k][0]
            hgt = int(round(3.4 * min(k / 7.0, (10 - k) / 3.0)))
            body[max(0, t0 - hgt):t0, x0 + dx0 + k] = True
        # 尾鳍：横着的宽尾，跟着尾柄翘
        ty = cy + wave(1.0)
        tilt = 0.32 * np.cos(ph - 2.2)
        ca, sa = np.cos(tilt), np.sin(tilt)
        pts = [(x0 + L - 3 + px * ca - py * 0.72 * sa, ty + px * sa + py * 0.72 * ca) for px, py in FLUKE]
        fluke = poly_mask(pts, fh, fw)
        # 胸鳍：很长一片，从肚子前三分之一往后下方垂，根部宽、往尖收，前缘几个小疙瘩，慢慢扇
        fa = 0.66 + 0.07 * np.sin(ph)
        rx = int(L * 0.26)
        ry = cen[rx][1] - 4
        flen = 60
        lead, trail = [], []
        for k in range(0, flen + 1, 3):
            f = k / flen
            a_ = fa + 0.1 * f * np.sin(ph - 1.2)
            px, py = rx + k * np.cos(a_), ry + k * np.sin(a_) * 0.78
            wd = 5.2 * (1 - f) ** 0.75 + 0.6 + (0.8 if (k // 3) % 3 == 1 and f < 0.8 else 0)
            nx, ny = -np.sin(a_), np.cos(a_)
            lead.append((x0 + px - nx * wd, py - ny * wd))
            trail.append((x0 + px + nx * wd * 0.8, py + ny * wd * 0.8))
        fin = poly_mask(lead + trail[::-1], fh, fw)
        fr = np.zeros((fh, fw, 4), np.uint8)
        col = lambda k: np.array(WHALE_MUL[k] + (255,), np.uint8)
        allm = body | fluke
        fr[allm] = col("body")
        for x in range(L):
            t0, b0, c = cen[x]
            u = (x + 0.5) / L
            for y in range(max(0, t0), b0 + 1):
                if y > c + T * np.interp(u, U, BOT) * 0.35:
                    fr[y, x0 + x] = col("belly")
            if 0.06 < u < 0.4:                                    # 腹褶：贴着肚线的两道浅线
                for d in (3, 6):
                    if b0 - d > c + 2:
                        fr[b0 - d, x0 + x] = col("groove")
        top_edge = allm & ~np.roll(allm, 1, axis=0)
        top_edge[:, :x0 + 4] = False
        fr[top_edge & body] = col("back")
        fr[fluke & ~body & (np.arange(fh)[:, None] > ty)] = col("fin")
        fr[fin] = col("fin")
        sheet[:, fi * fw:(fi + 1) * fw] = fr
    return sheet


def pod():
    """果荚 1×2 的暖芯由 Godot 画（underwater_glow.gd），这里不出图。"""
    return None


# ---------------------------------------------------------------- 组装、检查、预览

SIZES = {"deep": (H, SW), "surface": (SURF_H, SW), "kelp": (KELP_H, W), "bedweeds": (BED_H, W),
         "front": (FRONT_H, W), "headweeds": (HW_H, W), "caustic": (64, 64), "whale": (WHALE_FH, WHALE_FW * WHALE_N)}


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    hd, socket, _, dune = head_layer()
    hw = head_weeds(dune)
    sf = Layer(SW, SURF_H)
    sf.a = surface()
    mn, lit = main_layer()
    ml = Layer()
    ml.a[..., 0] = lit
    ml.a[..., 3] = np.where(lit > 0, 255, 0)
    ca = Layer(64, 64)
    ca.a = caustic_tile()
    wh = Layer(WHALE_FW * WHALE_N, WHALE_FH)
    wh.a = whale()
    hl = Layer()
    hl.a = HEADLIGHT
    layers = {"headlight": hl, "deep": deep(), "surface": sf, "distant": distant(), "far": far(), "midfar": midfar(), "head": hd, "headweeds": hw,
              "kelp": kelp(), "main": mn, "bedweeds": bed_weeds(), "front": front_layer(),
              "bedlight": ml, "caustic": ca, "whale": wh}
    for k, v in layers.items():
        v.save(k)
    info = {"socket": socket, "pod": (POD_X, int(round(float(ground_y(POD_X)))) - 1)}
    return layers, info


def check_alpha(layers):
    for k, v in layers.items():
        u = set(np.unique(v.a[..., 3]).tolist())
        assert u <= {0, 255}, (k, u)
        if k in SIZES:
            assert v.a.shape[:2] == SIZES[k], (k, v.a.shape)
        else:
            assert v.a.shape[:2] == (H, W), (k, v.a.shape)


def check_floating(layers, verbose=True):
    """自检：每层不透明像素 8 连通（左右绕回），找出碰不到这层「地面」的团块。
    会摆的贴图（kelp / bedweeds / front / headweeds）地面就是贴图底下几行（根）；headweeds 的根长在头像上，
    所以它和 head 合在一起查。"""
    bad = {}
    xs = np.arange(W)
    for k in ("distant", "far", "midfar", "head", "main", "kelp", "bedweeds", "front", "headweeds"):
        a = layers[k].a
        lab, n = components(a[..., 3] > 0, wrap=True)
        hh = a.shape[0]
        if k == "main":
            floor = np.round(ground_y(xs)).astype(int) - 4
        elif k in ("kelp", "front"):
            floor = np.full(W, hh - 3)
        elif k == "headweeds":
            floor = np.full(W, hh - 14)                 # 根在沙丘上（沙丘高低起伏，在贴图底下 14 行以内）
        elif k == "bedweeds":
            floor = np.round(ground_y(xs)).astype(int) - BED_Y - 2
        else:
            floor = np.full(W, {"distant": 200, "far": 200, "midfar": 205, "head": 214}[k])
        out = []
        for i in range(1, n + 1):
            yy, xx = np.nonzero(lab == i)
            if (yy >= floor[xx]).any():
                continue
            out.append((len(yy), int(xx.min()), int(xx.max()), int(yy.min()), int(yy.max())))
        bad[k] = sorted(out, reverse=True)
        if verbose:
            print(f"  {k:9s} 连通区域 {n:4d}，悬空 {len(out)}", out[:6] if out else "")
    return bad


def surf_rgb(a):
    out = np.zeros_like(a)
    m = a[..., 3] > 0
    lv = np.clip(np.floor(a[..., 0] / 255 * 3 + 0.25), 0, 3).astype(int)
    pal = np.array([rgba(lch(*p)) for p in SURF_PAL], np.uint8)
    out[m] = pal[lv[m]]
    return out


def preview(layers, info, cam_x, path, stand_in=False):
    """按视差比例合成一张 480×270（镜头左边缘在 cam_x），放大 3 倍。光柱、焦散、粒子不画（在 Godot 里）。"""
    out = np.zeros((H, SW, 4), np.uint8)
    place = {"surface": (0, 0), "kelp": (0, KELP_Y), "bedweeds": (0, BED_Y), "front": (0, FRONT_Y),
             "headweeds": (0, HW_Y)}
    for k in SCROLL:
        a = layers[k].a
        if k == "surface":
            a = surf_rgb(a)
        ox, oy = place.get(k, (0, 0))
        if a.shape[1] == SW and k in ("deep", "surface"):
            src = a
        else:
            full = np.zeros((a.shape[0], W, 4), np.uint8)
            full[:, ox:ox + a.shape[1]] = a[:, :W - ox]
            off = int(round(cam_x * SCROLL[k])) % W
            src = np.roll(full, -off, axis=1)[:, :SW]
        if k == "front" and stand_in:
            gy = int(round(float(ground_y((204 + cam_x) % W))))
            out[gy - 37:gy + 1, 199:209] = (205, 196, 190, 255)
        m = src[..., 3] > 0
        out[oy:oy + src.shape[0]][m] = src[m]
    Image.fromarray(out).resize((SW * 3, H * 3), Image.NEAREST).save(path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="把几张合成预览存到这个目录")
    args = ap.parse_args()
    ls, info = build()
    check_alpha(ls)
    print("悬空自检：")
    floating = check_floating(ls)
    if args.preview:
        d = Path(args.preview)
        d.mkdir(parents=True, exist_ok=True)
        for cx in (0, 300, 620):
            preview(ls, info, cx, d / f"underwater_{cx}.png", stand_in=True)
    print("ok", info)
    n_bad = sum(len(v) for v in floating.values())
    if n_bad:
        sys.exit(f"有 {n_bad} 块悬空的东西，见上面的列表")
