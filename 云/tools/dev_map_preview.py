"""F8 传送页地图预览：和 scripts/dev_panel.gd 的 _map_geo / _map_layout 同一套算法、读同样的数据，每章画一张（放大 3 倍），
不用开 Godot。章节从 scripts/chapter_flow.gd 的 CHAPTERS 读，新加的章节、房间自己会出来。dev_panel.gd 改了算法这里也改。
用法：python3 tools/dev_map_preview.py <云的目录> <输出目录> [章:房间（画成晨在的那间，亮黄）]"""
import json, os, re, sys
from PIL import Image, ImageDraw, ImageFont

ROOT, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

MAP_W = 380 - 16          # 地图区宽（面板 380 宽，两边各留 8）
ROW = 24                  # 一行多高
BOX_H = 18
GAP = 3
FS = 12
SCALE = 3

HERE = sys.argv[3].split(":") if len(sys.argv) > 3 else ["", ""]

# chapter_flow.gd 的 CHAPTERS：章 → 剧本、room
cf = open(os.path.join(ROOT, "scripts/chapter_flow.gd"), encoding="utf-8").read()
cf = cf[cf.find("const CHAPTERS"):]
CHAPTERS, CH_ROOM = {}, {}
for m in re.finditer(r'^\t"(\w+)": \{"story": "res://([^"]+)"(.*)$', cf, re.M):
    CHAPTERS[m.group(1)] = m.group(2)
    r = re.search(r'"room": "(\w+)"', m.group(3))
    if r:
        CH_ROOM[m.group(1)] = r.group(1)

# room_stage.gd DEFAULT（没 room.json 时）
src = open(os.path.join(ROOT, "scripts/room_stage.gd"), encoding="utf-8").read()
STAGE_DEFAULT = {
    "river_bank": {"size": [1280, 270], "origin": [0, 0]},
    "market": {"size": [1100, 270], "origin": [880, -270]},
    "stairwell": {"size": [480, 270], "origin": [2400, -270]},
    "oldstreet": {"size": [1200, 270], "origin": [3000, 0]},
    "warehouse": {"size": [640, 270], "origin": [3000, 270]},
    "southbridge": {"size": [1500, 270], "origin": [6000, 0]},
    "river_home": {"kind": "house", "host": "river_bank", "x": 1040, "size": [420, 200]},
}
assert '"southbridge": {"size": [1500, 270], "origin": [6000, 0]' in src, "room_stage DEFAULT 改了，同步一下"

wsrc = open(os.path.join(ROOT, "scripts/story_world.gd"), encoding="utf-8").read()
FOREST_MK = {k: int(v) for k, v in re.findall(r'"(\w+)": (-?\d+)', wsrc[wsrc.find("const DEFAULT_MARKERS"):wsrc.find("}", wsrc.find("const DEFAULT_MARKERS"))])}

_dn = json.load(open(os.path.join(ROOT, "data/dev_names.json"), encoding="utf-8"))
names = _dn["rooms"]
CH_NAME = {c: _dn.get("chapters", {}).get(c, {"final": "终章"}.get(c, c)) for c in CHAPTERS}
font = ImageFont.truetype(os.path.join(ROOT, "fonts/PixelFont_ui.ttf"), FS)


def peek(rid):
    c = {}
    for d in ("art/river_city/%s/", "art/%s/"):
        p = os.path.join(ROOT, d % rid, "room.json")
        if os.path.exists(p):
            c = json.load(open(p, encoding="utf-8"))
            break
    for k, v in STAGE_DEFAULT.get(rid, {}).items():
        c.setdefault(k, v)
    return c


def label(rid):
    return re.sub(r"（.*?）", "", names.get(rid, rid))


def mk_x(v):
    if isinstance(v, dict):
        v = v.get("x")
    elif isinstance(v, list) and v:
        v = v[0]
    return float(v) if isinstance(v, (int, float)) else None


def chapter_rooms(ch, d):
    rooms = list(d.get("rooms", []))
    if not rooms:
        rooms = [CH_ROOM.get(ch, "forest")]
        for h in d.get("hotspots", []):
            if isinstance(h, dict) and h.get("room", "forest") not in rooms:
                rooms.append(h.get("room", "forest"))
    return rooms


