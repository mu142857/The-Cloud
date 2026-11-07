"""小兔子（兔子的幼崽）原尺寸图：第一章兔子家的三只小兔子 rabbit_kit_1~3、终章「结局回看」那一窝。

python3 tools/rabbit_kit_art.py [--preview 目录]  →  art/characters/rabbit_kit/rabbit_kit.png + rabbit_kit.json

11-07 终章会话要的：原来是把兔子 rabbit.png 最近邻缩 0.57 顶着，像素不齐。npc_generic.art_for() 看到
rabbit_kit/rabbit_kit.json 就不再缩放，蒙太奇（scripts/ending_montage.gd）也一样。

- 和兔子（tools/rabbit_art.py）同一条暖棕色阶、同样不描边、光从左上来、画的是朝右。
- 幼崽：头大（头差不多和身子一样大）、耳朵短、身子圆、坐着团成一团。整只约 25 像素高（兔子 46）。
- 只要 idle：两帧换着呼吸（头和手往下一格、身子压扁一点），中间前耳抖一下，节奏和兔子 idle 一样。
  蹦是引擎整只往上抬，不用画。
- 帧 24×30，脚底 (12, 28)。
"""
import argparse
import json
import math
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "characters", "rabbit_kit")
FW, FH = 24, 30
FOOT = (12, 28)

# 和兔子同一条色阶（tools/rabbit_art.py 的 RAMP）
RAMP = [(78, 50, 50), (106, 59, 50), (153, 78, 56), (179, 94, 80), (200, 115, 90),
        (210, 133, 92), (240, 169, 140), (254, 208, 177), (255, 241, 204)]
FUR = 6
CREAM = 8
INNER = 4
EYE = 0
NOSE = 3


def ell_mask(cx, cy, rx, ry, ang=0.0):
    ys, xs = np.mgrid[0:FH, 0:FW]
    px = xs + 0.5 - cx
    py = ys + 0.5 - cy
    c, s = math.cos(ang), math.sin(ang)
    u = (px * c + py * s) / max(rx, 0.1)
    v = (-px * s + py * c) / max(ry, 0.1)
    m = u * u + v * v <= 1.0
    return m, px / max(rx, ry), py / max(rx, ry)


def limb(base, ang_deg, length, width):
    """从 base 往 ang 方向伸出去（0 = 朝下，90 = 朝右，180 = 朝上）"""
    a = math.radians(ang_deg)
    d = (math.sin(a), math.cos(a))
    return ell_mask(base[0] + d[0] * length / 2.0, base[1] + d[1] * length / 2.0,
                    length / 2.0, width / 2.0, math.atan2(d[1], d[0]))


IDLE = {"head": (0.0, 0.0), "sq": 0.0, "earF": 8.0, "earB": 20.0, "paw_y": 0.0}
POSES = {
    "idle": IDLE,
    "idle_b": dict(IDLE, head=(0.0, 1.0), sq=0.5, paw_y=1.0, earF=10.0, earB=22.0),   # 呼吸：头和手往下一格
    "idle_t": dict(IDLE, earF=-6.0),                                                   # 前耳抖一下
}


def render(p):
    lvl = np.full((FH, FW), -1, dtype=int)
    L = (-0.55, -0.83)

    def put(mask, base, nx, ny, bright=0.55, dark=-0.5, back=False):
        s = -(nx * L[0] + ny * L[1])
        v = np.full(mask.shape, base) + (s > bright).astype(int) - (s < dark).astype(int)
        if back:
            v = v - 1
        v = np.clip(v, 0, len(RAMP) - 1)
        lvl[mask] = v[mask]

    hx, hy = p["head"]
    sq = p["sq"]
    head_c = (13.2 + hx, 14.0 + hy)
    body_c = (11.0, 22.0 + sq * 0.6)

    # 后耳（短、圆头）
    m, nx, ny = limb((head_c[0] - 2.4, head_c[1] - 3.4), 180.0 + p["earB"], 7.6, 3.6)
    put(m, FUR, nx, ny, back=True)
    # 后脚
    m, nx, ny = ell_mask(8.6, 27.6, 3.6, 1.4)
    put(m, FUR, nx, ny, back=True)
    # 尾巴：一团奶白
    m, nx, ny = ell_mask(4.8, 23.8 + sq * 0.4, 2.4, 2.3)
    put(m, CREAM, nx, ny, bright=0.6, dark=-0.2)
    # 大腿（坐着，圆鼓鼓）
    m, nx, ny = ell_mask(9.4, 24.6 + sq * 0.3, 5.2, 3.7)
    put(m, FUR, nx, ny)
    # 身子
    m, nx, ny = ell_mask(body_c[0], body_c[1], 6.0 + sq * 0.4, 5.4 - sq * 0.6)
    put(m, FUR, nx, ny)
    # 肚子
    bm, nx, ny = ell_mask(body_c[0] + 2.6, body_c[1] + 1.2, 2.4, 3.8 - sq * 0.5)
    put(bm & m, CREAM - 1, nx, ny, bright=0.2, dark=-0.6)
    # 前脚
    m, nx, ny = ell_mask(14.2, 27.7, 3.6, 1.3)
    put(m, FUR, nx, ny)
    # 头（大）
    m, nx, ny = ell_mask(head_c[0], head_c[1], 6.3, 5.6)
    put(m, FUR, nx, ny)
    head_m = m
    # 嘴：一小团奶色
    mm, nx, ny = ell_mask(head_c[0] + 4.2, head_c[1] + 2.2, 2.4, 1.8)
    put(mm & head_m, CREAM - 1, nx, ny, bright=0.1, dark=-0.9)
    # 前耳（外 + 里），短
    ear_base = (head_c[0] + 0.2, head_c[1] - 4.2)
    m, nx, ny = limb(ear_base, 180.0 + p["earF"], 8.0, 3.8)
    put(m, FUR, nx, ny)
    mi, _, _ = limb(ear_base, 180.0 + p["earF"], 6.0, 1.4)
    lvl[mi & m & ~head_m] = INNER
    # 前爪：缩在胸前一小团
    m, nx, ny = ell_mask(14.6, 20.6 + p["paw_y"], 1.7, 1.3)
    put(m, FUR, nx, ny, bright=0.2)
    lvl[m & (lvl >= 0)] = np.maximum(lvl[m & (lvl >= 0)], FUR)
    # 眼睛：幼崽眼睛大一点（两格高的深色 + 一格亮点在左上）
    ex, ey = int(round(head_c[0] + 2.0)), int(round(head_c[1] - 1.2))
    lvl[ey, ex] = EYE + 1
    lvl[ey, ex + 1] = EYE
    lvl[ey + 1, ex] = EYE
    lvl[ey + 1, ex + 1] = EYE
    lvl[ey, ex] = CREAM          # 眼睛的高光
    # 鼻子
    nx_, ny_ = int(round(head_c[0] + 6.1)), int(round(head_c[1] + 1.0))
    for x in (nx_, nx_ - 1):
        if lvl[ny_, x] >= 0:
            lvl[ny_, x] = NOSE
            break

    img = np.zeros((FH, FW, 4), dtype=np.uint8)
    for i, c in enumerate(RAMP):
        img[lvl == i] = (*c, 255)
    return img


