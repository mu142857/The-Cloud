"""南桥「跟着痕迹走」（11-06）用的几张小图，并把对应的物件 / marker 写进 art/river_city/southbridge/room.json。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/southbridge_trail_art.py

南桥的 main.png 作者手改过（art/手改清单.json），tools/river_warehouse_bridge_art.py 不许再生成南桥，所以这里只出单独的物件图、只改 room.json 里这几项。
- southbridge_footprints.png：对的桥洞底下那一个大脚印（2 帧：陷在泥里 / 看过以后积水映着月光）；
- trail_print.png / trail_print_b.png：一路亮起来的脚印（2 帧：空 / 亮），左右脚两种；
- southbridge_lamps.png：三盏全往右歪的浮灯（被它拖过去的方向），绳子绷向右边；
- southbridge_hair.png：石沿上挂的一撮粗毛（2 帧：空 / 有）。
规则和别的图一样：1 倍像素，alpha 只有 0/255，光从右上来，暖色只给灯。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
import river_art as RA  # noqa: E402
import river_bank_moon_art as bm  # noqa: E402

OUT = TOOLS.parent / "art" / "river_city" / "southbridge"


def blue(L, C=0.03, h=250.0):
    return tuple(int(v) for v in bm.B(L, C, h))


DARK = [blue(0.07, 0.02, 262), blue(0.105, 0.025, 258), blue(0.15, 0.03, 254)]
GLOW = [blue(0.3, 0.035, 240), blue(0.4, 0.04, 234), blue(0.56, 0.04, 226)]
WOOD = [(30, 24, 26), (46, 36, 34), (66, 50, 42)]
IRON = [blue(0.16, 0.015, 250), blue(0.25, 0.015, 248)]
FLAME = [(122, 74, 34), (196, 134, 62), (238, 196, 118)]
HAIR = [(52, 44, 44), (78, 66, 60), (104, 90, 78)]
ROPE = blue(0.3, 0.012, 80)
TRAIL = [(922, 3), (980, 9), (1038, 3), (1094, 9), (1152, 3), (1208, 9), (1266, 3), (1322, 9), (1380, 3), (1438, 9), (1494, 3),
         (1552, 9), (1608, 3), (1658, 6), (1696, 5), (1734, 7)]
# (脚印中心 x, 离地几行)：地面从 sb_ground 读（坡上的脚印跟着坡走）


def foot_pixels(w, h, mirror_y=False):
    """大象的脚印（透视里压扁的地面，朝右）：一只圆脚掌 + 前沿三个分开的趾甲。返回 档位图：0 = 空，1 = 压痕的暗边，2.. = 坑里积水。"""
    out = np.zeros((h, w), int)
    cx, cy = (w - 6) / 2.0, (h - 1) / 2.0
    rx, ry = (w - 6) / 2.0, (h - 1) / 2.0 - 0.5
    for y in range(h):
        for x in range(w):
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d <= 1.0:
                out[y, x] = 1 if d > 0.62 else (2 if d > 0.3 else 3)
    tx = int(cx + rx) + 2
    for k, (ty, dx) in enumerate(((cy - ry * 0.75, -2), (cy, 0), (cy + ry * 0.75, -2))):    # 趾甲：和脚掌隔开一格
        for xx in (tx + dx, tx + dx + 1, tx + dx + 2):
            if 0 <= xx < w:
                out[int(round(ty)), xx] = 1 if xx == tx + dx + 2 else 2
    return out[::-1] if mirror_y else out


def paint_print(lv, lit):
    """lit = 坑里积了水映月亮（一道窄的水光）；否则只是陷在泥里的暗坑（左下那圈内壁一点受光）。"""
    h, w = lv.shape
    a = np.zeros((h, w, 4), np.uint8)
    for y in range(h):
        for x in range(w):
            k = lv[y, x]
            if k == 0:
                continue
            if lit:
                c = {1: DARK[1], 2: GLOW[0], 3: GLOW[1]}[int(k)]
            else:
                c = {1: DARK[2] if y >= h / 2 else DARK[0], 2: DARK[0], 3: DARK[0]}[int(k)]
            a[y, x, :3] = c
            a[y, x, 3] = 255
    if lit:                                                            # 水面上一道月光（只有一行、几格）
        y = h // 2 - 1
        xs = np.nonzero(lv[y] == 3)[0]
        if len(xs) > 3:
            for x in xs[1:len(xs) - 1]:
                a[y, x, :3] = GLOW[2]
    return a


def big_print():
    lv = foot_pixels(26, 11)
    return np.concatenate([paint_print(lv, False), paint_print(lv, True)], axis=1)


def trail_print(flip):
    lv = foot_pixels(22, 9, mirror_y=flip)
    return np.concatenate([np.zeros((9, 22, 4), np.uint8), paint_print(lv, True)], axis=1)


def _lamp_sprite(lit):
    """竖着的一盏浮灯：底下小木托，一截粗杆，上面方灯罩 + 铁盖。原点在木托中间（返回 图, 木托中心 x, 木托中心 y）。"""
    W, H_ = 16, 26
    a = np.zeros((H_, W, 4), np.uint8)

    def rect(x0, y0, x1, y1, c):
        a[y0:y1 + 1, x0:x1 + 1, :3] = c
        a[y0:y1 + 1, x0:x1 + 1, 3] = 255

    rect(1, 22, 14, 25, WOOD[1])
    rect(1, 22, 14, 22, WOOD[2])
    rect(1, 25, 14, 25, WOOD[0])
    rect(7, 13, 8, 21, IRON[0])
    rect(8, 13, 8, 21, IRON[1])
    rect(4, 3, 11, 12, IRON[0])                                        # 灯罩框
    if lit:
        rect(5, 4, 10, 11, FLAME[0])
        rect(6, 5, 9, 10, FLAME[1])
        rect(7, 6, 8, 9, FLAME[2])
    else:
        rect(5, 4, 10, 11, blue(0.13, 0.02, 252))
        rect(9, 5, 10, 8, blue(0.2, 0.025, 248))
    rect(5, 1, 10, 2, IRON[1])                                         # 铁盖
    rect(7, 0, 8, 0, IRON[1])
    return a, 7.5, 24.0


def lamps():
    """三盏浮灯，全往右歪（被它拖过去的方向），木托一头翘起、一头陷进泥里；绳子绷直串起来，最后一段一直扯到右边泥里。只有最近的一盏还亮着。"""
    W, H_ = 74, 34
    a = np.zeros((H_, W, 4), np.uint8)
    base = H_ - 1
    tops = []
    for fx, lit, ang in ((9, True, 26.0), (31, False, 30.0), (52, False, 34.0)):
        spr, px, py = _lamp_sprite(lit)
        th = np.radians(ang)
        cs, sn = np.cos(th), np.sin(th)
        for y in range(H_):
            for x in range(W):
                dx, dy = x - fx, y - (base - 1)
                sx = cs * dx + sn * dy + px                            # 反着转回竖直的图取色
                sy = -sn * dx + cs * dy + py
                ix, iy = int(round(sx)), int(round(sy))
                if 0 <= ix < spr.shape[1] and 0 <= iy < spr.shape[0] and spr[iy, ix, 3] and y <= base:
                    a[y, x] = spr[iy, ix]
        tx = fx + cs * (0) + sn * 22
        ty = base - 1 - cs * 22
        tops.append((int(round(tx)), int(round(ty))))

    def seg(x0, y0, x1, y1):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for t in range(n + 1):
            xx, yy = int(round(x0 + (x1 - x0) * t / n)), int(round(y0 + (y1 - y0) * t / n))
            if 0 <= xx < W and 0 <= yy < H_ and not a[yy, xx, 3]:
                a[yy, xx, :3] = ROPE
                a[yy, xx, 3] = 255

    for p0, p1 in zip(tops[:-1], tops[1:]):
        seg(p0[0], p0[1], p1[0], p1[1])
    seg(tops[-1][0], tops[-1][1], W - 1, base)
    return a


def hair():
    """一撮粗毛：七八根硬毛从一点往下扎开，上深下浅，长短不一。"""
    W, H_ = 14, 16
    a = np.zeros((H_, W, 4), np.uint8)
    rng = np.random.default_rng(9)
    for k in range(7):
        x = 7 + rng.uniform(-1.5, 1.5)
        slope = (k - 3.0) * 0.26 + rng.uniform(-0.08, 0.08)
        ln = int(rng.integers(6, 12))
        for t in range(ln):
            xx, yy = int(round(x + slope * t)), t
            if 0 <= xx < W and yy < H_:
                a[yy, xx, :3] = HAIR[0] if t < 3 else (HAIR[1] if t < ln - 3 else HAIR[2])
                a[yy, xx, 3] = 255
    return np.concatenate([np.zeros_like(a), a], axis=1)


def ground(cfg, x):
    xs = [p[0] for p in cfg["ground"]]
    ys = [p[1] for p in cfg["ground"]]
    return int(round(np.interp(x, xs, ys)))


def main():
    Image.fromarray(big_print()).save(OUT / "southbridge_footprints.png")
    Image.fromarray(trail_print(False)).save(OUT / "trail_print.png")
    Image.fromarray(trail_print(True)).save(OUT / "trail_print_b.png")
    Image.fromarray(lamps()).save(OUT / "southbridge_lamps.png")
    Image.fromarray(hair()).save(OUT / "southbridge_hair.png")
    p = OUT / "room.json"
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg.pop("viewfinder", None)
    ob = cfg["objects"]
    ob["southbridge_footprints"] = {"x": 858, "y": 231, "w": 26, "h": 11, "frames": 2, "states": {"default": 0, "seen": 1}}
    ob["southbridge_lamps"] = {"x": 888, "y": 195, "w": 74, "h": 34, "frames": 1}
    ob["southbridge_hair"] = {"x": 832, "y": 83, "w": 14, "h": 16, "frames": 2, "states": {"default": 0, "shown": 1}}
    mk = cfg["markers"]
    mk.pop("southbridge_view_spot", None)
    mk["southbridge_lamps"] = 900
    for i, (x, dy) in enumerate(TRAIL):
        oid = "south_trail_%d" % i
        ob[oid] = {"x": x - 11, "y": ground(cfg, x) + dy - 1, "w": 22, "h": 9, "frames": 2, "img": "trail_print_b.png" if i % 2 else "trail_print.png",
                   "states": {"default": 0, "lit": 1}}
        mk[oid] = x
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ok", len(TRAIL), "prints")


if __name__ == "__main__":
    main()
