"""河流星的水城（第二章「妮芙的三分钟」）外景：河岸、高处市集、旧街 + 水闸、水下仓库、南桥。以后改这些图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_city_art.py [--preview 目录] [--only 房间,...]

输出 art/river_city/<room>/*.png（1 倍）+ room.json；共用的天和远楼在 art/river_city/common/。
方案：docs/river_plan.md 第 0、1、2 节；剧情姐原文 71–152 行（每个房间画了原文的哪一句，写在各房间函数的说明里）。

美术方向（作者定）：
- 只画正侧面，平面视差，不要透视（没有斜着往里收的面，屋顶、台阶、桥都只画立面）。
- 亮主角、暗背景：晨（白发 L≈0.95，斗篷 L≈0.6~0.8）和妮芙（鲸鱼妹的蓝青 L≈0.6~0.85、色度 0.10+）永远是画面里最亮、最艳的；
  背景整体是低饱和的石板灰蓝（OKLCh h≈238，色度 ≤0.03），最亮的是远处水线上的日光霾（L≈0.6）。
- 城市是灰色鸽子笼一样的高楼，一格一格的窗，重复、整齐；下半截泡在水里，细桥连着屋顶（原文 71）。
  人用兜帽路人（A 的人群脚本），表达的是冷漠，不是焦虑：楼整齐安静，没有闪烁、没有赶路的乱。
- 身份色：灰蓝做底，和鲸鱼妹的蓝青协调（水里的亮纹、水下的光偏青 h≈215）；
  暖色只给标签纸、铜铃、少数亮窗、面包店（琥珀 h≈70），面积很小。
- 白天，有阳光（看得见水下整齐的街砖，原文 80），不下雨。太阳在左上（立面左边一条受光、右边一条背光）。
规则（和森林、城市一样）：1 倍像素，alpha 只有 0/255，不描边；所有随机固定 seed；tile 的层左右无缝。
水是不透明像素画的：water 层在 room.json 里写 alpha（引擎用 modulate 叠），底下的 under 层是水下的东西本来的样子。
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
from oscarkit.palette import from_lch, oklab_to_srgb, to_lab  # noqa: E402
from oscarkit.measure import srgb_to_oklab  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "river_city"
SW, SH = 480, 270
TW = 960                      # tile 宽

HUE = 238                     # 石板灰蓝
H_WATER = 222                 # 水：比墙偏青一点（和鲸鱼妹的蓝青是一家）
H_GLINT = 212                 # 水里的亮纹、水下的光：更青
H_WARM = 72                   # 琥珀：标签纸、铜铃、面包店、少数亮窗
H_MOSS = 150                  # 苔：灰绿，压得很暗、很灰（不和森林的绿撞：色度 ≤0.025）


# ============================================================ 颜色

def C(L, c=0.012, h=HUE):
    return from_lch(float(np.clip(L, 0.02, 0.97)), float(c), float(h))


def mix(a, b, t):
    la, lb = to_lab(a), to_lab(b)
    return tuple(int(v) for v in oklab_to_srgb((la + (lb - la) * t)[None])[0])


def Lof(c):
    return float(to_lab(c)[0])


def stone(L, c=0.012, h=HUE, n=7, dL=0.035):
    """一种材料的色阶（暗 -> 亮），中间那档是 (L, c, h)；亮的往暖偏一点点、暗的往冷偏一点点。"""
    out = []
    for i in range(n):
        k = i - n // 2
        hh = h + (-10 if k > 0 else 6) * min(1, abs(k) / 3)
        out.append(C(L + k * dL, c * (1 + 0.08 * k), hh))
    return out


# 晨（白发 L≈.95、斗篷亮面 L≈.8）。背景亮度的上限：
L_MAX_BG = 0.66


def haze(L):
    """日光霾：亮的偏一点青白、暗的偏石板蓝。"""
    t = float(np.clip((L - 0.3) / 0.3, 0, 1))
    return C(L, 0.022 - 0.006 * t, HUE - 14 * t)


# 窗、门洞里面：白天屋里是暗的；玻璃上沿反一道天光
GLASS = C(0.17, 0.014, HUE + 6)
GLASS_SKY = C(0.30, 0.016, HUE - 6)
WARM_WIN = C(0.52, 0.075, H_WARM)        # 极少几扇亮着的窗（琥珀，压得很暗）
AMBER = C(0.70, 0.10, H_WARM)            # 标签纸、铜铃最亮那档（比晨暗）
PAPER = C(0.62, 0.028, 85)               # 标签纸（旧白）
PAPER_SH = C(0.50, 0.026, 80)


# ============================================================ 画布

class Cv:
    """RGBA 画布。wrap=True：横向自动折回（tile 的层左右无缝）。坐标都是整像素，区间左闭右开。"""

    def __init__(self, w, h, wrap=False):
        self.w, self.h, self.wrap = w, h, wrap
        self.a = np.zeros((h, w, 4), np.uint8)

    def _xs(self, x0, x1):
        if not self.wrap:
            x0, x1 = max(0, x0), min(self.w, x1)
            return [(x0, x1)] if x0 < x1 else []
        if x1 - x0 >= self.w:
            return [(0, self.w)]
        a, b = x0 % self.w, x0 % self.w + (x1 - x0)
        if b <= self.w:
            return [(a, b)]
        return [(a, self.w), (0, b - self.w)]

    def rect(self, x0, y0, x1, y1, c):
        y0, y1 = max(0, int(y0)), min(self.h, int(y1))
        if y0 >= y1:
            return
        for a, b in self._xs(int(x0), int(x1)):
            self.a[y0:y1, a:b, :3] = c[:3]
            self.a[y0:y1, a:b, 3] = 255

    def px(self, x, y, c):
        self.rect(x, y, x + 1, y + 1, c)

    def hline(self, x0, x1, y, c):
        self.rect(x0, y, x1, y + 1, c)

    def vline(self, x, y0, y1, c):
        self.rect(x, y0, x + 1, y1, c)

    def mask(self, m, c):
        self.a[m, :3] = c[:3]
        self.a[m, 3] = 255

    def clear(self, x0, y0, x1, y1):
        y0, y1 = max(0, int(y0)), min(self.h, int(y1))
        for a, b in self._xs(int(x0), int(x1)):
            self.a[y0:y1, a:b] = 0

    def poly_mask(self, pts):
        im = Image.new("1", (self.w, self.h), 0)
        ImageDraw.Draw(im).polygon([tuple(p) for p in pts], fill=1)
        return np.array(im, bool)

    def poly(self, pts, c):
        if self.wrap:
            for dx in (-self.w, 0, self.w):
                self.mask(self.poly_mask([(x + dx, y) for x, y in pts]), c)
        else:
            self.mask(self.poly_mask(pts), c)

    def line(self, pts, c, width=1):
        im = Image.new("1", (self.w, self.h), 0)
        d = ImageDraw.Draw(im)
        for dx in ((-self.w, 0, self.w) if self.wrap else (0,)):
            d.line([(x + dx, y) for x, y in pts], fill=1, width=width)
        self.mask(np.array(im, bool), c)

    def ellipse(self, cx, cy, rx, ry, c):
        Y, X = np.mgrid[0:self.h, 0:self.w]
        dx = X - cx
        if self.wrap:
            dx = (dx + self.w / 2) % self.w - self.w / 2
        self.mask(((dx + 0.5) / max(rx, .5)) ** 2 + ((Y - cy + 0.5) / max(ry, .5)) ** 2 <= 1.0, c)

    def paste(self, src, x, y, flip=False):
        """贴一张 RGBA（numpy 或 Cv）：不透明像素盖上去。"""
        s = src.a if isinstance(src, Cv) else src
        if flip:
            s = s[:, ::-1]
        h, w = s.shape[:2]
        y0, y1 = max(0, y), min(self.h, y + h)
        if y0 >= y1:
            return
        offs = (-self.w, 0, self.w) if self.wrap else (0,)
        for o in offs:
            px = x + o
            x0, x1 = max(0, px), min(self.w, px + w)
            if x0 >= x1:
                continue
            sl = s[y0 - y:y1 - y, x0 - px:x1 - px]
            m = sl[..., 3] > 0
            self.a[y0:y1, x0:x1][m] = sl[m]

    def recolor(self, m, fn):
        """把 m 里每种颜色换成 fn(颜色)（一对一换，不碎）。"""
        m = m & (self.a[..., 3] > 0)
        if not m.any():
            return
        cols, inv = np.unique(self.a[m][:, :3], axis=0, return_inverse=True)
        new = np.array([fn(tuple(int(v) for v in c)) for c in cols], np.uint8)
        sub = self.a[m]
        sub[:, :3] = new[inv.reshape(-1)]
        self.a[m] = sub

    def save(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(self.a, "RGBA").save(path)


def narrow_levels(lv):
    """档位抖动（照 cloud_art / city_art）：大片硬边，只在档边留窄窄一条棋盘格。"""
    lv = np.asarray(lv, float)
    h, w = lv.shape
    gy, gx = np.gradient(lv)
    g = np.hypot(gx, gy) + 1e-6
    lo = np.floor(lv + 1e-9)
    dn = (lo + 1 - lv) / g
    Y, X = np.mgrid[0:h, 0:w]
    p50 = (X + Y) % 2 == 0
    p25 = (X + 2 * (Y % 2)) % 4 == 0
    up = ((dn < 1.0) & p50) | ((dn >= 1.0) & (dn < 2.0) & p25)
    return (lo + up).astype(int)


def fog(cv: Cv, t_of_y, col_of_y, steps=10, m=None):
    """往霾里褪：每个不透明像素往「它那一行的霾色」推 t(y)。t、霾色都按档硬边分开（档边窄窄抖一条）。"""
    a = cv.a
    if m is None:
        m = a[..., 3] > 0
    Y = np.broadcast_to(np.arange(cv.h, dtype=float)[:, None], (cv.h, cv.w))
    tl = narrow_levels(np.vectorize(t_of_y)(Y[:, :1]).repeat(cv.w, 1) * steps)
    rows = np.unique(tl[m])
    lab = srgb_to_oklab(a[..., :3].reshape(-1, 3)).reshape(cv.h, cv.w, 3)
    hz = np.array([to_lab(col_of_y(y)) for y in range(cv.h)])[:, None, :]
    t = np.clip(tl / steps, 0, 1)[..., None]
    new = lab * (1 - t) + hz * t
    rgb = oklab_to_srgb(new.reshape(-1, 3)).reshape(cv.h, cv.w, 3)
    a[m, :3] = rgb[m]
    del rows


def shade_mask(cv: Cv, m, dL, dc=0.0, dh=0.0):
    """把 m 里的颜色整体压暗 / 提亮 dL（OKLab），一对一换色。"""
    def f(c):
        lab = to_lab(c)
        L = lab[0] + dL
        ch = math.hypot(lab[1], lab[2]) + dc
        h = math.degrees(math.atan2(lab[2], lab[1])) + dh
        return C(L, max(0, ch), h)
    cv.recolor(m, f)


def pnoise(n, seed, kmin=1, kmax=8, falloff=1.0):
    """一维周期噪声（长度 n 一圈，左右无缝），-1..1。"""
    rng = np.random.default_rng(seed)
    x = np.arange(n) / n
    out = np.zeros(n)
    for k in range(kmin, kmax + 1):
        out += rng.normal() / k ** falloff * np.sin(2 * np.pi * (k * x + rng.random()))
    return out / (np.abs(out).max() + 1e-9)


# ============================================================ 共用：天、远楼

# 河岸那一屏（镜头 y=0）里各层的水线在屏幕上的哪一行；其他房间按镜头高低、各层竖直跟镜头的比例平移
SCROLL = {"sky": 0.0, "far": 0.15, "midfar": 0.35, "mid": 0.65, "main": 1.0, "front": 1.3}
FAR_WL, MIDFAR_WL = 168, 178
FAR_H, FAR_ROW_WL = 330, 208          # far.png：高 330，水线在第 208 行（河岸那屏 y 偏移 -40）
MIDFAR_H, MIDFAR_ROW_WL = 420, 300    # midfar.png：水线在第 300 行（河岸那屏 y 偏移 -122）


def sky():
    """白天的天：上面压着一层石板灰蓝的云，往下到远处水线一带是最亮的日光霾（L≈.6），
    左上太阳那边的云缝透一点亮。几条扁扁的云带横着（硬边，档边窄窄抖一条）。屏幕固定。"""
    cv = Cv(SW, SH)
    Y, X = np.mgrid[0:SH, 0:SW].astype(float)
    # 亮度只跟高度有关（往下到水线最亮）+ 左上太阳一团很淡的亮
    L = np.interp(Y, [0, 40, 90, 130, 160, 172, 200, 270], [0.40, 0.42, 0.47, 0.54, 0.6, 0.61, 0.5, 0.42])
    L += 0.05 * np.exp(-(((X - 96) / 120) ** 2 + ((Y - 30) / 60) ** 2))
    bands = np.zeros_like(L)
    for (cy, cx, hw, th, k) in ((34, 150, 260, 5, -0.03), (52, 330, 210, 3, -0.025), (70, 70, 180, 3.5, -0.02),
                                (96, 380, 240, 2.5, -0.018), (112, 200, 200, 2, 0.015), (124, 430, 150, 1.6, 0.012),
                                (20, 420, 200, 4, -0.03), (142, 110, 260, 1.4, 0.01)):
        for ox in (-SW, 0, SW):
            u = (X - cx - ox) / hw
            half = th * np.sqrt(np.clip(1 - u ** 2, 0, 1))
            bands += np.where(np.abs(Y - cy - 4 * u ** 2) < half, k, 0)
    step = 0.018
    lv = narrow_levels((L + bands) / step)
    for v in np.unique(lv):
        cv.mask(lv == v, haze(min(L_MAX_BG, v * step)))
    return cv


def tower(rng, w, top, bottom, unit, L, c, h, lit_p=0.0, det=1, roof=True):
    """一栋鸽子笼（正侧面）：楼身 w 宽，从 top 到 bottom；unit = (格宽, 层高, 窗宽, 窗高)。
    每层一样：一道楼板线、一排一样的窗；极少几扇窗亮着（琥珀，很暗）。返回 Cv（四周留 0 边，楼顶上方留 14 行放水箱天线）。"""
    cw, fh, ww, wh = unit
    hh = bottom - top
    pad = 14
    cv = Cv(w, hh + pad)
    st = stone(L, c, h, dL=0.03)
    cv.rect(0, pad, w, pad + hh, st[3])
    nx = max(1, (w - 2) // cw)
    x0 = (w - nx * cw) // 2
    lit_win = mix(WARM_WIN, st[3], 0.35)
    for k, yy in enumerate(range(pad + 3, pad + hh, fh)):
        if det >= 1:
            cv.hline(0, w, yy - 1, st[4])                       # 楼板受光的上沿
        if det >= 2:
            cv.hline(0, w, yy, st[2])
        for i in range(nx):
            wx = x0 + i * cw + (cw - ww) // 2
            on = rng.random() < lit_p
            cv.rect(wx, yy + 1, wx + ww, yy + 1 + wh, lit_win if on else GLASS)
            if not on and wh >= 2 and det >= 1:
                cv.hline(wx, wx + ww, yy + 1, mix(GLASS_SKY, st[3], 0.5))
            if det >= 2 and ww >= 3:
                cv.vline(wx + ww // 2, yy + 1, yy + 1 + wh, st[2])
            if det >= 2 and rng.random() < 0.18:                 # 空调外机 / 晾的东西
                cv.rect(wx + ww - 2, yy + wh, wx + ww, yy + wh + 1, st[5])
    cv.vline(0, pad, pad + hh, st[5])                            # 左边受光
    cv.vline(w - 1, pad, pad + hh, st[1])                        # 右边背光
    if roof:
        cv.hline(0, w, pad, st[5])
        cv.hline(-1 + 1, w, pad + 1, st[4])
        r = rng.random()
        if r < 0.45 and w >= 8:                                   # 水箱
            tx = int(rng.integers(1, max(2, w - 6)))
            tw_ = min(w - tx - 1, int(rng.integers(4, 7)))
            th = int(rng.integers(3, 6))
            cv.rect(tx, pad - th, tx + tw_, pad, st[3])
            cv.hline(tx, tx + tw_, pad - th, st[5])
            cv.vline(tx + 1, pad - 1, pad, st[1])
        elif r < 0.8:                                             # 天线、细杆
            ax = int(rng.integers(1, max(2, w - 1)))
            cv.vline(ax, pad - int(rng.integers(5, 13)), pad, st[2])
            if rng.random() < 0.5:
                cv.hline(ax - 2, ax + 3, pad - 6, st[2])
        if rng.random() < 0.4 and w >= 10:                        # 楼梯间小屋
            sx = int(rng.integers(0, w - 6))
            cv.rect(sx, pad - 4, sx + 6, pad, st[4])
            cv.vline(sx + 5, pad - 4, pad, st[2])
    return cv


def clock_tower(L, scale=1):
    """广场淹了，只露出一截钟楼（原文 71）：老石头方塔，钟面浅灰，指针停着。和飞行一窗外那座同一个样子。"""
    w, h = 18 * scale, 120 * scale
    cv = Cv(w + 4, h)
    st = stone(L, 0.014, HUE - 30, dL=0.03)
    s = scale
    cv.rect(4 * s, 26 * s, 14 * s, h, st[3])
    cv.vline(4 * s, 26 * s, h, st[5])
    cv.rect(13 * s, 26 * s, 14 * s, h, st[1])
    for y in range(30 * s, h, 5 * s):
        cv.hline(5 * s, 13 * s, y, st[2])
    cv.rect(3 * s, 14 * s, 15 * s, 26 * s, st[3])               # 钟室
    cv.vline(3 * s, 14 * s, 26 * s, st[5])
    cv.hline(2 * s, 16 * s, 26 * s, st[5])
    cv.hline(2 * s, 16 * s, 13 * s, st[5])
    cv.ellipse(9 * s, 20 * s, 3.6 * s, 3.6 * s, st[5])
    cv.ellipse(9 * s, 20 * s, 2.6 * s, 2.6 * s, st[6])
    cv.vline(9 * s, 18 * s, 20 * s + 1, st[1])
    cv.hline(9 * s, 11 * s, 20 * s, st[1])
    cv.poly([(9 * s, 1 * s), (16 * s, 13 * s), (2 * s, 13 * s)], st[1])     # 尖顶
    cv.poly([(9 * s, 1 * s), (2 * s, 13 * s), (6 * s, 13 * s)], st[3])
    cv.vline(9 * s, 0, 2 * s, st[1])
    for y in range(40 * s, h - 6, 18 * s):                       # 窄窗
        cv.rect(8 * s, y, 10 * s, y + 5 * s, GLASS)
    return cv


def water_band(cv: Cv, y0, y1, seed, L_top=0.56, L_bot=0.36, glint=0.62, refl=None, density=1.0):
    """水面（正侧面看就是一条横带）：贴着水线最亮（映着日光霾），往下越来越暗、越来越青；
    一道道断开的横亮纹（青白），越近越长。refl = 水线以上那几行的图（Cv），倒过来、压暗、断成横条照进水里。"""
    rng = np.random.default_rng(seed)
    hgt = y1 - y0
    for y in range(y0, y1):
        t = (y - y0) / max(1, hgt - 1)
        Lv = L_top + (L_bot - L_top) * min(1, t * 1.6) ** 0.8
        q = round(Lv / 0.02) * 0.02
        cv.hline(0, cv.w, y, C(q, 0.024 + 0.01 * t, H_WATER))
    cv.hline(0, cv.w, y0, C(L_top + 0.04, 0.02, H_GLINT))
    if refl is not None:
        # 倒影：水线上面的东西倒过来，只在暗的地方压一档（楼的影子），亮的不进来
        for d in range(1, min(hgt, 40)):
            ys = y0 - d
            if ys < 0:
                break
            row = refl.a[ys]
            dark = (row[:, 3] > 0)
            if not dark.any():
                continue
            yy = y0 + int(d * 0.8) + 1
            if yy >= y1:
                break
            if d % 3 == 2:
                continue
            brk = (np.arange(cv.w) + int(rng.integers(0, 9))) % (11 + d % 7) < 2
            m = dark & ~brk
            base = cv.a[yy, :, :3].copy()
            lab = srgb_to_oklab(base[m].reshape(-1, 3))
            refl_lab = srgb_to_oklab(row[m, :3].reshape(-1, 3))
            mixed = lab * 0.55 + refl_lab * 0.45
            mixed[:, 0] = np.minimum(mixed[:, 0], lab[:, 0] - 0.03)
            q = np.round(mixed / np.array([0.02, 0.01, 0.01])) * np.array([0.02, 0.01, 0.01])
            cv.a[yy, m, :3] = oklab_to_srgb(q)
    n = int(cv.w * hgt / 26 * density)
    for _ in range(n):
        y = int(y0 + 1 + (rng.random() ** 2.2) * (hgt - 2))
        x = int(rng.integers(0, cv.w))
        t = (y - y0) / max(1, hgt)
        ln = int(rng.integers(3, 8) + 14 * t * rng.random())
        Lg = glint - 0.14 * t - 0.04 * rng.random()
        cv.hline(x, x + ln, y, C(Lg, 0.03, H_GLINT))


def far():
    """远楼（scroll .15）：一排灰色鸽子笼，高高低低，看得到楼顶（水箱、天线）；楼顶之间一条条细桥（原文 71）；
    下半截泡在水里，水线一带是整张图最亮的日光霾，水里一道道青白的亮纹；左边一截钟楼（原文 71）、几根废弃的架空线。"""
    cv = Cv(TW, FAR_H, wrap=True)
    rng = np.random.default_rng(1101)
    blds = []
    x = 0
    while x < TW - 6:
        w = int(rng.integers(14, 34))
        if TW - x - w < 14:
            w = TW - x
        top = int(rng.integers(70, 160))
        L = 0.40 + rng.random() * 0.05
        t = tower(rng, w, top, FAR_ROW_WL + 2, (3, 4, 1, 2), L, 0.012, HUE + rng.integers(-6, 6), lit_p=0.004)
        cv.paste(t, x, top - 14)
        blds.append((x, top, w))
        x += w + int(rng.integers(0, 4))
    # 楼顶之间的细桥：一道桥面 + 一行稀疏的栏杆柱，搭在两栋楼相邻的楼顶 / 上层之间
    bst = stone(0.43, 0.012, HUE)
    for (xa, ta, wa), (xb, tb, wb) in zip(blds, blds[1:] + [(blds[0][0] + TW, blds[0][1], blds[0][2])]):
        if rng.random() < 0.55:
            yb = max(ta, tb) + int(rng.integers(2, 12))
            cv.hline(xa + wa - 1, xb + 1, yb, bst[2])
            cv.hline(xa + wa - 1, xb + 1, yb - 1, bst[4])
            for px in range(xa + wa + 1, xb, 3):
                cv.px(px, yb - 2, bst[3])
    # 钟楼：广场淹了只露一截（在河岸第一屏的左边，和飞行一窗外的钟楼对上）
    ct = clock_tower(0.44)
    cv.paste(ct, 70, FAR_ROW_WL - 96)
    fog(cv, lambda y: float(np.clip((y - 60) / 150, 0, 1)) * 0.5 + 0.25, lambda y: haze(0.58), steps=8)
    # 废弃的架空线：两根老电线杆之间垂下来的线（原文 71：机翼擦过废弃的架空线）
    pole = C(0.36, 0.01, HUE)
    for px0 in (40, 300, 610, 820):
        cv.vline(px0, FAR_ROW_WL - 70, FAR_ROW_WL, pole)
        cv.hline(px0 - 3, px0 + 4, FAR_ROW_WL - 68, pole)
    for xa, xb in ((40, 300), (300, 610), (610, 820), (820, 1000)):
        n = xb - xa
        pts = [(xa + i, FAR_ROW_WL - 68 + 14 * math.sin(math.pi * i / n)) for i in range(0, n + 1, 4)]
        cv.line(pts, C(0.34, 0.01, HUE))
    water_band(cv, FAR_ROW_WL, FAR_H, 1102, L_top=0.60, L_bot=0.44, glint=0.64, refl=cv, density=0.3)
    return cv


def midfar():
    """中远（scroll .35）：同一种鸽子笼放大、暗一档，窗格看得清；楼顶上细桥更清楚（桥面 + 栏杆 + 吊着的绳），
    一两根晾衣绳；下半截泡水，水线上一道长苔的旧水位印子。"""
    cv = Cv(TW, MIDFAR_H, wrap=True)
    rng = np.random.default_rng(1201)
    blds = []
    x = 6
    while x < TW - 10:
        w = int(rng.integers(30, 58))
        if TW - x - w < 26:
            w = TW - x - 2
        top = int(rng.integers(120, 230))
        L = 0.31 + rng.random() * 0.03
        t = tower(rng, w, top, MIDFAR_ROW_WL + 3, (5, 7, 3, 3), L, 0.013, HUE + rng.integers(-5, 5), lit_p=0.004, det=2)
        cv.paste(t, x, top - 14)
        blds.append((x, top, w))
        x += w + int(rng.integers(2, 9))
    bst = stone(0.38, 0.013, HUE)
    for (xa, ta, wa), (xb, tb, wb) in zip(blds, blds[1:] + [(blds[0][0] + TW, blds[0][1], blds[0][2])]):
        if rng.random() < 0.6:
            yb = max(ta, tb) + int(rng.integers(3, 20))
            cv.rect(xa + wa - 1, yb, xb + 1, yb + 2, bst[2])
            cv.hline(xa + wa - 1, xb + 1, yb, bst[4])
            cv.hline(xa + wa - 1, xb + 1, yb - 4, bst[3])
            for px in range(xa + wa + 1, xb, 4):
                cv.vline(px, yb - 4, yb, bst[3])
    # 旧水位印子：水线上面一道暗的苔痕（新旧水位交界）
    for (xa, ta, wa) in blds:
        y = MIDFAR_ROW_WL - 6 - int(rng.integers(0, 3))
        cv.rect(xa, y, xa + wa, MIDFAR_ROW_WL, C(0.26, 0.014, H_MOSS + 50))
    fog(cv, lambda y: float(np.clip((y - 150) / 160, 0, 1)) * 0.35 + 0.04, lambda y: haze(0.55), steps=8)
    water_band(cv, MIDFAR_ROW_WL, MIDFAR_H, 1202, L_top=0.53, L_bot=0.32, glint=0.6, refl=cv, density=0.25)
    return cv


# ============================================================ 部件（正侧面：只有立面，没有往里收的面）

def course_wall(cv: Cv, x0, x1, y0, y1, st, rng, course=6, block=(10, 22), lit_top=True, stain=0.15):
    """石砌的立面：一行行条石（行高 course），竖缝错开；每块石头明暗差一档；上沿一道受光，下面每行一道暗缝。"""
    cv.rect(x0, y0, x1, y1, st[3])
    row = 0
    for y in range(y0, y1, course):
        x = x0 - (int(rng.integers(0, block[1])) if row % 2 else 0)
        while x < x1:
            bw = int(rng.integers(*block))
            k = 3 + int(rng.choice([-1, 0, 0, 0, 1]))
            cv.rect(max(x0, x), y, min(x1, x + bw), min(y1, y + course), st[k])
            if x > x0:
                cv.vline(x, y, min(y1, y + course), st[1])
            x += bw
        cv.hline(x0, x1, y, st[2])
        row += 1
    if lit_top:
        cv.hline(x0, x1, y0, st[5])
        cv.hline(x0, x1, y0 + 1, st[4])
    # 往下拖的水渍
    for _ in range(int((x1 - x0) * stain)):
        sx = int(rng.integers(x0, x1))
        sy = int(rng.integers(y0 + 2, max(y0 + 3, y1 - 4)))
        cv.vline(sx, sy, min(y1, sy + int(rng.integers(3, 12))), st[1])


def moss_line(cv: Cv, x0, x1, y, rng, depth=3, L=0.22, seed=0):
    """水线（新、旧水位）上的一道苔：暗、灰绿，下沿参差。"""
    n = pnoise(max(8, x1 - x0), 900 + seed, 2, 12)
    for i, x in enumerate(range(x0, x1)):
        d = depth + int(round(n[i] * depth * 0.7))
        cv.vline(x, y - d, y + 1, C(L, 0.02, H_MOSS + 30))
        if d > 1 and (x * 7 + seed) % 5 == 0:
            cv.px(x, y - d, C(L + 0.04, 0.02, H_MOSS + 30))


def window(cv: Cv, x, y, w, h, st, rng, kind="sash", lit=False, warm=False):
    """一扇窗（正侧面）：窗洞、上沿一道天光、窗框十字、窗台一道受光；kind: sash / shutter / small / arched。"""
    glass = WARM_WIN if warm else GLASS
    cv.rect(x, y, x + w, y + h, glass)
    if not warm:
        r = rng.random()
        if r < 0.45:                                                      # 玻璃上半截映着天（白天）
            cv.rect(x, y, x + w, y + max(1, h * 2 // 5), mix(GLASS_SKY, glass, 0.25))
            cv.hline(x, x + w, y, GLASS_SKY)
        elif r < 0.75:                                                    # 拉了一半的帘子
            cv.rect(x, y, x + w, y + int(h * rng.uniform(0.3, 0.6)), C(0.25, 0.014, HUE - 24))
            cv.hline(x, x + w, y, GLASS_SKY)
        else:
            cv.hline(x, x + w, y, GLASS_SKY)
    if kind == "arched":
        cv.px(x, y, st[3])
        cv.px(x + w - 1, y, st[3])
    if w >= 5:
        cv.vline(x + w // 2, y, y + h, st[2])
    if h >= 8:
        cv.hline(x, x + w, y + h // 3, st[2])
    cv.hline(x - 1, x + w + 1, y + h, st[5])                              # 窗台
    cv.hline(x - 1, x + w + 1, y + h + 1, st[1])
    if kind == "shutter":
        cv.rect(x - 3, y, x - 1, y + h, st[2])
        cv.rect(x + w + 1, y, x + w + 3, y + h, st[2])
        for yy in range(y + 1, y + h, 2):
            cv.hline(x - 3, x - 1, yy, st[1])
            cv.hline(x + w + 1, x + w + 3, yy, st[1])


def house(rng, w, hgt, L, h=HUE, c=0.014, floor_h=20, win=(7, 10), kind="block", flood_y=None, roof=True):
    """背景里的水城老楼（正侧面，比远处的鸽子笼近、格子大）：一层一层同样的窗、窗台、阳台、落水管、空调、晾的东西；
    flood_y = 旧水位那道苔痕（楼身坐标）。返回 Cv（楼顶上方留 16 行放水箱、天线）。"""
    pad = 16
    cv = Cv(w, hgt + pad)
    st = stone(L, c, h)
    cv.rect(0, pad, w, pad + hgt, st[3])
    ww, wh = win
    cell = ww + 7
    nx = max(1, (w - 6) // cell)
    x0 = (w - nx * cell) // 2 + 3
    kinds = ["sash", "shutter", "small"]
    k_win = kinds[int(rng.integers(0, 3))] if kind != "block" else "sash"
    for fi, fy in enumerate(range(pad + 6, pad + hgt - floor_h // 2, floor_h)):
        cv.hline(0, w, fy - 3, st[4])                                     # 楼板线
        cv.hline(0, w, fy - 2, st[2])
        for i in range(nx):
            wx = x0 + i * cell
            if rng.random() < 0.06:
                continue                                                  # 砌死的一格
            window(cv, wx, fy, ww, wh, st, rng, kind=k_win, warm=rng.random() < 0.012)
        if kind == "block" and fi % 2 == 1 and rng.random() < 0.6:        # 一排阳台栏板
            by = fy + wh - 3
            cv.rect(2, by, w - 2, by + 4, st[4])
            cv.hline(2, w - 2, by, st[5])
            for px in range(4, w - 3, 3):
                cv.vline(px, by + 1, by + 4, st[3])
    # 落水管
    px = int(rng.integers(2, w - 3))
    cv.rect(px, pad, px + 2, pad + hgt, st[2])
    cv.vline(px, pad, pad + hgt, st[4])
    for yy in range(pad + 10, pad + hgt, 24):
        cv.hline(px - 1, px + 3, yy, st[1])
    # 水渍
    for _ in range(w * hgt // 400):
        sx, sy = int(rng.integers(1, w - 1)), int(rng.integers(pad, pad + hgt - 4))
        cv.vline(sx, sy, min(pad + hgt, sy + int(rng.integers(3, 14))), st[2])
    cv.vline(0, pad, pad + hgt, st[5])
    cv.vline(w - 1, pad, pad + hgt, st[1])
    if flood_y is not None:
        # 旧水位以下：墙更暗一档、偏一点苔色（泡过水）
        m = np.zeros((cv.h, cv.w), bool)
        m[pad + flood_y + 1:] = True
        shade_mask(cv, m, -0.035, 0.004, 30)
        moss_line(cv, 0, w, pad + flood_y, rng, depth=2, L=L - 0.06, seed=w)
    if roof:
        cv.hline(0, w, pad, st[5])
        cv.rect(0, pad + 1, w, pad + 3, st[4])
        cv.hline(0, w, pad + 3, st[1])
        r = rng.random()
        if r < 0.5:
            tx = int(rng.integers(2, max(3, w - 10)))
            cv.rect(tx, pad - 7, tx + 8, pad, st[3])
            cv.hline(tx, tx + 8, pad - 7, st[5])
            cv.vline(tx + 7, pad - 7, pad, st[1])
            cv.vline(tx + 2, pad - 10, pad - 7, st[2])
        else:
            ax = int(rng.integers(2, w - 2))
            cv.vline(ax, pad - 15, pad, st[2])
            cv.hline(ax - 3, ax + 4, pad - 11, st[2])
            cv.hline(ax - 2, ax + 3, pad - 8, st[2])
    return cv


def laundry(cv: Cv, x0, x1, y, rng, sag=3, kind="paper", density=0.5):
    """两点之间一根晾绳（下垂），上面夹着晾的东西：paper = 湿纸 / 标签（旧白、个别琥珀），cloth = 布。"""
    n = x1 - x0
    rope = C(0.30, 0.01, HUE)
    ys = []
    for i in range(n + 1):
        yy = y + int(round(sag * math.sin(math.pi * i / max(1, n))))
        ys.append(yy)
        cv.px(x0 + i, yy, rope)
    i = 2
    while i < n - 3:
        if rng.random() < density:
            yy = ys[i] + 1
            if kind == "paper":
                pw, ph = int(rng.integers(3, 6)), int(rng.integers(4, 7))
                col = AMBER if rng.random() < 0.12 else mix(PAPER, C(0.4, 0.01, HUE), 0.45)
                cv.rect(x0 + i, yy, x0 + i + pw, yy + ph, col)
                cv.hline(x0 + i, x0 + i + pw, yy + ph - 1, mix(col, C(0.3, 0.01, HUE), 0.4))
                cv.px(x0 + i + pw // 2, yy - 1, C(0.36, 0.01, HUE))       # 夹子
                i += pw + 1
            else:
                pw, ph = int(rng.integers(5, 10)), int(rng.integers(6, 12))
                col = C(rng.uniform(0.28, 0.36), 0.016, rng.choice([HUE, HUE - 30, 60]))
                cv.rect(x0 + i, yy, x0 + i + pw, yy + ph, col)
                cv.vline(x0 + i + pw - 1, yy, yy + ph, mix(col, C(0.2, 0.01, HUE), 0.5))
                i += pw + 1
        i += int(rng.integers(1, 4))


def railing(cv: Cv, x0, x1, y_top, y_base, col_lit, col, step=5):
    """细栏杆：一道扶手（上沿受光）+ 一排竖杆。"""
    cv.hline(x0, x1, y_top, col_lit)
    cv.hline(x0, x1, y_top + 1, col)
    for x in range(x0, x1, step):
        cv.vline(x, y_top + 2, y_base, col)


def post(cv: Cv, x, y_top, y_bot, w, st, rng, rope=False):
    """木桩：顶上一圈受光，往下越来越暗；水线附近一圈苔、几颗藤壶；可以缠一圈绳子。"""
    cv.rect(x, y_top, x + w, y_bot, st[3])
    cv.vline(x, y_top, y_bot, st[5])
    cv.vline(x + w - 1, y_top, y_bot, st[1])
    cv.hline(x, x + w, y_top, st[6])
    for yy in range(y_top + 3, y_bot, 7):                                 # 木纹的裂
        if rng.random() < 0.6:
            cv.vline(x + 1 + int(rng.integers(0, max(1, w - 2))), yy, yy + 3, st[2])
    if rope:
        rc = C(0.42, 0.03, 70)
        for yy in (y_top + 5, y_top + 7):
            cv.hline(x - 1, x + w + 1, yy, rc)
        cv.px(x + w, y_top + 9, rc)
        cv.px(x + w + 1, y_top + 10, rc)


def hood_figure(cv: Cv, x, foot_y, hgt, col, rim):
    """很小的兜帽人剪影（静的：背景里站着、靠着栏杆的）。"""
    w = max(3, hgt // 3)
    cv.poly([(x, foot_y - hgt + 2), (x + w // 2, foot_y - hgt), (x + w, foot_y - hgt + 3),
             (x + w + 1, foot_y), (x - 1, foot_y)], col)
    cv.px(x + w // 2, foot_y - hgt, rim)
    cv.vline(x, foot_y - hgt + 3, foot_y - hgt // 2, rim)


# ============================================================ 水下（正侧面剖开的水）

def underwater_tint(cv: Cv, y0, y1, L_surf=0.34, L_deep=0.13, t0=0.35, t1=0.8):
    """水面以下：每个像素往「那一深度的水色」推，越深推得越多（分档硬边）。"""
    def t_of(y):
        if y < y0:
            return 0.0
        u = (y - y0) / max(1, y1 - y0)
        return t0 + (t1 - t0) * u

    def col_of(y):
        u = float(np.clip((y - y0) / max(1, y1 - y0), 0, 1))
        return C(L_surf + (L_deep - L_surf) * u, 0.03 + 0.008 * u, H_WATER + 6 * u)
    m = cv.a[..., 3] > 0
    m[:y0] = False
    fog(cv, t_of, col_of, steps=12, m=m)


def caustics(cv: Cv, x0, x1, y0, y1, rng, n=40, L_add=0.08):
    """水下的光斑（静的一层，引擎另有焦散 shader 可以叠）：一块块不规则的亮网，只亮一档，偏青。"""
    for _ in range(n):
        cx, cy = int(rng.integers(x0, x1)), int(rng.integers(y0, y1))
        w, hh = int(rng.integers(4, 12)), int(rng.integers(1, 3))
        m = np.zeros((cv.h, cv.w), bool)
        m[max(0, cy):min(cv.h, cy + hh), max(0, cx):min(cv.w, cx + w)] = True
        shade_mask(cv, m, L_add, 0.01, -8)


def fish(cv: Cv, x, y, col, d=1):
    """窗框间穿过的小鱼（原文 80）：4~5 像素一条，朝 d 方向。"""
    pts = [(0, 0), (1, 0), (2, 0), (3, 0), (1, -1), (2, -1), (-1, -1), (-1, 1)]
    for px_, py in pts:
        cv.px(x + px_ * d, y + py, col)


# ============================================================ 房间：图层 + 物件 + room.json + 预览

CHEN_SHEET = ROOT / "art" / "characters" / "chen" / "chen_oscar.png"
CHEN_FRAME, CHEN_FOOT = (68, 60), (28, 56)


class Room:
    def __init__(self, rid, w, env="river_day"):
        self.id, self.w, self.env = rid, w, env
        self.layers = []          # (spec dict, Cv 或 None=共用图)
        self.objects = {}         # id -> (spec, [Cv 帧])
        self.markers = {}
        self.extra = {}
        self.ground = None

    def need_w(self, scroll):
        return int(math.ceil(SW + (self.w - SW) * scroll - 1e-9))

    def layer(self, lid, cv, scroll, y=0, **kw):
        spec = {"id": lid, "img": f"{lid}.png", "scroll": scroll, "y": y, **kw}
        if cv is not None and not kw.get("tile"):
            assert cv.w >= self.need_w(scroll), (self.id, lid, cv.w, self.need_w(scroll))
        self.layers.append((spec, cv))
        return spec

    def shared(self, lid, scroll, y, **kw):
        """共用图（art/river_city/common/）：路径相对本房间的 json。"""
        spec = {"id": lid, "img": f"res://art/river_city/common/{lid}.png", "scroll": scroll, "y": y, "tile": True, **kw}
        self.layers.append((spec, None))
        return spec

    def obj(self, oid, frames, x, y, states=None, **kw):
        w, h = frames[0].w, frames[0].h
        spec = {"x": int(x), "y": int(y), "w": w, "h": h, "frames": len(frames), **kw}
        if states:
            spec["states"] = states
        self.objects[oid] = (spec, frames)

    def ground_at(self, x):
        g = self.ground
        if isinstance(g, (int, float)):
            return int(g)
        xs, ys = zip(*g)
        return int(round(np.interp(x, xs, ys)))

    def json(self):
        d = {"_note": "tools/river_city_art.py 生成，别手改。约定见 docs/river_rooms_contract.md。",
             "size": [self.w, SH], "env": self.env, "bg": ["#1b2228", "#3a4752"],
             "layers": [s for s, _ in self.layers], "ground": self.ground,
             "markers": self.markers, "objects": {k: s for k, (s, _) in self.objects.items()}}
        d.update(self.extra)
        return d

    def write(self):
        d = OUT / self.id
        d.mkdir(parents=True, exist_ok=True)
        for s, cv in self.layers:
            if cv is not None:
                check_alpha(cv.a, f"{self.id}/{s['id']}")
                cv.save(d / s["img"])
        for oid, (s, frames) in self.objects.items():
            strip = Cv(s["w"] * len(frames), s["h"])
            for i, f in enumerate(frames):
                strip.paste(f, i * s["w"], 0)
            check_alpha(strip.a, f"{self.id}/{oid}")
            strip.save(d / s.get("img", f"{oid}.png"))
        (d / "room.json").write_text(json.dumps(self.json(), ensure_ascii=False, indent=1))


def check_alpha(a, name):
    al = a[..., 3]
    assert ((al == 0) | (al == 255)).all(), f"{name}: 有半透明像素"


_SHARED = {}


def shared_img(lid):
    if lid not in _SHARED:
        _SHARED[lid] = {"sky": sky, "far": far, "midfar": midfar}[lid]()
    return _SHARED[lid]


def chen_img(frame=7):
    a = np.array(Image.open(CHEN_SHEET).convert("RGBA"))
    fw = CHEN_FRAME[0]
    return a[:, frame * fw:(frame + 1) * fw]


def render(room: Room, cam_x, states=None, chen_x=None, extra=(), water_dy=0):
    """按约定模拟引擎画一屏：层（scroll、y、tile、alpha、z）+ 物件 + 晨（站在 chen_x 的地面上）。"""
    states = states or {}
    cam_x = int(np.clip(cam_x, 0, max(0, room.w - SW)))
    im = np.zeros((SH, SW, 3), float)
    top, bot = np.array(Image.new("RGB", (1, 1), "#1b2228"))[0, 0], np.array(Image.new("RGB", (1, 1), "#3a4752"))[0, 0]
    im[:] = (top[None, None] * (1 - np.linspace(0, 1, SH)[:, None, None]) + bot[None, None] * np.linspace(0, 1, SH)[:, None, None])
    items = []
    for i, (s, cv) in enumerate(room.layers):
        z = s.get("z", 100 + i if s.get("front") else -100 + i)
        items.append((z, "layer", s, cv))
    for oid, (s, frames) in room.objects.items():
        st = states.get(oid, s.get("default", "default"))
        if st in ("hidden", "gone", "taken") or ("on" in s and not _on(s["on"], states)):
            continue
        fi = 0
        if "states" in s and st in s["states"]:
            v = s["states"][st]
            fi = v[0] if isinstance(v, list) else v
        z = s.get("z", 100 if s.get("front") else -1)
        items.append((z, "obj", s, frames[fi]))
    if chen_x is not None:
        items.append((0, "chen", chen_x, None))
    for e in extra:
        items.append(e)
    for z, kind, s, cv in sorted(items, key=lambda t: t[0]):
        if kind == "layer":
            a = (cv if cv is not None else shared_img(s["id"])).a
            y = s["y"] + (water_dy if s.get("water") else 0)
            sx = int(round(cam_x * s["scroll"])) - s.get("x", 0)
            if s.get("tile"):
                sx %= a.shape[1]
                a2 = np.concatenate([a, a, a], axis=1)[:, sx:sx + SW]
            else:
                a2 = a[:, sx:sx + SW]
            _blit(im, a2, 0, y, s.get("alpha", 1.0))
        elif kind == "obj":
            _blit(im, cv.a, s["x"] - cam_x, s["y"], 1.0)
        elif kind == "chen":
            fr = chen_img()
            gy = room.ground_at(s)
            _blit(im, fr, int(s) - cam_x - CHEN_FOOT[0], gy - CHEN_FOOT[1], 1.0)
        else:
            _blit(im, cv, s[0] - cam_x, s[1], 1.0)
    return im.round().astype(np.uint8)


def _on(cond, states):
    k, v = cond.split("=")
    return states.get(k) == v


def _blit(im, a, x, y, alpha):
    h, w = a.shape[:2]
    y0, y1 = max(0, y), min(SH, y + h)
    x0, x1 = max(0, x), min(SW, x + w)
    if y0 >= y1 or x0 >= x1:
        return
    s = a[y0 - y:y1 - y, x0 - x:x1 - x]
    m = (s[..., 3] > 0)[..., None] * alpha
    im[y0:y1, x0:x1] = im[y0:y1, x0:x1] * (1 - m) + s[..., :3] * m


# ============================================================ 河岸 river_bank

BANK_W = 1440
B_G, B_WL, B_BACK_WL, B_GAL = 206, 218, 196, 118      # 晨的地面、前面的水面、后排楼脚的水面、高处街道（廊道面）
B_HOUSE = (680, 1100)                                  # 妮芙家（D 画的剖面小屋，420 宽）占的那一段


def bank_ground():
    return [[0, 214], [110, 214], [150, 212], [330, B_G], [570, B_G], [582, 209], [595, 212], [608, 215],
            [660, 215], [673, 212], [686, 209], [700, B_G], [1100, B_G], [1160, 213], [1300, 213], [1312, B_G],
            [BANK_W, B_G]]


def mid_strip(rid, w, seed, wl, L=0.3, top_rng=(30, 110)):
    """中景（scroll .6）：一排近一点的泡水楼（house），比远楼大、暗；楼脚在 wl 进水，水里一道倒影。"""
    cv = Cv(w, SH)
    rng = np.random.default_rng(seed)
    x = -int(rng.integers(0, 20))
    while x < w:
        bw = int(rng.integers(44, 86))
        top = int(rng.integers(*top_rng))
        hgt = wl + 2 - top
        hcv = house(rng, bw, hgt, L + rng.uniform(-0.02, 0.02), HUE + rng.integers(-6, 6), win=(5, 7), floor_h=14,
                    kind="block" if rng.random() < 0.6 else "old", flood_y=hgt - 22 - int(rng.integers(0, 8)))
        cv.paste(hcv, x, top - 16)
        x += bw + int(rng.integers(4, 22))
    fog(cv, lambda y: 0.18 + 0.2 * float(np.clip((y - 60) / 120, 0, 1)), lambda y: haze(0.52), steps=8)
    water_band(cv, wl, SH, seed + 1, L_top=0.5, L_bot=0.3, glint=0.58, refl=cv, density=0.25)
    return cv


def bank_main(rng):
    """河岸主层（scroll 1）：后排泡水的楼 + 高处街道（廊道），前面晨走的岸；水面以下剖开画（旧街、旧门、街砖）。"""
    W = BANK_W
    cv = Cv(W, SH)
    # ---- 后排楼：楼脚在 B_BACK_WL 进水；左边那两栋就是飞机卡进去的那条窄水道的墙（和飞行一最后一格同一面墙）
    spans = [(0, 168, -4, 0.25, "block"), (168, 330, 26, 0.26, "block"), (372, 522, 62, 0.28, "old"),
             (560, 700, 54, 0.27, "old"), (700, 1100, 40, 0.26, "block"), (1100, 1172, 74, 0.29, "old"),
             (1200, 1300, 84, 0.28, "old"), (1300, 1440, 30, 0.26, "block")]
    for (x0, x1, top, L, kind) in spans:
        base = 258 if x0 < 330 else B_BACK_WL + 4
        hgt = base - top
        hcv = house(rng, x1 - x0, hgt, L, HUE + int(rng.integers(-4, 5)), win=(7, 10) if kind == "block" else (6, 11),
                    floor_h=20, kind=kind, flood_y=(B_WL - 6 - top) if x0 < 330 else (152 - top))
        cv.paste(hcv, x0, top - 16)
    # 后排楼脚的水（晨背后一窄条，映着楼）
    wb = Cv(W, SH)
    water_band(wb, B_BACK_WL, B_G + 2, 2101, L_top=0.36, L_bot=0.28, glint=0.5, refl=cv, density=0.4)
    cv.paste(Cv_slice(wb, 330, W, B_BACK_WL, B_G + 2), 330, B_BACK_WL)

    # ---- 高处街道（原文 80「高处是仍有人来往的街道」）：沿后排楼的一条廊道，下面三角托架
    gst = stone(0.36, 0.012, HUE - 14)
    cv.rect(372, B_GAL, 1300, B_GAL + 4, gst[3])
    cv.hline(372, 1300, B_GAL, gst[5])
    cv.hline(372, 1300, B_GAL + 4, gst[1])
    for bx in range(380, 1300, 26):
        cv.poly([(bx, B_GAL + 4), (bx + 8, B_GAL + 4), (bx + 1, B_GAL + 12)], gst[2])
        cv.vline(bx, B_GAL + 4, B_GAL + 12, gst[4])
    cv.rect(522, B_GAL, 560, B_GAL + 4, gst[3])                      # 两栋楼之间的那段廊道搭在空里
    # 店面：廊道这一层每栋楼开一排门，门边各有一个小标记（原文 103 写市集，这里只放几扇门）
    for dx in (390, 450, 600, 640, 1110, 1220, 1260):
        cv.rect(dx, B_GAL - 16, dx + 8, B_GAL, GLASS)
        cv.hline(dx - 1, dx + 9, B_GAL - 17, gst[5])
        cv.px(dx + 9, B_GAL - 10, mix(PAPER, gst[3], 0.5))
    # ---- 面包店（原文 80）：伸出一块木板，搭到对面的修补摊；店里暖光，门上一块小招牌（一只面包的剪影）
    wood = stone(0.33, 0.03, 60)
    bk = (1104, 1170)
    cv.rect(bk[0] + 6, B_GAL - 22, bk[0] + 30, B_GAL, C(0.42, 0.06, H_WARM))        # 暖光的橱窗
    cv.rect(bk[0] + 8, B_GAL - 20, bk[0] + 28, B_GAL - 8, C(0.5, 0.075, H_WARM))
    for i, sx in enumerate(range(bk[0] + 9, bk[0] + 28, 4)):                         # 架子上的面包
        cv.rect(sx, B_GAL - 11, sx + 3, B_GAL - 9, C(0.58, 0.08, H_WARM - 6))
    cv.hline(bk[0] + 8, bk[0] + 28, B_GAL - 8, C(0.36, 0.04, H_WARM))
    cv.rect(bk[0] + 34, B_GAL - 16, bk[0] + 42, B_GAL, GLASS)                         # 门
    for i, ax in enumerate(range(bk[0] + 2, bk[0] + 46)):                             # 遮阳篷（条纹，褪色）
        cv.vline(ax, B_GAL - 28 + (1 if ax % 2 else 0), B_GAL - 24, wood[4] if (ax // 3) % 2 else C(0.36, 0.02, HUE))
    cv.hline(bk[0] + 1, bk[0] + 47, B_GAL - 29, wood[5])
    cv.rect(bk[0] + 48, B_GAL - 26, bk[0] + 60, B_GAL - 19, wood[3])                  # 招牌
    cv.rect(bk[0] + 50, B_GAL - 24, bk[0] + 58, B_GAL - 21, C(0.55, 0.07, H_WARM - 4))
    cv.vline(bk[0] + 54, B_GAL - 29, B_GAL - 26, wood[2])
    # 木板：从面包店伸出去，跨过两栋楼之间的水缝，搭到修补摊
    cv.rect(1166, B_GAL - 1, 1206, B_GAL + 2, wood[3])
    cv.hline(1166, 1206, B_GAL - 1, wood[5])
    cv.hline(1166, 1206, B_GAL + 2, wood[1])
    for px_ in (1172, 1186, 1199):
        cv.vline(px_, B_GAL - 1, B_GAL + 2, wood[2])
    # 修补摊：一个小棚子，工具挂了一排（扳手、钳子、卷尺、线团）
    rp = (1204, 1262)
    cv.rect(rp[0], B_GAL - 30, rp[1], B_GAL - 27, wood[4])
    cv.hline(rp[0], rp[1], B_GAL - 30, wood[5])
    cv.vline(rp[0] + 1, B_GAL - 27, B_GAL, wood[2])
    cv.vline(rp[1] - 2, B_GAL - 27, B_GAL, wood[2])
    cv.rect(rp[0] + 2, B_GAL - 8, rp[1] - 2, B_GAL, wood[3])                          # 台面
    cv.hline(rp[0] + 2, rp[1] - 2, B_GAL - 8, wood[5])
    met = stone(0.4, 0.012, HUE - 20)
    for i, tx in enumerate(range(rp[0] + 6, rp[1] - 6, 5)):
        ln = 6 + (i * 3) % 5
        cv.vline(tx, B_GAL - 26, B_GAL - 26 + ln, met[3])
        cv.px(tx - 1, B_GAL - 26 + ln, met[4])
        cv.px(tx + 1, B_GAL - 26 + ln, met[4])
    cv.rect(rp[0] + 10, B_GAL - 12, rp[0] + 16, B_GAL - 8, met[2])                   # 台上的零件盒
    cv.rect(rp[0] + 30, B_GAL - 11, rp[0] + 34, B_GAL - 8, C(0.45, 0.05, H_WARM))
    # ---- 屋顶的窄桥（原文 80「邮差从屋顶的窄桥走过，袋子碰得栏杆轻轻响」）：两栋楼的楼顶之间
    rb_y = 68
    cv.rect(518, rb_y, 564, rb_y + 2, gst[3])
    cv.hline(518, 564, rb_y, gst[5])
    railing(cv, 518, 564, rb_y - 7, rb_y, gst[4], gst[2], step=4)
    for sx in (530, 552):
        cv.line([(sx, rb_y + 2), (sx - 4 if sx < 540 else sx + 4, rb_y + 9)], gst[2])
    # ---- 小船（原文 83「仍然会划船」、146 告别画里的「小船」）：系在浅滩边后排水里，一根绳拴在矮桩上
    boat = stone(0.31, 0.03, 58)
    bx0, bx1, by = 1206, 1250, B_BACK_WL + 3
    cv.poly([(bx0, by - 4), (bx1, by - 4), (bx1 - 5, by + 1), (bx0 + 4, by + 1)], boat[3])
    cv.hline(bx0, bx1, by - 4, boat[5])
    cv.hline(bx0 + 1, bx1 - 1, by - 3, boat[4])
    cv.rect(bx0 + 14, by - 6, bx0 + 17, by - 4, boat[2])                  # 坐板
    cv.rect(bx0 + 28, by - 6, bx0 + 31, by - 4, boat[2])
    cv.line([(bx0 + 20, by - 4), (bx0 + 34, by - 12)], boat[2])          # 一支桨搭在船舷上
    cv.px(bx1 - 3, by - 6, C(0.5, 0.06, H_WARM))                          # 船头一个空挂钩（铃原来挂在这，原文 143）
    cv.rect(1188, by - 12, 1192, by + 1, boat[2])
    cv.hline(1188, 1192, by - 12, boat[5])
    cv.line([(1192, by - 9), (bx0, by - 4)], C(0.38, 0.03, 70))
    # ---- 晾的东西（原文 79、91、119：一直在晾）：后排楼之间几根绳子
    laundry(cv, 380, 440, 72, rng, sag=3, kind="cloth", density=0.5)
    laundry(cv, 600, 690, 96, rng, sag=4, kind="cloth", density=0.45)
    laundry(cv, 1210, 1290, 60, rng, sag=3, kind="cloth", density=0.5)

    # ---- 窄水道（x 0–330）：后墙一直下到水里，墙脚一圈苔；水道右边一片卵石浅滩（飞机被拖上来的地方）
    shoal = stone(0.30, 0.016, 70)
    for x in range(110, 340):
        gy = int(round(np.interp(x, [110, 150, 330, 340], [214, 212, B_G, B_G])))
        cv.vline(x, gy, B_WL + 6, shoal[3])
        cv.px(x, gy, shoal[5])
    for _ in range(140):                                              # 卵石
        x = int(rng.integers(115, 335))
        gy = int(round(np.interp(x, [110, 150, 330], [214, 212, B_G])))
        y = int(rng.integers(gy + 1, B_WL + 4))
        k = int(rng.integers(2, 5))
        cv.rect(x, y, x + int(rng.integers(2, 4)), y + 1 + (rng.random() < 0.4), shoal[k])
    # ---- 石岸（x 330–570）：条石砌的岸墙，上沿一道受光；水线一圈苔；铁环
    qst = stone(0.30, 0.012, HUE - 24)
    course_wall(cv, 330, 570, B_G, SH, qst, rng, course=6, block=(12, 26))
    moss_line(cv, 330, 570, B_WL, rng, depth=3, seed=1)
    cv.rect(452, B_G + 5, 456, B_G + 9, qst[1])
    cv.rect(453, B_G + 6, 455, B_G + 8, qst[3])
    # ---- 台阶（x 570–700）：往下到贴着水的一块平台，再上来（原文 75「杯子要碰台阶啦」）
    steps = [(570, 582, B_G), (582, 595, 209), (595, 608, 212), (608, 660, 215), (660, 673, 212), (673, 686, 209),
             (686, 700, B_G)]
    for (x0, x1, y) in steps:
        course_wall(cv, x0, x1, y, SH, qst, rng, course=6, block=(10, 16), stain=0.05)
        cv.hline(x0, x1, y, qst[6] if y == 215 else qst[5])
        cv.vline(x1 - 1, y, y + 3, qst[1]) if y < 215 and x1 <= 608 else None
    cv.hline(608, 660, 216, C(0.36, 0.024, H_WATER))                  # 最下面那级是湿的
    moss_line(cv, 570, 700, B_WL, rng, depth=2, seed=2)
    # ---- 木栈道（x 700–1100，妮芙家门口）：板子 + 一排桩；栈道下面是水，水下是她家泡着的旧一层
    deck = stone(0.30, 0.02, 64)
    # 旧一层：墙从栈道下面一直到街砖，窗框间有小鱼；旧门 + 旧门牌（原文 80）
    old = stone(0.27, 0.014, HUE - 16)
    course_wall(cv, 700, 1100, B_G + 4, 258, old, rng, course=7, block=(14, 30), lit_top=False, stain=0.2)
    cv.rect(712, 222, 730, 258, C(0.14, 0.012, HUE))                  # 旧门（门洞，里面黑）
    cv.rect(711, 220, 731, 222, old[5])
    cv.vline(711, 222, 258, old[4])
    cv.vline(730, 222, 258, old[1])
    cv.rect(714, 224, 728, 238, C(0.18, 0.012, HUE))                  # 门板上半截还在
    cv.hline(714, 728, 231, C(0.15, 0.01, HUE))
    cv.rect(734, 232, 744, 238, PAPER_SH)                             # 旧门牌（字迹和上面那块一样：几道一样的小划）
    for xx, yy in ((736, 234), (738, 234), (741, 234), (736, 236), (739, 236)):
        cv.px(xx, yy, C(0.3, 0.02, 60))
    for wx in (780, 840, 900, 960, 1020):                            # 旧窗：只剩窗框
        cv.rect(wx, 226, wx + 20, 248, C(0.13, 0.012, HUE + 4))
        cv.rect(wx - 1, 225, wx + 21, 226, old[5])
        cv.vline(wx + 10, 226, 248, old[3])
        cv.hline(wx, wx + 20, 236, old[3])
        cv.hline(wx - 1, wx + 21, 248, old[5])
    # 街砖：整齐的一排排（阳光好的时候看得见，原文 80）
    brick = stone(0.30, 0.012, HUE - 30)
    for y in range(258, SH, 4):
        off = 0 if (y // 4) % 2 else 6
        cv.rect(0, y, 1440, y + 4, brick[3])
        cv.hline(0, 1440, y, brick[2])
        for x in range(-off, 1440, 12):
            cv.vline(x, y, y + 4, brick[1])
    # 栈道板子和桩
    for x in range(700, 1100, 34):
        post(cv, x + 2, B_G, 258, 5, deck, rng)
    cv.rect(700, B_G, 1100, B_G + 4, deck[3])
    cv.hline(700, 1100, B_G, deck[5])
    cv.hline(700, 1100, B_G + 4, deck[1])
    for x in range(700, 1100, 9):
        cv.vline(x, B_G + 1, B_G + 4, deck[2])
    # ---- 下游浅滩（x 1100–1312）：旧街的地面在这里拱上来，低低的一条湿石面，水清，看得见街砖
    for x in range(1100, 1312):
        gy = int(round(np.interp(x, [1100, 1160, 1300, 1312], [B_G, 213, 213, B_G])))
        cv.vline(x, gy, 258, brick[3])
        cv.px(x, gy, C(0.4, 0.02, H_WATER))
        if gy + 1 < 258:
            cv.px(x, gy + 1, brick[4])
    course_wall(cv, 1160, 1300, 213, 258, brick, rng, course=5, block=(8, 14), lit_top=False, stain=0.05)
    cv.hline(1160, 1300, 213, C(0.46, 0.022, H_WATER))                # 湿亮的面
    cv.hline(1160, 1300, 214, brick[5])
    for px_ in range(1166, 1296, 23):                                  # 石面上几处小水洼（映天）
        cv.hline(px_, px_ + 6 + px_ % 5, 213, C(0.52, 0.02, H_GLINT))
    # ---- 楼梯井（x 1300–1440）：去高处市集的楼梯口（原文 103「高处市集」），门洞里看得见往上的台阶
    sw = stone(0.29, 0.012, HUE - 8)
    course_wall(cv, 1312, 1440, B_G, SH, qst, rng, course=6, block=(12, 24))
    cv.rect(1336, 150, 1366, B_G, C(0.13, 0.012, HUE))
    cv.rect(1334, 146, 1368, 150, sw[5])
    cv.vline(1334, 150, B_G, sw[5])
    cv.vline(1367, 150, B_G, sw[1])
    for i in range(9):                                                # 门洞里往上的台阶（正侧面的锯齿）
        sx = 1338 + i * 3
        cv.rect(sx, B_G - 6 - i * 6, 1366, B_G - i * 6, C(0.17 + 0.008 * (8 - i), 0.012, HUE))
        cv.hline(sx, 1366, B_G - 6 - i * 6, C(0.24, 0.012, HUE))
    cv.rect(1324, 136, 1378, 140, sw[4])
    cv.hline(1324, 1378, 136, sw[6])
    cv.rect(1346, 128, 1356, 135, sw[3])                              # 门上一个小牌：往上的箭头
    cv.vline(1351, 129, 134, PAPER_SH)
    cv.px(1350, 130, PAPER_SH)
    cv.px(1352, 130, PAPER_SH)
    # 旧水位：后排楼上一道苔（新旧水位交界，原文 80）——house() 里按 flood_y 画了；右边小巷口（去南桥）
    cv.rect(1416, 140, 1440, B_G, C(0.16, 0.012, HUE))
    cv.vline(1416, 140, B_G, qst[5])
    return cv


def largest_component(m):
    """最大的一块（8 邻接）。"""
    lbl = np.zeros(m.shape, int)
    best, best_n, k = 0, 0, 0
    H_, W_ = m.shape
    for y0, x0 in zip(*np.nonzero(m)):
        if lbl[y0, x0]:
            continue
        k += 1
        st, n = [(y0, x0)], 0
        lbl[y0, x0] = k
        while st:
            y, x = st.pop()
            n += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < H_ and 0 <= xx < W_ and m[yy, xx] and not lbl[yy, xx]:
                        lbl[yy, xx] = k
                        st.append((yy, xx))
        if n > best_n:
            best, best_n = k, n
    return lbl == best


def Cv_slice(cv, x0, x1, y0, y1):
    out = Cv(x1 - x0, y1 - y0)
    out.a = cv.a[y0:y1, x0:x1].copy()
    return out


def water_body(w, y0, y1, L0=0.34, L1=0.16):
    """前面那片水（water 层，引擎半透明叠在主层前面）：一片水色，越深越暗。"""
    cv = Cv(w, y1 - y0)
    for y in range(cv.h):
        t = y / max(1, cv.h - 1)
        q = round((L0 + (L1 - L0) * t) / 0.03) * 0.03
        cv.hline(0, w, y, C(q, 0.032, H_WATER + 4 * t))
    return cv


def ripples(w, rows, seed):
    """水面上会闪的亮纹（ripples 层，river_water.gdshader palette_mode=false：每 7 像素一段一会儿有一会儿没有）。
    rows = [(水面 y, 往下几行, 密度)]。返回 (Cv, y0)。"""
    y0 = min(r[0] for r in rows) - 1
    y1 = max(r[0] + r[1] for r in rows) + 1
    cv = Cv(w, y1 - y0)
    rng = np.random.default_rng(seed)
    for (wy, depth, dens) in rows:
        cv.hline(0, w, wy - y0, C(0.5, 0.02, H_GLINT))
        for _ in range(int(w * depth * dens / 10)):
            d = int((rng.random() ** 1.8) * depth)
            x = int(rng.integers(0, w))
            ln = int(rng.integers(2, 6 + d))
            cv.hline(x, x + ln, wy - y0 + 1 + d, C(0.56 - 0.012 * d, 0.03, H_GLINT))
    return cv, y0


def front_bank(w, rng):
    """前景（scroll 1.3）：离镜头最近的近黑剪影，只在画面上下边：水里的老桩、一根垂下来的缆绳、屋檐一角。"""
    cv = Cv(w, SH)
    dark = stone(0.11, 0.012, HUE, dL=0.02)
    for x in (120, 760, 1340, 1650):
        top = int(rng.integers(226, 240))
        cv.rect(x, top, x + 9, SH, dark[3])
        cv.hline(x, x + 9, top, dark[5])
        cv.vline(x, top, SH, dark[4])
        cv.rect(x - 1, top + 9, x + 10, top + 11, dark[2])            # 缠的绳
    # 一根从画面上面垂下来的缆绳
    pts = [(560 + i, 4 + 18 * math.sin(math.pi * i / 110)) for i in range(0, 111, 2)]
    cv.line(pts, dark[4])
    return cv


def sun_shafts(w, seed, x_every=(140, 260), slope=0.45, y0=0, y1=SH):
    """左上来的斜光（一层很淡的光带，引擎按 alpha 叠）：几条宽窄不一的斜带，硬边。"""
    cv = Cv(w, SH)
    rng = np.random.default_rng(seed)
    col = C(0.78, 0.03, 85)
    x = int(rng.integers(0, 80))
    while x < w + SH:
        bw = int(rng.integers(10, 34))
        cv.poly([(x, y0), (x + bw, y0), (x + bw - (y1 - y0) * slope, y1), (x - (y1 - y0) * slope, y1)], col)
        x += int(rng.integers(*x_every))
    return cv


def wreck_plane():
    """河岸上的飞机：用坠毁飞船那张图（art/level1/ship_wreck.png，森林的苔堆、碎点去掉），配色不改（它是晨的船）。"""
    a = np.array(Image.open(ROOT / "art" / "level1" / "ship_wreck.png").convert("RGBA"))
    lab = srgb_to_oklab(a[..., :3].reshape(-1, 3)).reshape(a.shape[0], a.shape[1], 3)
    hue = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360
    ch = np.hypot(lab[..., 1], lab[..., 2])
    green = (hue > 90) & (hue < 170) & (ch > 0.02)
    a[green] = 0
    a[:, :, 3][(np.arange(a.shape[0])[:, None] > 60) & (np.arange(a.shape[1])[None, :] < 75)] = \
        a[:, :, 3][(np.arange(a.shape[0])[:, None] > 60) & (np.arange(a.shape[1])[None, :] < 75)]
    # 去掉和船身不连着的碎点
    a[~largest_component(a[..., 3] > 0)] = 0
    cv = Cv(a.shape[1], a.shape[0])
    cv.a = a
    return cv


def plane_frames():
    """river_bank_plane：default = 卡在窄水道里（船身下半截在水里，水层盖住）；beached = 拖上浅滩；
    straps_drying = 机翼绑着、几根绑带晾在旁边的绳上、缝里还在滴水（原文 79）；fixed = 修好（补丁、接好的管子，原文 145）。
    四帧同一张画布（300×96），船在画布里的位置不同：default 靠左低一点（浮在水道里），其余拖到浅滩上。"""
    base = wreck_plane()
    W_, H_ = 300, 96
    out = []
    rng = np.random.default_rng(2201)
    rope = C(0.42, 0.03, 70)
    strap = C(0.34, 0.03, 40)
    for k in range(4):
        cv = Cv(W_, H_)
        if k == 0:
            cv.paste(base, 4, H_ - 78 + 6)
        else:
            cv.paste(base, 70, H_ - 78)
        if k >= 1:
            # 绑机翼的绳：从翼尖斜拉到地上的一根短桩
            cv.rect(250, H_ - 16, 254, H_, C(0.26, 0.02, 64))
            cv.hline(250, 254, H_ - 16, C(0.34, 0.02, 64))
            cv.line([(212, 34), (251, H_ - 14)], rope)
        if k == 2:
            # 晾绑带：两根短杆之间一根绳，挂着四条绑带；船缝里滴水
            for px_ in (262, 296):
                cv.vline(px_, 40, H_, C(0.26, 0.02, 64))
                cv.px(px_, 40, C(0.34, 0.02, 64))
            for i in range(262, 297):
                cv.px(i, 42 + int(round(2 * math.sin(math.pi * (i - 262) / 34))), rope)
            for sx in (266, 273, 280, 288):
                ln = int(rng.integers(12, 20))
                yy = 43 + int(round(2 * math.sin(math.pi * (sx - 262) / 34)))
                cv.rect(sx, yy, sx + 3, yy + ln, strap)
                cv.vline(sx + 2, yy, yy + ln, mix(strap, C(0.2, 0.01, HUE), 0.5))
                cv.px(sx + 1, yy + ln + 2, C(0.5, 0.03, H_GLINT))
            for (dx, dy) in ((150, 70), (171, 66), (198, 61)):
                cv.px(dx, dy, C(0.5, 0.03, H_GLINT))
                cv.px(dx, dy + 3, C(0.44, 0.03, H_GLINT))
        if k == 3:
            # 修好：机身上两块新补丁（亮一档的金属，铆钉），裂开的管子接上一截新管
            for (px_, py, pw, ph) in ((150, 48, 10, 7), (196, 40, 8, 6)):
                cv.rect(px_, py, px_ + pw, py + ph, C(0.42, 0.012, HUE - 30))
                cv.hline(px_, px_ + pw, py, C(0.5, 0.012, HUE - 30))
                for xx in range(px_ + 1, px_ + pw, 3):
                    cv.px(xx, py + 1, C(0.3, 0.01, HUE))
                    cv.px(xx, py + ph - 1, C(0.3, 0.01, HUE))
            cv.rect(222, 58, 236, 61, C(0.46, 0.04, H_WARM - 20))
            cv.hline(222, 236, 58, C(0.56, 0.05, H_WARM - 20))
        out.append(cv)
    return out


def crates_frames():
    """river_bank_crates：岸边一排箱子（原文 74）。tail = 箱子后面露出妮芙的鲸鱼尾在动（两帧）；
    tail_still = 尾巴停住、她站起来了（剧本里 tail_still 下一步就是 show niff + stand_up），所以这一帧没有尾巴，default 也没有。
    尾巴是妮芙身上的，归美术组画：这里只放一块鲸鱼妹尾巴颜色的平涂占位（形状是个大概），美术组的图来了换掉。"""
    W_, H_ = 76, 44
    rng = np.random.default_rng(2301)
    wood = stone(0.34, 0.03, 62)
    box = Cv(W_, H_)
    for (x0, y0, w, h) in ((2, 20, 24, 24), (26, 24, 22, 20), (48, 18, 26, 26), (8, 6, 20, 14)):
        box.rect(x0, y0, x0 + w, y0 + h, wood[3])
        box.hline(x0, x0 + w, y0, wood[5])
        box.vline(x0, y0, y0 + h, wood[4])
        box.vline(x0 + w - 1, y0, y0 + h, wood[1])
        for yy in range(y0 + 5, y0 + h, 6):
            box.hline(x0 + 1, x0 + w - 1, yy, wood[2])
        # 圆圆的字的标签（妮芙写的）
        lx, ly = x0 + 3 + int(rng.integers(0, max(1, w - 12))), y0 + 3
        box.rect(lx, ly, lx + 8, ly + 5, mix(PAPER, wood[3], 0.25))
        box.px(lx + 2, ly + 2, wood[1])
        box.px(lx + 5, ly + 2, wood[1])
    frames = []
    tail = C(0.62, 0.11, 262)            # 鲸鱼妹尾巴的蓝紫（#7195ea 一带）——占位
    tail_hi = C(0.74, 0.08, 255)
    for k in range(3):
        cv = Cv(W_, H_ + 14)
        cv.paste(box, 0, 14)
        if k == 2:
            frames.append(cv)
            continue
        # 尾巴（占位）：从两只箱子之间往上翘，k=0/1 左右摆
        lean = (-2, 2)[k]
        pts = [(40, 40), (44, 40), (45 + lean, 22), (50 + lean * 2, 12), (44 + lean, 14), (38 + lean * 2, 12), (41 + lean, 22)]
        cv.poly(pts, tail)
        cv.line([(42 + lean, 24), (43 + lean, 38)], tail_hi)
        cv.paste(Cv_slice(box, 26, 48, 24, 44), 26, 38)
        frames.append(cv)
    return frames


def box_frames():
    """river_bank_box：金属盒（原文 75）。default = 漂在台阶边的水面上；sunk_shallow = 沉在浅水底（水层盖住，「还看得见」）。"""
    met = stone(0.40, 0.012, HUE - 30)
    out = []
    for k in range(2):
        cv = Cv(14, 40)
        y = 6 if k == 0 else 30
        cv.rect(1, y, 13, y + 9, met[3])
        cv.hline(1, 13, y, met[5])
        cv.vline(1, y, y + 9, met[4])
        cv.vline(12, y, y + 9, met[1])
        cv.hline(1, 13, y + 3, met[2])
        cv.rect(5, y + 4, 9, y + 6, met[5])                          # 搭扣
        cv.rect(4, y + 6, 10, y + 8, mix(PAPER, met[3], 0.4))        # 标签
        out.append(cv)
    return out


def float_crate():
    """开场漂过的木箱（原文 72，飞行一最后一格那只）：漂在水道里，下半截吃水。"""
    cv = Cv(22, 18)
    wood = stone(0.33, 0.03, 62)
    cv.rect(0, 0, 22, 18, wood[3])
    cv.hline(0, 22, 0, wood[5])
    cv.vline(0, 0, 18, wood[4])
    cv.rect(20, 0, 22, 18, wood[1])
    for y in (5, 10):
        cv.hline(1, 20, y, wood[2])
    cv.line([(2, 2), (18, 11)], wood[2])
    return cv


# 剧本 river_salvage 步骤里的 id（会话 B 定的）-> 画哪一样
SALVAGE = {"lid": "pot_lid", "tin": "tea_tin", "joint": "pipe_joint", "bottle": "bottle", "labels": "label_roll"}


def salvage_frames(kind):
    """打捞的漂浮物（第 4.1，原文 76）：5 帧 = 漂着上下晃 2 帧 + 往下沉 3 档（越沉越往下、越暗，水层盖住吃水那截）。
    杯子（原文 75，底下有标签和小扳手）、茶罐、标签纸卷、小锅盖、贴标签的空瓶、管道接头（修船材料，金属、重）。"""
    W_, H_ = 18, 22
    met = stone(0.42, 0.014, HUE - 30)
    base = Cv(W_, 12)
    if kind == "cup":
        base.rect(5, 3, 13, 10, C(0.56, 0.02, 85))
        base.hline(5, 13, 3, C(0.64, 0.02, 85))
        base.vline(12, 3, 10, C(0.46, 0.02, 85))
        base.rect(13, 5, 15, 8, C(0.5, 0.02, 85))
        base.px(14, 6, (0, 0, 0)); base.a[6, 14, 3] = 0
        base.rect(6, 6, 10, 8, PAPER_SH)
    elif kind == "tea_tin":
        base.rect(4, 2, 14, 11, C(0.38, 0.03, 160 + 40))
        base.hline(4, 14, 2, C(0.46, 0.03, 200))
        base.rect(4, 5, 14, 8, mix(PAPER, C(0.4, 0.01, HUE), 0.3))
    elif kind == "label_roll":
        base.ellipse(9, 7, 5, 4, mix(PAPER, C(0.4, 0.01, HUE), 0.2))
        base.ellipse(9, 7, 1.5, 1.5, C(0.3, 0.02, 60))
        base.hline(9, 16, 10, PAPER_SH)
    elif kind == "pot_lid":
        base.rect(2, 7, 16, 9, met[4])
        base.hline(3, 15, 6, met[5])
        base.rect(7, 4, 11, 6, met[2])
    elif kind == "bottle":
        base.rect(4, 5, 14, 10, C(0.4, 0.03, H_GLINT))
        base.rect(14, 6, 17, 9, C(0.38, 0.03, H_GLINT))
        base.hline(4, 14, 5, C(0.52, 0.03, H_GLINT))
        base.rect(7, 6, 11, 9, mix(PAPER, C(0.4, 0.01, HUE), 0.3))
    else:                                                             # 管道接头：重、发暗的铜
        base.rect(3, 4, 15, 9, C(0.4, 0.05, H_WARM - 20))
        base.hline(3, 15, 4, C(0.5, 0.06, H_WARM - 20))
        base.rect(2, 3, 4, 10, C(0.34, 0.04, H_WARM - 20))
        base.rect(14, 3, 16, 10, C(0.34, 0.04, H_WARM - 20))
    out = []
    for k, (dy, dark) in enumerate(((0, 0), (1, 0), (4, 0.04), (7, 0.08), (10, 0.12))):
        cv = Cv(W_, H_)
        cv.paste(base, 0, 4 + dy)
        if dark:
            shade_mask(cv, np.ones((H_, W_), bool), -dark, 0, -10)
        out.append(cv)
    return out


def wake_frames():
    """V 形水纹（第 4.1「漂浮轨迹提供同步视觉信息」）：漂浮物后面拖出两道往后张开的亮纹，2 帧。贴在物件左边（水往右流）。"""
    out = []
    for k in range(2):
        cv = Cv(30, 9)
        c1, c2 = C(0.56, 0.03, H_GLINT), C(0.46, 0.03, H_GLINT)
        for i in range(0, 28, 2):
            sp = i // 6 + k
            cv.px(29 - i, 4 - sp, c1 if i < 12 else c2)
            cv.px(29 - i, 4 + sp, c1 if i < 12 else c2)
        out.append(cv)
    return out


def bank():
    r = Room("river_bank", BANK_W)
    rng = np.random.default_rng(2001)
    r.ground = bank_ground()
    r.shared("sky", 0.0, 0)
    r.shared("far", 0.15, FAR_WL - FAR_ROW_WL)
    r.shared("midfar", 0.35, MIDFAR_WL - MIDFAR_ROW_WL)
    r.layer("mid", mid_strip("river_bank", r.need_w(0.6), 2401, 188), 0.6, 0)
    main = bank_main(rng)
    pre = Cv_slice(main, 1100, 1312, 0, SH)
    underwater_tint(main, B_WL + 1, SH, L_surf=0.33, L_deep=0.15, t0=0.3, t1=0.72)
    # 下游浅滩：水浅、清，街砖看得清（原文 80「阳光好的时候，可以看见水下整齐的街砖」）
    underwater_tint(pre, 215, SH, L_surf=0.42, L_deep=0.3, t0=0.12, t1=0.4)
    main.paste(Cv_slice(pre, 0, 212, 214, SH), 1100, 214)
    caustics(main, 0, BANK_W, B_WL + 6, SH, rng, n=220, L_add=0.05)
    caustics(main, 1160, 1300, 214, 258, rng, n=40, L_add=0.06)
    # 窗框间的小鱼（原文 80）：静的几条（引擎还可以加 river_fish.gd 游的）
    for (fx, fy, d) in ((790, 238, 1), (852, 231, -1), (918, 242, 1), (973, 234, 1), (1031, 240, -1), (1210, 246, 1)):
        fish(main, fx, fy, C(0.42, 0.03, H_GLINT), d)
    r.layer("main", main, 1.0, 0)
    r.layer("shafts", sun_shafts(BANK_W, 2601), 1.0, 0, alpha=0.07, z=-15)
    # 廊道栏杆（在走廊上的人前面）
    rail = Cv(BANK_W, SH)
    gst = stone(0.36, 0.012, HUE - 14)
    railing(rail, 372, B_HOUSE[0], B_GAL - 8, B_GAL, gst[4], gst[2], step=6)          # 妮芙家那段被小屋挡住，不画
    railing(rail, B_HOUSE[1], 1166, B_GAL - 8, B_GAL, gst[4], gst[2], step=6)
    railing(rail, 1206, 1300, B_GAL - 8, B_GAL, gst[4], gst[2], step=6)
    r.layer("rail", rail, 1.0, 0, z=-10)
    wb = water_body(BANK_W, B_WL, SH)
    r.layer("water", wb, 1.0, B_WL, water=True, front=True, alpha=0.4)
    rp, ry = ripples(BANK_W, [(B_BACK_WL, 7, 0.25)], 2502)
    r.layer("ripples_back", rp, 1.0, ry, shader="water", shader_params={"palette_mode": False, "show": 0.7, "wobble": 1.0},
            z=-20)
    rp, ry = ripples(BANK_W, [(B_WL, 14, 0.22)], 2501)
    r.layer("ripples", rp, 1.0, ry, shader="water", shader_params={"palette_mode": False, "show": 0.7, "wobble": 1.0},
            front=True)
    r.layer("front", front_bank(r.need_w(1.3), rng), 1.3, 0, front=True)
    r.extra["water"] = {"y": B_WL}
    r.extra["walk"] = [150, BANK_W - 10]
    # 物件
    pf = plane_frames()
    r.obj("river_bank_plane", pf, 40, B_WL + 2 - 96 + 6, {"default": 0, "beached": 1, "straps_drying": 2, "fixed": 3})
    cf = crates_frames()
    r.obj("river_bank_crates", cf, 420, B_G - cf[0].h, {"default": 2, "tail": [0, 1], "tail_still": 2}, ms=200)
    bf = box_frames()
    r.obj("river_bank_box", bf, 640, B_WL - 12, {"default": 0, "sunk_shallow": 1})
    r.obj("river_bank_crate_float", [float_crate()], 20, B_WL - 9, {"default": 0})
    # 打捞的漂浮物（B 的 river_salvage.gd：float 漂着 / sunk 沉到浅水底 / shallow 停在下游浅滩 / taken 捞走；
    # 它用 stage.move_object 顺水挪 x，y 不动；这里的 x 只是起点）
    for i, (sid, kind) in enumerate(SALVAGE.items()):
        r.obj(f"river_bank_salvage_{sid}", salvage_frames(kind), 230 + i * 16, B_WL - 12,
              {"float": [0, 1], "sink1": 2, "sink2": 3, "sunk": 4, "shallow": 1}, default="hidden", ms=500)
    r.obj("river_bank_salvage_wake", wake_frames(), 200, B_WL - 4, {"on": [0, 1]}, default="hidden", ms=300)
    r.markers = {"river_bank_plane": 190, "river_bank_hatch": 196, "river_bank_channel": 90, "river_bank_crates": 456,
                 "river_bank_niff": 470, "river_bank_steps": 626, "river_bank_box": 646, "river_bank_post": 346,
                 "river_bank_ting": 360, "river_bank_shallow": 1220, "river_bank_toolkit": 304,
                 "river_bank_home_door": 722, "river_bank_doorplate": 738, "river_bank_bakery": 1150,
                 "river_bank_postman": 540, "river_bank_to_market": 1351, "river_bank_to_south": 1428,
                 "river_bank_arrive": 1390,
                 "river_bank_drift_start": 236}
    for oid, (spec, _) in r.objects.items():                     # 打捞物也给同名 marker（物件中心）
        if oid.startswith("river_bank_salvage_") and oid != "river_bank_salvage_wake":
            r.markers[oid] = spec["x"] + spec["w"] // 2
    r.extra["walkers"] = [
        {"npc": "postman", "path": [[500, 67], [590, 67]], "speed": 14, "pause": [3, 8], "z": -20, "loop": "pingpong"},
        {"npc": "hood_a", "path": [[372, B_GAL - 1], [1300, B_GAL - 1]], "speed": 10, "z": -20, "loop": "wrap", "count": 3}]
    r.extra["portals"] = [{"to": "market", "at": "market_entry", "kind": "pan_up", "x": 1351},
                          {"edge": "right", "to": "southbridge", "at": "southbridge_entry", "kind": "walk_fade"}]
    r.extra["ambient"] = [{"name": "river_flow", "db": -12}]
    return r


# ============================================================ 高处市集 market

MARKET_W = 1440
M_G = 200                     # 市集地面（屋顶平台）
M_BRIDGE = (776, 884)         # 平台中间一座窄桥（下面是空的，看得见下面的城和水）


def awning(cv: Cv, x0, x1, y, col_a, col_b, depth=6, stripe=3):
    """遮阳篷（正侧面：一条有条纹的檐，下沿一排小三角）。"""
    for x in range(x0, x1):
        c = col_a if ((x - x0) // stripe) % 2 == 0 else col_b
        cv.vline(x, y, y + depth, c)
        if (x - x0) % 4 < 2:
            cv.px(x, y + depth, c)
    cv.hline(x0 - 1, x1 + 1, y - 1, mix(col_a, C(0.6, 0.01, HUE), 0.3))


def door_marks(cv: Cv, x, y, rng):
    """门边的标记（原文 103「妮芙路过每家店都要看看门边的标记」）：一小条纸签、几道粉笔划、一根系着的布条。"""
    k = int(rng.integers(0, 3))
    if k == 0:
        cv.rect(x, y, x + 3, y + 5, mix(PAPER, C(0.4, 0.01, HUE), 0.35))
        cv.px(x + 1, y + 2, C(0.3, 0.02, 60))
    elif k == 1:
        for i in range(int(rng.integers(2, 5))):
            cv.vline(x + i * 2, y, y + 4, C(0.5, 0.01, HUE - 20))
        cv.line([(x - 1, y + 3), (x + 7, y + 1)], C(0.5, 0.01, HUE - 20))
    else:
        cv.px(x, y, C(0.32, 0.01, HUE))
        cv.vline(x + 1, y, y + 7, C(0.46, 0.06, H_WARM - 30))
        cv.vline(x + 2, y + 1, y + 6, C(0.4, 0.05, H_WARM - 30))


def shop(cv: Cv, x0, x1, base, rng, wall_L=0.3, kind="plain", warm=False):
    """一间铺面（正侧面）：门、橱窗或柜台、遮阳篷、门边的标记。返回 (门 x, 柜台 x)。"""
    st = stone(wall_L, 0.012, HUE - 12)
    dx = x0 + 6 + int(rng.integers(0, 6))
    cv.rect(dx, base - 20, dx + 10, base, GLASS)
    cv.rect(dx - 1, base - 21, dx + 11, base - 20, st[5])
    cv.vline(dx + 10, base - 20, base, st[1])
    cv.px(dx + 8, base - 10, st[5])
    door_marks(cv, dx + 12, base - 17, rng)
    wx0, wx1 = dx + 18, x1 - 6
    if wx1 - wx0 >= 10:
        inside = C(0.4, 0.06, H_WARM) if warm else C(0.2, 0.012, HUE)
        cv.rect(wx0, base - 22, wx1, base - 8, inside)
        cv.rect(wx0 - 1, base - 8, wx1 + 1, base, st[4])                 # 柜台
        cv.hline(wx0 - 1, wx1 + 1, base - 8, st[6])
        cv.hline(wx0 - 1, wx1 + 1, base - 7, st[3])
    return dx, (wx0 + wx1) // 2


def market_main(rng):
    W = MARKET_W
    cv = Cv(W, SH)
    # ---- 平台后面的楼：平台以上只有一两层（市集在高处，天和远城露得多）
    spans = [(0, 120, 120, 0.3), (120, 250, 96, 0.29), (250, 400, 110, 0.31), (400, 590, 80, 0.3),
             (590, 776, 104, 0.29), (884, 1030, 92, 0.3), (1030, 1190, 118, 0.31), (1190, 1316, 100, 0.3),
             (1316, 1440, 70, 0.29)]
    for (x0, x1, top, L) in spans:
        hcv = house(rng, x1 - x0, M_G - top, L, HUE + int(rng.integers(-4, 5)), win=(6, 9), floor_h=20, kind="old")
        cv.paste(hcv, x0, top - 16)
    # ---- 平台：一整条石面（上沿受光），下面是下一层楼的立面（往下沉进雾里）
    pst = stone(0.33, 0.012, HUE - 20)
    for (x0, x1) in ((0, M_BRIDGE[0]), (M_BRIDGE[1], W)):
        cv.rect(x0, M_G, x1, M_G + 6, pst[3])
        cv.hline(x0, x1, M_G, pst[6])
        cv.hline(x0, x1, M_G + 1, pst[5])
        cv.hline(x0, x1, M_G + 6, pst[1])
        below = house(rng, x1 - x0, SH - M_G - 6, 0.25, HUE, win=(6, 9), floor_h=18, kind="block", roof=False)
        cv.paste(Cv_slice(below, 0, x1 - x0, 16, below.h), x0, M_G + 7)
    # 窄桥（市集中间，下面是空的，看得见下面城里的水）
    bst = stone(0.36, 0.014, 60)
    cv.rect(M_BRIDGE[0] - 4, M_G, M_BRIDGE[1] + 4, M_G + 3, bst[3])
    cv.hline(M_BRIDGE[0] - 4, M_BRIDGE[1] + 4, M_G, bst[5])
    for x in range(M_BRIDGE[0], M_BRIDGE[1], 6):
        cv.vline(x, M_G + 1, M_G + 3, bst[2])
    cv.line([(M_BRIDGE[0], M_G + 3), ((M_BRIDGE[0] + M_BRIDGE[1]) // 2, M_G + 12), (M_BRIDGE[1], M_G + 3)], bst[2])
    for x in range(M_BRIDGE[0] + 6, M_BRIDGE[1] - 4, 9):
        t = (x - M_BRIDGE[0]) / (M_BRIDGE[1] - M_BRIDGE[0])
        cv.vline(x, M_G + 3, M_G + 3 + int(9 * math.sin(math.pi * t)), bst[2])
    # ---- 铺面（左 → 右）：卖菜、修补摊、气瓶（借呼吸装置）、饼干、其他几家
    shops = {}
    shops["veg"] = shop(cv, 40, 120, M_G, rng)
    shops["tools"] = shop(cv, 262, 380, M_G, rng)
    shops["breather"] = shop(cv, 430, 560, M_G, rng)
    shops["biscuit"] = shop(cv, 600, 700, M_G, rng, warm=True)
    for (a, b) in ((150, 240), (900, 990), (1040, 1130), (1150, 1250)):
        shops[a] = shop(cv, a, b, M_G, rng, warm=rng.random() < 0.3)
    awning(cv, 36, 124, M_G - 34, C(0.36, 0.02, 150 + 40), C(0.3, 0.012, HUE))
    awning(cv, 258, 384, M_G - 34, C(0.38, 0.03, 60), C(0.3, 0.012, HUE))
    awning(cv, 426, 564, M_G - 36, C(0.36, 0.025, HUE - 40), C(0.29, 0.012, HUE))
    awning(cv, 596, 704, M_G - 32, C(0.46, 0.06, H_WARM), C(0.36, 0.03, H_WARM - 10))
    awning(cv, 1036, 1134, M_G - 34, C(0.34, 0.02, HUE + 20), C(0.29, 0.012, HUE))
    # 卖菜：门口两筐菜（灰绿、旧紫，压得很暗）
    for i, (bx, col) in enumerate(((72, C(0.34, 0.03, 140)), (90, C(0.32, 0.03, 330)), (104, C(0.36, 0.03, 90)))):
        cv.rect(bx, M_G - 7, bx + 12, M_G, C(0.3, 0.025, 64))
        cv.hline(bx, bx + 12, M_G - 7, C(0.38, 0.025, 64))
        for k in range(5):
            cv.rect(bx + 1 + k * 2, M_G - 9 - (k % 2), bx + 3 + k * 2, M_G - 7, col)
    # 修补摊：棚子下面一整面挂工具的墙（工具会晃，单独做成物件 market_tools）
    cv.rect(300, M_G - 32, 376, M_G - 8, C(0.22, 0.014, HUE - 10))
    # 气瓶铺：墙上一排气瓶和面罩
    met = stone(0.4, 0.014, HUE - 24)
    for i, tx in enumerate(range(470, 548, 9)):
        cv.rect(tx, M_G - 30, tx + 6, M_G - 12, met[3])
        cv.vline(tx, M_G - 30, M_G - 12, met[5])
        cv.vline(tx + 5, M_G - 30, M_G - 12, met[1])
        cv.rect(tx + 2, M_G - 33, tx + 4, M_G - 30, met[2])
        cv.rect(tx + 1, M_G - 24, tx + 5, M_G - 21, mix(PAPER, met[3], 0.4))       # 每只瓶上一张归还地点的签
    for mx in (452, 462):                                                         # 挂着的面罩
        cv.ellipse(mx, M_G - 26, 3, 3, C(0.26, 0.012, HUE))
        cv.ellipse(mx, M_G - 26, 2, 2, C(0.36, 0.02, H_GLINT))
    # 饼干：暖光的橱窗里一排罐子、纸袋
    for i, jx in enumerate(range(626, 690, 9)):
        cv.rect(jx, M_G - 20, jx + 6, M_G - 11, C(0.5, 0.05, H_WARM - 10))
        cv.hline(jx, jx + 6, M_G - 20, C(0.58, 0.05, H_WARM - 10))
        cv.rect(jx + 1, M_G - 16, jx + 5, M_G - 13, C(0.62, 0.07, H_WARM))
    # 其他铺面门口的东西：一盏挂灯、一摞木箱、一辆手推车
    wood = stone(0.32, 0.03, 62)
    for (x, y) in ((950, M_G - 10), (962, M_G - 10), (956, M_G - 18)):
        cv.rect(x, y, x + 10, y + 8, wood[3])
        cv.hline(x, x + 10, y, wood[5])
        cv.vline(x + 9, y, y + 8, wood[1])
    cv.rect(1180, M_G - 9, 1204, M_G - 4, wood[3])
    cv.hline(1180, 1204, M_G - 9, wood[5])
    cv.ellipse(1185, M_G - 3, 2.5, 2.5, wood[1])
    cv.ellipse(1199, M_G - 3, 2.5, 2.5, wood[1])
    cv.line([(1204, M_G - 8), (1212, M_G - 14)], wood[2])
    # ---- 楼梯口（市集最右边，从河岸上来的地方）
    sw = stone(0.3, 0.012, HUE - 8)
    cv.rect(1336, M_G - 40, 1366, M_G, C(0.13, 0.012, HUE))
    cv.rect(1332, M_G - 44, 1370, M_G - 40, sw[5])
    cv.vline(1332, M_G - 40, M_G, sw[5])
    cv.vline(1369, M_G - 40, M_G, sw[1])
    for i in range(5):
        cv.rect(1340 + i * 5, M_G - 4 - i * 0, 1366, M_G, C(0.16 + 0.01 * i, 0.012, HUE))
    cv.hline(1338, 1366, M_G - 1, C(0.24, 0.012, HUE))
    # 晾的东西、楼间的细桥（原文 71）
    laundry(cv, 120, 250, 116, rng, sag=4, kind="cloth", density=0.45)
    laundry(cv, 1030, 1190, 126, rng, sag=5, kind="cloth", density=0.4)
    laundry(cv, 1316, 1440, 82, rng, sag=3, kind="cloth", density=0.5)
    return cv, shops


def market_front(w, rng):
    """前景（scroll 1.3）：上沿一排挂着的小旗和电线、下沿平台外面的栏杆柱（近黑剪影）。"""
    cv = Cv(w, SH)
    dark = stone(0.12, 0.012, HUE, dL=0.02)
    for x0 in range(0, w, 260):
        x1 = x0 + 200
        pts = [(x0 + i, 6 + 12 * math.sin(math.pi * i / 200)) for i in range(0, 201)]
        cv.line(pts, dark[3])
        for i in range(8, 200, 14):
            y = int(6 + 12 * math.sin(math.pi * i / 200))
            cv.poly([(x0 + i, y), (x0 + i + 6, y), (x0 + i + 3, y + 6)], dark[4] if (i // 14) % 2 else dark[2])
    for x in range(40, w, 330):
        cv.rect(x, 236, x + 8, SH, dark[3])
        cv.hline(x - 1, x + 9, 236, dark[5])
    return cv


def market_rail(w, rng, gaps=()):
    """平台外沿的栏杆（scroll 1，在人前面，很细，晨看得见）+ 吊在栏杆外的菜篮（原文 103）。"""
    cv = Cv(w, SH)
    st = stone(0.34, 0.012, HUE - 16)
    for (x0, x1) in ((0, M_BRIDGE[0]), (M_BRIDGE[1], w)):
        cv.hline(x0, x1, M_G - 13, st[5])
        cv.hline(x0, x1, M_G - 12, st[3])
        for x in range(x0 + 2, x1, 10):
            cv.vline(x, M_G - 11, M_G, st[3])
    # 窄桥的扶手：两根绳
    rope = C(0.4, 0.03, 70)
    for yy in (M_G - 12, M_G - 7):
        pts = [(M_BRIDGE[0] + i, yy + 3 * math.sin(math.pi * i / (M_BRIDGE[1] - M_BRIDGE[0])))
               for i in range(0, M_BRIDGE[1] - M_BRIDGE[0] + 1, 2)]
        cv.line(pts, rope)
    return cv


def baskets_frames():
    """market_baskets：卖菜的人把篮子吊在栏杆外（原文 103）：三只吊篮，两帧轻轻晃。"""
    out = []
    for k in range(2):
        cv = Cv(70, 40)
        rope = C(0.38, 0.02, 70)
        for i, (bx, ln, col) in enumerate(((6, 16, C(0.34, 0.03, 140)), (28, 22, C(0.36, 0.03, 90)),
                                           (50, 14, C(0.32, 0.03, 330)))):
            sway = (k + i) % 2
            cv.vline(bx + 6, 0, ln, rope)
            cv.poly([(bx + sway, ln), (bx + 12 + sway, ln), (bx + 10 + sway, ln + 9), (bx + 2 + sway, ln + 9)],
                    C(0.32, 0.03, 64))
            cv.hline(bx + sway, bx + 12 + sway, ln, C(0.4, 0.03, 66))
            for j in range(4):
                cv.rect(bx + 2 + j * 2 + sway, ln - 2 - (j % 2), bx + 4 + j * 2 + sway, ln, col)
            for yy in range(ln + 3, ln + 9, 3):
                cv.hline(bx + 2 + sway, bx + 10 + sway, yy, C(0.27, 0.025, 60))
        out.append(cv)
    return out


def tools_frames():
    """market_tools：修补摊挂了一墙工具，叮当响（原文 103）：4 帧，一排工具依次轻轻晃。"""
    out = []
    met = stone(0.42, 0.012, HUE - 24)
    for k in range(4):
        cv = Cv(76, 26)
        cv.hline(0, 76, 1, C(0.3, 0.02, 64))
        for i, tx in enumerate(range(4, 72, 6)):
            sw = 1 if (i + k) % 4 == 0 else (-1 if (i + k) % 4 == 2 else 0)
            kind = i % 4
            ln = 10 + (i * 5) % 9
            cv.line([(tx, 2), (tx + sw, ln)], met[3])
            if kind == 0:                                 # 扳手
                cv.rect(tx - 1 + sw, ln, tx + 2 + sw, ln + 2, met[4])
            elif kind == 1:                               # 钳子
                cv.px(tx - 1 + sw, ln + 1, met[4])
                cv.px(tx + 1 + sw, ln + 1, met[4])
            elif kind == 2:                               # 卷尺 / 线团
                cv.ellipse(tx + sw, ln + 1, 2, 2, C(0.5, 0.06, H_WARM - 20))
            else:                                         # 小铃（叮当）
                cv.rect(tx - 1 + sw, ln, tx + 2 + sw, ln + 2, AMBER)
            cv.px(tx, 2, met[5])
        out.append(cv)
    return out


def breather_frames():
    """market_breather_stall：default = 柜台空着；tank_on_counter = 摊主把气瓶放到柜台上（原文 103）：气瓶 + 面罩 + 一张归还地点的签。"""
    met = stone(0.44, 0.014, HUE - 24)
    out = []
    for k in range(2):
        cv = Cv(30, 22)
        if k == 1:
            cv.rect(8, 2, 15, 21, met[3])
            cv.vline(8, 2, 21, met[5])
            cv.vline(14, 2, 21, met[1])
            cv.rect(10, 0, 13, 2, met[2])
            cv.rect(9, 9, 14, 12, mix(PAPER, met[3], 0.3))
            cv.ellipse(21, 16, 4, 3, C(0.26, 0.012, HUE))
            cv.ellipse(21, 16, 3, 2, C(0.4, 0.03, H_GLINT))
            cv.line([(14, 6), (18, 13)], C(0.2, 0.01, HUE))
        out.append(cv)
    return out


def market():
    r = Room("market", MARKET_W)
    rng = np.random.default_rng(3001)
    r.ground = M_G
    r.shared("sky", 0.0, 0)
    r.shared("far", 0.15, 228 - FAR_ROW_WL)
    r.shared("midfar", 0.35, 262 - MIDFAR_ROW_WL)
    r.layer("mid", mid_strip("market", r.need_w(0.6), 3401, 290, L=0.32, top_rng=(110, 190)), 0.6, 0)
    main, shops = market_main(rng)
    r.layer("main", main, 1.0, 0)
    r.layer("shafts", sun_shafts(MARKET_W, 3601), 1.0, 0, alpha=0.08, z=-15)
    r.layer("rail", market_rail(MARKET_W, rng), 1.0, 0, front=True)
    r.layer("front", market_front(r.need_w(1.3), rng), 1.3, 0, front=True)
    bf = baskets_frames()
    r.obj("market_baskets", bf, 60, M_G - 13, {"default": [0, 1]}, ms=600, front=True)
    r.obj("market_tools", tools_frames(), 300, M_G - 32, {"default": [0, 3]}, fps=4)
    r.obj("market_breather_stall", breather_frames(), shops["breather"][1] - 15, M_G - 8 - 21,
          {"default": 0, "tank_on_counter": 1})
    r.markers = {"market_entry": 1351, "market_back": 1342, "market_niff": 1310, "market_breather_stall": shops["breather"][1],
                 "market_keeper": shops["breather"][1] + 6, "market_biscuit_stall": shops["biscuit"][1],
                 "market_baskets": 90, "market_tool_stall": 330, "market_bridge": (M_BRIDGE[0] + M_BRIDGE[1]) // 2,
                 "market_to_oldstreet": 16}
    r.extra["walk"] = [10, MARKET_W - 60]
    r.extra["walkers"] = [
        {"npc": "hood_a", "path": [[0, M_G - 1], [MARKET_W, M_G - 1]], "speed": 12, "z": -20, "loop": "wrap", "count": 5},
        {"npc": "vendor", "path": [[80, M_G - 1], [130, M_G - 1]], "speed": 8, "pause": [4, 10], "z": -20,
         "loop": "pingpong"}]
    r.extra["portals"] = [{"to": "river_bank", "at": "river_bank_to_market", "kind": "pan_down", "x": 1351},
                          {"edge": "left", "to": "oldstreet", "at": "oldstreet_entry", "kind": "walk_fade"}]
    r.extra["ambient"] = [{"name": "tools_clink", "x": 330, "db": -10, "range": 300}, {"name": "river_flow", "db": -20}]
    return r


# ============================================================ 旧街 + 水闸 oldstreet

OLD_W = 1280
O_UP, O_LOW = 150, 236                      # 上层闸台、下层旧街的地面
O_LEVELS = {"submerged": 156, "l1": 178, "l2": 200, "l3": 222, "revealed": 246}   # 水位（墙上的年份刻线就在这几行）
O_STEPS = (440, 580)                        # 踏步：从上层往下到旧街
O_WAREHOUSE = (1036, 1092)                  # 仓库入口：旧街最低处往下的一段台阶，一直在水下
WHEELS = {1: (206, 116, 5), 2: (252, 116, 5), 3: (318, 112, 8)}    # 闸轮：中心 x, y, 半径（3 是大的）


def old_ground():
    pts = [[0, O_UP], [O_STEPS[0], O_UP]]
    n = 14
    for i in range(1, n + 1):
        x = O_STEPS[0] + i * (O_STEPS[1] - O_STEPS[0]) // n
        pts.append([x, O_UP + i * (O_LOW - O_UP) // n])
    pts += [[O_WAREHOUSE[0], O_LOW], [O_WAREHOUSE[0] + 40, 262], [O_WAREHOUSE[1], 262], [O_WAREHOUSE[1] + 4, O_LOW],
            [OLD_W, O_LOW]]
    return pts


def pipe(cv: Cv, pts, st, w=3):
    """一根管子（正侧面，折线）：上沿受光、下沿背光；拐角一个法兰。"""
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if y0 == y1:
            a, b = sorted((x0, x1))
            cv.hline(a, b + w, y0 + w, C(0.14, 0.01, HUE))                 # 管子在墙上的影子
            cv.rect(a, y0, b + w, y0 + w, st[3])
            cv.hline(a, b + w, y0, st[5])
            cv.hline(a, b + w, y0 + w - 1, st[1])
            for xx in range(a + 12, b, 24):                                   # 管卡
                cv.vline(xx, y0 - 1, y0 + w + 1, st[1])
        else:
            a, b = sorted((y0, y1))
            cv.vline(x0 + w, a, b + w, C(0.14, 0.01, HUE))
            cv.rect(x0, a, x0 + w, b + w, st[3])
            cv.vline(x0, a, b + w, st[5])
            cv.vline(x0 + w - 1, a, b + w, st[1])
    for (x, y) in pts[1:-1]:
        cv.rect(x - 1, y - 1, x + w + 1, y + w + 1, st[4])
        cv.hline(x - 1, x + w + 1, y - 1, st[6])
    x, y = pts[-1]
    cv.rect(x - 1, y - 1, x + w + 1, y + w + 1, st[2])          # 出水口
    cv.rect(x, y, x + w, y + w, C(0.1, 0.01, HUE))


def wheel_frames(r, plate=True, n=8):
    """sluice_wheel_N：闸轮 + 下面一条刻度。8 帧 = 转到 8 个位置（指针指着刻度上第几格）；plate=False 的少了铭牌（只剩两个螺丝眼、一块干净的印子）。"""
    met = stone(0.40, 0.016, HUE - 30)
    size = 2 * r + 8
    out = []
    for k in range(n):
        cv = Cv(size + 10, size + 12)
        cx, cy = size // 2 + 5, size // 2
        cv.ellipse(cx, cy, r + 1.4, r + 1.4, met[2])
        cv.ellipse(cx, cy, r + 0.4, r + 0.4, met[4])
        cv.ellipse(cx, cy, r - 0.8, r - 0.8, C(0.16, 0.01, HUE))
        ang = k * math.pi / 4
        for j in range(4):                                         # 辐条
            a = ang + j * math.pi / 2
            cv.line([(cx, cy), (cx + round((r - 0.5) * math.cos(a)), cy + round((r - 0.5) * math.sin(a)))], met[3])
        cv.ellipse(cx, cy, 1.4, 1.4, met[5])
        hx, hy = cx + round((r + 1) * math.cos(ang)), cy + round((r + 1) * math.sin(ang))
        cv.rect(hx - 1, hy - 1, hx + 1, hy + 1, AMBER if r >= 8 else met[6])     # 摇把
        # 刻度条：8 格，指针指在第 k 格
        sy = size + 4
        cv.rect(cx - 9, sy, cx + 9, sy + 3, met[2])
        for j in range(8):
            cv.vline(cx - 8 + j * 2 + (j > 3), sy, sy + 2, met[4])
        px_ = cx - 8 + k * 2 + (k > 3)
        cv.rect(px_, sy - 2, px_ + 1, sy, AMBER)
        # 铭牌
        if plate:
            cv.rect(cx - 6, sy + 4, cx + 6, sy + 8, mix(PAPER, met[3], 0.35))
            for j in range(4):
                cv.px(cx - 4 + j * 3, sy + 6, met[1])
        else:
            cv.rect(cx - 6, sy + 4, cx + 6, sy + 8, met[4])
            cv.px(cx - 5, sy + 6, met[1])
            cv.px(cx + 5, sy + 6, met[1])
        out.append(cv)
    return out


def bubble_frames():
    """sluice_pipes：出水口冒泡（原文 105「咕噜咕噜」）。bubble_3 / 2 / 1 三档（各 2 帧）+ still（不冒）。"""
    out = []
    col, hi = C(0.5, 0.03, H_GLINT), C(0.62, 0.03, H_GLINT)
    for lvl in (3, 2, 1):
        for k in range(2):
            cv = Cv(16, 30)
            rng = np.random.default_rng(lvl * 10 + k)
            for _ in range(lvl * 4):
                x = 8 + int(rng.integers(-2 - lvl, 3 + lvl))
                y = int(rng.integers(2, 28))
                if rng.random() < 0.4:
                    cv.rect(x, y, x + 2, y + 2, col)
                    cv.px(x, y, hi)
                else:
                    cv.px(x, y, col)
            cv.hline(8 - lvl * 2, 9 + lvl * 2, 0, hi)              # 水面上的一圈
            out.append(cv)
    out.append(Cv(16, 30))
    return out


def oldstreet_main(rng):
    W = OLD_W
    cv = Cv(W, SH)
    # ---- 上层闸台后面的墙（x 0–440）：管道、年份刻线在它右边那截挡土墙上
    wst = stone(0.29, 0.012, HUE - 18)
    hcv = house(rng, 440, O_UP - 30, 0.28, HUE, win=(7, 10), floor_h=20, kind="old")
    cv.paste(hcv, 0, 30 - 16)
    course_wall(cv, 0, 440, 92, O_UP, wst, rng, course=7, block=(14, 28), lit_top=True, stain=0.25)
    # ---- 旧街这一边的楼（x 440–1280）：上面一排现在的店的招牌，下面一排更旧的门窗（同样的店名、油漆剥落，原文 108）
    spans = [(440, 640, 20), (640, 760, 40), (800, 1000, 12), (1000, 1150, 30), (1150, 1280, 24)]
    for (x0, x1, top) in spans:
        hcv = house(rng, x1 - x0, O_LOW - top, 0.27, HUE + int(rng.integers(-4, 5)), win=(7, 10), floor_h=20,
                    kind="old", flood_y=O_LEVELS["l1"] - top)
        cv.paste(hcv, x0, top - 16)
    # 拐角（x 760–800）：两栋楼之间一条窄巷，往里黑下去；巷口只剩半截台阶（原文 108「以前从这里能买果酱」）
    cv.rect(760, 60, 800, O_LOW, C(0.15, 0.012, HUE + 4))
    cv.rect(760, 60, 763, O_LOW, C(0.22, 0.012, HUE))
    for i in range(4):                                          # 半截台阶：往上四级，到半空就断了
        cv.rect(768 + i * 6, O_LOW - 5 - i * 5, 800, O_LOW - i * 5, wst[3 + (i % 2)])
        cv.hline(768 + i * 6, 800, O_LOW - 5 - i * 5, wst[5])
    cv.rect(788, O_LOW - 26, 800, O_LOW - 20, wst[2])          # 断口
    for (x, y) in ((790, O_LOW - 27), (795, O_LOW - 28), (798, O_LOW - 26)):
        cv.px(x, y, wst[2])
    jam = C(0.36, 0.05, 20)                                     # 墙上褪色的果酱罐招牌（只剩轮廓）
    cv.rect(774, O_LOW - 64, 790, O_LOW - 46, mix(jam, wst[3], 0.55))
    cv.rect(778, O_LOW - 68, 786, O_LOW - 64, mix(jam, wst[3], 0.7))
    # 现在的店（在上面那层）：一排挂出来的招牌；下面同一个位置是更旧的门，门楣上写着同样的店名（剥落）
    signs = [(470, 0), (540, 1), (600, 2), (668, 3), (830, 4), (900, 5), (1050, 6), (1180, 7)]
    sign_cols = [C(0.36, 0.03, 60), C(0.34, 0.02, HUE - 40), C(0.38, 0.04, 30), C(0.35, 0.02, 160 + 40),
                 C(0.37, 0.03, 80), C(0.34, 0.02, HUE + 30), C(0.36, 0.03, 50), C(0.35, 0.02, HUE - 60)]
    for (sx, k) in signs:
        col = sign_cols[k]
        # 上面：现在的招牌（挂在铁架上）
        cv.hline(sx - 2, sx + 16, 128, C(0.3, 0.01, HUE))
        cv.vline(sx - 2, 124, 129, C(0.3, 0.01, HUE))
        cv.rect(sx, 130, sx + 16, 140, col)
        cv.hline(sx, sx + 16, 130, mix(col, C(0.6, 0.01, 80), 0.3))
        glyph = [(2, 3), (4, 3), (6, 3), (9, 3), (11, 3), (3, 5), (8, 5), (12, 5)]
        g = glyph[k % len(glyph):] + glyph[:k % len(glyph)]
        for (gx, gy) in g[:5]:
            cv.px(sx + gx, 130 + gy, mix(col, C(0.6, 0.02, 80), 0.6))
        # 下面：更旧的门（门洞、门楣上同样的店名，褪色剥落）
        dx = sx - 2
        cv.rect(dx, O_LOW - 26, dx + 18, O_LOW, C(0.13, 0.012, HUE))
        cv.rect(dx - 2, O_LOW - 34, dx + 20, O_LOW - 27, mix(col, wst[3], 0.5))
        for (gx, gy) in g[:5]:
            if (gx + k) % 3:
                cv.px(dx + gx + 2, O_LOW - 31 + gy // 2, mix(col, C(0.55, 0.02, 80), 0.35))
        for _ in range(4):                                      # 剥落：几块露出底下墙色
            px_, py = dx - 1 + int(rng.integers(0, 20)), O_LOW - 34 + int(rng.integers(0, 6))
            cv.rect(px_, py, px_ + int(rng.integers(1, 4)), py + 1, wst[3])
        cv.rect(dx + 3, O_LOW - 22, dx + 15, O_LOW - 12, C(0.18, 0.012, HUE))   # 门上的小窗
        cv.vline(dx + 9, O_LOW - 22, O_LOW - 12, wst[2])
    # 身高刻线墙（原文 109）：一排小小的刻线 + 最上面一道粗红线（写着洪水的日期），高过妮芙头顶很多
    hx = 868
    cv.rect(hx - 4, 100, hx + 24, O_LOW, mix(wst[3], wst[4], 0.5))
    cv.vline(hx - 4, 100, O_LOW, wst[5])
    for i, y in enumerate(range(O_LOW - 30, O_LOW - 6, 3)):
        ln = 5 + (i % 3) * 2
        cv.hline(hx + 2, hx + 2 + ln, y, wst[1])
        if i % 2 == 0:
            cv.px(hx + 4 + ln, y, wst[2])
    red = C(0.42, 0.09, 28)
    cv.rect(hx - 4, 114, hx + 24, 117, red)
    cv.hline(hx - 4, hx + 24, 114, C(0.48, 0.09, 30))
    for j, gx in enumerate((hx + 2, hx + 5, hx + 9, hx + 12, hx + 16)):
        cv.px(gx, 119 + (j % 2), mix(red, wst[3], 0.3))         # 日期（几个小字）
    # 干燥的台阶（原文 109「晨在旁边找了一处干燥的台阶」）
    cv.rect(930, O_LOW - 10, 974, O_LOW, wst[4])
    cv.rect(938, O_LOW - 16, 974, O_LOW - 10, wst[3])
    cv.hline(930, 974, O_LOW - 10, wst[6])
    cv.hline(938, 974, O_LOW - 16, wst[6])
    # 仓库：入口在水下（原文 110），门在旧街最低处往下的台阶尽头；外侧墙上一只旧挂钩（原文 143）
    cv.rect(O_WAREHOUSE[0] + 34, 222, O_WAREHOUSE[1] + 2, SH, C(0.1, 0.012, HUE + 4))
    cv.rect(O_WAREHOUSE[0] + 32, 218, O_WAREHOUSE[1] + 4, 222, wst[5])
    cv.hline(O_WAREHOUSE[0] + 36, O_WAREHOUSE[1], 226, C(0.4, 0.06, H_WARM - 20))     # 门楣上一条旧漆（仓库）
    cv.rect(O_WAREHOUSE[0] - 2, 150, O_WAREHOUSE[1] + 30, 158, wst[4])                # 仓库的檐
    cv.hline(O_WAREHOUSE[0] - 2, O_WAREHOUSE[1] + 30, 150, wst[6])
    hook = (1112, 204)
    cv.rect(hook[0], hook[1], hook[0] + 3, hook[1] + 2, C(0.3, 0.012, HUE))
    cv.vline(hook[0] + 1, hook[1] + 2, hook[1] + 7, C(0.32, 0.012, HUE))
    cv.px(hook[0] + 2, hook[1] + 7, C(0.32, 0.012, HUE))
    cv.px(hook[0] + 3, hook[1] + 6, C(0.32, 0.012, HUE))
    # ---- 地面：上层闸台（石面）、踏步、旧街路面（街砖）、仓库口往下的台阶
    gst = stone(0.31, 0.012, HUE - 26)
    course_wall(cv, 0, O_STEPS[0], O_UP, SH, gst, rng, course=7, block=(14, 30))
    n = 14
    for i in range(n):
        x0 = O_STEPS[0] + i * (O_STEPS[1] - O_STEPS[0]) // n
        x1 = O_STEPS[0] + (i + 1) * (O_STEPS[1] - O_STEPS[0]) // n
        y = O_UP + (i + 1) * (O_LOW - O_UP) // n
        cv.rect(x0, y, x1, SH, gst[3 + (i % 2)])
        cv.hline(x0, x1, y, gst[6])
        cv.vline(x1 - 1, y, y + 3, gst[1])
    brick = stone(0.3, 0.012, HUE - 30)
    for y in range(O_LOW, SH, 4):
        off = 0 if (y // 4) % 2 else 6
        cv.rect(O_STEPS[1], y, W, y + 4, brick[3])
        cv.hline(O_STEPS[1], W, y, brick[2])
        for x in range(O_STEPS[1] - off, W, 12):
            cv.vline(x, y, y + 4, brick[1])
    cv.hline(O_STEPS[1], W, O_LOW, brick[5])
    # 仓库口：路面在这里断开，几级台阶往下没进水里
    cv.rect(O_WAREHOUSE[0], O_LOW, O_WAREHOUSE[1], SH, C(0.14, 0.012, HUE))
    for i in range(5):
        x = O_WAREHOUSE[0] + i * 8
        y = O_LOW + 2 + i * 6
        cv.rect(x, y, x + 8, SH, gst[3])
        cv.hline(x, x + 8, y, gst[5])
    # 各层水位留在墙上的苔痕（旧水位）
    moss_line(cv, O_STEPS[1], W, O_LEVELS["l2"], rng, depth=1, L=0.22, seed=5)
    # ---- 年份刻线（原文 105）：踏步旁那截挡土墙上，正好对着几个水位；最旧（最低）那条被苔盖住
    mx = 404
    cv.rect(mx, O_UP + 2, mx + 30, SH, mix(gst[3], gst[4], 0.4))
    cv.vline(mx, O_UP + 2, SH, gst[5])
    for k, (name, y) in enumerate(O_LEVELS.items()):
        if name == "submerged":
            continue
        cv.hline(mx + 3, mx + 26, y, C(0.48, 0.012, HUE - 30))
        cv.hline(mx + 3, mx + 26, y + 1, gst[1])
        for j in range(3):                                      # 年份（几个小刻字）
            cv.px(mx + 5 + j * 3, y - 3, C(0.46, 0.012, HUE - 30))
    moss_line(cv, mx + 1, mx + 30, O_LEVELS["revealed"] + 2, rng, depth=4, L=0.24, seed=9)
    # ---- 管道（原文 105「管道方向」）：从三只闸轮通向墙上不同的地方，方向要看得清
    pst = stone(0.42, 0.016, HUE - 40, dL=0.04)
    (x1, y1, _), (x2, y2, _), (x3, y3, _) = WHEELS[1], WHEELS[2], WHEELS[3]
    pipe(cv, [(x1 - 1, y1 + 8), (x1 - 1, 132), (40, 132), (40, 186)], pst)                    # 1：往左，下到闸台底下
    pipe(cv, [(x2 - 1, y2 + 8), (x2 - 1, 138), (452, 138), (452, 210)], pst)                  # 2：往右，下到踏步旁
    pipe(cv, [(x3 - 1, y3 - 12), (x3 - 1, 90), (712, 90), (712, O_LOW - 40)], pst, w=4)      # 3（大的）：往上，绕到旧街
    # 闸轮后面的墙板
    for (wx, wy, r) in WHEELS.values():
        cv.rect(wx - r - 4, wy - r - 4, wx + r + 6, wy + r + 24, mix(wst[2], wst[3], 0.5))
    return cv


def oldstreet():
    r = Room("oldstreet", OLD_W)
    rng = np.random.default_rng(4001)
    r.ground = old_ground()
    r.shared("sky", 0.0, 0)
    r.shared("far", 0.15, FAR_WL - FAR_ROW_WL)
    r.shared("midfar", 0.35, MIDFAR_WL - MIDFAR_ROW_WL)
    r.layer("mid", mid_strip("oldstreet", r.need_w(0.6), 4401, 188), 0.6, 0)
    r.layer("main", oldstreet_main(rng), 1.0, 0)
    r.layer("shafts", sun_shafts(OLD_W, 4601), 1.0, 0, alpha=0.07, z=-15)
    rail = Cv(OLD_W, SH)
    gst = stone(0.36, 0.012, HUE - 14)
    railing(rail, 0, O_STEPS[0] - 30, O_UP - 12, O_UP, gst[5], gst[3], step=7)       # 妮芙趴着听的栏杆（原文 105）
    r.layer("rail", rail, 1.0, 0, front=True)
    y0 = O_LEVELS["submerged"]
    wb = water_body(OLD_W, y0, SH + (O_LEVELS["revealed"] - y0) + 2, L0=0.36, L1=0.18)
    r.layer("water", wb, 1.0, y0, water=True, front=True, alpha=0.55)
    rp, ry = ripples(OLD_W, [(y0, 10, 0.25)], 4501)
    r.layer("ripples", rp, 1.0, ry, water=True, front=True, shader="water",
            shader_params={"palette_mode": False, "show": 0.7, "wobble": 1.0})
    r.layer("front", front_bank(r.need_w(1.3), rng), 1.3, 0, front=True)
    r.extra["water"] = {"y": y0, "prop": "oldstreet_steps", "levels": O_LEVELS, "sec": 1.5}
    r.extra["walk"] = [12, OLD_W - 12]
    r.extra["walk_when"] = [{"prop": "oldstreet_steps=submerged", "walk": [12, O_STEPS[0] + 6]},
                            {"prop": "oldstreet_steps=l1", "walk": [12, O_STEPS[0] + 30]},
                            {"prop": "oldstreet_steps=l2", "walk": [12, O_STEPS[0] + 60]},
                            {"prop": "oldstreet_steps=l3", "walk": [12, O_STEPS[0] + 100]}]
    for k, (wx, wy, rr) in WHEELS.items():
        fr = wheel_frames(rr, plate=(k == 3))
        st = {f"pos{i}": i for i in range(8)}
        st.update({"default": 0, "set": 2, "ready": 0})
        r.obj(f"sluice_wheel_{k}", fr, wx - fr[0].w // 2, wy - (2 * rr + 8) // 2, st)
    bf = bubble_frames()
    r.obj("sluice_pipes", bf, 452 + 1 - 8, 180, {"bubble_3": [0, 1], "bubble_2": [2, 3], "bubble_1": [4, 5], "still": 6,
                                                  "default": [0, 1]}, fps=6)
    r.markers = {"oldstreet_entry": 30, "oldstreet_back": 16, "oldstreet_niff": 70, "oldstreet_railing": 290,
                 "oldstreet_marks": 418, "sluice_wheel_1": WHEELS[1][0], "sluice_wheel_2": WHEELS[2][0],
                 "sluice_wheel_3": WHEELS[3][0], "sluice_pipes": 452, "oldstreet_steps": 470,
                 "oldstreet_signs": 620, "oldstreet_corner": 784, "oldstreet_height_wall": 878,
                 "oldstreet_dry_step": 950, "oldstreet_warehouse_entry": O_WAREHOUSE[0] + 30,
                 "oldstreet_hook": 1114, "oldstreet_to_south": OLD_W - 16}
    r.extra["portals"] = [{"edge": "left", "to": "market", "at": "market_to_oldstreet", "kind": "walk_fade"},
                          {"edge": "right", "to": "southbridge", "at": "southbridge_entry", "kind": "walk_fade"},
                          {"to": "warehouse", "at": "warehouse_entry", "kind": "pan_down", "x": O_WAREHOUSE[0] + 30}]
    r.extra["ambient"] = [{"name": "pipe_gurgle", "x": 452, "db": -6, "range": 260}, {"name": "river_flow", "db": -14}]
    return r


# ============================================================ 水下仓库 warehouse

WH_W = 720
WH_G, WH_CEIL = 236, 36            # 地板、天花板下沿
WH_DOOR = 548                      # 内门（隔墙）的 x


def wh_back():
    """仓库外面（scroll .3）：后墙破窗里看出去的水——远处泡着的楼影、往上越亮（水面在很高的地方）。"""
    w = int(math.ceil(SW + (WH_W - SW) * 0.3))
    cv = Cv(w, SH)
    for y in range(SH):
        L = 0.34 - 0.2 * (y / SH)
        cv.hline(0, w, y, C(round(L / 0.025) * 0.025, 0.035, H_WATER + 6))
    rng = np.random.default_rng(5101)
    x = -10
    while x < w:
        bw = int(rng.integers(30, 60))
        top = int(rng.integers(40, 120))
        cv.rect(x, top, x + bw, SH, C(0.17, 0.03, H_WATER + 8))
        for yy in range(top + 6, SH, 12):
            for xx in range(x + 4, x + bw - 4, 8):
                cv.rect(xx, yy, xx + 3, yy + 5, C(0.13, 0.03, H_WATER + 10))
        x += bw + int(rng.integers(10, 30))
    return cv


def warehouse_main(rng):
    W = WH_W
    cv = Cv(W, SH)
    wall = stone(0.25, 0.016, HUE - 14)
    # 后墙：抹灰墙 + 一排高窗（破了，看得见外面的水 = 透明，露出 back 层）
    cv.rect(0, 0, W, SH, wall[3])
    for y in range(WH_CEIL + 20, WH_G, 26):
        cv.hline(0, W, y, wall[2])
    for wx in range(90, W - 60, 92):
        cv.clear(wx, 52, wx + 34, 92)
        cv.rect(wx - 2, 50, wx + 36, 52, wall[5])
        cv.rect(wx - 2, 92, wx + 36, 94, wall[5])
        cv.vline(wx + 17, 52, 92, wall[2])
        cv.hline(wx, wx + 34, 72, wall[2])
        for (gx, gy) in ((wx + 3, 60), (wx + 26, 80)):                 # 碎玻璃的残角
            cv.poly([(gx, gy), (gx + 5, gy), (gx, gy + 6)], C(0.3, 0.03, H_GLINT))
    # 天花板：粗梁
    cv.rect(0, 0, W, WH_CEIL, wall[1])
    cv.hline(0, W, WH_CEIL - 1, wall[3])
    for bx in range(30, W, 120):
        cv.rect(bx, WH_CEIL, bx + 10, WH_CEIL + 8, wall[2])
        cv.hline(bx, bx + 10, WH_CEIL + 8, wall[3])
    # 地板
    floor = stone(0.27, 0.016, HUE - 24)
    cv.rect(0, WH_G, W, SH, floor[3])
    cv.hline(0, W, WH_G, floor[5])
    for x in range(0, W, 16):
        cv.vline(x, WH_G + 1, SH, floor[2])
    # 入口（左）：门洞，上面一盏出口灯（物件，会亮）
    cv.rect(14, 150, 52, WH_G, C(0.12, 0.02, H_WATER))
    cv.rect(10, 146, 56, 150, wall[5])
    cv.vline(10, 150, WH_G, wall[5])
    cv.vline(55, 150, WH_G, wall[1])
    # 隔墙 + 内门（物件 warehouse_inner_door 开 / 关）
    cv.rect(WH_DOOR - 8, WH_CEIL, WH_DOOR + 8, WH_G, wall[2])
    cv.vline(WH_DOOR - 8, WH_CEIL, WH_G, wall[4])
    cv.rect(WH_DOOR - 6, 176, WH_DOOR + 6, WH_G, C(0.1, 0.02, H_WATER))
    # 桌椅被绑到高处（原文 111）：天花板梁上吊着、绳子勒着
    wood = stone(0.3, 0.025, 60)
    rope = C(0.38, 0.03, 70)
    for (tx, ty, kind) in ((84, 46, "table"), (130, 50, "chair"), (176, 44, "table"), (232, 52, "chair"),
                           (300, 48, "chair"), (350, 44, "table")):
        if kind == "table":
            cv.rect(tx, ty, tx + 30, ty + 3, wood[4])
            cv.hline(tx, tx + 30, ty, wood[5])
            for lx in (tx + 2, tx + 26):
                cv.rect(lx, ty + 3, lx + 2, ty + 16, wood[3])
        else:
            cv.rect(tx, ty + 6, tx + 12, ty + 8, wood[4])
            cv.rect(tx, ty - 6, tx + 2, ty + 18, wood[3])
            cv.rect(tx + 10, ty + 8, tx + 12, ty + 18, wood[3])
        for rx in (tx + 3, tx + (24 if kind == "table" else 9)):
            cv.vline(rx, WH_CEIL, ty, rope)
        cv.hline(tx - 1, tx + (31 if kind == "table" else 13), ty + 1, rope)
    # 抽屉都朝同一个方向敞着（原文 111）：靠后墙一排柜子，每只抽屉都往右拉出来一截
    for cx0 in (70, 150):
        cv.rect(cx0, 150, cx0 + 60, WH_G, wood[3])
        cv.hline(cx0, cx0 + 60, 150, wood[5])
        cv.vline(cx0, 150, WH_G, wood[4])
        for k, dy in enumerate(range(156, WH_G - 6, 14)):
            for col in range(2):
                dx = cx0 + 3 + col * 29
                cv.rect(dx, dy, dx + 26, dy + 11, wood[2])
                cv.rect(dx + 6, dy - 2, dx + 34, dy + 9, wood[4])          # 拉出来的那截（都往右）
                cv.hline(dx + 6, dx + 34, dy - 2, wood[5])
                cv.rect(dx + 7, dy - 1, dx + 33, dy + 2, C(0.14, 0.02, H_WATER))
                cv.rect(dx + 28, dy + 3, dx + 31, dy + 5, wood[1])
    # 一排贴着圆圆的字的箱子（原文 111：「借来的」「还不知道是谁的，先放好」）
    for (bx, by, bw, bh) in ((316, 204, 30, 32), (346, 210, 26, 26), (372, 200, 32, 36), (404, 212, 24, 24),
                             (428, 206, 28, 30), (324, 176, 24, 28), (378, 174, 26, 26)):
        cv.rect(bx, by, bx + bw, by + bh, wood[3])
        cv.hline(bx, bx + bw, by, wood[5])
        cv.vline(bx, by, by + bh, wood[4])
        cv.vline(bx + bw - 1, by, by + bh, wood[1])
        for yy in range(by + 6, by + bh, 7):
            cv.hline(bx + 1, bx + bw - 1, yy, wood[2])
        lx, ly = bx + 4, by + 4
        cv.rect(lx, ly, lx + 14, ly + 7, mix(PAPER, wood[3], 0.3))
        for j in range(4):                                             # 圆圆的字：一个个小圈
            cv.px(lx + 2 + j * 3, ly + 3, wood[1])
            cv.px(lx + 2 + j * 3, ly + 2, mix(PAPER, wood[1], 0.5))
    # 设备柜（内门那边，原文 112–113）：一排贴标签的小抽屉
    met = stone(0.32, 0.016, HUE - 30)
    ex = 576
    cv.rect(ex, 120, ex + 46, WH_G, met[3])
    cv.hline(ex, ex + 46, 120, met[5])
    cv.vline(ex, 120, WH_G, met[4])
    cv.vline(ex + 45, 120, WH_G, met[1])
    for dy in range(126, WH_G - 8, 12):
        for col in range(3):
            dx = ex + 3 + col * 14
            cv.rect(dx, dy, dx + 12, dy + 10, met[2])
            cv.rect(dx + 2, dy + 2, dx + 10, dy + 5, mix(PAPER, met[3], 0.45))
            cv.px(dx + 6, dy + 7, met[5])
    return cv


def warehouse_objects(r: Room):
    wood = stone(0.3, 0.025, 60)
    met = stone(0.34, 0.016, HUE - 30)
    # 出口灯（原文 112）：入口上面一盏，慢慢一明一暗
    fr = []
    for k in range(2):
        cv = Cv(16, 8)
        cv.rect(0, 0, 16, 8, met[2])
        cv.rect(2, 2, 14, 6, C(0.62 if k == 0 else 0.5, 0.06, H_GLINT - 30))
        cv.rect(4, 3, 8, 5, C(0.4, 0.04, H_GLINT - 30))
        fr.append(cv)
    r.obj("warehouse_exit_light", fr, 25, 134, {"default": [0, 1], "on": [0, 1]}, ms=900)
    # 破箱子（原文 111）：default = 破了一角；spilled = 纽扣、空瓶、褪色照片散在柜底
    fr = []
    for k in range(2):
        cv = Cv(48, 24)
        cv.rect(2, 4, 30, 24, wood[3])
        cv.hline(2, 30, 4, wood[5])
        cv.poly([(22, 4), (30, 4), (30, 14)], C(0.12, 0.02, H_WATER))
        cv.rect(6, 8, 18, 13, mix(PAPER, wood[3], 0.3))
        if k == 1:
            for (bx, by, c) in ((32, 21, C(0.5, 0.05, H_WARM)), (36, 22, C(0.44, 0.02, HUE)), (41, 21, AMBER),
                                (45, 22, C(0.44, 0.02, HUE))):
                cv.rect(bx, by, bx + 2, by + 2, c)
            cv.rect(33, 16, 36, 22, C(0.42, 0.03, H_GLINT))           # 空瓶
            cv.px(34, 15, C(0.42, 0.03, H_GLINT))
            cv.rect(38, 18, 46, 21, C(0.48, 0.02, 80))                # 褪色照片（一张夹在硬套里）
            cv.hline(38, 46, 18, C(0.56, 0.02, 80))
        fr.append(cv)
    r.obj("warehouse_broken_box", fr, 262, WH_G - 24, {"default": 0, "spilled": 1})
    # 倒下的高柜（原文 112「利用浮箱改变柜子的受力位置」）：warehouse_tall_cabinet。fallen = 一头压在堵门的家具上、斜着；
    # lifted = 浮箱把柜顶那头吊起来、放平离开家具。柜顶拴环在右上（对的点），柜脚拴环在左下。
    CAB_X, CAB_W, CAB_H = 470, 68, 64
    fr = []
    for k in range(2):
        cv = Cv(CAB_W, CAB_H)
        if k == 0:
            cv.poly([(2, 44), (60, 12), (66, 26), (8, 60)], wood[3])
            cv.line([(2, 44), (60, 12)], wood[5])
            cv.line([(10, 52), (58, 25)], wood[2])
            cv.line([(30, 46), (24, 36)], wood[2])
            cv.rect(58, 12, 62, 15, met[5])                      # 柜顶拴环
            cv.rect(6, 54, 10, 57, met[5])                       # 柜脚拴环
        else:
            cv.rect(6, 10, 64, 40, wood[3])
            cv.hline(6, 64, 10, wood[5])
            cv.hline(7, 63, 25, wood[2])
            cv.vline(35, 11, 40, wood[2])
            cv.rect(60, 7, 64, 10, met[5])
            cv.rect(6, 40, 10, 43, met[5])
        fr.append(cv)
    r.obj("warehouse_tall_cabinet", fr, CAB_X, WH_G - CAB_H, {"default": 0, "fallen": 0, "lifted": 1})
    r.markers["warehouse_cabinet_top"] = CAB_X + 60
    r.markers["warehouse_cabinet_foot"] = CAB_X + 8
    # 浮箱：idle = 搁在柜子左边的地上；tied_warehouse_cabinet_top = 拴在柜顶、浮到上面把那头吊起来；
    # tied_warehouse_cabinet_foot = 拴错在柜脚（浮在柜脚上面，绳子绷着，柜子不动）
    FX = 430
    fr = []
    for k in range(3):
        cv = Cv(CAB_X + CAB_W - FX + 4, 80)
        if k == 0:
            bx, by = 2, 66
        elif k == 1:
            bx, by = CAB_X + 56 - FX - 8, 8
        else:
            bx, by = CAB_X + 6 - FX - 8, 26
        cv.rect(bx, by, bx + 20, by + 12, C(0.4, 0.05, H_WARM - 20))
        cv.hline(bx, bx + 20, by, C(0.5, 0.05, H_WARM - 20))
        cv.vline(bx + 19, by, by + 12, C(0.32, 0.04, H_WARM - 20))
        cv.hline(bx, bx + 20, by + 6, C(0.34, 0.04, H_WARM - 20))
        if k == 1:
            cv.vline(bx + 10, by + 12, 80 - CAB_H + 7 + 2, C(0.38, 0.03, 70))
        if k == 2:
            cv.vline(bx + 10, by + 12, 80 - 10, C(0.38, 0.03, 70))
        fr.append(cv)
    r.obj("warehouse_float", fr, FX, WH_G - 80, {"default": 0, "idle": 0, "tied_warehouse_cabinet_top": 1,
                                                  "tied_warehouse_cabinet_foot": 2})
    # 堵住内门的家具：pinned = 被柜子压着、斜顶在门上；loose = 柜子吊起来以后松了一点；moved = 拉开靠到一边
    fr = []
    for k in range(3):
        cv = Cv(40, 44)
        if k < 2:
            d = k * 2
            cv.poly([(4 - d, 44), (12 - d, 44), (38 - d, 6 + d), (32 - d, 2 + d)], wood[2])
            cv.rect(0, 30, 26, 44, wood[3])
            cv.hline(0, 26, 30, wood[5])
        else:
            cv.rect(0, 22, 16, 44, wood[3])
            cv.hline(0, 16, 22, wood[5])
            cv.rect(2, 4, 6, 22, wood[2])
        fr.append(cv)
    r.obj("warehouse_furniture", fr, WH_DOOR - 38, WH_G - 44, {"default": 0, "pinned": 0, "loose": 1, "moved": 2})
    fr = []
    for k in range(2):
        cv = Cv(12, 60)
        if k == 0:
            cv.rect(0, 0, 12, 60, met[3])
            cv.vline(0, 0, 60, met[4])
            cv.rect(8, 30, 10, 34, met[5])
        fr.append(cv)
    r.obj("warehouse_inner_door", fr, WH_DOOR - 6, WH_G - 60, {"default": 0, "closed": 0, "open": 1})
    # 旧泄水门（原文 113）：一扇圆角铁门，门边挂着操作记录（下面压着手绘图）；taken = 记录取下来了
    fr = []
    for k in range(2):
        cv = Cv(64, 100)
        cv.rect(14, 10, 60, 100, met[2])
        cv.rect(16, 12, 58, 100, met[3])
        cv.hline(16, 58, 12, met[5])
        for yy in range(20, 100, 14):
            cv.hline(16, 58, yy, met[2])
            for xx in range(18, 58, 8):
                cv.px(xx, yy + 1, met[4])
        cv.ellipse(37, 54, 9, 9, met[1])
        cv.ellipse(37, 54, 7, 7, met[4])
        cv.line([(31, 54), (43, 54)], met[2])
        cv.line([(37, 48), (37, 60)], met[2])
        if k == 0:
            cv.vline(6, 30, 36, C(0.3, 0.01, HUE))
            cv.rect(1, 36, 12, 52, mix(PAPER, met[3], 0.35))
            for yy in range(39, 50, 2):
                cv.hline(3, 10, yy, met[2])
            cv.rect(2, 50, 12, 56, mix(PAPER, met[3], 0.5))              # 下面压着的手绘图露出一角
        fr.append(cv)
    r.obj("warehouse_sluice_door", fr, 640, WH_G - 100, {"default": 0, "log": 0, "signatures": 0, "taken": 1})


def warehouse():
    r = Room("warehouse", WH_W, env="underwater")
    rng = np.random.default_rng(5001)
    r.ground = WH_G
    r.extra["bg"] = ["#16242b", "#0d161b"]
    r.layer("back", wh_back(), 0.3, 0)
    main = warehouse_main(rng)
    # 整间屋都在水里：往水色里推（越往下越暗），高窗那一带亮一点
    underwater_tint(main, 0, SH, L_surf=0.3, L_deep=0.13, t0=0.4, t1=0.62)
    caustics(main, 0, WH_W, WH_CEIL + 4, WH_G, rng, n=90, L_add=0.04)
    r.layer("main", main, 1.0, 0)
    r.layer("shafts", sun_shafts(WH_W, 5601, x_every=(110, 190), slope=0.3), 1.0, 0, alpha=0.06, z=-15)
    fr = Cv(r.need_w(1.2), SH)
    dark = stone(0.1, 0.02, H_WATER, dL=0.02)
    for x in range(30, fr.w, 170):                                      # 前景：几缕从上面垂下来的水草 / 断绳
        ln = int(rng.integers(20, 60))
        for y in range(0, ln):
            fr.px(x + int(2 * math.sin(y / 7)), y, dark[3])
            fr.px(x + 1 + int(2 * math.sin(y / 7)), y, dark[3])
    r.layer("front", fr, 1.2, 0, front=True)
    warehouse_objects(r)
    for oid, (spec, frames) in r.objects.items():                       # 物件也泡在水里（出口灯除外：它自己亮）
        if oid == "warehouse_exit_light":
            continue
        for f in frames:
            fog(f, lambda y: 0.42, lambda y: C(0.22, 0.032, H_WATER + 4), steps=12)
    r.markers.update({"warehouse_entry": 40, "warehouse_niff": 70, "warehouse_rope": 40, "warehouse_boxes": 380,
                      "warehouse_broken_box": 286, "warehouse_float": 440, "warehouse_tall_cabinet": 504,
                      "warehouse_furniture": WH_DOOR - 20, "warehouse_inner_door": WH_DOOR,
                      "warehouse_cabinet": 598, "warehouse_sluice_door": 660, "warehouse_exit_light": 33,
                      "warehouse_knot_1": 230, "warehouse_knot_2": 420})
    r.extra["walk"] = [24, WH_W - 30]
    r.extra["rope"] = {"prop": "warehouse_rope", "on": "on", "anchor": [33, 150], "end": WH_W - 34,
                       "color": "#8e9a98", "knots": [230, 420]}
    r.extra["portals"] = [{"to": "oldstreet", "at": "oldstreet_warehouse_entry", "kind": "pan_up", "x": 33}]
    r.extra["ambient"] = [{"name": "underwater", "db": -8}]
    r.extra["scripts"] = [{"script": "res://scripts/underwater_motes.gd", "x": 0, "y": 0, "z": -12,
                           "params": {"count": 40, "area": [0, 40, WH_W, 190]}}]
    return r


# ============================================================ 南桥 + 货台 southbridge

SB_W = 1500
S_G, S_WL, S_HIGH = 228, 248, 132          # 泥滩（退水后晨走的地方）、现在的水面、影像里的高水位（墙上一道水印）
S_DECK = (66, 84)                          # 桥面（上沿、下沿）
S_PIERS = [(150, 190), (430, 470), (710, 750), (950, 990)]
S_ARCHES = [(190, 430), (470, 710), (750, 950)]    # 第 2 个（中间）是对的那个桥洞
S_WATERWAY = (1060, 1140)
S_DOCK = (1180, SB_W)
S_DOCK_Y = 196


PLATES_X = (1420, 1440, 1460)
DIGITS = {"0": ["###", "#.#", "#.#", "#.#", "###"], "1": [".#.", "##.", ".#.", ".#.", "###"],
          "2": ["###", "..#", "###", "#..", "###"], "7": ["###", "..#", ".#.", ".#.", ".#."]}


def sb_ground():
    return [[0, 212], [60, 212], [120, S_G], [S_DOCK[0] + 6, S_G], [S_DOCK[0] + 14, 220], [S_DOCK[0] + 22, 212],
            [S_DOCK[0] + 30, 204], [S_DOCK[0] + 38, S_DOCK_Y], [SB_W, S_DOCK_Y]]


def southbridge_main(rng):
    W = SB_W
    cv = Cv(W, SH)
    bst = stone(0.31, 0.014, HUE - 26)
    # ---- 桥：桥面 + 桥墩 + 拱（拱洞是空的，透出后面的层）
    course_wall(cv, 130, 1010, S_DECK[0], S_DECK[1] + 20, bst, rng, course=6, block=(14, 30))
    for (x0, x1) in S_PIERS:
        course_wall(cv, x0, x1, S_DECK[1], S_G + 6, bst, rng, course=7, block=(10, 20), lit_top=False)
        cv.vline(x0, S_DECK[1], S_G, bst[5])
        cv.vline(x1 - 1, S_DECK[1], S_G, bst[1])
    for (a, b) in S_ARCHES:
        cx, r = (a + b) / 2, (b - a) / 2
        # 拱肩（拱和桥面之间的墙）
        Y, X = np.mgrid[0:SH, 0:W]
        spring = S_DECK[1] + 20 + int(r * 0.55)
        hole = (((X - cx) / r) ** 2 + ((Y - spring) / (r * 0.55 + 1)) ** 2 < 1) & (Y >= S_DECK[1]) | \
               ((X > a) & (X < b) & (Y >= spring))
        wall = (X >= a) & (X < b) & (Y >= S_DECK[1]) & (Y < S_G + 6) & ~hole
        cv.mask(wall, bst[3])
        cv.a[hole & (Y < S_G + 6)] = 0
        # 拱圈：一圈楔石（亮一档）
        ring = (((X - cx) / (r + 6)) ** 2 + ((Y - spring) / (r * 0.55 + 7)) ** 2 < 1) & ~hole & (Y < spring + 1) & wall
        cv.mask(ring, bst[5])
        inner = (((X - cx) / (r + 2)) ** 2 + ((Y - spring) / (r * 0.55 + 3)) ** 2 < 1) & ring
        cv.mask(inner, bst[4])
        for k in range(6, 180, 10):                                     # 楔石的缝
            t = math.radians(k)
            for d in range(0, 7):
                x0 = cx - (r + 0.5 + d) * math.cos(t)
                y0 = spring - (r * 0.55 + 1 + d) * math.sin(t)
                if 0 <= int(y0) < SH and ring[int(y0), int(x0)]:
                    cv.px(int(x0), int(y0), bst[2])
        # 拱洞里：桥身的背面（暗）只露上沿一窄条，看得出是个洞
        under = hole & (Y < spring - int(r * 0.55) + 6)
        cv.mask(under, bst[1])
        # 石沿（拱脚那一道出挑的石条，原文 138「石沿上缠着几根粗硬的毛」）
        cv.rect(a - 4, spring, a + 6, spring + 3, bst[5])
        cv.rect(b - 6, spring, b + 4, spring + 3, bst[5])
    # 旧的高水位：桥墩、桥身上一道水印（影像里水比现在高得多，原文 136）
    for x in range(130, 1010):
        if cv.a[S_HIGH, x, 3]:
            cv.px(x, S_HIGH, C(0.24, 0.016, H_MOSS + 40))
            if cv.a[S_HIGH + 1, x, 3]:
                cv.px(x, S_HIGH + 1, C(0.27, 0.014, H_MOSS + 40))
    shade = np.zeros((SH, W), bool)
    shade[S_HIGH + 2:S_G] = True
    shade &= cv.a[..., 3] > 0
    shade_mask(cv, shade, -0.03, 0.004, 40)
    # 对的那个桥洞里很高的擦痕（原文 138）：右边桥墩的内侧、高过人头很多
    a, b = S_ARCHES[1]
    for (sx, sy, ln) in ((b - 2, 112, 14), (b - 4, 118, 18), (b - 1, 126, 12), (a + 2, 120, 10)):
        cv.line([(sx, sy), (sx + (3 if sx > a + 10 else -3), sy + ln)], C(0.4, 0.012, HUE - 30))
    # 桥面上：栏杆、灯柱（原文 136「先照着画面寻找灯柱」）、垂下来的浮灯缆绳
    railing(cv, 130, 1010, S_DECK[0] - 9, S_DECK[0], bst[5], bst[3], step=8)
    lamp = stone(0.3, 0.012, HUE)
    for lx in (230, 520, 800):
        cv.rect(lx, S_DECK[0] - 44, lx + 3, S_DECK[0], lamp[3])
        cv.vline(lx, S_DECK[0] - 44, S_DECK[0], lamp[5])
        cv.rect(lx - 3, S_DECK[0] - 52, lx + 6, S_DECK[0] - 44, lamp[2])
        cv.rect(lx - 2, S_DECK[0] - 50, lx + 5, S_DECK[0] - 46, C(0.36, 0.02, H_GLINT))
        cv.hline(lx - 4, lx + 7, S_DECK[0] - 53, lamp[5])
        cv.rect(lx - 2, S_DECK[0] - 2, lx + 5, S_DECK[0], lamp[4])
    for (x0, x1, sag) in ((200, 420, 26), (480, 700, 34), (760, 940, 22)):     # 拴浮灯的缆绳，退水后垂下来
        n = x1 - x0
        for i in range(n + 1):
            yy = S_DECK[1] + 2 + int(sag * math.sin(math.pi * i / n))
            cv.px(x0 + i, yy, C(0.34, 0.02, 70))
        for i in range(14, n - 10, 30):                                        # 浮灯：一个个灯笼形的浮子
            yy = S_DECK[1] + 3 + int(sag * math.sin(math.pi * i / n))
            cv.rect(x0 + i - 2, yy, x0 + i + 3, yy + 6, C(0.38, 0.04, H_WARM - 20))
            cv.hline(x0 + i - 2, x0 + i + 3, yy, C(0.46, 0.05, H_WARM - 20))
            cv.px(x0 + i, yy + 6, C(0.3, 0.02, 70))
    # ---- 桥那头：退水后露出来的矮房子，屋脊上一排装饰（原文 136「原先像栏杆的东西，原来是屋顶上的装饰」）
    hst = stone(0.27, 0.014, HUE - 10)
    for (x0, x1, top) in ((990, 1060, 150), (1140, 1180, 160)):
        cv.rect(x0, top, x1, S_G + 4, hst[3])
        cv.vline(x0, top, S_G, hst[5])
        cv.hline(x0, x1, top, hst[5])
        for yy in range(top + 14, S_G, 18):
            window(cv, x0 + 10, yy, 8, 9, hst, rng)
        for fx in range(x0 + 4, x1 - 2, 7):                                    # 屋脊上的装饰：一排小尖柱（像栏杆）
            cv.rect(fx, top - 9, fx + 2, top, hst[4])
            cv.px(fx, top - 10, hst[5])
            cv.px(fx + 1, top - 11, hst[5])
        cv.hline(x0, x1, top - 3, hst[4])
        # 苔：整栋房子到屋顶都泡过
        moss_line(cv, x0, x1, top + 2, rng, depth=2, L=0.22, seed=x0)
    # ---- 旧运输水道（原文 137）：挡土墙上一个拱口；露出前被淤泥和垂下来的水草挡着（物件 southbridge_waterway）
    course_wall(cv, S_WATERWAY[0] - 10, S_DOCK[0], 120, S_G + 6, bst, rng, course=7, block=(12, 26))
    cv.rect(S_WATERWAY[0], 160, S_WATERWAY[1], S_G + 6, C(0.1, 0.012, HUE + 4))
    cv.ellipse((S_WATERWAY[0] + S_WATERWAY[1]) / 2, 162, (S_WATERWAY[1] - S_WATERWAY[0]) / 2, 14, C(0.1, 0.012, HUE + 4))
    cv.rect(S_WATERWAY[0] - 3, 150, S_WATERWAY[1] + 3, 152, bst[5])
    # ---- 货台（原文 139–140）：高出泥滩的一块平台 + 台阶；后墙上航线图掉了只剩印子、几块编号牌、旧装卸记录
    dk = stone(0.3, 0.02, 64)
    course_wall(cv, S_DOCK[0], W, 70, S_DOCK_Y, bst, rng, course=8, block=(16, 32))
    cv.rect(S_DOCK[0] + 38, S_DOCK_Y, W, SH, dk[3])
    cv.hline(S_DOCK[0] + 38, W, S_DOCK_Y, dk[5])
    for x in range(S_DOCK[0] + 38, W, 12):
        cv.vline(x, S_DOCK_Y + 1, S_DOCK_Y + 6, dk[2])
    cv.hline(S_DOCK[0] + 38, W, S_DOCK_Y + 6, dk[1])
    for i, (x0, y) in enumerate(((S_DOCK[0] + 6, 220), (S_DOCK[0] + 14, 212), (S_DOCK[0] + 22, 204),
                                 (S_DOCK[0] + 30, S_DOCK_Y + 0))):
        cv.rect(x0, y, S_DOCK[0] + 38, SH, bst[3 + (i % 2)])
        cv.hline(x0, S_DOCK[0] + 38, y, bst[6])
    # 航线图：墙上一大块颜色浅一点的印子（图掉了），四角的钉子还在
    mx0, my0, mx1, my1 = 1300, 96, 1400, 150
    cv.rect(mx0, my0, mx1, my1, mix(bst[3], bst[5], 0.4))
    for (x, y) in ((mx0 + 1, my0 + 1), (mx1 - 2, my0 + 1), (mx0 + 1, my1 - 2), (mx1 - 2, my1 - 2)):
        cv.rect(x, y, x + 2, y + 2, C(0.22, 0.01, HUE))
    cv.line([(mx0 + 10, my0 + 30), (mx0 + 40, my0 + 18), (mx0 + 72, my0 + 26), (mx1 - 8, my0 + 10)],
            mix(bst[3], bst[5], 0.7))                                         # 底下透出来一点航线的印子
    # 几块编号牌（原文 139）：航线图旁边一排小铁牌，07 / 12 / 21（会话 B 的编号；12 是去云层星那班）
    for num, px_ in zip(("07", "12", "21"), PLATES_X):
        cv.rect(px_, 104, px_ + 14, 114, C(0.4, 0.016, HUE - 30))
        cv.hline(px_, px_ + 14, 104, C(0.48, 0.016, HUE - 30))
        cv.px(px_ + 1, 105, C(0.24, 0.01, HUE))
        cv.px(px_ + 12, 105, C(0.24, 0.01, HUE))
        for j, ch in enumerate(num):
            for yy, row in enumerate(DIGITS[ch]):
                for xx, b in enumerate(row):
                    if b == "#":
                        cv.px(px_ + 3 + j * 5 + xx, 106 + yy, C(0.2, 0.01, HUE))
    # 旧装卸记录：墙上一个铁皮夹板
    cv.rect(1250, 120, 1274, 152, C(0.3, 0.012, HUE - 30))
    cv.rect(1252, 124, 1272, 150, mix(PAPER, bst[3], 0.45))
    for yy in range(127, 148, 3):
        cv.hline(1254, 1270, yy, mix(PAPER, bst[1], 0.6))
    cv.rect(1258, 118, 1266, 122, C(0.4, 0.016, HUE - 30))
    # 货台上的东西：系船桩、一段坡板、吊钩
    for bx in (1340, 1460):
        cv.rect(bx, S_DOCK_Y - 8, bx + 8, S_DOCK_Y, C(0.27, 0.012, HUE))
        cv.rect(bx - 1, S_DOCK_Y - 10, bx + 9, S_DOCK_Y - 8, C(0.33, 0.012, HUE))
    cv.line([(1380, S_DOCK_Y), (1430, S_DOCK_Y - 14)], dk[4], width=2)
    cv.vline(1480, 70, 120, C(0.3, 0.01, HUE))
    cv.rect(1476, 120, 1484, 126, C(0.32, 0.01, HUE))
    # ---- 泥滩（退水后）：一条暗的湿泥，表面一道湿亮的边；下面一窄条水
    mud = stone(0.24, 0.02, 60)
    for x in range(0, S_DOCK[0] + 6):
        gy = int(round(np.interp(x, [0, 60, 120, S_DOCK[0]], [212, 212, S_G, S_G])))
        cv.vline(x, gy, SH, mud[3])
        cv.px(x, gy, C(0.38, 0.02, H_WATER))
        cv.px(x, gy + 1, mud[4])
    for _ in range(260):
        x, y = int(rng.integers(0, S_DOCK[0])), int(rng.integers(S_G + 2, S_WL))
        cv.hline(x, x + int(rng.integers(2, 6)), y, mud[int(rng.integers(1, 5))])
    cv.rect(0, 200, 60, 212, mud[2])
    course_wall(cv, 0, 60, 196, 212, bst, rng, course=6)
    return cv


def footprint_frames():
    """southbridge_footprints：泥滩上一串连续的大脚印（原文 138）。default = 不注意看不出来；seen = 边上一圈湿亮、看得清。"""
    out = []
    for k in range(2):
        cv = Cv(150, 14)
        for i, x in enumerate(range(6, 146, 34)):
            y = 4 + (i % 2) * 3
            dark = C(0.17, 0.02, 60)
            cv.ellipse(x + 8, y + 3, 9, 3, dark if k else C(0.21, 0.02, 60))
            if k:
                cv.hline(x + 1, x + 15, y, C(0.38, 0.02, H_WATER))
                for t in range(3):                                         # 趾印
                    cv.px(x + 3 + t * 5, y - 1, C(0.3, 0.02, H_WATER))
        out.append(cv)
    return out


def arch_frames():
    """southbridge_arch：对的那个桥洞。scratches = 擦痕看清楚了 + 石沿上缠着几根粗硬的毛（原文 138）。"""
    a, b = S_ARCHES[1]
    out = []
    for k in range(2):
        cv = Cv(30, 70)
        if k:
            for (sx, sy, ln) in ((24, 8, 14), (22, 14, 18), (26, 22, 12)):
                cv.line([(sx, sy), (sx + 3, sy + ln)], C(0.48, 0.014, HUE - 30))
            hair = C(0.44, 0.012, 60)
            for (hx, hy) in ((10, 62), (14, 61), (17, 63), (21, 62)):
                cv.line([(hx, hy), (hx + 3, hy + 4)], hair)
                cv.px(hx + 4, hy + 5, hair)
        out.append(cv)
    return out


def waterway_frames():
    """southbridge_waterway：旧运输水道的入口。default = 被淤泥和垂下来的水草、烂木板挡着，看着就是墙；revealed = 露出来，里面一条暗水道。"""
    w, h = S_WATERWAY[1] - S_WATERWAY[0] + 8, S_G + 6 - 146
    out = []
    mud = stone(0.25, 0.02, 60)
    for k in range(2):
        cv = Cv(w, h)
        if k == 0:
            cv.rect(4, 8, w - 4, h, mud[3])
            for x in range(4, w - 4, 3):
                ln = 10 + (x * 7) % 23
                cv.vline(x, 8, 8 + ln, C(0.22, 0.02, H_MOSS + 30))
            for (px_, py) in ((10, 40), (30, 52), (50, 36)):
                cv.rect(px_, py, px_ + 22, py + 4, C(0.3, 0.025, 62))
                cv.hline(px_, px_ + 22, py, C(0.36, 0.025, 62))
            cv.hline(4, w - 4, 8, mud[5])
        else:
            cv.rect(6, h - 14, w - 6, h, C(0.3, 0.03, H_WATER))
            cv.hline(6, w - 6, h - 14, C(0.46, 0.03, H_GLINT))
            for x in range(10, w - 10, 9):
                cv.hline(x, x + 4, h - 10 + (x % 3), C(0.4, 0.03, H_GLINT))
            for x in range(4, w - 4, 6):
                cv.vline(x, 8, 12 + (x * 5) % 9, C(0.2, 0.02, H_MOSS + 30))
        out.append(cv)
    return out


def routemap_frames():
    """southbridge_routemap：default = 航线图歪挂着只剩一个角；fallen = 整张掉在货台上（原文 139「墙上的航线图已经脱落」）。"""
    out = []
    paper = mix(PAPER, C(0.3, 0.01, HUE), 0.5)
    for k in range(2):
        cv = Cv(110, 110)
        if k == 0:
            cv.poly([(4, 2), (60, 6), (52, 56), (2, 50)], paper)
            cv.line([(10, 30), (30, 20), (50, 26)], C(0.3, 0.02, 30))
        else:
            cv.rect(8, 104, 70, 108, paper)
            cv.hline(8, 70, 104, mix(paper, C(0.6, 0.01, 80), 0.3))
        out.append(cv)
    return out


def southbridge():
    r = Room("southbridge", SB_W)
    rng = np.random.default_rng(6001)
    r.ground = sb_ground()
    r.shared("sky", 0.0, 0)
    r.shared("far", 0.15, FAR_WL - FAR_ROW_WL)
    r.shared("midfar", 0.35, MIDFAR_WL - MIDFAR_ROW_WL + 8)
    r.layer("mid", mid_strip("southbridge", r.need_w(0.6), 6401, 200, top_rng=(60, 140)), 0.6, 0)
    main = southbridge_main(rng)
    r.layer("main", main, 1.0, 0)
    r.layer("shafts", sun_shafts(SB_W, 6601), 1.0, 0, alpha=0.07, z=-15)
    wb = water_body(SB_W, S_WL, SH, L0=0.36, L1=0.24)
    r.layer("water", wb, 1.0, S_WL, water=True, front=True, alpha=0.7)
    rp, ry = ripples(SB_W, [(S_WL, 12, 0.3)], 6501)
    r.layer("ripples", rp, 1.0, ry, front=True, shader="water", shader_params={"palette_mode": False, "show": 0.7})
    r.layer("front", front_bank(r.need_w(1.3), rng), 1.3, 0, front=True)
    a, b = S_ARCHES[1]
    r.obj("southbridge_arch", arch_frames(), b - 28, 104, {"default": 0, "scratches": 1})
    r.obj("southbridge_footprints", footprint_frames(), 520, S_G + 1, {"default": 0, "seen": 1})
    wf = waterway_frames()
    r.obj("southbridge_waterway", wf, S_WATERWAY[0] - 4, 146, {"default": 0, "revealed": 1})
    r.obj("southbridge_routemap", routemap_frames(), 1296, 90, {"default": 0, "fallen": 1})
    r.markers = {"southbridge_entry": 24, "southbridge_back": 14, "southbridge_niff": 60, "southbridge_lamp_post": 522,
                 "southbridge_ornament": 1024, "southbridge_arch_wrong": 310, "southbridge_arch": 590,
                 "southbridge_footprints": 596, "southbridge_waterway": 1100, "southbridge_dock": 1262,
                 "southbridge_routemap": 1350, "southbridge_dock_step": S_DOCK[0] + 30, "southbridge_plates": 1450,
                 "southbridge_arch_far": (S_ARCHES[2][0] + S_ARCHES[2][1]) // 2, "southbridge_view_spot": VF_CAM + 240,
                 "southbridge_plate_07": PLATES_X[0] + 7, "southbridge_plate_12": PLATES_X[1] + 7,
                 "southbridge_plate_21": PLATES_X[2] + 7}
    r.extra["walk"] = [12, SB_W - 14]
    r.extra["walk_when"] = [{"not": ["river_waterway_open"], "walk": [12, S_WATERWAY[0] - 6]}]
    r.extra["portals"] = [{"edge": "left", "to": "oldstreet", "at": "oldstreet_to_south", "kind": "walk_fade"}]
    r.extra["ambient"] = [{"name": "river_flow", "db": -14}]
    # 还原拍摄位置（原文 137，第 4.5 节）：镜头左边缘在这个 x 时，影像里的桥洞、灯柱、浮灯和现在对上
    r.extra["viewfinder"] = {"img": "viewfinder.png", "cam_x": VF_CAM, "chen_x": VF_CAM + 240,
                             "note": "镜头左边缘 = cam_x 时对齐；取景框不跟镜头（CanvasLayer），alpha 自己定（建议 0.45）"}
    return r


VF_CAM = 352      # 取景框的拍摄位置：镜头左边缘（对的那个桥洞在画面中间偏左，灯柱在右）


def viewfinder(r: Room):
    """取景框（第 4.5 节，工具出图）：南桥的视差层在拍摄位置渲染一张，水位抬到影像里那么高、浮灯往一边歪、
    桥洞里一团灰影（大象的长鼻搭在石沿上，原文 97），加影像颗粒、压暗、偏冷。引擎半透明叠在屏幕上（不跟镜头）。"""
    base = render(r, VF_CAM, {}, None)
    cv = Cv(SW, SH)
    cv.a[..., :3] = base
    cv.a[..., 3] = 255
    # 高水位：从 S_HIGH 往下全是水（影像里的桥半淹在水里）
    wl = S_HIGH
    sub = np.zeros((SH, SW), bool)
    sub[wl:] = True
    fog(cv, lambda y: 0.0 if y < wl else 0.6, lambda y: C(0.3, 0.03, H_WATER), steps=10, m=sub)
    cv.hline(0, SW, wl, C(0.5, 0.02, H_GLINT))
    # 浮灯：被托起来，整排往右歪（原文 97、124）
    for i, x in enumerate(range(40, SW, 46)):
        y = wl - 4 - (i % 3)
        cv.rect(x, y, x + 5, y + 6, C(0.5, 0.05, H_WARM - 20))
        cv.line([(x + 2, y), (x + 6, y - 5)], C(0.36, 0.02, 70))
    # 灰影：桥洞里雾中靠过来的一团（原文 97、124）：背脊和头露出水面，宽大的耳朵边上一道缺口，
    # 长鼻从水里探出来搭到桥墩的石沿上；水面以下只隐约一团（和雾几乎一个颜色，第二眼才看得出）
    a, b = S_ARCHES[1]
    cx = (a + b) // 2 - VF_CAM + 14
    Y, X = np.mgrid[0:SH, 0:SW]
    shadow, shadow_w = C(0.27, 0.006, HUE), C(0.27, 0.02, H_WATER)
    back = ((X - cx) / 46) ** 2 + ((Y - wl - 4) / 20) ** 2 < 1
    head = ((X - cx + 40) / 15) ** 2 + ((Y - wl + 6) / 13) ** 2 < 1
    ear = (((X - cx + 26) / 13) ** 2 + ((Y - wl + 4) / 17) ** 2 < 1)
    notch = ((X - cx + 33) ** 2 + (Y - wl - 9) ** 2) < 10
    m = (back | head | ear) & ~notch
    cv.mask(m & (Y <= wl), shadow)
    under = m & (Y > wl) & ((X + Y) % 2 == 0)
    cv.mask(under, shadow_w)
    trunk = [(cx - 50, wl - 2), (cx - 58, wl + 2), (cx - 64, wl), (cx - 70, wl - 5), (a - VF_CAM + 3, wl - 4)]
    cv.line(trunk, shadow, width=2)
    # 雾：上半部分一层灰
    fog(cv, lambda y: 0.35 if y < wl else 0.2, lambda y: C(0.4, 0.008, HUE), steps=10)
    # 颗粒 + 横扫描线（整像素、硬边：一半的行压暗一档，随机几颗亮点）
    rng = np.random.default_rng(7001)
    m = np.zeros((SH, SW), bool)
    m[::3] = True
    shade_mask(cv, m, -0.03)
    for _ in range(900):
        x, y = int(rng.integers(0, SW)), int(rng.integers(0, SH))
        cv.px(x, y, C(rng.uniform(0.3, 0.5), 0.006, HUE))
    # 取景框的四个角
    fc = C(0.7, 0.01, HUE)
    for (x, y, dx, dy) in ((8, 8, 1, 1), (SW - 9, 8, -1, 1), (8, SH - 9, 1, -1), (SW - 9, SH - 9, -1, -1)):
        cv.hline(min(x, x + 14 * dx), max(x, x + 14 * dx) + 1, y, fc)
        cv.vline(x, min(y, y + 10 * dy), max(y, y + 10 * dy) + 1, fc)
    return cv


# ============================================================ 联系表：每个房间几屏（叠好 + 晨站在里面）+ 原文写到的东西画在哪

NOTES = {
    "river_bank": [
        "原文 72 卡进狭窄水道、木箱漂过：x 0–330 窄水道，后墙一直下到水里（=飞行一最后一格那面墙），物件 river_bank_crate_float",
        "原文 74 岸边一排箱子、只露尾巴：物件 river_bank_crates x≈420（尾巴是占位色块，等美术组）",
        "原文 75 台阶、下游、较浅的水：台阶 x 570–700（往下到贴水的平台再上来），金属盒 river_bank_box（漂 / 沉到浅水）",
        "原文 78 木桩：石岸前沿 x≈346（marker river_bank_post）；原文 79 浅滩、晾绑带：飞机拖上 x 110–330 的卵石滩，river_bank_plane 4 帧",
        "原文 80 高处街道：y=118 一条廊道（人群 walkers 走在上面）；面包店（暖光）伸出木板 → 对面修补摊 x 1100–1262",
        "原文 80 邮差走屋顶的窄桥、碰栏杆：x 518–564 两楼楼顶之间（walkers postman）",
        "原文 80 低处房屋泡水、窗框间小鱼、水下街砖、旧门牌：栈道下面剖开，妮芙家旧一层的门 x≈720 + 旧门牌 x≈738",
        "原文 80 新旧水位交界：后排楼身上一道苔痕（旧水位），妮芙家（D 画）站在 x 680–1100 的栈道上",
        "原文 83、146 小船：系在浅滩边的后排水里 x 1206–1250（船头一个空挂钩，铃原来挂这）；去市集的楼梯井 x 1336（pan_up），右端小巷去南桥",
        "妮芙家（D 画的 home_back / home_front，x=890）在这张联系表里也叠上了，看接缝",
    ],
    "market": [
        "原文 103 高处、比河岸热闹：平台在屋顶高度，天和远城露得多；walkers 5 个兜帽人 + 卖菜的人",
        "原文 103 卖菜的人把篮子吊在栏杆外：物件 market_baskets（两帧轻晃，在栏杆前面）",
        "原文 103 修补摊的工具挂得叮当响：物件 market_tools（4 帧，一排工具依次晃）",
        "原文 103 每家店门边的标记：每扇门右边一样小记号（纸签 / 粉笔划 / 布条）",
        "原文 103 摊主把气瓶放到柜台上：物件 market_breather_stall（default 空 / tank_on_counter），墙上一排气瓶都贴着签",
        "原文 104 不太甜的饼干、纸袋：饼干铺（暖光橱窗、一排罐子）",
        "原文 71 细桥连接屋顶：平台中间一座窄桥（market_bridge），下面是空的，看得见下面城里的水",
    ],
    "oldstreet": [
        "原文 105 踏步大半浸在水里：踏步 x 440–580；水位 5 档 submerged/l1/l2/l3/revealed = y 156/178/200/222/246",
        "原文 105 三道小闸、少了两块铭牌：sluice_wheel_1/2 小、没铭牌，3 大、有铭牌；8 帧 = 刻度上 8 格",
        "原文 105 墙上不同年份的水位刻线、最旧一条被苔盖住：踏步旁挡土墙 x 404–434，刻线正好对着各档水位",
        "原文 105 管道方向：1 往左下到闸台底下、2 往右下到踏步旁（冒泡 sluice_pipes）、3（大）往上绕到旧街",
        "原文 105 妮芙趴在栏杆边：上层闸台前沿的栏杆（在人前面）",
        "原文 108 招牌下面另一排更旧的门窗、同样的店名、油漆剥落：x 470–1196，上一排挂牌、下一排旧门楣",
        "原文 108 拐角、半截台阶（果酱店）：x 760–800 窄巷口，四级台阶断在半空，墙上褪色的果酱罐",
        "原文 109 身高刻线、最上面粗红线写着洪水日期：x 864–892；干燥的台阶 x 930–974",
        "原文 110 仓库入口在水下：x 1036–1092 往下的台阶没进水里；原文 143 仓库外侧旧挂钩 x≈1112",
    ],
    "warehouse": [
        "原文 111 匆忙搬迁的样子、桌椅被绑到高处：天花板梁上吊着三张桌子、三把椅子",
        "原文 111 抽屉朝同一个方向敞着：后墙两排柜子，每只抽屉都往右拉出来",
        "原文 111 一排贴着圆圆的字的箱子：x 316–456（marker warehouse_boxes）",
        "原文 111 破箱子，纽扣、空瓶、褪色照片散在柜底：物件 warehouse_broken_box（spilled）",
        "原文 112 浮箱改变柜子的受力位置：warehouse_tall_cabinet（fallen / lifted），浮箱 warehouse_float（idle / 拴柜顶 / 拴错柜脚）",
        "原文 112 拉开堵住内门的家具：warehouse_furniture（pinned / loose / moved）、warehouse_inner_door（closed / open）",
        "原文 112 设备柜（贴标签的抽屉，marker warehouse_cabinet x 598）、导绳 rope + 绳结 2 个、出口灯（入口上，一明一暗）",
        "原文 113 旧泄水门、门边挂着操作记录、下面压着手绘图：物件 warehouse_sluice_door（taken = 记录取下）",
    ],
    "southbridge": [
        "原文 136 退水后露得多、像栏杆的东西原来是屋顶上的装饰：桥那头两栋矮房子屋脊上一排小尖柱（southbridge_ornament）",
        "原文 136 灯柱、走错一次桥洞：桥面三根灯柱；三个桥洞，左边那个是错的、中间是对的",
        "原文 97/124 浮灯：拴浮灯的缆绳退水后垂在桥下；桥墩上一道旧的高水位印子",
        "原文 138 很高的擦痕、石沿上的粗毛、泥滩上连续的脚印：southbridge_arch（scratches）、southbridge_footprints（seen）",
        "原文 137 旧运输水道的入口：southbridge_waterway（default 被淤泥水草挡着 / revealed）",
        "原文 139 废弃货台、航线图脱落、几块编号牌（07 / 12 / 21）、旧装卸记录：x 1180–1500（台阶、印子、三块牌、夹板）；southbridge_routemap",
        "原文 137 还原拍摄位置：viewfinder.png（晨站在 southbridge_view_spot=592、镜头居中时对齐；水位抬高、浮灯歪、桥洞里一团灰影）",
    ],
}

SHOTS = {
    "river_bank": [(200, 0, {}), (470, 0, {"river_bank_plane": "beached", "river_bank_crates": "tail"}),
                   (630, 0, {"river_bank_plane": "straps_drying"}), (900, 0, {}), (1180, 0, {}), (1360, 0, {"river_bank_plane": "fixed"})],
    "market": [(100, 0, {}), (470, 0, {"market_breather_stall": "tank_on_counter"}), (830, 0, {}), (1300, 0, {})],
    "oldstreet": [(260, 0, {}), (520, 0, {"oldstreet_steps": "l2"}), (700, 0, {"oldstreet_steps": "revealed"}),
                  (1000, 0, {"oldstreet_steps": "revealed"})],
    "warehouse": [(80, 0, {}), (360, 0, {"warehouse_broken_box": "spilled"}),
                  (500, 0, {"warehouse_tall_cabinet": "lifted", "warehouse_float": "tied_warehouse_cabinet_top",
                            "warehouse_furniture": "loose"}),
                  (620, 0, {"warehouse_furniture": "moved", "warehouse_inner_door": "open", "warehouse_tall_cabinet": "lifted",
                            "warehouse_float": "tied_warehouse_cabinet_top"})],
    "southbridge": [(300, 0, {}), (600, 0, {"southbridge_arch": "scratches", "southbridge_footprints": "seen"}),
                    (1080, 0, {"southbridge_waterway": "revealed"}), (1360, 0, {"southbridge_routemap": "fallen"})],
}


def house_items(r: Room):
    """联系表里把 D 画的妮芙家（art/river_home）也叠上：back 在人后面、front 在人前面（屋外看）。"""
    if r.id != "river_bank":
        return []
    hp = ROOT / "art" / "river_home" / "room.json"
    if not hp.exists():
        return []
    hj = json.loads(hp.read_text())
    out = []
    for key, z in (("back", -10), ("front", 50)):
        f = ROOT / "art" / "river_home" / hj.get(key, "")
        if f.is_file():
            a = np.array(Image.open(f).convert("RGBA"))
            a[..., 3] = np.where(a[..., 3] > 0, 255, 0)
            x = int(round(hj["x"] - a.shape[1] / 2))
            y = r.ground_at(hj["x"]) + 1 - a.shape[0]
            out.append((z, "img", (x, y), a))
    return out


def contact_sheet(r: Room, path, extra_imgs=()):
    from PIL import ImageFont
    font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 22)
    small = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 18)
    S = 2
    shots = SHOTS[r.id]
    tiles = []
    for (chx, _, st) in shots:
        dy = 0
        if r.id == "oldstreet":
            lv = st.get("oldstreet_steps", "submerged")
            dy = O_LEVELS[lv] - O_LEVELS["submerged"]
        im = render(r, chx - 240, st, chx, water_dy=dy, extra=house_items(r))
        label = f"晨 x={chx}" + ("  " + ", ".join(f"{k.split('_', 1)[1]}={v}" for k, v in st.items()) if st else "")
        tiles.append((Image.fromarray(im).resize((SW * S, SH * S), Image.NEAREST), label))
    for img, label in extra_imgs:
        tiles.append((Image.fromarray(img).resize((SW * S, SH * S), Image.NEAREST), label))
    cols = 2
    rows = (len(tiles) + cols - 1) // cols
    tw, th = SW * S, SH * S + 34
    notes = NOTES.get(r.id, [])
    nh = 40 + 30 * len(notes)
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * 12, rows * th + (rows + 1) * 12 + nh + 50), (14, 16, 18))
    d = ImageDraw.Draw(sheet)
    d.text((12, 10), f"{r.id}（{r.w}×270）  tools/river_city_art.py", fill=(220, 220, 220), font=font)
    for i, (im, label) in enumerate(tiles):
        x = 12 + (i % cols) * (tw + 12)
        y = 50 + (i // cols) * (th + 12)
        sheet.paste(im, (x, y + 30))
        d.text((x, y + 4), label, fill=(180, 190, 200), font=small)
    y = 50 + rows * (th + 12) + 6
    d.text((12, y), "原文写到的东西画在哪：", fill=(220, 210, 180), font=font)
    for k, n in enumerate(notes):
        d.text((12, y + 34 + 30 * k), "· " + n, fill=(200, 200, 200), font=small)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


ROOMS = {"river_bank": bank, "market": market, "oldstreet": oldstreet, "warehouse": warehouse,
         "southbridge": southbridge}


def build(only=None, preview=None):
    common = OUT / "common"
    common.mkdir(parents=True, exist_ok=True)
    for lid in ("sky", "far", "midfar"):
        check_alpha(shared_img(lid).a, lid)
        shared_img(lid).save(common / f"{lid}.png")
    out = {}
    for rid, fn in ROOMS.items():
        if only and rid not in only:
            continue
        r = fn()
        extra = []
        if rid == "southbridge":
            vf = viewfinder(r)
            check_alpha(vf.a, "viewfinder")
            vf.save(OUT / rid / "viewfinder.png")
            extra.append((vf.a, f"取景框 viewfinder.png（镜头左边缘 {VF_CAM}）"))
        r.write()
        if preview:
            contact_sheet(r, Path(preview) / f"sheet_{rid}.png", extra)
        out[rid] = r
        print("ok", rid, r.w, len(r.layers), "layers", len(r.objects), "objects")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default=None, help="联系表写到这个目录")
    ap.add_argument("--only", default=None, help="只出这几个房间（逗号分开）")
    a = ap.parse_args()
    build(a.only.split(",") if a.only else None, a.preview)
