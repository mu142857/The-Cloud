"""美术组的鲸鱼妹（= 妮芙，作者 10-29 确认）→ art/characters/niff/niff_swim.png + niff.json。

原样导入：不改色、不改形、帧长保留 GIF 里的 200ms（docs/river_plan.md 第 3.4 节）。和 snake_from_gif.py 的做法一样，
只有三处不同：
  1. 不清杂点：鲸鱼尾旁边那几颗分开的水花像素是画师故意画的，一颗都不去。
  2. 不换纯黑：这张图里没有不透明的纯黑（有的话直接报错，让人来看，而不是偷偷换色）。
  3. 写 niff.json（岸上 land、水下 swim 都用这张图；岸上悬浮，见 json 的 _comment）。
步骤：找放大倍数（每 s×s 一格纯色）→ 按每格中心像素缩回 → GIF 透明色 → alpha 0，其余 255 →
所有帧同一块裁剪（不透明像素并集，四周留 PAD 格透明）→ 横排写 png → 自检：缩回的图放大 s 倍和原 GIF 逐像素一样。

用法（工程根目录下）：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/niff_from_gif.py [源文件.gif]
美术组以后交别的动作，照同样的方法放进 art/characters/niff/，写进 niff.json 的 anims。
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent.parent
SRC = Path("/Users/jiamulin/Desktop/鲸鱼妹.gif")
DIR = ROOT / "art/characters/niff"
PAD = 2


def load(src: Path):
    im = Image.open(src)
    frames, ms = [], []
    for f in ImageSequence.Iterator(im):
        frames.append(np.array(f.convert("RGBA")))
        ms.append(int(f.info.get("duration", im.info.get("duration", 100))))
    return frames, ms


def find_scale(frames):
    h, w = frames[0].shape[:2]
    for s in sorted({d for d in range(1, min(h, w) + 1) if h % d == 0 and w % d == 0}, reverse=True):
        if all((np.repeat(np.repeat(f[s // 2::s, s // 2::s], s, 0), s, 1) == f).all() for f in frames):
            return s
    return 1


def to_alpha(f):
    f = f.copy()
    f[f[..., 3] < 128] = 0
    f[f[..., 3] > 0, 3] = 255
    return f


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
    shutil.copyfile(src, DIR / "src/whale_girl.gif")
    sheet = np.concatenate(crop, axis=1)
    Image.fromarray(sheet).save(DIR / "niff_swim.png")
    print(f"→ niff_swim.png：{len(crop)} 帧横排，每帧 {fw}×{fh}（原生图里的 x {x0 + PAD}..{x1 - 1 - PAD}、y {y0 + PAD}..{y1 - 1 - PAD} 外留 {PAD} 格）")

    # 自检：从 png 读回来，贴回原生画布、放大 s 倍，和原 GIF（透明处 alpha 归一）逐像素比
    back = np.array(Image.open(DIR / "niff_swim.png").convert("RGBA"))
    for i, b in enumerate(big):
        canvas = np.zeros((h + 2 * PAD, w + 2 * PAD, 4), np.uint8)
        canvas[y0 + PAD:y1 + PAD, x0 + PAD:x1 + PAD] = back[:, i * fw:(i + 1) * fw]
        up = np.repeat(np.repeat(canvas[PAD:-PAD, PAD:-PAD], s, 0), s, 1)
        ref = to_alpha(b)
        same = (up[..., 3] == ref[..., 3]).all() and (up[ref[..., 3] > 0] == ref[ref[..., 3] > 0]).all()
        assert same, f"帧 {i} 放大回去和原 GIF 不一样"
    print(f"自检：4 帧缩回再放大 {s} 倍，和原 GIF 逐像素一样")

    # 锚点：鲸壳底边中点（4 帧里最下面一行的中位数，横向取不透明像素并集的中线）
    bottoms = [int(np.nonzero((c[..., 3] > 0).any(1))[0].max()) for c in crop]
    cols = np.nonzero(np.any([c[..., 3] > 0 for c in crop], axis=0).any(0))[0]
    anchor = [int(round((cols.min() + cols.max()) / 2)), int(np.median(bottoms))]
    colors = {tuple(p) for c in crop for p in c[c[..., 3] > 0][:, :3]}
    print(f"每帧最下一行 {bottoms} → 锚点 {anchor}；共 {len(colors)} 色")

    meta = {
        "_comment": "妮芙 = 美术组的鲸鱼妹（作者 10-29 确认；10-30 作者定：整个河流篇都用这张鲸鱼壳动图，岸上不用占位）。swim 是 GIF 原样导入（tools/niff_from_gif.py），不改色不改形不缩放，"
                    "帧长保留 200ms；头朝右，朝左用水平翻转；tint false = 不着色不压暗。两套形态都用这张图：land = 坐在水壳里悬浮在地面上方 hover 像素、"
                    "整只上下 bob 像素（平滑正弦，bob_s 秒一圈，只动位置不改帧），地上留影子；swim = 水下，只浮 1 像素、没影子。alias 把 idle/walk/talk 都接到 swim；"
                    "剧本里别的动作（tail_up、write……）没有帧，退回这张动图并打 MISSING_ANIM niff.<名字>。anchor = 鲸壳底边中点（帧内像素坐标）；head = 对话框离脚底多高。",
        "sheet": "niff_swim.png",
        "frame": [fw, fh],
        "anchor": anchor,
        "faces": "right",
        "speed": 70,      # 10-30 作者：妮芙走得太慢、老得等她（原来默认 36；跟晨时最快 2.2 倍 ≈ 晨跑步 150）
        "anims": {"swim": {"frames": list(range(len(crop))), "ms": ms[0] if len(set(ms)) == 1 else ms}},
        "alias": {"idle": "swim", "walk": "swim", "talk": "swim"},
        "forms": {
            "land": {"hover": 2, "bob": 3, "bob_s": 2.8, "head": 48},
            "swim": {"bob": 1, "bob_s": 2.4, "head": 44},
        },
        "form": "land",
        "tint": False,
    }
    (DIR / "niff.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("→ niff.json")


if __name__ == "__main__":
    main()
