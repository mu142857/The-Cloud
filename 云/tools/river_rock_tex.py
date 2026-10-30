"""河流篇的石头质感（妮芙家第三版起用；作者 10-30：「这些石头还是缺乏质感」，标准见主对话转来的「石头质感要求」）。

不是平的多边形 + 一样粗的黑线，也不是大片棋盘格抖动：
  - 横向岩层（层厚 6~16，层线有起伏）+ 每层里错开的竖向节理，把石面分成大小不一的块；
  - 每块自己一档深浅；块的上沿受月光（右上来）一道亮边、下沿一道凹进去的暗缝；节理右边那块的左侧面背光；
  - 大面上慢慢变的明暗（右上亮、左下暗）+ 一点冷暖；
  - 上色时用小色团（2~3 像素的团块噪声）在相邻两档之间取，不用规则棋盘格；
  - 轮廓：右沿一道冷色亮边（rim）、顶面受光、左沿暗；贴地处暗（AO）；
  - 裂缝粗细不一、会分叉、少；缝里、背光处长苔；旧水位以下更深更湿，一道水渍带、几条往下淌的湿痕；偶尔垂下来的根须。
cave_texture：凿出来的屋里的石壁（更暗，凿痕，顶角和墙根暗）。
"""
from __future__ import annotations

import math

import numpy as np

import river_art as ra
from river_bank_moon_art import B, Wm, MOSS

# 外面的石头：8 档（暗的偏靛、亮的往青灰），最亮那档留给月光亮边
ROCK8 = ra.bramp(8, .07, .36, 262, 236)
RIM = B(.46, .035, 228)
CRACK = B(.045, .02, 266)
WET = [B(.06, .03, 238), B(.09, .034, 232), B(.13, .036, 226)]
# 屋里的石壁
CAVE7 = ra.bramp(7, .06, .27, 256, 238)


def vnoise(h, w, scale, rng):
    """值噪声（双线性插值），0..1。"""
    gh, gw = int(h / scale) + 3, int(w / scale) + 3
    g = rng.random((gh, gw))
    ys = np.arange(h) / scale
    xs = np.arange(w) / scale
    y0 = ys.astype(int)
    x0 = xs.astype(int)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def clusters(h, w, rng):
    """小色团：两层细噪声叠起来，量化时用它当阈值偏移（团块 2~3 像素，不规则，不是棋盘格）。"""
    return vnoise(h, w, 2.2, rng) * 0.65 + vnoise(h, w, 1.3, rng) * 0.35


def _edges(m):
    """每个像素离轮廓的距离（只数 0..4）：右、左、上、下。"""
    h, w = m.shape
    out = {}
    for name, (dy, dx) in {"r": (0, 1), "l": (0, -1), "t": (-1, 0), "b": (1, 0)}.items():
        d = np.full((h, w), 9, np.int16)
        cur = m.copy()
        for k in range(1, 6):
            sh = np.zeros_like(m)
            ys = slice(max(0, -dy * k), h - max(0, dy * k))
            yd = slice(max(0, dy * k), h - max(0, -dy * k))
            xs = slice(max(0, -dx * k), w - max(0, dx * k))
            xd = slice(max(0, dx * k), w - max(0, -dx * k))
            sh[ys, xs] = m[yd, xd]
            edge = cur & ~sh
            d[edge & (d == 9)] = k - 1
            cur = cur & sh
        out[name] = d
    return out


def strata(h, w, rng, lo=6, hi=16, amp=1.6):
    """横向岩层：返回 (每像素的层号, 每像素离本层上沿多少行, 离下一层上沿多少行)。"""
    bounds = []
    y = int(rng.integers(-4, 4))
    while y < h + hi:
        bounds.append(y)
        y += int(rng.integers(lo, hi + 1))
    wob = [np.round(ra.smooth1d(w, rng, float(rng.uniform(14, 40)), amp) - 0).astype(int) for _ in bounds]
    band = np.zeros((h, w), np.int16)
    top = np.zeros((h, w), np.int16)
    below = np.full((h, w), 99, np.int16)
    Y = np.arange(h)[:, None]
    for k, by in enumerate(bounds):
        line = by + wob[k][None, :]
        band += (Y >= line).astype(np.int16)
    for k, by in enumerate(bounds):
        line = by + wob[k][None, :]
        inb = band == (k + 1)
        top = np.where(inb, Y - line, top)
        if k + 1 < len(bounds):
            nxt = bounds[k + 1] + wob[k + 1][None, :]
            below = np.where(inb, nxt - Y, below)
    return band, top, below


