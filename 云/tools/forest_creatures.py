"""针叶林深处的影子动物：鹿、鸟群、渡鸦、枝头小鸟、驼鹿、狐狸的剪影精灵。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/forest_creatures.py [--preview 目录]

输出 art/creatures/*.png（1 倍横排精灵表 + 同名 .json，Aseprite json-array 格式，每帧时长写在里面）。

颜色约定（Godot 里 scripts/shadow_tint.gdshader 读）：
  白 (255,255,255) = 身体，着色成「影子色」；
  灰 (178,178,178) = 远侧的腿 / 远侧的翅膀，着色时往雾色多靠 30%，腿交叉时分得清前后。
  alpha 只有 0 / 255。所以图里只有剪影的形状，真正的颜色在 Godot 里按雾带的明暗和远近定。

四足动物用一个小骨架画：躯干是几个椭圆，脖子 / 头 / 尾是粗细线，腿是两段 IK（给脚的位置，膝盖自己弯）。
步态按相位算脚的位置（着地时脚往后匀速退，抬起时往前摆），所以「每帧往前走多少像素」是算出来的，
Godot 里按这个速度移动，脚不打滑（奔跑是每换一帧精灵跳一步，见 RUN_KEYS 上面的说明）。
转身用绕竖轴转（yaw）加脖子单独转（head_yaw，扭头往后看），不画正对镜头的那一帧（剪影会变成竖条）。
渡鸦和枝头小鸟是逐像素手写的（太小，程序画不干净）。
所有帧同一画布、脚底同一行，身体中心在画布正中（水平翻转后位置不变）。没有随机。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.anim import write_gif, write_sheet  # noqa: E402
from oscarkit.canvas import Canvas  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "art" / "creatures"
A = (255, 255, 255)   # 身体
B = (178, 178, 178)   # 远侧
B_FOG = 0.3           # 远侧往雾里多靠多少（和 shader 里 178/255 对应：1 - 0.7）


# ---------------------------------------------------------------- 画图小工具

def lerp(a, b, t):
    return a + (b - a) * t


def smooth(u):
    return u * u * (3 - 2 * u)


class Pen:
    """在画布上按「身体坐标」画：x 往前（朝右），y 往上为负，地面 y=0 就是画布最后一行。
    yaw 绕身体中心 cx 转：x' = cx + (x - cx)·cos(yaw) + z·sin(yaw)。"""

    def __init__(self, c: Canvas, ox: float, cx: float, yaw: float = 0.0):
        self.c, self.ox, self.cx = c, ox, cx
        self.cos, self.sin = math.cos(yaw), math.sin(yaw)

    def px(self, x, y, z=0.0):
        X = self.ox + self.cx + (x - self.cx) * self.cos + z * self.sin
        Y = self.c.h - 1 + y
        return X, Y

    def dot(self, x, y, z, col):
        X, Y = self.px(x, y, z)
        self.c.put(int(round(X)), int(round(Y)), col)

    def blob(self, x, y, z, rx, ry, col, wz=None):
        """一个椭圆（侧面看 rx×ry）；转身时横向半径在 rx 和身体半宽 wz 之间过渡。"""
        X, Y = self.px(x, y, z)
        wz = ry * 0.8 if wz is None else wz
        rxp = math.hypot(rx * self.cos, wz * self.sin)
        self.c.ellipse(X + 0.5, Y + 0.5, rxp, ry, col)

    def shape(self, pts, col, half_w):
        """躯干轮廓（侧面的多边形）。转身时 x 往中心压，再并上一个半宽 half_w 的椭圆，正对时不会变成一条线。"""
        P = [self.px(x, y) for x, y in pts]
        self.c.poly([(X + 0.5, Y + 0.5) for X, Y in P], col)
        if abs(self.sin) > 0.2:
            ys = [y for _, y in pts]
            top, bot = min(ys), max(ys)
            X, _ = self.px(self.cx, 0)
            _, Y = self.px(0, (top + bot) / 2)
            self.c.ellipse(X + 0.5, Y + 0.5, half_w * abs(self.sin), (bot - top) / 2, col)

    def seg(self, p0, p1, w, col, z=0.0):
        """线段，w=1 或 2 像素粗（2 粗时往竖直线的右边 / 水平线的下边加一列）。"""
        x0, y0 = self.px(p0[0], p0[1], z)
        x1, y1 = self.px(p1[0], p1[1], z)
        x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
        m = self.c.line(x0, y0, x1, y1)
        if w >= 2:
            if abs(x1 - x0) <= abs(y1 - y0):
                m |= self.c.line(x0 + 1, y0, x1 + 1, y1)
            else:
                m |= self.c.line(x0, y0 + 1, x1, y1 + 1)
        self.c.fill_mask(m, col)

    def taper(self, p0, p1, w0, w1, col, z=0.0, n=6):
        """从 w0 粗渐变到 w1 粗（像素圆点串），画脖子、头、尾巴。"""
        for i in range(n + 1):
            t = i / n
            x, y = lerp(p0[0], p1[0], t), lerp(p0[1], p1[1], t)
            r = lerp(w0, w1, t) / 2
            X, Y = self.px(x, y, z)
            if r <= 0.55:
                self.c.put(int(round(X)), int(round(Y)), col)
            else:
                self.c.ellipse(X + 0.5, Y + 0.5, r, r, col)