def geo(ch, d):
    """每个房间：{out: True, x, y, w} 或 {out: False, host, door(房间里的 x), w}"""
    rooms = chapter_rooms(ch, d)
    smk = d.get("markers", {}) if isinstance(d.get("markers"), dict) else {}
    g = {}
    for r in rooms:
        c = peek(r) if r not in ("forest", "treehouse", "cockpit") else {}
        sz = c.get("size", [480, 270])
        w = float(sz[0]) if isinstance(sz, list) and sz else 480.0
        if r == "forest":
            x0 = FOREST_MK["wall_left"]
            g[r] = {"out": True, "x": x0, "y": 0.0, "w": FOREST_MK["wall_right"] - x0}
        elif c.get("kind") == "house" and c.get("host") in rooms:
            g[r] = {"out": False, "host": c["host"], "door": float(c.get("x", 0)), "w": w}
        elif isinstance(c.get("origin"), list):
            g[r] = {"out": True, "x": float(c["origin"][0]), "y": float(c["origin"][1]), "w": w}
        else:
            g[r] = {"out": None, "w": w}
    # 没坐标的：剧本里哪个房间的 hotspot 换到它（门口），就挨着那个房间
    for h in d.get("hotspots", []):
        if not isinstance(h, dict):
            continue
        src_r = h.get("room", "forest")
        for st in d.get("scenes", {}).get(h.get("scene", ""), []):
            if isinstance(st, dict) and st.get("do") == "fade_to":
                dst = st.get("room", "")
                # 门在 src 里、通到 dst：dst 还没位置才挂过去；src 自己也没位置时，只挂剧本 rooms 里排在它后面的（外面的房间先写），不绕成圈
                if dst in g and g[dst]["out"] is None and dst != src_r and src_r in g and \
                        (g[src_r]["out"] is not None or rooms.index(src_r) < rooms.index(dst)) and not _under(g, src_r, dst):
                    g[dst] = {"out": False, "host": src_r, "door": door_x(src_r, h.get("at"), smk, g), "w": g[dst]["w"]}
                break
    for r in g:
        if g[r]["out"] is None:
            g[r] = {"out": True, "x": 0.0, "y": 0.0, "w": g[r]["w"], "loose": True}
    return rooms, g


def _under(g, r, top):
    """r 是不是挂在 top 底下（顺着 host 往上找）"""
    seen = set()
    while r in g and g[r]["out"] is False and r not in seen:
        seen.add(r)
        r = g[r]["host"]
        if r == top:
            return True
    return False


def door_x(host, at, smk, g):
    if not isinstance(at, str):
        return g[host]["w"] / 2
    if host == "forest":
        v = mk_x(FOREST_MK.get(at, smk.get(at)))
        return v - FOREST_MK["wall_left"] if v is not None else g[host]["w"] / 2
    c = peek(host)
    v = mk_x(c.get("markers", {}).get(at))
    if v is None:
        v = mk_x(smk.get(at))
        if v == 0:
            v = None
    return v if v is not None else g[host]["w"] / 2


def text_w(s):
    return font.getbbox(s)[2] if s else 0