def vnoise2(h, w, sy, sx, rng):
    """各向异性的值噪声：竖着拉长（sy > sx）= 竖向的柱状起伏。"""
    gh, gw = int(h / sy) + 3, int(w / sx) + 3
    g = rng.random((gh, gw))
    ys = np.arange(h) / sy
    xs = np.arange(w) / sx
    y0 = ys.astype(int)
    x0 = xs.astype(int)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def rock_texture(m, seed, pal=ROCK8, rim=RIM, ground_y=None, old_water=None, light=1.0, cracks=5, roots=4, moss=True,
                 amp=1.0, seams=0.3):
    """一整块石头上色。m = 石头的形（bool）。ground_y：贴地那一行（AO）；old_water：旧水位那一行（以下更深更湿）。
    体积：一张高度场（竖向拉长的几层噪声 = 风化出来的竖向鼓包和凹槽）按右上的月光算明暗；
    岩层只是若隐若现的横向明暗 + 断断续续的短缝（seams = 有缝的比例），不画成砖。返回 RGBA。"""
    rng = np.random.default_rng(seed)
    h, w = m.shape
    n = len(pal)
    hf = 0.72 * vnoise2(h, w, 80, 38, rng) + 0.22 * vnoise2(h, w, 30, 14, rng) + 0.06 * vnoise2(h, w, 9, 6, rng)
    gx = np.zeros_like(hf)
    gy = np.zeros_like(hf)
    gx[:, 1:-1] = hf[:, 2:] - hf[:, :-2]
    gy[1:-1, :] = hf[:-2, :] - hf[2:, :]
    shade = (gx * 1.0 + gy * 0.6) * 11.0                # 朝右上的面亮
    v = np.full((h, w), 0.42) + np.clip(shade, -0.22, 0.22) * amp
    v += 0.10 * (vnoise(h, w, 60, rng) - 0.5)
    X = np.arange(w)[None, :]
    Y = np.arange(h)[:, None]
    v += 0.12 * light * (X / w - 0.5) - 0.10 * light * (Y / h - 0.5)
    band, top, below = strata(h, w, rng, 7, 24, 2.6)
    boff = rng.uniform(-0.05, 0.05, int(band.max()) + 2)
    v += boff[band]
    brk = vnoise(h, w, 9, rng)                          # 缝断断续续：只在这张噪声高的地方有
    seam = (below == 0) & (top > 0) & (brk > 1 - seams)
    lip = (top == 0) & (brk > 0.45)
    v += np.where(lip, 0.13, 0) - np.where((below == 1) & (brk > 0.5), 0.07, 0)
    # 轮廓：右沿亮、上沿受光、左沿暗
    e = _edges(m)
    v += np.where(e["r"] <= 1, 0.22, np.where(e["r"] <= 3, 0.09, 0)) * light
    v += np.where(e["t"] == 0, 0.26, np.where(e["t"] <= 2, 0.10, 0)) * light
    v -= np.where(e["l"] <= 3, 0.13, 0)
    if ground_y is not None:
        v -= 0.26 * np.exp(-np.clip(ground_y - Y, 0, None) / 5.0)
    wet = np.zeros((h, w), bool)
    if old_water is not None:
        wet = (Y > old_water + ra.smooth1d(w, rng, 20, 1.2)[None, :]) & m
        v -= np.where(wet, 0.10, 0)
    c = clusters(h, w, rng)
    idx = np.clip(np.floor(v * (n - 1) + (c - 0.5) * 0.95 + 0.5), 0, n - 1).astype(int)
    img = np.zeros((h, w, 4), np.uint8)
    for k in range(n):
        mm = m & (idx == k)
        img[mm, :3] = pal[k]
        img[mm, 3] = 255
    sidx = np.clip(idx - 2, 0, n - 1)
    for k in range(n):
        mm = m & seam & (sidx == k)
        img[mm, :3] = pal[k]                            # 层缝：比周围暗两档（不是统一的黑线）
    # 竖向的凹槽（高度场的谷底）：深一档，像风化出来的沟
    valley = m & (np.abs(gx) < 0.004) & (hf < np.percentile(hf, 30)) & (c > 0.5)
    img[valley, :3] = pal[1]
    # 鼓包的脊（高度场沿 x 的局部最高、又朝着光）：一道断断续续的亮线，石头才「硬」
    ridge = np.zeros_like(m)
    ridge[:, 1:-1] = (hf[:, 1:-1] >= hf[:, :-2]) & (hf[:, 1:-1] > hf[:, 2:]) & (shade[:, 1:-1] > -0.02)
    ridge &= m & (c > 0.42) & (vnoise(h, w, 6, rng) > 0.35)
    ri = np.clip(idx + 2, 0, n - 2)
    for k in range(n):
        mm = ridge & (ri == k)
        img[mm, :3] = pal[k]
    rimm = m & ((e["r"] == 0) | (e["t"] == 0)) & (c > 0.28)
    img[rimm, :3] = rim
    if old_water is not None:
        wi = m & wet
        sub = img[wi, :3].astype(float)
        img[wi, :3] = np.clip(sub * 0.82 + np.array(WET[1]) * 0.18, 0, 255).astype(np.uint8)
        for x in range(w):
            ys = np.nonzero(wet[:, x])[0]
            if len(ys) == 0:
                continue
            y0 = ys[0]
            for d in range(2):
                if y0 + d < h and m[y0 + d, x] and c[y0 + d, x] > 0.3:
                    img[y0 + d, x, :3] = WET[2] if d == 0 else WET[0]
            if rng.random() < 0.05:
                for d in range(int(rng.integers(4, 14))):
                    yy = y0 - 6 + d
                    if 0 <= yy < h and m[yy, x]:
                        img[yy, x, :3] = WET[0]
            if rng.random() < 0.06 and m[min(h - 1, y0 + 4), x]:
                img[min(h - 1, y0 + 4), x, :3] = B(.34, .03, 222)
    _cracks(img, m, rng, cracks, pal)
    if moss:
        _moss(img, m, rng, top, e)
    _roots(img, m, rng, roots, top)
    return img