def ik(j, f, l1, l2, bend):
    """两段腿：关节 j、脚 f，返回 (膝, 脚)。脚够不着就沿方向伸直。bend=+1 膝朝前，-1 朝后。"""
    dx, dy = f[0] - j[0], f[1] - j[1]
    d = math.hypot(dx, dy)
    ux, uy = dx / d, dy / d
    d = min(max(d, abs(l1 - l2) + 0.05), l1 + l2 - 0.02)
    f = (j[0] + ux * d, j[1] + uy * d)
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    bx, by = j[0] + ux * a, j[1] + uy * a
    px_, py_ = -uy, ux
    if px_ * bend < 0:
        px_, py_ = -px_, -py_
    return (bx + px_ * h, by + py_ * h), f


# ---------------------------------------------------------------- 四足骨架

@dataclass
class Body:
    """一种四足动物的身材（身体坐标，后腿关节在 x=0）。"""
    torso: list                 # 躯干轮廓 [(x, y)]，顺时针：从尾根沿背到胸、再沿肚子回来
    hip: tuple                  # 后腿关节
    shoulder: tuple             # 前腿关节
    hind: tuple                 # (大腿长, 小腿长, 大腿粗[, 小腿粗=1])
    fore: tuple
    neck_root: tuple
    neck_w: tuple               # 脖子根 / 头根的粗细
    head_len: float
    head_w: tuple               # 头根 / 鼻尖粗细
    leg_z: float = 1.2          # 左右腿离中线多远（转身时才看得出）
    half_w: float = 2.0         # 躯干半宽（正对镜头时）
    extras: object = None       # f(pen, pose, col) 画耳朵、角、尾巴等


@dataclass
class Pose:
    feet: dict                  # {"hn": (dx, lift), "hf":…, "fn":…, "ff":…}，dx 相对各自关节
    bob: float = 0.0            # 整个身体往下沉（+）
    pitch: float = 0.0          # 前半身往上抬（−）
    head: tuple = (3.0, -6.0)   # 头根相对脖子根
    nose: float = 0.0           # 头的朝向（弧度，0 = 水平朝前，+ 朝下）
    tail: float = 0.0           # 尾巴：0 垂着，1 翘起
    yaw: float = 0.0
    ears: float = 0.0           # 0 平常，1 竖起警觉
    stretch: float = 0.0        # 身体前后拉长（+）/ 收拢（−）的比例：奔跑腾空时伸展、收腿时收拢
    arch: float = 0.0           # 背往上拱（+，收腿腾空）/ 往下塌（−，伸展腾空），像素
    head_yaw: float | None = None   # 脖子和头单独绕竖轴转（扭头往后看 = π）；None 跟身体一起转


def draw_quad(body: Body, pose: Pose, size, cx_canvas, report=None):
    W, H = size
    c = Canvas(W, H)
    cx = (body.hip[0] + body.shoulder[0]) / 2
    pen = Pen(c, cx_canvas - cx, cx, pose.yaw)
    span = body.shoulder[0] - body.hip[0]

    def bp(x, y):
        """身体上的一个点（静止时的坐标）→ 这一帧的位置：
        stretch 以身体中心前后拉伸，bob 整体上下，pitch 从后到前线性（后腿关节 0，前腿关节 pitch），arch 中间拱起。"""
        u = (x - cx) / (span * 0.5 + 3.0)
        return (cx + (x - cx) * (1 + pose.stretch),
                y + pose.bob + pose.pitch * (x - body.hip[0]) / span - pose.arch * max(0.0, 1 - u * u))

    legs = {
        "hn": (body.hip, body.hind, -1, +body.leg_z),
        "hf": (body.hip, body.hind, -1, -body.leg_z),
        "fn": (body.shoulder, body.fore, +1, +body.leg_z),
        "ff": (body.shoulder, body.fore, +1, -body.leg_z),
    }

    def depth(x, z):
        return z * pen.cos - (x - cx) * pen.sin

    def draw_leg(k, col):
        j0, spec, bend, z = legs[k]
        l1, l2, w1 = spec[:3]
        w2 = spec[3] if len(spec) > 3 else 1
        j = bp(*j0)
        dx, lift = pose.feet[k]
        f = (j0[0] + dx, -lift)          # 脚的位置按「静止时的关节」算，所以着地的脚只跟 dx 有关
        knee, f2 = ik(j, f, l1, l2, bend)
        if lift == 0:
            if report is not None and abs(f2[1]) > 0.35:
                report.append(f"{k} 够不着地（差 {-f2[1]:.2f}）")
            if math.dist(f, f2) < 1.2:
                f2 = f                   # 着地的脚钉在要求的那个像素上（差一点点就让小腿多伸一点），不然取整会滑 1 像素
        pen.taper(j, knee, w1, max(1.0, w2 * 0.9), col, z, n=5)
        pen.seg(knee, f2, w2, col, z)

    far = [k for k in legs if depth(legs[k][0][0], legs[k][3]) < 0]
    near = [k for k in legs if k not in far]
    for k in far:
        draw_leg(k, B)
    pen.shape([bp(x, y) for x, y in body.torso], A, body.half_w)
    nr = bp(*body.neck_root)
    # 头用自己的笔：以脖子根为轴单独转（扭头往后看），没给 head_yaw 就跟身体同一支笔
    if pose.head_yaw is None:
        hp = pen
    else:
        Xn, _ = pen.px(*nr)
        hp = Pen(c, Xn - nr[0], nr[0], pose.head_yaw)
    hb = (nr[0] + pose.head[0], nr[1] + pose.head[1])
    hp.taper(nr, hb, body.neck_w[0], body.neck_w[1], A)
    tip = (hb[0] + body.head_len * math.cos(pose.nose), hb[1] + body.head_len * math.sin(pose.nose))
    hp.taper(hb, tip, body.head_w[0], body.head_w[1], A, n=4)
    if body.extras:
        body.extras(pen, hp, pose, hb, tip, bp)
    for k in near:
        draw_leg(k, A)
    return c.a


