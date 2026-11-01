"""以物易物的两个 NPC：美术组的大嘴鸟（森林）、料理鼠妈（河流篇高处市集），原样导入 + 鼠妈小摊。

原样导入（和 niff_from_gif.py / ray_courier_from_gif.py 一样）：找放大倍数（每 s×s 一格纯色）→ 按每格中心像素缩回 →
透明 → alpha 0，其余 255 → 所有帧同一块裁剪（不透明像素并集，四周留 PAD 格）→ 横排写 png → 自检：缩回的图放大 s 倍和原图逐像素一样。
不清杂点、不换色、不改帧长（鼠妈 200ms 一帧，6 帧；大嘴鸟 1 帧，起伏由 npc_generic.gd 的 bob_top 用代码做，不改图）。

  大嘴鸟 /Users/jiamulin/Desktop/大嘴鸟.png  640×640 = 32×32 放大 20 倍（自带一截树桩）→ art/characters/toucan/toucan.png
  料理鼠妈 /Users/jiamulin/Desktop/料理鼠妈.gif 480×480 = 48×48 放大 10 倍，6 帧 → art/characters/rat_chef/rat_chef.png

--stall：画鼠妈的小摊（灶、锅、小招牌）→ art/river_city/market/market_rat_stall.png（市集的 objects 里一件，鼠妈站在摊后面）。

用法（工程根目录下）：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/barter_npcs_art.py [--stall]
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
CH = ROOT / "art/characters"
SRC = {"toucan": Path("/Users/jiamulin/Desktop/大嘴鸟.png"), "rat_chef": Path("/Users/jiamulin/Desktop/料理鼠妈.gif")}
PAD = 1


def restore(who: str):
    src = SRC[who]
    big, ms = load(src)
    s = find_scale(big)
    assert s > 1, f"{src.name} 找不到整数放大倍数"
    frames = [to_alpha(b[s // 2::s, s // 2::s]) for b in big]
    h, w = frames[0].shape[:2]
    union = np.any([f[..., 3] > 0 for f in frames], axis=0)
    ys, xs = np.nonzero(union)
    x0, x1, y0, y1 = xs.min() - PAD, xs.max() + 1 + PAD, ys.min() - PAD, ys.max() + 1 + PAD
    padded = [np.pad(f, ((PAD, PAD), (PAD, PAD), (0, 0))) for f in frames]
    crop = [p[y0 + PAD:y1 + PAD, x0 + PAD:x1 + PAD] for p in padded]
    fw, fh = int(x1 - x0), int(y1 - y0)
    d = CH / who
    (d / "src").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, d / "src" / src.name)
    Image.fromarray(np.concatenate(crop, axis=1)).save(d / f"{who}.png")
    back = np.array(Image.open(d / f"{who}.png").convert("RGBA"))
    for i, b in enumerate(big):
        canvas = np.zeros((h + 2 * PAD, w + 2 * PAD, 4), np.uint8)
        canvas[y0 + PAD:y1 + PAD, x0 + PAD:x1 + PAD] = back[:, i * fw:(i + 1) * fw]
        up = np.repeat(np.repeat(canvas[PAD:-PAD, PAD:-PAD], s, 0), s, 1)
        ref = to_alpha(b)
        assert (up[..., 3] == ref[..., 3]).all() and (up[ref[..., 3] > 0] == ref[ref[..., 3] > 0]).all(), f"{who} 帧 {i} 放大回去和原图不一样"
    print(f"{src.name}：{big[0].shape[1]}×{big[0].shape[0]}，放大 {s} 倍 → 原生 {w}×{h}，{len(big)} 帧 {ms}ms → {who}.png 每帧 {fw}×{fh}；自检逐像素一样")
    return crop, fw, fh, ms


def main():
    tc, tw, th, _ = restore("toucan")
    op = tc[0][..., 3] > 0
    bottom = int(np.nonzero(op.any(1))[0].max())
    # 树桩切面那一行（浅色 n = 192,176,141）：上面是鸟，下面是树桩。bob_top = 鸟的脚那一行，这行以上整块（头、身子）轻轻往下点 1 像素，
    # 脚和树桩不动（往下压不会露缝）
    stump_top = int(next(y for y in range(th) if ((tc[0][y, :, :3] == (192, 176, 141)).all(-1) & op[y]).any()))
    xs = np.nonzero(op[bottom])[0]
    (CH / "toucan/toucan.json").write_text(json.dumps({
        "_comment": "美术组的大嘴鸟（tools/barter_npcs_art.py 按格取样还原，不改图）。住在森林林间空地尽头（story_forest.json 的 residents），"
                    "以物易物（data/barter.json）。图里朝左、蹲在自带的树桩上：anchor = 树桩底边中间。只有一帧：bob_top = 这一行以上（头和身子）"
                    "平滑地往下点 bob 像素再回来（只动位置、取整到像素，脚和树桩不动，不改图）。tint false = 美术组的图原色。shadow_w = 影子按树桩宽。",
        "frame": [tw, th], "sheet": "toucan.png", "anchor": [int((xs.min() + xs.max()) // 2), bottom], "faces": "left", "ms": 100,
        "tint": False, "bob": 1, "bob_s": 3.4, "bob_top": stump_top - 1, "head": th - 4, "speed": 0, "shadow_w": int(xs.max() - xs.min() + 1),
        "color": "#ffb72a", "anims": {"idle": {"frames": [0], "loop": True}}, "alias": {"talk": "idle", "walk": "idle"},
    }, ensure_ascii=False, indent=1))
    rc, rw, rh, rms = restore("rat_chef")
    op = np.any([f[..., 3] > 0 for f in rc], axis=0)
    bottom = int(np.nonzero(op.any(1))[0].max())
    xs = np.nonzero(op[bottom])[0]
    (CH / "rat_chef/rat_chef.json").write_text(json.dumps({
        "_comment": "美术组的料理鼠妈（tools/barter_npcs_art.py 按格取样还原，不改图，6 帧 200ms 原样）。在高处市集自己的小摊后面"
                    "（market/room.json 的 residents + 物件 market_rat_stall），以物易物（data/barter.json）。正面站着、举着汤勺挥手，"
                    "不翻转（residents 的 face 写 1）。anchor = 两只脚中间的底边。tint false = 美术组的图原色。pass = 不占路（晨从摊前走过去，story_runner._is_body）。",
        "frame": [rw, rh], "sheet": "rat_chef.png", "anchor": [int((xs.min() + xs.max()) // 2), bottom], "faces": "right", "ms": int(rms[0]),
        "tint": False, "head": rh - 2, "speed": 0, "pass": True, "color": "#c8a07a",
        "anims": {"idle": {"frames": list(range(len(rc))), "loop": True}}, "alias": {"talk": "idle", "walk": "idle"},
    }, ensure_ascii=False, indent=1))
    print("toucan.json / rat_chef.json 写好")
    if "--stall" in sys.argv:
        stall()


# ======================================================================= 鼠妈的小摊（市集，market_rat_stall）
STALL_W, STALL_H, STALL_FRAMES = 84, 48, 3
STALL_X, STALL_Y = 1051, 200 - STALL_H          # 底行 47 踩在桥面（地面 200）上；鼠妈站在中间 x = STALL_X + 44
PAL = {
    "S0": "#091121", "S1": "#102031", "S2": "#173141", "S3": "#1f4250",          # 石头：市集主图里的四档（moonlit 左上）
    "W0": "#24160f", "W1": "#3a281c", "W2": "#523b29",                          # 木头
    "C0": "#2c1618", "C1": "#3f1f1f", "C2": "#552c27",                          # 布篷：暗的旧红
    "I0": "#0d1219", "I1": "#1a222c", "I2": "#2d3640",                          # 铁锅
    "SO": "#5e4024",                                                            # 锅里的汤
    "E0": "#3a2622", "E1": "#5a3020",                                           # 灶口边上被火照暖的石头
    "F0": "#7a3218", "F1": "#c8602a", "F2": "#f0a04a", "F3": "#ffd88a",         # 火
    "T1": "#41606a", "T2": "#6a8890",                                           # 热气
    "B0": "#6a5a48", "B1": "#a89070", "B2": "#c8b08a",                          # 碗
}


def _hex(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def stall():
    """market_rat_stall：3 帧 84×48（火苗、热气轻轻动，其余不动）。常见坑：不画虚线、不留角碰角的细线、没有孤立单像素、没有悬空的东西。"""
    P = {k: _hex(v) for k, v in PAL.items()}
    frames = []
    for f in range(STALL_FRAMES):
        a = np.zeros((STALL_H, STALL_W, 4), np.uint8)

        def put(x, y, c):
            if 0 <= x < STALL_W and 0 <= y < STALL_H:
                a[y, x] = P[c]

        def hline(x0, x1, y, c):
            for x in range(x0, x1 + 1):
                put(x, y, c)

        # 杆：两根 2 像素宽的木杆，左边一列朝月光亮一档；脚下一块压杆的石头（宽 1 像素，不成台阶）
        for px in (3, 79):
            for y in range(10, 46):
                put(px, y, "W1")
                put(px + 1, y, "W0")
            hline(px - 1, px + 2, 46, "S2")
            hline(px - 1, px + 2, 47, "S1")
        # 布篷：顶边直，下摆一条缓的波浪（周期 13、起伏 1 像素，连续的边）；左上亮、往下暗；三道斜褶
        bottom = [11 + int(round(1.0 * np.sin(x * 2 * np.pi / 13 + 0.6))) for x in range(STALL_W)]
        for x in range(1, STALL_W - 1):
            for y in range(4, bottom[x] + 1):
                c = "C2" if y <= 5 else ("C0" if y >= bottom[x] - 1 else "C1")
                put(x, y, c)
        for fx in (21, 44, 64):                       # 褶：一条暗楔（2 宽），紧贴左边一条亮棱
            for y in range(6, 11):
                put(fx + (y - 6) // 3, y, "C0")
                put(fx + 1 + (y - 6) // 3, y, "C0")
                put(fx - 1 + (y - 6) // 3, y, "C2")
        hline(2, STALL_W - 3, 3, "C1")                # 顶上压一道
        # 灶：x 7..31，y 29..47，上两角各切一格；顶面亮、左边亮、右边暗
        for y in range(29, 48):
            x0, x1 = (8, 30) if y == 29 else (7, 31)
            for x in range(x0, x1 + 1):
                c = "S1"
                if y == 29:
                    c = "S3"
                elif y == 30:
                    c = "S2"
                elif x == x0:
                    c = "S2"
                elif x == x1:
                    c = "S0"
                put(x, y, c)
        hline(9, 14, 33, "S0")                        # 两道石缝（横的，不规则）
        hline(25, 29, 41, "S0")
        # 灶口：拱形（半宽 3 → 5 → 6），外圈被火照暖的石头，里面火
        half = {35: 2, 36: 3, 37: 5}               # 35 = 拱顶上面那圈暖边的宽（不是火）
        for y in range(36, 48):
            hw = half.get(y, 6)
            for x in range(19 - hw, 19 + hw + 1):
                put(x, y, "F0")
            up = half.get(y - 1, 6)
            for x in range(19 - hw - 1, 19 - up):    # 暖边连续：这一行的外沿一直接到上一行外沿（拱肩那几行横着补齐）
                put(x, y, "E1")
            for x in range(19 + up + 1, 19 + hw + 2):
                put(x, y, "E0")
            put(19 - hw - 1, y, "E1")
            put(19 + hw + 1, y, "E0")
        hline(16, 22, 35, "E1")
        # 火苗：三条舌头，每帧高低不同（2 宽，连在底下的炭火上）
        tongues = [(15, [41, 39, 40]), (18, [38, 40, 37]), (21, [40, 38, 39])]
        for tx, tops in tongues:
            top = tops[f]
            for y in range(top, 46):
                put(tx, y, "F1")
                put(tx + 1, y, "F1")
            for y in range(top + 2, 46):
                put(tx, y, "F2")
        hline(14, 24, 45, "F2")
        hline(16, 21, 46, "F3")
        hline(17, 20, 45, "F3")
        hline(13, 25, 47, "F1")
        # 锅：坐在灶顶（y 20..28）；口沿亮、里面一层汤；两只耳；锅底朝火的一圈暖色
        rows = {21: (12, 26), 22: (11, 27), 23: (10, 28), 24: (10, 28), 25: (10, 28), 26: (10, 28), 27: (11, 27), 28: (13, 25)}
        for y, (x0, x1) in rows.items():
            for x in range(x0, x1 + 1):
                c = "I1"
                if y == 21:
                    c = "I2"
                elif y == 22:
                    c = "SO" if x0 + 2 <= x <= x1 - 2 else "I2"
                elif x <= x0 + 1:
                    c = "I2"
                elif x >= x1 - 1 or y == 28:
                    c = "I0"
                put(x, y, c)
        hline(14, 24, 28, "E0")
        for hx in (9, 29):
            put(hx, 23, "I0")
            put(hx, 24, "I0")
        # 热气：两缕，2 宽的正弦（周期 6 行、每帧往上走 2 行，3 帧接成一圈）；相邻两行最多错 1 格，总有一格边相邻；
        # 顶上收成 1 宽（落在下一行那两格里面）
        for bx, top, ph in ((15, 13, 0), (21, 15, 3)):
            cx = {y: bx + int(round(0.9 * np.sin((y + 2 * f + ph) * 2 * np.pi / 6))) for y in range(top, 21)}
            for y in range(top + 1, 21):
                put(cx[y], y, "T2" if y < top + 4 else "T1")
                put(cx[y] + 1, y, "T1")
            put(min(max(cx[top], cx[top + 1]), cx[top + 1] + 1), top, "T1")
        # 小木柜：x 56..76；台面两行，柜身一道竖缝；右边暗
        for y in range(37, 48):
            for x in range(56, 77):
                c = "W1"
                if y == 37:
                    c = "W2"
                elif y == 38 or x == 76:
                    c = "W0"
                elif x == 56:
                    c = "W2"
                put(x, y, c)
        for y in range(40, 47):
            put(66, y, "W0")
        # 一摞碗（三只，从下往上一只比一只小一点点）
        for y, (x0, x1), c in ((36, (61, 69), "B0"), (35, (60, 70), "B1"), (34, (61, 69), "B0"), (33, (60, 70), "B2"),
                               (32, (61, 69), "B1"), (31, (60, 70), "B2")):
            hline(x0, x1, y, c)
        # 招牌：两根绳从篷下摆垂下来接住木牌；牌上画一只冒热气的碗
        for rx in (59, 73):
            for y in range(bottom[rx] + 1, 16):
                put(rx, y, "W0")
        for y in range(16, 26):
            for x in range(58, 75):
                c = "W1"
                if y == 16:
                    c = "W2"
                elif y == 25 or x == 74:
                    c = "W0"
                put(x, y, c)
        hline(61, 71, 21, "B2")
        hline(62, 70, 22, "B1")
        hline(64, 68, 23, "B1")
        for (x, y) in ((64, 18), (64, 19), (65, 19), (65, 20), (68, 18), (68, 19), (67, 19), (67, 20)):
            put(x, y, "B1")
        frames.append(a)
    sheet = np.concatenate(frames, axis=1)
    out = ROOT / "art/river_city/market/market_rat_stall.png"
    Image.fromarray(sheet).save(out)
    print(f"→ {out.relative_to(ROOT)}：{STALL_FRAMES} 帧 {STALL_W}×{STALL_H}，放在市集 x {STALL_X}、y {STALL_Y}")


if __name__ == "__main__":
    main()
