"""「大象的画」：作者 10 岁的妹妹用蓝色圆珠笔画的大象，处理成游戏里用的图。以后改这张画只改这一个文件。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/elephant_drawing_art.py [--ink blue|gray] [--preview 目录]

原画：art/forest_story/drawing_src/elephant_sister_photo.png（作者给的照片原样存一份，别改它）。
只做「一点点处理」：线条、比例、歪歪扭扭的地方全保留（涂黑的脚、鼻子末端卷的圈、尾巴的毛、身上那一小道竖线、
地面那条线），不重画、不修正、不美化。头朝右（原画就是这样，没镜像）。
  1. 照片里抠出蓝色笔迹（蓝 - 红 > 5：纸是偏黄的灰，笔迹偏蓝），细化成骨架，按 S 倍缩小落到像素格上，再细化一遍：
     1 像素宽的线，没有灰边。涂黑的地方（三只脚、眼睛、鼻尖的两块）按面积缩，不细化。
  2. 缩小以后挤成一团的地方照着原画手排像素（hand_fixes）：鼻子（上沿、下沿、一排褶子、末端的圈）、
     嘴边那几笔（象牙）、眼睛、尾巴的粗细和末端三根毛。坐标都是原照片的像素坐标，量照片得来的。
  3. 放到游戏原来那张纸上（drawing_src/paper.png 的质感、折痕和边缘），纸在没有斜折痕穿过的地方插列加宽到 190
     （画比原来那张宽）。特写在 UI 上按 2 倍显示（story_dialogue.gd 的 closeup：400 / 宽、220 / 高取整）。
  4. 墨色两版：blue（圆珠笔的蓝，压暗一点配纸）/ gray（游戏原来铅笔的深灰紫，和旧图标同色）。--ink 选哪版进游戏，
     两版都另存在 drawing_src/ 里给作者挑。

输出 art/forest_story/：
  drawing_closeup.png   画的特写（纸 + 画）
  drawing_arc.png       只有背的那道线（同一张画布、同样的像素）：树冠缺口那一屏把它放大 3 倍叠到凹口上
  drawing_arc.json      背线两头 / 最高点的坐标（forest_story_art.py 读 drawing_arc.png 算缺口形状，再写对齐用的数）
  icon_drawing.png      背包图标（18×14：一张纸上一头朝右的小象，鼻子往前伸、末端卷圈，脚踩在地面线上）
drawing_src/：elephant_lines.png（处理后的线稿，透明底）、elephant_closeup_blue.png / _gray.png、
  icon_drawing_blue.png / _gray.png。

改了画以后要接着跑 `forest_story_art.py --treeline`：树冠缺口的弧线就是这张画的背线，要跟着重画。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art" / "forest_story"
SRC = OUT / "drawing_src"
PHOTO = SRC / "elephant_sister_photo.png"

S = 0.19                       # 照片 → 像素稿的缩放（899 宽的照片 → 171 宽）
PAPER_X, PAPER_Y = 10, -21     # 像素稿放到纸上的偏移
INK = {"blue": (58, 70, 140), "gray": (96, 92, 110)}
INK_DEFAULT = "blue"
PAPER_L, PAPER_M, PAPER_D = (226, 218, 200), (200, 190, 170), (170, 160, 142)
BACK_Y_END = 50                # 背线取到像素稿第几行（两头：屁股那条竖线、头前面那条竖线，都切在这一行）


# ================================================================ 1. 抠线、细化、缩小

def _nb(m):
    p = np.pad(m, 1)
    return [p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:], p[2:, 2:], p[2:, 1:-1], p[2:, :-2], p[1:-1, :-2], p[:-2, :-2]]


def thin(m):
    """Zhang-Suen 细化：留下 1 像素宽的骨架。"""
    m = m.copy().astype(bool)
    while True:
        changed = False
        for step in (0, 1):
            P = _nb(m)
            B = sum(x.astype(int) for x in P)
            seq = P + [P[0]]
            A = sum(((~seq[i]) & seq[i + 1]).astype(int) for i in range(8))
            if step == 0:
                c = ~(P[0] & P[2] & P[4]) & ~(P[2] & P[4] & P[6])
            else:
                c = ~(P[0] & P[2] & P[6]) & ~(P[0] & P[4] & P[6])
            d = m & (B >= 2) & (B <= 6) & (A == 1) & c
            if d.any():
                m &= ~d
                changed = True
        if not changed:
            return m


def _filt(m, *fs):
    im = Image.fromarray(m.astype(np.uint8) * 255)
    for f in fs:
        im = im.filter(f)
    return np.array(im) > 0


def auto_lines():
    """照片 → 像素稿（0 纸 / 1 线 / 2 涂黑），尺寸 = 照片 × S。"""
    a = np.array(Image.open(PHOTO).convert("RGB")).astype(int)
    ink = (a[..., 2] - a[..., 0]) > 5
    # 涂黑的地方：闭运算把涂黑的笔触连成块，只在这几个框里认
    core = _filt(ink, ImageFilter.MaxFilter(5), ImageFilter.MinFilter(9))
    boxes = [(85, 555, 185, 605), (425, 540, 515, 605), (515, 550, 595, 605),   # 三只涂黑的脚
             (615, 275, 685, 310),                                              # 眼珠
             (775, 360, 865, 425)]                                              # 鼻子末端圈上涂黑的两块
    fill = np.zeros_like(ink)
    for x0, y0, x1, y1 in boxes:
        fill[y0:y1, x0:x1] = core[y0:y1, x0:x1]
    fill &= _filt(ink, ImageFilter.MinFilter(9)) | _filt(ink, ImageFilter.MinFilter(7), ImageFilter.MaxFilter(9))
    sk = thin(ink)
    H, W = ink.shape
    w, h = int(round(W * S)), int(round(H * S))
    low = np.zeros((h, w), bool)
    ys, xs = np.nonzero(sk)
    low[np.minimum((ys * S).astype(int), h - 1), np.minimum((xs * S).astype(int), w - 1)] = True
    low = thin(low)
    fl = np.array(Image.fromarray(fill.astype(np.uint8) * 255).resize((w, h), Image.BOX)) > 110
    px = np.zeros((h, w), np.uint8)
    px[low] = 1
    px[fl] = 2
    return px


# ================================================================ 2. 手排的地方

def path_px(pts):
    """折线（照片坐标）→ 1 像素宽的格子，去掉 L 形拐角多出来的那一格。"""
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * S * 4) + 1
        for t in np.linspace(0, 1, n, endpoint=False):
            p = (int(round((x0 + (x1 - x0) * t) * S)), int(round((y0 + (y1 - y0) * t) * S)))
            if not out or out[-1] != p:
                out.append(p)
    p = (int(round(pts[-1][0] * S)), int(round(pts[-1][1] * S)))
    if out[-1] != p:
        out.append(p)
    i = 1
    while i < len(out) - 1:
        a, c = out[i - 1], out[i + 1]
        if abs(a[0] - c[0]) == 1 and abs(a[1] - c[1]) == 1:
            out.pop(i)
        else:
            i += 1
    return out


def draw(px, pts, v=1):
    for x, y in path_px(pts):
        if 0 <= y < px.shape[0] and 0 <= x < px.shape[1]:
            px[y, x] = v


def ellipse(px, cx, cy, rx, ry, v=2):
    yy, xx = np.mgrid[0:px.shape[0], 0:px.shape[1]]
    px[((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0] = v


def _removable(m, y, x):
    r = [m[y - 1, x], m[y - 1, x + 1], m[y, x + 1], m[y + 1, x + 1], m[y + 1, x], m[y + 1, x - 1], m[y, x - 1], m[y - 1, x - 1]]
    A = sum((not r[i]) and r[(i + 1) % 8] for i in range(8))
    return 2 <= sum(r) <= 6 and A == 1


def hand_fixes(px):
    """缩小以后挤成一团的地方，照着原画手排。坐标：draw / path 用照片坐标，px[y, x] 用像素稿坐标。"""
    # ---- 鼻子和嘴：整块清掉重排
    px[66:89, 112:167] = 0
    # 头的轮廓往下弯成鼻子的上沿，再往上绕成鼻尖的圈
    draw(px, [(691.7, 345), (692, 396.7), (700, 413.3), (713.3, 425), (733.3, 430), (760, 430), (780, 423.3), (790, 411.7),
              (787, 395), (786.7, 380), (793, 366.7), (805, 364)])
    # 圈的上沿：左边涂黑的一块 → 中间凹进去 → 右边涂黑的一块 → 右边往下
    draw(px, [(805, 364), (815, 372), (818.3, 390), (830, 386), (848, 385), (860, 395), (860, 406.7), (855, 423.3)])
    # 鼻子下沿：从嘴边的尖顶斜着下来，沿底边往右接到圈的右下
    draw(px, [(630, 355), (665, 400), (690, 430), (705, 442), (720, 445), (760, 445), (800, 437), (843.3, 430), (855, 423.3)])
    # 嘴 / 象牙那一团
    draw(px, [(566, 432), (600, 400), (627, 360)])                  # 嘴线（接前腿）
    draw(px, [(627, 360), (632, 400), (642, 425), (655, 440)])      # 尖顶往下那一笔
    draw(px, [(596, 382), (600, 397), (612, 412), (640, 435), (658, 447)])
    # 鼻子上的褶子
    for a, b in [((650, 385), (682, 360)), ((662, 393), (684, 377)), ((672, 404), (689, 391)), ((681, 415), (697, 401)),
                 ((692, 427), (704, 418)), ((707, 438), (714, 428)), ((727, 443), (729, 434)), ((740, 443), (742, 434)),
                 ((753, 443), (755, 434)), ((767, 441), (768, 432)), ((780, 437), (781, 428))]:
        draw(px, [a, b])
    # 鼻尖的两块涂黑（照片量的：左上 790-815×365-390，右边 830-860×383-420）
    ellipse(px, 152.5, 71.6, 2.5, 2.3)
    ellipse(px, 160.6, 76.2, 2.6, 3.2)
    # ---- 眼睛：涂黑的杏仁形，里面两小块没涂到的白
    eb = px[50:61, 115:131]
    eb[eb == 2] = 0
    for y, (a, b) in {54: (120, 124), 55: (118, 126), 56: (118, 128), 57: (120, 125)}.items():
        px[y, a:b + 1] = 2
    px[55, 120] = 0
    px[56, 124] = 0
    px[52, 117] = 1                     # 耳朵下沿被眼睛的框清掉的一格
    # ---- 尾巴：贴着屁股的轮廓长出来，粗粗一笔往左下
    for y in range(54, 81):
        xs = np.nonzero(px[y, :30])[0]
        if len(xs):
            px[y, :xs.max()] = 0
    for y in range(55, 69):
        xc = int(round(26 - 0.75 * (y - 55)))
        px[y, xc] = 2
        if 56 <= y <= 65:
            px[y, xc - 1] = 2
        if 58 <= y <= 62:               # 最粗的一段三像素
            px[y, xc - 2] = 2
    px[66, 16] = 1                      # 末端往左上翘的一根短毛
    px[57, 22] = 1                      # 两边的小刺
    px[59, 25] = 1
    for y in range(50, 55):             # 尾巴根压在背的轮廓上，那一段笔迹是双层的
        xs = np.nonzero(px[y, :32])[0]
        px[y, xs.min() - 1] = 2
    # ---- 收拾 2×2 的线团：块里挑一个去掉后不断线的像素去掉
    for _ in range(3):
        for y in range(1, px.shape[0] - 2):
            for x in range(1, px.shape[1] - 2):
                if (px[y:y + 2, x:x + 2] == 1).all():
                    for yy, xx in ((y, x), (y, x + 1), (y + 1, x), (y + 1, x + 1)):
                        if _removable(px > 0, yy, xx):
                            px[yy, xx] = 0
                            break
    # ---- 尾巴末端的三根毛（手排，避免挤成一团）
    px[69:78, 0:21] = 0
    for y, xs in {69: [15], 70: [13, 14, 15], 71: [11, 12, 14], 72: [9, 10, 13], 73: [8, 12, 14], 74: [7, 12, 14],
                  75: [11], 76: [10], 77: [10]}.items():
        px[y, xs] = 1
    # ---- 嘴边那个 X：两笔在 (115,75) 交叉
    px[75, 114] = 0
    px[76, 115] = 0
    px[76, 116] = 1
    return px


def lines():
    return hand_fixes(auto_lines())


# ================================================================ 3. 纸、背线、图标

def paper():
    """游戏原来那张纸（drawing_src/paper.png，160×110），在没有斜折痕穿过的列上各复制一列，加宽到 190。
    竖折痕（x 70~97）和右上角的折角（x > 140）都不碰，所以折痕还是 1 像素宽。"""
    p = np.array(Image.open(SRC / "paper.png").convert("RGBA"))
    dup = set(np.linspace(12, 62, 15).round().astype(int)) | set(np.linspace(102, 140, 15).round().astype(int))
    cols = []
    for x in range(p.shape[1]):
        cols += [x, x] if x in dup else [x]
    return p[:, cols]


def on_paper(px):
    """像素稿放到纸上的坐标：返回和纸同尺寸的 0/1/2 图（纸外面的墨丢掉）。"""
    P = paper()
    m = np.zeros(P.shape[:2], np.uint8)
    ys, xs = np.nonzero(px)
    for y, x in zip(ys, xs):
        Y, X = y + PAPER_Y, x + PAPER_X
        if 0 <= Y < m.shape[0] and 0 <= X < m.shape[1] and P[Y, X, 3] > 0:
            m[Y, X] = px[y, x]
    return m


def closeup(m, ink):
    img = paper().copy()
    img[m > 0, :3] = ink
    return img


def back_line(px):
    """背的那道线：从背上连着的轮廓，切在 BACK_Y_END 这一行以上（左头是屁股那条竖线，右头是头前面那条竖线）。
    只要线（1），不要尾巴根的涂黑（2）、耳朵、眼睛（不连着）。返回像素稿坐标的 bool 图。"""
    line = (px == 1)
    line[BACK_Y_END + 1:] = False
    ys, xs = np.nonzero(line)
    top = ys.min()
    seed = (top, int(xs[ys == top].mean()))
    out = np.zeros_like(line)
    stack = [seed]
    while stack:
        y, x = stack.pop()
        if 0 <= y < line.shape[0] and 0 <= x < line.shape[1] and line[y, x] and not out[y, x]:
            out[y, x] = True
            stack += [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    return out


def icon(ink):
    """背包图标 18×14：一张纸（右边一列、底下一行是纸的暗边，右上角折过一小角），上面一头朝右的小象剪影：
    平平的长背、大大的 U 形耳朵（纸的暗色）、四条腿涂黑、尾巴末端分叉、鼻子往前伸末端卷一个圈、脚踩在地面线上，
    地面线过了前腿往右下斜。"""
    W, H = 18, 14
    a = np.zeros((H, W, 4), np.uint8)
    a[:, :] = PAPER_L + (255,)
    a[:, W - 1] = PAPER_M + (255,)
    a[H - 1, :] = PAPER_M + (255,)
    a[H - 1, W - 1] = PAPER_D + (255,)
    a[1, W - 3] = PAPER_D + (255,)
    cells = {(x, 3) for x in range(4, 12)}                                # 背
    for y in range(4, 8):
        cells |= {(x, y) for x in range(3, 13)}                           # 身子（头在右边）
    for y in (8, 9):
        cells |= {(3, y), (4, y), (8, y), (9, y), (11, y), (12, y)}       # 腿
    cells |= {(2, 5), (1, 6), (1, 7), (0, 7)}                             # 尾巴，末端两根毛
    cells |= {(13, 7), (14, 7), (15, 7), (16, 7), (14, 6), (16, 6), (14, 5), (15, 5)}   # 鼻子和末端的圈
    cells |= {(x, 10) for x in range(1, 13)} | {(x, 11) for x in range(13, 17)}       # 地面线
    for x, y in cells:
        a[y, x] = ink + (255,)
    for x, y in ((8, 4), (8, 5), (9, 6), (10, 6), (11, 5)):              # 耳朵：U，右边那笔短
        a[y, x] = PAPER_D + (255,)
    return a


# ================================================================ 输出

def build(ink_name=INK_DEFAULT):
    px = lines()
    m = on_paper(px)
    lines_png = np.zeros(m.shape + (4,), np.uint8)
    lines_png[m > 0] = INK["gray"] + (255,)
    Image.fromarray(lines_png).save(SRC / "elephant_lines.png")
    for k, v in INK.items():
        Image.fromarray(closeup(m, v)).save(SRC / f"elephant_closeup_{k}.png")
        Image.fromarray(icon(v)).save(SRC / f"icon_drawing_{k}.png")
    ink = INK[ink_name]
    cl = closeup(m, ink)
    Image.fromarray(cl).save(OUT / "drawing_closeup.png")
    Image.fromarray(icon(ink)).save(OUT / "icon_drawing.png")
    # 背线：同一张画布、同样的像素
    bl = on_paper(back_line(px).astype(np.uint8)) > 0
    arc = np.zeros_like(cl)
    arc[bl] = cl[bl]
    Image.fromarray(arc).save(OUT / "drawing_arc.png")
    ys, xs = np.nonzero(bl)
    print(f"drawing_closeup {cl.shape[1]}x{cl.shape[0]}  墨 {ink_name}  背线 x {xs.min()}~{xs.max()}  y {ys.min()}~{ys.max()}")
    return px, m


def preview(d, px, m):
    """原画和处理后并排（4 倍）、两版墨色、图标。"""
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for k, v in INK.items():
        cl = Image.fromarray(closeup(m, v))
        big = cl.resize((cl.width * 4, cl.height * 4), Image.NEAREST)
        ph = Image.open(PHOTO).convert("RGB")
        ph = ph.resize((int(ph.width * big.height / ph.height), big.height), Image.LANCZOS)
        c = Image.new("RGB", (ph.width + big.width + 24, big.height + 16), (34, 40, 37))
        c.paste(ph, (8, 8))
        c.paste(big, (ph.width + 16, 8), big)
        p = d / f"compare_{k}_x4.png"
        c.save(p)
        out.append(p)
    ic = [Image.fromarray(icon(v)) for v in INK.values()]
    c = Image.new("RGBA", (2 * 18 * 8 + 24, 14 * 8 + 16), (34, 40, 37, 255))
    for i, im in enumerate(ic):
        c.alpha_composite(im.resize((18 * 8, 14 * 8), Image.NEAREST), (8 + i * (18 * 8 + 8), 8))
    p = d / "icon_x8.png"
    c.save(p)
    out.append(p)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ink", choices=list(INK), default=INK_DEFAULT, help="哪一版墨色进游戏（两版都另存在 drawing_src/）")
    ap.add_argument("--preview", help="把对比图存到这个目录")
    args = ap.parse_args()
    px, m = build(args.ink)
    if args.preview:
        for p in preview(Path(args.preview), px, m):
            print("preview", p)
