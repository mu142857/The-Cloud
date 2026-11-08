# 连拍日志 → 每段泥芙的毛病计数：python3 niff_defects.py BURST日志
import sys, re, collections
rows = collections.defaultdict(list)
for line in open(sys.argv[1], errors='ignore'):
    m = re.match(r'BURST (\S+) f(\d+) t=([\d.]+) scene=(\S*) step=(-?\d+) room=(\S+) fade=([\d.]+) chen=\((-?\d+),(-?\d+)\) niff=\((-?\d+),(-?\d+)\) a=([\d.]+) vis=(\w+) z=(-?\d+) idx=(\d+) room=(\S+)', line)
    if m:
        g = m.groups()
        rows[g[0]].append(dict(f=int(g[1]), room=g[5], fade=float(g[6]), cx=int(g[7]), nx=int(g[9]), ny=int(g[10]), a=float(g[11]), vis=g[12] == 'true', nroom=g[15]))
tot = collections.Counter()
for tag in sorted(rows):
    r = rows[tag]
    tele = inv = flick = 0
    for i in range(1, len(r)):
        p, q = r[i - 1], r[i]
        if p['vis'] and q['vis'] and p['a'] > 0.5 and q['a'] > 0.5 and p['nroom'] == q['nroom'] and q['fade'] < 0.3 and p['fade'] < 0.3 \
                and (abs(q['nx'] - p['nx']) > 25 or abs(q['ny'] - p['ny']) > 25):
            tele += 1
    for q in r:
        if q['fade'] < 0.3 and q['nroom'] == q['room'] and (not q['vis'] or q['a'] < 0.5) and abs(q['nx'] - q['cx']) < 260:
            inv += 1
    a = [q['a'] for q in r if q['nroom'] == q['room']]
    for i in range(2, len(a)):
        if (a[i - 1] < a[i - 2] - 0.2 and a[i] > a[i - 1] + 0.2) or (a[i - 1] > a[i - 2] + 0.2 and a[i] < a[i - 1] - 0.2):
            flick += 1
    tot.update(tele=tele, invisible=inv, flicker=flick)
    print('%-28s frames=%3d teleport=%d invisible=%d flicker=%d' % (tag, len(r), tele, inv, flick))
print('TOTAL', dict(tot))
