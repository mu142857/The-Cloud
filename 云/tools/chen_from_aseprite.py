"""奥斯卡画的晨（art/characters/chen/chen_oscar.aseprite）→ 游戏用的精灵表 art/characters/chen/chen_oscar.png。

用 Aseprite 命令行把每一帧导出来，再做这几件事：
  1. 清杂点：半透明的像素（alpha < 255）一律去掉；和身体不连着的单个像素（右上角那几颗）去掉。
  2. 去掉纯黑 #000：斗篷最下面两行是纯黑，贴在地上像描了一道黑边 → 换成同一列上面的斗篷色；
     别处的纯黑（斗篷背后那条暗边）换成 DEEP，比斗篷暗、但不是死黑。原文件不动。
  3. 每帧裁成同一块 CROP（所有帧的身体都在里面），一行横排，帧号和 aseprite 里一样 0..30。
  4. 打印每段 tag 的帧号，对照 scripts/chen.gd 的 ANIMS。
  5. 斗篷换色：奥斯卡画的斗篷是几档近黑的灰，在暗背景里糊成一团 → 按 CLOAK 换成砖红（作者 2026-10 选定），见 CLOAKS。
  6. 算每帧「头」的中心（白发那团最亮像素的重心），存 data/chen_heads.json，给 chen.gd 画头发后面那圈淡光晕。

用法（工程根目录下）：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/chen_from_aseprite.py [源文件.aseprite]
不给源文件就用 art/characters/chen/chen_oscar.aseprite。奥斯卡改了图以后，把新文件拷过去覆盖再跑一次。
只重算头的位置（不用 Aseprite，读现成的 chen_oscar.png）：tools/chen_from_aseprite.py --heads
斗篷颜色：默认 CLOAK（砖红 brick）。--cloak=orig 回到奥斯卡原图的近黑灰，--cloak=sea / oat / mist 换成别的方案
  （都是写 chen_oscar.png + chen_heads.json，也就是正式换上）。
  只出候选、不动正在用的图：--cloak=all → 每个方案另存 chen_oscar_<方案>.png（含 orig）。
  游戏里看候选：Godot … res://scenes/forest_test.tscn -- --chen_sheet=res://art/characters/chen/chen_oscar_sea.png
"""
import json
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "art/characters/chen/chen_oscar.aseprite"
OUT = ROOT / "art/characters/chen/chen_oscar.png"
ASEPRITE = "/Applications/Aseprite.app/Contents/MacOS/aseprite"

# aseprite 画布 111×105 里裁出来的这一块（x0, y0, x1, y1）：站着时身体中线 x≈40、脚底 y=80，
# 所以 chen.gd 里 FOOT = (40 - 12, 80 - 24) = (28, 56)
CROP = (12, 24, 80, 84)
MIN_PIECE = 3          # 和身体不连着、小于这么多像素的碎块算杂点
DEEP = (34, 34, 40)    # 纯黑换成的颜色：斗篷最暗那档（37,37,37）再暗一点、带一点冷
HEM_ROWS = 2           # 每一列最下面几格是纯黑就算「底边黑线」
HEADS = ROOT / "data/chen_heads.json"
HAIR_L = 0.75          # 亮度高过这个的算白发（白发 L≈0.85~0.95，斗篷 0.13~0.25，手和腿 0.4 左右）

CLOAK = "brick"        # 正式用的斗篷配色（CLOAKS 里的名字；"orig" = 奥斯卡原图的灰，不换）

