"""蛇女走路（作者 11-02 用 dotpict 画的 9 帧，150ms 一帧）→ art/characters/snake/snake_walk.png + 每帧锚点。

源：art/characters/snake/src/snake_walk.gif（480×480，dotpict 导出放大 10 倍）。按每格中心取样还原成 48×48。
帧 0~2 = 从盘着到展开（头往前探、尾巴拉长），帧 3~8 = 滑行循环。
锚点 x = 身体中线：取头那一行（第 15 行）实心段的中点 + 2.5，和待机图 snake.png 的 FOOT.x=17 对得上
（待机第 15 行是 8~21，中点 14.5）。打印出来的 WALK_FOOT_X 抄进 scripts/npc_snake.gd。
"""
from PIL import Image

SRC = "art/characters/snake/src/snake_walk.gif"
OUT = "art/characters/snake/snake_walk.png"
N, SCALE = 48, 10

im = Image.open(SRC)
sheet = Image.new("RGBA", (N * im.n_frames, N))
foot = []
for i in range(im.n_frames):
    im.seek(i)
    f = im.convert("RGBA")
    n = Image.new("RGBA", (N, N))
    for y in range(N):
        for x in range(N):
            p = f.getpixel((x * SCALE + SCALE // 2, y * SCALE + SCALE // 2))
            n.putpixel((x, y), p if p[3] > 0 else (0, 0, 0, 0))
    xs = [x for x in range(N) if n.getpixel((x, 15))[3] > 0]
    foot.append(round((min(xs) + max(xs)) / 2 + 2.5))
    sheet.paste(n, (i * N, 0))
sheet.save(OUT)
print("WALK_FOOT_X :=", foot)