# 步态：每条腿一个相位偏移；duty = 着地占一圈的比例。stride = 着地时脚从 +s/2 退到 −s/2。

def gait_feet(t, offsets, duty, stride, lift, reach=0.0, fold=0.0):
    """t∈[0,1) 一圈里的时刻。reach：腾空末段脚往前多伸；fold：腾空中段脚往关节收（膝盖折起来）。"""
    feet = {}
    for k, off in offsets.items():
        p = (t - off) % 1.0
        s = stride[k] if isinstance(stride, dict) else stride
        if p < duty:
            u = p / duty
            dx, ly = s / 2 - s * u, 0.0
        else:
            u = (p - duty) / (1 - duty)
            dx = -s / 2 + (s + reach) * smooth(u) - reach * max(0.0, u - 0.85) / 0.15 * 0.0
            ly = lift * math.sin(math.pi * u) + fold * math.sin(math.pi * u) ** 2
        feet[k] = (dx, ly)
    return feet


# ---------------------------------------------------------------- 鹿

def deer_extras(pen, hp, pose, hb, tip, bp):
    # 耳朵：头根后上方一两个像素（耳朵、角跟着头的那支笔走，扭头时一起转过去）
    e = pose.ears
    hp.dot(hb[0] - 0.8, hb[1] - 1.4 - e * 0.6, 0, A)
    # 角：从头顶往后上方，一根主枝两个分叉（头低下去时跟着头转）
    ang = pose.nose
    ca, sa = math.cos(ang), math.sin(ang)

    def rot(dx, dy):  # 以头根为轴，跟头一起转
        return (hb[0] + dx * ca - dy * sa, hb[1] + dx * sa + dy * ca)

    base = rot(0.0, -1.0)
    p1 = rot(-0.8, -2.8)
    hp.seg(base, p1, 1, A)
    hp.dot(*rot(-1.9, -3.4), 0, A)          # 往后的主枝尖
    hp.dot(*rot(0.2, -3.6), 0, A)           # 往前的叉
    # 尾巴：短的一小撮，跑的时候翘起（白尾鹿受惊时尾巴竖起来）
    rump = bp(-2.4, -11.6)
    t = pose.tail
    end = (rump[0] - 1.2 + 0.4 * t, rump[1] + 1.6 - 2.8 * t)
    pen.seg(rump, end, 1, A)


DEER = Body(
    torso=[(-2.4, -12.6), (-0.6, -13.8), (3.0, -13.4), (6.0, -13.4), (8.6, -14.0), (11.0, -13.2),
           (12.0, -11.4), (11.4, -9.0), (9.4, -8.2), (6.0, -9.0), (3.2, -9.2), (1.8, -8.2), (-0.8, -8.4),
           (-2.6, -10.4)],
    hip=(0.6, -10.6), shoulder=(9.6, -10.0),
    hind=(4.8, 6.0, 3.0), fore=(4.4, 5.8, 2.2),
    neck_root=(10.6, -12.6), neck_w=(2.8, 2.0), head_len=3.4, head_w=(2.4, 1.2),
    half_w=2.2, extras=deer_extras,
)
DEER_SIZE = (34, 26)
DEER_CX = 17


