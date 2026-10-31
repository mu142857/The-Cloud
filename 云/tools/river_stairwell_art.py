"""河流篇 · 楼梯间 stairwell（10-31 作者：市集和旧街之间加一间室内楼梯间，旧街是被水淹的、比市集低，不能直接平移过去）。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_stairwell_art.py [--preview 目录] [--jelly 水母原图]

一整屏（480×270，镜头不动），凿在石头里的旧楼梯间，月夜蓝调 + 三盏黄灯，做法和质量照妮芙家（tools/river_home_rooms_art.py）：
  左上：平台（y118），左墙上的门洞通市集（门板往里开着，门洞外是市集那一片夜空）。
  中间：石阶从左上往右下（150→330，十级），阶面磨圆了——不画直角台阶（xiao-oscar 常见坑）：每级是一段缓坡（踏面）接一段陡坡（磨圆的阶沿），
        轮廓上相邻两行横向最多差 2 像素；后墙上一道铁扶手顺着石阶（一像素粗，四邻接，几处托架钉在墙上）；阶下凿了个放杂物的洞。
  右下：低处（y228），柜台（单独一层 counter.png，盖在水母前面、晨后面），柜台后面住着一只水母（美术姐画的，art/characters/jellyfish/）；
        右墙门洞通旧街（门槛泡着一层薄水，门外是水面）；墙根一道旧水位的湿痕。
  高处一扇拱窗，正好框住月亮（窗、门洞都是镂空的，透出 room.json 里垫在后面的市集夜空层，不画实心色块）；月光斜着落到石阶上（light.png）。
  外面一圈是剖开的石头断面（front.png，在人前面），和妮芙家的剖面屋一个意思。

输出 art/river_city/stairwell/：back.png、counter.png、light.png、front.png、room.json；
--jelly：把原图（480×480，32×32 像素画放大 15 倍）按格取样还原成 1 倍，存 art/characters/jellyfish/jellyfish.png（不重画、不改色），原图复制一份在旁边。
所有随机固定 seed；back / counter / front 的 alpha 只有 0/255（light 是半透明的光层）。不碰 art/手改清单.json 里的文件。
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import river_bank_moon_art as bm  # noqa: E402
from river_bank_moon_art import B, Wm, MOSS, Cv  # noqa: E402
import river_art as ra  # noqa: E402
import river_rock_tex as rt  # noqa: E402
import river_home_props as hp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "river_city" / "stairwell"
JELLY = ROOT / "art" / "characters" / "jellyfish"

W, H = 480, 270
LAND, LOW = 118, 228              # 平台、低处的地面（脚底那一行）
SX0, NSTEP, STEP, TREAD = 150, 10, 18, 14     # 石阶：从 x150 起十级，每级 18 宽、降 11；踏面约 14 宽，后面是磨圆的阶沿（见 _floor_table）
SX1 = SX0 + NSTEP * STEP          # 330
FL, FR, FB = 6, 474, 240          # 剖面框：左、右、底（里面是屋）
CEIL = [(6, 52), (40, 40), (100, 31), (180, 27), (260, 22), (318, 16), (372, 18), (420, 24), (452, 36), (474, 52)]

DOOR_L = (12, 70, 24, 48)         # 通市集的门洞 x, y, w, h（门槛 = LAND）
DOOR_R = (444, 176, 26, 52)       # 通旧街的门洞（门槛 = LOW）
WIN = (320, 30, 40, 66)           # 拱窗：圆心 (340, 50)，月亮在市集夜空层的 (340, 54)
NICHE_X = (188, 300)              # 阶下的洞
COUNTER = (360, 414, 206)         # 柜台左右、台面那一行
JELLY_X = 396                     # 水母站的地方（柜台后面偏右，晨在柜台前面说话不挡她）

LA = (86, 74, 10, 64, 1.0)        # 平台上吊着的灯（灯芯）
LB = (238, 128, 8, 56, 0.9)       # 石阶中间墙上托架挂的灯
LC = (372, 172, 10, 62, 1.0)      # 柜台上方托架挂的灯
LD = (84, 87, 4, 18, 0.45)        # 平台架板上的一截蜡烛
MOON = (330, 64, 40, 150, 0.55, (90, 236))   # 窗进来的月光（冷，只提亮）
LAMPS = [LA, LB, LC, LD, MOON]

CAVE = rt.CAVE7
MASS = ra.bramp(7, .07, .31, 258, 240)       # 石阶 / 平台 / 地面这块实心的石头：比后墙亮一档（离灯近、朝外）
DARK = [B(.03, .02, 266), B(.05, .022, 262), B(.08, .026, 256)]
POLISH = B(.40, .03, 234)                    # 被脚磨亮的阶沿 / 地面边（比石块最亮那档再亮一点）
SIL = [B(.03, .018, 266), B(.07, .022, 258), B(.27, .04, 232)]   # 前景剪影：暗、暗一档、朝月光那一线冷亮边
BEAM = (324, 356)                            # 月光光带（窗洞里面那一段的左右）
BEAM_Y, BEAM_XR = 34, 292                    # 顶上的老木系梁：上沿那一行、右头


# ======================================================================= 形
def _floor_table():
    """脚底那一行（每列一个整数）：平台 → 十级磨旧了的石阶 → 低处。
    每级的坡度是平滑变的（踏面几乎平、往下 0.15，阶沿那里用升余弦鼓起来到最陡 2.9，再圆回下一级的踏面）：
    看得出一级一级，但轮廓上没有横着走再突然竖着下去的直角（xiao-oscar 常见坑）。"""
    st, hw = 0.15, 3.0
    uc = TREAD + 1.0                                   # 阶沿最陡的地方（每级里的 x）
    sr = st + (11.0 - st * STEP) / hw                  # 每级正好降 11
    ys = np.full(W, float(LAND))
    acc = float(LAND)
    for x in range(SX0, SX1):
        u = (x - SX0) % STEP + 0.5
        d = abs(u - uc)
        bump = 0.5 * (1 + math.cos(math.pi * d / hw)) if d < hw else 0.0
        acc += st + (sr - st) * bump
        ys[x + 1] = acc
    ys[SX1:] = LOW
    return np.round(ys).astype(int)


FLOOR = None


def floor_y(x):
    global FLOOR
    if FLOOR is None:
        FLOOR = _floor_table()
    return int(FLOOR[min(max(int(x), 0), W - 1)])


def ground_pts():
    """给引擎的折线：每一段同高的两头各一个点（引擎逐列线性插值再取整，和画出来的一列不差）。"""
    pts = [[0, LAND]]
    x = 0
    while x < W:
        y = floor_y(x)
        x2 = x
        while x2 + 1 < W and floor_y(x2 + 1) == y:
            x2 += 1
        if x > 0:
            pts.append([x, y])
        if x2 != x:
            pts.append([x2, y])
        x = x2 + 1
    return pts


def interp(pts, x):
    return float(np.interp(x, [p[0] for p in pts], [p[1] for p in pts]))


def ceil_y():
    xs = np.arange(W)
    raw = np.array([interp(CEIL, x) for x in xs])
    k = np.array([1, 4, 6, 4, 1], float)
    k /= k.sum()
    sm = np.convolve(np.pad(raw, 2, mode="edge"), k, mode="valid")
    rng = np.random.default_rng(9101)
    return np.round(sm + ra.smooth1d(W, rng, 18, 1.4)).astype(int)


def masks():
    cy = ceil_y()
    cave = np.zeros((H, W), bool)
    air = np.zeros((H, W), bool)
    rng = np.random.default_rng(9102)
    nl = ra.smooth1d(H, rng, 24, 1.0)
    for x in range(W):
        for y in range(H):
            xl = FL + int(round(nl[y]))
            xr = FR - int(round(nl[(y * 5) % H]))
            if xl <= x < xr and cy[x] <= y < FB:
                cave[y, x] = True
                if y <= floor_y(x):
                    air[y, x] = True
    mass = cave & ~air
    # 阶下的洞：左边一道竖壁（顶上磨圆），上沿是石阶的底面（和扶手平行的一道直斜线，阶面往下 16），往右收到地面
    niche = np.zeros((H, W), bool)
    x0, x1 = NICHE_X
    for x in range(x0, x1):
        top = int(round(LAND + 16 + (x - SX0) * (LOW - LAND) / (SX1 - SX0)))
        d = x - x0
        if d < 6:
            top += int(round(6 - math.sqrt(max(0.0, 36 - (6 - d) ** 2))))       # 左上角磨圆
        if top <= LOW - 6:
            niche[top:LOW + 1, x] = True
    return cave, air, mass, niche, cy


def dilate(m, n):
    o = m.copy()
    for _ in range(n):
        p = o.copy()
        p[1:] |= o[:-1]
        p[:-1] |= o[1:]
        p[:, 1:] |= o[:, :-1]
        p[:, :-1] |= o[:, 1:]
        o = p
    return o


# ======================================================================= 石头
def paint_walls(cv: Cv, cave, air, mass, niche):
    # 后墙：凿出来的石壁（暗）
    tex = rt.cave_texture(cave, 9201)
    cv.a[cave] = tex[cave]
    # 实心的那块（平台、石阶、低处的地）：砌的石块，比后墙亮一档
    m2 = mass & ~niche
    rng = np.random.default_rng(9202)
    masonry(cv, m2, rng)
    sealed_arch(cv, 64, LOW, 28, 36, rng)
    # 上沿：最上面一行是被脚磨亮的一道高光（整条连续，不断开）；下面两行踏面亮、阶沿那一小段朝右下暗一档
    for x in range(FL, FR):
        fy = floor_y(x)
        steep = floor_y(x + 1) - fy >= 2 or fy - floor_y(x - 1) >= 2
        cols = (POLISH, MASS[4], MASS[3]) if steep else (POLISH, MASS[5], MASS[3])
        for d, c in zip((1, 2, 3), cols):
            y = fy + d
            if y < H and m2[y, x]:
                cv.px(x, y, c)
    # 阶下的洞：更暗的石壁，洞口一圈断面
    tn = rt.cave_texture(niche, 9203)
    darker = np.clip(tn[..., :3].astype(int) * 0.62, 0, 255).astype(np.uint8)
    cv.a[niche, :3] = darker[niche]
    r1 = dilate(niche, 1) & ~niche & mass
    cv.a[r1, :3] = rt.CRACK
    r2 = dilate(niche, 2) & ~niche & ~r1 & mass
    cv.a[r2, :3] = np.clip(cv.a[r2, :3].astype(int) * 0.8, 0, 255).astype(np.uint8)


def masonry(cv: Cv, m, rng, pal=MASS, base=(2, 3, 3, 4), hs=(7, 10), ws=(12, 26), y_ref=LOW + 1):
    """砌的石块：横缝一整行连续，竖缝每层错开、宽窄不一；每块自己一档深浅，块的上沿亮一档、下沿暗一档，缝是暗的那档；
    块里用小色团（不是棋盘格）偶尔差一档。横缝从 y_ref（低处地面下面那一行）往上、往下排，所以地面那一行正好是一道缝。"""
    h, w = m.shape
    ys = np.nonzero(m.any(axis=1))[0]
    if len(ys) == 0:
        return
    bounds = [y_ref]
    while bounds[0] > ys.min():
        bounds.insert(0, bounds[0] - int(rng.integers(hs[0], hs[1] + 1)))
    while bounds[-1] <= ys.max():
        bounds.append(bounds[-1] + int(rng.integers(hs[0], hs[1] + 1)))
    c = rt.clusters(h, w, rng)
    idx = np.zeros((h, w), int)
    for ya, yb in zip(bounds[:-1], bounds[1:]):
        x = -int(rng.integers(0, ws[1]))
        while x < w:
            bw = int(rng.integers(ws[0], ws[1] + 1))
            lv = int(base[int(rng.integers(0, len(base)))])
            for yy in range(max(0, ya), min(h, yb)):
                for xx in range(max(0, x), min(w, x + bw)):
                    k = lv
                    if yy == ya:
                        k = 1                                   # 横缝
                    elif xx == x:
                        k = 1                                   # 竖缝
                    else:
                        if yy == ya + 1:
                            k += 1                              # 块的上沿受光
                        elif yy == yb - 1:
                            k -= 1                              # 下沿背光
                        if xx == x + 1:
                            k += 1 if yy > ya + 1 else 0        # 缝右边一线亮（光从左上）
                        if c[yy, xx] > 0.78:
                            k += 1
                        elif c[yy, xx] < 0.16:
                            k -= 1
                    idx[yy, xx] = int(np.clip(k, 0, len(pal) - 1))
            x += bw
    for k in range(len(pal)):
        mm = m & (idx == k)
        cv.a[mm, :3] = pal[k]
        cv.a[mm, 3] = 255


def sealed_arch(cv: Cv, x, base, w, h, rng):
    """平台下面一道封起来的旧拱门（以前低处的门，水淹以后用石块砌死了）：一圈拱石（亮一档），里面小一号的石块（暗一档）。"""
    m = bm.opening_mask(w, h, "arch")
    inner = np.zeros((H, W), bool)
    inner[base - h + 1:base + 1, x:x + w] = m
    masonry(cv, inner, rng, base=(1, 2, 2, 3), hs=(5, 7), ws=(6, 11))
    ring = dilate(inner, 2) & ~inner
    ring[base + 1:] = False
    r_in = dilate(inner, 1) & ~inner
    cv.a[ring, :3] = MASS[4]
    cv.a[r_in & ring, :3] = MASS[1]
    top = dilate(ring, 1) & ~ring & ~inner
    top[base - h + 6:] = False
    cv.a[top & (cv.a[..., 3] > 0), :3] = MASS[5]


def old_waterline(cv: Cv, cave, air, rng):
    """低处墙根一道旧水位的湿痕（水退了留下的）：y 212 以下偏深偏湿，上沿一道不规则的痕（连续，起伏，不是虚线），几条往下淌的湿印。"""
    edge = 212 + np.round(ra.smooth1d(W, rng, 26, 1.6)).astype(int)
    nz = rt.vnoise(H, W, 6.0, rng)
    for x in range(FL, FR):
        for y in range(edge[x] - 16, edge[x]):              # 水痕上面一截慢慢变潮（两档，档边用噪声扰，不是一条横线）
            if cave[y, x]:
                k = (y - (edge[x] - 16)) / 16 + (nz[y, x] - 0.5) * 0.5
                if k > 0.35:
                    c = tuple(int(v) for v in cv.a[y, x, :3])
                    cv.a[y, x, :3] = bm.mixc(c, rt.WET[0], 0.12 if k < 0.7 else 0.22)
        for y in range(edge[x], LOW + 1):                   # 水痕以下：越靠地面越深越湿
            if cave[y, x]:
                c = tuple(int(v) for v in cv.a[y, x, :3])
                cv.a[y, x, :3] = bm.mixc(c, rt.WET[0], 0.35 if y < LOW - 6 else 0.48)
        y = edge[x]
        if cave[y, x] and x > SX0 + 40:
            cv.px(x, y, rt.WET[2])
    for _ in range(9):
        x = int(rng.integers(SX0 + 60, FR - 4))
        ln = int(rng.integers(4, 11))
        for d in range(ln):
            y = edge[x] + 1 + d
            if cave[y, x] and air[y, x]:
                c = tuple(int(v) for v in cv.a[y, x, :3])
                cv.a[y, x, :3] = bm.mixc(c, rt.WET[0], 0.5)


def seep(cv: Cv, cave, cy, rng):
    """顶上渗水：一道道从顶上往下淌的湿痕（一像素宽、连续、长短不一，偶尔往旁边错一格时补一格让上下有边相连）；
    拱窗窗台两头也往下淌两道（雨水顺着窗台流下来）。"""
    starts = [(x0, None) for x0 in (52, 141, 173, 226, 289, 371, 398, 411, 446, 461)] + [(WIN[0] + 1, WIN[1] + WIN[3] + 2),
                                                                                        (WIN[0] + WIN[2] - 2, WIN[1] + WIN[3] + 2)]
    for x0, y0 in starts:
        x = x0 + (int(rng.integers(-2, 3)) if y0 is None else 0)
        y = int(cy[x]) + 1 if y0 is None else y0
        ln = int(rng.integers(14, 52))
        for d in range(ln):
            if not (0 <= x < W) or not cave[y, x]:
                break
            c = tuple(int(v) for v in cv.a[y, x, :3])
            cv.a[y, x, :3] = bm.mixc(c, rt.WET[0], 0.55 if d < ln - 4 else 0.3)
            if rng.random() < 0.08:
                x += 1 if rng.random() < 0.5 else -1
                c = tuple(int(v) for v in cv.a[y, x, :3])
                cv.a[y, x, :3] = bm.mixc(c, rt.WET[0], 0.55)
            y += 1


def wall_blocks(cv: Cv, cave, air, cy, rng):
    """后墙是大块的条石（比石阶那块大得多）：横缝一层一层（高 18～26，有一点起伏），竖缝每层错开、宽窄不一。
    缝是暗一档的连续线，缝下面一行亮一点（石块的上沿受光）——看得出石头的走向，又不抢戏。"""
    wall = cave & air
    ys = []
    y = int(cy.min()) + 14
    while y < LOW:
        ys.append(y)
        y += int(rng.integers(18, 27))
    wav = ra.smooth1d(W, rng, 40, 1.2)
    top_c = rt.CAVE7[0]
    lit_c = rt.CAVE7[4]

    def mark(x, y, c, t):
        if 0 <= x < W and 0 <= y < H and wall[y, x] and y > cy[x] + 3:
            cv.a[y, x, :3] = bm.mixc(tuple(int(v) for v in cv.a[y, x, :3]), c, t)
    for i, y0 in enumerate(ys):
        prev_row = None
        row = [y0 + int(round(wav[x])) for x in range(W)]
        for x in range(FL, FR):
            mark(x, row[x], top_c, 0.5)
            if prev_row is not None and row[x] != prev_row:      # 起伏错一格：补一格，上下两段有边相连
                mark(x, prev_row, top_c, 0.5)
            mark(x, row[x] + 1, lit_c, 0.22)
            prev_row = row[x]
        if i + 1 < len(ys):
            nxt = ys[i + 1]
            x = FL - int(rng.integers(0, 40))
            while x < FR:
                x += int(rng.integers(26, 52))
                for yy in range(row[min(max(x, 0), W - 1)] + 1, nxt + int(round(wav[min(max(x, 0), W - 1)]))):
                    mark(x, yy, top_c, 0.45)
                    mark(x + 1, yy, lit_c, 0.18)


def plaster_patches(cv: Cv, cave, air, rng):
    """几块墙皮剥落的地方，露出里面的小砖（暗一档、砖小）：洞的上沿在墙皮的影子里（暗），下沿是墙皮断口受光（亮）。"""
    wall = cave & air
    nz = rt.vnoise(H, W, 6.0, rng)
    nz2 = rt.vnoise(H, W, 2.5, rng)
    for (cx, cy_, rx, ry) in ((232, 70, 17, 9), (441, 94, 11, 15), (122, 52, 10, 6)):
        m = np.zeros((H, W), bool)
        for y in range(cy_ - ry - 3, cy_ + ry + 4):
            for x in range(cx - rx - 3, cx + rx + 4):
                d = ((x - cx) / rx) ** 2 + ((y - cy_) / ry) ** 2 + (nz[y, x] - 0.5) * 1.6 + (nz2[y, x] - 0.5) * 0.6
                if d < 1 and wall[y, x]:
                    m[y, x] = True
        masonry(cv, m, rng, pal=rt.CAVE7, base=(1, 2, 2, 3), hs=(4, 5), ws=(7, 11), y_ref=cy_)
        ring = dilate(m, 1) & ~m & wall
        for y, x in zip(*np.nonzero(ring)):
            c = tuple(int(v) for v in cv.a[y, x, :3])
            cv.a[y, x, :3] = bm.mixc(c, rt.CAVE7[5], 0.45) if y > cy_ else bm.mixc(c, rt.CAVE7[0], 0.5)
        for y, x in zip(*np.nonzero(m)):
            if y - 1 >= 0 and not m[y - 1, x]:
                cv.a[y, x, :3] = rt.CAVE7[0]                       # 洞的上沿：墙皮的影子


def corner_moss(cv: Cv, cave, air, cy, rng):
    """墙角的苔：低处墙根（靠右门那一段）、平台墙根、顶上两个角。成团，下面厚上面薄，不撒点。"""
    spots = [(420, LOW, 9), (452, LOW, 7), (16, LAND, 8), (44, LAND, 5), (14, None, 7), (466, None, 6)]
    for (cx, base, w) in spots:
        for x in range(cx - w, cx + w + 1):
            if not (FL <= x < FR):
                continue
            th = 1 + (1 if abs(x - cx) < w * 0.6 else 0) + (1 if abs(x - cx) < w * 0.25 else 0)
            for d in range(th):
                if base is None:
                    y = int(cy[x]) + d + 1                       # 顶角：贴着顶往下长
                    col = MOSS[min(2, d)]
                else:
                    y = base - d
                    col = MOSS[min(2, th - 1 - d)]
                if 0 <= y < H and cave[y, x] and air[y, x]:
                    cv.px(x, y, col)


def light_falloff(cv: Cv, m, rng):
    """离灯越远越冷越暗：每个像素看最近的灯（含月光），远的往深靛蓝压两档（档边用噪声扰一下，不是一圈圈的硬线）。
    灯旁边的暖光由 hp.wall_light 推（之后做）。"""
    nz = rt.vnoise(H, W, 8.0, rng)
    yy, xx = np.mgrid[0:H, 0:W]
    near = np.zeros((H, W))
    for lp in LAMPS:
        lx, ly, lz, r, pw = lp[:5]
        d = np.hypot((xx - lx) / 1.2, yy - ly)
        near = np.maximum(near, np.clip(1 - d / (r * 1.9), 0, 1) * min(1.0, pw + 0.2))
    cache = {}
    cold = B(.035, .03, 266)
    for y, x in zip(*np.nonzero(m)):
        v = near[y, x] + (nz[y, x] - 0.5) * 0.18
        q = 0 if v > 0.42 else (1 if v > 0.18 else 2)
        if q == 0:
            continue
        c = tuple(int(t) for t in cv.a[y, x, :3])
        key = (c, q)
        if key not in cache:
            cache[key] = bm.mixc(c, cold, (0.0, 0.14, 0.27)[q])
        cv.a[y, x, :3] = cache[key]


def moon_pool(cv: Cv, rng):
    """月光竖直落到窗下的台阶和地面：地面边、墙根留一块冷亮的窗形亮斑（椭圆，边上用噪声扰成两档，柔和，不是硬边）。"""
    nz = rt.vnoise(H, W, 4.0, rng)
    cx, cy_ = (BEAM[0] + BEAM[1]) / 2, LOW - 1
    for y in range(cy_ - 14, LOW + 6):
        for x in range(BEAM[0] - 14, BEAM[1] + 15):
            if not cv.a[y, x, 3] or y > floor_y(x) + 3:
                continue
            d = math.hypot((x - cx) / ((BEAM[1] - BEAM[0]) / 2 + 9), (y - cy_) / 8.0) + (nz[y, x] - 0.5) * 0.3
            q = 2 if d < 0.55 else (1 if d < 1.0 else 0)
            if q:
                c = tuple(int(v) for v in cv.a[y, x, :3])
                cv.a[y, x, :3] = bm.mixc(c, B(.42, .035, 232), (0, 0.18, 0.34)[q])


def moss(cv: Cv, mass, rng):
    """石阶这块石头的上沿、靠墙根的几处长了一点苔（成团，不撒点）。"""
    for cx in (60, 132, 214, 302, 350, 452):
        cx += int(rng.integers(-6, 7))
        w = int(rng.integers(5, 10))
        for x in range(cx - w, cx + w):
            if not (FL <= x < FR):
                continue
            th = 1 + (1 if abs(x - cx) < w * 0.5 else 0) + (1 if abs(x - cx) < w * 0.2 else 0)
            for d in range(th):
                y = floor_y(x) + 3 + d
                if mass[y, x]:
                    cv.px(x, y, MOSS[min(2, th - 1 - d)])


def cut_opening(cv: Cv, x, y, w, h, kind="arch", sill=True, seed=0):
    """凿一个透的洞（门洞 / 窗）：中间镂空（透出后面的夜空层），看得出墙厚——左内壁朝右接月光（冷亮）、顶上内壁在影子里、
    右内壁一线暗；洞口外沿一道浅门楣，几处磨损；下面一道受光的石边（门槛 / 窗台），再下一道影子。返回镂空的 mask（整张图坐标）。"""
    rng = np.random.default_rng(seed + x * 7 + y * 13)
    m = bm.opening_mask(w, h, kind)
    hole = np.zeros((H, W), bool)
    dep = 3
    for yy in range(h):
        xs = np.nonzero(m[yy])[0]
        if len(xs) == 0:
            continue
        xl, xr = xs[0], xs[-1]
        for xx in xs:
            ytop = np.nonzero(m[:, xx])[0][0]
            if yy - ytop < dep:
                cv.px(x + xx, y + yy, DARK[0] if yy - ytop == 0 else DARK[1])      # 顶上内壁
            elif xx - xl < dep:
                cv.px(x + xx, y + yy, rt.ROCK8[5] if xx - xl == 0 else rt.ROCK8[3])   # 左内壁：朝右，接月光
            elif xr - xx < 1:
                cv.px(x + xx, y + yy, DARK[1])
            else:
                hole[y + yy, x + xx] = True
    for xx in range(w):
        ys = np.nonzero(m[:, xx])[0]
        if len(ys) and rng.random() < 0.8:
            cv.px(x + xx, y + ys[0] - 1, rt.ROCK8[4])                      # 门楣
    for _ in range(max(2, w // 5)):
        yy = int(rng.integers(3, h - 2))
        xs = np.nonzero(m[yy])[0]
        if len(xs):
            cv.px(x + xs[-1] + 1, y + yy, rt.ROCK8[6])
    if sill:
        sy = y + h
        cv.hline(x - 2, x + w + 2, sy, rt.ROCK8[6])
        cv.px(x + w + 1, sy, rt.RIM)
        cv.hline(x - 2, x + w + 2, sy + 1, rt.CRACK)
    return hole


# ======================================================================= 家具、灯、扶手（hp.Props 记形，最后按灯打光）
def rail_y(x):
    """扶手（后墙上，比阶面高 22，顺着石阶的直线，不跟着阶沿起伏）。"""
    if x <= SX0:
        return LAND - 22
    if x >= SX1:
        return LOW - 22
    return int(round(LAND - 22 + (x - SX0) * (LOW - LAND) / (SX1 - SX0)))


def handrail(p: hp.Props):
    """一根铁扶手：平台上从 x112 起，顺着石阶下去，到低处 x346 往下弯一小段收进墙上的托座。
    一像素粗、四邻接（错一格的地方补一格，让上下两段有边贴着，不只是角碰角）。托架：几根短竖铁接到墙上的托板。"""
    xs = list(range(112, 347))
    prev = None
    for x in xs:
        y = rail_y(x)
        pol = 0.5 + 0.24 * math.sin(math.pi * (x - xs[0]) / (xs[-1] - xs[0]))   # 中间那段手一直扶着，磨得最亮
        p.px(x, y, "iron", pol, hp.TOP, z=6.0)
        p.px(x, y + 1, "iron", 0.3, hp.FRONT, z=6.0)
        if prev is not None and y != prev:
            for yy in range(min(prev, y), max(prev, y) + 1):
                p.px(x - 1, yy, "iron", pol - 0.04, hp.TOP, z=6.0)
                p.px(x - 1, yy + 1, "iron", 0.3, hp.FRONT, z=6.0)
        prev = y
    # 两头：往下弯进墙上的托座（不是悬着的断头）
    for (x, d) in ((112, -1), (346, 1)):
        y = rail_y(x)
        for k in range(1, 4):
            p.px(x, y + 1 + k, "iron", 0.35, hp.LEFT if d < 0 else hp.RIGHT, z=6.0)
        p.rect(x - 1, y + 5, x + 1, y + 6, "iron", 0.28, hp.FRONT, z=5.0)
    # 托架：扶手下面一根短竖铁 + 墙上一块小托板
    for x in (140, 190, 240, 292, 330):
        y = rail_y(x) + 2
        for k in range(3):
            p.px(x, y + k, "iron", 0.3, hp.RIGHT, z=5.5)
        p.rect(x - 1, y + 3, x + 1, y + 4, "iron", 0.25, hp.FRONT, z=5.0)


def lamps(p: hp.Props, cy):
    # 平台：吊在系梁上的提灯
    x, y = LA[0], LA[1]
    p.lantern(x, y, cord_top=BEAM_Y + 7, cord="iron")     # 挂在系梁上（一根实的吊绳：链子一格亮一格暗会成点线，不用）
    # 石阶中间、柜台上方：墙上一块铁托板 + 横出来的托架，灯挂在托架头上
    for (x, y, side) in ((LB[0], LB[1], -1), (LC[0], LC[1], -1)):
        arm_y = y - 10
        wall_x = x + side * 9
        p.rect(wall_x - 1, arm_y - 2, wall_x + 1, arm_y + 2, "iron", 0.3, hp.FRONT, z=6.0)   # 托板
        for xx in range(min(wall_x, x), max(wall_x, x) + 1):
            p.px(xx, arm_y, "iron", 0.5, hp.TOP, z=7.0)
        # 托架下面一道斜撑：从托板下沿斜着撑到横杆（四邻接，两头都接上）
        for (dx, dy) in ((1, 3), (2, 3), (2, 2), (3, 2), (3, 1), (4, 1)):
            p.px(wall_x - side * dx, arm_y + dy, "iron", 0.33, hp.FRONT, z=7.0)
        p.lantern(x, y, cord_top=arm_y + 1, cord="iron")


def ceiling(p: hp.Props, cv: Cv, cy):
    """顶上：一根老木系梁横在拱顶下面（左头埋进墙里，右头用两道铁箍吊在顶上，端头看得到截面），梁下墙上一道影子；
    几处垂下来的根须（一像素、弯弯的、四邻接，根部接在顶上）。返回梁底那一行（平台的灯挂在梁上）。"""
    y0, y1 = BEAM_Y, BEAM_Y + 6
    xl = FL                                                              # 左头：埋进顶 / 墙里（顶以上的部分被 clip 掉，看着是从石头里伸出来的）
    xr = BEAM_XR
    p.box(xl, y0, xr, y1, "wood_d", t=0.42, z=6.0, top=1, grain=0.08)
    for x in range(xl + 3, xr - 2):                                      # 一道顺着梁的干裂（连续，两头收掉）
        if 0.12 < (x - xl) / (xr - xl) < 0.78:
            p.dt(x, y0 + 3, -0.12)
    p.rect(xr - 1, y0 + 1, xr, y1 - 1, "wood_l", 0.42, hp.RIGHT, z=6.1)  # 右头截面亮一点
    for sx in (BEAM_XR - 104, BEAM_XR - 6):                             # 铁箍：从顶上吊下来，绕梁一圈
        for y in range(int(cy[sx]), y0):
            p.px(sx, y, "iron", 0.34, hp.FRONT, z=6.5)
        for y in range(y0, y1 + 2):
            p.px(sx, y, "iron", 0.3, hp.FRONT, z=6.5)
            p.px(sx + 1, y, "iron", 0.4, hp.FRONT, z=6.5)
        p.px(sx - 1, y1 + 1, "iron", 0.3, hp.FRONT, z=6.5)
        p.px(sx + 2, y1 + 1, "iron", 0.3, hp.FRONT, z=6.5)
    for x in range(xl, xr + 1):                                          # 梁下墙上的影子（两行）
        for d in (1, 2):
            y = y1 + d
            if 0 <= y < H and cv.a[y, x, 3]:
                c = tuple(int(v) for v in cv.a[y, x, :3])
                cv.a[y, x, :3] = bm.mixc(c, DARK[0], 0.42 - 0.17 * d)
    rng = np.random.default_rng(9701)
    for (rx, ln) in ((312, 20), (316, 11), (378, 18), (383, 9), (459, 14)):
        x, y = rx, int(cy[rx])
        for d in range(ln):
            p.px(x, y, "wood_d", 0.34 + 0.04 * (d < 3), hp.FRONT, z=5.0)
            if d > 2 and rng.random() < 0.22:
                nx = x + (1 if rng.random() < 0.5 else -1)
                p.px(nx, y, "wood_d", 0.34, hp.FRONT, z=5.0)            # 往旁边错一格：同一行补上，上下有边相连
                x = nx
            y += 1


def landing(p: hp.Props):
    """平台：墙上一块小架板（有托），上面两个罐子、一截点着的蜡烛、一只瓶子；门边墙上钉着一个木挂钩挂着一把旧伞；
    石阶口墙上钉着一块指路的木牌（画着往右下的箭头和一道水波 = 往下是旧街）。"""
    p.shelf(64, 92, 94, mat="wood", t=0.36)
    p.jar(67, 93, 5, 6, mat="clay", label=False)
    p.jar(74, 93, 4, 5, mat="glaze_b", label=False)
    p.candle(84, 93, h=3)
    p.fx(87, 93, B(.16, .02, 256), z=4.0)              # 烛台小把手底下接到碟子上
    p.bottle(88, 93, 3, 8, mat="glass_g", label=False)
    # 挂钩 + 伞（伞把勾在钩上）
    hx, hy = 50, 84
    p.rect(hx - 1, hy - 1, hx + 1, hy + 1, "wood", 0.3, hp.FRONT, z=4.0)
    p.px(hx + 2, hy, "wood", 0.4, hp.TOP, z=4.0)
    p.px(hx + 2, hy + 1, "iron", 0.4, hp.FRONT, z=4.5)
    p.px(hx + 2, hy + 2, "iron", 0.4, hp.FRONT, z=4.5)
    p.px(hx + 3, hy + 2, "iron", 0.4, hp.FRONT, z=4.5)
    p.px(hx + 3, hy + 3, "iron", 0.4, hp.FRONT, z=4.5)
    for yy in range(hy + 3, hy + 30):
        p.px(hx + 4, yy, "wood_d", 0.32, hp.FRONT, z=4.5)
    top = hy + 8
    for yy in range(top, hy + 28):                     # 收起来的伞布：上窄下宽一点，裹着伞杆
        k = (yy - top) / 20
        half = 1 + int(round(1.6 * min(1.0, k * 1.6)))
        for xx in range(hx + 4 - half, hx + 4 + half + 1):
            if xx == hx + 4:
                continue
            u = (xx - (hx + 4)) / max(1, half)
            p.px(xx, yy, "cloth_t", 0.34 - 0.08 * abs(u), hp.nrm(u, 0, 0.9), z=5.0)
    p.px(hx + 4, hy + 30, "iron", 0.3, hp.FRONT, z=4.5)
    # 指路木牌：两颗钉子钉在墙上；刷的浅色漆：一个往下的箭头（实心箭头），旁边一道水波（四邻接的连续线）= 往下是旧街
    sx0, sy0, sx1, sy1 = 126, 67, 148, 77
    p.box(sx0, sy0, sx1, sy1, "wood_l", t=0.36, z=4.0, top=1, grain=0.05)
    paint = B(.56, .03, 228)
    ax = 133
    for y in range(sy0 + 2, sy0 + 6):
        p.fx(ax, y, paint, z=4.5)
    for k, half in enumerate((2, 1, 0)):
        for x in range(ax - half, ax + half + 1):
            p.fx(x, sy0 + 6 + k, paint, z=4.5)
    prev = None
    for x in range(137, 146):
        y = sy0 + 5 + int(round(1.0 * math.sin((x - 137) * 1.2)))
        p.fx(x, y, B(.5, .045, 220), z=4.5)
        if prev is not None and y != prev:
            p.fx(x, prev, B(.5, .045, 220), z=4.5)
        prev = y
    p.fx(sx0 + 2, sy0 + 1, B(.3, .02, 246), z=4.6)
    p.fx(sx1 - 2, sy0 + 1, B(.3, .02, 246), z=4.6)


def niche_things(p: hp.Props, niche):
    """阶下的洞：两只叠着的木箱、一只桶、一捆绳子，都放在地上。"""
    old = p.clip
    p.clip = niche
    p.crate(204, LOW, 20, 14, label=True)
    p.crate(208, LOW - 14, 14, 10, label=False)
    p.barrel(230, LOW, 12, 15, label=False)
    _rope_coil(p, 252, LOW, 14)
    p.clip = old


def _rope_coil(p: hp.Props, x, base, w):
    """一捆盘起来的绳子（侧面看：扁的一摞圈，一圈一圈亮暗交替）。"""
    for k in range(3):
        y0 = base - 2 * k
        x0, x1 = x + k, x + w - k
        for xx in range(x0, x1 + 1):
            u = (xx - (x0 + x1) / 2) / max(1, (x1 - x0) / 2)
            p.px(xx, y0, "rope", 0.34 - 0.06 * abs(u), hp.nrm(u, -0.3, 0.9), z=5.0)
            p.px(xx, y0 - 1, "rope", 0.42 - 0.06 * abs(u), hp.TOP, z=5.0)
    p.px(x + w // 2, base - 6, "rope", 0.4, hp.TOP, z=5.0)


def doors(p: hp.Props):
    """两扇往里开的木门板，贴在门洞旁边的墙上（铰链那一侧挨着门洞）：竖板、两道铁箍、门环。"""
    for (x0, x1, y0, y1) in ((DOOR_L[0] + DOOR_L[2] + 1, DOOR_L[0] + DOOR_L[2] + 8, DOOR_L[1] + 4, LAND),
                             (DOOR_R[0] - 9, DOOR_R[0] - 2, DOOR_R[1] + 5, LOW)):
        p.box(x0, y0, x1, y1, "wood", t=0.42, z=4.0, top=1, grain=0.06)
        for xx in range(x0 + 2, x1, 3):
            for yy in range(y0 + 1, y1):
                p.dt(xx, yy, -0.16)                    # 板缝：一整条连续的暗线（太浅了量化以后会断成一截一截）
        for yy in (y0 + 6, y1 - 7):
            p.hline(x0, x1, yy, "iron", 0.32, hp.FRONT, z=4.5)
        cx = (x0 + x1) // 2
        p.px(cx, (y0 + y1) // 2, "brass", 0.5, hp.FRONT, z=5.0)
        p.px(cx, (y0 + y1) // 2 + 1, "brass", 0.35, hp.FRONT, z=5.0)


def back_shelf(p: hp.Props):
    """柜台后面墙上的架子（水母右边）：一只瓶子、一个罐子、一个贝壳；门边墙上钉着一张手写的水位表（纸条，有图钉）。"""
    p.slip(426, 116, 13, 15, tilt=1, lines=5, pin=Wm(.42, .07, 40), curl=True)
    p.shelf(414, 432, 184, mat="wood", t=0.36)
    p.bottle(416, 183, 3, 7, mat="glass_b", label=False)
    p.jar(421, 183, 5, 5, mat="glaze", label=True)
    p.shell(429, 183, 2, 2)


def counter(p: hp.Props):
    """柜台（侧面看）：台面一块厚木板，两头各出一像素；正面竖板拼的，一道踢脚；台面上：铜铃、摊开的本子、一罐水里泡着个小贝壳。"""
    x0, x1, top = COUNTER
    p.box(x0 - 1, top, x1 + 1, top + 2, "wood_l", t=0.42, z=8.0, top=1, grain=0.04)
    p.box(x0, top + 3, x1, LOW - 2, "wood", t=0.33, z=7.0, top=0, grain=0.05)
    for xx in range(x0 + 4, x1 - 1, 7):
        for yy in range(top + 3, LOW - 2):
            p.px(xx, yy, "wood_d", 0.3, hp.FRONT, z=7.0)
    p.box(x0, LOW - 1, x1, LOW, "wood_d", t=0.26, z=7.0, top=1)
    # 正面一张小纸条（钉着）
    p.slip(x0 + 10, top + 7, 7, 6, tilt=0, lines=2, pin=Wm(.42, .07, 40))
    # 铜铃
    p.dome(368, top - 2, 3, 2, "brass", t=0.48, z=9.0)
    p.px(368, top - 5, "brass", 0.55, hp.TOP, z=9.0)
    p.hline(365, 371, top - 1, "brass", 0.3, hp.FRONT, z=9.0)
    # 摊开的本子 + 一支笔
    p.rect(376, top - 1, 389, top - 1, "paper", 0.52, hp.TOP, z=9.0)
    p.px(382, top - 2, "paper", 0.44, hp.TOP, z=9.0)
    p.px(383, top - 2, "paper", 0.44, hp.TOP, z=9.0)
    for (x, y) in ((386, top - 4), (387, top - 4), (387, top - 3), (388, top - 3), (389, top - 3), (389, top - 2), (390, top - 2)):
        p.px(x, y, "wood_d", 0.4, hp.FRONT, z=9.5)
    # 一罐水，里面一个小贝壳
    p.jar(404, top - 1, 6, 7, mat="glass_b", lid="cork", label=False)


# ======================================================================= 光层、剖面框
def build_light(air, hole_m):
    img = np.zeros((H, W, 4), np.uint8)
    # 每盏灯玻璃外一圈柔和的光晕：亮度往外慢慢掉（分几档，每档很淡），不是贴上去的两个硬圈
    for (lx, ly, lz, r, pw) in [LA[:5], LB[:5], LC[:5], LD[:5]]:
        r2 = 7.0 + 7.0 * pw
        for y in range(int(ly - r2) - 1, int(ly + r2) + 2):
            for x in range(int(lx - r2) - 1, int(lx + r2) + 2):
                if not (0 <= x < W and 0 <= y < H) or not air[y, x]:
                    continue
                d = math.hypot(x - lx, (y - ly) * 1.15)
                if d < r2:
                    a = int(round(34 * pw * (1 - d / r2) ** 1.6 / 4)) * 4
                    if a:
                        img[y, x] = (255, 212, 140, a)
    # 窗进来的月光：从窗台往下一条竖直的光带，上面亮、往下慢慢暗下去；左右两边各三像素柔和地淡掉
    x0, y0, w, h = WIN
    top = y0 + h + 2
    for y in range(top, LOW + 4):
        t = min(1.0, (y - top) / (LOW - top))
        base = 6 + 26 * (1 - t) ** 1.3
        for x in range(BEAM[0] - 3, BEAM[1] + 4):
            if not (0 <= x < W) or y > floor_y(x) + 2:
                continue
            e = min(x - (BEAM[0] - 4), (BEAM[1] + 4) - x)
            k = 1.0 if e >= 4 else (0.15, 0.35, 0.62)[max(0, e - 1)]
            a = int(round(base * k / 2)) * 2
            if a > 0 and img[y, x, 3] == 0:
                img[y, x] = (160, 184, 228, a)
    # 光落地的地方：一块窗形（椭圆）的亮斑，中间亮、往外柔和地淡掉
    cx, cy_ = (BEAM[0] + BEAM[1]) / 2, LOW - 1
    for y in range(cy_ - 12, LOW + 4):
        for x in range(BEAM[0] - 16, BEAM[1] + 17):
            if y > floor_y(x) + 2:
                continue
            d = math.hypot((x - cx) / ((BEAM[1] - BEAM[0]) / 2 + 12), (y - cy_) / 9.0)
            if d < 1:
                a = int(round(22 * (1 - d) ** 1.2 / 2)) * 2
                if a > img[y, x, 3]:
                    img[y, x] = (170, 194, 236, a)
    # 水母身后墙上一点淡淡的粉光（她自己会发光；她上下浮 3 像素，光圈够大盖得住）
    for y in range(176, 222):
        for x in range(JELLY_X - 24, JELLY_X + 25):
            if not air[y, x] or img[y, x, 3]:
                continue
            d = math.hypot((x - JELLY_X) / 1.2, y - 198)
            a = 14 if d <= 13 else (7 if d <= 21 else 0)
            if a:
                img[y, x] = (236, 196, 240, a)
    img[hole_m] = 0
    return img


def build_front(cave):
    """剖面框：屋外一圈是被剖开的石头（外面的石头质感），贴着屋的一圈暗缝、再往外一档暗；底边是地基。"""
    outside = ~cave
    # 石头在画面四边外面还接着：在大一圈的画布上算质感再裁回来，不然画面边上会多一圈「轮廓亮边」（顶上一排亮的断断续续，像点线）
    pad = 16
    big = np.pad(outside, pad, mode="edge")
    rock = rt.rock_texture(big, 9301, cracks=4, roots=2, moss=False)[pad:-pad, pad:-pad]
    cv = Cv(W, H)
    cv.a[outside] = rock[outside]
    r1 = dilate(cave, 1) & outside
    cv.a[r1, :3] = rt.CRACK
    r2 = dilate(cave, 2) & outside & ~r1
    cv.a[r2, :3] = np.clip(cv.a[r2, :3].astype(int) * 0.72, 0, 255).astype(np.uint8)
    cv.a[outside, 3] = 255
    # 前景剪影：画面最左边一根石柱（在人前面，拉出纵深；右边一线冷亮边是月光），从顶到底，轮廓每行最多差一像素
    # 柱子是一根粗糙的石柱：中间细（13 左右、慢慢起伏）、顶上和底下往外撇（接着顶和地）；里面暗的两档成大团（不撒点）
    rng = np.random.default_rng(9311)
    raw = 12 + ra.smooth1d(H, rng, 36, 2.4)
    yy = np.arange(H)
    raw += 9 * np.exp(-(yy / 34.0) ** 2) + 8 * np.exp(-((H - 1 - yy) / 30.0) ** 2)
    edge = np.zeros(H, int)
    for y in range(H):
        e = int(round(raw[y]))
        if y > 0:
            e = int(np.clip(e, edge[y - 1] - 1, edge[y - 1] + 1))     # 每行最多差一像素：轮廓连续，没有台阶
        edge[y] = e
    blob = rt.vnoise(H, W, 9.0, rng)
    for y in range(H):
        e = int(edge[y])
        for x in range(0, e + 1):
            cv.px(x, y, SIL[1] if (blob[y, x] > 0.62 and x < e - 1) else SIL[0])
        cv.px(e - 1, y, SIL[1])
        cv.px(e, y, SIL[2] if 24 < y < 244 else SIL[1])
    # 一截从顶上垂下来的旧绳子（两像素粗，轻轻弯，末端一个结、散开一点）；在晨头顶上面，不挡人
    cy = ceil_y()
    rx = 268
    y0 = int(cy[rx]) - 3
    end = 94
    for y in range(y0, end):
        t = (y - y0) / (end - y0)
        x = rx + int(round(2.0 * math.sin(t * math.pi * 0.9)))
        cv.px(x, y, SIL[1])
        cv.px(x + 1, y, SIL[2] if 0.15 < t < 0.9 else SIL[1])
    xe = rx + int(round(2.0 * math.sin(math.pi * 0.9)))
    cv.rect(xe - 1, end, xe + 3, end + 3, SIL[1])                      # 结
    cv.px(xe + 2, end, SIL[2])
    cv.vline(xe, end + 3, end + 7, SIL[1])                             # 散开的绳头
    cv.vline(xe + 2, end + 3, end + 6, SIL[1])
    return cv.a


# ======================================================================= 合起来
def build():
    cave, air, mass, niche, cy = masks()
    rng = np.random.default_rng(9001)
    back = Cv(W, H)
    paint_walls(back, cave, air, mass, niche)
    wall_blocks(back, cave, air, cy, rng)
    plaster_patches(back, cave, air, rng)
    old_waterline(back, cave, air, rng)
    moss(back, mass, rng)
    corner_moss(back, cave, air, cy, rng)
    seep(back, cave, cy, rng)
    hole = cut_opening(back, *DOOR_L, kind="arch", seed=1)
    hole |= cut_opening(back, *DOOR_R, kind="arch", seed=2)
    hole |= cut_opening(back, *WIN, kind="arch", seed=3)
    hole |= cut_opening(back, 188, 44, 11, 11, kind="round", sill=False, seed=4)    # 高处一只小圆窗
    # 窗：一道横的窗棂（木，两头接到窗洞的内壁上）
    wx, wy, ww, wh = WIN
    ty = wy + 40
    xs = [x for x in range(wx, wx + ww) if hole[ty, x]]
    p = hp.Props(W, H, seed=9400)
    p.clip = cave
    for x in range(xs[0] - 1, xs[-1] + 2):
        p.px(x, ty, "wood_d", 0.36, hp.TOP, z=4.0)
        p.px(x, ty + 1, "wood_d", 0.26, hp.FRONT, z=4.0)
    handrail(p)
    ceiling(p, back, cy)
    lamps(p, cy)
    landing(p)
    niche_things(p, niche)
    doors(p)
    back_shelf(p)
    lit = cave & (back.a[..., 3] > 0) & ~hole
    light_falloff(back, lit, np.random.default_rng(9032))
    moon_pool(back, np.random.default_rng(9033))
    hp.wall_light(back.a, lit, LAMPS, p.cast, np.random.default_rng(9031), strength=1.3)
    pr = p.render(LAMPS)
    pm = pr[..., 3] > 0
    back.a[pm] = pr[pm]
    floor_water(back, hole)
    back.a[hole] = 0
    back.a[~cave] = (0, 0, 0, 0)              # 框外交给 front

    pc = hp.Props(W, H, seed=9500)
    counter(pc)
    cnt = pc.render(LAMPS)

    light = build_light(air, hole)
    front = build_front(cave)
    return back.a, cnt, light, front, pr


def floor_water(cv: Cv, hole):
    """通旧街的门槛前地上一层薄水（门外的水渗进来）：靠门最深，往左越来越薄；几道亮的反光（不等距）。"""
    rng = np.random.default_rng(9601)
    W0 = [B(.13, .035, 236), B(.18, .04, 228), B(.3, .035, 222), B(.45, .03, 230)]
    for x in range(410, FR):
        depth = 1 + (1 if x > 432 else 0) + (1 if x > 446 else 0)
        for d in range(depth):
            y = LOW - d
            if cv.a[y, x, 3] and not hole[y, x]:
                c = tuple(int(v) for v in cv.a[y, x, :3])
                cv.a[y, x, :3] = bm.mixc(c, W0[0 if d else 1], 0.55)
    for x in sorted(rng.choice(np.arange(414, FR - 2), 6, replace=False)):
        ln = int(rng.integers(1, 4))
        for k in range(ln):
            if not hole[LOW, x + k]:
                cv.px(x + k, LOW, W0[3] if k == 0 else W0[2])


def room_json():
    return {
        "_note": "tools/river_stairwell_art.py 生成，别手改。约定见 docs/river_rooms_contract.md。市集右头的门 → 这里（平台）→ 石阶往下 → 右下的门 → 旧街。",
        "size": [W, H],
        "origin": [2400, -270],
        "env": "river",
        "bg": ["#03060f", "#0a1424"],
        "layers": [
            {"id": "sky", "img": "res://art/river_city/market/sky.png", "scroll": 0.0, "y": 0},
            {"id": "ridge", "img": "res://art/river/ridge.png", "scroll": 0.05, "y": 46, "tile": True},
            {"id": "mist", "img": "res://art/river/mist.png", "scroll": 0.1, "y": 46, "tile": True, "drift": -2.5},
            {"id": "glints", "img": "res://art/river_city/market/moonpath.png", "scroll": 0.0, "y": 197, "shader": "moonpath",
             "shader_params": {"speed": 1.0, "wobble": 1.5, "flicker": 0.9}},
            {"id": "far", "img": "res://art/river_city/market/far.png", "scroll": 0.2, "y": 0, "tile": True},
            {"id": "back", "img": "back.png", "scroll": 1.0, "y": 0},
            {"id": "counter", "img": "counter.png", "scroll": 1.0, "y": 0, "z": -1},
            {"id": "light", "img": "light.png", "scroll": 1.0, "y": 0, "z": -1},
            {"id": "front", "img": "front.png", "scroll": 1.0, "y": 0, "front": True},
        ],
        "ground": ground_pts(),
        "walk": [26, 462],
        "markers": {"stairwell_up": 30, "stairwell_top": 72, "stairwell_counter": 370, "stairwell_jelly": JELLY_X, "stairwell_down": 448},
        "residents": [{"who": "jellyfish", "at": "stairwell_jelly", "z": -2, "face": 1}],
        "portals": [
            {"edge": "left", "to": "market", "at": "market_from_stairwell", "kind": "walk_fade"},
            {"edge": "right", "to": "oldstreet", "at": "oldstreet_entry", "kind": "pan_down", "need": ["river_oldstreet"]},
        ],
        "ambient": [{"name": "river_flow", "db": -26}],
        "scripts": [{"script": "res://scripts/dust_motes.gd", "x": 0, "y": 0, "z": -1,
                     "params": {"rect": [BEAM[0] + 1, WIN[1] + WIN[3] + 4, BEAM[1] - BEAM[0] - 2, LOW - 12 - (WIN[1] + WIN[3] + 4)],
                                "count": 6, "seed": 7}}],
    }


# ======================================================================= 水母（美术姐的图，只还原尺寸）
def jelly(src: Path):
    a = np.array(Image.open(src).convert("RGBA"))
    assert a.shape[:2] == (480, 480), a.shape
    s = 15
    for by in range(32):                      # 确认是 15 倍放大的整格像素画（每格一个颜色），取样才是无损的
        for bx in range(32):
            blk = a[by * s:(by + 1) * s, bx * s:(bx + 1) * s].reshape(-1, 4)
            assert (blk == blk[0]).all(), (bx, by)
    small = a[s // 2::s, s // 2::s]
    JELLY.mkdir(parents=True, exist_ok=True)
    Image.fromarray(small, "RGBA").save(JELLY / "jellyfish.png")
    shutil.copyfile(src, JELLY / "jellyfish_480.png")
    print("ok jellyfish", small.shape)


# ======================================================================= 检查：只有对角相连、细线缺口、直角台阶
def check_thin(img, name):
    """细线（1 像素宽的竖 / 斜线）错一格时只有角碰角：找「这一格和右下 / 左下有东西，但它们之间的两个边邻居都是空的」。
    只看前景（alpha）——back 是满的，所以对 back 只看 Props 那层，调用的人传进来。"""
    a = img[..., 3] > 0
    bad = []
    h, w = a.shape
    for y in range(h - 1):
        for x in range(w - 1):
            if a[y, x] and a[y + 1, x + 1] and not a[y, x + 1] and not a[y + 1, x]:
                bad.append((x, y, "\\"))
            if a[y, x + 1] and a[y + 1, x] and not a[y, x] and not a[y + 1, x + 1]:
                bad.append((x, y, "/"))
    print(f"{name}: 只有对角相连 {len(bad)} 处", bad[:12])
    return bad


def check_steps(fn=floor_y):
    jumps = [(x, fn(x + 1) - fn(x)) for x in range(W - 1) if abs(fn(x + 1) - fn(x)) > 2]
    print("地面轮廓：一列跳 ≥3 像素的地方", jumps)


def hand_edited():
    p = ROOT / "art" / "手改清单.json"
    return set(json.loads(p.read_text()).get("files", {})) if p.exists() else set()


def preview(path, back, cnt, light, front, chen_x=None):
    """按 room.json 叠一屏（夜空层 + back + 水母 + counter + light + front），放大 2 倍。月光倒影用河岸的 moonpath_rgb 近似。"""
    j = room_json()
    out = Image.new("RGBA", (W, H), (3, 6, 15, 255))
    for l in j["layers"]:
        if l["id"] in ("back", "counter", "light", "front"):
            continue
        src = l["img"]
        im = Image.open(ROOT / src[6:]).convert("RGBA")
        if l.get("shader") == "moonpath":
            im = Image.fromarray(bm.moonpath_rgb(np.array(im), 0))
        lay = Image.new("RGBA", (W, H))
        lay.paste(im, (0, l.get("y", 0)))
        out.alpha_composite(lay)
    out.alpha_composite(Image.fromarray(back))
    jf = JELLY / "jellyfish.png"
    if jf.exists():
        js = Image.open(jf).convert("RGBA")
        cfg = json.loads((JELLY / "jellyfish.json").read_text()) if (JELLY / "jellyfish.json").exists() else {}
        ax, ay = cfg.get("anchor", [15, 30])
        hov = cfg.get("hover", 14)
        out.alpha_composite(js, (JELLY_X - ax, LOW - ay - 1 - hov))
    out.alpha_composite(Image.fromarray(cnt))
    out.alpha_composite(Image.fromarray(light))
    sc = j["scripts"][0]["params"]                       # 光带里的灰尘（游戏里是 dust_motes.gd 在动），预览画一帧
    r = np.random.default_rng(sc["seed"])
    for _ in range(sc["count"]):
        dx, dy = int(r.integers(0, sc["rect"][2])), int(r.integers(0, sc["rect"][3]))
        k = dy / sc["rect"][3]
        c = tuple(int(round(a + (b - a) * k)) for a, b in zip((189, 204, 235), (51, 64, 92)))
        out.putpixel((sc["rect"][0] + dx, sc["rect"][1] + dy), c + (255,))
    if chen_x is not None:
        lay = Image.new("RGBA", (W, H))
        px = lay.load()
        for cx in chen_x:
            gy = floor_y(cx)
            for yy in range(gy - 37, gy + 1):
                for xx in range(cx - 4, cx + 4):
                    px[xx, yy] = (226, 222, 214, 255) if yy < gy - 29 else (120, 70, 60, 255)
        out.alpha_composite(lay)
    out.alpha_composite(Image.fromarray(front))
    out.save(path)
    out.resize((W * 3, H * 3), Image.NEAREST).save(str(path).replace(".png", "_3x.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    ap.add_argument("--jelly", default="")
    args = ap.parse_args()
    if args.jelly:
        jelly(Path(args.jelly))
    back, cnt, light, front, props = build()
    check_thin(props, "back 里的家具和细线")
    check_thin(cnt, "counter")
    for a, nm in ((back, "back"), (cnt, "counter"), (front, "front")):
        al = a[..., 3]
        bad = ((al > 0) & (al < 255)).sum()
        if bad:
            print("半透明像素：", nm, bad)
    check_steps()
    OUT.mkdir(parents=True, exist_ok=True)
    locked = hand_edited()

    def save(arr, name):
        rel = (OUT / name).relative_to(ROOT).as_posix()
        if rel in locked:
            print("跳过（作者手改，见 art/手改清单.json）:", rel)
            return
        Image.fromarray(arr, "RGBA").save(OUT / name)
    save(back, "back.png")
    save(cnt, "counter.png")
    save(light, "light.png")
    save(front, "front.png")
    rj = OUT / "room.json"
    if rj.relative_to(ROOT).as_posix() not in locked:
        rj.write_text(json.dumps(room_json(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ok stairwell", W, H)
    if args.preview:
        pv = Path(args.preview)
        pv.mkdir(parents=True, exist_ok=True)
        preview(pv / "stairwell.png", back, cnt, light, front)
        preview(pv / "stairwell_chen.png", back, cnt, light, front, chen_x=[40, 200, 300, 380])


if __name__ == "__main__":
    main()
