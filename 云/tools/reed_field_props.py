#!/usr/bin/env python3
"""芦苇地（reed_field）上第三章结局一（西半边 yard_*）、结局二（东半边 east_*）用的物件。

跑：「AI Oscar/.venv/bin/python tools/reed_field_props.py [--preview DIR]」
写 art/reed_field/props/*.png 和 props/objects.json，并把 objects 填进 art/reed_field/room.json
（reed_field_art.py 重出 room.json 时也读 props/objects.json，不会丢）。

和芦苇地同一套画法：颜色只用第十一版画面里已有的（最后有检查），不比第十一版深；左上受光；
立在浅水里的东西底下一道贴水的暗边 + 压扁的倒影（两档，按行分，不逐格换）。100ms 一帧（静物只有状态帧）。
飞船是作者的原图（art/level1/ship_lift.png 第 17 帧，和云上小镇 ship_parked.png 同一块），一个像素都不改色：
结局二落地时左边支架坏了 → 整条船按列往左（机头）斜 4 像素、机头那头多沉进水里；居民扶起来（wing_up）= 摆平。

物件（剧本 data/story_final.json 的 prop）：
  yard_ship      结局一停在落地点的飞船（剧本没 prop 它；只在 final_ending_1 时出现，见 reed_field.gd 的 need）
  yard_toolbag   结局一落地放在手边的工具包（placed）
  yard_stone     水边那块湿土（平时就在）；种完种子压一块小石头（placed）
  east_plane     结局二的飞船：默认左边支架坏了往左斜；wing_up = 居民扶起来摆平（只在 final_ending_2 时出现）
  east_toolbag   结局二夜里收拾好的工具包（ready：开着口、扳手放在旁边）
  east_tree      结局二大象蹭树的那棵 = 第二棵大树（BIGTREES 1580）；bark_rubbed = 树干上被蹭亮的一块（平时透明）
  east_bed       居民围起来的花圃（两头开花、中间空着）；planted = 中间一个湿土包 + 小芽
  east_water_cup 居民留下的一杯水（placed）
  sky            纯剧情状态（day / dusk / night / shadow_pass），1×1 空图
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reed_field_art as R  # noqa: E402

ROOT = R.ROOT
OUT = R.OUT / "props"
REL = "props/"

# ---------------------------------------------------------------- 颜色（都在第十一版画面里）
STEM = ["#e0cb6c", "#dcc66a", "#d5ba52", "#cfb34c"]        # 芦苇秆 / 蒲棒的黄棕：受光 → 背光
SEAM = "#cab04a"                                           # 包上的缝、包口里头
ROCK = R.ROCK_TONES                                        # 石头：奶白、淡灰黄、淡青灰、背光青灰
MUD = ["#c0d8c0", "#acccbd", "#9ec5b8", "#88b4a7"]          # 湿土（透出水底的沙那几档 + 树干背光）：受光 → 最湿
LEAF = ["#cbe39c", "#b8d98a", "#a6cf7c", "#93c47a"]          # main 草丛的绿
FLOWER = ["#fffef6", "#fef3bf", "#bae2f3"]                 # 小白花、奶黄、淡蓝
FLOWER_EYE = "#ecc23e"
BED_FLOWER = ["#93cbec", "#fffef6", "#93cbec"]             # 花圃的花：芦苇穗背光的淡蓝为主、夹白的（后面是黄草，奶黄的花看不出来）
WATER_IN = ["#93cbec", "#a6cde5"]                          # 杯子里的水
WET = "#88b4a7"                                            # 贴水的那一道暗边
REFL = ["#a5d3a8", "#c0e0b9"]                              # 浅色东西的倒影（草丛倒影那两档，水面那一行的水色混进去）
SHIP_REFL = ["#9ec5b8", "#acccbd"]                         # 飞船的倒影：深一档、浅一档（青灰，不比第十一版深）
BARK_RUB = {"#9ec5b8": "#acccbd", "#acccbd": "#c0d8c0", "#c0d8c0": "#cddbd5"}   # 被蹭过的树皮亮一档


def hx(c):
    return R.hexc(c)


def put(img, x, y, c):
    if 0 <= y < img.shape[0] and 0 <= x < img.shape[1]:
        img[y, x] = hx(c) if isinstance(c, str) else c


def from_rows(rows, key):
    """一张手排的小图：每行一个字符串，key = {字符: 颜色}，'.' 透明"""
    h, w = len(rows), max(len(r) for r in rows)
    img = R.blank(w, h)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != ".":
                img[y, x] = hx(key[ch])
    return img


def reflect(img, base, tones, k=0.5, maxlen=6, edge=WET, solid=False):
    """img 的第 base 行是贴水的那一行：下面一行一道暗边（只在贴着水的那几列），再往下是压扁 k 的倒影（前一半深、后一半浅）"""
    h, w = img.shape[:2]
    src = img[:base + 1].copy()
    a = src[..., 3] > 0
    touch = [x for x in range(w) if a[base, x]]
    rh = 0
    for x in range(w):
        ys = np.nonzero(a[:, x])[0]
        if not len(ys):
            continue
        for d in range(1, maxlen + 1):
            sy = base - int((d - 1) / k)
            if sy < 0:
                break
            if a[sy, x] and base + d < h:
                img[base + d, x] = hx(tones[0] if d <= max(1, maxlen * 0.45) else tones[1])
                rh = max(rh, d)
    if solid:                                       # 一排小桩的倒影连成一整片（不然是一排点，像虚线）
        for d in range(1, rh + 1):
            xs = np.nonzero(img[base + d, :, 3] > 0)[0]
            if len(xs):
                img[base + d, xs.min():xs.max() + 1] = hx(tones[0] if d <= max(1, maxlen * 0.45) else tones[1])
        touch = list(range(min(touch), max(touch) + 1)) if touch else touch
    for x in touch:
        if base + 1 < h:
            img[base + 1, x] = hx(edge)
    return rh


def clean(img):
    for f in (R.corner_fix, R.speck_fix, R.corner_fix, R.alpha_fix):
        f(img)
    R.edge_diag_fill(img)
    R.speck_fix(img)
    R.corner_fix(img)
    return img


# ---------------------------------------------------------------- 飞船（作者原图）
SHIP_SINK = 2            # 肚子沉进水里几行
SHIP_TILT = 4            # 支架坏了：机头那头往下斜几像素
SHIP_REFL_H = 14


# 作者原图是很深的灰黑（最深亮度 12），在芦苇地里比第十一版深得多、比晨还抢眼。SHIP_RECOLOR = True：形状、每一格的位置一点不动，
# 只把 15 个颜色按明暗一对一换成第十一版已有的颜色（船身 → 树干 / 水底沙那几档青灰，舷窗玻璃 → 芦苇穗背光的淡蓝，
# 紫色腰线 → 淡蓝，橙色小灯 → 蒲棒的黄）。False = 用作者的原色（和云上小镇一样）。
SHIP_RECOLOR = True
SHIP_MAP = {
    "#0b0c0f": "#88b4a7", "#15161a": "#88b4a7", "#1c2125": "#9ec5b8", "#24242a": "#9ec5b8", "#222a2f": "#acccbd",
    "#2a3338": "#b6d2c0", "#333c40": "#c0d8c0", "#3d4548": "#cddbd5", "#587077": "#e4e2cd",
    "#0a1416": "#7fb8de", "#142a2c": "#8cc3e3",
    "#33203a": "#93cbec", "#45293f": "#a6cde5",
    "#7a3420": "#cfb34c", "#c06a2c": "#ecc23e",
}


def ship_src(recolor=None):
    im = np.asarray(Image.open(ROOT / "art/level1/ship_lift.png").convert("RGBA"))[:, 17 * 204:18 * 204][0:120]
    im = im[23:77, 32:174].copy()
    if SHIP_RECOLOR if recolor is None else recolor:
        for y, x in zip(*np.nonzero(im[..., 3])):
            im[y, x, :3] = hx(SHIP_MAP["#%02x%02x%02x" % tuple(im[y, x, :3])])[:3]
    return im


def ship_frames(recolor=None):
    s = ship_src(recolor)
    sh, sw = s.shape[:2]
    base = sh - 1 - SHIP_SINK                 # 水面那一行（帧里）
    H = base + 1 + SHIP_REFL_H
    frames = []
    for tilt in (0, SHIP_TILT):
        f = R.blank(sw, H)
        def dyc(c):
            return int(round(tilt * (sw - 1 - c) / (sw - 1))) if 0 <= c < sw else 0   # 第 0 列是机头（左），斜最多
        for c in range(sw):
            dy = dyc(c)
            # 台阶那一列（右边一列少沉一格）先往上多画一格：横线在台阶处竖着接上，不成只有对角相连的断口
            for d in ((dy - 1, dy) if dy > dyc(c + 1) else (dy,)):
                for y in range(sh):
                    if s[y, c, 3] and 0 <= y + d <= base:
                        f[y + d, c] = s[y, c]
        for c in range(sw - 1):                   # 台阶处颜色线的拐角：只有对角相连的那一格补成线的颜色（只动台阶那几列）
            if dyc(c) > dyc(c + 1):
                for t in range(1, base):
                    k = tuple(f[t + 1, c])
                    if f[t + 1, c, 3] and tuple(f[t, c + 1]) == k and tuple(f[t, c]) != k and tuple(f[t + 1, c + 1]) != k:
                        f[t, c] = f[t + 1, c]
                    k2 = tuple(f[t, c])
                    if f[t, c, 3] and tuple(f[t + 1, c + 1]) == k2 and tuple(f[t, c + 1]) != k2 and tuple(f[t + 1, c]) != k2:
                        f[t + 1, c] = f[t, c]
        reflect(f, base, SHIP_REFL, k=0.42, maxlen=SHIP_REFL_H)
        frames.append(f)
    return frames, base


# ---------------------------------------------------------------- 工具包
BAG_KEY = {"L": STEM[0], "B": STEM[2], "b": STEM[1], "S": STEM[3], "K": SEAM, "W": ROCK[0], "w": ROCK[2], "v": ROCK[3]}
BAG_CLOSED = [                     # 一只帆布工具包：上口一道铁框、提手，前面一道口袋缝；左上受光
    ".....SSSSSS........",
    ".....SS..SS........",
    "....WWWWWWWWWW.....",
    "...LLLLLLLLLLLB....",
    "..LLbbbbbbbbbbBS...",
    "..LbbbbbbbbbbBBS...",
    "..LbbKKKKKKKbBBS...",
    "..LbbbbbbbbbbBBS...",
    "...SSSSSSSSSSSSS...",
]
BAG_OPEN = [                       # 开着口（铁框往两边张开、露出里头），扳手平放在旁边（头朝左）
    "...................",
    "..WW.........WW....",
    "...WWKKKKKKKWW.....",
    "...LKKKKKKKKKBB....",
    "..LLbbbbbbbbbbBS...",
    "..LbbbbbbbbbbBBS...",
    "..LbbKKKKKKKbBBS........",
    "..LbbbbbbbbbbBBS..W.W...",
    "...SSSSSSSSSSSSS..WWWwww",
]


def toolbag():
    out = []
    for rows in (BAG_CLOSED, BAG_OPEN):
        img = from_rows(rows, BAG_KEY)
        f = R.blank(img.shape[1] + 6, img.shape[0] + 4)
        f[:img.shape[0], :img.shape[1]] = img
        reflect(f, img.shape[0] - 1, REFL, k=0.5, maxlen=3)
        out.append(f)
    return out, len(BAG_CLOSED) - 1


# ---------------------------------------------------------------- 水杯
CUP = [                            # 居民的搪瓷杯：一圈奶白杯口、里头的水、右边把手
    ".LLLL..",
    ".LwwS..",
    ".LBBSSS",
    ".LBBS.S",
    ".LBBSSS",
    ".LBBS..",
    ".SSSS..",
]
CUP_KEY = {"L": ROCK[0], "B": ROCK[1], "S": ROCK[2], "w": WATER_IN[0]}


def cup():
    img = from_rows(CUP, CUP_KEY)
    f = R.blank(img.shape[1] + 2, img.shape[0] + 3)
    f[:img.shape[0], :img.shape[1]] = img
    reflect(f, img.shape[0] - 1, REFL, k=0.5, maxlen=2)
    return f, img.shape[0] - 1


# ---------------------------------------------------------------- 湿土 + 小石头（结局一种种子的地方）
def mound(img, x0, x1, base, hgt, tones):
    """贴水的一小块土：中间高、两头收，上沿一道受光，往下一档档湿"""
    for x in range(x0, x1 + 1):
        u = (x - x0) / max(1, x1 - x0)
        hh = int(round(hgt * (1 - abs(2 * u - 1) ** 2.2)))
        for d in range(hh + 1):
            y = base - d
            c = tones[0] if d == hh and u < 0.7 else tones[1] if d >= hh - 1 else tones[2]
            if d == 0:
                c = tones[3] if u > 0.5 else tones[2]
            put(img, x, y, c)


def soil_frames():
    W_, H_ = 34, 14
    base = 9
    frames = []
    for planted in (False, True):
        f = R.blank(W_, H_)
        mound(f, 2, 31, base, 4, MUD)
        for (sx, hgt, lean) in ((4, 4, -1), (6, 6, 0), (29, 5, 1)):          # 土边上两三根草
            for d in range(hgt):
                put(f, sx + (lean if d >= hgt - 2 else 0), base - 2 - d, LEAF[2] if d < hgt - 2 else LEAF[1])
        if planted:
            mound(f, 11, 23, base - 3, 2, [MUD[1], MUD[2], MUD[3], MUD[3]])      # 拍实的新土（更湿一档）
            stone = from_rows(["...LLB...", ".LLLBBBS.", "LLBBBBBSv", "BBBBBSSSv", ".BSSSSvv."],
                              {"L": ROCK[0], "B": ROCK[1], "S": ROCK[2], "v": ROCK[3]})
            sy, sx = base - 3 - 5, 13
            m = stone[..., 3] > 0
            f[sy:sy + 5, sx:sx + 9][m] = stone[m]
        reflect(f, base, REFL, k=0.5, maxlen=3)
        frames.append(clean(f))
    return frames, base


# ---------------------------------------------------------------- 花圃（居民围起来的）
def flower(img, x, y, c, eye=True):
    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
        put(img, x + dx, y + dy, c)
    put(img, x, y, FLOWER_EYE if eye else c)


SOIL_H = 6               # 花圃里垫高的土有几行（两道绳中间露出来）
FENCE_H = 9              # 小桩多高（最上面一格是削尖的亮头）


def bed_frames():
    """手排，不过 corner_fix 那些清理（会动手排的格子）；围栏里头一整块土，绳从桩前面一整道过去"""
    W_, H_ = 64, 36
    base = 29
    x0, x1 = 4, 59
    frames = []
    MID = (x0 + x1) // 2
    rng = np.random.default_rng(1919)
    stems = []
    for side in (0, 1):                          # 两头各一丛花（三棵，隔 4–5 格），中间空着
        for i in range(4):
            sx = (x0 + 5 + i * 5 - int(rng.integers(0, 2))) if side == 0 else (x1 - 5 - i * 5 + int(rng.integers(0, 2)))
            stems.append((sx, int(rng.integers(10, 18)), BED_FLOWER[(i + side * 2) % 3]))
    for planted in (False, True):
        f = R.blank(W_, H_)
        for x in range(x0, x1 + 2):              # 土
            for d in range(SOIL_H):
                put(f, x, base - d, MUD[1] if d >= 2 else MUD[3])
        top = base - SOIL_H
        for k, (sx, hgt, fc) in enumerate(stems):  # 花：秆、一片斜叶（左右交替、高低不同）、花头
            for d in range(hgt):
                put(f, sx, top - d, LEAF[3])
            side, lh = (-1 if k % 2 else 1), 3 + (k * 3) % max(1, hgt - 6)
            posts = {c for px in range(x0, x1 + 1, 6) for c in (px, px + 1)}
            if lh <= FENCE_H - SOIL_H + 1 and ({sx + side, sx + 2 * side} & posts):
                side = -side                         # 叶子别搭在小桩尖上
            put(f, sx + side, top - lh, LEAF[2])
            put(f, sx + 2 * side, top - lh - 1, LEAF[2])
            put(f, sx + 2 * side, top - lh, LEAF[2])
            flower(f, sx, top - hgt, fc, eye=False)
        if planted:                                  # 中间一个拍实的湿土包 + 一棵小芽
            for x in range(MID - 4, MID + 5):
                u = abs(x - MID) / 4.5
                for d in range(1 if u > 0.6 else 2):
                    put(f, x, top - d, MUD[2] if d == 0 else MUD[3])
            for d in range(5):
                put(f, MID, top - 2 - d, LEAF[2] if d < 2 else LEAF[1])
            for (dx, dy, c) in ((-1, -6, LEAF[0]), (-2, -6, LEAF[0]), (-2, -7, LEAF[0]), (1, -6, LEAF[1]), (2, -6, LEAF[1]), (2, -7, LEAF[1])):
                put(f, MID + dx, top + dy, c)
        for px in range(x0, x1 + 1, 6):           # 小桩：两格宽，左亮右暗；上面那道绳以上整截亮一档、右边矮一格（削尖）
            for d in range(2, FENCE_H + 1):           # 插在土里：最下面一行是土（贴水的暗边连成一整条），下面那道绳贴着土
                top_part = base - d < base - SOIL_H
                put(f, px, base - d, STEM[0] if top_part else STEM[1])
                if d < FENCE_H:
                    put(f, px + 1, base - d, STEM[3])
        for x in range(x0, x1 + 2):                 # 两道绳，从桩前面一整道过去
            put(f, x, base - SOIL_H, STEM[2])         # 上面那道贴着土的上沿（花秆从绳上面露出来）
            put(f, x, base - 1, STEM[2])
        reflect(f, base, REFL, k=0.5, maxlen=4, solid=True)
        frames.append(f)
    return frames, base


# ---------------------------------------------------------------- 大树上被蹭亮的一块树皮
TREE_PATCH = (1572, 132, 26, 22)          # 房间坐标的框：x, y, w, h（第二棵大树的树干，草上面露出来的那一截）


def tree_frames():
    big = np.asarray(Image.open(R.OUT / "bigtrees.png").convert("RGBA"))
    x, y, w, h = TREE_PATCH
    crop = big[y:y + h, x:x + w]
    on = R.blank(w, h)
    cx, cy, rx, ry = w / 2 + 1, h / 2, 7.5, 5.5
    for j in range(h):
        for i in range(w):
            if crop[j, i, 3] == 0:
                continue
            c = "#%02x%02x%02x" % tuple(crop[j, i, :3])
            if c in BARK_RUB and ((i + 0.5 - cx) / rx) ** 2 + ((j + 0.5 - cy) / ry) ** 2 <= 1:
                on[j, i] = hx(BARK_RUB[c])
    for f in (R.corner_fix, R.speck_fix, R.corner_fix):
        f(on)
    return [R.blank(w, h), on]


# ---------------------------------------------------------------- 中景的树（v18）
# 作者：「树只有两种：和晨同一层的大树、很远的小树丛，中间缺一档」。在 mid（0.35）、isles（0.62）两层的小洲上加几棵：
# 和大树同一个画法（一层层伞形的叶、很多小叶团平涂、受光只在每层上沿、垂叶），按 s 缩小，叶团半径跟着缩、垂叶更少更短；
# 颜色只用那一层图里已有的（越远越淡、越偏冷）。每层一张不 tile 的图（宽 = 480 + 1440 × 视差），视差和那层一样，
# 放在那层后面（z 比它小 1）：树根被洲上的草和水面挡住，看着就是长在洲上的。
TREE_PAL = {
    "isles": {"leaf": ["#deedbf", "#c2de9f", "#b3d694", "#a4cd92"], "inner": ["#c6e2c7", "#c0e0c4", "#add6b8", "#9ecab5"],
              "bark": ["#c6e2c7", "#add6b8", "#9ecab5"]},
    "mid": {"leaf": ["#e1efcd", "#cce4b6", "#c2deae", "#b7d8ac"], "inner": ["#d0e8cc", "#cae5ca", "#b7dcbc", "#b3d5c6"],
            "bark": ["#cae5ca", "#b7dcbc", "#b3d5c6"]},
}
# (层, 层里的 x, 缩放, 种子, 朝向)——都在那层的洲上（mid 洲：tile x 202–294、756–832；isles 洲：661–776）；一对一对、一棵单的，不等距
MIDTREES = [("mid", 222, 0.14, 21, 1), ("mid", 249, 0.10, 22, -1), ("mid", 762, 0.13, 23, -1),
            ("isles", 694, 0.24, 31, 1), ("isles", 725, 0.17, 32, -1)]
LAYER_FOR = {"mid": (R.MID_Y, R.MID_WT, 0.35, -85), "isles": (R.ISL_Y, R.ISL_WT, 0.62, -75)}


def tree_limb(img, p0, p1, w0, w1, tones):
    (x0, y0), (x1, y1) = p0, p1
    L = max(0.5, ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5)
    n = int(L * 2) + 2
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if nx > 0 or (nx == 0 and ny > 0):
        nx, ny = -nx, -ny
    H2, W2 = img.shape[:2]
    for i in range(n + 1):
        t = i / n
        cx, cy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        r = (w0 + (w1 - w0) * t) / 2
        for yy in range(int(cy - r - 1), int(cy + r + 2)):
            for xx in range(int(cx - r - 1), int(cx + r + 2)):
                ddx, ddy = xx + 0.5 - cx, yy + 0.5 - cy
                if not (0 <= yy < H2 and 0 <= xx < W2) or ddx * ddx + ddy * ddy > r * r:
                    continue
                sd = (ddx * nx + ddy * ny) / max(r, 0.5)
                img[yy, xx] = tones[0] if sd > 0.45 and r > 1.4 else tones[2] if sd < -0.35 else tones[1]


def mini_tree(s, seed, pal):
    """大树（reed_field_art.bigtree_sprite）缩小 s 倍的样子。返回 (图, 树干中心 x, 根那一行 y)"""
    rng = np.random.default_rng(seed)
    rs = max(0.34, s * 1.4)                       # 叶团半径缩多少（太小了就成噪点，留个下限）
    PW, PH = int(260 * s) + 14, int(290 * s) + 10
    ox, oy = PW // 2, PH - 3
    img = R.blank(PW, PH)
    bark = [hx(c) for c in pal["bark"]]
    for y in range(oy - int(158 * s), oy + 1):    # 树干
        h = (oy - y) / s
        hw = max(1.1, (12 + 6 * max(0, 1 - h / 40) ** 2 + 0.02 * max(0, 100 - h)) * s)
        c0 = ox - 0.04 * h * s
        for x in range(int(c0 - hw - 1), int(c0 + hw + 2)):
            d = (x + 0.5 - c0) / hw
            if abs(d) <= 1:
                img[y, x] = bark[0] if d < -0.55 else bark[2] if d > 0.4 else bark[1]
    for (tx, ty), w0, w1 in R.BIGTREE_LIMBS:      # 主枝
        sx, sy = ox + (-6 + tx * 0.12) * s, oy + max(ty + 40, -150) * s
        ex, ey = ox + tx * s, oy + ty * s
        mx, my = sx + (ex - sx) * 0.35, sy + (ey - sy) * 0.65
        a, b = max(1.2, w0 * s), max(1.0, w1 * s)
        tree_limb(img, (sx, sy), (mx, my), a, (a + b) / 2, bark)
        tree_limb(img, (mx, my), (ex, ey), (a + b) / 2, b, bark)
    shelf_id = np.full((PH, PW), -1)
    darker = {**dict(zip(pal["leaf"], pal["leaf"][1:] + pal["leaf"][-1:])), **dict(zip(pal["inner"], pal["inner"][1:] + pal["inner"][-1:]))}
    for k, (cx, t, b, hw) in enumerate(R.BIGTREE_SHELVES):
        cx, t, b, hw = ox + cx * s, oy + t * s, oy + b * s, hw * s
        H_ = b - t
        n = max(3, int(2 * hw * H_ * 0.7 / (38 * rs * rs)))
        lobes, tries = [], 0
        while len(lobes) < n and tries < n * 30:
            tries += 1
            u = rng.uniform(-1, 1)
            x = cx + u * hw
            ytop = t + H_ * 0.62 * abs(u) ** 1.7
            ybot = b + H_ * 0.12 * abs(u) ** 2
            r = (rng.uniform(3.2, 5.5) + 4.0 * (1 - abs(u)) * rng.uniform(0.3, 1.0)) * rs
            if ybot - ytop < 2 * r * 0.8:
                r = max(1.2, (ybot - ytop) / 2 * 0.9)
            y = rng.uniform(ytop + r * 0.85, max(ytop + r * 0.85, ybot - r * 0.85))
            lobes.append((x, y, r, (y - t) / H_ * 1.8 + rng.uniform(-0.4, 0.4)))
        cols = [hx(c) for c in (pal["inner"] if k < R.BIGTREE_N_INNER else pal["leaf"])]
        xa = int(min(l[0] - l[2] for l in lobes)) - 1
        xb = int(max(l[0] + l[2] for l in lobes)) + 2
        ya = int(min(l[1] - l[2] for l in lobes)) - 1
        yb = int(max(l[1] + l[2] for l in lobes)) + 2
        tone = R.leaf_tones(lobes, xa, ya, xb, yb, rng, cut=R.BIGTREE_CUT)
        rel = (np.arange(ya, yb)[:, None] - t) / max(1.0, H_)
        m = tone >= 0
        tone[m & (rel > 0.42) & (tone == 0)] = 1
        tone[m & (rel > 0.66) & (tone < 2)] = 2
        tone[m & (rel > 0.9)] = 3
        for j, i in zip(*np.nonzero(m)):
            yy, xx = ya + j, xa + i
            if 0 <= yy < PH and 0 <= xx < PW:
                img[yy, xx] = cols[tone[j, i]]
                shelf_id[yy, xx] = k
        # 垂叶：比大树少、短（隔得更开，长 2 ~ 13·s 格），两格宽、从这一层最下面一格接出去
        x = xa + int(rng.integers(2, 5))
        while x < xb - 2:
            ys = np.nonzero(shelf_id[:, x] == k)[0]
            ys2 = np.nonzero(shelf_id[:, x + 1] == k)[0] if x + 1 < PW else []
            if len(ys) and len(ys2) and ys.max() > t + H_ * 0.5 and rng.random() < 0.6:
                y0 = min(ys.max(), ys2.max())
                L = int(rng.integers(2, max(3, int(13 * s * 1.6))))
                for d in range(1, L + 1):
                    if y0 + d < PH:
                        img[y0 + d, x] = cols[1] if d <= L // 2 else cols[2]
                        img[y0 + d, x + 1] = cols[2] if d <= L // 2 else cols[3]
                        shelf_id[y0 + d, x:x + 2] = k
            x += int(rng.integers(4, 9)) if rng.random() > 0.3 else int(rng.integers(9, 15))
    out = img.copy()                               # 上一层盖下一层：头顶 1 格是先画的那层 → 压暗一档
    for yy, xx in zip(*np.nonzero(shelf_id >= 0)):
        k = shelf_id[yy, xx]
        if yy - 1 >= 0 and 0 <= shelf_id[yy - 1, xx] < k:
            cur = "#%02x%02x%02x" % tuple(int(v) for v in img[yy, xx][:3])
            if cur in darker:
                out[yy, xx] = hx(darker[cur])
    img = out
    for f in (R.corner_fix, R.speck_fix, R.corner_fix, R.alpha_fix):
        f(img)
    R.de_alt(img, passes=2)
    for f in (R.corner_fix, R.edge_diag_fill, R.speck_fix, R.corner_fix):
        f(img)
    return img, ox, oy


def draw_midtrees():
    """返回 {层 id: 图} 和 room.json 的层（每层一张，放在 mid / isles 后面一格）"""
    imgs, layers = {}, []
    for lid, (ly, wt, sc, z) in LAYER_FOR.items():
        W_ = int(480 + (R.W - 480) * sc) + 4
        root = wt + 6                                # 根在洲上的草里（水面上 ~6 行以内被洲挡住）
        trees = [t for t in MIDTREES if t[0] == lid]
        sprites = [mini_tree(s_, seed, TREE_PAL[lid]) + (x, face) for (_l, x, s_, seed, face) in trees]
        top = max(sp[2] for sp in sprites) + 2
        img = R.blank(W_, top + root + 1)
        for (spr, tx, ty, x, face) in sorted(sprites, key=lambda q: -q[0].shape[0]):    # 大的在后
            sp = spr if face > 0 else spr[:, ::-1]
            sx = tx if face > 0 else spr.shape[1] - 1 - tx
            X0, Y0 = x - sx, top + root - ty
            m = sp[..., 3] > 0
            for yy, xx in zip(*np.nonzero(m)):
                if 0 <= Y0 + yy < img.shape[0] and 0 <= X0 + xx < W_:
                    img[Y0 + yy, X0 + xx] = sp[yy, xx]
        for f_ in (R.corner_fix, R.speck_fix, R.corner_fix):   # 一对树叠在一起的地方再清一遍
            f_(img)
        name = "trees_" + lid
        imgs[name + ".png"] = img
        layers.append({"id": name, "img": REL + name + ".png", "scroll": sc, "y": ly - top, "z": z, "after": lid})
    return imgs, layers


# ---------------------------------------------------------------- 指示牌（结局一 yard_sign：「运输记录里的指示牌」「箭头指着水源」）
# 旧货场边上的一块旧木牌：一根柱子，上面一块箭头形的板（朝右 = 水源那边），漆褪得只剩一个淡淡的箭头和几块看不清的字；
# 柱子上再钉一小块编号牌（货运的模板字，磨掉了，铁皮的）。
# v19：作者说看不清 → 木头换成温暖的旧木棕（比蒲棒深一点、灰一点），三档：受光边、木面、木纹 / 背光；
# 只这一个物件比第十一版深（作者同意），最深那档亮度 127，仍远浅于晨的斗篷。漆是褪了的米白，箭头三格粗。
SIGN_AT = 256            # 柱子的房间 x（yard_sign 240 = 晨站的地方，牌子在她右手边，箭头朝水源）
WOOD = ["#c9a560", "#b58f55", "#9c7848"]                    # 旧木：受光边、木面、木纹 / 背光 / 下沿（只暗一档）
PAINT = ["#e1d9a3", "#d0c39e"]                              # 褪了色的漆：箭头、看不清的字
PLATE = ["#f6f3e2", "#e4e2cd", "#cddbd5", "#b9d1cb"]        # 编号牌（铁皮，石头那几档）
SIGN_OWN = set(WOOD)                                        # 第十一版里没有、作者同意只给指示牌用的颜色


def sign_frames():
    W_, H_ = 34, 46
    base = 40                                    # 贴水那一行
    f = R.blank(W_, H_)
    px = 6                                       # 柱子左边那一列
    for y in range(base - 37, base + 1):         # 柱子：三格宽，左亮右暗，顶上斜着削掉一角
        put(f, px, y, WOOD[0])
        put(f, px + 1, y, WOOD[1])
        put(f, px + 2, y, WOOD[2])
    f[base - 37, px + 2] = 0
    bx0, by0, bw, bh = 2, base - 34, 25, 9       # 箭头板：长方形 + 右头一个尖
    for y in range(bh):
        tip = 4 - abs(y - bh // 2)
        for x in range(bx0, bx0 + bw + tip + 1):
            if y == 0 and x < bx0 + 2:
                continue                         # 左上角缺一块（旧了，掉了个角）
            c = WOOD[0] if y == 0 or x == bx0 else WOOD[2] if y == bh - 1 or x >= bx0 + bw else WOOD[1]
            put(f, x, by0 + y, c)
    for x in range(bx0 + 4, bx0 + bw + 2):       # 两块木板拼的缝（一整道，左头藏在第一个字下面）
        put(f, x, by0 + bh // 2, WOOD[2])
    # 褪色的漆：一个往右的箭头（三格粗的杆 + 尖），杆上磨掉一块；左边两个看不清的字
    for x in range(bx0 + 10, bx0 + 19):
        for y in range(by0 + 3, by0 + 6):
            if not (x in (bx0 + 13, bx0 + 14) and y == by0 + 5):
                put(f, x, y, PAINT[0])
    for d in range(4):
        for y in range(by0 + 4 - (3 - d), by0 + 4 + (3 - d) + 1):
            put(f, bx0 + 19 + d, y, PAINT[0])
    for (x, y, w, h) in ((bx0 + 2, by0 + 2, 2, 5), (bx0 + 4, by0 + 5, 1, 2),     # 一个 L 一样的字
                         (bx0 + 6, by0 + 2, 2, 2), (bx0 + 6, by0 + 5, 2, 2)):    # 一个只剩上下两块的字
        for dx in range(w):
            for dy in range(h):
                put(f, x + dx, y + dy, PAINT[1])
    plate = from_rows(["LLLLLLLLL", "LbbKKbbbS", "LbKKbbKbS", "LbbbbKKbS", "SSSSSSSSS"],
                      {"L": PLATE[0], "b": PLATE[1], "K": PLATE[2], "S": PLATE[3]})
    m = plate[..., 3] > 0
    f[base - 21:base - 16, px - 2:px + 7][m] = plate[m]
    reflect(f, base, [ "#a5d3a8", "#c0e0b9"], k=0.45, maxlen=6)
    return [f], base


# ---------------------------------------------------------------- 被压倒的草（结局一 yard_grass：「草被压倒了。」「……一大片。」）
# 晨这一排、她右手边一大段（FLAT_X，大象往水源走过去拖倒的）：main 草丛那套绿，一根根草叶朝右躺倒、叠在一起，
# 几根被压弯又翘起来半截、折在中间；两头留几根半倒的接到旁边站着的草。这一段的会动草丛（g1）reed_field_art.py 不放。
FLAT_X = R.YARD_FLAT
FLAT_T = [["#dcecb2", "#cbe39c", "#b8d98a"], ["#cbe39c", "#b8d98a", "#a6cf7c"], ["#b8d98a", "#a6cf7c", "#93c47a"]]


def flat_frames():
    """main 草丛的那种一团团草（grass_base，同一套颜色和画法），一团团往右放倒：离根越高的那一行越往右挪、越往下压
    （高 h 的一格 → 往右 h·FLAT_LEAN、只剩 h·FLAT_SQUASH 高），叶尖叠在上面；两头几团半倒，接到旁边站着的草"""
    x0, x1 = FLAT_X
    W_, H_ = x1 - x0 + 40, 30
    base = 22
    rng = np.random.default_rng(1818)
    f = R.blank(W_, H_)
    x = 2.0
    clumps = []
    while x < W_ - 34:
        clumps.append(x)
        x += rng.uniform(9, 15)
    for i, cx in enumerate(clumps):
        u = i / max(1, len(clumps) - 1)
        edge = min(u, 1 - u)
        k_ = 1.0 if edge > 0.1 else 0.5          # 两头半倒
        w, h = int(rng.integers(16, 24)), int(rng.integers(18, 25))
        g, bx, by = R.grass_base(w, h, R.GRASS_T["G"], rng, 0.0)
        ys, xs = np.nonzero(g[..., 3] > 0)
        for k in np.argsort(-ys):                    # 从根往上画：叶尖后画、盖在上面
            yy, xx = ys[k], xs[k]
            hh = by - yy
            if hh < 0:
                continue
            q = (hh / h) ** 1.4                       # 越往上弯得越多：一团团拱起来的背、叶尖压到地上
            X = int(round(cx + xx - bx + FLAT_LEAN * h * q * k_))
            Y = base - int(round(hh - FLAT_DROP * h * q * k_))
            if 0 <= X < W_ and 0 <= Y < H_:
                f[Y, X] = g[yy, xx]
    top = np.array([np.argmax(f[:, x, 3] > 0) if f[:, x, 3].any() else base for x in range(W_)])
    for _ in range(9):                               # 面上几片躺倒的长叶（暗一档），朝右，看得出被拖的方向
        sx = int(rng.uniform(6, W_ - 46))
        R.plant_blade(f, sx, top[sx] + 2, rng.uniform(13, 20), 1.33, 0.12, 2.6, FLAT_T[int(rng.integers(1, 3))])
    f[base + 1:] = 0
    for f_ in (R.corner_fix, R.speck_fix, R.corner_fix, R.alpha_fix):
        f_(f)
    R.de_alt(f, passes=2)
    for f_ in (R.corner_fix, R.edge_diag_fill, R.speck_fix, R.corner_fix):
        f_(f)
    reflect(f, base, REFL, k=0.5, maxlen=3, solid=True)
    return [f], base


FLAT_LEAN, FLAT_DROP = 1.3, 0.62


# ---------------------------------------------------------------- 摆放（房间坐标）
# 立在水面上的小东西（工具包、水杯、花圃）：在晨脚边那层半透明的水（ankle_water，z 21）前面，不然被罩得看不见；
# 底边比晨脚底往前（往下）挪 FRONT_DY 行 = 离镜头比晨近一点，晨走过时从它后面过。湿土那一小块也一样（露出水面的土包）。
FRONT_Z = 22
FRONT_DY = 2
FLAT_DY = 1
BED_Z, BED_DY = 26, 6     # 花圃再往前一点（和近景那排水草 g3 一样近、在它前面），不然花被水草挡住
BED_AT = 1470             # = 剧本 markers 的 east_bed（花圃放在两株近景水草 1391、1466 中间的空当里）
YARD_SHIP_X = 34          # 结局一：yard_landing 120 站在船身中间（舱门在 92 那一列）
EAST_SHIP_X = 1772        # 结局二：船尾贴着房间右头；east_landing 1810 在机头后面的船身前


def sheet(frames):
    w = max(f.shape[1] for f in frames)
    h = max(f.shape[0] for f in frames)
    out = R.blank(w * len(frames), h)
    for i, f in enumerate(frames):
        out[h - f.shape[0]:, i * w:i * w + f.shape[1]] = f
    return out, w, h


def build():
    """画全部物件，返回 {文件名: 图} 和 {物件 id: room.json 的写法}"""
    pngs, objs = {}, {}

    ship, sbase = ship_frames()
    img, w, h = sheet(ship)
    pngs["ship.png"] = img
    for oid, x, need, states, default in (
            ("yard_ship", YARD_SHIP_X, "final_ending_1", {"default": 0, "parked": 0}, ""),
            ("east_plane", EAST_SHIP_X, "final_ending_2", {"broken": 1, "wing_up": 0}, "broken")):
        gy = R.ground(x + w // 2)
        o = {"img": REL + "ship.png", "x": x, "y": gy - sbase, "w": w, "h": h, "frames": 2, "states": states, "z": -5,
             "need": [need], "click": [x, gy - sbase, w, sbase + 1]}
        if default:
            o["default"] = default
        objs[oid] = o

    bag, bbase = toolbag()
    img, w, h = sheet(bag)
    pngs["toolbag.png"] = img
    for oid, x, st in (("yard_toolbag", 134, {"placed": 0}), ("east_toolbag", 1834, {"ready": 1})):   # 晨（落地点）右手边
        gy = R.ground(x + 8)
        objs[oid] = {"img": REL + "toolbag.png", "x": x, "y": gy + FRONT_DY - bbase, "w": w, "h": h, "frames": 2, "states": st,
                     "default": "hidden", "z": FRONT_Z}

    c, cbase = cup()
    pngs["water_cup.png"] = c
    x = 1756
    objs["east_water_cup"] = {"img": REL + "water_cup.png", "x": x, "y": R.ground(x) + FRONT_DY - cbase, "w": c.shape[1], "h": c.shape[0],
                              "states": {"placed": 0}, "default": "hidden", "z": FRONT_Z}

    soil, obase = soil_frames()
    img, w, h = sheet(soil)
    pngs["soil.png"] = img
    x = 904                                   # 晨站在 yard_soil（900）蹲下挖：土在她脚前偏右，石头露在她右边
    objs["yard_stone"] = {"img": REL + "soil.png", "x": x, "y": R.ground(900) + FRONT_DY - obase, "w": w, "h": h, "frames": 2,
                          "states": {"default": 0, "placed": 1}, "z": FRONT_Z}

    bed, ebase = bed_frames()
    img, w, h = sheet(bed)
    pngs["flower_bed.png"] = img
    x = BED_AT - 74                           # 晨站在 east_bed（BED_AT）：花圃在她左手边，围栏右头挨着她
    objs["east_bed"] = {"img": REL + "flower_bed.png", "x": x, "y": R.ground(x + 32) + BED_DY - ebase, "w": w, "h": h, "frames": 2,
                        "states": {"default": 0, "empty": 0, "planted": 1}, "z": BED_Z}

    sg, gbase = sign_frames()
    pngs["sign.png"] = sg[0]
    objs["yard_sign"] = {"img": REL + "sign.png", "x": SIGN_AT - 6, "y": R.ground(SIGN_AT) - gbase, "w": sg[0].shape[1],
                         "h": sg[0].shape[0], "z": -5, "click": [SIGN_AT - 6, R.ground(SIGN_AT) - 37, 34, 38]}
    fl, fbase = flat_frames()
    pngs["flat_grass.png"] = fl[0]
    objs["yard_grass"] = {"img": REL + "flat_grass.png", "x": FLAT_X[0] - 4, "y": R.ground(FLAT_X[0] + 50) + FLAT_DY - fbase,
                          "w": fl[0].shape[1], "h": fl[0].shape[0], "z": FRONT_Z}

    tr = tree_frames()
    img, w, h = sheet(tr)
    pngs["tree_rub.png"] = img
    tx, ty, _, _ = TREE_PATCH
    objs["east_tree"] = {"img": REL + "tree_rub.png", "x": tx, "y": ty, "w": w, "h": h, "frames": 2,
                         "states": {"default": 0, "bark_rubbed": 1}, "z": -65}

    pngs["empty.png"] = R.blank(1, 1)
    objs["sky"] = {"img": REL + "empty.png", "x": 0, "y": 0, "w": 1, "h": 1,
                   "states": {"day": 0, "dusk": 0, "night": 0, "shadow_pass": 0},
                   "_note": "纯剧情状态（看天：傍晚、夜里、白天），画面上没有东西"}
    return pngs, objs


# ---------------------------------------------------------------- 检查
def v11_palette():
    import io
    import subprocess
    fs = subprocess.run(["git", "ls-tree", "--name-only", "HEAD", "art/reed_field/"], capture_output=True, text=True, cwd=ROOT).stdout.split()
    pal = set()
    for f in fs:
        if not f.endswith(".png") or "bigtrees" in f or "/src/" in f:
            continue
        b = subprocess.run(["git", "show", "HEAD:./" + f], capture_output=True, cwd=ROOT).stdout
        a = np.array(Image.open(io.BytesIO(b)).convert("RGBA")).reshape(-1, 4)
        pal.update("#%02x%02x%02x" % tuple(c) for c in np.unique(a[a[:, 3] == 255][:, :3], axis=0))
    return pal


def lum(c):
    return 0.299 * int(c[1:3], 16) + 0.587 * int(c[3:5], 16) + 0.114 * int(c[5:7], 16)


def check(pngs, objs):
    pal = v11_palette()
    ship_cols = {"#%02x%02x%02x" % tuple(c[:3]) for c in ship_src().reshape(-1, 4) if c[3] == 255}
    bad = 0
    for name, img in pngs.items():
        cols = {"#%02x%02x%02x" % tuple(c[:3]) for c in img.reshape(-1, 4) if c[3] > 0}
        own = cols - ship_cols if name == "ship.png" and not SHIP_RECOLOR else cols
        if name == "sign.png":
            print(f"  sign.png: 作者同意的旧木色 {sorted(own & SIGN_OWN)}（只这一个物件）")
            own = own - SIGN_OWN
        off = sorted(own - pal)
        dark = min((lum(c) for c in own), default=999)
        print(f"  {name}: 颜色 {len(own)}（不在第十一版里的 {off}），最深 {dark:.0f}")
        bad += len(off)
        if name == "ship.png":
            for i, f in enumerate(ship_frames()[0]):
                R.scan(f"ship.png#{i}（作者原图的像素，只报不改）", f)
                bad += R.dashes(f"ship.png#{i}", f)
            continue
        o = next((v for v in objs.values() if v["img"].endswith(name)), {})
        fw = o.get("w", img.shape[1])
        for i in range(max(1, img.shape[1] // fw)):
            f = img[:, i * fw:(i + 1) * fw]
            bad += R.scan(f"{name}#{i}", f) + R.dashes(f"{name}#{i}", f)
    return bad


# ---------------------------------------------------------------- 预览
def preview(dirp, objs):
    sys.path.insert(0, str(ROOT / "tools"))
    A = R.OUT
    j = json.loads((A / "room.json").read_text(encoding="utf-8"))
    imgs = {L["id"]: np.array(Image.open(A / L["img"]).convert("RGBA")) for L in j["layers"]}
    R.birds_img_global[0] = np.array(Image.open(A / "birds.png").convert("RGBA"))
    R.fauna_global[:] = [np.array(Image.open(A / "fauna.png").convert("RGBA")), json.load(open(A / "fauna.json"))]
    rj = json.load(open(A / "reeds.json"))
    atlas = np.array(Image.open(A / "reeds.png").convert("RGBA"))
    PUSH = {"g1": (24, 38), "g2": (22, 38), "r1": (17, 64), "r2": (16, 70), "g3": (20, 40), "g4": (30, 26)}
    sheets = {}

    def npc(who, frame, fw=48, fh=64, anchor=(22, 61)):
        if who not in sheets:
            sheets[who] = np.array(Image.open(ROOT / f"art/characters/{who}/{who}.png").convert("RGBA"))
        return sheets[who][:, frame * fw:(frame + 1) * fw][:fh], anchor

    def shot(cx, cl, chen_face, props, people):
        def fn(row, x, sx):
            b = 3.0 * (0.45 if row.startswith("g") else 1.0)
            if row in PUSH:
                rad, bend = PUSH[row]
                sc = R.ROW_SCROLL.get(row, 1.0)
                dx = x - (cx if sc == 1.0 else cx - cl + cl * sc)
                f = max(0.0, 1 - abs(dx) / rad)
                f = f * f * (3 - 2 * f)
                b += bend * f * (1 if dx >= 0 else -1)
            return b
        extra = []
        for oid, st in props.items():
            o = objs[oid]
            im = np.array(Image.open(A / o["img"]).convert("RGBA"))
            fr = o.get("states", {}).get(st, 0)
            fw = o.get("w", im.shape[1])
            extra.append((o.get("z", -1), lambda blit, im=im, fr=fr, fw=fw, o=o: blit(im[:, fr * fw:(fr + 1) * fw], o["x"] - cl, o["y"])))
        for (who, frame, x, face) in people:
            im, (ax, ay) = npc(who, frame, *( (100, 64, (50, 61)) if who == "crowd" else (48, 64, (22, 61)) ))
            if face < 0:
                im = im[:, ::-1]
                ax = im.shape[1] - 1 - ax
            extra.append((0.5, lambda blit, im=im, ax=ax, ay=ay, x=x: blit(im, round(x - cl - ax), R.ground(x) - ay)))
        return R.compose(imgs, atlas, rj, rj["rows"], cl, chen_x=cx, theta_fn=fn, chen_frame=7, chen_flip=chen_face < 0, extra=extra)

    def cam(x):
        return int(min(max(x - 240, 0), R.W - 480))

    def stack(name_, panels):
        out = np.concatenate([np.concatenate([p_, np.full((4, 480, 4), 255, np.uint8)]) for p_ in panels])[:-4]
        Image.fromarray(out).resize((out.shape[1] * 2, out.shape[0] * 2), Image.NEAREST).save(Path(dirp) / (name_ + "_2x.png"))

    M = json.loads((ROOT / "data/story_final.json").read_text(encoding="utf-8"))["markers"]
    wing = M["east_wing"]
    # trigger:"enter"（range 30）的点：晨走进 30 像素就播、不再往前走 → 晨停在 marker 外 30（结局一从左边来、结局二从右边来）
    e1_meet = M["yard_water"] - 30
    e2_see = M["east_slope"] + 30
    # 结局一：落地（飞船、工具包）→ 浅水边见大象（路过的人在晨身后；大象还没有图）→ 湿土种完种子压石头
    stack("ending1", [
        shot(M["yard_landing"], cam(M["yard_landing"]), 1, {"yard_ship": "default", "yard_toolbag": "placed"}, []),
        shot(e1_meet, cam(e1_meet), 1, {}, [("passerby", 0, M["yard_passerby"], 1)]),
        shot(M["yard_soil"], cam(M["yard_soil"]), -1, {"yard_stone": "placed"}, []),
    ])
    # 结局二：坡下看见（树皮蹭过、居民、周围的人）→ 傍晚留下的水 → 第二天居民扶机翼、工具包备好 → 花圃种下
    e2 = {"east_plane": "broken", "east_tree": "bark_rubbed", "east_bed": "default"}
    stack("ending2", [
        shot(e2_see, cam(e2_see), -1, e2, [("resident", 0, M["east_resident"], -1), ("crowd", 0, M["east_crowd"], 1)]),
        shot(e2_see, cam(e2_see), -1, {**e2, "east_water_cup": "placed"}, [("resident", 21, M["east_resident"], -1)]),
        shot(M["east_landing"], cam(M["east_landing"]), -1, {**e2, "east_plane": "wing_up", "east_toolbag": "ready", "east_water_cup": "placed"},
             [("resident", 26, wing, 1)]),
        shot(M["east_bed"], cam(M["east_bed"]), 1, {**e2, "east_bed": "planted"}, []),
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    args = ap.parse_args()
    p = ROOT / "art" / "手改清单.json"
    locked = set(json.loads(p.read_text()).get("files", {})) if p.exists() else set()
    OUT.mkdir(parents=True, exist_ok=True)
    pngs, objs = build()
    tpngs, tlayers = draw_midtrees()
    pngs.update(tpngs)
    for name, img in pngs.items():
        q = OUT / name
        if q.relative_to(ROOT).as_posix() in locked:
            print("  手改过，不覆盖：", name)
            continue
        Image.fromarray(img, "RGBA").save(q)
    (OUT / "objects.json").write_text(json.dumps(objs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (OUT / "layers.json").write_text(json.dumps(tlayers, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    room = R.OUT / "room.json"
    if room.relative_to(ROOT).as_posix() not in locked:
        j = json.loads(room.read_text(encoding="utf-8"))
        j["objects"] = objs
        j["layers"] = R.insert_prop_layers([L for L in j["layers"] if not str(L["id"]).startswith("trees_")])
        room.write_text(json.dumps(j, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("检查：")
    bad = check(pngs, objs)
    print("ok reed_field props", len(objs), "个物件，问题", bad)
    if args.preview:
        Path(args.preview).mkdir(parents=True, exist_ok=True)
        preview(args.preview, objs)


if __name__ == "__main__":
    main()
