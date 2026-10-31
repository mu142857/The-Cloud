"""河流篇 · 水下仓库 warehouse（第三版：先走一段开阔的水底，再到泡在水底里的半塌石头仓库）。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_underwater_art.py [--preview 目录]

输出 art/river_city/warehouse/*.png + room.json（覆盖第二版）。约定见 docs/river_rooms_contract.md。

作者（10-30）：「水下仓库太封闭了，我最好看的水下背景都没了，或许也可以走一段再到仓库」——水底是他打 5 分的场景。
所以：
- 远景全部直接引用作者原来的水底 `res://art/underwater/*`（deep / distant / far / midfar / head / headweeds / kelp），
  会动的东西（水面碎月、月光光柱、鲸、鱼群、焦散、发光果荚、气泡）由 scripts/river_uw_fx.gd 照 scenes/underwater_test.tscn 原样搭。
- 0..690：开阔的河床 = 原来的 main / bedweeds / front（前景大叶子），一盏出口灯 + 导绳的桩，别的什么都没有（不能点，只有景色）。
- 690..1360：一栋泡在水底的旧石头仓库，剖面：前墙塌成了地上的一排碎石（前景层），能看进屋里；
  左半边屋顶整个塌了、后墙只剩半截（看得见后面的石头人头、海带、光柱），右边内间的屋角也塌了一块，大厅后墙一扇窗洞。
  东西照剧本，少而精：贴圆字标签的几只箱子、破箱子、抽屉全朝右敞着的矮柜、绑到屋顶下的桌椅、浮箱、倒下的高柜、
  堵着内门的五斗柜、内门、设备柜、旧泄水门 + 操作记录、出口灯、导绳和两个绳结。
画法：石头一块一块（每块自己的明暗 + 顶上受光 + 右沿亮 + 磨圆的角 + 崩口 + 石缝），整体明暗由「月光从右上照进来、
被屋顶挡掉多少」算出来（光线投射），所以塌顶下面亮、屋顶下面暗，色块边是光照的边。苔藓长在朝上的面，水渍从石缝往下拖。
颜色：石头 OKLCh L .045→.33、色相 262→242（和原来水底的石头人头同一族），木头偏暖但很灰；暖黄只有出口灯。
alpha 只有 0/255，所有随机固定 seed。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import underwater_art as ua  # noqa: E402
import uw_props as up  # noqa: E402
from oscarkit.palette import from_lch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "river_city" / "warehouse"
UW = ROOT / "art" / "underwater"

W, H = 1360, 270
G = 226                      # 屋里地板（晨脚底那一行）；屋外是原来河床的 ground_y（≈226 上下起伏 2 格）
OPEN = 690                   # 0..OPEN 开阔的水底
HEAD_X = 40                  # head 层的 x：开场石头人头在右边，走进仓库时正好在左边塌掉的后墙里

# ---- 仓库的结构（房间坐标）
LW = (698, 714)              # 左墙剖面（门洞 166..G）
BACK = (714, 1176)           # 大厅后墙（右头压在巨石下面）
ROOF_Y = (82, 96)            # 屋顶剖面（上沿 82，下沿 95）
ROOF_A = (932, 1105)         # 大厅右半的屋顶
PART = (1088, 1098)          # 隔墙剖面（内门 166..G）
ROCK = (1146, W)             # 巨石（内间凿在里面）
CAVE = (1146, 1340)          # 内间（左边就是巨石的边：洞口朝着屋角塌口敞开）
PORT = (1247, 134, 10)        # 内间后壁凿穿的圆窗（中心、半径）
WIN = (1036, 1066, 108, 150)  # 大厅后墙的窗洞
DOOR_TOP = 166

# ---- 东西
POST = (20, 32)              # 出口灯的石桩
ROPE_Y = 184                 # 导绳（= room.json rope.anchor 的 y；引擎的绳结也画在这一行）
STAKES = [196, 372, 548]     # 开阔那段的铁桩
HOOKS = [762, 906, 1124, 1166, 1252]   # 屋里后墙上的挂钩（1124 / 1166 = 两个绳结）
BOXES = (762, 834)
LOWCAB = (870, 904)
EQUIP = (1192, 1230)


def oc(L, C, h):
    return tuple(int(v) for v in from_lch(float(L), float(C), float(h)))


def rgba(c):
    return tuple(int(v) for v in c[:3]) + (255,)


STONE = ua.bramp(8, .045, .33, 262, 242)
SECT = ua.bramp(8, .05, .34, 262, 242)
ROCKP = ua.bramp(8, .05, .34, 262, 244)
MOSS = [oc(.1, .026, 222), oc(.14, .03, 212), oc(.19, .032, 204), oc(.24, .03, 198)]
WOOD = [oc(.07, .01, 255), oc(.1, .012, 68), oc(.135, .014, 70), oc(.175, .016, 72), oc(.22, .017, 75),
        oc(.27, .016, 80)]                         # 泡久了的木头：很灰，亮面才看得出一点暖
WOODH = WOOD[1:] + [oc(.32, .015, 84)]            # 小游戏要点的东西（高柜、五斗柜、内门）亮一档，暗处也读得出
PAPER = [oc(.24, .01, 240), oc(.3, .012, 85), oc(.36, .014, 88)]
IRON = ua.bramp(6, .055, .28, 254, 232)
RUST = [oc(.14, .018, 45), oc(.18, .022, 50)]
CAB = [oc(.075, .014, 240), oc(.11, .018, 220), oc(.15, .02, 208), oc(.2, .022, 202), oc(.26, .022, 198),
       oc(.32, .02, 196)]
FRONT = ua.bramp(4, .035, .1, 266, 256)        # 前景（和原来 front.png 一样近黑）
WARM = [oc(.26, .05, 52), oc(.36, .07, 58), oc(.48, .085, 64), oc(.58, .09, 70), oc(.66, .085, 78)]
LIGHTC = [oc(.30, .05, 236), oc(.38, .055, 232), oc(.46, .055, 228)]   # 光柱层（层 alpha 0.12）
BAYER = ua.BAYER


class Img:
    def __init__(self, w, h):
        self.a = np.zeros((h, w, 4), np.uint8)

    @property
    def w(self):
        return self.a.shape[1]

    @property
    def h(self):
        return self.a.shape[0]

    def put(self, x, y, c):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = rgba(c)

    def rect(self, x0, y0, x1, y1, c):
        """[x0, x1) × [y0, y1)"""
        x0, x1 = max(0, int(x0)), min(self.w, int(x1))
        y0, y1 = max(0, int(y0)), min(self.h, int(y1))
        if x1 > x0 and y1 > y0:
            self.a[y0:y1, x0:x1] = rgba(c)

    def paste(self, src, x, y):
        h, w = src.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        s = src[y0 - y:y1 - y, x0 - x:x1 - x]
        m = s[..., 3] > 0
        self.a[y0:y1, x0:x1][m] = s[m]

    def save(self, path):
        Image.fromarray(self.a).save(path)


def line(img, x0, y0, x1, y1, c):
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for i in range(n + 1):
        t = i / max(1, n)
        img.put(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, c)


def sag_line(img, x0, y0, x1, y1, sag, c, c_lit=None):
    """一根下垂的绳（抛物线），一格宽、连着；c_lit：上沿偶尔一格亮（绳子的纤维）。"""
    n = int(abs(x1 - x0)) * 2 + 2
    prev = None
    for i in range(n + 1):
        t = i / n
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t + sag * 4 * t * (1 - t)
        p = (int(round(x)), int(round(y)))
        if prev is not None and abs(p[1] - prev[1]) > 1:
            for yy in range(min(p[1], prev[1]) + 1, max(p[1], prev[1])):
                img.put(prev[0], yy, c)
        img.put(*p, c_lit if (c_lit is not None and i % 6 < 2) else c)          # 拧着的绳：隔几格一段亮一点
        prev = p


def tile_from(path, w, h=None, y=0):
    a = np.asarray(Image.open(path).convert("RGBA"))
    th, tw = a.shape[:2]
    out = np.zeros((h or th, w, 4), np.uint8)
    for x0 in range(0, w, tw):
        x1 = min(w, x0 + tw)
        out[y:y + th, x0:x1] = a[:, :x1 - x0]
    return out


def gy_out(x):
    return float(ua.ground_y(x))


def ground_poly():
    pts = []
    for x in range(0, OPEN - 8, 8):
        pts.append([x, int(round(gy_out(x)))])
    pts.append([OPEN - 4, int(round(gy_out(OPEN - 4)))])
    pts.append([OPEN + 4, G])
    pts.append([W, G])
    return pts


# ====================================================================== 结构遮罩
def jag(x0, x1, base, amp, rng, period=7.0):
    """一条啃过的边（崩塌的轮廓）：base(x) 上叠一点平滑噪声 + 几个一块一块的台阶（掉了的石块）。"""
    xs = np.arange(x0, x1)
    b = np.array([base(x) for x in xs], float)
    nz = np.zeros(len(xs))
    for k in range(1, 4):
        nz += rng.uniform(0.4, 1.0) / k * np.sin(xs / (period * k) + rng.uniform(0, 6.28))
    out = b + amp * nz
    # 台阶：每 6~14 格一段取同一个值（石块是一块一块掉的，不是波浪线）
    i = 0
    while i < len(xs):
        n = int(rng.integers(5, 14))
        out[i:i + n] = np.round(out[i:i + n].mean() + rng.uniform(-1.5, 1.5))
        i += n
    return dict(zip(xs.tolist(), out.astype(int).tolist()))


class Struct:
    """仓库的几何：大厅（大块垒石的后墙 + 剖面 + 右半石板屋顶）、内间（凿在一整块巨石里，屋角塌口在两者之间）。"""

    def __init__(self):
        rng = np.random.default_rng(71)
        self.rng = rng
        h, w = H, W
        self.back = np.zeros((h, w), bool)      # 大厅后墙
        self.sect = np.zeros((h, w), bool)      # 剖面：左墙、隔墙、屋顶
        self.floor = np.zeros((h, w), bool)
        self.rock = np.zeros((h, w), bool)      # 巨石（整块）
        self.cave = np.zeros((h, w), bool)      # 巨石里凿出来的内间（后面那面石壁）
        self.holes = np.zeros((h, w), bool)     # 透出水底的洞（窗、圆窗）

        def back_top(x):
            if x < 935:
                if x < 760:
                    return 122 + (x - 714) * 0.6
                if x < 862:
                    return 150 + 9 * math.sin((x - 760) / 102 * math.pi)
                return 150 - (x - 862) * 0.68
            if x < ROOF_A[1]:
                return 96
            u = (x - ROOF_A[1]) / (ROCK[0] + 30 - ROOF_A[1])
            return 104 + 58 * math.sin(math.pi * min(1.0, 0.25 + 0.75 * u)) ** 0.7
        self.btop = {x: int(round(back_top(x))) for x in range(BACK[0], ROCK[0] + 30)}
        for x, t in self.btop.items():
            self.back[t:G, x] = True
        wx0, wx1, wy0, wy1 = WIN
        for x in range(wx0, wx1):
            u = (x + 0.5 - (wx0 + wx1) / 2) / ((wx1 - wx0) / 2)
            top = wy0 + int(round(9 * (1 - math.sqrt(max(0, 1 - u * u)))))
            self.holes[top:wy1, x] = True
        # 左墙
        for x in range(LW[0], LW[1]):
            t = 114 + (x - LW[0]) // 3 + int(rng.integers(0, 2))
            self.sect[t:G, x] = True
        self.sect[DOOR_TOP:G, LW[0]:LW[1]] = False
        # 隔墙（上到屋顶）
        self.sect[ROOF_Y[1]:G, PART[0]:PART[1]] = True
        self.sect[DOOR_TOP:G, PART[0]:PART[1]] = False
        # 屋顶（左端断成一截截往下垂；右端在塌口那里参差地断）
        for x in range(ROOF_A[0] - 8, ROOF_A[1] + 3):
            y0, y1 = ROOF_Y
            if x < ROOF_A[0] + 10:
                d = ROOF_A[0] + 10 - x
                y0 += d // 2 + (d % 3 == 0)
                y1 += min(4, d // 4)
            if x > ROOF_A[1] - 6:
                y0 += (x - (ROOF_A[1] - 6)) // 2
            if y1 - y0 >= 3:
                self.sect[y0:y1, x] = True
        # 巨石：左边从屋角塌口那里斜着升上去，顶是压扁的圆拱，右边出房间
        x0 = ROCK[0]
        nz = np.zeros(W)
        for k in range(1, 4):
            nz += rng.uniform(0.5, 1.0) / k * np.sin(np.arange(W) / (14 * k) + rng.uniform(0, 6))
        for x in range(x0, W):
            u = (x - x0) / 150.0
            top = 48 + 104 * (1 - min(1.0, u) ** 0.55) + 2.5 * nz[x]
            self.rock[int(round(top)):G, x] = True
        # 内间（凿出来的）：平地、直壁、拱顶
        cx0, cx1 = CAVE
        for x in range(cx0, cx1):
            u = (x + 0.5 - (cx0 + cx1) / 2) / ((cx1 - cx0) / 2)
            top = 102 + int(round(20 * abs(u) ** 3.2))
            self.cave[top:G, x] = True
        self.cave &= self.rock
        # 圆窗（凿穿后壁，透出水底）
        px, py, pr = PORT
        yy, xx = np.mgrid[0:h, 0:w]
        self.holes |= ((xx - px) ** 2 + (yy - py) ** 2 * 1.1) < pr * pr
        self.floor[G:G + 8, OPEN:W] = True
        # 月光从右上来，被屋顶 / 墙 / 巨石挡掉多少
        occ = self.sect | (self.rock & ~self.cave)
        occ[:, :BACK[0]] = False
        lit = np.zeros((h, w))
        slopes = (0.25, 0.4, 0.55, 0.7, 0.9)
        for s in slopes:
            blk = np.zeros((h, w), bool)
            acc = 0.0
            for y in range(1, h):
                acc += s
                sh = int(acc)
                acc -= sh
                prev = blk[y - 1]
                if sh:
                    prev = np.concatenate([prev[sh:], np.zeros(sh, bool)])
                blk[y] = prev | occ[y]
            lit += ~blk
        lit /= len(slopes)
        lit = np.clip(ua.blur(lit, 3.0), 0, 1)
        # 圆窗 / 窗洞漏进来一小团光（落在下面的墙和地上）
        for (lx, ly, r, k) in ((WIN[0] + 4, WIN[3] + 24, 18, 0.3),):
            lit += k * np.exp(-(((xx - lx) / r) ** 2 + ((yy - ly) / (r * 1.6)) ** 2))
        # 圆窗：一道月光斜着穿进来（往左下），落在设备柜旁边的地上
        dx_, dy_ = -0.55, 1.0
        nn = math.hypot(dx_, dy_)
        dx_, dy_ = dx_ / nn, dy_ / nn
        rx, ry = xx - PORT[0], yy - PORT[1]
        along = rx * dx_ + ry * dy_
        perp = rx * dy_ - ry * dx_
        beam = np.exp(-(perp / (PORT[2] * 0.8)) ** 2) * (along > -PORT[2]) * np.exp(-np.clip(along, 0, None) / 160)
        lit += 0.75 * beam * self.cave
        self.light = np.clip(lit, 0, 1)
        # 暗部（AO）+ 深度：越深越暗（暗档本来就偏靛，所以也越蓝）；墙脚、屋顶底下、贴着剖面墙的那几格、拱顶下暗
        Y = np.arange(h)[:, None] * np.ones((1, w))
        ao = -0.1 * np.clip((Y - 90) / 140, 0, 1)
        ao -= 0.16 * np.exp(-np.clip(G - 1 - Y, 0, None) / 4.0) * (Y < G)
        ao[:, ROOF_A[0]:ROOF_A[1]] -= (0.08 * np.exp(-np.clip(Y - ROOF_Y[1], 0, None) / 6.0) * (Y >= ROOF_Y[1]))[:, ROOF_A[0]:ROOF_A[1]]
        prev = self.sect | (self.rock & ~self.cave)
        for k in range(1, 6):
            dil = prev.copy()
            dil[:, 1:] |= prev[:, :-1]
            dil[:, :-1] |= prev[:, 1:]
            dil[1:, :] |= prev[:-1, :]
            ring = dil & ~prev
            ao[ring] -= 0.12 * math.exp(-k / 2.5)
            prev = dil
        self.ao = ao


# ====================================================================== 石头
def voronoi_stones(mask, rng, cw=26.0, ch=15.0, p=2.6, row_jit=0.2, keep=None):
    """把 mask 切成一块块不规则的垒石（按层排的种子 + 抖动，p 范数 Voronoi：p 大 = 方一点）。
    返回 (id 图 -1=外面, 到边的距离)。keep(seed_x, seed_y) = False 的石块整块扔掉（塌口顺着石块的边断，不是一刀切）。"""
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return np.full(mask.shape, -1), np.zeros(mask.shape)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    seeds = []
    y = y1 + ch * 0.5
    r = 0
    while y > y0 - ch:
        rh = ch * rng.uniform(0.8, 1.25)
        x = x0 - cw * rng.uniform(0.2, 1.0)
        while x < x1 + cw:
            sw = cw * rng.uniform(0.65, 1.45)
            seeds.append((x + sw / 2 + rng.uniform(-0.12, 0.12) * sw, y - rh / 2 + rng.uniform(-row_jit, row_jit) * rh,
                          sw / cw, rh / ch))
            x += sw
        y -= rh
        r += 1
    hh, ww = y1 - y0, x1 - x0
    Y, X = np.mgrid[y0:y1, x0:x1].astype(float)
    d1 = np.full((hh, ww), 1e9)
    d2 = np.full((hh, ww), 1e9)
    idm = np.full((hh, ww), -1)
    for i, (sx, sy, sxs, sys_) in enumerate(seeds):
        if abs(sy - (y0 + y1) / 2) > hh / 2 + ch * 2:
            continue
        d = ((np.abs(X - sx) / (cw * sxs)) ** p + (np.abs(Y - sy) / (ch * sys_)) ** p) ** (1 / p)
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        idm = np.where(closer, i, idm)
        d1 = np.where(closer, d, d1)
    edge = (d2 - d1) * min(cw, ch) * 0.5
    ids = np.full(mask.shape, -1)
    eg = np.zeros(mask.shape)
    sub = mask[y0:y1, x0:x1]
    idm = np.where(sub, idm, -1)
    if keep is not None:
        for i, (sx, sy, _, _) in enumerate(seeds):
            if not keep(sx, sy):
                idm[idm == i] = -1
    ids[y0:y1, x0:x1] = idm
    eg[y0:y1, x0:x1] = edge
    return ids, eg


# ---------------------------------------------------------------- 石头的材质（作者 10-30 夜：「石头还是缺乏质感」）
# 标准（fb1030/石头质感要求.md，水下版）：岩层统一横向（每块石头是从不同的岩层里凿出来的，层距、偏移各不一样）；
# 表面是 2~3 色的小色团（平滑小噪声取阈值，再去掉孤立的单像素），不用棋盘格抖动；大面上明暗、冷暖缓慢地变；
# 光从水面往下（右上来）：越深越暗越蓝（暗档色相偏靛、亮档偏青灰）；朝右的边一道冷亮边、朝上的面落一层淤泥；
# 墙脚、屋顶下、墙角有暗部（AO）；缝里长藻、背光的下沿挂一点附着物，裂缝少而准（粗细不一、分叉）。
def stone_pal(n=9, L0=.038, L1=.335, h_dark=266, h_lit=236, C0=.018, C1=.032):
    """9 档 × 3 种冷暖（偏青 / 中 / 偏靛紫），暗档偏靛、亮档偏蓝灰（和原来水底的石头人头一族，不偏绿）。"""
    out = []
    for i in range(n):
        t = i / (n - 1)
        L = L0 + (L1 - L0) * t
        h = h_dark + (h_lit - h_dark) * t ** 0.8
        C = C0 + (C1 - C0) * t
        out.append([oc(L, C + .004, h - 7), oc(L, C, h), oc(L, C - .003, h + 9)])
    return out


SP = stone_pal()
SILT = [oc(.15, .008, 236), oc(.2, .008, 226), oc(.25, .009, 214), oc(.29, .009, 200)]   # 淤泥：冷灰（不黄）
BARN = [oc(.12, .012, 250), oc(.27, .012, 215), oc(.36, .012, 205)]                    # 附着的小藤壶
AO = None                                   # build_main 里设成 st.ao（每个像素往暗推多少）
DUMP = None                                 # 调试：局部图存这里
ENV = None                                  # 物件打光用的场景光照（st.light 模糊过；main() 里设）


def env_for(ox, oy, w, h, lo=0.3):
    """物件画布那块的场景光照（lo..1：最暗的地方也留一点，要点的东西在暗处也读得出）。"""
    e = np.full((h, w), 0.5)
    if ENV is not None:
        y0, x0 = max(0, oy), max(0, ox)
        y1, x1 = min(H, oy + h), min(W, ox + w)
        if y1 > y0 and x1 > x0:
            e[y0 - oy:y1 - oy, x0 - ox:x1 - ox] = ENV[y0:y1, x0:x1]
    return lo + (1 - lo) * np.clip(e, 0, 1)


def set_env(st):
    global ENV
    ENV = np.clip(ua.blur(st.light, 6.0) * 1.15, 0, 1)


def despeckle(lev, M):
    """去掉孤立的单像素：8 邻里没有一个同档的，改成邻居的中位数（色团至少两三格，不是噪点）。"""
    p = np.pad(lev, 1, mode="edge")
    nb = np.stack([p[1 + dy:p.shape[0] - 1 + dy, 1 + dx:p.shape[1] - 1 + dx]
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx])
    same = (nb == lev[None]).sum(0)
    med = np.median(nb, axis=0).round().astype(int)
    out = lev.copy()
    fix = M & (same == 0)
    out[fix] = med[fix]
    return out


def material(V, M, L, rng, oy, ox, ids=None, per=(4, 8), strata=0.07, cluster=0.075, warp=None, n=len(SP)):
    """V（连续的明暗，0..1）→ 档位：加大面的慢变化、横向岩层（断断续续，层线下沿暗、上面一行受光）、小色团，去孤点。"""
    hh, ww = M.shape
    Y = np.arange(hh)[:, None] + oy
    X = np.arange(ww)[None, :] + ox
    V = V + 0.08 * (ua.vnoise(hh, ww, 30, 46, rng) - 0.5)
    wp = ua.vnoise(hh, ww, 18, 40, rng) * 3.5 + ua.vnoise(hh, ww, 4, 10, rng) * 1.2
    if warp is not None:
        wp = wp + warp
    if ids is not None:
        uid = np.unique(ids[ids >= 0])
        offm = np.zeros(int(ids.max()) + 2)
        perm = np.full(int(ids.max()) + 2, float(np.mean(per)))
        for i in uid:
            offm[i] = rng.uniform(0, 12)
            perm[i] = rng.uniform(*per)
        off = offm[np.clip(ids, 0, None)]
        pr = perm[np.clip(ids, 0, None)]
    else:
        off, pr = 0.0, float(np.mean(per))
    s = (Y + wp + off) / pr
    fr = s - np.floor(s)
    line = (fr < 1.0 / pr) & (ua.vnoise(hh, ww, 3, 9, rng) > 0.4) & M
    lip = np.zeros_like(line)
    lip[:-1] = line[1:]
    lip &= M & ~line
    V = V - strata * line + 0.6 * strata * lip * (L > 0.3)
    cn = ua.vnoise(hh, ww, 2.2, 3.1, rng) - 0.5
    V = V + cluster * 1.6 * cn                       # 半档左右的小噪声：只把色阶交界抖成一团团的，大面不动
    lev = np.clip(np.floor(V * (n - 1) + 0.5), 0, n - 1).astype(int)
    lev = despeckle(lev, M)
    tb = ua.vnoise(hh, ww, 26, 40, rng)
    tbin = np.where(tb < 0.38, 0, np.where(tb > 0.63, 2, 1))
    return lev, tbin


def paint(out, M, lev, tbin, pal=SP):
    for k in range(len(pal)):
        for b in range(3):
            mm = M & (lev == k) & (tbin == b)
            if mm.any():
                out[mm] = rgba(pal[k][b])


def crack(lev, M, rng, x, y, ln, width=2, depth=0):
    """一条裂缝：往下爬、左右摆，起头粗（2 格）后面细，半路可能分一个叉；芯最暗，右唇亮一档。"""
    h, w = lev.shape
    n = len(SP)
    fx, fy = float(x), float(y)
    for s in range(int(ln)):
        wd = width if s < ln * 0.45 else 1
        xi, yi = int(round(fx)), int(round(fy))
        for k in range(wd):
            X = xi + k
            if 0 <= yi < h and 0 <= X < w and M[yi, X]:
                lev[yi, X] = 0
        X = xi + wd
        if 0 <= yi < h and 0 <= X < w and M[yi, X] and lev[yi, X] > 0:
            lev[yi, X] = min(n - 1, lev[yi, X] + 1)
        fx += rng.choice([-1, 0, 0, 0, 1]) * 0.9 + 0.15
        fy += 1
        if depth == 0 and abs(s - ln * 0.5) < 0.5 and rng.random() < 0.7:
            crack(lev, M, rng, fx, fy, ln * 0.4, 1, depth=1)


def stone_shade(img, ids, edge, pal, light, rng, ambient=0.06, gain=0.62, tone=0.05, R=3.2, seam=0.9,
                moss=0.0, lit_floor=0.0, wear=True, cracks=(), per=(4, 8)):
    """垒石，一块一块手绘式地画（不是噪声）：
    - 底色 = 这块石头里的平均光照 × gain + 环境 + 这块自己深一点浅一点（冷暖也按块定，跟着大面的慢噪声走，所以相邻的块相近）；
    - 面：右上一块亮一档、左下一角暗一档，交界用小色团抖成锯齿（色团只在交界）；光照的边从块上横穿过去的地方再差一档；
    - 边：顶上 1~2 格受光带（朝上的面）、右沿一格亮、左沿 / 下沿一格暗；
    - 少量：崩口（缺一角，下沿一格亮）、坑点（暗一格、右下一格亮）、一两条横的岩层线（断续）、下半截块角里的藻；
    - 缝：一两格宽不等，最暗，缝里长藻。cracks = [(x, y, 长)] 房间坐标。"""
    n = len(SP)
    m = ids >= 0
    if not m.any():
        return
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    I = ids[y0:y1, x0:x1]
    E = edge[y0:y1, x0:x1]
    M = I >= 0
    L = np.maximum(light[y0:y1, x0:x1], lit_floor)
    A = AO[y0:y1, x0:x1] if AO is not None else np.zeros_like(L)
    hh, ww = I.shape
    sm = M & (E < seam * (0.65 + 0.7 * ua.vnoise(hh, ww, 5, 9, rng)))
    face = M & ~sm
    cn = ua.vnoise(hh, ww, 2.0, 2.6, rng) - 0.5               # 交界处的小色团
    slow = ua.vnoise(hh, ww, 26, 40, rng)
    lev = np.zeros((hh, ww), int)
    tb = np.ones((hh, ww), int)
    step = 1.0 / (n - 1)
    for k in np.unique(I[face]):
        bm = (I == k) & face
        yy, xx = np.nonzero(bm)
        by0, by1, bx0, bx1 = yy.min(), yy.max() + 1, xx.min(), xx.max() + 1
        sub = bm[by0:by1, bx0:bx1]
        bh, bw = sub.shape
        Ls = L[by0:by1, bx0:bx1]
        Lm = float(Ls[sub].mean())
        base = ambient + gain * Lm * 0.95 + rng.uniform(-tone, tone) + float(A[by0:by1, bx0:bx1][sub].mean())
        u = (np.arange(bw)[None, :] + 0.5) / bw
        v = (np.arange(bh)[:, None] + 0.5) / bh
        diag = (u - v) + 0.5 * cn[by0:by1, bx0:bx1]
        V = base + step * ((diag > 0.18) * 1.0 - (diag < -0.5) * 1.0)
        V = V + gain * 0.8 * (Ls - Lm) + (A[by0:by1, bx0:bx1] - float(A[by0:by1, bx0:bx1][sub].mean()))
        # 边
        def sh(a, dy, dx):
            o = np.zeros_like(a)
            hs, ws = a.shape
            if abs(dy) >= hs or abs(dx) >= ws:
                return o
            o[max(0, dy):hs + min(0, dy), max(0, dx):ws + min(0, dx)] = \
                a[max(0, -dy):hs + min(0, -dy), max(0, -dx):ws + min(0, -dx)]
            return o
        up1 = sub & ~sh(sub, 1, 0)
        up2 = sub & ~up1 & ~sh(sub, 2, 0)
        rt = sub & ~sh(sub, 0, -1)
        lf = sub & ~sh(sub, 0, 1)
        dn = sub & ~sh(sub, -1, 0)
        lit = 0.4 + 0.6 * Ls
        V = V + up1 * step * 2.0 * lit + up2 * step * 0.9 * lit + rt * step * lit - lf * step * 0.7 - dn * step
        lv = np.clip(np.floor(V / step + 0.5), 0, n - 1).astype(int)
        # 崩口 / 坑点 / 岩层线 / 藻（少）
        if wear and bw > 7 and bh > 5:
            for _ in range(int(rng.integers(0, 3))):          # 崩口：顶边或左边缺一小块
                if rng.random() < 0.6:
                    cx = int(rng.integers(1, bw - 3))
                    w_ = int(rng.integers(2, 4))
                    d_ = int(rng.integers(1, 3))
                    rows = np.nonzero(sub[:, cx])[0]
                    if len(rows):
                        r0 = rows[0]
                        lv[r0:r0 + d_, cx:cx + w_] = 0
                        lv[r0 + d_:r0 + d_ + 1, cx:cx + w_] = np.minimum(n - 1, lv[r0 + d_:r0 + d_ + 1, cx:cx + w_] + 1)
            for _ in range(int(rng.integers(0, 3))):          # 坑点
                py_, px_ = int(rng.integers(2, bh - 2)), int(rng.integers(2, bw - 2))
                if sub[py_, px_] and sub[py_ + 1, px_ + 1]:
                    lv[py_, px_] = max(0, lv[py_, px_] - 2)
                    if rng.random() < 0.5 and sub[py_, px_ + 1]:
                        lv[py_, px_ + 1] = max(0, lv[py_, px_ + 1] - 2)
                    lv[py_ + 1, px_ + 1] = min(n - 1, lv[py_ + 1, px_ + 1] + 1)
            if bh > 8 and rng.random() < 0.55:                 # 岩层线：横的、断续、微微起伏
                for _ in range(int(rng.integers(1, 3))):
                    ry = int(rng.integers(3, bh - 3))
                    sx0 = int(rng.integers(0, max(1, bw // 3)))
                    ln = int(bw * rng.uniform(0.35, 0.8))
                    ph = rng.uniform(0, 6)
                    for j in range(ln):
                        X = sx0 + j
                        Y = ry + int(round(0.8 * math.sin(j / 5.0 + ph)))
                        if 0 <= Y < bh - 1 and X < bw and sub[Y, X] and (j % 9) != 7:
                            lv[Y, X] = max(0, lv[Y, X] - 1)
                            if Y + 1 < bh and sub[Y + 1, X] and Ls[Y + 1, X] > 0.3:
                                lv[Y + 1, X] = min(n - 1, lv[Y + 1, X] + 1)
        reg = lev[by0:by1, bx0:bx1]
        reg[sub] = lv[sub]
        cy_, cx_ = (by0 + by1) // 2, (bx0 + bx1) // 2
        t_ = slow[cy_, cx_] + rng.uniform(-0.08, 0.08)
        tb[by0:by1, bx0:bx1][sub] = 0 if t_ < 0.4 else (2 if t_ > 0.62 else 1)
    lev[sm] = np.where(L[sm] > 0.55, 1, 0)
    for (cx, cy, ln) in cracks:
        if x0 <= cx < x1 and y0 <= cy < y1:
            crack(lev, M, rng, cx - x0, cy - y0, ln)
    out = img.a[y0:y1, x0:x1]
    paint(out, M, lev, tb)
    # 缝里的藻、块的左下角里一簇藻（下半截多）
    r = rng.random((hh, ww))
    Yg = np.arange(hh)[:, None] + y0
    deep = np.clip((Yg - 130) / 80.0, 0, 1)
    alg = sm & (r < moss * (0.3 + 0.7 * deep))
    out[alg] = rgba(MOSS[0])
    out[alg & (L > 0.45) & (r < moss * 0.25)] = rgba(MOSS[1])
    return lev


def rock_shade(img, mask, pal, light, rng, amp=26.0, blur_r=10.0, ambient=0.05, gain=0.7, cracks=(), dith=0.0,
               per=(5, 7), strata=0.085):
    """一整块巨石：高度场 = 模糊过的形 × amp + 低频起伏，按月光打光；岩层顺着石头的鼓包微微弯（warp 跟高度场走）。"""
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = max(0, ys.min() - 2), ys.max() + 1, max(0, xs.min() - 2), xs.max() + 1
    M = mask[y0:y1, x0:x1]
    hh, ww = M.shape
    big = ua.blur(M.astype(float), blur_r)
    hf = big * amp + ua.vnoise(hh, ww, 26, 36, rng) * amp * 0.12 + ua.vnoise(hh, ww, 5, 7, rng) * 1.0
    gy_, gx_ = np.gradient(hf)
    nrm = np.stack([-gx_, -gy_, np.ones_like(hf)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    lam = np.clip((nrm * ua.LIGHT).sum(-1), 0, 1)
    L = light[y0:y1, x0:x1]
    V = ambient + gain * (0.3 + 0.7 * L) * (lam - 0.05)
    if AO is not None:
        V = V + AO[y0:y1, x0:x1]
    lev, tbin = material(V, M, L, rng, y0, x0, per=per, strata=strata, warp=-big * 9)
    for (cx, cy, ln) in cracks:
        if x0 <= cx < x1 and y0 <= cy < y1:
            crack(lev, M, rng, cx - x0, cy - y0, ln)
    out = img.a[y0:y1, x0:x1]
    paint(out, M, lev, tbin)
    return lev, (y0, x0)


def weathering(img, st, solid):
    """整体的最后一道：朝右的边一道冷亮边（月光 rim）、朝上的面落淤泥、下半截背光处几簇藤壶 / 藻，
    屋顶断口、窗洞、巨石檐下挂几缕水草。"""
    a = img.a
    rng = np.random.default_rng(141)
    L = st.light
    h, w = solid.shape
    right = solid & ~np.roll(solid, -1, 1)
    right[:, -1] = False
    top = solid & ~np.roll(solid, 1, 0)
    top[0] = False
    for y, x in zip(*np.nonzero(right)):
        lv = L[y, x]
        if lv > 0.3 and y < G - 2:
            a[y, x] = rgba(SP[7 if lv > 0.65 else 6][0])
            if solid[y, x - 1] and lv > 0.55:
                a[y, x - 1] = rgba(SP[5][0])
    run = ua.vnoise(4, w, 4, 5, rng)[1]                  # 沿 x 的平滑噪声：淤泥一段一段的（2~8 格），不连成线
    heap = ua.vnoise(4, w, 4, 3, rng)[2]
    for y, x in zip(*np.nonzero(top)):
        lv = L[y, x]
        if lv > 0.3 and run[x] > 0.42:
            k = min(3, int(lv * 3.4))
            a[y, x] = rgba(SILT[k])
            if heap[x] > 0.66 and solid[y + 1, x]:
                a[y + 1, x] = rgba(SILT[max(0, k - 1)])
    # 藤壶：两三格一簇（亮点 + 左下一格暗），只在下半截、不太暗的面上，稀
    ys, xs = np.nonzero(solid & (np.arange(h)[:, None] > 150))
    for _ in range(int(len(ys) / 520)):
        i = int(rng.integers(0, len(ys)))
        y, x = ys[i], xs[i]
        if not (solid[y - 1:y + 2, x - 1:x + 3].all()):
            continue
        k = int(rng.integers(1, 4))
        for j in range(k):
            X = x + j * 2 - (j == 2) * 3
            Y = y - (j == 1)
            a[Y, X] = rgba(BARN[2 if L[Y, X] > 0.4 else 1])
            a[Y + 1, X - 1] = rgba(BARN[0])


def hang_strands(img, pts, rng, solid=None):
    """挂下来的几缕水草 / 根须：一格宽，弯弯地往下垂（水流往左），越往下越细越暗，尖上一格亮。"""
    pal = [MOSS[0], oc(.12, .026, 214), MOSS[1], MOSS[2]]
    for (x, y, ln) in pts:
        fx = float(x)
        ph = rng.uniform(0, 6)
        for s in range(int(ln)):
            f = s / ln
            X = int(round(fx + 1.6 * math.sin(s * 0.35 + ph) * f - 2.5 * f * f))
            c = pal[2] if s < 2 else (pal[1] if f < 0.7 else pal[0])
            if s == int(ln) - 1:
                c = pal[3]
            img.put(X, y + s, c)
            if s < ln * 0.3:
                img.put(X + 1, y + s, pal[1])


# ====================================================================== 主层
def seabed():
    """原来的河床（main.png 横着铺），仓库那一段之后再画盖掉。"""
    return tile_from(UW / "main.png", W)


def build_main(st: Struct):
    img = Img(W, H)
    img.a[:] = seabed()
    rng = np.random.default_rng(5)
    # 仓库那一段先把原来河床上的东西抹成干净的泥，地板压上去
    mud = ua.bramp(4, .055, .1, 262, 256)
    for x in range(OPEN - 6, W):
        col = img.a[:, x]
        col[:G] = 0
        for y in range(G, H):
            d = y - G
            f = min(1.0, max(0, d - 8) / 22)
            col[y] = rgba(mud[int(np.clip(round(3 - 3.2 * f + (rng.random() - 0.5) * 0.8), 0, 3))])
    approach_ruins(img, st)
    global AO
    AO = st.ao
    light = st.light
    # 巨石（外面受月光，越往下越暗）+ 凿出来的内间
    yy = np.arange(H)[:, None] * np.ones((1, W))
    Lr = np.clip(1.15 - (yy - 50) / 210.0, 0.25, 1.0)
    rock_shade(img, st.rock, ROCKP, Lr, np.random.default_rng(21), amp=80, blur_r=26, ambient=0.1, gain=0.78,
               cracks=[(1300, 84, 26), (1232, 66, 18), (1338, 120, 30)])
    cave_interior(img, st)
    rock_details(img, st)
    # 大厅后墙：垒起来的大块石头，塌口顺着石块断
    ext = st.back.copy()
    for x, t in st.btop.items():
        if t > 98:
            ext[max(0, t - 12):t, x] = True
    keep = lambda sx, sy: sy >= st.btop.get(int(np.clip(round(sx), BACK[0], ROCK[0] + 29)), 96) - 3
    ids, eg = voronoi_stones(ext & ~st.holes, np.random.default_rng(11), cw=27, ch=16, keep=keep)
    ids[st.rock & ~st.cave] = -1
    ids[st.cave] = -1
    stone_shade(img, ids, eg, STONE, light * 0.85, np.random.default_rng(12), ambient=0.28, gain=0.44, moss=0.35,
                cracks=[(788, 160, 30), (906, 128, 40), (1010, 98, 22), (1118, 150, 26)])
    st.back_ids = ids
    breach_edges(img, st, ids)
    # 剖面（左墙、隔墙：小一点的方石；屋顶：长石板）
    wall = st.sect.copy()
    wall[:ROOF_Y[1] + 1, :] &= False
    wall[:, LW[0]:LW[1]] = st.sect[:, LW[0]:LW[1]]
    ids, eg = voronoi_stones(wall, np.random.default_rng(13), cw=11, ch=9, p=3.0)
    stone_shade(img, ids, eg, SECT, np.maximum(light, 0.3), np.random.default_rng(14), ambient=0.12, gain=0.55,
                moss=0.4, R=2.4, seam=0.8, per=(3, 5))
    roof = st.sect.copy()
    roof[ROOF_Y[1] + 5:, :] = False
    roof[:, LW[0]:LW[1]] = False
    ids, eg = voronoi_stones(roof, np.random.default_rng(15), cw=38, ch=7, p=3.2, row_jit=0.05)
    stone_shade(img, ids, eg, SECT, np.maximum(light, 0.45), np.random.default_rng(16), ambient=0.12, gain=0.55,
                moss=0.5, R=2.6, seam=0.8, per=(3, 4), cracks=[(948, 83, 9), (1070, 83, 8)])
    roof_top(img, st)
    lintels(img, st)
    floor(img, st)
    rope_and_hooks(img, st)
    sluice_recess(img, st)
    solid = ((st.back_ids >= 0) | st.sect | st.rock) & ~st.holes
    solid[:, :LW[0]] = False
    weathering(img, st, solid)
    hang_strands(img, [(ROOF_A[0] - 4, ROOF_Y[1] + 3, 14), (ROOF_A[0] + 3, ROOF_Y[1], 9), (ROOF_A[1] - 2, ROOF_Y[1] + 1, 17),
                       (WIN[0] + 5, WIN[2] + 3, 8), (WIN[0] + 19, WIN[2] + 1, 12), (ROCK[0] + 6, 150, 13),
                       (ROCK[0] + 16, 128, 9), (PORT[0] - 3, PORT[1] - PORT[2] + 1, 7)], np.random.default_rng(151))
    boxes(img, st)
    low_cabinet(img, st)
    hanging(img, st)
    equip_cabinet(img, st)
    post_and_stakes(img)
    return img


def rock_details(img, st):
    """巨石外面凿的东西：上面一扇小方窗（凿进去的暗洞，下唇受光、左内壁暗），一道凿出来的窄台阶顺着石头往上（没人走了）。"""
    a = img.a
    # 小窗
    x0, y0, w_, h_ = 1296, 72, 8, 11
    for y in range(y0, y0 + h_):
        for x in range(x0, x0 + w_):
            a[y, x] = rgba(STONE[0] if x > x0 + 1 else STONE[1])
    for x in range(x0 - 1, x0 + w_ + 1):
        a[y0 + h_, x] = rgba(ROCKP[6])
        a[y0 - 1, x] = rgba(ROCKP[1])
    for y in range(y0, y0 + h_):
        a[y, x0 + w_] = rgba(ROCKP[5])
    # 台阶：从洞口上方顺着巨石左坡一级一级往上，每级 5 宽 2 高，踏面受光
    ys = [int(np.nonzero(st.rock[:, x])[0][0]) for x in range(ROCK[0], ROCK[0] + 60)]
    for i in range(6):
        x = ROCK[0] + 14 + i * 7
        t = ys[x - ROCK[0]]
        for k in range(5):
            if st.rock[t + 1, x + k]:
                a[t + 1, x + k] = rgba(ROCKP[6])
                a[t + 2, x + k] = rgba(ROCKP[3])
        a[t + 2, x] = rgba(ROCKP[1])


def cave_interior(img, st):
    """巨石里凿出来的内间：后壁是凿平的石面（很暗，一道道横的凿痕、不连贯），切开的那一圈石头（墙厚）是一条平的、
    比外面亮一点的边，拱顶那段边最厚。圆窗凿穿后壁（透明），窗下一小块被漏进来的光照亮。"""
    rng = np.random.default_rng(23)
    m = st.cave & ~st.holes
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    M = m[y0:y1, x0:x1]
    L = st.light[y0:y1, x0:x1]
    hh, ww = M.shape
    # 凿平的面：大面几乎是平的（一点点凹凸），亮度 = 环境 + 圆窗那道光；凿痕 = 很密的横向「岩层」（层距 5~7，断断续续）
    V = 0.31 + 0.72 * L + 0.04 * (ua.vnoise(hh, ww, 12, 16, rng) - 0.5) + 0.6 * AO[y0:y1, x0:x1]
    lev, tbin = material(V, M, L, rng, y0, x0, per=(6, 8), strata=0.08, cluster=0.05)
    for (cx, cy, ln) in ((1176, 112, 24), (1286, 104, 12)):
        crack(lev, M, rng, cx - x0, cy - y0, ln)
    paint(img.a[y0:y1, x0:x1], M, lev, tbin)
    a = img.a
    # 切开的那一圈（墙厚）：围着内间外沿 3 格，平的面，上沿 / 右边亮一点
    ring = np.zeros_like(m)
    cv = st.cave
    for d in (1, 2, 3):
        sh = np.zeros_like(cv)
        sh[:-d, :] |= cv[d:, :]
        sh[:, d:] |= cv[:, :-d]
        sh[:, :-d] |= cv[:, d:]
        ring |= sh
    ring &= st.rock & ~cv
    ry, rx = np.nonzero(ring)
    for y, x in zip(ry, rx):
        lv = 3
        if not cv[min(H - 1, y + 1), x] and not cv[y, max(0, x - 1)] and cv[y, min(W - 1, x + 3)]:
            lv = 2                                       # 左边那条（朝右，背着月光的那面）
        if cv[min(H - 1, y + 3), x] and not cv[min(H - 1, y + 1), x]:
            lv = 4                                       # 拱顶那段：上面受光
        a[y, x] = rgba(SECT[min(7, lv + 2)])
    # 洞里贴着那一圈的 3 格：暗一档（墙厚挡掉的光）
    inner = np.zeros_like(m)
    for d in (1, 2, 3):
        sh = np.zeros_like(cv)
        sh[d:, :] |= ~cv[:-d, :]
        sh[:, :-d] |= ~cv[:, d:]
        inner |= sh
    inner &= m
    for y, x in zip(*np.nonzero(inner)):
        c = a[y, x, :3].astype(int)
        a[y, x, :3] = np.maximum(c - 7, 0)
    # 圆窗：凿穿的厚度
    port = st.holes.copy()
    port[:, :ROCK[0]] = False
    reveal(img, port, np.random.default_rng(171), np.maximum(st.light, 0.6), top_d=2, left_d=2, sill_d=2)


def approach_ruins(img, st):
    """仓库外面那一小段（590..697）：一截横躺的石柱段、两块掉下来的方石，半埋。原来河床 560 那截石柱段保留。"""
    pal = ua.bramp(6, .055, .28, 262, 246)
    # 横躺的柱段：圆柱（上亮下暗），两头断面
    x0, w_, r = 612, 30, 6
    for x in range(x0, x0 + w_):
        g = int(round(gy_out(x)))
        for k in range(2 * r):
            y = g + 2 - 2 * r + k
            u = k / (2 * r - 1)
            lv = 4 if u < 0.18 else (3 if u < 0.38 else (2 if u < 0.62 else 1))
            if (x - x0) % 7 == 3 and 0.15 < u < 0.85:
                lv -= 1                                  # 柱身的竖槽
            if x == x0 + w_ - 1:
                lv = min(5, lv + 1)                      # 断面朝右，受光
            if x == x0:
                lv = max(0, lv - 1)
            img.put(x, y, pal[lv])
    # 两块方石（棱角磨圆，斜着半埋）
    for bx, bw_, bh, tilt in ((650, 13, 8, 1), (668, 16, 10, -1), (684, 9, 6, 0)):
        g = int(round(gy_out(bx + bw_ // 2)))
        for j in range(bw_):
            top = g + 2 - bh + (tilt * j) // 6
            for y in range(top, g + 3):
                k = y - top
                lv = 4 if k == 0 else (3 if k < 3 else 2)
                if j == bw_ - 1:
                    lv = min(5, lv + 1)
                if j == 0:
                    lv = max(1, lv - 1)
                if (j in (0, bw_ - 1)) and k == 0:
                    continue
                img.put(bx + j, y, pal[lv])
        # 顶上一点苔
        for j in range(2, bw_ - 2, 3):
            img.put(bx + j, g + 2 - bh + (tilt * j) // 6, MOSS[1 + (j % 2)])


def reveal(img, hole, rng, light, top_d=2, left_d=2, sill_d=2):
    """凿出来的洞的厚度（画在洞的边里，中间照样透明）：上沿 = 过梁的底面，最暗两格；下沿 = 窗台 / 洞底的顶面，受光两格、
    落一点淤泥；左内壁朝右、迎着月光，亮两格（外亮里暗）；右内壁背光一格暗。洞口外沿几处磨损的小缺口。"""
    a = img.a
    h, w = hole.shape
    ys, xs = np.nonzero(hole)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1

    def run(dy, dx):
        """每个洞里的像素：往 (dy, dx) 方向数几格才碰到墙"""
        d = np.zeros((h, w), int)
        rng_y = range(y0, y1) if dy >= 0 else range(y1 - 1, y0 - 1, -1)
        rng_x = range(x0, x1) if dx >= 0 else range(x1 - 1, x0 - 1, -1)
        if dy:
            for y in rng_y:
                prev = d[y - dy] if 0 <= y - dy < h else 0
                d[y] = np.where(hole[y], np.where(hole[y - dy] if 0 <= y - dy < h else False, prev + 1, 0), 0)
        else:
            for x in rng_x:
                prev = d[:, x - dx] if 0 <= x - dx < w else 0
                d[:, x] = np.where(hole[:, x], np.where(hole[:, x - dx] if 0 <= x - dx < w else False, prev + 1, 0), 0)
        return d
    dt, db, dl, dr = run(1, 0), run(-1, 0), run(0, 1), run(0, -1)
    L = light
    for y, x in zip(ys, xs):
        lv = L[y, x]
        if dt[y, x] < top_d:
            c = SP[0][1] if dt[y, x] == 0 else SP[1][2]
        elif db[y, x] < sill_d:
            k = 6 if db[y, x] == 0 else 4
            c = SP[k][0] if lv > 0.25 else SP[k - 2][1]
            if db[y, x] == 1 and rng.random() < 0.5:
                c = SILT[2]
        elif dl[y, x] < left_d:
            c = SP[5 if dl[y, x] == 0 else 3][0] if lv > 0.15 else SP[3 if dl[y, x] == 0 else 2][1]
        elif dr[y, x] < 1:
            c = SP[1][2]
        else:
            continue
        a[y, x] = rgba(c)
    # 外沿磨损：几处 1~2 格的小缺口（暗），缺口下面一格亮
    edge = np.zeros_like(hole)
    edge[1:-1, 1:-1] = (~hole[1:-1, 1:-1]) & (hole[:-2, 1:-1] | hole[2:, 1:-1] | hole[1:-1, :-2] | hole[1:-1, 2:])
    ey, ex = np.nonzero(edge)
    for _ in range(max(2, len(ey) // 14)):
        i = int(rng.integers(0, len(ey)))
        y, x = ey[i], ex[i]
        a[y, x] = rgba(SP[1][1])
        if rng.random() < 0.5:
            a[y, x + 1] = rgba(SP[1][1])
        if y + 1 < h and not hole[y + 1, x]:
            a[y + 1, x] = rgba(SP[4][0])


def breach_edges(img, st, ids):
    """大厅后墙的窗洞：凿出来的厚度（reveal），窗台多伸出来一点（两头各多一格的石唇）。"""
    wx0, wx1, wy0, wy1 = WIN
    win = st.holes.copy()
    win[:, :wx0 - 1] = False
    win[:, wx1 + 1:] = False
    reveal(img, win, np.random.default_rng(161), np.maximum(st.light, 0.6), top_d=2, left_d=3, sill_d=2)   # 洞的内壁吃的是从洞口进来的光
    for x in (wx0 - 2, wx0 - 1, wx1, wx1 + 1):
        img.a[wy1, x] = rgba(SP[5][0] if x > wx0 else SP[4][1])
        img.a[wy1 + 1, x] = rgba(SP[1][2])


def roof_top(img, st):
    """屋顶、左墙头、巨石顶上：朝上那一行受月光（有时是苔），偶尔一丛矮草；屋顶断口下面挂几缕苔。"""
    rng = np.random.default_rng(31)
    a = img.a
    tops = st.sect | st.rock
    for x in range(LW[0], W):
        if BACK[0] <= x < ROOF_A[0] - 8 or PART[0] <= x < PART[1]:
            continue
        ys = np.nonzero(tops[:ROOF_Y[1] + 60, x])[0]
        if not len(ys):
            continue
        y = ys[0]
        if rng.random() < 0.55:
            a[y, x] = rgba(MOSS[2 + (rng.random() < 0.35)])
            if rng.random() < 0.5:
                a[y + 1, x] = rgba(MOSS[1])
        if rng.random() < 0.07 and y - 1 >= 0:
            hgt = int(rng.integers(2, 6))
            lean = int(rng.choice([-1, 0, 0, 1]))
            for k in range(1, hgt):
                a[y - k, x + (lean if k > hgt // 2 else 0)] = rgba(MOSS[1 if k < hgt - 1 else 2])
        if ROOF_A[0] - 8 <= x < ROOF_A[1] + 3:
            yb = np.nonzero(st.sect[:ROOF_Y[1] + 8, x])[0][-1]
            if rng.random() < 0.05:
                for k in range(1, int(rng.integers(3, 8))):
                    a[yb + k, x] = rgba(MOSS[0] if k > 2 else MOSS[1])


def lintels(img, st):
    """门洞上的过梁：一整条长石（比墙里的石块长），底面一行暗。"""
    for (x0, x1) in ((LW[0] - 2, LW[1] + 2), (PART[0] - 1, PART[1] + 1)):
        y0, y1 = DOOR_TOP - 9, DOOR_TOP
        for x in range(x0, x1):
            for y in range(y0, y1):
                k = y - y0
                lv = 5 if k == 0 else (4 if k < 3 else 3)
                if x == x1 - 1:
                    lv += 1
                if x == x0:
                    lv -= 1
                if y == y1 - 1:
                    lv = 1
                img.put(x, y, SECT[lv])


def floor(img, st):
    """地板剖面：一行地面（亮度跟着光照：塌顶下面亮、屋顶下面暗），下面一条石板的断面，再往下是泥。"""
    rng = np.random.default_rng(41)
    L = np.zeros_like(st.light)
    L[G:G + 8] = st.light[G - 3][None, :] * 0.7
    ids, eg = voronoi_stones(st.floor, rng, cw=30, ch=5, p=3.0, row_jit=0.05)
    stone_shade(img, ids, eg, STONE, L, rng, ambient=0.1, gain=0.45, R=2.0, seam=0.8, wear=False)
    for x in range(OPEN, W):
        Lx = st.light[G - 2, x]
        img.a[G, x] = rgba(STONE[min(7, 2 + int(round(Lx * 4)))])
    for _ in range(70):                                   # 屋里地上的细沙 / 碎石（只在受光的地方看得出）
        x = int(rng.uniform(BACK[0], W))
        if st.light[G - 2, x] > 0.3:
            img.put(x, G - 1, STONE[3 + (rng.random() < 0.4)])


def rope_and_hooks(img, st):
    """导绳：从出口灯的石桩一路过铁桩、穿过左墙门洞、挂在后墙的钩子上、穿过内门、拴到泄水门的铁环。
    1 格宽、比引擎画的那根（晨身上的）暗一档。挂钩处正好在 ROPE_Y（引擎的绳结点也画在这一行）。"""
    c = oc(.2, .012, 230)
    pts = [(POST[1], ROPE_Y)] + [(x, ROPE_Y) for x in STAKES] + [(LW[0] - 1, ROPE_Y + 3), (LW[1] + 2, ROPE_Y + 3)] + \
          [(x, ROPE_Y) for x in HOOKS] + [(1262, ROPE_Y + 2)]
    sags = []
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        d = x1 - x0
        sag = 0 if d < 20 else min(7, d / 40)
        sag_line(img, x0, y0, x1, y1, sag, c)                       # 一根连续的暗绳（一段段亮会像虚线）
    for x in HOOKS:                                      # 钩子：钉在墙里的一截铁，弯上来；钉进墙那头锈出一道
        ip = up.PAL[up.IRON][1]
        img.put(x, ROPE_Y - 1, ip[5])
        img.put(x, ROPE_Y - 2, ip[6])
        img.put(x - 1, ROPE_Y - 2, ip[4])
        img.put(x + 1, ROPE_Y, ip[3])
        img.put(x + 1, ROPE_Y + 1, up.RUST[1][3])
        img.put(x + 1, ROPE_Y + 2, up.RUST[0][2])


def stamp(img, a, x, y):
    """把画好的 RGBA（物件材质画的）按房间坐标贴进 Img"""
    img.paste(a, int(x), int(y))


def crate_prop(w, h, seed, label=True, ox=0, oy=0, nails=True):
    """一只木箱的 Prop（还没打光）：横的木板一条条（板缝凹下去），四角竖条压在上面（钉子 + 锈水），
    顶上一块盖板的边（受光、落泥），贴一张泡皱了的圆字标签（右上角翘起来）。"""
    P = up.Prop(w, h, ox, oy, seed=seed)
    rng = np.random.default_rng(seed)
    P.fill(P.rect(0, 0, w, h), up.WOOD, 0.8, "h", dark=0.16)                      # 板缝（后面的暗）
    y = 2
    rows = []
    while y < h - 1:
        rh = int(rng.integers(4, 6))
        y1 = min(h - 1, y + rh)
        if h - 1 - y1 < 3:
            y1 = h - 1
        P.fill(P.rect(0, y + 1, w, y1), up.WOOD, 2.0, "h", round_=0.4)
        rows.append((y + 1, y1))
        y = y1
    P.fill(P.rect(0, 0, w, 2), up.WOOD, 2.6, "h")                                # 盖板
    P.fill(P.rect(0, h - 1, w, h), up.WOOD, 1.6, "h", dark=0.05)                # 底板
    for (x0, x1) in ((0, 2), (w - 2, w)):                                        # 四角的竖条
        P.fill(P.rect(x0, 1, x1, h), up.WOOD, 2.9, "v")
    if nails:
        for (r0, r1) in rows:
            for xn in (0, w - 1):
                yn = (r0 + r1) // 2
                P.put(xn + (1 if xn == 0 else -1) * 0, yn, up.PAL[up.IRON][1][6], room=False)
                P.drip(xn, yn + 1, 3 + (yn % 3), 0.8, room=False)
    if label:
        lw_, lh = 7, 6
        lx = int(rng.integers(3, max(4, w - lw_ - 3)))
        ly = int(rng.integers(3, max(4, h - lh - 2)))
        m = P.rect(lx, ly, lx + lw_, ly + lh)
        m[ly, lx + lw_ - 1] = False                                              # 右上角翘起来（露出木板）
        P.fill(m, up.PAPER, 2.3, None)
        P.nomoss[m] = True
        P.tint[m] = 1
        ink = up.PAL[up.PAPER][1][3]
        cx, cy = lx + 3, ly + 3
        for (dx, dy) in ((0, -1), (1, 0), (0, 1), (-1, 0)):                       # 圆字：一个圈
            P.put(cx + dx, cy + dy, ink, room=False)
        P.put(lx + 5, ly + 1 + int(rng.integers(0, 3)), ink, room=False)
        P.put(lx + lw_ - 2, ly, up.PAL[up.PAPER][1][8], room=False)              # 翘起来那角的亮边
    P.moss[0:2, :] += 0.25
    return P


def crate(w, h, rng, seed=0, ox=0, oy=0, label=True):
    P = crate_prop(w, h, seed, label=label, ox=ox, oy=oy)
    a = P.render(env=env_for(ox, oy, w, h, 0.35), ambient=0.38, gain=0.6)
    up.barnacles(a, [(int(rng.integers(3, w - 3)), h - 3)])
    return a


def boxes(img, st):
    """一摞贴圆字标签的箱子：底下两只、上面一只、旁边一只小的；大小、木色、标签位置都不一样。"""
    rng = np.random.default_rng(51)
    x0 = BOXES[0]
    specs = [(x0, 24, 20, 0), (x0 + 25, 22, 18, 0), (x0 + 6, 20, 16, 20), (x0 + 50, 16, 12, 0)]
    for i, (x, w_, h_, lift) in enumerate(specs):
        oy = G - h_ - lift
        stamp(img, crate(w_, h_, rng, seed=52 + i, ox=x, oy=oy), x, oy)
    for x in range(x0 - 1, x0 + 67):                                            # 箱底的接地阴影
        img.put(x, G, up.DARKC[0])


def low_cabinet(img, st):
    """靠后墙的一只矮柜（侧着放，柜面朝右）：竖纹侧板，顶上一块厚板；四个抽屉全朝右拉开（一层比一层拉得多一点，不一样长），
    看得见抽屉的侧板（顶边受光）和最外头的抽屉面板（铁拉手）。"""
    x0, x1 = LOWCAB
    top = G - 30
    outs = [9, 6, 11, 7]
    w = x1 - x0 + max(outs) + 2
    P = up.Prop(w, G - top + 1, x0, top, seed=61)
    R = P.R
    P.fill(R(x0, top + 2, x1, G - 1), up.WOOD, 2.0, "v", round_=0.5)            # 侧板
    P.fill(R(x0 + 3, top + 5, x1 - 3, G - 4), up.WOOD, 1.4, "v", dark=0.04)     # 侧板中间凹进去的一块
    P.fill(R(x0 - 1, top, x1 + 1, top + 2), up.WOOD, 2.8, "h", round_=0.8)      # 顶板
    P.fill(R(x0 + 1, G - 1, x0 + 4, G), up.WOOD, 1.6, "v")                       # 脚
    P.fill(R(x1 - 4, G - 1, x1 - 1, G), up.WOOD, 1.6, "v")
    for i, o in enumerate(outs):
        y0 = top + 3 + i * 7
        P.fill(R(x1, y0 + 1, x1 + o - 2, y0 + 6), up.WOOD, 1.8, "h", round_=0.3)  # 抽屉侧板
        P.fill(R(x1 + o - 2, y0, x1 + o, y0 + 7), up.WOOD, 2.6, "v")              # 抽屉面板（朝右）
        P.fill(R(x1 + o, y0 + 3, x1 + o + 1, y0 + 4), up.IRON, 3.0)                # 拉手
        P.rust[R(x1 + o - 2, y0 + 2, x1 + o + 1, y0 + 5)] += 0.3
    P.moss[R(x0 - 1, top, x1 + 1, top + 2)] += 0.2
    a = P.render(env=env_for(x0, top, w, G - top + 1, 0.35), ambient=0.36, gain=0.6)
    up.barnacles(a, [(4, G - top - 4), (x1 - x0 - 7, G - top - 9)])
    stamp(img, a, x0, top)
    for x in range(x0 - 1, x1 + 2):
        img.put(x, G, up.DARKC[0])


def hanging(img, st):
    """绑到屋顶下面的桌子和两把椅子（防水泡、防漂走）：绳子从屋顶底下的铁钩垂下来。桌子桌面朝下翻过来绑着（四条腿朝上）。"""
    ox, oy, w, h = 938, ROOF_Y[1], 100, 40
    P = up.Prop(w, h, ox, oy, seed=71)
    R = P.R
    tx, ty = 944, 118
    P.fill(R(tx, ty, tx + 38, ty + 3), up.WOOD, 2.4, "h", round_=0.6)           # 桌面（侧面看是一条厚板）
    P.fill(R(tx + 2, ty + 3, tx + 36, ty + 4), up.WOOD, 1.6, "h", dark=0.06)    # 桌面下的牙板
    for lx in (tx + 2, tx + 34):
        P.fill(R(lx, ty - 13, lx + 2, ty), up.WOOD, 2.2, "v")                    # 桌腿（朝上）
    P.fill(R(tx + 4, ty - 9, tx + 34, ty - 8), up.WOOD, 1.6, "h")                # 腿之间的横撑

    def chair(x, y, flip=False):
        s_ = -1 if flip else 1
        xa, xb = (x, x + 10) if not flip else (x - 9, x + 1)
        P.fill(R(min(x, x + s_), y, min(x, x + s_) + 2, y + 18), up.WOOD, 2.4, "v")   # 靠背 + 后腿
        P.fill(R(xa, y + 8, xb, y + 10), up.WOOD, 2.2, "h", round_=0.4)                 # 座面
        fx = x + s_ * 8
        P.fill(R(min(fx, fx + s_), y + 10, min(fx, fx + s_) + 2, y + 18), up.WOOD, 2.0, "v")  # 前腿
        P.fill(R(min(x, fx) + 1, y + 14, max(x, fx) + 1, y + 15), up.WOOD, 1.4, "h")     # 横撑
        P.fill(R(min(x, x + s_ * 2), y, max(x, x + s_ * 2) + 1, y + 2), up.WOOD, 2.8, "h")  # 靠背顶上一截搭脑
    chair(992, 104)
    chair(1022, 110, flip=True)
    a = P.render(env=env_for(ox, oy, w, h, 0.3), ambient=0.3, gain=0.6, moss_amt=0.6)
    stamp(img, a, ox, oy)
    rc = up.PAL[up.ROPE][1]
    for (x0, x1, y1) in ((tx + 3, tx + 3, ty - 13), (tx + 35, tx + 35, ty - 13), (992, 993, 104), (1020, 1021, 110)):
        for y in range(ROOF_Y[1] + 1, y1):
            t = (y - ROOF_Y[1]) / max(1, y1 - ROOF_Y[1])
            img.put(round(x0 + (x1 - x0) * t), y, rc[4] if y % 3 else rc[2])         # 拧着的绳：一格亮一格暗
        img.put(x0, ROOF_Y[1], up.PAL[up.IRON][1][5])
        img.put(x0 + 1, ROOF_Y[1], up.RUST[1][3])
    for x in range(tx + 6, tx + 32, 9):                                               # 桌子上绕的一圈绳子
        img.put(x, ty - 1, rc[4])
        img.put(x + 1, ty - 2, rc[3])


def equip_cabinet(img, st):
    """内间靠后墙的设备柜：铁皮柜，刷过一层青灰的漆（掉了好多块，掉漆的地方是锈），五格抽屉：抽屉面凸出来、四边倒角，
    每格一个铜框标签（纸泡得发灰，几个字）、一根铁拉手；顶上一块盖板受光、底下踢脚凹进去。读取头那格不特别标。"""
    x0, x1 = EQUIP
    top = G - 76
    w, h = x1 - x0 + 2, G - top + 1
    P = up.Prop(w, h, x0 - 1, top, seed=81)
    R = P.R
    P.fill(R(x0, top + 2, x1, G - 3), up.PAINT, 1.0, None, dark=0.12)              # 柜身（抽屉之间的缝）
    P.fill(R(x0, top + 2, x0 + 2, G - 3), up.PAINT, 2.4, None)                      # 两边的立边
    P.fill(R(x1 - 2, top + 2, x1, G - 3), up.PAINT, 2.4, None)
    P.fill(R(x0 - 1, top, x1 + 1, top + 2), up.PAINT, 3.0, None, round_=0.6)        # 盖板
    P.fill(R(x0 + 1, G - 3, x1 - 1, G), up.IRON, 1.2, None, dark=0.1)               # 踢脚（凹进去）
    rng = np.random.default_rng(61)
    for i in range(5):
        y0 = top + 3 + i * 14
        P.fill(R(x0 + 2, y0 + 1, x1 - 2, y0 + 13), up.PAINT, 2.2, None, round_=0.6)   # 抽屉面
        hx = (x0 + x1) // 2
        lw_ = int(rng.integers(9, 14))
        lx = hx - lw_ // 2
        P.fill(R(lx - 1, y0 + 3, lx + lw_ + 1, y0 + 7), up.BRASS, 2.8, None)           # 铜框
        m = R(lx, y0 + 4, lx + lw_, y0 + 6)
        P.fill(m, up.PAPER, 2.4, None)                                                  # 标签纸
        P.nomoss[m] = True
        P.tint[m] = 0
        for x in range(lx + 1, lx + lw_ - 1, 2):
            if rng.random() < 0.7:
                P.put(x, y0 + 5 - (rng.random() < 0.3), up.PAL[up.PAPER][0][3])          # 字
        P.fill(R(hx - 4, y0 + 9, hx + 4, y0 + 10), up.IRON, 3.6, None)                  # 拉手
        P.fill(R(hx - 4, y0 + 10, hx - 3, y0 + 11), up.IRON, 3.0, None)
        P.fill(R(hx + 3, y0 + 10, hx + 4, y0 + 11), up.IRON, 3.0, None)
        P.rust[R(x0 + 2, y0 + 11, x1 - 2, y0 + 13)] += 0.3                             # 抽屉下沿锈一圈
        P.drip(hx - 3 + (i % 3) * 3, y0 + 11, 3 + i % 3, 0.8)
    for _ in range(9):                                                                 # 掉漆（露锈）
        cx_, cy_ = int(rng.integers(x0, x1)), int(rng.integers(top, G))
        P.rust[R(cx_, cy_, cx_ + int(rng.integers(1, 4)), cy_ + int(rng.integers(1, 3)))] += 0.7
    P.rust[R(x0, G - 10, x1, G)] += 0.12
    a = P.render(env=env_for(x0 - 1, top, w, h, 0.35), ambient=0.36, gain=0.6, moss_amt=0.7)
    up.barnacles(a, [(3, h - 6), (w - 5, h - 10), (5, h - 22)])
    stamp(img, a, x0 - 1, top)
    for x in range(x0 - 1, x1 + 2):
        img.put(x, G, up.DARKC[0])


def sluice_recess(img, st):
    """泄水门那面后墙：一圈大块条石砌的门框（门楣一整条长石、两边立石），里面深深凹进去（门本身是物件 warehouse_sluice_door）。"""
    x0, x1, y0 = 1258, 1336, 110
    m_in = np.zeros((H, W), bool)
    m_in[y0:G, x0:x1] = True
    rng = np.random.default_rng(171)
    yy, xx = np.mgrid[0:H, 0:W]
    v = up.vn(xx / 3.0, yy / 3.0, 3)
    for y in range(y0, G):                                                       # 凹进去的里面：最暗，上面在门楣的影子里
        for x in range(x0, x1):
            k = 0 if (y < y0 + 4 or v[y, x] < 0.55) else 1
            img.a[y, x] = rgba(SP[k][1])
    frame = np.zeros((H, W), bool)
    frame[y0 - 8:y0, x0 - 4:x1 + 4] = True
    frame[y0:G, x0 - 4:x0] = True
    frame[y0:G, x1:x1 + 4] = True
    lit = np.clip(st.light + 0.35, 0, 1)
    ids, eg = voronoi_stones(frame, rng, cw=9, ch=13, p=3.4, row_jit=0.05)
    lint = np.zeros((H, W), bool)
    lint[y0 - 8:y0, x0 - 4:x1 + 4] = True
    ids[lint] = ids.max() + 1                                                    # 门楣：一整条长石（缝只在它的四边）
    ly, lx = np.nonzero(lint)
    eg[lint] = np.minimum(np.minimum(ly - (y0 - 8), y0 - 1 - ly), np.minimum(lx - (x0 - 4), x1 + 3 - lx)) + 0.5
    stone_shade(img, ids, eg, STONE, lit, np.random.default_rng(172), ambient=0.18, gain=0.5, moss=0.4,
                R=2.0, seam=0.8, per=(3, 5))


def post_and_stakes(img):
    """出口灯的石桩（一截截方石垒的，顶上一截铁臂挂灯）和导绳的铁桩（锈，桩脚糊着泥）。"""
    x0, x1 = POST
    top = 146
    g = int(round(gy_out((x0 + x1) / 2)))
    m = np.zeros((H, W), bool)
    m[top:g + 1, x0:x1] = True
    ids, eg = voronoi_stones(m, np.random.default_rng(181), cw=14, ch=15, p=4.0, row_jit=0.0)
    L = np.full((H, W), 0.8)
    stone_shade(img, ids, eg, STONE, L, np.random.default_rng(182), ambient=0.12, gain=0.5, moss=0.5,
                R=2.0, seam=0.85, per=(3, 5))
    # 铁臂（挂灯）+ 绳子绕两圈拴在桩上
    P = up.Prop(12, 6, x1 - 1, top + 1, seed=183)
    P.fill(P.R(x1, top + 3, x1 + 7, top + 5), up.IRON, 2.4, None)
    P.fill(P.R(x1 - 1, top + 2, x1 + 1, top + 6), up.IRON, 3.0, None)                # 箍在桩上的一圈铁
    P.fill(P.R(x1 + 6, top + 5, x1 + 7, top + 6), up.IRON, 2.0, None)
    stamp(img, P.render(ambient=0.36, gain=0.6, moss_amt=0.4), x1 - 1, top + 1)
    rc = up.PAL[up.ROPE][1]
    for y in (ROPE_Y - 1, ROPE_Y + 1):
        for x in range(x0, x1):
            img.put(x, y, rc[5] if (x + y) % 3 else rc[3])
    for sx in STAKES:
        g = int(round(gy_out(sx)))
        P = up.Prop(4, g + 2 - (ROPE_Y - 4), sx - 1, ROPE_Y - 4, seed=sx)
        P.fill(P.R(sx, ROPE_Y - 3, sx + 2, g + 2), up.IRON, 2.0, None, round_=0.6)
        P.fill(P.R(sx - 1, ROPE_Y - 4, sx + 3, ROPE_Y - 2), up.IRON, 2.6, None)          # 桩头
        P.rust[P.R(sx - 1, g - 9, sx + 3, g + 2)] += 0.5                                  # 桩脚：锈 + 泥
        P.rust[P.R(sx - 1, ROPE_Y - 4, sx + 3, ROPE_Y)] += 0.2
        P.moss[P.R(sx - 1, g - 4, sx + 3, g + 2)] += 0.4
        stamp(img, P.render(ambient=0.32, gain=0.6), sx - 1, ROPE_Y - 4)


# ====================================================================== 物件（每个一张横排帧图）
class Obj:
    def __init__(self, x, y, w, h, frames):
        self.x, self.y, self.w, self.h, self.n = x, y, w, h, frames
        self.f = [Img(w, h) for _ in range(frames)]

    def put(self, k, X, Y, c):
        """房间坐标画到第 k 帧"""
        self.f[k].put(X - self.x, Y - self.y, c)

    def sheet(self):
        a = np.zeros((self.h, self.w * self.n, 4), np.uint8)
        for k, f in enumerate(self.f):
            a[:, k * self.w:(k + 1) * self.w] = f.a
        return a


def lantern(o: Obj, k, cx, top, bright):
    """出口灯：顶上一个吊环、一顶铁皮灯罩（锈），四根细铁条护着一只玻璃罩，里面暖光（两帧一明一暗）；
    玻璃右上角一格冷的高光，底座一块铁板。只有这里用暖黄。"""
    P = up.Prop(o.w, o.h, o.x, o.y, seed=191)
    R = P.R
    P.fill(R(cx - 1, top, cx + 2, top + 1), up.IRON, 2.0, None)                     # 吊环
    P.fill(R(cx - 3, top + 1, cx + 4, top + 3), up.IRON, 2.8, None, round_=0.5)     # 灯罩
    P.fill(R(cx - 2, top + 3, cx + 3, top + 8), up.GLASS, 1.6, None)                # 玻璃（下面盖暖光）
    P.fill(R(cx - 3, top + 3, cx - 2, top + 8) | R(cx + 3, top + 3, cx + 4, top + 8), up.IRON, 2.6, None)  # 两边铁条
    P.fill(R(cx - 3, top + 8, cx + 4, top + 9), up.IRON, 2.4, None)                 # 底座
    P.fill(R(cx, top + 9, cx + 1, top + 10), up.IRON, 1.8, None)
    P.rust[R(cx - 3, top + 1, cx + 4, top + 3)] += 0.35
    P.rust[R(cx - 3, top + 8, cx + 4, top + 10)] += 0.45
    P.nomoss[:] = True
    a = P.render(ambient=0.36, gain=0.6, moss_amt=0, silt_amt=0)
    o.f[k].paste(a, 0, 0)
    for y in range(top + 3, top + 8):
        for x in range(cx - 2, cx + 3):
            d = abs(x - cx) + abs(y - (top + 5)) * 0.7
            lv = (4 if d < 1.2 else (3 if d < 2.4 else 2)) if bright else (3 if d < 1.2 else (2 if d < 2.4 else 1))
            o.put(k, x, y, WARM[lv])
    o.put(k, cx + 2, top + 3, oc(.62, .03, 220) if bright else oc(.5, .03, 220))     # 玻璃上的冷高光
    o.put(k, cx - 1, top + 3, WARM[min(4, (3 if bright else 2) + 1)])                 # 灯罩下沿被灯照亮
    o.put(k, cx, top + 3, WARM[min(4, (3 if bright else 2) + 1)])


def make_exit_light():
    o = Obj(30, 150, 16, 12, 2)
    for k in range(2):
        lantern(o, k, 38, 151, bright=(k == 0))
    return o


def make_knot(x):
    """绳结：导绳上打的一个粗结（绳子拧着，一格亮一格暗）+ 系着的两条布条往左飘（水流），布条有折（上沿亮、折痕暗）；
    lit = 布条上缝的反光带亮起来。"""
    o = Obj(x - 4, ROPE_Y - 3, 9, 14, 2)
    cloth = up.PAL[up.CLOTH][0]
    rope = up.PAL[up.ROPE][1]
    band = [oc(.4, .04, 214), oc(.52, .045, 208), oc(.64, .04, 204)]
    for k in range(2):
        for (dx, dy, lv) in ((-1, 0, 3), (0, -1, 5), (1, 0, 4), (0, 0, 4), (0, 1, 2), (-1, 1, 1), (1, 1, 3),
                             (1, -1, 6), (-1, -1, 3)):
            o.put(k, x + dx, ROPE_Y + dy, rope[lv])
        for i in range(9):                                   # 长的那条
            X = x - (i * i) // 22
            fold = (i % 4 == 2)
            o.put(k, X, ROPE_Y + 2 + i, cloth[5 if fold else (7 if i < 5 else 6)])
            o.put(k, X + 1, ROPE_Y + 2 + i, cloth[6 if fold else (8 if i < 3 else 7)])
        for i in range(5):                                   # 短的那条
            o.put(k, x + 2 - i // 3, ROPE_Y + 2 + i, cloth[6 if i < 3 else 5])
        o.put(k, x - 1 - 81 // 22, ROPE_Y + 11, cloth[8])    # 布尾一格亮
        if k == 1:
            for i in range(2, 6):
                X = x - (i * i) // 22
                o.put(k, X, ROPE_Y + 2 + i, band[1])
                o.put(k, X + 1, ROPE_Y + 2 + i, band[2] if i < 5 else band[1])
            o.put(k, x + 2, ROPE_Y + 3, band[0])
    return o


def make_broken_box():
    """破箱子：右上角整块崩掉（断口参差、里面露出后板，断茬浅一点），盖子歪着靠在右边，一块断板掉在地上；
    spilled：里面的东西撒出来（三颗不一样的纽扣、一只空瓶、一张照片）。"""
    o = Obj(838, 200, 52, 27, 2)
    for k in range(2):
        bx, bw, bh = 842, 26, 18
        P = crate_prop(bw, bh, 82, label=True, ox=bx, oy=G - bh)
        # 崩口：从顶边 x≈15 斜着往右下到右边 y≈10（参差），崩口里面是后板（暗、凹）
        brk = np.zeros((bh, bw), bool)
        edge = []
        for xx in range(bw):
            t = (xx - 14) / 11.0
            yb = int(round(10 * max(0.0, t) + (1 if xx % 3 == 0 else 0) - (1 if xx % 5 == 1 else 0))) if xx >= 14 else -1
            edge.append(yb)
            if yb >= 0:
                brk[:yb + 1, xx] = True
        inside = brk & ~P.rect(bw - 2, 0, bw, bh)
        P.fill(inside, up.WOOD, 0.2, "h", dark=0.3)                     # 后板（箱子里面）
        outer = brk & P.rect(bw - 2, 0, bw, bh)
        P.mat[outer] = 0                                                  # 角条那截一起断了
        for xx, yb in enumerate(edge):                                    # 断茬：浅、暖
            if 0 <= yb < bh - 1 and xx < bw:
                P.lift[yb + 1, xx] = 0.12
                P.tint[yb + 1, xx] = 2
        P.mat[0:2, 14:] = 0                                               # 盖板那截没了
        P.moss[:3, :] += 0.15
        a = P.render(env=env_for(bx, G - bh, bw, bh, 0.35), ambient=0.38, gain=0.6)
        o.f[k].paste(a, bx - o.x, G - bh - o.y)
        # 崩下来的那块盖板：斜靠在箱子左边；掉在右边地上的一截断板
        Q = up.Prop(34, 22, 838, G - 21, seed=83)
        lid = ua.poly_mask([(838 - 838, 21), (841 - 838, 21), (846 - 838, 3), (843 - 838, 2)], 22, 34)
        Q.fill(lid, up.WOOD, 2.6, "v", round_=0.4)
        Q.fill(Q.R(860, G - 2, 870, G), up.WOOD, 1.8, "h")
        Q.fill(Q.R(866, G - 3, 869, G - 2), up.WOOD, 1.4, "h")                # 断茬翘起来一点
        Q.put(843, G - 12, up.PAL[up.IRON][1][6])                         # 盖板上的钉子
        Q.drip(843, G - 11, 3)
        b = Q.render(env=env_for(838, G - 21, 34, 22, 0.35), ambient=0.38, gain=0.6)
        o.f[k].paste(b, 0, G - 21 - o.y)
        for x in range(bx - 4, bx + bw + 2):
            o.put(k, x, G, up.DARKC[0])
        if k == 1:
            ip = up.PAL[up.IRON][1]
            for (bx_, c0, c1) in ((872, up.PAL[up.PAPER][1][4], up.PAL[up.PAPER][1][7]),
                                  (879, up.PAL[up.WOOD][2][4], up.PAL[up.WOOD][2][7]), (884, ip[4], ip[7])):
                o.put(k, bx_, G - 2, c1)                                  # 纽扣：2×2，一格亮、中间一个暗点
                o.put(k, bx_ + 1, G - 2, c0)
                o.put(k, bx_, G - 1, c0)
                o.put(k, bx_ + 1, G - 1, up.DARKC[1])
            gl = up.PAL[up.GLASS][0]                                      # 空瓶（躺着）：瓶身、瓶颈、高光
            for i in range(9):
                o.put(k, 873 + i, G - 4, gl[5] if i < 6 else gl[3])
                if i < 8:
                    o.put(k, 873 + i, G - 3, gl[3] if i < 6 else gl[2])
                if i < 6:
                    o.put(k, 873 + i, G - 2, gl[2])
            for i in range(3):
                o.put(k, 875 + i, G - 4, gl[8])
            o.put(k, 882, G - 4, up.PAL[up.WOOD][1][4])                   # 瓶塞
            pp = up.PAL[up.PAPER][1]
            for yy in range(4):                                           # 照片：白边，中间暗（看不清是什么）
                for xx in range(7):
                    edge_ = xx in (0, 6) or yy in (0, 3)
                    o.put(k, 846 + xx, G - 4 + yy, pp[6] if (edge_ and yy == 0) else (pp[5] if edge_ else up.PAL[up.CLOTH][0][2 + (xx + yy) % 2]))
    return o


# ---- 倒下的高柜 / 浮箱 / 五斗柜（拴浮箱的小游戏）
CAB_L, CAB_T = 96, 15                # 高柜：长、厚
FOOT = (970, G)                      # 倒下时柜脚着地的那个角
DRESSER = (1052, 1083, 190)          # 五斗柜：x0, x1, 顶


def cabinet_pose(state):
    """高柜在三个状态下的位置：返回 (柜脚那个角, 角度)。角度 = 柜身往右上抬起多少（弧度）。"""
    base = math.atan2(G - DRESSER[2] + 1, DRESSER[0] + 12 - FOOT[0])
    if state == "lifted":
        return FOOT, base + 0.2
    if state == "tilt_wrong":
        # 柜脚一头被浮起来：绕压在五斗柜上的那一头转，柜脚离地
        top = (FOOT[0] + CAB_L * math.cos(base), FOOT[1] - CAB_L * math.sin(base))
        a = base - 0.15
        return (top[0] - CAB_L * math.cos(a), top[1] + CAB_L * math.sin(a)), a
    return FOOT, base


def cabinet_point(state, u, v):
    """柜子局部坐标（u 沿长度从柜脚 0 到柜顶 CAB_L，v 从下沿 0 到上沿 CAB_T）→ 房间坐标"""
    (fx, fy), a = cabinet_pose(state)
    ca, sa = math.cos(a), math.sin(a)
    return fx + u * ca - v * sa, fy - u * sa - v * ca


def draw_cabinet(o: Obj, k, state):
    """倒着的高柜（正面朝我们）。按柜身的局部坐标搭（u 沿长度，柜脚 0 → 柜顶 CAB_L；v 从下沿 0 到上沿 CAB_T），
    再整张打光，所以转了以后木纹、门缝、倒角还是顺着柜身，受光却按房间的方向（朝上那条侧面亮、压在下面那条边暗）：
    - 正面 v 0..12.5：两边立梃（顺长纹）、两扇门（门框 + 凹进去的门芯板 + 鼓起来的芯，门芯两块拼板一道缝）、
      两扇门之间一道门缝、锁眼铁片和两个铁拉手、门轴那边四个合页；
    - 朝上的侧板 v 12.5..15：一条斜面，最受光，落泥、长苔；
    - 柜顶一圈檐（比柜身宽一格，两道线脚）、柜脚一截踢脚 + 两只短腿；
    - 柜顶、柜脚各一个铁拴环（浮箱的绳拴在这里）。"""
    (fx, fy), a = cabinet_pose(state)
    ca, sa = math.cos(a), math.sin(a)
    L, T, F = CAB_L, CAB_T, 12.5
    U0, U1, V0, V1 = -4, L + 1, -2, T + 2                     # 局部画布：x = u - U0，y = V1 - v（v 朝上）
    P = up.Prop(U1 - U0, V1 - V0, 0, 0, seed=41)
    U = P.xx + U0 + 0.5
    V = V1 - (P.yy + 0.5)
    box = lambda u0, u1, v0, v1: (U >= u0) & (U < u1) & (V >= v0) & (V < v1)

    def fill(m, mat, hgt, part=None, dark=0.0, grain="h"):
        return P.fill(m, mat, hgt, grain=grain, part=part, dark=dark)
    fill(box(0, L, 0, F), up.WOOD, 1.0, dark=0.12)                                # 柜身（门后面的深处）
    fill(box(0, L, 0, 1.6), up.WOOD, 3.2)                                         # 下沿立梃
    fill(box(0, L, F - 1.6, F), up.WOOD, 3.2)                                     # 上沿立梃
    side = box(0, L, F, T)
    fill(side, up.WOOD, 0.0)                                                      # 朝上的侧板：斜面（越往外越低）
    P.hf[side] = 3.4 - (V[side] - F) * 1.1
    gap = L * 0.5
    for (u0, u1) in ((4, gap - 0.5), (gap + 0.5, L - 5)):
        fill(box(u0, u1, 1.6, F - 1.6), up.WOOD, 2.6)                              # 门框
        fill(box(u0 + 2, u1 - 2, 3.6, F - 3.6), up.WOOD, 1.2, dark=0.07)          # 门芯（凹）
        mid = (u0 + u1) / 2
        for (a0, a1) in ((u0 + 3, mid - 0.5), (mid + 0.5, u1 - 3)):
            fill(box(a0, a1, 4.6, F - 4.6), up.WOOD, 2.3)                         # 门芯里鼓起来的两块拼板
    fill(box(gap - 0.5, gap + 0.5, 1.6, F - 1.6), up.WOOD, 0.2, dark=0.2)         # 门缝
    fill(box(0, 4, 0, F), up.WOOD, 3.0, grain="v")                                # 柜脚的踢脚
    m = box(L - 5, L, -1, T + 1)
    fill(m, up.WOOD, 4.0, grain="v")                                              # 柜顶的檐
    P.hf[m & box(L - 3, L - 2, -1, T + 1)] -= 1.0                                 # 一道线脚
    fill(box(-3, 0, 1, 4) | box(-3, 0, 8.5, 11.5), up.WOOD, 2.0)                  # 两只短腿
    for (u0, u1, v0, v1, hgt) in ((gap - 3, gap - 1, 5.6, 7.6, 3.4), (gap + 1, gap + 3, 5.6, 7.6, 3.4),
                                  (gap - 0.5, gap + 0.5, 8, 9.6, 3.0)):
        mm = box(u0, u1, v0, v1)
        fill(mm, up.IRON, hgt)                                                     # 拉手、锁眼铁片
        P.rust[mm] += 0.25
    for u0 in (9, 37, gap + 7, L - 13):                                           # 合页（门轴在下沿那边）
        mm = box(u0, u0 + 3, 0, 1.6)
        fill(mm, up.IRON, 3.1)
        P.rust[mm] += 0.4
    P.moss[side] += 0.2
    P.moss[box(0, 4, 0, F)] += 0.12
    # 局部 → 房间：u 轴 = (cos a, -sin a)，v 轴（朝上）= (-sin a, -cos a)；局部 +y = -v
    wx = fx + U * ca - V * sa
    wy = fy - U * sa - V * ca
    E = env_for(o.x, o.y, o.w, o.h, 0.45)
    ex = np.clip(np.round(wx - o.x).astype(int), 0, o.w - 1)
    ey = np.clip(np.round(wy - o.y).astype(int), 0, o.h - 1)
    loc = P.render(env=E[ey, ex], ambient=0.4, gain=0.6, axes=((ca, -sa), (sa, ca)), world=(wx, wy))

    def to_local(X, Y):
        dx, dy = X - fx, Y - fy
        u = dx * ca - dy * sa
        v = -dx * sa - dy * ca
        return u - U0, V1 - v
    img = up.rotate_into(loc, o.x, o.y, o.w, o.h, to_local)
    if DUMP is not None:
        DUMP.append(loc)
    # 锈水：拉手、合页往下（房间坐标的「下」）拖
    for (u, v, ln) in ((gap - 2, 5.0, 5), (gap + 2, 5.0, 4), (10, 0.5, 3), (L - 11, 0.5, 4)):
        X, Y = cabinet_point(state, u, v)
        for d in range(ln):
            xx, yy = int(round(X)) - o.x, int(round(Y)) + 1 + d - o.y
            if 0 <= yy < o.h and 0 <= xx < o.w and img[yy, xx, 3] and d % 3 != 2:
                img[yy, xx, :3] = up.RUST[1][3 if d < 2 else 2]
    # 藤壶：压在下面那条边上
    bp = []
    for u in (14, 27, 33, 60, 71, 83):
        X, Y = cabinet_point(state, u, 0.6)
        bp.append((int(round(X)) - o.x, int(round(Y)) - 1 - o.y))
    up.barnacles(img, bp)
    o.f[k].paste(img, 0, 0)
    for (u, v) in ((CAB_L - 2, CAB_T + 1), (2, CAB_T + 1)):  # 拴环（柜顶 / 柜脚，在侧板上）：一圈铁，左下背光、右上亮，锈
        X, Y = cabinet_point(state, u, v)
        X, Y = int(round(X)), int(round(Y))
        for (ddx, ddy, c) in ((0, -1, up.PAL[up.IRON][1][6]), (-1, 0, up.PAL[up.IRON][1][3]), (1, 0, up.PAL[up.IRON][1][5]),
                              (0, 1, up.RUST[1][2]), (-1, -1, up.PAL[up.IRON][1][4]), (1, 1, up.RUST[0][2])):
            o.put(k, X + ddx, Y + ddy, c)
    # 柜脚着地的那一点：地上一小段接地阴影
    if state != "tilt_wrong":
        for X in range(FOOT[0] - 4, FOOT[0] + 9):
            o.put(k, X, G, up.DARKC[0])


def draw_dresser(o: Obj, k, dx=0, dy=0):
    """五斗柜：矮而宽、很沉。柜顶一块厚板（两边探出一格，朝上那面落泥长苔），两块竖纹侧板，四个横纹抽屉
    （抽屉面鼓出来一点、四边倒角，抽屉之间一道深缝），铁拉手 + 锁眼铁片（锈，锈水往下拖），底下踢脚板 + 两只方脚，
    脚下一行接地阴影。第三个抽屉泡胀了、往外鼓一格；左上角的面板崩掉一块。"""
    x0, x1, top = DRESSER
    x0, x1, top = x0 + dx, x1 + dx, top + dy
    P = up.Prop(o.w, o.h, o.x, o.y, seed=31)
    R = P.R
    P.fill(R(x0 - 1, top, x1 + 1, top + 3), up.WOOD, 3.2, "h", round_=1.0)          # 柜顶
    P.fill(R(x0, top + 3, x0 + 2, G - 3), up.WOOD, 2.4, "v", round_=0.6)            # 侧板
    P.fill(R(x1 - 2, top + 3, x1, G - 3), up.WOOD, 2.4, "v", round_=0.6)
    P.fill(R(x0 + 2, top + 3, x1 - 2, G - 3), up.WOOD, 0.4, "h", dark=0.14)         # 抽屉后面的框（缝里）
    ys = [top + 3, top + 11, top + 19, top + 27, G - 3]
    for i in range(4):
        y0, y1 = ys[i] + 1, ys[i + 1]
        bulge = 1 if i == 2 else 0
        P.fill(R(x0 + 2, y0, x1 - 2, y1), up.WOOD, 2.0 + 0.5 * bulge, "h", round_=0.9 + 0.5 * bulge, gv0=i * 3.1)
        cx = (x0 + x1) // 2
        yc = (y0 + y1) // 2
        P.fill(R(cx - 2, yc, cx + 3, yc + 1), up.IRON, 3.4)                             # 拉手（一根横的铁）
        P.fill(R(cx - 3, yc - 1, cx - 2, yc + 1), up.IRON, 3.0)
        P.fill(R(cx + 3, yc - 1, cx + 4, yc + 1), up.IRON, 3.0)
        P.fill(R(cx, yc - 3, cx + 1, yc - 1), up.IRON, 2.4)                             # 锁眼铁片
        P.rust[R(cx - 3, yc - 3, cx + 4, yc + 1)] += 0.25
        P.drip(cx + (i % 2) * 2 - 1, yc + 1, 4 + (i * 3) % 5, 0.75)
    # 崩掉的一块（左上角抽屉面）：露出里面的框，断口一格浅
    chip = R(x0 + 2, top + 4, x0 + 5, top + 6)
    P.hf[chip] = 0.8
    P.dark[chip] = 0.1
    P.fill(R(x0, G - 3, x1, G - 1), up.WOOD, 2.2, "h", round_=0.5)                  # 踢脚板
    P.fill(R(x0, G - 1, x0 + 4, G), up.WOOD, 1.8, "v")                               # 两只方脚
    P.fill(R(x1 - 4, G - 1, x1, G), up.WOOD, 1.8, "v")
    P.moss[R(x0 - 1, top, x1 + 1, top + 2)] += 0.2
    a = P.render(env=env_for(o.x, o.y, o.w, o.h, 0.42), ambient=0.4, gain=0.6)
    up.barnacles(a, [(x0 - o.x + 3, G - 2 - o.y), (x1 - o.x - 6, G - 4 - o.y), (x1 - o.x - 2, top + 9 - o.y)])
    up.contact(a, x0 - 1 - o.x, x1 + 1 - o.x, G - o.y, k=1)
    o.f[k].paste(a, 0, 0)


def make_cabinet_set():
    cab = Obj(950, 136, 140, 91, 3)
    for k, stt in enumerate(("fallen", "lifted", "tilt_wrong")):
        draw_cabinet(cab, k, stt)
    fur = Obj(1020, 186, 68, 41, 4)
    for k, (dx, dy) in enumerate(((0, 0), (-1, 0), (0, 0), (-24, 0))):
        draw_dresser(fur, k, dx, dy)
    # 浮箱：一只旧的浮筒（铁皮、两道箍、顶上一个环），平时用短绳拴在地上一块石坠上
    flo = Obj(918, 112, 170, 115, 5)
    drum = [oc(.09, .012, 245), oc(.13, .016, 232), oc(.18, .018, 225), oc(.24, .018, 220), oc(.31, .016, 216)]

    def float_at(k, cx, cy, rope_to=None):
        """浮箱：一只圆角的铁皮箱（13×10，鼓鼓的），两道凸起的竖箍（铆钉），顶上一个吊环、右边一个气阀；
        锈从下半截和箍边上长起来，箱底几颗藤壶；绳子（拧着的麻绳）从底下拴出去，松松地弯一点。"""
        P = up.Prop(17, 15, cx - 8, cy - 9, seed=201)
        R = P.R
        body = R(cx - 6, cy - 5, cx + 7, cy + 5)
        for (X, Y) in ((cx - 6, cy - 5), (cx + 6, cy - 5), (cx - 6, cy + 4), (cx + 6, cy + 4)):
            body &= ~R(X, Y, X + 1, Y + 1)                                    # 圆角
        P.fill(body, up.IRON, 2.6, None, round_=1.6)
        for bxx in (cx - 3, cx + 3):
            P.fill(R(bxx, cy - 5, bxx + 1, cy + 5), up.IRON, 3.3, None)       # 竖箍
        P.fill(R(cx - 1, cy - 8, cx + 2, cy - 7) | R(cx - 1, cy - 7, cx, cy - 5) | R(cx + 1, cy - 7, cx + 2, cy - 5),
               up.IRON, 2.4, None)                                            # 吊环
        P.fill(R(cx + 7, cy - 2, cx + 9, cy), up.BRASS, 2.6, None)            # 气阀（铜）
        P.rust[R(cx - 6, cy + 1, cx + 7, cy + 5)] += 0.3
        for bxx in (cx - 3, cx + 3):
            P.drip(bxx, cy - 2, 6, 0.7)
        a = P.render(env=env_for(cx - 8, cy - 9, 17, 15, 0.45), ambient=0.38, gain=0.6, moss_amt=0.6)
        up.barnacles(a, [(4, 13), (10, 13)])
        for (bxx, byy) in ((cx - 3, cy - 3), (cx - 3, cy + 2), (cx + 3, cy - 3), (cx + 3, cy + 2)):
            a[byy - (cy - 9), bxx - (cx - 8), :3] = up.PAL[up.IRON][1][7]       # 箍上的铆钉
        flo.f[k].paste(a, cx - 8 - flo.x, cy - 9 - flo.y)
        if rope_to is not None:
            sag_line(flo.f[k], cx - 1 - flo.x, cy + 5 - flo.y, rope_to[0] - flo.x, rope_to[1] - flo.y, 2.0,
                     up.PAL[up.ROPE][1][3], c_lit=up.PAL[up.ROPE][1][5])
    # idle（两帧上下浮 1 格）：拴在地上的石坠（一块圆石头，绳子在上面绕一圈）
    stone = ua.boulder(9, 6, 207, ua.bramp(6, .1, .32, 262, 244))
    for k, dy in ((0, 0), (1, 1)):
        float_at(k, 931, 191 + dy, rope_to=(927, G - 6))
        sh, sw = stone.shape[:2]
        flo.f[k].paste(stone, 927 - sw // 2 - flo.x, G - sh + 1 - flo.y)
        for xx in range(-4, 5):
            flo.put(k, 927 + xx, G - 3, up.PAL[up.ROPE][1][4 if xx % 3 else 2])  # 绕一圈的绳
        flo.put(k, 925, G - 5, up.MOSS[3])
        flo.put(k, 926, G - 5, up.MOSS[2])
        for xx in range(-5, 6):
            flo.put(k, 927 + xx, G, up.DARKC[0])
    # tied_top：浮在柜顶上方（柜子抬起来以后那一头的拴环）
    tx, ty = cabinet_point("lifted", CAB_L - 2, CAB_T + 1)
    float_at(2, int(round(tx)) - 2, int(round(ty)) - 30, rope_to=(int(round(tx)), int(round(ty)) - 1))
    # tied_foot：浮在柜脚上方
    fx, fy = cabinet_point("tilt_wrong", 2, CAB_T + 1)
    float_at(3, int(round(fx)) + 2, int(round(fy)) - 30, rope_to=(int(round(fx)), int(round(fy)) - 1))
    # held：空（在晨手里）
    return cab, fur, flo


DOOR_O = (1060, 164, 54, 63)          # 内门物件：开着的时候门板往大厅这边转出来，所以往左多留了一截


def make_inner_door():
    """内门（隔墙的门洞里，侧着看）。
    closed：厚木门板嵌在门洞里：三块竖板（越往里越窄，透视），两道铁门箍横着包过来、箍头在大厅这面露出一格、钉帽亮；
      大厅这面一个铁拉环（伸出门板外面两格，一看就是门），门顶在门楣的影子里，门脚泡烂了一点、糊着泥和苔。
    open：五斗柜挪开以后门往大厅这边拉开了：门板转过来露出正面（四块竖板、两道箍、拉环），门轴在门洞左沿，
      离镜头近的那头（左边）高一点、矮一点（透视），门板厚度在外沿露一格亮边；门洞里是内间的暗。"""
    ox, oy, w, h = DOOR_O
    o = Obj(ox, oy, w, h, 2)
    x0, x1 = PART
    ip = up.PAL[up.IRON][1]
    # ---- closed
    P = up.Prop(w, h, ox, oy, seed=211)
    R = P.R
    for (a_, b_) in ((x0, x0 + 4), (x0 + 4, x0 + 7), (x0 + 7, x1)):
        P.fill(R(a_, DOOR_TOP + 1, b_, G), up.WOOD, 2.2 - 0.3 * (a_ - x0) / 4, "v", round_=0.5)
    P.dark[R(x0, DOOR_TOP + 1, x1, DOOR_TOP + 4)] += 0.08                        # 门楣的影子
    for yb in (DOOR_TOP + 9, G - 12):
        P.fill(R(x0 - 1, yb, x1, yb + 2), up.IRON, 3.0, None)                     # 门箍（箍头在大厅这面露一格）
        P.rust[R(x0 - 1, yb, x1, yb + 2)] += 0.3
        P.drip(x0 + 2, yb + 2, 5, 0.7)
        P.drip(x0 + 6, yb + 2, 3, 0.6)
    ry = DOOR_TOP + 30
    P.fill(R(x0 - 3, ry, x0 - 2, ry + 4) | R(x0 - 2, ry - 1, x0, ry) | R(x0 - 2, ry + 4, x0, ry + 5), up.IRON, 3.2, None)  # 拉环
    P.fill(R(x0, ry + 1, x0 + 2, ry + 3), up.IRON, 2.8, None)                     # 拉环的座
    for xx in range(x0, x1):                                                      # 门脚泡烂了：参差缺几格
        if up.hsh(xx, 7) < 0.45:
            P.mat[G - 1 - oy, xx - ox] = 0
    P.moss[R(x0, G - 6, x1, G)] += 0.5
    a = P.render(env=env_for(ox, oy, w, h, 0.4), ambient=0.38, gain=0.6)
    for (xx, yy) in ((x0 - 1, DOOR_TOP + 9), (x0 - 1, G - 12)):
        a[yy - oy, xx - ox, :3] = ip[7]                                            # 钉帽
    up.barnacles(a, [(x0 + 3 - ox, G - 4 - oy), (x0 + 8 - ox, G - 3 - oy)])
    o.f[0].paste(a, 0, 0)
    # ---- open：门轴在 x0（门洞的大厅那沿），门板往左转出来
    hx, fx = x0, x0 - 23
    P = up.Prop(w, h, ox, oy, seed=212)
    R = P.R
    top = lambda X: DOOR_TOP + 1 - 2.0 * (hx - X) / (hx - fx)
    bot = lambda X: G - 1 + 1.0 * (hx - X) / (hx - fx)
    leaf = ua.poly_mask([(fx - ox, top(fx) - oy), (hx - ox, top(hx) - oy), (hx - ox, bot(hx) - oy + 1),
                         (fx - ox, min(G - oy, bot(fx) - oy + 1))], h, w)
    edges = [fx, fx + 6, fx + 12, fx + 18, hx]
    for a_, b_ in zip(edges[:-1], edges[1:]):
        P.fill(leaf & R(a_, 0, b_, 300), up.WOOD, 2.2, "v", round_=0.4)
    P.fill(leaf & R(fx, 0, fx + 1, 300), up.WOOD, 2.9, "v")                       # 门板的厚度：外沿一格
    for (t0, frac_) in ((DOOR_TOP + 9, 0.0), (G - 12, 1.0)):
        for X in range(fx + 1, hx):
            u = (hx - X) / (hx - fx)
            Y = int(round(t0 + (top(X) - top(hx)) * (1 - frac_) + (bot(X) - bot(hx)) * frac_))
            P.fill(R(X, Y, X + 1, Y + 2), up.IRON, 3.0, None)
            P.rust[R(X, Y, X + 1, Y + 2)] += 0.3
    rx, ry = fx + 4, DOOR_TOP + 30
    P.fill(R(rx, ry, rx + 3, ry + 1) | R(rx, ry + 4, rx + 3, ry + 5) | R(rx - 1, ry + 1, rx, ry + 4) |
           R(rx + 3, ry + 1, rx + 4, ry + 4), up.IRON, 3.2, None)                 # 拉环（正面看是一个圈）
    P.moss[leaf & R(fx, G - 6, hx, G + 2)] += 0.5
    a = P.render(env=env_for(ox, oy, w, h, 0.4), ambient=0.38, gain=0.6)
    o.f[1].paste(a, 0, 0)
    for X in range(fx - 1, hx + 1):
        if not o.f[1].a[G - oy, X - ox, 3]:
            o.put(1, X, G, up.DARKC[0])
    return o


def make_sluice():
    """旧泄水门：嵌在石框里的铁闸门。三块竖铁板（板缝凹下去），三道横筋（角铁：上沿受光、下面一道影子，一排铆钉），
    刷过的青灰漆掉了一大半，锈从下往上长、锈水从铆钉往下拖，门脚一排藤壶；右边一个大手轮（轮圈、四根辐条、轮毂，轴伸出来）。
    闸门上钉着一块操作记录板（木板 + 铁夹 + 泡皱的纸）。log = 记录板挂着；signatures = 最上面那张翻起来，露出下面一排签名；
    taken = 板子拿走了，铁板上留下一块干净一点的印子和那颗钉子。"""
    o = Obj(1262, 112, 70, 115, 3)
    X0, Y0, w, h = 1262, 112, 70, 115
    for k in range(3):
        P = up.Prop(w, h, X0, Y0, seed=221)
        R = P.R
        for (a_, b_) in ((0, 23), (24, 46), (47, 70)):
            P.fill(R(X0 + a_, Y0, X0 + b_, G), up.PAINT, 2.0, None, round_=0.4)
        P.fill(R(X0 + 23, Y0, X0 + 24, G) | R(X0 + 46, Y0, X0 + 47, G), up.IRON, 0.8, None, dark=0.1)   # 板缝
        for ry in (18, 56, 94):
            P.fill(R(X0, Y0 + ry, X0 + w, Y0 + ry + 3), up.IRON, 3.3, None)                            # 横筋
            P.dark[R(X0, Y0 + ry + 3, X0 + w, Y0 + ry + 5)] += 0.06                                     # 横筋下面的影子
            for xx in range(X0 + 3, X0 + w - 2, 6):
                if up.hsh(xx, ry) < 0.4:                                                                  # 只有几颗铆钉往下拖锈水
                    P.drip(xx, Y0 + ry + 3, 3 + int(up.hsh(ry, xx) * 12), 0.8)
        fy = np.clip((P.yy + Y0 - (G - 26)) / 26.0, 0, 1)                                                # 门脚：锈往上渐渐少
        P.rust += 0.5 * fy ** 1.5
        rng = np.random.default_rng(222)
        for _ in range(14):                                                                              # 掉漆的大块
            cx_, cy_ = int(rng.integers(X0, X0 + w)), int(rng.integers(Y0, G))
            P.rust[R(cx_, cy_, cx_ + int(rng.integers(2, 6)), cy_ + int(rng.integers(1, 4)))] += 0.6
        # 手轮
        cx, cy, r = 1318, 150, 8
        yy, xx = P.yy + Y0 + 0.5, P.xx + X0 + 0.5
        d = np.hypot(xx - cx, yy - cy)
        ring = (d >= r - 1.2) & (d < r + 0.6)
        P.fill(ring, up.IRON, 4.4, None)
        P.hf[ring] += 0.6 * np.cos((d[ring] - (r - 0.3)) * 2.5)
        for t in (0.4, 0.4 + math.pi / 2, 0.4 + math.pi, 0.4 + 3 * math.pi / 2):
            ux, uy = math.cos(t), math.sin(t)
            along = (xx - cx) * ux + (yy - cy) * uy
            perp = np.abs(-(xx - cx) * uy + (yy - cy) * ux)
            P.fill((perp < 0.7) & (along > 1.5) & (along < r - 1), up.IRON, 4.0, None)
        P.fill(d < 2.0, up.IRON, 4.8, None)
        P.dark[(d >= r + 0.6) & (d < r + 2.2) & (yy > cy)] += 0.06                                       # 轮圈在门上的影子
        P.rust[ring & (yy > cy + 3)] += 0.3
        # 记录板
        bx, by = 1274, 142
        if k < 2:
            P.fill(R(bx, by, bx + 14, by + 18), up.WOOD, 3.0, "v", round_=0.4)
            P.fill(R(bx + 4, by, bx + 10, by + 2), up.IRON, 4.0, None)                                     # 夹子
            s0 = by + 2 if k == 0 else by + 9
            m = R(bx + 2, s0, bx + 12, by + 17)
            P.fill(m, up.PAPER, 3.4, None)
            P.nomoss[m] = True
            P.tint[m] = 1
            if k == 1:                                                                                    # 翻起来那张（背面）
                m2 = R(bx + 1, by - 5, bx + 13, by + 9)
                P.fill(m2, up.PAPER, 4.0, None)
                P.nomoss[m2] = True
                P.tint[m2] = 0
                P.dark[R(bx + 1, by - 5, bx + 13, by - 3)] += 0.08
        a = P.render(env=env_for(X0, Y0, w, h, 0.3), ambient=0.29, gain=0.6, moss_amt=0.8)
        up.barnacles(a, [(xx_ - X0, G - 2 - Y0 - (xx_ % 3)) for xx_ in range(X0 + 2, X0 + w - 2, 5)])
        ip = up.PAL[up.IRON][1]
        for ry in (18, 56, 94):                                                                          # 横筋上的一排铆钉
            for xx in range(X0 + 3, X0 + w - 2, 6):
                if not (1306 <= xx <= 1330 and Y0 + ry < 162 and Y0 + ry > 138):
                    a[ry + 1, xx - X0, :3] = ip[7]
                    a[ry + 2, xx - X0, :3] = ip[3]
        o.f[k].paste(a, 0, 0)
        ink = up.PAL[up.PAPER][1][3]
        o.put(k, bx + 7, by - 2 if k < 2 else by, up.PAL[up.IRON][1][7])                                  # 钉子
        if k == 0:
            r2 = np.random.default_rng(92)
            for i, Y in enumerate(range(by + 4, by + 16, 2)):                                              # 一行行的字
                for X in range(bx + 3, bx + 11 - (i * 3) % 4):
                    if r2.random() < 0.75:
                        o.put(k, X, Y, ink)
        elif k == 1:
            for i, Y in enumerate((by + 11, by + 14)):                                                     # 两个签名：连笔
                for X in range(bx + 3, bx + 11):
                    o.put(k, X, Y + int(round(math.sin(X * 1.3 + i) * 0.8)), ink)
        else:
            pl = up.PAL[up.PAINT][1]
            for Y in range(by, by + 18):                                                                   # 板子挂过的地方：干净一点的印子
                for X in range(bx, bx + 14):
                    if X in (bx, bx + 13) or Y in (by, by + 17):
                        o.put(k, X, Y, pl[5])
    return o


# ====================================================================== 其他层
def front_layer(st):
    """前景（scroll 1，在人前面）：塌掉的前墙只剩地上一排碎石（比晨的脚低）和左边一截断柱；近黑，顶上一格亮一档。"""
    img = Img(W, H)
    rng = np.random.default_rng(101)
    pal = FRONT
    # 左前角的断柱（一截截方石垒的）
    x0, x1 = 686, 698
    top = 152
    y = H
    while y > top:
        bh = int(rng.integers(9, 15))
        y0 = max(top, y - bh)
        for Y in range(y0, y):
            for X in range(x0 - (Y - y0 == 0), x1):
                lv = 1
                if Y == y0:
                    lv = 2 if X > x0 else 1
                elif X == x1 - 1:
                    lv = 2
                if Y == y - 1:
                    lv = 0
                img.put(X, Y, pal[lv])
        y = y0 - 1
        x0 += int(rng.integers(-1, 2))
    for X in range(686, 698):                            # 断口：参差、受光
        t = top - int(rng.integers(0, 4)) * (X % 3 == 0)
        img.put(X, t, pal[3])
    # 地上一排碎石（前墙塌下来的）
    x = OPEN + 10
    while x < W:
        bw_ = int(rng.integers(10, 26))
        bh = int(rng.integers(4, 11))
        if rng.random() < 0.8:
            for X in range(x, x + bw_):
                u = (X - x - (bw_ - 1) / 2) / (bw_ / 2)
                t = int(round(bh * max(0.0, 1 - u * u) ** 0.4))
                for k in range(t):
                    Y = H - 1 - k
                    lv = 0
                    if k == t - 1:
                        lv = 2 if u > -0.3 else 1
                    elif k == t - 2 and u > 0.2:
                        lv = 1
                    img.put(X, Y + 0, pal[lv])
        x += bw_ + int(rng.integers(-3, 10))
    return img


def kelp_front():
    """开阔那段的前景大叶子：原来的 front.png（scroll 1.4），只留镜头还在河床上时能看到的那段，进了仓库就没有了。"""
    wf = 480 + int(math.ceil((W - 480) * 1.4))
    src = np.asarray(Image.open(UW / "front.png").convert("RGBA"))
    out = np.zeros((src.shape[0], wf, 4), np.uint8)
    out[:, :900] = src[:, :900]
    return out


def bed_weeds(st):
    """河床上一丛丛矮水草（会摆）：开阔那段 = 原来的 bedweeds.png；仓库里只在受光的墙角、塌口下面长几丛。"""
    src = tile_from(UW / "bedweeds.png", W)
    src[:, OPEN - 12:] = 0
    lay = Img(W, ua.BED_H)
    lay.a[:] = src
    pal = ua.bramp(4, .07, .2, 262, 248)
    rng = np.random.default_rng(111)
    for cx, n in ((656, 4), (720, 6), (744, 3), (1104, 5), (1134, 4), (1336, 3)):
        for _ in range(n):
            x = cx + rng.uniform(-6, 6)
            root = G + 2 - ua.BED_Y
            hgt = rng.uniform(4, 20)
            lean = rng.uniform(-0.3, 0.2)
            bend = rng.uniform(-3, 1)
            for s in range(int(hgt)):
                f = s / hgt
                xi = int(round(x + lean * s + bend * f * f))
                yi = root - s
                if 0 <= yi < ua.BED_H and 0 <= xi < W:
                    c = pal[3] if f > 0.85 else (pal[2] if f > 0.5 else (pal[1] if f > 0.15 else pal[0]))
                    lay.a[yi, xi] = rgba(c)
    return lay


WEEDS_Y = 96
def tall_weeds(st):
    """仓库里塌了顶的地方长上来的长水草（会摆，scroll 1）：大厅左角两三根、屋角塌口下面一根。贴图底边 = 根。"""
    h = G + 2 - WEEDS_Y
    img = np.zeros((h, W, 4), np.uint8)
    pal = ua.bramp(5, .06, .2, 264, 248)
    rng = np.random.default_rng(121)
    for x, hh, w0 in ((724, 74, 2.5), (733, 98, 3.0), (741, 52, 2.0), (1112, 66, 2.5), (1121, 42, 2.0)):
        ua.ribbon(img, x, h - 1, hh, rng, pal, w0=w0, current=-1.0)
    lay = Img(W, h)
    lay.a[:] = img
    return lay


def shafts_layer(st):
    """静的光柱（层 alpha 0.12）：月光从塌顶 / 屋角塌口照进来、落在后墙和地上的那一片，用光照算出来的，所以和石头的明暗对得上。"""
    img = Img(W, H)
    L = st.light
    bay = np.tile(BAYER, (H // 4 + 1, W // 4 + 1))[:H, :W]
    behind = st.back | st.cave
    behind[:, :BACK[0]] = False
    q = L + (bay - 0.5) * 0.12
    for k, th in enumerate((0.5, 0.72, 0.9)):
        m = behind & (q > th)
        img.a[m] = rgba(LIGHTC[k])
    return img


def bed_light(st):
    """主层的焦散遮罩（scripts/river_uw_fx.gd 用 underwater_caustics.gdshader 画）：开阔那段 = 原来的 bedlight.png；
    仓库里是受光的地面那一行、屋顶 / 墙头 / 巨石的顶。r 通道 = 强度。"""
    src = tile_from(UW / "bedlight.png", W)
    src[:, OPEN - 6:] = 0
    lay = Img(W, H)
    lay.a[:] = src
    for x in range(OPEN, W):
        Lx = st.light[G - 2, x]
        if Lx > 0.35:
            v = int(255 * min(1.0, Lx))
            lay.a[G, x] = (v, v, v, 255)
            lay.a[G + 1, x] = (v // 2, v // 2, v // 2, 255)
    tops = st.sect | st.rock
    for x in range(LW[0], W):
        ys = np.nonzero(tops[:, x])[0]
        if len(ys):
            lay.a[ys[0], x] = (200, 200, 200, 255)
    return lay


# ====================================================================== room.json
def room_json(objs):
    def layer(id_, img, scroll, y=0, **kw):
        d = {"id": id_, "img": img, "scroll": scroll, "y": y}
        d.update(kw)
        return d
    sway = lambda amp, speed, wl, pw, bend: {"amp": amp, "speed": speed, "wavelength": wl, "power": pw, "bend": bend}
    layers = [
        layer("deep", "res://art/underwater/deep.png", 0.0, z=-100),
        layer("distant", "res://art/underwater/distant.png", 0.05, tile=True, z=-98),
        layer("far", "res://art/underwater/far.png", 0.08, tile=True, z=-96),
        layer("midfar", "res://art/underwater/midfar.png", 0.17, tile=True, z=-94),
        layer("head", "res://art/underwater/head.png", 0.3, x=HEAD_X, tile=True, z=-92),
        layer("headweeds", "res://art/underwater/headweeds.png", 0.3, x=HEAD_X, y=ua.HW_Y, tile=True, z=-90,
              shader="sway", shader_params=sway(2.0, 0.55, 120.0, 1.4, 0.12)),
        layer("kelp", "res://art/underwater/kelp.png", 0.52, y=ua.KELP_Y, tile=True, z=-86,
              shader="sway", shader_params=sway(4.0, 0.5, 160.0, 1.7, 0.05)),
        layer("main", "main.png", 1.0, z=-80),
        layer("weeds", "weeds.png", 1.0, y=WEEDS_Y, z=-79, shader="sway", shader_params=sway(3.0, 0.5, 140.0, 1.6, 0.08)),
        layer("bedweeds", "bedweeds.png", 1.0, y=ua.BED_Y, z=-78, shader="sway",
              shader_params=sway(2.0, 0.6, 120.0, 1.3, 0.12)),
        layer("shafts", "shafts.png", 1.0, alpha=0.12, z=-15),
        layer("front", "front.png", 1.0, front=True),
        layer("kelpfront", "kelpfront.png", 1.4, y=ua.FRONT_Y, front=True, shader="sway",
              shader_params=sway(6.0, 0.42, 240.0, 1.6, 0.03)),
    ]
    markers = {
        "warehouse_entry": 40, "warehouse_niff": 72, "warehouse_rope": 40, "warehouse_exit_light": 38,
        "warehouse_boxes": 798, "warehouse_broken_box": 862, "warehouse_float": 934,
        "warehouse_cabinet_foot": 978, "warehouse_tall_cabinet": 1012, "warehouse_cabinet_top": 1050,
        "warehouse_furniture": 1066, "warehouse_inner_door": 1093, "warehouse_knot_1": HOOKS[2],
        "warehouse_knot_2": HOOKS[3], "warehouse_cabinet": (EQUIP[0] + EQUIP[1]) // 2, "warehouse_sluice_door": 1296,
    }
    O = {}

    def obj(id_, o, **kw):
        d = {"x": o.x, "y": o.y, "w": o.w, "h": o.h, "frames": o.n}
        d.update(kw)
        O[id_] = d
    cab, fur, flo = objs["cabset"]
    obj("warehouse_float", flo, z=-1, click=[920, 180, 22, 24], ms=700,
        states={"default": [0, 1], "idle": [0, 1], "tied_warehouse_cabinet_top": 2, "tied_warehouse_cabinet_foot": 3,
                "held": 4})
    obj("warehouse_tall_cabinet", cab, z=-2, click=[978, 176, 64, 44],
        states={"default": 0, "fallen": 0, "lifted": 1, "tilt_wrong": 2})
    obj("warehouse_furniture", fur, z=-3, click=[1048, 188, 38, 38],
        states={"default": 0, "pinned": 0, "wiggle": 1, "loose": 2, "moved": 3})
    obj("warehouse_inner_door", objs["door"], z=-2, states={"default": 0, "closed": 0, "open": 1})
    obj("warehouse_exit_light", objs["exit"], ms=900, states={"default": [0, 1], "on": [0, 1]})
    obj("warehouse_broken_box", objs["broken"], states={"default": 0, "spilled": 1})
    obj("warehouse_knot_1", objs["knot1"], states={"default": 0, "lit": 1})
    obj("warehouse_knot_2", objs["knot2"], states={"default": 0, "lit": 1})
    obj("warehouse_sluice_door", objs["sluice"], states={"default": 0, "log": 0, "signatures": 1, "taken": 2})
    return {
        "_note": "tools/river_underwater_art.py 生成，别手改。约定见 docs/river_rooms_contract.md。"
                 "0..690 是作者原来的水底（art/underwater 原图 + scripts/river_uw_fx.gd 照 underwater_test.tscn 搭的动效），"
                 "690..1360 是泡在水底的半塌石头仓库。origin 让入口正好在旧街仓库入口（1066）的正下方；下水 / 上水是渐黑渐亮（story_runner._dive_fade）。"
                 "仓库里的家具、铁器、绳、纸用 tools/uw_props.py 的材质画法画（10-30 重画）。",
        "size": [W, H],
        "origin": [3000 + 1066 - 40, 270],
        "env": "underwater",
        "bg": ["#16242b", "#0d161b"],
        "layers": layers,
        "ground": ground_poly(),
        "markers": markers,
        "walk": [24, 1330],
        "walk_when": [{"prop": "warehouse_inner_door=closed", "walk": [24, PART[0] - 6]}],
        "rope": {"prop": "warehouse_rope", "on": "on", "anchor": [POST[1] + 1, ROPE_Y], "end": 1326,
                 "color": "#66737a", "knots": [HOOKS[2], HOOKS[3]]},
        "portals": [{"to": "oldstreet", "at": "oldstreet_warehouse_entry", "kind": "pan_up", "x": 40}],
        "ambient": [{"name": "underwater", "db": -8}],
        "scripts": [
            {"script": "res://scripts/underwater_motes.gd", "x": 0, "y": 0, "z": -12,
             "params": {"count": 60, "area": [0, 40, W, 190]}},
            {"script": "res://scripts/river_uw_fx.gd", "x": 0, "y": 0, "z": 0,
             "params": {"head_x": HEAD_X, "bedlight": "res://art/river_city/warehouse/bedlight.png",
                        "pods": [[596, int(round(gy_out(596))) - 1, 2]], "bubbles": [[300, 225], [1120, 224], [1330, 224]],
                        "warm": [[38, 156]]}},
        ],
        "objects": O,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    st = Struct()
    set_env(st)
    build_main(st).save(OUT / "main.png")
    front_layer(st).save(OUT / "front.png")
    Image.fromarray(kelp_front()).save(OUT / "kelpfront.png")
    bed_weeds(st).save(OUT / "bedweeds.png")
    tall_weeds(st).save(OUT / "weeds.png")
    shafts_layer(st).save(OUT / "shafts.png")
    bed_light(st).save(OUT / "bedlight.png")
    objs = {"exit": make_exit_light(), "knot1": make_knot(HOOKS[2]), "knot2": make_knot(HOOKS[3]),
            "broken": make_broken_box(), "cabset": make_cabinet_set(), "door": make_inner_door(),
            "sluice": make_sluice()}
    names = {"exit": "warehouse_exit_light", "knot1": "warehouse_knot_1", "knot2": "warehouse_knot_2",
             "broken": "warehouse_broken_box", "door": "warehouse_inner_door", "sluice": "warehouse_sluice_door"}
    for k, n in names.items():
        Image.fromarray(objs[k].sheet()).save(OUT / f"{n}.png")
    cab, fur, flo = objs["cabset"]
    Image.fromarray(cab.sheet()).save(OUT / "warehouse_tall_cabinet.png")
    Image.fromarray(fur.sheet()).save(OUT / "warehouse_furniture.png")
    Image.fromarray(flo.sheet()).save(OUT / "warehouse_float.png")
    room = room_json(objs)
    (OUT / "room.json").write_text(json.dumps(room, ensure_ascii=False, indent=1))
    print("warehouse ok", OUT)


if __name__ == "__main__":
    main()
