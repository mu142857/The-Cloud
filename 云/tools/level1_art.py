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
FLAME = ["#8a3a22", "#d0782e", "#f0c070"]
SOIL = ["#141b15", "#1e1c18", "#24221e", "#2f4335", "#3f5041"]


def hexc(c):
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(int(v) for v in c[:3])


# ---------------------------------------------------------------- 飞船的形状（自己的坐标：机头朝左，x -22..22）
def hull_half(x):
    """船身在 x 处的上半高 / 下半高（机头圆、尾部平）。"""
    t = (x + 22) / 44.0                     # 0 机头 .. 1 尾
    if t < 0 or t > 1:
        return None
    top = 7.2 * math.sqrt(max(0.0, 1 - (1 - min(t / 0.55, 1)) ** 2)) * (1 - 0.25 * max(0, t - 0.55) / 0.45)
    bot = 5.2 * math.sqrt(max(0.0, 1 - (1 - min(t / 0.45, 1)) ** 2)) * (1 - 0.15 * max(0, t - 0.45) / 0.55)
    return top, bot


def in_tri(p, a, b, c):
    def s(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
    d1, d2, d3 = s(p, a, b), s(p, b, c), s(p, c, a)
    neg = d1 < 0 or d2 < 0 or d3 < 0
    pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (neg and pos)


def ship_color(lx, ly, damaged=False, broken_fin=False, flame_phase=-1, rng=None):
    """自己坐标里 (lx, ly) 这一点是什么颜色；None = 透明。"""
    # 喷口火焰（飞行时）
    if flame_phase >= 0 and 22 <= lx <= 30 and abs(ly + 0.5) <= 3.2 - (lx - 22) * (0.33 if flame_phase == 0 else 0.26):
        d = (lx - 22) + abs(ly + 0.5) * 1.5
        return FLAME[2] if d < 2.5 else FLAME[1] if d < 5.5 else FLAME[0]
    # 喷口
    if 19.5 <= lx <= 23 and -3.2 <= ly <= 2.6:
        return HULL[0] if ly > 0.5 else HULL[1]
    # 上尾翼
    if in_tri((lx, ly), (7, -5.5), (18.5, -5.5), (21, -12.5)):
        if broken_fin and lx > 15:
            return None
        return HULL[3] if ly < -9 or lx > 17 else HULL[2]
    # 下尾翼
    if not broken_fin and in_tri((lx, ly), (11, 3.5), (19.5, 3.5), (21.5, 8.5)):
        return HULL[1]
    h = hull_half(lx)
    if h is None:
        return None
    top, bot = h
    if not (-top <= ly <= bot):
        return None
    # 驾驶舱玻璃
    if ((lx + 9) / 6.2) ** 2 + ((ly + 3.2) / 3.4) ** 2 <= 1.0 and ly < -0.5:
        if -12 <= lx <= -11 and -5.5 <= ly <= -4.5 and not damaged:
            return GLASS[2]
        return GLASS[1] if ly < -3.3 else GLASS[0]
    # 紫红条纹
    if 0.6 <= ly <= 2.0 and -15 < lx < 19:
        return STRIPE[2] if lx < 2 else STRIPE[1]
    # 焦痕、破洞（坠毁）
    if damaged:
        if ((lx - 6) / 4.5) ** 2 + ((ly + 1.5) / 2.6) ** 2 <= 1:
            # 破洞里两颗余火（关卡里还会从这里冒火星）
            if abs(lx - 6) < 1.0 and abs(ly + 1.5) < 0.7:
                return EMBER[1]
            if abs(lx - 7.5) < 0.8 and abs(ly + 0.6) < 0.6:
                return EMBER[0]
            return SCORCH[0] if ((lx - 6) / 2.4) ** 2 + ((ly + 1.5) / 1.4) ** 2 <= 1 else SCORCH[1]
        if ((lx + 17) / 3.0) ** 2 + ((ly - 1) / 2.4) ** 2 <= 1:
            return SCORCH[1]
    # 光从上面来：按离顶边多远分档
    v = (ly + top) / (top + bot)            # 0 顶边 .. 1 底边
    if v < 0.12 and -16 < lx < 2:
        return RIM                           # 机头上沿一小段受光边
    k = 4 if v < 0.3 else 3 if v < 0.55 else 2 if v < 0.8 else 1
    if lx > 12 and k > 1:
        k -= 1                               # 尾部稍暗
    # 一条面板缝
    if abs(lx - 3) < 0.5 and v < 0.55:
        k = max(0, k - 2)
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


def ship_fly():
    """飞行中：机头朝左下斜 18°（往左下方坠），喷口火焰两帧。锚点 = 图中心。"""
    frames = [raster(56, 34, 28, 17, -18, flame_phase=i) for i in (0, 1)]
    sheet = Canvas(56 * 2, 34)
    for i, f in enumerate(frames):
        sheet.paste(f, 56 * i, 0)
    return sheet


def ship_wreck():
    """坠毁：机头扎进土里，斜 34°，下尾翼断了，焦痕。锚点：图底边 = 地面（ground_y 那一行），x = 图中心。"""
    W, H = 60, 34
    ground = H - 4                          # 图里地面线（再往下 4 行是翻起来的土）
    c = raster(W, H, 33, 14, -34, damaged=True, broken_fin=True)
    a = c.a
    # 地面以下的船身被土埋住
    a[ground:, :, 3] = 0
    rng = np.random.default_rng(3)
    # 机头周围翻起的土堆：左右两个小坡
    for x in range(W):
        hl = 0
        for (mx, r, hgt) in ((14, 13, 6), (31, 8, 3)):
            if abs(x - mx) < r:
                hl = max(hl, int(round(hgt * (1 - (abs(x - mx) / r) ** 2))))
        if hl == 0:
            continue                         # 土堆以外：什么都不画，地面由背景画
        for y in range(ground - hl, min(H, ground + 1 + hl // 2)):
            d = y - (ground - hl)
            col = SOIL[4] if d == 0 else SOIL[3] if d == 1 and hl > 1 else SOIL[2] if y < ground else SOIL[1]
            a[y, x] = (*hexc(col), 255)
    # 几块飞出去的土 / 碎片（脱离的碎点）
    for (x, y, col) in ((2, ground - 3, SOIL[2]), (5, ground - 7, SOIL[3]), (46, ground - 2, HULL[1]),
                        (52, ground - 1, HULL[2]), (26, ground - 9, SOIL[2])):
        a[y, x] = (*hexc(col), 255)
    return c


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


if __name__ == "__main__":
    main()
