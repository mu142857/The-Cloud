"""鹿（美术画的像素鹿，森林 NPC）→ 游戏用的精灵表 art/characters/deer/deer.png。

画师给了三张 640×640（放大 10 倍，原生 64×64，背景本来就是透明的）：
  站.png    = 静止站着（和「看.gif」第 0 帧一模一样，用来当对齐基准）
  看.gif    = 4 帧、每帧 200ms：侧面 → 转头看镜头 → 侧面 → 回头往后看
  吃草.gif  = 4 帧、每帧 200ms：从站着慢慢低头到嘴碰地（画布比另外两张往右挪了 7 格，身体和腿完全一样）
步骤和 tools/snake_from_gif.py 一样：
  1. 找放大倍数（从大往小试 640 的约数，每个 s×s 格子都纯色才算），按每格中心像素缩回原生尺寸。
  2. 背景变透明：自带透明就用；没有的话四个角最多的颜色（白底）当背景。alpha 只留 0 / 255。
  3. 不清杂点：这套图很干净，唯一一块「不连着的小碎块」是看.gif 第 1 帧（正脸）右边鹿角最上面那截 2 格的角尖，
     画师画的时候和角身断开了一格 —— 是画的东西不是杂点，snake 那套 clean() 会把它删掉，所以这里不调。
     只打印一下哪些帧有不连着的碎块，方便画师改。纯黑 #000 换成 DEEP（这套图里其实没有纯黑）。
  4. 对齐：每段的第 0 帧（= 站着）和基准帧逐格比，找让它们完全重合的平移 (dx, dy)，整段都按它挪 —— 鹿不会原地左右跳。
  5. 一模一样的帧只留一张（看.gif 第 0 帧、吃草.gif 第 0 帧都 = 站着）。
  6. 所有帧同一块裁剪（并集 + 四周 PAD 格透明；chen_light.gdshader 往外采 2 像素），一行横排写 deer.png。
  7. 打印：放大倍数、原生尺寸、帧数和时长、精灵表里每帧是谁、脚底那一行、四条腿的中线 → 对照 scripts/npc_deer.gd 顶部。

用法（工程根目录下）：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/deer_from_gif.py [站.png 看.gif 吃草.gif]
不给就用 SRC 里的路径（作者对话里贴的图存在临时目录，可能已经没了：画师改了图以后把三个文件按这个顺序传进来）。
帧尺寸 / FOOT / 帧号变了要改 npc_deer.gd。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from snake_from_gif import find_scale, to_alpha, pieces, unblack   # noqa: E402  同一套处理，别抄两份

ROOT = Path(__file__).resolve().parent.parent
_IMG = Path("/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/"
            "3cc950fc-c42d-4eb3-98c8-e1124f0c96de/images")
SRC = [_IMG / "8.png", _IMG / "7.gif", _IMG / "9.gif"]      # 站、看、吃草
NAMES = ["stand", "look", "graze"]
OUT = ROOT / "art/characters/deer/deer.png"

PAD = 2
LEG_ROWS = 6           # 量腿中线用脚底往上几行（只有四条腿，不受头和尾巴影响）
SHIFT = 12             # 对齐时最多试挪多少格


def load(src: Path):
    im = Image.open(src)
    frames, ms = [], []
    for f in ImageSequence.Iterator(im):
        frames.append(np.array(f.convert("RGBA")))
        ms.append(int(f.info.get("duration", im.info.get("duration", 0)) or 0))
    return frames, ms


def native(src: Path):
    big, ms = load(src)
    s = find_scale(big)
    out = []
    for i, b in enumerate(big):
        f = to_alpha(b[s // 2::s, s // 2::s])
        nb = unblack(f)
        ps = sorted(pieces(f[..., 3] > 0), key=len)[:-1]
        if ps or nb:
            print(f"  {src.name} 帧 {i}：不连着的碎块 {[(len(p), (int(p[0][1]), int(p[0][0]))) for p in ps]}"
                  f"（格数, (x, y)，保留），换掉 {nb} 个纯黑像素")
        out.append(f)
    print(f"{src.name}：{big[0].shape[1]}×{big[0].shape[0]}，放大 {s} 倍 → 原生 {out[0].shape[1]}×{out[0].shape[0]}，"
          f"{len(out)} 帧，ms {ms}")
    return out, ms, s


def shift(f, dx, dy, m):
    """平移 (dx, dy) 后放到四周各加 m 格的大画布上"""
    h, w = f.shape[:2]
    c = np.zeros((h + 2 * m, w + 2 * m, 4), np.uint8)
    c[m + dy:m + dy + h, m + dx:m + dx + w] = f
    return c


def best_shift(f, ref):
    best = None
    for dy in range(-SHIFT, SHIFT + 1):
        for dx in range(-SHIFT, SHIFT + 1):
            d = int((shift(f, dx, dy, SHIFT) != shift(ref, 0, 0, SHIFT)).any(-1).sum())
            if best is None or d < best[0]:
                best = (d, dx, dy)
    return best


def main():
    args = [Path(a) for a in sys.argv[1:] if not a.startswith("--")]
    srcs = args if args else SRC
    seqs = [native(p) for p in srcs]
    ref = seqs[0][0][0]
    M = SHIFT
    sheet, index = [], {}          # sheet = 去重后的帧；index[(段, 段内帧号)] = 精灵表帧号
    for name, (frames, ms, s) in zip(NAMES, seqs):
        d, dx, dy = best_shift(frames[0], ref)
        print(f"  {name}：整段平移 ({dx:+d}, {dy:+d}) 格和基准对齐（剩 {d} 格不一样）" if (dx or dy) else
              f"  {name}：不用挪（第 0 帧和基准差 {d} 格）")
        for i, f in enumerate(frames):
            g = shift(f, dx, dy, M)
            for j, h in enumerate(sheet):
                if (h == g).all():
                    index[(name, i)] = j
                    break
            else:
                index[(name, i)] = len(sheet)
                sheet.append(g)
    union = np.any([f[..., 3] > 0 for f in sheet], axis=0)
    ys, xs = np.nonzero(union)
    x0, x1, y0, y1 = xs.min() - PAD, xs.max() + 1 + PAD, ys.min() - PAD, ys.max() + 1 + PAD
    crop = [f[y0:y1, x0:x1] for f in sheet]
    fw, fh = x1 - x0, y1 - y0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.concatenate(crop, axis=1)).save(OUT)
    print(f"→ {OUT.relative_to(ROOT)}：{len(crop)} 帧横排，每帧 {fw}×{fh}")
    for name, (frames, ms, s) in zip(NAMES, seqs):
        print(f"  {name}：精灵表帧 {[index[(name, i)] for i in range(len(frames))]}，ms {ms}")

    a0 = crop[0][..., 3] > 0
    rows = np.nonzero(a0.any(1))[0]
    foot_y = int(rows.max())
    for i, c in enumerate(crop):
        r = np.nonzero((c[..., 3] > 0).any(1))[0]
        if int(r.max()) != foot_y:
            print(f"  注意：帧 {i} 最下面一行是 {int(r.max())}（站着是 {foot_y}）")
    leg = a0[foot_y - LEG_ROWS + 1:foot_y + 1].any(0)
    lx = np.nonzero(leg)[0]
    foot_x = int(round((lx.min() + lx.max()) / 2.0))
    print(f"脚底 y = {foot_y}；四条腿 x {lx.min()}..{lx.max()}，中线 x = {foot_x}")
    print(f"  →  npc_deer.gd：FRAME_SIZE = Vector2i({fw}, {fh})，FOOT = Vector2i({foot_x}, {foot_y})")
    lum = [(0.3 * c[..., 0] + 0.59 * c[..., 1] + 0.11 * c[..., 2])[c[..., 3] > 0].max() / 255.0 for c in crop]
    print(f"最亮像素 L = {max(lum):.2f}（游戏里乘 npc_deer.gd 的 TINT 压暗）")


if __name__ == "__main__":
    main()
