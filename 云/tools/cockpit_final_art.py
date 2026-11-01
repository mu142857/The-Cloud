"""终章（final）驾驶舱：窗外（船外背景）关键帧 + 驾驶舱补件。以后改这些图只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/cockpit_final_art.py [--preview 目录] [--json]

只新增文件，不改任何已有的图：
- art/cockpit/sky/fc_*.png + art/cockpit/sky/sky_final.json：终章的窗外关键帧（格式和 sky.json 一样，约定见
  docs/flight_sky_contract.md）。sky.json（tools/sky_art.py 生成）一个字不动；引擎把 sky_final.json 的 layers / states
  合进来（只加 sky.json 里没有的名字）。
- art/cockpit/cockpit_<物件>.png：剧本要、flight1 没有的物件（燃料柜、烧掉清单、航图、纸条、影像、日记、最初的画、
  左手边的工具、副驾驶座上的工具包、导航屏的下降 / 轨道两帧、关灯）。
- cockpit_phone_<状态>.png / cockpit_bag_<状态>.png：通讯器和背包的新状态（原来的 cockpit_phone.png / cockpit_bag.png 不动，
  by_gauges 那张是原图的拷贝）。
- --json：把新物件、markers、hotspots、窗外状态名合进 art/cockpit/cockpit.json（只加，原有条目不动；重跑 cockpit_art.py
  会重写 cockpit.json，之后要再跑一次 --json）。

图从哪来：
- 云海：作者的 art/cloud/（scenes/cloud_test.tscn 那一套）原图拷过来（只读，不改原图）：裁掉上下的空行、底下往下续 140 行
  （云沉下去时不露底），sky 四边各续 48 像素（SKY_M），cloud_stars.gd 的星星按同一个 seed 画成静止的；
  叠加混合的 wash / streaks 换成普通透明度的一层（引擎只有普通混合），颜色取余晖色，透明度按原来加多少换算。
- 云层下面的芦苇地：art/reed_field/ 的远景几层拷过来（另一个会话的图，只读）；降落点（旧货场、东侧缓坡）是这里画的。
- 风帆小镇：art/cloud_town/town_far.png 拷过来（只读）。
- 大象：等美术姐。现在 fc_elephant_far.png / fc_elephant_shadow.png 是极淡的剪影占位，直接用同名文件替换就行
  （大小可以变：远处那只是不 tile 的层，左上角 x / y 写在 sky_final.json 的 states 里）。

规矩：亮主角暗背景；森林绿 / 青绿，不用蓝（驾驶舱里）；无透视；不画虚线点线；不画晨和妮芙；动画 100ms 一帧。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CK = ROOT / "art" / "cockpit"
SKY = CK / "sky"
CLOUD = ROOT / "art" / "cloud"
REED = ROOT / "art" / "reed_field"
TOWN = ROOT / "art" / "cloud_town"
HAND = ROOT / "art" / "手改清单.json"

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, "/Users/jiamulin/Desktop/程序programs/AI Oscar")
import cloud_art as ca  # noqa: E402  只借函数（Field / cloud_pal），不调它的 build / save
from oscarkit.palette import from_hex, oklab_to_srgb, to_lab  # noqa: E402

M = 48                      # SKY_M：船外背景比屏幕每边大这么多
EXT = 140                   # 云层底下往下续多少行
SW, SH = 480, 270

# 驾驶舱在屏幕上的位置（cockpit.json：330×150，水平垂直居中）
CK_POS = (75, 60)


def rgba(a):
    return Image.fromarray(np.ascontiguousarray(a).astype(np.uint8), "RGBA")


def arr(im):
    return np.array(im.convert("RGBA"))


def load(p):
    return arr(Image.open(p))


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def protected():
    try:
        return set(json.loads(HAND.read_text())["files"].keys())
    except Exception:
        return set()


PROTECTED = protected()
WROTE: list[str] = []


def save(a, path: Path):
    rel = str(path.relative_to(ROOT))
    assert rel not in PROTECTED, "手改清单里的图不许覆盖：" + rel
    assert path.parent in (SKY, CK), "只往 art/cockpit/ 和 art/cockpit/sky/ 写：" + rel
    if path.parent == CK:
        assert path.name.startswith("cockpit_"), rel
    img = a if isinstance(a, Image.Image) else rgba(a)
    img.save(path)
    WROTE.append(rel)


# ====================================================================== 云海（作者 art/cloud/ 的拷贝）

def crop_rows(a):
    """裁到有内容的行；返回 (图, 上沿 y)。"""
    rows = np.where(a[..., 3].any(1))[0]
    return a[rows[0]:rows[-1] + 1], int(rows[0])


def extend_down(a, n=EXT):
    """底下往下续 n 行：一直通到底的列，用最底下几行里最常见的那个颜色铺下去（云的身体沉进暗里，不露底、
    也不逐列复制出竖条纹）。"""
    h, w = a.shape[:2]
    out = np.zeros((h + n, w, 4), np.uint8)
    out[:h] = a
    tail = a[h - 3:].reshape(-1, 4)
    tail = tail[tail[:, 3] > 0]
    if not len(tail):
        return out
    vals, cnt = np.unique(tail, axis=0, return_counts=True)
    fill = vals[cnt.argmax()]
    reach = a[h - 1, :, 3] > 0
    out[h:, reach] = fill
    return out


def pad_sky(a):
    """480×270 的天 → 576×366：四边按边缘那一行 / 列续出去。"""
    return np.pad(a, ((M, M), (M, M), (0, 0)), mode="edge")


STAR_COLORS = [(0x3a, 0x33, 0x52), (0x5a, 0x50, 0x78), (0x8a, 0x7f, 0xae), (0xbf, 0xb4, 0xdc)]


def bake_stars(a, seed=11, count=46, area=(0, 3, 480, 110), dx=0, dy=0):
    """scripts/cloud_stars.gd 的星星（同一个 seed 的分布思路），画成静止的：七成最暗档、三成第二档，十几颗亮一档。"""
    rng = np.random.default_rng(seed)
    n = 0
    while n < count:
        x = rng.uniform(area[0], area[0] + area[2])
        y = area[1] + area[3] * rng.random() ** 1.4
        if x < 300 and y > 78:
            continue
        lv = 0 if rng.random() < 0.7 else 1
        if rng.random() < 0.25:
            lv += 1
        a[int(y) + dy, int(x) + dx, :3] = STAR_COLORS[lv]
        n += 1
    return a


def additive_to_alpha(add, col):
    """叠加混合的一层（加多少 RGB）→ 普通混合：颜色 col，透明度 = 加的量 / (col - 底下大约的亮度)。"""
    base = np.array([70, 48, 70], float)
    amt = add[..., :3].astype(float) * (add[..., 3:4] / 255.0)
    k = (amt / np.maximum(col - base, 20)).max(-1)
    k = np.clip(k, 0, 0.6)
    k = np.round(k * 8) / 8                    # 透明度分档，不出连续渐变
    out = np.zeros(add.shape[:2] + (4,), np.uint8)
    out[..., :3] = col
    out[..., 3] = (k * 255).astype(np.uint8)
    out[k <= 0] = 0
    return out


GLOW = hexc("#e0977e")       # cloud_art.GLOW_C：余晖贴着地平线的暖玫瑰橙


def build_cloud_copies():
    L = {}
    sky = load(CLOUD / "sky.png")
    sky = bake_stars(sky.copy())
    st = load(CLOUD / "streaks.png")[:, :480]
    # streaks 是叠加的几缕亮丝，固定在余晖那一带：直接按叠加算进天里（天不动，丝也就不漂了，差别看不出）
    amt = st[..., :3].astype(int) * (st[..., 3:4].astype(int)) // 255
    sky[..., :3] = np.clip(sky[..., :3].astype(int) + amt, 0, 255)
    L["cs_sky"] = (pad_sky(sky), -M, False)
    wash = load(CLOUD / "wash.png")
    w2 = additive_to_alpha(wash, GLOW)
    w2, y0 = crop_rows(np.pad(w2, ((0, 0), (M, M), (0, 0)), mode="edge"))
    L["cs_wash"] = (w2, y0, False)
    for n in ("high", "spires", "far", "midfar", "mid", "near", "main", "front"):
        a = load(CLOUD / f"{n}.png")
        if n == "spires":
            a[181:] = 0                        # cloud_test 里 180 以下被远处云海挡住（REGION_CAP）
        a, y0 = crop_rows(a)
        if n not in ("high", "spires"):
            a = extend_down(a)
        L["cs_" + n] = (a, y0, True)
    return L


# ====================================================================== 预览合成（仿 cockpit_room.gd 的 _draw_sky）

def put(dst, src, x, y, alpha=1.0):
    x, y = int(round(x)), int(round(y))
    h, w = src.shape[:2]
    H, W = dst.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x].astype(float)
    a = s[..., 3:4] / 255.0 * alpha
    d = dst[y0:y1, x0:x1].astype(float)
    d[..., :3] = d[..., :3] * (1 - a) + s[..., :3] * a
    d[..., 3:4] = np.maximum(d[..., 3:4], a * 255)
    dst[y0:y1, x0:x1] = d.astype(np.uint8)


def put_tile(dst, src, x, y, alpha=1.0):
    w = src.shape[1]
    xx = int(round(x)) % w - w
    while xx < dst.shape[1]:
        put(dst, src, xx, y, alpha)
        xx += w


def render_state(layers_def, imgs, state, t=6.0, extra=None):
    """一个关键帧停住 t 秒后的样子（屏幕 480×270）。layers_def：layers 表；imgs：id → 图。"""
    out = np.zeros((SH, SW, 4), np.uint8)
    bg = state.get("bg", ["#000000", "#000000"])
    c0, c1 = hexc(bg[0]), hexc(bg[1])
    full = SH + 2 * M
    for i in range(10):
        ya = -M + full * i // 10
        yb = -M + full * (i + 1) // 10
        col = c0 + (c1 - c0) * i / 9
        out[max(0, ya):max(0, min(SH, yb)), :, :3] = col.astype(np.uint8)
    out[..., 3] = 255
    keys = list(layers_def.keys())
    ls = sorted(state["layers"], key=lambda e: layers_def[e["id"]].get("z", keys.index(e["id"])))
    for e in ls:
        d = layers_def[e["id"]]
        img = imgs[e["id"]]
        y = e.get("y", d.get("y", 0)) + e.get("vy", 0) * t
        a = e.get("alpha", 1.0)
        if d.get("tile"):
            put_tile(out, img, e.get("speed", 0) * t + d.get("x0", 0), y, a)
        else:
            put(out, img, e.get("x", d.get("x", 0)) + e.get("speed", 0) * t, y, a)
    if extra:
        extra(out)
    return out


def ck_layer(states=None, chen=True, lamp_off=False):
    """驾驶舱剖面（cockpit_back + 物件的当前帧）+ 晨坐在驾驶座（预览用；晨是 art/characters/chen 的原图，不改）。"""
    states = states or {}
    j = json.loads((CK / "cockpit.json").read_text())
    img = np.zeros((150, 330, 4), np.uint8)
    put(img, load(CK / "cockpit_back.png"), 0, 0)
    objs = dict(j["objects"])
    objs.update(NEW_OBJ_JSON)
    for k, o in objs.items():
        st = states.get(k, o.get("default", "default" if k not in NEW_OBJ_JSON else "hidden"))
        if st == "hidden" or "on" in o:
            continue
        p = CK / f"{k}_{st}.png"
        sd = o.get("states", {})
        if not sd and p.exists():
            put(img, load(p), o["px"][0], o["px"][1])
            continue
        f = CK / f"{k}.png"
        if not f.exists():
            continue
        a = load(f)
        fr = sd.get(st, 0) if sd else 0
        fr = fr[0] if isinstance(fr, list) else fr
        put(img, a[:, fr * o["w"]:(fr + 1) * o["w"]], o["px"][0], o["px"][1])
    if chen:
        ch = load(ROOT / "art" / "characters" / "chen" / "chen.png")[:, 0:40]
        ch = ch[:, ::-1]                      # 面朝左（机头）
        put(img, ch, 104 - 20, 128 - 41)
    return img


def compose(sky_img, ck=None, k=2):
    out = sky_img.copy()
    if ck is not None:
        put(out, ck, CK_POS[0], CK_POS[1])
    return np.array(rgba(out).resize((SW * k, SH * k), Image.NEAREST))


NEW_OBJ_JSON: dict = {}


# ====================================================================== 关键帧

def cloud_sea_layers(L, dy=0.0, k=1.0, alpha=None, skip=()):
    """云海一套层：dy = 整体往上 / 下挪（越近挪得越多，k 是近处的倍数）；speed 越近越快（往右卷：船往左飞）。"""
    order = [("cs_high", 0.15, 0.6), ("cs_spires", 0.2, 0.8), ("cs_far", 0.3, 2.0), ("cs_midfar", 0.45, 4.0),
             ("cs_mid", 0.65, 8.0), ("cs_wash", 0.65, 0.0), ("cs_near", 0.85, 14.0), ("cs_main", 1.0, 22.0),
             ("cs_front", 1.2, 34.0)]
    out = []
    for n, depth, sp in order:
        if n in skip:
            continue
        e = {"id": n, "y": L[n][1] + round(dy * (depth ** k)), "speed": sp, "vy": 0}
        if n == "cs_wash":
            e["x"] = -M
        if alpha and n in alpha:
            e["alpha"] = alpha[n]
        out.append(e)
    return out


# ====================================================================== 云层下面：芦苇地远景（art/reed_field/ 的拷贝）+ 草甸 + 云底

RAMP = ["#ecc23e", "#f2cb40", "#f9d847", "#fde67a", "#fef3bf", "#ddf1f5", "#bae2f3", "#95cfee", "#77b9e2"]  # reed_field_art.RAMP
GREEN = ["#a6cf7c", "#b8d98a", "#cbe39c", "#dcecb2", "#ecf4d2", "#e2f2e0", "#c8e8d4", "#addcc6", "#94cfb8"]
RIVER = ["#f6f0a6", "#e9eeae", "#d6eabe", "#c0e3c9", "#aad9cc", "#98d0c9"]
GLINT = ["#fffef6", "#f1fbff"]
REED_LAYERS = ["sky", "streaks", "mtn_far", "mtn_mid", "hills", "mist_hills", "far", "mist_far", "mid", "mid_glints",
               "mist_mid", "isles"]


def build_reed_copies():
    """芦苇地远处那几层（room.json 的 y 照抄）。只读拷贝：芦苇地会话改了图，这里重跑一次就跟上。"""
    d = json.loads((REED / "room.json").read_text())
    ys = {l["id"]: l.get("y", 0) for l in d["layers"]}
    L = {}
    for n in REED_LAYERS:
        a = load(REED / f"{n}.png")
        if n == "sky":
            L["rd_sky"] = (pad_sky(a), -M, False)
            continue
        a, y0 = crop_rows(a)
        L["rd_" + n] = (a, ys[n] + y0, True)
    return L


def vnoise(w, h, sx, sy, seed, wrap=True):
    """平滑噪声（双线性插值的格点随机数），横向按 w 无缝。"""
    rng = np.random.default_rng(seed)
    gw, gh = max(2, int(round(w / sx))), int(np.ceil(h / sy)) + 2
    g = rng.random((gh, gw))
    xs = np.arange(w) / w * gw
    ys = np.arange(h) / sy
    x0 = np.floor(xs).astype(int)
    fx = xs - x0
    y0 = np.floor(ys).astype(int)
    fy = ys - y0
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = g[y0][:, x0 % gw]
    b = g[y0][:, (x0 + 1) % gw]
    c = g[y0 + 1][:, x0 % gw]
    e = g[y0 + 1][:, (x0 + 1) % gw]
    top = a * (1 - fx) + b * fx
    bot = c * (1 - fx) + e * fx
    return top * (1 - fy[:, None]) + bot * fy[:, None]


def meadow(warm=0.0):
    """从高处看下去的草甸（无透视：一条条横带叠下去）。直接用芦苇地自己的 mid / isles 两条（浅水 + 草岛），
    往下叠几遍、每遍横向错开，越往下越近：和芦苇地一个画法、一套颜色。960 宽、左右无缝。"""
    mid = load(REED / "mid.png")
    isl = load(REED / "isles.png")
    mid, _ = crop_rows(mid)
    isl, _ = crop_rows(isl)
    water = {(200, 230, 235), (190, 225, 230), (180, 220, 224)}   # 芦苇地浅水的三档：抠掉，换成往下一直接着变的底
    strips = [(mid, 0), (isl, 333), (isl, 617), (isl, 151), (isl, 805)]
    h = sum(a.shape[0] for a, _ in strips) - 14 * (len(strips) - 1)
    out = np.zeros((h, 960, 4), np.uint8)
    top, bot = np.array([208, 233, 237]), np.array([150, 204, 210])
    for i in range(10):                               # 底：一条条横带，越近（越往下）越青
        out[h * i // 10:h * (i + 1) // 10, :, :3] = (top + (bot - top) * i / 9).astype(np.uint8)
    out[..., 3] = 255
    y = 0
    for a, sx in strips:
        b = np.roll(a, sx, axis=1).copy()
        wm = np.zeros(b.shape[:2], bool)
        for c in water:
            wm |= (b[..., :3] == c).all(-1)
        b[wm] = 0
        put(out, b, 0, y)
        y += b.shape[0] - 14
    if warm:
        out = grade(out, warm)
    return out


DUSK = ["#3e3656", "#5d4f74", "#86708f", "#b48c98", "#d9a39a", "#eebfa2", "#f8dcbc"]


def grade(a, k, sky=False):
    """黄昏调色：按明暗映射到 DUSK 色阶（暗的往靛紫、亮的往桃），亮度整体压一点，再掺回 (1 - k) 的原色。不动透明度。
    sky = 天那张：越往上越暗（靛紫），地平线那边留桃色的余光。"""
    rgb = a[..., :3].astype(float)
    lum = rgb @ np.array([0.3, 0.55, 0.15]) / 255
    q = np.clip((lum - 0.45) / 0.55, 0, 1) ** 1.2 * 0.8
    if sky:
        yy = np.arange(a.shape[0])[:, None] / a.shape[0]
        q = np.clip(q - 0.55 * (1 - yy) ** 1.5, 0, 1)
    ramp = np.array([hexc(c) for c in DUSK])
    f = q * (len(DUSK) - 1)
    i0 = np.floor(f).astype(int)
    i1 = np.minimum(i0 + 1, len(DUSK) - 1)
    t = (f - i0)[..., None]
    t = np.floor(t * 3) / 3                          # 色阶之间也只走三小档（硬边像素）
    g = ramp[i0] * (1 - t) + ramp[i1] * t
    out = g * k + rgb * 0.8 * (1 - k)
    o = a.copy()
    o[..., :3] = np.clip(np.round(out), 0, 255).astype(np.uint8)
    return o


CEIL = ["#8e7fae", "#a796c2", "#c0b2d4", "#d8cde2", "#ece3e4", "#f8eed6", "#fff5d2"]


def ceiling():
    """云层的底：作者 mid.png、midfar.png 上下翻过来叠在一起（midfar 错开半屏，填 mid 的留白），按明暗重新上色成
    被下面的日光照着的淡紫 / 奶白（受光的边翻到了下沿）。"""
    pal = np.array([np.r_[hexc(c), 255] for c in CEIL], np.uint8)

    def recol(a, lift=0):
        op = a[..., 3] > 0
        lum = (a[..., :3].astype(float) @ np.array([0.3, 0.55, 0.15]))
        v = lum[op]
        q = np.clip((lum - np.percentile(v, 3)) / (np.percentile(v, 97) - np.percentile(v, 3)), 0, 1)
        idx = np.clip(np.round(q * (len(CEIL) - 1)).astype(int) - lift, 0, len(CEIL) - 1)
        out = np.zeros_like(a)
        out[op] = pal[idx[op]]
        return out

    mid = recol(load(CLOUD / "mid.png")[::-1])
    mf = recol(np.roll(load(CLOUD / "midfar.png")[::-1], 480, axis=1), lift=1)
    base = np.zeros_like(mid)
    put(base, mf, 0, 14)                             # midfar 那排更远：往上缩一点、暗一档
    put(base, mid, 0, 0)
    a, _ = crop_rows(base)
    top = np.zeros((EXT, a.shape[1], 4), np.uint8)
    top[:] = pal[0]
    return np.concatenate([top, a], 0)


# ====================================================================== 画图小工具

class Cv:
    """一张 RGBA 画布：rect / line / px，颜色是 hex 或 RGB；haze = 往空气色混多少（远处的东西淡）。"""

    def __init__(self, w, h, haze=None, k=0.0):
        self.a = np.zeros((h, w, 4), np.uint8)
        self.w, self.h = w, h
        self.haze = None if haze is None else hexc(haze)
        self.k = k

    def c(self, col):
        c = hexc(col) if isinstance(col, str) else np.asarray(col, float)
        if self.haze is not None:
            c = c * (1 - self.k) + self.haze * self.k
        return np.r_[np.clip(np.round(c), 0, 255), 255].astype(np.uint8)

    def px(self, x, y, col):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = self.c(col)

    def rect(self, x, y, w, h, col):
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(self.w, int(x + w)), min(self.h, int(y + h))
        if x0 < x1 and y0 < y1:
            self.a[y0:y1, x0:x1] = self.c(col)

    def line(self, x0, y0, x1, y1, col):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        e = dx + dy
        while True:
            self.px(x0, y0, col)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * e
            if e2 >= dy:
                e += dy
                x0 += sx
            if e2 <= dx:
                e += dx
                y0 += sy

    def ellipse(self, cx, cy, rx, ry, col, fill=True):
        ys, xs = np.mgrid[0:self.h, 0:self.w]
        d = ((xs + 0.5 - cx) / rx) ** 2 + ((ys + 0.5 - cy) / ry) ** 2
        m = d <= 1 if fill else (d <= 1) & (d > (1 - 1.6 / min(rx, ry)) ** 2)
        self.a[m] = self.c(col)

    def mask(self, m, col):
        self.a[m] = self.c(col)


DIGITS = {"0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
          "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "011", "001", "111"],
          "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
          "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "010", "010", "010"],
          "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"],
          "-": ["000", "000", "111", "000", "000"]}


def text3(cv, x, y, s, col, skip=()):
    """3×5 的小字（船号）；skip = 哪几个像素剥落了（褪色）。"""
    for i, ch in enumerate(s):
        g = DIGITS[ch]
        for r, row in enumerate(g):
            for q, b in enumerate(row):
                if b == "1" and (i, r, q) not in skip:
                    cv.px(x + i * 4 + q, y + r, col)


def reed_tuft(cv, x, base, h, rng, plume=True):
    """一丛芦苇：几根细秆 + 穗（芦苇地的颜色：明黄受光、淡蓝背光）。"""
    stems = ["#dcc66a", "#e0cb6c", "#e8d57a"]
    plumes = ["#bfe1f2", "#fde67a", "#fff4c2"]
    for k in range(int(rng.integers(3, 6))):
        xx = x + int(rng.integers(-3, 4))
        hh = h + int(rng.integers(-3, 3))
        lean = rng.choice([-1, 0, 0, 1])
        for t in range(hh):
            cv.px(xx + (lean if t > hh * 0.6 else 0), base - t, stems[k % 3])
        if plume:
            top = base - hh
            px = xx + lean
            cv.px(px, top, plumes[2])
            cv.px(px, top - 1, plumes[1])
            cv.px(px - 1, top, plumes[1])
            cv.px(px + 1, top + 1, plumes[0])


# ====================================================================== 降落点：西侧旧货场

CONT = {   # 集装箱：受光 / 本色 / 背光 / 楞（都褪色了）
    "rust": ("#d6a688", "#c08a6e", "#a5766a", "#b07c66"),
    "teal": ("#acd0c4", "#8fb9ae", "#779f98", "#84ada3"),
    "ochre": ("#e4cc96", "#d2b67c", "#b99c66", "#c6aa72"),
    "blue": ("#bad4dc", "#9fc0cf", "#86a9ba", "#93b4c4"),
}


def container(cv, x, y, w, h, kind, rng, door=False, moss=0):
    lit, body, shade, rib = CONT[kind]
    cv.rect(x, y, w, h, body)
    cv.rect(x, y, w, 1, lit)                       # 顶受光
    cv.rect(x, y, 1, h, lit)                       # 左受光
    cv.rect(x + w - 1, y, 1, h, shade)
    cv.rect(x, y + h - 1, w, 1, shade)
    for xx in range(x + 2, x + w - 2, 2):          # 瓦楞（实线，一根根竖楞）
        cv.rect(xx, y + 2, 1, h - 3, rib)
    if door:
        cv.rect(x + w - 6, y + 1, 1, h - 2, shade)
        cv.rect(x + w - 4, y + 3, 1, 2, lit)
    # 锈迹往下淌、褪色的斑
    for _ in range(int(w / 7)):
        xx = x + int(rng.integers(2, w - 2))
        ln = int(rng.integers(2, h - 1))
        cv.rect(xx, y + 1, 1, ln, "#b9876c" if kind != "rust" else "#9c6c5c")
    for _ in range(moss):
        xx = x + int(rng.integers(1, w - 3))
        cv.rect(xx, y + h - 2, int(rng.integers(2, 5)), 2, "#a6c98a")
        cv.px(xx + 1, y + h - 3, "#b8d98a")


def freight_yard():
    rng = np.random.default_rng(7)
    cv = Cv(236, 124, haze="#e6f2ee", k=0.22)
    B = 114                                         # 地面（底沿）
    # 1. 半埋在草里的旧运输船（船头朝左、尖的，船号还在）
    hull_t = 80
    for x in range(2, 92):
        u = (x - 2) / 90
        top = hull_t + int(round(max(0.0, 0.16 - u) ** 1.6 * 160))      # 船头往下收成一道弧
        bot = B if u > 0.12 else int(B - 4 + (0.12 - u) * 40)
        cv.rect(x, top, 1, max(0, bot - top), "#8ea5a3")
        cv.px(x, top, "#c4d4cf")
        cv.px(x, top + 1, "#a9bdb8")
    for x in range(14, 90):                         # 船身的板缝（横的实线）+ 一根根肋
        cv.px(x, 93, "#7f9896")
        if x % 13 == 0:
            cv.rect(x, 83, 1, 28, "#82999a")
    cv.rect(10, 99, 80, 1, "#7a9290")
    for x in range(16, 88, 6):                      # 锈往下淌
        cv.rect(x + int(rng.integers(0, 3)), 84, 1, int(rng.integers(3, 12)), "#b98a6e")
    text3(cv, 22, 86, "07-3", "#efe6c8", skip={(1, 2, 1), (2, 0, 1), (3, 4, 0)})
    # 驾驶室 + 桅杆 + 一面破旗
    cv.rect(58, 60, 22, 21, "#9cb2ae")
    cv.rect(58, 60, 22, 1, "#c4d4cf")
    cv.rect(58, 60, 1, 21, "#bccdc8")
    cv.rect(79, 60, 1, 21, "#7d9693")
    cv.rect(56, 58, 26, 2, "#86a09d")
    cv.rect(56, 58, 26, 1, "#b0c2bd")
    for i in range(3):
        cv.rect(61 + i * 6, 64, 4, 4, "#5f7774")
        cv.px(61 + i * 6, 64, "#7d9693")
    cv.rect(64, 72, 3, 8, "#6a8380")
    cv.rect(70, 30, 1, 28, "#7d8f8c")
    cv.rect(66, 36, 9, 1, "#7d8f8c")
    for i, (dx, dy) in enumerate(((1, 0), (2, 0), (3, 1), (4, 1), (5, 2), (1, 1), (2, 1), (3, 2))):
        cv.px(70 + dx, 31 + dy, "#d9b38f" if i < 5 else "#c99c80")
    # 2. 龙门吊：两条腿（两根立柱 + 一格格交叉撑）、桁架横梁、小车、吊钩，褪了色的锈红
    cr, crl, crd = "#b98a74", "#d2a88f", "#9a7264"
    for lx in (128, 194):
        cv.rect(lx - 3, 44, 1, B - 44, crl)
        cv.rect(lx + 3, 44, 1, B - 44, crd)
        for y in range(48, B - 4, 9):
            cv.line(lx - 2, y, lx + 2, y + 8, cr)
            cv.line(lx + 2, y, lx - 2, y + 8, cr)
            cv.rect(lx - 2, y, 5, 1, cr)
    cv.rect(118, 38, 92, 2, crl)
    cv.rect(118, 45, 92, 1, crd)
    for x in range(120, 206, 6):                    # 桁架斜撑（实线）
        cv.line(x, 40, x + 3, 44, cr)
        cv.line(x + 3, 44, x + 6, 40, cr)
    cv.rect(156, 46, 8, 4, "#8f7468")              # 小车
    cv.rect(156, 46, 8, 1, crl)
    cv.rect(159, 50, 1, 26, "#7a6b66")             # 钢缆
    cv.rect(157, 76, 5, 2, "#8f7468")
    cv.px(158, 78, "#7a6b66")
    cv.px(159, 79, "#7a6b66")
    # 3. 集装箱堆：左边一垛三层（顶上插着标记），吊车底下两垛
    container(cv, 92, 104, 30, 10, "rust", rng, door=True, moss=3)
    container(cv, 94, 94, 26, 10, "teal", rng)
    container(cv, 98, 84, 22, 10, "ochre", rng, door=True)
    container(cv, 138, 104, 28, 10, "blue", rng, moss=2)
    container(cv, 142, 94, 22, 10, "rust", rng, door=True)
    container(cv, 168, 104, 22, 10, "ochre", rng, moss=4)
    # 4. 褪色的标记：箱子顶上一根杆子、一块方牌（颜色快褪没了，一角翻起来）
    cv.rect(109, 62, 1, 22, "#8a8580")
    cv.px(108, 83, "#8a8580")
    cv.px(110, 83, "#8a8580")
    cv.rect(103, 53, 12, 10, "#e9d4ae")
    cv.rect(104, 54, 10, 8, "#e3bf96")
    cv.rect(106, 56, 6, 4, "#efdcb8")
    cv.rect(103, 53, 12, 1, "#f3e6cc")
    cv.px(114, 53, "#c9b392")
    cv.px(113, 53, "#d8c4a2")
    cv.px(114, 54, "#c9b392")
    # 5. 矮棚子（瓦楞顶，门开着一条缝）
    cv.rect(206, 90, 28, 24, "#c7cfc2")
    cv.rect(206, 90, 1, 24, "#dde3d4")
    cv.rect(233, 90, 1, 24, "#a6b2a6")
    for x in range(204, 236):
        cv.px(x, 88 + (1 if x % 3 == 0 else 0), "#a99a88")
        cv.px(x, 89, "#bba98f")
    cv.rect(214, 98, 8, 16, "#8a958c")
    cv.rect(221, 98, 1, 16, "#6f7a72")
    cv.rect(225, 95, 5, 4, "#8a958c")
    # 6. 草：一条软软的草带盖住底沿，物体底下压暗一档；芦苇只零星几丛
    for x in range(0, 236):
        h = 3 + int(3 * vn1(x, 3))
        cv.rect(x, B - h, 1, h, "#cfe3b0" if (x * 7) % 11 else "#dcecb2")
        cv.px(x, B - h, "#e8f0c8")
        if (x // 3) % 4 == 0:
            cv.px(x, B - h - 1, "#e2edc0")
    for x in (8, 41, 84, 125, 133, 181, 199, 230):
        reed_tuft(cv, x + int(rng.integers(0, 4)), B - 2, int(rng.integers(7, 12)), rng)
    return cv.a


def vnf(x, y):
    return 0.5 + 0.25 * np.sin(x * 0.21 + y * 0.9) + 0.25 * np.sin(x * 0.067 - y * 0.31 + 1.3)


def vn1(x, seed):
    return float(np.sin(x * 0.37 + seed) * 0.5 + np.sin(x * 0.11 + seed * 2) * 0.5) * 0.5 + 0.5


# ====================================================================== 降落点：东侧低鸣

LEAF = ["#e6f1c4", "#dcecb2", "#cbe39c", "#b8d98a", "#a6cf7c"]     # 受光 → 背光（reed_field_art.BIGTREE_LEAF 加一档高光）
BIRD = ["#5e6a80", "#6f7a8e", "#8c96a6"]


def crown(cv, cx, cy, rx, ry, rng, n=9):
    """一团软软的树冠：很多小圆叠成一团（边是一个个鼓包），明暗按整团算（左上亮、右下暗），
    每个小圆自己左上再亮半档：读得出是一簇簇叶子，又是一整团。"""
    blobs = []
    for _ in range(n * 2):
        a = rng.uniform(0, 2 * np.pi)
        r = rng.uniform(0.2, 0.75) ** 0.7
        blobs.append((cx + np.cos(a) * rx * r * 0.85, cy + np.sin(a) * ry * r * 0.8, rx * rng.uniform(0.24, 0.4),
                      ry * rng.uniform(0.28, 0.45)))
    blobs.append((cx, cy, rx * 0.7, ry * 0.7))
    ys, xs = np.mgrid[0:cv.h, 0:cv.w]
    lvl = np.full((cv.h, cv.w), -1.0)
    for bx, by, brx, bry in sorted(blobs, key=lambda b: b[1]):
        d = ((xs + 0.5 - bx) / brx) ** 2 + ((ys + 0.5 - by) / bry) ** 2
        m = d <= 1
        g = ((xs + 0.5 - cx) / rx + (ys + 0.5 - cy) / ry) * 0.5          # 整团：左上 -1 .. 右下 +1
        loc = ((xs + 0.5 - bx) / brx + (ys + 0.5 - by) / bry) * 0.5      # 小圆自己
        v = 1.9 + g * 1.9 + np.where(loc < -0.35, -0.8, np.where(loc > 0.45, 0.6, 0.0))
        lvl = np.where(m, v, lvl)
    f = lvl >= 0
    idx = np.clip(np.round(lvl), 0, len(LEAF) - 1).astype(int)
    for i, col in enumerate(LEAF):
        cv.mask(f & (idx == i), col)


def east_slope():
    rng = np.random.default_rng(12)
    cv = Cv(236, 124, haze="#e6f2ee", k=0.18)
    B = 114
    # 缓坡
    xs = np.arange(236)
    top = B - 30 * np.exp(-((xs - 132) / 62.0) ** 2) - 3
    gpal = ["#eaf3cf", "#dcecb2", "#cfe3a2", "#c2db96", "#d8e6a6"]
    for x in xs:
        t = int(top[x])
        for y in range(t, B):
            k = (y - t)
            band = 0 if k == 0 else 1 if k < 3 else 2 if (y + x // 9) % 7 else 3
            if (x * 3 + y * 5) % 17 == 0 and k > 3:
                band = 4
            col = gpal[band]
            if vnf(x, y) > 0.78 and k > 1:
                col = "#f6e48e" if k % 3 else "#fbeeb0"
            cv.px(x, y, col)
    # 坡上的草被风（还是那个声音？）压成一道道往右的弯
    for x in range(40, 220, 5):
        t = int(top[x])
        for j in range(3):
            cv.px(x + j, t - 1 + j // 2, "#e8f0c8")
    # 树：一棵大树长在坡上，根部压一道阴影
    tx = 146
    tb = int(top[tx]) + 1
    cv.rect(tx - 2, tb - 24, 4, 24, "#9fc4ad")
    cv.rect(tx - 2, tb - 24, 1, 24, "#b8d4c0")
    cv.rect(tx + 1, tb - 24, 1, 24, "#86ad98")
    cv.px(tx - 3, tb - 1, "#9fc4ad")
    cv.px(tx + 2, tb - 1, "#86ad98")
    cv.line(tx - 1, tb - 16, tx - 9, tb - 24, "#9fc4ad")
    cv.line(tx + 1, tb - 14, tx + 10, tb - 22, "#86ad98")
    crown(cv, tx, tb - 34, 26, 17, rng, n=16)
    for x in range(tx - 12, tx + 16):
        cv.px(x, int(top[x]), "#b9d79a")
    # 坡脚的浅水，水面上一圈圈往外的波纹（实线的椭圆弧，越外越淡）
    cv.ellipse(52, 110, 38, 5.0, "#a9d9d6")
    cv.ellipse(52, 109.5, 34, 3.4, "#bfe3e3")
    for r, col in ((7, "#fbfef9"), (14, "#f0faf6"), (22, "#e2f5f1"), (30, "#d4eeea")):
        for x in range(int(52 - r), int(52 + r) + 1):
            u = (x + 0.5 - 52) / r
            if abs(u) > 1:
                continue
            y = 110 - 2.2 * np.sqrt(1 - u * u) * (r / 29) - 0.5
            cv.px(x, int(round(y)), col)
            y2 = 110 + 1.6 * np.sqrt(1 - u * u) * (r / 29)
            if r > 7:
                cv.px(x, int(round(y2)), col)
    # 惊起的鸟：从树那边飞起来，越高越小
    for i, (bx, by, s) in enumerate(((182, 30, 2), (192, 22, 2), (174, 18, 1), (204, 14, 1), (188, 8, 1))):
        c0, c1, c2 = BIRD
        cv.px(bx, by, c1)
        cv.px(bx - 1, by - (i % 2), c0)
        cv.px(bx + 1, by - (i % 2), c0)
        if s > 1:
            cv.px(bx - 2, by - 1 + (i % 2), c2)
            cv.px(bx + 2, by - 1 + (i % 2), c2)
    # 前面的草带 + 几丛芦苇
    for x in range(0, 236):
        h = 2 + int(3 * vn1(x, 7))
        cv.rect(x, B - h, 1, h, "#cfe3b0" if (x * 7) % 11 else "#dcecb2")
        cv.px(x, B - h, "#e8f0c8")
    for x in (6, 30, 88, 104, 196, 222):
        reed_tuft(cv, x + int(rng.integers(0, 4)), B - 2, int(rng.integers(7, 12)), rng)
    return cv.a


# ====================================================================== 云散开：两岸云 + 缺口下面的日光

WARM = ["#f6dcae", "#e9b98f", "#c98f86"]       # 缺口那边的边：下面的日光照上来（亮 → 暗）


def cloud_bank(side, seed):
    """一岸云（像作者 near / mid 那样一团团的积云顶），朝缺口那边（side = 'l' 是左岸、缺口在它右边）的边是一串大小不一、
    不带身体的圆团从上到下鼓出去（软的、一团团的边，不是一刀切的竖墙）；离缺口近的几像素被下面的日光照成暖桃色、
    再往里一点映一层淡淡的紫粉。Field 画在一张更宽的图中间（Field 横向是卷的），再裁出来。"""
    W2, H2 = 720, 230
    F = ca.Field(W2, H2)
    rng = np.random.default_rng(seed)
    x0, x1 = 180, 540                                # 云岸在宽图里的范围
    edge = x1 if side == "l" else x0
    sgn = 1 if side == "l" else -1                   # 往缺口去的方向

    def dist(x):                                      # 离缺口那条线多远（往岸里为正）
        return (edge - x) * sgn

    for k, (base, sc, sq, z) in enumerate(((66, 15, 0.62, 0), (90, 19, 0.66, 30), (116, 23, 0.7, 60))):
        F.new_group()
        F.row += 1
        x = x0 - 30 if side == "l" else x1 + 30
        while dist(x) > 0:
            r = sc * rng.uniform(0.6, 1.3)
            if dist(x) > r + 10:
                F.cauli(x, base + rng.uniform(-3, 3) + r * sq, r, z + rng.uniform(-1, 1), rng, sq, depth=2,
                        kids=(2, 5), ks=(0.3, 0.55), rmin=2.0, ref=base - 6, unit=sc * sq * 1.6)
            x += sgn * r * rng.uniform(1.0, 1.6)
    # 缺口那条边：从上到下一串圆团，往外鼓的多少不一样
    y = 58.0
    F.new_group()
    F.row += 1
    while y < H2 + 10:
        r = rng.uniform(9, 17)
        out = rng.uniform(-4, 7)
        ex = edge - sgn * (r * 0.9 + 10) + sgn * out
        F.cauli(ex, y, r, 70 + rng.uniform(0, 6), rng, 0.85, depth=2, kids=(2, 4), ks=(0.3, 0.5), rmin=2.0,
                body=False, spread=(-200, 20) if side == "l" else (-200, 20), ref=58, unit=40)
        # 往岸里补一颗大的，接上后面的云身（不留洞）
        F.ball(ex - sgn * r * 1.2, y + 2, r * 1.3, r * 1.0, 40, body=True, ref=58, unit=40)
        y += r * rng.uniform(0.9, 1.3)
    pal = ca.cloud_pal(0.10, 0.40, 6, C_lo=0.045, C_hi=0.08, h_lo=286, h_hi=346)
    a = F.render(pal, body=2, rim=(1.5, 3.0), crease=2.0, bands=(0.8, 1.8), run_bands=(8, 20))
    a = a[:, x0 - 50:x1 + 50].copy()
    # 朝缺口的那条边：每行最靠缺口的像素往里 0..9 像素：暖桃 → 粉 → 往紫粉里淡
    op = a[..., 3] > 0
    warm = [hexc(c) for c in WARM]
    lil = hexc("#a98aa6")
    for yy in range(a.shape[0]):
        xs = np.where(op[yy])[0]
        if not len(xs) or yy < 40:
            continue
        e = xs.max() if side == "l" else xs.min()
        for d in range(15):
            x = e - d * sgn
            if not (0 <= x < a.shape[1]) or not op[yy, x]:
                break
            if d == 0:
                a[yy, x, :3] = warm[0]
            elif d <= 2:
                a[yy, x, :3] = warm[1]
            elif d <= 5:
                a[yy, x, :3] = warm[2]
            else:
                t = 0.5 if d <= 8 else 0.32 if d <= 11 else 0.16
                a[yy, x, :3] = (a[yy, x, :3] * (1 - t) + lil * t).astype(np.uint8)
    a, y0 = crop_rows(a)
    return extend_down(a, 80), y0


def gap_light():
    """缺口下面：远远的芦苇地（明黄淡蓝）+ 往上冒的一片暖光。不 tile，576 宽，一条条横带（不抖动）。"""
    w, h = SW + 2 * M, 200
    out = np.zeros((h, w, 4), np.uint8)
    # 上沿贴着云岸的顶：先是暗紫粉（云海里），几像素里亮成桃色、奶黄（光从下面冒上来）
    stops = [(0, "#c98f96"), (10, "#e9b39a"), (20, "#f6d6ac"), (32, "#fff6cf"), (52, "#fdeeb4"),
             (70, "#e9f2df"), (90, "#cde9f4"), (200, "#a9d6ea")]
    for y in range(h):
        for i in range(len(stops) - 1):
            if stops[i][0] <= y < stops[i + 1][0]:
                t = (y - stops[i][0]) / (stops[i + 1][0] - stops[i][0])
                t = np.floor(t * 4) / 4
                c = hexc(stops[i][1]) * (1 - t) + hexc(stops[i + 1][1]) * t
                out[y, :, :3] = c.astype(np.uint8)
    out[..., 3] = 255
    # 远处的地：芦苇地自己的浅水 + 草岛（meadow），往天的颜色里淡一层（很远、隔着光）
    m = meadow()
    haze = hexc("#f4f0d8")
    mm = m.copy()
    mm[..., :3] = (m[..., :3] * 0.62 + haze * 0.38).astype(np.uint8)
    put(out, np.tile(mm, (1, 2, 1))[:, :w], 0, 66)
    # 上沿 18 像素：光往上冒进紫色的夜里，透明度 4 档（.25 / .5 / .75 / 1），不是一道硬边
    for y in range(18):
        out[y, :, 3] = int(255 * (np.floor((y + 1) / 18 * 4) / 4 if y < 17 else 1))
    return out


# ====================================================================== 大象（占位：极淡的剪影，等美术姐的图直接换同名文件）

def elephant_sil(w, h, col, alpha, flip=False):
    """一只大象的剪影（侧面、朝左）：身子、头、垂下来的鼻子、贴在头后面的耳朵（左耳一个缺口）、四条腿。
    只是占位：颜色一种、透明度很低。"""
    cv = Cv(w, h)
    sx, sy = w / 44.0, h / 28.0
    E = lambda cx, cy, rx, ry: cv.ellipse(cx * sx, cy * sy, rx * sx, ry * sy, col)  # noqa: E731
    E(25, 13, 14, 9)            # 身子
    E(12, 10, 7, 7)             # 头
    E(15, 9, 5, 6)              # 耳朵
    for lx in (16, 21, 30, 35):  # 腿
        cv.rect(round((lx - 2) * sx), round(17 * sy), max(2, round(4 * sx)), round(11 * sy), col)
    for t in range(14):          # 鼻子：从头往下垂，末端往外卷
        x = 7 - t * 0.12 + (1.5 if t > 11 else 0)
        y = 13 + t * 0.9
        cv.rect(round((x - 1.2) * sx), round(y * sy), max(1, round(2.6 * sx)), max(1, round(1.2 * sy)), col)
    # 耳朵上的缺口
    cv.a[round(6 * sy):round(8 * sy), round(18 * sx):round(20 * sx)] = 0
    a = cv.a
    a[..., 3] = (a[..., 3] > 0) * int(alpha * 255)
    return a[:, ::-1] if flip else a


# ====================================================================== 关键帧（sky_final.json）

BG_NIGHT = ["#120c1e", "#2a1d33"]
BG_DAY = ["#cfe8f2", "#e9f4ee"]
BG_DUSK = ["#9c8bb0", "#f0c4a2"]


def build_all():
    """所有新图：{id: (图, 默认 y, tile)}。"""
    L = build_cloud_copies()
    L.update(build_reed_copies())
    L["fc_meadow"] = (meadow(), 0, True)
    c = ceiling()
    L["fc_ceiling"] = (c, 0, True)
    bl, yl = cloud_bank("l", 3)
    br, yr = cloud_bank("r", 5)
    L["fc_bank_l"] = (bl, yl, False)
    L["fc_bank_r"] = (br, yr, False)
    L["fc_gap"] = (gap_light(), 0, False)
    L["fc_yard"] = (freight_yard(), 0, False)
    L["fc_east"] = (east_slope(), 0, False)
    tf = load(TOWN / "town_far.png")
    tf[227:] = 0                                     # 塔脚下那条暗的底座不要：塔脚埋进近处的云里
    tf, ty = crop_rows(tf)
    L["fc_town_far"] = (tf, ty, False)
    # 黄昏（结局一停在芦苇地上：e1_evening 天变 dusk 以后回驾驶舱发消息）
    for n in REED_LAYERS:
        a, y0, t = L["rd_" + n]
        L["rk_" + n] = (grade(a, 0.8, sky=n == "sky"), y0, t)
    L["fk_meadow"] = (meadow(warm=0.8), 0, True)
    L["fk_yard"] = (grade(freight_yard(), 0.8), 0, False)
    L["fc_elephant_far"] = (elephant_sil(22, 14, "#5d4a68", 0.5), 0, False)
    L["fc_elephant_shadow"] = (elephant_sil(132, 84, "#0c0814", 0.36), 0, False)
    return L


Z = ["cs_sky", "rd_sky", "rk_sky", "cs_high", "rd_streaks", "rk_streaks", "fc_ceiling", "cs_spires",
     "rd_mtn_far", "rk_mtn_far", "rd_mtn_mid", "rk_mtn_mid", "cs_far", "fc_elephant_shadow", "rd_hills", "rk_hills",
     "rd_mist_hills", "rk_mist_hills", "cs_midfar", "rd_far", "rk_far", "rd_mist_far", "rk_mist_far", "fc_elephant_far",
     "fc_town_far", "cs_mid", "cs_wash", "rd_mid", "rk_mid", "rd_mid_glints", "rk_mid_glints", "rd_mist_mid",
     "rk_mist_mid", "rd_isles", "rk_isles", "fc_meadow", "fk_meadow", "fc_yard", "fk_yard", "fc_east", "fc_gap",
     "fc_bank_l", "fc_bank_r", "cs_near", "cs_main", "cs_front"]


def states(L):
    def lay(n, **kw):
        e = {"id": n, "y": L[n][1], "speed": 0, "vy": 0}
        e.update(kw)
        return e

    sky = lay("cs_sky", x=-M, y=-M)
    S = {}
    # 1. 云层星的云海：作者 cloud_test 那一片，余晖在左边地平线上（窗里正好看见），船在云顶上面平稳地飞
    S["cloud_sea"] = {"blend": 3.0, "bg": BG_NIGHT, "layers": [sky] + cloud_sea_layers(L)}
    # 2. 下降航标：船往下沉，云海整片往上来（近的上来得多），慢慢还在沉；两岸云已经在近处云下面垫着（还合着）
    low = cloud_sea_layers(L, dy=-26, k=1.2)
    for e in low:
        e["vy"] = -0.6 if e["id"] not in ("cs_high", "cs_spires") else -0.2
    S["cloud_low"] = {"blend": 4.0, "bg": BG_NIGHT, "layers": [sky] + low + [
        lay("fc_bank_l", x=-170, y=122, speed=0), lay("fc_bank_r", x=150, y=122, speed=0)]}
    # 3. 云散开：近处的云顶淡掉，露出两岸云往左右分开，缺口下面是远远的芦苇地和往上冒的光
    part = cloud_sea_layers(L, dy=-26, k=1.2)
    for e in part:
        if e["id"] in ("cs_near", "cs_main", "cs_front"):
            e["alpha"] = 0.0
            e["y"] -= 30
    S["cloud_part"] = {"blend": 3.5, "bg": BG_NIGHT, "layers": [sky] + part + [
        lay("fc_gap", x=-M, y=154),
        lay("fc_bank_l", x=-420, y=122, speed=0, vy=-0.5), lay("fc_bank_r", x=176, y=122, speed=0, vy=-0.5)]}
    # 4. 三个降落点。西 / 东：从缺口下去，云层在头顶，下面是白天的芦苇地，降落点在机头前面（左边），地面慢慢上来
    def land(site):
        ls = [lay("rd_sky", x=-M, y=-M)]
        for n, sp in (("rd_streaks", 1), ("rd_mtn_far", 0.4), ("rd_mtn_mid", 0.8), ("rd_hills", 1.6),
                      ("rd_mist_hills", 2), ("rd_far", 3), ("rd_mist_far", 3.5), ("rd_mid", 4.5), ("rd_mid_glints", 4.5),
                      ("rd_mist_mid", 5.5), ("rd_isles", 7)):
            ls.append(lay(n, y=L[n][1] - 8, speed=sp, vy=-0.4))
        ls.append(lay("fc_meadow", y=172, speed=12, vy=-0.8))
        ls.append(lay("fc_ceiling", y=-L["fc_ceiling"][0].shape[0] + 58, speed=4, vy=-1.5))
        ls.append(lay(site, x=-26, y=62, speed=2.5, vy=-0.6))
        return ls
    S["land_west"] = {"blend": 2.2, "bg": BG_DAY, "layers": land("fc_yard")}
    S["land_east"] = {"blend": 2.2, "bg": BG_DAY, "layers": land("fc_east")}
    # 居民区：不下去，贴着云顶往小镇滑过去；夜里，风车尖塔一排排从云海上冒出来
    town = cloud_sea_layers(L, dy=-40, k=1.2)
    S["land_town"] = {"blend": 2.5, "bg": BG_NIGHT, "layers": [sky] + town + [
        lay("fc_town_far", x=-520, y=L["fc_town_far"][1] - 52, speed=6, vy=-0.5)]}
    # 5. 结局一：停在芦苇地上，黄昏（e1_phone 回驾驶舱前先切到这里，黑屏里直接到位）
    def dusk():
        ls = [lay("rk_sky", x=-M, y=-M)]
        for n, sp in (("rk_streaks", 1), ("rk_mtn_far", 0), ("rk_mtn_mid", 0), ("rk_hills", 0), ("rk_mist_hills", 0.4),
                      ("rk_far", 0), ("rk_mist_far", 0.6), ("rk_mid", 0), ("rk_mid_glints", 0), ("rk_mist_mid", 0.8),
                      ("rk_isles", 0)):
            ls.append(lay(n, y=L[n][1] - 22, speed=sp))
        ls.append(lay("fk_meadow", y=200, speed=0))
        ls.append(lay("fk_yard", x=300, y=86, speed=0))
        return ls
    S["yard_parked"] = {"blend": 2.0, "bg": BG_DUSK, "layers": dusk()}
    # 远处的大象（剧本 e1_phone：晨转头看窗外）：小山上一只，占位剪影（等美术姐），4 档淡进来
    S["yard_elephant_far"] = {"blend": 2.5, "bg": BG_DUSK, "layers": dusk() + [
        lay("fc_elephant_far", x=126, y=110)]}
    # 6. 结局四：安全漂行轨道，升到云海上面很高的地方，云海沉到画面下面、慢慢漂
    orbit = cloud_sea_layers(L, dy=100, k=1.0, skip=("cs_main", "cs_front"))
    for e in orbit:
        e["speed"] = round(e["speed"] * 0.3, 2)
    S["cloud_orbit"] = {"blend": 5.0, "bg": ["#0b0714", "#221830"], "layers": [sky] + orbit}
    # 一个很大的影子从远处的云海上走过去（剧本 e4_write 的 sky shadow_pass；占位剪影，等美术姐）
    S["elephant_shadow"] = {"blend": 2.0, "bg": ["#0b0714", "#221830"], "layers": [sky] + orbit + [
        lay("fc_elephant_shadow", x=-30, y=94, speed=9)]}
    return S


def sky_json(L, S):
    layers = {}
    for n in Z:
        if n in L:
            d = {"img": n + ".png", "z": 1000 + Z.index(n)}
            if L[n][2]:
                d["tile"] = True
            layers[n] = d
    return {"_note": "tools/cockpit_final_art.py 生成，别手改。终章（final）的窗外关键帧；格式和 sky.json 一样"
                     "（docs/flight_sky_contract.md），引擎把这里的 layers / states 合进 sky.json（只加 sky.json 里没有的名字）。"
                     "z 从 1000 起：和 flight1 的层不混。大象两张（fc_elephant_far / fc_elephant_shadow）是占位，"
                     "美术姐的图直接换同名文件。",
            "layers": layers, "states": S}


# ====================================================================== 驾驶舱补件（剧本 story_final.json 要、flight1 没有的物件）
# 都按舱里的光画：室内很暗（纸是 #6a6b5f 那一档，不是白），朝窗（左）那边亮一档。坐标 = cockpit_back.png 的像素。

WOOD = ["#4a3826", "#3a2a1c", "#322215", "#291e16", "#1d150d", "#120d07"]   # 木柜：受光 → 柜里最暗
PAPER = ["#7c7c6c", "#6a6b5f", "#5e5f53", "#51534b"]
INK = "#2a2e34"
TAPE = "#4f4d3e"
BRASS = ["#7a6a44", "#5c4f34"]
GLASS = ["#86aaa0", "#4f7a74", "#3a5a56"]
METAL = ["#7e8882", "#66706a", "#4a524d", "#343b37"]
CANVAS = ["#525a42", "#454c37", "#383e2d", "#2c3124"]
CRAYON = {"ele": "#5f6a78", "ele_d": "#4d5664", "sky": "#4e6766", "grass": "#56664a", "sun": "#8a7448"}
SCR = {"bg": "#02130c", "dim": "#2e513b", "hi": "#65936e", "edge": "#000d08"}

NEW_OBJ: dict = {}          # id → dict(px, w, h, frames: [(state, 图)], default, note)


def frame(w, h):
    return Cv(w, h)


def obj(name, px, frames, default=None, layer=None):
    w = frames[0][1].w
    h = frames[0][1].h
    NEW_OBJ[name] = {"px": px, "w": w, "h": h, "frames": frames, "default": default, "layer": layer}


# ---------- 燃料柜：右边那只木柜（cockpit_back 里 x 223..247、y 111..127）的门，里面一格格放着纪念品
def cabinet():
    W_, H_ = 34, 20
    ox, oy = 5, 2                                    # 柜子本身在图里的左上（图左上角 = 剖面 218, 108 → 柜子 223, 110）
    cw, ch = 25, 18

    def body(cv):
        cv.rect(ox, oy, cw, ch, WOOD[2])
        cv.rect(ox, oy, cw, 1, WOOD[0])                  # 顶板受光
        cv.rect(ox, oy + 1, cw, 1, WOOD[1])
        cv.rect(ox, oy, 1, ch, WOOD[1])
        cv.rect(ox + cw - 1, oy, 1, ch, WOOD[4])
        cv.rect(ox + 1, oy + ch - 1, cw - 2, 1, WOOD[4])

    def inside(cv, items):
        x0, y0, x1, y1 = ox + 2, oy + 2, ox + cw - 2, oy + ch - 1
        cv.rect(x0, y0, x1 - x0, y1 - y0, WOOD[5])
        # 两排三列的格子（隔板是受光的木条）
        for gx in (x0 + 7, x0 + 14):
            cv.rect(gx, y0, 1, y1 - y0, WOOD[3])
        cv.rect(x0, y0 + 7, x1 - x0, 1, WOOD[3])
        cv.rect(x0, y0 + 8, x1 - x0, 1, WOOD[4])
        cells = [(x0 + 1, y0 + 1), (x0 + 8, y0 + 1), (x0 + 15, y0 + 1), (x0 + 1, y0 + 9), (x0 + 8, y0 + 9), (x0 + 15, y0 + 9)]
        for (cx, cy), it in zip(cells, items):
            draw_item(cv, cx, cy, it)

    def door(cv, x, w):
        cv.rect(x, oy + 1, w, ch - 1, WOOD[1])
        cv.rect(x, oy + 1, 1, ch - 1, WOOD[0])
        cv.rect(x + w - 1, oy + 1, 1, ch - 1, WOOD[3])
        cv.rect(x + 1, oy + 4, max(1, w - 2), 1, WOOD[2])
        cv.rect(x + 1, oy + ch - 5, max(1, w - 2), 1, WOOD[2])

    frames = []
    # closed：两扇门关着，中间一道缝，一个铜搭扣
    c = frame(W_, H_)
    body(c)
    c.rect(ox + 2, oy + 2, cw - 4, ch - 3, WOOD[2])
    for x0 in (ox + 2, ox + 13):
        c.rect(x0, oy + 2, 10, ch - 3, WOOD[1])
        c.rect(x0, oy + 2, 10, 1, WOOD[0])
        c.rect(x0, oy + 2, 1, ch - 3, WOOD[0])
        c.rect(x0 + 2, oy + 5, 6, ch - 9, WOOD[2])        # 门芯板凹进去一档
        c.rect(x0 + 2, oy + 5, 6, 1, WOOD[3])
    c.rect(ox + 12, oy + 2, 1, ch - 3, WOOD[5])
    c.rect(ox + 11, oy + 8, 3, 2, BRASS[0])
    c.px(ox + 13, oy + 9, BRASS[1])
    frames.append(("closed", c))
    full = ["bottle", "seed", "musicbox", "film", "papers", "roll"]
    # open：两扇门往两边打开（侧着看只剩一条窄板），里面六格
    c = frame(W_, H_)
    body(c)
    inside(c, ["empty", "seed", "musicbox", "film", "papers", "roll"])
    door(c, 0, 4)
    door(c, ox + cw + 1, 3)
    frames.append(("open", c))
    # hand：手搭在门上没拉开——左门开一条缝，右门还关着
    c = frame(W_, H_)
    body(c)
    inside(c, ["empty", "seed", "musicbox", "film", "papers", "roll"])
    c.rect(ox + 13, oy + 2, 10, ch - 3, WOOD[1])
    c.rect(ox + 13, oy + 2, 10, 1, WOOD[0])
    c.rect(ox + 13, oy + 2, 1, ch - 3, WOOD[0])
    c.rect(ox + 15, oy + 5, 6, ch - 9, WOOD[2])
    c.rect(ox + 6, oy + 2, 7, ch - 3, WOOD[1])           # 左门半开：斜着变窄
    c.rect(ox + 6, oy + 2, 1, ch - 3, WOOD[0])
    c.rect(ox + 8, oy + 5, 3, ch - 9, WOOD[2])
    c.rect(ox + 12, oy + 8, 2, 2, BRASS[0])
    frames.append(("hand", c))
    # empty_bottle：河水倒进去了，空瓶放回第一格，标签还在
    c = frame(W_, H_)
    body(c)
    inside(c, ["empty_bottle", "seed", "musicbox", "film", "papers", "roll"])
    door(c, 0, 4)
    door(c, ox + cw + 1, 3)
    frames.append(("empty_bottle", c))
    # put_back：东西一件件放回去、摆整齐（剩下的都在）
    c = frame(W_, H_)
    body(c)
    inside(c, ["bottle", "seed", "musicbox", "film", "papers", "roll"])
    door(c, 0, 4)
    door(c, ox + cw + 1, 3)
    for x in range(ox + 3, ox + cw - 3):                # 擦过的柜沿亮一点
        c.px(x, oy + 1, WOOD[0])
    frames.append(("put_back", c))
    obj("cockpit_cabinet", (218, 108), frames, default="hidden")


def draw_item(cv, x, y, it):
    """燃料柜一格里的东西（6×6 像素以内）。"""
    if it == "bottle" or it == "empty_bottle":
        full = it == "bottle"
        cv.rect(x + 2, y, 2, 1, METAL[2])                # 盖
        cv.rect(x + 1, y + 1, 4, 5, GLASS[2])
        if full:
            cv.rect(x + 1, y + 3, 4, 3, GLASS[1])
        cv.px(x + 1, y + 1, GLASS[0])
        cv.px(x + 1, y + 2, GLASS[0])
        cv.rect(x + 2, y + 3, 2, 2, PAPER[1])            # 标签
        cv.px(x + 2, y + 3, PAPER[0])
    elif it == "seed":
        cv.rect(x + 1, y + 2, 4, 4, "#2d3a33")           # 小玻璃罐
        cv.px(x + 2, y + 3, "#9fb98a")                   # 种子：一点淡淡的光
        cv.px(x + 3, y + 4, "#7f9a70")
        cv.px(x + 1, y + 2, "#4a5a50")
    elif it == "musicbox":
        cv.rect(x, y + 2, 6, 4, "#4a3628")
        cv.rect(x, y + 2, 6, 1, "#5c4532")
        cv.px(x + 4, y + 3, BRASS[0])                    # 铜把手
        cv.px(x + 5, y + 4, BRASS[1])
    elif it == "film":
        cv.rect(x + 1, y + 1, 5, 5, METAL[3])
        cv.rect(x + 2, y + 2, 3, 3, METAL[2])
        cv.px(x + 3, y + 3, METAL[3])
        cv.px(x + 1, y + 1, METAL[1])
    elif it == "papers":
        cv.rect(x, y + 3, 6, 3, PAPER[2])                # 明信片、照片、座位图一叠
        cv.rect(x + 1, y + 2, 5, 1, PAPER[1])
        cv.rect(x, y + 3, 6, 1, PAPER[0])
        cv.px(x + 2, y + 4, "#5a4a44")
    elif it == "roll":
        cv.rect(x, y + 3, 6, 2, PAPER[1])                # 卷起来的拓片
        cv.rect(x, y + 3, 6, 1, PAPER[0])
        cv.px(x + 5, y + 3, PAPER[2])
        cv.px(x + 5, y + 4, PAPER[3])
        cv.px(x + 2, y + 5, TAPE)


# ---------- 烧掉清单：柜子左边墙上贴着的一张纸（close = 写着的那面，有几行划掉了；flipped = 翻过去，背面空白）
def burnlist():
    frames = []
    for st in ("close", "flipped"):
        c = frame(8, 11)
        c.rect(1, 1, 6, 10, PAPER[2])
        c.rect(1, 1, 6, 1, PAPER[1])
        c.rect(1, 1, 1, 10, PAPER[1])
        c.rect(2, 0, 4, 2, TAPE)                         # 胶带
        if st == "close":
            # 一行行字；上面两行（石头、卡）划掉了：划线是红褐的，压在字上
            for i, w in enumerate((4, 3, 4, 2, 3)):
                c.rect(2, 3 + i * 2, w, 1, INK)
            c.rect(2, 3, 5, 1, "#5a3a32")
            c.rect(2, 5, 4, 1, "#5a3a32")
        else:
            c.rect(2, 2, 5, 9, PAPER[3])                 # 背面：暗一档，透出一点反过来的字
            c.px(5, 4, PAPER[2])
            c.px(4, 6, PAPER[2])
            c.rect(6, 9, 1, 2, PAPER[2])                 # 一角卷起来
        frames.append((st, c))
    obj("cockpit_burnlist", (213, 95), frames, default="hidden")


# ---------- 航图（「下次一起去看看云层里的大象」那张）：靠在台子上、斜贴着玻璃
def travel_map():
    W_, H_ = 26, 15
    frames = []

    def sheet(c, top_dx, lean, h, pressed):
        # 一张斜靠的纸：底边贴着台面（y = H_-1），上沿往右靠 lean 像素（靠着玻璃）
        for yy in range(h):
            y = H_ - 1 - yy
            sh = int(round(lean * yy / max(1, h - 1)))
            c.rect(1 + sh, y, 20, 1, PAPER[1] if yy < h - 1 else PAPER[0])
            c.px(1 + sh, y, PAPER[0])
            c.px(20 + sh, y, PAPER[3])
            if not pressed and yy == h // 2:
                c.rect(1 + sh, y, 20, 1, PAPER[2])        # 折痕
            if 2 <= yy <= h - 3:
                if (yy + sh) % 5 == 0:
                    c.rect(4 + sh, y, 5, 1, "#56604c")   # 淡淡的绿地块
                if yy % 4 == 1:
                    c.rect(12 + sh, y, 4, 1, "#5d5a66")  # 云层那块（偏紫）
        # 航线：一条实线从左下到右上，终点画个小圈（云层星）
        x0, y0 = 4, H_ - 3
        x1, y1 = 16 + lean, H_ - h + 2
        col = "#6e3e32" if pressed else "#7a4a3a"
        c.line(x0, y0, x1, y1, col)
        if pressed:
            c.line(x0 + 1, y0, x1 + 1, y1, "#5a3228")
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            c.px(x1 + dx + 1, y1 + dy - 1, "#6a5a72")

    c = frame(W_, H_)
    sheet(c, 0, 3, 13, False)
    frames.append(("open", c))
    c = frame(W_, H_)
    sheet(c, 0, 1, 10, True)                             # 抹平了：靠得更平、线压实了
    frames.append(("line_pressed", c))
    c = frame(W_, H_)                                    # 折起来放在控制台旁边
    c.rect(18, H_ - 4, 7, 4, PAPER[2])
    c.rect(18, H_ - 4, 7, 1, PAPER[1])
    c.rect(18, H_ - 4, 1, 4, PAPER[1])
    c.px(22, H_ - 3, "#7a4a3a")
    c.px(21, H_ - 2, "#7a4a3a")
    frames.append(("beside_panel", c))
    obj("cockpit_map", (21, 79), frames, default="hidden")


# ---------- 弥洛的纸条：贴在窗边立柱上（flipped 翻到背面「没长出来不一定是你的问题」；folded_half / open / folded）
def note():
    frames = []
    for st in ("flipped", "folded_half", "open", "folded"):
        c = frame(7, 10)
        c.rect(2, 0, 3, 2, TAPE)
        if st in ("open", "flipped"):
            c.rect(1, 1, 5, 8, PAPER[1])
            c.rect(1, 1, 5, 1, PAPER[0])
            c.rect(5, 1, 1, 8, PAPER[3])
            lines = ((2, 3, 3), (2, 5, 2), (2, 7, 3)) if st == "open" else ((2, 4, 3), (2, 6, 3))
            for x, y, w in lines:
                c.rect(x, y, w, 1, "#4a4a48" if st == "open" else "#3e4446")
        elif st == "folded_half":
            c.rect(1, 1, 5, 5, PAPER[1])
            c.rect(1, 1, 5, 1, PAPER[0])
            c.rect(1, 5, 5, 3, PAPER[2])                # 折下来的那半，背面朝外
            c.rect(1, 7, 5, 1, PAPER[3])
            c.rect(2, 3, 3, 1, "#4a4a48")
        else:
            c.rect(1, 1, 5, 4, PAPER[2])
            c.rect(1, 1, 5, 1, PAPER[1])
            c.rect(5, 1, 1, 4, PAPER[3])
        frames.append((st, c))
    obj("cockpit_note", (87, 71), frames, default="hidden")


# ---------- 影像：台子上一只小放映盒，盖子压下去了
def footage():
    c = frame(11, 8)
    c.rect(1, 3, 9, 5, METAL[3])
    c.rect(1, 3, 9, 1, METAL[2])
    c.rect(1, 3, 1, 5, METAL[2])
    c.rect(0, 2, 10, 1, METAL[2])                        # 盖子合上：一道平的上沿
    c.rect(0, 1, 10, 1, METAL[1])
    c.px(8, 5, "#5a3a32")                                # 灭了的小灯
    c.rect(3, 5, 3, 1, "#2a302d")                        # 镜头那条缝
    obj("cockpit_footage", (65, 85), [("lid_closed", c)], default="hidden")


# ---------- 日记：靠着窗边立柱摊开（deer_page 翻到鹿那页；first_page_out 首页撕下来放在旁边）
def journal():
    frames = []
    for st in ("deer_page", "first_page_out"):
        c = frame(10, 10)
        c.rect(0, 2, 8, 8, "#3a2a22")                    # 封皮
        c.rect(1, 3, 3, 6, PAPER[1])
        c.rect(4, 3, 3, 6, PAPER[2])
        c.rect(1, 3, 6, 1, PAPER[0])
        c.rect(4, 3, 1, 6, PAPER[3])                     # 书脊的缝
        if st == "deer_page":
            # 左页：鹿角画得太大（两根分叉的褐线），右页几行字
            for p in ((1, 4), (2, 5), (3, 4), (2, 6), (2, 7)):
                c.px(*p, "#5a4634")
            c.rect(5, 5, 2, 1, INK)
            c.rect(5, 7, 1, 1, INK)
        else:
            c.rect(1, 3, 3, 6, PAPER[3])                 # 第一页没了：露出撕口，下一页暗一点
            c.px(1, 3, PAPER[1])
            c.px(3, 3, PAPER[1])
            c.rect(6, 0, 4, 3, PAPER[1])                 # 撕下来的首页：搁在本子上沿
            c.rect(6, 0, 4, 1, PAPER[0])
            c.px(7, 1, INK)
        frames.append((st, c))
    obj("cockpit_journal", (80, 83), frames, default="hidden")


# ---------- 最初的画：小时候画的大象（蜡笔，耳朵画小了、缺口是后来补的），贴在驾驶座后面的墙上
def drawing():
    W_, H_ = 36, 46                                      # 图左上 = 剖面 (78, 66)；墙上那张在 (98, 70)
    frames = []

    def paper(c, x, y, cover=False):
        c.rect(x, y, 13, 10, PAPER[1])
        c.rect(x, y, 13, 1, PAPER[0])
        c.rect(x, y, 1, 10, PAPER[0])
        c.rect(x + 12, y + 1, 1, 9, PAPER[3])
        c.rect(x, y + 9, 13, 1, PAPER[2])
        c.rect(x + 5, y - 1, 3, 2, TAPE)
        # 蜡笔：天、地、太阳，中间一只圆滚滚的象（只是小孩画的几笔）
        c.rect(x + 1, y + 7, 11, 1, CRAYON["grass"])
        c.px(x + 10, y + 2, CRAYON["sun"])
        c.px(x + 11, y + 2, CRAYON["sun"])
        c.px(x + 10, y + 3, CRAYON["sun"])
        c.rect(x + 3, y + 3, 6, 3, CRAYON["ele"])
        c.rect(x + 2, y + 3, 2, 2, CRAYON["ele"])        # 头
        c.px(x + 1, y + 5, CRAYON["ele_d"])              # 鼻子
        c.px(x + 1, y + 6, CRAYON["ele_d"])
        c.px(x + 4, y + 2, CRAYON["ele_d"])              # 耳朵（小）
        c.px(x + 5, y + 2, "#6a6b5f")                    # 缺口：补的一笔
        c.px(x + 4, y + 6, CRAYON["ele_d"])
        c.px(x + 7, y + 6, CRAYON["ele_d"])
        if cover:
            # 日记首页压在上面（盖住右下半张）
            c.rect(x + 6, y + 4, 9, 8, PAPER[0])
            c.rect(x + 6, y + 4, 9, 1, "#8a8a7a")
            c.rect(x + 14, y + 5, 1, 7, PAPER[2])
            c.rect(x + 7, y + 6, 6, 1, "#40464a")         # 「我一定要找到大象，因为」
            c.rect(x + 7, y + 8, 3, 1, "#40464a")

    c = frame(W_, H_)
    paper(c, 20, 4)
    frames.append(("open", c))
    c = frame(W_, H_)
    paper(c, 20, 4, cover=True)
    frames.append(("under_page", c))
    # beside_panel：折成小块，插在维修记录板旁边（操纵台右边的缝里）
    c = frame(W_, H_)
    c.rect(1, 31, 4, 6, PAPER[1])
    c.rect(1, 31, 4, 1, PAPER[0])
    c.rect(4, 32, 1, 5, PAPER[3])
    c.px(2, 33, CRAYON["ele"])
    c.px(3, 33, CRAYON["ele"])
    frames.append(("beside_panel", c))
    # within_reach：躺下以后放在座椅边上，一伸手就够得着
    c = frame(W_, H_)
    c.rect(16, 39, 9, 2, PAPER[1])
    c.rect(16, 39, 9, 1, PAPER[0])
    c.px(19, 40, CRAYON["ele"])
    c.px(20, 40, CRAYON["ele"])
    frames.append(("within_reach", c))
    obj("cockpit_drawing", (78, 66), frames, default="hidden")


# ---------- 左手边的工具：从右边的工具盒挪到操纵台下面，挂在一条帆布带上（「这里我拿着更顺」）
def tools_left():
    c = frame(14, 14)
    c.rect(0, 1, 14, 2, CANVAS[1])                       # 带子
    c.rect(0, 1, 14, 1, CANVAS[0])
    for x in (2, 6, 10):
        c.rect(x, 3, 2, 1, CANVAS[2])                    # 插口
    # 扳手
    c.rect(2, 3, 1, 8, METAL[1])
    c.px(1, 10, METAL[1])
    c.px(3, 10, METAL[1])
    c.px(1, 11, METAL[2])
    c.px(3, 11, METAL[2])
    c.px(2, 3, METAL[0])
    # 螺丝刀
    c.rect(6, 3, 2, 4, "#5a3e28")
    c.px(6, 3, "#6b4a2e")
    c.rect(7, 7, 1, 5, METAL[1])
    # 钳子
    c.rect(10, 3, 1, 6, METAL[2])
    c.rect(12, 3, 1, 6, METAL[3])
    c.px(11, 9, METAL[1])
    c.px(10, 10, METAL[1])
    c.px(12, 10, METAL[2])
    c.px(10, 11, METAL[1])
    c.px(12, 11, METAL[2])
    obj("cockpit_tools", (70, 112), [("left", c)], default="hidden")


# ---------- 副驾驶座：座上放着工具包，扳手露出来
def copilot():
    c = frame(22, 14)
    c.rect(3, 6, 15, 7, CANVAS[1])
    c.rect(3, 6, 15, 1, CANVAS[0])
    c.rect(3, 6, 1, 7, CANVAS[0])
    c.rect(17, 7, 1, 6, CANVAS[3])
    c.rect(4, 12, 13, 1, CANVAS[3])
    c.rect(4, 8, 13, 1, CANVAS[2])                       # 包口的拉链
    c.rect(9, 4, 4, 2, CANVAS[2])                        # 提手
    c.px(9, 4, CANVAS[1])
    c.px(12, 4, CANVAS[1])
    # 扳手从包口斜着伸出来
    c.line(12, 7, 18, 1, METAL[1])
    c.px(18, 0, METAL[0])
    c.px(19, 1, METAL[0])
    c.px(17, 0, METAL[2])
    c.px(13, 7, METAL[2])
    obj("cockpit_copilot", (128, 96), [("toolbag_wrench", c)], default="hidden")


# ---------- 导航屏（结局四）：盖在 cockpit_nav 上，descent = 下降航线，orbit = 安全漂行轨道
def screen():
    nav = load(CK / "cockpit_nav.png")[:, :23].copy()
    frames = []
    for st in ("descent", "orbit"):
        c = frame(23, 18)
        c.a[:] = nav
        c.rect(4, 3, 16, 10, SCR["bg"])
        c.rect(4, 12, 16, 1, SCR["dim"])                 # 地平线
        if st == "descent":
            pts = [(11, 4), (11, 5), (12, 6), (12, 7), (13, 8), (14, 9), (15, 10), (16, 11)]
            for p in pts:
                c.px(*p, SCR["dim"])
            for p in ((10, 4), (11, 3), (12, 4), (11, 4)):
                c.px(*p, SCR["hi"])                      # 船
            c.rect(16, 11, 2, 1, SCR["hi"])              # 降落点
        else:
            for x in range(5, 19):                       # 一圈扁扁的轨道（实线）
                u = (x + 0.5 - 12) / 7
                dy = 2.6 * np.sqrt(max(0.0, 1 - u * u))
                c.px(x, int(round(7 - dy)), SCR["dim"])
                c.px(x, int(round(7 + dy)), SCR["dim"])
            for p in ((6, 5), (7, 4), (6, 4), (5, 5)):
                c.px(*p, SCR["hi"])                      # 船停在轨道上
        frames.append((st, c))
    obj("cockpit_screen", (58, 96), frames, default="hidden")


# ---------- 关灯（结局四躺下以后）：驾驶座上方那盏灯（cockpit_art.LAMP_L，(108, 52)）灭了，它照着的那一圈暗下去，
# 灯罩里那点暖光也没了。整张剖面那么大的一层半透明暗色，只盖在不透明的地方（窗洞还是透明的）。
def lamp():
    back = load(CK / "cockpit_back.png")
    h, w = back.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    d = np.hypot(xs - 108, (ys - 52) * 1.1)
    k = np.clip(1 - d / 46.0, 0, 1)
    k = np.floor(k * 4) / 4 * 0.42 + 0.12                # 灯那一圈暗得多，整个舱也暗一点（4 档）
    c = frame(w, h)
    c.a[..., :3] = hexc("#050a09").astype(np.uint8)
    c.a[..., 3] = (np.where(back[..., 3] > 0, k, 0) * 255).astype(np.uint8)
    # 灯罩：熄了的灯泡
    for x in range(105, 111):
        c.a[50, x] = np.r_[hexc("#1a201e"), 255].astype(np.uint8)
    obj("cockpit_lamp", (0, 0), [("off", c)], default="hidden")


# ---------- 通讯器、背包的新状态（原图不动；by_gauges 是原图拷贝，单独存一张，cockpit.json 里这两件改成「一状态一张图」）
def phone_states():
    orig = load(CK / "cockpit_phone.png")
    out = {"by_gauges": orig.copy()}
    # screen_on：屏幕亮起来（淡绿的光，一行字）
    a = orig.copy()
    scr = (a[..., 1].astype(int) > 120) & (a[..., 3] > 0)
    a[scr] = np.r_[hexc("#9fd0a8"), 255].astype(np.uint8)
    ys, xs = np.where(scr)
    if len(ys):
        a[ys.min() + 1, xs.min():xs.max()] = np.r_[hexc("#3a5a48"), 255].astype(np.uint8)
    out["screen_on"] = a
    # face_down：扣过去了——只看见背壳（暗一档，没有屏幕和按键）
    b = orig.copy()
    op = b[..., 3] > 0
    lum = b[..., :3].astype(float) @ np.array([0.3, 0.55, 0.15])
    b[op & (lum > 70), :3] = hexc("#3a4741").astype(np.uint8)
    b[op & (lum <= 70), :3] = hexc("#2a3430").astype(np.uint8)
    b[op & (lum > 120), :3] = hexc("#46544d").astype(np.uint8)
    out["face_down"] = b
    # seat_screen_up：放到驾驶座上、屏幕朝上（平躺：只看见一条侧边 + 屏幕的一点光）
    c = Cv(58, 24)
    c.rect(48, 21, 8, 2, "#3e4d48")
    c.rect(48, 21, 8, 1, "#6f8178")
    c.rect(50, 20, 4, 1, "#9fd0a8")
    out["seat_screen_up"] = c.a
    return out


def bag_states():
    orig = load(CK / "cockpit_bag.png")
    a = orig.copy()
    # 侧兜里插着灌满河水的瓶子（青绿的玻璃，瓶口露出包沿）
    h, w = a.shape[:2]
    x = w - 5
    cv = Cv(w, h)
    cv.a = a
    cv.rect(x, 7, 3, 8, GLASS[2])
    cv.rect(x, 10, 3, 5, GLASS[1])
    cv.px(x, 8, GLASS[0])
    cv.px(x, 9, GLASS[0])
    cv.rect(x, 6, 3, 1, METAL[2])
    cv.rect(x - 1, 12, 5, 3, CANVAS[2])                  # 侧兜把瓶子下半截兜住
    cv.rect(x - 1, 12, 5, 1, CANVAS[1])
    return {"bottle_side_pocket": cv.a}


def build_props():
    NEW_OBJ.clear()
    cabinet()
    burnlist()
    travel_map()
    note()
    footage()
    journal()
    drawing()
    tools_left()
    copilot()
    screen()
    lamp()
    return phone_states(), bag_states()


MARKERS_NEW = {"cockpit_cabinet": 235, "cockpit_drawing": 100, "cockpit_panel": 84, "cockpit_tools": 88}


# ====================================================================== 写文件

def strip(frames):
    return np.concatenate([c.a for _, c in frames], 1)


def obj_json(name, o):
    x, y = o["px"]
    e = {"x": x - 165, "y": y - 150, "w": o["w"], "h": o["h"], "frames": len(o["frames"]),
         "states": {st: i for i, (st, _) in enumerate(o["frames"])}, "px": [x, y]}
    if o["default"]:
        e["default"] = o["default"]
    return e


def write_art():
    L = build_all()
    S = states(L)
    J = sky_json(L, S)
    for n, (a, _, _) in L.items():
        save(a, SKY / f"{n}.png")
    (SKY / "sky_final.json").write_text(json.dumps(J, ensure_ascii=False, indent=1) + "\n")
    WROTE.append("art/cockpit/sky/sky_final.json")
    ph, bg = build_props()
    for name, o in NEW_OBJ.items():
        save(strip(o["frames"]), CK / f"{name}.png")
    for st, a in ph.items():
        save(a, CK / f"cockpit_phone_{st}.png")
    for st, a in bg.items():
        save(a, CK / f"cockpit_bag_{st}.png")
    return L, S, J


def patch_cockpit_json():
    """把新物件、markers、hotspots、窗外状态名合进 cockpit.json。原有的条目一个不改，只有两处例外：
    cockpit_phone / cockpit_bag 去掉 states / frames（改成一状态一张图：cockpit_phone_<状态>.png，原图还在、
    by_gauges 那张是原图的拷贝），flight1 看起来完全一样。"""
    p = CK / "cockpit.json"
    j = json.loads(p.read_text())
    if not NEW_OBJ:
        build_props()
    for name, o in NEW_OBJ.items():
        j["objects"][name] = obj_json(name, o)
    for name in ("cockpit_phone", "cockpit_bag"):
        e = j["objects"][name]
        e.pop("states", None)
        e["frames"] = 1
        e["note"] = "一状态一张图：%s_<状态>.png（tools/cockpit_final_art.py）；没有那张就用 %s.png" % (name, name)
    for name, x in MARKERS_NEW.items():
        j["markers"][name] = {"x": x - 165, "ground_y": -22, "px": [x, 128]}
    for name in ("cabinet", "drawing", "tools", "panel"):
        j["hotspots"].setdefault(name, MARKERS_NEW["cockpit_" + name] - 165)
    sts = j["window"]["states"]
    for st in json.loads((SKY / "sky_final.json").read_text())["states"]:
        if st not in sts:
            sts.append(st)
    j["layers"][3] = ("objects（cockpit_console / cockpit_nav / cockpit_repair_log / cockpit_bell / cockpit_toolbox / "
                      "cockpit_leak / cockpit_leak_steam / cockpit_converter / cockpit_bag / cockpit_phone；终章加："
                      "cockpit_cabinet / cockpit_burnlist / cockpit_map / cockpit_note / cockpit_footage / cockpit_journal / "
                      "cockpit_drawing / cockpit_tools / cockpit_copilot / cockpit_screen / cockpit_lamp，都默认 hidden）")
    j["final_note"] = ("终章（tools/cockpit_final_art.py --json 合进来的）：新物件都默认 hidden，剧本 prop 了才出现，flight1 看不见；"
                       "cockpit_screen 盖在 cockpit_nav 上；cockpit_lamp 是整张剖面那么大的一层暗色（关灯）；"
                       "窗外的终章状态在 sky/sky_final.json。重跑 tools/cockpit_art.py 会重写这个文件，之后要再跑一次 --json。")
    p.write_text(json.dumps(j, ensure_ascii=False, indent=1) + "\n")
    WROTE.append("art/cockpit/cockpit.json（合进去）")


def preview(d: Path, L, S, J):
    d.mkdir(parents=True, exist_ok=True)
    imgs = {k: v[0] for k, v in L.items()}
    ldef = {k: dict(v, y=L[k][1]) for k, v in J["layers"].items()}
    plan = [("cloud_sea", {}), ("cloud_low", {"cockpit_map": "line_pressed", "cockpit_drawing": "open"}),
            ("cloud_part", {"cockpit_map": "beside_panel", "cockpit_drawing": "beside_panel", "cockpit_phone": "face_down",
                            "cockpit_cabinet": "open"}),
            ("land_west", {}), ("land_east", {}), ("land_town", {}),
            ("yard_elephant_far", {"cockpit_tools": "left", "cockpit_copilot": "toolbag_wrench"}),
            ("cloud_orbit", {"cockpit_screen": "orbit", "cockpit_cabinet": "closed", "cockpit_bag": "bottle_side_pocket"}),
            ("elephant_shadow", {"cockpit_screen": "orbit", "cockpit_drawing": "within_reach", "cockpit_lamp": "off",
                                 "cockpit_phone": "seat_screen_up"})]
    for st, props in plan:
        sky = render_state(ldef, imgs, S[st], t=1.5)
        ck = ck_layer(props)
        Image.fromarray(compose(sky, ck)).save(d / f"final_window_{st}.png")
    # 驾驶舱整体：终章开场（工具挂到左边、燃料柜开着、航图摊开、日记、画），云海
    props = {"cockpit_tools": "left", "cockpit_copilot": "toolbag_wrench", "cockpit_cabinet": "open",
             "cockpit_burnlist": "close", "cockpit_map": "open", "cockpit_journal": "deer_page", "cockpit_drawing": "open",
             "cockpit_note": "open", "cockpit_footage": "lid_closed", "cockpit_phone": "screen_on"}
    sky = render_state(ldef, imgs, S["cloud_sea"], t=1.5)
    Image.fromarray(compose(sky, ck_layer(props))).save(d / "final_cockpit_all_props.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="把预览（2 倍）存到这个目录")
    ap.add_argument("--json", action="store_true", help="把新物件 / markers / 窗外状态名合进 art/cockpit/cockpit.json")
    args = ap.parse_args()
    L, S, J = write_art()
    if args.json:
        patch_cockpit_json()
    for k in NEW_OBJ:
        NEW_OBJ_JSON[k] = obj_json(k, NEW_OBJ[k])
    if args.preview:
        preview(Path(args.preview), L, S, J)
    print("写了 %d 个文件" % len(WROTE))
    print("窗外状态：", ", ".join(S.keys()))
    print("新物件：", ", ".join(NEW_OBJ.keys()))
