"""河流篇 · 月夜水上小镇：高处市集 market、旧街 + 水闸 oldstreet 两个房间。以后改这两间的图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_town_moon_art.py [--preview 目录] [--only market,oldstreet]

输出 art/river_city/market/*、art/river_city/oldstreet/*（图 + room.json，覆盖旧的灰色大都市版）。之后跑一次 `--headless --import`。

世界和河岸（art/river/*，tools/river_art.py）是同一个：深蓝的月夜，月亮在右上，远处雾里立着巨大的石柱。
这里是河上的一座小镇——不是城市，也没有砖房和吊脚楼（作者 10-30）：人家是巨石 / 石柱里凿出来的洞窟屋，或者大块粗石
垒的矮屋，一间间分开；门窗是石头里凿出的洞，透着暖黄的灯。石头的画法、颜色直接用河岸那份 tools/river_bank_moon_art.py 的
（boulder_house / stone_hut / carve / shade_mass / stone_lantern），三个外景的石头一个样。到处是石像（和水底那颗石头人头同一张脸）。
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


def bg(y):
    """这一行背后的天 / 水的颜色（不算月光的那团亮）。"""
    return RA.L_color(float(RA.quant_L(RA.base_L(y))), y)


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


def fog(cv, t_of_y, steps=6):
    """整层往背后的天 / 水色褪 t(y)（分档 + Bayer 抖动，不出横向台阶）。"""
    a = cv.a
    xs = np.arange(cv.w)
    for y in range(cv.h):
        m = a[y, :, 3] > 0
        if not m.any():
            continue
        tc = float(np.clip(t_of_y(y), 0, 1)) * steps
        lo = np.floor(tc)
        tq = (lo + (BAYER[y % 4, xs % 4] < tc - lo)) / steps
        b = bg(y)
        for x in np.nonzero(m)[0]:
            if tq[x] > 0:
                a[y, x, :3] = mix(a[y, x, :3], b, min(1.0, tq[x]))


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
    """码头边当系缆桩的小石头人头（脖子埋在石沿里）。"""
    img, m = head_relief(s, RA.bramp(5, .07, .34, 262, 250))
    return img


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

def far_town(seed, width=960, waterline=151, n=9):
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
    fog(cv, lambda y: 0.5 + 0.3 * np.clip((y - 120) / 30, 0, 1))
    for (lx, ly) in lights:      # 灯点和倒影（褪过雾以后再点，雾里的灯不褪）
        cv.px(lx, ly, WARM[2])
        cv.px(lx, ly + 1, HALO)
        for r, yy in enumerate(range(waterline + 2, waterline + 9, 2)):
            if rng.random() < 0.8:
                cv.hline(lx - (1 if r % 2 else 0), lx + 1, yy, REFL[1] if r < 2 else HALO)
    return cv, lights


def rope_bridge(cv, x0, y0, x1, y1, sag=6, lamps=(), pal=WOOD):
    """两点之间的细桥：一排木板（下沿）+ 一根扶绳，中间往下垂。lamps：在 0..1 哪几处挂小灯。"""
    n = int(abs(x1 - x0))
    pts = []
    for i in range(n + 1):
        t = i / max(1, n)
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t + sag * 4 * t * (1 - t)
        pts.append((x, y))
        cv.px(x, y, pal[2])
        cv.px(x, y + 1, pal[0])
        if i % 3 == 0:
            cv.px(x, y - 1, pal[3])
        cv.px(x, y - 6 + sag * 0.3 * 4 * t * (1 - t), pal[1])        # 扶绳
        if i % 8 == 0:
            cv.vline(int(round(x)), int(round(y - 6 + sag * 1.2 * t * (1 - t))), int(round(y)), pal[1])
    for t in lamps:
        x, y = pts[int(t * n)]
        lantern(cv, int(x), int(y) + 3, hang=2)


# ---------------------------------------------------------------- 石头住处（作者 10-30：不要砖房、不要吊脚楼——
# 房子是巨石 / 石柱里凿出来的洞窟屋，或者大块粗石垒的矮屋；门窗是石头里凿出的洞。石头的画法直接用河岸那份
# tools/river_bank_moon_art.py 的 boulder_house / stone_hut / carve / shade_mass，三个房间的石头一个样）

def rock(cv, x0, x1, base, top, seed, p=4.0, pal=None, moss=True):
    """一整块石头（底平、顶圆鼓，p 越大越方）。返回 (img, 左上 x, 左上 y)。"""
    rng = np.random.default_rng(seed)
    w, h = int(x1 - x0), int(base - top + 1)
    m = BM.blob_mask(w, h, rng, p=p, lump=0.06)
    img = BM.shade_mass(m, rng, pal or BM.STONE, cracks=(1 + w // 30) if w >= 12 else 0, strata=1 + h // 40)
    if moss:
        for xx in range(w):
            ys = np.nonzero(m[:, xx])[0]
            if len(ys) and rng.random() < 0.5:
                img[ys[0], xx, :3] = BM.MOSS[2] if rng.random() < 0.4 else BM.MOSS[1]
    cv.paste(img, int(x0), int(top))
    return img, int(x0), int(top)


def dwelling_pillar(cv, x, base, w, h, seed, wins, door_y=None, door_side=1, pal=None):
    """一根石柱，柱身上凿出人家：wins = [(相对底的 dy, 形, 宽, 高, 亮, 门)]；door_y 那一行开一扇门，门口伸出一块石台。
    返回石台外沿的 x（细桥从这里搭出去）。"""
    pal = pal or BM.STONE
    img = RA.pillar(w, h, seed, pal, crown=[BM.B(.07, .02, 258), BM.B(.1, .022, 252)], kind="tower")
    ox, oy = int(x - img.shape[1] // 2), int(base - img.shape[0] + 1)
    cv.paste(img, ox, oy)
    for (dy, kind, ww, hh, lit, door) in wins:
        r = BM.rows_of(img, ox, oy, base + dy + hh // 2)
        if r:
            BM.carve(cv, (r[0] + r[1]) // 2 - ww // 2, base + dy, ww, hh, kind, lit, door, pal=pal)
    if door_y is None:
        return x
    r = BM.rows_of(img, ox, oy, door_y - 6)
    if door_side > 0:
        BM.carve(cv, r[1] - 10, door_y - 13, 7, 13, "arch", True, True, pal=pal)
        a, b = r[1] - 4, r[1] + 9
    else:
        BM.carve(cv, r[0] + 4, door_y - 13, 7, 13, "arch", True, True, pal=pal)
        a, b = r[0] - 9, r[0] + 4
    cv.rect(a, door_y, b, door_y + 4, pal[2])
    cv.hline(a, b, door_y, pal[-1])
    cv.hline(a, b, door_y + 4, DARK)
    cv.vline(b - 1, door_y, door_y + 4, pal[-2])
    return b if door_side > 0 else a


def rock_town(width, spots, seed, foot=H + 6, pal=None):
    """中景：一根根从下面（水里）升上来的石柱，柱身上凿着几扇小窗（多数亮着），有的柱顶压着一间粗石小屋。
    spots = [(x, 柱顶 y, 柱宽, 窗数, 顶上有没有小屋)]。返回 (画布, [(x, 柱顶, 宽)])。"""
    pal = pal or BM.STONE_FAR
    cv = Cv(width)
    tops = []
    for i, (x, top, pw, nwin, hut) in enumerate(spots):
        rng = np.random.default_rng(seed + i)
        img = RA.pillar(pw, foot - top, seed + i, pal, crown=None if hut else [BM.B(.1, .02, 256), BM.B(.13, .022, 250)],
                        kind="tower")
        ox, oy = int(x - img.shape[1] // 2), int(foot - img.shape[0])
        cv.paste(img, ox, oy)
        ty = oy + int(np.nonzero(img[..., 3].any(1))[0][0])
        for k in range(nwin):
            y = ty + 10 + k * int(rng.integers(14, 22))
            r = BM.rows_of(img, ox, oy, y + 1)
            if r and r[1] - r[0] > 8:
                cx_ = (r[0] + r[1]) // 2 + int(rng.integers(-3, 4))
                BM.carve(cv, cx_ - 1, y, 3, 4, "arch", rng.random() < 0.8, False, pal=pal, glow_r=5)
        if hut:
            r = BM.rows_of(img, ox, oy, ty + 1)
            if r:
                BM.stone_hut(cv, r[0] + 1, r[1] - 1, ty, 11, seed + 50 + i, openings=(("rect", 3, 3, 2, 3, True, False),),
                             pal=pal)
        tops.append((x, ty, pw))
    return cv, tops


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


def ledge(m, a, b, y, pal=None):
    """从石壁上伸出来的一块石台（今天的门口，在水面以上）：厚 4，上沿亮，下面一道影子，底下一个凿出来的托。"""
    pal = pal or BM.STONE
    m.rect(a, y, b, y + 4, pal[2])
    m.hline(a, b, y, pal[-1])
    m.hline(a, b, y + 4, DARK)
    m.vline(b - 1, y, y + 4, pal[-2])
    for k in range(3):
        m.hline(a + 2 + k, b - 2 - k, y + 5 + k, pal[1])


# ---------------------------------------------------------------- 水

def water_img(width, h=120):
    """水层（Godot 里 alpha 0.55、在人前面）：最上一行是月光照亮的水面线，往下很快暗下去。"""
    cv = Cv(width, h)
    rng = np.random.default_rng(3)
    for y in range(h):
        L = .22 - .1 * min(1, y / 40) - .03 * min(1, y / 100)
        cv.hline(0, width, y, C(L, 254))
    for x in range(width):
        cv.px(x, 0, C(.34 if (x // 3 + rng.integers(0, 2)) % 3 else .28, 250))
        if rng.random() < 0.5:
            cv.px(x, 1, C(.27, 252))
    for _ in range(width // 6):             # 水下几道很淡的横纹
        x, y = rng.integers(0, width), rng.integers(4, 40)
        cv.hline(x, x + rng.integers(3, 9), y, C(.2, 252))
    return cv


def ripples_img(width, lamps, h=14, seed=4):
    """水面上一闪一闪的横纹（water shader 按 7 像素一段让它们出没）；灯底下一串碎的暖倒影。"""
    rng = np.random.default_rng(seed)
    cv = Cv(width, h)
    for y in range(0, h, 2):
        for _ in range(width // (10 + y * 2)):
            x = rng.integers(0, width)
            cv.hline(x, x + rng.integers(2, 6 - y // 4), y, C(.36 - y * .012, 250))
    for lx in lamps:
        for y in range(1, 9, 2):
            if rng.random() < 0.7:
                x0 = lx + int(rng.integers(-2, 2))
                cv.hline(x0, x0 + 2, y, REFL[1] if y < 4 else HALO)
    return cv


# ---------------------------------------------------------------- 市集 market（1440 宽，地面 200）

MK_W, MK_G = 1440, 200


def market_layers():
    rng = np.random.default_rng(11)
    G = MK_G
    L = {}
    # ---- far（scroll 0.2，平铺 960）
    L["far"], _ = far_town(21, n=10)

    # ---- mid（scroll 0.6）：从下面升上来的石柱，柱身上凿出人家（小窗透暖光），两处之间拉着细桥
    mw = 480 + int((MK_W - 480) * 0.6) + 4
    spots = [(40, 112, 30, 3, False), (150, 96, 40, 4, True), (262, 128, 26, 2, False), (390, 84, 46, 5, True),
             (520, 118, 30, 3, False), (640, 100, 38, 4, True), (760, 132, 28, 2, False), (880, 90, 44, 5, True),
             (1000, 120, 32, 3, False)]
    mid, tops = rock_town(mw, spots, 300)
    for i in (0, 4):                              # 只有两处拉着细桥
        (xa, ta, pa), (xb, tb, pb) = tops[i], tops[i + 1]
        rope_bridge(mid, xa + pa // 2 - 2, ta + 6, xb - pb // 2 + 2, tb + 6, sag=5, lamps=(0.5,))
    fog(mid, lambda y: 0.36 + 0.4 * np.clip((y - 150) / 120, 0, 1))
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
    m.paste(BM.shade_mass(shelf, np.random.default_rng(12), BM.STONE, cracks=18, strata=10, amp=0.45), 0, G)
    for x in range(MK_W):                         # 拱洞的内沿暗一格；平台面月光一条
        col = np.nonzero(shelf[:, x])[0]
        if len(col) and col[-1] + G < H - 1:
            m.px(x, col[-1] + G, DARK)
    m.hline(0, MK_W, G, BM.STONE[5])
    m.hline(0, MK_W, G + 1, BM.STONE[3])
    for p0, p1 in [(150, 300), (640, 800), (960, 1130)]:
        BM.lantern(m, (p0 + p1) // 2, 222, "hang")
    # 楼梯井（1320..1420）：拱里一段往下的石阶，接到下面的河岸
    for i in range(11):
        sx, sy = 1322 + i * 8, G + 8 + i * 6
        m.rect(sx, sy, sx + 9, sy + 6, BM.STONE[2])
        m.hline(sx, sx + 9, sy, BM.STONE[5])
        m.vline(sx + 8, sy, sy + 6, BM.STONE[3])
        m.rect(sx, sy + 6, sx + 9, min(H, sy + 14), BM.STONE[0])

    gb = G - 1                                    # 屋子的最下一行（踩在平台上）
    # 左头：一块巨石里凿穿的拱门（去旧街），门洞里挂一盏灯
    rock(m, 0, 40, gb, 112, 401, p=5)
    BM.carve(m, 9, 150, 20, 50, "arch", False, pal=BM.STONE)
    BM.lantern(m, 19, 158, "hang")
    # 吊篮那家：巨石屋
    BM.boulder_house(m, 88, gb, 72, 60, 41, openings=(("arch", 10, 26, 5, 7, True, False),
                                                      ("round", 52, 30, 6, 6, True, False),
                                                      ("arch", 30, 0, 9, 16, True, True)), pipe=54)
    BM.stone_lantern(m, 150, gb)
    # 修补摊：粗石矮屋，前面支着一块旧布篷，工具挂在篷下（market_tools）
    BM.stone_hut(m, 270, 386, gb, 44, 42, openings=(("rect", 84, 20, 7, 6, True, False),))
    for x in range(292, 392):
        y = 160 + (x - 292) // 25
        m.vline(x, 158, y + 3, BM.B(.13, .03, 230) if (x // 6) % 2 else BM.B(.16, .03, 226))
        m.px(x, 158, BM.B(.24, .03, 222))
        if x % 3 == 0:
            m.px(x, y + 3, DARK)
    for px_ in (291, 389):
        m.rect(px_, 158, px_ + 2, G, BM.WOOD[1])
        m.vline(px_ + 1, 158, G, BM.WOOD[3])
    BM.lantern(m, 381, 170, "hang")
    rock(m, 272, 290, gb, 180, 402, p=3)          # 门口一块当凳子的石头
    # 气瓶柜台：粗石矮屋，正面凿出一个大柜台窗口，里面亮着，架子上挂面罩、立着气瓶
    BM.stone_hut(m, 466, 558, gb, 56, 43, openings=(("arch", 76, 32, 5, 7, True, False),))
    m.rect(480, 153, 530, 157, BM.STONE[2])       # 窗口上的过梁石
    m.hline(480, 530, 153, BM.STONE[5])
    m.rect(482, 157, 528, 184, HUSK)
    m.rect(483, 158, 527, 183, mix(HALO, DARK, .35))
    m.hline(483, 527, 168, HUSK)
    for mx_ in (490, 500):
        m.vline(mx_ + 2, 158, 160, HUSK)
        m.rect(mx_, 160, mx_ + 5, 164, STONE[2])
        m.px(mx_ + 4, 160, STONE[4])
        m.px(mx_ + 2, 162, HUSK)
    for a_ in np.linspace(0, 2 * np.pi, 22):
        m.px(516 + 3.5 * np.cos(a_), 162 + 2.5 * np.sin(a_), STONE[1])
    for k, bx in enumerate((486, 497, 508, 519)):
        m.rect(bx, 172, bx + 5, 183, STONE[3] if k % 2 else STONE[2])
        m.hline(bx + 1, bx + 4, 171, STONE[3])
        m.vline(bx + 4, 172, 183, STONE[5])
        m.px(bx + 2, 170, STONE[1])
        m.hline(bx, bx + 5, 176, C(.3, 60, .05))
    m.rect(480, 183, 532, 187, BM.STONE[3])       # 石台面
    m.hline(480, 532, 183, BM.STONE[5])
    m.rect(498, 144, 516, 150, BM.WOOD[1])        # 招牌：一块木牌，画着一个气泡
    m.hline(498, 516, 144, BM.WOOD[4])
    for (bx, by) in [(502, 146), (505, 147), (510, 146)]:
        m.px(bx, by, CHALK)
    # 饼干摊：巨石屋，底下凿出一个烤炉口，门口一块石板摆着饼干
    BM.boulder_house(m, 656, gb, 92, 56, 44, openings=(("round", 68, 28, 6, 6, True, False),), pipe=62)
    BM.carve(m, 626, 182, 14, 12, "arch", True, True, pal=BM.STONE)
    m.rect(650, 184, 704, 188, BM.STONE[2])
    m.hline(650, 704, 184, BM.STONE[5])
    rock(m, 652, 702, gb, 188, 403, p=6)
    for bx in range(652, 702, 5):
        m.hline(bx, bx + 3, 182, C(.3, 70, .04))
        m.hline(bx, bx + 3, 183, C(.26, 70, .04))
    BM.lantern(m, 678, 168, "hang")
    # 屋顶之间的细桥：两根石柱，柱身上凿出人家，门口各伸出一块石台，石台之间一座窄木桥
    pa = dwelling_pillar(m, 772, gb, 42, 120, 450, [(-30, "arch", 4, 6, True, False), (-62, "arch", 4, 6, False, False)],
                         door_y=104, door_side=1)
    pb = dwelling_pillar(m, 894, gb, 48, 152, 451, [(-24, "arch", 5, 7, True, False), (-90, "round", 5, 5, True, False),
                                                    (-60, "arch", 4, 6, True, False)], door_y=84, door_side=-1)
    rope_bridge(m, pa, 104, pb, 84, sag=7, lamps=(0.3, 0.7))
    # 当中的石像：捧灯的人 + 两盏石灯笼
    st, _ = lamp_bearer()
    m.paste(st, 1060 - st.shape[1] // 2, G - st.shape[0])
    BM.stone_lantern(m, 986, gb)
    BM.stone_lantern(m, 1134, gb)
    # 妮芙常站的这家：粗石矮屋，大石板压顶
    BM.stone_hut(m, 1188, 1272, gb, 58, 47, openings=(("arch", 10, 26, 6, 8, True, False),
                                                       ("arch", 66, 26, 6, 8, True, False),
                                                       ("arch", 36, 0, 9, 17, True, True)))
    BM.stone_lantern(m, 1300, gb)
    for x0 in (1318, 1420):                       # 楼梯井口的两块石墩
        rock(m, x0, x0 + 7, gb, G - 16, 404 + x0, p=6)
    # 右头：一根巨大的石柱的边（镇子就靠着它）
    big = RA.pillar(40, 280, 77, BM.ROCK, kind="tower")
    m.paste(big, 1440 - big.shape[1] // 2 + 6, G + 40 - big.shape[0])
    for bx in (212, 586, 726, 938):               # 地上几只木桶
        m.rect(bx, G - 8, bx + 6, G, BM.WOOD[2])
        m.hline(bx, bx + 6, G - 8, BM.WOOD[4])
        m.hline(bx, bx + 6, G - 4, BM.WOOD[0])
        m.vline(bx + 5, G - 8, G, BM.WOOD[3])
    sm = bollard_head(0.15)
    m.paste(sm, 232, G - sm.shape[0])
    m.paste(sm, 1158 - sm.shape[1], G - sm.shape[0])
    fog_bottom(m, 236)
    L["main"] = m

    # ---- rail（人前面）：平台外沿的木栏杆，只在左边一段和楼梯井口
    rail = Cv(MK_W)
    for (x0, x1) in [(36, 136), (176, 252), (1308, 1430)]:
        for x in range(x0, x1):
            rail.px(x, 186, BM.WOOD[4])
            rail.px(x, 187, BM.WOOD[2])
            rail.px(x, 194, BM.WOOD[1])
        for x in range(x0, x1 + 1, 14):
            rail.rect(x, 186, x + 2, G + 1, BM.WOOD[1])
            rail.vline(x + 1, 186, G + 1, BM.WOOD[3])
    L["rail"] = rail

    # ---- front（scroll 1.3）
    fw = 480 + int((MK_W - 480) * 1.3) + 4
    fr = Cv(fw)
    for (x0, x1, low) in [(260, 520, 26), (1010, 1240, 20)]:
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


def fog_bottom(cv, y0):
    fog(cv, lambda y: 0 if y < y0 else ((y - y0) / (H - y0)) ** 1.2 * 0.95, steps=8)


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
    metal = RA.bramp(4, .14, .44, 256, 246)
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
    mid, tops = rock_town(mw, spots, 500)
    hd, _, _, _ = UA.stone_head()
    mid.paste(hd, 318, 226 - int(hd.shape[0] * 0.8))
    rope_bridge(mid, tops[1][0] + 13, tops[1][1] + 8, tops[2][0] - 21, tops[2][1] + 10, sag=6, lamps=(0.5,))
    rope_bridge(mid, tops[5][0] + 14, tops[5][1] + 8, tops[6][0] - 22, tops[6][1] + 10, sag=5, lamps=(0.5,))
    fog(mid, lambda y: 0.34 + 0.3 * np.clip((y - 150) / 100, 0, 1))
    rewarm(mid)
    L["mid"] = mid

    # ---- main
    m = Cv(OS_W)
    # 地基：上层码头、台阶、下层街面——整片的岩石（不是砖），顶面一条月光；几道竖的大石缝把它分成几块
    ground = np.zeros((H - OS_UP, OS_W), bool)
    for x in range(OS_W):
        ground[gy_os(x) - OS_UP:, x] = True
    m.paste(BM.shade_mass(ground, np.random.default_rng(64), BM.STONE, cracks=26, strata=14, amp=0.4), 0, OS_UP)
    for sx in (120, 300, 640, 870, 1180):
        for y in range(gy_os(sx) + 2, H):
            m.px(sx + int(1.5 * np.sin(y / 7.0)), y, DARK)
    for x in range(OS_W):
        g = gy_os(x)
        m.px(x, g, BM.STONE[5])
        m.px(x, g + 1, BM.STONE[3])
    for i in range(14):                         # 台阶的踏面（每一级右边亮）
        x0 = 440 + i * 10
        y0 = gy_os(x0)
        m.hline(x0, x0 + 10, y0, BM.STONE[5])
        m.vline(x0, y0, y0 + 6, BM.STONE[1])
    # 仓库入口：街面上一个往下的石口，石门框是两块立石 + 一块横石，里面黑水
    m.rect(1040, 236, 1092, H, DARK)
    for i in range(5):
        m.hline(1044 + i * 2, 1092 - i * 2, 240 + i * 6, BM.STONE[1])
    rock(m, 1028, 1040, 236, 196, 901, p=8, moss=False)
    rock(m, 1090, 1102, 236, 196, 902, p=8, moss=False)
    rock(m, 1026, 1104, 200, 190, 903, p=10)
    m.rect(1040, 201, 1090, 236, C(.05, 262))
    for i in range(6):
        m.hline(1042 + i * 4, 1062 + i * 4, 210 + i * 5, BM.STONE[1])

    ub = OS_UP - 1
    # 上层：左头一块巨石里凿出往上的石阶小巷（去市集）
    rock(m, 0, 30, ub, 60, 911, p=6)
    for i in range(7):
        x0, y0 = 4 + i * 5, 112 + i * 6
        m.rect(x0, y0, x0 + 8, y0 + 3, BM.STONE[2])
        m.hline(x0, x0 + 8, y0, BM.STONE[5])
    BM.stone_lantern(m, 44, ub)
    # 妮芙等的这家：巨石屋
    BM.boulder_house(m, 98, ub, 80, 62, 61, openings=(("arch", 10, 28, 5, 7, True, False), ("arch", 62, 28, 5, 7, True, False),
                                                       ("arch", 34, 0, 9, 16, True, True)), pipe=58)
    bh = bollard_head(0.16)
    m.paste(bh, 146, OS_UP - bh.shape[0])
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
    for x in range(262, 342):
        m.px(x, 128, BM.WOOD[4])
        m.px(x, 129, BM.WOOD[2])
    for x in range(262, 343, 13):
        m.rect(x, 128, x + 2, OS_UP, BM.WOOD[1])
        m.vline(x + 1, 128, OS_UP, BM.WOOD[3])
    # 两根管子：从小闸轮底下出来，顺着墙走，过了大闸轮就翻下码头钻进水里
    # （a：左边那只、下面那根，先下水；b：右边那只、上面那根，走得更远、下得更深）
    pipe_pal = RA.bramp(4, .15, .46, 252, 240)

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
    slab = np.zeros((H - 104, 38), bool)
    for x in range(38):
        slab[max(0, int(3 - 3 * np.sin(np.pi * (x + .5) / 38))):, x] = True
    m.paste(BM.shade_mass(slab, np.random.default_rng(63), BM.STONE, cracks=1, strata=0, amp=0.25), 400, 104)
    marks = [(WATER["submerged"], "19"), (WATER["l1"], "07"), (WATER["l2"], "96"), (WATER["l3"], "81")]
    for (yy, yr) in marks:
        m.hline(402, 436, yy, DARK)
        m.hline(402, 436, yy + 1, BM.STONE[5])
        tiny_digits(m, 405, yy - 6, yr, DARK)
        tiny_digits(m, 405, yy - 5, yr, BM.STONE[4])
        tiny_digits(m, 405, yy - 6, yr, DARK)
    for x in range(400, 438):
        for yy in range(WATER["l3"] - 3, WATER["l3"] + 4):
            if (x * 7 + yy * 3) % 5 < 3:
                m.px(x, yy, MOSS[(x + yy) % 2])

    lb = OS_LOW - 1
    # 下层旧街：一块块分开的巨石，人家凿在石头里。水面以上是今天的门（门口伸出一块石台）、亮着的窗、挂着的木店招；
    # 水面以下（泡过水）是更旧的一排门窗，同一块店招刻在石壁上（同名店）
    rk, rx, ry = rock(m, 588, 694, lb, 98, 921, p=5)
    ledge(m, 592, 622, 152)
    BM.carve(m, 600, 139, 8, 13, "arch", True, True, pal=BM.STONE)
    BM.carve(m, 630, 112, 5, 7, "arch", True, pal=BM.STONE)
    BM.carve(m, 652, 112, 5, 7, "arch", True, pal=BM.STONE)
    wood_sign(m, 632, 132, "cup")
    BM.carve(m, 598, 213, 9, 22, "arch", False, pal=BM.STONE)
    BM.carve(m, 628, 206, 6, 8, "arch", False, pal=BM.STONE)
    BM.carve(m, 664, 206, 6, 8, "arch", False, pal=BM.STONE)
    carved_sign(m, 638, 194, "cup")
    BM.lantern(m, 699, 150, "hang")
    m.hline(692, 700, 145, BM.B(.07, .015, 262))
    # 拐角：一块方一点的石头，角上凿了个灯龛
    rock(m, 724, 806, lb, 112, 922, p=7)
    BM.carve(m, 736, 128, 5, 7, "arch", True, pal=BM.STONE)
    BM.carve(m, 786, 130, 5, 7, "arch", True, pal=BM.STONE)
    BM.carve(m, 760, 140, 7, 10, "arch", True, pal=BM.STONE)
    m.px(763, 146, BM.WARM[4])
    BM.carve(m, 734, 216, 8, 19, "arch", False, pal=BM.STONE)
    BM.carve(m, 770, 208, 6, 8, "arch", False, pal=BM.STONE)
    # 身高刻线墙：一块磨平了的大石板，小孩的身高一道道刻在下面，上面一道红线 = 那年的洪水
    face = np.ones((OS_LOW - 140, 54), bool)
    face[:2, :3] = face[:2, -3:] = False
    m.paste(BM.shade_mass(face, np.random.default_rng(73), RA.bramp(5, .12, .3, 252, 240), cracks=1, strata=0, amp=0.18),
            852, 140)
    for k, hh in enumerate([16, 19, 21, 24, 26, 28, 31]):
        y0 = OS_LOW - hh
        x0 = 862 + (k % 3) * 4
        m.hline(x0, x0 + 10, y0, DARK)
        m.hline(x0, x0 + 10, y0 + 1, CHALK if k % 2 else C(.4, 250, .015))
    m.hline(854, 904, 168, RED)
    m.hline(854, 904, 169, mix(RED, C(.2, 250), .5))
    # 果酱店：门开在高处的石台上，门前一截只凿了一半的台阶（半截台阶）
    rock(m, 916, 1012, lb, 96, 924, p=5)
    ledge(m, 960, 994, 176)
    BM.carve(m, 974, 163, 8, 13, "arch", True, True, pal=BM.STONE)
    for i in range(4):
        sx, sy = 934 + i * 7, OS_LOW - (i + 1) * 7
        m.rect(sx, sy, sx + 8, OS_LOW, BM.STONE[2])
        m.hline(sx, sx + 8, sy, BM.STONE[5])
        m.vline(sx + 7, sy, OS_LOW, BM.STONE[3])
    for k in range(6):
        m.px(963 + k % 3, OS_LOW - 34 + k, BM.STONE[0])
    BM.carve(m, 930, 116, 9, 8, "rect", True, pal=BM.STONE)             # 窗里一排果酱罐
    for k in range(3):
        m.rect(931 + k * 3, 120, 933 + k * 3, 124, HUSK)
        m.px(931 + k * 3, 119, BM.WOOD[3])
    BM.carve(m, 990, 116, 5, 7, "arch", True, pal=BM.STONE)
    wood_sign(m, 946, 140, "jar")
    carved_sign(m, 980, 200, "jar")
    BM.carve(m, 922, 208, 6, 8, "arch", False, pal=BM.STONE)
    # 仓库外墙：大块粗石垒的矮房，窗都用石头封了；外侧一个旧挂钩，挂着一只铜铃（铃舌被泥堵住）
    BM.stone_hut(m, 1104, 1176, lb, 116, 75)
    for k in range(2):
        m.rect(1116 + k * 30, 140, 1124 + k * 30, 150, BM.STONE[0])
        m.rect(1117 + k * 30, 141, 1123 + k * 30, 150, BM.STONE[2])
    m.rect(1110, 192, 1120, 194, C(.18, 250))
    m.line(1118, 194, 1118, 200, C(.24, 250))
    m.px(1117, 200, C(.24, 250))
    bell = [C(.34, 62, .05), C(.27, 62, .05), C(.42, 62, .05)]
    for r in range(7):
        hw = 1 + r // 2
        m.hline(1118 - hw, 1118 + hw + 1, 201 + r, bell[1])
        m.px(1118 + hw, 201 + r, bell[2])
    m.hline(1114, 1123, 208, bell[0])
    m.rect(1117, 209, 1120, 211, C(.12, 40, .03))
    # 右头：一间亮着的巨石屋 + 石灯笼
    BM.boulder_house(m, 1224, lb, 66, 78, 76, openings=(("arch", 10, 50, 5, 7, True, False),
                                                          ("arch", 46, 50, 5, 7, True, False),
                                                          ("round", 28, 30, 5, 5, False, False),
                                                          ("arch", 28, 0, 9, 18, True, True)))
    BM.stone_lantern(m, 1268, lb)
    # 泡过水的那一截：水位线以下颜色更暗、更湿，长着青苔斑
    for y in range(158, H):
        t = min(0.22, 0.08 + (y - 158) / 500)
        row = m.a[y]
        for x in np.nonzero(row[:, 3])[0]:
            o = tuple(int(v) for v in row[x, :3])
            if o[0] - o[2] > 10:
                continue
            if y == gy_os(x):
                continue
            if (x * 13 + y * 7) % 23 == 0:
                m.px(x, y, MOSS[0])
            elif (x + y) % 2 == 0:
                m.px(x, y, mix(o, C(.06, 258), t))
    # 水在每一档停过很久的地方留下的一圈水渍（浅色的钙线，下面挂一溜苔）——和刻线石壁上的线对得上
    ring = C(.27, 240, .015)
    for lv in ("l1", "l2", "l3"):
        yy = WATER[lv]
        for x in range(OS_W):
            o = m.get(x, yy)
            if gy_os(x) + 2 < yy and o is not None and (x // 3 + yy) % 7 != 0 and o[0] - o[2] <= 10:
                m.px(x, yy, ring)
                if (x * 5 + yy) % 3 == 0:
                    m.px(x, yy + 1, MOSS[1])
                    if (x * 7) % 5 == 0:
                        m.px(x, yy + 2, MOSS[0])
    for rx_ in (96, 236, 318):                   # 码头石岸上的系船铁环
        for a_ in np.linspace(0, 2 * np.pi, 16, endpoint=False):
            m.px(rx_ + 2.5 * np.cos(a_), 168 + 2.5 * np.sin(a_), STONE[4] if np.sin(a_) < 0 else STONE[3])
        m.rect(rx_ - 1, 164, rx_ + 2, 166, DARK)
    L["main"] = m

    # ---- water / ripples
    L["water"] = water_img(OS_W)
    L["ripples"] = ripples_img(OS_W, [162, 44, 699, 1268, 763])

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
    cv.hline(3, 13, 6, CHALK)
    cv.line(14, 4, 16, 8, CHALK)
    cv.line(16, 4, 14, 8, CHALK)
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


def market_json(old):
    j = {"_note": NOTE, "size": [MK_W, H], "env": "river", "bg": BG,
         "layers": SKY_LAYERS + [
             {"id": "rail", "img": "rail.png", "scroll": 1.0, "y": 0, "front": True},
             {"id": "front", "img": "front.png", "scroll": 1.3, "y": 0, "front": True}],
         "ground": MK_G}
    j["markers"] = old.get("markers", {})
    j["objects"] = {
        "market_baskets": {"x": 46, "y": 187, "w": 70, "h": 40, "frames": 2, "ms": 600, "front": True,
                           "states": {"default": [0, 1]}},
        "market_tools": {"x": 300, "y": 168, "w": 76, "h": 26, "frames": 4, "fps": 4, "states": {"default": [0, 3]}},
        "market_breather_stall": {"x": 489, "y": 171, "w": 30, "h": 22, "frames": 2,
                                  "states": {"default": 0, "tank_on_counter": 1}},
    }
    j["walk"] = old.get("walk", [10, 1380])
    j["walkers"] = [{"npc": "vendor", "path": [[160, 199], [250, 199]], "speed": 8, "pause": [4, 10], "z": -20,
                     "loop": "pingpong"}]
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
    for k, cv in L.items():
        cv.save(d / f"{k}.png")
    for k, img in O.items():
        Image.fromarray(img).save(d / f"{k}.png")
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