# 斗篷换色（--cloak=方案）：原图斗篷用的每一档颜色 → 方案里对应的一档，一一映射，档数和形状不变；
# 手、腿、鞋、头发、眼睛、脸上的粉不在表里，不动。CLOAK_SRC 按原图的明暗从暗到亮排（unblack 之后的颜色）。
# 方案的颜色是在 OKLCh 里定的：主色（原图 45 灰那档）定 L / C / h，其余各档按原图和主色的明度差 ×1.5 拉开
# （原图档距太小，换亮以后要拉开一点才看得出褶子），暗档色相往冷 / 往深偏、亮档往暖 / 往浅偏；里衬比主色暗 0.06。
CLOAK_SRC = [
    (31, 31, 31), (34, 34, 34), DEEP, (37, 37, 37), (42, 42, 42),   # 暗档（31~42 只在「看」那几帧出现；DEEP = 背后暗边）
    (45, 45, 45),                                                   # 主色：站着时斗篷大部分
    (56, 56, 56), (65, 65, 65), (62, 70, 65),                       # 亮档：褶子受光面、跑步时外侧、背后那道偏绿的边
    (104, 93, 111),                                                 # 里衬：跑步时甩起来露出的内侧
]
CLOAKS = {
    # 海蓝（作者提的）：主色 OKLCh(0.50, 0.09, 242)，暗档偏靛（h 260），亮档偏青（h 232）
    "sea": [(49, 75, 118), (49, 81, 124), (54, 81, 127), (48, 91, 134), (47, 98, 141),
            (45, 105, 146),
            (62, 126, 163), (75, 142, 176), (70, 137, 171),
            (56, 83, 124)],
    # 砖红 / 胭脂：主色 OKLCh(0.45, 0.11, 29)，暗档偏胭脂（h 18），亮档偏砖橙（h 38）
    "brick": [(103, 37, 42), (109, 40, 44), (112, 42, 48), (121, 47, 46), (129, 53, 47),
              (136, 57, 48),
              (154, 79, 62), (168, 96, 74), (164, 91, 70),
              (109, 46, 48)],
    # 燕麦 / 暖米灰：主色 OKLCh(0.60, 0.03, 75)，最亮一档 0.72，仍比白发（0.83~0.90）暗一大截
    "oat": [(115, 99, 89), (120, 104, 93), (123, 106, 95), (128, 113, 99), (134, 120, 104),
            (139, 126, 109),
            (158, 146, 128), (172, 163, 143), (167, 157, 138),
            (120, 104, 94)],
    # 雾灰蓝：主色 OKLCh(0.52, 0.035, 240)，低饱和
    "mist": [(71, 81, 99), (74, 86, 104), (77, 88, 106), (80, 95, 112), (84, 102, 118),
             (87, 108, 123),
             (106, 128, 140), (121, 143, 154), (116, 138, 149),
             (78, 89, 105)],
}


def export(src: Path, tmp: Path):
    sheet, data = tmp / "sheet.png", tmp / "data.json"
    subprocess.run([ASEPRITE, "-b", str(src), "--list-tags", "--sheet", str(sheet), "--sheet-type", "horizontal",
                    "--data", str(data), "--format", "json-array"], check=True, capture_output=True)
    return np.array(Image.open(sheet).convert("RGBA")), json.loads(data.read_text())


def pieces(mask):
    """8 连通的连通块，每块是 [(y, x), …]"""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        seen[y, x] = True
        q, px = deque([(y, x)]), []
        while q:
            cy, cx = q.popleft()
            px.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
        out.append(px)
    return out


def clean(frame):
    frame = frame.copy()
    frame[frame[..., 3] < 255] = 0
    ps = pieces(frame[..., 3] > 0)
    biggest = max(len(p) for p in ps)
    removed = 0
    for p in ps:
        if len(p) < biggest and len(p) < MIN_PIECE:
            for y, x in p:
                frame[y, x] = 0
            removed += len(p)
    return frame, removed


def unblack(frame):
    """斗篷底边的纯黑换成上面的斗篷色，其余纯黑换成 DEEP。返回换了几个像素。"""
    rgb, op = frame[..., :3], frame[..., 3] == 255
    black = op & (rgb.sum(-1) == 0)
    n = int(black.sum())
    for x in np.nonzero(black.any(0))[0]:
        ys = np.nonzero(op[:, x])[0]
        above = [y for y in ys if not black[y, x]]
        for y in ys[-HEM_ROWS:]:
            if black[y, x]:
                up = [a for a in above if a < y and int(rgb[a, x].max()) < 80]   # 只借斗篷那种暗色，别借到手或头发
                if up:
                    rgb[y, x] = rgb[up[-1], x]
                    black[y, x] = False
    rgb[black] = DEEP
    return n


