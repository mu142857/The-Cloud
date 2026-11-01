"""云层星的居民（第三章终章）：路过的人（passerby）、居民（resident）、镇上的居民（townsfolk）、周围的人（crowd）。
以后改这些人只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/cloud_folk_art.py [--preview 目录]

方向（第三章计划第一节「云层星居民」）：
- 云层星的人是圆头的小个子（小奥斯卡给晨出的候选 A / B / C 那一家的身形，作者 10-28 说三版留着当 NPC），
  但不是晨、也不是候选本身：不长芽（A）、不戴白帽兜（B）、没有长耳（C），每人一身自己的行头。
- 热情：露脸、脸颊一点红、说话时会比划、笑起来往后仰；和母星城市里戴兜帽、互不理睬的人群正好反过来。
- 晨永远最显眼：居民比晨矮（身高约晨的 0.7），颜色全在中间调（OKLab L 0.36~0.76，不碰晨的白发、砖红斗篷），
  色度低于晨的斗篷；白天的芦苇地（很亮）和夜里的紫色云镇（很暗）都能站住。
- 画法：xiao-oscar 极简派。不描边、硬边、没有半透明；每块料子三档（光从左上来：亮面偏暖、暗面偏冷），
  褶子是斜的暗楔；脸只有两只眼睛、一点腮红，说话时一格嘴。
- 动画一律 100ms 一帧；所有帧同一块画布，待机、说话时脚底不动。图里朝右，朝左引擎翻转。

谁在哪（data/story_final.json）：
- passerby：结局一芦苇地（白天），在大象旁边告诉晨别把包放太近，会笑（laugh）。
- resident：结局二芦苇地（白天到傍晚），陪晨坐下（sit，坐在草地上），第二天帮忙扶机翼（lift）。
- townsfolk：结局三风帆小镇（夜里），带晨去喷泉、走到长椅坐下（sit，跳上长椅：长椅座面比脚底高 13 像素）。
- crowd：芦苇地（结局二）和小镇（结局三）都有，一群四个人，整组一张图。

输出 art/characters/<id>/<id>.png（横排）+ <id>.json（docs/river_rooms_contract.md 第 2 节的格式，npc_generic.gd 读）。
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
from oscarkit.palette import from_lch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FW, FH = 48, 64
FOOT = (22, 61)                 # 脚底那一行（踩在地面最上面一行上，和晨一样）
LIGHT = (-0.72, -0.69)          # 指向光：左上


def col(L, C, h):
    return from_lch(max(0.05, min(0.95, L)), max(0.0, C), h)


def ramp3(L, C, h, step=0.065):
    """一块料子三档（暗、中、亮）：亮面偏暖（色相往 70° 靠一点）、暗面偏冷（往 280° 靠一点）。"""
    def toward(h0, target, k):
        d = (target - h0 + 540) % 360 - 180
        return h0 + d * k
    return (col(L - step, C * 0.92, toward(h, 280, 0.12)), col(L, C, h), col(L + step * 0.85, C * 1.04, toward(h, 70, 0.1)))


# ============================================================ 画图的小工具
def blank():
    return np.zeros((FH, FW), bool)


def m_poly(pts):
    return Canvas(FW, FH).poly([(float(x), float(y)) for x, y in pts])


def m_ell(cx, cy, rx, ry):
    yy, xx = np.mgrid[0:FH, 0:FW]
    return ((xx + 0.5 - cx) / rx) ** 2 + ((yy + 0.5 - cy) / ry) ** 2 <= 1.0


def m_limb(p0, p1, w):
    """两头圆的带子（胳膊、腿）。w = 宽。"""
    m = blank()
    (x0, y0), (x1, y1) = p0, p1
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 3) + 2
    r = w / 2.0
    yy, xx = np.mgrid[0:FH, 0:FW]
    for t in np.linspace(0, 1, n):
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        m |= (xx + 0.5 - x) ** 2 + (yy + 0.5 - y) ** 2 <= r * r
    return m


def m_line(pts):
    """连续的 1 像素线（Bresenham，拐角边相邻）。"""
    c = Canvas(FW, FH)
    m = blank()
    for p, q in zip(pts, pts[1:]):
        m |= c.line(int(round(p[0])), int(round(p[1])), int(round(q[0])), int(round(q[1])))
    return _edge_connect(m)


def _edge_connect(m):
    """只在角上相接的两格之间补一格，让线边相邻（作者 10-31：竖线拐弯处要边相邻）。"""
    out = m.copy()
    H, W = m.shape
    for y in range(H - 1):
        for x in range(W):
            if not m[y, x]:
                continue
            for dx in (-1, 1):
                x2 = x + dx
                if 0 <= x2 < W and m[y + 1, x2] and not m[y + 1, x] and not m[y, x2]:
                    out[y + 1, x] = True
    return out


def planes(c: Canvas, m, rp, cut=(-0.3, 0.3), light=LIGHT, center=None):
    """光从左上来，把一块 mask 用两条直线分成暗 / 中 / 亮三大块（块边是直的，像奥斯卡的光面）。"""
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return
    cx, cy = center if center is not None else (xs.mean(), ys.mean())
    p = (xs - cx) * light[0] + (ys - cy) * light[1]
    s = max(1e-6, np.abs(p).max())
    p = p / s
    for y, x, v in zip(ys, xs, p):
        c.put(x, y, rp[2] if v > cut[1] else (rp[0] if v < cut[0] else rp[1]))


def fill(c: Canvas, m, color):
    c.fill_mask(m, color) if m.any() else None


def wedge(c: Canvas, keep, pts, color):
    """一条暗楔（褶子）：只画在 keep 里面。"""
    m = m_poly(pts) & keep
    fill(c, m, color)


def lerp(a, b, t):
    return a + (b - a) * t


# ============================================================ 一个人：姿势 → 一帧
POSE = dict(
    lift=0,            # 整个人离地多少（跳上长椅）
    squash=0,          # 身子往下压几格（呼吸、蹲）
    lean=0.0,          # 身子前倾（正 = 往前 / 右），像素：头顶相对脚底往前挪多少
    head=(0, 0),       # 头再挪一点
    feet=((-2, 0), (2, 0)),   # 远脚、近脚：(dx, 抬高)
    arms=((-20, 0), (20, 0)), # 远臂、近臂：(肩角度, 肘再弯) 角度 0 = 竖直向下，正 = 往前
    eyes="open",       # open / blink / happy / look_up
    mouth=0,           # 0 闭、1 张一点、2 大笑
    sit=None,          # None / "ground" / "bench"
    sway=0.0,          # 配件（芦苇、围巾、帽尖）的摆动相位
    shake=0,           # 笑的时候肩膀抖
)


class Folk:
    """一个居民的身形和行头。子类只改尺寸、颜色和 accessories。"""
    head_r = (7.5, 7.0)
    body_h = 14
    body_top = 8
    body_bot = 15
    leg = 5
    arm_len = 7.5
    skin = (0.72, 0.04, 70)
    cloth = (0.52, 0.04, 140)
    legs = (0.40, 0.02, 60)
    shoe = (0.34, 0.02, 50)
    eye = col(0.27, 0.025, 285)
    blush = col(0.66, 0.075, 18)
    mouth_c = col(0.40, 0.06, 20)

    def __init__(self):
        self.SK = ramp3(*self.skin)
        self.CL = ramp3(*self.cloth)
        self.LG = ramp3(*self.legs, step=0.05)
        self.SH = ramp3(*self.shoe, step=0.05)

    # ---- 骨架
    def skeleton(self, p):
        fx, fy = FOOT
        fy -= p["lift"]
        sit = p["sit"]
        hip_y = fy - self.leg
        if sit == "ground":
            hip_y = fy - 1
        elif sit == "bench":
            hip_y = fy - self.leg + 1
        hem_y = hip_y + 1
        neck_y = hem_y - self.body_h + p["squash"]
        lean = p["lean"]
        hcx = fx + 1 + lean + p["head"][0] + p["shake"]
        hcy = neck_y - self.head_r[1] + 1.5 + p["head"][1]
        return dict(fx=fx, fy=fy, hip_y=hip_y, hem_y=hem_y, neck_y=neck_y, lean=lean, hc=(hcx, hcy))

    # ---- 部件
    def draw_leg(self, c, k, far, p):
        dx, up = p["feet"][0 if far else 1]
        side = -2 if far else 1
        x0 = k["fx"] + side + (0 if far else 0)
        if p["sit"] == "ground":            # 坐在地上：腿往前伸，脚尖朝上
            hy = k["hip_y"]
            foot = (k["fx"] + 9 + (0 if far else 2) + dx, k["fy"] - 1 - up)
            m = m_limb((x0 + 1, hy), foot, 3)
            shoe = m_ell(foot[0] + 0.8, foot[1] - 0.3, 1.6, 1.9)
        elif p["sit"] == "bench":           # 坐在长椅上：小腿往下垂，脚悬着
            hy = k["hip_y"]
            knee = (k["fx"] + 4 + (0 if far else 1), hy)
            foot = (knee[0] + 1 + dx, hy + 4 - up)
            m = m_limb((x0 + 1, hy - 1), knee, 3) | m_limb(knee, foot, 2.6)
            shoe = m_ell(foot[0] + 0.9, foot[1] + 0.3, 1.8, 1.2)
        else:
            top = (x0 + 0.5, k["hip_y"] - 1)
            foot = (x0 + 0.5 + dx, k["fy"] - up)
            m = m_limb(top, (foot[0], foot[1] - 1.2), 2.6)
            shoe = m_ell(foot[0] + 0.9, foot[1] - 0.2, 1.9, 1.15)
        rp = self.LG if not far else tuple(col_shift(x, -0.05) for x in self.LG)
        planes(c, m & ~shoe, rp)
        sp = self.SH if not far else tuple(col_shift(x, -0.04) for x in self.SH)
        planes(c, shoe, sp, cut=(-0.1, 0.45))

    def body_mask(self, k, p):
        nx = k["fx"] + 1 + k["lean"] * 0.6 + p["shake"]
        tw, bw = self.body_top, self.body_bot
        ny, hy = k["neck_y"], k["hem_y"]
        hx = k["fx"] + 0.5 + (2.5 if p["sit"] == "ground" else 0)
        if p["sit"] == "bench":
            hx += 1.5
        pts = [(nx - tw / 2, ny), (nx + tw / 2, ny), (hx + bw / 2, hy), (hx - bw / 2, hy)]
        m = m_poly(pts) | m_ell(nx, ny + 2.2, tw / 2 + 1.0, 2.8)
        return m, (nx, ny), (hx, hy)

    def shoulder(self, k, p, far):
        nx = k["fx"] + 1 + k["lean"] * 0.6 + p["shake"]
        return (nx + (-2.5 if far else 1.5), k["neck_y"] + 2.5)

    def draw_arm(self, c, k, p, far):
        ang, bend = p["arms"][0 if far else 1]
        s = self.shoulder(k, p, far)
        a = math.radians(ang)
        L = self.arm_len
        e = (s[0] + L * 0.55 * math.sin(a), s[1] + L * 0.55 * math.cos(a))
        a2 = a + math.radians(bend)
        h = (e[0] + L * 0.5 * math.sin(a2), e[1] + L * 0.5 * math.cos(a2))
        m = m_limb(s, e, 3.0) | m_limb(e, h, 2.7)
        rp = self.sleeve_ramp() if not far else tuple(col_shift(x, -0.06) for x in self.sleeve_ramp())
        planes(c, m, rp, cut=(-0.2, 0.35))
        hm = m_ell(h[0] + 0.2, h[1] + 0.4, 1.5, 1.5)
        sk = self.SK if not far else tuple(col_shift(x, -0.07) for x in self.SK)
        planes(c, hm, sk, cut=(-0.2, 0.4))
        return h, m

    def sleeve_ramp(self):
        return self.CL

    def draw_head(self, c, k, p):
        cx, cy = k["hc"]
        rx, ry = self.head_r
        m = m_ell(cx, cy, rx, ry)
        planes(c, m, self.SK, cut=(-0.36, 0.28), center=(cx + 0.5, cy + 0.3))
        self.face(c, k, p)
        return m

    def face(self, c, k, p):
        cx, cy = k["hc"]
        ex1, ex2, ey = int(round(cx + 1.5)), int(round(cx + 4.5)), int(round(cy + 0.2))
        e = p["eyes"]
        if e == "open":
            for ex in (ex1, ex2):
                c.put(ex, ey, self.eye)
                c.put(ex, ey + 1, self.eye)
        elif e == "look_up":
            for ex in (ex1, ex2):
                c.put(ex, ey - 1, self.eye)
                c.put(ex, ey, self.eye)
        elif e == "blink":
            for ex in (ex1, ex2):
                c.put(ex, ey + 1, self.eye)
        elif e == "happy":                  # 眯成两道弯（侧脸：一道往后下的短斜）
            for ex in (ex1, ex2):
                c.put(ex, ey, self.eye)
                c.put(ex - 1, ey + 1, self.eye)
        c.put(ex2 - 1, ey + 2, self.blush)  # 腮红（眼睛下面一格）
        c.put(ex2 + 1, ey + 2, self.blush)
        mx, my = ex2 - 0, ey + 3
        if p["mouth"] == 1:
            c.put(mx, my, self.mouth_c)
        elif p["mouth"] == 2:
            c.put(mx, my, self.mouth_c)
            c.put(mx - 1, my, self.mouth_c)
            c.put(mx, my + 1, self.mouth_c)

    def draw_body(self, c, k, p):
        m, n, h = self.body_mask(k, p)
        planes(c, m, self.CL, cut=(-0.25, 0.38))
        return m, n, h

    # ---- 子类加东西（背后 / 衣服上 / 头上 / 手里）
    def back(self, c, k, p):
        pass

    def over(self, c, k, p, body):
        pass

    def hat(self, c, k, p, head):
        pass

    def front(self, c, k, p, hand):
        pass

    def frame(self, **pose):
        p = dict(POSE)
        p.update(pose)
        k = self.skeleton(p)
        c = Canvas(FW, FH)
        self.back(c, k, p)
        self.draw_arm(c, k, p, far=True)
        self.draw_leg(c, k, True, p)
        self.draw_leg(c, k, False, p)
        body = self.draw_body(c, k, p)
        self.over(c, k, p, body)
        head = self.draw_head(c, k, p)
        self.hat(c, k, p, head)
        hand, _ = self.draw_arm(c, k, p, far=False)
        self.front(c, k, p, hand)
        return c.a


def col_shift(rgb, dL):
    """整体暗 / 亮一点（远侧的胳膊、腿）：在 OKLab 里只动 L。"""
    from oscarkit.palette import oklab_to_srgb
    lab = srgb_to_oklab(rgb)
    lab[0] = max(0.05, lab[0] + dL)
    return tuple(int(v) for v in oklab_to_srgb(np.array([lab]))[0])


def srgb_to_oklab(rgb):
    r, g, b = [v / 255 for v in rgb[:3]]
    f = lambda u: u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4
    r, g, b = f(r), f(g), f(b)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    return [0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s]


# ============================================================ 路过的人：拾苇的
class Passerby(Folk):
    """芦苇地上割芦苇的人：宽平的草帽、灰绿罩衫、腰上一条靛蓝布带，背后一捆芦苇（穗子随风摆）。
    个子最矮、肚子圆，笑起来往后仰。"""
    head_r = (7.5, 7.0)
    body_h = 13
    body_top = 9
    body_bot = 16
    leg = 5
    arm_len = 8.5
    skin = (0.70, 0.045, 68)
    cloth = (0.56, 0.042, 142)
    legs = (0.51, 0.02, 70)
    shoe = (0.45, 0.03, 55)
    straw = (0.66, 0.065, 86)
    sash = (0.47, 0.05, 268)
    stalk = (0.58, 0.06, 98)
    plume = (0.70, 0.045, 84)

    def __init__(self):
        super().__init__()
        self.ST = ramp3(*self.straw)
        self.SA = ramp3(*self.sash, step=0.05)
        self.SK2 = ramp3(*self.stalk, step=0.05)
        self.PL = ramp3(*self.plume, step=0.05)

    def back(self, c, k, p):
        """背后斜插一捆芦苇：从左肩后面往左上斜出去，三根杆子 + 穗子。"""
        bx, by = k["fx"] - 3 + k["lean"] * 0.6 + p["shake"], k["neck_y"] + 7
        sw = p["sway"]
        tips = []
        for i, (ln, ang) in enumerate([(19, -26), (17, -18), (15, -33)]):
            a = math.radians(ang + 2.5 * math.sin(sw + i * 0.9))
            tx, ty = bx + ln * math.sin(a), by - ln * math.cos(a)
            m = m_line([(bx + i * 0.6, by), (tx, ty)])
            fill(c, m, self.SK2[1] if i != 2 else self.SK2[0])
            tips.append((tx, ty, a, i))
        for tx, ty, a, i in tips:            # 穗子：沿着杆子的方向、往下垂一点的一小团
            d = (math.sin(a), -math.cos(a))
            pm = m_limb((tx - d[0] * 1.5, ty - d[1] * 1.5), (tx + d[0] * 3.0 - 1.4, ty + d[1] * 3.0 + 1.2), 2.8)
            planes(c, pm, self.PL if i != 2 else tuple(col_shift(x, -0.05) for x in self.PL), cut=(-0.1, 0.3))
        # 捆绳（布带同色）在背后一格露出来
        c.put(int(round(bx - 1)), int(round(by - 3)), self.SA[1])

    def over(self, c, k, p, body):
        m, n, h = body
        # 腰带：靛蓝布条，绕一圈，在身前打结垂下一截
        wy = int(round(lerp(n[1], h[1], 0.62)))
        band = m & (np.mgrid[0:FH, 0:FW][0] >= wy) & (np.mgrid[0:FH, 0:FW][0] <= wy + 1)
        planes(c, band, self.SA, cut=(-0.2, 0.5))
        ys, xs = np.nonzero(band)
        if len(xs):
            kx = xs.max() - 1
            c.put(kx, wy + 2, self.SA[1])
            c.put(kx, wy + 3, self.SA[0])
            c.put(kx + 1, wy + 2, self.SA[0])
        # 罩衫的褶：一条从腰带往右下的暗楔
        wedge(c, m, [(n[0] + 1, wy + 2), (n[0] + 3, wy + 2), (h[0] + 5, h[1]), (h[0] + 2, h[1])], self.CL[0])
        # 领口：脖子下面一小块亮
        c.put(int(round(n[0])), int(n[1]), self.CL[2])
        c.put(int(round(n[0] + 1)), int(n[1]), self.CL[2])

    def hat(self, c, k, p, head):
        """宽平草帽：帽檐一长条（左边亮右边暗、前沿往下压一点），上面扁圆的帽冠，帽冠底边一圈靛蓝帽带；
        帽檐下面一行阴影落在额头上。"""
        cx, cy = k["hc"]
        yy, xx = np.mgrid[0:FH, 0:FW]
        top = cy - self.head_r[1]
        by = int(round(top + 3.0))                   # 帽檐上沿那一行
        brim = m_poly([(cx - 10.5, by + 0.3), (cx + 10.5, by), (cx + 11.8, by + 1.9), (cx - 10.2, by + 1.9)])
        crown = m_ell(cx - 0.5, by + 0.2, 6.0, 4.6) & (yy < by)
        under = m_ell(cx, cy, *self.head_r) & (yy == by + 2)
        fill(c, under, self.SK[0])
        planes(c, brim, self.ST, cut=(-0.4, 0.2))
        fill(c, brim & (yy == by + 1) & (xx > cx + 3), self.ST[0])   # 前沿的厚边背光
        planes(c, crown, self.ST, cut=(-0.25, 0.3))
        fill(c, crown & (yy == by - 1), self.SA[1])
        fill(c, crown & (yy == by - 1) & (xx < cx - 3), self.SA[2])


# ============================================================ 居民：帮晨扶机翼的
class Resident(Folk):
    """芦苇地那边的居民：个子最大、手最粗，帆布斗篷（淡灰蓝，帆的料子）用两个芥黄木扣扣着，
    额头上推着一副铜框风镜（修东西的人），斜挎一个小工具袋。"""
    head_r = (8.0, 7.5)
    body_h = 15
    body_top = 10
    body_bot = 17
    leg = 5
    arm_len = 10.0
    skin = (0.63, 0.055, 52)
    hair_c = (0.48, 0.04, 45)
    cloth = (0.58, 0.036, 232)
    legs = (0.51, 0.025, 62)
    shoe = (0.44, 0.025, 50)
    brass = (0.60, 0.07, 78)
    lens = (0.66, 0.03, 200)
    toggle = (0.64, 0.08, 86)
    bag = (0.52, 0.045, 62)

    def __init__(self):
        super().__init__()
        self.BR = ramp3(*self.brass, step=0.05)
        self.LN = ramp3(*self.lens, step=0.05)
        self.TG = ramp3(*self.toggle, step=0.05)
        self.BG = ramp3(*self.bag, step=0.05)
        self.HR = ramp3(*self.hair_c, step=0.055)

    def body_mask(self, k, p):
        """斗篷：肩膀圆、下摆宽，下摆左右各低一格（帆布的角）。"""
        m, n, h = super().body_mask(k, p)
        m |= m_poly([(h[0] - self.body_bot / 2, h[1] - 3), (h[0] - self.body_bot / 2 - 1, h[1] + 1), (h[0] - self.body_bot / 2 + 3, h[1])])
        return m, n, h

    def over(self, c, k, p, body):
        m, n, h = body
        # 斗篷的两条斜褶（暗楔 + 向光一侧亮一格的棱）
        wedge(c, m, [(n[0] + 2, n[1] + 5), (n[0] + 3.5, n[1] + 5), (h[0] + 6, h[1] + 1), (h[0] + 3.5, h[1] + 1)], self.CL[0])
        wedge(c, m, [(n[0] - 2, n[1] + 7), (n[0] - 1, n[1] + 7), (h[0] - 1, h[1] + 1), (h[0] - 3, h[1] + 1)], self.CL[0])
        ridge = m_line([(n[0] - 2.6, n[1] + 8), (h[0] - 3.8, h[1])]) & m
        fill(c, ridge, self.CL[2])
        # 工具袋的斜挎带：从右肩到左胯（袋子在 back 里，挂在身后）
        strap = m_line([(n[0] + 3, n[1] + 1), (h[0] - 5, h[1] - 4)]) & m
        fill(c, strap, self.BG[0])
        # 两颗木扣（芥黄），领口一颗、胸前一颗
        for i, dy in enumerate((2, 6)):
            x = int(round(n[0] + 2.4 + dy * 0.08))
            c.put(x, int(n[1] + dy), self.TG[2] if i == 0 else self.TG[1])

    def hat(self, c, k, p, head):
        """一头蓬松的卷发（深栗色，顶上鼓三个小包、后脑勺往下盖到耳后），风镜推在额头上：
        皮带绕过头发，前面一个铜框圆镜片（镜片反一点天光）。"""
        cx, cy = k["hc"]
        rx, ry = self.head_r
        yy, xx = np.mgrid[0:FH, 0:FW]
        top = cy - ry
        hair = m_ell(cx - 0.8, cy - 1.6, rx + 0.6, ry - 0.4)
        for bx, by_, r in ((cx - 5.0, top + 1.6, 2.6), (cx - 1.0, top + 0.3, 2.8), (cx + 3.2, top + 0.9, 2.5)):
            hair |= m_ell(bx, by_, r, r - 0.3)
        hair |= m_ell(cx - 5.2, cy + 1.5, 3.0, 4.2)                  # 后脑勺、耳后
        face = m_ell(cx + 2.4, cy + 1.6, rx - 2.3, ry - 2.6) | ((yy > cy + 1) & head)
        hair &= ~face
        planes(c, hair, self.HR, cut=(-0.3, 0.32), center=(cx - 1, cy - 2))
        # 两三处卷：比发色亮一档的小弯（只几格，不铺满）
        for (x, y) in ((cx - 5, top + 1), (cx - 1, top - 0.5), (cx - 6.5, cy - 1)):
            x, y = int(round(x)), int(round(y))
            if hair[y, x]:
                c.put(x, y, self.HR[2])
                if hair[y + 1, x + 1]:
                    c.put(x + 1, y + 1, self.HR[2])
        # 风镜皮带：头发上斜着一道
        gy = top + 3.4
        band = (hair | head) & (yy >= gy - 0.5) & (yy <= gy + 0.5) & (xx < cx + 3)
        fill(c, band, self.BG[0])
        gx = cx + 3.6
        ring = m_ell(gx, gy, 2.8, 2.5)
        fill(c, ring, self.BR[0])
        fill(c, ring & (xx + yy < gx + gy - 0.5), self.BR[2])
        fill(c, ring & (xx + yy >= gx + gy - 0.5) & (xx + yy < gx + gy + 1.5), self.BR[1])
        lens = m_ell(gx + 0.2, gy + 0.1, 1.6, 1.4)
        planes(c, lens, self.LN, cut=(-0.1, 0.35))
        c.put(int(round(gx - 0.6)), int(round(gy - 0.8)), self.LN[2])

    def back(self, c, k, p):
        """工具袋挂在左胯后面（身子挡住一半）。"""
        bx = int(round(k["fx"] - self.body_bot / 2 - 0.5))
        by = int(round(k["hem_y"] - 6))
        bagm = m_poly([(bx, by), (bx + 6, by), (bx + 6, by + 5), (bx + 0.6, by + 5)])
        planes(c, bagm, self.BG, cut=(-0.2, 0.3))
        fill(c, m_poly([(bx, by), (bx + 6, by), (bx + 6, by + 1), (bx, by + 1)]), self.BG[2])   # 袋盖
        c.put(bx + 2, by + 2, self.TG[1])                                                         # 扣

    def front(self, c, k, p, hand):
        pass


# ============================================================ 镇上的居民：带晨去喷泉的
class Townsfolk(Folk):
    """风帆小镇的人：尖尖的针织帽（像镇上的尖顶塔，帽尖一个小绒球，走路时晃），紫灰短外套，
    脖子上一条很长的帆布围巾（淡蓝，镇上帆的颜色），被风往后吹。个子细一点，动作多。"""
    head_r = (7.2, 6.8)
    body_h = 14
    body_top = 8
    body_bot = 13
    leg = 6
    arm_len = 9.0
    skin = (0.64, 0.04, 48)
    cloth = (0.43, 0.04, 300)
    legs = (0.38, 0.02, 290)
    shoe = (0.32, 0.02, 40)
    cap = (0.47, 0.055, 345)
    pom = (0.62, 0.025, 330)
    scarf = (0.55, 0.035, 222)

    def __init__(self):
        super().__init__()
        self.CP = ramp3(*self.cap)
        self.PM = ramp3(*self.pom, step=0.045)
        self.SC = ramp3(*self.scarf, step=0.055)

    def back(self, c, k, p):
        """围巾的长尾巴：从后颈往左后方飘的一条宽布（3 格宽，越往尾巴越窄），随 sway 起伏，整条连续。
        向上的那条边亮一档（天光），下面那条边暗一档。"""
        nx = k["fx"] + 1 + k["lean"] * 0.6 + p["shake"]
        ny = k["neck_y"] + 1.5
        sw = p["sway"]
        L = 13.0
        pts = []
        for i in range(14):
            t = i / 13
            x = nx - 2.5 - t * L
            y = ny + t * 2.5 + 2.6 * math.sin(sw - t * 3.0) * t
            pts.append((x, y))
        m = blank()
        for i, ((x0, y0), (x1, y1)) in enumerate(zip(pts, pts[1:])):
            m |= m_limb((x0, y0), (x1, y1), 4.6 - 2.4 * i / 13)
        fill(c, m, self.SC[1])
        yy = np.mgrid[0:FH, 0:FW][0]
        up = m & ~np.roll(m, 1, axis=0)
        dn = m & ~np.roll(m, -1, axis=0)
        fill(c, dn, self.SC[0])
        fill(c, up, self.SC[2])
        # 尾端两道短流苏：最左边两列各往下垂一格，贴着布边（边相邻，不飘）
        ys, xs = np.nonzero(m)
        x0 = xs.min()
        for x in (x0, x0 + 2):
            col_ys = ys[xs == x]
            if len(col_ys):
                c.put(x, col_ys.max() + 1, self.SC[0])

    def over(self, c, k, p, body):
        m, n, h = body
        # 外套前襟一道暗楔、下摆往右下的褶
        wedge(c, m, [(n[0] + 2, n[1] + 3), (n[0] + 3, n[1] + 3), (h[0] + 4.5, h[1] + 1), (h[0] + 3, h[1] + 1)], self.CL[0])
        # 两个口袋盖：比外套亮一档的短横（只在身前一侧）
        py = int(round(lerp(n[1], h[1], 0.7)))
        for x in range(int(round(h[0] - 1)), int(round(h[0] + 2))):
            if m[py, x]:
                c.put(x, py, self.CL[2])
        # 围巾在脖子上绕的那一圈
        ring = m_ell(n[0] + 0.5, n[1] + 0.8, self.body_top / 2 + 1.2, 1.9)
        planes(c, ring, self.SC, cut=(-0.3, 0.2))
        c.put(int(round(n[0] + 3)), int(round(n[1] + 2.5)), self.SC[1])   # 前面垂下来的一小截
        c.put(int(round(n[0] + 3)), int(round(n[1] + 3.5)), self.SC[0])

    def hat(self, c, k, p, head):
        """针织尖帽：帽口一圈翻边，帽身往后上方弯成尖，尖上一颗绒球。帽身横着有两道浅一档的针织纹（不是网格，只两道）。"""
        cx, cy = k["hc"]
        top = cy - self.head_r[1]
        sw = p["sway"]
        yy, xx = np.mgrid[0:FH, 0:FW]
        rim_y = top + 4.2
        tipx = cx - 4.5 + 1.2 * math.sin(sw)
        tipy = top - 8.5
        body = m_poly([(cx - 7.6, rim_y), (cx + 7.0, rim_y), (cx + 3.5, top - 1.5), (tipx + 1.0, tipy), (tipx - 0.8, tipy + 1), (cx - 6.0, top + 0.5)])
        body &= ~(yy > rim_y)
        planes(c, body, self.CP, cut=(-0.35, 0.3))
        for k2, frac in enumerate((0.35, 0.62)):        # 两道针织纹：连续的一行，只亮一档
            y = int(round(lerp(rim_y, tipy, frac)))
            fill(c, body & (yy == y) & (xx < cx + 2 - k2 * 3), self.CP[2])
        cuff = m_poly([(cx - 7.8, rim_y - 1.5), (cx + 7.4, rim_y - 1.5), (cx + 7.4, rim_y + 1.0), (cx - 7.8, rim_y + 1.0)]) & (head | body | m_ell(cx, cy, self.head_r[0] + 1, self.head_r[1] + 1))
        planes(c, cuff, self.CP, cut=(-0.5, 0.0))
        fill(c, cuff & (yy == int(round(rim_y - 1.5))), self.CP[2])
        pm = m_ell(tipx - 0.3, tipy - 0.6, 1.9, 1.8)
        planes(c, pm, self.PM, cut=(-0.2, 0.3))


# ============================================================ 动作（每格一个姿势；100ms 一帧）
def breathe(n=6, **kw):
    """待机：6 格一圈，身子在第 3、4 格往下沉一格；配件跟着慢慢摆。"""
    out = []
    for i in range(n):
        f = dict(kw)
        f["squash"] = kw.get("squash", 0) + (1 if i in (2, 3) else 0)
        f["sway"] = i / n * 2 * math.pi
        out.append(f)
    return out


def walk(**kw):
    """6 格：小短腿一前一后交替，脚过中间那格身子抬一格；胳膊反着摆；配件摆得快一点。"""
    out = []
    for i in range(6):
        ph = i / 6 * 2 * math.pi
        d = 2.6 * math.cos(ph)
        up_n = 1 if math.sin(ph) > 0.4 else 0
        up_f = 1 if math.sin(ph) < -0.4 else 0
        f = dict(kw)
        f["feet"] = ((round(-d), up_f), (round(d), up_n))
        f["squash"] = -1 if i in (1, 4) else 0
        f["arms"] = ((-22 - 22 * math.cos(ph), 10), (22 + 22 * math.cos(ph) + kw.get("arm_bias", 0), 10))
        f["sway"] = ph * 2
        f.pop("arm_bias", None)
        out.append(f)
    return out


def talk(**kw):
    """4 格：嘴一张一合，近手在胸前比划一下，头点一格。"""
    base = kw.get("arms", ((-20, 0), (20, 0)))
    return [dict(kw, mouth=1, arms=(base[0], (40, 50)), sway=0.0),
            dict(kw, mouth=0, arms=(base[0], (60, 55)), head=(0, 1), sway=0.8),
            dict(kw, mouth=1, arms=(base[0], (70, 40)), sway=1.6),
            dict(kw, mouth=0, arms=(base[0], (45, 50)), sway=2.4)]


def blink_cycle(idle_frames, total=24, blink_at=17):
    """待机的帧号：6 格一圈重复 4 遍（2.4 秒），第 blink_at 格换成闭眼那张（idle_frames 末尾那张）。"""
    seq = [idle_frames[i % 6] for i in range(total)]
    seq[blink_at] = idle_frames[6]
    return seq


def passerby_anims():
    A = {}
    A["idle"] = breathe(arms=((-15, 10), (25, 70)))            # 近手搭在肚子上
    A["idle_blink"] = [dict(A["idle"][4], eyes="blink")]
    A["walk"] = walk()
    A["talk"] = talk(arms=((-15, 10), (25, 70)))
    A["laugh"] = [dict(eyes="happy", mouth=1, arms=((-15, 10), (30, 75)), sway=0.3),
                  dict(eyes="happy", mouth=2, head=(-1, -1), lean=-1, arms=((-10, 10), (35, 85)), sway=0.9),
                  dict(eyes="happy", mouth=2, head=(-1, -1), lean=-1, shake=1, squash=1, arms=((-10, 10), (35, 85)), sway=1.5),
                  dict(eyes="happy", mouth=2, head=(-1, -1), lean=-1, arms=((-10, 10), (35, 85)), sway=2.1),
                  dict(eyes="happy", mouth=2, head=(-1, -1), lean=-1, shake=1, squash=1, arms=((-10, 10), (35, 85)), sway=2.7),
                  dict(eyes="happy", mouth=1, head=(0, 0), arms=((-15, 10), (30, 75)), sway=3.3),
                  dict(eyes="happy", mouth=0, arms=((-15, 10), (25, 70)), sway=3.9)]
    A["point"] = [dict(arms=((-15, 10), (60, 0)), sway=0.4), dict(arms=((-15, 10), (85, -5)), mouth=1, sway=0.8),
                  dict(arms=((-15, 10), (95, -10)), mouth=0, sway=1.2), dict(arms=((-15, 10), (95, -10)), mouth=0, sway=1.6)]
    A["nod"] = [dict(arms=((-15, 10), (25, 70)), head=(0, 1)), dict(arms=((-15, 10), (25, 70)), head=(1, 2), squash=1),
                dict(arms=((-15, 10), (25, 70)), head=(0, 1)), dict(arms=((-15, 10), (25, 70)))]
    meta = dict(loop={"idle", "walk", "talk"}, hold={"point"},
                alias={"smile": "laugh", "chuckle": "laugh", "look": "idle", "stand": "idle", "wave": "point", "give": "point"})
    return A, meta


def resident_anims():
    A = {}
    A["idle"] = breathe(arms=((-12, 5), (12, 8)))
    A["idle_blink"] = [dict(A["idle"][4], eyes="blink")]
    A["walk"] = walk()
    A["talk"] = talk(arms=((-12, 5), (12, 8)))
    # 坐下：膝盖弯、往下蹲、一屁股坐在草地上、腿伸出去，手撑在身后
    A["sit"] = [dict(squash=1, feet=((0, 0), (1, 0)), arms=((-20, 5), (20, 10))),
                dict(squash=3, lean=-1, feet=((0, 0), (2, 0)), arms=((-35, 5), (30, 10))),
                dict(sit="ground", squash=2, lean=-2, feet=((-1, 1), (-1, 1)), arms=((-45, -10), (-10, 20))),
                dict(sit="ground", squash=1, lean=-1, arms=((-40, -10), (-20, 10))),
                dict(sit="ground", squash=0, lean=-1, arms=((-40, -10), (-20, 10)))]
    A["sit_idle"] = [dict(sit="ground", lean=-1, arms=((-40, -10), (-20, 10)), squash=q) for q in (0, 0, 0, 1, 1, 1)]   # 坐着慢慢喘气
    # 扶机翼：先蹲一下、两手往前上方托起来，踮脚，最后一格停着（hold），抬头看着托住的地方
    up = ((105, -10), (115, -10))
    A["lift"] = [dict(squash=1, arms=((-20, 10), (20, 30))),
                 dict(squash=2, lean=1, arms=((50, 40), (60, 40))),
                 dict(squash=0, lean=1, arms=((85, 10), (95, 10)), eyes="look_up"),
                 dict(squash=-1, lift=1, lean=1, arms=up, eyes="look_up"),
                 dict(squash=0, lift=1, lean=1, arms=up, eyes="look_up", mouth=1)]
    A["nod"] = [dict(arms=((-12, 5), (12, 8)), head=(0, 1)), dict(arms=((-12, 5), (12, 8)), head=(1, 2), squash=1),
                dict(arms=((-12, 5), (12, 8)), head=(0, 1)), dict(arms=((-12, 5), (12, 8)))]
    A["wave"] = [dict(arms=((-12, 5), (95, 40)), mouth=1), dict(arms=((-12, 5), (100, 60))),
                 dict(arms=((-12, 5), (95, 40)), mouth=1), dict(arms=((-12, 5), (100, 60))), dict(arms=((-12, 5), (12, 8)))]
    meta = dict(loop={"idle", "walk", "talk", "sit_idle"}, hold={"lift"}, then={"sit": "sit_idle"},
                alias={"hold": "lift", "help": "lift", "look": "idle", "stand": "idle", "smile": "nod", "laugh": "nod", "give": "wave"})
    return A, meta


BENCH = 13            # 长椅座面比脚底高几格（art/cloud_town/town_main.png：座面 215 行，地面 228）


def townsfolk_anims():
    A = {}
    A["idle"] = breathe(arms=((-15, 10), (15, 15)))
    A["idle_blink"] = [dict(A["idle"][4], eyes="blink")]
    A["walk"] = walk()
    A["talk"] = talk(arms=((-15, 10), (15, 15)))
    # 顺着我的手看：胳膊抬起来往前上方指，停住
    A["point"] = [dict(arms=((-15, 10), (60, 10)), mouth=1, sway=0.5), dict(arms=((-15, 10), (100, 0)), sway=1.0, lean=1),
                  dict(arms=((-15, 10), (115, -5)), sway=1.5, lean=1), dict(arms=((-15, 10), (115, -5)), sway=2.0, lean=1)]
    # 坐长椅：小个子够不着，往上一跳坐上去（离地 0 → 6 → 11 → 14 → 13），腿垂下来晃
    A["sit"] = [dict(squash=2, arms=((-30, 10), (30, 10)), sway=0.4),
                dict(lift=6, squash=-1, arms=((-60, 20), (60, 20)), feet=((0, 1), (1, 1)), sway=1.0),
                dict(lift=11, squash=-1, arms=((-50, 20), (50, 20)), feet=((0, 2), (0, 2)), sway=1.6),
                dict(lift=BENCH + 1, sit="bench", squash=0, arms=((-30, 30), (30, 30)), sway=2.2),
                dict(lift=BENCH, sit="bench", squash=1, arms=((-10, 40), (10, 50)), sway=2.8),
                dict(lift=BENCH, sit="bench", squash=0, arms=((-10, 40), (10, 50)), sway=3.4)]
    A["sit_idle"] = [dict(lift=BENCH, sit="bench", arms=((-10, 40), (10, 50)), feet=((0, 0), (fx, 0)), sway=s)
                     for fx, s in ((0, 0.0), (1, 0.8), (1, 1.6), (0, 2.4))]
    A["wave"] = [dict(arms=((-15, 10), (95, 40)), mouth=1, sway=0.4), dict(arms=((-15, 10), (100, 60)), sway=0.9),
                 dict(arms=((-15, 10), (95, 40)), mouth=1, sway=1.4), dict(arms=((-15, 10), (100, 60)), sway=1.9),
                 dict(arms=((-15, 10), (15, 15)), sway=2.4)]
    A["laugh"] = [dict(eyes="happy", mouth=1, arms=((-15, 10), (30, 60))),
                  dict(eyes="happy", mouth=2, head=(-1, -1), arms=((-15, 10), (40, 70)), sway=0.8),
                  dict(eyes="happy", mouth=2, head=(-1, -1), shake=1, squash=1, arms=((-15, 10), (40, 70)), sway=1.6),
                  dict(eyes="happy", mouth=2, head=(-1, -1), arms=((-15, 10), (40, 70)), sway=2.4),
                  dict(eyes="happy", mouth=0, arms=((-15, 10), (15, 15)), sway=3.2)]
    A["nod"] = [dict(arms=((-15, 10), (15, 15)), head=(0, 1)), dict(arms=((-15, 10), (15, 15)), head=(1, 2), squash=1),
                dict(arms=((-15, 10), (15, 15)), head=(0, 1)), dict(arms=((-15, 10), (15, 15)))]
    meta = dict(loop={"idle", "walk", "talk", "sit_idle"}, hold={"point"}, then={"sit": "sit_idle"},
                no_shadow={"sit", "sit_idle"},
                alias={"look": "idle", "stand": "idle", "smile": "laugh", "give": "point", "show": "point", "guide": "point"})
    return A, meta


# ============================================================ 周围的人：一群四个
class Plain(Folk):
    """人群里的人：只要身形（没有背后的东西），帽子 / 头发按 hat_of 借别人的。"""
    def __init__(self, src, **kw):
        self.src = src
        for k2, v in kw.items():
            setattr(self, k2, v)
        super().__init__()
        for k2 in ("ST", "SA", "CP", "PM", "SC", "HR", "BR", "LN", "BG", "TG"):
            if hasattr(src, k2):
                setattr(self, k2, getattr(src, k2))

    def hat(self, c, k, p, head):
        if self.src is not None:
            type(self.src).hat(self, c, k, p, head)


CROWD_FW = 100
CROWD_FOOT = (50, 61)
# 四个人：(身形来源, 改的尺寸, 在组里的 x, 朝向, 明暗偏移, 相位)
CROWD = [
    (Townsfolk, dict(body_h=15, leg=6), -27, 1, -0.07, 0),
    (Passerby, dict(body_h=13), -10, -1, 0.04, 2),       # 转过去跟旁边的人说话
    (Resident, dict(), 8, 1, -0.04, 4),
    (Folk, dict(head_r=(6.8, 6.4), body_h=11, body_top=7, body_bot=12, leg=4), 26, 1, 0.06, 1),   # 小孩，光头顶一撮
]
CROWD_TONE = {"": (0.56, 0.028, 285),       # 白天（芦苇地）：淡紫灰，像隔着一点雾
              "cloud": (0.40, 0.036, 318)}  # 夜里（云镇）：暗一截的紫红灰，比地面亮一点、比晨暗得多


def crowd_recolor(a, dL, tone):
    """把一个人压成剪影的一条窄色阶：按原来的明暗排成 4 档，色相统一。"""
    out = a.copy()
    L0, C0, h0 = tone
    steps = [col(L0 - 0.10 + dL, C0 * 0.9, h0 + 8), col(L0 - 0.04 + dL, C0, h0), col(L0 + 0.03 + dL, C0, h0 - 6),
             col(L0 + 0.09 + dL, C0 * 1.1, h0 - 14)]
    ys, xs = np.nonzero(a[..., 3])
    for y, x in zip(ys, xs):
        L = srgb_to_oklab(a[y, x])[0]
        i = 0 if L < 0.40 else 1 if L < 0.52 else 2 if L < 0.66 else 3
        out[y, x, :3] = steps[i]
    return out


def crowd_frame(member_poses, tone):
    c = np.zeros((FH, CROWD_FW, 4), np.uint8)
    for (cls, kw, ox, face, dL, ph), pose in zip(CROWD, member_poses):
        src = cls() if cls is not Folk else None
        f = Plain(src, **kw)
        if cls is Folk:
            f.hat = lambda c2, k, p, head: _tuft(f, c2, k, p, head)
        img = crowd_recolor(f.frame(**pose), dL, tone)
        if face < 0:
            img = img[:, ::-1]
            x0 = CROWD_FOOT[0] + ox - (FW - 1 - FOOT[0])
        else:
            x0 = CROWD_FOOT[0] + ox - FOOT[0]
        m = img[..., 3] > 0
        sub = c[:, max(0, x0):x0 + FW]
        mm = m[:, max(0, -x0):max(0, -x0) + sub.shape[1]]
        sub[mm] = img[:, max(0, -x0):max(0, -x0) + sub.shape[1]][mm]
    return c


def _tuft(f, c, k, p, head):
    """小孩头顶翘起来的一撮（和身子同色，只是一个小弯）。"""
    cx, cy = k["hc"]
    top = cy - f.head_r[1]
    sw = 1 if math.sin(p["sway"]) > 0.3 else 0
    x0 = int(round(cx - 1))
    col_ys = np.nonzero(head[:, x0])[0]
    y0 = int(col_ys.min()) - 1 if len(col_ys) else int(round(top))
    for (x, y) in ((x0, y0), (x0, y0 - 1), (x0, y0 - 2), (x0 + 1 - 2 * sw, y0 - 2)):     # 尖往前 / 往后弯
        c.put(x, y, f.SK[2])


def crowd_anims():
    """idle：四个人各按自己的相位呼吸（6 格一圈），第 17 格旁边那个小孩眨眼；
    talk：左边的人比划、第二个人点头、大个子抬手往前指、小孩踮脚。"""
    base = [dict(arms=((-15, 10), (15, 15))), dict(arms=((-15, 10), (25, 70))), dict(arms=((-12, 5), (12, 8))),
            dict(arms=((-10, 5), (10, 10)))]
    idle = []
    for i in range(6):
        poses = []
        for (cls, kw, ox, face, dL, ph), b in zip(CROWD, base):
            j = (i + ph) % 6
            poses.append(dict(b, squash=1 if j in (2, 3) else 0, sway=j / 6 * 2 * math.pi))
        idle.append(poses)
    blink = [dict(pp) for pp in idle[4]]
    blink[3]["eyes"] = "blink"
    blink[0]["eyes"] = "blink"
    talk = []
    for i in range(4):
        t0 = talk_pose = None
        poses = [dict(base[0], mouth=i % 2, arms=((-15, 10), ((40, 50), (60, 55), (70, 40), (45, 50))[i]), sway=i * 0.8),
                 dict(base[1], head=((0, 1), (1, 2), (0, 1), (0, 0))[i], squash=1 if i == 1 else 0, mouth=1 if i == 2 else 0),
                 dict(base[2], arms=((-12, 5), (90 + 10 * (i % 2), -5)), mouth=1 if i in (0, 3) else 0),
                 dict(base[3], lift=1 if i in (1, 2) else 0, eyes="look_up", feet=((0, 0), (0, 0)))]
        talk.append(poses)
    return {"idle": idle, "idle_blink": [blink], "talk": talk}


def build_crowd(out_root: Path):
    anims = crowd_anims()
    frames, night, idx = [], [], {}
    for name, seq in anims.items():
        idx[name] = []
        for poses in seq:
            idx[name].append(len(frames))
            frames.append(crowd_frame(poses, CROWD_TONE[""]))
            night.append(crowd_frame(poses, CROWD_TONE["cloud"]))
    meta_anims = {"idle": {"frames": blink_cycle(idx["idle"] + idx["idle_blink"]), "loop": True},
                  "talk": {"frames": idx["talk"], "loop": True}}
    out = out_root / "crowd"
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.concatenate(frames, axis=1)).save(out / "crowd.png")
    Image.fromarray(np.concatenate(night, axis=1)).save(out / "crowd_night.png")
    j = {"_comment": "tools/cloud_folk_art.py 生成，别手改（要改先改脚本）。云层星的「周围的人」：四个人一张图（剪影，一条窄色阶），"
                     "只出现 / 消失、不走路（walk 退回待机）。图里朝右，朝左引擎翻转；100ms 一帧。"
                     "forms：白天（芦苇地）用默认的淡紫灰；放进 env 是 cloud 的房间（夜里的云镇）时 story_runner 换成 cloud 那套（暗一截）。"
                     "pass = 不占路：是背景里站着的一群人，晨和别人可以站在他们前面（不然 100 宽的一格会把人推出 70 像素）。",
         "form": "", "env_forms": True, "forms": {"cloud": {"sheet": "crowd_night.png"}},
         "frame": [CROWD_FW, FH], "sheet": "crowd.png", "anchor": list(CROWD_FOOT), "faces": "right", "ms": 100, "tint": False,
         "head": 52, "speed": 24, "shadow_w": 60, "pass": True, "color": "#8a8296", "anims": meta_anims,
         "alias": {"walk": "idle", "look": "idle", "point": "talk", "laugh": "talk", "nod": "talk", "cheer": "talk"}}
    (out / "crowd.json").write_text(json.dumps(j, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return frames, j


CHARS = {
    "passerby": (Passerby, passerby_anims, dict(head=40, speed=24, color="#8a9a7c")),
    "resident": (Resident, resident_anims, dict(head=42, speed=28, color="#8c98a8")),
    "townsfolk": (Townsfolk, townsfolk_anims, dict(head=50, speed=30, color="#7c6c84")),
}


def build_char(cid, out_root: Path):
    cls, fn, extra = CHARS[cid]
    folk = cls()
    anims, meta = fn()
    frames, cache, meta_anims = [], {}, {}

    def add(pose):
        key = json.dumps(pose, sort_keys=True, default=str)
        if key not in cache:
            cache[key] = len(frames)
            frames.append(folk.frame(**pose))
        return cache[key]

    idx = {name: [add(p) for p in poses] for name, poses in anims.items()}
    for name, ids in idx.items():
        if name == "idle_blink":
            continue
        d = {"frames": ids}
        if name == "idle":
            d["frames"] = blink_cycle(ids + idx["idle_blink"])
        if name in meta["loop"]:
            d["loop"] = True
        elif name not in ("idle", "walk", "talk"):
            d["loop"] = False
        if name in meta["hold"]:
            d["hold"] = True
        if name in meta.get("then", {}):
            d["then"] = meta["then"][name]
        if name in meta.get("no_shadow", ()):
            d["shadow"] = False
        meta_anims[name] = d
    sheet = np.concatenate(frames, axis=1)
    out = out_root / cid
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet).save(out / f"{cid}.png")
    j = {"_comment": f"tools/cloud_folk_art.py 生成，别手改（要改先改脚本）。云层星的居民，图里朝右，朝左引擎翻转；100ms 一帧。",
         "frame": [FW, FH], "sheet": f"{cid}.png", "anchor": list(FOOT), "faces": "right", "ms": 100, "tint": False,
         **extra, "anims": meta_anims, "alias": meta["alias"]}
    (out / f"{cid}.json").write_text(json.dumps(j, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return frames, j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "art" / "characters"))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    for cid in CHARS:
        if a.only and cid not in a.only.split(","):
            continue
        frames, j = build_char(cid, Path(a.out))
        print(cid, len(frames), "frames", sorted(j["anims"]))
    if not a.only or "crowd" in a.only.split(","):
        frames, j = build_crowd(Path(a.out))
        print("crowd", len(frames), "frames", sorted(j["anims"]))


if __name__ == "__main__":
    main()
