"""母星闪回第二次的列车（scripts/flashback.gd：晨在城市街上追一列要开走的车，车门在她面前关上）。以后改这列车只改这个文件。

    python3 tools/flashback_train_art.py [--preview 目录]

输出 art/flashback/train_car.png（一节车厢，1 倍）、train_door_l.png / train_door_r.png（最后那扇门的两片门扇，Godot 里滑着关）。
11-04 作者：「我不知道为什么是去电梯，可以但是电梯做的更有质感一些吧」→ 一眼是列车：车厢、一排车窗、带胶条的门、
里面暖的灯光、站台边的安全线；地上的倒影是 city_wet.gdshader 照出来的（车画在湿地面前面）。
照 tools/city_art.py 的城市：低饱和的灰（暗的带一点冷、亮的带一点暖），光从上方偏右来（右边、上边受光），
大面积 L≈0.2~0.33；1 倍像素，alpha 只有 0/255，不描边，不画虚线。暖色只给车里的灯（琥珀，面积小、比晨暗）。
坐标：车厢图 W×H；安全线是第 PLAT+1、PLAT+2 行，Godot 里车厢左上角放在世界 y = 227-(PLAT+1) = 100（安全线落在晨脚底 227~228）。
最后那扇门（车尾，晨从左边追过来先到它）是开着的门洞（里面亮），门扇单独两张图；第二扇门画成关着的。
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "art" / "flashback"

W, H = 400, 132
DOOR = (24, 22, 36, 96)       # 尾门门洞 x, y, 宽, 高（门扇各一半）
DOOR2 = (318, 22, 36, 96)     # 第二扇门（关着）
WIN_Y, WIN_H, WIN_W = 30, 28, 34
WINS = [76, 122, 168, 214, 260, 372]  # 车窗左边 x（门旁边空开）
ROOF = 12
BELT = 64
SKIRT = 112
PLAT = 126                    # 站台边那条安全线的第一行

# 城市的灰（tools/city_art.py 实测：近黑偏冷，亮边一点点暖）
C = {
    "roof_hi": (120, 128, 128), "roof": (58, 64, 66), "roof_dk": (34, 39, 41),
    "body_hi": (64, 71, 72), "body": (44, 50, 52), "body_lo": (33, 38, 40), "body_dk": (22, 27, 29),
    "seam": (17, 21, 23), "rim": (92, 100, 100),
    "belt": (36, 58, 60), "belt_hi": (62, 84, 84),
    "frame": (12, 15, 17), "rubber": (3, 4, 6), "lip": (70, 78, 78),
    "skirt": (13, 16, 18), "skirt_hi": (30, 35, 37), "under": (5, 6, 8),
    "plat": (122, 112, 74), "plat_dk": (40, 38, 30), "plat_lo": (14, 15, 15),
    # 车里的暖光（上亮下暗）
    "in_lamp": (214, 184, 132), "in_hi": (150, 116, 74), "in": (118, 88, 55), "in_lo": (88, 64, 40),
    "in_dk": (58, 42, 27), "seat": (50, 37, 25), "pole": (196, 170, 124), "strap": (44, 32, 21),
    "far": (22, 27, 29), "far_hi": (40, 47, 49),
    "glare": (128, 122, 104), "stain": (36, 41, 43),
    "tail": (150, 38, 30), "tail_hi": (210, 70, 52), "lamp_off": (46, 34, 24),
}


def px(im, x, y, c):
    if 0 <= x < im.width and 0 <= y < im.height:
        im.putpixel((x, y), c + (255,))


def rect(im, x, y, w, h, c):
    for j in range(y, y + h):
        for i in range(x, x + w):
            px(im, i, j, c)


def interior(im, x, y, w, h, pole=None, straps=True, seat=True):
    """车里：顶上一条灯，往下从亮到暗（整行一档，不抖），吊环、扶杆、座椅靠背"""
    for j in range(h):
        k = j / max(1, h - 1)
        c = C["in_hi"] if k < 0.18 else C["in"] if k < 0.55 else C["in_lo"] if k < 0.85 else C["in_dk"]
        rect(im, x, y + j, w, 1, c)
    rect(im, x, y + 1, w, 1, C["in_lamp"])
    rect(im, x, y + 2, w, 1, C["in_hi"])
    if straps:
        rect(im, x, y + 4, w, 1, C["in_dk"])            # 吊环的横杆
        for sx in range(x + 3, x + w - 2, 7):
            rect(im, sx, y + 5, 1, 3, C["strap"])
            rect(im, sx - 1, y + 8, 3, 2, C["strap"])
            px(im, sx, y + 8, C["in_hi"])                  # 环中间透光
    if pole is not None:
        rect(im, pole, y + 3, 1, h - 3, C["pole"])
        rect(im, pole + 1, y + 3, 1, h - 3, C["in_lo"])
    if seat:
        rect(im, x, y + h - 7, w, 7, C["seat"])
        for sx in range(x + 1, x + w - 1, 9):
            rect(im, sx, y + h - 7, 7, 1, C["in_lo"])        # 靠背顶上受光


def window(im, x, seed):
    y = WIN_Y
    rect(im, x - 2, y - 2, WIN_W + 4, WIN_H + 4, C["frame"])
    rect(im, x - 2, y - 3, WIN_W + 4, 1, C["lip"])            # 窗框上沿受光
    rect(im, x + WIN_W + 2, y - 2, 1, WIN_H + 4, C["lip"])     # 右边受光
    interior(im, x, y, WIN_W, WIN_H, pole=x + 9 + (seed * 11) % 16)
    # 圆角：四个角各挖掉一格
    for cx, cy in [(x, y), (x + WIN_W - 1, y), (x, y + WIN_H - 1), (x + WIN_W - 1, y + WIN_H - 1)]:
        px(im, cx, cy, C["frame"])
    # 斜反光：从右上往左下两道
    k = 6 + (seed * 7) % 12
    for t in range(WIN_H):
        for d in (0, 1):
            gx = x + k + t + d
            gy = y + WIN_H - 1 - t
            if x < gx < x + WIN_W - 1 and gy > y + 2:
                px(im, gx, gy, C["glare"])
        gx = x + k + t + 8
        gy = y + WIN_H - 1 - t
        if x < gx < x + WIN_W - 1 and gy > y + 2:
            px(im, gx, gy, C["glare"])


def door_frame(im, x, y, w, h):
    """门洞外面一圈：暗框、黑胶条、受光的唇边；门楣上一盏关着的指示灯（Godot 里关门时点亮）"""
    rect(im, x - 4, y - 4, w + 8, h + 4, C["frame"])
    rect(im, x - 2, y - 2, w + 4, h + 2, C["rubber"])
    rect(im, x - 4, y - 5, w + 8, 1, C["lip"])
    rect(im, x + w + 4, y - 4, 1, h + 4, C["lip"])
    rect(im, x + w // 2 - 3, y - 9, 6, 2, C["lamp_off"])


def door_leaf(side):
    """一片门扇（宽 = 门洞一半）：车身的灰，一扇窄窗（暖光），合缝那边黑胶条 + 一道受光唇边，底下踢脚板暗一档"""
    w, h = DOOR[2] // 2, DOOR[3]
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for j in range(h):
        c = C["body_hi"] if j < 4 else C["body"] if j < 54 else C["body_lo"]
        rect(im, 0, j, w, 1, c)
    rect(im, 0, h - 8, w, 8, C["body_dk"])
    wx = 3 if side == 0 else w - 3 - 10
    rect(im, wx - 1, 9, 12, 38, C["frame"])
    interior(im, wx, 10, 10, 36, pole=None, straps=False, seat=False)
    for t in range(14):                                         # 窗上的斜反光
        gx, gy = wx + 3 + t // 2, 10 + 35 - t * 2
        if wx <= gx < wx + 10 and 10 <= gy < 46:
            px(im, gx, gy, C["glare"])
            px(im, gx, gy - 1, C["glare"])
    lead = w - 1 if side == 0 else 0
    rect(im, lead - (1 if side == 0 else 0), 0, 2, h, C["rubber"])
    rect(im, lead - 2 if side == 0 else 2, 0, 1, h, C["lip"])
    rect(im, 0, 0, w, 1, C["rim"])
    return im


def car():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # 车顶：两头圆，顶上一道受光
    for j in range(ROOF):
        inset = max(0, 4 - j) if j < 4 else 0
        c = C["roof_hi"] if j == 1 else C["roof"] if j < 6 else C["roof_dk"]
        rect(im, inset, j, W - inset * 2, 1, c)
    for bx in (70, 210, 300):                                    # 车顶上的设备箱
        rect(im, bx, 0, 28, 3, C["roof_dk"])
        rect(im, bx, 0, 28, 1, C["roof"])
    # 车身：上亮下暗三档 + 腰带
    for j in range(ROOF, SKIRT):
        c = C["body_hi"] if j < ROOF + 3 else C["body"] if j < BELT else C["body_lo"] if j < SKIRT - 10 else C["body_dk"]
        rect(im, 0, j, W, 1, c)
    rect(im, 0, BELT, W, 3, C["belt"])
    rect(im, 0, BELT, W, 1, C["belt_hi"])
    # 竖的板缝
    for sx in (68, 160, 252, 306, 366):
        rect(im, sx, ROOF + 2, 1, SKIRT - ROOF - 2, C["seam"])
        rect(im, sx + 1, ROOF + 2, 1, SKIRT - ROOF - 2, C["body_hi"] if False else C["body"])
    # 车尾：圆角、端面暗一档、尾灯
    rect(im, 0, ROOF, 3, SKIRT - ROOF, C["body_dk"])
    rect(im, 0, 94, 3, 5, C["tail"])
    px(im, 1, 95, C["tail_hi"])
    rect(im, W - 2, ROOF, 2, SKIRT - ROOF, C["rim"])            # 车头那端受光（光从右来）
    # 窗下拖出来的水渍（竖的，一像素宽，长短不一；照城市楼墙的做法）
    for i, x in enumerate(WINS + [DOOR[0] - 2, DOOR2[0] + DOOR2[2] + 2]):
        for k in range(3):
            sx = x + 4 + (i * 13 + k * 11) % 28
            ln = 6 + (i * 7 + k * 5) % 14
            if sx < W - 3:
                rect(im, sx, WIN_Y + WIN_H + 3, 1, ln, C["stain"])
    # 车窗
    for i, x in enumerate(WINS):
        if x + WIN_W < W - 4:
            window(im, x, i + 3)
    # 门：尾门开着（门洞里亮），第二扇关着（门扇画上去）
    x, y, w, h = DOOR
    door_frame(im, x, y, w, h)
    interior(im, x, y, w, h, pole=x + w // 2, straps=True, seat=False)
    rect(im, x + 4, y + 16, w - 8, 26, C["frame"])               # 对面那排车窗（外面是夜里的城，冷、暗）
    rect(im, x + 5, y + 17, w - 10, 24, C["far"])
    rect(im, x + 5, y + 17, w - 10, 1, C["far_hi"])
    for gx in range(x + 7, x + w - 6, 6):
        rect(im, gx, y + 22 + (gx * 7) % 9, 2, 3, C["far_hi"])   # 远处楼上几扇窗
    rect(im, x + w // 2, y + 3, 1, h - 3, C["pole"])            # 扶杆挡在对面窗前面
    rect(im, x + w // 2 + 1, y + 3, 1, h - 3, C["in_lo"])
    rect(im, x + 1, y + 50, w - 2, 4, C["seat"])                 # 对面的长座椅
    rect(im, x + 1, y + 50, w - 2, 1, C["in_lo"])
    rect(im, x + 1, y + 54, w - 2, 16, C["in_dk"])
    rect(im, x, y + h - 9, w, 9, C["in_dk"])                    # 车里地板
    rect(im, x, y + h - 9, w, 1, C["in_lo"])
    rect(im, x, y + h - 1, w, 1, C["lip"])                       # 门槛
    x2, y2, w2, h2 = DOOR2
    door_frame(im, x2, y2, w2, h2)
    im.alpha_composite(door_leaf(0), (x2, y2))
    im.alpha_composite(door_leaf(1), (x2 + w2 // 2, y2))
    # 裙板、底架（车轮藏在里面），一条台阶受光
    rect(im, 0, SKIRT, W, PLAT - SKIRT, C["skirt"])
    rect(im, 0, SKIRT, W, 1, C["skirt_hi"])
    for bx in (40, 300):                                         # 转向架的暗块
        rect(im, bx, SKIRT + 4, 56, PLAT - SKIRT - 4, C["under"])
        rect(im, bx + 6, SKIRT + 5, 10, 2, C["skirt_hi"])
        rect(im, bx + 40, SKIRT + 5, 10, 2, C["skirt_hi"])
    rect(im, x - 2, SKIRT, w + 4, 2, C["lip"])                   # 尾门下面的踏板
    # 站台边：暗缝、安全线（两行，暖灰）、下面一行暗
    rect(im, 0, PLAT, W, 1, C["plat_lo"])
    rect(im, 0, PLAT + 1, W, 2, C["plat"])
    rect(im, 0, PLAT + 3, W, 1, C["plat_dk"])
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    c = car()
    assert c.height == H
    c.save(OUT / "train_car.png")
    door_leaf(0).save(OUT / "train_door_l.png")
    door_leaf(1).save(OUT / "train_door_r.png")
    if a.preview:
        p = Path(a.preview)
        p.mkdir(parents=True, exist_ok=True)
        big = Image.new("RGBA", (W + 20, H + 20), (8, 10, 11, 255))
        big.alpha_composite(c, (10, 10))
        big.resize((big.width * 3, big.height * 3), Image.NEAREST).save(p / "train_car_3x.png")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