# 奔跑（跳跃式的快跑，8 帧 × 70ms，每帧往前 RUN_P 像素 ≈ 143 px/s，穿过 480 宽的画面约 3.6 秒）。
# 一圈：收腿腾空 → 后腿一前一后落地、蹬地 → 伸展腾空 → 前腿一前一后落地、撑过去 → 收腿腾空……
# 每只脚着地正好 2 帧：落地那帧脚在关节前 +RUN_P/2，下一帧退到 −RUN_P/2。Godot 里精灵每换一帧往前跳 RUN_P，
# 所以着地的脚在地上一动不动（不打滑）。腿长只有 10~11 像素，脚要前后各够 5 像素，着地的帧身体得压低（bob ≥ 1）。
# 同一对腿差一帧落地，近腿 / 远腿分得开；两次腾空（收拢、伸展）各一帧，腾空感靠它们和身体起伏。
RUN_P = 10
RUN_MS = 70
# 着地的脚：落地在关节前 +5.5，下一帧在 −4.5（前后差 RUN_P）。用 .5 是为了让脚落在整像素上：
# 关节的画布 x 是 x.5（后腿 0.6、前腿 9.6，身体中心 5.1 对着画布第 17 列），差半格取整不会来回跳。
_F, _B = RUN_P / 2 + 0.5, -RUN_P / 2 + 0.5
RUN_KEYS = [
    # 0 收腿腾空：后腿往前收到肚子下，前腿折到后面，背拱起，身体最高
    dict(hn=(7.0, 2.6), hf=(5.0, 3.6), fn=(-4.5, 5.0), ff=(-7.5, 3.0),
         bob=-1.4, pitch=0.0, stretch=-0.07, arch=0.9, head=(3.0, -4.8), nose=0.4),
    # 1 近侧后腿落地（在肚子下，很靠前），远侧后腿马上到；前腿还折着往前摆
    dict(hn=(_F, 0), hf=(7.0, 1.4), fn=(-1.0, 6.0), ff=(-4.0, 5.2),
         bob=1.4, pitch=-0.8, stretch=-0.04, arch=0.4, head=(3.2, -4.6), nose=0.35),
    # 2 近后腿蹬到后面，远后腿落地；前半身抬起，前腿往前伸
    dict(hn=(_B, 0), hf=(_F, 0), fn=(3.0, 5.6), ff=(0.0, 6.0),
         bob=1.4, pitch=-1.8, stretch=0.0, arch=0.0, head=(3.4, -4.8), nose=0.3),
    # 3 远后腿最后一蹬；前腿伸到最前面
    dict(hn=(-9.0, 2.6), hf=(_B, 0), fn=(6.5, 4.0), ff=(4.0, 5.0),
         bob=1.1, pitch=-2.4, stretch=0.05, arch=-0.3, head=(3.6, -4.6), nose=0.25),
    # 4 伸展腾空：后腿全伸到后面，前腿全伸到前面，身体拉长、背略塌
    dict(hn=(-8.5, 4.2), hf=(-10.0, 2.6), fn=(8.0, 2.2), ff=(6.5, 3.4),
         bob=-1.6, pitch=-0.4, stretch=0.09, arch=-0.6, head=(3.9, -3.8), nose=0.18),
    # 5 近前腿落地，前半身往下压；后腿开始往前折
    dict(hn=(-4.0, 6.0), hf=(-7.0, 4.8), fn=(_F, 0), ff=(7.5, 1.6),
         bob=0.6, pitch=1.0, stretch=0.04, arch=-0.2, head=(3.7, -3.4), nose=0.3),
    # 6 近前腿撑到后面，远前腿落地；后腿折在肚子下往前收
    dict(hn=(1.0, 6.4), hf=(-2.5, 6.2), fn=(_B, 0), ff=(_F, 0),
         bob=0.7, pitch=0.9, stretch=0.0, arch=0.2, head=(3.4, -3.6), nose=0.4),
    # 7 远前腿最后一撑；后腿收到前面快要落地
    dict(hn=(5.0, 4.6), hf=(2.5, 5.6), fn=(-8.0, 2.8), ff=(_B, 0),
         bob=0.4, pitch=0.8, stretch=-0.04, arch=0.6, head=(3.2, -4.2), nose=0.45),
]


def run_pose(k, **kw):
    d = dict(k)
    feet = {n: d.pop(n) for n in ("hn", "hf", "fn", "ff")}
    d.update(kw)
    return Pose(feet=feet, tail=1.0, **d)


def deer_run():
    frames, poses, rep = [], [], []
    for i, k in enumerate(RUN_KEYS):
        p = run_pose(k)
        poses.append(p)
        r = []
        frames.append(draw_quad(DEER, p, DEER_SIZE, DEER_CX, report=r))
        rep += [f"run {i}: {m}" for m in r]
    for m in rep:
        print("!!", m)
    return frames, poses, float(RUN_P)


def deer_walk(n=8):
    offs = {"hn": 0.0, "fn": 0.25, "hf": 0.5, "ff": 0.75}   # 横向步序：左后、左前、右后、右前
    stride = 6.0
    frames = []
    for i in range(n):
        t = i / n
        feet = gait_feet(t, offs, 0.62, stride, 1.6)
        bob = 0.5 if i % 4 in (1, 2) else 0.0
        head = (2.6, -6.2 + (0.5 if i % 4 in (2, 3) else 0.0))
        p = Pose(feet=feet, bob=bob, head=head, nose=0.35, tail=0.1)
        frames.append(draw_quad(DEER, p, DEER_SIZE, DEER_CX))
    return frames, stride / (0.62 * n)


STAND = {"hn": (-0.6, 0), "hf": (0.6, 0), "fn": (0.4, 0), "ff": (-0.4, 0)}


