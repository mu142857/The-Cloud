#!/usr/bin/env python3
"""第二章主线剧本：把 data/story_river.json 按实际游玩顺序导出成给作者读、给作者改的 txt。

    python3 tools/story_to_txt.py

台词、旁白、选项、日记原样从 json 取，一个字不改。动作（walk / anim / prop……）用下面几张表翻成一句中文。
段落顺序是 MAIN：河流主线 --story_auto --main_only 实际走的顺序（11-05），分支场景嵌在选项 / 条件下面。
表里没有的动作名会直接报错，不会漏写；写完检查主线每一句都在 txt 里。

同时写一份同名「.底稿.txt」：作者改完以后和它比（tools/story_from_txt.py）。作者已经改过 txt 时拒绝覆盖（加 --force 才覆盖）。
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "第二章_主线剧本.txt")
BASE = os.path.join(ROOT, "docs", "第二章_主线剧本.底稿.txt")

# 段落：(场景, 标题)。第三项是同一段的另一个入口。
MAIN = [
    ("start_river", "河面。飞机撞进水道，晨从舱门出来"),
    ("bank_meet", "河岸。晨走到箱子边，妮芙从箱子后面钻出来"),
    ("bank_meet_b", "河岸台阶。捞杯子，捞漂走的东西"),
    ("bank_cup", "河岸。互相报名字，阿汀冲出来，把飞机拖上岸"),
    ("home_enter", "妮芙家一楼。进门，本子，泡茶，报名字"),
    ("home_bell", "妮芙家一楼。铃响，妮芙不认识晨了"),
    ("home_bell_b", "妮芙家一楼。她翻本子重新认人"),
    ("home_postcard", "妮芙家。来客册在窗边晾着"),
    ("book_peek3", "妮芙家三楼窗边。坐下等"),
    ("home_deer_msg", "妮芙家窗边。鹿发来消息"),
    ("home_wait_talk", "妮芙家窗边。晨问她「等很久的人怎么办」，闪回"),
    ("home_drawing", "妮芙家窗边。她看见晨本子上的画"),
    ("home_drawing_b", "妮芙家二楼。翻柜子，放影像，影像盒卡住"),
    ("home_tape_wrap", "妮芙家二楼。影像盒要换读取头，她拿出气瓶"),
    ("home_out", "出门，回河岸"),
    ("market_go", "高处市集。路过"),
    ("market_to_stairwell", "市集下楼"),
    ("oldstreet_go", "旧街。台阶泡在水里"),
    ("sluice", "旧街。调水闸"),
    ("oldstreet_corner", "旧街拐角。果酱店，墙上的身高刻线"),
    ("warehouse_go", "旧街仓库入口。系绳，下水"),
    ("warehouse_in", "水下仓库。找读取头和密封圈，发现泄水门记录"),
    ("home_coat", "妮芙家。阿汀来了，对质是谁开的闸"),
    ("pocket", "妮芙家。晨摸口袋"),
    ("home_coat_b", "妮芙家。铃又响，晨打开和朋友的聊天记录"),
    ("tape_fix", "妮芙家二楼。修好影像盒，看大象"),
    ("tape_sound", "妮芙家二楼。听见大象的声音"),
    ("bank_to_market", "再去市集"),
    ("market_to_oldstreet_again", "再经过楼梯间，到旧街"),
    ("south_go", "南桥。找机位，看大象灰影，选桥洞，量脚印"),
    ("south_dock", "南桥旧货台。查装卸记录"),
    ("dock_plates", "南桥旧货台。选编号牌"),
    ("south_back", "回旧街。妮芙捡到铜铃，送给晨，回河岸"),
    ("farewell", "妮芙家。喝茶，留画，拿礼物"),
    ("farewell_b", "妮芙家。她说画得像水壶"),
    ("farewell_phone", "妮芙家。加通讯录，回河岸"),
    ("plane_fix", "河岸。修飞机"),
    ("depart", "河岸。起飞。第二章完"),
]
# 这些场景不单独成段：玩家这一遍走的那一支，已经嵌在选项 / 条件下面
INLINE_ONLY = {"n_meet_plain", "n_name_p", "n_note_p", "ch_bread_busy", "rb_who_a", "deer_msg_m", "dr_el", "ch_tape_sorry",
               "n_tank_p", "sluice_open", "oldstreet_jam", "pocket_stone", "el_rope", "dock_plate_12", "n_tea_p", "ch_bye_write", "n_bye_p"}

ROOMS = {"river_bank": "河岸", "river_home": "妮芙家", "market": "高处市集", "stairwell": "楼梯间", "oldstreet": "旧街",
         "warehouse": "水下仓库", "southbridge": "南桥", "cockpit": "驾驶舱"}
WHO = {"chen": "晨", "niff": "妮芙", "ting": "阿汀"}
PLACE = {
    "river_bank_crates": "箱子", "river_bank_plane": "飞机", "river_bank_hatch": "舱门", "river_bank_steps": "台阶", "river_bank_toolkit": "工具箱",
    "river_bank_ting": "岸边", "river_bank_niff": "家门口那边", "river_home_door": "门口", "river_home_table": "桌子", "river_home_kitchen": "厨房",
    "river_home_chair": "窗边的椅子", "river_home_window": "窗边", "river_home_player": "播放器", "river_home_player_r": "播放器右边",
    "river_home_cabinet": "柜子", "river_home_labels": "门边", "river_home_chen": "屋子中间", "river_home_niff": "屋子里", "market_tool_stall": "修补摊",
    "oldstreet_railing": "栏杆边", "oldstreet_corner": "拐角", "oldstreet_steps": "台阶", "oldstreet_height_wall": "墙边",
    "oldstreet_dry_step": "干的台阶", "oldstreet_warehouse_entry": "仓库入口", "oldstreet_hook": "钩子那儿", "warehouse_broken_box": "破箱子", "warehouse_sluice_door": "泄水门",
    "southbridge_arch_wrong": "错的桥洞", "southbridge_arch": "对的桥洞", "southbridge_footprints": "脚印那儿", "southbridge_dock": "旧货台",
    "southbridge_dock_step": "货台台阶",
}
ANIM = {
    "chen": {
        "reach": "伸手", "hook": "用钩子把杯子钩上来", "tie": "绑机翼", "lean_hatch": "靠着舱门", "step_off": "跳下来", "open_toolkit": "打开工具箱",
        "close_toolkit": "合上工具箱", "pickup": "捡东西", "flip_pages": "翻本子", "draw": "画画", "touch_cover": "摸本子封面", "shake_head": "摇头",
        "take_box": "接过影像盒", "plug_in": "插上播放器", "sit_up": "坐直", "press_button": "狂按按钮", "freeze_hand": "手停住", "lower_hand": "放下手",
        "nod": "点头", "hold_box": "抱着影像盒", "tie_rope": "系绳子", "untie_rope": "解开绳子", "point_log": "指记录", "point_niff": "指妮芙",
        "show_item": "把东西拿出来", "reach_pocket": "手伸进口袋", "touch_seam": "摸到口袋缝", "withdraw_hand": "抽回手", "stop": "停住", "flip_to_page": "翻到那一页",
        "dry_sleeves": "晾袖子", "close_journal": "合上日记", "hold_paper": "拿着纸", "hold_shell": "扶住外壳", "open_mouth": "张开嘴", "laugh": "笑",
        "pen_stop": "笔停住", "glance_phone": "瞥一眼通讯器", "move_journal": "挪开日记", "listen": "听", "palm_table": "手掌贴桌面", "lift_hand": "抬起手",
        "point_page": "指着那一页", "compare": "对比", "mark_paper": "在纸上标记", "look_up": "抬头看", "crouch": "蹲下", "hand_compare": "拿手比", "rubbing": "拓脚印",
        "open_record": "打开记录", "hold_plate": "拿起编号牌", "flip": "翻到背面", "sit": "坐下", "hold_far": "拿远了看", "wash": "洗铜铃", "clear_bell": "洗干净铜铃",
        "sip": "喝茶", "turn_wheel": "转闸轮", "reach_pocket_card": "手伸进口袋摸卡的位置", "sign": "签名", "type": "打字", "repair": "修", "steady_bell": "扶住晃的铜铃", "write": "写",
    },
    "niff": {
        "crouch": "蹲下", "spin": "绕一圈", "look_bowl": "看碗", "read_notebook": "看本子", "push_cup": "把碗推过来", "write": "写本子",
        "pull_notebook": "把本子拉过来", "pause": "愣住", "search_notebook": "翻本子找", "press_page": "按住那一页", "look_close": "凑近看", "nod": "点头",
        "flip": "翻本子", "push_book": "把本子推过来", "peek_journal": "偷看晨的本子", "stand_up": "站起来", "hold_up_kettle": "从柜子里举出一只水壶",
        "shake_head": "摇头", "search_index": "翻目录", "cover_button": "按住晨的手", "show_lid": "指盖子上的字", "unplug": "拔插头", "wrap_box": "把影像盒包好",
        "lean_listen": "趴在栏杆上听", "tuck_notebook": "收好本子", "stop": "停下", "scratch_cheek": "挠脸", "look_up": "抬头看", "hand_board": "递板子",
        "point_board": "指板子", "pickup": "捡东西", "read_slow": "慢慢读", "hand_still": "手停住", "hold_record": "拿着记录", "look_photo": "看照片",
        "press_photo": "按住照片", "hold_coat": "抱着外套", "search_photo": "找照片", "touch_photo": "摸照片", "push_head": "把读取头按进去", "read_steps": "照本子念步骤",
        "connect_wire": "接线", "lean_close": "凑近", "tune": "调声音", "tail_up": "尾巴翘起来", "smile_blank": "笑了，但已经忘了为什么", "startle": "吓一跳",
        "laugh": "笑", "palm_table": "手掌贴桌面", "foot_compare": "比脚的大小", "pull_foot": "缩回脚", "count": "数", "sit": "坐下", "swing_feet": "晃脚",
        "cover_ears": "捂耳朵", "hand_bell": "把铜铃递过来", "write_tag": "写标签", "look_long": "看了很久", "label_box": "往影像盒上贴标签", "flip_bottle": "翻过一个瓶子",
        "hand_bag": "递袋子", "hand_pen": "递笔", "hold_phone": "拿着通讯器", "stick_label": "贴标签", "wave": "挥手", "think": "想了想", "look_screen": "看屏幕", "catch_crumbs": "接饼干渣",
    },
    "ting": {
        "check": "检查", "hold_shell": "摸外壳", "hand_coat": "递外套", "nod": "点头", "show_record": "指记录", "coat_on_chair": "把外套搭在椅子上", "look_down": "低头",
    },
}
SFX = {
    "thud": "砰的一声", "cup_clink": "杯子叮一声", "drag_plane": "拖飞机的声音", "kitchen_timer": "厨房定时器响", "bell_soft": "铃响了", "tape_run": "影像开始放",
    "tape_glitch": "影像卡住", "low_call_tape": "影像里传来低低的叫声", "splash_in": "扑通下水", "door_touch": "有人碰门", "sluice_open": "闸门打开", "bell_dull": "铜铃闷响",
    "bell_ring": "铜铃响了", "engine_idle": "发动机转起来", "engine_up": "发动机加速", "hatch_open": "舱门打开", "hatch_close": "舱门关上",
}
PROP = {
    ("river_bank_crates", "tail_still"): "箱子后面露出一截鲸鱼壳的尾巴", ("river_bank_shallow", "floating"): "水面上漂着东西",
    ("niff_notebook", "tea_arrow"): "本子上画了个先放茶的箭头", ("niff_notebook", "star"): "本子上画了颗星", ("river_home_chair", "by_window"): "椅子拖到窗边",
    ("warehouse_tall_cabinet", "lifted"): "高柜子浮起来", ("warehouse_inner_door", "open"): "里面的门开了", ("river_home_table", "old_pages"): "桌上摊开旧纸页",
    ("guestbook", "drawing_in"): "画夹进来客册", ("southbridge_routemap", "fallen"): "航线图掉在地上", ("river_bank_plane", "beached"): "飞机被拖上岸", ("river_bank_plane", "straps_drying"): "飞机绑好，晾着", ("river_home_table", "two_bowls_water"): "桌上摆了两碗水",
    ("river_home_hourglass", "running"): "沙漏开始漏", ("river_home_hourglass", "empty"): "沙漏漏完了", ("guestbook", "drying"): "来客册晾在窗边",
    ("river_home_cabinet", "open"): "柜门开了", ("river_home_cabinet", "footage_box"): "柜子里有个影像盒", ("river_home_player", "footage_part1"): "屏幕上是河面的影像",
    ("river_home_player", "stopped"): "画面停了", ("river_home_player", "red_blink"): "红灯闪", ("oldstreet_steps", "submerged"): "台阶泡在水下",
    ("oldstreet_steps", "revealed"): "水退下去，台阶露出来", ("oldstreet_height_wall", "seen"): "看见墙上的刻线", ("warehouse_sluice_door", "log"): "门上有操作记录",
    ("niff_photo", "on_table"): "桌上放着一张照片", ("river_home_player", "footage_part2"): "影像接着放", ("river_home_player", "paused"): "暂停",
    ("river_home_player", "ear_swing"): "画面里大象的左耳晃了一下", ("southbridge_footprints", "seen"): "地上有很大的脚印", ("river_bank_plane", "fixed"): "飞机修好了",
    ("river_home_table", "two_cups_tea"): "桌上有两杯茶", ("chen_drawing", "done"): "画好了", ("cockpit_bell", "bell"): "铜铃挂在驾驶舱里",
}
# 走到哪个场景要玩家做什么
ITEM_FILES = ["items.json", "items_later.json"]
KEY_LABEL = {
    "start": "", "intro": "", "gate_1": "第一道闸卡住时", "gate_2": "第二道闸卡住时", "fail_1": "转过头时", "give": "错太多次时", "done": "做完时",
    "hint_sink": "站着不动时", "hint": "站着不动时", "sank_1": "东西第一次沉下去时", "sank": "东西沉下去时", "give_some": "没捞全时", "give_all": "全捞到时",
    "wrong": "拧反时", "aligned": "对上时", "ask": "", "right": "选对时", "miss_1": "早了时",
}
OPTION_NOTE = {
    "n_meet_courier": "之后这一章妮芙都叫晨「取件员」，终章的消息也这么叫",
    "n_meet_bio": "之后只有报名字那句不一样",
    "n_meet_rude": "之后和选「不是。」一样",
    "dock_plate_07": "看完回到这里重选",
    "dock_plate_21": "看完回到这里重选",
}
COND = {
    "river_n_courier": "开头选了「对，我是来取件的。」的人",
    "!river_n_courier": "其他人",
    "river_n_bio": "开头选了「你是谁？我在哪儿？」的人",
    "river_n_plain": "开头选了「不是。」或「你没长眼啊？把我的飞船撞坏了！」的人",
    "c1_mom": "第一章对鹿说过「我是你的母亲」的人",
    "!c1_mom": "第一章没这么说的人",
    "burned_blue_stone": "飞行一烧了蓝色石头的人",
    "!burned_blue_stone": "飞行一没烧蓝色石头的人",
    "burned_commute_card": "飞行一烧了通勤卡的人",
    "river_biscuits": "在市集买了饼干的人",
    "!river_biscuits": "没买饼干的人",
    "river_rule_self": "找阿汀定第十三条时选了「落水的人先捞自己」的人",
    "river_rule_wish": "找阿汀定第十三条时选了「不许对着飞机许愿」的人",
    "river_rule_niff": "找阿汀定第十三条时选了「妮芙说了算」的人",
}
OPTIONAL = [
    "河岸可点：杯子（杯底纸条，叫小姐那句，进妮芙家以后就没了）",
    "河岸可点：门牌、面包店、屋顶窄桥、水底的街，晨说一句或记一句",
    "河岸可点：飞机（晾着时晨说一句，后面零件、道别各一句）",
    "阿汀：一直跟他说话，就一条一条往下念河岸条例（四十来条）；另有几句跟着进度变的闲聊",
    "阿汀支线：把影像盒拿给他看，定第十三条（三选一），修飞机时他会念回来",
    "妮芙闲聊：河岸、妮芙家、旧街、南桥、临走前各有一句；市集里点她是看那块防水板",
    "妮芙家可点：罐子（盐的标签）、标签、沙漏、厨房、窗边的来客册（还湿的时候）",
    "市集支线：饼干摊砍价（三选一），买了饼干，旧街拐角会坐下来分着吃",
    "市集支线：料理鼠妈，帮她看锅放料（小游戏），之后可以拿东西换吃的，换了汤终章多一格燃料",
    "市集可点：吊着的篮子、修补摊、屋顶的桥、摊主",
    "楼梯间可点：水母",
    "旧街可点：水位刻线、两层招牌；妮芙聊天",
    "水下仓库可点：箱子（标签）；妮芙",
    "来客册支线：修好影像盒以后，回窗边扇干来客册（小游戏），看名单，知道弥洛的朋友寄过信，拿到杯底记号",
    "南桥可点：灯柱、屋顶装饰；妮芙聊天",
]


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)


class Writer:
    def __init__(self, data):
        self.d = data
        self.sc = data["scenes"]
        self.lines = []
        self.buf = []
        self.items = {}
        for f in ITEM_FILES:
            for it in load(f).get("items", []):
                self.items[it["id"]] = it.get("name", {}).get("zh", it["id"])
        self.flags = set()
        self.goal = ""
        self.used = set()

    def flush(self, ind=""):
        if self.buf:
            self.lines.append(ind + "[" + "，".join(dict.fromkeys(self.buf)) + "]")
            self.buf = []

    def act(self, text):
        if text:
            self.buf.append(text)

    def out(self, text, ind=""):
        self.flush(ind)
        self.lines.append(ind + text)

    def who(self, k):
        if k in WHO:
            return WHO[k]
        return self.d["speakers"].get(k, {}).get("zh", k)

    def say(self, st, ind="", tag=""):
        self.out("%s%s：%s" % (tag, self.who(st["say"]), st["zh"]), ind)

    def walk(self, st):
        who, to = st.get("who"), st.get("to")
        if isinstance(to, (int, float)):
            return {"chen": "晨走了几步", "niff": "妮芙飘到一边", "ting": "阿汀从左边走过来"}.get(who, who)
        if to == "chen":
            return "%s走到晨身边" % WHO.get(who, who)
        if to not in PLACE:
            sys.exit("PLACE 里没有：%s" % to)
        return "%s走到%s" % (WHO.get(who, who), PLACE[to])

    def fade(self, st):
        room = ROOMS.get(st.get("room"), st.get("room"))
        if st.get("style") == "pixel":
            return "格子转场，到%s的飞机旁" % room
        return "转场到%s" % room

    def steps(self, steps, ind=""):
        """一串步骤。"""
        for st in steps:
            if not isinstance(st, dict):
                continue
            if "say" in st:
                self.say(st, ind)
            elif "narr" in st:
                self.out("旁白：" + st["narr"]["zh"], ind)
            else:
                self.do(st, ind)
        self.flush(ind)

    def branch_body(self, name, ind):
        """一个分支场景的内容（不跟 goto）。"""
        self.used.add(name)
        self.steps([s for s in self.sc[name] if s.get("do") != "goto"], ind)

    def do(self, st, ind):
        do = st.get("do")
        if do == "flag":
            if isinstance(st.get("set"), str):
                self.flags.add(st["set"])
        elif do in ("wait", "face", "pose", "ambient", "follow", "goto", "journal_strike", "flashback_wake", "end_chapter"):
            if do == "journal_strike":
                self.act("把日记里「%s」那句划掉" % st["match"])
            elif do == "end_chapter":
                self.act("第二章完")
        elif do == "anim":
            who = st.get("who")
            name = st.get("name")
            if name not in ANIM.get(who, {}):
                sys.exit("ANIM 里没有：%s.%s" % (who, name))
            self.act("%s%s" % (WHO[who], ANIM[who][name]))
        elif do == "walk":
            self.act(self.walk(st))
        elif do == "sfx":
            self.act(SFX.get(st.get("name")))
        elif do == "prop":
            self.act(PROP.get((st.get("id"), st.get("state"))))
        elif do == "show":
            self.act("%s出现" % WHO.get(st["who"], st["who"]))
        elif do == "hide":
            self.act({"chen": "晨在飞机里", "ting": "阿汀走了"}.get(st["who"], st["who"]))
        elif do == "fade_to":
            self.act(self.fade(st))
        elif do == "give":
            self.act("得到：" + self.items.get(st["item"], st["item"]))
        elif do == "take":
            self.act("交出：" + self.items.get(st["item"], st["item"]))
        elif do == "show_item":
            self.act("拿出来看：" + self.items.get(st["item"], st["item"]))
        elif do == "journal":
            self.out("日记：" + st["zh"], ind)
        elif do == "phone_msg":
            self.out("通讯器消息：" + st["zh"], ind)
            if st.get("reply"):
                self.out("晨回：" + st["reply"]["zh"], ind)
        elif do == "phone_add":
            self.act("通讯录里加上「%s」" % st["zh"])
        elif do == "phone_open":
            self.act("晨打开和朋友的聊天记录")
        elif do == "flashback":
            self.act("闪回：城市街上，最后一片白")
            for l in st.get("lines", []):
                self.out("闪回里的字：" + l["zh"], ind)
        elif do == "if":
            self.cond(st, ind)
        elif do in ("choice", "pick"):
            self.choice(st, ind)
        elif do == "mechanic":
            self.mech(st, ind)
        else:
            sys.exit("不认识的步骤：%s" % st)

    def cond(self, st, ind):
        self.flush(ind)
        for key, flag in (("then", st["flag"]), ("else", ("!" + st["flag"]) if not st["flag"].startswith("!") else st["flag"][1:])):
            name = st.get(key)
            if not name or name not in self.sc:
                continue
            if name == "sluice_later" or name in {m[0] for m in MAIN}:
                continue
            label = COND.get(flag)
            if flag == "river_sluice_open":
                label = None
            elif not label:
                sys.exit("COND 里没有：%s" % flag)
            mark = len(self.lines)
            if label:
                self.out("（%s）" % label, ind)
                mark = len(self.lines)
            self.branch_body(name, ind + ("    " if label else ""))
            if label and len(self.lines) == mark:
                self.lines.pop()      # 这个条件下面什么也没有
        self.flush(ind)

    def choice(self, st, ind):
        self.flush(ind)
        for o in st["options"]:
            text = o["label"]["zh"] if "label" in o and isinstance(o["label"], dict) else o["zh"]
            target = o.get("scene")
            body = [s for s in self.sc.get(target, []) if s.get("do") != "goto"] if target else []
            note = OPTION_NOTE.get(target)
            say_only = [s for s in body if "say" in s or "narr" in s]
            head = "▶ " + text
            acts = [s for s in body if "say" not in s and "narr" not in s and s.get("do") not in ("flag", "wait", "face")]
            if note:
                head += " → " + note
            if len(say_only) == 1 and not acts and not note and "say" in say_only[0]:
                self.out(head + " → %s：%s" % (self.who(say_only[0]["say"]), say_only[0]["zh"]), ind)
                self.used.add(target)
            else:
                if not body:
                    head += " → 什么也没发生，接着往下"
                self.out(head, ind)
                if target:
                    self.branch_body(target, ind + "    ")
            if target:
                for s in self.sc.get(target, []):
                    if s.get("do") == "flag" and isinstance(s.get("set"), str):
                        pass
        if not any(str(o.get("scene", "")).startswith("dock_plate") for o in st["options"]):
            self.out("（汇合）", ind)

    def mech(self, st, ind):
        mid = st.get("id")
        if mid == "river_salvage":
            names = "、".join(i["label"]["zh"] for i in st.get("items", []))
            self.act("小游戏：站在岸边抛钩，把漂过来的东西捞上来（%s，还有一个%s）" % (names, st["box"]["label"]["zh"]))
        elif mid == "river_valve":
            self.act("小游戏：按住转闸轮，管子不咕噜了就松手，一共三道闸。表盘上是妮芙画的小鱼、鞋、茶壶、鲸鱼")
        elif mid == "river_borrowed":
            boxes = "、".join("%s（她忘了时写「%s」）" % (b["label"]["zh"], b["code"]["zh"]) for b in st.get("boxes", []))
            self.act("小游戏：水下的箱子漂来漂去，选一只打开，找读取头和浮筒密封圈。妮芙头上的泡泡破光了，标签就变成她的暗号。箱子：" + boxes)
        elif mid == "river_thread":
            self.act("小游戏：拧接头。管子上印着「%s」的箭头，妮芙贴的便条写着「%s」，照箭头拧会松，反着拧才紧" % (st.get("arrow", {}).get("zh", ""), st.get("note", {}).get("zh", "")))
        elif mid == "river_bridge_view":
            arches = " / ".join(a["label"]["zh"] for a in st.get("arches", []))
            self.act("小游戏：走到对的位置，取景框和影像对上，大象的灰影从桥洞底下走过去。然后选它从哪个桥洞过去（%s）" % arches)
        elif mid == "river_explore_order":
            rows = st.get("rows", [])
            if rows:
                self.act("妮芙的防水板上写着：" + " / ".join(r["zh"] for r in rows))
            else:
                self.act("晨看防水板")
        else:
            sys.exit("没写这个小游戏：%s" % mid)
        self.flush(ind)
        lines = st.get("lines", {})
        if isinstance(lines, dict):
            for key, arr in lines.items():
                label = KEY_LABEL.get(key)
                if label is None and key.startswith("wrong_"):
                    label = "选错桥洞时"
                if label is None and key == "shallows":
                    continue
                if label is None:
                    sys.exit("KEY_LABEL 里没有：%s" % key)
                for s in arr:
                    if "say" in s:
                        self.say(s, ind, "（%s）" % label if label else "")
                    elif "narr" in s:
                        self.out(("（%s）" % label if label else "") + "旁白：" + s["narr"]["zh"], ind)
                if mid == "river_borrowed" and key == "intro":
                    for j in st.get("junk", []):
                        self.out("（开错箱子时）" + j["zh"], ind)

    def objective(self):
        for o in self.d.get("objectives", []):
            if all(f in self.flags for f in o.get("need", [])) and not any(f in self.flags for f in o.get("not", [])):
                return o["zh"]
        return ""

    def entrance(self, name):
        for h in self.d.get("hotspots", []):
            if h.get("scene") == name and "_side" not in h:
                if h.get("trigger") == "enter":
                    return "[玩家走到「%s」那儿，自动开始]" % h["label"]["zh"]
                return "[玩家走到「%s」，按互动]" % h["label"]["zh"]
        return ""

    def paragraph(self, name, title):
        extra = "、south_walk_in" if name == "south_go" else ""
        self.lines.append("")
        self.lines.append("## %s（%s%s）" % (title, name, extra))
        self.used.add(name)
        ent = self.entrance(name)
        if ent:
            self.lines.append(ent)
        self.steps(self.sc[name])
        g = self.objective()
        if g and g != self.goal:
            self.goal = g
            self.lines.append("（左上角目标变成：%s）" % g)


def build():
    d = load("story_river.json")
    w = Writer(d)
    w.lines += [
        "第二章 主线剧本",
        "照现在游戏里的样子，按玩家实际走的顺序写的，没有改任何一句，不通顺的地方也原样留着。",
        "",
        "[方括号] 是动作，我概括的。「名字：台词」是原文。▶ 是选项，（汇合）是几个选项走回同一条路。",
        "（开头选了……的人）这种括号，是只有这些人才看到下面缩进的那几句。",
        "每段标题括号里的英文是场景名，改的时候留着，我靠它对回去。其他都可以改：重写台词、删句、加句、调顺序，都直接改。",
    ]
    for name, title in MAIN:
        if name not in d["scenes"]:
            sys.exit("场景没有了：%s" % name)
        w.paragraph(name, title)
    w.lines += ["", "## 可选，不在主线", ""]
    w.lines += ["- " + x for x in OPTIONAL]
    w.lines.append("")
    return d, w


def check(d, w):
    text = "\n".join(w.lines)
    missing = []

    def go(o):
        if isinstance(o, dict):
            if "zh" in o and "en" in o and o["zh"] not in text:
                missing.append(o["zh"])
            for k, v in o.items():
                if not k.startswith("_"):
                    go(v)
        elif isinstance(o, list):
            for v in o:
                go(v)

    for name in w.used:
        go(d["scenes"][name])
    return missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if os.path.exists(OUT) and os.path.exists(BASE) and not a.force:
        if open(OUT, encoding="utf-8").read() != open(BASE, encoding="utf-8").read():
            sys.exit("作者已经改过 %s，没有覆盖（要覆盖加 --force）" % OUT)
    d, w = build()
    miss = check(d, w)
    text = "\n".join(w.lines)
    for p in (OUT, BASE):
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
    print(OUT, len(w.lines), "行")
    if miss:
        print("主线里有 %d 句没写进 txt：" % len(miss))
        for m in miss:
            print("  " + m)


if __name__ == "__main__":
    main()
