"""兔子（第一关「兔子舞步」）占位图：等作者的美术来换。

python3 tools/rabbit_art.py  →  art/characters/rabbit/rabbit.png + rabbit.json + arrows.png

- 和鹿同一条暖棕色阶（从 art/characters/deer/deer_idle.png 取的颜色），比鹿浅一截：奶黄带棕的兔子。
- 不描边：部件靠明暗分开（后耳、后手、后脚暗一档），光从左上来。
- 用部件 + 姿势参数拼：每个姿势是一组数（身体往哪歪、耳朵角度、手往哪伸），前摇 / 收势帧 = 待机和姿势的一半，
  所以帧和帧之间是连着的，不跳。
- 帧 44×52，脚底 (22, 50)，画的是朝右。整只站起来约 46 像素高（晨 52）。
- 箭头 arrows.png：13×13 一格，列 = 上 右 下 左，行 = 淡（等着按）/ 平常 / 亮（刚跳 / 刚按对）。
"""
import json
import math
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "characters", "rabbit")
FW, FH = 44, 52
FOOT = (22, 50)

# 鹿的色阶（暗 → 亮），兔子用偏亮的一半
RAMP = [(78, 50, 50), (106, 59, 50), (153, 78, 56), (179, 94, 80), (200, 115, 90),
        (210, 133, 92), (240, 169, 140), (254, 208, 177), (255, 241, 204)]
FUR = 6          # 毛的底色
CREAM = 8        # 肚子、尾巴、嘴
INNER = 4        # 耳朵里
EYE = 0
NOSE = 3


# ======================================================================= 部件
def ell_mask(cx, cy, rx, ry, ang=0.0):
    """旋转椭圆（ang 弧度，绕中心）。返回 mask 和每个像素在椭圆里的归一化坐标（屏幕方向）"""
    ys, xs = np.mgrid[0:FH, 0:FW]
    px = xs + 0.5 - cx
    py = ys + 0.5 - cy
    c, s = math.cos(ang), math.sin(ang)
    u = (px * c + py * s) / max(rx, 0.1)
    v = (-px * s + py * c) / max(ry, 0.1)
    m = u * u + v * v <= 1.0
    nx = px / max(rx, ry)
    ny = py / max(rx, ry)
    return m, nx, ny


def limb(base, ang_deg, length, width):
    """从 base 往 ang 方向伸出去的一根（0 = 朝下，90 = 朝右，180 = 朝上，-90 = 朝左）"""
    a = math.radians(ang_deg)
    d = (math.sin(a), math.cos(a))
    cx = base[0] + d[0] * length / 2.0
    cy = base[1] + d[1] * length / 2.0
    # 椭圆的长轴沿 d：ell_mask 的 rx 沿 (cos, sin)，所以转到 d 的角度
    rot = math.atan2(d[1], d[0])
    return ell_mask(cx, cy, length / 2.0, width / 2.0, rot)


def lerp(a, b, k):
    if isinstance(a, (tuple, list)):
        return tuple(lerp(x, y, k) for x, y in zip(a, b))
    return a + (b - a) * k


IDLE = {
    "dy": 0.0,          # 整只上下（负 = 跳起来）
    "lean": 0.0,        # 上身往左右歪（像素，头最多）
    "sq": 0.0,          # 身体压扁（正 = 矮胖）
    "head": (0.0, 0.0),
    "earF": 6.0, "earB": 16.0, "ear_len": 15.0,
    "armF": 10.0, "armB": 6.0, "arm_len": 8.0, "arm_y": 0.0,
    "footF": 0.0, "footB": 0.0, "feet_up": 0.0,
}


def pose(**kw):
    p = dict(IDLE)
    p.update(kw)
    return p


