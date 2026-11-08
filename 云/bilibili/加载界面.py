#!/usr/bin/env python3
"""导出后跑（bilibili/export.sh 会调）：把游戏的像素字体嵌进 index.html 的加载界面。

    python3 bilibili/加载界面.py <导出目录>

作者 11-07：「为什么加载页面的云字不是像素体？」——加载界面上的「云」、THE CLOUD、版本号、进度文字都要用游戏 UI 的那套字
（fonts/PixelFont_ui.ttf，天王星像素 11Px，GPLv2 + 字体嵌入例外）。整套 1.3MB 太大，只留页面上出现的字：
页面里所有非 ASCII 的字 + 全部可打印 ASCII（百分比、版本号、报错）+ 几个常用标点，几十个汉字约 20KB，写成 data: 地址替换
shell.html 里的 __CLOUD_FONT__，加载界面一出来字就在，不用再等别的文件。字号在 shell.html 里都是 11 的整数倍 × 游戏像素倍数（--k）。
"""
import base64
import io
import os
import sys

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, "fonts", "PixelFont_ui.ttf")
EXTRA = "·…—、，。：；！？（）「」％"

out = sys.argv[1]
html_path = os.path.join(out, "index.html")
html = open(html_path, encoding="utf-8").read()
if "__CLOUD_FONT__" not in html:
    sys.exit("index.html 里没有 __CLOUD_FONT__（shell.html 变了？）")

chars = {c for c in html if ord(c) > 127} | {chr(i) for i in range(32, 127)} | set(EXTRA)
font = TTFont(FONT)
opts = subset.Options()
opts.flavor = "woff"
opts.layout_features = []
opts.name_IDs = []
opts.notdef_outline = True
sub = subset.Subsetter(opts)
sub.populate(unicodes=[ord(c) for c in chars])
sub.subset(font)
buf = io.BytesIO()
font.flavor = "woff"
font.save(buf)
data = buf.getvalue()
url = "data:font/woff;base64," + base64.b64encode(data).decode()
html = html.replace("__CLOUD_FONT__", url)
open(html_path, "w", encoding="utf-8").write(html)
print("加载界面：像素字体子集 %d 个字 %.1f KB（base64 后 %.1f KB）" % (len(chars), len(data) / 1024, len(url) / 1024))
