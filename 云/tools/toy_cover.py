"""B 站 Toy 的封面（4:3）和图标（1:1），用现成素材拼，纯 Pillow，不开 Godot。

    python3 tools/toy_cover.py                 # A、B 两版全出
    python3 tools/toy_cover.py --version A     # 只出 A
    python3 tools/toy_cover.py --out 目录       # 默认 ../宣传素材/
    python3 tools/toy_cover.py --title 云 --sub "The Cloud"

底图按 480×360（封面）/ 250×250（图标）画，再整像素放大（COVER_SCALE / ICON_SCALE），
另存 300px 宽的缩略图到 <out>/缩略检查/ 看信息流里字还看不看得清。

- A 版：云层星黄昏，晨站在伸出云台的木栈桥尽头，远处余晖里一只「像帽子」的大象剪影（奥斯卡的象 → 深色剪影）。
- B 版：标题页那座风帆小镇（art/town/room.json 的层，照游戏的视差取一屏），晨站在广场前景。
- 图标 A：余晖 + 大象剪影 + 云；图标 B：晨的头 + 云。

只读 art/ 里的图（手改清单里的象也只读不写）。背景整体提亮一档（封面不要游戏里那种黑边暗角），
字用 fonts/PixelFont.ttf 14 号点阵（一格一像素）再 NEAREST 放大，见 Bilibili Toy 使用手册「中文像素字体」那条。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "art"
FONT = ROOT / "fonts" / "PixelFont.ttf"
DEFAULT_OUT = ROOT.parent / "宣传素材"

COVER_BASE = (480, 360)
COVER_SCALE = 4          # → 1920×1440（4:3）
ICON_BASE = 250
ICON_SCALE = 3           # → 750×750
THUMB_W = 300

# 云层场景（art/town/room.json 的顺序和视差；天和云是作者 art/cloud/ 的原图）
CLOUD_LAYERS = [
    ("cloud/sky.png", 0.0), ("cloud/high.png", 0.02), ("cloud/streaks.png", 0.02), ("cloud/spires.png", 0.04),
    ("cloud/far.png", 0.08), ("cloud/midfar.png", 0.18), ("cloud/mid.png", 0.36), ("cloud/wash.png", 0.0),
    ("cloud/near.png", 0.6), ("cloud/main.png", 1.0), ("cloud/front.png", 1.4),
]
TOWN_ROOM = ART / "town" / "room.json"

# 文字颜色：云层余晖那一家子（玫瑰白 + 靛紫描边）
TITLE_FILL = (255, 240, 232)
TITLE_EDGE = (46, 28, 62)
SUB_FILL = (248, 214, 200)


# ----------------------------------------------------------------------- 基础
def load(rel: str) -> Image.Image:
    return Image.open(ART / rel).convert("RGBA")


def tile_crop(im: Image.Image, x0: int, w: int, h: int) -> Image.Image:
    """横向无限平铺的层，取从 x0 开始宽 w 的一截。"""
    x0 %= im.width
    out = Image.new("RGBA", (w, h))
    x = -x0
    while x < w:
        out.alpha_composite(im, (x, 0)) if x >= 0 else out.alpha_composite(im.crop((-x, 0, im.width, im.height)), (0, 0))
        x += im.width
    return out


def cloud_scene(cam: float, wash: bool = True):
    """作者 art/cloud/ 的一屏，照 cloud_test.tscn / cloud_town.gd：streaks、wash 是 ADD 叠加（wash 不是黑云台，是加上去的一层余晖），spires 只取前 181 行。"""
    out = Image.new("RGBA", (480, 270))
    sky = None
    for p, sc in CLOUD_LAYERS:
        im = load(p)
        if sky is None:
            sky = im
        if p.endswith("wash.png") and not wash:
            continue
        if p.endswith("spires.png"):
            im = im.crop((0, 0, im.width, 181))
        piece = tile_crop(im, int(round(cam * sc)), 480, 270) if im.width >= 480 else im
        if p.endswith(("streaks.png", "wash.png")):
            blend_add(out, piece, (0, 0))
        else:
            out.alpha_composite(piece, (0, 0))
    return out, sky


def extend_sky(scene: Image.Image, sky: Image.Image, rows: int) -> Image.Image:
    """画布比 270 高：上面补天。把 sky 最上面那行的颜色往上铺，稀稀拉拉撒几颗同样的星。"""
    w = scene.width
    out = Image.new("RGBA", (w, scene.height + rows))
    top = np.array(sky.convert("RGB"))[0:4].mean(axis=(0, 1))
    band = Image.new("RGBA", (w, rows), tuple(int(v) for v in top) + (255,))
    rng = np.random.default_rng(7)
    px = band.load()
    for _ in range(rows * w // 900):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, rows))
        c = int(rng.integers(150, 230))
        px[x, y] = (c, c - 6, c + 10, 255)
    out.alpha_composite(band, (0, 0))
    out.alpha_composite(scene, (0, rows))
    return out


def lift(im: Image.Image, gamma=0.66, floor=(30, 19, 46), gain=1.08) -> Image.Image:
    """整体提亮：伽马拉亮暗部，黑的地方垫成深紫（不要黑边暗角），再乘一点增益。alpha 不动。"""
    a = np.array(im).astype(np.float32)
    rgb = a[..., :3] / 255.0
    rgb = np.power(rgb, gamma) * gain
    fl = np.array(floor, np.float32) / 255.0
    rgb = fl + rgb * (1 - fl)
    a[..., :3] = np.clip(rgb * 255, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def scale(im: Image.Image, k: int) -> Image.Image:
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def glyphs(text: str, k: int, fill, edge=None, size=14) -> Image.Image:
    """14 号点阵字一格一像素画出来，再 ×k 放大。edge 给了就加一格宽的描边。"""
    font = ImageFont.truetype(str(FONT), size)
    pad = 3
    probe = Image.new("L", (len(text) * 16 + pad * 2, 24), 0)
    d = ImageDraw.Draw(probe)
    d.fontmode = "1"
    d.text((pad, pad), text, font=font, fill=255)
    bb = probe.getbbox()
    mask = probe.crop(bb)
    if edge is not None:
        m = np.array(mask) > 0
        pm = np.pad(m, 1)
        dil = pm.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                dil |= np.roll(np.roll(pm, dy, 0), dx, 1)
        out = np.zeros(dil.shape + (4,), np.uint8)
        out[dil] = (*edge, 255)
        out[np.pad(m, 1)] = (*fill, 255)
        img = Image.fromarray(out, "RGBA")
    else:
        img = Image.new("RGBA", mask.size, (*fill, 255))
        img.putalpha(mask)
    return scale(img, k)


def chen_frame(idx: int, flip=False) -> Image.Image:
    """奥斯卡画的晨：68×60 一帧（scripts/chen.gd 的 FRAME_SIZE），脚底在 y=56。"""
    sheet = load("characters/chen/chen_oscar.png")
    f = sheet.crop((idx * 68, 0, idx * 68 + 68, 60))
    return f.transpose(Image.FLIP_LEFT_RIGHT) if flip else f


def elephant_silhouette() -> Image.Image:
    """奥斯卡的大象（登记在手改清单里，只读），按明度映到云层的深靛紫 → 变成余晖里的剪影，形状像素一个不动。"""
    el = load("characters/elephant/elephant.png")
    a = np.array(el)
    lum = a[..., :3].astype(np.float32).mean(-1)
    alpha = a[..., 3] > 0
    lo, hi = lum[alpha].min(), lum[alpha].max()
    t = (lum - lo) / max(1.0, hi - lo)
    dark = np.array((44, 28, 60), np.float32)
    light = np.array((74, 48, 92), np.float32)
    rgb = dark + (light - dark) * t[..., None]
    out = np.zeros_like(a)
    out[..., :3] = np.clip(rgb, 0, 255)
    out[..., 3] = a[..., 3]
    return Image.fromarray(out, "RGBA").crop(el.getbbox())


def pier(x0=390) -> Image.Image:
    """云台那座木栈桥（art/cloud_town/deck_main.png 右边那截：桥面 + 桥桩 + 桥头的灯），x0 往右到桥头。"""
    dm = load("cloud_town/deck_main.png")
    return dm.crop((x0, 213, 500, 243))


def save_thumb(im: Image.Image, path: Path):
    h = round(im.height * THUMB_W / im.width)
    im.convert("RGB").resize((THUMB_W, h), Image.LANCZOS).save(path)


# ----------------------------------------------------------------------- 封面
def cover_a(title: str, sub: str) -> Image.Image:
    """晨站在木栈桥尽头望向余晖，余晖里一只帽子形的大象剪影。"""
    scene, sky = cloud_scene(cam=600)                      # 余晖在左，石针和积雨云柱在右
    top = COVER_BASE[1] - 270
    bg = extend_sky(scene, sky, top)
    bg = lift(bg)

    # 大象剪影：站在远处云海的地平线上（scene y=145），正落在余晖（sky 层固定在 x≈140）里
    el = elephant_silhouette()
    bg.alpha_composite(el, (140 - el.width // 2, top + 146 - el.height))

    # 木栈桥 ×2 从画外伸进来（镜像：灯在桥头），晨 ×2 站在桥头回头看大象
    pr = scale(pier().transpose(Image.FLIP_LEFT_RIGHT), 2)
    pier_x, pier_y = COVER_BASE[0] - pr.width + 6, top + 158
    bg.alpha_composite(pr, (pier_x, pier_y))
    ch = scale(chen_frame(13, flip=True), 2)              # idle_eye 那帧：抬眼看；翻过来朝左
    foot_y = pier_y + 2 * (221 - 213) + 1                  # 桥面最上一行（deck_main 的 221 行）+ 踩进去一行
    bg.alpha_composite(ch, (pier_x + 2 * 14 - 2 * (68 - 28) + 20, foot_y - 2 * 56))

    # 字：云 在左上角的天上，The Cloud 在右下
    t = glyphs(title, 10, TITLE_FILL, TITLE_EDGE)
    bg.alpha_composite(t, (30, 26))
    s = glyphs(sub, 2, SUB_FILL, TITLE_EDGE)
    bg.alpha_composite(s, (COVER_BASE[0] - s.width - 24, COVER_BASE[1] - s.height - 16))
    return bg


def cover_b(title: str, sub: str) -> Image.Image:
    """标题页那座风帆小镇：广场、喷泉、大风车、塔，晨站在前景。层按 art/town/room.json（Room 类，含 cloud_town.gd 给 streaks / wash 的加法叠加）。"""
    room = Room("town")
    scene = room.shot(770)
    top = COVER_BASE[1] - 270
    bg = lift(extend_sky(scene, room._img("res://art/cloud/sky.png"), top))
    ch = scale(chen_frame(9), 2)
    bg.alpha_composite(ch, (COVER_BASE[0] // 2 - 2 * 28 - 135, top + 232 - 2 * 56 + 8))
    t = glyphs(title, 10, TITLE_FILL, TITLE_EDGE)
    bg.alpha_composite(t, ((COVER_BASE[0] - t.width) // 2, 24))
    s = glyphs(sub, 2, SUB_FILL, TITLE_EDGE)
    bg.alpha_composite(s, (COVER_BASE[0] - s.width - 24, COVER_BASE[1] - s.height - 16))
    return bg


# ----------------------------------------------------------------------- C / D 版：泥芙待机帧整数倍放大的「大头」+ 右侧大字 The Cloud
# 作者 11-07：不画新角色；像参考图那样把现成精灵整数倍放大占半边画面，一个像素不改。
NIFF_SHEET = ART / "characters" / "niff" / "niff_swim.png"      # 游戏里的泥芙（swim 帧 0 就是待机，niff.json idle → swim）
NIFF_BUST = (49, 7, 70, 33)        # 帧 0 里头到胸口那一截：头发 y 8..21、脸 x 57..64、手和肩到 32（21×26）
NIFF_HEAD = (51, 7, 67, 23)        # 图标用：只到下巴（16×16）
NIFF_K = 14                        # 13 格高的头 ×14 = 182，占 360 高的一半；×18 能到 65% 但整个左半边只剩一片青壳，脸反而认不出
CHEN_BUST = (18, 2, 42, 26)        # chen_oscar 第 9 帧（idle）头到胸口（24×24）
SUB_FILL_C = (142, 242, 255)       # 「Cloud」用她壳的青色，「The」用奶白


def niff_frame(idx=0) -> Image.Image:
    sh = Image.open(NIFF_SHEET).convert("RGBA")
    return sh.crop((idx * 71, 0, idx * 71 + 71, 46))


def dim_bg(scene: Image.Image, dark=0.72, radius=1.2) -> Image.Image:
    """封面底：先提亮（游戏的夜太黑，封面不要黑边），再压一点、略虚，让放大的精灵跳出来。"""
    from PIL import ImageFilter
    im = lift(scene, gamma=0.6, floor=(34, 40, 60)).convert("RGB").filter(ImageFilter.GaussianBlur(radius))
    a = np.array(im).astype(np.float32) * dark
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def river_night_bg(size=COVER_BASE, cam_left=1500) -> Image.Image:
    """河岸月夜（art/river_city/river_bank）有人家亮灯那一段，上面补天到 4:3。"""
    room = Room("river_city/river_bank")
    scene = room.shot(cam_left)
    top = size[1] - 270
    sky = room._img("res://art/river/sky.png")
    return extend_sky(scene, sky, top)


def title_two_lines(text: str, k: int):
    """「The Cloud」拆两行：第一行奶白、第二行青色，都带一格靛紫描边。"""
    words = text.split(" ", 1)
    first = glyphs(words[0], k, TITLE_FILL, TITLE_EDGE)
    second = glyphs(words[1], k, SUB_FILL_C, TITLE_EDGE) if len(words) > 1 else None
    return first, second


def cover_c(title: str, sub: str, with_chen=False) -> Image.Image:
    bg = dim_bg(river_night_bg())
    bust = scale(niff_frame(0).crop(NIFF_BUST), NIFF_K)                     # 294×364：左边 61%，头顶到胸口，底边裁掉几行
    bg.alpha_composite(bust, (0, COVER_BASE[1] - bust.height + 4))
    if with_chen:
        ch = scale(chen_frame(9).crop(CHEN_BUST), NIFF_K)                    # 晨同样倍数，站在她右边，被底边裁到胸口
        bg.alpha_composite(ch, (COVER_BASE[0] - ch.width - 20, COVER_BASE[1] - ch.height + 10))   # 站在泥芙右肩旁，略压住她的手
        k, y = 3, 16
    else:
        k, y = 4, 112
    first, second = title_two_lines(sub, k)
    right = COVER_BASE[0] - 14
    bg.alpha_composite(first, (right - first.width, y))
    if second is not None:
        bg.alpha_composite(second, (right - second.width, y + first.height + 8))
    return bg


def cover_d(title: str, sub: str) -> Image.Image:
    return cover_c(title, sub, with_chen=True)


def icon_c(title: str) -> Image.Image:
    """泥芙那截裁方放大，不要字：16×16 的头 ×32 = 512。底是压暗的河岸夜。"""
    head = niff_frame(0).crop(NIFF_HEAD)
    bg = dim_bg(river_night_bg(size=(480, 270), cam_left=1500).crop((300, 80, 316, 96)))
    bg.alpha_composite(head, (0, 0))
    return bg


# ----------------------------------------------------------------------- 图标
def icon_a(title: str) -> Image.Image:
    """余晖里的大象剪影 + 云（字在上、象在下，像给帽子戴了顶帽子）。"""
    scene, sky = cloud_scene(cam=600)
    top = 90
    bg = lift(extend_sky(scene, sky, top))
    cx, horizon = 140, top + 146                             # 余晖中心、远处云海地平线
    x0, y0 = cx - ICON_BASE // 2, horizon - 176
    bg = bg.crop((x0, y0, x0 + ICON_BASE, y0 + ICON_BASE))
    el = elephant_silhouette()
    bg.alpha_composite(el, (cx - x0 - el.width // 2, horizon - y0 - el.height))
    t = glyphs(title, 9, TITLE_FILL, TITLE_EDGE)
    bg.alpha_composite(t, ((ICON_BASE - t.width) // 2, 10))
    return bg


def icon_b(title: str) -> Image.Image:
    """晨的头 + 云。"""
    scene, _ = cloud_scene(cam=600)
    bg = lift(scene).crop((60, 20, 60 + ICON_BASE, 20 + ICON_BASE))
    f = chen_frame(9)
    head = f.crop((14, 2, 46, 34))                             # 头和肩那块 32×32
    h = scale(head, 4)
    bg.alpha_composite(h, ((ICON_BASE - h.width) // 2, ICON_BASE - h.height))
    t = glyphs(title, 8, TITLE_FILL, TITLE_EDGE)
    bg.alpha_composite(t, ((ICON_BASE - t.width) // 2, 10))
    return bg


# ----------------------------------------------------------------------- 截图（Toy 上传页的游戏截图）
SHOT_SIZE = (480, 270)
SHOT_SCALE = 3           # → 1440×810
SHOTS_DIR = "截图"


def _hash(px, py):
    """两个 shader 共用的 hash(vec2)：fract(sin(dot(p, (127.1, 311.7))) * 43758.5453)。float32 精度，和 GPU 一样抖。"""
    v = np.sin((px * 127.1 + py * 311.7).astype(np.float32)) * np.float32(43758.5453)
    return v - np.floor(v)


_WATER_PAL = [(46, 59, 84), (71, 87, 115), (102, 117, 145), (133, 148, 173)]     # shader 里 c0..c3 的默认值


def shader_water(im: Image.Image, prm: dict) -> Image.Image:
    """scripts/river_water.gdshader 在 TIME=0 的一帧：每行晃 off 像素；palette_mode 查 4 档色，否则按 7 像素一段决定显示与否。"""
    a = np.array(im).astype(np.float32)
    h, w = a.shape[:2]
    wobble = float(prm.get("wobble", 1.5)); show = float(prm.get("show", 0.6)); flicker = float(prm.get("flicker", 0.9))
    py = np.arange(h, dtype=np.float32)[:, None]
    px = np.arange(w, dtype=np.float32)[None, :]
    depth = py / h
    ww = wobble * (0.3 + 0.7 * depth)
    off = np.round(ww * (0.65 * np.sin(py * 0.71) + 0.35 * np.sin(py * 1.93)))
    sx = np.clip((px - off).astype(int), 0, w - 1)
    t = a[np.arange(h)[:, None], sx]
    out = np.zeros_like(a)
    vis = t[..., 3] >= 128
    if prm.get("palette_mode", True):
        lv = t[..., 0] / 255 * 3 + 0.25 + flicker * np.sin(t[..., 1] / 255 * 6.2832)
        vis &= lv >= 0
        i = np.clip(np.floor(lv), 0, 3).astype(int)
        pal = np.array(_WATER_PAL, np.float32)
        out[..., :3] = pal[i]
    else:
        ph = _hash(np.floor((px - off) / 7.0), py + 0 * px)
        sgn = np.sin(ph * 40.0)
        vis &= sgn >= 1.0 - 2.0 * show
        out[..., :3] = t[..., :3]
    out[..., 3] = np.where(vis, 255, 0)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def shader_moonpath(im: Image.Image, prm: dict, cam_left: float) -> Image.Image:
    """scripts/river_moonpath.gdshader 在 TIME=0 的一帧：A 遮罩、R 最亮档、B 密度、G 这一行的 scroll（÷2 存）；碎光按世界 x 切 6 像素一格。"""
    m = np.array(im).astype(np.float32) / 255.0
    h, w = m.shape[:2]
    wobble = float(prm.get("wobble", 1.5)); flicker = float(prm.get("flicker", 0.9))
    py = np.arange(h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
    px = np.arange(w, dtype=np.float32)[None, :] * np.ones((h, 1), np.float32)
    sc = m[..., 1] * 2.0
    ww = wobble * np.clip(sc, 0.3, 1.0)
    off = np.round(ww * (0.65 * np.sin(py * 0.71) + 0.35 * np.sin(py * 1.93)))
    wx = px - off + np.floor(cam_left * sc + 0.5)
    cell = 6.0
    ci = np.floor(wx / cell)
    k = wx - ci * cell
    h1 = _hash(ci, py); h2 = _hash(ci + 31.0, py + 17.0); h3 = _hash(ci + 57.0, py + 3.0); h4 = _hash(ci + 11.0, py + 41.0)
    vis = m[..., 3] >= 0.5
    vis &= h1 <= m[..., 2]
    vis &= k < np.maximum(1.0, np.floor((0.35 + 0.65 * h2) * (cell - 1.0)))
    lv = m[..., 0] * 3.0 * (0.55 + 0.45 * h3) + 0.25 + flicker * np.sin(h2 * 6.2832)
    vis &= lv >= 0
    i = np.clip(np.floor(lv), 0, 3).astype(int)
    pal = np.array(_WATER_PAL, np.float32)
    out = np.zeros((h, w, 4), np.float32)
    out[..., :3] = pal[i]
    out[..., 3] = np.where(vis, 255, 0)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


# room.json 之外、房间脚本运行时给层加的东西：scripts/cloud_town.gd 把 streaks / wash 设成 BLEND_MODE_ADD（和 cloud_test.tscn 一样），
# spires 只取前 181 行。Pillow 直接 alpha 叠 wash（那块深色大云台）就成了一块棕色——作者 11-08 看到的「棕色部分」就是它。
ROOM_LAYER_FIX = {"town": {"streaks": {"blend": "add"}, "wash": {"blend": "add"}, "spires": {"rows": 181}}}


def blend_add(out: Image.Image, im: Image.Image, pos):
    """CanvasItemMaterial BLEND_MODE_ADD：dst += src.rgb × src.a。"""
    x, y = pos
    W, H = out.size
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + im.width), min(H, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    src = np.array(im).astype(np.float32)[y0 - y:y1 - y, x0 - x:x1 - x]
    dst = np.array(out).astype(np.float32)
    dst[y0:y1, x0:x1, :3] += src[..., :3] * (src[..., 3:4] / 255.0)
    out.paste(Image.fromarray(np.clip(dst, 0, 255).astype(np.uint8), "RGBA"))


def paste_any(out: Image.Image, im: Image.Image, pos):
    """普通 alpha 叠，位置可以是负的 / 超出右边。"""
    x, y = pos
    if x + im.width <= 0 or x >= out.width:
        return
    if x >= 0:
        out.alpha_composite(im, (x, y))
    else:
        out.alpha_composite(im.crop((-x, 0, im.width, im.height)), (0, y))


class Room:
    """按 scripts/room_stage.gd 的规则读一个 room.json 并照游戏的视差画一屏（不含 drift、动画帧；water / moonpath shader 静态近似）。"""

    def __init__(self, rel_dir: str):
        self.dir = ART / rel_dir
        self.cfg = json.loads((self.dir / "room.json").read_text("utf-8"))
        for L in self.cfg.get("layers", []):
            L.update(ROOM_LAYER_FIX.get(rel_dir, {}).get(L.get("id"), {}))
        g = self.cfg.get("ground", 228)
        self._gpts = g if isinstance(g, list) else [[0, int(g)]]
        self.markers = {k: (v["x"] if isinstance(v, dict) else (v[0] if isinstance(v, list) else v))
                        for k, v in self.cfg.get("markers", {}).items()}

    def ground(self, x: float) -> int:
        pts = self._gpts
        if x <= pts[0][0] or len(pts) == 1:
            return int(pts[0][1])
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x <= x1:
                k = (x - x0) / max(x1 - x0, 1)
                return int(round(y0 + (y1 - y0) * k))
        return int(pts[-1][1])

    def _img(self, res: str) -> Image.Image:
        """room_stage._tex：res:// 是工程路径，不带的就在房间自己的目录里。"""
        p = ROOT / res.replace("res://", "") if res.startswith("res://") else self.dir / res
        return Image.open(p).convert("RGBA")

    def layers(self, front: bool):
        """(img, cfg, z) 列表：room_stage._build_layers 的 z = -100+i，front 的 100+i，cfg 里有 z 就用 z。"""
        out = []
        for i, c in enumerate(self.cfg.get("layers", [])):
            z = int(c.get("z", (100 + i) if c.get("front") else (-100 + i)))
            if (z >= 0) == front:
                out.append((self._img(c["img"]), c, z))
        return out

    def objects(self, states: dict | None = None, hide=()):
        """默认显示的物件：(img帧, x, y, z)。states 覆盖默认状态；hide 里的不画。"""
        states = states or {}
        out = []
        for oid, c in self.cfg.get("objects", {}).items():
            if oid in hide:
                continue
            st = str(states.get(oid, c.get("default", "")))
            if st in ("hidden", "hide", "gone", "taken"):
                continue
            try:
                im = self._img(c.get("img", oid + ".png"))         # room_stage._make_object：没写 img 就是同名 png
            except FileNotFoundError:
                print("  物件缺图，跳过：", oid)
                continue
            n = max(int(c.get("frames", 1)), 1)
            w = int(c.get("w", im.width // n))
            fi = 0
            if st not in ("show", "shown", "default", ""):
                sts = c.get("states")
                if isinstance(sts, dict) and st in sts:
                    v = sts[st]
                    fi = int(v[0] if isinstance(v, list) else v)
                elif isinstance(sts, list) and st in sts:
                    fi = sts.index(st)
            fi = max(0, min(fi, n - 1))
            fr = im.crop((fi * w, 0, fi * w + w, im.height))
            z = int(c.get("z", 50 if (c.get("front") or c.get("layer") == "front") else -1))
            out.append((fr, int(c.get("x", 0)), int(c.get("y", 0)), z))
        return out

    def draw_layer(self, out: Image.Image, im: Image.Image, c: dict, cl: float):
        """cl = 镜头左边缘的房间 x。非 tile 层：屏幕 x = x − cl·scroll；tile 层按图宽铺满；scroll 0 的窄天在宽画布上横向接着铺。
        shader：water / moonpath 静态算一帧，sway 原图；blend=add 用加法（cloud_town.gd 给 streaks / wash 加的）；rows 只取前几行（spires）。"""
        sc = float(c.get("scroll", 1.0))
        x = float(c.get("x", 0))
        y = int(c.get("y", 0))
        sh = c.get("shader")
        if sh == "water":
            im = shader_water(im, c.get("shader_params", {}))
        elif sh == "moonpath":
            im = shader_moonpath(im, c.get("shader_params", {}), cam_left=cl)
        if c.get("rows"):
            im = im.crop((0, 0, im.width, min(im.height, int(c["rows"]))))
        if float(c.get("alpha", 1.0)) < 1.0:
            a = im.split()[3].point(lambda v: int(v * float(c["alpha"])))
            im = im.copy()
            im.putalpha(a)
        put = blend_add if c.get("blend") == "add" else paste_any
        if c.get("tile", False):
            w = im.width
            sx = int(round((x - cl * sc) % w - w))
            while sx < out.width:
                put(out, im, (sx, y))
                sx += w
        elif sc == 0.0 and im.width < out.width:
            sx = 0
            while sx < out.width:
                put(out, im, (sx, y)); sx += im.width
        else:
            put(out, im, (int(round(x - cl * sc)), y))

    def shot(self, cam_left: float, actors=(), states=None, hide=(), size=SHOT_SIZE) -> Image.Image:
        """actors = [(sprite, anchor(ax, ay), world_x, world_y)]：锚点落在房间坐标 (world_x, world_y)，和物件一样夹在 z<0 的层和 front 层之间。"""
        out = Image.new("RGBA", size)
        bg = self.cfg.get("bg")
        if bg:
            out.paste(self._grad(size, bg), (0, 0))
        items = [(z, "L", im, c) for im, c, z in self.layers(front=False)]
        items += [(z, "O", fr, (x, y)) for fr, x, y, z in self.objects(states, hide)]
        items.sort(key=lambda t: t[0])
        for z, kind, im, c in items:
            if kind == "L":
                self.draw_layer(out, im, c, cam_left)
            else:
                out.alpha_composite(im, (int(round(c[0] - cam_left)), c[1]))
        for sp, (ax, ay), wx, wy in actors:
            out.alpha_composite(sp, (int(round(wx - ax - cam_left)), int(round(wy - ay))))
        for im, c, z in self.layers(front=True):
            self.draw_layer(out, im, c, cam_left)
        return out

    @staticmethod
    def _grad(size, bg):
        def hx(s):
            s = s.lstrip("#")
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
        c0, c1 = hx(bg[0]), hx(bg[1] if len(bg) > 1 else bg[0])
        a = np.zeros((size[1], size[0], 4), np.uint8)
        t = np.linspace(0, 1, size[1])[:, None]
        a[..., :3] = (np.array(c0) * (1 - t) + np.array(c1) * t)[:, None, :]
        a[..., 3] = 255
        return Image.fromarray(a, "RGBA")


def npc(name: str, anim: str = "idle", pick: int = 0, flip: bool = False, json_name: str | None = None):
    """art/characters/<name>/<name>.json 那套精灵（frame / sheet / anchor / anims）：返回 (帧图, 锚点)。
    pick 是该动画 frames 列表里的第几个。flip=True 翻面（锚点 x 跟着翻）。"""
    d = json.loads((ART / "characters" / name / f"{json_name or name}.json").read_text("utf-8"))
    a = d["anims"][anim]
    sheet = a.get("sheet", d["sheet"])
    fw, fh = a.get("frame", d["frame"])
    ax, ay = a.get("anchor", d["anchor"])
    idx = a["frames"][pick]
    im = Image.open(ART / "characters" / name / sheet).convert("RGBA")
    per_row = max(1, im.width // fw)
    fx, fy = (idx % per_row) * fw, (idx // per_row) * fh
    fr = im.crop((fx, fy, fx + fw, fy + fh))
    if flip:
        fr = fr.transpose(Image.FLIP_LEFT_RIGHT)
        ax = fw - 1 - ax
    return fr, (ax, ay)


def chen(idx: int = 9, flip: bool = False):
    """晨的待机帧（scripts/chen.gd：68×60，脚底 FOOT=(28,56)），返回 (帧图, 锚点)。"""
    fr = chen_frame(idx, flip)
    return fr, ((68 - 1 - 28) if flip else 28, 56)


def save_shot(im: Image.Image, out: Path, thumbs: Path, name: str):
    assert im.size == SHOT_SIZE, im.size
    big = scale(im, SHOT_SCALE).convert("RGB")
    p = out / SHOTS_DIR / f"{name}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    big.save(p)
    save_thumb(big, thumbs / f"截图_{name}_300.png")
    print(p, big.size)


SHOTS = {}       # 名字 → 画函数（下面逐个注册）


def shot(name):
    def reg(fn):
        SHOTS[name] = fn
        return fn
    return reg


def tint(im: Image.Image, m) -> Image.Image:
    """npc_generic / npc_deer 的 modulate。"""
    a = np.array(im).astype(np.float32)
    a[..., :3] *= np.array(m, np.float32)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


NPC_TINT = (0.86, 0.87, 0.9)       # npc_generic.gd：json tint=true 的 NPC
DEER_TINT = (0.66, 0.74, 0.7)      # npc_deer.gd


def place(out: Image.Image, sp: Image.Image, anchor, wx, wy, cl):
    ax, ay = anchor
    out.alpha_composite(sp, (int(round(wx - ax - cl)), int(round(wy - ay))))


# ---------------- 森林（没有 room.json：层写在 scenes/level_forest.tscn，数据见 tools/forest_art.py 和 scripts/story_world.gd）
FOREST_SCROLL = [("forest/ridge.png", 0.06), ("forest/far.png", 0.18), ("forest/midfar.png", 0.38), ("forest/mid.png", 0.62)]
FOREST_CRASH_DX = -960             # level_forest.gd：Ridge/Far/MidFar/Mid/Front 的 scroll_offset.x += -960×scroll
FOG_C = (0x7f, 0x98, 0x8c)         # story_world.gd FOG_C


def forest_ground(x: float) -> int:
    """chen.gd ground_y：228 + 2 sin(2π x'·2/960) + 1.5 sin(2π x'·5/960 + 1)。"""
    import math
    xp = x % 960
    return int(round(228 + 2 * math.sin(math.tau * xp * 2 / 960) + 1.5 * math.sin(math.tau * xp * 5 / 960 + 1)))


def forest_layer(out: Image.Image, im: Image.Image, scroll: float, L: float, offset: float):
    """Parallax2D：贴图像素 tx 画在屏幕 (tx + offset − L·scroll) mod 960。"""
    w = im.width
    sx = int(round(offset - L * scroll)) % w - w
    while sx < out.width:
        out.alpha_composite(im, (sx, 0)) if sx >= 0 else out.alpha_composite(im.crop((-sx, 0, w, im.height)), (0, 0))
        sx += w


def fog_layer(size, density: float, alpha: float, y0: int, seed: int, cell=4) -> Image.Image:
    """story_world.gd 的噪声雾（fog_noise.gdshader）近似：低频噪声按格子画，a = clamp(n·2.25 − 1) × density，再乘层 alpha。"""
    w, h = size
    rng = np.random.default_rng(seed)
    gw, gh = w // cell // 6 + 3, (h - y0) // cell // 6 + 3
    coarse = Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8), "L")
    n = np.array(coarse.resize((w // cell, (h - y0) // cell + 1), Image.BICUBIC)).astype(np.float32) / 255
    a = np.clip(n * 2.25 - 1.0, 0, 1) * density * alpha
    a = np.floor(a * 20) / 20
    fog = np.zeros(a.shape + (4,), np.uint8)
    fog[..., :3] = FOG_C
    fog[..., 3] = (a * 255).astype(np.uint8)
    im = Image.fromarray(fog, "RGBA").resize((n.shape[1] * cell, n.shape[0] * cell), Image.NEAREST)
    out = Image.new("RGBA", size)
    out.alpha_composite(im.crop((0, 0, w, h - y0)), (0, y0))
    return out


def vignette(im: Image.Image, strength=0.62, tint=(0.86, 0.95, 0.9)) -> Image.Image:
    """scripts/vignette.gdshader（level_forest 的 Overlay）：四角压暗带一点青绿，乘法叠加。"""
    w, h = im.size
    yy, xx = np.mgrid[0:h, 0:w]
    px = (xx / w * 2 - 1) * 1.2
    py = yy / h * 2 - 1
    r = np.sqrt(px * px + py * py)
    t = np.clip((r - 0.7) / (1.65 - 0.7), 0, 1)
    v = t * t * (3 - 2 * t)
    c = 1 - v[..., None] * (1 - np.array(tint, np.float32) * (1 - strength))
    a = np.array(im).astype(np.float32)
    a[..., :3] *= c
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def forest_shot(cam_x: float, actors, fog_k=0.0, props=(), front_props=(), fog_bank_x=None, vig=True, size=SHOT_SIZE) -> Image.Image:
    """actors / props = [(img, anchor, wx, wy)]，world 坐标。fog_k 是 story_world.fog_at 的浓度 0..1。vig = 游戏里的暗角 Overlay。"""
    L = cam_x - size[0] / 2
    out = Image.new("RGBA", size, (5, 12, 10, 255))
    sky = load("forest/sky.png").crop((0, 0, 480, 270 - 17))                               # parallax_zoom_fix.gd SKY_Y=17；画布宽就横向接着铺
    sx = 0
    while sx < size[0]:
        out.alpha_composite(sky, (sx, 17)); sx += sky.width
    for rel, sc in FOREST_SCROLL:
        forest_layer(out, load(rel), sc, L, FOREST_CRASH_DX * sc)
    if fog_k > 0:
        out.alpha_composite(fog_layer(size, 0.1 + 0.87 * fog_k, 0.97, 0, 3))          # FogBack
    if fog_bank_x is not None:                                                             # forest_story/fog_bank.png：480×120，底边中点落地 +4
        fb = load("forest_story/fog_bank.png")
        place(out, fb, (240, 120), fog_bank_x, forest_ground(fog_bank_x) + 1 + 4, L)
    forest_layer(out, load("forest/main.png"), 1.0, L, 0)
    for im, anc, wx, wy in props:
        place(out, im, anc, wx, wy, L)
    for im, anc, wx, wy in front_props:          # treehouse_front 在 Snake 后一格 = 在晨后面（story_world.gd 930）；屋里时淡出不画
        place(out, im, anc, wx, wy, L)
    for im, anc, wx, wy in actors:
        place(out, im, anc, wx, wy, L)
    if fog_k > 0:
        out.alpha_composite(fog_layer(size, 0.04 + 0.30 * fog_k, 0.34, 135, 5))     # FogFront
    forest_layer(out, load("forest/front.png"), 1.4, L, FOREST_CRASH_DX * 1.4)
    return vignette(out) if vig else out


def forest_prop(rel: str, wx: float, dy=0, frame=None):
    im = load(rel)
    if frame is not None:
        n, i = frame
        w = im.width // n
        im = im.crop((i * w, 0, i * w + w, im.height))
    return (im, (im.width // 2, im.height), wx, forest_ground(wx) + 1 + dy)


def deer_idle(idx=0) -> tuple:
    """npc_deer.gd：deer_idle.png 53×58 一帧，FOOT (34,55)，美术朝左。"""
    sh = load("characters/deer/deer_idle.png")
    fr = sh.crop((idx * 53, 0, idx * 53 + 53, 58))
    return tint(fr, DEER_TINT), (34, 55)


@shot("01_木星森林_兔子")
def shot_forest_rabbit():
    """兔子一家在游戏里的位置：兔子（首领）c1_rabbit=4516 朝左，母兔 c1_rabbit_offer 那段走到 4558 朝向兔子；晨走进互动范围（hotspots RANGE 20~24）朝右。
    镜头 = 晨 + 36。雾只留一点（作者认可的森林封面是暗绿、树干清楚，不是雾墙），暗角照游戏的 Overlay。"""
    rb, ranc = npc("rabbit", "idle", 0, flip=True)
    doe, danc = npc("rabbit_doe", "idle", 0, flip=True)
    rb, doe = tint(rb, NPC_TINT), tint(doe, NPC_TINT)
    ch, canc = chen(13)
    chen_x, rabbit_x, doe_x = 4478, 4516, 4558
    cam = chen_x + 36
    return forest_shot(cam, [(doe, danc, doe_x, forest_ground(doe_x) + 1), (rb, ranc, rabbit_x, forest_ground(rabbit_x) + 1),
                             (ch, canc, chen_x, forest_ground(chen_x) + 1)], fog_k=0.18)


TREEHOUSE_X = 3550                 # story_forest.json marker treehouse；两张图底边中点落在 (3550, 228)


def treehouse_objects(anchor_x: int, anchor_y: int):
    """art/forest_story/treehouse.json 的 objects：x,y 相对图底边中点（y 往上为负），多帧取第 0 帧；pipe_steam 默认在 pipe_c 漏。"""
    tj = json.loads((ART / "forest_story" / "treehouse.json").read_text("utf-8"))
    out = []
    for oid, c in tj["objects"].items():
        im = load(f"forest_story/{oid}.png")
        w = int(c.get("w", im.width))
        fr = im.crop((0, 0, w, im.height))
        out.append((fr, (0, 0), anchor_x + int(c["x"]), anchor_y + int(c["y"])))
    return out


@shot("01b_森林树屋_室内")
def shot_treehouse_room():
    """弥洛树屋的屋内剖面（treehouse_back + 物件 + room_light，前墙进屋后淡出不画），晨站在屋里桌椅旁朝左看炉子那边。镜头 = 晨 − 36。"""
    back = load("forest_story/treehouse_back.png")
    light = load("forest_story/room_light.png")
    ay = 229
    objs = treehouse_objects(TREEHOUSE_X, ay)
    ch, canc = chen(9, flip=True)
    chen_x = TREEHOUSE_X - 20
    cam = chen_x - 36
    return forest_shot(cam, [(ch, canc, chen_x, forest_ground(chen_x) + 1)],
                       props=[(back, (170, 236), TREEHOUSE_X, ay)] + objs + [(light, (170, 236), TREEHOUSE_X, ay)])


@shot("02_森林坡地_鹿")
def shot_forest_deer():
    """坡地支线走完：鹿在 sb_slope_deer=4480（美术朝左，不翻），晨在最后一个蹄印 4432 朝右，两个面对面（作者封面的构图）；
    雾墙 fog_bank 在 4470、凹陷 depressions 在 4270，雾只留一点。"""
    deer, danc = deer_idle(0)
    ch, canc = chen(13)
    chen_x, deer_x = 4432, 4480
    cam = chen_x + 36
    return forest_shot(cam, [(deer, danc, deer_x, forest_ground(deer_x) + 1), (ch, canc, chen_x, forest_ground(chen_x) + 1)],
                       fog_k=0.18, props=[forest_prop("forest_story/depressions.png", 4270)], fog_bank_x=4470)


# ---------------- 河流篇（room.json 房间）
def room_actor(room: Room, name, wx, flip=False, hover=0, pick=0, z=0, anim="idle", tint_on=None, sheet=None):
    sp, anc = npc(name, anim, pick, flip=flip) if sheet is None else npc_sheet(name, sheet, anim, pick, flip)
    d = json.loads((ART / "characters" / name / f"{name}.json").read_text("utf-8"))
    if tint_on is None:
        tint_on = d.get("tint", True)
    if tint_on:
        sp = tint(sp, NPC_TINT)
    return (sp, anc, wx, room.ground(wx) - hover, z)


def npc_sheet(name, sheet, anim, pick, flip):
    """换一张精灵表（crowd 在云层用 crowd_night.png）。"""
    d = json.loads((ART / "characters" / name / f"{name}.json").read_text("utf-8"))
    a = d["anims"][anim]
    fw, fh = d["frame"]; ax, ay = d["anchor"]
    idx = a["frames"][pick]
    im = Image.open(ART / "characters" / name / sheet).convert("RGBA")
    fr = im.crop((idx * fw, 0, idx * fw + fw, fh))
    if flip:
        fr = fr.transpose(Image.FLIP_LEFT_RIGHT); ax = fw - 1 - ax
    return fr, (ax, ay)


def chen_actor(room: Room, wx, flip=False, idx=9, z=0):
    sp, anc = chen(idx, flip)
    return (sp, anc, wx, room.ground(wx), z)


def room_shot(room: Room, cl: float, actors, states=None, hide=(), size=SHOT_SIZE):
    """和 Room.shot 一样，但 actors 带 z（水母 z −2 要画在柜台层 −1 后面）。"""
    out = Image.new("RGBA", size)
    bg = room.cfg.get("bg")
    if bg:
        out.paste(Room._grad(size, bg), (0, 0))
    items = [(z, 0, "L", im, c) for im, c, z in room.layers(front=False)]
    items += [(z, 1, "O", fr, (x, y)) for fr, x, y, z in room.objects(states, hide)]
    items += [(z, 2, "A", sp, (anc, wx, wy)) for sp, anc, wx, wy, z in actors]
    items.sort(key=lambda t: (t[0], t[1]))
    for z, _, kind, im, c in items:
        if kind == "L":
            room.draw_layer(out, im, c, cl)
        elif kind == "O":
            out.alpha_composite(im, (int(round(c[0] - cl)), c[1]))
        else:
            place(out, im, c[0], c[1], c[2], cl)
    for im, c, z in room.layers(front=True):
        room.draw_layer(out, im, c, cl)
    return out


@shot("03_河岸月夜_阿汀泥芙")
def shot_river_bank():
    """自由探索时阿汀守在河岸（place ting → river_bank_post 一带）、泥芙在她家门口（river_bank_niff=1318，hover 2），
    晨站在两人中间；镜头往右一点，把亮灯的人家（main.png 1280 往右）收进来。阿汀美术朝左，朝右要翻；泥芙美术朝右，朝左要翻。"""
    r = Room("river_city/river_bank")
    actors = [room_actor(r, "ting", 1110, flip=True), chen_actor(r, 1200), room_actor(r, "niff", 1318, flip=True, hover=2, anim="swim")]
    return room_shot(r, 1000, actors)


@shot("03b_泥芙家_室内")
def shot_niff_home():
    """泥芙家（art/river_home/room.json，kind house，挂在河岸 x=1570，420×280，一层地板 279 ↔ 河岸地面 206）。
    home_enter：晨 fade_to river_home_chen=154 朝泥芙，泥芙 place 在 river_home_niff=212 朝晨；home_tea 把桌子换成 two_bowls_water（两碗热水）。
    屋内时前墙 home_front 淡出不画；home_light 盖在物件上、人下面；标签 labels=on，来客册 drying（在阁楼窗台）。河岸本身在房子后面透出来。"""
    bank = Room("river_city/river_bank")
    hj = json.loads((ART / "river_home" / "room.json").read_text("utf-8"))
    hx = int(hj["x"]); hw, hh = hj["size"]
    gy = bank.ground(hx)
    ox, oy = round(hx - hw / 2), gy + 1 - hh                       # room_stage._place_house：origin = (x − w/2, 地面 + 1 − 高)
    chen_x, niff_x = 154, 212
    cl = ox + hw // 2 - 240                                          # 整栋房子居中（游戏里镜头跟晨，会偏一点）
    out = bank.shot(cl, actors=[])
    def hx_(x):
        return int(round(ox + x - cl))
    out.alpha_composite(Image.open(ART / "river_home" / hj["back"]).convert("RGBA"), (hx_(0), oy))
    states = {"river_home_table": "two_bowls_water", "river_home_labels": "on", "guestbook": "drying"}
    for oid, c in hj["objects"].items():
        im = Image.open(ART / "river_home" / c["img"]).convert("RGBA")
        n = max(int(c.get("frames", 1)), 1); w = int(c.get("w", im.width // n))
        st = states.get(oid, c.get("default", ""))
        sts = c.get("states", {})
        fi = 0 if st in ("", "default", "show", "shown") else (sts[st][0] if isinstance(sts.get(st), list) else int(sts.get(st, 0)))
        fr = im.crop((fi * w, 0, fi * w + w, im.height))
        out.alpha_composite(fr, (hx_(int(c["x"])), oy + int(c["y"])))
    def floor_at(x):
        pts = hj["levels"][0]["floor"]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x <= x1:
                return y0 if x0 == x1 else round(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
        return pts[-1][1]
    ch, canc = chen(9)
    out.alpha_composite(ch, (hx_(chen_x) - canc[0], oy + floor_at(chen_x) - canc[1]))
    nf, nanc = npc("niff", "swim", 0, flip=True)
    out.alpha_composite(nf, (hx_(niff_x) - nanc[0], oy + floor_at(niff_x) - 2 - nanc[1]))
    out.alpha_composite(Image.open(ART / "river_home" / hj["light"]).convert("RGBA"), (hx_(0), oy))
    return out


@shot("04_高处市集_鼠妈")
def shot_market():
    """鼠妈 rat_chef 守在 market_rat_chef=1095 的锅前（residents，face 1），晨从入口走来停在 1129 朝左（clear 34）；镜头中心 1093。"""
    r = Room("river_city/market")
    actors = [room_actor(r, "rat_chef", 1095), chen_actor(r, 1129, flip=True)]
    return room_shot(r, 853, actors)


@shot("05_楼梯间_水母")
def shot_stairwell():
    """楼梯间 480 宽镜头不动；水母 resident 在 stairwell_jelly=396（hover 14，z −2，柜台 z −1 挡住下半身），晨下完石阶站在 340 朝右。"""
    r = Room("river_city/stairwell")
    actors = [room_actor(r, "jellyfish", 396, hover=14, z=-2), chen_actor(r, 340)]
    return room_shot(r, 0, actors)


@shot("05b_水底仓库_绿柜子")
def shot_warehouse():
    """水底仓库最右一屏（镜头夹到 cl=880）：倒下的高柜、五斗柜、内门、绳结、绿柜子（画在 main.png 里，marker 1211）、闸门。晨在柜子前朝右。"""
    r = Room("river_city/warehouse")
    return room_shot(r, 880, [chen_actor(r, 1160)])


# ---------------- 驾驶舱（cockpit_room.gd：船外背景铺满屏 → cockpit_back (75,60) → 物件 → 晨）
COCKPIT_DEFAULT_OBJS = ["cockpit_console", "cockpit_nav", "cockpit_repair_log", "cockpit_bell", "cockpit_converter", "cockpit_toolbox", "cockpit_leak", "cockpit_bag"]


def cockpit_shot(state: str, sky_file="sky_final.json", objects=None, states=None, chen_at=(179, True), chen_idx=9,
                 sky_extra=None, show_front=False, t=0.0) -> Image.Image:
    """cockpit_room.gd 的一屏：船外背景（sky.json / sky_final.json 的某个状态，停在 t 秒）铺满 → cockpit_back (75,60) → 物件 → 晨 → [cockpit_front]。
    objects = 显示哪些物件 id（默认 flight1 那八个），states = {物件: 状态名}（按 cockpit.json 的 states 取帧，不写就第 0 帧）。
    sky_extra(out, layer_id) 在画完某一层后插东西（大象剪影、碎石）。chen_at = (屏幕 x, 朝左?)，None 不画。"""
    sky_dir = ART / "cockpit" / "sky"
    sj = json.loads((sky_dir / sky_file).read_text("utf-8"))
    st = sj["states"][state]
    out = Image.new("RGBA", SHOT_SIZE)
    out.paste(Room._grad(SHOT_SIZE, st["bg"]), (0, 0))
    for L in st["layers"]:
        meta = sj["layers"][L["id"]]
        if float(L.get("alpha", 1.0)) <= 0.0:
            continue
        im = Image.open(sky_dir / meta["img"]).convert("RGBA")
        if float(L.get("alpha", 1.0)) < 1.0:
            al = im.split()[3].point(lambda v, k=float(L["alpha"]): int(v * k))
            im = im.copy(); im.putalpha(al)
        x = int(L.get("x", 0)) + int(round(-float(L.get("speed", 0)) * t))
        y = int(L["y"]) + int(round(float(L.get("vy", 0)) * t))
        if meta.get("tile"):
            sx = x % im.width - im.width
            while sx < 480:
                out.alpha_composite(im, (sx, y)) if sx >= 0 else out.alpha_composite(im.crop((-sx, 0, im.width, im.height)), (0, y))
                sx += im.width
        else:
            if x >= 0:
                out.alpha_composite(im, (x, y))
            else:
                out.alpha_composite(im.crop((-x, 0, im.width, im.height)), (0, y))
        if sky_extra:
            sky_extra(out, L["id"])
    ck = json.loads((ART / "cockpit" / "cockpit.json").read_text("utf-8"))
    out.alpha_composite(load("cockpit/cockpit_back.png"), (75, 60))
    states = states or {}
    for oid in (objects or COCKPIT_DEFAULT_OBJS):
        c = ck["objects"][oid]
        stn = states.get(oid)
        img_name = f"cockpit/{oid}.png"
        if stn and (ART / f"cockpit/{oid}_{stn}.png").exists():          # 一状态一张图的（bag / phone）
            img_name = f"cockpit/{oid}_{stn}.png"
        im = load(img_name)
        w = int(c["w"]); n = max(1, im.width // w)
        fi = 0
        sts = c.get("states", {})
        if stn in sts:
            v = sts[stn]; fi = int(v[0] if isinstance(v, list) else v)
        fi = max(0, min(fi, n - 1))
        out.alpha_composite(im.crop((fi * w, 0, fi * w + w, im.height)), (75 + c["px"][0], 60 + c["px"][1]))
    if chen_at is not None:
        ch, anc = chen(chen_idx, flip=chen_at[1])
        out.alpha_composite(ch, (chen_at[0] - anc[0], 188 - anc[1]))
    if show_front:
        out.alpha_composite(load("cockpit/cockpit_front.png"), (75, 60))
    return out


@shot("06_驾驶舱_云层星")
def shot_cockpit():
    """sky_final.json 的 cloud_sea 状态（start_final 用）停在 t=0；终章物件 copilot（toolbag_wrench）、tools（left）打开；晨站在 cockpit_seat（屏幕 x 179）朝左看前窗。
    大象：游戏里没有「整只大象在云上」的窗外状态（只有 22×14 的远景剪影和一个已删的 elephant_shadow），这里按作者要的画面，把 elephant.png
    1:1 做成深色剪影放在中景云（cs_mid，云顶 y≈127）上、衬着余晖，从窗洞 (97,105)-(164,153) 里露出来。"""
    def extra(out, lid):
        if lid == "cs_mid":
            el = elephant_silhouette()
            out.alpha_composite(el, (130 - el.width // 2, 131 - el.height))
    return cockpit_shot("cloud_sea", objects=COCKPIT_DEFAULT_OBJS + ["cockpit_copilot", "cockpit_tools"], sky_extra=extra)


# ---------------- 云层小镇
@shot("07_云层小镇_镇民")
def shot_cloud_town():
    """结局三广场：镇民（美术姐画的 townsfolk_art.png，不调色）站在 town_plaza_side=862 朝右和晨说话，晨在 896 朝左（clear 34）；
    围观的人 crowd 在 town_crowd=1116（云层用 crowd_night.png）；镜头 cl=770 把喷泉、大风车收进来。"""
    r = Room("town")
    actors = [room_actor(r, "townsfolk", 862), chen_actor(r, 896, flip=True),
              room_actor(r, "crowd", 1116, sheet="crowd_night.png", tint_on=False, z=-1)]
    return room_shot(r, 770, actors)


# ---------------- 芦苇地（room.json + reed_field.gd 程序画的芦苇 / 超前景）
REED_ROWS = {"r0": (1.0, -40), "g0": (1.0, -38), "r1": (1.0, -30), "g1": (1.0, -28), "r2": (1.0, 5), "g2": (1.0, 6), "g3": (1.0, 24), "g4": (1.25, 112), "gf": (1.3, 115)}


@shot("08_芦苇地")
def shot_reed_field():
    """tools/reed_field_art.py 自己的「dandelions」预览那一屏：cl=1440，晨在 1700（大树 1474–1687 在左、大蒲公英 near_b 在右）。"""
    return reed_scene(1440, chen_x=1700)


def reed_scene(cl: float, chen_x=None, size=SHOT_SIZE) -> Image.Image:
    """芦苇地一屏：room.json 的层 + reeds.json rows 静止姿态（角度 3 + rest + 斜度，草丛 ×0.45）贴图集 + 白鹭（fauna.json）+ 超前景 fg.png scroll 1.6。chen_x=None 不画晨。"""
    r = Room("reed_field")
    rj = json.loads((ART / "reed_field" / "reeds.json").read_text("utf-8"))
    atlas = load("reed_field/reeds.png")
    angles = rj["angles"]
    extra = []
    for row, reeds in rj["rows"].items():
        sc, z = REED_ROWS[row]
        for e in reeds:
            x, y, vn = e[0], e[1], e[2]
            lean = e[4] if len(e) > 4 else 0.0
            sx = round(x - cl * sc)
            if sx < -160 or sx > size[0] + 160:
                continue
            v = rj["variants"][vn]
            th = (3.0 + v["rest"] + lean) * (0.45 if row.startswith("g") else 1.0)
            i = min(range(len(angles)), key=lambda k: abs(angles[k] - th))
            fx, fy, fw, fh, ox, oy = v["frames"][i][:6]
            extra.append((z, atlas.crop((fx, fy, fx + fw, fy + fh)), sx + ox, y + oy))
    fj = json.loads((ART / "reed_field" / "fauna.json").read_text("utf-8"))
    fa = load("reed_field/fauna.png")
    for lx, fy_, face in fj["egrets"]:
        sx = (round(-cl * fj["isle_scroll"]) + round(lx) + 40) % 960 - 40
        fr = fj["frames"]["egret_stand"]
        im = fa.crop((fr[0], fr[1], fr[0] + fr[2], fr[1] + fr[3]))
        if face < 0:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        extra.append((r.cfg["scripts"][0]["params"]["fauna_z"][0], im, sx - fr[4], fy_ - fr[5]))
    fgc = r.cfg["scripts"][0]["params"]["fg"]
    fg = Image.open(ROOT / fgc["img"].replace("res://", "")).convert("RGBA")
    extra.append((fgc["z"], fg, round(-cl * fgc["scroll"]), fgc["y"]))

    out = Image.new("RGBA", size)
    out.paste(Room._grad(size, r.cfg["bg"]), (0, 0))
    items = [(z, 0, "L", im, c) for im, c, z in r.layers(front=False)] + [(z, 0, "L", im, c) for im, c, z in r.layers(front=True)]
    items += [(z, 1, "O", fr, (x, y)) for fr, x, y, z in r.objects(hide=("yard_ship", "east_plane"))]   # 两条结局才出现的船 / 飞机
    items += [(z, 1, "X", im, (x, y)) for z, im, x, y in extra]
    if chen_x is not None:
        ch, anc = chen(9)
        items.append((0, 2, "X", ch, (round(chen_x - anc[0] - cl), r.ground(chen_x) - anc[1])))
    items.sort(key=lambda t: (t[0], t[1]))
    for z, _, kind, im, c in items:
        if kind == "L":
            r.draw_layer(out, im, c, cl)
        elif kind == "O":
            out.alpha_composite(im, (int(round(c[0] - cl)), c[1]))
        else:
            x, y = int(c[0]), int(c[1])
            if x + im.width <= 0 or y + im.height <= 0 or x >= out.width or y >= out.height:
                continue
            if x >= 0 and y >= 0:
                out.alpha_composite(im, (x, y))
            else:
                out.alpha_composite(im.crop((max(0, -x), max(0, -y), im.width, im.height)), (max(0, x), max(0, y)))
    return out


# ---------------- 母星城市（第一章闪回：scripts/flashback.gd 把 scenes/city_test.tscn 整个搬进来当街）
CITY_SCROLL = [("ridge", 0.06), ("far", 0.18), ("midfar", 0.38), ("mid", 0.62), ("main", 1.0), ("front", 1.4)]
CITY_CROWDS = [   # scenes/city_test.tscn 的 Crowd 节点：(挂在哪层, 帧图, 帧宽高, 人数, 方向, 脚底 y(层坐标), tint 或 ramp 参数, seed)
    ("far", "hood_11", (14, 11), 40, 0, 133, {"tint": (0.471, 0.478, 0.494)}, 3),
    ("midfar", "hood_18", (18, 18), 30, 0, 155, {"tint": (0.424, 0.435, 0.447)}, 5),
    ("mid", "hood_30", (26, 30), 22, 0, 177, {"tint": (0.380, 0.388, 0.404)}, 7),
    ("main", "hood_90", (66, 90), 16, -1, 223, {"lo": (0.012, 0.020, 0.024), "hi": (0.169, 0.180, 0.192), "rim": (0.294, 0.302, 0.318), "glow": (0.353, 0.459, 0.494)}, 11),
    ("main", "hood_100", (72, 100), 12, 1, 226, {"lo": (0.0, 0.004, 0.004), "hi": (0.212, 0.220, 0.235), "rim": (0.447, 0.459, 0.475), "glow": (0.380, 0.490, 0.525)}, 14),
    ("near", "hood_110", (79, 110), 3, -1, 228, {"lo": (0.0, 0.0, 0.004), "hi": (0.094, 0.106, 0.118), "rim": (0.271, 0.282, 0.294), "glow": (0.384, 0.494, 0.529)}, 12),
]
CITY_HUES = [(1, 1, 1), (0.93, 0.96, 1.04), (0.86, 0.87, 0.9)]
CITY_DY = -40          # cam_y 175：屏幕 y = 世界 y − 40


def hood_color(fr: Image.Image, prm: dict, hue) -> Image.Image:
    """city_crowd.gd / city_crowd_ramp.gdshader：灰度档上色。远处几层乘 tint；晨那条街的三排按 lo..hi、rim、glow 映射。"""
    a = np.array(fr).astype(np.float32)
    g = a[..., 0]
    out = np.zeros_like(a)
    if "tint" in prm:
        c = np.array(prm["tint"], np.float32) * np.array(hue, np.float32)
        out[..., :3] = (g / 255.0)[..., None] * c * 255
    else:
        lo, hi, rim, glow = (np.array(prm[k], np.float32) for k in ("lo", "hi", "rim", "glow"))
        t = np.clip((g - 30.0) / 146.0, 0, 1)[..., None]
        c = lo + (hi - lo) * t
        c = np.where((g > 190)[..., None], (hi + rim) / 2, c)
        c = np.where((g > 225)[..., None], glow, c)
        c = np.where((g > 248)[..., None], rim, c)
        out[..., :3] = c * np.array(hue, np.float32) * 255
    out[..., 3] = np.where(a[..., 3] >= 128, 255, 0)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def city_crowd(out: Image.Image, layer: str, L: float, rng_seed_shift=0):
    """按 tscn 里的人数、脚底行，把兜帽人等距（带抖动）撒在 960 宽的这一层上。朝左的翻过来。脚下一道接触阴影。"""
    sc = dict(CITY_SCROLL).get(layer, 1.0)
    for lay, sheet, (fw, fh), count, direction, feet, prm, seed in CITY_CROWDS:
        if lay != layer:
            continue
        rng = np.random.default_rng(seed + rng_seed_shift)
        img = load(f"city/{sheet}.png")
        types = img.height // fh
        lanes = [(direction, count)] if direction != 0 else [(1, count // 2), (-1, count - count // 2)]
        for d, n in lanes:
            if n <= 0:
                continue
            gap = 960 / n
            for i in range(n):
                x = (i + 0.5) * gap + rng.uniform(-0.15, 0.15) * gap + rng.uniform(0, 960) * 0
                ty = int(rng.integers(0, types)); fi = int(rng.integers(0, 8))
                fr = img.crop((fi * fw, ty * fh, fi * fw + fw, ty * fh + fh))
                fr = hood_color(fr, prm, CITY_HUES[int(rng.integers(0, 3))])
                if d < 0:
                    fr = fr.transpose(Image.FLIP_LEFT_RIGHT)
                sx = int(round(x - L * sc)) % 960
                for base in (sx - 960, sx):
                    px = base - fw // 2
                    if px + fw <= 0 or px >= out.width:
                        continue
                    sw = max(2, int(fw * 0.45)); sh = 2 if fh >= 60 else 1
                    shadow = Image.new("RGBA", (sw, sh), (0, 0, 0, int(255 * (0.65 if "lo" in prm else 0.5))))
                    out.alpha_composite(shadow, (max(0, px + fw // 2 - sw // 2), feet + 1 + CITY_DY))
                    if px >= 0:
                        out.alpha_composite(fr, (px, feet - fh + CITY_DY))
                    else:
                        out.alpha_composite(fr.crop((-px, 0, fw, fh)), (0, feet - fh + CITY_DY))


T_INK, T_BODY, T_SHEEN, T_RIM = (3, 4, 6), (9, 12, 14), (40, 52, 58), (104, 124, 130)
TENT = [[110.0, 0.78, 0.30, 12.0, 5.6, 2.8], [144.0, 0.97, -0.02, 17.0, 0.0, 2.3], [180.0, 1.06, 0.06, 22.0, 1.7, -2.5],
        [216.0, 1.00, -0.04, 19.0, 3.1, 2.6], [246.0, 1.08, -0.10, 24.0, 4.4, -2.2], [272.0, 0.92, -0.16, 16.0, 2.3, 2.5],
        [294.0, 0.70, -0.30, 12.0, 0.9, -2.6]]


def tentacles(out: Image.Image, left: float, front: float, chen_x: float, grab=0.5, t=0.0):
    """flashback.gd _draw_tentacles / _spine / _tentacle 在某一帧的样子（屏幕坐标 = 世界 x − left，y − 40）。
    7 条从屏幕左边外 T_ROOT=−46 伸出来，尖到 front；grab > 0 时尖朝晨收拢。四边形都用 PIL 多边形（不抗锯齿）。"""
    import math
    d = ImageDraw.Draw(out)
    bx = left - 46.0
    chen_c = (chen_x, 228 - 24)
    TN = 26
    for by, lenk, a0, thick, ph, curl0 in TENT:
        reach = max(20.0, (front - bx) * lenk)
        curl = curl0 * (0.75 + 0.25 * math.sin(t * 1.3 + ph))
        amp = 0.42
        if grab > 0:
            a0 = a0 + (math.atan2(chen_c[1] - by, max(40.0, chen_c[0] - bx)) - a0) * grab * 0.8
            curl *= 1.0 + 0.6 * grab
            amp = 0.42 + (0.6 - 0.42) * grab
        length = reach / 0.86
        pts = [(bx, by)]
        px, py = bx, by
        ds = length / TN
        for i in range(1, TN + 1):
            sgm = i / TN
            ss = max(0.0, min(1.0, (sgm - 0.62) / 0.38)); ss = ss * ss * (3 - 2 * ss)
            a = a0 + amp * math.sin(2.4 * math.pi * sgm - t * 2.2 + ph) * (0.25 + 0.75 * sgm) + curl * (ss ** 1.6)
            px += math.cos(a) * ds; py += math.sin(a) * ds
            pts.append((px, py))
        n = TN
        lp, rp, wd = [], [], []
        for i in range(n + 1):
            sgm = i / n
            x0, y0 = pts[max(0, i - 1)]; x1, y1 = pts[min(n, i + 1)]
            dvx, dvy = x1 - x0, y1 - y0
            ln = math.hypot(dvx, dvy) or 1.0
            nx, ny = -dvy / ln, dvx / ln
            w = thick * (1.0 - sgm) ** 1.15 + 0.7
            wd.append(w); lp.append((pts[i][0] + nx * w, pts[i][1] + ny * w)); rp.append((pts[i][0] - nx * w, pts[i][1] - ny * w))
        def S(p):
            return (round(p[0] - left), round(p[1] + CITY_DY))
        for i in range(n):
            d.polygon([S(lp[i]), S(lp[i + 1]), S(rp[i + 1]), S(rp[i])], fill=(*T_BODY, 255))
        def lerp(a, b, k):
            return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
        for i in range(n):
            sgm = i / n
            up_l = lp[i][1] < rp[i][1]
            su0, su1 = (lp[i], lp[i + 1]) if up_l else (rp[i], rp[i + 1])
            sd0, sd1 = (rp[i], rp[i + 1]) if up_l else (lp[i], lp[i + 1])
            if wd[i] >= 2.5:
                d.polygon([S(lerp(pts[i], sd0, 0.6)), S(lerp(pts[i + 1], sd1, 0.6)), S(sd1), S(sd0)], fill=(*T_INK, 255))
            if 0.06 < sgm < 0.9 and wd[i] >= 1.6:
                d.polygon([S(lerp(pts[i], su0, 0.45)), S(lerp(pts[i + 1], su1, 0.45)), S(su1), S(su0)], fill=(*T_SHEEN, 255))
                if wd[i] > 3.2 and 0.12 < sgm < 0.7:
                    d.line([S(su0), S(su1)], fill=(*T_RIM, 255), width=1)


def left_shade(out: Image.Image, edge_x: int, width=70, k=0.7, col=(5, 6, 8)):
    """flashback_view.gdshader 的 grey：触手那边整片压黑（edge_x 往左全暗，往右 width 像素里渐回）。"""
    a = np.array(out).astype(np.float32)
    xs = np.arange(out.width)
    m = np.clip((edge_x + width - xs) / width, 0, 1) * k
    a[..., :3] = a[..., :3] * (1 - m[None, :, None]) + np.array(col, np.float32) * m[None, :, None]
    out.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA"))


def city_scene(L: float, crowds=True) -> Image.Image:
    """母星城市一屏（到晨那条街的三排人为止，不含前景 front 层）：city_test 的六层楼 + 人流，屏幕 y = 世界 y − 40。"""
    out = Image.new("RGBA", SHOT_SIZE, (29, 32, 36, 255))
    out.alpha_composite(load("city/sky.png").crop((0, 0, 480, 270)), (0, 0))
    for lid, sc in CITY_SCROLL[:-1]:
        im = load(f"city/{lid}.png")
        if lid == "main" and crowds:
            city_crowd(out, "far", L); city_crowd(out, "midfar", L); city_crowd(out, "mid", L)
        sx = int(round(-L * sc)) % im.width - im.width
        while sx < 480:
            out.alpha_composite(im, (sx, CITY_DY)) if sx >= 0 else out.alpha_composite(im.crop((-sx, 0, im.width, im.height)), (0, CITY_DY))
            sx += im.width
    if crowds:
        city_crowd(out, "main", L)
    return out


def city_front(out: Image.Image, L: float):
    fr = load("city/front.png")
    sx = int(round(-L * 1.4)) % fr.width - fr.width
    while sx < 480:
        out.alpha_composite(fr, (sx, CITY_DY)) if sx >= 0 else out.alpha_composite(fr.crop((-sx, 0, fr.width, fr.height)), (0, CITY_DY))
        sx += fr.width


@shot("00_母星_城市")
def shot_city_flashback():
    """第一章开头的闪回（追照片）：母星的雨街（city_test.tscn 六层楼 + 五排兜帽人流）、晨在屏幕 x=300 往右跑、
    照片在她前面飘（PAPER_Y 190）、前面一摞纸箱和一个施工路障、触手从左边扑过来（_front 到她身后 30，grab 0.5），左边整片压黑，暗角照游戏。"""
    chen_x = 1000.0
    cam = chen_x + 60.0
    L = cam - 240.0
    out = city_scene(L)
    # 障碍（flashback._build_obstacle）：纸箱三只摞起来、路障（底边在 GROUND 228）
    bx = chen_x + 95
    for i, (ox, oy) in enumerate([(12, -8.5), (13.5, -24), (11, -36.5)]):
        b = load(f"flashback/obstacle_box_{'abc'[i]}.png")
        out.alpha_composite(b, (round(bx + ox - b.width / 2 - L), round(228 + oy - b.height / 2 + CITY_DY)))
    rx = chen_x + 165
    bar = load("flashback/obstacle_barrier.png")
    out.alpha_composite(bar, (round(rx - L), 228 - 34 + CITY_DY))
    lamp = ImageDraw.Draw(out)
    cx, cy = round(rx + 22 + 12 - L), 228 - 28 + CITY_DY
    for r, al in ((6, 0.10), (3.5, 0.2)):
        ov = Image.new("RGBA", out.size); ImageDraw.Draw(ov).ellipse((cx - r, cy - r, cx + r, cy + r), fill=(230, 170, 70, int(255 * al)))
        out.alpha_composite(ov)
    # 触手（在近排人流前面、晨后面）
    front = chen_x - 30.0
    left_shade(out, round(front - 70 - L))
    tentacles(out, L, front, chen_x)
    ch, anc = chen(20)                                                     # run 帧
    out.alpha_composite(ch, (300 - anc[0], 228 - anc[1] + CITY_DY))
    paper = load("forest_story/icon_drawing.png")
    out.alpha_composite(paper, (round(300 + 58 - paper.width / 2), round(190 - paper.height / 2 + CITY_DY)))
    city_crowd(out, "near", L)
    fr = load("city/front.png")
    sx = int(round(-L * 1.4)) % fr.width - fr.width
    while sx < 480:
        out.alpha_composite(fr, (sx, CITY_DY)) if sx >= 0 else out.alpha_composite(fr.crop((-sx, 0, fr.width, fr.height)), (0, CITY_DY))
        sx += fr.width
    return vignette(out)


# ---------------- 回家的列车（终章尾声：scripts/home_train.gd + art/home_train/）
TRAIN_LAYERS = [("ridge", 960, 6.0, "city"), ("far", 960, 18.0, "city"), ("midfar", 960, 38.0, "city"), ("mid", 960, 62.0, "city"),
                ("poles", 480, 240.0, "home_train"), ("deck", 480, 240.0, "home_train")]


@shot("00b_母星_列车")
def shot_home_train():
    """epi_home：晨从车门 train_door=52 走到座位 train_seat=305（剧本接着播 sit，chen.gd 没有坐姿帧，游戏里就是站着），
    窗外还在城里（train_window=afternoon_sun）：作者 art/city 四层楼按各自车速往左退（这里停在 t=4 秒），高架桥面和路灯最快；
    车厢 car.png + 玻璃 glass.png，太阳光束 beam_* 加法叠在车厢上（被楼挡住的那几束暗到 0.35），乘客和吊环取第 0 帧。"""
    out = Image.new("RGBA", SHOT_SIZE)
    out.alpha_composite(load("home_train/sky.png"), (0, 0))
    t = 4.0
    occ = json.loads((ART / "home_train" / "occlusion.json").read_text("utf-8"))
    shift = {}
    for lid, w, speed, d in TRAIN_LAYERS:
        im = load(f"{d}/{lid}.png")
        s = int(round(speed * t))
        shift[lid] = s
        sx = -(s % w)
        while sx < 480:
            out.alpha_composite(im, (sx, 0)) if sx >= 0 else out.alpha_composite(im.crop((-sx, 0, im.width, im.height)), (0, 0))
            sx += w
    out.alpha_composite(load("home_train/car.png"), (0, 0))
    out.alpha_composite(load("home_train/glass.png"), (0, 0))
    # 光束：加法；被 mid / midfar 的楼挡住 → 0.35（home_train._update_beams，窗看的是 u = s + 96 + (win − 96) × SWEEP）
    SWEEP = {"midfar": 0.4, "mid": 0.5}
    base = np.array(out).astype(np.float32)
    for b in occ["beams"]:
        wx = b["win"]
        o = 0.0
        for lid in ("mid", "midfar"):
            u = int(round(shift[lid] + 96 + (wx - 96) * SWEEP[lid])) % 960
            v = occ[f"occ_{lid}"][u]
            o = max(o, v * (1.0 if lid == "mid" else 0.7))
        alpha = 1.0 + (0.35 - 1.0) * o
        bm = np.array(load(f"home_train/{b['img']}")).astype(np.float32)
        x, y = b["at"]
        h, w = bm.shape[:2]
        x1, y1 = min(480, x + w), min(270, y + h)
        if x1 <= x or y1 <= y:
            continue
        reg = base[y:y1, x:x1, :3]
        src = bm[:y1 - y, :x1 - x]
        reg += src[..., :3] * (src[..., 3:4] / 255.0) * alpha
    out = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGBA")
    for name, y in (("straps", 127), ("passengers", 128)):
        im = load(f"home_train/{name}.png")
        out.alpha_composite(im.crop((0, 0, 480, im.height)), (0, y))
    ch, anc = chen(9)
    out.alpha_composite(ch, (305 - anc[0], 228 - anc[1]))
    return out


# ----------------------------------------------------------------------- itch.io Banner 960×400（作者：角色一排、左右各几个、中间标题、城市背景）
BANNER_BASE = (480, 200)       # ×2 = 960×400（240×100 ×4 放不下十个 1× 的角色；320×133 ×3 = 399 差一行）
BANNER_SCALE = 2
BANNER_FONT = ROOT.parent.parent / "无引擎小样" / "assets" / "pixel.ttf"     # 粗笔画的像素字，和作者自己做的封面字形最接近（fonts/PixelFont 是 1 格细线）
BANNER_GROUND = 190
TITLE_THE = (176, 180, 232)    # 作者封面：The 淡紫、Cloud 白
TITLE_CLOUD = (255, 255, 255)


def banner_text(text: str, size: int, fill) -> Image.Image:
    font = ImageFont.truetype(str(BANNER_FONT), size)
    probe = Image.new("L", (len(text) * size * 2 + 8, size * 3), 0)
    d = ImageDraw.Draw(probe)
    d.fontmode = "1"
    d.text((4, 4), text, font=font, fill=255)
    m = probe.crop(probe.getbbox())
    im = Image.new("RGBA", m.size, (*fill, 255))
    im.putalpha(m)
    return im


def city_band(w=480, h=270, L=0) -> Image.Image:
    """scenes/city_test.tscn 的一屏：Sky 钉在屏幕，其余层 Parallax2D（y 随世界），cam_y 175 → 屏幕 y = 世界 y − 40。"""
    out = Image.new("RGBA", (w, h), (29, 32, 36, 255))
    out.alpha_composite(load("city/sky.png").crop((0, 0, w, h)), (0, 0))
    for rel, sc in [("city/ridge.png", 0.06), ("city/far.png", 0.18), ("city/midfar.png", 0.38), ("city/mid.png", 0.62), ("city/main.png", 1.0), ("city/front.png", 1.4)]:
        im = load(rel)
        sx = int(round(-L * sc)) % im.width - im.width
        while sx < w:
            out.alpha_composite(im, (sx, -40)) if sx >= 0 else out.alpha_composite(im.crop((-sx, 0, im.width, im.height)), (0, -40))
            sx += im.width
    return out


def cool_dark(im: Image.Image, k=0.55, tint=(0.82, 0.9, 1.0)) -> Image.Image:
    a = np.array(im).astype(np.float32)
    a[..., :3] *= k * np.array(tint, np.float32)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def banner(with_title=True) -> Image.Image:
    W, H = BANNER_BASE
    # 夜空：深冷渐变 + 星（art/flight/stars.png，淡）+ 一条远云（art/flight/clouds_far.png，压暗）给大象站
    out = Image.new("RGBA", (W, H))
    out.paste(Room._grad((W, H), ["#0a0e16", "#1a2230"]), (0, 0))
    stars = load("flight/stars.png").crop((0, 0, W, H))
    sa = stars.split()[3].point(lambda v: int(v * 0.55))
    stars.putalpha(sa)
    out.alpha_composite(stars)
    clouds = cool_dark(load("cloud/far.png"), 0.42, (0.8, 0.88, 1.0)).crop((120, 130, 120 + W, 270))   # 作者云层的远云，压暗偏冷
    out.alpha_composite(clouds, (0, 96 - 10))
    # 大象：elephant.png 压暗 40%，当远景剪影站在云上、标题后面
    el = load("characters/elephant/elephant.png")
    el = cool_dark(el, 0.6, (1, 1, 1)).crop(el.getbbox())
    out.alpha_composite(el, (W // 2 - el.width // 2, 96 - el.height))
    # 城市：下半截当剪影带，压暗偏冷；带子顶部渐隐进夜空
    city = cool_dark(city_band(), 0.55)
    band_top = BANNER_GROUND - 188 + 90                       # 城市屏幕 y=90 那一行落到这里，地面 188 → BANNER_GROUND
    crop = city.crop((0, 90, W, 90 + (H - band_top)))
    fade = np.array(crop).astype(np.float32)
    rows = fade.shape[0]
    ramp = np.clip(np.arange(rows) / 34.0, 0, 1)[:, None]      # 顶上 34 行从 0 渐到 1
    fade[..., 3] = fade[..., 3] * ramp
    out.alpha_composite(Image.fromarray(fade.astype(np.uint8), "RGBA"), (0, band_top))
    # 角色：全部 1×，站在同一条地面线上。左边朝右：晨、兔子首领、鹿、大嘴鸟、弥洛；右边朝左：泥芙、阿汀、鼠妈、水母、云层镇民
    def snake():
        sh = load("characters/snake/snake.png")
        return sh.crop((0, 0, 31, 50)), (17, 45)
    deer_im, deer_anc = deer_idle(0)
    deer_im = deer_im.transpose(Image.FLIP_LEFT_RIGHT); deer_anc = (53 - 1 - deer_anc[0], deer_anc[1])
    tou, tanc = npc("toucan", "idle", 0, flip=True)                 # 美术朝左，翻成朝右
    rb, ranc = npc("rabbit", "idle", 0); rb = tint(rb, NPC_TINT)
    left = [chen(9), (rb, ranc), (deer_im, deer_anc), (tou, tanc), snake()]
    tg, tganc = npc("ting", "idle", 0); tg = tint(tg, NPC_TINT)    # 美术朝左，不翻
    nf, nanc = npc("niff", "swim", 0, flip=True)
    rc, rcanc = npc("rat_chef", "idle", 0, flip=True)
    jf, jfanc = npc("jellyfish", "idle", 0, flip=True)
    tf, tfanc = npc("townsfolk", "idle", 0, flip=True)
    right = [(nf, nanc, 2), (tg, tganc, 0), (rc, rcanc, 0), (jf, jfanc, 14), (tf, tfanc, 0)]
    gap = 8
    x = 12
    for im, anc in left:
        bb = im.getbbox()
        out.alpha_composite(im, (x - bb[0], BANNER_GROUND - anc[1]))
        x += (bb[2] - bb[0]) + gap
    total = sum(im.getbbox()[2] - im.getbbox()[0] for im, _, _ in right) + gap * (len(right) - 1)
    x = W - 12 - total
    for im, anc, hover in right:
        bb = im.getbbox()
        out.alpha_composite(im, (x - bb[0], BANNER_GROUND - hover - anc[1]))
        x += (bb[2] - bb[0]) + gap
    if with_title:
        the = banner_text("The", 24, TITLE_THE)
        cloud = banner_text("Cloud", 48, TITLE_CLOUD)
        out.alpha_composite(the, (W // 2 - the.width // 2, 24))
        out.alpha_composite(cloud, (W // 2 - cloud.width // 2, 24 + the.height + 6))
    return out


# ----------------------------------------------------------------------- 角色卡 1920×1080（作者：左边大名字、右边角色顶到接近画面高、背景压暗、不写简介）
CARD_SIZE = (1920, 1080)
CARD_K = 19                  # 角色 NEAREST 放大倍数（五张同一个，按人形角色定）：晨 50 格 ×19 = 950，88% 画面高；其他矮就矮，脚踩同一条基线
CARD_BASELINE = 1020         # 脚底那条线（屏幕 y）
CARD_NAME_LIGHT = (0xf4, 0xef, 0xe4)   # 兜底的米白
CARD_NAME_BASE = 16          # pixel.ttf 在 16 号是干净的 2 格笔画点阵（大写 9 格高），按它整数倍放大，像素对齐
CARD_NAME_MAX_H = 0.27       # 字母最高 27% 画面高（作者 11-08）
CARD_GAP = 100               # 名字和角色之间至少空这么多（作者：80–120）
# 每张的字色都取自该场景 / 精灵里已有的像素色（作者：别凭空选色，像 Banner 里 The 的淡紫那种感觉）
CARD_NAME_COLORS = {
    "Milo": (0x6e, 0x8e, 0x78),     # 森林雾带最亮那档青绿（art/forest/sky.png）
    "Niff": (0x49, 0xcd, 0xde),     # 她鲸鱼壳的青（niff_swim.png）
    "???": (0xf2, 0xcb, 0x40),      # 芦苇穗的暖黄（reed_field/reeds.png）
    "Light": (0xd5, 0xde, 0xff),    # 晨头发的淡紫（chen_oscar.png），冷、不灰
    "Nimbus": (0xec, 0xc4, 0xd4),   # 云层镇花圃 / 粉云的粉（cloud_town/town_main.png）
}
CARD_MARGIN = int(1920 * 0.08)
CARD_NAME_Y = 0.5            # 名字中心在画面中线
CARD_DIR = "角色卡"


def card_bg(scene: Image.Image) -> Image.Image:
    """背景原色原亮度（作者 11-08：压暗了看不清），只把 480×270 的一屏 ×4。"""
    return scale(scene.convert("RGB"), 4).convert("RGBA")


def outlined(text: Image.Image, edge, px=8) -> Image.Image:
    """给字加一圈深色描边（px = 放大后的像素数，8 = 背景的 2 格），字和背景撞色时还能读。"""
    a = np.array(text)[..., 3] > 0
    pad = np.pad(a, px)
    dil = pad.copy()
    for dy in range(-px, px + 1):
        for dx in range(-px, px + 1):
            if dx * dx + dy * dy <= px * px:
                dil |= np.roll(np.roll(pad, dy, 0), dx, 1)
    out = np.zeros(dil.shape + (4,), np.uint8)
    out[dil] = (*edge, 255)
    out[pad] = np.array(text)[a]
    return Image.fromarray(out, "RGBA")


def card(scene: Image.Image, sprite: Image.Image, name: str, color=None, k=CARD_K, side="right", bleed_x=None) -> Image.Image:
    """side = 角色在哪边（"left" / "right"），名字放另一边、都看着画面中间；名字和角色不重叠，中间至少空 CARD_GAP。
    字号按名字长度定：16 号点阵 ×k 整数放大，k 取「名字块宽 ≤ 那半边可用宽（边距到角色之间）」和「字母高 ≤ 27% 画面高」里小的那个。
    bleed_x：角色左上角直接放在这个屏幕 x（超出画面的部分裁掉）。"""
    out = card_bg(scene)
    sp = sprite.crop(sprite.getbbox())
    big = scale(sp, k)
    if bleed_x is not None:
        x = bleed_x
    elif side == "left":
        x = 80
    else:
        x = CARD_SIZE[0] - 80 - big.width
    char_l, char_r = max(0, x), min(CARD_SIZE[0], x + big.width)
    if x < 0:
        out.alpha_composite(big.crop((-x, 0, big.width, big.height)), (0, CARD_BASELINE - big.height))
    else:
        out.alpha_composite(big.crop((0, 0, min(big.width, CARD_SIZE[0] - x), big.height)), (x, CARD_BASELINE - big.height))
    # 名字
    base = banner_text(name, CARD_NAME_BASE, color or CARD_NAME_COLORS.get(name, CARD_NAME_LIGHT))
    cap = banner_text("M", CARD_NAME_BASE, (255, 255, 255)).height
    if side == "right":                                  # 角色在右：名字在左，从左边距到角色左边减间距
        avail = char_l - CARD_GAP - CARD_MARGIN
    else:
        avail = CARD_SIZE[0] - CARD_MARGIN - (char_r + CARD_GAP)
    kk = max(1, min(avail // base.width, int(CARD_SIZE[1] * CARD_NAME_MAX_H) // cap))
    t = scale(base, kk)
    tx = CARD_MARGIN if side == "right" else CARD_SIZE[0] - CARD_MARGIN - t.width
    out.alpha_composite(t, (tx, int(1080 * CARD_NAME_Y) - t.height // 2))
    return out


def cards() -> dict:
    """五张，左右交错、都看着画面中间（作者 11-08）：Milo 在右朝左、Niff 在左朝右、??? 大象在右朝左出血、Light（晨）在左朝右、Nimbus 在左朝右。
    名字按作者定的：Milo（= 游戏 i18n）/ Niff / ???（大象是梦里的那只，没名字）/ Light / Nimbus。"""
    out = {}
    back = load("forest_story/treehouse_back.png"); front = load("forest_story/treehouse_front.png")
    forest = forest_shot(TREEHOUSE_X - 60, [], props=[(back, (170, 236), TREEHOUSE_X, 229)], front_props=[(front, (170, 236), TREEHOUSE_X, 229)], fog_k=0.15)
    snake = load("characters/snake/snake.png").crop((0, 0, 31, 50)).transpose(Image.FLIP_LEFT_RIGHT)      # 美术朝右，镜像朝左
    out["01_Milo"] = card(forest, snake, "Milo", side="right")
    niff, _ = npc("niff", "swim", 0)                                                                    # 美术朝右
    out["02_Niff"] = card(Room("river_city/river_bank").shot(1000), niff, "Niff", side="left", bleed_x=-200)   # 鲸鱼壳 1216 宽：尾巴从左边出血一点，人在壳右端完整
    el = load("characters/elephant/elephant.png")                                                      # 头在左边 = 朝左
    out["03_Elephant"] = card(reed_scene(1440), el, "???", side="right", bleed_x=900)
    ch, _ = chen(9)                                                                                     # 美术朝右
    city = city_scene(820.0)
    city_front(city, 820.0)
    out["04_Light"] = card(city, ch, "Light", side="left")
    sheep, _ = npc("townsfolk", "idle", 0)                                                              # 美术朝右
    out["05_Nimbus"] = card(Room("town").shot(770), sheep, "Nimbus", side="left", bleed_x=-140)   # 背往左出血一点，脸朝右完整；六个字母只能到 512 号
    return out


# ----------------------------------------------------------------------- 星图（paper_view 摊开的样子）和 itch 侧栏竖图
UI_FONT = ROOT / "fonts" / "PixelFont_ui.ttf"
PAPER_LABELS = [("Home", 26, 97), ("Forest", 58, 3), ("River", 101, 93), ("Clouds", 149, 5), ("Town", 179, 37), ("Reeds", 163, 98)]   # scripts/paper_view.gd BACK_LABELS 的英文（作者：地名不要中文）
LABEL_INK = (40, 48, 104)


def star_map_shot() -> Image.Image:
    """scripts/paper_view.gd：场景上盖 DIM (0.02,0.03,0.04,0.78)，paper_map.png ×2 居中再上提 6，地名用 UI 字 14 号、墨色，80 宽居中在 (x×2−40, y×2)。
    底下的场景取晨在树屋门口那一屏（第一次看地图就在弥洛家门外）。"""
    back = load("forest_story/treehouse_back.png"); front = load("forest_story/treehouse_front.png")
    ch, canc = chen(9, flip=True)
    chen_x = TREEHOUSE_X - 80
    scene = forest_shot(chen_x - 36, [(ch, canc, chen_x, forest_ground(chen_x) + 1)],
                        props=[(back, (170, 236), TREEHOUSE_X, 229)], front_props=[(front, (170, 236), TREEHOUSE_X, 229)], fog_k=0.15)
    dim = Image.new("RGBA", SHOT_SIZE, (5, 8, 10, int(255 * 0.78)))
    scene.alpha_composite(dim)
    paper = load("forest_story/paper_map.png")
    pw, ph = paper.width * 2, paper.height * 2
    px, py = round((480 - pw) / 2), round((270 - ph) / 2 - 6)
    scene.alpha_composite(scale(paper, 2), (px, py))
    font = ImageFont.truetype(str(UI_FONT), 14)
    d = ImageDraw.Draw(scene)
    d.fontmode = "1"
    for text, lx, ly in PAPER_LABELS:
        w = d.textlength(text, font=font)
        d.text((px + lx * 2 - 40 + (80 - w) / 2, py + ly * 2), text, font=font, fill=(*LABEL_INK, 255))
    return scene


STRIP_BASE = (180, 360)
STRIP_SCALE = 3          # → 540×1080


def strip(scene: Image.Image, sky_rel: str, x0: int, top_rows=45, sky_x0=None) -> Image.Image:
    """从 480×270 的一屏裁 180 宽一竖条，上面接这个场景天空层最上面那几行（sky_x0 可以另选一段，躲开亮斑）、下面把地面那几行往下接，凑到 360 高。"""
    w, h = STRIP_BASE
    out = Image.new("RGBA", (w, h))
    sky = load(sky_rel)
    sx0 = (x0 if sky_x0 is None else sky_x0) % max(1, sky.width - w + 1)
    top = sky.crop((sx0, 0, sx0 + w, top_rows)).transpose(Image.FLIP_TOP_BOTTOM)   # 上下翻：带子最下一行 = 天空图第 0 行，和下面场景的第 0 行接得上，渐变不跳
    out.alpha_composite(top, (0, 0))
    out.alpha_composite(scene.crop((x0, 0, x0 + w, 270)), (0, top_rows))
    foot = scene.crop((x0, 258, x0 + w, 270))
    y = top_rows + 270
    while y < h:                                   # top_rows=90 时正好 360，不用接地
        out.alpha_composite(foot, (0, y))
        y += foot.height
    return out.crop((0, 0, w, h))


def strips() -> dict:
    out = {}
    # 1 森林：树屋门口（01b 那一屏的屋外），晨在门口
    back = load("forest_story/treehouse_back.png"); front = load("forest_story/treehouse_front.png")
    ch, canc = chen(9, flip=True)
    cx = TREEHOUSE_X - 80
    forest = forest_shot(cx - 36, [(ch, canc, cx, forest_ground(cx) + 1)],
                         props=[(back, (170, 236), TREEHOUSE_X, 229)], front_props=[(front, (170, 236), TREEHOUSE_X, 229)], fog_k=0.15)
    out["01_森林"] = strip(forest, "forest/sky.png", 200)
    # 2 河岸月夜 + 黄灯小镇：泥芙漂在她家门口那段
    r = Room("river_city/river_bank")
    bank = room_shot(r, 1000, [room_actor(r, "ting", 1110, flip=True), chen_actor(r, 1200), room_actor(r, "niff", 1318, flip=True, hover=2, anim="swim")])
    out["02_河岸"] = strip(bank, "river/sky.png", 290)
    # 3 水底仓库：绿柜子和倒下的高柜那段
    r = Room("river_city/warehouse")
    wh = room_shot(r, 880, [chen_actor(r, 1160)])
    out["03_水底仓库"] = strip(wh, "underwater/deep.png", 230, sky_x0=0)     # deep.png 顶上中间有一块亮斑，接天那段从左边取
    # 4 云层小镇：cl=700 从路灯开始的那一段街：路灯 712、带阳台的塔 720–750、亮窗的房子 780–820、长椅、镇民 862（一整段，不切房子）。
    #   小镇底下本来就是云海（不是地），所以不往下接地，而是上面多接 90 行天（从 sky.png 另一段取，星星不重复），正好 360 高。
    r = Room("town")
    town = room_shot(r, 700, [room_actor(r, "townsfolk", 862), chen_actor(r, 896, flip=True), room_actor(r, "crowd", 1116, sheet="crowd_night.png", tint_on=False, z=-1)])
    out["04_云层小镇"] = strip(town, "cloud/sky.png", 0, top_rows=90, sky_x0=300)
    # 5 芦苇地：晨在大树和大蒲公英之间
    out["05_芦苇地"] = strip(reed_scene(1440, chen_x=1700), "reed_field/sky.png", 200)
    return out


# ----------------------------------------------------------------------- itch 页面分割条 1920×320（960×160 ×2）：每张取一个场景地平线附近的一条横带
DIV_BASE = (960, 160)
DIV_SCALE = 2


def band(scene: Image.Image, y0: int) -> Image.Image:
    return scene.crop((0, y0, DIV_BASE[0], y0 + DIV_BASE[1]))


def train_scene(width=960) -> Image.Image:
    """回家的列车拉到 960 宽：窗外城市层本来就是 960 的 tile；车厢 car / glass / 乘客 / 吊环是 480 宽，镜像接一节（两头对得上，接缝不露）。"""
    W = width
    out = Image.new("RGBA", (W, 270))
    sky = load("home_train/sky.png")
    for sx in range(0, W, sky.width):
        out.alpha_composite(sky, (sx, 0))
    t = 4.0
    for lid, w, speed, d in TRAIN_LAYERS:
        im = load(f"{d}/{lid}.png")
        sx = -(int(round(speed * t)) % w)
        while sx < W:
            out.alpha_composite(im, (sx, 0)) if sx >= 0 else out.alpha_composite(im.crop((-sx, 0, im.width, im.height)), (0, 0))
            sx += w

    def mirrored(im):
        return [im, im.transpose(Image.FLIP_LEFT_RIGHT)]
    for name in ("car", "glass"):
        for i, im in enumerate(mirrored(load(f"home_train/{name}.png"))):
            out.alpha_composite(im, (i * 480, 0))
    occ = json.loads((ART / "home_train" / "occlusion.json").read_text("utf-8"))
    base = np.array(out).astype(np.float32)
    for i in range(2):
        for b in occ["beams"]:
            bm = load(f"home_train/{b['img']}")
            if i == 1:
                bm = bm.transpose(Image.FLIP_LEFT_RIGHT)
            bm = np.array(bm).astype(np.float32)
            x, y = b["at"]
            if i == 1:
                x = 960 - x - bm.shape[1]
            h, w = bm.shape[:2]
            x0, x1, y1 = max(0, x), min(W, x + w), min(270, y + h)
            if x1 <= x0 or y1 <= y:
                continue
            src = bm[:y1 - y, x0 - x:x1 - x]
            base[y:y1, x0:x1, :3] += src[..., :3] * (src[..., 3:4] / 255.0) * 0.8
    out = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGBA")
    for name, y in (("straps", 127), ("passengers", 128)):
        im = load(f"home_train/{name}.png").crop((0, 0, 480, 270))
        for i, fr in enumerate(mirrored(im)):
            out.alpha_composite(fr, (i * 480, y))
    ch, anc = chen(9)
    out.alpha_composite(ch, (305 - anc[0], 228 - anc[1]))
    return out


def dividers() -> dict:
    out = {}
    back = load("forest_story/treehouse_back.png"); front = load("forest_story/treehouse_front.png")
    ch, canc = chen(9, flip=True)
    cx = TREEHOUSE_X - 80
    forest = forest_shot(TREEHOUSE_X + 40, [(ch, canc, cx, forest_ground(cx) + 1)],
                         props=[(back, (170, 236), TREEHOUSE_X, 229)], front_props=[(front, (170, 236), TREEHOUSE_X, 229)], fog_k=0.15, size=(960, 270))
    out["01_森林"] = band(forest, 100)                   # 树冠底到地面，树屋在中间，晨在门口
    r = Room("river_city/river_bank")
    bank = room_shot(r, 760, [room_actor(r, "ting", 1110, flip=True), chen_actor(r, 1200), room_actor(r, "niff", 1318, flip=True, hover=2, anim="swim")], size=(960, 270))
    out["02_河岸"] = band(bank, 100)                     # 水面 + 对岸黄灯的人家
    r = Room("river_city/warehouse")
    out["03_水底仓库"] = band(room_shot(r, 400, [chen_actor(r, 1160)], size=(960, 270)), 100)
    r = Room("town")
    town = room_shot(r, 480, [room_actor(r, "townsfolk", 862), chen_actor(r, 896, flip=True), room_actor(r, "crowd", 1116, sheet="crowd_night.png", tint_on=False, z=-1)], size=(960, 270))
    out["04_云层小镇"] = band(town, 70)                  # 屋顶一排、余晖、石针
    out["05_芦苇地"] = band(reed_scene(1200, chen_x=1700, size=(960, 270)), 90)
    out["06_列车"] = band(train_scene(960), 100)
    return out


# ----------------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["A", "B", "C", "D", "all"], default="all")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--title", default="云")
    ap.add_argument("--sub", default="The Cloud")
    ap.add_argument("--no-icon", action="store_true")
    ap.add_argument("--dividers", action="store_true", help="出 分割条/01–06（1920×320）")
    ap.add_argument("--extra", action="store_true", help="出 截图/星图.png 和 竖图/01–05（540×1080）")
    ap.add_argument("--cards", action="store_true", help="出 1920×1080 角色卡到 <out>/角色卡/（五张），缩略到 缩略检查/")
    ap.add_argument("--banner", action="store_true", help="出 itch.io 的 960×400 banner（带字 + 无字两张）到 <out>/")
    ap.add_argument("--shots", nargs="*", metavar="名字",
                    help="出游戏截图到 <out>/截图/（不带名字 = 全部；带名字只出那几张）；给了这个就不出封面")
    args = ap.parse_args()

    out = args.out
    thumbs = out / "缩略检查"
    out.mkdir(parents=True, exist_ok=True)
    thumbs.mkdir(parents=True, exist_ok=True)
    if args.dividers:
        (out / "分割条").mkdir(parents=True, exist_ok=True)
        for name, b in dividers().items():
            big = scale(b, DIV_SCALE).convert("RGB")
            assert big.size == (1920, 320), big.size
            big.save(out / "分割条" / f"{name}.png")
            save_thumb(big, thumbs / f"分割条_{name}_300.png")
            print(out / "分割条" / f"{name}.png", big.size)
        return
    if args.extra:
        im = star_map_shot()
        (out / SHOTS_DIR).mkdir(parents=True, exist_ok=True)
        scale(im, SHOT_SCALE).convert("RGB").save(out / SHOTS_DIR / "星图.png")
        save_thumb(scale(im, SHOT_SCALE), thumbs / "截图_星图_300.png")
        print(out / SHOTS_DIR / "星图.png")
        return
    if args.cards:
        (out / CARD_DIR).mkdir(parents=True, exist_ok=True)
        for name, im in cards().items():
            assert im.size == CARD_SIZE, im.size
            p = out / CARD_DIR / f"{name}.png"
            im.convert("RGB").save(p)
            save_thumb(im, thumbs / f"角色卡_{name}_300.png")
            print(p, im.size)
        return
    if args.banner:
        for name, wt in (("banner_960x400", True), ("banner_960x400_无字", False)):
            im = scale(banner(wt), BANNER_SCALE).convert("RGB")
            assert im.size == (960, 400), im.size
            im.save(out / f"{name}.png")
            print(out / f"{name}.png", im.size)
        return
    if args.shots is not None:
        names = args.shots or list(SHOTS)
        for n in names:
            save_shot(SHOTS[n](), out, thumbs, n)
        return
    versions = ["A", "B", "C", "D"] if args.version == "all" else [args.version]
    covers = {"A": cover_a, "B": cover_b, "C": cover_c, "D": cover_d}
    icons = {"A": (icon_a, ICON_SCALE), "B": (icon_b, ICON_SCALE), "C": (icon_c, 32)}    # 图标 C 是 16×16 ×32 = 512
    for v in versions:
        cover = covers[v](args.title, args.sub)
        assert cover.size == COVER_BASE, cover.size
        big = scale(cover, COVER_SCALE).convert("RGB")
        p = out / f"封面_4x3_{v}.png"
        big.save(p)
        save_thumb(big, thumbs / f"封面_4x3_{v}_300.png")
        print(p, big.size)
        if not args.no_icon and v in icons:
            fn, k = icons[v]
            icon = fn(args.title)
            assert icon.width == icon.height, icon.size
            big = scale(icon, k).convert("RGB")
            p = out / f"图标_1x1_{v}.png"
            big.save(p)
            save_thumb(big, thumbs / f"图标_1x1_{v}_300.png")
            print(p, big.size)


if __name__ == "__main__":
    main()