def recolor_cloak(sheet, name):
    """斗篷换色：按 CLOAK_SRC → CLOAKS[name] 一一换。换完的颜色不能撞上图里别处（手、腿、头发）已有的颜色。"""
    if name == "orig":
        return sheet
    pal = CLOAKS[name]
    assert len(pal) == len(CLOAK_SRC) and len(set(pal)) == len(pal), f"{name}：档数不对或有重复"
    rgb, op = sheet[..., :3], sheet[..., 3] == 255
    masks = [op & (rgb == src).all(-1) for src in CLOAK_SRC]
    rest = op & ~np.any(masks, axis=0)
    others = {tuple(int(v) for v in c) for c in rgb[rest]}
    assert not others & set(pal), f"{name}：和图里别的颜色撞了 {others & set(pal)}"
    out = sheet.copy()
    for m, dst in zip(masks, pal):
        out[m, :3] = dst
    return out


def write_heads(png: Path = OUT, out: Path = HEADS, fw: int = 0):
    """每帧白发那团（最亮像素）的重心，帧里的像素坐标（左上角原点、美术朝右）。chen.gd 用它摆头发后面的光晕。"""
    a = np.array(Image.open(png).convert("RGBA")).astype(float)
    fw = fw or (CROP[2] - CROP[0])
    heads = []
    for i in range(a.shape[1] // fw):
        f = a[:, i * fw:(i + 1) * fw]
        lum = (0.3 * f[..., 0] + 0.59 * f[..., 1] + 0.11 * f[..., 2]) / 255.0
        ys, xs = np.nonzero((f[..., 3] > 0) & (lum > HAIR_L))
        heads.append([round(float(xs.mean()), 1), round(float(ys.mean()), 1)] if len(xs) else None)
    out.write_text(json.dumps({"frame_w": fw, "heads": heads}, ensure_ascii=False) + "\n")
    print(f"→ {out.relative_to(ROOT)}：{len(heads)} 帧的头中心")


def main():
    if "--heads" in sys.argv[1:]:
        write_heads()
        return
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cloak = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--cloak=")), CLOAK)
    assert cloak in ("all", "orig", *CLOAKS), f"没有这个斗篷方案：{cloak}（可选 orig / {' / '.join(CLOAKS)} / all）"
    src = Path(args[0]) if args else SRC
    with tempfile.TemporaryDirectory() as t:
        sheet, data = export(src, Path(t))
    x0, y0, x1, y1 = CROP
    frames = []
    for i, f in enumerate(data["frames"]):
        r = f["frame"]
        fr, removed = clean(sheet[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]])
        unblack(fr)
        ys, xs = np.nonzero(fr[..., 3])
        assert xs.min() >= x0 and xs.max() < x1 and ys.min() >= y0 and ys.max() < y1, f"第 {i} 帧超出 CROP"
        frames.append(fr[y0:y1, x0:x1])
        if removed:
            print(f"帧 {i:2d}：去掉 {removed} 个杂点像素")
    sheet = np.concatenate(frames, axis=1)
    if cloak == "all":
        # 只出候选，不碰正在用的 chen_oscar.png 和 chen_heads.json（头发没变，头的位置一样）
        for name in ("orig", *CLOAKS):
            out = OUT.with_name(f"{OUT.stem}_{name}.png")
            Image.fromarray(recolor_cloak(sheet, name)).save(out)
            print(f"→ {out.relative_to(ROOT)}：斗篷 {name}")
        return
    Image.fromarray(recolor_cloak(sheet, cloak)).save(OUT)
    print(f"→ {OUT.relative_to(ROOT)}：{len(frames)} 帧，每帧 {x1 - x0}×{y1 - y0}，斗篷 {cloak}")
    for tag in data["meta"]["frameTags"]:
        ms = [data["frames"][i]["duration"] for i in range(tag["from"], tag["to"] + 1)]
        print(f"  {tag['name']}: 帧 {tag['from']}..{tag['to']}，ms {ms}")
    write_heads()


if __name__ == "__main__":
    main()
