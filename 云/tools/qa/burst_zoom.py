# python3 zoom.py 帧目录 起 止 输出.png [列数] [步长]：原尺寸（缩到 480 宽）拼几帧细看
import sys, glob, os
from PIL import Image, ImageDraw
d, a, b, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
cols = int(sys.argv[5]) if len(sys.argv) > 5 else 4
step = int(sys.argv[6]) if len(sys.argv) > 6 else 1
fs = [os.path.join(d, 'f%03d.png' % i) for i in range(a, b + 1, step) if os.path.exists(os.path.join(d, 'f%03d.png' % i))]
W, H = 480, 270
rows = (len(fs) + cols - 1) // cols
sh = Image.new('RGB', (cols * W, rows * (H + 12)), (30, 30, 30))
dr = ImageDraw.Draw(sh)
for i, f in enumerate(fs):
    im = Image.open(f).convert('RGB')
    if im.width != W:
        im = im.resize((W, H), Image.NEAREST)
    x, y = (i % cols) * W, (i // cols) * (H + 12)
    sh.paste(im, (x, y + 12))
    dr.text((x + 3, y), os.path.basename(f), fill=(255, 255, 0))
sh.save(out)
print(out, sh.size)
