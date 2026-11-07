"""美术姐画的云层镇居民（结局三的「居民」townsfolk）→ art/characters/townsfolk/townsfolk_art.png + townsfolk.json。

原样导入：不改色、不改形、不重画。做法和 niff_from_gif.py 一样：找放大倍数（dotpict 导出放大 10 倍）→ 按每格中心像素缩回 →
GIF 透明色 → alpha 0，其余 255 → 横排写 png → 自检：缩回的图放大回去和原 GIF 逐像素一样。

原图只有 4 帧走路（0、2 两腿并拢，1、3 两腿分开，2 闭眼），朝右。帧时长按作者 11-07 定的 100ms（GIF 里是 300ms，只作参考）。
- walk = 原图 4 帧；走路速度按步幅配（一步约 8 像素、两帧 200ms → 40 像素 / 秒），脚不打滑。
- idle = 停在帧 0，隔一会儿换一下帧 2（闭眼、尾巴换个弯），脚只差一格；不是新画的，只是用原图的帧。
- talk、sit 等原图没有的动作全部别名到 idle：长椅那段只能站着，要坐下得等美术姐画。

用法（工程根目录下）：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/townsfolk_from_gif.py [源文件.gif]
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
SRC = Path("/Users/jiamulin/Desktop/dotpict_animation_20261107_130914.gif")
DIR = ROOT / "art/characters/townsfolk"
SHEET = "townsfolk_art.png"
IDLE = [0] * 28 + [2] * 2          # 3 秒一圈：最后 200ms 闭眼、尾巴换个弯


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = Path(args[0]) if args else SRC
    if not src.exists():
        src = DIR / "src/townsfolk.gif"
    big, ms = load(src)
    s = find_scale(big)
    frames = [to_alpha(b[s // 2::s, s // 2::s]) for b in big]
    h, w = frames[0].shape[:2]
    print(f"{src.name}：{big[0].shape[1]}×{big[0].shape[0]}，放大 {s} 倍 → 原生 {w}×{h}，{len(frames)} 帧，GIF 里 ms {ms}")
    for i, f in enumerate(frames):
        black = (f[..., 3] == 255) & (f[..., :3].sum(-1) == 0)
        assert not black.any(), f"帧 {i} 有不透明纯黑像素，按规矩不能偷偷换色，请人来看"

    (DIR / "src").mkdir(parents=True, exist_ok=True)
    if src != DIR / "src/townsfolk.gif":
        shutil.copyfile(src, DIR / "src/townsfolk.gif")
    Image.fromarray(np.concatenate(frames, axis=1)).save(DIR / SHEET)

    back = np.array(Image.open(DIR / SHEET).convert("RGBA"))
    for i, b in enumerate(big):
        up = np.repeat(np.repeat(back[:, i * w:(i + 1) * w], s, 0), s, 1)
        ref = to_alpha(b)
        same = (up[..., 3] == ref[..., 3]).all() and (up[ref[..., 3] > 0] == ref[ref[..., 3] > 0]).all()
        assert same, f"帧 {i} 放大回去和原 GIF 不一样"
    print(f"自检：{len(big)} 帧缩回再放大 {s} 倍，和原 GIF 逐像素一样")

    foot = {int(np.nonzero((f[..., 3] > 0).any(1))[0].max()) for f in frames}
    assert len(foot) == 1, f"每帧脚底不在同一行：{foot}"
    foot_y = foot.pop()
    j = {
        "_comment": "tools/townsfolk_from_gif.py 生成。云层镇的居民 = 美术姐 11-07 画的（dotpict，原生 48×48，4 帧走路，朝右），像素一个不改。"
                    "100ms 一帧（作者定，GIF 里是 300ms）。原图只有走路：idle 用帧 0 + 偶尔帧 2（闭眼），"
                    "talk、sit 等都别名到 idle（长椅那段站着）。tint false = 原色。旧的 townsfolk.png 是 cloud_folk_art.py 以前画的，不再用。",
        "frame": [w, h], "sheet": SHEET, "anchor": [24, foot_y], "faces": "right", "ms": 100, "tint": False,
        "head": 46, "speed": 40, "color": "#bb9687",
        "anims": {"idle": {"frames": IDLE, "loop": True}, "walk": {"frames": [0, 1, 2, 3], "loop": True}},
        "alias": {n: "idle" for n in ("talk", "sit", "sit_idle", "point", "wave", "laugh", "nod", "look", "stand", "smile", "give", "show", "guide")},
    }
    (DIR / "townsfolk.json").write_text(json.dumps(j, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"→ {SHEET}：{len(frames)} 帧横排，脚底第 {foot_y} 行")


if __name__ == "__main__":
    main()
