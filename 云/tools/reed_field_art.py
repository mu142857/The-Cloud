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
WATERS = [(0, W)]                       # 路泡在水里的段（画完按真的水算，见 main()）
TOWN = (1110, 1490)                     # 留给草原小镇
SPOTS = [330, 860, 1320]                # 惊鸟的地方（房间 x）：草那一片、芦苇那一片、开花草那一片（鸟也能歇在草丛顶上）
SUN = (150, 112)                        # 太阳光（屏幕坐标，天是钉在屏幕上的）
W_TOP = 198                             # 亮纹从这一行往下放


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
# 第五版（作者：「天的颜色和水的一样了，允许在水这里加一些绿，郁郁葱葱的湿地」）：水带一点清澈的青绿底，和天的淡蓝拉开
RIVER = ["#f6f0a6", "#e9eeae", "#d6eabe", "#c0e3c9", "#aad9cc", "#98d0c9"]       # 远（映地平线的黄，带一点嫩绿）→ 近（青绿）
RIVER_EDGE = "#fffbe0"
CLUMP = ["#f1cc4c", "#fde67a", "#fff3bf"]
CLUMP_REFL = "#f3ecbe"
POOL = ["#f6efa2", "#e6ecaa", "#d4e8bc", "#c2e2c8", "#b0dccd", "#a0d4cd", "#90cbc8"]
POOL_SAND = ["#f2e9a0", "#e2e4a8", "#d6e1b8", "#cadcbe", "#c0d8c0", "#b6d2c0", "#acccbd"]   # 透出水底的沙
POOL_EDGE = "#fbf9dc"
SURF = ["#fbfcec", "#e4f3e2", "#c6e7d8"]
# 水边的绿：嫩绿 → 薄荷 → 浅青绿，饱和度不高。GREEN 按 RAMP 的明暗一档对一档（岸上的黄草走到水边慢慢换成它）
GREEN = ["#a6cf7c", "#b8d98a", "#cbe39c", "#dcecb2", "#ecf4d2", "#e2f2e0", "#c8e8d4", "#addcc6", "#94cfb8"]
REFL_TONES = ["#9ccc8a", "#cde4a8"]
POOL_SET: set = set()                    # 水的颜色（植物带的倒影只落在水上），main() 开头填
PAD_SET: set = set()       # 水边的草在水里的倒影：深、浅两档（再混进水色）
YGREEN = ["#cdcb58", "#d8d466", "#e4df74", "#eeea96", "#f6f4c8", "#e0f0e6", "#c2e4e2", "#a2d6d6", "#88c8cc"]   # 黄和绿中间那一档
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


def de_alt(img, passes=2):
    """一格一格交替的细碎（像点线）：一格的左右同色、上下都不是它 → 并进左右；上下同色、左右都不是它 → 并进上下。
    只动不透明的格子。"""
    h, w = img.shape[:2]
    for _ in range(passes):
        a = img[..., 3] > 0
        key = (img[..., 0].astype(np.int64) << 16) | (img[..., 1].astype(np.int64) << 8) | img[..., 2]
        key = np.where(a, key, -1)
        c = key[1:-1, 1:-1]
        L, Rr, U, D = key[1:-1, :-2], key[1:-1, 2:], key[:-2, 1:-1], key[2:, 1:-1]
        hor = (c != -1) & (L == Rr) & (L != c) & (L != -1) & (U != c) & (D != c)
        ver = (c != -1) & (U == D) & (U != c) & (U != -1) & (L != c) & (Rr != c) & ~hor
        # 一像素细线上的一格缺口：左右同色、上下都不是那条线的颜色（那就是一条横的细线），中间这格补成线的颜色；竖线同理
        gap_h = (c != -1) & (L == Rr) & (L != c) & (L != -1) & (U != L) & (D != L) & ~hor
        gap_v = (c != -1) & (U == D) & (U != c) & (U != -1) & (L != U) & (Rr != U) & ~ver & ~hor & ~gap_h
        ys, xs = np.nonzero(hor | gap_h)
        img[ys + 1, xs + 1] = img[ys + 1, xs]
        ys, xs = np.nonzero(ver | gap_v)
        img[ys + 1, xs + 1] = img[ys, xs + 1]


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


# ---------------------------------------------------------------- 远景（第八版：作者「背景缺乏层次感，你现在只有一层山」）
# 从远到近四层，每层的明度、颜色、清晰度、视差都不一样，互相遮挡，层和层之间夹一条薄雾：
#   mtn_far   最远的高山：很淡，几乎化进天里，峰高、圆（scroll 0.008）
#   mtn_mid   次远的山：深一点、矮一点、起伏的节奏和最远那层不一样（scroll 0.025）
#   hills     低缓的丘陵 + 一溜溜树丛 / 灌木岛，带一点淡绿（scroll 0.07）
#   far       远处的湿地：一条淡黄绿的草带 + 一条映着天的水（scroll 0.14）
# 然后才是中景的小洲（mid 0.35）、岛层（isles 0.62）、晨这一层。
RANGES = [
    {"id": "mtn_far", "y": 22, "h": 128, "scroll": 0.008, "body": "#d2e7f1", "lit": "#e3eff0", "shade": "#c8e1ee",
     "mist": ("#e6f1f0", "#eef5ee"), "peaks": 5, "ph": (62, 96), "pw": (70, 130), "trees": False},
    {"id": "mtn_mid", "y": 58, "h": 94, "scroll": 0.025, "body": "#b7d8eb", "lit": "#e2ece3", "shade": "#a6cde5",
     "mist": ("#dfeeef", "#ebf3ec"), "peaks": 8, "ph": (30, 58), "pw": (40, 90), "trees": False},
    {"id": "hills", "y": 100, "h": 54, "scroll": 0.07, "body": "#c3e1c7", "lit": "#e3eecf", "shade": "#acd4bf",
     "mist": ("#e3f0e6", "#edf4e8"), "peaks": 6, "ph": (10, 22), "pw": (70, 150), "trees": True},
]


# 丘陵上的树（第九版，作者：「背景的树很奇怪，没什么质感」——原来每棵是同一个带斜条纹的圆疙瘩，一样大、一样高、等距排成一条花边）。
# 现在：一丛一丛聚着（丛和丛之间空着，偶尔一棵孤树），丛中间高大、两头矮小；每棵树冠是几团叶团叠起来的（球面算受光，
# 前面的叶团在后面的叶团上投一道暗），左上受光、右下背光；山脊上的丛远 → 小、淡、对比低，坡上的丛近 → 大一点、清楚一点。
# 树底下一溜灌木把树根和山坡连上，灌木下面山坡压暗一条。颜色还是原来那几档淡绿，只是多了中间档。
TREE_TONES = ["#d6eac6", "#c3e0bd", "#b0d6b4", "#9ccbae"]          # 受光 → 半受光 → 本色 → 背光
TREE_TRUNK = "#9fc4ad"
BUSH_TONES = ["#dcecca", "#c9e3c3", "#b6d9b9", "#a6d0b4"]
LIGHT = np.array([-0.5, -0.66, 0.56]) / np.linalg.norm([-0.5, -0.66, 0.56])


