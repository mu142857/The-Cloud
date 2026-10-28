"""城市视差（晨打听大象、找古老记载的那座城）。以后改城市图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/city_art.py [--preview 目录]

输出 art/city/*.png（1 倍）和兜帽人的走路帧 art/city/hood_*.png，同时重写 scenes/city_test.tscn
（每层只画有东西的那几行、天缝的斜光、各层人群的参数都从这里算出来，场景里的数不用手改）。
做法照 tools/forest_art.py / cloud_art.py（函数是拷过来的，没有 import 它们）。

第三版（2026-10-28，作者定的方向）：「鸽子笼」。
- 整片一模一样的灰色高层住宅：一格一格的大窗、阳台、楼板线、楼梯间的竖条窗，重复、整齐、冷漠。
  所有楼都从街面冲出画面顶，看不到顶，天只在最远那排楼缝里露几条。越远越小、越淡（同一个设计缩小），
  一层层叠出纵深。没有招牌、晾衣、花盆、烟囱、杂物、小店；亮着的窗只有极少几扇，很暗。
- 颜色以灰为主：亮的（霾、楼板受光的边）带一点点暖（OKLCh h≈85），暗的带一点点冷（h≈255），色度都在 0.01 上下。
  每栋楼只在冷暖上有一点点偏差，不是五颜六色。
- 明暗：近处的楼墙暗，远处往霾里褪；霾在楼腰那一带（y≈130~170）最亮，楼缝深处是一道道发亮的远楼；
  往下沉进街面的暗：晨身后那条（地面往上约 45 像素）又暗又干净。最亮的永远是晨。
- 人：每一层都有一条走道（远处、中远、中景是横贯的高架步道，近处是街面，再近是前景），
  上面一群戴兜帽的人匆匆左右走过，互相不理：远处小、近处大，都是剪影（Godot 里 scripts/city_crowd.gd）。
- 大象：中景有一栋楼的端头是一整面没开窗的山墙，上面一幅褪成浅灰的大象壁画，第二眼才看得出。
图层（scroll_scale 见 SCROLL）：
- sky    霾的色带（屏幕固定），只在 ridge 的楼缝里露出来
- ridge  最远：极小的鸽子笼楼，窗是一个个点
- far    远处：同一种楼，缩小；y≈134 一条高架步道
- midfar 中远：同一种楼；y≈156 一条高架步道
- mid    中景：同一种楼（大窗、阳台、楼梯间），一栋端头是大象山墙；y≈178 一条高架步道
- main   能走的街：路沿一条受光边就是地面（y=228，平的），一排一模一样、不亮的路灯
- front  前景两根近黑的大方柱（高架桥的墩子），从顶通到底
除了天，每层宽 960、左右无缝。所有随机都固定 seed。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
from oscarkit.measure import srgb_to_oklab  # noqa: E402
from oscarkit.palette import from_lch, oklab_to_srgb, to_lab  # noqa: E402

W, H = 960, 270
GROUND = 228
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "city"
CHEN = ROOT / "art" / "characters" / "chen" / "chen.png"
SCENE = ROOT / "scenes" / "city_test.tscn"

SCROLL = {"sky": 0.0, "ridge": 0.06, "far": 0.18, "midfar": 0.38, "mid": 0.62, "main": 1.0, "front": 1.4}

H_WARM = 85     # 亮的一点点暖
H_COOL = 255    # 暗的一点点冷


# ---------------------------------------------------------------- 颜色

def lch(L, C, h):
    return from_lch(L, C, h)


def mix(c, d, t):
    a, b = to_lab(c), to_lab(d)
    return tuple(int(v) for v in oklab_to_srgb((a + (b - a) * t)[None])[0])


def _ab(C, h):
    return np.array([C * np.cos(np.radians(h)), C * np.sin(np.radians(h))])


def lab_col(L, ab):
    return tuple(int(v) for v in oklab_to_srgb(np.array([[L, ab[0], ab[1]]]))[0])


def mat(L, C=0.006, h=H_COOL, n=7, dL=0.042, mid=3):
    """一种灰的色阶（暗 -> 亮），第 mid 档是 (L, C, h)。亮一档往暖偏一点点、暗一档往冷偏一点点。"""
    base = _ab(C, h)
    out = []
    for i in range(n):
        k = i - mid
        ab = base + (abs(k) / 3) * (_ab(0.006, H_WARM) if k > 0 else _ab(0.006, H_COOL))
        out.append(lab_col(float(np.clip(L + k * dL, 0.03, 0.9)), ab))
    return out


# 霾：亮度只跟高度有关；颜色跟亮度走：暗的偏冷、亮的偏一点暖，中间几乎是纯灰
HAZE_Y = [0, 40, 80, 105, 125, 140, 152, 164, 174, 186, 200, 214, 230, 270]
HAZE_L = [0.27, 0.28, 0.32, 0.38, 0.46, 0.53, 0.57, 0.55, 0.47, 0.34, 0.23, 0.16, 0.12, 0.09]
HAZE_STEP = 0.02


def haze_L(y):
    return np.interp(y, HAZE_Y, HAZE_L)


def haze_col(L):
    t = float(np.clip((L - 0.12) / 0.45, 0, 1))
    ab = _ab(0.011, H_COOL) * (1 - t) + _ab(0.012, H_WARM) * t
    return lab_col(L, ab)


SHADOW = lab_col(0.07, _ab(0.009, H_COOL))       # 街面最深的暗（偏冷的近黑）
LIT_DIM = lch(0.34, 0.022, 78)                   # 极少几扇亮窗：很暗的暖灰（晨 L≈0.80）


# ---------------------------------------------------------------- 图层

class Layer:
    """一层图：RGBA + 每个像素的「参照高度」yref（褪色按它查霾色，一栋楼一层楼一个值）+ 自发光（亮窗）。"""

    def __init__(self, w=W, h=H):
        self.a = np.zeros((h, w, 4), np.uint8)
        self.yr = np.zeros((h, w), np.int16)
        self.em = np.zeros((h, w), bool)
        self.info = {}

    def paste(self, p, x, y):
        h, w = p.a.shape[:2]
        H_, W_ = self.a.shape[:2]
        for px in (x - W_, x, x + W_):
            x0, y0 = max(0, px), max(0, y)
            x1, y1 = min(W_, px + w), min(H_, y + h)
            if x0 >= x1 or y0 >= y1:
                continue
            sl = (slice(y0 - y, y1 - y), slice(x0 - px, x1 - px))
            m = p.a[sl][..., 3] > 0
            self.a[y0:y1, x0:x1][m] = p.a[sl][m]
            self.yr[y0:y1, x0:x1][m] = p.yr[sl][m]
            self.em[y0:y1, x0:x1][m] = p.em[sl][m]

    def put(self, x, y, c, yref=None, em=False):
        x %= self.a.shape[1]
        if 0 <= y < self.a.shape[0]:
            self.a[y, x] = tuple(c) + (255,)
            self.yr[y, x] = y if yref is None else yref
            self.em[y, x] = em

    def rect(self, x0, y0, x1, y1, c, yref=None, em=False):
        for y in range(max(0, y0), min(self.a.shape[0], y1)):
            for x in range(x0, x1):
                self.put(x, y, c, yref, em)

    def save(self, name):
        Image.fromarray(self.a).save(OUT / f"{name}.png")


class Piece(Layer):
    """一栋楼的局部画布：坐标原点 = 楼身左上角，四周留 pad。"""

    def __init__(self, w, h, pad=2):
        super().__init__(w + 2 * pad, h)
        self.pad, self.bw, self.bh = pad, w, h

    def R(self, x0, y0, x1, y1, c, em=False):
        ax0, ax1 = max(0, x0 + self.pad), min(self.a.shape[1], x1 + self.pad)
        ay0, ay1 = max(0, y0), min(self.a.shape[0], y1)
        if ax0 < ax1 and ay0 < ay1:
            self.a[ay0:ay1, ax0:ax1] = tuple(c) + (255,)
            self.em[ay0:ay1, ax0:ax1] = em

    def P(self, x, y, c, em=False):
        self.R(x, y, x + 1, y + 1, c, em)


# ---------------------------------------------------------------- 档位抖动（照 cloud_art：大片硬边，只在档边留窄窄一条）

def narrow_levels(lv):
    lv = np.asarray(lv, float)
    h, w = lv.shape
    gy, gx = np.gradient(lv)
    g = np.hypot(gx, gy) + 1e-6
    lo = np.floor(lv + 1e-9)
    dn = (lo + 1 - lv) / g
    Y, X = np.mgrid[0:h, 0:w]
    p50 = (X + Y) % 2 == 0
    p25 = (X + 2 * (Y % 2)) % 4 == 0
    up = ((dn < 1.0) & p50) | ((dn >= 1.0) & (dn < 2.0) & p25)
    return (lo + up).astype(int)


# ---------------------------------------------------------------- 天

def sky():
    """天：只在最远那排楼的缝里露出窄窄几条。上面是压下来的灰霾，往下到楼腰那一带最亮，再往下沉进街面的暗；
    几道扁扁的烟带横着，楼缝里看得到一截一截的明暗。"""
    lay = Layer(480, H)
    Y, X = np.mgrid[0:H, 0:480].astype(float)
    L = haze_L(Y)
    smog = np.zeros_like(L)
    for (cy, cx, hw, th, k) in ((96, 300, 230, 2.4, 0.04), (113, 250, 190, 1.6, 0.04), (124, 420, 240, 2.6, 0.03),
                                (60, 140, 200, 3.0, 0.03), (40, 380, 260, 3.5, 0.025), (78, 90, 170, 2.5, 0.03)):
        u = (X - cx) / hw
        half = th * np.sqrt(np.clip(1 - u ** 2, 0, 1))
        smog += np.where(np.abs(Y - cy - 3 * u ** 2) < half, k, 0)
    lv = narrow_levels((L - smog) / HAZE_STEP)
    out = np.zeros((H, 480, 4), np.uint8)
    for v in np.unique(lv):
        out[lv == v] = tuple(haze_col(min(0.64, v * HAZE_STEP))) + (255,)
    lay.a = out
    return lay


# ---------------------------------------------------------------- 鸽子笼

# 一栋楼从左到右的竖向单元：C 楼梯间（一条竖的窄窗）、w 窗、b 阳台、B 空墙（山墙，不开窗、没有楼板线）
PATTERN = "CwwbwwbwwC"


def block_tower(rng, dims, L, C, h, top, pattern=PATTERN, lit=(), mural=None):
    """一栋鸽子笼：每层一模一样。dims = dict(bay, core, ww, wh, fh, detail)。返回 (Piece, 宽)。
    lit = [(第几层, 第几个单元), ...]：极少几扇亮着的窗（很暗）。mural = (x, y)：大象画在 B 墙上的位置（楼身坐标）。"""
    bay, core, ww, wh, fh, det = (dims[k] for k in ("bay", "core", "ww", "wh", "fh", "detail"))
    xs, x = [], 0
    for u in pattern:
        uw = core if u == "C" else bay
        xs.append((u, x, uw))
        x += uw
    w = x
    hgt = H - top
    p = Piece(w, hgt)
    wl = mat(L, C, h)
    glass = mat(L - 0.14, 0.006, H_COOL, dL=0.03)
    p.R(0, 0, w, hgt, wl[3])
    # 楼层：从下往上数，底层（落地那层）高一点；最上面的楼层冲出画面
    g_h = fh + fh // 2
    floors = []
    y1 = hgt - g_h
    while y1 > -fh:
        floors.append((y1 - fh, y1))
        y1 -= fh
    yref_rows = np.full(hgt, top + hgt - g_h // 2, np.int16)
    for (a, b) in floors:
        yref_rows[max(0, a):max(0, b)] = top + (a + b) // 2
    for k, (y0, y1) in enumerate(floors):
        for i, (u, ux, uw) in enumerate(xs):
            if u == "B":
                # 山墙：大板拼起来的一整面墙，只有板缝（横的每层一道、竖的每格一道），没有窗
                p.R(ux, y0, ux + uw, y0 + 1, wl[2])
                if i + 1 < len(xs) and xs[i + 1][0] == "B":
                    p.R(ux + uw - 1, y0, ux + uw, y1, wl[2])
                continue
            # 楼板：上沿一行受光、下面一行暗（楼板的影子）
            if det >= 2:
                p.R(ux, y0, ux + uw, y0 + 1, wl[5])
                p.R(ux, y0 + 1, ux + uw, y0 + 2, wl[4] if det >= 3 else wl[3])
                p.R(ux, y0 + 2, ux + uw, y0 + 3, wl[1])
            else:
                p.R(ux, y0, ux + uw, y0 + 1, wl[4])
            on = (k, i) in lit
            if u == "C":
                sw = 1 if det <= 2 else 2
                sx = ux + (uw - sw) // 2
                p.R(sx, y0 + 3 + (det >= 3), sx + sw, y1 - 2, glass[1])
            elif u == "w":
                wx = ux + (uw - ww) // 2
                wy = y0 + (3 if det >= 2 else 2)
                p.R(wx, wy, wx + ww, wy + wh, LIT_DIM if on else glass[2], em=on)
                if not on:
                    p.R(wx, wy, wx + ww, wy + 1, glass[0])
                if det >= 2 and ww >= 4:
                    p.R(wx + ww // 2, wy, wx + ww // 2 + 1, wy + wh, wl[2])        # 竖棂
                if det >= 3:
                    p.R(wx, wy + wh // 3, wx + ww, wy + wh // 3 + 1, wl[2])         # 横棂（上面一扇小气窗）
                    p.R(wx, wy + wh, wx + ww, wy + wh + 1, wl[4])                   # 窗台
            elif u == "b":
                # 阳台：整格凹进去（暗），里面一扇门；前面一道实心栏板（亮一档，上沿最亮）
                bx0, bx1 = ux + 1, ux + uw - 1
                if det >= 2:
                    p.R(bx0, y0 + 3, bx1, y1, wl[1])
                    dw = max(2, ww - 2)
                    dx = bx0 + (bx1 - bx0 - dw) // 2
                    p.R(dx, y0 + 4, dx + dw, y1, LIT_DIM if on else glass[1], em=on)
                    ph = max(2, (y1 - y0) * 2 // 5)
                    p.R(bx0 - 1, y1 - ph, bx1 + 1, y1, wl[4])
                    p.R(bx0 - 1, y1 - ph, bx1 + 1, y1 - ph + 1, wl[5])
                    p.R(bx0 - 1, y1 - ph + 1, bx0, y1, wl[5])
                else:
                    p.R(bx0, y0 + 2, bx1, y1 - 1, glass[2])
    # 底层：一排暗的门洞
    gy0 = hgt - g_h
    p.R(0, gy0, w, gy0 + 1, wl[5])
    for (u, ux, uw) in xs:
        if u in "wb" and det >= 2:
            p.R(ux + 2, gy0 + 3, ux + uw - 2, hgt, glass[0])
    # 左边一条受光、右边一条背光
    p.R(0, 0, 1, hgt, wl[4])
    p.R(w - 1, 0, w, hgt, wl[2])
    if mural:
        _mural(p, wl, *mural)
    p.yr[:] = yref_rows[:, None]
    return p, w


# 大象（侧面，朝左）：# 身子，e 耳朵，t 象牙
ELEPHANT = [
    "......######.......................",
    "....##########....##########.......",
    "...############.##############.....",
    "..#######eeeee##################...",
    "..######eeeeeee#################...",
    ".#######eeeeeee##################..",
    ".#######eeeeeee##################..",
    ".########eeeee###################..",
    ".##########ee####################..",
    ".###.############################.#",
    ".###tt##########################..#",
    ".###..#########################....",
    ".###...########################....",
    "..##...####.####.......####.####...",
    "..##...####.####.......####.####...",
    "..##...####.####.......####.####...",
    "#.##...####.####.......####.####...",
    ".##....####.####.......####.####...",
]


def _mural(p, wl, x0, y0):
    """褪成浅灰的大象壁画：比山墙只亮一点点，耳朵再淡一档，下面一道很淡的旧框线。第二眼才看得出。"""
    paint = mix(wl[3], wl[5], 0.42)
    ear = mix(wl[3], wl[5], 0.22)
    tusk = mix(wl[3], wl[6], 0.6)
    for yy, row in enumerate(ELEPHANT):
        for xx, ch in enumerate(row):
            if ch == "#":
                p.P(x0 + xx, y0 + yy, paint)
            elif ch == "e":
                p.P(x0 + xx, y0 + yy, ear)
            elif ch == "t":
                p.P(x0 + xx, y0 + yy, tusk)
    # 掉了几块（露出底下的墙）、一道很淡的框
    for (ox, oy, rw, rh) in ((x0 + 24, y0 + 1, 5, 3), (x0 + 12, y0 + 14, 4, 4)):
        p.R(ox, oy, ox + rw, oy + rh, wl[3])
    frame = mix(wl[3], wl[4], 0.5)
    p.R(x0 - 4, y0 + len(ELEPHANT) + 3, x0 + len(ELEPHANT[0]) + 4, y0 + len(ELEPHANT) + 4, frame)


# ---------------------------------------------------------------- 褪色（按 yref）

def finish(lay, t_air, dark_y0, dark_y1, dark_max, glow_air=0.0, em_air=0.3, dark_steps=6, air_steps=8):
    """把每个像素往「它那层楼高度的霾色」里推 t_air（楼腰那一带霾最亮，再多推 glow_air），
    再往街面的暗里推：yref 在 dark_y0 以上不推，到 dark_y1 推 dark_max，分 dark_steps 档。亮窗只推一点霾、不压暗。"""
    a = lay.a
    m = a[..., 3] > 0
    yr = lay.yr.astype(float)
    hl = np.round(haze_L(yr) / HAZE_STEP).astype(int)
    glow = np.exp(-((yr - 150) / 26) ** 2)
    ta = np.round((t_air + glow_air * glow) * air_steps).astype(int)
    td = np.round(np.clip((yr - dark_y0) / (dark_y1 - dark_y0), 0, 1) * dark_steps).astype(int)
    em = lay.em
    ta = np.where(em, np.round(ta * em_air).astype(int), ta)
    td = np.where(em, 0, td)
    rgb = a[..., :3]
    key = (rgb[..., 0].astype(np.int64) << 40) | (rgb[..., 1].astype(np.int64) << 32) | \
          (rgb[..., 2].astype(np.int64) << 24) | (hl.astype(np.int64) << 12) | (ta.astype(np.int64) << 6) | td
    ks, inv = np.unique(key[m], return_inverse=True)
    cols = np.stack([(ks >> 40) & 255, (ks >> 32) & 255, (ks >> 24) & 255], 1).astype(np.uint8)
    lab = srgb_to_oklab(cols)
    hz = np.array([to_lab(haze_col(min(0.64, v * HAZE_STEP))) for v in ((ks >> 12) & 63)])
    tav = (((ks >> 6) & 63) / air_steps)[:, None]
    tdv = ((ks & 63) / dark_steps * dark_max)[:, None]
    lab = lab * (1 - tav) + hz * tav
    lab = lab * (1 - tdv) + to_lab(SHADOW)[None] * tdv
    new = oklab_to_srgb(lab)
    out = a.copy()
    out[m, :3] = new[inv]
    lay.a = out
    return lay


# ---------------------------------------------------------------- 各层

# 每层：同一种楼缩小。n = 一圈 960 里几栋（楼宽 + 楼缝 = 960 / n），x0 = 第一栋从哪开始（让各层的楼缝错开）
TIERS = {
    "ridge": dict(bay=3, core=2, ww=1, wh=1, fh=4, detail=1, n=30, x0=5, L=0.24, top=-6),
    "far": dict(bay=5, core=4, ww=3, wh=3, fh=6, detail=1, n=16, x0=21, L=0.25, top=-10),
    "midfar": dict(bay=8, core=6, ww=5, wh=5, fh=10, detail=2, n=10, x0=40, L=0.25, top=-20),
    "mid": dict(bay=13, core=9, ww=9, wh=9, fh=16, detail=3, n=6, x0=18, L=0.2, top=-30),
}
DECKS = {"far": 134, "midfar": 156, "mid": 178}      # 横贯的高架步道：桥面最上面一行（人的脚踩在它上面一行）


def tower_row(name, seed, lit_n=0, mural_at=None):
    t = TIERS[name]
    rng = np.random.default_rng(seed)
    lay = Layer()
    period = W // t["n"]
    for i in range(t["n"]):
        # 每栋只在冷暖上有一点点偏差，亮度差一点点
        h = H_COOL if rng.random() < 0.6 else H_WARM
        C = float(rng.uniform(0.003, 0.009))
        L = t["L"] + float(rng.uniform(-0.015, 0.015))
        pat = PATTERN
        mural = None
        if mural_at is not None and i == mural_at:
            pat = "BBBwwbwwC"            # 端头是一整面山墙
            mural = (4, 104 - t["top"])
        lit = []
        for _ in range(lit_n if rng.random() < 0.5 else 0):
            k = int(rng.integers(2, 9))          # 只在上面几层（楼腰以上），不进晨身后那条
            lit.append((k, int(rng.choice([1, 2, 4, 5, 7, 8]))))
        p, w = block_tower(rng, t, L, C, h, t["top"], pattern=pat, lit=lit, mural=mural)
        x = t["x0"] + i * period
        lay.paste(p, x - p.pad, t["top"])
    return lay


def deck(lay, y, L, post=6):
    """横贯整层的高架步道：桥面三行（上沿受光、底面最暗），一道细栏杆，一根根栏杆柱。"""
    m = mat(L, 0.005, H_COOL)
    for x in range(W):
        lay.put(x, y - 4, m[5], yref=y)
        if x % post == 0:
            lay.rect(x, y - 3, x + 1, y, m[3], yref=y)
        lay.put(x, y, m[5], yref=y)
        lay.put(x, y + 1, m[3], yref=y)
        lay.put(x, y + 2, m[1], yref=y)


def ridge():
    lay = tower_row("ridge", 31)
    ys = np.arange(H)[:, None]
    lay.yr = np.broadcast_to(ys // 6 * 6, lay.yr.shape).astype(np.int16).copy()
    return finish(lay, 0.74, 172, 215, 0.85, glow_air=0.14, em_air=0.6)


def far():
    lay = tower_row("far", 41, lit_n=1)
    deck(lay, DECKS["far"], 0.24, post=4)
    return finish(lay, 0.6, 168, 212, 0.85, glow_air=0.2, em_air=0.4)


def midfar():
    lay = tower_row("midfar", 52, lit_n=1)
    deck(lay, DECKS["midfar"], 0.24, post=5)
    return finish(lay, 0.4, 160, 204, 0.85, glow_air=0.24, em_air=0.25)


def mid():
    lay = tower_row("mid", 63, lit_n=1, mural_at=2)
    deck(lay, DECKS["mid"], 0.2, post=6)
    return finish(lay, 0.06, 150, 200, 0.9, glow_air=0.2, em_air=0.0)


LAMPS = [60, 300, 540, 780]    # 主层一排一模一样、不亮的路灯


def main_layer():
    """能走的街：路沿一条受光边就是地面（y=228），人行道一块块石板，下面是很暗的路面。
    街上只有一排间距一样、都不亮的路灯。"""
    lay = Layer()
    curb = lab_col(0.29, _ab(0.006, H_WARM))
    curb2 = lab_col(0.2, _ab(0.006, H_COOL))
    slab = [lab_col(0.13, _ab(0.007, H_COOL)), lab_col(0.145, _ab(0.007, H_COOL))]
    joint = lab_col(0.1, _ab(0.008, H_COOL))
    face = lab_col(0.08, _ab(0.008, H_COOL))
    road = [lab_col(0.075, _ab(0.008, H_COOL)), lab_col(0.09, _ab(0.008, H_COOL))]
    for x in range(W):
        lay.put(x, GROUND, curb)
        lay.put(x, GROUND + 1, curb2)
        for y in range(GROUND + 2, GROUND + 9):
            lay.put(x, y, joint if (x + 7) % 20 == 0 else slab[(x // 20) % 2])
        lay.put(x, GROUND + 9, curb2)
        for y in range(GROUND + 10, GROUND + 12):
            lay.put(x, y, face)
        for y in range(GROUND + 12, H):
            lay.put(x, y, road[1] if (y - GROUND) % 9 == 0 and (x // 30) % 2 == 0 and y < GROUND + 30 else road[0])
    dark = mat(0.11, 0.006, H_COOL, dL=0.03)
    for lx in LAMPS:
        top = 160
        lay.rect(lx - 1, GROUND - 4, lx + 2, GROUND, dark[2])
        lay.rect(lx, top, lx + 1, GROUND - 4, dark[2])
        lay.rect(lx - 1, top, lx, GROUND - 4, dark[4])
        for i in range(8):
            lay.put(lx + 1 + i, top - 1 + (1 if i in (0, 7) else 0), dark[3])
        lay.rect(lx + 6, top + 1, lx + 11, top + 2, dark[3])
        lay.rect(lx + 7, top + 2, lx + 10, top + 6, dark[1])
        lay.rect(lx + 6, top + 6, lx + 11, top + 7, dark[3])
    lay.yr[:] = np.arange(H)[:, None]
    return lay


PILLARS = [(330, 22), (860, 22)]    # 前景的大方柱：x、宽


def front_layer():
    """最前面：两根近黑的大方柱（高架桥的墩子），从顶通到底；左边一条很暗的受光边，每隔一段一道接缝。"""
    lay = Layer()
    c = [lab_col(v, _ab(0.006, H_COOL)) for v in (0.04, 0.055, 0.075, 0.1)]
    for (px, pw) in PILLARS:
        lay.rect(px, 0, px + pw, H, c[1])
        lay.rect(px, 0, px + 1, H, c[3])
        lay.rect(px + 1, 0, px + 3, H, c[2])
        lay.rect(px + pw - 3, 0, px + pw, H, c[0])
        for y in range(18, H, 48):
            lay.rect(px + 1, y, px + pw - 1, y + 1, c[0])
    lay.yr[:] = np.arange(H)[:, None]
    return lay


# ---------------------------------------------------------------- 兜帽人（走路帧）

CROWD_SIZES = (7, 11, 18, 34, 50)
HOOD_FRAMES = 6


def _poly_mask(h, w, pts):
    from matplotlib.path import Path as MPath
    yy, xx = np.mgrid[0:h, 0:w]
    pts_c = np.c_[xx.ravel() + 0.5, yy.ravel() + 0.5]
    return MPath(pts).contains_points(pts_c).reshape(h, w)


def hood_frames(hh):
    """一个戴兜帽的人（朝右走，身子往前倾），高 hh 像素，6 帧走路。返回 (帧列表, 帧宽)。
    剪影为主：灰度三档，Godot 里乘上染色 —— 255 = 兜帽顶、肩膀上的一条受光边，70 = 身子，30 = 兜帽里的脸。"""
    fw = int(np.ceil(hh * 0.62)) + 4
    frames = []
    for f in range(HOOD_FRAMES):
        ph = f / HOOD_FRAMES * 2 * np.pi
        cx = fw / 2 - hh * 0.02

        def P(u, v):          # u 横（以身体中线为 0，向前为正），v 竖（0 头顶，1 脚底）；越往上越往前倾
            return (cx + (u + 0.08 * (1 - v)) * hh, v * hh)

        sway = 0.035 * np.sin(ph * 2)
        body = [P(-0.04, 0.0), P(0.08, 0.04), P(0.14, 0.12), P(0.15, 0.2), P(0.1, 0.25), P(0.15, 0.3),
                P(0.17, 0.55), P(0.19, 0.8), P(0.15, 0.84), P(-0.21 - sway, 0.85), P(-0.17, 0.6),
                P(-0.15, 0.31), P(-0.12, 0.2), P(-0.12, 0.08)]
        m = _poly_mask(hh, fw, body)
        legs = np.zeros_like(m)
        lw = max(1.0, hh * 0.07)
        for side in (1, -1):
            s = side * np.sin(ph)
            fx = 0.15 * s
            leg = [P(-0.05, 0.8), P(-0.05 + 0.0, 0.8), P(fx - lw / hh / 2, 1.0), P(fx + lw / hh / 2, 1.0),
                   P(lw / hh, 0.8)]
            legs |= _poly_mask(hh, fw, [(x, y + 0.01) for x, y in leg])
        face = _poly_mask(hh, fw, [P(0.06, 0.09), P(0.15, 0.12), P(0.14, 0.2), P(0.06, 0.2)])
        img = np.zeros((hh, fw, 4), np.uint8)
        allm = m | legs
        img[allm] = (70, 70, 70, 255)
        img[legs & ~m] = (55, 55, 55, 255)
        if hh >= 11:
            img[face & m] = (30, 30, 30, 255)
        # 受光边：上面或左边是空的、在身体上半截
        up = np.zeros_like(allm)
        up[1:] = allm[:-1]
        left = np.zeros_like(allm)
        left[:, 1:] = allm[:, :-1]
        rows = np.arange(hh)[:, None] < hh * (0.45 if hh >= 18 else 0.3)
        rim = allm & (~up | (~left & rows)) & rows
        img[rim] = (255, 255, 255, 255)
        frames.append(img)
    return frames, fw


def write_hoods():
    info = {}
    for hh in CROWD_SIZES:
        frames, fw = hood_frames(hh)
        sheet = np.concatenate(frames, 1)
        Image.fromarray(sheet).save(OUT / f"hood_{hh}.png")
        info[hh] = fw
    return info


# ---------------------------------------------------------------- 组装

def build():
    OUT.mkdir(parents=True, exist_ok=True)
    layers = {
        "sky": sky(),
        "ridge": ridge(),
        "far": far(),
        "midfar": midfar(),
        "mid": mid(),
        "main": main_layer(),
        "front": front_layer(),
    }
    for k, v in layers.items():
        v.save(k)
    return layers


def check_alpha(layers):
    for k, v in layers.items():
        u = set(np.unique(v.a[..., 3]).tolist())
        assert u <= {0, 255}, (k, u)
        assert v.a.shape[:2] == ((H, 480) if k == "sky" else (H, W)), (k, v.a.shape)


def components(mask, wrap=False):
    """8 连通区域标号（wrap = 左右绕回）。返回 (labels, n)。"""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        st = [(y0, x0)]
        while st:
            y, x = st.pop()
            for yy in (y - 1, y, y + 1):
                if not 0 <= yy < h:
                    continue
                for xx in (x - 1, x, x + 1):
                    if wrap:
                        xx %= w
                    elif not 0 <= xx < w:
                        continue
                    if mask[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n
                        st.append((yy, xx))
    return lab, n


def check_floating(layers, verbose=True):
    """每一块不透明的东西都要落到这层的底边（楼、街、柱子）。返回 {层: [问题...]}。"""
    bad = {}
    for k, lay in layers.items():
        if k == "sky":
            continue
        lab, n = components(lay.a[..., 3] > 0, wrap=True)
        out = []
        for i in range(1, n + 1):
            yy, xx = np.nonzero(lab == i)
            if yy.max() >= H - 1:
                continue
            out.append((len(yy), int(xx.min()), int(xx.max()), int(yy.min()), int(yy.max()), "悬空"))
        bad[k] = out
        if verbose:
            print(f"  {k:7s} 连通区域 {n:4d}，悬空 {len(out)}")
            for b in out[:8]:
                print("     ", b)
    return bad


def check_brightness(layers):
    """背景最亮处要明显低于晨（晨身上大块的米白 L≈0.80）。"""
    worst = 0.0
    for k, v in layers.items():
        m = v.a[..., 3] > 0
        cols = np.unique(v.a[m][:, :3], axis=0)
        lab = srgb_to_oklab(cols)
        worst = max(worst, float(lab[:, 0].max()))
        print(f"  {k:7s} 最亮 L={lab[:, 0].max():.3f}，最大色度 {np.hypot(lab[:, 1], lab[:, 2]).max():.3f}，{len(cols)} 色")
    assert worst < 0.68, f"背景太亮了：L={worst:.3f}"


def check_strip(img):
    """晨身后那一条（地面往上 45 像素，屏幕上）的亮度：最亮、平均。"""
    lab = srgb_to_oklab(img[GROUND - 45:GROUND, :, :3].reshape(-1, 3))
    return float(lab[:, 0].max()), float(lab[:, 0].mean())


def chen_frame(i=3):
    a = np.array(Image.open(CHEN).convert("RGBA"))
    return a[:, i * 40:(i + 1) * 40]


def compose(layers, cam_x, chen_sx=204, chen=True):
    out = np.zeros((H, 480, 4), np.uint8)
    for k in SCROLL:
        a = layers[k].a
        if a.shape[1] == 480:
            src = a
        else:
            off = int(round(cam_x * SCROLL[k])) % a.shape[1]
            src = np.roll(a, -off, axis=1)[:, :480]
        if k == "front" and chen:
            fr = chen_frame()
            y0, x0 = GROUND + 1 - 42, chen_sx - 20
            m = fr[..., 3] > 0
            out[y0:y0 + 42, x0:x0 + 40][m] = fr[m]
        m = src[..., 3] > 0
        out[m] = src[m]
    return out


def preview(layers, cam_x, path):
    Image.fromarray(compose(layers, cam_x)).resize((1440, 810), Image.NEAREST).save(path)


# ---------------------------------------------------------------- 场景

SHAFTS = [(70, 10, 0.07), (300, 6, 0.09), (520, 14, 0.06), (760, 8, 0.08)]   # 远处层的 x、宽、最亮的 alpha
SHAFT_END = 176
SHAFT_SLANT = 0.32        # 光从左上来：每往下 1 像素往右 0.32

# 每条人行道上的人群：层、脚底 y、个子（像素）、人数、速度（像素/秒，这一层的坐标）、染色（受光边的颜色；身子是它的 70/255）
CROWD = [
    ("Far", DECKS["far"] - 1, 7, 12, (7, 12), 0.58),
    ("MidFar", DECKS["midfar"] - 1, 11, 10, (12, 20), 0.52),
    ("Mid", DECKS["mid"] - 1, 18, 8, (20, 32), 0.44),
    ("Main", GROUND - 1, 34, 4, (46, 64), 0.34),
    ("Front", H + 6, 50, 2, (70, 90), 0.2),
]


def shafts():
    """天缝里漏下来的几道斜光（叠加混合），跟远处那层（far，0.18）一起走；Godot 里慢慢呼吸。"""
    out = ['[node name="Shafts" type="Parallax2D" parent="."]', f"scroll_scale = Vector2({SCROLL['far']}, 1)",
           "repeat_size = Vector2(960, 0)", "repeat_times = 2", ""]
    for i, (x, w, a) in enumerate(SHAFTS):
        ym = 140
        pts = [(x, 0), (x + w, 0), (x + w + SHAFT_SLANT * ym * 1.15, ym), (x + w + SHAFT_SLANT * SHAFT_END * 1.25, SHAFT_END),
               (x + SHAFT_SLANT * SHAFT_END, SHAFT_END), (x + SHAFT_SLANT * ym, ym)]
        al = [a * 0.35, a * 0.35, a, 0, 0, a]
        c = "0.82, 0.82, 0.8"
        out += [f'[node name="Shaft{i}" type="Polygon2D" parent="Shafts"]', 'material = SubResource("add")',
                "polygon = PackedVector2Array(" + ", ".join(f"{px:.1f}, {py:.1f}" for px, py in pts) + ")",
                "vertex_colors = PackedColorArray(" + ", ".join(f"{c}, {v:.3f}" for v in al) + ")", ""]
    return out


def write_scene(layers, hood_w):
    def region(name):
        a = layers[name].a[..., 3] > 0
        r = np.nonzero(a.any(1))[0]
        return max(0, int(r.min()) - 1), int(r.max())

    ext = [
        ('Texture2D', 'res://art/city/sky.png', '1_sky'),
        ('Texture2D', 'res://art/city/ridge.png', '2_ridge'),
        ('Texture2D', 'res://art/city/far.png', '3_far'),
        ('Texture2D', 'res://art/city/midfar.png', '4_midfar'),
        ('Texture2D', 'res://art/city/mid.png', '5_mid'),
        ('Texture2D', 'res://art/city/main.png', '6_main'),
        ('Texture2D', 'res://art/city/front.png', '7_front'),
        ('Script', 'res://scripts/city_test.gd', '20_script'),
        ('Shader', 'res://scripts/vignette.gdshader', '21_vig'),
        ('Script', 'res://scripts/city_crowd.gd', '22_crowd'),
        ('Script', 'res://scripts/city_motes.gd', '25_motes'),
        ('PackedScene', 'res://scenes/chen.tscn', '40_chen'),
    ] + [('Texture2D', f'res://art/city/hood_{hh}.png', f'50_hood{hh}') for hh in CROWD_SIZES]
    s = [f"[gd_scene load_steps={len(ext) + 3} format=3]", ""]
    for t, p, i in ext:
        s.append(f'[ext_resource type="{t}" path="{p}" id="{i}"]')
    s += ["", '[sub_resource type="CanvasItemMaterial" id="add"]', "blend_mode = 1", "",
          '[sub_resource type="ShaderMaterial" id="vig"]', 'shader = ExtResource("21_vig")',
          "shader_parameter/strength = 0.55", "shader_parameter/tint = Color(0.92, 0.93, 0.95, 1)", "",
          '[node name="CityTest" type="Node2D"]', 'script = ExtResource("20_script")', ""]

    def para(name, key, tex):
        y0, y1 = region(key)
        sc = SCROLL[key]
        out = [f'[node name="{name}" type="Parallax2D" parent="."]',
               f"scroll_scale = Vector2({sc}, {0 if key == 'sky' else 1})"]
        if key != "sky":
            out += ["repeat_size = Vector2(960, 0)", "repeat_times = 2"]
        out += ["", f'[node name="Sprite" type="Sprite2D" parent="{name}"]', f'texture = ExtResource("{tex}")',
                "centered = false", f"position = Vector2(0, {y0})", "region_enabled = true",
                f"region_rect = Rect2(0, {y0}, {layers[key].a.shape[1]}, {y1 - y0 + 1})", ""]
        return out

    def crowd(parent, feet, hh, n, sp, Lt, seed):
        r, g, b = (v / 255 for v in lab_col(Lt, _ab(0.006, H_COOL)))
        return [f'[node name="Crowd" type="Node2D" parent="{parent}"]', 'script = ExtResource("22_crowd")',
                f'texture = ExtResource("50_hood{hh}")', f"frame_size = Vector2i({hood_w[hh]}, {hh})",
                f"count = {n}", f"feet_y = {feet}", f"speed = Vector2({sp[0]}, {sp[1]})",
                f"tint = Color({r:.3f}, {g:.3f}, {b:.3f}, 1)", f"seed = {seed}", ""]

    cr = {c[0]: c for c in CROWD}
    s += para("Sky", "sky", "1_sky")
    s += para("Ridge", "ridge", "2_ridge")
    s += para("Far", "far", "3_far")
    _, feet, hh, n, sp, Lt = cr["Far"]
    s += crowd("Far", feet, hh, n, sp, Lt, 3)
    s += shafts()
    s += para("MidFar", "midfar", "4_midfar")
    _, feet, hh, n, sp, Lt = cr["MidFar"]
    s += crowd("MidFar", feet, hh, n, sp, Lt, 5)
    s += para("Mid", "mid", "5_mid")
    _, feet, hh, n, sp, Lt = cr["Mid"]
    s += crowd("Mid", feet, hh, n, sp, Lt, 7)
    s += para("Main", "main", "6_main")
    _, feet, hh, n, sp, Lt = cr["Main"]
    s += crowd("Main", feet, hh, n, sp, Lt, 11)
    s += ['[node name="Motes" type="Node2D" parent="Main"]', 'script = ExtResource("25_motes")',
          "color = Color(0.45, 0.45, 0.46, 1)", "count = 16", ""]
    s += ['[node name="Chen" parent="." instance=ExtResource("40_chen")]', f"position = Vector2(204, {GROUND + 1})", ""]
    s += para("Front", "front", "7_front")
    _, feet, hh, n, sp, Lt = cr["Front"]
    s += crowd("Front", feet, hh, n, sp, Lt, 13)
    s += ['[node name="Camera" type="Camera2D" parent="."]', "position = Vector2(240, 135)", "",
          '[node name="Overlay" type="CanvasLayer" parent="."]', "layer = 10", "",
          '[node name="Vignette" type="ColorRect" parent="Overlay"]', 'material = SubResource("vig")',
          "offset_right = 480.0", "offset_bottom = 270.0", "mouse_filter = 2", ""]
    SCENE.write_text("\n".join(s))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="把几张合成预览存到这个目录")
    args = ap.parse_args()
    ls = build()
    hood_w = write_hoods()
    write_scene(ls, hood_w)
    check_alpha(ls)
    print("亮度：")
    check_brightness(ls)
    print("悬空自检：")
    floating = check_floating(ls)
    for cx in (0, 420, 900):
        mx, mean = check_strip(compose(ls, cx, chen=False))
        print(f"  镜头 {cx}: 晨身后那条 最亮 L={mx:.3f} 平均 {mean:.3f}")
    if args.preview:
        d = Path(args.preview)
        d.mkdir(parents=True, exist_ok=True)
        for cx in (0, 420, 900):
            preview(ls, cx, d / f"city_{cx}.png")
    print("ok", {k: v.a.shape[1] for k, v in ls.items()})
    n_bad = sum(len(v) for v in floating.values())
    if n_bad:
        sys.exit(f"有 {n_bad} 块悬空，见上面的列表")
