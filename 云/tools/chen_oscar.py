"""主角「晨」重做：三版候选造型（A / B / C），小奥斯卡（Oscar 极简派）画法，每版 idle 4 帧 + 跑步 8 帧。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/chen_oscar.py [--preview 目录]

  A 围巾：大圆头 + 一根天线 + 一条很长的珊瑚红围巾（跑起来拖在身后）。暖白 + 珊瑚红。
  B 帽兜：高尖帽兜的小斗篷，脸藏在帽兜阴影里只露两点琥珀色的眼睛，背上斜背一只地图筒。冷白（淡紫影）+ 琥珀。
  C 长耳：一整颗蛋形的小外星生物，头顶两根软耳朵（尖往后耷拉），背一只铁锈红背包，包口露出一角地图。柠檬黄 + 铁锈红。

输出 art/characters/chen_candidates/<a|b|c>/：
  chen.png + chen.json   一行横排精灵表（Aseprite json-array，frameTags 分 run / idle），帧 40×42，
                         脚底锚点 (20,41)，美术朝右。0~7 = run，8~11 = idle。
  直接能接到 scripts/chen.gd 顶部「精灵配置」：SHEET 换成这张图，ANIMS 换成脚本最后打印的那几行。
--preview 目录：再出 candidates.png（三版并排放大 4 倍）、run_a/b/c.gif（放大 4 倍）、
                on_scenes.png（贴进森林 / 河岸 / 水底 / 云星截图，1 倍贴、整体放大 3 倍；截图要先拍好，见 SCENES）。

跑步怎么做到「不奇怪」：
  - 腿是两节（大腿 + 小腿）的反向运动学，膝盖朝前弯；每只脚走同一条轨迹，两只脚差半圈。
  - 着地的脚每帧在画布里往后退正好 3 像素（RUN_FOOT 的前 4 帧：+4 → +1 → −2 → −5），chen.gd 每换一帧身体前进 3，
    所以着地的脚在世界里一像素不动，不打滑。离地的 4 帧：往后上踢（−6，抬 2）→ 收膝（−3，抬 4）→ 往前摆（+1，抬 4）
    → 前伸（+5，抬 2）→ 落地（+4）。
  - 身体随步子上下起伏（落地后压低 1，蹬地时抬高 1），跑步时整个人往前倾 1 像素，手臂和同侧腿反着摆。
  - 围巾 / 帽兜尖 / 长耳朵 / 下摆是「跟随」部件：按相位延迟的正弦波摆，比身体晚半拍。
待机：脚不动，头 / 上身每隔一帧抬 1 像素（呼吸），跟随部件慢慢摆。没有随机，所有帧同一套颜色。
上色：每个部件一条窄色阶（OKLab，亮端偏暖、暗端偏冷），按「光从上前方来」的球面 / 柱面法线分档，不描边、硬边。
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.anim import write_sheet  # noqa: E402
from oscarkit.checks import check_animation, check_image, report  # noqa: E402
from oscarkit.palette import from_lch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "characters" / "chen_candidates"

W, H = 40, 42
FOOT = (20, 41)
GROUND = 41                       # 脚底那一行

# 跑步：近腿的脚每帧相对胯部的 (x, 抬起高度)。远腿 = 差 4 帧。
RUN_FOOT = [(4, 0), (1, 0), (-2, 0), (-5, 0), (-6, 2), (-3, 4), (1, 4), (5, 2)]
RUN_BOB = [0, 1, 0, -1, 0, 1, 0, -1]          # 胯部上下（+ = 往下压）
RUN_STEP = [3] * 8                             # 每换一帧前进几像素（着地的脚往后退 3）
RUN_MS = 80                                    # 3 像素 / 80ms = 37.5 像素/秒（旧晨 40）
IDLE_MS = 220
IDLE_N = 4


def lch(L, C, h):
    return from_lch(L, C, h)


def ramp_lch(Ls, C, h, warm=8.0):
    """暗 → 亮。亮端色相往暖（黄）偏、暗端往冷偏；两头的色度稍低。"""
    n = len(Ls)
    out = []
    for i, L in enumerate(Ls):
        t = i / (n - 1) - 0.5
        hh = h + warm * t * 2 * (1 if ((90 - h + 540) % 360 - 180) > 0 else -1)
        out.append(lch(L, C * (1 - 0.3 * (2 * abs(t)) ** 2), hh))
    return out


# ============================================================ 画布和图元（全部整像素，硬边）

class Fig:
    def __init__(self):
        self.a = np.zeros((H, W, 4), np.uint8)

    def paint(self, m, col):
        self.a[m] = (*col, 255)

    def paint_idx(self, m, idx, ramp):
        for i, c in enumerate(ramp):
            sel = m & (idx == i)
            self.a[sel] = (*c, 255)

    def erase(self, m):
        self.a[m] = 0

    def put(self, x, y, col):
        if 0 <= x < W and 0 <= y < H:
            self.a[y, x] = (*col, 255)


YY, XX = np.mgrid[0:H, 0:W]


def m_ellipse(cx, cy, rx, ry):
    return ((XX + 0.5 - cx) / rx) ** 2 + ((YY + 0.5 - cy) / ry) ** 2 <= 1.0


def m_poly(pts):
    """多边形内部（像素中心判定）。"""
    px, py = XX + 0.5, YY + 0.5
    inside = np.zeros((H, W), bool)
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        cond = ((y0 > py) != (y1 > py))
        xint = (x1 - x0) * (py - y0) / ((y1 - y0) if y1 != y0 else 1e-9) + x0
        inside ^= cond & (px < xint)
    return inside


def m_line(p0, p1, w=2):
    """粗线：沿线段每 0.25 像素盖一个 w×w 的方块。"""
    m = np.zeros((H, W), bool)
    (x0, y0), (x1, y1) = p0, p1
    n = max(1, int(math.hypot(x1 - x0, y1 - y0) * 4))
    for k in range(n + 1):
        t = k / n
        x = x0 + (x1 - x0) * t - w / 2
        y = y0 + (y1 - y0) * t - w / 2
        xi, yi = int(round(x)), int(round(y))
        m[max(0, yi):max(0, yi + w), max(0, xi):max(0, xi + w)] = True
    return m


def m_chain(pts, widths):
    m = np.zeros((H, W), bool)
    for i in range(len(pts) - 1):
        m |= m_line(pts[i], pts[i + 1], widths[min(i, len(widths) - 1)])
    return m


def m_rect(x0, y0, x1, y1):
    return (XX >= x0) & (XX < x1) & (YY >= y0) & (YY < y1)


def shift(m, dx, dy):
    out = np.zeros_like(m)
    ys, xs = np.nonzero(m)
    ys, xs = ys + dy, xs + dx
    ok = (ys >= 0) & (ys < H) & (xs >= 0) & (xs < W)
    out[ys[ok], xs[ok]] = True
    return out


# ============================================================ 上色：按法线分档

LIGHT = np.array([0.45, -0.80, 0.40])          # 上前方（朝右 = +x，往上 = −y）
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def sphere_idx(m, cx, cy, rx, ry, n, bias=0.0, gain=1.0):
    """把 mask 当成以 (cx,cy) 为中心的椭球来打光，分成 n 档（0 = 最暗）。"""
    nx = (XX + 0.5 - cx) / rx
    ny = (YY + 0.5 - cy) / ry
    r2 = np.clip(nx ** 2 + ny ** 2, 0, 1)
    nz = np.sqrt(1 - r2)
    lit = nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]
    v = 0.5 + 0.5 * gain * lit + bias
    idx = np.clip(np.floor(v * n), 0, n - 1).astype(int)
    return np.where(m, idx, 0)


def column_idx(m, n, base, top=1, top_depth=1, bottom=-1, bottom_depth=1, back=-1, back_depth=1, front=0):
    """柱面 / 平面的分档：上边缘亮一档，下边缘暗一档，背面（左）暗一档。"""
    idx = np.full((H, W), base, int)
    above = np.zeros((H, W), int)      # 这个像素上面连续几格还在 mask 里
    below = np.zeros((H, W), int)
    for y in range(H):
        above[y] = np.where(m[y], (above[y - 1] + 1) if y else 1, 0)
    for y in range(H - 1, -1, -1):
        below[y] = np.where(m[y], (below[y + 1] + 1) if y < H - 1 else 1, 0)
    left = np.zeros((H, W), int)
    right = np.zeros((H, W), int)
    for x in range(W):
        left[:, x] = np.where(m[:, x], (left[:, x - 1] + 1) if x else 1, 0)
    for x in range(W - 1, -1, -1):
        right[:, x] = np.where(m[:, x], (right[:, x + 1] + 1) if x < W - 1 else 1, 0)
    idx = idx + np.where(left <= back_depth, back, 0)
    idx = idx + np.where(right <= 1, front, 0)
    idx = idx + np.where(below <= bottom_depth, bottom, 0)
    idx = np.where(above <= top_depth, base + top, idx)
    return np.where(m, np.clip(idx, 0, n - 1), 0)


# ============================================================ 腿（两节反向运动学）

def leg_points(hip, foot, a, b):
    """胯 → 膝 → 踝，膝盖朝前（+x）弯。"""
    hx, hy = hip
    fx, fy = foot
    dx, dy = fx - hx, fy - hy
    d = min(math.hypot(dx, dy), a + b - 1e-3)
    base = math.atan2(dy, dx)
    cosA = max(-1.0, min(1.0, (a * a + d * d - b * b) / (2 * a * d)))
    ang = base - math.acos(cosA)
    knee = (hx + a * math.cos(ang), hy + a * math.sin(ang))
    return knee


def draw_leg(f, hip, fx, lift, ramp, shoe, thigh, shin, w=2, shoe_len=3, near=True):
    """一条腿：腿（ramp 两档：上亮下暗）+ 鞋（shoe 色阶）。fx = 脚尖往后那一列（鞋跟），lift = 抬起几格。"""
    sole = GROUND - lift
    ank = (fx + 0.5, sole - 1.0)
    knee = leg_points(hip, ank, thigh, shin)
    m = m_line(hip, knee, w) | m_line(knee, ank, w)
    f.paint(m, ramp[1])
    upper = m & (YY < knee[1])
    f.paint(upper, ramp[2] if len(ramp) > 2 else ramp[1])
    # 鞋：两行，鞋跟在 fx，往前伸 shoe_len；离地往后踢时鞋尖朝下一点
    x0 = int(math.floor(fx)) - (w - 1) // 2
    sm = m_rect(x0, sole - 1, x0 + shoe_len, sole + 1)
    if lift >= 2 and fx < 0 + hip[0] - 2:     # 往后踢：鞋尖翘下去，只留脚跟两格
        sm = m_rect(x0, sole - 2, x0 + 2, sole + 1)
    f.paint(sm, shoe[0])
    f.paint(sm & (YY == sole - 1 if not (lift >= 2 and fx < hip[0] - 2) else YY == sole - 2), shoe[1])


# ============================================================ 姿势

def run_pose(i):
    nf = RUN_FOOT[i % 8]
    ff = RUN_FOOT[(i + 4) % 8]
    return dict(mode="run", i=i, bob=RUN_BOB[i % 8], lean=1, near=nf, far=ff,
                arm=-nf[0] / 5.5,                 # 近手和近腿反着摆
                phase=2 * math.pi * i / 8 * 2,     # 跟随部件每步一个来回（一圈两步）
                breath=0, blink=False)


def idle_pose(i):
    return dict(mode="idle", i=i, bob=0, lean=0, near=(2, 0), far=(-2, 0), arm=0.0,
                phase=2 * math.pi * i / IDLE_N, breath=[0, 1, 1, 0][i], blink=False)


# ============================================================ A 围巾

def pal_a():
    body = ramp_lch([0.70, 0.80, 0.885, 0.945, 0.985], 0.032, 80, warm=10)
    scarf = ramp_lch([0.48, 0.58, 0.67, 0.75], 0.165, 32, warm=10)
    eye = lch(0.24, 0.035, 300)
    return body, scarf, eye


def draw_a(p):
    body, scarf, eye = pal_a()
    f = Fig()
    cx = 20 + p["lean"]
    hip_y = 31 + p["bob"]
    hip = (cx - 0.5, hip_y)
    leg_ramp = [body[0], body[1], body[2]]
    shoe = [scarf[0], scarf[1]]
    head_dy = p["bob"] - p["breath"] + 1
    # 围巾两条尾巴（在身体后面）
    knot = (cx - 3.0, 20.5 + head_dy)
    for k, (off, length, wid) in enumerate([(0.0, 7, 3), (1.6, 6, 2)]):
        pts = [knot]
        for s in range(1, length + 1):
            if p["mode"] == "run":
                x = knot[0] - s * 1.9
                y = knot[1] + off + 0.35 * s + 1.4 * math.sin(p["phase"] - s * 0.9 + k * 0.9) * min(1, s / 3)
            else:
                x = knot[0] - s * 0.55 - 0.35 * s * s / length
                y = knot[1] + off + s * 1.45 + 0.6 * math.sin(p["phase"] - s * 0.7 + k) * s / length
            pts.append((x, y))
        m = m_chain(pts, [wid] * 3 + [max(2, wid - 1)] * 10)
        idx = column_idx(m, 4, 1 if k == 0 else 0, top=1, bottom=-1, back=0)
        f.paint_idx(m, idx, scarf)
    # 远腿、远手
    nf, ff = p["near"], p["far"]
    draw_leg(f, (hip[0] - 1, hip[1]), cx - 1 + ff[0], ff[1], [body[0], body[0], body[1]],
             [lch(0.40, 0.13, 30), scarf[0]], 4.8, 5.9)
    sh = (cx - 1.0, 22.5 + head_dy)
    arm_far = (sh[0] + 4.2 * math.sin(-p["arm"]), sh[1] + 4.2 * math.cos(p["arm"]))
    m = m_line(sh, arm_far, 2)
    f.paint(m, body[1])
    # 身体（短袍）
    tor = m_poly([(cx - 3.5, 20 + head_dy), (cx + 3.5, 20 + head_dy), (cx + 6.5, hip_y + 2.5), (cx - 7, hip_y + 2.5)])
    idx = column_idx(tor, 5, 3, top=1, bottom=-1, back=-1, back_depth=2)
    idx = np.where(tor & (XX + 0.5 > cx + 0.5) & (YY > hip_y - 3), np.maximum(idx - 1, 0), idx)   # 前襟下摆背光
    f.paint_idx(tor, idx, body)
    # 近腿
    draw_leg(f, (hip[0] + 1, hip[1]), cx + 1 + nf[0], nf[1], leg_ramp, shoe, 4.8, 5.9)
    # 头
    hcx, hcy = cx + 0.5, 11.0 + head_dy
    head = m_ellipse(hcx, hcy, 9.1, 8.3)
    head &= ~((YY > hcy + 5) & (np.abs(XX + 0.5 - hcx) > 6.5))     # 下巴收一点
    idx = sphere_idx(head, hcx - 0.5, hcy - 0.5, 9.5, 8.8, 5, bias=0.06, gain=1.15)
    f.paint_idx(head, idx, body)
    # 天线：从头顶偏后长出来，往后弯，顶上一颗珊瑚红的球
    tip_sway = (math.sin(p["phase"] - 1.2) * (1.0 if p["mode"] == "run" else 0.6))
    top = hcy - 8.6
    a0 = (hcx - 1.5, top + 1.0)
    a1 = (hcx - 2.5, top - 1.5)
    a2 = (hcx - 4.0 + tip_sway * 0.6, top - 2.6)
    f.paint(m_chain([a0, a1, a2], [1, 1]), body[3])
    bx, by = int(math.floor(a2[0] - 0.5)), int(math.floor(a2[1] - 1.0))
    bulb = m_rect(bx, by, bx + 2, by + 2)
    f.paint(bulb, scarf[3])
    f.put(bx + 1, by, lch(0.88, 0.09, 55))
    # 脸：两只大眼睛（3/4 侧面，近眼大、远眼窄）
    ey = int(round(hcy)) - 1
    blink = p["blink"]
    ex = int(round(hcx)) + 1
    if blink:
        f.paint(m_rect(ex, ey + 2, ex + 3, ey + 3), eye)
        f.paint(m_rect(ex + 5, ey + 2, ex + 7, ey + 3), eye)
    else:
        f.paint(m_rect(ex, ey, ex + 3, ey + 4), eye)
        f.paint(m_rect(ex + 5, ey, ex + 7, ey + 4), eye)
        f.put(ex + 1, ey, body[4])
        f.put(ex + 5, ey, body[4])
        f.erase(m_rect(ex + 2, ey + 3, ex + 3, ey + 4) & ~head)
        f.put(ex + 2, ey + 3, body[2])
    f.put(ex + 3, ey + 4, scarf[2])                 # 一点腮红
    # 围巾绕脖子一圈 + 结
    ring = m_poly([(cx - 5, 18.5 + head_dy), (cx + 5, 18.5 + head_dy), (cx + 5, 21.5 + head_dy), (cx - 5, 21.5 + head_dy)])
    ring &= ~(head & (YY < 19 + head_dy))
    idx = column_idx(ring, 4, 2, top=1, bottom=-1, back=-1)
    f.paint_idx(ring, idx, scarf)
    # 近手
    arm = (sh[0] + 1 + 5.0 * math.sin(p["arm"]), sh[1] + 5.0 * math.cos(p["arm"]))
    m = m_line((sh[0] + 1, sh[1]), arm, 2)
    f.paint(m, body[2])
    f.paint(m & (YY <= sh[1] + 1), body[3])
    f.paint(m & (YY >= arm[1] - 0.5), body[1])
    return f.a


# ============================================================ B 帽兜 + 地图筒

def pal_b():
    cloak = ramp_lch([0.60, 0.70, 0.80, 0.89, 0.965], 0.035, 300, warm=6)
    tube = ramp_lch([0.42, 0.54, 0.66, 0.78], 0.12, 62, warm=8)
    hole = lch(0.20, 0.035, 295)
    glow = lch(0.90, 0.13, 80)
    return cloak, tube, hole, glow


def draw_b(p):
    cloak, tube, hole, glow = pal_b()
    f = Fig()
    cx = 20 + p["lean"]
    bob = p["bob"]
    hip_y = 33 + bob
    up = bob - p["breath"]
    run = p["mode"] == "run"
    ph = p["phase"]
    sw = math.sin(ph - 1.4) * (1.0 if run else 0.6)
    # 地图筒：斜背在背后，上端从后肩伸出来，比肩高一截
    t0 = (cx - 9.0 - (0.5 if run else 0), 4.5 + up)
    t1 = (cx - 2.0, 29.0 + up)
    tm = m_line(t0, t1, 4)
    idx = column_idx(tm, 4, 2, top=1, bottom=-1, back=-1)
    f.paint_idx(tm, idx, tube)
    ty = int(round(t0[1])) - 1
    capm = tm & (YY <= ty + 1)
    f.paint(capm, tube[3])
    lid = m_rect(int(math.floor(t0[0])) - 2, ty + 2, int(math.floor(t0[0])) + 3, ty + 3)
    f.paint(lid, tube[0])
    # 远腿
    nf, ff = p["near"], p["far"]
    boot = [tube[0], tube[1]]
    draw_leg(f, (cx - 1.5, hip_y), cx - 1 + ff[0], ff[1], [cloak[0], cloak[0], cloak[1]], boot, 3.8, 4.4)
    # 斗篷（肩以下）：下摆往后飘
    hem_y = 34.5 + bob
    flap = math.sin(ph - 2.0) * (1.4 if run else 0.5)
    back_hem = cx - 9.5 - (2.0 if run else 0) + flap
    body_pts = [(cx - 6.0, 15.5 + up), (cx + 5.5, 15.5 + up), (cx + 7.0 + (0.6 if run else 0), 24.0 + up),
                (cx + 8.5 + (0.5 if run else 0), hem_y - 0.5), (cx + 5, hem_y + 0.5), (cx + 1, hem_y),
                (cx - 3, hem_y + 0.6), (back_hem, hem_y - 0.3 - (1.5 if run else 0)), (cx - 8.0, 24 + up)]
    cm = m_poly(body_pts)
    for x in range(W):                                   # 下摆参差：几列短一格
        if (x * 7 + 3) % 5 == 0:
            col = np.nonzero(cm[:, x])[0]
            if len(col) and col.max() >= hem_y - 1:
                cm[col.max(), x] = False
    idx = sphere_idx(cm, cx + 1, 18 + up, 11, 16, 5, bias=0.10, gain=1.0)
    fold = m_line((cx - 1.0, 21 + up), (cx + 1.5 + (0.5 if run else 0), hem_y), 1) & cm
    ridge = shift(fold, 1, 0) & cm & ~fold
    idx = np.where(fold, np.maximum(idx - 1, 0), idx)
    idx = np.where(ridge, np.minimum(idx + 1, 4), idx)
    f.paint_idx(cm, idx, cloak)
    # 帽兜：前面圆、顶上一个往后翘的尖
    tipx = cx - 5.5 + sw * 0.8 - (1.0 if run else 0)
    tipy = 0.5 + up + (0.5 * math.cos(ph - 1.4) if run else 0)
    hood_pts = [(tipx, tipy), (cx - 1.5, 3.0 + up), (cx + 2.5, 3.8 + up), (cx + 5.8, 7.0 + up), (cx + 7.0, 12.0 + up),
                (cx + 6.4, 17.0 + up), (cx + 4.0, 19.6 + up), (cx - 4.0, 19.6 + up), (cx - 7.0, 16.5 + up),
                (cx - 7.4, 11.0 + up), (cx - 6.5, 6.5 + up)]
    hm = m_poly(hood_pts)
    hidx = sphere_idx(hm, cx + 0.5, 10.5 + up, 8.5, 9.5, 5, bias=0.16, gain=1.05)
    f.paint_idx(hm, hidx, cloak)
    # 帽兜底边在斗篷上压出一道影子（不是描边：只在斗篷那一侧暗一档）
    shadow = shift(hm, 0, 1) & cm & ~hm
    f.paint_idx(shadow, np.maximum(idx - 1, 0), cloak)
    # 帽兜开口：尖椭圆，填最深色，两点琥珀色的眼睛
    hcx, hcy = cx + 3.3, 12.0 + up
    face = m_ellipse(hcx, hcy, 3.5, 4.4) & hm
    face &= ~((YY < hcy - 2) & (XX + 0.5 < hcx - 1.5))
    f.paint(face, hole)
    rim = shift(face, 0, -1) & hm & ~face
    f.paint(rim & (YY < hcy), cloak[4])
    ex, ey = int(round(hcx)), int(round(hcy)) - 1
    if p["blink"]:
        f.put(ex - 1, ey + 1, glow)
        f.put(ex + 2, ey + 1, glow)
    else:
        f.paint(m_rect(ex - 1, ey, ex, ey + 2), glow)
        f.paint(m_rect(ex + 2, ey, ex + 3, ey + 2), glow)
    # 背带：从后肩斜到前腰（细，一档亮一档暗）
    strap = m_line((cx - 5.0, 20.5 + up), (cx + 4.0, 28.5 + up), 1) & cm
    f.paint(strap, tube[1])
    # 近腿
    draw_leg(f, (cx + 0.5, hip_y), cx + 1 + nf[0], nf[1], [cloak[1], cloak[1], cloak[2]], boot, 3.8, 4.4)
    f.paint_idx(cm & (YY >= hem_y - 3), idx, cloak)       # 下摆盖住大腿根
    return f.a


# ============================================================ C 长耳 + 背包（包上捆着卷起来的地图）

def pal_c():
    body = ramp_lch([0.70, 0.80, 0.88, 0.94, 0.98], 0.105, 102, warm=6)
    pack = ramp_lch([0.36, 0.45, 0.54, 0.62], 0.10, 38, warm=10)
    paper = lch(0.93, 0.03, 85)
    eye = lch(0.24, 0.04, 285)
    return body, pack, paper, eye


# 耳朵：从头顶竖起来，尖往后耷拉（像倒过来的 J）；跑起来整根往后倒
EAR_IDLE = [(0, 0), (-0.4, -2.0), (-0.9, -4.0), (-1.9, -5.6), (-3.4, -6.3), (-4.9, -5.8), (-5.9, -4.4)]
EAR_RUN = [(0, 0), (-1.0, -2.0), (-2.6, -3.6), (-4.5, -4.5), (-6.6, -4.7), (-8.6, -4.2), (-10.2, -3.3)]


def draw_c(p):
    body, pack, paper, eye = pal_c()
    f = Fig()
    run = p["mode"] == "run"
    cx = 20 + p["lean"]
    bob = p["bob"]
    hip_y = 34 + bob
    up = bob - p["breath"]
    ph = p["phase"]
    bcx, bcy = cx + 0.5, 22.5 + up

    def ear(k, ramp_base, tip_col):
        root = (bcx + 1.0 - 5.0 * k, bcy - 10.4 + 1.6 * k)
        base = EAR_RUN if run else EAR_IDLE
        pts = []
        for s, (dx, dy) in enumerate(base):
            w = (1.3 if run else 0.6) * math.sin(ph - s * 0.8 + k * 0.9) * s / len(base)
            pts.append((root[0] + dx * (1 - 0.1 * k), root[1] + dy * (1 - 0.1 * k) + w))
        m = m_chain(pts, [3, 2, 2, 2, 2, 2])
        tipx, tipy = pts[-1]
        tip = m_ellipse(tipx - 0.3, tipy + 0.5, 1.6, 1.6)
        m |= tip
        idx = column_idx(m, 5, ramp_base, top=1, bottom=-1, back=0)
        f.paint_idx(m, idx, body)
        f.paint(tip, tip_col)

    ear(1, 1, body[2])                                   # 远耳在身体后面，暗一档
    nf, ff = p["near"], p["far"]
    draw_leg(f, (cx - 2, hip_y), cx - 1 + ff[0], ff[1], [body[0], body[0], body[1]], [pack[0], pack[1]], 3.4, 4.2)
    # 背包（小一点、靠下），上面横捆一卷地图
    px0, py0 = int(round(bcx - 13)), int(round(bcy - 3))
    corner = m_poly([(px0 + 1.5, py0 + 0.5), (px0 + 3.5, py0 - 3.5), (px0 + 6.5, py0 - 2), (px0 + 5.5, py0 + 0.5)])
    f.paint(corner, paper)
    f.paint(corner & (YY >= py0 - 1), body[2])
    pm = m_poly([(px0 + 0.5, py0), (px0 + 8.5, py0), (px0 + 9, py0 + 12.5), (px0 + 1, py0 + 12.5), (px0 - 0.5, py0 + 6)])
    idx = column_idx(pm, 4, 2, top=1, bottom=-1, back=-1)
    f.paint_idx(pm, idx, pack)
    flap = m_rect(px0, py0, px0 + 9, py0 + 4) & pm
    f.paint(flap, pack[3])
    f.paint(m_rect(px0, py0 + 4, px0 + 9, py0 + 5) & pm, pack[1])
    f.paint(m_rect(px0 + 3, py0 + 4, px0 + 5, py0 + 6) & pm, pack[0])      # 扣
    # 身体：蛋形，头身一体
    bm = m_ellipse(bcx, bcy, 9.2, 11.6)
    bm &= YY < hip_y + 1
    idx = sphere_idx(bm, bcx - 0.5, bcy - 3, 10, 12, 5, bias=0.12, gain=1.05)
    f.paint_idx(bm, idx, body)
    # 背带：只在肩上露一小段
    f.paint(m_line((bcx - 7.6, bcy - 1.5), (bcx - 5.6, bcy + 1.5), 1) & bm, pack[1])
    # 眼睛：大而圆，靠前；一个小嘴
    ex, ey = int(round(bcx)) + 1, int(round(bcy)) - 6
    if p["blink"]:
        f.paint(m_rect(ex, ey + 2, ex + 3, ey + 3), eye)
        f.paint(m_rect(ex + 5, ey + 2, ex + 7, ey + 3), eye)
    else:
        f.paint(m_rect(ex, ey, ex + 3, ey + 4), eye)
        f.paint(m_rect(ex + 5, ey + 1, ex + 7, ey + 4), eye)
        f.put(ex + 1, ey, body[4])
        f.put(ex + 5, ey + 1, body[4])
    f.put(ex + 4, ey + 5, pack[2])
    # 近耳（在身体前面）
    ear(0, 3, body[4])
    # 近腿
    draw_leg(f, (cx + 1, hip_y), cx + 1 + nf[0], nf[1], [body[1], body[1], body[2]], [pack[1], pack[2]], 3.4, 4.2)
    # 近手：小短手
    sh = (bcx - 0.5, bcy + 3.0)
    arm = (sh[0] + 4.0 * math.sin(p["arm"]) + 0.5, sh[1] + 4.0 * math.cos(p["arm"]))
    m = m_line(sh, arm, 2)
    f.paint(m, body[2])
    f.paint(m & (YY >= arm[1] - 0.5), body[1])
    return f.a


# ============================================================ 输出

CANDS = {
    "a": ("A 围巾", draw_a, pal_a),
    "b": ("B 帽兜", draw_b, pal_b),
    "c": ("C 长耳", draw_c, pal_c),
}


def frames_of(draw):
    run = [draw(run_pose(i)) for i in range(8)]
    idle = [draw(idle_pose(i)) for i in range(IDLE_N)]
    return run, idle


def foot_check(frames):
    """脚底那一行在 run / idle 每帧都要有像素（不浮空）。"""
    return [bool(f[GROUND, :, 3].any()) for f in frames]


def export(key):
    title, draw, _ = CANDS[key]
    run, idle = frames_of(draw)
    out = OUT / key
    out.mkdir(parents=True, exist_ok=True)
    frames = run + idle
    tags = [{"name": "run", "from": 0, "to": 7, "direction": "forward"},
            {"name": "idle", "from": 8, "to": 8 + IDLE_N - 1, "direction": "forward"}]
    write_sheet(frames, out / "chen.png", tags=tags, durations=[RUN_MS] * 8 + [IDLE_MS] * IDLE_N)
    print(f"== {title}  ({out / 'chen.png'})")
    print(report(check_image(idle[0], "minimal_hooded"), "  idle[0] vs 帽兜人形（同尺寸的人形）"))
    print(report(check_animation(run, "move"), "  run"))
    print(report(check_animation(idle, "idle"), "  idle"))
    for f in frames:
        assert set(np.unique(f[..., 3])) <= {0, 255}
    print("  脚底着地:", foot_check(run))
    return run, idle


ANIMS_TXT = f'''const ANIMS := {{
	"run": {{"frames": [0, 1, 2, 3, 4, 5, 6, 7], "ms": {RUN_MS}, "step": {RUN_STEP}}},
	"idle": {{"frames": [8, 9, 10, 11], "ms": {IDLE_MS}}},
}}'''


# ============================================================ 预览（不进工程）

SCENES = [("森林", "forest_test"), ("河岸", "river_test"), ("水底", "underwater_test"), ("云星", "cloud_test")]


def font(size):
    from PIL import ImageFont
    for p in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def up(a, k):
    return np.repeat(np.repeat(a, k, 0), k, 1)


def comp(bg, spr, x, y):
    m = spr[..., 3] > 0
    ys, xs = np.nonzero(m)
    ok = (ys + y >= 0) & (ys + y < bg.shape[0]) & (xs + x >= 0) & (xs + x < bg.shape[1])
    bg[ys[ok] + y, xs[ok] + x] = spr[ys[ok], xs[ok], :3]


def preview(d: Path, all_frames: dict):
    from PIL import ImageDraw
    d.mkdir(parents=True, exist_ok=True)
    BG = (34, 36, 44)
    # ---- candidates.png：每版一行：idle 4 帧 | 跑步 8 帧，放大 4 倍
    k = 4
    gap = 6
    label_w = 150
    rows = []
    for key, (title, _, _) in CANDS.items():
        run, idle = all_frames[key]
        cells = idle + [None] + run
        wpx = sum((W if c is not None else 8) for c in cells) + gap * (len(cells) - 1)
        row = np.zeros((H + 4, wpx, 3), np.uint8)
        row[:] = BG
        x = 0
        for c in cells:
            if c is None:
                x += 8 + gap
                continue
            comp(row, c, x, 2)
            row[2 + GROUND + 1, x:x + W] = (52, 55, 66)
            x += W + gap
        rows.append((title, up(row, k)))
    hh = 40
    Wt = label_w + max(r.shape[1] for _, r in rows) + 20
    Ht = hh + sum(r.shape[0] + 20 for _, r in rows) + 10
    im = Image.new("RGB", (Wt, Ht), BG)
    dr = ImageDraw.Draw(im)
    dr.text((14, 8), "晨 · 三版候选（放大 4 倍）   待机 4 帧 × 220ms   |   跑步 8 帧 × 80ms", fill=(220, 220, 230), font=font(18))
    y = hh
    for title, r in rows:
        dr.text((14, y + r.shape[0] // 2 - 12), title, fill=(235, 235, 240), font=font(22))
        im.paste(Image.fromarray(r), (label_w, y))
        y += r.shape[0] + 20
    im.save(d / "candidates.png")
    # ---- 跑步 GIF（放大 4 倍，暗背景，地面一条线；人原地跑，地面线上的刻度往后走，看脚有没有打滑）
    for key in CANDS:
        run, _ = all_frames[key]
        ims = []
        off = 0
        for i, fr in enumerate(run):
            bg = np.zeros((H + 4, W + 40, 3), np.uint8)
            bg[:] = (30, 34, 40)
            bg[GROUND + 1:, :] = (44, 50, 56)
            for tx in range(-off % 8, bg.shape[1], 8):
                bg[GROUND + 1:GROUND + 3, tx] = (70, 78, 86)
            comp(bg, fr, 20, 0)
            ims.append(Image.fromarray(up(bg, 4)))
            off += RUN_STEP[i]
        ims[0].save(d / f"run_{key}.gif", save_all=True, append_images=ims[1:], duration=RUN_MS, loop=0, disposal=2)
    # ---- on_scenes.png：截图缩回 480×270（取像素中心）、1 倍贴三版，再整体放大 3 倍
    bgdir = d / "bg"
    crops = []
    for name, scene in SCENES:
        p = bgdir / f"{scene}.png"
        if not p.exists():
            print("缺截图，跳过 on_scenes：", p)
            return
        a = np.array(Image.open(p).convert("RGB"))
        Hs, Ws = a.shape[:2]
        xs = ((np.arange(480) + 0.5) * Ws / 480).astype(int)
        ys = ((np.arange(270) + 0.5) * Hs / 270).astype(int)
        s = a[ys][:, xs].copy()
        foot = old_chen_foot(s, scene)
        # 旧晨站在屏幕 x≈200；在它右边 40 像素外摆三版（裁掉旧晨）
        x0 = 232
        crop_w, crop_h = 240, 110
        y0 = foot - 80
        for j, key in enumerate(CANDS):
            fr = all_frames[key][1][0]
            gx = x0 + 22 + j * 76
            gy = ground_near(gx + FOOT[0], foot, scene)
            comp(s, fr, gx, gy - FOOT[1])
        crops.append((name, s[y0:y0 + crop_h, x0:x0 + crop_w]))
    k = 3
    im = Image.new("RGB", (crop_w * k * 2 + 30, (crop_h * k + 36) * 2 + 10), (20, 20, 24))
    dr = ImageDraw.Draw(im)
    for i, (name, c) in enumerate(crops):
        gx, gy = (i % 2) * (crop_w * k + 30), (i // 2) * (crop_h * k + 36)
        dr.text((gx + 8, gy + 6), f"{name}    A 围巾   ·   B 帽兜   ·   C 长耳    （1 倍贴，放大 3 倍）", fill=(220, 220, 228), font=font(18))
        im.paste(Image.fromarray(up(c, k)), (gx, gy + 34))
    im.save(d / "on_scenes.png")
    print("预览写到", d)


# 截图里旧晨的脚底那一行（拍的时候都用 --x=300：晨在世界 x=504、屏幕 x≈206；从截图里找旧晨的像素量出来的）
OLD_X_SCREEN, OLD_X_WORLD = 206, 504


def old_chen_foot(s, scene):
    return {"forest_test": 230, "river_test": 226, "underwater_test": 226, "cloud_test": 225}[scene]


def _scene_ground(scene, wx):
    """各场景 chen.ground_fn 的同一套公式（世界 x → 地面行），只用来算贴图处和旧晨处的高差。"""
    t = 2 * math.pi
    wx = wx % 960
    if scene == "forest_test":
        return 2.0 * math.sin(t * wx * 2 / 960) + 1.5 * math.sin(t * wx * 5 / 960 + 1.0)
    if scene == "river_test":
        return 1.5 * math.sin(t * wx * 2 / 960) + 1.0 * math.sin(t * wx * 5 / 960 + 2.0)
    if scene == "underwater_test":
        return 1.5 * math.sin(t * wx * 2 / 960 + 0.5) + 1.0 * math.sin(t * wx * 5 / 960 + 1.3)
    a = np.array(Image.open(ROOT / "art" / "cloud" / "main.png").convert("RGBA"))[..., 3]
    col = np.nonzero(a[:, int(wx) % a.shape[1]] > 0)[0]
    return float(col[0]) if len(col) else 0.0


def ground_near(x, foot, scene):
    """贴图处（屏幕 x）的地面行 = 旧晨脚底 + 两处地面公式的高差。"""
    wx = OLD_X_WORLD + (x - OLD_X_SCREEN)
    return int(round(foot + _scene_ground(scene, wx) - _scene_ground(scene, OLD_X_WORLD)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default=None)
    args = ap.parse_args()
    allf = {k: export(k) for k in CANDS}
    print("\nchen.gd 精灵配置（三版一样，只换 SHEET 路径）：")
    print('const SHEET := preload("res://art/characters/chen_candidates/<a|b|c>/chen.png")')
    print("const FRAME_SIZE := Vector2i(40, 42)\nconst FOOT := Vector2i(20, 41)\nconst ART_FACES := 1")
    print(ANIMS_TXT)
    if args.preview:
        preview(Path(args.preview), allf)


if __name__ == "__main__":
    main()
