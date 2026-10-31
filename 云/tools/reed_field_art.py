"""第三章 · 云层星的芦苇地 reed_field。结局一、结局二原来的两张草地（yard、east_meadow）都改成这一张；以后在它上面加「草原小镇」。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/reed_field_art.py [--preview 目录]

第二版（10-31 作者看了第一版：「芦苇草地首先是草地，黄色是明黄色，蓝色是淡蓝色，这些颜色都交织在一起，而不是泾渭分明的分开来，
不要卷云，天空中一层一层的就可以，最梦幻最唯美，不要太具体，浅草或者浅水没过了主角脚踝，地上有清澈透明甚至反光的河」）：
- 首先是草地：一大片开阔的草甸，芦苇只是长在草里的几丛（会弯腰的那些），不是一整面芦苇墙。
- 明黄 + 淡蓝交织：草甸、河、天都用同一条色阶 RAMP（深金 → 明黄 → 奶白 → 淡蓝 → 蓝），大块的色斑由噪声分档，黄和蓝之间隔着奶白，
  边是一档档软过渡；横向的短笔触把黄掺进蓝、蓝掺进黄。芦苇穗也是黄的受光、淡蓝的背光。
- 天：一层层柔和的横向色带（淡蓝 → 一道淡黄 → 淡蓝 → 地平线上一大片明黄），几条很薄很长的横云（蓝里的是奶黄、黄里的是淡蓝），
  左边低处一团很淡的太阳光。没有积云。
- 概括：远景融成色带，草不画一根根，只有色块 + 笔触。
- 没过脚踝：ankle.png（草丛）/ ankle_water.png（水面，半透明）在晨前面画（z 20 / 21，不用 front: true —— 那个会在挡住晨时淡掉），
  整段都有：草地上晨的脚踝一直埋在草丛里，水里水面线在脚底上方 3 行。
- 地上的河：中景一条横着的清澈的河；路上两段浅水（WATERS），路整个泡在水里：远的一边映地平线的明黄、近处映天的淡蓝、
  近处透出水底的沙色，波纹黄蓝互掺，亮纹用 water shader 闪。晨在水里时脚下有她的倒影（scripts/reed_field.gd 画）。
- 亮主角：晨身后那一带的草深一档（深金 / 蓝），reed_field.gd 还在晨身后压一圈很淡的暗（正片叠底，三档），画面整体不变暗。

横向 1920：0–520 草甸（芦苇丛，惊鸟 1：x 330）/ 520–860 浅水（惊鸟 2：x 700）/ 860–1110 草甸 /
1110–1490 平缓、空的草地，留给以后的「草原小镇」（room.json 的 _note_town）/ 1540–1780 浅水 / 1780–1920 草甸（惊鸟 3：x 1660 在水边）

图层（room.json，从后往前）：
  sky.png         480×270  scroll 0     天的色带 + 太阳光
  streaks.png     960×130  scroll 0.03  很薄很长的横云（tile，drift）
  far.png         960×34   scroll 0.12  远处的草甸（tile，sway shader 轻摆）
  mid.png         960×44   scroll 0.4   中景：草甸 + 一条清澈的河（tile）
  mid_glints.png  960×44   scroll 0.4   河上的亮纹（water shader）
  main.png        1920×270 scroll 1     草甸、路、两段浅水
  glints.png      1920×270 scroll 1     浅水上的亮纹（water shader）
  （会动的芦苇、鸟、晨的倒影、晨身后压暗：scripts/reed_field.gd）
  ankle.png       1920×270 scroll 1 z 20    没过脚踝的草丛
  ankle_water.png 1920×270 scroll 1 z 21    没过脚踝的水面（alpha 0.6）
会动的芦苇：reeds.png + reeds.json（每种芦苇 31 个弯曲角度各一帧；1 像素的秆四邻接画，弯到哪一帧都不断）；鸟：birds.png + birds.json。

所有随机固定 seed；除了 ankle_water / 亮纹层以外 alpha 只有 0/255。不碰 art/手改清单.json 里的文件。
画完自己扫一遍：只有对角相连、孤立单像素、细线缺口、虚线、地面直角台阶。
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
WATERS = [(520, 860), (1540, 1780)]     # 路泡在浅水里的两段（画完按水塘的真形状重算，见 draw_main）
# 浅水塘：几团扁椭圆 (中心 x, 中心 y, 半宽, 半高) 叠起来，再用噪声把岸弄弯
# 椭圆的中心放在画面下沿以下：画面里看到的是它的上半，两边的岸是斜着收下去的（不是竖直的一刀）
POOLS = [[(690, 312, 236, 112), (596, 300, 120, 84), (792, 296, 128, 82), (706, 280, 70, 64)],
         [(1660, 312, 180, 108), (1594, 300, 96, 80), (1736, 300, 96, 82)]]
TOWN = (1110, 1490)                     # 留给草原小镇
SPOTS = [150, 664, 1680]                # 惊鸟的地方（房间 x，都在芦苇丛里）
# 芦苇聚成几大片（房间 x 范围）：r0 后面高的、r1 路后面的。中间留开阔的草地，草原小镇那段（TOWN）没有
R0_MASSES = [(40, 250), (420, 640), (880, 1070), (1560, 1770)]
R1_MASSES = [(80, 230), (600, 730), (950, 1060), (1620, 1740), (1800, 1900)]
FRONT_MASSES = [(150, 210), (980, 1050), (2120, 2190)]      # 前景（scroll 1.25 的层坐标）
SUN = (150, 112)                        # 太阳光（屏幕坐标，天是钉在屏幕上的）
MEADOW_TOP = 174                        # 晨这一层草甸的上沿（大约）
W_TOP = 198                             # 浅水的远岸（大约）


def hexc(h, a=255):
    return np.array([int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), a], np.uint8)


def mix(a, b, k):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    out = a * (1 - k) + b * k
    out[3] = 255
    return np.round(out).astype(np.uint8)


# ---------------------------------------------------------------- 调色板（第三版的颜色：回到第二版的明黄 + 淡蓝，只去掉最深的那档深黄）
# 10-31 作者：第三版淡成奶色「没有暖味道了，上一个去掉最深的深黄就差不多」。RAMP 第 0 档原来是 #d4a42e（深金），去掉；
# 芦苇秆最深的那档也往上提一档。
RAMP = ["#ecc23e", "#f2cb40", "#f9d847", "#fde67a", "#fef3bf", "#ddf1f5", "#bae2f3", "#95cfee", "#77b9e2"]
SKY_STOPS = [(0, "#9dd2f1"), (34, "#b4def4"), (56, "#cde9f4"), (68, "#f6efc4"), (78, "#d6edf5"), (98, "#c4e6f5"),
             (116, "#e6f2ee"), (126, "#fbf0bb"), (136, "#fee88a"), (146, "#ffe066"), (162, "#fff0a8")]
SUN_WARM = "#fff6cf"
STREAK = {"y": ["#fff6cf", "#fbeeb4"], "w": ["#fdfdf4", "#eef6f2"], "b": ["#d5edf6", "#bfe2f3"]}
RIVER = ["#fff2a8", "#fde98c", "#f2f1d0", "#d8eef4", "#bfe3f4", "#a6d8f2"]       # 远（映地平线的黄）→ 近（映高处的蓝）
RIVER_EDGE = "#fffbe0"
CLUMP = ["#f1cc4c", "#fde67a", "#fff3bf"]
CLUMP_REFL = "#f3ecbe"
POOL = ["#fff0a0", "#fde88a", "#f4f0cc", "#dcefF3", "#c4e6f5", "#aedcf3", "#98d1ef"]
POOL_SAND = ["#fbe9a0", "#f8e290", "#f5ebc4", "#e9eccf", "#dde8d6", "#d0e2d7", "#c3dbd6"]   # 透出水底的沙
POOL_EDGE = "#fffbe2"
SURF = ["#fffbe8", "#eef6ef", "#d3ecf4"]
GLINT = ["#fffef6", "#f1fbff"]
# 会动的芦苇：每排一套色（stem 下 → 上、plume 背光淡蓝 → 明黄 → 受光奶黄、leaf）。离晨越近的排越浓一点
REED_PAL = {
    "r0": {"stem": ["#dcc66a", "#e0cb6c", "#e8d57a"], "plume": ["#bfe1f2", "#fde67a", "#fff4c2"], "leaf": ["#a9d3ea", "#e0cb6c"]},
    "r1": {"stem": ["#cfb34c", "#d5ba52", "#dbc05a"], "plume": ["#93cbec", "#f8d445", "#ffeb8e"], "leaf": ["#8cc3e3", "#cfb34c"]},
    "r2": {"stem": ["#c4a644", "#cab04a", "#d0b350"], "plume": ["#86c1e6", "#f3cb3e", "#fde27a"], "leaf": ["#7fb8de", "#c4a644"]},
    "f": {"stem": ["#b8a040", "#c0a346", "#c8ac4e"], "plume": ["#73b2dd", "#e9bf38", "#f8d866"], "leaf": ["#6caad6", "#b8a040"]},
}
# 每一帧的弯曲角度（度，正 = 往右弯）。0 附近密（风里轻摆一档只挪一两像素），越弯越疏
ANGLES_POS = [0, 2, 4, 7, 10, 14, 18, 23, 28, 34, 40, 47, 54, 62, 70, 78]
ANGLES = [-a for a in reversed(ANGLES_POS[1:])] + ANGLES_POS
BIRD = {"wing": "#5e6a80", "body": "#6f7a8e", "tail": "#8c96a6"}


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


def edge_diag_fill(img):
    """corner_fix 之后还剩的：同色两格只在角上碰、旁边一格是透明的 —— 把透明那格补成它（轮廓多长一格）"""
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


# ---------------------------------------------------------------- 画面（第二版：开阔的草甸，明黄和淡蓝交织，梦幻、概括）
def noise2(h, w, sx, sy, rng, period=None):
    """平滑的二维噪声（值噪声 + smoothstep），sx / sy 是一格多大（横向拉长 = 地面、天上那种横的色带）。period 给了就左右无缝。"""
    gw = (period // sx if period else w // sx + 2)
    gh = h // sy + 3
    g = rng.uniform(-1, 1, (gh, gw))
    ys = np.arange(h) / sy
    xs = np.arange(w) / sx
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    ty = ys - y0
    tx = xs - x0
    ty = ty * ty * (3 - 2 * ty)
    tx = tx * tx * (3 - 2 * tx)
    xa = x0 % gw if period else np.minimum(x0, gw - 1)
    xb = (x0 + 1) % gw if period else np.minimum(x0 + 1, gw - 1)
    a = g[y0][:, xa]
    b = g[y0][:, xb]
    c = g[y0 + 1][:, xa]
    d = g[y0 + 1][:, xb]
    top = a + (b - a) * tx[None, :]
    bot = c + (d - c) * tx[None, :]
    return top + (bot - top) * ty[:, None]


def fbm(h, w, sx, sy, rng, period=None, octaves=3):
    out = np.zeros((h, w))
    amp = 1.0
    tot = 0.0
    for o in range(octaves):
        p = period
        out += amp * noise2(h, w, max(2, sx >> o), max(2, sy >> o), rng, p)
        tot += amp
        amp *= 0.5
    return out / tot


def ramp_paint(idx):
    """色阶下标（可以是小数）→ 颜色。RAMP 从深金 → 明黄 → 奶白 → 淡蓝 → 蓝，黄和蓝之间隔着奶白，过渡是软的"""
    i = np.clip(np.round(idx), 0, len(RAMP) - 1).astype(int)
    pal = np.array([hexc(c) for c in RAMP])
    return pal[i]


def dabs(img, mask, rng, n, lmin, lmax, choose, period=None):
    """印象派的笔触：横向的短梭形（两头尖，中间 1–2 行），颜色由 choose(原色下标) 给。只落在 mask 里"""
    h, w = img.shape[:2]
    pal = [tuple(hexc(c)) for c in RAMP]
    for _ in range(n):
        x0 = int(rng.integers(0, w))
        y = int(rng.integers(0, h - 1))
        if not mask[y, x0]:
            continue
        here = tuple(img[y, x0])
        if here not in pal:
            continue
        k = choose(pal.index(here))
        if k is None:
            continue
        k = int(np.clip(k, 0, len(RAMP) - 1))
        c = hexc(RAMP[k])
        L = int(rng.integers(lmin, lmax + 1))
        thick = 2 if L >= 9 and rng.random() < 0.5 else 1
        for i in range(L):
            u = abs(i / max(1, L - 1) * 2 - 1)
            xx = (x0 + i) % w if period else x0 + i
            if not 0 <= xx < w:
                break
            if mask[y, xx]:
                img[y, xx] = c
            if thick == 2 and u < 0.55 and y + 1 < h and mask[y + 1, xx]:
                img[y + 1, xx] = c


def draw_sky():
    """天：一层层柔和的横向色带，淡蓝（上）→ 一道淡黄 → 淡蓝 → 地平线上一大片明黄的光。每两档之间插一两档过渡色，色带边微微起伏。
    左边低处一轮很淡的太阳（只是一团暖白的光，不画清楚的圆盘边）。"""
    rng = np.random.default_rng(11)
    w = 480
    img = blank(w, H)
    cols = []
    ys = []
    for i in range(len(SKY_STOPS) - 1):
        (y0, c0), (y1, c1) = SKY_STOPS[i], SKY_STOPS[i + 1]
        n = 3 if y1 - y0 > 18 else 2
        for k in range(n):
            ys.append(y0 + (y1 - y0) * k / n)
            cols.append(mix(hexc(c0), hexc(c1), k / n))
    ys.append(SKY_STOPS[-1][0])
    cols.append(hexc(SKY_STOPS[-1][1]))
    wob = [knots(w, 110, rng, 1.8) + knots(w, 37, rng, 0.6) for _ in ys]
    for x in range(w):
        for y in range(H):
            k = 0
            for i, y0 in enumerate(ys):
                if y >= y0 + (wob[i][x] if i else 0):
                    k = i
            img[y, x] = cols[k]
    # 太阳：地平线上方偏左，一团几圈越来越淡的暖光
    sx, sy = SUN
    base = img.copy()
    yy, xx = np.mgrid[0:H, 0:w]
    for (rx, ry), k in [((96, 46), 0.12), ((66, 32), 0.22), ((44, 22), 0.36), ((27, 14), 0.52), ((15, 8), 0.72), ((8, 5), 0.9)]:
        m = ((xx - sx) / rx) ** 2 + ((yy - sy) / ry) ** 2 <= 1
        for y, x in zip(*np.nonzero(m)):
            img[y, x] = mix(base[y, x], hexc(SUN_WARM), k)
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    return img


def draw_streaks():
    """很薄、很长的横向云层：两头尖的长条（2–4 行厚），在蓝的地方是奶黄的、在黄的地方是淡蓝的 —— 黄和蓝在天上也交织。左右无缝。"""
    rng = np.random.default_rng(23)
    w, h = 960, 130
    img = blank(w, h)
    for cx, cy, L, th, kind in [(140, 22, 360, 3, "y"), (520, 12, 300, 2, "w"), (760, 34, 420, 3, "y"), (300, 52, 260, 2, "b"),
                                (650, 66, 380, 3, "w"), (60, 84, 300, 2, "b"), (430, 98, 460, 3, "b"), (880, 108, 240, 2, "w"),
                                (220, 116, 330, 2, "b")]:
        topn = knots(L + 1, 60, rng, 1.0)
        cols = STREAK[kind]
        for i in range(L + 1):
            u = i / L * 2 - 1
            t = th * (1 - u * u) ** 0.9 + topn[i] * (1 - abs(u)) * 0.8
            top, bot = int(round(cy - t * 0.6)), int(round(cy + t * 0.4))
            if bot < top or t < 0.5:
                continue
            for y in range(top, bot + 1):
                if 0 <= y < h:
                    img[y, (cx - L // 2 + i) % w] = hexc(cols[0] if y <= (top + bot) // 2 else cols[1])
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    return img


def draw_far():
    """远处：草甸融成一条色带（明黄、奶白、淡蓝横着交织），上沿一点点起伏，几乎化进天里。左右无缝。"""
    rng = np.random.default_rng(31)
    w, h = 960, 34
    n = fbm(h, w, 96, 6, rng, period=960)
    top = 6 + knots(w, 80, rng, 2.0, period=960) + knots(w, 23, rng, 0.8, period=960)
    img = blank(w, h)
    yy = np.arange(h)[:, None]
    idx = 4 + n * 3.2 - (yy / h) * 1.2              # 越往下越黄（近一点）
    col = ramp_paint(np.clip(idx, 2, 6))
    for x in range(w):
        t = int(round(top[x]))
        img[t:, x] = col[t:, x]
        img[t:t + 1, x] = hexc(RAMP[4])               # 上沿一行奶白，化进天
    m = img[..., 3] > 0
    dabs(img, m, rng, 120, 8, 26, lambda k: {2: 4, 3: 5, 4: 3, 5: 3, 6: 4}.get(k), period=960)
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    edge_diag_fill(img)
    return img


def draw_mid():
    """中景（scroll 0.4，左右无缝）：一条横着的清澈的河。上岸、下岸是草甸（色块），河面映着天：远的一边映地平线的明黄，近的一边映高处的淡蓝，
    中间一道道两头尖的波纹把黄和蓝互相掺进去。（岸上的芦苇丛试过，远看像草垛，关掉了。）"""
    rng = np.random.default_rng(53)
    w, h = 960, 44
    img = blank(w, h)
    bank_top = 3 + knots(w, 70, rng, 1.6, period=960)
    r0 = 12 + knots(w, 120, rng, 1.2, period=960)          # 河的上沿
    r1 = 30 + knots(w, 140, rng, 1.5, period=960)          # 河的下沿
    n = fbm(h, w, 64, 6, rng, period=960)
    yy = np.arange(h)[:, None]
    grass = ramp_paint(np.clip(3.0 + n * 3.4 - (yy / h) * 1.0, 1, 7))
    for x in range(w):
        a, b, t = int(round(r0[x])), int(round(r1[x])), int(round(bank_top[x]))
        img[t:, x] = grass[t:, x]
        for y in range(a, b):
            u = (y - a) / max(1, b - a)
            k = min(len(RIVER) - 1, int(u * len(RIVER)))
            img[y, x] = hexc(RIVER[k])
        img[a, x] = hexc(RIVER_EDGE)
    # 河面上的波纹：两头尖的横条，取上一档 / 下一档的颜色（黄掺进蓝、蓝掺进黄）
    for _ in range(160):
        x0 = int(rng.integers(0, w))
        a, b = int(round(r0[x0])), int(round(r1[x0]))
        if b - a < 5:
            continue
        y = int(rng.integers(a + 2, b - 1))
        k = min(len(RIVER) - 1, int((y - a) / max(1, b - a) * len(RIVER)))
        k2 = k + (1 if rng.random() < 0.5 else -1)
        k2 = int(np.clip(k2 + (2 if rng.random() < 0.25 else 0) * (1 if k2 > k else -1), 0, len(RIVER) - 1))
        L = int(rng.integers(6, 26))
        for i in range(L):
            xx = (x0 + i) % w
            if int(round(r0[xx])) + 1 < y < int(round(r1[xx])):
                img[y, xx] = hexc(RIVER[k2])
    # 岸上的芦苇丛：软软的一团团（上圆下平），明黄 / 奶白，背光一侧淡蓝；水里倒影是压扁、偏蓝的一片
    for cx in rng.choice(np.arange(0, w, 24), 0, replace=False):     # 第二版不画岸上的芦苇丛（远看像草垛），留着写法
        cx = int(cx + rng.integers(-8, 8))
        cw = int(rng.integers(10, 26))
        ch = int(rng.integers(5, 11))
        base = int(round(r0[cx % w]))
        for i in range(-cw // 2, cw // 2 + 1):
            u = i / (cw / 2)
            hh = ch * max(0.0, 1 - u * u) ** 0.6
            for d in range(int(round(hh))):
                y = base - d
                c = CLUMP[0] if u > 0.35 else CLUMP[2] if d > hh * 0.55 else CLUMP[1]
                img[max(0, y), (cx + i) % w] = hexc(c)
            for d in range(1, int(round(hh * 0.5)) + 1):
                y = base + d
                if y < int(round(r1[(cx + i) % w])) - 1:
                    img[y, (cx + i) % w] = hexc(CLUMP_REFL)
    m = img[..., 3] > 0
    river = np.zeros_like(m)
    for x in range(w):
        river[int(round(r0[x])):int(round(r1[x])), x] = True
    dabs(img, m & ~river, rng, 120, 6, 18, lambda k: k + (1 if rng.random() < 0.5 else -1) if 1 <= k <= 6 else None, period=960)
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    return img, r0, r1


def in_water(x):
    return any(a <= x <= b for a, b in WATERS)


def water_amt(x):
    """这一列有多「水」：水段中间 1，边上 50 像素里平滑过渡（岸是弯的，不切竖直一刀）"""
    best = 0.0
    for a, b in WATERS:
        best = max(best, sstep(a - 30, a + 40, x) * (1 - sstep(b - 40, b + 30, x)))
    return best


def draw_main():
    """晨这一层（第三版）：绵绵软软的一整片草甸 —— 一排排横着的、软软鼓起来的草团（像厚绒毯、一团团起伏的云），
    从后往前一排压一排，每团只露出上面那一道圆弧：顶上一两行受光（奶白），身子淡黄或淡蓝，下面一档浅灰。看不到根，也没有一根根的草。
    颜色：每一团按一张大的噪声决定偏黄 / 偏奶白 / 偏蓝，黄蓝交织，都很淡。晨身后那一带（脚底往上 8–56 行）用淡灰黄（暖），晨的淡紫白头发、砖红斗篷在上面跳出来。
    两段浅水（POOLS）：清澈的浅水塘，按离地平线多远分一道道横的映天色带（远的一边淡黄、近处淡蓝），近处透出一点水底的沙色，波纹黄蓝互掺。
    返回：图、草甸上沿、地面、水上沿、这一列的路是不是在水里、每个像素是哪一排草团画的（row_base：芦苇根前面的草团层用）。"""
    rng = np.random.default_rng(67)
    img = blank(W, H)
    gy = np.array([ground(x) for x in range(W)])
    top = MEADOW_TOP + knots(W, 110, rng, 2.0) + knots(W, 33, rng, 0.8)
    row_base = np.full((H, W), -1, int)
    fam = fbm(H, W, 120, 36, rng)
    xs = np.arange(W)
    # 一排排草团（后 → 前）
    y_b = float(MEADOW_TOP + 6)
    rows = []
    while y_b < H + 14:
        rows.append(y_b)
        y_b += rng.uniform(9.0, 15.0)
    for rb in rows:
        x = -60.0 - rng.uniform(0, 40)
        while x < W + 60:
            w = rng.uniform(80, 210)
            h = rng.uniform(8, 19)
            cx = x + w / 2
            base = rb + rng.uniform(-1.5, 1.5)
            if rb < MEADOW_TOP + 10:
                base = max(base, float(np.interp(cx, xs, top)) + h * 0.7)     # 最后一排的顶贴着草甸上沿
            x0, x1 = int(max(0, cx - w / 2)), int(min(W, cx + w / 2 + 1))
            if x1 > x0:
                f = fam[int(np.clip(base, 0, H - 1)), int(np.clip(cx, 0, W - 1))]
                near = (gy[int(np.clip(cx, 0, W - 1))] - 56) <= base <= (gy[int(np.clip(cx, 0, W - 1))] - 8)
                if near:
                    tones = [RAMP[0], RAMP[1], RAMP[3]]          # 晨身后：淡灰黄（暖）
                elif f < -0.12:
                    tones = [RAMP[1], RAMP[2], RAMP[4]]          # 偏黄
                elif f > 0.22:
                    tones = [RAMP[7], RAMP[6], RAMP[4]]          # 偏蓝
                else:
                    tones = [RAMP[2], RAMP[3], RAMP[4]] if f < 0.05 else [RAMP[6], RAMP[5], RAMP[4]]   # 奶白偏黄 / 偏蓝
                cols = np.arange(x0, x1)
                u = (cols - cx) / (w / 2)
                ok = np.abs(u) <= 1
                ytop = base - h * np.sqrt(np.clip(1 - u * u, 0, 1))
                t0 = int(max(0, np.floor(ytop[ok].min()))) if ok.any() else H
                if t0 < H:
                    Y = np.arange(t0, H)[:, None]
                    yt = np.round(ytop)[None, :]
                    m = ok[None, :] & (Y >= yt)
                    d = Y - ytop[None, :]
                    lit = np.where(u < 0.25, 1.4 + 0.8 * (u < -0.4), -1.0)[None, :]   # 光从左上：只有左上那段圆弧亮一道
                    k = np.where(d < lit, 2, np.where(d < h * 0.9, 1, 0))
                    pal = np.array([hexc(c) for c in tones])
                    sub = img[t0:H, x0:x1]
                    sub[m] = pal[k][m]
                    rb_sub = row_base[t0:H, x0:x1]
                    rb_sub[m] = int(base)
            x += w * rng.uniform(0.5, 0.85)
    # 草甸上沿以上清掉（最后一排草团可能鼓出来一点：留着，那就是起伏的上沿）
    # 浅水塘
    field = np.full((H, W), -9.0)
    yy, xx = np.mgrid[0:H, 0:W]
    for pool in POOLS:
        for (cx, cy, rx, ry) in pool:
            e = 1 - ((xx - cx) / rx) ** 2 - ((yy - cy) / ry) ** 2
            field = np.maximum(field, e)
    field += fbm(H, W, 64, 16, rng) * 0.22
    water_m = (field > 0) & (yy > top[None, :] + 6)
    wtop = np.full(W, H + 2, int)
    for x in range(W):
        col = water_m[:, x]
        if col.any():
            wtop[x] = int(np.argmax(col))
    for _ in range(300):
        before = wtop.copy()
        for x in range(1, W):
            if abs(wtop[x] - wtop[x - 1]) > 2:
                m = max(wtop[x], wtop[x - 1]) - 2
                if wtop[x] < m:
                    wtop[x] = m
                if wtop[x - 1] < m:
                    wtop[x - 1] = m
        if (before == wtop).all():
            break
    water_m[:] = False
    for x in range(W):
        if wtop[x] < H:
            water_m[wtop[x]:, x] = True
    ws = np.array([1.0 if water_m[min(H - 1, gy[x] + 1), x] else 0.0 for x in range(W)])
    sand = fbm(H, W, 26, 7, rng)
    wwob = fbm(H, W, 90, 30, rng) * 3.0
    for x in range(W):
        a = wtop[x]
        if a >= H:
            continue
        for y in range(a, H):
            u = float(np.clip((y + wwob[y, x] - W_TOP) / (H - W_TOP), 0, 1))
            k = min(len(POOL) - 1, int(u ** 0.8 * len(POOL)))
            c = POOL[k]
            if u > 0.35 and sand[y, x] > 0.18:
                c = POOL_SAND[k]
            img[y, x] = hexc(c)
            row_base[y, x] = y
        img[a, x] = hexc(POOL_EDGE)
    # 水面的波纹：两头尖的横条，取相邻一档（黄蓝互掺）
    for _ in range(900):
        x0 = int(rng.integers(0, W))
        y = int(rng.integers(0, H))
        if not water_m[y, x0] or y <= wtop[x0] + 1:
            continue
        u = float(np.clip((y - W_TOP) / (H - W_TOP), 0, 1))
        k = min(len(POOL) - 1, int(u ** 0.8 * len(POOL)))
        k2 = int(np.clip(k + rng.choice([-2, -1, 1, 1, 2]), 0, len(POOL) - 1))
        L = int(rng.integers(5, 24))
        for i in range(L):
            xx2 = x0 + i
            if xx2 < W and water_m[y, xx2] and y > wtop[xx2] + 1:
                img[y, xx2] = hexc(POOL[k2])
    # 草甸最上沿：极少的几处毛边（1 像素宽、1–2 高，和下面同色）
    for _ in range(40):
        x = int(rng.integers(2, W - 2))
        col = img[:, x, 3] > 0
        if not col.any():
            continue
        t = int(np.argmax(col))
        if t < 2 or water_m[t, x]:
            continue
        for k in range(1, int(rng.integers(1, 3)) + 1):
            img[t - k, x] = img[t, x]
            row_base[t - k, x] = row_base[t, x]
    # 草甸上沿：两团草的圆弧接在一起的地方可能一下差好几行（直角台阶），往上补成一道最多差 2 的缓坡
    t2 = np.array([int(np.argmax(img[:, x, 3] > 0)) for x in range(W)])
    for _ in range(50):
        ch = False
        for x in range(1, W):
            for (p, q) in ((x - 1, x), (x, x - 1)):
                if t2[q] - t2[p] > 2:
                    ny = t2[p] + 2
                    img[ny:t2[q], q] = img[t2[q], q]
                    row_base[ny:t2[q], q] = row_base[t2[q], q]
                    t2[q] = ny
                    ch = True
        if not ch:
            break
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    edge_diag_fill(img)
    top2 = np.array([int(np.argmax(img[:, x, 3] > 0)) for x in range(W)])
    return img, top2, gy, wtop, ws, row_base


def mound(img, a, b, base_fn, height, rng, lean=0.0):
    """芦苇丛里鼓起来的一大团绒绒的草（盖住芦苇下半截的秆，芦苇像是从草堆里长出来的）：顶是几个圆包连起来的起伏，
    受光的左上一道亮边，身子明黄，往下深一档。轮廓相邻两列最多差 2。"""
    n = b - a + 1
    xs = np.arange(n)
    u = xs / max(1, n - 1)
    env = np.sin(np.pi * u) ** 0.7
    lumps = np.zeros(n)
    for _ in range(int(rng.integers(3, 6))):
        c = rng.uniform(0.1, 0.9)
        w = rng.uniform(0.12, 0.3)
        lumps += rng.uniform(0.15, 0.35) * np.clip(1 - ((u - c) / w) ** 2, 0, None) ** 0.5
    hgt = height * env * (0.75 + lumps)
    prev = None
    for i in range(n):
        x = a + i
        if not 0 <= x < W:
            continue
        b0 = int(base_fn(x))
        t = int(round(b0 - hgt[i]))
        if prev is not None:
            t = int(np.clip(t, prev - 2, prev + 2))
        prev = t
        tones = [RAMP[2], RAMP[3], RAMP[4]]      # 一整团同一套暖色（按列换色会切出竖直的接缝）
        slope = (hgt[i + 1] - hgt[i - 1]) if 0 < i < n - 1 else 0.0
        rim = 2 if slope > 0.15 else 1          # 往右上升的那一侧（朝左上的光）亮边宽一点
        for y in range(max(0, t), min(H, b0 + 3)):
            d = y - t
            c = tones[2] if d < rim else tones[1] if d < hgt[i] * 0.55 + 2 else tones[0]
            img[y, x] = hexc(c)


def draw_root_cover(main, row_base, ranges, ylo_fn, yhi_fn):
    """芦苇根前面那一层草团（z 在这一排芦苇前面）：抄 main 的像素，只取「前面那几排草团」画的那部分（row_base ≥ ylo），
    所以上沿就是草团的圆弧 —— 芦苇像是从绒绒的草里长出来的，看不到根。只在芦苇丛的 x 范围里（别处不盖 main 上的亮纹）。"""
    img = blank(W, H)
    for (a, b) in ranges:
        for x in range(max(0, a), min(W, b + 1)):
            lo, hi = ylo_fn(x), yhi_fn(x)
            for y in range(0, min(H, hi + 1)):
                if row_base[y, x] >= lo and main[y, x, 3]:
                    img[y, x] = main[y, x]
    return img


def draw_ankle(main, gy, ws):
    """没过脚踝的一层（在晨前面画，z 20）：草地上从脚底往上 3–6 行，颜色直接抄 main 同一位置的草（平时和后面的草甸连成一片看不出来，
    晨走进去时脚踝埋在草里）。上沿是起伏的草丛顶（相邻两列最多差 1），顶上一行亮一档（草尖受光）。水里不画（ankle_water 管）。"""
    rng = np.random.default_rng(71)
    img = blank(W, H)
    hgt = 4.4 + knots(W, 11, rng, 1.4) + knots(W, 41, rng, 0.7)
    pal = [tuple(hexc(c)) for c in RAMP]
    prev = None
    for x in range(W):
        if ws[x] > 0.5:
            prev = None
            continue
        t = int(round(gy[x] - hgt[x]))
        if prev is not None:
            t = int(np.clip(t, prev - 1, prev + 1))
        prev = t
        b = int(gy[x]) + 3
        img[t:b + 1, x] = main[t:b + 1, x]
        here = tuple(img[t, x])
        if here in pal:
            k = pal.index(here)
            img[t, x] = hexc(RAMP[3] if k <= 3 else RAMP[4] if k == 4 else RAMP[5])
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    alpha_fix(img)
    edge_diag_fill(img)
    return img


def draw_ankle_water(gy, ws):
    """水里那一段没过脚踝的水面（在晨前面画，z 21，层的 alpha 0.6）：水面线在脚底上方 3 行，一道连续、微微起伏的亮线，
    下面几行是映着天的水色（黄蓝两档交替的长条）。半透明：脚在水下看得见，颜色被水染了。"""
    rng = np.random.default_rng(73)
    img = blank(W, H)
    wav = knots(W, 13, rng, 0.7)
    band = 2.5 + knots(W, 23, rng, 1.2)
    for x in range(W):
        if ws[x] < 0.45:
            continue
        s = int(round(gy[x] - 3 + wav[x]))
        img[s, x] = hexc(SURF[0])
        for y in range(s + 1, int(gy[x]) + 6):
            img[y, x] = hexc(SURF[1] if y - s <= band[x] else SURF[2])
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    return img


def draw_glints_main(gy, ws, wtop):
    """浅水上的亮纹（water shader 让它晃、时有时无）：横的短段，长短不一、随机散开（不等距），黄白和淡蓝白两种"""
    rng = np.random.default_rng(79)
    img = blank(W, H)
    placed = 0
    for _ in range(4000):
        if placed > 150:
            break
        x = int(rng.integers(0, W - 10))
        if wtop[x] > H - 8:
            continue
        y = int(rng.integers(max(wtop[x] + 3, 0), H - 1))
        if abs(y - gy[x]) < 5:
            continue
        L = int(rng.integers(2, 8))
        if img[max(0, y - 1):y + 2, max(0, x - 2):x + L + 2, 3].any() or y < wtop[x + L] + 3:
            continue
        img[y, x:x + L] = hexc(GLINT[0] if rng.random() < 0.5 else GLINT[1])
        placed += 1
    return img


def draw_glints_mid(r0, r1):
    rng = np.random.default_rng(81)
    w, h = 960, 44
    img = blank(w, h)
    placed = 0
    for _ in range(3000):
        if placed > 60:
            break
        x = int(rng.integers(0, w - 8))
        a, b = int(round(r0[x])), int(round(r1[x]))
        if b - a < 6:
            continue
        y = int(rng.integers(a + 2, b - 1))
        L = int(rng.integers(2, 6))
        if img[max(0, y - 1):y + 2, max(0, x - 2):x + L + 2, 3].any():
            continue
        img[y, x:x + L] = hexc(GLINT[0] if rng.random() < 0.5 else GLINT[1])
        placed += 1
    return img


# ---------------------------------------------------------------- 会动的芦苇：每种在每个角度下画一帧
def reed_variants():
    """每排几种：L 总长（含穗）、P 穗长、PW 穗宽、nod 平时穗往右垂多少度、strands 穗下沿垂下来的几缕穗丝、
    leaves [(在秆的几成处, 左右, 长, 弧)]"""
    rng = np.random.default_rng(83)
    out = {}
    #       种数  总长        穗长      穗宽         点头
    spec = {"r0": (6, (40, 84), (16, 21), (5.2, 6.6), (62, 88)),
            "r1": (7, (22, 56), (12, 17), (4.4, 5.6), (52, 78)),
            "r2": (5, (14, 26), (8, 11), (2.2, 2.8), (44, 64)),
            "f": (4, (50, 76), (15, 19), (4.8, 6.0), (56, 80))}
    for row, (n, lr, pr, wr, nr) in spec.items():
        for i in range(n):
            L = int(round(lr[0] + (lr[1] - lr[0]) * (i / max(1, n - 1)) + rng.uniform(-2, 2)))
            P = int(rng.integers(pr[0], pr[1] + 1))
            PW = float(rng.uniform(*wr))
            leaves = []
            nl = int(rng.integers(0, 2)) if row in ("r0", "r1") else int(rng.integers(1, 3))
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


def place_reeds(vs, top, gy):
    """芦苇聚成几大片（R0_MASSES、R1_MASSES）：每片里密密地一根挨一根（隔 1.6–2.6 像素），高矮按一个圆顶的包络排（中间高、两头矮），
    穗头连成一条软软的淡色带，像起伏的一大团；根埋在前面的草团里（cover_r0 / cover_r1）。片和片之间是开阔的草地。
    前景（f，scroll 1.25）两三团。路前面（r2）不放（第二版那种孤零零的一根根，作者不要）。"""
    rng = np.random.default_rng(97)
    names = {r: sorted([n for n in vs if vs[n]["row"] == r], key=lambda n: vs[n]["L"]) for r in ("r0", "r1", "r2", "f")}
    out = {"r0": [], "r1": [], "r2": [], "f": []}

    def mass(row, a, b, ybase):
        n = len(names[row])
        bump = knots(b - a + 1, 30, rng, 0.18)
        x = a + rng.uniform(0, 2)
        while x < b:
            xi = int(x)
            env = math.sin(math.pi * (x - a) / (b - a)) ** 0.6 + bump[xi - a]
            k = int(np.clip(round(env * (n - 1) + rng.uniform(-1.2, 1.2)), 0, n - 1))
            out[row].append([xi, int(ybase(xi)), names[row][k], round(float(rng.uniform(0, 6.28)), 2)])
            x += rng.uniform(1.6, 2.6)

    for a, b in R0_MASSES:
        mass("r0", a, b, lambda x: top[x] + rng.integers(12, 20))
    for a, b in R1_MASSES:
        mass("r1", a, b, lambda x: gy[x] - rng.integers(4, 9))
    fw = 480 + (W - 480) * 1.25
    for (a, b) in FRONT_MASSES:
        if b < fw:
            mass("f", a, b, lambda x: rng.integers(286, 296))
    for r in out:
        out[r].sort(key=lambda t: t[0])
    return out


# ---------------------------------------------------------------- room.json
def room_json():
    layers = [
        {"id": "sky", "img": "sky.png", "scroll": 0.0, "y": 0},
        {"id": "streaks", "img": "streaks.png", "scroll": 0.03, "y": 10, "tile": True, "drift": -1.0},
        {"id": "far", "img": "far.png", "scroll": 0.12, "y": 132, "tile": True, "shader": "sway",
         "shader_params": {"amp": 1.0, "speed": 0.7, "wavelength": 240.0, "power": 1.2, "bend": 0.0}},
        {"id": "mid", "img": "mid.png", "scroll": 0.4, "y": 142, "tile": True},
        {"id": "mid_glints", "img": "mid_glints.png", "scroll": 0.4, "y": 142, "tile": True, "shader": "water",
         "shader_params": {"palette_mode": False, "speed": 0.6, "wobble": 1.0, "flicker": 0.0, "show": 0.55}},
        {"id": "main", "img": "main.png", "scroll": 1.0, "y": 0},
        {"id": "glints", "img": "glints.png", "scroll": 1.0, "y": 0, "shader": "water",
         "shader_params": {"palette_mode": False, "speed": 0.8, "wobble": 1.0, "flicker": 0.0, "show": 0.6}},
        {"id": "cover_r0", "img": "cover_r0.png", "scroll": 1.0, "y": 0, "z": -36},
        {"id": "cover_r1", "img": "cover_r1.png", "scroll": 1.0, "y": 0, "z": -26},
        {"id": "ankle", "img": "ankle.png", "scroll": 1.0, "y": 0, "z": 20},
        {"id": "cover_f", "img": "cover_f.png", "scroll": 1.25, "y": 0, "z": 111},
        {"id": "ankle_water", "img": "ankle_water.png", "scroll": 1.0, "y": 0, "z": 21, "alpha": 0.6},
    ]
    return {
        "_note": ("tools/reed_field_art.py 生成，别手改（要改先改脚本）。云层星的芦苇地（第三章；结局一、结局二的 yard / east_meadow 都改成这张）。"
                  "第二版：开阔的草甸，明黄 + 淡蓝交织，梦幻概括；浅草 / 浅水没过晨的脚踝（ankle / ankle_water 在晨前面）。"
                  "会动的芦苇、惊鸟、晨在水里的倒影、晨身后压暗是 scripts/reed_field.gd（scripts 里），数据在 reeds.json / birds.json。"
                  "约定见 docs/river_rooms_contract.md。"),
        "_note_town": f"草原小镇留在 x {TOWN[0]}–{TOWN[1]}：地是平的（ground {ground(TOWN[0])}），这一段没有成丛的芦苇、没有水，"
                      "只是平缓的草地。小镇的房子画在这一段，放进 main 和 glints 之间一层（scroll 1，z 不写，在晨后面）；"
                      "脚踝的草丛（ankle.png）在这一段照常有。",
        "size": [W, H],
        "origin": [0, 1080],
        "env": "reeds",
        "bg": ["#9dd2f1", "#fff0a8"],
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
                                "spots": [[SPOTS[0], 6], [SPOTS[1], 5], [SPOTS[2], 6]],
                                "water": [list(w) for w in WATERS]}}],
    }


# ---------------------------------------------------------------- 预览：按 room.json 叠一屏 + 芦苇 + 晨（含倒影、身后压暗，近似 reed_field.gd）
SHADE_RINGS = [((44, 54), 0.99), ((35, 45), 0.98), ((27, 36), 0.97), ((20, 28), 0.962), ((13, 21), 0.955)]   # 晨身后压暗（和 reed_field.gd 一样）


def compose(layers_img, atlas, meta, place, cl, chen_x=None, theta_fn=None, birds=None, bmeta=None, chen_frame=18):
    j = room_json()
    out = np.zeros((H, 480, 4), np.uint8)
    out[...] = hexc(j["bg"][0])

    def blit(src, x, y, alpha=1.0):
        h, w = src.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(480, x + w), min(H, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        s = src[y0 - y:y1 - y, x0 - x:x1 - x]
        m = s[..., 3] > 0
        if alpha >= 1.0:
            out[y0:y1, x0:x1][m] = s[m]
        else:
            d = out[y0:y1, x0:x1].astype(float)
            d[m, :3] = d[m, :3] * (1 - alpha) + s[m, :3].astype(float) * alpha
            out[y0:y1, x0:x1] = np.round(d).astype(np.uint8)

    def layer(L):
        im = layers_img[L["id"]]
        sc = L.get("scroll", 1.0)
        x = round(L.get("x", 0) - cl * sc)
        a = L.get("alpha", 1.0)
        if L.get("tile"):
            w = im.shape[1]
            x = x % w - w
            while x < 480:
                blit(im, x, L["y"], a)
                x += w
        else:
            blit(im, x, L["y"], a)

    def reeds(row, sc):
        for (x, y, vn, ph) in place[row]:
            sx = round(x - cl * sc)
            if sx < -100 or sx > 580:
                continue
            v = meta["variants"][vn]
            th = theta_fn(row, x, sx) if theta_fn else 3.0 + v["rest"]
            i = int(np.argmin([abs(a - th) for a in meta["angles"]]))
            fx, fy, fw, fh, ox, oy, _, _ = v["frames"][i]
            blit(atlas[fy:fy + fh, fx:fx + fw], sx + ox, y + oy)

    sheet = np.array(Image.open(ROOT / "art/characters/chen/chen_oscar.png").convert("RGBA"))
    fr = sheet[:, chen_frame * 68:(chen_frame + 1) * 68]

    def do_birds():
        if birds is not None:
            for (bx, by, idx) in birds:
                cw, ch = bmeta["cell"]
                blit(birds_img_global[0][:, idx * cw:(idx + 1) * cw], round(bx - cl - cw // 2), by - ch + 1)

    def do_shade():
        if chen_x is None:
            return
        gx, g = round(chen_x - cl), ground(chen_x)
        yy, xx = np.mgrid[0:H, 0:480]
        for (rx, ry), k in SHADE_RINGS:          # 从外到里，每圈「以内一共乘多少」
            m = ((xx - gx) / rx) ** 2 + ((yy - (g - 24)) / ry) ** 2 <= 1
            out[m, :3] = np.round(out[m, :3] * (k / prev_k(k))).astype(np.uint8)

    def prev_k(k):
        ks = [1.0] + [r[1] for r in SHADE_RINGS]
        return ks[ks.index(k) - 1]

    def do_refl():
        if chen_x is None or not in_water(chen_x):
            return
        gx, g = round(chen_x - cl), ground(chen_x)
        ref = fr[::-1].copy()
        m = ref[..., 3] > 0
        ref[m, :3] = np.round(ref[m, :3] * 0.55 + np.array([196, 228, 244]) * 0.45).astype(np.uint8)
        blit(ref, gx - 26, g, alpha=0.42)

    def do_chen():
        if chen_x is not None:
            blit(fr, round(chen_x - cl) - 26, ground(chen_x) - 58)

    items = []
    for i, L in enumerate(j["layers"]):
        items.append((L.get("z", -100 + i), i, lambda L=L: layer(L)))
    items += [(-40, 0, lambda: reeds("r0", 1.0)), (-30, 0, lambda: reeds("r1", 1.0)), (5, 0, lambda: reeds("r2", 1.0)),
              (110, 0, lambda: reeds("f", 1.25)), (-29, 0, do_birds), (-3, 0, do_refl), (-2, 0, do_shade), (0, 0, do_chen)]
    for _z, _i, fn in sorted(items, key=lambda t: (t[0], t[1])):
        fn()
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
    print("画：天、横云、远景、中景的河、草甸、浅水、脚踝……")
    imgs["sky"] = draw_sky()
    imgs["streaks"] = draw_streaks()
    imgs["far"] = draw_far()
    imgs["mid"], r0, r1 = draw_mid()
    imgs["mid_glints"] = draw_glints_mid(r0, r1)
    imgs["main"], top, gy, wtop, ws, row_base = draw_main()
    global WATERS
    WATERS = []
    x = 0
    while x < W:
        if ws[x] > 0.5:
            a = x
            while x < W and ws[x] > 0.5:
                x += 1
            WATERS.append((a, x - 1))
        x += 1
    print("  路泡在水里的段：", WATERS)
    imgs["glints"] = draw_glints_main(gy, ws, wtop)
    imgs["ankle"] = draw_ankle(imgs["main"], gy, ws)
    imgs["ankle_water"] = draw_ankle_water(gy, ws)
    print("画：芦苇的弯曲帧、鸟……")
    atlas, meta, vs = build_reeds()
    place = place_reeds(vs, top, gy)
    rngm = np.random.default_rng(89)
    imgs["cover_r0"] = draw_root_cover(imgs["main"], row_base, [(a - 20, b + 20) for a, b in R0_MASSES],
                                       lambda x: int(top[x]) + 10, lambda x: int(top[x]) + 34)
    for a, b in R0_MASSES:                       # 后面那一大片：草堆盖住下半截（约四成高）
        mound(imgs["cover_r0"], a - 14, b + 14, lambda x: int(top[x]) + 18, 30, rngm)
    imgs["cover_r1"] = draw_root_cover(imgs["main"], row_base, [(a - 20, b + 20) for a, b in R1_MASSES],
                                       lambda x: int(gy[x]) - 10, lambda x: int(gy[x]) - 1)
    for a, b in R1_MASSES:
        mound(imgs["cover_r1"], a - 10, b + 10, lambda x: int(gy[x]) - 5, 19, rngm)
    # 前景（scroll 1.25）的芦苇丛也埋在一团草里
    fwid = int(480 + (W - 480) * 1.25)
    imgs["cover_f"] = blank(fwid, H)
    for (fa, fb) in FRONT_MASSES:
        mound(imgs["cover_f"], fa - 12, fb + 12, lambda x: 276, 30, rngm)
    for k in ("cover_r0", "cover_r1", "cover_f"):
        corner_fix(imgs[k])
        speck_fix(imgs[k])
        corner_fix(imgs[k])
        edge_diag_fill(imgs[k])
    birds, bmeta = build_birds()
    birds_img_global[0] = birds

    print("自查：")
    bad = 0
    for k in ("sky", "streaks", "far", "mid", "main", "ankle", "ankle_water", "cover_r0", "cover_r1", "cover_f"):
        bad += scan(k, imgs[k], alpha_only=False)
        bad += dashes(k, imgs[k])
    for k in ("glints", "mid_glints"):
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
    tops = [int(np.argmax(imgs["main"][:, x, 3] > 0)) for x in range(W)]
    st = [(x, tops[x + 1] - tops[x]) for x in range(W - 1) if abs(tops[x + 1] - tops[x]) > 2]
    print("  草甸上沿：相邻两列跳 ≥3 像素（直角台阶嫌疑）", st[:10])

    def save(arr, name):
        rel = (OUT / name).relative_to(ROOT).as_posix()
        if rel in locked:
            print("跳过（作者手改，见 art/手改清单.json）:", rel)
            return
        Image.fromarray(arr, "RGBA").save(OUT / name)

    # 第一版的图，这一版不用了
    for old in ("wisps.png", "clouds.png", "lake.png", "sunpath.png"):
        q = OUT / old
        if q.exists() and q.relative_to(ROOT).as_posix() not in locked:
            q.unlink()
            imp = OUT / (old + ".import")
            if imp.exists():
                imp.unlink()
    for k, v in imgs.items():
        save(v, k + ".png")
    save(atlas, "reeds.png")
    save(birds, "birds.png")
    for name, data in (("reeds.json", {**meta, "rows": place}), ("birds.json", bmeta), ("room.json", room_json())):
        rel = (OUT / name).relative_to(ROOT).as_posix()
        if rel not in locked:
            (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=1 if name == "room.json" else None) + "\n", encoding="utf-8")
    print("ok reed_field", W, H, "芦苇", {r: len(v) for r, v in place.items()}, "种类", len(vs), "atlas", atlas.shape[1], "×", atlas.shape[0],
          "问题", bad)

    if args.preview:
        pv = Path(args.preview)
        pv.mkdir(parents=True, exist_ok=True)
        # 1 倍全图：镜头从左到右四屏拼起来（视差层每屏各算各的，屏和屏之间远景会错开），每屏中间站一个晨
        shots = [compose(imgs, atlas, meta, place, cl, chen_x=cl + 240) for cl in (0, 480, 960, 1440)]
        full = np.concatenate(shots, axis=1)
        Image.fromarray(full).save(pv / "full_1x.png")
        for i, s in enumerate(shots):
            Image.fromarray(s).resize((480 * 2, H * 2), Image.NEAREST).save(pv / f"screen{i}_2x.png")
        # 晨所在位置 3 倍局部：草地里一张、水里一张
        for name, cxr in (("chen_grass", 160), ("chen_water", 700)):
            cl = cxr - 240
            s = compose(imgs, atlas, meta, place, cl, chen_x=cxr)
            crop = s[130:270, 160:320]
            Image.fromarray(crop).resize((crop.shape[1] * 3, crop.shape[0] * 3), Image.NEAREST).save(pv / f"{name}_3x.png")
        Image.fromarray(atlas).resize((atlas.shape[1] * 3, atlas.shape[0] * 3), Image.NEAREST).save(pv / "reeds_3x.png")
        print("预览:", pv)


if __name__ == "__main__":
    main()
