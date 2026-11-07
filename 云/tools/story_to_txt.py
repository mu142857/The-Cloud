#!/usr/bin/env python3
"""章节主线剧本：把剧情 json 按实际游玩顺序导出成给作者读、给作者改的 txt。

    python3 tools/story_to_txt.py                  第二章（data/story_river.json）
    python3 tools/story_to_txt.py --chapter=final  第三章（data/story_final.json）

台词、旁白、选项、日记原样从 json 取，一个字不改。动作（walk / anim / prop……）用下面几张表翻成一句中文。
第二章段落顺序是 MAIN：河流主线 --story_auto --main_only 实际走的顺序（11-05），分支场景嵌在选项 / 条件下面。
第三章段落顺序是 FINAL_PLAN：--chapter=final --story_auto 和 --beat=final_ending_1 / final_ending_3 / final_ending_home --story_auto 实际走的顺序（11-07 结局重构后）；
if / goto 照引擎的规矩展开（分支跳走就是跳走，分支播完没跳走就接着往下），不在 FINAL_PLAN 里的小场景嵌在条件下面。
表里没有的动作名会直接报错，不会漏写；写完检查主线每一句都在 txt 里（第三章检查整个文件的每一句）。

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
    ("bank_cup", "河岸飞机旁。阿汀把飞机拴住，妮芙邀请晨去她家"),
    ("home_enter", "妮芙家一楼。她问晨是谁"),
    ("home_asked", "妮芙家一楼。晨问本子里有没有大象"),
    ("home_find", "妮芙家二楼。她翻柜子，录像带放不出，又忘了晨是谁"),
    ("home_find_b", "妮芙家二楼。记下来，任务开始"),
    ("home_out", "出门，回河岸"),
    ("market_go", "高处市集。路过"),
    ("market_to_stairwell", "市集下楼"),
    ("stairwell_jelly", "楼梯间。水母飘过来要东西"),
    ("oldstreet_go", "旧街。台阶泡在水里"),
    ("sluice", "旧街。调水闸，水退下去，露出氧气瓶"),
    ("oldstreet_tank_take", "旧街。捡氧气瓶"),
    ("warehouse_go", "旧街仓库入口。下水"),
    ("warehouse_in", "水下仓库。找读取头"),
    ("warehouse_out", "水下仓库。自己游到入口上去，再自己走回妮芙家（旧街 → 楼梯间 → 市集 → 河岸），路上能去市集换密封圈"),
    ("tape_fix", "回妮芙家二楼。修好录像带，看大象"),
    ("bank_to_market", "再去市集"),
    ("market_to_oldstreet_again", "再经过楼梯间，到旧街"),
    ("south_go", "南桥。到了"),
    ("south_intro", "南桥。一共三个桥洞"),
    ("south_arch_left", "南桥。看左边的桥洞（三个洞顺序随便）"),
    ("south_arch_far", "南桥。看右边的桥洞"),
    ("south_arch_right", "南桥。看中间的桥洞：对了，量脚印"),
    ("south_trail_start", "南桥。顺着发亮的脚印走（一共十几个，走到一个亮下一个）"),
    ("south_trail_end", "南桥。脚印走到旧货台"),
    ("south_dock", "南桥旧货台。查装卸记录"),
    ("dock_plates", "南桥旧货台。选编号牌"),
    ("south_back", "回旧街。妮芙捡到铜铃，送给晨，回河岸（没有密封圈的，这时先出「获取密封圈」，拿到了才能去道别）"),
    ("farewell", "妮芙家。喝茶，留画，拿礼物"),
    ("farewell_b", "妮芙家。她说画得像水壶"),
    ("farewell_phone", "道别完，回河岸"),
    ("plane_fix", "河岸。修飞机"),
    ("depart", "河岸。起飞。第二章完"),
]
# 这些场景不单独成段：玩家这一遍走的那一支，已经嵌在选项 / 条件下面
INLINE_ONLY = {"n_meet_plain", "n_name_p", "n_note_p", "ch_bread_busy", "rb_who_a", "deer_msg_m", "dr_el", "ch_tape_sorry",
               "n_tank_p", "sluice_open", "oldstreet_jam", "pocket_stone", "el_rope", "dock_plate_12", "n_tea_p", "ch_bye_write", "n_bye_p"}

FADE_AT = {"river_bank_toolkit": "飞机旁", "river_home_chen": "妮芙家屋里", "river_home_player_r": "妮芙家二楼柜子旁（不走路，直接到）",
           "oldstreet_warehouse_entry": "旧街仓库入口"}
ROOMS = {"river_bank": "河岸", "river_home": "妮芙家", "market": "高处市集", "stairwell": "楼梯间", "oldstreet": "旧街",
         "warehouse": "水下仓库", "southbridge": "南桥", "cockpit": "驾驶舱"}
WHO = {"chen": "晨", "niff": "妮芙", "ting": "阿汀", "jellyfish": "水母"}
PLACE = {
    "river_bank_crates": "箱子", "river_bank_plane": "飞机", "river_bank_hatch": "舱门", "river_bank_steps": "台阶", "river_bank_toolkit": "工具箱",
    "river_bank_ting": "岸边", "river_bank_niff": "家门口那边", "river_home_door": "门口", "river_home_table": "桌子", "river_home_kitchen": "厨房",
    "river_home_chair": "窗边的椅子", "river_home_window": "窗边", "river_home_player": "播放器", "river_home_player_r": "播放器右边",
    "river_home_cabinet": "柜子", "river_home_labels": "门边", "river_home_chen": "屋子中间", "river_home_niff": "屋子里", "market_tool_stall": "修补摊",
    "oldstreet_railing": "栏杆边", "oldstreet_corner": "拐角", "oldstreet_steps": "台阶", "oldstreet_height_wall": "墙边",
    "oldstreet_dry_step": "干的台阶", "oldstreet_warehouse_entry": "仓库入口", "oldstreet_tank": "氧气瓶那儿", "southbridge_lamps": "歪掉的灯下面", "oldstreet_hook": "钩子那儿", "warehouse_broken_box": "破箱子", "warehouse_sluice_door": "泄水门",
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
        "hand_bag": "递袋子", "hand_pen": "递笔", "hold_phone": "拿着通讯器", "stick_label": "贴标签", "wave": "挥手", "hop": "蹦了一下", "think": "想了想", "look_screen": "看屏幕", "catch_crumbs": "接饼干渣",
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
    ("oldstreet_tank", "revealed"): "水退后旧街露出一个氧气瓶", ("river_home_player", "camera_tilt"): "镜头转过去", ("southbridge_hair", "shown"): "石沿上挂着一撮毛", ("southbridge_arch", "scratches"): "石沿蹭秃了",
    ("river_bank_crates", "tail_still"): "箱子后面露出一截鲸鱼壳的尾巴", ("river_bank_shallow", "floating"): "水面上漂着东西",
    ("niff_notebook", "tea_arrow"): "本子上画了个先放茶的箭头", ("niff_notebook", "star"): "本子上画了颗星", ("river_home_chair", "by_window"): "椅子拖到窗边",
    ("warehouse_tall_cabinet", "lifted"): "高柜子浮起来", ("warehouse_inner_door", "open"): "里面的门开了", ("river_home_table", "old_pages"): "桌上摊开旧纸页",
    ("guestbook", "drawing_in"): "画夹进来客册", ("southbridge_routemap", "fallen"): "航线图掉在地上", ("river_bank_plane", "beached"): "飞机换到岸边（晨在远处，看不见这一下）", ("river_bank_plane", "straps_drying"): "飞机拴好了", ("river_home_table", "two_bowls_water"): "桌上摆了两碗水",
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
    "n_meet_bio": "之后和选「不是。」一样",
    "n_meet_rude": "之后和选「不是。」一样",
    "dock_plate_07": "看完回到这里重选",
    "dock_plate_21": "看完回到这里重选",
}
COND = {
    "river_n_courier": "开头选了「对，我是来取件的。」的人",
    "!river_n_courier": "其他人",
    "!river_seal_got": "还没有密封圈的人",
    "river_seal_got": "已经有密封圈的人",
    "river_n_bio": "开头选了「你是谁？我在哪儿？」的人",
    "river_n_plain": "开头选了「不是。」或「你没长眼啊？把我的飞船撞坏了！」的人",
    "c1_mom": "第一章对鹿说过「我是你的母亲」的人",
    "!c1_mom": "第一章没这么说的人",
    "burned_blue_stone": "飞行一烧了蓝色石头的人",
    "!burned_blue_stone": "飞行一没烧蓝色石头的人",
    "burned_commute_card": "飞行一烧了通勤卡的人",
    "river_biscuits": "在市集买了饼干的人",
    "!river_biscuits": "没买饼干的人",
    "river_robbed": "进门时说了打劫的人",
    "!river_robbed": "进门时没说打劫的人",
    "river_rule_self": "找阿汀定第十三条时选了「落水的人先捞自己」的人",
    "river_rule_wish": "找阿汀定第十三条时选了「不许对着飞机许愿」的人",
    "river_rule_niff": "找阿汀定第十三条时选了「妮芙说了算」的人",
}
OPTIONAL = [
    "河岸可点：杯子（杯底纸条，叫小姐那句）",
    "河岸可点：门牌、面包店、屋顶窄桥、水底的街，晨说一句或记一句",
    "河岸可点：飞机（零件、道别各一句）",
    "阿汀：一直跟他说话，就一条一条往下念河岸条例（四十来条）；另有几句跟着进度变的闲聊",
    "阿汀支线：把录像带拿给他看，定第十三条（三选一），修飞机时他会念回来",
    "妮芙闲聊：河岸、妮芙家、市集、旧街、南桥、临走前各有一句",
    "妮芙家可点：茶碗（你喝茶吗 / 忘了放茶叶 / 没烧水，上一轮作者写的三句）、罐子（盐的标签）、标签、沙漏、厨房",
    "妮芙家窗边：来客册（修好录像带以前只说「还是湿的」，修好以后是来客册支线）",
    "市集支线：饼干摊砍价（三选一），买了饼干，旧街拐角会坐下来分着吃",
    "市集支线：料理鼠妈，帮她看锅放料（小游戏），之后可以拿东西换吃的，换了汤终章多一格燃料",
    "市集修补摊：用任意一件东西换密封圈（什么时候都能换，不用等任务）",
    "河岸飞机：有「获取密封圈」任务时点飞机，妮芙提醒去哪拿",
    "市集可点：吊着的篮子、屋顶的桥、摊主",
    "楼梯间：水母（没给东西时还能再给；给过以后每次点都说「好像叫寿登耄耋？」）",
    "旧街可点：拐角（果酱店、身高刻线，买过饼干会坐下来分）、水位刻线、两层招牌",
    "水下仓库可点：破箱子那儿（标签）；绿柜子（平时只看标签「修船的，还不急」，有「获取密封圈」任务时翻出一个密封圈，拿过以后是「抽屉空了」）",
    "来客册支线：修好录像带以后，回窗边扇干来客册（小游戏），看名单，知道弥洛的朋友寄过信，拿到杯底记号",
    "南桥可点：灯柱、屋顶装饰",
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
            return "格子转场，到%s" % FADE_AT.get(st.get("at"), room)
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
        elif do == "inner":
            if st.get("zh"):
                self.out("晨（心里，字直接打在画面上，没有对话框）：" + st["zh"], ind)
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
        elif do == "barter":
            self.flush(ind)
            d = self.d["barter"][st["npc"]]
            self.act("弹出背包，选一件东西给它（任务物品和终章要用的不收），也可以选「算了」")
            self.flush(ind)
            for t in d.get("trades", [])[:1]:
                if t.get("scene") in self.sc:
                    self.branch_body(t["scene"], ind)
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
            if flag in ("river_sluice_open", "river_jelly_given"):   # 刚设上就判断，不是分支
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
            self.act("小游戏：水下的箱子漂来漂去，选一只打开，找读取头（箱子里没有密封圈，密封圈在绿柜子）。妮芙头上的泡泡破光了，标签就变成她的暗号。箱子：" + boxes)
        elif mid == "river_thread":
            self.act("小游戏：拧接头。管子上印着「%s」的箭头，妮芙贴的便条写着「%s」，照箭头拧会松，反着拧才紧" % (st.get("arrow", {}).get("zh", ""), st.get("note", {}).get("zh", "")))
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
        hs = sorted(self.d.get("hotspots", []), key=lambda h: h.get("trigger") != "enter")
        for h in hs:
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


# ---------------- 第三章（终章） ----------------

OUT_FINAL = os.path.join(ROOT, "docs", "第三章_主线剧本.txt")
BASE_FINAL = os.path.join(ROOT, "docs", "第三章_主线剧本.底稿.txt")

# str 是大标题（"结局" 开头或尾声：目标从下降那一刻重新算），tuple 是 (场景, 标题)。
FINAL_PLAN = [
    "飞向云层星",
    ("start_final", "驾驶舱。离开河流星，修东西，哼歌"),
    ("final_route", "碎石带"),
    ("final_cabinet", "燃料柜。数一数还剩什么"),
    ("final_fuel", "燃料柜。晨对自己说"),
    ("final_paper", "燃料柜。能烧的这一次都能烧完（燃料到 300 就能收起，芦苇地要 760）"),
    ("final_approach", "接近云层。画背面的字，第一页，第四次闪回"),
    ("final_descend", "最后的选择：芦苇地 / 云层小镇 / 回母星"),
    "结局一：西侧旧货场的芦苇地（真结局，大象真的在，吃草很响，不理人。燃料要 760，不够的话这一项是灰的）",
    ("ending1", "降落"),
    ("e1_prints", "脚印"),
    ("e1_meet", "浅水边。见到大象"),
    ("e1_sit", "坐下来看它"),
    ("e1_plant_ask", "问哪里能种种子（种子没烧的人才有）"),
    ("e1_plant", "种种子（种子没烧的人才有）"),
    ("e1_evening", "傍晚。修飞机，写日记"),
    ("e1_cockpit", "驾驶舱。看窗外的大象"),
    "尾声（只有芦苇地这条有：鹿 → 弥洛 → 妮芙 → 城市 → 列车）",
    ("epilogue", "森林路口。鹿"),
    ("epi_miluo", "树屋。弥洛"),
    ("epi_niff", "妮芙家"),
    ("epi_city", "回到城市"),
    ("epi_home", "回家的列车"),
    ("epi_home_seat", "列车上。坐下。全剧终"),
    "结局二：居民区·云层小镇（大家都看得见，只有晨看不见；停在小镇，全剧终）",
    ("ending3", "降落"),
    ("e3_plaza", "广场。大家都说它在喷泉边"),
    ("e3_plaza_rest", "晨还是看不见"),
    ("e3_touch", "第二天。伸手，大家欢呼；回住处写日记"),
    ("e3_confess", "又过了一天。晨说手心是空的"),
    ("e3_listen", "喷泉另一侧"),
    ("e3_wait", "自己走走"),
    ("e3_round", "云台尽头"),
    ("e3_bench", "长椅"),
    ("e3_plant", "种种子（种子没烧的人才有）"),
    ("e3_night", "回住处。改日记"),
    ("final_end_town", "全剧终"),
    "结局三：掉头回母星（接下来就是上面尾声最后那段「回家的列车」，一模一样）",
    ("ending_home", "掉头"),
]
FINAL_OPTIONAL = [
    ("ck_bell", "驾驶舱：铜铃"), ("ck_drawing", "驾驶舱：最初的画"), ("yard_sign", "芦苇地：指示牌"), ("e1_elephant_chat", "芦苇地：大象"),
    ("e1_passerby_chat", "芦苇地：路过的人"), ("town_basket", "云层小镇：空篮子"),
    ("e3_crowd_chat", "云层小镇：周围的人"), ("e3_townsfolk_chat", "云层小镇：居民"), ("epi_deer_chat", "尾声：鹿"),
    ("epi_miluo_chat", "尾声：弥洛"), ("epi_niff_chat", "尾声：妮芙"),
]
# 没有字的场景，不用写进 txt
FINAL_SILENT = {"yard_grass"}
# 只是往下问一句的条件场景，自己不写「（……的人）」
FINAL_PASS = {"epi_miluo_q"}
FINAL_LABEL_SCENE = {
    "epi_home_chart": "没烧座位图，第一章也没和鹿认亲的人",
    "epi_miluo_kept": "种子没种也没烧的人",
}
FINAL_COND = {
    "barter_rat_chef_soup": "在市集用浮木跟鼠妈换了汤的人",
    "!barter_rat_chef_soup": "没换汤的人",
    "barter_rat_chef_fire": "把不灭的木头给了鼠妈、换了饭团的人",
    "barter_rat_chef_recipe": "用大嘴鸟的羽毛跟鼠妈换了菜谱的人",
    "barter_toucan_whistle": "第一章跟大嘴鸟换了鸟哨的人",
    "musicbox_fixed": "第一章修好了音乐盒的人",
    "!musicbox_fixed": "没修好音乐盒的人",
    "final_ending_1": "结局一",
    "final_ending_3": "云层小镇",
    "final_seed_planted": "把种子种下了的人",
    "river_cup_traced": "看过来客册、拿到杯底记号的人",
    "sa_sign_done": "第一章把路标送回空地的人",
    "sa_radio_done": "第一章把收音机送回小吃棚的人",
    "saw_rock": "第一章看过空地岩画的人",
    "c1_mom": "第一章对鹿说过「我是你的母亲」的人",
    "!c1_mom": "其他人",
    "c1_child": "第一章让鹿把晨当孩子的人",
}
FINAL_GOTO_NOTE = {
    "final_descend": "往下接「最后的选择」", "ending1": "芦苇地", "ending3": "云层小镇", "ending_home": "回母星", "epi_home": "接「回家的列车」（和尾声最后一段一样）", "final_end_town": "全剧终",
}
WHO_FINAL = {"chen": "晨", "niff": "妮芙", "elephant": "大象", "deer": "鹿", "miluo": "弥洛", "passerby": "路过的人", "resident": "居民", "townsfolk": "居民", "crowd": "周围的人"}
ROOMS_FINAL = {"cockpit": "驾驶舱", "reed_field": "芦苇地", "town": "云层小镇", "town_room": "住处", "forest": "森林路口", "treehouse": "树屋",
               "river_home": "妮芙家", "city": "城市", "home_train": "回家的列车"}
FADE_AT_FINAL = {"town_fountain_stand": "喷泉边", "yard_landing": "西边的旧货场", "east_landing": "东边的缓坡"}
PLACE_FINAL = {"east_rest": "飞机旁躺下的地方", "train_seat": "座位", "yard_landing": "飞机", "east_far": "远处", "east_water": "水边", "yard_hill": "山坡那边",
               "town_bench": "长椅", "town_plaza_side": "广场那边"}
ANIM_FINAL = {
    "chen": {
        "cap_twist": "拧瓶盖", "check": "看了看", "close_lid": "合上盖子", "delete": "删字", "dig": "挖土", "drink": "喝水", "eat": "吃东西", "fill": "填土",
        "finger_still": "手指停住", "flip_phone": "把通讯器翻过去", "fold_bag": "叠好袋子", "hand_flip": "翻过手看手心", "hand_over": "递过去", "hand_still": "手停住",
        "hold_close": "把它贴近", "hold_phone": "拿着通讯器", "hug_bag": "抱住背包", "hum": "哼歌", "lie": "躺下", "lips": "抿嘴", "look_around": "四处看",
        "open_map_fold": "打开折着的纸", "peek": "探头看", "pen_hover": "笔悬着", "pocket": "收进口袋", "press": "按下去", "raise_hand": "抬手", "reach_bag": "手伸进背包",
        "reach_camera": "想拍照", "release": "松手", "smooth_paper": "把纸抚平", "stand": "站起来", "step_aside": "让到一边", "step_back": "往后退", "sulk": "撇嘴",
        "take_cup": "接过杯子", "take_phone": "拿出通讯器", "thumb_lid": "拇指按着盖子", "untie": "解绳子", "wait": "等着",
        "pickup": "捡起绑带", "tie": "系好绑带",
    },
    "elephant": {"drink": "喝水", "ear": "耳朵动了动", "eat": "吃草", "graze": "吃草", "look": "看了一眼", "trunk_branch": "鼻子勾树枝", "trunk_out": "鼻子伸过来",
                 "trunk_up": "鼻子抬起来", "tug_grass": "扯草", "turn": "转身"},
    "passerby": {"laugh": "笑"},
    "resident": {"lift": "帮忙抬机翼", "sit": "坐下"},
    "townsfolk": {"sit": "坐下"},
    "deer": {"ear": "耳朵动了动", "lean": "凑过来", "look": "看"},
    "miluo": {"check": "看了看", "flip": "翻过来", "read": "读", "screw": "拧螺丝"},
    "niff": {"read": "看本子"},
}
SFX_FINAL = {
    "bag_open": "打开背包", "beacon_slow": "信标慢慢响", "bird_whistle": "鸟哨响", "biscuit_rustle": "饼干袋窸窣响", "bottle_knock": "空瓶子磕了一下", "bridge_lamps": "影像里桥灯的声音",
    "cabinet_open": "柜门开了", "cap_twist": "拧瓶盖", "chewing": "咀嚼声", "cloud_part": "云层散开", "confirm": "确认的提示音", "convert": "变成燃料", "crowd_cheer": "人群欢呼",
    "door_open": "门开了", "elephant_breath": "大象的呼吸声", "elephant_low_call": "大象的低鸣", "engine_off": "发动机关了", "engine_steady": "发动机平稳地响", "engine_test": "试发动机",
    "footage_play": "影像放起来", "fountain": "喷泉声", "grass_tear": "扯草声", "hiss_small": "小声漏气", "hull_rattle": "船壳咯吱响", "hum_late": "哼慢了一拍", "hum_new_key": "换了个调",
    "hum_stop": "哼不下去了", "hum_wrong": "哼错一个音", "knock": "敲门", "landing_soft": "平稳落地", "latch_tap": "搭扣轻响", "leak_hiss": "漏气声", "leak_slow": "慢慢漏气", "leak_small": "还有一点漏气",
    "musicbox_open": "音乐盒打开", "musicbox_play": "音乐盒响", "musicbox_stop": "音乐盒停了", "niff_bell": "妮芙的铃响", "plaza_noise": "广场上很吵", "rough_landing": "重重落地",
    "screw_back": "螺丝拧回去", "screw_half": "螺丝拧到一半", "seat_creak": "座椅吱呀响", "stomach": "肚子叫", "thruster_recover": "推进器缓过来", "tighten": "拧紧", "valve_close": "关阀门",
    "water_drop": "水滴声", "water_pour": "倒水", "water_slosh": "水晃", "wrench_half": "扳手转了半圈",
}
PROP_FINAL = {
    ("cockpit_bag", "bottle_side_pocket"): "瓶子放进背包侧袋", ("cockpit_bell", "empty_loop"): "铜铃那儿只剩绳圈", ("cockpit_bell", "moved"): "把铜铃挪了个地方", ("cockpit_bell", "rope_short"): "绳圈收短",
    ("cockpit_bell", "rope_swing"): "绳圈晃", ("cockpit_burnlist", "close"): "凑近看已烧掉的清单", ("cockpit_burnlist", "flipped"): "把清单翻过去", ("cockpit_cabinet", "closed"): "燃料柜关上",
    ("cockpit_cabinet", "empty_bottle"): "空瓶子放回柜子", ("cockpit_cabinet", "hand"): "手放在柜门上", ("cockpit_cabinet", "open"): "燃料柜开着", ("cockpit_cabinet", "put_back"): "把东西放回柜子",
    ("cockpit_copilot", "toolbag_wrench"): "副驾驶座上放着工具包和扳手", ("cockpit_drawing", "beside_panel"): "画放到仪表盘边", ("cockpit_drawing", "open"): "打开那张画",
    ("cockpit_drawing", "under_page"): "画压到那一页下面", ("cockpit_drawing", "within_reach"): "画放在够得着的地方", ("cockpit_footage", "lid_closed"): "合上影像盒盖",
    ("cockpit_journal", "deer_page"): "翻到鹿那一页", ("cockpit_journal", "first_page_out"): "把第一页取下来", ("cockpit_lamp", "off"): "灯关了", ("cockpit_map", "beside_panel"): "航图放到仪表盘边",
    ("cockpit_map", "line_pressed"): "按住航线", ("cockpit_map", "open"): "打开航图", ("cockpit_note", "flipped"): "把纸条翻过来", ("cockpit_note", "folded"): "纸条叠好", ("cockpit_note", "folded_half"): "纸条叠到一半",
    ("cockpit_note", "open"): "又打开纸条", ("cockpit_phone", "face_down"): "通讯器扣着放", ("cockpit_phone", "screen_on"): "通讯器屏幕亮了", ("cockpit_phone", "seat_screen_up"): "通讯器屏幕朝上放在座位上",
    ("cockpit_screen", "descent"): "屏幕切到下降航道", ("cockpit_screen", "orbit"): "切回轨道", ("cockpit_tools", "left"): "工具换到左边", ("cockpit_window", "cloud_low"): "窗外云层近了",
    ("cockpit_window", "cloud_orbit"): "窗外云层在下面", ("cockpit_window", "cloud_sea"): "窗外是云海", ("cockpit_window", "elephant_shadow"): "窗外有大象的影子过去",
    ("cockpit_window", "yard_elephant_far"): "窗外远处是大象", ("cockpit_window", "yard_parked"): "窗外是停飞机的地方", ("east_bed", "planted"): "花圃种上了", ("east_plane", "wing_up"): "机翼抬起来",
    ("east_toolbag", "ready"): "工具包放好", ("east_tree", "bark_rubbed"): "树皮蹭秃了", ("east_water_cup", "placed"): "旁边留了一杯水", ("forest_map", "corrected"): "地图改好了",
    ("river_home_cup", "offered"): "妮芙递来一杯", ("sky", "day"): "天亮了", ("sky", "dusk"): "傍晚了", ("sky", "night"): "夜里", ("sky", "shadow_pass"): "一个影子掠过", ("town_bed", "planted"): "花圃种上了",
    ("town_toolbag", "on_seat"): "工具包放在座位上", ("train_seat", "sun_on_knees"): "太阳晒到膝盖", ("train_window", "afternoon_sun"): "窗外是下午的太阳", ("train_window", "trees_passing"): "窗外的树一棵棵过去",
    ("treehouse_glass", "paper"): "玻璃杯压住那张纸", ("yard_stone", "placed"): "放了块石头做记号", ("yard_toolbag", "placed"): "工具包放下",
}


class FinalWriter(Writer):
    """第三章：动作表多，if / goto 要照引擎的跳转展开。第二章的 Writer 不动，第二章的导出结果一字不变。"""

    def __init__(self, data):
        super().__init__(data)
        self.main = {x[0] for x in FINAL_PLAN if isinstance(x, tuple)}
        self.arm_seen = {}
        self.sfx = dict(SFX, **SFX_FINAL)
        self.prop = {**PROP, **PROP_FINAL}

    def who(self, k):
        return WHO_FINAL.get(k) or super().who(k)

    def walk(self, st):
        who, to = st["who"], st["to"]
        if to not in PLACE_FINAL:
            sys.exit("PLACE_FINAL 里没有：%s" % to)
        return "%s走到%s" % (WHO_FINAL[who], PLACE_FINAL[to])

    def fade(self, st):
        return "转场到" + (FADE_AT_FINAL.get(st.get("at")) or ROOMS_FINAL[st["room"]])

    def label(self, flag, scene):
        if scene in FINAL_LABEL_SCENE:
            return FINAL_LABEL_SCENE[scene]
        if flag in FINAL_COND:
            return FINAL_COND[flag]
        if flag in COND:
            return COND[flag]
        neg = flag.startswith("!")
        name = flag[1:] if neg else flag
        if name.startswith("burned_"):
            item = self.items.get(name[len("burned_"):])
            if item:
                return ("没烧%s的人" if neg else "烧了%s的人") % item
        sys.exit("FINAL_COND 里没有：%s" % flag)

    def exit_of(self, name):
        """这个场景最后跳到哪儿；播完回来接着往下就是 None。"""
        steps = [s for s in self.sc.get(name, []) if isinstance(s, dict)]
        if not steps:
            return None
        last = steps[-1]
        if last.get("do") == "goto":
            return last["scene"]
        if last.get("do") == "if" and last.get("then") and last.get("else"):
            a, b = last["then"], last["else"]
            ea, eb = self.exit_of(a), self.exit_of(b)
            if eb == a:
                return a
            if ea == b:
                return b
            if ea and ea == eb:
                return ea
        return None

    def flow(self, name, ind, stop=frozenset()):
        """播一个场景。返回 True = 跳走了，调用它的场景不再往下。"""
        self.used.add(name)
        steps = [s for s in self.sc[name] if isinstance(s, dict)]
        return self.run(steps, ind, stop)

    def run(self, steps, ind, stop):
        for i, st in enumerate(steps):
            if st.get("do") == "goto":
                self.jump(st["scene"], ind, stop)
                return True
            if st.get("do") == "if":
                if self.branch(st, steps[i + 1:], ind, stop):
                    return True
            elif "say" in st:
                self.say(st, ind)
            elif "narr" in st:
                self.out("旁白：" + st["narr"]["zh"], ind)
            else:
                self.do(st, ind)
        self.flush(ind)
        return False

    def jump(self, to, ind, stop):
        self.flush(ind)
        if to not in self.main and to not in stop:
            self.flow(to, ind, stop)

    def capture(self, fn, ind):
        keep_lines, keep_buf = self.lines, self.buf
        self.lines, self.buf = [], []
        fn()
        self.flush(ind)
        got = self.lines
        self.lines, self.buf = keep_lines, keep_buf
        return got

    def arm_flags(self, scene):
        """这一支走完会设哪些 flag（分支里最后那一步设的，不跟 goto）。"""
        return {s["set"] for s in self.sc.get(scene, []) if isinstance(s, dict) and s.get("do") == "flag" and isinstance(s.get("set"), str)}

    def arm_body(self, scene, flag, ind, stop):
        """一支分支的内容。分支里设的 flag 只在这一支算数，目标变化写在这一支里。"""
        keep = set(self.flags)
        before = self.objective()
        if scene in self.arm_seen:
            return [ind + "（和上面「%s」那一支一样）" % self.arm_seen[scene]]
        if scene not in FINAL_PASS:
            self.arm_seen[scene] = self.label(flag, scene)

        def play():
            if isinstance(scene, list):
                self.run(scene, ind, stop)
            else:
                self.flow(scene, ind, stop)

        got = self.capture(play, ind)
        goal = self.objective()
        if goal and goal != before:
            got.append(ind + "（左上角目标变成：%s）" % goal)
        self.flags = keep
        return got

    def arms(self, arms, ind, stop):
        done = []
        before = set(self.flags)
        added = []
        for flag, scene in arms:
            key = scene if isinstance(scene, str) else None
            if key is None:
                self.used.add("(rest)")
                body = self.capture(lambda s=scene: self.run(s, ind + "    ", stop), ind + "    ")
            else:
                body = self.arm_body(scene, flag, ind + "    ", stop)
                added.append(self.arm_flags(scene) - before)
            done.append((flag, key, body))
        if len(added) == 2:                 # 两支都设的 flag，走完都算数
            self.flags |= added[0] & added[1]
        if len(done) == 2 and done[0][2] and done[0][2] == done[1][2]:      # 两支一模一样，不分了
            self.lines += [x[4:] for x in done[0][2]]
            return
        for flag, key, body in done:
            if not body:
                continue
            if key in FINAL_PASS:
                self.lines += [x[4:] for x in body]
                continue
            self.lines.append(ind + "（%s）" % self.label(flag, key))
            self.lines += body

    def branch(self, st, rest, ind, stop):
        """一个 if。返回 True = 后面的步骤不会再走（都跳走了）。"""
        self.flush(ind)
        flag = st["flag"]
        neg = flag[1:] if flag.startswith("!") else "!" + flag
        a, b = st.get("then"), st.get("else")
        if a and b:
            ea, eb = self.exit_of(a), self.exit_of(b)
            join = None
            if eb == a:
                join, arms = a, [(neg, b)]
            elif ea == b:
                join, arms = b, [(flag, a)]
            else:
                arms = [(flag, a), (neg, b)]
                if ea and ea == eb:
                    join = ea
            self.arms(arms, ind, stop | {join} if join else stop)
            if join:
                self.jump(join, ind, stop)
                return True
            return bool(ea and eb)
        target, f = (a, flag) if a else (b, neg)
        other = neg if a else flag
        if target in self.main:
            return False
        e = self.exit_of(target)
        body = [s for s in rest if s.get("do") != "goto"]
        tail = [s for s in rest if s.get("do") == "goto"]
        if e and body and tail and tail[0]["scene"] == e:    # 这一支跳走了，后面那几步是其他人才走的
            self.arms([(f, target), (other, body)], ind, stop | {e})
            self.jump(e, ind, stop)
            return True
        self.arms([(f, target)], ind, stop | {e} if e else stop)
        return False

    def branch_body(self, name, ind):
        self.used.add(name)
        e = self.exit_of(name)
        self.flow(name, ind, frozenset({e}) if e else frozenset())

    def choice(self, st, ind):
        self.flush(ind)
        pick = st["do"] == "pick"
        if st.get("title"):
            self.out("屏幕标题：" + st["title"]["zh"], ind)
        for o in st["options"]:
            text = o["label"]["zh"] if "label" in o else o["zh"]
            target = o.get("scene")
            head = "▶ " + text
            for need in o.get("need", []):
                head = "▶ （%s才有这句）%s" % (self.label(need, None), text)
            if o.get("fuel_need"):
                head += "（燃料不到 %d 这一项是灰的，写「燃料还差 X」，选不了）" % o["fuel_need"]
            if o.get("confirm"):
                head += "（二次确认：%s）" % o["confirm"]["zh"]
            if target in self.main:
                self.out(head + " → " + FINAL_GOTO_NOTE[target], ind)
                continue
            body = [s for s in self.sc.get(target, []) if s.get("do") != "goto"]
            says = [s for s in body if "say" in s or "narr" in s]
            acts = [s for s in body if "say" not in s and "narr" not in s and s.get("do") not in ("flag", "wait", "face")]
            if len(says) == 1 and not acts and "say" in says[0]:
                self.out(head + " → %s：%s" % (self.who(says[0]["say"]), says[0]["zh"]), ind)
                self.used.add(target)
            else:
                if not says and not acts:
                    head += " → 什么也没发生，接着往下"
                self.out(head, ind)
                self.branch_body(target, ind + "    ")
        if not pick:
            self.out("（汇合）", ind)

    def do(self, st, ind):
        do = st.get("do")
        if do == "anim":
            who, name = st["who"], st["name"]
            text = ANIM_FINAL.get(who, {}).get(name) or ANIM.get(who, {}).get(name)
            if not text:
                sys.exit("ANIM_FINAL 里没有：%s.%s" % (who, name))
            self.act(WHO_FINAL[who] + text)
        elif do == "sfx":
            if st["name"] not in self.sfx:
                sys.exit("SFX_FINAL 里没有：%s" % st["name"])
            self.act(self.sfx[st["name"]])
        elif do == "prop":
            key = (st["id"], st["state"])
            if key not in self.prop:
                sys.exit("PROP_FINAL 里没有：%s" % (key,))
            self.act(self.prop[key])
        elif do == "show":
            self.act("%s出现" % WHO_FINAL[st["who"]])
        elif do == "hide":
            self.act({"elephant": "大象走远了", "resident": "居民走了", "crowd": "周围的人散了"}[st["who"]])
        elif do == "fuel":
            if "sub" in st:
                self.act("燃料少了 %d" % st["sub"])
            elif "have" in st:
                self.act("燃料表：有 %d，要 %d" % (st["have"], st["need"]))
            else:
                self.act("燃料表：现在要 %d" % st["need"])
        elif do == "cockpit_dash":
            self.act("飞机往前一冲，黑屏")
        elif do == "music":
            self.act("配乐淡出" if st.get("stop") else "配乐淡入（第一章树屋那首）")
        elif do == "debris_steer":
            self.act("小游戏：穿过碎石带（撞一下少 %d 燃料，最多少 %d）" % (st["fuel_per_bump"], st["fuel_max_loss"]))
        elif do == "keepsake_choice":
            self.act("弹出燃料柜，航线图 %s → %s，玩家选要烧的东西，可以选好几件。每件东西选中时、烧掉时的话，都在最后「燃料柜」那几段"
                     % (st["route_from"]["zh"], st["route_to"]["zh"]))
        elif do == "phone_draft":
            self.out("通讯器，输入栏里打好了：%s（玩家选「发送」或「暂时不发」）" % st["zh"], ind)
        elif do == "flashback":
            self.act("第四次闪回：城市街上，站着不动，触手和人群从身边过去")
            for l in st.get("lines", []):
                self.out("闪回里的字：" + l["zh"], ind)
        elif do == "end_chapter":
            self.act("全剧终，放名单")
        elif do == "if":
            self.branch(st, [], ind, frozenset())
        else:
            super().do(st, ind)

    def paragraph(self, name, title):
        extra = "、e2_night" if name == "e2_night_go" else ""
        self.lines.append("")
        self.lines.append("## %s（%s%s）" % (title, name, extra))
        self.arm_seen = {}
        ent = self.entrance(name)
        if ent:
            self.lines.append(ent)
        self.flow(name, "")
        g = self.objective()
        if g and g != self.goal:
            self.goal = g
            self.lines.append("（左上角目标变成：%s）" % g)

    def keepsakes(self):
        k = next(s for s in self.sc["final_paper"] if s.get("do") == "keepsake_choice")
        self.lines += ["", "# 燃料柜：每件东西选中时、烧掉时（燃料柜只有那一次，列表里只有手上有的）"]
        for item in k["items"]:
            look, burn, keep = k["look_scenes"].get(item), k["scenes"].get(item), k.get("keep_scenes", {}).get(item)
            names = "、".join(x for x in (look, keep, burn) if x)
            self.lines += ["", "## 燃料柜：%s（%s）" % (self.items[item], names)]
            self.arm_seen = {}
            for tag, scene in (("选中时", look), ("放回去时", keep), ("烧掉时", burn)):
                if scene:
                    self.lines.append("（%s）" % tag)
                    self.flow(scene, "    ")


def build_final():
    d = load("story_final.json")
    w = FinalWriter(d)
    w.lines += [
        "第三章 主线剧本",
        "照现在游戏里的样子，按玩家实际走的顺序写的，没有改任何一句，不通顺的地方也原样留着。",
        "",
        "[方括号] 是动作，我概括的。「名字：台词」是原文。▶ 是选项，（汇合）是几个选项走回同一条路。",
        "（烧了……的人）（结局一）这种括号，是只有这些人才看到下面缩进的那几句。",
        "飞向云层星只有一遍，然后在「最后的选择」分三个去处：芦苇地（真结局，接完整尾声）、云层小镇（停在小镇）、回母星（直接坐列车）。最后是燃料柜里每件东西的话和可点的东西。",
        "每段标题括号里的英文是场景名，改的时候留着，我靠它对回去。其他都可以改：重写台词、删句、加句、调顺序，都直接改。",
    ]
    base = None
    for x in FINAL_PLAN:
        if isinstance(x, str):
            if base is None and x.startswith("结局"):
                base = set(w.flags)
            if base is not None:
                w.flags = set(base)
            w.goal = ""
            w.lines += ["", "# " + x]
            continue
        if x[0] not in d["scenes"]:
            sys.exit("场景没有了：%s" % x[0])
        w.paragraph(x[0], x[1])
    w.keepsakes()
    w.lines += ["", "# 可点的东西，不在主线"]
    for name, title in FINAL_OPTIONAL:
        w.paragraph(name, title)
    w.lines += ["", "## 站着不动时晨心里想的（hints）" + ("（字直接打在画面上，没有对话框）" if d.get("hints_inner") else "")]
    w.lines += ["- " + l["zh"] for h in d["hints"] for l in h["lines"]]
    w.lines.append("")
    merged = []
    for line in w.lines:                    # 相邻两行动作并成一行
        if merged and line.lstrip().startswith("[") and line.endswith("]") and merged[-1].lstrip().startswith("[") and merged[-1].endswith("]") \
                and not merged[-1].startswith("[玩家走到") \
                and len(line) - len(line.lstrip()) == len(merged[-1]) - len(merged[-1].lstrip()):
            merged[-1] = merged[-1][:-1] + "，" + line.lstrip()[1:]
        else:
            merged.append(line)
    w.lines = merged
    return d, w


def check_final(d, w):
    text = "\n".join(w.lines)
    missing = []

    def go(o):
        if isinstance(o, dict):
            if "zh" in o and str(o["zh"]) and o["zh"] not in text:
                missing.append(o["zh"])
            for k, v in o.items():
                if not k.startswith("_"):
                    go(v)
        elif isinstance(o, list):
            for v in o:
                go(v)

    go(d["scenes"])
    go(d["hints"])
    go(d["objectives"])
    for name in d["scenes"]:
        if name not in w.used and name not in FINAL_SILENT:
            missing.append("场景没写进去：" + name)
    return missing

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--chapter", choices=["river", "final"], default="river")
    a = ap.parse_args()
    out, base = (OUT_FINAL, BASE_FINAL) if a.chapter == "final" else (OUT, BASE)
    if os.path.exists(out) and os.path.exists(base) and not a.force:
        if open(out, encoding="utf-8").read() != open(base, encoding="utf-8").read():
            sys.exit("作者已经改过 %s，没有覆盖（要覆盖加 --force）" % out)
    d, w = build_final() if a.chapter == "final" else build()
    miss = check_final(d, w) if a.chapter == "final" else check(d, w)
    text = "\n".join(w.lines)
    for p in (out, base):
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
    print(out, len(w.lines), "行")
    if miss:
        print("主线里有 %d 句没写进 txt：" % len(miss))
        for m in miss:
            print("  " + m)


if __name__ == "__main__":
    main()