def deer_graze():
    """低头吃草：头埋在前腿前面的地上，2 帧（头点一下），中间夹一帧尾巴甩。"""
    out = []
    for dy, tail in ((0.0, 0.0), (0.6, 0.0), (0.0, 0.0), (0.0, 0.4)):
        p = Pose(feet=STAND, head=(3.4, 7.6 + dy), nose=1.3, tail=tail)
        out.append(draw_quad(DEER, p, DEER_SIZE, DEER_CX))
    return out


def deer_lookup():
    """抬头：低头 → 脖子半抬 → 抬头警觉（耳朵竖起来、尾巴翘一下）。最后一帧在 Godot 里停一会儿。"""
    seq = [Pose(feet=STAND, head=(3.2, 1.0), nose=0.9, tail=0.0),
           Pose(feet=STAND, head=(2.6, -5.0), nose=0.45, tail=0.2),
           Pose(feet=STAND, head=(2.0, -6.2), nose=0.15, tail=0.6, ears=1.0)]
    return [draw_quad(DEER, p, DEER_SIZE, DEER_CX) for p in seq]


TURN_MS = 75


def deer_turn():
    """受惊转身：5 个姿势 7 帧（扭头、人立各停两拍），每帧 TURN_MS。
    扭头往后看 → 后腿一沉、身子微微转过来 → 前半身人立、前腿收起、头甩向新方向 →
    （人立的时候在空中转过去）前腿落在另一边 → 后腿收到肚子下压低，准备起跳。
    不画正对镜头的那一帧（剪影会变成一根竖条），转身发生在人立和落地两帧之间：
    人立那帧还是 38° 的斜侧面，落地那帧已经是 145°。最后一帧差不多就是翻转过来的侧面，
    Godot 里这时翻转精灵，接奔跑的第 3 帧（后腿蹬地）。"""
    R = math.radians
    seq = [
        # 扭头：身体不动，脖子和头转过去往后看（head_yaw = 180°），尾巴竖起
        Pose(feet=STAND, head=(1.6, -6.0), nose=0.1, tail=1.0, ears=1.0, head_yaw=R(180)),
        # 后腿一沉，前脚抬起一点，身子开始往镜头这边转
        Pose(feet={"hn": (0.8, 0), "hf": (1.6, 0), "fn": (1.2, 1.2), "ff": (0.2, 0)}, bob=1.0, pitch=-1.4,
             head=(2.0, -5.6), nose=0.1, tail=1.0, ears=1.0, yaw=R(20), head_yaw=R(182)),
        # 人立：后腿撑在身子下面，前半身抬到最高、前腿收起，头甩向新方向
        Pose(feet={"hn": (2.2, 0), "hf": (3.0, 0), "fn": (2.5, 5.5), "ff": (0.5, 4.6)}, bob=1.2, pitch=-4.2,
             head=(2.4, -5.0), nose=-0.15, tail=1.0, ears=1.0, yaw=R(38), head_yaw=R(190)),
        # 前腿落在另一边，前半身压下来
        Pose(feet={"hn": (-1.0, 0.0), "hf": (0.0, 0.8), "fn": (4.5, 1.2), "ff": (3.0, 0)}, bob=0.8, pitch=0.8,
             head=(3.4, -4.4), nose=0.3, tail=1.0, ears=0.6, yaw=R(145)),
        # 后腿收到肚子下压低，前腿撑地，准备起跳（≈ 翻过来的侧面）
        Pose(feet={"hn": (3.5, 0), "hf": (2.5, 0), "fn": (-0.5, 0), "ff": (0.5, 0)}, bob=1.4, pitch=-0.4,
             head=(3.2, -4.8), nose=0.35, tail=1.0, ears=0.3, yaw=R(168), arch=0.6, stretch=-0.05),
    ]
    out = []
    for p in seq:
        r = []
        out.append(draw_quad(DEER, p, DEER_SIZE, DEER_CX, report=r))
        for m in r:
            print("!! turn:", m)
    return [out[0], out[0], out[1], out[2], out[2], out[3], out[4]]


# ---------------------------------------------------------------- 驼鹿（很大、很慢、很淡）

MK = 1.4   # 驼鹿按这个比例放大（骨架数字是按 1 倍写的）


def moose_extras(pen_body, pen, pose, hb, tip, bp):
    # 驼鹿的长脸往下垂、鼻头大；喉下一撮垂肉；掌状的宽角往两边、往后张开（侧面看是一块横的板，上沿有几个齿）
    k = MK
    pen.taper((hb[0] + 1.0 * k, hb[1] + 0.5 * k), (tip[0], tip[1] + 0.6 * k), 3.0 * k, 2.2 * k, A, n=5)
    pen.seg((hb[0] + 0.6 * k, hb[1] + 1.8 * k), (hb[0] + 0.3 * k, hb[1] + 4.4 * k), 2, A)     # 垂肉
    pen.dot(hb[0] - 1.4 * k, hb[1] - 1.6 * k, 0, A)                                            # 耳朵
    # 掌状角：侧面看两片角掌一前一后，中间低、两头翘，像一只浅碗，上沿一排齿
    rows = ["x.x.x.....x.x",
            "xxxxx....xxxx",
            ".xxxxx..xxxx.",
            "..xxxxxxxxx..",
            "....xxxxx...."]
    X, Y = pen.px(hb[0] - 0.4 * k, hb[1] - 1.2 * k)
    x0, y0 = int(round(X)) - len(rows[0]) // 2, int(round(Y)) - len(rows) + 1
    for dy, r in enumerate(rows):
        for dx, ch in enumerate(r):
            if ch == "x":
                pen.c.put(x0 + dx, y0 + dy, A)


