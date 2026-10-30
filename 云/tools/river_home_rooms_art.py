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
import river_home_props as hp  # noqa: E402
from river_home_props import FRONT, INK, INK_R  # noqa: E402

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

# 新画的家具的位置（图里的坐标）——物件（桌面、柜门、影像机、椅子）的框没变，家具对着它们画
T_X0F, T_X1F, T_TOPF = 150, 208, 253          # 餐桌：台面左右、台面那一行（桌上的物件底边踩在它上面）
CAB_X0F, CAB_X1F = 210, 252                   # 索引柜柜体
CABD_X0, CABD_X1, CABD_Y0, CABD_Y1 = 212, 250, 110, 192   # 柜门（= obj_cabinet 关着时的门）
CAB_OBJ_X0, CAB_OBJ_X1 = 206, 256             # obj_cabinet 的框（开着时两扇门板贴在两边）
WIN_X0, WIN_X1, WIN_Y0, WIN_Y1 = 238, 288, 30, 82   # 窗台的大窗洞（来客册晾干那两帧摊在窗台上 y 74–82）
PL_X, PL_Y = 262, 152                         # obj_player 的左上角
INK_THREAD = Wm(.36, .08, 28)                 # 条子之间拉的红线

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


def paint_nook(cv: Cv, rock):
    """右上的小储藏室：只露出一半（右边那半被没凿开的石头挡着）。架子上的东西在 furnish_nook。"""
    x0, x1, y0, y1 = NOOK
    m = np.zeros((H, W), bool)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for y in range(y0, y1):
        for x in range(x0, x1):
            if ((x - cx) / ((x1 - x0) / 2)) ** 2 + ((y - cy) / ((y1 - y0) / 2)) ** 2 <= 1 and y < y1 - 2:
                m[y, x] = True
    tex = rt.cave_texture(m, 7701)
    cv.a[m] = tex[m]
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


# ======================================================================= 家具和小物件（第四版，tools/river_home_props.py 打光）
# 作者 10-30：「一个灰色长方形套着一个黄色长方形，缺乏质感啊喂！还有很多内部装饰也是」。
# 每样东西都按形状画（罐、瓶、卷纸、贝壳、捆好的本子、木箱、桶、麻袋……），手写小纸条当标签，架板有厚度，
# 最后按屋里的灯一起打光：朝灯那条边亮、背灯的暗，离灯远的沉在月夜的蓝里；墙上一圈圈的暖光被东西挡出影子。

# 屋里的灯（灯芯 x, y, 离墙多远, 光的半径, 强度）
LAMPS = [
    (166, 228, 10, 64, 1.0),     # 餐桌上的大提灯
    (264, 130, 10, 58, 1.0),     # 收藏间
    (174, 92, 9, 44, 0.85),      # 阁楼（吊在通往窗台的台阶口）
    (372, 178, 9, 44, 0.85),     # 楼梯井 1
    (66, 122, 7, 44, 0.85),      # 楼梯井 2（墙上的托架灯）
    (147, 165, 5, 34, 0.6),      # 卧室：架子上的蜡烛
    (284, 234, 5, 32, 0.6),      # 储物：架子上的蜡烛
    (352, 99, 4, 18, 0.45),      # 右上小储藏室：蜡烛
    (125, 272, 4, 16, 0.35),     # 厨房：炉膛里一点余火
    (48, 220, 6, 38, 0.75),      # 门厅：门楣上方托架挂的小灯
    (276, 44, 30, 90, 0.8, (20, F2B + 3)),   # 窗台：大窗进来的月光（冷，只照窗台这一层）
]


def furnish_hall(p: hp.Props):
    """门厅：门（从里面看：竖板、Z 字撑、铁合页、拉环，门缝透进一线月光）、挂钉上的雨衣和围巾、地上一双胶靴、斜靠的桨。"""
    x0, y0, w, h = 36, F0 + 1 - 50, 25, 50
    m = bm.opening_mask(w, h, "arch")
    rng = np.random.default_rng(7811)
    planks = [rng.random() for _ in range(6)]
    for yy in range(h):
        for xx in range(w):
            if not m[yy, xx]:
                continue
            k = xx // 5
            n = FRONT if xx % 5 else hp.LEFT
            t = 0.3 + planks[k] * 0.07 - (0.12 if xx % 5 == 0 else 0)
            if (xx * 13 + yy * 7) % 17 == 0:
                t -= 0.05                                       # 木纹的结
            p.px(x0 + xx, y0 + yy, "wood_d", t, n, z=2)
    # 两道横撑 + 一道斜撑（Z 字）
    for by in (y0 + 16, y0 + h - 9):
        p.box(x0 + 2, by, x0 + w - 3, by + 2, "wood_d", 0.4, z=3, top=1)
    for k in range(h - 27):
        yy = y0 + h - 10 - k
        xx = x0 + 3 + int(k * (w - 7) / (h - 27))
        p.px(xx, yy, "wood_d", 0.42, hp.TOP, z=3)
        p.px(xx + 1, yy, "wood_d", 0.36, FRONT, z=3)
    # 铁合页（左边，长条带圆头）、拉环和锁眼（右边）
    for by in (y0 + 17, y0 + h - 8):
        p.hline(x0 + 1, x0 + 9, by, "iron", 0.36, FRONT, z=3.5)
        p.px(x0 + 10, by, "iron", 0.44, FRONT, z=3.5)
        p.px(x0 + 10, by - 1, "iron", 0.4, hp.TOP, z=3.5)
    rx, ry = x0 + w - 5, y0 + h // 2 + 3
    for (dx, dy) in ((0, -1), (-1, 0), (1, 0), (0, 1), (-1, 1), (1, 1)):
        p.px(rx + dx, ry + dy + 1, "brass", 0.3 if dy > 0 else 0.42, hp.nrm(dx, dy, 0.6), z=4)
    p.fx(rx, ry + 5, B(.06, .02, 266))
    # 门缝：右边和门槛透进一线月光
    for yy in range(int(r_ := w / 2), h):
        p.fx(x0 + w, y0 + yy, B(.36 if yy % 7 else .3, .03, 236), z=1, cast=False)
    for xx in range(w + 1):
        p.fx(x0 + xx, F0, B(.32 if xx % 5 else .26, .03, 238), z=1, cast=False)
    # 挂钉板 + 雨衣（带兜帽）+ 一条围巾；地上一双胶靴；桨斜靠在墙上
    p.box(20, 222, 34, 223, "wood", 0.32, z=3, top=1)
    for k in (23, 31):
        p.px(k, 224, "wood", 0.36, hp.BOT, z=4)
    cx = 25
    p.dome(cx, 228, 3, 3, "cloth_t", 0.34, z=5)                  # 兜帽
    p.px(cx, 225, "cloth_t", 0.42, hp.TOP, z=5)
    for (dx, dy) in ((-1, 227), (0, 227), (1, 227), (-1, 228), (0, 228), (0, 229)):
        p.px(cx + dx, dy, "cloth_t", 0.1, FRONT, z=5.1)                  # 兜帽的开口（里面暗）
    for yy in range(229, 254):
        k = (yy - 229) / 25
        half = 3 + int(round(2.6 * min(1, k * 2.4))) + (1 if k > 0.75 else 0)
        for xx in range(cx - half, cx + half + 1):
            u = (xx - cx) / (half + 0.5)
            fold = ((xx - cx + 9) % 3 == 0) and yy > 233
            t = 0.4 - (0.1 if fold else 0) - 0.04 * abs(u)
            if yy == 253 and (xx % 3 == 0):
                continue                                            # 下摆不齐
            p.px(xx, yy, "cloth_t", t, hp.nrm(u, 0, 0.9), z=5)
    for yy in range(231, 246):                                       # 袖子（垂在身侧，往右一点）
        p.px(cx + 5, yy, "cloth_t", 0.28, hp.RIGHT, z=5.5)
    p.px(cx + 5, 246, "cloth_t", 0.2, hp.BOT, z=5.5)
    for yy in range(230, 251, 4):
        p.px(cx, yy, "iron", 0.36, FRONT, z=5.2)                     # 一排扣子
    for yy in range(225, 240):                                       # 围巾（第二个钉子上垂下来，两条）
        p.px(31, yy, "cloth_r", 0.34 - 0.004 * (yy - 225), hp.LEFT, z=4)
        p.px(32, yy + (1 if yy > 236 else 0), "cloth_r", 0.3, FRONT, z=4)
    for yy in range(240, 243):
        p.px(31, yy, "cloth_r", 0.4, FRONT, z=4) if yy % 2 else None
    for bx in (22, 28):                                              # 胶靴
        p.cyl(bx, 268, bx + 3, 277, "rubber", 0.4, z=5, top_rows=1, round_bot=False)
        p.rect(bx, 278, bx + 5, F0, "rubber", 0.32, FRONT, z=5)
        p.hline(bx + 4, bx + 5, 277, "rubber", 0.42, hp.TOP, z=5)
    for k in range(52):                                             # 桨：靠在门右边的墙上，杆从右上斜到左下，底下是桨叶
        yy = 226 + k
        xx = 68 - int(k * 4 / 52)
        if yy < F0 - 12:
            p.px(xx, yy, "wood_l", 0.36, FRONT, z=4)
            p.px(xx + 1, yy, "wood_l", 0.26, hp.RIGHT, z=4)
        else:
            for d in range(-1, 3):
                p.px(xx + d, yy, "wood_l", 0.38 - 0.05 * abs(d - 0.5), FRONT, z=4)
    p.hline(67, 69, 226, "wood_l", 0.46, hp.TOP, z=4)
    # 门楣上方一盏小挂灯（铁托架从石壁里伸出来）
    p.hline(43, 48, 211, "iron", 0.38, hp.TOP, z=3)
    p.vline(43, 211, 214, "iron", 0.3, hp.LEFT, z=3)
    p.lantern(48, 220, cord_top=212, z=6)


