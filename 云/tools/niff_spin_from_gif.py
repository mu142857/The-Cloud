"""妮芙「高兴转圈圈」（作者 11-02 画的 4 帧 GIF，100ms 一帧）→ art/characters/niff/niff_spin.png，写进 niff.json 的 anims.spin。
和 niff_from_gif.py 一样原样导入：不改色不改形、按每格中心缩回原生像素、所有帧同一块裁剪。
每帧比平时的鲸壳大（整只转起来），所以 spin 自带 sheet / frame / anchor（npc_generic 支持按动作换图）。
用法：python3 tools/niff_spin_from_gif.py [源.gif]
"""
import json, shutil, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent.parent
SRC = Path("/Users/jiamulin/Desktop/高兴转圈圈.gif")
DIR = ROOT / "art/characters/niff"
PAD = 2

def load(src):
    im = Image.open(src); fr, ms = [], []
    for f in ImageSequence.Iterator(im):
        fr.append(np.array(f.convert("RGBA"))); ms.append(int(f.info.get("duration", 100)))
    return fr, ms

def find_scale(frames):
    h, w = frames[0].shape[:2]
    for s in sorted({d for d in range(1, min(h, w) + 1) if h % d == 0 and w % d == 0}, reverse=True):
        if all((np.repeat(np.repeat(f[s // 2::s, s // 2::s], s, 0), s, 1) == f).all() for f in frames):
            return s
    return 1

def to_alpha(f):
    f = f.copy(); f[f[..., 3] < 128] = 0; f[f[..., 3] > 0, 3] = 255; return f

src = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC
big, ms = load(src); s = find_scale(big)
frames = [to_alpha(b[s // 2::s, s // 2::s]) for b in big]
union = np.any([f[..., 3] > 0 for f in frames], axis=0)
ys, xs = np.nonzero(union)
x0, x1, y0, y1 = xs.min() - PAD, xs.max() + 1 + PAD, ys.min() - PAD, ys.max() + 1 + PAD
padded = [np.pad(f, ((PAD, PAD), (PAD, PAD), (0, 0))) for f in frames]
crop = [p[y0 + PAD:y1 + PAD, x0 + PAD:x1 + PAD] for p in padded]
fw, fh = int(x1 - x0), int(y1 - y0)
(DIR / "src").mkdir(parents=True, exist_ok=True)
shutil.copyfile(src, DIR / "src/happy_spin.gif")
Image.fromarray(np.concatenate(crop, axis=1)).save(DIR / "niff_spin.png")
# 锚点：鲸壳平时的底边中点在 swim 图里是 (35, 41)；转圈时整只在转，用帧的横向中线、底边取 4 帧最下行的中位数
bottoms = [int(np.nonzero((c[..., 3] > 0).any(1))[0].max()) for c in crop]
anchor = [fw // 2, int(np.median(bottoms))]
meta = json.loads((DIR / "niff.json").read_text(encoding="utf-8"))
meta["anims"]["spin"] = {"sheet": "niff_spin.png", "frame": [fw, fh], "anchor": anchor,
    "frames": [0, 1, 2, 3, 0, 1, 2, 3], "ms": ms[0], "loop": False,
    "_note": "作者 11-02 画的「高兴转圈圈」：转两圈（0.8 秒）回待机。高兴的时候用：捞齐了、影像有声音了、送铜铃"}
meta["alias"]["laugh"] = "spin"
(DIR / "niff.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"{src.name}: 放大 {s} 倍 → 每帧 {fw}×{fh}，{len(crop)} 帧，{ms[0]}ms，锚点 {anchor}")
