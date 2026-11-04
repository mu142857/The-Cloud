# 连拍 → 拼图：python3 sheet.py 连拍目录 BURST日志 输出目录 [列数] [缩放]
import sys, os, re, glob
from PIL import Image, ImageDraw, ImageFont
src, log, out = sys.argv[1], sys.argv[2], sys.argv[3]
cols = int(sys.argv[4]) if len(sys.argv) > 4 else 8
k = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
os.makedirs(out, exist_ok=True)
info = {}
for line in open(log, errors='ignore'):
    m = re.match(r'BURST (\S+) f(\d+) t=([\d.]+) scene=(\S*) step=(-?\d+) room=(\S+) fade=([\d.]+) (.*)', line)
    if m:
        tag, f = m.group(1), int(m.group(2))
        rest = m.group(8)
        nm = re.search(r'niff=\((-?\d+),(-?\d+)\) a=([\d.]+) vis=(\w+) z=(-?\d+) idx=(\d+) room=(\S+)', rest)
        info[(tag, f)] = (m.group(4), m.group(5), float(m.group(7)), nm.groups() if nm else None, m.group(6))
try:
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 11)
except Exception:
    font = ImageFont.load_default()
for d in sorted(glob.glob(os.path.join(src, '*'))):
    tag = os.path.basename(d)
    frames = sorted(glob.glob(os.path.join(d, 'f*.png')))
    if not frames:
        continue
    im0 = Image.open(frames[0])
    w, h = int(im0.width * k), int(im0.height * k)
    lab = 26
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * w, rows * (h + lab)), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for i, fp in enumerate(frames):
        fi = int(os.path.basename(fp)[1:4])
        im = Image.open(fp).convert('RGB').resize((w, h), Image.NEAREST)
        x, y = (i % cols) * w, (i // cols) * (h + lab)
        sheet.paste(im, (x, y + lab))
        inf = info.get((tag, fi))
        t1 = 'f%03d' % fi
        t2 = ''
        if inf:
            sc, st, fade, nf, room = inf
            t1 += ' %s#%s fade%.1f' % (sc[:14], st, fade)
            if nf:
                t2 = 'niff x%s a%.2f %s z%s %s' % (nf[0], float(nf[2]), 'V' if nf[3] == 'true' else '-', nf[4], nf[6][:10])
        dr.text((x + 2, y + 1), t1, fill=(230, 230, 120), font=font)
        dr.text((x + 2, y + 13), t2, fill=(140, 220, 230), font=font)
    sheet.save(os.path.join(out, tag + '.png'))
    print(tag, len(frames), sheet.size)
