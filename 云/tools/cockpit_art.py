"""飞行段：小飞机的驾驶舱（正侧面剖面）+ 舱里会变的物件 + 前窗窗外 16 个状态 + 通讯器图标和聊天框。以后改这些图只改这个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/cockpit_art.py [--preview 目录]

和树屋（tools/forest_room_art.py）同一套做法：
- 没有透视：正侧面剖面，把靠镜头这一侧的机身拿掉看进去。机头朝左（前窗、操纵台在左边），
  右边是右侧机身接口、转化装置、背包架和后舱壁。地板是一条平线，东西都是正侧面。
- 忧郁、旧、不温馨：暗的灰绿金属，补丁、铆钉、胶带、划痕；光只有前窗透进来的一片冷的灰绿光，
  驾驶座上方一盏很弱的小灯；暖色只出现在转化装置（发光时）和铜铃上，面积小，比晨暗。

输出（art/cockpit/）：
- cockpit_back.png   机身剖面：舱壁、肋条、管线、地板、腹下、操纵台壳、两张座椅、灯、背包架、铃钩；
                     前窗那块是**透明的洞**（窗外图 window_* 画在 back 下面，从洞里露出来）；
- cockpit_front.png  靠镜头那一侧的机身外壳（关着的），盖在一切上面；进舱淡出、出舱淡入（像树屋前墙）；
- cockpit_*.png      会换状态的物件，同一张图横排多帧，cockpit.json 里写帧宽和 states 顺序；
- window_<state>.png 窗外 16 个状态（窗洞外接矩形大小）；debris_*.png、airflow.png 避障时在窗外飘的碎石和气流线；
- cockpit.json       尺寸、地板、可走范围、窗矩形、每个 marker 的 x / 地面 y、每个物件的位置和帧。
另外：art/forest_story/icon_communicator.png（背包图标）、art/ui/phone_*.png（通讯器聊天框，9-slice）。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

AIO = Path("/Users/jiamulin/Desktop/程序programs/AI Oscar")
sys.path.insert(0, str(AIO))
from oscarkit.canvas import Canvas  # noqa: E402
from oscarkit.light import Light, polygonal, smooth_noise  # noqa: E402
from oscarkit.measure import srgb_to_oklab  # noqa: E402
from oscarkit.palette import from_lch, oklab_to_srgb  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "cockpit"
UI = ROOT / "art" / "ui"
ICON_OUT = ROOT / "art" / "forest_story"

W, H = 330, 150                 # 剖面图尺寸（右边 44 像素是机尾和尾翼的外壳，不剖开）
FL = 128                        # 地板面（晨脚底踩的那一行；物件底边在 FL-1）
CX = W // 2
SKIN = 5                        # 机身切口厚度
STEP = 0.042                    # 一档明暗
GREEN_H, WARM_H, COOL_H = 165.0, 62.0, 255.0

# 机身外轮廓（图坐标）：机头朝左，前窗在机头上斜着
HULL = [(4, 121), (8, 110), (17, 94), (31, 74), (48, 58), (68, 47), (92, 41), (250, 40), (268, 44),
        (286, 52), (286, 141), (270, 146), (44, 147), (24, 142), (10, 133)]
CAB_X1 = 284                    # 后舱壁（剖面到这里为止，再往右是机尾外壳）
# 机尾（外壳，不剖开）：从后舱壁往右收成锥，上面一片尾翼
TAIL = [(280, 49), (290, 54), (312, 72), (326, 91), (328, 99), (323, 105), (300, 121), (284, 133), (280, 135)]
FIN = [(284, 51), (289, 30), (298, 13), (307, 8), (312, 11), (308, 36), (311, 70), (292, 55)]
# 窗洞 = 座舱玻璃（10-29 重画）：机头上半整片都是玻璃，弧边直接就是机身外壳（外壳在这里只留 CANOPY_FRAME 像素当窗框，
# 不再是「外壳一道弧 + 里面又一道窗框弧」两层皮）；右边一根立柱（PILLAR_X..+4）接天花板，下沿是操纵台的台沿。
WIN_POLY = [(22, 92), (26, 87), (30, 81), (35, 74), (41, 68), (47, 62), (54, 57), (61, 53), (69, 49), (77, 47),
            (88, 45), (88, 92)]
WIN_RECT = (22, 45, 88, 92)     # 外接矩形 x0, y0, x1, y1（含）
CANOPY_FRAME = 3
PILLAR_X = 89
# 玻璃上的两根斜撑：下端在台沿，上端接外壳（大致朝机头弧的法线方向）
STRUTS = (((47, 92), (32, 77)), ((74, 92), (60, 53)))
WIN_W, WIN_H = WIN_RECT[2] - WIN_RECT[0] + 1, WIN_RECT[3] - WIN_RECT[1] + 1

# 光：前窗（冷灰绿）、驾驶座上方的小灯（很弱、微暖）
WIN_L = Light(62, 72, 34, power=1.0, radius=58)
LAMP_L = Light(108, 52, 12, power=0.45, radius=20)
BUNK_L = Light(264, 60, 10, power=0.40, radius=24)   # 后舱铺位上方夹着的小灯（也微暖），后舱靠它才看得清家当
LIGHTS = (WIN_L, LAMP_L, BUNK_L)

N_WALL = smooth_noise(H, W, 14, 40, seed=21)
N_MISC = smooth_noise(H, W, 30, 24, seed=22)
N_FLOOR = smooth_noise(H, W, 40, 4, seed=23)


def col(L, C, h):
    return from_lch(L, C, h)


def cv(img) -> Canvas:
    c = Canvas(1, 1)
    c.a = img
    return c


def S(w, h):
    return Canvas(w, h)


def mrect(x0, y0, x1, y1, shape=(H, W)):
    m = np.zeros(shape, bool)
    m[max(0, y0):max(0, y1 + 1), max(0, x0):max(0, x1 + 1)] = True
    return m


def mpoly(pts, shape=(H, W)):
    c = Canvas(shape[1], shape[0])
    return c.poly(pts, (255, 255, 255))


def erode(m, n):
    out = m.copy()
    for i in range(n):
        o = out.copy()
        o[1:] &= out[:-1]
        o[:-1] &= out[1:]
        o[:, 1:] &= out[:, :-1]
        o[:, :-1] &= out[:, 1:]
        if i % 2:                      # 交替 8 邻域，边角圆一点
            o[1:, 1:] &= out[:-1, :-1]
            o[:-1, :-1] &= out[1:, 1:]
            o[1:, :-1] &= out[:-1, 1:]
            o[:-1, 1:] &= out[1:, :-1]
        out = o
    return out


def dilate(m, n):
    return ~erode(~m, n)


# ============================================================ 打光（和树屋同一个 shade：光照 → 一档一档的块）
def _ill(L, gx, gy, z):
    v = np.stack([L.x - gx, L.y - gy, np.full_like(gx, L.z - z)], -1)
    d = np.linalg.norm(v, axis=-1) + 1e-6
    lam = np.clip(v[..., 2] / d, 0, 1)
    return L.power * lam / (1 + (d / L.radius) ** 2)


_GY, _GX = np.mgrid[0:H, 0:W].astype(float)
_IW = {}


def shade(img, mask, L0, C0, h0, z=0.0, gain=0.5, center=0.0, noise=None, noise_amp=0.6, cell=(10, 14), seed=0,
          green=1.0, warm=1.0, ox=0, oy=0):
    """一块正对镜头的面上色：亮度 = 底色 + gain×(光 - center)，按 STEP 分档（三角网格上分段线性，块边是直线）。
    窗光多的块偏灰绿，灯光多的块微暖，暗的块偏冷。ox, oy：mask 在剖面图里的偏移（单独出图的物件也按舱里的光打）。"""
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return img
    Hh, Ww = mask.shape
    gy, gx = np.mgrid[0:Hh, 0:Ww].astype(float)
    gx += ox
    gy += oy
    Iw, Il = _ill(WIN_L, gx, gy, z), _ill(LAMP_L, gx, gy, z) + _ill(BUNK_L, gx, gy, z)
    F = gain * (Iw + Il - center)
    if noise is not None:
        F = F + noise_amp * STEP * noise
    F = polygonal(F, cell[0], cell[1], seed=seed)
    Tw = polygonal(Iw, cell[0], cell[1], seed=seed)
    Tl = polygonal(Il, cell[0], cell[1], seed=seed)
    k = np.round(F[ys, xs] / STEP)
    tw = np.clip(np.round(Tw[ys, xs] * 3 * green) / 3, 0, 1)
    tl = np.clip(np.round(Tl[ys, xs] * 3 * warm) / 3, 0, 1)
    L = np.clip(L0 + k * STEP, 0.08, 0.95)
    hr = math.radians(h0)
    a = np.full(len(ys), C0 * math.cos(hr))
    b = np.full(len(ys), C0 * math.sin(hr))
    cool = np.clip(-k, 0, 3) / 3 * 0.008
    for amt, hh in ((cool, COOL_H), (tw * 0.026, GREEN_H), (tl * 0.03, WARM_H)):
        a += amt * math.cos(math.radians(hh))
        b += amt * math.sin(math.radians(hh))
    rgb = oklab_to_srgb(np.stack([L, a, b], 1))
    img[ys, xs, :3] = rgb
    img[ys, xs, 3] = 255
    return img


def tone(img, m, steps=1.0, cool=True):
    """把 m 里已经画了的像素整体调亮 / 调暗几档（负数 = 暗）。"""
    sel = m & (img[..., 3] > 0)
    if not sel.any():
        return
    lab = srgb_to_oklab(img[sel][:, :3])
    lab[:, 0] += STEP * steps
    if steps < 0:
        lab[:, 1:] *= 0.92
        if cool:
            lab[:, 1] += 0.004 * math.cos(math.radians(COOL_H)) * -steps
            lab[:, 2] += 0.004 * math.sin(math.radians(COOL_H)) * -steps
    img[sel, :3] = oklab_to_srgb(lab)


def limit_colors(a: np.ndarray, n: int) -> np.ndarray:
    """整张图收到 n 色以内（median cut，不抖动），透明的地方保持透明。"""
    m = a[..., 3] > 0
    im = Image.fromarray(a[..., :3]).quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = a.copy()
    out[..., :3] = np.array(im.convert("RGB"))
    out[~m] = 0
    return out


def lum(img, x, y):
    return float(srgb_to_oklab(img[y, x, :3][None].astype(np.uint8))[0, 0])


# 舱里东西用的几条色（都暗、低饱和）
METAL = (0.25, 0.016, 170)      # 舱壁：旧的灰绿漆
METAL_D = (0.20, 0.014, 180)
RIB = (0.22, 0.012, 175)
FLOOR = (0.21, 0.010, 120)
BELLY = (0.13, 0.010, 200)
CUT = (0.34, 0.012, 150)        # 切口（机身厚度的截面）亮一点
SEAT = (0.24, 0.022, 55)        # 座椅：褪色的旧皮，暗褐
SEAT_D = (0.19, 0.018, 45)
CONSOLE = (0.19, 0.010, 190)
PIPE = (0.27, 0.010, 90)
CABLE = col(0.16, 0.012, 210)
TAPE = col(0.36, 0.020, 85)
RIVET = None  # 按底色亮一档


# ============================================================ 机身
def hull_masks():
    outer = mpoly(HULL)
    inner = erode(outer, SKIN)
    cut = outer & ~inner
    room = inner & (_GY < FL)
    floor = inner & (_GY >= FL) & (_GY < FL + 3)
    belly = inner & (_GY >= FL + 3)
    win = canopy_glass(outer)
    return outer, inner, cut, room, floor, belly, win


def canopy_glass(outer):
    """座舱玻璃（= 窗洞）：WIN_POLY 和「外壳往里收 CANOPY_FRAME 像素」的交集，弧边就是外壳。"""
    return mpoly(WIN_POLY) & erode(outer, CANOPY_FRAME)


def strut_mask(width=2, shape=(H, W)):
    """玻璃上的斜撑（STRUTS），width 像素粗。"""
    m = np.zeros(shape, bool)
    for (x0, y0), (x1, y1) in STRUTS:
        n = max(abs(x1 - x0), abs(y1 - y0))
        for i in range(n + 1):
            x = int(round(x0 + (x1 - x0) * i / n))
            y = int(round(y0 + (y1 - y0) * i / n))
            m[y, x:x + width] = True
    return m


RIBS = [104, 152, 186, 230, 256]       # 竖肋条的 x（窗和操纵台那边是机头的斜框，不放）
STRINGER_Y = (66, 106)


def back_layer():
    outer, inner, cut, room, floor, belly, win = hull_masks()
    img = np.zeros((H, W, 4), np.uint8)
    c = cv(img)
    # 舱壁：大块灰绿旧漆，窗边亮、往后舱越来越沉
    shade(img, room, METAL[0], METAL[1], METAL[2], z=0, gain=0.55, center=0.12, noise=N_WALL, noise_amp=0.7,
          cell=(18, 22), seed=1)
    # 天花板那一圈（离切口 6 像素内）暗一档：弧面背光
    ceil = room & ~erode(inner, 6) & (_GY < 62)
    tone(img, ceil, -1)
    # 蒙皮板缝：横向两条长桁 + 竖肋条
    for y in STRINGER_Y:
        m = room & (_GY == y) & (_GX > 92)
        img[m, :3] = col(*METAL_D)
        m2 = room & (_GY == y + 1) & (_GX > 92)
        tone(img, m2, 1)
    for i, x in enumerate(RIBS):
        m = room & (_GX >= x) & (_GX <= x + 3)
        shade(img, m, RIB[0], RIB[1], RIB[2], z=3, gain=0.5, center=0.1, cell=(8, 26), seed=10 + i)
        tone(img, room & (_GX == x), 1)                # 朝窗那条边受光
        tone(img, room & (_GX == x + 3), -1)
        tone(img, room & (_GX == x + 4), -1)            # 肋条在舱壁上投的细影
        for y in range(54, FL - 2, 10):                 # 铆钉
            if room[y, x + 1]:
                c.put(x + 1, y, img[y, x + 1, :3] + 0)
                tone(img, mrect(x + 1, y, x + 1, y), 1.5)
    # 补丁：两块旧补的铁皮，四角铆钉
    for (x0, y0, x1, y1, s) in ((120, 90, 130, 99, 0),):
        m = mrect(x0, y0, x1, y1) & room
        shade(img, m, METAL[0] + 0.02 * s, METAL[1] - 0.004, METAL[2] - 25, z=1, gain=0.5, center=0.1, cell=(6, 6),
              seed=30 + x0)
        tone(img, mrect(x0, y1, x1, y1) & room, -1)
        tone(img, mrect(x1, y0, x1, y1) & room, -1)
        for (px, py) in ((x0 + 1, y0 + 1), (x1 - 1, y0 + 1), (x0 + 1, y1 - 1), (x1 - 1, y1 - 1)):
            tone(img, mrect(px, py, px, py), 1.5)
    # 天花板：两捆电缆在卡子之间往下垂，一盏小灯
    for (x0, x1, y, sag, cc) in ((96, 286, 48, 2, CABLE), (110, 286, 51, 3, col(0.19, 0.016, 60))):
        for x in range(x0, x1):
            t = ((x - x0) % 30) / 30
            yy = y + int(round(sag * math.sin(math.pi * t)))
            if inner[yy, x]:
                c.put(x, yy, cc)
        for x in range(x0, x1, 30):
            if inner[y, x]:
                c.rect(x, y - 1, x + 1, y + 1, col(0.28, 0.008, 170))
    lamp(c)
    # 一根管子：从转化装置顶上出来，沿舱壁往机尾（引擎）走，经过右侧接口（那一段在 cockpit_leak 里画）；往机头那头细一点
    pipe(img)
    # 操纵台壳（台面上的仪表板 / 导航屏是物件）
    console_shell(img, inner)
    # 两张座椅、铃钩
    seat(img, 92, kind="pilot")
    seat(img, COPILOT_X, kind="copilot")
    bell_hook(c)
    # 家当（10-29 作者：「流浪者最私人的空间一般都是很满的，因为这是唯一的家当」）：都是极简、收纳式的，
    # 后墙上挂的 / 堆的在先，地上靠前的在后（盖住一点后面的），晨走的那一条地面上什么都不挡
    wall_stuff(img, room)
    bunk(img, room)
    under_bunk(img, room)
    bag_rack(img)
    # 地板：钢板 + 防滑纹，下面是腹舱（很暗的横梁和一根管）
    shade(img, floor, FLOOR[0] + 0.05, FLOOR[1], FLOOR[2], z=6, gain=0.4, center=0.1, noise=N_FLOOR, cell=(16, 3),
          seed=50)
    tone(img, floor & (_GY == FL), 1)
    for x in range(0, W, 14):
        tone(img, floor & (_GX >= x) & (_GX <= x + 2) & (_GY == FL + 1), -1)
    shade(img, belly, BELLY[0], BELLY[1], BELLY[2], z=0, gain=0.2, center=0.0, cell=(14, 8), seed=51)
    for x in range(30, 290, 22):
        m = belly & (_GX >= x) & (_GX <= x + 1)
        tone(img, m, 1)
    m = belly & (_GY == FL + 9)
    img[m, :3] = col(0.18, 0.012, 80)
    tone(img, belly & (_GY == FL + 10), -0.5)
    # 地上靠窗那一块被窗光照亮的斜光斑（亮一档）
    spot = mpoly([(60, FL), (98, FL), (112, FL + 2), (66, FL + 2)]) & floor
    tone(img, spot, 1)
    # 切口：机身厚度的截面，比舱壁亮（像树屋的切口），外缘暗一档
    shade(img, cut, CUT[0], CUT[1], CUT[2], z=8, gain=0.25, center=0.05, cell=(28, 28), seed=60)
    tone(img, cut & dilate(inner, 1) & ~inner, -0.6)
    img[win] = 0                                         # 窗洞透明
    canopy(img, inner, win)
    img[~outer] = 0
    tail_and_fin(img)
    return limit_colors(img, 120)


def lamp(c: Canvas):
    """驾驶座上方的小顶灯：一个旧灯罩，灯泡很暗的暖黄（只比周围亮一点）。"""
    x, y = 104, 46
    c.rect(x, y, x + 7, y + 1, col(0.22, 0.008, 180))
    c.rect(x + 1, y + 2, x + 6, y + 4, col(0.27, 0.010, 170))
    c.rect(x + 2, y + 5, x + 5, y + 5, col(0.52, 0.045, 80))
    c.put(x + 1, y + 4, col(0.22, 0.008, 180))
    c.put(x + 6, y + 4, col(0.22, 0.008, 180))


PIPE_Y = 86
PIPE_X0, PIPE_X1 = 96, 281      # 机头那头钻进立柱后面，机尾那头钻进后舱壁（引擎在机尾）
CONV_PIPE_X = 176               # 转化装置顶上接进来的那一段（cockpit_converter 局部 x 20..22）


def pipe(img):
    """沿舱壁的一根燃料管（暗铜色，落灰）：机头 → 转化装置顶 → 右侧接口 → 机尾。两个卡箍。后舱那一段被家当挡住大半。"""
    c = cv(img)
    m = mrect(PIPE_X0, PIPE_Y, PIPE_X1, PIPE_Y + 2)
    shade(img, m, PIPE[0], 0.016, PIPE[2], z=5, gain=0.4, center=0.1, cell=(8, 3), seed=70)
    tone(img, mrect(PIPE_X0, PIPE_Y, PIPE_X1, PIPE_Y), 1)
    tone(img, mrect(PIPE_X0, PIPE_Y + 2, PIPE_X1, PIPE_Y + 2), -1)
    tone(img, mrect(PIPE_X0, PIPE_Y + 3, PIPE_X1, PIPE_Y + 3), -1)       # 管子在舱壁上的影
    # 往下拐进转化装置顶
    m = mrect(CONV_PIPE_X, PIPE_Y, CONV_PIPE_X + 2, 92)
    shade(img, m, PIPE[0], 0.016, PIPE[2], z=5, gain=0.4, center=0.1, cell=(3, 6), seed=71)
    tone(img, mrect(CONV_PIPE_X, PIPE_Y, CONV_PIPE_X, 92), 1)
    for x in (126, 236):
        c.rect(x, PIPE_Y - 1, x + 1, PIPE_Y + 3, col(0.20, 0.008, 190))
    # 修过又修：一段旧胶带上面又缠一段新的，另一处绑着铁丝
    c.rect(183, PIPE_Y - 1, 189, PIPE_Y + 3, col(0.30, 0.020, 80))
    c.rect(186, PIPE_Y - 1, 191, PIPE_Y + 3, TAPE)
    tone(img, mrect(183, PIPE_Y + 3, 191, PIPE_Y + 3), -1)
    for x in (99, 101, 103):
        c.rect(x, PIPE_Y - 1, x, PIPE_Y + 3, col(0.40, 0.010, 180))


CON_X0, CON_X1, CON_TOP = 14, 84, 95
SILL_Y = WIN_RECT[3] + 1        # 台沿（= 窗台）两行：93..94


def console_shell(img, inner):
    """操纵台：机头下面一整块台子，顶上的台沿就是玻璃的下沿，一直接到立柱；朝驾驶座那面是竖的。
    下半截不是一块黑：检修面板（四颗螺丝、散热缝）、一张旧标签、一捆垂下来的线、踢脚板，脚下只留一小块放脚的凹处和两块踏板。"""
    c = cv(img)
    m = mpoly([(10, FL - 1), (14, CON_TOP + 6), (22, CON_TOP), (CON_X1, CON_TOP), (CON_X1, FL - 1)]) & inner
    knee = mrect(70, 117, CON_X1, FL - 3)
    shade(img, m & ~knee, 0.22, 0.012, 185, z=10, gain=0.5, center=0.2, cell=(10, 8), seed=80)
    shade(img, knee & inner, 0.15, 0.010, 200, z=0, gain=0.2, center=0.1, cell=(8, 8), seed=81)
    tone(img, mrect(70, 117, CON_X1, 117), -1)                         # 凹处顶上的影
    tone(img, mrect(CON_X1 - 2, CON_TOP, CON_X1, CON_TOP + 3), 1)      # 手常扶的台角，漆磨掉了
    tone(img, mrect(CON_X1, CON_TOP, CON_X1, 116), -1)                 # 朝座椅那面的边
    # 台沿：从外壳一直接到立柱（玻璃就坐在它上面）
    sill = mrect(0, SILL_Y, PILLAR_X + 4, SILL_Y + 1) & inner
    shade(img, sill, 0.30, 0.012, 175, z=12, gain=0.4, center=0.2, cell=(12, 2), seed=82)
    tone(img, sill & (_GY == SILL_Y), 1.5)
    tone(img, mrect(0, SILL_Y + 2, CON_X1, SILL_Y + 2) & inner & m, -1)  # 台沿下的一道影
    # 腰线 + 检修面板（四角螺丝、四道散热缝）
    tone(img, mrect(16, 114, CON_X1 - 1, 114) & inner, -1)
    tone(img, mrect(16, 115, CON_X1 - 1, 115) & inner, 0.6)
    pan = mrect(20, 117, 44, 124)
    tone(img, pan & ~erode(pan, 1), -1)
    tone(img, mrect(20, 117, 44, 117), 0.5)
    for (px, py) in ((21, 118), (43, 118), (21, 123), (43, 123)):
        c.put(px, py, col(0.32, 0.012, 90))
    for y in (119, 121):
        c.rect(25, y, 39, y, col(0.15, 0.008, 205))
    # 一张旧标签（暗纸）、两个旋钮
    c.rect(48, 117, 54, 120, col(0.36, 0.018, 85))
    c.rect(49, 118, 53, 118, col(0.27, 0.014, 80))
    for x in (58, 63):
        c.rect(x, 118, x + 1, 119, col(0.27, 0.012, 80))
        c.put(x, 118, col(0.34, 0.012, 85))
    # 一捆线从仪表板底下垂出来，绕一圈钻回台子里
    for i, (x, y) in enumerate(((66, 115), (66, 116), (67, 117), (67, 118), (68, 119), (67, 120), (66, 121),
                                (65, 121), (64, 120))):
        c.put(x, y, CABLE if i % 3 else col(0.20, 0.016, 60))
    # 踢脚板
    kick = mrect(14, FL - 2, 69, FL - 1) & inner & m
    tone(img, kick, -1.2)
    # 脚下的两块踏板（斜着）+ 一根搁脚杆
    for px in (73, 78):
        for i in range(3):
            c.put(px + i, FL - 3 - i, col(0.28, 0.010, 180))
            c.put(px + i, FL - 2 - i, col(0.20, 0.010, 190))
    c.rect(70, FL - 2, CON_X1, FL - 1, col(0.18, 0.008, 200))


def canopy(img, inner, win):
    """座舱玻璃上的东西（窗洞清掉以后再画）：右边一根立柱接天花板、两根斜撑、玻璃上几道反光、台面上一只旧搪瓷杯。"""
    c = cv(img)
    pil = mrect(PILLAR_X, 0, PILLAR_X + 4, SILL_Y + 1) & inner
    shade(img, pil, CUT[0] - 0.02, CUT[1], CUT[2], z=8, gain=0.3, center=0.1, cell=(5, 14), seed=61)
    tone(img, pil & (_GX == PILLAR_X), 1)
    tone(img, pil & (_GX == PILLAR_X + 4), -1)
    tone(img, mrect(PILLAR_X + 5, 0, PILLAR_X + 5, SILL_Y - 1) & inner, -1)    # 立柱在舱壁上的细影
    for y in range(54, SILL_Y, 9):
        tone(img, mrect(PILLAR_X + 2, y, PILLAR_X + 2, y), 1.5)
    st = strut_mask() & dilate(win, 1)
    shade(img, st, CUT[0] - 0.04, CUT[1], CUT[2], z=8, gain=0.3, center=0.1, cell=(6, 6), seed=62)
    tone(img, st & ~np.roll(st, 1, 1), 1)                              # 斜撑朝机头那条边受光
    # 反光：玻璃上三小段斜线（不透明的浅灰绿点，稀疏）
    for (x0, y0, n) in ((27, 88, 6), (31, 87, 2), (52, 74, 5), (76, 62, 4), (79, 63, 2)):
        for i in range(n):
            if win[y0 - i, x0 + i]:
                c.put(x0 + i, y0 - i, col(0.44, 0.024, 172))
    # 台沿上一小盆植物（罐头盒当盆），窗边光最好的地方
    c.rect(63, 89, 66, 92, col(0.36, 0.014, 70))
    c.rect(63, 89, 66, 89, col(0.44, 0.014, 75))
    c.rect(66, 90, 66, 92, col(0.28, 0.012, 80))
    for (px, py, L) in ((64, 88, 0.42), (65, 87, 0.46), (63, 86, 0.40), (62, 85, 0.44), (66, 86, 0.38), (67, 85, 0.42),
                        (65, 85, 0.48), (64, 84, 0.50), (61, 86, 0.36), (68, 87, 0.36)):
        c.put(px, py, col(L, 0.060, 145))
    # 台面上的旧搪瓷杯（掉了一块瓷）
    c.rect(76, 88, 79, 92, col(0.46, 0.016, 95))
    c.rect(76, 88, 79, 88, col(0.54, 0.016, 95))
    c.rect(79, 89, 79, 92, col(0.38, 0.014, 100))
    c.put(80, 89, col(0.40, 0.014, 100))
    c.put(80, 90, col(0.40, 0.014, 100))
    c.put(77, 91, col(0.24, 0.012, 200))


def seat(img, x0, kind="pilot"):
    """座椅（正侧面，面朝左 = 朝机头）：一块厚坐垫、往后仰的高靠背（在右边）、一根扶手、铁框和一根腿。
    旧皮褪色，坐垫中间被坐塌一档。副驾驶座：一样的椅子，更旧，落灰，安全带垂着没扣。"""
    c = cv(img)
    base = SEAT if kind == "pilot" else (0.22, 0.016, 62)
    cush = mpoly([(x0, 107), (x0 + 19, 107), (x0 + 21, 109), (x0 + 21, 113), (x0, 113), (x0 - 1, 110)])
    back = mpoly([(x0 + 17, 113), (x0 + 22, 80), (x0 + 28, 80), (x0 + 25, 113)])
    for i, m in enumerate((back, cush)):
        shade(img, m, base[0], base[1], base[2], z=12, gain=0.55, center=0.15, cell=(6, 6), seed=90 + i + x0)
    tone(img, back & ~erode(back, 1) & (_GY < 84), 1)                 # 靠背顶边
    left = np.zeros((H, W), bool)
    for y in range(80, 114):
        xs = np.nonzero(back[y])[0]
        if len(xs):
            left[y, xs[0]] = True
            left[y, xs[-1]] = False
    tone(img, left, 1)                                                 # 靠背朝窗那条边受光
    tone(img, cush & (_GY == 107), 1.2)
    tone(img, cush & (_GY >= 108) & (_GY <= 109) & (_GX > x0 + 4) & (_GX < x0 + 14), -1)   # 坐塌的地方
    for y in (90, 99):                                                  # 靠背上的缝线
        tone(img, back & (_GY == y), -1)
    # 扶手：从靠背伸出来一根细杆，前头一根短立柱
    arm = mrect(x0 + 3, 101, x0 + 20, 102)
    shade(img, arm, 0.20, 0.008, 190, z=13, gain=0.4, center=0.15, cell=(6, 2), seed=93 + x0)
    tone(img, mrect(x0 + 3, 101, x0 + 20, 101), 1)
    c.rect(x0 + 3, 103, x0 + 4, 106, col(0.17, 0.008, 200))
    # 铁框 + 腿 + 底座
    c.rect(x0, 114, x0 + 22, 115, col(0.16, 0.008, 200))
    leg = mrect(x0 + 9, 116, x0 + 11, FL - 1)
    shade(img, leg, 0.20, 0.008, 190, z=10, gain=0.4, center=0.15, cell=(3, 6), seed=95 + x0)
    c.rect(x0 + 4, FL - 2, x0 + 17, FL - 1, col(0.17, 0.008, 200))
    tone(img, mrect(x0 + 4, FL - 2, x0 + 17, FL - 2), 1)
    tone(img, cush & (_GY == 112) & (_GX < x0 + 3), 1.5)                           # 坐垫前沿磨亮的角
    if kind == "copilot":
        c.rect(x0 + 5, 109, x0 + 9, 110, TAPE)                                      # 坐垫裂了，贴过两回胶带
        c.rect(x0 + 7, 108, x0 + 8, 111, col(0.42, 0.020, 85))
        for y in range(84, 112):                                        # 垂着没扣的安全带 + 扣子
            c.put(x0 + 21 - (y - 84) // 9, y, col(0.20, 0.012, 150))
        c.rect(x0 + 17, 111, x0 + 19, 112, col(0.34, 0.010, 90))
        tone(img, cush & (_GY == 108) & (_GX > x0 + 1) & (_GX < x0 + 9), 0.8)   # 落了灰，一块发白
        tone(img, back & (_GY >= 82) & (_GY <= 84), 0.6)
        # 外套搭在靠背上：前片垂到坐垫上方，一只袖子耷拉下来
        coat = mpoly([(x0 + 20, 81), (x0 + 23, 78), (x0 + 29, 78), (x0 + 30, 82), (x0 + 28, 97), (x0 + 25, 96),
                      (x0 + 24, 86), (x0 + 20, 99), (x0 + 16, 98), (x0 + 18, 87)])
        blk(img, coat, (0.32, 0.026, 140), z=13, seed=96 + x0, cell=(4, 5))
        tone(img, mrect(x0 + 21, 85, x0 + 21, 96) & coat, -1)                       # 前片的褶
        sleeve = mpoly([(x0 + 27, 92), (x0 + 29, 92), (x0 + 30, 104), (x0 + 28, 105)])
        blk(img, sleeve, (0.29, 0.024, 140), z=13, seed=97 + x0, cell=(2, 4))
        c.put(x0 + 22, 90, col(0.40, 0.012, 90))                                    # 一颗扣子


BELL_HOOK = (124, 78)


def bell_hook(c: Canvas):
    """驾驶座靠背右边舱壁上一个铁钩（铜铃 / 空绳圈是物件，挂在它下面）。"""
    x, y = BELL_HOOK
    c.rect(x - 1, y - 2, x + 1, y - 1, col(0.18, 0.008, 200))
    c.put(x, y, col(0.30, 0.010, 180))
    c.put(x + 1, y + 1, col(0.30, 0.010, 180))
    c.put(x + 1, y + 2, col(0.24, 0.010, 180))


def bag_rack(img):
    """后舱铺位底下一个低的铁框 + 网兜（背包放这里，背包本身是物件 cockpit_bag）。框比旁边的家当亮一点，好找。"""
    c = cv(img)
    x0, x1, y0 = 248, 269, 104
    for x in (x0, x1):
        c.rect(x, y0, x + 1, FL - 1, col(0.26, 0.008, 185))
        c.put(x, y0, col(0.36, 0.008, 180))
    c.rect(x0, FL - 3, x1 + 1, FL - 2, col(0.22, 0.008, 190))
    for y in range(y0 + 4, FL - 3, 5):                # 网兜：几道横着的暗绳
        c.rect(x0 + 2, y, x1 - 1, y, col(0.20, 0.012, 60))
    c.rect(x0, y0 + 1, x1 + 1, y0 + 1, col(0.26, 0.014, 60))


# ============================================================ 家当（后墙上挂的、堆的；地上靠前的）
COPILOT_X = 130                 # 副驾驶座（往机头挪了 4 像素，给转化装置让地方）
BUNK_Y = 74                     # 铺板上沿
BUNK_X0, BUNK_X1 = 224, 281


def blk(img, m, base, z=8, seed=0, cell=(6, 6), gain=0.5, center=0.12, edge=True):
    """一件家当的一个面：按舱里的光上色；上沿亮一档，右沿、下沿暗一档（不描边）。"""
    shade(img, m, base[0], base[1], base[2], z=z, gain=gain, center=center, cell=cell, seed=seed)
    if edge:
        tone(img, m & ~np.roll(m, 1, 0), 1)
        tone(img, m & (~np.roll(m, -1, 1) | ~np.roll(m, -1, 0)), -1)


def wall_stuff(img, room):
    """前半舱的墙上：驾驶座边贴着的纸和一张照片；副驾驶座上方一块搁板（玻璃罐、几本书、罐头、叠好的布、铁皮盒，一根松紧绳拦着），
    板下钩子上挂一只杯子；天花板一张兜着软包的货网。漏气口那一片墙空着（白汽要看得见）。"""
    c = cv(img)
    # 立柱右边贴的两张纸 + 一张照片（照片暗、白边）
    blk(img, mrect(96, 56, 101, 63) & room, (0.40, 0.020, 85), z=6, seed=300, cell=(4, 4))
    c.rect(97, 58, 100, 58, col(0.30, 0.016, 80))
    c.rect(97, 60, 99, 60, col(0.30, 0.016, 80))
    blk(img, mrect(113, 57, 118, 62) & room, (0.44, 0.012, 95), z=6, seed=301, cell=(4, 4))
    c.rect(114, 58, 117, 61, col(0.22, 0.020, 150))
    c.rect(114, 60, 117, 61, col(0.26, 0.024, 120))
    c.put(115, 56, col(0.34, 0.010, 90))
    blk(img, mrect(196, 66, 201, 72) & room, (0.42, 0.022, 80), z=6, seed=305, cell=(3, 3))      # 一张纸条
    c.rect(197, 68, 200, 68, col(0.30, 0.016, 80))
    c.rect(196, 65, 199, 65, TAPE)
    # 副驾驶座上方贴着一张折过的航线图（一条虚线、几个圈、一个打叉）
    blk(img, mrect(134, 68, 150, 79) & room, (0.40, 0.022, 90), z=6, seed=304, cell=(5, 4))
    tone(img, mrect(142, 68, 142, 79), -0.7)
    for i, (px, py) in enumerate(((136, 77), (138, 76), (140, 75), (142, 73), (144, 73), (146, 71), (148, 70))):
        c.put(px, py, col(0.26, 0.030, 150))
    c.put(137, 72, col(0.30, 0.040, 75))
    c.rect(147, 74, 148, 75, col(0.30, 0.050, 40))
    c.put(141, 66, col(0.34, 0.010, 90))
    # 货网：两头挂在天花板卡子上，往下兜，里面塞着三个软包
    for (x0, x1, y0, y1, base) in ((146, 162, 50, 56, (0.30, 0.026, 120)), (161, 178, 49, 57, (0.27, 0.030, 70)),
                                   (177, 196, 50, 55, (0.29, 0.018, 160))):
        m = Canvas(W, H).ellipse((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, (1, 1, 1)) & room
        blk(img, m, base, z=9, seed=302 + x0, cell=(5, 4))
    for x in range(144, 199):
        sag = int(round(6 * math.sin(math.pi * (x - 144) / 54)))
        if room[50 + sag, x]:
            c.put(x, 51 + sag, col(0.20, 0.012, 60))
        if (x - 144) % 4 == 0:
            for y in range(48, 51 + sag):
                if room[y, x] and (y + x) % 2 == 0:
                    c.put(x, y, col(0.20, 0.012, 60))
    # 搁板 + 两个托架
    blk(img, mrect(132, 63, 196, 64) & room, (0.27, 0.012, 175), z=7, seed=310, cell=(10, 2))
    for bx in (136, 190):
        for i in range(4):
            c.put(bx + i // 2, 65 + i, col(0.20, 0.008, 195))
    # 板上的东西（底边 y=62）
    blk(img, mrect(134, 56, 138, 62), (0.33, 0.030, 150), z=8, seed=311, cell=(3, 4))        # 玻璃罐
    c.rect(134, 55, 138, 55, col(0.30, 0.010, 90))
    c.rect(135, 58, 135, 60, col(0.42, 0.030, 150))
    for i, (y0, x1, base) in enumerate(((60, 153, (0.30, 0.034, 80)), (58, 151, (0.27, 0.026, 130)),
                                        (56, 152, (0.30, 0.024, 25)))):             # 平躺着的三本书
        blk(img, mrect(141, y0, x1, y0 + 1), base, z=8, seed=312 + i, cell=(4, 2))
    blk(img, mrect(156, 56, 160, 62), (0.32, 0.010, 180), z=8, seed=315, cell=(3, 4))       # 罐头
    c.rect(156, 59, 160, 59, col(0.38, 0.030, 70))
    blk(img, mrect(163, 58, 174, 62), (0.30, 0.022, 165), z=8, seed=316, cell=(4, 3))       # 叠好的布
    c.rect(163, 60, 174, 60, col(0.24, 0.020, 170))
    blk(img, mrect(180, 55, 193, 62), (0.28, 0.024, 60), z=8, seed=317, cell=(5, 4))        # 铁皮盒
    c.rect(180, 58, 193, 58, col(0.22, 0.020, 55))
    c.rect(185, 56, 187, 56, col(0.40, 0.020, 80))
    for x in range(133, 196):                                                                # 拦着的松紧绳
        c.put(x, 59 if (x // 9) % 2 else 60, col(0.30, 0.040, 70))
    # 板下钩子上挂着一只杯子
    c.put(171, 65, col(0.30, 0.010, 180))
    c.put(171, 66, col(0.30, 0.010, 180))
    blk(img, mrect(168, 67, 172, 71), (0.40, 0.020, 150), z=8, seed=318, cell=(3, 3))
    c.put(173, 68, col(0.34, 0.018, 150))
    c.put(173, 69, col(0.34, 0.018, 150))


def bunk(img, room):
    """后舱上半一张窄铺：铺板挂在两根链子和后舱壁上，薄褥子、叠了一半的赭黄旧毯子（一角垂过铺沿）、枕头；
    铺上方的墙上夹着一盏小灯（很弱的暖光，后舱的光源）、一张照片、一张纸。"""
    c = cv(img)
    x0, x1, y = BUNK_X0, BUNK_X1, BUNK_Y
    for cx in (x0 + 2, x0 + 30):                                                  # 链子
        for yy in range(49, y):
            if room[yy, cx]:
                c.put(cx, yy, col(0.30 if yy % 2 else 0.20, 0.008, 180))
    blk(img, mrect(x0, y, x1, y + 2) & room, (0.26, 0.012, 175), z=8, seed=320, cell=(10, 2))   # 铺板
    blk(img, mrect(x0 + 1, y - 3, x1, y - 1) & room, (0.30, 0.016, 150), z=9, seed=321, cell=(8, 3))  # 褥子
    pil = Canvas(W, H).ellipse(274, y - 5, 6, 3, (1, 1, 1)) & room                  # 枕头
    blk(img, pil, (0.42, 0.012, 120), z=10, seed=322, cell=(4, 3))
    # 毯子叠了一半：右边三层叠得整整齐齐，左边还摊着、皱着，一角垂过铺沿（起床叠到一半就去开船了）
    bl = Canvas(W, H).poly([(x0 + 4, y - 1), (x0 + 7, y - 5), (x0 + 13, y - 6), (x0 + 18, y - 4), (x0 + 24, y - 5),
                            (x0 + 28, y - 3), (x0 + 28, y - 1)], (1, 1, 1))
    hang = Canvas(W, H).poly([(x0 + 5, y), (x0 + 17, y), (x0 + 16, y + 5), (x0 + 13, y + 4), (x0 + 10, y + 7),
                              (x0 + 6, y + 5)], (1, 1, 1))
    blk(img, (bl | hang) & room, (0.36, 0.044, 75), z=10, seed=323, cell=(5, 4))
    for (fx, fy) in ((x0 + 8, y + 1), (x0 + 9, y + 2), (x0 + 12, y + 1), (x0 + 14, y + 1)):
        tone(img, mrect(fx, fy, fx, fy + 2), -1)                                   # 垂下来那一角的褶
    tone(img, mrect(x0 + 5, y, x0 + 17, y), -1)
    for i, (fx0, fx1) in enumerate(((x0 + 29, x0 + 43), (x0 + 30, x0 + 42), (x0 + 29, x0 + 42))):
        fy = y - 2 - i * 2
        blk(img, mrect(fx0, fy - 1, fx1, fy), (0.38 - 0.01 * i, 0.044, 75), z=10, seed=326 + i, cell=(5, 2))
    tone(img, mrect(x0 + 43, y - 7, x0 + 43, y - 1), -1)                            # 叠好那摞的折边
    # 一盏小灯照在墙上的一小圈暖光（只亮一档）
    halo = Canvas(W, H).ellipse(264, 59, 6, 3.5, (1, 1, 1)) & room & (img[..., 3] > 0)
    lab_shift(img, halo, 0.025, 0.005, WARM_H)
    # 墙上：照片（白边、暗的画面）、一张纸、夹着的小灯
    blk(img, mrect(238, 57, 244, 63) & room, (0.46, 0.012, 95), z=6, seed=324, cell=(4, 4))
    c.rect(239, 58, 243, 61, col(0.24, 0.024, 160))
    c.rect(239, 60, 243, 61, col(0.30, 0.030, 120))
    blk(img, mrect(247, 55, 252, 62) & room, (0.40, 0.020, 85), z=6, seed=325, cell=(4, 4))
    for yy in (57, 59):
        c.rect(248, yy, 251, yy, col(0.30, 0.016, 80))
    c.rect(262, 54, 266, 56, col(0.24, 0.008, 190))                                # 灯罩
    c.rect(263, 57, 265, 57, col(0.62, 0.070, 80))                                  # 灯泡（暖黄，比晨暗）
    c.put(264, 53, col(0.30, 0.008, 180))


def under_bunk(img, room):
    """铺底下：左边一摞家当（木箱、橄榄绿铁皮箱、用绳捆着的一卷铺盖），一件衬衫搭在铺沿上，最里面一个压缩式马桶
    （翻盖、贴墙的水箱、一卷纸）、半拉着的帘子；地上靠前一双旧靴子（盖住箱子底边一点）。"""
    c = cv(img)
    # 木箱
    box = mrect(223, 111, 246, FL - 1)
    blk(img, box, (0.31, 0.036, 62), z=8, seed=330, cell=(6, 5))
    for yy in (116, 121):
        tone(img, mrect(224, yy, 245, yy), -1)
    for xx in (225, 244):
        tone(img, mrect(xx, 112, xx, FL - 1), -0.7)
    c.rect(230, 117, 236, 119, col(0.22, 0.026, 55))                               # 模糊的喷字
    c.rect(231, 118, 235, 118, col(0.31, 0.036, 62))
    # 橄榄绿铁皮箱（把手、搭扣）
    case = mrect(225, 101, 244, 110)
    blk(img, case, (0.29, 0.030, 125), z=9, seed=331, cell=(5, 4))
    c.rect(231, 100, 237, 100, col(0.22, 0.010, 190))
    c.rect(233, 105, 235, 106, col(0.40, 0.012, 90))
    tone(img, mrect(225, 104, 244, 104), -1)
    # 捆着的铺盖卷（两道绳）
    roll = Canvas(W, H).ellipse(234, 96.5, 8.5, 3.6, (1, 1, 1))
    blk(img, roll, (0.31, 0.022, 165), z=10, seed=332, cell=(4, 3))
    for xx in (229, 239):
        c.rect(xx, 93, xx, 100, col(0.40, 0.030, 80))
    c.put(226, 96, col(0.24, 0.018, 165))                                           # 卷的端面一圈
    c.put(227, 95, col(0.24, 0.018, 165))
    # 衬衫搭在铺沿上（两只袖子垂下来）
    sh = Canvas(W, H).poly([(255, 77), (267, 77), (267, 84), (265, 88), (263, 84), (259, 84), (257, 89), (255, 85)],
                           (1, 1, 1)) & room
    blk(img, sh, (0.32, 0.030, 100), z=9, seed=333, cell=(4, 4))
    tone(img, mrect(261, 78, 261, 84) & sh, -1)
    # 帘子：铺板底下一根杆，帘子收在马桶左边，竖褶
    c.rect(268, BUNK_Y + 3, 281, BUNK_Y + 3, col(0.22, 0.008, 190))
    cur = Canvas(W, H).poly([(268, 78), (273, 78), (274, 104), (272, 106), (269, 105), (267, 103)], (1, 1, 1)) & room
    blk(img, cur, (0.28, 0.022, 165), z=7, seed=334, cell=(3, 6))
    for xx in (269, 271):
        tone(img, mrect(xx, 80, xx, 104) & cur, -1)
    # 压缩式马桶：贴墙的水箱板 + 翻盖 + 方底座 + 冲水钮；墙上一卷纸
    blk(img, mrect(277, 100, 281, 112) & room, (0.30, 0.010, 175), z=8, seed=335, cell=(3, 5))
    c.put(279, 102, col(0.44, 0.012, 90))
    bowl = Canvas(W, H).poly([(272, 114), (281, 114), (281, FL - 1), (276, FL - 1), (275, 121), (273, 119)], (1, 1, 1))
    blk(img, bowl & room, (0.34, 0.010, 165), z=9, seed=336, cell=(4, 5))
    blk(img, mrect(271, 112, 279, 113) & room, (0.42, 0.010, 160), z=10, seed=337, cell=(4, 2))   # 坐圈
    blk(img, mrect(275, 102, 276, 111) & room, (0.36, 0.010, 165), z=10, seed=341, cell=(2, 4))   # 掀起来靠墙的盖
    tone(img, mrect(276, 123, 281, 123) & room, -1)
    blk(img, mrect(274, 106, 276, 110) & room, (0.46, 0.010, 100), z=8, seed=338, cell=(2, 2))
    # 铺板底下拉一根细绳，晾着两只袜子（木夹子）
    for x in range(241, 255):
        c.put(x, 78 + (1 if 244 <= x <= 251 else 0), col(0.30, 0.012, 80))
    for (sx, base) in ((243, (0.36, 0.022, 25)), (249, (0.34, 0.024, 95))):
        sock = Canvas(W, H).poly([(sx, 80), (sx + 2, 80), (sx + 2, 85), (sx + 4, 86), (sx + 4, 87), (sx, 87)], (1, 1, 1))
        blk(img, sock & room, base, z=9, seed=342 + sx, cell=(2, 3))
        c.rect(sx + 1, 78, sx + 1, 80, col(0.48, 0.020, 85))
    # 木箱：换过一块新一点的板，磨亮的角
    tone(img, mrect(224, 117, 245, 120), 0.8)
    for (px, py) in ((223, 111), (246, 111), (223, FL - 1)):
        tone(img, mrect(px, py, px, py), 1.5)
    # 地上靠前：一双旧靴子（一只立着、一只躺倒），比木箱暗、偏橄榄，剪影分得开
    boot = Canvas(W, H).poly([(226, 118), (230, 118), (230, 123), (234, 124), (234, FL - 1), (226, FL - 1)], (1, 1, 1))
    blk(img, boot, (0.21, 0.020, 80), z=12, seed=339, cell=(3, 3))
    c.rect(226, 118, 230, 118, col(0.28, 0.020, 85))
    boot2 = Canvas(W, H).poly([(236, 124), (243, 124), (243, FL - 1), (233, FL - 1), (234, 125)], (1, 1, 1))
    blk(img, boot2, (0.20, 0.020, 80), z=12, seed=340, cell=(3, 3))
    c.rect(244, 123, 244, FL - 1, col(0.15, 0.012, 60))                           # 躺倒那只的鞋底
    c.put(231, 124, col(0.30, 0.020, 85))                                           # 鞋带扣


# ============================================================ 外壳：和 art/flight/ship.png 同一架飞机（银灰机身、一道暗紫红条、青绿座舱玻璃、暗尾翼）
SKIN_GRAY = (0.40, 0.008, 150)
STRIPE = (0.33, 0.045, 340)
FIN_C = (0.26, 0.014, 320)


def exterior(img, body, seed=0, panels=(60, 112, 166, 214, 252), stripe=True, detail=True):
    """在 body 这块上画机身外壳：旧银灰漆（夜里，暗一些），面板缝和铆钉、雨痕、一道暗紫红条。
    detail=False：只画大块颜色（底漆 + 上下明暗带），不画面板缝 / 铆钉 / 接缝 / 雨痕 / 紫红条（船外远景按缩小后的像素另画，见 ship_out）。"""
    c = cv(img)
    noise = smooth_noise(H, W, 6, 50, seed=31 + seed)
    shade(img, body, SKIN_GRAY[0], SKIN_GRAY[1], SKIN_GRAY[2], z=40, gain=0.35, center=0.15, noise=noise,
          noise_amp=0.8, cell=(14, 18), seed=100 + seed, green=0.5, warm=0)
    tone(img, body & (_GY < 58), 1)
    tone(img, body & (_GY > 120), -1.5)
    tone(img, body & (_GY > 136), -1)
    if not detail:
        return
    for x in panels:
        tone(img, body & (_GX == x), -1.5)
        for y in range(48, 144, 12):
            if body[y, x + 2] and body[y + 1, x + 2]:
                tone(img, mrect(x + 2, y, x + 2, y + 1), 1)
    for y in (66, 122):
        tone(img, body & (_GY == y) & (_GX > 20), -1.2)
    if stripe:
        # 暗紫红条：从机头下方斜着往机尾抬（像 ship.png）
        band = np.zeros((H, W), bool)
        for x in range(W):
            yc = 116 - (x - 20) * 0.10
            band[int(round(yc)):int(round(yc)) + 3, x] = True
        band &= body
        shade(img, band, STRIPE[0], STRIPE[1], STRIPE[2], z=40, gain=0.3, center=0.15, cell=(14, 4), seed=110 + seed,
              green=0, warm=0)
    rng = np.random.default_rng(9 + seed)
    for _ in range(18):
        x = int(rng.integers(10, W - 10))
        y0 = int(rng.integers(44, 100))
        ln = int(rng.integers(6, 22))
        tone(img, body & (_GX == x) & (_GY >= y0) & (_GY < y0 + ln), -0.8)


def tail_and_fin(img, detail=True):
    """机尾（锥形外壳）+ 尾翼。不剖开，前后层都一样。detail=False 见 exterior。"""
    tail = mpoly(TAIL)
    fin = mpoly(FIN)
    exterior(img, tail, seed=3, panels=(296, 312), detail=detail)
    shade(img, fin, FIN_C[0], FIN_C[1], FIN_C[2], z=40, gain=0.3, center=0.1, cell=(8, 10), seed=120, green=0.3,
          warm=0)
    if detail:
        tone(img, fin & ~erode(fin, 1) & (_GX < 300), 1)
    tone(img, fin & (_GY > 40) & (_GX > 300), -1)
    # 尾翼上一道褪色的条
    tone(img, fin & (_GY >= 20) & (_GY <= 22), 1.2)
    return tail | fin


def front_layer():
    """关着的机身外壳（靠镜头这一侧）：银灰旧漆、面板缝、铆钉、雨痕、暗紫红条、座舱玻璃（青绿、很暗，左上一道反光）、
    舱门轮廓、一块补丁。"""
    outer = mpoly(HULL)
    img = np.zeros((H, W, 4), np.uint8)
    c = cv(img)
    exterior(img, outer)
    win = canopy_glass(outer)
    shade(img, win, 0.24, 0.035, 185, z=40, gain=0.3, center=0.1, cell=(10, 10), seed=101, green=0.4, warm=0)
    tone(img, win & (_GY < 66), 1)
    tone(img, dilate(win, 2) & ~win & outer, -1.5)
    tone(img, strut_mask() & win, -1.5)                 # 玻璃上的两根斜撑（和舱里同一位置）
    for i in range(7):
        c.put(50 + i, 80 - i, col(0.42, 0.030, 175))
    for i in range(4):
        c.put(58 + i, 82 - i, col(0.36, 0.030, 175))
    door = mrect(168, 54, 204, 126)
    tone(img, door & ~erode(door, 1), -1.8)
    c.rect(198, 88, 201, 89, col(0.24, 0.010, 250))
    m = mrect(120, 96, 140, 106)
    tone(img, m, 0.7)
    tone(img, m & ~erode(m, 1), -1)
    for x in (226, 231, 236):
        c.rect(x, 96, x + 2, 101, col(0.30, 0.010, 250))
    img[~outer] = 0
    tail_and_fin(img)
    return limit_colors(img, 64)


# ============================================================ 船外远景：躲碎石时镜头拉远看到的整艘船（10-30 作者：「躲避石头的时候飞船能不能缩小一点」
# 「切远景，但不是那个跟角色一样小的那个，我觉得只是缩小」）
# 和 cockpit_front 同一架船、同一套颜色和破损，按 OUT_SCALES 每档原生重画一张（不做非整数缩放，像素不糊）：
#   大块颜色（底漆、上下明暗带、窗玻璃、尾翼）= 1 倍外壳的「平涂版」按像素中心取样（色块边都是直线，取样不糊）；
#   1 像素的细节（面板缝、接缝、雨痕、门缝、补丁边、窗框、窗上的反光、紫红条、尾翼亮边）按缩小后的坐标重新画，粗细不跟着缩没。
# 拉远 / 拉回时引擎一档档交叉淡入（cockpit_room.gd「船外远景」），最后停在作者挑的那一档（debris_steer 的 "far_scale"）。
# 0.5 倍左右就和森林里起飞那艘（art/level1/ship_fly.png，约 165×45）一样小了，所以最小只做到 0.55。
SHIP_OUT = OUT / "ship_out"
OUT_SCALES = (0.93, 0.87, 0.81, 0.75, 0.70, 0.65, 0.60, 0.55)


def _ext_flat():
    """1 倍外壳的大块颜色（不画细节）：机身 + 窗玻璃 + 机尾 + 尾翼。"""
    outer = mpoly(HULL)
    img = np.zeros((H, W, 4), np.uint8)
    exterior(img, outer, detail=False)
    img[~outer] = 0
    tail_and_fin(img, detail=False)
    return img


def ship_out(k: float, flat=None):
    """k 倍大小的船外观（RGBA 数组）。坐标 = 1 倍图坐标 × k；图左上角对应 1 倍图的左上角。"""
    flat = _ext_flat() if flat is None else flat
    w, h = int(round(W * k)), int(round(H * k))
    sh = (h, w)
    gy, gx = np.mgrid[0:h, 0:w]

    def sc(pts):
        return [(x * k, y * k) for x, y in pts]

    def r(v):
        return int(round(v * k))

    body = mpoly(sc(HULL), sh)
    tail = mpoly(sc(TAIL), sh)
    fin = mpoly(sc(FIN), sh)
    win = mpoly(sc(WIN_POLY), sh) & erode(body, max(2, r(CANOPY_FRAME)))     # 座舱玻璃，同 canopy_glass
    ship = body | tail | fin
    # 大块颜色：取 1 倍平涂版里对应的像素中心
    sx = np.clip(((gx + 0.5) / k).astype(int), 0, W - 1)
    sy = np.clip(((gy + 0.5) / k).astype(int), 0, H - 1)
    img = flat[sy, sx].copy()
    # 轮廓按缩小后的多边形重新算（边更顺）；取样落到透明处的边缘像素，从旁边借颜色
    for _ in range(3):
        hole = ship & (img[..., 3] == 0)
        if not hole.any():
            break
        for dy, dx in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            src = np.roll(np.roll(img, dy, 0), dx, 1)
            take = hole & (src[..., 3] > 0)
            img[take] = src[take]
            hole &= ~take
    img[~ship] = 0
    tbody = body | tail
    # 面板缝（竖）+ 铆钉（大的几档才有，小了就是噪点）
    for x in (60, 112, 166, 214, 252, 296, 312):
        xs = r(x)
        tone(img, tbody & ~fin & (gx == xs), -1.5)
        if k >= 0.7:
            for y in range(48, 144, 12):
                yy = r(y)
                if 0 <= yy < h and xs + 1 < w and tbody[yy, xs + 1]:
                    tone(img, (gx == xs + 1) & (gy == yy), 1)
    # 横接缝
    for y in (66, 122):
        tone(img, tbody & ~fin & (gy == r(y)) & (gx > r(20)), -1.2)
    # 雨痕（同一个随机种子，位置 / 长度跟着缩）
    rng = np.random.default_rng(9)
    for _ in range(18):
        x = int(rng.integers(10, W - 10))
        y0 = int(rng.integers(44, 100))
        ln = int(rng.integers(6, 22))
        tone(img, body & (gx == r(x)) & (gy >= r(y0)) & (gy < r(y0) + max(3, r(ln))), -0.8)
    # 暗紫红条：从机头下方斜着往机尾抬，粗细最少 2 像素
    band = np.zeros(sh, bool)
    th = max(2, r(3))
    for x in range(w):
        yc = (116 - (x / k - 20) * 0.10) * k
        band[int(round(yc)):int(round(yc)) + th, x] = True
    band &= tbody & ~fin
    shade(img, band, STRIPE[0], STRIPE[1], STRIPE[2], z=40, gain=0.3, center=0.15, cell=(14, 4), seed=110, green=0, warm=0)
    # 座舱玻璃（青绿、很暗）：窗框暗一圈，左上一道反光
    shade(img, win, 0.24, 0.035, 185, z=40, gain=0.3, center=0.1, cell=(10, 10), seed=101, green=0.4, warm=0)
    tone(img, win & (gy < r(66)), 1)
    tone(img, dilate(win, max(1, r(2))) & ~win & body, -1.5)
    # 玻璃上的两根斜撑（同 strut_mask，粗细最少 1 像素）
    sw = max(1, r(2))
    struts = np.zeros(sh, bool)
    for (x0, y0), (x1, y1) in STRUTS:
        n = max(abs(x1 - x0), abs(y1 - y0))
        for i in range(n + 1):
            x = int(round((x0 + (x1 - x0) * i / n) * k))
            y = int(round((y0 + (y1 - y0) * i / n) * k))
            if 0 <= y < h:
                struts[y, x:x + sw] = True
    tone(img, struts & win, -1.5)
    c = cv(img)
    for (x0, y0, n, L) in ((50, 80, 7, 0.42), (58, 82, 4, 0.36)):
        for i in range(max(2, r(n))):
            px, py = r(x0) + i, r(y0) - i
            if 0 <= py < h and 0 <= px < w and win[py, px]:
                c.put(px, py, col(L, 0.030, 175))
    # 舱门轮廓 + 把手
    door = mrect(r(168), r(54), r(204), r(126), sh)
    tone(img, door & ~erode(door, 1), -1.8)
    c.rect(r(198), r(88), r(198) + max(1, r(4)) - 1, r(88), col(0.24, 0.010, 250))
    # 补丁
    m = mrect(r(120), r(96), r(140), r(106), sh)
    tone(img, m, 0.7)
    tone(img, m & ~erode(m, 1), -1)
    # 三道通风口
    for x in (226, 231, 236):
        c.rect(r(x), r(96), r(x) + max(1, r(3)) - 1, r(96) + max(2, r(6)) - 1, col(0.30, 0.010, 250))
    # 尾翼迎光的亮边
    tone(img, fin & ~erode(fin, 1) & (gx < r(300)), 1)
    img[~ship] = 0
    return limit_colors(img, 64)


def build_ship_out(preview_path=None):
    flat = _ext_flat()
    outs = {}
    for k in OUT_SCALES:
        a = ship_out(k, flat)
        outs[k] = a
        save(a, "ship_out_%02d" % int(round(k * 100)), SHIP_OUT)
    if preview_path:
        front = front_layer()
        ims = [Image.fromarray(front)] + [Image.fromarray(outs[k]) for k in OUT_SCALES]
        Wd = sum(i.width + 6 for i in ims)
        out = Image.new("RGBA", (Wd, H + 4), BG)
        xx = 0
        for i in ims:
            out.alpha_composite(i, (xx, H - i.height))
            xx += i.width + 6
        out.resize((out.width * 2, out.height * 2), Image.NEAREST).save(preview_path)
    return outs


# ============================================================ 会换状态的物件（每个一张横排帧条）
# 名字：(图左上角 x, y, 帧宽, 帧高)，图坐标
OBJ = {
    "cockpit_console": (18, 97, 38, 16),
    "cockpit_nav": (58, 96, 23, 18),
    "cockpit_repair_log": (82, 97, 9, 14),
    "cockpit_bell": (119, 79, 11, 17),
    "cockpit_toolbox": (195, 108, 22, 20),   # 地上、漏气口正下方（修漏气用的就是它）
    "cockpit_leak": (205, 79, 16, 15),
    "cockpit_leak_steam": (206, 60, 13, 22),
    "cockpit_converter": (156, 66, 46, 62),  # 10-29 往前挪到副驾驶座后面（作者：「炉子可以往前一点」）
    "cockpit_bag": (250, 107, 20, 21),
    "cockpit_phone": (47, 84, 8, 13),        # 通讯器：立在操纵台上沿、仪表旁（剧本 prop cockpit_phone by_gauges 才出现）
}


def P(name):
    x, y, w, h = OBJ[name]
    return x, y, w, h, Canvas(w, h)


def pshade(c: Canvas, name, mask, L0, C0, h0, **kw):
    x, y, w, h = OBJ[name]
    kw.setdefault("cell", (5, 5))
    shade(c.a, mask, L0, C0, h0, ox=x, oy=y, **kw)


def lm(c: Canvas, x0, y0, x1, y1):
    return mrect(x0, y0, x1, y1, shape=(c.h, c.w))


def ptone(c: Canvas, m, steps):
    tone(c.a, m, steps)


def strip(frames):
    w, h = frames[0].w, frames[0].h
    out = np.zeros((h, w * len(frames), 4), np.uint8)
    for i, f in enumerate(frames):
        out[:, i * w:(i + 1) * w] = f.a
    return out


# ---------- 操纵台仪表板：normal / dim / main_off
DIAL = {"normal": (0.56, 0.030, 150), "dim": (0.42, 0.022, 150), "main_off": (0.27, 0.010, 170)}
NEEDLE = col(0.18, 0.010, 200)


CONSOLE_STATES = ["normal", "dim", "main_off", "stone_shadow"]


def console_frames():
    frames = []
    for st0 in CONSOLE_STATES:
        # stone_shadow：调暗的仪表板（dim）上落着蓝色石头很淡的影子（晨在转化装置前举起石头的那几秒）
        st = "dim" if st0 == "stone_shadow" else st0
        x, y, w, h, c = P("cockpit_console")
        plate = lm(c, 0, 0, w - 1, h - 1)
        pshade(c, "cockpit_console", plate, 0.20, 0.010, 185, z=11, gain=0.5, center=0.2, cell=(8, 6), seed=200)
        ptone(c, lm(c, 0, 0, w - 1, 0), 1.2)
        ptone(c, lm(c, 0, h - 1, w - 1, h - 1), -1)
        # 三个圆表（5×5，表盘按状态亮 / 暗），针的角度三种状态不一样（关了就都落到最左）
        L0, C0, h0 = DIAL[st]
        for i, gx in enumerate((2, 9, 16)):
            disc = Canvas(w, h).ellipse(gx + 2, 4, 2.4, 2.4, (1, 1, 1))
            c.fill_mask(disc, col(L0, C0, h0))
            c.fill_mask(disc & ~erode(disc, 1), col(L0 - 0.08, C0 * 0.7, h0))
            ang = {"normal": (-0.6, 0.3, 0.9), "dim": (-0.9, -0.2, 0.4), "main_off": (-1.4, -1.4, -1.4)}[st][i]
            c.put(gx + 2, 4, NEEDLE)
            c.put(gx + 2 + int(round(1.6 * math.sin(ang))), 4 - int(round(1.6 * math.cos(ang))), NEEDLE)
        # 一排拨动开关（6 个，dim 时关了两个，main_off 全关 = 往下）
        for i in range(6):
            sx = 2 + i * 3
            on = {"normal": True, "dim": i not in (1, 4), "main_off": False}[st]
            c.put(sx, 11, col(0.13, 0.008, 210))
            c.put(sx, 10 if on else 12, col(0.36, 0.010, 90))
        # 右边：两个指示灯（暖黄 / 绿）、一块小读数窗、一个旋钮
        lamps = {"normal": (True, True), "dim": (True, False), "main_off": (False, False)}[st]
        c.rect(25, 2, 26, 3, col(0.62, 0.090, 75) if lamps[0] else col(0.24, 0.016, 70))
        c.rect(28, 2, 29, 3, col(0.58, 0.070, 150) if lamps[1] else col(0.22, 0.012, 160))
        rd = lm(c, 24, 6, 34, 9)
        c.fill_mask(rd, col(0.13, 0.012, 170))
        if st != "main_off":
            for xx in range(25, 34, 2 if st == "normal" else 3):
                c.put(xx, 7 + (xx // 3) % 2, col(0.45 if st == "normal" else 0.34, 0.06, 150))
        c.rect(31, 11, 33, 13, col(0.27, 0.010, 90))
        c.put(31, 11, col(0.35, 0.010, 90))
        # 旧：一条胶带压着一个坏了的开关、几道划痕
        c.rect(19, 9, 22, 10, TAPE)
        ptone(c, lm(c, 19, 10, 22, 10), -0.7)
        for (sx, sy) in ((5, 14), (6, 14), (12, 1), (13, 1), (14, 2)):
            ptone(c, lm(c, sx, sy, sx, sy), 1)
        if st0 == "stone_shadow":
            # 石头的影子：一个扁圆，里面暗一档、边上隔一个像素暗一档（很淡，不压住表盘的形状）
            core = Canvas(w, h).ellipse(19, 9, 4.2, 2.4, (1, 1, 1))
            rim = Canvas(w, h).ellipse(19, 9, 5.6, 3.4, (1, 1, 1)) & ~core
            yy, xx = np.mgrid[0:h, 0:w]
            ptone(c, core, -0.9)
            ptone(c, rim & ((xx + yy) % 2 == 0), -0.9)
        frames.append(c)
    return frames, CONSOLE_STATES


# ---------- 导航屏：stable / route_broken / detour / fuel_short / zoom / river_in_range / landing_zone
PH_BG = (0.17, 0.030, 165)
PH = col(0.62, 0.075, 150)        # 亮线（暗绿荧光，不是蓝）
PH_D = col(0.40, 0.055, 155)      # 暗线
PH_W = col(0.66, 0.085, 80)       # 警告（暗琥珀）
NAV_STATES = ["stable", "route_broken", "detour", "fuel_short", "zoom", "river_in_range", "landing_zone"]


def nav_frames():
    frames = []
    for st in NAV_STATES:
        x, y, w, h, c = P("cockpit_nav")
        box = lm(c, 0, 0, w - 1, h - 1)
        pshade(c, "cockpit_nav", box, 0.22, 0.010, 185, z=12, gain=0.5, center=0.2, cell=(6, 6), seed=210)
        ptone(c, lm(c, 0, 0, w - 1, 0), 1.2)
        ptone(c, lm(c, w - 1, 0, w - 1, h - 1), -1)
        # 屏：17×11（x 3..19, y 2..12）
        sx0, sy0, sx1, sy1 = 3, 2, 19, 12
        scr = lm(c, sx0, sy0, sx1, sy1)
        c.fill_mask(scr, col(*PH_BG))
        ptone(c, lm(c, sx0, sy0, sx1, sy0) | lm(c, sx0, sy0, sx0, sy1), -0.6)
        # 屏下：燃料刻度条（14 格），下面一排两个小按钮
        fuel = {"stable": 9, "route_broken": 9, "detour": 9, "fuel_short": 5, "zoom": 9, "river_in_range": 7,
                "landing_zone": 6}[st]
        for i in range(14):
            c.put(sx0 + 1 + i, 14, PH_D if i < fuel else col(0.15, 0.010, 190))
        c.put(4, 16, col(0.30, 0.010, 90))
        c.put(18, 16, col(0.30, 0.010, 90))
        ship, tgt = (sx0 + 2, 9), (sx1 - 3, 5)

        def dots(p0, p1, color=PH_D, every=2):
            n = max(abs(p1[0] - p0[0]), abs(p1[1] - p0[1]))
            for k in range(0, n + 1, every):
                c.put(int(round(p0[0] + (p1[0] - p0[0]) * k / n)), int(round(p0[1] + (p1[1] - p0[1]) * k / n)), color)

        def target(cx, cy):
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                c.put(cx + dx, cy + dy, PH)

        def plane(px, py):
            c.put(px, py, PH)
            c.put(px - 1, py, PH_D)

        def hatch(x0, y0, x1, y1):
            for yy in range(y0, y1 + 1):
                for xx in range(x0, x1 + 1):
                    if (xx + yy) % 3 == 0:
                        c.put(xx, yy, PH_D)

        if st == "stable":
            dots(ship, tgt)
            plane(*ship)
            target(*tgt)
        elif st == "route_broken":
            hatch(9, 3, 12, 11)
            dots(ship, (8, 7), PH_D, 2)
            dots((13, 6), tgt, PH_D, 2)
            for d in (-1, 0, 1):                                   # 断在碎石带上：一个 ×
                c.put(10 + d, 7 + d, PH_W)
                c.put(10 + d, 7 - d, PH_W)
            plane(*ship)
            target(*tgt)
        elif st == "detour":
            hatch(9, 5, 12, 11)
            pts = [ship, (7, 5), (9, 3), (13, 3), (15, 4), tgt]
            for p0, p1 in zip(pts, pts[1:]):
                dots(p0, p1, PH, 1)
            plane(*ship)
            target(*tgt)
        elif st == "fuel_short":
            hatch(9, 5, 12, 11)
            pts = [ship, (7, 5), (9, 3), (13, 3)]
            for p0, p1 in zip(pts, pts[1:]):
                dots(p0, p1, PH, 1)
            dots((13, 3), tgt, PH_D, 2)
            c.put(13, 2, PH_W)                                     # 燃料够到的地方：一个琥珀色记号
            c.put(13, 4, PH_W)
            plane(*ship)
            target(*tgt)
            for i in range(fuel, fuel + 3):
                c.put(sx0 + 1 + i, 14, PH_W)
        elif st == "zoom":
            hatch(4, 2, 18, 12)                                   # 放大：整屏是碎石带
            for (rx, ry) in ((7, 4), (12, 6), (15, 9), (9, 10), (16, 3)):
                c.put(rx, ry, PH)
                c.put(rx + 1, ry, PH_D)
            plane(5, 8)
            c.rect(4, 7, 4, 9, PH_D)
        elif st == "river_in_range":
            dots(ship, tgt, PH, 1)
            for dx, dy in ((0, -2), (2, 0), (0, 2), (-2, 0), (1, -1), (1, 1), (-1, 1), (-1, -1)):
                c.put(tgt[0] + dx, tgt[1] + dy, PH)                  # 目的地变成一个圈
            plane(*ship)
        elif st == "landing_zone":
            for xx in range(sx0 + 1, sx1):                         # 地平线（星球的弧）+ 一块着陆区方框
                yy = 10 - int(round(2.5 * math.sin(math.pi * (xx - sx0) / (sx1 - sx0))))
                c.put(xx, yy, PH_D)
            c.rect(10, 5, 13, 5, PH)
            c.rect(10, 7, 13, 7, PH)
            c.put(10, 6, PH)
            c.put(13, 6, PH)
            c.put(11, 3, PH_W)
            c.put(12, 3, PH_W)
        # 屏幕左上一道很淡的反光
        c.put(sx0 + 1, sy0 + 1, col(0.27, 0.030, 165))
        frames.append(c)
    return frames, NAV_STATES


# ---------- 维修记录：none / check_1 / check_2（贴在操纵台右边沿的一张纸，上面一条胶带）
def repair_frames():
    frames = []
    for st in ("none", "check_1", "check_2"):
        x, y, w, h, c = P("cockpit_repair_log")
        paper = Canvas(w, h).poly([(0, 1), (w - 2, 1), (w - 1, h - 2), (w - 2, h - 1), (1, h - 1)], (1, 1, 1))
        pshade(c, "cockpit_repair_log", paper, 0.44, 0.016, 85, z=13, gain=0.5, center=0.2, cell=(4, 4), seed=220)
        ptone(c, paper & lm(c, w - 3, h - 4, w - 1, h - 1), -1)          # 右下角卷起来
        c.rect(2, 0, 6, 1, TAPE)
        for i, ly in enumerate((4, 7, 10)):
            c.rect(1, ly, 2, ly + 1, col(0.30, 0.012, 80))                 # 小方框
            c.put(1, ly, col(0.40, 0.014, 85)) if False else None
            for xx in range(4, w - 2):
                if (xx + i) % 4:
                    c.put(xx, ly + (1 if i == 2 else 0), col(0.30, 0.012, 260))
        ticks = {"none": 0, "check_1": 1, "check_2": 2}[st]
        for i, ly in enumerate((4, 7)[:ticks]):
            c.put(1, ly, col(0.20, 0.014, 300))                          # 铅笔勾
            c.put(2, ly + 1, col(0.20, 0.014, 300))
            c.put(3, ly - 1, col(0.20, 0.014, 300))
        frames.append(c)
    return frames, ["none", "check_1", "check_2"]


# ---------- 铜铃 / 空绳圈（挂在驾驶座右边的铁钩上）
COPPER = (0.45, 0.058, 58)


# 帧：0 bell、1 empty_loop、2..9 rope_swing（空绳圈轻轻摆，100ms 一帧、0.8 秒一个来回）、10 moved（铃挪开一点，
# 别碰窗框：往右偏 1 像素、绳子斜着）、11 rope_short（绳圈收短了）
SWING = [1, 1, 0, 0, -1, -1, 0, 0]
BELL_STATES = {"bell": 0, "empty_loop": 1, "rope_swing": [2, 2 + len(SWING) - 1], "moved": 2 + len(SWING),
               "rope_short": 3 + len(SWING)}


def bell_frames():
    frames = []
    looks = [("bell", 0, 5), ("empty_loop", 0, 5)] + [("empty_loop", dx, 5) for dx in SWING] + [("bell", 1, 5), ("empty_loop", 0, 2)]
    for st, dx, cl in looks:
        x, y, w, h, c = P("cockpit_bell")
        cord = col(0.30, 0.020, 70)
        top = 5 - cl                                                      # 绳子短了：绳圈往上提
        if st == "bell":
            for yy in range(0, 5):
                c.put(5 + (1 if dx and yy >= 3 else 0), yy, cord)
            body = Canvas(w, h).poly([(4 + dx, 5), (7 + dx, 5), (8 + dx, 7), (8 + dx, 10), (9 + dx, 12), (2 + dx, 12),
                                      (3 + dx, 10), (3 + dx, 7)], (1, 1, 1))
            pshade(c, "cockpit_bell", body, COPPER[0], COPPER[1], COPPER[2], z=14, gain=0.6, center=0.2,
                   cell=(3, 3), seed=230, green=0.3)
            ptone(c, body & lm(c, 0, 0, 4 + dx, 9), 1)                    # 朝窗那边亮
            ptone(c, body & lm(c, 7 + dx, 6, w - 1, h - 1), -1.5)
            c.rect(2 + dx, 12, 9 + dx, 12, col(COPPER[0] - 0.12, COPPER[1], COPPER[2] - 8))
            c.put(5 + dx, 13, col(0.30, 0.040, 55))                        # 铃舌
            c.put(5 + dx, 14, col(0.36, 0.050, 58))
            c.put(4 + dx, 7, col(0.66, 0.060, 75))                         # 一点高光
        else:
            # 只剩一个绳圈：从钩子垂下来，绕一圈（摆的时候钩子不动，越往下偏得越多）
            for yy in range(0, cl):
                c.put(5 + (dx if yy >= 3 else 0), yy, cord)
            loop = [(4, 5), (3, 6), (3, 7), (3, 8), (4, 9), (5, 9), (6, 9), (7, 8), (7, 7), (7, 6), (6, 5)]
            for (px, py) in loop:
                c.put(px + dx, py - top, cord)
            c.put(6 + dx, 10 - top, cord)
            c.put(6 + dx, 11 - top, col(0.26, 0.018, 70))
        frames.append(c)
    return frames, BELL_STATES


# ---------- 弥洛给的工具盒：closed / open
BOX = (0.27, 0.030, 40)        # 暗锈红褐的铁皮盒


def toolbox_frames():
    frames = []
    for st in ("closed", "open"):
        x, y, w, h, c = P("cockpit_toolbox")
        body = lm(c, 1, 10, w - 2, h - 1)
        pshade(c, "cockpit_toolbox", body, BOX[0], BOX[1], BOX[2], z=8, gain=0.5, center=0.15, cell=(5, 4), seed=240)
        ptone(c, lm(c, 1, h - 1, w - 2, h - 1), -1)
        ptone(c, lm(c, w - 2, 10, w - 2, h - 1), -1)
        c.rect(1, 14, w - 2, 14, col(BOX[0] - 0.06, BOX[1], BOX[2]))      # 腰线
        c.rect(9, 12, 12, 13, col(0.36, 0.012, 90))                      # 搭扣
        # 一块刮掉漆的地方、一张弥洛写的小标签（暗纸片）
        c.rect(3, 16, 6, 17, col(0.33, 0.016, 85))
        ptone(c, lm(c, 15, 17, 18, 18), 0.8)
        if st == "closed":
            lid = lm(c, 0, 8, w - 1, 10)
            pshade(c, "cockpit_toolbox", lid, BOX[0] + 0.03, BOX[1], BOX[2], z=8, gain=0.5, center=0.15, cell=(5, 3),
                   seed=241)
            ptone(c, lm(c, 0, 8, w - 1, 8), 1.2)
            c.rect(7, 5, 14, 5, col(0.24, 0.010, 190))                    # 提手
            c.put(7, 6, col(0.24, 0.010, 190))
            c.put(7, 7, col(0.24, 0.010, 190))
            c.put(14, 6, col(0.24, 0.010, 190))
            c.put(14, 7, col(0.24, 0.010, 190))
        else:
            # 盖子往后翻起来立在后面（细细一条），里面一层托盘：扳手头、螺丝刀柄、一卷胶带、钳子
            lid = lm(c, w - 4, 0, w - 2, 10)
            pshade(c, "cockpit_toolbox", lid, BOX[0] + 0.02, BOX[1], BOX[2], z=8, gain=0.5, center=0.15,
                   cell=(3, 5), seed=242)
            ptone(c, lm(c, w - 4, 0, w - 4, 10), 1)
            c.rect(1, 10, w - 2, 10, col(0.12, 0.010, 220))                # 盒口里面的暗
            c.rect(3, 7, 4, 10, col(0.40, 0.010, 190))                      # 扳手
            c.rect(2, 6, 5, 6, col(0.44, 0.010, 190))
            c.put(3, 6, col(0.12, 0.010, 220))
            c.rect(7, 8, 8, 10, col(0.40, 0.060, 40))                       # 螺丝刀柄（暗红）
            c.put(7, 7, col(0.46, 0.010, 190))
            c.rect(10, 8, 12, 10, TAPE)                                     # 一卷胶带
            c.put(11, 9, col(0.14, 0.010, 220))
            c.rect(14, 9, 16, 10, col(0.34, 0.010, 190))                    # 钳子
            c.put(15, 8, col(0.34, 0.010, 190))
        frames.append(c)
    return frames, ["closed", "open"]


# ---------- 右侧机身接口：default / steam / fixed（steam 时另有 cockpit_leak_steam 冒白汽）
def leak_frames():
    frames = []
    for st in ("default", "steam", "fixed"):
        x, y, w, h, c = P("cockpit_leak")
        # 接口：管子在这里断开接上，一个方法兰（4 颗螺丝），往舱壁里伸一根短支管
        fl = lm(c, 5, 2, 10, 12)
        pshade(c, "cockpit_leak", fl, 0.27, 0.012, 100, z=6, gain=0.5, center=0.15, cell=(3, 4), seed=250)
        ptone(c, lm(c, 5, 2, 10, 2), 1.2)
        ptone(c, lm(c, 10, 2, 10, 12), -1)
        stub = lm(c, 7, 12, 8, h - 1)
        pshade(c, "cockpit_leak", stub, 0.22, 0.010, 100, z=5, gain=0.4, center=0.15, cell=(2, 3), seed=251)
        for (bx, by) in ((6, 3), (9, 3), (6, 11), (9, 11)):
            c.put(bx, by, col(0.36, 0.010, 90))
        # 两头接着管子（和舱壁上的管同一高度 y=86 → 局部 7..9）
        for xx in list(range(0, 5)) + list(range(11, w)):
            c.put(xx, 7, col(0.32, 0.014, 90))
            c.put(xx, 8, col(0.27, 0.014, 90))
            c.put(xx, 9, col(0.22, 0.014, 90))
        if st == "steam":
            c.put(9, 3, col(0.14, 0.010, 220))                              # 一颗螺丝松掉（只剩孔）
            c.rect(10, 5, 10, 9, col(0.12, 0.010, 220))                     # 法兰和管子之间裂开一道缝
            c.put(11, 4, col(0.36, 0.010, 90))                              # 松出来的螺丝歪在外面
        elif st == "fixed":
            c.rect(4, 6, 11, 10, TAPE)                                      # 缠了一圈新胶带 + 一个亮一点的新卡箍
            ptone(c, lm(c, 4, 6, 11, 6), 1)
            ptone(c, lm(c, 4, 10, 11, 10), -1)
            c.rect(7, 5, 8, 11, col(0.42, 0.010, 190))
            c.put(7, 4, col(0.50, 0.010, 190))
        frames.append(c)
    return frames, ["default", "steam", "fixed"]


def steam_frames():
    """细白汽，从接口那道缝往上斜着飘（往机尾方向偏一点），4 帧循环。不透明的浅灰绿小点，不刺眼。"""
    x, y, w, h, _ = P("cockpit_leak_steam")
    paths = [
        [(9, 21), (10, 20), (10, 19), (11, 18), (11, 17), (10, 15), (10, 14), (11, 12), (11, 11), (10, 9), (9, 7), (9, 6)],
        [(9, 21), (10, 20), (11, 19), (11, 18), (10, 16), (10, 15), (11, 13), (12, 12), (12, 10), (11, 8), (10, 6), (10, 4)],
        [(9, 21), (10, 20), (10, 19), (10, 18), (11, 16), (12, 15), (12, 13), (11, 11), (10, 10), (10, 8), (11, 6), (12, 3)],
        [(9, 21), (9, 20), (10, 19), (11, 18), (11, 17), (11, 15), (10, 13), (9, 12), (9, 10), (10, 8), (11, 7), (11, 5)],
    ]
    frames = []
    for i, pts in enumerate(paths):
        c = Canvas(w, h)
        for j, (px, py) in enumerate(pts):
            L = 0.70 if j < 5 else (0.58 if j < 9 else 0.46)
            c.put(px, py, col(L, 0.012, 165))
            if j in (2, 6) and i % 2 == 0:
                c.put(px - 1, py, col(L - 0.12, 0.012, 170))
        frames.append(c)
    return frames


# ---------- 转化装置：closed / idle / glow / burn / card_curl
CONV = (0.27, 0.014, 170)      # 比旁边的家当亮一点（可互动的东西要一眼找得到）
EMBER = {0: None, 1: (0.36, 0.070, 55), 2: (0.52, 0.100, 62), 3: (0.68, 0.110, 72)}


def converter_frames():
    """一个立着的旧铁柜（正侧面）：上面一块带铰链的盖子，正面一个圆的小观察窗，最下面一条炉栅（光从这里漏出来，照亮地面）。
    closed：全暗；idle：炉栅里一点余烬；glow：盖子打开（往后翻起），柜口和炉栅亮，地上一片暖光；
    burn：盖子关着，炉栅和观察窗很亮，盖缝漏光；card_curl：观察窗里一张卷起来的卡片剪影在火光里。"""
    frames = []
    st_list = ["closed", "idle", "glow", "burn", "card_curl"]
    for st in st_list:
        x, y, w, h, c = P("cockpit_converter")
        lvl = {"closed": 0, "idle": 1, "glow": 2, "burn": 3, "card_curl": 3}[st]
        bx0, bx1, by0 = 8, 37, 26                         # 柜身（局部坐标）；底边 = h-1（地板上）
        body = lm(c, bx0, by0, bx1, h - 3)
        pshade(c, "cockpit_converter", body, CONV[0], CONV[1], CONV[2], z=10, gain=0.55, center=0.12,
               cell=(7, 8), seed=260)
        ptone(c, lm(c, bx0, by0, bx0, h - 3), 1)
        ptone(c, lm(c, bx1, by0, bx1, h - 3), -1)
        # 脚
        for fx in (bx0 + 1, bx1 - 3):
            c.rect(fx, h - 2, fx + 2, h - 1, col(0.16, 0.008, 200))
        # 铆钉、板缝、一张褪色的警示标（暗琥珀小方块）
        c.rect(bx0 + 1, by0 + 14, bx1 - 1, by0 + 14, col(0.18, 0.010, 190))
        for rx in range(bx0 + 2, bx1, 5):
            ptone(c, lm(c, rx, by0 + 2, rx, by0 + 2), 1.5)
        c.rect(bx1 - 8, by0 + 17, bx1 - 4, by0 + 20, col(0.34, 0.040, 75))
        c.rect(bx1 - 7, by0 + 18, bx1 - 5, by0 + 18, col(0.24, 0.030, 70))
        # 观察窗（圆，5×5）
        win = Canvas(w, h).ellipse(bx0 + 9, by0 + 7, 2.6, 2.6, (1, 1, 1))
        ring = dilate(win, 1) & ~win
        c.fill_mask(ring, col(0.30, 0.012, 90))
        if lvl == 0:
            c.fill_mask(win, col(0.12, 0.010, 220))
        else:
            c.fill_mask(win, col(*EMBER[lvl]))
            if st == "card_curl":                         # 卷起来的卡片：暗剪影，一角翘起
                for (px, py) in ((bx0 + 7, by0 + 8), (bx0 + 8, by0 + 8), (bx0 + 9, by0 + 8), (bx0 + 10, by0 + 7),
                                 (bx0 + 10, by0 + 6), (bx0 + 8, by0 + 7)):
                    c.put(px, py, col(0.20, 0.020, 40))
            else:
                c.put(bx0 + 8, by0 + 6, col(min(0.8, EMBER[lvl][0] + 0.12), 0.08, 80))
        # 炉栅（最下面一条，4 根竖栅）
        gy0, gy1 = h - 9, h - 5
        grate = lm(c, bx0 + 4, gy0, bx1 - 4, gy1)
        c.fill_mask(grate, col(0.11, 0.010, 220) if lvl == 0 else col(*EMBER[lvl]))
        if lvl >= 2:
            c.fill_mask(lm(c, bx0 + 6, gy0 + 1, bx1 - 6, gy1), col(*EMBER[min(3, lvl + 1)]))
        for gx in range(bx0 + 6, bx1 - 4, 4):
            c.rect(gx, gy0, gx, gy1, col(0.20, 0.010, 200))
        # 光从下面来：柜身下半被炉栅照亮（亮 1~2 档、偏暖），地上一片暖光（贴着地板最下两行）
        if lvl >= 1:
            warm = lm(c, bx0 + 1, gy0 - 2, bx1 - 1, gy0 - 1) & body
            lab_shift(c.a, warm, 0.018 * lvl, 0.012 * lvl, WARM_H)
            if lvl >= 2:
                lab_shift(c.a, lm(c, bx0 + 2, gy0 - 4, bx1 - 2, gy0 - 3) & body, 0.012 * lvl, 0.008 * lvl, WARM_H)
            half = {1: 8, 2: 16, 3: 21}[lvl]
            cx = (bx0 + bx1) // 2
            for yy, hw in ((h - 2, half), (h - 1, half + 2)):
                for xx in range(cx - hw, cx + hw + 1):
                    if 0 <= xx < w and not (c.a[yy, xx, 3] and (abs(xx - bx0 - 2) < 3 or abs(xx - bx1 + 2) < 3)):
                        k = 1 - abs(xx - cx) / (hw + 1)
                        Lg = 0.20 + 0.06 * lvl * k
                        c.put(xx, yy, col(Lg, 0.03 + 0.02 * lvl * k, 60))
        # 盖子
        lid_c = (CONV[0] + 0.03, CONV[1], CONV[2])
        if st == "glow":
            # 打开：盖子往后翻起，立在柜顶右边（竖着的一条），柜口里面是暖光
            lid = Canvas(w, h).poly([(bx1 - 2, by0 - 1), (bx1 + 1, by0 - 1), (bx1 + 7, by0 - 15), (bx1 + 4, by0 - 16)],
                                    (1, 1, 1))
            pshade(c, "cockpit_converter", lid, lid_c[0], lid_c[1], lid_c[2], z=10, gain=0.5, center=0.12,
                   cell=(4, 6), seed=261)
            c.rect(bx1 - 1, by0 - 1, bx1 + 1, by0, col(0.18, 0.010, 200))
            mouth = lm(c, bx0 + 1, by0, bx1 - 4, by0 + 1)
            c.fill_mask(mouth, col(*EMBER[3]))
            c.fill_mask(lm(c, bx0 + 3, by0, bx1 - 6, by0), col(0.78, 0.090, 82))
            # 柜口往上冒的一点暖光（几粒亮点，脚本特效的做法）
            for (px, py) in ((bx0 + 8, by0 - 3), (bx0 + 14, by0 - 5), (bx0 + 20, by0 - 2), (bx0 + 11, by0 - 8),
                             (bx0 + 18, by0 - 10)):
                c.put(px, py, col(0.62, 0.090, 72))
        else:
            lid = lm(c, bx0 - 1, by0 - 3, bx1 + 1, by0 - 1)
            pshade(c, "cockpit_converter", lid, lid_c[0], lid_c[1], lid_c[2], z=10, gain=0.5, center=0.12,
                   cell=(6, 3), seed=262)
            ptone(c, lm(c, bx0 - 1, by0 - 3, bx1 + 1, by0 - 3), 1.2)
            c.rect(bx0 + 3, by0 - 4, bx0 + 6, by0 - 4, col(0.30, 0.010, 90))    # 盖子上的把手
            c.rect(bx1 - 1, by0 - 2, bx1 + 1, by0 - 1, col(0.18, 0.010, 200))   # 铰链
            if lvl == 3:
                c.rect(bx0 + 1, by0 - 1, bx1 - 3, by0 - 1, col(*EMBER[2]))       # 盖缝漏光
                for (px, py) in ((bx0 + 6, by0 - 6), (bx0 + 22, by0 - 7)):
                    c.put(px, py, col(0.56, 0.080, 70))
        # 管子从上面接进来（和舱壁上那根对齐：图 x 224..226 → 局部 20..22）
        top = by0 - 4 if st != "glow" else by0 - 1
        c.rect(20, 20, 22, top, col(0.27, 0.016, 90))
        c.rect(20, 20, 20, top, col(0.32, 0.016, 90))
        c.rect(19, top, 23, top, col(0.20, 0.010, 200))                       # 接头
        frames.append(c)
    return frames, st_list


def lab_shift(img, m, dL, dC, hue):
    sel = m & (img[..., 3] > 0)
    if not sel.any():
        return
    lab = srgb_to_oklab(img[sel][:, :3])
    lab[:, 0] += dL
    lab[:, 1] += dC * math.cos(math.radians(hue))
    lab[:, 2] += dC * math.sin(math.radians(hue))
    img[sel, :3] = oklab_to_srgb(lab)


# ---------- 背包（晨的旧帆布包，塌在网兜里）
def bag_frames():
    x, y, w, h, c = P("cockpit_bag")
    body = Canvas(w, h).poly([(3, 6), (8, 3), (14, 4), (17, 8), (18, h - 1), (1, h - 1), (2, 10)], (1, 1, 1))
    pshade(c, "cockpit_bag", body, 0.40, 0.022, 130, z=9, gain=0.5, center=0.15, cell=(5, 5), seed=270)
    flap = Canvas(w, h).poly([(4, 6), (9, 4), (14, 5), (16, 9), (15, 12), (4, 12)], (1, 1, 1))
    pshade(c, "cockpit_bag", flap, 0.45, 0.022, 125, z=10, gain=0.5, center=0.15, cell=(4, 4), seed=271)
    ptone(c, flap & ~erode(flap, 1) & lm(c, 0, 12, w - 1, 12), -1.2)
    ptone(c, body & lm(c, 0, h - 3, w - 1, h - 1), -1)
    c.rect(9, 12, 10, 14, col(0.36, 0.012, 90))                       # 扣子
    for yy in range(4, 16):                                           # 一根背带搭在外面
        c.put(17 - (yy - 4) // 5, yy + 3, col(0.24, 0.016, 60))
    return [c], ["default"]


# ---------- 通讯器：立在操纵台上沿、仪表旁（背包图标那张，压暗一点放进舱里的光）
def phone_frames():
    x, y, w, h, c = P("cockpit_phone")
    ico = Canvas.from_rows(ICON_COMMUNICATOR, ICON_PAL).trim()
    a = ico.a.copy()
    a[..., :3] = (a[..., :3].astype(np.float32) * 0.78).astype(np.uint8)
    c.a[h - a.shape[0]:, :a.shape[1]] = a
    ptone(c, lm(c, 0, h - 2, w - 1, h - 1), -0.8)                    # 底下两行靠着台面，暗一档
    return [c], {"by_gauges": 0}


PROP_DEFAULT = {"cockpit_phone": "hidden"}     # 没有剧本 prop 之前的状态（hidden = 不显示）

PROP_BUILDERS = {
    "cockpit_console": console_frames,
    "cockpit_nav": nav_frames,
    "cockpit_repair_log": repair_frames,
    "cockpit_bell": bell_frames,
    "cockpit_toolbox": toolbox_frames,
    "cockpit_leak": leak_frames,
    "cockpit_converter": converter_frames,
    "cockpit_bag": bag_frames,
    "cockpit_phone": phone_frames,
}


def build_props():
    objects = {}
    out = {}
    for name, fn in PROP_BUILDERS.items():
        frames, states = fn()
        save(strip(frames), name)
        x, y, w, h = OBJ[name]
        if not isinstance(states, dict):
            states = {s: i for i, s in enumerate(states)}
        objects[name] = {"x": rel(x), "y": y - H, "w": w, "h": h, "frames": len(frames),
                         "states": states, "px": [x, y]}
        if name in PROP_DEFAULT:
            objects[name]["default"] = PROP_DEFAULT[name]
        out[name] = frames
        PROP_STATES[name] = states
    frames = steam_frames()
    save(strip(frames), "cockpit_leak_steam")
    x, y, w, h = OBJ["cockpit_leak_steam"]
    objects["cockpit_leak_steam"] = {"x": rel(x), "y": y - H, "w": w, "h": h, "frames": len(frames), "fps": 10,
                                     "loop": True, "on": "cockpit_leak=steam", "px": [x, y]}
    out["cockpit_leak_steam"] = frames
    return objects, out


# ============================================================ 写 cockpit.json
def rel(x, y=None):
    """图坐标 → 相对锚点（图底边中点；y 往上为负）。"""
    if y is None:
        return x - CX
    return [x - CX, y - H]


# 物件：名字 → (图左上角 x, y)；尺寸在画的时候填
OBJ_POS = {}
MARKERS_PX = {
    # 名字：(人站的 x, 地面 y)；地面 y = 那件东西的底边 / 人站的那一行
    # 窗 / 操纵台 / 维修记录挤在机头那一小段：互动点至少隔 5 像素（hotspots.gd 的 SAME_X = 4，再近就只留一个）
    "cockpit_window": (89, FL),
    "cockpit_console": (84, FL),
    "cockpit_nav": (78, FL),
    "cockpit_repair_log": (95, FL),
    "cockpit_seat": (104, FL),
    "cockpit_bell": (122, FL),
    "cockpit_copilot": (142, FL),
    "cockpit_converter": (178, FL),
    "cockpit_toolbox": (204, FL),
    "cockpit_leak": (213, FL),
    "cockpit_bag": (259, FL),
}
WALK = (84, 260)               # 晨（中心 x）能走的范围，图坐标


def write_json(objects: dict):
    meta = {
        "size": [W, H],
        "anchor": "底边中点。所有 x / y 都相对锚点（x 往右、y 往上为负）；同时给了 px（图左上角起的像素坐标）",
        "floor_offset": FL - H,
        "floor_px": FL,
        "walk_min": rel(WALK[0]),
        "walk_max": rel(WALK[1]),
        "walk_px": list(WALK),
        "window": {"x": WIN_RECT[0] - CX, "y": WIN_RECT[1] - H, "w": WIN_W, "h": WIN_H,
                   "px": [WIN_RECT[0], WIN_RECT[1], WIN_W, WIN_H],
                   "poly_px": [list(p) for p in WIN_POLY],
                   "states": WINDOW_STATES,
                   "mask": "window_mask.png",
                   "debris": ["debris_a", "debris_b", "debris_c", "debris_d", "debris_e"],
                   "airflow": "airflow.png",
                   "note": "window_<state>.png 都是 w×h，左上角对齐这里，画在 cockpit_back 下面；已经按窗洞形状（poly）裁好，窗洞外是透明的。"
                           "避障时 debris_*.png / airflow.png 也画在 back 下面，但窗矩形左上角在机身外面，"
                           "所以这一层要用 window_mask.png 裁（Godot：一个 Sprite2D 放 window_mask、clip_children = CLIP_CHILDREN_ONLY，碎石当它的子节点）。"
                           "airflow.png 和窗一样宽，横向循环滚动；碎石从左右两边飘进来。"},
        "layers": [
            "（屏幕底色：很暗的灰绿，比如 #101614）",
            "window_<state>（+ 避障时的 airflow / debris_*）",
            "cockpit_back",
            "objects（cockpit_console / cockpit_nav / cockpit_repair_log / cockpit_bell / cockpit_toolbox / cockpit_leak / cockpit_leak_steam / cockpit_converter / cockpit_bag / cockpit_phone）",
            "人物",
            "cockpit_front（机身外壳；进舱淡出 / 出舱淡入，舱里时不显示）",
        ],
        "markers": {k: {"x": rel(v[0]), "ground_y": v[1] - H, "px": [v[0], v[1]]} for k, v in MARKERS_PX.items()},
        "objects": objects,
        "hotspots": {k.replace("cockpit_", ""): rel(v[0]) for k, v in MARKERS_PX.items()},
        "note": "objects 的 x,y = 左上角（相对锚点），w = 帧宽，frames = 横排帧数；states = 每个状态对应第几帧（多帧动画写成 [起, 止]）；"
                "fps = 动画帧率（100ms 一帧 = 10）。cockpit_leak_steam 只在 cockpit_leak = steam 时显示。"
                "默认状态：console normal、nav stable、converter closed、leak default、toolbox closed、repair_log none、bell bell；"
                "写了 default 的按它（cockpit_phone 默认 hidden，剧本 prop by_gauges 才出现）。",
    }
    (OUT / "cockpit.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


def save(a, name, out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a.astype(np.uint8), "RGBA").save(out / f"{name}.png")


def build_section():
    back = back_layer()
    front = front_layer()
    save(back, "cockpit_back")
    save(front, "cockpit_front")
    return back, front


# ============================================================ 窗外（57×39，窗洞外接矩形大小；不透明）
WINDOW_STATES = ["forest_canopy", "canopy_fall", "forest_below", "forest_far", "turning", "clouds", "debris_wall",
                 "clouds_fast", "river_planet", "river_city", "clocktower", "boats", "tilt", "skid", "channel", "crate"]
FLIGHT = ROOT / "art" / "flight"


def _load(p):
    return np.array(Image.open(p).convert("RGBA"))


def _over(dst, src, x, y):
    """src 硬边贴到 dst（alpha>0 的像素覆盖），超出边界裁掉。"""
    h, w = src.shape[:2]
    H2, W2 = dst.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W2, x + w), min(H2, y + h)
    if x1 <= x0 or y1 <= y0:
        return dst
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    m = s[..., 3] > 0
    dst[y0:y1, x0:x1][m] = s[m]
    dst[y0:y1, x0:x1, 3][m] = 255
    return dst


def _scale(a, k):
    im = Image.fromarray(a)
    return np.array(im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.NEAREST))


def _flight_sky():
    sky = _load(FLIGHT / "sky_green.png")
    return sky


def _flight_clouds():
    base = _flight_sky().copy()
    for n in ("clouds_far", "clouds_mid", "clouds_near"):
        _over(base, _load(FLIGHT / f"{n}.png")[:, :480], 0, 0)
    return base


def _crop(a, x, y, w=None, h=None):
    w, h = w or WIN_W, h or WIN_H
    return a[y:y + h, x:x + w].copy()


def _fill(w=None, h=None, c=(0, 0, 0)):
    w, h = w or WIN_W, h or WIN_H
    a = np.zeros((h, w, 4), np.uint8)
    a[..., :3] = c
    a[..., 3] = 255
    return a


def _vgrad(a, y0, y1, L0, L1, C, hue, steps=4):
    """竖向分档的天：y0..y1 从 L0 到 L1，分 steps 档（硬边）。"""
    for y in range(y0, y1):
        t = (y - y0) / max(1, (y1 - y0 - 1))
        k = round(t * (steps - 1)) / (steps - 1)
        a[y, :, :3] = col(L0 + (L1 - L0) * k, C, hue)
        a[y, :, 3] = 255


def _cone_trees(a, base_y, n, hmin, hmax, colors, seed, xs=None, w=None):
    """一排很小的针叶树尖（三角），近的大、暗；colors = (主色, 受光边)。"""
    rng = np.random.default_rng(seed)
    Wd = a.shape[1] if w is None else w
    xs = xs if xs is not None else np.sort(rng.integers(-3, Wd + 3, n))
    c = cv(a)
    for x in xs:
        h = int(rng.integers(hmin, hmax + 1))
        hw = max(1, h // 3)
        c.poly([(x, base_y - h), (x + hw, base_y), (x - hw, base_y)], colors[0])
        c.put(int(x), base_y - h, colors[1])


def _rotate(a, deg):
    im = Image.fromarray(a)
    r = im.rotate(deg, resample=Image.NEAREST, expand=False)
    return np.array(r)


# 森林的几档绿（和 launch_forest / 森林章节同一套暗青绿）
FOR_D = col(0.17, 0.020, 175)
FOR_M = col(0.21, 0.022, 168)
FOR_L = col(0.26, 0.024, 160)
FOR_HAZE = col(0.30, 0.020, 165)


def w_forest_canopy():
    a = _crop(_flight_sky(), 200, 150)
    lf = _scale(_load(FLIGHT / "launch_forest.png"), 2)
    _over(a, lf[66:66 + WIN_H, 300:300 + WIN_W], 0, 0)
    # 最近的一棵树冠擦着窗边（左下一大块暗）
    c = cv(a)
    c.poly([(-2, 10), (10, 24), (6, 24), (16, 38), (-2, 38)], col(0.12, 0.016, 180))
    return a


def w_canopy_fall():
    a = _crop(_flight_sky(), 200, 165)
    lf = _load(FLIGHT / "launch_forest.png")
    _over(a, lf[30:30 + WIN_H, 120:120 + WIN_W], 0, 12)
    return a


def w_forest_below():
    """飞到树顶上面：地平线在上面，下面是一片俯看的树冠（一点点的尖，越远越小越灰），一块残骸留下的空地，
    空地旁一个很小的浅色点（鹿）。"""
    a = _crop(_flight_sky(), 230, 175)
    hz = 9
    a[hz:, :, :3] = FOR_D
    rows = [(hz + 3, 1, 2, FOR_HAZE), (hz + 6, 1, 2, FOR_L), (hz + 10, 2, 3, FOR_L), (hz + 15, 2, 4, FOR_M),
            (hz + 21, 3, 5, FOR_M), (hz + 28, 4, 6, FOR_M), (hz + 35, 4, 7, FOR_L)]
    a[hz:hz + 3, :, :3] = FOR_HAZE
    for i, (by, h0, h1, cc) in enumerate(rows):
        _cone_trees(a, by, 16 + i * 2, h0, h1, (cc, col(0.32, 0.020, 150)), seed=300 + i)
    c = cv(a)
    clear = c.poly([(22, 22), (31, 20), (38, 23), (36, 27), (27, 28), (20, 26)])
    a[clear, :3] = col(0.30, 0.016, 110)
    for (px, py) in ((27, 23), (28, 23), (29, 24), (30, 24), (26, 25)):     # 残骸烧过的暗痕
        c.put(px, py, col(0.18, 0.012, 60))
    c.put(34, 24, col(0.56, 0.030, 70))                                  # 鹿：一个很小的浅点
    c.put(34, 25, col(0.42, 0.025, 70))
    return a


def w_forest_far():
    a = _crop(_flight_sky(), 376, 34)
    hz = 30
    a[hz:, :, :3] = FOR_D
    a[hz:hz + 2, :, :3] = FOR_HAZE
    _cone_trees(a, hz + 3, 30, 1, 2, (FOR_L, FOR_HAZE), seed=310)
    _cone_trees(a, hz + 7, 22, 2, 3, (FOR_M, FOR_L), seed=311)
    _cone_trees(a, WIN_H + 1, 18, 3, 5, (FOR_M, FOR_L), seed=312)
    # 一条雾带
    a[hz - 3:hz - 1, :, :3] = col(0.22, 0.020, 165)
    return a


def w_turning():
    big = np.zeros((WIN_H + 30, WIN_W + 30, 4), np.uint8)
    sky = _crop(_flight_sky(), 240, 135, WIN_W + 30, WIN_H + 30)
    big[:] = sky
    hz = 34
    big[hz:, :, :3] = FOR_D
    big[hz:hz + 2, :, :3] = FOR_HAZE
    _cone_trees(big, hz + 4, 40, 1, 2, (FOR_L, FOR_HAZE), seed=320)
    _cone_trees(big, hz + 9, 30, 2, 3, (FOR_M, FOR_L), seed=321)
    _cone_trees(big, hz + 16, 26, 3, 5, (FOR_M, FOR_L), seed=322)
    big[hz - 4:hz - 2, :, :3] = col(0.22, 0.020, 165)
    r = _rotate(big, -14)
    return r[15:15 + WIN_H, 15:15 + WIN_W].copy()


def w_clouds():
    return _crop(_flight_clouds(), 60, 150)


def w_clouds_fast():
    a = _crop(_flight_clouds(), 250, 156)
    rng = np.random.default_rng(330)
    for _ in range(9):                                 # 横着的速度线（比云亮一档的虚线）
        y = int(rng.integers(2, WIN_H - 2))
        x0 = int(rng.integers(-10, WIN_W))
        ln = int(rng.integers(8, 20))
        Lb = float(srgb_to_oklab(a[y, max(0, min(WIN_W - 1, x0)), :3][None])[0, 0])
        for x in range(x0, x0 + ln):
            if 0 <= x < WIN_W and (x - x0) % 5 != 4:
                a[y, x, :3] = col(min(0.5, Lb + 0.06), 0.012, 170)
    return a


ROCK_C = [col(0.20, 0.022, 310), col(0.25, 0.024, 305), col(0.31, 0.022, 300), col(0.15, 0.018, 300)]


def debris_sprites():
    """碎石小图（给避障玩法在窗外飘）：从 art/flight/rock_* 缩一半 + 两块手画的小碎片。"""
    out = {}
    for n in ("rock_a", "rock_b", "rock_c"):
        r = _scale(_load(FLIGHT / f"{n}.png"), 0.5)
        r[r[..., 3] < 128] = 0
        r[r[..., 3] > 0, 3] = 255
        ys, xs = np.nonzero(r[..., 3])
        out["debris_" + n[-1]] = r[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    d = Canvas.from_rows([".aab.", "aabbc", ".abc.", "..d.."], {"a": ROCK_C[1], "b": ROCK_C[0], "c": ROCK_C[3],
                                                               "d": ROCK_C[3]})
    out["debris_d"] = d.a
    e = Canvas.from_rows([".ab", "aac", ".c."], {"a": ROCK_C[2], "b": ROCK_C[1], "c": ROCK_C[0]})
    out["debris_e"] = e.a
    return out


def airflow_strip():
    """淡淡的气流线：一条横穿窗的、轻轻起伏的虚线（暗的灰青绿，不透明的点，很稀），57×5。引擎横向滚它。"""
    a = np.zeros((5, WIN_W, 4), np.uint8)
    for x in range(WIN_W):
        y = 2 + int(round(1.4 * math.sin(x / WIN_W * 2 * math.pi)))
        if x % 4 in (0, 1):
            a[y, x, :3] = col(0.42 if x % 8 < 2 else 0.36, 0.022, 168)
            a[y, x, 3] = 255
    return a


def w_debris_wall():
    a = _crop(_flight_clouds(), 120, 160)
    rocks = debris_sprites()
    rng = np.random.default_rng(340)
    names = ["debris_a", "debris_b", "debris_c", "debris_d", "debris_e"]
    # 一整面墙：中间一条带子挤满碎石，远的（小、暗）先画
    for i in range(34):
        n = names[int(rng.integers(0, 5))] if i > 10 else names[3 + int(rng.integers(0, 2))]
        r = rocks[n]
        if i < 14:
            r = r.copy()
            m = r[..., 3] > 0
            lab = srgb_to_oklab(r[m][:, :3])
            lab[:, 0] -= 0.06
            r[m, :3] = oklab_to_srgb(lab)
        x = int(rng.integers(-8, WIN_W))
        y = int(rng.integers(2, 26)) + (i % 3)
        _over(a, r, x, y)
    return a


# 河流城市（清晨，灰绿；水是青灰，不是蓝）
R_SKY = (0.48, 0.020, 130)
R_WATER = (0.40, 0.026, 185)
R_WATER_L = (0.52, 0.026, 175)
R_ROOF = [(0.34, 0.010, 80), (0.40, 0.008, 90), (0.30, 0.010, 200), (0.44, 0.012, 70), (0.36, 0.014, 40)]


def w_river_planet():
    a = _fill(c=col(0.10, 0.014, 180))
    rng = np.random.default_rng(350)
    for _ in range(9):
        a[int(rng.integers(0, 20)), int(rng.integers(0, WIN_W)), :3] = col(0.5, 0.01, 150)
    c = cv(a)
    disc = Canvas(WIN_W, WIN_H).ellipse(34, 78, 56, 56, (1, 1, 1))
    a[disc, :3] = col(0.30, 0.030, 175)
    yy, xx = np.mgrid[0:WIN_H, 0:WIN_W]
    d = np.hypot(xx - 34, yy - 78)
    a[disc & (d > 52), :3] = col(0.38, 0.030, 170)                # 大气边亮一圈
    a[disc & (d > 55), :3] = col(0.46, 0.026, 165)
    land = disc & (smooth_noise(WIN_H, WIN_W, 9, 4, seed=351) > 0.15) & (d < 51)
    a[land, :3] = col(0.26, 0.022, 120)
    # 一条亮的大河弯过去
    for x in range(WIN_W):
        y = int(round(30 + 4 * math.sin(x / 9.0)))
        if disc[y, x] and d[y, x] < 52:
            a[y, x, :3] = col(0.48, 0.030, 175)
    halo = (~disc) & (d < 58)
    a[halo, :3] = col(0.16, 0.020, 175)
    return a


def _city(seed, scale=1.0, water_rows=((14, 3), (29, 2)), w=None, h=None):
    """俯看的城市：灰屋顶一块块排着，中间几条水道（青灰，偶尔一道亮），细桥横过水道。"""
    w, h = w or WIN_W, h or WIN_H
    a = _fill(w, h, col(0.26, 0.010, 200))
    rng = np.random.default_rng(seed)
    c = cv(a)
    y = 0
    while y < h:
        bh = int(rng.integers(3, 6) * scale)
        x = int(rng.integers(-3, 0))
        while x < w:
            bw = int(rng.integers(3, 8) * scale)
            L, C, hh = R_ROOF[int(rng.integers(0, len(R_ROOF)))]
            c.rect(x, y, x + bw - 2, y + bh - 2, col(L, C, hh))
            c.rect(x, y, x + bw - 2, y, col(L + 0.05, C, hh))
            x += bw
        y += bh
    for (wy, ww) in water_rows:
        for x in range(w):
            yy = wy + int(round(1.5 * math.sin(x / 7.0 + seed)))
            a[yy:yy + ww, x, :3] = col(*R_WATER)
            if x % 6 == 0:
                a[yy, x, :3] = col(*R_WATER_L)
        for bx in rng.integers(4, w - 4, 2):                   # 细桥
            a[wy - 2:wy + ww + 2, bx, :3] = col(0.46, 0.010, 80)
    return a


def w_river_city():
    a = _city(360)
    a[:5, :, :3] = col(*R_SKY)                                  # 远处一线天和雾
    a[5:7, :, :3] = col(0.40, 0.016, 140)
    return a


def w_clocktower():
    a = _city(370, scale=1.6, water_rows=((26, 6),))
    a[:3, :, :3] = col(*R_SKY)
    c = cv(a)
    # 广场被水淹了，只露出钟楼的一截：一根方塔 + 一个浅色钟面
    c.rect(36, 9, 42, 30, col(0.38, 0.016, 60))
    c.rect(36, 9, 36, 30, col(0.46, 0.016, 70))
    c.rect(35, 7, 43, 8, col(0.30, 0.012, 60))
    c.ellipse(39, 15, 2, 2, col(0.62, 0.016, 90))
    c.put(39, 14, col(0.25, 0.010, 60))
    c.put(40, 15, col(0.25, 0.010, 60))
    a[31:, 30:48, :3] = col(*R_WATER)
    for x in range(31, 47, 3):
        a[32, x, :3] = col(*R_WATER_L)
    return a


def w_boats():
    """地图上的跑道：一条笔直的宽水道，旧跑道的白线还在水下，上面停着一排小船。"""
    a = _city(380, water_rows=())
    a[12:30, :, :3] = col(*R_WATER)
    for x in range(0, WIN_W, 6):
        a[20:22, x:x + 3, :3] = col(0.48, 0.016, 170)          # 水下的跑道虚线
    c = cv(a)
    for i, bx in enumerate((4, 14, 25, 35, 47)):
        by = 14 + (i % 2) * 9
        c.rect(bx, by, bx + 6, by + 2, col(0.42, 0.030, 50))
        c.rect(bx + 1, by + 3, bx + 5, by + 3, col(0.30, 0.020, 190))   # 船下的影
        c.rect(bx + 2, by - 1, bx + 3, by, col(0.52, 0.012, 90))
    return a


def w_tilt():
    big = _city(390, w=WIN_W + 40, h=WIN_H + 40, water_rows=((20, 4), (44, 3)))
    big[:8, :, :3] = col(*R_SKY)
    r = _rotate(big, 22)
    return r[20:20 + WIN_H, 20:20 + WIN_W].copy()


def w_skid():
    """擦着水面滑：上面一截岸边屋檐，下面整片水，水花一道道往后溅。"""
    a = _fill(c=col(*R_WATER))
    a[:8, :, :3] = col(0.34, 0.010, 80)
    a[6:8, :, :3] = col(0.26, 0.010, 200)
    for y in range(10, WIN_H, 4):
        a[y, ::5, :3] = col(*R_WATER_L)
    rng = np.random.default_rng(400)
    c = cv(a)
    for _ in range(12):
        x, y = int(rng.integers(0, WIN_W)), int(rng.integers(18, WIN_H))
        ln = int(rng.integers(4, 10))
        for k in range(ln):
            c.put(x + k, y - k // 2, col(0.68, 0.012, 160) if k < ln - 2 else col(0.56, 0.014, 165))
    return a


def _channel_base(seed):
    """狭窄水道（侧面近景）：对岸一面旧砖墙和小窗，下面水，水上漂着几根浮木。"""
    a = _fill(c=col(0.32, 0.012, 60))
    c = cv(a)
    for y in range(0, 22, 4):                                    # 砖缝
        off = 0 if (y // 4) % 2 else 3
        a[y, :, :3] = col(0.26, 0.010, 60)
        for x in range(off, WIN_W, 6):
            a[y:y + 4, x, :3] = col(0.26, 0.010, 60)
    for x in (8, 30, 48):
        c.rect(x, 5, x + 4, 11, col(0.18, 0.010, 200))
        c.rect(x, 5, x + 4, 5, col(0.36, 0.012, 60))
    a[22:, :, :3] = col(*R_WATER)
    a[22, :, :3] = col(0.24, 0.012, 200)                         # 水线
    for y in range(25, WIN_H, 3):
        a[y, (np.arange(WIN_W) % 7 == (y % 7)), :3] = col(*R_WATER_L)
    rng = np.random.default_rng(seed)
    for _ in range(3):
        x, y = int(rng.integers(-4, WIN_W - 8)), int(rng.integers(24, 34))
        ln = int(rng.integers(8, 15))
        c.rect(x, y, x + ln, y + 1, col(0.30, 0.030, 55))
        c.rect(x, y, x + ln, y, col(0.38, 0.030, 60))
    return a


def w_channel():
    return _channel_base(410)


def w_crate():
    a = _channel_base(420)
    c = cv(a)
    x, y = 30, 22
    c.rect(x, y, x + 13, y + 10, col(0.40, 0.040, 60))
    c.rect(x, y, x + 13, y, col(0.48, 0.040, 65))
    c.rect(x + 13, y, x + 13, y + 10, col(0.32, 0.034, 55))
    c.line(x + 1, y + 1, x + 12, y + 9, col(0.32, 0.034, 55))
    c.rect(x, y + 5, x + 13, y + 5, col(0.32, 0.034, 55))
    a[y + 9:y + 11, x - 1:x + 15, :3] = col(*R_WATER_L)          # 箱子吃水那一线
    return a


WINDOW_PAINTERS = {
    "forest_canopy": w_forest_canopy, "canopy_fall": w_canopy_fall, "forest_below": w_forest_below,
    "forest_far": w_forest_far, "turning": w_turning, "clouds": w_clouds, "debris_wall": w_debris_wall,
    "clouds_fast": w_clouds_fast, "river_planet": w_river_planet, "river_city": w_river_city,
    "clocktower": w_clocktower, "boats": w_boats, "tilt": w_tilt, "skid": w_skid, "channel": w_channel,
    "crate": w_crate,
}


def window_mask():
    """窗洞形状（WIN_POLY，相对窗矩形左上角）：True = 露出来。"""
    pts = [(x - WIN_RECT[0], y - WIN_RECT[1]) for x, y in WIN_POLY]
    return Canvas(WIN_W, WIN_H).poly(pts, (1, 1, 1))


def build_windows():
    out = {}
    wm = window_mask()
    mk = np.zeros((WIN_H, WIN_W, 4), np.uint8)
    mk[wm] = 255
    save(mk, "window_mask")
    for n in WINDOW_STATES:
        a = WINDOW_PAINTERS[n]()
        assert a.shape[:2] == (WIN_H, WIN_W), (n, a.shape)
        a[..., 3] = 255
        a[~wm] = 0                       # 窗矩形的左上角在机身外面，裁成窗洞的形状
        save(a, f"window_{n}")
        out[n] = a
    extras = {}
    for n, r in debris_sprites().items():
        save(r, n)
        extras[n] = r
    af = airflow_strip()
    save(af, "airflow")
    extras["airflow"] = af
    return out, extras


# ============================================================ 通讯器：背包图标 + 聊天界面的小框（9-slice）
# 图标和 art/forest_story/icon_* 同一套（tools/forest_room_art.py 的 ICON_PAL：平涂、4~7 色、不描边）
ICON_PAL = {
    "k": (52, 46, 58), "g": (58, 74, 67), "G": (92, 111, 102), "s": (143, 166, 154), "S": (185, 201, 191),
    "m": (120, 120, 132), "h": (104, 100, 110), "y": (232, 184, 96), "o": (168, 100, 46),
}
# 一个旧的、普通的手持通讯器：竖着的灰绿小机身，一根短天线，小屏（暗的灰绿，不亮），下面两排按键，边上磨掉一块漆
ICON_COMMUNICATOR = [
    "..k......",
    "..k......",
    ".gGGGGGg.",
    ".GkkkkkGg",
    ".GksssGkg",
    ".GkSssGkg",
    ".GkkkkkGg",
    ".GGGGGGsg",
    ".GmGmGmGg",
    ".GGGGGGGg",
    ".GmGhGmGg",
    ".GGGGGGGg",
    "..ggggg..",
]
ICON_COMMUNICATOR = [r.replace("GkkkkkGg", "GkkkkkGg") for r in ICON_COMMUNICATOR]

UI_C = {
    "body": col(0.40, 0.016, 160), "body_l": col(0.48, 0.016, 155), "body_d": col(0.32, 0.016, 170),
    "edge": col(0.24, 0.012, 190),
    "screen": col(0.20, 0.022, 165), "screen_l": col(0.26, 0.024, 160),
    "in": col(0.30, 0.020, 165), "in_l": col(0.36, 0.020, 160),
    "out": col(0.44, 0.022, 120), "out_l": col(0.52, 0.022, 110),
    "card": col(0.24, 0.014, 170), "card_l": col(0.42, 0.018, 160),
    "btn": col(0.34, 0.016, 165), "btn_l": col(0.44, 0.016, 160), "btn_h": col(0.46, 0.030, 80),
    "dot": col(0.68, 0.100, 75),
}


def ui_box(w, h, fill, top=None, edge=None, round_=True, bottom=None):
    """9-slice 用的简单框：平涂底 + 上沿亮一行 + 一圈暗边（圆角切掉角上一个像素）。"""
    c = Canvas(w, h)
    c.rect(0, 0, w - 1, h - 1, edge or fill)
    c.rect(1, 1, w - 2, h - 2, fill)
    if top:
        c.rect(1, 1, w - 2, 1, top)
    if bottom:
        c.rect(1, h - 2, w - 2, h - 2, bottom)
    if round_:
        for (x, y) in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            c.clear(x, y)
    return c


def phone_ui():
    """art/ui/phone_*.png + phone_ui.json（每张图的 9-slice 边距）。"""
    UI.mkdir(parents=True, exist_ok=True)
    items = {}
    # 机身外框：外面一圈灰绿机身（4 像素），里面一圈暗屏边，中间是屏（平涂，拉伸）。左下角一块磨掉的漆，右上一颗螺丝。
    c = Canvas(24, 24)
    c.rect(0, 0, 23, 23, UI_C["edge"])
    c.rect(1, 1, 22, 22, UI_C["body"])
    c.rect(1, 1, 22, 1, UI_C["body_l"])
    c.rect(1, 22, 22, 22, UI_C["body_d"])
    c.rect(5, 5, 18, 18, UI_C["edge"])
    c.rect(6, 6, 17, 17, UI_C["screen"])
    c.rect(6, 6, 17, 6, col(0.17, 0.020, 170))
    c.put(20, 2, col(0.30, 0.010, 190))
    c.put(2, 20, UI_C["body_l"])
    for (x, y) in ((0, 0), (23, 0), (0, 23), (23, 23)):
        c.clear(x, y)
    items["phone_frame"] = (c, [7, 7, 7, 7], "聊天界面外框：外面一圈旧机身、中间暗屏（拉伸）")
    items["phone_bubble_in"] = (ui_box(9, 9, UI_C["in"], UI_C["in_l"], UI_C["edge"]), [3, 3, 3, 3], "对方的消息")
    items["phone_bubble_out"] = (ui_box(9, 9, UI_C["out"], UI_C["out_l"], UI_C["edge"]), [3, 3, 3, 3], "晨发的消息")
    nc = ui_box(16, 12, UI_C["card"], UI_C["card_l"], UI_C["edge"], bottom=col(0.20, 0.012, 180))
    items["phone_notify"] = (nc, [4, 4, 4, 4], "屏幕角落的通知小卡")
    items["phone_button"] = (ui_box(12, 10, UI_C["btn"], UI_C["btn_l"], UI_C["edge"]), [3, 3, 3, 3], "回复 / 稍后看 / 发送 按钮")
    items["phone_button_hover"] = (ui_box(12, 10, UI_C["btn_l"], UI_C["btn_h"], UI_C["edge"]), [3, 3, 3, 3], "按钮悬停")
    ic = ui_box(12, 10, UI_C["screen_l"], None, UI_C["edge"], round_=False)
    ic.rect(1, 8, 10, 8, UI_C["in_l"])
    items["phone_input"] = (ic, [3, 3, 3, 3], "输入栏（草稿）")
    d = Canvas(3, 3)
    d.rect(0, 0, 2, 2, UI_C["dot"])
    for (x, y) in ((0, 0), (2, 0), (0, 2), (2, 2)):
        d.clear(x, y)
    items["phone_unread"] = (d, [0, 0, 0, 0], "未读小点（不拉伸）")
    meta = {"note": "9-slice 边距 margins = [左, 上, 右, 下]（Godot NinePatchRect 的 patch_margin_*）；文字颜色建议：屏上 #b9c9bf，按钮上 #e3dccb",
            "items": {}}
    for n, (cc, mg, desc) in items.items():
        cc.save(UI / f"{n}.png")
        meta["items"][n] = {"size": [cc.w, cc.h], "margins": mg, "desc": desc}
    (UI / "phone_ui.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    ico = Canvas.from_rows(ICON_COMMUNICATOR, ICON_PAL).trim()
    ico.save(ICON_OUT / "icon_communicator.png")
    return {n: v[0] for n, v in items.items()}, ico


# ============================================================ 预览
BG = (16, 22, 20, 255)


def compose(back, front=None, props=None, states=None, window=None, chen=True):
    """把剖面 + 窗外 + 物件（指定状态）拼成一张 1 倍图。"""
    im = Image.new("RGBA", (W, H), BG)
    if window is not None:
        im.alpha_composite(Image.fromarray(window), (WIN_RECT[0], WIN_RECT[1]))
    im.alpha_composite(Image.fromarray(back))
    states = states or {}
    for name, frames in (props or {}).items():
        x, y, w, h = OBJ[name]
        if name == "cockpit_leak_steam":
            if states.get("cockpit_leak") != "steam":
                continue
            i = 0
        else:
            sts = PROP_STATES[name]
            stn = states.get(name, PROP_DEFAULT.get(name, next(iter(sts))))
            if stn == "hidden":
                continue
            i = sts[stn][0] if isinstance(sts[stn], list) else sts[stn]
        im.alpha_composite(Image.fromarray(frames[i].a), (x, y))
    if chen:
        # 只用来看比例（晨是奥斯卡画的，预览里借他的待机第 9 帧，68×60 一帧）
        sheet = Image.open(ROOT / "art/characters/chen/chen_oscar.png").convert("RGBA")
        fr = sheet.crop((9 * 68, 0, 10 * 68, 60))
        a = np.array(fr)
        ys, xs = np.nonzero(a[..., 3])
        fr = fr.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
        cx = MARKERS_PX["cockpit_toolbox"][0] - 22
        im.alpha_composite(fr, (cx - fr.width // 2, FL - fr.height))
    if front is not None:
        im.alpha_composite(Image.fromarray(front))
    return im


PROP_STATES = {}


def x3(im):
    return im.resize((im.width * 3, im.height * 3), Image.NEAREST)


def preview(path, back, front, prop_frames, windows=None, extras=None):
    rows = []
    rows.append(compose(back, None, prop_frames, {}, windows.get("forest_far") if windows else None))
    rows.append(compose(back, None, prop_frames, {"cockpit_leak": "steam", "cockpit_converter": "glow",
                                                    "cockpit_toolbox": "open", "cockpit_console": "dim",
                                                    "cockpit_nav": "detour", "cockpit_repair_log": "check_2",
                                                    "cockpit_bell": "empty_loop"},
                        windows.get("debris_wall") if windows else None, chen=False))
    rows.append(compose(back, front, None, {}, None, chen=False))
    # 物件状态排开（2× 背景色上）
    strip_rows = []
    for name, frames in prop_frames.items():
        ww = sum(f.w + 3 for f in frames)
        hh = max(f.h for f in frames)
        r = Image.new("RGBA", (ww, hh), BG)
        xx = 0
        for f in frames:
            r.alpha_composite(Image.fromarray(f.a), (xx, hh - f.h))
            xx += f.w + 3
        strip_rows.append(r)
    if windows:
        names = list(windows)
        per = 8
        for i in range(0, len(names), per):
            r = Image.new("RGBA", (per * (WIN_W + 3), WIN_H), BG)
            for j, n in enumerate(names[i:i + per]):
                r.alpha_composite(Image.fromarray(windows[n]), (j * (WIN_W + 3), 0))
            strip_rows.append(r)
    for e in (extras or []):
        strip_rows.append(e)
    Wd = max([W] + [r.width for r in strip_rows])
    Ht = sum(r.height + 4 for r in rows) + sum(r.height + 4 for r in strip_rows)
    out = Image.new("RGBA", (Wd, Ht), (0, 0, 0, 255))
    yy = 0
    for r in rows + strip_rows:
        out.alpha_composite(r, (0, yy))
        yy += r.height + 4
    x3(out).save(path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default=None, help="预览图写到这个文件（.png）")
    ap.add_argument("--ship_out", action="store_true",
                    help="只重画船外远景 art/cockpit/ship_out/（不动别的图：完整重跑会覆盖 tools/sky_art.py 画的 debris_*.png）")
    args = ap.parse_args()
    if args.ship_out:
        build_ship_out(args.preview)
        sys.exit(0)
    back, front = build_section()
    objects, prop_frames = build_props()
    windows, extras = build_windows()
    ui_items, ico = phone_ui()
    write_json(objects)
    if args.preview:
        ex = Image.new("RGBA", (330, 26), BG)
        xx = 0
        for n, r in extras.items():
            ex.alpha_composite(Image.fromarray(r), (xx, 0))
            xx += r.shape[1] + 4
        for n, r in list(ui_items.items()) + [("icon", ico)]:
            ex.alpha_composite(Image.fromarray(r.a), (xx, 0))
            xx += r.w + 4
        preview(args.preview, back, front, prop_frames, windows, [ex])
