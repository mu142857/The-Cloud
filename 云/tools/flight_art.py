"""飞行段（木星 → 水星）的占位美术。以后改飞行段的图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/flight_art.py [--preview 目录]

输出 art/flight/*.png（1 倍）。--preview 另存 4 倍预览和一张拼好的整屏样图。

画面：夜里从木星的森林飞往水星。天从森林那种墨绿慢慢变成水星的深蓝（sky_green / sky_blue 两张，Godot 里按进度交叉淡入），
云层画成偏中性的冷灰（Godot 里用 modulate 从绿调到蓝）。右上一轮小月亮，光从右上来：东西右上受光、左下背光。
飞船最亮（灰蓝金属 + 晨围巾的紫红条纹 + 青色舷窗），尾巴一团暖光；背景都很暗。
- 天、云：整片硬边色带，只在档边留 1 像素的稀疏抖动（和 cloud_art.py 一样，Bayer 不用）。
- 飞船：在自己的坐标系里定义形状，每个像素反算回去上色，所以 5 个倾角帧都是硬边像素，不是旋转出来的。
- 物品图标 24×24：色块派的小物件（平面 + 按光照分档，右上亮、左下暗，亮面偏暖、暗面偏冷，不描边）。
- 特效（光点的光晕、引擎光）可以半透明，其余 alpha 只有 0 / 255。
所有随机都固定 seed。
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.canvas import Canvas  # noqa: E402
from oscarkit.palette import from_hex, oklab_to_srgb, ramp, to_lab  # noqa: E402
from oscarkit.shade import step_color  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "flight"
OUT.mkdir(parents=True, exist_ok=True)
SW, SH = 480, 270
LW = 960                           # 会横向重复的图层宽度
LIGHT = np.array([0.7, -0.7])      # 指向光源（右上，月亮那边）；屏幕 y 朝下
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def mix(c, d, t):
    a, b = to_lab(c), to_lab(d)
    return tuple(int(v) for v in oklab_to_srgb((a + (b - a) * t)[None])[0])


def save(arr_or_canvas, name):
    a = arr_or_canvas.a if isinstance(arr_or_canvas, Canvas) else arr_or_canvas
    Image.fromarray(a).save(OUT / f"{name}.png")
    return a


# ---------------------------------------------------------------- 分档上色（色块派）

def walk_out(mask, d, maxn=12):
    """每个像素沿方向 d 走几步出 mask（整像素步进）。"""
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    out = np.zeros((h, w), float)
    steps = np.full(len(ys), float(maxn))
    alive = np.ones(len(ys), bool)
    for k in range(1, maxn + 1):
        px = np.round(xs + d[0] * k).astype(int)
        py = np.round(ys + d[1] * k).astype(int)
        inside = (px >= 0) & (px < w) & (py >= 0) & (py < h)
        m = np.zeros(len(ys), bool)
        m[inside] = mask[py[inside], px[inside]]
        hit = alive & ~m
        steps[hit] = k
        alive &= m
    out[ys, xs] = steps
    return out


def lit_levels(mask, lit=(1.5, 3.5), shade=1.5, light=LIGHT):
    """mask 里每个像素的档：朝光那边的边往里 lit[0] 像素内 +2，lit[1] 内 +1，背光的边 shade 内 -1。"""
    to_l = walk_out(mask, light)
    to_s = walk_out(mask, -light)
    lv = np.zeros(mask.shape, int)
    lv[to_l <= lit[1]] = 1
    lv[to_l <= lit[0]] = 2
    lv[(to_s <= shade) & (lv == 0)] = -1
    return np.where(mask, lv, 0)


def paint_lit(c, mask, base, lit=(1.5, 3.5), shade=1.5, dL=0.06, light=LIGHT, extra=None):
    lv = lit_levels(mask, lit, shade, light)
    if extra is not None:
        lv = lv + extra
    for k in np.unique(lv[mask]):
        c.fill_mask(mask & (lv == k), step_color(base, k, dL=dL))
    return lv


# ---------------------------------------------------------------- 天（屏幕固定）

def band_sky(stops, glow_y, glow_c, seed):
    """stops: [(y, hex)]，从上到下。每 3 行一个小档，档边 50% 稀疏抖动一行。"""
    ys = np.array([s[0] for s in stops], float)
    cols = [from_hex(s[1]) for s in stops]
    a = np.zeros((SH, SW, 4), np.uint8)
    a[..., 3] = 255
    step = 3
    prev = None
    for y0 in range(0, SH, step):
        yc = y0 + step / 2
        i = int(np.clip(np.searchsorted(ys, yc, side="right") - 1, 0, len(ys) - 2))
        t = float(np.clip((yc - ys[i]) / (ys[i + 1] - ys[i]), 0, 1))
        col = mix(cols[i], cols[i + 1], t)
        a[y0:y0 + step, :, :3] = col
        if prev is not None and prev != col:
            row = a[y0, :, :3]
            xs = np.arange(SW)
            row[(xs + y0) % 2 == 0] = prev
        prev = col
    # 地平线附近的一道光（宽的椭圆，分 3 档往 glow_c 推），屏幕坐标固定
    Y, X = np.mgrid[0:SH, 0:SW]
    for k, (rx, ry, t) in enumerate([(300, 46, 0.18), (220, 30, 0.34), (150, 16, 0.5)]):
        m = ((X - 250) / rx) ** 2 + ((Y - glow_y) / ry) ** 2 <= 1
        edge = m & ~(((X - 250) / (rx - 2)) ** 2 + ((Y - glow_y) / (ry - 1.2)) ** 2 <= 1) & ((X + Y) % 2 == 0)
        inner = m & ~edge
        for yy in range(SH):
            row = inner[yy]
            if row.any():
                a[yy, row, :3] = mix(tuple(a[yy, row][0, :3]), glow_c, t)
    return a


def moon(a, cx, cy, r):
    """右上的小月亮：近白偏冷，左下一弯暗，几块月海；外面两圈很淡的光环（硬边，往背景推一点）。"""
    Y, X = np.mgrid[0:SH, 0:SW]
    d = np.hypot(X + 0.5 - cx, Y + 0.5 - cy)
    for rr, t in [(r + 9, 0.10), (r + 4, 0.2)]:
        ring = d <= rr
        for yy in np.unique(Y[ring]):
            row = ring[yy]
            a[yy, row, :3] = mix(tuple(a[yy, row][0, :3]), from_hex("#c9d8e8"), t)
    disc = d <= r
    base = from_hex("#d9e3ea")
    c = Canvas(SW, SH, a)
    lv = paint_lit(c, disc, base, lit=(2.5, 6), shade=3, dL=0.05)
    # 月海
    rng = np.random.default_rng(4)
    for _ in range(5):
        mx, my = cx + rng.uniform(-r * 0.5, r * 0.5), cy + rng.uniform(-r * 0.5, r * 0.5)
        m = (np.hypot(X + 0.5 - mx, (Y + 0.5 - my) * 1.2) <= rng.uniform(2, 4.5)) & disc
        c.fill_mask(m, step_color(base, -2, dL=0.05))
    # 背光一侧的暗弯
    dark = disc & (np.hypot(X + 0.5 - cx + r * 0.55, Y + 0.5 - cy - r * 0.55) <= r * 0.95)
    c.fill_mask(dark, step_color(base, -4, dL=0.06))
    return c.a


def stars(seed=7):
    """星星层（960 宽、无缝），很慢地视差。大部分 1 像素，几颗十字。越往下（地平线光里）越少。"""
    rng = np.random.default_rng(seed)
    a = np.zeros((SH, LW, 4), np.uint8)
    for _ in range(260):
        x, y = rng.integers(0, LW), int(rng.triangular(0, 0, 200))
        b = rng.choice([0.35, 0.5, 0.65, 0.9], p=[0.45, 0.3, 0.17, 0.08])
        col = mix(from_hex("#1a2a33"), from_hex("#e8f0ff"), b)
        a[y, x] = (*col, 255)
        if b >= 0.9 and 4 < y < SH - 4:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a[y + dy, (x + dx) % LW] = (*mix(from_hex("#1a2a33"), from_hex("#e8f0ff"), 0.45), 255)
    return a


# ---------------------------------------------------------------- 云（中性冷灰，Godot 里染色）

def puff_row(rng, w, base_y, r_lo, r_hi, n, jitter):
    """一排云团：返回各团的圆。第二版：天际线随 x 起伏（周期整除 960，左右无缝），
    两处高高堆起的云山、一处沉下去的低平留白，团的大小也随位置变（不再一排一样大的馒头）。"""
    circles = []
    ph = rng.uniform(0, 2 * np.pi, 3)
    towers = rng.uniform(0, w, 2)
    flat = rng.uniform(0, w)

    def wrapd(x, c):
        d = abs(x - c) % w
        return min(d, w - d)

    x = 0.0
    while x < w:
        u = 2 * np.pi * x / w
        lift = 7 * np.sin(u + ph[0]) + 4 * np.sin(3 * u + ph[1]) + 2.5 * np.sin(5 * u + ph[2])
        scale = 1.0
        for t in towers:
            k = max(0.0, 1 - wrapd(x, t) / 70)
            lift += 18 * k * k
            scale += 0.7 * k * k
        fk = max(0.0, 1 - wrapd(x, flat) / 60)
        lift -= 10 * fk
        scale -= 0.45 * fk
        r = rng.uniform(r_lo, r_hi) * scale
        cy = base_y - lift + rng.uniform(-jitter, jitter) + r * 0.35
        circles.append((x, cy, r))
        x += max(4.0, r * rng.uniform(0.7, 1.4))
    return circles


def circles_mask(circles, h, w, wrap=True):
    Y, X = np.mgrid[0:h, 0:w]
    m = np.zeros((h, w), bool)
    for cx, cy, r in circles:
        for off in ((-w, 0, w) if wrap else (0,)):
            m |= (X + 0.5 - cx - off) ** 2 + ((Y + 0.5 - cy) * 1.25) ** 2 <= r * r
    return m


def cloud_layer(seed, rows, palette, h=SH, w=LW, fill_below=True):
    """rows: [(base_y, r_lo, r_hi, jitter)] 从远（上）到近（下）。每排一个亮度档：前面的排更暗，顶边一道受光边。
    palette：暗 → 亮。每排的身体用 palette[i] 起，受光边 +1 / +2 档。"""
    rng = np.random.default_rng(seed)
    a = np.zeros((h, w, 4), np.uint8)
    c = Canvas(w, h, a)
    for i, (by, rlo, rhi, jit) in enumerate(rows):
        circles = puff_row(rng, w, by, rlo, rhi, 0, jit)
        m = circles_mask(circles, h, w)
        if fill_below:
            # 每列从天际线一直填到底（云海是一整片）
            top = np.where(m.any(0), m.argmax(0), h)
            Y = np.arange(h)[:, None]
            m = Y >= top[None, :]
        body = palette[i]
        # 受光：沿光的方向出团的步数（右上亮），左下背光边暗一档
        to_l = walk_out(m, LIGHT, 6)
        lv = np.zeros(m.shape, int)
        lv[to_l <= 3.5] = 1
        lv[to_l <= 1.5] = 2
        # 档边稀疏抖动一像素
        Y, X = np.mgrid[0:h, 0:w]
        edge1 = (to_l > 3.5) & (to_l <= 4.5) & ((X + Y) % 2 == 0)
        lv[edge1] = 1
        for k in (0, 1, 2):
            col = step_color(body, k * 1.15, dL=0.05)
            c.fill_mask(m & (lv == k), col)
    return c.a


def wisps(seed=21):
    """高空几缕薄云（很暗、很扁），挡一点星星。"""
    rng = np.random.default_rng(seed)
    a = np.zeros((SH, LW, 4), np.uint8)
    c = Canvas(LW, SH, a)
    base = from_hex("#1c2426")
    for _ in range(7):
        cx, cy = rng.uniform(0, LW), rng.uniform(40, 130)
        L = rng.uniform(60, 150)
        th = rng.uniform(2, 4.5)
        Y, X = np.mgrid[0:SH, 0:LW]
        for off in (-LW, 0, LW):
            dx = (X + 0.5 - cx - off) / L
            dy = (Y + 0.5 - cy - 6 * np.sin(dx * 2.2)) / th
            m = dx ** 2 + dy ** 2 <= 1
            c.fill_mask(m, base)
            top = m & (dy < -0.35)
            c.fill_mask(top, step_color(base, 1, dL=0.05))
    return c.a


# ---------------------------------------------------------------- 起飞的森林、水星

def launch_forest(seed=31):
    """起飞时脚下那片云杉林冠（720×120，不重复，只在开头经过）。墨绿近黑，树尖顶上一点受光。"""
    rng = np.random.default_rng(seed)
    w, h = 760, 120
    c = Canvas(w, h)
    far, near = from_hex("#0f211b"), from_hex("#08130f")
    for layer, (col, y0, sz) in enumerate([(far, 40, (26, 46)), (near, 62, (34, 58))]):
        x = -10.0
        while x < w + 10:
            th = rng.uniform(*sz)
            hw = th * rng.uniform(0.26, 0.34)
            top = y0 + rng.uniform(-10, 14)
            pts = [(x, top)]
            # 云杉：一层层往外伸的枝（锯齿）
            tiers = 5
            for k in range(1, tiers + 1):
                yy = top + th * k / tiers
                ww = hw * k / tiers
                pts.append((x + ww, yy))
                pts.append((x + ww * 0.55, yy - 1))
            pts += [(x + hw * 0.3, h), (x - hw * 0.3, h)]
            for k in range(tiers, 0, -1):
                yy = top + th * k / tiers
                ww = hw * k / tiers
                pts.append((x - ww * 0.55, yy - 1))
                pts.append((x - ww, yy))
            m = c.poly(pts)
            m |= c.rect(int(x - hw * 0.3), int(top + th), int(x + hw * 0.3), h)
            c.fill_mask(m, col)
            lv = lit_levels(m, lit=(1.2, 1.2), shade=0)
            c.fill_mask(m & (lv >= 1), step_color(col, 1.2, dL=0.05))
            x += hw * rng.uniform(0.9, 1.4)
    c.rect(0, 100, w, h, near)
    return c


def mercury(d=240):
    """水星：一颗海蓝的星球（这里的「水星」是水的星球）。右上受光，几条浅色云带，外面一圈薄薄的大气。"""
    c = Canvas(d + 8, d + 8)
    cx = cy = (d + 8) / 2
    r = d / 2
    Y, X = np.mgrid[0:d + 8, 0:d + 8]
    dx, dy = (X + 0.5 - cx) / r, (Y + 0.5 - cy) / r
    rr = np.hypot(dx, dy)
    disc = rr <= 1
    atm = (rr <= 1 + 3 / r) & ~disc
    c.fill_mask(atm, from_hex("#3d7fa8"))
    # 球面法线点乘光
    nz = np.sqrt(np.clip(1 - rr ** 2, 0, 1))
    lam = np.clip(dx * LIGHT[0] + (dy * LIGHT[1]) + nz * 0.55, 0, None)
    # 云带：纬度方向的正弦，打成硬边条
    lat = dy + 0.08 * np.sin(dx * 6)
    band = (np.sin(lat * 13) > 0.55) | (np.sin(lat * 7 + 1.3) > 0.8)
    base = from_hex("#143a5e")
    lv = np.floor(lam * 4.2 + 0.0).astype(int)
    # 档边抖动
    frac = lam * 4.2 - np.floor(lam * 4.2)
    lv += ((frac > 0.82) & ((X + Y) % 2 == 0)).astype(int)
    lv = np.clip(lv, 0, 5)
    for k in range(6):
        m = disc & (lv == k)
        c.fill_mask(m & ~band, step_color(base, (k - 1.5) * 1.1, dL=0.045))
        c.fill_mask(m & band, step_color(base, (k - 1.5) * 1.1 + 1.2, dL=0.045))
    # 受光一侧的大气亮边
    rim = disc & (rr > 1 - 2.2 / r) & (lam > 0.55)
    c.fill_mask(rim, from_hex("#6fb0cc"))
    return c


def planet_icon(base, band_c, seed):
    """进度条两端的小星球（9×9）。"""
    c = Canvas(9, 9)
    m = c.ellipse(4.5, 4.5, 4.5, 4.5)
    paint_lit(c, m, from_hex(base), lit=(1.2, 2.5), shade=1.2, dL=0.07)
    if band_c:
        c.fill_mask(m & c.rect(0, 5, 8, 5), from_hex(band_c))
    return c


# ---------------------------------------------------------------- 飞船（侧面，机头朝右）

HULL = ramp((0x8c, 0x9c, 0xa8), 6, L_span=0.34, hue_shift=10)
STRIPE = [from_hex(h) for h in ("#5b3152", "#7e4772", "#a35f8f")]
GLASS = [from_hex(h) for h in ("#173638", "#2f6a68", "#8fe0d0")]
NOZZLE = from_hex("#2a2c36")


def ship_shape(u, v):
    """自己的坐标（机头朝右，u -22..22，v 向下）。返回部件名或 None。"""
    t = (u + 22) / 44.0                     # 0 尾 .. 1 机头
    # 驾驶舱玻璃（船身上方前段的一个鼓包）
    if ((u - 7) / 8.5) ** 2 + ((v + 5.0) / 4.2) ** 2 <= 1 and v < -2.2:
        return "glass"
    # 尾翼（上）
    if -21 <= u <= -9:
        ft = (u + 21) / 12.0
        if -4 >= v >= -4 - 9 * (1 - ft) and v >= -13 + 0 * ft and u <= -9 - (v + 4) * 0.45 + 0:
            return "fin"
    # 下面一片小翼
    if -12 <= u <= 0 and 3 <= v <= 3 + (u + 12) * 0.32 and u >= -12 + (v - 3) * 2.2:
        return "wing"
    if t < 0 or t > 1:
        return None
    # 船身：机头圆、尾部收成平的喷口
    nose = min((1 - t) / 0.42, 1)
    top = 5.6 * math.sqrt(max(0.0, 1 - (1 - nose) ** 2)) * (1 - 0.2 * max(0, 0.35 - t) / 0.35)
    bot = 4.6 * math.sqrt(max(0.0, 1 - (1 - min((1 - t) / 0.5, 1)) ** 2)) * (1 - 0.25 * max(0, 0.35 - t) / 0.35)
    if -top <= v <= bot:
        if u < -19.5:
            return "nozzle"
        if 0.6 <= v <= 1.9 and u < 15:
            return "stripe"
        return "hull"
    return None


def ship_frame(angle_deg, W=54, H=40):
    """船身中心在 (W/2, H/2)；angle 正 = 机头朝下。"""
    c = Canvas(W, H)
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    part = {}
    for y in range(H):
        for x in range(W):
            px, py = x + 0.5 - W / 2, y + 0.5 - H / 2
            u = px * ca + py * sa                 # 反旋转回自己的坐标
            v = -px * sa + py * ca
            p = ship_shape(u, v)
            if p:
                part[(x, y)] = (p, u, v)
    mask = np.zeros((H, W), bool)
    for (x, y) in part:
        mask[y, x] = True
    # 光从右上：沿光走几步出船身
    to_l = walk_out(mask, LIGHT, 8)
    to_s = walk_out(mask, -LIGHT, 8)
    for (x, y), (p, u, v) in part.items():
        k = 2
        if to_l[y, x] <= 1.5:
            k = 5
        elif to_l[y, x] <= 3.5:
            k = 4
        elif to_l[y, x] <= 6.5:
            k = 3
        if to_s[y, x] <= 1.5:
            k = min(k, 1)
        if p == "hull" or p == "fin" or p == "wing":
            col = HULL[k - (1 if p == "wing" else 0)]
        elif p == "stripe":
            col = STRIPE[2 if k >= 4 else (1 if k >= 2 else 0)]
        elif p == "glass":
            col = GLASS[0] if v > -4.6 or u < 3 else GLASS[1]
        else:
            col = NOZZLE
        c.put(x, y, col)
    # 舷窗高光一颗
    gx, gy = 9.5, -6.6
    hx = gx * ca - gy * sa + W / 2
    hy = gx * sa + gy * ca + H / 2
    c.put(int(hx), int(hy), GLASS[2])
    c.put(int(hx) - 1, int(hy), GLASS[1])
    # 机身上一道板缝（暗一档）
    for vv in np.linspace(-4.5, 3.5, 12):
        uu = -3
        sx = uu * ca - vv * sa + W / 2
        sy = uu * sa + vv * ca + H / 2
        if 0 <= int(sx) < W and 0 <= int(sy) < H and part.get((int(sx), int(sy)), ("",))[0] == "hull":
            cur = c.get(int(sx), int(sy))[:3]
            c.put(int(sx), int(sy), step_color(cur, -1.3, dL=0.05))
    return c


def ship_sheet():
    angles = [-22, -11, 0, 11, 22]
    frames = [ship_frame(a) for a in angles]
    W, H = frames[0].w, frames[0].h
    sheet = Canvas(W * len(frames), H)
    for i, f in enumerate(frames):
        sheet.paste(f, i * W, 0)
    return sheet


def glow(r, col, alpha_max=200, steps=4):
    """半透明圆形光晕（特效用）：几圈硬边的同心圆，越往外越淡。"""
    d = r * 2 + 1
    a = np.zeros((d, d, 4), np.uint8)
    Y, X = np.mgrid[0:d, 0:d]
    dist = np.hypot(X - r, Y - r)
    for k in range(steps):
        rr = r * (1 - k / steps)
        m = dist <= rr
        a[m, :3] = col
        a[m, 3] = int(alpha_max * (k + 1) / steps * 0.55)
    return a


def flame_frames():
    """尾焰 3 帧（10×7），朝左喷。暖白 → 橙。半透明不用，硬边。"""
    pal = [from_hex("#f7e7b0"), from_hex("#f0b860"), from_hex("#d0703a")]
    rows = [
        ["...cc.....", "..cbbbc...", ".cbaaabbc.", "cbaaaaaab.", ".cbaaabbc.", "..cbbbc...", "...cc....."],
        ["....c.....", "..ccbbc...", "ccbbaaabc.", ".cbaaaaab.", "ccbbaaabc.", "..ccbbc...", "....c....."],
        ["..........", "...cbbc...", ".ccbaabbc.", "cbbaaaaab.", ".ccbaabbc.", "...cbbc...", ".........."],
    ]
    sheet = Canvas(30, 7)
    for i, r in enumerate(rows):
        f = Canvas.from_rows([row[::-1] for row in r], {"a": pal[0], "b": pal[1], "c": pal[2]})
        sheet.paste(f, i * 10, 0)
    return sheet


# ---------------------------------------------------------------- 障碍

def rock(seed, w, h):
    """漂浮的岩块：上面一层苔，下面收成一个尖，挂几根根须。右上受光。"""
    rng = np.random.default_rng(seed)
    c = Canvas(w, h)
    top_y = h * 0.3
    pts = []
    n = 9
    for i in range(n + 1):                         # 顶边（略起伏）
        x = 1 + (w - 2) * i / n
        pts.append((x, top_y + rng.uniform(-2.5, 2.0) - 2 * math.sin(i / n * math.pi)))
    tip_x = w * rng.uniform(0.42, 0.58)
    pts += [(w - 2, top_y + h * 0.18), (w * 0.8, h * 0.62), (tip_x + 3, h * 0.86), (tip_x, h - 1),
            (tip_x - 4, h * 0.82), (w * 0.2, h * 0.58), (1, top_y + h * 0.15)]
    m = c.poly(pts)
    stone = from_hex("#3a3a4c")
    lv = paint_lit(c, m, stone, lit=(1.5, 3.5), shade=2, dL=0.065)
    # 斜向的裂缝（暗楔 + 一条亮棱）
    for _ in range(2):
        x0 = rng.uniform(w * 0.25, w * 0.75)
        y0 = top_y + rng.uniform(4, 8)
        for k in range(int(h * 0.3)):
            xx, yy = int(x0 - k * 0.5), int(y0 + k)
            if 0 <= xx < w and 0 <= yy < h and m[yy, xx] and m[yy, min(xx + 1, w - 1)]:
                cur = c.get(xx, yy)[:3]
                c.put(xx, yy, step_color(cur, -1.5, dL=0.06))
                c.put(xx + 1, yy, step_color(cur, 1, dL=0.06))
    # 苔：顶边往下 2~4 像素
    Y, X = np.mgrid[0:h, 0:w]
    top_edge = np.where(m.any(0), m.argmax(0), h)
    depth = Y - top_edge[None, :]
    thick = 2 + (np.sin(X * 0.7 + seed) > 0.3).astype(int) + (np.sin(X * 1.9 + seed * 2) > 0.6).astype(int)
    moss = m & (depth >= 0) & (depth < thick)
    mb = from_hex("#34503f")
    c.fill_mask(moss, mb)
    c.fill_mask(moss & (depth == 0), step_color(mb, 1.6, dL=0.06))
    c.fill_mask(moss & (depth == 0) & (X > w * 0.55), step_color(mb, 2.6, dL=0.06))
    # 根须
    for _ in range(3):
        x = int(rng.uniform(w * 0.25, w * 0.75))
        ys = np.nonzero(m[:, x])[0]
        if len(ys) == 0:
            continue
        y = ys.max() + 1
        L = int(rng.uniform(3, 7))
        for k in range(L):
            c.put(x + (1 if k > L // 2 and seed % 2 else 0), y + k, from_hex("#2a2b38"))
    # 两颗小小的发光晶体（冷青色，让岩块在暗处也读得出来）
    for _ in range(2):
        cand = np.argwhere(m & (depth > 4) & (lv <= 0))
        if len(cand):
            y, x = cand[rng.integers(len(cand))]
            c.put(x, y, from_hex("#6fc6c0"))
            c.put(x, y - 1, from_hex("#3f8a8c"))
    return c


def storm(seed=5, w=230, h=112):
    """低垂的雷云：从屏幕顶上垂下来，三排云团越往下越少、中间垂得最低。暗石板蓝，每团底边被下面的光照出一道冷亮边。
    另出一张 storm_flash（里面的闪光区域，Godot 里叠加混合、偶尔一闪）。返回 (图, 闪光, 碰撞圆[(x, y, r)])。"""
    rng = np.random.default_rng(seed)
    c = Canvas(w, h)
    Y, X = np.mgrid[0:h, 0:w]
    rows = [(-6, 22, 32, 0.0), (30, 17, 25, 0.18), (60, 13, 20, 0.34)]
    circles = []
    for ry, rlo, rhi, inset in rows:
        x = w * inset + 6
        while x < w * (1 - inset) - 6:
            r = rng.uniform(rlo, rhi)
            sag = 12 * math.sin(math.pi * x / w) if ry > 0 else 0
            cy = min(ry + sag + rng.uniform(-4, 4), h - r - 1)
            circles.append((x, cy, r))
            x += r * rng.uniform(0.95, 1.35)
    m = np.zeros((h, w), bool)
    own = np.full((h, w), -1)
    for i, (cx, cy, r) in enumerate(circles):
        cm = (X + 0.5 - cx) ** 2 + ((Y + 0.5 - cy) * 1.15) ** 2 <= r * r
        m |= cm
        own[cm] = i                      # 后画（更低一排）的团盖住前面的
    base = from_hex("#1b2031")
    c.fill_mask(m, base)
    # 每团底边：被下面的光照亮一条（只在这团露在外面的地方）
    for i, (cx, cy, r) in enumerate(circles):
        d = r - np.hypot(X + 0.5 - cx, (Y + 0.5 - cy) * 1.15)
        lower = (Y + 0.5 > cy + r * 0.25) & (own == i)
        c.fill_mask(lower & (d < 4) & (d >= 0), from_hex("#262c41"))
        c.fill_mask(lower & (d < 1.6) & (d >= 0), from_hex("#3a4260"))
    to_b = walk_out(m, np.array([0.0, 1.0]), 6)
    c.fill_mask(m & (to_b <= 1) & (Y > 20), from_hex("#525c7c"))
    flash = np.zeros((h, w, 4), np.uint8)
    inner = m & (to_b > 3) & (Y > 18)
    flash[inner] = (180, 170, 255, 255)
    hit = [(cx, cy, r * 0.8) for cx, cy, r in circles if cy > 10]
    return c, flash, hit


def bird_frames():
    """迁徙的鸟 4 帧（17×9），被月光照着的浅灰蓝：身体一小截，两翼长，扇一下往下压。"""
    pal = {"a": from_hex("#aebdcc"), "b": from_hex("#7d8ca0"), "c": from_hex("#d6e2ec"), "d": from_hex("#5d6b80")}
    frames = [
        ["a...............a", ".aa...........aa.", "...aa.......aa...", ".....acccccb.....", "......bbbbb......",
         ".......d.d.......", ".................", ".................", "................."],
        [".................", "aaa...........aaa", "...aaa.....aaa...", ".....acccccb.....", "......bbbbb......",
         ".......d.d.......", ".................", ".................", "................."],
        [".................", ".................", ".................", "....aacccccbaa...", "..aa..bbbbb..aa..",
         ".a.....d.d.....a.", "a...............a", ".................", "................."],
        [".................", ".................", ".aaa.........aaa.", "....aacccccbaa...", "......bbbbb......",
         ".......d.d.......", ".................", ".................", "................."],
    ]
    sheet = Canvas(68, 9)
    for i, r in enumerate(frames):
        sheet.paste(Canvas.from_rows(r, pal), i * 17, 0)
    return sheet


# ---------------------------------------------------------------- 光点、小特效

def mote():
    c = Canvas.from_rows([".b.", "bab", ".b."], {"a": from_hex("#fff4cf"), "b": from_hex("#f2bb5c")})
    return c


def wood_chunk():
    """掉出飞船的木头（10×5）：发光木头，切面琥珀色。"""
    pal = {"a": from_hex("#3b2c25"), "b": from_hex("#57402f"), "c": from_hex("#77583c"), "d": from_hex("#f0b860"),
           "e": from_hex("#c9783a")}
    return Canvas.from_rows([".bbbbbbcc.", "baaabbbbde", "aaaaaaabdd", "aaaaaaaaed", ".aaaaaaaa."], pal)


def puff_frames():
    """引擎咳嗽冒的小烟（3 帧 7×7，灰紫）。"""
    pal = {"a": from_hex("#4a4a58"), "b": from_hex("#34343f")}
    rows = [
        [".......", ".......", "..aa...", ".aaab..", ".abbb..", "..bb...", "......."],
        [".......", "..aaa..", ".aaaab.", ".aabbb.", ".abbbb.", "..bbb..", "......."],
        ["..a.a..", ".a...b.", "a.....b", ".......", "b.....b", ".b...b.", "..b.b.."],
    ]
    sheet = Canvas(21, 7)
    for i, r in enumerate(rows):
        sheet.paste(Canvas.from_rows(r, pal), i * 7, 0)
    return sheet


def ui_icons():
    out = {}
    out["ui_flame"] = Canvas.from_rows(
        ["...b...", "..bb...", "..bab..", ".baab..", ".baaab.", "bacaab.", "baccab.", ".bccb..", "..bb..."],
        {"a": from_hex("#f0b860"), "b": from_hex("#c9683a"), "c": from_hex("#fbe6b0")})
    out["ui_keep"] = Canvas.from_rows(
        [".aa.aa.", "abbabba", "abbbbba", ".abbba.", "..aba..", "...a..."],
        {"a": from_hex("#b9a8c8"), "b": from_hex("#e6d6ee")})
    out["ui_drop"] = Canvas.from_rows(
        ["..a..", "..a..", ".aba.", "abbba", "abcba", ".aaa."],
        {"a": from_hex("#c9783a"), "b": from_hex("#f0b860"), "c": from_hex("#fbe6b0")})
    return out


def card_bg(w=220, h=178):
    """决定卡的底：很深的夜蓝，一圈细边，四个角一颗小星。图标后面的暖光是另一张半透明的 card_glow（特效）。"""
    c = Canvas(w, h)
    base = from_hex("#0f1320")
    m = c.rect(1, 0, w - 2, h - 1) | c.rect(0, 1, w - 1, h - 2)
    c.fill_mask(m, base)
    # 细边：内缩 3 像素一圈更亮一点的线，四角留缺口放小星
    edge_c = from_hex("#2a3146")
    for x in range(8, w - 8):
        c.put(x, 3, edge_c)
        c.put(x, h - 4, edge_c)
    for y in range(8, h - 8):
        c.put(3, y, edge_c)
        c.put(w - 4, y, edge_c)
    star = from_hex("#8d97b8")
    for (sx, sy) in ((5, 5), (w - 6, 5), (5, h - 6), (w - 6, h - 6)):
        c.put(sx, sy, star)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c.put(sx + dx, sy + dy, edge_c)
    return c


def soft_glow(w, h, cx, cy, rx, ry, col, alpha, seed, wobble=0.18):
    """柔的光晕（特效，半透明）：alpha 从中心往外平滑落下去，轮廓被低频噪声推得不规则（不是一圈圈的靶子）。"""
    rng = np.random.default_rng(seed)
    Y, X = np.mgrid[0:h, 0:w]
    ang = np.arctan2(Y + 0.5 - cy, X + 0.5 - cx)
    k = np.ones_like(ang)
    for f in (2, 3, 5):
        k += wobble / f * 2 * np.sin(f * ang + rng.uniform(0, 6.28))
    d = np.hypot((X + 0.5 - cx) / rx, (Y + 0.5 - cy) / ry) / k
    a = np.clip(1 - d, 0, 1) ** 1.8
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = col
    out[..., 3] = np.round(a * alpha * 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------- 物品图标（24×24，色块派小物件）

def icon_canvas():
    return Canvas(24, 24)


def ic_wood():
    c = icon_canvas()
    bark = from_hex("#5a4436")
    m = c.poly([(3, 15), (17, 7), (21, 12), (7, 20)])
    paint_lit(c, m, bark, dL=0.06)
    # 树皮纹：几条斜的暗线
    for k in range(3):
        c.line(7 + k * 4, 16 - k * 2, 10 + k * 4, 14 - k * 2, step_color(bark, -1.6, dL=0.06))
    # 发光的切面（右端椭圆）
    e = c.ellipse(19.5, 9.8, 3.2, 3.6)
    c.fill_mask(e, from_hex("#c9783a"))
    c.fill_mask(c.ellipse(19.8, 9.6, 2.0, 2.4), from_hex("#f0b860"))
    c.put(20, 9, from_hex("#fbe6b0"))
    return c


def ic_moss():
    c = icon_canvas()
    base = from_hex("#56704f")
    m = c.ellipse(12, 15, 9, 6) | c.ellipse(9, 11.5, 5, 4.5) | c.ellipse(15.5, 11, 5, 4.5)
    paint_lit(c, m, base, dL=0.06)
    rng = np.random.default_rng(3)
    for _ in range(10):
        x, y = rng.integers(5, 20), rng.integers(9, 20)
        if m[y, x]:
            c.put(x, y, step_color(c.get(x, y)[:3], rng.choice([-1, 1]), dL=0.06))
    # 一根麻绳
    c.line(4, 15, 20, 13, from_hex("#a08a62"))
    c.put(12, 14, from_hex("#c7b285"))
    return c


def ic_canvas():
    c = icon_canvas()
    base = from_hex("#a9a08a")
    m = c.poly([(3, 9), (19, 6), (21, 17), (14, 19), (12, 17), (9, 20), (4, 19)])
    paint_lit(c, m, base, dL=0.055)
    # 折痕
    c.line(4, 13, 20, 11, step_color(base, -1.5, dL=0.055))
    c.line(4, 14, 20, 12, step_color(base, 0.8, dL=0.055))
    # 一块补丁
    c.rect(14, 8, 17, 10, from_hex("#7d6f8a"))
    return c


def ic_scarf():
    """叠好的围巾：一摞折了两折的厚布，一端垂下来带流苏，两道暖色细条（晨围巾的紫红）。"""
    c = icon_canvas()
    base = STRIPE[1]
    m = c.poly([(3, 9), (19, 7), (20, 17), (4, 18)])
    paint_lit(c, m, base, dL=0.065)
    c.line(4, 13, 19, 12, step_color(base, -1.6, dL=0.065))          # 折缝
    c.line(4, 12, 19, 11, step_color(base, 1.2, dL=0.065))
    tail = c.poly([(15, 16), (20, 16), (21, 22), (16, 22)])
    paint_lit(c, tail, step_color(base, -0.6, dL=0.065), dL=0.065)
    for (x0, y0, x1, y1) in ((4, 15, 19, 14), (16, 19, 20, 19)):
        c.line(x0, y0, x1, y1, from_hex("#d9a35e"))
    for x in range(16, 22, 2):
        c.put(x, 23, from_hex("#c58ab0"))
    return c


def ic_letter():
    c = icon_canvas()
    paper = from_hex("#d8ccb4")
    # 信纸从信封里探出来
    sheet = c.poly([(6, 4), (17, 3), (18, 13), (7, 14)])
    paint_lit(c, sheet, from_hex("#e7dfcd"), dL=0.04)
    for k in range(3):
        c.line(8, 6 + k * 2, 15, 5 + k * 2, from_hex("#8d8fa8"))
    env = c.rect(3, 10, 20, 20)
    paint_lit(c, env, paper, dL=0.05)
    c.polyline([(3, 10), (11, 16), (20, 10)], step_color(paper, -1.4, dL=0.05))
    # 封口的小红蜡
    c.rect(10, 15, 12, 17, from_hex("#a8413f"))
    c.put(11, 15, from_hex("#d06a5a"))
    c.put(12, 15, from_hex("#d06a5a"))
    return c


def ic_pinecone():
    c = icon_canvas()
    base = from_hex("#7a5236")
    m = c.ellipse(11.5, 14, 6, 8)
    paint_lit(c, m, base, dL=0.06)
    # 鳞片：错开的小 V
    for row in range(5):
        y = 8 + row * 3
        for k in range(-2, 3):
            x = 11 + k * 3 + (row % 2)
            if m[min(y, 23), max(0, min(x, 23))]:
                c.put(x, y, step_color(base, -1.8, dL=0.06))
                c.put(x - 1, y - 1, step_color(base, -1.0, dL=0.06))
                c.put(x + 1, y - 1, step_color(base, 1.2, dL=0.06))
    # 顶上冒出一片小嫩芽（她说会长出森林）
    c.line(12, 6, 12, 3, from_hex("#5f8f55"))
    c.put(13, 3, from_hex("#8cc27a"))
    c.put(14, 2, from_hex("#8cc27a"))
    c.put(11, 4, from_hex("#6fa565"))
    return c


def ic_drawing():
    c = icon_canvas()
    paper = from_hex("#e2dccb")
    m = c.poly([(3, 5), (20, 3), (21, 20), (4, 21)])
    paint_lit(c, m, paper, dL=0.04)
    # 卷起来的一角
    c.poly([(17, 20), (21, 16), (21, 20)], step_color(paper, -2, dL=0.05))
    # 画：一个大眼睛的小人（晨），彩笔
    pen = from_hex("#7e4772")
    c.ellipse(12, 10, 4.5, 4.5, from_hex("#c9b6a0"))
    c.put(10, 10, from_hex("#2f6a68"))
    c.put(11, 10, from_hex("#2f6a68"))
    c.put(13, 10, from_hex("#2f6a68"))
    c.put(14, 10, from_hex("#2f6a68"))
    c.put(10, 9, from_hex("#8fe0d0"))
    c.put(13, 9, from_hex("#8fe0d0"))
    c.line(10, 12, 14, 12, from_hex("#a8413f"))
    c.rect(9, 15, 15, 18, pen)
    c.line(7, 8, 17, 7, from_hex("#d9a35e"))      # 发箍
    # 角落一颗歪歪的星星
    c.put(18, 6, from_hex("#d9a35e"))
    c.put(17, 6, from_hex("#e6c88a"))
    c.put(18, 5, from_hex("#e6c88a"))
    return c


ICONS = {
    "wood": ic_wood, "moss": ic_moss, "canvas": ic_canvas,
    "scarf": ic_scarf, "letter": ic_letter, "pinecone": ic_pinecone, "drawing": ic_drawing,
}


# ---------------------------------------------------------------- main

SKY_GREEN = [(0, "#030907"), (40, "#050e0b"), (80, "#08140f"), (120, "#0c1c16"), (160, "#12281f"),
             (196, "#1a3a2d"), (214, "#21473a"), (232, "#183427"), (270, "#0c1a14")]
SKY_BLUE = [(0, "#02050c"), (40, "#040914"), (80, "#07101f"), (120, "#0b182c"), (160, "#11233d"),
            (196, "#19324f"), (214, "#21405f"), (232, "#183049"), (270, "#0b1626")]
CLOUD_PAL = [from_hex(h) for h in ("#1d2a2e", "#16201f", "#0e1515")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    args = ap.parse_args()

    for name, stops in (("sky_green", SKY_GREEN), ("sky_blue", SKY_BLUE)):
        a = band_sky(stops, 214, from_hex("#3d6a58" if name == "sky_green" else "#3c6a90"), 1)
        a = moon(a, 404, 56, 13)
        save(a, name)
    save(stars(), "stars")
    save(wisps(), "wisps")
    save(cloud_layer(11, [(196, 14, 26, 6)], [from_hex("#2a3a3e")]), "clouds_far")
    save(cloud_layer(12, [(222, 16, 30, 6)], [from_hex("#1c2829")]), "clouds_mid")
    save(cloud_layer(13, [(250, 18, 34, 5)], [from_hex("#101718")]), "clouds_near")
    save(launch_forest(), "launch_forest")
    save(mercury(), "mercury")
    save(planet_icon("#5f7a52", "#3f5640", 1), "icon_jupiter")
    save(planet_icon("#3f7fb0", "#9ad0e8", 2), "icon_mercury")
    save(ship_sheet(), "ship")
    save(flame_frames(), "flame")
    save(glow(12, (255, 190, 110), 210), "glow_warm")
    save(glow(7, (255, 230, 170), 230, 3), "glow_mote")
    save(glow(20, (255, 255, 255), 255, 5), "glow_white")
    for i, (w, h) in enumerate([(34, 30), (46, 38), (28, 26)]):
        save(rock(40 + i, w, h), f"rock_{'abc'[i]}")
    st, fl, _ = storm()
    save(st, "storm")
    save(fl, "storm_flash")
    save(bird_frames(), "bird")
    save(mote(), "mote")
    save(wood_chunk(), "wood_chunk")
    save(puff_frames(), "puff")
    for k, v in ui_icons().items():
        save(v, k)
    save(card_bg(), "card")
    save(soft_glow(220, 120, 110, 48, 82, 56, (214, 150, 104), 0.30, 3), "card_glow")
    save(soft_glow(64, 64, 32, 32, 30, 30, (240, 190, 120), 0.45, 4, 0.1), "sel_glow")
    save(soft_glow(420, 420, 210, 210, 205, 205, (120, 200, 235), 0.22, 5, 0.05), "mercury_glow")
    for k, fn in ICONS.items():
        save(fn(), f"item_{k}")

    if args.preview:
        pv = Path(args.preview)
        pv.mkdir(parents=True, exist_ok=True)
        comp = Image.open(OUT / "sky_green.png").convert("RGBA")
        for n, y in (("stars", 0), ("wisps", 0), ("clouds_far", 0), ("clouds_mid", 0)):
            comp.alpha_composite(Image.open(OUT / f"{n}.png").crop((0, 0, SW, SH)))
        comp.alpha_composite(Image.open(OUT / "launch_forest.png").crop((0, 0, SW, 120)), (0, 150))
        comp.alpha_composite(Image.open(OUT / "rock_b.png"), (300, 120))
        comp.alpha_composite(Image.open(OUT / "storm.png"), (200, 0))
        shp = Image.open(OUT / "ship.png").crop((108, 0, 162, 40))
        comp.alpha_composite(shp, (100, 110))
        comp.alpha_composite(Image.open(OUT / "clouds_near.png").crop((0, 0, SW, SH)))
        comp.resize((SW * 3, SH * 3), Image.NEAREST).save(pv / "comp_green.png")
        comp2 = Image.open(OUT / "sky_blue.png").convert("RGBA")
        for n in ("stars", "wisps", "clouds_far", "clouds_mid"):
            comp2.alpha_composite(Image.open(OUT / f"{n}.png").crop((200, 0, 200 + SW, SH)))
        comp2.alpha_composite(Image.open(OUT / "mercury.png"), (300, 120))
        comp2.alpha_composite(Image.open(OUT / "clouds_near.png").crop((200, 0, 200 + SW, SH)))
        comp2.resize((SW * 3, SH * 3), Image.NEAREST).save(pv / "comp_blue.png")
        # 图标 / 飞船 / 小东西拼一张
        names = ["ship", "flame", "bird", "mote", "wood_chunk", "puff", "ui_flame", "ui_keep", "ui_drop",
                 "icon_jupiter", "icon_mercury", "rock_a", "rock_b", "rock_c"] + [f"item_{k}" for k in ICONS]
        ims = [Image.open(OUT / f"{n}.png").convert("RGBA") for n in names]
        Wt = 8 + sum(i.width + 6 for i in ims[:6])
        rows = [ims[:6], ims[6:14], ims[14:]]
        Wt = max(sum(i.width + 6 for i in r) for r in rows) + 8
        Ht = sum(max(i.height for i in r) + 6 for r in rows) + 8
        sheet = Image.new("RGBA", (Wt, Ht), (24, 28, 40, 255))
        y = 4
        for r in rows:
            x = 4
            for im in r:
                sheet.alpha_composite(im, (x, y))
                x += im.width + 6
            y += max(i.height for i in r) + 6
        sheet.resize((Wt * 5, Ht * 5), Image.NEAREST).save(pv / "sprites.png")
        cb = Image.open(OUT / "card.png").convert("RGBA")
        cb.alpha_composite(Image.open(OUT / "item_scarf.png").resize((48, 48), Image.NEAREST), (82, 20))
        cb.resize((cb.width * 4, cb.height * 4), Image.NEAREST).save(pv / "card.png")
        print("preview ->", pv)


if __name__ == "__main__":
    main()