POSES = {
    "idle": IDLE,
    "idle_b": pose(head=(0.0, 1.0), arm_y=1.0, earF=8.0, earB=18.0, sq=0.6),     # 呼吸：头和手往下一格
    "idle_t": pose(earF=-4.0),                                                   # 前耳抖一下
    # 舞步（画的是朝右，← = 往后）：身子往那边歪，伸手指过去，耳朵被甩到反方向
    "left": pose(lean=-5.0, head=(-1.0, 0.0), earF=28.0, earB=40.0, armF=-75.0, armB=-100.0, arm_len=12.0,
                 arm_y=-1.0, footB=-3.0),
    "right": pose(lean=5.0, head=(1.0, 0.0), earF=-18.0, earB=-6.0, armF=100.0, armB=75.0, arm_len=12.0,
                  arm_y=-1.0, footF=3.0),
    "up": pose(dy=-4.0, sq=-1.0, earF=2.0, earB=10.0, ear_len=16.0, armF=142.0, armB=-148.0, arm_len=13.0,
               arm_y=-2.0, feet_up=1.0),
    "down": pose(dy=0.0, sq=3.5, head=(1.0, 6.0), earF=62.0, earB=74.0, ear_len=14.0, armF=30.0, armB=20.0,
                 arm_y=5.0, footF=2.0, footB=-2.0),
    # 耸肩：两手摊开、手心朝上，头歪一点，耳朵一高一低
    "shrug": pose(head=(-1.0, 1.0), earF=34.0, earB=8.0, armF=104.0, armB=-104.0, arm_len=11.0, arm_y=0.0),
    # 认输：鞠一躬
    "bow": pose(lean=5.0, head=(3.0, 5.0), earF=-50.0, earB=-38.0, armF=20.0, armB=10.0, arm_y=3.0, sq=1.5),
}


def edge_light(lvl, m, base):
    """手臂和身子同色，靠一道上亮下暗的边分开（不描边：只差一档）"""
    up = np.zeros_like(m)
    up[1:] = m[:-1]
    dn = np.zeros_like(m)
    dn[:-1] = m[1:]
    lvl[m] = base
    lvl[m & ~up] = min(base + 1, len(RAMP) - 1)
    lvl[m & ~dn] = max(base - 1, 0)


