"""河流篇 · 妮芙家 river_home（第三版：一整块巨石被一点点掏空，里面好几个小洞屋层层叠叠，石阶往上）。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_home_rooms_art.py [--preview 目录]

作者（10-30）：「还是一个大客厅……想分房间，里面有很多房间，层层叠叠，有一点高度差异，你还能往上」；
主对话补充：别排成方格表——每间屋是大小不一、凿出来的不规则洞（拱顶 / 斜顶、弧墙），同一层地面也错开一两级，
房间之间的石壁厚薄不一，有的屋只露出一半；石头要有质感（见 tools/river_rock_tex.py 开头）。

  L0（地面，和河岸同高 y279）：门厅（门、雨衣）→ 厨房（罐子、灶台）→ 上两级到餐桌（沙漏、本子、吊灯、条子板）
                              → 厚石壁里的矮门洞 → 储物（标签箱子、旧门牌、地上一层薄水）→ 楼梯井 1（石阶贴着后壁从右往左上）
  L1（y199）：楼梯井 2（高高的拱，石阶从左往右上，阶下塞箱子）→ 上一级到卧室（妮芙睡的石水盆）→ 收藏间（高，索引柜、影像机、格子架）
  L2：阁楼（y129，来客册档案，顶斜）→ 几级台阶 → 窗台（y94，大窗、晾来客册、椅子）
  右上：一间只露出一半的小储藏室（不能进，圆窗里一点灯）。

家具：tools/river_home_art.py（会话 D）的家具层——把它的灰泥墙（shell）换成空的再 build_back，只剩家具，
上河岸会话的月夜色（river_bank_moon_art.moon_interior），按块挪进各个洞里（裁到洞的形状里）；物件（桌面、沙漏、本子、照片、
来客册、椅子、柜门、影像机、标签）跟着它所在那块家具一起挪，来客册一帧横跨两层（桌上那半 / 窗台那半分别挪）。
石头：tools/river_rock_tex.py（岩层 + 节理 + 小色团 + 月光亮边 + 苔 + 水渍 + 根须）；凿的门窗：这里的 carve_opening。
所有随机固定 seed，back / front / 物件的 alpha 只有 0/255（light 是半透明的光层）。

输出 art/river_home/：home_back / home_front / home_light、obj_*.png、room.json（levels / stairs / markers / objects）。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import river_bank_moon_art as bm  # noqa: E402
from river_bank_moon_art import B, Wm, WARM, MOSS, Cv  # noqa: E402
import river_art as ra  # noqa: E402
import river_rock_tex as rt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "river_home"

W, H = 420, 280
F0, F1 = 279, 199                 # L0、L1 的地面（脚底那一行）
F0D = 276                         # 餐桌那一截高两级
F1B = 196                         # 卧室高一级
F2A, F2B = 129, 94                # L2：阁楼、窗台
HOME_X = bm.HOME_X                # 底边中点在河岸的 x（和河岸的门、门牌对得上）
DOOR_X = 48
DFL = 175                         # D 的地板（脚底那一行，D 坐标）

# 每层能走的地面（折线，图里的坐标）——房间之间错开一两级
L0_FLOOR = [[20, F0], [134, F0], [138, F0D], [222, F0D], [226, F0], [406, F0]]
L1_FLOOR = [[20, F1], [110, F1], [113, F1B], [198, F1B], [202, F1], [342, F1]]
L2_FLOOR = [[94, F2A], [172, F2A], [206, F2B], [320, F2B]]
STAIR1 = (402, F0, 337, F1)       # 楼梯井 1：从 L0 最右往左上到 L1
STAIR2 = (28, F1, 100, F2A)       # 楼梯井 2：从 L1 最左往右上到 L2
RAMP = (172, F2A, 206, F2B)       # 阁楼 → 窗台

# 洞（凿空的地方）：x0, x1, 地面折线（None = 用所在层的）, 顶的控制点 [(x, y)]
CAVES = {
    "hall":    (20, 70, L0_FLOOR, [(20, 212), (44, 205), (70, 210)]),
    "p_hk":    (64, 78, L0_FLOOR, [(64, 228), (71, 224), (78, 228)]),
    "kitchen": (72, 138, L0_FLOOR, [(72, 211), (96, 206), (138, 213)]),
    "dining":  (134, 222, L0_FLOOR, [(134, 214), (178, 205), (222, 215)]),
    "p_ds":    (218, 238, L0_FLOOR, [(218, 234), (228, 229), (238, 234)]),
    "store":   (232, 340, L0_FLOOR, [(232, 228), (268, 221), (340, 226)]),
    "shaft1":  (338, 409, L0_FLOOR, [(338, 206), (348, 156), (366, 136), (392, 132), (409, 150)]),
    "p_cs":    (316, 344, L1_FLOOR, [(316, 156), (330, 149), (344, 156)]),
    "coll":    (206, 322, L1_FLOOR, [(206, 108), (258, 101), (322, 110)]),
    "p_bc":    (194, 212, L1_FLOOR, [(194, 154), (203, 149), (212, 154)]),
    "bed":     (116, 200, L1_FLOOR, [(116, 154), (152, 146), (200, 152)]),
    "p_sb":    (100, 120, L1_FLOOR, [(100, 156), (110, 151), (120, 156)]),
    "shaft2":  (20, 106, L1_FLOOR, [(20, 104), (36, 70), (66, 58), (106, 70)]),
    "p_sa":    (98, 116, L2_FLOOR, [(98, 86), (107, 81), (116, 86)]),
    "attic":   (110, 178, L2_FLOOR, [(110, 88), (140, 80), (178, 74)]),
    "ramp":    (170, 210, L2_FLOOR, [(170, 76), (190, 56), (210, 40)]),
    "win":     (204, 320, L2_FLOOR, [(204, 40), (258, 24), (320, 34)]),
}
NOOK = (330, 394, 68, 118)        # 右上只露出一半的小储藏室（x0, x1, 顶, 底）

# 家具块（D 坐标的框 x0, y0, x1, y1）→ 挪多少（dx, dy）、贴进哪个洞
PIECES = {
    "coat":    ((18, 100, 33, 146), (0, 112), "hall"),
    "door":    ((30, 108, 68, 176), (0, 104), "hall"),
    "kitchen": ((68, 108, 134, 176), (4, 104), "kitchen"),
    "jars":    ((66, 80, 135, 100), (170, 148), "store"),
    "board":   ((144, 106, 201, 141), (6, 101), "dining"),
    "dining":  ((128, 150, 216, 176), (6, 101), "dining"),
    "lamp":    ((166, 98, 180, 108), (8, 116), "dining"),
    "cabinet": ((284, 80, 333, 176), (-76, 24), "coll"),
    "stand":   ((326, 118, 370, 176), (-70, 24), "coll"),
    "shelves": ((369, 80, 403, 176), (-71, 24), "coll"),
    "map":     ((32, 64, 66, 92), (126, 88), "bed"),
    "note":    ((18, 85, 35, 99), (22, 88), "shaft2"),
    "window":  ((214, 74, 292, 136), (10, -47), "win"),
}

# 屋里的灯（灯芯 x, y, 光的半径）
LAMPS = [(186, 220, 52), (264, 128, 46), (154, 166, 34), (140, 96, 30), (372, 176, 34), (62, 120, 34), (292, 252, 26),
         (360, 98, 14)]
PAPER = B(.36, .018, 90)
TAG = Wm(.48, .06, 70)
TAG_ON = Wm(.62, .08, 76)
WOODS = [B(.07, .018, 262), B(.095, .02, 258), B(.12, .022, 254), B(.155, .024, 250), B(.2, .026, 246)]
WATER = [B(.13, .035, 236), B(.18, .04, 228), B(.3, .035, 222), B(.45, .03, 230)]
IRON = B(.08, .015, 262)
CAVE = rt.CAVE7


# ======================================================================= 形
def interp(pts, x):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return float(np.interp(x, xs, ys))


def smooth_ceiling(pts, x0, x1):
    """顶：控制点之间插值，再用余弦平滑（拱 / 斜都圆滑），两头的角磨圆。"""
    xs = np.arange(x0, x1)
    raw = np.array([interp(pts, x) for x in xs])
    k = np.array([1, 4, 6, 4, 1], float)
    k /= k.sum()
    pad = np.pad(raw, 2, mode="edge")
    sm = np.convolve(pad, k, mode="valid")
    r = 5
    for i, x in enumerate(xs):
        d = min(x - x0, x1 - 1 - x)
        if d < r:
            sm[i] += r - math.sqrt(max(0.0, r * r - (r - d) ** 2))
    return sm


def cave_masks():
    """每个洞的 mask（dict）和合起来的一张。地面那一行（脚底）算在洞里；墙根磨圆一像素。"""
    out = {}
    allm = np.zeros((H, W), bool)
    for name, (x0, x1, fl, ceil) in CAVES.items():
        m = np.zeros((H, W), bool)
        cs = smooth_ceiling(ceil, x0, x1)
        for i, x in enumerate(range(x0, x1)):
            f = int(round(interp(fl, x)))
            if name == "ramp":
                f = int(round(np.interp(x, [RAMP[0], RAMP[2]], [RAMP[1], RAMP[3]])))
            c = int(round(cs[i]))
            if x in (x0, x1 - 1):
                f -= 1
            m[max(0, c):f + 1, x] = True
        out[name] = m
        allm |= m
    return out, allm


def rock_mask():
    """巨石的形：底宽、两边微鼓、往上收成一个歪的圆顶；左肩低一点，右边一截矮的鼓包（小储藏室在里面）。"""
    rng = np.random.default_rng(7101)
    # 三根柱头长在一起：左（楼梯井 2 顶上）、中间最高（窗台顶上）、右边矮的（小储藏室）；柱头之间是往下凹的豁口
    top_pts = [(5, 96), (9, 60), (22, 44), (52, 36), (84, 40), (100, 52), (108, 62), (116, 58), (130, 34), (160, 14),
               (200, 6), (246, 3), (292, 8), (316, 18), (324, 40), (330, 58), (338, 62), (346, 54), (366, 50), (392, 52),
               (408, 70), (414, 104), (416, 140)]
    nz = ra.smooth1d(W, rng, 16, 2.2)
    nl = ra.smooth1d(H, rng, 30, 1.6)
    m = np.zeros((H, W), bool)
    for x in range(W):
        t = interp(top_pts, x) + nz[x]
        for y in range(int(max(0, t)), H):
            xl = 6 + nl[y] - 3 * max(0.0, (y - 250) / 30.0)          # 底下往外撇一点（脚）
            xr = 414 - nl[(y * 7) % H] * 0.8 + 3 * max(0.0, (y - 250) / 30.0)
            if xl <= x <= xr:
                m[y, x] = True
    return m


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


def stair_y(st, x):
    xa, ya, xb, yb = st
    k = min(1.0, max(0.0, (x - xa) / (xb - xa)))
    return int(round(ya + (yb - ya) * k))


# ======================================================================= 屋里
def paint_caves(back: Cv, masks, allm):
    """洞里的石壁（凿出来的，暗），每个洞自己一张（岩层、凿痕各不相同）；洞口四周一圈断面。"""
    for i, (name, m) in enumerate(masks.items()):
        tex = rt.cave_texture(m, 7300 + i * 17)
        back.a[m] = tex[m]
    # 断面：洞外一圈（石头被剖开的切口）——贴着洞最暗、往外一档；地面（洞底下那两行）是踩亮的石面
    r1 = dilate(allm, 1) & ~allm
    r2 = dilate(allm, 2) & ~allm & ~r1
    rp = rt.ROCK8
    back.a[r1, :3] = rt.CRACK
    sub = back.a[r2, :3].astype(int)
    back.a[r2, :3] = np.clip(sub * 0.75, 0, 255).astype(np.uint8)
    below = np.zeros_like(allm)
    below[1:] = allm[:-1]
    below &= ~allm
    below2 = np.zeros_like(allm)
    below2[1:] = below[:-1]
    below2 &= ~allm
    back.a[below, :3] = rp[5]
    back.a[below2, :3] = rp[3]


def draw_steps(cv: Cv, st, cavem, body=11, pal=CAVE):
    """凿在后壁上的石阶（凸出来一块）：一级级的踏面（上沿一道亮）、踢面暗、台阶下面是实的一条斜石（越往下越暗）。"""
    xa, ya, xb, yb = st
    n = max(2, int(round(abs(ya - yb) / 6.5)))
    rise = (ya - yb) / n
    run = (xb - xa) / n
    sgn = 1 if xb > xa else -1
    rng = np.random.default_rng(xa * 7 + ya)
    for i in range(n):
        tx0, tx1 = xa + run * i, xa + run * (i + 1)
        top = int(round(ya - rise * (i + 1)))
        lo, hi = sorted((int(round(tx0)), int(round(tx1))))
        for x in range(lo - (1 if sgn < 0 else 0), hi + (1 if sgn > 0 else 0)):
            bot = stair_y(st, x) + body
            for y in range(top, min(bot, H)):
                if not cavem[y, x]:
                    continue
                d = y - top
                if d == 0:
                    c = pal[6]
                elif d == 1:
                    c = pal[5]
                else:
                    k = 4 - min(3, (d - 2) // 4)
                    c = pal[k] if rng.random() > 0.18 else pal[max(0, k - 1)]
                cv.px(x, y, c)
        ex = hi if sgn < 0 else lo
        for y in range(top + 1, int(round(top + rise)) + 1):
            if 0 <= y < H and cavem[y, ex]:
                cv.px(ex, y, pal[1])
    for x in range(min(xa, xb), max(xa, xb) + 1):
        y = stair_y(st, x) + body
        if 0 <= y < H and cavem[y, x]:
            cv.px(x, y, pal[0])
            if y + 1 < H and cavem[y + 1, x]:
                cv.px(x, y + 1, pal[1])


def crate(cv: Cv, x0, y0, w, h, labels: list, wet=False):
    cv.rect(x0, y0, x0 + w, y0 + h, WOODS[2])
    for yy in range(y0 + 4, y0 + h, 5):
        cv.hline(x0 + 1, x0 + w - 1, yy, WOODS[1])
    cv.hline(x0, x0 + w, y0, WOODS[4])
    cv.vline(x0 + w - 1, y0, y0 + h, WOODS[3])
    cv.vline(x0, y0, y0 + h, WOODS[0])
    if wet:
        for yy in range(y0 + h - 3, y0 + h):
            for xx in range(x0 + 1, x0 + w - 1):
                if (xx * 3 + yy) % 4:
                    cv.px(xx, yy, B(.08, .024, 236))
    lx, ly = x0 + w // 2 - 2, y0 + 3
    cv.rect(lx, ly, lx + 5, ly + 3, PAPER)
    cv.hline(lx + 1, lx + 4, ly + 1, WOODS[1])
    labels.append((lx, ly, 5, 3))


def paper_note(cv: Cv, x, y, w, h, labels=None):
    cv.rect(x, y, x + w, y + h, PAPER)
    cv.hline(x + 1, x + w - 1, y + 1, B(.22, .02, 250))
    if h > 4:
        cv.hline(x + 1, x + w - 2, y + 3, B(.22, .02, 250))
    cv.px(x + w // 2, y - 1, B(.3, .02, 40))
    if labels is not None:
        labels.append((x, y, w, h))


def lamp(cv: Cv, x, y, cord_top=None, kind="hang"):
    """一盏小灯（灯芯 x, y）：hang = 从顶上垂下来的铁框小提灯；candle = 一截蜡烛 + 一小团火。光落到墙上由 warm_spill 管。"""
    if kind == "candle":
        cv.rect(x - 1, y, x + 1, y + 4, B(.5, .02, 90))
        cv.px(x - 1, y - 1, WARM[3])
        cv.px(x - 1, y - 2, WARM[4])
        cv.hline(x - 3, x + 2, y + 4, IRON)
        return
    if cord_top is not None:
        cv.vline(x, cord_top, y - 2, IRON)
    cv.rect(x - 2, y - 2, x + 3, y - 1, IRON)
    cv.rect(x - 2, y - 1, x + 3, y + 3, WARM[3])
    cv.px(x, y, WARM[4])
    cv.px(x, y + 1, WARM[4])
    cv.vline(x - 2, y - 1, y + 3, WARM[2])
    cv.rect(x - 2, y + 3, x + 3, y + 4, IRON)


def paint_store(cv: Cv, labels):
    """储物：一排罐子（D 厨房最上面那层搁板挪过来）、几只泡过水的箱子、墙上一排旧门牌（河涨一次换一个，妮芙都留着）、
    挂钩上一卷绳，地上漫着一层薄水（底层泡着一点水），石阶下面的三角空当里也塞了箱子。"""
    for (cx, cy, w, h) in ((240, F0 - 18, 22, 18), (264, F0 - 14, 18, 14), (244, F0 - 32, 16, 14), (318, F0 - 20, 20, 20),
                           (342, F0 - 14, 16, 14), (360, F0 - 10, 12, 10)):
        crate(cv, cx, cy, w, h, labels, wet=True)
    for i in range(4):
        px_ = 288 + i * 8
        py = 236 + (i % 2) * 3
        cv.rect(px_, py, px_ + 7, py + 5, Wm(.27 + 0.03 * i, .03, 74))
        cv.hline(px_ + 1, px_ + 6, py + 2, B(.12, .02, 250))
        cv.px(px_ + 3, py - 1, WOODS[3])
        cv.rect(px_ + 1, py + 6, px_ + 5, py + 8, PAPER)
        labels.append((px_ + 1, py + 6, 4, 2))
    for r_, k in ((5, 1), (4, 2), (2, 0)):
        cv.ellipse(300, F0 - 4, r_ + 1, 2, WOODS[k])
    lamp(cv, 292, 252, kind="candle")


def floor_water(cv: Cv, x0, x1, m):
    """地上一层薄水：靠墙最深；几道亮的反光（月光从门口进来）。"""
    rng = np.random.default_rng(7211)
    for x in range(x0, x1):
        depth = 2 + (1 if (x * 7) % 13 < 4 else 0)
        for d in range(depth):
            y = F0 - d
            if m[y, x] and cv.a[y, x, 3]:
                c = tuple(int(v) for v in cv.a[y, x, :3])
                cv.a[y, x, :3] = bm.mixc(c, WATER[0 if d else 1], 0.55)
        if rng.random() < 0.12:
            cv.px(x, F0 - 1, WATER[3] if rng.random() < 0.4 else WATER[2])


def paint_bed(cv: Cv, labels):
    """卧室：妮芙睡在一个凿出来的石水盆里（鲸鱼妹），盆沿搭一条毯子；床头墙上贴满提醒条，一块小搁板、一截蜡烛。"""
    bx0, bx1, by = 124, 186, F1B - 15
    for x in range(bx0, bx1):
        u = (x - (bx0 + bx1) / 2) / ((bx1 - bx0) / 2)
        depth = int(round(13 * math.sqrt(max(0, 1 - u * u))))
        for y in range(by, by + depth + 2):
            c = CAVE[4] if y == by + depth + 1 else CAVE[3]
            if y <= by + 1:
                c = CAVE[5]
            cv.px(x, y, c)
        cv.px(x, by - 1, CAVE[6] if abs(u) < 0.95 else CAVE[5])
    for x in range(bx0 + 4, bx1 - 4):
        cv.px(x, by, WATER[2] if (x // 3) % 3 else WATER[3])
        cv.px(x, by + 1, WATER[1])
    for x in range(bx1 - 16, bx1 - 2):
        for y in range(by - 3, by + 4 + (x % 3 == 0)):
            cv.px(x, y, B(.3, .035, 15) if (x + y) % 4 else B(.24, .03, 15))
    for (nx, ny, nw, nh) in ((122, 160, 8, 6), (132, 156, 10, 7), (144, 161, 7, 5), (190, 162, 6, 8)):
        paper_note(cv, nx, ny, nw, nh, labels)
    cv.hline(124, 150, 172, WOODS[2])
    for k, jx in enumerate((126, 132, 139, 145)):
        hh = 5 + (k % 2) * 2
        cv.rect(jx, 172 - hh, jx + 4, 172, B(.28 + 0.03 * k, .02, 215))
        cv.rect(jx, 172 - hh + 2, jx + 3, 172 - hh + 4, PAPER)
        labels.append((jx, 172 - hh + 2, 3, 2))
    lamp(cv, 154, 166, kind="candle")


def paint_shaft2(cv: Cv, labels, m):
    """楼梯井 2：高拱，石阶贴后壁从左往右上；阶下的三角空当塞着箱子；墙上一盏挂灯、一张纸条。"""
    for (cx, cy, w, h) in ((52, F1 - 12, 14, 12), (68, F1 - 16, 16, 16), (70, F1 - 28, 12, 12), (86, F1 - 10, 12, 10)):
        crate(cv, cx, cy, w, h, labels)
    draw_steps(cv, STAIR2, m)
    lamp(cv, 62, 120, cord_top=None)
    cv.vline(62, 108, 118, IRON)
    cv.hline(58, 63, 108, IRON)


def paint_shaft1(cv: Cv, labels, m):
    draw_steps(cv, STAIR1, m)
    lamp(cv, 372, 176, cord_top=140)
    paper_note(cv, 392, 214, 8, 6, labels)


def paint_attic(cv: Cv, labels, m):
    """阁楼：一格格的来客册档案（书脊一条条、每格一张标签），地上一摞没归档的，一盏提灯。"""
    rng = np.random.default_rng(7602)
    for row, sy in enumerate((104, 118)):
        x0, x1 = 114, 170
        cv.hline(x0, x1, sy, WOODS[3])
        cv.hline(x0, x1, sy + 1, WOODS[1])
        x = x0 + 2
        while x < x1 - 4:
            w = int(rng.integers(2, 4))
            h = int(rng.integers(7, 12))
            c = (B(.22, .03, 20), B(.26, .03, 200), B(.3, .035, 90), B(.2, .02, 250), Wm(.3, .04, 60))[int(rng.integers(0, 5))]
            cv.rect(x, sy - h, x + w, sy, c)
            cv.vline(x + w - 1, sy - h, sy, B(.12, .02, 250))
            x += w + (1 if rng.random() < 0.2 else 0)
        for k in range(3):
            lx = x0 + 6 + k * 18 + row * 5
            cv.rect(lx, sy + 2, lx + 5, sy + 5, PAPER)
            labels.append((lx, sy + 2, 5, 3))
    for y in range(F2A - 9, F2A + 1):
        cv.hline(150, 164, y, (B(.32, .02, 90) if y % 2 else B(.26, .02, 90)))
    lamp(cv, 140, 96, cord_top=82)


def paint_win_extra(cv: Cv, labels):
    """窗台右边：一架窄格子，放影像盒和来客册；顶上一根晾绳挂着两张湿纸。"""
    x0, x1 = 300, 318
    for k, sy in enumerate((54, 70, 86)):
        cv.hline(x0, x1, sy, WOODS[3])
        for j in range(2):
            bx = x0 + 2 + j * 8
            cv.rect(bx, sy - 7, bx + 6, sy, B(.2 + 0.02 * ((j + k) % 3), .015, 240))
            cv.hline(bx, bx + 6, sy - 7, B(.3, .015, 240))
            cv.rect(bx + 1, sy - 5, bx + 4, sy - 3, PAPER)
            labels.append((bx + 1, sy - 5, 3, 2))
    for x in range(212, 300):
        cv.px(x, int(36 + 3 * math.sin(math.pi * (x - 212) / 88)), WOODS[3])
    cv.rect(220, 38, 226, 46, PAPER)
    cv.rect(284, 38, 289, 44, B(.3, .02, 90))


def paint_nook(cv: Cv, rock):
    """右上的小储藏室：只露出一半（右边那半被没凿开的石头挡着）。里面一排影像盒、一只圆窗透进一点灯。"""
    x0, x1, y0, y1 = NOOK
    m = np.zeros((H, W), bool)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for y in range(y0, y1):
        for x in range(x0, x1):
            if ((x - cx) / ((x1 - x0) / 2)) ** 2 + ((y - cy) / ((y1 - y0) / 2)) ** 2 <= 1 and y < y1 - 2:
                m[y, x] = True
    tex = rt.cave_texture(m, 7701)
    cv.a[m] = tex[m]
    for k, sy in enumerate((92, 106)):
        cv.hline(340, 376, sy, WOODS[3])
        for j in range(5):
            bx = 341 + j * 7
            cv.rect(bx, sy - 6, bx + 5, sy, B(.18 + 0.02 * ((j + k) % 3), .015, 240))
            cv.rect(bx + 1, sy - 4, bx + 4, sy - 2, PAPER)
    lamp(cv, 360, 98, kind="candle")
    # 断面圈
    r1 = dilate(m, 1) & ~m
    cv.a[r1, :3] = rt.CRACK
    # 右边那半被石头挡着：一块没凿开的鼓包（外面的石头纹理），左沿是一道受光的弧
    cover = np.zeros((H, W), bool)
    for y in range(y0 - 2, y1 + 2):
        bx = 364 + 10 * math.sin((y - y0) / (y1 - y0) * math.pi) - 4
        cover[y, int(bx):x1 + 2] = True
    cover &= rock[..., 3] > 0
    cv.a[cover] = rock[cover]
    for y in range(y0 - 2, y1 + 2):
        bx = int(364 + 10 * math.sin((y - y0) / (y1 - y0) * math.pi) - 4)
        if 0 <= bx < W and cover[y, bx]:
            cv.px(bx, y, rt.ROCK8[5])
            cv.px(bx + 1, y, rt.ROCK8[4])
    return m


# ======================================================================= 门窗（前墙上凿的洞）
def carve_opening(cv: Cv, x, y, w, h, kind="arch", lit=True, seed=0, mull=0, door=False, spill=None):
    """在石面上凿一个洞，看得出厚度：左内壁朝右（接月光，冷亮）、顶上内壁在影子里（暗）、右内壁一线暗；
    洞里：亮的是屋里的暖光（下面中间最亮、往上往边一档档暗，小色团分档），暗的是深蓝、一点冷反光；
    窗台 / 门槛一道受光的石边（比洞宽一点）、下面一道影子；洞口边缘几处磨损；暖光溢到洞口外面一小圈（很快衰减）。
    mull = 窗棂（0 无、1 竖一根、2 十字）。door = 门：左边一扇往里开的木门板、门槛外地上一小片暖光。"""
    rng = np.random.default_rng(seed + x * 7 + y * 13)
    m = bm.opening_mask(w, h, kind)
    dep = 2 if w < 9 else 3
    deep = [Wm(.17, .04, 48), Wm(.24, .055, 52), Wm(.34, .07, 58), Wm(.46, .085, 64), Wm(.56, .09, 70)]
    dark = [B(.03, .02, 266), B(.06, .025, 262), B(.1, .03, 250)]
    c = rt.clusters(h, w, rng)
    for yy in range(h):
        xs = np.nonzero(m[yy])[0]
        if len(xs) == 0:
            continue
        xl, xr = xs[0], xs[-1]
        for xx in xs:
            col = None
            ytop = np.nonzero(m[:, xx])[0][0]
            if yy - ytop < dep - 1 or yy - ytop == 0:
                col = dark[0]                                   # 顶上内壁：影子
            elif xx - xl < dep:
                col = rt.ROCK8[5] if xx - xl == 0 else rt.ROCK8[3]   # 左内壁：朝右，接月光
            elif xr - xx < 1:
                col = dark[1]
            elif lit:
                d = math.hypot((xx - w * 0.52) / (w * 0.6), (yy - h * (0.82 if door else 0.7)) / (h * 0.75))
                v = (1 - d) * 4.2 + (c[yy, xx] - 0.5) * 0.9
                col = deep[int(np.clip(v, 0, 4))]
            else:
                col = dark[1] if (c[yy, xx] > 0.35) else dark[2]
            cv.px(x + xx, y + yy, col)
    if not lit:
        cv.px(x + w // 2 + 1, y + h // 3, B(.3, .03, 230))          # 暗窗：玻璃上一点冷反光
    if mull and lit:
        mx = x + w // 2
        for yy in range(h):
            if m[yy, w // 2]:
                cv.px(mx, y + yy, WOODS[1])
        if mull == 2:
            my = y + int(h * 0.42)
            for xx in range(w):
                if m[int(h * 0.42), xx]:
                    cv.px(x + xx, my, WOODS[1])
    if door:
        # 门板往里开（左边一条，看得到厚度）
        for yy in range(h):
            xs = np.nonzero(m[yy])[0]
            if len(xs) == 0:
                continue
            for k in range(dep, dep + 5):
                if k < len(xs):
                    cv.px(x + xs[0] + k, y + yy, WOODS[1] if (yy % 6) else WOODS[0])
            if dep + 5 < len(xs):
                cv.px(x + xs[0] + dep + 5, y + yy, Wm(.36, .06, 60))          # 门边被屋里的灯照亮一条
    # 窗台 / 门槛：一道受光的石边
    sy = y + h
    cv.hline(x - 1, x + w + 1, sy, rt.ROCK8[6] if not door else rt.ROCK8[5])
    cv.px(x + w, sy, rt.RIM)
    cv.hline(x - 1, x + w + 1, sy + 1, rt.CRACK)
    # 洞口外沿：上面一道浅的门楣（受光）、几处磨损
    for xx in range(w):
        ys = np.nonzero(m[:, xx])[0]
        if len(ys) and y + ys[0] - 1 >= 0 and rng.random() < 0.75:
            cv.px(x + xx, y + ys[0] - 1, rt.ROCK8[5])
    for _ in range(max(2, w // 4)):
        side = rng.integers(0, 2)
        yy = int(rng.integers(1, h - 1))
        xs = np.nonzero(m[yy])[0]
        if len(xs):
            px_ = x + (xs[0] - 1 if side == 0 else xs[-1] + 1)
            cv.px(px_, y + yy, rt.ROCK8[2] if side == 0 else rt.ROCK8[6])
    if lit:
        r = spill or (w * 1.5 + 7)
        rt.warm_spill(cv.a, cv.a[..., 3] > 0, [(x + w / 2, y + h * 0.6, r)], rng, strength=0.85)
    if door:
        for xx in range(-2, w + 10):
            for d in range(2):
                yy = sy + d
                if 0 <= yy < H and cv.a[yy, x + xx, 3] and (xx < w or (c[d % h, xx % w] > 0.4 and xx < w + 6 - d * 3)):
                    cv.px(x + xx, yy, WARM[2] if d == 0 else WARM[1])


FRONT_OPENINGS = [
    # x, y（洞顶）, w, h, kind, lit, 窗棂
    (96, 232, 9, 12, "arch", True, 0),        # 厨房
    (164, 226, 15, 18, "arch", True, 1),      # 餐桌
    (258, 246, 4, 7, "arch", False, 0),       # 储物：一道窄缝、一只暗的小圆窗
    (300, 238, 6, 6, "round", False, 0),
    (384, 252, 4, 8, "arch", True, 0),        # 楼梯井 1：顺着台阶一高一低
    (366, 214, 4, 7, "arch", False, 0),
    (350, 178, 5, 9, "arch", True, 0),
    (150, 164, 10, 10, "round", True, 0),     # 卧室
    (236, 134, 10, 15, "arch", True, 0),      # 收藏间
    (290, 128, 5, 6, "arch", False, 0),
    (40, 170, 4, 8, "arch", True, 0),         # 楼梯井 2
    (62, 132, 4, 7, "arch", False, 0),
    (84, 98, 5, 8, "arch", True, 0),
    (136, 100, 7, 9, "arch", True, 0),        # 阁楼
    (250, 44, 22, 30, "arch", True, 2),       # 窗台的大窗
    (352, 86, 6, 6, "round", True, 0),        # 右上小储藏室
]


def build_front(rock, allm, nook):
    cover = dilate(allm | nook, 4) & (rock[..., 3] > 0)
    cv = Cv(W, H)
    cv.a[cover] = rock[cover]
    door_w, door_h = 25, 50
    # 门：用河岸会话的 carve(door=True)（门板、屋里的深浅、光从里往外一档档弱），和河岸上别家的门同一个画法
    bm.carve(cv, 36, F0 + 1 - door_h, door_w, door_h, "arch", True, True, glow_r=26, seed=7020)
    # 门灯、门牌（和河岸水下的旧门牌同一个 x）
    lamp(cv, 36 + door_w + 6, F0 + 1 - door_h + 4)
    rt.warm_spill(cv.a, cv.a[..., 3] > 0, [(36 + door_w + 6, F0 + 1 - door_h + 5, 13)], np.random.default_rng(7022))
    ax, ay = bm.HOUSE_PLATE[0], F0 + 1 - 34
    cv.rect(ax, ay, ax + 11, ay + 7, Wm(.42, .035, 80))
    cv.vline(ax + 11, ay + 1, ay + 7, Wm(.32, .03, 70))
    cv.hline(ax + 2, ax + 9, ay + 2, B(.14, .02, 250))
    cv.hline(ax + 2, ax + 7, ay + 4, B(.14, .02, 250))
    cv.hline(ax, ax + 12, ay + 8, rt.CRACK)
    cv.px(ax + 5, ay - 1, WOODS[3])
    for i, (wx, wy, ww, wh, kind, lit, mull) in enumerate(FRONT_OPENINGS):
        carve_opening(cv, wx, wy, ww, wh, kind, lit, seed=7030 + i, mull=mull)
    # 大窗下的石台上晾着来客册（外面看是一小片纸）、一根晾绳斜到左边
    for x in range(200, 250):
        cv.px(x, int(50 + 3 * math.sin(math.pi * (x - 200) / 50)), B(.3, .025, 70))
    cv.px(199, 49, B(.2, .02, 70))
    cv.rect(214, 53, 220, 60, B(.22, .03, 210))
    cv.rect(232, 53, 237, 58, PAPER)
    # 门边两只花盆
    for (ppx, ph) in ((14, 6), (21, 5)):
        cv.rect(ppx, F0 + 1 - ph, ppx + 5, F0 + 1, Wm(.22, .035, 50))
        cv.hline(ppx, ppx + 5, F0 + 1 - ph, Wm(.28, .035, 55))
        for j in range(4):
            cv.line([(ppx + 1 + j, F0 - ph), (ppx + j - 1 + (j % 3), F0 - ph - 4 - j % 2)], MOSS[2])
    return cv


CLEFTS = [(108, 62, 150, 0.9), (334, 62, 128, -0.6)]    # 柱头之间的豁口往下裂开的深缝：起点 x, y, 到哪一行, 斜率


def clefts(cv: Cv, m, avoid):
    """两根柱头之间往下的一道深缝（几根石柱长在一起的接缝）：两像素宽的暗沟，越往下越窄，左唇暗、右唇受光，缝里长苔。
    avoid = 洞（剖开的地方不画）。"""
    rng = np.random.default_rng(7041)
    for (x0, y0, y1, k) in CLEFTS:
        x = float(x0)
        for y in range(y0, y1):
            xi = int(round(x))
            wdt = 2 if y < y0 + (y1 - y0) * 0.6 else 1
            for d in range(-1, wdt + 1):
                xx = xi + d
                if not (0 <= xx < W) or not m[y, xx] or avoid[y, xx]:
                    continue
                if d == -1:
                    cv.px(xx, y, rt.ROCK8[1])
                elif d == wdt:
                    cv.px(xx, y, rt.ROCK8[5])
                else:
                    cv.px(xx, y, rt.CRACK if rng.random() > 0.12 else MOSS[0])
            x += k * 0.15 + rng.uniform(-0.5, 0.5)


def top_things(cv: Cv, m):
    """顶上：一截铁皮烟囱（厨房的炉子从石头里通上来），烟囱根一圈苔。"""
    px_ = 150
    top = int(np.nonzero(m[:, px_])[0][0])
    cv.rect(px_, top - 9, px_ + 4, top + 2, B(.1, .015, 250))
    cv.vline(px_ + 3, top - 9, top + 2, B(.2, .02, 246))
    cv.hline(px_ - 1, px_ + 5, top - 9, B(.22, .02, 246))
    for k in range(-2, 7):
        cv.px(px_ + k, top + 1, MOSS[k % 3])


# ======================================================================= 合起来
def furniture_layer():
    """D 的家具层（没有灰泥墙），月夜色 + 吊灯那一圈暖。D 坐标（420×176）。"""
    rha = bm._rha()
    rha.window = bm.moon_window
    rha.shell = lambda: np.zeros((rha.H, rha.W, 4), np.uint8)
    rha.TAGS.clear()
    f = rha.build_back()
    bm.home_lamp(f)
    return bm.moon_interior(f, dark=0.66)                  # 和 build_home_parts 的物件同一档（河岸会话 10-30 改成 0.66）


def build():
    _r, _b, _f, _l, dobjs = bm.build_home_parts()
    furn = furniture_layer()
    labels_all = []
    masks, allm = cave_masks()
    km = rock_mask() | allm
    # 外面的石头用河岸会话的 stone_shade（柱状节理切面 + 小色团 + 亮边 + 苔 + 水渍），和河岸上的石柱、面包店是同一种石头；
    # river_rock_tex.rock_texture 是我这边的另一种画法（竖向风化沟），留着备用
    rock = np.zeros((H, W, 4), np.uint8)
    for i, (x0, x1) in enumerate(((0, CLEFTS[0][0]), (CLEFTS[0][0], CLEFTS[1][0]), (CLEFTS[1][0], W))):
        part = km.copy()                                    # 三根柱子分开上色（stone_shade 按每行的连续段切节理，合在一起会断层）
        part[:, :x0] = False
        part[:, x1:] = False
        tex = bm.stone_shade(part, np.random.default_rng(7001 + i), bm.STONE, facet_w=16.0, ledges=0.45, water_row=F0 - 56)
        rock[part] = tex[part]

    back = Cv(W, H)
    back.paste(rock, 0, 0)
    nook = paint_nook(back, rock)
    paint_caves(back, masks, allm)
    # 石阶、新房间里的东西
    paint_shaft1(back, labels_all, masks["shaft1"] | masks["store"])
    paint_shaft2(back, labels_all, masks["shaft2"])
    draw_steps(back, RAMP, masks["ramp"] | masks["attic"] | masks["win"], body=8)
    paint_store(back, labels_all)
    paint_bed(back, labels_all)
    paint_attic(back, labels_all, masks["attic"])
    paint_win_extra(back, labels_all)
    # D 的家具块：挪进洞里、裁到洞的形状
    for name, ((x0, y0, x1, y1), (dx, dy), cave) in PIECES.items():
        seg = furn[y0:y1, x0:x1]
        cm = masks[cave] | (masks["p_cs"] if cave == "coll" else False)
        for yy in range(seg.shape[0]):
            for xx in range(seg.shape[1]):
                if seg[yy, xx, 3] == 0:
                    continue
                tx, ty = x0 + xx + dx, y0 + yy + dy
                if 0 <= tx < W and 0 <= ty < H and cm[ty, tx]:
                    back.a[ty, tx] = seg[yy, xx]
    # 吊灯的线、餐桌那盏
    back.vline(180, 206, 216, IRON)
    lamp(back, 264, 128, cord_top=103)
    floor_water(back, 20, 134, allm)
    floor_water(back, 232, 406, allm)
    rt.warm_spill(back.a, allm | nook, LAMPS, np.random.default_rng(7031))
    top_things(back, km)
    clefts(back, km, dilate(allm | nook, 2))

    front = build_front(rock, allm, nook)
    clefts(front, front.a[..., 3] > 0, np.zeros((H, W), bool))
    light = build_light(allm)
    objs = build_objects(dobjs, labels_all)
    return back.a, front.a, light, objs


def build_light(allm):
    img = np.zeros((H, W, 4), np.uint8)
    for (lx, ly, r) in LAMPS:
        for y in range(int(ly), min(H, int(ly + r * 1.6))):
            t = (y - ly) / (r * 1.6)
            half = 5 + r * 0.75 * t
            for x in range(int(lx - half), int(lx + half) + 1):
                if 0 <= x < W and allm[y, x]:
                    u = abs(x - lx) / half
                    a = int(24 * (1 - u ** 2) * (1 - 0.6 * t))
                    if a > 4 and a > img[y, x, 3]:
                        img[y, x] = (238, 196, 120, a)
    # 大窗斜进来的一道月光
    for y in range(30, F2B + 1):
        t = (y - 30) / (F2B - 30)
        for x in range(236 - int(22 * t), 296 - int(22 * t)):
            if allm[y, x] and img[y, x, 3] == 0:
                img[y, x] = (150, 176, 220, int(16 * (1 - 0.5 * t)))
    return img


def shift_parts(frames, parts, x0, y0):
    """把一帧（左上角 x0, y0）按列分成几块各自挪（parts = [(列起, 列止, dx, dy)]），拼成新帧。返回 (帧, 新 x, 新 y)。"""
    h = frames[0].shape[0]
    boxes = [(x0 + c0 + dx, y0 + dy, x0 + c1 + dx, y0 + h + dy) for (c0, c1, dx, dy) in parts]
    nx0, ny0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    nx1, ny1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    out = []
    for f in frames:
        a = np.zeros((ny1 - ny0, nx1 - nx0, 4), np.uint8)
        for (c0, c1, dx, dy) in parts:
            tx, ty = x0 + c0 + dx - nx0, y0 + dy - ny0
            seg = f[:, c0:c1]
            mm = seg[..., 3] > 0
            a[ty:ty + h, tx:tx + seg.shape[1]][mm] = seg[mm]
        out.append(a)
    return out, nx0, ny0


def build_objects(dobjs, labels_all):
    """物件：D 的帧原样（月夜色已上），跟着它那块家具挪。dobjs 是 river_bank_moon_art 的（y 多了 HDY）。"""
    hdy = bm.HDY
    move = {"river_home_table": "dining", "river_home_hourglass": "dining", "niff_notebook": "dining", "niff_photo": "dining",
            "river_home_cabinet": "cabinet", "river_home_player": "stand"}
    out = {}
    for prop, img, frames, x, y, states, note in dobjs:
        y -= hdy                                                    # → D 坐标
        if prop in move:
            dx, dy = PIECES[move[prop]][1]
            out[prop] = (img, frames, x + dx, y + dy, states, note)
        elif prop == "river_home_chair":
            dx = PIECES["window"][1][0]
            out[prop] = (img, frames, x + dx, y + (F2B - DFL), states,
                         "晨坐的那把：default 靠在窗台右边的格子架旁，by_window 在大窗前（两个状态都在 L2 窗台）")
        elif prop == "guestbook":
            w = frames[0].shape[1]
            split = 215 - x                                         # D x 215 以左是桌上那半，以右是窗台那半
            (dxa, dya), (dxb, dyb) = PIECES["dining"][1], PIECES["window"][1]
            nf, nx, ny = shift_parts(frames, [(0, split, dxa, dya), (split, w, dxb, dyb)], x, y)
            out[prop] = (img, nf, nx, ny, states,
                         "一帧竖着跨两层：open / photo_cup / pages_stuck / closed / drawing_in 在 L0 餐桌上，"
                         "drying / dry 在 L2 窗台上；特写 closeup_guestbook_<state>.png")
        elif prop == "river_home_labels":
            fr = []
            for k, f in enumerate(frames):
                full = np.zeros((260, W, 4), np.uint8)              # D 坐标的整张
                full[y:y + f.shape[0], x:x + f.shape[1]] = f
                a = np.zeros((H, W, 4), np.uint8)
                for name, ((x0, y0, x1, y1), (dx, dy), cave) in PIECES.items():
                    seg = full[y0:y1, x0:x1]
                    mm = seg[..., 3] > 0
                    a[y0 + dy:y1 + dy, x0 + dx:x1 + dx][mm] = seg[mm]
                for (lx, ly, lw, lh) in labels_all:
                    a[ly:ly + lh, lx:lx + lw, :3] = (TAG_ON if k else TAG)[:3]
                    a[ly:ly + lh, lx:lx + lw, 3] = 255
                fr.append(a)
            out[prop] = (img, fr, 0, 0, states, note + "；整张图大小（标签在三层的各个洞里），点击框只在门厅雨衣那块")
        else:
            raise SystemExit("没处理的物件：" + prop)
    return out


def room_json(objs):
    od = {}
    for prop, (img, frames, x, y, states, note) in objs.items():
        d = {"img": f"{img}.png", "x": int(x), "y": int(y), "w": frames[0].shape[1], "h": frames[0].shape[0],
             "frames": len(frames), "states": states, "default": "default"}
        if note:
            d["note"] = note
        if prop == "river_home_labels":
            d["click"] = [18, 212, 18, 46]
        od[prop] = d
    for prop, st in (("chen_drawing", "done"), ("chen_journal", "memory_page")):
        # 纯剧情状态（特写在 art/river_story/）：1×1 的空物件，免得引擎报 ROOM_WARN
        od[prop] = {"img": "obj_empty.png", "x": 0, "y": 0, "w": 1, "h": 1, "frames": 1, "states": {"default": 0, st: 0},
                    "default": "default", "note": "只记剧情状态，不画（特写见 art/river_story/）"}

    def mk(x, lv="l0"):
        return {"x": x, "level": lv}
    return {
        "_comment": "妮芙家（第三版：一整块巨石被掏空的三层洞屋，石阶往上）。格式照 docs/river_rooms_contract.md 1.6"
                    "（多层：levels / stairs，见 scripts/room_stage.gd）；坐标都是图里的像素（左上角 0,0）。"
                    "tools/river_home_rooms_art.py 生成，别手改。地面以下泡在水里的旧一层（旧门、旧门牌）画在河岸主层里。",
        "kind": "house", "host": "river_bank", "x": HOME_X, "size": [W, H],
        "back": "home_back.png", "front": "home_front.png", "light": "home_light.png",
        "floor": F0, "walk": [24, 406], "door": DOOR_X,
        "levels": [
            {"id": "l0", "floor": L0_FLOOR, "walk": [24, 406], "note": "门厅 → 厨房 → 上两级餐桌 → 储物 → 楼梯井 1"},
            {"id": "l1", "floor": L1_FLOOR, "walk": [26, 340], "note": "楼梯井 2 → 上一级卧室 → 收藏间"},
            {"id": "l2", "floor": L2_FLOOR, "walk": [96, 316], "note": "阁楼 → 几级台阶 → 窗台"},
        ],
        "stairs": [
            {"from": "l0", "x": STAIR1[0], "to": "l1", "x2": STAIR1[2], "note": "楼梯井 1：从最右往左上"},
            {"from": "l1", "x": STAIR2[0], "to": "l2", "x2": STAIR2[2], "note": "楼梯井 2：从最左往右上"},
        ],
        "cam_dy": 36, "cam_top": -100,
        "markers": {
            "river_home_door": mk(DOOR_X), "river_home_labels": mk(28), "river_home_jar": mk(100),
            "river_home_kitchen": mk(108), "river_home_chen": mk(154), "river_home_table": mk(168),
            "river_home_hourglass": mk(178), "river_home_niff": mk(212), "river_home_up1": mk(398),
            "river_home_l1": mk(332, "l1"), "river_home_up2": mk(34, "l1"),
            "river_home_cabinet": mk(231, "l1"), "river_home_player": mk(266, "l1"),
            "river_home_l2": mk(104, "l2"), "river_home_chair": mk(258, "l2"), "river_home_window": mk(262, "l2"),
        },
        "objects": od,
    }


def check_alpha(a, name):
    al = a[..., 3]
    bad = ((al != 0) & (al != 255)).sum()
    assert bad == 0, f"{name}: 半透明像素 {bad}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    args = ap.parse_args()
    back, front, light, objs = build()
    check_alpha(back, "back")
    check_alpha(front, "front")
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(back, "RGBA").save(OUT / "home_back.png")
    Image.fromarray(front, "RGBA").save(OUT / "home_front.png")
    Image.fromarray(light, "RGBA").save(OUT / "home_light.png")
    for prop, (img, frames, x, y, states, note) in objs.items():
        a = np.concatenate(frames, axis=1)
        check_alpha(a, img)
        Image.fromarray(a, "RGBA").save(OUT / f"{img}.png")
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(OUT / "obj_empty.png")
    meta = room_json(objs)
    (OUT / "room.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ok river_home", W, H)
    if args.preview:
        pv = Path(args.preview)
        pv.mkdir(parents=True, exist_ok=True)
        bg = Image.new("RGBA", (W, H), (8, 12, 26, 255))
        bg.alpha_composite(Image.fromarray(back))
        st = bg.copy()
        for prop, (img, frames, x, y, states, note) in objs.items():
            st.alpha_composite(Image.fromarray(frames[0]), (int(x), int(y)))
        st.alpha_composite(Image.fromarray(light))
        st.resize((W * 2, H * 2), Image.NEAREST).save(pv / "home_inside.png")
        bg.alpha_composite(Image.fromarray(front))
        bg.resize((W * 2, H * 2), Image.NEAREST).save(pv / "home_outside.png")


if __name__ == "__main__":
    main()