def tidy(img):
    a = img[..., 3] > 0
    out = img.copy()
    for y in range(FH):
        for x in range(FW):
            if not a[y, x]:
                continue
            n = sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if 0 <= x + dx < FW and 0 <= y + dy < FH and a[y + dy, x + dx])
            if n <= 1:
                out[y, x] = 0
    return out


FRAMES = ["idle", "idle_b", "idle_t"]
ANIMS = {
    # 和兔子 idle 同一个节奏（100ms 一帧）
    "idle": {"frames": [0] * 6 + [1] * 6 + [0] * 6 + [1] * 6 + [0] * 3 + [2] * 2 + [0] * 3 + [1] * 6, "loop": True},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    sheet = np.zeros((FH, FW * len(FRAMES), 4), dtype=np.uint8)
    for i, nm in enumerate(FRAMES):
        sheet[:, i * FW:(i + 1) * FW] = tidy(render(POSES[nm]))
    Image.fromarray(sheet).save(os.path.join(OUT, "rabbit_kit.png"))
    cfg = {
        "_comment": "小兔子（兔子的幼崽）原尺寸图：tools/rabbit_kit_art.py 生成，和兔子同一条暖棕色阶，头大耳朵短。"
                    "第一章 rabbit_kit_1~3、终章结局回看那一窝都用它（有这个文件就不再把兔子缩 0.57）。"
                    "只有 idle（呼吸 + 前耳抖一下），别的动作都退回 idle；蹦是引擎整只往上抬。画的是朝右，100ms 一帧。",
        "frame": [FW, FH],
        "sheet": "rabbit_kit.png",
        "anchor": list(FOOT),
        "faces": "right",
        "ms": 100,
        "tint": True,
        "head": 26,
        "speed": 30,
        "color": "#f0a98c",
        "anims": ANIMS,
        "alias": {"talk": "idle", "walk": "idle", "nod": "idle", "laugh": "idle", "give": "idle",
                  "hand": "idle", "point": "idle", "shrug": "idle", "bow": "idle"},
    }
    with open(os.path.join(OUT, "rabbit_kit.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
        big = Image.open(os.path.join(ROOT, "art/characters/rabbit/rabbit.png")).convert("RGBA").crop((0, 0, 44, 52))
        v = Image.new("RGBA", (44 + 4 + FW * 3 + 8, 52), (118, 136, 116, 255))
        v.alpha_composite(big, (0, 0))
        for i in range(3):
            v.alpha_composite(Image.fromarray(sheet[:, i * FW:(i + 1) * FW]), (48 + i * (FW + 4), 52 - FH))
        v.resize((v.width * 8, v.height * 8), Image.NEAREST).save(os.path.join(a.preview, "rabbit_kit_8x.png"))
        z = Image.new("RGBA", (FW * 3 + 8, FH), (118, 136, 116, 255))
        for i in range(3):
            z.alpha_composite(Image.fromarray(sheet[:, i * FW:(i + 1) * FW]), (i * (FW + 4), 0))
        z.resize((z.width * 14, z.height * 14), Image.NEAREST).save(os.path.join(a.preview, "rabbit_kit_14x.png"))
    print("写了", os.path.join(OUT, "rabbit_kit.png"))


if __name__ == "__main__":
    main()