def _k(pts, k=MK):
    return [(x * k, y * k) for x, y in pts]


MOOSE = Body(
    torso=_k([(-2.6, -19.6), (-0.8, -21.6), (4.0, -21.4), (8.0, -22.4), (11.0, -24.8), (14.0, -24.4),
              (16.2, -21.6), (16.4, -17.4), (14.0, -14.4), (10.0, -15.0), (5.0, -15.2), (2.0, -14.6),
              (-1.6, -15.2), (-2.8, -17.2)]),   # 肩上高高的驼峰，屁股低
    hip=(1.0 * MK, -17.0 * MK), shoulder=(12.2 * MK, -16.4 * MK),
    hind=(7.4 * MK, 9.7 * MK, 5.0, 2), fore=(7.0 * MK, 9.5 * MK, 4.0, 2),
    neck_root=(14.0 * MK, -20.4 * MK), neck_w=(6.0, 4.4), head_len=5.2 * MK, head_w=(4.4, 3.4),
    leg_z=1.8 * MK, half_w=3.4 * MK, extras=moose_extras,
)
MOOSE_SIZE = (66, 52)
MOOSE_CX = 32


def moose_walk(n=8):
    offs = {"hn": 0.0, "fn": 0.25, "hf": 0.5, "ff": 0.75}
    stride = 13.0
    frames = []
    for i in range(n):
        t = i / n
        feet = gait_feet(t, offs, 0.64, stride, 2.6)
        bob = 0.5 if i % 4 in (1, 2) else 0.0
        head = (3.0 * MK, -2.6 * MK + (0.5 if i % 4 in (2, 3) else 0.0))
        p = Pose(feet=feet, bob=bob, head=head, nose=1.0)
        frames.append(draw_quad(MOOSE, p, MOOSE_SIZE, MOOSE_CX))
    return frames, stride / (0.64 * n)


# ---------------------------------------------------------------- 狐狸（中远层，小跑）

def fox_extras(pen, hp, pose, hb, tip, bp):
    hp.dot(hb[0] - 0.6, hb[1] - 1.4, 0, A)        # 两只尖耳朵，各一个像素
    hp.dot(hb[0] + 0.6, hb[1] - 1.4, 0, A)
    # 大尾巴：从屁股往后拖，几乎水平，尾巴尖一点点上翘；一边跑一边轻轻上下
    r0 = (-1.6, bp(-1.0, -5.6)[1])
    wob = pose.tail
    pen.taper(r0, (-5.0, r0[1] + 0.4 + wob), 2.2, 2.6, A, n=5)
    pen.taper((-5.0, r0[1] + 0.4 + wob), (-8.2, r0[1] - 0.2 + wob * 0.5), 2.6, 1.0, A, n=5)


FOX = Body(
    torso=[(-1.4, -6.6), (0.6, -7.4), (4.0, -7.2), (7.0, -7.6), (8.4, -6.4), (8.0, -4.6), (6.0, -4.2),
           (3.0, -4.6), (0.4, -4.2), (-1.4, -5.0)],
    hip=(0.5, -5.6), shoulder=(6.6, -5.4),
    hind=(3.0, 3.2, 2.0), fore=(2.8, 3.2, 1.4),
    neck_root=(7.8, -6.6), neck_w=(2.4, 2.2), head_len=3.2, head_w=(2.6, 1.0),
    leg_z=0.8, half_w=1.6, extras=fox_extras,
)
FOX_SIZE = (28, 16)
FOX_CX = 14


def fox_trot(n=6):
    offs = {"hn": 0.0, "ff": 0.0, "hf": 0.5, "fn": 0.5}    # 对角两条腿一起
    stride, duty = 6.0, 0.38
    frames = []
    for i in range(n):
        t = i / n
        feet = gait_feet(t, offs, duty, stride, 1.4)
        bob = 0.5 if i % 3 == 1 else 0.0
        p = Pose(feet=feet, bob=bob, head=(1.4, -1.0), nose=0.2, tail=0.5 if i % 3 == 2 else 0.0)
        frames.append(draw_quad(FOX, p, FOX_SIZE, FOX_CX))
    return frames, stride / (duty * n)


# ---------------------------------------------------------------- 鸟（一只 5×4，扇翅 4 帧：上、平、下、平）

