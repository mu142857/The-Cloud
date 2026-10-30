"""河流篇 · 河岸 river_bank + 妮芙家 river_home（月夜版）。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_bank_moon_art.py [--preview 目录] [--only bank,home]

底子是作者原来的蓝色月夜河岸（art/river/*，tools/river_art.py）：天、月亮、远岸石柱、雾、对岸怪树、水面碎光那几层原样引用
（room.json 里写 res://art/river/…），在它前面加剧本要的东西：
  岸边卵石滩 + 窄水道（飞机）、一排箱子、木桩、台阶、浅滩、小船、面包店和修补摊（中间一块木板）、
  石柱顶上的两间小屋和屋顶窄桥（邮差）、去市集的石阶、妮芙家（新旧水位交界：水下还有旧一层、旧门牌）。
规矩：夜里，光只有右上的月亮 + 窗里、灯里一点暖黄；近处的东西是暗的剪影（右沿一条月光），晨的白发最亮；
小屋各自分开、不重叠；没有高楼、没有兜帽人群。所有随机固定 seed，alpha 只有 0/255。

输出：art/river_city/river_bank/（层、物件、room.json）、art/river_home/（back / front / light、物件重新上色、room.json）。
物件的 id、状态名、markers 名字、portals 和旧版一样（剧本 story_river.json、打捞 river_salvage.gd 靠它们）。
飞机、箱子、金属盒、漂浮物的形状借 tools/river_city_art.py 的函数画，再换成月夜的颜色；妮芙家的屋内借 tools/river_home_art.py。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from oscarkit.palette import from_lch, oklab_to_srgb  # noqa: E402
from oscarkit.measure import srgb_to_oklab  # noqa: E402

import river_art as ra  # noqa: E402
import river_city_art as rca  # noqa: E402
from river_city_art import Cv  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BANK_DIR = ROOT / "art" / "river_city" / "river_bank"
HOME_DIR = ROOT / "art" / "river_home"
RIVER = ROOT / "art" / "river"

SW, SH = 480, 270
W = 2320                        # 河岸宽（第三版加长：飞机在最左，晨先一个人走一大段空的河岸，才碰到箱子后面的妮芙）
G = 206                         # 岸（石砌码头）的地面
WL = 218                        # 近处的水面（water 层的上沿）
LONE = (330, 820)               # 空的那一段：只有月亮、石柱、垂枝树、雾、水面碎光，什么都不能点、没有人家
DRIFT = 820                     # 打捞：东西从这里往下游漂
POST = 872                      # 木桩（阿汀撑船靠过来）
CRATES = 904                    # 一排箱子（物件左边）
STEPS_X = 1022                  # 台阶（码头上沿往下到水边的平台）
SHALLOW = (1180, 1320)          # 下游浅滩（水底的旧街砖）
HOME_X = 1570                   # 妮芙家底边中点
HOME = (1360, 1780)             # 妮芙家占的那一段（house 的 back 画在这里，主层这段只画地面和水下的旧一层）
BAKERY = 1870                   # 面包店（巨石里凿的）
INLET = (1930, 2050)            # 面包店和修补摊之间那一小片浅水
STALL = (1975, 2025)            # 修补摊（浅水里一块平顶大石头）
TOWERS = (2088, 2166)           # 两根凿了人家的石柱（作者喜欢的那种）
STAIR = 2240                    # 去市集：大石柱脚下凿进去的拱门洞，石阶在里面往上
SOUTH = 2306                    # 往南桥的窄巷口

GROUND = [[0, 214], [110, 214], [150, 212], [330, 206], [STEPS_X, 206], [STEPS_X + 12, 209], [STEPS_X + 25, 212],
          [STEPS_X + 38, 215], [STEPS_X + 88, 215], [STEPS_X + 101, 212], [STEPS_X + 114, 209], [STEPS_X + 128, 206],
          [SHALLOW[0] - 20, 206], [SHALLOW[0] + 40, 213], [SHALLOW[1] - 20, 213], [SHALLOW[1] + 10, 206],
          [INLET[0], 206], [INLET[0] + 14, 213], [INLET[1] - 10, 213], [INLET[1] + 4, 206], [W, 206]]


def gy(x):
    xs, ys = zip(*GROUND)
    return int(round(np.interp(x, xs, ys)))


# ============================================================ 颜色（和 river_art 同一套：OKLCh，暗的偏靛、亮的偏青银）

def B(L, C=None, h=256.0):
    """月夜蓝（river_art.lch：色相按亮度偏）。"""
    return ra.lch(L, C, h)


def Wm(L, C=0.085, h=68.0):
    """暖黄（灯、窗）。最亮 .66，比晨暗。"""
    return tuple(int(v) for v in from_lch(float(L), float(C), float(h)))


ROCK = ra.bramp(5, .075, .235, 260, 247)          # 近处的石头（码头、石柱）
ROCK_FAR = ra.bramp(5, .11, .25, 258, 248)        # 中景
WOOD = [B(.085, .02, 262), B(.115, .022, 258), B(.15, .024, 254), B(.2, .026, 250), B(.27, .028, 246)]
WALL = ra.bramp(5, .09, .25, 260, 248)            # 小屋墙（灰泥 / 木板，月光下都是蓝灰）
ROOF = ra.bramp(4, .06, .2, 264, 250)
MOSS = [B(.1, .028, 228), B(.14, .03, 222), B(.19, .032, 214)]
DARK = B(.05, .02, 266)
WARM = [Wm(.26, .05, 52), Wm(.36, .07, 58), Wm(.48, .085, 64), Wm(.58, .09, 70), Wm(.66, .085, 78)]
WARM_REF = [Wm(.34, .06, 60), Wm(.44, .075, 66)]   # 水里的灯影
SILVER = [B(.3, .03, 250), B(.4, .03, 248), B(.5, .026, 246)]   # 水纹


def to_lab(c):
    return srgb_to_oklab(np.array([c[:3]], float))[0]


def mixc(a, b, t):
    la, lb = to_lab(a), to_lab(b)
    return tuple(int(v) for v in oklab_to_srgb((la + (lb - la) * t)[None])[0])


BAYER = ra.BAYER
LIGHTS_X: list = []             # 主层上亮着的灯 / 窗（x, 大小）：水里的暖影按这个画（画主层时记下来）


# ============================================================ 画东西的小工具

def shade_box(cv: Cv, x0, y0, x1, y1, ramp, lit_r=True, lit_t=True, seed=0, grain=0.35):
    """一块平面（墙、木板）：中间档 + 一点颗粒，上沿、右沿一条月光，左沿暗一档。"""
    rng = np.random.default_rng(seed)
    n = len(ramp)
    mid = n // 2 - (1 if n > 3 else 0)
    for y in range(int(y0), int(y1)):
        for x in range(int(x0), int(x1)):
            k = mid
            if rng.random() < grain * 0.25:
                k = max(0, mid - 1)
            cv.px(x, y, ramp[k])
    if lit_t:
        cv.hline(x0, x1, y0, ramp[min(n - 1, mid + 2)])
    if lit_r:
        cv.vline(x1 - 1, y0, y1, ramp[min(n - 1, mid + 1)])
    cv.vline(x0, y0 + 1, y1, ramp[max(0, mid - 1)])


def _hash01(x, y, seed=0):
    """一个像素的固定随机数（0..1）。"""
    v = (x * 374761393 + y * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
    return (v & 0xFFFF) / 65535.0


def glow(cv: Cv, cx, cy, r, base_mask=None, steps=((0.45, 0), (0.75, 1)), solid_only=True, warm=WARM):
    """暖光落到周围的石头上：已经画了的像素里，离灯 r 以内的往暖色推；离灯越远推得越少、很快就没了。
    外圈不用棋盘格，用一团一团的（两三个像素一块）断开。"""
    y0, y1 = max(0, int(cy - r)), min(cv.h, int(cy + r + 1))
    x0, x1 = max(0, int(cx - r)), min(cv.w, int(cx + r + 1))
    for y in range(y0, y1):
        for x in range(x0, x1):
            if cv.a[y, x, 3] == 0:
                continue
            if base_mask is not None and not base_mask[y, x]:
                continue
            d = math.hypot(x - cx, (y - cy) * 1.1) / r
            if d > 1:
                continue
            if d > 0.6 and _hash01(x // 2, y // 2, 7) < (d - 0.6) * 2.2:
                continue
            c = tuple(int(v) for v in cv.a[y, x, :3])
            L = to_lab(c)[0]
            t = 0.55 * (1 - d) ** 1.6
            tgt = warm[1] if d > 0.45 else warm[2]
            nl = mixc(c, tgt, t)
            if to_lab(nl)[0] < L:
                nl = mixc(c, warm[0], t * 0.5)
            cv.a[y, x, :3] = nl


def lantern(cv: Cv, x, y, kind="hang", r=9):
    """一盏灯（x, y = 灯芯）：hang = 挂着的小提灯（铁框），post = 柱头上的方灯，stone = 石灯笼的灯窗。"""
    iron = B(.07, .015, 262)
    if kind == "hang":
        cv.vline(x, y - 5, y - 2, iron)
        cv.rect(x - 2, y - 2, x + 3, y - 1, iron)
        cv.rect(x - 2, y - 1, x + 3, y + 3, WARM[3])
        cv.px(x, y, WARM[4])
        cv.px(x, y + 1, WARM[4])
        cv.vline(x - 2, y - 1, y + 3, WARM[2])
        cv.rect(x - 2, y + 3, x + 3, y + 4, iron)
    elif kind == "post":
        cv.rect(x - 2, y - 3, x + 3, y - 2, iron)
        cv.rect(x - 2, y - 2, x + 3, y + 2, WARM[3])
        cv.px(x, y - 1, WARM[4])
        cv.px(x, y, WARM[4])
        cv.rect(x - 1, y - 4, x + 2, y - 3, iron)
    glow(cv, x, y, r)


def pillar_at(cv: Cv, x, foot, w, h, seed, kind="tower", pal=ROCK, crown=True, broken=False):
    img = stone_pillar(w, h, seed, pal, crown=[B(.07, .02, 258), B(.1, .022, 252)] if crown else None, kind=kind,
                    broken=broken)
    cv.paste(img, int(x - img.shape[1] // 2), int(foot - img.shape[0] + 1))
    return img


def weeping(cv: Cv, x, base, h, cw, seed, pal=None, kind="weeping"):
    """近处的垂枝怪树（river_art.strange_tree，换成近处的暗色）。"""
    pal = pal or [B(.06, .02, 262), B(.085, .022, 258), B(.12, .024, 252)]
    tmp = ra.Layer(cv.w, cv.h)
    ra.strange_tree(tmp, x, base, h, cw, seed, pal, kind)
    cv.paste(ra.keep_attached(tmp.a, base) if tmp.a[base].any() else tmp.a, 0, 0)


def rope_line(cv: Cv, x0, y0, x1, y1, sag, c):
    n = max(2, int(abs(x1 - x0)))
    for i in range(n + 1):
        t = i / n
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t + sag * math.sin(math.pi * t)
        cv.px(int(round(x)), int(round(y)), c)


# ============================================================ 石头住处（作者 10-30：不要砖房、不要吊脚楼；房子是巨石 / 石柱里凿出来的洞窟屋，
# 或者大块粗石垒的矮屋。门窗是石头里凿出的洞，里面透暖黄的灯。参考 art/river 的怪石柱、art/underwater 的石头人头）

STONE = ra.bramp(6, .085, .32, 258, 238)          # 住处的石头：比码头亮一点、往青灰偏（水下石头人头那种）
STONE_FAR = ra.bramp(5, .12, .27, 256, 240)


def shade_mass(m, rng, pal, cracks=4, strata=3, amp=0.5):
    """一整块石头的上色（不是砖缝）：大块的明暗起伏（平滑噪声），顶面一圈受月光、右沿亮、左沿暗，
    几条往下爬的裂缝和几道不贯通的岩层缝。分档上色，档边一条窄棋盘格。返回 RGBA。"""
    h, w = m.shape
    n = len(pal)
    nz = ra.vnoise(h, w, 22, 34, rng) * 0.7 + ra.vnoise(h, w, 6, 9, rng) * 0.3
    v = 0.3 + amp * (nz - 0.5)
    top = np.full(w, h)
    for x in range(w):
        ys = np.nonzero(m[:, x])[0]
        if len(ys):
            top[x] = ys[0]
    Y = np.arange(h)[:, None]
    v = v + 0.5 * np.exp(-np.clip(Y - top[None, :], 0, None) / 4.0)
    xl = np.full(h, w)
    xr = np.full(h, -1)
    for y in range(h):
        xs = np.nonzero(m[y])[0]
        if len(xs):
            xl[y], xr[y] = xs[0], xs[-1]
    X = np.arange(w)[None, :]
    v = v + 0.32 * np.exp(-np.clip(xr[:, None] - X, 0, None) / 3.0) - 0.22 * np.exp(-np.clip(X - xl[:, None], 0, None) / 6.0)
    v = v + 0.12 * (X / max(1, w) - 0.5)
    bay = np.tile(ra.BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w]
    idx = np.clip(np.floor(v * (n - 1) + 0.5 + (bay - 0.5) * 0.45), 0, n - 1).astype(int)
    img = np.zeros((h, w, 4), np.uint8)
    for k in range(n):
        mm = m & (idx == k)
        img[mm, :3] = pal[k]
        img[mm, 3] = 255
    # 裂缝（往下爬，暗一档、右唇亮一档）
    for _ in range(cracks):
        xs = np.nonzero(m.any(0))[0]
        x = float(rng.uniform(xs[0] + 4, xs[-1] - 4))
        y = float(top[int(x)] + rng.uniform(2, 10))
        for s in range(int(rng.integers(8, 30))):
            xi, yi = int(round(x)), int(round(y))
            if 0 <= yi < h and 0 < xi < w - 1 and m[yi, xi] and m[yi, xi + 1]:
                img[yi, xi, :3] = pal[0]
                img[yi, xi + 1, :3] = pal[min(n - 1, idx[yi, xi + 1] + 1)]
            x += rng.uniform(-0.7, 0.7)
            y += 1
    # 岩层缝（横的，一段一段）
    for _ in range(strata):
        y = int(rng.uniform(h * 0.2, h * 0.9))
        x = int(rng.uniform(0, w * 0.6))
        ln = int(rng.uniform(w * 0.15, w * 0.45))
        for k in range(ln):
            yy = y + int(round(1.5 * math.sin(k / 9.0)))
            if 0 <= yy < h - 1 and 0 <= x + k < w and m[yy, x + k]:
                img[yy, x + k, :3] = pal[0]
                if m[yy + 1, x + k]:
                    img[yy + 1, x + k, :3] = pal[min(n - 1, idx[yy + 1, x + k] + 1)]
    return img


# ------------------------------------------------------------ 第四版石头材质（作者：石头缺质感——像剪纸、糊、脏）
# 做法：先按形体定光（月光从右上：柱子按竖着的柱状节理切成几个面，每个面一个朝向、一个亮度，面和面之间一道节理缝），
# 再加大面的冷暖明暗慢变化、手画感的 2~3 色小色团（不是满屏棋盘格）、右沿一道冷亮边、底部和缝里的暗部（AO）、
# 被自己挡住月光的投影、几道横的岩层台（上沿受光、下面一道影子）、苔藓长在缝里和背光处、台子下面挂水渍、水位线以下更深更湿。

def expand_pal(pal, n=8):
    """把一条石头色阶扩成 n 档（最暗 → 最亮）+ 一档冷的边缘亮光。"""
    out = [mixc(pal[0], pal[-1], i / (n - 1)) for i in range(n)]
    out[0] = mixc(pal[0], B(.035, .02, 266), 0.35)
    rim = mixc(pal[-1], B(.52, .035, 228), 0.45)
    return out + [rim]


def cluster_noise(h, w, rng, cell=2.6):
    """小色团用的噪声：几个像素一团（手画的笔触块），不是一格一格的棋盘。"""
    a = ra.vnoise(h, w, cell, cell * 1.3, rng)
    b = ra.vnoise(h, w, cell * 2.2, cell * 1.6, rng)
    return np.clip(0.65 * a + 0.35 * b, 0, 1)


def stone_shade(m, rng, pal, facet_w=9.0, joints=0.75, ledges=1.0, moss=0.6, stains=1.0, water_row=None,
                ao_rows=10, light=1.0):
    """一整块石头（柱子 / 巨石）的材质。m = bool 形状，pal = 石头色阶（会扩成 8 档 + 亮边）。返回 RGBA。"""
    h, w = m.shape
    P = expand_pal(pal)
    n = len(P) - 1                                    # 0..n-1 是面的明暗，P[n] 是亮边
    tone = np.full((h, w), -1.0)
    fac = np.full((h, w), -1, int)
    # 节理：每一行把这一段（柱身）切成几个竖面，切点的相对位置随高度慢慢漂（柱状节理，竖着走）
    k_max = 9
    drift = [ra.smooth1d(h, rng, max(12, h / 3), 1.0) for _ in range(k_max)]
    base_u = np.sort(rng.uniform(0.05, 0.95, k_max))
    rows = np.nonzero(m.any(1))[0]
    if len(rows) == 0:
        return np.zeros((h, w, 4), np.uint8)
    bot = rows.max()
    for y in rows:
        xs = np.nonzero(m[y])[0]
        runs = np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1)
        for run in runs:
            a, b = run[0], run[-1]
            wid = b - a + 1
            k = max(1, min(k_max, int(round(wid / facet_w))))
            cuts = np.sort(np.clip(np.linspace(0, 1, k + 1)[1:-1] + 0.35 / k * np.array([drift[i][y] for i in range(k - 1)]),
                                   0.02, 0.98)) if k > 1 else np.array([])
            for x in run:
                u = (x - a + 0.5) / wid
                fi = int(np.searchsorted(cuts, u))
                lo = 0.0 if fi == 0 else cuts[fi - 1]
                hi = 1.0 if fi == len(cuts) else cuts[fi]
                uc = (lo + hi) / 2
                nx = 2 * uc - 1                       # 这个面朝哪边（−1 左 … 1 右）
                lam = 0.42 + 0.42 * nx * light        # 月光从右边来：背光面不掉成死黑
                lam += 0.08 * ((fi * 37 + 11) % 5 - 2) / 2    # 相邻的面差一点（面是平的，不是渐变）
                tone[y, x] = np.clip(lam, 0, 1)
                fac[y, x] = fi + 100 * (a // 4)
    # 朝上的面（顶、台）亮
    up = m & ~np.vstack([np.zeros((1, w), bool), m[:-1]])
    up2 = m & ~np.vstack([np.zeros((2, w), bool), m[:-2]])
    tone[up2] = np.maximum(tone[up2], 0.72)
    tone[up] = np.maximum(tone[up], 0.88)
    # 大面的慢变化 + 竖向的纹理（顺着节理）
    big = ra.vnoise(h, w, 34, 22, rng) - 0.5
    streak = ra.vnoise(h, w, 14, 2.2, rng) - 0.5
    tone += 0.16 * big + 0.07 * streak
    # 底部 AO、往上略亮（月光从上来）
    Y = np.arange(h)[:, None]
    tone += 0.06 * (1 - Y / max(1, bot))
    near_bot = np.clip((bot - Y) / max(1, ao_rows), 0, 1)
    tone = tone * (0.55 + 0.45 * near_bot)
    # 自己挡住月光的地方（右上方向撞回石头 = 投影）
    for y, x in zip(*np.nonzero(m)):
        out = False
        for k in range(1, 18):
            qy, qx = y - k, int(round(x + 0.7 * k))
            if qy < 0 or qx >= w:
                break
            if not m[qy, qx]:
                out = True
            elif out:
                tone[y, x] = min(tone[y, x], 0.12 if k < 10 else 0.3)
                break
    # 横的岩层台：从一边伸进去一截，台面一行受光，下面一行影子，再下面一截水渍
    ledge_rows = []
    for _ in range(int(ledges * max(1, len(rows) // 34))):
        y = int(rng.choice(rows[4:-6])) if len(rows) > 14 else None
        if y is None:
            break
        xs = np.nonzero(m[y])[0]
        a, b = xs[0], xs[-1]
        ln = int((b - a) * rng.uniform(0.25, 0.7))
        from_right = rng.random() < 0.6
        yy = y
        for k in range(ln):
            x = b - k if from_right else a + k
            if rng.random() < 0.12:
                yy += int(rng.choice([-1, 1]))
            if 0 < yy < h - 1 and m[yy, x] and m[yy + 1, x]:
                tone[yy, x] = max(tone[yy, x], 0.8)
                tone[yy + 1, x] = min(tone[yy + 1, x], 0.1)
                ledge_rows.append((yy + 1, x))
    # 量化：面的明暗 + 小色团（2~3 色一团）
    cn = cluster_noise(h, w, rng)
    q = tone * (n - 1) + 0.5 + (cn - 0.5) * 0.7
    idx = np.clip(np.floor(q), 0, n - 1).astype(int)
    img = np.zeros((h, w, 4), np.uint8)
    for k in range(n):
        mm = m & (idx == k)
        img[mm, :3] = P[k]
        img[mm, 3] = 255
    # 节理缝：面和面之间，一段一段（不是一根到底的黑线），宽窄不一；缝右边一条亮唇
    jl = ra.vnoise(h, w, 9, 30, rng)
    for y in rows:
        for x in range(1, w - 1):
            if not (m[y, x] and m[y, x - 1]) or fac[y, x] == fac[y, x - 1]:
                continue
            if jl[y, x] < 1 - joints:
                continue
            img[y, x, :3] = P[max(0, idx[y, x] - 2)]
            if jl[y, x] > 0.86 and m[y, x - 1]:
                img[y, x - 1, :3] = P[max(0, idx[y, x - 1] - 2)]
            if x + 1 < w and m[y, x + 1] and tone[y, x + 1] > 0.45:
                img[y, x + 1, :3] = P[min(n - 1, idx[y, x + 1] + 1)]
    # 分叉的细裂缝（少而准）
    pts = np.argwhere(m)
    for _ in range(int(rng.integers(1, 2 + w // 40))):
        y, x = pts[int(rng.integers(0, max(1, len(pts) // 2)))]
        ln = int(rng.uniform(0.1, 0.35) * h)
        xf = float(x)
        for k in range(ln):
            yy, xx = y + k, int(round(xf))
            if not (0 <= yy < h and 0 < xx < w - 1 and m[yy, xx] and m[yy, xx - 1] and m[yy, xx + 1]):
                break
            img[yy, xx, :3] = P[max(0, idx[yy, xx] - 3)]
            xf += rng.uniform(-0.6, 0.6)
            if rng.random() < 0.05:                   # 分一个小叉
                bx, by = xx, yy
                d = 1 if rng.random() < 0.5 else -1
                for j in range(int(rng.integers(2, 6))):
                    bx += d
                    by += 1
                    if 0 <= by < h and 0 <= bx < w and m[by, bx]:
                        img[by, bx, :3] = P[max(0, idx[by, bx] - 2)]
    # 右沿冷亮边、左沿暗一档（不描深色边）
    for y in rows:
        xs = np.nonzero(m[y])[0]
        runs = np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1)
        for run in runs:
            b = run[-1]
            if len(run) >= 4 and tone[y, b] > 0.3:
                img[y, b, :3] = P[n]
                img[y, b - 1, :3] = P[min(n - 1, idx[y, b - 1] + 1)]
    # 台子下面挂的水渍：往下一两条暗的细痕
    for (y, x) in ledge_rows[::3]:
        if rng.random() < 0.35 * stains:
            for d in range(1, int(rng.integers(3, 12))):
                if y + d < h and m[y + d, x]:
                    img[y + d, x, :3] = P[max(0, idx[y + d, x] - 1)]
    # 苔藓：长在朝上的面、台子上和背光的缝里（一小团一小团）
    if moss > 0:
        mo = cluster_noise(h, w, rng, 2.0)
        for y, x in zip(*np.nonzero(m)):
            on_top = up[y, x] or (y > 0 and up2[y, x])
            shady = tone[y, x] < 0.35
            if (on_top and mo[y, x] > 1 - 0.55 * moss) or (shady and mo[y, x] > 1 - 0.12 * moss):
                img[y, x, :3] = MOSS[2] if (on_top and mo[y, x] > 0.85) else (MOSS[1] if on_top else MOSS[0])
    # 水位线以下：更深、更湿，水线上一道湿亮
    if water_row is not None:
        for y in range(max(0, water_row - 6), h):
            for x in np.nonzero(m[y])[0]:
                c = tuple(int(v) for v in img[y, x, :3])
                if y >= water_row:
                    img[y, x, :3] = mixc(c, B(.06, .03, 236), 0.5)
                elif y >= water_row - 6:
                    img[y, x, :3] = mixc(c, B(.08, .03, 238), 0.25)
            if y == water_row - 1:
                for x in np.nonzero(m[y])[0]:
                    if (x * 7 + y) % 5 < 2:
                        img[y, x, :3] = B(.3, .03, 236)
    return img


def stone_pillar(w, h, seed, pal=None, crown=None, kind="tower", broken=False, **kw):
    """一根石柱（形状用 river_art 的 pillar_mask，材质换成 stone_shade）。返回 RGBA，柱脚在底边正中。"""
    pal = pal or STONE
    rng = np.random.default_rng(seed)
    m, top = ra.pillar_mask(w, h, rng, kind, broken)
    img = stone_shade(m, rng, pal, facet_w=max(6.0, w / 4.0), **kw)
    ih, iw = m.shape
    if crown is not None:                             # 顶上一丛垂下来的怪植物（照 river_art.pillar）
        ys, xs_ = np.nonzero(m)
        ty = ys.min()
        tx = xs_[ys == ty].mean()
        nc = len(crown)
        for i in range(int(rng.integers(3, 8))):
            side = -1 if rng.random() < 0.5 else 1
            ln = rng.uniform(w * 0.3, w * 0.9)
            px, py = tx + rng.uniform(-w * 0.25, w * 0.25), ty + 1.0
            ang = rng.uniform(-1.9, -1.2)
            steps = int(ln * 1.6)
            turn = rng.uniform(1.4, 2.3) / max(1, steps)
            for s_ in range(steps):
                ang += turn
                px += np.cos(ang) * side * 0.6
                py += np.sin(ang) * 0.6
                xi, yi = int(round(px)), int(round(py))
                if 0 <= xi < iw and 0 <= yi < ih:
                    img[yi, xi] = ra.rgba(crown[min(nc - 1, 1 if side > 0 else 0)])
    return ra.keep_attached(img, ih - 1)


def blob_mask(w, h, rng, p=2.6, lump=0.08):
    """一块巨石的形：底平，顶是压扁的圆拱（超椭圆），边上风化起伏。"""
    m = np.zeros((h, w), bool)
    nz = ra.smooth1d(w, rng, max(10, w / 2), 1.0)
    for x in range(w):
        u = min(1.0, abs((x + 0.5 - w / 2) / (w / 2)))
        t = (1 - u ** p) ** (1 / p) * (1 + lump * nz[x])
        m[int(round(h * (1 - min(1.0, t)))):, x] = True
    return m


def opening_mask(w, h, kind):
    m = np.zeros((h, w), bool)
    r = w / 2
    for yy in range(h):
        for xx in range(w):
            if kind == "round":
                m[yy, xx] = math.hypot(xx + .5 - w / 2, (yy + .5 - h / 2) * w / h) <= w / 2
            elif kind == "arch":
                m[yy, xx] = yy >= r or math.hypot(xx + .5 - r, yy + .5 - r) <= r
            else:
                m[yy, xx] = True
    return m


DEEP = [Wm(.15, .035, 48), Wm(.2, .045, 50)] + WARM      # 洞里由暗到亮：最暗两档是屋里的角落


def carve(cv: Cv, x, y, w, h, kind="arch", lit=True, door=False, pal=STONE, glow_r=None, seed=0):
    """在石头上凿一个洞（门 / 窗），凿出厚度（作者：门窗洞不能只是一个亮色块）：
    - 洞口的内侧壁：左壁朝右、接月光（冷，亮一档），右壁和上沿（门楣底面）在影子里——看得出洞有多深；
    - 洞口外沿：门楣、窗台一道受光的边，窗台石板伸出来一点、下面一道影子；洞口边磨损（缺一两个像素）；
    - 洞里是屋里：灯在里面偏下，中间亮、往四边一档档暗（一团一团，不是棋盘格）；有的窗有木窗棂 / 半截帘子 /
      一扇推开的木板窗，窗台上一两样小东西的剪影；亮度每扇不一样，lit=False 的是暗窗（里面深蓝，只有一点冷反光）；
    - 门：一扇往里开的木门板，门槛一道最亮；
    - 暖光从洞口溢到石面上，很快就没了。"""
    rng = np.random.default_rng(seed + x * 7 + y * 13)
    m = opening_mask(w, h, kind)
    # 洞口边磨损：轮廓上随机缺 / 多一两个像素
    for _ in range(max(1, (w + h) // 10)):
        yy, xx = int(rng.integers(0, h)), int(rng.integers(0, w))
        if m[yy, xx] and (xx in (0, w - 1) or yy == 0 or not m[max(0, yy - 1), xx]):
            m[yy, xx] = False
    P = expand_pal(pal)
    rl = max(1, round(w / 5))                        # 左内壁宽（墙厚）
    rr = 1 if w >= 6 else 0                           # 右内壁
    rt = max(1, round(h / 8))                         # 门楣底面
    bright = rng.uniform(0.75, 1.15) if lit else 0
    cx_, cy_ = w * (0.6 if door else 0.55), h * (0.78 if door else 0.62)
    nd = len(DEEP)
    cn = cluster_noise(h + 2, w + 2, rng, 1.8)
    for yy in range(h):
        for xx in range(w):
            if not m[yy, xx]:
                continue
            left = xx < rl or not m[yy, max(0, xx - rl)]
            right = rr and (xx >= w - rr or not m[yy, min(w - 1, xx + rr)])
            top = yy < rt or not m[max(0, yy - rt), xx]
            if top:
                c = P[0]
            elif left:
                c = P[5] if xx == 0 or not m[yy, xx - 1] else P[3]          # 左壁：外沿亮，往里暗
                if lit and yy > h * 0.4:
                    c = mixc(c, WARM[1], 0.35)                             # 屋里的灯也照到左壁下半截
            elif right:
                c = P[1]
            elif not lit:
                c = B(.045, .02, 264) if cn[yy, xx] < 0.7 else B(.07, .025, 250)
            else:
                d = math.hypot((xx + .5 - cx_) / (w * 0.62), (yy + .5 - cy_) / (h * 0.7))
                v = ((1 - d) * (nd - 1.2) + 0.6) * bright + (cn[yy, xx] - 0.5) * 1.1
                c = DEEP[int(np.clip(v, 0, nd - 2))]
            cv.px(x + xx, y + yy, c)
    inner = [(xx, yy) for yy in range(h) for xx in range(w) if m[yy, xx]]
    if lit and not door and w >= 5 and h >= 6:
        v = int(rng.integers(0, 4))
        x_in0 = x + rl
        x_in1 = x + w - 1 - rr
        if v == 0 and w >= 7:                          # 木窗棂：一竖一横
            mx = (x_in0 + x_in1) // 2
            for yy in range(y + rt + 1, y + h):
                if m[yy - y, mx - x]:
                    cv.px(mx, yy, WOOD[1])
            hy = y + int(h * 0.55)
            for xx in range(x_in0, x_in1 + 1):
                if m[hy - y, xx - x]:
                    cv.px(xx, hy, WOOD[1])
        elif v == 1:                                   # 半截帘子（暗暖的布，挡住一边）
            cw = max(1, (x_in1 - x_in0) // 2)
            for yy in range(y + rt, y + h - 1):
                for xx in range(x_in1 - cw + 1, x_in1 + 1):
                    if m[yy - y, xx - x] and (xx + yy // 3) % 3:
                        cv.px(xx, yy, Wm(.3, .06, 40))
        elif v == 2 and w <= 9:                        # 一扇推开的木板窗，挂在窗洞右边
            for yy in range(y + 1, y + h - 1):
                cv.px(x + w + 1, yy, WOOD[2])
                cv.px(x + w + 2, yy, WOOD[1] if yy % 3 else WOOD[0])
        sill = y + h - 1                               # 窗台上的小剪影
        for k in range(int(rng.integers(1, 3))):
            px_ = x_in0 + 1 + int(rng.integers(0, max(1, x_in1 - x_in0 - 1)))
            hh = 1 + int(rng.integers(1, max(2, h // 4)))
            for d in range(hh):
                if m[sill - d - y, px_ - x]:
                    cv.px(px_, sill - d, DEEP[0])
    # 洞口外沿：右沿受月光一道（石唇），门楣上沿一道亮
    for yy in range(h):
        row = np.nonzero(m[yy])[0]
        if len(row):
            cv.px(x + row[-1] + 1, y + yy, P[6])
    for xx in range(w):
        col = np.nonzero(m[:, xx])[0]
        if len(col):
            cv.px(x + xx, y + col[0] - 1, P[5] if xx > w // 3 else P[3])
    # 窗台石板：伸出来一点，台面受光，下面一道影子；门是门槛
    if door:
        cv.hline(x - 1, x + w + 1, y + h, P[6])
    else:
        cv.hline(x - 1, x + w + 1, y + h, P[7])
        cv.hline(x - 1, x + w + 1, y + h + 1, P[3])
        cv.hline(x, x + w + 1, y + h + 2, P[0])
        if lit:
            cv.hline(x + rl, x + w - 1, y + h, mixc(P[7], WARM[3], 0.5))    # 窗台被屋里的光照着
    if door and lit:
        dw = max(2, w // 3)                           # 门板：往里开，斜着看只剩一窄条
        top_ = int(w / 2) + 1
        for yy in range(top_, h):
            for xx in range(rl, rl + dw):
                if m[yy, xx]:
                    cv.px(x + xx, y + yy, WOOD[1] if (xx - rl) % 3 else WOOD[0])
            cv.px(x + rl + dw - 1, y + yy, WARM[2] if yy > h * 0.55 else WARM[1])
        cv.hline(x + rl, x + rl + dw, y + top_, WOOD[0])
        cv.px(x + rl + dw - 2, y + int(h * 0.6), WARM[3])           # 门把手被灯照着
        cv.hline(x + rl + dw, x + w - 1, y + h - 1, WARM[4])        # 门槛那一道最亮
        cv.hline(x + rl + dw, x + w - 1, y + h - 2, WARM[3])
    if lit:
        glow(cv, x + w / 2, y + h * (0.75 if door else 0.55), (glow_r or (max(w, h) + 5)) * (0.7 + 0.3 * bright))


def door_spill(cv: Cv, x, w, ground, length=7):
    """门里的光落到门外地上：一块往外散开的梯形，离门越远越淡（两档 + 棋盘格），只染已经画了的地面。"""
    for d in range(1, length + 1):
        yy = ground + d - 1
        if yy >= cv.h:
            break
        spread = d // 2
        for xx in range(x - spread, x + w + spread):
            if not (0 <= xx < cv.w) or cv.a[yy, xx, 3] == 0:
                continue
            t = d / length
            if t > 0.45 and _hash01(xx // 2, yy, 3) < (t - 0.45) * 1.8:
                continue
            c = tuple(int(v) for v in cv.a[yy, xx, :3])
            cv.a[yy, xx, :3] = mixc(c, WARM[2] if t < 0.4 else WARM[1], 0.5 * (1 - t) + 0.15)


def boulder_house(cv: Cv, cx, base, w, h, seed, openings=(), pal=STONE, moss=True, pipe=None):
    """巨石里凿出来的屋：一整块圆鼓的石头，门窗是凿出的洞；顶上一层苔、几缕垂叶。
    openings = [(kind, 离左 x, 离地 y, w, h, lit, door)]。返回左上角。"""
    rng = np.random.default_rng(seed)
    m = blob_mask(w, h, rng)
    img = stone_shade(m, rng, pal, facet_w=max(7.0, w / 5), ledges=0.6)     # 和石柱同一种质感
    x0, y0 = int(cx - w // 2), int(base - h + 1)
    cv.paste(img, x0, y0)
    if pipe:                                          # 顶上一截铁皮烟囱
        px_ = x0 + pipe
        ty = y0 + int(np.nonzero(m[:, pipe])[0][0])
        cv.rect(px_, ty - 7, px_ + 3, ty + 1, B(.1, .015, 250))
        cv.vline(px_ + 2, ty - 7, ty + 1, B(.2, .02, 246))
        cv.hline(px_ - 1, px_ + 4, ty - 7, B(.22, .02, 246))
    if moss:
        for xx in range(w):
            ys = np.nonzero(m[:, xx])[0]
            if len(ys) and rng.random() < 0.55:
                cv.px(x0 + xx, y0 + ys[0], MOSS[2] if rng.random() < 0.4 else MOSS[1])
                if rng.random() < 0.25:
                    for d in range(1, int(rng.integers(2, 7))):
                        if ys[0] + d < h and m[ys[0] + d, xx]:
                            cv.px(x0 + xx, y0 + ys[0] + d, MOSS[0])
    for (kind, ox, oy, ow, oh, lit, door) in openings:
        carve(cv, x0 + ox, base - oy - oh + 1, ow, oh, kind, lit, door, pal=pal)
        if lit:
            LIGHTS_X.append((x0 + ox + ow // 2, 2 if door else 1))
    return x0, y0


def rough_wall(cv: Cv, x0, x1, y0, y1, rng, pal=STONE):
    """（第三版起不用了：作者看着像砖墙。人家统一用整块巨石 / 石柱凿洞。留着只为别的会话 import 不报错。）
    大块粗石垒的墙：一层层大小不一的石块（不是砖：块宽 9~22、层高 6~11，边角圆、缝是暗的），每块上沿、右沿受月光。"""
    cv.rect(x0, y0, x1, y1, pal[0])
    y = y1
    while y > y0:
        ch = int(rng.integers(6, 12))
        top = max(y0, y - ch)
        x = x0 - int(rng.integers(0, 10))
        while x < x1:
            bw = int(rng.integers(9, 23))
            a, b = max(x0, x), min(x1, x + bw)
            if b - a >= 3:
                tone = int(rng.integers(1, 3))
                for yy in range(top + 1, y):
                    for xx in range(a + 1, b):
                        if (yy in (top + 1, y - 1)) and (xx in (a + 1, b - 1)):
                            continue
                        k = tone
                        if yy == top + 1:
                            k = tone + 2
                        elif xx == b - 1:
                            k = tone + 1
                        elif yy == y - 1:
                            k = max(0, tone - 1)
                        cv.px(xx, yy, pal[min(len(pal) - 1, k)])
            x += bw
        y = top


def stone_hut(cv: Cv, x0, x1, base, wall_h, seed, openings=(), pal=STONE, slab=True):
    """（第三版起不用了：作者看着像砖墙。）
    粗石垒的矮屋：墙是大石块，顶上压一块挑出去的厚石板（上面长苔）。openings 同 boulder_house（相对 x0、地面）。"""
    rng = np.random.default_rng(seed)
    top = base - wall_h
    rough_wall(cv, x0, x1, top, base + 1, rng, pal)
    if slab:
        sx0, sx1 = x0 - 5, x1 + 5
        tilt = rng.uniform(-1.5, 1.5)
        for x in range(sx0, sx1):
            t = (x - sx0) / (sx1 - sx0)
            yy = int(round(top - 5 + tilt * (t - 0.5) * 2 + 0.8 * math.sin(x / 5.0)))
            for d in range(6):
                k = 4 if d == 0 else (2 if d < 4 else (1 if d < 5 else 0))
                cv.px(x, yy + d, pal[k])
            if rng.random() < 0.5:
                cv.px(x, yy - 1, MOSS[1 if rng.random() < 0.6 else 2])
        cv.vline(sx1 - 1, top - 5, top + 1, pal[4])
    for (kind, ox, oy, ow, oh, lit, door) in openings:
        carve(cv, x0 + ox, base - oy - oh + 1, ow, oh, kind, lit, door, pal=pal)


def rows_of(img, ox, oy, y):
    """贴在 (ox, oy) 的一张 RGBA 在房间 y 那一行的左右范围。"""
    r = y - oy
    if not 0 <= r < img.shape[0]:
        return None
    xs = np.nonzero(img[r, :, 3])[0]
    return (ox + xs[0], ox + xs[-1]) if len(xs) else None


# ============================================================ 河岸：中景（scroll 0.55）——河里几块凿了窗的石头、一颗半沉的石头人头

MID_S = 0.55
MID_WL = 192                     # 中景的水线（第七版从 197 抬到 192：远 172 / 中 192 / 近中 200，柱脚不在一条线上；和市集中景一样）
MID_FOOT = MID_WL + 1            # 中景里立在水里的东西，水面和石身相交的那一行
MID_REFL_END = 215               # 中景倒影一直盖到这一行：主层码头上沿最低到 215（台阶、浅滩那里），月光碎片 glints 到 210
WATER_FAR = (6, 13, 28)          # 中景那截远水（art/river/water.png，一行 (6,13,28) 一行 (4,9,23)）
WET = B(.065, .03, 232)          # 贴水那几行湿石头


_WATER_ROWS = None


def water_at(y):
    """远水在房间第 y 行的颜色（天、远岸、雾、远水纹、远水几层叠起来，横向取中位数）：越近地平线越亮越雾。
    远层 / 近中层的倒影按自己那一行的水色来定深浅。"""
    global _WATER_ROWS
    if _WATER_ROWS is None:
        stub = {"size": [W, SH], "layers": [l for l in BG_LAYERS if l.get("shader") != "moonpath"], "objects": {}}
        a = np.concatenate([render(stub, BANK_DIR, c) for c in (0, 400, 800, 1200, 1600)], axis=1)
        _WATER_ROWS = [tuple(int(v) for v in np.median(a[r], axis=0)) for r in range(SH)]
    return _WATER_ROWS[int(np.clip(y, 0, SH - 1))]


def water_foot(img, wl, seed, refl=7, pad=11, water=WATER_FAR, light=1.0, lamps=(), wy=None, depth=0.5):
    """（第五版：作者说中景的石头一个水线是虚线、一个底下啥也没有像浮着）把一张立在水里的图（石柱、石屋、石像）
    在本地第 wl 行切开，接上「立在水里」的接触：
    - 水线以上四行越近水越深越湿（灯和暖光不动）；
    - 第 wl 行贴着石身一条连续的湿亮线，比石脚宽出一像素（月光从右上来：右边亮、左边暗）；
    - 再往下是石身的倒影：竖直镜像、整块不透明（要挡住后面月光碎片 glints 层），一直到 refl 行；每行被水波横着错开 0~2 像素，
      底色比远水深一档，受光的亮边翻成亮的，暖的窗和灯翻成暖的水影，几道很淡的横水纹；
    - 两边各一两道很短很淡的涟漪，往外渐隐，位置和长短不等。
    lamps = 本地 x 的列表：那里有灯 / 亮窗，水里从水线往下一串竖着的暖色水影（一行一小段，左右晃，往下变短变淡）。
    返回 (新图, pad)：新图比原图宽 2*pad、高 wl+1+refl；贴的时候 x 往左挪 pad，第 wl 行对准水线。light 调水线和涟漪的亮度。
    （河岸第七版：中景拆成远 / 中 / 近中三层）wy = 水线在房间里的 y：给了就按那一行往下的真实水色（water_at）定深浅；
    depth 0 远 … 0.5 中（默认，和以前一样）… 1 近：越近倒影底色越深；越远倒影越往下越淡，到底和水一个色（仍不透明，照样挡月光）。"""
    rng = np.random.default_rng(seed)
    if wy is not None:
        water = water_at(wy)

    def wc(d):
        return water_at(wy + d) if wy is not None else water

    dk = 0.15 + 0.5 * depth
    fade = max(0.0, 1.0 - 2.0 * depth)
    h, w = img.shape[:2]
    out = np.zeros((wl + 1 + refl, w + 2 * pad, 4), np.uint8)
    out[:wl, pad:pad + w] = img[:wl]
    src_img = out.copy()                                           # 倒影翻的是没打湿的颜色
    al = out[..., 3] > 0

    def warm(c):
        lab = to_lab(c)
        return math.hypot(lab[1], lab[2]) > 0.05 and lab[2] > 0.02

    def put(x, y, c):
        if 0 <= x < out.shape[1] and 0 <= y < out.shape[0]:
            out[y, x] = (*c, 255)

    for k, t in enumerate((0.55, 0.4, 0.25, 0.12), 1):            # 湿的那一截
        y = wl - k
        if y < 0:
            break
        for x in np.nonzero(al[y])[0]:
            c = tuple(int(v) for v in out[y, x, :3])
            if not warm(c):
                out[y, x, :3] = mixc(c, WET, t)
    base = np.nonzero(al[wl - 1])[0]
    if not len(base):
        return out, pad
    x0, x1 = int(base[0]) - 1, int(base[-1]) + 1
    lo, hi = mixc(water, B(.2, .025, 250), light), mixc(water, SILVER[1], light)
    for x in range(x0, x1 + 1):                                    # 贴着石身的湿亮线：连续一行，亮度一小段一小段地起伏
        u = (x - x0) / max(1, x1 - x0)
        k = 0.7 + 0.45 * _hash01(x // 3, wl, seed + 5)
        put(x, wl, mixc(lo, hi, min(1.0, k * u ** 1.4)))
    sh = [0]                                                       # 倒影：每行横着错开多少（水波，最多两像素）
    ph = rng.uniform(0, 6.3)
    for d in range(1, refl + 1):
        a = min(2.0, 0.6 + 0.15 * d)
        sh.append(int(round(a * math.sin(1.9 * d + ph))))
    # 第六版（作者：柱子前面的月光碎片没被挡住，看着像漂浮）：倒影整块不透明，一直盖到 refl 行（中景看得见的远水底边），
    # 宽度是石身那一行的竖直镜像（中间不留洞），底色比远水深一档；受月光的亮边翻成亮的，暖窗 / 灯翻成暖影；几道很淡的横水纹
    for d in range(1, refl + 1):
        y, src = wl + d, wl - d
        if src < 0:
            break
        xs = np.nonzero(al[src])[0]
        if not len(xs):
            continue
        f = d / refl
        base_c = mixc(wc(d), (1, 3, 11), dk)
        sheen = mixc(base_c, B(.2, .025, 250), 0.25)
        line = d % 4 == 2                                          # 这一行有一道横水纹
        for x in range(int(xs[0]), int(xs[-1]) + 1):
            if al[src, x]:
                c = tuple(int(v) for v in src_img[src, x, :3])
                if warm(c):
                    col = mixc(WARM_REF[1] if d < 4 else WARM_REF[0], base_c, 0.15 + 0.4 * f)
                elif to_lab(c)[0] > 0.2:
                    col = mixc(c, base_c, 0.45 + 0.35 * f)
                else:
                    col = mixc(c, base_c, 0.7)
            else:
                col = base_c
            if line and not warm(col) and _hash01(x // 4, d, seed + 3) > 0.4:
                col = mixc(col, sheen, 0.7)
            if fade:
                col = mixc(col, wc(d), fade * f ** 0.8)
            put(x + sh[d], y, col)
    for lx in lamps:                                               # 灯在水里的暖影（一串竖的，一行一小段，往下变短变淡）
        for d in range(1, refl + 1):
            if _hash01(lx, d, seed + 9) < 0.2 * d / refl:
                continue
            ln = max(1, 3 - d // 4)
            xx = int(lx) + pad + sh[d] + (1 if d % 3 == 1 else 0) - ln // 2
            base_c = mixc(wc(d), (1, 3, 11), dk)
            for i in range(ln):
                put(xx + i, wl + d, mixc(WARM_REF[1] if d < 4 else WARM_REF[0], base_c, 0.1 + 0.55 * d / refl))
    for side in (-1, 1):                                           # 两边的涟漪：一两道，短、淡、往外渐隐
        x = x1 + 1 if side > 0 else x0 - 1
        b = (0.5 if side > 0 else 0.32) * light
        for j in range(int(rng.integers(1, 3)) if side < 0 else 2):
            x += side * int(rng.integers(1, 3 + 2 * j))
            ln = int(rng.integers(2, 5 - j))
            y = wl + (0 if j == 0 else int(rng.integers(0, 3)))
            for i in range(ln):
                put(x + side * i, y, mixc(water, SILVER[0], b * (1 - 0.55 * i / ln)))
            x += side * ln
            b *= 0.5
    return out, pad


def paste_in_water(cv: Cv, img, cx, wl, seed, cut=4, refl=None, **kw):
    """把一根石柱 / 一块石头立进水里：图的最下 cut 行（柱脚那圈外撇）沉到水下，接 water_foot。cx = 中心，wl = 水线。
    返回 (ox, oy)：原图左上角在 cv 里的位置。"""
    lw = img.shape[0] - cut
    out, pad = water_foot(img, lw, seed, refl=MID_REFL_END - wl if refl is None else refl, **kw)
    ox, oy = int(cx - img.shape[1] // 2), int(wl - lw)
    cv.paste(out, ox - pad, oy)
    return ox, oy


def rock_dwelling(cv: Cv, x, seed, h, w, wins, kind="hoodoo"):
    """河里一块凿了窗的石头（中景，比近处淡一档）：几扇小窗透暖光，一扇门洞贴着水，门口一块踏脚石。"""
    img = stone_pillar(w, h, seed, STONE_FAR, crown=[B(.11, .02, 256), B(.14, .022, 250)], kind=kind)
    c = Cv(img.shape[1] + 8, img.shape[0])           # 先画在自己的小画布上（两边各留 4 给门口的踏脚石），再整块立进水里
    c.paste(img, 4, 0)
    oy = MID_FOOT - (img.shape[0] - 4)               # 小画布第 0 行在中景里的 y（paste_in_water 默认沉 4 行）
    for (dy, lit) in wins:
        y = MID_WL - dy - oy
        r = rows_of(img, 4, 0, y)
        if r is None:
            continue
        cx_ = (r[0] + r[1]) // 2
        c.rect(cx_ - 1, y, cx_ + 2, y + 3, WARM[2] if lit else B(.07, .02, 262))
        c.px(cx_ - 1, y, WARM[1] if lit else DARK)
    r = rows_of(img, 4, 0, MID_WL - 6 - oy)
    if r:
        cx_ = (r[0] + r[1]) // 2 + 2
        c.rect(cx_ - 2, MID_WL - 7 - oy, cx_ + 2, MID_WL - oy, B(.05, .02, 264))
        c.hline(cx_ - 4, cx_ + 4, MID_WL - oy, STONE_FAR[3])
    paste_in_water(cv, c.a, x, MID_FOOT, seed)


def stone_head(cv: Cv, x, wl):
    """（第四版不用了：作者说和水底的石头人头重复。水上换成 lantern_statue。）"""
    a = np.array(Image.open(ROOT / "art" / "underwater" / "head.png").convert("RGBA"))
    sub = a[:, 260:440]
    m = sub[..., 3] > 0
    ys, xs = np.nonzero(m)
    sub = sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    sub = night(sub, 0.82)
    keep = int(sub.shape[0] * 0.62)
    sub = sub[:keep].copy()
    ox = int(x - sub.shape[1] // 2)
    cv.paste(sub, ox, wl - keep + 1)
    return ox, sub


def lantern_statue(cv: Cv, x, wl, seed=3150, refl_to=None):
    """提灯人：半截泡在河里的石雕人像，披着兜帽斗篷、低着头，两手在胸前捧着一盏真点着的小灯（住户给它点的）。
    画法照 xiao-oscar 的帽兜人形（oscarkit.paint.light_planes：一个光向、大块亮面暗面、斜的衣褶楔形 + 亮棱），
    颜色换成石头；月光从右上打在肩和兜帽上，灯从下面把胸前、袖口照暖；石面上苔藓、几道旧水位的刻痕，
    水位线以下更深更湿，水线上一圈涟漪，水下那截被波纹切碎（看得出是立在水里）。x = 中心，wl = 水线。"""
    from oscarkit.paint import light_planes
    Wd, Hd, WLL = 44, 72, 58                          # 本地画布；WLL = 本地的水线
    rng = np.random.default_rng(seed)
    R = expand_pal(STONE, 8)
    img_ = Image.new("1", (Wd, Hd), 0)
    dr = ImageDraw.Draw(img_)
    outline = [(25, 2), (29, 4), (31, 10), (31, 16), (33, 22), (35, 32), (37, 46), (39, 58), (40, 71),
               (5, 71), (6, 58), (8, 44), (10, 32), (12, 24), (15, 20), (13, 16), (14, 10), (18, 4)]
    dr.polygon(outline, fill=1)
    m = np.array(img_, bool)
    body = light_planes(m, R[:8], light=(1.0, -0.8), contrast=0.75, ambient=0.56,
                        folds=[((22, 22), (15, 66), 5), ((28, 24), (27, 66), 4), ((32, 30), (36, 66), 3)],
                        top_dark=0.15, rim=2)
    c = Cv(Wd, Hd)
    c.paste(body, 0, 0)
    # 兜帽开口：顺着帽檐的尖椭圆，最暗；低着头，脸看不见
    for yy in range(11, 23):
        for xx in range(12, 21):
            e = ((xx - 16.0) / 2.6) ** 2 + ((yy - 17.0) / 4.2) ** 2
            if e <= 1 and m[yy, xx]:
                c.px(xx, yy, R[0] if e < 0.6 else R[1])
    # 帽檐受月光的一道（右上来的光打在兜帽顶和右肩）
    for xx in range(17, 31):
        ys = np.nonzero(m[:, xx])[0]
        if len(ys):
            c.px(xx, ys[0], R[8] if xx > 22 else R[6])
    # 袖子：两只手臂从两边收到胸前，捧着灯
    sl = Image.new("1", (Wd, Hd), 0)
    ImageDraw.Draw(sl).polygon([(13, 26), (21, 28), (25, 34), (19, 37), (12, 36), (10, 31)], fill=1)
    sm = np.array(sl, bool)
    sleeve = light_planes(sm, R[:8], light=(1.0, -0.6), contrast=0.6, ambient=0.6)
    c.paste(sleeve, 0, 0)
    for xx in range(13, 22):                          # 袖口下沿被灯照暖
        col = np.nonzero(sm[:, xx])[0]
        if len(col):
            c.px(xx, col[-1], mixc(R[4], WARM[2], 0.6))
    # 灯：铁框、暖的灯芯，挂在两手下面
    lx, ly = 15, 38
    iron = B(.07, .015, 262)
    c.vline(lx + 2, ly - 2, ly, iron)
    c.rect(lx, ly, lx + 5, ly + 1, iron)
    c.rect(lx, ly + 1, lx + 5, ly + 6, WARM[3])
    c.rect(lx + 1, ly + 2, lx + 4, ly + 4, WARM[4])
    c.vline(lx, ly + 1, ly + 6, iron)
    c.vline(lx + 4, ly + 1, ly + 6, mixc(iron, WARM[2], 0.4))
    c.rect(lx, ly + 6, lx + 5, ly + 7, iron)
    glow(c, lx + 2.5, ly + 3, 15)
    # 石面：小色团、几条竖的细裂、苔藓（帽顶、肩上、背光的褶里）
    cn = cluster_noise(Hd, Wd, rng, 2.0)
    for yy, xx in zip(*np.nonzero(m)):
        if yy >= WLL:
            continue
        col = tuple(int(v) for v in c.a[yy, xx, :3])
        lab = to_lab(col)
        if math.hypot(lab[1], lab[2]) > 0.05:          # 灯和暖光不动
            continue
        if cn[yy, xx] > 0.8:
            c.px(xx, yy, mixc(col, R[2], 0.5))
        up_ = yy == 0 or not m[yy - 1, xx]
        if (up_ and cn[yy, xx] > 0.3) or (lab[0] < 0.12 and cn[yy, xx] < 0.08):
            c.px(xx, yy, MOSS[1] if up_ else MOSS[0])
    for (sx, sy, ln) in ((29, 18, 9), (11, 42, 7), (33, 36, 10)):
        for k in range(ln):
            if m[sy + k, sx + (k // 4)]:
                c.px(sx + (k // 4), sy + k, R[1])
    # 旧水位的刻痕：两道横线（一道深一道浅），断断续续；以下的石头更深更湿
    for (ty, cc) in ((47, R[1]), (52, R[2])):
        for xx in range(Wd):
            if m[ty, xx] and _hash01(xx, ty, 2) > 0.25:
                c.px(xx, ty, cc)
                if m[ty - 1, xx]:
                    c.px(xx, ty - 1, mixc(tuple(int(v) for v in c.a[ty - 1, xx, :3]), R[6], 0.35))
    for yy in range(48, WLL):                         # （第五版减轻：太黑的话下半截像一个墩子，倒影也翻不出来）
        for xx in np.nonzero(m[yy])[0]:
            col = tuple(int(v) for v in c.a[yy, xx, :3])
            c.a[yy, xx, :3] = mixc(col, B(.07, .03, 236), 0.12 + 0.015 * (yy - 48))
    # 水线以下：第五版不再画「被波纹切碎的水下那截 + 三行虚线涟漪」（作者说像虚线），换成 water_foot：
    # 一行连续的湿亮水线、石身的暗倒影被水波错开、两边很短很淡的涟漪；第六版倒影不透明、盖到 refl_to 行（默认 MID_REFL_END），挡住后面的月光碎片
    out, pad = water_foot(c.a, WLL, seed, refl=max(4, (refl_to or MID_REFL_END) - wl), lamps=(lx + 2,))
    ox, oy = int(x - Wd // 2), int(wl - WLL)
    cv.paste(out, ox - pad, oy)
    return ox, out[:, pad:pad + Wd]


def wm(xw):
    """主层的 x（晨走到那里、它在屏幕正中时）→ 中景图里的 x。"""
    return int(round((xw - SW / 2) * MID_S + SW / 2))


FAR_BRIDGE = None                # 远处两根石柱之间的细桥（中景坐标 x0, x1, y）：提灯的小人在上面走（river_far_lantern.gd）


def bank_mid():
    """中景：空的那一段（LONE）只有光秃的远石柱，很远处一块石头上一扇小窗（这一段唯一的一点灯）；
    箱子以后：半沉的石头人头（头顶一盏灯）、河里几块凿了小窗的石头、踏脚石；
    市集那头两根远石柱，顶上一座细桥（邮差：很小的一个提灯剪影走过，脚本画）。"""
    global FAR_BRIDGE
    w = int(math.ceil(SW + (W - SW) * MID_S))
    cv = Cv(w, SH)
    # 空的那一段：光秃的远石柱（第七版：420 的 spire、600 的 hoodoo 拿掉了，远近各一层另画，见 bank_far / bank_near）
    mid_pillar(cv, wm(1000), 20, 136, 3122, "twin")
    rock_dwelling(cv, wm(520), 3110, 40, 13, ((20, True),), "stack")
    # 箱子以后：人家
    lantern_statue(cv, wm(1300), MID_FOOT)         # 提灯人：两人一起往人家走的那段（作者：石头人头留给水底）
    for i, (xw, h, wd, wins, kind) in enumerate((
            (1430, 46, 14, ((22, True),), "hoodoo"), (1690, 58, 16, ((20, True), (36, True)), "tower"),
            (1880, 34, 12, ((16, False),), "stack"), (2010, 52, 15, ((24, True),), "hoodoo"))):
        rock_dwelling(cv, wm(xw), 3111 + i, h, wd, wins, kind)
    mid_pillar(cv, wm(1560), 18, 128, 3130, "twin")
    mid_pillar(cv, wm(2300), 16, 120, 3131, "spire")
    # 远处两根光秃的石柱 + 顶上的细桥：空的那一段尽头，很远处一个提灯的小人慢慢走过（唯一会动的一点灯）
    ims = []
    for (xw, h, wd, sd, kind) in ((740, 112, 18, 3140, "tower"), (850, 104, 16, 3141, "stack")):
        img = stone_pillar(wd, h, sd, STONE_FAR, crown=[B(.11, .02, 256), B(.14, .022, 250)], kind=kind)
        ox, oy = paste_in_water(cv, img, wm(xw), MID_FOOT, sd)
        ims.append((img, ox, oy))
    by = MID_WL - 92
    r1 = rows_of(*ims[0], by)
    r2 = rows_of(*ims[1], by)
    x0, x1 = r1[1] + 1, r2[0] - 1
    for x in range(x0, x1 + 1):
        t = (x - x0) / max(1, x1 - x0)
        yy = by + int(round(1.5 * math.sin(math.pi * t)))
        cv.px(x, yy, B(.09, .02, 258))
        if x % 4 == 0:
            cv.px(x, yy - 3, B(.11, .02, 256))
            cv.px(x, yy - 2, B(.11, .02, 256))
    rope_line(cv, x0, by - 4, x1, by - 4, 1.5, B(.12, .02, 254))
    FAR_BRIDGE = (int(x0) + 2, int(x1) - 2, int(by))
    # 石头之间几块露出水面的踏脚石（也接水线和一点倒影；第五版去掉了 reflect_down 那层稀疏的点）
    for xw in (1470, 1740, 1960):
        a = wm(xw)
        for j, xx in enumerate(range(a, a + 22, 7)):
            st = Cv(5, 3)
            st.rect(0, 0, 5, 3, STONE_FAR[2])
            st.hline(0, 5, 0, STONE_FAR[4])
            st.px(4, 0, STONE_FAR[3])
            st.px(0, 0, STONE_FAR[3])
            paste_in_water(cv, st.a, xx + 2, MID_FOOT, 3170 + xw + j, cut=1, pad=6, light=0.6)
    return cv


def mid_pillar(cv: Cv, x, w, h, seed, kind):
    """中景一根光秃的远石柱，立在水里（第五版：柱脚接水线和倒影，不再浮在远水上）。"""
    img = stone_pillar(w, h, seed, ROCK_FAR, crown=[B(.07, .02, 258), B(.1, .022, 252)], kind=kind)
    return paste_in_water(cv, img, x, MID_FOOT, seed)


# ============================================================ 河岸：远层（scroll 0.3）、近中层（scroll 0.75）
# 第七版（作者 10-30：「后面的石柱全是在一条线上的，这样不就没有视差背景了吗？没有层次感了」，参照森林前后几层错开的树）：
# 中景拆成三层，柱脚的水线跟着深度走——远层高、贴近地平线，细、淡、偏雾蓝，倒影短、往下淡到和水一个色；
# 近中层低、贴着码头，粗、暗、对比强，倒影深。各层倒影都不透明，挡住后面钉在屏幕上的月光碎片，各层挡的那段以不同速度移动。

FAR_S = 0.3
FAR_WL = 172                     # 远层的水线（地平线 151 和中景水线 192 之间）
FAR_FOOT = FAR_WL + 1
NEAR_S = 0.75
NEAR_WL = 200                    # 近中层的水线：码头上沿 206 后面，留出水线和几行倒影看得见
NEAR_FOOT = NEAR_WL + 1
FOG = (21, 36, 54)               # 远层的雾蓝（地平线那条雾 (33,56,76) 和远水 (11,22,38) 之间）


def wx(xw, s):
    """主层的 x（晨走到那里、它在屏幕正中时）→ scroll 为 s 的层图里的 x。"""
    return int(round((xw - SW / 2) * s + SW / 2))


def fogged(img, k, col=FOG):
    """远层：整块往雾蓝里推 k，再把明暗压扁一点（几乎是剪影，受光的右边还留一点亮）。暖色的窗留一半暖。"""
    out = img.copy()
    for y, x in zip(*np.nonzero(img[..., 3])):
        c = tuple(int(v) for v in img[y, x, :3])
        lab = to_lab(c)
        warm_ = math.hypot(lab[1], lab[2]) > 0.05 and lab[2] > 0.02
        out[y, x, :3] = mixc(c, col, k * (0.45 if warm_ else 1.0))
    return out


FAR_PILLARS = (  # (主层 x, 宽, 高, 形, 种子)：疏密不等——空河岸那段一根、一对挨着的、再空一大段
    (372, 9, 66, "spire", 3201), (588, 11, 52, "hoodoo", 3202), (612, 8, 74, "spire", 3203),
    (930, 10, 58, "stack", 3204), (1188, 12, 78, "tower", 3205), (1640, 9, 60, "spire", 3206),
    (1990, 11, 70, "hoodoo", 3207), (2230, 9, 54, "stack", 3208))
FAR_HOMES = ((1240, 12, 40, 3211), (2120, 10, 34, 3212))        # 远处两块有一扇暖窗的石头（人家那段才有）


def bank_far():
    """远层：很远的石柱，几乎是雾里的剪影；水线贴近地平线。"""
    w = int(math.ceil(SW + (W - SW) * FAR_S))
    cv = Cv(w, SH)
    crown = [mixc(B(.07, .02, 258), FOG, 0.5), mixc(B(.1, .022, 252), FOG, 0.5)]
    for (xw, wd, h, kind, sd) in FAR_PILLARS:
        img = fogged(stone_pillar(wd, h, sd, STONE_FAR, crown=crown, kind=kind, moss=0.2), 0.62)
        paste_in_water(cv, img, wx(xw, FAR_S), FAR_FOOT, sd, cut=3, refl=int(h * 0.45), pad=8, light=0.55,
                       wy=FAR_FOOT, depth=0.0)
    for (xw, wd, h, sd) in FAR_HOMES:
        img = stone_pillar(wd, h, sd, STONE_FAR, crown=None, kind="hoodoo", moss=0.2)
        ys = np.nonzero(img[..., 3].any(axis=1))[0]
        wy_ = int(ys[0]) + (img.shape[0] - int(ys[0])) // 3
        r = np.nonzero(img[wy_, :, 3])[0]
        cx_ = (int(r[0]) + int(r[-1])) // 2
        img[wy_:wy_ + 2, cx_:cx_ + 1, :3] = WARM[2]
        img[wy_, cx_, :3] = WARM[1]
        img = fogged(img, 0.6)
        paste_in_water(cv, img, wx(xw, FAR_S), FAR_FOOT, sd, cut=3, refl=int(h * 0.45), pad=8, light=0.55,
                       wy=FAR_FOOT, depth=0.0)
    return cv


NEAR_PILLARS = (  # (主层 x, 宽, 高, 形, 断, 种子)：原来主层贴着码头的两根（470、690）挪到这里；台阶后一根、浅滩后一根
    (452, 30, 158, "hoodoo", False, 3301), (706, 22, 122, "spire", True, 3302),
    (1128, 26, 168, "tower", False, 3303), (1236, 18, 96, "stack", True, 3304))


def moon_rim(img, seed, dark=0.35, hi=None, mid_=None):
    """近处的石头对比更强：右边（月光那边）贴边一像素亮棱、里面一像素半亮，断断续续；左边背光那几列再压暗。"""
    out = img.copy()
    hi, mid_ = hi or B(.27, .03, 248), mid_ or B(.19, .028, 252)
    for y in range(img.shape[0]):
        xs = np.nonzero(img[y, :, 3])[0]
        if len(xs) < 4:
            continue
        a, b = int(xs[0]), int(xs[-1])
        c = tuple(int(v) for v in img[y, b, :3])
        if _hash01(y // 3, 1, seed) > 0.18:
            out[y, b, :3] = mixc(c, hi, 0.75)
            out[y, b - 1, :3] = mixc(tuple(int(v) for v in img[y, b - 1, :3]), mid_, 0.45)
        for k in range(min(3, (b - a) // 4)):
            out[y, a + k, :3] = mixc(tuple(int(v) for v in img[y, a + k, :3]), (2, 4, 12), dark * (1 - k / 3))
    return out


def bank_near():
    """近中层：贴着码头后面的水里，石柱粗、暗、对比强；倒影深，盖到码头上沿最低处（台阶、浅滩那里看得见）。"""
    w = int(math.ceil(SW + (W - SW) * NEAR_S))
    cv = Cv(w, SH)
    for (xw, wd, h, kind, broken, sd) in NEAR_PILLARS:
        img = moon_rim(stone_pillar(wd, h, sd, ROCK, crown=[B(.06, .02, 260), B(.085, .022, 254)], kind=kind,
                                    broken=broken), sd)
        paste_in_water(cv, img, wx(xw, NEAR_S), NEAR_FOOT, sd, refl=MID_REFL_END + 1 - NEAR_FOOT, pad=12,
                       wy=NEAR_FOOT, depth=1.0)
    return cv


def reflect_down(cv: Cv, wl, length, seed, x_range=None):
    """wl 以上的东西在水线下翻一个很淡、碎的倒影（只有亮窗、灯翻成暖色碎点，别的翻成比水略深的蓝）。"""
    rng = np.random.default_rng(seed)
    x0, x1 = x_range or (0, cv.w)
    for d in range(1, length + 1):
        y = wl + d
        src = wl - d
        if y >= cv.h or src < 0:
            break
        for x in range(x0, x1):
            if cv.a[src, x, 3] == 0 or cv.a[y, x, 3]:
                continue
            if rng.random() < 0.35 + 0.05 * d:
                continue
            c = tuple(int(v) for v in cv.a[src, x, :3])
            lab = to_lab(c)
            warm = math.hypot(lab[1], lab[2]) > 0.05 and lab[2] > 0.02
            if warm:
                cv.px(x + int(rng.integers(-1, 2)), y, WARM_REF[0] if d > 3 else WARM_REF[1])
            elif d < length * 0.6 and (x + d) % 3 == 0:
                cv.px(x, y, B(.12, .025, 256))


# ============================================================ 河岸：主层

def quay(cv: Cv, rng):
    """晨走的岸（第四版：作者说晨像浮着——地面要看得出是一块有厚度的路面）：
    最上面 3 行是朝上的路面（被月光照着，最亮；条石的接缝、几块磨亮的），往下是朝前的侧面（大块条石 / 卵石，暗），
    贴着水面一道暗部（AO）和一行湿亮；卵石滩是一颗颗圆石头（亮的顶 + 暗的底），不是噪点。"""
    P = expand_pal(ra.bramp(6, .075, .34, 260, 240))   # 路面比石头、比水亮：顶面能看清是地
    cn = cluster_noise(SH, W, rng, 2.2)
    for x in range(W):
        top = gy(x)
        beach = x < 330 or SHALLOW[0] - 60 < x < SHALLOW[1] + 12 or INLET[0] - 6 < x < INLET[1] + 6
        for y in range(top, SH):
            d = y - top
            if beach:
                # 卵石：按格子摆一颗颗扁圆的石头，石头顶亮、底暗，石头之间是暗缝
                row = d // 3
                off = (row * 5) % 7
                cell = (x + off) // 5
                cx_ = cell * 5 - off + 2.5
                r = 2.2 + 0.8 * _hash01(cell, row, 11)
                inside = abs(x + 0.5 - cx_) < r
                yy = (y - top) % 3
                if not inside:
                    k = 1
                elif yy == 0:
                    k = 6 if d < 3 else 4
                elif yy == 1:
                    k = 5 if d < 3 else 3
                else:
                    k = 3 if d < 3 else 2
                if d >= 3:
                    k = max(1, k - 1)
            else:
                if d < 3:                              # 路面（朝上）
                    seam = (x + (7 if d else 0)) % 23 == 0
                    k = 4 if seam else (7 if d == 0 else (6 if cn[y, x] > 0.45 else 5))
                    if d == 2:
                        k -= 1
                else:                                  # 侧面（朝前）：大块条石
                    dd = d - 3
                    rowb = dd // 6
                    offb = (rowb * 11) % 19
                    edge = dd % 6 == 0 or (x + offb) % 19 == 0
                    k = 1 if edge else (3 if dd < 2 else 2)
                    if not edge and cn[y, x] > 0.72:
                        k += 1
                    if dd == 1 and not edge:
                        k = 1                          # 路面边下面一道影子
            if WL - 3 <= y < WL:
                k = max(0, k - 2)                      # 贴着水面的暗部
            cv.px(x, y, P[min(8, max(0, k))])
        if beach:
            cv.px(x, top, P[7] if _hash01(x, 0, 5) > 0.3 else P[5])
        else:
            cv.px(x, top, P[8] if (x * 13) % 17 < 3 else P[7])    # 路面最外沿一道冷亮边
        if WL - 1 < SH and _hash01(x // 3, 1, 9) > 0.6:
            cv.px(x, WL - 1, B(.24, .03, 238))         # 水线上一行湿亮


def steps(cv: Cv):
    """台阶：码头左边一级级往下到水边的平台（地面 215），平台右边再一级级上来。每一级的踏面就踩在 ground 折线上
    （差不到 1 像素），踏面一行受光、立面暗；平台边一个系船的铁环。（第四版：以前是横跨整个平台的几条带子，晨在平台上像陷进去。）"""
    P = expand_pal(ra.bramp(6, .075, .34, 260, 240))
    treads = [(STEPS_X, STEPS_X + 13), (STEPS_X + 13, STEPS_X + 26), (STEPS_X + 26, STEPS_X + 38),
              (STEPS_X + 88, STEPS_X + 101), (STEPS_X + 101, STEPS_X + 114), (STEPS_X + 114, STEPS_X + 128)]
    for (x0, x1) in treads:
        ty = gy((x0 + x1) // 2)
        for x in range(x0, x1):
            for y in range(ty, WL):
                d = y - ty
                cv.px(x, y, P[7] if d == 0 else (P[5] if d == 1 else (P[1] if d == 2 else P[2])))
        for y in range(ty + 1, WL):                    # 每一级的侧边一道暗缝
            cv.px(x0, y, P[1])
    px0, px1 = STEPS_X + 38, STEPS_X + 88
    for x in range(px0, px1):                          # 平台：两块大石板
        cv.px(x, 215, P[8] if (x * 7) % 11 < 2 else P[7])
        cv.px(x, 216, P[5] if x != px0 + 25 else P[2])
    d = STEPS_X - 572
    for (xx, yy) in ((629, 217), (630, 216), (631, 217)):
        cv.px(xx + d, yy, B(.3, .02, 246))


def underwater_old_floor(cv: Cv, rng):
    """妮芙家下面泡在水里的旧一层：旧墙、旧门、旧门牌（和现在门边那块同一个 x、同样的字迹）。
    几扇泡水的窗（窗框间有小鱼）。"""
    old = ra.bramp(4, .09, .2, 252, 240)
    h0 = HOME[0]
    x0, x1 = h0 + 4, HOME[1] - 4
    shade_box(cv, x0, WL + 1, x1, SH, old, lit_t=False, seed=4101)
    for y in range(WL + 4, SH, 6):
        for x in range(x0, x1):
            if (x + (y // 6) * 9) % 18 == 0:
                cv.vline(x, y, y + 6, old[0])
        cv.hline(x0, x1, y, old[0])
    # 旧门
    cv.rect(h0 + 31, WL + 5, h0 + 55, SH, B(.05, .02, 262))
    cv.rect(h0 + 33, WL + 7, h0 + 53, SH, B(.08, .025, 248))
    for k in range(h0 + 36, h0 + 53, 4):
        cv.vline(k, WL + 7, SH, B(.06, .02, 252))
    cv.rect(h0 + 29, WL + 3, h0 + 57, WL + 5, old[2])
    # 旧门牌（和新门牌同一个 x）
    plate_x = h0 + HOUSE_PLATE[0]
    cv.rect(plate_x, WL + 12, plate_x + 11, WL + 19, B(.2, .03, 220))
    cv.hline(plate_x + 2, plate_x + 9, WL + 14, B(.32, .03, 210))
    cv.hline(plate_x + 2, plate_x + 7, WL + 16, B(.32, .03, 210))
    # 泡水的窗，窗框间的小鱼
    for wx in (h0 + 140, h0 + 260, h0 + 350):
        cv.rect(wx, WL + 10, wx + 18, WL + 30, B(.05, .02, 262))
        cv.rect(wx + 1, WL + 11, wx + 17, WL + 29, B(.1, .03, 236))
        cv.vline(wx + 9, WL + 11, WL + 29, B(.05, .02, 262))
        cv.hline(wx + 1, wx + 17, WL + 20, B(.05, .02, 262))
    for (fx, fy, d) in ((146, WL + 15, 1), (266, WL + 24, -1), (354, WL + 14, 1), (190, WL + 30, -1)):
        fish(cv, h0 + fx, fy, d)


def fish(cv: Cv, x, y, d=1):
    c = B(.34, .03, 214)
    for k in range(4):
        cv.px(x + k * d, y, c)
    cv.px(x + 4 * d, y - 1, c)
    cv.px(x + 4 * d, y + 1, c)
    cv.px(x + d, y - 1, B(.42, .03, 210))


def submerged_paving(cv: Cv, x0, x1):
    """浅滩下面整齐的街砖（原文 80：看得见水下整齐的街砖），比别处的水底亮一档。"""
    for y in range(WL + 2, SH):
        for x in range(x0, x1):
            if cv.a[y, x, 3] == 0:
                continue
            edge = (y - WL) % 6 == 0 or (x + ((y - WL) // 6 % 2) * 6) % 12 == 0
            cv.px(x, y, ROCK[1] if edge else ROCK[3])


def underwater_dim(cv: Cv, y0, x_ranges=None, keep=None):
    """水面以下压暗、往青蓝推（water 层再半透明盖一层）。"""
    for y in range(y0, SH):
        t = min(1.0, (y - y0) / 40)
        row = cv.a[y]
        for x in range(cv.w):
            if row[x, 3] == 0:
                continue
            if keep is not None and keep[y, x]:
                continue
            c = tuple(int(v) for v in row[x, :3])
            row[x, :3] = mixc(c, B(.07, .03, 236), 0.25 + 0.4 * t)


def towers(cv: Cv):
    """作者喜欢的「打洞的石柱房」：两根石柱，柱身上凿出门洞、几扇小窗透暖光，门口伸出一块凿出来的石台；
    左边那根柱脚也凿了一扇门（门口一道光落在码头上）。没有桥、没有绳梯（第三版：邮差和绳桥去掉了）。"""
    imgs = []
    for (x, w, h, seed, kind) in ((TOWERS[0], 30, 178, 4201, "tower"), (TOWERS[1], 26, 172, 4202, "stack")):
        img = stone_pillar(w, h, seed, STONE, crown=[B(.07, .02, 258), B(.1, .022, 252)], kind=kind)
        ox, oy = int(x - img.shape[1] // 2), int(G - 1 - img.shape[0] + 1)
        cv.paste(img, ox, oy)
        imgs.append((img, ox, oy))
    (i1, o1x, o1y), (i2, o2x, o2y) = imgs
    r1 = rows_of(i1, o1x, o1y, 60)
    r2 = rows_of(i2, o2x, o2y, 60)
    for (a, b) in ((r1[1] - 6, r1[1] + 6), (r2[0] - 6, r2[0] + 6)):     # 门口的石台
        cv.rect(a, 68, b, 72, STONE[2])
        cv.hline(a, b, 68, STONE[5])
        cv.hline(a, b, 72, DARK)
        cv.vline(b - 1, 68, 72, STONE[4])
    carve(cv, r1[1] - 13, 54, 7, 14, "arch", True, True)
    carve(cv, (r1[0] + r1[1]) // 2 - 3, 34, 5, 7, "arch", True)
    carve(cv, (r1[0] + r1[1]) // 2 - 1, 104, 5, 6, "round", False)
    carve(cv, r2[0] + 5, 55, 7, 13, "arch", True, True)
    carve(cv, (r2[0] + r2[1]) // 2 + 1, 38, 5, 7, "arch", True)
    r2b = rows_of(i2, o2x, o2y, 120)
    carve(cv, (r2b[0] + r2b[1]) // 2, 120, 5, 7, "arch", True)
    lantern(cv, r1[1] + 4, 58, "hang")
    lamp_bridge(cv, r1[1] + 6, r2[0] - 6, 67)
    for x_ in (r1[1] - 10, (r1[0] + r1[1]) // 2, r2[0] + 8, (r2[0] + r2[1]) // 2 + 3, (r2b[0] + r2b[1]) // 2 + 2):
        LIGHTS_X.append((x_, 1))
    # 柱脚的门（码头这一层的人家）
    rb = rows_of(i1, o1x, o1y, G - 10)
    dx = (rb[0] + rb[1]) // 2 - 4
    carve(cv, dx, G - 22, 9, 22, "arch", True, True, glow_r=20)
    LIGHTS_X.append((dx + 4, 2))
    return [(dx, 9)]


def lamp_bridge(cv: Cv, x0, x1, y):
    """两根石柱的石台之间一座窄绳桥（作者点赞的那屏有：桥下挂着几盏小灯）。木板一块块长短不一、有一两块缺了，
    两根绳栏杆往下垂，绳子上挂两三盏很小的灯。上面不走人（邮差去掉了）。"""
    sag = max(2, (x1 - x0) // 14)
    for x in range(x0, x1 + 1):
        t = (x - x0) / max(1, x1 - x0)
        yy = y + int(round(sag * math.sin(math.pi * t)))
        if _hash01(x // 3, 0, 21) > 0.08:              # 木板（偶尔缺一块）
            cv.px(x, yy + 1, WOOD[3] if (x // 3) % 2 else WOOD[2])
            cv.px(x, yy + 2, WOOD[0])
        if x % 5 == 0:
            cv.vline(x, yy - 6, yy + 1, WOOD[1])
    rope_line(cv, x0, y - 6, x1, y - 6, sag + 1, WOOD[3])
    rope_line(cv, x0, y + 3, x1, y + 3, sag + 3, B(.18, .03, 70))          # 下面一根挂灯的绳
    n = max(2, (x1 - x0) // 22)
    for i in range(n):
        t = (i + 0.5) / n
        lx = int(x0 + (x1 - x0) * t)
        ly = y + 3 + int(round((sag + 3) * math.sin(math.pi * t)))
        cv.vline(lx, ly, ly + 2, B(.1, .02, 258))
        cv.px(lx, ly + 3, WARM[3])
        cv.px(lx, ly + 4, WARM[2])
        glow(cv, lx, ly + 3, 5)
        LIGHTS_X.append((lx, 1))


def stone_lantern(cv: Cv, x, base):
    """石灯笼（路灯）：方座、细柱、灯室（暖光从小窗透出来）、宽顶。"""
    st = ROCK
    cv.rect(x - 6, base - 4, x + 7, base, st[1])
    cv.hline(x - 6, x + 7, base - 4, st[3])
    cv.rect(x - 2, base - 16, x + 3, base - 4, st[1])
    cv.vline(x + 2, base - 16, base - 4, st[3])
    cv.rect(x - 5, base - 25, x + 6, base - 16, st[1])
    cv.rect(x - 3, base - 23, x + 4, base - 18, WARM[3])
    cv.px(x, base - 21, WARM[4])
    cv.px(x + 1, base - 21, WARM[4])
    cv.poly([(x - 9, base - 25), (x, base - 31), (x + 10, base - 25), (x + 10, base - 24), (x - 9, base - 24)], st[1])
    cv.line([(x, base - 31), (x + 10, base - 25)], st[3])
    cv.px(x, base - 32, st[2])
    glow(cv, x, base - 21, 12)
    LIGHTS_X.append((x, 1))


def mooring_post(cv: Cv, x, base):
    """木桩（原文 78，阿汀撑船靠过来的地方）：粗的一根，顶上缠着绳，下半截泡进水里。"""
    cv.rect(x - 2, base - 22, x + 3, SH, WOOD[1])
    cv.vline(x + 2, base - 22, SH, WOOD[3])
    cv.vline(x - 2, base - 22, SH, WOOD[0])
    cv.hline(x - 2, x + 3, base - 22, WOOD[4])
    for y in range(base - 18, base - 12, 2):
        cv.hline(x - 3, x + 4, y, B(.3, .03, 70))
    cv.line([(x + 3, base - 14), (x + 12, base + 6)], B(.24, .03, 70))


def bakery(cv: Cv):
    """面包店：一块圆鼓的巨石里凿出来的（和石柱同一种质感），下面一扇凿出来的宽窗（架子上一排面包的剪影）、一扇门，
    上面一扇小窗下伸出一块长木板，搭到对面浅水里的修补摊——摊子在一块平顶的大石头上。返回门（x, w）。"""
    x0, y0 = boulder_house(cv, BAKERY, G, 86, 64, 4301, pipe=62,
                           openings=(("rect", 8, 7, 22, 13, True, False), ("arch", 40, 0, 10, 20, True, True),
                                     ("arch", 64, 30, 7, 9, True, False), ("round", 22, 36, 6, 6, False, False)))
    for k in range(4):                                   # 窗里一排面包：暗暖的圆
        cv.rect(x0 + 11 + k * 4, G - 13, x0 + 14 + k * 4, G - 11, DEEP[1])
    sx = x0 + 6                                          # 招牌：铁架子挑出来一块木板，上面一道暖色的字
    cv.hline(sx, sx + 12, G - 34, B(.1, .015, 250))
    cv.rect(sx + 1, G - 33, sx + 19, G - 27, WOOD[1])
    cv.hline(sx + 1, sx + 19, G - 33, WOOD[3])
    cv.hline(sx + 4, sx + 16, G - 30, WARM[1])
    # 伸出去的木板（上面那扇窗下）→ 修补摊
    for x in range(x0 + 70, STALL[0] + 6):
        cv.px(x, G - 30, WOOD[3])
        cv.px(x, G - 29, WOOD[1])
    # 修补摊：浅水里一块平顶大石头，上面一个布棚、挂着工具、一盏灯
    rng = np.random.default_rng(4302)
    sx0, sx1 = STALL
    m = np.zeros((SH - (G - 30), sx1 - sx0), bool)
    for x in range(sx1 - sx0):
        u = abs((x + .5 - (sx1 - sx0) / 2) / ((sx1 - sx0) / 2))
        t = 0 if u < 0.8 else int((u - 0.8) * 20)
        m[t:, x] = True
    cv.paste(stone_shade(m, rng, STONE, facet_w=10, water_row=WL - (G - 30)), sx0, G - 30)
    cv.vline(sx0 + 3, G - 56, G - 30, WOOD[1])
    cv.vline(sx1 - 4, G - 50, G - 30, WOOD[1])
    cv.poly([(sx0, G - 56), (sx1, G - 50), (sx1, G - 47), (sx0, G - 53)], B(.13, .03, 230))
    cv.line([(sx0, G - 56), (sx1, G - 50)], B(.24, .03, 222))
    for (tx, ln) in ((sx0 + 10, 6), (sx0 + 15, 4), (sx0 + 32, 7)):
        cv.vline(tx, G - 46, G - 46 + ln, B(.22, .015, 240))
    cv.rect(sx0 + 38, G - 36, sx0 + 44, G - 30, WOOD[1])
    cv.hline(sx0 + 38, sx0 + 44, G - 36, WOOD[3])
    lantern(cv, sx0 + 22, G - 43, "hang", r=10)
    LIGHTS_X.append((sx0 + 22, 1))
    return [(x0 + 40, 10)]


def boat(cv: Cv, x0, wl, tie_x):
    """系在浅水边的小船（原文 83、146）：两头翘的木壳，船头一个空挂钩（铃原来挂这），一根缆绳拴到修补摊的桩上。"""
    x1 = x0 + 44
    for x in range(x0, x1):
        t = (x - x0) / (x1 - x0)
        top = wl - 4 - int(round(3 * (abs(t - 0.5) * 2) ** 2.2))
        for y in range(top, wl + 2):
            k = 1 if y > top else 3
            cv.px(x, y, WOOD[k])
    cv.hline(x0 + 3, x1 - 3, wl - 3, WOOD[0])
    cv.vline(x1 - 3, wl - 14, wl - 5, WOOD[2])
    cv.hline(x1 - 3, x1 + 1, wl - 14, WOOD[2])
    cv.px(x1, wl - 13, B(.3, .02, 246))
    rope_line(cv, x1 - 2, wl - 5, tie_x, G - 10, 2, B(.22, .03, 70))


def market_gate(cv: Cv):
    """右端：一根粗大的石柱（上面是高处市集），柱身上凿了几扇住人的窗；柱脚凿进去一道拱门洞（STAIR），
    洞里几级石阶往上拐进黑里，洞顶挂一盏灯（第三版：不再在外面画之字形的楼梯）。
    最右一块岩壁上一道窄巷口往南桥，深处一点暖灯。"""
    cx = STAIR + 10
    img = stone_pillar(72, 220, 4401, ROCK, crown=[B(.07, .02, 258), B(.1, .022, 252)], kind="tower")
    ox, oy = cx - img.shape[1] // 2, G - img.shape[0] + 1
    cv.paste(img, ox, oy)
    for (y, side, lit) in ((48, 1, True), (96, -1, True), (128, 1, False), (150, -1, True)):
        r = rows_of(img, ox, oy, y)
        if r:
            x = r[1] - 12 if side > 0 else r[0] + 6
            carve(cv, x, y, 5, 7, "arch", lit, pal=ROCK)
            if lit:
                LIGHTS_X.append((x + 2, 1))
    # 拱门洞
    gw, gh = 22, 44
    gx = STAIR - gw // 2
    st = ra.bramp(5, .1, .3, 258, 244)
    m = opening_mask(gw, gh, "arch")
    for yy in range(gh):
        for xx in range(gw):
            if m[yy, xx]:
                cv.px(gx + xx, G - gh + 1 + yy, B(.035, .02, 266))
    for i in range(7):                                    # 洞里的石阶：从左下往右上，越往里越暗
        sy = G - 1 - i * 4
        sx0 = gx + 3 + i * 2
        c_top = WARM[2] if i < 3 else (WARM[1] if i < 5 else WARM[0])
        cv.hline(sx0, gx + gw - 2, sy - 3, c_top)
        cv.rect(sx0, sy - 2, gx + gw - 2, sy + 1, st[0] if i > 2 else st[1])
    lantern(cv, STAIR + 2, G - gh + 9, "hang", r=12)
    LIGHTS_X.append((STAIR + 2, 2))
    for yy in range(gh):                                  # 门洞的石唇
        row = np.nonzero(m[yy])[0]
        if len(row):
            cv.px(gx + row[-1] + 1, G - gh + 1 + yy, st[4])
            cv.px(gx + row[0] - 1, G - gh + 1 + yy, st[1])
    # 往南桥的窄巷：最右一块岩壁，拱形的口子，里面暗，深处一点暖灯
    img2 = stone_pillar(40, 150, 4402, ROCK, crown=None, kind="stack")
    cv.paste(img2, W + 4 - img2.shape[1] // 2, G - img2.shape[0] + 1)
    for y in range(G - 44, G):
        half = 9 if y > G - 34 else int(math.sqrt(max(0, 81 - (G - 34 - y) ** 2 * 1.2)))
        for x in range(SOUTH - half, SOUTH + half + 1):
            cv.px(x, y, B(.035, .02, 266))
        cv.px(SOUTH - half - 1, y, st[1])
        cv.px(SOUTH + half + 1, y, st[4])
    cv.rect(SOUTH - 2, G - 22, SOUTH + 1, G - 19, WARM[2])
    cv.px(SOUTH - 1, G - 21, WARM[3])
    lantern(cv, SOUTH - 14, G - 40, "hang", r=8)
    LIGHTS_X.append((SOUTH - 14, 1))
    return [(gx + 3, gw - 6)]


def plane_beach(cv: Cv, rng):
    """左边：窄水道（飞行最后一格那面墙：一根大石柱一直下到水里）、卵石滩上一棵垂枝树、几块礁石。"""
    img = pillar_at(cv, 18, SH + 20, 46, 290, 4501, kind="tower", crown=True)
    weeping(cv, 268, gy(268), 64, 52, 4502)
    weeping(cv, 112, gy(112) - 1, 30, 20, 4503, kind="young")


def lone_stretch(cv: Cv):
    """空的那一段（LONE）：晨一个人走。只有石柱、垂枝树、几块礁石和芦苇；没有灯、没有人家、没有能点的东西。
    （第七版：原来贴着码头的两根石柱 470、690 挪到近中层 bank_near，不再和中景排成一线。）"""
    weeping(cv, 420, G, 72, 60, 4513)
    weeping(cv, 610, G, 44, 34, 4514, kind="young")
    weeping(cv, 780, G, 58, 46, 4515)
    rng = np.random.default_rng(4516)
    for (x, w, h) in ((520, 14, 6), (566, 9, 4), (730, 12, 5)):          # 水里露头的礁石
        m = blob_mask(w, h, rng, p=2.2)
        cv.paste(stone_shade(m, rng, ROCK, facet_w=6, ledges=0, moss=0.3), x, WL - h + 2)


def reeds_near(cv: Cv, x, base, h, seed, k=6):
    pal = [B(.06, .02, 262), B(.09, .022, 256), B(.13, .024, 250)]
    tmp = ra.Layer(cv.w, cv.h)
    ra.reeds(tmp, x, base, h, seed, pal, k=k)
    cv.paste(tmp.a, 0, 0)


def bank_main():
    LIGHTS_X.clear()
    rng = np.random.default_rng(4001)
    cv = Cv(W, SH)
    plane_beach(cv, rng)
    lone_stretch(cv)
    doors = towers(cv)
    doors += market_gate(cv)
    doors += bakery(cv)
    doors.append((HOME[0] + 40, 20))                  # 妮芙家的门（门在 house 的 front 上，门口的光落在码头上）
    LIGHTS_X.append((HOME[0] + 48, 2))               # 房子本身（三层的巨石屋）是 tools/river_home_rooms_art.py 画的，这里只管门口
    # 路灯：稀疏的几盏（空的那一段一盏都没有）——箱子那里一盏、妮芙家门口前一盏、面包店前一盏
    stone_lantern(cv, STEPS_X - 26, G)
    stone_lantern(cv, HOME[0] - 22, G)
    stone_lantern(cv, BAKERY - 64, G)
    # 地面、台阶
    quay(cv, rng)
    steps(cv)
    for (dx, dw) in doors:
        door_spill(cv, dx, dw, G + 1)
    mooring_post(cv, POST, G)
    reeds_near(cv, 152, gy(152), 18, 4701)
    reeds_near(cv, 326, gy(326), 14, 4702, k=4)
    reeds_near(cv, 560, G, 12, 4704, k=4)
    reeds_near(cv, SHALLOW[1] + 4, 213, 16, 4703, k=5)
    reeds_near(cv, INLET[1] + 2, 213, 12, 4705, k=4)
    # 水下：旧一层、浅滩的街砖、压暗
    underwater_old_floor(cv, rng)
    submerged_paving(cv, SHALLOW[0] - 50, SHALLOW[1] + 10)
    underwater_dim(cv, WL + 1)
    boat(cv, INLET[0] - 2, WL - 1, STALL[0] + 22)
    return cv


# ============================================================ 河岸：水、水纹、前景

def water_front():
    """前面那片水（water 层，引擎半透明叠在主层前面）：越深越暗；水面一行亮一点。"""
    cv = Cv(W, SH - WL)
    for y in range(cv.h):
        t = y / max(1, cv.h - 1)
        L = .2 - .12 * t
        q = round(L / 0.02) * 0.02
        cv.hline(0, W, y, B(q, .03, 250))
    cv.hline(0, W, 0, B(.3, .03, 246))
    return cv


def water_ripples():
    """水面会闪的纹（river_water.gdshader palette_mode=false）：银的短横 + 灯在水里的暖影（竖着一串碎段）。"""
    rng = np.random.default_rng(4801)
    h = 30
    cv = Cv(W, h)
    for r in range(h):
        if r % (1 + r // 8) and r > 2:
            continue
        x = rng.uniform(0, 20)
        while x < W:
            ln = 2 + int(rng.integers(0, 4 + r // 3))
            if rng.random() < (0.42 if r < 4 else 0.22) - 0.006 * r:
                cv.hline(int(x), int(x) + ln, r, SILVER[2] if r < 3 else (SILVER[1] if r < 12 else SILVER[0]))
            x += ln + rng.integers(5, 16 + r)
    for (lx, k) in LIGHTS_X:
        for r in range(1, 22 + 6 * k, 2):
            if rng.random() < 0.25:
                continue
            ln = 1 + int(rng.integers(1, 3 + r // 6))
            off = int(rng.integers(-2 - r // 6, 3 + r // 6))
            cv.hline(lx + off - ln // 2, lx + off + ln - ln // 2, r, WARM_REF[1] if r < 10 else WARM_REF[0])
    return cv


FRONT_S = 1.3


def bank_front():
    w = int(math.ceil(SW + (W - SW) * FRONT_S))
    cv = Cv(w, SH)
    dark = [B(.035, .02, 266), B(.05, .02, 262), B(.07, .022, 258)]
    rng = np.random.default_rng(4901)
    # 底边几丛近黑的芦苇 / 宽叶（不挡晨：都很矮，几丛高的在两段之间）
    def fx(xw):                                      # 主层 x（在屏幕正中时）→ 前景图里的 x
        return int(round((xw - SW / 2) * FRONT_S + SW / 2))
    for x, h, k, nb, sd in ((fx(110), 40, 3, 7, 1), (fx(520), 30, 2, 5, 2), (fx(760), 50, 3, 8, 3),
                            (fx(1330), 34, 2, 6, 4), (fx(1850), 44, 3, 8, 5), (fx(1180), 22, 2, 4, 6),
                            (fx(2150), 30, 2, 5, 7)):
        tmp = ra.Layer(w, SH)
        ra.reeds(tmp, x, SH - 1 + 6, h, 4910 + sd, dark, k=k)
        for j in range(nb * 2):
            f = rng.random() ** 1.6
            off = rng.normal(0, 6 + 3 * (1 - f))
            ra.blade(tmp, x + off, SH + 4, h * (0.3 + 0.6 * f), off / 14 + rng.uniform(-0.4, 0.4),
                     int(rng.choice([3, 3, 4])), dark)
        cv.paste(tmp.a, 0, 0)
    # 第七版：空河岸那段，码头前面的水里一根近黑的石柱（森林那种最前面一层，顶出画面），晨从它后面走过去一下
    for (xw, wd, h, sd) in FRONT_PILLARS:
        img = stone_pillar(wd, h, sd, ra.bramp(5, .022, .07, 266, 258), crown=None, kind="tower", broken=False,
                           moss=0.0, stains=0.3)
        img = moon_rim(img, sd, dark=0.5, hi=B(.13, .025, 252), mid_=B(.09, .022, 256))
        cv.paste(img, fx(xw) - img.shape[1] // 2, SH + 24 - img.shape[0])
    return cv


FRONT_PILLARS = ((648, 30, 330, 4920),)             # (主层 x, 宽, 高, 种子)：比一屏高，柱顶在画面外


# ============================================================ 物件：借 river_city_art 的形状，换成月夜颜色

def night(a: np.ndarray, dark=0.72, keep_warm=True) -> np.ndarray:
    """把白天的颜色换成月夜：变暗、低饱和的往月光蓝推；本来就暖的（铜、灯、绳）留一点暖。"""
    a = a.copy()
    m = a[..., 3] > 0
    if not m.any():
        return a
    cols, inv = np.unique(a[m][:, :3], axis=0, return_inverse=True)
    lab = srgb_to_oklab(cols.astype(float))
    out = []
    for (L, aa, bb) in lab:
        C_ = math.hypot(aa, bb)
        h = math.degrees(math.atan2(bb, aa)) % 360
        L2 = 0.04 + L * dark
        if keep_warm and C_ > 0.04 and 30 < h < 110:
            c = from_lch(L2, C_ * 0.8, h)
        elif C_ > 0.07:                               # 鲜艳的（尾巴占位）基本不动
            c = from_lch(L * 0.92, C_, h)
        else:
            c = from_lch(L2, 0.018 + C_ * 0.3, 252)
        out.append(tuple(int(v) for v in c))
    new = np.array(out, np.uint8)
    sub = a[m]
    sub[:, :3] = new[inv.reshape(-1)]
    a[m] = sub
    return a


def crates_frames():
    """岸边一排箱子（原文 74），按月夜河岸的画法重画（第三版：作者嫌原来的亮木箱突兀）：
    泡过水的旧木箱，和码头石头一个调子——暗蓝灰，只有上沿、右沿一条月光；一块旧油布搭在后面那只上，一根绳捆着；
    妮芙的标签是几张很小的旧纸片（字是一道细线，不画点，免得像眼睛）。
    帧和尺寸跟旧的一样（76×58，0/1 = 箱子后面露出妮芙的尾巴在动，2 = 没有尾巴）。尾巴归美术组画，这里还是一块占位。"""
    W_, H_ = 76, 44
    wood = [B(.07, .018, 262), B(.095, .02, 258), B(.12, .022, 254), B(.155, .024, 250), B(.2, .026, 246),
            B(.26, .028, 242)]
    paper = B(.3, .018, 90)
    box = Cv(W_, H_)
    for (x0, y0, w, h) in ((2, 20, 24, 24), (26, 24, 22, 20), (48, 18, 26, 26), (8, 6, 20, 14)):
        box.rect(x0, y0, x0 + w, y0 + h, wood[2])
        for yy in range(y0 + 4, y0 + h, 5):                       # 板缝
            box.hline(x0 + 1, x0 + w - 1, yy, wood[1])
        for yy in range(y0, y0 + h):                              # 两根竖的压条
            box.px(x0 + 2, yy, wood[3])
            box.px(x0 + w - 3, yy, wood[1])
        box.hline(x0, x0 + w, y0, wood[5])
        box.hline(x0, x0 + w, y0 + 1, wood[3])
        box.vline(x0 + w - 1, y0, y0 + h, wood[4])
        box.vline(x0, y0, y0 + h, wood[0])
        for yy in range(y0 + h - 4, y0 + h):                      # 下面泡过水：暗一档、发青
            for xx in range(x0 + 1, x0 + w - 1):
                if (xx + yy) % 2 == 0 or yy > y0 + h - 3:
                    box.px(xx, yy, B(.08, .024, 236))
        lx, ly = x0 + w // 2 - 3, y0 + 5
        box.rect(lx, ly, lx + 6, ly + 4, paper)
        box.hline(lx + 1, lx + 5, ly + 2, wood[1])
    # 旧油布：从后面那只箱子上搭下来，几道褶
    tarp = [B(.09, .03, 230), B(.13, .032, 226), B(.18, .03, 222)]
    for x in range(6, 30):
        t = (x - 6) / 24
        top = 5 + int(round(2 * math.sin(t * 3.1)))
        bot = 12 + int(round(5 * t + 2 * math.sin(x / 2.5)))
        for y in range(top, bot):
            k = 2 if y == top else (0 if (x % 5 == 0) else 1)
            box.px(x, y, tarp[k])
    rope_line(box, 2, 24, 26, 26, 1, B(.24, .03, 70))
    rope_line(box, 48, 22, 74, 21, 1, B(.24, .03, 70))
    frames = []
    tail = rca.C(0.62, 0.11, 262)           # 妮芙尾巴的占位（美术组的图来了换掉）
    tail_hi = rca.C(0.74, 0.08, 255)
    for k in range(3):
        cv = Cv(W_, H_ + 14)
        cv.paste(box.a, 0, 14)
        if k == 2:
            frames.append(cv.a)
            continue
        lean = (-2, 2)[k]
        pts = [(40, 40), (44, 40), (45 + lean, 22), (50 + lean * 2, 12), (44 + lean, 14), (38 + lean * 2, 12), (41 + lean, 22)]
        cv.poly(pts, tail)
        cv.line([(42 + lean, 24), (43 + lean, 38)], tail_hi)
        cv.paste(box.a[24:44, 26:48], 26, 38)
        frames.append(cv.a)
    return frames


def float_crate_frames():
    """开场漂在窄水道里的木箱（原文 72，飞行最后一格那只）：斜着半沉，顶面受月光、正面几道板缝、右沿一道亮边，
    吃水那一行一道湿亮的水线，水下那截压暗、被波纹切碎（第四版：作者看着像一个半截黑方框）。"""
    W_, H_, wl = 24, 18, 11
    wood = [B(.07, .018, 262), B(.1, .02, 258), B(.13, .022, 254), B(.17, .024, 250), B(.22, .026, 246),
            B(.3, .028, 240)]
    cv = Cv(W_, H_)
    top = [(3, 4), (16, 1), (21, 3), (8, 7)]          # 顶面（往右上斜）
    cv.poly(top, wood[4])
    cv.line([(3, 4), (16, 1)], wood[5])
    cv.line([(16, 1), (21, 3)], wood[5])
    front = [(3, 4), (8, 7), (8, 17), (3, 15)]         # 左侧面（背光）
    cv.poly(front, wood[1])
    face = [(8, 7), (21, 3), (21, 14), (8, 17)]        # 正面
    cv.poly(face, wood[2])
    for k in (10, 13):                                 # 正面的板缝（顺着斜）
        cv.line([(8, k - 3), (21, k - 7)], wood[0])
    cv.line([(14, 6), (14, 16)], wood[1])
    cv.line([(21, 3), (21, 14)], wood[4])              # 右沿亮边
    cv.rect(10, 8, 14, 10, B(.26, .02, 90))            # 一张泡皱的标签
    for y in range(wl, H_):                            # 水下那截
        for x in range(W_):
            if cv.a[y, x, 3]:
                if _hash01(x // 2, y, 12) < 0.2 + 0.1 * (y - wl) or (y > wl + 3 and y % 2):
                    cv.a[y, x, 3] = 0
                else:
                    cv.a[y, x, :3] = mixc(tuple(int(v) for v in cv.a[y, x, :3]), B(.08, .03, 238), 0.55)
    for x in range(1, W_ - 1):                         # 水线
        if _hash01(x, wl, 13) > 0.3:
            cv.px(x, wl, SILVER[1] if x % 4 else SILVER[2])
    return [cv.a]


def objects():
    """河岸的物件：(id, 帧列表[np], x, y, spec)。y 跟着新的地面 / 水面。"""
    out = []
    pf = [night(f.a, 0.8) for f in rca.plane_frames()]
    out.append(("river_bank_plane", pf, 40, WL + 2 - 96 + 6, {"states": {"default": 0, "beached": 1, "straps_drying": 2,
                                                                          "fixed": 3}}))
    cf = crates_frames()
    out.append(("river_bank_crates", cf, CRATES, G - cf[0].shape[0], {"ms": 200, "states": {"default": 2, "tail": [0, 1],
                                                                                           "tail_still": 2}}))
    bf = [night(f.a, 0.5) for f in rca.box_frames()]       # 金属盒：暗一点，别成水上一块亮方块
    out.append(("river_bank_box", bf, STEPS_X + 68, WL - 12, {"states": {"default": 0, "sunk_shallow": 1}}))
    out.append(("river_bank_crate_float", float_crate_frames(), 18, WL - 11, {"states": {"default": 0}}))
    rp = []                                  # 剧本 prop river_bank_shallow floating：东西漂进浅滩，水面一圈圈的银纹（以前没有图，引擎画占位方块）
    for k in range(3):
        cv = Cv(28, 7)
        for (rx, ry, c) in ((4 + k * 3, 1 + k // 2, SILVER[2 - k]), (9 + k * 3, 2 + k // 2, SILVER[max(0, 1 - k)])):
            for i in range(64):
                t = i / 64 * 2 * math.pi
                x, y = int(round(14 + rx * math.cos(t))), int(round(3 + ry * math.sin(t)))
                if (i // 4) % 2 == 0 and 0 <= y < 7:
                    cv.px(x, y, c)
        rp.append(cv.a)
    rp.append(np.zeros_like(rp[0]))          # default = 空的一帧（不能 hidden：hotspot「水底的街」at 同一个名字，要靠这个物件的框）
    out.append(("river_bank_shallow", rp, SHALLOW[0] + 70 - 14, WL - 3, {"ms": 400,
                                                                          "states": {"default": 3, "floating": [0, 1, 2]}}))
    for i, (sid, kind) in enumerate(rca.SALVAGE.items()):
        fr = [night(f.a, 0.85) for f in rca.salvage_frames(kind)]
        out.append((f"river_bank_salvage_{sid}", fr, DRIFT - 6 + i * 16, WL - 12,
                    {"default": "hidden", "ms": 500,
                     "states": {"float": [0, 1], "sink1": 2, "sink2": 3, "sunk": 4, "shallow": 1}}))
    wk = []
    for k in range(2):                       # V 形水纹：月光银
        cv = Cv(30, 9)
        for i in range(0, 28, 2):
            sp = i // 6 + k
            c = SILVER[2] if i < 12 else SILVER[1]
            cv.px(29 - i, 4 - sp, c)
            cv.px(29 - i, 4 + sp, c)
        wk.append(cv.a)
    out.append(("river_bank_salvage_wake", wk, DRIFT - 36, WL - 4, {"default": "hidden", "ms": 300, "states": {"on": [0, 1]}}))
    return out


# ============================================================ 妮芙家（剖面小屋，学树屋）
# 屋内（家具、标签、柜子、影像机……）是会话 D 的 tools/river_home_art.py 画的，这里借它的函数重画一遍：
# 白天的冷光换成月夜（暗一档、往月光蓝推），桌子上方那盏吊灯点亮（一小圈暖黄，别的地方还是冷的）；窗外换成月下的河。
# 屋后加一根大石柱（像树屋靠着大树：前墙淡掉以后，石柱、屋顶还在，分层清楚）；前墙重画成小屋的立面。
# 图比 D 的高 HDY 像素（上面多出来给石柱），所以 D 的物件 y、地板都 + HDY；x 不变，markers 不变。

HOUSE_PLATE = (66, 0)            # 现在的门牌在图里的 x（旧门牌在水下同一个 x）
HDY = 30                         # 比 D 的图高多少


# ============================================================ 河岸 room.json

# （10-30 作者：远处的水纹太靠上，盖到对岸的岸上了）远岸 shore.png 的岸是一道 151–155 行的暗带（各列底边 154–156），
# 原来 far_ripples 从 151、glints 从 155 开始，又画在 shore 后面，就盖到了岸上。shore 和水纹滚得不一样快，没法逐列对齐，
# 所以水纹整层从岸的最低处以下开始：自己裁一份 art/river/ripples.png（不改原图），头两行稀一点当淡出；月光碎片也挪到岸下。
SHORE_WL = 157                   # 远岸最低的那一行再往下一行：远处的水纹、月光碎片都从这一行开始
FAR_RIPPLES_Y = SHORE_WL
# art/river/water.png 里那几块小礁石（scroll 0.42，比远层近、比中景远）原来水线在 178~186，正好卡在对岸石柱倒影的尾巴上（倒影到 179），
# 看着像石头搁在影子上。整层往下挪 6 行（不改原图）：石身都落到 179 以下，水线 184~192，夹在远层 172 和中景 192 之间。
# 它也要画在远层 mid_far 后面，不然更远的石柱倒影会压住更近的礁石，见 bank_json。
FAR_WATER_DY = 6


def far_ripples_img():
    """art/river/ripples.png（原来贴在 y=151）裁掉 SHORE_WL 以上的行；剩下最上面两行只留一部分（越往上越稀），水纹贴着岸淡出。"""
    a = np.array(Image.open(RIVER / "ripples.png").convert("RGBA"))[SHORE_WL - 151:].copy()
    for r, keep in ((0, 0.35), (1, 0.7)):
        for x in np.nonzero(a[r, :, 3])[0]:
            if _hash01(x // 2, r, 77) > keep:
                a[r, x] = 0
    return a


# ---------------------------------------------------------------- 月光倒影（第九版）
# 作者：「这个月光好像在平移一样，理论上是合理的，但是看起来总觉得有问题」。原来 glints 是 art/river/glints.png 整张钉在屏幕上
# （scroll 0），碎光的样子也钉住了，脚下的水、水纹、石柱都在走，像一张贴纸在水面上滑；而且它到码头就断了，前景的近水里没有，
# 看着是浮在半空的一块长方形。现在拆成两半（scripts/river_moonpath.gdshader）：
# - 这里画的是遮罩，钉在屏幕上、对着月亮（MOON_X）：越往近处越宽、越稀、越暗一点，边缘抖开；一直铺到画面最下面（码头前的近水）。
# - 碎光由 shader 按「这一行水面的世界 x」切出来：每一行有自己的视差 scroll（贴着哪一层的水线就跟那一层一样快），
#   镜头走，碎光跟着水往后退，月光条留在月亮底下。
MOON_X = 340                     # sky.png 里月亮的中心（326~355），sky scroll 0
MOON_SCROLL = ((155, 0.16), (172, FAR_S), (184, 0.42), (192, MID_S), (200, NEAR_S), (206, 0.95), (217, 1.0))
MOON_PARAMS = {"speed": 1.0, "wobble": 1.5, "flicker": 0.9}


def moon_scroll(y):
    """第 y 行水面的视差 scroll：按各层水线插值（远岸 0.16 … 远层 0.3 … 礁石 0.42 … 中景 0.55 … 近中 0.75 … 码头 1.0）。"""
    ys, ss = zip(*MOON_SCROLL)
    return float(np.interp(y, ys, ss))


def moonpath_img(y0, y1):
    """屏幕第 y0..y1-1 行的月光遮罩：A = 能不能有碎光，R = 最亮档，B = 密度，G = scroll / 2。"""
    a = np.zeros((y1 - y0, SW, 4), np.uint8)
    for y in range(y0, y1):
        d = y - SHORE_WL
        hw = 6.0 + 0.58 * d                          # 地平线下窄，往近处越来越宽（透视）
        dens = np.interp(d, (0, 20, 55, 112), (0.8, 0.62, 0.4, 0.22))
        if _hash01(0, y, 13) < 0.3:                  # 有几行稀一点：一行一行的水波，不是均匀撒的点
            dens *= 0.4
        lvl = np.interp(d, (0, 30, 60, 112), (1.0, 0.9, 0.72, 0.58))   # 越近越暗一点，别抢晨
        for x in range(SW):
            u = abs(x + 0.5 - MOON_X) / hw
            edge = 1.0 + 0.3 * (_hash01(x // 2, y, 91) - 0.5)   # 边缘抖开，不是一条直线
            if u > edge:
                continue
            f = max(0.0, 1.0 - (u / edge) ** 2)
            a[y - y0, x] = (int(255 * lvl * (0.6 + 0.4 * f)), int(round(moon_scroll(y) / 2 * 255)),
                            int(255 * dens * (0.25 + 0.75 * f)), 255)
    return a


def moonpath_rgb(a, cam, t=0.0, params=MOON_PARAMS):
    """预览：照 river_moonpath.gdshader 算一帧（cam = 镜头左边缘的房间 x）。"""
    def h(px, py):
        px = np.mod(px, 997.0); py = np.mod(py, 991.0)
        v = np.sin(px * 127.1 + py * 311.7) * 43758.5453
        return v - np.floor(v)
    hgt, wid = a.shape[:2]
    py, px = np.mgrid[0:hgt, 0:wid].astype(float)
    m = a[..., 3] >= 128
    sc = a[..., 1] / 255.0 * 2
    w = params["wobble"] * np.clip(sc, 0.3, 1.0)
    sp = params["speed"]
    off = np.round(w * (0.65 * np.sin(t * sp * 0.9 + py * 0.71) + 0.35 * np.sin(t * sp * 2.3 + py * 1.93)))
    wx = px - off + np.floor(cam * sc + 0.5)
    cell = np.clip(np.floor(4.0 + 7.0 * sc + 0.5), 4, 12)
    ci = np.floor(wx / cell)
    k = wx - ci * cell
    h1 = h(ci, py); h2 = h(ci + 31, py + 17); h3 = h(ci + 57, py + 3); h4 = h(ci + 11, py + 41)
    lv = (a[..., 0] / 255.0) * 3 * (0.55 + 0.45 * h3) + 0.25 + params["flicker"] * np.sin(t * sp * (0.8 + h4 * 2.4) + h2 * 6.2832)
    on = m & (h1 <= a[..., 2] / 255.0) & (k < np.maximum(1, np.floor((0.35 + 0.65 * h2) * (cell - 1)))) & (lv >= 0)
    out = np.zeros_like(a)
    pal = [B(*c) for c in ra.GLINT_PAL]
    li = np.clip(np.floor(lv), 0, 3).astype(int)
    for i in range(4):
        mm = on & (li == i)
        out[mm, :3] = pal[i]
        out[mm, 3] = 255
    return out


BG_LAYERS = [
    {"id": "sky", "img": "res://art/river/sky.png", "scroll": 0.0, "y": 0},
    {"id": "ridge", "img": "res://art/river/ridge.png", "scroll": 0.05, "y": 0, "tile": True},
    {"id": "mist", "img": "res://art/river/mist.png", "scroll": 0.1, "y": 0, "tile": True, "drift": -2.5},
    {"id": "shore", "img": "res://art/river/shore.png", "scroll": 0.16, "y": 0, "tile": True},
    {"id": "far_ripples", "img": "far_ripples.png", "scroll": 0.3, "y": FAR_RIPPLES_Y, "tile": True,
     "shader": "water", "shader_params": {"palette_mode": False, "speed": 0.7, "wobble": 2.0, "flicker": 0.0,
                                          "show": 0.62}},
    {"id": "glints", "img": "moonpath.png", "scroll": 0.0, "y": SHORE_WL, "shader": "moonpath",
     "shader_params": MOON_PARAMS},
    {"id": "far_water", "img": "res://art/river/water.png", "scroll": 0.42, "y": FAR_WATER_DY, "tile": True},
]


def bank_json(objs):
    far_water = BG_LAYERS[-1]
    assert far_water["id"] == "far_water"
    layers = BG_LAYERS[:-1] + [
        {"id": "mid_far", "img": "mid_far.png", "scroll": FAR_S, "y": 0},      # 第七版：远 / 中 / 近中三层
        far_water,                                                             # 礁石 0.42 比远层近，画在它后面
        {"id": "mid", "img": "mid.png", "scroll": MID_S, "y": 0},
        {"id": "mid_near", "img": "mid_near.png", "scroll": NEAR_S, "y": 0},
        {"id": "main", "img": "main.png", "scroll": 1.0, "y": 0},
        {"id": "water", "img": "water.png", "scroll": 1.0, "y": WL, "water": True, "front": True, "alpha": 0.5},
        {"id": "near_glints", "img": "moonpath_near.png", "scroll": 0.0, "y": WL, "water": True, "front": True,
         "shader": "moonpath", "shader_params": MOON_PARAMS},                 # 月光一直铺到码头前的近水
        {"id": "ripples", "img": "ripples.png", "scroll": 1.0, "y": WL, "shader": "water",
         "shader_params": {"palette_mode": False, "show": 0.62, "wobble": 1.5, "speed": 0.8}, "front": True},
        {"id": "front", "img": "front.png", "scroll": FRONT_S, "y": 0, "front": True},
    ]
    markers = {"river_bank_plane": 190, "river_bank_hatch": 196, "river_bank_channel": 90,
               "river_bank_crates": CRATES + 36, "river_bank_niff": HOME[0] - 42,
               "river_bank_steps": STEPS_X + 54, "river_bank_box": STEPS_X + 74, "river_bank_post": POST,
               "river_bank_ting": 360, "river_bank_shallow": SHALLOW[0] + 70, "river_bank_toolkit": 304,
               "river_bank_home_door": HOME[0] + HOUSE_DOOR, "river_bank_doorplate": HOME[0] + HOUSE_PLATE[0] + 5,
               "river_bank_bakery": BAKERY, "river_bank_postman": (TOWERS[0] + TOWERS[1]) // 2 + 2,
               "river_bank_to_market": STAIR, "river_bank_to_south": SOUTH + 2, "river_bank_arrive": SOUTH - 30,
               "river_bank_drift_start": DRIFT}
    objd = {}
    for oid, frames, x, y, spec in objs:
        d = {"x": int(x), "y": int(y), "w": frames[0].shape[1], "h": frames[0].shape[0], "frames": len(frames)}
        d.update(spec)
        objd[oid] = d
        if oid.startswith("river_bank_salvage_") and oid != "river_bank_salvage_wake":
            markers[oid] = int(x) + d["w"] // 2
    return {
        "_note": "tools/river_bank_moon_art.py 生成，别手改。约定见 docs/river_rooms_contract.md。月夜：天、远岸、雾、碎光沿用 art/river/。第三版：加长，左边一大段空的河岸（330–820）没有人家、没有能点的东西。",
        "size": [W, SH], "env": "river", "bg": ["#0b1220", "#141d2c"],
        "layers": layers, "ground": GROUND, "markers": markers, "objects": objd,
        "water": {"y": WL}, "walk": [150, W - 10],
        # 没遇到妮芙以前最远走到箱子跟前（停在 meet_niff 的触发范围里：路过时正好在播别的、没触发，停下来也会补上）
        # （10-30 作者：晨一个人走过了箱子、一直走到妮芙家门口，没有妮芙、没有任何提示）
        "walk_when": [{"need": ["river_ashore"], "not": ["river_met"],
                       "walk": [150, markers["river_bank_crates"] + 50]}],
        "scripts": [{"script": "res://scripts/river_far_lantern.gd", "x": 0, "y": 0,
                     "z": -100 + [l["id"] for l in layers].index("mid"),             # 和中景一层（在近中层后面）
                     "params": {"scroll": MID_S, "x0": FAR_BRIDGE[0], "x1": FAR_BRIDGE[1], "y": FAR_BRIDGE[2]}}],
        "portals": [{"to": "market", "at": "market_entry", "kind": "pan_up", "x": STAIR},
                    {"edge": "right", "to": "southbridge", "at": "southbridge_entry", "kind": "walk_fade"}],
        "ambient": [{"name": "river_flow", "db": -12}],
    }


HOUSE_DOOR = 48


# ============================================================ 妮芙家：屋内 / 前墙 / 光

def _rha():
    import river_home_art as rha
    return rha


def moon_window(img):
    """换掉 D 的窗（窗外原来是白天的灰楼）：窗外是月下的河——深蓝的天、对岸两根石柱的剪影、一道水里的碎月光、远处一点暖灯。
    窗框、十字棂、窗帘、窗台、窗台上的瓶子照 D 的画法。"""
    rha = _rha()
    c = rha.cv(img)
    col = rha.col
    x0, y0, x1, y1 = rha.WIN_RECT
    wl = y1 - 12
    rng = np.random.default_rng(81)
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(1, wl - y0)
        for x in range(x0, x1 + 1):
            if y < wl:
                L = 0.17 + 0.09 * t
                c.put(x, y, col(round(L / 0.025) * 0.025, 0.035, 255 - 8 * t))
            else:
                c.put(x, y, col(0.13 + 0.03 * ((y + x) % 2 == 0 and y < wl + 2), 0.035, 258))
    for (px_, w_, h_) in ((x0 + 8, 6, 24), (x0 + 15, 4, 14), (x1 - 12, 8, 20)):   # 对岸的石柱
        for y in range(wl - h_, wl):
            k = (y - (wl - h_)) / h_
            ww = int(round(w_ * (0.6 + 0.4 * k)))
            for x in range(px_ - ww // 2, px_ + ww - ww // 2):
                c.put(x, y, col(0.13, 0.03, 258))
            c.put(px_ + ww - ww // 2 - 1, y, col(0.2, 0.03, 250))
    c.put(x1 - 18, y0 + 6, col(0.6, 0.02, 245))                                      # 一颗星、月光
    c.put(x0 + 20, y0 + 3, col(0.5, 0.02, 245))
    for y in range(wl + 1, y1 + 1):                                                  # 水里的碎月光
        for k in range(int(rng.integers(1, 3))):
            gx = x0 + 22 + int(rng.integers(-4 - (y - wl), 5 + (y - wl)))
            for x in range(gx, gx + int(rng.integers(1, 4))):
                c.put(x, y, col(0.5 - 0.02 * (y - wl), 0.03, 245))
    c.put(x0 + 5, wl - 2, Wm(.56))                                                   # 对岸一点暖灯
    c.put(x0 + 5, wl + 2, Wm(.4))
    fr = col(0.3, 0.02, 230)
    frd = col(0.22, 0.02, 240)
    c.rect(x0 - 3, y0 - 3, x1 + 3, y0 - 1, fr)
    c.rect(x0 - 3, y0, x0 - 1, y1, fr)
    c.rect(x1 + 1, y0, x1 + 3, y1, frd)
    mx, my = (x0 + x1) // 2, y0 + (y1 - y0) * 2 // 5
    c.rect(mx - 1, y0, mx, y1, frd)
    c.line(x0, my, x1, my, frd)
    rha.box(img, x0 - 8, y1 + 1, x1 + 8, y1 + 4, rha.WOOD, z=12, top=1, cell=(10, 4))
    rha.darken(img, rha.mrect(x0 - 6, y1 + 5, x1 + 6, y1 + 6), 1.5)
    cr = rha.Canvas(rha.W, rha.H)
    L, C_, hh = rha.CLOTH_ROSE
    for y in range(y0 - 2, y1 - 2):
        t = (y - y0) / (y1 - y0)
        wdt = int(10 - 6 * math.sin(math.pi * min(1, t * 1.6)))
        for x in range(x0 - 6, x0 - 6 + wdt):
            k = 1 if (x - x0) % 4 < 2 else 0
            cr.put(x, y, col(L - rha.STEP + k * rha.STEP, C_, hh))
    rha.over_mask(img, cr.a)
    c.line(x0 - 8, y0 - 4, x1 + 8, y0 - 4, col(*rha.IRON))
    c.rect(x0 - 5, y0 + 18, x0 + 1, y0 + 19, col(0.28, 0.02, 60))
    for px_, ph in ((x1 - 2, 8), (x1 - 8, 6)):
        c.rect(px_, y1 + 1 - ph, px_ + 2, y1, col(*rha.GLASS))
        c.put(px_ + 2, y1 + 1 - ph, col(0.40, 0.02, 215))
        for k in range(3):
            c.line(px_ + 1, y1 - ph, px_ - 1 + k * 2, y1 - ph - 4 - k, col(0.34, 0.03, 120 - k * 30))
            c.put(px_ - 1 + k * 2, y1 - ph - 5 - k, col(0.45, 0.04, 30 + k * 30))
        rha.tag(c, px_, y1 - 2, 2, 1)


def lamp_pos():
    rha = _rha()
    return (rha.T_X0 + rha.T_X1) // 2, rha.FL - 73      # D 的吊灯（灯罩中心），D 坐标


def moon_interior(a: np.ndarray, ox=0, oy=0, lamp=True, dark=0.74) -> np.ndarray:
    """屋内上色：先整体换成月夜（night），再按离吊灯的远近往暖推（一小圈，地上、桌面、条子板最暖）；
    窗那边留冷。ox, oy = 这张图左上角在 D 的图里的位置（物件用）。"""
    out = night(a, dark)
    if not lamp:
        return out
    lx, ly = lamp_pos()
    hgt, wid = out.shape[:2]
    m = out[..., 3] > 0
    cache = {}
    for y in range(hgt):
        for x in range(wid):
            if not m[y, x]:
                continue
            d = math.hypot(x + ox - lx, (y + oy - ly) * 1.25) / 95.0
            if d >= 1:
                continue
            q = int(min(3, (1 - d) * 4.2))                      # 分档（不糊）：0..3
            if d > 0.62 and (x + y) % 2:
                q = max(0, q - 1)
            if q <= 0:
                continue
            key = (tuple(out[y, x, :3]), q)
            if key not in cache:
                c = tuple(int(v) for v in out[y, x, :3])
                lab = to_lab(c)
                L = lab[0]
                t = (0.0, 0.18, 0.3, 0.42)[q]
                tgt = Wm(min(0.62, L + 0.1 + 0.03 * q), 0.07, 66)
                nc = mixc(c, tgt, t)
                cache[key] = nc
            out[y, x, :3] = cache[key]
    return out


def home_lamp(img):
    """吊灯点亮：灯罩里暖黄，罩口下沿最亮。D 坐标。"""
    rha = _rha()
    c = rha.cv(img)
    lx, ly = lamp_pos()
    for y in range(ly - 2, ly + 2):
        for x in range(lx - 4, lx + 5):
            c.put(x, y, Wm(.5 + 0.04 * (y - ly + 2), 0.085, 66))
    c.line(lx - 5, ly + 2, lx + 5, ly + 2, Wm(.62, .09, 72))
    c.put(lx, ly + 2, Wm(.66, .085, 78))


HOME_PILLARS = ((70, 136, 146, 5511, "tower"), (214, 120, 128, 5512, "stack"), (354, 126, 162, 5513, "tower"))
HOME_SADDLE = 77                 # 柱子之间长在一起的那块石头的顶（图里的 y）：比屋内顶（82）高一点，盖住剖开的楼板
# 前墙上凿的窗（图里的 x, 离地 y, w, h, kind, 亮不亮）：都是小窗（作者：大墙 + 大平涂窗敷衍）
HOME_WINDOWS = ((104, 70, 9, 13, "arch", True), (192, 66, 12, 16, "arch", True), (252, 40, 9, 9, "round", True),
                (330, 82, 8, 12, "arch", True), (374, 50, 6, 8, "arch", False), (150, 96, 5, 7, "arch", False))


def home_rock(rha, hh):
    """妮芙家 = 三根石柱的脚长在一起，屋子凿在柱脚里（作者喜欢的「打洞的石柱房」，学树屋：大树 → 石柱）。
    三根柱子高矮不一，柱顶之间露出天和月亮（不是一整面墙）；柱子之间长在一起的那块是两道深的石缝（影子里）。
    和河岸的石柱同一种画法（river_art.pillar）。返回 (mask, RGBA)。"""
    w = rha.W
    img = np.zeros((hh, w, 4), np.uint8)
    rng = np.random.default_rng(5501)
    # 先摆柱子（记下哪些像素是柱子），柱子之间、两头没盖到屋子的地方再补上长在一起的石头（每一块单独上色，暗一档）
    pil = np.zeros((hh, w, 4), np.uint8)
    for (cx, pw, ph, sd, kind) in HOME_PILLARS:
        p = ra.pillar(pw, ph, sd, STONE, crown=[B(.07, .02, 258), B(.1, .022, 252)], kind=kind)
        ox, oy = cx - p.shape[1] // 2, hh - p.shape[0]
        for yy in range(p.shape[0]):
            ty = oy + yy
            if 0 <= ty < hh:
                for xx in np.nonzero(p[yy, :, 3])[0]:
                    if 0 <= ox + xx < w:
                        pil[ty, ox + xx] = p[yy, xx]
    fill = np.zeros((hh, w), bool)
    for x in range(w):
        e = min(x, w - 1 - x)                         # 离两边多远：屋子两头是往下圆过去的石脚，不是一刀竖边
        top = HOME_SADDLE + max(0, 24 - e) * 0.4 + (max(0, 14 - e) ** 1.5) * 3
        if top < hh:
            fill[int(round(top)):, x] = True
    fill &= pil[..., 3] == 0
    lab, n = ra.components(fill)
    for k in range(1, n + 1):
        mk = lab == k
        if mk.sum() < 4:
            continue
        ys, xs = np.nonzero(mk)
        sub = mk[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        sh = ra.shade_rock(sub, rng, ra.bramp(4, .055, .15, 262, 252), cracks=(0, 1), seams=False)   # 缝里：深影子，不抢柱子
        reg = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        reg[sub] = sh[sub]
    m0 = pil[..., 3] > 0
    img[m0] = pil[m0]
    m = img[..., 3] > 0
    return m, img


def home_rock_top(cv: Cv, m):
    """矮的那根柱子顶上一截铁皮烟囱（屋里的炉子），几处苔。"""
    rng = np.random.default_rng(5502)
    h, w = m.shape
    for x in range(w):
        ys = np.nonzero(m[:, x])[0]
        if len(ys) and rng.random() < 0.3:
            cv.px(x, ys[0], MOSS[1])
    px_ = 222
    top = int(np.nonzero(m[:, px_])[0][0])
    cv.rect(px_, top - 9, px_ + 4, top + 2, B(.1, .015, 250))
    cv.vline(px_ + 3, top - 9, top + 2, B(.2, .02, 246))
    cv.hline(px_ - 1, px_ + 5, top - 9, B(.22, .02, 246))


def home_section(cv: Cv, rha):
    """剖开的地方（屋内四周一圈 WALL_T 厚的墙 / 顶）：是凿开的石头的断面，不是灰泥。"""
    x0, x1 = rha.IX0 - rha.WALL_T, rha.IX1 + rha.WALL_T
    y0, fl = rha.CEIL - rha.WALL_T + HDY, rha.FL + HDY
    sec = [B(.07, .02, 262), B(.1, .022, 256), B(.14, .024, 250)]
    for y in range(y0, fl):
        for x in range(x0, x1):
            inner = rha.IX0 <= x < rha.IX1 and y >= rha.CEIL + HDY
            if inner:
                continue
            k = 1 if (x * 3 + y * 5) % 7 else 0
            if y == y0:
                k = 2
            cv.px(x, y, sec[k])
    cv.hline(rha.IX0, rha.IX1, rha.CEIL + HDY - 1, sec[0])


def home_front(rha, hh, rock):
    """前墙（进屋淡出）= 柱脚的正面（和 back 里的石头是同一张，淡掉时只有屋里那块变）：
    下面一截是旧水位以下泡过的（暗一档、一道苔）；左边凿出的门洞（往里开的门板、屋里的灯从里往外一档档暗下来，
    门上一盏灯、门边现在的门牌）；几扇小窗（HOME_WINDOWS，洞里看得出墙厚、屋里的深浅）；一根晾绳、门边花盆、一卷绳。
    只盖屋内那一块（x 14..405，y CEIL-6..FL）。"""
    x0, x1 = rha.IX0 - rha.WALL_T, rha.IX1 + rha.WALL_T
    y0, fl = rha.CEIL - rha.WALL_T + HDY, rha.FL + HDY
    cv = Cv(rha.W, hh)
    cv.a[y0:fl, x0:x1] = rock[y0:fl, x0:x1]
    rng = np.random.default_rng(5601)
    old_y = fl - 42                                   # 旧水位：以下的石头泡过，暗一档、发青
    for y in range(old_y, fl):
        for x in range(x0, x1):
            if cv.a[y, x, 3]:
                c = tuple(int(v) for v in cv.a[y, x, :3])
                cv.a[y, x, :3] = mixc(c, B(.07, .03, 232), 0.3)
    for x in range(x0, x1):
        for d in range(int(rng.integers(1, 3))):
            cv.px(x, old_y + d, MOSS[1] if d == 0 else MOSS[0])
        if rng.random() < 0.05:
            for d in range(int(rng.integers(3, 10))):
                cv.px(x, old_y + 3 + d, B(.06, .02, 252))
    # 门洞（D 的门在 X(16)..X(40)）
    dx0, dx1 = rha.X(16), rha.X(40)
    dw, dh = dx1 - dx0 + 1, 50
    carve(cv, dx0, fl - dh, dw, dh, "arch", True, True, glow_r=26)
    cv.hline(dx0 - 3, dx1 + 4, fl - 1, STONE[4])      # 门口一道凿平的石槛
    lantern(cv, dx1 + 7, fl - dh + 4, "hang", r=13)
    # 门牌（现在的地址）：门右边，离地约 30；水下同一个 x 有一块旧的，字一样
    ax, ay = HOUSE_PLATE[0], fl - 34
    cv.rect(ax, ay, ax + 11, ay + 7, Wm(.42, .035, 80))
    cv.vline(ax + 11, ay + 1, ay + 7, Wm(.32, .03, 70))
    cv.hline(ax + 2, ax + 9, ay + 2, B(.14, .02, 250))
    cv.hline(ax + 2, ax + 7, ay + 4, B(.14, .02, 250))
    cv.px(ax + 5, ay - 1, WOOD[3])
    # 小窗
    for i, (wx, oy, ww, wh, kind, lit) in enumerate(HOME_WINDOWS):
        carve(cv, wx, fl - oy - wh, ww, wh, kind, lit, glow_r=ww + 8, seed=5610 + i)
    wx, oy, ww, wh, _k, _l = HOME_WINDOWS[1]          # 大一点的那扇窗下一只窄花箱
    cv.rect(wx - 2, fl - oy + 1, wx + ww + 2, fl - oy + 4, WOOD[1])
    cv.hline(wx - 2, wx + ww + 2, fl - oy + 1, WOOD[3])
    for k in range(4):
        fx = wx + k * 4
        cv.line([(fx, fl - oy), (fx + (k % 2), fl - oy - 3)], MOSS[1])
        cv.px(fx + (k % 2), fl - oy - 4, (Wm(.5, .06, 40), B(.4, .03, 300), Wm(.5, .05, 90))[k % 3])
    # 晾绳：两扇窗之间，两头钉在石头里
    lx0, lx1, ly = 214, 300, fl - 92
    for x in range(lx0, lx1 + 1):
        cv.px(x, int(ly + 4 * math.sin(math.pi * (x - lx0) / (lx1 - lx0))), WOOD[3])
    cv.rect(232, ly + 4, 238, ly + 12, B(.2, .03, 210))
    cv.rect(256, ly + 5, 260, ly + 10, B(.32, .02, 90))
    cv.rect(278, ly + 4, 283, ly + 11, B(.2, .03, 60))
    # 门边两只花盆、一卷绳、靠墙一根撑船的篙
    for k, (ppx, ph) in enumerate(((rha.X(46), 6), (rha.X(53), 5))):
        cv.rect(ppx, fl - ph, ppx + 5, fl, Wm(.22, .035, 50))
        cv.hline(ppx, ppx + 5, fl - ph, Wm(.28, .035, 55))
        for j in range(4):
            cv.line([(ppx + 1 + j, fl - ph - 1), (ppx + j - 1 + (j % 3), fl - ph - 5 - j % 2)], MOSS[2])
    for y in range(fl - 74, fl):
        cv.px(rha.X(110) + (y - (fl - 74)) // 20, y, WOOD[3])
    for r_, k in ((5, 1), (4, 2), (2, 0)):
        cv.ellipse(rha.X(122), fl - 3, r_ + 1, 2, WOOD[k])
    return cv


def home_light(rha, hh):
    """屋里的光（半透明层）：吊灯下面一圈暖（桌子、地上最亮），窗里斜进来一道很淡的月光。"""
    img = np.zeros((hh, rha.W, 4), np.uint8)
    lx, ly = lamp_pos()
    ly += HDY
    fl = rha.FL + HDY
    for y in range(ly, fl):
        t = (y - ly) / (fl - ly)
        half = 10 + 34 * t
        for x in range(int(lx - half), int(lx + half) + 1):
            if rha.IX0 <= x < rha.IX1:
                u = abs(x - lx) / half
                a = int(30 * (1 - u ** 2) * (1 - 0.3 * t))
                if a > 4:
                    img[y, x] = (238, 196, 120, a)
    x0, y0, x1, y1 = rha.WIN_RECT
    for y in range(y0 + HDY, fl):
        t = (y - y0 - HDY) / (fl - y0 - HDY)
        a0 = x0 + int(30 * t)
        a1 = x1 + int(30 * t) - 6
        alpha = int(16 * (1 - 0.6 * t))
        for x in range(max(rha.IX0, a0), min(rha.IX1, a1)):
            if img[y, x, 3] == 0:
                img[y, x] = (150, 176, 220, alpha)
    return img


def build_home_parts():
    """返回 back, front, light（np）、物件列表 [(prop, img名, frames[np], x, y, states, note)]、D 的 meta（markers 等）。"""
    rha = _rha()
    rha.window = moon_window                          # build_back 里调的是模块里的 window
    rha.TAGS.clear()
    back_d = rha.build_back()
    rha.BACK_TAGS[:] = rha.TAGS
    home_lamp(back_d)
    back_d = moon_interior(back_d, dark=0.66)
    hh = rha.H + HDY
    back = Cv(rha.W, hh)
    rm, rock = home_rock(rha, hh)
    back.paste(rock, 0, 0)
    top_d = rha.CEIL - rha.WALL_T                     # D 的屋顶不要（屋是凿在石柱脚里的），从剖开的楼板往下贴
    back.paste(back_d[top_d:], 0, top_d + HDY)
    home_section(back, rha)
    home_rock_top(back, rm)
    front = home_front(rha, hh, rock)
    light = home_light(rha, hh)
    # 物件：照 D 的 build_objects 重画一遍，再上月夜 + 吊灯的色
    objs = []

    def put(prop, img, frames, x0, y0, states, note=""):
        fr = [moon_interior(f, x0, y0, dark=0.66) for f in frames]
        objs.append((prop, img, fr, int(x0), int(y0) + HDY, rha._states(states), note))

    f, names = rha.table_frames()
    put("river_home_table", "obj_table", f, rha.TB_X0, rha.TB_Y1 - rha.TB_H + 1,
        {n: {"frames": [i]} for i, n in enumerate(names)}, "桌面上的东西；沙漏、本子、照片、来客册是单独的物件")
    f, st = rha.hourglass_frames()
    put("river_home_hourglass", "obj_hourglass", f, rha.HG_X, rha.T_TOP - rha.HG_H, st,
        "右边铁丝挑着的小铃 = 漏完时响的轻铃（sfx bell_soft）")
    f, st = rha.notebook_frames()
    put("niff_notebook", "obj_notebook", f, rha.NB_X, rha.T_TOP - rha.NB_H, st,
        "桌上那本：合着 / 摊开；每页的字是特写 art/river_story/closeup_niff_notebook_<state>.png")
    f, st = rha.photo_frames()
    put("niff_photo", "obj_photo", f, rha.PH_X, rha.T_TOP - rha.PH_H, st, "特写 closeup_niff_photo.png")
    f, st = rha.guestbook_frames()
    put("guestbook", "obj_guestbook", f, rha.GB_X0, rha.GB_Y0, st,
        "一帧横跨桌子到窗台：open / photo_cup / pages_stuck / closed / drawing_in 在桌上，drying / dry 在窗台上；"
        "特写 closeup_guestbook_<state>.png")
    f, st = rha.chair_frames()
    put("river_home_chair", "obj_chair", f, rha.CH_X0, rha.FL - rha.CH_H, st, "晨坐的那把：default 靠在柜子边，by_window 在窗边")
    f, st = rha.cabinet_frames()
    put("river_home_cabinet", "obj_cabinet", f, rha.CB_X0, rha.CB_Y0, st, "柜门；柜体和柜顶的盒子在 home_back 里")
    f, st, _cls = rha.player_frames()
    put("river_home_player", "obj_player", f, rha.PL_X0, rha.FL - 14 - rha.PL_H, st,
        "屏幕里是影像缩小的；影像特写 art/river_story/closeup_footage_<state>.png（一格放大 2 倍），"
        "整段动画 art/river_home/footage_<state>.png（多帧横排，每帧 112×80，100ms）")
    f, st, (lx, ly) = rha.labels_frames()
    put("river_home_labels", "obj_labels", f, lx, ly, st, "on = 每张标签亮一档（晨注意到屋里几乎每件东西都有标签，原文 81）")
    return rha, back.a, front.a, light, objs


def build_home():
    rha, back, front, light, objs = build_home_parts()
    old = json.loads((HOME_DIR / "room.json").read_text())
    save_png(back, HOME_DIR / "home_back.png")
    save_png(front, HOME_DIR / "home_front.png")
    Image.fromarray(light, "RGBA").save(HOME_DIR / "home_light.png")
    od = {}
    for prop, img, frames, x, y, states, note in objs:
        save_png(np.concatenate(frames, axis=1), HOME_DIR / f"{img}.png")
        d = {"img": f"{img}.png", "x": x, "y": y, "w": frames[0].shape[1], "h": frames[0].shape[0],
             "frames": len(frames), "states": states, "default": "default"}
        if note:
            d["note"] = note
        od[prop] = d
    meta = {
        "_comment": "妮芙家（剖面小屋，月夜）。格式照 docs/river_rooms_contract.md 1.6：坐标都是图里的像素（左上角 0,0）。"
                    "tools/river_bank_moon_art.py 生成（屋内借 tools/river_home_art.py 的画法重新上色），别手改。"
                    "地板下面泡在水里的旧一层（旧门、旧门牌）画在河岸主层里。",
        "kind": "house", "host": "river_bank", "x": HOME_X, "size": [rha.W, rha.H + HDY],
        "back": "home_back.png", "front": "home_front.png", "light": "home_light.png",
        "floor": rha.FL - 1 + HDY, "walk": old.get("walk", [26, 392]), "door": old.get("door", HOUSE_DOOR),
        "markers": old["markers"], "objects": od,
    }
    for k in old.get("objects", {}):
        assert k in od, k
    (HOME_DIR / "room.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ok river_home")
    return meta


def house_for_preview(states=None):
    """预览用：小屋的几张图 + 物件（按状态取帧），放在河岸里的位置。"""
    states = states or {}
    meta = json.loads((HOME_DIR / "room.json").read_text())
    back = np.array(Image.open(HOME_DIR / meta["back"]).convert("RGBA"))
    front = np.array(Image.open(HOME_DIR / meta["front"]).convert("RGBA"))
    light = np.array(Image.open(HOME_DIR / meta["light"]).convert("RGBA"))
    objs = []
    for k, o in meta["objects"].items():
        if k == "river_home_labels":
            continue
        a = np.array(Image.open(HOME_DIR / o["img"]).convert("RGBA"))
        v = o["states"].get(states.get(k, "default"), 0)
        fi = v[0] if isinstance(v, list) else v
        objs.append((a[:, fi * o["w"]:(fi + 1) * o["w"]], o["x"], o["y"]))
    hw, hh = meta["size"]
    return {"x": meta["x"] - hw // 2, "y": G - hh + 1, "back": back, "front": front,
            "light": light, "objs": objs}


# ============================================================ 写文件、预览

def check_alpha(a, name):
    al = a[..., 3]
    assert ((al == 0) | (al == 255)).all(), f"{name}: 有半透明像素"


def save_png(a, path):
    check_alpha(a, path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a, "RGBA").save(path)


def load_res(p, base):
    if p.startswith("res://"):
        return np.array(Image.open(ROOT / p[6:]).convert("RGBA"))
    return np.array(Image.open(base / p).convert("RGBA"))


def glint_rgb(a):
    """glints.png（palette_mode）→ 预览用颜色。"""
    out = a.copy()
    pal = [B(*c) for c in ra.GLINT_PAL]
    m = a[..., 3] > 0
    lv = np.clip((a[..., 0] / 255.0 * 3 + 0.25).astype(int), 0, 3)
    for i in range(4):
        mm = m & (lv == i)
        out[mm, :3] = pal[i]
    return out


def render(room, base, cam_x, states=None, chen_x=None, house=None, house_front=1.0):
    """按约定模拟引擎画一屏（层、物件、小屋、晨）。"""
    states = states or {}
    cam_x = int(np.clip(cam_x, 0, room["size"][0] - SW))
    top, bot = np.array([11, 18, 32]), np.array([20, 29, 44])
    t = np.linspace(0, 1, SH)[:, None, None]
    im = (top[None, None] * (1 - t) + bot[None, None] * t) * np.ones((SH, SW, 3))
    items = []
    for i, s in enumerate(room["layers"]):
        z = s.get("z", 100 + i if s.get("front") else -100 + i)
        items.append((z, "layer", s))
    for oid, s in room["objects"].items():
        st = states.get(oid, s.get("default", "default"))
        if st in ("hidden", "gone", "taken"):
            continue
        v = s.get("states", {}).get(st, 0)
        fi = v[0] if isinstance(v, list) else v
        items.append((s.get("z", 100 if s.get("front") else -1), "obj", (oid, s, fi)))
    if house:
        items.append((-50, "house_back", None))
        items.append((90, "house_front", None))
    if chen_x is not None:
        items.append((0, "chen", chen_x))
    for z, kind, s in sorted(items, key=lambda q: q[0]):
        if kind == "layer":
            a = load_res(s["img"], base)
            if s.get("shader") == "moonpath":
                a = moonpath_rgb(a, cam_x)
            elif s["id"] == "glints":
                a = glint_rgb(a)
            y = s["y"]
            sx = int(round(cam_x * s["scroll"])) - s.get("x", 0)
            if s.get("tile"):
                sx %= a.shape[1]
                a2 = np.concatenate([a, a, a], axis=1)[:, sx:sx + SW]
            else:
                a2 = a[:, max(0, sx):sx + SW]
            rca._blit(im, a2, 0, y, s.get("alpha", 1.0))
        elif kind == "obj":
            oid, s2, fi = s
            a = load_res(s2.get("img", oid + ".png"), base)
            fr = a[:, fi * s2["w"]:(fi + 1) * s2["w"]]
            rca._blit(im, fr, s2["x"] - cam_x, s2["y"], 1.0)
        elif kind == "house_back":
            hx, hy, back, objs_, light = house["x"], house["y"], house["back"], house["objs"], house["light"]
            rca._blit(im, back, hx - cam_x, hy, 1.0)
            for (fr, ox, oy) in objs_:
                rca._blit(im, fr, hx + ox - cam_x, hy + oy, 1.0)
            if light is not None:
                ly0 = max(0, -hy)                             # 房子顶伸出画面上沿（妮芙家三层，比画面高）
                lt = light[ly0:]
                reg = im[max(0, hy):hy + light.shape[0], :]
                lt = lt[:reg.shape[0]]
                x0 = hx - cam_x
                xs0, xs1 = max(0, x0), min(SW, x0 + light.shape[1])
                if xs0 < xs1:
                    l2 = lt[:, xs0 - x0:xs1 - x0]
                    a2 = l2[..., 3:4] / 255.0
                    reg[:, xs0:xs1] = reg[:, xs0:xs1] * (1 - a2) + l2[..., :3] * a2
        elif kind == "house_front":
            rca._blit(im, house["front"], house["x"] - cam_x, house["y"], house_front)
        elif kind == "chen":
            fr = rca.chen_img()
            gy_ = room_ground(room, s)
            rca._blit(im, fr, int(s) - cam_x - rca.CHEN_FOOT[0], gy_ - rca.CHEN_FOOT[1], 1.0)
    return im.round().astype(np.uint8)


def room_ground(room, x):
    g = room["ground"]
    if isinstance(g, (int, float)):
        return int(g)
    xs, ys = zip(*g)
    return int(round(np.interp(x, xs, ys)))


def build_bank():
    BANK_DIR.mkdir(parents=True, exist_ok=True)
    for old in ("mid.png", "main.png", "water.png", "ripples.png", "ripples_back.png", "front.png", "rail.png",
                "shafts.png"):
        pass
    save_png(far_ripples_img(), BANK_DIR / "far_ripples.png")      # 先存：water_at() 叠远水时要用
    save_png(moonpath_img(SHORE_WL, WL), BANK_DIR / "moonpath.png")
    save_png(moonpath_img(WL, SH), BANK_DIR / "moonpath_near.png")
    save_png(bank_far().a, BANK_DIR / "mid_far.png")
    save_png(bank_mid().a, BANK_DIR / "mid.png")
    save_png(bank_near().a, BANK_DIR / "mid_near.png")
    save_png(bank_main().a, BANK_DIR / "main.png")
    save_png(water_front().a, BANK_DIR / "water.png")
    save_png(water_ripples().a, BANK_DIR / "ripples.png")
    save_png(bank_front().a, BANK_DIR / "front.png")
    objs = objects()
    for oid, frames, x, y, spec in objs:
        save_png(np.concatenate(frames, axis=1), BANK_DIR / f"{oid}.png")
    room = bank_json(objs)
    (BANK_DIR / "room.json").write_text(json.dumps(room, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ok river_bank")
    return room


def preview_bank(room, out: Path, house=None):
    out.mkdir(parents=True, exist_ok=True)
    fl = {f"river_bank_salvage_{k}": "float" for k in rca.SALVAGE}
    shots = [(0, {}, 196, 1), (330, {}, 560, 1), (740, {"river_bank_crates": "tail"}, 880, 1), (880, fl, 1076, 1),
             (1330, {}, 1408, 1), (1330, {}, 1500, 0), (1740, {}, 1900, 1), (1840, {}, 2200, 1)]
    tiles = [Image.fromarray(render(room, BANK_DIR, c, st, cx, house=house, house_front=hf)) for c, st, cx, hf in shots]
    sheet = Image.new("RGB", (SW * 2 + 4, (SH + 4) * 4), (20, 20, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 2) * (SW + 4), (i // 2) * (SH + 4)))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(out / "bank_sheet.png")
    return out / "bank_sheet.png"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default=None)
    ap.add_argument("--only", default="bank,home")
    a = ap.parse_args()
    only = a.only.split(",")
    room = build_bank() if "bank" in only else json.loads((BANK_DIR / "room.json").read_text())
    if "home" in only:
        build_home()
    if a.preview:
        print(preview_bank(room, Path(a.preview), house=house_for_preview()))
