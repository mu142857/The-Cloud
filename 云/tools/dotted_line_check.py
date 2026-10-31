"""找美术图里的虚线 / 点线（10-31 作者：「不要有虚线或者这种点线」，xiao-oscar 常见坑第一条）。

虚线 = 横着或竖着、一像素粗的一排短段，段长 1–4 像素、间隔 1–4 像素，按同一个周期（≤ 8 像素，一个周期里可以有一两段）严格重复，至少 4 段。
一像素粗：这一格和上下两格（竖线就是左右两格）都不一样、而且比它们明显亮或暗。

    python tools/dotted_line_check.py                                    # 默认：河流篇各房间真正用到的图
    python tools/dotted_line_check.py art/river_city art/river_home      # 或者给目录 / 文件
    python tools/dotted_line_check.py --min 4 --json out.json 某个.png

只列位置，不改图；找到的要 4 倍放大人工看一眼（规律的砖缝、窗格这类不一定是问题）。
上下也满是记号的（抖动、网点、扫描线）记成「纹理」，默认不列，--all 才列。
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ROOMS = ["art/river_city/river_bank", "art/river_home", "art/river_city/market", "art/river_city/stairwell", "art/river_city/oldstreet",
         "art/river_city/warehouse", "art/river_city/southbridge"]


def room_files():
    """每个房间文件夹里的图 + room.json 里 res:// 引用的图（河岸用 art/river/ 的天和远岸、仓库用 art/underwater/）。
    art/river_city/common/ 这类没有房间在用的不扫。"""
    out = set()
    for r in ROOMS:
        d = ROOT / r
        out |= set(d.glob("*.png"))
        rj = d / "room.json"
        if rj.exists():
            for m in re.findall(r'"res://([^"]+\.png)"', rj.read_text(encoding="utf-8")):
                out.add(ROOT / m)
    return sorted(out)
SKIP = ("moonpath",)            # 月光倒影的遮罩：RGB 存的是参数，不是画面（river_moonpath.gdshader）


def lum(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def thin_marks(a, thr):
    """一像素粗的横向记号：和上下两格比都明显亮（或都明显暗），三格都不透明。"""
    L = lum(a.astype(np.float32))
    op = a[..., 3] > 0
    m = np.zeros(L.shape, bool)
    up, mid, dn = L[:-2], L[1:-1], L[2:]
    ok = op[:-2] & op[1:-1] & op[2:]
    bright = (mid - up > thr) & (mid - dn > thr)
    dark = (up - mid > thr) & (dn - mid > thr)
    m[1:-1] = ok & (bright | dark)
    return m


def runs(row):
    """一行里 True 的段：[(起点, 长度)]"""
    d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
    s = np.nonzero(d == 1)[0]
    e = np.nonzero(d == -1)[0]
    return list(zip(s.tolist(), (e - s).tolist()))


def find_rows(m, min_rep, max_seg=4, max_gap=4, max_period=8):
    """一行里按固定周期重复的一串短段（段长 ≤ max_seg、间隔 ≤ max_gap）。
    周期里可以不止一段（比如「点、空一格、点、空两格」这样 5 像素一循环），只要整串按同一个周期严格重复、至少 min_rep 个周期。"""
    hits = []
    n = m.shape[1]
    for y in range(m.shape[0]):
        row = m[y]
        if row.sum() < min_rep:
            continue
        used = np.zeros(n, bool)
        for p in range(2, max_period + 1):
            eq = row[:-p] == row[p:]
            for s0, ln in runs(eq):
                if ln < p * (min_rep - 1):                 # 至少 min_rep 个完整周期
                    continue
                e0 = s0 + ln + p                           # [s0, e0) 按周期 p 重复
                rs = runs(row[s0:e0])
                if len(rs) < min_rep:
                    continue
                gaps = [rs[i + 1][0] - (rs[i][0] + rs[i][1]) for i in range(len(rs) - 1)]
                if max(r[1] for r in rs) > max_seg or max(gaps) > max_gap:
                    continue
                x0, x1 = s0 + rs[0][0], s0 + rs[-1][0] + rs[-1][1] - 1
                if used[x0:x1 + 1].any():
                    continue
                used[x0:x1 + 1] = True
                hits.append({"line": y, "from": int(x0), "to": int(x1), "seg": int(rs[0][1]), "gap": int(gaps[0]),
                             "period": p, "n": len(rs)})
    return hits


def scan(path: Path, min_rep=4, thr=6.0):
    a = np.asarray(Image.open(path).convert("RGBA"))
    out = []
    for d, arr in (("横", a), ("竖", a.transpose(1, 0, 2))):
        m = thin_marks(arr, thr)
        for h in find_rows(m, min_rep):
            h["dir"] = d
            # 上下两行（竖线就是左右两列）在这一段里也满是记号 → 抖动 / 网点这类成片的纹理，不是一条线
            y, x0, x1 = h["line"], h["from"], h["to"] + 1
            # （上下一行是同一个图案的不算：那是两像素粗的虚线）
            nb = [m[yy, x0:x1].mean() for yy in (y - 1, y + 1)
                  if 0 <= yy < m.shape[0] and (m[yy, x0:x1] != m[y, x0:x1]).mean() > 0.2]
            h["kind"] = "纹理" if max(nb, default=0) >= 0.35 else "线"
            out.append(h)
    return out


def merge(hits):
    """同一方向、相邻几行 / 几列的同一条记成一条（粗一点的虚线、上下两行的那种）。"""
    hits = sorted(hits, key=lambda h: (h["dir"], h["from"] // 8, h["line"]))
    out = []
    for h in hits:
        p = out[-1] if out else None
        if p and p["dir"] == h["dir"] and abs(p["from"] - h["from"]) <= 4 and 0 <= h["line"] - p["line_to"] <= 2:
            p["line_to"] = h["line"]
            p["to"] = max(p["to"], h["to"])
            p["n"] = max(p["n"], h["n"])
            if h["kind"] == "纹理" or p["line_to"] - p["line"] >= 3:
                p["kind"] = "纹理"
            continue
        h = dict(h)
        h["line_to"] = h["line"]
        out.append(h)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--min", type=int, default=4, help="至少连着重复几次")
    ap.add_argument("--thr", type=float, default=6.0, help="比上下亮 / 暗多少（0–255 亮度）才算一像素粗的线")
    ap.add_argument("--json", default=None)
    ap.add_argument("--all", action="store_true", help="成片的抖动纹理也列出来")
    a = ap.parse_args()
    files = [] if a.paths else room_files()
    for p in a.paths:
        p = Path(p) if Path(p).is_absolute() else ROOT / p
        files += sorted(p.rglob("*.png")) if p.is_dir() else [p]
    report = {}
    for f in files:
        if any(s in f.name for s in SKIP):
            continue
        hs = merge(scan(f, a.min, a.thr))
        if hs:
            rel = str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else str(f)
            report[rel] = hs
            for h in hs:
                where = (f"y={h['line']}" + (f"–{h['line_to']}" if h["line_to"] != h["line"] else "")
                         + f" x={h['from']}–{h['to']}") if h["dir"] == "横" else (
                    f"x={h['line']}" + (f"–{h['line_to']}" if h["line_to"] != h["line"] else "")
                    + f" y={h['from']}–{h['to']}")
                if h["kind"] == "线" or a.all:
                    print(f"{rel}\t{h['kind']}\t{h['dir']}\t{where}\t周期{h['period']} 段{h['seg']} 隔{h['gap']} ×{h['n']}")
    hs = [h for v in report.values() for h in v]
    print(f"DOTTED_CHECK 线 {sum(h['kind'] == '线' for h in hs)} 处 / 纹理 {sum(h['kind'] == '纹理' for h in hs)} 处"
          f"（--all 也列出来）/ {len(report)} 张图有 / 扫了 {len(files)} 张")
    if a.json:
        Path(a.json).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
