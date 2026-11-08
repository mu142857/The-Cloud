"""母兔（兔子首领想跳舞给她看的那只，第一章 rabbit_doe、终章「结局回看」）原尺寸图。

python3 tools/rabbit_doe_art.py [--preview 目录]  →  art/characters/rabbit_doe/rabbit_doe.png + rabbit_doe.json

11-08 作者：「兔子妹妹的样子按照当前美术风格修改，把蝴蝶结加入得自然一点」。
原来是兔子 rabbit.png 原样 + 引擎在头顶贴一块粉色 Polygon2D（不跟着呼吸动、没有明暗、像贴纸飘在耳朵前面）。

- 直接用 tools/rabbit_art.py 的部件和画法（同一套不描边、光从左上、朝右），只换参数：
  毛色往奶粉偏一点（色阶 5、6 两档换掉），耳朵往后收一点、前耳尖软软地往后弯，眼睛多一根睫毛。
- 蝴蝶结画进像素里：系在前耳根上（耳朵从结里穿出去），两片结翼 + 中间的结，三档粉 + 一格暗色结，
  光同样从左上来；每一帧按那一帧的头和耳朵位置放，呼吸时跟着头一起往下一格。
- 只要 idle（呼吸 + 前耳抖一下），别的动作都退回 idle（npc_generic 按 alias）。帧 44×52，脚底 (22, 50)，和兔子一样。
  npc_generic.art_for() 看到 rabbit_doe/rabbit_doe.json 就用它，不再借兔子的图、也不再贴 Polygon2D 蝴蝶结。
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rabbit_art as R  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "characters", "rabbit_doe")
FW, FH = R.FW, R.FH

# 兔子的色阶，毛的两档往奶粉偏一点（母兔比首领浅、暖一点，站在一起分得开）
RAMP = list(R.RAMP)
RAMP[5] = (222, 146, 112)
RAMP[6] = (246, 186, 158)

# 蝴蝶结：亮 / 平常 / 暗 / 结
BOW = [(246, 178, 190), (220, 128, 152), (170, 82, 112), (120, 54, 78)]
# 7×5，结在正中；. = 空，L/B/D/K = 上面四档。两片三角结翼在结上收窄，左边那片受光、右边那片背光
BOW_PX = [
    "LB...BD",
    "LBB.BBD",
    "LBBKBBD",
    "BBD.BDD",
    "BD...DD",
]

IDLE = R.pose(earF=12.0, earB=22.0, ear_len=14.5)
POSES = {
    "idle": IDLE,
    "idle_b": dict(IDLE, head=(0.0, 1.0), arm_y=1.0, earF=14.0, earB=24.0, sq=0.6),
    "idle_t": dict(IDLE, earF=4.0),
}


def head_c(p):
    return (23.0 + p["lean"] + p["head"][0], 23.0 + p["dy"] + p["head"][1])


def render(p):
    R.RAMP = RAMP
    img = R.tidy(R.render(p))
    hx, hy = head_c(p)
    # 睫毛：眼睛（rabbit_art 里 ex = 头 + 2，ey = 头 - 1.5）右上角斜出去一格
    ex, ey = int(round(hx + 2.0)), int(round(hy - 1.5))
    for x, y in ((ex + 2, ey - 1),):
        if 0 <= y < FH and 0 <= x < FW and img[y, x, 3] > 0:
            img[y, x] = (*RAMP[1], 255)
    # 蝴蝶结：系在耳根后面一点（结心在前耳根往后两格），坐在头顶上，不挡眼睛
    bx, by = int(round(hx + 0.5)) - 5, int(round(hy - 5.0)) - 2
    for j, row in enumerate(BOW_PX):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            x, y = bx + i, by + j
            if 0 <= x < FW and 0 <= y < FH:
                img[y, x] = (*BOW["LBDK".index(ch)], 255)
    return img


FRAMES = [("idle", POSES["idle"]), ("idle_b", POSES["idle_b"]), ("idle_t", POSES["idle_t"])]
ANIMS = {"idle": {"frames": [0] * 6 + [1] * 6 + [0] * 6 + [1] * 6 + [0] * 3 + [2] * 2 + [0] * 3 + [1] * 6, "loop": True}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="另存一张放大 6 倍、和兔子首领并排的预览图到这个目录")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    sheet = np.zeros((FH, FW * len(FRAMES), 4), dtype=np.uint8)
    for i, (_, p) in enumerate(FRAMES):
        sheet[:, i * FW:(i + 1) * FW] = render(p)
    Image.fromarray(sheet).save(os.path.join(OUT, "rabbit_doe.png"))
    cfg = {
        "_comment": "母兔原尺寸图：tools/rabbit_doe_art.py 生成（借 tools/rabbit_art.py 的画法），毛色比兔子首领浅暖一点，"
                    "蝴蝶结画在前耳根上、跟着呼吸动。只有 idle，别的动作都退回 idle。画的是朝右，100ms 一帧。",
        "frame": [FW, FH],
        "sheet": "rabbit_doe.png",
        "anchor": list(R.FOOT),
        "faces": "right",
        "ms": 100,
        "tint": True,
        "head": 46,
        "speed": 30,
        "color": "#f6ba9e",
        "anims": ANIMS,
        "alias": {k: "idle" for k in ["talk", "walk", "nod", "laugh", "give", "hand", "point", "shrug", "bow", "hop",
                                       "dance_left", "dance_up", "dance_right", "dance_down"]},
    }
    with open(os.path.join(OUT, "rabbit_doe.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    if a.preview:
        chief = Image.open(os.path.join(ROOT, "art", "characters", "rabbit", "rabbit.png")).crop((0, 0, FW, FH))
        bg = Image.new("RGBA", (FW * 5, FH), (60, 80, 70, 255))
        bg.alpha_composite(chief, (0, 0))
        bg.alpha_composite(Image.fromarray(sheet), (FW + 8, 0))
        bg.resize((bg.width * 6, bg.height * 6), Image.NEAREST).save(os.path.join(a.preview, "rabbit_doe_preview.png"))
    print("rabbit_doe frames", len(FRAMES))


if __name__ == "__main__":
    main()