def render(p):
    """一帧：部件从后往前叠，每格记下颜色档"""
    lvl = np.full((FH, FW), -1, dtype=int)
    L = (-0.55, -0.83)          # 光从左上来

    def put(mask, base, nx, ny, bright=0.55, dark=-0.5, back=False):
        s = -(nx * L[0] + ny * L[1])
        v = np.full(mask.shape, base)
        v = v + (s > bright).astype(int) - (s < dark).astype(int)
        if back:
            v = v - 1
        v = np.clip(v, 0, len(RAMP) - 1)
        lvl[mask] = v[mask]

    dy = p["dy"]
    lean = p["lean"]
    hx, hy = p["head"]
    sq = p["sq"]
    fy = 49.0 + dy - p["feet_up"]
    # 上身各部件随 lean 歪：越高歪得越多
    body_c = (21.0 + lean * 0.45, 36.0 + dy + sq * 0.8)
    head_c = (23.0 + lean + hx, 23.0 + dy + hy)
    shoulder = (body_c[0] + 3.0 + lean * 0.2, 31.0 + dy + sq + p["arm_y"])

    # 后耳
    m, nx, ny = limb((head_c[0] - 3.0, head_c[1] - 4.0), 180.0 + p["earB"], p["ear_len"], 3.6)
    put(m, FUR, nx, ny, back=True)
    # 后手
    m, nx, ny = limb((shoulder[0] - 2.0, shoulder[1]), p["armB"], p["arm_len"], 3.2)
    put(m, FUR, nx, ny, back=True)
    edge_light(lvl, m, FUR - 1)
    # 后脚
    m, nx, ny = ell_mask(17.0 + p["footB"], fy, 6.0, 1.8)
    put(m, FUR, nx, ny, back=True)
    # 尾巴
    m, nx, ny = ell_mask(12.5 + lean * 0.1, 41.5 + dy + sq * 0.6, 3.2, 3.0)
    put(m, CREAM, nx, ny, bright=0.6, dark=-0.2)
    # 大腿
    m, nx, ny = ell_mask(18.5 + lean * 0.1, 44.0 + dy + sq * 0.4, 7.2, 5.2 - sq * 0.2)
    put(m, FUR, nx, ny)
    # 身子
    m, nx, ny = ell_mask(body_c[0], body_c[1], 7.0 + sq * 0.5, 9.0 - sq)
    put(m, FUR, nx, ny)
    # 肚子
    bm, nx, ny = ell_mask(body_c[0] + 3.0, body_c[1] + 1.5, 3.6, 6.5 - sq * 0.8)
    put(bm & m, CREAM - 1, nx, ny, bright=0.2, dark=-0.6)
    # 前脚
    m, nx, ny = ell_mask(24.0 + p["footF"], fy + 0.4, 6.2, 1.8)
    put(m, FUR, nx, ny)
    # 头
    m, nx, ny = ell_mask(head_c[0], head_c[1], 7.0, 6.3)
    put(m, FUR, nx, ny)
    # 嘴
    mm, nx, ny = ell_mask(head_c[0] + 4.6, head_c[1] + 2.4, 2.8, 2.2)
    put(mm & m, CREAM - 1, nx, ny, bright=0.1, dark=-0.9)
    # 前耳（外 + 里）
    ear_base = (head_c[0] + 0.5, head_c[1] - 5.0)
    m, nx, ny = limb(ear_base, 180.0 + p["earF"], p["ear_len"], 4.0)
    put(m, FUR, nx, ny)
    mi, nx2, ny2 = limb(ear_base, 180.0 + p["earF"], p["ear_len"] - 3.5, 1.6)
    lvl[mi & m] = INNER
    # 前手
    m, nx, ny = limb(shoulder, p["armF"], p["arm_len"], 3.4)
    put(m, FUR, nx, ny)
    edge_light(lvl, m, FUR)
    # 爪尖：手的最远那一格亮一点（奶色）
    a = math.radians(p["armF"])
    tip = (shoulder[0] + math.sin(a) * (p["arm_len"] - 1.2), shoulder[1] + math.cos(a) * (p["arm_len"] - 1.2))
    tx, ty = int(math.floor(tip[0])), int(math.floor(tip[1]))
    if 0 <= tx < FW and 0 <= ty < FH and lvl[ty, tx] >= 0:
        lvl[ty, tx] = CREAM - 1
    # 眼睛（两格深色 + 一格亮点）、鼻子
    ex, ey = int(round(head_c[0] + 2.0)), int(round(head_c[1] - 1.5))
    lvl[ey, ex] = EYE
    lvl[ey + 1, ex] = EYE + 1
    lvl[ey, ex + 1] = EYE + 1
    nx_, ny_ = int(round(head_c[0] + 7.0)), int(round(head_c[1] + 1.0))
    if lvl[ny_, nx_] >= 0:
        lvl[ny_, nx_] = NOSE
    elif lvl[ny_, nx_ - 1] >= 0:
        lvl[ny_, nx_ - 1] = NOSE

    img = np.zeros((FH, FW, 4), dtype=np.uint8)
    for i, c in enumerate(RAMP):
        img[lvl == i] = (*c, 255)
    return img


def tidy(img):
    """去掉孤零零的一格（四邻都空）：小尺寸椭圆边上常冒出来"""
    a = img[..., 3] > 0
    out = img.copy()
    for y in range(FH):
        for x in range(FW):
            if not a[y, x]:
                continue
            n = 0
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < FW and 0 <= yy < FH and a[yy, xx]:
                    n += 1
            if n <= 1:
                out[y, x] = 0
    return out


# ======================================================================= 帧表
def mid(a, b, k=0.5):
    pa, pb = POSES[a], POSES[b]
    return {key: lerp(pa[key], pb[key], k) for key in pa}


FRAMES = [
    ("idle", POSES["idle"]),          # 0
    ("idle_b", POSES["idle_b"]),      # 1
    ("idle_t", POSES["idle_t"]),      # 2
]
for nm in ["left", "up", "right", "down", "shrug", "bow"]:
    FRAMES.append((nm + "_mid", mid("idle", nm)))     # 前摇 / 收势
    FRAMES.append((nm, POSES[nm]))
IDX = {n: i for i, (n, _) in enumerate(FRAMES)}


def move(nm, hold):
    return [IDX[nm + "_mid"]] + [IDX[nm]] * hold + [IDX[nm + "_mid"]]


