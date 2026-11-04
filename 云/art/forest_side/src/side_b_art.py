"""第一关支线 3、4（side-b）的图。跑：python3 art/forest_side/src/side_b_art.py

出这些（都在 art/forest_side/）：
  toucan_beak.png   大嘴鸟 5 帧（27×29，和 art/characters/toucan/toucan.png 同排布、同锚点）：
                    0 合嘴（原图）、1~3 下嘴一点点张开（嘴里露出深红）、4 抛果子（张嘴 2 档 + 上半身抬 1 像素）。
                    只从原图派生，原图一个像素都不改。
  fruit.png         果子 9×9 两格：0 红果（抛的、接住的）、1 灰果（头顶计数还没接到的那几格）
  prints.png        地上的脚印 5×4，三列：0 鹿（两瓣，原样取自 art/forest_story/hoofprints.png 第一格）、1 鸟（三趾）、
                    2 兔子（一长条）；两行：0 平常（深色坑）、1 亮（踩对了，暖光）
  icon_toucan_feather.png   大嘴鸟的尾羽（橙黄，根上一点黑）
  icon_antler_cloth.png     鹿角上的布条（照 cloth.png 的红布颜色）
不描边、光从左上来、硬边、没有半透明。
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "art/forest_side"
TOUCAN = ROOT / "art/characters/toucan/toucan.png"
HOOF = ROOT / "art/forest_story/hoofprints.png"


def ascii_img(rows, pal):
    h, w = len(rows), max(len(r) for r in rows)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != ".":
                im.putpixel((x, y), pal[ch] + (255,))
    return im


# ---------------------------------------------------------------- 大嘴鸟张嘴
MOUTH = (167, 39, 81)          # 原图里喉咙那块深红：嘴里的颜色


def lower_jaw(x, y):
    # 下嘴：第 7 行 x≤8、第 8 行 x≤9、第 9 行 x≤1（嘴尖那一点）；铰链在 x≈10
    return (y == 7 and x <= 8) or (y == 8 and x <= 9) or (y == 9 and x <= 1)


def open_beak(src, k):
    im = src.copy()
    px = src.load()
    jaw = [(x, y, px[x, y]) for y in range(7, 10) for x in range(0, 11) if lower_jaw(x, y) and px[x, y][3]]
    for x, y, _ in jaw:
        im.putpixel((x, y), (0, 0, 0, 0))
    shift = {x: round(k * (10 - x) / 9.0) for x in range(11)}
    # 嘴里：上嘴下沿到下嘴新位置之间填深红
    for x in range(1, 10):
        s = shift[x]
        for dy in range(s):
            y = 7 + dy
            if im.getpixel((x, y))[3] == 0:
                im.putpixel((x, y), MOUTH + (255,))
    for x, y, c in jaw:
        im.putpixel((x, y + shift[x]), c)
    return im


def lift_top(im, rows=18, d=1):
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    top = im.crop((0, 0, im.width, rows))
    out.paste(im.crop((0, rows, im.width, im.height)), (0, rows))
    out.alpha_composite(top, (0, -d))
    # 抬起来以后第 rows-1 行空出来的地方用原图那一行补上（身子不断开）
    for x in range(im.width):
        if out.getpixel((x, rows - 1))[3] == 0 and im.getpixel((x, rows - 1))[3]:
            out.putpixel((x, rows - 1), im.getpixel((x, rows - 1)))
    return out


def toucan_sheet():
    src = Image.open(TOUCAN).convert("RGBA")
    frames = [src, open_beak(src, 1), open_beak(src, 2), open_beak(src, 3), lift_top(open_beak(src, 2))]
    w, h = src.size
    sheet = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.alpha_composite(f, (i * w, 0))
    sheet.save(OUT / "toucan_beak.png")
    return sheet


# ---------------------------------------------------------------- 果子
FRUIT = [
    ".....L...",
    "....lL...",
    "..rRRRr..",
    ".rRWWRRr.",
    ".rRWRRRr.",
    ".rRRRRRd.",
    ".drRRRdd.",
    "..ddddd..",
    ".........",
]
FRUIT_PAL = {"d": (118, 30, 52), "r": (170, 40, 58), "R": (214, 58, 62), "W": (255, 150, 120),
             "l": (63, 92, 60), "L": (104, 136, 78)}
FRUIT_DIM = {"d": (62, 70, 68), "r": (78, 88, 84), "R": (92, 104, 98), "W": (112, 124, 116),
             "l": (70, 80, 76), "L": (88, 98, 92)}


def fruit_sheet():
    a = ascii_img(FRUIT, FRUIT_PAL)
    b = ascii_img(FRUIT, FRUIT_DIM)
    sheet = Image.new("RGBA", (18, 9), (0, 0, 0, 0))
    sheet.alpha_composite(a, (0, 0))
    sheet.alpha_composite(b, (9, 0))
    sheet.save(OUT / "fruit.png")
    return sheet


# ---------------------------------------------------------------- 脚印
PRINT_PAL = {"K": (10, 16, 13), "D": (20, 27, 21), "S": (14, 21, 17), "M": (34, 54, 43), "L": (63, 80, 65), "H": (80, 92, 79)}
PRINT_LIT = {"K": (122, 92, 52), "D": (150, 116, 66), "S": (136, 104, 60), "M": (190, 150, 86), "L": (232, 200, 130),
             "H": (252, 232, 180)}
BIRD = [
    "....H",
    "K.K.K",
    ".KDK.",
    "..S..",
]
RABBIT = [
    "....H",
    "LKKKK",
    ".DKKD",
    ".....",
]


def hoof_rows():
    im = Image.open(HOOF).convert("RGBA")
    inv = {v: k for k, v in PRINT_PAL.items()}
    rows = []
    for y in range(4):
        r = ""
        for x in range(5):
            p = im.getpixel((x, y))
            r += "." if p[3] == 0 else inv[p[:3]]
        rows.append(r)
    return rows


def prints_sheet():
    kinds = [hoof_rows(), BIRD, RABBIT]
    sheet = Image.new("RGBA", (15, 8), (0, 0, 0, 0))
    for i, rows in enumerate(kinds):
        sheet.alpha_composite(ascii_img(rows, PRINT_PAL), (i * 5, 0))
        sheet.alpha_composite(ascii_img(rows, PRINT_LIT), (i * 5, 4))
    sheet.save(OUT / "prints.png")
    return sheet


# ---------------------------------------------------------------- 图标
FEATHER = [
    "..........hY",
    ".........hYY",
    "........hYYO",
    ".......hYYOO",
    "......hYYOO.",
    ".....hYYOO..",
    "....hYYOO...",
    "...hYOOO....",
    "..hOOOo.....",
    "..ooo.......",
    ".kk.........",
    "kk..........",
]
FEATHER_PAL = {"h": (255, 226, 140), "Y": (255, 183, 42), "O": (226, 137, 42), "o": (180, 96, 34),
               "k": (20, 19, 26)}
CLOTH = [
    "..RRR..RRR..",
    ".RrrrRRrrrR.",
    ".RrddRRddrd.",
    "..drrRRrrd..",
    "....dRRd....",
    "...dRrrRd...",
    "..dRr..rRd..",
    "..dr....rd..",
    ".dr......rd.",
    ".d........d.",
]
CLOTH_PAL = {"R": (138, 75, 62), "r": (120, 60, 51), "d": (98, 48, 43)}


def icons():
    ascii_img(FEATHER, FEATHER_PAL).save(OUT / "icon_toucan_feather.png")
    ascii_img(CLOTH, CLOTH_PAL).save(OUT / "icon_antler_cloth.png")


def preview(path):
    items = [Image.open(OUT / n).convert("RGBA") for n in
             ["toucan_beak.png", "fruit.png", "prints.png", "icon_toucan_feather.png", "icon_antler_cloth.png"]]
    s = 8
    W = sum(i.width * s + 16 for i in items)
    H = max(i.height for i in items) * s + 16
    out = Image.new("RGBA", (W, H), (127, 152, 140, 255))   # 雾色底
    x = 8
    for i in items:
        out.alpha_composite(i.resize((i.width * s, i.height * s), Image.NEAREST), (x, 8))
        x += i.width * s + 16
    out.save(path)


# ---------------------------------------------------------------- 雾里的蹄印（11-04 改：大一点、亮一点，作者看不清原来那串）
# hoof_trail.png：13×5 三格。0 = 踩过的（暖色、不动）、1 = 下一个（更亮，代码里让它一明一暗地呼吸）、2 = 还没轮到的（暗，备用）
# hoof_glow.png：下一个蹄印上方那团光（41×10，底边贴地的半个椭圆，三圈），画在雾上面，代码里 4 档透明度一明一暗
HOOF_BIG = [
    "..aAa...aAa..",
    ".aBBBa.aBBBa.",
    ".BBBBB.BBBBB.",
    "..bBb...bBb..",
    "...b.....b...",
]
HOOF_LIT = {"a": (236, 196, 128), "A": (255, 226, 160), "B": (206, 148, 78), "b": (150, 98, 52)}
HOOF_NEXT = {"a": (255, 240, 200), "A": (255, 252, 232), "B": (250, 208, 132), "b": (212, 150, 84)}
HOOF_DIM = {"a": (96, 108, 92), "A": (112, 124, 106), "B": (70, 82, 70), "b": (52, 62, 54)}


def trail_sheet():
    sheet = Image.new("RGBA", (39, 5), (0, 0, 0, 0))
    for i, pal in enumerate([HOOF_LIT, HOOF_NEXT, HOOF_DIM]):
        sheet.alpha_composite(ascii_img(HOOF_BIG, pal), (i * 13, 0))
    sheet.save(OUT / "hoof_trail.png")
    # 光：从地面往上冒的半个椭圆（底边贴地），里圈暖白、外圈接近雾色，看着是雾里透出来的一团光，不是一块盘子
    w, h = 41, 10
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y in range(h):
        for x in range(w):
            dx = (x - (w - 1) / 2) / (w / 2)
            dy = (h - 1 - y) / h
            r = dx * dx + dy * dy
            if r <= 0.22:
                glow.putpixel((x, y), (250, 232, 186, 255))
            elif r <= 0.55:
                glow.putpixel((x, y), (214, 204, 164, 255))
            elif r <= 1.0:
                glow.putpixel((x, y), (168, 178, 150, 255))
    glow.save(OUT / "hoof_glow.png")


def trail_mock(path, chen_x=4310, nxt=4):
    """游戏尺寸的示意：坡地主层地面 + 雾（晨身边一圈）+ 踩过的蹄印 + 下一个发光的蹄印 + 晨。只是摆位预览，不是截图。"""
    main = Image.open(ROOT / "art/forest/main.png").convert("RGBA")
    chen_sheet = Image.open(ROOT / "art/characters/chen/chen_oscar.png").convert("RGBA")
    trail_img = Image.open(OUT / "hoof_trail.png").convert("RGBA")
    glow_img = Image.open(OUT / "hoof_glow.png").convert("RGBA")
    x0w = chen_x - 240
    scr = Image.new("RGBA", (480, 270), (127, 152, 140, 255))
    for sx in range(480):
        mx = (x0w + sx) % 960
        scr.paste(main.crop((mx, 0, mx + 1, 270)), (sx, 0), main.crop((mx, 0, mx + 1, 270)))
    G = 228
    start, offs = 4220, [0, 34, 70, 50, 90, 130, 172, 212]
    def put(img, wx, y):
        scr.alpha_composite(img, (wx - x0w - img.width // 2, y))
    hoof = lambda c: trail_img.crop((c * 13, 0, c * 13 + 13, 5))
    for o in offs[:nxt + 1]:
        put(hoof(0), start + o, G - 1)
    # 晨（待机第一帧，脚底大约在帧的 (28, 57)）
    fr = chen_sheet.crop((7 * 68, 0, 8 * 68, 60))
    scr.alpha_composite(fr, (chen_x - x0w - 28, G + 1 - 57))
    # 雾：圈外浓、圈里淡（分档）
    fog = Image.new("RGBA", (480, 270), (0, 0, 0, 0))
    cx, cy = 240, G - 24
    for y in range(270):
        for x in range(480):
            d = (((x - cx) ** 2 + ((y - cy) * 1.35) ** 2) ** 0.5)
            e = min(max((d - 64) / 44, 0), 1)
            a = 0.85 * (0.14 + (0.84 - 0.14) * e)
            a = round(a * 10) / 10
            fog.putpixel((x, y), (127, 152, 140, int(a * 255)))
    scr.alpha_composite(fog)
    # 下一个：光和蹄印画在雾上面
    nx = start + offs[nxt + 1]
    g = glow_img.copy()
    g.putalpha(g.getchannel("A").point(lambda v: v * 50 // 100))
    put(g, nx, G - 8)
    put(hoof(1), nx, G - 1)
    scr.save(path)
    scr.resize((960, 540), Image.NEAREST).save(str(path).replace(".png", "_2x.png"))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    toucan_sheet()
    fruit_sheet()
    prints_sheet()
    trail_sheet()
    icons()
    import sys
    if len(sys.argv) > 1:
        preview(sys.argv[1])
        trail_mock(sys.argv[1].replace(".png", "_trail.png"))
    print("ok", OUT)
