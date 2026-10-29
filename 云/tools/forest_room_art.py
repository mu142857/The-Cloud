"""森林章节：弥洛的树屋（屋外的大树干 + 屋内剖面 + 前墙）和这一章的背包图标。以后改这些图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/forest_room_art.py [--preview 目录 [--forest 森林截图.png]]

第二版（2026-10-29，作者否了第一版的透视房间：「完全没有整个森林的忧郁感」「太大了」「不需要透视」）：
- 没有透视：正侧面的剖面，像横版卷轴里把房子前墙拿掉看进去。地板就是森林地面那一行（y≈228），墙是平的，
  家具都是正侧面。树屋放在森林世界里（主层，scroll 1.0），不是单独的一屏。
- 一棵巨大树干的底部挖出来的一间小屋：屋里 260×122，四周是树皮和根，外面是森林（视差背景从屋子外面透出来）。
- 忧郁：和森林同一套调色（暗、冷、青绿、雾、灰尘）。屋里大部分在阴影里，光只有后墙一扇小窗透进的青绿雾光，
  加炉子一小团很弱的暖光（全屋唯一的暖色，面积小，比晨暗）。东西多但落灰、褪色、沉在暗里；姓名牌是暗的小纸片。

输出（art/forest_story/）：
- treehouse_back.png  大树干 + 屋内剖面（后墙、窗、炉子、桌、架子、工作台、管道之外的固定东西），一直显示；
- treehouse_front.png 前墙（拱门、很暗的圆窗、补丁和铁皮、挂着的小零件；树洞剩下的地方是长回来的树皮），
  盖在屋内上面，进屋淡出、出屋淡入；
  两张同尺寸，锚点 = 底边中点踩在地面上；
- room_light.png      窗里斜进来的一道雾光 + 几粒灰（半透明，单独一层，盖在家具上、人下面）；
- room_* / pipe_* / tool_*  能动或会换状态的物件（多帧横排，同名 .json 写帧宽帧数）；
- treehouse.json      尺寸、屋内地板、可走范围、门、每个物件的摆放和互动点（都是相对图底边中点的偏移）；
- icon_*              背包图标（和 art/level1/wood.png 同一套）。
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
from oscarkit.fx import despeckle  # noqa: E402
from oscarkit.light import Light, polygonal, smooth_noise  # noqa: E402
from oscarkit.measure import srgb_to_oklab  # noqa: E402
from oscarkit.palette import from_hex, from_lch, oklab_to_srgb  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "forest_story"

W, H = 340, 236                 # 两张树屋图的尺寸；底边 = 地面那一行（世界 y=228）
CX = W // 2                     # 锚点 x（底边中点）
CAV_X0, CAV_X1 = 40, 300        # 屋内（挖空的那块）左右，宽 260
CAV_TOP = H - 122               # 屋内顶（天花板下沿），高 122
FL = H                          # 屋内地板 = 图底边（物件的底边踩在这一行下面）
LIP = 3                         # 剖开的树干切口（最少这么宽）
LIP_MAX = 5                     # 切口最宽处（前墙至少盖到这一圈）
STEP = 0.042                    # 一档明暗


def X(c):
    """屋内坐标（从屋内左墙算起）→ 图坐标。"""
    return CAV_X0 + c


# 光：后墙小窗（青绿雾光）、炉火（很弱的暖光）
WIN_C = (X(88), FL - 80)
WIN = Light(WIN_C[0], WIN_C[1], 30, power=1.0, radius=46)
STOVE = Light(X(43), FL - 10, 14, power=0.75, radius=20)

GREEN_H, WARM_H, COOL_H = 165.0, 60.0, 255.0

N_WALL = smooth_noise(H, W, 10, 60, seed=11)
N_BARK = smooth_noise(H, W, 3, 40, seed=12, octaves=3)
N_BARK2 = smooth_noise(H, W, 14, 70, seed=13)
N_MISC = smooth_noise(H, W, 30, 30, seed=14)
N_MOSS = smooth_noise(H, W, 9, 6, seed=15)


def col(L, C, h):
    return from_lch(L, C, h)


def cv(img) -> Canvas:
    """包一层 Canvas 但不拷贝（Canvas(arr=) 会拷贝）。"""
    c = Canvas(1, 1)
    c.a = img
    return c


def mask_like(img):
    return np.zeros(img.shape[:2], bool)


def mrect(x0, y0, x1, y1, shape=(H, W)):
    m = np.zeros(shape, bool)
    m[max(0, y0):max(0, y1 + 1), max(0, x0):max(0, x1 + 1)] = True
    return m


# ============================================================ 打光：光照 → 一档一档的色块（Oscar 的做法，正侧面）
def shade(img, mask, L0, C0, h0, z=0.0, gain=0.5, center=0.0, noise=None, noise_amp=0.6, cell=(10, 14), seed=0,
          warm=1.0, green=1.0, lights=(WIN, STOVE)):
    """给一块正对镜头的面上色：亮度 = 底色 + gain×(光 - center)，按 STEP 分档（三角网格上分段线性，块边是直线）；
    窗光多的块偏青绿，炉光多的块偏暖，暗的块偏冷。"""
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return img
    Hh, Ww = mask.shape
    gy, gx = np.mgrid[0:Hh, 0:Ww].astype(float)

    def ill(L):
        if L not in lights:
            return np.zeros((Hh, Ww))
        v = np.stack([L.x - gx, L.y - gy, np.full_like(gx, L.z - z)], -1)
        d = np.linalg.norm(v, axis=-1) + 1e-6
        lam = np.clip(v[..., 2] / d, 0, 1)
        return L.power * lam / (1 + (d / L.radius) ** 2)

    Iw, Is = ill(WIN), ill(STOVE)
    F = gain * (Iw + Is - center)
    if noise is not None:
        F = F + noise_amp * STEP * noise
    F = polygonal(F, cell[0], cell[1], seed=seed)
    Tw = polygonal(Iw, cell[0], cell[1], seed=seed)
    Ts = polygonal(Is, cell[0], cell[1], seed=seed)
    k = np.round(F[ys, xs] / STEP)
    tw = np.clip(np.round(Tw[ys, xs] * 3 * green) / 3, 0, 1)
    ts = np.clip(np.round(Ts[ys, xs] * 3 * warm) / 3, 0, 1)
    L = np.clip(L0 + k * STEP, 0.08, 0.95)
    hr = math.radians(h0)
    a = np.full(len(ys), C0 * math.cos(hr))
    b = np.full(len(ys), C0 * math.sin(hr))
    cool = np.clip(-k, 0, 3) / 3 * 0.008
    for amt, hh in ((cool, COOL_H), (tw * 0.03, GREEN_H), (ts * 0.04, WARM_H)):
        a += amt * math.cos(math.radians(hh))
        b += amt * math.sin(math.radians(hh))
    rgb = oklab_to_srgb(np.stack([L, a, b], 1))
    img[ys, xs, :3] = rgb
    img[ys, xs, 3] = 255
    return img


def darken(img, m, steps=1.0, cool=True):
    sel = m & (img[..., 3] > 0)
    if not sel.any():
        return
    lab = srgb_to_oklab(img[sel][:, :3])
    lab[:, 0] -= STEP * steps
    lab[:, 1:] *= 0.92
    if cool:
        lab[:, 1] += 0.004 * math.cos(math.radians(COOL_H)) * steps
        lab[:, 2] += 0.004 * math.sin(math.radians(COOL_H)) * steps
    img[sel, :3] = oklab_to_srgb(lab)


def soften(a: np.ndarray, k: float = 0.7) -> np.ndarray:
    """小物件的明暗往自己的中间调收（Oscar 的物件对比低，相邻面只差一档左右）。"""
    out = a.copy()
    m = out[..., 3] > 0
    if not m.any():
        return out
    cols, inv = np.unique(out[m][:, :3], axis=0, return_inverse=True)
    lab = srgb_to_oklab(cols)
    med = float(np.median(srgb_to_oklab(out[m][:, :3])[:, 0]))
    lab[:, 0] = med + (lab[:, 0] - med) * k
    out[m, :3] = oklab_to_srgb(lab)[inv.ravel()]
    return out


def limit_colors(a: np.ndarray, n: int) -> np.ndarray:
    m = a[..., 3] > 0
    im = Image.fromarray(a[..., :3]).quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = a.copy()
    out[..., :3] = np.array(im.convert("RGB"))
    out[~m] = 0
    return out


# 屋里东西用的几条色（都很暗、低饱和；落灰的顶边亮一点、灰一点）
WOOD = (0.25, 0.022, 70)        # 家具木头
WOOD_D = (0.20, 0.018, 60)
WOOD_L = (0.30, 0.016, 85)      # 顶边落灰
IRON = (0.20, 0.008, 230)
TAG = col(0.36, 0.014, 90)      # 姓名牌：暗的小纸片
TAG_D = col(0.30, 0.012, 80)
STRING = col(0.22, 0.01, 60)


def tag(c: Canvas, x, y, string=1):
    """小姓名牌：一根线 + 2×2 的暗纸片。"""
    for i in range(string):
        c.put(x, y + i, STRING)
    c.rect(x, y + string, x + 1, y + string + 1, TAG)
    c.put(x + 1, y + string + 1, TAG_D)


# ============================================================ 树干
def trunk_edges():
    """每一行树干的左右边：笔直往上收进画面外（森林里的树干都是直的），到地面那一段往两边张开成板根。"""
    rng = np.random.default_rng(3)
    wob = np.cumsum(rng.normal(0, 0.3, H))
    wob = (wob - np.linspace(wob[0], wob[-1], H)) * 0.5
    xl, xr = np.zeros(H), np.zeros(H)
    for y in range(H):
        t = y / H
        base = 34 - 3 * t                                 # 笔直的一根（约 270 宽），往上收一点点
        flare = 30 * max(0.0, (y - 168) / (H - 168)) ** 2.4
        xl[y] = base - flare + wob[y]
        xr[y] = W - base + flare - wob[y] * 0.8 + 2
    return np.clip(np.round(xl), 0, W - 1).astype(int), np.clip(np.round(xr), 0, W - 1).astype(int)


CAV_SIDE = 100                  # 屋内两边墙高（拱脚），中间拱顶到 122


def cavity_top(x, pad=0):
    """屋内顶边：两边 CAV_SIDE 高，中间拱到 122；边上有一点点凿出来的不平。"""
    hw = (CAV_X1 - CAV_X0) / 2 + pad
    cx_ = (CAV_X0 + CAV_X1) / 2
    t = np.clip(1 - ((x - cx_) / hw) ** 2, 0, 1)
    jag = np.where((np.asarray(x) * 7 % 13) < 3, 1, 0)
    return np.round(FL - CAV_SIDE - pad - (122 - CAV_SIDE) * np.sqrt(t) + jag).astype(int)


def cut_mask():
    """前墙至少要盖住的范围：屋内 + 最宽的那圈切口。"""
    return cavity_mask(LIP_MAX)


def cavity_mask(pad=0):
    """屋内（挖空的那块）：两边直墙，顶上是一道扁拱（树洞），边缘有一点凿痕。pad>0 往外扩（切口那一圈）。"""
    m = np.zeros((H, W), bool)
    x0, x1 = CAV_X0 - pad, CAV_X1 - 1 + pad
    xs = np.arange(x0, x1 + 1)
    tops = cavity_top(xs.astype(float), pad)
    for x, t in zip(xs, tops):
        m[max(0, t):H, x] = True
    return m


BARK = {-3: (0.125, 0.009, 180), -2: (0.145, 0.010, 172), -1: (0.165, 0.011, 165), 0: (0.185, 0.012, 158),
        1: (0.205, 0.012, 150), 2: (0.228, 0.013, 140)}


def bark_layer():
    """大树干，照 art/forest/main.png 近景树干的画法：
    - 圆柱：两边暗、中间亮一档（光从左上的雾里来，所以最亮的那条偏左），左边缘一条受光边，右边缘压暗；
    - 树皮竖纹：2~4 像素宽的竖条一亮一暗，有节奏地排，沿竖向很长、偶尔断开错位；几条长的深沟；
    - 疤（树瘤：外圈鼓起亮一档、中间深）、一道长裂口、苔（受光的左边下部和根上）；
    - 根：底下往两边张开成几条板根，中间是深的沟，扎进地面那一行。"""
    img = np.zeros((H, W, 4), np.uint8)
    xl, xr = trunk_edges()
    tm = np.zeros((H, W), bool)
    for y in range(H):
        tm[y, xl[y]:xr[y] + 1] = True
    yy, xx = np.mgrid[0:H, 0:W]
    u = (xx - xl[:, None]) / np.maximum(1, (xr - xl)[:, None])
    cyl = np.cos((u - 0.42) * np.pi * 1.05)                  # 圆柱：中间偏左最亮，两边往下掉
    # 竖纹节奏：列噪声（短周期）决定一条条竖棱，沿竖向用一条慢噪声把它偶尔错开一两格
    shift = np.round(2 * smooth_noise(H, 1, 1, 26, seed=41)).astype(int)
    stripe_col = smooth_noise(1, W + 8, 2.2, 1, seed=42)[0]
    stripe = stripe_col[np.clip(xx + 4 + shift, 0, W + 7)]
    vert = -0.55 * np.clip((yy - 200) / 36, 0, 1)
    v = 1.6 * cyl - 0.8 + 0.42 * stripe + 0.12 * N_BARK2 + vert
    lv = np.clip(np.round(v * 2.0), -3, 2)
    for k, (L, C, h) in BARK.items():
        m = tm & (lv == k)
        img[m, :3] = col(L, C, h)
        img[m, 3] = 255
    # 长深沟：竖纹里最低的那几列，断断续续
    gaps = smooth_noise(H, W, 1, 18, seed=43)
    crev = tm & (stripe < -0.62) & (gaps > -0.35)
    img[crev, :3] = col(*BARK[-3])
    # 受光边（左，雾光）和背光边（右）
    for y in range(H):
        img[y, xl[y]:xl[y] + 1, :3] = col(0.25, 0.016, 155)
        if y % 23 > 3:
            img[y, xl[y] + 1, :3] = col(0.21, 0.013, 150)
        img[y, xr[y] - 1:xr[y] + 1, :3] = col(*BARK[-3])
    c = cv(img)
    # 疤：树瘤
    for (kx, ky, rx, ry) in [(104, 52, 5, 7), (238, 22, 4, 6), (292, 128, 3, 5), (60, 150, 3, 4)]:
        outer = ((xx - kx) / (rx + 2)) ** 2 + ((yy - ky) / (ry + 2)) ** 2 <= 1
        inner = ((xx - kx) / rx) ** 2 + ((yy - ky) / ry) ** 2 <= 1
        core = ((xx - kx) / (rx - 2)) ** 2 + ((yy - ky) / (ry - 2)) ** 2 <= 1
        img[outer & tm, :3] = col(0.20, 0.012, 150)
        img[outer & tm & (xx < kx), :3] = col(0.235, 0.013, 140)
        img[inner & tm, :3] = col(0.15, 0.010, 170)
        img[core & tm, :3] = col(0.12, 0.009, 190)
    # 一道长裂口：深的缝，左边缘受一点光
    for y in range(6, 92):
        x = 196 + round(1.5 * math.sin(y / 9))
        w_ = 1 + (1 if 30 < y < 70 else 0)
        c.rect(x, y, x + w_ - 1, y, col(0.10, 0.009, 200))
        c.put(x - 1, y, col(0.215, 0.013, 145))
    # 板根：几条往外张开的根，中间是深沟
    root_valleys = [(30, 236, 18, 196, 5), (310, 236, 322, 198, 5), (12, 236, 8, 220, 3), (330, 236, 334, 222, 3)]
    for (x0, y0, x1, y1, w_) in root_valleys:
        c.poly([(x0 - w_, y0), (x0 + w_, y0), (x1, y1)], col(*BARK[-3]))
        c.line(x0 - w_ - 1, y0 - 1, x1 - 1, y1 + 1, col(0.205, 0.012, 150))
    # 苔：受光的左边下部、根的顶面、贴地那一段
    moss = tm & (N_MOSS > 0.2) & (((u < 0.2) & (yy > 120)) | ((u > 0.88) & (yy > 170)) | (yy > H - 10))
    img[moss, :3] = col(0.235, 0.032, 150)
    img[moss & (N_MOSS > 0.5), :3] = col(0.275, 0.038, 145)
    return img, tm


def pulley(c: Canvas):
    """左边树干上伸出一根横木，头上一只滑轮，绳子垂下来吊着一只小铁桶，另一头拴在树干的木桩上。"""
    xl, _ = trunk_edges()
    y = 92
    x_end = 4
    c.rect(x_end, y, xl[y] + 6, y + 2, col(0.20, 0.016, 60))
    c.rect(x_end, y, xl[y] + 6, y, col(0.25, 0.016, 75))
    c.line(xl[y + 16] + 2, y + 16, x_end + 14, y + 3, col(0.18, 0.014, 60))      # 斜撑
    px, py = x_end + 3, y + 5
    yy, xx = np.mgrid[0:H, 0:W]
    c.fill_mask((xx - px) ** 2 + (yy - py) ** 2 <= 9, col(0.24, 0.008, 220))
    c.put(px, py, col(0.14, 0.008, 230))
    rope = col(0.30, 0.02, 80)
    c.line(px - 3, py, px - 3, 176, rope)
    c.line(px + 3, py, xl[150] + 3, 150, rope)
    c.rect(xl[150] + 2, 148, xl[150] + 5, 151, col(0.22, 0.016, 60))           # 拴绳的木桩
    # 小铁桶
    bx = px - 3
    c.line(bx - 4, 182, bx, 177, col(0.26, 0.008, 220))
    c.line(bx, 177, bx + 4, 182, col(0.26, 0.008, 220))
    c.poly([(bx - 5, 182), (bx + 5, 182), (bx + 4, 191), (bx - 4, 191)], col(0.24, 0.01, 210))
    c.poly([(bx + 1, 182), (bx + 5, 182), (bx + 4, 191), (bx + 1, 191)], col(0.20, 0.01, 220))
    c.rect(bx - 5, 182, bx + 5, 182, col(0.30, 0.01, 200))
    c.put(bx - 2, 186, col(0.24, 0.04, 45))


def fungus(c: Canvas):
    """树干上几朵层孔菌（灰白的小台子，顶面亮一点），一处旧钉子挂过东西的印子。"""
    for x, y, w_ in [(286, 70, 9), (290, 77, 6), (300, 150, 7), (64, 30, 7), (68, 36, 5)]:
        c.rect(x, y, x + w_ - 1, y + 1, col(0.30, 0.02, 95))
        c.rect(x + 1, y, x + w_ - 2, y, col(0.36, 0.02, 100))
        c.rect(x + 1, y + 2, x + w_ - 2, y + 2, col(0.19, 0.012, 160))


def chimney_out(c: Canvas):
    """炉子的烟囱从屋顶穿出树干（在切口上方），往上一截，戴个帽。屋里屋外都看得见。"""
    x = X(34)
    t = int(cavity_top(float(x), LIP)) - 1
    c.rect(x, 74, x + 4, t, col(0.24, 0.008, 230))
    c.rect(x, 74, x, t, col(0.29, 0.008, 220))
    c.rect(x - 2, 70, x + 6, 73, col(0.22, 0.008, 235))
    c.rect(x - 2, 70, x + 6, 70, col(0.28, 0.008, 220))
    c.rect(x - 1, 100, x + 5, 101, col(0.20, 0.008, 240))


# ============================================================ 屋内剖面（画进 back）
WIN_RECT = (X(78), FL - 92, X(98), FL - 70)          # 后墙小窗（x0, y0, x1, y1）
STOVE_X = (X(30), X(54))
TABLE_X = (X(68), X(108))
TABLE_TOP = FL - 22
SHELF_X = (X(124), X(162))
SHELF_H = (24, 48, 72, 96)                            # 隔板离地高度
BENCH_X = (X(186), X(258))
BENCH_TOP = FL - 26
SMALL_SHELF = (X(58), X(76), FL - 62)


def interior(img):
    cav = cavity_mask()
    lip = cavity_mask(LIP) & ~cav
    # 切口：树干被挖开的断面。贴着屋子是一道背光的暗边，往外是几圈年轮（浅、深相间），最外圈毛毛糙糙地
    # 吃进树皮里，宽窄不一，不是一个整齐的框
    fray = smooth_noise(H, W, 3, 3, seed=51)
    band = [cavity_mask(p) for p in range(0, LIP_MAX + 1)]
    tones = {1: (0.13, 0.010, 220), 2: (0.215, 0.018, 80), 3: (0.185, 0.016, 75), 4: (0.205, 0.016, 85),
             5: (0.175, 0.014, 80)}
    for p in range(1, LIP_MAX + 1):
        ring_m = band[p] & ~band[p - 1]
        if p >= 4:
            ring_m &= fray > (p - 4) * 0.35 - 0.1
        img[ring_m, :3] = col(*tones[p])
        img[ring_m, 3] = 255
    lip = cut_mask() & ~cav
    # 后墙：挖出来的木头，钉了竖木板。窗附近被雾光照亮几档，炉边一小块暖，其余沉在暗里
    shade(img, cav, 0.165, 0.016, 75, gain=0.22, center=0.04, noise=N_WALL, noise_amp=1.1, cell=(14, 18), seed=2)
    c = cv(img)
    seam = mrect(0, 0, 0, 0)
    for x in range(CAV_X0 + 7, CAV_X1, 11):
        seam |= mrect(x, CAV_TOP, x, FL - 1)
    darken(img, seam & cav, 1.0)
    # 天花板：一道暗梁 + 梁下几根短椽的头
    # 顶：顺着拱的一道暗（凿出来的木头，背光）+ 几根横撑的头
    sh5 = np.zeros_like(cav)
    sh5[5:] = cav[:-5]
    img[cav & ~sh5, :3] = col(0.12, 0.011, 230)
    sh6 = np.zeros_like(cav)
    sh6[6:] = cav[:-6]
    img[cav & sh5 & ~sh6, :3] = col(0.15, 0.012, 205)
    c.rect(CAV_X0, FL - 100, CAV_X1 - 1, FL - 98, col(0.14, 0.012, 225))     # 拱脚那道横梁
    c.rect(CAV_X0, FL - 97, CAV_X1 - 1, FL - 97, col(0.17, 0.012, 205))
    # 踢脚
    c.rect(CAV_X0, FL - 2, CAV_X1 - 1, FL - 1, col(0.13, 0.012, 230))
    window(c)
    door_inside(c)
    stove(img)
    small_shelf(c)
    table(c)
    shelf(img)
    bench(c)
    wall_things(c)
    ceiling_things(c)
    return cav, lip


def window(c: Canvas):
    """后墙上的小窗：窗外是雾里的林子（和森林的雾带同一个青灰绿），窗框暗，窗台上落着灰。"""
    x0, y0, x1, y1 = WIN_RECT
    fog = [(0.48, 0.035), (0.54, 0.04), (0.60, 0.04), (0.52, 0.04)]
    rows = np.linspace(y0, y1 + 1, len(fog) + 1).astype(int)
    for (L, C), ya, yb in zip(fog, rows[:-1], rows[1:]):
        c.rect(x0, ya, x1, yb - 1, col(L, C, 165))
    for tx, tw_, L in [(x0 + 2, 2, 0.40), (x0 + 9, 1, 0.43), (x0 + 14, 3, 0.33), (x1 - 2, 2, 0.38)]:
        c.rect(tx, y0, tx + tw_ - 1, y1, col(L, 0.03, 170))
    c.poly([(x0, y1 + 1), (x0, y1 - 4), (x0 + 6, y1 - 6), (x0 + 12, y1 - 3), (x1 - 3, y1 - 7), (x1 + 1, y1 - 5),
            (x1 + 1, y1 + 1)], col(0.30, 0.03, 165))
    fr = col(0.17, 0.012, 200)
    mx, my = (x0 + x1) // 2, (y0 + y1) // 2
    c.rect(x0 - 2, y0 - 2, x1 + 2, y0 - 1, fr)
    c.rect(x0 - 2, y0, x0 - 1, y1, fr)
    c.rect(x1 + 1, y0, x1 + 2, y1, fr)
    c.rect(mx, y0, mx, y1, fr)
    c.rect(x0, my, x1, my, fr)
    c.rect(x0 - 3, y1 + 1, x1 + 3, y1 + 2, col(0.30, 0.02, 120))           # 窗台（受光、落灰）
    c.rect(x0 - 3, y1 + 3, x1 + 3, y1 + 3, col(0.16, 0.012, 220))
    c.rect(x0 + 1, y1 - 3, x0 + 2, y1, col(0.30, 0.02, 160))               # 窗台上一只空瓶


def door_inside(c: Canvas):
    """门在前墙上（剖面里看不见门板）：屋里这边只有门口的地垫、墙上的挂钩和一件旧外套、一把伞。"""
    c.rect(X(4), FL - 2, X(30), FL - 1, col(0.17, 0.02, 30))
    c.rect(X(6), FL - 66, X(28), FL - 65, col(0.21, 0.016, 60))
    for hx in (X(9), X(17), X(25)):
        c.put(hx, FL - 64, col(0.26, 0.01, 220))
    # 外套
    c.poly([(X(7), FL - 63), (X(12), FL - 63), (X(14), FL - 30), (X(5), FL - 29)], col(0.19, 0.016, 250))
    c.poly([(X(10), FL - 63), (X(12), FL - 63), (X(14), FL - 30), (X(11), FL - 30)], col(0.17, 0.014, 255))
    tag(c, X(13), FL - 60)
    # 伞
    c.rect(X(25), FL - 63, X(25), FL - 26, col(0.16, 0.01, 230))
    c.poly([(X(23), FL - 58), (X(27), FL - 58), (X(28), FL - 34), (X(25), FL - 30), (X(22), FL - 34)], col(0.20, 0.02, 290))
    # 墙上一只停了的钟（姓名牌）
    c.rect(X(14), FL - 96, X(22), FL - 86, col(0.20, 0.016, 60))
    c.rect(X(15), FL - 95, X(21), FL - 87, col(0.30, 0.014, 95))
    c.rect(X(18), FL - 94, X(18), FL - 91, col(0.18, 0.01, 60))
    c.rect(X(18), FL - 91, X(20), FL - 91, col(0.18, 0.01, 60))
    tag(c, X(23), FL - 92)


def stove(img):
    """铸铁小炉子：正侧面，四条短腿，炉门里一小团很弱的火（全屋唯一的暖色）。烟囱从炉顶上天花板。"""
    c = cv(img)
    x0, x1 = STOVE_X
    body = mrect(x0, FL - 26, x1, FL - 5)
    shade(img, body, 0.19, 0.008, 230, gain=0.25, center=0.02, cell=(6, 8), seed=21, noise=N_MISC, noise_amp=0.4,
          lights=(WIN,))
    c.rect(x0 - 1, FL - 28, x1 + 1, FL - 27, col(0.24, 0.008, 220))        # 炉盘
    c.rect(x0 - 1, FL - 28, x1 + 1, FL - 28, col(0.27, 0.01, 200))
    for lx in (x0 + 1, x1 - 2):
        c.rect(lx, FL - 4, lx + 1, FL - 1, col(0.16, 0.008, 240))
    c.rect(x0, FL - 6, x1, FL - 5, col(0.16, 0.008, 240))
    # 炉门 + 火（很弱）
    fx0, fx1, fy0, fy1 = x0 + 7, x1 - 7, FL - 20, FL - 10
    c.rect(fx0, fy0, fx1, fy1, col(0.14, 0.008, 250))
    c.rect(fx0 + 1, fy0 + 5, fx1 - 1, fy1 - 1, col(0.32, 0.07, 40))
    c.rect(fx0 + 2, fy1 - 3, fx1 - 2, fy1 - 1, col(0.42, 0.09, 55))
    c.rect(fx0 + 4, fy1 - 2, fx1 - 4, fy1 - 1, col(0.50, 0.09, 68))
    for bx in range(fx0 + 2, fx1, 3):
        c.rect(bx, fy0 + 1, bx, fy1 - 1, col(0.14, 0.008, 250))
    # 烟囱（贴着后墙，在水壶后面）
    px = X(34)
    pt = int(cavity_top(float(px)))
    c.rect(px, pt, px + 4, FL - 29, col(0.18, 0.008, 230))
    c.rect(px, pt, px, FL - 29, col(0.22, 0.008, 215))
    c.rect(px - 1, FL - 70, px + 5, FL - 69, col(0.21, 0.008, 225))
    # 炉边一小摞柴
    for (lx, ly) in [(x1 + 3, FL - 3), (x1 + 8, FL - 3), (x1 + 5, FL - 6)]:
        c.rect(lx, ly - 1, lx + 4, ly + 1, col(0.21, 0.03, 55))
        c.put(lx, ly, col(0.27, 0.03, 70))


def small_shelf(c: Canvas):
    x0, x1, y = SMALL_SHELF
    c.rect(x0, y, x1, y + 1, col(*WOOD))
    c.rect(x0, y, x1, y, col(*WOOD_L))
    for bx in (x0 + 2, x1 - 3):
        c.rect(bx, y + 2, bx + 1, y + 5, col(*WOOD_D))


def table(c: Canvas):
    x0, x1 = TABLE_X
    c.rect(x0, TABLE_TOP, x1, TABLE_TOP + 2, col(*WOOD))
    c.rect(x0, TABLE_TOP, x1, TABLE_TOP, col(*WOOD_L))
    c.rect(x0 + 1, TABLE_TOP + 3, x1 - 1, TABLE_TOP + 3, col(*WOOD_D))
    for lx in (x0 + 2, x1 - 4):
        c.rect(lx, TABLE_TOP + 3, lx + 2, FL - 1, col(*WOOD_D))
    c.rect(x0 + 5, TABLE_TOP + 9, x1 - 5, TABLE_TOP + 9, col(0.18, 0.016, 55))   # 横撑


def shelf(img):
    """顶天的架子：四层，放满修好的东西，每件挂一个暗的小姓名牌。全是灰扑扑、褪了色的。"""
    c = cv(img)
    x0, x1 = SHELF_X
    shade(img, mrect(x0, FL - 104, x1, FL - 1), 0.15, 0.014, 70, gain=0.25, center=0.03, cell=(8, 12), seed=40,
          noise=N_WALL, noise_amp=0.6)
    for px in (x0, x1 - 2):
        c.rect(px, FL - 106, px + 2, FL - 1, col(*WOOD_D))
        c.rect(px, FL - 106, px, FL - 1, col(0.23, 0.02, 65))
    for h_ in SHELF_H:
        y = FL - h_
        c.rect(x0, y, x1, y + 1, col(*WOOD))
        c.rect(x0, y, x1, y, col(*WOOD_L))
    d = lambda L, h, C=0.02: col(L, C, h)  # noqa: E731
    # 最低一层（地上，人身后：只放大件，压暗）：打字机、一只箱子
    by = FL - 1
    c.rect(x0 + 4, by - 9, x0 + 17, by - 1, d(0.17, 220, 0.012))
    c.rect(x0 + 6, by - 12, x0 + 15, by - 10, d(0.15, 230, 0.01))
    tag(c, x0 + 18, by - 9)
    c.rect(x0 + 22, by - 11, x1 - 4, by - 1, d(0.18, 50))
    c.rect(x0 + 22, by - 11, x1 - 4, by - 11, d(0.21, 70))
    # 第一层（离地 24）：左边收音机、右边油灯，都单独出图（姓名牌支线会被晨拿走），这里空着
    # 第二层（48）：电扇、茶壶
    by = FL - SHELF_H[1] - 1
    c.rect(x0 + 4, by - 13, x0 + 13, by - 4, d(0.22, 175, 0.018))
    c.rect(x0 + 6, by - 11, x0 + 11, by - 6, d(0.17, 175, 0.014))
    c.rect(x0 + 8, by - 9, x0 + 9, by - 8, d(0.25, 175, 0.018))
    c.rect(x0 + 8, by - 3, x0 + 9, by, d(0.19, 60))
    tag(c, x0 + 14, by - 12)
    c.rect(x0 + 20, by - 6, x0 + 29, by, d(0.23, 35, 0.025))
    c.rect(x0 + 23, by - 8, x0 + 26, by - 7, d(0.20, 35, 0.02))
    c.rect(x0 + 30, by - 5, x0 + 31, by - 4, d(0.23, 35, 0.025))
    tag(c, x0 + 33, by - 7)
    # 第三层（72）：小机器人、几本书
    by = FL - SHELF_H[2] - 1
    c.rect(x0 + 4, by - 12, x0 + 11, by - 6, d(0.22, 220, 0.014))
    c.put(x0 + 6, by - 10, d(0.30, 90, 0.02))
    c.put(x0 + 9, by - 10, d(0.30, 90, 0.02))
    c.rect(x0 + 3, by - 5, x0 + 12, by, d(0.19, 220, 0.012))
    tag(c, x0 + 13, by - 10)
    for i, (h_, L) in enumerate([(30, 0.19), (150, 0.21), (290, 0.18), (60, 0.22), (200, 0.19)]):
        c.rect(x0 + 18 + i * 3, by - 10 + (i % 2), x0 + 20 + i * 3, by, d(L, h_, 0.022))
    # 顶上（96）：摞到天花板的箱子、一只鸟笼
    by = FL - SHELF_H[3] - 1
    c.rect(x0 + 2, by - 8, x0 + 18, by, d(0.17, 50))
    c.rect(x0 + 2, by - 8, x0 + 18, by - 8, d(0.21, 70))
    for xx in range(x0 + 22, x0 + 35, 3):
        c.rect(xx, by - 12, xx, by, d(0.24, 80, 0.018))
    c.rect(x0 + 21, by - 12, x0 + 35, by - 12, d(0.24, 80, 0.018))
    c.rect(x0 + 21, by, x0 + 35, by, d(0.22, 70, 0.018))
    tag(c, x0 + 36, by - 10)


def bench(c: Canvas):
    x0, x1 = BENCH_X
    c.rect(x0, BENCH_TOP, x1, BENCH_TOP + 3, col(*WOOD))
    c.rect(x0, BENCH_TOP, x1, BENCH_TOP, col(*WOOD_L))
    for lx in (x0 + 2, x1 - 5):
        c.rect(lx, BENCH_TOP + 4, lx + 3, FL - 1, col(*WOOD_D))
    c.rect(x0 + 4, FL - 9, x1 - 4, FL - 8, col(0.18, 0.016, 55))           # 下面的横撑
    # 台面下：一只木箱（压暗）
    c.rect(x0 + 18, FL - 14, x0 + 40, FL - 1, col(0.16, 0.016, 50))
    c.rect(x0 + 18, FL - 14, x0 + 40, FL - 14, col(0.19, 0.018, 65))
    # 台钳（固定在台子右端）
    c.rect(x1 - 6, BENCH_TOP - 5, x1 - 1, BENCH_TOP - 1, col(0.21, 0.008, 230))
    c.rect(x1 - 6, BENCH_TOP - 5, x1 - 1, BENCH_TOP - 5, col(0.25, 0.008, 220))


def wall_things(c: Canvas):
    """工作台上方墙上：一只自行车轮（挂姓名牌）、一卷铜线；桌子上方一张钉着的旧纸（没有字，只有一道暗线）。"""
    wx, wy, r = X(240), FL - 87, 8
    yy, xx = np.mgrid[0:H, 0:W]
    dd = (xx - wx) ** 2 + (yy - wy) ** 2
    ring = (dd <= r * r) & (dd > (r - 2) ** 2)
    c.fill_mask(ring, col(0.17, 0.008, 240))
    for k in range(6):
        ang = k * math.pi / 3
        c.line(wx, wy, round(wx + (r - 2) * math.cos(ang)), round(wy + (r - 2) * math.sin(ang)), col(0.22, 0.008, 225))
    c.rect(wx, wy - r - 2, wx, wy - r - 1, STRING)
    tag(c, wx + r, wy - 4)
    # 铜线
    m = ((xx - X(218)) ** 2 + (yy - (FL - 86)) ** 2 <= 16) & ((xx - X(218)) ** 2 + (yy - (FL - 86)) ** 2 > 4)
    c.fill_mask(m, col(0.27, 0.04, 55))
    # 纸
    c.rect(X(110), FL - 60, X(117), FL - 50, col(0.27, 0.014, 95))
    c.rect(X(111), FL - 57, X(116), FL - 57, col(0.22, 0.012, 80))
    c.put(X(113), FL - 60, col(0.18, 0.01, 60))


def ceiling_things(c: Canvas):
    """从拱脚那道横梁上垂下来的：一盏不亮的灯、一把干草药、一只空鸟笼（挂姓名牌）。"""
    top = FL - 96
    lx = X(114)
    c.rect(lx, top, lx, FL - 90, STRING)
    c.poly([(lx - 5, FL - 84), (lx + 6, FL - 84), (lx + 4, FL - 89), (lx - 3, FL - 89)], col(0.21, 0.016, 170))
    c.rect(lx - 2, FL - 83, lx + 3, FL - 83, col(0.26, 0.02, 90))
    hx = X(62)
    c.rect(hx, top, hx, FL - 93, STRING)
    for i, dx in enumerate((-2, -1, 0, 1, 2)):
        c.line(hx, FL - 93, hx + dx, FL - 85 + (i % 2), col(0.22, 0.03, 120))
    bx = X(196)
    c.rect(bx, top, bx, FL - 93, STRING)
    for xx in range(bx - 5, bx + 6, 2):
        c.rect(xx, FL - 90, xx, FL - 81, col(0.21, 0.016, 80))
    c.rect(bx - 3, FL - 92, bx + 3, FL - 91, col(0.23, 0.016, 85))
    c.rect(bx - 5, FL - 90, bx + 5, FL - 90, col(0.23, 0.016, 85))
    c.rect(bx - 5, FL - 80, bx + 5, FL - 80, col(0.20, 0.016, 75))
    tag(c, bx + 6, FL - 88)


# ============================================================ 前墙（treehouse_front）
# 前墙的轮廓：一间贴着树干长进去的小屋，屋顶线高低不平（中间高、两边低），比树洞小一圈；
# 树洞剩下的部分（四角、屋顶以上）是树皮又长回来盖住的
FRONT_ROOF = [(CAV_X0, FL - 78), (X(8), FL - 86), (X(24), FL - 92), (X(48), FL - 98), (X(70), FL - 103),
              (X(92), FL - 110), (X(112), FL - 113), (X(130), FL - 118), (X(150), FL - 116), (X(170), FL - 112),
              (X(196), FL - 106), (X(220), FL - 100), (X(240), FL - 94), (X(252), FL - 86), (CAV_X1 - 1, FL - 80)]
DOOR = (X(7), X(29), FL - 54)          # 拱门：左、右、拱顶
PORT = (X(128), FL - 72, 6)            # 圆窗：圆心、半径


def front(cav, lip, bark_raw):
    """前墙（只在屋外看得见）：
    - 树洞的四角和屋顶以上用树皮盖回去（和 back 的树皮是同一张，接得上），屋顶贴着树干是一道长苔的暗檐；
    - 下半截竖板（宽窄、深浅不一），上半截横钉的搭接板；一道横梁上挂着几个小零件；
    - 左边一扇拱门（铁合页、把手），门边一块小牌；中间偏右一只很暗的圆窗（铁圈，里面一点点暖）；
    - 补丁：两块铁皮（一块瓦楞的）、斜钉的木板、一块颜色浅的新板、锈。暗、冷，不温馨。"""
    img = np.zeros((H, W, 4), np.uint8)
    cover = cut_mask()
    yy, xx = np.mgrid[0:H, 0:W]
    # 屋子轮廓
    roof_y = np.interp(np.arange(W), [p[0] for p in FRONT_ROOF], [p[1] for p in FRONT_ROOF])
    house = cav & (yy >= roof_y[None, :].round())
    # 树皮（长回来的部分）
    rest = cover & ~house
    img[rest] = bark_raw[rest]
    # 树皮和屋顶之间的阴影 + 暗檐
    c = cv(img)
    for x in range(CAV_X0, CAV_X1):
        ry = int(round(roof_y[x]))
        c.rect(x, ry - 3, x, ry - 1, col(0.13, 0.010, 200))
        c.put(x, ry - 4, col(0.16, 0.011, 190))
    # 板：下半截竖板，上半截横钉的搭接板。每块板自己一个明度 / 色相（同一档里 ±1 档），左边离雾近、整体亮一档；
    # 木纹是少量 1 像素的深色短线和节疤；板缝是暗线，缝的上沿 / 左沿一行受光；板头有开裂、缺角、烂掉的一截
    lower = house & (yy > FL - 60)
    upper = house & ~lower
    rng = np.random.default_rng(71)

    def lit_of(x):
        return 1 - (x - CAV_X0) / (CAV_X1 - CAV_X0)                       # 1 = 最左（雾光那边）.. 0 = 最右

    def wood(L, dh=0.0, C=0.014):
        return col(L, C, 100 + dh)

    x = CAV_X0
    while x < CAV_X1:
        w_ = int(rng.integers(5, 10))
        cxb = x + w_ / 2
        L = 0.198 + 0.016 * int(rng.integers(-1, 2)) + 0.022 * round(lit_of(cxb) * 2) / 2
        dh = 8.0 * int(rng.integers(-1, 2))
        m = lower & (xx >= x) & (xx < x + w_)
        img[m, :3] = wood(L, dh)
        img[m, 3] = 255
        img[m & (xx == x), :3] = col(0.145, 0.011, 200)                     # 板缝
        if lit_of(cxb) > 0.3 or rng.random() < 0.5:                        # 缝的左沿受光（右边的板只有一半有）
            img[m & (xx == x + 1), :3] = wood(L + 0.026, dh - 6)
        if lit_of(cxb) < 0.5:                                               # 右边的板，右沿背光
            img[m & (xx == x + w_ - 1), :3] = wood(L - 0.02, dh + 6)
        for _ in range(int(rng.integers(1, 3))):                            # 木纹：竖的短暗线
            gx = int(rng.integers(x + 2, max(x + 3, x + w_ - 1)))
            gy = int(rng.integers(FL - 56, FL - 14))
            c.rect(gx, gy, gx, gy + int(rng.integers(3, 7)), wood(L - 0.03, dh))
        if rng.random() < 0.22:                                             # 节疤
            kx, ky = int(rng.integers(x + 2, max(x + 3, x + w_ - 2))), int(rng.integers(FL - 50, FL - 20))
            c.rect(kx, ky, kx + 1, ky + 1, wood(L - 0.045, dh))
            c.put(kx, ky - 1, wood(L + 0.02, dh))
        if rng.random() < 0.3:                                              # 板头烂掉一截，颜色深
            cut = int(rng.integers(FL - 18, FL - 8))
            img[m & (yy > cut) & (xx > x), :3] = wood(L - 0.035, dh - 5)
        if rng.random() < 0.4:                                              # 板头开裂
            kx = int(rng.integers(x + 2, max(x + 3, x + w_ - 1)))
            c.rect(kx, FL - int(rng.integers(4, 8)), kx, FL - 1, col(0.13, 0.011, 210))
        if rng.random() < 0.3:                                              # 缺角
            kx = x + 1 if rng.random() < 0.5 else x + w_ - 2
            c.rect(kx, FL - 2, kx + 1, FL - 1, col(0.12, 0.011, 215))
            c.put(kx + (1 if kx == x + 1 else 0), FL - 3, col(0.12, 0.011, 215))
        x += w_
    # 上半截：一行 6 像素的横板，每行在随机的地方接头；每段板自己一个明度
    top = int(roof_y.min())
    for j, y0 in enumerate(range(FL - 60 - 6, top - 6, -6)):
        xb = CAV_X0 - int(rng.integers(0, 30))
        while xb < CAV_X1:
            ln = int(rng.integers(44, 96))
            xa, xe = max(CAV_X0, xb), min(CAV_X1, xb + ln)
            L = 0.192 + 0.016 * int(rng.integers(-1, 2)) + 0.022 * round(lit_of((xa + xe) / 2) * 2) / 2
            dh = 8.0 * int(rng.integers(-1, 2))
            seg = upper & (xx >= xa) & (xx < xe) & (yy >= y0) & (yy < y0 + 6)
            img[seg, :3] = wood(L, dh)
            img[seg, 3] = 255
            img[seg & (yy == y0), :3] = col(0.145, 0.011, 200)              # 板缝（暗）
            img[seg & (yy == y0 + 5), :3] = wood(L + 0.016, dh - 4)        # 下一道缝的上沿：受光
            if xa > CAV_X0:                                                 # 接头
                img[seg & (xx == xa), :3] = col(0.15, 0.011, 200)
            if rng.random() < 0.7:                                          # 木纹：横的短暗线
                gx = int(rng.integers(xa + 2, max(xa + 3, xe - 6)))
                gy = y0 + int(rng.integers(2, 4))
                c.rect(gx, gy, gx + int(rng.integers(3, 7)), gy, wood(L - 0.03, dh))
            xb += ln
    # 板画完以后再把屋子外面（树皮）恢复（木纹的短线可能画出了界）
    img[rest] = bark_raw[rest]
    for x in range(CAV_X0, CAV_X1):
        ry = int(round(roof_y[x]))
        c.rect(x, ry - 3, x, ry - 1, col(0.13, 0.010, 200))
        c.put(x, ry - 4, col(0.16, 0.011, 190))
    # 横梁（上下两截的分界），上面挂零件
    c.rect(CAV_X0, FL - 61, CAV_X1 - 1, FL - 58, col(0.18, 0.016, 65))
    c.rect(CAV_X0, FL - 61, CAV_X1 - 1, FL - 61, col(0.235, 0.018, 80))
    c.rect(CAV_X0, FL - 57, CAV_X1 - 1, FL - 57, col(0.14, 0.011, 210))
    # 拱门
    d0, d1, dtop = DOOR
    r = (d1 - d0) / 2
    dcx = (d0 + d1) / 2
    arch_out = ((xx >= d0 - 2) & (xx <= d1 + 2) & (yy >= dtop + r)) | \
        (((xx - dcx) ** 2 + (yy - (dtop + r)) ** 2 <= (r + 2) ** 2) & (yy < dtop + r + 1))
    arch_in = ((xx >= d0) & (xx <= d1) & (yy >= dtop + r)) | \
        (((xx - dcx) ** 2 + (yy - (dtop + r)) ** 2 <= r ** 2) & (yy < dtop + r + 1))
    img[arch_out, :3] = col(0.15, 0.012, 60)
    img[arch_out, 3] = 255
    img[arch_in, :3] = col(0.185, 0.02, 55)
    for x in range(d0 + 4, d1, 5):
        img[arch_in & (xx == x), :3] = col(0.15, 0.016, 50)
    for hy in (FL - 40, FL - 12):
        c.rect(d0, hy, d0 + 9, hy + 1, col(0.22, 0.008, 225))
        c.put(d0 + 9, hy + 1, col(0.27, 0.008, 210))
    c.rect(d1 - 4, FL - 27, d1 - 3, FL - 25, col(0.32, 0.02, 85))
    c.rect(d0 - 2, FL - 1, d1 + 2, FL - 1, col(0.17, 0.02, 40))                # 门槛
    # 门边的小牌（写过字，看不清），两根链子
    sx = d1 + 6
    c.put(sx + 1, FL - 50, STRING)
    c.put(sx + 8, FL - 50, STRING)
    c.rect(sx, FL - 49, sx + 9, FL - 44, col(0.23, 0.016, 90))
    c.rect(sx + 2, FL - 47, sx + 7, FL - 47, col(0.17, 0.012, 70))
    # 圆窗（很暗，里面一点点暖）
    pcx, pcy, pr = PORT
    dd = (xx - pcx) ** 2 + (yy - pcy) ** 2
    img[dd <= (pr + 2) ** 2, :3] = col(0.25, 0.008, 215)
    img[(dd <= (pr + 2) ** 2) & (xx < pcx) & (yy < pcy), :3] = col(0.29, 0.008, 205)
    img[dd <= pr ** 2, :3] = col(0.11, 0.01, 230)
    img[(dd <= pr ** 2) & (yy > pcy + 1) & (xx < pcx + 1), :3] = col(0.19, 0.03, 55)
    img[(dd <= pr ** 2) & (yy > pcy + 3) & (xx < pcx - 1), :3] = col(0.25, 0.045, 60)
    c.rect(pcx - pr, pcy, pcx + pr, pcy, col(0.22, 0.008, 220))
    for ang in range(0, 360, 90):
        c.put(round(pcx + (pr + 1) * math.cos(math.radians(ang + 45))), round(pcy + (pr + 1) * math.sin(math.radians(ang + 45))),
              col(0.33, 0.01, 90))
    # 补丁：铁皮（四角铆钉 + 锈）、瓦楞铁皮、斜钉的木板、浅色的新板
    c.rect(X(196), FL - 46, X(216), FL - 30, col(0.235, 0.008, 210))
    c.rect(X(196), FL - 46, X(216), FL - 46, col(0.28, 0.008, 200))
    for px_, py_ in [(X(197), FL - 45), (X(215), FL - 45), (X(197), FL - 31), (X(215), FL - 31)]:
        c.put(px_, py_, col(0.31, 0.01, 90))
    c.rect(X(208), FL - 38, X(211), FL - 34, col(0.22, 0.04, 45))
    c.rect(X(209), FL - 34, X(209), FL - 31, col(0.21, 0.035, 45))
    for i, x in enumerate(range(X(222), X(244))):
        c.rect(x, FL - 92 + (1 if x > X(238) else 0), x, FL - 70, col(0.25 if i % 3 == 0 else 0.215, 0.008, 210))
    c.poly([(X(60), FL - 30), (X(84), FL - 40), (X(85), FL - 36), (X(61), FL - 26)], col(0.24, 0.018, 85))
    for px_, py_ in [(X(62), FL - 29), (X(82), FL - 37)]:
        c.put(px_, py_, col(0.14, 0.01, 220))
    c.rect(X(160), FL - 57, X(165), FL - 2, col(0.255, 0.02, 92))
    c.rect(X(160), FL - 57, X(160), FL - 2, col(0.15, 0.011, 200))
    c.poly([(X(100), FL - 92), (X(118), FL - 96), (X(119), FL - 93), (X(101), FL - 89)], col(0.23, 0.018, 85))
    weather(img, house, roof_y, rng)
    # 横梁上挂着的小零件：齿轮、小铃、弹簧、一把小扳手、一串螺母（都暗）
    hang_y = FL - 57
    for hx, ln, kind in [(X(44), 6, "gear"), (X(98), 4, "bell"), (X(146), 8, "spring"), (X(184), 5, "wrench"),
                         (X(236), 7, "gear"), (X(254), 3, "nuts")]:
        c.rect(hx, hang_y, hx, hang_y + ln, STRING)
        y = hang_y + ln + 1
        if kind == "gear":
            c.rect(hx - 2, y, hx + 2, y + 4, col(0.24, 0.008, 210))
            c.put(hx, y + 2, col(0.13, 0.01, 230))
            for ox, oy in ((-3, 2), (3, 2), (0, -1), (0, 5)):
                c.put(hx + ox, y + oy, col(0.24, 0.008, 210))
        elif kind == "bell":
            c.poly([(hx - 2, y + 4), (hx + 3, y + 4), (hx + 2, y), (hx - 1, y)], col(0.28, 0.035, 75))
            c.put(hx, y + 5, col(0.20, 0.03, 60))
        elif kind == "spring":
            for i in range(6):
                c.rect(hx - 1 + (i % 2), y + i, hx + (i % 2), y + i, col(0.25, 0.008, 210))
        elif kind == "wrench":
            c.rect(hx, y, hx, y + 7, col(0.27, 0.008, 210))
            c.rect(hx - 1, y + 7, hx + 1, y + 8, col(0.27, 0.008, 210))
            c.put(hx, y + 8, col(0.14, 0.01, 220))
        else:
            for i in range(3):
                c.rect(hx - 1, y + i * 2, hx + 1, y + i * 2, col(0.26, 0.008, 210))
    # 底部：潮湿变深的一截（深一档、偏绿），上沿高低不平；苔从地上往上长，有几簇长得高；门口踩秃了
    damp_top = FL - 10 + np.round(2 * smooth_noise(1, W, 6, 1, seed=81)[0]).astype(int)
    damp = house & (yy >= damp_top[None, :]) & ~((xx >= d0 - 2) & (xx <= d1 + 2))
    tint(img, damp, -1.0, 165, 0.006)
    for x in range(CAV_X0, CAV_X1):
        if d0 - 3 <= x <= d1 + 3:
            continue
        hgt = 2 + int(round(1.5 * N_MOSS[FL - 2, x]))
        if N_MOSS[FL - 30, x] > 0.45:
            hgt += 3
        c.rect(x, FL - hgt, x, FL - 1, col(0.215, 0.03, 152))
        c.put(x, FL - hgt, col(0.255, 0.036, 146))
        if hgt > 4 and x % 2 == 0:
            c.put(x, FL - hgt + 1, col(0.255, 0.036, 146))
    # 生锈的钉头（暗暖 1 像素）+ 下面一道锈迹：钉在横梁、竖板上下两头、补丁旁
    rust_head, rust = col(0.25, 0.045, 50), col(0.185, 0.03, 45)
    nails = [(x, y) for x in range(CAV_X0 + 4, CAV_X1 - 2, 23) for y in (FL - 53, FL - 16)]
    nails += [(X(70), FL - 59), (X(140), FL - 59), (X(250), FL - 59), (X(116), FL - 80), (X(178), FL - 86)]
    for (nx, ny) in nails:
        if d0 - 3 <= nx <= d1 + 3 or not house[ny, nx]:
            continue
        c.put(nx, ny, rust_head)
        c.rect(nx, ny + 1, nx, ny + 2 + (nx % 3), rust)
    return img


def tint(img, m, steps, hue, amt):
    """把一块往暗（steps<0）/ 亮走几档，同时往某个色相推一点（水渍偏冷绿）。"""
    sel = m & (img[..., 3] > 0)
    if not sel.any():
        return
    lab = srgb_to_oklab(img[sel][:, :3])
    lab[:, 0] += STEP * steps * 0.85
    lab[:, 1] += amt * math.cos(math.radians(hue))
    lab[:, 2] += amt * math.sin(math.radians(hue))
    img[sel, :3] = oklab_to_srgb(lab)


def weather(img, house, roof_y, rng):
    """风化：屋檐下一条阴影带（暗一档）；雨水从屋檐往下流的竖向水渍（深一档、偏冷绿，有长有短，
    有几道在横梁下面接着流）；横梁下、门框右边这些凹进去的地方暗一档。"""
    yy, xx = np.mgrid[0:H, 0:W]
    eave = house & (yy < np.round(roof_y)[None, :] + 5)
    tint(img, eave, -1.0, 220, 0.002)
    streak = np.zeros((H, W), bool)
    for x in list(rng.choice(np.arange(CAV_X0 + 6, CAV_X1 - 4), 14, replace=False)):
        y0 = int(round(roof_y[x])) + 4
        ln = int(rng.integers(10, 34))
        w_ = 2 if rng.random() < 0.35 else 1
        streak |= (xx >= x) & (xx < x + w_) & (yy >= y0) & (yy < y0 + ln)
        if rng.random() < 0.5:                                    # 流到下边一截的末梢，细一点
            streak |= (xx == x) & (yy >= y0 + ln) & (yy < y0 + ln + int(rng.integers(3, 8)))
    for x in list(rng.choice(np.arange(CAV_X0 + 40, CAV_X1 - 4), 6, replace=False)):
        y0 = FL - 56
        streak |= (xx == x) & (yy >= y0) & (yy < y0 + int(rng.integers(6, 18)))
    keep = ((xx >= DOOR[0] - 3) & (xx <= DOOR[1] + 3) & (yy >= DOOR[2] - 3)) | \
        ((xx - PORT[0]) ** 2 + (yy - PORT[1]) ** 2 <= (PORT[2] + 3) ** 2)
    streak &= ~keep
    tint(img, house & streak, -1.0, 170, 0.008)
    recess = house & (((yy >= FL - 56) & (yy <= FL - 55)) | ((xx >= DOOR[1] + 3) & (xx <= DOOR[1] + 4) & (yy > DOOR[2] + 4)))
    tint(img, recess, -1.0, 220, 0.002)


# ============================================================ 单独的物件（正侧面；能动 / 换状态）
def S(w, h):
    return Canvas(w, h)


def radio():
    """木壳收音机：左边喇叭格栅，右边刻度窗和两个旋钮，顶上落灰，挂姓名牌。"""
    c = S(19, 12)
    c.rect(0, 1, 16, 11, col(0.27, 0.028, 55))
    c.rect(0, 0, 16, 0, col(0.33, 0.016, 90))
    c.rect(15, 1, 16, 11, col(0.22, 0.024, 50))
    c.rect(2, 3, 8, 9, col(0.20, 0.02, 50))
    for y in (4, 6, 8):
        c.rect(3, y, 7, y, col(0.29, 0.026, 60))
    c.rect(10, 3, 13, 5, col(0.38, 0.035, 85))
    c.put(11, 4, col(0.24, 0.03, 50))
    c.rect(10, 8, 10, 9, col(0.17, 0.01, 240))
    c.rect(13, 8, 13, 9, col(0.17, 0.01, 240))
    tag(c, 17, 2)
    return c


def sign_frames():
    """自己转的路标：立杆 + 十字底座，顶上一块箭头牌绕杆转（4 帧：右长正面、左短背面、左长背面、右短正面），
    杆上还钉一块不动的小牌，挂姓名牌。"""
    fw, fh = 26, 46
    px = 12
    front_, front_d = col(0.34, 0.025, 85), col(0.29, 0.024, 75)
    back_, back_d = col(0.24, 0.02, 60), col(0.21, 0.018, 55)
    frames = []
    for ang in (22.5, 112.5, 202.5, 292.5):
        c = S(fw, fh)
        c.rect(px - 5, fh - 2, px + 6, fh - 1, col(0.17, 0.014, 50))
        c.rect(px - 3, fh - 3, px + 4, fh - 3, col(0.20, 0.016, 60))
        c.rect(px, 5, px + 1, fh - 3, col(0.23, 0.02, 60))
        c.rect(px, 5, px, fh - 3, col(0.27, 0.02, 75))
        c.poly([(px - 8, 20), (px, 20), (px, 24), (px - 8, 24), (px - 10, 22)], col(0.24, 0.02, 60))   # 不动的小牌（朝左）
        c.rect(px - 7, 22, px - 2, 22, col(0.19, 0.016, 55))
        tag(c, px + 2, 18)
        cs = math.cos(math.radians(ang))
        L = round(11 * cs)
        top, bot = 7, 12
        face, face_d = (front_, front_d) if cs > 0 else (back_, back_d)
        if L > 0:
            x0, x1 = px + 2, px + 1 + L
            tip = x1 + (3 if L > 6 else 1)
            c.poly([(x0, top), (x1 + 1, top), (tip + 1, (top + bot + 1) / 2), (x1 + 1, bot + 1), (x0, bot + 1)], face)
            c.rect(x0, bot, x1, bot, face_d)
            if L > 6:
                c.rect(x0 + 2, 9, x1 - 2, 9, col(0.22, 0.02, 60))
        else:
            x0, x1 = px + L, px - 1
            tip = x0 - (3 if -L > 6 else 1)
            c.poly([(x1 + 1, top), (x0, top), (tip, (top + bot + 1) / 2), (x0, bot + 1), (x1 + 1, bot + 1)], face)
            c.rect(x0, bot, x1, bot, face_d)
        c.rect(px - 1, 4, px + 2, 5, col(0.27, 0.02, 70))
        frames.append(c)
    return frames, fw, fh


CHAIR_SPAN = (X(54), X(122))       # 椅子图覆盖的范围（中间是桌子，透明）


def chairs():
    """两把换过椅脚的椅子（一张图，中间空着放桌子）：左边那把面朝桌子，晨能坐；右边靠窗那把不让坐——
    椅背上搭着一件褪色的旧外套，两条椅脚下垫着木片，座面干干净净没落灰（屋里别的东西都落了灰）。
    换过的那根椅脚是新木头的浅色。各挂一个姓名牌。"""
    w = CHAIR_SPAN[1] - CHAIR_SPAN[0] + 1
    c = S(w, 32)
    wood, wood_d, wood_t = col(*WOOD), col(*WOOD_D), col(*WOOD_L)
    new = col(0.36, 0.035, 80)

    def chair(x, back_left, new_leg, kept=False):
        seat_y = 32 - 14
        c.rect(x, seat_y, x + 10, seat_y + 1, wood)
        c.rect(x, seat_y, x + 10, seat_y, col(0.27, 0.03, 62) if kept else wood_t)   # 不让坐的那把：座面没灰
        for j, lx in enumerate((x, x + 9)):
            c.rect(lx, seat_y + 2, lx + 1, 30 if kept else 31, new if j == new_leg else wood_d)
            if kept:                                                                   # 椅脚下垫的木片
                c.rect(lx - 1, 31, lx + 2, 31, col(0.33, 0.03, 80))
        bx = x if back_left else x + 9
        c.rect(bx, 0, bx + 1, seat_y - 1, wood)
        c.rect(bx, 0, bx + 1, 0, wood_t)
        c.rect(bx, 4, bx + 1, 5, wood_d)
        c.rect(bx, 9, bx + 1, 10, wood_d)
        c.rect(x + 1, seat_y + 7, x + 8, seat_y + 7, wood_d)
        if kept:                                                                       # 搭在椅背上的旧外套
            coat, coat_d, coat_l = col(0.27, 0.02, 245), col(0.22, 0.018, 250), col(0.31, 0.016, 240)
            c.poly([(bx - 3, 1), (bx + 3, 1), (bx + 3, 13), (bx + 2, 15), (bx + 1, 13)], coat)          # 背后那半
            c.poly([(bx - 4, 1), (bx, 1), (bx, seat_y + 3), (bx - 2, seat_y + 4), (bx - 5, seat_y + 2),
                    (bx - 4, 8)], coat)                                                                  # 朝前那半，垂到座面
            c.rect(bx - 3, 0, bx + 2, 1, coat_l)                                                         # 领子
            c.rect(bx - 2, 4, bx - 2, seat_y + 1, coat_d)                                                # 褶
            c.rect(bx - 4, 10, bx - 3, 11, coat_d)                                                       # 口袋
            c.rect(bx + 2, 3, bx + 2, 12, coat_d)

    chair(0, True, 1)
    tag(c, 2, 3)
    chair(w - 11, False, 0, kept=True)
    tag(c, w - 9, 21)
    return c


def kettle_frames():
    """水壶（旧铜，褪成暗褐），两帧冒汽（汽是不透明的浅灰绿小点，从壶嘴往上飘）。"""
    frames = []
    body, body_d, body_l = col(0.32, 0.04, 55), col(0.26, 0.035, 45), col(0.40, 0.04, 75)
    for i in range(2):
        c = S(15, 18)
        c.poly([(1, 18), (11, 18), (12, 14), (10, 10), (2, 10), (0, 14)], body)
        c.poly([(7, 18), (11, 18), (12, 14), (10, 10), (8, 10)], body_d)
        c.rect(2, 11, 3, 12, body_l)
        c.rect(4, 8, 8, 9, body_d)
        c.line(2, 9, 3, 6, col(0.20, 0.01, 240))
        c.line(3, 5, 9, 5, col(0.20, 0.01, 240))
        c.line(9, 6, 10, 9, col(0.20, 0.01, 240))
        c.poly([(11, 14), (14, 10), (15, 10), (13, 15)], body)
        steam, steam_d = col(0.58, 0.015, 165), col(0.48, 0.015, 165)
        pts = [(14, 8), (14, 7), (13, 5), (14, 3), (13, 1)] if i == 0 else [(14, 8), (13, 7), (14, 5), (14, 4), (12, 2)]
        for j, (x, y) in enumerate(pts):
            c.put(x, y, steam if j < 3 else steam_d)
        frames.append(c)
    return frames, 15, 18


def cups():
    """两个杯子：一个旧白、一个褪色的灰绿（另一个人的）。"""
    c = S(15, 6)
    for x, (L, C, h) in [(0, (0.40, 0.012, 90)), (8, (0.33, 0.025, 165))]:
        c.rect(x, 0, x + 4, 5, col(L, C, h))
        c.rect(x + 3, 1, x + 4, 5, col(L - 0.05, C, h))
        c.rect(x, 0, x + 4, 0, col(L + 0.04, C * 0.6, h))
        c.rect(x + 5, 1, x + 6, 1, col(L - 0.04, C, h))
        c.rect(x + 6, 2, x + 6, 3, col(L - 0.04, C, h))
        c.rect(x + 5, 4, x + 5, 4, col(L - 0.04, C, h))
    return c


def dish():
    """小碟子，里面一撮螺丝（冒出碟沿一点）。"""
    c = S(10, 4)
    c.rect(0, 2, 9, 2, col(0.32, 0.01, 200))
    c.rect(1, 3, 8, 3, col(0.25, 0.01, 220))
    for x in (2, 4, 5, 7):
        c.put(x, 1, col(0.38, 0.012, 90))
    c.put(4, 0, col(0.38, 0.012, 90))
    c.put(3, 1, col(0.27, 0.01, 230))
    c.put(6, 1, col(0.27, 0.01, 230))
    return c


GRAM_ROWS = [
    ".LLLLL................",
    "LHiiiHL...............",
    "LHiIIihL..............",
    "LHiiiihHL.............",
    ".HHhhhHHHL............",
    "..hhHHHHHHL...........",
    "....hhhHHHHL..........",
    ".......hhHHHL.........",
    ".........hhHHL........",
    "...........hHHa.......",
    "............hHa.......",
    "..........xxxxa.......",
    "..........xXxxa.......",
    "...........x..a.......",
    "..rrrrrrrrrrr.aa......",
    ".WWWWWWWWWWWWWWWWW....",
    ".WwwwwwwwwwwwwwwwWd...",
    ".wwddddddddddddwwwdc..",
    ".wwdwwwwwwwwwwdwwwdcc.",
    ".wwddddddddddddwwwd...",
    ".wwwwwwwwwwwwwwwwwd...",
    ".ddddddddddddddddddd..",
    "..dd............dd....",
]


def gramophone_frames():
    """留声机两帧：old（音箱头是发黑的旧铜，喇叭上一处凹痕）/ new（换了一个发灰亮的新音箱头，多一颗亮螺丝）。"""
    frames = []
    for state in ("old", "new"):
        pal = {
            "L": col(0.38, 0.045, 85), "H": col(0.33, 0.045, 75), "h": col(0.27, 0.04, 62),
            "i": col(0.16, 0.02, 40), "I": col(0.20, 0.03, 50), "a": col(0.29, 0.03, 80),
            "r": col(0.14, 0.008, 280), "W": col(0.30, 0.02, 80), "w": col(0.25, 0.026, 55),
            "d": col(0.20, 0.022, 45), "c": col(0.28, 0.02, 80),
            "x": col(0.20, 0.025, 55) if state == "old" else col(0.46, 0.012, 215),
            "X": col(0.24, 0.03, 60) if state == "old" else col(0.56, 0.01, 200),
        }
        c = Canvas.from_rows(GRAM_ROWS, pal)
        if state == "old":
            c.put(6, 5, pal["h"])
            c.put(7, 5, pal["h"])
        else:
            c.put(13, 12, col(0.66, 0.012, 90))
        frames.append(c)
    return frames, c.w, c.h


PIPE_Y = FL - 76                    # 管子顶
PIPE_X = (X(168), X(260))           # 左端（弯头）到右墙


def pipes():
    """后墙上一条管道，切成三段：a 光管（清脆）+ 左端弯头接天花板，b 缠了布条（发闷），c 一块旧补丁和锈（漏气）。
    返回 (整条画布, 左上角在图里的位置, [(名字, x0, x1)], {名字: 漏气点（画布坐标）})。"""
    x0, x1 = PIPE_X
    top = FL - 97
    c = S(x1 - x0, PIPE_Y + 5 - top + 1)
    oy = PIPE_Y - top
    m, md, ml = col(0.27, 0.012, 210), col(0.21, 0.012, 230), col(0.33, 0.012, 190)
    c.rect(1, 0, 5, oy + 4, m)
    c.rect(1, 0, 1, oy + 4, ml)
    c.rect(5, 0, 5, oy + 4, md)
    c.rect(1, oy, c.w - 1, oy + 4, m)
    c.rect(1, oy, c.w - 1, oy, ml)
    c.rect(1, oy + 4, c.w - 1, oy + 4, md)
    for fx in (0, 30, 60):
        c.rect(fx, oy - 1, fx + 2, oy + 5, col(0.24, 0.012, 220))
        c.rect(fx, oy - 1, fx + 2, oy - 1, col(0.30, 0.012, 200))
    c.rect(0, 2, 6, 3, col(0.24, 0.012, 220))
    for bx in range(35, 58, 4):                       # b：缠的布条
        c.rect(bx, oy, bx + 2, oy + 4, col(0.29, 0.02, 85))
        c.rect(bx, oy, bx + 2, oy, col(0.33, 0.02, 90))
    c.rect(70, oy - 1, 77, oy + 5, col(0.25, 0.025, 55))          # c：补丁
    c.rect(70, oy - 1, 77, oy - 1, col(0.30, 0.025, 70))
    for rx, ry in ((71, oy), (76, oy), (71, oy + 4), (76, oy + 4)):
        c.put(rx, ry, col(0.32, 0.02, 80))
    c.rect(82, oy + 2, 84, oy + 4, col(0.26, 0.04, 45))
    c.put(65, oy + 3, col(0.26, 0.04, 45))
    segs = [("pipe_a", 0, 30), ("pipe_b", 30, 60), ("pipe_c", 60, x1 - x0)]
    leaks = {"pipe_a": (16, oy), "pipe_b": (46, oy), "pipe_c": (80, oy)}
    return c, (x0, top), segs, leaks


def steam_frames():
    """一丝细白汽（不透明的浅灰绿小点），从管子上沿往上飘，3 帧。底边中点 = 漏气点。"""
    fw, fh = 7, 12
    pts = [
        [(3, 11), (3, 10), (4, 9), (4, 8), (3, 7), (3, 6), (2, 4), (2, 3), (3, 1)],
        [(3, 11), (4, 10), (4, 9), (3, 8), (2, 7), (2, 6), (3, 4), (4, 3), (5, 1)],
        [(3, 11), (3, 10), (2, 9), (2, 8), (3, 7), (4, 6), (4, 5), (3, 3), (1, 0)],
    ]
    frames = []
    for p in pts:
        c = S(fw, fh)
        for j, (x, y) in enumerate(p):
            c.put(x, y, col(0.66, 0.012, 165) if j < len(p) - 3 else col(0.52, 0.012, 170))
        frames.append(c)
    return frames, fw, fh


def tools():
    """台面上三把工具，正侧面看：a 扳手（灰钢，一头开口一头梅花圈）、b 螺丝刀（红褐木柄 + 细钢杆）、c 锤子（木柄 + 铁锤头）。
    轮廓完全不同，颜色也不同，1 倍下一眼分得清。"""
    st, sd, sl = col(0.44, 0.01, 215), col(0.34, 0.01, 230), col(0.54, 0.008, 200)
    a = Canvas.from_rows([
        "LLLL..........sss.",
        "...LL........sLLLs",
        "....LLLLLLLLLLL.Ls",
        "....sssssssssss.ds",
        "...dd........sddd.",
        "dddd..........ddd.",
    ], {"L": sl, "s": st, "d": sd})
    b = Canvas.from_rows([
        ".rrrrrr...........",
        "RRRRRRRgSSSSSSSSSS",
        "RooooooggsssssssS.",
        ".oooooo...........",
    ], {"r": col(0.42, 0.07, 40), "R": col(0.36, 0.07, 32), "o": col(0.29, 0.05, 28), "g": col(0.30, 0.01, 230),
        "S": sl, "s": sd})
    c = Canvas.from_rows([
        "............LL.",
        "...........LssL",
        "...........Lssd",
        "wwwwwwwwwwwssdd",
        "WWWWWWWWWWWssdd",
        "...........sdd.",
        "...........Ldd.",
        "...........dd..",
    ], {"w": col(0.38, 0.04, 70), "W": col(0.30, 0.035, 60), "L": sl, "s": st, "d": sd})
    return {"tool_a": a, "tool_b": b, "tool_c": c}


def seed_box():
    """放种子的小木盒：盖子落灰，前面一个暗铜扣。"""
    c = S(11, 7)
    c.rect(0, 2, 10, 6, col(0.26, 0.026, 50))
    c.rect(9, 2, 10, 6, col(0.22, 0.022, 45))
    c.rect(0, 0, 10, 1, col(0.29, 0.024, 60))
    c.rect(0, 0, 10, 0, col(0.34, 0.014, 90))
    c.rect(5, 2, 5, 3, col(0.40, 0.05, 80))
    return c


TOOLWALL_ROWS = [
    "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    "dBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBd",
    "dBBBBpBBBBBBBBpBBBBBBBBBpBBBBBBBBBBpBBBBBBBBBBBpBBBBBBBBBBBBBd",
    "dBBBBkBBBBBBBlkllBBBBBBlkBBBBBBBBBlklBBBBBBBBBBkBBBBBBBBBBBBBd",
    "dBBBlMlBBBBBBlMMlBBBBBlmlBBBBBBBBBlwlBBBBBBBBlMMMlBBBBBBBBBBBd",
    "dBBlmMmlBBBBBlMMlBBBBBlmlBBBBBBBBBlwlBBBBBBBBlmMmlBBBBBBBBBBBd",
    "dBBlmMmlBBBBBBlmlBBBBlmmmlBBBBBBBBlwlBBBBBBBBBlmlBBBBBBBBBBBBd",
    "dBBBlMlBBBBBBBlmlBBBBlmmmlBBBBBBBBlnlBBBBBBBBBlmlBBBBBBBBBBBBd",
    "dBBBBwlBBBBBBBlmlBBBBBlmlBBBBBBBBBlmlBBBBBBBBBlmlBBBBBBBBBBBBd",
    "dBBBlwlBBBBBBBlmlBBBBBlmlBBBBBBBBBlmlBBBBBBBBBlmlBBBBBBBBBBBBd",
    "dBBBlwlBBBBBBBlmlBBBBBlmlBBBBBBBBBlmlBBBBBBBBlmmmlBBBBBBBBBBBd",
    "dBBBlwlBBBBBBlmmmlBBBBlmlBBBBBBBBBBlBBBBBBBBBlmMmlBBBBBBBBBBBd",
    "dBBBBlBBBBBBBBlllBBBBBBlBBBBBBBBBBBBBBBBBBBBBBlllBBBBBBBBBBBBd",
    "dBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBd",
    "dBBBBpBBBBBBBBBpBBBBBBBBBpBBBBBBBBBpBBBBBBBBBBBBBBBBBBBBBBBBBd",
    "dBBBlllBBBBBBBlBlBBBBBBBlBlBBBBBBBlllBBBBBBBBBBBBBBBBBBBBBBBBd",
    "dBBBlBlBBBBBBBlBlBBBBBBBlBlBBBBBBBlBlBBBBBBBBBBBBBBBBBBBBBBBBd",
    "dBBBlBlBBBBBBBBlBBBBBBBlBBBlBBBBBBlBlBBBBBBNNNNNNNNNBBBBBBBBBd",
    "dBBBBlBBBBBBBBBlBBBBBBBlBBBlBBBBBBBlBBBBBBBNnNnnNnNNBBBBBBBBBd",
    "dBBBBlBBBBBBBBBlBBBBBBBBlBlBBBBBBBBlBBBBBBBNNnNNnnNNBBBBBBBBBd",
    "dBBBBlBBBBBBBBBlBBBBBBBBBlBBBBBBBBBlBBBBBBBNNNNNNNNNBBBBBBBBBd",
    "dBBBBlBBBBBBBBlllBBBBBBBBBBBBBBBBBBlBBBBBBBBBBBBBBBBBBBBBBBBBd",
    "dBBBBlBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBsBssBsBsssBBBBBBd",
    "dBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBd",
    "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
]


def toolwall():
    """工具墙：一块挂板，上面用浅色画着两套不同高度的工具轮廓。高的那排（弥洛的高度）挂着工具：锤子、钳子、
    一把锉、螺丝刀、扳手；低的那排（另一个人的高度）空着，只剩画出来的轮廓和空钩子。旁边两行不同的笔迹：
    一张圆乎乎字迹的小纸条（「用完放回来，我够不到。」），下面一行弥洛后来刻上去的、尖的短划（「那就长高一点。」）。
    1 倍下读不出字，只看得出是两种笔迹。"""
    pal = {"d": col(0.15, 0.012, 60), "B": col(0.195, 0.018, 70), "l": col(0.27, 0.012, 95),
           "p": col(0.30, 0.008, 220), "k": col(0.24, 0.008, 225), "M": col(0.36, 0.008, 210),
           "m": col(0.28, 0.008, 225), "w": col(0.30, 0.035, 60), "n": col(0.25, 0.03, 30),
           "N": col(0.30, 0.016, 85), "s": col(0.25, 0.014, 90)}
    c = Canvas.from_rows(TOOLWALL_ROWS, pal)
    return c


def part_pack():
    """新零件的小纸包：牛皮纸，拆过又重新折了好几次（几道折痕、一个翘起来的角），细绳。"""
    return Canvas.from_rows([
        "..q...",
        ".PPqPq",
        "PqPPPP",
        "PPPwqP",
        "PqPwPP",
        "PPPwPq",
    ], {"P": col(0.34, 0.03, 75), "q": col(0.28, 0.026, 70), "w": col(0.40, 0.012, 90)})


def postcard():
    """玻璃下压着的半张明信片：一块小玻璃板斜靠在墙上（左上一道高光），里面半张明信片——
    干净、没灰、边角不卷，右上角一枚邮票和半个邮戳圈。屋里唯一干净的纸。"""
    return Canvas.from_rows([
        "TggggggG",
        "gppppsSg",
        "gpqqpSsg",
        "gpppeppg",
        "gpqqpepg",
        "gpppppg.",
        "Gggggg..",
    ], {"T": col(0.50, 0.02, 170), "g": col(0.36, 0.02, 175), "G": col(0.30, 0.02, 180),
        "p": col(0.52, 0.02, 85), "q": col(0.40, 0.015, 80), "s": col(0.40, 0.05, 30), "S": col(0.46, 0.05, 40),
        "e": col(0.36, 0.015, 230)})


LAMP_X = SHELF_X[1] - 7            # 油灯在架子第一层右边的中心


def lamp():
    """一盏旧油灯（和 icon_lamp 同一件东西）：旧铜灯座，蒙了灰的暗玻璃罩（左边一道浅的高光），
    灯芯是暗的、不亮；灯颈上挂着姓名牌。"""
    return Canvas.from_rows([
        "...mm......",
        "..mMMm.....",
        "...gg......",
        "..tggg.....",
        ".tggggg....",
        ".tgbbgg....",
        ".tgbbgg....",
        "..tggg.....",
        ".mmmmmmh...",
        "mOOOOOOmh..",
        "mOyOOOOOmzz",
        "mOOOOOOomzz",
        ".mooooom...",
        "..mmmmm....",
    ], {"m": col(0.24, 0.012, 215), "M": col(0.30, 0.01, 210), "g": col(0.20, 0.015, 195),
        "t": col(0.27, 0.014, 185), "b": col(0.12, 0.01, 230), "O": col(0.31, 0.045, 72), "y": col(0.37, 0.04, 82),
        "o": col(0.25, 0.04, 62), "h": STRING, "z": TAG})


def lamp_mark():
    """油灯被拿走以后架子上留下的印子：隔板顶上那一行（落了灰的浅色）在灯座底下是一截没灰的干净木色。
    一直显示，有灯的时候被灯座盖住、只从两边露一点。"""
    c = S(11, 1)
    c.rect(1, 0, 9, 0, col(0.215, 0.03, 58))                  # 没灰的木头（比落灰的隔板顶暗、颜色实）
    c.put(0, 0, col(0.33, 0.014, 88))                         # 两头灰积得厚一点
    c.put(10, 0, col(0.33, 0.014, 88))
    return c


def light_shaft():
    """窗里斜进来的一道雾光（半透明，单独一层）+ 光里飘着的几粒灰。"""
    img = np.zeros((H, W, 4), np.uint8)
    x0, y0, x1, y1 = WIN_RECT
    outer = Canvas(W, H).poly([(x0, y1 + 1), (x1 + 1, y0), (x1 + 52, FL), (x0 + 18, FL)])
    inner = Canvas(W, H).poly([(x0 + 5, y1 + 1), (x1 - 2, y0 + 6), (x1 + 34, FL), (x0 + 24, FL)])
    img[outer, :3] = col(0.62, 0.04, 165)
    img[outer, 3] = 22
    img[inner, 3] = 38
    rng = np.random.default_rng(7)
    ys, xs = np.nonzero(inner)
    for i in rng.choice(len(ys), 9, replace=False):
        img[ys[i], xs[i], :3] = col(0.70, 0.02, 120)
        img[ys[i], xs[i], 3] = 120
    return img


# ============================================================ 背包图标（和 art/level1/wood.png、icon_bag.png 同一套：
# 平涂、4~7 色、不描边，用 level1 图标里的灰绿 / 橙 / 棕；纸是暖白）
ICON_PAL = {
    "k": (52, 46, 58),       # 最暗（带紫的灰，不是黑）
    "g": (58, 74, 67), "G": (92, 111, 102), "s": (143, 166, 154), "S": (185, 201, 191),   # 灰绿（icon_bag）
    "o": (168, 100, 46), "O": (200, 130, 60), "y": (232, 184, 96), "Y": (240, 210, 140),  # 橙（wood / flame）
    "b": (58, 42, 34), "B": (90, 63, 44), "w": (130, 92, 62),                              # 棕
    "p": (226, 218, 200), "P": (200, 190, 170), "q": (170, 160, 142),                      # 纸
    "e": (96, 92, 110),      # 铅笔（灰紫）
    "r": (170, 72, 58), "R": (126, 52, 48),                                                # 晨的锈红
    "c": (140, 170, 190), "C": (96, 124, 150), "t": (210, 228, 230), "T": (236, 244, 240), # 冷：玻璃、天
    "m": (120, 120, 132), "M": (160, 160, 170), "n": (88, 86, 100),                        # 金属 / 城市灰
    "v": (100, 150, 110), "V": (140, 190, 140),                                            # 嫩芽绿
    "L": (150, 112, 78),     # 木头受光的那一条
    "z": (132, 124, 108),    # 姓名牌：暗的小纸片（比纸 p 暗得多）
    "h": (104, 100, 110),
    "D": (70, 88, 110), "u": (128, 152, 172),                                              # 蓝石头：暗边、受光    # 挂姓名牌的线（比最暗的 k 亮一档，在背包底色上看得见）
}

ICONS = {
    # 晨醒来画的大象：一张纸，铅笔涂的灰色大象，长鼻子从头前面一直垂到底再往外卷，两只耳朵（一只大的贴在头上、一只翘在头顶），四条腿长短不一
    "icon_drawing": [
        "................",
        ".ppppppppppppppP",
        ".pppeeepppppppqP",
        ".ppeeqqeeeeeeppP",
        ".ppeeqqeeeeeeepP",
        ".ppeeqqeeeeeeeeP",
        ".pepeqeeeeeeeepP",
        ".pepppeeeeeeeepP",
        ".pepppepeppepepP",
        ".pepppepeppepppP",
        ".pepppeppppepppP",
        ".ppepppppppppppP",
        ".ppppppppppppppP",
        ".PPPPPPPPPPPPPPq",
    ],
    # 物种查询结果：打印的小单子，灰绿抬头，几行字，最下面一个空框（未找到）
    "icon_query": [
        "...pppppppppp...",
        "...pGGGGGGGGp...",
        "...pGsGsGGGGp...",
        "...ppppppppppq..",
        "...pmmmmmppppq..",
        "...ppppppppppq..",
        "...pmmmpmmmppq..",
        "...ppppppppppq..",
        "...pmmmmmmmppq..",
        "...ppppppppppq..",
        "...pqqqqqqqqpq..",
        "...pqpppppppqpq.",
        "...pqpppppppqpq.",
        "...pqqqqqqqqpq..",
        "...pppppppppppq.",
        "....qpqpqpqpqq..",
    ],
    # 通勤卡：圆角卡片，灰绿底，橙色条，左上一块芯片
    "icon_card": [
        "................",
        "................",
        "................",
        "..SSSSSSSSSSSS..",
        ".SssssssssssssG.",
        ".SsyysssssssssG.",
        ".SsyOsssssssssG.",
        ".SsssssssssssGG.",
        ".OOOOOOOOOOOOOo.",
        ".SssssssMMMMssG.",
        ".SsssssssssssGG.",
        "..GGGGGGGGGGGG..",
        "................",
        "................",
        "................",
        "................",
    ],
    # 母星照片：白边相片，里面是灰色的鸽子笼高楼和一点暗天，几扇很暗的亮窗
    "icon_photo": [
        "................",
        "..pppppppppppp..",
        "..pCCCCCCCCCCp..",
        "..pCCcCCCCCCCp..",
        "..pnnCCmmCCnnp..",
        "..pnnCmmmmCnnp..",
        "..pnnmmymmmnnp..",
        "..pnymmmmmmnnp..",
        "..pnnmmmmymnyp..",
        "..pnnmmmmmmnnp..",
        "..pkkkkkkkkkkp..",
        "..ppppppppppppP.",
        "..pppppppppppPP.",
        "...PPPPPPPPPPP..",
        "................",
        "................",
    ],
    # 音乐盒：木盒子，盖子掀开，里面一排金色梳齿，侧面一个小摇柄
    "icon_musicbox": [
        "................",
        "...BBBBBBBBBB...",
        "..BwwwwwwwwwwB..",
        "..BwOOOOOOOOwB..",
        "..BBBBBBBBBBBB..",
        "..kkkkkkkkkkkk..",
        "..OyOyOyOyOyOO..",
        "..wwwwwwwwwwwB..",
        "..wOOOOOOOOwwBy.",
        "..wwwwwwwwwwwByy",
        "..wwwwwwwwwwwB..",
        "..BBBBBBBBBBBB..",
        "................",
        "................",
        "................",
        "................",
    ],
    # 地图：折了三折的纸，绿的森林、蓝的河、虚线路线，终点一个橙点
    "icon_map": [
        "................",
        "................",
        ".pppppPPPPPppppp",
        ".pVVvpPccCPpppqp",
        ".pVvVpPPcPPpqppp",
        ".pvVppPPcCPpppyp",
        ".ppqpqPqPPPqpqyp",
        ".pqppPPPcPPppppp",
        ".ppVvPPccPPppTTp",
        ".pvVVPcCPPPpTttp",
        ".ppppPPPPPPppppp",
        ".qqqqqPPPPPqqqqq",
        "................",
        "................",
        "................",
        "................",
    ],
    # 日记：锈红布面，一条松紧带，橙色书签露在下面
    "icon_journal": [
        "................",
        "...RRRRRRRRRRp..",
        "...RrrrrrrrrRp..",
        "...RrrrrrrrrRp..",
        "...RrrrrrrrrRp..",
        "...RrrrrrrrrRp..",
        "...RrrrrrrrrRp..",
        "...RrrrrrrrrSRp.",
        "...RrrrrrrrrSRp.",
        "...RrrrrrrrrRp..",
        "...RrrrrrrrrRp..",
        "...RrrrrrrrrRp..",
        "...RRRRRRRRRRp..",
        ".......Oy.......",
        ".......O........",
        "................",
    ],
    # 坏掉的推进器零件：带螺栓法兰的金属喷口，一道从口沿裂上去的透明裂缝，右下角缺一块，口沿烧黑
    "icon_part": [
        "....nMMMMn......",
        "....MmMmMm......",
        ".....mMMm.......",
        "....mMMm.m......",
        "...mMMmm..m.....",
        "...mMMm..mmm....",
        "..mMMmm.mmmmm...",
        "..mMmmm..mmmmn..",
        ".mMMmmmm.mmmmn..",
        ".mMmmmmm..mm....",
        ".nbbBbbb..n.....",
        "..nnnnnn........",
    ],
    # 透明的种子：只有一圈很浅的边、一个高光，中间是空的（看得见后面），里面浮着一点嫩芽
    "icon_seed": [
        "................",
        ".........tT.....",
        "........t..t....",
        ".......t....c...",
        "......T.....c...",
        ".....t.T.V..c...",
        ".....t..vV..C...",
        ".....t..v...C...",
        "....t.......C...",
        "....t......C....",
        "....c.....C.....",
        ".....c...C......",
        "......CCC.......",
        "................",
    ],
    # 弥洛的纸条：一小张对折的纸，右上角折了，两三行字
    "icon_note": [
        "................",
        "................",
        "................",
        "...pppppppPq....",
        "...pppppppqPq...",
        "...peeeeepqqqq..",
        "...ppppppppppp..",
        "...peeepeeeepp..",
        "...ppppppppppp..",
        "...peeeeppppqp..",
        "...ppppppppppp..",
        "...qqqqqqqqqqq..",
        "...PPPPPPPPPPP..",
        "................",
        "................",
        "................",
    ],
}


def _spring_rows():
    """闹钟里拆出来的发条：一圈扁的螺旋（外圈受光亮、里圈暗），尾巴伸出去一截，几处锈。"""
    n = 13
    g = [["."] * (n + 3) for _ in range(n)]
    cx = cy = n // 2
    th = 0.0
    while th < 5.2 * math.pi:
        r = 0.55 + 0.36 * th
        x, y = round(cx + r * math.cos(th)), round(cy + r * math.sin(th) * 0.95)
        if 0 <= x < n and 0 <= y < n:
            g[y][x] = "M" if (r > 3.5 and math.sin(th) < 0.2) else ("m" if r > 2 else "n")
        th += 0.05
    for x in range(n - 1, n + 3):                       # 尾巴
        g[cy + 4][x] = "m"
    g[cy + 3][n + 2] = "M"
    for (x, y) in ((2, 4), (9, 10), (6, 1)):            # 锈
        if g[y][x] != ".":
            g[y][x] = "o"
    return ["".join(r) for r in g]


def _valve_rows():
    """锈的阀门：上面一只手轮（圆圈 + 四根辐条 + 轴心），下面一截阀体管子带两片法兰，锈斑一块块。"""
    W_, H_ = 14, 15
    g = [["."] * W_ for _ in range(H_)]
    cx, cy, r = 6, 4, 4
    for y in range(H_):
        for x in range(W_):
            d = math.hypot(x - cx, (y - cy) * 1.05)
            if r - 0.75 <= d <= r + 0.45:
                g[y][x] = "R" if (x + y) % 5 == 0 else ("r" if y < cy else "R")
    for k in range(-3, 4):                                # 辐条
        g[cy][cx + k] = "n" if g[cy][cx + k] == "." else g[cy][cx + k]
        g[cy + k][cx] = "n" if g[cy + k][cx] == "." else g[cy + k][cx]
    g[cy][cx] = "M"
    for y in range(cy + 4, cy + 7):                       # 阀杆
        g[y][cx] = "m"
        g[y][cx + 1] = "n"
    body = ["..mmmmmmmmm...", "nMmmmmommmmMn.", "nmmmooommmmmn.", "nmmmmmmmmommn.", "..nnnnnnnnn..."]
    for i, row in enumerate(body):
        for x, ch in enumerate(row):
            if ch != ".":
                g[cy + 6 + i][x] = ch
    return ["".join(r).rstrip(".") or "." for r in g]


ICONS.update({
    # 一块旧木板（从商店烂货架上拆下来的）：顶边受光，两个钉眼，右头断得参差
    "icon_plank": [
        "................",
        "................",
        "................",
        "................",
        "................",
        "LLLLLLLLLLLLLL..",
        "wwwwwBwwwwwwwwL.",
        "wwbwwwwwwwwbwwwL",
        "wwwwwwwBwwwwwwww",
        "BBBBBBBBBBBBBBB.",
        ".bbbbbbbbbbbbb..",
    ],
    # 空的小罐子：铁盖，玻璃只画一圈边和一道高光，中间是空的（看得见后面）
    "icon_jar": [
        "...MMMMMM...",
        "...mmmmmm...",
        "..tc....ct..",
        ".t........c.",
        ".t.T......c.",
        ".t.T......c.",
        ".t........c.",
        ".t........C.",
        ".t........C.",
        "..t......C..",
        "...CCCCCC...",
    ],
    # 同一个罐子，装了金黄的松脂（满到肩），罐口挂着一滴
    "icon_sap": [
        "...MMMMMM...",
        "...mmmmmm...",
        "..tc..y.ct..",
        ".t....y...c.",
        ".tYYYYYYYYc.",
        ".tyTyyyyyOc.",
        ".tyTyyyyOOc.",
        ".tyyyyyOOOC.",
        ".tOyyyOOOoC.",
        "..tOOOOOoC..",
        "...CCCCCC...",
    ],
    "icon_spring": _spring_rows(),
    "icon_valve": _valve_rows(),
    # 树屋里那台收音机：木壳，左边格栅，右边刻度窗（指针）和两个旋钮，挂着暗的小姓名牌
    "icon_radio": [
        "................",
        ".LLLLLLLLLLLL...",
        ".wwwwwwwwwwwwh..",
        ".wbbbbbwyyywwh..",
        ".wwwwwwwyoywwzz.",
        ".wbbbbbwyyywwzz.",
        ".wwwwwwwwwwww...",
        ".wbbbbbwnwnww...",
        ".wwwwwwwwwwww...",
        ".BBBBBBBBBBBB...",
        "..b........b....",
    ],
    # 那个自己转的路标：木杆，顶上一块朝右的箭头牌（受光），下面一块朝左的小牌，十字脚，挂姓名牌
    "icon_sign": [
        ".....bL.........",
        ".....bLLLLLLLL..",
        ".....bwwwwwwwwL.",
        ".....bwBBBBwwwwL",
        ".....bwwwwwwwwL.",
        ".....bBBBBBBBB..",
        ".....bh.........",
        "..BBBbh.........",
        ".Bwwwbzz........",
        "..BBBbzz........",
        ".....b..........",
        ".....b..........",
        ".....b..........",
        ".....bB.........",
        "...bbbbbb.......",
    ],
    # 一盏旧油灯（不亮）：铜灯座，蒙了灰的暗玻璃罩（左边一道高光），灯芯是暗的，灯颈上挂着姓名牌
    "icon_lamp": [
        "......mm........",
        ".....mMMm.......",
        "......CC........",
        ".....tCCC.......",
        "....tCCCCC......",
        "....tCbbCC......",
        "....tCbbCC......",
        ".....tCCC.......",
        "....mmmmmmh.....",
        "...mOOOOOOmh....",
        "..mOyOOOOOOmh...",
        "..mOyOOOOOom.zz.",
        "...mooooooom.zz.",
        "....mmmmmmm.....",
    ],
    # 蓝色小石头（不发光，暗一点的灰蓝）：扁卵石，左上受光；中间一道放拇指的浅槽（上沿是槽壁的影子、下面一道受光）
    "icon_blue_stone": [
        "....DDDDD....",
        "..DCuuCCCD...",
        ".DCuCCCCCCCD.",
        "DCuCCDDDDCCCD",
        "DCCCCuuuuCCCD",
        ".DCCCCCCCCCD.",
        "..DDCCCCCDD..",
        "....DDDDD....",
    ],
    # 明信片：暖白的卡片，右上一枚锈红邮票，盖着半个邮戳圈（两道波浪线），左边几行字，中间一道竖线
    "icon_postcard": [
        "PPPPPPPPPPPPPP",
        "PppppppPppRRrP",
        "PpeeeppPppRrRP",
        "PppppppPeeeeeP",
        "PpeeeepPpeppeP",
        "PppppppPppppqP",
        "PpeeeppPpeeepP",
        "PppppppPppppqP",
        "qqqqqqqqqqqqqq",
    ],
})


def icon(name):
    rows = ICONS[name]
    c = Canvas.from_rows(rows, ICON_PAL)
    return c.trim()



# ============================================================ 拼起来
def build():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in ("room_bg.png", "room_bg.png.import", "room_bg.json"):          # 第一版（透视房间）不要了
        (OUT / old).unlink(missing_ok=True)
    back, _ = bark_layer()
    c = cv(back)
    fungus(c)
    chimney_out(c)
    pulley(c)
    bark_raw = back.copy()
    cav, lip = interior(back)
    back = despeckle(back, max_dL=0.06)[0]
    back = limit_colors(back, 200)
    fr = front(cav, lip, bark_raw)
    fr = despeckle(fr, max_dL=0.06)[0]
    fr = limit_colors(fr, 140)
    # 前墙必须盖满屋内 + 切口（back 上那一块），一个像素都不漏
    hole = cut_mask() & (fr[..., 3] == 0)
    assert not hole.any(), f"front 漏了 {int(hole.sum())} 个像素"
    # 前墙盖在树皮上的那部分和 back 的树皮颜色一样（只差 limit_colors 的合并），接缝看不出来
    Canvas(1, 1, back).save(OUT / "treehouse_back.png")
    Canvas(1, 1, fr).save(OUT / "treehouse_front.png")
    Canvas(1, 1, light_shaft()).save(OUT / "room_light.png")

    objs = {}

    def rel(x, y):
        return int(x) - CX, int(y) - H

    def put(name, canv, ax, ay, frames=1, fw=None, extra=None):
        """底边中点踩在图坐标 (ax, ay)（ay = 台面那一行，物件最下一行在 ay-1）。"""
        fw = fw or canv.w
        x, y = int(round(ax - fw / 2)), int(ay - canv.h)
        rx, ry = rel(x, y)
        objs[name] = {"x": rx, "y": ry, "w": fw, "h": canv.h, "frames": frames, **(extra or {})}

    def save(name, canv):
        canv.save(OUT / f"{name}.png")

    def sheet(name, frames, fw, fh, ms, states=None):
        s = Canvas(fw * len(frames), fh)
        for i, f in enumerate(frames):
            s.a[:, i * fw:(i + 1) * fw] = f.a
        save(name, s)
        meta = {"frame_w": fw, "frame_h": fh, "frames": len(frames), "ms": ms}
        if states:
            meta["states"] = states
        (OUT / f"{name}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")

    r = radio()
    save("room_radio", r)
    put("room_radio", r, SHELF_X[0] + 3 + r.w / 2, FL - SHELF_H[0])
    lm = lamp_mark()
    save("room_lamp_mark", lm)
    put("room_lamp_mark", lm, LAMP_X + 0.5, FL - SHELF_H[0] + 1)    # 盖在隔板顶那一行上
    la = lamp()
    save("room_lamp", la)
    put("room_lamp", la, LAMP_X + 2, FL - SHELF_H[0])            # 灯座中心对准印子（图右边多出来的是姓名牌）
    f, fw, fh = sign_frames()
    sheet("room_sign", f, fw, fh, 250)
    put("room_sign", f[0], X(175) + 1, FL, frames=4, fw=fw)
    ch = chairs()
    save("room_chairs", ch)
    rx, ry = rel(CHAIR_SPAN[0], FL - ch.h)
    objs["room_chairs"] = {"x": rx, "y": ry, "w": ch.w, "h": ch.h, "frames": 1}
    f, fw, fh = kettle_frames()
    sheet("room_kettle", f, fw, fh, 300)
    put("room_kettle", f[0], X(45), FL - 28, frames=2, fw=fw)
    cu = cups()
    save("room_cups", cu)
    put("room_cups", cu, X(101), TABLE_TOP)
    di = dish()
    save("room_dish", di)
    put("room_dish", di, BENCH_X[0] + 7, BENCH_TOP)
    f, fw, fh = gramophone_frames()
    sheet("room_gramophone", f, fw, fh, 0, states=["old", "new"])
    put("room_gramophone", f[0], X(78), TABLE_TOP, frames=2, fw=fw, extra={"states": ["old", "new"]})
    pk = part_pack()
    save("room_part_pack", pk)
    put("room_part_pack", pk, X(91), TABLE_TOP)                    # 留声机和杯子之间（不重叠）
    bx = seed_box()
    save("room_box", bx)
    put("room_box", bx, SMALL_SHELF[0] + 6, SMALL_SHELF[2])
    pcd = postcard()
    save("room_postcard", pcd)
    put("room_postcard", pcd, SMALL_SHELF[1] - 3, SMALL_SHELF[2])    # 盒子旁边，玻璃下压着
    tw = toolwall()
    save("room_toolwall", tw)
    put("room_toolwall", tw, (BENCH_X[0] + BENCH_X[1]) / 2, FL - 36)  # 工作台上方的墙上（管道下面）
    pc, (px0, py0), segs, leaks = pipes()
    for name, a, b in segs:
        part = Canvas(b - a, pc.h, pc.a[:, a:b])
        ys, xs = np.nonzero(part.mask)
        t = part.trim()
        save(name, t)
        rx, ry = rel(px0 + a + int(xs.min()), py0 + int(ys.min()))
        lx, ly = leaks[name]
        objs[name] = {"x": rx, "y": ry, "w": t.w, "h": t.h, "frames": 1, "leak": list(rel(px0 + lx, py0 + ly))}
    f, fw, fh = steam_frames()
    sheet("pipe_steam", f, fw, fh, 150)
    lx, ly = objs["pipe_c"]["leak"]
    objs["pipe_steam"] = {"x": lx - fw // 2, "y": ly - fh, "w": fw, "h": fh, "frames": 3, "on": "pipe_c"}
    tl = tools()
    for (name, t), cxx in zip(tl.items(), (X(208), X(228), X(248))):
        save(name, t)
        put(name, t, cxx, BENCH_TOP)

    # 图标
    for name in ICONS:
        save(name, icon(name))

    def mid(n):
        return objs[n]["x"] + objs[n]["w"] // 2

    hot = {"door": X(18) - CX, "stove": mid("room_kettle"), "box": mid("room_box"),
           "postcard": mid("room_postcard"), "lamp": LAMP_X - CX, "part_pack": mid("room_part_pack"), "toolwall": mid("room_toolwall"),
           "chairs": X(116) - CX, "chair_free": X(60) - CX, "cups": mid("room_cups"),
           "gramophone": mid("room_gramophone"), "radio": mid("room_radio"),
           "shelf": (SHELF_X[0] + SHELF_X[1]) // 2 - CX, "sign": mid("room_sign"), "dish": mid("room_dish")}
    for n in ("pipe_a", "pipe_b", "pipe_c", "tool_a", "tool_b", "tool_c"):
        hot[n] = mid(n)
    meta = {
        "size": [W, H],
        "anchor": "底边中点 = 世界里的 (树屋 x, 地面 228)；两张图（back / front）和 room_light 同尺寸同锚点",
        "floor_offset": 0,
        "walk_min": X(8) - CX,
        "walk_max": X(252) - CX,
        "door_x": X(18) - CX,
        "layers": ["treehouse_back", "objects (room_*, pipe_*, tool_*；room_lamp_mark 一直显示、在 room_lamp 下面)", "room_light（半透明）", "人物",
                   "treehouse_front（进屋淡出 / 出屋淡入）"],
        "note": "所有坐标都是相对锚点（图底边中点）的偏移：x 往右、y 往上为负。objects 的 x,y = 左上角；"
                "多帧的 w = 帧宽。hotspots = 人走到这个 x 互动。pipe_*.leak = 那段漏气时细白汽（pipe_steam，底边中点）"
                "的位置，默认漏 pipe_c。chairs = 带垫子那把（不给晨坐的），chair_free = 晨能坐的那把。",
        "objects": objs,
        "hotspots": hot,
    }
    (OUT / "treehouse.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    return meta


# ============================================================ 预览
def load(name):
    return np.array(Image.open(OUT / f"{name}.png").convert("RGBA"))


def over(dst, src, x, y):
    """贴图：不透明的直接盖，半透明的按 alpha 混。"""
    h, w = src.shape[:2]
    H_, W_ = dst.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W_, x + w), min(H_, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x].astype(float)
    d = dst[y0:y1, x0:x1].astype(float)
    al = s[..., 3:4] / 255
    d[..., :3] = d[..., :3] * (1 - al) + s[..., :3] * al
    d[..., 3:4] = np.maximum(d[..., 3:4], s[..., 3:4])
    dst[y0:y1, x0:x1] = np.round(d).astype(np.uint8)


def x3(a):
    return Image.fromarray(a).resize((a.shape[1] * 3, a.shape[0] * 3), Image.NEAREST)


def preview(meta, out_dir: Path, forest_png: Path | None):
    out_dir.mkdir(parents=True, exist_ok=True)
    if forest_png and forest_png.exists():
        bg = np.array(Image.open(forest_png).convert("RGBA"))
        if bg.shape[:2] != (270, 480):        # Godot 截图 3024×1701：按 480×270 的像素中心取样还原
            Hh, Ww = bg.shape[:2]
            ys = ((np.arange(270) + 0.5) * Hh / 270).astype(int)
            xs = ((np.arange(480) + 0.5) * Ww / 480).astype(int)
            bg = bg[ys][:, xs]
    else:
        bg = np.full((270, 480, 4), (30, 40, 36, 255), np.uint8)
    ox, oy = 240 - CX, 228 - H            # 树屋锚点放在屏幕 x=240、地面 228
    chen = np.array(Image.open(ROOT / "art/characters/chen/chen_oscar.png").convert("RGBA"))[:, 7 * 68:8 * 68]
    snake = np.array(Image.open(ROOT / "art/characters/snake/snake.png").convert("RGBA"))[:, 0:31]
    s_foot = int(np.nonzero(snake[..., 3].any(1))[0].max())

    inside = bg.copy()
    over(inside, load("treehouse_back"), ox, oy)
    for name, o in meta["objects"].items():
        over(inside, load(name)[:, :o["w"]], ox + CX + o["x"], oy + H + o["y"])
    over(inside, load("room_light"), ox, oy)
    cx_chen = ox + CX + meta["hotspots"]["shelf"] + 4
    over(inside, chen, cx_chen - 28, 228 - 56)
    sn = snake[:, ::-1].copy()
    over(inside, sn, ox + CX + meta["hotspots"]["sign"] + 14 - 15, 228 - s_foot)
    x3(inside).save(out_dir / "inside_x3.png")

    outside = bg.copy()
    over(outside, load("treehouse_back"), ox, oy)
    over(outside, load("treehouse_front"), ox, oy)
    over(outside, chen, ox - 40, 228 - 56)
    x3(outside).save(out_dir / "outside_x3.png")

    # 和森林原图放一起比（各 2 倍，上下排）：原图 / 屋外 / 屋里
    stack = np.concatenate([bg, outside, inside], 0)
    Image.fromarray(stack).resize((960, 1620), Image.NEAREST).save(out_dir / "compare_forest_outside_inside_x2.png")

    # 特写：管道 + 汽 3 帧、留声机 old/new、工作台上的三把工具和碟子（5 倍）
    o = meta["objects"]
    base = load("treehouse_back")

    def crop_with(names, x0, y0, w, h, frame=None):
        cr = base[y0:y0 + h, x0:x0 + w].copy()
        for n in names:
            src = load(n)
            fw = o[n]["w"]
            k = frame.get(n, 0) if frame else 0
            over(cr, src[:, k * fw:(k + 1) * fw], CX + o[n]["x"] - x0, H + o[n]["y"] - y0)
        return cr

    px0, py0 = CX + o["pipe_a"]["x"] - 4, H + o["pipe_c"]["y"] - 16
    blocks = [crop_with(["pipe_a", "pipe_b", "pipe_c", "pipe_steam"], px0, py0, 100, 26, {"pipe_steam": k}) for k in range(3)]
    gx, gy = CX + o["room_gramophone"]["x"] - 14, H + o["room_gramophone"]["y"] - 4
    blocks += [crop_with(["room_gramophone", "room_cups"], gx, gy, 60, 30, {"room_gramophone": k}) for k in range(2)]
    tx, ty = CX + o["room_dish"]["x"] - 4, H + o["tool_a"]["y"] - 10
    blocks.append(crop_with(["room_dish", "tool_a", "tool_b", "tool_c"], tx, ty, 80, 24))
    Wd = max(b.shape[1] for b in blocks)
    Hd = sum(b.shape[0] + 3 for b in blocks)
    sh = np.full((Hd, Wd, 4), (20, 24, 22, 255), np.uint8)
    y = 0
    for b in blocks:
        sh[y:y + b.shape[0], :b.shape[1]] = b
        y += b.shape[0] + 3
    Image.fromarray(sh).resize((Wd * 5, Hd * 5), Image.NEAREST).save(out_dir / "closeups_x5.png")

    # 图标 1 倍和 4 倍（最后两个是 level1 的 wood / icon_bag 作对照）
    ic = [load(n) for n in ICONS] + [np.array(Image.open(ROOT / "art/level1/wood.png").convert("RGBA")),
                                    np.array(Image.open(ROOT / "art/level1/icon_bag.png").convert("RGBA"))]
    cell = 20
    strip = np.full((cell, cell * len(ic), 4), (40, 44, 50, 255), np.uint8)
    for i, a in enumerate(ic):
        over(strip, a, i * cell + (cell - a.shape[1]) // 2, (cell - a.shape[0]) // 2)
    big = np.array(Image.fromarray(strip).resize((strip.shape[1] * 4, cell * 4), Image.NEAREST))
    comb = np.full((cell + 8 + cell * 4, strip.shape[1] * 4, 4), (40, 44, 50, 255), np.uint8)
    comb[:cell, :strip.shape[1]] = strip
    comb[cell + 8:] = big
    Image.fromarray(comb).save(out_dir / "icons_x1_x4.png")

    # 物件全部帧（4 倍，暗底）
    items = ["room_radio", "room_sign", "room_chairs", "room_kettle", "room_cups", "room_dish", "room_gramophone",
             "room_box", "pipe_a", "pipe_b", "pipe_c", "pipe_steam", "tool_a", "tool_b", "tool_c"]
    arrs = [load(n) for n in items]
    Wd = max(a.shape[1] for a in arrs) + 4
    Hd = sum(a.shape[0] + 4 for a in arrs)
    s = np.full((Hd, Wd, 4), (34, 38, 36, 255), np.uint8)
    y = 2
    for a in arrs:
        over(s, a, 2, y)
        y += a.shape[0] + 4
    Image.fromarray(s).resize((Wd * 4, Hd * 4), Image.NEAREST).save(out_dir / "objects_x4.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default=None)
    ap.add_argument("--forest", default=None, help="森林真实背景截图（Godot 3024×1701 或 480×270）")
    args = ap.parse_args()
    meta = build()
    print(json.dumps({k: meta[k] for k in ("size", "floor_offset", "walk_min", "walk_max", "door_x")}))
    if args.preview:
        preview(meta, Path(args.preview), Path(args.forest) if args.forest else None)


if __name__ == "__main__":
    main()
