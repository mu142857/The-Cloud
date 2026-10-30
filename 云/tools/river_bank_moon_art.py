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
W = 1440                        # 河岸宽
G = 206                         # 岸（石砌码头）的地面
WL = 218                        # 近处的水面（water 层的上沿）
HOME_X = 890                    # 妮芙家底边中点
HOME = (680, 1100)              # 妮芙家占的那一段（house 的 back 画在这里，主层这段只画地面和水下的旧一层）
SHALLOW = (1160, 1300)          # 下游浅滩
STAIR = 1351                    # 去市集的石阶口

GROUND = [[0, 214], [110, 214], [150, 212], [330, 206], [570, 206], [582, 209], [595, 212], [608, 215], [660, 215],
          [673, 212], [686, 209], [700, 206], [1100, 206], [1160, 213], [1300, 213], [1312, 206], [1440, 206]]


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


def glow(cv: Cv, cx, cy, r, base_mask=None, steps=((0.45, 0), (0.75, 1)), solid_only=True, warm=WARM):
    """暖光落到周围的东西上：已经画了的像素里，离灯 r 以内的一圈往暖色推（两档，边上棋盘格）。"""
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
            if d > 0.75 and (x + y) % 2:
                continue
            c = tuple(int(v) for v in cv.a[y, x, :3])
            L = to_lab(c)[0]
            t = 0.55 * (1 - d) ** 1.2
            tgt = warm[1] if d > 0.5 else warm[2]
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
    img = ra.pillar(w, h, seed, pal, crown=[B(.07, .02, 258), B(.1, .022, 252)] if crown else None, kind=kind,
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


def carve(cv: Cv, x, y, w, h, kind="arch", lit=True, door=False, pal=STONE, glow_r=None):
    """在石头上凿一个洞（门 / 窗）：洞口左、上的内壁在影子里（墙厚），里面透暖黄的灯；右沿、下沿的石唇受月光。
    门：里面暗一点，地上一道暖光，左边一扇半开的木门。"""
    m = opening_mask(w, h, kind)
    for yy in range(h):
        for xx in range(w):
            if not m[yy, xx]:
                continue
            el = xx == 0 or not m[yy, xx - 1]
            et = yy == 0 or not m[yy - 1, xx]
            el2 = xx == 1 or (xx > 1 and not m[yy, xx - 2])
            if not lit:
                c = DARK if (el or et) else B(.06, .02, 262)
            elif door:
                c = DARK if (el or et) else (WARM[0] if yy < h * 0.5 else (WARM[1] if yy < h - 2 else WARM[3]))
            else:
                c = DARK if (el or et) else (WARM[1] if el2 else (WARM[2] if yy < h * 0.4 else WARM[3]))
            cv.px(x + xx, y + yy, c)
    if lit and not door and w >= 4 and h >= 4:
        cv.px(x + w - 2, y + h - 2, WARM[4])
    for yy in range(h):
        row = np.nonzero(m[yy])[0]
        if len(row):
            cv.px(x + row[-1] + 1, y + yy, pal[-2])
    cv.hline(x - 1, x + w + 1, y + h, pal[-1])
    if door:
        cv.rect(x + 1, y + int(w / 2) + 1, x + max(2, w // 3), y + h, WOOD[1])
        cv.vline(x + max(2, w // 3) - 1, y + int(w / 2) + 1, y + h, WOOD[3])
    if lit:
        glow(cv, x + w / 2, y + h / 2, glow_r or (max(w, h) + 6))


def boulder_house(cv: Cv, cx, base, w, h, seed, openings=(), pal=STONE, moss=True, pipe=None):
    """巨石里凿出来的屋：一整块圆鼓的石头，门窗是凿出的洞；顶上一层苔、几缕垂叶。
    openings = [(kind, 离左 x, 离地 y, w, h, lit, door)]。返回左上角。"""
    rng = np.random.default_rng(seed)
    m = blob_mask(w, h, rng)
    img = shade_mass(m, rng, pal, cracks=2 + w // 40, strata=1 + w // 50)
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
    return x0, y0


def rough_wall(cv: Cv, x0, x1, y0, y1, rng, pal=STONE):
    """大块粗石垒的墙：一层层大小不一的石块（不是砖：块宽 9~22、层高 6~11，边角圆、缝是暗的），每块上沿、右沿受月光。"""
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
    """粗石垒的矮屋：墙是大石块，顶上压一块挑出去的厚石板（上面长苔）。openings 同 boulder_house（相对 x0、地面）。"""
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
MID_WL = 197                     # 中景的水线（码头上沿后面一点）


def rock_dwelling(cv: Cv, x, seed, h, w, wins, kind="hoodoo"):
    """河里一块凿了窗的石头（中景，比近处淡一档）：几扇小窗透暖光，一扇门洞贴着水，门口一块踏脚石。"""
    img = ra.pillar(w, h, seed, STONE_FAR, crown=[B(.11, .02, 256), B(.14, .022, 250)], kind=kind)
    ox, oy = int(x - img.shape[1] // 2), int(MID_WL + 3 - img.shape[0] + 1)
    cv.paste(img, ox, oy)
    for (dy, lit) in wins:
        r = rows_of(img, ox, oy, MID_WL - dy)
        if r is None:
            continue
        cx_ = (r[0] + r[1]) // 2
        cv.rect(cx_ - 1, MID_WL - dy, cx_ + 2, MID_WL - dy + 3, WARM[2] if lit else B(.07, .02, 262))
        cv.px(cx_ - 1, MID_WL - dy, WARM[1] if lit else DARK)
    r = rows_of(img, ox, oy, MID_WL - 6)
    if r:
        cx_ = (r[0] + r[1]) // 2 + 2
        cv.rect(cx_ - 2, MID_WL - 7, cx_ + 2, MID_WL + 1, B(.05, .02, 264))
        cv.hline(cx_ - 4, cx_ + 4, MID_WL + 1, STONE_FAR[3])


def stone_head(cv: Cv, x, wl):
    """半沉在河里的石头人头（借 art/underwater/head.png 那颗的形，换成月夜河的颜色）：只露出鼻子以上，侧脸朝右；
    头顶上有人放了一盏灯。"""
    a = np.array(Image.open(ROOT / "art" / "underwater" / "head.png").convert("RGBA"))
    sub = a[:, 260:440]
    m = sub[..., 3] > 0
    ys, xs = np.nonzero(m)
    sub = sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    sub = night(sub, 0.82)
    hh = sub.shape[0]
    keep = int(hh * 0.62)                              # 水线在下巴上面一点
    sub = sub[:keep].copy()
    ox = int(x - sub.shape[1] // 2)
    cv.paste(sub, ox, wl - keep + 1)
    tm = sub[..., 3] > 0
    ty = int(np.nonzero(tm.any(1))[0][0])
    txs = np.nonzero(tm[ty + 2])[0]
    lantern(cv, ox + int(txs.mean()) - 4, wl - keep + 1 + ty - 3, "post", r=10)
    return ox, sub


def bank_mid():
    w = int(math.ceil(SW + (W - SW) * MID_S))
    cv = Cv(w, SH)
    stone_head(cv, 724, MID_WL + 2)
    for i, (x, h, wd, wins, kind) in enumerate((
            (73, 46, 14, ((22, True),), "hoodoo"), (186, 34, 12, ((16, False),), "stack"),
            (315, 58, 16, ((20, True), (36, True)), "tower"), (640, 44, 14, ((18, True),), "stack"),
            (892, 52, 15, ((24, True),), "hoodoo"))):
        rock_dwelling(cv, x, 3110 + i, h, wd, wins, kind)
    for i, (x, h, wd, kind) in enumerate(((236, 120, 18, "spire"), (420, 96, 14, "hoodoo"), (980, 130, 20, "twin"))):
        pillar_at(cv, x, MID_WL + 3, wd, h, 3120 + i, kind=kind, pal=ROCK_FAR)
    # 石头之间几块露出水面的踏脚石
    for (a, b) in ((86, 112), (330, 352), (654, 676)):
        for k, xx in enumerate(range(a, b, 7)):
            cv.rect(xx, MID_WL - 1, xx + 4, MID_WL + 1, STONE_FAR[2])
            cv.hline(xx, xx + 4, MID_WL - 1, STONE_FAR[4])
    reflect_down(cv, MID_WL + 2, 10, seed=3130)
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
    """晨走的岸：左边卵石滩（窄水道边）→ 石砌码头 → 台阶下到水边的平台 → 码头 → 浅滩 → 码头。
    顶面一行被月光照亮，往下是石块（越往下越暗，泡进水里那截主层下面再压暗）。"""
    for x in range(W):
        top = gy(x)
        beach = x < 330 or SHALLOW[0] - 60 < x < SHALLOW[1] + 12
        for y in range(top, SH):
            d = y - top
            if beach:
                # 卵石：小圆点，亮的点在上面几行
                n = (x * 7 + y * 13 + (x // 3) * 5) % 11
                k = 2 if d < 2 else (1 if n < 5 else 0)
                if d >= 2 and n == 0 and d < 8:
                    k = 3
            else:
                # 石块：一层 5 像素，错缝
                row = d // 5
                bx = (x + (row % 2) * 7) // 14
                edge = d % 5 == 0 or (x + (row % 2) * 7) % 14 == 0
                k = 0 if edge else (2 if d < 6 else 1)
                if not edge and (bx * 31 + row * 17) % 7 == 0:
                    k = max(0, k - 1)
            cv.px(x, y, ROCK[k])
        cv.px(x, top, ROCK[4] if (x % 9) else ROCK[3])
        if not beach and x % 13 < 11:
            cv.px(x, top + 1, ROCK[3])


def steps(cv: Cv):
    """台阶：码头上沿往下 5 级到水边的平台（595–660，地面 215），左右各一道矮石栏。"""
    for i in range(4):
        x0 = 572 + i * 6
        y = 206 + i * 2 + 2
        cv.rect(x0, y, 700 - i * 6, y + 2, ROCK[2])
        cv.hline(x0, 700 - i * 6, y, ROCK[3])
    cv.rect(596, 215, 660, 218, ROCK[2])
    cv.hline(596, 660, 215, ROCK[4])
    # 系船的铁环
    cv.px(629, 217, B(.3, .02, 246))
    cv.px(630, 216, B(.3, .02, 246))
    cv.px(631, 217, B(.3, .02, 246))


def underwater_old_floor(cv: Cv, rng):
    """妮芙家下面泡在水里的旧一层：旧墙、旧门（x 712–734）、旧门牌（和现在门边那块同一个位置、同样的字迹）。
    水下的街砖，几扇泡水的窗（窗框间有小鱼）。"""
    old = ra.bramp(4, .09, .2, 252, 240)
    x0, x1 = HOME[0] + 4, HOME[1] - 4
    shade_box(cv, x0, WL + 1, x1, SH, old, lit_t=False, seed=4101)
    for y in range(WL + 4, SH, 6):
        for x in range(x0, x1):
            if (x + (y // 6) * 9) % 18 == 0:
                cv.vline(x, y, y + 6, old[0])
        cv.hline(x0, x1, y, old[0])
    # 旧门
    cv.rect(711, WL + 5, 735, SH, B(.05, .02, 262))
    cv.rect(713, WL + 7, 733, SH, B(.08, .025, 248))
    for k in range(716, 733, 4):
        cv.vline(k, WL + 7, SH, B(.06, .02, 252))
    cv.rect(709, WL + 3, 737, WL + 5, old[2])
    # 旧门牌（和新门牌同一个 x）
    plate_x = HOME[0] + HOUSE_PLATE[0]
    cv.rect(plate_x, WL + 12, plate_x + 11, WL + 19, B(.2, .03, 220))
    cv.hline(plate_x + 2, plate_x + 9, WL + 14, B(.32, .03, 210))
    cv.hline(plate_x + 2, plate_x + 7, WL + 16, B(.32, .03, 210))
    # 泡水的窗（两扇），窗框间的小鱼
    for wx in (820, 940, 1030):
        cv.rect(wx, WL + 10, wx + 18, WL + 30, B(.05, .02, 262))
        cv.rect(wx + 1, WL + 11, wx + 17, WL + 29, B(.1, .03, 236))
        cv.vline(wx + 9, WL + 11, WL + 29, B(.05, .02, 262))
        cv.hline(wx + 1, wx + 17, WL + 20, B(.05, .02, 262))
    for (fx, fy, d) in ((826, WL + 15, 1), (946, WL + 24, -1), (1034, WL + 14, 1), (870, WL + 30, -1)):
        fish(cv, fx, fy, d)


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


def high_huts(cv: Cv):
    """高处的街：两根石柱，柱身上部凿出住处（门洞、几扇小窗透暖光），门口一块凿出来的石台，两个石台之间一座窄桥（邮差）。"""
    imgs = []
    for (x, w, h, seed, kind) in ((492, 30, 178, 4201, "tower"), (612, 26, 172, 4202, "stack")):
        img = ra.pillar(w, h, seed, STONE, crown=[B(.07, .02, 258), B(.1, .022, 252)], kind=kind)
        ox, oy = int(x - img.shape[1] // 2), int(G - 1 - img.shape[0] + 1)
        cv.paste(img, ox, oy)
        imgs.append((img, ox, oy))
    (i1, o1x, o1y), (i2, o2x, o2y) = imgs
    r1 = rows_of(i1, o1x, o1y, 60)
    r2 = rows_of(i2, o2x, o2y, 60)
    # 石台：从柱身伸出来的一块厚石板（门口），下面一道影子
    ledges = ((r1[1] - 6, r1[1] + 8), (r2[0] - 8, r2[0] + 6))
    for (a, b) in ledges:
        cv.rect(a, 68, b, 72, STONE[2])
        cv.hline(a, b, 68, STONE[5])
        cv.hline(a, b, 72, DARK)
        cv.vline(b - 1, 68, 72, STONE[4])
    # 门洞、窗（左柱门朝右开在石台上，右柱门朝左）
    carve(cv, r1[1] - 13, 54, 7, 14, "arch", True, True)
    carve(cv, (r1[0] + r1[1]) // 2 - 3, 36, 4, 6, "arch", True)
    carve(cv, (r1[0] + r1[1]) // 2 - 1, 92, 4, 5, "round", False)
    carve(cv, r2[0] + 5, 55, 7, 13, "arch", True, True)
    carve(cv, (r2[0] + r2[1]) // 2 + 1, 40, 4, 6, "arch", True)
    lantern(cv, r1[1] + 6, 58, "hang")
    postman_bridge(cv, ledges[0][1], ledges[1][0])
    # 一道往下的绳梯（柱子上去的路）
    for y in range(74, G - 4, 3):
        cv.hline(r1[1] + 2, r1[1] + 7, y, WOOD[1])
    cv.vline(r1[1] + 2, 72, G - 2, WOOD[0])
    cv.vline(r1[1] + 6, 72, G - 2, WOOD[0])


def postman_bridge(cv: Cv, x0=522, x1=594, y=67):
    """两块石台之间一座窄木桥（邮差从这里走过，原文 80）：木板一行，一根绳栏杆，下垂一点。"""
    for x in range(x0, x1 + 1):
        t = (x - x0) / (x1 - x0)
        yy = y + int(round(2 * math.sin(math.pi * t)))
        cv.px(x, yy + 1, WOOD[2] if x % 4 else WOOD[0])
        cv.px(x, yy + 2, WOOD[0])
        if x % 6 == 0:
            cv.vline(x, yy - 7, yy + 1, WOOD[1])
    rope_line(cv, x0, y - 7, x1, y - 7, 3, WOOD[3])



def stone_lantern(cv: Cv, x, base):
    """石灯笼：方座、细柱、灯室（暖光从四面小窗透出来）、宽顶。"""
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


def mooring_post(cv: Cv, x, base):
    """木桩（原文 78，老人站在它旁边）：粗的一根，顶上缠着绳，下半截泡进水里。"""
    cv.rect(x - 2, base - 22, x + 3, SH, WOOD[1])
    cv.vline(x + 2, base - 22, SH, WOOD[3])
    cv.vline(x - 2, base - 22, SH, WOOD[0])
    cv.hline(x - 2, x + 3, base - 22, WOOD[4])
    for y in range(base - 18, base - 12, 2):
        cv.hline(x - 3, x + 4, y, B(.3, .03, 70))
    cv.line([(x + 3, base - 14), (x + 12, base + 6)], B(.24, .03, 70))


def bakery(cv: Cv):
    """面包店（x≈1150）：粗石垒的两层矮屋（一块大石板压顶），下面一扇凿出来的大暖窗（架子上一排面包），
    二楼窗下伸出一块长木板搭到对面修补摊——摊子在浅滩里一块平顶的大石头上。"""
    x0, x1 = 1112, 1172
    stone_hut(cv, x0, x1, G, 48, 4301,
              openings=(("rect", 5, 6, 20, 13, True, False), ("arch", 33, 0, 8, 18, True, True),
                        ("arch", 44, 28, 6, 9, True, False)))
    for k in range(4):                                   # 窗里的面包：几块暗暖的圆
        cv.rect(x0 + 8 + k * 4, G - 10, x0 + 11 + k * 4, G - 8, WARM[1])
    cv.rect(x0 + 4, G - 30, x0 + 26, G - 25, WOOD[2])    # 招牌（一块木板，上面一道暖色的字）
    cv.hline(x0 + 4, x0 + 26, G - 30, WOOD[4])
    cv.hline(x0 + 7, x0 + 23, G - 28, WARM[1])
    # 伸出去的木板（二楼窗下）→ 修补摊
    for x in range(x1, 1240):
        cv.px(x, G - 30, WOOD[3])
        cv.px(x, G - 29, WOOD[1])
    # 修补摊：浅滩里一块平顶大石头，上面一个布棚、挂着工具、一盏灯
    rng = np.random.default_rng(4302)
    sx0, sx1 = 1236, 1286
    m = np.zeros((SH - (G - 30), sx1 - sx0), bool)
    for x in range(sx1 - sx0):
        u = abs((x + .5 - (sx1 - sx0) / 2) / ((sx1 - sx0) / 2))
        t = 0 if u < 0.8 else int((u - 0.8) * 20)
        m[t:, x] = True
    img = shade_mass(m, rng, STONE, cracks=2, strata=1)
    cv.paste(img, sx0, G - 30)
    cv.vline(sx0 + 3, G - 56, G - 30, WOOD[1])
    cv.vline(sx1 - 4, G - 50, G - 30, WOOD[1])
    cv.poly([(sx0, G - 56), (sx1, G - 50), (sx1, G - 47), (sx0, G - 53)], B(.13, .03, 230))
    cv.line([(sx0, G - 56), (sx1, G - 50)], B(.24, .03, 222))
    for (tx, ln) in ((sx0 + 10, 6), (sx0 + 15, 4), (sx0 + 32, 7)):
        cv.vline(tx, G - 46, G - 46 + ln, B(.22, .015, 240))
    cv.rect(sx0 + 38, G - 36, sx0 + 44, G - 30, WOOD[1])
    cv.hline(sx0 + 38, sx0 + 44, G - 36, WOOD[3])
    lantern(cv, sx0 + 22, G - 43, "hang", r=10)


def boat(cv: Cv, x0, wl):
    """系在浅滩边的小船（原文 83、146）：两头翘的木壳，船头一个空挂钩（铃原来挂这），一根缆绳拴到修补摊的桩上。"""
    x1 = x0 + 44
    for x in range(x0, x1):
        t = (x - x0) / (x1 - x0)
        top = wl - 4 - int(round(3 * (abs(t - 0.5) * 2) ** 2.2))
        for y in range(top, wl + 2):
            k = 1 if y > top else 3
            cv.px(x, y, WOOD[k])
    cv.hline(x0 + 3, x1 - 3, wl - 3, WOOD[0])
    # 船头的挂钩杆
    cv.vline(x1 - 3, wl - 14, wl - 5, WOOD[2])
    cv.hline(x1 - 3, x1 + 1, wl - 14, WOOD[2])
    cv.px(x1, wl - 13, B(.3, .02, 246))
    rope_line(cv, x1 - 2, wl - 5, 1258, G - 10, 2, B(.22, .03, 70))


def market_cliff(cv: Cv):
    """右端：一大块岩壁（上面是高处市集），岩壁上凿出往上走的石阶（STAIR 口），沿路几盏灯；最右一道窄巷口往南桥。"""
    img = ra.pillar(70, 214, 4401, ROCK, crown=[B(.07, .02, 258), B(.1, .022, 252)], kind="tower")
    cv.paste(img, 1386 - img.shape[1] // 2, G - img.shape[0] + 1)
    img2 = ra.pillar(40, 180, 4402, ROCK, crown=None, kind="stack")
    cv.paste(img2, 1330 - img2.shape[1] // 2, G - img2.shape[0] + 1)
    # 岩壁里也住着人：右边几扇凿出来的窗
    o1 = (1386 - img.shape[1] // 2, G - img.shape[0] + 1)
    o2 = (1330 - img2.shape[1] // 2, G - img2.shape[0] + 1)
    for (im_, (ox, oy), y, side, lit) in ((img, o1, 52, 1, True), (img, o1, 104, 1, True), (img, o1, 150, 1, False),
                                          (img2, o2, 70, -1, True), (img2, o2, 128, -1, False)):
        r = rows_of(im_, ox, oy, y)
        if r:
            x = r[1] - 10 if side > 0 else r[0] + 5
            carve(cv, x, y, 5, 7, "arch", lit, pal=ROCK)
    # 石阶：从码头上的口子（1336–1366）往左上折上去
    st = ra.bramp(5, .1, .3, 258, 244)
    segs = [((1344, G - 1), (1392, G - 64)), ((1392, G - 64), (1344, G - 128)), ((1344, G - 128), (1388, G - 186)),
            ((1388, G - 186), (1360, G - 230))]
    for (ax, ay), (bx, by) in segs:
        d = 1 if bx > ax else -1
        n = int((ay - by) / 3)
        for i in range(n + 1):
            x = int(round(ax + (bx - ax) * i / n))
            y = int(round(ay + (by - ay) * i / n))
            if y < 0:
                break
            cv.rect(x - 9, y, x + 9, y + 9, B(.05, .02, 264))            # 凿进岩壁的槽（暗）
        for i in range(n + 1):
            x = int(round(ax + (bx - ax) * i / n))
            y = int(round(ay + (by - ay) * i / n))
            if y < 0:
                break
            cv.hline(x - 8, x + 8, y, st[3] if i % 2 == 0 else st[2])     # 踏面受月光
            cv.hline(x - 8, x + 8, y + 1, st[1])
            cv.px(x + 8 * d, y - 4, WOOD[2])                               # 扶手的柱
        rope_line(cv, ax + 8 * d, ay - 5, bx + 8 * d, by - 5, 1, WOOD[3])
    # 阶梯口：两根门柱 + 一盏灯
    for px_ in (1334, 1368):
        cv.rect(px_, G - 26, px_ + 4, G, st[1])
        cv.vline(px_ + 3, G - 26, G, st[3])
        cv.hline(px_ - 1, px_ + 5, G - 27, st[3])
    lantern(cv, 1372, G - 30, "post", r=11)
    lantern(cv, 1352, G - 74, "hang", r=9)
    lantern(cv, 1362, G - 130, "hang", r=8)
    # 往南桥的窄巷：岩壁最右边一道拱形的口子，里面暗，深处一点暖灯
    for y in range(G - 44, G):
        half = 11 if y > G - 34 else int(math.sqrt(max(0, 121 - (G - 34 - y) ** 2 * 1.2)))
        for x in range(1430 - half, 1430 + half + 1):
            cv.px(x, y, B(.035, .02, 266))
        cv.px(1430 - half - 1, y, st[1])
        cv.px(1430 + half + 1, y, st[4])
    cv.rect(1428, G - 22, 1431, G - 19, WARM[2])
    cv.px(1429, G - 21, WARM[3])
    for y in range(G - 6, G):
        cv.hline(1420 + (G - y), 1441, y, st[1] if (G - y) % 2 else st[2])
    lantern(cv, 1414, G - 40, "hang", r=8)


def plane_beach(cv: Cv, rng):
    """左边：窄水道（飞行最后一格那面墙：一根大石柱一直下到水里）、卵石滩上一棵垂枝树、几块礁石。"""
    img = pillar_at(cv, 18, SH + 20, 46, 290, 4501, kind="tower", crown=True)
    ox, oy = int(18 - img.shape[1] // 2), int(SH + 20 - img.shape[0] + 1)
    r = rows_of(img, ox, oy, 96)
    if r:
        carve(cv, r[1] - 12, 96, 5, 8, "arch", True, pal=ROCK)
    weeping(cv, 268, gy(268), 64, 52, 4502)
    weeping(cv, 112, gy(112) - 1, 30, 20, 4503, kind="young")


def reeds_near(cv: Cv, x, base, h, seed, k=6):
    pal = [B(.06, .02, 262), B(.09, .022, 256), B(.13, .024, 250)]
    tmp = ra.Layer(cv.w, cv.h)
    ra.reeds(tmp, x, base, h, seed, pal, k=k)
    cv.paste(tmp.a, 0, 0)


def bank_main():
    rng = np.random.default_rng(4001)
    cv = Cv(W, SH)
    plane_beach(cv, rng)
    high_huts(cv)
    market_cliff(cv)
    bakery(cv)
    # 第一间小屋：木桩后面，箱子靠着它（原文 74 岸边一排箱子）
    boulder_house(cv, 398, G, 66, 48, 4601, pipe=50,
                  openings=(("arch", 26, 0, 9, 17, True, True), ("round", 9, 16, 8, 8, True, False),
                            ("arch", 46, 18, 6, 8, False, False)))
    # 码头上的石灯笼（石像的位置）、路灯
    stone_lantern(cv, 552, G)
    stone_lantern(cv, 1092, G)
    # 地面、台阶
    quay(cv, rng)
    steps(cv)
    mooring_post(cv, 346, G)
    reeds_near(cv, 152, gy(152), 18, 4701)
    reeds_near(cv, 326, gy(326), 14, 4702, k=4)
    reeds_near(cv, 1304, 213, 16, 4703, k=5)
    # 水下：旧一层、浅滩的街砖、压暗
    underwater_old_floor(cv, rng)
    submerged_paving(cv, SHALLOW[0] - 50, SHALLOW[1] + 10)
    keep = np.zeros((SH, W), bool)
    lab = cv.a[..., :3].reshape(-1, 3).astype(float)
    underwater_dim(cv, WL + 1)
    boat(cv, 1200, WL - 1)
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


LIGHTS_X = [(378, 1), (395, 1), (552, 1), (752, 1), (868, 2), (1019, 1), (1092, 1), (1127, 2), (1149, 1), (1258, 1),
            (1372, 1), (1414, 1)]


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
    for x, h, k, nb, sd in ((60, 40, 3, 7, 1), (430, 30, 2, 5, 2), (820, 56, 3, 9, 3), (1240, 34, 2, 6, 4),
                            (1560, 48, 3, 8, 5), (1020, 22, 2, 4, 6)):
        tmp = ra.Layer(w, SH)
        ra.reeds(tmp, x, SH - 1 + 6, h, 4910 + sd, dark, k=k)
        for j in range(nb * 2):
            f = rng.random() ** 1.6
            off = rng.normal(0, 6 + 3 * (1 - f))
            ra.blade(tmp, x + off, SH + 4, h * (0.3 + 0.6 * f), off / 14 + rng.uniform(-0.4, 0.4),
                     int(rng.choice([3, 3, 4])), dark)
        cv.paste(tmp.a, 0, 0)
    return cv


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


def objects():
    """河岸的物件：(id, 帧列表[np], x, y, spec)。y 跟着新的地面 / 水面。"""
    out = []
    pf = [night(f.a, 0.8) for f in rca.plane_frames()]
    out.append(("river_bank_plane", pf, 40, WL + 2 - 96 + 6, {"states": {"default": 0, "beached": 1, "straps_drying": 2,
                                                                          "fixed": 3}}))
    cf = [night(f.a, 0.6) for f in rca.crates_frames()]
    out.append(("river_bank_crates", cf, 420, G - cf[0].shape[0], {"ms": 200, "states": {"default": 2, "tail": [0, 1],
                                                                                         "tail_still": 2}}))
    bf = [night(f.a) for f in rca.box_frames()]
    out.append(("river_bank_box", bf, 640, WL - 12, {"states": {"default": 0, "sunk_shallow": 1}}))
    out.append(("river_bank_crate_float", [night(rca.float_crate().a)], 20, WL - 9, {"states": {"default": 0}}))
    for i, (sid, kind) in enumerate(rca.SALVAGE.items()):
        fr = [night(f.a, 0.85) for f in rca.salvage_frames(kind)]
        out.append((f"river_bank_salvage_{sid}", fr, 230 + i * 16, WL - 12,
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
    out.append(("river_bank_salvage_wake", wk, 200, WL - 4, {"default": "hidden", "ms": 300, "states": {"on": [0, 1]}}))
    return out


# ============================================================ 妮芙家（剖面小屋，学树屋）
# 屋内（家具、标签、柜子、影像机……）是会话 D 的 tools/river_home_art.py 画的，这里借它的函数重画一遍：
# 白天的冷光换成月夜（暗一档、往月光蓝推），桌子上方那盏吊灯点亮（一小圈暖黄，别的地方还是冷的）；窗外换成月下的河。
# 屋后加一根大石柱（像树屋靠着大树：前墙淡掉以后，石柱、屋顶还在，分层清楚）；前墙重画成小屋的立面。
# 图比 D 的高 HDY 像素（上面多出来给石柱），所以 D 的物件 y、地板都 + HDY；x 不变，markers 不变。

HOUSE_PLATE = (66, 0)            # 现在的门牌在图里的 x（旧门牌在水下同一个 x）
HDY = 30                         # 比 D 的图高多少


# ============================================================ 河岸 room.json

def bank_json(objs):
    layers = [
        {"id": "sky", "img": "res://art/river/sky.png", "scroll": 0.0, "y": 0},
        {"id": "ridge", "img": "res://art/river/ridge.png", "scroll": 0.05, "y": 0, "tile": True},
        {"id": "mist", "img": "res://art/river/mist.png", "scroll": 0.1, "y": 0, "tile": True, "drift": -2.5},
        {"id": "shore", "img": "res://art/river/shore.png", "scroll": 0.16, "y": 0, "tile": True},
        {"id": "far_ripples", "img": "res://art/river/ripples.png", "scroll": 0.3, "y": 151, "tile": True,
         "shader": "water", "shader_params": {"palette_mode": False, "speed": 0.7, "wobble": 2.0, "flicker": 0.0,
                                              "show": 0.62}},
        {"id": "glints", "img": "res://art/river/glints.png", "scroll": 0.0, "y": 155, "shader": "water",
         "shader_params": {"palette_mode": True, "speed": 1.0, "wobble": 2.0, "flicker": 0.9, "show": 0.6}},
        {"id": "far_water", "img": "res://art/river/water.png", "scroll": 0.42, "y": 0, "tile": True},
        {"id": "mid", "img": "mid.png", "scroll": MID_S, "y": 0},
        {"id": "main", "img": "main.png", "scroll": 1.0, "y": 0},
        {"id": "water", "img": "water.png", "scroll": 1.0, "y": WL, "water": True, "front": True, "alpha": 0.5},
        {"id": "ripples", "img": "ripples.png", "scroll": 1.0, "y": WL, "shader": "water",
         "shader_params": {"palette_mode": False, "show": 0.62, "wobble": 1.5, "speed": 0.8}, "front": True},
        {"id": "front", "img": "front.png", "scroll": FRONT_S, "y": 0, "front": True},
    ]
    markers = {"river_bank_plane": 190, "river_bank_hatch": 196, "river_bank_channel": 90, "river_bank_crates": 456,
               "river_bank_niff": 470, "river_bank_steps": 626, "river_bank_box": 646, "river_bank_post": 346,
               "river_bank_ting": 360, "river_bank_shallow": 1220, "river_bank_toolkit": 304,
               "river_bank_home_door": HOME[0] + HOUSE_DOOR, "river_bank_doorplate": HOME[0] + HOUSE_PLATE[0] + 5,
               "river_bank_bakery": 1150, "river_bank_postman": 556, "river_bank_to_market": STAIR,
               "river_bank_to_south": 1428, "river_bank_arrive": 1390, "river_bank_drift_start": 236}
    objd = {}
    for oid, frames, x, y, spec in objs:
        d = {"x": int(x), "y": int(y), "w": frames[0].shape[1], "h": frames[0].shape[0], "frames": len(frames)}
        d.update(spec)
        objd[oid] = d
        if oid.startswith("river_bank_salvage_") and oid != "river_bank_salvage_wake":
            markers[oid] = int(x) + d["w"] // 2
    return {
        "_note": "tools/river_bank_moon_art.py 生成，别手改。约定见 docs/river_rooms_contract.md。月夜：天、远岸、雾、碎光沿用 art/river/。",
        "size": [W, SH], "env": "river", "bg": ["#0b1220", "#141d2c"],
        "layers": layers, "ground": GROUND, "markers": markers, "objects": objd,
        "water": {"y": WL}, "walk": [150, W - 10],
        "walkers": [{"npc": "postman", "path": [[528, 68], [588, 68]], "speed": 12, "pause": [3, 8], "z": -20,
                     "loop": "pingpong"}],
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


HOME_ROCK_TOP = 20               # 巨石顶（图里的 y）


def home_rock(rha, hh):
    """妮芙家 = 一块巨石里凿出来的屋（学树屋：大树 → 巨石）。返回 (mask, RGBA)：
    底平、顶是一道起伏的圆拱，左边低一点、右边高（月光从右上来，右肩受光）；顶上长苔、垂叶。"""
    rng = np.random.default_rng(5501)
    w = rha.W
    m = np.zeros((hh, w), bool)
    nz = ra.smooth1d(w, rng, 70, 1.0)
    cx = 250
    for x in range(w):
        u = (x - cx) / (cx if x < cx else w - cx)
        top = HOME_ROCK_TOP + 46 * abs(u) ** 2.3 + 4 * nz[x]
        d = min(x, w - 1 - x)                         # 两边圆肩：最外 12 像素很快往下收
        if d < 12:
            top += 120 * (1 - d / 12) ** 2.2
        m[int(max(0, round(top))):, x] = True
    img = shade_mass(m, rng, STONE, cracks=9, strata=7, amp=0.32)
    return m, img


def home_rock_top(cv: Cv, m):
    """巨石顶上的苔、几丛垂下来的叶帘（河岸的怪植物）、一截烟囱管。"""
    rng = np.random.default_rng(5502)
    h, w = m.shape
    top = [int(np.nonzero(m[:, x])[0][0]) for x in range(w)]
    for x in range(w):
        if rng.random() < 0.7:
            cv.px(x, top[x], MOSS[2] if rng.random() < 0.35 else MOSS[1])
            for d in range(1, int(rng.integers(1, 4))):
                cv.px(x, top[x] + d, MOSS[0])
    for (vx, ln) in ((60, 26), (128, 18), (300, 30), (352, 22), (398, 14)):
        for k in range(8):
            l2 = int(ln * rng.uniform(0.35, 1.0))
            x = vx + k * 2
            for d in range(l2):
                cv.px(x + (1 if d > l2 * 0.7 else 0), top[x] + d, B(.08, .022, 256) if d < l2 - 1 else B(.13, .025, 250))
    px_ = 150
    cv.rect(px_, top[px_] - 9, px_ + 4, top[px_] + 2, B(.1, .015, 250))
    cv.vline(px_ + 3, top[px_] - 9, top[px_] + 2, B(.2, .02, 246))
    cv.hline(px_ - 1, px_ + 5, top[px_] - 9, B(.22, .02, 246))


def home_front(rha, hh, rock):
    """前墙（进屋淡出）= 巨石的正面（和 back 里的石头是同一张，所以淡掉时只有屋里那块变）：
    下面一截是旧水位以下泡过的（发暗、一道苔）；左边凿出的门洞（半开的木门、门上一盏灯、门边现在的门牌），
    中间一扇凿出来的大拱窗（吊灯的暖光透出来，窗台花箱），右边一扇圆窗，左上一扇小暗窗；窗之间一根晾绳。
    只盖屋内那一块（x 14..405，y CEIL-6..FL）。"""
    x0, x1 = rha.IX0 - rha.WALL_T, rha.IX1 + rha.WALL_T
    y0, fl = rha.CEIL - rha.WALL_T + HDY, rha.FL + HDY
    cv = Cv(rha.W, hh)
    cv.a[y0:fl, x0:x1] = rock[y0:fl, x0:x1]
    rng = np.random.default_rng(5601)
    old_y = fl - 42                                   # 旧水位：以下的石头泡过，暗一档、发青
    for y in range(old_y, fl):
        for x in range(x0, x1):
            c = tuple(int(v) for v in cv.a[y, x, :3])
            cv.a[y, x, :3] = mixc(c, B(.07, .03, 232), 0.35)
    for x in range(x0, x1):
        for d in range(int(rng.integers(1, 4))):
            cv.px(x, old_y + d, MOSS[1] if d == 0 else MOSS[0])
        if rng.random() < 0.07:
            for d in range(int(rng.integers(3, 12))):
                cv.px(x, old_y + 3 + d, B(.06, .02, 252))
    # 门洞（D 的门在 X(16)..X(40)）
    dx0, dx1, dtop = rha.X(16), rha.X(40), fl - 60
    carve(cv, dx0, dtop, dx1 - dx0 + 1, fl - dtop, "arch", True, True, glow_r=30)
    for k in range(3):                                # 门口两级凿出来的台阶
        cv.hline(dx0 - 3 + k * 0, dx1 + 4, fl - 1 - k * 0, STONE[4])
    lantern(cv, dx1 + 7, dtop + 4, "hang", r=14)
    # 门牌（现在的地址）：门右边，离地约 30；水下同一个 x 有一块旧的，字一样
    ax, ay = HOUSE_PLATE[0], fl - 34
    cv.rect(ax, ay, ax + 11, ay + 7, Wm(.42, .035, 80))
    cv.vline(ax + 11, ay + 1, ay + 7, Wm(.32, .03, 70))
    cv.hline(ax + 2, ax + 9, ay + 2, B(.14, .02, 250))
    cv.hline(ax + 2, ax + 7, ay + 4, B(.14, .02, 250))
    cv.px(ax + 5, ay - 1, WOOD[3])
    # 大拱窗（暖）+ 两根石棂 + 窗台花箱
    wx, wy, ww, wh = 166, fl - 98, 44, 36
    carve(cv, wx, wy, ww, wh, "arch", True, glow_r=44)
    for k in (15, 29):
        cv.vline(wx + k, wy + 6, wy + wh, STONE[1])
        cv.vline(wx + k + 1, wy + 6, wy + wh, STONE[3])
    cv.hline(wx + 2, wx + ww - 2, wy + 22, STONE[1])
    cv.rect(wx - 3, wy + wh + 2, wx + ww + 3, wy + wh + 7, WOOD[1])
    cv.hline(wx - 3, wx + ww + 3, wy + wh + 2, WOOD[3])
    for k in range(10):
        fx = wx - 1 + k * 5
        cv.line([(fx, wy + wh + 1), (fx + (k % 2), wy + wh - 3)], MOSS[1])
        cv.px(fx + (k % 2), wy + wh - 4, (Wm(.5, .06, 40), B(.4, .03, 300), Wm(.5, .05, 90))[k % 3])
    # 右边圆窗（暖，暗一档）、左上小窗（暗）
    carve(cv, 330, fl - 92, 18, 18, "round", True, glow_r=20)
    cv.hline(331, 347, fl - 83, STONE[1])
    carve(cv, 78, fl - 100, 10, 16, "arch", False)
    # 两扇窗之间的晾绳：一头钉在石头里
    lx0, lx1, ly = 222, 316, fl - 104
    for x in range(lx0, lx1 + 1):
        cv.px(x, int(ly + 5 * math.sin(math.pi * (x - lx0) / (lx1 - lx0))), WOOD[3])
    cv.rect(240, ly + 5, 248, ly + 15, B(.22, .03, 210))
    cv.rect(262, ly + 6, 267, ly + 12, B(.4, .02, 90))
    cv.rect(286, ly + 5, 292, ly + 13, B(.22, .03, 60))
    # 门边两只花盆、一卷绳、靠墙一根撑船的篙
    for k, (ppx, ph) in enumerate(((rha.X(46), 6), (rha.X(53), 5))):
        cv.rect(ppx, fl - ph, ppx + 5, fl, Wm(.24, .04, 50))
        cv.hline(ppx, ppx + 5, fl - ph, Wm(.3, .04, 55))
        for j in range(4):
            cv.line([(ppx + 1 + j, fl - ph - 1), (ppx + j - 1 + (j % 3), fl - ph - 5 - j % 2)], MOSS[2])
    for y in range(fl - 84, fl):
        cv.px(rha.X(110) + (y - (fl - 84)) // 20, y, WOOD[3])
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
    back_d = moon_interior(back_d, dark=0.74)
    hh = rha.H + HDY
    back = Cv(rha.W, hh)
    rm, rock = home_rock(rha, hh)
    back.paste(rock, 0, 0)
    top_d = rha.CEIL - rha.WALL_T                     # D 的屋顶不要（屋是凿在巨石里的），从剖开的楼板往下贴
    back.paste(back_d[top_d:], 0, top_d + HDY)
    home_rock_top(back, rm)
    front = home_front(rha, hh, rock)
    light = home_light(rha, hh)
    # 物件：照 D 的 build_objects 重画一遍，再上月夜 + 吊灯的色
    objs = []

    def put(prop, img, frames, x0, y0, states, note=""):
        fr = [moon_interior(f, x0, y0) for f in frames]
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
            if s["id"] == "glints":
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
                lm = light[..., 3:4] / 255.0
                reg = im[max(0, hy):hy + light.shape[0], :]
                x0 = hx - cam_x
                xs0, xs1 = max(0, x0), min(SW, x0 + light.shape[1])
                if xs0 < xs1:
                    l2 = light[:, xs0 - x0:xs1 - x0]
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
    save_png(bank_mid().a, BANK_DIR / "mid.png")
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
    shots = [(0, {}, 200, 1), (240, {"river_bank_crates": "tail"}, 470, 1), (500, {}, 640, 1), (650, {}, 900, 1),
             (650, {}, 840, 0), (960, {"river_bank_plane": "fixed"}, 1380, 1)]
    tiles = [Image.fromarray(render(room, BANK_DIR, c, st, cx, house=house, house_front=hf)) for c, st, cx, hf in shots]
    sheet = Image.new("RGB", (SW * 2 + 4, (SH + 4) * 3), (20, 20, 20))
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
