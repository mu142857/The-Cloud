"""针叶林视差（第一关）· 方向 C「Silvaron 式的林冠之下」。以后改森林图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/forest_art.py [--preview 目录]

输出 art/forest/*.png（1 倍）。原版在 tools/variants/original.py，最初的 C 稿在 tools/variants/c_canopy.py。
结构照 Phage 的 Silvaron：上面一整片暗林冠（很多层云杉下层枝叠起来）封住天，中间一条发亮的青灰雾带，
雾里一排排细高的树干、越远越淡，雾在地面那一截最浓最亮；下面是暗的地面。
远处的东西往「同一高度的背景色」里褪：林冠里褪成暗色，雾带里褪成雾色。
除了天空，每层宽 960、左右无缝，Godot 里用 Parallax2D 横向重复。
越远的层越偏雾色、色阶越少；越近越暗、杂点越细。光从左上来，亮面偏暖、暗面偏冷。
所有随机都固定 seed，改参数重跑结果不变。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.palette import from_hex, oklab_to_srgb, ramp, to_lab  # noqa: E402

W, H = 960, 270          # 每层的宽高；屏幕 480×270
GROUND = 228             # 主层地面的平均高度
OUT = Path(__file__).resolve().parents[1] / "art" / "forest"

FOG = from_hex("#4e6b5b")     # 雾带最亮的那一档（和 BANDS 里 170 那档一样）
WARM = from_hex("#c9cbb4")    # 这个方向几乎不用暖光；留着给以后的点缀

# 层名 -> 跟镜头的比例。Godot 场景里的 scroll_scale 照这个填
SCROLL = {"sky": 0.0, "ridge": 0.06, "far": 0.18, "midfar": 0.38, "mid": 0.62, "main": 1.0, "front": 1.4}
# 地上被光柱照到的地方（主层坐标）；Godot 里的光柱画在同样的 x
LIT_X = [190, 640]


# ---------------------------------------------------------------- 颜色

def mix(c, d, t):
    """OKLab 里从 c 往 d 走 t。"""
    a, b = to_lab(c), to_lab(d)
    return tuple(int(v) for v in oklab_to_srgb((a + (b - a) * t)[None])[0])


def fogged(r, t):
    return [mix(c, FOG, t) for c in r]


def blocky_noise(h, w, rng, cell=2):
    """一格一格的噪声（0..1），格子 cell×cell，叠一层 1 像素的细噪声。像素画叶子的杂点就是这样。"""
    gh, gw = h // cell + 2, w // cell + 2
    g = rng.random((gh, gw))
    big = np.repeat(np.repeat(g, cell, 0), cell, 1)
    oy, ox = rng.integers(0, cell, 2)
    big = big[oy:oy + h, ox:ox + w]
    return 0.7 * big + 0.3 * rng.random((h, w))


class Layer:
    """一层图：RGBA 数组，贴东西时左右绕回（无缝）。"""

    def __init__(self, w=W, h=H):
        self.a = np.zeros((h, w, 4), np.uint8)

    def paste(self, img, x, y, wrap=True):
        h, w = img.shape[:2]
        H_, W_ = self.a.shape[:2]
        xs = [x - W_, x, x + W_] if wrap else [x]
        for px in xs:
            x0, y0 = max(0, px), max(0, y)
            x1, y1 = min(W_, px + w), min(H_, y + h)
            if x0 >= x1 or y0 >= y1:
                continue
            src = img[y0 - y:y1 - y, x0 - px:x1 - px]
            m = src[..., 3] > 0
            self.a[y0:y1, x0:x1][m] = src[m]

    def save(self, name):
        Image.fromarray(self.a).save(OUT / f"{name}.png")


def paint(idx_map, mask, pal):
    """色阶下标 -> RGBA。"""
    h, w = mask.shape
    out = np.zeros((h, w, 4), np.uint8)
    pal_a = np.array([tuple(c) + (255,) for c in pal], np.uint8)
    idx = np.clip(np.round(idx_map), 0, len(pal) - 1).astype(int)
    out[mask] = pal_a[idx[mask]]
    return out


# ---------------------------------------------------------------- 针叶树

def conifer(height, radius, seed, fol, bark, detail=2, trunk_w=None, crown=0.82, droop=0.5, dead=0,
            grain=1.0, tier_lit=0.0, lean=0, snag=0.0, ragged=0.0, bough=False, hole=0.0):
    """一棵针叶树（云杉 / 冷杉），返回 RGBA，树根在图的底边正中。

    fol / bark   叶子、树皮色阶（暗 -> 亮）
    detail       0 = 远处的剪影（两档、没有杂点），1 = 少量杂点，2 = 近处，杂点 + 层间阴影 + 针叶须
    crown        树冠占树高的比例，下面露出树干
    droop        枝条下垂的程度
    dead         树冠下面伸出的枯枝数
    grain        叶子杂点的强度倍数（暗的近层调小，让一层层的枝看得出来，而不是一片灰点子）
    tier_lit     每层枝条上沿（左半边）受光提亮多少档：林冠里靠它读出「一层层的云杉枝」
    lean         树梢往一边歪多少像素（正 = 往右），根不动
    snag         断顶：从树尖往下砍掉树高的这个比例，留一截劈开的树干
    ragged       枝条长短的随机程度（0 = 规整的圆锥，0.5 = 很参差、有缺枝）
    bough        True = 只要树冠，不画树干（前景从上沿垂下来的枝，树干会在林冠里露成一根细线）
    hole         叶子暗到 tone < -hole 才挖成透明的洞（0 = 原来的蕾丝感；前景剪影给大一点，免得右半边碎成一条条）
    最后只留下连着树根（图的底边）或树尖的像素：挖洞、断顶挖出来的、飘在半空的碎枝都扔掉。
    """
    rng = np.random.default_rng(seed)
    w = 2 * radius + 10
    h = height + 3
    cx = w // 2
    top = 2
    crown_bottom = top + int(height * crown)
    n = len(fol)
    tone = np.full((h, w), -1.0)
    filled = np.zeros((h, w), bool)    # 画到了的格子（tone 可以是负的：很暗）
    tier_id = np.full((h, w), -1)
    noise = blocky_noise(h, w, rng, cell=2 if detail >= 2 else 3)

    # 树干：左边受光
    tw = trunk_w or max(1, radius // 8)
    trunk = np.zeros((h, w), bool)
    trunk_tone = np.zeros((h, w))
    trunk_lr = {}                      # 每行树干的左右边（枯枝从这里长出来）
    nb = len(bark)
    for y in range(top + height // 8, h if not bough else top + height // 8):
        f = (y - top) / max(1, h - top)
        half = max(0.5, tw * (0.35 + 0.65 * f) / 2)
        flare = max(0.0, (y - (h - 6)) / 6) * tw * 0.6 if detail >= 1 else 0
        x0, x1 = int(round(cx - half - flare)), int(round(cx + half + flare))
        trunk_lr[y] = (x0, max(x0 + 1, x1) - 1)
        for x in range(x0, max(x0 + 1, x1)):
            trunk[y, x] = True
            u = (x - x0) / max(1, x1 - x0 - 1) if x1 - x0 > 1 else 0.3
            v = (nb - 1) * (0.75 - 0.75 * u) + (noise[y, x] - 0.5) * (1.2 if detail >= 2 else 0)
            if tw >= 8 and 0 < x - x0 < x1 - x0 - 1:   # 粗树干：竖着的树皮缝，一节一节错开
                k = (x - x0 + int(cx)) // 4
                if (x - x0) % 4 == 0 or (y + k * 13) % 23 == 0:
                    v -= 1.1
            trunk_tone[y, x] = v
    # 枯枝
    for _ in range(dead if h - 6 > crown_bottom else 0):
        y = int(rng.uniform(crown_bottom - 4, h - 6))
        side = rng.choice([-1, 1])
        ln = int(rng.uniform(radius * 0.2, radius * 0.45))
        slope = rng.uniform(0.2, 0.4)
        lft, rgt = trunk_lr.get(y, (cx - tw // 2, cx + tw // 2))
        for i in range(ln):
            x = (rgt + 1 + i) if side > 0 else (lft - 1 - i)   # 贴着这一行树干的边长出去，不留缝
            yy = y + int(i * slope)
            if 0 <= x < w and 0 <= yy < h:
                trunk[yy, x] = True
                trunk_tone[yy, x] = 1.4

    # 一层层枝条，从下往上画：上层的枝条盖在下层前面
    spacing = 9 if detail >= 2 else 8
    nt = int(np.clip((crown_bottom - top) / spacing, 4, 40))
    ys = top + 3 + (crown_bottom - top - 3) * np.linspace(0, 1, nt) ** 1.05
    for k in reversed(range(nt)):
        yk = ys[k] + rng.uniform(-1, 1)
        frac = (yk - top) / max(1, crown_bottom - top)
        rk = radius * (0.12 + 0.88 * frac ** 0.8)
        gap = (ys[k] - ys[k - 1]) if k else spacing
        th = max(3.0, gap * rng.uniform(1.35, 1.7))
        for side in (-1, 1):
            r = max(2.0, rk * rng.uniform(0.72, 1.08))
            if ragged > 0:   # 参差：有的枝短一截，偶尔整枝没了（枯掉、断了）
                r = max(2.0, r * (1 - ragged * rng.random() ** 2))
                if 0 < k < nt - 1 and rng.random() < ragged * 0.35:
                    continue
            dr = droop * th * rng.uniform(0.6, 1.2) + r * 0.08
            y_att = yk - th
            ph, fq = rng.uniform(0, 6.28), rng.uniform(0.35, 0.6)
            for ui in range(int(r) + 1):
                t = ui / r
                yt = y_att + (th + dr) * t ** 1.4
                yb = yk - 0.2 * th + (0.2 * th + dr) * t ** 0.9
                if detail >= 1:   # 下沿一团一团（针叶簇），上沿偶尔缺一格
                    yb += 1.6 * max(0.0, np.sin(ui * fq + ph)) * (1 - t * 0.5)
                    if rng.random() < 0.18:
                        yt += 1
                if detail >= 2 and rng.random() < 0.35:   # 垂下来的针叶须
                    yb += rng.integers(1, 3) if rng.random() < 0.8 else rng.integers(3, 5)
                x = int(round(cx + side * ui))
                if not 0 <= x < w:
                    continue
                y0, y1 = int(round(yt)), int(round(yb))
                for y in range(max(0, y0), min(h, y1 + 1)):
                    rel = (y - yt) / max(1.0, yb - yt)
                    v = (n - 1) * (0.78 - 0.55 * rel)            # 上面亮、下面暗
                    v += -side * 0.9 * t                          # 光从左来：左边枝梢亮，右边暗
                    v -= 0.9 * (1 - t) ** 3                       # 贴着树干的地方最暗
                    v -= 0.7 * frac                               # 下层整体暗一点（被上面挡着）
                    if detail >= 1:
                        v += (noise[y, x] - 0.5) * (2.2 if detail >= 2 else 1.2) * grain
                    tone[y, x] = v
                    filled[y, x] = True
                    tier_id[y, x] = k
            # 枝梢：伸出去的一两个像素
            if detail >= 1:
                tx = int(round(cx + side * (r + 1)))
                ty = int(round(yk + dr))
                if 0 <= tx < w and 0 <= ty < h:
                    tone[ty, tx] = (n - 1) * 0.35 - side * 0.5
                    filled[ty, tx] = True
                    tier_id[ty, tx] = k
    # 树尖
    for y in range(0, top + 4):
        tone[y, cx] = (n - 1) * 0.7
        filled[y, cx] = True
        tier_id[y, cx] = 0

    fol_m = filled & (tone >= -hole)
    if detail >= 2:
        # 上层枝条的下沿在下层上投 2 像素的阴影
        shade = np.zeros_like(tone)
        for d in (1, 2):
            up = np.full_like(tier_id, -1)
            up[d:] = tier_id[:-d]
            shade[(fol_m) & (up >= 0) & (up < tier_id)] -= 1.0 if d == 1 else 0.6
        tone = tone + shade
    if tier_lit:
        # 每层枝条露出来的那截，紧挨着上一层投下的阴影线下面，是一条受光带（左边亮、右边弱），
        # 一条暗线 + 一条亮带，一层一层往下数得清
        run = np.zeros_like(tone)
        for y in range(1, h):
            same = (tier_id[y] == tier_id[y - 1]) & fol_m[y] & fol_m[y - 1]
            run[y] = np.where(same, run[y - 1] + 1, 0)
        band = ((run >= 2) & (run <= 4)).astype(float) + 0.5 * (run == 5)
        xs_ = np.arange(w)[None, :].repeat(h, 0)
        side_l = np.where(xs_ < cx, 1.0, 0.35)
        tone = np.where(fol_m, tone + tier_lit * band * side_l, tone)
    # 受光的上沿加一档
    above = np.zeros_like(fol_m)
    above[1:] = fol_m[:-1]
    xs = np.arange(w)[None, :].repeat(h, 0)
    rim = fol_m & ~above & (xs <= cx + radius * 0.2)
    tone[rim] += 1.0 if detail >= 1 else 0.8

    if detail == 0:   # 远景只要两档：受光边 + 身体
        tone = np.where(tone > (n - 1) * 0.62, n - 1, 0).astype(float)
        top_cap = n - 1
    else:
        top_cap = n - 2 if detail >= 2 else n - 1   # 最亮一档留给少数高光
    img = paint(np.clip(trunk_tone, 0, nb - 1), trunk & ~fol_m, bark)
    fol_img = paint(np.clip(tone, 0, top_cap), fol_m, fol)
    m = fol_img[..., 3] > 0
    img[m] = fol_img[m]
    if detail >= 2:   # 左上受光的枝梢，几颗最亮的点
        cand = np.argwhere(rim & (xs < cx - 2))
        for y, x in cand[rng.random(len(cand)) < 0.18]:
            img[y, x] = tuple(fol[-1]) + (255,)
    if snag > 0:   # 断顶：上面一截砍掉，留一根劈开的树干尖
        cut = int(top + height * snag)
        img[:cut] = 0
        tw_ = max(1, int(trunk_w or max(1, radius // 8)))
        for y in range(max(0, cut - int(rng.integers(3, 8))), cut + 1):
            for dx in range(-(tw_ // 2), tw_ - tw_ // 2):
                if (y < cut - 2 and dx != 0):
                    continue
                img[y, cx + dx] = tuple(bark[min(len(bark) - 1, 1 if dx <= 0 else 0)]) + (255,)
    if lean:   # 歪：越往上错得越多，根不动
        pad = abs(int(lean)) + 1
        out = np.zeros((h, w + 2 * pad, 4), np.uint8)
        for y in range(h):
            dx = int(round(lean * (1 - y / (h - 1)) ** 1.3))
            out[y, pad + dx:pad + dx + w] = img[y]
        img = out
    return keep_attached(img, top + 4)   # 歪的时候一行行错开，也可能把一根细枝梢错断


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


def keep_attached(img, tip_rows):
    """一棵树的图里，只留连着树根（底边）或树尖（最上面 tip_rows 行）的部分。
    叶子挖洞、断顶、歪都可能把一截枝条切下来，留着就是一块悬在半空的碎叶。"""
    m = img[..., 3] > 0
    lab, n = components(m)
    if n <= 1:
        return img
    anchor = np.r_[lab[-1], lab[:tip_rows].ravel()]
    keep = set(anchor[anchor > 0].tolist())
    if not keep:
        return img
    img = img.copy()
    img[~np.isin(lab, list(keep)) & m] = 0
    return img


# ---------------------------------------------------------------- 地面上的东西

def fern(size, seed, pal):
    """一丛蕨：几片从根部弯出去的叶子，小叶左右交替。"""
    rng = np.random.default_rng(seed)
    w, h = size * 3 + 8, size + 6
    img = np.zeros((h, w, 4), np.uint8)
    cx, base = w // 2, h - 1
    n = len(pal)
    fronds = int(rng.integers(6, 9))
    order = sorted(range(fronds), key=lambda i: abs(i - (fronds - 1) / 2), reverse=True)  # 中间的叶子在前
    for i in order:
        ang = np.radians(np.interp(i, [0, fronds - 1], [165, 15]) + rng.uniform(-7, 7))
        ln = size * rng.uniform(0.75, 1.1) * (1.15 if 0 < i < fronds - 1 else 0.85)
        lit = 1 if np.cos(ang) < 0 else 0          # 朝左的叶子受光
        steps = int(ln * 1.4)
        px, py = float(cx), float(base)
        dx, dy = np.cos(ang), -np.sin(ang)
        for s in range(steps):
            t = s / steps
            dy += 0.09 * (1 + t)                   # 越往外越往下垂
            m = np.hypot(dx, dy)
            dx, dy = dx / m, dy / m
            px, py = px + dx * 0.75, py + dy * 0.75
            xi, yi = int(round(px)), int(round(py))
            if not (0 <= xi < w and 0 <= yi < h):
                continue
            img[yi, xi] = tuple(pal[min(n - 1, 1 + lit + int((1 - t) * 1.5))]) + (255,)
            if s % 2 or t < 0.08:
                continue
            ll = (1 - t) ** 0.7 * size * 0.2 + 1   # 小叶：向前斜着长，上面一侧亮
            for side in (-1, 1):
                nx, ny = -dy * side, dx * side
                lx, ly = nx * 0.8 + dx * 0.5, ny * 0.8 + dy * 0.5 + 0.25
                upper = ly < 0
                c = pal[int(np.clip(lit + (2 if upper else 1) + (1 - t) * 1.2, 0, n - 1))]
                for k in range(1, int(ll) + 1):
                    xx, yy = int(round(px + lx * k)), int(round(py + ly * k))
                    if 0 <= xx < w and 0 <= yy < h:
                        img[yy, xx] = tuple(c) + (255,)
    return img


def log(length, thick, seed, bark, wood, moss):
    """倒下的树干：横着的圆柱，顶上受光，左端是切面年轮，背上长苔藓。"""
    rng = np.random.default_rng(seed)
    w, h = length + 4, thick + 4
    img = np.zeros((h, w, 4), np.uint8)
    noise = blocky_noise(h, w, rng, 2)
    nb = len(bark)
    for x in range(thick // 2, length):
        sag = int(round(1.2 * np.sin(np.pi * x / length)))
        for y in range(thick):
            u = y / (thick - 1)
            v = (nb - 1) * (0.95 - 0.9 * u) + (noise[y, x] - 0.5) * 1.2
            if x % int(rng.integers(5, 9) if x == thick // 2 else 7) == 0 and 0.2 < u < 0.8:
                v -= 0.8   # 树皮裂纹
            img[y + 2 + sag, x + 2] = tuple(bark[int(np.clip(round(v), 0, nb - 1))]) + (255,)
        if rng.random() < 0.55:   # 苔藓
            for d in range(int(rng.integers(1, 3))):
                c = moss[min(len(moss) - 1, 2 + d)] if rng.random() < 0.7 else moss[1]
                img[1 + sag - d + 1, x + 2] = tuple(c) + (255,)
    # 切面
    r = thick / 2
    ccx, ccy = thick // 2 + 2, h // 2
    nw = len(wood)
    for y in range(h):
        for x in range(0, thick + 2):
            dx, dy = (x - ccx) / (r * 0.55), (y - ccy) / r
            d = np.hypot(dx, dy)
            if d <= 1:
                ring = int(d * 4.5) % 2
                v = (nw - 1) * (0.8 - 0.4 * d) - ring * 0.8 - (0.6 if dx > 0.3 else 0)
                img[y, x] = tuple(wood[int(np.clip(round(v), 0, nw - 1))]) + (255,)
    return img


def stump(wd, ht, seed, bark, wood):
    rng = np.random.default_rng(seed)
    w, h = wd + 8, ht + 5
    img = np.zeros((h, w, 4), np.uint8)
    noise = blocky_noise(h, w, rng, 2)
    nb, nw = len(bark), len(wood)
    x0 = 4
    for y in range(3, h):
        flare = int(max(0, y - (h - 4)) * 1.3)
        for x in range(x0 - flare, x0 + wd + flare):
            u = (x - x0 + flare) / max(1, wd + 2 * flare - 1)
            v = (nb - 1) * (0.85 - 0.8 * u) + (noise[y, x] - 0.5) * 1.3
            if (x - x0) % 4 == 1 and y > 4:
                v -= 0.7
            img[y, x] = tuple(bark[int(np.clip(round(v), 0, nb - 1))]) + (255,)
    for x in range(x0, x0 + wd):   # 切口：一条椭圆面，左边受光
        for y in range(0, 5):
            dx, dy = (x - (x0 + wd / 2 - 0.5)) / (wd / 2), (y - 2.5) / 2.5
            if dx * dx + dy * dy <= 1:
                ring = int(np.hypot(dx, dy) * 3) % 2
                v = (nw - 1) * (0.9 - 0.35 * (dx + 1)) - ring * 0.7
                img[y, x] = tuple(wood[int(np.clip(round(v), 0, nw - 1))]) + (255,)
    tip = x0 + wd - 3   # 断口翘起的一根
    for y in range(-3, 1):
        if 0 <= y + 3 < h:
            img[y + 3, tip] = tuple(bark[1]) + (255,)
    return img


def rock(wd, ht, seed, stone, moss):
    rng = np.random.default_rng(seed)
    w, h = wd + 2, ht + 2
    img = np.zeros((h, w, 4), np.uint8)
    noise = blocky_noise(h, w, rng, 2)
    ns = len(stone)
    for y in range(h):
        for x in range(w):
            dx, dy = (x - w / 2) / (wd / 2), (y - h) / ht
            if dx * dx + dy * dy <= 1 + (noise[y, x] - 0.5) * 0.25:
                v = (ns - 1) * (0.75 - 0.45 * (y / h) - 0.3 * dx) + (noise[y, x] - 0.5) * 1.4
                img[y, x] = tuple(stone[int(np.clip(round(v), 0, ns - 1))]) + (255,)
    m = img[..., 3] > 0
    above = np.zeros_like(m)
    above[1:] = m[:-1]
    for y, x in np.argwhere(m & ~above):   # 顶上一层苔藓，往下垂一两格
        for d in range(int(rng.integers(1, 4))):
            if y + d < h and m[y + d, x]:
                img[y + d, x] = tuple(moss[min(len(moss) - 1, 3 - d)]) + (255,)
    return img


def mushrooms(seed, cap, stem):
    rng = np.random.default_rng(seed)
    img = np.zeros((9, 12, 4), np.uint8)
    for i in range(int(rng.integers(2, 4))):
        x = int(rng.integers(1, 9))
        hh = int(rng.integers(2, 5))
        for y in range(8 - hh, 9):
            img[y, x + 1] = tuple(stem[1]) + (255,)
        cy = 8 - hh
        for dx in (-1, 0, 1, 2):
            if 0 <= x + dx < 12:
                img[cy, x + dx] = tuple(cap[1 if dx > 0 else 2]) + (255,)
        img[cy - 1, x] = tuple(cap[2]) + (255,)
        img[cy - 1, x + 1] = tuple(cap[1]) + (255,)
    return img


# ---------------------------------------------------------------- 各层

def ground_y(x):
    """主层地面高度，左右无缝（整数周期）。"""
    return GROUND + 2.0 * np.sin(2 * np.pi * x * 2 / W) + 1.5 * np.sin(2 * np.pi * x * 5 / W + 1.0)


def fog_band(layer, y0, y1, steps, color, seed):
    """一条雾带：往下越来越密的有序抖动（Bayer），像素都是不透明的。y1 以下整片雾色。"""
    bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16
    hh, ww = layer.a.shape[:2]
    col = np.array(tuple(color) + (255,), np.uint8)
    for y in range(y0, hh):
        t = 1.0 if y >= y1 else (y - y0) / max(1, y1 - y0)
        t = np.floor(t * steps) / steps
        row = bayer[y % 4, np.arange(ww) % 4] < t
        layer.a[y, row] = col


def tint_rows(layer, y0, y1, target, amount):
    """把 y0 以下的像素一档一档往雾色推（越往下越淡），模拟雾里的树根。"""
    cache = {}
    for y in range(y0, min(y1, layer.a.shape[0])):
        t = np.floor((y - y0) / max(1, y1 - y0) * 4) / 4 * amount
        if t <= 0:
            continue
        m = layer.a[y, :, 3] > 0
        for x in np.nonzero(m)[0]:
            key = (tuple(layer.a[y, x, :3]), t)
            if key not in cache:
                cache[key] = mix(key[0], target, t)
            layer.a[y, x, :3] = cache[key]


# ---------------------------------------------------------------- 背景色（随高度）

# 从上往下：林冠里几乎是黑的墨绿，往下进一条青绿灰的雾带（170 附近最亮），
# 再往下又暗回去：地面上方 25 像素（主角背后）是暗而干净的林下，给很亮的主角让出对比。
# (这一档开始的 y, 颜色)。sky 层就是这几档；远处的东西也往「同一高度的这一档」里褪。
BANDS = [
    (0, "#050c0a"), (50, "#07100d"), (76, "#0a1511"), (92, "#0f1c17"), (104, "#16261f"),
    (114, "#1f3229"), (124, "#2b4135"), (134, "#385142"), (146, "#44604f"), (158, "#517060"),
    (170, "#5b7b67"), (182, "#4e6b5a"), (190, "#3e5748"), (197, "#2d4136"), (204, "#203027"),
    (212, "#18241e"),
]
BAND_Y = np.array([b[0] for b in BANDS])
BAND_C = [from_hex(b[1]) for b in BANDS]


def band_of(y):
    return int(np.searchsorted(BAND_Y, y, side="right") - 1)


_MIX = {}
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16


def band_frac(y):
    """y 在这一档里走了多少（0..1），用来往下一档抖动过渡。"""
    i = band_of(y)
    if i + 1 >= len(BANDS):
        return i, 0.0
    return i, (y - BAND_Y[i]) / (BAND_Y[i + 1] - BAND_Y[i])


def aerial(layer, t_of_y, steps=8, pool=None):
    """把每个像素往同一高度的背景色里推 t(y)。像素仍然全不透明。

    t 只取 1/steps 的整数倍（色数不会爆），但相邻两档之间、背景色相邻两档之间都用 Bayer 有序抖动过渡，
    不再一行一刀切：以前树干上那一截一截的横向台阶就是这么来的。
    pool = (shift, gain)：这层在光斑里往更亮的雾色褪（光斑位置按屏幕坐标 + shift 换到这层的坐标）。"""
    a = layer.a
    ww = a.shape[1]
    xs = np.arange(ww)
    for y in range(a.shape[0]):
        tc = min(1.0, max(0.0, t_of_y(y)))
        lo = np.floor(tc * steps + 1e-6)
        fr = tc * steps - lo
        if fr < 0.2:          # 整层统一的基础值不抖（免得整片树都是棋盘格）
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
        if pool:
            lv = np.maximum(pool_level((xs - pool[0]) % 480, y), 0) * 3
            p_lo = np.floor(lv)
            p_px = p_lo + (BAYER[(y + 1) % 4, (xs + 3) % 4] < lv - p_lo)
        else:
            p_px = np.zeros(ww)
        keys = np.stack([t_px * steps, b_px, p_px], 1)
        out = a[y, :, :3].copy()
        for tt, bb, pp in np.unique(keys[m], axis=0):
            sel = m & (keys[:, 0] == tt) & (keys[:, 1] == bb) & (keys[:, 2] == pp)
            t = tt / steps
            if t <= 0:
                continue
            tgt = pool_color(int(bb), int(pp) * (pool[1] if pool else 0))
            cols, inv = np.unique(a[y, sel, :3], axis=0, return_inverse=True)
            new = []
            for c in cols:
                key = (tuple(int(v) for v in c), tgt, t)
                if key not in _MIX:
                    _MIX[key] = mix(key[0], tgt, min(1.0, t))
                new.append(_MIX[key])
            out[sel] = np.array(new, np.uint8)[inv.ravel()]
        a[y, :, :3] = out


def ramp_t(base, ground_extra=0.0, y0=188, y1=226, canopy_extra=0.0, cy=104):
    """t(y)：整层一个基础值；地面附近（y0..y1）雾更浓；林冠里（cy 以上）再多褪一点。"""
    def f(y):
        t = base
        if y > y0:
            t += ground_extra * min(1.0, (y - y0) / max(1, y1 - y0))
        if y < cy:
            t += canopy_extra
        return min(1.0, t)
    return f


# 雾里的光斑（屏幕坐标；sky 不随镜头动，所以光斑总在画面里同样的位置）：(x 中心, 半宽, 强度)。
# 位置和 Godot 的光柱对上：镜头在 0 时 Shaft0 落在 x≈190，镜头在 240 / 520 时 Shaft1 落在 x≈400 / 120，
# 所以三张截图里光柱底下都正好有一团更亮、更透的雾。
POOLS = ((150, 46, 1.0), (378, 40, 0.85), (262, 26, 0.35))
POOL_Y = (118, 172, 198)          # 光斑从 118 开始亮起，172 最亮，198 收掉（主角背后那条不碰）
POOL_C = from_hex("#86a78e")      # 光斑最亮处往这个色推（青绿，明显低于近白）
POOL_STEP = 0.22                  # 每档往 POOL_C 走多少


def pool_level(x, y):
    """光斑强度 0..1（x 可以是数组）。"""
    y0, yc, y1 = POOL_Y
    if y <= y0 or y >= y1:
        return np.zeros_like(np.asarray(x, float))
    vy = (y - y0) / (yc - y0) if y < yc else (y1 - y) / (y1 - yc)
    vy = vy ** 1.2
    v = np.zeros_like(np.asarray(x, float))
    for cx, hw, k in POOLS:
        d = np.abs(np.asarray(x, float) - cx) / hw
        v = np.maximum(v, k * np.clip(1 - d * d, 0, 1) ** 1.5 * vy)
    return v


_POOLC = {}


def pool_color(band, level):
    """第 band 档背景色在光斑里提亮 level 档（0..3，可以是小数）。"""
    key = (band, round(level, 3))
    if key not in _POOLC:
        _POOLC[key] = mix(BAND_C[band], POOL_C, POOL_STEP * level) if level else BAND_C[band]
    return _POOLC[key]


def sky():
    """背景：BANDS 那几档，两档之间整段用 4×4 Bayer 有序抖动连续过渡，没有硬台阶。
    没有太阳，光只在雾里：几团光斑（POOLS）把雾带局部提亮 1~3 档，让静态截图也有焦点。"""
    lay = Layer(480, 270)
    xs = np.arange(480)
    pool_cache = {}
    for y in range(270):
        i, f = band_frac(y)
        idx = i + (BAYER[y % 4, xs % 4] < f)
        lv = pool_level(xs, y) * 3
        lo = np.floor(lv)
        lvl = (lo + (BAYER[(y + 1) % 4, (xs + 3) % 4] < (lv - lo))).astype(int)
        for x in range(480):
            key = (int(idx[x]), int(lvl[x]))
            if key not in pool_cache:
                base = BAND_C[key[0]]
                pool_cache[key] = pool_color(*key)
            lay.a[y, x] = tuple(pool_cache[key]) + (255,)
    return lay


# ---------------------------------------------------------------- 林冠下的树

def hanging(lay, x, base_y, cb_y, radius, seed, fol, bark, detail, trunk_w, droop=0.6, dead=0, extra=None, **kw):
    """一棵树冠伸出画面上沿的云杉：只看得到最下面几层下垂的枝（cb_y 是树冠下沿），下面是一根细高的树干。"""
    rng = np.random.default_rng(seed + 7)
    height = int(base_y + (extra if extra is not None else rng.uniform(60, 140)))
    crown = (cb_y - base_y + height + 1) / height
    img = conifer(height, radius, seed, fol, bark, detail=detail, trunk_w=trunk_w,
                  crown=float(np.clip(crown, 0.2, 0.97)), droop=droop, dead=dead, **kw)
    lay.paste(img, int(x) - img.shape[1] // 2, base_y - img.shape[0])


def bare_trunk(lay, x, w, y1, bark, seed):
    """只露树干的远树（树冠在林冠里看不见）：左边一列亮一档，偶尔一截枯枝桩。"""
    rng = np.random.default_rng(seed)
    nb = len(bark)
    for y in range(0, y1):
        for i in range(w):
            v = (nb - 1) * (0.55 if i == 0 and w > 1 else 0.2)
            lay.a[y, (x + i) % W] = tuple(bark[int(round(v))]) + (255,)
    for _ in range(int(rng.integers(0, 3))):
        y = int(rng.uniform(100, y1 - 30))
        side = rng.choice([-1, 1])
        for i in range(int(rng.integers(2, 6))):
            xx = (x + (w + i if side > 0 else -1 - i)) % W
            lay.a[y + i // 2, xx] = tuple(bark[0]) + (255,)


def forest_row(count, n_bare, base_y, cb_range, r_range, tw_range, seed, fol, bark, detail,
               small=None, droop=(0.5, 0.75), dead=0, **kw):
    """一整层：一排树冠伸出画面的云杉（冠底高低错开、宽冠互相叠住），中间夹着只露干的树，
    根部前面是一排雾里的小云杉（small = (棵数, 高度范围, 色阶)）。"""
    lay = Layer()
    rng = np.random.default_rng(seed)
    for i in range(n_bare):
        x = int(rng.uniform(0, W))
        bare_trunk(lay, x, int(rng.integers(tw_range[0], tw_range[1] + 1)), base_y, bark, seed * 31 + i)
    xs = (np.arange(count) + rng.uniform(-0.35, 0.35, count)) * W / count
    cbs = rng.uniform(*cb_range, count)
    for i in sorted(range(count), key=lambda i: cbs[i]):   # 冠底高的（远一点）先画
        hanging(lay, xs[i], base_y + int(rng.uniform(-2, 3)), int(cbs[i]), int(rng.uniform(*r_range)),
                seed * 100 + i, fol, bark, detail, int(rng.integers(tw_range[0], tw_range[1] + 1)),
                droop=rng.uniform(*droop), dead=dead, **kw)
    if small:
        small_trees(lay, small, base_y, seed, bark, detail)
    return lay


def ground_detail(lay, soil, litter, bark):
    """地面下面那一大片黑土里，很暗的纹理：埋着的树根、半露的石头、落叶和针叶的轮廓。
    只比土亮半档到一档，越往下越少、越暗，不抢亮度。"""
    rng = np.random.default_rng(77)
    hi = mix(soil[-1], from_hex("#2c3d32"), 0.4)    # 受光的上沿
    mid = soil[-1]
    lo_ = soil[0]                                   # 底下的阴影
    leaf = mix(litter[1], soil[-1], 0.5)

    def put(x, y, c):
        if 0 <= y < H:
            gy = int(round(ground_y(x % W)))
            if y >= gy + 4:
                lay.a[y, x % W] = tuple(c) + (255,)

    def depth_ok(x, y):
        return y - int(round(ground_y(x % W)))

    # 树根：从大树底下钻进土里，一条条往两边拐弯、变细
    for x0 in (120, 470, 790, 300, 630, 905):
        for side in (-1, 1):
            for k in range(int(rng.integers(1, 3))):
                px, py = float(x0 + side * rng.uniform(2, 8)), float(ground_y(x0) + 4 + k * 3)
                ang = rng.uniform(0.15, 0.6)
                ln = int(rng.uniform(22, 60))
                th = 2 if k == 0 else 1
                for i in range(ln):
                    ang += rng.normal(0, 0.12)
                    ang = float(np.clip(ang, -0.1, 0.9))
                    px += side * np.cos(ang)
                    py += np.sin(ang) * 0.6
                    xi, yi = int(round(px)), int(round(py))
                    t = i / ln
                    thick = th if t < 0.6 else 1
                    put(xi, yi, hi if depth_ok(xi, yi) < 18 else mid)
                    for d in range(1, thick + 1):
                        put(xi, yi + d, lo_ if d == thick else mid)
    # 半埋的石头：扁的圆顶，上沿一条亮一档，下面压一条暗缝
    for _ in range(26):
        x = int(rng.uniform(0, W))
        d = int(6 + 30 * rng.random() ** 1.5)
        y = int(round(ground_y(x))) + d
        wd = int(rng.uniform(4, 11 if d < 18 else 8))
        ht = max(2, int(wd * rng.uniform(0.3, 0.5)))
        for i in range(wd):
            u = (i - wd / 2 + 0.5) / (wd / 2)
            top = int(round(ht * (1 - u * u) ** 0.5))
            for j in range(top):
                put(x + i, y - j, mid if j < top - 1 else (hi if u < 0.3 else mid))
            put(x + i, y + 1, lo_)
    # 落叶、针叶：一两个像素的短斜线，越往下越少
    for _ in range(420):
        x = int(rng.uniform(0, W))
        d = int(5 + 34 * rng.random() ** 2.2)
        y = int(round(ground_y(x))) + d
        c = leaf if d < 16 else mid
        dx, dy = (1, 0) if rng.random() < 0.6 else (1, 1 if rng.random() < 0.5 else -1)
        for k in range(int(rng.integers(1, 4))):
            put(x + dx * k, y + dy * k, c)


def small_trees(lay, small, base_y, seed, bark, detail):
    """雾里的小云杉：成丛地长（不是匀匀地一排），高矮差很多；有的歪、有的断顶、有的枝条稀稀拉拉，
    还夹着几棵只剩枝桩的枯树。"""
    n, hr, sfol = small
    rng = np.random.default_rng(seed * 7 + 1)
    n_cl = max(2, n // 4)
    centers = rng.uniform(0, W, n_cl)
    sx = (centers[rng.integers(0, n_cl, n)] + rng.normal(0, W / n_cl * 0.45, n)) % W
    hs = hr[0] + (hr[1] - hr[0]) * rng.random(n) ** 0.9 * rng.uniform(0.8, 1.3, n)   # 高矮差很多，少数特别高
    hs = np.clip(hs, hr[0] * 0.6, hr[1] * 1.15)
    d = 0 if detail == 0 else 1
    for i in sorted(range(n), key=lambda i: -hs[i]):
        hh = int(hs[i])
        kind = rng.random()
        lean = int(round(rng.normal(0, hh * 0.05))) if rng.random() < 0.45 else 0
        if kind < 0.13:     # 枯树：只剩树干和往下耷拉的枝桩
            img = dead_spruce(hh, seed * 300 + i, sfol, lean=lean)
        else:
            snag = rng.uniform(0.18, 0.45) if kind < 0.25 else 0.0
            sparse = rng.random() < 0.25          # 四棵里一棵枝条稀稀拉拉（半枯），其余是完整的
            img = conifer(hh, int(hh * rng.uniform(0.2, 0.32)), seed * 300 + i, sfol, bark, detail=d,
                          crown=rng.uniform(0.75, 0.95), droop=rng.uniform(0.35, 0.65),
                          ragged=rng.uniform(0.35, 0.6) if sparse else rng.uniform(0.0, 0.2), lean=lean, snag=snag,
                          trunk_w=1 if hh < 50 else 2)
        lay.paste(img, int(sx[i]) - img.shape[1] // 2, base_y + 2 + int(rng.uniform(-2, 3)) - img.shape[0])


def dead_spruce(height, seed, pal, lean=0):
    """枯云杉：一根细树干，两边一节一节往下耷拉的短枝桩（越往上越短），顶上断掉一截。用叶子色阶的暗档。"""
    rng = np.random.default_rng(seed)
    w = int(height * 0.5) + 6
    h = height + 2
    img = np.zeros((h, w, 4), np.uint8)
    cx = w // 2
    top = int(height * rng.uniform(0.0, 0.25)) + 2
    n = len(pal)
    body, lit = tuple(pal[0]) + (255,), tuple(pal[min(n - 1, 1)]) + (255,)
    tw = 1 if height < 50 else 2
    for y in range(top, h):
        for dx in range(tw):
            img[y, cx + dx] = lit if dx == 0 else body
    y = top + int(rng.integers(1, 4))
    while y < h - height * 0.25:
        f = (y - top) / max(1, h - top)
        for side in (-1, 1):
            if rng.random() < 0.25:
                continue
            ln = int(max(1, height * 0.22 * (0.3 + f) * rng.uniform(0.5, 1.1)))
            sl = rng.uniform(0.3, 0.9)
            for k in range(1, ln + 1):
                xx = cx + (tw if side > 0 else -1) + side * (k - 1)
                yy = y + int(k * sl)
                if 0 <= xx < w and 0 <= yy < h:
                    img[yy, xx] = body
        y += int(rng.integers(3, 6))
    if lean:
        pad = abs(int(lean)) + 1
        out = np.zeros((h, w + 2 * pad, 4), np.uint8)
        for yy in range(h):
            dx = int(round(lean * (1 - yy / (h - 1)) ** 1.3))
            out[yy, pad + dx:pad + dx + w] = img[yy]
        img = out
    return keep_attached(img, 0)


def fol_ramp(hexc, n, span):
    return ramp(from_hex(hexc), n=n, L_span=span, hue_shift=10)


def ridge():
    """最远一层：密密的细树干墙，几乎是雾色；脚下一排小云杉剪影，尖顶戳进雾带。"""
    bark = fol_ramp("#2a3d34", 3, 0.06)
    lay = forest_row(60, 70, 214, (80, 112), (16, 26), (1, 2), 11, fol_ramp("#0c1613", 3, 0.04), bark, 0,
                     small=(70, (16, 40), fol_ramp("#24352e", 2, 0.05)))
    aerial(lay, ramp_t(0.66, 0.34, 182, 212, 0.3), pool=(16, 0.8))   # 0.06 的视差几乎不动，光斑跟着 sky 对得上
    return lay


def build_far():
    bark = fol_ramp("#22302a", 3, 0.07)
    lay = forest_row(46, 34, 216, (84, 122), (20, 32), (2, 3), 21, fol_ramp("#0b1512", 3, 0.05), bark, 0,
                     small=(46, (24, 56), fol_ramp("#1c2a24", 3, 0.06)))
    aerial(lay, ramp_t(0.46, 0.4, 184, 214, 0.3), pool=(43, 0.55))   # 按镜头在 240 附近对齐
    return lay


def build_midfar():
    bark = fol_ramp("#1c2621", 4, 0.08)
    lay = forest_row(28, 16, 220, (66, 118), (28, 44), (3, 5), 31, fol_ramp("#0b1512", 4, 0.07), bark, 1,
                     small=(16, (40, 80), fol_ramp("#15221d", 4, 0.07)), dead=1)
    aerial(lay, ramp_t(0.28, 0.5, 186, 216, 0.25))
    return lay


def build_mid():
    bark = fol_ramp("#161e1a", 4, 0.08)
    lay = forest_row(15, 5, 228, (40, 100), (44, 64), (6, 9), 41, fol_ramp("#0c1712", 5, 0.15), bark, 2,
                     small=(5, (60, 100), fol_ramp("#101b17", 4, 0.07)), dead=2, droop=(0.6, 0.85),
                     grain=0.45, tier_lit=1.2)
    aerial(lay, ramp_t(0.1, 0.5, 190, 222, 0.25))
    return lay


def main_layer():
    """能走的那一层：很暗的地面（上沿一条苔藓线就是能走的边），林下的东西全压暗、少杂点；
    几棵大树的下层枝从上面垂下来，把林冠封住，树干在雾带里是黑的剪影。"""
    lay = Layer()
    rng = np.random.default_rng(5)
    # 林冠：身体还是近黑，但色阶往上拉宽，每层枝的受光带亮一档，读得出一层层的云杉枝
    fol = fol_ramp("#0f1a15", 6, 0.2)
    bark = ramp(from_hex("#171d19"), n=5, L_span=0.11, hue_shift=8)
    wood = ramp(from_hex("#3e3d34"), n=4, L_span=0.12, hue_shift=8)
    moss = ramp(from_hex("#2f4335"), n=5, L_span=0.2, hue_shift=12)
    soil = ramp(from_hex("#111813"), n=4, L_span=0.07, hue_shift=6)
    fernp = ramp(from_hex("#1b2c24"), n=5, L_span=0.13, hue_shift=12)
    stone = ramp(from_hex("#2c322e"), n=4, L_span=0.12, hue_shift=8)
    cap = ramp(from_hex("#3c362e"), n=4, L_span=0.12, hue_shift=8)
    stem = ramp(from_hex("#4b4b42"), n=3, L_span=0.1, hue_shift=6)

    # 大树：树冠在画面外，下层枝垂到 50~75；再加几棵细一点的，把林冠缝补上
    big = ((120, 16, 58, 64), (470, 20, 52, 70), (790, 14, 62, 60))
    thin = ((300, 8, 40, 46), (630, 9, 46, 50), (905, 7, 36, 44))
    for i, (x, tw, cb, r) in enumerate(big + thin):
        gy = int(round(ground_y(x))) + 3
        hanging(lay, x, gy, cb, r, 900 + i, fol, bark, 2, tw, droop=0.75, dead=3 if tw > 10 else 1, extra=120,
                grain=0.45, tier_lit=1.5)

    # 大树的根
    for x, tw in ((120, 16), (470, 20), (790, 14)):
        gy = int(round(ground_y(x)))
        for side in (-1, 1):
            for k in range(int(rng.integers(1, 3))):
                ln = int(rng.uniform(8, 18))
                x0 = x + side * (tw // 2 - 2 - k * 3)
                for i in range(ln):
                    xx = (x0 + side * i) % W
                    hh = max(1, int(round(3.5 * (1 - i / ln))) - k)
                    for d in range(hh):
                        v = len(bark) - 2 - d - (0 if side < 0 else 1)
                        lay.a[gy - d + int(i > ln * 0.6), xx] = tuple(bark[int(np.clip(v, 0, len(bark) - 1))]) + (255,)

    # 地面：上沿 2 像素苔藓（能走的那条线，比背后亮一点），下面很快沉进黑土
    litter = ramp(from_hex("#211f1b"), n=4, L_span=0.08, hue_shift=8)
    noise = blocky_noise(H, W, rng, 2)
    noise_w = blocky_noise(H, W, rng, 3)
    for x in range(W):
        gy = int(round(ground_y(x)))
        lit = any(abs(((x - lx + W / 2) % W) - W / 2) < 26 for lx in LIT_X)
        for y in range(gy, H):
            d = y - gy
            n_ = noise[y, x] - 0.5
            if d < 2 or (d < 3 and noise_w[y, x] > 0.6):
                v = len(moss) - 2 - d + (1 if lit and d == 0 else 0) + n_ * 0.8
                c = moss[int(np.clip(round(v), 0, len(moss) - 1))]
            elif d < 7 and noise_w[y, x] + (7 - d) * 0.06 > 0.62:
                v = (len(litter) - 1) * 0.5 + n_ * 1.2 + (0.6 if lit else 0)
                c = litter[int(np.clip(round(v), 0, len(litter) - 1))]
            else:
                f = min(1.0, (d - 3) / 20)
                v = (len(soil) - 1) * (0.7 - 0.9 * f) + n_ * 0.9
                c = soil[int(np.clip(round(v), 0, len(soil) - 1))]
            lay.a[y, x] = tuple(c) + (255,)
        if rng.random() < 0.3:   # 草尖：只用苔藓的暗档
            for d in range(1, int(rng.integers(2, 4))):
                lay.a[gy - d, x] = tuple(moss[1 + (1 if lit else 0)]) + (255,)
    ground_detail(lay, soil, litter, bark)

    def on_ground(img, x, sink=1):
        lay.paste(img, x - img.shape[1] // 2, int(round(ground_y(x))) + sink - img.shape[0])

    # 林下的小云杉（暗剪影，几乎没有杂点）
    young = fol_ramp("#16261f", 4, 0.1)
    for x, hh, sd in ((30, 34, 1), (395, 40, 3), (700, 36, 5), (560, 22, 4)):
        on_ground(conifer(hh, int(hh * 0.4), 700 + sd, young, bark, detail=1, crown=0.92, droop=0.4), x, 2)

    on_ground(log(78, 12, 7, bark, wood, moss), 300, 2)
    on_ground(stump(15, 13, 8, bark, wood), 600, 2)
    for x, (wd, ht), sd in ((70, (16, 8), 1), (360, (10, 5), 2), (880, (12, 6), 4)):
        on_ground(rock(wd, ht, sd, stone, moss), x, 2)
    for x, sz, sd in ((52, 18, 1), (160, 14, 2), (420, 18, 4), (655, 20, 6), (850, 22, 8), (940, 14, 9)):
        on_ground(fern(sz, sd, fernp), x, 2)
    for x, sd in ((345, 1), (760, 3)):
        on_ground(mushrooms(sd, cap, stem), x, 1)
    aerial(lay, ramp_t(0.0, 0.0, canopy_extra=0.25, cy=70))   # 最上面那截林冠再沉一点
    return lay


def front_trunk(lay, x0, tw, bark_d, noise, plates, stubs=()):
    """前景的一根近黑树干，从上沿通到底边：左边一条冷的受光边，竖着的树皮缝，稍微左右晃。
    stubs = ((y, 长度), ...)：右边伸出去的枯枝桩，贴着这一行树干的右边。"""
    for y in range(H):
        wob = int(round(1.2 * np.sin(y / 23)))
        for x in range(x0 + wob, x0 + wob + tw):
            u = (x - x0 - wob) / tw
            v = 2.0 * (1 - u) ** 1.6 - 0.3 + (noise[y, x % W] - 0.5) * 0.7
            col = (x - x0 - wob) // 5
            if (x - x0 - wob) % 5 == 0 or ((y + col * 17) % 29 == 0):
                v -= 1.0
            v += (plates[(y // 6) % H, x % W] - 0.5) * 0.5
            lay.a[y, x % W] = tuple(bark_d[int(np.clip(round(v), 0, 3))]) + (255,)
        lay.a[y, (x0 + wob) % W] = tuple(bark_d[4] if (y // 3) % 4 else bark_d[3]) + (255,)   # 受光边
    for y, ln in stubs:
        for i in range(ln):
            for d in range(2):
                yy = y + i // 3 + d
                wob = int(round(1.2 * np.sin(yy / 23)))
                lay.a[yy, (x0 + wob + tw + i) % W] = tuple(bark_d[1 + (d == 0)]) + (255,)


def front_layer():
    """前景：近黑的大树干 + 从上沿垂下来的一圈云杉枝（把画面包住）+ 底边的蕨剪影。
    垂枝比林冠更黑、几乎不带杂点，下沿是一簇簇针叶的锯齿：靠「比后面的林冠暗」读出剪影；
    有两枝垂得更低，下沿压进雾带，在亮雾前面是最清楚的一笔。
    每块枝叶都要有来处：高的垂枝藏在上面的暗林冠里（伸出画面上沿）；垂进雾带的那两枝必须长在树干上
    （一枝是大树干自己的最下几层，一枝是另一棵细一点的前景树），不然就是一块悬在雾里的叶子。
    以前那枝在 x=168、没有树干、底边一刀切平，镜头在 45 附近正好压在主层大树（x=120）的树干顶上，
    像树干上顶着一块飘着的平底叶子。"""
    lay = Layer()
    dark = fol_ramp("#060b09", 3, 0.035)
    bark_d = ramp(from_hex("#0e1210"), n=5, L_span=0.08, hue_shift=8)
    rng = np.random.default_rng(9)
    noise = blocky_noise(H, W, rng, 2)
    plates = blocky_noise(H, W, rng, 1)
    # 垂进雾带、又不在大树干上的那枝：先画它的树干（比大树干细），树冠盖在上面
    x_low, tw_low = 612, 11
    front_trunk(lay, x_low - tw_low // 2, tw_low, bark_d, noise, plates)
    # 上沿的垂枝：几团大云杉的最下几层，只要树冠，枝身的下沿在 cb（14~122）。
    # 最下一层的枝梢照样垂下来，成一圈锯齿（以前在 cb 这一行一刀切，切出一条平底）。
    for i, (x, cb, r) in enumerate(((60, 50, 120), (250, 20, 70), (420, 36, 90), (612, 122, 84),
                                   (770, 30, 100), (905, 22, 70), (42, 112, 66))):   # 42 = 大树干的中线
        img = conifer(420, r, 500 + i, dark, bark_d, detail=1, trunk_w=1, crown=0.9, droop=0.85,
                      grain=0.25, bough=True, hole=0.5)
        body = int(img.shape[0] - 420 * 0.1) + 6
        lay.paste(img, x - img.shape[1] // 2, cb - body)
    # 大树干（以前 38 宽，挡掉画面太多；收到 24，往左靠）
    front_trunk(lay, 30, 24, bark_d, noise, plates, stubs=((70, 12), (150, 8)))
    for x, sz, sd in ((300, 28, 11), (690, 34, 12), (880, 22, 13)):
        f = fern(sz, sd, dark[:4] if len(dark) >= 4 else fol_ramp("#080e0c", 4, 0.06))
        lay.paste(f, x - f.shape[1] // 2, H + 8 - f.shape[0])
    return lay


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    layers = {
        "sky": sky(),
        "ridge": ridge(),
        "far": build_far(),
        "midfar": build_midfar(),
        "mid": build_mid(),
        "main": main_layer(),
        "front": front_layer(),
    }
    for k, v in layers.items():
        v.save(k)
    return layers


def preview(layers, cam_x, path, stand_in=False):
    """按 Godot 里的视差比例合成一张 480×270（镜头左边缘在 cam_x），放大 3 倍。
    stand_in：在屏幕 x=230 放一个 8×16 的近白方块当主角替身（只在预览里，不进图层）。"""
    out = np.zeros((270, 480, 4), np.uint8)
    for k in SCROLL:
        a = layers[k].a
        if a.shape[1] == 480:
            src = a
        else:
            off = int(round(cam_x * SCROLL[k])) % a.shape[1]
            src = np.roll(a, -off, axis=1)[:, :480]
        if k == "front" and stand_in:
            gy = int(round(ground_y((230 + cam_x) % W)))
            out[gy - 16:gy, 230:238] = (236, 240, 230, 255)
        m = src[..., 3] > 0
        out[m] = src[m]
    Image.fromarray(out).resize((1440, 810), Image.NEAREST).save(path)


def check_alpha(layers):
    for k, v in layers.items():
        u = set(np.unique(v.a[..., 3]).tolist())
        assert u <= {0, 255}, (k, u)
        assert v.a.shape[:2] == ((270, 480) if k == "sky" else (H, W)), (k, v.a.shape)


# 每层「地面」在哪：落到这一行上下 4 像素以内的东西算长在地上。forest_row 的层是 base_y；主层是 ground_y；
# 前景是底边。远处两层的雾到这一行以下已经褪了八成多（ramp_t ≥ 0.85），树根在这里看不见，算「落进雾里」。
GROUND_LINE = {"ridge": 214, "far": 216, "midfar": 220, "mid": 228, "front": H - 1}
FOG_FLOOR = {"ridge": 199, "far": 213}
HANG_MAX = 104      # 只挂在上沿的东西（没有树干），下沿不能低过这一行：再往下就进了雾带，看得出它悬着


def check_floating(layers, verbose=True):
    """自检：每层的不透明像素做 8 连通（左右绕回），找出「悬空团块」：
    既不碰画面上沿、又不落到这层的地面 / 雾底；或者只挂在上沿、却垂进了雾带（没有树干托着）。
    返回 {层: [(像素数, x0, x1, y0, y1, 原因), ...]}。"""
    bad = {}
    xs = np.arange(W)
    for k, lay in layers.items():
        if k == "sky":
            continue
        lab, n = components(lay.a[..., 3] > 0, wrap=True)
        gl = np.round(ground_y(xs)).astype(int) if k == "main" else np.full(W, GROUND_LINE[k])
        floor = np.minimum(gl - 4, FOG_FLOOR.get(k, H))
        ys_, xs_ = np.nonzero(lab)
        ids = lab[ys_, xs_]
        order = np.argsort(ids, kind="stable")
        ys_, xs_, ids = ys_[order], xs_[order], ids[order]
        cuts = np.searchsorted(ids, np.arange(1, n + 2))
        out = []
        for i in range(n):
            yy, xx = ys_[cuts[i]:cuts[i + 1]], xs_[cuts[i]:cuts[i + 1]]
            if (yy >= floor[xx]).any():
                continue
            if yy.min() == 0:
                if yy.max() <= HANG_MAX:
                    continue
                why = "只挂在上沿，垂进雾带"
            else:
                why = "悬空"
            # x 范围：绕回的团块按最短的那段报
            ux = np.unique(xx)
            gaps = np.diff(np.r_[ux, ux[0] + W])
            j = int(np.argmax(gaps))
            x0, x1 = int(ux[(j + 1) % len(ux)]), int(ux[j])
            out.append((len(yy), x0, x1, int(yy.min()), int(yy.max()), why))
        out.sort(reverse=True)
        bad[k] = out
        if verbose:
            print(f"  {k:7s} 连通区域 {n:4d}，悬空 {len(out)}")
            for b in out[:12]:
                print("     ", b)
    return bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="把几张合成预览存到这个目录")
    args = ap.parse_args()
    ls = build()
    check_alpha(ls)
    print("悬空枝叶自检：")
    floating = check_floating(ls)
    if args.preview:
        d = Path(args.preview)
        d.mkdir(parents=True, exist_ok=True)
        for cx in (0, 240, 520):
            preview(ls, cx, d / f"forest_{cx}.png")
        preview(ls, 240, d / "forest_240_standin.png", stand_in=True)
    print("ok", {k: v.a.shape[1] for k, v in ls.items()})
    n_bad = sum(len(v) for v in floating.values())
    if n_bad:
        sys.exit(f"有 {n_bad} 块悬空的枝叶，见上面的列表")