def layout(rooms, g):
    """返回 [{room, x, y, w, inside, host, door}]：和 dev_panel.gd _map_layout 一样。
    室外：按 origin 竖着分行（每 270 一行）、横着按比例；室内：在门口所在房间的下面半行，方块中心对着门。
    方块至少放得下名字，挤了就往右推；整行超宽就把比例缩小再排，还不行就折行"""
    lv = {}
    for _ in range(len(rooms) + 1):
        for r in rooms:
            q = g[r]
            if q["out"]:
                lv[r] = q["y"] / 270.0
            elif q["host"] in lv:
                lv[r] = lv[q["host"]] + 0.5
    outs = [r for r in rooms if g[r]["out"] and not g[r].get("loose")]
    lo = min([g[r]["x"] for r in outs] or [0.0])
    hi = max([g[r]["x"] + g[r]["w"] for r in outs] or [1.0])
    levels = sorted(set(lv.values()))
    sx = MAP_W / max(hi - lo, 1.0)
    for _try in range(12):
        box = {}
        over = False
        for L in levels:
            row = []
            for r in rooms:
                if lv.get(r) != L:
                    continue
                q = g[r]
                bw = text_w(label(r)) + 8
                if q["out"] and not q.get("loose"):
                    bw = max(q["w"] * sx, bw)
                    bx = (q["x"] - lo) * sx
                elif q["out"]:
                    bx = 1e9                                   # 没坐标的：排在这一行最后
                else:
                    hb = box[q["host"]]
                    door = hb[0] + hb[1] * min(max(q["door"] / max(g[q["host"]]["w"], 1.0), 0.0), 1.0)
                    bx = door - bw / 2
                    hb_door = door
                row.append([bx, bw, r, hb_door if not q["out"] else None])
            row.sort(key=lambda a: (a[0], rooms.index(a[2])))
            end = -GAP
            for a in row:
                a[0] = max(a[0] if a[0] < 1e8 else end + GAP + 4, end + GAP, 0)
                end = a[0] + a[1]
                over = over or end > MAP_W
                box[a[2]] = a
        if not over:
            break
        sx *= 0.85
    out = []
    line = 0
    for L in levels:
        x_off = 0
        for r in rooms:
            pass
        row = sorted([box[r] for r in rooms if lv.get(r) == L], key=lambda a: a[0])
        for a in row:
            bx = a[0] - x_off
            if bx + a[1] > MAP_W and bx > 0:                  # 实在挤不下：折到下一行
                line += 1
                x_off = a[0]
                bx = 0
            q = g[a[2]]
            out.append({"room": a[2], "x": round(bx), "y": line * ROW, "w": round(a[1]), "inside": not q["out"],
                        "host": q.get("host", ""), "door": None if a[3] is None else round(a[3])})
        line += 1
    return out, line * ROW


BG = (5, 13, 10)
for ch, p in CHAPTERS.items():
    d = json.load(open(os.path.join(ROOT, p), encoding="utf-8"))
    rooms, g = geo(ch, d)
    boxes, h = layout(rooms, g)
    W, H = MAP_W + 16, h + 40
    im = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(im)
    tx = 8
    for c2 in CHAPTERS:
        t = CH_NAME[c2]
        tw = text_w(t) + 8
        dr.rectangle([tx, 4, tx + tw, 4 + 16], fill=(70, 110, 90) if c2 == ch else (22, 34, 30))
        dr.text((tx + 4, 6), t, font=font, fill=(223, 232, 226))
        tx += tw + 3
    oy = 28
    by = {b["room"]: b for b in boxes}
    for b in boxes:
        if b["inside"] and b["host"] in by:
            hb = by[b["host"]]
            x = 8 + min(max(b["door"], hb["x"] + 1), hb["x"] + hb["w"] - 1)
            dr.line([x, oy + hb["y"] + BOX_H, x, oy + b["y"]], fill=(110, 140, 125))
            dr.line([x, oy + b["y"], 8 + b["x"] + b["w"] // 2, oy + b["y"]], fill=(110, 140, 125))
    for b in boxes:
        x0, y0 = 8 + b["x"], oy + b["y"]
        cur = (ch == HERE[0] and b["room"] == HERE[1])
        fill = (140, 120, 60) if cur else ((30, 44, 52) if b["inside"] else (24, 52, 40))
        edge = (230, 200, 110) if cur else ((90, 120, 140) if b["inside"] else (90, 130, 110))
        dr.rectangle([x0, y0, x0 + b["w"] - 1, y0 + BOX_H - 1], fill=fill, outline=edge)
        t = label(b["room"])
        dr.text((x0 + (b["w"] - text_w(t)) // 2, y0 + 3), t, font=font, fill=(223, 232, 226))
    im = im.resize((W * SCALE, H * SCALE), Image.NEAREST)
    fn = os.path.join(OUT, "地图_%s_%s.png" % (ch, CH_NAME[ch]))
    im.save(fn)
    print(fn, [(b["room"], b["x"], b["y"], b["w"]) for b in boxes])
