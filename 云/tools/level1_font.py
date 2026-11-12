"""界面用的像素字：从 fonts/PixelFont.ttf（天王星像素 11Px，GPLv2 + 字体嵌入例外）派生 fonts/PixelFont_ui.ttf，
只改两处排版度量，字形一个点都不动：

1. 英文标点贴紧前一个字母。原字体里 . , ' ! ; " 这些标点左边留了 2 格空（字母左边是 0 格、右边 1 格），
   所以「Ow...」「Should've」在 14 号字下标点前后空出 3 像素，看着像多打了空格。这里把这些字形整体左移到
   左边 0 格、右边 1 格（和字母一样），前进宽度跟着缩。中文全角标点（，。！……）不动。
2. 上 / 下沿（ascent / descent）改成整格：原来是 11.197 / 2.789 格，14 号字的基线落在 0.2 像素上，
   42 号（标题）落在 0.6 像素上，字的像素格和画面的像素格差半格。改成 11 / 3 格（一行还是 14 格）。

3. 补几个原字体没有的符号（▸ ♪ ▶，见 EXTRA）：按点阵格画，原有字形不动。

跑法："/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/level1_font.py
scripts/ui_theme.gd 读的就是 PixelFont_ui.ttf（没有这个文件会退回原字体）。
"""
from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "fonts" / "PixelFont.ttf"
DST = ROOT / "fonts" / "PixelFont_ui.ttf"
CELL = 1024 / 14                    # 一个点阵格 = 73.14 单位
TIGHT = ".,'!;:\"`?)"             # 只收紧左边空 >= 2 格的那些（ASCII 半角；中文的全角标点和弯引号不动）


# 3. 原字体里没有、游戏里要用的几个符号（11-08 作者截图：对话选项前的「▸」显示成写着 25b8 的框框）。
#    按点阵格画（一格 = CELL），「#」是实心格；y_top = 第一行的上沿在基线上面几格。
#    ▸ 选中标记（UITheme.MARK）：4×7 实心小三角，半角宽（和「>」一样 7 格），上下居中在「→」那一高度（基线上 1～8 格）
#    ♪ 弥洛唱歌（forest_side_a）：全角，和 ★ ● 一样宽；▶ 开发面板「快进」：全角，和 ▲ 同高
EXTRA = [
    ("▸", ["#", "##", "###", "####", "###", "##", "#"], 7, 1, 8),
    ("♪", ["   #", "   ##", "   # #", "   #  #", "   #  #", "   #", " ###", "####", "####", " ##"], 14, 3, 10),
    ("\u2007", [], 7, 0, 0),     # 空白、和 ▸ 一样宽（UITheme.MARK_OFF）：没选中的那几行用它占位，选中时字不左右跳
    ("▶", ["#", "##", "###", "####", "#####", "######", "#####", "####", "###", "##", "#"], 14, 4, 10),
    # Guillemets français, 7 cases d’avance comme les autres signes demi-chasse.
    ("«", ["  #  #", " #  #", "#  #", " #  #", "  #  #"], 7, 0, 7),
    ("»", ["#  #", " #  #", "  #  #", " #  #", "#  #"], 7, 0, 7),
]


def add_pixel_glyph(f, ch, rows, adv_cells, x0, y_top):
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    cp = ord(ch)
    if cp in f.getBestCmap():
        return f"U+{cp:04X} 已有，不画"
    name = "uni%04X" % cp
    pen = TTGlyphPen(None)
    for i, row in enumerate(rows):          # 每一行连着的实心格画成一个矩形
        top = y_top - i
        x = 0
        while x < len(row):
            if row[x] != "#":
                x += 1
                continue
            x1 = x
            while x1 < len(row) and row[x1] == "#":
                x1 += 1
            l, r = round((x0 + x) * CELL), round((x0 + x1) * CELL)
            b, t = round((top - 1) * CELL), round(top * CELL)
            pen.moveTo((l, b)); pen.lineTo((l, t)); pen.lineTo((r, t)); pen.lineTo((r, b)); pen.closePath()
            x = x1
    gl = pen.glyph()
    order = f.getGlyphOrder() + [name]
    f.setGlyphOrder(order)
    f["glyf"].glyphOrder = order
    f["glyf"][name] = gl
    gl.recalcBounds(f["glyf"])
    f["hmtx"][name] = (int(round(adv_cells * CELL)), gl.xMin if rows else 0)
    for t in f["cmap"].tables:
        if t.isUnicode():
            t.cmap[cp] = name
    return f"U+{cp:04X} 新画：{len(rows)} 行，宽 {adv_cells} 格"


def main():
    f = TTFont(SRC)
    cmap = f.getBestCmap()
    glyf, hmtx = f["glyf"], f["hmtx"]
    changed = []
    for ch in TIGHT:
        g = cmap.get(ord(ch))
        if g is None:
            continue
        gl = glyf[g]
        if gl.numberOfContours == 0:
            continue
        gl.recalcBounds(glyf)
        adv, lsb = hmtx[g]
        lsb_cells = round(gl.xMin / CELL)
        if lsb_cells < 2:
            continue
        dx = -int(round(lsb_cells * CELL))
        if gl.isComposite():
            continue
        coords = gl.coordinates
        for i in range(len(coords)):
            x, y = coords[i]
            coords[i] = (x + dx, y)
        gl.recalcBounds(glyf)
        ink = round((gl.xMax - gl.xMin) / CELL)
        new_adv = int(round((ink + 1) * CELL))
        hmtx[g] = (new_adv, gl.xMin)
        changed.append(f"{ch} 左空 {lsb_cells} 格 → 0，宽 {adv / CELL:.0f} → {new_adv / CELL:.0f} 格")
    for ch, rows, adv, x0, y_top in EXTRA:
        changed.append(add_pixel_glyph(f, ch, rows, adv, x0, y_top))
    asc, desc = int(round(11 * CELL)), int(round(3 * CELL))
    f["hhea"].ascent, f["hhea"].descent, f["hhea"].lineGap = asc, -desc, 0
    os2 = f["OS/2"]
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = asc, -desc, 0
    os2.usWinAscent, os2.usWinDescent = asc, desc
    f.save(DST)
    print("\n".join(changed))
    print(f"ascent {asc} ({asc / CELL:.3f} 格) descent {desc} ({desc / CELL:.3f} 格) → {DST}")


if __name__ == "__main__":
    main()
