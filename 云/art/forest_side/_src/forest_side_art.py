"""第一关支线 side-a 的小游戏特写面板（scripts/side_pine.gd / side_radio.gd / side_sign.gd / side_lamp.gd）。

跑法（在项目根目录）：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" art/forest_side/_src/forest_side_art.py [预览.png]
输出到 art/forest_side/；给一个路径参数另存一张 3 倍预览。坐标都是 1 倍像素，和脚本里的常量一一对应。

  pine_panel.png   232×150  老松树树干特写：树皮一块块的板、正中一道割口（松脂从 (116,63) 滴下来）、底下树根托着罐子
  pine_jar_back.png 30×36   罐子里面（暗的玻璃底），罐子放在 (101,102)
  pine_jar_front.png 30×36  罐子玻璃（边、高光、暖红的刻度线），里面透明好看见松脂；罐内 x 3..26、y 6..33
  pine_lid.png     26×6     盖子（接好以后盖上）
  radio_panel.png  232×150  收音机正面：木壳、上面一长条刻度窗（18..214, 14..38）、左边喇叭布、右边猫眼灯 (187,64) 和旋钮 (187,108)
  radio_knob.png   30×30    旋钮（指示刻痕脚本画，跟着转）
  sign_panel.png   232×150  从上往下看的空地：草地、正中树桩底座 (116,75)
  sign_icons.png   128×16   八个方向的图标（每个 16×16）：云 / 老松 / 树屋 / 雾 / 你（两个鞋印）/ 小吃棚 / 空地 / 商店
  lamp_panel.png   232×150  空屋里面：竖木板墙、左上窗户、底下窗台，灯在 (40,124)
  lamp_lit.png     232×150  同一面墙被灯照亮（按离灯远近分四档，档的边落在木板缝上），脚本按灯光亮度叠上去
  lamp.png         32×26    油灯两帧（没点 / 点着，玻璃罩里亮），一帧 16×26，灯芯在帧里 (8,12)
  lamp_shadows.png 192×52   墙上的影子（白色剪影，脚本染色）：一格 32×52，大人甲 站 / 挥手、大人乙 站 / 挥手、小孩 弯腰摸地上 / 比划一个背包
  lamp_hands.png   96×24    手影：兔子 / 鸟 / 狗（白色剪影，一格 32×24）
  radio_eye.png    232×150  猫眼灯亮起来的那层
  icon_menu.png    12×13    背包图标：小吃棚的旧菜单
  icon_key.png     14×10    背包图标：小屋的钥匙

画法：色块派（小奥斯卡 skill）：大平面、光从左上来、相邻块只差一档、不描边、没有半透明、没有虚线点线、正面平视没有透视。
配色取自森林现有的图（pine_sap / empty_house / room_radio / icon_sap），暖红点缀用第一关的 #c9473a / #e8795a。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "art" / "forest_side"


def hx(s: str) -> tuple:
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)


F = [hx(c) for c in ["#0b110f", "#121b17", "#1b2420", "#252e29", "#2f3833", "#3b423d", "#464c47", "#555a52"]]
G = [hx(c) for c in ["#16241c", "#1e3226", "#26392c", "#2f4335", "#3f5041", "#4f6450"]]
W = [hx(c) for c in ["#150e0a", "#1f1610", "#2c2118", "#3a2c20", "#4d3a2a", "#634a34", "#7a5c40", "#94744f"]]
SAP = [hx(c) for c in ["#5a3a1c", "#7d552f", "#a8642e", "#c8823c", "#e8b860", "#f0d28c"]]
GL = [hx(c) for c in ["#1e2c2a", "#2c3e3c", "#4a6260", "#7d9894", "#b6ccc6", "#e2ece6"]]
HOT = [hx(c) for c in ["#4a2226", "#962f2c", "#c9473a", "#e8795a", "#f0c070"]]
WALL = [hx(c) for c in ["#161c1d", "#1b2122", "#242b2c", "#2d3536", "#373f40"]]
LIT = [hx(c) for c in ["#2f2a24", "#463628", "#634a32", "#82623e", "#a07c4c"]]   # 被灯照着的木板（暗 → 亮）
CLOTH = [hx(c) for c in ["#241f17", "#2e281d", "#3a3326", "#463e2c"]]
DIAL = [hx(c) for c in ["#4d3a20", "#6b5430", "#8a7244", "#a88c58"]]
WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)


class Img:
    def __init__(self, w: int, h: int, fill=CLEAR):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)
        self.a[:, :] = fill

    def put(self, x: int, y: int, c) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = c

    def rect(self, x0: int, y0: int, w: int, h: int, c) -> None:
        x1, y1 = min(self.w, x0 + w), min(self.h, y0 + h)
        x0, y0 = max(0, x0), max(0, y0)
        if x1 > x0 and y1 > y0:
            self.a[y0:y1, x0:x1] = c

    def fill(self, m: np.ndarray, c) -> None:
        self.a[m] = c

    def grid(self):
        return np.mgrid[0:self.h, 0:self.w]

    def save(self, name: str) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        Image.fromarray(self.a, "RGBA").save(OUT / name)


def disk(img: Img, cx: float, cy: float, r: float) -> np.ndarray:
    yy, xx = img.grid()
    return (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2 <= r * r


def ell(img: Img, cx: float, cy: float, rx: float, ry: float) -> np.ndarray:
    yy, xx = img.grid()
    return ((xx + 0.5 - cx) / rx) ** 2 + ((yy + 0.5 - cy) / ry) ** 2 <= 1.0


def poly(img: Img, pts) -> np.ndarray:
    """整像素多边形（像素中心在里面就算）"""
    yy, xx = img.grid()
    px, py = xx + 0.5, yy + 0.5
    inside = np.zeros((img.h, img.w), bool)
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if y0 == y1:
            continue
        cond = (py >= min(y0, y1)) & (py < max(y0, y1))
        xi = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
        inside ^= cond & (px < xi)
    return inside


def lit(img: Img, m: np.ndarray, ramp, lo: int, cuts=(0.35, 0.72), tilt=0.6) -> None:
    """一块平面按左上来的光切成三块直边的面：左上亮一档、中间、右下暗一档。"""
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    yy, xx = img.grid()
    u = ((xx - x0) / max(1, x1 - x0) + tilt * (yy - y0) / max(1, y1 - y0)) / (1 + tilt)
    for k, (a, b) in enumerate([(-1, cuts[0]), (cuts[0], cuts[1]), (cuts[1], 2)]):
        lv = min(len(ramp) - 1, max(0, lo + 1 - k))
        img.fill(m & (u > a) & (u <= b), ramp[lv])


def edges(m: np.ndarray) -> np.ndarray:
    e = np.zeros_like(m)
    e[1:, :] |= m[1:, :] & ~m[:-1, :]
    e[:-1, :] |= m[:-1, :] & ~m[1:, :]
    e[:, 1:] |= m[:, 1:] & ~m[:, :-1]
    e[:, :-1] |= m[:, :-1] & ~m[:, 1:]
    e[0, :] |= m[0, :]
    e[-1, :] |= m[-1, :]
    e[:, 0] |= m[:, 0]
    e[:, -1] |= m[:, -1]
    return e


def over(dst: np.ndarray, src: np.ndarray, x: int, y: int) -> None:
    h, w = src.shape[:2]
    reg = dst[y:y + h, x:x + w]
    a = src[: reg.shape[0], : reg.shape[1], 3:4] > 0
    reg[:] = np.where(a, src[: reg.shape[0], : reg.shape[1]], reg)


# ======================================================================= 老松树
def bark(img: Img, m: np.ndarray, x0: int, x1: int, seed: int) -> None:
    """树皮：竖长的一块块板，左边受光亮、右边暗；板和板之间的缝只暗一档、连续的。"""
    rng = np.random.default_rng(seed)
    seeds = []
    for gy in range(-1, img.h // 26 + 2):
        for gx in range(-1, (x1 - x0) // 16 + 2):
            seeds.append((x0 + gx * 16 + rng.uniform(2, 14) + (8 if gy % 2 else 0), gy * 26 + rng.uniform(3, 23)))
    sd = np.array(seeds)
    yy, xx = img.grid()
    d = ((xx[..., None] - sd[:, 0]) * 1.0) ** 2 + ((yy[..., None] - sd[:, 1]) * 0.42) ** 2
    cid = np.argmin(d, axis=2)
    crack = np.zeros_like(m)
    crack[:, 1:] |= cid[:, 1:] != cid[:, :-1]
    crack[1:, :] |= cid[1:, :] != cid[:-1, :]
    u = np.clip((xx - x0) / max(1, x1 - x0), 0, 1)
    jitter = rng.integers(-1, 2, size=len(seeds))
    for i in range(len(seeds)):
        cm = m & (cid == i)
        if not cm.any():
            continue
        cx = sd[i, 0]
        base = 5 - int(round(3.2 * np.clip((cx - x0) / max(1, x1 - x0), 0, 1)))
        lv = int(np.clip(base + jitter[i] * (1 if 0.2 < (cx - x0) / max(1, x1 - x0) < 0.8 else 0), 2, 6))
        img.fill(cm, F[lv])
        img.fill(cm & crack, F[max(1, lv - 1)])
    # 树干两侧边缘暗一档（圆柱）
    img.fill(m & (u > 0.9), F[2])
    img.fill(m & (u < 0.03), F[4])


def pine_panel() -> Img:
    img = Img(232, 150, F[0])
    yy, xx = img.grid()
    # 远处两棵树
    img.fill((xx >= 6) & (xx < 24), F[1])
    img.fill((xx >= 204) & (xx < 218), F[1])
    img.fill((xx >= 204) & (xx < 207), F[2])
    # 主干：上窄下宽，底下根盘开
    left = 66 - np.clip((yy - 96) * 0.35, 0, 30)
    right = 166 + np.clip((yy - 96) * 0.32, 0, 30)
    trunk = (xx >= left) & (xx < right)
    bark(img, trunk, 62, 172, 7)
    # 地面：苔藓，上沿不规则
    ground = yy >= 136 + np.round(2 * np.sin(xx * 0.11) + np.sin(xx * 0.37))
    img.fill(ground, G[1])
    img.fill(ground & (yy < 140 + np.round(np.sin(xx * 0.2))), G[2])
    img.fill(ground & trunk, G[0])
    # 托罐子的树根（一块平的根瘤）
    root = ell(img, 116, 140, 26, 5) & (yy >= 137)
    img.fill(root, W[3])
    img.fill(root & (yy == 137), W[4])
    img.fill(root & (xx > 128), W[2])
    # 割口：杏仁形，里面露出浅色的木头
    cut = ell(img, 116, 46, 5.5, 13)
    img.fill(cut, W[6])
    img.fill(cut & (xx >= 117), W[5])
    img.fill(edges(cut) & (xx < 116), W[4])
    img.fill(edges(cut) & (xx >= 116), W[2])
    # 割口下沿挂着的松脂和往下流的一道
    bead = ell(img, 116, 58, 3.2, 3.6)
    img.fill(bead, SAP[3])
    img.fill(bead & (xx < 116) & (yy < 58), SAP[4])
    img.rect(116, 60, 1, 3, SAP[2])
    img.put(115, 57, SAP[5])
    # 割口上方一小片旧的松脂痕（干了的）
    old = ell(img, 113, 30, 2, 4)
    img.fill(old, SAP[1])
    return img


def jar() -> tuple:
    back = Img(30, 36)
    front = Img(30, 36)
    yy, xx = back.grid()
    body = (xx >= 1) & (xx <= 28) & (yy >= 5) & (yy <= 35)
    body &= ~(((xx <= 2) | (xx >= 27)) & (yy >= 34))          # 底下两个角圆一点
    body &= ~(((xx <= 1) | (xx >= 28)) & (yy <= 5))
    inner = (xx >= 3) & (xx <= 26) & (yy >= 6) & (yy <= 33)
    back.fill(body, GL[0])
    back.fill(inner & (xx >= 18), GL[1])
    # 罐口（上面一圈唇）
    lip = (xx >= 2) & (xx <= 27) & (yy >= 2) & (yy <= 5)
    front.fill(lip, GL[3])
    front.fill(lip & (yy == 2), GL[4])
    front.fill(lip & (xx >= 20), GL[2])
    # 玻璃的边：左边受光、右边背光、底
    wall = body & ~inner & ~lip
    front.fill(wall, GL[2])
    front.fill(wall & (xx <= 2), GL[3])
    front.fill(wall & (xx >= 27), GL[1])
    front.fill(wall & (yy >= 34), GL[1])
    # 高光：左边一道连续的竖线
    front.rect(5, 9, 1, 16, GL[5])
    front.rect(6, 9, 1, 3, GL[4])
    # 刻度线：从罐底往上 20 格（y = 13），暖红一整条，左边伸出一个小舌头
    front.rect(3, 13, 24, 1, HOT[2])
    front.rect(1, 12, 3, 3, HOT[3])
    front.put(1, 14, HOT[2])
    lid = Img(26, 6)
    ly, lx = lid.grid()
    lm = (lx >= 0) & (ly >= 1)
    lm &= ~(((lx == 0) | (lx == 25)) & (ly == 1))
    lid.fill(lm, W[4])
    lid.fill(lm & (ly <= 2), W[6])
    lid.fill(lm & (lx >= 19), W[3])
    lid.rect(10, 0, 6, 1, W[5])
    return back, front, lid


# ======================================================================= 收音机
def radio_panel() -> tuple:
    img = Img(232, 150)
    yy, xx = img.grid()
    case = (xx >= 4) & (xx <= 227) & (yy >= 2) & (yy <= 141)
    # 上面两个角是圆的（老式收音机的拱顶）
    for cx in (18, 213):
        corner = ((xx < 18) if cx == 18 else (xx > 213)) & (yy < 16)
        case &= ~(corner & ~disk(img, cx + 0.5, 16.5, 15))
    lit(img, case, W, 4, cuts=(0.25, 0.8))
    img.fill(edges(case) & (yy < 70) & (xx < 116), W[6])
    img.fill(edges(case) & ((xx > 200) | (yy > 120)), W[2])
    # 脚
    for fx in (16, 202):
        img.rect(fx, 142, 14, 6, W[2])
        img.rect(fx, 142, 14, 1, W[3])
    # 刻度窗：框 + 暖黄的底（老收音机刻度盘里有灯）
    img.rect(16, 12, 200, 29, W[2])
    img.rect(16, 12, 200, 1, W[1])
    img.rect(16, 40, 200, 1, W[5])
    img.rect(18, 14, 196, 25, DIAL[2])
    img.rect(18, 14, 196, 6, DIAL[3])
    img.rect(150, 14, 64, 25, DIAL[1])                        # 右边灯照不到，暗一档
    img.rect(150, 14, 64, 6, DIAL[2])
    # 刻度：老收音机的刻度是不等距的（越往右越密），长短不一
    for i, x in enumerate((24, 52, 76, 97, 115, 131, 145, 158, 170, 181, 191, 200, 208)):
        h = 9 if i % 2 == 0 else 5
        img.rect(x, 38 - h, 1, h, DIAL[0])
    img.rect(18, 37, 196, 1, DIAL[0])
    # 喇叭布 + 三根木条（中间宽）
    cloth = (xx >= 16) & (xx <= 151) & (yy >= 48) & (yy <= 134)
    img.fill(cloth, CLOTH[2])
    img.fill(cloth & (xx + yy * 0.5 > 120), CLOTH[1])
    img.fill(cloth & (xx + yy * 0.5 > 190), CLOTH[0])
    img.fill(cloth & (xx + yy * 0.5 < 70), CLOTH[3])
    img.rect(16, 46, 136, 2, W[2])
    img.rect(16, 135, 136, 2, W[5])
    for bx, bw in ((50, 5), (80, 9), (114, 5)):
        img.rect(bx, 48, bw, 87, W[4])
        img.rect(bx, 48, 1, 87, W[5])
        img.rect(bx + bw - 1, 48, 1, 87, W[3])
    # 右边：猫眼灯的座、旋钮的座
    eye = disk(img, 187, 64, 11)
    img.fill(eye, W[2])
    img.fill(disk(img, 187, 64, 9), GL[0])
    img.fill(disk(img, 187, 64, 9) & (xx < 184) & (yy < 61), GL[1])
    seat = disk(img, 187, 108, 18)
    img.fill(seat, W[3])
    img.fill(seat & (xx + yy < 187 + 108 - 8), W[5])
    img.fill(seat & (xx + yy > 187 + 108 + 10), W[2])
    # 猫眼灯亮起来的那层（单独存，脚本按信号强弱叠）
    glow = Img(232, 150)
    gm = disk(glow, 187, 64, 9)
    glow.fill(gm, G[4])
    glow.fill(disk(glow, 187, 64, 6), G[5])
    glow.fill(disk(glow, 187, 64, 3), hx("#9fd6b4"))
    glow.fill(gm & (xx < 184) & (yy < 61), hx("#b9e8c8"))
    knob = Img(30, 30)
    ky, kx = knob.grid()
    km = disk(knob, 15, 15, 13)
    knob.fill(km, W[5])
    knob.fill(km & (kx + ky > 32), W[4])
    knob.fill(km & (kx + ky < 22), W[6])
    knob.fill(edges(km) & (kx + ky > 30), W[2])
    knob.fill(disk(knob, 15, 15, 8), W[4])
    knob.fill(disk(knob, 15, 15, 8) & (kx + ky < 28), W[5])
    return img, glow, knob


# ======================================================================= 路标（从上往下看的空地）
SIGN_C = (116, 75)


def sign_panel() -> Img:
    img = Img(232, 150, G[1])
    yy, xx = img.grid()
    u = xx / 232 + 0.7 * yy / 150
    img.fill(u < 0.45, G[2])
    img.fill(u < 0.2, G[3])
    img.fill(u > 1.25, G[0])
    # 踩出来的一圈土（路标转的时候大家围着看）
    cx, cy = SIGN_C
    ring = disk(img, cx, cy, 34) & ~disk(img, cx, cy, 24)
    img.fill(ring, hx("#2e3222"))
    img.fill(ring & (xx + yy < cx + cy - 6), hx("#3a3d2a"))
    img.fill(ring & (xx + yy > cx + cy + 14), hx("#262a1c"))
    # 几簇草（不规则地散着）
    rng = np.random.default_rng(3)
    for _ in range(26):
        gx, gy = rng.integers(4, 228), rng.integers(4, 146)
        if (gx - cx) ** 2 + (gy - cy) ** 2 < 38 ** 2:
            continue
        lv = 4 if gx / 232 + 0.7 * gy / 150 < 0.6 else 3
        img.put(gx, gy, G[lv])
        img.put(gx + 1, gy - 1, G[lv])
        img.put(gx - 1, gy - 1, G[lv - 1])
    # 树桩底座
    stump = disk(img, cx, cy, 11)
    img.fill(stump, W[4])
    img.fill(stump & (xx + yy < cx + cy - 4), W[5])
    img.fill(stump & (xx + yy > cx + cy + 6), W[3])
    ringd = disk(img, cx, cy, 6.5) & ~disk(img, cx, cy, 5.5)
    img.fill(ringd, W[3])
    img.fill(disk(img, cx, cy, 3), W[1])
    return img


def sign_icons() -> Img:
    img = Img(128, 16)
    cell = []
    for i in range(8):
        cell.append(Img(16, 16))
    # 0 云
    c = cell[0]
    m = disk(c, 6, 9, 4) | disk(c, 10, 8, 4.5) | ell(c, 8, 11, 7, 3)
    c.fill(m, hx("#c9d6cf"))
    c.fill(m & (c.grid()[0] >= 11), hx("#94a69c"))
    # 1 老松（从上往下看：一团深绿的针叶，正中树干）
    c = cell[1]
    m = disk(c, 8, 8, 7)
    yy, xx = c.grid()
    c.fill(m, G[3])
    c.fill(m & (xx + yy < 13), G[5])
    c.fill(m & (xx + yy > 19), G[1])
    c.fill(disk(c, 8, 8, 2), W[4])
    c.fill(ell(c, 11, 5, 1.2, 1.6), SAP[4])
    # 2 树屋（屋顶）
    c = cell[2]
    m = poly(c, [(1, 9), (8, 2), (15, 9), (15, 14), (1, 14)])
    c.fill(m, W[5])
    c.fill(m & (xx >= 8), W[4])
    c.fill(m & (yy >= 11), W[3])
    c.rect(6, 10, 4, 4, HOT[3])
    c.rect(6, 10, 4, 1, HOT[4])
    # 3 雾：三道长长的雾带
    c = cell[3]
    for y0, x0, x1, col in ((4, 2, 13, hx("#b6c2bc")), (8, 4, 15, hx("#94a69c")), (12, 1, 11, hx("#7d8c84"))):
        c.rect(x0, y0, x1 - x0, 2, col)
        c.put(x0 - 1, y0 + 1, col)
        c.put(x1, y0, col)
    # 4 你：两个鞋印
    c = cell[4]
    for ox, oy in ((4, 4), (10, 7)):
        sole = ell(c, ox + 0.5, oy + 3, 2.2, 3.4)
        c.fill(sole, hx("#c48fb4"))
        c.fill(sole & (yy < oy + 2), hx("#d8aac8"))
    # 5 小吃棚：条纹雨棚（两色的宽条，不是虚线）
    c = cell[5]
    m = poly(c, [(1, 4), (15, 4), (14, 11), (2, 11)])
    c.fill(m, hx("#8e8a6c"))
    c.fill(m & ((xx // 4) % 2 == 1), hx("#5d6b5a"))
    c.rect(2, 11, 12, 3, W[3])
    c.rect(2, 11, 12, 1, W[4])
    # 6 空地：一圈浅草，中间一朵小花
    c = cell[6]
    m = disk(c, 8, 8, 7)
    c.fill(m, G[4])
    c.fill(m & (xx + yy < 12), G[5])
    c.fill(m & (xx + yy > 20), G[3])
    c.fill(disk(c, 8, 8, 2), hx("#e8d27a"))
    c.put(7, 7, hx("#f4e8b0"))
    # 7 商店：方屋顶 + 门
    c = cell[7]
    m = (xx >= 2) & (xx <= 13) & (yy >= 3) & (yy <= 14)
    c.fill(m, F[6])
    c.fill(m & (xx >= 9), F[5])
    c.fill(m & (yy <= 5), W[5])
    c.rect(6, 9, 4, 6, W[2])
    for i, c in enumerate(cell):
        over(img.a, c.a, i * 16, 0)
    return img


# ======================================================================= 油灯（空屋里）
LAMP_AT = (40, 124)          # 灯座底边中点
FLAME = (40, 110)            # 火苗的位置（面板里）


def planks(seed: int):
    rng = np.random.default_rng(seed)
    xs = [0]
    while xs[-1] < 232:
        xs.append(xs[-1] + int(rng.integers(12, 19)))
    return xs


def lamp_panel() -> tuple:
    dark = Img(232, 150)
    litimg = Img(232, 150)
    yy, xx = dark.grid()
    px = planks(11)
    col = np.zeros((150, 232), int)
    for i in range(len(px) - 1):
        col[:, px[i]:px[i + 1]] = i
    seam = np.zeros((150, 232), bool)
    for x in px[1:-1]:
        if x < 232:
            seam[:, x] = True
    # 不亮的墙：每块板一个底色（2 或 3 档），左上那几块亮一档；缝只暗一档
    rng = np.random.default_rng(5)
    base = rng.integers(2, 4, size=len(px))
    wall_lv = np.take(base, col)
    wall_lv = np.where(xx + yy * 0.6 < 60, np.minimum(wall_lv + 1, 4), wall_lv)
    for lv in range(5):
        dark.fill(wall_lv == lv, WALL[lv])
        dark.fill((wall_lv == lv) & seam, WALL[max(0, lv - 1)])
    # 被灯照的墙：按离火苗的距离分档，档的边按木板一块一块地错开（光落在木板上，边是直的）
    fx, fy = FLAME
    jit = np.take(rng.integers(-6, 7, size=len(px)), col)
    d = np.sqrt((xx - fx) ** 2 * 0.8 + (yy - fy) ** 2 * 1.2) + jit
    band = np.select([d < 34, d < 70, d < 112, d < 160], [4, 3, 2, 1], 0)
    lit_lv = np.clip(band + np.take(base, col) - 3, 0, 4)
    for lv in range(5):
        litimg.fill(lit_lv == lv, LIT[lv])
        litimg.fill((lit_lv == lv) & seam, LIT[max(0, lv - 1)])
    # 两边都有的东西：窗户、窗台（窗台被照亮的那层另算）
    for img, lights in ((dark, False), (litimg, True)):
        frame = (xx >= 12) & (xx <= 60) & (yy >= 14) & (yy <= 62)
        glass = (xx >= 15) & (xx <= 57) & (yy >= 17) & (yy <= 59)
        img.fill(frame, W[4] if lights else W[2])
        img.fill(frame & (yy == 14), W[5] if lights else W[3])
        img.fill(glass, F[1])
        img.fill(glass & (yy > 44), G[0])
        # 窗外：远处几棵树的剪影（暗的平面）
        for tx, tw, top in ((20, 7, 26), (33, 5, 34), (46, 8, 22)):
            img.fill(glass & (xx >= tx) & (xx < tx + tw) & (yy >= top), F[2])
        img.fill(glass & (xx >= 35) & (xx <= 37), W[3] if lights else W[1])        # 窗棂
        img.fill(glass & (yy >= 37) & (yy <= 39), W[3] if lights else W[1])
        img.fill(disk(img, 50, 25, 3) & glass, hx("#c9d6cf"))                       # 月亮
        sill = (yy >= 124) & (yy <= 149)
        img.fill(sill, W[3] if not lights else W[4])
        img.fill(sill & (yy <= 125), W[4] if not lights else W[6])
        img.fill(sill & (yy >= 140), W[2] if not lights else W[3])
        if lights:
            img.fill(sill & (yy <= 125) & (np.abs(xx - fx) < 30), W[7])
    # 灯
    lamp = Img(32, 26)
    for f in range(2):
        ox = f * 16
        ly, lx = lamp.grid()
        lx = lx - ox
        on = (lx >= 0) & (lx < 16)
        base_m = on & (ly >= 21) & (ly <= 25) & (lx >= 2) & (lx <= 13)
        lamp.fill(base_m, W[5])
        lamp.fill(base_m & (ly == 21), W[6])
        lamp.fill(base_m & (lx >= 10), W[4])
        tank = on & ell(lamp, ox + 8, 19, 6, 3)
        lamp.fill(tank, SAP[1] if f == 0 else SAP[2])
        lamp.fill(tank & (lx < 6) & (ly < 19), SAP[2] if f == 0 else SAP[3])
        globe = on & ell(lamp, ox + 8, 10, 4.5, 7)
        lamp.fill(globe, GL[1] if f == 0 else SAP[4])
        lamp.fill(globe & (lx < 6), GL[2] if f == 0 else SAP[5])
        lamp.fill(on & (ly >= 2) & (ly <= 3) & (lx >= 5) & (lx <= 10), W[3])        # 罩顶
        lamp.fill(on & (ly == 1) & (lx >= 6) & (lx <= 9), W[4])
        lamp.fill(on & (lx == 8) & (ly >= 13) & (ly <= 15), W[1] if f == 0 else HOT[2])   # 灯芯
    return dark, litimg, lamp


def figure(img: Img, ox: int, h: int, w: int, pose: str, child=False) -> None:
    """墙上的影子：一个人的剪影（白）。pose = stand 手放下 / wave 举手挥 / search 弯腰摸地上 / mime 两手比划一个背包"""
    yy, xx = img.grid()
    cx = ox + 16
    top = 52 - h
    hr = max(3.2, h * 0.09)
    aw = 2.6 if not child else 2.0
    if pose == "search":
        # 弯着腰：背差不多是横的，头探在前面低着，一只手往地上摸，两条腿直直地站着
        hip = top + h * 0.5
        img.fill(poly(img, [(cx - 7, hip - 3), (cx + 4, top + h * 0.3), (cx + 6, top + h * 0.42), (cx - 5, hip + 3)]), WHITE)
        img.fill(disk(img, cx + 8, top + h * 0.38, hr), WHITE)
        img.fill(poly(img, [(cx - 7, hip), (cx - 2, hip), (cx - 2, 52), (cx - 7, 52)]), WHITE)
        img.fill(poly(img, [(cx + 2, top + h * 0.38), (cx + 5, top + h * 0.4), (cx + 9, 50), (cx + 6, 51)]), WHITE)
        img.fill(disk(img, cx + 8, 50, 1.8), WHITE)
        return
    img.fill(disk(img, cx, top + hr, hr), WHITE)
    neck = top + 2 * hr
    sh = w * 0.5
    img.fill(poly(img, [(cx - sh * 0.8, neck + 1), (cx + sh * 0.8, neck + 1), (cx + sh, 52), (cx - sh, 52)]), WHITE)
    low = neck + h * 0.42

    def arm(x0, y0, x1, y1):
        # 一条连着肩膀的胳膊（四边形，宽 aw），手是末端一个小圆
        dx, dy = x1 - x0, y1 - y0
        n = math.hypot(dx, dy) or 1.0
        px_, py_ = -dy / n * aw / 2, dx / n * aw / 2
        img.fill(poly(img, [(x0 + px_, y0 + py_), (x1 + px_, y1 + py_), (x1 - px_, y1 - py_), (x0 - px_, y0 - py_)]), WHITE)
        img.fill(disk(img, x1, y1, aw * 0.75), WHITE)

    if pose == "mime":
        # 两手在身前比出一个背包：一个空心的方框 + 上面一道背带
        arm(cx - sh * 0.6, neck + 2, cx - 7, neck + h * 0.32)
        arm(cx + sh * 0.6, neck + 2, cx + 7, neck + h * 0.32)
        bx0, by0, bx1, by1 = cx - 7, int(neck + h * 0.2), cx + 7, int(neck + h * 0.6)
        box = (xx >= bx0) & (xx <= bx1) & (yy >= by0) & (yy <= by1)
        hole = (xx >= bx0 + 2) & (xx <= bx1 - 2) & (yy >= by0 + 2) & (yy <= by1 - 2)
        img.fill(box, WHITE)
        img.a[hole] = CLEAR
        strap = disk(img, cx + 0.5, by0, 4.5) & ~disk(img, cx + 0.5, by0, 2.6) & (yy < by0)
        img.fill(strap, WHITE)
        return
    arm(cx - sh * 0.75, neck + 2, cx - sh - 1, low)
    if pose == "wave":
        arm(cx + sh * 0.7, neck + 2, cx + sh + 5, neck - h * 0.2)
    else:
        arm(cx + sh * 0.75, neck + 2, cx + sh + 1, low)


def shadows() -> Img:
    img = Img(192, 52)
    figure(img, 0, 50, 16, "stand")
    figure(img, 32, 50, 16, "wave")
    figure(img, 64, 45, 15, "stand")
    figure(img, 96, 45, 15, "wave")
    figure(img, 128, 32, 11, "search", child=True)
    figure(img, 160, 32, 11, "mime", child=True)
    return img


def hands() -> Img:
    img = Img(96, 24)
    yy, xx = img.grid()
    # 兔子：拳头 + 两只竖耳朵 + 一个眼睛洞
    m = ell(img, 14, 17, 9, 6) | poly(img, [(9, 13), (11, 1), (14, 1), (13, 13)]) | poly(img, [(14, 13), (18, 3), (21, 4), (18, 14)])
    m |= poly(img, [(20, 18), (28, 21), (27, 23), (18, 22)])
    m &= ~disk(img, 11, 16, 1.3)
    img.fill(m, WHITE)
    # 鸟：两只手搭成张开的翅膀，中间一个小头
    ox = 32
    m = poly(img, [(ox + 2, 6), (ox + 14, 14), (ox + 18, 14), (ox + 30, 6), (ox + 28, 11), (ox + 19, 18), (ox + 13, 18), (ox + 4, 11)])
    m |= disk(img, ox + 16, 11, 3)
    m |= poly(img, [(ox + 18, 10), (ox + 22, 11), (ox + 18, 12)])
    m |= poly(img, [(ox + 13, 17), (ox + 19, 17), (ox + 20, 23), (ox + 12, 23)])
    img.fill(m, WHITE)
    # 狗：长脸、垂耳、张着嘴
    ox = 64
    m = ell(img, ox + 12, 11, 8, 6) | poly(img, [(ox + 14, 8), (ox + 29, 10), (ox + 29, 13), (ox + 16, 13)])
    m |= poly(img, [(ox + 15, 15), (ox + 27, 16), (ox + 26, 18), (ox + 14, 18)])
    m |= poly(img, [(ox + 6, 6), (ox + 10, 6), (ox + 8, 16), (ox + 5, 15)])
    m |= poly(img, [(ox + 6, 15), (ox + 16, 15), (ox + 15, 23), (ox + 5, 23)])
    m &= ~disk(img, ox + 15, 9, 1.2)
    img.fill(m, WHITE)
    return img


# ======================================================================= 背包图标（和 art/forest_story/icon_*.png 一样亮一点、10~14 像素）
def icon_menu() -> Img:
    """小吃棚的旧菜单：一张对折过的纸，最上面一行字、一块油渍"""
    img = Img(12, 13)
    yy, xx = img.grid()
    paper = (xx >= 1) & (xx <= 10) & (yy >= 1) & (yy <= 12)
    img.fill(paper, hx("#e2d2a8"))
    img.fill(paper & (xx >= 6), hx("#cbb98c"))                 # 对折的另一半背光
    img.fill(paper & (yy == 12), hx("#a8946c"))
    img.fill(paper & (xx == 10), hx("#a8946c"))
    img.rect(2, 3, 6, 1, hx("#825c3e"))                         # 标题一行
    img.rect(2, 6, 3, 1, hx("#a8946c"))
    img.rect(2, 8, 4, 1, hx("#a8946c"))
    oil = ell(img, 7.5, 9.5, 2.2, 1.8)
    img.fill(oil & paper, hx("#c8a060"))
    img.put(1, 1, CLEAR)
    return img


def icon_key() -> Img:
    """小屋的钥匙：旧铁钥匙，圆柄、短齿，挂着一截细绳"""
    img = Img(14, 10)
    yy, xx = img.grid()
    bow = disk(img, 4, 5, 3.6) & ~disk(img, 4, 5, 1.6)
    img.fill(bow, hx("#847c6c"))
    img.fill(bow & (xx + yy < 8), hx("#a8a090"))
    img.fill(bow & (xx + yy > 11), hx("#5d574c"))
    img.rect(7, 4, 6, 2, hx("#847c6c"))
    img.rect(7, 4, 6, 1, hx("#a8a090"))
    img.rect(10, 6, 1, 2, hx("#5d574c"))
    img.rect(12, 6, 1, 3, hx("#5d574c"))
    img.rect(2, 0, 1, 2, hx("#c48a5a"))                          # 细绳
    img.rect(1, 0, 1, 1, hx("#c48a5a"))
    return img


# ======================================================================= 导出 + 预览
def main() -> None:
    p = pine_panel()
    p.save("pine_panel.png")
    jb, jf, jl = jar()
    jb.save("pine_jar_back.png")
    jf.save("pine_jar_front.png")
    jl.save("pine_lid.png")
    r, rg, rk = radio_panel()
    r.save("radio_panel.png")
    rg.save("radio_eye.png")
    rk.save("radio_knob.png")
    sp = sign_panel()
    sp.save("sign_panel.png")
    si = sign_icons()
    si.save("sign_icons.png")
    ld, ll, lamp = lamp_panel()
    ld.save("lamp_panel.png")
    ll.save("lamp_lit.png")
    lamp.save("lamp.png")
    sh = shadows()
    sh.save("lamp_shadows.png")
    hd = hands()
    hd.save("lamp_hands.png")
    icon_menu().save("icon_menu.png")
    icon_key().save("icon_key.png")
    if len(sys.argv) > 1:
        preview(sys.argv[1], p, jb, jf, jl, r, rg, rk, sp, si, ld, ll, lamp, sh, hd)


def preview(path, p, jb, jf, jl, r, rg, rk, sp, si, ld, ll, lamp, sh, hd) -> None:
    S = 3
    sheet = np.zeros((150 * 2 + 10, 232 * 3 + 20, 4), np.uint8)
    sheet[:, :] = hx("#0e1214")
    a = p.a.copy()
    over(a, jb.a, 101, 102)
    # 松脂到刻度线上一点
    for y in range(102 + 12, 102 + 34):
        a[y, 104:128] = SAP[3]
    a[102 + 12, 104:128] = SAP[4]
    over(a, jf.a, 101, 102)
    sheet[0:150, 0:232] = a
    a = r.a.copy()
    over(a, rg.a, 0, 0)
    over(a, rk.a, 172, 93)
    a[15:38, 120] = HOT[3]
    sheet[0:150, 242:474] = np.where(a[..., 3:4] > 0, a, sheet[0:150, 242:474])
    a = sp.a.copy()
    cx, cy = SIGN_C
    for i in range(8):
        ang = i * math.pi / 4
        ix, iy = int(cx + 54 * math.sin(ang)) - 8, int(cy - 54 * math.cos(ang)) - 8
        iy = max(0, min(134, iy))
        over(a, si.a[:, i * 16:(i + 1) * 16], ix, iy)
    sheet[0:150, 484:716] = a
    a = ll.a.copy()
    over(a, lamp.a[:, 16:32], 32, 98)
    for k, ox in ((1, 96), (3, 128), (5, 168)):
        m = sh.a[:, k * 32:(k + 1) * 32, 3] > 0
        sub = a[64:116, ox:ox + 32]
        sub[m] = hx("#2a1e16")
    m = hd.a[:, 0:32, 3] > 0
    sub = a[30:54, 150:182]
    sub[m] = hx("#2a1e16")
    sheet[160:310, 0:232] = a
    a = ld.a.copy()
    over(a, lamp.a[:, 0:16], 32, 98)
    sheet[160:310, 242:474] = a
    b = np.zeros((150, 232, 4), np.uint8)
    b[:, :] = hx("#c9b58a")
    over(b, sh.a, 4, 4)
    over(b, hd.a, 4, 70)
    over(b, si.a, 4, 110)
    over(b, lamp.a, 140, 70)
    over(b, rk.a, 180, 100)
    over(b, jl.a, 140, 120)
    sheet[160:310, 484:716] = b
    Image.fromarray(sheet, "RGBA").resize((sheet.shape[1] * S, sheet.shape[0] * S), Image.NEAREST).save(path)


if __name__ == "__main__":
    main()
