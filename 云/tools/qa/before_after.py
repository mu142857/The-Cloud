# 修前 / 修后对照：python3 ba_sheet.py 修前目录 修前日志 修后目录 修后日志 输出目录 [每几帧取一张] [最多几张]
import sys, os, re, glob
from PIL import Image, ImageDraw, ImageFont
bdir, blog, adir, alog, out = sys.argv[1:6]
step = int(sys.argv[6]) if len(sys.argv) > 6 else 2
maxn = int(sys.argv[7]) if len(sys.argv) > 7 else 24
os.makedirs(out, exist_ok=True)
def load(log):
    info = {}
    for line in open(log, errors='ignore'):
        m = re.match(r'BURST (\S+) f(\d+) t=([\d.]+) scene=(\S*) step=(-?\d+) room=(\S+) fade=([\d.]+) (.*)', line)
        if m:
            nm = re.search(r'niff=\((-?\d+),(-?\d+)\) a=([\d.]+) vis=(\w+)', m.group(8))
            info[(m.group(1), int(m.group(2)))] = (float(m.group(7)), nm.groups() if nm else None)
    return info
bi, ai = load(blog), load(alog)
try:
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 11)
    big = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 16)
except Exception:
    font = big = ImageFont.load_default()
W, H, LAB, COLS = 240, 135, 14, 8
def strip(d, info, tag):
    fs = sorted(glob.glob(os.path.join(d, tag, 'f*.png')))[::step][:maxn]
    rows = max(1, (len(fs) + COLS - 1) // COLS)
    im = Image.new('RGB', (COLS * W, rows * (H + LAB)), (18, 18, 18))
    dr = ImageDraw.Draw(im)
    for i, f in enumerate(fs):
        fi = int(os.path.basename(f)[1:4])
        t = Image.open(f).convert('RGB').resize((W, H), Image.NEAREST)
        x, y = (i % COLS) * W, (i // COLS) * (H + LAB)
        im.paste(t, (x, y + LAB))
        inf = info.get((tag, fi))
        s = 'f%03d' % fi
        if inf:
            s += ' fade%.1f' % inf[0]
            if inf[1]:
                s += ' niff x%s a%.1f%s' % (inf[1][0], float(inf[1][2]), '' if inf[1][3] == 'true' else ' hid')
        dr.text((x + 2, y + 1), s, fill=(230, 230, 140), font=font)
    return im
tags = sorted(set(os.path.basename(p) for p in glob.glob(os.path.join(adir, '*'))) | set(os.path.basename(p) for p in glob.glob(os.path.join(bdir, '*'))))
for tag in tags:
    parts = []
    for name, d, info, col in [('BEFORE', bdir, bi, (240, 120, 120)), ('AFTER', adir, ai, (120, 230, 140))]:
        if not os.path.isdir(os.path.join(d, tag)):
            continue
        s = strip(d, info, tag)
        head = Image.new('RGB', (s.width, 24), (40, 40, 40))
        ImageDraw.Draw(head).text((6, 3), '%s  %s  (every %d frames = %.1fs)' % (name, tag, step, step * 0.1), fill=col, font=big)
        parts += [head, s]
    if not parts:
        continue
    sheet = Image.new('RGB', (COLS * W, sum(p.height for p in parts)), (0, 0, 0))
    y = 0
    for p in parts:
        sheet.paste(p, (0, y)); y += p.height
    sheet.save(os.path.join(out, tag + '.png'))
    print(tag, sheet.size)