def leaf_tones(lobes, x0, y0, x1, y1, rng, cut=(0.80, 0.60, 0.30)):
    """几团叶团（lx, ly, r, z）的并：每格归最高的那一团，按那一团的球面法线算受光；下半截压暗一点；
    被前面（更高）的叶团压着的那一圈下沿投一道暗。返回 tone 下标（-1 = 空）。"""
    ys, xs = np.mgrid[y0:y1, x0:x1]
    px, py = xs + 0.5, ys + 0.5
    hz = np.full(xs.shape, -1e9)
    win = np.full(xs.shape, -1)
    for i, (lx, ly, r, z) in enumerate(lobes):
        d2 = (px - lx) ** 2 + (py - ly) ** 2
        inn = d2 < r * r
        v = z + np.sqrt(np.clip(r * r - d2, 0, None))
        up = inn & (v > hz)
        hz[up] = v[up]
        win[up] = i
    out = np.full(xs.shape, -1)
    m = win >= 0
    if not m.any():
        return out
    L = np.array(lobes, float)
    lx, ly, lr = L[win.clip(0), 0], L[win.clip(0), 1], L[win.clip(0), 2]
    nx, ny = (px - lx) / lr, (py - ly) / lr
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0.05, None))
    nn = np.sqrt(nx * nx + ny * ny + nz * nz)
    inten = (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / nn
    rows = np.nonzero(m.any(axis=1))[0]
    top, bot = rows[0], rows[-1] + 1
    inten -= 0.32 * (np.arange(xs.shape[0])[:, None] - top) / max(1, bot - top)
    # 投影：上面一格或左上一格属于另一团、而且那一团在这里更靠前（高）→ 这格在它的影子里
    sh = np.zeros(xs.shape, bool)
    for dy, dx in ((1, 0), (1, 1)):
        a = win[:-dy, :xs.shape[1] - dx]
        b = win[dy:, dx:]
        ha = hz[:-dy, :xs.shape[1] - dx]
        hb = hz[dy:, dx:]
        sh[dy:, dx:] |= (a >= 0) & (b >= 0) & (a != b) & (ha > hb + 0.4)
    inten -= sh * 0.3
    out[m] = 3
    out[m & (inten > cut[2])] = 2
    out[m & (inten > cut[1])] = 1
    out[m & (inten > cut[0])] = 0
    return out


def tree_lobes(cx, base, rx, ry, rng):
    """一棵树的树冠：顶上一团 + 几团绕着中心的叶团（下面的靠前），撑出一个不规则、一团团鼓出来的轮廓"""
    cy = base - ry
    small = rx < 3.4
    lobes = [(cx, cy + ry * 0.1, min(rx, ry) * 0.85, -0.8),                      # 芯（垫在后面，叶团之间不漏天）
             (cx + rng.uniform(-0.25, 0.25) * rx, cy - ry * 0.38, min(rx, ry) * rng.uniform(0.55, 0.68), 0.0)]
    n = 2 if small else int(np.clip(round(rx * ry / 6.0), 3, 7))
    for i in range(n):
        a = (i + rng.uniform(0.1, 0.9)) / n * 2 * math.pi
        k = rng.uniform(0.35, 0.7)
        lx = cx + math.cos(a) * rx * k
        ly = cy + math.sin(a) * ry * k * 0.85 + ry * 0.12
        r = min(rx, ry) * rng.uniform(0.5, 0.66 if not small else 0.75)
        z = (ly - cy) / ry * 1.6 + rng.uniform(-0.3, 0.6)
        lobes.append((lx, ly, r, z))
    return lobes


def draw_groves(img, prof, ylim, spec, rng, groves):
    """groves：[(x0, x1, dy, haze, size, lone)]——每一丛从哪到哪、根比 prof 低几像素、多淡、多大；lone = 孤树（一棵 + 一小团灌木）"""
    w = img.shape[1]
    mist = hexc(spec["mist"][0])
    hill_shade = hexc(spec["shade"])
    hill_body = hexc(spec["body"])
    items = []            # (根的 y, 种类, 数据)
    shadows = []          # (x0, x1, dy)：丛下面压暗的那一段
    for (x0, x1, dy, haze, size, lone) in groves:
        if lone:
            lt = (x0 + x1) / 2
            rx = rng.uniform(2.6, 4.4) * size
            bl = min(prof[int(lt) % w] + dy, ylim - 1)
            items.append((bl, "tree", (lt, bl - 2, rx, rx * rng.uniform(1.0, 1.4), 2, haze)))
            items.append((bl + 0.5, "bush", (lt - 1.5, min(bl + 1.2, ylim), 1.8, haze)))
            shadows.append((lt - 4, lt + 4, dy))
            continue
        gw = x1 - x0
        near = 0.5
        shadows.append((x0, x1, dy))
        t = x0 + rng.uniform(0, 3)
        while t < x1:
            u = (t - x0) / gw
            env = math.sin(math.pi * min(1, max(0, u))) ** 0.6       # 丛中间高大、两头矮小
            rx = (1.8 + 4.2 * env * rng.uniform(0.6, 1.15)) * size
            ry = rx * rng.choice([0.9, 1.05, 1.3, 1.6], p=[0.3, 0.35, 0.2, 0.15])
            base = prof[int(t) % w] + dy + rng.uniform(-0.6, 1.4)
            base = min(base, ylim - 1)
            trunk = int(rng.integers(0, 3)) if rx > 2.6 else 0
            items.append((base, "tree", (t, base - trunk, rx, ry, trunk, haze)))
            t += rx * rng.uniform(0.9, 1.7) + (rng.uniform(3, 8) if rng.random() < 0.18 else 0)    # 有时候中间留个缝
        # 灌木：一溜贴着丛的根，两头伸出去一点
        b = x0 - rng.uniform(2, 6)
        while b < x1 + rng.uniform(2, 6):
            rb = rng.uniform(1.4, 2.6) * (0.8 + 0.3 * near)
            base = min(prof[int(b) % w] + dy + 1.6 + rng.uniform(0, 0.8), ylim)
            items.append((base + 0.5, "bush", (b, base, rb, haze)))
            b += rb * rng.uniform(1.0, 1.7)
    # 丛下面的山坡压暗：根那条线往下 1–3 像素，两头慢慢收
    for (x0, x1, dy) in shadows:
        for xi in range(int(x0) - 3, int(x1) + 4):
            e = min(sstep(x0 - 3, x0 + 6, xi), 1 - sstep(x1 - 6, x1 + 3, xi))
            th = 3.2 * e
            y0 = prof[xi % w] + dy + 1.0
            for yy in range(int(round(y0)), int(round(y0 + th))):
                if 0 <= yy < ylim + 1 and img[yy, xi % w, 3]:
                    img[yy, xi % w] = mix(hill_body, hill_shade, 1.0 if yy - y0 < th * 0.55 else 0.5)
    items.sort(key=lambda it: it[0])
    for base, kind, d in items:
        if kind == "tree":
            cx, cb, rx, ry, trunk, haze = d
            lobes = tree_lobes(cx, cb, rx, ry, rng)
            pal = [mix(mix(hexc(c), hexc(TREE_TONES[2]), haze * 0.5), mist, haze) for c in TREE_TONES]
            cut = (0.80, 0.60, 0.30)
            if trunk:
                tc = mix(mix(hexc(TREE_TRUNK), hexc(TREE_TONES[2]), haze * 0.5), mist, haze)
                for yy in range(int(round(cb - 1)), int(round(base)) + 1):
                    if 0 <= yy <= ylim:
                        img[yy, int(round(cx)) % w] = tc
        else:
            bx, bb, rb, haze = d
            lobes = [(bx, bb - rb * 0.55, rb, 0.0), (bx + rb * 0.8, bb - rb * 0.35, rb * 0.75, 0.4)]
            pal = [mix(mix(hexc(c), hexc(BUSH_TONES[2]), haze * 0.5), mist, haze) for c in BUSH_TONES]
            cut = (0.9, 0.72, 0.4)
        xa = int(min(l[0] - l[2] for l in lobes)) - 1
        xb = int(max(l[0] + l[2] for l in lobes)) + 2
        ya = int(min(l[1] - l[2] for l in lobes)) - 1
        yb = int(max(l[1] + l[2] for l in lobes)) + 2
        tone = leaf_tones(lobes, xa, ya, xb, yb, rng, cut)
        for j in range(tone.shape[0]):
            yy = ya + j
            if yy < 0 or yy > ylim:
                continue
            for i in range(tone.shape[1]):
                if tone[j, i] >= 0:
                    img[yy, (xa + i) % w] = pal[tone[j, i]]


def draw_range(spec):
    """一层山（tile 960）：几座圆顶的峰（不是尖的）叠出起伏的轮廓，按坡朝哪边分亮面 / 背光面（只在上沿往下一截里分，下面是身子），
    山脚化进两档雾里。trees = True：低丘陵上一溜溜圆圆的树丛（左上亮、右下暗），有的地方空着。"""
    rng = np.random.default_rng(sum(map(ord, spec["id"])))
    w, h = 960, spec["h"]
    xs = np.arange(w)
    prof = np.full(w, float(h - 6))
    for _ in range(spec["peaks"]):
        c = rng.uniform(0, w)
        ph = rng.uniform(*spec["ph"])
        pw = rng.uniform(*spec["pw"])
        d = np.minimum(np.abs(xs - c), w - np.abs(xs - c))
        dome = ph * np.clip(1 - (d / pw) ** 2, 0, 1) ** 0.75
        prof = np.minimum(prof, h - 8 - dome)
    prof += knots(w, 37, rng, 1.6, period=960) + knots(w, 13, rng, 0.6, period=960)
    img = blank(w, h)
    body, lit, shade = hexc(spec["body"]), hexc(spec["lit"]), hexc(spec["shade"])
    mist0, mist1 = hexc(spec["mist"][0]), hexc(spec["mist"][1])
    mw = knots(w, 50, rng, 1.5, period=960)
    for x in range(w):
        t = int(round(prof[x]))
        sl = prof[(x + 4) % w] - prof[(x - 4) % w]          # < 0：往右在升高 = 这面朝左（朝光）
        dl = max(0.0, -sl - 0.4) * 5.0                       # 亮面 / 背光面有多厚：随坡度慢慢变，到平的地方收成 0（不竖着切一刀）
        ds = max(0.0, sl - 0.4) * 5.0
        for y in range(max(0, t), h):
            d = y - t
            c = lit if d < dl else shade if d < ds else body
            if y >= h - 11 + mw[x]:
                c = mist0
            if y >= h - 5 + mw[x] * 0.5:
                c = mist1
            img[y, x] = c
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    de_alt(img, passes=3)
    corner_fix(img)
    edge_diag_fill(img)
    speck_fix(img)
    corner_fix(img)
    return img


# ---------------------------------------------------------------- 第十版：背景是湿地（作者：「背景也会有湿地而不像现在都是黄土高坡」）
# 远山后面不再是一层层平的黄带子，而是一片片映着天的水，中间隔着草洲、芦苇荡、灌木和沙洲，越远越小越淡：
#   hills（0.07）  一个个矮矮的草洲浮在水上，第九版的树丛长在洲上，水里有洲和树的倒影；洲和洲之间是开阔的水，一直接到远山脚下的雾
#   far（0.14）    更近一点的一溜：远处的芦苇荡、几团灌木、扁扁的沙洲，中间都是水
#   mid（0.35）    草、芦苇、开花草几片小洲，片和片之间空出一段段水
#   isles（0.62）  同上，大一点、清楚一点；白鹭站在洲边、野鸭在洲和洲之间的水上（reed_field.gd 画）
# 远处的水按屏幕上的高度取色（越远越亮、越近越青），几层的水在同一高度是同一个颜色，层和层之间接起来看不出缝。
BGW = [(0, "#eef6ef"), (136, "#e6f3f0"), (143, "#dcf0f1"), (151, "#d2ebef"), (160, "#c8e6eb"), (170, "#bee1e6"), (180, "#b4dce0")]
BGW_GLINT = ["#f8fcf6", "#fbf3c8"]
BGW_SET: set = set()
HILLS_WL = 34                            # hills 层里水面那一行（屏幕 y 134）


def bgw_c(y):
    c = BGW[0][1]
    for yy, cc in BGW:
        if y >= yy:
            c = cc
    return c


def bg_water(w, h, y0, top, rng, glints=1.0):
    """一片远处的水（tile）：top 行往下，按屏幕高度分档取色（档和档的边界轻轻起伏）+ 几道长长的横亮纹（天光、偶尔一道暖的）"""
    img = blank(w, h)
    wob = fbm(h, w, 90, 6, rng, period=w) * 1.4
    for y in range(top, h):
        for x in range(w):
            img[y, x] = hexc(bgw_c(y0 + y + wob[y, x]))
    placed = 0
    gl = {tuple(hexc(c)) for c in BGW_GLINT}
    for _ in range(int(w * (h - top) / 220 * glints) * 6):
        if placed >= int(w * (h - top) / 220 * glints):
            break
        y = int(rng.integers(top + 1, h - 1))
        x = int(rng.integers(0, w))
        L = int(rng.integers(6, 26))
        xs = [(x + i) % w for i in range(-2, L + 2)]
        if any(tuple(img[yy, xx]) in gl for yy in range(max(top, y - 1), min(h, y + 2)) for xx in xs):
            continue
        c = hexc(BGW_GLINT[1] if rng.random() < 0.25 else BGW_GLINT[0])
        for i in range(L):
            img[y, (x + i) % w] = c
        placed += 1
    return img


def reflect_down(img, src_mask, base_of, k=0.5, amt=0.6, maxlen=99, period=True):
    """src_mask 里的东西（水面以上）在水里的倒影：离水面 d 的那格 → 水面下 1 + d·k 那格，混进水色 amt；只画在水上（BGW 的颜色）"""
    h, w = img.shape[:2]
    done = np.zeros((h, w), bool)
    ys, xs = np.nonzero(src_mask)
    order = np.argsort(-ys)                         # 从靠水面的往上：近水面的先占位
    src = img.copy()
    for i in order:
        y, x = ys[i], xs[i]
        b = base_of(x)
        d = b - y
        if d < 0:
            continue
        ry = b + 1 + int(d * k)
        if ry - b > maxlen or ry >= h or done[ry, x] or src_mask[ry, x] or tuple(img[ry, x]) not in BGW_SET:
            continue
        img[ry, x] = mix(src[y, x], img[ry, x], amt)
        done[ry, x] = True


def draw_hills10(spec):
    """远处的草洲（scroll 0.07，tile 960）：水面以上一个个矮洲（上沿一道亮、贴水一道暗），洲上长第九版那种一丛丛的树，洲和洲之间空着"""
    rng = np.random.default_rng(1010)
    w, h, y0 = 960, spec["h"], spec["y"]
    WL = HILLS_WL
    img = bg_water(w, h, y0, WL + 1, rng, glints=0.7)
    land = np.zeros(w)
    spans = []
    x = rng.uniform(4, 30)
    while x < w - 50:
        iw = rng.uniform(50, 170)
        x0, x1 = x, min(x + iw, w - 10)
        hg = rng.uniform(2.2, 4.8)
        kn = knots(w, 23, rng, 0.8, period=960)
        for xi in range(int(x0), int(x1) + 1):
            e = min(sstep(x0, x0 + 16, xi), 1 - sstep(x1 - 16, x1, xi))
            land[xi] = max(land[xi], (hg + kn[xi]) * e)
        spans.append((x0, x1))
        x = x1 + rng.uniform(26, 96)
    lit = mix(hexc(spec["lit"]), hexc(spec["body"]), 0.45)
    body, shade = hexc(spec["body"]), hexc(spec["shade"])
    prof = np.full(w, float(WL))
    for xi in range(w):
        hgt = int(round(land[xi]))
        if hgt < 1:
            continue
        top = WL - hgt
        prof[xi] = top
        for y in range(top, WL + 1):
            img[y, xi] = lit if y == top else shade if y == WL else body
    # 洲上的树：大洲一两丛、小洲一棵孤树或空着
    groves = []
    for (x0, x1) in spans:
        haze = rng.uniform(0.1, 0.32)
        if x1 - x0 > 70 and rng.random() < 0.85:
            n = 1 if x1 - x0 < 120 else int(rng.integers(1, 3))
            seg = (x1 - x0 - 24) / n
            for k in range(n):
                gx0 = x0 + 12 + k * seg + rng.uniform(0, seg * 0.25)
                gx1 = gx0 + seg * rng.uniform(0.45, 0.8)
                groves.append((gx0, gx1, rng.uniform(0.5, 1.5), haze, rng.uniform(0.85, 1.15), False))
        elif rng.random() < 0.6:
            c = rng.uniform(x0 + 16, x1 - 16)
            groves.append((c - 2, c + 2, 1.0, haze, 1.0, True))
    draw_groves(img, prof, WL, spec, rng, groves)
    above = np.zeros((h, w), bool)
    above[:WL + 1] = img[:WL + 1, :, 3] > 0
    for xi in range(w):                               # 贴水一道湿的暗边（洲底下）
        if land[xi] >= 0.5 and tuple(img[WL + 1, xi]) in BGW_SET:
            img[WL + 1, xi] = mix(shade, img[WL + 1, xi], 0.35)
    reflect_down(img, above, lambda x: WL + 1, k=0.5, amt=0.62)
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    de_alt(img, passes=3)
    corner_fix(img)
    edge_diag_fill(img)
    speck_fix(img)
    corner_fix(img)
    return img


FAR_Y, FAR_H, FAR_WT, FAR_B = 128, 26, 11, 16      # far 层：屏幕 y、高、水从哪一行开始、东西的根在哪一行


def draw_far10():
    """远处的一溜（scroll 0.14，tile 960）：芦苇荡（一长条，上沿软软起伏，穗是奶白 / 淡蓝的一道）、几团灌木、扁扁的沙洲，中间是水"""
    rng = np.random.default_rng(1014)
    w, h = 960, FAR_H
    img = bg_water(w, h, FAR_Y, FAR_WT, rng, glints=0.8)
    el = blank(w, h)
    hz = 0.42
    base = FAR_B + knots(w, 70, rng, 0.8, period=960)
    x = rng.uniform(0, 20)
    while x < w - 12:
        kind = rng.choice(["reeds", "bush", "sand"], p=[0.42, 0.28, 0.30])
        if kind == "reeds":
            fw = rng.uniform(34, 120)
            hgt = rng.uniform(3.5, 6.5)
            top = knots(w, 9, rng, 0.9, period=960)
            plume = [hexc("#f6f0cc"), hexc("#dcedf1")][int(rng.integers(0, 2))]
            for xi in range(int(x), int(min(x + fw, w - 2))):
                e = min(sstep(x, x + 10, xi), 1 - sstep(x + fw - 10, x + fw, xi))
                hh = int(round((hgt + top[xi]) * e ** 0.6))
                b = int(round(base[xi]))
                for y in range(b - hh, b + 1):
                    d = y - (b - hh)
                    el[y, xi] = plume if d < 1 else hexc("#e7dfa2") if d < max(2, hh * 0.55) else hexc("#cfdcab")
        elif kind == "bush":
            fw = rng.uniform(10, 26)
            lobes = []
            t = x
            while t < x + fw:
                r = rng.uniform(1.4, 2.8)
                lobes.append((t, base[int(t) % w] - r * 0.6, r, rng.uniform(0, 0.6)))
                t += r * rng.uniform(0.9, 1.5)
            xa, xb = int(x - 4), int(x + fw + 5)
            ya, yb = 0, h
            tone = leaf_tones(lobes, xa, ya, xb, yb, rng)
            for j in range(tone.shape[0]):
                for i in range(tone.shape[1]):
                    if tone[j, i] >= 0 and j <= base[(xa + i) % w] + 0.5:
                        el[j, (xa + i) % w] = hexc(TREE_TONES[tone[j, i]])
        else:
            fw = rng.uniform(20, 64)
            for xi in range(int(x), int(min(x + fw, w - 2))):
                e = min(sstep(x, x + 8, xi), 1 - sstep(x + fw - 8, x + fw, xi))
                hh = 1 if e > 0.15 else 0
                if e > 0.6 and fw > 36:
                    hh = 2
                b = int(round(base[xi])) + 1
                for y in range(b - hh, b + 1):
                    el[y, xi] = hexc("#f6f1d8") if y == b - hh else hexc("#e5e3c4")
        x += fw + rng.uniform(10, 56)
    haze_img(el, hz)
    m = el[..., 3] > 0
    img[m] = el[m]
    img[:FAR_WT][~m[:FAR_WT]] = 0
    reflect_down(img, m, lambda xx: int(round(base[xx])) + 1, k=0.5, amt=0.6, maxlen=4)
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    de_alt(img, passes=3)
    corner_fix(img)
    edge_diag_fill(img)
    speck_fix(img)
    corner_fix(img)
    return img


def in_water(x):
    return any(a <= x <= b for a, b in WATERS)


def water_amt(x):
    """这一列有多「水」：水段中间 1，边上 50 像素里平滑过渡（岸是弯的，不切竖直一刀）"""
    best = 0.0
    for a, b in WATERS:
        best = max(best, sstep(a - 30, a + 40, x) * (1 - sstep(b - 40, b + 30, x)))
    return best


# ---------------------------------------------------------------- 湿地草地：各种草、水边、水里（第五版：作者「与其说是芦苇地，不如说是湿地或者草地，每处都有草，一片生机」）
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
    alpha_fix(img)
    edge_diag_fill(img)
    corner_fix(img)
    return img


def draw_glints_band(w, h, y0, under, seed, n):
    """一条水上的亮纹（tile）：只放在 under 是水的地方（POOL 的颜色），横的短段，长短不一、随机散开"""
    rng = np.random.default_rng(seed)
    img = blank(w, h)
    pool = {tuple(hexc(c)) for c in POOL} | BGW_SET
    placed = 0
    for _ in range(n * 40):
        if placed >= n:
            break
        x = int(rng.integers(0, w - 8))
        y = int(rng.integers(2, h - 1))
        L = int(rng.integers(2, 6))
        if not all(tuple(under[y, xx]) in pool for xx in range(x, x + L)):
            continue
        if img[max(0, y - 1):y + 2, max(0, x - 2):x + L + 2, 3].any():
            continue
        img[y, x:x + L] = hexc(GLINT[0] if rng.random() < 0.5 else GLINT[1])
        placed += 1
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


# ---------------------------------------------------------------- 巨大作物（装饰：比人大好几倍的麦穗、蒲公英，「这是另一颗星球」）
# 每一株一张自己的图、一个自己的层（room.json：x、y、scroll、sway shader 让它随风轻轻摆；图的最下面一行是根）。
# 远的（scroll 0.4）小、淡（混进天色）；近的（scroll 0.8，在 main 后面，根埋在草甸后面）大、被画面上沿切掉一截；
# 前景那一株（scroll 1.25，在晨前面）只从画面下沿弯进来一点，顶不超过路（y 236 以下），不挡晨。
# 都是一团团实心的圆章叠出来的（没有 1 像素的细线，只有麦芒是四邻接的细线），形状概括、边缘软（亮边 / 暗边各一档）。
HAZE = "#e8f3f2"
GIANT_LAYERS: list = []                 # draw_giants 填（room_json 用）
GIANTS = [
    # id, 种类, 大小倍数, scroll, 「在屏幕正中时对着晨这一层的 x」, 根在屏幕上的 y, 朝向, 淡（混天色多少）, z（None = 按层顺序）, 球心的屏幕 y
    # 第五版：作者「蒲公英好看，麦穗不太好看」—— 只留蒲公英，远近五株。
    # 第十版：作者「有的大蒲公英是杆子悬浮在地面的」—— 以前杆子画到图底就完，底下要靠别的层盖住，镜头一动就露出来悬在半空。
    # 现在每株的根都插在它那一层看得见的水面上（0.35 / 0.4 在 mid 的水上，0.6 在 isles 的水上，0.8 在晨这一层的水后沿），
    # 根上自己带一丛草（盖住杆子底）+ 贴水一道湿边 + 水里的倒影；层也按远近插在对应的层后面（不会被更远的水盖住根）。
    ("giant_dandelion_far_a", "dandelion", 0.3, 0.35, 330, 156, 1, 0.5, None, 100),
    ("giant_dandelion_far_b", "dandelion", 0.36, 0.4, 1760, 157, -1, 0.5, None, 94),
    ("giant_dandelion_mid", "dandelion", 0.62, 0.6, 790, 172, 1, 0.22, None, 62),
    ("giant_dandelion_near_a", "dandelion", 0.85, 0.8, 70, 178, -1, 0.0, None, 48),
    ("giant_dandelion_near_b", "dandelion", 1.0, 0.8, 1880, 179, 1, 0.0, None, 32),
]
SEED_EMITTERS: list = []
RIPPLE_PTS: list = []                   # draw_main 填：水面上会偶尔泛一圈涟漪的点（房间坐标）
MOTE_PTS: list = []                     # draw_main 填：草上小飞虫 / 光点慢慢飘的锚点                # draw_giants 填：[层 x, 层 y, scroll, 半径]（绒毛从这里被风吹走，reed_field.gd 画）


def stamp(img, pts, rads, color_fn):
    """沿一串点盖实心圆章（半径可变）。color_fn(i, dx, dy, r) → 颜色（按在圆章里的位置分亮边 / 身子 / 暗边）"""
    h, w = img.shape[:2]
    for i, ((px, py), r) in enumerate(zip(pts, rads)):
        r = max(0.6, r)
        for y in range(int(py - r - 1), int(py + r + 2)):
            for x in range(int(px - r - 1), int(px + r + 2)):
                dx, dy = x - px, y - py
                if 0 <= x < w and 0 <= y < h and dx * dx + dy * dy <= r * r:
                    img[y, x] = hexc(color_fn(i, dx, dy, r))


def bez(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        a = (1 - t) ** 3
        b = 3 * (1 - t) ** 2 * t
        c = 3 * (1 - t) * t * t
        d = t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def haze_img(img, k):
    if k <= 0:
        return
    m = img[..., 3] > 0
    hz = hexc(HAZE).astype(float)
    img[m, :3] = np.round(img[m, :3] * (1 - k) + hz[:3] * k).astype(np.uint8)


def draw_dandelion(sc, reach):
    """巨大的蒲公英绒球：一根微弯的细茎，顶上一个毛茸茸的球（边上一圈软软的小鼓包；外圈奶白、里面一层淡蓝白、正中一小团淡黄的种托），
    左上受光的那一侧白一档；球里几道从中心往外的淡蓝细线（冠毛，四邻接）；旁边飘着两三颗种子（小降落伞，3×3 实心，不是孤立的点）。"""
    rng = np.random.default_rng(int(sc * 1000) + 3)
    R = 46 * sc
    Wc, Hc = int(R * 2 + 70 * sc) + 16, int(R + 8 + reach) + 1          # reach：球心到根多高
    img = blank(Wc, Hc)
    cx, cy = Wc * 0.55, R + 8
    sl = Hc - 1 - (cy + R * 0.5)
    stem = bez((Wc * 0.42, Hc - 1), (Wc * 0.40, Hc - 1 - sl * 0.45), (cx - 10 * sc, cy + R + sl * 0.2), (cx, cy + R * 0.5), int(sl * 1.3) + 10)
    stamp(img, stem, [max(1.0, 2.2 * sc) for _ in stem], lambda i, dx, dy, r: RAMP[4] if dx < 0 else RAMP[2])
    # 球：边上一圈细碎的小鼓包（毛茸茸），按球面法线 · 左上的光分五档：受光白、奶白、淡蓝白、淡蓝、背光边一道深一点的淡蓝；
    # 正中一小团淡黄的种托（藏在里面，只在受光那侧露一点）
    bumps = knots(360, 5, rng, 0.06, period=360) + knots(360, 23, rng, 0.05, period=360)
    Lv = np.array([-0.55, -0.62, 0.56])
    Lv = Lv / np.linalg.norm(Lv)
    for y in range(int(cy - R * 1.2), int(cy + R * 1.2)):
        for x in range(int(cx - R * 1.2), int(cx + R * 1.2)):
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            a = int(math.degrees(math.atan2(dy, dx))) % 360
            rr = R * (1 + bumps[a])
            if d > rr or not (0 <= x < Wc and 0 <= y < Hc):
                continue
            nx, ny = dx / rr, dy / rr
            nz = math.sqrt(max(0.0, 1 - nx * nx - ny * ny))
            lit = nx * Lv[0] + ny * Lv[1] + nz * Lv[2]
            if d < R * 0.13:
                c = RAMP[3]
            elif lit > 0.78:
                c = GLINT[0]
            elif lit > 0.45:
                c = RAMP[4]
            elif lit > 0.15:
                c = RAMP[5]
            elif lit > -0.2:
                c = RAMP[6]
            else:
                c = RAMP[7]
            img[y, x] = hexc(c)
    # 飘走的种子
    for k in range(2 if sc > 0.6 else 0):
        sx = int(cx + R * (0.9 + 0.35 * k) + rng.uniform(-4, 4))
        sy = int(cy - R * (0.5 + 0.25 * k) + rng.uniform(-4, 4))
        for (dx, dy, c) in [(0, -1, GLINT[0]), (-1, 0, GLINT[0]), (0, 0, GLINT[0]), (1, 0, GLINT[0]), (0, 1, RAMP[3])]:
            if 0 <= sx + dx < Wc and 0 <= sy + dy < Hc:
                img[sy + dy, sx + dx] = hexc(c)
    return img, cx, cy, R


def dandelion_root(im, sc, hz, root_y, rng):
    """给一株蒲公英的图在根上加一丛草 + 贴水的湿边 + 水里的倒影（杆子插进水里、草里）。im 的最后一行是根；返回新图和图往左、往上各扩了多少"""
    h, w = im.shape[:2]
    rx = int(np.nonzero(im[h - 1, :, 3])[0].mean())
    tw, th = int(14 + 26 * sc), int(5 + 9 * sc)
    fam = "G" if rng.random() < 0.6 else "YG"
    tuft, tbx, tby = grass_base(tw, th, GRASS_T[fam], rng, 0.35, sep=sc > 0.5, fringe=0.6)
    haze_img(tuft, hz)
    th2, tw2 = tuft.shape[:2]
    rh = int(th * 0.6) + 3                                   # 倒影几行
    left = max(0, tbx - rx + 2)
    right = max(0, (tw2 - tbx) - (w - rx) + 2)
    top = max(0, tby - (h - 1))
    out = blank(w + left + right, h + top + rh)
    out[top:top + h, left:left + w] = im
    ry, rxx = top + h - 1, left + rx                         # 根在新图里的位置
    m = tuft[..., 3] > 0
    for (yy, xx) in zip(*np.nonzero(m)):
        Y, X = ry - tby + yy, rxx - tbx + xx
        if 0 <= Y <= ry and 0 <= X < out.shape[1]:
            out[Y, X] = tuft[yy, xx]
    src = out.copy()
    above = src[..., 3] > 0
    above[ry + 1:] = False
    wet = hexc("#8cc0a6")
    for X in range(out.shape[1]):
        col = np.nonzero(above[:, X])[0]
        if not len(col) or col.max() < ry - 1:
            continue
        sy = root_y + 1
        out[ry + 1, X] = mix(mix(wet, hexc(HAZE), hz), hexc(bgw_c(sy)), 0.3)
        for Y in range(ry, max(-1, ry - 2 * rh), -1):         # 倒影：压扁一半，混进水色
            if not above[Y, X]:
                continue
            d = ry - Y
            ty = ry + 2 + d // 2
            if ty < out.shape[0] and out[ty, X, 3] == 0:
                out[ty, X] = mix(src[Y, X], hexc(bgw_c(root_y + 2 + d // 2)), 0.6)
    return out, left, top, rxx


def draw_giants():
    """画 GIANTS 里的每一株，返回 {id: 图} 和要放进 room.json 的层"""
    imgs, layers = {}, []
    for gid, kind, sc, scroll, room_x, bottom, face, hz, z, ball_y in GIANTS:
        im, bcx, bcy, br = draw_dandelion(sc, bottom - ball_y)
        if face < 0:
            im = im[:, ::-1].copy()
            bcx = im.shape[1] - 1 - bcx
        haze_img(im, hz)
        im, dl, dt, root_x = dandelion_root(im, sc, hz, bottom, np.random.default_rng(int(sc * 777) + 5))
        bcx, bcy = bcx + dl, bcy + dt
        corner_fix(im)
        speck_fix(im)
        corner_fix(im)
        alpha_fix(im)
        edge_diag_fill(im)
        speck_fix(im)
        corner_fix(im)
        h, w = im.shape[:2]
        x = int(round(240 + (room_x - 240) * scroll - w / 2))
        y = int(bottom - (dt + int(br + 8 + bottom - ball_y)))
        L = {"id": gid, "img": gid + ".png", "scroll": scroll, "x": x, "y": y, "shader": "sway",
             "shader_params": {"amp": 2.0 if scroll >= 0.8 else 1.0, "speed": 0.45, "wavelength": 4000.0, "power": 1.8, "bend": 0.012}}
        if z is not None:
            L["z"] = z
        imgs[gid] = im
        layers.append(L)
        SEED_EMITTERS.append([int(x + bcx), int(y + bcy), scroll, round(float(br), 1)])
        GIANT_ROOTS.append((gid, scroll, int(x + root_x), bottom))
    return imgs, layers


GIANT_ROOTS: list = []


# ---------------------------------------------------------------- 第十三版：只加东西，颜色一律沿用第十一版
# 作者：「我的方案本是叫你多加一些石头，树木……一团一团的树，大一点，可能跟主角同一层，但是大到直接顶到屏幕顶上」。
# 大树（bigtrees 层，scroll 1.0，紧贴在 main 后面）。
# 第十四版用作者「森林阔叶木」原图换色直接贴（作者：「我没让你直接搬过来，我叫你画出和背景一样的那个风格」），撤掉。
# 第十五版：尺寸照第十四版（和晨同一层、冲出屏幕上沿，宽 200 出头），作者的阔叶木只拿来参考轮廓和体量
# （一层层横着的伞形叶、粗主干、枝从叶层的缝里露出来、下沿垂下来的叶），用湿地自己的画法重画：
# - 叶：每一层是一大片扁穹顶，里面挤很多小叶团（半径 3–9，和远处小树、小洲那种一团团一个颗粒），leaf_tones 那套球面受光
#   （左上来光，四档平涂）；每层下半截不出最亮那档、底下一截压到背光（伞的底面），上一层盖在下一层上投一道暗；
#   下沿每隔一段垂一绺两三格宽、往下收尖的叶（不是作者原图那种一像素的细丝）。
# - 颜色只用第十一版画面里已经有的颜色：叶 = main 草丛的嫩绿一套（BIGTREE_LEAF），树冠里头垫几层岛上那种偏冷的淡绿
#   （BIGTREE_INNER，照不到太阳）；上一层盖住下一层的地方压暗一档；树干 = 超前景、石头用过的那几档淡青灰
#   （BIGTREE_BARK：左受光、中本色、右背光），两格宽的竖纹。整棵树的平均亮度不低于 main。
# - 根放在 BIGTREE_ROOT 行，藏在 main 那一溜草带和会动的草丛后面。
BIGTREE_LEAF = ["#dcecb2", "#cbe39c", "#b8d98a", "#a6cf7c"]     # 受光 → 半受光 → 本色 → 背光
BIGTREE_INNER = ["#c2e2c8", "#b6dcba", "#b6dcba", "#a5d3a8"]    # 树冠里层（岛上的淡绿）
BIGTREE_BARK = ["#c0d8c0", "#acccbd", "#9ec5b8"]                # 受光、本色、背光
BIGTREE_DARKER = {**{a: b for a, b in zip(["#dcecb2", "#cbe39c", "#b8d98a", "#a6cf7c"], ["#cbe39c", "#b8d98a", "#a6cf7c", "#93c47a"])},
                  **{a: b for a, b in zip(["#c2e2c8", "#b6dcba", "#a5d3a8"], ["#b6dcba", "#a5d3a8", "#a5d3a8"])}}   # 压暗一档
BIGTREE_CUT = (0.78, 0.5, 0.0)
BIGTREES = [(600, 1), (1580, -1)]                                  # 树干中心的房间 x、朝向（−1 = 左右翻过来）
BIGTREE_ROOT = 214
# 一层层叶（相对树干中心 x、根往上为负）：(中心 x, 顶, 底, 半宽)；前 BIGTREE_N_INNER 层是里层（先画，垫在后面）
BIGTREE_SHELVES = [
    (-30, -232, -196, 30), (34, -226, -192, 30), (-20, -186, -150, 26), (30, -180, -146, 24), (-6, -146, -120, 26),
    (-44, -254, -212, 48), (40, -248, -208, 44),
    (-64, -204, -170, 38), (4, -214, -178, 30), (64, -200, -166, 36),
    (-78, -160, -130, 26), (-28, -168, -134, 31), (33, -164, -130, 35), (82, -150, -122, 21),
    (-49, -120, -92, 33), (47, -118, -90, 35),
]
BIGTREE_N_INNER = 5
# 主枝：(伸到哪, 根上多粗, 梢上多粗)——从树干上头分出去，先往上长、再往外伸进各层叶
BIGTREE_LIMBS = [((-42, -228), 11, 5), ((37, -222), 10, 5), ((-58, -180), 9, 4), ((60, -176), 9, 4), ((6, -196), 8, 4),
                 ((-75, -136), 7, 3), ((76, -128), 7, 3), ((-50, -100), 7, 3), ((45, -98), 7, 3)]


def shelf_lobes(cx, top, bot, hw, rng):
    """一层伞形的叶：外形是个扁穹顶（中间高、两头往下垂一点），里面撒很多小叶团（中间大、边上小），下面的靠前"""
    lobes = []
    H = bot - top
    n = int(2 * hw * H * 0.7 / 38)
    tries = 0
    while len(lobes) < n and tries < n * 30:
        tries += 1
        u = rng.uniform(-1, 1)
        x = cx + u * hw
        ytop = top + H * 0.62 * abs(u) ** 1.7
        ybot = bot + H * 0.12 * abs(u) ** 2
        r = rng.uniform(3.2, 5.5) + 4.0 * (1 - abs(u)) * rng.uniform(0.3, 1.0)
        if ybot - ytop < 2 * r * 0.8:
            r = max(2.4, (ybot - ytop) / 2 * 0.9)
        y = rng.uniform(ytop + r * 0.85, max(ytop + r * 0.85, ybot - r * 0.85))
        lobes.append((x, y, r, (y - top) / H * 1.8 + rng.uniform(-0.4, 0.4)))
    return lobes


def limb(img, p0, p1, w0, w1):
    """一截枝：从 p0（粗 w0）到 p1（细 w1），法线朝左上的那一边受光、另一边背光"""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    n = int(L * 2) + 2
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if nx > 0 or (nx == 0 and ny > 0):
        nx, ny = -nx, -ny                                            # 让 (nx, ny) 指向左上
    H2, W2 = img.shape[:2]
    tones = [hexc(c) for c in BIGTREE_BARK]
    for i in range(n + 1):
        t = i / n
        cx, cy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        r = (w0 + (w1 - w0) * t) / 2
        for yy in range(int(cy - r - 1), int(cy + r + 2)):
            for xx in range(int(cx - r - 1), int(cx + r + 2)):
                ddx, ddy = xx + 0.5 - cx, yy + 0.5 - cy
                if not (0 <= yy < H2 and 0 <= xx < W2) or ddx * ddx + ddy * ddy > r * r:
                    continue
                s = (ddx * nx + ddy * ny) / max(r, 0.5)
                img[yy, xx] = tones[0] if s > 0.45 and r > 1.4 else tones[2] if s < -0.35 else tones[1]


def bigtree_sprite(seed=15):
    """一棵大树（朝右的样子）。返回 (图, 树干中心 x, 根那一行 y)"""
    rng = np.random.default_rng(seed)
    PW, PH = 260, 290
    ox, oy = PW // 2, PH - 6
    img = blank(PW, PH)
    bark = [hexc(c) for c in BIGTREE_BARK]
    # 树干：根部往两边撇，往上收，略往左斜；左受光、右背光，几道两格宽的背光竖纹
    for y in range(oy - 158, oy + 1):
        h = oy - y
        hw = 12 + 6 * max(0, 1 - h / 40) ** 2 + 0.02 * max(0, 100 - h)
        c0 = ox - 0.04 * h
        for x in range(int(c0 - hw - 1), int(c0 + hw + 2)):
            d = (x + 0.5 - c0) / hw
            if abs(d) <= 1:
                img[y, x] = bark[0] if d < -0.55 else bark[2] if d > 0.4 else bark[1]
    for (bx, y0, y1) in [(-3, 6, 52), (5, 22, 90), (-8, 70, 128), (2, 104, 150)]:
        for y in range(oy - y1, oy - y0):
            x = int(round(ox - 0.04 * (oy - y) + bx))
            img[y, x:x + 2] = bark[2]
    # 主枝（两截，弯的）
    for (tx, ty), w0, w1 in BIGTREE_LIMBS:
        sx, sy = ox - 6 + tx * 0.12, oy + max(ty + 40, -150)
        ex, ey = ox + tx, oy + ty
        mx, my = sx + (ex - sx) * 0.35, sy + (ey - sy) * 0.65
        limb(img, (sx, sy), (mx, my), w0, (w0 + w1) / 2)
        limb(img, (mx, my), (ex, ey), (w0 + w1) / 2, w1)
    # 叶：一层层贴（里层先、再从上往下，下面的在前）
    shelf_id = np.full((PH, PW), -1)
    for k, (cx, t, b, hw) in enumerate(BIGTREE_SHELVES):
        lobes = shelf_lobes(ox + cx, oy + t, oy + b, hw, rng)
        pal = [hexc(c) for c in (BIGTREE_INNER if k < BIGTREE_N_INNER else BIGTREE_LEAF)]
        xa = int(min(l[0] - l[2] for l in lobes)) - 1
        xb = int(max(l[0] + l[2] for l in lobes)) + 2
        ya = int(min(l[1] - l[2] for l in lobes)) - 1
        yb = int(max(l[1] + l[2] for l in lobes)) + 2
        tone = leaf_tones(lobes, xa, ya, xb, yb, rng, cut=BIGTREE_CUT)
        rel = (np.arange(ya, yb)[:, None] - (oy + t)) / (b - t)
        m = tone >= 0
        tone[m & (rel > 0.42) & (tone == 0)] = 1                    # 受光只在每层的上沿
        tone[m & (rel > 0.66) & (tone < 2)] = 2                     # 伞的底面背光
        tone[m & (rel > 0.9)] = 3
        for j, i in zip(*np.nonzero(m)):
            yy, xx = ya + j, xa + i
            if 0 <= yy < PH and 0 <= xx < PW:
                img[yy, xx] = pal[tone[j, i]]
                shelf_id[yy, xx] = k
        # 垂叶：从这一层真正的最下面一格接出去（不悬空），两三格宽、往下收；左边亮一档、下半截右边和尖上暗一档
        x = xa + int(rng.integers(3, 8))
        while x < xb - 3:
            ys = np.nonzero(shelf_id[:, x] == k)[0]
            ys2 = np.nonzero(shelf_id[:, x + 1] == k)[0] if x + 1 < PW else []
            if len(ys) and len(ys2) and ys.max() > oy + t + (b - t) * 0.5:
                y0 = min(ys.max(), ys2.max())
                L = int(rng.integers(4, 13))
                wd = rng.uniform(2.6, 3.8)
                for d in range(1, L + 1):
                    u = d / L
                    r = wd * 0.5 * (1 - u * 0.6) + 0.3
                    pxc = x + 1 + 0.6 * math.sin(d * 0.7 + x)
                    for xx in range(int(pxc - r - 1), int(pxc + r + 2)):
                        dx = xx + 0.5 - pxc
                        if abs(dx) > r or not (0 <= xx < PW) or y0 + d >= PH:
                            continue
                        img[y0 + d, xx] = pal[1] if dx < -r * 0.35 and u < 0.6 else pal[3] if (dx > r * 0.3 and u > 0.4) or u > 0.85 else pal[2]
                        shelf_id[y0 + d, xx] = k
            x += int(rng.integers(4, 10)) if rng.random() > 0.25 else int(rng.integers(12, 22))
    # 上一层盖在下一层上的影子：头顶 1–2 格是先画的那一层 → 压暗一档
    out = img.copy()
    for yy, xx in zip(*np.nonzero(shelf_id >= 0)):
        k = shelf_id[yy, xx]
        if any(yy - d >= 0 and 0 <= shelf_id[yy - d, xx] < k for d in (1, 2)):
            cur = "#%02x%02x%02x" % tuple(int(v) for v in img[yy, xx][:3])
            if cur in BIGTREE_DARKER:
                out[yy, xx] = hexc(BIGTREE_DARKER[cur])
    img = out
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    alpha_fix(img)
    de_alt(img, passes=2)
    corner_fix(img)
    edge_diag_fill(img)
    speck_fix(img)
    corner_fix(img)
    return img, ox, oy


def draw_bigtrees():
    img = blank(W, BIGTREE_ROOT + 2)
    spr, tx, bot = bigtree_sprite()
    for (x0, face) in BIGTREES:
        s = spr if face > 0 else spr[:, ::-1]
        sx = tx if face > 0 else spr.shape[1] - 1 - tx
        X0, Y0 = int(x0 - sx), BIGTREE_ROOT - bot
        for y in range(s.shape[0]):
            Y = Y0 + y
            if not (0 <= Y < img.shape[0]):
                continue
            row = s[y]
            m = row[:, 3] > 0
            xs = np.nonzero(m)[0] + X0
            ok = (xs >= 0) & (xs < W)
            img[Y, xs[ok]] = row[m][ok]
    return img


# 石头：水边、草里、浅水里几块圆圆的石头（左上受光的奶白、身子淡灰黄、背光偏冷的淡青灰——都是第十一版画面里已有的明度），
# 在水里的：贴水一道暗边（接触阴影）+ 水里压扁一半的倒影；在草里的：底下一道淡淡的影子，会动的草丛在它前面。
ROCK_TONES = ["#f6f3e2", "#e4e2cd", "#cddbd5", "#b9d1cb"]
ROCK_WET = "#9fc4b8"


def draw_rocks(main, rng):
    pool = {tuple(hexc(c)) for c in POOL + POOL_SAND + [POOL_EDGE] + SURF + GLINT}
    tones = [hexc(c) for c in ROCK_TONES]
    mask = np.zeros(main.shape[:2], bool)
    spots = []
    for (n, y0, y1, rx0, rx1) in ((9, 238, 262, 4, 9), (6, 216, 220, 5, 11), (6, 200, 212, 6, 13)):
        tries = 0
        while sum(1 for s in spots if y0 <= s[1] <= y1) < n and tries < 400:
            tries += 1
            x = rng.uniform(20, W - 20)
            if any(abs(x - s[0]) < 110 for s in spots if y0 <= s[1] <= y1) or any(abs(x - m) < 40 for m in room_json_markers()):
                continue
            spots.append((x, rng.uniform(y0, y1), rng.uniform(rx0, rx1)))
    for (cx, base, rx) in spots:
        base = int(round(base))
        ry = rx * rng.uniform(0.55, 0.8)
        wet = tuple(main[min(H - 1, base + 1), int(cx)]) in pool
        moss = (not wet) or rng.random() < 0.35
        for y in range(int(base - ry - 1), base + 1):
            for x in range(int(cx - rx - 1), int(cx + rx + 2)):
                dx, dy = (x + 0.5 - cx) / rx, (y + 0.5 - base) / ry
                if abs(dx) ** 2.4 + abs(dy) ** 2.4 > 1 or not (0 <= x < W):
                    continue
                nz = math.sqrt(max(0.0, 1 - min(1.0, dx * dx + dy * dy)))
                lit = -0.55 * dx - 0.7 * dy + 0.45 * nz
                c = tones[0] if lit > 0.62 else tones[1] if lit > 0.3 else tones[2] if lit > 0.02 else tones[3]
                if moss and dy < -0.62 and lit > 0.15:
                    c = hexc(GREEN[3])                 # 顶上一点青苔
                main[y, x] = c
                mask[y, x] = True
        cols = [x for x in range(int(cx - rx - 1), int(cx + rx + 2)) if 0 <= x < W and mask[base, x]]
        if not cols:
            continue
        if wet:
            for x in cols:                                   # 贴水的暗边 + 倒影（压扁一半）
                main[base + 1, x] = mix(hexc(ROCK_WET), main[base + 1, x], 0.25)
                for d in range(0, int(ry)):
                    sy, ty = base - d, base + 2 + d // 2
                    if ty < H and mask[sy, x] and tuple(main[ty, x]) in pool:
                        main[ty, x] = mix(tones[2], main[ty, x], 0.55)    # 倒影一个色（混进那一行的水色），不碎
        else:
            for x in range(cols[0] - 1, cols[-1] + 2):       # 草里：底下一道淡影
                if 0 <= x < W and not mask[base + 1, x]:
                    main[base + 1, x] = mix(main[base + 1, x], hexc(GREEN[1]), 0.45)
    for (cx, base, rx) in spots:                             # 只在每块石头周围清理（别的地方和第十一版逐像素一样）
        y0, y1 = max(0, int(base - rx - 4)), min(H, int(base + rx + 6))
        x0, x1 = max(0, int(cx - rx - 5)), min(W, int(cx + rx + 6))
        Y0, Y1, X0, X1 = max(0, y0 - 4), min(H, y1 + 4), max(0, x0 - 4), min(W, x1 + 4)
        win = main[Y0:Y1, X0:X1].copy()                       # 多带一圈邻居一起清，只把里面那块贴回去（边上的格子看得见真的邻居）
        for _ in range(2):
            corner_fix(win)
            speck_fix(win)
        corner_fix(win)
        main[y0:y1, x0:x1] = win[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0]
    ROCK_SPOTS[:] = [(round(x), round(y), round(r, 1)) for x, y, r in spots]
    return mask


ROCK_SPOTS: list = []


# ---------------------------------------------------------------- 会动的芦苇：每种在每个角度下画一帧
def reed_variants():
    """每排几种：L 总长（含穗）、P 穗长、PW 穗宽、nod 平时穗往右垂多少度、strands 穗下沿垂下来的几缕穗丝、
    leaves [(在秆的几成处, 左右, 长, 弧)]"""
    rng = np.random.default_rng(83)
    out = {}
    #       种数  总长        穗长      穗宽         点头
    spec = {"r0": (5, (34, 70), (13, 18), (4.2, 5.4), (50, 80)),
            "r1": (6, (26, 64), (12, 17), (4.0, 5.2), (46, 76)),
            "r2": (4, (22, 40), (9, 13), (3.0, 3.8), (40, 64))}
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
                                 "strands": strands, "slen": rng.integers(2, 5, len(strands)).tolist(), "leaves": leaves,
                                 "thick": bool(L > 36 and rng.random() < 0.5)}
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
        if v.get("thick") and j < n * 0.55:
            px[(p[0] + 1, p[1])] = hexc(pal["stem"][0])       # 粗的那几根：下半截两格宽
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
    """芦苇（reed_variants）+ 草丛（grass_variants）每种 31 个角度各一帧，装进一张图集。帧按高矮排架子（宽 2048），
    同一帧图（草丛 θ 超过 ±40 的那些是同一张）只装一次。meta：angles、variants{名字: {row, L, rest, frames[[x,y,w,h,ox,oy,顶x,顶y]…]}}"""
    vs = reed_variants()
    frames = {}
    for name, v in vs.items():
        lst = []
        for a in ANGLES:
            img, ox, oy = clean_sprite(reed_frame(v, a))
            ys, xs = np.nonzero(img[..., 3])
            top = ys.min()
            tx = int(xs[ys == top].mean())
            lst.append((img, ox, oy, tx + ox, int(top) + oy))
        frames[name] = lst
    grass = grass_variants()
    for name, g in grass.items():
        frames[name] = g["frames"]
        vs[name] = {"row": "g", "L": g["h"], "rest": 0.0, "kind": g["kind"], "size": g["size"], "h": g["h"]}
    uniq = {}
    for name in frames:
        for fr in frames[name]:
            uniq.setdefault(id(fr[0]), fr[0])
    order = sorted(uniq, key=lambda k: -uniq[k].shape[0])
    AW = 2048
    pos = {}
    x = y = shelf = 0
    for k in order:
        h, w = uniq[k].shape[:2]
        if x + w > AW:
            x, y, shelf = 0, y + shelf + 1, 0
        pos[k] = (x, y)
        x += w + 1
        shelf = max(shelf, h)
    atlas = blank(AW, y + shelf + 1)
    for k, (x, y) in pos.items():
        h, w = uniq[k].shape[:2]
        atlas[y:y + h, x:x + w] = uniq[k]
    meta = {"angles": ANGLES, "variants": {}}
    for name in frames:
        fl = []
        for img, ox, oy, tx, ty in frames[name]:
            px, py = pos[id(img)]
            h, w = img.shape[:2]
            fl.append([px, py, w, h, ox, oy, tx, ty])
        v = vs[name]
        meta["variants"][name] = {"row": v["row"], "L": v["L"], "rest": round(v["rest"], 2), "frames": fl}
    return atlas, meta, vs, grass


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


# ================================================================ 第十一版：超前景、雾
# 作者（11-01）：「这个场景已经很不错了」，再加：超前景（镜头最前面离得很近、虚的大植物）和几层薄雾（把远近隔开、有空气感）。
# 超前景（fg.png，reed_field.gd 自己挂一个 Sprite2D：scroll 1.6、z 116，在 gf 前面）：
#   几丛很近的大芦苇叶 / 草叶从画面下沿探进来（根在画面外），一两团没对上焦的蒲公英绒球贴着下沿。颜色偏冷、压暗、淡，形状只有身子、
#   背光一侧、受光一道边三档，没有细节（虚）。数量克制：整条路上 6 处，一屏里通常一两处。
#   高的那几丛（顶高过 y 200）在晨停下来说话的地方（markers）不会在屏幕中间（FG_CLEAR 以外）；盖住晨或者正在说话的人时，
#   reed_field.gd 把它淡到 FG_DIM（和 room_stage 的 front 层一个意思）。随风轻摆，100ms 一帧。
FG_SCROLL = 1.6
FG_Y = 120
FG_W = int(math.ceil((W - 480) * FG_SCROLL)) + 480 + 8
FG_H = H - FG_Y
FG_TONES = ["#88b4a7", "#9ec5b8", "#b9d8cc"]      # 背光、身子、受光边
FLUFF_TONES = ["#d7e8e4", "#e6f1ed", "#f2f8f4"]
FG_CLEAR = (130, 350)                             # markers 那几个镜头位置，高的超前景不进屏幕的这一段


def fg_blade(img, tone_idx, x0, top, lean, wid, curve):
    """一片很近的芦苇叶：根在画面下沿外，往上长到 top 附近再往 lean 那边弯过去、叶尖垂下来一点（像一条软带子，不是直的尖刺）；
    左半身子、右半背光，左边一道受光边（上半截才有）"""
    h, w = img.shape[:2]
    droop = abs(lean) * (0.25 + curve * 0.6)
    p0 = (x0, h + 10)
    p1 = (x0 + lean * 0.05, top - 6)
    p2 = (x0 + lean * 0.75, top - 10)
    p3 = (x0 + lean, top + droop)
    n = int((p0[1] - top) * 2 + abs(lean) * 2) + 10
    tones = [hexc(c) for c in FG_TONES]
    for i in range(n + 1):
        t = i / n
        a, b, c_, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        cx = a * p0[0] + b * p1[0] + c_ * p2[0] + d * p3[0]
        cy = a * p0[1] + b * p1[1] + c_ * p2[1] + d * p3[1]
        tx = 3 * (1 - t) ** 2 * (p1[0] - p0[0]) + 6 * (1 - t) * t * (p2[0] - p1[0]) + 3 * t * t * (p3[0] - p2[0])
        ty = 3 * (1 - t) ** 2 * (p1[1] - p0[1]) + 6 * (1 - t) * t * (p2[1] - p1[1]) + 3 * t * t * (p3[1] - p2[1])
        r = max(0.6, wid / 2 * (1 - t) ** 0.9)
        for yy in range(int(cy - r - 1), int(cy + r + 2)):
            for xx in range(int(cx - r - 1), int(cx + r + 2)):
                if not (0 <= yy < h and 0 <= xx < w):
                    continue
                dx, dy = xx + 0.5 - cx, yy + 0.5 - cy
                if dx * dx + dy * dy > r * r:
                    continue
                side = tx * dy - ty * dx                 # < 0：中线左边
                if side > 0:
                    c = tones[max(0, tone_idx - 1)]
                elif t > 0.35 and dx * dx + dy * dy > (r - 1.1) ** 2 and r > 1.6:
                    c = tones[min(2, tone_idx + 1)]
                else:
                    c = tones[tone_idx]
                img[yy, xx] = c


def fg_fluff(img, cx, r, rng):
    """没对上焦的蒲公英绒球，一大半在画面下沿外：外圈、里圈、左上一块亮，三档；边上轻轻起伏"""
    h, w = img.shape[:2]
    cy = h + r * 0.35
    bumps = knots(360, 9, rng, 0.05, period=360)
    tones = [hexc(c) for c in FLUFF_TONES]
    for yy in range(max(0, int(cy - r * 1.1)), h):
        for xx in range(int(cx - r * 1.1), int(cx + r * 1.1)):
            if not (0 <= xx < w):
                continue
            dx, dy = xx + 0.5 - cx, yy + 0.5 - cy
            d = math.hypot(dx, dy)
            a = int(math.degrees(math.atan2(dy, dx))) % 360
            rr = r * (1 + bumps[a])
            if d > rr:
                continue
            lit = (-dx * 0.6 - dy * 0.8) / rr
            img[yy, xx] = tones[2] if (d < rr * 0.62 and lit > 0.25) else tones[1] if d < rr * 0.8 else tones[0]


def draw_fg():
    """超前景整条（不 tile）：屏幕 x = 图 x − 镜头 × FG_SCROLL。几丛叶 + 一两团绒球，高的避开 markers 的镜头"""
    rng = np.random.default_rng(1111)
    img = blank(FG_W, FG_H)
    marks = [m for m in room_json_markers()]
    cams = [min(max(m - 240, 0), W - 480) for m in marks]

    def clear_at(a, b):
        return all(b - c * FG_SCROLL < FG_CLEAR[0] or a - c * FG_SCROLL > FG_CLEAR[1] for c in cams)
    # (种类, 大约在哪（图 x）, 多高)。tall：顶到 y 172–196；low：顶在 y 226 以下（晨脚底那行以下，不挡人）
    plan = [("low", 150), ("tall", 560), ("fluff", 980), ("low", 1380), ("tall", 1900), ("low", 2350), ("fluff", 2640)]
    placed = []
    for kind, x in plan:
        x += rng.uniform(-40, 40)
        span = 70 if kind == "tall" else 50
        if kind == "tall":
            for _ in range(40):
                if clear_at(x - span / 2, x + span / 2):
                    break
                x += 23
        placed.append((kind, x))
        if kind == "fluff":
            fg_fluff(img, x, rng.uniform(30, 40), rng)
            continue
        nb = int(rng.integers(3, 5)) if kind == "tall" else int(rng.integers(2, 4))
        for k in range(nb):                          # 后面的先画（深一档），前面的后画
            top = (rng.uniform(172, 196) if kind == "tall" else rng.uniform(226, 244)) - FG_Y + (k * 6 if kind == "tall" else 0)
            lean = rng.choice([-1, 1]) * rng.uniform(24, 56)
            fg_blade(img, 0 if k == 0 and nb > 2 else 1, x + rng.uniform(-span / 2, span / 2), top, lean,
                     rng.uniform(16, 24) if kind == "tall" else rng.uniform(13, 18), rng.uniform(0.1, 0.5))
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    alpha_fix(img)
    de_alt(img, passes=2)
    corner_fix(img)
    edge_diag_fill(img)
    speck_fix(img)
    corner_fix(img)
    FG_PLACED[:] = placed
    return img


FG_PLACED: list = []


def room_json_markers():
    return [60, SPOTS[0], SPOTS[1], (TOWN[0] + TOWN[1]) // 2, SPOTS[2], 1860]


# 雾：几条贴着水面、夹在草洲之间的薄雾（各自一层，层的 alpha 让它半透明），越远越宽越淡，和远山脚下的雾一个颜色。
# 每一缕两头尖、上沿软软起伏；里面按离中线多远分三档颜色（外圈、中间、芯），叠在半透明里就是一层层柔和的过渡，没有抖点、没有硬方块。
# mist_low：近景前面偶尔慢慢飘过的一缕低雾（tile 1920 只有两缕，drift 很慢，z 25 在晨和脚踝的水面前面、gf 后面）。
MIST_TONES = ["#e6f1ee", "#eef5f0", "#f6faf3"]
MISTS = [
    # id, 插在哪一层前面（room.json 的层顺序）, scroll, 屏幕 y, 高, alpha, 几缕, 长, 厚, tile 宽, drift, z
    ("mist_hills", "far", 0.1, 124, 22, 0.42, 7, (160, 340), (5, 9), 960, 0.0, None),
    ("mist_far", "mid", 0.24, 136, 22, 0.36, 7, (120, 280), (4, 8), 960, 0.0, None),
    ("mist_mid", "isles", 0.48, 150, 22, 0.3, 6, (110, 240), (4, 7), 960, 0.0, None),
    ("mist_low", "ankle", 1.15, 192, 46, 0.24, 2, (170, 260), (8, 14), 1920, 1.2, 25),
]


def draw_mist(spec):
    mid, _after, _sc, _y, h, _a, n, (lmin, lmax), (tmin, tmax), w, _drift, _z = spec
    rng = np.random.default_rng(sum(map(ord, mid)))
    img = blank(w, h)
    tones = [hexc(c) for c in MIST_TONES]
    x = rng.uniform(0, w / n)
    for _ in range(n):
        L = rng.uniform(lmin, lmax)
        th = rng.uniform(tmin, tmax)
        yc = rng.uniform(th * 0.6 + 1, h - th * 0.5 - 2)
        wave = knots(int(L) + 2, 40, rng, 1.2)
        topn = knots(int(L) + 2, 11, rng, 0.9)
        for i in range(int(L)):
            u = i / L
            e = math.sin(math.pi * u) ** 0.8
            t = th * e * (0.8 + 0.2 * math.sin(u * 7 + yc))
            if t < 0.6:
                continue
            c0 = yc + wave[i]
            top = c0 - t * 0.6 + topn[i] * e
            bot = c0 + t * 0.4
            for y in range(int(round(top)), int(round(bot)) + 1):
                if 0 <= y < h:
                    d = abs(y - c0) / max(t * 0.5, 0.5)
                    img[y, int(x + i) % w] = tones[2] if d < 0.35 else tones[1] if d < 0.75 else tones[0]
        x += L + rng.uniform(20, w / n)
    for _ in range(2):                                 # 两缕之间只隔一行的地方补上（不然后面的清理会把那一行补成一格一格的）
        a = img[..., 3] > 0
        gap = ~a[1:-1] & a[:-2] & a[2:]
        ys, xs = np.nonzero(gap)
        img[ys + 1, xs] = img[ys, xs]
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    alpha_fix(img)
    de_alt(img, passes=2)
    corner_fix(img)
    edge_diag_fill(img)
    speck_fix(img)
    corner_fix(img)
    return img


# ================================================================ 第十版：湿地里更多活的东西（作者：「惊鸟非常好，但是除此之外太单调，湿地都是一片生机」）
# 数量克制（第七版被批过「太过于杂乱」）：岛层水上两三只白鹭、两小群野鸭，远处天上偶尔一队鸟慢慢飞过。惊鸟一点不动。
# 都是几个像素概括的剪影（和惊鸟一个画法：一个字母一种颜色），白鹭和野鸭的帧里自带贴水的一道亮线和水里的倒影。
# 动作在 reed_field.gd：白鹭大多站着，隔几秒低头啄一下水 / 抬一下脚 / 转个身；野鸭在两片洲之间的水上慢慢划来划去，
# 身后拖一小道波纹，偶尔扎个猛子（屁股朝天）；鸟群排成松散的人字，扇几下滑一下，从画面一边飞到另一边。都是 100ms 一帧。
FAUNA_C = {"W": "#fdfdf4", "S": "#c4dae6", "Y": "#f2cb40", "L": "#8e9ea4",
           "B": "#cdbd92", "D": "#9b9c88", "G": "#7fae8f"}
EGRET_FR = {
    "stand": ["...WWYY..", "...WW....", "...W.....", "...WW....", "....W....", "..WWWW...", ".WWWWWW..", "SSWWWWS..",
              ".SSSSSS..", "....L....", "....L....", "....L...."],
    "half": [".........", ".........", ".........", "......WYY", ".....WW..", "..WWWW...", ".WWWWWW..", "SSWWWWS..",
             ".SSSSSS..", "....L....", "....L....", "....L...."],
    "down": [".........", ".........", ".........", ".........", ".........", "..WWWW...", ".WWWWWWW.", "SSWWWWSW.",
             ".SSSSSSWW", "....L...Y", "....L...Y", "....L...."],
    "lift": ["...WWYY..", "...WW....", "...W.....", "...WW....", "....W....", "..WWWW...", ".WWWWWW..", "SSWWWWS..",
             ".SSSSSS..", "....LLL..", "....L.L..", "....L...."],
}
DUCK_FR = {
    "swim0": ["...GY", "DBBG.", ".BBB."],
    "swim1": ["...GY", ".BBG.", "DBBB."],
    "dabble": ["D....", "BB...", ".BBBG"],
}
FAUNA_Y = {"egret": 172, "duck": 167}           # 白鹭脚 / 野鸭贴水那一行的屏幕 y（岛层的水上）
FLOCK = {"scroll": 0.1, "y": [30, 74], "speed": 7.0}
FAUNA_Z: dict = {}


# 第十一版：晨在浅水里每落一脚溅一簇水花（reed_field.gd 盯着晨的动画：run 的图集帧 18、21 和 run_stop 的 24 是脚着地那帧，
# 看 art/characters/chen/chen_oscar.png：这三帧后脚踩到最低那行 58）。
# 第十二版（作者：「你是涟漪而不是水花」——上一版水珠只有一两个像素、颜色和水差不多）：六帧，100ms 一帧，美术朝右（水往身后、左边甩）：
#   0 落脚：脚两边各翻起一圈水冠（5 像素高）；1 水冠冲到最高（7 像素），四颗水珠离开；2–4 水珠走抛物线，水冠塌回去；
#   5 水珠落回水面，各漾开一个小点。亮面是接近白的高光 H，身子 M，背光一侧和水冠根上是比水深一档的青蓝 D——淡色背景上靠明暗分得出来。
#   大水珠 2×2（H M / M D），小水珠 1×2（H / D），没有孤立的单点。锚点 = 水面那一行、脚的正下方。涟漪还在（reed_field.gd 另画，在水花下面）。
SPLASH_C = {"H": "#fbfefb", "M": "#c4e8ee", "D": "#5b9cae"}
SPLASH_W, SPLASH_H = 23, 15
SPLASH_ANCHOR = (12, 14)
SPLASH_CROWN = [5, 7, 4, 2, 0, 0]                  # 每帧水冠多高（0 = 没了）
# 每颗水珠：大小、第 1–5 帧在哪（x 偏移，离水面多高；h ≤ 0 = 落回水面那一下，画一个小点）
SPLASH_DROPS = [
    ("big", [(-4, 7), (-6, 10), (-8, 10), (-9, 7), (-10, 0)]),
    ("small", [(-5, 4), (-7, 6), (-9, 5), (-11, 2), None]),
    ("small", [(-2, 8), (-3, 11), (-4, 12), (-5, 9), (-6, 3)]),
    ("small", [(4, 5), (5, 7), (6, 6), (7, 2), (8, 0)]),
]
SPLASH_FRAMES = 6


def splash_frames():
    ax, ay = SPLASH_ANCHOR
    out = []
    for f in range(SPLASH_FRAMES):
        g = [["."] * SPLASH_W for _ in range(SPLASH_H)]

        def put(dx, hh, c):
            x, y = ax + dx, ay - hh
            if 0 <= x < SPLASH_W and 0 <= y < SPLASH_H:
                g[y][x] = c
        h = SPLASH_CROWN[f]
        for side in (-1, 1):
            if h <= 0:
                if f == 4:                          # 水冠塌回去：根上剩一小截暗边
                    for x in (3, 4):
                        put(side * x, 0, "D")
                continue
            for y in range(0, h + 1):
                xs = [2, 3, 4, 5] if y == 0 else [2, 3, 4] if y <= max(1, h // 3) else [3, 4] if y < h else [4]
                for x in xs:
                    if y == 0:
                        c = "D"
                    elif y == h:
                        c = "H"
                    elif x == xs[-1]:
                        c = "D"                      # 外侧背光
                    elif y >= h - 2:
                        c = "H"
                    else:
                        c = "M"
                    put(side * x, y, c)
        if f >= 1:
            for size, path in SPLASH_DROPS:
                q = path[f - 1]
                if q is None:
                    continue
                dx, hh = q
                if hh <= 0:                         # 落回水面：一个小点（中间深、两边浅）
                    put(dx - 1, 0, "M")
                    put(dx, 0, "D")
                    put(dx + 1, 0, "M")
                elif size == "big":
                    put(dx, hh, "H")
                    put(dx + 1, hh, "M")
                    put(dx, hh - 1, "M")
                    put(dx + 1, hh - 1, "D")
                else:
                    put(dx, hh, "H")
                    put(dx, hh - 1, "D")
        im = blank(SPLASH_W, SPLASH_H)
        for y in range(SPLASH_H):
            for x in range(SPLASH_W):
                if g[y][x] in SPLASH_C:
                    im[y, x] = hexc(SPLASH_C[g[y][x]])
        out.append(im)
    return out


def fauna_frame(rows, foot_row, water_y, haze, ripple_w):
    """字母图 → 一帧（带贴水亮线 + 倒影）。foot_row：贴水的那一行（白鹭的脚、野鸭的肚子）；倒影从下一行往下，压扁一半、混进那里的水色"""
    w, h = len(rows[0]), len(rows)
    rh = (foot_row + 1) // 2 + 1
    img = blank(w + 2, h + rh + 1)
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c in FAUNA_C:
                img[y, x + 1] = mix(hexc(FAUNA_C[c]), hexc(HAZE), haze)
    body = img.copy()
    wy = foot_row + 1
    cols = [x for x in range(w + 2) if body[:foot_row + 1, x, 3].any()]
    cx = (min(cols) + max(cols)) / 2
    for x in range(int(round(cx - ripple_w / 2)), int(round(cx + ripple_w / 2)) + 1):
        if 0 <= x < w + 2:
            img[wy, x] = mix(hexc("#f6fbf4"), hexc(bgw_c(water_y + 1)), 0.2)
    for k in range(1, rh + 1):
        sy = foot_row - (k - 1) * 2
        if sy < 0:
            break
        for x in range(w + 2):
            if body[sy, x, 3] and wy + k < img.shape[0]:
                img[wy + k, x] = mix(body[sy, x], hexc(bgw_c(water_y + 1 + k)), 0.62)
    speck_fix(img)
    corner_fix(img)
    alpha_fix(img)
    speck_fix(img)
    return img, (int(round(cx)), foot_row)


def build_fauna():
    """白鹭、野鸭、远处鸟群的帧 → fauna.png（一行排开，帧和帧之间空一列）+ fauna.json"""
    frames = {}
    for k, rows in EGRET_FR.items():
        frames["egret_" + k] = fauna_frame(rows, len(rows) - 1, FAUNA_Y["egret"], 0.0, 5)
    for k, rows in DUCK_FR.items():
        frames["duck_" + k] = fauna_frame(rows, len(rows) - 1, FAUNA_Y["duck"], 0.12, 5)
    for i, im in enumerate(splash_frames()):
        frames[f"splash_{i}"] = (im, (SPLASH_ANCHOR[0], SPLASH_ANCHOR[1]))
    sky = hexc("#cbe8f4")
    for s, names in ((2, ("up", "mid", "down")), (3, ("up", "mid", "down"))):
        for fr, nm in zip(BIRD_FR[s], names):
            w, h = len(fr[0]), len(fr)
            im = blank(w, h)
            for y, r in enumerate(fr):
                for x, c in enumerate(r):
                    if c in ("D", "B", "T"):
                        im[y, x] = mix(hexc({"D": BIRD["wing"], "B": BIRD["body"], "T": BIRD["tail"]}[c]), sky, 0.45)
            frames[f"flock{s}_{nm}"] = (im, (w // 2, h // 2))
    W2 = sum(im.shape[1] + 1 for im, _ in frames.values())
    H2 = max(im.shape[0] for im, _ in frames.values())
    atlas = blank(W2, H2)
    meta = {"frames": {}}
    x = 0
    for k, (im, (ax, ay)) in frames.items():
        h, w = im.shape[:2]
        atlas[:h, x:x + w] = im
        meta["frames"][k] = [x, 0, w, h, ax, ay]
        x += w + 1
    return atlas, meta


def open_water_runs(isles):
    """岛层里真正开阔的水：根那几行（ISL_B 上下）一格植物都没有的列，连成段（tile 首尾相接）。返回 [(x0, x1)]，x1 可能 > 960"""
    w = isles.shape[1]
    rows = isles[ISL_B - 5:ISL_B + 3]
    plant = np.zeros(w, bool)
    for x in range(w):
        for y in range(rows.shape[0]):
            c = tuple(rows[y, x])
            if c[3] and c not in BGW_SET:
                plant[x] = True
                break
    if plant.all():
        return []
    start = int(np.argmax(plant))                    # 从一格植物开始绕一圈，段就不会被 0 / 960 切开
    runs, a = [], None
    for i in range(1, w + 1):
        x = (start + i) % w
        if not plant[x] and a is None:
            a = start + i
        if plant[x] and a is not None:
            runs.append((a, start + i - 1))
            a = None
    return [(a % w, a % w + (b - a)) for a, b in runs]


def fauna_places(meta, isles):
    """白鹭站在开阔水的边上（挨着洲、朝着水），野鸭在开阔水中间划；都用岛层的层坐标"""
    rng = np.random.default_rng(1077)
    runs = sorted(open_water_runs(isles), key=lambda r: -(r[1] - r[0]))
    egrets, ducks = [], []
    for i, (a, b) in enumerate(runs[:4]):
        if len(egrets) < 3 and b - a > 40:
            side = 1 if i % 2 == 0 else -1
            x = a + rng.uniform(3, 6) if side > 0 else b - rng.uniform(3, 6)
            egrets.append([round(x % 960, 1), FAUNA_Y["egret"], side])          # side 1：洲在左边，脸朝右（朝水）
    for (a, b) in runs[:4]:
        if len(ducks) < 2 and b - a > 60:
            ducks.append([round(a + 16, 1), round(b - 16, 1), FAUNA_Y["duck"], int(rng.integers(1, 3))])
    meta["egrets"] = egrets
    meta["ducks"] = ducks
    meta["isle_scroll"] = 0.62
    meta["flock"] = FLOCK
    print("  岛层开阔的水：", [(round(a), round(b)) for a, b in runs[:6]], "白鹭", egrets, "野鸭", ducks)
    return meta


# ================================================================ 第六版：一片连起来的湿地水面、草丛为主、前后几层
# 作者（10-31）：「颜色好了，但是缺乏质感。水体很有质感，可以一直连成一片；芦苇太多竿竿，跟竖琴一样，换成草和一些芦苇；看起来只有一层」
# - 水：整张图是一片连着的浅水（远处中景的水、岛层的水、晨脚下的水同一套颜色，按离地平线多远取色 water_c），
#   陆地只有开头的岸（LAND 第一段）和草原小镇那段（第二段），岸是斜着收进水里的。晨大部分时候在浅水里走。
# - 草丛为主：一团团绵软的草（grass_base：几片叶团从后往前叠，叶团之间有一道暗的分隔，上沿受光、下半背光、根上一道湿的暗边），
#   每团也像芦苇一样预先画好 31 个弯曲角度（整团按离根的高度横着错开，像被压弯），在水里的那些把「湿边 + 倒影」一起画进帧里，
#   reed_field.gd 用同一套弹簧阻尼让它们和零星的芦苇一起被晨压下去、再弹回来。
# - 芦苇只零星几簇（3–6 根），长短、粗细、斜度都不一样，根藏在草丛后面。
# - 层次：远山 → 远岸（far）→ 中景的水和小洲（mid，scroll 0.4，小、淡）→ 岛（isles，scroll 0.68，中等）→ 晨这一层（main，静止的小岛 +
#   会动的草丛 g0 / g1 / g2 和芦苇 r0 / r1 / r2）→ 前景（gf，scroll 1.3，画面下沿几团大的、深一点的草，顶不超过 y 238，不挡晨也不挡路）。
LAND: list = []                         # 第八版：没有陆地了，整张图都是湿地（以前开头的岸和小镇那段）
LAND_EDGE = 150
MAIN_TOP = 184                          # 晨这一层的水从这一行开始（上面接着岛层的水）
WATER_Y0 = 148                          # 水的颜色：从这一行（远）到画面下沿（近）走一遍 POOL
GRASS_T = {                              # 草丛的颜色（暗缝、背光、身子、受光、叶尖）—— 都在定好的那套颜色里
    "Y": (RAMP[0], RAMP[1], RAMP[2], RAMP[4], RAMP[3]),
    "YG": (YGREEN[0], YGREEN[1], YGREEN[2], YGREEN[4], YGREEN[3]),
    "G": ("#93c47a", GREEN[0], GREEN[1], GREEN[3], GREEN[2]),
    "M": (GREEN[8], GREEN[7], GREEN[6], GREEN[4], GREEN[2]),
    "GF": ("#86b86e", "#93c47a", GREEN[0], GREEN[2], GREEN[1]),      # 前景：深一档
}
YARD_FLAT = (338, 446)                   # 结局一被压倒的那一大片草（tools/reed_field_props.py 画）：这一段不放会动的草丛 g1
ROW_Z = {"r0": -40, "g0": -38, "r1": -30, "g1": -28, "r2": 5, "g2": 6, "g3": 24, "g4": 112, "gf": 115}
ROW_SCROLL = {"gf": 1.3, "g4": 1.25}


def water_c(y):
    u = float(np.clip((y - WATER_Y0) / (H - WATER_Y0), 0, 1))
    return POOL[min(len(POOL) - 1, int(u ** 0.85 * len(POOL)))]


def land_amt(x):
    best = 0.0
    for a, b in LAND:
        best = max(best, sstep(a - LAND_EDGE / 2, a + LAND_EDGE / 2, x) * (1 - sstep(b - LAND_EDGE / 2, b + LAND_EDGE / 2, x)))
    return best


def grass_base(w, h, tones, rng, tall=0.0, sep=True, style="grass", fringe=1.0):
    """一团草（静止的样子）：pad 一圈透明。几片软叶团从后往前叠（中间高、两边矮，轮廓起伏），每片前先压一道暗缝（往右下错一格），
    叶团内：上沿左半受光、下半背光；根上两行暗（坐在地上 / 水里）。tall > 0：再插几片高而细的叶（有高有矮）。返回 (图, 根的 x, 根的 y)"""
    pad = 6
    W2, H2 = w + pad * 2, h + pad + 3
    img = blank(W2, H2)
    bx, by = W2 // 2, H2 - 2
    n = max(3, w // 8 + int(rng.integers(0, 3)))
    if style == "cat":
        n = 1                                        # 香蒲：底下一小团软叶，上面是一丛剑一样的长叶 + 几根带棒头的茎
    lobes = []
    for k in range(n):
        u = (k + 0.5) / n * 2 - 1 + rng.uniform(-0.12, 0.12)
        hl = h * (1 - 0.5 * u * u) * rng.uniform(0.7, 1.05)
        wl = rng.uniform(9.0, 15.0) * (0.75 + 0.45 * (1 - abs(u)))
        lean = u * 0.25 + rng.uniform(-0.1, 0.1)
        lobes.append((abs(u) - rng.uniform(0, 0.3), bx + u * w * 0.4, hl, wl, lean, True))
    for _ in range(int(tall * rng.integers(2, 5))):
        u = rng.uniform(-0.6, 0.6)
        lobes.append((rng.uniform(0.2, 0.6), bx + u * w * 0.4, h * rng.uniform(1.1, 1.4), rng.uniform(2.8, 3.8),
                      u * 0.5 + rng.uniform(-0.15, 0.15), False))
    if style == "cat":
        for _ in range(max(5, w // 3)):
            u = rng.uniform(-0.9, 0.9)
            lobes.append((rng.uniform(-0.4, 0.4), bx + u * w * 0.4, h * rng.uniform(0.65, 1.0), rng.uniform(2.6, 3.6),
                          u * 0.3 + rng.uniform(-0.18, 0.18), False))
    # 上沿一圈短尖的草叶（是草，不是一块面包）：从软团的顶附近冒出来，往两边斜，长短不一
    for _ in range(int(max(3, w // 5) * fringe) if style != "cat" else 0):
        u = rng.uniform(-0.85, 0.85)
        hb = h * (1 - 0.5 * u * u) * rng.uniform(0.55, 0.85)
        lobes.append((rng.uniform(-0.6, -0.1), bx + u * w * 0.42, hb + rng.uniform(3, 8), rng.uniform(2.4, 3.4),
                      u * 0.6 + rng.uniform(-0.2, 0.2), False))
    # 后面（离中心远 / 矮的）先画，前面的压上去
    lobes.sort(key=lambda t: -t[0])
    dark, shade, body, lit, tip = tones

    def blade(cx, hl, wl, lean, col_fn, grow=0.0, soft=True):
        steps = max(6, int(hl * 2))
        for i in range(steps + 1):
            t = i / steps
            px = cx + math.sin(lean) * hl * t + 0.12 * hl * t * t * (1 if lean >= 0 else -1)
            py = by - hl * t * (1 - 0.1 * t * t)
            if soft:                                 # 软团：顶是圆的（像一团绒）
                r = wl * 0.5 * max(0.0, 1 - t ** 2.4) ** 0.5 + 0.5 + grow
                py = by - (hl - wl * 0.35) * t
            else:                                    # 高叶：尖的
                r = wl * 0.5 * (1 - t) ** 0.7 + 0.5 + grow
            for yy in range(int(py - r - 1), int(py + r + 2)):
                for xx in range(int(px - r - 1), int(px + r + 2)):
                    dx, dy = xx - px, yy - py
                    if 0 <= xx < W2 and 0 <= yy < H2 and dx * dx + dy * dy <= r * r and yy <= by:
                        img[yy, xx] = hexc(col_fn(t, dx / max(r, 0.6), yy))

    for (_o, cx, hl, wl, lean, soft) in lobes:
        if sep and soft:                             # 暗缝只垫在软团后面（细叶后面垫会拉出一道道斜的细线）
            blade(cx + 1, hl, wl, lean, lambda t, d, yy: dark, grow=0.4, soft=soft)   # 暗缝（往右下错一点，压在后面的叶团上）
        if soft:
            blade(cx, hl, wl, lean, lambda t, d, yy: lit if (t > 0.72 and d < 0.35) or (d < -0.45 and t > 0.4) else
                  shade if (t < 0.3 or d > 0.5) else body, soft=True)
        else:
            blade(cx, hl, wl, lean, lambda t, d, yy: tip if t > 0.86 else lit if (d < -0.25 and t > 0.45) else
                  shade if (t < 0.3 or d > 0.45) else body, soft=False)
    if style == "cat":
        # 香蒲的棒头：一根细茎（四邻接）顶着一截圆柱（暖金，左边亮一档），顶上再冒一小截尖
        for _ in range(max(1, w // 12)):
            sx = bx + rng.uniform(-0.35, 0.35) * w
            top = by - h * rng.uniform(0.95, 1.2)
            lean = rng.uniform(-0.12, 0.12)
            pts = [(sx + lean * (by - (by - (by - top) * t)) * 0.3, by - (by - top) * t) for t in np.linspace(0, 1, 60)]
            for (x, y) in path4(pts):
                if 0 <= x < W2 and 0 <= y < H2:
                    img[y, x] = hexc(GREEN[0])
            hx, hy = pts[-1]
            hh = max(5, int(h * 0.2))
            for yy in range(int(hy) - hh, int(hy) - 1):
                for dx in (-1, 0, 1):
                    xx = int(round(hx)) + dx
                    if 0 <= xx < W2 and 0 <= yy < H2:
                        img[yy, xx] = hexc(RAMP[2] if dx < 0 else RAMP[1] if dx == 0 else RAMP[0])
            for yy in range(int(hy) - hh - 3, int(hy) - hh):
                xx = int(round(hx))
                if 0 <= xx < W2 and 0 <= yy < H2:
                    img[yy, xx] = hexc(GREEN[0])
    if style == "flw":
        # 开小花的：草团上面零星几朵（两格花瓣，落在草上，不是悬空的单点）
        aa = img[..., 3] > 0
        for _ in range(max(3, w // 6)):
            ys, xs = np.nonzero(aa)
            if not len(ys):
                break
            i = int(rng.integers(0, len(ys)))
            y, x = int(ys[i]), int(xs[i])
            if y > by - h * 0.35 or x + 1 >= W2 or not aa[y, x + 1]:
                continue
            c = hexc([GLINT[0], RAMP[6], RAMP[4], RAMP[3]][int(rng.integers(0, 4))])
            img[y, x] = img[y, x + 1] = c
    # 暗缝贴着透明的那一边换成背光色（不要一圈深色描边）
    a = img[..., 3] > 0
    dk = (img[..., :3] == hexc(dark)[:3]).all(-1)
    edge = np.zeros_like(a)
    edge[:, :-1] |= ~a[:, 1:]
    edge[:, 1:] |= ~a[:, :-1]
    edge[:-1, :] |= ~a[1:, :]
    img[dk & a & edge] = hexc(shade)
    # 根上两行暗：坐在地上
    for x in range(W2):
        col = np.nonzero(a[:, x])[0]
        if len(col) and col.max() >= by - 1:
            img[by, x] = hexc(dark) if a[by, x] else img[by, x]
    return img, bx, by


def grass_frames(base, bx, by, wet, wy):
    """一团草在 ANGLES 每个角度下的样子：每一行按离根多高横着错开（顶上错 h·0.5·sin θ，越往下越少），像整团被压弯；
    θ 超过 ±40 的按 ±40 算（草不会像芦苇那样倒下去）。wet：根下面画一道湿的暗边、一道亮边和倒影（两档，混进 wy 那一行的水色）。
    返回和芦苇帧一样的 [(图, ox, oy, 顶 x, 顶 y), …]（ox, oy = 图左上角相对根）。"""
    H2, W2 = base.shape[:2]
    a = base[..., 3] > 0
    ys = np.nonzero(a.any(1))[0]
    top = int(ys.min())
    h = by - top
    frames = []
    cache = {}
    wc = hexc(water_c(wy)).astype(float)
    for ang in ANGLES:
        th = math.radians(float(np.clip(ang, -40, 40)) * 0.85)
        key = round(th, 4)
        if key in cache:
            frames.append(cache[key])
            continue
        disp = h * 0.5 * math.sin(th)
        ext = int(abs(disp)) + 2
        rh = int(h * 0.55) if wet else 0
        out = blank(W2 + ext * 2, H2 + rh + 2)
        for y in range(H2):
            hh = max(0.0, (by - y) / max(1, h))
            sh = int(round(disp * hh ** 1.5))
            dy = int(round((1 - math.cos(th)) * h * 0.35 * hh ** 1.5))
            for x in range(W2):
                if a[y, x]:
                    yy = y + dy
                    if 0 <= yy <= by:
                        out[yy, x + sh + ext] = base[y, x]
        if wet:
            # 倒影：把弯好的这一团上下翻到根下面（压扁成 0.55），两档颜色混进水色；根下第一行一道暗（湿的影子）、第二行一道亮（水边的反光）
            src = out[:by + 1].copy()
            lum = src[..., 0].astype(float) * 0.3 + src[..., 1] * 0.55 + src[..., 2] * 0.15
            sa = src[..., 3] > 0
            midv = np.median(lum[sa]) if sa.any() else 0
            dark = np.round(hexc(REFL_TONES[0]).astype(float)[:3] * 0.55 + wc[:3] * 0.45).astype(np.uint8)
            light = np.round(hexc(REFL_TONES[1]).astype(float)[:3] * 0.55 + wc[:3] * 0.45).astype(np.uint8)
            for k in range(1, rh + 1):
                sy = by - int(k / 0.55)
                if sy < 0:
                    break
                for x in range(out.shape[1]):
                    if sa[sy, x]:
                        out[by + k, x, :3] = dark if k <= rh * 0.45 else light      # 靠根那一截深、远一截浅（按行分两档，不逐格换）
                        out[by + k, x, 3] = 255
            cols = np.nonzero(out[by].astype(bool)[:, 3] if False else out[by, :, 3] > 0)[0]
            if len(cols):
                for x in range(cols.min() - 1, cols.max() + 2):
                    if 0 <= x < out.shape[1]:
                        out[by + 1, x] = hexc("#7fb89a")
                        if by + 2 < out.shape[0] and out[by + 2, x, 3] == 0:
                            out[by + 2, x] = hexc(SURF[0])
        corner_fix(out)
        speck_fix(out)
        corner_fix(out)
        alpha_fix(out)
        edge_diag_fill(out)
        alpha_fix(out)
        yy2, xx2 = np.nonzero(out[..., 3] > 0)
        crop = out[yy2.min():yy2.max() + 1, xx2.min():xx2.max() + 1]
        ox = int(xx2.min()) - (bx + ext)
        oy = int(yy2.min()) - by
        cy, cx = np.nonzero(crop[..., 3] > 0)
        t0 = int(cy.min())
        tx = int(cx[cy == t0].mean()) + ox
        fr = (crop, ox, oy, tx, t0 + oy)
        cache[key] = fr
        frames.append(fr)
    return frames


def grass_variants():
    """草丛的种类：干的（陆地上，黄）和湿的（水里 / 水边，嫩绿、黄绿、薄荷，带倒影）；大、中、小。前景 gf：大、深一档、不带倒影（根在画面外）"""
    rng = np.random.default_rng(131)
    spec = [
        # 名字前缀, 排, 色, 湿, 宽, 高, 高叶, 几种
        ("gd_l", "dry", "Y", False, (56, 84), (24, 34), 0.6, 2),
        ("gd_m", "dry", "Y", False, (34, 52), (15, 24), 0.4, 2),
        ("gd_s", "dry", "Y", False, (16, 26), (9, 15), 0.0, 2),
        ("gw_l", "wet", "G", True, (56, 90), (24, 38), 0.7, 3),
        ("gw_m", "wet", "YG", True, (34, 56), (16, 26), 0.4, 2),

        ("gw_s", "wet", "G", True, (16, 26), (9, 15), 0.0, 2),
        ("gf", "front", "GF", False, (80, 120), (44, 60), 0.8, 3),
        ("flw_l", "flw", "YG", True, (44, 68), (18, 28), 0.2, 2),
        ("flw_m", "flw", "YG", True, (30, 44), (12, 20), 0.1, 2),
    ]
    out = {}
    for pre, kind, fam, wet, wr, hr, tall, n in spec:
        for i in range(n):
            w = int(rng.integers(*wr))
            h = int(rng.integers(*hr))
            base, bx, by = grass_base(w, h, GRASS_T[fam], rng, tall, style=kind if kind in ("cat", "flw") else "grass",
                                      fringe=0.5 if kind != "front" else 0.8)
            wy = 226 if kind != "front" else 260
            out[f"{pre}{i}"] = {"row": "g", "kind": kind, "size": pre[-1], "h": h, "rest": 0.0,
                                "frames": grass_frames(base, bx, by, wet, wy)}
    out.update(deep_variants())
    return out


# ---------------------------------------------------------------- 第十六版：晨脚前的水草（g3）+ 镜头前的大叶（g4）
# 作者看第十五版：「这些草太像了，像泡沫一样笼罩着主角」——第十五版的深草是 grass_base 那种圆鼓鼓的草团，连成一条整带、颜色和 main 草丛一样。
# 改成一根根的叶：两三像素宽、往上收尖、各自朝不同方向斜（plant_blade），混几种湿地植物，每种高矮不一：
#   莎草（细叶一丛）、香蒲（细秆顶一根棕黄蒲棒）、芦苇秆（顶上一小撮穗、秆上斜出两片蓝叶）、开小花的细茎、偶尔一两片很长的斜叶。
# 颜色只挑第十一版画面里已有的、和 main 草丛分得开的：叶 = 岛上那种偏冷的淡绿（DEEP_LEAF），蒲棒 = 芦苇秆的棕黄（DEEP_CAT），
# 芦苇 = 芦苇层的秆、穗、蓝叶（DEEP_REED），小花 = 奶白 / 白 / 淡蓝。没有比第十一版更深的颜色。
# 镜头前的大丛（g4）：根在画面下沿外。第十七版（作者：「最前面那两大丛像芦荟、龙舌兰」）改成香蒲和芦苇：细长的叶（有的折下来垂着）、
# 几根顶着暖棕蒲棒的香蒲秆、一两根带穗的芦苇秆；颜色用 main 草丛的绿、芦苇那一带的黄绿、蒲棒的棕黄（不再用超前景那套淡青灰）。
DEEP_LEAF = ["#b6dcba", "#a5d3a8", "#9ed0ac"]          # 受光、本色、背光
DEEP_CAT = ["#dbc05a", "#d5ba52", "#cfb34c"]
DEEP_REED = {"stem": ["#e0cb6c", "#dcc66a"], "plume": ["#ffeb8e", "#f8d445", "#93cbec"], "leaf": ["#93cbec", "#8cc3e3"]}
DEEP_FLOWER = ["#fffef6", "#fef3bf", "#bae2f3"]
NEAR_LEAF = [["#cbe39c", "#b8d98a", "#a6cf7c"],       # 第十七版镜头前的大丛：main 草丛的绿（受光、本色、背光）
             ["#e4df74", "#d8d466", "#cdcb58"]]       # 芦苇那一带草的黄绿
NEAR_REED_STEM = ["#e0cb6c", "#dcc66a", "#dbc05a"]


def plant_blade(img, x0, y0, L, ang, curve, w, tones, fold=None):
    """一片叶：根在 (x0, y0)，往上长 L，起始斜 ang（弧度，正 = 往右），越往上越往 ang 那边弯（curve）；
    根上 w 宽、往上收尖。法线朝左的那半边受光一档、宽的地方右边背光一档。
    fold = (t0, da)：长到 t0 那儿折一下，往 da 那边弯下去（叶子弯折下垂）"""
    H2, W2 = img.shape[:2]
    cs = [hexc(c) for c in tones]
    n = max(8, int(L * 4))
    x, y = float(x0), float(y0)
    for i in range(n + 1):
        t = i / n
        a = ang + curve * t
        if fold:
            a += fold[1] * sstep(fold[0] - 0.04, fold[0] + 0.06, t)
        r = w / 2 * (1 - t) ** 0.85
        ca, sa = math.cos(a), math.sin(a)
        for yy in range(int(y - r - 1), int(y + r + 2)):
            for xx in range(int(x - r - 1), int(x + r + 2)):
                if not (0 <= yy < H2 and 0 <= xx < W2):
                    continue
                dx, dy = xx + 0.5 - x, yy + 0.5 - y
                core = xx == int(math.floor(x)) and yy == int(math.floor(y))
                if not core and dx * dx + dy * dy > r * r:
                    continue
                sd = dx * ca + dy * sa                      # 横过叶片的距离（负 = 左边）
                img[yy, xx] = cs[0] if sd < -0.3 and r > 0.7 else cs[2] if sd > 0.5 and r > 1.1 else cs[1]
        x += sa * L / n
        y -= ca * L / n
    return x, y


def plant_stem(img, x0, y0, L, ang, c):
    """一根一像素的细秆（四邻接），微微弯；返回顶端"""
    pts = path4([(x0 + math.sin(ang) * L * t * (1 + 0.3 * t), y0 - L * t) for t in np.linspace(0, 1, int(L * 3) + 2)])
    for (px, py) in pts:
        if 0 <= py < img.shape[0] and 0 <= px < img.shape[1]:
            img[py, px] = hexc(c)
    return pts[-1]


def deep_plant(kind, h, rng):
    """一株（一小丛）水草，返回 (图, 根 x, 根 y)。种类：s/m 莎草矮/中、f 小花、c 香蒲、r 芦苇秆、t 很长的斜叶、n 镜头前的大叶"""
    big = kind == "n"
    W2, H2 = (int(h * 1.6) + 40, h + 16) if big else (int(h * 1.4) + 24, h + 12)
    img = blank(W2, H2)
    bx, by = W2 // 2, H2 - 2
    if kind in ("s", "m", "t"):
        nb = int(rng.integers(5, 9)) if kind != "t" else int(rng.integers(2, 4))
        blades = []
        for _ in range(nb):
            ang = rng.uniform(-0.65, 0.65)
            blades.append((h * rng.uniform(0.4, 0.95), ang, math.copysign(rng.uniform(0.1, 0.5), ang), float(rng.choice([2.0, 2.4, 3.0]))))
        if kind == "t":                                        # 一两片很长的斜叶（从晨身前划过去的那种）
            side = rng.choice([-1, 1])
            for k in range(int(rng.integers(1, 3))):
                blades.append((h * rng.uniform(0.9, 1.05), side * rng.uniform(0.32, 0.5), side * rng.uniform(0.15, 0.45), 3.0))
        else:
            blades.append((h, rng.uniform(-0.25, 0.25), rng.uniform(-0.3, 0.3), 2.6))
        for (L, ang, cv, w) in sorted(blades, key=lambda b: -b[0]):
            plant_blade(img, bx + ang * 3, by, L, ang, cv, w, DEEP_LEAF)
    elif kind == "f":
        for _ in range(int(rng.integers(3, 5))):
            ang = rng.uniform(-0.6, 0.6)
            plant_blade(img, bx + ang * 2, by, h * rng.uniform(0.3, 0.5), ang, math.copysign(0.3, ang), 2.0, DEEP_LEAF)
        for _ in range(int(rng.integers(3, 6))):
            tx, ty = plant_stem(img, bx + int(rng.integers(-3, 4)), by - 1, h * rng.uniform(0.6, 1.0), rng.uniform(-0.35, 0.35), DEEP_LEAF[1])
            c = hexc(DEEP_FLOWER[int(rng.integers(0, 3))])
            for (fx, fy) in ((tx, ty - 1), (tx + 1, ty - 1), (tx, ty)):
                if 0 <= fy < H2 and 0 <= fx < W2:
                    img[fy, fx] = c
    elif kind == "c":
        for _ in range(int(rng.integers(3, 5))):                # 底下几片剑一样的叶
            ang = rng.uniform(-0.45, 0.45)
            plant_blade(img, bx + ang * 3, by, h * rng.uniform(0.45, 0.8), ang, math.copysign(rng.uniform(0.1, 0.35), ang), 2.4, DEEP_LEAF)
        for _ in range(int(rng.integers(1, 3))):
            tx, ty = plant_stem(img, bx + int(rng.integers(-2, 3)), by - 1, h * rng.uniform(0.8, 1.0), rng.uniform(-0.12, 0.12), DEEP_LEAF[2])
            hh = int(rng.integers(6, 9))                        # 蒲棒：三格宽，左亮右暗，上下收圆一点，顶上再冒一小截秆
            for k in range(hh):
                yy = ty - 1 - k
                for dx, c in ((-1, DEEP_CAT[0]), (0, DEEP_CAT[1]), (1, DEEP_CAT[2])):
                    if (k == 0 or k == hh - 1) and dx != 0 and dx == (1 if k == 0 else -1):
                        continue
                    if 0 <= yy < H2:
                        img[yy, tx + dx] = hexc(c)
            for k in range(2):
                if ty - 1 - hh - k >= 0:
                    img[ty - 1 - hh - k, tx] = hexc(DEEP_LEAF[2])
    elif kind == "r":
        for _ in range(int(rng.integers(1, 3))):
            ang = rng.uniform(-0.15, 0.15)
            L = h * rng.uniform(0.85, 1.0)
            sx = bx + int(rng.integers(-2, 3))
            tx, ty = plant_stem(img, sx, by - 1, L, ang, DEEP_REED["stem"][1])
            plant_stem(img, sx + 1, by - 1, L * 0.55, ang, DEEP_REED["stem"][0])     # 秆下半截两格宽
            side = rng.choice([-1, 1])                          # 秆上斜出一片蓝叶，往上翘
            fy = by - 1 - L * rng.uniform(0.25, 0.45)
            plant_blade(img, sx + math.sin(ang) * (by - fy), fy, rng.uniform(9, 14), side * rng.uniform(0.45, 0.7), side * 0.35, 2.0,
                        [DEEP_REED["leaf"][0], DEEP_REED["leaf"][0], DEEP_REED["leaf"][1]])
            side = rng.choice([-1, 1])                          # 穗：一小撮，往一边垂
            for _k in range(int(rng.integers(2, 4))):
                plant_blade(img, tx, ty, rng.uniform(3, 6), side * rng.uniform(1.7, 2.3), side * 0.3, 2.0, DEEP_REED["plume"])
    elif kind == "n":                                       # 第十七版：镜头前的一大丛香蒲和芦苇
        for k in range(int(rng.integers(8, 12))):              # 细长的叶，一根根往上收尖，有的折下来垂着
            ang = rng.uniform(-0.5, 0.5)
            tones = NEAR_LEAF[int(rng.integers(0, 2))]
            fold = (rng.uniform(0.68, 0.85), math.copysign(rng.uniform(0.9, 1.4), ang)) if rng.random() < 0.4 else None
            plant_blade(img, bx + ang * 12 + rng.uniform(-6, 6), by, h * rng.uniform(0.55, 1.0), ang,
                        math.copysign(rng.uniform(0.1, 0.35), ang), rng.uniform(5.0, 7.0), tones, fold=fold)
        for k in range(int(rng.integers(2, 4))):               # 香蒲秆：顶上一根暖棕的蒲棒
            ang = rng.uniform(-0.18, 0.18)
            L = h * rng.uniform(0.75, 1.0)
            sx = bx + rng.uniform(-14, 14)
            tx, ty = plant_blade(img, sx, by, L, ang, ang * 0.3, 3.0, NEAR_LEAF[0])
            hh, hw = int(rng.integers(13, 18)), 5
            cx0, cy0 = int(round(tx)), int(round(ty))
            for j in range(hh):
                yy = cy0 + 2 - j
                inset = 1 if j in (0, hh - 1) else 0
                for dx in range(-hw // 2 + inset, hw // 2 + 1 - inset):
                    if 0 <= yy < H2 and 0 <= cx0 + dx < W2:
                        img[yy, cx0 + dx] = hexc(DEEP_CAT[0] if dx < -1 + inset else DEEP_CAT[2] if dx > 0 else DEEP_CAT[1])
            for j in range(4):                                  # 蒲棒顶上冒出来的一小截秆
                yy = cy0 + 2 - hh - j
                if 0 <= yy < H2:
                    img[yy, cx0] = hexc(NEAR_LEAF[0][1])
        for k in range(int(rng.integers(1, 3))):               # 芦苇秆：秆上斜出一片叶，顶上一撮穗往一边垂
            ang = rng.uniform(-0.25, 0.25)
            L = h * rng.uniform(0.85, 1.05)
            sx = bx + rng.uniform(-16, 16)
            tx, ty = plant_blade(img, sx, by, L, ang, ang * 0.4, 3.0, NEAR_REED_STEM)
            side = rng.choice([-1, 1])
            fy = by - L * rng.uniform(0.35, 0.55)
            plant_blade(img, sx + math.sin(ang) * (by - fy), fy, L * rng.uniform(0.3, 0.45), side * rng.uniform(0.5, 0.8),
                        side * 0.6, 4.0, NEAR_LEAF[1], fold=(0.6, side * 1.2))
            side = rng.choice([-1, 1])
            for _j in range(int(rng.integers(6, 10))):
                plant_blade(img, tx + rng.uniform(-1, 1), ty + rng.uniform(0, 4), rng.uniform(12, 20), side * rng.uniform(1.1, 2.4),
                            side * 0.5, 4.0, DEEP_REED["plume"])
    return img, bx, by


def fill_slits(img):
    """左右都是不透明、自己透明的一像素横缝 → 用右边那格的颜色填上"""
    a = img[..., 3] > 0
    ys, xs = np.nonzero(~a[:, 1:-1] & a[:, :-2] & a[:, 2:])
    for y, x in zip(ys, xs + 1):
        img[y, x] = img[y, x + 1]


def deep_variants():
    """g3 / g4 的种类，各 31 个角度一帧（同 grass_frames）。自己的随机数，别的草一格不动"""
    rng = np.random.default_rng(1616)
    spec = [  # 名字前缀, 种类, 高, 几种
        ("dp_s", "s", (10, 15), 3), ("dp_m", "m", (16, 22), 3), ("dp_f", "f", (12, 18), 3),
        ("dp_c", "c", (24, 32), 3), ("dp_r", "r", (28, 40), 3), ("dp_t", "t", (38, 48), 2),
        ("near_n", "n", (88, 112), 3),
    ]
    out = {}
    for pre, k, hr, n in spec:
        for i in range(n):
            h = int(rng.integers(*hr))
            base, bx, by = deep_plant(k, h, rng)
            wet = k not in ("n", "t")                          # 长斜叶不画倒影（倒影会在水里交叉成一个叉）
            frames = grass_frames(base, bx, by, wet, 226)
            if k == "n":                                    # 大丛弯过去时两片叶时贴时不贴，中间一道一像素的缝会断成点线：贴上
                for fr in frames:
                    fill_slits(fr[0])
            out[f"{pre}{i}"] = {"row": "g", "kind": "near" if k == "n" else "deep", "size": k, "h": h, "rest": 0.0,
                                "frames": frames}
    return out


def draw_water_layer(w, h, y0, rng, period=960):
    """一条水（tile）：每行按 water_c(y0 + 行) 取色（和晨脚下的水同一套），一道道两头尖的长波纹把相邻两档互相掺"""
    img = blank(w, h)
    wob = fbm(h, w, 90, 20, rng, period=period) * 2.5
    for y in range(h):
        for x in range(w):
            img[y, x] = hexc(water_c(y0 + y + wob[y, x]))
    for _ in range(int(w * h / 90)):
        x0 = int(rng.integers(0, w))
        y = int(rng.integers(1, h - 1))
        k = POOL.index(water_c(y0 + y))
        k2 = int(np.clip(k + rng.choice([-1, 1]), 0, len(POOL) - 1))
        L = int(rng.integers(8, 30))
        for i in range(L):
            img[y, (x0 + i) % w] = hexc(POOL[k2])
    return img


def islet(img, cx, base_y, width, rng, haze, fam_pool, reflect=True, rb=None):
    """一个小洲：一条矮矮的湿地（一两行，边是弯的）+ 上面几团静止的草（从后往前，有高有矮）+ 水里的倒影（两档）+ 根上一道湿的暗边"""
    el = blank(img.shape[1], img.shape[0])
    n = max(2, int(width / 18) + int(rng.integers(0, 3)))
    for k in range(n):
        u = (k + 0.5) / n * 2 - 1
        x = cx + u * width * 0.45 + rng.uniform(-4, 4)
        hh = (1 - 0.5 * u * u) * rng.uniform(0.6, 1.0)
        fam = fam_pool[int(rng.integers(0, len(fam_pool)))]
        w = int(width / n * rng.uniform(1.4, 2.0)) + 6
        h = int(max(5, (8 + width * 0.14) * hh))
        base, bx, by = grass_base(w, h, GRASS_T[fam], rng, 0.4 if h > 12 else 0.0, sep=haze < 0.3)
        y0 = int(base_y + rng.integers(-1, 2)) - by
        x0 = int(x) - bx
        m = base[..., 3] > 0
        for (yy, xx) in zip(*np.nonzero(m)):
            Y, X = y0 + yy, x0 + xx
            if 0 <= Y < el.shape[0] and 0 <= X < el.shape[1]:
                el[Y, X] = base[yy, xx]
    haze_img(el, haze)
    m = el[..., 3] > 0
    if reflect:
        lum = el[..., 0].astype(float) * 0.3 + el[..., 1] * 0.55 + el[..., 2] * 0.15
        midv = np.median(lum[m]) if m.any() else 0
        hgt = max(1, base_y - int(np.nonzero(m.any(1))[0].min())) if m.any() else 1
        for (yy, xx) in zip(*np.nonzero(m)):
            ry = 2 * base_y - yy + 1
            ry = base_y + 1 + int((ry - base_y - 1) * 0.6)
            if 0 <= ry < img.shape[0] and img[ry, xx, 3] and not m[ry, xx]:
                wc = img[ry, xx].astype(float)
                t = hexc(REFL_TONES[0] if (ry - base_y) <= hgt * 0.27 else REFL_TONES[1]).astype(float)
                img[ry, xx, :3] = np.round(t[:3] * 0.5 + wc[:3] * 0.5).astype(np.uint8)
        cols = np.nonzero(m[min(base_y, img.shape[0] - 1)])[0]
        for x in cols:
            for d, c in ((1, "#8cc0a6"), (2, SURF[0])):
                if 0 <= base_y + d < img.shape[0] and not m[base_y + d, x]:
                    img[base_y + d, x] = mix(hexc(c), hexc(HAZE), haze)
    img[m] = el[m]
    if rb is not None:
        rb[m] = base_y


def draw_mid6():
    """中景（scroll 0.4，tile 960）：远岸的一条（上面几行）+ 一片水 + 几个小而淡的小洲"""
    rng = np.random.default_rng(53)
    w, h, y0 = 960, 46, 148
    img = draw_water_layer(w, h, y0, rng)
    bank = 4 + knots(w, 70, rng, 1.6, period=960)
    n = fbm(h, w, 64, 6, rng, period=960)
    for x in range(w):
        t = int(round(bank[x]))
        for y in range(0, t + 1):
            img[y, x] = hexc(RAMP[3] if n[y, x] > 0 else RAMP[2])
        img[t + 1, x] = hexc(GREEN[3])
    for cx in np.linspace(40, 920, 7) + rng.uniform(-30, 30, 7):
        islet(img, int(cx), int(rng.integers(16, 30)), int(rng.integers(24, 50)), rng, 0.5, ["G", "YG", "Y"])
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    de_alt(img, passes=4)
    speck_fix(img)
    corner_fix(img, max_iter=10)
    de_alt(img, passes=2)
    corner_fix(img, max_iter=10)
    speck_fix(img)
    edge_diag_fill(img)
    return img


def draw_isles():
    """岛层（scroll 0.68，tile 960）：一片水 + 一排中等的小洲（比中景大、比 main 的淡一点），在晨这一层的水后面"""
    rng = np.random.default_rng(57)
    w, h, y0 = 960, 50, 160
    img = draw_water_layer(w, h, y0, rng)
    img[:4] = 0                                     # 最上面几行透明，透出中景
    x = 20.0
    while x < 940:
        islet(img, int(x), int(rng.integers(18, 32)), int(rng.integers(40, 90)), rng, 0.22, ["G", "YG", "M", "G"])
        x += rng.uniform(110, 190)
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    de_alt(img)
    edge_diag_fill(img)
    return img


# ================================================================ 第七版：按植物分的大片（作者：「一大片草，一大片芦苇，一大片另一种植物……这才是湿地」）
# 从左到右一大片接一大片（ZONES），每片又密又连成一体，片和片的交界互相伸进去一点（ZONE_BLEND），不留大块空水。
# 每一层（中景 mid、岛层 isles、晨这一层 main）都是这样成片的，越远越淡越小。水从植物带中间（后排和路之间）和前面露出来。
# 第八版（作者：「太过于杂乱」）：晨这一层只留三种，每片更大、更整：绵草、芦苇海、开小花的水草。小镇那段也是湿地（小镇定在粉色云层上了）
ZONES = [("grass", -80, 600), ("reeds", 600, 1120), ("flw", 1120, 1520), ("reeds", 1520, 1800), ("grass", 1800, 2000)]
ZONE_BLEND = 30
ZONE_FAM = {"dry": ["Y"], "grass": ["G", "YG"], "reeds": ["G"], "cat": ["G", "M"], "lily": ["M", "G"], "flw": ["YG"]}


def zone_at(x):
    for z, a, b in ZONES:
        if a <= x < b:
            return z
    return None


def static_reeds(el, x0, x1, base_fn, hmin, hmax, rng, pal="r0"):
    """一片静止的芦苇（后排、远处）：一根根挨得很密，但长短、斜度、弯法都不一样（不平行、不等距）；穗是往一边垂的一小蓬软团。
    根会被前面压上去的草团盖住，这里只管秆和穗。"""
    P = REED_PAL[pal]
    h_, w_ = el.shape[:2]
    x = float(x0)
    n_ = fbm(1, max(2, x1 - x0 + 2), 40, 2, rng)[0]
    while x < x1:
        xi = int(x)
        env = 0.75 + 0.25 * n_[min(len(n_) - 1, max(0, xi - x0))]
        L = rng.uniform(hmin, hmax) * env
        lean = rng.uniform(-0.18, 0.28)
        curve = rng.uniform(-0.25, 0.25)
        b = base_fn(xi)
        pts = []
        for t in np.linspace(0, 1, int(L * 2) + 4):
            a = lean + curve * t * t
            pts.append((x + math.sin(a) * L * t, b - math.cos(a) * L * t))
        stem = path4(pts)
        for j, (sx, sy) in enumerate(stem):
            if 0 <= sx < w_ and 0 <= sy < h_:
                el[sy, sx] = hexc(P["stem"][0] if j < len(stem) * 0.4 else P["stem"][1] if j < len(stem) * 0.8 else P["stem"][2])
        # 穗：从顶上往点头的方向垂下去的一小蓬（几个圆章，上面受光）
        tx, ty = pts[-1]
        nod = lean + curve + rng.uniform(0.6, 1.2)
        pl = rng.uniform(6, 10) * (L / hmax) ** 0.5 + 2
        for k in range(8):
            t = k / 7
            cx = tx + math.sin(nod) * pl * t
            cy = ty - math.cos(nod) * pl * t * 0.6 + pl * 0.35 * t * t
            r = 1.0 + 1.6 * math.sin(math.pi * min(1.0, 0.15 + t * 0.9))
            for yy in range(int(cy - r - 1), int(cy + r + 2)):
                for xx in range(int(cx - r - 1), int(cx + r + 2)):
                    if 0 <= xx < w_ and 0 <= yy < h_ and (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                        el[yy, xx] = hexc(P["plume"][2] if yy < cy - r * 0.3 else P["plume"][0] if yy > cy + r * 0.4 else P["plume"][1])
        x += rng.uniform(1.6, 3.6)


def paste(el, base, bx, by, x, y):
    m = base[..., 3] > 0
    for (yy, xx) in zip(*np.nonzero(m)):
        Y, X = y - by + yy, x - bx + xx
        if 0 <= Y < el.shape[0] and 0 <= X < el.shape[1]:
            el[Y, X] = base[yy, xx]


def band(img, x0, x1, base_fn, kind, scale, rng, haze=0.0, period=None, rb=None, sep=True):
    """一片植物带（kind = grass / reeds / cat / lily / flw / dry），从 x0 到 x1 连成一整片，根在 base_fn(x) 那一行，水里的带倒影和湿边。
    scale：高矮的倍数（远处的小）。period：tile 层（左右无缝）的宽。"""
    h_, w_ = img.shape[:2]
    el = blank(w_, h_)
    fams = ZONE_FAM[kind]

    def wrap(x):
        return int(x) % w_ if period else int(x)

    def clump(x, hgt, wid, style="grass", tall=0.3, fam=None):
        fam = fam or fams[int(rng.integers(0, len(fams)))]
        base, bx, by = grass_base(max(10, int(wid)), max(5, int(hgt)), GRASS_T[fam], rng, tall, sep=sep, style=style, fringe=0.3)
        y = int(base_fn(wrap(x))) + int(rng.integers(-1, 2))
        xx = int(x)
        if period:
            for off in (-w_, 0, w_):
                paste(el, base, bx, by, xx + off, y)
        else:
            paste(el, base, bx, by, xx, y)

    if kind == "reeds":
        if period:
            for off in (-w_, 0, w_):
                static_reeds(el, x0 + off, x1 + off, lambda x: base_fn(wrap(x)) - 2, 40 * scale, 66 * scale, rng)
        else:
            static_reeds(el, x0, x1, lambda x: base_fn(wrap(x)) - 2, 40 * scale, 66 * scale, rng)
        x = x0
        while x < x1:                                       # 前面压一排草团，盖住秆的下半截
            clump(x, rng.uniform(14, 24) * scale, rng.uniform(26, 44) * max(0.6, scale), tall=0.2)
            x += rng.uniform(10, 18) * max(0.6, scale)
    elif kind == "lily":
        x = x0
        while x < x1:                                       # 后排一溜矮苔草
            clump(x, rng.uniform(7, 12) * scale, rng.uniform(18, 30) * max(0.6, scale), tall=0.0, fam="M")
            x += rng.uniform(14, 26) * max(0.6, scale)
    else:
        style = {"cat": "cat", "flw": "flw"}.get(kind, "grass")
        hr = {"grass": (20, 30), "dry": (16, 26), "cat": (30, 46), "flw": (16, 24)}[kind]
        x = x0
        while x < x1:                                       # 大团、挨得紧：远看一整块，起伏靠大的明暗
            clump(x, rng.uniform(*hr) * scale, rng.uniform(44, 76) * max(0.6, scale), style=style, tall=0.15)
            x += rng.uniform(16, 26) * max(0.6, scale)
    haze_img(el, haze)
    m = el[..., 3] > 0
    # 倒影（水上才画）：按离根多远分两档，压扁 0.6；根下一道湿的暗边、一道亮边
    if m.any():
        tops = {}
        for (yy, xx) in zip(*np.nonzero(m)):
            tops[xx] = min(tops.get(xx, 9999), yy)
        for (yy, xx) in zip(*np.nonzero(m)):
            b = int(base_fn(xx if not period else xx % w_))
            if yy > b:
                continue
            hgt = max(1, b - tops[xx])
            ry = b + 1 + int((b - yy) * 0.6)
            if 0 <= ry < h_ and img[ry, xx, 3] and not m[ry, xx] and tuple(img[ry, xx]) in POOL_SET:
                wc = img[ry, xx].astype(float)
                t = hexc(REFL_TONES[0] if (ry - b) <= hgt * 0.27 else REFL_TONES[1]).astype(float)
                img[ry, xx, :3] = np.round(t[:3] * 0.5 + wc[:3] * 0.5).astype(np.uint8)
        for xx in range(w_):
            col = np.nonzero(m[:, xx])[0]
            if not len(col):
                continue
            b = int(col.max())
            for d, c in ((1, "#8cc0a6"),):                 # 根下一道湿的暗边（亮边那一道会被倒影切碎成一截一截，不画）
                if 0 <= b + d < h_ and not m[b + d, xx] and tuple(img[b + d, xx]) in POOL_SET:
                    img[b + d, xx] = mix(hexc(c), hexc(HAZE), haze)
    img[m] = el[m]
    if rb is not None:
        rb[m] = 0
    # 睡莲：贴着水的一片浮叶（扁椭圆，亮边在上、下沿深一档），零星几朵小白花（3×2，中间淡黄）
    if kind == "lily":
        for _ in range(int((x1 - x0) * 0.9)):
            x = rng.uniform(x0, x1)
            y = base_fn(wrap(x)) + rng.uniform(3, 14) * scale
            rx, ry = rng.uniform(3.5, 7.5) * max(0.6, scale), rng.uniform(1.2, 2.4) * max(0.6, scale)
            pad_c = [GREEN[0], GREEN[1], GREEN[3]]
            for yy in range(int(y - ry - 1), int(y + ry + 2)):
                for xx in range(int(x - rx - 1), int(x + rx + 2)):
                    X = xx % w_ if period else xx
                    if 0 <= X < w_ and 0 <= yy < h_ and ((xx - x) / rx) ** 2 + ((yy - y) / ry) ** 2 <= 1 and tuple(img[yy, X]) in POOL_SET | PAD_SET:
                        img[yy, X] = mix(hexc(pad_c[2] if yy < y - ry * 0.3 else pad_c[1] if yy <= y + ry * 0.5 else pad_c[0]), hexc(HAZE), haze)
        for _ in range(int((x1 - x0) / 22)):
            x = int(rng.uniform(x0, x1))
            y = int(base_fn(wrap(x)) + rng.uniform(4, 12) * scale)
            for (dx, dy, c) in ((-1, 0, GLINT[0]), (0, 0, RAMP[3]), (1, 0, GLINT[0]), (0, -1, GLINT[0])):
                X = (x + dx) % w_ if period else x + dx
                if 0 <= X < w_ and 0 <= y + dy < h_:
                    img[y + dy, X] = mix(hexc(c), hexc(HAZE), haze)


def gapped_bands(img, base_fn, scale, rng, haze, period, kinds, wmin, wmax, gmin, gmax, sep=True):
    """tile 层（中景、岛层）：一片植物带接一段开阔的水（gmin–gmax 宽），再一片……（kinds 轮着来）"""
    x = rng.uniform(0, 30)
    k = int(rng.integers(0, len(kinds)))
    while x < period - wmin * 0.6:
        w = min(rng.uniform(wmin, wmax), period - 20 - x)
        if w < 30:
            break
        band(img, int(x), int(x + w), base_fn, kinds[k % len(kinds)], scale, rng, haze, period, sep=sep)
        x += w + rng.uniform(gmin, gmax)
        k += 1


def clean_layer(img):
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    de_alt(img, passes=4)
    speck_fix(img)
    corner_fix(img, max_iter=10)
    de_alt(img, passes=2)
    corner_fix(img, max_iter=10)
    speck_fix(img)
    edge_diag_fill(img)


MID_Y, MID_H, MID_WT, MID_B = 134, 50, 14, 21        # mid：屏幕 y 134，水从第 14 行（y 148），根在第 21 行（y 155）
ISL_Y, ISL_H, ISL_WT, ISL_B = 146, 64, 16, 25        # isles：屏幕 y 146，水从第 16 行（y 162），根在第 25 行（y 171）


def draw_mid10():
    """中景（scroll 0.35，tile 960）：一片映天的水，上面几片小洲（草 / 芦苇 / 开花草），片和片之间空出水"""
    rng = np.random.default_rng(1053)
    img = bg_water(960, MID_H, MID_Y, MID_WT, rng)
    bl = MID_B + knots(960, 90, rng, 1.0, period=960)
    gapped_bands(img, lambda x: int(round(bl[int(x) % 960])), 0.2, rng, 0.42, 960, ["grass", "reeds", "flw"], 60, 150, 34, 100, sep=False)
    clean_layer(img)
    return img


def draw_isles10():
    """岛层（scroll 0.62，tile 960）：同上，小洲大一点、清楚一点、空当宽一点"""
    rng = np.random.default_rng(1057)
    img = bg_water(960, ISL_H, ISL_Y, ISL_WT, rng)
    bl = ISL_B + knots(960, 110, rng, 1.2, period=960)
    gapped_bands(img, lambda x: int(round(bl[int(x) % 960])), 0.3, rng, 0.2, 960, ["reeds", "grass", "flw"], 80, 190, 60, 150)
    clean_layer(img)
    return img


def draw_main6():
    """晨这一层：一整片浅水（按 y 取色 + 波纹 + 透出水底的沙）；陆地只有 LAND 那两段（软的黄草地，靠水那边慢慢变绿，岸斜着收进水里）；
    水里几个静止的小洲（路后面）、浮叶、几丛水草。返回 (图, 地面, 水的上沿, 这一列的路在不在水里, 小洲列表, 涟漪点, 飞虫点)。"""
    rng = np.random.default_rng(67)
    img = blank(W, H)
    gy = np.array([ground(x) for x in range(W)])
    la = np.array([land_amt(x) for x in range(W)])
    # 每一列：陆地占到哪一行（陆地在上、水在下；岸斜着从后往前收）
    shore = knots(W, 70, rng, 14.0) + knots(W, 19, rng, 3.0)       # 岸线弯弯曲曲（大弯 + 小弯）
    land_bot = np.round(MAIN_TOP + (H + 4 - MAIN_TOP) * np.sin(la * math.pi / 2) ** 2 + shore * (la > 0.02) * (la < 0.98)).astype(int)
    for _ in range(300):
        ch = False
        for x in range(1, W):
            if abs(land_bot[x] - land_bot[x - 1]) > 2:
                m = min(land_bot[x], land_bot[x - 1]) + 2
                if land_bot[x] > m:
                    land_bot[x] = m
                    ch = True
                if land_bot[x - 1] > m:
                    land_bot[x - 1] = m
                    ch = True
        if not ch:
            break
    water_m = np.zeros((H, W), bool)
    sand = fbm(H, W, 26, 7, rng)
    wob = fbm(H, W, 90, 30, rng) * 3.0
    base = fbm(H, W, 150, 26, rng)
    for x in range(W):
        lb = int(np.clip(land_bot[x], MAIN_TOP, H))
        for y in range(MAIN_TOP, lb):
            k = 2.4 + base[y, x] * 2.6
            img[y, x] = hexc(RAMP[int(np.clip(round(k), 1, 4))])
        for y in range(lb, H):
            c = water_c(y + wob[y, x])
            if y > 214 and sand[y, x] > 0.2:
                c = POOL_SAND[POOL.index(c)]
            img[y, x] = hexc(c)
            water_m[y, x] = True
        if MAIN_TOP < lb < H:
            img[lb, x] = hexc(POOL_EDGE)
    wtop = np.array([int(np.argmax(water_m[:, x])) if water_m[:, x].any() else H + 2 for x in range(W)])
    ws = np.array([1.0 if water_m[min(H - 1, gy[x] + 1), x] else 0.0 for x in range(W)])
    # 陆地上几道扁扁的软草团（一道道起伏，左上一道亮边），不是一整块平涂
    for rb in np.arange(MAIN_TOP + 8, H + 10, 13):
        x = -40.0
        while x < W + 40:
            w = rng.uniform(120, 300)
            h = rng.uniform(3.0, 6.0)
            cx = x + w / 2
            cols = np.arange(max(0, int(cx - w / 2)), min(W, int(cx + w / 2) + 1))
            if len(cols):
                u = (cols - cx) / (w / 2)
                ytop = rb + rng.uniform(-2, 2) - h * np.clip(1 - u * u, 0, 1) ** 1.6
                k = int(rng.integers(1, 4))
                for i, xx in enumerate(cols):
                    t = int(round(ytop[i]))
                    for yy in range(max(MAIN_TOP, t), min(H, int(rb) + 3)):
                        if not water_m[yy, xx] and img[yy, xx, 3]:
                            img[yy, xx] = hexc(RAMP[min(4, k + 2)] if yy - ytop[i] < 1.6 and u[i] < 0.3 else RAMP[k])
            x += w * rng.uniform(0.5, 0.85)
    # 陆地靠水那一带变绿（和第五版一样：GREEN / YGREEN）
    near_w = np.zeros((H, W), int) + 99
    cur = water_m.copy()
    for dd in range(1, 23):
        nxt = cur.copy()
        nxt[1:, :] |= cur[:-1, :]
        nxt[:-1, :] |= cur[1:, :]
        nxt[:, 1:] |= cur[:, :-1]
        nxt[:, :-1] |= cur[:, 1:]
        near_w[nxt & ~cur] = dd
        cur = nxt
    gn = fbm(H, W, 22, 8, rng) * 6.0
    pal = [tuple(hexc(c)) for c in RAMP]
    for (yy, xx) in zip(*np.nonzero((img[..., 3] > 0) & ~water_m & (near_w < 30))):
        here = tuple(img[yy, xx])
        if here in pal:
            d = near_w[yy, xx] + gn[yy, xx]
            k = pal.index(here)
            if d < 9:
                img[yy, xx] = hexc(GREEN[k])
            elif d < 20:
                img[yy, xx] = hexc(YGREEN[k])
    # 水面波纹
    for _ in range(1800):
        x0 = int(rng.integers(0, W))
        y = int(rng.integers(MAIN_TOP + 2, H))
        if not water_m[y, x0]:
            continue
        k = POOL.index(water_c(y))
        k2 = int(np.clip(k + rng.choice([-2, -1, 1, 1, 2]), 0, len(POOL) - 1))
        for i in range(int(rng.integers(6, 26))):
            if x0 + i < W and water_m[y, x0 + i] and y > wtop[x0 + i] + 1:
                img[y, x0 + i] = hexc(POOL[k2])
    # 陆地靠水的那一圈：一团团草（嫩绿 / 黄绿 / 薄荷），坐在水边，带倒影 —— 岸不是一刀切的
    for x in range(4, W - 4, 1):
        if 0.03 < la[x] < 0.98 and wtop[x] < H - 2 and rng.random() < 0.2:
            islet(img, x, int(wtop[x]) + 1, int(rng.integers(18, 34)), rng, 0.0, ["G", "YG", "G", "M"])
    # 后排：按植物分的大片（ZONES），一片接一片连成一整条，根在 ~y 203（和路之间留一条水，映着它们的倒影）
    isles = []
    bl = 203 + knots(W, 80, rng, 2.5)
    for z, a, b in ZONES:
        band(img, max(-40, a - ZONE_BLEND), min(W + 40, b + ZONE_BLEND), lambda x: int(bl[int(np.clip(x, 0, W - 1))]), z, 1.0, rng)
    # 路前面：草和开花草那两片在画面下沿再压一溜矮的（顶在 y 250 以下，不挡晨），睡莲那片在路前的水面上再铺一片浮叶
    # （第八版：路前面不再压一溜矮带，水面要安静）
    # 浮叶、水里的水草（矮的，路前面压到脚底以下）
    wpts = np.argwhere(water_m)
    PAD = (GREEN[0], GREEN[1], GREEN[3])
    for _ in range(14):
        y, x = wpts[int(rng.integers(0, len(wpts)))]
        if y < 210 or abs(y - gy[x]) < 6:
            continue
        rx, ry = rng.uniform(3.0, 5.5), rng.uniform(1.0, 1.6)
        for yy in range(int(y - ry - 1), int(y + ry + 2)):
            for xx in range(int(x - rx - 1), int(x + rx + 2)):
                if 0 <= xx < W and 0 <= yy < H and ((xx - x) / rx) ** 2 + ((yy - y) / ry) ** 2 <= 1 and water_m[yy, xx]:
                    img[yy, xx] = hexc(PAD[2] if yy < y - 0.3 else PAD[1] if yy <= y + 0.5 else PAD[0])
    corner_fix(img)
    speck_fix(img)
    corner_fix(img)
    de_alt(img, passes=4)
    speck_fix(img)
    corner_fix(img, max_iter=10)
    de_alt(img, passes=2)
    corner_fix(img, max_iter=10)
    speck_fix(img)
    edge_diag_fill(img)
    rip = []
    for _ in range(800):
        y, x = wpts[int(rng.integers(0, len(wpts)))]
        if y > 212 and y < H - 3 and abs(y - gy[x]) > 4:
            rip.append([int(x), int(y)])
        if len(rip) >= 60:
            break
    motes = [[int(x), int(gy[x] - rng.uniform(8, 50))] for x in rng.integers(10, W - 10, 80)]
    return img, gy, wtop, ws, isles, rip, motes


def place6(vs, grass, gy, ws, isles):
    """会动的东西放哪（第七版：按植物带）：
    g1 = 路后面，按这一片是什么植物密排（草 / 香蒲 / 开花草 / 苔草 / 陆地上的干草），连成一片；
    r1 = 芦苇那一片：密密的一大片芦苇（长短、斜度不一，不等距），穗连成穗海，g1 的矮草团压在它们根前面；
    g2 / r2 = 路前面零星几团、几簇（矮，顶不超过晨的脚底）；gf = 前景（scroll 1.3）画面下沿几团大的。小镇那段都不放。"""
    rng = np.random.default_rng(97)
    out = {k: [] for k in ROW_Z}

    def town(x):
        return False                                # 第八版：小镇不在这张图上了

    def pick(kind, size=None):
        c = [n for n, v in grass.items() if v["kind"] == kind and (size is None or v["size"] in size)]
        return str(rng.choice(c))

    def add(row, x, y, name, lean=0.0):
        out[row].append([int(x), int(y), name, round(float(rng.uniform(0, 6.28)), 2), round(float(lean), 1)])

    # g1 / r1：路后面，按植物带密排（连成一片，不留大空当）
    def kinds_of(z):
        return {"dry": ("dry", None), "grass": ("wet", "lm"), "flw": ("flw", None), "reeds": ("wet", "ms")}[z]
    x = 6.0
    while x < W - 6:
        xi = int(x)
        z = zone_at(xi)
        if z is None or town(xi):
            x += 10
            continue
        k, size = kinds_of(z)
        add("g1", xi, gy[xi] - int(rng.integers(2, 7)), pick(k, size))
        if z == "reeds":
            x += rng.uniform(14, 24)
        elif z == "lily":
            x += rng.uniform(22, 38)
        else:
            x += rng.uniform(8, 15)
    # 芦苇那一片：一大片密密的芦苇（穗连成一片起伏的穗海），每根长短、斜度不一，不等距
    rn = sorted([n for n in vs if vs[n]["row"] == "r1"], key=lambda n: vs[n]["L"])
    for z, a, b in ZONES:
        if z != "reeds":
            continue
        x = a - ZONE_BLEND + rng.uniform(0, 3)
        env = knots(int(b - a + 2 * ZONE_BLEND) + 2, 60, rng, 1.0)
        while x < b + ZONE_BLEND:
            xi = int(x)
            fade = min(1.0, (x - (a - ZONE_BLEND)) / (2 * ZONE_BLEND), ((b + ZONE_BLEND) - x) / (2 * ZONE_BLEND))
            if rng.random() < fade:
                e = 0.5 + 0.5 * env[int(x - (a - ZONE_BLEND))]
                kk = int(np.clip(round(e * (len(rn) - 1) + rng.uniform(-1.5, 1.5)), 0, len(rn) - 1))
                add("r1", xi, gy[xi] - int(rng.integers(5, 11)), rn[kk], rng.uniform(-10, 12))
            x += rng.uniform(3.0, 5.6)
    # g2 / r2：路前面零星（矮，顶不超过晨的脚底）
    x = 30.0
    while x < W - 30:
        xi = int(x)
        z = zone_at(xi)
        if z in ("grass", "flw") and not town(xi):
            y = int(gy[xi] + rng.integers(18, 34))
            name = pick({"grass": "wet", "flw": "flw"}[z], "ms" if z != "flw" else None)
            if y - grass[name]["h"] - 2 > gy[xi]:
                add("g2", xi, y, name)
        x += rng.uniform(110, 220)
    # gf：前景（层坐标，宽 480 + 1440 × 1.3）
    fw = 480 + (W - 480) * 1.3
    fx = 60.0
    while fx < fw - 40:
        mx = (fx - 240) / 1.3 + 240
        if not town(mx):
            add("gf", fx, int(rng.integers(292, 302)), pick("front"))
        fx += rng.uniform(260, 420)
    # 芦苇：零星几簇
    rnames = {r: sorted([n for n in vs if vs[n]["row"] == r], key=lambda n: vs[n]["L"]) for r in ("r0", "r1", "r2")}
    centers = []                                    # 第八版：芦苇只在芦苇那两片
    for cx in centers:
        if town(cx):
            continue
        back = cx in SPOTS or rng.random() < 0.6
        row = "r1" if back else "r2"
        if not back and ws[cx] < 0.5:
            row = "r1"
        for k in range(int(rng.integers(3, 7))):
            x = int(cx + rng.normal(0, 6))
            if not (4 <= x < W - 4):
                continue
            name = str(rng.choice(rnames[row]))
            y = gy[x] - int(rng.integers(4, 9)) if row == "r1" else gy[x] + int(rng.integers(20, 34))
            add(row, x, y, name, rng.uniform(-9, 11))
    for (cx, by, wdt) in isles:
        if rng.random() < 0.6:
            for k in range(int(rng.integers(2, 5))):
                add("r0", cx + rng.normal(0, 8), by + int(rng.integers(0, 3)), str(rng.choice(rnames["r0"])), rng.uniform(-8, 10))
    out["g3"] = place_deep(grass, gy)
    out["g1"] = [e for e in out["g1"] if not (YARD_FLAT[0] <= e[0] <= YARD_FLAT[1])]   # 被压倒的那一片（v18）
    out["g4"] = place_near(grass)
    for r in out:
        out[r].sort(key=lambda t: t[0])
    return out


# g3：晨脚前的水草，根在晨脚底前面 3–7 行（水里，带湿边和倒影）。第十六版大幅变稀：一簇 1–3 株，簇和簇之间空 80–190 像素，
# 露出水面和后面的草；大多是矮的（顶在晨的小腿到膝盖），香蒲 / 芦苇秆细，挡不住人；隔一大段才有一株很长的斜叶从晨身前划过去。
# 说话的地方（markers 左右 44）只放矮莎草和小花；芦苇那两片前面不放香蒲和芦苇秆（颜色和后面的芦苇一样，会糊）。z 24：在脚踝的水面（21）和水花（22）前面、低雾（25）后面；被晨推开、再弹回来。
G4_SCROLL = 1.25
G4_CLEAR = (110, 370)                                   # 说话的那几个镜头位置，镜头前的大叶不进屏幕这一段


def place_deep(grass, gy):
    rng = np.random.default_rng(1616)
    by = {}
    for n, v in grass.items():
        if v["kind"] == "deep":
            by.setdefault(v["size"], []).append(n)
    by = {k: sorted(v) for k, v in by.items()}
    marks = room_json_markers()
    out = []

    def add(x, k):
        xi = int(np.clip(x, 4, W - 5))
        out.append([xi, int(gy[xi] + rng.integers(3, 8)), str(rng.choice(by[k])), round(float(rng.uniform(0, 6.28)), 2),
                    round(float(rng.uniform(-5, 5)), 1)])
    x = rng.uniform(20, 60)
    while x < W - 20:
        near = any(abs(x - m) < 44 for m in marks)
        n = int(rng.choice([1, 2, 2, 3]))
        if near:
            kinds = list(rng.choice(["s", "f"], size=min(n, 2), replace=False))
        elif zone_at(int(x)) == "reeds":                 # 芦苇那两片前面：香蒲的棕黄、芦苇秆会和后面的芦苇糊在一起，只放冷绿的莎草和小花
            kinds = list(rng.choice(["s", "m", "f"], size=n, replace=False, p=[0.4, 0.3, 0.3]))
        else:
            kinds = list(rng.choice(["s", "m", "f", "c", "r"], size=n, replace=False, p=[0.2, 0.15, 0.15, 0.25, 0.25]))
        for j, k in enumerate(kinds):                    # 一簇里每株是不同的植物，不重复同一块印章
            add(x + j * rng.uniform(5, 11), str(k))
        x += rng.uniform(80, 190)
    x = rng.uniform(150, 300)                           # 很长的斜叶：隔一大段一株，不在说话的地方
    while x < W - 40:
        if not any(abs(x - m) < 60 for m in marks):
            add(x, "t")
        x += rng.uniform(280, 420)
    return out


def place_near(grass):
    """g4：镜头前的大叶（层坐标，宽 480 + 1440 × G4_SCROLL），根在画面下沿外；说话的镜头位置屏幕中间空开"""
    rng = np.random.default_rng(1717)
    names = sorted(n for n, v in grass.items() if v["kind"] == "near")
    cams = [min(max(m - 240, 0), W - 480) for m in room_json_markers()]
    fw = 480 + (W - 480) * G4_SCROLL
    out = []
    fx = rng.uniform(20, 80)
    while fx < fw - 20:
        for _ in range(40):
            if all(not (G4_CLEAR[0] - 40 < fx - c * G4_SCROLL < G4_CLEAR[1] + 40) for c in cams):
                break
            fx += 17
        if fx < fw - 20:
            out.append([int(fx), int(rng.integers(288, 298)), names[len(out) % len(names)], round(float(rng.uniform(0, 6.28)), 2),
                        round(float(rng.uniform(-6, 6)), 1)])
        fx += rng.uniform(200, 340)
    return out


# ---------------------------------------------------------------- room.json
def insert_prop_layers(layers):
    """中景的树（tools/reed_field_props.py 画，props/layers.json）：每层插在它跟着的那层（after）后面；z 都写明了，不挤别的层的 z"""
    p = OUT / "props" / "layers.json"
    if not p.exists():
        return layers
    out = list(layers)
    for L in json.loads(p.read_text(encoding="utf-8")):
        L = {k: v for k, v in L.items() if k != "after"} | {"_after": L.get("after", "")}
        i = next((k for k, q in enumerate(out) if q["id"] == L["_after"]), len(out) - 1)
        out.insert(i + 1, {k: v for k, v in L.items() if k != "_after"})
    return out


def prop_objects():
    """结局一、二的物件：tools/reed_field_props.py 画、写在 props/objects.json（重出 room.json 时照抄过来，不丢）"""
    p = OUT / "props" / "objects.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def room_json():
    layers = [
        {"id": "sky", "img": "sky.png", "scroll": 0.0, "y": 0},
        {"id": "streaks", "img": "streaks.png", "scroll": 0.03, "y": 10, "tile": True, "drift": -1.0},
        *[{"id": r["id"], "img": r["id"] + ".png", "scroll": r["scroll"], "y": r["y"], "tile": True} for r in RANGES],
        {"id": "far", "img": "far.png", "scroll": 0.14, "y": FAR_Y, "tile": True},
        {"id": "mid", "img": "mid.png", "scroll": 0.35, "y": MID_Y, "tile": True},
        {"id": "mid_glints", "img": "mid_glints.png", "scroll": 0.35, "y": MID_Y, "tile": True, "shader": "water",
         "shader_params": {"palette_mode": False, "speed": 0.6, "wobble": 1.0, "flicker": 0.0, "show": 0.55}},
        *[L for L in GIANT_LAYERS if "z" not in L and L["scroll"] < 0.5],
        {"id": "isles", "img": "isles.png", "scroll": 0.62, "y": ISL_Y, "tile": True},
        *[L for L in GIANT_LAYERS if "z" not in L and L["scroll"] >= 0.5],
        {"id": "bigtrees", "img": "bigtrees.png", "scroll": 1.0, "y": 0},
        {"id": "main", "img": "main.png", "scroll": 1.0, "y": 0},
        {"id": "glints", "img": "glints.png", "scroll": 1.0, "y": 0, "shader": "water",
         "shader_params": {"palette_mode": False, "speed": 0.8, "wobble": 1.0, "flicker": 0.0, "show": 0.6}},
        {"id": "ankle", "img": "ankle.png", "scroll": 1.0, "y": 0, "z": 20},
        {"id": "ankle_water", "img": "ankle_water.png", "scroll": 1.0, "y": 0, "z": 21, "alpha": 0.6},
    ]
    # 第十版：层的 z 写明，隔一个空一个（−100、−98、…），空出来的给 reed_field.gd 的远处鸟群（hills 前面）和岛层的白鹭、野鸭（isles 前面）
    layers = [dict(L) for L in layers]
    for (mid, before, sc, y, _h, a, _n, _l, _t, _w, drift, z) in MISTS:      # 第十一版的雾
        L = {"id": mid, "img": mid + ".png", "scroll": sc, "y": y, "tile": True, "alpha": a}
        if drift:
            L["drift"] = drift
        if z is not None:
            L["z"] = z
        layers.insert(next(i for i, q in enumerate(layers) if q["id"] == before), L)
    for i, L in enumerate(layers):
        L.setdefault("z", -100 + 2 * i)
    layers = insert_prop_layers(layers)
    zid = {L["id"]: L["z"] for L in layers}
    FAUNA_Z.update({"isle": zid["isles"] + 1, "flock": zid["hills"] + 1})
    return {
        "_note": ("tools/reed_field_art.py 生成，别手改（要改先改脚本）。云层星的芦苇地（第三章；结局一、结局二的 yard / east_meadow 都改成这张）。"
                  "第六版：一整片连着的浅水湿地，草丛为主、零星几簇芦苇，前后几层（远山、远岸、中景小洲 mid、岛 isles、晨这一层、前景 gf）。"
                  "会动的草丛和芦苇、惊鸟、绒毛、飞虫、涟漪、晨的倒影、晨身后压暗是 scripts/reed_field.gd，数据在 reeds.json / birds.json。"
                  "约定见 docs/river_rooms_contract.md。"),
        "_note_town": "第八版：小镇定在粉色云层上，不在这张图；以前留给小镇的 x 1110–1490 现在是普通湿地（开小花的水草那一片）。",
        "size": [W, H],
        "origin": [0, 1080],
        "env": "reeds",
        "bg": ["#9dd2f1", "#fff0a8"],
        "layers": layers,
        "ground": GROUND,
        "walk": WALK,
        "markers": {"reed_field_west": 60, "reed_field_spot1": SPOTS[0], "reed_field_water": SPOTS[1],
                    "reed_field_town": (TOWN[0] + TOWN[1]) // 2, "reed_field_spot3": SPOTS[2], "reed_field_east": 1860},
        "objects": prop_objects(),
        "portals": [],
        "ambient": [],
        "scripts": [{"script": "res://scripts/reed_field.gd", "x": 0, "y": 0, "z": -40,
                     "params": {"data": "res://art/reed_field/reeds.json", "birds": "res://art/reed_field/birds.json",
                                "spots": [[SPOTS[0], 6], [SPOTS[1], 5], [SPOTS[2], 6]],
                                "water": [list(w) for w in WATERS], "seeds": SEED_EMITTERS,
                                "ripples": RIPPLE_PTS, "motes": MOTE_PTS, "fauna": "res://art/reed_field/fauna.json",
                                "fauna_z": [FAUNA_Z.get("isle", -70), FAUNA_Z.get("flock", -90)],
                                "fg": {"img": "res://art/reed_field/fg.png", "y": FG_Y, "scroll": FG_SCROLL, "z": 116}}}],
    }


# ---------------------------------------------------------------- 预览：按 room.json 叠一屏 + 芦苇 + 晨（含倒影、身后压暗，近似 reed_field.gd）
SHADE_RINGS = [((44, 54), 0.99), ((35, 45), 0.98), ((27, 36), 0.97), ((20, 28), 0.962), ((13, 21), 0.955)]   # 晨身后压暗（和 reed_field.gd 一样）


def compose(layers_img, atlas, meta, place, cl, chen_x=None, theta_fn=None, birds=None, bmeta=None, chen_frame=18, skip=None, splash=None,
            chen_flip=False, extra=None):
    """extra：[(z, fn(blit))]，预览里另外叠的东西（物件、居民……，tools/reed_field_props.py 用）；chen_flip = 晨朝左"""
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
        if L["id"] == skip:
            return
        if L["id"] not in layers_img:                  # 中景的树（props/ 里的层）：主脚本不画，从文件读
            layers_img[L["id"]] = np.array(Image.open(OUT / L["img"]).convert("RGBA"))
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
        for e in place.get(row, []):
            x, y, vn = e[0], e[1], e[2]
            lean = e[4] if len(e) > 4 else 0.0
            sx = round(x - cl * sc)
            if sx < -160 or sx > 640:
                continue
            v = meta["variants"][vn]
            th = theta_fn(row, x, sx) if theta_fn else (3.0 + v["rest"] + lean) * (0.45 if row.startswith("g") else 1.0)
            i = int(np.argmin([abs(a - th) for a in meta["angles"]]))
            fx, fy, fw, fh, ox, oy, _, _ = v["frames"][i]
            blit(atlas[fy:fy + fh, fx:fx + fw], sx + ox, y + oy)

    sheet = np.array(Image.open(ROOT / "art/characters/chen/chen_oscar.png").convert("RGBA"))
    fr = sheet[:, chen_frame * 68:(chen_frame + 1) * 68]
    cax = 26
    if chen_flip:
        fr = fr[:, ::-1]
        cax = 67 - 26

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
        ref[m, :3] = np.round(ref[m, :3] * 0.55 + np.array([176, 220, 205]) * 0.45).astype(np.uint8)
        blit(ref, gx - cax, g, alpha=0.42)

    def do_chen():
        if chen_x is not None:
            blit(fr, round(chen_x - cl) - cax, ground(chen_x) - 58)

    items = []
    for i, L in enumerate(j["layers"]):
        items.append((L.get("z", -100 + i), i, lambda L=L: layer(L)))
    for rname, z in ROW_Z.items():
        items.append((z, 0, lambda r=rname: reeds(r, ROW_SCROLL.get(r, 1.0))))
    items += [(-29, 0, do_birds), (-3, 0, do_refl), (-2, 0, do_shade), (0, 0, do_chen)]
    for z, fn in (extra or []):
        items.append((z, 1, lambda fn=fn: fn(blit)))

    def do_splash():                              # 预览：落脚那一下的水花（第 splash 帧），锚点 = 水面那一行、脚的正下方
        if splash is None or chen_x is None or not fauna_global:
            return
        fa, fm = fauna_global
        fx, fy, fw, fh, ax, ay = fm["frames"]["splash_%d" % splash]
        blit(fa[fy:fy + fh, fx:fx + fw], round(chen_x - cl) - 2 - ax, ground(chen_x) - 3 - ay)
    items.append((22, 0, do_splash))

    def do_isle_fauna():                          # 预览：白鹭一只站、一只啄水；野鸭带一道波纹
        if not fauna_global:
            return
        fa, fm = fauna_global
        sc = fm["isle_scroll"]

        def put_fr(name, lx, ly, face=1):
            fx, fy, fw, fh, ax, ay = fm["frames"][name]
            im = fa[fy:fy + fh, fx:fx + fw]
            if face < 0:
                im = im[:, ::-1]
                ax = fw - 1 - ax
            sx = (round(-cl * sc) + lx + 40) % 960 - 40
            blit(im, round(sx - ax), round(ly - ay))
            return sx
        for i, (lx, ly, face) in enumerate(fm["egrets"]):
            put_fr("egret_" + ("down" if i % 2 else "stand"), lx, ly, face)
        for (a, b, ly, n) in fm["ducks"]:
            for k in range(n):
                lx = a + (b - a) * 0.4 + k * 8
                sx = put_fr("duck_swim0", lx, ly, 1)
                for d, (L, dy, c) in enumerate(((4, 0, "#f6fbf4"), (5, 1, "#dcefee"))):
                    for t in range(L):
                        X, Y = round(sx - 3 - d * 2 - t), ly + 1 + dy
                        if 0 <= X < 480:
                            out[Y, X] = hexc(c)

    def do_flock():
        if not fauna_global or chen_x is None:
            return
        fa, fm = fauna_global
        for k in range(6):
            side = 1 if k % 2 else -1
            x, y = 330 - (k + 1) // 2 * 7, 52 + side * ((k + 1) // 2) * 3
            fx, fy, fw, fh, ax, ay = fm["frames"]["flock%d_%s" % (2 if k < 3 else 3, ("up", "mid", "down")[k % 3])]
            blit(fa[fy:fy + fh, fx:fx + fw], x - ax, y - ay)
    items += [(FAUNA_Z.get("isle", -70), 1, do_isle_fauna), (FAUNA_Z.get("flock", -90), 1, do_flock)]

    def do_fg():
        if "fg" in layers_img:
            blit(layers_img["fg"], round(-cl * FG_SCROLL), FG_Y)
    items.append((116, 0, do_fg))
    for _z, _i, fn in sorted(items, key=lambda t: (t[0], t[1])):
        fn()
    return out


birds_img_global = [None]
fauna_global: list = []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    args = ap.parse_args()
    p = ROOT / "art" / "手改清单.json"
    locked = set(json.loads(p.read_text()).get("files", {})) if p.exists() else set()
    OUT.mkdir(parents=True, exist_ok=True)

    imgs = {}
    BGW_SET.update(tuple(hexc(c)) for c in [q[1] for q in BGW] + BGW_GLINT)
    POOL_SET.update(tuple(hexc(c)) for c in POOL + POOL_SAND + [POOL_EDGE])
    POOL_SET.update(BGW_SET)
    PAD_SET.update(tuple(hexc(c)) for c in (GREEN[0], GREEN[1], GREEN[3]))
    print("画：天、横云、远景、中景的河、草甸、浅水、脚踝……")
    imgs["sky"] = draw_sky()
    imgs["streaks"] = draw_streaks()
    for r in RANGES:
        imgs[r["id"]] = draw_hills10(r) if r["id"] == "hills" else draw_range(r)
    imgs["far"] = draw_far10()
    imgs["mid"] = draw_mid10()
    imgs["mid_glints"] = draw_glints_band(960, MID_H, MID_Y, imgs["mid"], 61, 50)
    imgs["isles"] = draw_isles10()
    for m in MISTS:
        imgs[m[0]] = draw_mist(m)
    imgs["fg"] = draw_fg()
    imgs["main"], gy, wtop, ws, isles, rip, motes = draw_main6()
    RIPPLE_PTS[:] = rip
    MOTE_PTS[:] = motes
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
    rock_mask = draw_rocks(imgs["main"], np.random.default_rng(1331))
    imgs["glints"] = draw_glints_main(gy, ws, wtop)
    imgs["glints"][rock_mask] = 0                           # 亮纹不压在石头上
    imgs["bigtrees"] = draw_bigtrees()
    imgs["ankle"] = draw_ankle(imgs["main"], gy, ws)
    imgs["ankle_water"] = draw_ankle_water(gy, ws)
    print("画：巨大作物……")
    gimgs, glayers = draw_giants()
    imgs.update(gimgs)
    GIANT_LAYERS[:] = glayers
    print("画：芦苇和草丛的弯曲帧、鸟……")
    atlas, meta, vs, grass = build_reeds()
    place = place6(vs, grass, gy, ws, isles)
    birds, bmeta = build_birds()
    birds_img_global[0] = birds
    fauna, fmeta = build_fauna()
    fmeta = fauna_places(fmeta, imgs["isles"])
    fauna_global[:] = [fauna, fmeta]

    print("自查：")
    bad = 0
    for k in ("sky", "streaks", *[r["id"] for r in RANGES], "far", "mid", "isles", "main", "ankle", "ankle_water", *[g[0] for g in GIANTS],
              *[m[0] for m in MISTS], "fg", "bigtrees"):
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
    nf = 0
    for k, (fx, fy, fw, fh, _ax, _ay) in fmeta["frames"].items():
        f = blank(fw + 2, fh + 2)
        f[1:-1, 1:-1] = fauna[fy:fy + fh, fx:fx + fw]
        nf += scan_quiet(f)
    print(f"  fauna（逐帧，只看轮廓）: 只有对角相连 + 孤立单像素 + 细线缺口 共 {nf}")
    bad += nf
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
    for old in ("wisps.png", "clouds.png", "lake.png", "sunpath.png", "giant_wheat_far.png", "giant_wheat_near.png",
                "giant_wheat_front.png", "giant_dandelion_far.png", "giant_dandelion_near.png", "cover_r0.png", "cover_r1.png",
                "cover_f.png", "hills0.png", "hills1.png", "hills2.png", "tall.png"):
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
    save(fauna, "fauna.png")
    for name, data in (("reeds.json", {**meta, "rows": place}), ("birds.json", bmeta), ("fauna.json", fmeta), ("room.json", room_json())):
        rel = (OUT / name).relative_to(ROOT).as_posix()
        if rel not in locked:
            (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=1 if name == "room.json" else None) + "\n", encoding="utf-8")
    print("ok reed_field", W, H, "芦苇", {r: len(v) for r, v in place.items()}, "种类", len(vs), "atlas", atlas.shape[1], "×", atlas.shape[0],
          "问题", bad)

    # 悬空检查（第十版）：镜头从左走到右，每株大蒲公英的根要么看得见（自己那丛草 + 倒影），
    # 要么被更近的植物盖住；杆子看得见的最下面一格底下要是植物 / 它自己的草，不能是水或天（那就是悬在半空）
    print("悬空检查：")
    water_like = BGW_SET | POOL_SET | {tuple(hexc(c)) for c in GLINT + SURF}
    nfloat = 0
    for gid, sc, rx, ry in GIANT_ROOTS:
        seen = hidden = 0
        for cl in range(0, W - 480 + 1, 24):
            sx = round(rx - cl * sc)
            if not (4 <= sx < 476):
                continue
            a = compose(imgs, atlas, meta, place, cl)
            b = compose(imgs, atlas, meta, place, cl, skip=gid)
            diff = (a != b).any(axis=2)
            col = np.nonzero(diff[:, max(0, sx - 1):sx + 2].any(axis=1))[0]
            col = col[col < ry + 1]
            if not len(col):
                hidden += 1
                continue
            yb = int(col.max())
            if yb >= ry - 1:
                seen += 1
                continue
            below = tuple(a[yb + 1, sx])
            if below in water_like or yb + 1 < 120:
                nfloat += 1
                print(f"  {gid}: 镜头 {cl}，杆子在 y {yb} 断了，底下是水 / 天 {below}")
            else:
                hidden += 1
        print(f"  {gid}: 根看得见 {seen} 次，被前面的植物挡住 {hidden} 次")
    print("  悬空：", nfloat)
    bad += nfloat

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
        for name, cxr in (("chen_water", 700), ("chen_reeds", 300), ("dandelions", 1700)):
            s2 = compose(imgs, atlas, meta, place, min(max(cxr - 240, 0), W - 480), chen_x=cxr)
            Image.fromarray(s2).resize((480 * 2, H * 2), Image.NEAREST).save(pv / f"{name}_2x.png")
        Image.fromarray(atlas).resize((atlas.shape[1] * 3, atlas.shape[0] * 3), Image.NEAREST).save(pv / "reeds_3x.png")
        # 第十一版：带晨的一屏 2 倍（落脚溅起水花那一下）、水花 8 倍逐帧（晨的脚 + 水面，从左到右 0–4 帧）、超前景和雾的局部
        s1 = compose(imgs, atlas, meta, place, 0, chen_x=240, splash=1)
        Image.fromarray(s1).resize((960, H * 2), Image.NEAREST).save(pv / "chen_splash_2x.png")
        cells = []
        for f in range(SPLASH_FRAMES):
            s2 = compose(imgs, atlas, meta, place, 0, chen_x=240, splash=f)
            g = ground(240)
            cells.append(s2[g - 24:g + 6, 216:258])
            cells.append(np.full((30, 1, 4), 255, np.uint8))
        strip = np.concatenate(cells[:-1], axis=1)
        Image.fromarray(strip).resize((strip.shape[1] * 8, strip.shape[0] * 8), Image.NEAREST).save(pv / "splash_frames_8x.png")
        tall = [x for k, x in FG_PLACED if k == "tall"]
        if tall:
            cl = int(min(max((tall[0] - 330) / FG_SCROLL, 0), W - 480))
            s3 = compose(imgs, atlas, meta, place, cl, chen_x=cl + 240)
            Image.fromarray(s3).resize((960, H * 2), Image.NEAREST).save(pv / "foreground_2x.png")
        s4 = compose(imgs, atlas, meta, place, 160, chen_x=400)
        crop = s4[112:186, 0:480]
        Image.fromarray(crop).resize((crop.shape[1] * 3, crop.shape[0] * 3), Image.NEAREST).save(pv / "mist_3x.png")
        print("  超前景放在：", [(k, round(x)) for k, x in FG_PLACED])
        print("预览:", pv)


if __name__ == "__main__":
    main()
