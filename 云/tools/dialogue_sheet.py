#!/usr/bin/env python3
"""第二章台词表：把河流章玩家看得到的字导出成表，作者改完再写回去。

    python3 tools/dialogue_sheet.py export [--out docs/第二章台词表_v2]
    python3 tools/dialogue_sheet.py apply --xlsx 作者改的.xlsx --base 导出时的原表.xlsx [--dry-run]

字从哪来：data/story_river.json 全部；第二章用到的物品（items_later.json / items.json）；通讯器（phone.json）；
代码里写死的玩家可见文字（CODE_TEXT，小游戏按键提示、共用界面字）。

export：表里已经有作者填的字时拒绝覆盖（要覆盖加 --force）。

apply 认两种改法（作者习惯直接改原文列，所以都支持）：
  - 填「改后中文 / 改后英文」。
  - 给了 --base：直接改「中文原文 / 英文原文」，和原表逐行比。原文改空 = 删掉这句（开头写 # 也算删，# 后面当作者的话打印出来）。
  - 给了 --base：没有「定位」的行写了字 = 新加一句，加在上一条有定位的行所在步骤后面（「说话人」空着就和上一行同一个人）。
写回时只替换那个字符串 / 那一步，文件其他字节一个不动（手排的格式、_note 都不变）。
表导出以后 json 又被改过、某行对不上（当前的字和表里原文不同）时一行都不写，并列出来；加 --skip-stale 跳过这些行、写其他行。
选项、物品名、标签这种不能单独删的行，改空会报出来，不会动。写之前把原文件备份到系统临时目录，写完跑 --story_check。
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata

try:
    import openpyxl
except ImportError:
    # 系统 python 不让装包（PEP 668），openpyxl 装在这个专用虚拟环境里
    venv_py = os.path.expanduser("~/.venvs/the_cloud_tools/bin/python")
    if os.path.exists(venv_py) and os.path.abspath(sys.prefix) != os.path.dirname(os.path.dirname(venv_py)):
        os.execv(venv_py, [venv_py] + sys.argv)
    sys.exit("缺 openpyxl：python3 -m venv ~/.venvs/the_cloud_tools && ~/.venvs/the_cloud_tools/bin/pip install openpyxl")
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = "story_river.json"
ITEMS = "items_later.json"
ITEMS_BASE = "items.json"
PHONE = "phone.json"
OUT = os.path.join(ROOT, "docs", "第二章台词表")
GT_SH = os.environ.get("GT_SH", "/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/"
                       "282992cb-4fc2-479e-8b54-17f26919d4d8/scratchpad/gt.sh")

## 主线的场景顺序：11-05 河流主线 --story_auto --main_only 实际走过的顺序（普通开头）。
## 剧本加了新场景不用改这里：新场景会跟在引用它的场景后面，或者落到后面的分组里。
MAIN_SPINE = """start_river bank_meet n_meet_plain bank_meet_b bank_cup bank_invite_yes home_enter home_who_invite home_asked
home_find home_who2_chen home_find_b home_out market_go market_to_stairwell stairwell_jelly oldstreet_go sluice sluice_open oldstreet_tank_take
warehouse_go warehouse_in tape_fix bank_to_market market_to_oldstreet_again south_walk_in south_go south_intro south_arch_right south_trail_start south_trail_end
south_dock dock_plates dock_plate_12 south_back farewell n_tea_p ch_bye_write farewell_b farewell_phone plane_need_seal plane_fix depart n_bye_p""".split()

## 步骤里指向别的场景的字段
REF_KEYS = {"scene", "then", "else", "after", "on_head", "on_seal", "quit_scene"}
SKIP_KEYS = {"spec", "match"}          # 写给开发看的说明 / 只用来匹配的字，玩家看不到

PHONE_NAMES = {"miluo": "弥洛", "friend": "她", "nifu": "妮芙"}

## 代码里写死的玩家可见文字：(分组, 文件, 中文字面量)。按字面量找行（别的会话改代码后行号会变），apply 也按字面量写回。
## 只收第二章会显示的。默认值（DEFAULT_JUNK、DEFAULT_GATES 这些）剧本都给了，显示不出来，不收。
CODE_TEXT = [
    ("小游戏按键提示", "scripts/river_valve.gd", "按住转闸轮，管子不咕噜了就松手"), ("小游戏按键提示", "scripts/river_borrowed.gd", "←→ 选箱子，空格打开。趁她还记得"),
    ("小游戏按键提示", "scripts/river_cook.gd", "大泡「咕嘟」的那一下按空格，放进去"), ("小游戏按键提示", "scripts/river_thread.gd", "←→ 拧接头"),
    ("小游戏按键提示", "scripts/river_guestbook.gd", "←→ 交替按，扇干这一页"), ("小游戏按键提示", "scripts/side_kit.gd", "Esc 退出"),
    ("章末卡", "scripts/chapter_flow.gd", "第二章　完"),
    ("左上角", "scripts/level_forest.gd", "（可选）"), ("左上角", "scripts/level_forest.gd", "　等 %d 件"),
    ("提示", "scripts/story_runner.gd", "交出 %d 件东西"),
    ("物品", "scripts/story_runner.gd", "日记"), ("物品", "scripts/phone_state.gd", "通讯器"), ("物品", "scripts/phone_state.gd", "一直带在行李里的旧通讯器。"),
    ("闪回", "scripts/flashback.gd", "狂按 E 冲刺"),
]
## 拼出来的字（一行里不是成对的字面量）：手写 (文件, 行, 中文字面量, 英文字面量, 说明)
CODE_LITERAL = [
    ("scripts/river_borrowed.gd", 287, "读取头 %s　密封圈 %s", "Head %s  Seal %s", "水下仓库右上角，%s 是「有 / —」"),
    ("scripts/river_explore_order.gd", 103, "（试过 %s）", " (tried %s)", "南桥货台编号牌的板子"),
    ("scripts/river_explore_order.gd", 101, "第%d格×", "%d ×", "南桥货台编号牌的板子"),
]
I18N_KEYS = """settings language vol_master vol_music vol_sfx quality q_full q_lite fullscreen on off close bag bag_empty burn
burn_value to_launch personal rarity_common rarity_uncommon rarity_rare rarity_epic rarity_legendary who_chen got_item got_items
luggage_items gave_item journal_added journal_empty to_be_continued to_be_continued_sub just_look barter_none use use_nothing
use_here_nothing journal_struck cat_keepsake cat_quest keepsake_burn quest_item""".split()
PHONE_UI_KEYS = "view reply later send not_now close fold new_msg no_contacts".split()

COLUMNS = [("序号", 6), ("场景", 17), ("步骤", 6), ("类型", 13), ("说话人", 10), ("中文原文", 42), ("英文原文", 42),
           ("来源", 9), ("改后中文", 42), ("改后英文", 42), ("备注", 28), ("定位（别改）", 16)]
COL = {name: i + 1 for i, (name, _) in enumerate(COLUMNS)}


# ----------------------------------------------------------------------- 带位置的 json 扫描
def scan_strings(text):
    """返回 {路径 tuple: (起, 止)}：每个值在 text 里的范围（字符串含引号）。"""
    spans = {}
    dec = json.JSONDecoder()
    n = len(text)

    def ws(i):
        while i < n and text[i] in " \t\r\n":
            i += 1
        return i

    def value(i, path):
        i = ws(i)
        end = body(i, path)
        spans[path] = (i, end)
        return end

    def body(i, path):
        c = text[i]
        if c == "{":
            i = ws(i + 1)
            if text[i] == "}":
                return i + 1
            while True:
                key, i = json.decoder.scanstring(text, ws(i) + 1)
                i = ws(i)
                assert text[i] == ":", i
                i = value(i + 1, path + (key,))
                i = ws(i)
                if text[i] == "}":
                    return i + 1
                assert text[i] == ",", i
                i += 1
        if c == "[":
            i = ws(i + 1)
            if text[i] == "]":
                return i + 1
            k = 0
            while True:
                i = value(i, path + (k,))
                k += 1
                i = ws(i)
                if text[i] == "]":
                    return i + 1
                assert text[i] == ",", i
                i += 1
        if c == '"':
            _, end = json.decoder.scanstring(text, i + 1)
            return end
        _, end = dec.raw_decode(text, i)
        return end

    value(0, ())
    return spans


def fmt_path(path):
    out = ""
    for p in path:
        if isinstance(p, int):
            out += "[%d]" % p
        else:
            out += ("." if out else "") + p
    return out


def parse_path(s):
    out = []
    for m in re.finditer(r"([^.\[\]]+)|\[(\d+)\]", s):
        out.append(m.group(1) if m.group(1) is not None else int(m.group(2)))
    return tuple(out)


def get_at(o, path):
    for p in path:
        o = o[p]
    return o


# ----------------------------------------------------------------------- 收字
def is_text(o):
    return isinstance(o, dict) and "zh" in o and "en" in o


def collect(o, path, mech=None):
    """按文件顺序列出 o 里所有 {zh, en} 节点：(路径, 节点, 外层一串 dict)。"""
    out = []

    def go(x, p, parents):
        if isinstance(x, dict):
            if is_text(x):
                out.append((p, x, parents))
            for k, v in x.items():
                if k.startswith("_") or k in SKIP_KEYS:
                    continue
                go(v, p + (k,), parents + [x])
        elif isinstance(x, list):
            for i, v in enumerate(x):
                go(v, p + (i,), parents)

    go(o, path, [])
    return out


def source_of(node, parents):
    return "added" if node.get("added") or any(q.get("added") for q in parents) else "本2兔原文"


DEV_NAMES = {}


def load_dev_names(data_dir):
    DEV_NAMES.clear()
    try:
        DEV_NAMES.update(json.load(open(os.path.join(data_dir, "dev_names.json"), encoding="utf-8")))
    except OSError:
        pass


def flag_name(f):
    n = DEV_NAMES.get("flags", {}).get(f)
    return "%s（%s）" % (n, f) if n else f


def needs_note(node):
    bits = []
    if node.get("need"):
        bits.append("需要 " + "、".join(flag_name(f) for f in node["need"]))
    if node.get("not"):
        bits.append("没有 " + "、".join(flag_name(f) for f in node["not"]))
    return bits


def scene_rows(data, name, strike):
    """一个场景的所有行。"""
    rows = []
    speakers = data.get("speakers", {})
    for path, node, parents in collect(data["scenes"][name], ("scenes", name)):
        step = path[2]
        step_d = data["scenes"][name][step]
        do = step_d.get("do", "")
        last = path[-1]
        who = ""
        note = needs_note(node)
        if "say" in node:
            who = speakers.get(node["say"], {}).get("zh", node["say"])
        if do == "mechanic":
            mid = step_d.get("id", "")
            if "say" in node or last == "narr" or "lines" in path:
                kind = "bark" if node.get("bark") else ("narr" if last == "narr" else "小游戏台词")
                if "lines" in path:
                    note.append("%s：%s" % (mid, path[path.index("lines") + 1]))
            else:
                kind = "小游戏文字"
                note.append("%s：%s" % (mid, next((str(p) for p in reversed(path) if isinstance(p, str) and p != "label"), "")))
        elif last == "narr":
            kind = "narr"
        elif "say" in node:
            kind = "bark" if node.get("bark") else "say"
        elif do == "journal":
            kind = "journal"
            for m in strike:
                if m in node["zh"]:
                    note.append("后面按「%s」找这句划掉：改的时候这几个字要留着" % m)
        elif do == "phone_msg":
            kind = "phone 回复" if last == "reply" else "phone 消息"
            if last != "reply":
                who = PHONE_NAMES.get(step_d.get("from", ""), step_d.get("from", ""))
        elif do == "phone_add":
            kind = "phone 联系人"
        elif do == "flashback":
            kind = "闪回"
        elif do in ("choice", "pick"):
            kind = "choice 选项"
            who = speakers.get("chen", {}).get("zh", "")
            opt = next((q for q in reversed(parents) if "scene" in q), node)
            if "scene" in opt:
                note.append("选这个 → " + opt["scene"])
            if opt is not node:
                note += needs_note(opt)
        else:
            kind = do or "text"
        if last == "narr":
            who = "旁白"
        rows.append(dict(scene=name, step=step, kind=kind, who=who, zh=node["zh"], en=node["en"],
                         src=source_of(node, parents), note="；".join(note), loc=fmt_path(path)))
    return rows


def refs_in(o):
    """o 里按出现顺序指向的场景名。"""
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k.startswith("_"):
                continue
            if k in REF_KEYS and isinstance(v, str):
                out.append(v)
            else:
                out += refs_in(v)
    elif isinstance(o, list):
        for v in o:
            out += refs_in(v)
    return out


def scene_children(data, name):
    out = refs_in(data["scenes"][name])
    for st in data["scenes"][name]:
        if isinstance(st, dict) and st.get("do") == "barter":
            b = data.get("barter", {}).get(st.get("npc"), {})
            out += [t["scene"] for t in b.get("trades", []) if "scene" in t]
            out += [v for k in ("wrong", "none", "done") for v in [b.get(k)] if v]
            out += list(b.get("react", {}).values())
    seen = []
    for c in out:
        if c in data["scenes"] and c not in seen and c != name:
            seen.append(c)
    return seen


def order_scenes(data):
    """返回 [(分组名, [场景…])…]"""
    scenes = data["scenes"]
    children = {n: scene_children(data, n) for n in scenes}
    spine = [n for n in MAIN_SPINE if n in scenes]
    spine_set = set(spine)
    placed = []
    placed_set = set()

    def place(n):
        if n not in placed_set:
            placed.append(n)
            placed_set.add(n)

    def branches(n):
        # n 底下不属于主线的场景（遇到主线场景就停）
        for c in children[n]:
            if c not in spine_set and c not in placed_set:
                place(c)
                branches(c)

    # 主线：别的选项分支紧跟在玩家这遍走的那一支后面
    pending = None
    for i, n in enumerate(spine):
        place(n)
        if pending:
            branches(pending)
            pending = None
        nxt = spine[i + 1] if i + 1 < len(spine) else None
        if nxt in children[n]:
            pending = n
        else:
            branches(n)
    groups = [("主线（从落地到起飞）", list(placed))]

    def from_hotspots(pred):
        # 按场景在文件里的顺序排（同一个地方的放一起，第一次见的在前）
        hs = {h.get("scene") for h in data.get("hotspots", []) if pred(h)}
        n0 = len(placed)
        for sc in scenes:
            if sc in hs and sc not in placed_set:
                place(sc)
                branches(sc)
        return list(placed[n0:])

    groups.append(("可选支线（左上角暗一行「（可选）」的那些）", from_hotspots(lambda h: "_side" in h)))
    groups.append(("走到跟前才有的（物件、闲聊、换地方）", from_hotspots(lambda h: True)))
    # 还有被主线外场景引用、前面没排到的
    rest = [n for n in scenes if n not in placed_set]
    referenced = {c for n in scenes for c in children[n]}
    nudged = [n for n in rest if n in referenced]
    for n in nudged:
        place(n)
    orphan = [n for n in scenes if n not in placed_set]
    if nudged:
        groups.append(("其他分支", nudged))
    if orphan:
        groups.append(("没有入口的场景（目前玩家看不到）", orphan))
    return groups


def option_causes(data):
    """flag → 设它的选项文字：选项进的那个场景里 flag set 的。"""
    causes = {}
    for sc in data["scenes"].values():
        for st in sc:
            if not isinstance(st, dict) or st.get("do") not in ("choice", "pick"):
                continue
            for o in st.get("options", []):
                text = (o.get("label") if is_text(o.get("label")) else o).get("zh", "")
                for s2 in data["scenes"].get(o.get("scene"), []):
                    if isinstance(s2, dict) and s2.get("do") == "flag" and isinstance(s2.get("set"), str):
                        causes.setdefault(s2["set"], []).append(text)
    return causes


def cond_text(flag, causes, negate):
    if flag.startswith("!"):
        flag, negate = flag[1:], not negate
    who = causes.get(flag)
    if who:
        q = "、".join("「%s」" % t for t in who)
        return ("没选%s才会到" if negate else "选了%s才会到") % q
    return ("没有 %s 才会到" if negate else "有 %s 才会到") % flag_name(flag)


def scene_causes(data):
    """场景 → 「选了 X 才会到」这样的说明。"""
    flags = option_causes(data)
    out = {}

    def add(sc, text):
        if sc in data["scenes"] and text not in out.setdefault(sc, []):
            out[sc].append(text)

    for name, sc in data["scenes"].items():
        for st in sc:
            if not isinstance(st, dict):
                continue
            if st.get("do") in ("choice", "pick"):
                for o in st.get("options", []):
                    text = (o.get("label") if is_text(o.get("label")) else o).get("zh", "")
                    add(o.get("scene"), "选了「%s」才会到（%s 的选项）" % (text, name))
            elif st.get("do") == "if" and isinstance(st.get("flag"), str):
                add(st.get("then"), cond_text(st["flag"], flags, False))
                add(st.get("else"), cond_text(st["flag"], flags, True))
    return out


def entry_note(data, name, parents_of, causes):
    bits = []
    for h in data.get("hotspots", []):
        if h.get("scene") == name:
            bits.append("点「%s」" % h.get("label", {}).get("zh", h.get("id", "")))
    bits += causes.get(name, [])
    src = parents_of.get(name, [])
    if src and name not in causes:
        bits.append("← " + "、".join(src[:3]) + ("…" if len(src) > 3 else ""))
    return "；".join(dict.fromkeys(bits))


def build(data, items, items_base=None, phone=None):
    """返回 [(分组名, [(场景标题, [行…])…])…]"""
    strike = []
    for s in data["scenes"].values():
        for st in s:
            if isinstance(st, dict) and st.get("do") == "journal_strike" and st.get("match"):
                strike.append(st["match"])
    causes = scene_causes(data)
    parents_of = {}
    for n in data["scenes"]:
        for c in scene_children(data, n):
            parents_of.setdefault(c, []).append(n)
    out = []
    for gname, names in order_scenes(data):
        blocks = []
        for n in names:
            rows = scene_rows(data, n, strike)
            if rows:
                e = entry_note(data, n, parents_of, causes)
                nice = DEV_NAMES.get("scenes", {}).get(n, "")
                blocks.append((n + ("（%s）" % nice if nice else "") + ("    " + e if e else ""), rows))
                if causes.get(n):
                    first = "；".join(causes[n])
                    rows[0]["note"] = first + ("；" + rows[0]["note"] if rows[0]["note"] else "")
        if blocks:
            out.append((gname, blocks))

    # 界面上的字
    ui = []

    def rows_of(key, kind, who=""):
        res = []
        for path, node, parents in collect(data.get(key, []), (key,)):
            res.append(dict(scene=key, step=path[1], kind=kind, who=who, zh=node["zh"], en=node["en"],
                            src=source_of(node, parents), note="；".join(needs_note(parents[0] if parents else node) or needs_note(node)),
                            loc=fmt_path(path)))
        return res

    ui.append(("左上角目标 objectives", rows_of("objectives", "goal 目标")))
    ui.append(("左上角可选目标 side_objectives", rows_of("side_objectives", "goal 可选")))
    ui.append(("闲太久时晨自言自语 hints", rows_of("hints", "hint 提示", "晨")))
    labels = []
    for i, h in enumerate(data.get("hotspots", [])):
        if is_text(h.get("label")):
            labels.append(dict(scene="hotspots", step=i, kind="互动提示", who="", zh=h["label"]["zh"], en=h["label"]["en"],
                               src=source_of(h, []), note=h.get("id", ""), loc="hotspots[%d].label" % i))
    ui.append(("走近时的互动提示 hotspots", labels))
    sp = [dict(scene="speakers", step="", kind="说话人名字", who="", zh=v["zh"], en=v["en"], src="本2兔原文", note=k,
               loc="speakers.%s" % k) for k, v in data.get("speakers", {}).items() if is_text(v)]
    ui.append(("对话框上的名字 speakers", sp))
    out.append(("界面上的字", ui))

    # 物品：只要第二章用到的
    used = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("do") in ("give", "take", "show_item") and isinstance(o.get("item"), str):
                used.append(o["item"])
            for k in ("want", "get"):
                if isinstance(o.get(k), str):
                    used.append(o[k])
            for k, v in o.items():
                if not k.startswith("_"):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    blocks = []
    for fname, src in ((ITEMS, items), (ITEMS_BASE, items_base or {})):
        for i, it in enumerate(src.get("items", [])):
            if it.get("id") not in used:
                continue
            rows = []
            for key, kind in (("name", "物品名"), ("desc", "物品说明")):
                if is_text(it.get(key)):
                    rows.append(dict(scene=it["id"], step="", kind=kind, who="", zh=it[key]["zh"], en=it[key]["en"],
                                     src="added" if it.get("added") else "本2兔原文",
                                     note="和别的章共用" if fname == ITEMS_BASE else "",
                                     loc="%s:items[%d].%s" % (fname, i, key)))
            if rows:
                blocks.append((it["id"], rows))
    out.append(("物品", blocks))

    # 通讯器：聊天记录
    blocks = []
    for cid, c in (phone or {}).get("contacts", {}).items():
        rows = []
        if is_text(c.get("name")) or "zh" in c.get("name", {}):
            n = c["name"]
            rows.append(dict(scene=cid, step="", kind="phone 名字", who="", zh=n.get("zh", ""), en=n.get("en", ""),
                             src="added" if c.get("added") else "本2兔原文", note="", loc="%s:contacts.%s.name" % (PHONE, cid)))
        for i, m in enumerate(c.get("history", [])):
            if is_text(m):
                who = "晨" if m.get("from") == "chen" else n.get("zh", cid)
                rows.append(dict(scene=cid, step=i, kind="phone 记录", who=who, zh=m["zh"], en=m["en"],
                                 src="added" if m.get("added") else "本2兔原文", note=str(m.get("date", "")),
                                 loc="%s:contacts.%s.history[%d]" % (PHONE, cid, i)))
        if rows:
            blocks.append((cid + "（" + n.get("zh", "") + "）", rows))
    if blocks:
        out.append(("通讯器聊天记录（和别的章共用）", blocks))

    groups = code_rows()
    if groups:
        out.append(("写在代码里的字（小游戏提示、界面；有些全游戏共用）", groups))
    return out


# ----------------------------------------------------------------------- 代码里的字
GD_LIT = r'"((?:[^"\\\n]|\\.)*)"'
GD_PAIR_ZH_EN = re.compile(r'"zh"\s*:\s*' + GD_LIT + r'\s*,\s*"en"\s*:\s*' + GD_LIT)
GD_PAIR_EN_ZH = re.compile(r'"en"\s*:\s*' + GD_LIT + r'\s*,\s*"zh"\s*:\s*' + GD_LIT)
GD_ARRAY = re.compile(r'^\s*"(\w+)"\s*:\s*\[\s*' + GD_LIT + r'\s*,\s*' + GD_LIT + r'\s*\]')


def gd_decode(lit):
    try:
        return json.loads('"' + lit + '"')
    except ValueError:
        return lit


def code_rows():
    groups = {}
    cache = {}

    def lines_of(p):
        if p not in cache:
            with open(os.path.join(ROOT, p), encoding="utf-8") as f:
                cache[p] = f.read().split("\n")
        return cache[p]

    def add(group, p, ln, zh, en, note=""):
        groups.setdefault(group, []).append(dict(scene=os.path.basename(p), step=ln, kind=group, who="", zh=zh, en=en,
                                                 src="代码", note=note, loc="%s:%d" % (p, ln)))

    for group, p, zh in CODE_TEXT:
        lit = json.dumps(zh, ensure_ascii=False)
        hit = next(((ln, t) for ln, t in enumerate(lines_of(p), 1) if lit in t), None)
        if not hit:
            print("代码里的字没找到（被改了？改 CODE_TEXT）：%s %s" % (p, zh))
            continue
        ln, text = hit
        m = GD_PAIR_ZH_EN.search(text) or GD_PAIR_EN_ZH.search(text)
        en = None
        for mm in (GD_PAIR_ZH_EN.finditer(text)):
            if gd_decode(mm.group(1)) == zh:
                en = gd_decode(mm.group(2))
        for mm in (GD_PAIR_EN_ZH.finditer(text)):
            if gd_decode(mm.group(2)) == zh:
                en = gd_decode(mm.group(1))
        if en is None:
            m = re.search(r'\[\s*' + GD_LIT + r'\s*,\s*' + GD_LIT + r'\s*\]', text)
            en = gd_decode(m.group(1)) if m else ""
        add(group, p, ln, zh, en)
    for p, ln, zh, en, note in CODE_LITERAL:
        add("拼出来的字", p, ln, zh, en, note)
    for p, keys, group, note in (("scripts/i18n.gd", I18N_KEYS, "共用界面字", "全游戏共用"),
                                 ("scripts/phone_ui.gd", PHONE_UI_KEYS, "通讯器按钮", "全游戏共用")):
        for ln, text in enumerate(lines_of(p), 1):
            m = GD_ARRAY.match(text)
            if m and m.group(1) in keys:
                add(group, p, ln, gd_decode(m.group(3)), gd_decode(m.group(2)), note + "：" + m.group(1))
    return [(k, v) for k, v in groups.items()]


# ----------------------------------------------------------------------- 导出
def disp_width(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def text_lines(s, col_w):
    return sum(max(1, math.ceil(disp_width(p) / max(1.0, col_w - 1))) for p in str(s).split("\n"))


def has_author_edits(path):
    # 判断「改后」列有没有填（直接改原文列的看不出来，所以作者改的表另存别的名字，别让 export 覆盖）
    if not os.path.exists(path):
        return False
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    head = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    idx = [i for i, h in enumerate(head) if h in ("改后中文", "改后英文")]
    filled = any(str(r[i]).strip() for r in ws.iter_rows(min_row=2, values_only=True) for i in idx if i < len(r) and r[i] is not None)
    wb.close()
    return filled


def write_xlsx(tree, path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "第二章台词"
    thin = Side(style="thin", color="DDDDDD")
    border = Border(bottom=thin)
    body = Font(name="PingFang SC", size=12)
    wrap = Alignment(wrap_text=True, vertical="top")
    top = Alignment(vertical="top")
    edit_fill = PatternFill("solid", fgColor="FFF8DC")
    group_fill = PatternFill("solid", fgColor="2F4F4F")
    scene_fill = PatternFill("solid", fgColor="DCE6E4")
    head_fill = PatternFill("solid", fgColor="444444")
    choice_font = Font(name="PingFang SC", size=12, color="1F5C99")
    narr_font = Font(name="PingFang SC", size=12, italic=True, color="555555")
    grey = Font(name="PingFang SC", size=10, color="999999")

    for i, (name, w) in enumerate(COLUMNS, 1):
        c = ws.cell(row=1, column=i, value=name)
        c.font = Font(name="PingFang SC", size=12, bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(vertical="center")
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 24
    ws.freeze_panes = ws.cell(row=2, column=COL["中文原文"])

    r = 2
    seq = 0

    def band(text, fill, font, height):
        nonlocal r
        for i in range(1, len(COLUMNS) + 1):
            ws.cell(row=r, column=i).fill = fill
        c = ws.cell(row=r, column=1, value=text)
        c.font = font
        c.alignment = Alignment(vertical="center")
        ws.row_dimensions[r].height = height
        r += 1

    for gname, blocks in tree:
        band(gname, group_fill, Font(name="PingFang SC", size=13, bold=True, color="FFFFFF"), 26)
        for title, rows in blocks:
            band(title, scene_fill, Font(name="PingFang SC", size=12, bold=True), 21)
            for row in rows:
                seq += 1
                row["seq"] = seq
                vals = {"序号": seq, "场景": row["scene"], "步骤": row["step"], "类型": row["kind"], "说话人": row["who"],
                        "中文原文": row["zh"], "英文原文": row["en"], "来源": row["src"], "备注": row["note"], "定位（别改）": row["loc"]}
                for name, v in vals.items():
                    c = ws.cell(row=r, column=COL[name])
                    c.value = v
                    if isinstance(v, str):
                        c.data_type = "s"       # 「=」开头的字不要被当成公式
                    c.font = body
                    c.alignment = wrap if name in ("中文原文", "英文原文", "备注") else top
                    c.border = border
                if row["kind"].startswith("choice"):
                    ws.cell(row=r, column=COL["中文原文"]).font = choice_font
                elif row["kind"] == "narr":
                    ws.cell(row=r, column=COL["中文原文"]).font = narr_font
                for name in ("序号", "步骤", "来源", "定位（别改）"):
                    ws.cell(row=r, column=COL[name]).font = grey
                for name in ("改后中文", "改后英文"):
                    c = ws.cell(row=r, column=COL[name])
                    c.fill = edit_fill
                    c.font = body
                    c.alignment = wrap
                    c.border = border
                    c.number_format = "@"
                n = max(text_lines(row["zh"], 42), text_lines(row["en"], 42), text_lines(row["note"], 28))
                ws.row_dimensions[r].height = 18 * n + 4
                r += 1
            r += 1      # 场景之间空一行
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = openpyxl.worksheet.properties.PageSetupProperties(fitToPage=True)
    wb.save(path)
    return seq


def md_cell(s):
    return str(s).replace("|", "\\|").replace("\n", "<br>")


def write_md(tree, path):
    out = ["# 第二章台词表", "", "由 `tools/dialogue_sheet.py export` 从 `data/story_river.json` 生成，别手改这份；要改字填同名 .xlsx。", ""]
    for gname, blocks in tree:
        out += ["## " + gname, ""]
        for title, rows in blocks:
            out += ["### " + title, "", "| 序号 | 步骤 | 类型 | 说话人 | 中文 | 英文 | 备注 |", "|---|---|---|---|---|---|---|"]
            for row in rows:
                out.append("| %s | %s | %s | %s | %s | %s | %s |" % (row["seq"], row["step"], row["kind"], row["who"] or "",
                           md_cell(row["zh"]), md_cell(row["en"]), md_cell(row["note"])))
            out.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def load_json(data_dir, name):
    with open(os.path.join(data_dir, name), encoding="utf-8") as f:
        return json.load(f)


def cmd_export(a):
    path = a.out + ".xlsx"
    if not a.force and has_author_edits(path):
        sys.exit("表里已经有填过的「改后」：%s\n先 apply，或者确定不要了再加 --force。" % path)
    load_dev_names(a.data_dir)
    tree = build(load_json(a.data_dir, STORY), load_json(a.data_dir, ITEMS), load_json(a.data_dir, ITEMS_BASE), load_json(a.data_dir, PHONE))
    n = write_xlsx(tree, path)
    write_md(tree, a.out + ".md")
    print("导出 %d 行：%s" % (n, path))
    for g, blocks in tree:
        print("  %-30s %3d 段 %4d 行" % (g, len(blocks), sum(len(b[1]) for b in blocks)))
    print(a.out + ".md")


# ----------------------------------------------------------------------- 写回
def clean(v):
    if v is None:
        return ""
    return str(v).replace("\r\n", "\n").replace("\r", "\n")


LOC = "定位（别改）"


def sheet_rows(path):
    """表 → [{列名: 字符串}]（Numbers 导出可能多 sheet、多标题行：找含「定位」表头的那张）。"""
    wb = openpyxl.load_workbook(path, data_only=True)
    for ws in wb.worksheets:
        for hr in range(1, min(ws.max_row, 6) + 1):
            head = {c.value: c.column for c in ws[hr] if c.value}
            if LOC in head and "中文原文" in head:
                out = []
                for r in range(hr + 1, ws.max_row + 1):
                    row = {k: clean(ws.cell(row=r, column=c).value) for k, c in head.items()}
                    row["_row"] = r
                    out.append(row)
                return out
    sys.exit("表里找不到表头（要有「%s」和「中文原文」）：%s" % (LOC, path))


def read_edits(path, base):
    """返回 [{row, loc, op: edit/delete/insert, zh, en, old_zh, old_en, ...}]"""
    rows = sheet_rows(path)
    base_map = {r[LOC].strip(): r for r in sheet_rows(base) if r[LOC].strip()} if base else {}
    out = []
    prev = None
    for r in rows:
        loc = r[LOC].strip()
        zh_cell = r["中文原文"].strip()
        if not loc:
            # 分隔行序号列是场景名、其他列空；作者加的句子写在中文原文列
            if base and zh_cell:
                who = r.get("说话人", "").strip()
                out.append(dict(row=r["_row"], loc=prev[LOC].strip() if prev else "", op="insert", zh=zh_cell,
                                en=r.get("改后英文", "").strip() or r.get("英文原文", "").strip(), who=who or (prev.get("说话人", "") if prev else "")))
            continue
        prev = r
        o = base_map.get(loc)
        if base and o is None:
            out.append(dict(row=r["_row"], loc=loc, op="stale", why="原表里没有这个定位"))
            continue
        old_zh = o["中文原文"] if o else r["中文原文"]
        old_en = o["英文原文"] if o else r["英文原文"]
        zh = r.get("改后中文", "").strip()
        en = r.get("改后英文", "").strip()
        note = ""
        if o:
            if not zh and r["中文原文"].strip() != old_zh.strip():
                zh = r["中文原文"].strip()
                if zh == "" or zh.startswith("#"):
                    note = zh.lstrip("# ")
                    out.append(dict(row=r["_row"], loc=loc, op="delete", old_zh=old_zh, old_en=old_en, note=note))
                    continue
            if not en and r["英文原文"].strip() != old_en.strip():
                en = r["英文原文"].strip()
        if zh or en:
            out.append(dict(row=r["_row"], loc=loc, op="edit", zh=zh, en=en, old_zh=old_zh, old_en=old_en))
    return out


def split_loc(loc):
    """定位 → (文件, json 路径 tuple 或 代码行号)"""
    if ":" not in loc:
        return STORY, parse_path(loc)
    f, rest = loc.split(":", 1)
    if f.endswith(".gd"):
        return f, int(rest)
    return f, parse_path(rest)


def speaker_id(data, name):
    for k, v in data.get("speakers", {}).items():
        if isinstance(v, dict) and v.get("zh") == name:
            return k
    return None


def plan_gd(fname, edits):
    full = os.path.join(ROOT, fname)
    with open(full, encoding="utf-8") as f:
        text = f.read()
    new = text
    done, stale = [], []
    for e in edits:
        if e["op"] != "edit":
            stale.append((e, "代码里的字不能删 / 不能在这里加句子"))
            continue
        bad = None
        for lang, old in (("zh", e["old_zh"]), ("en", e["old_en"])):
            if not e[lang] or e[lang] == old:
                continue
            lit = json.dumps(old, ensure_ascii=False)
            if new.count(lit) != 1:
                bad = "代码里 %s 出现 %d 次" % (lit, new.count(lit))
                break
            new = new.replace(lit, json.dumps(e[lang], ensure_ascii=False))
        if bad:
            stale.append((e, bad))
        else:
            done.append(e)
    return new, text, done, stale


def plan_file(fname, edits, a):
    """算出一个文件的改动：返回 (新文本, 原文本, 已改行, 对不上的行)。"""
    if fname.endswith(".gd"):
        return plan_gd(fname, edits)
    full = os.path.join(a.data_dir, fname)
    with open(full, encoding="utf-8", newline="") as f:
        text = f.read()
    data = json.loads(text)
    spans = scan_strings(text)
    splices = []
    done = []
    stale = []
    expect = json.loads(text)        # 同样的改动在内存里做一遍，写之前和新文本比
    sets, deletes, inserts = [], {}, []

    for e in edits:
        path = split_loc(e["loc"])[1] if e["loc"] else ()
        if e["op"] == "stale":
            stale.append((e, e["why"]))
            continue
        if e["op"] == "insert":
            if len(path) < 3 or path[0] != "scenes" or path[1] not in data["scenes"]:
                stale.append((e, "新加的句子前面不是剧本场景的行（%s）" % e["loc"]))
                continue
            sid = speaker_id(data, e.get("who", ""))
            if not sid:
                stale.append((e, "新加的句子不知道谁说的（说话人「%s」）" % e.get("who", "")))
                continue
            step = path[:3]
            sp = {"say": sid, "zh": e["zh"], "en": e["en"] or e["zh"], "added": True}
            inserts.append((step, sp, e))
            continue
        try:
            node = get_at(data, path)
        except (KeyError, IndexError, TypeError):
            node = None
        if not is_text(node):
            stale.append((e, "定位找不到了"))
            continue
        if e["op"] == "delete":
            if clean(node["zh"]) != e["old_zh"]:
                stale.append((e, "现在是「%s」" % node["zh"]))
                continue
            elem = path[:-1] if path[-1] == "narr" else path
            elem_node = get_at(data, elem)
            if not isinstance(elem[-1], int) or not ("say" in elem_node or "narr" in elem_node):
                stale.append((e, "这一行不是一句台词，不能单独删（选项要连分支一起处理）"))
                continue
            deletes.setdefault(elem[:-1], set()).add(elem[-1])
            done.append(e)
            continue
        bad = None
        for lang, old_key in (("zh", "old_zh"), ("en", "old_en")):
            # 已经是改后的字 = 上次 apply 过了，不算对不上
            if e[lang] and clean(node[lang]) != e[old_key] and clean(node[lang]) != e[lang]:
                bad = "现在是「%s」" % node[lang]
                w = where_now(data, e[old_key]) if lang == "zh" else ""
                if w:
                    bad += "；表里那句现在在 " + w
        if bad:
            stale.append((e, bad))
            continue
        changed = False
        for lang in ("zh", "en"):
            if e[lang] and e[lang] != node[lang]:
                sets.append((path + (lang,), e[lang]))
                changed = True
        if changed:
            done.append(e)

    for path, val in sets:
        s, t = spans[path]
        splices.append((s, t, json.dumps(val, ensure_ascii=False)))
        get_at(expect, path[:-1])[path[-1]] = val
    bad_ins = []
    for step, sp, e in inserts:
        if step[-1] in deletes.get(step[:-1], ()):
            bad_ins.append((e, "它前面那句被删了，放不下；请把它写到别的行后面"))
            continue
        _, end = spans[step]
        indent = "\n" + "\t" * 3
        splices.append((end, end, "," + indent + json.dumps(sp, ensure_ascii=False)))
        done.append(e)
    stale += bad_ins
    # 同一步后面加多句：保持表里的先后。splice 按位置倒着做，同位置的要反过来排
    ins_expect = {}
    for step, sp, e in inserts:
        ins_expect.setdefault(step, []).append(sp)
    for lst, idx in deletes.items():
        arr = get_at(data, lst)
        kept = [i for i in range(len(arr)) if i not in idx]
        run = sorted(idx)
        k = 0
        while k < len(run):
            j = k
            while j + 1 < len(run) and run[j + 1] == run[j] + 1:
                j += 1
            first, last = run[k], run[j]
            if last + 1 < len(arr):
                splices.append((spans[lst + (first,)][0], spans[lst + (last + 1,)][0], ""))
            else:
                before = [i for i in kept if i < first]
                if before:
                    splices.append((spans[lst + (before[-1],)][1], spans[lst + (last,)][1], ""))
                else:
                    splices.append((spans[lst + (first,)][0], spans[lst + (last,)][1], ""))
            k = j + 1
    # 内存里同步：先按步骤从大到小加句子 / 删句子，下标才不乱
    struct = []
    for step, sps in ins_expect.items():
        struct.append((step[:-1], step[-1] + 0.5, "ins", sps))
    for lst, idx in deletes.items():
        for i in idx:
            struct.append((lst, i, "del", None))
    for lst, i, kind, sps in sorted(struct, key=lambda x: (-len(x[0]), str(x[0]), -x[1])):
        arr = get_at(expect, lst)
        if kind == "del":
            del arr[i]
        else:
            arr[int(i) + 1:int(i) + 1] = sps
    new = text
    for pos, (s, t, rep) in sorted(enumerate(splices), key=lambda x: (x[1][0], x[0]), reverse=True):
        new = new[:s] + rep + new[t:]
    if json.loads(new) != expect:
        sys.exit("内部检查没过，没有写：%s 的结果和预期不一样" % fname)
    return new, text, done, stale


def where_now(data, text):
    """这句现在在哪（只用来报错时帮忙找）。"""
    for path, node, _ in collect(data, ()):
        if node["zh"] == text or node["en"] == text:
            return fmt_path(path)
    return ""


def run_story_check():
    if not os.path.exists(GT_SH):
        print("找不到 gt.sh（%s），没跑 --story_check。设 GT_SH 环境变量指过去再跑一次。" % GT_SH)
        return 2
    log = os.path.join(tempfile.gettempdir(), "dialogue_sheet_story_check.log")
    subprocess.run([GT_SH, "300", log, "--", "--chapter=river", "--story_check"], check=False)
    errs = []
    done = False
    with open(log, encoding="utf-8", errors="replace") as f:
        for ln in f:
            if ln.startswith("STORY_CHECK done"):
                done = True
            elif ln.startswith("STORY_CHECK ") and not ln.startswith("STORY_CHECK info:"):
                errs.append(ln.rstrip())
            elif "SCRIPT ERROR" in ln or "Parse JSON failed" in ln:
                errs.append(ln.rstrip())
    if not done:
        print("--story_check 没跑完，日志：%s" % log)
        return 2
    print("--story_check：%d 错误（日志 %s）" % (len(errs), log))
    for e in errs[:30]:
        print("  " + e)
    return 1 if errs else 0


def cmd_apply(a):
    edits = read_edits(a.xlsx, a.base)
    if not edits:
        print("表里没有改动，什么也没改。")
        return 0
    by_file = {}
    for e in edits:
        by_file.setdefault(split_loc(e["loc"])[0] if e["loc"] else STORY, []).append(e)
    plans = {f: plan_file(f, es, a) for f, es in by_file.items()}
    stale = [s for p in plans.values() for s in p[3]]
    done = [e for p in plans.values() for e in p[2]]
    for e, why in stale:
        print("对不上 第 %d 行 %s：%s" % (e["row"], e["loc"], why))
    if stale and not a.skip_stale:
        print("有 %d 行对不上（表导出以后 json 改过），一行都没写。重新导出再填，或者加 --skip-stale 只写对得上的。" % len(stale))
        return 1
    for e in done:
        if e["op"] == "delete":
            print("删 第 %d 行 %s：%s" % (e["row"], e["loc"], e["old_zh"]) + ("（作者写：%s）" % e["note"] if e.get("note") else ""))
        elif e["op"] == "insert":
            print("加 第 %d 行（%s 后面，%s）：%s" % (e["row"], e["loc"], e.get("who", ""), e["zh"]))
        else:
            print("改 第 %d 行 %s" % (e["row"], e["loc"]))
            if e["zh"]:
                print("    中：%s" % e["zh"])
            if e["en"]:
                print("    英：%s" % e["en"])
    zh_only = [e for e in done if e["op"] != "delete" and e["zh"] and not e["en"]]
    if zh_only:
        print("提醒：%d 行只改了中文，英文还是旧的（新加的句子英文先和中文一样）：%s" % (len(zh_only), "、".join(str(e["row"]) for e in zh_only)))
    print("共 %d 行" % len(done))
    if a.dry_run or not done:
        return 0
    backup = os.path.join(tempfile.gettempdir(), "the_cloud_dialogue_backup", time.strftime("%m%d_%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    for f, (new, old, _, _) in plans.items():
        full = os.path.join(ROOT, f) if f.endswith(".gd") else os.path.join(a.data_dir, f)
        with open(full, encoding="utf-8", newline="") as h:
            if h.read() != old:
                sys.exit("%s 在这几秒里被别的会话改了，没有写。再跑一次。" % f)
        if new == old:
            continue
        shutil.copy2(full, backup)
        tmp = full + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as h:
            h.write(new)
        os.replace(tmp, full)
    print("原文件备份在 %s" % backup)
    if a.no_check:
        return 0
    return run_story_check()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("export", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--data-dir", default=os.path.join(ROOT, "data"), help="json 所在目录（测试时指向副本）")
    e = sub.choices["export"]
    e.add_argument("--out", default=OUT, help="输出路径（不带扩展名）")
    e.add_argument("--force", action="store_true", help="表里有填过的字也覆盖")
    p = sub.choices["apply"]
    p.add_argument("--xlsx", default=OUT + ".xlsx")
    p.add_argument("--base", help="导出时的原表：给了就认「直接改原文列」「改空 = 删」「新行 = 加句」")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-stale", action="store_true", help="跳过对不上的行，写其他行")
    p.add_argument("--no-check", action="store_true", help="写完不跑 --story_check")
    a = ap.parse_args()
    sys.exit(cmd_export(a) if a.cmd == "export" else cmd_apply(a))


if __name__ == "__main__":
    main()