def _cracks(img, m, rng, k, pal):
    """裂缝：从上面某处往下爬，开头粗（2）、越往下越细，偶尔分一叉；缝右唇亮一档、缝里偶尔一点苔。"""
    h, w = m.shape
    xs = np.nonzero(m.any(0))[0]
    if len(xs) == 0:
        return
    for _ in range(k):
        x = float(rng.uniform(xs[0] + 8, xs[-1] - 8))
        col = np.nonzero(m[:, int(x)])[0]
        if len(col) == 0:
            continue
        y = float(col[0] + rng.uniform(2, max(3, (col[-1] - col[0]) * 0.5)))
        length = int(rng.integers(14, 46))
        stack = [(x, y, length, 2)]
        while stack:
            x, y, L, wd = stack.pop()
            for s in range(L):
                xi, yi = int(round(x)), int(round(y))
                if not (0 <= yi < h and 1 <= xi < w - 2 and m[yi, xi]):
                    break
                width = wd if s < L * 0.35 else 1
                for d in range(width):
                    if m[yi, xi + d]:
                        img[yi, xi + d, :3] = CRACK
                if m[yi, xi + width]:
                    img[yi, xi + width, :3] = pal[min(len(pal) - 1, 5)]
                if rng.random() < 0.06 and m[yi, xi - 1]:
                    img[yi, xi - 1, :3] = MOSS[0]
                x += rng.uniform(-0.8, 0.8)
                y += 1
                if rng.random() < 0.05 and L - s > 8:
                    stack.append((x + rng.choice([-1, 1]), y, int((L - s) * 0.45), 1))


def _moss(img, m, rng, top, e):
    """苔：长在层的上沿（受光的平台上一小撮）和背光的左沿，一团一团的，不是一条线。"""
    h, w = m.shape
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if not m[y, x]:
                continue
            p = 0.0
            if top[y, x] == 0:
                p = 0.05
            if e["l"][y, x] <= 1:
                p = max(p, 0.03)
            if e["t"][y, x] == 0:
                p = max(p, 0.25)
            if rng.random() < p:
                n = int(rng.integers(1, 5))
                for k in range(n):
                    yy = y - (1 if k == 0 and e["t"][y, x] == 0 else 0)
                    xx = x + k - n // 2
                    if 0 <= xx < w and 0 <= yy < h:
                        img[yy, xx, :3] = MOSS[min(2, k % 3)]
                        img[yy, xx, 3] = 255


def _roots(img, m, rng, k, top):
    """根须：从某层的上沿垂下来，细，长短不一，末端一点。"""
    h, w = m.shape
    ys, xs = np.nonzero(m & (top == 0))
    if len(ys) == 0:
        return
    for _ in range(k):
        i = int(rng.integers(0, len(ys)))
        x, y = int(xs[i]), int(ys[i]) + 1
        L = int(rng.integers(5, 18))
        for d in range(L):
            yy = y + d
            xx = x + (1 if d > L * 0.6 and (d % 3 == 0) else 0)
            if 0 <= yy < h and 0 <= xx < w and m[yy, xx]:
                img[yy, xx, :3] = B(.12, .025, 70) if d % 4 else B(.2, .03, 80)


