"""河流篇 · 妮芙家屋里的家具和小物件（作者 10-30：「一个灰色长方形套着一个黄色长方形，缺乏质感啊喂！还有很多内部装饰也是」）。

tools/river_home_rooms_art.py 调用。不直接上颜色，而是先记「材质 + 底色深浅 + 朝向 + 离墙多远」，最后按屋里的灯一起打光：
  - 每个像素有材质（木、铁、玻璃、陶、纸、贝壳、布……每种一条暗→亮的色阶，暗端偏靛蓝、亮端偏它自己的颜色）；
  - 有朝向（正面、顶面、左右侧面、圆柱 / 圆顶按位置变）：朝着灯的那条边亮、背着灯的暗，所以罐子是圆的、架板有厚度；
  - 光分档（8 档明暗 × 4 档暖），档边是硬的，不撒点；离灯远的东西沉在月夜的蓝里，只有灯附近的才暖；
  - 墙上的光（wall_light）也在这里：一圈圈分档、很快衰减，东西挡住的地方墙上留一块影子（光只落在附近的家具和墙上）。
灯芯、火苗、玻璃上的高光、纸条上的字迹是固定色（fix），不参与打光。
所有随机固定 seed。
"""
from __future__ import annotations

import math

import numpy as np

from river_bank_moon_art import B, Wm, to_lab
from oscarkit.palette import oklab_to_srgb

# ---------------------------------------------------------------- 材质：暗端（L, C, h）→ 亮端（L, C, h），在 OKLab 里插值
MATS = {
    "wood":   ((.065, .02, 266), (.44, .035, 62)),
    "wood_d": ((.05, .02, 268), (.36, .03, 58)),
    "wood_l": ((.08, .02, 262), (.52, .035, 72)),
    "iron":   ((.045, .014, 266), (.40, .014, 236)),
    "brass":  ((.07, .025, 262), (.60, .075, 84)),
    "tin":    ((.07, .016, 262), (.56, .02, 222)),
    "paper":  ((.16, .02, 262), (.80, .028, 92)),
    "card":   ((.15, .02, 264), (.74, .035, 80)),
    "kraft":  ((.10, .022, 266), (.58, .05, 66)),
    "glass_g": ((.07, .03, 250), (.56, .06, 170)),
    "glass_b": ((.07, .03, 264), (.58, .05, 222)),
    "glass_a": ((.07, .03, 268), (.58, .08, 62)),
    "clay":   ((.07, .025, 274), (.52, .065, 42)),
    "glaze":  ((.09, .02, 262), (.70, .03, 96)),
    "glaze_b": ((.08, .025, 264), (.58, .04, 232)),
    "shell":  ((.10, .022, 284), (.76, .045, 28)),
    "leather": ((.05, .02, 274), (.42, .05, 36)),
    "cloth_t": ((.06, .025, 252), (.48, .04, 196)),
    "cloth_r": ((.06, .025, 284), (.50, .05, 12)),
    "cloth_m": ((.07, .025, 266), (.56, .06, 92)),
    "cloth_g": ((.06, .025, 262), (.44, .035, 140)),
    "rope":   ((.07, .02, 266), (.56, .045, 80)),
    "cork":   ((.07, .025, 270), (.50, .06, 58)),
    "rubber": ((.04, .014, 266), (.40, .025, 226)),
    "stone":  ((.06, .02, 262), (.40, .02, 238)),
    "herb":   ((.06, .025, 250), (.44, .05, 128)),
    "screen": ((.05, .02, 250), (.40, .03, 200)),
}
INK = B(.2, .035, 262)                     # 妮芙的笔迹（深灰蓝；比纸暗三四档，不是黑洞）
INK_R = Wm(.30, .07, 28)                   # 红铅笔
FLAME = [Wm(.48, .11, 52), Wm(.66, .12, 70), Wm(.80, .10, 86), Wm(.90, .06, 96)]
GLOW = [Wm(.42, .09, 58), Wm(.54, .10, 66), Wm(.64, .10, 76)]
SPEC = B(.62, .02, 220)                    # 玻璃 / 铁皮上的一点冷高光（离灯远）
SPEC_W = Wm(.80, .07, 86)                  # 灯照到的高光

FRONT = (0.0, 0.0, 1.0)


def nrm(x, y, z=0.8):
    v = np.array([x, y, z], float)
    return tuple(v / np.linalg.norm(v))


TOP = nrm(0, -1, 0.85)
BOT = nrm(0, 1, 0.9)
LEFT = nrm(-1, 0, 0.9)
RIGHT = nrm(1, 0, 0.9)

N_LV = 8                                    # 明暗档数
WARM_MIX = (0.0, 0.24, 0.42, 0.58)          # 暖的 4 档


def _lab(c):
    L, C, h = c
    return np.array([L, C * math.cos(math.radians(h)), C * math.sin(math.radians(h))])


_cache: dict = {}


def mat_color(mat, q, wq):
    key = (mat, q, wq)
    if key in _cache:
        return _cache[key]
    lo, hi = MATS[mat]
    t = q / (N_LV - 1)
    lab = _lab(lo) + (_lab(hi) - _lab(lo)) * t
    if wq:
        w = _lab((min(.86, lab[0] + .03 + .02 * wq), .09, 68))
        lab = lab + (w - lab) * WARM_MIX[wq]
    c = tuple(int(v) for v in np.clip(oklab_to_srgb(lab[None])[0], 0, 255))
    _cache[key] = c
    return c


