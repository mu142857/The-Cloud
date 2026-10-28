"""主角「晨」的 1 倍精灵：从美术给的 ~/Desktop/character.gif 生成跑步、待机、正面待机。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/chen_sprites.py [--preview 目录]

原 gif 只读：480×480、4 帧，10 倍放大的 48×48 像素画（to_1x 检测 k=10、offset 0）。
  第 0 帧：正面站姿；第 1~3 帧：侧面朝右的走 / 跑（1 = 深色远腿着地、浅色近腿抬在后面；
  2 = 两腿分开，近腿在前；3 = 近腿着地、远腿抬在后面）。

输出 art/characters/chen/：
  chen.png + chen.json   所有帧一张横排精灵表（Aseprite json-array，frameTags 分动画，每帧时长在里面）
  跑完会打印 scripts/chen.gd 顶部「精灵配置」里 ANIMS 该填的内容（帧号、每帧毫秒、步长），帧序变了就照着改。
所有帧同一画布 40×42：原图 x 0~39、y 2~43，脚底在最后一行（原图 y=43），画布正中 x=20 是锚点，
水平翻转后位置不变。

跑步（run）：只用 1-2-3 三帧循环，不改美术的像素。为什么不是 1-2-3-2：第 3 帧近腿踩在 x19~23，
回到第 2 帧它又出现在 x23~27（着地的脚往前滑），2→1 远腿也一样；1-2-3 每一步着地的脚都只往后退：
  1→2 远腿着地，脚从 x20 退到 x13：前进 7 像素；2→3 近腿着地，x23→x19/20：前进 4；
  3→1 换脚（近腿抬起往后、远腿落下），没有共同着地的脚，取 4。
Godot 里每换一帧身体跳一步（step），着地的脚在世界里一像素不动。每帧时长和这一步成正比（每像素 25ms），
所以平均速度恒定 40 像素/秒：175 / 100 / 100ms。步长写在 chen.gd 的 ANIMS["run"]["step"]。

待机（idle，侧面朝右）：底图是第 3 帧（近腿着地），把第 1 帧着地的远腿整条挪过来（左移 3 像素）垫在近腿
后面，让两只脚都踩在地上（只搬像素，不上色）。然后按 xiao-oscar 的做法只移动像素：
  呼吸：第 28 行以上（头、肩、头发、前面那条触手）整体抬 1 行，裙摆和腿不动（第 28 行是纯色裙子，
        重复这一行看不出来；26、27 行有金扣，重复了扣子会变大）；
  后面那条大触手单独一层，尖端几行左右摆 1 像素，比呼吸晚半拍；
  头发 / 垂耳的末梢几行往后摆 1 像素，再晚一拍；前面触手的尖端往前探 1 像素；
  眨眼：换部件，眼睛上面几行换成脸的颜色，最下一行换成最深的那档（闭眼线）。
  idle / idle_blink（眨眼）/ idle_eye（头环上的第三只眼慢慢闭一下）三段呼吸完全一样，
  chen.gd 在 idle 循环到头时偶尔换成后两段，所以眨眼不会每一圈都眨。
正面待机（front / front_blink）：第 0 帧呼吸（第 24 行以上抬 1 行）+ 眨眼，给对话、过场用。
脚底在所有帧里完全不动（check_animation 的 foot_jitter = 0）。没有随机。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.anim import write_gif, write_sheet  # noqa: E402
from oscarkit.checks import check_animation  # noqa: E402
from oscarkit.paint import breathe, over, shift_rows  # noqa: E402
from oscarkit.pixel import to_1x  # noqa: E402

SRC = Path("/Users/jiamulin/Desktop/character.gif")
OUT = Path(__file__).resolve().parents[1] / "art" / "characters" / "chen"

X0, X1, Y0, Y1 = 0, 40, 2, 44      # 从 48×48 里裁的画布（脚底 y=43 → 画布最后一行）
MS_PER_UNIT = 25                    # 跑步每前进 1 像素 25ms（= 40 像素/秒）
RUN_STEP = [7, 4, 4]                # 1→2、2→3、3→1 前进的像素（= run 每帧的 duration 单位）
IDLE_UNITS = 6                      # 待机每帧 150ms


def hx(s):
    return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))


# 原图里会用到的几种颜色
EYE_DARK = hx("#14131a")     # 瞳孔 / 最深
EYE_BLUE = hx("#85a4e0")
EYE_GRAY = hx("#474d5d")
EYE_HI = hx("#baf3ff")
EYE = {EYE_DARK, EYE_BLUE, EYE_GRAY, EYE_HI}
SKIN = hx("#b2a195")         # 脸
GOLD = hx("#e0cb88")         # 头环
HAIR = {hx("#c7bdb8"), hx("#868080")}
TENT = {hx("#573450"), hx("#7e4772"), hx("#9c5d86"), hx("#c5769c"), EYE_GRAY, hx("#4b6592")}


def load_frames():
    out = []
    for f in ImageSequence.Iterator(Image.open(SRC)):
        a, info = to_1x(np.array(f.convert("RGBA")))
        assert info["k"] == 10 and info["exact"], info
        assert a.shape == (48, 48, 4)
        assert set(np.unique(a[..., 3])) <= {0, 255}
        out.append(a)
    assert len(out) == 4
    return out


def crop(a):
    return a[Y0:Y1, X0:X1].copy()


def rgb(a, x, y):
    return tuple(int(v) for v in a[y, x, :3]) if a[y, x, 3] else None


# ---------------------------------------------------------------- 站姿底图
def stand_pose(f1, f3):
    """第 3 帧（近腿着地）+ 第 1 帧着地的远腿，左移 3 像素垫在近腿后面。坐标是 48×48 原图坐标。"""
    base = f3.copy()
    # 去掉第 3 帧抬在后面的远腿小腿（y38~40、x16~18 那几块米色）
    far = {hx("#998976"), hx("#8e6a62")}
    for y in range(38, 41):
        for x in range(14, 19):
            if rgb(base, x, y) in far:
                base[y, x] = 0
    # 第 1 帧的远腿：y38~43、x19~24 的米色像素
    leg = np.zeros_like(f1)
    for y in range(38, 44):
        for x in range(17, 26):
            if rgb(f1, x, y) in far:
                leg[y, x] = f1[y, x]
    leg = np.roll(leg, -3, axis=1)
    return over(leg, base)          # 近腿盖在远腿上面


# ---------------------------------------------------------------- 部件
def split(a, mask):
    """把 mask 里的像素拆成单独一层，返回 (剩下的, 拆出来的)。"""
    part = np.zeros_like(a)
    part[mask] = a[mask]
    rest = a.copy()
    rest[mask] = 0
    return rest, part


def color_mask(a, colors, x0, x1, y0, y1):
    m = np.zeros(a.shape[:2], bool)
    for y in range(y0, y1):
        for x in range(x0, x1):
            if rgb(a, x, y) in colors:
                m[y, x] = True
    return m


def blink(a, box, level, lid, line):
    """眨眼（换部件）：box 里属于眼睛的像素，level=1 半闭（最上一行换成眼皮），2 全闭（只剩最下一行闭眼线）。"""
    if level == 0:
        return a
    x0, x1, y0, y1 = box
    out = a.copy()
    rows = [y for y in range(y0, y1) if any(rgb(a, x, y) in EYE for x in range(x0, x1))]
    for y in rows:
        for x in range(x0, x1):
            if rgb(a, x, y) not in EYE:
                continue
            if y == rows[-1]:
                if level == 2:
                    out[y, x, :3] = line
            elif level == 2 or y == rows[0]:
                out[y, x, :3] = lid
    return out


def move_part(a, mask, dx, fill=True):
    """mask 里的像素横移 dx（只搬像素）。fill=True 时空出来的格用身体那侧（和移动方向相反）
    最近的非部件像素补上；fill=False 时空出来就是透明。"""
    if dx == 0:
        return a
    out = a.copy()
    part = np.zeros_like(a)
    part[mask] = a[mask]
    out[mask] = 0
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):
        if not fill:
            continue
        k = x - dx
        while 0 <= k < a.shape[1] and mask[y, k]:
            k -= dx
        if 0 <= k < a.shape[1]:
            out[y, x] = a[y, k]
    moved = shift_rows(part, [dx] * a.shape[0])
    return over(out, moved)


def lift(a, rise, cut):
    """呼吸：cut 行以上整体抬 rise 行（oscarkit.paint.breathe，按 cut 行换算成 at）。"""
    ys = np.nonzero((a[..., 3] > 0).any(1))[0]
    y0, y1 = ys.min(), ys.max()
    return breathe(a, rise, at=(cut - y0 + 0.5) / (y1 - y0))


# ---------------------------------------------------------------- 动画
# 每帧：呼吸抬几行、后触手尖端横移、头发末梢横移、前触手尖端横移
IDLE_KEYS = [
    # rise tent hair arm
    (0, 0, 0, 0),
    (0, 0, 0, 0),
    (1, 0, 0, 0),
    (1, -1, 0, 1),
    (1, -1, -1, 1),
    (1, -1, -1, 0),
    (0, 0, -1, 0),
    (0, 0, 0, 0),
]
BLINK = [0, 0, 0, 1, 2, 1, 0, 0]          # 两只眼睛
EYE3 = [0, 0, 1, 2, 2, 2, 1, 0]           # 头环上的第三只眼


def side_idle(stand, eyes=None, eye3=None):
    """stand：48×48 站姿。返回 8 帧（48×48）。"""
    # 后面那条大触手（臀部往左下绕一圈、尖端翘在左上）拆成单独一层
    body0, tent0 = split(stand, color_mask(stand, TENT, 0, 17, 18, 37))
    hair = color_mask(body0, HAIR, 13, 22, 23, 26)  # 头发 / 垂耳最下面三行
    arm = color_mask(body0, TENT, 26, 31, 21, 23)   # 前面那条触手垂下来的尖
    frames = []
    for i, (rise, tdx, hdx, adx) in enumerate(IDLE_KEYS):
        b = body0
        if eyes:
            b = blink(b, (17, 21, 9, 13), eyes[i], SKIN, EYE_DARK)
            b = blink(b, (22, 25, 9, 13), eyes[i], SKIN, EYE_DARK)
        if eye3:
            b = blink(b, (20, 25, 6, 9), eye3[i], GOLD, EYE_GRAY)
        b = move_part(b, hair, hdx)                 # 头发末梢往后摆，空出来的格由裙子补
        b = move_part(b, arm, adx, fill=False)      # 前面那条触手的尖往前探
        b = lift(b, rise, cut=28)
        t = tent0
        if tdx:
            offs = [tdx if 18 <= y <= 26 else 0 for y in range(t.shape[0])]   # 卷起来的那一圈
            t = shift_rows(t, offs)                 # 触手尖端那几行横移，根部不动
        frames.append(over(t, b))                   # 触手在身体后面
    return frames


FRONT_KEYS = [0, 0, 1, 1, 1, 0]
FRONT_BLINK = [0, 0, 0, 1, 2, 0]


def front_idle(f0, eyes=None):
    frames = []
    for i, rise in enumerate(FRONT_KEYS):
        b = f0
        if eyes:
            b = blink(b, (15, 20, 11, 15), eyes[i], SKIN, EYE_DARK)
            b = blink(b, (21, 25, 11, 15), eyes[i], SKIN, EYE_DARK)
        frames.append(lift(b, rise, cut=24))   # 第 24 行没有金扣
    return frames


def foot_x(a, colors, row=43):
    xs = [x for x in range(a.shape[1]) if rgb(a, x, row) in colors]
    return (min(xs), max(xs)) if xs else None


# ---------------------------------------------------------------- 输出
def main(preview=None):
    f0, f1, f2, f3 = load_frames()

    # 跑步：检查每一步着地的脚确实只往后退了 RUN_STEP 像素
    near, far = {SKIN, hx("#b48e80")}, {hx("#998976"), hx("#8e6a62")}
    assert foot_x(f1, far)[0] - foot_x(f2, far)[0] == RUN_STEP[0], (foot_x(f1, far), foot_x(f2, far))
    assert foot_x(f2, near)[1] - foot_x(f3, near)[1] == RUN_STEP[1], (foot_x(f2, near), foot_x(f3, near))
    run = [crop(f) for f in (f1, f2, f3)]

    stand = stand_pose(f1, f3)
    idle = [crop(f) for f in side_idle(stand)]
    idle_blink = [crop(f) for f in side_idle(stand, eyes=BLINK)]
    idle_eye = [crop(f) for f in side_idle(stand, eye3=EYE3)]
    front = [crop(f) for f in front_idle(f0)]
    front_blink = [crop(f) for f in front_idle(f0, eyes=FRONT_BLINK)]

    anims = [("run", run, RUN_STEP), ("idle", idle, None), ("idle_blink", idle_blink, None),
             ("idle_eye", idle_eye, None), ("front", front, None), ("front_blink", front_blink, None)]
    frames, durs_ms, tags, cfg = [], [], [], []
    for name, fr, units in anims:
        units = units or [IDLE_UNITS] * len(fr)
        tags.append({"name": name, "from": len(frames), "to": len(frames) + len(fr) - 1, "direction": "forward"})
        ms = [u * MS_PER_UNIT for u in units]
        step = f', "step": {RUN_STEP}' if name == 'run' else ''
        ms_s = str(ms) if len(set(ms)) > 1 else str(ms[0])
        cfg.append(f'\t"{name}": {{"frames": {list(range(len(frames), len(frames) + len(fr)))}, "ms": {ms_s}{step}}},')
        frames += fr
        durs_ms += [u * MS_PER_UNIT for u in units]
        # 检查：画布、脚底不跳、调色板一致、alpha 只有 0/255
        rep = check_animation(fr, "move" if name == "run" else "idle", [u * MS_PER_UNIT for u in units])
        bad = [r for r in rep if r["level"] != "OK" and r["rule"] != "durations"]
        alpha = set(np.unique(np.stack(fr)[..., 3]))
        print(f"{name:12s} {len(fr)} 帧 {[u * MS_PER_UNIT for u in units]}ms  alpha={sorted(alpha)}  "
              + ("OK" if not bad else str(bad)))
        assert alpha <= {0, 255}

    OUT.mkdir(parents=True, exist_ok=True)
    write_sheet(frames, OUT / "chen.png", tags=tags, durations=durs_ms)
    h, w = frames[0].shape[:2]
    print(f"写出 {OUT}/chen.png（{len(frames)} 帧，每帧 {w}×{h}）、chen.json")
    print(f"chen.gd 精灵配置：FRAME_SIZE = Vector2i({w}, {h})，FOOT = Vector2i({w // 2}, {43 - Y0})，ANIMS =")
    print("{\n" + "\n".join(cfg) + "\n}")

    if preview:
        p = Path(preview)
        p.mkdir(parents=True, exist_ok=True)
        bg = (28, 52, 48)        # 深青绿
        write_gif(run * 4, p / "chen_run_8x.gif", scale=8, durations=[u * MS_PER_UNIT for u in RUN_STEP] * 4, bg=bg)
        seq = idle + idle + idle_blink + idle + idle_eye
        write_gif(seq, p / "chen_idle_8x.gif", scale=8, durations=[IDLE_UNITS * MS_PER_UNIT] * len(seq), bg=bg)
        seq = front + front_blink
        write_gif(seq, p / "chen_front_8x.gif", scale=8, durations=[IDLE_UNITS * MS_PER_UNIT] * len(seq), bg=bg)
        # 跑步在地上：每帧按步长往前挪（看脚有没有打滑）+ 逐帧条带
        W = 150
        strip_frames, x = [], 0
        for k in range(10):
            i = k % 3
            c = np.zeros((h + 2, W, 4), np.uint8)
            c[h:, :] = (60, 80, 60, 255)
            c[:h, x:x + w] = np.where(run[i][..., 3:] > 0, run[i], c[:h, x:x + w])
            strip_frames.append(c)
            x += RUN_STEP[i]
        write_gif(strip_frames, p / "chen_run_ground_8x.gif", scale=8,
                  durations=[RUN_STEP[k % 3] * MS_PER_UNIT for k in range(10)], bg=bg)
        allf = run + idle_blink + idle_eye + front_blink
        strip = np.zeros((h, w * len(allf), 4), np.uint8)
        for i, f in enumerate(allf):
            strip[:, i * w:(i + 1) * w] = f
        im = Image.new("RGBA", (strip.shape[1], h), bg + (255,))
        im.alpha_composite(Image.fromarray(strip, "RGBA"))
        im.convert("RGB").resize((strip.shape[1] * 6, h * 6), Image.NEAREST).save(p / "chen_strip_6x.png")
        print(f"预览写到 {p}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="放大预览（GIF + 条带）存到这个目录")
    main(ap.parse_args().preview)
