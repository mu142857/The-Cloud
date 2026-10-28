"""针叶林视差小样：用小奥斯卡（oscarkit）的色阶，画 480×270 的分层森林，Silvaron 那种杂点质感。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/variants/original.py [--preview 目录]

输出 art/variants/original/*.png（1 倍；原版 tools/forest_art.py 的备份，现在 art/forest 换成了方向 C）。除了天空，每层宽 960、左右无缝，Godot 里用 Parallax2D 横向重复。
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
OUT = Path(__file__).resolve().parents[2] / "art" / "variants" / "original"

FOG = from_hex("#9fb4a8")
WARM = from_hex("#efe0b4")

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

def conifer(height, radius, seed, fol, bark, detail=2, trunk_w=None, crown=0.82, droop=0.5, dead=0):
    """一棵针叶树（云杉 / 冷杉），返回 RGBA，树根在图的底边正中。

    fol / bark   叶子、树皮色阶（暗 -> 亮）
    detail       0 = 远处的剪影（两档、没有杂点），1 = 少量杂点，2 = 近处，杂点 + 层间阴影 + 针叶须
    crown        树冠占树高的比例，下面露出树干
    droop        枝条下垂的程度
    dead         树冠下面伸出的枯枝数
    """
    rng = np.random.default_rng(seed)
    w = 2 * radius + 10
    h = height + 3
    cx = w // 2
    top = 2
    crown_bottom = top + int(height * crown)
    n = len(fol)
    tone = np.full((h, w), -1.0)       # -1 = 空
    tier_id = np.full((h, w), -1)
    noise = blocky_noise(h, w, rng, cell=2 if detail >= 2 else 3)

    # 树干：左边受光
    tw = trunk_w or max(1, radius // 8)
    trunk = np.zeros((h, w), bool)
    trunk_tone = np.zeros((h, w))
    nb = len(bark)
    for y in range(top + height // 8, h):
        f = (y - top) / max(1, h - top)
        half = max(0.5, tw * (0.35 + 0.65 * f) / 2)
        flare = max(0.0, (y - (h - 6)) / 6) * tw * 0.6 if detail >= 1 else 0
        x0, x1 = int(round(cx - half - flare)), int(round(cx + half + flare))
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
        for i in range(ln):
            x = cx + side * (tw // 2 + i)
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
                        v += (noise[y, x] - 0.5) * (2.2 if detail >= 2 else 1.2)
                    tone[y, x] = v
                    tier_id[y, x] = k
            # 枝梢：伸出去的一两个像素
            if detail >= 1:
                tx = int(round(cx + side * (r + 1)))
                ty = int(round(yk + dr))
                if 0 <= tx < w and 0 <= ty < h:
                    tone[ty, tx] = (n - 1) * 0.35 - side * 0.5
                    tier_id[ty, tx] = k
    # 树尖
    for y in range(0, top + 4):
        tone[y, cx] = (n - 1) * 0.7
        tier_id[y, cx] = 0

    fol_m = tone >= 0
    if detail >= 2:
        # 上层枝条的下沿在下层上投 2 像素的阴影
        shade = np.zeros_like(tone)
        for d in (1, 2):
            up = np.full_like(tier_id, -1)
            up[d:] = tier_id[:-d]
            shade[(fol_m) & (up >= 0) & (up < tier_id)] -= 1.0 if d == 1 else 0.6
        tone = tone + shade
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


def sky():
    """天空：从上往下 7 条色带，交界处一行抖动；左上角一团暖光。"""
    lay = Layer(480, 270)
    top, mid, low = from_hex("#4b6566"), from_hex("#86a096"), from_hex("#c4cdb8")
    bands = 7
    cols = [mix(top, mid, i / 3) if i <= 3 else mix(mid, low, (i - 3) / (bands - 4)) for i in range(bands)]
    edges = np.linspace(0, 200, bands + 1).astype(int)
    for i in range(bands):
        lay.a[edges[i]:edges[i + 1]] = tuple(cols[i]) + (255,)
        if i:   # 交界抖一行
            y = edges[i]
            lay.a[y, ::2] = tuple(cols[i - 1]) + (255,)
    lay.a[200:] = tuple(low) + (255,)
    # 太阳在左上画面外：暖光分 5 档，档与档之间用 Bayer 抖动过渡，不出硬圈
    bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16
    yy, xx = np.mgrid[:270, :480]
    d = np.hypot(xx + 30, yy + 40)
    level = np.clip((190 - d) / 150, 0, 1) * 5
    q = np.floor(level + bayer[yy % 4, xx % 4] - 0.5).clip(0, 5) / 5 * 0.4
    cache = {}
    for y, x in zip(*np.nonzero(q > 0)):
        key = (tuple(lay.a[y, x, :3]), q[y, x])
        if key not in cache:
            cache[key] = mix(key[0], WARM, key[1])
        lay.a[y, x, :3] = cache[key]
    return lay


def ridge():
    """最远的山脊，上沿是一排很小的树尖。两档，几乎是雾色。"""
    lay = Layer()
    rng = np.random.default_rng(11)
    c_body = mix(from_hex("#6f8a84"), FOG, 0.45)
    c_lit = mix(c_body, WARM, 0.18)
    xs = np.arange(W)
    base = 150 + 14 * np.sin(2 * np.pi * xs / W * 2 + 0.6) + 8 * np.sin(2 * np.pi * xs / W * 5 + 2.0) + 4 * np.sin(2 * np.pi * xs / W * 11)
    for x in xs:
        y0 = int(base[x])
        # 树尖锯齿
        tooth = 3 - abs((x % 5) - 2) + (1 if rng.random() < 0.2 else 0)
        y0 -= tooth
        lay.a[y0:, x] = tuple(c_body) + (255,)
        if base[(x + 1) % W] > base[x] or tooth >= 3:   # 朝左上的坡受光
            lay.a[y0, x] = tuple(c_lit) + (255,)
    fog_band(lay, 172, 205, 4, FOG, 1)
    return lay


def tree_row(name, count, hrange, base_y, fog_t, detail, seed, base_col, n_tones, spread=1.0,
             dead=0, fog_band_y=None, tint=None):
    lay = Layer()
    rng = np.random.default_rng(seed)
    fol = fogged(ramp(from_hex(base_col), n=n_tones, L_span=0.42 * (1 - fog_t * 0.6), hue_shift=16), fog_t)
    bark = fogged(ramp(from_hex("#5c4a40"), n=4, L_span=0.3, hue_shift=10), min(1.0, fog_t + 0.1))
    xs = np.sort(rng.uniform(0, W, count))
    xs += rng.uniform(-W / count * 0.3, W / count * 0.3, count) * spread
    order = rng.permutation(count)
    hs = rng.uniform(*hrange, count)
    for i in sorted(range(count), key=lambda i: -hs[i]):   # 高的在后面，矮的在前面
        hh = int(hs[i])
        rad = int(hh * rng.uniform(0.2, 0.27))
        img = conifer(hh, rad, seed * 100 + int(order[i]), fol, bark, detail=detail,
                      crown=rng.uniform(0.74, 0.88), droop=rng.uniform(0.35, 0.65), dead=dead)
        by = base_y + int(rng.uniform(-4, 4))
        lay.paste(img, int(xs[i]) - img.shape[1] // 2, by - img.shape[0])
    if tint:
        tint_rows(lay, tint[0], tint[1], FOG, tint[2])
    if fog_band_y:
        fog_band(lay, fog_band_y[0], fog_band_y[1], 4, FOG, seed)
    return lay


def main_layer():
    """能走的那一层：地面、蕨、倒木、树桩、石头、蘑菇，还有三棵冲出画面的大树。"""
    lay = Layer()
    rng = np.random.default_rng(5)
    fol = ramp(from_hex("#28473e"), n=7, L_span=0.44, hue_shift=18)
    bark = ramp(from_hex("#5a463c"), n=6, L_span=0.42, hue_shift=12)
    wood = ramp(from_hex("#b08a62"), n=5, L_span=0.34, hue_shift=10)
    moss = ramp(from_hex("#5f7d45"), n=6, L_span=0.4, hue_shift=18)
    soil = ramp(from_hex("#3d3832"), n=5, L_span=0.22, hue_shift=8)
    fernp = ramp(from_hex("#4f7c4a"), n=6, L_span=0.4, hue_shift=18)
    stone = ramp(from_hex("#6d716c"), n=5, L_span=0.34, hue_shift=10)
    cap = ramp(from_hex("#b5643a"), n=4, L_span=0.3, hue_shift=10)
    stem = ramp(from_hex("#cfc3a6"), n=3, L_span=0.2, hue_shift=6)

    # 大树：比画面高，树冠从上面垂下来
    for x, hh, tw, sd in ((120, 430, 16, 1), (470, 470, 20, 2), (790, 410, 14, 3)):
        img = conifer(hh, int(hh * 0.2), 900 + sd, fol, bark, detail=2, trunk_w=tw, crown=0.62, droop=0.6, dead=3)
        lay.paste(img, x - img.shape[1] // 2, int(ground_y(x)) + 3 - img.shape[0])

    # 大树的根：从树干两边爬到地上
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

    # 地面：上面一条苔藓，下面是松针落叶层，再往下越来越暗
    litter = ramp(from_hex("#5a4434"), n=5, L_span=0.3, hue_shift=12)
    noise = blocky_noise(H, W, rng, 2)
    noise_w = blocky_noise(H, W, rng, 3)
    for x in range(W):
        gy = int(round(ground_y(x)))
        lit = any(abs(((x - lx + W / 2) % W) - W / 2) < 40 for lx in LIT_X)
        for y in range(gy, H):
            d = y - gy
            n_ = noise[y, x] - 0.5
            if d < 2 or (d < 4 and noise_w[y, x] > 0.55):
                v = len(moss) - 2 - d + (1 if lit and d == 0 else 0) + n_ * 1.4
                c = moss[int(np.clip(round(v), 0, len(moss) - 1))]
            elif d < 9 and noise_w[y, x] + (9 - d) * 0.06 > 0.6:
                v = (len(litter) - 1) * 0.6 - (d - 4) * 0.25 + n_ * 1.8 + (0.8 if lit else 0)
                c = litter[int(np.clip(round(v), 0, len(litter) - 1))]
            else:
                f = min(1.0, (d - 3) / 34)
                v = (len(soil) - 1) * (0.75 - 0.85 * f) + n_ * 1.3 + (0.6 if lit and d < 14 else 0)
                c = soil[int(np.clip(round(v), 0, len(soil) - 1))]
            lay.a[y, x] = tuple(c) + (255,)
        if rng.random() < 0.45:   # 草尖、苔藓簇
            for d in range(1, int(rng.integers(2, 5))):
                lay.a[gy - d, x] = tuple(moss[min(len(moss) - 1, 2 + d // 2 + (1 if lit else 0))]) + (255,)
    # 地上的松针（亮一档的小斜线）
    for _ in range(140):
        x = int(rng.integers(0, W - 3))
        y = int(round(ground_y(x))) + int(rng.integers(2, 9))
        for i in range(2):
            if y + i < H:
                lay.a[y + i, x + i] = tuple(litter[-1] if rng.random() < 0.5 else litter[-2]) + (255,)

    def on_ground(img, x, sink=1):
        lay.paste(img, x - img.shape[1] // 2, int(round(ground_y(x))) + sink - img.shape[0])

    # 林下的小云杉、灌丛
    young = ramp(from_hex("#3a6150"), n=6, L_span=0.46, hue_shift=18)
    for x, hh, sd in ((30, 34, 1), (205, 26, 2), (395, 40, 3), (545, 28, 4), (700, 36, 5), (905, 27, 6)):
        on_ground(conifer(hh, int(hh * 0.4), 700 + sd, young, bark, detail=1, crown=0.92, droop=0.4), x, 2)

    on_ground(log(78, 12, 7, bark, wood, moss), 300, 2)
    on_ground(stump(15, 13, 8, bark, wood), 600, 2)
    for x, (wd, ht), sd in ((70, (16, 8), 1), (360, (10, 5), 2), (560, (22, 10), 3), (880, (12, 6), 4)):
        on_ground(rock(wd, ht, sd, stone, moss), x, 2)
    for x, sz, sd in ((52, 20, 1), (160, 16, 2), (240, 24, 3), (420, 20, 4), (512, 15, 5), (655, 22, 6),
                      (735, 17, 7), (850, 26, 8), (940, 16, 9)):
        on_ground(fern(sz, sd, fernp), x, 2)
    for x, sd in ((345, 1), (612, 2), (760, 3)):
        on_ground(mushrooms(sd, cap, stem), x, 1)
    return lay


def front_layer():
    """前景：很暗的大树干和一根从上面垂下来的枝，把画面框住。"""
    lay = Layer()
    dark = ramp(from_hex("#1a2422"), n=5, L_span=0.16, hue_shift=10)
    bark_d = ramp(from_hex("#241d1b"), n=5, L_span=0.17, hue_shift=10)
    rng = np.random.default_rng(9)
    noise = blocky_noise(H, W, rng, 2)
    plates = blocky_noise(H, W, rng, 1)
    # 这棵树的树冠在画面外，最下面几层枝从上沿垂下来
    x0, tw = 40, 38
    crown = conifer(620, 150, 79, dark, bark_d, detail=2, trunk_w=tw, crown=0.6, droop=0.7)
    lay.paste(crown, x0 + tw // 2 - crown.shape[1] // 2, H + 4 - crown.shape[0])
    # 大树干：圆柱的明暗 + 一块块竖着的树皮，左边一条暖色受光边
    for y in range(H):
        wob = int(round(1.5 * np.sin(y / 23)))
        for x in range(x0 + wob, x0 + wob + tw):
            u = (x - x0 - wob) / tw
            v = 2.4 * (1 - u) ** 1.6 - 0.2 + (noise[y, x] - 0.5) * 0.9
            col = (x - x0 - wob) // 5
            if (x - x0 - wob) % 5 == 0 or ((y + col * 17) % 29 == 0):   # 树皮缝
                v -= 1.0
            v += (plates[(y // 6) % H, x] - 0.5) * 0.6
            lay.a[y, x] = tuple(bark_d[int(np.clip(round(v), 0, 3))]) + (255,)
        lay.a[y, x0 + wob] = tuple(mix(bark_d[3], WARM, 0.25 if (y // 3) % 4 else 0.12)) + (255,)
    # 树干上的断枝
    for y, ln in ((70, 14), (150, 9)):
        for i in range(ln):
            for d in range(2):
                lay.a[y + i // 3 + d, x0 + tw + i] = tuple(bark_d[1 + (d == 0)]) + (255,)
    # 底边的蕨剪影、草
    for x, sz, sd in ((300, 28, 11), (690, 34, 12), (880, 22, 13)):
        f = fern(sz, sd, dark[:4])
        lay.paste(f, x - f.shape[1] // 2, H + 8 - f.shape[0])
    return lay


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    layers = {
        "sky": sky(),
        "ridge": ridge(),
        "far": tree_row("far", 34, (38, 78), 206, 0.62, 0, 21, "#3c5e55", 4, fog_band_y=(188, 214)),
        "midfar": tree_row("midfar", 17, (80, 145), 216, 0.4, 1, 31, "#33574c", 5,
                           tint=(170, 216, 0.5), fog_band_y=(200, 222)),
        "mid": tree_row("mid", 9, (160, 270), 226, 0.16, 2, 41, "#2d5045", 6, dead=2,
                        tint=(185, 226, 0.4), fog_band_y=(212, 232)),
        "main": main_layer(),
        "front": front_layer(),
    }
    for k, v in layers.items():
        v.save(k)
    return layers


def preview(layers, cam_x, path):
    """按 Godot 里的视差比例合成一张 480×270（镜头左边缘在 cam_x），放大 3 倍。"""
    out = np.zeros((270, 480, 4), np.uint8)
    for k in SCROLL:
        a = layers[k].a
        if a.shape[1] == 480:
            src = a
        else:
            off = int(round(cam_x * SCROLL[k])) % a.shape[1]
            src = np.roll(a, -off, axis=1)[:, :480]
        m = src[..., 3] > 0
        out[m] = src[m]
    Image.fromarray(out).resize((1440, 810), Image.NEAREST).save(path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="把几张合成预览存到这个目录")
    args = ap.parse_args()
    ls = build()
    if args.preview:
        d = Path(args.preview)
        d.mkdir(parents=True, exist_ok=True)
        for cx in (0, 240, 520):
            preview(ls, cx, d / f"forest_{cx}.png")
    print("ok", {k: v.a.shape[1] for k, v in ls.items()})
