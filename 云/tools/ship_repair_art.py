"""维修小游戏 ship_repair 的美术（第一关弥洛树屋里修推进器）：推进器内部的特写面板。

跑法：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/ship_repair_art.py [预览.png]
输出到 art/ship_repair/，给一个路径参数会另存一张 4 倍预览（面板 + 盖子 + 零件 + 水管都摆上去）。

图（坐标都是 1 倍像素，脚本 scripts/ship_repair.gd 里的常量和这里一一对应）：
  panel.png       232×150  推进器外壳：左边炉膛（看得见里面的余火）、中间凹槽（放 4×3 水管）、两侧盖子滑轨、
                           右边出口管 + 喷口。凹槽 = (64,40) 起 96×72，进口在左第 1 行，出口在右第 0 行。
  furnace_glow.png 232×150 炉膛窗里的火（叠在 panel 上，脚本按呼吸调亮度）
  nozzle_glow.png 232×150  水管接通以后喷口里的暖红热光（同上，接通前不显示）
  pipes.png       96×48    水管：一格 24×24，列 = 直管 / 弯管 / 三通 / 堵头，行 = 冷的 / 接通后烧热的
                           基准方向：直管 西-东，弯管 北-东，三通 北-东-西，堵头 只通西
  lid.png         108×80   盖子：从面板顶上顺着滑轨滑下来，停在 (58,36)
  parts.png       64×40    四个零件（六角螺栓 / 铆钉 / 楔销 / 方螺母），一格 16×20，行 = 翘着的 / 敲到位的
  hammer.png      32×32    小锤子：锤头朝左上（中心 (9,9)），握柄末端（支点）在 (28,28)

配色：飞船自己那套暗灰蓝金属（art/level1/ship_fly.png 实测）+ 船身的紫红条纹；火和热光一律第一关的暖红
（scripts/ship_glow.gd 的 HOT_INNER / HOT_MID / HOT_OUTER）。光从左上来，大平面按受光切成几块直边的面，
相邻块只差一档。不描边、不画虚线点线、没有透视（正面平视的特写）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "art" / "ship_repair"


def hx(s: str) -> tuple:
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)


# 飞船金属（暗 → 亮），实测自 ship_fly.png，往两头各补一档
M = [hx(c) for c in ["#0a1416", "#142a2c", "#1c2125", "#222a2f", "#2a3338", "#333c40", "#3d4548", "#4a5559", "#587077"]]
STRIPE = [hx("#33203a"), hx("#45293f")]
# 第一关暖红（ship_glow.gd）+ 余火的亮芯
HOT = [hx("#4a2226"), hx("#962f2c"), hx("#c9473a"), hx("#e8795a"), hx("#f0c070")]
WOOD = [hx("#3a2a26"), hx("#5a3a2e"), hx("#74503a")]
CLEAR = (0, 0, 0, 0)


class Img:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)

    def put(self, x: int, y: int, c) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = c

    def rect(self, x0: int, y0: int, w: int, h: int, c) -> None:
        x1, y1 = min(self.w, x0 + w), min(self.h, y0 + h)
        x0, y0 = max(0, x0), max(0, y0)
        if x1 > x0 and y1 > y0:
            self.a[y0:y1, x0:x1] = c

    def mask_fill(self, m: np.ndarray, c) -> None:
        self.a[m] = c

    def grid(self):
        return np.mgrid[0:self.h, 0:self.w]

    def save(self, name: str) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        Image.fromarray(self.a, "RGBA").save(OUT / name)


def lit_plate(img: Img, m: np.ndarray, lo: int, cuts=(0.33, 0.72), tilt=0.55) -> None:
    """一块平板按左上来的光切成三块直边的面：左上亮一档、中间、右下暗一档（等亮线是斜直线）。"""
    yy, xx = img.grid()
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    t = ((xx - x0) / max(1, x1 - x0) * (1 - tilt) + (yy - y0) / max(1, y1 - y0) * tilt)
    img.mask_fill(m & (t >= cuts[1]), M[lo])
    img.mask_fill(m & (t < cuts[1]) & (t >= cuts[0]), M[lo + 1])
    img.mask_fill(m & (t < cuts[0]), M[lo + 2])


def bevel(img: Img, x0: int, y0: int, w: int, h: int, top, left, bot, right) -> None:
    """一圈 1 像素的受光边：上、左亮一档，下、右暗一档（不是描边：都只差一档）。"""
    img.rect(x0, y0, w, 1, top)
    img.rect(x0, y0, 1, h, left)
    img.rect(x0, y0 + h - 1, w, 1, bot)
    img.rect(x0 + w - 1, y0, 1, h, right)


def round_corners(img: Img, x0: int, y0: int, w: int, h: int, r: int = 2) -> None:
    for i in range(r):
        for j in range(r - i):
            for (x, y) in [(x0 + j, y0 + i), (x0 + w - 1 - j, y0 + i), (x0 + j, y0 + h - 1 - i), (x0 + w - 1 - j, y0 + h - 1 - i)]:
                img.put(x, y, CLEAR)


def ellipse_mask(img: Img, cx: float, cy: float, rx: float, ry: float) -> np.ndarray:
    yy, xx = img.grid()
    return ((xx + 0.5 - cx) / rx) ** 2 + ((yy + 0.5 - cy) / ry) ** 2 <= 1.0


# ======================================================================= 面板
PW, PH = 232, 150
CAV = (64, 40, 96, 72)            # 凹槽（水管 4×3，一格 24）
IN_Y = 76                         # 进口管中心（第 1 行）
OUT_Y = 52                        # 出口管中心（第 0 行）
PIPE_R = 5                        # 管子半宽（管宽 10）
FURN = (26.0, 76.0, 15.0, 30.0)   # 炉膛（椭圆 cx, cy, rx, ry）
NOZ_X0, NOZ_X1 = 182, 222          # 喷口从窄到宽


def nozzle_mask(img: Img) -> np.ndarray:
    yy, xx = img.grid()
    k = np.clip((xx - NOZ_X0) / (NOZ_X1 - NOZ_X0), 0, 1)
    half = 9 + k * k * 15          # 往外张开（曲线，不是直的梯形）
    return (xx >= NOZ_X0) & (xx <= NOZ_X1) & (np.abs(yy + 0.5 - OUT_Y) <= half)


def pipe_h(img: Img, x0: int, x1: int, cy: int, cols) -> None:
    """一段横管：截面明暗对称（中间亮、两边暗一档），cols = [边, 中, 亮]"""
    prof = [0, 1, 1, 2, 2, 2, 2, 1, 1, 0]
    for i, p in enumerate(prof):
        img.rect(x0, cy - PIPE_R + i, x1 - x0, 1, cols[p])


def panel() -> tuple:
    img = Img(PW, PH)
    yy, xx = img.grid()
    body = np.ones((PH, PW), bool)
    lit_plate(img, body, 3)
    bevel(img, 0, 0, PW, PH, M[6], M[6], M[2], M[2])
    round_corners(img, 0, 0, PW, PH, 3)
    # 船身那条紫红条纹（横贯底部，和飞船外面对上）
    img.rect(1, 124, PW - 2, 3, STRIPE[0])
    img.rect(1, 124, PW - 2, 1, STRIPE[1])
    # 四角的固定铆钉（只有四个，不成排）
    for (x, y) in [(6, 6), (PW - 8, 6), (6, PH - 8), (PW - 8, PH - 8)]:
        img.rect(x, y, 2, 2, M[6])
        img.put(x + 1, y + 1, M[4])

    # 盖子滑轨：凹槽两边各一道连续的槽，从顶边一直到凹槽底下
    for gx in (58, 164):
        img.rect(gx, 0, 2, 120, M[1])
        img.rect(gx, 0, 1, 120, M[0])
        img.rect(gx + 2, 0, 1, 120, M[5])
    # 凹槽：一圈 2 像素的唇边（上左暗、下右亮 = 凹进去），里面最暗的底
    x, y, w, h = CAV
    img.rect(x - 2, y - 2, w + 4, h + 4, M[2])
    img.rect(x - 2, y + h, w + 4, 2, M[5])
    img.rect(x + w, y - 2, 2, h + 4, M[4])
    img.rect(x - 2, y - 2, w + 4, 1, M[0])
    img.rect(x - 2, y - 2, 1, h + 4, M[0])
    floor = (xx >= x) & (xx < x + w) & (yy >= y) & (yy < y + h)
    t = (xx - x) / w * 0.4 + (yy - y) / h * 0.6
    img.mask_fill(floor & (t < 0.45), M[1])
    img.mask_fill(floor & (t >= 0.45), M[0])

    # 炉膛：一个椭圆的厚壳，中间一扇窗看得见里面的火
    cx, cy, rx, ry = FURN
    shell = ellipse_mask(img, cx, cy, rx + 4, ry + 4)
    img.mask_fill(shell, M[4])
    img.mask_fill(shell & (yy + xx * 0.5 < cy + cx * 0.5 - 12), M[5])
    img.mask_fill(shell & (yy + xx * 0.5 > cy + cx * 0.5 + 14), M[3])
    win = ellipse_mask(img, cx, cy, rx, ry)
    img.mask_fill(win, M[0])
    rim = win & ~ellipse_mask(img, cx, cy, rx - 1, ry - 1)
    img.mask_fill(rim & (yy < cy), M[1])
    # 进口管：炉膛 → 凹槽左边第 1 行
    pipe_h(img, int(cx + rx + 2), x, IN_Y, [M[3], M[5], M[6]])
    img.rect(x - 4, IN_Y - PIPE_R - 1, 2, PIPE_R * 2 + 2, M[6])      # 法兰
    # 出口管：凹槽右边第 0 行 → 喷口
    pipe_h(img, x + w, NOZ_X0, OUT_Y, [M[3], M[5], M[6]])
    img.rect(x + w + 2, OUT_Y - PIPE_R - 1, 2, PIPE_R * 2 + 2, M[6])
    # 喷口：外壳亮面在上、暗面在下，口里最暗
    noz = nozzle_mask(img)
    img.mask_fill(np.roll(np.roll(noz, 2, 0), 1, 1) & ~noz, M[2])     # 喷口在面板上落一块影子（右下）
    img.mask_fill(noz, M[5])
    img.mask_fill(noz & (yy < OUT_Y - 3 - (xx - NOZ_X0) * 0.3), M[6])
    img.mask_fill(noz & (yy < OUT_Y - 8 - (xx - NOZ_X0) * 0.38), M[7])
    img.mask_fill(noz & (yy > OUT_Y + 5 + (xx - NOZ_X0) * 0.3), M[4])
    mouth = noz & (xx >= NOZ_X1 - 5) & (np.abs(yy + 0.5 - OUT_Y) <= 20)
    img.mask_fill(mouth, M[1])
    img.mask_fill(mouth & (xx >= NOZ_X1 - 2), M[0])
    img.rect(NOZ_X0, OUT_Y - 10, 2, 21, M[7])                         # 喷口和出口管接缝的箍

    # 右下一块压力表（实心圆，表针朝左上）
    gm = ellipse_mask(img, 204.0, 100.0, 11.0, 11.0)
    img.mask_fill(gm, M[5])
    img.mask_fill(ellipse_mask(img, 204.0, 100.0, 9.0, 9.0), hx("#b9b6a4"))
    img.mask_fill(ellipse_mask(img, 204.0, 100.0, 9.0, 9.0) & (yy + xx > 304 + 3), hx("#a09e8e"))
    for i in range(6):
        img.put(203 - i, 99 - i // 2, HOT[1])
    img.rect(203, 99, 2, 2, M[2])
    img.save("panel.png")

    # ---- 炉膛里的火（单独一层）：底下堆着余火，越往下越亮
    fg = Img(PW, PH)
    yy, xx = fg.grid()
    inner = ellipse_mask(fg, cx, cy, rx - 1, ry - 1)
    h = (yy - (cy - ry)) / (2 * ry)
    wob = np.sin(xx * 1.3) * 0.04 + np.sin(xx * 0.55 + 1.0) * 0.05
    fg.mask_fill(inner & (h + wob > 0.34), HOT[0])
    fg.mask_fill(inner & (h + wob > 0.5), HOT[1])
    fg.mask_fill(inner & (h + wob > 0.66), HOT[2])
    fg.mask_fill(inner & (h + wob > 0.8), HOT[3])
    for (ex, ey) in [(22, 98), (29, 100), (25, 95), (32, 96)]:
        fg.rect(ex, ey, 2, 1, HOT[4])
    fg.save("furnace_glow.png")

    # ---- 喷口热光（单独一层）：口里烧亮 + 外面三圈暖红（实心环，越外越暗）
    ng = Img(PW, PH)
    yy, xx = ng.grid()
    noz = nozzle_mask(ng)
    mouth = noz & (xx >= NOZ_X1 - 5) & (np.abs(yy + 0.5 - OUT_Y) <= 20)
    ng.mask_fill(mouth, HOT[2])
    ng.mask_fill(mouth & (np.abs(yy + 0.5 - OUT_Y) < 14), HOT[3])
    ng.mask_fill(mouth & (np.abs(yy + 0.5 - OUT_Y) < 6) & (xx >= NOZ_X1 - 3), HOT[4])
    for i, (r, c) in enumerate([(9, HOT[1]), (6, HOT[2]), (3, HOT[3])]):
        halo = ellipse_mask(ng, NOZ_X1 + 0.0, OUT_Y + 0.0, r, 24 - i * 6) & (xx > NOZ_X1)
        ng.mask_fill(halo, c)
    ng.save("nozzle_glow.png")
    return img, fg, ng


# ======================================================================= 水管
T = 24


def pipe_tile(kind: str, hot: bool) -> np.ndarray:
    """一格水管（24×24，透明底），截面对称上色，所以转 90° 光也不乱。"""
    t = Img(T, T)
    if hot:
        cols = [HOT[1], HOT[2], HOT[3]]
        flange = HOT[1]
        hub = [HOT[1], HOT[2]]
    else:
        cols = [M[3], M[5], M[6]]
        flange = M[6]
        hub = [M[4], M[5]]
    prof = [0, 1, 1, 2, 2, 2, 2, 1, 1, 0]
    c0 = T // 2 - PIPE_R
    arms = {"straight": "EW", "elbow": "NE", "tee": "NEW", "cap": "W"}[kind]

    def arm(d: str) -> None:
        for i, p in enumerate(prof):
            if d == "W":
                t.rect(0, c0 + i, T // 2, 1, cols[p])
            elif d == "E":
                t.rect(T // 2, c0 + i, T // 2, 1, cols[p])
            elif d == "N":
                t.rect(c0 + i, 0, 1, T // 2, cols[p])
            elif d == "S":
                t.rect(c0 + i, T // 2, 1, T // 2, cols[p])

    for d in arms:
        arm(d)
    # 管子在格子边上的法兰（一道 2 像素宽的箍，接口处读得出是「一节一节接起来」的）
    for d in arms:
        if d == "W":
            t.rect(0, c0 - 1, 2, 12, flange)
        elif d == "E":
            t.rect(T - 2, c0 - 1, 2, 12, flange)
        elif d == "N":
            t.rect(c0 - 1, 0, 12, 2, flange)
        elif d == "S":
            t.rect(c0 - 1, T - 2, 12, 2, flange)
    # 转弯 / 分叉的地方一个接头块；堵头是一个圆帽
    if kind in ("elbow", "tee"):
        t.rect(c0, c0, 10, 10, hub[1])
        t.rect(c0 + 1, c0 + 1, 8, 1, cols[2])
        t.rect(c0 + 1, c0 + 8, 8, 1, hub[0])
    if kind == "cap":
        m = ellipse_mask(t, 12.0, 12.0, 6.0, 6.0)
        t.mask_fill(m, hub[1])
        t.mask_fill(m & ~ellipse_mask(t, 12.0, 12.0, 5.0, 5.0), hub[0])
        t.rect(10, 10, 3, 2, cols[2])
    return t.a


def pipes() -> np.ndarray:
    sheet = Img(T * 4, T * 2)
    for i, k in enumerate(["straight", "elbow", "tee", "cap"]):
        for j, hot in enumerate([False, True]):
            sheet.a[j * T:(j + 1) * T, i * T:(i + 1) * T] = pipe_tile(k, hot)
    sheet.save("pipes.png")
    return sheet.a


# ======================================================================= 盖子
LW, LH = 108, 80
PART_X = [20, 42, 66, 88]          # 零件中心（盖子里的 x）
PART_Y = 60                       # 零件插孔中心（盖子里的 y）


def lid() -> np.ndarray:
    img = Img(LW, LH)
    yy, xx = img.grid()
    m = np.ones((LH, LW), bool)
    lit_plate(img, m, 4, cuts=(0.3, 0.68))
    bevel(img, 0, 0, LW, LH, M[7], M[7], M[3], M[3])
    round_corners(img, 0, 0, LW, LH, 2)
    # 两边插进滑轨的舌头（盖子比凹槽宽，左右各 3 像素落在轨道里）
    img.rect(0, 4, 3, LH - 8, M[4])
    img.rect(LW - 3, 4, 3, LH - 8, M[3])
    # 上面一道把手槽（连续的横槽）和船身紫条
    img.rect(30, 8, 48, 3, M[2])
    img.rect(30, 11, 48, 1, M[6])
    img.rect(3, 22, LW - 6, 3, STRIPE[0])
    img.rect(3, 22, LW - 6, 1, STRIPE[1])
    # 四个零件的插孔：凹下去的圆坑
    for px in PART_X:
        hole = ellipse_mask(img, px + 0.0, PART_Y + 0.0, 6.0, 4.0)
        img.mask_fill(hole, M[1])
        img.mask_fill(hole & (yy >= PART_Y + 1), M[0])
        lip = ellipse_mask(img, px + 0.0, PART_Y + 1.0, 7.0, 4.5) & ~hole & (yy > PART_Y)
        img.mask_fill(lip, M[7])
    img.save("lid.png")
    return img.a


# ======================================================================= 零件
PWID, PHT = 16, 20


def part(kind: str, locked: bool) -> np.ndarray:
    """一个零件：翘着（帽子高出插孔、露出一截螺杆）/ 敲到位（帽子贴住、边上一圈暖红的热封）。"""
    p = Img(PWID, PHT)
    lift = 0 if locked else 7
    base_y = 14                     # 帽子底边落在插孔上（插孔中心 = 格子里的 (8, 15)）
    cy = base_y - lift
    if not locked:
        p.rect(6, cy, 4, lift + 2, M[4])                # 螺杆
        p.rect(6, cy, 1, lift + 2, M[6])
        p.rect(9, cy, 1, lift + 2, M[3])                # 螺杆背光那一侧（连续的一条，不画等距的螺纹）
    if locked:
        seal = ellipse_mask(p, 8.0, base_y + 1.0, 7.0, 3.0)
        p.mask_fill(seal, HOT[1])
        p.mask_fill(seal & ellipse_mask(p, 8.0, base_y + 0.5, 6.0, 2.0), HOT[2])
    if kind == "hex":
        p.rect(3, cy - 5, 10, 5, M[5])
        p.rect(4, cy - 6, 8, 1, M[7])
        p.rect(3, cy - 5, 3, 5, M[6])
        p.rect(10, cy - 5, 3, 5, M[4])
    elif kind == "rivet":
        cap = ellipse_mask(p, 8.0, cy - 1.0, 6.0, 4.5) & (np.mgrid[0:PHT, 0:PWID][0] < cy)
        p.mask_fill(cap, M[5])
        p.mask_fill(cap & ellipse_mask(p, 6.5, cy - 3.0, 3.0, 2.0), M[7])
    elif kind == "pin":
        for i in range(6):
            w = 4 + i
            p.rect(8 - w // 2, cy - 6 + i, w, 1, M[6] if i < 2 else M[5])
        p.rect(8 - 4, cy - 1, 9, 1, M[4])
    elif kind == "nut":
        p.rect(2, cy - 4, 12, 4, M[4])
        p.rect(2, cy - 4, 12, 1, M[6])
        p.rect(6, cy - 4, 4, 2, M[2])
        p.rect(6, cy - 2, 4, 1, M[3])
    if locked:
        p.put(5, cy - 4 if kind != "nut" else cy - 3, HOT[3])     # 一颗暖红的亮点：到位了
    return p.a


KINDS = ["hex", "rivet", "pin", "nut"]


def parts() -> np.ndarray:
    sheet = Img(PWID * 4, PHT * 2)
    for i, k in enumerate(KINDS):
        for j, lk in enumerate([False, True]):
            sheet.a[j * PHT:(j + 1) * PHT, i * PWID:(i + 1) * PWID] = part(k, lk)
    sheet.save("parts.png")
    return sheet.a


# ======================================================================= 锤子
def hammer() -> np.ndarray:
    """32×32：握柄从支点 (28,28) 斜向左上，锤头是一块和柄垂直的方铁，中心在 (9,9)。
    锤头朝左上那一面受光（亮），靠柄那一面暗；柄朝左上的一侧亮一档。"""
    h = Img(32, 32)
    yy, xx = h.grid()
    px, py = xx + 0.5, yy + 0.5
    # 握柄：(11,11) → (28,28) 的一条粗 3 的直线
    u = ((px - 11) + (py - 11)) / np.sqrt(2)          # 沿柄
    v = ((px - 11) - (py - 11)) / np.sqrt(2)          # 横过柄（正 = 右上那一侧）
    handle = (u >= 0) & (u <= 24.5) & (np.abs(v) <= 1.6)
    h.mask_fill(handle, WOOD[1])
    h.mask_fill(handle & (v > 0.6), WOOD[0])
    h.mask_fill(handle & (v < -0.6), WOOD[2])
    h.mask_fill(handle & (u > 21.5), WOOD[0])          # 柄尾
    # 锤头：横 15（沿 (1,-1)）、厚 7（沿柄的方向）
    a = ((px - 9) - (py - 9)) / np.sqrt(2)
    b = ((px - 9) + (py - 9)) / np.sqrt(2)             # 负 = 朝左上（离柄远、受光）
    head = (np.abs(a) <= 7.5) & (b >= -4.2) & (b <= 3.2)
    h.mask_fill(head, M[5])
    h.mask_fill(head & (b < -1.5), M[6])
    h.mask_fill(head & (b < -3.0), M[7])
    h.mask_fill(head & (b > 1.8), M[4])
    h.mask_fill(head & (np.abs(a) > 6.4), M[4])        # 两头的敲击面暗一档
    h.save("hammer.png")
    return h.a


# ======================================================================= 预览
def over(dst: np.ndarray, src: np.ndarray, x: int, y: int) -> None:
    hh, ww = src.shape[:2]
    reg = dst[y:y + hh, x:x + ww]
    m = src[..., 3] > 0
    reg[m] = src[m]


def preview(path: str) -> None:
    pan, fg, ng = panel()
    pi = pipes()
    li = lid()
    pa = parts()
    hm = hammer()
    W = PW * 2 + 24 + 140
    canvas = np.zeros((PH + 20, W, 4), np.uint8)
    canvas[...] = hx("#15171a")
    # 左：打开的面板，水管摆上去（一半冷一半热），喷口热光
    a = pan.a.copy()
    over(a, fg.a, 0, 0)
    over(a, ng.a, 0, 0)
    layout = [["elbow", "straight", "tee", "elbow"], ["straight", "elbow", "cap", "straight"], ["tee", "elbow", "straight", "elbow"]]
    for r in range(3):
        for c in range(4):
            k = ["straight", "elbow", "tee", "cap"].index(layout[r][c])
            hot = 1 if r == 1 and c < 2 else 0
            tile = pi[hot * T:(hot + 1) * T, k * T:(k + 1) * T]
            tile = np.rot90(tile, -((r + c) % 4)).copy()
            over(a, tile, CAV[0] + c * T, CAV[1] + r * T)
    over(canvas, a, 10, 10)
    # 中：盖上盖子 + 零件
    b = pan.a.copy()
    over(b, fg.a, 0, 0)
    over(b, li, 58, 36)
    for i, px in enumerate(PART_X):
        lk = 1 if i % 2 else 0
        over(b, pa[lk * PHT:(lk + 1) * PHT, i * PWID:(i + 1) * PWID], 58 + px - 8, 36 + PART_Y - 15)
    over(canvas, b, PW + 14, 10)
    # 右：两张图集和锤子
    over(canvas, pi, PW * 2 + 24, 10)
    over(canvas, pa, PW * 2 + 24, 70)
    over(canvas, hm, PW * 2 + 24 + 80, 70)
    big = Image.fromarray(canvas, "RGBA").resize((canvas.shape[1] * 4, canvas.shape[0] * 4), Image.NEAREST)
    big.save(path)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        preview(sys.argv[1])
    else:
        panel()
        pipes()
        lid()
        parts()
        hammer()
    print("ok ->", OUT)