BIRD_ROWS = [
    ["x...x",
     ".x.x.",
     "..x..",
     "....."],
    [".....",
     "xxxxx",
     "..x..",
     "....."],
    [".....",
     "..x..",
     ".xxx.",
     "x...x"],
    [".....",
     ".xxx.",
     "x.x.x",
     "....."],
]


BIRD_SMALL = [["x.x", ".x.", "..."], ["...", "xxx", "..."], ["...", ".x.", "x.x"], ["...", "xxx", "..."]]


def bird_flap():
    # 远侧那只翅膀（左半边，飞向右时在后面）用灰，扇的时候看得出两片翅膀
    out = []
    for rows in BIRD_ROWS:
        c = Canvas.from_rows(rows, {"x": A})
        out.append(c.a)
    return out


# ---------------------------------------------------------------- 渡鸦（中远层，8~14 像素，扇几下、滑一段）

# 逐像素手写（14×12，朝右）：身体每帧一样，只换翅膀。x = 身体 / 近侧翅膀（白），o = 远侧翅膀（灰）。
# 渡鸦和乌鸦的区别：头大、喙粗，尾巴末端是楔形（比尾根宽）。翼尖分开的「指」用缺口表示。
# 程序投影的 3D 翅膀试过：侧面看翅膀只是一片竖鳍，读不出是鸟，所以改成手写。
RAVEN_BODY = [
    "..............",
    "..............",
    "..............",
    "..............",
    "..........xx..",
    "xx..xxxxxxxxx.",
    "xxxxxxxxxxxxxx",
    "xx..xxxxxxx...",
    "..............",
    "..............",
    "..............",
    "..............",
]
# 每帧的翅膀：{行号: 那一行}。扇一圈 6 帧（最高 → 下扑 → 平 → 最低 → 收翅上扬 → 上扬）+ 滑翔 1 帧
RAVEN_WINGS = [
    {0: "..x.x.........",
     1: "..xxxx.o......",
     2: "...xxxx.o.....",
     3: "....xxxxoo....",
     4: ".....xxxx.....",
     5: "......xx......"},
    {2: "x.x...........",
     3: "xxxxx.....o...",
     4: ".xxxxxxx.oo...",
     5: "....xxxx......"},
    {7: "....xxxxxx....",
     8: ".....xxxxx....",
     9: "......x.x.....",
     4: "........oo...."},
    {7: "....xxxxx.....",
     8: ".....xxxx.....",
     9: "....xxxx......",
     10: "...xxx........",
     11: "...x.x........"},
    {3: ".....x.x......",
     4: ".....xxxxo....",
     5: "......xxx....."},
    {1: "...x..........",
     2: "...xx.x.......",
     3: "....xxxxo.....",
     4: ".....xxxxo....",
     5: "......xxx....."},
    {3: "........oo....",
     4: ".xxxxxxxx.....",
     5: "x.xxxxx......."},
]
RAVEN_SIZE = (14, 12)


def raven_frame(wing):
    rows = [list(r) for r in RAVEN_BODY]
    for y, r in wing.items():
        for x, ch in enumerate(r):
            if ch == "x":
                rows[y][x] = "x"
            elif ch == "o" and rows[y][x] == ".":
                rows[y][x] = "o"
    return Canvas.from_rows(["".join(r) for r in rows], {"x": A, "o": B}).a


def raven_fly():
    return [raven_frame(w) for w in RAVEN_WINGS]


# ---------------------------------------------------------------- 枝头的小鸟（停着 → 忽然一起飞走）

PERCH_ROWS = [
    ["..x.",
     ".xxx",
     "xxx.",
     "x..."],
    ["....",
     "..xx",
     "xxx.",
     "x..."],
    ["..x.",
     ".xx.",
     "xxx.",
     ".x.."],
]


def bird_perch():
    return [Canvas.from_rows(r, {"x": A}).a for r in PERCH_ROWS]


# ---------------------------------------------------------------- 输出

def check_alpha(frames):
    for f in frames:
        assert set(np.unique(f[..., 3]).tolist()) <= {0, 255}


