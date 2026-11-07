"""母星闪回第一次（追照片）路上的两个障碍（scripts/flashback.gd：晨撞上就停住，狂按 E 推开）。以后改障碍只改这个文件。

    python3 tools/flashback_obstacle_art.py [--preview 目录]

输出 art/flashback/：
- obstacle_barrier.png       施工路障：两个 A 字铁架 + 一块斜条纹的挡板 + 顶上一盏琥珀警示灯的灯罩（灯在 Godot 里一闪一闪地画）
- obstacle_box_a/b/c.png     倒在路中间的一摞纸箱（城市人群里「抱箱子低头」的人掉的），三只分开，最后一下被推散
11-07 作者：「中间会碰到障碍物，这个时候需要按E很多次来通过，障碍的风格按照现有的像素美术风格来生成」。
照 tools/city_art.py / flashback_train_art.py 的城市：低饱和的灰（暗的带一点冷、亮的带一点暖），光从上方偏右来
（右边、上边受光），1 倍像素，alpha 只有 0/255，不描边，不画虚线。暖色只给小面积（警示灯、纸箱），都比晨暗。
坐标：每张图底边就是地面（Godot 里 offset 让底边落在 GROUND 228）。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "art" / "flashback"

C = {
    # 铁架（和列车车身一族的灰）
    "iron_hi": (92, 100, 100), "iron": (48, 55, 57), "iron_lo": (30, 35, 37), "iron_dk": (16, 20, 22),
    # 挡板：褪色的白 / 锈红斜条，受光边亮一点
    "w_hi": (150, 148, 134), "w": (118, 117, 106), "w_lo": (84, 84, 77),
    "r_hi": (118, 70, 54), "r": (90, 52, 42), "r_lo": (64, 38, 32),
    "board_dk": (24, 26, 27),
    # 警示灯罩（灯芯在 Godot 里画）
    "lamp_cap": (40, 44, 44), "lamp_glass": (96, 70, 40), "lamp_glass_hi": (140, 104, 58),
    # 底座沙袋 / 配重块
    "bag": (52, 56, 52), "bag_hi": (78, 82, 74), "bag_dk": (30, 33, 31),
    # 纸箱：湿了的旧纸板，暖灰
    "box_hi": (120, 102, 78), "box": (92, 78, 60), "box_lo": (70, 59, 46), "box_dk": (44, 37, 30),
    "tape": (128, 120, 98), "tape_lo": (96, 90, 74), "wet": (60, 51, 40), "label": (138, 134, 120),
}


def px(im, x, y, c):
    if 0 <= x < im.width and 0 <= y < im.height:
        im.putpixel((x, y), c + (255,))


def rect(im, x, y, w, h, c):
    for j in range(y, y + h):
        for i in range(x, x + w):
            px(im, i, j, c)


# ----------------------------------------------------------------------------------------------- 施工路障
def barrier() -> Image.Image:
    W, H = 44, 34
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # A 字铁架：左右各一对斜腿（侧面看是一个 Λ），腿 2 像素粗，右边受光
    for (top, foot_l, foot_r) in [(9, 3, 15), (34, 28, 40)]:
        for y in range(14, H - 3):
            k = (y - 14) / (H - 4 - 14)
            xl = round(top - (top - foot_l) * k)
            xr = round(top + (foot_r - top) * k)
            px(im, xl, y, C["iron_lo"]); px(im, xl + 1, y, C["iron"])
            px(im, xr, y, C["iron"]); px(im, xr + 1, y, C["iron_hi"] if y % 5 else C["iron"])
        # 腿中间一道横撑
        rect(im, top - 3, 25, 8, 1, C["iron_lo"])
        rect(im, top - 2, 24, 6, 1, C["iron"])
    # 底下压着的两只沙袋（配重）
    for bx in (1, 26):
        rect(im, bx, H - 4, 16, 4, C["bag"])
        rect(im, bx + 1, H - 5, 14, 1, C["bag"])
        rect(im, bx + 2, H - 5, 12, 1, C["bag_hi"])
        rect(im, bx, H - 1, 16, 1, C["bag_dk"])
        px(im, bx + 8, H - 3, C["bag_dk"]); px(im, bx + 8, H - 4, C["bag_dk"])   # 扎口
    # 挡板：横跨两个架子，斜条纹（白 / 锈红，每 6 像素一换），上沿受光、下沿一道暗
    bx0, by0, bw, bh = 1, 12, 42, 9
    for y in range(by0, by0 + bh):
        for x in range(bx0, bx0 + bw):
            stripe = ((x - y) // 6) % 2 == 0
            if y == by0:
                c = C["w_hi"] if stripe else C["r_hi"]
            elif y >= by0 + bh - 2:
                c = C["w_lo"] if stripe else C["r_lo"]
            else:
                c = C["w"] if stripe else C["r"]
            px(im, x, y, c)
    rect(im, bx0, by0 + bh, bw, 1, C["board_dk"])
    for y in range(by0, by0 + bh):                     # 两头的端面暗一点
        px(im, bx0, y, C["board_dk"])
    for y in range(by0 + 1, by0 + bh):
        px(im, bx0 + bw - 1, y, C["w_lo"] if ((bx0 + bw - 1 - y) // 6) % 2 == 0 else C["r_lo"])
    # 挡板上两颗固定螺栓
    for x in (9, 34):
        px(im, x, by0 + 4, C["iron_dk"])
    # 顶上的警示灯罩（右边那个架子顶上）：灯芯 Godot 里画在 (34, 6)
    rect(im, 32, 9, 5, 3, C["lamp_cap"])
    rect(im, 32, 4, 5, 5, C["lamp_glass"])
    rect(im, 35, 4, 2, 4, C["lamp_glass_hi"])
    rect(im, 33, 3, 3, 1, C["lamp_cap"])
    return im


def barrier_down() -> Image.Image:
    """被推倒、拍在地上的路障：挡板平躺（只看得见上沿那一窄条斜纹），两个铁架歪在下面，沙袋滚到一边，灯罩掉在前面。"""
    W, H = 52, 10
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # 铁架的腿：几道歪着的暗线（压在挡板下面）
    for (x0, x1) in [(3, 12), (9, 1), (30, 40), (36, 27)]:
        for i in range(abs(x1 - x0) + 1):
            x = x0 + (i if x1 > x0 else -i)
            y = H - 2 - (i * 3) // max(1, abs(x1 - x0))
            px(im, x, y, C["iron_lo"])
            px(im, x, y + 1, C["iron_dk"])
    # 平躺的挡板：4 像素高，斜纹压扁（每 6 像素一换，一行错一格）
    for y in range(3, 7):
        for x in range(2, 44):
            stripe = ((x - y * 2) // 6) % 2 == 0
            if y == 3:
                c = C["w_hi"] if stripe else C["r_hi"]
            elif y == 6:
                c = C["w_lo"] if stripe else C["r_lo"]
            else:
                c = C["w"] if stripe else C["r"]
            px(im, x, y, c)
    rect(im, 2, 7, 42, 1, C["board_dk"])
    # 沙袋滚到右边一只
    rect(im, 44, H - 3, 7, 3, C["bag"])
    rect(im, 45, H - 4, 5, 1, C["bag_hi"])
    rect(im, 44, H - 1, 7, 1, C["bag_dk"])
    # 灯罩掉在前面（灯灭了）
    rect(im, 46, H - 7, 3, 3, C["lamp_glass"])
    px(im, 48, H - 7, C["lamp_glass_hi"])
    rect(im, 45, H - 4, 1, 1, C["lamp_cap"])
    return im


# ----------------------------------------------------------------------------------------------- 纸箱
def box(w: int, h: int, flaps: bool, label: bool) -> Image.Image:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rect(im, 0, 1, w, h - 1, C["box"])
    rect(im, 0, 1, w, 1, C["box_hi"])                 # 顶边受光
    rect(im, w - 2, 2, 2, h - 2, C["box_lo"])         # 右侧面（光从右上，侧面稍暗：纸箱侧面是另一个面）
    rect(im, w - 2, 1, 2, 1, C["box_hi"])
    rect(im, 0, h - 2, w, 2, C["box_dk"])             # 底边吸了水，暗
    rect(im, 0, h - 4, w - 2, 2, C["wet"])
    rect(im, 0, 2, 1, h - 4, C["box_lo"])
    # 一道封箱胶带竖着过中间
    tx = (w - 2) // 2 - 1
    rect(im, tx, 1, 3, h - 3, C["tape_lo"])
    rect(im, tx + 1, 1, 1, h - 3, C["tape"])
    if flaps:                                          # 翘起来的一片盖子
        rect(im, 1, 0, w // 3, 1, C["box_hi"])
    if label:                                          # 一张小标签
        rect(im, 2, h // 2 - 1, 4, 3, C["label"])
        px(im, 3, h // 2, C["tape_lo"]); px(im, 4, h // 2, C["tape_lo"])
    return im


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    out = {
        "obstacle_barrier.png": barrier(),
        "obstacle_barrier_down.png": barrier_down(),
        "obstacle_box_a.png": box(24, 17, False, True),
        "obstacle_box_b.png": box(19, 14, True, False),
        "obstacle_box_c.png": box(14, 11, False, False),
    }
    for name, im in out.items():
        im.save(OUT / name)
        print("wrote", OUT / name, im.size)
    if a.preview:
        p = Path(a.preview)
        p.mkdir(parents=True, exist_ok=True)
        sheet = Image.new("RGBA", (120, 54), (12, 15, 17, 255))
        sheet.alpha_composite(out["obstacle_barrier_down.png"], (2, 42))
        sheet.alpha_composite(out["obstacle_barrier.png"], (2, 4))
        sheet.alpha_composite(out["obstacle_box_a.png"], (56, 21))
        sheet.alpha_composite(out["obstacle_box_b.png"], (59, 7))
        sheet.alpha_composite(out["obstacle_box_c.png"], (84, 27))
        sheet.resize((sheet.width * 6, sheet.height * 6), Image.NEAREST).save(p / "obstacles_6x.png")


if __name__ == "__main__":
    main()
