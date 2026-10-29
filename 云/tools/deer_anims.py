"""鹿的手画动画（美术姐的鹿，美术姐没画的两段）：idle（呼吸待机）、ear（耳朵抖一下）、run（奔跑）。

全部从 art/characters/deer/deer.png 的帧 0（站着）逐像素改出来：只用原图调色板里的颜色、原生像素、不缩放、
硬边 alpha 0/255、不描边、没有纯黑。deer.png 是 tools/deer_from_gif.py 生成的，先跑那个再跑这个。

输出：
  art/characters/deer/deer_idle.png   53×58 一帧（和 deer.png 一样，FOOT 一样），帧 0~5 = idle 循环，帧 6 = 耳朵往后抖
  art/characters/deer/deer_walk.png   64×60 一帧（和 run 同一块画布、同一个锚点），帧 0~7 walk，8~15 walk_flick
  art/characters/deer/deer_run.png    64×60 一帧（右边多 11 列给往后蹬的后腿、上面多 2 行给跳起来的身体），
                                      FOOT = (34, 57)：和 deer.png 的 (34, 55) 是同一个点，只是画布大了
各自配一份 Aseprite 格式的 .json（帧、时长、标签），画师想接着改可以直接导进去。

idle（6 帧 × 200ms，循环）：身体（腿根以上整块）吸气时抬 1 格、腿跟着长 1 格（脚底不动）；尾巴先翘、再往后甩一下、落回。
ear（耳朵抖：抖、回、抖，每帧 200ms，npc_deer.gd 偶尔穿插在 idle 两圈之间）：耳朵尖往后歪 1 格。
walk（8 帧 × 100ms，循环；后 8 帧是同样的步子、尾巴甩一下的版本，偶尔替换一圈）：四拍慢走，见下面 WALK_*。
run（6 帧 × 100ms，循环）：四条腿用两节骨头（IK）现画，躯干去掉原来的腿；一步 = 伸展腾空 → 前腿落地 → 前腿蹬 →
     收腿腾空 → 后腿落地 → 后腿蹬。身体跟着上下 0~2 格，尾巴竖起来（白尾巴翘着跑）。
     着地的蹄子一帧往后扫 SWEEP 格：npc_deer.gd 的 RUN_SPEED = SWEEP × 10 像素 / 秒时蹄子不打滑。

用法（工程根目录下）："/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/deer_anims.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "art/characters/deer/deer.png"
OUT_IDLE = ROOT / "art/characters/deer/deer_idle.png"
OUT_RUN = ROOT / "art/characters/deer/deer_run.png"
OUT_WALK = ROOT / "art/characters/deer/deer_walk.png"

FW, FH = 53, 58                 # deer.png 的帧
FOOT_Y = 55
LEG_TOP = 43                    # 这一行往下全是腿（腿根在上面一点的身体里）
RUN_W, RUN_H, RUN_TOP = 64, 60, 2   # 奔跑画布：上面多 RUN_TOP 行
SWEEP = 9                       # 着地的蹄子一帧往后扫几格

# 原图调色板（deer.png 里的颜色，按亮度）
P = {
    "b": (78, 50, 50), "c": (106, 59, 50), "g": (111, 85, 99),
    "h": (153, 78, 56), "i": (166, 90, 71), "j": (179, 94, 80), "k": (200, 115, 90),
}


def load_stand():
    a = np.array(Image.open(SRC).convert("RGBA"))
    return a[:, :FW].copy()


def save(frames, path, ms, tags):
    H, W = frames[0].shape[:2]
    sheet = np.concatenate(frames, axis=1)
    Image.fromarray(sheet).save(path)
    data = {"frames": [{"filename": f"{path.stem} {i}", "frame": {"x": i * W, "y": 0, "w": W, "h": H},
                        "duration": int(d)} for i, d in enumerate(ms)],
            "meta": {"image": path.name, "size": {"w": W * len(frames), "h": H},
                     "frameTags": [{"name": n, "from": a, "to": b, "direction": "forward"} for n, a, b in tags]}}
    path.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"→ {path.relative_to(ROOT)}：{len(frames)} 帧，每帧 {W}×{H}，ms {ms}")


# ----------------------------------------------------------------------------------------- idle
TAIL = (slice(22, 28), slice(42, 50))    # 尾巴那块（第 28 行起是背）


def breathe(f, rise):
    """腿根以上整体抬 rise 行，最上面那行腿重复一次补空（脚底不动）"""
    if rise == 0:
        return f.copy()
    o = f.copy()
    o[:LEG_TOP - rise] = f[rise:LEG_TOP]
    o[LEG_TOP - rise:LEG_TOP] = f[LEG_TOP - 1]
    return o


def tail(f, mode, base=0):
    """mode：'up' 尾巴翘高 1 格（往上伸长）、'flick' 再往后甩 1 格、'flag' 竖起来 2 格（跑）。
    base = 身体抬了几格（尾巴那块跟着往上挪了）"""
    if mode is None:
        return f
    o = f.copy()
    y0, y1 = 24 - base, 28 - base          # 尾巴是 y0..y1-1 这四行，y1 那行是背
    x0, x1 = 42, 50
    t = f[y0:y1, x0:x1].copy()
    o[y0 - 3:y1, x0:x1 + 1] = 0
    o[y1 - 1, x0:x1] = np.where(t[-1, ..., 3:] > 0, t[-1], 0)       # 尾根那行留着，接着背
    if mode == "up":
        o[y0 - 1:y1 - 1, x0:x1] = _over(o[y0 - 1:y1 - 1, x0:x1], t)
    elif mode == "flick":
        o[y0 - 1:y1 - 1, x0 + 1:x1 + 1] = _over(o[y0 - 1:y1 - 1, x0 + 1:x1 + 1], t)
        o[y1 - 2, x0:x1] = _over(o[y1 - 2, x0:x1], t[-1])                # 尾根别断
    elif mode == "flag":
        o[y0 - 2:y1 - 2, x0 + 1:x1 + 1] = _over(o[y0 - 2:y1 - 2, x0 + 1:x1 + 1], t)
        o[y1 - 3:y1 - 1, x0:x1] = _over(o[y1 - 3:y1 - 1, x0:x1], np.stack([t[-1], t[-1]]))
    return o


def _over(dst, src):
    m = src[..., 3:] > 0
    return np.where(m, src, dst)


def ear_back(f):
    """耳朵（正对镜头那只，浅色的内耳）尖往后歪 1 格：第 10~11 行的耳朵往右挪 1，空出来的地方露出后面的角根色"""
    o = f.copy()
    ear = {(10, x) for x in (26, 27, 28)} | {(11, x) for x in (25, 26, 27, 28)}
    for y, x in ear:
        o[y, x] = (*P["c"], 255)
    for y, x in ear:
        o[y, x + 1] = f[y, x]
    return o


def make_idle(stand):
    # 帧：呼吸抬几格、尾巴
    plan = [(0, None), (0, "up"), (1, "flick"), (1, "up"), (1, None), (0, None)]
    frames = [tail(breathe(stand, r), t, r) for r, t in plan]
    frames.append(ear_back(stand))
    return frames


# ----------------------------------------------------------------------------------------- run
# 腿根（帧 0 坐标，腿的转轴在身体里面），两节骨头长度，膝/跗关节往哪边弯（-1 = 往前 = 往左），粗细，颜色
LEGS = {
    #       根            L1   L2   弯   上粗 下粗  上色  下色  蹄色
    "FF": ((27.0, 38.0), 8.0, 10.5, -1, 3.0, 2.5, "h", "h", "b"),   # 远侧前腿（比近侧暗一档，跑起来分得清前后）
    "FH": ((42.0, 37.0), 8.0, 11.5, 1, 3.0, 2.5, "h", "h", "b"),    # 远侧后腿
    "NF": ((23.5, 38.0), 8.0, 10.5, -1, 3.0, 2.5, "k", "j", "c"),   # 近侧前腿
    "NH": ((47.0, 37.0), 8.0, 11.5, 1, 4.0, 3.0, "k", "j", "c"),    # 近侧后腿
}
G = FOOT_Y
S = SWEEP / 2
# 每帧：身体上下（负 = 往上）和四只蹄子的位置（相对腿根的 x，绝对 y；y = G 是踩在地上）
RUN = [
    # 伸展腾空：前腿往前伸、后腿往后蹬直
    {"dy": -2, "FF": (-8, G - 4), "NF": (-10, G - 5), "FH": (8, G - 4), "NH": (10, G - 5)},
    # 前腿落地（近侧先），后腿往前收
    {"dy": -1, "FF": (-7, G - 3), "NF": (-S, G), "FH": (6, G - 7), "NH": (6, G - 8)},
    # 前腿蹬，后腿收到肚子下
    {"dy": 0, "FF": (-S + 3, G), "NF": (S, G), "FH": (-1, G - 6), "NH": (0, G - 7)},
    # 收腿腾空：前腿往后折、后腿往前伸
    {"dy": -1, "FF": (4, G - 6), "NF": (6, G - 5), "FH": (-5, G - 3), "NH": (-4, G - 4)},
    # 后腿落地，前腿折着
    {"dy": 0, "FF": (1, G - 7), "NF": (3, G - 6), "FH": (-S + 2, G), "NH": (-S, G)},
    # 后腿蹬，前腿往前送
    {"dy": -1, "FF": (-5, G - 5), "NF": (-7, G - 6), "FH": (S - 1, G - 1), "NH": (S, G)},
]


def bone(pts, a, b, w):
    a, b = np.array(a), np.array(b)
    d = b - a
    n = np.linalg.norm(d)
    if n < 1e-6:
        return
    u = d / n
    perp = np.array([-u[1], u[0]])
    for t in np.linspace(0.0, 1.0, int(n * 4) + 2):
        p = a + t * d
        for s in np.arange(-(w - 1) / 2.0, (w - 1) / 2.0 + 0.01, 0.5):
            q = p + s * perp
            pts.add((int(math.floor(q[1] + 0.5)), int(math.floor(q[0] + 0.5))))


def ik(root, target, l1, l2, bend):
    r, t = np.array(root), np.array(target, float)
    d = t - r
    dist = float(np.clip(np.linalg.norm(d), abs(l1 - l2) + 0.01, l1 + l2 - 0.01))
    if np.linalg.norm(d) > l1 + l2 - 0.01:
        t = r + d / np.linalg.norm(d) * dist
    base = math.atan2(d[1], d[0])
    a = math.acos(np.clip((l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist), -1, 1))
    ks = [r + l1 * np.array([math.cos(base + s * a), math.sin(base + s * a)]) for s in (1, -1)]
    knee = min(ks, key=lambda k: k[0]) if bend < 0 else max(ks, key=lambda k: k[0])
    return knee, t


def draw_leg(o, name, hoof, dy, legs=None):
    (rx, ry), l1, l2, bend, w1, w2, c1, c2, ch = (legs or LEGS)[name]
    root = (rx, ry + dy)
    target = (rx + hoof[0], hoof[1])
    knee, end = ik(root, target, l1, l2, bend)
    up, low = set(), set()
    bone(up, root, knee, w1)
    bone(low, knee, end, w2)
    # 蹄子：小腿最末 2 格
    d = end - knee
    hoof_px = set()
    bone(hoof_px, knee + d * (1 - 1.6 / np.linalg.norm(d)), end, w2)
    for y, x in up:
        o[y, x] = (*P[c1], 255)
    for y, x in low - up:
        o[y, x] = (*P[ch if (y, x) in hoof_px else c2], 255)
    return int(round(end[1]))


def make_run(stand):
    body = stand.copy()
    body[39:] = 0                       # 原来的腿去掉（第 39 行起是腿；胸口和后腿根的肉在 38 行以上留着）
    frames = []
    for k, fr in enumerate(RUN):
        dy = fr["dy"]
        o = np.zeros((RUN_H, RUN_W, 4), np.uint8)
        legs_far = np.zeros_like(o)
        legs_near = np.zeros_like(o)
        lows = {}
        for n in ("FF", "FH"):
            lows[n] = draw_leg(legs_far, n, (fr[n][0], fr[n][1] + RUN_TOP), dy + RUN_TOP)
        for n in ("NF", "NH"):
            lows[n] = draw_leg(legs_near, n, (fr[n][0], fr[n][1] + RUN_TOP), dy + RUN_TOP)
        b = tail(body, "flag")
        bb = np.zeros_like(o)
        y0 = RUN_TOP + dy
        bb[max(0, y0):y0 + FH, :FW] = b[max(0, -y0):RUN_H - y0]
        o = _over(o, legs_far)
        o = _over(o, legs_near)
        o = _over(o, bb)
        on = [n for n in lows if lows[n] - RUN_TOP == G]
        print(f"  run {k}：身体 {dy:+d}，着地 {on or '无（腾空）'}，蹄子最低 y {max(lows.values()) - RUN_TOP}")
        frames.append(o)
    return frames


# ----------------------------------------------------------------------------------------- walk
# 走路：四拍（近后 → 近前 → 远后 → 远前，各差 2 帧；对角的两条腿「近前 + 远后」「远前 + 近后」差 2 帧成对交替），8 帧 × 100ms。
# 每条腿 8 帧里 5 帧着地（蹄子在地上，相对身体每帧往后挪 WALK_STEP 格 = 世界里不动），3 帧抬起来往前送。
# 腿根、粗细、颜色和 run 一样（远侧两条腿暗一档），只是两节骨头长一点：着地的蹄子在腿根前后 2×WALK_STEP 格也够得着。
WALK_STEP = 3                   # 着地的蹄子一帧往后挪几格 → npc_deer.gd 的 WALK_SPEED = WALK_STEP × 10 像素 / 秒不打滑
# 两节骨头总长 = 刚好够到最前 / 最后那一步（2×WALK_STEP 格）：站在中间时膝盖只弯一点点，腿比 run 直、稳
def _walk_len(name):
    (rx, ry), l1 = LEGS[name][0], LEGS[name][1]
    return math.hypot(G - ry, 2 * WALK_STEP) + 0.05 - l1


WALK_LEGS = {n: (v[0], v[1], _walk_len(n), *v[3:]) for n, v in LEGS.items()}
WALK_PHASE = {"NH": 0, "NF": 2, "FH": 4, "FF": 6}
# 一条腿在自己这一圈第 t 帧：(蹄子相对腿根的 x, 离地几格)；朝左走，往前 = x 变小
_W = WALK_STEP
WALK_LEG = [(-2 * _W, 0), (-_W, 0), (0, 0), (_W, 0), (2 * _W, 0),     # 着地：从前往后
            (_W, 2), (0, 3), (-_W, 2)]                                # 抬起来往前送（小腿往后折）
WALK_DY = [0, 0, 1, 0, 0, 0, 1, 0]          # 身体：两只后蹄各落地一帧以后往下沉 1 格
WALK_HEAD = [0, 0, 0, 1, 0, 0, 0, 1]        # 头再晚一帧点一下（相对身体），所以头是 0 0 1 1 0 0 1 1
WALK_FLICK = {3: "up", 4: "flick", 5: "up"}  # walk_flick（偶尔替换一圈）：这几帧尾巴甩一下


def nod(f, d):
    """头（第 0~21 行）往下点 d 格，压进脖子上端"""
    if d == 0:
        return f
    o = f.copy()
    o[d:22 + d] = f[0:22]
    o[:d] = 0
    return o


def make_walk(stand, flick=False):
    body = stand.copy()
    body[39:] = 0
    frames = []
    for k in range(8):
        dy = WALK_DY[k]
        o = np.zeros((RUN_H, RUN_W, 4), np.uint8)
        legs_far = np.zeros_like(o)
        legs_near = np.zeros_like(o)
        lows = {}
        for n in ("FF", "FH", "NF", "NH"):
            x, lift = WALK_LEG[(k - WALK_PHASE[n]) % 8]
            dst = legs_far if n[0] == "F" else legs_near
            lows[n] = draw_leg(dst, n, (x, G - lift + RUN_TOP), dy + RUN_TOP, WALK_LEGS) - RUN_TOP
        b = nod(body, WALK_HEAD[k])
        if flick and k in WALK_FLICK:
            b = tail(b, WALK_FLICK[k])
        bb = np.zeros_like(o)
        y0 = RUN_TOP + dy
        bb[y0:y0 + FH, :FW] = b[:RUN_H - y0]
        o = _over(o, legs_far)
        o = _over(o, legs_near)
        o = _over(o, bb)
        on = [n for n in lows if lows[n] == G]
        bad = [n for n in lows if WALK_LEG[(k - WALK_PHASE[n]) % 8][1] == 0 and lows[n] != G]
        if not flick:
            print(f"  walk {k}：身体 {dy:+d}，着地 {on}" + (f"  ！够不着地：{bad}" if bad else ""))
        frames.append(o)
    return frames


def check(frames, name):
    sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
    try:
        from oscarkit.checks import check_animation, report
    except Exception as e:                       # noqa: BLE001  检查器不在也能出图
        print(f"  （没跑 oscarkit 检查：{e}）")
        return
    print(report(check_animation(frames, name if name in ("idle", "move") else None), f"  oscarkit {name}"))


def main():
    stand = load_stand()
    pal = {tuple(c) for c in stand.reshape(-1, 4) if c[3]}
    idle = make_idle(stand)
    save(idle, OUT_IDLE, [200] * len(idle), [("idle", 0, 5), ("ear", 6, 6)])
    check(idle[:6], "idle")
    run = make_run(stand)
    save(run, OUT_RUN, [100] * len(run), [("run", 0, len(run) - 1)])
    check(run, "move")
    walk = make_walk(stand) + make_walk(stand, flick=True)
    save(walk, OUT_WALK, [100] * len(walk), [("walk", 0, 7), ("walk_flick", 8, 15)])
    check(walk[:8], "move")
    for name, fs in (("idle", idle), ("run", run), ("walk", walk)):
        new = {tuple(c) for f in fs for c in f.reshape(-1, 4) if c[3]} - pal
        alpha = {int(v) for f in fs for v in np.unique(f[..., 3])}
        print(f"  {name}：原图调色板以外的颜色 {len(new)} 种，alpha {sorted(alpha)}")


if __name__ == "__main__":
    main()
