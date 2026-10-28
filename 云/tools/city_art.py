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
- front  镜头最近的近黑剪影：头顶两段高架梁、三根细灯杆、底边一组很矮的闸机（都碰不到晨）
第四版（同一天，作者：「不够繁忙、不够焦虑，加一些前景，改兜帽人」）：
- 人更多更快，三两成群、交错超车，每条道上有一小股人挤成一团涌过去；兜帽人换成五种赶路的人
  （高瘦甩手 / 背包 / 提公文包 / 矮胖插兜 / 抱箱子低头），前倾、步子大、手臂摆；前景的大个子只露上半身，一闪而过。
- 机械节奏：中景楼前横过一条高架轨道，隔几秒一列车厢窗冷白的列车呼啸穿过（远处还有一条小的）；
  楼边上一颗颗冷青色信号灯按同一个节拍闪，从左到右错开成一道扫过去的脉冲。
- 前景的两根 22 像素宽方柱会挡住晨，去掉了。
第五版（同一天，作者：「缺细节、质感和氛围感」）：
- 鸽子群（scripts/city_pigeons.gd）：远、中远、中景各一群淡灰白的鸽子在楼间慢慢盘旋，像流体一样拉长挤扁，
  转向时一只接一只翻过来；中景还有一群歇在高架轨道梁上，列车开过来时被惊起，绕一圈再落回梁上另一处。
- 下雨（scripts/city_rain.gd）：远、中、近、前景四层斜雨，整像素硬边；街面上溅小水花。
- 湿街面（scripts/city_wet.gdshader）：把地面线以上的亮东西（窗、霾缝、日光灯、信号灯、列车车窗、人影、晨）
  上下翻转照进街面，断成竖条、随雨抖动，几处积水更清楚；晨自己的倒影压得很淡。
- 墙面：窗下、楼板下拖出长短不一的水渍和几道淡锈痕；一排排重复的空调外机；楼梯间竖条窗里的冷白日光灯
  （scripts/city_flicker.gd，个别接触不良，隔几秒快速闪两下）。block_tower 记下楼梯间窗洞的位置给它用。
第六版（同一天）：
- 湿街面倒影不读整屏的细碎东西：每一列看上面那一截城市的平均亮度，只有成块成列的光（霾缝、日光灯、列车车窗）
  在街面上拉成安静的竖光带，边缘被雨打得微微断开；几处积水是镜子。前景底边的栏杆、立柱底座去掉，只留一组很矮的闸机。
- 鸽子群改成 boids（对齐、聚合、分离 + 领头点），整群转向时一大片一起翻亮、翻暗；被列车惊起的那群跟着镜头绕圈，
  落回当前画面里的梁上。墙面水渍压暗两档、空调外机亮一档。
