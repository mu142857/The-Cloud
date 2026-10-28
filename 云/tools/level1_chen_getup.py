"""第一关开场：晨被甩出飞船以后「脸朝下趴着 → 撑起上身 → 跪坐 → 半蹲 → 站直」的几帧。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/level1_chen_getup.py [--preview 目录]

只从现有的晨精灵（art/characters/chen/chen.png 的待机第 0 帧，也就是 tools/chen_sprites.py 的站姿）挪 / 重组像素，
不重新上色：把站姿拆成 头、上身、腿、后面的大触手、前面的小触手 五块，每块只做 90° 旋转（像素一一对应，
不会出 mixel）、整格平移、按行 / 按列整格错位（倾斜），再叠回去。

输出 art/characters/chen/chen_getup.png + chen_getup.json：一行横排，每帧 64×42（比站立帧宽，因为趴着更长）。
锚点和站立帧一样：x = 20（站姿正好贴在画布左边 40 列里，所以最后一帧和待机第 0 帧逐像素重合，接得上），y = 41（地面行）。
帧：0 趴着（脸朝下，头朝右）、1 抽一下（头和肩抬 1 像素）、2 撑起上身（抬头、前触手撑地）、3 跪坐、4 半蹲前倾、5 站直（= 待机第 0 帧）。
scripts/chen.gd 顶部「精灵配置」里的 lie / getup 两段用的就是这张表；换新美术时这两段可以删掉，关卡会退回旋转的老办法。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.anim import write_gif, write_sheet  # noqa: E402
from oscarkit.checks import check_animation  # noqa: E402
from oscarkit.paint import over, shift_rows  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CHEN = ROOT / "art" / "characters" / "chen"
SRC_FRAME = 3                 # chen.png 的第 3 帧 = 待机第 0 帧（站姿）
FW, FH = 40, 42               # 站立帧
CW, CH = 64, 42               # 这张表每帧
GROUND = 41                   # 地面行（= 站立帧脚底那行）


def hx(s):
    return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))


TENT = {hx(c) for c in ("#573450", "#7e4772", "#9c5d86", "#c5769c", "#474d5d", "#4b6592")}


def load_stand():
    sheet = np.array(Image.open(CHEN / "chen.png").convert("RGBA"))
    return sheet[:, SRC_FRAME * FW:(SRC_FRAME + 1) * FW].copy()


def mask_of(a, colors=None, x0=0, x1=FW, y0=0, y1=FH):
    m = np.zeros(a.shape[:2], bool)
    sub = a[y0:y1, x0:x1]
    on = sub[..., 3] > 0
    if colors is not None:
        cm = np.zeros(on.shape, bool)
        for c in colors:
            cm |= np.all(sub[..., :3] == np.array(c), -1)
        on &= cm
    m[y0:y1, x0:x1] = on
    return m


def take(a, m):
    p = np.zeros_like(a)
    p[m] = a[m]
    return p


def parts(stand):
    tail_m = mask_of(stand, TENT, 0, 18, 16, 36)          # 后面的大触手（臀部往左下绕一圈）
    arm_m = mask_of(stand, TENT, 25, 32, 13, 24)          # 前面那条小触手
    body = stand.copy()
    body[tail_m | arm_m] = 0
    rows = np.arange(FH)[:, None]
    head = take(body, (body[..., 3] > 0) & (rows <= 13))
    torso = take(body, (body[..., 3] > 0) & (rows >= 14) & (rows <= 31))
    legs = take(body, (body[..., 3] > 0) & (rows >= 32))
    return dict(tail=take(stand, tail_m), arm=take(stand, arm_m), head=head, torso=torso, legs=legs, body=body)


def blank():
    return np.zeros((CH, CW, 4), np.uint8)


def put(dst, src, dx, dy):
    """src 的不透明像素平移 (dx, dy) 叠到 dst 上（超出画布的丢掉）。"""
    ys, xs = np.nonzero(src[..., 3] > 0)
    ok = (ys + dy >= 0) & (ys + dy < dst.shape[0]) & (xs + dx >= 0) & (xs + dx < dst.shape[1])
    out = dst.copy()
    out[ys[ok] + dy, xs[ok] + dx] = src[ys[ok], xs[ok]]
    return out


def under(dst, src, dx, dy):
    """同 put，但只填 dst 透明的地方（画在后面）。"""
    return put(put(np.zeros_like(dst), src, dx, dy), dst, 0, 0)


def cw(a):
    """顺时针 90°：头朝右、身体正面（右边）朝下 = 脸朝下趴着。原 (x, y) → (行 x, 列 H-1-y)。"""
    return np.rot90(a, k=-1).copy()


def ccw(a):
    return np.rot90(a, k=1).copy()


def shear_cols(a, x0, x1, rise):
    """x0..x1 这几列从 0 到 rise 像素线性往上抬（按列整格错位，像把身体斜着撑起来）；x1 往右都抬 rise。"""
    out = np.zeros_like(a)
    for x in range(a.shape[1]):
        k = 0 if x < x0 else 1.0 if x >= x1 else (x - x0) / (x1 - x0)
        d = int(round(rise * k))
        if d:
            out[:-d, x] = a[d:, x]
        else:
            out[:, x] = a[:, x]
    return out


def bottom(a):
    ys = np.nonzero((a[..., 3] > 0).any(1))[0]
    return int(ys.max())


# ---------------------------------------------------------------- 各个姿势
LIE_DX = 10        # 趴着：转过来以后脚在左（列 0）→ 平移到 x=10，膝盖约 x=14、头顶 x=48
LIE_DY = 16        # 身体正面（原 x=25）落到地面行 41


def pose_lie(P, lift=0):
    """脸朝下趴着：身体整块顺时针 90°；后触手跟着转（搭在背上）；前触手压在身子底下看不见。
    lift = 头和肩抬起几像素（抽一下）。"""
    upper = over(P["head"], P["torso"])
    up_rot = cw(upper)
    legs_rot = cw(P["legs"])
    f = blank()
    f = put(f, cw(P["tail"]), LIE_DX, LIE_DY - 1)        # 触手软软地搭在臀部后面
    f = put(f, legs_rot, LIE_DX, LIE_DY)
    if lift:
        # 肩膀往前（原 y < 20 → 转过来列 >= 22）抬 lift 行，胸口那几列抬一半
        up_rot = shear_cols(up_rot, 18, 24, lift)
    f = put(f, up_rot, LIE_DX, LIE_DY)
    return f


def pose_push(P, rise=6):
    """撑起上身：腿和臀还趴着，胸口斜着撑起来（按列整格错位），头立起来往前看，前触手撑在肩膀下面的地上。"""
    legs_rot = cw(P["legs"])
    torso_rot = cw(P["torso"])
    # 转过来以后上身占列 10..27（臀 → 肩），行 13..25。臀部不动，越往肩膀抬得越高
    torso_rot = shear_cols(torso_rot, 11, 28, rise)
    f = blank()
    f = put(f, cw(P["tail"]), LIE_DX, LIE_DY)
    f = put(f, legs_rot, LIE_DX, LIE_DY)
    f = put(f, torso_rot, LIE_DX, LIE_DY)
    # 头：立着（不转），下巴压在肩膀前端上面。站姿里头占 x13..25、y3..13
    f = put(f, P["head"], 14, 15 - (rise - 6))
    # 前触手：顺时针 90° 以后往下垂（原 x25..30 → 行 25..30，原 y15..21 → 列 20..26），根接肩膀、尖点地
    arm = cw(P["arm"])
    f = put(f, arm, 10, GROUND - bottom(arm))
    return f


NEAR_LEG = {hx(c) for c in ("#b2a195", "#b48e80", "#be9898")}


def pose_kneel(P, lean_px=2):
    """跪坐：上身立着、往前倾一点（按行错位），近处那条小腿顺时针放倒、平贴在地上往后伸，脚丫露在身子后面；
    大腿藏在裙摆下面。比站着矮 5 行。"""
    upper = over(P["head"], P["torso"])                  # 第 3..31 行
    lean = [lean_px if y <= 9 else (lean_px + 1) // 2 if y <= 20 else 0 for y in range(FH)]
    upper = shift_rows(upper, lean)
    shin = take(P["legs"], mask_of(P["legs"], NEAR_LEG, 0, FW, 36, FH))
    shin = cw(shin)                                       # 脚（原 y41）在列 0，膝在右，小腿正面朝下
    far = take(P["legs"], mask_of(P["legs"], None, 0, FW, 39, FH) & ~mask_of(P["legs"], NEAR_LEG))
    f = blank()
    f = put(f, far, -9, 0)                                # 远处那只脚丫，藏在后面露一点
    f = put(f, shin, 8, GROUND - bottom(shin))           # 膝盖在裙摆下面，脚丫往后伸出身子
    shin_top = int(np.nonzero((f[..., 3] > 0).any(1))[0].min())
    dy = shin_top - 31                                    # 裙摆（第 31 行）压在小腿上沿
    tail = P["tail"]
    f = under(f, tail, -1, min(dy, GROUND - bottom(tail)))
    f = put(f, upper, 0, dy)
    f = put(f, shift_rows(P["arm"], [lean_px // 2] * FH), 0, dy)
    return f


def pose_crouch(P):
    """半蹲、往前倾：站姿去掉大腿的 3 行（第 33~35 行），上面整体往下落 3 行，头往前探 1~2 像素。"""
    s = over(P["tail"], over(P["body"], P["arm"]))
    cut = [33, 34, 35]
    keep = [y for y in range(FH) if y not in cut]
    squat = np.zeros_like(s)
    squat[len(cut):] = s[keep]
    lean = [2 if y <= 12 else 1 if y <= 24 else 0 for y in range(FH)]
    squat = shift_rows(squat, lean)
    f = blank()
    return put(f, squat, 0, 0)


def pose_stand(stand):
    return put(blank(), stand, 0, 0)


# getup 一段（chen.gd 里用的帧序和毫秒）：抽一下 → 又趴回去 → 再抽一下 → 撑起 → 跪坐 → 半蹲 → 站直
GETUP_FRAMES = [1, 0, 1, 2, 3, 4, 5]
GETUP_MS = [140, 420, 160, 460, 420, 200, 150]


def build():
    stand = load_stand()
    P = parts(stand)
    frames = [
        pose_lie(P),            # 0 趴着
        pose_lie(P, lift=1),    # 1 抽一下
        pose_push(P),           # 2 撑起上身
        pose_kneel(P),          # 3 跪坐
        pose_crouch(P),         # 4 半蹲
        pose_stand(stand),      # 5 站直 = 待机第 0 帧
    ]
    return frames


def main(preview=None):
    frames = build()
    for i, f in enumerate(frames):
        assert set(np.unique(f[..., 3])) <= {0, 255}
        assert f[GROUND, :, 3].any(), f"第 {i} 帧没有像素踩在地面行"
    rep = check_animation(frames, None)
    print([(r["rule"], r["level"], r["value"]) for r in rep])
    tags = [{"name": "lie", "from": 0, "to": 0, "direction": "forward"},
            {"name": "getup", "from": 1, "to": len(frames) - 1, "direction": "forward"}]
    write_sheet(frames, CHEN / "chen_getup.png", tags=tags, durations=[400, 150, 460, 420, 200, 150])
    print(f"写出 {CHEN}/chen_getup.png（{len(frames)} 帧，每帧 {CW}×{CH}）")
    if preview:
        p = Path(preview)
        p.mkdir(parents=True, exist_ok=True)
        bg = (28, 52, 48)
        seq = [frames[0]] * 4 + [frames[i] for i in GETUP_FRAMES] + [frames[-1]] * 3
        ms = [250] * 4 + GETUP_MS + [300] * 3
        write_gif(seq, p / "chen_getup_8x.gif", scale=8, durations=ms, bg=bg)
        strip = Image.new("RGBA", ((CW + 2) * len(frames), CH + 2), bg + (255,))
        for i, f in enumerate(frames):
            g = np.zeros((CH + 2, CW, 4), np.uint8)
            g[CH:, :] = (60, 80, 60, 255)
            g[:CH] = np.where(f[..., 3:] > 0, f, g[:CH])
            strip.alpha_composite(Image.fromarray(g, "RGBA"), ((CW + 2) * i, 0))
        strip.convert("RGB").resize((strip.width * 6, strip.height * 6), Image.NEAREST).save(p / "chen_getup_6x.png")
        print("预览", p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview")
    main(ap.parse_args().preview)