ANIMS = {
    "idle": {"frames": [0] * 6 + [1] * 6 + [0] * 6 + [1] * 6 + [0] * 3 + [2] * 2 + [0] * 3 + [1] * 6, "loop": True},
    # 每一步 0.6 秒：前摇 1 帧 + 定住 4 帧 + 收势 1 帧（100ms 一帧）
    "dance_left": {"frames": move("left", 4), "loop": False},
    "dance_up": {"frames": move("up", 4), "loop": False},
    "dance_right": {"frames": move("right", 4), "loop": False},
    "dance_down": {"frames": move("down", 4), "loop": False},
    "shrug": {"frames": move("shrug", 7), "loop": False},
    "bow": {"frames": move("bow", 8), "loop": False},          # 认输鞠一躬，1 秒，回待机
}


# ======================================================================= 箭头
AW = 13
ARROW_UP = [
    "......#......",
    ".....###.....",
    "....#####....",
    "...#######...",
    "..#########..",
    ".###########.",
    "....#####....",
    "....#####....",
    "....#####....",
    "....#####....",
    "....#####....",
    ".............",
    ".............",
]
ARROW_ROWS = [  # 淡 / 平常 / 亮：(底色, 上边亮, 下边暗)
    ((122, 79, 71), (153, 78, 56), (106, 59, 50)),
    ((254, 208, 177), (255, 241, 204), (210, 133, 92)),
    ((255, 241, 204), (255, 252, 236), (240, 169, 140)),
]


def arrows():
    up = np.array([[c == "#" for c in r] for r in ARROW_UP])
    shapes = [up, np.rot90(up, -1), np.rot90(up, 2), np.rot90(up, 1)]    # 上 右 下 左
    sheet = np.zeros((AW * 3, AW * 4, 4), dtype=np.uint8)
    for row, (base, hi, lo) in enumerate(ARROW_ROWS):
        for col, m in enumerate(shapes):
            # 箭头在 13×13 里居中（转过以后空的两行在另一边）
            ys, xs = np.nonzero(m)
            oy = (AW - (ys.max() - ys.min() + 1)) // 2 - ys.min()
            ox = (AW - (xs.max() - xs.min() + 1)) // 2 - xs.min()
            mm = np.zeros_like(m)
            for y, x in zip(ys, xs):
                mm[y + oy, x + ox] = True
            for y in range(AW):
                for x in range(AW):
                    if not mm[y, x]:
                        continue
                    c = base
                    if y == 0 or not mm[y - 1, x] or x == 0 or not mm[y, x - 1]:
                        c = hi
                    if y == AW - 1 or not mm[y + 1, x]:
                        c = lo
                    sheet[row * AW + y, col * AW + x] = (*c, 255)
    return sheet


def main():
    os.makedirs(OUT, exist_ok=True)
    sheet = np.zeros((FH, FW * len(FRAMES), 4), dtype=np.uint8)
    for i, (_, p) in enumerate(FRAMES):
        sheet[:, i * FW:(i + 1) * FW] = tidy(render(p))
    Image.fromarray(sheet).save(os.path.join(OUT, "rabbit.png"))
    Image.fromarray(arrows()).save(os.path.join(OUT, "arrows.png"))
    cfg = {
        "_comment": "兔子：占位图（tools/rabbit_art.py 生成），等作者的美术来换。和鹿同一条暖棕色阶。画的是朝右；"
                    "舞步 dance_left / dance_right 是按画面方向（朝右站时）画的，朝左站时 rabbit_dance.gd 会换成镜像那一段。"
                    "每一步 0.6 秒（100ms 一帧，不加速）。",
        "frame": [FW, FH],
        "sheet": "rabbit.png",
        "anchor": list(FOOT),
        "faces": "right",
        "ms": 100,
        "tint": True,
        "head": 46,
        "speed": 34,
        "color": "#f0a98c",
        "anims": ANIMS,
        "alias": {"talk": "idle", "walk": "idle", "nod": "dance_down", "laugh": "dance_up", "give": "idle",
                  "hand": "idle", "point": "dance_right"},
    }
    with open(os.path.join(OUT, "rabbit.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    print("frames", len(FRAMES), {n: i for n, i in IDX.items()})


if __name__ == "__main__":
    main()