def furnish_kitchen(p: hp.Props):
    """厨房：灶台（台面一线亮、两扇框板门、圆把手）、铁炉子（炉门里一点余火、烟囱管通进石头）、炉上一把水壶、
    墙上一块架板（罐子、瓶子、铁皮罐，各贴手写条；空盐罐在 x≈100）、架子下一根挂杆（勺子、小锅）、顶上倒挂一束干草。"""
    # 灶台
    cx0, cx1, ct = 74, 110, 258
    p.box(cx0 - 1, ct, cx1 + 1, ct + 2, "wood_l", 0.36, z=8, top=1)
    p.rect(cx0, ct + 3, cx1, F0 - 2, "wood", 0.26, FRONT, z=7)
    p.hline(cx0, cx1, ct + 3, "wood", 0.14, hp.BOT, z=7)
    for dx0, dx1 in ((cx0 + 1, cx0 + 17), (cx0 + 19, cx1 - 1)):
        p.box(dx0, ct + 5, dx1, F0 - 4, "wood", 0.3, z=7.5, top=1)
        p.rect(dx0 + 2, ct + 8, dx1 - 2, F0 - 7, "wood", 0.25, FRONT, z=7.2)   # 门芯（凹进去）
        p.hline(dx0 + 2, dx1 - 2, ct + 7, "wood", 0.16, hp.BOT, z=7.2)
        p.hline(dx0 + 2, dx1 - 2, F0 - 6, "wood", 0.36, hp.TOP, z=7.2)
        kx = dx1 - 3 if dx0 == cx0 + 1 else dx0 + 3
        p.px(kx, ct + 11, "brass", 0.4, hp.nrm(0, -1, 1), z=8)
    p.rect(cx0, F0 - 1, cx1, F0, "wood_d", 0.12, FRONT, z=7)               # 踢脚，最暗
    # 台面上：砧板 + 半条面包、一摞碗、插着木勺的陶罐
    p.box(78, ct - 2, 90, ct - 1, "wood_l", 0.4, z=9, top=1)
    p.dome(84, ct - 3, 4, 2, "kraft", 0.42, z=9.5)
    p.px(87, ct - 3, "kraft", 0.3, hp.RIGHT, z=9.5)
    for k, (bw, by) in enumerate(((9, ct - 1), (8, ct - 3), (7, ct - 5))):
        bx = 94 + k // 2
        for xx in range(bx, bx + bw):
            p.px(xx, by, "glaze", 0.36, hp.TOP, z=9)
            p.px(xx, by - 1 if xx in (bx, bx + bw - 1) else by, "glaze", 0.42, hp.TOP, z=9)
        p.hline(bx + 1, bx + bw - 2, by + 1 if by + 1 < ct else by, "glaze", 0.28, hp.BOT, z=9)
    p.cyl(104, ct - 6, 108, ct - 1, "clay", 0.34, z=9, top_rows=1)
    for k, (sx, sh) in enumerate(((105, 5), (106, 7), (107, 4))):
        p.vline(sx, ct - 6 - sh, ct - 7, "wood_l", 0.38, FRONT, z=9)
    p.px(106, ct - 14, "wood_l", 0.44, hp.TOP, z=9)
    # 炉子
    sx0, sx1, st = 114, 133, 259
    p.box(sx0, st, sx1, F0 - 3, "iron", 0.3, z=8, top=2)
    p.hline(sx0 - 1, sx1 + 1, st, "iron", 0.44, hp.TOP, z=8.5)
    for lx in (sx0 + 1, sx1 - 2):
        p.rect(lx, F0 - 2, lx + 1, F0, "iron", 0.22, FRONT, z=8)
    fx0, fy0 = sx0 + 5, st + 6
    p.box(fx0 - 1, fy0 - 1, fx0 + 10, fy0 + 8, "iron", 0.36, z=8.5, top=1)
    for xx in range(fx0, fx0 + 10):
        for yy in range(fy0, fy0 + 8):
            if xx % 3 == 0:
                p.px(xx, yy, "iron", 0.4, FRONT, z=8.6)                     # 炉门的格栅
            else:
                ember = yy >= fy0 + 5 and (xx * 7 + yy) % 5 != 0
                p.fx(xx, yy, Wm(.30 + .06 * (yy - fy0 - 5), .09, 46) if ember else B(.06, .02, 266), z=8.2, cast=False)
    p.px(fx0 + 11, fy0 + 3, "brass", 0.44, hp.RIGHT, z=9)
    # 烟囱管：从炉顶往上，中间一道接口，进到顶上的石头里
    for yy in range(206, st):
        p.px(sx1 - 5, yy, "iron", 0.3, hp.LEFT, z=6)
        p.px(sx1 - 4, yy, "iron", 0.34, FRONT, z=6)
        p.px(sx1 - 3, yy, "iron", 0.24, hp.RIGHT, z=6)
    for jy in (226, 243):
        p.hline(sx1 - 6, sx1 - 2, jy, "iron", 0.42, hp.TOP, z=6.2)
    # 炉上的水壶
    kx, kb = 118, st - 1
    p.cyl(kx, kb - 5, kx + 7, kb, "tin", 0.34, z=9, top_rows=1)
    p.hline(kx + 2, kx + 5, kb - 6, "tin", 0.4, hp.TOP, z=9)
    p.px(kx + 3, kb - 7, "iron", 0.4, hp.TOP, z=9)
    for k in range(4):
        p.px(kx - 1 - k, kb - 3 - k // 2, "tin", 0.34, hp.TOP, z=9)          # 壶嘴
    for (dx, dy) in ((1, -7), (2, -8), (3, -8), (4, -8), (5, -8), (6, -7)):
        p.px(kx + dx, kb + dy, "iron", 0.3, hp.TOP, z=9.2)                # 提梁
    p.spec.append((kx + 1, kb - 4, kx + 6, 9))
    # 墙上的架板 + 一排罐子瓶子
    p.shelf(76, 112, 236, "wood", 0.34, iron=True)
    p.jar(78, 235, 6, 9, "glaze", "cork")
    p.bottle(85, 235, 3, 11, "glass_g")
    p.jar(89, 235, 5, 6, "clay", "cloth_r")
    p.tin(95, 235, 4, 7, label=False)
    p.jar(100, 235, 6, 8, "glass_b", "iron")                              # 空盐罐（原文 81：「盐，很咸，尝过了」）
    p.bottle(107, 235, 4, 9, "glass_a")
    # 挂杆：勺子、小锅、一只杯子
    p.hline(78, 110, 243, "iron", 0.32, hp.TOP, z=5)
    for hx in (82, 90, 97, 104):
        p.px(hx, 244, "iron", 0.36, FRONT, z=5)
    p.vline(82, 245, 251, "wood_l", 0.34, FRONT, z=5)
    p.dome(82, 253, 1, 1, "wood_l", 0.32, z=5, lower=True)
    p.vline(90, 245, 247, "iron", 0.3, FRONT, z=5)
    p.cyl(87, 248, 93, 251, "iron", 0.32, z=5, top_rows=1)
    p.box(96, 245, 99, 249, "glaze_b", 0.34, z=5, top=1)
    p.px(100, 246, "glaze_b", 0.3, hp.RIGHT, z=5)
    p.vline(104, 245, 250, "tin", 0.36, FRONT, z=5)
    p.px(103, 251, "tin", 0.34, FRONT, z=5)
    p.px(105, 251, "tin", 0.3, FRONT, z=5)
    # 顶上倒挂一束干草（扎绳 + 往下散开）
    hx, hy = 86, 214
    p.vline(hx, 208, hy, "rope", 0.36, FRONT, z=4)
    for k in range(7):
        ln = 7 + (k * 5) % 4
        for j in range(ln):
            p.px(hx - 3 + k + (j * (k - 3)) // 9, hy + 1 + j, "herb", 0.3 + 0.06 * ((k + j) % 2), FRONT, z=4)
    p.hline(hx - 2, hx + 2, hy + 1, "rope", 0.42, hp.TOP, z=4.2)


def furnish_dining(p: hp.Props):
    """餐桌：木桌（台面有厚度，前沿受灯光、桌裙下一道暗、桌腿往下收、一道横撑）、两只三条腿的凳子、
    桌子上方一块条子板（软木，钉满手写条子、一张照片，两张条子之间拉了一根线）、吊着的大提灯。"""
    tx0, tx1, tt = T_X0F, T_X1F, T_TOPF
    for x in range(tx0, tx1 + 1):
        p.px(x, tt, "wood_l", 0.5, hp.TOP, z=12)
        p.px(x, tt + 1, "wood_l", 0.4 + (0.05 if x % 13 == 0 else 0), FRONT, z=12)
        p.px(x, tt + 2, "wood_l", 0.24, hp.BOT, z=12)
    p.px(tx0, tt + 1, "wood_l", 0.34, hp.LEFT, z=12)
    p.px(tx1, tt + 1, "wood_l", 0.36, hp.RIGHT, z=12)
    p.rect(tx0 + 3, tt + 3, tx1 - 3, tt + 4, "wood", 0.26, FRONT, z=11)
    p.hline(tx0 + 3, tx1 - 3, tt + 5, "wood", 0.12, hp.BOT, z=11)
    for lx in (tx0 + 3, tx1 - 5):
        for yy in range(tt + 3, F0D + 1):
            w_ = 3 if yy < tt + 12 else 2
            p.px(lx, yy, "wood", 0.34, hp.LEFT, z=11)
            p.px(lx + 1, yy, "wood", 0.3, FRONT, z=11)
            if w_ == 3:
                p.px(lx + 2, yy, "wood", 0.22, hp.RIGHT, z=11)
    p.hline(tx0 + 6, tx1 - 6, F0D - 8, "wood", 0.28, hp.TOP, z=10)
    for (s0, s1) in ((138, 148), (210, 220)):
        p.box(s0, F0D - 14, s1, F0D - 13, "wood_l", 0.4, z=13, top=1, bottom=False)
        p.hline(s0 + 1, s1 - 1, F0D - 12, "wood", 0.18, hp.BOT, z=13)
        for (lx, d) in ((s0 + 1, -1), (s1 - 2, 1), ((s0 + s1) // 2, 0)):
            for k in range(12):
                xx = lx + (d * k) // 7
                p.px(xx, F0D - 11 + k, "wood", 0.32 if d <= 0 else 0.26, FRONT, z=13 if d else 12)
        p.hline(s0 + 2, s1 - 2, F0D - 5, "wood", 0.26, hp.TOP, z=12.5)
    # 条子板
    bx0, bx1, by0, by1 = 178, 207, 214, 240
    p.box(bx0, by0, bx1, by1, "wood", 0.32, z=1.5, top=1)
    rng = np.random.default_rng(7841)
    for yy in range(by0 + 2, by1 - 1):
        for xx in range(bx0 + 2, bx1 - 1):
            p.px(xx, yy, "cork", 0.3 + (0.06 if rng.random() < 0.18 else 0) - (0.05 if rng.random() < 0.12 else 0),
                 FRONT, z=1.6)
    p.hline(bx0 + 2, bx1 - 2, by0 + 2, "cork", 0.18, hp.BOT, z=1.6)          # 框里一道影子（软木凹进去）
    p.vline(bx0 + 2, by0 + 2, by1 - 2, "cork", 0.2, FRONT, z=1.6)
    pins = [Wm(.46, .1, 28), B(.5, .05, 230), Wm(.6, .09, 90)]
    notes = [(181, 217, 7, 6, 0, "paper"), (190, 216, 6, 8, 1, "card"), (198, 218, 7, 5, -1, "paper"),
             (182, 226, 5, 7, 0, "kraft"), (195, 226, 8, 6, 0, "paper"), (186, 234, 6, 4, 1, "card"),
             (199, 233, 5, 5, 0, "paper")]
    centers = []
    for i, (nx, ny, nw, nh, tl, mt) in enumerate(notes):
        p.slip(nx, ny, nw, nh, tilt=tl, pin=pins[i % 3], mat=mt, t=0.36 + 0.03 * (i % 3), z=2.2, curl=i % 3 == 1)
        centers.append((nx + nw // 2, ny))
    # 一张照片（白边、里面两个人影）
    p.rect(189, 226, 193, 231, "paper", 0.44, FRONT, z=2.3)
    p.rect(190, 227, 192, 230, "glaze_b", 0.2, FRONT, z=2.35)
    p.px(190, 229, "leather", 0.1, FRONT, z=2.4)
    p.px(192, 228, "leather", 0.12, FRONT, z=2.4)
    p.fx(191, 225, pins[0], z=2.5)
    p.line(centers[0][0], centers[0][1], 191, 225, "", 0, z=2.6, fixc=INK_THREAD)
    p.line(191, 225, centers[4][0], centers[4][1], "", 0, z=2.6, fixc=INK_THREAD)
    # 提灯（链子从顶上垂下来）
    p.lantern(166, 228, cord_top=206, cord="chain", big=True)


def furnish_store(p: hp.Props):
    """储物：一块架板上一排罐子、瓶子（一截蜡烛）；墙上一排旧门牌（每个钉子上一块，搪瓷 / 铁皮，大小锈迹都不同，下面一张日期条）；
    地上泡过水的木箱、一只木桶、一只麻袋、一只藤筐；钩子上一卷绳。"""
    p.shelf(238, 288, 240, "wood", 0.32, iron=True)
    x = 240
    for kind, w, h, m in (("jar", 5, 8, "glaze"), ("bottle", 3, 10, "glass_b"), ("jar", 6, 6, "clay"), ("shell", 3, 3, None),
                          ("jar", 4, 9, "glaze_b"), ("bottle", 4, 8, "glass_a"), ("scroll", 9, 3, None),
                          ("jar", 6, 7, "glass_g"), ("candle", 3, 4, None), ("bottle", 3, 11, "glass_g")):
        if kind == "jar":
            p.jar(x, 239, w, h, m, "cork" if w < 6 else "cloth_m",
                  contents=("herb", 0.3, h - 4) if m == "glass_g" else None)
        elif kind == "bottle":
            p.bottle(x, 239, w, h, m)
        elif kind == "shell":
            p.shell(x + 3, 238, 3, 3)
            w = 7
        elif kind == "scroll":
            p.scroll(x, 236, w, 3)
        elif kind == "candle":
            p.candle(x + 1, 239, 4)
        x += w + 1
    # 旧门牌
    for (px_, py, pw, ph, mt, num) in ((294, 233, 8, 6, "glaze_b", 2), (305, 231, 7, 7, "tin", 3), (315, 234, 9, 5, "clay", 2),
                                       (327, 232, 7, 6, "glaze", 1)):
        p.px(px_ + pw // 2, py - 1, "iron", 0.4, FRONT, z=2.5)
        p.box(px_, py, px_ + pw - 1, py + ph - 1, mt, 0.36, z=2.2, top=1)
        p.hline(px_ + 1, px_ + pw - 2, py + 1, mt, 0.46, FRONT, z=2.2) if mt == "glaze_b" else None
        for k in range(num):
            nx = px_ + 2 + k * 2
            p.fx(nx, py + 2, INK, z=2.4)
            p.fx(nx, py + ph - 3, INK, z=2.4)
            if k == 0:
                p.fx(nx + 1, py + 2, INK, z=2.4)
        if mt == "clay":
            for (dx, dy) in ((1, ph - 1), (pw - 2, 1), (pw - 3, ph - 2)):
                p.dt(px_ + dx, py + dy, -0.14)                            # 锈
        p.slip(px_ + 1, py + ph + 1, pw - 2, 2, lines=1, t=0.36, z=2.2, tilt=0)
    # 钩子上一卷绳
    p.px(333, 247, "iron", 0.38, FRONT, z=3)
    for a in range(0, 360, 15):
        for rr in (3, 4):
            xx = 333 + int(round(rr * math.cos(math.radians(a))))
            yy = 252 + int(round(rr * 1.1 * math.sin(math.radians(a))))
            p.px(xx, yy, "rope", 0.36 - 0.08 * (rr == 3) + 0.06 * math.sin(math.radians(a) * 3), hp.nrm(xx - 333, yy - 252, 2), z=3)
    # 地上的东西
    p.crate(240, F0, 20, 16, t=0.38, wet=True)
    p.crate(243, F0 - 16, 14, 11, t=0.4)
    p.barrel(263, F0, 10, 15, t=0.38)
    p.sack(276, F0, 11, 13, t=0.38)
    p.box_small(289, F0, 11, 7, "kraft", 0.32, string=True)
    p.basket(316, F0, 13, 8, t=0.34)
    p.crate(342, F0, 16, 13, t=0.38, wet=True)
    p.crate(360, F0, 12, 10, t=0.36, wet=True, handle=False)


def furnish_shafts(p: hp.Props):
    """两个楼梯井：井 1 一盏吊灯、墙上一张钉着的条子；井 2 墙上一只铁托架挂灯、两张拴线的提醒条、阶下塞的箱子。"""
    p.lantern(372, 178, cord_top=140)
    p.slip(391, 213, 7, 6, tilt=1, pin=Wm(.46, .1, 28), t=0.36)
    p.slip(396, 221, 5, 4, pin=B(.5, .05, 230), t=0.34, mat="card")
    # 井 2：托架（从墙上伸出来一根弯铁）+ 挂灯
    p.vline(60, 106, 112, "iron", 0.32, hp.LEFT, z=3)
    p.hline(60, 66, 106, "iron", 0.38, hp.TOP, z=4)
    p.px(59, 109, "iron", 0.4, FRONT, z=3)
    p.px(59, 112, "iron", 0.4, FRONT, z=3)
    p.lantern(66, 122, cord_top=107, z=7)
    p.slip(40, 174, 8, 6, tilt=-1, pin=Wm(.46, .1, 28), t=0.36)
    p.slip(50, 178, 6, 7, pin=B(.5, .05, 230), t=0.34, mat="card", curl=True)
    p.line(44, 174, 53, 178, "", 0, z=2.6, fixc=INK_THREAD)
    p.crate(52, F1, 14, 12, t=0.32)
    p.crate(68, F1, 16, 16, t=0.34)
    p.box_small(70, F1 - 16, 12, 8, "kraft", 0.34, string=True)
    p.sack(86, F1, 11, 10, t=0.3)


def furnish_bed(p: hp.Props):
    """卧室：石水盆（盆沿受光、水面两道反光）、搭在盆沿上的毯子（褶子）、一只扁枕头；墙上一块小架板（罐子、贝壳、
    一摞本子、一截蜡烛）、一张手画的河道图（四角钉着、右下角卷起来）、一串提醒条。"""
    bx0, bx1, by = 124, 186, F1B - 15
    for x in range(bx0, bx1):
        u = (x - (bx0 + bx1) / 2) / ((bx1 - bx0) / 2)
        depth = int(round(13 * math.sqrt(max(0, 1 - u * u))))
        for y in range(by, by + depth + 2):
            k = (y - by) / 14
            if y <= by:
                n, t = hp.TOP, 0.5                                          # 盆沿：磨亮的一圈
            elif y == by + 1 or y == by + 2:
                n, t = FRONT, 0.4
            elif y == by + 3:
                n, t = hp.BOT, 0.18                                         # 盆沿下的一道影子
            else:
                n, t = hp.nrm(u * 0.7, k * 0.8, 1), 0.46 - 0.14 * k
                if (y - by) % 4 == 0 and (x * 3 + y) % 7 > 1:
                    t -= 0.06                                               # 凿痕：一道道横的
            p.px(x, y, "stone", t, n, z=8)
    for x in range(bx0 + 3, bx1 - 3):
        p.fx(x, by - 1, WATER[2] if (x // 3) % 4 else WATER[3], z=7.5)     # 水面（比盆沿低一点看得到一线）
    # 枕头（左端，扁的）
    p.dome(bx0 + 8, by, 6, 3, "cloth_m", 0.4, z=9)
    p.hline(bx0 + 3, bx0 + 13, by + 1, "cloth_m", 0.26, hp.BOT, z=9)
    # 毯子：搭在右边盆沿上，一半垂到盆外
    for x in range(bx1 - 20, bx1 + 2):
        top = by - 2 + (1 if (x // 4) % 2 else 0)
        drop = by + 3 if x < bx1 - 5 else by + 9 + (x * 7) % 3
        for y in range(top, drop + 1):
            fold = (x // 4) % 2
            n = hp.TOP if y == top else (hp.nrm(0.6 if fold else -0.4, 0, 1))
            p.px(x, y, "cloth_r", 0.36 + (0.08 if y == top else 0) - 0.08 * fold, n, z=9.5)
    # 架板 + 小东西 + 蜡烛
    p.shelf(122, 152, 172, "wood", 0.34)
    p.jar(124, 171, 5, 7, "glaze_b", "cork")
    p.shell(133, 170, 3, 3)
    p.books_flat(138, 171, [(7, 1, "leather", 0), (6, 1, "cloth_t", 1), (7, 1, "kraft", 0)], string=False)
    p.candle(148, 171, 5)
    # 提醒条：一根线上夹着四张
    p.line(118, 158, 150, 160, "", 0, z=2, fixc=B(.22, .02, 250))
    for i, (nx, nw, nh, mt) in enumerate(((120, 6, 7, "paper"), (128, 7, 5, "card"), (137, 5, 8, "paper"), (144, 6, 6, "kraft"))):
        ny = 158 + (nx - 118) // 16 + 1
        p.slip(nx, ny, nw, nh, tilt=(i % 3) - 1, t=0.38, mat=mt, curl=i == 2)
        p.fx(nx + nw // 2, ny - 1, B(.44, .02, 236), z=2.5)              # 夹子
    # 河道图：纸、一条弯弯的河、几个红铅笔圈
    mx0, my0, mw, mh = 160, 152, 26, 20
    for yy in range(mh):
        for xx in range(mw):
            if (xx, yy) in ((mw - 1, mh - 1), (mw - 2, mh - 1), (mw - 1, mh - 2)):
                continue                                                 # 右下角卷起来
            p.px(mx0 + xx, my0 + yy, "paper", 0.36, FRONT, z=1.5)
    p.px(mx0 + mw - 2, my0 + mh - 2, "paper", 0.5, hp.nrm(-1, -1, 1), z=1.8)
    p.px(mx0 + mw - 3, my0 + mh - 1, "paper", 0.24, hp.BOT, z=1.8)
    for xx in range(mw - 2):
        yy = my0 + mh // 2 + int(round(4 * math.sin(xx / 4.0))) - xx // 6
        p.fx(mx0 + 1 + xx, yy, B(.36, .05, 232), z=1.6)
        if xx % 5 != 2:
            p.fx(mx0 + 1 + xx, yy + 1, B(.3, .05, 236), z=1.6)
    for (cx, cy) in ((mx0 + 6, my0 + 6), (mx0 + 18, my0 + 13)):
        for (dx, dy) in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p.fx(cx + dx, cy + dy, INK_R, z=1.7)
    for k in range(4):
        p.fx(mx0 + 3 + k * 2, my0 + 15, INK, z=1.7)
    for (cx, cy) in ((mx0, my0), (mx0 + mw - 1, my0), (mx0, my0 + mh - 1)):
        p.fx(cx, cy, Wm(.46, .1, 28), z=2)
    p.slip(190, 160, 6, 8, tilt=1, pin=B(.5, .05, 230), t=0.36)


def cabinet_doors(p: hp.Props, state):
    """索引柜的门（state = closed / open / box_out），画在 p 上（整张图坐标）。
    关着：两扇框板门（门框受光、门芯凹进去：上沿一道影、下沿一道亮），门芯上钉满大小不一的索引卡（有的歪、有的卷边、
    有的两张叠着），中间两只铜拉环；开着：柜里三块隔板，盒子、铁皮罐、长柄水壶、影像盒（box_out 时只剩一块灰印子），
    门板从正面看成两条窄边贴在柜子两侧（背面钉着几张卡的边）。"""
    rng = np.random.default_rng(7861)
    x0, x1, y0, y1 = CABD_X0, CABD_X1, CABD_Y0, CABD_Y1
    if state == "closed":
        mid = (x0 + x1) // 2
        for (a, b) in ((x0, mid - 1), (mid + 1, x1)):
            p.box(a, y0, b, y1, "wood", 0.34, z=9, top=1)
            for (py0, py1) in ((y0 + 3, y0 + 38), (y0 + 42, y1 - 3)):
                p.rect(a + 3, py0, b - 3, py1, "wood", 0.28, FRONT, z=8.6)
                p.hline(a + 3, b - 3, py0, "wood", 0.16, hp.BOT, z=8.6)
                p.vline(a + 3, py0, py1, "wood", 0.2, hp.RIGHT, z=8.6)
                p.hline(a + 3, b - 3, py1, "wood", 0.42, hp.TOP, z=8.6)
                p.vline(b - 3, py0, py1, "wood", 0.36, hp.LEFT, z=8.6)
                # 索引卡：大小差得多（小卡片、半张纸、一张大单子），有的叠着、有的歪、有的卷边，中间留出几块空的木头
                y = py0 + 2 + int(rng.integers(0, 2))
                while y < py1 - 3:
                    x = a + 4 + int(rng.integers(0, 3))
                    rowh = 0
                    while x < b - 5:
                        cw, ch = [(4, 3), (5, 3), (6, 4), (7, 5), (5, 5), (9, 6), (4, 4)][int(rng.integers(0, 7))]
                        cw = min(cw, b - 3 - x)
                        if cw < 3 or y + ch > py1:
                            break
                        if rng.random() < 0.07:
                            x += cw
                            continue
                        mt = ("card", "paper", "card", "kraft", "paper")[int(rng.integers(0, 5))]
                        yo = int(rng.integers(0, 3))
                        p.slip(x, y + yo, cw, ch, tilt=int(rng.integers(-1, 2)) if rng.random() < 0.35 else 0,
                               lines=None, t=0.34 + rng.random() * 0.1, mat=mt, z=9.2, curl=rng.random() < 0.25,
                               pin=(Wm(.46, .1, 28), B(.5, .05, 230), Wm(.6, .09, 90))[int(rng.integers(0, 3))]
                               if rng.random() < 0.4 else None)
                        x += cw + (1 if rng.random() < 0.55 else -1)         # 偶尔叠在前一张上
                        rowh = max(rowh, ch + yo)
                    y += rowh + int(rng.integers(0, 2))
            p.vline(a, y0 + 1, y1, "wood", 0.28, hp.LEFT, z=9)
        # 拉环（铜）、两道门缝
        p.vline(mid, y0, y1, "wood_d", 0.06, FRONT, z=8.5)
        for rx in (mid - 3, mid + 3):
            ry = y0 + 40
            for (dx, dy) in ((0, 0), (-1, 1), (1, 1), (0, 2)):
                p.px(rx + dx, ry + dy, "brass", 0.42 - 0.08 * dy, hp.nrm(dx, dy - 1, 0.8), z=10)
        for hy in (y0 + 6, y1 - 6):                                     # 合页
            p.px(x0, hy, "iron", 0.4, hp.LEFT, z=9.5)
            p.px(x1, hy, "iron", 0.36, hp.RIGHT, z=9.5)
        return
    # 开着：柜里
    p.rect(x0, y0, x1, y1, "wood_d", 0.12, FRONT, z=2)
    for sx in range(x0 + 6, x1, 7):
        p.vline(sx, y0, y1, "wood_d", 0.05, FRONT, z=2)                   # 背板的板缝
    p.vline(x0, y0, y1, "wood_d", 0.05, FRONT, z=2)
    for sy in (y0 + 20, y0 + 42, y0 + 62):
        p.shelf(x0, x1, sy, "wood", 0.3, brackets=False, z=6)
    s1, s2, s3, s4 = y0 + 19, y0 + 41, y0 + 61, y1
    p.box_small(x0 + 1, s1, 8, 10, "kraft", 0.3)
    p.box_small(x0 + 10, s1, 7, 8, "cloth_t", 0.28)
    p.books_up(x0 + 18, x0 + 27, s1, hmin=6, hmax=11)
    p.jar(x0 + 30, s1, 5, 7, "glaze", "cork")
    p.scroll(x0 + 2, s2 - 2, 8, 3)                                      # 第二层：一卷纸、长柄水壶、影像盒
    kx = x0 + 11
    p.cyl(kx, s2 - 6, kx + 6, s2, "tin", 0.34, z=5, top_rows=1)
    p.px(kx + 3, s2 - 7, "iron", 0.4, hp.TOP, z=5)
    for k in range(10):
        p.px(kx + 7 + k, s2 - 4 - k // 2, "wood_l", 0.36, hp.TOP, z=5)    # 长柄
    p.slip(kx + 1, s2 - 4, 4, 2, lines=1, t=0.36)
    tx = x1 - 13
    if state == "open":
        p.tin(tx, s2, 11, 7, t=0.4)
        p.slip(tx + 2, s2 - 4, 7, 2, lines=1, t=0.42, mat="card")         # 盖上那张：「南桥，退水后，第七日」
    else:
        p.hline(tx, tx + 10, s2, "wood", 0.2, FRONT, z=6.1)                # 拖走以后空出来的一格：一块没落灰的印子
        p.hline(tx + 1, tx + 9, s2 - 1, "wood_d", 0.08, FRONT, z=2.1)
    p.box_small(x0 + 2, s3, 9, 9, "kraft", 0.3, string=True)
    p.bottle(x0 + 13, s3, 4, 10, "glass_g")
    p.box_small(x0 + 19, s3, 10, 7, "glaze_b", 0.3)
    p.shell(x1 - 4, s3 - 1, 3, 3)
    p.box_small(x0 + 2, s4, 12, 12, "kraft", 0.3)
    p.basket(x0 + 16, s4, 13, 8, t=0.3)
    # 门板（从正面看是两条窄边）
    for (a, b, side) in ((CAB_OBJ_X0, CAB_OBJ_X0 + 5, -1), (CAB_OBJ_X1 - 5, CAB_OBJ_X1, 1)):
        for yy in range(y0 - 1, y1 + 2):
            for xx in range(a, b + 1):
                edge = (xx == a and side < 0) or (xx == b and side > 0)
                p.px(xx, yy, "wood", 0.36 if edge else 0.26, hp.LEFT if side < 0 else hp.RIGHT, z=9)
        for yy in range(y0 + 4, y1 - 3, 7):
            p.vline(a + (1 if side < 0 else 2), yy, yy + 2, "card", 0.34, FRONT, z=9.2)


def furnish_coll(p: hp.Props):
    """收藏间：索引柜（柜体：顶檐、踢脚、侧板）、影像机的木座（两格里塞着影像盒）、墙上的插座和一根线、
    右边一架敞开的格子（每层的东西都不一样）、地上一只筐、中间吊一盏灯。"""
    x0, x1 = CAB_X0F, CAB_X1F
    p.box(x0 - 2, 104, x1 + 2, 107, "wood", 0.36, z=10, top=1)            # 顶檐
    p.hline(x0 - 1, x1 + 1, 108, "wood", 0.14, hp.BOT, z=10)
    p.rect(x0, 109, x1, F1, "wood", 0.24, FRONT, z=9)
    p.vline(x0, 109, F1, "wood", 0.3, hp.LEFT, z=9)
    p.vline(x1, 109, F1, "wood", 0.2, hp.RIGHT, z=9)
    p.box(x0, CABD_Y1 + 1, x1, F1 - 2, "wood", 0.3, z=9.5, top=1)          # 踢脚
    for fx_ in (x0 + 1, x1 - 2):
        p.rect(fx_, F1 - 1, fx_ + 1, F1, "wood_d", 0.2, FRONT, z=9)
    cabinet_doors(p, "closed")                                           # 背后也画一遍（物件盖在上面）
    # 影像机的木座
    sx0, sx1, st = 260, 298, 186
    p.box(sx0 - 1, st, sx1 + 1, st + 1, "wood_l", 0.4, z=10, top=1)
    p.rect(sx0, st + 2, sx1, F1 - 2, "wood", 0.24, FRONT, z=9.5)
    p.vline(sx0, st + 2, F1, "wood", 0.3, hp.LEFT, z=9.5)
    p.vline(sx1, st + 2, F1, "wood", 0.22, hp.RIGHT, z=9.5)
    p.vline((sx0 + sx1) // 2, st + 2, F1 - 2, "wood", 0.3, FRONT, z=9.6)
    for (a, b) in ((sx0 + 2, (sx0 + sx1) // 2 - 2), ((sx0 + sx1) // 2 + 2, sx1 - 2)):
        p.rect(a, st + 3, b, F1 - 3, "wood_d", 0.08, FRONT, z=6)
        x = a + 1
        for k in range(3):
            p.tin(x, F1 - 3, 5 + (k % 2), 7 - (k % 2) * 2, t=0.3, label=k != 1)
            x += 6 + (k % 2)
    p.rect(sx0, F1 - 1, sx1, F1, "wood_d", 0.16, FRONT, z=9.5)
    # 墙上的插座、线
    p.box(302, 184, 305, 188, "glaze", 0.34, z=2, top=1)
    p.fx(303, 186, B(.1, .02, 260), z=2.2)
    for k in range(10):
        p.px(297 + (k // 3), 178 + k if k < 7 else 184 + (k - 6) // 2, "rubber", 0.3, FRONT, z=3)
    # 右边的格子架
    gx0, gx1 = 300, 319
    for ux in (gx0, gx1):
        p.rect(ux, 112, ux + 1, F1, "wood", 0.32, FRONT, z=6)
        p.px(ux, 112, "wood", 0.42, hp.TOP, z=6)
        p.px(ux + 1, 112, "wood", 0.42, hp.TOP, z=6)
    for sy in (128, 146, 164, 182):
        p.shelf(gx0, gx1 + 1, sy, "wood", 0.32, brackets=False, z=6.5)
    a = gx0 + 2
    p.jar(a, 127, 5, 8, "glaze", "cork")                                 # 第一层：罐、瓶、海螺
    p.bottle(a + 6, 127, 3, 10, "glass_g")
    p.conch(a + 10, 127, 7)
    p.books_flat(a, 145, [(9, 2, "leather", 0), (8, 1, "cloth_r", 1), (9, 2, "kraft", 0)])   # 第二层：一捆本子、一只小盒
    p.box_small(a + 10, 145, 7, 6, "glaze_b", 0.32)
    for k, (h_, d) in enumerate(((10, 2), (8, 2), (11, 2))):              # 第三层：竖着插的几卷纸、一只贝壳
        p.scroll_up(a + k * 2 + (k > 1), 163, h_, d)
    p.scroll(a + 7, 160, 9, 3)
    p.shell(a + 12, 162, 3, 2)
    p.tin(a, 181, 8, 6)                                                  # 第四层：铁皮罐、两只瓶子
    p.bottle(a + 9, 181, 4, 9, "glass_a")
    p.bottle(a + 14, 181, 3, 7, "glass_b")
    p.basket(gx0 + 2, F1, 15, 9, t=0.32)
    p.lantern(264, 130, cord_top=104)


def furnish_attic(p: hp.Props):
    """阁楼：两层档案架（来客册一本本竖着、有的横着摞、架板前沿挂着手写的小吊牌）、地上一捆没归档的（绳子十字捆）、
    台阶口吊一盏灯。"""
    for sy in (106, 121):
        p.shelf(113, 168, sy, "wood", 0.34)
    p.books_up(115, 136, 105, hmin=7, hmax=11, mats=("leather", "kraft", "cloth_t", "kraft", "cloth_r"))
    p.books_flat(138, 105, [(11, 2, "kraft", 0), (10, 2, "leather", 1), (11, 1, "cloth_g", 0), (9, 2, "kraft", 1)], string=False)
    p.books_up(151, 166, 105, hmin=6, hmax=10, mats=("leather", "kraft", "cloth_m"))
    p.box_small(115, 120, 10, 8, "kraft", 0.32)
    p.books_up(126, 150, 120, hmin=7, hmax=12, mats=("kraft", "leather", "cloth_t", "cloth_g"))
    p.tin(152, 120, 8, 6)
    p.scroll(160, 117, 8, 3)
    for (lx, ly) in ((120, 109), (134, 109), (149, 109), (128, 124), (145, 124), (161, 124)):
        p.px(lx + 1, ly - 1, "rope", 0.4, FRONT, z=6)
        p.slip(lx, ly, 4, 3, lines=1, t=0.36, mat="card", tilt=0)
    p.books_flat(148, F2A, [(14, 2, "kraft", 0), (13, 2, "paper", 1), (14, 2, "kraft", 0), (12, 1, "leather", 1)])
    p.lantern(174, 92, cord_top=76)


def furnish_win(p: hp.Props):
    """窗台：大窗（石壁上凿的深窗洞：左内壁接月光、顶上内壁在影子里；木窗框十字棂；外面是月夜、对岸的石头小镇两点灯、
    河面一道银）、宽石窗台、左边一幅扎起来的布帘、一根晾绳（几张纸、一只袜子）；右边一架窄格子（影像盒、贝壳、来客册）。"""
    wx0, wx1, wy0, wy1 = WIN_X0, WIN_X1, WIN_Y0, WIN_Y1
    w, h = wx1 - wx0 + 1, wy1 - wy0 + 1
    m = bm.opening_mask(w, h, "arch")
    rng = np.random.default_rng(7881)
    horizon = wy0 + int(h * 0.66)
    roofs = {}                                                            # 对岸的石头小镇：高高矮矮的屋顶（一段段平顶 / 尖顶）
    xx = wx0
    while xx <= wx1:
        seg = int(rng.integers(3, 8))
        hh = int(rng.integers(2, 7))
        peak = rng.random() < 0.35
        for k in range(seg):
            roofs[xx + k] = hh + (min(k, seg - 1 - k) if peak else 0)
        xx += seg
    streak = {}                                                           # 河面：几道断断续续的银线（长短不一），月亮底下一列碎光
    for yy in range(horizon + 1, wy1 + 1):
        if rng.random() < 0.55:
            a = wx0 + int(rng.integers(3, w - 6))
            for k in range(int(rng.integers(2, 9))):
                streak[(a + k, yy)] = True
    mxc = wx1 - 13
    for yy in range(horizon + 1, wy1 + 1):
        ln = 2 + (yy - horizon) // 4 + int(rng.integers(0, 2))
        a = mxc - ln // 2 + int(rng.integers(-1, 2))
        if (yy - horizon) % 3 != 2:
            for k in range(ln):
                streak[(a + k, yy)] = True
    for yy in range(h):
        xs = np.nonzero(m[yy])[0]
        if len(xs) == 0:
            continue
        xl, xr = xs[0], xs[-1]
        for xx in xs:
            X_, Y_ = wx0 + xx, wy0 + yy
            ytop = np.nonzero(m[:, xx])[0][0]
            if yy - ytop < 2:
                p.fx(X_, Y_, B(.05, .02, 266), z=0.5, cast=False)          # 顶上内壁：影子
            elif xx - xl < 3:
                p.fx(X_, Y_, (rt.ROCK8[5], rt.ROCK8[4], rt.ROCK8[3])[xx - xl], z=0.5, cast=False)   # 左内壁接月光
            elif xr - xx < 1:
                p.fx(X_, Y_, B(.07, .02, 262), z=0.5, cast=False)
            else:
                Y = Y_
                if Y < horizon - roofs.get(X_, 0):
                    k = (Y - wy0) / max(1, horizon - wy0)
                    c = B(.08 + .1 * k + (.05 if k > 0.86 else 0), .04, 262 - 14 * k)
                    if rng.random() < 0.006:
                        c = B(.6, .02, 230)                                 # 星星（很少）
                    d = math.hypot(X_ - mxc, (Y - (wy0 + 15)) * 1.1)
                    if d < 3.2:
                        c = B(.74, .03, 220)                                # 月亮
                    elif d < 6:
                        c = B(.32, .04, 234)                                # 月晕
                    elif d < 8.5:
                        c = B(.24, .04, 240)
                elif Y < horizon:
                    c = B(.055, .025, 264)                                  # 屋顶的剪影
                else:
                    k = (Y - horizon) / max(1, wy1 - horizon)
                    c = B(.15 - .05 * k, .04, 258)
                    if streak.get((X_, Y)):
                        c = B(.38, .03, 236) if abs(X_ - mxc) < 4 else B(.28, .03, 240)
                p.fx(X_, Y_, c, z=0.5, cast=False)
    for (lx, ly) in ((wx0 + 14, horizon - 2), (wx0 + 33, horizon - 3)):
        p.fx(lx, ly, Wm(.56, .09, 72), z=0.6, cast=False)                   # 对岸两点灯
        p.fx(lx, ly + 3, Wm(.38, .06, 64), z=0.6, cast=False)
    # 窗框 + 十字棂（木，月光从外面来：框的左内沿亮）
    mx, my = (wx0 + wx1) // 2, wy0 + int(h * 0.5)
    for yy in range(h):
        if m[yy, w // 2]:
            p.px(mx, wy0 + yy, "wood", 0.3, FRONT, z=1)
            p.px(mx + 1, wy0 + yy, "wood", 0.22, hp.RIGHT, z=1)
    for xx in range(3, w - 1):
        p.px(wx0 + xx, my, "wood", 0.34, hp.TOP, z=1)
        p.px(wx0 + xx, my + 1, "wood", 0.2, hp.BOT, z=1)
    for k in range(6):                                                    # 玻璃上两道斜的反光
        p.fx(wx0 + 6 + k, wy0 + 18 - k, B(.34, .02, 228), z=0.8, cast=False)
        if k < 4:
            p.fx(mx + 6 + k, my + 12 - k, B(.3, .02, 228), z=0.8, cast=False)
    # 石窗台
    sy = wy1 + 1
    p.hline(wx0 - 3, wx1 + 3, sy, "stone", 0.5, hp.TOP, z=3)
    p.hline(wx0 - 3, wx1 + 3, sy + 1, "stone", 0.34, FRONT, z=3)
    p.hline(wx0 - 2, wx1 + 2, sy + 2, "stone", 0.14, hp.BOT, z=3)
    # 布帘（左边，中间用绳扎起来：上下两截是散开的布，褶子竖着，扎绳那里收窄）
    tie = wy0 + int(h * 0.55)
    for yy in range(wy0 + 4, wy1 + 1):
        if yy < tie:
            wd = 3 + int(4 * (yy - wy0 - 4) / max(1, tie - wy0 - 4))
        else:
            wd = max(3, 7 - (yy - tie) // 2) if yy < tie + 5 else 4 + (1 if (yy % 5) < 2 else 0)
        if abs(yy - tie) <= 1:
            wd = 3
        for xx in range(wd):
            fold = (xx + (1 if yy > tie else 0)) % 3
            n = hp.nrm(-0.6 if fold == 0 else (0.5 if fold == 1 else 0.1), 0, 1)
            p.px(wx0 - 2 + xx, yy, "cloth_r", 0.42 + (0.07 if fold == 1 else 0) - (0.1 if fold == 0 else 0), n, z=4)
    p.hline(wx0 - 2, wx0, tie, "rope", 0.5, hp.TOP, z=4.5)
    p.px(wx0 - 3, tie + 1, "rope", 0.4, FRONT, z=4.5)
    p.px(wx0 - 3, tie + 2, "rope", 0.36, FRONT, z=4.5)
    p.hline(wx0 - 5, wx0 + 6, wy0 + 3, "iron", 0.36, hp.TOP, z=4.2)      # 帘杆
    # 晾绳（从左边石壁到窗框）
    lx0, lx1, ly = 210, wx0 - 4, 44
    for xx in range(lx0, lx1 + 1):
        p.fx(xx, ly + int(3 * math.sin(math.pi * (xx - lx0) / (lx1 - lx0))), B(.26, .02, 246), z=3)
    for (xx, kind) in ((215, "paper"), (222, "sock"), (228, "photo")):
        yy = ly + int(3 * math.sin(math.pi * (xx - lx0) / (lx1 - lx0))) + 1
        if kind == "paper":
            p.slip(xx, yy, 5, 7, lines=2, t=0.34, curl=True, tilt=1)
        elif kind == "sock":
            p.rect(xx, yy, xx + 1, yy + 5, "cloth_r", 0.32, FRONT, z=3)
            p.hline(xx, xx + 3, yy + 5, "cloth_r", 0.28, FRONT, z=3)
        else:
            p.rect(xx, yy, xx + 4, yy + 5, "paper", 0.38, FRONT, z=3)
            p.rect(xx + 1, yy + 1, xx + 3, yy + 3, "glaze_b", 0.2, FRONT, z=3.1)
        p.fx(xx + 1, yy - 1, B(.44, .02, 236), z=3.5)
    # 右边的窄格子
    gx0, gx1 = 300, 318
    for ux in (gx0, gx1):
        p.rect(ux, 42, ux + 1, F2B, "wood", 0.3, FRONT, z=6)
    for sy_ in (56, 72, 88):
        p.shelf(gx0, gx1 + 1, sy_, "wood", 0.32, brackets=False, z=6.5)
    p.tin(gx0 + 2, 55, 8, 5)
    p.tin(gx0 + 3, 50, 7, 5, label=False)
    p.shell(gx0 + 14, 54, 3, 3)
    p.books_up(gx0 + 2, gx0 + 9, 71, hmin=7, hmax=10)
    p.box_small(gx0 + 10, 71, 7, 6, "kraft", 0.32, string=True)
    p.jar(gx0 + 2, 87, 5, 7, "glass_g", "cork", contents=("shell", 0.3, 3))
    p.books_flat(gx0 + 8, 87, [(9, 2, "leather", 0), (8, 2, "kraft", 1)])


def furnish_nook(p: hp.Props):
    """右上的小储藏室（只露出一半）：两块架板，一排盒子 / 罐子 / 一卷纸，一截蜡烛。"""
    for sy in (93, 107):
        p.shelf(338, 372, sy, "wood", 0.3, brackets=False)
    p.box_small(340, 92, 7, 7, "kraft", 0.3)
    p.jar(348, 92, 4, 6, "glaze", "cork")
    p.books_up(353, 362, 92, hmin=5, hmax=8)
    p.tin(341, 106, 7, 5)
    p.candle(352, 106, 4)
    p.scroll(356, 103, 8, 3)


def chair_pixels(p: hp.Props, x):
    """一把木椅子（侧面）：靠背两根立柱 + 三根横档、坐面有厚度（顶一线亮）、四条腿看到两条、腿间一道横撑。
    x = 帧里椅子左边（全图坐标）；底在 F2B。"""
    seat = F2B - 13
    for yy in range(F2B - 29, F2B + 1):
        p.px(x + 10, yy, "wood", 0.32 if yy < seat else 0.28, hp.RIGHT if yy >= seat else FRONT, z=12)
        p.px(x + 11, yy, "wood", 0.22, hp.RIGHT, z=12)
    p.px(x + 10, F2B - 30, "wood", 0.44, hp.TOP, z=12)
    for k, yy in enumerate((F2B - 27, F2B - 22, F2B - 17)):
        p.px(x + 9, yy, "wood", 0.36, hp.TOP, z=12)
        p.px(x + 8, yy, "wood", 0.3, hp.TOP, z=12) if k == 0 else None
    p.hline(x, x + 11, seat, "wood_l", 0.46, hp.TOP, z=12)
    p.hline(x, x + 11, seat + 1, "wood_l", 0.32, FRONT, z=12)
    p.hline(x + 1, x + 10, seat + 2, "wood", 0.14, hp.BOT, z=12)
    for yy in range(seat + 3, F2B + 1):
        p.px(x + 1, yy, "wood", 0.3, hp.LEFT, z=12)
        p.px(x + 2, yy, "wood", 0.24, FRONT, z=12)
    p.hline(x + 3, x + 9, F2B - 5, "wood", 0.28, hp.TOP, z=12)
    p.slip(x + 4, seat + 3, 4, 2, lines=1, t=0.34, mat="card")


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
    fp = hp.Props(W, H, seed=7023)
    lx, ly = 36 + door_w + 6, F0 + 1 - door_h + 6
    fp.hline(lx - 3, lx, ly - 7, "iron", 0.38, hp.TOP, z=3)                 # 从石头里伸出来的铁托架
    fp.vline(lx - 3, ly - 7, ly - 4, "iron", 0.3, hp.LEFT, z=3)
    fp.lantern(lx, ly, cord_top=ly - 6, z=6)
    fr = fp.render([(lx, ly, 6, 14, 0.8)])
    cv.a[fr[..., 3] > 0] = fr[fr[..., 3] > 0]
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
FURNISH = (furnish_hall, furnish_kitchen, furnish_dining, furnish_store, furnish_shafts, furnish_bed, furnish_coll,
           furnish_attic, furnish_win, furnish_nook)


def build():
    _r, _b, _f, _l, dobjs = bm.build_home_parts()
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
    draw_steps(back, STAIR1, masks["shaft1"] | masks["store"])
    draw_steps(back, STAIR2, masks["shaft2"])
    draw_steps(back, RAMP, masks["ramp"] | masks["attic"] | masks["win"], body=8)
    # 家具和小物件：先记形，墙上先打光（东西挡出影子），再给东西打光贴上去
    p = hp.Props(W, H, seed=7800)
    p.clip = allm | nook
    for f in FURNISH:
        f(p)
    lit = dilate(allm | nook, 2) & (back.a[..., 3] > 0)
    hp.wall_light(back.a, lit, LAMPS, p.cast, np.random.default_rng(7031))
    pr = p.render(LAMPS)
    pm = pr[..., 3] > 0
    back.a[pm] = pr[pm]
    floor_water(back, 20, 134, allm)
    floor_water(back, 232, 406, allm)
    top_things(back, km)
    clefts(back, km, dilate(allm | nook, 2))

    front = build_front(rock, allm, nook)
    clefts(front, front.a[..., 3] > 0, np.zeros((H, W), bool))
    light = build_light(allm)
    objs = build_objects(dobjs, p, back.a)
    return back.a, front.a, light, objs


def build_light(allm):
    """光层（盖在家具上、人下面）：每盏灯玻璃外一小圈很窄的光晕（两档，硬边），不再是一大团糊的锥形；大窗斜进来一道月光。"""
    img = np.zeros((H, W, 4), np.uint8)
    for (lx, ly, lz, r, pw) in [lp for lp in LAMPS if len(lp) == 5]:
        r1, r2 = 2.5 + 3.0 * pw, 5.0 + 5.0 * pw
        for y in range(int(ly - r2) - 1, int(ly + r2) + 2):
            for x in range(int(lx - r2) - 1, int(lx + r2) + 2):
                if not (0 <= x < W and 0 <= y < H) or not allm[y, x]:
                    continue
                d = math.hypot(x - lx, (y - ly) * 1.15)
                a = 40 if d <= r1 else (18 if d <= r2 else 0)
                if a:
                    img[y, x] = (255, 214, 142, int(a * pw))
    # 大窗斜进来的一道月光
    for y in range(WIN_Y0, F2B + 1):
        t = (y - WIN_Y0) / (F2B - WIN_Y0)
        for x in range(WIN_X0 - int(22 * t), WIN_X1 + 6 - int(22 * t)):
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


def render_crop(draw, x0, y0, w, h, seed):
    """在一张整图大小的 Props 上画（draw(p)），按屋里的灯打光，裁出物件的框。"""
    p = hp.Props(W, H, seed=seed)
    draw(p)
    return p.render(LAMPS)[y0:y0 + h, x0:x0 + w].copy()


def cabinet_frames(x0, y0, w, h):
    return [render_crop(lambda p, s=st: cabinet_doors(p, s), x0, y0, w, h, 7860) for st in ("closed", "open", "box_out")]


def player_case(p: hp.Props, x0, y0, tape):
    """影像机（帧左上角 x0, y0；36×34）：上面一台老显示器（米灰外壳、四角圆、屏幕凹在一圈深色框里、右边两只旋钮和喇叭孔、
    框下沿贴一张小条）；下面一台读带机（铁皮、插带口、三只按钮、指示灯的位置）；tape = 带子插着（露出一截、贴着条）。"""
    for yy in range(0, 26):
        for xx in range(1, 35):
            if (xx, yy) in ((1, 0), (34, 0), (1, 25), (34, 25)):
                continue
            n, t = FRONT, 0.34
            if yy == 0 or (yy == 1 and xx in (1, 34)):
                n, t = hp.TOP, 0.46
            elif xx == 1:
                n, t = hp.LEFT, 0.36
            elif xx == 34:
                n, t = hp.RIGHT, 0.26
            elif yy == 25:
                n, t = hp.BOT, 0.2
            p.px(x0 + xx, y0 + yy, "glaze", t, n, z=12)
    for yy in range(2, 24):                                               # 屏幕外的一圈深框（凹进去：上沿暗、下沿亮一线）
        for xx in range(3, 31):
            t = 0.12 if yy == 2 or xx == 3 else (0.24 if yy == 23 or xx == 30 else 0.16)
            p.px(x0 + xx, y0 + yy, "rubber", t, FRONT, z=11.6)
    for ky in (6, 10):                                                    # 旋钮
        p.px(x0 + 32, y0 + ky, "brass", 0.42, hp.nrm(0, -1, 0.8), z=12.5)
        p.px(x0 + 32, y0 + ky + 1, "brass", 0.26, hp.BOT, z=12.5)
    for yy in range(14, 23, 2):                                           # 喇叭孔
        p.hline(x0 + 31, x0 + 33, y0 + yy, "glaze", 0.16, hp.BOT, z=12)
    p.slip(x0 + 21, y0 + 24, 6, 2, lines=1, t=0.4, mat="card")
    # 读带机
    p.box(x0, y0 + 26, x0 + 35, y0 + 33, "tin", 0.3, z=12, top=1)
    p.hline(x0 + 1, x0 + 34, y0 + 27, "tin", 0.24, FRONT, z=12)
    p.rect(x0 + 4, y0 + 29, x0 + 16, y0 + 30, "rubber", 0.04, FRONT, z=11)
    p.hline(x0 + 4, x0 + 16, y0 + 31, "tin", 0.4, hp.TOP, z=12)
    for bx in (x0 + 20, x0 + 23, x0 + 26):
        p.px(bx, y0 + 29, "tin", 0.46, hp.TOP, z=12.4)
        p.px(bx, y0 + 30, "tin", 0.2, hp.BOT, z=12.4)
    if tape:
        p.box(x0 + 5, y0 + 27, x0 + 15, y0 + 29, "tin", 0.44, z=12.6, top=1)
        p.slip(x0 + 7, y0 + 28, 5, 1, lines=0, t=0.42, mat="card")


def player_frames(dframes):
    """D 的影像帧（屏幕里的影像、黑屏扫描线、红灯）原样，外壳换成新画的；屏幕四角磨圆，关着时玻璃上映着吊灯的一点光。"""
    x0, y0 = PL_X, PL_Y
    w, h = dframes[0].shape[1], dframes[0].shape[0]
    case = {tp: render_crop(lambda p, t=tp: player_case(p, x0, y0, t), x0, y0, w, h, 7870) for tp in (False, True)}
    rha = bm._rha()
    kinds = [(st, kind) for st, kind, n in rha.PLAYER_ORDER for _ in range(n)]
    out = []
    sx0, sy0, sw, sh = 4, 3, rha.PL_SCR[0], rha.PL_SCR[1]
    for i, f in enumerate(dframes):
        st, kind = kinds[i]
        a = case[kind != "off"].copy()
        scr = f[sy0:sy0 + sh, sx0:sx0 + sw].copy()
        if kind == "off":
            scr[:] = (*B(.09, .02, 250), 255)
            for yy in range(sh):
                for xx in range(sw):
                    d = math.hypot((xx - sw / 2) / (sw / 2), (yy - sh / 2) / (sh / 2))
                    if d < 0.55:
                        scr[yy, xx, :3] = B(.12, .025, 246)                # 鼓出来的玻璃：中间亮一档
            for k in range(5):
                scr[2, 3 + k, :3] = B(.22, .02, 236)                      # 上沿一道冷反光
            scr[3, 2, :3] = B(.18, .02, 236)
            scr[2, 4, :3] = Wm(.5, .08, 70)                                 # 映着吊灯的一点
        else:
            scr[1, 2, :3] = B(.5, .02, 228) if kind != "black" else B(.24, .02, 236)     # 玻璃反光一点
        for (cx, cy) in ((0, 0), (sw - 1, 0), (0, sh - 1), (sw - 1, sh - 1)):
            scr[cy, cx, :3] = case[False][sy0 + cy, sx0 + cx, :3] if case[False][sy0 + cy, sx0 + cx, 3] else B(.06, .02, 266)
        a[sy0:sy0 + sh, sx0:sx0 + sw] = scr
        led_on = (kind == "black" and st == "red_blink" and kinds[:i].count((st, kind)) < 2) or \
            kind in ("part1", "part2", "tilt", "ear", "paused", "glitch")
        a[29, 31, :3] = Wm(.56, .14, 30) if led_on else Wm(.2, .03, 30)
        a[29, 31, 3] = 255
        if led_on:
            a[28, 31, :3] = Wm(.36, .06, 36)
        out.append(a)
    return out


def hourglass_pixels(p: hp.Props, x0, y0, top_sand, bot_sand, stream):
    """桌上的沙漏（帧 10×14）：上下两块木盖（顶一线亮）、两根细木柱、玻璃只画轮廓（朝灯那边亮一线、里面透明看得到后面的墙）、
    沙（上面那泡从细腰往上堆、下面那泡堆成小丘）、中间一线往下漏；右边一根铁丝挑着一只铜铃。"""
    hw = {1: 2, 2: 2, 3: 2, 4: 2, 5: 1, 6: 0, 7: 0, 8: 1, 9: 2, 10: 2, 11: 2, 12: 2}
    for xx in range(7):
        p.px(x0 + xx, y0, "wood_l", 0.5, hp.TOP, z=13)
        p.px(x0 + xx, y0 + 13, "wood_l", 0.44 if xx else 0.38, hp.TOP if xx else hp.LEFT, z=13)
    p.px(x0 + 6, y0 + 13, "wood_l", 0.3, hp.RIGHT, z=13)
    for yy in range(1, 13):
        p.px(x0, y0 + yy, "wood", 0.36, hp.LEFT, z=13)
        p.px(x0 + 6, y0 + yy, "wood", 0.24, hp.RIGHT, z=13)
        a = hw[yy]
        p.fx(x0 + 3 - a, y0 + yy, B(.5, .03, 222), z=12.5)
        if a:
            p.fx(x0 + 3 + a, y0 + yy, B(.34, .03, 228), z=12.5)
    for i in range(top_sand):                                             # 上面的沙
        yy = 5 - i
        for xx in range(3 - hw[yy] + 1, 3 + hw[yy]):
            p.px(x0 + xx, y0 + yy, "kraft", 0.46 - 0.04 * (xx == 3 + hw[yy] - 1), FRONT, z=12.6)
    for i in range(bot_sand):                                             # 下面的沙（小丘）
        yy = 12 - i
        a = hw[yy] - (1 if i == bot_sand - 1 else 0)
        for xx in range(3 - a + (0 if i < bot_sand - 1 else 1), 3 + a + (0 if i < bot_sand - 1 else 0)):
            p.px(x0 + xx, y0 + yy, "kraft", 0.42 + (0.08 if i == bot_sand - 1 else 0), hp.TOP if i == bot_sand - 1 else FRONT, z=12.6)
    if stream is not None:
        for yy in range(6, 12 - bot_sand + 1):
            if (yy + stream) % 2 == 0:
                p.px(x0 + 3, y0 + yy, "kraft", 0.5, FRONT, z=12.7)
    p.fx(x0 + 2, y0 + 2, B(.62, .02, 222), z=12.8)                        # 玻璃上一点高光
    for yy in range(3, 14):                                               # 铁丝 + 铜铃
        p.px(x0 + 7, y0 + yy, "iron", 0.36, FRONT, z=13)
    p.px(x0 + 8, y0 + 3, "iron", 0.4, hp.TOP, z=13)
    p.dome(x0 + 8.5, y0 + 6, 1, 2, "brass", 0.4, z=13.5)
    p.px(x0 + 8, y0 + 7, "brass", 0.3, hp.BOT, z=13.5)
    p.px(x0 + 9, y0 + 7, "brass", 0.26, hp.BOT, z=13.5)


def hourglass_frames(x0, y0, w, h):
    """和 D 的一样的帧序：default（沙在上面）、running 4 帧、empty。"""
    seq = [(4, 0, None)] + [(3 - (k // 2), 1 + (k // 2), k) for k in range(4)] + [(0, 4, None)]
    return [render_crop(lambda p, a=a: hourglass_pixels(p, x0, y0, *a), x0, y0, w, h, 7880) for a in seq]


def chair_frames(x0, y0, w, h):
    return [render_crop(lambda p, cx=cx: chair_pixels(p, cx), x0, y0, w, h, 7890) for cx in (285, 254)]


def labels_frames(p: hp.Props, back):
    """标签：剧本 river_home_labels on = 晨注意到「屋里每件东西几乎都有标签」。default 什么都不画（纸条在 home_back 里），
    on 把每张纸条提亮一档多、往暖推一点（字迹不动；这一状态整章大部分时间开着，不能刺眼）。柜门、影像机上的纸条在它们自己的物件里，这层不管。"""
    on = np.zeros((H, W, 4), np.uint8)
    cache = {}
    skip = np.zeros((H, W), bool)
    skip[CABD_Y0 - 2:CABD_Y1 + 2, CAB_OBJ_X0:CAB_OBJ_X1 + 1] = True
    for (x, y) in p.slips:
        if not (0 <= x < W and 0 <= y < H) or skip[y, x] or back[y, x, 3] == 0:
            continue
        c = tuple(int(v) for v in back[y, x, :3])
        if p.fix[y, x, 3] and tuple(p.fix[y, x, :3]) == INK[:3]:
            on[y, x] = (*INK[:3], 255)
            continue
        if c not in cache:
            cache[c] = bm.mixc(c, Wm(min(.7, bm.to_lab(c)[0] + .12), .06, 80), 0.5)
        on[y, x] = (*cache[c], 255)
    return [np.zeros((H, W, 4), np.uint8), on]


def build_objects(dobjs, p, back):
    """物件：桌面、沙漏、本子、照片、来客册用 D 的帧（月夜色已上），跟着它那块家具挪；
    柜门、影像机、椅子、标签用这里新画的（框和状态不变）。dobjs 是 river_bank_moon_art 的（y 多了 HDY）。"""
    hdy = bm.HDY
    move = {"river_home_table": "dining", "river_home_hourglass": "dining", "niff_notebook": "dining", "niff_photo": "dining",
            "river_home_cabinet": "cabinet", "river_home_player": "stand"}
    out = {}
    for prop, img, frames, x, y, states, note in dobjs:
        y -= hdy                                                    # → D 坐标
        if prop in move:
            dx, dy = PIECES[move[prop]][1]
            x, y = x + dx, y + dy
            if prop == "river_home_cabinet":
                frames = cabinet_frames(x, y, frames[0].shape[1], frames[0].shape[0])
            elif prop == "river_home_player":
                frames = player_frames(frames)
            elif prop == "river_home_hourglass":
                frames = hourglass_frames(x, y, frames[0].shape[1], frames[0].shape[0])
            out[prop] = (img, frames, x, y, states, note)
        elif prop == "river_home_chair":
            dx = PIECES["window"][1][0]
            x, y = x + dx, y + (F2B - DFL)
            out[prop] = (img, chair_frames(x, y, frames[0].shape[1], frames[0].shape[0]), x, y, states,
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
            out[prop] = (img, labels_frames(p, back), 0, 0, states,
                         note + "；整张图大小（标签在三层的各个洞里），点击框只在门厅雨衣那块")
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
