"""河流篇：妮芙家（剖面小屋）+ 屋里会换状态的物件 + 特写大图。以后改这些图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_home_art.py [--preview 目录]

方向（docs/river_plan.md 第 1.1 / 2.3 节，作者定）：
- 平面剖面，绝对不要透视：正侧面，像横版卷轴里把房子前墙拿掉看进去（和森林树屋一样的做法）。
- 塞得满、有生活气息：私人空间就是她唯一的家当。东西多但不乱：每样东西有自己的位置、几乎都贴着标签（原文 81）。
- 配色还是忧郁的：灰蓝做底（第 0 节身份色），光只从后墙的窗进来（白天、河面反上来的冷光），
  暖色只给标签纸（琥珀小纸片）。不做成温馨咖啡馆：没有暖灯，吊灯不亮，炉子冷着。
- 房子在新旧水位交界处（原文 80）：屋里地板就是现在的水面那一层，后墙上留着一道旧水位的水渍；
  地板下面泡在水里的旧一层（旧门、旧门牌）由会话 C 画在河岸栈道下面；现在的地址牌在前墙门右边（图里 x≈65、离地约 30），正对着下面的旧门牌。

原文写到、这里画了的（行号 = 剧情姐合订稿 yun1.txt）：
  81 几乎每件东西都有标签（空罐「盐，很咸，尝过了」）、桌边翻软的小本子；82 计时器、厨房、两碗热水；83 桌上的沙漏；
  86 面包、盘子；87 桌上的轻铃（沙漏漏完响）；89 来客册（收据、包装纸、干花）、杯子；91–92 窗边晾册子、窗边通风处的椅子；
  93 干燥的桌角（通讯器）；95–96 柜子 + 柜门上的索引、长柄水壶、金属影像盒、播放器、插头；
  116 阿汀把外套搭到椅背上、旧家照片；120 夹子、湿纸（纸套）一张一张摆开；83 她会划船（门边的桨）；
  119 晚上睡觉的地方（床）；152 / 146 桌上两碗热水 → 两杯茶。

输出（art/river_home/）：
- home_back.png   屋子剖面（屋顶、后墙、窗、厨房、桌、柜、床、架子……不换状态的东西），一直显示；
- home_front.png  前墙（门、门边现在的地址、两扇前窗、水渍），盖在屋内上面，进屋淡出、出屋淡入；
- home_light.png  窗里斜进来的一道冷光 + 地上的一块亮（半透明，盖在家具上、人下面）；
- obj_*.png       会换状态的物件（多帧横排）；
- footage_*.png   影像整段（多帧横排，每帧 112×80，100ms；播放器屏幕里是它缩小的）；
- room.json       照 docs/river_rooms_contract.md 1.6：host、x、尺寸、地板、可走范围、门、markers、objects（键 = 剧本 prop id）。
特写大图在 art/river_story/closeup_<名字>[_<状态>].png（原生，最大 480×270；_en 是英文版）。
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
OUT = ROOT / "art" / "river_home"

W, H = 420, 176                 # back / front 的尺寸；底边 = 屋里地板那一行（物件的底边踩在这一行下面）
CX = W // 2                     # 锚点 x（底边中点）
IX0, IX1 = 20, 400              # 屋内左右（宽 380）；整张宽 420，河岸给小屋留了 x 680–1100（会话 C）
FL = H                          # 屋内地板
CEIL = FL - 118                 # 屋内顶（天花板下沿）
WALL_T = 6                      # 剖开的墙 / 楼板厚
STEP = 0.042                    # 一档明暗


def X(c):
    """屋内坐标（从屋内左墙算起）→ 图坐标。"""
    return IX0 + c


# 光：后墙的窗（白天，河面反上来的冷光）。屋里没有别的光（吊灯不亮、炉子冷着：作者「不要温馨咖啡馆」）。
WIN_RECT = (X(208), FL - 94, X(256), FL - 48)       # 窗洞（x0, y0, x1, y1）
WIN_C = ((WIN_RECT[0] + WIN_RECT[2]) // 2, (WIN_RECT[1] + WIN_RECT[3]) // 2)
WIN = Light(WIN_C[0], WIN_C[1], 34, power=1.0, radius=170)
LIGHTS = (WIN,)

COOL_H, DAY_H, WARM_H = 255.0, 220.0, 75.0

N_WALL = smooth_noise(H, W, 12, 50, seed=21)
N_MISC = smooth_noise(H, W, 30, 30, seed=22)
N_FLOOR = smooth_noise(H, W, 60, 4, seed=23)


def col(L, C, h):
    return from_lch(L, C, h)


def cv(img) -> Canvas:
    c = Canvas(1, 1)
    c.a = img
    return c


def mrect(x0, y0, x1, y1, shape=(H, W)):
    m = np.zeros(shape, bool)
    m[max(0, y0):max(0, y1 + 1), max(0, x0):max(0, x1 + 1)] = True
    return m


# ============================================================ 打光：窗光 → 一档一档的色块（正侧面）
def shade(img, mask, L0, C0, h0, z=0.0, gain=0.55, center=0.18, noise=None, noise_amp=0.6, cell=(10, 14), seed=0,
          day=1.0, lights=LIGHTS):
    """给一块正对镜头的面上色：亮度 = 底色 + gain×(光 - center)，按 STEP 分档（三角网格上分段线性，块边是直线）；
    窗光多的块往冷白的日光偏，暗的块往冷蓝偏。"""
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return img
    Hh, Ww = mask.shape
    gy, gx = np.mgrid[0:Hh, 0:Ww].astype(float)
    I = np.zeros((Hh, Ww))
    for L in lights:
        v = np.stack([L.x - gx, L.y - gy, np.full_like(gx, L.z - z)], -1)
        d = np.linalg.norm(v, axis=-1) + 1e-6
        lam = np.clip(v[..., 2] / d, 0, 1)
        I += L.power * lam / (1 + (d / L.radius) ** 2)
    F = gain * (I - center)
    if noise is not None:
        F = F + noise_amp * STEP * noise
    F = polygonal(F, cell[0], cell[1], seed=seed)
    T = polygonal(I, cell[0], cell[1], seed=seed)
    k = np.round(F[ys, xs] / STEP)
    td = np.clip(np.round(T[ys, xs] * 3 * day) / 3, 0, 1)
    L = np.clip(L0 + k * STEP, 0.07, 0.95)
    hr = math.radians(h0)
    a = np.full(len(ys), C0 * math.cos(hr))
    b = np.full(len(ys), C0 * math.sin(hr))
    cool = np.clip(-k, 0, 3) / 3 * 0.008
    for amt, hh in ((cool, COOL_H), (td * 0.012, DAY_H)):
        a += amt * math.cos(math.radians(hh))
        b += amt * math.sin(math.radians(hh))
    img[ys, xs, :3] = oklab_to_srgb(np.stack([L, a, b], 1))
    img[ys, xs, 3] = 255
    return img


def lit_at(x, y, z=6.0):
    """某一点的窗光（0..1 左右），小物件用它决定自己亮一档还是暗一档。"""
    s = 0.0
    for L in LIGHTS:
        v = np.array([L.x - x, L.y - y, L.z - z], float)
        d = np.linalg.norm(v) + 1e-6
        s += L.power * max(0.0, v[2] / d) / (1 + (d / L.radius) ** 2)
    return s


def lc(L, C, h, x, y, z=6.0, gain=0.5, center=0.18):
    """小物件的颜色：按所在位置的窗光加减整档。"""
    k = round(gain * (lit_at(x, y, z) - center) / STEP)
    return col(min(0.9, max(0.08, L + k * STEP)), C, h if k >= 0 else h + 6)


def darken(img, m, steps=1.0):
    sel = m[:img.shape[0], :img.shape[1]] & (img[..., 3] > 0)
    if not sel.any():
        return
    lab = srgb_to_oklab(img[sel][:, :3])
    lab[:, 0] -= STEP * steps
    lab[:, 1:] *= 0.92
    lab[:, 1] += 0.004 * math.cos(math.radians(COOL_H)) * steps
    lab[:, 2] += 0.004 * math.sin(math.radians(COOL_H)) * steps
    img[sel, :3] = oklab_to_srgb(lab)


def limit_colors(a: np.ndarray, n: int) -> np.ndarray:
    """整张图压到 n 种颜色（中位切分，不抖动）；透明的地方不动。"""
    m = a[..., 3] > 0
    im = Image.fromarray(a[..., :3]).quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = a.copy()
    out[..., :3] = np.array(im.convert("RGB"))
    out[~m] = 0
    return out


# ============================================================ 颜色（灰蓝底；木头灰褐；暖色只给标签纸）
PLASTER = (0.31, 0.016, 238)    # 后墙灰泥
PANEL = (0.25, 0.014, 70)       # 护墙板（灰褐木）
BEAM = (0.20, 0.012, 60)
WOOD = (0.27, 0.018, 68)        # 家具木头
WOOD_D = (0.21, 0.015, 60)
IRON = (0.22, 0.008, 240)
SLATE = (0.24, 0.014, 245)      # 屋顶石板
STONE = (0.30, 0.012, 230)
TAG = col(0.60, 0.045, 80)      # 标签：琥珀小纸片（全屋唯一的暖色）
TAG_D = col(0.50, 0.040, 72)
INK = col(0.30, 0.02, 250)
STRING = col(0.26, 0.012, 60)
PAPER = col(0.52, 0.016, 95)    # 纸（灰白，比标签冷）
PAPER_D = col(0.44, 0.014, 90)
CLOTH_TEAL = (0.33, 0.030, 195)  # 雨衣、毯子：低饱和的青、灰玫、芥末
CLOTH_ROSE = (0.36, 0.030, 10)
CLOTH_MUST = (0.40, 0.035, 90)
GLASS = (0.34, 0.020, 215)


TAGS: list = []                 # 画 home_back 时记下每张标签的位置（obj_labels 用）


def tag(c: Canvas, x, y, w=2, h=2, string=0):
    """标签：一根短线（可选）+ 小纸片（左上亮、右下暗一档）。"""
    for i in range(string):
        c.put(x, y + i, STRING)
    y += string
    if c.w == W and c.h == H:
        TAGS.append((x, y, w, h))
    c.rect(x, y, x + w - 1, y + h - 1, TAG)
    c.put(x + w - 1, y + h - 1, TAG_D)
    if w >= 4 and h >= 3:
        c.line(x + 1, y + 1, x + w - 2, y + 1, TAG_D)


def box(img, x0, y0, x1, y1, base, z=8.0, top=1, seed=0, cell=(8, 8), gain=0.5):
    """正侧面的一个盒子 / 柜子：正面打光，顶边亮一档落灰，底下一行暗一档。"""
    m = mrect(x0, y0, x1, y1, img.shape[:2])
    shade(img, m, *base, z=z, cell=cell, seed=seed, gain=gain)
    if top:
        tm = mrect(x0, y0, x1, y0 + top - 1, img.shape[:2])
        darken(img, tm, -1)
    darken(img, mrect(x0, y1, x1, y1, img.shape[:2]), 1)
    return m


def shelf_board(img, x0, x1, y, base=WOOD, bracket=True):
    box(img, x0, y, x1, y + 1, base, z=10, top=0)
    darken(img, mrect(x0, y + 2, x1, y + 2, img.shape[:2]), 1.5)    # 隔板下面一道影子落在墙上
    if bracket:
        c = cv(img)
        for bx in (x0 + 3, x1 - 3):
            c.line(bx, y + 2, bx, y + 4, col(*WOOD_D))
            c.put(bx - 1 if bx > x0 + 3 else bx + 1, y + 2, col(*WOOD_D))


# ============================================================ 屋子壳：屋顶、剖开的墙和楼板、后墙
ROOF_EAVE = CEIL - WALL_T - 1   # 屋檐那一行
ROOF_TOP = 26                   # 屋脊


def shell():
    img = np.zeros((H, W, 4), np.uint8)
    c = cv(img)
    # 后墙：灰泥，上面是旧水位以上的；FL-42 一道旧水渍，下面泛一点青；最下面一圈护墙板
    wall = mrect(IX0, CEIL, IX1 - 1, FL - 1)
    shade(img, wall, *PLASTER, z=0, gain=0.36, center=0.14, noise=N_WALL, noise_amp=0.8, cell=(26, 30), seed=1)
    stain_y = FL - 42
    st = mrect(IX0, stain_y + 1, IX1 - 1, FL - 1)
    darken(img, st, 0.6)
    tint(img, st, 180, 0.006)
    rng = np.random.default_rng(5)
    for x in range(IX0, IX1):                       # 水渍线：一条不太齐的深线
        yy = stain_y + (1 if (x // 23) % 3 == 0 else 0)
        darken(img, mrect(x, yy, x, yy), 1.4)
        if rng.random() < 0.05:
            darken(img, mrect(x, yy + 1, x, yy + 1 + rng.integers(1, 4)), 0.8)
    pan = mrect(IX0, FL - 28, IX1 - 1, FL - 1)
    shade(img, pan, *PANEL, z=1, noise=N_FLOOR, cell=(16, 10), seed=2)
    for x in range(IX0 + 9, IX1, 13):               # 竖板缝
        darken(img, mrect(x, FL - 27, x, FL - 1), 1)
    darken(img, mrect(IX0, FL - 28, IX1 - 1, FL - 28), -1)    # 护墙板顶边压条
    darken(img, mrect(IX0, FL - 27, IX1 - 1, FL - 27), 1)
    # 天花板下面两根梁的端头 + 一条贯通的檩
    darken(img, mrect(IX0, CEIL, IX1 - 1, CEIL + 2), 1.5)
    for bx in range(IX0 + 40, IX1 - 10, 92):
        box(img, bx, CEIL, bx + 7, CEIL + 5, (0.27, 0.014, 65), z=20, top=0, cell=(6, 6))
        darken(img, mrect(bx + 7, CEIL, bx + 7, CEIL + 5), 1)
    # 剖开的墙和楼板（截面：深一点的灰石 + 一道亮边，像切开的面）
    sec = (mrect(IX0 - WALL_T, CEIL - WALL_T, IX0 - 1, FL - 1) | mrect(IX1, CEIL - WALL_T, IX1 + WALL_T - 1, FL - 1)
           | mrect(IX0 - WALL_T, CEIL - WALL_T, IX1 + WALL_T - 1, CEIL - 1))
    shade(img, sec, 0.20, 0.010, 235, z=40, gain=0.2, cell=(8, 8), seed=3)
    darken(img, mrect(IX0 - WALL_T, CEIL - WALL_T, IX1 + WALL_T - 1, CEIL - WALL_T), -1.5)
    darken(img, mrect(IX0 - WALL_T, CEIL - WALL_T, IX0 - WALL_T, FL - 1), -1)
    darken(img, mrect(IX1 + WALL_T - 1, CEIL - WALL_T, IX1 + WALL_T - 1, FL - 1), 1)
    # 屋顶：浅坡石板，两头出檐；一根铁皮烟囱、一根晾衣绳挂着两件东西（河边一直在晾东西，原文 79 / 91 / 119）
    x0, x1 = IX0 - WALL_T - 8, IX1 + WALL_T + 8
    ridge_x0, ridge_x1 = CX - 60, CX + 60
    pts = [(x0, ROOF_EAVE), (ridge_x0, ROOF_TOP), (ridge_x1, ROOF_TOP), (x1, ROOF_EAVE)]
    roof = Canvas(W, H).poly(pts)
    roof &= ~mrect(0, ROOF_EAVE + 1, W - 1, H - 1)
    shade(img, roof, *SLATE, z=60, gain=0.2, center=0.1, noise=N_MISC, noise_amp=0.4, cell=(30, 10), seed=4)
    for y in range(ROOF_TOP + 3, ROOF_EAVE, 4):    # 石板一排一排
        row = roof & mrect(0, y, W - 1, y)
        darken(img, row, 1)
        for x in range(0, W, 9):
            xx = x + (4 if (y // 4) % 2 else 0)
            darken(img, roof & mrect(xx, y - 3, xx, y - 1), 0.7)
    darken(img, roof & mrect(0, ROOF_TOP, W - 1, ROOF_TOP), -1.5)          # 屋脊受天光
    for x in range(x0, x1 + 1):                     # 屋檐下沿一道深
        c.put(x, ROOF_EAVE, col(0.16, 0.01, 245))
    # 屋檐和楼板之间露一截墙（灰泥，外墙色）
    gap = mrect(IX0 - WALL_T, ROOF_EAVE + 1, IX1 + WALL_T - 1, CEIL - WALL_T - 1)
    shade(img, gap, 0.27, 0.014, 235, z=40, gain=0.2, cell=(10, 6), seed=6)
    # 烟囱（铁皮，冷着：没有烟）
    chx = X(56)
    box(img, chx, ROOF_TOP + 2, chx + 5, ROOF_EAVE - 18, IRON, z=60, top=1, cell=(4, 6))
    box(img, chx - 1, ROOF_TOP, chx + 6, ROOF_TOP + 2, IRON, z=60, top=1, cell=(4, 4))
    # 屋顶晾衣绳：两根杆 + 一条下垂的绳 + 一块布、一只袜子、一个标签袋
    p0, p1 = X(280), X(360)
    for px in (p0, p1):
        c.line(px, roof_y(px) - 14, px, roof_y(px), col(*WOOD_D))
    for x in range(p0, p1 + 1):
        t = (x - p0) / (p1 - p0)
        c.put(x, int(roof_y(p0) - 13 + 4 * math.sin(math.pi * t) + (roof_y(p1) - roof_y(p0)) * t), STRING)
    cloth(c, X(296), roof_y(X(296)) - 10, 10, 9, CLOTH_TEAL)
    cloth(c, X(316), roof_y(X(316)) - 9, 4, 7, CLOTH_ROSE)
    cloth(c, X(334), roof_y(X(334)) - 9, 7, 6, CLOTH_MUST)
    return img


def roof_y(x):
    x0, x1 = IX0 - WALL_T - 8, IX1 + WALL_T + 8
    if x < CX - 60:
        return int(ROOF_EAVE + (ROOF_TOP - ROOF_EAVE) * (x - x0) / (CX - 60 - x0))
    if x > CX + 60:
        return int(ROOF_TOP + (ROOF_EAVE - ROOF_TOP) * (x - CX - 60) / (x1 - CX - 60))
    return ROOF_TOP


def cloth(c: Canvas, x, y, w, h, base):
    """挂着晾的一块布：上边夹两个夹子，下摆不齐，左亮右暗一档。"""
    L, C, hh = base
    for yy in range(h):
        for xx in range(w):
            if yy == h - 1 and (xx * 7 + y) % 3 == 0:
                continue
            k = 1 if xx < w // 2 else 0
            c.put(x + xx, y + yy, col(L + k * STEP, C, hh))
    c.put(x, y - 1, col(0.45, 0.01, 90))
    c.put(x + w - 1, y - 1, col(0.45, 0.01, 90))


def tint(img, m, hue, amt):
    sel = m[:img.shape[0], :img.shape[1]] & (img[..., 3] > 0)
    if not sel.any():
        return
    lab = srgb_to_oklab(img[sel][:, :3])
    lab[:, 1] += amt * math.cos(math.radians(hue))
    lab[:, 2] += amt * math.sin(math.radians(hue))
    img[sel, :3] = oklab_to_srgb(lab)


# ============================================================ 窗（窗外：对岸泡水的楼、河面、白天的天）
def window(img):
    c = cv(img)
    x0, y0, x1, y1 = WIN_RECT
    # 窗外
    for y in range(y0, y1 + 1):
        t = (y - y0) / (y1 - y0)
        L = 0.60 - 0.06 * t
        for x in range(x0, x1 + 1):
            c.put(x, y, col(L, 0.022, 225))
    rng = np.random.default_rng(8)
    wl = y1 - 9                                        # 窗外的水面
    bx = x0
    while bx < x1:                                     # 对岸的楼：灰色鸽子笼，下半截泡在水里
        bw = int(rng.integers(8, 15))
        top = y0 + int(rng.integers(4, 16))
        L = 0.46 + 0.04 * rng.random()
        for y in range(top, wl):
            for x in range(bx, min(bx + bw, x1 + 1)):
                c.put(x, y, col(L if x - bx < bw - 2 else L - STEP, 0.014, 235))
        for wy in range(top + 2, wl - 2, 4):           # 小窗格
            for wx in range(bx + 2, min(bx + bw - 2, x1 - 1), 3):
                if rng.random() < 0.8:
                    c.put(wx, wy, col(L - 2 * STEP, 0.014, 240))
        bx += bw + int(rng.integers(0, 3))
    for x in range(x0, x1 + 1):                        # 一条细桥连着屋顶（原文 71「细桥连接屋顶」）
        c.put(x, y0 + 13, col(0.40, 0.012, 240))
    for y in range(wl, y1 + 1):                        # 河面：灰蓝，一道一道亮纹
        for x in range(x0, x1 + 1):
            c.put(x, y, col(0.50 - 0.015 * (y - wl), 0.028, 215))
    for k in range(10):
        gy = wl + 1 + int(rng.integers(0, y1 - wl))
        gx = x0 + int(rng.integers(0, x1 - x0 - 4))
        for x in range(gx, gx + int(rng.integers(2, 6))):
            c.put(x, gy, col(0.62, 0.02, 210))
    # 窗框（木头，刷过的灰青漆，掉了）+ 十字棂
    fr = col(0.36, 0.018, 200)
    frd = col(0.29, 0.016, 205)
    c.rect(x0 - 3, y0 - 3, x1 + 3, y0 - 1, fr)
    c.rect(x0 - 3, y0, x0 - 1, y1, fr)
    c.rect(x1 + 1, y0, x1 + 3, y1, frd)
    mx, my = (x0 + x1) // 2, y0 + (y1 - y0) * 2 // 5
    c.rect(mx - 1, y0, mx, y1, frd)
    c.line(x0, my, x1, my, frd)
    # 窗台：深一点、往外伸（晾来客册的地方，原文 91）
    box(img, x0 - 8, y1 + 1, x1 + 8, y1 + 4, WOOD, z=12, top=1, cell=(10, 4))
    darken(img, mrect(x0 - 6, y1 + 5, x1 + 6, y1 + 6), 1.5)
    # 窗帘：一半拉开束在左边，灰玫色
    cr = Canvas(W, H)
    L, C, hh = CLOTH_ROSE
    for y in range(y0 - 2, y1 - 2):
        t = (y - y0) / (y1 - y0)
        wdt = int(10 - 6 * math.sin(math.pi * min(1, t * 1.6)))
        for x in range(x0 - 6, x0 - 6 + wdt):
            k = 1 if (x - x0) % 4 < 2 else 0
            cr.put(x, y, col(L - STEP + k * STEP, C, hh))
    over_mask(img, cr.a)
    c.line(x0 - 8, y0 - 4, x1 + 8, y0 - 4, col(*IRON))                     # 帘杆
    c.rect(x0 - 5, y0 + 18, x0 + 1, y0 + 19, col(0.28, 0.02, 60))           # 束帘的带子
    # 窗台上：两只玻璃瓶插着干花、一只小盆
    for px, ph in ((x1 - 2, 8), (x1 - 8, 6)):
        gl = col(*GLASS)
        c.rect(px, y1 + 1 - ph, px + 2, y1, gl)
        c.put(px + 2, y1 + 1 - ph, col(0.40, 0.02, 215))
        for k in range(3):
            c.line(px + 1, y1 - ph, px - 1 + k * 2, y1 - ph - 4 - k, col(0.34, 0.03, 120 - k * 30))
            c.put(px - 1 + k * 2, y1 - ph - 5 - k, col(0.45, 0.04, 30 + k * 30))
        tag(c, px, y1 - 2, 2, 1)


def over_mask(dst, src):
    m = src[..., 3] > 0
    dst[m] = src[m]


# ============================================================ 门边：衣钩、雨衣、桨、靴子、出门前的条子
def door_side(img):
    c = cv(img)
    # 门洞在前墙（home_front）上，后墙这里画门框的里侧（深一圈）——人从这里进出
    dx0, dx1, dtop = X(16), X(40), FL - 60
    m = mrect(dx0, dtop, dx1, FL - 1)
    shade(img, m, 0.25, 0.018, 205, z=2, gain=0.3, cell=(8, 10), seed=11)               # 门的里面：灰青漆的木板门
    for xx in range(dx0 + 5, dx1, 6):
        darken(img, mrect(xx, dtop + 1, xx, FL - 2), 1)
    for yy in (dtop + 8, FL - 12):
        darken(img, mrect(dx0 + 1, yy, dx1 - 1, yy + 1), -0.5)                          # 两道横档
    c.rect(dx0 + 2, dtop + 30, dx0 + 4, dtop + 31, col(*IRON))                           # 门闩
    c.put(dx0 + 5, dtop + 30, col(0.34, 0.01, 240))
    darken(img, mrect(dx0, FL - 1, dx1, FL - 1), 1)
    for k in range(3):                                                                   # 门缝透进来一点外面的光
        c.put(dx1, dtop + 10 + k * 14, col(0.42, 0.016, 215))
    box(img, dx0 - 2, dtop - 3, dx1 + 2, dtop - 1, WOOD_D, z=4, cell=(8, 4))
    box(img, dx0 - 3, dtop - 3, dx0 - 1, FL - 1, WOOD_D, z=4, top=0, cell=(4, 8))
    box(img, dx1 + 1, dtop - 3, dx1 + 3, FL - 1, WOOD_D, z=4, top=0, cell=(4, 8))
    # 衣钩板 + 雨衣（青灰）+ 一只布袋
    hx0, hx1, hy = X(0), X(14), FL - 70
    box(img, hx0, hy, hx1, hy + 2, WOOD, z=6, cell=(8, 4))
    for kx in (hx0 + 3, hx0 + 10, hx0 + 17):
        c.put(kx, hy + 3, col(*IRON))
    coat = Canvas(W, H)
    L, C, hh = CLOTH_TEAL
    for y in range(hy + 3, hy + 36):
        t = (y - hy - 3) / 33
        half = int(3 + 4 * t)
        for x in range(hx0 + 3 - half + 2, hx0 + 3 + half + 2):
            k = 1 if x < hx0 + 4 else 0
            if y > hy + 33 and (x % 3 == 0):
                continue
            coat.put(x, y, col(L + k * STEP - (STEP if t > 0.7 else 0), C, hh))
    over_mask(img, coat.a)
    c.rect(hx0 + 9, hy + 4, hx0 + 13, hy + 13, col(0.34, 0.02, 80))         # 布袋
    c.line(hx0 + 10, hy + 3, hx0 + 12, hy + 3, col(0.30, 0.02, 80))
    tag(c, hx0 + 10, hy + 8, 3, 2)
    tag(c, hx0 + 5, hy + 12, 2, 2)
    # 桨：靠在门边的墙上（她会划船，原文 83）
    ox = X(43)
    for y in range(FL - 76, FL):
        x = ox + (y - (FL - 76)) // 26
        c.put(x, y, lc(0.32, 0.02, 70, x, y))
    for y in range(FL - 22, FL):
        x = ox + (y - (FL - 76)) // 26
        c.rect(x - 2, y, x + 2, y, lc(0.30, 0.02, 70, x, y))
    tag(c, ox + 1, FL - 50, 2, 2, string=1)
    # 靴子一双、一只水桶
    for bx in (X(1), X(8)):
        c.rect(bx, FL - 9, bx + 4, FL - 1, col(0.22, 0.012, 230))
        c.rect(bx, FL - 3, bx + 6, FL - 1, col(0.20, 0.012, 230))
        c.put(bx, FL - 9, col(0.26, 0.012, 230))
    # 出门前看的条子（原文 81 第一页那句的意思：贴在门边，字太小看不清）
    note(c, X(1), FL - 88, 12, 9, lines=3)
    tag(c, X(14) - 1, FL - 80, 2, 2)


def note(c: Canvas, x, y, w, h, lines=2, pin=True, paper=PAPER):
    c.rect(x, y, x + w - 1, y + h - 1, paper)
    c.line(x + w - 1, y + 1, x + w - 1, y + h - 1, PAPER_D)
    c.line(x + 1, y + h - 1, x + w - 1, y + h - 1, PAPER_D)
    for i in range(lines):
        ly = y + 2 + i * 2
        if ly >= y + h - 1:
            break
        c.line(x + 2, ly, x + w - 3 - (i * 3) % 4, ly, INK)
    if pin:
        c.put(x + w // 2, y, col(0.40, 0.04, 30))


# ============================================================ 厨房：台子、冷着的小炉子和锅、水壶、计时器、两层罐子
K_X0, K_X1 = X(50), X(110)
K_TOP = FL - 30


def kitchen(img):
    c = cv(img)
    # 台子（下面两扇小门，帘子挡着一半）
    box(img, K_X0, K_TOP, K_X1, FL - 1, WOOD, z=12, top=2, seed=12, cell=(10, 10))
    darken(img, mrect(K_X0 + 1, K_TOP + 6, K_X1 - 1, K_TOP + 6), 1)
    for dx in (K_X0 + 22, K_X0 + 44):
        darken(img, mrect(dx, K_TOP + 7, dx, FL - 3), 1)
    cur = Canvas(W, H)
    for y in range(K_TOP + 7, FL - 2):
        for x in range(K_X0 + 2, K_X0 + 21):
            k = 1 if (x // 3) % 2 else 0
            cur.put(x, y, lc(0.30 + k * STEP, 0.022, 200, x, y, 13))
    over_mask(img, cur.a)
    tag(c, K_X0 + 30, K_TOP + 10, 3, 2)
    tag(c, K_X0 + 52, K_TOP + 10, 3, 2)
    # 炉子（铸铁小炉，两个灶眼，冷的）+ 锅
    sx0 = K_X0 + 4
    box(img, sx0, K_TOP - 8, sx0 + 22, K_TOP - 1, IRON, z=14, top=1, cell=(6, 6))
    c.rect(sx0 + 3, K_TOP - 5, sx0 + 8, K_TOP - 3, col(0.15, 0.008, 240))
    c.put(sx0 + 18, K_TOP - 5, col(0.32, 0.01, 240))                         # 旋钮
    c.put(sx0 + 20, K_TOP - 5, col(0.32, 0.01, 240))
    pot = (sx0 + 1, K_TOP - 17, sx0 + 11, K_TOP - 9)
    box(img, *pot, (0.30, 0.012, 230), z=16, top=1, cell=(6, 6))
    c.line(pot[0] - 2, pot[1] + 2, pot[0] - 1, pot[1] + 2, col(*IRON))
    c.line(pot[2] + 1, pot[1] + 2, pot[2] + 2, pot[1] + 2, col(*IRON))
    c.rect(pot[0] + 1, pot[1] - 1, pot[2] - 1, pot[1] - 1, col(0.34, 0.012, 230))
    c.put((pot[0] + pot[2]) // 2, pot[1] - 2, col(0.36, 0.012, 230))
    tag(c, pot[2] - 3, pot[1] + 3, 2, 2)
    # 水壶（右边灶眼）
    kx = sx0 + 13
    box(img, kx, K_TOP - 15, kx + 8, K_TOP - 9, (0.33, 0.016, 205), z=16, top=1, cell=(5, 5))
    c.line(kx + 9, K_TOP - 13, kx + 11, K_TOP - 16, col(0.30, 0.016, 205))
    c.line(kx + 2, K_TOP - 17, kx + 6, K_TOP - 17, col(0.28, 0.01, 60))
    c.put(kx + 1, K_TOP - 16, col(0.28, 0.01, 60))
    c.put(kx + 7, K_TOP - 16, col(0.28, 0.01, 60))
    # 洗菜盆 + 碗架
    bx = K_X0 + 26
    c.rect(bx, K_TOP - 4, bx + 13, K_TOP - 1, col(0.36, 0.012, 225))
    c.line(bx, K_TOP - 4, bx + 13, K_TOP - 4, col(0.42, 0.012, 225))
    for i in range(3):
        c.rect(bx + 17 + i * 3, K_TOP - 9, bx + 18 + i * 3, K_TOP - 1, lc(0.42, 0.02, 220 - i * 30, bx, K_TOP))
    # 计时器（原文 82）：台子右端，一只圆铁皮小钟
    tx = K_X1 - 9
    c.rect(tx, K_TOP - 7, tx + 6, K_TOP - 1, col(0.40, 0.025, 30))
    c.rect(tx + 1, K_TOP - 6, tx + 5, K_TOP - 3, col(0.52, 0.02, 90))
    c.put(tx + 3, K_TOP - 5, INK)
    c.put(tx + 3, K_TOP - 8, col(0.36, 0.02, 30))
    tag(c, tx + 1, K_TOP - 2, 2, 1)
    # 两层架子：罐子（每只都贴标签；空盐罐在下层中间，原文 81）
    for sy, items in ((FL - 58, JARS_1), (FL - 82, JARS_2)):
        shelf_board(img, K_X0 - 2, K_X1 + 2, sy)
        x = K_X0 + 1
        for w, h, colr, kind in items:
            jar(c, img, x, sy - 1, w, h, colr, kind)
            x += w + 2
    # 架子下面挂勺子、漏勺
    for i, (x, ln) in enumerate(((K_X0 + 6, 10), (K_X0 + 11, 12), (K_X0 + 16, 9), (K_X0 + 21, 11))):
        c.line(x, FL - 55, x, FL - 55 + ln, col(0.30, 0.01, 240))
        c.rect(x - 1, FL - 55 + ln, x + 1, FL - 54 + ln, col(0.32, 0.01, 240))
    # 一串挂着晾的干菜（芥末黄）
    for k in range(5):
        c.rect(K_X1 - 14 + k * 2, FL - 55, K_X1 - 13 + k * 2, FL - 48 + k % 2, lc(0.38, 0.035, 95 - k * 6, K_X1, FL - 50))
    c.line(K_X1 - 15, FL - 56, K_X1 - 4, FL - 56, STRING)


# 罐子：宽、高、颜色（L, C, h）、种类（jar 玻璃罐 / tin 铁罐 / bowl 摞起来的碗 / salt 空盐罐）
JARS_1 = [(6, 9, (0.40, 0.02, 215), "jar"), (5, 7, (0.34, 0.02, 30), "tin"), (7, 10, (0.38, 0.015, 230), "jar"),
          (6, 8, (0.42, 0.01, 90), "salt"), (5, 6, (0.30, 0.02, 200), "tin"), (8, 5, (0.44, 0.012, 230), "bowl"),
          (6, 9, (0.36, 0.02, 120), "jar")]
JARS_2 = [(5, 8, (0.36, 0.02, 200), "jar"), (6, 6, (0.32, 0.02, 30), "tin"), (6, 10, (0.40, 0.018, 220), "jar"),
          (7, 7, (0.34, 0.015, 240), "tin"), (5, 9, (0.38, 0.02, 100), "jar"), (6, 6, (0.30, 0.02, 60), "tin"),
          (6, 8, (0.42, 0.015, 215), "jar")]
SALT_X = None                   # 空盐罐的 x（build 时记下，写进 markers）


def jar(c: Canvas, img, x, base_y, w, h, colr, kind):
    global SALT_X
    L, C, hh = colr
    y0 = base_y - h + 1
    if kind == "bowl":
        for i in range(3):
            c.rect(x, base_y - i * 2 - 1, x + w - 1, base_y - i * 2, lc(L - i * 0.01, C, hh, x, y0))
            c.put(x + w - 1, base_y - i * 2, lc(L - STEP, C, hh, x, y0))
        return
    body = lc(L, C, hh, x, y0, 10)
    dark = lc(L - STEP, C, hh, x, y0, 10)
    c.rect(x, y0 + 1, x + w - 1, base_y, body)
    c.line(x + w - 1, y0 + 1, x + w - 1, base_y, dark)
    lid = lc(0.28 if kind != "tin" else L + 0.03, 0.012, 60 if kind != "tin" else hh, x, y0)
    c.rect(x, y0, x + w - 1, y0, lid)
    if kind == "jar":                                  # 玻璃罐里装着东西，上面一截空
        c.rect(x + 1, y0 + h // 2, x + w - 2, base_y - 1, lc(L - 0.04, C + 0.01, hh + 20, x, y0))
        c.put(x + 1, y0 + 2, lc(L + 0.06, C, hh, x, y0))
    if kind == "salt":
        SALT_X = x + w // 2
    tag(c, x + 1, base_y - h // 2, min(3, w - 2), 2 if h > 6 else 1)


# ============================================================ 桌子 + 两只凳子 + 吊灯 + 墙上的条子板
T_X0, T_X1 = X(124), X(182)
T_TOP = FL - 24
STOOL_L = (X(112), X(122))
STOOL_R = (X(184), X(194))


def table(img):
    c = cv(img)
    box(img, T_X0, T_TOP, T_X1, T_TOP + 2, WOOD, z=16, top=1, seed=13, cell=(10, 4))
    darken(img, mrect(T_X0 + 2, T_TOP + 3, T_X1 - 2, T_TOP + 4), 1)                # 桌裙
    for lx in (T_X0 + 3, T_X1 - 5):
        box(img, lx, T_TOP + 3, lx + 2, FL - 1, WOOD_D, z=16, top=0, cell=(4, 8))
    darken(img, mrect(T_X0 + 6, T_TOP + 12, T_X1 - 6, T_TOP + 12), -0.5)           # 横撑
    c.line(T_X0 + 6, T_TOP + 12, T_X1 - 6, T_TOP + 12, col(*WOOD_D))
    # 桌上一直在的：笔筒、一卷标签纸、一只贴标签的铁盒（会换状态的东西在 obj_table）
    px = T_X1 - 8
    c.rect(px, T_TOP - 6, px + 3, T_TOP - 1, lc(0.34, 0.02, 200, px, T_TOP))
    for k, hh in enumerate((30, 250, 90)):
        c.line(px + k, T_TOP - 7 - k % 2 - 2, px + k, T_TOP - 7, col(0.40, 0.03, hh))
    c.rect(px - 6, T_TOP - 3, px - 3, T_TOP - 1, TAG)                                 # 标签纸卷
    c.put(px - 5, T_TOP - 2, TAG_D)
    for sx0, sx1 in (STOOL_L, STOOL_R):
        box(img, sx0, FL - 15, sx1, FL - 13, WOOD, z=18, top=1, cell=(6, 4))
        for lx in (sx0 + 1, sx1 - 2):
            c.rect(lx, FL - 12, lx + 1, FL - 1, col(*WOOD_D))
        c.line(sx0 + 2, FL - 6, sx1 - 2, FL - 6, col(*WOOD_D))
    # 吊灯（不亮：玻璃罩灰灰的）
    lx = (T_X0 + T_X1) // 2
    c.line(lx, CEIL, lx, FL - 76, STRING)
    c.rect(lx - 4, FL - 75, lx + 4, FL - 71, lc(0.36, 0.02, 215, lx, FL - 73, 20))
    c.line(lx - 5, FL - 71, lx + 5, FL - 71, lc(0.40, 0.02, 215, lx, FL - 71, 20))
    c.rect(lx - 1, FL - 76, lx + 1, FL - 76, col(*IRON))
    # 墙上的条子板（软木，钉满了条子、清单、照片、标签——她的「记性」挂在墙上）
    bx0, bx1, by0, by1 = T_X0 + 2, T_X1 - 4, FL - 66, FL - 38
    box(img, bx0, by0, bx1, by1, (0.30, 0.025, 60), z=3, top=1, seed=14, cell=(8, 8), gain=0.4)
    rng = np.random.default_rng(14)
    spots = [(2, 2, 10, 8, 3), (14, 3, 8, 11, 4), (24, 2, 9, 7, 2), (35, 4, 11, 9, 3), (48, 2, 9, 12, 4),
             (3, 13, 9, 10, 3), (26, 12, 10, 8, 3), (38, 15, 8, 10, 4), (49, 17, 9, 8, 2)]
    for sx, sy, w, h, ln in spots:
        if sx + w > bx1 - bx0 - 1:
            continue
        note(c, bx0 + sx, by0 + sy, w, h, lines=ln, paper=PAPER if rng.random() < 0.7 else col(0.48, 0.02, 80))
    # 一张照片（灰蓝，两个人影）、几枚小标签
    c.rect(bx0 + 14, by0 + 16, bx0 + 23, by0 + 24, col(0.42, 0.012, 230))
    c.rect(bx0 + 15, by0 + 17, bx0 + 22, by0 + 23, col(0.34, 0.016, 225))
    c.rect(bx0 + 17, by0 + 19, bx0 + 18, by0 + 23, col(0.26, 0.01, 240))
    c.rect(bx0 + 20, by0 + 20, bx0 + 21, by0 + 23, col(0.26, 0.01, 240))
    for k in range(6):
        tag(c, bx0 + 4 + k * 9, by1 - 3 if k % 2 else by0 - 1, 2, 2)


# ============================================================ 窗下：一排装收藏的矮箱子；晾衣绳和夹子（原文 120）
def under_window(img):
    c = cv(img)
    # 晾衣绳：从厨房那边一直拉到窗边，夹子夹着几张纸、一只袜子、一包干草
    lx0, lx1, ly = X(100), X(262), CEIL + 12
    for xx in range(lx0, lx1 + 1):
        t = (xx - lx0) / (lx1 - lx0)
        c.put(xx, int(ly + 6 * math.sin(math.pi * t)), STRING)
    c.put(lx0 - 1, ly, col(*IRON))
    c.put(lx1 + 1, ly, col(*IRON))

    def line_y(xx):
        return int(ly + 6 * math.sin(math.pi * (xx - lx0) / (lx1 - lx0)))
    for xx, kind in ((lx0 + 12, "paper"), (lx0 + 26, "sock"), (lx0 + 38, "paper"), (lx0 + 60, "herb"),
                     (lx0 + 86, "paper"), (lx0 + 102, "bag"), (lx0 + 128, "paper"), (lx0 + 144, "clip")):
        y = line_y(xx) + 1
        if kind == "paper":
            c.rect(xx, y, xx + 6, y + 7, lc(0.48, 0.015, 95, xx, y, 20))
            c.line(xx + 6, y, xx + 6, y + 7, lc(0.42, 0.015, 95, xx, y, 20))
            c.line(xx + 1, y + 3, xx + 4, y + 3, col(0.38, 0.015, 240))
        elif kind == "sock":
            c.rect(xx, y, xx + 2, y + 6, lc(*CLOTH_ROSE, xx, y, 20))
            c.rect(xx, y + 5, xx + 4, y + 6, lc(*CLOTH_ROSE, xx, y, 20))
        elif kind == "herb":
            for k in range(4):
                c.line(xx + k, y, xx + k - 1 + k % 2, y + 8 + k % 2, lc(0.34, 0.03, 120, xx, y, 20))
            c.rect(xx, y, xx + 3, y + 1, STRING)
        elif kind == "bag":
            c.rect(xx, y, xx + 5, y + 6, lc(0.38, 0.02, 80, xx, y, 20))
            tag(c, xx + 1, y + 2, 3, 2)
        c.put(xx + 1, y - 1, col(0.46, 0.012, 90))      # 夹子
        if kind != "clip":
            c.put(xx + (5 if kind in ("paper", "bag") else 2), y - 1, col(0.46, 0.012, 90))
        else:
            for k in range(4):
                c.put(xx + k * 2, y - 1, col(0.46, 0.012, 90))


# ============================================================ 柜子（门上一格一格的索引，原文 96）+ 柜顶摞到屋顶的盒子
CAB_X0, CAB_X1 = X(268), X(306)
CAB_TOP = FL - 92


def cabinet_shell(img):
    """柜体和柜顶（门在 obj_cabinet 里：关 / 开 / 影像盒被拖出来）。"""
    c = cv(img)
    box(img, CAB_X0, CAB_TOP, CAB_X1, FL - 1, WOOD_D, z=10, top=2, seed=30, cell=(10, 12))
    box(img, CAB_X0 - 2, CAB_TOP - 3, CAB_X1 + 2, CAB_TOP - 1, WOOD, z=12, top=1, cell=(10, 4))
    box(img, CAB_X0, FL - 6, CAB_X1, FL - 1, WOOD, z=12, top=1, cell=(10, 4))        # 柜脚的踢脚板
    # 柜顶的盒子，一直摞到天花板
    x = CAB_X0 - 1
    for w, h, hh in ((12, 10, 220), (14, 13, 65), (10, 8, 30)):
        box(img, x, CAB_TOP - 3 - h, x + w - 1, CAB_TOP - 4, (0.29, 0.02, hh), z=12, top=1, cell=(6, 6))
        tag(c, x + 2, CAB_TOP - 1 - h, 3, 2)
        x += w + 1
    box(img, CAB_X0 + 2, CAB_TOP - 24, CAB_X0 + 20, CAB_TOP - 17, (0.27, 0.02, 230), z=12, top=1, cell=(6, 6))
    tag(c, CAB_X0 + 5, CAB_TOP - 22, 4, 2)


# ============================================================ 播放器的木箱座 + 墙上的插座（原文 96）
P_X0, P_X1 = X(310), X(348)


def player_stand(img):
    c = cv(img)
    box(img, P_X0, FL - 14, P_X1, FL - 1, (0.27, 0.02, 65), z=10, top=1, seed=31, cell=(8, 8))
    darken(img, mrect(P_X0 + 1, FL - 8, P_X1 - 1, FL - 8), 1)
    tag(c, P_X0 + 4, FL - 12, 5, 3)
    # 插座在墙上，线垂下来
    sx, sy = P_X0 - 4, FL - 36
    c.rect(sx, sy, sx + 3, sy + 4, col(0.42, 0.01, 90))
    c.put(sx + 1, sy + 2, INK)
    c.put(sx + 2, sy + 2, INK)
    tag(c, sx - 3, sy, 2, 2)


# ============================================================ 床（原文 119「晚上我就没地方睡了」）+ 床上方一排收藏盒的架子
B_X0, B_X1 = WIN_RECT[0] - 10, WIN_RECT[2] + 6          # 床在窗下（靠窗的矮床）


def bed(img):
    """窗下一张矮床（原文 119「再捞一堆，晚上我就没地方睡了」）：床底下塞满了箱子，毯子是灰玫色，床头一摞叠好的衣服。"""
    c = cv(img)
    box(img, B_X0, FL - 14, B_X1, FL - 11, WOOD, z=14, top=1, cell=(10, 4))
    for lx in (B_X0, B_X1 - 2):
        c.rect(lx, FL - 10, lx + 2, FL - 1, col(*WOOD_D))
    box(img, B_X0, FL - 26, B_X0 + 3, FL - 11, WOOD, z=14, top=1, cell=(4, 8))            # 床头板（左）
    x = B_X0 + 3
    for k, (w, hh) in enumerate(((15, 220), (17, 65), (14, 30), (11, 200))):              # 床底下的箱子
        if x + w > B_X1 - 2:
            break
        box(img, x, FL - 9, x + w - 1, FL - 1, (0.24, 0.018, hh), z=12, top=1, cell=(6, 4))
        tag(c, x + 2, FL - 7, 3, 2)
        x += w + 1
    box(img, B_X0 + 4, FL - 18, B_X1 - 1, FL - 15, (0.38, 0.012, 230), z=16, top=1, cell=(8, 4))    # 褥子
    blank = Canvas(W, H)
    L, C, hh = CLOTH_ROSE
    for x in range(B_X0 + 16, B_X1 + 1):
        top = FL - 20 + (1 if (x // 9) % 2 else 0)
        for y in range(top, FL - 14):
            k = 1 if y == top else 0
            blank.put(x, y, lc(L + k * STEP, C, hh, x, y, 16))
    for y in range(FL - 19, FL - 11):                                                      # 毯子垂下来一角
        blank.put(B_X1 + 1, y, lc(L - STEP, C, hh, B_X1, y, 16))
    over_mask(img, blank.a)
    c.rect(B_X0 + 4, FL - 22, B_X0 + 14, FL - 18, lc(0.46, 0.012, 230, B_X0, FL - 20, 16))  # 枕头
    c.line(B_X0 + 4, FL - 22, B_X0 + 14, FL - 22, lc(0.50, 0.012, 230, B_X0, FL - 20, 16))
    for k, hh in enumerate((200, 90, 30)):                                                  # 床头叠好的衣服
        c.rect(B_X0 + 4, FL - 26 - k * 2, B_X0 + 12, FL - 25 - k * 2, lc(0.36, 0.025, hh, B_X0, FL - 25, 16))
    tag(c, B_X0 + 10, FL - 30, 3, 2)
    tag(c, B_X1 - 10, FL - 19, 3, 2)


# ============================================================ 右边一整面墙的收藏架（地上到天花板，每只盒子一个标签）
R_X0, R_X1 = X(351), X(379)


def right_shelves(img):
    c = cv(img)
    for lx in (R_X0, R_X1):
        box(img, lx, CEIL + 4, lx + 1, FL - 1, WOOD_D, z=8, top=0, cell=(4, 10))
    k = 0
    for sy in (FL - 2, FL - 24, FL - 46, FL - 68, FL - 90):
        shelf_board(img, R_X0, R_X1 + 1, sy, bracket=False)
        x = R_X0 + 2
        while x < R_X1 - 3:
            w = 6 + (k * 5) % 5
            h = 9 + (k * 7) % 9
            if sy - h < CEIL + 6:
                h = sy - CEIL - 6
            hh = (220, 65, 30, 200, 100, 240)[k % 6]
            x1 = min(x + w - 1, R_X1 - 1)
            box(img, x, sy - h, x1, sy - 1, (0.28 + 0.02 * (k % 3), 0.02, hh), z=10, top=1, cell=(5, 5), seed=40 + k)
            if x1 - x >= 3:
                tag(c, x + 1, sy - h + 2, min(3, x1 - x - 1), 2)
            x += w + 1
            k += 1
    # 墙上：一只挂钟（停了），在窗和柜子之间
    cx_, cy_ = WIN_RECT[2] + 9, FL - 108
    c.ellipse(cx_, cy_, 4, 4, col(0.40, 0.012, 90))
    c.ellipse(cx_, cy_, 3, 3, col(0.48, 0.012, 95))
    c.line(cx_, cy_, cx_, cy_ - 2, INK)
    c.line(cx_, cy_, cx_ + 2, cy_ + 1, INK)


# ============================================================ 地板上零碎的东西：一只篮子（标签纸卷和夹子）
def floor_things(img):
    c = cv(img)
    bx = R_X0 + 4
    c.rect(bx, FL - 8, bx + 8, FL - 1, col(0.32, 0.03, 75))
    for x in range(bx, bx + 9, 2):
        c.line(x, FL - 8, x, FL - 1, col(0.28, 0.03, 70))
    c.line(bx, FL - 8, bx + 8, FL - 8, col(0.38, 0.03, 80))
    c.rect(bx + 2, FL - 10, bx + 4, FL - 9, TAG)


FRONT_WIN = ((X(150), X(174)), (X(290), X(314)))


def front():
    img = np.zeros((H, W, 4), np.uint8)
    c = cv(img)
    x0, x1 = IX0 - WALL_T, IX1 + WALL_T - 1
    y0 = CEIL - WALL_T
    m = mrect(x0, y0, x1, FL - 1)
    shade(img, m, 0.30, 0.016, 232, z=0, gain=0.12, noise=N_WALL, noise_amp=0.45, cell=(30, 22), seed=50,
          lights=(Light(CX - 120, -80, 200, power=1.2, radius=400),))
    # 楼板那一道（外墙上一条压檐）
    box(img, x0, y0, x1, y0 + 3, (0.26, 0.012, 235), z=4, top=1, cell=(12, 4))
    # 旧水位的水渍：门槛以下泛青、发暗；几道一层层的线
    for k, yy in enumerate((FL - 42, FL - 30, FL - 18)):
        darken(img, mrect(x0, yy, x1, FL - 1), 0.35)
        for x in range(x0, x1 + 1):
            if (x * 13 + k * 7) % 17 > 2:
                darken(img, mrect(x, yy, x, yy), 0.8)
    tint(img, mrect(x0, FL - 12, x1, FL - 1), 165, 0.01)
    # 门（灰青漆，掉了几块；门上一张小标签）
    dx0, dx1, dtop = X(16), X(40), FL - 60
    box(img, dx0 - 3, dtop - 4, dx1 + 3, dtop - 1, STONE, z=4, top=1, cell=(8, 4))
    m = mrect(dx0, dtop, dx1, FL - 1)
    shade(img, m, 0.30, 0.022, 200, z=3, gain=0.15, cell=(8, 10), seed=51,
          lights=(Light(CX - 120, -80, 200, power=1.2, radius=400),))
    for xx in range(dx0 + 4, dx1, 6):
        darken(img, mrect(xx, dtop + 2, xx, FL - 2), 1)
    for (px, py, w, h) in ((dx0 + 3, dtop + 30, 4, 3), (dx0 + 15, dtop + 12, 3, 5), (dx0 + 9, dtop + 44, 5, 2)):
        c.rect(px, py, px + w - 1, py + h - 1, col(0.27, 0.01, 60))                     # 掉漆露出木头
    c.put(dx1 - 4, dtop + 32, col(0.44, 0.02, 80))                                       # 门把
    c.put(dx1 - 4, dtop + 33, col(0.36, 0.02, 75))
    tag(c, dx0 + 8, dtop + 18, 5, 3)
    # 门边现在的地址（原文 80）：一块小木牌，手写；图里 x≈65、离地约 30（会话 C 把水下的旧门牌画在它正下方）
    ax, ay = dx1 + 3, FL - 34
    c.rect(ax, ay, ax + 11, ay + 6, col(0.46, 0.02, 85))
    c.line(ax + 11, ay + 1, ax + 11, ay + 6, col(0.38, 0.02, 80))
    c.line(ax + 2, ay + 2, ax + 8, ay + 2, INK)
    c.line(ax + 2, ay + 4, ax + 6, ay + 4, INK)
    c.put(ax + 5, ay - 1, STRING)
    # 两扇前窗（暗玻璃，从外面看不进去），窗台花箱
    for wx0, wx1 in FRONT_WIN:
        wy0, wy1 = FL - 82, FL - 52
        box(img, wx0 - 3, wy0 - 3, wx1 + 3, wy1 + 3, (0.34, 0.016, 200), z=4, top=1, cell=(8, 8))
        m = mrect(wx0, wy0, wx1, wy1)
        shade(img, m, 0.24, 0.02, 220, z=2, gain=0.2, cell=(8, 8), seed=52,
              lights=(Light(wx0 - 30, wy0 - 60, 80, power=1.2, radius=120),))
        for k in range(3):                                                              # 玻璃上斜着的反光
            c.line(wx0 + 4 + k * 3, wy1 - 2, wx0 + 12 + k * 3, wy0 + 6, col(0.32 + 0.01 * k, 0.02, 215))
        c.rect((wx0 + wx1) // 2, wy0, (wx0 + wx1) // 2 + 1, wy1, col(0.30, 0.016, 205))
        c.line(wx0, wy0 + 12, wx1, wy0 + 12, col(0.30, 0.016, 205))
        box(img, wx0 - 4, wy1 + 4, wx1 + 4, wy1 + 9, WOOD, z=6, top=1, cell=(8, 4))
        for k in range(6):
            fx = wx0 - 2 + k * 5
            c.line(fx, wy1 + 3, fx + (k % 2), wy1 - 1, col(0.32, 0.03, 140))
            c.put(fx + (k % 2), wy1 - 2, col(0.40, 0.035, 20 + 40 * k))
        tag(c, wx1 - 4, wy1 + 6, 3, 2)
    # 落水管（右边）+ 几处裂缝和补过的灰泥
    px = X(392)
    box(img, px, y0 + 4, px + 3, FL - 1, IRON, z=8, top=0, cell=(4, 12))
    for yy in range(y0 + 16, FL, 24):
        c.rect(px - 1, yy, px + 4, yy + 1, col(0.26, 0.008, 240))
    for (sx, sy, ln) in ((X(100), FL - 90, 10), (X(222), FL - 70, 7), (X(350), FL - 96, 12)):
        for i in range(ln):
            c.put(sx + i // 2 + (i % 3 == 0), sy + i, col(0.22, 0.012, 240))
    for (sx, sy, w, h) in ((X(200), FL - 104, 18, 9), (X(70), FL - 74, 12, 7)):
        darken(img, mrect(sx, sy, sx + w, sy + h), -0.6)
    # 门边一只挂着的旧铁皮信箱
    mx = X(62)
    box(img, mx, FL - 56, mx + 8, FL - 46, (0.30, 0.02, 30), z=6, top=1, cell=(4, 4))
    c.line(mx + 2, FL - 53, mx + 6, FL - 53, col(0.20, 0.01, 30))
    tag(c, mx + 2, FL - 50, 3, 2)
    # 门上方一只壁灯架（不亮）、门边两只花盆、靠墙一根撑船的竹篙和一卷绳子
    lx = X(41)
    c.line(lx, FL - 70, lx + 4, FL - 70, col(*IRON))
    c.rect(lx + 3, FL - 69, lx + 6, FL - 64, col(0.34, 0.016, 215))
    c.put(lx + 4, FL - 71, col(*IRON))
    for k, (px, ph, hh) in enumerate(((X(46), 6, 30), (X(53), 5, 200))):
        c.rect(px, FL - ph, px + 5, FL - 1, col(0.30, 0.03, hh))
        c.line(px, FL - ph, px + 5, FL - ph, col(0.36, 0.03, hh))
        for j in range(4):
            c.line(px + 1 + j, FL - ph - 1, px + j - 1 + (j % 3), FL - ph - 5 - j % 2, col(0.32, 0.03, 140))
    for y in range(FL - 84, FL):
        x = X(92) + (y - (FL - 84)) // 20
        c.put(x, y, col(0.36, 0.025, 80))
    for r, Lr in ((5, 0.30), (4, 0.34), (2, 0.28)):
        c.ellipse(X(104), FL - 3, r + 1, 2, col(Lr, 0.025, 75))
    # 两扇前窗之间一根晾绳：一条毛巾、一张晾着的标签纸、两只夹子
    y = FL - 88
    x0_, x1_ = FRONT_WIN[0][1] + 12, FRONT_WIN[1][0] - 12
    for x in range(x0_, x1_ + 1):
        c.put(x, int(y + 4 * math.sin(math.pi * (x - x0_) / (x1_ - x0_))), STRING)
    cloth(c, x0_ + 18, y + 3, 9, 12, CLOTH_TEAL)
    cloth(c, x0_ + 44, y + 4, 5, 6, (0.50, 0.016, 95))
    cloth(c, x0_ + 66, y + 4, 7, 9, CLOTH_MUST)
    return img


# ============================================================ 窗里斜进来的冷光（半透明一层）
def light_layer():
    img = np.zeros((H, W, 4), np.uint8)
    x0, y0, x1, y1 = WIN_RECT
    # 窗光往左下斜（下午的太阳在窗外偏右上）：一个平行四边形落到地上，地上一块亮
    shift = 46
    for y in range(y0, FL):
        t = (y - y0) / (FL - y0)
        a0 = x0 - int(shift * t)
        a1 = x1 - int(shift * t) - 6
        alpha = int(22 * (1 - 0.6 * t))
        for x in range(max(IX0, a0), min(IX1, a1)):
            img[y, x] = (205, 220, 228, alpha)
    for y in range(FL - 3, FL):
        for x in range(max(IX0, x0 - shift - 6), x1 - shift):
            img[y, x] = (210, 224, 230, 34)
    return img


# ============================================================ 高处：门上的手画水道图、厨房上面一条高架、梁上搭的渔网、挂篮
def high_things(img):
    c = cv(img)
    # 手画的水道图（她认得常走的路，原文 83）：门上方钉着，几条弯弯的路线、几个小标签
    mx0, my0, mx1, my1 = X(14), FL - 108, X(42), FL - 88
    c.rect(mx0, my0, mx1, my1, PAPER)
    c.line(mx1, my0 + 1, mx1, my1, PAPER_D)
    c.line(mx0 + 1, my1, mx1, my1, PAPER_D)
    route = col(0.40, 0.03, 215)
    pts = [(mx0 + 2, my0 + 14), (mx0 + 8, my0 + 12), (mx0 + 12, my0 + 7), (mx0 + 19, my0 + 6), (mx0 + 26, my0 + 3)]
    c.polyline(pts, route)
    c.polyline([(mx0 + 12, my0 + 7), (mx0 + 15, my0 + 13), (mx0 + 24, my0 + 16)], route)
    c.line(mx0 + 3, my0 + 4, mx0 + 8, my0 + 4, INK)
    for px, py in ((mx0 + 8, my0 + 12), (mx0 + 19, my0 + 6), (mx0 + 24, my0 + 16)):
        c.put(px, py, col(0.46, 0.06, 40))
    for px, py in ((mx0 - 1, my0 - 1), (mx1, my0 - 1)):
        c.put(px, py, col(0.40, 0.04, 30))
    tag(c, mx1 + 2, my0 + 3, 3, 2)
    # 厨房上面一条高架：几只大盒子、一盏旧马灯（不亮）、卷起来的纸
    sy = FL - 102
    shelf_board(img, X(50), K_X1 + 2, sy)
    x = X(52)
    for w, h, hh in ((12, 8, 220), (9, 11, 65), (8, 9, 200)):
        box(img, x, sy - h, x + w - 1, sy - 1, (0.28, 0.02, hh), z=10, top=1, cell=(6, 5))
        tag(c, x + 2, sy - h + 2, 3, 2)
        x += w + 1
    lx = x + 3                                                                           # 马灯
    c.rect(lx, sy - 9, lx + 5, sy - 1, lc(0.30, 0.02, 215, lx, sy, 12))
    c.rect(lx + 1, sy - 8, lx + 4, sy - 3, lc(0.38, 0.02, 210, lx, sy, 12))
    c.line(lx + 1, sy - 11, lx + 4, sy - 11, col(*IRON))
    c.put(lx, sy - 10, col(*IRON))
    c.put(lx + 5, sy - 10, col(*IRON))
    x = lx + 9
    for k in range(4):                                                                   # 卷起来的纸，一捆
        c.rect(x, sy - 3 - k % 2 * 2, x + 12, sy - 2 - k % 2 * 2, lc(0.46 - 0.02 * k, 0.015, 95, x, sy, 12))
        c.put(x + 12, sy - 3 - k % 2 * 2, PAPER_D)
    tag(c, x + 4, sy - 6, 3, 2)
    # 梁上搭着一张渔网（河边人家），垂下来一截，网眼一格一格
    bx = IX0 + 136
    net = col(0.30, 0.02, 120)
    for y in range(CEIL + 6, CEIL + 22):
        span = 8 - abs(y - (CEIL + 14)) // 3
        for x in range(bx - span, bx + 8 + span):
            if (x + y) % 3 == 0 or (x - y) % 3 == 0:
                c.put(x, y, net)
    for k in range(3):
        c.put(bx - 2 + k * 6, CEIL + 22 + k % 2, col(0.40, 0.03, 40))                    # 浮子
    # 两只挂篮从第二根梁吊下来（装着洋葱、标签卷）
    for hx, hy in ((IX0 + 44, CEIL + 22), (IX0 + 316 + 6, CEIL + 4)):
        c.line(hx, CEIL + 6, hx, hy, STRING)
        c.rect(hx - 4, hy, hx + 4, hy + 5, lc(0.32, 0.03, 75, hx, hy, 18))
        for x in range(hx - 4, hx + 5, 2):
            c.put(x, hy + 2, lc(0.28, 0.03, 70, hx, hy, 18))
        c.rect(hx - 2, hy - 2, hx, hy - 1, lc(0.42, 0.03, 60, hx, hy, 18))
        tag(c, hx + 2, hy + 3, 2, 2)


# ============================================================ 会换状态的物件（每个一张多帧横排图）
def frame(w, h):
    return Canvas(w, h)


# ---- 桌面上的东西（obj_table）：每个状态一帧，帧里是那一刻桌上该有的东西
TB_X0, TB_Y1 = T_X0 - 4, T_TOP - 1     # 帧的左边、底边（底边 = 桌面上面那一行）
TB_W, TB_H = (T_X1 - T_X0) + 9, 16


def _bowl(c, x, y1, tea=False):
    """一只碗（侧面）：碗沿一道亮，里面的水 = 清的 / 茶色；上面两缕热气。"""
    rim = col(0.50, 0.012, 230)
    c.rect(x, y1 - 3, x + 6, y1 - 1, col(0.44, 0.012, 230))
    c.line(x + 1, y1, x + 5, y1, col(0.36, 0.012, 235))
    c.line(x, y1 - 3, x + 6, y1 - 3, rim)
    c.line(x + 1, y1 - 4, x + 5, y1 - 4, col(0.40, 0.03, 70) if tea else col(0.52, 0.02, 210))
    for k, sx in enumerate((x + 2, x + 4)):
        for i in range(3):
            if (i + k) % 2 == 0:
                c.put(sx + (i % 2), y1 - 6 - i * 2, col(0.46, 0.008, 230))


def _cup(c, x, y1, flipped=False):
    """借来的杯子（原文 77）：带把；倒扣时底朝上，底上一点小扳手记号。"""
    body = col(0.46, 0.02, 200)
    if not flipped:
        c.rect(x, y1 - 4, x + 3, y1, body)
        c.line(x + 3, y1 - 4, x + 3, y1, col(0.38, 0.02, 205))
        c.put(x + 4, y1 - 3, body)
        c.put(x + 5, y1 - 2, body)
        c.put(x + 4, y1 - 1, body)
        c.line(x, y1 - 5, x + 3, y1 - 5, col(0.54, 0.02, 200))
        c.put(x + 1, y1 - 2, TAG)
    else:
        c.rect(x, y1 - 4, x + 3, y1, body)
        c.line(x + 3, y1 - 4, x + 3, y1, col(0.38, 0.02, 205))
        c.line(x, y1 - 5, x + 3, y1 - 5, col(0.50, 0.02, 200))
        c.put(x + 1, y1 - 5, col(0.30, 0.02, 240))                     # 底上的小扳手（刻痕）
        c.put(x + 2, y1 - 6, col(0.30, 0.02, 240))
        c.put(x + 4, y1 - 2, body)


def _plate(c, x, y1, bread=1, crumbs=False):
    c.line(x, y1, x + 9, y1, col(0.46, 0.01, 225))
    c.line(x + 1, y1 - 1, x + 8, y1 - 1, col(0.42, 0.01, 225))
    if bread:
        for i in range(bread):
            bx = x + 1 + i * 4
            c.rect(bx, y1 - 3, bx + 3, y1 - 2, col(0.46, 0.04, 75))
            c.line(bx, y1 - 3, bx + 3, y1 - 3, col(0.38, 0.045, 60))     # 烤得最深的边（原文 85）
    if crumbs:
        for cx_ in (x + 2, x + 5, x + 7):
            c.put(cx_, y1 - 2, col(0.44, 0.04, 75))


def _paper_stack(c, x, y1, n=4, w=12, pale=False):
    for i in range(n):
        Lp = 0.48 - 0.02 * (i % 2) if not pale else 0.54
        c.line(x + (i % 2), y1 - i, x + w - 1 - (i % 3), y1 - i, col(Lp, 0.014, 92))
    c.line(x + 2, y1 - n, x + w - 4, y1 - n, col(0.40, 0.014, 92))


def _phone(c, x, y1):
    """晨的通讯器：深灰小盒、亮一格屏。"""
    c.rect(x, y1 - 1, x + 5, y1, col(0.26, 0.01, 240))
    c.line(x + 1, y1 - 1, x + 3, y1 - 1, col(0.46, 0.03, 200))


def _journal(c, x, y1):
    """晨的日记：锈红封面（和晨的斗篷同一个色相，压暗）。"""
    c.rect(x, y1 - 2, x + 11, y1, col(0.34, 0.06, 35))
    c.line(x, y1 - 2, x + 11, y1 - 2, col(0.40, 0.06, 38))
    c.line(x + 11, y1 - 2, x + 11, y1, col(0.30, 0.05, 30))
    c.put(x + 3, y1 - 1, col(0.50, 0.02, 90))


def _sleeves(c, x, n):
    """湿纸套一张一张摆开（原文 120）：灰白、颜色深一点的水印、每张之间空一格。"""
    for i in range(n):
        sx = x + i * 6
        c.line(sx, TB_H - 1, sx + 4, TB_H - 1, col(0.50, 0.012, 215))
        c.line(sx + 1, TB_H - 2, sx + 4, TB_H - 2, col(0.44, 0.014, 215))
        c.put(sx + 2, TB_H - 1, col(0.42, 0.016, 215))


def table_frames():
    """状态（剧本 river_home_table）→ 一帧。桌面上东西的 x 都相对桌面左边（T_X0），沙漏（24..33）和本子（47..58）是单独的物件，空着那两块。"""
    y = TB_H - 1
    o = T_X0 - TB_X0

    def f(*items):
        c = frame(TB_W, TB_H)
        for fn in items:
            fn(c)
        return c.a
    cup_l = lambda c: _cup(c, o + 1, y)                                  # noqa: E731
    bowls = lambda c: (_bowl(c, o + 7, y), _bowl(c, o + 34, y))          # noqa: E731
    plates = lambda c: (_plate(c, o + 14, y, 1), _plate(c, o + 38, y, 2))  # noqa: E731
    order = [
        ("default", f()),
        ("two_bowls_water", f(bowls, cup_l)),                                                   # 82：两碗清清的热水
        ("half_back", f(lambda c: _plate(c, o + 14, y, 1), lambda c: _plate(c, o + 38, y, 1, crumbs=True),
                        bowls, cup_l)),                                                         # 88：掰一半放回她的盘子
        ("cup_bottom", f(lambda c: _plate(c, o + 14, y, 0, crumbs=True), bowls,
                         lambda c: _cup(c, o + 42, y, flipped=True))),                          # 90：杯底的小扳手
        ("phone_corner", f(lambda c: _cup(c, o + 42, y, flipped=True), lambda c: _phone(c, o - 2, y))),   # 93：干燥的桌角
        ("old_pages", f(cup_l, lambda c: _paper_stack(c, o + 10, y, 5))),                      # 117：阿汀拿出的旧记录
        ("sleeves_drying", f(cup_l, lambda c: _paper_stack(c, o + 10, y, 5), lambda c: _sleeves(c, o + 32, 3),
                             lambda c: _sleeves(c, o - 3, 1))),                                 # 120：纸套一张张摆开
        ("phone_under_journal", f(cup_l, lambda c: _sleeves(c, o + 32, 3), lambda c: _phone(c, o + 8, y),
                                  lambda c: _journal(c, o + 6, y - 2))),                        # 122：通讯器压在本子下面
        ("phone_at_hand", f(cup_l, lambda c: _phone(c, o + 8, y), lambda c: _journal(c, o + 13, y))),     # 126：通讯器放在手边
        ("cup_stays", f(lambda c: _cup(c, o + 42, y))),                                         # 135：杯子留在桌上
        ("two_cups_tea", f(lambda c: _bowl(c, o + 7, y, tea=True), lambda c: _bowl(c, o + 34, y, tea=True),
                           lambda c: _cup(c, o + 1, y))),                                       # 152：两杯茶
    ]
    return [a for _, a in order], [n for n, _ in order]


# ---- 沙漏 + 桌上的轻铃（原文 83、87）
HG_X = T_X0 + 24
HG_W, HG_H = 10, 14


def hourglass_frames():
    """running 4 帧（100ms：中间一线沙往下漏，上面一格一格少）、full（没翻过来时）、empty；右边细铁丝挑着一只小铃。"""
    out = []

    def base(top_sand, bot_sand, stream):
        c = frame(HG_W, HG_H)
        wood = col(0.30, 0.018, 65)
        c.rect(0, 0, 6, 0, wood)
        c.rect(0, HG_H - 1, 6, HG_H - 1, wood)
        c.line(0, 1, 0, HG_H - 2, col(0.26, 0.018, 60))
        c.line(6, 1, 6, HG_H - 2, col(0.24, 0.018, 60))
        glass = col(0.40, 0.014, 215)
        for yy in range(1, HG_H - 1):                    # 玻璃：上下两个泡，中间细腰
            if abs(yy - (HG_H - 1) / 2) < 1.6:
                c.put(3, yy, glass)
            else:
                c.rect(1, yy, 5, yy, glass)
        sand = col(0.52, 0.035, 85)
        sand_d = col(0.46, 0.035, 80)
        for i in range(top_sand):                         # 上面的沙（从细腰往上堆）
            c.rect(2, 5 - i, 4, 5 - i, sand)
        for i in range(bot_sand):
            c.rect(2 if i < 2 else 1 + (i > 3), HG_H - 2 - i, 4 if i < 2 else 5 - (i > 3), HG_H - 2 - i, sand_d)
        if stream is not None:
            for yy in range(7, HG_H - 2 - bot_sand + 1):
                if (yy + stream) % 2 == 0:
                    c.put(3, yy, sand)
        # 小铃（铁丝 + 黄铜铃，压暗）
        c.line(7, HG_H - 1, 7, 3, col(*IRON))
        c.put(8, 3, col(*IRON))
        c.rect(8, 4, 9, 6, col(0.42, 0.05, 75))
        c.put(9, 6, col(0.36, 0.045, 70))
        return c.a
    states = {}
    out.append(base(4, 0, None))
    states["default"] = {"frames": [0]}
    run0 = len(out)
    for k in range(4):
        out.append(base(3 - (k // 2), 1 + (k // 2), k))
    states["running"] = {"frames": list(range(run0, run0 + 4)), "ms": 100, "loop": True}
    out.append(base(0, 4, None))
    states["empty"] = {"frames": [len(out) - 1]}
    return out, states


NOTEBOOK_PAGES = ["page1", "page1_circled", "tea_arrow", "circle_not_eaten", "crust_note", "plane_on_shore", "star",
                  "record_behind_photo"]


# ---- 妮芙的小本子（桌上那本，原文 81：翻得很软）：合着 / 摊开；8 页的字在特写里
NB_X = T_X0 + 47
NB_W, NB_H = 12, 5


def notebook_frames():
    a = frame(NB_W, NB_H)
    cover = col(0.36, 0.03, 200)
    a.rect(0, NB_H - 3, 9, NB_H - 1, cover)
    a.line(0, NB_H - 3, 9, NB_H - 3, col(0.42, 0.03, 200))
    a.line(1, NB_H - 2, 8, NB_H - 2, col(0.48, 0.014, 92))               # 翻软了的纸边从侧面看得见
    a.put(10, NB_H - 4, TAG)                                             # 夹着一张标签当书签
    a.put(10, NB_H - 5, TAG)
    b = frame(NB_W, NB_H)
    b.line(0, NB_H - 1, 11, NB_H - 1, cover)
    b.line(0, NB_H - 2, 5, NB_H - 2, col(0.52, 0.014, 92))
    b.line(6, NB_H - 2, 11, NB_H - 2, col(0.48, 0.014, 92))
    b.put(0, NB_H - 3, col(0.52, 0.014, 92))
    b.put(11, NB_H - 3, col(0.48, 0.014, 92))
    b.put(6, NB_H - 3, col(0.40, 0.014, 92))
    b.put(3, NB_H - 3, INK)
    states = {"default": {"frames": [0]}}
    for st in NOTEBOOK_PAGES:
        states[st] = {"frames": [1]}
    return [a.a, b.a], states


# ---- 来客册：桌上（翻开、杯子照片、粘住的页）→ 窗台上晾 → 晾干 → 合上 → 夹进晨的画
GB_X0 = T_X0 + 30
GB_X1 = WIN_RECT[2] + 8
GB_Y0 = WIN_RECT[3] - 8                 # 帧顶（窗台上的册子立起来晾）
GB_W, GB_H = GB_X1 - GB_X0 + 1, T_TOP - GB_Y0


def guestbook_frames():
    ledge_y = WIN_RECT[3] + 1 - GB_Y0 - 1        # 窗台面上一行（帧内）
    table_y = GB_H - 1                            # 桌面上一行（帧内）
    tx = 6                                         # 桌上册子的左边（帧内）
    wx = WIN_RECT[0] - GB_X0 + 10                  # 窗台上册子的左边（帧内）
    cov = col(0.32, 0.03, 30)                      # 封面：旧的灰红布面
    pg = col(0.50, 0.016, 92)

    def on_table(c, open_=True, photo=False, stuck=False, drawing=False):
        if open_:
            c.line(tx, table_y, tx + 21, table_y, cov)
            c.line(tx, table_y - 1, tx + 10, table_y - 1, pg)
            c.line(tx + 11, table_y - 1, tx + 21, table_y - 1, col(0.46, 0.016, 92))
            c.put(tx + 10, table_y - 2, col(0.42, 0.016, 92))
            c.put(tx + 3, table_y - 2, col(0.42, 0.05, 20))          # 夹着的干花
            c.put(tx + 4, table_y - 2, col(0.36, 0.03, 120))
            c.put(tx + 15, table_y - 2, col(0.44, 0.02, 60))         # 收据的一角
            if photo:
                c.rect(tx + 13, table_y - 2, tx + 18, table_y - 2, col(0.40, 0.012, 230))
            if stuck:
                c.rect(tx + 11, table_y - 3, tx + 19, table_y - 2, col(0.42, 0.02, 200))   # 泡过粘在一起的一沓
        else:
            c.rect(tx, table_y - 2, tx + 12, table_y, cov)
            c.line(tx, table_y - 2, tx + 12, table_y - 2, col(0.38, 0.03, 32))
            c.line(tx + 1, table_y - 1, tx + 11, table_y - 1, pg)
            c.put(tx + 13, table_y - 1, col(0.44, 0.02, 60))
            if drawing:                                               # 晨的画夹在里面，露出一角
                c.rect(tx + 3, table_y - 4, tx + 8, table_y - 3, col(0.54, 0.012, 95))
                c.put(tx + 4, table_y - 4, INK)
            tag(c, tx + 2, table_y - 2, 3, 1)

    def on_ledge(c, drying=True):
        # 立着半开，书页之间夹着薄片隔开（原文 91）
        c.line(wx, ledge_y, wx + 4, ledge_y - 7, cov)
        c.line(wx + 1, ledge_y, wx + 5, ledge_y - 7, cov)
        c.line(wx + 14, ledge_y, wx + 10, ledge_y - 7, cov)
        c.line(wx + 13, ledge_y, wx + 9, ledge_y - 7, cov)
        for k in range(4 if drying else 2):
            x0 = wx + 3 + k * 2
            c.line(x0, ledge_y, x0 + 1, ledge_y - 6, pg if k % 2 else col(0.46, 0.016, 92))
        if drying:
            for k in range(3):                                         # 薄片（灰白透明一点的）
                c.line(wx + 4 + k * 2, ledge_y - 1, wx + 4 + k * 2, ledge_y - 5, col(0.56, 0.01, 220))
            c.put(wx + 7, ledge_y + 1, col(0.40, 0.02, 215))           # 滴下来的一点水
        c.line(wx, ledge_y, wx + 14, ledge_y, col(0.30, 0.02, 30))

    order = [("default", []), ("open", [lambda c: on_table(c)]), ("photo_cup", [lambda c: on_table(c, photo=True)]),
             ("pages_stuck", [lambda c: on_table(c, photo=True, stuck=True)]), ("drying", [lambda c: on_ledge(c)]),
             ("dry", [lambda c: on_ledge(c, drying=False)]), ("closed", [lambda c: on_table(c, open_=False)]),
             ("drawing_in", [lambda c: on_table(c, open_=False, drawing=True)])]
    frames, states = [], {}
    for i, (st, fns) in enumerate(order):
        c = frame(GB_W, GB_H)
        for fn in fns:
            fn(c)
        frames.append(c.a)
        states[st] = {"frames": [i]}
    return frames, states


# ---- 晨坐的椅子：原来靠在柜子边上 → 妮芙搬到窗边通风的地方（原文 92）
CH_X0 = WIN_RECT[0] + 2
CH_X1 = CAB_X0 - 1
CH_W, CH_H = CH_X1 - CH_X0 + 1, 30


def chair_at(c, x):
    wood = col(0.30, 0.02, 68)
    wd = col(0.24, 0.018, 62)
    y1 = CH_H - 1
    c.rect(x, y1 - 14, x + 11, y1 - 13, wood)                    # 座
    c.line(x, y1 - 14, x + 11, y1 - 14, col(0.36, 0.02, 75))
    for lx in (x + 1, x + 9):
        c.rect(lx, y1 - 12, lx + 1, y1, wd)
    c.rect(x + 10, y1 - 29, x + 11, y1 - 15, wood)               # 靠背（朝右）
    for yy in (y1 - 28, y1 - 22):
        c.rect(x + 7, yy, x + 11, yy + 1, wood)
    c.line(x + 3, y1 - 5, x + 9, y1 - 5, wd)
    tag(c, x + 2, y1 - 12, 2, 2)


def chair_frames():
    a = frame(CH_W, CH_H)
    chair_at(a, CH_W - 13)                                       # 靠在柜子边
    b = frame(CH_W, CH_H)
    chair_at(b, 14)                                              # 窗边
    return [a.a, b.a], {"default": {"frames": [0]}, "by_window": {"frames": [1]}}


# ---- 柜门（门上贴一格一格的索引，原文 96）：关 / 开（长柄水壶、一排盒子）/ 影像盒被拖出来
CB_X0, CB_X1 = CAB_X0 - 6, CAB_X1 + 6
CB_Y0 = CAB_TOP + 2
CB_W, CB_H = CB_X1 - CB_X0 + 1, (FL - 7) - CB_Y0


def cabinet_frames():
    o = CAB_X0 - CB_X0
    iw = CAB_X1 - CAB_X0 + 1

    def doors_closed(c):
        for k in range(2):
            x0 = o + 1 + k * (iw // 2)
            x1 = o + (k + 1) * (iw // 2) - 1
            c.rect(x0, 1, x1, CB_H - 2, col(0.25, 0.016, 62))
            c.line(x0, 1, x1, 1, col(0.30, 0.016, 68))
            c.line(x1, 1, x1, CB_H - 2, col(0.21, 0.014, 60))
            for gi, gy in enumerate(range(6, CB_H - 10, 9)):      # 索引：一格一格的小纸条（灰白），隔几格一张琥珀标签
                for gj, gx in enumerate(range(x0 + 2, x1 - 4, 9)):
                    warm = (gi * 3 + gj * 5 + k) % 7 == 0
                    c.rect(gx, gy, gx + 6, gy + 3, TAG if warm else col(0.40, 0.014, 90))
                    c.put(gx + 6, gy + 3, TAG_D if warm else col(0.34, 0.014, 88))
                    c.line(gx + 1, gy + 1, gx + 4 - (gi + gj) % 2, gy + 1, col(0.28, 0.02, 250))
            c.put(x1 - 1 if k == 0 else x0 + 1, CB_H // 2, col(0.42, 0.02, 80))

    def inside(c, box_out=False):
        c.rect(o + 1, 1, o + iw - 2, CB_H - 2, col(0.15, 0.012, 240))
        for sy in (18, 38, 58, 78):
            if sy < CB_H - 2:
                c.line(o + 1, sy, o + iw - 2, sy, col(0.28, 0.016, 65))
        # 架子上一排盒子（每只标签），第二层一只长柄水壶（原文 95 她先拿错的那个）
        for sy, items in ((18, [(9, 12, 220), (8, 10, 65), (10, 13, 30), (9, 11, 200)]),
                          (58, [(10, 14, 65), (8, 12, 220), (11, 15, 30), (8, 10, 100)]),
                          (78, [(12, 12, 230), (10, 9, 65), (12, 11, 200)])):
            x = o + 2
            for w, h, hh in items:
                if sy - h < 2 or x + w > o + iw - 2:
                    continue
                c.rect(x, sy - h, x + w - 1, sy - 1, col(0.28, 0.02, hh))
                c.line(x, sy - h, x + w - 1, sy - h, col(0.33, 0.02, hh))
                c.rect(x + 2, sy - h + 2, x + 4, sy - h + 3, TAG)
                x += w + 1
        kx = o + 4
        c.rect(kx, 30, kx + 8, 37, col(0.34, 0.016, 205))          # 长柄水壶
        c.line(kx + 9, 33, kx + 24, 26, col(0.30, 0.016, 205))
        c.line(kx + 3, 29, kx + 5, 29, col(0.28, 0.01, 60))
        c.put(kx + 2, 32, TAG)
        # 金属影像盒：第二层右边，灰亮一点，盒盖上一张标签（原文 96「南桥，退水后，第七日」）
        bx = o + iw - 15
        if not box_out:
            c.rect(bx, 31, bx + 11, 37, col(0.40, 0.01, 230))
            c.line(bx, 31, bx + 11, 31, col(0.46, 0.01, 230))
            c.rect(bx + 3, 33, bx + 8, 35, TAG)
            c.line(bx + 4, 34, bx + 7, 34, INK)
        else:
            c.rect(bx, 36, bx + 11, 37, col(0.12, 0.01, 240))      # 拖走以后空出来的一格，灰印子
            c.line(bx, 37, bx + 11, 37, col(0.22, 0.012, 240))
        # 门开着：从正面看是两条窄边，贴在柜子两侧
        for x0 in (0, CB_W - 6):
            c.rect(x0, 0, x0 + 5, CB_H - 1, col(0.26, 0.016, 62))
            c.line(x0 + (5 if x0 == 0 else 0), 0, x0 + (5 if x0 == 0 else 0), CB_H - 1, col(0.21, 0.014, 60))
            for gy in range(6, CB_H - 10, 9):
                c.rect(x0 + 1, gy, x0 + 3, gy + 3, col(0.36, 0.014, 90))

    a = frame(CB_W, CB_H)
    doors_closed(a)
    b = frame(CB_W, CB_H)
    inside(b)
    d = frame(CB_W, CB_H)
    inside(d, box_out=True)
    return [a.a, b.a, d.a], {"default": {"frames": [0]}, "open": {"frames": [1]}, "footage_box": {"frames": [2]}}


# ---- 播放器（原文 96–100、123–131）：木箱座上一台旧显示器 + 下面的读带机，红灯；屏幕里的影像照原文
PL_X0 = P_X0 + 2
PL_SCR = (26, 20)                        # 屏幕（帧内 x 4..29, y 3..22）；右边一条是旋钮和喇叭
PL_W, PL_H = 36, 34
FOOT_W, FOOT_H = 112, 80                 # 影像特写的尺寸（同一套画法放大画；屏幕上是它缩小的）
FOOT_PAL = [(18, 24, 28), (34, 44, 50), (56, 68, 74), (82, 96, 102), (112, 126, 130), (146, 158, 160), (186, 196, 196)]


def _ell(shape, cx, cy, rx, ry):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1


def _thick(m, pts, w0, w1):
    """沿折线画一条由粗到细的带子（长鼻子、缆绳）。"""
    segs = list(zip(pts, pts[1:]))
    n = len(segs)
    for i, ((x0, y0), (x1, y1)) in enumerate(segs):
        for s_ in np.linspace(0, 1, 30):
            x, y = x0 + (x1 - x0) * s_, y0 + (y1 - y0) * s_
            w = w0 + (w1 - w0) * (i + s_) / n
            r = w / 2
            yy, xx = np.mgrid[int(y - r) - 1:int(y + r) + 2, int(x - r) - 1:int(x + r) + 2]
            ok = ((xx - x) ** 2 + (yy - y) ** 2 <= r * r) & (yy >= 0) & (yy < m.shape[0]) & (xx >= 0) & (xx < m.shape[1])
            m[yy[ok], xx[ok]] = True
    return m


F_WL = 58                                # 影像里的水面（高水位）
F_DECK = 40                              # 桥面顶


def footage(kind, t):
    """画影像的一帧（FOOT_W×FOOT_H，灰蓝单色 7 档 + 扫描线 + 颗粒），镜头在岸上、正侧面看一座半淹的桥：
    part1 0..7：雾里一团灰影从左边靠近桥，浮灯一盏盏抬高（像被托起来）；5–6 一截弯曲的长鼻搭到桥沿，7 滑下去（原文 97）
    glitch 0..3：白纹，声音断（原文 97）
    part2 0..7：雾短暂散开，灰影露出一只宽大的耳朵、边缘一道缺口；鼻子卷住垂在桥边的缆绳往旁边扯，浮灯整排移动（原文 124）
    tilt 0..3：镜头一歪，露出一截打着补丁的袖口（原文 124）；ear 0..3：耳朵甩，缺口跟着晃（原文 127）；paused：停住的一格。"""
    S = (FOOT_H, FOOT_W)
    idx = np.zeros(S, int)
    rng = np.random.default_rng(100 + t + (sum(map(ord, kind)) * 7) % 1000)
    clear = kind in ("part2", "tilt", "ear", "paused")
    yy, xx = np.mgrid[0:FOOT_H, 0:FOOT_W]
    # 天：雾，上亮下暗一档
    idx[:] = 5
    idx[yy > 20] = 4
    # 远处的楼（雾里两档灰）
    for bx, bw, bt in ((0, 14, 18), (16, 10, 24), (70, 16, 14), (90, 12, 22), (104, 8, 16)):
        idx[(xx >= bx) & (xx < bx + bw) & (yy >= bt) & (yy < F_WL)] = 3
    # 灰影（大象）：在桥的那一边，下半身被桥挡住、泡在水里
    near = clear
    if kind in ("part1", "glitch"):
        tt_ = t if kind == "part1" else 7
        hx, hy = 34 + tt_ * 3, 30
    else:
        hx, hy = 58, 24
    ear_sw = {"ear": [0, 2, 4, 2], "paused": [2]}.get(kind, [0] * 8)[t % (4 if kind == "ear" else 1 if kind == "paused" else 8)]
    el = np.zeros(S, bool)
    el |= _ell(S, hx - 22, hy + 12, 26, 14)                      # 背
    el |= _ell(S, hx, hy, 12, 11)                                # 头顶
    el |= _ell(S, hx + 8, hy + 6, 6, 8)                          # 脸，接鼻根
    ear = _ell(S, hx - 6 - ear_sw // 2, hy + 4, 9 + ear_sw, 14) & (xx <= hx + 1)
    if near:                                                      # 缺口：耳朵下后缘咬掉一块（原文 124）
        ear &= ~_ell(S, hx - 14 - ear_sw, hy + 13, 3, 4)
    # 鼻子
    if kind == "part1" and t in (5, 6):
        trunk = [(hx + 10, hy + 9), (hx + 15, hy + 3), (hx + 21, hy + 4), (hx + 24, F_DECK)]      # 搭到桥沿
    elif kind in ("part1", "glitch") and (t == 7 or kind == "glitch"):
        trunk = [(hx + 10, hy + 9), (hx + 13, hy + 15), (hx + 16, F_DECK + 6)]                    # 滑下去
    elif kind == "part2":
        pull = min(4, max(0, t - 3))
        trunk = [(hx + 10, hy + 9), (hx + 15, hy + 14), (hx + 20 + pull, F_DECK - 2), (hx + 23 + pull, F_DECK + 1)]
    else:
        trunk = [(hx + 10, hy + 9), (hx + 13, hy + 16), (hx + 12, F_DECK + 4)]
    tr = _thick(np.zeros(S, bool), trunk, 5, 3)
    shade_el = 1                                                 # 灰影比雾里的楼暗：一团深色
    idx[el] = shade_el
    idx[el & (yy < hy - 5)] = shade_el + 1                       # 头顶受天光
    idx[ear] = shade_el + 1
    if near:
        idx[ear & (xx >= hx - 9 - ear_sw)] = shade_el + 2        # 耳朵前半边亮一档、后半边一道褶
    if near:
        idx[hy - 1, hx + 5] = 0                                  # 眼
    # 桥：桥面 + 一排像栏杆的东西（其实是屋顶装饰）+ 两个半淹的桥洞
    idx[(yy >= F_DECK) & (yy < F_WL)] = 2
    idx[(yy == F_DECK)] = 3
    for k in range(10):
        x0 = 3 + k * 11
        idx[(xx >= x0) & (xx < x0 + 2) & (yy >= F_DECK - 4) & (yy < F_DECK)] = 2
        idx[F_DECK - 5, x0:x0 + 2] = 3
    for ax in (30, 82):                                          # 桥洞：水面上只露出上半个，最黑
        idx[_ell(S, ax, F_WL + 2, 14, 12) & (yy >= F_DECK + 4)] = 0
        idx[_ell(S, ax, F_WL + 2, 15, 13) & ~_ell(S, ax, F_WL + 2, 14, 12) & (yy >= F_DECK + 3)] = 3
    # 鼻子画在桥前面（搭在桥沿上）；part2 的缆绳垂在桥边
    if kind == "part2":
        pull = min(4, max(0, t - 3))
        cab = [(hx + 22 + pull, F_DECK - 6), (hx + 23 + pull * 2, F_DECK + 4), (hx + 22 + pull * 2, F_WL)]
        idx[_thick(np.zeros(S, bool), cab, 1.2, 1.2)] = 5
    idx[tr & (yy < F_WL)] = shade_el
    idx[tr & (yy < F_WL) & ~np.roll(tr, 1, 0)] = shade_el + 1      # 鼻子上沿一道亮
    # 灯柱
    idx[(xx == 100) & (yy >= F_DECK - 18) & (yy < F_DECK)] = 1
    idx[F_DECK - 19, 98:103] = 2
    # 水
    idx[yy >= F_WL] = 1
    idx[(yy >= F_WL) & ((xx * 5 + yy * 13) % 23 == 0)] = 2
    # 浮灯：part1 一盏盏抬高（像被什么托起来），part2 整排往鼻子扯的方向移
    for k in range(5):
        lx = 40 + k * 12
        ly = F_WL - 1
        if kind == "part1":
            ly -= min(6, max(0, t - k) * 2)
        elif kind == "glitch":
            ly -= min(6, max(0, 7 - k) * 2)
        elif kind == "part2":
            lx += max(0, t - 3) * 2
        elif kind in ("ear", "paused", "tilt"):
            lx += 8
        idx[ly, lx:lx + 2] = 6
        idx[ly + 1, lx] = 5
        for y in range(max(ly + 2, F_WL + 1), F_WL + 7, 2):
            idx[y, lx] = 4                                       # 灯在水里的倒影
    # 雾：远的时候整块往雾的那档靠
    fog = {"part1": 0.55 - 0.05 * t, "glitch": 0.2}.get(kind, 0.1)
    idx = np.round(idx * (1 - fog) + 4 * fog).astype(int)
    if kind == "tilt":                                           # 镜头一歪 + 打着补丁的袖口
        ang = math.radians([0, 3, 7, 10][t])
        sa, ca = math.sin(ang), math.cos(ang)
        sx = ((xx - 56) * ca + (yy - 40) * sa + 56).astype(int)
        sy = (-(xx - 56) * sa + (yy - 40) * ca + 40).astype(int)
        ok = (sx >= 0) & (sx < FOOT_W) & (sy >= 0) & (sy < FOOT_H)
        rot = np.zeros(S, int)
        rot[ok] = idx[sy[ok], sx[ok]]
        idx = rot
        if t >= 1:
            sw = 10 + t * 9
            sl = (yy > FOOT_H - sw) & (xx < (yy - (FOOT_H - sw)) * 1.4 + 8)
            idx[sl] = 2
            idx[sl & (xx > 3) & (xx < 14) & (yy > FOOT_H - sw + 4) & (yy < FOOT_H - sw + 12)] = 4   # 补丁
            idx[sl & ((xx == 3) | (xx == 14)) & (yy > FOOT_H - sw + 4) & (yy < FOOT_H - sw + 12) & (yy % 2 == 0)] = 5
    if kind == "glitch":                                         # 白纹
        for k in range(3 + t):
            gy = int(rng.integers(0, FOOT_H - 1))
            g0 = int(rng.integers(0, 50))
            idx[gy, g0:] = 6
            idx[gy + 1, g0 + int(rng.integers(0, 30)):] = 5
    a = np.zeros((FOOT_H, FOOT_W, 4), np.uint8)
    a[..., :3] = np.array(FOOT_PAL)[np.clip(idx, 0, 6)]
    a[..., 3] = 255
    a[::2, :, :3] = (a[::2, :, :3] * 0.88).astype(np.uint8)       # 扫描线
    for _ in range(50):                                          # 颗粒
        x, y = int(rng.integers(0, FOOT_W)), int(rng.integers(0, FOOT_H))
        a[y, x, :3] = np.minimum(255, a[y, x, :3].astype(int) + 22)
    if kind == "paused":
        for x0 in (FOOT_W - 12, FOOT_W - 8):
            a[4:11, x0:x0 + 2, :3] = FOOT_PAL[6]
    return a


def shrink_footage(a):
    """影像特写 → 屏幕（PL_SCR）：按块取最多的那档颜色（像素画缩小，不糊）。"""
    sw, sh = PL_SCR
    out = np.zeros((sh, sw, 4), np.uint8)
    for y in range(sh):
        for x in range(sw):
            blk = a[y * FOOT_H // sh:(y + 1) * FOOT_H // sh, x * FOOT_W // sw:(x + 1) * FOOT_W // sw, :3]
            v, n = np.unique(blk.reshape(-1, 3), axis=0, return_counts=True)
            # 亮的细东西（灯、缆绳）不要被平均掉：亮度最高的那档占了 1/8 以上就用它
            lum = v.sum(1)
            br = lum.argmax()
            pick = br if n[br] * 8 >= n.sum() and lum[br] > 400 else n.argmax()
            out[y, x, :3] = v[pick]
            out[y, x, 3] = 255
    return out


PLAYER_ORDER = [("default", "off", 1), ("footage_part1", "part1", 8), ("glitch", "glitch", 4), ("stopped", "black", 1),
                ("red_blink", "black", 4), ("footage_part2", "part2", 8), ("camera_tilt", "tilt", 4),
                ("paused", "paused", 1), ("ear_swing", "ear", 4)]


def player_frames():
    frames, states, closeups = [], {}, {}
    case = col(0.30, 0.012, 225)
    for st, kind, n in PLAYER_ORDER:
        idx = []
        cl = []
        for t in range(n):
            c = frame(PL_W, PL_H)
            # 显示器外壳（灰蓝铁皮）+ 底下读带机（深一档）+ 红灯 + 两个按钮
            c.rect(1, 0, PL_W - 2, 25, case)
            c.line(1, 0, PL_W - 2, 0, col(0.36, 0.012, 225))
            c.line(PL_W - 2, 1, PL_W - 2, 25, col(0.25, 0.012, 230))
            c.rect(0, 26, PL_W - 1, PL_H - 1, col(0.24, 0.012, 230))
            c.line(0, 26, PL_W - 1, 26, col(0.30, 0.012, 230))
            c.rect(4, 29, 17, 30, col(0.14, 0.01, 240))            # 插带口
            c.put(PL_W - 4, 6, col(0.40, 0.012, 225))              # 旋钮两只（老式显示器）
            c.put(PL_W - 4, 10, col(0.40, 0.012, 225))
            for yy in range(14, 23, 2):
                c.line(PL_W - 5, yy, PL_W - 3, yy, col(0.24, 0.012, 230))   # 喇叭孔
            led_on = (kind == "black" and st == "red_blink" and t < 2) or kind in ("part1", "part2", "tilt", "ear", "paused", "glitch")
            c.put(PL_W - 6, 29, col(0.42, 0.10, 28) if led_on else col(0.26, 0.02, 30))
            c.put(PL_W - 10, 29, col(0.36, 0.01, 230))
            c.put(PL_W - 13, 29, col(0.36, 0.01, 230))
            # 屏幕
            sx0, sy0 = 4, 3
            if kind == "off":
                c.rect(sx0, sy0, sx0 + PL_SCR[0] - 1, sy0 + PL_SCR[1] - 1, col(0.18, 0.012, 215))
                c.line(sx0 + 2, sy0 + 2, sx0 + 6, sy0 + 2, col(0.24, 0.012, 215))      # 玻璃上一道反光
            elif kind == "black":
                c.rect(sx0, sy0, sx0 + PL_SCR[0] - 1, sy0 + PL_SCR[1] - 1, col(0.12, 0.012, 230))
                for yy in range(sy0, sy0 + PL_SCR[1], 2):
                    c.line(sx0, yy, sx0 + PL_SCR[0] - 1, yy, col(0.14, 0.012, 230))
            else:
                big = footage(kind, t)
                cl.append(big)
                c.a[sy0:sy0 + PL_SCR[1], sx0:sx0 + PL_SCR[0]] = shrink_footage(big)
            # 影像盒插在上面（盒子放进来以后的状态都有）
            if kind != "off":
                c.rect(20, 28, 30, 31, col(0.40, 0.01, 230))
                c.rect(23, 29, 27, 30, TAG)
            idx.append(len(frames))
            frames.append(c.a)
        states[st] = {"frames": idx} if n == 1 else {"frames": idx, "ms": 100 if kind != "black" else 150, "loop": True}
        if cl:
            closeups[st] = cl
    return frames, states, closeups


# ---- 标签（原文 81）：剧本 river_home_labels on = 晨注意到「屋里每件东西几乎都有标签」。
#      home_back 里的标签一直在；这一层把每张标签提亮一档、纸边亮一点（叠在上面，on 以后一直显示）
def labels_frames():
    c = frame(W, H)
    for (x, y, w, h) in BACK_TAGS:
        c.rect(x, y, x + w - 1, y + h - 1, col(0.66, 0.045, 82))
        c.put(x + w - 1, y + h - 1, col(0.58, 0.04, 76))
    ys, xs = np.nonzero(c.a[..., 3])
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    crop = c.a[y0:y1 + 1, x0:x1 + 1]
    empty = np.zeros_like(crop)
    return [empty, crop], {"default": {"frames": [0]}, "on": {"frames": [1]}}, (int(x0), int(y0))


# ---- 旧家照片（原文 116：涨水前的收藏室、窗边一长排盒子、盒子之间她留出来的小过道）：桌上 / 压平四个角
PH_X = T_X0 + 36
PH_W, PH_H = 9, 3


def photo_frames():
    a = frame(PH_W, PH_H)
    a.line(0, PH_H - 1, 7, PH_H - 1, col(0.42, 0.012, 225))
    a.line(1, PH_H - 2, 6, PH_H - 2, col(0.46, 0.012, 225))
    a.put(0, PH_H - 2, col(0.42, 0.012, 225))
    a.put(7, PH_H - 3, col(0.42, 0.012, 225))                    # 角翘起来
    b = frame(PH_W, PH_H)
    b.line(0, PH_H - 1, 7, PH_H - 1, col(0.44, 0.012, 225))      # 压平：平平一条
    b.put(0, PH_H - 2, col(0.36, 0.01, 230))                     # 四个角压着的东西（小石子）
    b.put(7, PH_H - 2, col(0.36, 0.01, 230))
    return [frame(PH_W, PH_H).a, a.a, b.a], {"default": {"frames": [0]}, "on_table": {"frames": [1]}, "flattened": {"frames": [2]}}


# ============================================================ 背包图标（art/river_story/，和森林的 icon_* 同一套画法：逐像素手写）
ICON_PAL = {
    "k": (52, 46, 58),       # 最暗（带紫的灰，不是黑）
    "p": (226, 218, 200), "P": (200, 190, 170), "q": (170, 160, 142),                      # 纸
    "e": (96, 92, 110), "E": (70, 66, 84),                                                 # 墨 / 铅笔
    "y": (214, 168, 92), "Y": (236, 204, 140),                                             # 标签（琥珀）
    "m": (120, 124, 136), "M": (160, 164, 174), "n": (86, 88, 102), "t": (204, 214, 220),  # 金属
    "c": (140, 168, 186), "C": (96, 126, 150), "D": (66, 90, 112), "T": (214, 232, 236),   # 玻璃、水
    "o": (150, 90, 44), "O": (196, 128, 62), "u": (226, 170, 96),                          # 铜
    "b": (58, 42, 34), "B": (90, 63, 44), "w": (130, 92, 62), "L": (150, 112, 78),         # 木头
    "g": (148, 150, 140), "G": (186, 186, 174), "f": (112, 114, 108),                      # 晾干的浮木（灰白）
    "h": (104, 100, 112), "H": (140, 136, 146),                                            # 灰（照片里的灰影、橡胶）
    "s": (88, 112, 108), "S": (128, 152, 146),                                             # 灰青（气瓶）
    "r": (150, 70, 58),      # 红（圈、签名旁的记号）
    "v": (110, 150, 110),    # 饼干袋上的绿叶子 / 菜
    "l": (214, 186, 132), "j": (176, 140, 92),                                             # 饼干
}

ICONS = {
    # 南桥影像：金属影像盒，盒盖上贴着标签（原文 96「南桥，退水后，第七日」+ 她的字）
    "icon_footage": [
        ".MMMMMMMMMMMMM.",
        "MtttttttttttttM",
        "MmmmmmmmmmmmmmM",
        "nnnnnnnnnnnnnnn",
        "mmYYYYYYYYYYmmn",
        "mmYeeeeeeeeYmmn",
        "mmYYYYYYYYYYmmn",
        "mmYeeeeeYYYYmmn",
        "mmYYYYYYYYYYmmn",
        "mmmmmmmmmmmmmmn",
        "mmmmmmmmmmmmmmn",
        ".nnnnnnnnnnnnn.",
    ],
    # 铜铃（原文 143–144）：铃身铜色，挂绳，旁边一张标签（背面画了小飞机）
    "icon_bell": [
        ".....kk........",
        "....k..k.......",
        ".....oo........",
        "....oOOo.......",
        "...oOuOOo......",
        "...oOuOOo......",
        "..oOuOOOOo.....",
        "..oOuOOOOo.....",
        ".ooOOOOOOOo....",
        ".oooooooooo..e.",
        ".....oo.....e..",
        "....oooo...YYYy",
        "...........YeYy",
        "...........YYyy",
    ],
    # 一瓶河水（原文 147）：玻璃瓶、灰蓝的河水、标签「晨来过的那条河」
    "icon_river_water": [
        ".....kk.....",
        ".....bb.....",
        "....cTTc....",
        "....cTTc....",
        "...cTTTTc...",
        "..cTTTTTTc..",
        "..cCCCCCCc..",
        "..cCYYYYCc..",
        "..cCYeeYCc..",
        "..cCYYYYCc..",
        "..cCCCcCCc..",
        "..cDDDDDDc..",
        "...cccccc...",
    ],
    # 脚印拓片：薄纸，泥滩上的大脚印（圆的，前沿一排趾印），旁边比着画的小手和小脚
    "icon_rubbing": [
        "pppppppppppppP",
        "ppphhhhhhpppqP",
        "pphEEEEEEhppqP",
        "phEEhEEhEEhpqP",
        "phEEEEEEEEhpqP",
        "phEEEEEEEEhpqP",
        "phEEEEEEEEhpeP",
        "phEEEEEEEEhpeP",
        "pphEEEEEEhpeeP",
        "ppphhhhhhppeeP",
        "pppppppppppppP",
        "PPPPPPPPPPPPPq",
    ],
    # 杯底记号：一张纸，描下来的小扳手 + 抄的日期和船名
    "icon_tracing": [
        "ppppppppppppP",
        "ppeepppppppqP",
        "pepppppppppqP",
        "ppeeepppppppP",
        "pppppeeeepppP",
        "pppppppppeepP",
        "ppppppppppepP",
        "pppppppppppqP",
        "peeeeeppeeeqP",
        "pppppppppppqP",
        "peeepeeeeppqP",
        "PPPPPPPPPPPPq",
    ],
    # 货台旧照片：白边，灰的天，一团宽大的灰影站在货台边、耳朵缺一角；旁边一个小人拿着一长串食物
    "icon_dock_photo": [
        "pppppppppppppp",
        "pccccccccccccP",
        "pcchhhhcccccCP",
        "pchHHHhhhcccCP",
        "pchHhhhhhhcccP",
        "pcHhhhhhhhhccP",
        "pcchhhhhhhhkcP",
        "pcchhhhhhhhvkP",
        "pcchhcchhcvkcP",
        "pnnhhnnhhnvknP",
        "pnnnnnnnnnnnnP",
        "pppppppppppppP",
        "PPPPPPPPPPPPPq",
    ],
    # 不太甜的饼干：纸袋，口折下来，露出两块饼干，贴着标签
    "icon_biscuits": [
        "....ll.lj...",
        "...ljlljlj..",
        ".PPPPPPPPPP.",
        ".PqqqqqqqqP.",
        ".PppppppppP.",
        ".PpYYYYYppP.",
        ".PpYeeeYppP.",
        ".PpYYYYYppP.",
        ".PppppppppP.",
        ".PppppppppP.",
        ".PppppppppP.",
        ".qqqqqqqqqq.",
    ],
    # 读取头：小小的旧型号零件，金属头 + 两根线 + 一张小标签
    "icon_reading_head": [
        "....tMMMt.....",
        "...tMMMMMt....",
        "...MmmmmmM....",
        "...MmkkkmM....",
        "...MmmmmmM....",
        "...nmmmmmn....",
        "....nnnnn.....",
        ".....r.C......",
        ".....r..C.....",
        "....r....C....",
        "...r......CYY.",
        "...........Ye.",
    ],
    # 泄水门记录：几页记录，最后一行接连签着她的名字；下面一张手绘图，「开闸」被圈起来
    "icon_sluice_record": [
        "..pppppppppppP",
        "..peeeeepeeepP",
        "..pppppppppppP",
        "..peeeepeeeepP",
        "pppppppppppppP",
        "peeeeepeeeqP.P",
        "pppppppppppP.P",
        "pepeepepeeqP.P",
        "pprrrppppppP..",
        "prpeeprpppqP..",
        "pprrrppppppP..",
        "PPPPPPPPPPPq..",
    ],
    # 防水板：灰白的板，一个穿绳的孔，几行写好的事项，「跟着导绳走」下面划了一道
    "icon_board": [
        "..MMMMMMMMMM..",
        ".MttttkttttM..",
        ".MtttttttttMn.",
        ".MteeeeetttMn.",
        ".MtttttttttMn.",
        ".MteeeteeetMn.",
        ".MtttttttttMn.",
        ".MteeeeeeetMn.",
        ".MtrrrrrrttMn.",
        ".MtttttttttMn.",
        ".MteetttttTMn.",
        ".MMMMMMMMMMMn.",
        "..nnnnnnnnnn..",
    ],
    # 呼吸装置（借的）：灰青气瓶 + 面罩 + 一根管子，瓶上一张写着归还地点的标签
    "icon_breather": [
        "...kk.........",
        "..knnk........",
        "..SSSs........",
        ".SSSSss.......",
        ".SSSSss...hhh.",
        ".SSSSss..hHHHh",
        ".SYYYss..hcTch",
        ".SYeYss..hccch",
        ".SYYYss...hhh.",
        ".SSSSss....h..",
        ".SSSSss.hhh...",
        ".SSSSsshh.....",
        "..ssss........",
    ],
    # 管道接头：一截弯头，两头带螺纹
    "icon_pipe_joint": [
        "..MMMM........",
        ".MtttMn.......",
        ".MmmmMn.......",
        ".nnnnnn.......",
        ".MmmmMn.......",
        ".MmmmMn.......",
        ".MmmmMMMMMMMn.",
        ".MmmmmmmmmmMn.",
        ".MmmmmmmmmmMnM",
        "..nnnnnnnnnnnM",
        "............nM",
    ],
    # 浮筒密封圈：一只黑灰的橡胶圈，泡过水反而没裂
    "icon_float_seal": [
        "....hhhhh....",
        "..hHHHHHHhh..",
        ".hHhkkkkkhHh.",
        "hHhk.....khHh",
        "hHk.......kHh",
        "hhk.......khh",
        "hhhk.....khhh",
        ".hhhkkkkkhhh.",
        "..hhhhhhhhh..",
        "....hhhhh....",
    ],
    # 晾干的浮木：一捆灰白的木棍，用绳子扎着
    "mat_driftwood": [
        "..GGGGGGGGgg...",
        ".GgggggggggggG.",
        "fffffffffffff..",
        ".GGGGGGBGGGGGgg",
        "gggggggBggggggf",
        "..fffffBffffff.",
        ".GGGGGGBGGGgg..",
        "ggggggggggggggf",
        "..ffffffffff...",
    ],
    # 编号牌（南桥货台，原文 139；小游戏要放进背包就用这张）
    "icon_number_plate": [
        "MMMMMMMMMMMM",
        "MtttttttttMn",
        "MtkkttkkktMn",
        "MttkttttktMn",
        "MttktttkttMn",
        "MttkttkttkMn",
        "MtkkktkkktMn",
        "MtttttttttMn",
        "MnnnnnnnnnMn",
        ".nnnnnnnnnn.",
    ],
}


def icon(name):
    return Canvas.from_rows(ICONS[name], ICON_PAL).trim()


# ============================================================ 特写大图（art/river_story/closeup_*.png，原生 1:1，closeup_ui.gd 居中显示）
# 字用游戏里的像素字（fonts/PixelFont.ttf，11px，不抗锯齿）。有字的图出两份：中文 closeup_<名>.png、英文 closeup_<名>_en.png。
# 字的内容：原文 / 剧本里有的照原句（英文用 story_river.json 的 en）；原文没写、为了画面补的几行在 CLOSEUP_ADDED 里列出来。
from PIL import ImageDraw, ImageFont  # noqa: E402

FONT_PX = ImageFont.truetype(str(ROOT / "fonts" / "PixelFont.ttf"), 11)
C_PAPER = col(0.86, 0.022, 90)
C_PAPER_D = col(0.78, 0.024, 85)
C_PAPER_E = col(0.70, 0.026, 80)
C_RULE = col(0.80, 0.02, 230)
C_INK = col(0.34, 0.05, 255)           # 妮芙的笔：深灰蓝
C_RED = col(0.52, 0.11, 25)            # 红铅笔：圈、星星、划线
C_PENCIL = col(0.50, 0.012, 260)       # 晨的铅笔
CLOSEUP_ADDED = []                     # (图名, 行) 原文没写、补的字


def text_w(s):
    return int(FONT_PX.getlength(s))


def wrap(s, maxw, lang):
    if text_w(s) <= maxw:
        return [s]
    out, cur = [], ""
    toks = list(s) if lang == "zh" else s.split(" ")
    for t in toks:
        nxt = cur + t if lang == "zh" else (cur + " " + t if cur else t)
        if text_w(nxt) > maxw and cur:
            out.append(cur)
            cur = t
        else:
            cur = nxt
    if cur:
        out.append(cur)
    return out


def put_text(a, x, y, s, color=None, maxw=None, lang="zh", lh=13):
    """在 a（RGBA 数组）上写字（不抗锯齿），返回 [(x0, y0, x1, y1) 每行的框]。"""
    color = color or C_INK
    lines = wrap(s, maxw, lang) if maxw else [s]
    boxes = []
    for i, ln in enumerate(lines):
        im = Image.new("L", (text_w(ln) + 4, 16), 0)
        d = ImageDraw.Draw(im)
        d.fontmode = "1"
        d.text((0, 0), ln, font=FONT_PX, fill=255)
        m = np.array(im) > 127
        ys, xs = np.nonzero(m)
        if len(ys) == 0:
            continue
        yy = y + i * lh
        for py, px in zip(ys, xs):
            if 0 <= yy + py < a.shape[0] and 0 <= x + px < a.shape[1]:
                a[yy + py, x + px, :3] = color
                a[yy + py, x + px, 3] = 255
        boxes.append((x, yy + ys.min(), x + xs.max(), yy + ys.max()))
    return boxes


def paper(w, h, worn=True, rules=None, margin=None, seed=0):
    """一张纸：边上一圈暗一档（旧、翻软了），四个角圆一点，可选横格线、页边线。"""
    c = Canvas(w, h)
    c.rect(0, 0, w - 1, h - 1, C_PAPER)
    a = c.a
    rng = np.random.default_rng(seed)
    if worn:
        for x in range(w):
            for y in (0, h - 1):
                a[y, x, :3] = C_PAPER_D
        for y in range(h):
            for x in (0, w - 1):
                a[y, x, :3] = C_PAPER_D
        for (cx_, cy_) in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            a[cy_, cx_, 3] = 0
        for _ in range(w * h // 900):                         # 几块淡淡的旧渍
            sx, sy = int(rng.integers(4, w - 12)), int(rng.integers(4, h - 10))
            for yy in range(sy, sy + int(rng.integers(3, 7))):
                for xx in range(sx, sx + int(rng.integers(4, 10))):
                    a[yy, xx, :3] = C_PAPER_D
    if rules:
        y0, dy = rules
        for yy in range(y0, h - 4, dy):
            a[yy, 4:w - 4, :3] = C_RULE
    if margin:
        a[2:h - 2, margin, :3] = col(0.74, 0.05, 20)
    return c


def ring(a, box, color, pad=3, loops=1):
    """手画的圈：框外一圈椭圆，loops=2 圈两遍（第二圈错开一点）。"""
    x0, y0, x1, y1 = box
    for k in range(loops):
        cx_, cy_ = (x0 + x1) / 2 + k, (y0 + y1) / 2 + k * 0.5
        rx, ry = (x1 - x0) / 2 + pad + k, (y1 - y0) / 2 + pad - k * 0.5
        for t in np.linspace(0, 2 * math.pi * (1.06 if k == 0 else 0.97), 400):
            x = int(round(cx_ + rx * math.cos(t + k * 0.4)))
            y = int(round(cy_ + ry * math.sin(t + k * 0.4)))
            if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
                a[y, x, :3] = color
                a[y, x, 3] = 255


def strike(a, box, color):
    x0, y0, x1, y1 = box
    ym = (y0 + y1) // 2
    for x in range(x0 - 1, x1 + 2):
        a[ym + (1 if (x // 7) % 2 else 0), x, :3] = color


def underline(a, box, color, dy=2):
    x0, y0, x1, y1 = box
    a[y1 + dy, x0:x1 + 1, :3] = color


def star(a, cx_, cy_, r, color):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        t = -math.pi / 2 + i * math.pi / 5
        pts.append((cx_ + rr * math.cos(t), cy_ + rr * math.sin(t)))
    pts.append(pts[0])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        for s_ in np.linspace(0, 1, 12):
            a[int(round(y0 + (y1 - y0) * s_)), int(round(x0 + (x1 - x0) * s_)), :3] = color


def arrow(a, p0, p1, color):
    (x0, y0), (x1, y1) = p0, p1
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for s_ in np.linspace(0, 1, n * 2):
        a[int(round(y0 + (y1 - y0) * s_)), int(round(x0 + (x1 - x0) * s_)), :3] = color
    ang_ = math.atan2(y1 - y0, x1 - x0)
    for da in (0.5, -0.5):                                     # 箭头：往回斜两笔
        for k in range(1, 5):
            a[int(round(y1 - k * math.sin(ang_ + da))), int(round(x1 - k * math.cos(ang_ + da))), :3] = color


def save_story(name, a):
    STORY.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a).save(STORY / f"{name}.png")


def tr(zh, en):
    return {"zh": zh, "en": en}


# ---- 妮芙的本子：8 页（剧本 niff_notebook 的 8 个状态）。一页 200×150，左边订口，横格。
NB_PAGE = (200, 186)
L_P1 = tr("你叫妮芙。这是你的家。", "You are Niff. This is your home.")
L_P2 = tr("先看桌上的本子，再出门。", "Read the notebook on the table before you go out.")
L_P3 = tr("锅里有东西的时候，不要离开厨房。", "Don't leave the kitchen when something's on the stove.")
L_CHEN = tr("晨。", "Chen.")
L_PLANE = tr("飞机掉进河里，帮忙捞了杯子。", "Ship fell in the river. Helped fish out the cup.")
L_HUNGRY = tr("肚子还饿着。", "Still hungry.")
L_CRUST = tr("喜欢面包的脆边。", "Likes the crusty ends.")
L_SHORE = tr("飞机在岸上。", "Ship on shore.")


def notebook_page(state, lang):
    w, h = NB_PAGE
    c = paper(w, h, rules=(28, 14), seed=3)
    a = c.a
    for y in range(6, h - 6, 9):                               # 订口：一排小孔
        a[y, 6, :3] = C_PAPER_E
        a[y + 1, 6, :3] = C_PAPER_E
    a[2:h - 2, 11, :3] = col(0.76, 0.05, 20)
    X0, MW = 18, w - 28
    T = lambda d: d[lang]                                      # noqa: E731

    def write(y, d, color=None, x=X0):
        return put_text(a, x, y, T(d), color, maxw=w - x - 10, lang=lang, lh=14)
    if state in ("page1", "page1_circled"):
        y = 16
        b1 = write(y, L_P1)
        y = b1[-1][3] + 5
        b2 = write(y, L_P2)
        y = b2[-1][3] + 14
        b3 = write(y, L_P3)
        if state == "page1_circled":                           # 被圈了两遍（原文 81）
            x0 = min(b[0] for b in b3)
            x1 = max(b[2] for b in b3)
            ring(a, (x0, b3[0][1], x1, b3[-1][3]), C_RED, pad=4, loops=2)
    elif state == "tea_arrow":
        b0 = write(16, tr("泡茶", "Making tea"))
        underline(a, b0[0], C_INK)
        b1 = write(40, tr("1　烧水", "1  Boil water"))
        b2 = write(56, tr("2　放茶", "2  Add tea"))
        b3 = write(72, tr("3　倒进碗里", "3  Pour into bowls"))
        CLOSEUP_ADDED.append(("niff_notebook_tea_arrow", "3 倒进碗里 / 3 Pour into bowls"))
        # 她自己添的箭头：把「放茶」挪到更显眼的位置（原文 82）——在右边大大地再写一遍、框起来，箭头从原来那行指过去
        bx = put_text(a, 120 if lang == "zh" else 128, 28, T(tr("先放茶！", "TEA FIRST!")), C_RED)
        x0, y0, x1, y1 = bx[0]
        ring(a, (x0, y0, x1, y1), C_RED, pad=3)
        arrow(a, (b2[0][2] + 4, (b2[0][1] + b2[0][3]) // 2), (x0 - 4, y1 + 4), C_RED)
        CLOSEUP_ADDED.append(("niff_notebook_tea_arrow", "先放茶！/ TEA FIRST!（原文只写了「添了个箭头」）"))
    elif state in ("circle_not_eaten", "crust_note", "plane_on_shore", "star", "record_behind_photo"):
        y = 16
        bc = write(y, L_CHEN)
        bp = write(bc[-1][3] + 5, L_PLANE)
        bh = write(bp[-1][3] + 5, L_HUNGRY)
        ring(a, (bh[0][0], bh[0][1], bh[0][2], bh[0][3]), C_INK, pad=3)          # 「肚子还饿着」圈起来（原文 84）
        yb = bh[-1][3] + 10
        if state != "circle_not_eaten":
            # 顺手在旁边写了几个字（原文 85）→ 读到时是「喜欢面包的脆边」（原文 88）
            put_text(a, X0 + 66 if lang == "zh" else X0 + 70, bh[0][1] + 1, T(L_CRUST), C_INK, maxw=w - X0 - 80, lang=lang, lh=12)
        if state in ("plane_on_shore", "star", "record_behind_photo"):
            # 把「飞机在河里」划掉，改成「飞机在岸上」（原文 88）：划掉的那段在第二行开头，新的写在上面的空当
            seg = T(tr("飞机掉进河里", "Ship fell in the river"))
            x1 = bp[0][0] + text_w(seg)
            strike(a, (bp[0][0], bp[0][1], x1, bp[0][3]), C_INK)
            put_text(a, X0 + (40 if lang == "zh" else 46), bc[0][1], T(L_SHORE), C_INK)
        if state in ("star", "record_behind_photo"):
            # 修好声音以后记的步骤 + 晨问能不能写的那句，旁边一颗星星（原文 130–131）
            steps = [tr("影像：你帮我按着，我接线。", "Footage: you hold it, I connect the wire."),
                     tr("低鸣像从桌子底下传出来。", "The low call comes from under the table.")]
            y2 = yb + 4
            for st_ in steps:
                bb = write(y2, st_)
                y2 = bb[-1][3] + 5
            bs = write(y2 + 2, tr("我们都很高兴。", "We were both happy."))
            star(a, bs[-1][2] + 10, (bs[-1][1] + bs[-1][3]) // 2, 5, C_RED)
            yb = bs[-1][3] + 8
            CLOSEUP_ADDED.append(("niff_notebook_star", "影像那两行（原文 123、129 的话改写成她的记录）"))
        if state == "record_behind_photo":
            # 闸门记录夹在旧家照片后面，封面写了「不要替我收走」（原文 120）：本子右下贴一张标签
            l1, l2 = T(tr("闸门记录在照片后面", "Sluice log: behind photo")), T(tr("不要替我收走", "Don't put this away"))
            lw = max(text_w(l1), text_w(l2)) + 10
            tx, ty = w - lw - 6, max(yb, h - 36)
            for yy in range(ty, ty + 30):
                a[yy, tx:tx + lw, :3] = col(0.80, 0.07, 80)
            a[ty + 29, tx:tx + lw, :3] = col(0.70, 0.07, 75)
            put_text(a, tx + 4, ty + 2, l1, C_INK)
            put_text(a, tx + 4, ty + 16, l2, C_RED)
    return a


# ---- 来客册（原文 89–90、119、132）：摊开两页 300×170
GB_PAGE = (300, 190)


def _spread():
    w, h = GB_PAGE
    c = paper(w, h, seed=7)
    a = c.a
    a[2:h - 2, w // 2, :3] = C_PAPER_E                       # 中缝
    a[2:h - 2, w // 2 + 1, :3] = C_PAPER_D
    return a


def _receipt(a, x, y, w=36, h=52):
    a[y:y + h, x:x + w, :3] = col(0.92, 0.01, 95)
    for yy in range(y + 6, y + h - 6, 5):
        a[yy, x + 4:x + w - 6 - (yy * 7) % 9, :3] = col(0.62, 0.01, 250)
    for xx in range(x, x + w, 2):                              # 撕下来的锯齿边
        a[y + h - 1, xx, 3] = 0
    a[y + h - 10, x + 4:x + w - 4, :3] = col(0.45, 0.01, 250)


def _wrap_paper(a, x, y, w=44, h=34):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            k = ((xx // 4) + (yy // 4)) % 2
            a[yy, xx, :3] = col(0.70 if k else 0.64, 0.05, 200)
    a[y + h // 2, x:x + w, :3] = col(0.60, 0.08, 30)          # 一道丝带


def _flower(a, x, y):
    stem = col(0.50, 0.05, 130)
    for k in range(18):
        a[y + k, x + k // 6, :3] = stem
    for (dx, dy) in ((-2, -2), (0, -3), (2, -2), (-3, 0), (3, 0), (-1, 1), (1, 1), (0, -1)):
        a[y + dy, x + dx, :3] = col(0.66, 0.07, 10)
    a[y - 1, x, :3] = col(0.74, 0.06, 80)
    for (dx, dy) in ((2, 8), (3, 7), (-1, 11), (-2, 10)):
        a[y + dy, x + dx, :3] = stem


def _cup_photo(a, x, y):
    """旧照片：拿杯子的人背对镜头，外套袖口露出一块不太整齐的补丁（原文 89）。"""
    pw, ph = 70, 56
    a[y:y + ph, x:x + pw, :3] = col(0.94, 0.01, 95)
    ix0, iy0, ix1, iy1 = x + 4, y + 4, x + pw - 5, y + ph - 12
    for yy in range(iy0, iy1):
        for xx in range(ix0, ix1):
            a[yy, xx, :3] = col(0.62 - 0.08 * (yy - iy0) / (iy1 - iy0), 0.015, 230)
    for yy in range(iy0 + 24, iy1):                           # 桌面
        a[yy, ix0:ix1, :3] = col(0.48, 0.02, 70)
    body = col(0.36, 0.02, 220)
    for yy in range(iy0 + 8, iy1):                             # 背影
        half = 7 + (yy - iy0 - 8) // 3
        a[yy, x + 30 - half:x + 30 + half, :3] = body
    for yy in range(iy0 + 2, iy0 + 11):
        for xx in range(x + 25, x + 36):
            if (xx - x - 30.5) ** 2 / 30 + (yy - iy0 - 6.5) ** 2 / 20 < 1:
                a[yy, xx, :3] = col(0.30, 0.02, 60)            # 头发
    for yy in range(iy0 + 20, iy0 + 26):                       # 胳膊伸向右边，手里那只杯子
        a[yy, x + 38:x + 52, :3] = body
    a[iy0 + 21:iy0 + 25, x + 44:x + 48, :3] = col(0.56, 0.03, 80)   # 补丁（颜色不太一样、歪的）
    a[iy0 + 21, x + 44:x + 47, :3] = col(0.62, 0.03, 80)
    a[iy0 + 17:iy0 + 24, x + 52:x + 57, :3] = col(0.70, 0.03, 200)  # 杯子
    a[iy0 + 19:iy0 + 22, x + 57, :3] = col(0.70, 0.03, 200)
    put_text(a, x + 6, y + ph - 11, "· · ·", col(0.55, 0.01, 250))


def guestbook_page(state, lang):
    a = _spread()
    T = lambda d: d[lang]                                      # noqa: E731
    w, h = GB_PAGE
    R = w // 2 + 10
    if state in ("open", "photo_cup", "pages_stuck"):
        _receipt(a, 14, 14)
        _wrap_paper(a, 56, 20)
        _flower(a, 120, 30)
        for i, yy in enumerate(range(80, 150, 12)):           # 左页下面别人的几条记录（写得密，看不清）
            a[yy, 16:16 + 100 - (i * 17) % 40, :3] = col(0.58, 0.03, 250)
        if state == "open":
            for i, yy in enumerate(range(20, 150, 12)):
                a[yy, R:R + 110 - (i * 13) % 50, :3] = col(0.58, 0.03, 250)
        else:
            _cup_photo(a, R + 2, 10)
            y = 74
            for d in (tr("从森林来的客人。怕甜，会修东西。", "A guest from the forest. Doesn't like sweets. Can fix things."),
                      tr("说自己只住两天，后来住了很久。", "Said she'd only stay two days. Stayed a long time."),
                      tr("不要问她为什么不写回信。", "Don't ask her why she never wrote back."),
                      tr("问过了，她会把茶搅很久。", "Asked once. She stirred her tea for a long time.")):
                bb = put_text(a, R, y, T(d), C_INK, maxw=w - R - 8, lang=lang, lh=12)
                y = bb[-1][3] + 4
            if state == "pages_stuck":                         # 后面的纸被水泡过，粘在一起（原文 90）
                for yy in range(118, h - 4):
                    for xx in range(R - 6, w - 4):
                        wav = int(2 * math.sin((xx + yy) / 6.0))
                        a[yy, xx, :3] = col(0.74 - 0.02 * ((yy + wav) // 5 % 2), 0.03, 210)
                for yy in range(118, h - 4, 5):
                    a[yy, R - 6:w - 4, :3] = col(0.66, 0.03, 215)
                for (cx_, cy_, r) in ((R + 30, 140, 9), (R + 90, 150, 12)):
                    for yy in range(cy_ - r, cy_ + r):
                        for xx in range(cx_ - r * 2, cx_ + r * 2):
                            if ((xx - cx_) / (2 * r)) ** 2 + ((yy - cy_) / r) ** 2 < 1 and 0 <= yy < h:
                                a[yy, xx, :3] = col(0.66, 0.035, 215)
    elif state == "dry":
        # 晾干以后，最后几页（原文 132–133）
        y = 12
        for d in (tr("洪水以后，她留了一阵，", "After the flood she stayed a while,"),
                  tr("帮忙修泵、打捞东西。", "helped fix the pumps and fish things out."),
                  tr("后来跟着补给船，去了云层星。", "Then went to the Cloud Planet on a supply ship.")):
            bb = put_text(a, 12, y, T(d), C_INK, maxw=w // 2 - 20, lang=lang, lh=12)
            y = bb[-1][3] + 5
        y += 6
        put_text(a, 12, y, T(tr("出发：", "Left:")), C_INK)
        a[y + 9, 48:100, :3] = col(0.45, 0.04, 250)
        put_text(a, 12, y + 16, T(tr("船名：", "Ship:")), C_INK)
        a[y + 25, 48:110, :3] = col(0.45, 0.04, 250)
        CLOSEUP_ADDED.append(("guestbook_dry", "日期和船名只画成一道字迹（原文没写是哪天、哪条船）"))
        y = 12
        for d in (tr("走的那天，她把借来的杯子交给我，", "The day she left, she gave me the cup she'd borrowed,"),
                  tr("说先寄放，下一次来拿。", "said to keep it for her, she'd come back for it."),
                  tr("给弥洛的信，投进了北岸的旧邮箱。", "Her letter to Milo went in the old mailbox on the north bank.")):
            bb = put_text(a, R, y, T(d), C_INK, maxw=w - R - 8, lang=lang, lh=12)
            y = bb[-1][3] + 5
        _flower(a, w - 30, h - 40)
    return a


# ---- 防水板（原文 101、106、110）：灰白板，穿绳的孔，横线。字由引擎叠上去（lines 第一行 baseline 在 (16, 24)，行距 14）
def board():
    w, h = 220, 150
    c = Canvas(w, h)
    c.rect(0, 0, w - 1, h - 1, col(0.80, 0.012, 215))
    a = c.a
    a[0, :, :3] = col(0.88, 0.01, 215)
    a[:, 0, :3] = col(0.86, 0.01, 215)
    a[h - 1, :, :3] = col(0.66, 0.014, 220)
    a[:, w - 1, :3] = col(0.66, 0.014, 220)
    for cx_ in (w // 2 - 1, w // 2):
        a[4:8, cx_, :3] = col(0.40, 0.01, 240)                  # 穿绳的孔
    a[5:7, w // 2 - 2:w // 2 + 2, :3] = col(0.40, 0.01, 240)
    for yy in range(27, h - 6, 14):
        a[yy, 10:w - 10, :3] = col(0.72, 0.014, 215)
    for (sx, sy) in ((30, 90), (150, 40), (180, 120)):          # 几道划痕
        for k in range(10):
            a[sy + k // 3, sx + k, :3] = col(0.74, 0.012, 215)
    return a


# ---- 阿汀的图纸（原文 105）：只标了管道连接，没写哪只闸轮是哪只
def ting_plan():
    w, h = 260, 160
    c = paper(w, h, seed=11)
    a = c.a
    blue = col(0.50, 0.06, 245)
    for yy in range(8, h - 8, 10):                             # 方格纸
        a[yy, 8:w - 8, :3] = col(0.82, 0.02, 230)
    for xx in range(8, w - 8, 10):
        a[8:h - 8, xx, :3] = col(0.82, 0.02, 230)
    wheels = [(52, 110, 12), (110, 110, 9), (168, 110, 9)]     # 一大两小；只画了圈和辐条，没有名字
    yy_, xx_ = np.mgrid[0:h, 0:w]
    for (cx_, cy_, r) in wheels:
        ringm = ((xx_ - cx_) ** 2 + (yy_ - cy_) ** 2 <= r * r) & ((xx_ - cx_) ** 2 + (yy_ - cy_) ** 2 >= (r - 2) ** 2)
        a[ringm, :3] = blue
        for t in range(0, 360, 60):
            for k in range(r - 1):
                a[int(cy_ + k * math.sin(math.radians(t))), int(cx_ + k * math.cos(math.radians(t))), :3] = blue
    pipes = [[(52, 98), (52, 60), (210, 60), (210, 30)], [(110, 101), (110, 76), (232, 76), (232, 30)],
             [(168, 101), (168, 88), (196, 88), (196, 30)]]
    for pts in pipes:
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            for xx in range(min(x0, x1), max(x0, x1) + 1):
                for yy in range(min(y0, y1), max(y0, y1) + 1):
                    a[yy, xx, :3] = blue
                    a[yy, xx + 1 if x0 == x1 else xx, :3] = blue
    for x0 in (196, 210, 232):                                 # 墙上的出水口（三个小方框）
        a[22:30, x0 - 4:x0 + 6, :3] = blue
        a[23:29, x0 - 3:x0 + 5, :3] = C_PAPER
    a[140, 20:240, :3] = col(0.42, 0.03, 60)                    # 地面线
    for x0 in range(20, 240, 8):
        a[141:144, x0, :3] = col(0.42, 0.03, 60)
    return a


# ---- 设备柜（原文 112）：一排贴标签的抽屉。抽屉框照 story_river.json 里 river_warehouse 的 drawers.rect（会话 B 定的）
CAB_DRAWERS = [(20, 14, 120, 22), (20, 40, 120, 22), (20, 66, 120, 22), (20, 92, 120, 22), (20, 118, 120, 22)]
CAB_LABELS = [tr("渡船灯", "Ferry lamps"), tr("浮筒", "Floats"), tr("抽水泵", "Pumps"),
              tr("影像播放器　旧型号", "Players (old model)"), tr("收音机", "Radios")]


def warehouse_cabinet(lang, opened=False):
    w, h = 160, 150
    c = Canvas(w, h)
    c.rect(0, 0, w - 1, h - 1, col(0.36, 0.03, 200))          # 铁皮柜，水下：灰青
    a = c.a
    a[0, :, :3] = col(0.44, 0.03, 200)
    a[:, 0, :3] = col(0.42, 0.03, 200)
    a[:, w - 1, :3] = col(0.28, 0.03, 205)
    rng = np.random.default_rng(4)
    for _ in range(40):                                         # 锈点、水垢
        x, y = int(rng.integers(2, w - 3)), int(rng.integers(2, h - 3))
        a[y, x, :3] = col(0.42, 0.05, 60)
    for i, (x, y, dw, dh) in enumerate(CAB_DRAWERS):
        out_ = opened and i == 1
        a[y:y + dh, x:x + dw, :3] = col(0.30, 0.03, 205)
        a[y, x:x + dw, :3] = col(0.40, 0.03, 200)
        a[y + dh - 1, x:x + dw, :3] = col(0.24, 0.03, 210)
        if out_:                                                # 拉开过、空了（密封圈已经拿走）
            a[y + 2:y + dh - 2, x + 2:x + dw - 2, :3] = col(0.16, 0.02, 220)
            a[y + dh - 4:y + dh - 2, x + 2:x + dw - 2, :3] = col(0.26, 0.03, 210)
        lx, ly = x + 6, y + 5
        lbl = CAB_LABELS[i][lang]
        lw = text_w(lbl) + 8
        a[ly:ly + 13, lx:lx + lw, :3] = col(0.78, 0.05, 85)     # 圆圆的字写在标签纸上（贴歪一点）
        a[ly + 12, lx:lx + lw, :3] = col(0.66, 0.05, 80)
        put_text(a, lx + 4, ly + 1, lbl, C_INK)
        a[y + dh // 2 - 1:y + dh // 2 + 2, x + dw - 14:x + dw - 6, :3] = col(0.50, 0.02, 210)   # 拉手
    return a


# ---- 泄水门：操作记录（签名，原文 113–114）和下面压着的手绘图（原文 113）
def sluice_log(lang):
    w, h = 220, 150
    c = paper(w, h, rules=(24, 12), seed=21)
    a = c.a
    T = lambda d: d[lang]                                      # noqa: E731
    put_text(a, 10, 6, T(tr("泄水门　操作记录", "Sluice gate  log")), C_INK)
    for i, yy in enumerate(range(22, 82, 12)):                 # 前面别人的几行（看不清）
        a[yy + 8, 12:60, :3] = col(0.58, 0.02, 250)
        a[yy + 8, 80:150 - (i * 11) % 30, :3] = col(0.58, 0.02, 250)
    y = 94
    for k in range(4):                                         # 接连签着她的名字，几次的时间挨得很近（原文 114）
        a[y + k * 12 + 8, 12:52, :3] = col(0.50, 0.03, 250)
        put_text(a, 80, y + k * 12, T(tr("开　　妮芙", "Open   Niff")), C_INK)
    return a


def sluice_plan(lang):
    w, h = 240, 180
    c = paper(w, h, seed=22)
    a = c.a
    T = lambda d: d[lang]                                      # noqa: E731
    blue = col(0.48, 0.05, 240)
    # 手绘：上面一条窄渠停着渡船，中间仓库和泄水门，右边外河；箭头 = 开闸以后水往哪走
    a[30:44, 10:150, :3] = col(0.74, 0.04, 220)
    put_text(a, 14, 18, T(tr("窄渠", "Channel")), blue)
    for xx in range(60, 84):                                   # 渡船（小方块 + 几个人点）
        a[36:41, xx, :3] = col(0.40, 0.03, 60)
    for xx in (64, 70, 76):
        a[33:36, xx, :3] = col(0.30, 0.02, 250)
    a[60:110, 40:150, :3] = col(0.80, 0.02, 90)
    for xx in range(40, 151):
        a[60, xx, :3] = blue
        a[109, xx, :3] = blue
    a[60:110, 40, :3] = blue
    a[60:110, 150, :3] = blue
    put_text(a, 50, 64, T(tr("仓库", "Warehouse")), blue)
    a[78:96, 148:153, :3] = col(0.40, 0.03, 30)                # 泄水门
    a[70:120, 170:230, :3] = col(0.74, 0.04, 220)
    put_text(a, 178, 108, T(tr("外河", "River")), blue)
    arrow(a, (100, 46), (100, 70), blue)
    arrow(a, (154, 88), (184, 88), blue)
    bo = put_text(a, 156, 74, T(tr("开闸", "Open")), C_RED)
    ring(a, bo[0], C_RED, pad=3, loops=2)                      # 「开闸」被圈了起来
    bb = put_text(a, 10, 118, T(tr("再看一遍。阿汀已经确认，船上还有人。",
                                    "Read it again. Ting has confirmed there are still people on the boat.")), C_INK,
                  maxw=w - 20, lang=lang, lh=12)
    put_text(a, 10, bb[-1][3] + 4, T(tr("箱子拿不完。不要为了回来拿箱子，再把闸关上。",
                                         "We can't take all the crates. Don't come back for them and close the gate again.")),
             C_INK, maxw=w - 20, lang=lang, lh=12)
    return a


# ---- 货台：旧装卸记录（原文 139；三行照剧本的编号牌）和照片正反面
def dock_records(lang):
    w, h = 220, 130
    c = paper(w, h, rules=(30, 14), seed=31)
    a = c.a
    T = lambda d: d[lang]                                      # noqa: E731
    put_text(a, 10, 8, T(tr("装卸记录", "Loading log")), C_INK)
    rows = [tr("07　补给船　去往东岸", "07  Supply ship  To the east bank"),
            tr("12　运输船　去往云层星", "12  Transport ship  To the Cloud Planet"),
            tr("21　渡船　去往下游船坞", "21  Ferry  To the downstream boatyard")]
    y = 34
    for i, d in enumerate(rows):
        a[y + 18, 12:40, :3] = col(0.60, 0.02, 250)
        put_text(a, 12, y, T(d), C_INK)
        y += 28
    for yy in range(40, 120, 7):                                # 水渍
        a[yy, 180:210, :3] = C_PAPER_D
    return a


def dock_photo(back=False, lang="zh"):
    w, h = 180, 130
    c = Canvas(w, h)
    c.rect(0, 0, w - 1, h - 1, col(0.92, 0.012, 95))
    a = c.a
    if back:
        T = lambda d: d[lang]                                  # noqa: E731
        put_text(a, 16, 40, T(tr("目的地：云层星", "To: the Cloud Planet")), C_INK)
        put_text(a, 16, 62, T(tr("船号：12", "Ship no. 12")), C_INK)
        for yy in range(90, 120, 6):
            a[yy, 16:120 - (yy * 3) % 30, :3] = col(0.70, 0.01, 250)
        CLOSEUP_ADDED.append(("dock_photo_back", "船号写 12（和剧本里编号牌 12「运输船　去往云层星」对上）"))
        return a
    x0, y0, x1, y1 = 8, 8, w - 9, h - 22
    yy, xx = np.mgrid[0:h, 0:w]
    inner = (xx >= x0) & (xx <= x1) & (yy >= y0) & (yy <= y1)
    a[inner, :3] = col(0.66, 0.012, 230)
    a[inner & (yy > 80), :3] = col(0.46, 0.015, 225)          # 货台
    for k in range(5):                                          # 坡板
        a[(yy == 80 - k * 3 - (xx - 120) // 3) & (xx > 120) & (xx < 150) & inner, :3] = col(0.38, 0.02, 60)
    ramp = (yy < 82) & (yy > 80 - (xx - 120) * 0.45) & (xx > 118) & (xx < 152) & (yy > 60)
    a[ramp & inner, :3] = col(0.44, 0.03, 60)
    # 一团宽大的灰影：背、头、宽大的耳朵（左耳缺一角，原文 139）、往坡板伸的鼻子
    ell = lambda cx_, cy_, rx, ry: ((xx - cx_) / rx) ** 2 + ((yy - cy_) / ry) ** 2 <= 1   # noqa: E731
    body = ell(70, 62, 40, 22) | ell(108, 50, 13, 13) | ell(116, 58, 7, 9)
    body &= yy < 84
    a[body, :3] = col(0.34, 0.012, 240)
    a[body & (yy < 44), :3] = col(0.40, 0.012, 240)
    ear = ell(98, 56, 10, 14) & (xx <= 108)
    ear &= ~ell(88, 66, 3, 4)                                  # 缺的那一角
    a[ear, :3] = col(0.42, 0.012, 235)
    for k in range(16):                                         # 鼻子垂下来往前卷
        x = 120 + int(k * 0.6)
        y = 62 + k
        a[y:y + 3, x:x + 3, :3] = col(0.34, 0.012, 240)
    a[48, 112, :3] = col(0.18, 0.01, 250)
    for (lx, ly) in ((48, 84), (62, 84), (84, 84), (96, 84)):  # 腿
        a[ly - 2:ly + 4, lx:lx + 6, :3] = col(0.30, 0.012, 240)
    # 旁边的人用一长串食物引它上坡板
    a[54:84, 158:163, :3] = col(0.26, 0.012, 240)
    a[48:54, 157:164, :3] = col(0.28, 0.012, 60)
    for k in range(10):
        a[66 + (k % 2), 156 - k * 3:158 - k * 3, :3] = col(0.48, 0.04, 100 - k * 6)
    rng = np.random.default_rng(9)
    for _ in range(120):                                        # 旧照片的颗粒
        x, y = int(rng.integers(x0, x1)), int(rng.integers(y0, y1))
        a[y, x, :3] = np.minimum(255, a[y, x, :3].astype(int) + 18)
    return a


# ---- 旧家照片（原文 116）：涨水前的收藏室，窗边一长排盒子，盒子之间她留出来的小过道
def niff_photo():
    w, h = 180, 130
    c = Canvas(w, h)
    c.rect(0, 0, w - 1, h - 1, col(0.92, 0.012, 95))
    a = c.a
    x0, y0, x1, y1 = 8, 8, w - 9, h - 22
    a[y0:y1, x0:x1, :3] = col(0.56, 0.014, 230)
    a[y0 + 70:y1, x0:x1, :3] = col(0.48, 0.02, 70)             # 地板
    a[y0 + 10:y0 + 50, x0 + 50:x0 + 110, :3] = col(0.78, 0.015, 220)   # 窗
    a[y0 + 10:y0 + 50, x0 + 79:x0 + 81, :3] = col(0.40, 0.015, 220)
    a[y0 + 28:y0 + 30, x0 + 50:x0 + 110, :3] = col(0.40, 0.015, 220)
    x = x0 + 6
    k = 0
    while x < x1 - 10:                                         # 一长排盒子，每隔几只空一条小过道
        bw = 12 + (k * 5) % 7
        bh = 18 + (k * 7) % 14
        a[y0 + 72 - bh:y0 + 72, x:x + bw, :3] = col(0.42 + 0.03 * (k % 3), 0.02, (220, 65, 30)[k % 3])
        a[y0 + 72 - bh, x:x + bw, :3] = col(0.50, 0.02, 90)
        a[y0 + 76 - bh:y0 + 78 - bh, x + 3:x + 7, :3] = col(0.80, 0.03, 85)
        x += bw + (7 if k % 3 == 2 else 1)
        k += 1
    for (gx, gy) in ((x0 + 64, y0 + 60), (x0 + 67, y0 + 61)):  # 小盒子里的玻璃珠（绿色那颗最圆，原文 118）
        a[gy, gx, :3] = col(0.66, 0.06, 150)
    a[h - 14, 12:70, :3] = col(0.72, 0.01, 250)
    return a


# ---- 晨画给她的画（原文 146、149）：屋子、飞机、小船、桌上两碗热水，岸桩旁的阿汀和围裙补丁；签名旁一只小象（鼻子添了一笔）
def chen_drawing():
    w, h = 200, 140
    c = paper(w, h, seed=41)
    a = c.a
    pen = C_PENCIL

    def line(p0, p1):
        (x0, y0), (x1, y1) = p0, p1
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for s_ in np.linspace(0, 1, n * 2):
            a[int(round(y0 + (y1 - y0) * s_)), int(round(x0 + (x1 - x0) * s_)), :3] = pen

    def poly(pts):
        for p0, p1 in zip(pts, pts[1:]):
            line(p0, p1)
    poly([(20, 80), (20, 44), (50, 26), (80, 44), (80, 80)])    # 屋子
    poly([(16, 46), (50, 22), (84, 46)])
    poly([(30, 80), (30, 62), (40, 62), (40, 80)])
    poly([(56, 56), (70, 56), (70, 66), (56, 66), (56, 56)])
    poly([(52, 76), (74, 76)])                                  # 桌上两碗热水
    for bx in (55, 66):
        poly([(bx, 74), (bx + 5, 74), (bx + 4, 76), (bx + 1, 76)])
        line((bx + 2, 72), (bx + 2, 70))
    poly([(8, 82), (192, 82)])                                  # 岸
    for x in range(10, 190, 12):
        line((x, 90), (x + 6, 90))                              # 水
    poly([(96, 74), (140, 74), (146, 66), (134, 62), (104, 62), (96, 74)])   # 飞机（机翼歪的）
    poly([(110, 62), (106, 54), (128, 58)])
    poly([(150, 92), (176, 92), (180, 86), (146, 86), (150, 92)])            # 小船
    line((163, 86), (163, 78))
    for y in range(52, 82):                                     # 岸桩
        a[y, 184, :3] = pen
    a[50, 183:186, :3] = pen
    poly([(172, 82), (172, 66), (176, 60), (180, 66), (180, 82)])            # 阿汀（画得年轻了一点）
    a[56:60, 175:178, :3] = pen
    poly([(173, 68), (179, 68), (179, 80), (173, 80)])          # 围裙
    a[73:76, 175:178, :3] = col(0.56, 0.02, 80)                 # 补丁（妮芙提醒才添上的）
    put_text(a, 24, 108, "晨", pen)                             # 签名（写大一点）
    poly([(52, 118), (52, 108), (60, 104), (70, 106), (72, 114), (66, 118)])  # 小象
    poly([(70, 110), (76, 116), (78, 122)])                     # 鼻子（又添了一笔，像水壶）
    line((78, 122), (82, 124))
    return a


def build_closeups():
    CLOSEUP_ADDED.clear()
    for lang in ("zh", "en"):
        sfx_ = "" if lang == "zh" else "_en"
        for st in NOTEBOOK_PAGES:
            save_story(f"closeup_niff_notebook_{st}{sfx_}", notebook_page(st, lang))
        for st in ("open", "photo_cup", "pages_stuck", "dry"):
            save_story(f"closeup_guestbook_{st}{sfx_}", guestbook_page(st, lang))
        save_story(f"closeup_warehouse_cabinet{sfx_}", warehouse_cabinet(lang))
        save_story(f"closeup_warehouse_cabinet_open{sfx_}", warehouse_cabinet(lang, opened=True))
        save_story(f"closeup_sluice_log{sfx_}", sluice_log(lang))
        save_story(f"closeup_sluice_plan{sfx_}", sluice_plan(lang))
        save_story(f"closeup_dock_records{sfx_}", dock_records(lang))
        save_story(f"closeup_dock_photo_back{sfx_}", dock_photo(True, lang))
    save_story("closeup_board", board())
    save_story("closeup_ting_plan", ting_plan())
    save_story("closeup_dock_photo", dock_photo())
    save_story("closeup_dock_photo_front", dock_photo())
    save_story("closeup_niff_photo", niff_photo())
    save_story("closeup_chen_drawing", chen_drawing())
    save_story("closeup_chen_drawing_done", chen_drawing())
    seen = []
    for k in CLOSEUP_ADDED:
        if k not in seen:
            seen.append(k)
    (STORY / "closeup_added.txt").write_text(
        "特写图里原文没写、为了画面补的字（tools/river_home_art.py 生成）：\n" +
        "\n".join(f"- {a}：{b}" for a, b in seen) + "\n", encoding="utf-8")


# ============================================================ 拼起来
def build_back():
    img = shell()
    window(img)
    door_side(img)
    kitchen(img)
    table(img)
    under_window(img)
    cabinet_shell(img)
    player_stand(img)
    bed(img)
    right_shelves(img)
    floor_things(img)
    high_things(img)
    return img


def save(name, a):
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a).save(OUT / f"{name}.png")
    return a


BACK_TAGS: list = []
STORY = ROOT / "art" / "river_story"


def build():
    for old in ["home_under.png", "home.json"] + [p.name for p in OUT.glob("obj_*.json")] + \
               [p.name for p in OUT.glob("closeup_footage_*")]:
        (OUT / old).unlink(missing_ok=True)                     # 第一版的文件（旧一层归会话 C 画；json 照约定改成 room.json）
    TAGS.clear()
    save("home_back", limit_colors(build_back(), 256))      # Oscar 的房间 34~287 色（风格检查器）；PIL 最多 256
    BACK_TAGS[:] = TAGS
    save("home_front", front())
    save("home_light", light_layer())
    meta = {
        "_comment": "妮芙家（剖面小屋）。格式照 docs/river_rooms_contract.md 1.6：坐标都是图里的像素（左上角 0,0）。"
                    "tools/river_home_art.py 生成，别手改。地板下面泡在水里的旧一层（旧门、旧门牌）是会话 C 画在河岸栈道下面的。",
        "kind": "house",
        "host": "river_bank",
        "x": 890,
        "size": [W, H],
        "back": "home_back.png",
        "front": "home_front.png",
        "light": "home_light.png",
        "floor": FL - 1,
        "walk": [IX0 + 6, IX1 - 8],
        "door": X(28),
        "markers": {
            "river_home_door": X(28),
            "river_home_kitchen": K_X0 + 30,
            "river_home_jar": SALT_X,
            "river_home_labels": K_X0 + 44,
            "river_home_chen": T_X0 + 4,
            "river_home_table": T_X0 + 18,
            "river_home_hourglass": T_X0 + 28,
            "river_home_niff": T_X1 - 4,
            "river_home_window": WIN_C[0],
            "river_home_chair": CH_X0 + 20,
            "river_home_cabinet": (CAB_X0 + CAB_X1) // 2,
            "river_home_player": P_X0 + 4,
        },
        "objects": {},
    }
    build_objects(meta)
    STORY.mkdir(parents=True, exist_ok=True)
    for name in ICONS:
        icon(name).save(STORY / f"{name}.png")
    build_closeups()
    return meta


def _states(st):
    """{状态: {"frames": [...]}} → 约定的写法：一帧写帧号，多帧（连着的）写 [起, 止] 循环播。"""
    out = {}
    for k, d in st.items():
        fr = d["frames"]
        out[k] = fr[0] if len(fr) == 1 else [fr[0], fr[-1]]
        assert len(fr) == 1 or fr == list(range(fr[0], fr[-1] + 1)), (k, fr)
    return out


def put_obj(meta, prop, img, frames, x0, y0, states, note=""):
    """存一张多帧横排图，在 room.json 的 objects 里记下（键 = 剧本的 prop id）。"""
    fh, fw = frames[0].shape[:2]
    save(img, np.concatenate(frames, axis=1))
    info = {"img": f"{img}.png", "x": int(x0), "y": int(y0), "w": fw, "h": fh, "frames": len(frames),
            "states": _states(states), "default": "default"}
    if note:
        info["note"] = note
    meta["objects"][prop] = info


def build_objects(meta):
    f, names = table_frames()
    put_obj(meta, "river_home_table", "obj_table", f, TB_X0, TB_Y1 - TB_H + 1,
            {n: {"frames": [i]} for i, n in enumerate(names)}, "桌面上的东西；沙漏、本子、照片、来客册是单独的物件")
    f, st = hourglass_frames()
    put_obj(meta, "river_home_hourglass", "obj_hourglass", f, HG_X, T_TOP - HG_H, st,
            "右边铁丝挑着的小铃 = 漏完时响的轻铃（sfx bell_soft）")
    f, st = notebook_frames()
    put_obj(meta, "niff_notebook", "obj_notebook", f, NB_X, T_TOP - NB_H, st,
            "桌上那本：合着 / 摊开；每页的字是特写 art/river_story/closeup_niff_notebook_<state>.png")
    f, st = photo_frames()
    put_obj(meta, "niff_photo", "obj_photo", f, PH_X, T_TOP - PH_H, st, "特写 closeup_niff_photo.png")
    f, st = guestbook_frames()
    put_obj(meta, "guestbook", "obj_guestbook", f, GB_X0, GB_Y0, st,
            "一帧横跨桌子到窗台：open / photo_cup / pages_stuck / closed / drawing_in 在桌上，drying / dry 在窗台上；"
            "特写 closeup_guestbook_<state>.png")
    f, st = chair_frames()
    put_obj(meta, "river_home_chair", "obj_chair", f, CH_X0, FL - CH_H, st, "晨坐的那把：default 靠在柜子边，by_window 在窗边")
    f, st = cabinet_frames()
    put_obj(meta, "river_home_cabinet", "obj_cabinet", f, CB_X0, CB_Y0, st, "柜门；柜体和柜顶的盒子在 home_back 里")
    f, st, cls = player_frames()
    put_obj(meta, "river_home_player", "obj_player", f, PL_X0, FL - 14 - PL_H, st,
            "屏幕里是影像缩小的；影像特写 art/river_story/closeup_footage_<state>.png（一格放大 2 倍），"
            "整段动画 art/river_home/footage_<state>.png（多帧横排，每帧 112×80，100ms）")
    STORY.mkdir(parents=True, exist_ok=True)
    for stn, frs in cls.items():
        save(f"footage_{stn}", np.concatenate(frs, axis=1))
        key = {"footage_part1": 5, "footage_part2": 6, "glitch": 1, "camera_tilt": 3, "ear_swing": 2}.get(stn, 0)
        Image.fromarray(x3(frs[min(key, len(frs) - 1)], 2)).save(STORY / f"closeup_footage_{stn}.png")
    f, st, (lx, ly) = labels_frames()
    put_obj(meta, "river_home_labels", "obj_labels", f, lx, ly, st,
            "on = 每张标签亮一档（晨注意到屋里几乎每件东西都有标签，原文 81）")
    return meta


def x3(a, k=3):
    return np.repeat(np.repeat(a, k, 0), k, 1)


FONT = ROOT / "fonts" / "PixelFont.ttf"


def _obj_frame(name, i):
    info = json.loads((OUT / "room.json").read_text())["objects"][name]
    sheet = Image.open(OUT / info["img"])
    return sheet.crop((i * info["w"], 0, (i + 1) * info["w"], info["h"]))


def _frames_of(v):
    return [v] if isinstance(v, int) else list(range(v[0], v[1] + 1))


def room_image(states=None, chen_at=None, niff_at=None, front_alpha=0.0):
    """按给的状态把屋子拼起来（states: {prop: 状态名}），可选摆一个晨（idle 第一帧）和妮芙的占位色块。"""
    meta = json.loads((OUT / "room.json").read_text())
    im = Image.new("RGBA", (W, H), (24, 30, 36, 255))
    im.alpha_composite(Image.open(OUT / meta["back"]))
    for name, o in meta["objects"].items():
        st = (states or {}).get(name, "default")
        v = o["states"].get(st, o["states"]["default"])
        im.alpha_composite(_obj_frame(name, _frames_of(v)[0]), (o["x"], o["y"]))
    im.alpha_composite(Image.open(OUT / meta["light"]))
    if chen_at is not None:
        chen = Image.open(ROOT / "art/characters/chen/chen_oscar.png").convert("RGBA").crop((7 * 68, 0, 8 * 68, 60))
        im.alpha_composite(chen, (meta["markers"][chen_at] - 28, FL - 58))
    if niff_at is not None:
        x = meta["markers"][niff_at]
        im.alpha_composite(Image.new("RGBA", (10, 44), (90, 170, 190, 200)), (x - 5, FL - 44))
    if front_alpha > 0:
        a = np.array(Image.open(OUT / meta["front"]))
        a[..., 3] = (a[..., 3] * front_alpha).astype(np.uint8)
        im.alpha_composite(Image.fromarray(a))
    return im


# 联系表里按剧情顺序拼几格（原文的几个时刻）
MOMENTS = [
    ("进门（81–82）：两碗热水、本子第一页、沙漏在漏", {"river_home_table": "two_bowls_water", "niff_notebook": "page1",
                                                       "river_home_hourglass": "running", "river_home_labels": "on"}),
    ("吃面包、铃响（86–88）", {"river_home_table": "half_back", "niff_notebook": "plane_on_shore", "river_home_hourglass": "empty",
                           "river_home_labels": "on"}),
    ("来客册、杯底（89–90）", {"river_home_table": "cup_bottom", "guestbook": "pages_stuck", "river_home_labels": "on"}),
    ("册子在窗边晾、椅子搬到窗边（91–93）", {"river_home_table": "phone_corner", "guestbook": "drying", "river_home_chair": "by_window",
                                  "river_home_labels": "on"}),
    ("开柜子、影像（95–100）", {"river_home_cabinet": "footage_box", "river_home_player": "footage_part1", "guestbook": "drying",
                           "river_home_chair": "by_window", "river_home_labels": "on"}),
    ("回来以后：照片、旧记录、纸套（116–122）", {"river_home_table": "sleeves_drying", "niff_photo": "flattened",
                                     "niff_notebook": "record_behind_photo", "river_home_cabinet": "footage_box",
                                     "guestbook": "drying", "river_home_chair": "by_window", "river_home_labels": "on"}),
    ("修好影像（123–131）", {"river_home_table": "phone_at_hand", "river_home_player": "paused", "niff_photo": "flattened",
                         "river_home_cabinet": "footage_box", "guestbook": "dry", "river_home_chair": "by_window",
                         "river_home_labels": "on"}),
    ("告别（146–150）：两杯茶、画夹进来客册", {"river_home_table": "two_cups_tea", "guestbook": "drawing_in",
                                    "niff_photo": "flattened", "river_home_cabinet": "footage_box",
                                    "river_home_chair": "by_window", "river_home_labels": "on"}),
]


def preview(out_dir: Path):
    from PIL import ImageDraw, ImageFont
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = json.loads((OUT / "room.json").read_text())
    font = ImageFont.truetype(str(FONT), 11)
    # 1) 屋子：默认 + 晨 + 妮芙占位；前墙盖上
    full = Image.new("RGBA", (W, H * 2 + 8), (24, 30, 36, 255))
    full.alpha_composite(room_image(chen_at="river_home_chen", niff_at="river_home_niff"), (0, 0))
    full.alpha_composite(room_image(front_alpha=1.0), (0, H + 8))
    full.resize((full.width * 3, full.height * 3), Image.NEAREST).save(out_dir / "home_preview.png")
    # 2) 剧情里的几个时刻（每格是整间屋，原生 1 倍 ×2）
    cw, chh = W * 2, H * 2 + 16
    sheet = Image.new("RGBA", (cw * 2 + 12, chh * 4 + 8), (36, 42, 48, 255))
    d = ImageDraw.Draw(sheet)
    for i, (lab, st) in enumerate(MOMENTS):
        x, y = 4 + (i % 2) * (cw + 4), 4 + (i // 2) * chh
        im = room_image(st, chen_at="river_home_chen", niff_at="river_home_niff")
        sheet.alpha_composite(im.resize((W * 2, H * 2), Image.NEAREST), (x, y + 14))
        d.text((x, y), lab, font=font, fill=(220, 220, 210))
    sheet.save(out_dir / "home_moments.png")
    # 3) 每个物件的每个状态（放大，下面写状态名）
    rows = []
    for name, o in meta["objects"].items():
        cells = []
        for st, v in o["states"].items():
            fr_ids = _frames_of(v)
            for k, fi in enumerate(fr_ids):
                fr = _obj_frame(name, fi)
                if name == "river_home_labels":
                    continue
                cells.append((f"{st}" + (f" {k}" if len(fr_ids) > 1 else ""), fr))
        if not cells:
            continue
        k = 4 if o["w"] < 80 else 2
        cw2 = max(fr.width for _, fr in cells) * k + 8
        ch2 = max(fr.height for _, fr in cells) * k + 18
        per = max(1, 1500 // cw2)
        nrow = (len(cells) + per - 1) // per
        img = Image.new("RGBA", (min(len(cells), per) * cw2 + 8, nrow * ch2 + 20), (36, 42, 48, 255))
        dd = ImageDraw.Draw(img)
        dd.text((4, 2), f"{name}（{o['img']}）", font=font, fill=(220, 220, 210))
        for i, (lab, fr) in enumerate(cells):
            x, y = 4 + (i % per) * cw2, 18 + (i // per) * ch2
            bg = Image.new("RGBA", fr.size, (52, 60, 68, 255))
            bg.alpha_composite(fr)
            img.alpha_composite(bg.resize((fr.width * k, fr.height * k), Image.NEAREST), (x, y))
            dd.text((x, y + fr.height * k + 2), lab, font=font, fill=(200, 200, 190))
        rows.append(img)
    Wd = max(r.width for r in rows)
    sh = Image.new("RGBA", (Wd, sum(r.height for r in rows)), (36, 42, 48, 255))
    y = 0
    for r in rows:
        sh.alpha_composite(r, (0, y))
        y += r.height
    sh.save(out_dir / "home_objects.png")
    return out_dir / "home_preview.png", out_dir / "home_moments.png", out_dir / "home_objects.png"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=Path)
    a = ap.parse_args()
    meta = build()
    (OUT / "room.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("→", OUT)
    if a.preview:
        print(preview(a.preview))


if __name__ == "__main__":
    main()