class Props:
    """记材质 / 深浅 / 朝向 / 离墙距离的画布；render() 按灯打光出 RGBA。坐标都是图里的像素，矩形两头都含。"""

    def __init__(self, w, h, seed=0):
        self.W, self.H = w, h
        self.mat = np.full((h, w), "", object)
        self.t = np.zeros((h, w))
        self.n = np.zeros((h, w, 3))
        self.n[..., 2] = 1
        self.z = np.zeros((h, w))
        self.fix = np.zeros((h, w, 4), np.uint8)
        self.clip = None                      # 只能画在这个 mask 里（洞的形）
        self.rng = np.random.default_rng(seed)
        self.slips = []                       # 标签纸条的像素 [(x, y, 是字吗)]，给 obj_labels 的 on 帧
        self.cast = np.zeros((h, w), bool)    # 会在墙上投影的像素
        self.spec = []                        # 玻璃 / 铁皮高光的位置 (x0, y, x1, z)：render 时放在朝灯那一侧

    # ---- 基本
    def ok(self, x, y):
        return 0 <= x < self.W and 0 <= y < self.H and (self.clip is None or self.clip[y, x])

    def px(self, x, y, mat, t, n=FRONT, z=3.0, cast=True):
        x, y = int(x), int(y)
        if not self.ok(x, y):
            return
        self.mat[y, x] = mat
        self.t[y, x] = t
        self.n[y, x] = n
        self.z[y, x] = z
        self.fix[y, x, 3] = 0
        self.cast[y, x] = cast

    def fx(self, x, y, c, z=3.0, cast=True):
        x, y = int(x), int(y)
        if not self.ok(x, y):
            return
        self.fix[y, x, :3] = c[:3]
        self.fix[y, x, 3] = 255
        self.mat[y, x] = "fix"
        self.z[y, x] = z
        self.cast[y, x] = cast

    def dt(self, x, y, d):
        """已经画了的像素深浅加一点（纹理、木纹）。"""
        x, y = int(x), int(y)
        if self.ok(x, y) and self.mat[y, x] not in ("", "fix"):
            self.t[y, x] += d

    def rect(self, x0, y0, x1, y1, mat, t, n=FRONT, z=3.0, cast=True):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.px(x, y, mat, t, n, z, cast)

    def hline(self, x0, x1, y, mat, t, n=FRONT, z=3.0):
        for x in range(int(x0), int(x1) + 1):
            self.px(x, y, mat, t, n, z)

    def vline(self, x, y0, y1, mat, t, n=FRONT, z=3.0):
        for y in range(int(y0), int(y1) + 1):
            self.px(x, y, mat, t, n, z)

    def line(self, x0, y0, x1, y1, mat, t, n=FRONT, z=3.0, fixc=None):
        n_ = max(abs(x1 - x0), abs(y1 - y0)) + 1
        for i in range(int(n_)):
            k = i / max(1, n_ - 1)
            x, y = round(x0 + (x1 - x0) * k), round(y0 + (y1 - y0) * k)
            if fixc is not None:
                self.fx(x, y, fixc, z)
            else:
                self.px(x, y, mat, t, n, z)

    def mask(self):
        return self.mat != ""

    # ---- 形
    def box(self, x0, y0, x1, y1, mat, t=0.36, z=4.0, top=1, sides=True, bottom=True, grain=0.0):
        """方的东西：正面 + 顶上一两行朝上（亮）+ 左右一列侧面 + 底下一行朝下（暗）。grain = 横向木纹的深浅抖动。"""
        rng = self.rng
        rows = {}
        for y in range(y0, y1 + 1):
            rows[y] = (rng.random() - 0.5) * grain
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                n, tt = FRONT, t + rows[y]
                if y < y0 + top:
                    n, tt = TOP, t + 0.12
                elif bottom and y == y1:
                    n, tt = BOT, t - 0.1
                elif sides and x == x0:
                    n, tt = LEFT, t - 0.02
                elif sides and x == x1:
                    n, tt = RIGHT, t - 0.02
                self.px(x, y, mat, tt, n, z)

    def cyl(self, x0, y0, x1, y1, mat, t=0.36, z=4.0, top_rows=1, round_top=False, round_bot=True):
        """竖着的圆柱（罐、瓶身、桶）：横向按位置算朝向；顶上一行是开口 / 盖面（朝上）；底下两角磨圆。"""
        w = x1 - x0 + 1
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if round_bot and y == y1 and w > 3 and x in (x0, x1):
                    continue
                if round_top and y == y0 and w > 3 and x in (x0, x1):
                    continue
                u = ((x - x0) + 0.5) / w * 2 - 1
                n = nrm(u * 1.1, 0, math.sqrt(max(0.05, 1 - u * u)))
                tt = t - 0.06 * abs(u) ** 2
                if y < y0 + top_rows:
                    n, tt = TOP, t + 0.14
                self.px(x, y, mat, tt, n, z)

    def hcyl(self, x0, y0, x1, y1, mat, t=0.36, z=4.0, cap=True):
        """横躺的圆柱（纸卷、木棍）：竖向按位置算朝向；右端一个端面（cap）。"""
        hgt = y1 - y0 + 1
        for y in range(y0, y1 + 1):
            v = ((y - y0) + 0.5) / hgt * 2 - 1
            n = nrm(0, v * 1.1, math.sqrt(max(0.05, 1 - v * v)))
            for x in range(x0, x1 + 1):
                self.px(x, y, mat, t - 0.05 * abs(v), n, z)
        if cap:
            for y in range(y0, y1 + 1):
                self.px(x1, y, mat, t + 0.1, RIGHT, z)

    def dome(self, cx, cy, rx, ry, mat, t=0.36, z=4.0, lower=False):
        """半个椭圆鼓包（贝壳、布堆、帽子）：朝向按球面算。lower=True 画整个椭圆。"""
        for y in range(int(cy - ry), int(cy + (ry if lower else 0)) + 1):
            for x in range(int(cx - rx), int(cx + rx) + 1):
                u, v = (x - cx) / (rx + 0.5), (y - cy) / (ry + 0.5)
                if u * u + v * v > 1:
                    continue
                n = nrm(u, v, math.sqrt(max(0.05, 1 - u * u - v * v)))
                self.px(x, y, mat, t, n, z)

    # ---- 纸条（手写的标签）
    def slip(self, x, y, w, h, tilt=0, lines=None, pin=None, string_to=None, t=0.42, mat="paper", z=2.0, curl=False):
        """一张手写小纸条：边不齐（缺个角 / 斜一像素），上面一两道断断续续的字迹；pin = 图钉色；string_to = 一根细绳拴到 (x, y)。"""
        rng = self.rng
        pts = []
        for yy in range(h):
            off = int(round(tilt * (yy - (h - 1) / 2) / max(1, h))) if tilt else 0
            for xx in range(w):
                if (xx, yy) in ((0, 0), (w - 1, h - 1)) and rng.random() < 0.5 and w > 2 and h > 2:
                    continue
                X_, Y_ = x + xx + off, y + yy
                n = FRONT
                tt = t
                if curl and yy == h - 1:
                    n, tt = BOT, t - 0.12
                if xx == w - 1 and w > 3:
                    tt -= 0.04
                self.px(X_, Y_, mat, tt, n, z)
                pts.append((X_, Y_))
        if lines is None:
            lines = 1 if h <= 4 else 2
        for k in range(lines):
            yy = y + 1 + k * 2
            if yy >= y + h - (0 if h <= 2 else 1) and h > 2:
                break
            x0 = x + 1 + (1 if rng.random() < 0.35 and w > 4 else 0)
            ln = max(1, int(round((w - 2 - (x0 - x - 1)) * (0.85 if k == 0 else 0.5) * (0.6 + 0.4 * rng.random()))))
            gap = int(rng.integers(1, ln)) if ln > 3 and rng.random() < 0.6 else -1
            for xx in range(x0, x0 + ln):
                if xx - x0 == gap:
                    continue                                    # 字和字之间空一格
                off = int(round(tilt * (yy - y - (h - 1) / 2) / max(1, h))) if tilt else 0
                self.fx(xx + off, yy, INK, z)
        if pin is not None:
            self.fx(x + w // 2, y, pin, z + 0.5)
        if string_to is not None:
            self.line(x + w // 2, y, string_to[0], string_to[1], "rope", 0.3, z=z)
        for (X_, Y_) in pts:
            self.slips.append((X_, Y_))
        return pts

    # ---- 小物件
    def shelf(self, x0, x1, y, mat="wood", t=0.36, thick=2, brackets=True, z=5.0, iron=False):
        """一块有厚度的架板：顶上一行朝上（受光）、前沿 thick 行、最底下一行背光；两头下面一只三角托架。"""
        for x in range(x0, x1 + 1):
            self.px(x, y, mat, t + 0.16, TOP, z)
            for k in range(1, thick):
                self.px(x, y + k, mat, t - 0.02 * k + (0.05 if (x * 7 + k) % 11 == 0 else 0), FRONT, z)
            self.px(x, y + thick, mat, t - 0.16, BOT, z)
        self.px(x0, y, mat, t + 0.08, LEFT, z)
        self.px(x1, y, mat, t + 0.04, RIGHT, z)
        if brackets:
            for bx, d in ((x0 + 2, 1), (x1 - 2, -1)):
                for k in range(3):
                    for j in range(3 - k):
                        self.px(bx + d * j, y + thick + 1 + k, "iron" if iron else mat, t - 0.08, FRONT, z - 1)

    def jar(self, x, base, w, h, mat="glaze", lid="cork", t=0.36, label=True, z=4.0, contents=None):
        """罐子：圆柱身、肩往里收一像素、盖子（软木塞 / 铁盖 / 扎布），前面贴一张手写小纸条。"""
        top = base - h + 1
        self.cyl(x + 1, top, x + w - 2, top + 1, lid, t + 0.02, z, top_rows=1, round_bot=False)
        self.cyl(x, top + 2, x + w - 1, base, mat, t, z, top_rows=0)
        self.hline(x + 1, x + w - 2, top + 2, mat, t + 0.1, TOP, z)
        if contents is not None:                   # 玻璃罐里装的东西（下面半截颜色深一档）
            cm, ct, lv = contents
            for yy in range(base - lv + 1, base):
                for xx in range(x + 1, x + w - 1):
                    u = ((xx - x) + 0.5) / w * 2 - 1
                    self.px(xx, yy, cm, ct - 0.05 * abs(u), nrm(u, 0, 0.9), z)
        if label and w >= 4 and h >= 6:
            lw = max(2, w - 2 - int(self.rng.integers(0, 2)))
            lh = 2 if h < 9 else 3
            lx = x + (w - lw) // 2 + int(self.rng.integers(-1, 1) if w > 5 else 0)
            ly = top + 3 + int(self.rng.integers(0, max(1, h - 5 - lh)))
            self.slip(lx, ly, lw, lh, lines=1, z=z + 0.2, t=0.42 + self.rng.random() * 0.06,
                      mat="card" if self.rng.random() < 0.5 else "paper")

    def bottle(self, x, base, w, h, mat="glass_g", t=0.34, z=4.0, label=True, cork=True, neck=1):
        """瓶子：身子是圆柱，肩一行收窄，细瓶颈，软木塞；靠灯那边一点高光（render 时按灯放）。"""
        body_top = base - int(h * 0.6)
        self.cyl(x, body_top, x + w - 1, base, mat, t, z, top_rows=0, round_top=True)
        cx = x + (w - neck) // 2
        self.rect(cx - (1 if w > 3 else 0), body_top - 1, cx + neck - 1 + (1 if w > 3 else 0), body_top - 1, mat, t + 0.08,
                  TOP, z)
        self.rect(cx, base - h + 2, cx + neck - 1, body_top - 2, mat, t + 0.04, FRONT, z)
        if cork:
            self.rect(cx, base - h + 1, cx + neck - 1, base - h + 1, "cork", 0.36, TOP, z)
        self.spec.append((x + 1, body_top + 1, x + w - 2, z))
        if label and w >= 4:
            self.slip(x + 1, body_top + 2, w - 2, 2, lines=1, z=z + 0.2, t=0.4)

    def scroll(self, x, y, ln, d=3, mat="paper", t=0.38, tie=True, z=4.0):
        """横躺的一卷纸：圆柱 + 右端看得到卷起来的端面（中间一点暗）+ 一道绳子。"""
        self.hcyl(x, y, x + ln - 1, y + d - 1, mat, t, z)
        self.px(x + ln - 1, y + d // 2, mat, t - 0.25, RIGHT, z)
        if tie:
            tx = x + ln // 3 + int(self.rng.integers(0, max(1, ln // 3)))
            self.vline(tx, y, y + d - 1, "rope", 0.22, FRONT, z + 0.1)

    def scroll_up(self, x, base, h, d=2, mat="paper", t=0.38, z=4.0):
        """竖着插的一卷纸：顶上一个端面（中间一点暗），偏一点歪。"""
        self.cyl(x, base - h + 1, x + d - 1, base, mat, t, z, top_rows=1, round_bot=False)
        self.px(x + d // 2, base - h + 1, mat, t - 0.2, TOP, z)

    def shell(self, cx, base, rx, ry, t=0.42, z=4.0, mat="shell"):
        """扇贝：半圆鼓包，几道放射的棱（亮暗交替），底下一截铰合部。"""
        self.dome(cx, base, rx, ry, mat, t, z)
        for k in range(-rx + 1, rx, 2):
            for y in range(base - ry + 1, base + 1):
                x = cx + int(round(k * (base - y + 1) / (ry + 1) * 0.9 + k * 0.1))
                self.dt(x, y, -0.1)
        self.px(cx - 1, base + 1, mat, t - 0.04, BOT, z)
        self.px(cx, base + 1, mat, t, BOT, z)
        self.px(cx + 1, base + 1, mat, t - 0.04, BOT, z)

    def conch(self, x, base, w, t=0.44, z=4.0):
        """一只海螺（横躺）：一头尖、一头宽，螺纹几道斜的暗线，开口一点粉的暗。"""
        h = max(3, w // 2)
        for xx in range(w):
            k = xx / max(1, w - 1)
            hh = max(1, int(round(h * (0.35 + 0.65 * math.sin(k * math.pi * 0.85 + 0.25)))))
            for yy in range(hh):
                v = (yy + 0.5) / hh * 2 - 1
                tt = t - (0.1 if (xx + yy) % 3 == 0 and xx < w * 0.7 else 0)
                self.px(x + xx, base - yy, "shell", tt, nrm(0, -v, 0.9), z)
        self.px(x + w - 2, base - 1, "shell", t - 0.28, FRONT, z)

    def books_flat(self, x, base, specs, string=True, z=4.0):
        """横着摞的本子（一捆）：specs = [(长, 厚, 材质, 往右错开)]，自下往上；外面十字捆一道绳。"""
        y = base
        xs = []
        for (ln, th, m, off) in specs:
            for k in range(th):
                yy = y - k
                for xx in range(x + off, x + off + ln):
                    n = FRONT
                    tt = 0.32
                    if k == th - 1:
                        n, tt = TOP, 0.42
                    if xx == x + off + ln - 1:
                        n, tt = RIGHT, 0.3
                    if xx == x + off and th > 1 and k < th - 1:
                        self.px(xx, yy, "paper", 0.4, LEFT, z)      # 书页那一侧（浅）
                        continue
                    self.px(xx, yy, m, tt, n, z)
            xs.append((x + off, x + off + ln - 1))
            y -= th
        if string:
            sx = x + min(a for a, b in xs) + (min(b for a, b in xs) - min(a for a, b in xs)) // 2
            for yy in range(y + 1, base + 1):
                self.px(sx, yy, "rope", 0.42, FRONT, z + 0.2)
            self.px(sx - 1, y, "rope", 0.5, TOP, z + 0.2)
            self.px(sx + 1, y, "rope", 0.5, TOP, z + 0.2)
        return y

    def books_up(self, x0, x1, base, hmin=5, hmax=9, mats=("leather", "cloth_t", "cloth_r", "kraft", "cloth_m", "cloth_g"),
                 lean_end=True, z=4.0, gap=0.12):
        """一排竖着的书 / 册子：高矮、厚薄、颜色各不同；书脊顶一行亮、右边一线暗；偶尔一本歪着靠、偶尔空一格。"""
        rng = self.rng
        x = x0
        while x <= x1:
            wd = int(rng.integers(1, 4))
            if x + wd - 1 > x1:
                break
            h = int(rng.integers(hmin, hmax + 1))
            m = mats[int(rng.integers(0, len(mats)))]
            tt = 0.26 + rng.random() * 0.12
            for xx in range(x, x + wd):
                for yy in range(base - h + 1, base + 1):
                    n = TOP if yy == base - h + 1 else (RIGHT if xx == x + wd - 1 and wd > 1 else FRONT)
                    self.px(xx, yy, m, tt + (0.12 if n == TOP else 0) - (0.05 if n == RIGHT else 0), n, z)
            if h >= 6 and rng.random() < 0.55:                  # 书脊上一道烫的横线
                self.dt(x, base - h + 3, 0.12)
                if wd > 1:
                    self.dt(x + 1, base - h + 3, 0.12)
            x += wd
            if rng.random() < gap:
                x += 1
        if lean_end and x + 3 <= x1 + 3:                            # 最后一本斜着靠
            h = hmin + 1
            m = mats[int(rng.integers(0, len(mats)))]
            for k in range(h):
                xx = x + k // 3
                self.px(xx, base - k, m, 0.3, FRONT, z)
                self.px(xx + 1, base - k, m, 0.26, RIGHT, z)

    def box_small(self, x, base, w, h, mat="kraft", t=0.34, z=4.0, label=True, lid=True, string=False):
        """小盒子：盖子比盒身宽一像素、盖沿下一道暗缝；手写小纸条；可以捆一道绳。"""
        top = base - h + 1
        self.box(x + 1, top + (2 if lid else 0), x + w - 2, base, mat, t, z, top=0)
        if lid:
            self.box(x, top, x + w - 1, top + 1, mat, t + 0.06, z, top=1, bottom=False)
            self.hline(x + 1, x + w - 2, top + 2, mat, t - 0.14, FRONT, z)
        if string:
            sx = x + w // 2 + int(self.rng.integers(-1, 2))
            self.vline(sx, top, base, "rope", 0.44, FRONT, z + 0.1)
        if label and w >= 5 and h >= 4:
            lw = min(w - 3, 2 + int(self.rng.integers(1, 4)))
            self.slip(x + 1 + int(self.rng.integers(0, max(1, w - 2 - lw))), top + (3 if lid else 1), lw, 2, lines=1,
                      z=z + 0.2, tilt=0)

    def tin(self, x, base, w, h, t=0.36, z=4.0, label=True):
        """铁皮盒（影像盒、茶罐）：盖沿一线亮、四角圆、侧面一点冷高光。"""
        top = base - h + 1
        self.box(x, top, x + w - 1, base, "tin", t, z, top=1)
        self.hline(x, x + w - 1, top + 1, "tin", t - 0.12, FRONT, z)
        self.spec.append((x + 1, top + 2, x + w - 2, z))
        if label and w >= 5:
            self.slip(x + 2, top + 2, min(w - 4, 5), 2, lines=1, z=z + 0.2)

    def crate(self, x, base, w, h, t=0.32, z=6.0, wet=False, label=True, handle=True, mat="wood"):
        """木箱：横板（板缝一道暗、每块板深浅不同、上沿一线亮）、两边竖的角柱、钉子、一侧麻绳把手、顶面露一行板。"""
        rng = self.rng
        top = base - h + 1
        self.box(x, top, x + w - 1, base, mat, t, z, top=1, grain=0.0)
        y = top + 1
        while y <= base:
            ph = int(rng.integers(3, 5))
            tt = t + (rng.random() - 0.5) * 0.1
            for yy in range(y, min(base, y + ph - 1) + 1):
                for xx in range(x + 2, x + w - 2):
                    self.px(xx, yy, mat, tt + (0.06 if yy == y else 0) + (0.04 if (xx * 5 + yy * 3) % 13 == 0 else 0),
                            FRONT, z)
            if y + ph <= base:
                self.hline(x + 2, x + w - 3, y + ph - 1, mat, t - 0.2, BOT, z)
            y += ph
        for cx in (x, x + 1, x + w - 2, x + w - 1):                 # 角柱
            for yy in range(top + 1, base + 1):
                n = LEFT if cx == x else (RIGHT if cx == x + w - 1 else FRONT)
                self.px(cx, yy, mat, t + (0.06 if cx in (x + 1, x + w - 2) else -0.02), n, z)
        for (nx, ny) in ((x + 1, top + 2), (x + w - 2, top + 2), (x + 1, base - 2), (x + w - 2, base - 2)):
            self.px(nx, ny, "iron", 0.4, FRONT, z)
        if handle and h >= 8:
            hy = top + h // 3
            self.px(x + w - 1, hy, "rope", 0.4, RIGHT, z)
            self.px(x + w, hy + 1, "rope", 0.36, RIGHT, z)
            self.px(x + w - 1, hy + 2, "rope", 0.32, RIGHT, z)
        if wet:
            for yy in range(base - 2, base + 1):
                for xx in range(x, x + w):
                    if (xx * 3 + yy * 2) % 5:
                        self.dt(xx, yy, -0.14)
        if label:
            lw = int(rng.integers(4, 7))
            self.slip(x + 3 + int(rng.integers(0, max(1, w - 6 - lw))), top + 2 + int(rng.integers(0, max(1, h // 3))), lw,
                      3, lines=1, tilt=int(rng.integers(-1, 2)), z=z + 0.2)

    def barrel(self, x, base, w, h, t=0.32, z=6.0, label=True):
        """木桶：竖板（一条条深浅）、中间鼓、两道铁箍（亮的一线）。"""
        rng = self.rng
        top = base - h + 1
        for yy in range(top, base + 1):
            k = (yy - top) / max(1, h - 1)
            bulge = 1 if 0.2 < k < 0.8 else 0
            for xx in range(x - bulge, x + w + bulge):
                u = ((xx - x + bulge) + 0.5) / (w + 2 * bulge) * 2 - 1
                stave = ((xx - x) // 2) % 2
                n = nrm(u * 1.1, 0, math.sqrt(max(0.05, 1 - u * u)))
                tt = t + (0.07 if stave else -0.05) - 0.06 * abs(u)
                if yy == top:
                    n, tt = TOP, t + 0.14
                self.px(xx, yy, "wood", tt, n, z)
        for hy in (top + 2, base - 2):
            for xx in range(x - 1, x + w + 1):
                if self.mat[hy, xx] if 0 <= xx < self.W else False:
                    u = ((xx - x) + 0.5) / w * 2 - 1
                    self.px(xx, hy, "iron", 0.46, nrm(u, -0.4, 0.8), z + 0.1)
        if label:
            self.slip(x + w // 2 - 2, top + h // 2 - 1, 5, 3, lines=1, tilt=1, z=z + 0.2)

    def sack(self, x, base, w, h, t=0.34, z=6.0, mat="kraft"):
        """麻袋：下面宽上面收、顶上扎一道绳、口子翻出一撮；两道斜褶。"""
        top = base - h + 1
        for yy in range(top + 2, base + 1):
            k = (yy - top) / h
            half = (w / 2) * (0.55 + 0.45 * math.sin(min(1, k * 1.4) * math.pi / 2))
            cx = x + w / 2
            for xx in range(int(cx - half), int(cx + half) + 1):
                u = (xx - cx) / (half + 0.5)
                v = (k - 0.6) * 1.6
                self.px(xx, yy, mat, t, nrm(u, v, math.sqrt(max(0.05, 1 - u * u))), z)
        cx = int(x + w / 2)
        self.hline(cx - 1, cx + 1, top + 2, "rope", 0.4, FRONT, z + 0.1)
        self.px(cx - 1, top + 1, mat, t + 0.1, TOP, z)
        self.px(cx + 1, top, mat, t + 0.12, TOP, z)
        self.px(cx, top + 1, mat, t + 0.06, TOP, z)
        for k in range(h // 2):
            self.dt(cx - 2 - k // 2, top + 4 + k, -0.14)
            self.dt(cx + 3 + k // 3, top + 6 + k, -0.1)

    def basket(self, x, base, w, h, t=0.36, z=5.0):
        """藤筐：编织（交错的两档）、上沿一圈粗边亮、往下收一点。"""
        top = base - h + 1
        for yy in range(top, base + 1):
            inset = 1 if yy == base else 0
            for xx in range(x + inset, x + w - inset):
                if yy <= top + 1:
                    self.px(xx, yy, "rope", t + (0.14 if yy == top else 0.0), TOP if yy == top else FRONT, z)
                else:
                    u = ((xx - x) + 0.5) / w * 2 - 1
                    weave = ((xx + (yy // 2) % 2 * 2) // 3 + yy) % 2 if yy % 2 else 0   # 一行行藤条，隔行错开
                    self.px(xx, yy, "rope", t - 0.03 + 0.08 * weave - 0.05 * abs(u), nrm(u, 0, 0.9), z)

    # ---- 灯
    def lantern(self, x, y, cord_top=None, cord="iron", z=10.0, big=False):
        """一盏吊着的小铁框提灯（灯芯在 x, y）：吊环 + 小尖顶 + 两根框条 + 玻璃（灯光透出来、上暗下亮）+ 火苗 + 底座，
        框条内侧被火照亮一线。big = 餐桌那盏大一号。"""
        hw = 3 if big else 2                       # 玻璃半宽
        gt, gb = y - (4 if big else 3), y + (3 if big else 2)
        if cord_top is not None:
            for yy in range(cord_top, gt - 3):
                if cord == "chain":
                    self.fx(x, yy, B(.16, .02, 250) if yy % 2 else B(.26, .02, 240), z)
                else:
                    self.fx(x, yy, B(.14, .02, 256), z)
        # 吊环、尖顶
        self.fx(x, gt - 3, B(.24, .02, 246), z)
        for k, yy in enumerate((gt - 2, gt - 1)):
            for xx in range(x - k - (1 if big else 0), x + k + (1 if big else 0) + 1):
                c = Wm(.42, .06, 60) if yy == gt - 1 and xx >= x else B(.2 + .05 * k, .02, 246)
                self.fx(xx, yy, c, z)
        self.fx(x - hw - 1, gt - 1, B(.14, .02, 256), z)
        self.fx(x + hw + 1, gt - 1, B(.2, .02, 250), z)
        # 框条
        for yy in range(gt, gb + 1):
            self.fx(x - hw - 1, yy, B(.12, .02, 258), z)
            self.fx(x + hw + 1, yy, Wm(.30, .05, 52) if yy > gt else B(.18, .02, 250), z)
        # 玻璃：中间火苗、周围一档档暖；下面最亮（灯芯在下半）
        for yy in range(gt, gb + 1):
            for xx in range(x - hw, x + hw + 1):
                d = math.hypot((xx - x) * 1.1, (yy - y) * 0.9)
                if d < 1.0:
                    c = FLAME[3]
                elif d < 1.9:
                    c = FLAME[2]
                elif d < 2.9:
                    c = GLOW[2]
                elif d < 3.8:
                    c = GLOW[1]
                else:
                    c = GLOW[0]
                self.fx(xx, yy, c, z, cast=False)
        self.fx(x, y - 1, FLAME[2], z, cast=False)
        if big:
            self.fx(x, y - 2, FLAME[1], z, cast=False)
            self.fx(x - hw + 1, gt + 1, Wm(.78, .06, 90), z, cast=False)      # 玻璃上一点反光
        else:
            self.fx(x - hw, gt, Wm(.70, .07, 86), z, cast=False)
        # 底座：一条铁、下面一个小坠
        for xx in range(x - hw - 1, x + hw + 2):
            self.fx(xx, gb + 1, Wm(.36, .05, 56) if xx < x + hw + 1 else B(.16, .02, 254), z)
        for xx in range(x - hw, x + hw + 1):
            self.fx(xx, gb + 2, B(.1, .02, 260), z)
        self.fx(x, gb + 3, B(.16, .02, 254), z)

    def candle(self, x, base, h=4, dish=True, z=4.0):
        """一截蜡烛：烛台小碟（铁）、蜡（受火光的一侧亮）、蜡泪一滴、火苗两三像素（外暖内亮）。"""
        if dish:
            for xx in range(x - 2, x + 3):
                self.fx(xx, base, Wm(.30, .05, 54) if abs(xx - x) < 2 else B(.16, .02, 256), z)
            self.fx(x - 3, base, B(.12, .02, 258), z)
            self.fx(x + 3, base - 1, B(.2, .02, 250), z)       # 小把手
        top = base - h
        for yy in range(top, base):
            self.fx(x - 1, yy, Wm(.56, .05, 82), z)
            self.fx(x, yy, Wm(.68, .05, 88), z)
            self.fx(x + 1, yy, Wm(.46, .045, 74), z)
        self.fx(x + 1, top + 1, Wm(.64, .05, 86), z)           # 蜡泪
        self.fx(x, top - 1, FLAME[3], z, cast=False)
        self.fx(x, top - 2, FLAME[2], z, cast=False)
        self.fx(x, top - 3, FLAME[0], z, cast=False)
        self.fx(x - 1, top - 1, FLAME[0], z, cast=False)

    # ---- 打光
    def render(self, lamps, amb=0.1):
        """lamps = [(x, y, z, 半径, 强度)]，或者 (x, y, z, 半径, 强度, (y0, y1)) = 冷光（月光从窗洞进来）：
        只照 y0..y1 这几行、只提亮不加暖。返回 RGBA（alpha 0/255）。"""
        H, W = self.H, self.W
        out = np.zeros((H, W, 4), np.uint8)
        ys, xs = np.nonzero((self.mat != "") & (self.mat != "fix"))
        if len(ys):
            n = self.n[ys, xs]
            term = np.zeros(len(ys))
            cool = np.zeros(len(ys))
            for lp in lamps:
                lx, ly, lz, r, pw = lp[:5]
                dx, dy, dz = lx - xs, ly - ys, lz - self.z[ys, xs]
                d = np.hypot(dx, dy)
                fall = np.clip(1 - d / r, 0, 1) ** 1.25
                ln = np.sqrt(dx * dx + dy * dy + dz * dz) + 1e-6
                ndl = np.clip((n[:, 0] * dx + n[:, 1] * dy + n[:, 2] * dz) / ln, 0, 1)
                if len(lp) > 5:
                    y0, y1 = lp[5]
                    cool += pw * fall * (0.1 + 0.9 * ndl) * ((ys >= y0) & (ys <= y1))
                else:
                    term += pw * fall * (0.22 + 0.78 * ndl)
            term = np.clip(term, 0, 1.2)
            # 底光：屋里的冷光从上面来一点（顶面、架板上沿亮一档），月光从右边的窗洞来一点（右侧面亮一点）；
            # 冷光（窗洞进来的月光）只提亮
            tone = self.t[ys, xs] + amb * np.clip(-n[:, 1], 0, 1) + 0.4 * amb * np.clip(n[:, 0], 0, 1) + 0.52 * term \
                + 0.4 * np.clip(cool, 0, 1)
            q = np.clip(np.round(tone * (N_LV - 1)), 0, N_LV - 1).astype(int)
            wq = np.clip(np.floor(term * 3.4), 0, 3).astype(int)
            mats = self.mat[ys, xs]
            for i in range(len(ys)):
                c = mat_color(mats[i], int(q[i]), int(wq[i]))
                out[ys[i], xs[i], :3] = c
                out[ys[i], xs[i], 3] = 255
            # 玻璃 / 铁皮的一点高光：放在朝灯那一侧
            for (x0, y0, x1, z) in self.spec:
                best = None
                for (lx, ly, lz, r, pw) in [lp[:5] for lp in lamps if len(lp) == 5]:
                    d = math.hypot(lx - (x0 + x1) / 2, ly - y0)
                    if d < r * 0.9 and (best is None or d < best[0]):
                        best = (d, lx)
                if best is None:
                    hx, c = x0, SPEC
                else:
                    hx, c = (x1 if best[1] > (x0 + x1) / 2 else x0), SPEC_W
                if 0 <= hx < W and 0 <= y0 < H and out[y0, hx, 3]:
                    out[y0, hx, :3] = c
        fm = self.fix[..., 3] > 0
        out[fm] = self.fix[fm]
        return out


# ---------------------------------------------------------------- 墙上的光
def wall_light(img, mask, lamps, cast, rng, strength=1.0):
    """灯光落到墙上（已经画了的石壁往暖推）：离灯越近越暖、分 3 档，档边是一圈圈有棱角的线（低频噪声扰一下，不撒点）；
    挡在灯和墙之间的东西在墙上留一块影子（沿着离开灯的方向，离灯越远影子越长）。
    lamps = [(x, y, z, 半径, 强度)]；cast = 会投影的东西的 mask。"""
    import river_rock_tex as rt
    h, w = mask.shape
    nz = rt.vnoise(h, w, 9.0, rng)
    cache = {}
    level = np.zeros((h, w))
    for (lx, ly, lz, r, pw) in [lp for lp in lamps if len(lp) == 5]:
        y0, y1 = max(0, int(ly - r)), min(h, int(ly + r) + 1)
        x0, x1 = max(0, int(lx - r * 1.2)), min(w, int(lx + r * 1.2) + 1)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if not mask[y, x] or cast[y, x]:
                    continue
                d = math.hypot((x - lx) / 1.15, (y - ly) * (1.0 if y >= ly else 1.25)) / 0.8
                if d >= r:
                    continue
                fall = (1 - d / r) ** 1.6 * pw * strength
                # 影子：从这一点往灯走一小段，碰到东西就算挡住
                ux, uy = (lx - x) / max(d, 1e-3), (ly - y) / max(d, 1e-3)
                smax = min(9.0, d * 0.32)
                s = 1.0
                shadow = False
                while s <= smax:
                    sx, sy = int(round(x + ux * s)), int(round(y + uy * s))
                    if 0 <= sx < w and 0 <= sy < h and cast[sy, sx]:
                        shadow = True
                        break
                    s += 1.0
                if shadow:
                    fall *= 0.12
                level[y, x] = max(level[y, x], fall)
    wab = _lab((0.5, 0.075, 72))[1:]
    lift = (0.0, 0.03, 0.06, 0.1)
    mix = (0.0, 0.16, 0.4, 0.62)
    for y, x in zip(*np.nonzero(level > 0)):
        q = int(np.clip(math.floor(level[y, x] * 4.2 + (nz[y, x] - 0.5) * 0.3), 0, 3))
        if q <= 0:
            continue
        col = tuple(int(v) for v in img[y, x, :3])
        key = (col, q)
        if key not in cache:
            lab = to_lab(col)
            lab = np.array([lab[0] + lift[q], *(lab[1:] * (1 - mix[q]) + wab * mix[q] * min(1.0, 0.5 + lab[0] * 2))])
            cache[key] = tuple(int(v) for v in np.clip(oklab_to_srgb(lab[None])[0], 0, 255))
        img[y, x, :3] = cache[key]
