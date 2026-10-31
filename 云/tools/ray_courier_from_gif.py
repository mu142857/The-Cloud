"""美术组的鳐鱼快递员（河流城市的邮差）→ art/characters/ray_courier/ray_swim.png + ray_courier.json。

原样导入：不改色、不改形、帧长保留 GIF 里的 200ms（美术组的图保留原时长）。做法和 niff_from_gif.py 一样：
找放大倍数（每 s×s 一格纯色）→ 按每格中心像素缩回 → GIF 透明色 → alpha 0，其余 255 →
所有帧同一块裁剪（不透明像素并集，四周留 PAD 格透明）→ 横排写 png → 自检：缩回的图放大 s 倍和原 GIF 逐像素一样。
不清杂点、不换色（有不透明纯黑就报错，让人来看）。

夜里的小暖灯不在这张图里：scripts/ray_courier.gd 在邮包上另画一层（json 的 lamp = 灯挂在帧内哪一格），原图一格不动。

用法（工程根目录下）：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/ray_courier_from_gif.py [源文件.gif]
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from niff_from_gif import find_scale, load, to_alpha  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = Path("/Users/jiamulin/Desktop/鳐鱼快递员.gif")
DIR = ROOT / "art/characters/ray_courier"
PAD = 1


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = Path(args[0]) if args else SRC
    big, ms = load(src)
    s = find_scale(big)
    frames = [to_alpha(b[s // 2::s, s // 2::s]) for b in big]
    h, w = frames[0].shape[:2]
    print(f"{src.name}：{big[0].shape[1]}×{big[0].shape[0]}，放大 {s} 倍 → 原生 {w}×{h}，{len(frames)} 帧，ms {ms}")
    for i, f in enumerate(frames):
        black = (f[..., 3] == 255) & (f[..., :3].sum(-1) == 0)
        assert not black.any(), f"帧 {i} 有不透明纯黑像素，按规矩不能偷偷换色，请人来看"

    union = np.any([f[..., 3] > 0 for f in frames], axis=0)
    ys, xs = np.nonzero(union)
    x0, x1, y0, y1 = xs.min() - PAD, xs.max() + 1 + PAD, ys.min() - PAD, ys.max() + 1 + PAD
    padded = [np.pad(f, ((PAD, PAD), (PAD, PAD), (0, 0))) for f in frames]
    crop = [p[y0 + PAD:y1 + PAD, x0 + PAD:x1 + PAD] for p in padded]
    fw, fh = int(x1 - x0), int(y1 - y0)
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "src").mkdir(exist_ok=True)
    shutil.copyfile(src, DIR / "src/ray_courier.gif")
    Image.fromarray(np.concatenate(crop, axis=1)).save(DIR / "ray_swim.png")
    print(f"→ ray_swim.png：{len(crop)} 帧横排，每帧 {fw}×{fh}（原生图里的 x {x0 + PAD}..{x1 - 1 - PAD}、y {y0 + PAD}..{y1 - 1 - PAD} 外留 {PAD} 格）")

    back = np.array(Image.open(DIR / "ray_swim.png").convert("RGBA"))
    for i, b in enumerate(big):
        canvas = np.zeros((h + 2 * PAD, w + 2 * PAD, 4), np.uint8)
        canvas[y0 + PAD:y1 + PAD, x0 + PAD:x1 + PAD] = back[:, i * fw:(i + 1) * fw]
        up = np.repeat(np.repeat(canvas[PAD:-PAD, PAD:-PAD], s, 0), s, 1)
        ref = to_alpha(b)
        same = (up[..., 3] == ref[..., 3]).all() and (up[ref[..., 3] > 0] == ref[ref[..., 3] > 0]).all()
        assert same, f"帧 {i} 放大回去和原 GIF 不一样"
    print(f"自检：{len(big)} 帧缩回再放大 {s} 倍，和原 GIF 逐像素一样")
    colors = {tuple(p) for c in crop for p in c[c[..., 3] > 0][:, :3]}
    print(f"共 {len(colors)} 色")

    # 小灯挂在邮包朝前（右）的那一侧：邮包顶 = 身子下面（第 16 行以后）第一行有 ≥7 格的（上面几行是吊带）；往下 1..3 行最右的不透明格再右一格。
    # 邮包每帧晃的位置不一样，灯跟着它（逐帧一个点）。
    lamp = []
    for c in crop:
        op = c[..., 3] > 0
        top = next(y for y in range(16, fh) if op[y].sum() >= 7)
        xr = max(int(np.nonzero(op[y])[0].max()) for y in range(top + 1, top + 4))
        lamp.append([xr + 1, top + 2])
    bag_bottom = [int(np.nonzero((c[..., 3] > 0).any(1))[0].max()) for c in crop]
    print(f"小灯（逐帧）{lamp}；邮包底 {bag_bottom}")

    # 远景用：整数缩小（2 倍、3 倍），不出新颜色、不糊。游戏里用「每 k×k 一块取块里最多的那个颜色」（ray_swim_d2.png）：
    # 纯最近邻（每块取一格，*_nearest.png，留着对比）会让邮包上的红邮戳这一帧有、下一帧没有，游起来一闪一闪。
    for k in (2, 3):
        for mode in ("nearest", "mode"):
            outs = []
            for c in crop:
                hh, ww = (fh + k - 1) // k * k, (fw + k - 1) // k * k
                p = np.zeros((hh, ww, 4), np.uint8)
                p[:fh, :fw] = c
                if mode == "nearest":
                    outs.append(p[k // 2::k, k // 2::k])
                    continue
                o = np.zeros((hh // k, ww // k, 4), np.uint8)
                for y in range(hh // k):
                    for x in range(ww // k):
                        blk = p[y * k:(y + 1) * k, x * k:(x + 1) * k].reshape(-1, 4)
                        vis = blk[blk[..., 3] > 0]
                        if len(vis) * 2 < len(blk):
                            continue
                        keys, cnt = np.unique(vis, axis=0, return_counts=True)
                        o[y, x] = keys[cnt.argmax()]
                outs.append(o)
            Image.fromarray(np.concatenate(outs, axis=1)).save(DIR / f"ray_swim_d{k}{'_nearest' if mode == 'nearest' else ''}.png")
    print("→ ray_swim_d2.png / ray_swim_d3.png（块内最多色，游戏用）、*_nearest.png（最近邻，对比用）")

    old = {}
    if (DIR / "ray_courier.json").exists():
        old = json.loads((DIR / "ray_courier.json").read_text(encoding="utf-8"))
    meta = {
        "_comment": "鳐鱼快递员 = 美术组画的河流城市邮差（青绿鳐鱼、身下绳子挂着棕色邮包，头朝右；这个世界里它在空中游）。"
                    "GIF 原样导入（tools/ray_courier_from_gif.py），不改色不改形不缩放，帧长保留 200ms；朝左用水平翻转。"
                    "scripts/ray_courier.gd 让它在河岸、市集的屋顶之间隔一阵游过去一次。"
                    "anchor = 身体中心（帧内像素，曲线上的点对着这里）；lamp = 邮包上挂小暖灯的那一格（夜里的识别，单独一层画，原图不动）；"
                    "bag = 邮包底边中点（停在窄桥边时这一格贴着栏杆）。重新导入不会覆盖手调过的 anchor / lamp / bag。",
        "sheet": "ray_swim.png",
        "frame": [fw, fh],
        "faces": "right",
        "anims": {"swim": {"frames": list(range(len(crop))), "ms": ms[0] if len(set(ms)) == 1 else ms}},
        "anchor": [fw // 2, 9],
        "lamp": lamp,
        "bag": bag_bottom,
        "small": {"2": "ray_swim_d2.png", "3": "ray_swim_d3.png"},
    }
    for k in ("anchor",):
        if k in old:
            meta[k] = old[k]
    (DIR / "ray_courier.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("→ ray_courier.json")


if __name__ == "__main__":
    main()
