"""第三章 · 云层星的芦苇地 reed_field（10-31 作者：「主题色是浅黄色和淡蓝色，主角走过去芦苇全都弯下去，会有鸟飞起来，
相当唯美，美好且明亮的场景」）。结局一、结局二原来的两张草地（yard、east_meadow）都改成这一张；以后在它上面加「草原小镇」。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/reed_field_art.py [--preview 目录]

白天，全游戏最亮的一屏：淡蓝的天、左上一轮白太阳、地平线上一大片积云（云层星）、浅黄的芦苇海、一片映着天的浅湖（太阳在湖里一道碎光）。
晨走的那一层（main + 会动的芦苇）压低明度、降饱和（土金 / 卡其），保证晨的淡紫白头发和砖红斗篷一眼看得见（作者的「亮主角暗背景」）。

横向 1920，从左到右：
  0–690     芦苇丛，小路穿过去（惊鸟 1：x 400）
  690–1090  小路沿着一片浅水走，水在路的前面（惊鸟 2：x 905）
  1110–1490 平缓、空的一段：矮草地 + 几处小花，芦苇稀，远处的中景也空着 —— 留给以后的「草原小镇」（room.json 的 _note）
  1510–1920 又是芦苇丛（惊鸟 3：x 1650）

图层（room.json，从后往前）：
  sky.png        480×270  scroll 0     天 + 太阳（固定在屏幕上）
  wisps.png      960×56   scroll 0.03  高处几缕薄云（tile，drift 慢慢往左漂）
  clouds.png     960×124  scroll 0.06  地平线上的积云（tile）
  far.png        960×38   scroll 0.2   远处的芦苇海（tile，sway shader：随风轻摆 1 像素）
  lake.png       960×50   scroll 0.35  浅湖（tile）
  sunpath.png    480×50   scroll 0     太阳在湖里的碎光（water shader：每行晃、一会儿亮一会儿没）
  glints.png     960×50   scroll 0.35  湖面别处零星的亮纹（water shader）
  mid.png        1300×112 scroll 0.55  中景：湖里一簇簇芦苇岛 + 倒影（sway shader）
  main.png       1920×270 scroll 1     后面的芦苇根丛、踩出来的小路、路前面的芦苇根丛 / 浅水 / 矮草地
  会动的芦苇（scripts/reed_field.gd 画，不是图层）：
    reeds.png + reeds.json   每种芦苇在 31 个弯曲角度下各画一帧（1 像素的秆四邻接画，弯到哪一帧都不断、不只角碰角），
                             reeds.json 里还有每一根放在哪（四排：r0 后排高的、r1 路后、r2 路前、f 前景 scroll 1.25）
    birds.png + birds.json   鸟：四种远近大小 × 扇翅三帧（100ms）+ 落在芦苇顶上的两帧

所有随机固定 seed；除了 sunpath / glints（water shader 用）以外 alpha 只有 0/255。不碰 art/手改清单.json 里的文件。
画完自己扫一遍：只有对角相连、孤立单像素、细线缺口、虚线（tools/dotted_line_check.py 的规则）、地面直角台阶。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "reed_field"
W, H = 1920, 270

# 晨脚底那一行（折线，平缓）。1110–1490 是平的（草原小镇的地）
GROUND = [[0, 228], [180, 227], [420, 227], [600, 226], [760, 226], [1000, 225], [1110, 224], [1490, 224], [1640, 225],
          [1800, 226], [1920, 227]]
WALK = [24, 1896]
WATER = (690, 1090)          # 路前面是浅水的一段
TOWN = (1110, 1490)          # 留给草原小镇
SPOTS = [400, 905, 1650]     # 惊鸟的地方（房间 x）
SUN = (148, 40)              # 太阳（屏幕坐标，天是钉在屏幕上的）


def hexc(h, a=255):
    return np.array([int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), a], np.uint8)


def mix(a, b, k):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    out = a * (1 - k) + b * k
    out[3] = 255
    return np.round(out).astype(np.uint8)


# ---------------------------------------------------------------- 调色板
SKY = ["#86bde0", "#93c4e4", "#a1cce8", "#b0d5eb", "#bfdded", "#cde4ee", "#d9eaee", "#e3eeec"]
SKY_Y = [0, 30, 58, 82, 104, 122, 136, 146]           # 每一档从哪一行开始
SUN_CORE, SUN_WARM = "#fffdf4", "#fff3cf"
CLOUD = ["#c6d7e3", "#d6e3eb", "#e7eef1", "#f6f8f4", "#fffcef"]     # 最暗（云底）→ 受光的顶
WISP = ["#e9f2f3", "#f5f9f6"]
FAR = {"lit": "#f3e6bc", "plume": "#e8d6a3", "body": "#dccc9b", "low": "#d0c7a2", "deep": "#c6c4a8"}
LAKE = ["#d8ecef", "#cbe5ed", "#bedeea", "#b2d6e6", "#a8cfe2"]       # 近地平线（亮）→ 近处（深一点：映的是高处的天）
LAKE_REFL = ["#e6e2c2", "#dbdcc0"]                                    # 远处芦苇海的倒影
GLINT = ["#fbfdf8", "#eaf5f6"]
MIDR = {"lit": "#efd99c", "plume": "#e2c685", "shade": "#d2b273", "stem": "#c9b07a", "stem_d": "#b9a271",
        "base": "#b4a573", "base_d": "#a69a70", "refl": "#c4d2c8", "refl_d": "#b4c8c6"}
# 主层（晨那一层）：压暗、降饱和
MAIN = {"tip": "#a69a6a", "mass": "#958b5e", "mass_d": "#857d56", "mass_dd": "#77714f", "shadow": "#6c6849",
        "path": "#d3c39c", "path_lit": "#ddcfab", "path_edge": "#bfae88", "pebble": "#c6b894", "pebble_d": "#ad9c79",
        "ftip": "#968b5f", "fmass": "#857c55", "fmass_d": "#776f4d", "fmass_dd": "#6a6446",
        "mud": "#a8977a", "mud_d": "#958770",
        "w0": "#a9c6c9", "w1": "#b7d8e6", "w2": "#c6e1ec", "w3": "#a6cde0", "w_lit": "#d7ecf2",
        "grass_t": "#c2b680", "grass": "#b2a774", "grass_d": "#a1976a", "grass_dd": "#90885f",
        "fl_blue": "#cfe0f0", "fl_cream": "#f4edcf", "fl_stem": "#8f8a5f"}
# 会动的芦苇：每排一套色（stem 下 → 上、plume 暗 → 亮、leaf）
REED_PAL = {
    "r0": {"stem": ["#8f8460", "#9c8f65", "#a89a6c"], "plume": ["#b29c6c", "#c4ad7a", "#d4bf8e"], "leaf": ["#8d855f", "#9a9067"]},
    "r1": {"stem": ["#867b56", "#94875d", "#a09265"], "plume": ["#a99263", "#bba26f", "#cbb382"], "leaf": ["#857d57", "#928960"]},
    "r2": {"stem": ["#766d4d", "#827853", "#8c8159"], "plume": ["#9a8459", "#ab9463", "#baa372"], "leaf": ["#736d4c", "#7f7853"]},
    "f": {"stem": ["#605b43", "#6a6447", "#736c4c"], "plume": ["#7f704f", "#8f7e58", "#9d8c63"], "leaf": ["#5f5b42", "#6a6548"]},
}
# 每一帧的弯曲角度（度，正 = 往右弯）。0 附近密（风里轻摆一档只挪一两像素），越弯越疏
ANGLES_POS = [0, 2, 4, 7, 10, 14, 18, 23, 28, 34, 40, 47, 54, 62, 70, 78]
ANGLES = [-a for a in reversed(ANGLES_POS[1:])] + ANGLES_POS
BIRD = {"wing": "#5c5147", "body": "#6d6052", "tail": "#887a68"}


# ---------------------------------------------------------------- 小工具
def ground(x):
    xs = [p[0] for p in GROUND]
    ys = [p[1] for p in GROUND]
    return int(round(float(np.interp(x, xs, ys))))


def knots(n, step, rng, amp=1.0, period=None):
    """平滑噪声：每 step 像素一个随机值，中间 smoothstep 插值；period 给了就首尾相接（tile 层用）"""
    m = int(math.ceil(n / step)) + 2
    v = rng.uniform(-amp, amp, m)
    if period:
        m = period // step
        v = rng.uniform(-amp, amp, m)
    out = np.zeros(n)
    for x in range(n):
        f = x / step
        i = int(math.floor(f))
        t = f - i
        t = t * t * (3 - 2 * t)
        a = v[i % len(v)] if period else v[min(i, len(v) - 1)]
        b = v[(i + 1) % len(v)] if period else v[min(i + 1, len(v) - 1)]
        out[x] = a + (b - a) * t
    return out


def sstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def blank(w, h):
    return np.zeros((h, w, 4), np.uint8)


def put(img, x, y, c):
    h, w = img.shape[:2]
    if 0 <= x < w and 0 <= y < h:
        img[y, x] = c


def line4(p0, p1):
    """两点之间的四邻接线（错一格时先竖着走、再横着走：每一格都和上一格有一条边贴着）"""
    x0, y0 = p0
    x1, y1 = p1
    pts = [(x0, y0)]
    n = max(abs(x1 - x0), abs(y1 - y0))
    for i in range(1, n + 1):
        x = int(round(x0 + (x1 - x0) * i / n))
        y = int(round(y0 + (y1 - y0) * i / n))
        px, py = pts[-1]
        if x != px and y != py:
            pts.append((px, y))
        if (x, y) != pts[-1]:
            pts.append((x, y))
    return pts


def path4(fpts):
    """浮点折线 → 四邻接像素串（相邻两点错一格时，补离真曲线近的那一格）"""
    out = []
    for i, (fx, fy) in enumerate(fpts):
        p = (int(round(fx)), int(round(fy)))
        if not out:
            out.append(p)
            continue
        q = out[-1]
        if p == q:
            continue
        if abs(p[0] - q[0]) > 1 or abs(p[1] - q[1]) > 1:
            for r in line4(q, p)[1:]:
                out.append(r)
            continue
        if p[0] != q[0] and p[1] != q[1]:
            a, b = (q[0], p[1]), (p[0], q[1])
            mx, my = (fpts[i - 1][0] + fx) / 2, (fpts[i - 1][1] + fy) / 2
            da = (a[0] - mx) ** 2 + (a[1] - my) ** 2
            db = (b[0] - mx) ** 2 + (b[1] - my) ** 2
            out.append(a if da <= db else b)
        out.append(p)
    return out


def fill_disc(img, cx, cy, r, c):
    h, w = img.shape[:2]
    y0, y1 = max(0, int(cy - r - 1)), min(h, int(cy + r + 2))
    x0, x1 = max(0, int(cx - r - 1)), min(w, int(cx + r + 2))
    if y0 >= y1 or x0 >= x1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    m = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    img[y0:y1, x0:x1][m] = c


# ---------------------------------------------------------------- 清理 + 检查
def corner_fix(img, max_iter=6, keep_alpha_zero=True):
    """只有对角相连的地方补一格（作者在河岸的做法）：同一种颜色（或同是不透明）两格只在角上碰，就把旁边一格涂成它。
    不透明的层只看颜色；透明的层先看 alpha，再看颜色。"""
    for _ in range(max_iter):
        n = 0
        h, w = img.shape[:2]
        a = img[..., 3] > 0
        key = (img[..., 0].astype(np.int64) << 24) | (img[..., 1].astype(np.int64) << 16) | (img[..., 2].astype(np.int64) << 8) | img[..., 3]
        key = np.where(a, key, -1)
        for y in range(h - 1):
            for x in range(w - 1):
                k00, k01, k10, k11 = key[y, x], key[y, x + 1], key[y + 1, x], key[y + 1, x + 1]
                if k00 == k11 and k00 != -1 and k01 != k00 and k10 != k00:
                    # 透明里的对角：先补成同色（不透明）；不透明里的对角：补上
                    tgt = (y, x + 1) if (k01 == -1) <= (k10 == -1) else (y + 1, x)
                    if k01 != -1 and k10 == -1:
                        tgt = (y, x + 1)
                    img[tgt] = img[y, x]
                    key[tgt] = k00
                    n += 1
                elif k01 == k10 and k01 != -1 and k00 != k01 and k11 != k01:
                    tgt = (y, x) if k00 != -1 or k11 == -1 else (y + 1, x + 1)
                    img[tgt] = img[y, x + 1]
                    key[tgt] = k01
                    n += 1
        if n == 0:
            return


def speck_fix(img):
    """孤立的单像素（四邻都不是它的颜色）：并进旁边最多的颜色；四周全透明的不透明单点 → 删掉（悬空的碎点）。"""
    h, w = img.shape[:2]
    for _ in range(3):
        n = 0
        src = img
        for y in range(h):
            for x in range(w):
                if src[y, x, 3] == 0:
                    continue
                c = tuple(src[y, x])
                nb = []
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < w and 0 <= yy < h:
                        nb.append(tuple(src[yy, xx]))
                if not nb or c in nb:
                    continue
                opaque = [q for q in nb if q[3] > 0]
                if not opaque:
                    # 四邻都透明：看看对角有没有东西（有就是对角相连，交给 corner_fix），没有就是悬空点
                    diag = [src[y + dy, x + dx] for dx, dy in ((1, 1), (-1, -1), (1, -1), (-1, 1))
                            if 0 <= x + dx < w and 0 <= y + dy < h and src[y + dy, x + dx, 3] > 0]
                    if not diag:
                        img[y, x] = 0
                        n += 1
                    continue
                best = max(set(opaque), key=opaque.count)
                img[y, x] = best
                n += 1
        if n == 0:
            return


def alpha_fix(img):
    """精灵（透明底）：轮廓上只在角上碰的两格（颜色不同也算）补一格；一格宽的缺口（上下或左右都有东西、旁边全空）补上。
    补的颜色取旁边那格。"""
    h, w = img.shape[:2]
    for _ in range(4):
        a = img[..., 3] > 0
        n = 0
        for y in range(h - 1):
            for x in range(w - 1):
                for (p, q, r1, r2) in (((y, x), (y + 1, x + 1), (y, x + 1), (y + 1, x)),
                                       ((y, x + 1), (y + 1, x), (y, x), (y + 1, x + 1))):
                    if a[p] and a[q] and not a[r1] and not a[r2]:
                        # 补在旁边不透明格多的那一边（拐角更圆）
                        def cnt(t):
                            yy, xx = t
                            return int(a[max(0, yy - 1):yy + 2, max(0, xx - 1):xx + 2].sum())
                        t = r1 if cnt(r1) >= cnt(r2) else r2
                        img[t] = img[p] if t[0] == p[0] or t[1] == p[1] else img[q]
                        a[t] = True
                        n += 1
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if a[y, x]:
                    continue
                if a[y - 1, x] and a[y + 1, x] and not a[y, x - 1] and not a[y, x + 1]:
                    img[y, x] = img[y - 1, x]
                    a[y, x] = True
                    n += 1
                elif a[y, x - 1] and a[y, x + 1] and not a[y - 1, x] and not a[y + 1, x]:
                    img[y, x] = img[y, x - 1]
                    a[y, x] = True
                    n += 1
        if n == 0:
            return


def scan(name, img, alpha_only=False):
    """报告：只有对角相连（同色 / 同是不透明）、孤立单像素、细线缺口（一格透明，上下或左右都是一像素粗的线）"""
    h, w = img.shape[:2]
    a = img[..., 3] > 0
    key = (img[..., 0].astype(np.int64) << 24) | (img[..., 1].astype(np.int64) << 16) | (img[..., 2].astype(np.int64) << 8) | img[..., 3]
    key = np.where(a, key, -1)
    diag, iso, gap = [], [], []
    for y in range(h - 1):
        for x in range(w - 1):
            if alpha_only:
                if a[y, x] and a[y + 1, x + 1] and not a[y, x + 1] and not a[y + 1, x]:
                    diag.append((x, y))
                if a[y, x + 1] and a[y + 1, x] and not a[y, x] and not a[y + 1, x + 1]:
                    diag.append((x, y))
            else:
                k00, k01, k10, k11 = key[y, x], key[y, x + 1], key[y + 1, x], key[y + 1, x + 1]
                if (k00 == k11 and k00 != -1 and k01 != k00 and k10 != k00) or (k01 == k10 and k01 != -1 and k00 != k01 and k11 != k01):
                    diag.append((x, y))
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if a[y, x]:
                k = key[y, x]
                if alpha_only:
                    if not (a[y - 1, x] or a[y + 1, x] or a[y, x - 1] or a[y, x + 1]):
                        iso.append((x, y))
                elif k not in (key[y - 1, x], key[y + 1, x], key[y, x - 1], key[y, x + 1]):
                    iso.append((x, y))
            else:
                if a[y - 1, x] and a[y + 1, x] and not a[y, x - 1] and not a[y, x + 1] \
                        and not a[y - 1, x - 1] and not a[y - 1, x + 1] and not a[y + 1, x - 1] and not a[y + 1, x + 1]:
                    gap.append((x, y))
                if a[y, x - 1] and a[y, x + 1] and not a[y - 1, x] and not a[y + 1, x] \
                        and not a[y - 1, x - 1] and not a[y + 1, x - 1] and not a[y - 1, x + 1] and not a[y + 1, x + 1]:
                    gap.append((x, y))
    print(f"  {name}: 只有对角相连 {len(diag)}，孤立单像素 {len(iso)}，细线缺口 {len(gap)}", (diag + iso + gap)[:8])
    return len(diag) + len(iso) + len(gap)


def scan_quiet(img):
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        return scan("", img, alpha_only=True)


def dashes(name, img):
    """虚线：一行里一像素粗的短段（1–4 长）按同一个周期重复 ≥4 次（tools/dotted_line_check.py 的意思，简化）"""
    h, w = img.shape[:2]
    key = (img[..., 0].astype(np.int64) << 16) | (img[..., 1].astype(np.int64) << 8) | img[..., 2]
    key = np.where(img[..., 3] > 0, key, -1)
    hits = []
    for y in range(1, h - 1):
        row = key[y]
        thin = (row != key[y - 1]) & (row != key[y + 1]) & (row != -1)
        x = 0
        runs = []
        while x < w:
            if thin[x]:
                c = row[x]
                s = x
                while x < w and thin[x] and row[x] == c:
                    x += 1
                if x - s <= 4:
                    runs.append((s, x - s, c))
            else:
                x += 1
        for i in range(len(runs) - 3):
            a, b, c2, d = runs[i:i + 4]
            if a[2] == b[2] == c2[2] == d[2]:
                p1, p2, p3 = b[0] - a[0], c2[0] - b[0], d[0] - c2[0]
                if p1 == p2 == p3 and 2 <= p1 <= 8:
                    hits.append((a[0], y))
    print(f"  {name}: 虚线嫌疑 {len(hits)}", hits[:6])
    return len(hits)


# ---------------------------------------------------------------- 天
def draw_sky():
    rng = np.random.default_rng(11)
    img = blank(480, H)
    wob = [knots(480, 90, rng, 1.6) for _ in SKY_Y]
    for x in range(480):
        for y in range(H):
            k = 0
            for i, y0 in enumerate(SKY_Y):
                if y >= y0 + (round(wob[i][x]) if i else 0):
                    k = i
            img[y, x] = hexc(SKY[k])
    # 太阳：白芯 + 几圈越来越淡的暖光（一圈一档，平涂）
    sx, sy = SUN
    rings = [(54, 0.07), (39, 0.15), (28, 0.27), (19, 0.42), (12.5, 0.62), (8.5, 0.85)]
    warm = hexc(SUN_WARM)
    base = img.copy()
    for r, k in rings:
        yy, xx = np.mgrid[0:H, 0:480]
        m = (xx - sx) ** 2 + (yy - sy) ** 2 <= r * r
        for y, x in zip(*np.nonzero(m)):
            img[y, x] = mix(base[y, x], warm, k)
    fill_disc(img, sx, sy, 6.2, hexc(SUN_CORE))
    corner_fix(img)
    speck_fix(img)
    return img


def draw_wisps():
    """高处的几缕薄云：扁长的一片（两头尖、中间鼓），底边几乎平、顶边起伏，受光的上半亮一档。不画成线。"""
    rng = np.random.default_rng(23)
    w, h = 960, 56
    img = blank(w, h)
    for cx, cy, L, th in [(120, 22, 170, 7), (330, 40, 100, 5), (540, 16, 220, 8), (720, 44, 130, 5), (880, 28, 120, 6)]:
        topn = knots(L + 1, 18, rng, 1.6)
        botn = knots(L + 1, 40, rng, 0.8)
        for i in range(L + 1):
            u = i / L * 2 - 1
            t = th * (1 - u * u) ** 0.8 + topn[i] * (1 - abs(u))
            b = th * 0.25 * (1 - u * u) + botn[i] * (1 - abs(u))
            top, bot = int(round(cy - t)), int(round(cy + b))
            if bot < top:
                continue
            for y in range(top, bot + 1):
                if 0 <= y < h:
                    img[y, (cx - L // 2 + i) % w] = hexc(WISP[1] if y < (top + bot) / 2 - 0.5 else WISP[0])
    corner_fix(img)
    speck_fix(img)
    return img


def draw_clouds():
    """地平线上的积云（云层星）：一团团圆叠起来，按「球面法线 · 左上来的光」分五档（等亮线切出来的块，不是随机切面）。
    底边平、在湖和芦苇海后面。左右无缝（960）。"""
    rng = np.random.default_rng(7)
    w, h = 960, 124
    base_y = 118
    circles = []
    # (中心 x, 宽, 高)：一座高的、两座中等、一长条矮的
    for mx, mw, mh in [(90, 230, 88), (330, 170, 52), (560, 260, 104), (800, 190, 66), (960 - 20, 90, 34)]:
        n = max(4, mw // 22)
        for i in range(n):
            u = (i + 0.5) / n * 2 - 1
            prof = (1 - u * u) ** 0.7
            r = 10 + mh * 0.45 * prof * rng.uniform(0.8, 1.1)
            cx = mx + u * mw / 2 + rng.uniform(-6, 6)
            cy = base_y - r * 0.55 - mh * 0.25 * prof
            circles.append((cx, cy, r))
            # 顶上的小鼓包
            if prof > 0.45 and rng.random() < 0.8:
                r2 = r * rng.uniform(0.45, 0.65)
                circles.append((cx + rng.uniform(-r * 0.4, r * 0.4), cy - r * 0.62, r2))
    # 每一团顶上再冒几个小鼓包，轮廓不那么圆
    extra = []
    for cx, cy, r in circles:
        if r > 16:
            for k in range(int(rng.integers(1, 4))):
                ang = rng.uniform(-2.6, -0.5)
                extra.append((cx + math.cos(ang) * r * 0.85, cy + math.sin(ang) * r * 0.85, r * rng.uniform(0.18, 0.32)))
    circles += extra
    L = np.array([-0.55, -0.62, 0.56])
    L = L / np.linalg.norm(L)
    cols = [hexc(c) for c in CLOUD]
    m = np.zeros((h, w), bool)
    shade = np.zeros((h, w))
    yy, xx = np.mgrid[0:h, 0:w]
    # 先画大的、后画顶上的小鼓包（压在前面），一团团菜花似的叠出来
    for cx, cy, r in sorted(circles, key=lambda c: -c[2]):
        for off in (-w, 0, w):
            dx = xx - (cx + off)
            dy = yy - cy
            cm = (dx * dx + dy * dy <= r * r) & (yy <= base_y)
            if not cm.any():
                continue
            nx, ny = dx / r, dy / r
            nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
            b = nx * L[0] + ny * L[1] + nz * L[2]
            shade[cm] = b[cm]
            m |= cm
    # 云底：最下面几行压暗（湖面反上来的冷光）
    lo = np.clip((yy - (base_y - 16)) / 16.0, 0, 1)
    # 等亮线不要太圆：加一点拉长的笔触扰动
    nz = np.zeros((h, w))
    for k in range(3):
        fx, fy, ph = rng.uniform(0.02, 0.06), rng.uniform(0.05, 0.12), rng.uniform(0, 6.28, 2)
        nz += np.sin(xx * fx * (2 * math.pi / (fx * w)) * round(fx * w / (2 * math.pi)) + ph[0]) * np.sin(yy * fy + ph[1]) / (k + 1)
    b = shade - lo * 0.45 + nz * 0.06
    lv = np.digitize(b, [-0.05, 0.3, 0.58, 0.82])
    img = blank(w, h)
    for i, c in enumerate(cols):
        img[m & (lv == i)] = c
    corner_fix(img)
    speck_fix(img)
    corner_fix(img, max_iter=12)
    # 剩下的（轮廓上一格受光的边只在角上碰）：把透明的那一格补成它，轮廓多长一格
    h2, w2 = img.shape[:2]
    for y in range(h2 - 1):
        for x in range(w2 - 1):
            q = img[y:y + 2, x:x + 2]
            if q[0, 1, 3] and q[1, 0, 3] and (q[0, 1] == q[1, 0]).all() and (q[0, 0] != q[0, 1]).any() and (q[1, 1] != q[0, 1]).any():
                if q[0, 0, 3] == 0:
                    q[0, 0] = q[0, 1]
                elif q[1, 1, 3] == 0:
                    q[1, 1] = q[0, 1]
            if q[0, 0, 3] and q[1, 1, 3] and (q[0, 0] == q[1, 1]).all() and (q[0, 1] != q[0, 0]).any() and (q[1, 0] != q[0, 0]).any():
                if q[0, 1, 3] == 0:
                    q[0, 1] = q[0, 0]
                elif q[1, 0, 3] == 0:
                    q[1, 0] = q[0, 0]
    return img


def draw_far():
    """远处的芦苇海：一条浅黄的带，上沿是一个个小穗子鼓起来（往右偏一点，风往右吹），下面是秆的竖纹，越往下越灰蓝（远）。
    最下面一行是根（sway shader 按离最下面多高摆）。"""
    rng = np.random.default_rng(31)
    w, h = 960, 38
    img = blank(w, h)
    top = 14 + knots(w, 120, rng, 2.5, period=960) + knots(w, 30, rng, 1.0, period=960)
    for x in range(w):
        t = int(round(top[x]))
        for y in range(t, h):
            d = y - t
            c = FAR["plume"] if d < 4 else FAR["body"] if d < 12 else FAR["low"] if d < 20 else FAR["deep"]
            img[y, x] = hexc(c)
    # 穗子：上沿冒出来的小椭圆，受光的上半亮
    xs = np.sort(rng.choice(np.arange(w), 150, replace=False))
    for x0 in xs:
        t = top[x0]
        pw, ph = rng.uniform(1.6, 3.2), rng.uniform(1.8, 3.4)
        cy = t - ph * 0.6
        for y in range(int(cy - ph - 1), int(t) + 2):
            for x in range(int(x0 - pw - 2), int(x0 + pw + 3)):
                u = (x - x0 - (t - y) * 0.35) / pw
                v = (y - cy) / ph
                if u * u + v * v <= 1.0 and 0 <= y < h:
                    img[y, x % w] = hexc(FAR["lit"] if v < 0 else FAR["plume"])
    # 竖纹：一截截秆的影子（随机位置、长短不一，不等距）
    for _ in range(260):
        x = int(rng.integers(0, w))
        y0 = int(top[x]) + int(rng.integers(5, 14))
        L = int(rng.integers(3, 9))
        c = hexc(FAR["low"] if y0 < top[x] + 10 else FAR["deep"])
        for y in range(y0, min(h, y0 + L)):
            img[y, x] = c
    corner_fix(img)
    speck_fix(img)
    return img


def draw_lake():
    """浅湖：最上面是远处芦苇海的倒影（浅黄、波浪边），往下按映的天从亮到深分几档；档和档之间是一条条长的、两头尖的波纹。"""
    rng = np.random.default_rng(41)
    w, h = 960, 50
    img = blank(w, h)
    cuts = [5, 13, 23, 35]
    wob = [knots(w, 70, rng, 1.4, period=960) for _ in cuts]
    refl = 3 + knots(w, 40, rng, 1.6, period=960)
    for x in range(w):
        for y in range(h):
            k = 0
            for i, c0 in enumerate(cuts):
                if y >= c0 + round(wob[i][x]):
                    k = i + 1
            img[y, x] = hexc(LAKE[k])
        r = int(round(refl[x]))
        for y in range(0, max(1, r)):
            img[y, x] = hexc(LAKE_REFL[0] if y < r - 1 else LAKE_REFL[1])
    # 波纹：两头尖的长条，颜色取上一档（亮一档），长短不一
    for _ in range(70):
        y = int(rng.integers(6, h - 2))
        x0 = int(rng.integers(0, w))
        L = int(rng.integers(10, 46))
        here = img[y, x0 % w].copy()
        k = [i for i, c in enumerate(LAKE) if (hexc(c) == here).all()]
        if not k or k[0] == 0:
            continue
        c = hexc(LAKE[k[0] - 1])
        for i in range(L):
            u = i / (L - 1) * 2 - 1
            if abs(u) > 0.92 and rng.random() < 0.5:
                continue
            img[y, (x0 + i) % w] = c
            if abs(u) < 0.45 and L > 24:
                img[y + 1, (x0 + i) % w] = c
    corner_fix(img)
    speck_fix(img)
    return img


def draw_glints(w, h, seed, n, center=None, spread=60):
    """湖面的亮纹：长短不一的横段（2–9 像素），随机散开不等距。center 给了 = 太阳底下那一道：越靠近太阳的 x 越密、越长。
    water shader（palette_mode false）让它每行晃、一会儿有一会儿没。"""
    rng = np.random.default_rng(seed)
    img = blank(w, h)
    placed = 0
    tries = 0
    while placed < n and tries < n * 20:
        tries += 1
        y = int(rng.integers(1, h - 1))
        if center is not None:
            x = int(round(rng.normal(center, spread * (0.45 + y / h))))
            L = int(rng.integers(2, 10 if abs(x - center) < spread * 0.5 else 6))
        else:
            x = int(rng.integers(0, w))
            L = int(rng.integers(2, 6))
        if x < 0 or x + L >= w:
            continue
        if img[max(0, y - 1):y + 2, max(0, x - 2):x + L + 2, 3].any():
            continue
        c = hexc(GLINT[0] if (center is not None and abs(x - center) < spread * 0.6) or rng.random() < 0.3 else GLINT[1])
        img[y, x:x + L] = c
        placed += 1
    return img


# ---------------------------------------------------------------- 静止的小芦苇（中景）
def mini_reed(img, x, root, L, lean, pal, rng, plume=True):
    """中景的一根：1 像素的秆（四邻接，微微往右偏）+ 顶上一个小穗"""
    pts = []
    for i in range(L + 1):
        u = i / L
        pts.append((x + lean * u ** 1.6, root - i))
    px = path4(pts)
    for j, (a, b) in enumerate(px):
        c = pal["stem_d"] if j < len(px) * 0.4 else pal["stem"]
        put(img, a, b, hexc(c))
    if plume:
        tx, ty = px[-1]
        ph = int(rng.integers(3, 6))
        for k in range(ph):
            yy = ty + k - 1
            ww = 1 if k in (0, ph - 1) else 2
            for d in range(ww):
                put(img, tx + d + (1 if k > ph // 2 and lean > 0.5 else 0), yy, hexc(pal["lit"] if k < ph // 2 and d == 0 else pal["plume"]))
        put(img, tx, ty, hexc(pal["plume"]))


def draw_mid():
    """中景：湖里的一簇簇芦苇岛（scroll 0.55），每簇底下是根丛和倒影。x 580–1060 留空（镜头在草原小镇那段时，这里正好在后面）。"""
    rng = np.random.default_rng(53)
    w, h, oy = 1300, 112, 96            # 图上沿在房间 y 96；根在 y 186–198
    img = blank(w, h)
    islands = []
    x = 10
    while x < w - 20:
        cw = int(rng.integers(40, 150))
        if not (560 < x + cw / 2 < 1080):
            islands.append((x, cw, int(rng.integers(186, 199)) - oy, int(rng.integers(24, 62))))
        x += cw + int(rng.integers(30, 110))
    islands.sort(key=lambda t: t[2])
    for x0, cw, root, tall in islands:
        prof = np.array([(1 - (2 * (i + 0.5) / cw - 1) ** 2) ** 0.6 for i in range(cw)])
        # 倒影：根丛下面 3–5 行，颜色混了水
        rh = int(rng.integers(3, 6))
        for i in range(cw):
            if prof[i] < 0.15:
                continue
            for d in range(1, int(rh * prof[i]) + 1):
                put(img, x0 + i, root + d, hexc(MIDR["refl"] if d < rh * prof[i] * 0.6 else MIDR["refl_d"]))
        # 秆：一根根往上
        n = int(cw / 2.2)
        for k in range(n):
            i = int(rng.integers(2, cw - 2))
            L = int(tall * prof[i] * rng.uniform(0.6, 1.05))
            if L < 6:
                continue
            mini_reed(img, x0 + i, root - 2, L, rng.uniform(0.0, 2.5), MIDR, rng)
        # 根丛：一条矮的厚边，上沿是叶尖
        for i in range(cw):
            t = int(round((4 + 6 * prof[i]) + rng.uniform(-1, 1)))
            for d in range(t):
                c = MIDR["base"] if d > 1 else MIDR["shade"]
                if d > t * 0.6:
                    c = MIDR["base_d"]
                put(img, x0 + i, root - d, hexc(c))
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    return img


# ---------------------------------------------------------------- 主层（晨那一层，静止部分）
def zone_reeds(x):
    """这里路两边是不是芦苇丛：1 = 是，0 = 浅水 / 草地；交界处平滑过渡"""
    def ramp(a, b):
        return float(np.clip((x - a) / (b - a), 0, 1))
    town = ramp(TOWN[0] - 40, TOWN[0] + 30) * (1 - ramp(TOWN[1] - 30, TOWN[1] + 40))
    return 1 - town


def front_kind(x):
    if WATER[0] + 20 <= x <= WATER[1] - 20:
        return "water"
    if TOWN[0] <= x <= TOWN[1]:
        return "meadow"
    return "reeds"


def draw_main():
    rng = np.random.default_rng(67)
    img = blank(W, H)
    z = np.array([zone_reeds(x) for x in range(W)])
    gy = np.array([ground(x) for x in range(W)])
    # 后面的根丛：上沿（芦苇区 ~194–199，草地区 ~212）
    btop = gy - (8 + 22 * z) + z * knots(W, 55, rng, 4.0) + knots(W, 13, rng, 1.0)
    ptop = gy - 4 + np.round(knots(W, 80, rng, 0.8))          # 路的上沿
    pbot = gy + 8 + np.round(knots(W, 70, rng, 1.2))          # 路的下沿
    for x in range(W):
        bt = int(round(btop[x]))
        pt = int(ptop[x])
        for y in range(bt, pt):
            d = (y - bt) / max(1, pt - bt)
            grass = z[x] < 0.3 + 0.4 * d          # 草地和芦苇根丛的交界是斜的
            if grass:
                c = MAIN["grass_t"] if y - bt < 2 else MAIN["grass"] if d < 0.6 else MAIN["grass_d"]
            else:
                c = MAIN["tip"] if y - bt < 2 else MAIN["mass"] if d < 0.45 else MAIN["mass_d"] if d < 0.85 else MAIN["shadow"]
            img[y, x] = hexc(c)
    # 根丛上沿冒出来的叶尖（1 像素宽、2–7 高、斜着，四邻接）
    for _ in range(int(W * 0.55)):
        x = int(rng.integers(2, W - 2))
        bt = int(round(btop[x]))
        grass = z[x] < 0.5
        L = int(rng.integers(2, 5 if grass else 8))
        lean = rng.uniform(-1.5, 2.5)
        pts = path4([(x + lean * (i / L) ** 1.5, bt - i) for i in range(L + 1)])
        for (a, b) in pts:
            put(img, a, b, hexc(MAIN["grass_t"] if grass else MAIN["tip"]))
    # 根丛里一道道叶片的明暗（细长、竖着偏一点，亮一档或暗一档），随机不等距
    for _ in range(int(W * 0.9)):
        x = int(rng.integers(0, W))
        bt, pt = int(round(btop[x])), int(ptop[x])
        if pt - bt < 6:
            continue
        y0 = int(rng.integers(bt + 2, pt - 3))
        L = int(rng.integers(3, 9))
        grass = z[x] < 0.5
        here = img[y0, x].copy()
        if grass:
            c = MAIN["grass_d"] if (here == hexc(MAIN["grass"])).all() else MAIN["grass"]
        else:
            c = MAIN["mass_d"] if (here == hexc(MAIN["mass"])).all() else MAIN["mass"] if (here == hexc(MAIN["mass_d"])).all() else MAIN["mass_dd"]
        lean = rng.uniform(-0.5, 1.2)
        for (a, b) in path4([(x + lean * i / L, y0 + i) for i in range(L)]):
            if 0 <= a < W and b < pt - 1 and img[b, a, 3]:
                img[b, a] = hexc(c)
    # 小路：踩出来的土路，中间亮（踩得多），两边一圈深一点，偶尔几块小石子
    for x in range(W):
        pt, pb = int(ptop[x]), int(pbot[x])
        for y in range(pt, pb):
            c = MAIN["path"]
            if y - pt < 1 or pb - y <= 1:
                c = MAIN["path_edge"]
            img[y, x] = hexc(c)
    worn_a = gy - 1 + np.round(knots(W, 50, rng, 0.9))
    worn_b = gy + 4 + np.round(knots(W, 60, rng, 1.0))
    on = knots(W, 45, rng, 1.0) > -0.35
    for x in range(W):
        if on[x]:
            for y in range(int(worn_a[x]), int(worn_b[x])):
                img[y, x] = hexc(MAIN["path_lit"])
    for _ in range(46):
        x = int(rng.integers(10, W - 10))
        y = int(rng.integers(int(ptop[x]) + 2, int(pbot[x]) - 2))
        L = int(rng.integers(2, 4))
        img[y, x:x + L] = hexc(MAIN["pebble"])
        img[y + 1, x:x + L] = hexc(MAIN["pebble_d"])
    # 路前面：芦苇丛 / 浅水 / 矮草地。交界不切竖直的一刀：水面的上沿、芦苇丛的上沿顺着一道斜坡（每列最多差一两格）交过去
    ftop = pbot + np.round(knots(W, 40, rng, 1.0))
    wtop = np.array([int(pbot[x]) + 2 for x in range(W)])
    ew = np.array([sstep(WATER[0] - 10, WATER[0] + 60, x) * (1 - sstep(WATER[1] - 60, WATER[1] + 10, x)) for x in range(W)])
    em = np.array([sstep(TOWN[0] - 60, TOWN[0] + 10, x) * (1 - sstep(TOWN[1] - 10, TOWN[1] + 60, x)) for x in range(W)])
    water_y = np.round(wtop + (H - wtop) * (1 - ew) + 10 * ew * (1 - ew) * knots(W, 16, rng, 1.0)).astype(int)        # 这一列从哪一行起是水（H = 没有水）
    mass_y = np.round(ftop + (H + 4 - ftop) * em).astype(int)           # 这一列从哪一行起是芦苇丛（往下）
    for x in range(W):
        pb, ft = int(pbot[x]), int(ftop[x])
        for y in range(pb, H):
            if y >= water_y[x]:
                d = y - wtop[x]
                c = MAIN["w0"] if d < 3 else MAIN["w1"] if d < 14 else MAIN["w2"] if d < 26 else MAIN["w3"]
            elif ew[x] > 0.97:
                c = MAIN["mud"] if y == pb else MAIN["mud_d"]
            elif y >= mass_y[x]:
                d = y - max(ft, mass_y[x])
                c = MAIN["ftip"] if d < 2 else MAIN["fmass"] if d < 12 else MAIN["fmass_d"] if d < 24 else MAIN["fmass_dd"]
                if water_y[x] < H and water_y[x] - y <= 1:
                    c = MAIN["mud_d"]                  # 芦苇丛泡进水的那一圈：泥
            elif em[x] > 0.02:
                d = y - pb
                c = MAIN["grass_t"] if d < 2 else MAIN["grass"] if d < 14 else MAIN["grass_d"] if d < 26 else MAIN["grass_dd"]
            else:
                c = MAIN["path_edge"]
            img[y, x] = hexc(c)
    # 路前芦苇丛的叶尖（往上冒）+ 里面的叶片明暗
    for _ in range(int(W * 0.5)):
        x = int(rng.integers(2, W - 2))
        ft = int(ftop[x])
        if not (mass_y[x] <= ft + 1 and water_y[x] > ft + 6):
            continue
        L = int(rng.integers(2, 7))
        lean = rng.uniform(-1.5, 2.0)
        for (a, b) in path4([(x + lean * (i / L) ** 1.5, ft - i) for i in range(L + 1)]):
            if not 0 <= a < W or b < int(pbot[a]) + 1:
                continue
            put(img, a, b, hexc(MAIN["ftip"]))
    for _ in range(int(W * 0.8)):
        x = int(rng.integers(0, W))
        ft = max(int(ftop[x]), int(mass_y[x]))
        if ft > H - 8 or water_y[x] < H:
            continue
        y0 = int(rng.integers(ft + 3, H - 3))
        L = int(rng.integers(3, 10))
        here = img[y0, x].copy()
        c = MAIN["fmass_d"] if (here == hexc(MAIN["fmass"])).all() else MAIN["fmass"] if (here == hexc(MAIN["fmass_d"])).all() else MAIN["fmass_d"]
        lean = rng.uniform(-0.6, 1.0)
        for (a, b) in path4([(x + lean * i / L, y0 + i) for i in range(L)]):
            if 0 <= a < W and b < H and any((img[b, a] == hexc(MAIN[k])).all() for k in ("fmass", "fmass_d", "fmass_dd")):
                img[b, a] = hexc(c)
    # 浅水：映着天的亮纹（两头尖的横条，长短不一），岸边一条芦苇的倒影（深一档、横向抖）
    for _ in range(40):
        x = int(rng.integers(WATER[0] + 30, WATER[1] - 30))
        y = int(rng.integers(wtop[x] + 5, H - 2))
        L = int(rng.integers(6, 30))
        for i in range(L):
            if y >= water_y[x + i] + 2 and (img[y, x + i] != hexc(MAIN["w0"])).any():
                img[y, x + i] = hexc(MAIN["w_lit"] if 0.15 < i / L < 0.85 else MAIN["w2"])
    # 草地里一道道草叶的明暗（短、斜，亮一档或暗一档）
    gset = {k: hexc(MAIN[k]) for k in ("grass", "grass_d", "grass_dd")}
    for _ in range(900):
        x = int(rng.integers(TOWN[0] - 50, TOWN[1] + 50))
        y0 = int(rng.integers(int(pbot[x]) + 3, H - 3))
        here = img[y0, x]
        k = next((k for k, c in gset.items() if (here == c).all()), None)
        if k is None:
            continue
        c = gset["grass_d"] if k == "grass" else gset["grass"] if k == "grass_d" else gset["grass_d"]
        L = int(rng.integers(2, 6))
        lean = rng.uniform(-0.8, 0.8)
        for (a, b) in path4([(x + lean * i / L, y0 + i) for i in range(L)]):
            if 0 <= a < W and b < H and (img[b, a] == here).all():
                img[b, a] = c
    # 草地上的小花：一格花 + 下面一格花茎（不是孤立的单点），稀稀拉拉
    for _ in range(60):
        x = int(rng.integers(TOWN[0] + 10, TOWN[1] - 10))
        y = int(rng.integers(int(pbot[x]) + 4, H - 3))
        c = MAIN["fl_blue"] if rng.random() < 0.55 else MAIN["fl_cream"]
        img[y, x] = hexc(c)
        img[y + 1, x] = hexc(MAIN["fl_stem"])
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    return img, btop, ptop, pbot


# ---------------------------------------------------------------- 会动的芦苇：每种在每个角度下画一帧
def reed_variants():
    """每排几种：L 总长（含穗）、P 穗长、PW 穗宽、nod 平时穗往右垂多少度、strands 穗下沿垂下来的几缕穗丝、
    leaves [(在秆的几成处, 左右, 长, 弧)]"""
    rng = np.random.default_rng(83)
    out = {}
    #       种数  总长        穗长      穗宽         点头
    spec = {"r0": (5, (58, 84), (16, 21), (4.4, 5.6), (62, 88)),
            "r1": (7, (24, 58), (12, 17), (3.2, 4.2), (52, 78)),
            "r2": (5, (14, 26), (8, 11), (2.2, 2.8), (44, 64)),
            "f": (4, (50, 76), (15, 19), (4.8, 6.0), (56, 80))}
    for row, (n, lr, pr, wr, nr) in spec.items():
        for i in range(n):
            L = int(round(lr[0] + (lr[1] - lr[0]) * (i / max(1, n - 1)) + rng.uniform(-2, 2)))
            P = int(rng.integers(pr[0], pr[1] + 1))
            PW = float(rng.uniform(*wr))
            leaves = []
            nl = int(rng.integers(1, 3)) + (1 if L > 48 else 0)
            side = -1 if rng.random() < 0.5 else 1
            for k in range(nl):
                s = rng.uniform(0.18, 0.5)
                leaves.append((s + 0.12 * k, side, int(L * rng.uniform(0.2, 0.34)), rng.uniform(0.3, 0.8)))
                side = -side
            strands = sorted(rng.uniform(0.3, 0.9, int(rng.integers(2, 5 if P > 10 else 3))).tolist())
            out[f"{row}_{i}"] = {"row": row, "L": L, "P": P, "PW": PW, "nod": float(rng.uniform(*nr)),
                                 "rest": float(rng.uniform(-3, 3)), "jag": rng.uniform(-0.5, 0.5, 64).tolist(),
                                 "strands": strands, "slen": rng.integers(2, 5, len(strands)).tolist(), "leaves": leaves}
    return out


def reed_frame(v, theta):
    """一根芦苇弯 theta 度的样子。返回 {(x, y): rgba}，原点 = 根（最下面那一格），y 往上为负。
    秆：角度沿长度按 (s/L)^1.25 增加（根稳、整根顺下来弯，不是只弯顶上一截）；
    穗：一大蓬往一边垂（平时往右点头 nod 度，被压弯时跟着翻到弯的那边），上侧受光亮、下侧暗，下沿垂几缕穗丝；
    叶：从秆的节上斜着长出来，外半截缓缓往下垂，跟着秆一起转。"""
    pal = REED_PAL[v["row"]]
    L, P, PW = v["L"], v["P"], v["PW"]
    th = math.radians(theta)
    nod_dir = math.tanh((theta + 9.0) / 8.0)
    nod = math.radians(v["nod"] * nod_dir) + 0.3 * th
    ds = 0.25
    pts = [(0.0, 0.0)]
    angs = [0.0]
    x = y = 0.0
    s = 0.0
    while s < L:
        u = s / L
        a = th * u ** 1.25
        if s > L - P:
            pu = (s - (L - P)) / P
            a += nod * pu ** 1.3
        x += math.sin(a) * ds
        y -= math.cos(a) * ds
        s += ds
        pts.append((x, y))
        angs.append(a)
    px = {}
    stem = path4(pts[: int((L - P * 0.7) / ds)])
    n = len(stem)
    for j, p in enumerate(stem):
        c = pal["stem"][0] if j < n * 0.35 else pal["stem"][1] if j < n * 0.75 else pal["stem"][2]
        px[p] = hexc(c)
    # 叶
    for (sf, side, ll, arc) in v["leaves"]:
        i0 = min(len(pts) - 1, int(sf * L / ds))
        root = stem[min(len(stem) - 1, int(sf * len(stem)))]
        a0 = angs[i0] + side * math.radians(32)
        lx, ly = float(root[0]), float(root[1])
        lp = [(lx, ly)]
        steps = int(ll / 0.3)
        for k in range(steps):
            t = k / max(1, steps - 1)
            a = a0 + side * arc * max(0.0, t - 0.35) ** 1.5 * 2.2 + 0.25 * th * t
            lx += math.sin(a) * 0.3
            ly -= math.cos(a) * 0.3
            lp.append((lx, ly))
        lpx = path4(lp)
        for j, p in enumerate(lpx):
            if p not in px:
                px[p] = hexc(pal["leaf"][0] if j < len(lpx) * 0.5 else pal["leaf"][1])
    # 穗
    i_p = int((L - P) / ds)
    tip_a = angs[-1]
    down = 1.0 if tip_a >= -0.05 else -1.0     # 法线 (cos a, sin a) 的哪一边是「下侧」
    plume = {}
    edge = {}
    for i in range(i_p, len(pts)):
        u = (i - i_p) / max(1, len(pts) - 1 - i_p)
        a = angs[i]
        cx, cy = pts[i]
        nx, ny = math.cos(a) * down, math.sin(a) * down
        wprof = PW * (math.sin(math.pi * min(1.0, 0.12 + u * 1.05)) ** 0.7) * (1 - 0.3 * u)
        wprof += 0.5 * v["jag"][int(u * 63)]
        wprof = max(0.6, wprof)
        lo, hi = -wprof * 0.3, wprof * 0.7
        k = lo
        while k <= hi + 1e-6:
            q = (int(round(cx + nx * k)), int(round(cy + ny * k)))
            h = -(ny * k) - u * 0.6           # 越高越亮；越往穗尖越暗一点
            plume[q] = max(plume.get(q, -99.0), h)
            k += 0.33
        edge[round(u, 3)] = (cx + nx * hi, cy + ny * hi, a)
    if plume:
        vals = np.array(list(plume.values()))
        q1, q2 = np.quantile(vals, [0.4, 0.75])
        for p, val in plume.items():
            px[p] = hexc(pal["plume"][0] if val < q1 else pal["plume"][1] if val < q2 else pal["plume"][2])
    # 穗丝：从下沿垂下来 2–4 格（偏向重力，带一点穗的走向），四邻接、颜色最暗那档
    keys = sorted(edge)
    for sf, sl in zip(v["strands"], v["slen"]):
        if not keys:
            break
        kk = min(keys, key=lambda t: abs(t - sf))
        ex, ey, a = edge[kk]
        tx, ty = math.sin(a), -math.cos(a)
        dx, dy = 0.35 * tx * down, 1.0
        nrm = math.hypot(dx, dy)
        dx, dy = dx / nrm, dy / nrm
        sp = [(ex, ey)] + [(ex + dx * t, ey + dy * t) for t in np.arange(0.5, sl + 0.5, 0.5)]
        for p in path4(sp):
            if p not in px:
                px[p] = hexc(pal["plume"][0])
    return px


def clean_sprite(px):
    """一帧：转成小图 → 补对角 → 去孤立单像素 → 返回 (img, ox, oy)，(ox, oy) = 图左上角相对根的偏移"""
    xs = [p[0] for p in px]
    ys = [p[1] for p in px]
    x0, y0 = min(xs) - 1, min(ys) - 1
    w, h = max(xs) - x0 + 2, max(ys) - y0 + 2
    img = blank(w, h)
    for (x, y), c in px.items():
        img[y - y0, x - x0] = c
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    alpha_fix(img)
    # 去掉多留的一圈
    a = img[..., 3] > 0
    yy, xx = np.nonzero(a)
    img = img[yy.min():yy.max() + 1, xx.min():xx.max() + 1]
    return img, x0 + int(xx.min()), y0 + int(yy.min())


def build_reeds():
    vs = reed_variants()
    frames = {}
    for name, v in vs.items():
        lst = []
        for a in ANGLES:
            img, ox, oy = clean_sprite(reed_frame(v, a))
            # 顶（给落在上面的鸟用）：最上面一行里离中心最近的那格
            ys, xs = np.nonzero(img[..., 3])
            top = ys.min()
            tx = int(xs[ys == top].mean())
            lst.append((img, ox, oy, tx + ox, int(top) + oy))
        frames[name] = lst
    # 打包：一行一种（31 帧横排）
    rows = []
    for name in vs:
        hmax = max(f[0].shape[0] for f in frames[name])
        wsum = sum(f[0].shape[1] + 1 for f in frames[name])
        rows.append((name, hmax, wsum))
    aw = max(r[2] for r in rows)
    ah = sum(r[1] + 1 for r in rows)
    atlas = blank(aw, ah)
    meta = {"angles": ANGLES, "variants": {}}
    y = 0
    for name, hmax, _ in rows:
        x = 0
        fl = []
        for img, ox, oy, tx, ty in frames[name]:
            h, w = img.shape[:2]
            atlas[y:y + h, x:x + w] = img
            fl.append([x, y, w, h, ox, oy, tx, ty])
            x += w + 1
        v = vs[name]
        meta["variants"][name] = {"row": v["row"], "L": v["L"], "rest": round(v["rest"], 2), "frames": fl}
        y += hmax + 1
    return atlas, meta, vs


def place_reeds(vs, btop, ptop, pbot):
    """每一根放哪：[x, 根 y, 种类, 自己的风相位]。r0 后排高的成簇、中间留缝透出湖；r1 路后面密；r2 路前面；f 前景（scroll 1.25 的坐标）。"""
    rng = np.random.default_rng(97)
    names = {r: [n for n in vs if vs[n]["row"] == r] for r in ("r0", "r1", "r2", "f")}
    out = {"r0": [], "r1": [], "r2": [], "f": []}
    dens0 = knots(W, 90, rng, 1.0) + knots(W, 25, rng, 0.35)
    dens1 = knots(W, 50, rng, 1.0)
    x = 6.0
    while x < W - 6:
        xi = int(x)
        z = zone_reeds(xi)
        if z > 0.7 and dens0[xi] > 0.2:                              # 后排高的：一簇一簇，中间留缝透出湖
            out["r0"].append([xi, int(round(btop[xi])) + int(rng.integers(6, 12)), str(rng.choice(names["r0"])), round(float(rng.uniform(0, 6.28)), 2)])
        x += rng.uniform(3.0, 6.5)
    x = 4.0
    while x < W - 4:
        xi = int(x)
        z = zone_reeds(xi)
        if (z > 0.5 and dens1[xi] > -0.55) or rng.random() < 0.06:
            pool = names["r1"] if z > 0.5 else names["r1"][:2]       # 草地上只零星几根矮的
            out["r1"].append([xi, int(ptop[xi]) - int(rng.integers(2, 8)), str(rng.choice(pool)), round(float(rng.uniform(0, 6.28)), 2)])
        x += rng.uniform(2.6, 5.2) if z > 0.5 else rng.uniform(14, 30)
    x = 4.0
    while x < W - 4:
        xi = int(x)
        if front_kind(xi) == "reeds" and front_kind(xi - 14) == "reeds" and front_kind(xi + 14) == "reeds" \
                and not (WATER[0] - 50 < xi < WATER[1] + 50) and not (TOWN[0] - 50 < xi < TOWN[1] + 50):
            out["r2"].append([xi, int(pbot[xi]) + int(rng.integers(12, 28)), str(rng.choice(names["r2"])), round(float(rng.uniform(0, 6.28)), 2)])
        x += rng.uniform(8.0, 17.0)
    # 前景：一簇簇（3–6 根），簇和簇之间隔 140–300（层坐标；层宽 480 + 1440 × 1.25 = 2280）
    fx = 60.0
    fw = 480 + (W - 480) * 1.25
    while fx < fw - 30:
        # 这簇正好在屏幕中间时，晨那一层对着的 x
        cl = (fx - 240) / 1.25
        mx = cl + 240
        if not (TOWN[0] - 60 < mx < TOWN[1] + 60):
            for k in range(int(rng.integers(3, 7))):
                out["f"].append([int(fx + k * rng.uniform(4, 9)), int(rng.integers(276, 292)), str(rng.choice(names["f"])), round(float(rng.uniform(0, 6.28)), 2)])
        fx += rng.uniform(150, 310)
    for r in out:
        out[r].sort(key=lambda t: t[0])
    return out


# ---------------------------------------------------------------- 鸟
# 背影（飞走的方向背对镜头）：D = 翅、B = 身、T = 尾。四种大小（近 → 远），每种 up / mid / down 三帧；
# 翅膀斜着的地方一格一格竖着接（四邻接），不只角碰角。最后两帧是落在芦苇顶上的侧影（朝右），歇着 / 低头
BIRD_FR = {
    0: [["D.......D", "DD.....DD", ".DD...DD.", "..DDBDD..", "...BBB...", "....T...."],
        [".........", ".........", "DDD...DDD", "..DDBDD..", "...BBB...", "....T...."],
        [".........", ".........", "...DBD...", "..DBBBD..", ".DD.T.DD.", "DD.....DD"]],
    1: [["D.....D", "DD...DD", ".DDBDD.", "..BBB..", "...T..."],
        [".......", "DD...DD", ".DDBDD.", "..BBB..", "...T..."],
        [".......", "..DBD..", ".DBBBD.", "DD.T.DD", "D.....D"]],
    2: [["D...D", "DDBDD", ".BBB."],
        [".....", "DDBDD", ".BBB."],
        [".BBB.", "DDBDD", "D...D"]],
    3: [["D.D", "DBD"], ["...", "DBD"], ["DBD", "D.D"]],
}
PERCH_FR = [["...BB", ".BBBB", "TBBB."], [".....", ".BBBB", "TBBBB"]]


def build_birds():
    cmap = {"D": hexc(BIRD["wing"]), "B": hexc(BIRD["body"]), "T": hexc(BIRD["tail"])}
    cells = []
    for s in range(4):
        for fr in BIRD_FR[s]:
            cells.append(fr)
    cells += PERCH_FR
    cw = max(len(r) for fr in cells for r in fr) + 1      # 格子之间空一列
    ch = max(len(fr) for fr in cells)
    img = blank(cw * len(cells), ch)
    meta = {"cell": [cw, ch], "sizes": {}, "perch": []}
    for i, fr in enumerate(cells):
        w = len(fr[0])
        h = len(fr)
        ox = (cw - w) // 2
        oy = ch - h
        for y, row in enumerate(fr):
            for x, ch_ in enumerate(row):
                if ch_ in cmap:
                    img[oy + y, i * cw + ox + x] = cmap[ch_]
    for s in range(4):
        meta["sizes"][str(s)] = [s * 3, s * 3 + 1, s * 3 + 2]
    meta["perch"] = [12, 13]
    # 落脚点（帧里）：每格底边中间
    meta["foot"] = [cw // 2, ch - 1]
    return img, meta


# ---------------------------------------------------------------- room.json
def room_json():
    layers = [
        {"id": "sky", "img": "sky.png", "scroll": 0.0, "y": 0},
        {"id": "wisps", "img": "wisps.png", "scroll": 0.03, "y": 6, "tile": True, "drift": -1.2},
        {"id": "clouds", "img": "clouds.png", "scroll": 0.06, "y": 34, "tile": True, "drift": -0.35},
        {"id": "far", "img": "far.png", "scroll": 0.2, "y": 124, "tile": True, "shader": "sway",
         "shader_params": {"amp": 1.0, "speed": 0.9, "wavelength": 240.0, "power": 1.2, "bend": 0.0}},
        {"id": "lake", "img": "lake.png", "scroll": 0.35, "y": 155, "tile": True},
        {"id": "sunpath", "img": "sunpath.png", "scroll": 0.0, "y": 155, "shader": "water",
         "shader_params": {"palette_mode": False, "speed": 0.8, "wobble": 1.5, "flicker": 0.0, "show": 0.7}},
        {"id": "glints", "img": "glints.png", "scroll": 0.35, "y": 155, "tile": True, "shader": "water",
         "shader_params": {"palette_mode": False, "speed": 0.6, "wobble": 1.0, "flicker": 0.0, "show": 0.55}},
        {"id": "mid", "img": "mid.png", "scroll": 0.55, "y": 96, "shader": "sway",
         "shader_params": {"amp": 1.0, "speed": 0.75, "wavelength": 260.0, "power": 1.6, "bend": 0.0}},
        {"id": "main", "img": "main.png", "scroll": 1.0, "y": 0},
    ]
    return {
        "_note": ("tools/reed_field_art.py 生成，别手改（要改先改脚本）。云层星的芦苇地（第三章；结局一、结局二的 yard / east_meadow 都改成这张）。"
                  "白天、最亮的一屏。会动的芦苇和惊鸟是 scripts/reed_field.gd（scripts 里），数据在 reeds.json / birds.json。"
                  "约定见 docs/river_rooms_contract.md。"),
        "_note_town": f"草原小镇留在 x {TOWN[0]}–{TOWN[1]}：地是平的（ground {ground(TOWN[0])}），路前面是矮草地、后面没有高芦苇，"
                      "中景这一段（mid.png 的 x 560–1080）也空着。小镇的房子画在这一段，放进 main 后面一层（scroll 1，z 在 main 前、晨后）。",
        "size": [W, H],
        "origin": [0, 1080],
        "env": "reeds",
        "bg": ["#86bde0", "#e3eeec"],
        "layers": layers,
        "ground": GROUND,
        "walk": WALK,
        "markers": {"reed_field_west": 60, "reed_field_spot1": SPOTS[0], "reed_field_water": SPOTS[1],
                    "reed_field_town": (TOWN[0] + TOWN[1]) // 2, "reed_field_spot3": SPOTS[2], "reed_field_east": 1860},
        "objects": {},
        "portals": [],
        "ambient": [],
        "scripts": [{"script": "res://scripts/reed_field.gd", "x": 0, "y": 0, "z": -40,
                     "params": {"data": "res://art/reed_field/reeds.json", "birds": "res://art/reed_field/birds.json",
                                "spots": [[SPOTS[0], 5], [SPOTS[1], 7], [SPOTS[2], 4]]}}],
    }


# ---------------------------------------------------------------- 预览：按 room.json 叠一屏 + 芦苇（风里的平时样子）+ 晨
def compose(layers_img, atlas, meta, place, cl, chen_x=None, theta_fn=None, birds=None, bmeta=None):
    j = room_json()
    out = np.zeros((H, 480, 4), np.uint8)
    out[...] = hexc(j["bg"][0])

    def blit(src, x, y):
        h, w = src.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(480, x + w), min(H, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        s = src[y0 - y:y1 - y, x0 - x:x1 - x]
        m = s[..., 3] > 0
        out[y0:y1, x0:x1][m] = s[m]

    for L in j["layers"]:
        im = layers_img[L["id"]]
        sc = L.get("scroll", 1.0)
        x = round(L.get("x", 0) - cl * sc)
        if L.get("tile"):
            w = im.shape[1]
            x = x % w - w
            while x < 480:
                blit(im, x, L["y"])
                x += w
        else:
            blit(im, x, L["y"])

    def reeds(row, sc, zlist=None):
        for (x, y, vn, ph) in place[row]:
            sx = round(x - cl * sc)
            if sx < -100 or sx > 580:
                continue
            v = meta["variants"][vn]
            th = theta_fn(row, x, sx) if theta_fn else 3.0 + v["rest"]
            i = int(np.argmin([abs(a - th) for a in meta["angles"]]))
            fx, fy, fw, fh, ox, oy, _, _ = v["frames"][i]
            blit(atlas[fy:fy + fh, fx:fx + fw], sx + ox, y + oy)
    reeds("r0", 1.0)
    if birds is not None:
        for (bx, by, idx) in birds:
            cw, ch = bmeta["cell"]
            blit(birds_img_global[0][:, idx * cw:(idx + 1) * cw], round(bx - cl - cw // 2), by - ch + 1)
    reeds("r1", 1.0)
    if chen_x is not None:
        sheet = np.array(Image.open(ROOT / "art/characters/chen/chen_oscar.png").convert("RGBA"))
        f = 18
        fr = sheet[:, f * 68:(f + 1) * 68]
        blit(fr, round(chen_x - cl - 26), ground(chen_x) - 58)
    reeds("r2", 1.0)
    reeds("f", 1.25)
    return out


birds_img_global = [None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    args = ap.parse_args()
    p = ROOT / "art" / "手改清单.json"
    locked = set(json.loads(p.read_text()).get("files", {})) if p.exists() else set()
    OUT.mkdir(parents=True, exist_ok=True)

    imgs = {}
    print("画：天、云、远景、湖、中景、主层……")
    imgs["sky"] = draw_sky()
    imgs["wisps"] = draw_wisps()
    imgs["clouds"] = draw_clouds()
    imgs["far"] = draw_far()
    imgs["lake"] = draw_lake()
    imgs["sunpath"] = draw_glints(480, 50, 5, 70, center=SUN[0], spread=34)
    imgs["glints"] = draw_glints(960, 50, 6, 26)
    imgs["mid"] = draw_mid()
    imgs["main"], btop, ptop, pbot = draw_main()
    print("画：芦苇的弯曲帧、鸟……")
    atlas, meta, vs = build_reeds()
    place = place_reeds(vs, btop, ptop, pbot)
    birds, bmeta = build_birds()
    birds_img_global[0] = birds

    print("自查：")
    bad = 0
    for k in ("sky", "wisps", "clouds", "far", "lake", "mid", "main"):
        bad += scan(k, imgs[k], alpha_only=False)
        bad += dashes(k, imgs[k])
    nr = 0
    for vn, v in meta["variants"].items():          # 逐帧扫（整张图集里帧和帧之间的分隔列会被当成缺口）
        for (fx, fy, fw, fh, *_r) in v["frames"]:
            f = blank(fw + 2, fh + 2)
            f[1:-1, 1:-1] = atlas[fy:fy + fh, fx:fx + fw]
            nr += scan_quiet(f)
    print(f"  reeds（逐帧，只看轮廓）: 只有对角相连 + 孤立单像素 + 细线缺口 共 {nr}")
    bad += nr
    bad += scan("birds（只看轮廓）", birds, alpha_only=True)
    gl = [(x, ground(x + 1) - ground(x)) for x in range(W - 1) if abs(ground(x + 1) - ground(x)) > 1]
    print("  地面：相邻两列差 ≥2 像素的地方", gl)

    def save(arr, name):
        rel = (OUT / name).relative_to(ROOT).as_posix()
        if rel in locked:
            print("跳过（作者手改，见 art/手改清单.json）:", rel)
            return
        Image.fromarray(arr, "RGBA").save(OUT / name)

    for k, v in imgs.items():
        save(v, k + ".png")
    save(atlas, "reeds.png")
    save(birds, "birds.png")
    for name, data in (("reeds.json", {**meta, "rows": place}), ("birds.json", bmeta), ("room.json", room_json())):
        rel = (OUT / name).relative_to(ROOT).as_posix()
        if rel not in locked:
            (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=1 if name == "room.json" else None) + "\n", encoding="utf-8")
    print("ok reed_field", W, H, "芦苇", {r: len(v) for r, v in place.items()}, "种类", len(vs), "atlas", atlas.shape[1], "×", atlas.shape[0])

    if args.preview:
        pv = Path(args.preview)
        pv.mkdir(parents=True, exist_ok=True)
        # 全图：镜头从左到右四屏拼起来；每屏各放一个晨
        shots = []
        for cl in (0, 480, 960, 1440):
            shots.append(compose(imgs, atlas, meta, place, cl, chen_x=cl + 240,
                                 birds=[(SPOTS[0] - 6, 150, 12)] if cl == 0 else None, bmeta=bmeta))
        full = np.concatenate(shots, axis=1)
        Image.fromarray(full).save(pv / "full_1x.png")
        Image.fromarray(full).resize((full.shape[1] * 2, H * 2), Image.NEAREST).save(pv / "full_2x.png")
        for i, s in enumerate(shots):
            Image.fromarray(s).resize((480 * 4, H * 4), Image.NEAREST).save(pv / f"screen{i}_4x.png")
        Image.fromarray(atlas).resize((atlas.shape[1] * 3, atlas.shape[0] * 3), Image.NEAREST).save(pv / "reeds_3x.png")
        Image.fromarray(birds).resize((birds.shape[1] * 8, birds.shape[0] * 8), Image.NEAREST).save(pv / "birds_8x.png")
        print("预览:", pv)


if __name__ == "__main__":
    main()
