"""河流篇 · 月夜水上小镇：高处市集 market、旧街 + 水闸 oldstreet 两个房间。以后改这两间的图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_town_moon_art.py [--preview 目录] [--only market,oldstreet]

输出 art/river_city/market/*、art/river_city/oldstreet/*（图 + room.json，覆盖旧的灰色大都市版）。之后跑一次 `--headless --import`。

世界和河岸（art/river/*，tools/river_art.py）是同一个：深蓝的月夜，月亮在右上，远处雾里立着巨大的石柱。
这里是河上的一座小镇——不是城市，没有砖房、吊脚楼、粗石垒的屋（作者 10-30）：人家是石柱 / 巨石里凿出来的洞窟屋，
一间间分开；门窗是石头里凿出的洞（opening()：屋里有明暗、有门板），透着暖黄的灯；路边稀疏的石灯柱、柱上挂灯；每间留一段只有石柱、水、雾、灯的空路。
石头全用 RA.shade_rock 的干净切面 + weather()（磨角、苔、水渍、小坑），大片横石面用 mass()；不用 Bayer 抖动（像脏了）。配色用河岸那份 tools/river_bank_moon_art.py 的。到处是石像（和水底那颗石头人头同一张脸）。
像森林那样一层层往雾里褪：天 / 远石柱（直接用河岸的 sky、ridge、mist）→ 远处水边的石头人家（far）→ 中景石柱上凿的人家（mid）
→ 能走的这一层（main）→ 栏杆、吊篮（人前面）→ 偶尔挡一下的近景（front）。

规则（和河岸一样）：1 倍像素，alpha 只有 0/255，不描边；光从右上（月亮）来：右边、顶上亮一档；色相 246~262 的蓝。
暖灯的芯最亮 L≈0.62，明显低于晨的白发（全屏最亮的永远是晨）。所有随机固定 seed。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
sys.path.insert(0, str(TOOLS))
import river_art as RA  # noqa: E402
import river_bank_moon_art as BM  # noqa: E402
import underwater_art as UA  # noqa: E402

H = 270
ROOT = TOOLS.parent
OUT = ROOT / "art" / "river_city"
BAYER = RA.BAYER


# ---------------------------------------------------------------- 颜色

def C(L, h=256.0, c=None):
    return RA.lch(L, c, h)


STONE = RA.bramp(7, .075, .36, 258, 248)      # 0 最暗 … 6 月光照到的边
WOOD = RA.bramp(6, .07, .30, 252, 238)
DARK = C(.05, 262)
MOSS = [C(.13, 205, .03), C(.17, 200, .035)]
# 暖灯：和河岸（river_bank_moon_art.WARM）同一套，最亮 L≈0.66，比晨暗
WARM = [BM.WARM[4], BM.WARM[3], BM.WARM[2]]
HALO = BM.WARM[0]
HALO2 = (46, 30, 18)
HUSK = (36, 23, 16)
REFL = [BM.WARM_REF[1], BM.WARM_REF[0]]
CHALK = C(.5, 250, .015)
RED = RA.lch(.34, .085, 22)      # 身高墙上的洪水红线（褪了色的砖红）

_MIX = {}


def mix(c, d, t):
    key = (tuple(c[:3]), tuple(d[:3]), round(float(t), 3))
    if key not in _MIX:
        _MIX[key] = RA.mix(tuple(int(v) for v in c[:3]), tuple(int(v) for v in d[:3]), float(t))
    return _MIX[key]


SKY_KEEP = 124      # sky.png 里最低的云在 123 行；再往下到地平线（150）是一段雾蒙蒙的渐变


def sky_row(y, hz=None):
    """地平线挪到 hz 以后，屏幕第 y 行对应河岸 sky.png 的哪一行：云和月亮那截不动，云下的渐变拉长，地平线以下照搬原图的水。"""
    if hz is None or hz == RA.HORIZON or y < SKY_KEEP:
        return y
    if y < hz:
        return SKY_KEEP + (y - SKY_KEEP) * (RA.HORIZON - SKY_KEEP) / (hz - SKY_KEEP)
    return RA.HORIZON + (y - hz)


def bg(y, hz=None):
    """这一行背后的天 / 水的颜色（不算月光的那团亮）。hz = 这间屋的地平线（默认河岸的 150）。"""
    ys = sky_row(y, hz)
    return RA.L_color(float(RA.quant_L(RA.base_L(ys))), ys)


# ---------------------------------------------------------------- 画布

class Cv:
    def __init__(self, w, h=H, wrap=False):
        self.a = np.zeros((h, w, 4), np.uint8)
        self.wrap = wrap

    @property
    def w(self):
        return self.a.shape[1]

    @property
    def h(self):
        return self.a.shape[0]

    def _xs(self, x0, x1):
        xs = np.arange(int(x0), int(x1))
        if self.wrap:
            return xs % self.w
        return xs[(xs >= 0) & (xs < self.w)]

    def px(self, x, y, c, empty=False):
        x, y = int(round(x)), int(round(y))
        if self.wrap:
            x %= self.w
        if 0 <= x < self.w and 0 <= y < self.h:
            if empty and self.a[y, x, 3]:
                return
            self.a[y, x] = (*c[:3], 255)

    def get(self, x, y):
        x, y = int(x), int(y)
        if self.wrap:
            x %= self.w
        if 0 <= x < self.w and 0 <= y < self.h and self.a[y, x, 3]:
            return tuple(int(v) for v in self.a[y, x, :3])
        return None

    def rect(self, x0, y0, x1, y1, c):
        y0, y1 = max(0, int(y0)), min(self.h, int(y1))
        xs = self._xs(x0, x1)
        if y1 > y0 and len(xs):
            self.a[y0:y1, xs] = (*c[:3], 255)

    def hline(self, x0, x1, y, c):
        self.rect(x0, y, x1, y + 1, c)

    def vline(self, x, y0, y1, c):
        self.rect(x, y0, x + 1, y1, c)

    def blend(self, x, y, c, t):
        """已经有东西的地方往 c 推 t（灯光照到墙上）。"""
        o = self.get(x, y)
        if o is not None:
            self.px(x, y, mix(o, c, t))

    def line(self, x0, y0, x1=None, y1=None, c=None, empty=False):
        if x1 is None:                       # river_city_art.Cv 的写法：line([(x, y), …], c)
            pts, c = x0, y0
            for (a, b), (d, e) in zip(pts[:-1], pts[1:]):
                self.line(a, b, d, e, c)
            return
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n):
            t = i / max(1, n - 1)
            self.px(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, c, empty)

    def poly(self, pts, c):
        pts = np.asarray(pts, float)
        x0, y0 = np.floor(pts.min(0)).astype(int)
        x1, y1 = np.ceil(pts.max(0)).astype(int) + 1
        m = UA.poly_mask(pts - [x0, y0], y1 - y0, x1 - x0)
        for yy, xx in zip(*np.nonzero(m)):
            self.px(x0 + xx, y0 + yy, c)

    def paste(self, img, x, y):
        img = img.a if isinstance(img, Cv) else img
        h, w = img.shape[:2]
        for yy in range(h):
            m = img[yy, :, 3] > 0
            if not m.any():
                continue
            ty = y + yy
            if not 0 <= ty < self.h:
                continue
            for xx in np.nonzero(m)[0]:
                self.px(x + xx, ty, img[yy, xx])

    def save(self, path):
        Image.fromarray(self.a).save(path)


def fog(cv, t_of_y, steps=6, hz=None):
    """整层往背后的天 / 水色褪 t(y)。一行一个褪色量（1/32 一档，细到看不出台阶），不抖——
    第四版：Bayer 抖动在中景石柱上是一片棋盘格，像脏了。steps 参数留着兼容，不用了。"""
    a = cv.a
    for y in range(cv.h):
        m = a[y, :, 3] > 0
        if not m.any():
            continue
        tq = round(float(np.clip(t_of_y(y), 0, 1)) * 32) / 32
        if tq <= 0:
            continue
        b = bg(y, hz)
        for x in np.nonzero(m)[0]:
            a[y, x, :3] = mix(a[y, x, :3], b, tq)


# ---------------------------------------------------------------- 灯

def lantern(cv, x, y, hang=0, big=False, rope=None):
    """一盏灯笼：顶上暗盖、2×3（大的 3×4）的暖芯、底下一格暗坠；外面一圈晕。(x, y) = 盖子左上。"""
    rope = rope or DARK
    if hang:
        cv.vline(x + (1 if big else 0), y - hang, y, rope)
    bw, bh = (3, 4) if big else (2, 3)
    cv.hline(x - 1, x + bw + 1, y, HUSK)
    for yy in range(bh):
        cv.hline(x, x + bw, y + 1 + yy, WARM[0] if yy == 0 else WARM[1] if yy < bh - 1 else WARM[2])
    cv.hline(x, x + bw, y + 1 + bh, HUSK)
    for yy in range(y + 1, y + 1 + bh):
        cv.px(x - 1, yy, HALO)
        cv.px(x + bw, yy, HALO)
    for yy in range(y + 2, y + bh):
        cv.px(x - 2, yy, HALO2)
        cv.px(x + bw + 1, yy, HALO2)
    cv.px(x + bw // 2, y + bh + 2, HALO2)


# ---------------------------------------------------------------- 石像（和水底那颗石头人头同一张脸）

def head_relief(s, pal=None, tilt=0.0):
    """缩小的石头人头（脸朝右，头环），s = 缩放。返回 (img, mask)。"""
    pal = pal or RA.bramp(7, .06, .40, 262, 250)
    pts = np.array(UA.HEAD_PTS, float) * s
    ca, sa = np.cos(tilt), np.sin(tilt)
    c = pts.mean(0)
    p = pts - c
    pts = np.stack([p[:, 0] * ca - p[:, 1] * sa, p[:, 0] * sa + p[:, 1] * ca], -1)
    pad = 3
    off = -pts.min(0) + pad
    pts = pts + off

    def R(x, y):
        q = np.array([x, y], float) * s - c
        return (q[0] * ca - q[1] * sa + off[0], q[0] * sa + q[1] * ca + off[1])

    iw, ih = int(pts[:, 0].max()) + pad + 1, int(pts[:, 1].max()) + 1
    m = UA.poly_mask(pts, ih, iw)
    S = m.shape
    hf = UA.blur(m.astype(float), max(1.2, 7.0 * s)) * 26 * s + UA.blur(m.astype(float), max(.8, 2.2 * s)) * 5 * s
    k = max(s, 0.25)
    hf += UA.line_bump(S, [R(76, 44), R(86, 46), R(92, 48)], 2.0 * k, 1.3 * k * 3)
    hf += UA.gbump(S, *R(83, 54), 6 * k, 4 * k, -3.2 * k * 3, tilt)
    hf += UA.gbump(S, *R(76, 68), 8 * k, 5 * k, 2.4 * k * 3, tilt + .4)
    hf += UA.line_bump(S, [R(94, 80), R(90, 78), R(88, 74)], 1.3 * k, -1.6 * k * 3)
    hf += UA.line_bump(S, [R(92, 90), R(86, 92)], 1.0 * k, -1.6 * k * 3)
    hf += UA.gbump(S, *R(40, 70), 3.5 * k, 7 * k, -2.2 * k * 3, tilt)
    band = [R(90, 33), R(70, 34), R(48, 38), R(26, 44), R(6, 52)]
    hf += UA.line_bump(S, band, 2.6 * k, 2.6 * k * 3)
    idx, _ = UA.relief(hf, m, pal, ambient=0.1, cuts=[.3, .42, .54, .66, .78, .9][:len(pal) - 1])
    img = np.zeros((ih, iw, 4), np.uint8)
    pa = np.array([RA.rgba(q) for q in pal], np.uint8)
    img[m] = pa[idx[m]]
    return img, m


def lamp_bearer(seed=5):
    """市集当中坐着的石像：一个大块头的人坐在石台上，头是水底那张脸（头环、闭着眼），双手往前捧着一只石碗，碗里点着灯。
    灯从下往上照亮它的手、下巴和鼻底（一圈暖）。返回 (img, 灯芯在图里的位置)。"""
    rng = np.random.default_rng(seed)
    w, h = 96, 150
    S = (h, w)
    yy, xx = np.mgrid[0:h, 0:w].astype(float)

    def ell(cx, cy, rx, ry):
        return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1

    plinth_top = 122
    torso = ell(40, 90, 21, 30) & (yy < plinth_top)
    lap = ell(52, 112, 25, 11) & (yy < plinth_top)
    shins = (xx > 62) & (xx < 76) & (yy > 108) & (yy < plinth_top)
    arm = np.zeros(S, bool)
    for t in np.linspace(0, 1, 40):
        ax, ay = 48 + (70 - 48) * t, 74 + (96 - 74) * t ** 0.8
        arm |= ell(ax, ay, 5.5, 5.5)
    bowl = ell(74, 92, 9, 4.5) & (yy >= 91)
    body = torso | lap | shins | arm | bowl
    hf = (UA.blur(torso.astype(float), 5) * 14 + UA.blur(lap.astype(float), 3.5) * 8 + UA.blur(arm.astype(float), 2.2) * 7
          + UA.blur(bowl.astype(float), 1.5) * 4 + UA.blur(shins.astype(float), 2) * 5)
    pal = RA.bramp(7, .06, .40, 262, 250)
    idx, _ = UA.relief(hf, body, pal, ambient=0.1, cuts=[.3, .42, .54, .66, .78, .9])
    img = np.zeros((h, w, 4), np.uint8)
    pa = np.array([RA.rgba(q) for q in pal], np.uint8)
    img[body] = pa[idx[body]]
    # 衣褶：几道从肩往下的暗线
    for x0 in (30, 38, 46):
        for y in range(70, 116):
            x = int(round(x0 + (y - 70) * 0.18 + np.sin(y * 0.3 + x0) * 0.6))
            if body[y, x]:
                img[y, x, :3] = pal[max(0, idx[y, x] - 2)]
    # 头
    hd, hm = head_relief(0.42, pal)
    hx, hy = 40 - int(hd.shape[1] * 0.42), 64 - hd.shape[0]
    hy += 14
    m = hd[..., 3] > 0
    sub = img[hy:hy + hd.shape[0], hx:hx + hd.shape[1]]
    sub[m] = hd[m]
    # 石台：两级，顶面亮，右面一条亮边，石缝
    def block(x0, y0, x1, y1):
        img[y0:y1, x0:x1] = RA.rgba(pal[2])
        img[y0, x0:x1] = RA.rgba(pal[5])
        img[y0 + 1, x0:x1] = RA.rgba(pal[4])
        img[y0:y1, x1 - 1] = RA.rgba(pal[4])
        img[y0:y1, x0] = RA.rgba(pal[1])
        for x in range(x0 + 5, x1 - 2, 11):
            img[y0 + 2:y1, x] = RA.rgba(pal[1])
        img[y1 - 1, x0:x1] = RA.rgba(pal[1])
    block(12, plinth_top, 88, 138)
    block(4, 138, 94, 150)
    # 裂纹 + 苔
    for _ in range(5):
        x, y = int(rng.uniform(24, 70)), int(rng.uniform(60, 118))
        for k in range(int(rng.uniform(6, 14))):
            if 0 <= y < h and 0 <= x < w and img[y, x, 3]:
                img[y, x, :3] = pal[0]
            y += 1
            x += rng.choice([-1, 0, 0, 1])
    for x in range(w):
        col = np.nonzero(img[:, x, 3])[0]
        if len(col) and rng.random() < 0.35:
            y = col.min()
            img[y, x] = RA.rgba(MOSS[1])
    # 碗里的灯：暖芯 + 往上照亮下巴、手（距离分档、抖动）
    fx, fy = 73, 88
    for y in range(h):
        for x in range(w):
            if not img[y, x, 3]:
                continue
            d = np.hypot((x - fx) * 1.0, (y - fy) * 1.2)
            if d < 26 and not (y > 95 and d > 12):
                t = 0.62 * (1 - d / 26) ** 1.2
                tq = np.floor(t * 4 + (BAYER[y % 4, x % 4] < (t * 4 % 1))) / 4
                if tq > 0:
                    img[y, x, :3] = mix(img[y, x, :3], REFL[0], min(.75, tq))
    fl = [(fx, fy - 4, WARM[0]), (fx, fy - 3, WARM[0]), (fx - 1, fy - 2, WARM[1]), (fx, fy - 2, WARM[0]),
          (fx + 1, fy - 2, WARM[1]), (fx - 1, fy - 1, WARM[1]), (fx, fy - 1, WARM[1]), (fx + 1, fy - 1, WARM[2]),
          (fx - 2, fy, WARM[2]), (fx + 2, fy, WARM[2])]
    for x, y, c in fl:
        img[y, x] = RA.rgba(c)
    for x, y in [(fx - 2, fy - 2), (fx + 2, fy - 2), (fx - 1, fy - 4), (fx + 1, fy - 4), (fx, fy - 5)]:
        img[y, x] = RA.rgba(HALO)
    return img, (fx, fy)


def bollard_head(s=0.17, seed=1):
    """码头边当系缆桩的小石头人头（脖子埋在石沿里）。10-30 起不用了：水上的房间不再出现水底那张脸，换成 stone_post()。"""
    img, m = head_relief(s, RA.bramp(5, .07, .34, 262, 250))
    return img


# ---------------------------------------------------------------- 水上的石像（作者 10-30：水底那颗戴帽人头留给水底，水上只用提灯人 / 半沉的石鲸）

STATUE = RA.bramp(7, .08, .46, 260, 238)


def carve_shade(m, pal, seed, folds=(), top_lit=True):
    """雕像的上色：月光从右上来。每一行按左右沿分三个面（背光 / 侧 / 受光），右沿一道亮边、第二格亮一档；
    朝上的面亮；folds = [((x0, y0), (x1, y1))]：斜的衣褶 = 一道暗楔，紧贴它右边一道亮一档的棱。不抖。"""
    rng = np.random.default_rng(seed)
    h, w = m.shape
    n = len(pal)
    idx = np.full((h, w), -1)
    ctop = np.full(w, h)
    for x in range(w):
        ys_ = np.nonzero(m[:, x])[0]
        if len(ys_):
            ctop[x] = ys_[0]
    for y in range(h):
        xs = np.nonzero(m[y])[0]
        if not len(xs):
            continue
        runs = np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1)
        for run in runs:
            a, b = run[0], run[-1]
            for x in run:
                u = (x - a) / max(1, b - a)
                k = 1 if u < 0.3 else (2 if u < 0.58 else 3)
                if b - a >= 4:
                    if x == b:
                        k = n - 1
                    elif x == b - 1:
                        k = max(k, n - 2)
                    elif x == a:
                        k = 0
                dt = y - ctop[x]                      # 离这一列顶面多远：顶上一条受月光的带
                if top_lit and dt == 0:
                    k = max(k, n - 2 if u > 0.25 else 3)
                elif top_lit and dt <= 2 and u > 0.35:
                    k = max(k, 4)
                idx[y, x] = k
    for (x0, y0), (x1, y1) in folds:
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(steps):
            t = i / max(1, steps - 1)
            x, y = int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t))
            wd = 1 + (1 if 0.3 < t < 0.8 else 0)
            for d in range(wd):
                if 0 <= y < h and 0 <= x - d < w and m[y, x - d]:
                    idx[y, x - d] = max(0, idx[y, x - d] - 2)
            if 0 <= y < h and x + 1 < w and m[y, x + 1]:
                idx[y, x + 1] = min(n - 1, idx[y, x + 1] + 1)
    img = np.zeros((h, w, 4), np.uint8)
    for k in range(n):
        img[idx == k, :3] = pal[k][:3]
        img[idx == k, 3] = 255
    return weather(img, rng, pal, moss=0.35, chips=2, pits=3)


def waterline_band(img, wl, pal, seed, sparkle=True):
    """泡水的那截：水线以上 4 行湿、暗一档，偶尔一格苔；水线那一行几格湿亮的反光。"""
    rng = np.random.default_rng(seed)
    idx = _pal_index(img, pal)
    h, w = img.shape[:2]
    for y in range(max(0, wl - 4), min(h, wl + 1)):
        for x in range(w):
            if idx[y, x] > 0:
                img[y, x, :3] = pal[idx[y, x] - 1][:3]
                if rng.random() < 0.08:
                    img[y, x, :3] = BM.MOSS[0][:3]
    for x in range(w):
        if sparkle and 0 <= wl < h and img[wl, x, 3] and rng.random() < 0.3:
            img[wl, x, :3] = pal[-2][:3]


def lantern_bearer(seed=7, pal=None):
    """提灯人：半截泡在水里的石雕人像。斗篷兜帽、低着头（帽尖往前垂），双手在胸前捧着一盏真的点着的小灯；
    脸藏在帽兜的影子里，只有灯从下面照亮帽檐下沿、双手和胸前一小片（暖色很快衰减）。
    返回 (RGBA, 灯芯 (x, y), 水线 y)。图 60×84，水线在最底一行。"""
    pal = pal or STATUE
    w, h, wl = 60, 84, 83
    body = UA.poly_mask([(19, 26), (14, 36), (11, 50), (9, 64), (7, h), (53, h), (51, 64), (49, 50), (47, 38), (44, 29)], h, w)
    hood = UA.poly_mask([(19, 30), (18, 18), (22, 9), (29, 4), (36, 6), (42, 12), (46, 20), (47, 27), (43, 31)], h, w)
    hands = UA.poly_mask([(41, 44), (46, 41), (53, 42), (55, 46), (51, 49), (44, 49)], h, w)
    m = body | hood | hands
    img = carve_shade(m, pal, seed, folds=[((22, 34), (15, 80)), ((30, 38), (27, 80)), ((38, 44), (40, 80)),
                                           ((24, 10), (21, 28))])
    # 帽兜的开口：朝右下（低着头），里面最暗；开口下沿被手里的灯照到一道暖
    face = UA.poly_mask([(40, 18), (44, 20), (46, 25), (44, 28), (40, 26)], h, w)
    img[face, :3] = DARK[:3]
    for x in range(w):                            # 帽檐：开口上沿一道受月光的边，读得出是兜帽而不是一个洞
        ys_ = np.nonzero(face[:, x])[0]
        if len(ys_) and ys_[0] > 0 and m[ys_[0] - 1, x]:
            img[ys_[0] - 1, x, :3] = pal[5][:3]
    for (x, y) in [(40, 26), (41, 27), (42, 27), (43, 27)]:
        img[y, x, :3] = HUSK
    # 灯：一盏小提灯，铁框 + 暖芯
    lx, ly = 50, 38
    iron = BM.B(.07, .015, 262)
    for (x, y, c) in [(lx - 2, ly - 4, iron), (lx - 1, ly - 4, iron), (lx, ly - 4, iron), (lx + 1, ly - 4, iron),
                      (lx, ly - 5, iron)]:
        img[y, x] = (*c[:3], 255)
    for y in range(ly - 3, ly + 2):
        for x in range(lx - 2, lx + 2):
            img[y, x] = (*BM.WARM[3 if (x, y) in ((lx - 1, ly - 1), (lx, ly - 1), (lx - 1, ly), (lx, ly)) else 2][:3], 255)
    img[ly + 2, lx - 2:lx + 2] = (*iron[:3], 255)
    img[ly - 1, lx - 1] = (*BM.WARM[4][:3], 255)
    # 灯光落在手、胸前、帽檐下沿：三档，按距离很快衰减，只照朝着灯的面（灯的左边、上下一小片）
    for y in range(h):
        for x in range(w):
            if not m[y, x] or face[y, x] or (lx - 2 <= x < lx + 2 and ly - 5 <= y <= ly + 2):
                continue
            d = np.hypot(x - lx, (y - ly) * 1.1)
            if d > 16:
                continue
            k = 0 if d < 5 else (1 if d < 10 else 2)
            t = (0.7, 0.42, 0.2)[k]
            o = tuple(int(v) for v in img[y, x, :3])
            img[y, x, :3] = mix(o, BM.WARM[1] if k else BM.WARM[2], t)
    waterline_band(img, wl, pal, seed)
    return img, (lx, ly), wl


def stone_whale(seed=9, pal=None):
    """半沉的石鲸：只露出一段背和左边翘出水的尾鳍。背上一层苔、几颗藤壶，水线一带湿暗。返回 (RGBA, 水线 y)。图 170×60。"""
    pal = pal or STATUE
    w, h, wl = 170, 60, 59
    m = np.zeros((h, w), bool)
    # 背的轮廓：尾柄低低地出水，往前慢慢拱起（最高在中间偏头），一个小背鳍，头那头圆圆地落回水里
    ts = [0, .12, .3, .5, .66, .8, .92, 1.0]
    hs = [3, 9, 18, 25, 26, 21, 11, 0]
    ctop = np.full(w, h)
    for x in range(44, 168):
        t = (x - 44) / 123
        hh = np.interp(t, ts, hs) + 5 * np.exp(-((t - 0.36) / 0.035) ** 2) * (1 if t < 0.36 else 0.6)
        ctop[x] = int(round(wl - hh))
        m[ctop[x]:, x] = True
    fluke = UA.poly_mask([(30, h), (27, 46), (18, 33), (7, 25), (2, 23), (9, 26), (21, 32), (30, 38), (35, 30),
                          (46, 20), (52, 19), (45, 28), (38, 40), (37, h)], h, w)
    # 第六版：材质用河岸的 BM.stone_shade（整章一个画法），水线以下更深更湿
    img = BM.stone_shade(m | fluke, np.random.default_rng(seed), pal, facet_w=12, joints=0.5, ledges=0.3, moss=0.7,
                         water_row=wl)
    rng = np.random.default_rng(seed + 1)
    for _ in range(14):                           # 藤壶：一颗暗点 + 右下一格亮
        x = int(rng.integers(70, 160))
        ys = np.nonzero(m[:, x])[0]
        if len(ys):
            y = int(ys[0]) + int(rng.integers(3, 14))
            if y < wl - 3 and m[y, x + 1] and m[y + 1, x + 1]:
                img[y, x, :3] = pal[1][:3]
                img[y + 1, x + 1, :3] = pal[4][:3]
    waterline_band(img, wl, pal, seed, sparkle=False)
    return img, wl


def stone_post(cv, x, base, pal=None):
    """码头上的石系缆桩（替掉以前那几颗小人头）：一截圆头短石柱，腰上一道磨出来的绳槽，挂一只铁环。"""
    pal = pal or BM.STONE
    for y in range(base - 12, base + 1):
        half = 3 if y > base - 10 else (2 if y > base - 12 else 1)
        for xx in range(x - half, x + half + 1):
            u = (xx - (x - half)) / max(1, 2 * half)
            k = 1 if u < 0.35 else (2 if u < 0.7 else 3)
            if xx == x + half:
                k = 5
            if y == base - 12 or (y == base - 11 and half == 2):
                k = 4
            cv.px(xx, y, pal[k])
    cv.hline(x - 3, x + 4, base - 7, pal[0])          # 绳槽
    cv.px(x + 3, base - 7, pal[2])
    cv.hline(x - 2, x + 3, base - 6, pal[3])
    for a_ in np.linspace(0, 2 * np.pi, 12, endpoint=False):
        cv.px(x + 4 + 1.6 * np.cos(a_), base - 4 + 1.8 * np.sin(a_), BM.B(.1, .015, 255) if np.sin(a_) > 0 else BM.B(.18, .02, 250))


def carved_line(cv, x0, x1, y, seed, pal=None, worn=0.12, lip=0.5):
    """凿进石面的一道横线：槽里暗（上沿在影子里），槽的下唇受月光亮一点（不是整条亮线：混进原来的石色，断断续续）；
    两头参差，中间偶尔被磨平一两格。"""
    pal = pal or BM.STONE
    rng = np.random.default_rng(seed)
    a, b = x0 + int(rng.integers(0, 3)), x1 - int(rng.integers(0, 3))
    for x in range(a, b):
        if rng.random() < worn:
            continue
        o = cv.get(x, y)
        if o is None:
            continue
        cv.px(x, y, mix(o, DARK, 0.85))
        if rng.random() < 0.8:
            cv.blend(x, y + 1, pal[5], lip)


def carved_digits(cv, x, y, text, seed, pal=None, lip=0.5):
    """凿进石面的小数字：笔画是暗槽，笔画下面一格是受光的唇；年头久了，少几格。"""
    pal = pal or BM.STONE
    rng = np.random.default_rng(seed)
    tmp = Cv(len(text) * 4 + 1, 7)
    tiny_digits(tmp, 0, 0, text, (255, 255, 255))
    on = tmp.a[..., 3] > 0
    for yy, xx in zip(*np.nonzero(on)):
        if rng.random() < 0.12:
            continue
        cv.blend(x + xx, y + yy, DARK, 0.8)
        if yy + 1 >= on.shape[0] or not on[yy + 1, xx]:
            cv.blend(x + xx, y + yy + 1, pal[5], lip)


def faded_paint(cv, x0, x1, y, seed, color, thick=2):
    """刷在石面上、褪了色的一道漆：每格只混进去一点（三档，随机），掉漆的地方露出石头，上下沿参差。"""
    rng = np.random.default_rng(seed)
    # 10-30：原来每格随机掉、随机深浅，远看是一条点点的虚线。现在漆是一整段一整段的（掉漆是几块成片的缺口，
    # 缺口里只剩上沿或下沿一格），深浅两档、成片地变，上下沿偶尔多出一格（刷子毛边）
    gap, deep, x = 0, True, x0
    for x in range(x0, x1):
        if gap <= 0 and rng.random() < 0.05:
            gap = int(rng.integers(2, 6))
        if rng.random() < 0.08:
            deep = not deep
        t = 0.62 if deep else 0.48
        for d in range(thick):
            if gap > 0 and d != (0 if gap % 2 else thick - 1):
                continue
            cv.blend(x, y + d, color, t * (0.7 if gap > 0 else 1.0))
        if gap <= 0 and rng.random() < 0.12:
            cv.blend(x, y + (-1 if rng.random() < 0.5 else thick), color, t * 0.6)
        gap -= 1


def tiny_digits(cv, x, y, text, c):
    """3×5 的小数字（墙上刻的年份）。"""
    F = {"0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111",
         "4": "101101111001001", "5": "111100111001111", "6": "111100111101111", "7": "111001010010010",
         "8": "111101111101111", "9": "111101111001111"}
    for i, ch in enumerate(text):
        for k, b in enumerate(F[ch]):
            if b == "1":
                cv.px(x + i * 4 + k % 3, y + k // 3, c)


# ---------------------------------------------------------------- 远景（两个房间共用的画法）

def far_town(seed, width=960, waterline=151, n=9, hz=None):
    """远处水边的人家：贴着地平线的一块块圆石头（凿了门窗）和几根小石柱（柱身上一点灯），往雾里褪得很厉害，
    只剩一个个小灯点和水里的倒影。"""
    rng = np.random.default_rng(seed)
    cv = Cv(width, wrap=True)
    pal = RA.bramp(4, .10, .2, 258, 250)
    lights = []
    xs = np.sort(rng.choice(np.arange(20, width - 20, 24), n, replace=False)) + rng.integers(-6, 6, n)
    for i, x in enumerate(xs):
        if rng.random() < 0.4:
            ph = int(rng.integers(26, 46))
            pw = int(rng.integers(9, 14))
            img = RA.pillar(pw, ph, int(seed * 10 + i), RA.bramp(4, .11, .22, 258, 248), kind="tower")
            cv.paste(img, x - img.shape[1] // 2, waterline - img.shape[0])
            for k in range(int(rng.integers(1, 3))):
                lights.append((x - 1 + k, waterline - ph + 6 + k * 9))
        else:
            for j in range(int(rng.integers(1, 3))):
                hx = x + j * int(rng.integers(13, 18))
                bw, bh = int(rng.integers(9, 15)), int(rng.integers(5, 9))
                for xx in range(bw):
                    u = abs((xx + .5 - bw / 2) / (bw / 2))
                    t = int(round(bh * (1 - u ** 2.6) ** (1 / 2.6)))
                    cv.vline(hx + xx, waterline - t, waterline + 1, pal[1])
                    cv.px(hx + xx, waterline - t, pal[3] if xx > bw / 2 else pal[2])
                cv.vline(hx + bw - 1, waterline - bh + 2, waterline + 1, pal[2])
                if rng.random() < 0.85:
                    lights.append((hx + int(rng.integers(2, max(3, bw - 3))), waterline - int(bh * 0.5)))
    # 地平线上一条很低的岸
    noise = RA.smooth1d(width, rng, 50, 1.0)
    for x in range(width):
        for d in range(1 + int(round(1 + noise[x]))):
            cv.px(x, waterline - d, pal[0], empty=True)
    fog(cv, lambda y: 0.5 + 0.3 * np.clip((y - waterline + 31) / 30, 0, 1), hz=hz)
    for (lx, ly) in lights:      # 灯点和倒影（褪过雾以后再点，雾里的灯不褪）
        cv.px(lx, ly, WARM[2])
        cv.px(lx, ly + 1, HALO)
        for yy in range(waterline + 2, waterline + 8):      # 倒影：一条连着的细竖带，往下变暗（10-30：原来是等距的短横）
            cv.px(lx + (1 if rng.random() < 0.3 else 0), yy, REFL[1] if yy < waterline + 5 else HALO)
    return cv, lights


def rope_bridge(cv, x0, y0, x1, y1, sag=None, lamps=(), pal=WOOD, far=False):
    """两块石台之间的人行吊桥（作者 10-30：「这个吊桥没连在一起，连在一起的有的竖着看着也很奇怪」）。
    x0 / x1 = 桥面最左 / 最右一格，紧贴两头石台的外角；y0 / y1 = 两头石台的上沿（桥面就落在这一行）。
    两头高差不许超过跨度的 8%（像真的吊桥：基本水平，中间垂下去约跨度的 7%，一条悬链线）。
    木板顺着弧线等距排（每 3 格一道缝，缝和弧线垂直）；两头各一根木桩、桩顶一个绳结，扶手绳从桩顶拉过去、
    比桥面多垂一点，几根竖绳把桥面吊在扶手上。lamps：0..1 哪几处，从桥面下吊一盏小灯。
    far=True：远处的小桥，只有桥面、扶手和两头的桩。"""
    span = x1 - x0
    assert span > 8 and abs(y1 - y0) <= max(2, span * 0.08), ("吊桥两头高差太大", x0, y0, x1, y1)
    sag = sag if sag is not None else max(2, int(round(span * 0.07)))
    post = 4 if far else 6
    k = 1.6

    def dip(x):                                   # 悬链线：两头 0，正中 1
        u = 2 * (x - x0) / span - 1
        return 1 - (np.cosh(k * u) - 1) / (np.cosh(k) - 1)

    def deck(x):
        return int(round(y0 + (y1 - y0) * (x - x0) / span + sag * dip(x)))

    def rail(x):
        return int(round(y0 + (y1 - y0) * (x - x0) / span - post + (sag + (1 if far else 2)) * dip(x)))

    s, prev, seam = 0.0, None, -1
    for x in range(x0, x1 + 1):                   # 桥面：上沿受光的木板 + 下面一道暗的托梁，缝按弧长等距
        yd = deck(x)
        if prev is not None:
            s += float(np.hypot(1, yd - prev))
        prev = yd
        cut = int(s // 3) != seam and x not in (x0, x1)
        seam = int(s // 3)
        cv.px(x, yd, pal[1] if cut else pal[4 if far else 3])
        cv.px(x, yd + 1, pal[0] if cut or far else pal[2])
        if not far:
            cv.px(x, yd + 2, pal[0])
    py = None
    for x in range(x0, x1 + 1):                   # 扶手绳（1 像素，断了就竖着补一格，保证连着）
        yr = rail(x)
        if py is not None and abs(yr - py) > 1:
            cv.vline(x, min(yr, py) + 1, max(yr, py), pal[2])
        cv.px(x, yr, pal[2])
        py = yr
    step = 4 if far else 6                        # 竖绳：等距，把桥面吊在扶手上
    n = max(1, int(span // step))
    for i in range(1, n):
        x = int(round(x0 + span * i / n))
        cv.vline(x, rail(x) + 1, deck(x), pal[1])
    for x, side in ((x0, -1), (x1, 1)):            # 两头的木桩：立在石台上，桩顶一个亮绳结，外侧一格影子
        yd = deck(x)
        cv.vline(x, yd - post - 1, yd + 1, pal[3])
        cv.px(x, yd - post - 1, pal[5])
        cv.px(x - side, rail(x), pal[4])          # 扶手绳在桩上绕一圈的结
        if not far:
            cv.vline(x + side, yd - post, yd, pal[0])
    for t in lamps:                               # 灯：从桥面下的托梁吊下来
        x = int(round(x0 + span * t))
        lantern(cv, x, deck(x) + (2 if far else 5), hang=2 if far else 3)


def pillar_bridge(cv, a, b, pal=None, lamps=(0.5,)):
    """中景两根石柱（rock_town 返回的 (x, 柱顶, 宽)）之间的吊桥：在两根都够得着的同一高度（比矮的那根柱顶再低 22 格，不落在柱顶的肩上）
    各凿一块石台和一扇小门，桥挂在两块石台之间。"""
    pal = pal or BM.STONE_FAR
    y = max(a[1], b[1]) + 22
    x0, _ = bridge_ledge(cv, a[0], y, 1, pal)
    x1, _ = bridge_ledge(cv, b[0], y, -1, pal)
    rope_bridge(cv, x0, y, x1, y, lamps=lamps)


def bridge_ledge(cv, x, y, side, pal, door=True, glow_r=5):
    """吊桥的桥头：从石柱 x 那一侧（side = 朝哪边伸）在 y 这一行凿出一块小石台，石台里侧凿一扇亮着的小门
    （人从门里出来上桥）。返回 (桥面该从哪一格开始, y)。"""
    xs = np.nonzero(cv.a[int(y), :, 3])[0]
    e = stone_edge(cv, int(xs[np.abs(xs - x).argmin()]), y, side)     # 柱子会歪：从这一行离 x 最近的那格石头往外找
    a, b = (e - 3, e + 6) if side > 0 else (e - 5, e + 4)
    cv.rect(a, y, b, y + 3, pal[2])
    cv.hline(a, b, y, pal[-1])
    cv.hline(a, b, y + 3, DARK)
    for i in range(2):                            # 石台底下凿出来的托，贴着柱子收进去
        if side > 0:
            cv.hline(a, b - 2 - 2 * i, y + 4 + i, pal[1])
        else:
            cv.hline(a + 2 + 2 * i, b, y + 4 + i, pal[1])
    if door:
        dx = e - 9 if side > 0 else e + 6
        BM.carve(cv, dx, y - 8, 4, 8, "arch", True, True, pal=pal, glow_r=glow_r)
    return (b if side > 0 else a - 1), y


# ---------------------------------------------------------------- 石头住处（作者 10-30：不要砖房、不要吊脚楼——
# 房子是巨石 / 石柱里凿出来的洞窟屋，或者大块粗石垒的矮屋；门窗是石头里凿出的洞。石头的画法直接用河岸那份
# tools/river_bank_moon_art.py 的 boulder_house / stone_hut / carve / shade_mass，三个房间的石头一个样）

# ---------------------------------------------------------------- 石头的质感（10-30 第四版：质量优先）
# 作者点赞的那一屏里，石柱是 RA.pillar 画的：几个干净的竖切面（背光 / 中间 / 受光）、右沿一道亮边、顶面亮、被自己挡住的地方落进最暗，
# 没有满屏棋盘格。所以这里所有石头都走同一套：形 → RA.shade_rock 切面 → weather() 加磨损的边角、苔、往下淌的水渍、小坑。
# 大片横着的石面（平台下的岩架、码头）用 mass()：BM.shade_mass 的大块明暗，但档边不抖（抖动会像脏了）。

def _pal_index(img, pal):
    """RGBA 每个像素在 pal 里最近的档（-1 = 透明）。"""
    p = np.array([c[:3] for c in pal], int)
    d = ((img[..., None, :3].astype(int) - p[None, None]) ** 2).sum(-1)
    idx = d.argmin(-1)
    idx[img[..., 3] == 0] = -1
    return idx


def weather(img, rng, pal, moss=0.5, stains=None, chips=None, pits=None):
    """给一张石头 RGBA 加岁月：外沿磨掉几个角（缺口里一格影子）、顶上一层苔（偶尔垂一两格）、
    从顶面往下淌的水渍（暗一档、断断续续）、几个风蚀小坑（坑里暗、右下唇亮）。就地改，返回 img。"""
    h, w = img.shape[:2]
    a = img[..., 3] > 0
    if not a.any():
        return img
    idx = _pal_index(img, pal)
    n = len(pal)
    cols = np.nonzero(a.any(0))[0]
    tops = {x: int(np.nonzero(a[:, x])[0][0]) for x in cols}
    area = int(a.sum())
    # 磨损的边角：外沿上挑几处，抠掉 1~3 格，缺口里面那格压暗
    for _ in range(chips if chips is not None else max(2, area // 900)):
        x = int(rng.choice(cols))
        ys = np.nonzero(a[:, x])[0]
        y = int(ys[0]) if rng.random() < 0.6 else int(rng.choice(ys))
        side = 1 if rng.random() < 0.5 else -1
        for k in range(int(rng.integers(1, 4))):
            xx = x + side * k
            if 0 <= xx < w and a[y, xx] and (y == 0 or not a[y - 1, xx] or xx in (0, w - 1)
                                              or not a[y, max(0, xx - 1)] or not a[y, min(w - 1, xx + 1)]):
                img[y, xx, 3] = 0
                if y + 1 < h and a[y + 1, xx]:
                    img[y + 1, xx, :3] = pal[max(0, idx[y + 1, xx] - 1)]
    a = img[..., 3] > 0
    # 水渍：从顶面往下淌，暗一档，一格宽，断断续续
    for _ in range(stains if stains is not None else max(2, len(cols) // 9)):
        x = int(rng.choice(cols))
        y = tops[x] + int(rng.integers(1, 4))
        for k in range(int(rng.integers(5, 22))):
            yy = y + k
            if yy >= h or not a[yy, x]:
                break
            if rng.random() < 0.8 and idx[yy, x] > 0:
                img[yy, x, :3] = pal[idx[yy, x] - 1]
            if rng.random() < 0.08:
                x = min(w - 1, max(0, x + int(rng.choice([-1, 1]))))
    # 风蚀小坑
    for _ in range(pits if pits is not None else max(1, area // 1400)):
        ys, xs = np.nonzero(a)
        k = int(rng.integers(len(ys)))
        y, x = int(ys[k]), int(xs[k])
        if 1 <= y < h - 1 and 1 <= x < w - 1 and a[y - 1:y + 2, x - 1:x + 2].all():
            img[y, x, :3] = pal[0]
            img[y + 1, x + 1, :3] = pal[min(n - 1, max(idx[y + 1, x + 1], 0) + 1)]
    # 苔：顶面一层，偶尔垂下来一两格
    if moss:
        for x in cols:
            y = tops[x]
            if img[y, x, 3] and rng.random() < moss:
                img[y, x, :3] = BM.MOSS[2] if rng.random() < 0.35 else BM.MOSS[1]
                if rng.random() < 0.18:
                    for d in range(1, int(rng.integers(2, 5))):
                        if y + d < h and img[y + d, x, 3]:
                            img[y + d, x, :3] = BM.MOSS[0]
    return img


def stone_img(m, seed, pal=None, cracks=None, moss=0.5, **kw):
    """一块石头的形 m（bool）→ 上好色的 RGBA。第六版起直接用河岸的 BM.stone_shade（柱状节理切面、小色团、右沿冷亮边、
    底部 AO、自投影、岩层台、分叉细裂、苔、水渍）——整章的石头一个画法。cracks / chips 这些旧参数不用了。"""
    pal = pal or BM.STONE
    rng = np.random.default_rng(seed)
    w = m.shape[1]
    return BM.stone_shade(m, rng, pal, facet_w=max(6.0, w / 5), ledges=0.6, moss=0.6 if moss else 0.0)


def mass(m, rng, pal, cracks=4, strata=3, amp=0.5):
    """大片横着的石面：和 BM.shade_mass 一样的大块明暗（顶面受光、右沿亮、左沿暗、往下爬的裂缝、不贯通的岩层缝），
    但档边是干净的（不抖）——一块块不规则的明暗斑，像风化的石面，不像脏了。"""
    h, w = m.shape
    n = len(pal)
    nz = RA.vnoise(h, w, 22, 34, rng) * 0.7 + RA.vnoise(h, w, 6, 9, rng) * 0.3
    v = 0.3 + amp * (nz - 0.5)
    top = np.full(w, h)
    for x in range(w):
        ys = np.nonzero(m[:, x])[0]
        if len(ys):
            top[x] = ys[0]
    Y = np.arange(h)[:, None]
    v = v + 0.5 * np.exp(-np.clip(Y - top[None, :], 0, None) / 4.0)
    xl = np.full(h, w)
    xr = np.full(h, -1)
    for y in range(h):
        xs = np.nonzero(m[y])[0]
        if len(xs):
            xl[y], xr[y] = xs[0], xs[-1]
    X = np.arange(w)[None, :]
    v = v + 0.32 * np.exp(-np.clip(xr[:, None] - X, 0, None) / 3.0) - 0.22 * np.exp(-np.clip(X - xl[:, None], 0, None) / 6.0)
    idx = np.clip(np.floor(v * (n - 1) + 0.5), 0, n - 1).astype(int)
    img = np.zeros((h, w, 4), np.uint8)
    for k in range(n):
        mm = m & (idx == k)
        img[mm, :3] = pal[k]
        img[mm, 3] = 255
    for _ in range(cracks):                       # 裂缝：往下爬，暗一档、右唇亮一档
        xs = np.nonzero(m.any(0))[0]
        x = float(rng.uniform(xs[0] + 4, xs[-1] - 4))
        y = float(top[int(x)] + rng.uniform(2, 10))
        for s in range(int(rng.integers(8, 30))):
            xi, yi = int(round(x)), int(round(y))
            if 0 <= yi < h and 0 < xi < w - 1 and m[yi, xi] and m[yi, xi + 1]:
                img[yi, xi, :3] = pal[0]
                img[yi, xi + 1, :3] = pal[min(n - 1, idx[yi, xi + 1] + 1)]
            x += rng.uniform(-0.7, 0.7)
            y += 1
    for _ in range(strata):                       # 岩层缝：横的一段，不贯通
        y = int(rng.uniform(h * 0.2, h * 0.9))
        x = int(rng.uniform(0, w * 0.6))
        ln = int(rng.uniform(w * 0.15, w * 0.45))
        for k in range(ln):
            yy = y + int(round(1.5 * np.sin(k / 9.0)))
            if 0 <= yy < h - 1 and 0 <= x + k < w and m[yy, x + k]:
                img[yy, x + k, :3] = pal[0]
                if m[yy + 1, x + k]:
                    img[yy + 1, x + k, :3] = pal[min(n - 1, idx[yy + 1, x + k] + 1)]
    return img


def warm_spill(cv, cx, cy, r, strength=0.42):
    """洞里 / 灯里溢出来的暖光：只落在已经画了的石头上（暖色的像素不动），三档，按距离很快衰减，不抖。"""
    for y in range(int(cy - r), int(cy + r) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            o = cv.get(x, y)
            if o is None or o[0] - o[2] > 10:
                continue
            d = np.hypot(x - cx, (y - cy) * 1.15) / r
            if d > 1:
                continue
            t = strength * (1.0 if d < 0.4 else (0.5 if d < 0.7 else 0.2))
            cv.px(x, y, mix(o, BM.WARM[1], round(t * 16) / 16))


def opening(cv, x, y, w, h, kind="arch", lit=True, door=False, pal=None, glow_r=None, spill=True):
    """石头上凿出来的门 / 窗。第六版起整章统一用河岸的 BM.carve（左内壁接月光、右内壁和门楣底面在影子里、门楣受光、
    窗台石板、洞口磨损、每扇窗亮度和样子不一样）+ BM.door_spill（门外地上的光）。seed 按位置定，同一扇窗每次一样。"""
    BM.carve(cv, x, y, w, h, kind, lit, door, pal=pal or BM.STONE, glow_r=glow_r, seed=(x * 7919 + y * 104729) % 100000)
    if door and lit and spill:
        BM.door_spill(cv, x, w, y + h + 1)


def lamp_post(cv, x, base, h=26, pal=None):
    """路灯：一根凿出来的细石柱（3 宽），顶上一块挑出的石帽，帽下凿空的灯室里一盏暖灯。x = 柱子中线，base = 地面。"""
    pal = pal or BM.STONE
    top = base - h
    BM.glow(cv, x + 0.5, top - 3, 16)
    cv.rect(x - 2, base - 3, x + 3, base + 1, pal[2])           # 柱脚
    cv.hline(x - 2, x + 3, base - 3, pal[4])
    cv.vline(x + 2, base - 3, base + 1, pal[4])
    cv.rect(x - 1, top, x + 2, base - 3, pal[2])                # 柱身
    cv.vline(x - 1, top, base - 3, pal[1])
    cv.vline(x + 1, top, base - 3, pal[4])
    cv.rect(x - 2, top - 7, x + 3, top, pal[1])                 # 灯室（两根细柱夹着灯）
    cv.rect(x - 1, top - 6, x + 2, top - 1, W_LAMP[1])
    cv.px(x, top - 4, W_LAMP[3])
    cv.px(x, top - 3, W_LAMP[2])
    cv.hline(x - 1, x + 2, top - 6, W_LAMP[0])
    cv.vline(x + 2, top - 7, top, pal[3])
    cv.rect(x - 3, top - 10, x + 4, top - 7, pal[2])            # 石帽
    cv.hline(x - 3, x + 4, top - 10, pal[-1])
    cv.vline(x + 3, top - 10, top - 7, pal[4])
    cv.hline(x - 2, x + 3, top - 11, pal[3])


IRON = BM.B(.07, .015, 262)
IRON_LIT = BM.B(.15, .02, 248)                    # 铁件朝月光的那一格 / 铆钉


def stone_edge(cv, x, y, side):
    """这一行石头朝 side 那边的最外一格（x 在石头里就往外走到边，在石头外就往回找到边）。"""
    a = cv.a[int(y), :, 3]
    xx = int(x)
    if a[xx]:
        while 0 <= xx + side < cv.w and a[xx + side]:
            xx += side
    else:
        while 0 <= xx < cv.w and not a[xx]:
            xx -= side
    return xx


def bracket_lamp(cv, x, y, side=1, arm=6):
    """石柱上钉一根铁臂，臂头挂一盏小提灯。x 只是大概位置：先找到这一行石头的边，铁臂从石头里钉出来——
    石面上一块铁板（一颗铆钉亮）、一根平臂、一根斜撑，斜撑的脚也钉在石头上。
    （10-30 作者实机：铁臂后面什么都没有、灯悬在半空。灯一定要挂在实物上。）"""
    w0 = stone_edge(cv, x, y, side)
    w1 = stone_edge(cv, w0, y + 5, side)
    ex = w0 + side * arm
    for (wx, wy) in ((w0, y), (w1, y + 5)):       # 两块钉在石面上的铁板
        cv.rect(min(wx, wx - side), wy - 1, max(wx, wx - side) + 1, wy + 2, IRON)
        cv.px(wx - side, wy, IRON_LIT)
    cv.line(w0, y, ex, y, IRON)
    cv.line(w0 + side, y - 1, ex - side, y - 1, IRON_LIT)     # 平臂上沿接一点月光
    cv.line(w1 + side, y + 5, w0 + side * (arm - 2), y, IRON)
    cv.px(ex + side, y + 1, IRON)                 # 臂头往下一勾
    BM.lantern(cv, ex, y + 6, "hang", r=10)


def hang_chain(cv, x, y0, y1, pal=None):
    """一根从 y0（石头底面）垂到 y1 的铁链：一格亮一格暗，看得出是链子；顶上一个钉进石头的环，挨着灯的两格被灯照暖。"""
    pal = pal or BM.STONE
    for yy in range(y0, y1):
        cv.px(x, yy, pal[3] if (yy - y0) % 2 == 0 else pal[1])
    cv.hline(x - 1, x + 1, y0, IRON_LIT)
    cv.px(x, y1 - 1, HUSK)
    cv.px(x, y1 - 2, BM.WARM[0])


def chain_lamp(cv, x, y, ceil):
    """拱顶 / 门洞顶上一根铁链吊下来的提灯。ceil = 拱顶石头最下一行，y = 灯芯。"""
    BM.lantern(cv, x, y, "hang")
    hang_chain(cv, x, ceil + 1, y - 2)


def lamp_niche(cv, x, y, pal=None):
    """石头上凿进去的一个灯龛，里面坐着一盏方灯（嵌在石头里的灯）。(x, y) = 龛的左上，龛 7×10。"""
    opening(cv, x, y, 7, 10, "arch", False, pal=pal or BM.STONE)
    BM.lantern(cv, x + 3, y + 6, "post", r=9)
    cv.hline(x, x + 7, y + 10, (pal or BM.STONE)[4])      # 龛底的石台受光


W_LAMP = [BM.WARM[1], BM.WARM[2], BM.WARM[3], BM.WARM[4]]


def boulder(cv, cx, base, w, h, seed, openings=(), pipe=None, pal=None):
    """巨石屋：BM.boulder_house 的石头，门窗换成上面的 opening（门洞里有明暗）。openings 同 BM：(形, 离左 x, 离地 y, 宽, 高, 亮, 门)。"""
    pal = pal or BM.STONE
    rng = np.random.default_rng(seed)
    m = BM.blob_mask(w, h, rng)
    img = stone_img(m, seed, pal, moss=0.55)
    x0, y0 = int(cx - w // 2), int(base - h + 1)
    cv.paste(img, x0, y0)
    if pipe:                                      # 顶上一截铁皮烟囱
        px_ = x0 + pipe
        ty = y0 + int(np.nonzero(m[:, pipe])[0][0])
        cv.rect(px_, ty - 7, px_ + 3, ty + 1, BM.B(.1, .015, 250))
        cv.vline(px_ + 2, ty - 7, ty + 1, BM.B(.17, .02, 246))
        cv.hline(px_ - 1, px_ + 4, ty - 7, BM.B(.17, .02, 246))
    for (kind, ox, oy, ow, oh, lit, door) in openings:
        opening(cv, x0 + ox, base - oy - oh + 1, ow, oh, kind, lit, door, pal=pal)
    return x0, y0


def rock(cv, x0, x1, base, top, seed, p=4.0, pal=None, moss=True):
    """一整块石头（底平、顶圆鼓，p 越大越方）。返回 (img, 左上 x, 左上 y)。"""
    rng = np.random.default_rng(seed)
    w, h = int(x1 - x0), int(base - top + 1)
    m = BM.blob_mask(w, h, rng, p=p, lump=0.06)
    img = stone_img(m, seed, pal, moss=0.5 if moss else 0, chips=None if w >= 12 else 0)
    cv.paste(img, int(x0), int(top))
    return img, int(x0), int(top)


def pillar_rock(cv, cx, base, w, h, seed, pal=None):
    """一根宽石柱（RA.pillar 的形：边上风化缺口、微微歪），柱脚在 base、中线 cx。旧街下层的人家都凿在这种柱子里。"""
    img = BM.stone_pillar(w, h, seed, pal or BM.STONE, crown=[BM.B(.07, .02, 258), BM.B(.1, .022, 252)], kind="tower")
    ox, oy = int(cx - img.shape[1] // 2), int(base - img.shape[0] + 1)
    cv.paste(img, ox, oy)
    return img, ox, oy


def dwelling_pillar(cv, x, base, w, h, seed, wins, door_y=None, door_side=1, pal=None):
    """一根石柱，柱身上凿出人家：wins = [(相对底的 dy, 形, 宽, 高, 亮, 门)]；door_y 那一行开一扇门，门口伸出一块石台。
    返回石台外沿的 x（细桥从这里搭出去）。"""
    pal = pal or BM.STONE
    img = BM.stone_pillar(w, h, seed, pal, crown=[BM.B(.07, .02, 258), BM.B(.1, .022, 252)], kind="tower")
    ox, oy = int(x - img.shape[1] // 2), int(base - img.shape[0] + 1)
    cv.paste(img, ox, oy)
    for (dy, kind, ww, hh, lit, door) in wins:
        r = BM.rows_of(img, ox, oy, base + dy + hh // 2)
        if r:
            opening(cv, (r[0] + r[1]) // 2 - ww // 2, base + dy, ww, hh, kind, lit, door, pal=pal)
    if door_y is None:
        return x
    r = BM.rows_of(img, ox, oy, door_y - 6)
    if door_side > 0:
        opening(cv, r[1] - 10, door_y - 13, 7, 13, "arch", True, True, pal=pal)
        a, b = r[1] - 4, r[1] + 9
    else:
        opening(cv, r[0] + 4, door_y - 13, 7, 13, "arch", True, True, pal=pal)
        a, b = r[0] - 9, r[0] + 4
    vines(cv, a + 1, b - 1, door_y + 5, seed + 3, n=2, max_len=10)
    cv.rect(a, door_y, b, door_y + 4, pal[2])
    cv.hline(a, b, door_y, pal[-1])
    cv.hline(a, b, door_y + 4, DARK)
    cv.vline(b - 1, door_y, door_y + 4, pal[-2])
    return b if door_side > 0 else a


def rock_town(width, spots, seed, foot=H + 6, pal=None, wl=None, refl=12):
    """中景：一根根从下面（水里）升上来的石柱，柱身上凿着几扇小窗（多数亮着），有的柱顶压着一间粗石小屋。
    spots = [(x, 柱顶 y, 柱宽, 窗数, 顶上有没有小屋)]。返回 (画布, [(x, 柱顶, 宽)])。"""
    pal = pal or BM.STONE_FAR
    cv = Cv(width)
    tops = []
    for i, (x, top, pw, nwin, hut) in enumerate(spots):
        rng = np.random.default_rng(seed + i)
        img = BM.stone_pillar(pw, foot - top, seed + i, pal,
                              crown=None if hut else [BM.B(.1, .02, 256), BM.B(.13, .022, 250)], kind="tower")
        ox, oy = int(x - img.shape[1] // 2), int(foot - img.shape[0])
        if wl is None:
            cv.paste(img, ox, oy)
        else:                                      # 10-30：柱子立在水里——水线一条连着的湿亮线，下面不透明的倒影（河岸的 BM.water_foot）
            lw = wl - oy
            out, pad = BM.water_foot(img[:lw + 1], lw, seed + 70 + i, refl=refl)
            cv.paste(out, ox - pad, oy)
        ty = oy + int(np.nonzero(img[..., 3].any(1))[0][0])
        for k in range(nwin):
            y = ty + 10 + k * int(rng.integers(14, 22))
            if wl is not None and y > wl - 8:          # 水线以下不开窗
                break
            r = BM.rows_of(img, ox, oy, y + 1)
            if r and r[1] - r[0] > 8:
                cx_ = (r[0] + r[1]) // 2 + int(rng.integers(-3, 4))
                opening(cv, cx_ - 1, y, 3, 4, "arch", rng.random() < 0.8, False, pal=pal, glow_r=5)
        if hut:                                   # 柱顶凿出一户：一扇亮着的门洞，门边挂一盏小灯
            r = BM.rows_of(img, ox, oy, ty + 8)
            if r and r[1] - r[0] > 10:
                cx_ = (r[0] + r[1]) // 2
                opening(cv, cx_ - 2, ty + 4, 5, 8, "arch", True, True, pal=pal, glow_r=7, spill=False)
                lantern(cv, min(cx_ + 5, r[1] - 4), ty + 5, hang=2)     # 灯整盏落在柱面上（挂在门边石头上，不伸出柱外）
        tops.append((x, ty, pw))
    return cv, tops


def statue_on_column(cv, x, base, seed, pal=None):
    """提灯人立在石柱顶上：BM.lantern_statue 画在一张小画布上，只取水线以上那截（水线那一行起是涟漪和水下的倒影），
    底下一块凿平的石座（上沿受月光、右沿亮一档、下面一行影子），石座下面一根石柱一直伸到画面外。base = 石座上沿。"""
    pal = pal or BM.STONE_FAR
    st = Cv(80)
    BM.lantern_statue(st, 40, 100, seed=seed)
    rng = np.random.default_rng(seed + 7)          # 柱身：一根直的方石柱（两边各有 0~2 格的起伏），材质照河岸的 stone_shade
    ch = H + 6 - base - 4
    lw, rw = RA.smooth1d(ch, rng, 30, 1.0), RA.smooth1d(ch, rng, 26, 1.0)
    m = np.zeros((ch, 36), bool)
    for yy in range(ch):
        m[yy, 2 + int(round(1 + lw[yy])):34 - int(round(1 + rw[yy]))] = True
    cv.paste(BM.stone_shade(m, rng, pal, facet_w=8), x - 18, base + 4)
    for yy in range(base, base + 5):              # 石座：比柱子宽一圈、比人像脚宽一点
        cv.hline(x - 21, x + 20, yy, pal[2] if yy < base + 4 else pal[0])
    cv.hline(x - 21, x + 20, base, pal[4])
    cv.vline(x + 20, base, base + 3, pal[3])
    cv.vline(x - 21, base + 1, base + 4, pal[1])
    cv.hline(x - 17, x + 16, base + 5, pal[0])    # 石座压在柱头上的一道影子
    cv.paste(st.a[:100], x - 40, base - 100)
    for xx in range(x - 16, x + 18):              # 人像脚下贴着石座的一行接触暗
        if cv.a[base - 1, xx, 3]:
            cv.px(xx, base, mix(cv.get(xx, base), pal[0], 0.5))


def rewarm(cv):
    """雾褪过以后，窗里的暖光拉回来一点（雾里的灯不该被雾吃掉太多）。"""
    a = cv.a
    warmish = (a[..., 0].astype(int) - a[..., 2].astype(int) > 20) & (a[..., 3] > 0)
    for y, x in zip(*np.nonzero(warmish)):
        a[y, x, :3] = mix(a[y, x, :3], WARM[2], 0.5)


def carved_sign(m, x, y, kind, pal=None):
    """刻在石壁上的旧店招：一块浅浅凿进去的方框（框内暗一档），里面的记号是凿出来的槽（暗）+ 下沿一格亮（石唇）。"""
    pal = pal or BM.STONE
    m.rect(x, y, x + 18, y + 9, pal[1])
    m.hline(x, x + 18, y, DARK)
    m.vline(x, y, y + 9, DARK)
    m.hline(x, x + 18, y + 9, pal[4])
    m.vline(x + 18, y, y + 10, pal[3])
    for (dx, dy) in SIGN_GLYPH[kind]:
        m.px(x + dx, y + dy + 1, DARK)
        if (dx, dy + 1) not in SIGN_GLYPH[kind]:
            m.px(x + dx, y + dy + 2, pal[3])
    for k in range(0, 18, 3):
        m.px(x + k + 1, y + 8, BM.MOSS[1])


def wood_sign(m, x, y, kind):
    """今天挂着的木店招：一块木牌，记号用暖色描（和旧的刻在石头上的那块一模一样——同名店）。"""
    m.rect(x, y, x + 18, y + 8, BM.WOOD[2])
    m.hline(x, x + 18, y, BM.WOOD[4])
    m.hline(x, x + 18, y + 7, BM.WOOD[0])
    for (dx, dy) in SIGN_GLYPH[kind]:
        m.px(x + dx, y + dy, BM.WARM[2])
    m.vline(x + 3, y - 3, y, BM.B(.07, .015, 262))
    m.vline(x + 15, y - 3, y, BM.B(.07, .015, 262))


SIGN_GLYPH = {
    "cup": [(6, 2), (7, 2), (8, 2), (9, 2), (10, 2), (6, 3), (10, 3), (11, 3), (12, 4), (6, 4), (10, 4), (11, 5),
            (7, 5), (8, 5), (9, 5)],
    "jar": [(7, 2), (8, 2), (9, 2), (10, 2), (6, 3), (11, 3), (6, 4), (8, 4), (9, 4), (11, 4), (6, 5), (11, 5),
            (7, 6), (8, 6), (9, 6), (10, 6)],
}


def vines(cv, x0, x1, y, seed, n=3, max_len=14):
    """从石沿下挂下来的几根藤 / 根须：一格宽、长短不一、微微摆，末端偶尔一片小叶；暗苔色，不抢眼。"""
    rng = np.random.default_rng(seed)
    for _ in range(n):
        x = float(rng.uniform(x0, x1))
        ln = int(rng.integers(4, max_len + 1))
        ph = rng.uniform(0, 6)
        for k in range(ln):
            xx = int(round(x + 0.8 * np.sin(k / 3.5 + ph)))
            cv.px(xx, y + k, BM.MOSS[0] if k > 2 else BM.MOSS[1])
            if rng.random() < 0.12:
                cv.px(xx + (1 if rng.random() < 0.5 else -1), y + k, BM.MOSS[1])


def ledge(m, a, b, y, pal=None):
    """从石壁上伸出来的一块石台（今天的门口，在水面以上）：厚 4，上沿亮，下面一道影子，底下一个凿出来的托。"""
    pal = pal or BM.STONE
    m.rect(a, y, b, y + 4, pal[2])
    m.hline(a, b, y, pal[-1])
    m.hline(a, b, y + 4, DARK)
    m.vline(b - 1, y, y + 4, pal[-2])
    for k in range(3):
        m.hline(a + 2 + k, b - 2 - k, y + 5 + k, pal[1])
    vines(m, a + 2, b - 2, y + 5, a * 7 + y, n=2, max_len=9)


# ---------------------------------------------------------------- 水

def water_img(width, h=120):
    """水层（Godot 里 alpha 0.55、在人前面）：最上一行是月光照亮的水面线，往下很快暗下去。"""
    cv = Cv(width, h)
    rng = np.random.default_rng(3)
    for y in range(h):
        L = .22 - .1 * min(1, y / 40) - .03 * min(1, y / 100)
        cv.hline(0, width, y, C(L, 254))
    wob = RA.smooth1d(width, rng, 46, 1.0)
    for x in range(width):                  # 水面线：一条连着的湿亮线（10-30：原来是 3 格一段的虚线），亮度跟一条慢噪声起伏
        cv.px(x, 0, C(.35 if wob[x] > -0.4 else .31, 250))
        cv.px(x, 1, C(.27 if wob[x] > 0.15 else .245, 252))
    for _ in range(width // 14):            # 水下几道很淡、很长的横纹（不排成一行）
        x, y = rng.integers(0, width), rng.integers(5, 40)
        cv.hline(x, x + rng.integers(14, 34), y, C(.2, 252))
    return cv


def ripples_img(width, lamps, h=14, seed=4):
    """水面上一闪一闪的横纹（water shader 按 7 像素一段让它们出没）；灯底下一串碎的暖倒影。"""
    rng = np.random.default_rng(seed)
    cv = Cv(width, h)
    for y in range(2, h, 2):                # 从水面线下面一行开始（ripples 层 y 比水面高 1 格：第 0、1 行不画，水纹不上岸）
        for _ in range(width // (10 + y * 2)):
            x = rng.integers(0, width)
            cv.hline(x, x + rng.integers(2, 6 - y // 4), y, C(.36 - y * .012, 250))
    for lx in lamps:                        # 灯的倒影：一条连着的暖带，往下变窄变暗，每行左右错一格（10-30：原来是一摞等距的短横）
        for y in range(2, 11):
            x0 = lx + int(rng.integers(-1, 2))
            hw = 1 if y < 7 else 0
            cv.hline(x0 - hw, x0 + 2, y, REFL[1] if y < 5 else (REFL[0] if y < 8 else HALO))
    return cv


# ---------------------------------------------------------------- 市集 market（1440 宽，地面 200）

MK_W, MK_G = 1440, 200
# 10-30 作者：「后面还是有一部分河流在地面之上」。市集在河岸正上方 270 像素，人站在高处往远处看，河在脚下：
# 原来天 / 远石柱 / 雾 / 月光碎片照搬河岸那套（地平线 150），水面占了画面 40%~65%，比桥面（200）高出一大截。
# 现在地平线压到桥面上面 4 行：桥面上只露对岸一线和一线水光，近一点的河要从桥下的拱洞里往下看；天多露 46 行，显得高。
MK_HZ = 196
MK_DY = MK_HZ - RA.HORIZON          # 河岸的 ridge / mist 整层往下挪这么多


def market_sky():
    """市集自己的天（从河岸的 art/river/sky.png 改，那张不动）：云和月亮那截（0..123）原样（月亮还在 x=338，月光条对得上）；
    云下到地平线那段渐变按河岸的亮度表重算、拉长到 MK_HZ（同一套 Bayer 抖动）；地平线以下接原图的水。"""
    src = np.array(Image.open(ROOT / "art" / "river" / "sky.png").convert("RGBA"))
    out = np.zeros_like(src)
    out[:SKY_KEEP] = src[:SKY_KEEP]
    xs = np.arange(RA.SW)
    mw, _ = RA.milky_way_field()
    for y in range(SKY_KEEP, MK_HZ):
        ys = sky_row(y, MK_HZ)
        L = RA.bg_L(xs, ys) + mw[min(int(ys), RA.HORIZON - 1)]
        lo = np.floor(L / RA.L_STEP)
        idx = lo + (RA.BAYER[y % 4, xs % 4] < (L / RA.L_STEP - lo))
        for x in xs:
            out[y, x] = RA.rgba(RA.L_color(idx[x] * RA.L_STEP, ys))
    out[MK_HZ:] = src[RA.HORIZON:RA.HORIZON + H - MK_HZ]
    return out


def market_moonpath():
    """月光条遮罩（给 scripts/river_moonpath.gdshader；通道含义见 river_bank_moon_art.moonpath_img）：从市集的地平线下一行铺到画面底，
    还是对着月亮的那一竖条、上亮下暗、上密下稀。桥面上面只露 3 行（远处一线水光），其余要从桥下的拱洞里才看得见。
    视差：贴着地平线的远水 0.16，拱洞里看到的近一点的水 0.3~0.45（都比中景石柱 0.6 慢，河在它们脚下更远处）。"""
    y0 = MK_HZ + 1
    a = np.zeros((H - y0, RA.SW, 4), np.uint8)
    for y in range(y0, H):
        d = y - y0
        dens = np.interp(d, (0, 15, 45, 73), (0.85, 0.7, 0.45, 0.3))
        if BM._hash01(0, y, 13) < 0.3:
            dens *= 0.4
        lvl = np.interp(d, (0, 15, 45, 73), (1.0, 0.92, 0.75, 0.62))
        sc = float(np.interp(y, (y0, 214, H), (0.16, 0.3, 0.45)))
        lo = BM.MOON_X - BM.MOON_HW - int(BM._hash01(y // 2, 1, 93) * 3)
        hi = BM.MOON_X + BM.MOON_HW + int(BM._hash01(y // 2, 2, 93) * 3)
        for x in range(lo, hi):
            u = abs(x + 0.5 - BM.MOON_X) / (hi - lo) * 2
            f = max(0.0, 1.0 - u ** 2)
            a[y - y0, x] = (int(255 * lvl * (0.7 + 0.3 * f)), int(round(sc / 2 * 255)), int(255 * dens * (0.3 + 0.7 * f)), 255)
    return a


STALL_X0, STALL_X1 = 290, 388    # 修补摊两根立柱（左柱贴着石柱，右柱在灯那头）
STALL_ROD = 160                   # 挂工具的横杆那一行 = market_tools 物件的 y（物件第 0、1 行就是这根杆）


def repair_stall(m, G):
    """修补摊（10-31 作者：「这个右侧悬空的东西是啥」——原来只有一条布篷 + 一根横杆，左边和中间没撑，浮在半空）。
    现在：两根木立柱插进桥面（脚下一圈铁箍），一根顶梁左头凿进石柱、右头搭在右柱上，布篷搭在顶梁上；
    两根斜撑托着顶梁；横杆两头绑在立柱上（工具挂在杆上，是 market_tools 物件）；杆下一张摊桌，桌上台钳、补了一半的壶、
    一盒零件，桌下一只木箱、一只铁桶。光从右上：木头右边和上沿亮一档；灯挂在杆的右头，只照右半张桌子和右柱。"""
    W = RA.bramp(5, .12, .36, 256, 242)          # 风吹日晒发白的旧木头（BM.WOOD 太黑，在雾前面成了一块剪影）
    x0, x1, rod = STALL_X0, STALL_X1, STALL_ROD
    beam = rod - 14                                # 顶梁（146、147 两行）
    # 顶梁：左头凿进石柱（梁头伸进去 4 格，梁上下两道凿口的影子），右头搭在右柱上再伸出 3 格
    edge = x0 - 1
    while edge > x0 - 40 and not m.a[beam, edge, 3]:
        edge -= 1                                  # 石柱这一行的右边沿
    bl = edge - 4
    m.rect(bl, beam, x1 + 6, beam + 2, W[2])
    m.hline(bl, x1 + 6, beam, W[3])
    m.vline(x1 + 5, beam, beam + 2, W[4])
    m.hline(bl - 1, edge + 1, beam - 1, STONE[1])  # 凿口：梁上沿一道浅槽、梁下一道影子
    m.hline(bl - 1, edge + 1, beam + 2, STONE[0])
    m.vline(bl - 1, beam - 1, beam + 3, STONE[0])
    # 布篷：搭在顶梁上往前垂，左高右低一点；竖条布纹（6 格一条），右边受光亮一档；
    # 下沿是一整条起伏的边（一段 3~8 格长低一格、再一段高回来），不是一格一格的毛刺（像虚线）
    sag, run, x = {}, 0, edge - 2
    while x < x1 + 6:
        n = 3 + int(BM._hash01(x, 5, 91) * 6)
        for k in range(n):
            sag[x + k] = run % 2
        run += 1
        x += n
    for x in range(edge - 2, x1 + 6):
        yb = beam + 8 + (x - x0) // 40 + sag[x]
        lit = x > x0 + (x1 - x0) * 2 // 3
        a, b = (BM.B(.13, .03, 230), BM.B(.16, .03, 226)) if not lit else (BM.B(.15, .03, 228), BM.B(.18, .03, 224))
        m.vline(x, beam + 2, yb, a if (x // 6) % 2 else b)
        m.px(x, beam + 2, BM.B(.24, .03, 222))
        m.px(x, yb - 1, BM.B(.11, .03, 232))       # 下沿往里卷的那道折边（暗一档）
    # 两根立柱：3 宽，左边暗、右边亮；从顶梁一直插到桥面下面，脚下一圈铁箍 + 桥面上一道接缝的影子
    for px_ in (x0, x1):
        m.rect(px_ - 1, beam, px_ + 2, G + 2, W[2])
        m.vline(px_ - 1, beam, G + 2, W[1])
        m.vline(px_ + 1, beam, G + 2, W[4])
        m.rect(px_ - 2, G - 3, px_ + 3, G, IRON)
        m.hline(px_ - 2, px_ + 3, G - 3, IRON_LIT)
        m.px(px_ + 2, G - 2, IRON_LIT)
        m.hline(px_ - 3, px_ + 4, G, STONE[0])
        m.rect(px_ - 1, beam - 1, px_ + 2, beam, W[3])         # 柱头顶着梁，露出一格柱头
    # 斜撑：立柱往里斜着顶到顶梁下（2 宽，上沿亮）
    for k in range(9):
        for sx, d in ((x0 + 2, 1), (x1 - 2, -1)):
            xx, yy = sx + d * k, rod + 2 - k
            if yy <= beam + 1:
                continue
            m.px(xx, yy, W[3])
            m.px(xx, yy + 1, W[2])
            m.px(xx, yy - 1, W[4] if d < 0 else W[3])
    # 横杆：两头绑在立柱上（物件自己也画了中间那段杆，两头接上）；绳圈 3 道，最上一道亮
    m.rect(x0 - 1, rod, x1 + 2, rod + 2, W[1])
    m.hline(x0 - 1, x1 + 2, rod, W[2])
    rope = [BM.B(.22, .014, 80), BM.B(.3, .016, 84)]   # 麻绳：灰白，不带暖色（灯只照右头）
    for px_ in (x0, x1):
        for k, yy in enumerate((rod - 1, rod, rod + 1, rod + 2)):
            m.hline(px_ - 2, px_ + 3, yy, rope[1] if k == 0 else rope[0])
        m.px(px_ + 2, rod + 1, rope[1])
    # 摊桌：桌面两行（上沿受光），前面一块挡板（右头亮一档），两条腿，桌下一块搁板
    tx0, tx1, ty = x0 + 5, x1 - 4, 186
    m.rect(tx0, ty, tx1, ty + 2, W[3])
    m.hline(tx0, tx1, ty, W[4])
    m.rect(tx0, ty + 2, tx1, ty + 6, W[2])
    m.hline(tx0, tx1, ty + 5, W[1])
    for k in range(tx0 + 14, tx1, 22):            # 挡板上几道木板缝（不是虚线：整条竖缝）
        m.vline(k, ty + 2, ty + 5, W[1])
    m.vline(tx1 - 1, ty, ty + 6, W[4])
    for lx in (tx0 + 2, tx1 - 4):
        m.rect(lx, ty + 6, lx + 3, G, W[1])
        m.vline(lx + 2, ty + 6, G, W[2])
    m.rect(tx0 + 5, G - 5, tx1 - 4, G - 4, W[1])   # 搁板
    m.hline(tx0 + 5, tx1 - 4, G - 5, W[2])
    # 桌下：左边一只铁桶（搁板上），右边地上一只木箱（板缝、上沿亮、右面亮一档）
    bx = tx0 + 9
    m.rect(bx, G - 11, bx + 8, G - 5, BM.B(.13, .02, 250))
    m.vline(bx + 6, G - 11, G - 5, BM.B(.19, .02, 244))
    m.vline(bx, G - 11, G - 5, BM.B(.1, .02, 254))
    m.hline(bx, bx + 8, G - 11, BM.B(.22, .02, 242))
    m.hline(bx, bx + 8, G - 8, BM.B(.1, .02, 254))
    cx0 = tx1 - 26
    m.rect(cx0, G - 9, cx0 + 16, G, W[2])
    m.vline(cx0, G - 9, G, W[1])
    m.hline(cx0, cx0 + 16, G - 9, W[3])
    m.vline(cx0 + 15, G - 9, G, W[3])
    m.hline(cx0, cx0 + 15, G - 5, W[1])
    m.vline(cx0 + 8, G - 8, G, W[1])
    # 桌面上：左头一只台钳（铁，螺杆手柄横着伸出来），中间一把补了一半的壶，右头一盒零件
    vx = tx0 + 4
    m.rect(vx, ty - 6, vx + 7, ty, IRON)
    m.hline(vx, vx + 7, ty - 6, IRON_LIT)
    m.vline(vx + 6, ty - 6, ty, IRON_LIT)
    m.hline(vx - 4, vx, ty - 3, IRON_LIT)
    m.vline(vx - 4, ty - 4, ty - 1, IRON)
    kx = tx0 + 38
    pot = [BM.B(.16, .02, 248), BM.B(.22, .02, 244), BM.B(.3, .02, 240)]
    m.rect(kx, ty - 6, kx + 9, ty, pot[0])
    m.rect(kx + 1, ty - 7, kx + 8, ty - 6, pot[1])
    m.vline(kx + 7, ty - 6, ty, pot[1])
    m.hline(kx + 1, kx + 8, ty - 7, pot[2])
    m.rect(kx + 3, ty - 9, kx + 6, ty - 7, pot[0])           # 壶盖钮
    m.line(kx + 9, ty - 4, kx + 12, ty - 7, pot[1])          # 壶嘴
    m.px(kx + 3, ty - 3, BM.B(.08, .015, 262))               # 还没补上的那个洞
    m.px(kx + 4, ty - 3, BM.B(.08, .015, 262))
    m.px(kx + 4, ty - 2, pot[2])                             # 洞下沿新补的一小块锡（亮）
    ox = tx1 - 16
    m.rect(ox, ty - 4, ox + 11, ty, W[1])
    m.hline(ox, ox + 11, ty - 4, W[3])
    m.vline(ox + 10, ty - 4, ty, W[3])
    for k, c in enumerate((BM.B(.3, .02, 244), BM.B(.24, .02, 248), BM.B(.34, .02, 240), BM.B(.26, .02, 246))):
        m.px(ox + 2 + k * 2, ty - 5, c)                      # 盒子里冒出来的螺丝、铁片
    # 桌下和摊子脚下的影子：光从右上来，影子往左下落（桥面上压暗两行，不描线）
    for yy in (G, G + 1):
        for xx in range(tx0 - 3, tx1 - 2):
            if m.a[yy, xx, 3]:
                m.a[yy, xx, :3] = mix(m.a[yy, xx, :3], DARK, 0.45 if yy == G else 0.25)
    # 灯：挂在横杆右头（柱子里边），只照右柱、右半张桌子和那盒零件
    BM.lantern(m, x1 - 6, rod + 7, "hang", r=20)
    BM.glow(m, x1 - 14, ty, 22)                    # 灯光落在桌面右半张、零件盒和右柱脚上


def market_layers():
    rng = np.random.default_rng(11)
    G = MK_G
    L = {}
    # ---- far（scroll 0.2，平铺 960）
    L["far"], _ = far_town(21, n=10, waterline=MK_HZ + 1, hz=MK_HZ)     # 对岸贴着压低了的地平线

    # ---- mid（scroll 0.6）：从下面升上来的石柱，柱身上凿出人家（小窗透暖光），两处之间拉着细桥
    mw = 480 + int((MK_W - 480) * 0.6) + 4
    spots = [(40, 112, 30, 3, False), (150, 96, 40, 4, True), (262, 128, 26, 2, False), (390, 84, 46, 5, True),
             (520, 118, 30, 3, False), (640, 100, 38, 4, True), (880, 90, 44, 5, True), (1000, 120, 32, 3, False)]
    # 10-30 第二版：石柱从桥面下面（脚下很远的河里）长上来，柱脚和水线都在画面外，看不见（原来水线 192，比桥面还高）
    mid, tops = rock_town(mw, spots, 300)
    # 提灯人（中景，晨走到留白那段时它在雾里）：直接用河岸的 BM.lantern_statue（整章一个样式），换个 seed。
    # 河在脚下，它不能再半截泡在桥面高度的水里——立在一根升上来的石柱顶上，只取水线以上那截，脚下一块凿平的石座
    statue_on_column(mid, 760, 150, seed=4150)
    for i in (0, 4):                              # 只有两处拉着吊桥：两根柱子同一高度凿出石台，桥挂在两块石台之间
        pillar_bridge(mid, tops[i], tops[i + 1])
    fog(mid, lambda y: 0.36 + 0.4 * np.clip((y - 150) / 120, 0, 1), hz=MK_HZ)
    rewarm(mid)
    L["mid"] = mid

    # ---- main
    m = Cv(MK_W)
    # 平台下面：一整块岩架，下沿凿出一排拱洞（往下化进夜色，竖直平移时接河岸的天）
    piers = [0, 150, 300, 470, 640, 800, 960, 1130, 1300, 1440]
    shelf = np.zeros((H - G, MK_W), bool)
    for x in range(MK_W):
        k = min(max(i for i, p in enumerate(piers) if p <= x), len(piers) - 2)
        p0, p1 = piers[k], piers[k + 1]
        if x - p0 < 6 or p1 - x < 6:
            yb = H
        else:
            t = ((x - p0 - 6) / max(1, (p1 - p0 - 12))) * 2 - 1
            yb = int(round(214 + (1 - np.sqrt(max(0.0, 1 - t * t))) * 70))
        shelf[:yb - G, x] = True
    m.paste(BM.stone_shade(shelf, np.random.default_rng(12), BM.STONE, facet_w=16, ledges=1.0, moss=0.4), 0, G)
    for x in range(MK_W):                         # 拱洞的内沿暗一格；平台面月光一条
        col = np.nonzero(shelf[:, x])[0]
        if len(col) and col[-1] + G < H - 1:
            m.px(x, col[-1] + G, DARK)
    road_top(m, lambda x: G, 0, MK_W, 31)          # 平台朝上的路面（不悬空）
    for p0, p1 in [(150, 300), (640, 800), (960, 1130)]:  # 拱洞里的灯：一根铁链挂在拱顶上（不悬空）
        lx = (p0 + p1) // 2
        chain_lamp(m, lx, 222, int(np.nonzero(shelf[:, lx])[0][-1]) + G)
    for i, (p0, p1) in enumerate(zip(piers[:-1], piers[1:])):    # 拱洞里挂下来的根须
        vines(m, p0 + 14, p1 - 14, 216, 900 + i, n=3, max_len=16)
    # 往下去河岸的路（1351，pan_down）：不画大楼梯——平台边上凿出几级窄台阶，往下拐进岩架的影子里就看不见了
    for i in range(5):
        sx, sy = 1338 + i * 6, G + 3 + i * 5
        m.rect(sx, sy, sx + 7, sy + 5, BM.STONE[1])
        m.hline(sx, sx + 7, sy, BM.STONE[2])
    for i in range(14):
        m.hline(1366 + i // 3, 1382, G + 26 + i, DARK)

    gb = G - 1                                    # 屋子的最下一行（踩在平台上）
    # 左头：到头了——一面一直升到画面外的石壁，脚下一道苔、两根垂下来的根须（10-30：旧街改在右头，这头不通）
    img_, ox_, oy_ = pillar_rock(m, 10, gb, 56, 230, 405)
    vines(m, 2, 30, 120, 406, n=2, max_len=22)
    # 吊篮那家：一根石柱，柱身上凿出门窗（吊篮挂在栏杆外，门在篮子右边）
    dwelling_pillar(m, 112, gb, 40, 168, 441, [(-17, "arch", 8, 17, True, True), (-46, "arch", 5, 7, True, False),
                                               (-84, "round", 5, 5, True, False), (-118, "arch", 4, 6, False, False),
                                               (-146, "arch", 4, 6, True, False)])
    lamp_post(m, 160, gb, 28)
    # 修补摊：一根石柱的脚下，柱子右边支出一块旧布篷，工具挂在篷下（market_tools）
    dwelling_pillar(m, 266, gb, 36, 182, 442, [(-60, "arch", 4, 6, True, False), (-98, "arch", 5, 7, True, False),
                                               (-140, "round", 4, 4, True, False)])
    repair_stall(m, G)
    # 气瓶柜台：一块圆巨石，正面凿出一个宽的弧顶柜台口（不是贴上去的方框）：
    # 口沿左、上两道内壁在影子里，弧顶外一圈券石亮一档；里面上暗下亮几块干净的暖色，搁板上挂面罩，下面一排气瓶背着光
    rock(m, 456, 568, gb, 120, 443, p=3.2)
    opening(m, 542, 138, 5, 7, "arch", True)
    BM.glow(m, 505, 170, 36)
    ax0, ax1, ay_mid, ay_side, ay1 = 482, 528, 152, 157, 184
    def arch_top(xx):
        t = (xx + 0.5 - (ax0 + ax1) / 2) / ((ax1 - ax0) / 2)
        return int(round(ay_side - (ay_side - ay_mid) * np.sqrt(max(0.0, 1 - t * t))))
    for xx in range(ax0 - 2, ax1 + 2):            # 弧顶外一圈券石（亮一档）+ 券石间两道缝
        yt = arch_top(min(max(xx, ax0), ax1 - 1))
        for d in (1, 2):
            m.px(xx, yt - d, BM.STONE[3] if d == 1 else BM.STONE[2])
    for xx in (494, 505, 516):
        m.px(xx, arch_top(xx) - 1, BM.STONE[1])
        m.px(xx, arch_top(xx) - 2, BM.STONE[1])
    for xx in range(ax0, ax1):
        yt = arch_top(xx)
        for yy in range(yt, ay1):
            t = (yy - yt) / max(1, ay1 - yt - 1)
            if xx < ax0 + 2 or yy < yt + 2:
                c = DARK if (xx == ax0 or yy == yt) else BM.STONE[0]
            else:
                k = 0 if t < 0.3 else (1 if t < 0.6 else (2 if t < 0.9 else 3))
                if xx > 512 and k in (1, 2):
                    k += 1
                c = [HUSK, BM.WARM[0], BM.WARM[1], BM.WARM[2]][k]
            m.px(xx, yy, c)
    m.vline(ax1, arch_top(ax1 - 1), ay1, BM.STONE[4])     # 右沿石唇受月光
    m.hline(ax0 + 2, ax1, 168, HUSK)              # 一层搁板
    m.hline(ax0 + 2, ax1, 169, BM.WARM[0])
    for mx_ in (490, 500):                        # 两只面罩（剪影）
        m.vline(mx_ + 2, 160, 162, HUSK)
        m.rect(mx_, 162, mx_ + 5, 166, BM.STONE[1])
        m.px(mx_ + 4, 162, BM.WARM[0])
        m.px(mx_ + 2, 164, HUSK)
    for a_ in np.linspace(0, 2 * np.pi, 22):      # 一卷管子
        m.px(516 + 3.5 * np.cos(a_), 163 + 2.5 * np.sin(a_), BM.STONE[1])
    for k, (bx, th) in enumerate(((486, 11), (497, 10), (508, 11), (519, 8))):   # 气瓶：背光的剪影，右沿一道暖边
        top = 183 - th
        m.rect(bx, top, bx + 5, 183, BM.STONE[1] if k % 2 else BM.STONE[0])
        m.hline(bx + 1, bx + 4, top - 1, BM.STONE[1])
        m.vline(bx + 4, top, 183, BM.WARM[0])
        m.px(bx + 2, top - 2, BM.STONE[1])
        m.hline(bx, bx + 4, top + 4, C(.24, 60, .04))
    m.rect(480, 183, 532, 187, BM.STONE[2])       # 石台面
    m.hline(480, 532, 183, BM.STONE[4])
    m.hline(484, 500, 183, BM.STONE[3])
    m.rect(498, 144, 516, 150, BM.WOOD[1])        # 招牌：一块木牌，画着一个气泡
    m.hline(498, 516, 144, BM.WOOD[4])
    for (bx, by) in [(502, 146), (505, 147), (510, 146)]:
        m.px(bx, by, CHALK)
    # 饼干摊：巨石屋，底下凿出一个烤炉口，门口一块石板摆着饼干
    boulder(m, 656, gb, 92, 56, 44, openings=(("round", 68, 28, 6, 6, True, False),), pipe=62)
    opening(m, 626, 182, 14, 12, "arch", True, False, pal=BM.STONE)
    m.rect(650, 184, 704, 188, BM.STONE[2])
    m.hline(650, 704, 184, BM.STONE[5])
    rock(m, 652, 702, gb, 188, 403, p=6)
    for bx in range(652, 702, 5):
        m.hline(bx, bx + 3, 182, C(.3, 70, .04))
        m.hline(bx, bx + 3, 183, C(.26, 70, .04))
    BM.lantern(m, 678, 168, "hang")
    m.px(678, 162, IRON_LIT)                      # 灯挂在钉进石头的铁钉上
    # 屋顶之间的细桥：两根石柱，柱身上凿出人家，门口各伸出一块石台，石台之间一座绳桥
    pa = dwelling_pillar(m, 772, gb, 42, 120, 450, [(-30, "arch", 4, 6, True, False), (-62, "arch", 4, 6, False, False)],
                         door_y=104, door_side=1)
    pb = dwelling_pillar(m, 894, gb, 48, 152, 451, [(-24, "arch", 5, 7, True, False), (-90, "round", 5, 5, True, False),
                                                    (-60, "arch", 4, 6, True, False)], door_y=101, door_side=-1)
    rope_bridge(m, pa, 104, pb - 1, 101, lamps=(0.3, 0.7))      # 两扇门差 3 格高，桥基本水平（10-30 以前差 20 格，像梯子）
    # 930..1240 留白：什么都不能点，只有平台、两盏路灯、后面的石柱和雾
    lamp_post(m, 1010, gb, 30)
    lamp_post(m, 1176, gb, 30)
    # 妮芙常站的这家：一根高石柱，脚下一扇亮着的门，柱身上一路凿上去几扇小窗，门边铁臂上挂一盏灯
    dwelling_pillar(m, 1262, gb, 46, 176, 447, [(-18, "arch", 9, 18, True, True), (-50, "arch", 5, 7, True, False),
                                                (-86, "round", 5, 5, True, False), (-120, "arch", 4, 6, False, False),
                                                (-152, "arch", 4, 6, True, False)])
    bracket_lamp(m, 1282, 158, side=1, arm=7)
    lamp_post(m, 1332, gb, 20)                    # 下去河岸的口上一盏矮路灯
    # 右头：石桥走到头，一根大石柱脚下凿穿一道拱门——穿过去就是旧街（10-30：旧街在世界里本来就在右边）；
    # 门洞里黑，拱顶一根铁链吊一盏灯，门槛一道月光
    img_, ox_, oy_ = pillar_rock(m, 1424, gb, 60, 240, 77)
    opening(m, 1410, 150, 22, 50, "arch", False, pal=BM.STONE)
    chain_lamp(m, 1421, 163, 152)
    m.hline(1410, 1432, gb, BM.STONE[4])
    for bx in (212, 586):                         # 地上几只木桶
        m.rect(bx, G - 8, bx + 6, G, BM.WOOD[2])
        m.hline(bx, bx + 6, G - 8, BM.WOOD[4])
        m.hline(bx, bx + 6, G - 4, BM.WOOD[0])
        m.vline(bx + 5, G - 8, G, BM.WOOD[3])
    stone_post(m, 236, G - 1)
    ground_ao(m, lambda x: G, 0, MK_W)
    fog_bottom(m, 236, hz=MK_HZ)
    L["main"] = m

    # ---- rail（人前面）：平台外沿的木栏杆，只在左边一段和楼梯井口
    rail = Cv(MK_W)
    for i, (x0, x1) in enumerate([(36, 136), (176, 252), (1296, 1334), (1372, 1402)]):
        wood_rail(rail, x0, x1, 186, G, 600 + i, mid=194)
    L["rail"] = rail

    # ---- front（scroll 1.3）
    fw = 480 + int((MK_W - 480) * 1.3) + 4
    fr = Cv(fw)
    for (x0, x1, low) in [(260, 520, 26)]:
        n = x1 - x0
        for i in range(n + 1):
            t = i / n
            y = low * 4 * t * (1 - t) - 2
            fr.px(x0 + i, y, DARK)
            fr.px(x0 + i, y + 1, DARK)
        for t in (0.22, 0.5, 0.78):
            lantern(fr, int(x0 + n * t), int(low * 4 * t * (1 - t)) + 4, hang=4, big=True)
    for (x, hgt, seed) in [(700, 70, 1), (1520, 90, 2)]:
        frond(fr, x, H, hgt, seed)
    L["front"] = fr

    O = {}
    O["market_baskets"] = baskets()
    O["market_tools"] = tools_strip()
    O["market_breather_stall"] = breather()
    return L, O


def wood_rail(cv, x0, x1, top, foot, seed, mid=None):
    """一段旧木栏杆：扶手 + 一道横档，立柱间距不匀（11~17），有的柱子矮一截（断了），有一处横档掉了一头垂下来。
    颜色压在木头的中暗档（不发亮），扶手上沿只亮一档。"""
    rng = np.random.default_rng(seed)
    mid = mid if mid is not None else top + (foot - top) // 2
    drop = int(rng.integers(x0 + 10, max(x0 + 11, x1 - 20))) if x1 - x0 > 40 else None
    for x in range(x0, x1):
        cv.px(x, top, BM.WOOD[3])
        cv.px(x, top + 1, BM.WOOD[1])
        if drop is None or not drop <= x < drop + 14:
            cv.px(x, mid, BM.WOOD[1])
    if drop is not None:                          # 掉了一头的横档，斜着垂下去
        for k in range(14):
            cv.px(drop + k, mid + k * 4 // 14, BM.WOOD[1])
    x = x0
    while x <= x1:
        short = rng.random() < 0.12
        y0 = top + (4 if short else 0)
        cv.rect(x, y0, x + 2, foot + 1, BM.WOOD[1])
        cv.vline(x + 1, y0, foot + 1, BM.WOOD[2])
        if short:
            cv.px(x + 1, y0, BM.WOOD[3])
        x += int(rng.integers(11, 18))


def road_top(cv, ground, x0, x1, seed):
    """路面朝上的那一面（作者：晨像浮着）：照河岸 quay() 的做法，地面线往下 3 行是被月光照着的路面（单独一条更亮的色阶，
    小色团、条石接缝、几块磨亮的），最外沿一道冷亮边，第 4 行一道影子（路面边下面），再往下才是暗的侧面。只改已经画了的石头。"""
    P = BM.expand_pal(RA.bramp(6, .075, .34, 260, 240))
    rng = np.random.default_rng(seed)
    cn = BM.cluster_noise(8, cv.w, rng, 2.2)
    for x in range(x0, x1):
        g = ground(x)
        for d in range(5):
            if cv.get(x, g + d) is None:
                continue
            if d < 3:
                seam = (x + (7 if d else 0)) % 23 == 0
                k = 4 if seam else (7 if d == 0 else (6 if cn[d, x] > 0.45 else 5))
                if d == 2:
                    k -= 1
                if d == 0 and (x * 13) % 17 < 3:
                    k = 8
            elif d == 3:
                k = 1
            else:
                continue
            cv.px(x, g + d, P[k])


def ground_ao(cv, ground, x0, x1, depth=4):
    """石柱 / 石头落地的地方压一道暗（接触阴影）：地面线往上几行、本来就画了石头的像素往暗推，越贴地越暗。暖色（灯、窗）不动。"""
    for x in range(x0, x1):
        g = ground(x)
        for k in range(1, depth + 1):
            o = cv.get(x, g - k)
            if o is None or o[0] - o[2] > 10:
                continue
            cv.px(x, g - k, mix(o, DARK, (0.42, 0.3, 0.18, 0.1, 0.05)[min(4, k - 1)]))


def fog_bottom(cv, y0, hz=None):
    fog(cv, lambda y: 0 if y < y0 else ((y - y0) / (H - y0)) ** 1.2 * 0.95, steps=8, hz=hz)


def frond(cv, x, base, hgt, seed):
    """近景一丛近黑的宽叶：从底边长上来、往两边弯垂。"""
    rng = np.random.default_rng(seed)
    for k in range(7):
        ln = hgt * rng.uniform(0.5, 1.0)
        side = -1 if k % 2 else 1
        ang = -np.pi / 2 + side * rng.uniform(0.05, 0.5)
        px, py = x + rng.uniform(-6, 6), base
        wdt = rng.uniform(2.5, 4.5)
        for s in range(int(ln)):
            t = s / ln
            ang += side * 0.02
            px += np.cos(ang)
            py += np.sin(ang)
            ww = max(1, int(round(wdt * np.sin(np.pi * min(0.95, t + 0.1)))))
            for d in range(-ww // 2, ww - ww // 2):
                cv.px(px + d, py, DARK)
            cv.px(px + ww - ww // 2, py, C(.08, 258))


def baskets():
    """market_baskets：2 帧 70×40。三只吊在栏杆外的篮子（绳从顶上那根栏杆垂下来），一只里面点着小灯；两帧轻轻晃。"""
    w, h = 70, 40
    img = np.zeros((h, w * 2, 4), np.uint8)
    for f in range(2):
        cv = Cv(w, h)
        for (bx, ln, bw, bh, lamp) in [(5, 16, 14, 10, False), (28, 24, 16, 11, True), (52, 12, 13, 9, False)]:
            sw = (1 if f else 0) * (1 if bx != 30 else -1)
            cv.line(bx + bw // 2, 0, bx + bw // 2 + sw, ln, C(.22, 250))
            x0, y0 = bx + sw, ln
            for y in range(bh):
                inset = 1 if y == bh - 1 else 0
                for x in range(x0 + inset, x0 + bw - inset):
                    c = WOOD[3] if (x + y) % 3 == 0 else WOOD[2]
                    if x == x0 + bw - 1 - inset:
                        c = WOOD[4]
                    cv.px(x, y0 + y, c)
            cv.hline(x0, x0 + bw, y0, WOOD[5])
            cv.line(x0, y0, x0 + bw // 2, y0 - 4, C(.16, 250))
            cv.line(x0 + bw - 1, y0, x0 + bw // 2, y0 - 4, C(.16, 250))
            if lamp:
                for x in range(x0 + 3, x0 + bw - 3):
                    cv.px(x, y0 - 1, WARM[1] if x % 2 else WARM[2])
                cv.px(x0 + bw // 2, y0 - 2, WARM[0])
                cv.blend(x0 + 2, y0 - 1, HALO, 1)
            else:
                for k in range(bw // 3):
                    cv.px(x0 + 1 + k * 3, y0 - 1, STONE[4])
                    cv.px(x0 + 2 + k * 3, y0 - 1, STONE[3])
        img[:, f * w:(f + 1) * w] = cv.a
    return img


def tools_strip():
    """market_tools：4 帧 76×26。雨篷下一根横杆，挂着扳手、锤子、勺、一圈铁丝、一串钥匙、剪子；
    一下一下轻轻晃（下端左右错 1 像素），亮点在金属上挪。"""
    w, h = 76, 26
    out = np.zeros((h, w * 4, 4), np.uint8)
    metal = RA.bramp(4, .2, .52, 256, 246)        # 10-31 提亮一档：原来在雾里的远柱前面几乎看不见
    items = [(4, "wrench", 18), (14, "hammer", 16), (25, "ladle", 20), (36, "coil", 12), (48, "keys", 10),
             (58, "scissor", 14), (68, "wrench", 15)]
    for f in range(4):
        cv = Cv(w, h)
        cv.hline(0, w, 0, WOOD[2])
        cv.hline(0, w, 1, WOOD[1])
        for i, (x, kind, ln) in enumerate(items):
            sw = [0, 1, 0, -1][(f + i) % 4]
            cv.px(x, 2, C(.14, 250))
            top = 3
            if kind == "wrench":
                cv.line(x, top, x + sw, top + ln - 3, metal[1])
                cv.line(x + 1, top, x + 1 + sw, top + ln - 3, metal[2])
                cv.rect(x - 1 + sw, top + ln - 3, x + 3 + sw, top + ln, metal[1])
                cv.px(x + sw, top + ln - 2, DARK)
            elif kind == "hammer":
                cv.line(x, top, x + sw, top + ln, WOOD[3])
                cv.rect(x - 2 + sw, top + ln - 3, x + 4 + sw, top + ln, metal[1])
                cv.hline(x - 2 + sw, x + 4 + sw, top + ln - 3, metal[3])
            elif kind == "ladle":
                cv.line(x, top, x + sw, top + ln - 4, metal[2])
                cv.rect(x - 2 + sw, top + ln - 4, x + 3 + sw, top + ln, metal[1])
                cv.hline(x - 1 + sw, x + 2 + sw, top + ln - 1, metal[0])
            elif kind == "coil":
                for a in np.linspace(0, 2 * np.pi, 30):
                    cv.px(x + sw * .5 + 4 * np.cos(a), top + 6 + 4 * np.sin(a), metal[2 if np.cos(a) > 0 else 1])
            elif kind == "keys":
                cv.line(x, top, x + sw, top + 3, metal[1])
                for k in range(3):
                    cv.vline(x - 2 + k * 2 + sw, top + 4, top + ln - k, metal[2])
            elif kind == "scissor":
                cv.line(x - 1, top + 2, x + 1 + sw, top + ln, metal[2])
                cv.line(x + 2, top + 2, x + sw, top + ln, metal[1])
                cv.px(x - 1, top + 1, metal[1])
                cv.px(x + 2, top + 1, metal[1])
        gx, gy = [(5, 8), (26, 18), (49, 12), (69, 14)][f]       # 一点亮光在金属上挪
        if cv.get(gx, gy):
            cv.px(gx, gy, metal[3])
        BM.glow(cv, STALL_X1 - 6 - 300, 7, 20)                   # 杆右头那盏灯只照到最右边两三件（物件 x=300）
        out[:, f * w:(f + 1) * w] = cv.a
    return out


def breather():
    """market_breather_stall：2 帧 30×22。第 0 帧空台面（只有一本借用簿）；第 1 帧台上立着一只气瓶（阀门、软管、面罩）。"""
    w, h = 30, 22
    out = np.zeros((h, w * 2, 4), np.uint8)
    for f in range(2):
        cv = Cv(w, h)
        cv.rect(2, 9, 10, 12, C(.4, 240, .015))      # 借用簿
        cv.hline(2, 10, 9, C(.5, 240, .015))
        cv.vline(6, 9, 12, C(.25, 250))
        if f == 1:
            cv.rect(15, 0, 21, 12, STONE[3])
            cv.vline(20, 1, 12, STONE[5])
            cv.vline(15, 1, 12, STONE[1])
            cv.hline(16, 20, 0, STONE[5])
            cv.rect(17, -1, 19, 1, STONE[1])
            cv.px(18, 0, STONE[6])
            cv.hline(15, 21, 5, C(.3, 60, .05))          # 一圈褪色的黄条（借来的瓶子）
            for i, (x, y) in enumerate([(21, 1), (23, 2), (24, 4), (25, 6), (25, 8), (24, 10)]):
                cv.px(x, y, DARK)
            cv.rect(23, 9, 27, 12, STONE[2])
            cv.hline(23, 27, 9, STONE[4])
        out[:, f * w:(f + 1) * w] = cv.a
    return out


# ---------------------------------------------------------------- 旧街 oldstreet（1280 宽）

OS_W = 1280
OS_UP = 150          # 上层街（闸那边）的地面
OS_LOW = 236         # 下层旧街的地面
OS_GROUND = [[0, 150], [440, 150], [450, 156], [460, 162], [470, 168], [480, 174], [490, 180], [500, 186],
             [510, 193], [520, 199], [530, 205], [540, 211], [550, 217], [560, 223], [570, 229], [580, 236],
             [1036, 236], [1044, 262], [1088, 262], [1096, 236], [1280, 236]]
WATER = {"submerged": 156, "l1": 178, "l2": 200, "l3": 222, "revealed": 246}
WHEELS = {"sluice_wheel_1": (192, 107, 28, 30), "sluice_wheel_2": (238, 107, 28, 30), "sluice_wheel_3": (301, 100, 34, 36)}
PIPES_OBJ = (340, 146, 60, 40)
PIPE_A_X, PIPE_B_X = 356, 384        # 两根管子的出水口（a 接左边小闸轮，b 接右边）


def gy_os(x):
    xs, ys = zip(*OS_GROUND)
    return int(round(np.interp(x, xs, ys)))


def oldstreet_layers():
    rng = np.random.default_rng(12)
    L = {}
    L["far"], _ = far_town(31, n=9)

    # ---- mid（scroll 0.6）：运河对面一根根站在水里的石柱人家 + 一颗沉了半截的大石头人头
    mw = 480 + int((OS_W - 480) * 0.6) + 4
    spots = [(20, 92, 40, 4, True), (120, 110, 30, 3, False), (232, 96, 46, 5, True), (470, 116, 30, 3, False),
             (640, 98, 42, 4, True), (752, 112, 32, 3, False), (850, 88, 48, 5, True)]
    mid, tops = rock_town(mw, spots, 500, wl=178, refl=240 - 178)          # 和石鲸同一条水线；倒影盖到下层街面后面
    wh, wwl = stone_whale()                        # 半沉的石鲸（水退了露得更多）；水底那颗人头留给水底
    # 10-30：水线接河岸的 BM.water_foot（一条连着的湿亮线 + 不透明倒影 + 两边淡涟漪），原来水线上是一排亮点、底下什么都没有
    whf, wpad = BM.water_foot(wh[:wwl + 1], wwl, 9, refl=240 - 178)
    mid.paste(whf, 350 - wpad, 178 - wwl)
    pillar_bridge(mid, tops[1], tops[2])
    pillar_bridge(mid, tops[5], tops[6])
    fog(mid, lambda y: 0.34 + 0.3 * np.clip((y - 150) / 100, 0, 1))
    rewarm(mid)
    L["mid"] = mid

    # ---- main
    m = Cv(OS_W)
    # 地基：上层码头、台阶、下层街面——整片的岩石（不是砖），顶面一条月光；几道竖的大石缝把它分成几块
    ground = np.zeros((H - OS_UP, OS_W), bool)
    for x in range(OS_W):
        ground[gy_os(x) - OS_UP:, x] = True
    m.paste(BM.stone_shade(ground, np.random.default_rng(64), BM.STONE, facet_w=16, ledges=1.0, moss=0.5), 0, OS_UP)
    for sx in (120, 300, 640, 870, 1180):     # 几道竖的大石缝：缝里暗一档、右唇接月光亮一档（10-30：原来是一条纯黑的线，像描边）
        for y in range(gy_os(sx) + 2, H):
            xx = sx + int(1.5 * np.sin(y / 7.0))
            o = m.get(xx, y)
            if o is not None:
                m.px(xx, y, mix(o, BM.STONE[0], 0.7))
                m.blend(xx + 1, y, BM.STONE[3], 0.45)
    for x in range(OS_W):
        g = gy_os(x)
        m.px(x, g, BM.STONE[5])
        m.px(x, g + 1, BM.STONE[3])
    road_top(m, gy_os, 0, OS_W, 32)                # 码头 / 街面朝上的路面（不悬空）
    for i in range(14):                         # 台阶的踏面（每一级右边亮）
        x0 = 440 + i * 10
        y0 = gy_os(x0)
        m.hline(x0, x0 + 10, y0, BM.STONE[5])
        m.vline(x0, y0, y0 + 6, BM.STONE[1])
    # 仓库入口：两根立石门柱 + 一块压在上面的过梁石，门里是一段往下的石阶（10-30 重画：原来门里是平涂的黑盒子，
    # 里面一排等距的亮横线）。月光从右上来：过梁和右门柱在门里后墙上投下影子（影子边一横一竖），只有左下一块后墙接到光；
    # 石阶的踏面上沿亮、立面朝左在影子里，一级比一级暗，最后没进黑里
    wall_rng = np.random.default_rng(904)
    nz = RA.vnoise(37, 52, 7, 9, wall_rng)
    for y in range(200, 237):                     # 门里的后墙：粗凿的石面（一团团暗一档），只有左下一块接到一点月光
        for x in range(1040, 1092):
            lit = x < 1076 and y > 213
            dark = nz[y - 200, x - 1040] < 0.42
            if lit:
                soft = (1076 - x) < 4 or (y - 213) < 4             # 影子边上过渡一档
                c = BM.STONE[0] if soft else (BM.STONE[0] if dark else BM.STONE[1])
                if soft and not dark:
                    c = mix(BM.STONE[0], BM.STONE[1], 0.5)
            else:
                c = mix(BM.STONE[0], DARK, 0.65 if dark else 0.45)
            m.px(x, y, c)
    m.hline(1040, 1076, 236, BM.STONE[3])        # 门槛：月光照到的一道
    for x in range(1044, 1088):                   # 往下的石阶：每级 8 格宽、5 格高，往右往下
        i = min(4, (x - 1044) // 8)
        f = 237 + 5 * (i + 1)
        k = 0.15 + 0.17 * i                       # 越往下越暗
        for y in range(237, H):
            if y < f:
                m.px(x, y, mix(BM.STONE[0], DARK, 0.6 + 0.08 * i))
            elif y == f:
                m.px(x, y, mix(BM.STONE[3], DARK, k))
            else:
                m.px(x, y, mix(BM.STONE[1], DARK, k + 0.1))
        if (x - 1044) % 8 == 0 and x > 1044:      # 立面：朝左，在影子里
            for y in range(f - 4, f):
                m.px(x, y, mix(BM.STONE[1], DARK, k + 0.25))
    rock(m, 1026, 1042, 236, 194, 901, p=8, moss=False)
    rock(m, 1090, 1106, 236, 194, 902, p=8, moss=False)
    rock(m, 1020, 1110, 201, 184, 903, p=12)
    m.hline(1042, 1090, 201, DARK)               # 过梁压在门柱上：底下一道最暗的缝

    ub = OS_UP - 1
    # 上层：左头一块巨石里凿出往上的石阶小巷（去市集）
    rock(m, 0, 30, ub, 60, 911, p=6)
    for i in range(7):
        x0, y0 = 4 + i * 5, 112 + i * 6
        m.rect(x0, y0, x0 + 8, y0 + 3, BM.STONE[2])
        m.hline(x0, x0 + 8, y0, BM.STONE[5])
    BM.stone_lantern(m, 44, ub)
    # 妮芙等的这家：巨石屋
    boulder(m, 98, ub, 80, 62, 61, openings=(("arch", 10, 28, 5, 7, True, False), ("arch", 62, 28, 5, 7, True, False),
                                                       ("arch", 34, 0, 9, 16, True, True)), pipe=58)
    stone_post(m, 150, OS_UP - 1)
    BM.stone_lantern(m, 162, ub)
    # 水闸房：一整块方石头凿平了正面，三只闸轮挂在上面；两只小的上面只剩铭牌的空框
    rock(m, 172, 348, ub, 84, 62, p=9)
    for wid in ("sluice_wheel_1", "sluice_wheel_2"):    # 铭牌的空框（四颗钉眼）
        x, y, w, h = WHEELS[wid]
        px0 = x + w // 2 - 7
        m.rect(px0, 99, px0 + 14, 105, BM.STONE[0])
        m.rect(px0 + 1, 100, px0 + 13, 104, BM.STONE[2])
        for (dx, dy) in [(1, 100), (12, 100), (1, 103), (12, 103)]:
            m.px(px0 + dx, dy, DARK)
    x, y, w, h = WHEELS["sluice_wheel_3"]                # 大闸轮：铭牌还在（暗铜色，刻着两行看不清的字）
    m.rect(x + 4, 92, x + w - 4, 99, C(.28, 70, .035))
    m.hline(x + 4, x + w - 4, 92, C(.38, 70, .04))
    m.hline(x + 6, x + w - 8, 94, C(.18, 70, .03))
    m.hline(x + 7, x + w - 6, 96, C(.18, 70, .03))
    for wid, (x, y, w, h) in WHEELS.items():             # 轮轴后面的墙上一块暗的底座
        m.rect(x + w // 2 - 2, y + h - 2, x + w // 2 + 2, y + h + 2, DARK)
    # 闸边的矮栏杆（妮芙趴在这儿听）：画在墙前、管子后面，不挡管子
    wood_rail(m, 262, 342, 128, OS_UP - 1, 610, mid=138)
    # 两根管子：从小闸轮底下出来，顺着墙走，过了大闸轮就翻下码头钻进水里
    # （a：左边那只、下面那根，先下水；b：右边那只、上面那根，走得更远、下得更深）
    pipe_pal = RA.bramp(4, .13, .39, 252, 240)     # 铁管：看得清，但不比月光照的石沿亮

    def pipe(path, wdt):
        for (x0, y0), (x1, y1) in zip(path[:-1], path[1:]):
            if y0 == y1:
                for xx in range(min(x0, x1), max(x0, x1) + wdt):
                    m.px(xx, y0, pipe_pal[3])
                    for k in range(1, wdt):
                        m.px(xx, y0 + k, pipe_pal[1] if k == wdt - 1 else pipe_pal[2])
                    if xx % 24 == 0:
                        m.vline(xx, y0 - 1, y0 + wdt + 1, pipe_pal[0])
            else:
                for yy in range(min(y0, y1), max(y0, y1) + 1):
                    m.px(x0, yy, pipe_pal[1])
                    for k in range(1, wdt):
                        m.px(x0 + k, yy, pipe_pal[3] if k == wdt - 1 else pipe_pal[2])
                    if yy % 14 == 0:
                        m.hline(x0 - 1, x0 + wdt + 1, yy, pipe_pal[0])
    a1x = WHEELS["sluice_wheel_1"][0] + 13
    b1x = WHEELS["sluice_wheel_2"][0] + 13
    pipe([(a1x, 139), (a1x, 144), (PIPE_A_X, 144), (PIPE_A_X, 168)], 3)
    pipe([(b1x, 139), (b1x, 138), (PIPE_B_X, 138), (PIPE_B_X, 190)], 3)
    for (px_, py_) in [(PIPE_A_X, 168), (PIPE_B_X, 190)]:     # 管口：一圈喇叭
        m.rect(px_ - 1, py_, px_ + 4, py_ + 3, pipe_pal[1])
        m.hline(px_ - 1, px_ + 4, py_, pipe_pal[3])
        m.rect(px_, py_ + 2, px_ + 3, py_ + 3, DARK)
    # 刻线石壁（400..438）：一整块竖着的石头，不同年份的水位线凿在上面，最旧（最低）那条被苔盖住
    # （第五版：线和年份都是凿进去的槽——槽暗、下唇亮一点、断断续续；石头本身是一块边角磨圆的立石，不是方块）
    slab = BM.blob_mask(38, H - 104, np.random.default_rng(62), p=7, lump=0.04)
    m.paste(BM.stone_shade(slab, np.random.default_rng(63), BM.STONE, facet_w=13, joints=0.35, ledges=0.2, moss=0.4),
            400, 104)
    marks = [(WATER["submerged"], "19"), (WATER["l1"], "07"), (WATER["l2"], "96"), (WATER["l3"], "81")]
    for i, (yy, yr) in enumerate(marks):
        # 水闸小游戏要看这几条线：槽更深、下唇更亮（还是石头的颜色，不是白线）
        carved_line(m, 402, 436, yy, 640 + i, worn=0.06 + 0.05 * i, lip=0.75)
        carved_digits(m, 405, yy - 6, yr, 650 + i, lip=0.7)
    mrng = np.random.default_rng(66)                # 最旧那条（81）被苔盖了一大半：一团团的，不排成格子
    for _ in range(26):
        x, yy = int(mrng.integers(400, 438)), int(mrng.integers(WATER["l3"] - 4, WATER["l3"] + 5))
        for k in range(int(mrng.integers(1, 4))):
            if m.get(x + k, yy) is not None:
                m.px(x + k, yy, MOSS[int(mrng.integers(0, 2))])

    lb = OS_LOW - 1
    # 下层旧街：一块块分开的巨石，人家凿在石头里。水面以上是今天的门（门口伸出一块石台）、亮着的窗、挂着的木店招；
    # 水面以下（泡过水）是更旧的一排门窗，同一块店招刻在石壁上（同名店）
    pillar_rock(m, 634, lb, 96, 236, 921)          # 高高的一根石柱，一直伸到画面外
    opening(m, 646, 74, 4, 6, "arch", True)
    opening(m, 620, 46, 5, 7, "arch", True)
    opening(m, 664, 28, 4, 4, "round", False)
    ledge(m, 592, 622, 152)
    opening(m, 600, 139, 8, 13, "arch", True, True, pal=BM.STONE)
    opening(m, 630, 112, 5, 7, "arch", True, pal=BM.STONE)
    opening(m, 652, 112, 5, 7, "arch", True, pal=BM.STONE)
    wood_sign(m, 632, 132, "cup")
    opening(m, 598, 213, 9, 22, "arch", False, pal=BM.STONE)
    opening(m, 628, 206, 6, 8, "arch", False, pal=BM.STONE)
    opening(m, 664, 206, 6, 8, "arch", False, pal=BM.STONE)
    carved_sign(m, 638, 194, "cup")
    bracket_lamp(m, 684, 145, side=1, arm=7)      # 铁臂钉在石柱右边上（10-30：原来那根铁臂没挨着石头）
    # 拐角：一块方一点的石头，角上凿了个灯龛
    pillar_rock(m, 766, lb, 74, 150, 922)
    opening(m, 772, 96, 4, 6, "arch", True)
    lamp_niche(m, 790, 146)                       # 拐角石头上凿的灯龛（原来是一根悬空的铁臂）
    opening(m, 736, 128, 5, 7, "arch", True, pal=BM.STONE)
    opening(m, 786, 130, 5, 7, "arch", True, pal=BM.STONE)
    opening(m, 760, 140, 7, 10, "arch", True, pal=BM.STONE)
    m.px(763, 146, BM.WARM[4])
    opening(m, 734, 216, 8, 19, "arch", False, pal=BM.STONE)
    opening(m, 770, 208, 6, 8, "arch", False, pal=BM.STONE)
    # 身高刻线墙：一块磨平了的大石板，小孩的身高一道道刻在下面，上面一道红线 = 那年的洪水
    # （第五版：石板是一块边角磨圆、有水渍的立石；身高是刻上去的短槽，几道上面还留着褪了的粉笔；
    #   洪水那道是刷上去又褪了色的暗红漆，斑驳、掉了好几块，不发亮）
    face_pal = RA.bramp(6, .1, .31, 252, 238)
    face = BM.blob_mask(54, OS_LOW - 140, np.random.default_rng(72), p=8, lump=0.03)
    m.paste(BM.stone_shade(face, np.random.default_rng(73), face_pal, facet_w=18, joints=0.3, ledges=0.15, moss=0.35,
                           light=0.9), 852, 140)
    for k, hh in enumerate([16, 19, 21, 24, 26, 28, 31]):
        y0 = OS_LOW - hh
        x0 = 862 + (k % 3) * 4 + (k * 5) % 3
        carved_line(m, x0, x0 + 9 + k % 3, y0, 700 + k, face_pal, worn=0.1)
        if k % 2:
            faded_paint(m, x0 + 1, x0 + 8, y0 - 1, 710 + k, CHALK, thick=1)
    faded_paint(m, 855, 904, 167, 720, RA.lch(.33, .07, 24), thick=2)
    # 果酱店：门开在高处的石台上，门前一截只凿了一半的台阶（半截台阶）
    pillar_rock(m, 964, lb, 100, 214, 924)
    opening(m, 958, 72, 5, 7, "arch", True)
    opening(m, 978, 40, 4, 6, "arch", True)
    opening(m, 940, 30, 4, 6, "arch", False)
    ledge(m, 960, 994, 176)
    opening(m, 974, 163, 8, 13, "arch", True, True, pal=BM.STONE)
    for i in range(4):
        sx, sy = 934 + i * 7, OS_LOW - (i + 1) * 7
        m.rect(sx, sy, sx + 8, OS_LOW, BM.STONE[2])
        m.hline(sx, sx + 8, sy, BM.STONE[5])
        m.vline(sx + 7, sy, OS_LOW, BM.STONE[3])
    for k in range(6):
        m.px(963 + k % 3, OS_LOW - 34 + k, BM.STONE[0])
    opening(m, 930, 116, 9, 8, "rect", True, pal=BM.STONE)             # 窗里一排果酱罐
    for k in range(3):
        m.rect(931 + k * 3, 120, 933 + k * 3, 124, HUSK)
        m.px(931 + k * 3, 119, BM.WOOD[3])
    opening(m, 990, 116, 5, 7, "arch", True, pal=BM.STONE)
    wood_sign(m, 946, 140, "jar")
    carved_sign(m, 980, 200, "jar")
    opening(m, 922, 208, 6, 8, "arch", False, pal=BM.STONE)
    # 仓库外墙：一块方石头凿出来的（不垒石块），窗都用石头封了；外侧一个旧挂钩，挂着一只铜铃（铃舌被泥堵住）
    pillar_rock(m, 1140, lb, 76, 150, 75)
    for k in range(2):
        m.rect(1116 + k * 30, 140, 1124 + k * 30, 150, BM.STONE[0])
        m.rect(1117 + k * 30, 141, 1123 + k * 30, 150, BM.STONE[2])
    m.rect(1110, 192, 1120, 194, C(.18, 250))
    m.line(1118, 194, 1118, 200, C(.24, 250))
    m.px(1117, 200, C(.24, 250))
    bell = [C(.3, 62, .04), C(.23, 62, .035), C(.37, 62, .04)]
    for r in range(7):
        hw = 1 + r // 2
        m.hline(1118 - hw, 1118 + hw + 1, 201 + r, bell[1])
        m.px(1118 + hw, 201 + r, bell[2])
    m.hline(1114, 1123, 208, bell[0])
    m.rect(1117, 209, 1120, 211, C(.12, 40, .03))
    # 右头留白（1180..1280）：只有一盏路灯、水和后面的石柱
    lamp_post(m, 1236, lb, 30)
    # 泡过水的那一截：水位线以下颜色更暗、更湿，长着青苔斑
    # （第四版：整片均匀压暗，不再隔一格压——那是一片棋盘格；苔斑随机撒成小团，不排成格子）
    wet_rng = np.random.default_rng(77)
    for y in range(158, H):
        t = round(min(0.2, 0.07 + (y - 158) / 600) * 32) / 32
        row = m.a[y]
        for x in np.nonzero(row[:, 3])[0]:
            o = tuple(int(v) for v in row[x, :3])
            if o[0] - o[2] > 10 or y == gy_os(x):
                continue
            m.px(x, y, mix(o, C(.06, 258), t))
    for _ in range(90):
        x, y = int(wet_rng.integers(0, OS_W)), int(wet_rng.integers(160, H))
        for k in range(int(wet_rng.integers(2, 6))):
            xx, yy = x + int(wet_rng.integers(-2, 3)), y + int(wet_rng.integers(-1, 2))
            o = m.get(xx, yy)
            if o is not None and o[0] - o[2] <= 10 and yy != gy_os(xx):
                m.px(xx, yy, MOSS[0])
    # 水在每一档停过很久的地方留下的一圈水渍（浅色的钙线，下面挂一溜苔）——和刻线石壁上的线对得上
    # （第四版：钙线不再是一条固定的浅灰虚线，是底下那块石头提一点亮，断处随机，宽窄不一）
    ring_rng = np.random.default_rng(78)
    for lv in ("l1", "l2", "l3"):
        yy = WATER[lv]
        on = True
        for x in range(OS_W):
            if ring_rng.random() < 0.06:
                on = not on
            o = m.get(x, yy)
            if not on or gy_os(x) + 2 >= yy or o is None or o[0] - o[2] > 10:
                continue
            m.px(x, yy, mix(o, C(.3, 236, .015), 0.35))
            r = ring_rng.random()
            if r < 0.25:
                m.blend(x, yy + 1, MOSS[1], 0.6)
                if r < 0.07:
                    m.blend(x, yy + 2, MOSS[0], 0.6)
    for rx_ in (96, 236, 318):                   # 码头石岸上的系船铁环：钉进石头的一块铁板 + 一根销，环垂下来，环在墙上落一道影子
        m.rect(rx_ - 1, 163, rx_ + 3, 166, IRON)
        m.px(rx_ + 2, 163, IRON_LIT)
        m.px(rx_ + 1, 166, IRON)
        for a_ in np.linspace(0, 2 * np.pi, 20, endpoint=False):
            x_, y_ = rx_ + 1 + 2.5 * np.cos(a_), 169.5 + 2.5 * np.sin(a_)
            m.blend(x_ - 1, y_ + 1, BM.STONE[0], 0.6)          # 影子（月光从右上来，落在左下）
        for a_ in np.linspace(0, 2 * np.pi, 20, endpoint=False):
            m.px(rx_ + 1 + 2.5 * np.cos(a_), 169.5 + 2.5 * np.sin(a_), IRON_LIT if (np.sin(a_) < 0 and np.cos(a_) > -0.3) else IRON)
    ground_ao(m, lambda x: OS_UP, 0, 440)
    ground_ao(m, gy_os, 580, OS_W)
    L["main"] = m

    # ---- water / ripples
    L["water"] = water_img(OS_W)
    L["ripples"] = ripples_img(OS_W, [162, 44, 699, 1236, 811])

    # ---- front（scroll 1.3）
    fw = 480 + int((OS_W - 480) * 1.3) + 4
    fr = Cv(fw)
    for (x0, x1, low) in [(120, 380, 24), (980, 1240, 18)]:
        n = x1 - x0
        for i in range(n + 1):
            t = i / n
            fr.px(x0 + i, low * 4 * t * (1 - t) - 2, DARK)
        for t in (0.3, 0.7):
            lantern(fr, int(x0 + n * t), int(low * 4 * t * (1 - t)) + 3, hang=3, big=True)
    for (x, hgt, seed) in [(640, 60, 3), (1420, 84, 4)]:
        frond(fr, x, H, hgt, seed)
    L["front"] = fr

    O = {wid: wheel_frames(wid) for wid in WHEELS}
    O["sluice_pipes"] = pipes_frames()
    O["oldstreet_height_wall"] = height_mark()
    O["oldstreet_steps"] = np.zeros((1, 1, 4), np.uint8)    # 空的：水位 prop 的名字，有了这个物件引擎就不在 marker 那儿画占位色块
    return L, O


def wheel_frames(wid):
    """闸轮。小的（1、2）：后面一块圆刻度盘，四个刻度（1~4 个点），手轮 4 根辐条，一颗把手指着现在那一格；
    帧 0..3 = 第 1..4 格（n1..n4），帧 4 = 对上了（set：指着对的格子，旁边一道粉笔记号）。
    大的（3）：8 根辐条，铭牌在墙上；帧 0 = 关着，帧 1 = 拧开了（set）。"""
    x, y, w, h = WHEELS[wid]
    big = wid == "sluice_wheel_3"
    metal = RA.bramp(5, .16, .52, 256, 244)
    right = {"sluice_wheel_1": 2, "sluice_wheel_2": 3}.get(wid, 0)
    nf = 2 if big else 5
    out = np.zeros((h, w * nf, 4), np.uint8)
    cx, cy = (w - 1) / 2, (h - 1) / 2 + (0 if big else 1)
    R = (min(w, h) / 2 - 1)
    for f in range(nf):
        cv = Cv(w, h)
        if not big:
            for yy in range(h):         # 刻度盘
                for xx in range(w):
                    d = np.hypot(xx - cx, yy - cy)
                    if d <= R:
                        rim = d > R - 1.2
                        cv.px(xx, yy, (STONE[5] if (xx - cx) - (yy - cy) > 0 else STONE[3]) if rim else STONE[0])
            for k in range(4):         # 刻度：上、右、下、左；第 k+1 格画 k+1 个点
                ang = -np.pi / 2 + k * np.pi / 2
                for j in range(k + 1):
                    off = (j - k / 2) * 2
                    tx = cx + np.cos(ang) * (R - 2) - np.sin(ang) * off
                    ty = cy + np.sin(ang) * (R - 2) + np.cos(ang) * off
                    cv.px(tx, ty, STONE[6])
            rr = R - 4.5
            notch = (f + 1) if f < 4 else right
            spokes = 4
            rot = -np.pi / 2 + (notch - 1) * np.pi / 2
        else:
            rr = R - 1
            spokes = 8
            rot = -np.pi / 2 + (np.pi / 3 if f == 1 else 0)
        for a in np.linspace(0, 2 * np.pi, 120, endpoint=False):     # 轮圈（右上亮）
            for dr in (0, 0.9):
                xx, yy = cx + np.cos(a) * (rr - dr), cy + np.sin(a) * (rr - dr)
                lit = np.cos(a - (-np.pi / 4))
                cv.px(xx, yy, metal[3] if lit > 0.5 and dr == 0 else metal[2] if lit > -0.3 else metal[1])
        for k in range(spokes):
            a = rot + k * 2 * np.pi / spokes
            for t in np.linspace(0, rr - 1, int(rr * 2)):
                cv.px(cx + np.cos(a) * t, cy + np.sin(a) * t, metal[2] if k else metal[3])
        cv.rect(int(cx) - 1, int(cy) - 1, int(cx) + 2, int(cy) + 2, metal[1])
        cv.px(int(cx) + 1, int(cy) - 1, metal[4])
        ax, ay = cx + np.cos(rot) * (rr + 1.5), cy + np.sin(rot) * (rr + 1.5)    # 把手（指着那一格）
        cv.rect(int(round(ax)) - 1, int(round(ay)) - 1, int(round(ax)) + 2, int(round(ay)) + 2, metal[2])
        cv.px(int(round(ax)), int(round(ay)) - 1, metal[4])
        cv.px(int(round(ax)) + 1, int(round(ay)), metal[4])
        if not big and f == 4:          # 粉笔记号
            ang = -np.pi / 2 + (right - 1) * np.pi / 2
            tx, ty = cx + np.cos(ang) * (R + 0.2), cy + np.sin(ang) * (R + 0.2)
            for d in (-2, -1, 0, 1, 2):
                cv.px(tx - np.sin(ang) * d + np.cos(ang) * 0.6, ty + np.cos(ang) * d + np.sin(ang) * 0.6, CHALK)
        out[:, f * w:(f + 1) * w] = cv.a
    return out


def pipes_frames():
    """sluice_pipes：17 帧 54×40（物件左上 = PIPES_OBJ）。a = 左边小闸轮那根（出水口 x 440，水面 submerged 156 上冒泡），
    b = 右边那根（出水口 x 470，水位 l1 178 时冒泡）。每档 4 帧（100ms 一帧）：
    0..3 a_bubble_3（翻滚，一圈白沫）、4..7 a_bubble_2（零星几个泡）、8..11 b_bubble_3、12..15 b_bubble_2、16 still（不冒）。"""
    ox, oy, w, h = PIPES_OBJ
    out = np.zeros((h, w * 17, 4), np.uint8)
    foam = [C(.58, 246, .02), C(.45, 248, .02), C(.33, 250)]

    def bubbles(cv, sx, sy, level, f):
        """管口正上方的水面：3 档 = 翻滚的一团（白沫鼓起来、泡往上冒、一圈被搅乱的亮水纹）；2 档 = 零星几个泡。"""
        rng = np.random.default_rng(100 + f + level * 10)
        if level == 3:
            for k in range(-9, 11):                      # 一圈被搅乱的水纹
                if (k + f * 2) % 4 < 2 and abs(k) > 3:
                    cv.px(sx + k, sy + (1 if abs(k) > 6 else 0), foam[2])
            dome = [(-3, 0), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (3, 0), (-2, -1), (-1, -1), (0, -1), (1, -1),
                    (2, -1), (-1, -2), (0, -2), (1, -2)]
            h_ = [0, 1, 2, 1][f]                         # 白沫一鼓一落
            for (dx, dy) in dome:
                if dy >= -h_ or dy == 0:
                    cv.px(sx + dx, sy + dy, foam[0] if dy < 0 or abs(dx) < 2 else foam[1])
            for k in range(4):                           # 往上冒的泡（一个个圆圈）
                by = sy - 3 - ((f + k * 2) % 5)
                bx = sx + [-4, 3, -1, 5][k]
                if by < sy - 2:
                    cv.px(bx, by, foam[0])
                    cv.px(bx + 1, by, foam[1])
        else:
            for k in range(-5, 6):
                if (k + f) % 5 == 0:
                    cv.px(sx + k, sy, foam[2])
            bx = sx + [-1, 1, 0, 2][f]
            cv.px(bx, sy, foam[0])
            cv.px(bx + 1, sy, foam[1])
            if f in (1, 2):
                cv.px(bx, sy - 1 - (f - 1), foam[0])
    seq = [("a", 3), ("a", 2), ("b", 3), ("b", 2)]
    for i, (p, lv) in enumerate(seq):
        for f in range(4):
            cv = Cv(w, h)
            if p == "a":
                bubbles(cv, PIPE_A_X + 1 - ox, WATER["submerged"] - oy, lv, f)
            else:
                bubbles(cv, PIPE_B_X + 1 - ox, WATER["l1"] - oy, lv, f)
            out[:, (i * 4 + f) * w:(i * 4 + f + 1) * w] = cv.a
    return out


def height_mark():
    """oldstreet_height_wall：2 帧 20×12（贴在身高墙红线上方）。帧 0 空；帧 1 = 看过以后，妮芙在红线旁边添的一道新粉笔记号。"""
    w, h = 20, 12
    out = np.zeros((h, w * 2, 4), np.uint8)
    cv = Cv(w, h)
    chalk = C(.42, 250, .015)                      # 新的粉笔：比石头亮，但不发光
    for x in range(3, 13):
        if x not in (6, 11):
            cv.px(x, 6, chalk)
    cv.line(14, 4, 16, 8, chalk)
    cv.line(16, 4, 14, 8, chalk)
    out[:, w:] = cv.a
    return out


# ---------------------------------------------------------------- room.json

def keep(path):
    return json.loads(path.read_text()) if path.exists() else {}


SKY_LAYERS = [
    {"id": "sky", "img": "res://art/river/sky.png", "scroll": 0.0, "y": 0},
    {"id": "ridge", "img": "res://art/river/ridge.png", "scroll": 0.05, "y": 0, "tile": True},
    {"id": "mist", "img": "res://art/river/mist.png", "scroll": 0.1, "y": 0, "tile": True, "drift": -2.5},
    {"id": "glints", "img": "res://art/river/glints.png", "scroll": 0.0, "y": 155, "shader": "water",
     "shader_params": {"palette_mode": True, "wobble": 2.0}},
    {"id": "far", "img": "far.png", "scroll": 0.2, "y": 0, "tile": True},
    {"id": "mid", "img": "mid.png", "scroll": 0.6, "y": 0},
    {"id": "main", "img": "main.png", "scroll": 1.0, "y": 0},
]
NOTE = "tools/river_town_moon_art.py 生成，别手改。约定见 docs/river_rooms_contract.md。"
BG = ["#03060f", "#0a1424"]


def market_sky_layers():
    """市集站在高处：天换成自己的 sky.png（地平线 MK_HZ），河岸的远石柱和雾整层往下挪 MK_DY，
    月光碎片换成河岸那套 river_moonpath.gdshader 的竖条遮罩（moonpath.png），从压低了的地平线开始。"""
    out = []
    for l in SKY_LAYERS:
        l = dict(l)
        if l["id"] == "sky":
            l["img"] = "sky.png"
        elif l["id"] in ("ridge", "mist"):
            l["y"] = MK_DY
        elif l["id"] == "glints":
            l = {"id": "glints", "img": "moonpath.png", "scroll": 0.0, "y": MK_HZ + 1, "shader": "moonpath",
                 "shader_params": dict(BM.MOON_PARAMS)}
        out.append(l)
    return out


def market_json(old):
    j = {"_note": NOTE, "size": [MK_W, H], "env": "river", "bg": BG,
         "layers": market_sky_layers() + [
             {"id": "rail", "img": "rail.png", "scroll": 1.0, "y": 0, "front": True},
             {"id": "front", "img": "front.png", "scroll": 1.3, "y": 0, "front": True}],
         "ground": MK_G}
    j["markers"] = old.get("markers", {})
    j["objects"] = {
        "market_baskets": {"x": 46, "y": 187, "w": 70, "h": 40, "frames": 2, "ms": 600, "front": True,
                           "states": {"default": [0, 1]}},
        "market_tools": {"x": 300, "y": STALL_ROD, "w": 76, "h": 26, "frames": 4, "fps": 4, "states": {"default": [0, 3]}},
        "market_breather_stall": {"x": 489, "y": 171, "w": 30, "h": 22, "frames": 2,
                                  "states": {"default": 0, "tank_on_counter": 1}},
    }
    j["walk"] = old.get("walk", [10, 1380])
    # 10-31 作者：戴帽子提篮子的路人（vendor）先不出场，美术姐画了新的再加回来：
    # {"npc": "vendor", "path": [[160, 199], [250, 199]], "speed": 8, "pause": [4, 10], "z": -20, "loop": "pingpong"}
    for k in ("portals", "ambient", "walk_when", "origin", "water", "scripts"):
        if k in old:
            j[k] = old[k]
    return j


def oldstreet_json(old):
    j = {"_note": NOTE, "size": [OS_W, H], "env": "river", "bg": BG,
         "layers": [l for l in SKY_LAYERS if l["id"] != "glints"] + [
             {"id": "water", "img": "water.png", "scroll": 1.0, "y": WATER["submerged"], "water": True, "front": True,
              "alpha": 0.55},
             {"id": "ripples", "img": "ripples.png", "scroll": 1.0, "y": WATER["submerged"] - 1, "water": True,
              "front": True, "shader": "water", "shader_params": {"palette_mode": False, "show": 0.7, "wobble": 1.0}},
             {"id": "front", "img": "front.png", "scroll": 1.3, "y": 0, "front": True}],
         "ground": OS_GROUND}
    j["markers"] = old.get("markers", {})
    j["markers"]["sluice_pipes"] = (PIPE_A_X + PIPE_B_X) // 2
    wheel_states = {}
    for wid, (x, y, w, h) in WHEELS.items():
        if wid == "sluice_wheel_3":
            st = {f"pos{k}": 0 for k in range(8)}
            st.update({"default": 0, "ready": 0, "set": 1})
            nf = 2
        else:
            start = {"sluice_wheel_1": 4, "sluice_wheel_2": 1}[wid]
            st = {f"pos{k}": k % 4 for k in range(8)}
            st.update({f"n{k}": k - 1 for k in range(1, 5)})
            st.update({"default": start - 1, "ready": start - 1, "set": 4})
            nf = 5
        wheel_states[wid] = {"x": x, "y": y, "w": w, "h": h, "frames": nf, "states": st}
    ox, oy, w, h = PIPES_OBJ
    j["objects"] = dict(wheel_states)
    j["objects"]["sluice_pipes"] = {
        "x": ox, "y": oy, "w": w, "h": h, "frames": 17, "z": 130,
        "states": {"a_bubble_3": [0, 3], "a_bubble_2": [4, 7], "b_bubble_3": [8, 11], "b_bubble_2": [12, 15],
                   "still": 16, "bubble_3": [0, 3], "bubble_2": [4, 7], "bubble_1": [12, 15], "default": [0, 3]}}
    j["objects"]["oldstreet_height_wall"] = {"x": 880, "y": 160, "w": 20, "h": 12, "frames": 2,
                                             "states": {"default": 0, "seen": 1}}
    j["objects"]["oldstreet_steps"] = {"x": 0, "y": 0, "w": 1, "h": 1, "frames": 1,
                                       "states": {k: 0 for k in ["default"] + list(WATER)}}
    for k in ("water", "walk", "walk_when", "portals", "ambient", "origin", "scripts"):
        if k in old:
            j[k] = old[k]
    j["water"]["levels"] = dict(WATER)
    for a in j.get("ambient", []):
        if a.get("name") == "pipe_gurgle":
            a["x"] = (PIPE_A_X + PIPE_B_X) // 2
    j["water"]["y"] = WATER["submerged"]
    return j


# ---------------------------------------------------------------- 预览

def preview(room, cam_x, path, water_y=None, chen_x=None):
    """按 room.json 合成一屏（镜头左边缘 cam_x），物件取 default 状态；放大 2 倍。"""
    d = OUT / room
    j = json.loads((d / "room.json").read_text())
    out = Image.new("RGBA", (480, H), (0, 0, 0, 255))
    wy0 = j.get("water", {}).get("y", 0)
    shift = (water_y - wy0) if (water_y is not None and "water" in j) else 0
    items = []
    for i, l in enumerate(j["layers"]):
        items.append((l.get("z", (100 if l.get("front") else -100) + i), "L", l))
    for oid, o in j.get("objects", {}).items():
        items.append((o.get("z", 50 if o.get("front") else -1), "O", (oid, o)))
    items.append((0, "C", None))
    items.sort(key=lambda t: t[0])
    for _, kind, it in items:
        if kind == "L":
            if it.get("shader_params", {}).get("palette_mode"):
                continue
            src = it["img"]
            p = ROOT / src[6:] if src.startswith("res://") else d / src
            im = Image.open(p).convert("RGBA")
            if it.get("shader") == "moonpath":
                im = Image.fromarray(BM.moonpath_rgb(np.array(im), cam_x))
            sx = int(round(cam_x * it["scroll"]))
            y = it.get("y", 0) + (shift if it.get("water") else 0)
            if it.get("tile"):
                tw = im.size[0]
                for k in range(-1, 480 // tw + 3):
                    lay = Image.new("RGBA", (480, H))
                    lay.paste(im, (k * tw - sx % tw, y))
                    out.alpha_composite(_alpha(lay, it.get("alpha", 1)))
            else:
                lay = Image.new("RGBA", (480, H))
                lay.paste(im, (-sx, y))
                out.alpha_composite(_alpha(lay, it.get("alpha", 1)))
        elif kind == "O":
            oid, o = it
            im = Image.open(d / f"{oid}.png").convert("RGBA")
            st = o.get("states", {}).get("default", 0)
            fi = st[0] if isinstance(st, list) else st
            fr = im.crop((fi * o["w"], 0, (fi + 1) * o["w"], o["h"]))
            lay = Image.new("RGBA", (480, H))
            lay.paste(fr, (o["x"] - cam_x, o["y"]))
            out.alpha_composite(lay)
        elif chen_x is not None:
            g = j["ground"]
            gy = g if isinstance(g, int) else int(np.interp(chen_x, [p[0] for p in g], [p[1] for p in g]))
            lay = Image.new("RGBA", (480, H))
            px = lay.load()
            for yy in range(gy - 38, gy):
                for xx in range(chen_x - cam_x - 4, chen_x - cam_x + 4):
                    if 0 <= xx < 480:
                        px[xx, yy] = (226, 222, 214, 255) if yy < gy - 30 else (120, 70, 60, 255)
            out.alpha_composite(lay)
    out.resize((960, 540), Image.NEAREST).save(path)


def _alpha(im, a):
    if a >= 1:
        return im
    arr = np.array(im)
    arr[..., 3] = (arr[..., 3].astype(float) * a).astype(np.uint8)
    return Image.fromarray(arr)


def check_alpha(d):
    for p in sorted(d.glob("*.png")):
        a = np.array(Image.open(p).convert("RGBA"))[..., 3]
        bad = ((a > 0) & (a < 255)).sum()
        if bad:
            print("半透明像素：", p.name, bad)


def hand_edited():
    """art/手改清单.json 里登记的作者手改图（相对 art/ 上一级的路径）：这些文件一张都不许覆盖。"""
    p = ROOT / "art" / "手改清单.json"
    return set(json.loads(p.read_text()).get("files", {})) if p.exists() else set()


def build(room):
    d = OUT / room
    d.mkdir(parents=True, exist_ok=True)
    old = keep(d / "room.json")
    if room == "market":
        L, O = market_layers()
        j = market_json(old)
    else:
        L, O = oldstreet_layers()
        j = oldstreet_json(old)
    locked = hand_edited()

    def save(name, write):
        rel = (d / name).relative_to(ROOT).as_posix()
        if rel in locked:
            print("跳过（作者手改，见 art/手改清单.json）:", rel)
            return
        write(d / name)
    for k, cv in L.items():
        save(f"{k}.png", cv.save)
    for k, img in O.items():
        save(f"{k}.png", Image.fromarray(img).save)
    if room == "market":
        save("sky.png", Image.fromarray(market_sky()).save)
        save("moonpath.png", Image.fromarray(market_moonpath()).save)
    (d / "room.json").write_text(json.dumps(j, ensure_ascii=False, indent=1) + "\n")
    for stale in ("shafts.png", "shafts.png.import"):     # 旧版的光柱层不用了
        if (d / stale).exists():
            (d / stale).unlink()
    check_alpha(d)
    print("ok", room, {k: v.a.shape[:2] for k, v in L.items()})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="合成预览存到这个目录")
    ap.add_argument("--only", default="market,oldstreet")
    args = ap.parse_args()
    rooms = [r for r in args.only.split(",") if r]
    for r in rooms:
        build(r)
    if args.preview:
        pd = Path(args.preview)
        pd.mkdir(parents=True, exist_ok=True)
        if "market" in rooms:
            for cx, chx in [(0, 120), (240, 504), (560, 830), (900, 1100), (960, 1300)]:
                preview("market", cx, pd / f"market_{cx}.png", chen_x=chx)
        if "oldstreet" in rooms:
            for cx, wy, chx in [(80, 156, 300), (300, 156, 446), (560, 246, 800), (800, 246, 1066), (300, 200, 500)]:
                preview("oldstreet", cx, pd / f"oldstreet_{cx}_{wy}.png", water_y=wy, chen_x=chx)
