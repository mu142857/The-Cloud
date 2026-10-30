"""河流篇的配角：阿汀（ting）、摊主（keeper）、卖菜的人（vendor）、邮差（postman）。以后改这些人只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/river_chars.py [--preview 目录] [--ting]

阿汀（10-30 起）：不再用下面的 agent 小人，改用奥斯卡画的「阴险守卫」+ 白胡子（build_ting），默认不重做，--ting 才重做。

画法（docs/river_plan.md 第 2.3 节、作者定）：
- xiao-oscar 色块派的人：大块平涂、不描边，每块料子只有亮 / 暗两档（光从左上来，亮面偏暖、暗面偏冷），
  比晨暗一点（引擎 tint 再压一档）；身高约 46~48（晨约 50）。
- 一律 100ms 一帧（agent 画的）。所有帧同一块画布 40×52，脚底点 (16, 51)，待机和走路时脚底不动。
- 图里朝右画，朝左引擎水平翻转。
原文：阿汀 = 穿防水围裙的老人（原文 78），围裙上一块补丁（原文 146）；丢绳子、站在木桩旁（78）、按住外壳 / 检查浮筒（79、145）、
拆外壳（101）、递防水板 / 外套 / 一袋材料（101、115、145）、把外套搭到椅背上（116）、低下头（117）。
摊主：柜台后，把气瓶放到柜台上（原文 103）。卖菜的人：篮子吊在栏杆外（原文 103）。邮差：屋顶窄桥上走过、袋子碰栏杆（原文 80）。

输出 art/characters/<id>/<id>.png（横排）+ <id>.json（docs/river_rooms_contract.md 第 2 节的格式）。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

AIO = Path("/Users/jiamulin/Desktop/程序programs/AI Oscar")
sys.path.insert(0, str(AIO))
from oscarkit.canvas import Canvas  # noqa: E402
from oscarkit.palette import from_lch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FW, FH = 40, 52
FOOT = (16, 51)
STEP = 0.05


def col(L, C, h):
    return from_lch(max(0.05, min(0.95, L)), C, h)


def two(base):
    """一块料子的两档：亮面（偏暖一点）、暗面（偏冷一点）。"""
    L, C, h = base
    return col(L + STEP * 0.5, C, h - 6), col(L - STEP * 0.6, C * 0.9, h + 10)


def paint(c: Canvas, m: np.ndarray, base, split=(0.8, 0.45), hi_top=False):
    """按「光从左上来」把一块 mask 分成亮 / 暗两大块：过 mask 中心的一条斜线，右下那边是暗面。"""
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return
    lt, dk = two(base)
    cx, cy = xs.mean(), ys.mean()
    shadow = (xs - cx) * split[0] + (ys - cy) * split[1] > 0.6
    for y, x, s in zip(ys, xs, shadow):
        c.put(x, y, dk if s else lt)
    if hi_top:                                     # 头顶 / 肩膀最上面一行再亮一档
        L, C, h = base
        top = {}
        for y, x in zip(ys, xs):
            top[x] = min(top.get(x, 999), y)
        for x, y in top.items():
            if x < cx + 2:
                c.put(x, y, col(L + STEP * 1.3, C, h - 10))


def mask():
    return np.zeros((FH, FW), bool)


def on(c, x, y):
    """(x, y) 这一格已经画了东西吗（出界算没有）。"""
    x, y = int(x), int(y)
    return 0 <= x < FW and 0 <= y < FH and c.a[y, x, 3] > 0


def m_poly(pts):
    return Canvas(FW, FH).poly([(int(round(x)), int(round(y))) for x, y in pts])


def m_ell(cx, cy, rx, ry):
    yy, xx = np.mgrid[0:FH, 0:FW]
    return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0


def m_limb(p0, p1, w):
    """一段胳膊 / 腿：两端圆头、宽 w 的带子。"""
    m = mask()
    (x0, y0), (x1, y1) = p0, p1
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 2
    r = w / 2.0
    yy, xx = np.mgrid[0:FH, 0:FW]
    for t in np.linspace(0, 1, n):
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        m |= (xx - x + 0.5) ** 2 + (yy - y + 0.5) ** 2 <= r * r
    return m


def ang(p, length, deg):
    """从 p 出发、长 length、角度 deg（0 = 竖直向下，正 = 往前 / 往右）。"""
    a = math.radians(deg)
    return (p[0] + length * math.sin(a), p[1] + length * math.cos(a))


# ============================================================ 一个人：姿势 → 一帧
DEFAULT_POSE = dict(lean=0.0, bob=0, head=(0, 0), legs=(0.0, 0.0), knees=(0.0, 0.0),
                    near=(5.0, 5.0), far=(-3.0, 0.0), item=None, crouch=0)


def figure(costume, **pose):
    p = dict(DEFAULT_POSE)
    p.update(pose)
    cs = costume
    c = Canvas(FW, FH)
    hip = (FOOT[0], FOOT[1] - cs["leg"] - p["crouch"])
    torso_len = cs["torso"]
    lean = math.radians(p["lean"] + cs.get("stoop", 0))
    sh = (hip[0] + torso_len * math.sin(lean), hip[1] - torso_len * math.cos(lean) + p["bob"])
    neck = (sh[0] + 1 + cs.get("neck_fwd", 0), sh[1] - 1)
    head_c = (neck[0] + 1 + p["head"][0], neck[1] - cs["head_r"] + 1 + p["head"][1])

    def leg(deg, knee, far):
        k = ang(hip, cs["leg"] / 2 + 0.5, deg)
        f = ang(k, cs["leg"] / 2, deg - knee)
        f = (f[0], min(f[1], FOOT[1]))
        m = m_limb(hip, k, cs["leg_w"]) | m_limb(k, f, cs["leg_w"] - 1)
        boot = m_limb((f[0], f[1] - cs["boot_h"]), f, cs["leg_w"]) | m_limb(f, (f[0] + 2.5, f[1]), 2)
        base = cs["pants"]
        if far:
            base = (base[0] - 0.05, base[1], base[2])
        paint(c, m & ~boot, base)
        bb = cs["boots"] if not far else (cs["boots"][0] - 0.04, cs["boots"][1], cs["boots"][2])
        paint(c, boot, bb)

    def arm(spec, far):
        s = (sh[0] - (1 if far else -0), sh[1] + 1)
        e = ang(s, cs["arm"] / 2, spec[0])
        h = ang(e, cs["arm"] / 2, spec[0] + spec[1])
        m = m_limb(s, e, cs["arm_w"]) | m_limb(e, h, cs["arm_w"] - 0.5)
        base = cs["sleeve"]
        if far:
            base = (base[0] - 0.06, base[1], base[2])
        paint(c, m, base)
        hm = m_ell(h[0] + 0.3, h[1] + 0.3, 1.3, 1.3)
        sk = cs["skin"] if not far else (cs["skin"][0] - 0.06, cs["skin"][1], cs["skin"][2])
        paint(c, hm, sk)
        return h

    # 后面那条腿、后面那只胳膊（暗一档）
    leg(p["legs"][0], p["knees"][0], True)
    arm(p["far"], True)
    # 身子
    bw = cs["body_w"]
    lx = -math.cos(lean)
    ly = -math.sin(lean)
    body = m_poly([(sh[0] - bw / 2 + 0, sh[1]), (sh[0] + bw / 2, sh[1]),
                   (hip[0] + bw / 2 + 0.5 + cs.get("belly", 0), hip[1] + 2), (hip[0] - bw / 2 - 0.5, hip[1] + 2)])
    body |= m_ell(sh[0], sh[1] + 1.5, bw / 2, 2.5)
    paint(c, body, cs["shirt"], hi_top=True)
    leg(p["legs"][1], p["knees"][1], False)
    # 衣服上的东西（围裙、背心、长外套下摆……）
    if "over" in cs:
        cs["over"](c, sh, hip, lean, p)
    # 头
    r = cs["head_r"]
    hm = m_ell(head_c[0], head_c[1], r, r + 0.5)
    face = hm & m_ell(head_c[0] + 2.2, head_c[1] + 0.8, r - 0.5, r - 0.6)
    paint(c, hm, cs["hair"], hi_top=True)
    paint(c, face & ~cs["hairline"](head_c, r), cs["skin"], split=(0.5, 0.9))
    if "head_extra" in cs:
        cs["head_extra"](c, head_c, r, p)
    eye = (int(round(head_c[0] + r - 1.5)), int(round(head_c[1] + 0.3)))
    c.put(*eye, cs["eye"])
    # 前面那只胳膊 + 手里的东西
    hand = arm(p["near"], False)
    if p["item"]:
        ITEMS[p["item"]](c, hand)
    return c.a


# ============================================================ 手里的东西
def item_rope(c, h):
    x, y = int(h[0]), int(h[1])
    for r_, L in ((3, 0.42), (2, 0.36)):
        yy, xx = np.mgrid[0:FH, 0:FW]
        m = (((xx - x - 1) / (r_ + 0.5)) ** 2 + ((yy - y - 1) / r_) ** 2 <= 1) & \
            (((xx - x - 1) / (r_ - 0.6)) ** 2 + ((yy - y - 1) / (r_ - 1.2)) ** 2 > 1)
        for yy_, xx_ in zip(*np.nonzero(m)):
            c.put(xx_, yy_, col(L, 0.035, 80))


def item_coat(c, h):
    """叠起来搭在手上的外套（灰青，原文 115）。"""
    x, y = int(h[0]), int(h[1])
    for yy in range(y - 1, y + 9):
        w = 4 if yy < y + 7 else 3
        for xx in range(x - 1, x + w):
            c.put(xx, yy, col(0.38 if xx < x + 1 else 0.33, 0.03, 200))
    c.put(x + 1, y + 9, col(0.33, 0.03, 200))


def item_bag(c, h):
    """一袋晾干的材料（原文 145）：麻布袋，口扎着。"""
    x, y = int(h[0]), int(h[1])
    for yy in range(y, y + 8):
        for xx in range(x - 2, x + 4):
            if yy == y and xx in (x - 2, x + 3):
                continue
            c.put(xx, yy, col(0.44 if xx < x + 1 else 0.38, 0.035, 75))
    c.put(x, y - 1, col(0.36, 0.03, 70))
    c.put(x + 1, y - 1, col(0.36, 0.03, 70))


def item_board(c, h):
    """防水板（原文 101）：一块灰白的板，上面几道字。"""
    x, y = int(h[0]), int(h[1])
    for yy in range(y - 6, y + 2):
        for xx in range(x, x + 6):
            c.put(xx, yy, col(0.56 if xx < x + 5 else 0.48, 0.012, 210))
    for yy in (y - 4, y - 2):
        for xx in range(x + 1, x + 4):
            c.put(xx, yy, col(0.32, 0.02, 250))


def item_paper(c, h):
    """旧记录（原文 116、117）：几页纸。"""
    x, y = int(h[0]), int(h[1])
    for yy in range(y - 5, y + 1):
        for xx in range(x - 1, x + 4):
            c.put(xx, yy, col(0.54 if xx < x + 3 else 0.46, 0.015, 92))
    c.put(x, y - 3, col(0.32, 0.02, 250))
    c.put(x + 1, y - 3, col(0.32, 0.02, 250))


def item_tank(c, h):
    """气瓶（原文 103）：灰青铁罐，顶上一只阀。"""
    x, y = int(h[0]), int(h[1])
    for yy in range(y - 8, y + 2):
        for xx in range(x - 1, x + 4):
            c.put(xx, yy, col(0.44 if xx < x + 1 else 0.36, 0.025, 195))
    c.put(x + 1, y - 9, col(0.30, 0.01, 240))
    c.put(x + 1, y - 10, col(0.36, 0.01, 240))
    c.put(x, y - 4, col(0.58, 0.04, 80))                       # 一张标签


def item_basket(c, h):
    """一只菜篮：编织纹，上面露出几根绿叶子。"""
    x, y = int(h[0]), int(h[1])
    for yy in range(y + 1, y + 7):
        for xx in range(x - 3, x + 4):
            k = (xx + yy) % 2
            c.put(xx, yy, col(0.42 - 0.04 * k, 0.035, 75))
    for xx in range(x - 3, x + 4):
        c.put(xx, y + 1, col(0.48, 0.035, 80))
    for k, xx in enumerate((x - 2, x, x + 2)):
        c.put(xx, y, col(0.40, 0.05, 140))
        c.put(xx + (k % 2), y - 1, col(0.44, 0.05, 135))
    c.put(x, y - 1, col(0.36, 0.03, 75))                       # 提手
    c.put(x, y - 2, col(0.36, 0.03, 75))


def item_letters(c, h):
    x, y = int(h[0]), int(h[1])
    for yy in range(y - 2, y + 2):
        for xx in range(x - 1, x + 3):
            c.put(xx, yy, col(0.56 if yy < y else 0.48, 0.015, 92))
    c.put(x, y - 1, col(0.36, 0.04, 30))


ITEMS = {"rope": item_rope, "coat": item_coat, "bag": item_bag, "board": item_board, "paper": item_paper,
         "tank": item_tank, "basket": item_basket, "letters": item_letters}


# ============================================================ 衣服
def hairline_cap(head_c, r):
    """帽檐以上算头发 / 帽子：脸只露出帽子下面。"""
    return m_ell(head_c[0] - 0.5, head_c[1] - r + 1.2, r + 1, r * 0.75)


def hairline_short(head_c, r):
    return m_ell(head_c[0] - 1.5, head_c[1] - 1.5, r * 0.8, r * 0.9) | m_ell(head_c[0], head_c[1] - r + 0.5, r, r * 0.55)


# ============================================================ 阿汀 = 奥斯卡的「阴险守卫」+ 白胡子
# 10-30 作者定：阿汀不用 agent 画的小人了，用奥斯卡给《Dream of Fantacy》画的旧角色「阴险守卫」当彩蛋，
# 原话「你加一个白胡子就行了」；后来又要袍子换深蓝。轮廓 / 比例 / 帧 / 帧时长都照奥斯卡原图，不缩放。
# 原图：~/骑士山城/Dream-of-Fantacy/Assets/幽盲区/战斗场景/阴险守卫/阴险守卫-Sheet.aseprite（单帧单层的 sheet，230×211 一格，
# 动画分段和帧速在同目录 阴险守卫.tscn 里：Idle = 第 0 行 0~3 格 8fps，Walking = 第 3 行 0~3 格 10fps）。
# 用到的 8 格原样裁成 92×104（格内 x 108~200、y 96~200，8 格的不透明像素都在里面）存在 art/characters/ting/src/guard_idle_walk.png，
# 这个函数只读它、往上画胡子、写 ting.png / ting.json。别的动作（攻击、分身、钻地……）当不了递东西 / 检查，不用，剧本里的动作名全别名到待机。
TING_SRC = ROOT / "art/characters/ting/src/guard_idle_walk.png"
TING_FW, TING_FH = 92, 104
TING_BEARD_PAL = {"W": (226, 224, 218, 255), "M": (188, 186, 182, 255), "S": (138, 138, 140, 255)}   # 亮 / 中 / 暗：中性灰白，跟黑团子的灰一路
TING_BEARD_FRONT = [      # 待机：正脸下巴的白胡子，锚 = 左眼往下两行（dx 从左眼算起），胡子尖往前（左）翘
    ".WWMMS.",
    "WWMMMMS",
    "WMMMMMS",
    ".WMMMS.",
    ".WWMMS.",
    "..WMMS.",
    "..WMS..",
    "..MMS..",
    ".WMS...",
    ".MS....",
]
TING_BEARD_SIDE = [       # 走路：脸藏在兜帽里，只从兜帽口下巴那里垂出来一撮，锚 = 下巴点（第一行左起第二格）
    ".WMS",
    "WWMS",
    "WMMS",
    "WMS.",
    "WMS.",
    ".MS.",
    "WS..",
    "S...",
]
TING_IDLE_EYE = [(16, 46), (16, 48), (16, 49), (16, 48)]    # 待机 4 帧左眼（亮绿那颗）的位置：脸每帧上下动，胡子跟着
TING_WALK_CHIN = [(9, 39), (12, 42), (11, 41), (11, 39)]    # 走路 4 帧兜帽口前沿的下巴点
TING_ALIAS_IDLE = ["talk", "check", "hold_shell", "count", "open_shell", "hand_board", "hand_coat", "hand_bag", "nod",
                   "show_record", "coat_on_chair", "look_down", "throw_rope", "hand", "give", "throw", "point",
                   "lift_hand", "repair", "point_log"]


# 10-30 作者又定：橙袍子换成深蓝（更融进月夜河岸）。只换色相：原来每一档橙（色相 15~25°、饱和 > 0.9）按明度一一对到深蓝的一档，
# 明暗层次照奥斯卡原图；深棕内衬对到近黑的藏青。绿脸、白胡子、背后的黑团子不动。
TING_ROBE_HUE, TING_ROBE_SAT = 222, 0.62
TING_ROBE_V = (0.53, 0.80, 0.24, 0.46)       # 原图橙的明度范围 → 深蓝的明度范围
TING_LINING = (0.10, 0.55)                   # 深棕内衬 → 明度 / 饱和


def ting_robe(fr: Image.Image):
    import colorsys
    px = fr.load()
    lo, hi, v0, v1 = TING_ROBE_V
    for y in range(fr.height):
        for x in range(fr.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            h, sat, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if not (15 <= h * 360 <= 25 and sat > 0.9):
                continue
            nv, ns = TING_LINING if v < 0.2 else (v0 + (v - lo) / (hi - lo) * (v1 - v0), TING_ROBE_SAT)
            rr, gg, bb = colorsys.hsv_to_rgb(TING_ROBE_HUE / 360, ns, nv)
            px[x, y] = (round(rr * 255), round(gg * 255), round(bb * 255), a)


def ting_beard(fr: Image.Image, tpl, ox, oy):
    px = fr.load()
    for j, row in enumerate(tpl):
        for i, ch in enumerate(row):
            if ch != ".":
                px[ox + i, oy + j] = TING_BEARD_PAL[ch]


def build_ting():
    src = Image.open(TING_SRC).convert("RGBA")
    frames = []
    for k in range(8):
        fr = src.crop((k * TING_FW, 0, (k + 1) * TING_FW, TING_FH))
        ting_robe(fr)
        if k < 4:
            ex, ey = TING_IDLE_EYE[k]
            ting_beard(fr, TING_BEARD_FRONT, ex, ey + 2)
        else:
            cx, cy = TING_WALK_CHIN[k - 4]
            ting_beard(fr, TING_BEARD_SIDE, cx - 1, cy)
        frames.append(fr)
    sheet = Image.new("RGBA", (TING_FW * 8, TING_FH))
    for k, fr in enumerate(frames):
        sheet.paste(fr, (k * TING_FW, 0))
    out = ROOT / "art/characters/ting"
    sheet.save(out / "ting.png")
    meta = {
        "_comment": "阿汀 = 奥斯卡给《Dream of Fantacy》画的「阴险守卫」（Assets/幽盲区/战斗场景/阴险守卫/阴险守卫-Sheet.aseprite），"
                    "彩蛋（作者 10-30 定），加了白胡子、橙袍子换成深蓝（作者 10-30 又定，更融进月夜；tools/river_chars.py 的 build_ting，原帧在 src/）。"
                    "原像素尺寸不缩放：92×104 一格，人比晨（40×52）大一倍。帧时长照原图：待机 125ms（8fps）、走路 100ms（10fps）。"
                    "图里朝左，朝右引擎翻转。anchor = 兜帽里那个人的脚底中点（不算背后的黑团子和拖地的斗篷下摆，"
                    "转身时人站着不动、黑团子换到另一边；和原工程一样待机 / 走路同一个 x，走路的斗篷拖地低 2 像素，y 单独给）。"
                    "原图只有待机 / 走路能用（别的段是攻击、分身、钻地），剧本里的动作名全别名到待机。",
        "frame": [TING_FW, TING_FH], "sheet": "ting.png", "anchor": [28, 97], "faces": "left", "tint": True,
        "head": 94, "speed": 40, "color": "#6b6a58",
        "anims": {"idle": {"frames": [0, 1, 2, 3], "ms": 125, "loop": True},
                  "walk": {"frames": [4, 5, 6, 7], "ms": 100, "loop": True, "anchor": [28, 99]}},
        "alias": {n: "idle" for n in TING_ALIAS_IDLE},
        # 他比晨大一倍：剧情里站位自动和别人隔开（story_runner.gd 的 _clear_x），也不挡飞机舱门（深色门板 + 门框的世界 x）
        "keep_clear": True,
        "avoid": [{"room": "river_bank", "prop": "river_bank_plane", "states": ["", "default"], "x": [138, 158]},
                  {"room": "river_bank", "prop": "river_bank_plane", "states": ["beached", "straps_drying", "fixed"],
                   "x": [204, 224]}],
    }
    (out / "ting.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return frames, meta


def keeper_over(c, sh, hip, lean, p):
    """摊主：长到小腿的灰褐长外套（下摆盖住腿），袖子挽起；脖子上一条围巾（灰青）。"""
    m = m_poly([(sh[0] - 5, sh[1] + 1), (sh[0] + 5, sh[1] + 1), (hip[0] + 6.5, hip[1] + 12), (hip[0] - 6.5, hip[1] + 12)])
    paint(c, m, (0.34, 0.03, 55), split=(0.9, 0.2))
    for yy in range(int(sh[1] + 4), int(hip[1] + 12)):       # 门襟一道
        xx = int(sh[0] + 3 + (yy - sh[1]) * 0.08)
        if on(c, xx, yy):
            c.put(xx, yy, col(0.28, 0.03, 50))
    for xx in range(int(sh[0] - 4), int(sh[0] + 5)):         # 围巾
        for yy in (int(sh[1]), int(sh[1]) + 1):
            c.put(xx, yy, col(0.40 if xx < sh[0] else 0.34, 0.03, 190))
    c.put(int(sh[0] + 3), int(sh[1] + 2), col(0.34, 0.03, 190))
    c.put(int(sh[0] + 3), int(sh[1] + 3), col(0.34, 0.03, 190))


def keeper_head(c, head_c, r, p):
    """头巾（灰玫），在脑后打个结。"""
    x, y = head_c
    for xx in range(int(x - r - 1), int(x - r + 1)):
        for yy in range(int(y + 1), int(y + 4)):
            c.put(xx, yy, col(0.36, 0.035, 15))


KEEPER = dict(leg=18, leg_w=4.4, boot_h=4, torso=15, stoop=2, head_r=5, body_w=11, belly=1,
              arm=15, arm_w=3.4,
              skin=(0.58, 0.045, 55), hair=(0.40, 0.035, 15), eye=col(0.22, 0.02, 250),
              shirt=(0.34, 0.03, 55), sleeve=(0.36, 0.03, 55), pants=(0.26, 0.012, 240), boots=(0.24, 0.015, 60),
              hairline=hairline_cap, over=keeper_over, head_extra=keeper_head)


def vendor_head(c, head_c, r, p):
    """宽边草帽（灰米色）。"""
    x, y = head_c
    by = int(round(y - r + 3))
    for xx in range(int(x - r - 3), int(x + r + 4)):
        c.put(xx, by, col(0.50 if xx < x else 0.44, 0.03, 85))
    for yy in range(int(y - r - 1), by):
        for xx in range(int(x - r + 1), int(x + r)):
            c.put(xx, yy, col(0.52 if xx < x else 0.46, 0.03, 85))
    for xx in range(int(x - r + 1), int(x + r)):
        c.put(xx, by - 1, col(0.36, 0.035, 30))             # 帽带


def vendor_over(c, sh, hip, lean, p):
    """卖菜的人：短罩衫（灰绿）、围裙（灰白）。"""
    m = m_poly([(sh[0] - 1, sh[1] + 4), (sh[0] + 4.5, sh[1] + 4), (hip[0] + 5, hip[1] + 6), (hip[0] - 1, hip[1] + 6)])
    paint(c, m, (0.46, 0.012, 95), split=(0.9, 0.3))


VENDOR = dict(leg=19, leg_w=4.0, boot_h=4, torso=14, stoop=4, head_r=5, body_w=10,
              arm=15, arm_w=3.2,
              skin=(0.56, 0.045, 50), hair=(0.30, 0.02, 60), eye=col(0.22, 0.02, 250),
              shirt=(0.36, 0.025, 150), sleeve=(0.36, 0.025, 150), pants=(0.28, 0.015, 230), boots=(0.22, 0.015, 60),
              hairline=hairline_short, over=vendor_over, head_extra=vendor_head)


def postman_head(c, head_c, r, p):
    """邮差帽（深灰蓝，短帽檐朝前）。"""
    x, y = head_c
    for yy in range(int(y - r - 1), int(y - r + 3)):
        for xx in range(int(x - r), int(x + r + 1)):
            c.put(xx, yy, col(0.30 if xx < x else 0.26, 0.025, 245))
    for xx in range(int(x + r - 1), int(x + r + 3)):
        c.put(xx, int(y - r + 3), col(0.22, 0.02, 245))


def postman_over(c, sh, hip, lean, p):
    """斜挎的邮袋（原文 80「袋子碰得栏杆轻轻响」）：带子从肩斜到胯，袋子在身后。"""
    for t in np.linspace(0, 1, 20):
        xx = int(round(sh[0] + 3 - 7 * t))
        yy = int(round(sh[1] + 1 + (hip[1] - sh[1]) * t))
        c.put(xx, yy, col(0.30, 0.03, 60))
    bx, by = int(hip[0] - 7), int(hip[1] - 3)
    for yy in range(by, by + 7):
        for xx in range(bx, bx + 6):
            c.put(xx, yy, col(0.40 if yy < by + 2 else 0.34, 0.035, 65))
    for xx in range(bx, bx + 6):
        c.put(xx, by + 2, col(0.30, 0.03, 60))                # 袋盖


POSTMAN = dict(leg=19, leg_w=4.0, boot_h=4, torso=15, stoop=3, head_r=5, body_w=10,
               arm=15, arm_w=3.2,
               skin=(0.56, 0.045, 50), hair=(0.26, 0.02, 60), eye=col(0.22, 0.02, 250),
               shirt=(0.32, 0.03, 245), sleeve=(0.32, 0.03, 245), pants=(0.26, 0.02, 245), boots=(0.20, 0.012, 240),
               hairline=hairline_short, over=postman_over, head_extra=postman_head)


# ============================================================ 动作（每格一个姿势；100ms 一帧）
def idle(n=4, **kw):
    return [dict(kw, bob=b) for b in (0, 0, 1, 1)[:n]]


def walk(slow=1.0, **kw):
    out = []
    for i in range(6):
        ph = i / 6 * 2 * math.pi
        a = 22 * math.sin(ph) * slow
        out.append(dict(kw, legs=(-a, a), knees=(max(0, -16 * math.sin(ph + 0.6)), max(0, 16 * math.sin(ph + 0.6))),
                        bob=1 if i in (1, 4) else 0,
                        near=(-10 * math.sin(ph) * slow + kw.get("near", (5, 5))[0], kw.get("near", (5, 5))[1]),
                        far=(10 * math.sin(ph) * slow - 3, 0)))
    return out


def keeper_anims():
    A = {}
    A["idle"] = idle()
    A["walk"] = walk(0.8)
    A["talk"] = [dict(), dict(near=(25, 40)), dict(near=(28, 50)), dict(near=(25, 40))]
    A["set_tank"] = [dict(lean=12, near=(20, 0), item="tank", crouch=2), dict(lean=8, near=(30, 20), item="tank", crouch=1),
                     dict(lean=6, near=(50, 30), item="tank"), dict(lean=8, near=(70, 25), item="tank"),
                     dict(lean=6, near=(75, 15), item="tank"), dict(lean=2, near=(30, 20))]
    A["nod"] = [dict(head=(0, 1)), dict(head=(1, 2), lean=3), dict(head=(0, 1)), dict()]
    A["wait"] = [dict(near=(20, 80), far=(20, 80)), dict(near=(20, 80), far=(20, 80), bob=1)]   # 两手搭在柜台上等她写完
    hold = {"wait"}
    loop = {"idle", "walk", "talk", "wait"}
    alias = {"tank_on_counter": "set_tank", "give": "set_tank", "hand": "set_tank"}
    return A, hold, loop, alias


def vendor_anims():
    A = {"idle": idle(near=(30, 60), item="basket"), "walk": walk(0.7, near=(30, 60), item="basket")}
    for f in A["walk"]:
        f["near"] = (30, 60)
    A["lower_basket"] = [dict(near=(40, 50), item="basket", lean=4), dict(near=(60, 30), item="basket", lean=8),
                         dict(near=(80, 15), item="basket", lean=10), dict(near=(80, 15), lean=10),
                         dict(near=(50, 20), lean=4)]                          # 把篮子吊到栏杆外（原文 103）
    return A, set(), {"idle", "walk"}, {}


def postman_anims():
    A = {"idle": idle(near=(25, 55), item="letters"), "walk": walk(1.0)}
    return A, set(), {"idle", "walk"}, {}


CHARS = {               # 阿汀不在这里了：改用奥斯卡的阴险守卫，见 build_ting（--ting 才重做）
    "keeper": (KEEPER, keeper_anims, dict(head=46, speed=30, color="#6a5e54")),
    "vendor": (VENDOR, vendor_anims, dict(head=46, speed=20, color="#5e6a5a")),
    "postman": (POSTMAN, postman_anims, dict(head=46, speed=26, color="#4e5868")),
}


def build_char(cid):
    cs, fn, extra = CHARS[cid]
    anims, hold, loop, alias = fn()
    frames, meta_anims = [], {}
    for name, poses in anims.items():
        idx = []
        for p in poses:
            idx.append(len(frames))
            frames.append(figure(cs, **p))
        d = {"frames": idx}
        if name in loop:
            d["loop"] = True
        elif name not in ("idle", "walk", "talk"):
            d["loop"] = False
        if name in hold:
            d["hold"] = True
        meta_anims[name] = d
    out = ROOT / "art" / "characters" / cid
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.concatenate(frames, axis=1)).save(out / f"{cid}.png")
    meta = {"_comment": f"tools/river_chars.py 生成（agent 画，100ms 一帧）。图里朝右，朝左引擎翻转。",
            "frame": [FW, FH], "sheet": f"{cid}.png", "anchor": list(FOOT), "faces": "right", "ms": 100, "tint": True,
            **extra, "anims": meta_anims}
    if alias:
        meta["alias"] = alias
    (out / f"{cid}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return frames, meta


def preview(out_dir: Path):
    from PIL import ImageDraw, ImageFont
    font = ImageFont.truetype(str(ROOT / "fonts" / "PixelFont.ttf"), 11)
    out_dir.mkdir(parents=True, exist_ok=True)
    K = 4
    rows = []
    chen = Image.open(ROOT / "art/characters/chen/chen_oscar.png").convert("RGBA").crop((7 * 68, 0, 8 * 68, 60))
    for cid in CHARS:
        meta = json.loads((ROOT / f"art/characters/{cid}/{cid}.json").read_text())
        sheet = Image.open(ROOT / f"art/characters/{cid}/{cid}.png")
        for name, d in meta["anims"].items():
            n = len(d["frames"])
            img = Image.new("RGBA", (max(n, 6) * (FW * K + 6) + 160 + 72 * K, FH * K + 22), (40, 46, 52, 255))
            dr = ImageDraw.Draw(img)
            flags = ("循环" if d.get("loop") else "一遍") + ("，停在最后一帧" if d.get("hold") else "")
            dr.text((4, 4), f"{cid}.{name}（{n} 帧，100ms，{flags}）", font=font, fill=(220, 220, 210))
            for i, fi in enumerate(d["frames"]):
                fr = sheet.crop((fi * FW, 0, fi * FW + FW, FH))
                bg = Image.new("RGBA", fr.size, (58, 66, 74, 255))
                bg.alpha_composite(fr)
                img.alpha_composite(bg.resize((FW * K, FH * K), Image.NEAREST), (160 + i * (FW * K + 6), 18))
            if name == "idle":                                       # 旁边站一个晨比身高
                cmp_ = Image.new("RGBA", (68 + FW, 60), (58, 66, 74, 255))
                cmp_.alpha_composite(chen, (0, 0))
                cmp_.alpha_composite(sheet.crop((0, 0, FW, FH)), (52, 60 - FH - 2))
                img.alpha_composite(cmp_.resize((cmp_.width * K // 2, cmp_.height * K // 2), Image.NEAREST),
                                    (img.width - 72 * K, 18))
            rows.append(img)
    Wd = max(r.width for r in rows)
    sh = Image.new("RGBA", (Wd, sum(r.height for r in rows)), (40, 46, 52, 255))
    y = 0
    for r in rows:
        sh.alpha_composite(r, (0, y))
        y += r.height
    sh.save(out_dir / "chars_frames.png")
    return out_dir / "chars_frames.png"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=Path)
    ap.add_argument("--ting", action="store_true", help="重做阿汀（阴险守卫 + 白胡子），不加就不碰 art/characters/ting/")
    a = ap.parse_args()
    if a.ting:
        frames, meta = build_ting()
        print("ting", len(frames), "帧", list(meta["anims"]))
    for cid in CHARS:
        frames, meta = build_char(cid)
        print(cid, len(frames), "帧", list(meta["anims"]))
    if a.preview:
        print(preview(a.preview))


if __name__ == "__main__":
    main()
