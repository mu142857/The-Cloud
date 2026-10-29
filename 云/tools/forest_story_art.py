"""森林章节（木星）屋外的场景物件。以后改这些图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/forest_story_art.py [--preview 目录]
    ... forest_story_art.py --treeline [--preview 目录]   只重画树冠缺口那一屏（treeline_view_*.png + .json）、
        更新 drawing_arc.json，别的图不动（预览：v5_view / v5_view_arc 叠弧线 / v5_view_end 漂到头 / 画的特写）

输出 art/forest_story/ 下「屋外」那一批（清单见 docs/forest_chapter.md「美术清单」）：
树屋、空屋（+ 门边的旧东西）、旧商店、小吃棚、倒木（+ 推开以后）、两根轻树枝、布条（2 帧）、蹄印、塌陷口、
凹陷、远处的雾、行李、三样材料、水泵。室内和图标（room_* / pipe_* / tool_* / icon_*）不在这里。

和 tools/forest_art.py 的主层是同一套：光从左上来，亮面偏暖、暗面偏冷；不描边、不用纯黑；
硬边、alpha 只有 0/255（只有 fog_bank 半透明）。所有东西都比晨暗（晨的头发 L≈0.9，斗篷 L≈0.45~0.55），
暖色只在很小的地方（树屋的暗窗、铜箍、树脂、布条、行李的扣子）。
色块按光照分档：朝光的面亮一档，背光的面、檐下、门洞里暗一档，是硬边的块，不是随机切面。
底边几行往地面的暗色里沉（和主层的树根一样），上到林冠里的部分往林冠的暗色里褪。

锚点：底边中点踩在地面上（底边那一行就是地面那一行）。
贴在地面上的图（蹄印、塌陷口、凹陷）有一部分在地面线以下：同名 .json 里的 ground_row 是「图里哪一行对齐地面线」，
放的时候图的上边 = 地面 y - ground_row。多帧的图横排，同名 .json 写 frame_w / frames。
所有随机都固定 seed，重跑结果不变。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from oscarkit.canvas import Canvas  # noqa: E402
from oscarkit.palette import from_hex, ramp, to_lab  # noqa: E402
import forest_art as FA  # noqa: E402

OUT = ROOT / "art" / "forest_story"
GROUND = 228


def R(hexc, n, span, hs=10):
    return ramp(from_hex(hexc), n=n, L_span=span, hue_shift=hs)


def H(*hexs):
    return [from_hex(h) for h in hexs]


# ---------------------------------------------------------------- 调色板（暗 -> 亮）
BARK = R("#252e29", 7, 0.24)          # 树屋那棵大树：比林子里的树干亮一点，读得出树皮
WOOD = R("#37392f", 6, 0.24)          # 风吹雨淋的旧木板（树屋、小吃棚），灰里带一点点暖
WOOD_C = R("#323a3b", 6, 0.2)         # 空屋的木板：更冷、更灰
PAINT = R("#34423f", 5, 0.18)         # 商店门脸剥落的旧漆（灰青）
TIN = R("#3a4548", 5, 0.22)           # 铁皮、管子、补丁（和坠毁的飞船一个色系）
MOSS = R("#2f4335", 5, 0.2, 12)       # 和主层地面的苔藓同一条
SOIL = R("#111813", 4, 0.07, 6)       # 主层的土
STONE = R("#2c322e", 4, 0.12)
DRY = R("#45423a", 4, 0.16)           # 干枝、断口的木头
DUST = R("#4c4e48", 3, 0.08)          # 门槛上的灰
GLOW = H("#3b2a20", "#553a26", "#6c4b2c", "#7f5a33")   # 树屋很暗的暖窗
COPPER = H("#3e2e27", "#57402f", "#6b5038")            # 铜箍、扣子：很小的暖色
CLOTH = R("#704c46", 4, 0.18)         # 布条：褪了色的旧红布，雾里能看见，但比晨暗
AWN = R("#34403d", 5, 0.16, 24)           # 小吃棚的雨棚布（青灰）
AWN_W = R("#44423e", 5, 0.16)         # 雨棚上另一种条纹（褪了色的旧红，几乎成灰）
RESIN = H("#4a3022", "#664227", "#7d552f", "#8e6a43")
WATER = H("#22352f", "#35504a", "#4d6c64")             # 水光：往雾色靠，不比雾亮
TAG = H("#4f4d45", "#68655a")                          # 姓名牌、纸片
FOGC = H("#3e5748", "#4e6b5a", "#5b7b67", "#6a8a74")   # 雾（和背景雾带同色）
GROUND_DARK = from_hex("#18241e")     # 主角背后那条林下的颜色，底边往这里沉


# ---------------------------------------------------------------- 画布

class Spr:
    """一张图：RGBA + 画形状用的 mask 工具。所有图元整像素，没有抗锯齿。"""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)
        self.yy, self.xx = np.mgrid[0:h, 0:w]
        self._cv = Canvas(w, h)

    # 形状 -> mask
    def poly(self, pts):
        return self._cv.poly(pts)

    def rect(self, x0, y0, x1, y1):
        return self._cv.rect(int(x0), int(y0), int(x1), int(y1))

    def ell(self, cx, cy, rx, ry):
        return self._cv.ellipse(cx, cy, rx, ry)

    def line(self, *pts):
        return self._cv.polyline([tuple(int(round(v)) for v in p) for p in pts])

    def stroke(self, pts, w0, w1):
        """贝塞尔曲线，从 w0 粗渐变到 w1 粗（树根、树枝、绳子）。"""
        P = np.array(pts, float)
        m = np.zeros((self.h, self.w), bool)
        n = int(np.sum(np.hypot(*np.diff(P, axis=0).T)) * 1.5) + 2
        for i in range(n + 1):
            t = i / n
            Q = P.copy()
            while len(Q) > 1:
                Q = Q[:-1] * (1 - t) + Q[1:] * t
            x, y = Q[0]
            r = (w0 + (w1 - w0) * t) / 2
            m |= (self.xx + 0.5 - x) ** 2 + (self.yy + 0.5 - y) ** 2 <= r * r
        return m

    # 上色
    def fill(self, m, pal, t=0):
        t = np.broadcast_to(np.asarray(t, float), (self.h, self.w))
        idx = np.clip(np.round(t), 0, len(pal) - 1).astype(int)
        cols = np.array([tuple(c) + (255,) for c in pal], np.uint8)
        self.a[m] = cols[idx[m]]

    def put(self, x, y, c):
        """手点的单个像素（钉子、铆钉、反光）：记进 keep，收尾去噪点时不动它。"""
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = tuple(c) + (255,)
            self.keep[y, x] = True

    @property
    def keep(self):
        if not hasattr(self, "_keep"):
            self._keep = np.zeros((self.h, self.w), bool)
        return self._keep

    def clear(self, m):
        self.a[m] = 0

    @property
    def mask(self):
        return self.a[..., 3] > 0

    def paste(self, other, x, y):
        c = Canvas(self.w, self.h, self.a)
        c.paste(Canvas(other.w, other.h, other.a), x, y)
        self.a = c.a


def edges(m):
    """mask 的上 / 下 / 左 / 右边缘像素。"""
    up = np.zeros_like(m)
    up[1:] = m[:-1]
    dn = np.zeros_like(m)
    dn[:-1] = m[1:]
    lf = np.zeros_like(m)
    lf[:, 1:] = m[:, :-1]
    rt = np.zeros_like(m)
    rt[:, :-1] = m[:, 1:]
    return m & ~up, m & ~dn, m & ~lf, m & ~rt


def shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = m[ys, xs]
    return out


def dilate(m, r=1):
    out = m.copy()
    for _ in range(r):
        o = out.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            o |= shift(out, dx, dy)
        out = o
    return out


def bbox_uv(s, m):
    """mask 外接框里的 u（左 0 右 1）、v（上 0 下 1）。"""
    ys, xs = np.nonzero(m)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    return (s.xx - x0) / max(1, x1 - x0), (s.yy - y0) / max(1, y1 - y0)


def round_tone(s, cx, cy, rx, ry):
    """圆东西的受光：法线和左上来的光点乘，-1..1。"""
    nx = (s.xx + 0.5 - cx) / max(rx, 0.5)
    ny = (s.yy + 0.5 - cy) / max(ry, 0.5)
    return np.clip(-(0.6 * nx + 0.8 * ny), -1, 1)


_MIX = {}


def mixc(c, d, t):
    key = (tuple(int(v) for v in c), tuple(int(v) for v in d), round(t, 3))
    if key not in _MIX:
        _MIX[key] = FA.mix(key[0], key[1], t)
    return _MIX[key]


_STEP = {}


def _step_table():
    """颜色 -> (色阶, 下标)：tint 先在自己那条色阶里往暗走，色数不会因为阴影翻倍。"""
    if not _STEP:
        for pal in (BARK, WOOD, WOOD_C, PAINT, TIN, MOSS, SOIL, STONE, DRY, DUST, GLOW, COPPER, CLOTH, AWN, AWN_W,
                    RESIN, WATER, TAG, ROCK, RUST):
            for i, c in enumerate(pal):
                _STEP.setdefault(tuple(int(v) for v in c), (pal, i))
    return _STEP


def tint(s, m, target, t):
    """把 m 里的像素压暗 t（0..1）：在自己的色阶里往下走几档；走到底了才往 target 混。"""
    tab = _step_table()
    for y, x in zip(*np.nonzero(m)):
        c = tuple(int(v) for v in s.a[y, x, :3])
        if c in tab:
            pal, i = tab[c]
            n = max(1, int(round(t * len(pal) / 2)))
            if i - n >= 0:
                s.a[y, x, :3] = pal[i - n]
                continue
            c = pal[0]
            t = t * (n - i) / n
        s.a[y, x, :3] = mixc(c, target, t)


def step_tone(s, m, k):
    """把 m 里每个像素在它自己那条色阶里挪 k 档（负 = 暗）；不认识的颜色不动。"""
    tab = _step_table()
    for y, x in zip(*np.nonzero(m)):
        c = tuple(int(v) for v in s.a[y, x, :3])
        if c in tab:
            pal, i = tab[c]
            s.a[y, x, :3] = pal[int(np.clip(i + k, 0, len(pal) - 1))]


def sink_bottom(s, rows=4, amount=0.45, target=GROUND_DARK):
    """底边几行一档一档往林下的暗色里沉：贴地的地方和主层地面融在一起，不像贴纸。"""
    for k in range(rows):
        y = s.h - 1 - k
        t = amount * (rows - k) / rows
        m = np.zeros((s.h, s.w), bool)
        m[y] = s.mask[y]
        tint(s, m, target, round(t, 2))


def noise(s, seed, cell=(3, 3)):
    """一格一格的噪声（-0.5..0.5），没有单像素的细噪声：只用来让大块的明暗分档有点起伏，不出噪点。
    cell = (宽, 高)：树皮用竖长的格子，地面用横长的。"""
    cw, ch = (cell, cell) if np.isscalar(cell) else cell
    rng = np.random.default_rng(seed)
    g = rng.random((s.h // ch + 2, s.w // cw + 2))
    big = np.repeat(np.repeat(g, ch, 0), cw, 1)
    oy, ox = int(rng.integers(0, ch)), int(rng.integers(0, cw))
    return big[oy:oy + s.h, ox:ox + s.w] - 0.5


def clean(m, keep=2):
    """去掉 mask 里孤零零的像素（四邻里少于 keep 个同伴）。"""
    n = sum(shift(m, dx, dy).astype(int) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    return m & (n >= keep)


def despeckle(s, protect=None):
    """收尾：和上下左右四个都不一样、而四邻里有 3 个以上是同一种颜色的单个像素，换成那种颜色。
    protect 里的像素（钉子、铆钉、反光这些故意点的）不动。"""
    a = s.a
    h, w = s.h, s.w
    key = (a[..., 0].astype(np.int64) << 24) | (a[..., 1].astype(np.int64) << 16) | (a[..., 2].astype(np.int64) << 8) | a[..., 3]
    out = a.copy()
    protect = s.keep if protect is None else (protect | s.keep)
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if a[y, x, 3] == 0 or protect[y, x]:
                continue
            nb = [key[y - 1, x], key[y + 1, x], key[y, x - 1], key[y, x + 1]]
            if key[y, x] in nb:
                continue
            vals, cnt = np.unique(nb, return_counts=True)
            j = int(np.argmax(cnt))
            if cnt[j] >= 3 and (vals[j] & 0xFF) == 255:
                v = int(vals[j])
                out[y, x] = ((v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, 255)
    s.a = out


def boards(s, m, pal, base, widths, seed, vertical=True, gap=1.2, var=(0, 0, 0.5, -0.5, 0.9, -0.8)):
    """木板墙：一块块板子各自深浅略不同（旧板、换过的新板），板缝暗一档。返回每个像素的色阶（float）。"""
    rng = np.random.default_rng(seed)
    coord = s.xx if vertical else s.yy
    ys, xs = np.nonzero(m)
    c0 = (xs.min() if vertical else ys.min())
    c1 = (xs.max() if vertical else ys.max())
    t = np.zeros((s.h, s.w))
    edges_at = []
    c, i = c0, 0
    while c <= c1:
        w = widths[i % len(widths)]
        sel = (coord >= c) & (coord < c + w)
        t[sel] = base + float(rng.choice(var))
        edges_at.append(c)
        c += w
        i += 1
    for c in edges_at[1:]:
        t[(coord == c) & m] -= gap
    return t


# ---------------------------------------------------------------- 小零件

GEAR = [".#.#.", "#####", "##.##", "#####", ".#.#."]
KEY = ["##.", "#.#", "##.", "#..", "##.", "#.."]
NUT = [".##.", "#..#", ".##."]


def stamp(s, rows, x, y, pal, light=True):
    """ASCII 小件：左上那半亮一档。"""
    h, w = len(rows), len(rows[0])
    for j, r in enumerate(rows):
        for i, ch in enumerate(r):
            if ch == "#":
                k = len(pal) - 1 if (light and i + j < (w + h) / 2 - 1) else len(pal) - 2
                s.put(x + i, y + j, pal[k])


# ================================================================ 树屋

def treehouse():
    """弥洛的树屋：一棵大树的树洞，正面用一块块不配套的旧木板封起来，门开在地面上；
    门和窗上面一条补过的檐（换过的新瓦、一块铆上去的铁皮、缺一片瓦），窗里是很暗的暖光。
    修理匠住的地方：挂着一串零件做的风铃、门把手上挂着姓名牌、船上拆下来的舷窗、补过的烟囱管、
    滑轮和吊桶、靠在门边修了一半的轮子、装零件的箱子。"""
    W, Hh = 172, 240
    s = Spr(W, Hh)
    gy = Hh - 1
    cx = 86
    rng = np.random.default_rng(11)
    sy = s.yy + (GROUND - gy)                  # 屏幕 y
    # 上到林冠里的部分往暗里沉：按树皮片一段段错开地暗一档、两档（不是一刀切的横线）
    jit = np.repeat(np.random.default_rng(12).integers(-9, 10, W // 3 + 2), 3)[:W]
    canopy_dark = np.clip(np.floor((124 - sy + jit[None, :]) / 20), 0, 4) * 0.5

    # ---- 树干：圆柱，左边受光；底下往外撑开成板根
    trunk = np.zeros((Hh, W), bool)
    left = np.zeros(Hh)
    right = np.zeros(Hh)
    for y in range(Hh):
        f = y / Hh
        half = 39 + 9 * f ** 2
        flare = max(0, y - (Hh - 46))
        half += (flare / 46) ** 2.4 * 22
        x0 = cx - half + 1.2 * np.sin(y / 21 + 0.5)
        x1 = cx + half + 1.0 * np.sin(y / 17 + 2.0)
        left[y], right[y] = x0, x1
        trunk[y, int(round(x0)):int(round(x1)) + 1] = True
    u = np.clip((s.xx - left[:, None]) / (right - left)[:, None], 0, 1)
    # 分档的受光：左边一条亮带，中间一档，右边两档暗（硬边，跟着树皮片走）
    plate = noise(s, 3, (3, 9)) * 0.9
    lt = 1 - np.abs(u - 0.18) / 0.82
    tone = 1.0 + 4.2 * np.clip(lt, 0, 1) ** 1.2 + plate
    tone[(u < 0.025)] -= 0.8
    # 树皮：竖着的一片片，缝顺着树干的粗细走，一段段错开；缝右边那片的左沿接到光，亮半档
    for k, uc in enumerate(np.cumsum(rng.uniform(0.07, 0.12, 14))):
        if uc > 0.96:
            break
        y = 0
        while y < Hh:
            ln = int(rng.integers(12, 34))
            off = int(rng.integers(-1, 2))
            for yy in range(y, min(Hh, y + ln)):
                xx = int(round(left[yy] + uc * (right[yy] - left[yy]))) + off
                if 0 <= xx < W and trunk[yy, xx]:
                    tone[yy, xx] -= 1.8
                    if xx + 1 < W and uc < 0.6:
                        tone[yy, xx + 1] += 0.7
            y += ln + int(rng.integers(1, 5))
    tone -= canopy_dark * 1.2
    s.fill(trunk, BARK, tone)

    # ---- 板根：几条从树干上撑下来、扎进土里的根，顶上受光（左边的根朝光、右边的背光）
    def root(x_t, h_t, x_tip, front, seed):
        m = np.zeros((Hh, W), bool)
        sgn = 1 if x_tip > x_t else -1
        L = abs(x_tip - x_t)
        for i in range(L + 1):
            x = x_t + sgn * i
            hh = h_t * (1 - i / L) ** 1.7 + 0.8 * np.sin(i / 4 + seed)
            if hh >= 0.5:
                m[int(round(gy - hh)):gy + 1, x] = True
        if not front:
            m &= ~trunk
        top, _, _, _ = edges(m)
        rn = noise(s, seed, (4, 2)) * 0.6
        base = 3.0 if sgn < 0 else 1.9
        t = base - 1.4 * np.clip((s.yy - (gy - h_t)) / max(1, h_t), 0, 1) ** 2 + rn
        s.fill(m, BARK, t)
        s.fill(top, BARK, base + 1.6)
        s.fill(clean(dilate(top, 1) & m & (noise(s, seed + 5, (5, 2)) > -0.05) & (s.yy < gy - 1)), MOSS, 2.3 if sgn < 0 else 1.6)
        return m
    root(38, 36, 1, False, 51)
    root(134, 38, 171, False, 52)
    root(30, 15, 10, True, 53)
    root(142, 16, 160, True, 54)

    # ---- 树枝（左边吊滑轮，右边一根光秃的）
    def branch(pts, w0, w1, seed):
        m = s.stroke(pts, w0, w1) & ~trunk
        top, bot, _, _ = edges(m)
        t = np.full((Hh, W), 3.0) - 1.2 * dilate(bot, 1) + 1.2 * top - canopy_dark * 1.3
        s.fill(m, BARK, t)
        mm = clean(top & (noise(s, seed + 1, (4, 1)) > 0.0), 1)
        s.fill(mm, MOSS, 2 - canopy_dark)
        return m
    branch([(52, 58), (28, 46), (2, 26)], 9, 3, 21)
    s.fill(s.stroke([(30, 44), (26, 36), (21, 31)], 2, 1), BARK, 2.5)          # 小杈
    branch([(122, 82), (148, 74), (170, 58)], 8, 3, 22)
    s.fill(s.stroke([(152, 73), (157, 80), (160, 84)], 2, 1), BARK, 1.5)

    # ---- 树洞（正面那块木板墙）
    top_y, spring_y = 126, 170
    opening = np.zeros((Hh, W), bool)
    for y in range(top_y, Hh):
        if y >= spring_y:
            hw = 31
        else:
            p = (spring_y - y) / (spring_y - top_y)
            hw = 31 * np.sqrt(max(0.0, 1 - p ** 2)) * (1 - 0.3 * p)
        hw += 0.7 * np.sin(y / 9)
        c = cx + 1 + 2 * (1 - min(1, (y - top_y) / 50))   # 顶上往右偏一点，树洞不是规矩的拱
        opening[y, int(round(c - hw)):int(round(c + hw)) + 1] = True
    # 洞口外一圈卷起来的树皮（愈伤的边）：左上那半圈朝光、亮；右下那半圈暗
    lip = dilate(opening, 3) & ~opening & trunk
    ul, vl = bbox_uv(s, opening)
    lip_in = dilate(opening, 1) & lip
    s.fill(lip, BARK, np.where(ul < 0.5, 4.4, 2.6) + np.where(lip_in, 0.8, 0) - 1.6 * ((ul > 0.5) & lip_in))
    # 洞的内壁（墙板缩在洞里 3 格）：洞口中线左边那条背光、右边那条朝光，是两道月牙，不是一圈线
    inner = opening.copy()
    for _ in range(3):
        inner = inner & shift(inner, 1, 0) & shift(inner, -1, 0) & shift(inner, 0, 1)
    reveal = opening & ~inner
    ocx = cx + 1
    s.fill(reveal & (s.xx < ocx), BARK, 0.6 + 0.6 * (s.yy > gy - 40))
    s.fill(reveal & (s.xx >= ocx), WOOD, 3.6 - 1.0 * (s.yy < top_y + 10) - 0.5 * ((s.yy // 3) % 2))
    wall = inner
    # 光从左上照进洞里：洞口左沿和顶沿在墙板上投下硬影
    lit = wall & shift(opening, 6, 9)
    wt = boards(s, wall, WOOD, 0, [6, 5, 7, 6, 5, 6, 7, 5, 6, 6, 5], 31)
    s.fill(wall, WOOD, np.where(lit, 2.9, 1.5) + wt)
    # 木纹：每块板上一两道短的暗纹
    for k in range(16):
        gx = int(rng.integers(58, 115))
        gy0 = int(rng.integers(top_y + 14, gy - 4))
        gm = wall & (s.xx == gx) & (s.yy >= gy0) & (s.yy < gy0 + int(rng.integers(4, 9)))
        s.fill(gm, WOOD, np.where(lit, 2.1, 0.9))
    # 两条横撑（钉子是亮一档的点）
    for by in (gy - 98, gy - 66):
        bm = wall & (s.yy >= by) & (s.yy <= by + 2)
        s.fill(bm, WOOD, np.where(lit, 3.6, 2.2) - (s.yy == by + 2) * 0.9)
        for nx_ in np.nonzero(bm[by + 1])[0][2::9]:
            s.put(nx_, by + 1, WOOD[5] if lit[by + 1, nx_] else WOOD[3])
    # 墙上一块铆上去的铁皮（右下，补一块烂掉的板）
    pm = s.rect(100, gy - 75, 110, gy - 68) & wall
    s.fill(pm, TIN, 1.6 + edges(pm)[0] * 1.2 - edges(pm)[1] * 0.8)
    for px_, py_ in ((101, gy - 74), (109, gy - 74), (101, gy - 69), (109, gy - 69)):
        s.put(px_, py_, TIN[3])
    # 舷窗左边挂着修理匠的小招牌：一块木牌，上面画一只齿轮
    s.put(64, gy - 95, WOOD[2])
    s.put(73, gy - 95, WOOD[2])
    sg = s.rect(62, gy - 94, 75, gy - 86)
    s.fill(sg, WOOD, 3.8 + 0.6 * (s.yy == gy - 94) - 1.4 * ((s.yy == gy - 86) | (s.xx == 75)))
    stamp(s, GEAR, 66, gy - 92, TIN)
    s.put(68, gy - 90, WOOD[2])

    # ---- 舷窗（从船上拆下来的）
    pcx, pcy = cx + 1, gy - 82
    ring = s.ell(pcx, pcy, 7.5, 7.5) & ~s.ell(pcx, pcy, 5, 5)
    s.fill(ring, TIN, 2 + 1.6 * round_tone(s, pcx, pcy, 7.5, 7.5))
    glass = s.ell(pcx, pcy, 5, 5)
    s.fill(glass, BARK, 0.6 + 0.6 * (round_tone(s, pcx, pcy, 5, 5) < -0.3))
    s.fill(s.line((pcx - 3, pcy - 1), (pcx - 1, pcy - 3)), WATER, 1)   # 玻璃上一道反光
    for a in (0.8, 2.4, 4.0, 5.5):
        s.put(round(pcx - 0.5 + 6.2 * np.cos(a)), round(pcy - 0.5 + 6.2 * np.sin(a)), TIN[4])

    # ---- 门：圆顶，三块竖板（右边那块是换过的新板），Z 形撑，门把手上挂姓名牌
    dx0, dx1, dtop = 66, 87, gy - 44
    door = s.rect(dx0, dtop, dx1, gy) | s.ell((dx0 + dx1 + 1) / 2, dtop + 1, (dx1 - dx0 + 1) / 2, 8)
    frame = dilate(door, 2) & ~door & (s.yy <= gy)
    ft, _, fl, _ = edges(frame)
    s.fill(frame, WOOD, 3.6 + 0.8 * (s.xx < dx0) - 0.9 * (s.xx > dx1))
    dt = np.where(s.xx < 73, 1.7, np.where(s.xx < 80, 1.3, 2.6))
    dt = dt - 1.0 * ((s.xx == 73) | (s.xx == 80))
    s.fill(door, WOOD, dt)
    for ry in (gy - 8, gy - 38):
        s.fill(door & (s.yy >= ry) & (s.yy <= ry + 1), WOOD, 2.9 - (s.yy == ry + 1) * 0.6)
    zb = s.stroke([(dx0 + 1.5, gy - 9), (dx1 - 0.5, gy - 36)], 2.2, 2.2) & door
    s.fill(zb, WOOD, 3.0)
    s.fill(edges(zb)[1], WOOD, 1.6)
    s.put(dx1 - 2, gy - 23, TIN[4])
    s.put(dx1 - 2, gy - 22, TIN[1])
    s.put(dx1 - 2, gy - 21, WOOD[1])
    s.fill(s.rect(dx1 - 3, gy - 20, dx1 - 1, gy - 18), TAG, 0)
    s.put(dx1 - 3, gy - 20, TAG[1])
    s.put(dx1 - 2, gy - 20, TAG[1])
    # 门前一块垫脚石
    st = s.rect(dx0 - 2, gy - 2, dx1 + 3, gy) & ~s.rect(dx0 - 2, gy - 2, dx0 - 1, gy - 2) & ~s.rect(dx1 + 2, gy - 2, dx1 + 3, gy - 2)
    s.fill(st, STONE, 1.2 + 1.6 * edges(st)[0] * (s.xx < dx1))

    # ---- 窗：很暗的暖光，窗台上一个瓶子的剪影；右边一扇百叶，掉了一片
    wx0, wx1, wy0, wy1 = 94, 108, gy - 47, gy - 33
    wm = s.rect(wx0, wy0, wx1, wy1)
    s.fill(wm, WOOD, 4.0 - 0.8 * (s.xx == wx1) - 0.8 * (s.yy == wy1))
    gm = s.rect(wx0 + 1, wy0 + 1, wx1 - 1, wy1 - 1)
    gt = 2.0 + 1.1 * (s.yy > (wy0 + wy1) / 2) - 0.9 * (s.xx > (wx0 + wx1) / 2 + 0.5) - 0.8 * (s.yy < wy0 + 4)
    s.fill(gm, GLOW, gt)
    s.fill(s.rect(wx0 + 1, (wy0 + wy1) // 2, wx1 - 1, (wy0 + wy1) // 2) | s.rect((wx0 + wx1) // 2, wy0 + 1, (wx0 + wx1) // 2, wy1 - 1), WOOD, 1.2)
    s.fill(s.rect(wx0 + 3, wy1 - 5, wx0 + 4, wy1 - 1) | s.rect(wx0 + 3, wy1 - 6, wx0 + 3, wy1 - 6), GLOW, 0)  # 瓶子
    s.fill(s.rect(wx0 + 9, wy1 - 3, wx0 + 11, wy1 - 1), GLOW, 0.4)                                    # 一个杯子
    sill = s.rect(wx0 - 1, wy1 + 1, wx1 + 1, wy1 + 1)
    s.fill(sill, WOOD, 4.4)
    s.fill(s.rect(wx0 - 1, wy1 + 2, wx1 + 1, wy1 + 2) & wall, WOOD, 1.0)
    for x in range(wx0, wx1 + 1):                 # 窗台上沿被窗里的暖光照到一点
        if x % 3 != 2:
            s.put(x, wy1 + 1, mixc(WOOD[4], GLOW[3], 0.35))
    sh = s.rect(wx1 + 2, wy0, wx1 + 5, wy1)
    s.fill(sh, WOOD, 2.2 - 0.8 * ((s.xx - wx1) % 2 == 0) * 0 - 0.7 * (s.yy % 3 == 0))
    s.clear(s.rect(wx1 + 2, wy0 + 6, wx1 + 5, wy0 + 7))           # 掉了一片
    s.fill(s.rect(wx1 + 2, wy0 + 6, wx1 + 5, wy0 + 7) & wall, WOOD, 0.8)

    # ---- 檐：两排瓦，一块铆上去的铁皮，两片换过的新瓦，缺一片；檐下一条硬影
    ex0, ex1, ey0 = 46, 126, gy - 65
    EH = 11                                   # 三排瓦，每排 4 行（最后一排露 3 行）
    eave = s.rect(ex0, ey0, ex1, ey0 + EH) & ~s.rect(ex0, ey0, ex0 + 2, ey0) & ~s.rect(ex1 - 2, ey0, ex1, ey0)
    sag = np.round(1.4 * np.sin(np.pi * (s.xx - ex0) / (ex1 - ex0))).astype(int)
    row = (s.yy - ey0 - sag)
    eave = eave & (row >= 0) & (row <= EH) | (s.rect(ex0 + 3, ey0 + EH + 1, ex1 - 3, ey0 + EH + 1) & (sag > 0))
    rowv = np.clip(row, 0, EH)
    course = rowv // 4
    sh_col = ((s.xx - ex0) + course * 3) % 6
    # 瓦是冷灰的旧木瓦（和暖一点的墙板分开）；每排瓦的上沿接到光，下沿压一条暗；左边亮
    et = 3.4 - 0.5 * course - 0.7 * (s.xx > 102) + 0.5 * (s.xx < 66)
    et = et + 0.9 * (rowv % 4 == 0) - 1.4 * (sh_col == 0) * (rowv % 4 != 0) - 1.3 * (rowv % 4 == 3) - 1.6 * (rowv == EH)
    s.fill(eave, WOOD_C, et)
    for x0_, r0 in ((62, 4), (110, 0)):        # 换过的新瓦
        m = eave & (s.xx >= x0_ + 1) & (s.xx <= x0_ + 5) & (rowv >= r0) & (rowv <= r0 + 2)
        s.fill(m, WOOD, 4.2 - 0.9 * (rowv == r0 + 2))
    miss = eave & (s.xx >= 75) & (s.xx <= 79) & (rowv >= 1) & (rowv <= 3)    # 缺一片，露出底下的暗
    s.fill(miss, BARK, 0.5)
    tin = eave & (s.xx >= 90) & (s.xx <= 104) & (rowv <= 7)
    s.fill(tin, TIN, 2.4 + 1.2 * (rowv == 0) - 1.0 * (rowv == 7) + 0.6 * (s.xx < 95))
    for px_ in (91, 97, 103):
        s.put(px_, ey0 + 1 + (1 if 82 < px_ < 112 else 0), TIN[4])
        s.put(px_, ey0 + 6 + (1 if 82 < px_ < 112 else 0), TIN[3])
    et_top, _, _, _ = edges(eave)
    mossm = clean(dilate(et_top, 1) & eave & (rowv <= 1) & (noise(s, 41, (5, 2)) > -0.1) & ~tin, 1)
    s.fill(mossm, MOSS, 2.6)
    for x in (55, 56, 68, 84, 85, 118):        # 檐口垂下来的苔
        yb = np.nonzero(eave[:, x])[0].max()
        s.put(x, yb + 1, MOSS[1])
    under = (s.yy > ey0 + EH + sag) & (s.yy <= ey0 + EH + 3 + sag) & s.mask & ~eave & (s.xx > ex0) & (s.xx < ex1)
    tint(s, under, BARK[0], 0.45)
    # 撑檐的两根斜木
    for a, b in (((ex0 + 6, ey0 + EH + 1), (ex0 + 11, ey0 + EH + 7)), ((ex1 - 6, ey0 + EH + 1), (ex1 - 11, ey0 + EH + 7))):
        s.fill(s.stroke([a, b], 2, 2), WOOD, 1.8)

    # ---- 风铃：零件串（右边）；一盏没点的小灯（左边）
    for x, ln, kind in ((114, 5, GEAR), (118, 8, KEY), (121, 3, NUT)):
        yb = np.nonzero(s.mask[:, x] & eave[:, x])[0].max()
        for y in range(yb + 1, yb + 1 + ln):
            s.put(x, y, WOOD[2])
        stamp(s, kind, x - len(kind[0]) // 2, yb + 1 + ln, TIN)
    lx = 53
    yb = np.nonzero(eave[:, lx])[0].max()
    for y in range(yb + 1, yb + 4):
        s.put(lx, y, WOOD[2])
    lamp = s.rect(lx - 2, yb + 5, lx + 2, yb + 10)
    s.fill(lamp, TIN, 1.0 + 1.2 * (s.xx < lx) )
    s.fill(s.rect(lx - 1, yb + 6, lx + 1, yb + 8), GLOW, 0)
    s.fill(s.rect(lx - 1, yb + 4, lx + 1, yb + 4), TIN, 3)

    # ---- 烟囱管：从墙上出来，拐上去贴着树皮，中间一道铜箍、两道铁丝
    py0 = gy - 77
    hp = s.rect(108, py0, 126, py0 + 3)
    vp = s.rect(123, gy - 130, 126, py0 + 3)
    pipe = hp | vp
    pt = np.where(vp, 2.2 + 1.2 * (s.xx == 123) - 1.2 * (s.xx == 126), 2.2 + 1.2 * (s.yy == py0) - 1.2 * (s.yy == py0 + 3))
    s.fill(pipe, TIN, pt)
    s.fill(s.rect(121, gy - 133, 128, gy - 131), TIN, 2.4 + 1.2 * (s.yy == gy - 133) - 0.8 * (s.xx > 125))
    s.fill(s.rect(122, gy - 134, 127, gy - 134), TIN, 2.0)
    s.fill(s.rect(123, gy - 104, 126, gy - 102), COPPER, 1 + (s.xx == 123) - (s.yy == gy - 102))
    for wy in (gy - 118, gy - 90):
        s.fill(s.rect(122, wy, 127, wy), BARK, 0.3)
    s.fill(s.rect(122, py0 - 1, 123, py0 + 4), TIN, 3)              # 弯头的焊缝

    # ---- 滑轮和吊桶：绳子一头拴在树干的木桩上
    pcx2, pcy2 = 24, 47
    s.fill(s.rect(pcx2 - 1, 41, pcx2, 44), TIN, 1)
    pul = s.ell(pcx2, pcy2 + 0.5, 3.5, 3.5)
    s.fill(pul, TIN, 2 + 1.4 * round_tone(s, pcx2, pcy2, 3.5, 3.5))
    s.put(pcx2 - 1, pcy2 - 1 + 1, TIN[0])
    rope = s.line((pcx2 - 3, pcy2 + 1), (pcx2 - 3, 150))
    rope2 = s.line((pcx2 + 3, pcy2 + 1), (47, 140))
    s.fill((rope | rope2) & ~trunk, WOOD, 3.2)
    s.fill(rope2 & trunk, WOOD, 4.2)
    s.fill(s.rect(46, 139, 49, 141), WOOD, 2.2)                       # 木桩
    s.put(46, 139, WOOD[4])
    bx = pcx2 - 3
    s.fill(s.line((bx, 150), (bx, 152)), TIN, 1)
    hand = s.line((bx - 4, 156), (bx - 3, 154), (bx + 3, 154), (bx + 4, 156))
    s.fill(hand, TIN, 2)
    bucket = s.poly([(bx - 4.5, 156), (bx + 5.5, 156), (bx + 4.5, 164), (bx - 3.5, 164)])
    s.fill(bucket, TIN, 2.6 - 1.6 * ((s.xx - bx + 4) / 9) + 0.8 * (s.yy == 156) - 0.4 * (s.yy == 160))
    s.fill(s.rect(bx - 4, 156, bx + 5, 156), TIN, 3.4)

    # ---- 苔藓：树干受光那侧下半截几片成团的苔（不是撒点）
    for k, (yc, dxc, rx, ry) in enumerate(((214, 6, 5, 11), (186, 4, 4, 9), (160, 9, 3, 6), (226, 22, 6, 5))):
        xc = left[yc] + dxc
        mm = s.ell(xc, yc, rx, ry) & trunk & ~dilate(opening, 3) & (noise(s, 61 + k, (2, 3)) > -0.3)
        mm = clean(mm)
        s.fill(mm, MOSS, 1.4 + 1.0 * (s.xx < xc) + 0.8 * edges(mm)[0])
    # ---- 洞口上沿垂下来的几根藤
    vr = np.random.default_rng(71)
    for x0, ln in ((76, 9), (80, 15), (93, 12), (99, 7)):
        y0 = int(np.nonzero(opening[:, x0])[0].min()) - 1
        x = x0
        for k in range(ln):
            if k % 4 == 3:
                x += int(vr.choice([-1, 1]))
            s.put(x, y0 + k, MOSS[1 + (k < 3)])
            if k % 3 == 1 and k < ln - 1:
                s.put(x + (1 if (k // 3) % 2 else -1), y0 + k, MOSS[3 if (k // 3) % 2 else 2])

    # ---- 门边：修了一半的轮子（缺两根辐条），右边装零件的箱子、上面一只油壶
    wcx, wcy = 59.5, gy - 8.5
    rim = s.ell(wcx, wcy, 9, 9) & ~s.ell(wcx, wcy, 7, 7)
    s.fill(rim, WOOD, 2.4 + 1.3 * round_tone(s, wcx, wcy, 9, 9))
    for a in (0.3, 1.35, 2.4, 4.5, 5.55):
        s.fill(s.line((wcx - 0.5, wcy - 0.5), (wcx - 0.5 + 7 * np.cos(a), wcy - 0.5 + 7 * np.sin(a))), WOOD, 2.2)
    s.fill(s.ell(wcx, wcy, 2, 2), TIN, 2.5)
    s.put(int(wcx) - 1, int(wcy) - 1, TIN[4])
    cr = s.rect(95, gy - 10, 108, gy)
    s.fill(cr, WOOD, 2.6 + 0.9 * (s.yy == gy - 10) - 0.9 * ((s.yy - gy) % 4 == 3) - 0.5 * (s.xx > 104))
    s.fill(s.rect(95, gy - 10, 95, gy) | s.rect(108, gy - 10, 108, gy), WOOD, 1.6)
    can = s.rect(99, gy - 15, 102, gy - 11)
    s.fill(can, TIN, 2 + (s.xx == 99) - (s.xx == 102))
    s.fill(s.line((103, gy - 14), (105, gy - 16)), TIN, 2)
    stamp(s, GEAR, 103, gy - 15, TIN)

    despeckle(s)
    sink_bottom(s, 4, 0.45)
    return s


# ================================================================ 空屋

def empty_house():
    """空屋：很久没人回来了。冷灰的横板墙，屋顶塌了一点、长满苔、缺瓦；一扇窗钉死，一扇窗里窗帘拉着；
    门关着，门上方原来挂牌子的地方留下一块干净的印子；门槛上一层厚灰，草从墙根和台阶缝里长出来。
    烟囱是冷的。整体比树屋暗、冷。"""
    W, Hh = 110, 80
    s = Spr(W, Hh)
    gy = Hh - 1
    nz = noise(s, 7)
    # 墙：横着的搭接板，每块板下沿压一条暗缝；左边亮
    wall = s.rect(12, 28, 97, gy)
    u, v = bbox_uv(s, wall)
    wt = 2.6 - 1.4 * u - 1.0 * ((s.yy - 28) % 5 == 4) + 0.5 * ((s.yy - 28) % 5 == 0)
    s.fill(wall, WOOD_C, wt - 0.2 + nz * 0.3)
    for x, y0, y1 in ((30, 28, 45), (71, 50, 70)):      # 两块翘起来、颜色不一样的板
        s.fill(s.rect(x, y0, x + 9, y0 + 3), WOOD_C, 3.2 - 1.4 * (x / 97))
    # 墙角柱
    s.fill(s.rect(12, 28, 13, gy), WOOD_C, 3.4)
    s.fill(s.rect(96, 28, 97, gy), WOOD_C, 0.8)

    # 屋顶：瓦片一排排，中间塌下去一点；苔藓一块块；左边缺了几片，露出椽子
    roof = s.poly([(2, 30), (108, 30), (96, 6), (14, 6)])
    sag = np.round(2.2 * np.sin(np.pi * np.clip((s.xx - 14) / 82, 0, 1)) ** 2).astype(int)
    roof = roof & (s.yy >= 6 + sag)
    rr = (s.yy - 6 - sag)
    rt = 3.0 - 1.2 * (s.xx / W) + 0.4 * (rr < 6)
    rt = rt - 1.1 * (rr % 5 == 4) - 1.0 * (((s.xx + (rr // 5) * 3) % 7) == 0)
    s.fill(roof, WOOD_C, rt - 0.2 + nz * 0.3)
    eave_b = s.rect(2, 29, 108, 31)
    s.fill(eave_b & roof | s.rect(2, 30, 108, 31), WOOD_C, 1.4 - 0.6 * (s.yy == 31))
    hole = s.poly([(26, 16), (40, 14), (42, 22), (30, 24)]) & roof
    s.fill(hole, BARK, 0.3)
    s.fill(hole & ((s.xx == 33) | (s.yy == 19)), WOOD_C, 1.0)    # 露出来的椽子
    mz = noise(s, 9, 3)
    mossm = clean(roof & (mz > 0.18) & ~hole)
    s.fill(mossm, MOSS, 1.6 + 1.0 * (s.xx < 50) + 0.6 * (rr < 8))
    tp, _, _, _ = edges(roof)
    s.fill(tp & (mz > -0.2), MOSS, 2.4)
    for x in (8, 9, 22, 47, 48, 66, 90, 91, 100):     # 檐口挂下来的苔
        for k in range((x * 7) % 3 + 1):
            s.put(x, 32 + k, MOSS[1])
    # 檐下的硬影
    tint(s, wall & (s.yy >= 32) & (s.yy <= 34), BARK[0], 0.45)
    # 冷的烟囱：石头砌的，顶上掉了两块
    ch = s.rect(78, 0, 87, 12) & ~s.rect(78, 0, 80, 1) & ~s.rect(86, 0, 87, 0)
    ct = 2.0 + 1.0 * (s.xx < 81) - 0.9 * (s.xx > 85) - 0.8 * ((s.yy % 3 == 2) | (((s.xx + (s.yy // 3) * 2) % 5) == 0))
    s.fill(ch & (s.yy < 8 + sag), STONE, ct)

    # 门：关着，冷的竖板；门上方原来挂牌子的地方一块干净的印子，两个钉子眼
    dx0, dx1, dtop = 44, 65, 33
    door = s.rect(dx0, dtop, dx1, gy)
    frame = dilate(door, 2) & ~door & (s.yy <= gy) & (s.yy >= dtop - 2)
    s.fill(frame, WOOD_C, 3.0 + 0.8 * (s.xx < dx0) - 1.0 * (s.xx > dx1))
    dt = 1.4 + 0.5 * ((s.xx - dx0) // 7 == 1) - 1.0 * (((s.xx - dx0) % 7) == 6)
    s.fill(door, WOOD_C, dt)
    for ry in (dtop + 6, gy - 9):
        s.fill(door & (s.yy >= ry) & (s.yy <= ry + 1), WOOD_C, 2.2 - (s.yy == ry + 1) * 0.8)
    s.put(dx1 - 3, 57, TIN[2])
    s.put(dx1 - 3, 58, TIN[0])
    tint(s, door & (s.yy <= dtop + 2), BARK[0], 0.35)   # 檐影落在门顶
    plate = s.rect(49, 28, 60, 30)
    s.fill(plate, WOOD_C, 3.3)
    s.put(50, 29, WOOD_C[1])
    s.put(59, 29, WOOD_C[1])
    # 门槛：一块厚木板，上面一层灰，灰上没有脚印；台阶缝里长草
    th = s.rect(40, gy - 2, 69, gy)
    s.fill(th, WOOD_C, 2.0 - 1.0 * (s.yy == gy))
    dust = s.rect(41, gy - 4, 68, gy - 2) & ~(s.rect(41, gy - 4, 68, gy - 4) & ((((s.xx * 5) % 7) < 3) | (s.xx < 43) | (s.xx > 66)))
    s.fill(dust, DUST, 1.2 + (s.yy <= gy - 3) * 0.9 + 0.4 * (s.xx < 52) - 0.6 * (s.xx > 62) - 0.8 * (s.yy == gy - 2))
    for x in (47, 58, 63):
        s.put(x, gy - 4 + (x == 58), DUST[0])   # 几片落叶
    s.put(53, gy - 2, mixc(DUST[0], from_hex("#3b2f26"), 0.5))

    # 窗：左边钉死（两块斜木），右边窗帘拉着、一角破了
    for wx0 in (19, 75):
        wm = s.rect(wx0, 40, wx0 + 13, 54)
        s.fill(wm, WOOD_C, 3.0 - 1.2 * ((s.xx == wx0 + 13) | (s.yy == 54)))
        s.fill(s.rect(wx0 + 1, 41, wx0 + 12, 53), BARK, 0.6 + 0.6 * (s.xx < wx0 + 4))
        s.fill(s.rect(wx0 - 1, 55, wx0 + 14, 55), WOOD_C, 3.4)
    s.fill(s.line((20, 42), (31, 52)), WATER, 1)                     # 裂了的玻璃
    for a, b in (((17, 43), (35, 50)), ((17, 50), (35, 44))):
        bm = s.stroke([a, b], 2.4, 2.4)
        s.fill(bm, WOOD_C, 2.6 - 1.0 * edges(bm)[1])
    for px_, py_ in ((19, 43), (33, 49), (19, 49), (33, 44)):
        s.put(px_, py_, WOOD_C[4])
    cur = s.rect(77, 41, 87, 53) & ~s.poly([(84, 53), (88, 46), (88, 54)])
    s.fill(cur, WOOD_C, 1.0 + 0.6 * ((s.xx - 77) % 3 == 0))
    s.fill(s.rect(76, 41, 88, 41), WOOD_C, 0.4)

    # 墙根的草和蕨：没人收拾
    rng = np.random.default_rng(5)
    for x in list(range(12, 40)) + list(range(70, 99)):
        if rng.random() < 0.55:
            hgt = int(rng.integers(1, 5 if x < 26 or x > 88 else 3))
            for k in range(hgt):
                s.put(x + (1 if k == hgt - 1 and rng.random() < 0.3 else 0), gy - k, MOSS[1 + (k == hgt - 1) + (x < 30)])
    for x, hh in ((39, 4), (70, 5), (71, 3)):
        for k in range(hh):
            s.put(x, gy - 1 - k, MOSS[2])
    despeckle(s)
    sink_bottom(s, 3, 0.4)
    return s


def empty_item():
    """门边早就放好的东西：一个纸包，包装纸褪了色（发灰、发白，顶上落了灰，边角泡过水），
    但捆它的细绳比纸新一档——颜色还实、没落灰，顶上一个刚系过的结，两个绳头翘着。挂一张小纸牌。"""
    s = Spr(12, 10)
    box = s.rect(1, 3, 9, 9)
    u, v = bbox_uv(s, box)
    s.fill(box, DUST, 1.6 - 1.2 * u - 0.6 * (s.yy == 9))             # 褪了色的包装纸
    s.fill(s.rect(1, 3, 9, 3), DUST, 2 - 0.8 * (s.xx > 6))             # 顶上的灰
    s.fill(s.rect(1, 8, 3, 9) | s.rect(8, 9, 9, 9), DUST, 0)            # 泡过水的边角，发暗
    s.fill(s.rect(5, 3, 5, 9) | s.rect(1, 6, 9, 6), WOOD, 1.2)          # 新一点的细绳：颜色实、压在灰上面
    s.put(5, 6, WOOD[0])
    s.put(5, 2, WOOD[3])                                                # 绳结和两个翘起来的绳头
    s.put(4, 2, WOOD[1])
    s.put(6, 2, WOOD[1])
    s.put(3, 1, WOOD[2])
    s.put(7, 1, WOOD[2])
    s.put(10, 7, WOOD[1])
    s.fill(s.rect(10, 8, 11, 9), TAG, 1)                              # 纸牌
    s.put(11, 9, TAG[0])
    return s


def pump():
    """水泵（修好的）：铸铁泵身、往左上翘的压柄、右边的出水嘴，中间一道新铜箍；也当背包图标。"""
    s = Spr(16, 16)
    body = s.rect(5, 4, 9, 13)
    s.fill(body, TIN, 2.0 + 1.2 * (s.xx == 5) + 0.6 * (s.xx == 6) - 1.0 * (s.xx == 9))
    s.fill(s.rect(4, 3, 10, 4), TIN, 2.4 + 1.2 * (s.yy == 3) - 0.6 * (s.xx > 8))
    s.fill(s.rect(6, 2, 8, 2), TIN, 3)
    handle = s.stroke([(7, 2.5), (4, 1), (0.5, 0.5)], 1.6, 1.4)
    s.fill(handle, TIN, 3.2 - 1.0 * edges(handle)[1])
    s.put(7, 1, TIN[1])
    spout = s.rect(10, 6, 13, 7)
    s.fill(spout, TIN, 2.2 + (s.yy == 6) - (s.yy == 7) * 0.6)
    s.fill(s.rect(13, 8, 13, 8), TIN, 1)
    s.fill(s.rect(5, 9, 9, 10), COPPER, 1.6 + (s.xx == 5) - (s.xx == 9) - (s.yy == 10) * 0.6)
    base = s.rect(3, 14, 11, 15)
    s.fill(base, STONE, 2.2 + (s.yy == 14) - 0.8 * (s.xx > 9))
    s.put(4, 14, TIN[3])
    s.put(10, 14, TIN[1])
    return s


# ================================================================ 旧商店

def shop():
    """旧商店（卖饼的）：灰青的旧漆门脸一块块剥落露出木头；招牌上画的饼褪了色；
    橱窗里两层空架子、一只罩着玻璃盖的空蛋糕托；破了的小雨棚垂着几条；门上挂着歪了的牌子，门把那块被摸得亮一点；
    门边一块折叠的菜单板，字已经看不清。"""
    W, Hh = 100, 80
    s = Spr(W, Hh)
    gy = Hh - 1
    rng = np.random.default_rng(13)
    face = s.rect(5, 12, 92, gy) | s.rect(26, 2, 71, 12) | s.poly([(16, 12), (26, 6), (26, 12)]) | s.poly([(71, 6), (81, 12), (71, 12)])
    u, v = bbox_uv(s, face)
    seam = ((s.xx - 5) % 6) == 5
    s.fill(face, PAINT, 2.7 - 1.5 * u - 0.9 * seam)
    # 剥落的漆：几大片露出底下的木头，多在下半截和边角（雨水溅到的地方）
    pn = noise(s, 17, (5, 7)) + 0.25 * (v > 0.7) + 0.2 * ((u < 0.08) | (u > 0.92))
    peel = clean(clean(face & (pn > 0.3)))
    s.fill(peel, WOOD, 2.5 - 1.3 * u - 0.9 * seam)
    s.fill(edges(peel)[0] & ~seam, PAINT, 3.4 - 1.5 * u)    # 翘起来的漆边，上沿接到光
    tp, _, _, _ = edges(face)
    s.fill(tp, PAINT, 4)
    s.fill(s.rect(5, 12, 6, 12) | s.rect(26, 2, 27, 2), PAINT, 4)
    # 招牌：一块横板，上面一个褪色的圆饼 + 看不清的字（只剩几道笔画）
    sign = s.rect(20, 7, 77, 17)
    s.fill(sign, WOOD, 2.2 + 1.2 * (s.yy == 7) - 1.0 * (s.yy == 17) - 0.6 * (s.xx > 60))
    cake = s.ell(30, 12.5, 4, 3)
    s.fill(cake, COPPER, 1.4 + round_tone(s, 30, 12.5, 4, 3))
    s.fill(s.rect(27, 12, 33, 12), COPPER, 0.4)          # 饼中间一道夹心
    s.put(28, 11, COPPER[2])
    for (x, y, ln) in ((38, 10, 4), (44, 10, 2), (48, 10, 5), (55, 10, 3), (61, 10, 2), (65, 10, 4),
                       (38, 13, 2), (42, 13, 6), (51, 13, 3), (57, 13, 5), (64, 13, 3), (39, 11, 1), (49, 12, 1), (58, 11, 1)):
        s.fill(s.rect(x, y, x + ln - 1, y), WOOD, 1.0 if x < 60 else 1.4)
    for x in (21, 76):
        s.put(x, 8, TIN[3])
    tint(s, face & (s.yy >= 18) & (s.yy <= 19), BARK[0], 0.4)
    # 雨棚：斜着的条纹帆布，从墙上伸出来盖住橱窗；褪色、破了个洞，前沿撕成几条垂下来
    awn = s.rect(6, 20, 51, 29)
    stripe = ((s.xx - 6) // 5) % 2                       # 正侧面：竖条纹，不斜
    at = 3.0 - 1.4 * (s.xx / 60) + 0.7 * (s.yy < 23) - 0.9 * (s.yy >= 27)
    s.fill(awn & (stripe == 0), AWN, at)
    s.fill(awn & (stripe == 1), AWN_W, at)
    s.fill(s.rect(6, 29, 51, 29), AWN_W, 1.2)
    hole = s.poly([(27, 22), (33, 22), (32, 26), (28, 26)])
    s.clear(hole)
    s.fill(dilate(hole, 1) & awn & ~hole & (s.yy > 22), AWN, 0.6)
    def strips():
        for x, ln in ((8, 4), (14, 2), (19, 3), (24, 7), (25, 6), (36, 3), (41, 5), (47, 2), (50, 4)):
            for k in range(ln):
                s.put(x + (k > 3), 30 + k, (AWN if (x // 5) % 2 else AWN_W)[1 + (k < 2)])
    strips()
    tint(s, face & (s.yy >= 30) & (s.yy <= 32) & (s.xx < 52) & (s.xx > 6), BARK[0], 0.4)
    # 橱窗
    wx0, wy0, wx1, wy1 = 11, 35, 45, 63
    s.fill(s.rect(wx0 - 2, wy0 - 2, wx1 + 2, wy1 + 2), WOOD, 3.4 - 1.4 * ((s.xx > wx1) | (s.yy > wy1)))
    gl = s.rect(wx0, wy0, wx1, wy1)
    s.fill(gl, BARK, 1.2 - 0.6 * (s.yy < wy0 + 4))
    for sy in (wy0 + 10, wy0 + 20):
        s.fill(s.rect(wx0, sy, wx1, sy), WOOD, 1.6)
        s.fill(s.rect(wx0, sy + 1, wx1, sy + 1), BARK, 0.2)
    stand = s.rect(34, wy0 + 17, 35, wy0 + 19) | s.rect(31, wy0 + 16, 38, wy0 + 16)
    s.fill(stand, TIN, 1.6)
    dome = s.ell(34.5, wy0 + 15, 4, 4.5) & (s.yy <= wy0 + 15) & ~s.ell(34.5, wy0 + 15, 3, 3.5)
    s.fill(dome, WATER, 1)
    s.put(32, wy0 + 12, WATER[2])
    for k in range(5):                      # 玻璃上的灰和一道反光
        s.put(wx0 + 3 + k, wy0 + 26 - k, WATER[1])
        s.put(wx0 + 6 + k, wy0 + 26 - k, WATER[0])
    s.fill(s.rect(wx0 - 2, wy1 + 3, wx1 + 2, gy), WOOD, 2.0 - 0.9 * (((s.xx - wx0) % 6) == 5) - 0.8 * u)
    s.fill(s.rect(wx0 - 3, wy1 + 2, wx1 + 3, wy1 + 2), WOOD, 4.2)
    strips()
    # 门：上半截一块小玻璃，挂着歪了的牌子；门把那里被摸得亮一点；门上方一只小铃
    dx0, dx1, dtop = 55, 76, 31
    s.fill(dilate(s.rect(dx0, dtop, dx1, gy), 2) & (s.yy <= gy), PAINT, 3.4 - 1.2 * (s.xx > dx1) + 0.6 * (s.xx < dx0))
    door = s.rect(dx0, dtop, dx1, gy)
    s.fill(door, PAINT, 1.4 - 0.9 * (((s.xx - dx0) % 7) == 6))
    s.fill(door & (noise(s, 23, 3) > 0.3), WOOD, 1.4)
    s.fill(s.rect(dx0 + 4, dtop + 4, dx1 - 4, dtop + 17), PAINT, 3)
    s.fill(s.rect(dx0 + 5, dtop + 5, dx1 - 5, dtop + 16), BARK, 0.9)
    s.put(dx0 + 6, dtop + 6, WATER[1])
    s.put(dx0 + 7, dtop + 6, WATER[1])
    s.put(dx0 + 6, dtop + 7, WATER[1])
    s.fill(s.line((dx0 + 7, dtop + 18), (dx0 + 10, dtop + 15), (dx0 + 13, dtop + 19)), WOOD, 1)
    plate = s.poly([(dx0 + 4, dtop + 19), (dx0 + 16, dtop + 21), (dx0 + 15, dtop + 26), (dx0 + 3, dtop + 24)])
    s.fill(plate, WOOD, 3.0 - 0.9 * edges(plate)[1])
    s.fill(s.line((dx0 + 6, dtop + 22), (dx0 + 12, dtop + 23)), WOOD, 1.2)
    s.fill(s.rect(dx1 - 4, 54, dx1 - 3, 57), PAINT, 4)       # 被摸亮的那块
    s.put(dx1 - 3, 55, TIN[4])
    s.put(dx1 - 3, 56, TIN[1])
    s.fill(s.rect(dx0 + 9, dtop - 6, dx0 + 12, dtop - 4), COPPER, 1 + (s.xx == dx0 + 9))
    s.put(dx0 + 10, dtop - 7, TIN[2])
    s.put(dx0 + 11, dtop - 3, COPPER[0])
    # 台阶
    st = s.rect(dx0 - 4, gy - 2, dx1 + 4, gy)
    s.fill(st, STONE, 1.6 + 1.4 * (s.yy == gy - 2) - 0.8 * (s.xx > dx1))
    # 折叠菜单板，靠在门右边
    board = s.poly([(81, 51), (91, 51), (94, gy + 1), (79, gy + 1)])
    s.fill(board, WOOD, 2.4 - 1.2 * edges(board)[1])
    inner = s.poly([(83, 54), (89, 54), (91, gy - 3), (82, gy - 3)])
    s.fill(inner, BARK, 1.0)
    for y in (58, 62, 66, 70):
        s.fill(s.rect(84 + (y % 3), y, 87 + (y % 2), y), WOOD, 1.8)
    s.fill(s.rect(90, 54, 90, 56), TAG, 0)
    despeckle(s)
    sink_bottom(s, 3, 0.4)
    return s


# ================================================================ 小吃棚

def stall():
    """废弃的小吃棚：两根柱子撑着一片条纹雨棚（褪色、往下坠、破了一个洞、右边撕下来一片），
    棚下柜台上一口大锅和一摞碗，棚边挂着三只没点的纸灯笼和一块菜牌；左边一条长凳（下雨时大家挤在这里），
    一只凳子翻倒在地上。"""
    W, Hh = 94, 78
    s = Spr(W, Hh)
    gy = Hh - 1
    nz = noise(s, 19)
    # 后板：棚下的阴影里
    back = s.rect(10, 16, 83, gy - 26)
    s.fill(back, WOOD, 1.2 - 0.9 * (((s.xx - 10) % 6) == 5) + nz * 0.4)
    for x in (24, 46, 61):                        # 后板上的挂钩和挂着的勺子剪影
        s.put(x, 30, TIN[2])
    s.fill(s.rect(46, 31, 46, 36) | s.rect(45, 37, 47, 38), TIN, 1)
    s.fill(s.rect(60, 31, 62, 31) | s.rect(61, 32, 61, 35), TIN, 1)
    # 柱子
    for x0 in (6, 84):
        p = s.rect(x0, 14, x0 + 3, gy)
        s.fill(p, WOOD, 3.0 + 0.9 * (s.xx == x0) - 1.2 * (s.xx == x0 + 3) - (x0 > 50) * 0.5)
    # 柜台
    ct = s.rect(34, gy - 27, 82, gy)
    s.fill(ct, WOOD, 2.2 - 0.9 * (((s.xx - 34) % 6) == 5) - 0.6 * (s.xx > 70) + nz * 0.4)
    s.fill(s.rect(32, gy - 29, 84, gy - 27), WOOD, 3.8 - 1.4 * (s.yy == gy - 27) - 0.5 * (s.xx > 72))
    s.fill(s.rect(34, gy - 18, 82, gy - 17), WOOD, 2.9 - (s.yy == gy - 17) * 1.0)
    # 锅、碗
    pot = s.rect(60, gy - 37, 72, gy - 30)
    s.fill(pot, TIN, 2.2 + 1.0 * (s.xx < 63) - 1.0 * (s.xx > 69) - 0.6 * (s.yy == gy - 30))
    s.fill(s.rect(59, gy - 38, 73, gy - 38), TIN, 3.2 - (s.xx > 70))
    s.fill(s.rect(65, gy - 40, 67, gy - 39), TIN, 2.6)
    s.put(58, gy - 35, TIN[1])
    s.put(74, gy - 35, TIN[1])
    for k, y in enumerate((gy - 31, gy - 33, gy - 35)):
        s.fill(s.rect(40 + k, y, 47 - k, y + 1), WOOD_C, 3.4 - (s.yy == y + 1) * 1.2)
    # 雨棚：条纹布，往下坠；前沿一圈波浪边
    canvas = s.rect(1, 5, 93, 22) & ~s.rect(1, 5, 2, 5) & ~s.rect(92, 5, 93, 5)
    sag = np.round(2.0 * np.sin(np.pi * np.clip((s.xx - 6) / 82, 0, 1))).astype(int)
    canvas &= s.yy <= 22 + sag
    stripe = ((s.xx - 1) // 8) % 2                       # 正侧面：竖条纹，不斜
    at = 2.8 - 1.2 * (s.xx / W) + 0.8 * (s.yy < 9) - 0.6 * (s.yy > 17 + sag)
    a1 = canvas & (stripe == 0)
    a2 = canvas & (stripe == 1)
    s.fill(a1, AWN, at)
    s.fill(a2, AWN_W, at)
    tp, _, _, _ = edges(canvas)
    s.fill(tp & a1, AWN, 4)
    s.fill(tp & a2, AWN_W, 4)
    val = np.zeros((Hh, W), bool)
    for x in range(1, 93):
        k = (x - 1) % 8
        depth = 4 if k in (2, 3, 4, 5) else (3 if k in (1, 6) else 2)
        y0 = 23 + sag[0, x]
        val[y0:y0 + depth, x] = True
    s.fill(val & (((s.xx - 1) // 8) % 2 == 0), AWN, 2.6 - 1.0 * edges(val)[1] - 0.6 * (s.xx > 60))
    s.fill(val & (((s.xx - 1) // 8) % 2 == 1), AWN_W, 2.6 - 1.0 * edges(val)[1] - 0.6 * (s.xx > 60))
    # 破洞（透出后面的雾）和撕下来的一片
    s.clear(s.poly([(56, 9), (63, 8), (65, 13), (58, 15)]))
    s.fill(dilate(s.poly([(56, 9), (63, 8), (65, 13), (58, 15)]), 1) & canvas & ~s.poly([(56, 9), (63, 8), (65, 13), (58, 15)]), AWN_W, 1)
    s.clear(s.rect(80, 23, 93, 28))
    flap = s.poly([(80, 22), (88, 22), (86, 34), (83, 38), (81, 31)])
    s.fill(flap, AWN_W, 2.0 - 0.9 * (s.xx > 85) - 0.8 * edges(flap)[1])
    # 棚下的硬影：落在后板上沿和柜台顶的后半
    tint(s, s.mask & (s.yy >= 27) & (s.yy <= 30) & (s.xx > 9) & (s.xx < 84) & ~val, BARK[0], 0.4)
    # 纸灯笼（没点，褪色的暖色，很小）和菜牌
    for x in (18, 40, 72):
        y = 26 + sag[0, x] + (4 if ((x - 1) % 8) in (2, 3, 4, 5) else 2)
        s.put(x, y, WOOD[2])
        s.put(x, y + 1, WOOD[2])
        lan = s.ell(x + 0.5, y + 5, 2.5, 3.2)
        s.fill(lan, COPPER, 0.8 + 0.9 * round_tone(s, x + 0.5, y + 5, 2.5, 3.2))
        s.fill(s.rect(x - 1, y + 2, x + 1, y + 2) | s.rect(x - 1, y + 8, x + 1, y + 8), WOOD, 1)
    mb = s.rect(50, 34, 58, 41)
    s.fill(s.line((51, 30), (51, 33)) | s.line((57, 30), (57, 33)), WOOD, 2)
    s.fill(mb, WOOD, 3.0 - 1.0 * (s.yy == 41) - 0.5 * (s.xx > 55))
    for y in (36, 38):
        s.fill(s.rect(52, y, 52 + (y % 5), y), WOOD, 1.2)
    # 长凳（左边，棚下）和翻倒的凳子
    bench = s.rect(10, gy - 12, 31, gy - 10)
    s.fill(bench, WOOD, 3.6 - 1.2 * (s.yy == gy - 10))
    for x in (12, 28):
        s.fill(s.rect(x, gy - 9, x + 1, gy), WOOD, 2.0 + (s.xx == x))
    # 翻倒的凳子：凳面着地，三条腿朝天
    seat = s.rect(38, gy - 2, 48, gy)
    s.fill(seat, WOOD, 3.4 - 1.0 * (s.yy == gy) + 0.6 * (s.xx < 41))
    for lx_, top in ((39, gy - 10), (43, gy - 11), (47, gy - 9)):
        s.fill(s.line((lx_, gy - 3), (lx_ + (1 if lx_ > 44 else 0), top)), WOOD, 3.6 if lx_ < 44 else 2.6)
    s.fill(s.rect(40, gy - 7, 46, gy - 7), WOOD, 2.4)
    # 地上的杂草
    rng = np.random.default_rng(3)
    for x in range(0, W):
        if rng.random() < 0.25:
            for k in range(int(rng.integers(1, 3))):
                s.put(x, gy - k, MOSS[1 + k])
    despeckle(s)
    sink_bottom(s, 3, 0.4)
    return s


# ================================================================ 倒木

def _log_body(s, x0, x1, y0, d, seed, sunk=0):
    """横着的大树干：顶上受光（苔藓），往下暗；横向的长树皮裂纹。sunk：下面埋进土里的行数（不画）。"""
    nz = noise(s, seed)
    rng = np.random.default_rng(seed)
    m = np.zeros((s.h, s.w), bool)
    for x in range(x0, x1 + 1):
        wob = int(round(0.8 * np.sin(x / 11)))
        m[y0 + wob:y0 + d + wob - sunk, x] = True
    vv = np.zeros((s.h, s.w))
    for x in range(x0, x1 + 1):
        ys = np.nonzero(m[:, x])[0]
        if len(ys):
            vv[ys, x] = (ys - ys.min()) / d
    t = 5.0 - 5.2 * vv ** 0.9 + nz * 0.7
    for k in range(9):                      # 横裂纹
        yy = y0 + int(rng.integers(3, d - 3))
        xa = int(rng.integers(x0, x1 - 20))
        ln = int(rng.integers(12, 40))
        sel = m & (s.yy == yy + np.round(0.8 * np.sin(s.xx / 11)).astype(int)) & (s.xx >= xa) & (s.xx < xa + ln)
        t[sel] -= 1.6
        t[shift(sel, 0, -1) & m] += 0.5
    s.fill(m, BARK, t)
    top, _, _, _ = edges(m)
    mz = noise(s, seed + 3, 3)
    s.fill(dilate(top, 1) & m & (mz > -0.05) & (s.yy <= y0 + 3), MOSS, 2.2 + (mz > 0.2))
    return m


def _torn_end(s, body, x0, seed):
    """倒木的根头（正侧面，不画切面）：参差撕开的轮廓，夹着带土的根团，压暗。"""
    rng = np.random.default_rng(seed)
    for y in np.unique(np.nonzero(body)[0]):
        cut = int(rng.integers(0, 5))
        s.clear(body & (s.yy == y) & (s.xx < x0 + cut))
        body[y, :x0 + cut] = False
    end = body & (s.xx < x0 + 7)
    s.fill(end, BARK, 1.2 - 0.6 * (s.xx < x0 + 4))
    clods = end & (noise(s, seed, (2, 3)) > 0.15)
    s.fill(clean(clods, 1), SOIL, 3)


def log_block():
    """倒木挡路：一棵大树倒在路上，比晨的腰还高。左头是撕裂的树根，右头是折断的白茬，背上两根断枝朝天。"""
    W, Hh = 122, 38
    s = Spr(W, Hh)
    gy = Hh - 1
    body = _log_body(s, 12, 106, 10, 27, 71)
    # 左头：根盘撕裂，几根根须
    for pts, w0, w1 in (([(16, 14), (8, 8), (3, 2)], 4, 1), ([(14, 22), (6, 21), (1, 17)], 4, 1),
                        ([(14, 30), (6, 33), (2, 37)], 4, 2), ([(16, 18), (9, 15), (5, 12)], 3, 1)):
        rm = s.stroke(pts, w0, w1) & ~body
        s.fill(rm, BARK, 2.6 - 1.2 * edges(rm)[1] + 0.8 * edges(rm)[0])
    _torn_end(s, body, 12, 7)
    # 右头：折断的茬，木头是浅的，参差
    snap = np.zeros((Hh, W), bool)
    rng = np.random.default_rng(4)
    for y in range(11, 37):
        ext = int(rng.integers(0, 6)) + (3 if 14 < y < 26 else 0)
        snap[y, 104:107 + ext] = True
    s.fill(snap & ~body | (snap & (s.xx > 103)), DRY, 2.4 + 1.0 * (s.yy < 20) - 1.4 * ((s.yy % 4) == 0) + 0.6 * (s.xx < 106))
    # 背上的断枝
    for pts, w0, w1 in (([(40, 12), (36, 5), (33, 0)], 4, 2), ([(78, 12), (83, 6), (85, 2)], 3, 2)):
        bm = s.stroke(pts, w0, w1) & ~(body & (s.yy > 13))
        s.fill(bm, BARK, 3.4 - 1.4 * edges(bm)[3] + 0.8 * edges(bm)[2])
        s.fill(edges(bm)[0], DRY, 2)
    # 垂下来的苔
    for x, ln in ((30, 3), (31, 5), (55, 2), (68, 4), (69, 2), (92, 3)):
        yb = np.nonzero(body[:, x])[0].max()
        for k in range(ln):
            s.put(x, yb - 3 + k, MOSS[1 + (k < 2)])
    despeckle(s)
    sink_bottom(s, 4, 0.45)
    return s


def log_moved():
    """推开以后：倒木滚进路边的低处、陷下去一半，上沿只到晨的膝盖；断枝朝向前面，压出一道土。"""
    W, Hh = 122, 20
    s = Spr(W, Hh)
    gy = Hh - 1
    body = _log_body(s, 12, 106, 3, 27, 71, sunk=10)
    _torn_end(s, body, 12, 7)
    snap = np.zeros((Hh, W), bool)
    rng = np.random.default_rng(4)
    for y in range(4, Hh):
        snap[y, 104:107 + int(rng.integers(0, 6))] = True
    s.fill(snap & (s.xx > 103), DRY, 2.4 + 1.0 * (s.yy < 9) - 1.4 * ((s.yy % 4) == 0))
    bm = s.stroke([(46, 6), (40, 4), (33, 4)], 3, 2)
    s.fill(bm, BARK, 3.0 - 1.4 * edges(bm)[1])
    # 被压起来的土
    mound = np.zeros((Hh, W), bool)
    for x in range(4, 118):
        h_ = 2 + int(round(1.2 * np.sin(x / 5) + 1.0 * np.sin(x / 13)))
        mound[gy - max(1, h_) + 1:, x] = True
    mound &= ~(body & (s.yy < gy - 3))
    s.fill(mound, SOIL, 2.4 + edges(mound)[0] * 0.8)
    s.fill(edges(mound)[0] & (noise(s, 9) > 0.1), MOSS, 1)
    sink_bottom(s, 3, 0.4)
    return s


def branch_piece(seed, kind):
    """压在倒木下的轻树枝：干透了、发灰，一根主枝 + 几个杈，一看就拖得动。"""
    s = Spr(36, 10)
    if kind == "a":
        main = s.stroke([(1, 8), (16, 6.5), (34, 5)], 2.6, 1.4)
        twigs = [([(12, 7), (15, 3), (17, 1)], 1.3, 1), ([(24, 6), (28, 3), (31, 2)], 1.2, 1), ([(30, 5), (34, 7)], 1, 1)]
    else:
        main = s.stroke([(2, 6), (14, 8), (26, 6.5), (35, 3)], 2.4, 1.2)
        twigs = [([(8, 7), (6, 3), (5, 1)], 1.3, 1), ([(18, 7.5), (21, 4), (22, 2)], 1.2, 1), ([(27, 6), (31, 8.5)], 1, 1),
                 ([(20, 5), (24, 2)], 1, 1)]
    s.fill(main, DRY, 2.2 + 1.0 * edges(main)[0] - 1.2 * edges(main)[1])
    for pts, w0, w1 in twigs:
        tm = s.stroke(pts, w0, w1) & ~main
        s.fill(tm, DRY, 2.6 - 0.8 * (np.asarray(pts)[0][0] > 25))
    for x, y in ((0, 7) if kind == "a" else (1, 5),):    # 断口
        s.put(x, y, DRY[3])
    sink_bottom(s, 2, 0.3)
    return s


# ================================================================ 旧路上的线索

RAG = H("#4a2724", "#62302b", "#783c33", "#8a4b3e")   # 路标布条：褪色的红，比晨的斗篷暗、灰，比身后的雾亮一点点，靠色相跳出来


def cloth():
    """路标：一棵从地上长出来的细枯树（比晨略高），齐胸高的地方往右横伸出一根枝杈，
    杈上系着一条褪色的红布条，打了个结，布尾垂下来；帧 0 垂着，帧 1 被风吹起来往右飘。
    一整样东西自己立在地上，一眼读出「有人系在树枝上做的记号」。底边那一行就是地面。"""
    W, Hh = 26, 54
    gy = Hh - 1
    frames = []
    for f in range(2):
        s = Spr(W, Hh)
        # 树干：底下粗、往上细，有点歪；左边受光
        trunk = s.stroke([(8, gy + 1), (8.5, 34), (10.5, 3)], 3.4, 1.2)
        s.fill(trunk, DRY, 1.4 + 1.3 * edges(trunk)[2] - 0.6 * (s.yy > gy - 8))
        for pts, w0 in ((((7, gy - 1), (3, gy)), 2.0), (((9, gy - 1), (13, gy)), 1.8)):   # 根
            s.fill(s.stroke(list(pts), w0, 1), DRY, 1.0)
        # 树梢几根细枝、左边一截断掉的枝桩
        for pts in (((10, 9), (6, 4), (5, 1)), ((10.5, 6), (13, 2)), ((9, 21), (5, 18))):
            m = s.stroke(list(pts), 1.1, 1) & ~trunk
            s.fill(m, DRY, 1.8)
        s.put(4, 17, DRY[2])
        # 齐胸高的枝杈（往右横伸，末梢往上翘一点）
        br = s.stroke([(9, 18), (15, 16), (21, 15), (23, 12)], 1.8, 1.0) & ~trunk
        s.fill(br, DRY, 2.0 + 1.0 * edges(br)[0])
        # 布条：结在枝杈上（x≈16），布尾
        knot = s.rect(15, 15, 17, 17)
        s.fill(knot, RAG, 2 - (s.yy == 17) - (s.xx == 17) * 0.5)
        s.put(15, 15, RAG[3])
        if f == 0:   # 垂着：两条布尾，长的那条微微往右弯
            tail = s.poly([(15, 18), (18, 18), (19, 24), (20, 30), (18, 31), (17, 25)])
            tail2 = s.poly([(14, 18), (15.5, 18), (15.5, 25), (14, 23)])
        else:        # 被风吹起来：往右上飘，尾巴分叉
            tail = s.poly([(17, 15), (21, 14), (26, 12), (26, 15), (23, 17), (21, 19), (17, 18)])
            tail2 = s.poly([(16, 18), (19, 20), (23, 22), (21, 23), (16, 20)])
        s.fill(tail, RAG, 2.4 - 1.4 * edges(tail)[1] - 0.6 * (s.xx > 22) + 0.8 * edges(tail)[0])
        s.fill(tail2 & ~tail, RAG, 1.2 - 0.6 * edges(tail2)[1])
        sink_bottom(s, 3, 0.35)
        frames.append(s)
    return frames


def preview_cloth(d):
    """布条单独一张：雾里的森林 + 晨站在旁边，3 倍；右上角放大 2 帧。"""
    cam = 1660 - 240
    bg = background(cam)
    fog = np.array(Image.open(OUT / "fog_bank.png"))
    place(bg, fog, 1660, cam, None, semi=True)
    sheet = np.array(Image.open(OUT / "cloth.png"))
    fw = sheet.shape[1] // 2
    place(bg, sheet[:, :fw], 1780 - cam + cam, cam)
    put_chen(bg, 1745, cam)
    big = np.array(Image.fromarray(bg).resize((1440, 810), Image.NEAREST))
    for k in range(2):        # 角上放大两帧（6 倍）
        fr = sheet[:, k * fw:(k + 1) * fw]
        z = np.array(Image.fromarray(fr).resize((fw * 6, fr.shape[0] * 6), Image.NEAREST))
        x0, y0 = 1440 - (2 - k) * (fw * 6 + 12), 12
        reg = big[y0:y0 + z.shape[0], x0:x0 + z.shape[1]]
        reg[:] = (24, 36, 30)
        m = z[..., 3] > 0
        reg[m] = z[m][:, :3]
    p = d / "preview_cloth.png"
    Image.fromarray(big).save(p)
    return p


def hoofprints():
    """地上一串蹄印：每个是两瓣的小坑，把地面最上面那条苔藓线啃出两个暗口子，前沿拱起一点湿泥。
    ground_row=1（图里第 1 行对齐地面最上面一行）。"""
    s = Spr(24, 4)
    for i, x in enumerate((1, 7, 13, 19)):
        dx = 1 if i % 2 else 0
        x += dx
        for k in (0, 2):
            s.put(x + k, 1, SOIL[0])
            s.put(x + k, 2, SOIL[0])
            s.put(x + k, 3, SOIL[1])
        s.put(x + 1, 1, MOSS[1])
        s.put(x + 1, 2, SOIL[2])
        s.put(x + 3, 0, MOSS[4])            # 往前挤起来的泥，朝上那面亮
        s.put(x + 3, 1, MOSS[3])
        s.put(x - 1, 1, MOSS[3])
    return s


AIR = from_hex("#18241e")      # 地面线上方林下那条背景色：坑里「空着」的地方就填它（横版正侧面，坑是地面线上的一个缺口）


def _ground_pit(s, cx, gr, rx, ry, seed, toes=False, water=True):
    """正侧面的一个浅坑：地面那条苔藓线往下弯成一个平底的碗，碗上面原来是土的地方现在空着（填林下的背景色），
    碗底一洼水（平的水面，上沿一条亮线映着雾）；两头被挤起来的泥拱出地面一行；
    toes：前头（右边）的坑壁上几个小台阶，像趾甲印。没有透视，没有俯视的椭圆。"""
    dx = (s.xx + 0.5 - cx) / rx
    prof = np.clip(1 - np.abs(dx) ** 2.6, 0, 1) ** 0.5                       # 平底、圆边
    if toes:
        for fx in (0.55, 0.7, 0.84):
            prof = prof + 0.22 * np.clip(1 - ((dx - fx) / 0.06) ** 2, 0, 1)   # 前沿几个小凹口
    curve = gr + np.round(ry * np.minimum(prof, 1.0))
    inside = np.abs(dx) < 1
    air = inside & (s.yy >= gr) & (s.yy < curve)
    s.fill(air, [AIR], 0)
    # 新的地面线（坑壁 + 坑底）：2 行苔藓，上面那行亮；再往下是土
    line1 = inside & (s.yy == curve) & (curve > gr)
    line2 = inside & (s.yy == curve + 1) & (curve > gr)
    s.fill(line1, MOSS, 2.6 + 0.6 * (dx < 0))
    s.fill(line2, MOSS, 1.6)
    soil = inside & (s.yy > curve + 1) & (curve > gr)
    s.fill(soil, SOIL, 2.6 - 1.6 * np.clip((s.yy - curve) / 8, 0, 1) + noise(s, seed, (6, 2)) * 0.6)
    if water:
        wl = gr + ry - 2
        pool = air & (s.yy >= wl)
        s.fill(pool, WATER, 0.6 + 0.6 * (s.yy == wl))
        ys, xs = np.nonzero(pool & (s.yy == wl))
        for x in xs[3::7]:
            s.put(x, wl, WATER[2])
    # 两头被挤起来的泥：拱出地面一行
    for sd in (-1, 1):
        xa = int(round(cx + sd * rx))
        bump = s.rect(min(xa, xa + sd * 7), gr - 1, max(xa, xa + sd * 7), gr - 1)
        s.fill(bump, MOSS, 3.2 if sd < 0 else 2.4)
        s.put(xa + sd * 2, gr - 2, MOSS[3])
    return air


def hollow():
    """下面是空的地方（正侧面）：地面那条线断开，草皮从两边耷拉进去；中间是一道往下的黑口子，
    越往下越黑，最底下一线水光。两边的地面有裂缝。ground_row=4。"""
    W, Hh = 60, 18
    s = Spr(W, Hh)
    gr = 4
    hole = np.zeros((Hh, W), bool)
    rng = np.random.default_rng(8)
    for y in range(gr, Hh):
        f = (y - gr) / (Hh - gr)
        hw = 18 - 7 * f + rng.uniform(-1, 1)
        c = 30 + 2 * f
        hole[y, int(round(c - hw)):int(round(c + hw)) + 1] = True
    # 口子里：上面一截是空着的林下（背景色），往下一档一档沉进很暗的洞里
    dv = (s.yy - gr) / (Hh - gr)
    s.fill(hole & (dv < 0.18), [AIR], 0)
    s.fill(hole & (dv >= 0.18), BARK, np.where(dv < 0.4, 1, 0))
    # 洞壁：右壁朝光亮一点，左壁暗
    _, _, lf, rt = edges(hole)
    wall_r = shift(rt, 1, 0) & ~hole
    wall_l = shift(lf, -1, 0) & ~hole
    s.fill(wall_r & (s.yy > gr + 1), SOIL, 3)
    s.fill(wall_l & (s.yy > gr + 1), SOIL, 1)
    # 水光：底下两三截平的亮线
    for x0, x1, y in ((24, 29, Hh - 3), (32, 37, Hh - 3), (27, 33, Hh - 2)):
        s.fill(s.rect(x0, y, x1, y) & hole, WATER, 1)
    for x in (25, 34):
        s.put(x, Hh - 3, WATER[2])
    # 两边断开的地面：苔藓线到口子边上就断了，草皮往里耷拉，土块往下掉
    for side, x_edge in ((-1, int(np.nonzero(hole[gr])[0].min())), (1, int(np.nonzero(hole[gr])[0].max()))):
        xs_ = range(x_edge - 10, x_edge) if side < 0 else range(x_edge + 1, x_edge + 11)
        for x in xs_:
            s.put(x, gr, MOSS[3])
            s.put(x, gr + 1, MOSS[2])
        for k, (dxx, ln) in enumerate(((0, 4), (2, 2), (-1, 3))):   # 耷拉进去的草皮和根须
            x = x_edge + side * (1 + dxx) if side < 0 else x_edge - (1 + dxx)
            x = x_edge - side * (1 + k)
            for j in range(ln):
                s.put(x, gr + j, MOSS[2] if j < 2 else SOIL[3])
    for x, y in ((26, gr + 6), (35, gr + 8), (30, gr + 10)):
        s.put(x, y, SOIL[3])
    for pts in (((9, gr + 2), (5, gr + 3), (1, gr + 3)), ((51, gr + 2), (55, gr + 4), (59, gr + 4)), ((11, gr + 4), (7, gr + 6))):
        s.fill(s.line(*pts), SOIL, 0)
    for x, h_ in ((6, 2), (7, 3), (53, 2), (54, 3)):
        for k in range(h_):
            s.put(x, gr - 1 - k, MOSS[2 + (k == h_ - 1)])
    s.fill(s.line((49, gr - 1), (46, gr - 4)), MOSS, 2)   # 往口子里歪的一棵小蕨
    s.fill(s.line((47, gr - 3), (45, gr - 3)), MOSS, 3)
    return s


def depressions():
    """坡地上几处很大的凹陷（正侧面）：地面线往下弯成三个平底的大碗，一个比晨还宽，深到晨的小腿；
    差不多一样大、隔着差不多的步子，前头坑壁上有几个小凹口（像趾甲），碗底积着水。不点破。ground_row=3。"""
    W, Hh = 220, 16
    s = Spr(W, Hh)
    gr = 3
    for i, (cx, rx) in enumerate(((34, 28), (110, 30), (184, 27))):
        _ground_pit(s, cx, gr, rx, 8, 20 + i, toes=True)
        for sd in (-1, 1):       # 坑边的裂纹
            x0 = int(cx + sd * (rx + 3))
            s.fill(s.line((x0, gr + 2), (x0 + sd * 5, gr + 3), (x0 + sd * 9, gr + 3)), SOIL, 0)
    return s


def fog_bank():
    """坡地远处的雾：一团团鼓起来的雾，按浓淡分成四档硬边的半透明（不是平滑渐变），档的边界跟着雾团起伏；
    越往下越浓，雾团顶上受光亮一档。最浓也透得出后面的树影。"""
    W, Hh = 480, 120
    s = Spr(W, Hh)
    rng = np.random.default_rng(31)
    yy, xx = s.yy, s.xx
    xs = np.arange(W)
    top = np.full(W, 96.0)
    for k in range(13):           # 雾团（左右无缝）
        c = rng.uniform(0, W)
        r = rng.uniform(30, 90)
        hgt = rng.uniform(26, 70)
        d = np.minimum(np.abs(xs - c), W - np.abs(xs - c))
        top = np.minimum(top, 92 - hgt * np.sqrt(np.clip(1 - (d / r) ** 2, 0, 1)))
    lump = np.zeros((Hh, W))
    for k in range(10):           # 雾里面也一团团的（档的边界不是横线）
        c, cy = rng.uniform(0, W), rng.uniform(20, 110)
        r, ry = rng.uniform(25, 70), rng.uniform(8, 18)
        d = np.minimum(np.abs(xx - c), W - np.abs(xx - c))
        lump += 0.22 * np.clip(1 - (d / r) ** 2 - ((yy - cy) / ry) ** 2, 0, 1)
    depth = yy - top[None, :]
    dens = np.clip(depth / 80, 0, 1) ** 0.7 + lump
    dens[depth < 0] = -1
    levels = [(0.0, 40), (0.28, 72), (0.55, 100), (0.85, 126)]
    alpha = np.zeros((Hh, W), np.uint8)
    lvl = np.full((Hh, W), -1)
    for i, (th, al) in enumerate(levels):
        alpha[dens > th] = al
        lvl[dens > th] = i
    # 颜色：每一档的上沿（雾团顶）受光亮一档，里面是雾色
    above_lower = np.zeros_like(lvl)
    above_lower[1:] = lvl[:-1]
    edge = (lvl >= 0) & ((above_lower < lvl) | (yy == 0))
    edge2 = shift(edge, 0, 1) & (lvl >= 0)
    col_t = np.where(edge, 3, np.where(edge2, 2, 1))
    cols = np.array([tuple(c) for c in FOGC], np.uint8)
    s.a[..., :3] = cols[col_t]
    s.a[..., 3] = alpha
    s.a[alpha == 0] = 0
    return s


# ================================================================ 坠毁现场

def luggage():
    """散落的行李（正侧面）：一只帆布包，一只摔开的旅行箱，盖子整个翻过去平摊在地上，
    箱里冒出一角布和几张纸（那张画就在里面），地上再散两张纸。"""
    W, Hh = 40, 18
    s = Spr(W, Hh)
    gy = Hh - 1
    # 帆布包（左）：鼓鼓的一团，提手
    bag = s.ell(8, 12.5, 7.5, 5.5) & (s.yy <= gy)
    s.fill(bag, AWN, 2.0 + 1.6 * round_tone(s, 8, 12.5, 7.5, 5.5) - 0.9 * ((s.xx == 8) & (s.yy > 9)))
    s.fill(s.stroke([(3, 10), (6, 4.5), (11, 5), (13, 10)], 1.2, 1.2) & ~bag, WOOD, 2.2)
    s.put(8, 10, COPPER[2])
    # 旅行箱：箱身一个长方块，盖子翻过去平摊在右边地上（只看得到一条厚边）
    box = s.rect(15, 9, 29, gy)
    s.fill(box, WOOD, 2.4 + 1.0 * (s.yy == 9) - 1.0 * (s.xx > 27) - 0.8 * (s.yy == gy))
    s.fill(s.rect(15, 12, 29, 12), WOOD, 1.2)
    for x in (18, 25):
        s.fill(s.rect(x, 11, x + 1, 13), COPPER, 1 + (s.yy == 11))
    lid = s.rect(30, gy - 2, 39, gy)
    s.fill(lid, WOOD, 2.0 + 1.0 * (s.yy == gy - 2) - 0.8 * (s.yy == gy))
    s.fill(s.rect(30, gy - 3, 39, gy - 3), AWN, 1.2)                # 盖子里的衬布朝上，翻出一点
    # 箱口冒出来的布和纸
    s.fill(s.poly([(16, 9), (21, 6), (25, 7), (24, 9)]), CLOTH, 0.6)
    pap = s.rect(23, 5, 28, 8)
    s.fill(pap, TAG, 1 - 1.0 * (s.yy == 8))
    s.fill(s.rect(24, 6, 27, 6), TAG, 0)
    # 地上散的纸
    s.fill(s.rect(32, gy - 4, 36, gy - 4), TAG, 1)
    s.fill(s.rect(0, gy, 4, gy), TAG, 0)
    s.put(1, gy, TAG[1])
    sink_bottom(s, 2, 0.3)
    return s


def mat_scrap():
    """金属碎片：一块从船壳上撕下来的铁皮，上沿一排铆钉，左上角折起来一个亮角，右边撕开成锯齿。"""
    s = Spr(14, 10)
    plate = s.poly([(0, 5), (3, 2), (11, 1), (13, 3), (12, 5), (13, 7), (11, 9), (1, 9)])
    plate &= ~s.poly([(11, 4), (14, 4.5), (11, 6)])
    u, v = bbox_uv(s, plate)
    s.fill(plate, TIN, 2.4 - 1.2 * u - 0.6 * v + 0.9 * edges(plate)[0] - 0.9 * edges(plate)[1])
    s.fill(s.rect(1, 6, 11, 6) & plate, TIN, 0.8)              # 弯折的那道棱下面暗
    s.fill(s.rect(1, 5, 10, 5) & plate, TIN, 3.2)              # 棱上沿亮
    fold = s.poly([(0, 5), (3, 2), (4, 5)])
    s.fill(fold, TIN, 4)
    for x in (5, 8, 11):
        s.put(x, 3, TIN[0])
    s.put(12, 8, TIN[3])
    return s


def mat_resin():
    """树脂：一片树皮上凝着两团琥珀色的树脂，受光那边亮一点。"""
    s = Spr(14, 10)
    bark = s.poly([(0, 6), (13, 4), (13, 9), (1, 9)])
    s.fill(bark, BARK, 3.4 - 1.4 * edges(bark)[1] - 1.0 * ((s.xx % 4) == 0))
    for cx, cy, rx, ry in ((5, 5, 3.5, 3), (10, 4.5, 2.5, 2.5)):
        b = s.ell(cx, cy, rx, ry)
        s.fill(b, RESIN, 1.5 + 1.5 * round_tone(s, cx, cy, rx, ry))
    s.put(4, 3, RESIN[3])
    s.put(9, 3, RESIN[3])
    return s


def mat_branch():
    """干枝：三根干透的细枝，中间用草绳捆了一道。"""
    s = Spr(14, 10)
    for pts, t in ((((0, 7), (13, 3)), 2.6), (((1, 9), (13, 6)), 2.0), (((0, 4), (12, 8)), 1.6)):
        m = s.stroke(list(pts), 1.6, 1.3)
        s.fill(m, DRY, t + edges(m)[0] * 0.8)
    s.fill(s.line((5, 4), (5, 9)) | s.line((6, 4), (6, 9)), MOSS, 2.2)
    s.put(12, 2, DRY[3])
    s.put(13, 5, DRY[2])
    return s


# ================================================================ 第三版：新地方和新物件
# 林间空地 glade（岩画、信号箱、路标底座）、旧路上的小空屋 road_house、老松树、木板和木板桥、
# 空屋窗台上的闹钟、送还以后摆回原处的收音机 / 路标 / 油灯。
# 「叠在宿主上」的图（闹钟、placed_*）在同名 json 里写 host 和 offset：
#   offset = 这张图的锚点（底边中点）相对宿主锚点（宿主底边中点）的像素偏移，y 往上是负。
#   锚点的像素约定：底边中点 = 第 w//2 列、最后一行。

ROCK = R("#2c3430", 7, 0.3)            # 空地的大岩石：冷灰绿
RUST = H("#2c2421", "#3e2f2a", "#4e3a31", "#5b4638")   # 铁锈（暗、灰，不跳）


def anchor_offset(host_w, host_h, px, py):
    """宿主图里的像素 (px, py) 相对宿主锚点的偏移。"""
    return [int(px - host_w // 2), int(py - (host_h - 1))]


# ---------------------------------------------------------------- 林间空地的岩画

def glade_rock():
    """林间空地的大岩石（正侧面）：一块风化的大石头，顶面朝天受光、左面朝光、右面背光，几道自然裂缝，
    顶上长苔、往下垂；正面刻着一只很古老的、画得不准的大象——像小孩画的：身子一个圈，头一个圈，
    头上两只耳朵，长鼻子一直拖到地上还卷了一下，四条腿长短不齐，一截小尾巴，一个点当眼睛；
    旁边一个很小的小人，举着手指着它。刻痕是凹下去的线：线本身暗，线的右下沿接到光亮一档。
    苔藓和风化把一条后腿、一段背和小人的半边吃掉了，所以看得出是「刻上去的画」，但不清楚。"""
    W, Hh = 124, 72
    s = Spr(W, Hh)
    gy = Hh - 1
    # 轮廓：一块有棱有角的大石头，左高右低，顶上崩掉一个缺口，右下压着一块小石头
    outline = [(2, 72), (1, 58), (4, 46), (7, 36), (12, 26), (19, 18), (31, 13), (46, 11), (57, 8), (63, 4),
               (70, 8), (84, 9), (98, 12), (108, 17), (113, 25), (117, 37), (121, 50), (123, 60), (123, 72)]
    sil = s.poly(outline)
    # 顶面：沿着上沿往下 7~10 格的一条带（朝天，最亮）
    top_pts = outline[3:17]
    top = s.poly(top_pts + [(x + (4 if x < 60 else -3), y + (8 if 20 < x < 100 else 6)) for x, y in reversed(top_pts)])
    top &= sil
    left = s.poly([(1, 58), (4, 46), (7, 36), (12, 26), (16, 30), (13, 44), (11, 58), (12, 72), (2, 72)])
    right = s.poly([(98, 12), (108, 17), (113, 25), (117, 37), (121, 50), (123, 60), (123, 72), (106, 72), (108, 56),
                    (104, 40), (103, 26), (96, 19)])
    face = sil & ~top & ~left & ~right
    face_hi = face & (s.xx + 0.9 * s.yy < 80)
    s.fill(sil, ROCK, 3)
    s.fill(face, ROCK, 2.6)
    s.fill(face_hi, ROCK, 3.2)
    s.fill(top, ROCK, 5.2 - 0.8 * (s.xx > 90))
    s.fill(left, ROCK, 3.8)
    s.fill(right, ROCK, 1.4)
    s.fill(right & (s.xx > 116), ROCK, 0.8)
    # 顶上崩掉的缺口：露出新一点的断面（亮一档）
    chip = s.poly([(58, 8), (63, 4), (70, 8), (67, 13), (60, 12)]) & sil
    s.fill(chip, ROCK, 5.4 - 1.2 * (s.xx > 66))
    # 顶面下沿那条棱：朝光的地方亮一线
    tb = edges(top)[1] & ~edges(sil)[1]
    s.fill(shift(tb, 0, 1) & face, ROCK, 1.6)
    # 风化的面：几大片比周围暗一档（不规则的块，不是网格）
    for cx_, cy_, rx_, ry_ in ((98, 34, 5, 9), (18, 50, 5, 6)):
        m = s.poly([(cx_ - rx_, cy_), (cx_ - rx_ // 2, cy_ - ry_), (cx_ + rx_, cy_ - ry_ // 2), (cx_ + rx_ // 2, cy_ + ry_),
                    (cx_ - rx_ + 2, cy_ + ry_ // 2)]) & face
        s.fill(m, ROCK, 1.9)
    # 右下压着的一块小石头
    pebble = s.poly([(102, 72), (105, 64), (112, 60), (120, 62), (123, 72)])
    s.fill(pebble, ROCK, 2.4 - 1.2 * (s.xx > 115) + 1.4 * edges(pebble)[0])
    # 自然裂缝：粗细不匀、走向乱、两头尖（和刻痕区分开）
    for pts in (((99, 13), (101, 20), (99, 27), (102, 37), (100, 46)), ((72, 8), (73, 13))):
        cm = s.line(*pts) & sil
        s.fill(cm, ROCK, 0.4)
        s.fill(shift(cm, -1, 0) & sil & ~cm, ROCK, 1.6)

    # ---- 凿刻的大象（坐标是石头上的像素）：没有连续的线，只有一下下敲出来的浅凹坑。
    # 每个坑 = 那块岩石本身的颜色暗一档；坑的下沿 / 右下一像素接到光，亮一档——读出来是「凹进去」。
    # 只靠坑的疏密排出大致轮廓：圆滚的身子、一只大耳朵的弧、一条往下垂再往外卷的鼻子；腿只是几列往下排的坑。
    ox, oy = 4, 2
    prng = np.random.default_rng(83)
    pits = np.zeros((Hh, W), bool)
    keep_lines = np.zeros((Hh, W), bool)          # 鼻子、耳朵：苔不准盖
    SHAPES = ((1, 1), (2, 1), (1, 2), (2, 2), (2, 1), (2, 2))

    def pit_at(x, y, big=False, keep=False):
        w_, h_ = ((2, 2) if prng.random() < 0.6 else (2, 1)) if big else SHAPES[int(prng.integers(0, len(SHAPES)))]
        x = int(round(x + ox + prng.uniform(-0.6, 0.6)))
        y = int(round(y + oy + prng.uniform(-0.6, 0.6)))
        m = s.rect(x, y, x + w_ - 1, y + h_ - 1)
        nonlocal_pits[0] |= m
        if keep:
            nonlocal_keep[0] |= m
    nonlocal_pits, nonlocal_keep = [pits], [keep_lines]

    def along(pts, step, skip=0.0, **kw):
        """沿折线每隔 step 敲一个坑；skip 的概率漏掉一个（风化 / 没敲到）。"""
        P = np.array(pts, float)
        seg = np.hypot(*np.diff(P, axis=0).T)
        total = seg.sum()
        t = prng.uniform(0, step * 0.5)
        while t < total:
            k = int(np.searchsorted(np.cumsum(seg), t, side="right"))
            k = min(k, len(seg) - 1)
            t0 = np.cumsum(seg)[k] - seg[k]
            f = (t - t0) / seg[k]
            x, y = P[k] + (P[k + 1] - P[k]) * f
            if prng.random() >= skip:
                pit_at(x, y, **kw)
            t += step * prng.uniform(0.8, 1.25)

    def arc(cx, cy, rx, ry, a0, a1, n=48):
        aa = np.radians(np.linspace(a0, a1, n))
        return list(zip(cx + rx * np.cos(aa), cy + ry * np.sin(aa)))

    along(arc(63, 41, 18, 11, -150, 150), 2.9, skip=0.15)                     # 身子（左前方被耳朵挡住的那截不敲）
    along(arc(47, 37, 7, 10, -115, 115), 2.2, big=True, keep=True)            # 大耳朵的弧
    along(arc(38, 36, 6.5, 6, 150, 300), 3.0, skip=0.1)                       # 头顶和脸
    along([(33, 40), (30, 45), (29, 50), (29, 55), (27, 58), (24, 58), (22, 56), (23, 53)], 2.1, big=True, keep=True)  # 鼻子：垂下来，往外卷
    for x0, y1 in ((51, 60), (58, 59), (71, 60), (78, 58)):                   # 腿：几列往下排的坑
        along([(x0, 53), (x0 + prng.uniform(-0.5, 0.5), y1)], 3.0, skip=0.25)
    along([(82, 38), (86, 42), (87, 46)], 3.0)                                # 小尾巴
    pit_at(35, 34)                                                            # 眼睛
    for _ in range(9):                                                        # 身子里零星几个坑（人为凿过的一片）
        a_ = prng.uniform(0, 2 * np.pi)
        r_ = np.sqrt(prng.uniform(0.05, 0.6))
        pit_at(63 + 16 * r_ * np.cos(a_), 41 + 9 * r_ * np.sin(a_))
    # 小人：也是凿坑，头一个大坑，身子、腿、举起来指着大象的手几个小坑
    pit_at(90.5, 43.5, big=True)
    along([(91, 47), (91, 54)], 2.6)
    along([(91, 55), (89, 59)], 2.5)
    along([(92, 55), (93, 59)], 2.5)
    along([(90, 49), (86, 45)], 2.4)
    pits = nonlocal_pits[0] & (face | face_hi | left)
    keep_lines = nonlocal_keep[0] & pits
    lip = (shift(pits, 0, 1) | shift(pits, 1, 1)) & ~pits & sil
    step_tone(s, pits, -1)
    step_tone(s, lip, +1)
    step_tone(s, lip & ((shift(keep_lines, 0, 1) | shift(keep_lines, 1, 1))), +1)   # 鼻子和耳朵敲得深一点，下沿的光也亮一点

    # ---- 苔：长在顶上、往下垂成一道道帘子；从地上往上爬；背光的右面一大片。
    # 一道帘子正好垂过大象的背，地上的苔吃掉一条后腿的脚，右边那片吃掉小人的半边身子。
    mrng = np.random.default_rng(85)
    moss = top & (noise(s, 85, (7, 2)) > 0.1)
    top_y = np.array([np.nonzero(sil[:, x])[0].min() if sil[:, x].any() else Hh for x in range(W)])
    for x0, x1, ln0 in ((61, 75, 34), (26, 33, 9), (88, 95, 14)):          # 从顶上垂下来的帘子
        for x in range(x0, x1 + 1):
            edge = 1 - abs((x - (x0 + x1) / 2) / ((x1 - x0) / 2 + 1))
            ln_ = int(ln0 * (0.35 + 0.65 * edge) * mrng.uniform(0.6, 1.0))
            moss[top_y[x]:top_y[x] + 6 + ln_, x] = True
    for x0, x1, h0 in ((64, 80, 8), (4, 22, 7), (40, 52, 3)):              # 从地上往上爬
        for x in range(x0, x1 + 1):
            edge = 1 - abs((x - (x0 + x1) / 2) / ((x1 - x0) / 2 + 1))
            hh = int(h0 * (0.3 + 0.7 * edge) * mrng.uniform(0.6, 1.0))
            moss[gy - hh:gy + 1, x] = True
    moss |= s.poly([(103, 22), (110, 26), (114, 40), (112, 58), (104, 64), (96, 60), (99, 50), (100, 36)])   # 背光面那一大片
    moss = clean(clean(moss & sil & ~dilate(keep_lines, 2)))
    mt, _, _, _ = edges(moss)
    s.fill(moss, MOSS, 1.2 + 1.0 * (s.xx < 90) + 0.6 * (s.yy < 24) - 0.6 * (s.yy > gy - 10))
    s.fill(mt & (s.xx < 100), MOSS, 3.2)
    # 地衣：几小块浅的
    for x, y in ((24, 44), (25, 44), (24, 45), (84, 26), (85, 26), (16, 52), (102, 30), (103, 30)):
        s.put(x, y, mixc(ROCK[4], from_hex("#6f7a62"), 0.4))
    # 石脚：贴地那几行压暗，长几丛蕨和草
    rng = np.random.default_rng(87)
    for x in range(0, W):
        if sil[gy, x] and rng.random() < 0.3:
            for k in range(int(rng.integers(1, 4))):
                s.put(x, gy - k, MOSS[1 + (k > 0)])
    despeckle(s)
    sink_bottom(s, 5, 0.5)
    return s


# ---------------------------------------------------------------- 信号箱、路标底座

def signal_box():
    """废弃的信号箱：一根铁杆撑着一只铁皮箱，斜顶，顶上一只灭了的信号灯；锈一片片往下淌；
    门往左半开着（侧着看只剩一条窄的门板，露出门里那面），箱里看得到零件：一只阀门手轮、一根弹簧、几根线。"""
    W, Hh = 32, 52
    s = Spr(W, Hh)
    gy = Hh - 1
    # 底座和杆
    s.fill(s.rect(11, gy - 3, 22, gy), STONE, 2.0 + 1.0 * (s.yy == gy - 3) - 0.8 * (s.xx > 20))
    pole = s.rect(15, 30, 18, gy - 4)
    s.fill(pole, TIN, 1.6 + 1.2 * (s.xx == 15) - 0.8 * (s.xx == 18))
    s.fill(pole & (noise(s, 91, (2, 4)) > 0.15), RUST, 1)
    # 箱子
    bx0, bx1, by0, by1 = 10, 29, 9, 31
    box = s.rect(bx0, by0, bx1, by1)
    s.fill(box, TIN, 2.3 - 1.4 * ((s.xx - bx0) / (bx1 - bx0)) + 0.6 * (s.xx == bx0))
    roof = s.poly([(bx0 - 2, by0), (bx1 + 2, by0), (bx1 + 1, by0 - 3), (bx0 - 1, by0 - 4)])
    s.fill(roof, TIN, 3.2 - 1.2 * (s.xx > 24) - 1.0 * (s.yy == by0))
    # 门洞（门开着）：里面暗
    cav = s.rect(bx0 + 3, by0 + 3, bx1 - 3, by1 - 3)
    s.fill(cav, BARK, 0.5)
    s.fill(s.rect(bx0 + 3, by0 + 3, bx1 - 3, by0 + 4), BARK, 0.1)       # 门洞顶上那道影
    # 里面的零件：阀门手轮（亮一点的铜）、一根弹簧、几根线、一只小表
    vx, vy = 22, 17
    wheel = s.ell(vx, vy, 3.6, 3.6) & ~s.ell(vx, vy, 2.2, 2.2)
    s.fill(wheel, COPPER, 1.4 + round_tone(s, vx, vy, 3.6, 3.6))
    s.fill(s.rect(vx - 1, vy - 1, vx - 1, vy - 1) | s.line((vx - 3, vy - 1), (vx + 1, vy - 1)), COPPER, 1)
    s.fill(s.rect(vx - 1, vy + 3, vx - 1, by1 - 4), TIN, 1.4)           # 手轮下面的管
    for k in range(5):                                                  # 弹簧：一圈一圈
        y = by0 + 12 + 2 * k
        s.fill(s.line((14, y), (17, y + 1)), TIN, 3)
    s.fill(s.rect(14, by0 + 10, 14, by0 + 11) | s.rect(17, by0 + 21, 17, by0 + 22), TIN, 2)
    for pts, t in ((((14, by0 + 4), (15, by0 + 7), (13, by0 + 9)), 1), (((26, by0 + 4), (25, by0 + 12), (26, by1 - 4)), 0.6)):
        s.fill(s.line(*pts) & cav, RUST, t)
    s.fill(s.ell(16, by0 + 6, 1.6, 1.6), TAG, 0)
    s.put(16, by0 + 6, TIN[0])
    # 门：往左半开，看到门里那面（暗），门边亮一线；一个铰链
    door = s.poly([(bx0 - 7, by0 + 2), (bx0, by0 + 1), (bx0, by1), (bx0 - 7, by1 - 2)])
    s.fill(door, TIN, 1.0 + 0.8 * edges(door)[0])
    s.fill(s.line((bx0 - 7, by0 + 2), (bx0 - 7, by1 - 2)), TIN, 2.6)
    s.fill(door & (noise(s, 93, (2, 3)) > 0.1), RUST, 0.8)
    s.put(bx0, by0 + 5, TIN[3])
    s.put(bx0, by1 - 4, TIN[3])
    # 锈：从顶上和铆钉往下淌的竖条
    rust = box & ~cav & (((s.xx * 7) % 5 == 0) & (s.yy < by0 + 3 + (s.xx * 13) % 9) | (noise(s, 95, (3, 4)) > 0.3))
    s.fill(rust, RUST, 2 - 1.0 * (s.xx > 24))
    for x in (bx0 + 1, bx1 - 1):
        for y in (by0 + 1, by1 - 1):
            s.put(x, y, TIN[3] if x < 20 else TIN[1])
    # 顶上的信号灯（灭的）
    s.fill(s.rect(17, 1, 21, 5), TIN, 1.6 + (s.xx == 17))
    s.fill(s.rect(18, 2, 20, 4), BARK, 0.8)
    s.put(18, 2, WATER[1])
    s.fill(s.rect(16, 0, 22, 0), TIN, 2.6)
    s.fill(s.rect(19, 6, 19, by0 - 4), TIN, 1.4)
    # 杆脚的草
    for x, h_ in ((12, 2), (13, 3), (19, 2), (21, 4), (22, 2)):
        for k in range(h_):
            s.put(x, gy - 2 - k, MOSS[1 + (k > 0)])
    despeckle(s)
    sink_bottom(s, 3, 0.4)
    return s


SIGN_BASE_TOP = 11          # 底座顶上插杆的那一行离底边多高（placed_sign 的偏移用）


def sign_base():
    """路标原来的底座：一截断掉的粗木桩，顶上参差的断茬，中间一道铁箍（锈，两颗铆钉），顶上留着插杆的方孔。"""
    W, Hh = 16, 15
    s = Spr(W, Hh)
    gy = Hh - 1
    post = s.rect(3, 3, 12, gy)
    s.fill(post, WOOD, 3.0 - 1.8 * ((s.xx - 3) / 9) + 0.8 * (s.xx == 3) - 0.9 * (((s.xx - 3) % 4) == 3))
    # 断茬：几根尖
    for x, h_ in ((3, 1), (4, 3), (5, 2), (10, 3), (11, 1), (12, 2)):
        for k in range(h_):
            s.put(x, 2 - k, DRY[2 if x < 8 else 1])
    s.fill(s.rect(6, 2, 9, 3), DRY, 3)           # 断口的浅木头
    s.fill(s.rect(7, 3, 8, 3), BARK, 0.2)        # 插杆的方孔
    # 铁箍
    band = s.rect(2, 7, 13, 9)
    s.fill(band, RUST, 2 - (s.yy == 9) - 0.8 * (s.xx > 10) + 0.8 * (s.yy == 7))
    s.put(4, 8, TIN[3])
    s.put(11, 8, TIN[1])
    s.fill(s.rect(2, 10, 13, 10), RUST, 0.5)     # 锈往下淌一道
    for x, h_ in ((1, 2), (2, 3), (13, 2), (14, 3), (15, 1)):
        for k in range(h_):
            s.put(x, gy - k, MOSS[1 + (k > 0)])
    s.put(5, 12, MOSS[2])
    s.put(5, 13, MOSS[2])
    sink_bottom(s, 2, 0.35)
    return s


# ---------------------------------------------------------------- 老松树

def pine_sap():
    """商店旁边的老松树，下半截（树干从画面外下来）：一片片龟裂的厚树皮，底下板根撑开；
    齐胸高有一道很老的伤口，露出里面的木头，松脂顺着往下淌成几道「眼泪」，挂着两滴。
    帧 0 平常，帧 1 松脂上的反光闪一下（亮两三个像素）。"""
    W, Hh = 60, 232
    gy = Hh - 1
    frames = []
    base = Spr(W, Hh)
    s = base
    cx = 30
    rng = np.random.default_rng(101)
    sy = s.yy + (GROUND - gy)
    jit = np.repeat(np.random.default_rng(102).integers(-9, 10, W // 3 + 2), 3)[:W]
    canopy_dark = np.clip(np.floor((124 - sy + jit[None, :]) / 20), 0, 4) * 0.5
    trunk = np.zeros((Hh, W), bool)
    left = np.zeros(Hh)
    right = np.zeros(Hh)
    for y in range(Hh):
        half = 13 + 2 * (y / Hh)
        fl = max(0, y - (Hh - 30))
        half += (fl / 30) ** 2.4 * 14
        left[y] = cx - half + 0.8 * np.sin(y / 19)
        right[y] = cx + half + 0.8 * np.sin(y / 23 + 1)
        trunk[y, int(round(left[y])):int(round(right[y])) + 1] = True
    u = np.clip((s.xx - left[:, None]) / (right - left)[:, None], 0, 1)
    tone = 0.9 + 4.4 * np.clip(1 - np.abs(u - 0.2) / 0.8, 0, 1) ** 1.2
    tone[u < 0.04] -= 0.8
    # 松树皮：不规则的大鳞片，竖着偏长，大小形状都乱；块和块之间是又深又曲折的裂沟。
    # 做法：在「树干展开」的坐标里撒点（竖向压扁的距离 = 鳞片竖长），每个像素归最近的点；
    # 最近和次近差不多远的地方就是裂沟。坐标先用两层正弦扭一下，沟就弯弯曲曲、不成行。
    uu = u * 5.0                                            # 横向：一面看过去约 4~5 块鳞片
    vv = s.yy / 13.0                                        # 竖向：鳞片高约是宽的 2 倍多
    wu = uu + 0.22 * np.sin(s.yy / 6.0 + uu * 1.3) + 0.1 * np.sin(s.yy / 2.7 + 2.0)
    wv = vv + 0.25 * np.sin(uu * 2.3 + s.yy / 9.0)
    pts = []
    for k in range(int(5 * Hh / 13.0 * 0.8)):
        pts.append((rng.uniform(-0.3, 5.3), rng.uniform(-1, Hh / 13.0 + 1), rng.uniform(0.7, 1.4)))
    d1 = np.full((Hh, W), 1e9)
    d2 = np.full((Hh, W), 1e9)
    cid = np.zeros((Hh, W), int)
    for k, (pu, pv, sc) in enumerate(pts):
        d = np.hypot(wu - pu, (wv - pv) * 0.9) / sc          # sc：有的块大、有的块小
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        cid = np.where(closer, k, cid)
        d1 = np.where(closer, d, d1)
    crack = trunk & ((d2 - d1) < 0.16)
    deep = trunk & ((d2 - d1) < 0.07)
    plate_off = np.array([rng.choice([-0.5, 0, 0, 0.4, 0.8]) for _ in pts])[cid]
    tone = tone + plate_off
    tone[crack] -= 1.8
    tone[deep] -= 0.8
    # 鳞片是凸起来的：每块左上沿（挨着沟）接到光，右下沿掉进沟里那一线暗
    plate = trunk & ~crack
    rim_lit = plate & (shift(crack, 1, 0) | shift(crack, 0, 1)) & (u < 0.75)
    rim_dark = plate & (shift(crack, -1, 0) | shift(crack, 0, -1))
    tone[rim_lit] += 0.8
    tone[rim_dark & ~rim_lit] -= 0.5
    tone -= canopy_dark * 1.2
    s.fill(trunk, BARK, tone)
    # 板根顶上受光、长苔
    rt = edges(trunk)[0]
    s.fill(clean(dilate(rt, 1) & trunk & (s.yy > gy - 28) & (noise(s, 104, (4, 2)) > -0.1)), MOSS, 2.2)
    # 伤口：一道竖长的、边缘卷起来的口子，里面是浅的木头
    wy0, wy1 = gy - 52, gy - 30
    wcx = cx - 3
    wound = s.ell(wcx, (wy0 + wy1) / 2, 4.5, (wy1 - wy0) / 2) & trunk
    lipm = dilate(wound, 1) & ~wound & trunk
    s.fill(lipm, BARK, np.where(s.xx < wcx, 5.2, 2.4))
    s.fill(wound, DRY, 2.2 + 1.0 * (s.xx < wcx - 1) - 1.0 * (s.yy > wy1 - 6))
    s.fill(wound & (s.xx == wcx + 1) & (s.yy > wy0 + 3) & (s.yy < wy1 - 3), DRY, 1)   # 木头的纹
    # 松脂：从伤口里往下淌，几道「眼泪」，末端挂一滴
    sap = np.zeros((Hh, W), bool)
    for x0, y0, ln_ in ((wcx - 2, wy0 + 5, 18), (wcx + 1, wy0 + 10, 30), (wcx + 3, wy1 - 6, 12), (wcx - 1, wy1 - 2, 8)):
        for k in range(ln_):
            sap[y0 + k, x0 + (1 if k > ln_ * 0.6 and x0 % 2 else 0)] = True
        sap[y0 + ln_, x0 + (1 if x0 % 2 else 0)] = True
        drop = s.rect(x0 - 1 + (1 if x0 % 2 else 0), y0 + ln_ - 1, x0 + (1 if x0 % 2 else 0), y0 + ln_ + 1)
        sap |= drop
    sap |= s.ell(wcx, wy0 + 8, 2.5, 3) & wound
    s.fill(sap, RESIN, 1.6 - 0.8 * (s.xx > wcx + 1) - 0.6 * edges(sap)[3])
    s.fill(edges(sap)[2] & sap, RESIN, 2.4)
    despeckle(s)
    sink_bottom(s, 4, 0.45)
    for f in range(2):
        fr = Spr(W, Hh)
        fr.a = base.a.copy()
        glints = ((wcx - 1, wy0 + 7), (wcx + 1, wy0 + 31), (wcx + 2, wy0 + 40))
        for k, (x, y) in enumerate(glints):
            if f == 1:
                fr.put(x, y, RESIN[3])
                if k == 0:
                    fr.put(x, y + 1, RESIN[3])
            else:
                fr.put(x, y, RESIN[2])
        frames.append(fr)
    return frames


# ---------------------------------------------------------------- 木板、木板桥

def plank():
    """地上的一块木板（正侧面）：烂货架上拆下来的，一头断得参差，两颗弯钉子还在。"""
    s = Spr(34, 5)
    gy = 4
    b = s.rect(0, 2, 33, 4) & ~s.rect(31, 2, 33, 2) & ~s.rect(33, 3, 33, 3)
    s.fill(b, WOOD, 3.4 + 0.9 * (s.yy == 2) - 0.8 * (s.yy == 4) - 0.6 * (s.xx > 26))
    s.fill(s.rect(9, 3, 15, 3), WOOD, 2.6)
    for x in (4, 22):
        s.put(x, 1, TIN[3])
        s.put(x + 1, 0, TIN[2])
    sink_bottom(s, 1, 0.3)
    return s


def plank_bridge():
    """搭在塌陷口上的木板：和 hollow.png 一样大、一样的 ground_row，直接叠在它上面。
    木板两头搭在口子两边的地面上，中间稍微往下压一点；口子还在底下看得见。"""
    W, Hh = 60, 18
    gr = 4
    s = Spr(W, Hh)
    sag = np.round(1.0 * np.sin(np.pi * np.clip((s.xx - 6) / 48, 0, 1))).astype(int)
    b = (s.xx >= 6) & (s.xx <= 54) & (s.yy >= gr - 3 + sag) & (s.yy <= gr - 1 + sag)
    rel = s.yy - (gr - 3 + sag)
    s.fill(b, WOOD, 3.4 + 0.9 * (rel == 0) - 1.4 * (rel == 2) - 0.6 * (s.xx > 44) + 0.4 * (s.xx < 14))
    s.fill(b & (s.xx >= 18) & (s.xx <= 24) & (rel == 1), WOOD, 2.6)
    for x in (9, 27):
        s.put(x, gr - 4 + sag[0, x], TIN[3])
    # 两头压在地上：底下各压出一点土
    for x0 in (5, 52):
        s.fill(s.rect(x0, gr, x0 + 3, gr), SOIL, 2.6)
    return s


# ---------------------------------------------------------------- 叠在宿主上的东西

CLOCK_SILL = (82, 54)        # empty_house 里右窗窗台上面那一行、闹钟中线所在的像素


def clock_window():
    """空屋窗台上一只停了的旧闹钟：两只铃、一个小锤、圆表盘、两只小脚；表盘发灰，指针停着；顶上落灰。"""
    s = Spr(9, 10)
    face_m = s.ell(4.5, 5.5, 3.5, 3.5)
    s.fill(face_m, TIN, 2.2 + 1.2 * round_tone(s, 4.5, 5.5, 3.5, 3.5))
    dial = s.ell(4.5, 5.5, 2.4, 2.4)
    s.fill(dial, DUST, 1.4 - 0.6 * (s.xx > 5))
    s.put(4, 4, TIN[0])
    s.put(4, 5, TIN[0])
    s.put(5, 5, TIN[0])
    for x in (1, 7):                       # 铃
        s.fill(s.rect(x - 1 + (x > 4), 0, x + (x > 4), 1), TIN, 3 - (x > 4))
    s.put(4, 1, TIN[2])
    s.fill(s.rect(2, 9, 2, 9) | s.rect(6, 9, 6, 9), TIN, 1)
    s.put(1, 0, DUST[2])
    s.put(8, 0, DUST[1])
    return s


HOOK = (33, 40)              # road_house 里门右边挂钩的钩尖（油灯的环挂在这里）


def road_house():
    """旧路上的小空屋：比 empty_house 小、更破、更久没人。屋顶右半边塌进去了，墙板掉了几块露出里面的黑，
    门只挂着一个铰链、歪着；窗户没有玻璃；藤从墙角爬上来，屋顶的破洞里长出一棵小云杉。
    门右边钉着一只空的铁挂钩——油灯原来挂在这里。"""
    W, Hh = 86, 64
    s = Spr(W, Hh)
    gy = Hh - 1
    wall = s.rect(8, 22, 77, gy)
    u, v = bbox_uv(s, wall)
    wt = 2.2 - 1.4 * u - 1.0 * ((s.yy - 22) % 5 == 4) + 0.4 * ((s.yy - 22) % 5 == 0)
    s.fill(wall, WOOD_C, wt - 0.3)
    # 掉了的墙板：露出里面的黑，边上的板头参差
    for x0, x1, y0 in ((12, 22, 42), (16, 26, 47), (60, 71, 32), (52, 58, 52)):
        m = s.rect(x0, y0, x1, y0 + 3)
        s.fill(m, BARK, 0.2)
        s.put(x0, y0 + 1, WOOD_C[2])
        s.put(x1, y0 + 2, WOOD_C[1])
    s.fill(s.rect(8, 22, 9, gy), WOOD_C, 2.8)
    s.fill(s.rect(76, 22, 77, gy), WOOD_C, 0.6)
    # 屋顶：左半边还在（苔很厚），右半边塌进去，只剩几根椽子斜着
    roof_l = s.poly([(1, 24), (44, 24), (44, 3), (13, 3)])
    sag = np.round(1.5 * np.sin(np.pi * np.clip((s.xx - 13) / 31, 0, 1))).astype(int)
    roof_l &= s.yy >= 3 + sag
    rr = s.yy - 3 - sag
    rt = 2.8 - 1.0 * (s.xx / W) - 1.1 * (rr % 5 == 4) - 1.0 * (((s.xx + (rr // 5) * 3) % 7) == 0)
    s.fill(roof_l, WOOD_C, rt - 0.3)
    mz = noise(s, 111, (4, 3))
    s.fill(clean(roof_l & (mz > 0.05)), MOSS, 1.4 + 0.8 * (s.xx < 26) + 0.6 * (rr < 6))
    s.fill(edges(roof_l)[0], MOSS, 2.6)
    # 塌下去的右半：一块屋面歪着压进屋里，椽子露在外面
    slab = s.poly([(44, 12), (60, 20), (78, 26), (76, 30), (58, 25), (44, 18)])
    s.fill(slab, WOOD_C, 1.6 - 0.8 * edges(slab)[1] + 0.8 * edges(slab)[0])
    s.fill(clean(slab & (noise(s, 113, (3, 2)) > 0.1), 1), MOSS, 1.6)
    for a, b in (((45, 4), (52, 15)), ((52, 8), (62, 20)), ((60, 13), (70, 23))):
        s.fill(s.stroke([a, b], 1.6, 1.4), WOOD_C, 1.2)
    s.fill(s.rect(44, 3, 45, 24), WOOD_C, 1.0)
    s.fill(s.rect(1, 23, 44, 24), WOOD_C, 0.8)
    # 屋顶破洞里长出来的一棵小云杉
    for k, (y, hw) in enumerate(((2, 0), (4, 1), (6, 2), (8, 2), (10, 3), (12, 4))):
        s.fill(s.rect(54 - hw, y + 2, 54 + hw, y + 3), MOSS, 1.4 + (k < 2) * 0.8 - 0.6 * (s.xx > 54))
    s.fill(s.rect(54, 15, 54, 18), BARK, 2)
    # 门：只挂一个铰链，歪着往外倒，露出门洞的黑
    dx0, dx1, dtop = 18, 31, 29
    s.fill(s.rect(dx0, dtop, dx1, gy), BARK, 0.2)
    s.fill(dilate(s.rect(dx0, dtop, dx1, gy), 1) & ~s.rect(dx0, dtop, dx1, gy), WOOD_C, 2.6)
    door = s.poly([(dx0, dtop + 1), (dx0 + 12, dtop + 3), (dx0 + 10, gy + 1), (dx0 - 2, gy - 1)])
    s.fill(door, WOOD_C, 1.4 + 0.6 * (((s.xx - dx0) // 4) % 2) - 0.8 * edges(door)[1])
    s.fill(s.line((dx0, dtop + 9), (dx0 + 11, dtop + 11)) | s.line((dx0 - 1, gy - 9), (dx0 + 10, gy - 7)), WOOD_C, 2.4)
    s.put(dx0, dtop + 4, TIN[2])
    # 门槛：灰更厚，压着落叶
    s.fill(s.rect(dx0 - 3, gy - 1, dx1 + 3, gy), WOOD_C, 1.4)
    s.fill(s.rect(dx0 - 2, gy - 2, dx1 + 2, gy - 2), DUST, 1)
    s.put(dx0 + 2, gy - 2, DUST[0])
    s.put(dx1 - 1, gy - 2, mixc(DUST[0], from_hex("#3b2f26"), 0.5))
    # 挂钩：门右边一块小铁板 + 往外弯的钩
    hx, hy = HOOK
    s.fill(s.rect(hx - 1, hy - 5, hx, hy - 2), TIN, 1.6 + (s.xx == hx - 1))
    s.fill(s.line((hx + 1, hy - 3), (hx + 2, hy - 3), (hx + 2, hy - 1)), TIN, 2.6)
    s.put(hx + 1, hy, TIN[3])
    s.put(hx - 1, hy - 1, RUST[1])
    s.put(hx - 1, hy, RUST[0])
    # 窗：没有玻璃，只剩框；里面黑
    wm = s.rect(48, 34, 60, 45)
    s.fill(wm, WOOD_C, 2.6 - 1.2 * ((s.xx == 60) | (s.yy == 45)))
    s.fill(s.rect(49, 35, 59, 44), BARK, 0.2)
    s.fill(s.line((49, 44), (55, 38)), WOOD_C, 1.4)      # 掉下来斜着的一根窗棂
    s.fill(s.rect(47, 46, 61, 46), WOOD_C, 3.0)
    # 藤：从左墙角爬上来
    vr = np.random.default_rng(115)
    x = 10
    for y in range(gy, 26, -1):
        if vr.random() < 0.3:
            x += int(vr.choice([-1, 1]))
        x = int(np.clip(x, 8, 14))
        s.put(x, y, MOSS[1 + (y < 40)])
        if y % 3 == 0:
            s.put(x + 1, y, MOSS[3])
    for x in range(8, 78):
        if vr.random() < 0.5:
            for k in range(int(vr.integers(1, 4 if x < 18 or x > 66 else 3))):
                s.put(x, gy - k, MOSS[1 + (k > 0)])
    despeckle(s)
    sink_bottom(s, 3, 0.4)
    return s


def placed_lamp():
    """挂回 road_house 门口挂钩上的油灯：顶上一个提环，铁皮灯帽，玻璃罩（灭着，里面一点点暖色的反光），
    黄铜的油壶，挂着弥洛的姓名牌。"""
    s = Spr(9, 15)
    s.fill(s.ell(4.5, 1.5, 2, 1.6) & ~s.ell(4.5, 1.5, 1, 0.7), TIN, 2.4)
    cap = s.rect(2, 3, 6, 4)
    s.fill(cap, TIN, 2.4 + (s.yy == 3) - 0.8 * (s.xx == 6))
    glass = s.rect(2, 5, 6, 10)
    s.fill(glass, BARK, 1.0 + 0.6 * (s.xx < 4))
    s.fill(s.rect(4, 7, 4, 9), GLOW, 0)
    s.put(4, 7, GLOW[1])
    s.put(2, 6, WATER[1])
    s.fill(s.rect(1, 11, 7, 13), COPPER, 1.4 + (s.yy == 11) - 0.8 * (s.xx > 5))
    s.fill(s.rect(2, 14, 6, 14), COPPER, 0.6)
    s.put(8, 12, TAG[1])
    s.put(8, 13, TAG[0])
    s.put(7, 11, TAG[0])
    return s


def _from_room(name):
    p = OUT / f"{name}.png"
    if not p.exists():
        print(f"  （没找到 {name}.png，placed 版先跳过）")
        return None
    return np.array(Image.open(p).convert("RGBA"))


def _outdoors(arr, t=0.18):
    """屋里那件东西搬到屋外：形状、像素一模一样，只往林下的冷暗里压一点（屋里是暖光）。"""
    out = arr.copy()
    m = out[..., 3] > 0
    for y, x in zip(*np.nonzero(m)):
        out[y, x, :3] = mixc(out[y, x, :3], from_hex("#1f2e27"), t)
    return out


RADIO_ON_STALL = (41, 47)    # stall 里收音机底边中点踩的像素（台面上面那一行）


def placed_radio():
    """送回小吃棚的收音机：就是树屋里 room_radio 那一台（同一张像素），放在柜台台面左边。"""
    a = _from_room("room_radio")
    if a is None:
        return None
    s = Spr(a.shape[1], a.shape[0])
    s.a = _outdoors(a)
    return s


def placed_sign():
    """立回底座上的路标：就是树屋里 room_sign 那一块（同样 4 帧、同样自己转），去掉屋里那个十字底座，
    杆子直接插进 sign_base 顶上的方孔。"""
    a = _from_room("room_sign")
    if a is None:
        return None
    meta = json.loads((OUT / "room_sign.json").read_text())
    fw, fh, n = meta["frame_w"], meta["frame_h"], meta["frames"]
    frames = []
    for k in range(n):
        f = a[:, k * fw:(k + 1) * fw].copy()
        f = f[:fh - 3]                 # 屋里的十字底座（最下面 3 行）不要
        s = Spr(fw, f.shape[0])
        s.a = _outdoors(f)
        frames.append(s)
    return frames, meta.get("ms", 250)


# ---------------------------------------------------------------- 第四版：剧情姐加的细节

JAR_IN_SHOP = (19, 54)       # shop 里橱窗下层架子上、空点心罐底边中点踩的像素
PHOTO_ON_SHOP = (86, 47)     # shop 里门右边墙上、旧招贴底边中点的像素


def shop_jar():
    """橱窗玻璃后面那只装点心的空罐：玻璃罐、铁皮盖，罐身贴着一张小纸条（两行看不清的字）。
    隔着积灰的玻璃，整个压暗。"""
    s = Spr(8, 9)
    body = s.rect(0, 2, 7, 8) & ~s.rect(0, 8, 0, 8) & ~s.rect(7, 8, 7, 8)
    s.fill(body, BARK, 1.2)
    s.fill(edges(body)[2] | edges(body)[3], WATER, 0)                  # 玻璃的两条边
    s.put(1, 3, WATER[1])
    s.put(1, 4, WATER[1])
    s.fill(s.rect(1, 1, 6, 2), TIN, 1.4 + (s.yy == 1))                 # 盖
    s.fill(s.rect(2, 0, 5, 0), TIN, 1.2)
    lab = s.rect(2, 4, 6, 7)
    s.fill(lab, TAG, 0)
    s.fill(s.rect(3, 5, 5, 5) | s.rect(3, 6, 4, 6), DUST, 0)          # 两行字
    s.put(2, 8, BARK[2])
    return s


def shop_photo():
    """店门边那张被雨泡皱的旧招贴：只剩半张合影，右边是撕掉的毛边。一个人站在柜台后面，脸转开；
    一只手从照片右边缘伸进来，往她头上扣一顶纸帽。一角被风吹起来（亮一点）。顶上一颗图钉。"""
    rows = [
        "....o.......",
        "PPPPPPPPPPP.",
        "Pddtttddddp.",
        "Pdtttttaasss",
        "Pddhhhaaasss",
        "Pdhhhhddddss",
        "Pddmmmddddp.",
        "Pdmmmmmdddp.",
        "Pdmmmmmdddp.",
        "Pcccccccccpp",
        "Pdddddddddp.",
        "PpPPPpPPPp..",
        "PPPpPPPPPPL.",
        "..........LL",
    ]
    # h 她的头发（暗的浅金），a 伸进来的那只手，s 照片外那个人的袖子（另一种颜色），t 纸帽
    pal = {"P": TAG[0], "p": mixc(TAG[0], BARK[0], 0.35), "d": BARK[2], "m": WOOD_C[2], "h": mixc(COPPER[2], DUST[1], 0.5),
           "a": DUST[2], "s": PAINT[3], "t": TAG[1], "c": WOOD[3], "o": TIN[3], "L": TAG[1]}
    s = Spr(len(rows[0]), len(rows))
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != ".":
                s.a[y, x] = tuple(pal[ch]) + (255,)
    return s


# ================================================================ 第五版：被撞出凹口的树线（单独一屏）+ 画的特写
# 以前的 broken_treeline（贴在 Mid 层里）已经删掉：循环层里每隔一段重复一次、标题画面上也有，融不进背景。
# 画上大象背的那道弧，和坠毁现场树线上被撞出来的凹口是同一条曲线：back_arc(u)，u 从 0 到 1，0 和 1 是两头（高 0），
# 中间最高（1）。树线上的弧正好是画上那道弧的 VIEW_K 倍（3 倍：宽 276 / 高 81 对 宽 92 / 高 27），引擎把 drawing_arc.png
# 最近邻放大 VIEW_K 倍、按 json 里的端点对齐，就严丝合缝地叠在凹口上。
# 树线不贴在森林的视差层里（循环层里融不进去）：是一张单独的全屏画面（treeline_view_*.png，480×270 的平面侧视，
# 不透视、不仰视），剧本 treeline_match / 看树冠缺口的时候淡入、叠弧线、淡出。分四层，画面里各自轻轻漂一点：
#   sky   天和雾光（不动）       far   远处一排树梢剪影（漂得最慢）
#   main  坠毁现场那排树冠，中间被撞出凹口（弧线跟着这一层走）       near  近处压在下沿的几簇枝梢（漂得最快）
# 天 = art/forest 的 BANDS 背景色档 + 凹口后面一团 POOL_C 雾光（0~2 档）；树冠 = 中景 Mid 的叶子色阶往雾带褪一成。
# 凹口：整排一样高的云杉，弧上面、两道撕开的墙之间全挖掉；断面下面补一层撕碎压在一起的枝叶（弧是一条连着的毛边），
# 每棵削断的树戳出一截劈开的深木色树干茬，几根折断翘起的枝、墙上挂下来的残枝。不画浅色断桩。

def back_arc(u):
    u = np.clip(np.asarray(u, float), 0, 1)
    return (1 - (2 * u - 1) ** 2) ** 0.75


ARC_DRAW = dict(x0=44, x1=136, y_end=58, h=27)          # 画上的弧（drawing_closeup / drawing_arc 的像素坐标）
VIEW_K = 3                                               # 树线上的弧 = 画上的几倍
ARC_VIEW = dict(x0=102, x1=102 + 92 * VIEW_K, y_end=198, h=27 * VIEW_K)   # 树线上的弧（treeline_view_main 的像素坐标）
VIEW_W = {"sky": 480, "far": 488, "main": 496, "near": 512}   # 各层图宽（比屏幕宽的那截就是能漂的距离）
VIEW_DRIFT = {"sky": 0.0, "far": 0.6, "main": 1.2, "near": 2.6}   # 每秒往左漂几像素（漂到图的右边缘就停）


def arc_y(a, x):
    u = (np.asarray(x, float) - a["x0"]) / (a["x1"] - a["x0"])
    return a["y_end"] - a["h"] * back_arc(u)


def arc_points(a, n=7):
    xs = np.linspace(a["x0"], a["x1"], n)
    return [[int(round(x)), int(round(float(arc_y(a, x))))] for x in xs]


def _dither_pick(cols, t, y, x):
    """t（0..len-1 的小数）在相邻两档之间用 Bayer 抖动挑一档（硬边、色数少）。"""
    lo = int(np.floor(t))
    fr = t - lo
    if lo >= len(cols) - 1:
        return cols[-1]
    return cols[lo + (FA.BAYER[y % 4, x % 4] < fr)]


def _paste_rgba(dst, img, x, y):
    """img 的底边中点放在 (x, y)（树根），不绕回。"""
    h, w = img.shape[:2]
    left, top = int(x) - w // 2, int(y) - h + 1
    H_, W_ = dst.shape[:2]
    x0, y0, x1, y1 = max(0, left), max(0, top), min(W_, left + w), min(H_, top + h)
    if x0 >= x1 or y0 >= y1:
        return
    src = img[y0 - top:y1 - top, x0 - left:x1 - left]
    m = src[..., 3] > 0
    dst[y0:y1, x0:x1][m] = src[m]


def view_sky():
    """天：就是 art/forest 的那几档背景色（上面几乎是黑的墨绿，往下进一条青绿灰的雾带，170 附近最亮），
    档与档之间 Bayer 抖动，不画渐变。凹口后面一团雾光（坠毁那一下被雾打散的天光，不暖）：同一套光斑，
    往 FA.POOL_C 提 0~2 档（每档 0.7），扁的一团，正好从凹口里透出来。"""
    W, Hh = VIEW_W["sky"], 270
    a = np.zeros((Hh, W, 4), np.uint8)
    cx, cy = (ARC_VIEW["x0"] + ARC_VIEW["x1"]) / 2, 165.0
    xs = np.arange(W)
    for y in range(Hh):
        i, bf = FA.band_frac(y)
        b_px = np.minimum(i + (FA.BAYER[(y + 2) % 4, (xs + 1) % 4] < bf), len(FA.BANDS) - 1)
        e = ((xs - cx) / 250.0) ** 2 + ((y - cy) / 72.0) ** 2
        lv = np.clip(1 - e, 0, 1) ** 1.1 * 2.0
        lo = np.floor(lv)
        p_px = np.minimum(2, lo + (FA.BAYER[(y + 1) % 4, (xs + 3) % 4] < lv - lo))
        for bb, pp in set(zip(b_px.tolist(), p_px.tolist())):
            sel = (b_px == bb) & (p_px == pp)
            a[y, sel] = tuple(FA.pool_color(int(bb), int(pp) * 0.7)) + (255,)
    return a


def view_far():
    """远处一排树梢：两档的剪影（受光边 + 身体），比主树线小、矮，往雾里褪（只从凹口和树缝里看得见）。"""
    W, Hh = VIEW_W["far"], 270
    a = np.zeros((Hh, W, 4), np.uint8)
    rng = np.random.default_rng(311)
    pal = [mixc(from_hex("#16261f"), from_hex("#517060"), t) for t in (0.38, 0.55)]
    x = -10
    while x < W + 10:
        r = int(rng.integers(13, 19))
        hgt = int(rng.integers(110, 140))
        tip = int(rng.uniform(146, 180))
        img = FA.conifer(hgt, r, int(rng.integers(1, 10 ** 6)), pal, pal, detail=0, crown=0.98, droop=0.55)
        _paste_rgba(a, img, x, tip + img.shape[0] - 3)
        x += int(rng.integers(10, 18))
    a[215:, :] = tuple(pal[0]) + (255,)
    a[..., 3] = np.where(a[..., 3] > 0, 255, 0)
    return a


# 和 art/forest 的中景 Mid 同一条叶子色阶，往雾带的颜色褪一成（远景；Mid 在森林里也是靠空气透视褪出来的，不然最暗那档近乎纯黑）
MAIN_FOL = [mixc(c, from_hex("#2b4135"), 0.1) for c in R("#0c1712", 5, 0.15, 10)]
MAIN_BARK = [mixc(c, from_hex("#2b4135"), 0.1) for c in R("#161e1a", 4, 0.08, 10)]
SNAP = H("#1f2620", "#2a2f27", "#363830")  # 断口新露出来的木头：只比树皮亮一点点，偏暖灰（不是浅灰）


def view_main():
    """坠毁现场那排树冠（平面侧视）：一排高云杉，树梢高低错开连成天际线；中间一段被撞出一道弧形的凹口——
    凹口里的树都被齐齐削断，断面连起来就是那道弧（和画上大象的背同一条曲线，凹口后面透出雾光）。
    断面不是一刀平：一簇簇撕开的针叶往上翘、往下缺，每棵树的树干在弧上戳出一截劈开的茬（深木色，往左歪：
    飞船从右上方斜着下来），几根折断的枝翘起来。凹口两边的树被撕掉半边枝（边上一截截参差），
    残枝斜斜挂下来。下面两排更近、更暗的树梢把画面下半填满。最亮的地方也只比树冠受光那一档亮一点。"""
    W, Hh = VIEW_W["main"], 270
    a = np.zeros((Hh, W, 4), np.uint8)
    rng = np.random.default_rng(321)
    A = ARC_VIEW
    yy, xx = np.mgrid[0:Hh, 0:W]

    def tree(x, tip, r, hgt, seed, fol=MAIN_FOL, bark=MAIN_BARK, detail=2, **kw):
        img = FA.conifer(hgt, r, seed, fol, bark, detail=detail, crown=0.97, droop=float(rng.uniform(0.6, 0.85)),
                         grain=0.45, tier_lit=1.2, ragged=0.25, **kw)
        _paste_rgba(a, img, x, tip + img.shape[0] - 3)

    # 第一排：天际线。整排一样的高云杉（凹口里的那几棵原来也一样高，削掉的是上半截）
    trees = []
    x = -14
    while x < W + 20:
        r, hgt = int(rng.integers(22, 30)), int(rng.integers(230, 262))
        tip = int(rng.uniform(28, 78))
        tree(x, tip, r, hgt, int(rng.integers(1, 10 ** 6)))
        trees.append(x)
        x += int(rng.integers(18, 28))
    # 第二、三排：更近、更暗的树梢，把下半截填满（凹口最低的两头也在它们上面）
    dark2 = [mixc(c, from_hex("#06100c"), 0.25) for c in MAIN_FOL]
    dark3 = [mixc(c, from_hex("#06100c"), 0.45) for c in MAIN_FOL]
    for fol, (t0, t1), sp, seed0 in ((dark2, (200, 224), (26, 36), 400), (dark3, (228, 246), (22, 30), 500)):
        x = -10
        while x < W + 10:
            tree(x, int(rng.uniform(t0, t1)), int(rng.integers(30, 40)), 140, seed0 + x, fol=fol)
            x += int(rng.integers(*sp))
    a[250:, :] = np.where(a[250:, :, 3:] > 0, a[250:, :], np.array(tuple(dark3[0]) + (255,), np.uint8))
    row1 = a.copy()

    # 凹口：弧上面、两道被撕开的「墙」之间，全挖空（透出后面的远树和雾光）。
    # 墙：从弧的两头往上张开，右边张得多（从右上方撞进来）；边上一截截参差（一层层被撕掉的枝，宽窄不一）
    def rag(seed, n, lo, hi, step=(3, 8)):
        r_ = np.random.default_rng(seed)
        out = np.zeros(n)
        i = 0
        while i < n:
            w_ = int(r_.integers(*step))
            out[i:i + w_] = r_.uniform(lo, hi)
            i += w_
        return out
    ys = np.arange(Hh)
    up = np.clip(A["y_end"] - ys, 0, None)
    xl = A["x0"] + 2 - 0.12 * up - rag(331, Hh, -2, 9)
    xr = A["x1"] - 2 + 0.32 * up + rag(332, Hh, -2, 11)
    xr = np.minimum(xr, W - 1)
    top_y = np.where((xx >= A["x0"]) & (xx <= A["x1"]), arc_y(A, xx), A["y_end"])
    # 断面：一簇簇针叶往上翘 1~2 格、偶尔往下缺 1~3 格（宽 1~3 格一簇）
    jag = np.zeros(W)
    i = 0
    while i < W:
        w_ = int(rng.integers(1, 4))
        jag[i:i + w_] = rng.choice([-2, -1, -1, 0, 0, 0, 1, 1, 2, 3])
        i += w_
    notch = (xx >= xl[:, None]) & (xx <= xr[:, None]) & (yy < top_y + jag[None, :])
    a[notch] = 0
    # 断面下面一层撕碎、压在一起的枝叶（一列列深浅不一的厚度），弧就是一条连着的毛边，
    # 不会被削断的树冠一棵棵的「^」顶断成一串小尖：再往下才露出冠和冠之间漏雾光的缝
    mat = rag(333, W, 4, 11, step=(2, 6))
    mat_m = (~notch) & (xx > A["x0"] - 1) & (xx < A["x1"] + 1) & (yy >= top_y + jag[None, :]) & \
        (yy < top_y + jag[None, :] + mat[None, :]) & (a[..., 3] == 0)
    for y, x in zip(*np.nonzero(mat_m)):
        d = y - (top_y[y, x] + jag[x])
        k = 1 if d < 2 else 0
        a[y, x] = tuple(MAIN_FOL[k + (FA.BAYER[y % 4, x % 4] < 0.3)]) + (255,)
    op = a[..., 3] > 0

    def put(x, y, c):
        if 0 <= x < W and 0 <= y < Hh:
            a[y, x] = tuple(c) + (255,)

    # 断口上沿：接到雾光的那一格亮一档（新撕开的针叶，最亮也就是树冠受光那一档）
    above_empty = np.zeros_like(op)
    above_empty[1:] = ~op[:-1]
    in_gap = (xx > A["x0"] - 2) & (xx < A["x1"] + 2) & (yy > top_y - 5) & (yy < top_y + 5)
    rim = op & above_empty & in_gap
    for y, x in zip(*np.nonzero(rim)):
        a[y, x, :3] = MAIN_FOL[3] if (x * 7 + y) % 5 else MAIN_FOL[2]
    # 劈开的树干茬：凹口里每棵被削断的树，树干在弧上戳出一截（往左歪），顶上参差的劈茬，深木色
    for cxt in trees:
        if not A["x0"] + 8 < cxt < A["x1"] - 8:
            continue
        y0 = int(round(float(arc_y(A, cxt)))) + 2
        tw = int(rng.integers(3, 5))
        hh = int(rng.integers(6, 13))
        lean = rng.uniform(0.2, 0.5)
        for k in range(hh):
            sx = int(round(-lean * k))
            for i in range(tw):
                if k > hh - 4 and rng.random() < 0.35 + 0.18 * (k - hh + 4):   # 劈茬：顶上几格缺牙
                    continue
                c = MAIN_BARK[2] if i == 0 else MAIN_BARK[1] if i < tw - 1 else MAIN_BARK[0]
                if k >= hh - 3 and i == 0:
                    c = SNAP[1]
                put(cxt - tw // 2 + i + sx, y0 - k, c)
        put(cxt - tw // 2 + int(round(-lean * (hh - 1))), y0 - hh, SNAP[0])
    # 折断的枝：从断面伸出来、往左上翘一截，末端一小簇针叶（深绿），稀稀拉拉
    for x in range(A["x0"] + 12, A["x1"] - 10, 11):
        x += int(rng.integers(-3, 4))
        if rng.random() < 0.35:
            continue
        y0 = int(round(float(arc_y(A, x)))) + 1
        ln = int(rng.integers(3, 8))
        sl = rng.uniform(0.5, 1.4)
        for k in range(ln):
            put(x - k, y0 - int(round(k * sl * 0.6)), MAIN_BARK[1] if k < ln - 1 else SNAP[0])
        ex, ey = x - ln, y0 - int(round(ln * sl * 0.6))
        for dx, dy in ((0, 0), (-1, 0), (0, 1), (-1, -1)):
            if rng.random() < 0.8:
                put(ex + dx, ey + dy, MAIN_FOL[1])
    # 两边的墙：被撕下来、还连着一点皮的枝，斜斜往下挂进凹口（针叶一簇簇往下垂）
    hangs = [("r", 92, 15), ("r", 128, 18), ("r", 160, 12), ("l", 110, 11), ("l", 158, 9)]
    for side, y0, ln in hangs:
        y0 += int(rng.integers(-4, 5))
        if side == "r":
            x0 = int(xr[y0]) + 1
            while x0 < W - 1 and not op[y0, x0]:
                x0 += 1
            dx_, dy_ = -0.85, 0.9
        else:
            x0 = int(xl[y0]) - 1
            while x0 > 0 and not op[y0, x0]:
                x0 -= 1
            dx_, dy_ = 1.0, 0.45
        px, py = float(x0), float(y0)
        for k in range(ln):
            px += dx_
            py += dy_ * (0.6 + 0.5 * k / ln)
            ix, iy = int(round(px)), int(round(py))
            if iy >= top_y[min(Hh - 1, iy), min(W - 1, max(0, ix))] - 1:
                break
            put(ix, iy, MAIN_BARK[1])
            if k % 2 == 0:
                for d in range(1, int(rng.integers(2, 4))):
                    put(ix, iy + d, MAIN_FOL[1] if d == 1 else MAIN_FOL[0])
                put(ix + (1 if side == "r" else -1), iy + 1, MAIN_FOL[2])
    # 被撕开的那一侧：墙边上的叶子新露出来的断面暗一档（不是浅色）
    del row1
    a[..., 3] = np.where(a[..., 3] > 0, 255, 0)
    a[a[..., 3] == 0] = 0
    return a


def view_near():
    """近处：下沿压着几簇很暗的枝梢（比主树线更暗、几乎是剪影），左上角垂下来一截枝。不挡凹口。"""
    W, Hh = VIEW_W["near"], 270
    a = np.zeros((Hh, W, 4), np.uint8)
    rng = np.random.default_rng(341)
    fol = [mixc(c, from_hex("#040b08"), 0.62) for c in MAIN_FOL]
    bark = [mixc(c, from_hex("#040b08"), 0.6) for c in MAIN_BARK]
    x = -6
    while x < W + 6:
        img = FA.conifer(120, int(rng.integers(20, 30)), int(rng.integers(1, 10 ** 6)), fol, bark, detail=1,
                         crown=0.97, droop=0.7, grain=0.4)
        _paste_rgba(a, img, x, int(rng.uniform(250, 262)) + img.shape[0] - 3)
        x += int(rng.integers(26, 46))
    # 左上角垂下来的一截枝（只要树冠的一边：一棵很大的树，树干在画面外左边）
    img = FA.conifer(150, 70, 3417, fol, bark, detail=1, crown=0.97, droop=0.85, grain=0.4, bough=True)
    _paste_rgba(a, img, -62, 30)
    a[..., 3] = np.where(a[..., 3] > 0, 255, 0)
    a[a[..., 3] == 0] = 0
    return a


def treeline_view():
    return {"sky": view_sky(), "far": view_far(), "main": view_main(), "near": view_near()}


def save_treeline_view():
    """存四层图 + treeline_view.json（弧在 main 层图里的坐标、各层漂移），并更新 drawing_arc.json 里对齐用的数。"""
    out = {}
    layers = treeline_view()
    for k, arr in layers.items():
        Image.fromarray(arr).save(OUT / f"treeline_view_{k}.png")
        out[f"treeline_view_{k}"] = arr
    meta = {
        "layers": ["sky", "far", "main", "near"],
        "drift": VIEW_DRIFT,
        "arc_layer": "main",
        "arc_points": arc_points(ARC_VIEW),
        "arc_end_left": [ARC_VIEW["x0"], ARC_VIEW["y_end"]], "arc_end_right": [ARC_VIEW["x1"], ARC_VIEW["y_end"]],
        "arc_top": [(ARC_VIEW["x0"] + ARC_VIEW["x1"]) // 2, ARC_VIEW["y_end"] - ARC_VIEW["h"]],
        "note": "单独一屏（平面侧视，不挂森林的视差层）：四层图左上角都放在屏幕 (0,0)，按 drift 每秒往左漂（漂到图的右边缘贴着屏幕右边就停）；"
                "drawing_arc 放大 scale_to_treeline 倍、arc_end_left 对到 main 层的 arc_end_left，跟着 main 层漂",
    }
    (OUT / "treeline_view.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return out


def drawing_arc_meta():
    return {
        "arc_end_left": [ARC_DRAW["x0"], ARC_DRAW["y_end"]], "arc_end_right": [ARC_DRAW["x1"], ARC_DRAW["y_end"]],
        "arc_top": [(ARC_DRAW["x0"] + ARC_DRAW["x1"]) // 2, ARC_DRAW["y_end"] - ARC_DRAW["h"]],
        "scale_to_treeline": VIEW_K,
        "treeline_arc_end_left": [ARC_VIEW["x0"], ARC_VIEW["y_end"]],
        "note": "最近邻放大 scale_to_treeline 倍后，把 arc_end_left 对到 treeline_view_main 的 treeline_arc_end_left（图内坐标），两条弧重合"}


def drawing_closeup():
    """晨醒来画的大象（特写，UI 用）：一张皱过又摊平的纸（几道折痕把纸分成几块，各接到的光不一样），
    铅笔线是深灰（偏一点紫，和背包图标 icon_drawing 同一个色），不是纯黑。朝左的大象：长鼻子垂下来卷一下，
    头侧面一只大耳朵、头顶后面再露出另一只，圆滚的背（就是那道弧），四条柱子腿，小尾巴；
    画得不太准：有的线描了两遍，一条腿和鼻子有擦掉的旧线（浅灰的糊印）。肚子底下几道斜着的排线。"""
    W, Hh = 160, 110
    s = Spr(W, Hh)
    PAPER = H("#aaa08e", "#c8bea9", "#e2dac8")          # 和 icon_drawing 的纸同色（暗 -> 亮）
    PEN = H("#605c6e", "#7a768a")                        # 铅笔：深灰偏紫（icon 的 96,92,110）
    ERASE = from_hex("#b9b0a0")                          # 擦掉的痕迹
    paper = s.poly([(2, 3), (60, 1), (157, 2), (158, 60), (157, 107), (90, 108), (1, 108), (0, 50)])
    # 折痕把纸切成几块：左上那块朝光最亮，右下那块最暗
    c1 = s.xx * 0.19 + 40 - s.yy          # 斜着的一道（从左边 y=40 到右边 y=70）
    c2 = (s.yy * 0.23 + 70) - s.xx        # 竖着偏斜的一道（从上面 x=70 到下面 x=95）
    t = np.where(c1 > 0, np.where(c2 > 0, 2, 1.4), np.where(c2 > 0, 1.2, 0.6))
    s.fill(paper, PAPER, t)
    for c in (c1, c2):
        crease = paper & (np.abs(c) < 0.6)
        s.fill(crease, PAPER, 0.4)
        s.fill(paper & (c > 0.6) & (c < 1.6), PAPER, 2)
    # 右上角折过一个角（折回去的那块暗一点）
    dog = s.poly([(140, 2), (157, 2), (157, 18)])
    s.fill(dog, PAPER, 0.3)
    s.fill(s.line((140, 2), (157, 18)), PAPER, 1)
    # 擦掉的旧线：一条歪了的鼻子、一条腿
    old = s.line((26, 64), (18, 78), (16, 90)) | s.line((30, 66), (22, 80), (21, 90)) | s.line((96, 74), (99, 98)) | s.line((102, 75), (104, 97))
    old = dilate(old, 1) & (noise(s, 131, (2, 2)) > -0.25)
    for y, x in zip(*np.nonzero(old & paper)):
        s.a[y, x, :3] = mixc(s.a[y, x, :3], ERASE, 0.6)
    pen = np.zeros((Hh, W), bool)
    soft = np.zeros((Hh, W), bool)

    def L(*pts, light=False):
        m = s.line(*[(int(round(x)), int(round(y))) for x, y in pts])
        if light:
            soft[:] |= m
        else:
            pen[:] |= m

    # 背：那道弧（drawing_arc 就从这里取）
    arc_px = np.zeros((Hh, W), bool)
    pts = [(x, float(arc_y(ARC_DRAW, x))) for x in np.linspace(ARC_DRAW["x0"], ARC_DRAW["x1"], 60)]
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        arc_px |= s.line((int(round(xa)), int(round(ya))), (int(round(xb)), int(round(yb))))
    pen |= arc_px
    # 描了第二遍的一小截（背的中段，偏上 1 格）
    L((70, float(arc_y(ARC_DRAW, 70)) - 1), (84, float(arc_y(ARC_DRAW, 84)) - 1), light=True)
    # 屁股和尾巴
    L((136, 58), (138, 64), (136, 72), (131, 76))
    L((137, 61), (142, 67), (141, 72))
    s_tail = s.rect(140, 72, 142, 73)
    # 头：一个歪一点的圈，接在背的前头
    head = s.ell(36, 57, 12, 12) & ~s.ell(36, 57, 11, 11)
    pen |= head & ~s.ell(47, 60, 8, 12)
    # 大耳朵（头侧面），另一只从头顶后面露出一点
    ear = s.ell(46, 60, 9, 12) & ~s.ell(46, 60, 8, 11)
    pen |= ear
    L((47, 52), (50, 60), (47, 67), light=True)
    L((28, 46), (31, 42), (35, 44))
    # 眼睛
    pen |= s.rect(30, 55, 31, 55)
    # 长鼻子：从脸前面垂下来，往外卷一圈；两条边
    L((26, 63), (22, 72), (20, 82), (20, 90), (17, 95), (13, 95), (11, 92), (13, 89), (16, 90))
    L((30, 67), (26, 76), (25, 86), (24, 93), (21, 98), (15, 99))
    # 肚子
    L((52, 76), (80, 79), (110, 78), (131, 76))
    # 四条腿（柱子，平脚；第三条描歪了又补了一笔）
    for x0_, y1 in ((54, 99), (68, 100), (104, 99), (118, 98)):
        L((x0_, 77), (x0_ - 1, y1))
        L((x0_ + 7, 79), (x0_ + 7, y1))
        L((x0_ - 1, y1), (x0_ + 7, y1))
    L((105, 80), (106, 96), light=True)
    # 肚子底下的排线
    for k in range(9):
        x = 60 + k * 7
        L((x, 70), (x + 4, 76), light=True)
    s.fill(pen & paper, PEN, 0)
    s.fill(soft & paper & ~pen, PEN, 1)
    s.fill(s_tail, PEN, 0)
    s._arc = arc_px & paper
    return s


def drawing_arc(closeup):
    """只有背的那道弧：从特写里原样取出来（同样的像素），透明底。"""
    s = Spr(closeup.w, closeup.h)
    m = closeup._arc
    s.a[m] = closeup.a[m]
    return s


def view_frame(t=0.0, with_arc=False, arc_alpha=0.8):
    """树冠缺口那一屏在第 t 秒的样子（和引擎同一套：各层左上角在 (-drift*t, 0)，漂到图的右边缘贴屏幕右边就停；
    with_arc = 叠上放大 VIEW_K 倍的 drawing_arc，跟着 main 层走）。"""
    bg = np.zeros((270, 480, 3), np.uint8)
    offs = {}
    for k in ("sky", "far", "main", "near"):
        a = np.array(Image.open(OUT / f"treeline_view_{k}.png"))
        off = int(round(min(VIEW_DRIFT[k] * t, a.shape[1] - 480)))
        offs[k] = off
        a = a[:, off:off + 480]
        m = a[..., 3] > 0
        bg[m] = a[m][:, :3]
    if with_arc:
        arc = np.array(Image.open(OUT / "drawing_arc.png"))
        big = np.repeat(np.repeat(arc, VIEW_K, 0), VIEW_K, 1)
        ex, ey = ARC_DRAW["x0"], ARC_DRAW["y_end"]
        ox_, oy_ = ARC_VIEW["x0"] - ex * VIEW_K - offs["main"], ARC_VIEW["y_end"] - ey * VIEW_K
        hh, ww = big.shape[:2]
        for j in range(hh):
            for i in range(ww):
                if big[j, i, 3] and 0 <= oy_ + j < 270 and 0 <= ox_ + i < 480:
                    y_, x_ = oy_ + j, ox_ + i
                    bg[y_, x_] = (bg[y_, x_] * (1 - arc_alpha) + big[j, i, :3] * arc_alpha).astype(np.uint8)
    return bg


def preview_v5(d):
    """树冠缺口那一屏（刚淡入 / 漂到头）、弧线叠在凹口上、画的特写。"""
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for name, t, wa in (("v5_view", 0.0, False), ("v5_view_arc", 2.0, True), ("v5_view_end", 30.0, False)):
        p = d / f"{name}.png"
        Image.fromarray(view_frame(t, wa)).resize((1440, 810), Image.NEAREST).save(p)
        out.append(p)
    cl = np.array(Image.open(OUT / "drawing_closeup.png"))
    z = np.zeros((cl.shape[0] + 10, cl.shape[1] + 10, 3), np.uint8)
    z[:] = (20, 26, 23)
    m = cl[..., 3] > 0
    z[5:5 + cl.shape[0], 5:5 + cl.shape[1]][m] = cl[m][:, :3]
    p = d / "v5_drawing_closeup_x3.png"
    Image.fromarray(z).resize((z.shape[1] * 3, z.shape[0] * 3), Image.NEAREST).save(p)
    out.append(p)
    return out


# ================================================================ 输出

def save(name, s, frames=None, ground_row=None, meta=None, ms=400):
    if frames:
        w = frames[0].w
        arr = np.concatenate([f.a for f in frames], 1)
    else:
        arr = s.a
    a = arr.copy()
    if name != "fog_bank":
        a[..., 3] = np.where(a[..., 3] > 0, 255, 0)
        a[a[..., 3] == 0] = 0
    Image.fromarray(a).save(OUT / f"{name}.png")
    if frames or ground_row is not None or meta:
        m = {}
        if frames:
            m.update(frame_w=w, frame_h=frames[0].h, frames=len(frames), ms=ms)
        if ground_row is not None:
            m.update(ground_row=ground_row)
        m.update(meta or {})
        (OUT / f"{name}.json").write_text(json.dumps(m, ensure_ascii=False, indent=1))
    return a


def build(with_treehouse=False):
    """treehouse.png 已经交给室内那边做成可淡出前墙的剖面（treehouse_back / front），这张只留作风格参考：
    默认不重画它（加 --treehouse 才重画）。"""
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    if with_treehouse:
        out["treehouse"] = save("treehouse", treehouse())
    elif (OUT / "treehouse.png").exists():
        out["treehouse"] = np.array(Image.open(OUT / "treehouse.png").convert("RGBA"))
    for name, fn in (("empty_house", empty_house), ("empty_item", empty_item), ("pump", pump),
                     ("shop", shop), ("stall", stall), ("log", log_block), ("log_moved", log_moved),
                     ("luggage", luggage), ("mat_scrap", mat_scrap), ("mat_resin", mat_resin), ("mat_branch", mat_branch),
                     ("fog_bank", fog_bank)):
        out[name] = save(name, fn())
    out["branch_a"] = save("branch_a", branch_piece(1, "a"))
    out["branch_b"] = save("branch_b", branch_piece(2, "b"))
    fr = cloth()
    out["cloth"] = save("cloth", None, frames=fr)
    out["hoofprints"] = save("hoofprints", hoofprints(), ground_row=1)
    # ---- 第三版
    for name, fn in (("glade_rock", glade_rock), ("signal_box", signal_box), ("sign_base", sign_base),
                     ("road_house", road_house), ("plank", plank)):
        out[name] = save(name, fn())
    out["pine_sap"] = save("pine_sap", None, frames=pine_sap(), ms=[1600, 200])
    out["plank_bridge"] = save("plank_bridge", plank_bridge(), ground_row=4,
                               meta={"host": "hollow", "note": "和 hollow.png 同尺寸、同 ground_row，放在同一个位置叠上去"})
    eh = out["empty_house"]
    out["clock_window"] = save("clock_window", clock_window(),
                               meta={"host": "empty_house", "offset": anchor_offset(eh.shape[1], eh.shape[0], *CLOCK_SILL)})
    sh = out["shop"]
    out["shop_jar"] = save("shop_jar", shop_jar(), meta={"host": "shop", "offset": anchor_offset(sh.shape[1], sh.shape[0], *JAR_IN_SHOP)})
    out["shop_photo"] = save("shop_photo", shop_photo(), meta={"host": "shop", "offset": anchor_offset(sh.shape[1], sh.shape[0], *PHOTO_ON_SHOP)})
    # ---- 第五版
    out.update(save_treeline_view())
    cl = drawing_closeup()
    out["drawing_closeup"] = save("drawing_closeup", cl)
    out["drawing_arc"] = save("drawing_arc", drawing_arc(cl), meta=drawing_arc_meta())
    rh = out["road_house"]
    lamp = placed_lamp()
    out["placed_lamp"] = save("placed_lamp", lamp, meta={
        "host": "road_house", "offset": anchor_offset(rh.shape[1], rh.shape[0], HOOK[0] + 2 - 4 + lamp.w // 2, HOOK[1] - 2 + lamp.h - 1)})
    st = out["stall"]
    r = placed_radio()
    if r is not None:
        out["placed_radio"] = save("placed_radio", r, meta={
            "host": "stall", "offset": anchor_offset(st.shape[1], st.shape[0], *RADIO_ON_STALL)})
    ps = placed_sign()
    if ps is not None:
        fr, ms_ = ps
        out["placed_sign"] = save("placed_sign", None, frames=fr, ms=ms_,
                                  meta={"host": "sign_base", "offset": [0, -SIGN_BASE_TOP]})
    out["hollow"] = save("hollow", hollow(), ground_row=4)
    out["depressions"] = save("depressions", depressions(), ground_row=3)
    return out


GROUND_ROW = {"hoofprints": 1, "hollow": 4, "depressions": 3}


# ---------------------------------------------------------------- 预览

def background(cam):
    """森林各层按视差叠一屏 480×270（镜头左边缘在 cam），不含 front 层。"""
    out = np.zeros((270, 480, 3), np.uint8)
    for k, sc in FA.SCROLL.items():
        if k == "front":
            continue
        a = np.array(Image.open(ROOT / "art" / "forest" / f"{k}.png"))
        if a.shape[1] != 480:
            off = int(round(cam * sc)) % a.shape[1]
            a = np.roll(a, -off, axis=1)[:, :480]
        m = a[..., 3] > 0
        out[m] = a[m][:, :3]
    return out


def chen_frame():
    sh = np.array(Image.open(ROOT / "art" / "characters" / "chen" / "chen_oscar.png"))
    return sh[:, 7 * 68:8 * 68], (28, 56)


def place(bg, a, x_center, cam, ground_row=None, semi=False):
    """把图按底边中点贴在地面上（ground_row：这一行对齐地面）。"""
    h, w = a.shape[:2]
    gy = int(round(FA.ground_y((x_center) % FA.W)))
    top = gy - (h - 1) if ground_row is None else gy - ground_row
    left = int(x_center - cam - w // 2)
    for j in range(h):
        y = top + j
        if not 0 <= y < 270:
            continue
        for i in range(w):
            x = left + i
            if 0 <= x < 480 and a[j, i, 3] > 0:
                if semi:
                    al = a[j, i, 3] / 255
                    bg[y, x] = (bg[y, x] * (1 - al) + a[j, i, :3] * al).astype(np.uint8)
                else:
                    bg[y, x] = a[j, i, :3]


def put_chen(bg, x_center, cam):
    f, (fx, fy) = chen_frame()
    gy = int(round(FA.ground_y(x_center % FA.W)))
    top = gy - fy + 1          # chen.gd SINK = 1
    left = int(x_center - cam - fx)
    for j in range(f.shape[0]):
        for i in range(f.shape[1]):
            if f[j, i, 3] and 0 <= top + j < 270 and 0 <= left + i < 480:
                bg[top + j, left + i] = f[j, i, :3]


def previews(imgs, d):
    d.mkdir(parents=True, exist_ok=True)
    shots = {
        "preview_landmarks": (0, [("treehouse", 92), ("empty_house", 252), ("empty_item", 318), ("pump", 228),
                                  ("shop", 400), ("CHEN", 182)]),
        "preview_road": (500, [("stall", 560), ("log", 700), ("branch_a", 676), ("branch_b", 722), ("cloth", 800),
                               ("hoofprints", 840), ("hollow", 900), ("CHEN", 630)]),
        "preview_crash_slope": (100, [("fog_bank", 340), ("luggage", 150), ("mat_scrap", 190), ("mat_resin", 210),
                                      ("mat_branch", 230), ("pump", 250), ("log_moved", 320), ("depressions", 460),
                                      ("CHEN", 270)]),
    }
    paths = []
    for name, (cam, items) in shots.items():
        bg = background(cam)
        for k, x in items:
            if k == "CHEN":
                put_chen(bg, x, cam)
                continue
            a = imgs[k]
            if k == "cloth":
                a = a[:, :a.shape[1] // 2]
            place(bg, a, x, cam, GROUND_ROW.get(k), semi=(k == "fog_bank"))
        p = d / f"{name}.png"
        Image.fromarray(bg).resize((1440, 810), Image.NEAREST).save(p)
        paths.append(p)
    # 每张图单独放大，摆在中间调的雾色上看细节
    sheet_items = [k for k in imgs]
    pad = 6
    cells = []
    for k in sheet_items:
        a = imgs[k]
        sc = 2 if a.shape[0] > 60 or a.shape[1] > 130 else 4
        cells.append((k, a, sc))
    Wd = 1400
    x = y = 0
    rowh = 0
    pos = []
    for k, a, sc in cells:
        w, h = a.shape[1] * sc, a.shape[0] * sc
        if x + w > Wd:
            x, y, rowh = 0, y + rowh + pad, 0
        pos.append((k, a, sc, x, y))
        x += w + pad
        rowh = max(rowh, h)
    sheet = np.zeros((y + rowh, Wd, 3), np.uint8)
    sheet[:] = (40, 60, 50)
    for k, a, sc, x, y in pos:
        big = np.array(Image.fromarray(a).resize((a.shape[1] * sc, a.shape[0] * sc), Image.NEAREST))
        m = big[..., 3] > 0
        reg = sheet[y:y + big.shape[0], x:x + big.shape[1]]
        al = big[..., 3:4] / 255
        reg[:] = np.where(m[..., None], (reg * (1 - al) + big[..., :3] * al).astype(np.uint8), reg)
    p = d / "sheet_zoom.png"
    Image.fromarray(sheet).save(p)
    paths.append(p)
    return paths


def _blit(bg, a, left, top, semi=False):
    h, w = a.shape[:2]
    for j in range(h):
        y = top + j
        if not 0 <= y < 270:
            continue
        for i in range(w):
            x = left + i
            if 0 <= x < 480 and a[j, i, 3] > 0:
                if semi:
                    al = a[j, i, 3] / 255
                    bg[y, x] = (bg[y, x] * (1 - al) + a[j, i, :3] * al).astype(np.uint8)
                else:
                    bg[y, x] = a[j, i, :3]


def _frame(name, k=0):
    a = np.array(Image.open(OUT / f"{name}.png").convert("RGBA"))
    j = OUT / f"{name}.json"
    if j.exists():
        m = json.loads(j.read_text())
        if "frame_w" in m:
            fw = m["frame_w"]
            a = a[:, k * fw:(k + 1) * fw]
    return a


def compose(cam, items, fog=False):
    """items: (名字, 世界 x[, 帧]) 或 ("CHEN", x)。有 host/offset 的图自动跟着宿主的位置放。"""
    bg = background(cam)
    if fog:
        place(bg, np.array(Image.open(OUT / "fog_bank.png")), cam + 240, cam, None, semi=True)
    hosts = {}
    for it in items:
        name, x = it[0], it[1]
        if name == "CHEN":
            put_chen(bg, x, cam)
            continue
        a = _frame(name, it[2] if len(it) > 2 else 0)
        h, w = a.shape[:2]
        meta = json.loads((OUT / f"{name}.json").read_text()) if (OUT / f"{name}.json").exists() else {}
        if "offset" in meta and meta.get("host") in hosts:
            hx, hy = hosts[meta["host"]]
            ax, ay = hx + meta["offset"][0], hy + meta["offset"][1]
        else:
            ax = x - cam
            ay = int(round(FA.ground_y(x % FA.W)))
            if meta.get("host") in hosts and "ground_row" in meta:
                ax = hosts[meta["host"]][0]
            hosts[name] = (ax, ay)
        top = ay - (h - 1) if "ground_row" not in meta else ay - meta["ground_row"]
        _blit(bg, a, ax - w // 2, top)
    return bg


def previews_v3(d):
    shots = {
        "v3_glade": (1900, [("glade_rock", 2080), ("sign_base", 2134), ("placed_sign", 2134), ("signal_box", 2190),
                             ("CHEN", 2000)], True),
        "v3_glade_before": (1900, [("glade_rock", 2080), ("sign_base", 2134), ("signal_box", 2190), ("CHEN", 2150)], True),
        "v3_road": (1040, [("stall", 1100), ("placed_radio", 0), ("road_house", 1250), ("placed_lamp", 0),
                           ("CHEN", 1180)], False),
        "v4_shop_house": (2950 - 240 + 60, [("empty_house", 2900), ("clock_window", 0), ("empty_item", 2930),
                                            ("shop", 3120), ("shop_jar", 0), ("shop_photo", 0), ("CHEN", 3030)], False),
        "v3_bridge_house_pine": (2900 - 120, [("hollow", 2840), ("plank_bridge", 2840), ("empty_house", 2930),
                                              ("clock_window", 0), ("plank", 3010), ("pine_sap", 3070, 1),
                                              ("CHEN", 2985)], False),
    }
    paths = []
    for name, (cam, items, fog) in shots.items():
        bg = compose(cam, items, fog)
        p = d / f"{name}.png"
        Image.fromarray(bg).resize((1440, 810), Image.NEAREST).save(p)
        paths.append(p)
    # 岩画单独放大
    rock = np.array(Image.open(OUT / "glade_rock.png"))
    z = np.zeros((rock.shape[0] + 8, rock.shape[1] + 8, 3), np.uint8)
    z[:] = (62, 87, 72)
    _m = rock[..., 3] > 0
    z[4:4 + rock.shape[0], 4:4 + rock.shape[1]][_m] = rock[_m][:, :3]
    p = d / "v3_glade_rock_x6.png"
    Image.fromarray(z).resize((z.shape[1] * 6, z.shape[0] * 6), Image.NEAREST).save(p)
    paths.append(p)
    return paths


UI_IMAGES = {"drawing_closeup"}   # UI 上的特写（纸是亮的，和背包图标一样），不在场景里，不受「比晨暗」限制


def check(imgs):
    """硬规矩自检：alpha 只有 0/255（雾除外）、没有纯黑、比晨暗（最亮的像素 L < 0.62）。"""
    ok = True
    for k, a in imgs.items():
        al = set(np.unique(a[..., 3]).tolist())
        m = a[..., 3] > 0
        cols = np.unique(a[m][:, :3], axis=0)
        Ls = np.array([to_lab(tuple(c))[0] for c in cols])
        black = (cols.max(1) < 8).any()
        bad_alpha = k != "fog_bank" and not al <= {0, 255}
        msg = f"  {k:12s} {a.shape[1]}x{a.shape[0]}  色数 {len(cols):3d}  L {Ls.min():.2f}~{Ls.max():.2f}"
        if bad_alpha or black or (Ls.max() > 0.62 and k not in UI_IMAGES):
            ok = False
            msg += "  <-- " + ("半透明 " if bad_alpha else "") + ("纯黑 " if black else "") + ("太亮" if Ls.max() > 0.62 else "")
        print(msg)
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="把合成预览存到这个目录")
    ap.add_argument("--treehouse", action="store_true", help="也重画 treehouse.png（默认不动它）")
    ap.add_argument("--treeline", action="store_true",
                    help="只重画树冠缺口那一屏（treeline_view_*.png + .json）并更新 drawing_arc.json，别的图不动")
    args = ap.parse_args()
    if args.treeline:
        imgs = save_treeline_view()
        (OUT / "drawing_arc.json").write_text(json.dumps(drawing_arc_meta(), ensure_ascii=False, indent=1))
        good = check(imgs)
        if args.preview:
            for p in preview_v5(Path(args.preview)):
                print("preview", p)
        sys.exit(0 if good else "有图不合规矩，见上面")
    imgs = build(args.treehouse)
    good = check(imgs)
    if args.preview:
        for p in previews(imgs, Path(args.preview)) + [preview_cloth(Path(args.preview))] + previews_v3(Path(args.preview)) + preview_v5(Path(args.preview)):
            print("preview", p)
    if not good:
        sys.exit("有图不合规矩，见上面")