def save(name, frames, dur, meta=None):
    check_alpha(frames)
    p = write_sheet(frames, OUT / f"{name}.png", durations=[dur] * len(frames))
    if meta:
        d = json.loads(p.with_suffix(".json").read_text())
        d["meta"]["shadow"] = meta
        p.with_suffix(".json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    return frames


def tint(frames, body=(36, 52, 44), fog=(84, 116, 98), bg=None):
    """预览用：白 → 影子色，灰 → 往雾色靠 30%，背景铺雾色。"""
    bg = fog if bg is None else bg
    out = []
    for f in frames:
        o = np.zeros_like(f)
        o[..., :3] = bg
        o[..., 3] = 255
        m = f[..., 3] > 0
        t = f[..., 0].astype(float) / 255.0
        for ch in range(3):
            v = fog[ch] + (body[ch] - fog[ch]) * t
            o[..., ch][m] = np.round(v[m]).astype(np.uint8)
        out.append(o)
    return out


def strip(frames, path, scale=8, gap=2, bg=(84, 116, 98), cols=4):
    """逐帧排开（每行 cols 帧），放大 scale 倍。"""
    H, W = frames[0].shape[:2]
    rows = (len(frames) + cols - 1) // cols
    cols = min(cols, len(frames))
    s = np.zeros(((H + gap) * rows, (W + gap) * cols, 4), np.uint8)
    s[..., :3] = (bg[0] - 14, bg[1] - 14, bg[2] - 14)
    s[..., 3] = 255
    for i, f in enumerate(frames):
        r, q = divmod(i, cols)
        s[r * (H + gap):r * (H + gap) + H, q * (W + gap):q * (W + gap) + W] = f
    Canvas(s.shape[1], s.shape[0], s).save(path, scale)


def game_colors(ground, h, k, sky=OUT.parent / "forest" / "sky.png", ink=(8, 16, 13)):
    """和 forest_shadows.gd 一样算颜色：天空层那一行的平均色 = 雾色，往 ink 推 k。"""
    from PIL import Image
    a = np.array(Image.open(sky).convert("RGB")).astype(float)
    y = int(ground - h * 0.55)
    fog = a[y].mean(0)
    body = fog + (np.array(ink) - fog) * k
    return tuple(int(round(v)) for v in body), tuple(int(round(v)) for v in fog)


def build(preview: Path | None):
    OUT.mkdir(parents=True, exist_ok=True)
    run, _, run_v = deer_run()
    walk, walk_v = deer_walk()
    graze, look, turn = deer_graze(), deer_lookup(), deer_turn()
    mw, moose_v = moose_walk()
    ft, fox_v = fox_trot()
    birds = bird_flap()
    raven, perch = raven_fly(), bird_perch()
    # 每帧前进的像素（着地的脚往后退多少，身体就往前多少）。Godot 里每换一帧精灵往前跳这么多（不是匀速滑），
    # 着地的脚才钉在地上不动。
    save("deer_run", run, RUN_MS, {"px_per_frame": round(run_v, 3), "foot_y": DEER_SIZE[1] - 1})
    save("deer_walk", walk, 100, {"px_per_frame": round(walk_v, 3), "foot_y": DEER_SIZE[1] - 1})
    save("deer_graze", graze, 200, {"foot_y": DEER_SIZE[1] - 1})
    save("deer_lookup", look, 120, {"foot_y": DEER_SIZE[1] - 1})
    save("deer_turn", turn, TURN_MS, {"foot_y": DEER_SIZE[1] - 1})
    save("moose_walk", mw, 150, {"px_per_frame": round(moose_v, 3), "foot_y": MOOSE_SIZE[1] - 1})
    save("fox_trot", ft, 90, {"px_per_frame": round(fox_v, 3), "foot_y": FOX_SIZE[1] - 1})
    save("bird_flap", birds, 90)
    small = [Canvas.from_rows(r, {"x": A}).a for r in BIRD_SMALL]
    save("bird_small", small, 80)
    save("raven_fly", raven, 85)     # 0~5 扇翅一圈，6 滑翔
    save("bird_perch", perch, 200)   # 停着：0 平常、1 低头、2 抬头张望
    print("deer run %.2f px/frame, walk %.2f, moose %.2f, fox %.2f" % (run_v, walk_v, moose_v, fox_v))
    if preview:
        preview.mkdir(parents=True, exist_ok=True)
        strip(tint(run), preview / "deer_run_strip.png")
        strip(tint(walk), preview / "deer_walk_strip.png")
        strip(tint(graze + look + turn + [f[:, ::-1] for f in run[:2]]), preview / "deer_graze_turn_strip.png")
        strip(tint(mw, body=(66, 92, 77)), preview / "moose_walk_strip.png", scale=6)
        strip(tint(ft, body=(22, 34, 28), fog=(48, 66, 56)), preview / "fox_trot_strip.png", bg=(48, 66, 56))
        strip(tint(birds), preview / "bird_strip.png", scale=12)
        strip(tint(raven), preview / "raven_strip.png", scale=12, cols=7)
        write_gif(tint(raven[:6] * 3 + [raven[6]] * 8), preview / "raven_8x.gif", scale=8, durations=[85] * 26)
        body, fog = game_colors(193, DEER_SIZE[1], 0.56)
        write_gif(tint(run, body, fog), preview / "deer_run_8x.gif", scale=8, durations=[RUN_MS] * len(run))
        rf = [f[:, ::-1] for f in run]
        seq = graze * 2 + look + turn + rf[3:] + rf
        dur = [200] * 8 + [120] * 3 + [1000] + [TURN_MS] * len(turn) + [RUN_MS] * (len(rf) - 3 + len(rf))
        write_gif(tint(seq), preview / "deer_graze_turn_8x.gif", scale=8, durations=dur)
        write_gif(tint(mw, body=(66, 92, 77)), preview / "moose_walk_6x.gif", scale=6, durations=[150] * len(mw))
        write_gif(tint(ft, body=(22, 34, 28), fog=(48, 66, 56)), preview / "fox_trot_8x.gif", scale=8)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="放大预览（条带 + GIF）存到这个目录")
    a = ap.parse_args()
    build(Path(a.preview) if a.preview else None)
