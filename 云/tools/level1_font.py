"""界面用的像素字：从 fonts/PixelFont.ttf（天王星像素 11Px，GPLv2 + 字体嵌入例外）派生 fonts/PixelFont_ui.ttf，
只改两处排版度量，字形一个点都不动：

1. 英文标点贴紧前一个字母。原字体里 . , ' ! ; " 这些标点左边留了 2 格空（字母左边是 0 格、右边 1 格），
   所以「Ow...」「Should've」在 14 号字下标点前后空出 3 像素，看着像多打了空格。这里把这些字形整体左移到
   左边 0 格、右边 1 格（和字母一样），前进宽度跟着缩。中文全角标点（，。！……）不动。
2. 上 / 下沿（ascent / descent）改成整格：原来是 11.197 / 2.789 格，14 号字的基线落在 0.2 像素上，
   42 号（标题）落在 0.6 像素上，字的像素格和画面的像素格差半格。改成 11 / 3 格（一行还是 14 格）。

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
