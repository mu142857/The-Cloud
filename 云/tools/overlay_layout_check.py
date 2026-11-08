"""叠在画面上的小游戏摆位检查（scripts/overlay_layout.gd 的规矩）：照游戏里的真位置画示意图，算有没有字叠在一起。

跑法（项目根目录）：
  "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/overlay_layout_check.py 输出目录
每个小游戏出一张 3 倍的示意图（中文、英文各一半），并打印 OVERLAY_CHECK 有几处叠在一起（0 = 没问题）。

画的东西（屏幕坐标 480×270，数字都和脚本里一致）：
  面板（side_kit / ship_repair：overlay_layout.panel_pos）、按键提示那一行（hint_y）、字幕框（收音机 CAP_RECT，
  最长的那句换行后）、最长的那组选项（story_dialogue._open_menu：x 116，y = 222 − (n−1)×18）、旁白（NARR_Y 206）、
  没有站在画面里的说话人的对话框（屏幕上方正中，框底在 39）、左上角目标。
规矩：按键提示和字幕在对话 / 选项显示的时候藏起来（HintLabel / busy），所以「提示 × 选项」「字幕 × 选项」不算冲突，
  但仍然要求它们的位置本身不进对话那一带（BAND_TOP 以下）。真正要查的是：面板 × 选项 / 旁白、字幕 × 面板外、提示 × 面板。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ImageFont.truetype(str(ROOT / "fonts" / "PixelFont_ui.ttf"), 14)
W, H = 480, 270
BAND_TOP = 184.0          # story_dialogue.gd BAND_TOP
TOP = 34.0                # overlay_layout.gd TOP
HINT_Y = 16.0
HINT_H = 16.0
NARR_Y = 206.0
LINE_H = 16


def tw(t: str) -> float:
    return FONT.getlength(t)


def panel_pos(sz):
    y = min(TOP, BAND_TOP - 2.0 - sz[1])
    return (round((W - sz[0]) / 2.0), round(max(0.0, y)))


def hint_y(top=None):
    return HINT_Y if top is None else max(0.0, top - HINT_H - 1.0)


def wrap(t: str, width: float) -> list:
    lines, cur = [], ""
    tokens = t.split(" ") if " " in t and t.isascii() else list(t)
    sep = " " if " " in t and t.isascii() else ""
    for tok in tokens:
        nxt = cur + (sep if cur else "") + tok
        if tw(nxt) <= width or not cur:
            cur = nxt
        else:
            lines.append(cur)
            cur = tok
    if cur:
        lines.append(cur)
    return lines


def choice_rects(opts: list) -> list:
    """story_dialogue._open_menu：平时从 x 120 起，最长那句放不下就整组往左让（x0 = clamp(474 − 8 − 最宽, 10, 120)）"""
    n = len(opts)
    y0 = 222.0 - (n - 1) * 18.0
    widest = max(tw("  " + o) for o in opts)
    x0 = min(120.0, max(10.0, round(474.0 - 8.0 - widest)))
    out = []
    for i, o in enumerate(opts):
        t = "  " + o
        out.append(("choice", (x0 - 4.0, y0 + i * 18.0 - 1.0, x0 - 4.0 + tw(t) + 12.0, y0 + i * 18.0 + 16.0), t))
    return out


def inter(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def visible_options(opts: list, flag: str) -> list:
    out = []
    for o in opts:
        need, not_ = o.get("need", []), o.get("not", [])
        if all(f == flag for f in need) and flag not in not_:
            out.append(o)
    return out


def longest_choice(json_path: Path, scene_keys: list) -> dict:
    """在剧本里找这几个 scene / mechanic lines 里的 choice，按母亲线、孩子线各算一次，挑字最长的那组"""
    d = json.loads(json_path.read_text(encoding="utf-8"))
    best = {"zh": [], "en": []}
    found = []

    def walk(o, inside):
        if isinstance(o, dict):
            if o.get("do") == "choice" and inside:
                found.append(o["options"])
            for k, v in o.items():
                walk(v, inside or k in scene_keys)
        elif isinstance(o, list):
            for v in o:
                walk(v, inside)
    for k in scene_keys:
        walk(d.get("scenes", {}).get(k, []), True)
    for opts in found:
        for flag in ("c1_mom", "c1_child"):
            vis = visible_options(opts, flag)
            for lang in ("zh", "en"):
                ts = [o[lang] for o in vis]
                if not best[lang] or max(tw("  " + t) for t in ts) + 4 * len(ts) > max(tw("  " + t) for t in best[lang]) + 4 * len(best[lang]):
                    best[lang] = ts
    return best


def render(name: str, spec: dict, out_dir: Path) -> int:
    img = Image.new("RGB", (W * 2 + 10, H), (14, 18, 20))
    dr = ImageDraw.Draw(img)
    bad = 0
    for side, lang in enumerate(("zh", "en")):
        ox = side * (W + 10)
        boxes = []        # (kind, rect, text)
        # 左上角目标（两行）、没有站在画面里的说话人的对话框（上方正中）
        if spec.get("hud"):
            # 左上角目标（level_forest：(8, 7) 起，主目标一行 + 「（可选）」一行）；面板 / 按键提示出来时 hud_fade 淡掉，只有不淡的小游戏画它
            boxes.append(("objective", (8, 7, 8 + 150, 7 + 33), "目标" if lang == "zh" else "Objective"))
        if spec.get("top_speaker"):
            t = spec["top_speaker"][lang]
            w = min(196.0, tw(t)) + 12
            boxes.append(("say_top", (240 - w / 2, 39 - 20, 240 + w / 2, 39), t))
        if "panel" in spec:
            px, py = panel_pos(spec["panel"])
            boxes.append(("panel", (px, py, px + spec["panel"][0], py + spec["panel"][1]), ""))
            hy = hint_y(py)
        else:
            hy = hint_y()
        for r in spec.get("world", []):
            boxes.append(("world", r, ""))
        if spec.get("hint"):
            t = spec["hint"][lang]
            boxes.append(("hint", (240 - tw(t) / 2, hy, 240 + tw(t) / 2, hy + HINT_H), t))
        if spec.get("caption"):
            px, py = panel_pos(spec["panel"])
            cx, cy, cw, ch = spec["cap_rect"]
            lines = wrap(spec["caption"][lang], cw)
            th = len(lines) * LINE_H
            boxes.append(("caption", (px + cx, py + cy + (ch - th) / 2, px + cx + cw, py + cy + (ch + th) / 2), "\n".join(lines)))
            if th > ch:
                print("  %s %s 字幕放不下：%d 行 %d 像素 > %d" % (name, lang, len(lines), th, ch))
                bad += 1
            boxes.append(("cap_area", (px + cx, py + cy, px + cx + cw, py + cy + ch), ""))
        if spec.get("choices") and spec["choices"][lang]:
            boxes += choice_rects(spec["choices"][lang])
        if spec.get("narr") and not (spec.get("choices") and spec["choices"][lang]):   # 选项一开旁白就收（_fade_narr_now），不会同时在
            t = spec["narr"][lang]
            boxes.append(("narr", (240 - tw(t) / 2, NARR_Y, 240 + tw(t) / 2, NARR_Y + 16), t))
        # 冲突：同时会显示的两样东西叠在一起
        hidden_when_dlg = {"hint", "caption", "cap_area"}
        dlg = {"choice", "narr", "say_top"}
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                ka, kb = a[0], b[0]
                pair = {ka, kb}
                if pair <= {"caption", "cap_area", "panel"} or pair == {"choice"} or pair <= dlg:
                    continue
                if pair == {"say_top", "panel"}:
                    continue                       # 对话框盖在面板的木框上（画在面板上面，不是字叠字）
                if (ka in hidden_when_dlg and kb in dlg) or (kb in hidden_when_dlg and ka in dlg):
                    continue                       # 对话 / 选项显示时它们藏起来（规矩 ③④）
                if pair == {"objective", "hint"} and spec.get("panel") is None:
                    pass
                if inter(a[1], b[1]):
                    print("  %s %s 叠在一起：%s × %s" % (name, lang, ka, kb))
                    bad += 1
        # 什么都不许出屏幕
        for k, r, _ in boxes:
            if r[0] < 0 or r[2] > W or r[1] < 0 or r[3] > H:
                print("  %s %s %s 出了屏幕 %s" % (name, lang, k, str(tuple(round(v) for v in r))))
                bad += 1
        # 字（提示、字幕）不许进对话那一带
        for k, r, _ in boxes:
            if k in ("hint", "caption", "cap_area", "panel", "world") and r[3] > BAND_TOP:
                print("  %s %s %s 进了对话那一带（底边 %.0f > %.0f）" % (name, lang, k, r[3], BAND_TOP))
                bad += 1
        # 画
        dr.rectangle((ox, BAND_TOP, ox + W - 1, H - 1), fill=(32, 26, 30))
        dr.line((ox, BAND_TOP, ox + W - 1, BAND_TOP), fill=(200, 90, 80))
        col = {"panel": (52, 60, 58), "objective": (40, 44, 40), "hint": (60, 70, 90), "caption": (36, 64, 52),
               "cap_area": None, "choice": (24, 40, 36), "narr": (60, 50, 70), "say_top": (24, 40, 36), "world": (70, 60, 40)}
        for k, r, t in boxes:
            rr = (ox + r[0], r[1], ox + r[2], r[3])
            if col.get(k):
                dr.rectangle(rr, fill=col[k])
            else:
                dr.rectangle(rr, outline=(90, 140, 110))
            if t:
                fc = {"hint": (200, 210, 230), "caption": (169, 216, 188)}.get(k, (223, 232, 226))
                for li, line in enumerate(t.split("\n")):
                    dr.text((rr[0] + (6 if k == "choice" else 0), rr[1] + li * LINE_H), line, font=FONT, fill=fc)
        dr.text((ox + 300, 4), name + " " + lang, font=FONT, fill=(120, 130, 125))
    img = img.resize((img.width * 3, img.height * 3), Image.NEAREST)
    img.save(out_dir / ("layout_%s.png" % name))
    return bad


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    sa = ROOT / "data" / "forest_side_a.json"
    sb = ROOT / "data" / "forest_side_b.json"           # 坡地
    st = ROOT / "data" / "forest_side_on_toucan.json"   # 11-08 大嘴鸟从 forest_side_b 拆出来
    P = (232, 150)
    radio_lost = {"zh": "失物招领：一位自称是鹿的母亲的人。有认识的，请来把她领走。",
                  "en": "Lost and found: one person claiming to be a deer's mother. If you know her, please come collect her."}
    specs = {
        "side_radio": {"panel": P, "cap_rect": (20, 50, 128, 82), "caption": radio_lost,
                       "hint": {"zh": "←→ 或按住左右拧旋钮，找小吃棚的台", "en": "← → or hold left / right to turn the dial. Find the stall's station."},
                       "choices": longest_choice(sa, ["sa_radio_return"]),
                       "top_speaker": {"zh": "请携带鹿一只。", "en": "Please bring one deer."}},
        "side_pine": {"panel": P, "hint": {"zh": "按住接松脂，到红线就松手", "en": "Hold to catch the sap. Let go at the red line."},
                      "narr": {"zh": "罐子黏在手上了。甩了两下，甩不掉。", "en": "The jar's stuck to your hand. Two shakes. Still stuck."},
                      "top_speaker": {"zh": "行了行了，我自己滴。", "en": "Okay, okay. I'll drip it myself."}},
        "side_sign": {"panel": P, "hint": {"zh": "按一下刹住，让它指着空地", "en": "Press to brake. Make it point at the Clearing."},
                      "choices": longest_choice(sa, ["sa_sign_return"]),
                      "narr": {"zh": "它好像觉得你就是路。", "en": "It seems to think you're the way."}},
        "side_lamp": {"panel": P, "hint": {"zh": "做一个一样的手影", "en": "Make the same hand shadow."},
                      "choices": longest_choice(sa, ["sa_lamp_light"]),
                      "narr": {"zh": "最小的那个在地上摸来摸去。它比划了一下：一个背包。", "en": "The smallest one feels around on the floor. Then it traces a shape: a backpack."}},
        "ship_repair": {"panel": P, "hint": {"zh": "圈里几个点就敲几下，敲够了就停手", "en": "Hit each part as many times as its dots, then stop."}},
        "side_toucan": {"hint": {"zh": "← → / A D：接住大嘴鸟抛过来的果子", "en": "← → / A D: catch the toucan's fruit"},
                        "choices": longest_choice(st, [k for k in json.loads(st.read_text(encoding="utf-8"))["scenes"] if "toucan" in k])},
        "side_slope": {"hint": {"zh": "← → / A D：跟着鹿的蹄印走（两瓣的那种）", "en": "← → / A D: follow the deer's hoofprints (the split ones)"},
                       "choices": longest_choice(sb, [k for k in json.loads(sb.read_text(encoding="utf-8"))["scenes"] if "slope" in k])},
        "rabbit_dance": {"hint": {"zh": "方向键 / WASD：跟着兔子跳", "en": "Arrow keys / WASD: follow the rabbit"}},
    }
    total = 0
    for name, spec in specs.items():
        n = render(name, spec, out_dir)
        print("  %-18s %s" % (name, "ok" if n == 0 else "%d 处" % n))
        total += n
    print("OVERLAY_CHECK %d" % total)


if __name__ == "__main__":
    main()