def cave_texture(m, seed, pal=CAVE7, floor_rows=None):
    """凿出来的屋里的石壁：比外面暗；岩层很淡；凿痕（短斜的一道暗一道亮）；顶角、墙根、两侧暗（AO）。返回 RGBA。"""
    rng = np.random.default_rng(seed)
    h, w = m.shape
    n = len(pal)
    band, top, below = strata(h, w, rng, 9, 18, 1.0)
    v = np.full((h, w), 0.48)
    v += 0.10 * (vnoise(h, w, 30, rng) - 0.5) + 0.03 * (vnoise(h, w, 8, rng) - 0.5)
    hf = 0.7 * vnoise2(h, w, 30, 22, rng) + 0.3 * vnoise2(h, w, 10, 8, rng)     # 凿出来的面：圆鼓鼓的大起伏，没有层线
    gx = np.zeros_like(hf)
    gy = np.zeros_like(hf)
    gx[:, 1:-1] = hf[:, 2:] - hf[:, :-2]
    gy[1:-1, :] = hf[:-2, :] - hf[2:, :]
    v += np.clip((gx * 0.4 + gy * 0.8) * 8.0, -0.08, 0.08)
    e = _edges(m)
    v -= np.where(e["t"] <= 1, 0.24, np.where(e["t"] <= 4, 0.10, 0))      # 顶上暗
    v -= np.where(np.minimum(e["l"], e["r"]) <= 2, 0.14, 0)
    v -= np.where(e["b"] <= 1, 0.06, 0)
    c = clusters(h, w, rng)
    idx = np.clip(np.floor(v * (n - 1) + (c - 0.5) * 0.6 + 0.5), 0, n - 1).astype(int)
    img = np.zeros((h, w, 4), np.uint8)
    for k in range(n):
        mm = m & (idx == k)
        img[mm, :3] = pal[k]
        img[mm, 3] = 255
    # 凿痕：一道 3 像素的斜线（暗）+ 下面一道亮，朝同一个方向（凿子从左上往右下）
    ys, xs = np.nonzero(m)
    for _ in range(int(len(ys) / 150)):
        i = int(rng.integers(0, len(ys)))
        y, x = int(ys[i]), int(xs[i])
        for d in range(3):
            yy, xx = y + d // 2, x + d
            if 0 <= yy < h - 1 and 0 <= xx < w and m[yy, xx] and m[yy + 1, xx]:
                k = int(idx[yy, xx])
                img[yy, xx, :3] = pal[max(0, k - 1)]
                img[yy + 1, xx, :3] = pal[min(n - 1, k + 1)]
    return img


def warm_spill(img, mask, lamps, rng, warm=None, strength=1.0):
    """灯光落到屋里（已经画了的像素往暖推）：离灯越近越暖，分 3 档，档边用小色团（不是棋盘格），很快衰减。
    lamps = [(x, y, r)]。"""
    from river_bank_moon_art import WARM, mixc, to_lab
    warm = warm or WARM
    h, w = mask.shape
    c = vnoise(h, w, 3.5, rng) * 0.7 + clusters(h, w, rng) * 0.3     # 暖光的档边：大一点的团，不撒点
    cache = {}
    for (lx, ly, r) in lamps:
        y0, y1 = max(0, int(ly - r)), min(h, int(ly + r * 1.2))
        x0, x1 = max(0, int(lx - r * 1.3)), min(w, int(lx + r * 1.3))
        for y in range(y0, y1):
            for x in range(x0, x1):
                if not mask[y, x] or img[y, x, 3] == 0:
                    continue
                d = math.hypot((x - lx) / 1.3, (y - ly) * (1.0 if y >= ly else 1.4)) / r
                if d >= 1:
                    continue
                t = (1 - d) ** 1.8 * strength
                q = int(np.clip(math.floor(t * 4.6 + (c[y, x] - 0.5) * 0.55), 0, 3))
                if q <= 0:
                    continue
                col = tuple(int(v) for v in img[y, x, :3])
                key = (col, q)
                if key not in cache:
                    L = to_lab(col)[0]
                    tgt = Wm(min(0.6, L + 0.08 + 0.03 * q), 0.07, 64)
                    cache[key] = mixc(col, tgt, (0.0, 0.22, 0.38, 0.52)[q])
                img[y, x, :3] = cache[key]
