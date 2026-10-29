"""蛇女（dotpict 画的待机动画 GIF）→ 游戏用的精灵表 art/characters/snake/snake.png。

原图是 dotpict 导出的 480×480 GIF（8 帧，每帧 200ms），整数倍放大过。做这几件事：
  1. 找放大倍数：从大往小试 480 的约数 s，每一帧每个 s×s 格子都是纯色才算数；按每格中心像素缩回原始尺寸。
  2. 背景变透明：GIF 自带透明色就用它；没有的话取四个角最多的那个颜色当背景。alpha 只留 0 / 255。
  3. 清杂点：和身体不连着、小于 MIN_PIECE 像素的碎块去掉（打印去了几个）。
  4. 纯黑 #000 换成 DEEP（项目规矩：不用死黑、不描边）。别的颜色一个都不改。
  5. 所有帧用同一块裁剪（所有帧不透明像素的并集，四周再留 PAD 格透明：chen_light.gdshader 会往外采 2 像素，
     帧和帧之间至少隔 2×PAD 格），一行横排写 snake.png。
  6. 打印：原始尺寸、帧尺寸、每帧最下面一行（脚底）、身体中线、建议的 FOOT —— 对照 scripts/npc_snake.gd 顶部。

用法（工程根目录下）：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/snake_from_gif.py [源文件.gif]
不给源文件就用 SRC（作者微信收到的那个文件）。画师改了图以后重新导出 GIF 再跑一次；帧尺寸 / FOOT 变了要改 npc_snake.gd。
"""
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent.parent
SRC = Path("/Users/jiamulin/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/"
           "wxid_xppvm6tm83zn12_d111/msg/file/2026-10/dotpict_animation_20261028_180642(1).gif")
OUT = ROOT / "art/characters/snake/snake.png"

PAD = 2                # 裁剪框四周留几格透明
MIN_PIECE = 3          # 和身体不连着、小于这么多像素的碎块算杂点
DEEP = (30, 32, 36)    # 纯黑换成的颜色：很暗、带一点冷，不是死黑
NECK_ROWS = (24, 34)   # 量身体中线用的行（原始像素）：脖子到蛇身竖直那一段，左右不受头发和盘起来的尾巴影响


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
        ok = True
        for f in frames:
            c = f[s // 2::s, s // 2::s]
            for dy in range(s):
                for dx in range(s):
                    if not (f[dy::s, dx::s] == c).all():
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            return s
    return 1


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


def to_alpha(f):
    """背景 → 透明，alpha 只留 0 / 255"""
    f = f.copy()
    if (f[..., 3] == 0).any():
        f[f[..., 3] < 128] = 0
        f[f[..., 3] > 0, 3] = 255
        return f
    corners = [tuple(f[y, x]) for y in (0, -1) for x in (0, -1)]
    bg = max(set(corners), key=corners.count)
    f[(f == bg).all(-1)] = 0
    f[f[..., 3] > 0, 3] = 255
    return f


def clean(f):
    f = f.copy()
    ps = pieces(f[..., 3] > 0)
    biggest = max(len(p) for p in ps)
    removed = 0
    for p in ps:
        if len(p) < biggest and len(p) < MIN_PIECE:
            for y, x in p:
                f[y, x] = 0
            removed += len(p)
    return f, removed


def unblack(f):
    black = (f[..., 3] == 255) & (f[..., :3].sum(-1) == 0)
    f[black, :3] = DEEP
    return int(black.sum())


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = Path(args[0]) if args else SRC
    big, ms = load(src)
    s = find_scale(big)
    frames = []
    for i, b in enumerate(big):
        f = to_alpha(b[s // 2::s, s // 2::s])
        f, removed = clean(f)
        nb = unblack(f)
        if removed or nb:
            print(f"帧 {i}：去掉 {removed} 个杂点像素，换掉 {nb} 个纯黑像素")
        frames.append(f)
    h, w = frames[0].shape[:2]
    print(f"{src.name}：{big[0].shape[1]}×{big[0].shape[0]}，放大 {s} 倍 → 原始 {w}×{h}，{len(frames)} 帧，ms {ms}")

    # 统一裁剪框：所有帧的并集 + PAD
    union = np.any([f[..., 3] > 0 for f in frames], axis=0)
    ys, xs = np.nonzero(union)
    x0, x1, y0, y1 = xs.min() - PAD, xs.max() + 1 + PAD, ys.min() - PAD, ys.max() + 1 + PAD
    padded = [np.pad(f, ((PAD, PAD), (PAD, PAD), (0, 0))) for f in frames]
    crop = [p[y0 + PAD:y1 + PAD, x0 + PAD:x1 + PAD] for p in padded]
    fw, fh = x1 - x0, y1 - y0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.concatenate(crop, axis=1)).save(OUT)
    print(f"→ {OUT.relative_to(ROOT)}：{len(crop)} 帧横排，每帧 {fw}×{fh}（原图里的 x {x0}..{x1 - 1}、y {y0}..{y1 - 1}）")

    # 脚底：每帧最下面一行；身体中线：脖子到竖直蛇身那几行左右边的中点
    bottoms, mids = [], []
    for i, c in enumerate(crop):
        a = c[..., 3] > 0
        rows = np.nonzero(a.any(1))[0]
        bottoms.append(int(rows.max()))
        cs = []
        for y in range(NECK_ROWS[0] - y0, NECK_ROWS[1] - y0):
            xx = np.nonzero(a[y])[0]
            if len(xx):
                cs.append((xx.min() + xx.max()) / 2.0)
        mids.append(float(np.mean(cs)))
        top = int(rows.min())
        print(f"  帧 {i}：最上 {top}、最下 {bottoms[-1]}（高 {bottoms[-1] - top + 1}），中线 x≈{mids[-1]:.1f}")
    foot_y = int(np.median(bottoms))
    foot_x = int(round(float(np.median(mids))))
    print(f"脚底（蛇尾盘着着地那一行）y = {foot_y}（大多数帧；尾巴尖甩下来的帧更低 {max(bottoms) - foot_y} 格 = 尾尖伸向镜头）")
    print(f"身体中线 x = {foot_x}  →  npc_snake.gd：FRAME_SIZE = Vector2i({fw}, {fh})，FOOT = Vector2i({foot_x}, {foot_y})")
    lum = [(0.3 * c[..., 0] + 0.59 * c[..., 1] + 0.11 * c[..., 2])[c[..., 3] > 0].max() / 255.0 for c in crop]
    print(f"最亮像素 L = {max(lum):.2f}（游戏里乘 npc_snake.gd 的 TINT 压暗）")


if __name__ == "__main__":
    main()
