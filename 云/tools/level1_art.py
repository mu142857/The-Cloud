"""第一关（森林坠毁 → 发光木头）的占位美术：飞船（飞行 2 帧）、坠毁的飞船、发光木头、木头光晕、
背包 / 设置 / 燃烧值图标、提示小箭头。全部是占位，以后美术会换（换的时候保持尺寸和锚点说明即可）。

跑法：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/level1_art.py
输出到 art/level1/。后面给一个路径参数会另存一张 8 倍预览。

画法：飞船在「自己的坐标系」里用几个形状定义（船身、驾驶舱、尾翼、喷口、条纹），每个像素反算回自己的坐标
再上色，所以飞行时斜 18° 和坠毁时斜 34° 都是一笔一笔硬边像素，不是把图旋转出来的（不会有 mixel）。
光从上面来：船身按「离自己顶边多远」分 5 档。颜色：暗的灰蓝金属 + 晨围巾的那种紫红条纹（都压得很暗）。
2026-10-28 夜：飞船整体压暗（船身 OKLab L 约 0.24~0.36，晨的米白是 0.72~0.8），只在机头上沿留一条
冷色受光边（L 约 0.5，像被天光擦到）和喷口火焰 / 坠毁后焦痕里的几颗余火，烟也压暗，不和晨抢。
发光木头是画面里唯一的暖色（琥珀），只比晨暗一点。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.canvas import Canvas  # noqa: E402
from oscarkit.palette import ramp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "art" / "level1"
OUT.mkdir(parents=True, exist_ok=True)

HULL = ramp((0x2a, 0x33, 0x38), 5, L_span=0.14, hue_shift=8)            # 暗的灰蓝金属，暗 → 亮（L 0.24..0.36）
RIM = "#587077"                                               # 机头上沿那条冷色受光边（L≈0.51），只有一小段
STRIPE = ["#26182a", "#33203a", "#45293f"]                    # 晨围巾的紫红，压暗
GLASS = ["#0a1416", "#142a2c", "#3f6f69"]                     # 驾驶舱玻璃，最后一档是一颗小高光
EMBER = ["#7a3420", "#c06a2c"]                                # 坠毁后焦痕里的余火
SCORCH = ["#15161a", "#24242a"]
INSIDE = "#0b0c0f"                                            # 坠毁后舱门口里面（最暗）
FLAME = ["#8a3a22", "#d0782e", "#f0c070"]
SOIL = ["#141b15", "#1e1c18", "#24221e", "#2f4335", "#3f5041"]


def hexc(c):
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(int(v) for v in c[:3])


# ---------------------------------------------------------------- 飞船的形状（自己的坐标，单位 = 像素：机头朝左，x -70..70）
# 2026-10-28：放大到约 3 倍（原来 44 长，晨换成 52 高的奥斯卡版以后，飞船看着像玩具）。
# 现在船身长 140、船身高约 41（加上尾翼约 67），能装下两个人：侧面一排 4 个舷窗，中间一扇舱门
# （坠毁后舱门没了，晨和另一个外星人就是从这个口子里被甩出来的）。
L_SHIP = 140.0
TOP_H, BOT_H = 24.0, 17.0


def hull_half(x):
    """船身在 x 处的上半高 / 下半高（机头圆、尾部平）。"""
    t = (x + L_SHIP / 2) / L_SHIP           # 0 机头 .. 1 尾
    if t < 0 or t > 1:
        return None
    top = TOP_H * math.sqrt(max(0.0, 1 - (1 - min(t / 0.55, 1)) ** 2)) * (1 - 0.25 * max(0, t - 0.55) / 0.45)
    bot = BOT_H * math.sqrt(max(0.0, 1 - (1 - min(t / 0.45, 1)) ** 2)) * (1 - 0.15 * max(0, t - 0.45) / 0.55)
    return top, bot


def in_tri(p, a, b, c):
    def s(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
    d1, d2, d3 = s(p, a, b), s(p, b, c), s(p, c, a)
    neg = d1 < 0 or d2 < 0 or d3 < 0
    pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (neg and pos)


PORTHOLES = (-6.0, 8.0, 36.0, 49.0)     # 舷窗中心 x（y = -9），中间空出来的是舱门
HATCH = (14.0, 30.0, -15.0, 6.0)        # 舱门 x0, x1, y0, y1
HOLE = (-4.0, 8.0, 10.0, 5.5)            # 坠毁：破洞中心 x, y, 半宽, 半高（往外冒火星）
FIN_UP = ((22, -17), (58, -17), (67, -42))
FIN_DN = ((36, 11), (62, 11), (70, 27))


def ship_color(lx, ly, damaged=False, broken_fin=False, flame_phase=-1, rng=None):
    """自己坐标里 (lx, ly) 这一点是什么颜色；None = 透明。"""
    # 喷口火焰（飞行时）
    if flame_phase >= 0 and 71 <= lx <= 98:
        half = 9.5 - (lx - 71) * (0.36 if flame_phase == 0 else 0.29)
        if abs(ly + 1.5) <= half:
            d = (lx - 71) + abs(ly + 1.5) * 1.5
            return FLAME[2] if d < 8 else FLAME[1] if d < 17 else FLAME[0]
    # 喷口（往外凸一截，两道环）
    if 63 <= lx <= 72 and -10 <= ly <= 8:
        if lx >= 70 and -8 <= ly <= 6:
            return GLASS[0]                  # 喷口里面
        if abs(lx - 66) < 0.6:
            return HULL[0]
        return HULL[1] if ly > -1 else HULL[2]
    # 上尾翼
    if in_tri((lx, ly), *FIN_UP):
        if broken_fin and lx + (ly + 17) * 0.35 > 52:
            return None                      # 断了一截，断口斜着
        if abs(lx - 40 + (ly + 17) * 0.2) < 0.6:
            return HULL[1]                   # 一道面板缝
        return HULL[3] if ly < -30 or lx > 56 else HULL[2]
    # 下尾翼
    if not broken_fin and in_tri((lx, ly), *FIN_DN):
        return HULL[1]
    h = hull_half(lx)
    if h is None:
        return None
    top, bot = h
    if not (-top <= ly <= bot):
        return None
    v = (ly + top) / (top + bot)            # 0 顶边 .. 1 底边
    # 驾驶舱玻璃
    if ((lx + 30) / 20.0) ** 2 + ((ly + 10.5) / 11.0) ** 2 <= 1.0 and ly < -1.5:
        if not damaged and -40 <= lx <= -38 and -17 <= ly <= -16:
            return GLASS[2]                  # 一颗小高光
        if damaged and (abs(ly + 14 - (lx + 22) * 0.9) < 0.7 and -26 < lx < -15
                        or abs(ly + 7 + (lx + 22) * 0.5) < 0.7 and -34 < lx < -22):
            return HULL[2]                   # 碎了：一道折线裂纹
        if abs(lx + 30 + (ly + 10.5) * 0.4) < 0.6:
            return HULL[2]                   # 窗框的竖条
        return GLASS[1] if ly < -11 else GLASS[0]
    # 舱门：飞行时是一圈缝，坠毁后门没了，是个黑洞（里面隐约一条座椅）
    hx0, hx1, hy0, hy1 = HATCH
    if hx0 <= lx <= hx1 and hy0 <= ly <= hy1:
        if damaged:
            if hx0 + 2 <= lx <= hx1 - 2 and hy0 + 2 <= ly <= hy1:
                if abs(ly - 0) < 1.0 and lx < hx1 - 5:
                    return SCORCH[1]         # 舱里的座椅
                return INSIDE
            return HULL[0]                   # 门框
        if lx < hx0 + 1 or lx > hx1 - 1 or ly < hy0 + 1 or ly > hy1 - 1:
            return HULL[1]
    # 舷窗
    for px in PORTHOLES:
        dd = (lx - px) ** 2 + (ly + 9) ** 2
        if dd <= 3.0 ** 2:
            if dd <= 1.6 ** 2 and ly < -9.5 and not damaged:
                return GLASS[1]
            return GLASS[0]
    # 紫红条纹
    if 2.0 <= ly <= 5.5 and -50 < lx < 63:
        return STRIPE[2] if lx < 6 else STRIPE[1]
    # 焦痕、破洞（坠毁）
    if damaged:
        cx, cy, rx, ry = HOLE
        if ((lx - cx) / rx) ** 2 + ((ly - cy) / ry) ** 2 <= 1:
            if abs(lx - cx) < 2.0 and abs(ly - cy) < 1.5:
                return EMBER[1]
            if abs(lx - cx - 4) < 1.5 and abs(ly - cy - 2) < 1.2:
                return EMBER[0]
            return SCORCH[0] if ((lx - cx) / (rx * 0.55)) ** 2 + ((ly - cy) / (ry * 0.55)) ** 2 <= 1 else SCORCH[1]
        if ((lx + 52) / 9.0) ** 2 + ((ly - 3) / 7.0) ** 2 <= 1:
            return SCORCH[1]                 # 机头擦地的焦痕
        if ((lx - 58) / 6.0) ** 2 + ((ly + 4) / 9.0) ** 2 <= 1:
            return SCORCH[1]                 # 喷口熏黑
    # 光从上面来：按离顶边多远分档
    if v < 0.07 and -56 < lx < -2:
        return RIM                           # 机头上沿一小段受光边
    k = 4 if v < 0.28 else 3 if v < 0.52 else 2 if v < 0.78 else 1
    if lx > 40 and k > 1:
        k -= 1                               # 尾部稍暗
    # 几道面板缝（竖），一道横缝
    for sx in (-48.0, 2.0, 40.0, 58.0):
        if abs(lx - sx) < 0.55 and v < 0.85:
            return HULL[max(0, k - 2)]
    if abs(v - 0.78) < 0.5 / (top + bot) * 2 and -40 < lx < 62:
        return HULL[max(0, k - 1)]
    return HULL[k]


def raster(w, h, cx, cy, ang_deg, **kw):
    c = Canvas(w, h)
    a = math.radians(ang_deg)
    ca, sa = math.cos(a), math.sin(a)
    for y in range(h):
        for x in range(w):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            # 世界 → 自己：逆旋转
            lx = dx * ca + dy * sa
            ly = -dx * sa + dy * ca
            col = ship_color(lx, ly, **kw)
            if col is not None:
                c.put(x, y, hexc(col))
    return c


def to_world(p, ang_deg):
    """自己坐标 → 相对旋转中心的世界偏移（关卡脚本用这些数摆烟、火星、甩人）。"""
    a = math.radians(ang_deg)
    return (p[0] * math.cos(a) - p[1] * math.sin(a), p[0] * math.sin(a) + p[1] * math.cos(a))


FLY_ANG = -16
FLY_W, FLY_H = 192, 104


def ship_fly():
    """飞行中：机头朝左下斜 16°（往左下方坠），喷口火焰两帧。锚点 = 图中心。"""
    frames = [raster(FLY_W, FLY_H, FLY_W / 2, FLY_H / 2, FLY_ANG, flame_phase=i) for i in (0, 1)]
    sheet = Canvas(FLY_W * 2, FLY_H)
    for i, f in enumerate(frames):
        sheet.paste(f, FLY_W * i, 0)
    return sheet


WRECK_ANG = -17
WRECK_W, WRECK_H = 176, 78
WRECK_GROUND = WRECK_H - 6                  # 图里地面线（再往下是翻起来的土）
WRECK_C = (84, 58)                          # 船身中心在图里的位置（旋转中心）
WRECK_ANCHOR_X = 84                         # 锚点 x（= 关卡里的 WRECK_X）


def ship_wreck():
    """坠毁：机头扎进土里，斜 17°，下尾翼没了、上尾翼断一截，舱门没了，焦痕和破洞。
    锚点：x = WRECK_ANCHOR_X（船身中心），y = 地面那一行（WRECK_GROUND）。"""
    W, H = WRECK_W, WRECK_H
    ground = WRECK_GROUND
    c = raster(W, H, WRECK_C[0], WRECK_C[1], WRECK_ANG, damaged=True, broken_fin=True)
    a = c.a
    # 地面以下的船身被土埋住
    a[ground:, :, 3] = 0
    # 机头周围翻起的土堆：左边大坡（机头犁出来的），右边小坡
    nose = to_world((-L_SHIP / 2, 0), WRECK_ANG)
    nx = int(round(WRECK_C[0] + nose[0]))
    for x in range(W):
        hl = 0
        for (mx, r, hgt) in ((nx + 4, 26, 10), (nx + 36, 14, 4)):
            if abs(x - mx) < r:
                hl = max(hl, int(round(hgt * (1 - (abs(x - mx) / r) ** 2))))
        if hl == 0:
            continue                         # 土堆以外：什么都不画，地面由背景画
        for y in range(ground - hl, min(H, ground + 1 + hl // 2)):
            d = y - (ground - hl)
            col = SOIL[4] if d == 0 else SOIL[3] if d == 1 and hl > 1 else SOIL[2] if y < ground else SOIL[1]
            a[y, x] = (*hexc(col), 255)
    # 几块飞出去的土 / 碎片（脱离的碎点）
    for (x, y, col) in ((nx - 22, ground - 4, SOIL[2]), (nx - 16, ground - 10, SOIL[3]), (nx - 26, ground - 1, SOIL[2]),
                        (nx + 30, ground - 13, SOIL[2]), (150, ground - 1, HULL[1]), (151, ground - 1, HULL[1]),
                        (162, ground - 2, HULL[2]), (170, ground - 1, HULL[1])):
        if 0 <= x < W:
            a[y, x] = (*hexc(col), 255)
    # 断下来的尾翼尖斜插在地上（尾巴右后方）
    for i in range(9):
        for j in range(3 - i // 4):
            a[ground - 1 - i, 140 + i // 2 + j] = (*hexc(HULL[2] if j == 0 else HULL[1]), 255)
    return c


def ship_points():
    """打印关卡脚本要用的几个点（相对锚点）。"""
    def fly(p):
        q = to_world(p, FLY_ANG)
        return (round(q[0]), round(q[1]))

    def wr(p):
        q = to_world(p, WRECK_ANG)
        return (round(WRECK_C[0] + q[0] - WRECK_ANCHOR_X), round(WRECK_C[1] + q[1] - WRECK_GROUND))
    hx0, hx1, hy0, hy1 = HATCH
    return {
        "fly nose": fly((-L_SHIP / 2, 4)), "fly engine": fly((74, -1.5)),
        "wreck offset": (-WRECK_ANCHOR_X, -WRECK_GROUND),
        "wreck nose(ground)": wr((-L_SHIP / 2 + 8, 0)),
        "wreck hatch": wr(((hx0 + hx1) / 2, (hy0 + hy1) / 2)),
        "wreck hole": wr((HOLE[0], HOLE[1])), "wreck engine": wr((72, -1)),
        "wreck fin break": wr((52, -24)),
    }


def wood():
    """发光的木头 18×8：暗的树皮 + 亮琥珀的裂纹和断口。锚点：底边 = 地面，x = 中心。"""
    rows = [
        "..................",
        "...bbbbbbbbbbbb...",
        "..bBBcBBBBBcBBBbo.",
        ".OYBccBBBBcYcBBBoO",
        ".OYbBBcBccYBBBBboO",
        "..obbbbbcbbbbbbbo.",
        "...dddddddddddd...",
        "..................",
    ]
    pal = {
        "b": "#3a2a22", "B": "#5a3f2c", "d": "#241a16",
        "c": "#c8823c", "Y": "#e8b860", "o": "#a8642e", "O": "#e0a050",
    }
    return Canvas.from_rows(rows, {k: hexc(v) for k, v in pal.items()})


def wood_glow():
    """木头的光晕（特效，允许半透明，加法混合用）：32×20 的椭圆，中心亮边缘淡，按 4 档分开（硬边阶梯，不是平滑渐变）。"""
    W, H = 40, 24
    a = np.zeros((H, W, 4), np.uint8)
    for y in range(H):
        for x in range(W):
            d = math.hypot((x + 0.5 - W / 2) / (W / 2), (y + 0.5 - H / 2) / (H / 2))
            if d < 1:
                lvl = 4 - int(d * 4)            # 4 .. 1
                a[y, x] = (240, 170, 90, [0, 40, 70, 105, 140][lvl])
    return a


def icon_bag():
    rows = [
        "....aaaaa....",
        "...a.....a...",
        "...a.....a...",
        ".bbbbbbbbbbb.",
        "bBBBBBBBBBBBb",
        "bBBBBccBBBBBb",
        "bBBBBcYBBBBBb",
        "bbbbbbbbbbbbb",
        "bBBBBBBBBBBBb",
        "bBBBBBBBBBBBb",
        "bBBBBBBBBBBBb",
        ".ddddddddddd.",
    ]
    pal = {"a": "#8fa69a", "b": "#5c6f66", "B": "#8fa69a", "d": "#3a4a43", "c": "#c8823c", "Y": "#e8b860"}
    return Canvas.from_rows(rows, {k: hexc(v) for k, v in pal.items()})


def icon_gear():
    rows = [
        ".....a.....",
        "..a.aaa.a..",
        ".aaaaaaaaa.",
        "..aaa.aaa..",
        ".aaa...aaa.",
        "aaa.....aaa",
        ".aaa...aaa.",
        "..aaa.aaa..",
        ".aaaaaaaaa.",
        "..a.aaa.a..",
        ".....a.....",
    ]
    return Canvas.from_rows(rows, {"a": hexc("#8fa69a")})


def icon_flame():
    rows = [
        "...o...",
        "...oo..",
        "..ooo..",
        ".oocoo.",
        ".occo.o",
        "ooccYoo",
        "ocYYYco",
        "ocYYYco",
        ".ocYco.",
    ]
    pal = {"o": "#a8642e", "c": "#d0782e", "Y": "#f0c070"}
    return Canvas.from_rows(rows, {k: hexc(v) for k, v in pal.items()})


def icon_headphones():
    rows = [
        "....aaaaaaa....",
        "..aa.......aa..",
        ".a...........a.",
        "a.............a",
        "a.............a",
        "a.............a",
        "bBB.........BBb",
        "bBB.........BBb",
        "bBB.........BBb",
        "bBB.........BBb",
        ".bb.........bb.",
    ]
    pal = {"a": "#8fa69a", "b": "#5c6f66", "B": "#b9c9bf"}
    return Canvas.from_rows(rows, {k: hexc(v) for k, v in pal.items()})


def hint_arrow():
    rows = [
        "aaaaa",
        ".aaa.",
        "..a..",
    ]
    return Canvas.from_rows(rows, {"a": hexc("#e8d6a8")})


def puff_sheet():
    """烟 / 尘土的小团，白色，游戏里按颜色染：半径 1..7 各一格，16×16 一格横排。"""
    n = 7
    a = np.zeros((16, 16 * n, 4), np.uint8)
    for i in range(n):
        r = i + 1
        for y in range(16):
            for x in range(16):
                if (x + 0.5 - 8) ** 2 + (y + 0.5 - 8) ** 2 <= r * r + 0.3:
                    a[y, 16 * i + x] = (255, 255, 255, 255)
    return a


def save_arr(a, name):
    from PIL import Image
    Image.fromarray(a, "RGBA").save(OUT / name)


def main():
    parts = {
        "ship_fly.png": ship_fly(),
        "ship_wreck.png": ship_wreck(),
        "wood.png": wood(),
        "icon_bag.png": icon_bag(),
        "icon_gear.png": icon_gear(),
        "icon_flame.png": icon_flame(),
        "hint_arrow.png": hint_arrow(),
        "icon_headphones.png": icon_headphones(),
    }
    for name, c in parts.items():
        c.save(OUT / name)
    save_arr(wood_glow(), "wood_glow.png")
    save_arr(puff_sheet(), "puffs.png")

    # 预览：深青绿底，8 倍
    from PIL import Image
    S = 8
    items = list(parts.items())
    W = sum(c.w for _, c in items) + 6 * len(items) + 6
    H = max(c.h for _, c in items) + 12
    bg = Image.new("RGBA", (W, H), (20, 32, 28, 255))
    x = 6
    for _, c in items:
        bg.alpha_composite(Image.fromarray(c.a, "RGBA"), (x, 6))
        x += c.w + 6
    if len(sys.argv) > 1:                   # 预览图存到哪（不进工程）：python tools/level1_art.py /某处/preview.png
        bg.resize((W * S, H * S), Image.NEAREST).save(sys.argv[1])
    print("ok", [n for n in parts])
    for k, v in ship_points().items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