- 居民（作者：「城市居民都要特别高大，主角很矮小、夹在人群中间才有感觉」，「进一步细化每个人身上的比例和东西」）：
  街面一层约 100 像素（晨 52）、前面那层约 128；成年人长比例（头约 1/8、胯在一半略上），
  高瘦 / 宽肩 / 驼背 / 矮壮 / 撑伞几种体型，各有标志物（看手腕、手提袋、公文包、拐杖、纸箱、背包、黑伞），
  外套的下摆、开衩、腰带、口袋盖、袖口，兜帽的帽檐和暗脸里的下巴，裤腿和鞋，肩上一道湿的受光边；8 帧走路。
  people_chart() 画「人物表」（每种人站姿 + 8 帧，旁边站着晨比身高）。
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
    # 空调外机挂在哪几格：整栋楼固定那几格（一排排重复），个别楼层没挂
    ac_units = {i for i, (u, ux, uw) in enumerate(xs) if u in "wb" and (i % 3 == 1 or u == "b")}
    p.info["cores"] = []
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
                p.info["cores"].append((sx, y0 + 3 + (det >= 3), sw, (y1 - 2) - (y0 + 3 + (det >= 3))))
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
    # 空调外机：窗下 / 阳台栏板上挂一个小盒子（亮一档的盒子、竖的散热格、底下一道影子）
    if det >= 2:
        aw, ah = (5, 3) if det >= 3 else (3, 2)
        for k, (y0, y1) in enumerate(floors):
            for i, (u, ux, uw) in enumerate(xs):
                if i not in ac_units or rng.random() < 0.18:
                    continue
                ax = ux + uw - aw - 1 if u == "w" else ux + 1
                ay = y1 - ah - (1 if u == "w" else 1)
                p.R(ax, ay, ax + aw, ay + ah, wl[5])
                p.R(ax, ay, ax + aw, ay + 1, wl[6])
                if det >= 3:
                    for gx in range(ax + 1, ax + aw - 1, 2):
                        p.R(gx, ay + 1, gx + 1, ay + ah, wl[3])
                p.R(ax + aw - 1, ay, ax + aw, ay + ah, wl[3])
                p.R(ax, ay + ah, ax + aw, ay + ah + 1, wl[1])
    # 水渍、锈痕：从窗台、空调、楼板往下拖的竖道，长短不一，把墙和楼板压暗两档（不压到玻璃上）
    if det >= 2:
        darker = {tuple(wl[j]): wl[max(0, j - 2)] for j in range(1, len(wl))}
        rust = lab_col(L - 0.05, _ab(0.016, 55))
        n_st = int(w * hgt / (90 if det >= 3 else 160))
        for _ in range(n_st):
            sx = int(rng.integers(1, w - 1))
            sy = int(rng.integers(0, hgt - g_h))
            ln = int(rng.integers(3, fh * (3 if rng.random() < 0.25 else 1) + 3))
            rusty = rng.random() < 0.18
            for yy in range(sy, min(hgt - g_h, sy + ln)):
                if rng.random() < 0.12 and yy > sy + 2:
                    break
                ax, ay = sx + p.pad, yy
                c = tuple(int(v) for v in p.a[ay, ax, :3])
                if c in darker and not p.em[ay, ax]:
                    nc = darker[c]
                    if rusty:
                        nc = mix(nc, rust, 0.5)
                    p.a[ay, ax, :3] = nc
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
        fh = t["fh"]
        base = H - (fh + fh // 2)                # 楼层从下往上数：第 k 层的上沿在 base - (k+1)*fh
        k_lo, k_hi = (base - 145) // fh, (base - 50) // fh
        for _ in range(lit_n if rng.random() < 0.5 else 0):
            k = int(rng.integers(k_lo, k_hi))    # 只在楼腰以上（y 50~145），不进晨身后那条
            lit.append((k, int(rng.choice([1, 2, 4, 5, 7, 8]))))
        p, w = block_tower(rng, t, L, C, h, t["top"], pattern=pat, lit=lit, mural=mural)
        x = t["x0"] + i * period
        lay.paste(p, x - p.pad, t["top"])
        lay.info.setdefault("towers", []).append((x, w))
        for (cx, cy, cw, ch) in p.info.get("cores", []):
            lay.info.setdefault("cores", []).append((x + cx, t["top"] + cy, cw, ch))
    return lay


TRACKS = {"far": 90, "mid": 62}     # 高架轨道梁的上沿（列车的轮子踩在它上面一行）；中景那条从楼前面横过去


def track(lay, y, L, th=4):
    """横贯整层的高架轨道梁：上沿一道受光的钢轨，下面一条深的梁腹，每隔一段一道加劲肋。"""
    m = mat(L, 0.005, H_COOL)
    for x in range(W):
        lay.put(x, y, m[5], yref=y)
        for k in range(1, th):
            lay.put(x, y + k, m[1] if k == th - 1 else m[2], yref=y)
        if x % 16 == 0:
            lay.rect(x, y + 1, x + 1, y + th, m[3], yref=y)


def signals(lay, name, seed, per=2):
    """冷色信号灯的位置：每栋楼右边（背光的那条边）上几颗，只在楼腰以上。返回 [(x, y), ...]。"""
    rng = np.random.default_rng(seed)
    out = []
    for (x, w) in lay.info["towers"]:
        for _ in range(per):
            out.append((x + w - 2, int(rng.integers(20, 140))))
    return out


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
    track(lay, TRACKS["far"], 0.24, th=3)
    lay.info["signals"] = signals(lay, "far", 5, per=1)
    return finish(lay, 0.6, 168, 212, 0.85, glow_air=0.2, em_air=0.4)


def midfar():
    lay = tower_row("midfar", 52, lit_n=1)
    deck(lay, DECKS["midfar"], 0.24, post=5)
    lay.info["signals"] = signals(lay, "midfar", 6, per=2)
    return finish(lay, 0.4, 160, 204, 0.85, glow_air=0.24, em_air=0.25)


def mid():
    lay = tower_row("mid", 63, lit_n=1, mural_at=2)
    deck(lay, DECKS["mid"], 0.2, post=6)
    track(lay, TRACKS["mid"], 0.2, th=7)
    lay.info["signals"] = signals(lay, "mid", 7, per=2)
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


FRONT_POLES = [40, 360, 680]    # 前景一排灯杆（很细；位置错开，三个截图位置都不压在晨身上，走动时只是一道线一闪而过）


def front_layer():
    """镜头最近的一层，全是近黑的剪影，把画面框住、塞满，但不长时间挡住晨：
    - 头顶横过两段高架梁（贴着画面上沿，最低到 y≈16），梁下一排吊杆；
    - 一排很细的灯杆（3 像素，不亮），从梁通到地；
    - 底边：一道栏杆、几组闸机、两个立柱底座（都在 y≥242，晨的脚在 228，碰不到她）。
    原来那两根 22 像素宽的方柱经过时会把晨挡住一阵，去掉了。"""
    lay = Layer()
    c = [lab_col(v, _ab(0.006, H_COOL)) for v in (0.035, 0.05, 0.07, 0.14)]
    # 高架梁
    for (x0, x1, d) in ((0, 560, 12), (620, 930, 8)):
        lay.rect(x0, 0, x1, d, c[1])
        lay.rect(x0, d - 1, x1, d, c[3])
        lay.rect(x0, d - 3, x1, d - 2, c[0])
        for x in range(x0 + 6, x1 - 2, 24):      # 梁的加劲肋 + 吊杆
            lay.rect(x, 0, x + 2, d, c[0])
            lay.rect(x, d, x + 1, d + 4, c[2])
    # 灯杆
    for px in FRONT_POLES:
        lay.rect(px, 0, px + 3, H, c[1])
        lay.rect(px, 0, px + 1, H, c[3])
        lay.rect(px - 4, 40, px + 7, 42, c[1])
        lay.rect(px + 5, 42, px + 8, 46, c[2])
    # 底边只留一组很矮的闸机（y≥260，只露个顶），把湿街面的倒影让出来；以前的栏杆、立柱底座挡掉了 y 250 以下大半的倒影
    for k in range(4):
        x = 470 + k * 18
        lay.rect(x, 260, x + 8, H, c[0])
        lay.rect(x, 260, x + 8, 261, c[3])
    lay.yr[:] = np.arange(H)[:, None]
    return lay


# ---------------------------------------------------------------- 兜帽人（走路帧）

CROWD_SIZES = (11, 18, 30, 100, 128)
HOOD_FRAMES = 8
# 城里的居民：成年人的长比例（头约身高 1/8，胯在身高一半略上），都比晨（52 像素）高一倍左右。
# 每种体型比例不同、身上至少一样标志物；每种两个小变体（有没有围巾、伞的角度……），Godot 里再按人换一点配色。
#   s 身高比例   sh 肩半宽   hip 胯（0 头顶，1 脚底）   hunch 驼背（肩、头往前探多少）   lean 前倾   stride 步幅（大腿摆角）
#   item: case 公文包 / pack 背包 / umbrella 黑伞 / box 纸箱 / cane 拐杖 / tote 手提袋 / watch 看手腕
#   collar 立领   belt 腰带   scarf 围巾   look 低头 / 看手腕
HOOD_TYPES = [
    dict(name="高瘦·立领看表", s=1.0, sh=0.085, hip=0.46, hunch=0.0, lean=0.06, stride=0.42, item="watch", collar=True,
         belt=True, scarf=False),
    dict(name="高瘦·立领", s=1.0, sh=0.085, hip=0.46, hunch=0.0, lean=0.07, stride=0.44, item="tote", collar=True,
         belt=True, scarf=True),
    dict(name="宽肩·公文包", s=0.97, sh=0.125, hip=0.47, hunch=0.0, lean=0.05, stride=0.38, item="case", collar=False,
         belt=True, scarf=False),
    dict(name="宽肩·公文包·围巾", s=0.97, sh=0.125, hip=0.47, hunch=0.0, lean=0.05, stride=0.38, item="case",
         collar=False, belt=False, scarf=True),
    dict(name="驼背·拐杖", s=0.92, sh=0.1, hip=0.48, hunch=0.07, lean=0.04, stride=0.3, item="cane", collar=False,
         belt=False, scarf=True),
    dict(name="驼背·纸箱·低头", s=0.93, sh=0.1, hip=0.48, hunch=0.06, lean=0.06, stride=0.32, item="box", collar=False,
         belt=True, scarf=False),
    dict(name="矮壮·背包·缩肩", s=0.82, sh=0.12, hip=0.49, hunch=0.02, lean=0.06, stride=0.34, item="pack", collar=True,
         belt=False, scarf=False),
    dict(name="矮壮·背包·围巾", s=0.82, sh=0.12, hip=0.49, hunch=0.02, lean=0.06, stride=0.34, item="pack", collar=False,
         belt=True, scarf=True),
    dict(name="撑伞", s=0.86, sh=0.1, hip=0.47, hunch=0.0, lean=0.05, stride=0.38, item="umbrella", collar=False,
         belt=True, scarf=False, tilt=0.0),
    dict(name="撑伞·斜", s=0.86, sh=0.1, hip=0.47, hunch=0.0, lean=0.05, stride=0.38, item="umbrella", collar=True,
         belt=False, scarf=True, tilt=0.14),
]
# 灰度档（Godot 里乘上染色）：255 湿的受光边（肩、兜帽顶、伞面上沿）、120 手、96 边（袖口、领口、帽檐、提手、伞骨节点）、
# 86 纸箱、78 围巾、70 外套、62 包和伞面、56 褶 / 腰带 / 口袋盖 / 开衩、48 裤子、40 下巴轮廓、36 鞋、30 远侧的胳膊腿、22 脸
G = dict(rim=255, hand=120, edge=96, box=86, scarf=78, body=70, bag=62, fold=56, pants=48, chin=40, shoe=36, far=30, face=22)


def _seg_mask(h, w, a, b, r):
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = np.clip(((xx - ax) * dx + (yy - ay) * dy) / max(1e-6, dx * dx + dy * dy), 0, 1)
    return np.hypot(xx - (ax + t * dx), yy - (ay + t * dy)) <= r


def _poly_mask(h, w, pts):
    from matplotlib.path import Path as MPath
    yy, xx = np.mgrid[0:h, 0:w]
    pts_c = np.c_[xx.ravel() + 0.5, yy.ravel() + 0.5]
    return MPath(pts).contains_points(pts_c).reshape(h, w)


def _ell_mask(h, w, c, rx, ry):
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    return ((xx - c[0]) / max(rx, 0.5)) ** 2 + ((yy - c[1]) / max(ry, 0.5)) ** 2 <= 1


def person_frame(hh, tp, ph, stand=False, f=0):
    """一个戴兜帽赶路的人（朝右走），帧高 hh。ph 是步子的相位（0..2π）；stand = 站姿（不迈步）。
    比例按身高 H = hh·s 算，坐标 u 横（身体中线 0，向前为正）、v 竖（0 头顶，1 脚底），都以 H 为单位。"""
    fw = int(np.ceil(hh * 0.66)) + 6
    H_ = hh * tp["s"]
    big = hh >= 30
    img = np.zeros((hh, fw, 4), np.uint8)
    lay = {}          # 灰度档 -> mask（后画的盖前画的）
    order = []

    def add(name, m):
        if name not in lay:
            lay[name] = np.zeros((hh, fw), bool)
            order.append(name)
        lay[name] |= m

    s = 0.0 if stand else np.sin(ph)
    c_ = 1.0 if stand else np.cos(ph)
    bob = 0.0 if stand or not big else 0.008 * abs(c_)
    cx = fw * 0.47
    hun = tp["hunch"]

    def P(u, v):
        # 前倾 + 驼背：越往上越往前；驼背的人肩以上再往前探
        sh_v = 0.2
        du = tp["lean"] * (1 - v) + (hun * min(1.0, max(0.0, (0.5 - v) / (0.5 - sh_v))) if v < 0.5 else 0.0)
        v2 = v + (bob if v < 0.5 else 0.0)
        return (cx + (u + du) * H_, hh - (1 - v2) * H_)

    def R(r):
        return max(0.55, r * H_)

    def seg(a, b, r):
        return _seg_mask(hh, fw, P(*a), P(*b), R(r))

    def poly(pts):
        return _poly_mask(hh, fw, [P(*p) for p in pts])

    def ell(c, rx, ry):
        return _ell_mask(hh, fw, P(*c), R(rx), R(ry))

    sh = tp["sh"] * (0.9 if tp["item"] == "pack" else 1.0)
    hipv = tp["hip"]
    st = tp["stride"]
    # ---- 腿：大腿、小腿、鞋（前脚掌长、后跟短）；往后蹬的那条腿膝盖弯
    thigh, shin = (0.96 - hipv) * 0.52, (0.96 - hipv) * 0.5
    legs = {}
    for side in (1, -1):
        a1 = st * s * side                                  # 大腿和竖直方向的夹角（弧度）
        bend = 0.0 if stand else 0.42 * max(0.0, -s * side) + 0.12 * max(0.0, c_ * side)
        kx, ky = np.sin(a1) * thigh, hipv + np.cos(a1) * thigh
        a2 = max(a1 - bend, -0.62)
        ax_, ay_ = kx + np.sin(a2) * shin, ky + np.cos(a2) * shin
        lift = max(0.0, ay_ - 0.96)
        ax_, ay_ = ax_, min(ay_, 0.96)
        legs[side] = ((0.0, hipv), (kx, ky), (ax_, ay_))
        toe = 0.055 if a1 > -0.15 else 0.045
        tilt = 0.0 if a1 > -0.15 else 0.015          # 后脚：脚跟抬起
        lw = 0.022 if tp["s"] > 0.85 else 0.026
        m = seg((0.0, hipv), (kx, ky), lw + 0.004) | seg((kx, ky), (ax_, ay_), lw)
        shoe = poly([(ax_ - 0.02, ay_ - 0.005 - tilt), (ax_ + toe * 0.6, ay_ + 0.01), (ax_ + toe, ay_ + 0.03 - tilt * 0.3),
                     (ax_ - 0.022, 1.0 - tilt * 0.6)]) if big else seg((ax_, ay_), (ax_ + toe, 1.0), 0.016)
        if side > 0:
            add("pants", m)
            add("shoe", shoe)
        else:
            add("far", m | shoe)
    # ---- 外套：领口到膝，下摆跟着前腿往前、后摆往后飘；背后开衩
    sway = 0.025 * s
    hem = 0.7 if tp["s"] > 0.85 else 0.72
    w0 = sh * (1.0 if tp["sh"] >= 0.12 else 0.9)
    fu = legs[1][1][0] * 0.35
    coat = [(0.0, 0.135), (w0 * 0.55, 0.15), (w0, 0.175 if tp["sh"] >= 0.12 else 0.19), (w0 * 0.85, 0.3),
            (0.075, hipv), (0.085 + fu, hem), (-0.02, hem + 0.01), (-0.09 - sway, hem + 0.02),
            (-0.08, hipv), (-0.075 - hun * 0.5, 0.3), (-w0 * 0.85 - hun * 0.3, 0.19), (-w0 * 0.55, 0.15)]
    torso = poly(coat)
    if hun > 0:    # 驼背：背上鼓起来一块
        torso |= ell((-0.05, 0.25), 0.065, 0.08)
    add("body", torso)
    # ---- 兜帽：比头大一圈、有厚度；帽檐压住脸
    look_down = tp["item"] in ("box", "watch")
    hd = (0.025 + (0.025 if look_down else 0.0), 0.07 + (0.02 if look_down else 0.0))
    hood = ell(hd, 0.062, 0.068)
    hood |= poly([(hd[0] - 0.01, hd[1] - 0.065), (hd[0] - 0.07, hd[1] - 0.01), (hd[0] - 0.075, hd[1] + 0.07),
                  (-0.04, 0.15), (0.03, 0.15), (hd[0] + 0.05, hd[1] + 0.03)])
    add("body", hood)
    face = ell((hd[0] + 0.035, hd[1] + 0.025), 0.03, 0.04) & hood
    brim = ell((hd[0] + 0.032, hd[1] - 0.005), 0.042, 0.022) & hood & ~face
    opening = ell((hd[0] + 0.03, hd[1] + 0.02), 0.045, 0.055) & hood & ~face
    chin = ell((hd[0] + 0.04, hd[1] + 0.055), 0.017, 0.012) & face
    # ---- 胳膊：和对侧的腿反着摆；拿东西的那只手不摆或摆得很小
    shj = (0.0 if tp["sh"] < 0.12 else -0.005, 0.19 if tp["sh"] < 0.12 else 0.18)
    if tp["item"] == "pack":
        shj = (0.0, 0.17)            # 缩着肩
    ua, fa = 0.155, 0.145
    ar = 0.021 if tp["sh"] < 0.12 else 0.024
    items = tp["item"]
    hands = []
    arm_specs = []
    for side in (-1, 1):             # -1 = 近侧（画在身子前面），1 = 远侧
        a = -st * 0.75 * s * side if not stand else 0.05
        hold = (items in ("case", "tote", "cane") and side == -1) or items in ("box",) or \
            (items == "umbrella" and side == -1) or (items == "watch" and side == 1)
        if items in ("case", "tote") and side == -1:
            a = 0.06 * s                                  # 提东西的手只轻轻晃
            el = (shj[0] + np.sin(a) * ua, shj[1] + np.cos(a) * ua)
            hn = (el[0] + np.sin(a) * fa, el[1] + np.cos(a) * fa)
        elif items == "cane" and side == -1:
            el = (shj[0] + 0.05, shj[1] + ua * 0.95)
            hn = (el[0] + 0.07, el[1] + fa * 0.6)
        elif items == "box":
            el = (shj[0] + 0.06, shj[1] + ua * 0.9)
            hn = (el[0] + 0.1, el[1] - 0.01)
        elif items == "umbrella" and side == -1:
            el = (shj[0] + 0.05, shj[1] + ua * 0.85)
            hn = (el[0] + 0.05, el[1] - 0.07)
        elif items == "watch" and side == 1:            # 远侧那只手抬到胸前，看手腕
            el = (shj[0] + 0.04, shj[1] + ua * 0.9)
            hn = (el[0] + 0.1, el[1] - 0.03)
        elif items == "watch" and side == -1:            # 近侧这只手横过来，露出手腕
            el = (shj[0] + 0.03, shj[1] + ua * 0.92)
            hn = (el[0] + 0.12, el[1] - 0.045)
        elif items == "pack" and side == -1 and tp["scarf"]:
            el = (shj[0] - 0.02, shj[1] + ua)             # 插兜
            hn = (el[0] + 0.05, el[1] + fa * 0.6)
        else:
            el = (shj[0] + np.sin(a) * ua, shj[1] + np.cos(a) * ua)
            b2 = a + (0.35 if a > -0.1 else 0.15)          # 肘往前弯一点
            hn = (el[0] + np.sin(b2) * fa, el[1] + np.cos(b2) * fa)
        arm_specs.append((side, el, hn))
        m = seg(shj, el, ar) | seg(el, hn, ar * 0.9)
        cuff = ell(((el[0] * 0.25 + hn[0] * 0.75), (el[1] * 0.25 + hn[1] * 0.75)), ar * 1.05, ar * 1.05) & m
        add("far" if side == 1 else "arm", m)
        if side == -1 and big:
            add("cuff", cuff)
        hands.append((side, hn))
    for side, hn in hands:
        hm = ell(hn, 0.017, 0.02)
        add("hand_far" if side == 1 else "hand", hm)
    # ---- 东西
    hn_near = [h for s_, h in hands if s_ == -1][0]
    if items == "case":
        sw = 0.012 * s
        x0, y0 = hn_near[0] - 0.07 + sw, hn_near[1] + 0.02
        add("bag", poly([(x0, y0), (x0 + 0.15, y0), (x0 + 0.15, y0 + 0.1), (x0, y0 + 0.1)]))
        if big:
            add("edge", seg((x0, y0), (x0 + 0.15, y0), 0.004) | seg((x0 + 0.055, y0), (x0 + 0.055, y0 - 0.018), 0.005) |
                seg((x0 + 0.095, y0), (x0 + 0.095, y0 - 0.018), 0.005) | seg((x0 + 0.055, y0 - 0.018), (x0 + 0.095, y0 - 0.018), 0.005))
            add("fold", seg((x0 + 0.075, y0 + 0.02), (x0 + 0.075, y0 + 0.035), 0.004))
    elif items == "tote":
        x0, y0 = hn_near[0] - 0.05, hn_near[1] + 0.035
        add("bag", poly([(x0, y0), (x0 + 0.1, y0), (x0 + 0.11, y0 + 0.13), (x0 - 0.01, y0 + 0.13)]))
        add("edge", seg((x0 + 0.015, y0), hn_near, 0.005) | seg((x0 + 0.085, y0), hn_near, 0.005))
    elif items == "cane":
        tip = (hn_near[0] + 0.07 + 0.05 * s, 1.0)
        add("edge", seg(hn_near, tip, 0.008) | seg(hn_near, (hn_near[0] - 0.03, hn_near[1] - 0.01), 0.008))
    elif items == "box":
        bx, by = hn_near[0] - 0.02, hn_near[1] - 0.1
        add("box", poly([(bx, by), (bx + 0.17, by), (bx + 0.17, by + 0.13), (bx, by + 0.13)]))
        if big:   # 箱角、封口
            add("fold", seg((bx, by + 0.035), (bx + 0.17, by + 0.035), 0.004) | seg((bx + 0.085, by), (bx + 0.085, by + 0.035), 0.004))
            add("edge", seg((bx, by), (bx + 0.17, by), 0.004) | seg((bx + 0.17, by), (bx + 0.17, by + 0.13), 0.004))
    elif items == "pack":
        pk = [(-sh * 0.6, 0.18), (-sh - 0.065, 0.2), (-sh - 0.075, 0.42), (-sh * 0.7, 0.44)]
        add("bag", poly(pk))
        if big:
            add("edge", seg((-sh - 0.065, 0.2), (-sh - 0.075, 0.42), 0.004))                   # 包体的厚度（侧面一道亮）
            add("fold", seg((-sh - 0.05, 0.3), (-sh * 0.75, 0.31), 0.005))                      # 包盖
            add("strap", seg((-0.01, 0.165), (sh * 0.6, 0.21), 0.008) | seg((sh * 0.6, 0.21), (sh * 0.55, 0.36), 0.008))
    elif items == "umbrella":
        tilt = tp.get("tilt", 0.0)
        top = (hn_near[0] - 0.02 + tilt * 0.4, -0.14)
        add("edge", seg(hn_near, top, 0.007))
        if big:   # 弯柄（J 形）
            add("edge", seg(hn_near, (hn_near[0], hn_near[1] + 0.03), 0.007) |
                seg((hn_near[0], hn_near[1] + 0.03), (hn_near[0] - 0.025, hn_near[1] + 0.025), 0.007))
        span, hgt_ = 0.3, 0.13
        cxu, base = top[0], top[1] + hgt_
        pts = []
        for k in range(17):
            a = np.pi * (1 - k / 16)
            pts.append((cxu + span * np.cos(a), base - hgt_ * np.sin(a) + tilt * span * np.cos(a)))
        rim_pts = []
        for k in range(8, -1, -1):
            uu = cxu - span + 2 * span * k / 8
            rim_pts.append((uu, base + tilt * (uu - cxu) + (0.0 if k % 2 == 0 else -0.015)))
        canopy = poly(pts + rim_pts)
        add("bag", canopy)
        if big:
            nodes = np.zeros((hh, fw), bool)
            for k in range(0, 9, 2):
                uu = cxu - span + 2 * span * k / 8
                nodes |= ell((uu, base + tilt * (uu - cxu) + 0.004), 0.008, 0.008)        # 伞骨末端的节点
            for k in (2, 4, 6):
                a = np.pi * (1 - k / 8)
                add("fold", seg(top, (cxu + span * np.cos(a), base + tilt * span * np.cos(a)), 0.003) & canopy)
            add("edge", nodes | seg(top, (top[0], top[1] - 0.025), 0.006))              # 伞尖
        up = np.zeros_like(canopy)
        up[1:] = canopy[:-1]
        add("rimx", canopy & ~up)
        if big:   # 雨点打在伞上溅开
            rr = np.random.default_rng(int(f) * 13 + hh)
            sp = np.zeros((hh, fw), bool)
            for _ in range(2):
                a = rr.uniform(0.2, 0.8) * np.pi
                x_, y_ = P(cxu + span * np.cos(a), base - hgt_ * np.sin(a) + tilt * span * np.cos(a))
                xi, yi = int(round(x_)), int(round(y_ - 2 - rr.integers(0, 2)))
                if 0 <= yi < hh and 0 <= xi < fw:
                    sp[yi, xi] = True
            add("rimx", sp)
    # ---- 衣服细节
    if big:
        add("fold", seg((-0.04 - sway * 0.5, hem - 0.08), (-0.045 - sway, hem + 0.015), 0.004) & torso)       # 开衩
        add("fold", seg((0.035, 0.36), (0.04 + fu * 0.5, hem - 0.01), 0.004) & torso)                           # 前襟
        add("fold", seg((0.0, 0.36), (-0.01 + sway * 0.3, hem - 0.02), 0.0035) & torso)                         # 褶
        add("fold", seg((0.045, 0.49), (0.085, 0.49), 0.005) & torso)                                          # 口袋盖
        if tp["belt"]:
            add("fold", seg((-0.08, 0.4), (0.075, 0.4), 0.007) & torso)
            add("edge", seg((0.02, 0.4), (0.03, 0.4), 0.007) & torso)
        add("fold", seg((0.0, 0.18), (w0 * 0.75, 0.2), 0.004) & torso)                                        # 肩线
    if tp["collar"]:
        add("collar", poly([(-0.02, 0.12), (0.055, 0.115), (0.07, 0.17), (0.0, 0.18)]) & ~face)
    if tp["scarf"]:
        add("scarf", poly([(-0.03, 0.14), (0.06, 0.14), (0.065, 0.175), (-0.03, 0.175)]))
        tail = poly([(0.03, 0.17), (0.06, 0.17), (0.07 - 0.02 * s, 0.32), (0.045 - 0.02 * s, 0.32)])          # 垂下的一截
        add("scarf", tail)
    if hh >= 18:
        add("opening", opening)
        add("brim", brim)
        add("face", face)
        if big:
            add("chin", chin)
    tone = dict(pants=G["pants"], shoe=G["shoe"], far=G["far"], body=G["body"], arm=G["body"], cuff=G["edge"],
                hand=G["hand"], hand_far=G["far"] + 20, bag=G["bag"], box=G["box"], fold=G["fold"], edge=G["edge"],
                strap=G["edge"], collar=G["edge"] - 10, scarf=G["scarf"], opening=G["edge"], brim=G["fold"] - 8,
                face=G["face"], chin=G["chin"], rimx=G["rim"])
    # 画的先后：远侧 → 裤鞋 → 身子 → 包 → 胳膊 → 细节 → 脸 → 受光边
    pri = ["far", "hand_far", "pants", "shoe", "body", "bag", "box", "arm", "cuff", "hand", "fold", "strap", "collar",
           "scarf", "edge", "opening", "brim", "face", "chin", "rimx"]
    for name in pri:
        if name in lay:
            img[lay[name]] = (tone[name],) * 3 + (255,)
    if big and "arm" in lay:
        # 近侧的胳膊压在外套上：沿着胳膊描一道暗缝，和身子分开（只描在外套上，不往外描）
        a = lay["arm"]
        dil = a.copy()
        dil[1:] |= a[:-1]
        dil[:-1] |= a[1:]
        dil[:, 1:] |= a[:, :-1]
        dil[:, :-1] |= a[:, 1:]
        edge = dil & ~a & ~lay.get("hand", np.zeros_like(a)) & lay["body"]
        img[edge] = (G["fold"] - 10,) * 3 + (255,)
    allm = img[..., 3] > 0
    up = np.zeros_like(allm)
    up[1:] = allm[:-1]
    shoulder_rows = np.arange(hh)[:, None] < (hh - H_ * (1 - 0.24))
    rim = allm & ~up & shoulder_rows & ~lay.get("face", np.zeros_like(allm))
    img[rim] = (G["rim"],) * 3 + (255,)
    return img, fw


def hood_frames(hh, tp):
    frames = []
    fw = None
    for f in range(HOOD_FRAMES):
        im, fw = person_frame(hh, tp, f / HOOD_FRAMES * 2 * np.pi, f=f)
        frames.append(im)
    return frames, fw


def write_hoods():
    """art/city/hood_<高>.png：每行一种人（HOOD_TYPES 的顺序），每列一帧（8 帧走路）。"""
    info = {}
    for hh in CROWD_SIZES:
        rows = []
        for tp in HOOD_TYPES:
            frames, fw = hood_frames(hh, tp)
            rows.append(np.concatenate(frames, 1))
        sheet = np.concatenate(rows, 0)
        Image.fromarray(sheet).save(OUT / f"hood_{hh}.png")
        info[hh] = fw
    return info


def people_chart(path, hh=100):
    """人物表：每种人一行 —— 站姿 + 8 帧走路，最左边是晨（奥斯卡版，站着）比身高，放大 4 倍。
    为了看清细节，这里把灰度档整体提亮（×1.7，受光边保持白）放在中灰底上；游戏里是乘上各层的暗染色，比这暗得多。"""
    chen = np.array(Image.open(ROOT / "art" / "characters" / "chen" / "chen_oscar.png").convert("RGBA"))[:, 7 * 68:8 * 68]
    tint = np.array([1.7, 1.72, 1.8])
    bg = np.array(lab_col(0.36, _ab(0.006, H_COOL)) + (255,), np.uint8)
    rows = []
    for tp in HOOD_TYPES:
        st, fw = person_frame(hh, tp, 0.0, stand=True)
        frs = [st] + hood_frames(hh, tp)[0]
        row = np.zeros((hh + 4, 68 + 10 + (fw + 4) * len(frs), 4), np.uint8)
        row[:] = bg
        # 晨：脚底对齐
        ch = chen.copy()
        y0 = hh + 1 - 57
        m = ch[..., 3] > 0
        row[y0:y0 + 60, 0:68][m] = ch[m]
        for k, fr in enumerate(frs):
            m = fr[..., 3] > 0
            col = np.clip(fr[..., :3].astype(float) * tint, 0, 255).astype(np.uint8)
            sub = row[1:1 + hh, 78 + k * (fw + 4):78 + k * (fw + 4) + fw]
            sub[m, :3] = col[m]
        rows.append(row)
    wmax = max(r.shape[1] for r in rows)
    sheet = np.concatenate([np.pad(r, ((0, 0), (0, wmax - r.shape[1]), (0, 0)), constant_values=0) for r in rows], 0)
    sheet[sheet[..., 3] == 0] = bg
    Image.fromarray(sheet).resize((sheet.shape[1] * 4, sheet.shape[0] * 4), Image.NEAREST).save(path)


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
            if yy.max() >= H - 1 or (k == "front" and yy.min() == 0):
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
    ("Far", DECKS["far"] - 1, 11, 40, (9, 17), 0.58),
    ("MidFar", DECKS["midfar"] - 1, 18, 30, (16, 30), 0.52),
    ("Mid", DECKS["mid"] - 1, 30, 20, (28, 50), 0.44),
    ("Main", GROUND - 1, 100, 9, (55, 95), 0.34),     # 晨身后一排高大的人（约 100 像素，晨只到他们腰、胸口）
    ("Front", H - 6, 128, 2, (150, 190), 0.17),       # 比晨近一点、从她面前快速划过的大个子（一闪而过，挡她不到半秒）
]
# 高架列车：层、轨道 y、车厢数、车厢长、车高、速度（像素/秒）、间隔（秒）、方向
TRAINS = [
    ("Mid", TRACKS["mid"], 8, 46, 13, 760.0, (4.0, 8.0), 1),
    ("Far", TRACKS["far"], 7, 20, 5, 300.0, (6.0, 11.0), -1),
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
        ('Script', 'res://scripts/city_train.gd', '23_train'),
        ('Script', 'res://scripts/city_signals.gd', '24_signals'),
        ('Script', 'res://scripts/city_pigeons.gd', '26_pigeons'),
        ('Script', 'res://scripts/city_rain.gd', '27_rain'),
        ('Script', 'res://scripts/city_flicker.gd', '28_flicker'),
        ('Shader', 'res://scripts/city_wet.gdshader', '29_wet'),
        ('PackedScene', 'res://scenes/chen.tscn', '40_chen'),
    ] + [('Texture2D', f'res://art/city/hood_{hh}.png', f'50_hood{hh}') for hh in CROWD_SIZES]
    s = [f"[gd_scene load_steps={len(ext) + 4} format=3]", ""]
    for t, p, i in ext:
        s.append(f'[ext_resource type="{t}" path="{p}" id="{i}"]')
    s += ["", '[sub_resource type="CanvasItemMaterial" id="add"]', "blend_mode = 1", "",
          '[sub_resource type="ShaderMaterial" id="wet"]', 'shader = ExtResource("29_wet")', "",
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
                f"types = {len(HOOD_TYPES)}", f"frames = {HOOD_FRAMES}",
                f"count = {n}", f"feet_y = {feet}", f"speed = Vector2({sp[0]}, {sp[1]})",
                f"tint = Color({r:.3f}, {g:.3f}, {b:.3f}, 1)", f"seed = {seed}", ""]

    cr = {c[0]: c for c in CROWD}

    def train(parent):
        for (par, ty, n, cl, ch, v, iv, d) in TRAINS:
            if par == parent:
                return [f'[node name="Train" type="Node2D" parent="{parent}"]', 'script = ExtResource("23_train")',
                        f"rail_y = {ty}", f"cars = {n}", f"car_len = {cl}", f"car_h = {ch}", f"speed = {v}",
                        f"interval = Vector2({iv[0]}, {iv[1]})", f"dir = {d}", f"far = {'true' if parent == 'Far' else 'false'}", ""]
        return []

    def rain(parent, n, ln, v, col, seed, ground=(228, 228), splash=False, dim=(0.17, 0.175, 0.19), area_y=-10):
        return [f'[node name="Rain" type="Node2D" parent="{parent}"]', 'script = ExtResource("27_rain")',
                f"count = {n}", f"length = {ln}", f"speed = {v}", f"color = Color({col[0]}, {col[1]}, {col[2]}, 1)",
                f"color_dim = Color({dim[0]}, {dim[1]}, {dim[2]}, 1)", f"area = Rect2(0, {area_y}, 960, 240)",
                f"ground = Vector2({ground[0]}, {ground[1]})", f"splash = {'true' if splash else 'false'}",
                f"seed = {seed}", ""]

    def pigeons(parent, name, n, size, c, r, sp, seed, perch=None, light=0.47):
        out = [f'[node name="{name}" type="Node2D" parent="{parent}"]', 'script = ExtResource("26_pigeons")',
               f"count = {n}", f"size = {size}", f"center = Vector2({c[0]}, {c[1]})", f"radius = Vector2({r[0]}, {r[1]})",
               f"orbit_speed = {sp}", f"light = Color({light}, {light}, {light + 0.02}, 1)",
               f"dark = Color({light - 0.17:.2f}, {light - 0.165:.3f}, {light - 0.15:.2f}, 1)", f"seed = {seed}"]
        if perch:
            out += ["perch = true", f"perch_y = {perch}", 'train = NodePath("../Train")']
        return out + [""]

    def flicker(parent, key, seed, share):
        rng = np.random.default_rng(seed)
        rs = [c for c in layers[key].info.get("cores", []) if 20 < c[1] and c[1] + c[3] < 165 and rng.random() < share]
        return [f'[node name="Flicker" type="Node2D" parent="{parent}"]', 'script = ExtResource("28_flicker")',
                "rects = Array[Rect2]([" + ", ".join(f"Rect2({x}, {y}, {w}, {h})" for x, y, w, h in rs) + "])",
                f"seed = {seed}", ""]

    def sig(parent, key, seed):
        pts = layers[key].info.get("signals", [])
        return [f'[node name="Signals" type="Node2D" parent="{parent}"]', 'script = ExtResource("24_signals")',
                "points = PackedVector2Array(" + ", ".join(f"{x}, {y}" for x, y in pts) + ")",
                f"dot = {1 if key == 'far' else 2}", f"seed = {seed}", ""]
    s += para("Sky", "sky", "1_sky")
    s += para("Ridge", "ridge", "2_ridge")
    s += para("Far", "far", "3_far")
    _, feet, hh, n, sp, Lt = cr["Far"]
    s += crowd("Far", feet, hh, n, sp, Lt, 3)
    s += train("Far")
    s += sig("Far", "far", 2)
    s += pigeons("Far", "Pigeons", 34, 0, (330, 70), (150, 20), 0.16, 31, light=0.5)
    s += rain("Far", 240, 3, 110, (0.33, 0.34, 0.36), 41, ground=(150, 236), dim=(0.2, 0.205, 0.22))
    s += shafts()
    s += para("MidFar", "midfar", "4_midfar")
    _, feet, hh, n, sp, Lt = cr["MidFar"]
    s += crowd("MidFar", feet, hh, n, sp, Lt, 5)
    s += flicker("MidFar", "midfar", 8, 0.35)
    s += pigeons("MidFar", "Pigeons", 36, 1, (420, 94), (150, 24), 0.2, 32, light=0.49)
    s += sig("MidFar", "midfar", 4)
    s += para("Mid", "mid", "5_mid")
    _, feet, hh, n, sp, Lt = cr["Mid"]
    s += crowd("Mid", feet, hh, n, sp, Lt, 7)
    s += sig("Mid", "mid", 6)
    s += flicker("Mid", "mid", 9, 0.3)
    s += train("Mid")
    s += pigeons("Mid", "Pigeons", 30, 3, (330, 108), (200, 30), 0.17, 33)
    s += pigeons("Mid", "Perched", 18, 3, (0, 0), (110, 26), 0.6, 34, perch=TRACKS["mid"] - 1)
    s += rain("Mid", 150, 5, 220, (0.34, 0.35, 0.37), 42, ground=(170, 236))
    s += para("Main", "main", "6_main")
    _, feet, hh, n, sp, Lt = cr["Main"]
    s += crowd("Main", feet, hh, n, sp, Lt, 11)
    s += rain("Main", 80, 7, 380, (0.38, 0.39, 0.41), 43, ground=(229, 268), splash=True)
    s += ['[node name="Chen" parent="." instance=ExtResource("40_chen")]', f"position = Vector2(204, {GROUND + 1})", ""]
    s += ['[node name="Wet" type="Parallax2D" parent="."]', "scroll_scale = Vector2(0, 0)", "",
          '[node name="Rect" type="ColorRect" parent="Wet"]', 'material = SubResource("wet")',
          "offset_top = 230.0", "offset_right = 480.0", "offset_bottom = 270.0", "mouse_filter = 2", ""]
    s += para("Front", "front", "7_front")
    _, feet, hh, n, sp, Lt = cr["Front"]
    s += crowd("Front", feet, hh, n, sp, Lt, 13)
    s += rain("Front", 14, 12, 620, (0.3, 0.31, 0.33), 44, ground=(240, 290), dim=(0.3, 0.31, 0.33), area_y=-40)
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
