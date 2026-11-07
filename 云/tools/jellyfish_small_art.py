"""小水母原尺寸图：终章「结局回看」水母那一镜（给过东西、被祝了寿 = 身边多了几只小水母）。

python3 tools/jellyfish_small_art.py [--preview 目录]  →  art/characters/jellyfish_small/jellyfish_small.png + .json

11-07 终章会话要的：原来是把大水母 jellyfish.png 最近邻缩 0.5 / 0.4 顶着，像素不齐。
scripts/ending_montage.gd 看到 jellyfish_small/jellyfish_small.json 就换上、不缩放。

- 颜色全部取自美术姐画的大水母（art/characters/jellyfish/jellyfish.png，一格不改色）：奶黄的伞顶、橙色十字、
  桃色一圈（十字右半边亮一档，和大图一样）、淡紫的裙边、灰紫 / 淡蓝的触须。不画光环（太小了画了是一团），伞上留一点高光。
- 14×14 一格。idle 四帧循环：伞一张一收（收的那帧伞窄一格、往上提一格），触须跟着往一边摆再摆回来。100ms 一帧。
  上下浮是引擎做的（hover / bob），这里不画。
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "characters", "jellyfish_small")
FW, FH = 14, 14

# 大水母的颜色（字母 = 在大图里数出来的那几格颜色）
PAL = {
    "a": (255, 252, 218), "b": (255, 240, 168), "c": (255, 232, 120), "e": (222, 214, 154),
    "f": (255, 207, 90), "g": (255, 231, 223), "h": (240, 160, 45), "j": (255, 185, 42), "i": (243, 196, 175),
    "k": (255, 222, 255), "l": (219, 171, 149), "m": (220, 179, 234), "n": (199, 157, 199),
    "o": (248, 200, 248), "p": (124, 126, 155), "q": (168, 154, 189), "r": (164, 167, 204),
}

# 伞：张开 / 收拢（收拢的那帧窄一格、高一格）
BELL_OPEN = [
    ".....abba.....",
    "...aabhjbaa...",
    "..aabbhjbbaa..",
    "..eefhhjjfee..",
    "..eiffhjffie..",
    "..giiihjiiig..",
    "..kgilllligk..",
    "..mnonnnnonm..",
    "..mo.onno.om..",
]
BELL_SHUT = [
    ".....abba.....",
    "....abhjba....",
    "...abbhjbba...",
    "...efhhjjfe...",
    "...iffhjffi...",
    "...giihjiig...",
    "...kgllllgk...",
    "...mnonnonm...",
    "...mo.nn.om...",
]
TENT = [
    "...p.qmmq.p...",
    "..p..krrk..p..",
    "...p.rkkr.p...",
    "....r.rr.r....",
    "......o.......",
]


def frame(bell, lift, sway):
    """bell：伞；lift：伞往上提几格；sway：触须摆（每一行偏多少，从上往下）"""
    g = [["."] * FW for _ in range(FH)]
    top = max(0, 0 - lift)
    for j, row in enumerate(bell):
        y = j + top
        for x, ch in enumerate(row):
            if ch != "." and 0 <= y < FH:
                g[y][x] = ch
    t0 = len(bell) + top
    for j, row in enumerate(TENT):
        y = t0 + j
        dx = sway[j]
        for x, ch in enumerate(row):
            xx = x + dx
            if ch != "." and 0 <= y < FH and 0 <= xx < FW and g[y][xx] == ".":
                g[y][xx] = ch
    img = np.zeros((FH, FW, 4), np.uint8)
    for y in range(FH):
        for x in range(FW):
            if g[y][x] != ".":
                img[y, x] = (*PAL[g[y][x]], 255)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview")
    a = ap.parse_args()
    frames = [
        frame(BELL_OPEN, 0, (0, 0, 0, 0, 0)),     # 0 张开，触须直
        frame(BELL_OPEN, 0, (0, 0, 1, 1, 1)),     # 1 触须往右摆
        frame(BELL_SHUT, 0, (0, 1, 1, 1, 1)),     # 2 一收：伞窄一格，触须甩开
        frame(BELL_OPEN, 0, (0, 0, 0, 1, 0)),     # 3 张开回来，触须收回
    ]
    os.makedirs(OUT, exist_ok=True)
    sheet = np.concatenate(frames, axis=1)
    Image.fromarray(sheet).save(os.path.join(OUT, "jellyfish_small.png"))
    cfg = {
        "_comment": "小水母原尺寸图：tools/jellyfish_small_art.py 生成，颜色全取自美术姐画的大水母，不画光环。"
                    "终章结局回看水母那一镜用（有这个文件就不再把大水母缩小）。idle 四帧：伞一张一收、触须摆，100ms 一帧；"
                    "上下浮靠 hover / bob（比大水母小、快一点，几只不会同步）。tint false = 自己会发光，不着色不压暗。"
                    "anchor = 最下面那根触须的底。",
        "frame": [FW, FH],
        "sheet": "jellyfish_small.png",
        "anchor": [6, 13],
        "faces": "right",
        "ms": 100,
        "tint": False,
        "pass": True,
        "hover": 6,
        "bob": 2,
        "bob_s": 2.6,
        "head": 22,
        "speed": 20,
        "color": "#e8c8f0",
        "anims": {"idle": {"frames": [0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3], "loop": True}},
        "alias": {"talk": "idle", "walk": "idle"},
    }
    with open(os.path.join(OUT, "jellyfish_small.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
        big = Image.open(os.path.join(ROOT, "art/characters/jellyfish/jellyfish.png")).convert("RGBA")
        v = Image.new("RGBA", (32 + 6 + (FW + 3) * 4, 32), (30, 40, 60, 255))
        v.alpha_composite(big, (0, 0))
        for i in range(4):
            v.alpha_composite(Image.fromarray(frames[i]), (38 + i * (FW + 3), 32 - FH - 2))
        v.resize((v.width * 12, v.height * 12), Image.NEAREST).save(os.path.join(a.preview, "jellyfish_small_12x.png"))
    print("写了", os.path.join(OUT, "jellyfish_small.png"))


if __name__ == "__main__":
    main()
