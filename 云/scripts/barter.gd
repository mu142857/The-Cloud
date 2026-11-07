extends RefCounted
## 以物易物（10-31 作者：NPC 之间可以换东西，用来达成成就、影响之后的剧情）。所有会换东西的 NPC 共用这一套；
## 不是商店界面：聊着聊着晨把背包里的东西递过去，对方看一眼，换给晨一样东西。story_runner.gd 建一个（barter），在几个地方调它。
##
## 剧本顶层 "barter"（每个 NPC 一份，id = 说话人 / 角色名）：
##   "barter": {"toucan": {
##       "trades": [{"id": "shiny", "want": "mat_scrap", "get": "toucan_feather", "scene": "toucan_take_scrap",
##                   "need": [], "not": [], "flags": [], "then": "", "keep": false}, …],
##       "react": {"elephant_drawing": "toucan_no_drawing"},   // 递了它不换、但有话说的东西（可选）
##       "wrong": "toucan_wrong",   // 递了它不要的东西：说完这段，东西留在晨手里
##       "none": "toucan_none",     // 选了「算了」（可选）
##       "done": "toucan_done"}}    // 能换的都换完了：barter 步骤直接跳到这段（可选，空 = 接着往下播）
## 剧本步骤 {"do": "barter", "npc": "toucan"}：一般放在 NPC 聊天那段的最后（先让 NPC 自己说想要什么、能给什么）。
##   弹背包的道具选择条（和 hotspot 的 accepts 同一个，最后一格「算了」）→ 选中的是某一笔 trade 的 want：
##   先当台词播 trade.scene（不跳走，播完回来），再交出 want（take）、拿到 get（give，飞进背包），
##   设 flag：barter_<npc>_<trade id>（这一笔）、barter_<npc>（和它换过）、barter_any（换过任何一次），再加 trade.flags；
##   最后跳到 trade.then（空 = 接着往下播）。一笔只能换一次；need / not 跟 hotspot 一样看 flag（比如第二笔要先换过第一笔）。
##   keep: true = 只是给对方看 / 听一下，东西还留在晨手里（大嘴鸟听一遍音乐盒，回一只鸟哨）。
##   want: "*" = 什么都收（11-06 市集修补摊换密封圈）：选择条里只摆能给的，任务物品（category quest）和 except 里的不摆，免得主线缺东西。
##     一件能给的都没有：不收东西白送，播 trade.empty（不让玩家卡在没东西可换上）。
##   mark: "fried" + repeat: true + all: true（11-07 料理鼠妈什么都能下锅）：任何东西都收（任务物品也收），不拿走、不给新的，
##     只给这件设 flag fried_<id>（Inventory.item 看到它，名字前面加「油炸的」、描述加一句；id / 功能都不变）；可以一直换。
##     scene 里的台词可以写 {item}（下锅前的名字）、{fried}（炸好以后的名字）。这种不设 barter_<npc> / barter_any（不算成就里的交换）。
##   auto_if: flag = 这个 flag 有了以后，自动玩 / 跳节拍不选「算了」，这一笔真的换（主线等着要的东西：修飞机缺密封圈）。
## 成就 / 蝴蝶效应：别的剧本只看上面这些 flag（docs/以物易物交换表.md）。flag 跟着 StoryState 存档、换章带过去。
##   成就表在 data/achievements.json（all / any 看 flag）；没有单独界面，终章「全剧终」卡下面 show_achievements 列出拿到的几个。
## 自动玩 / 跳节拍：选「算了」（交换都是可去可不去的，不动背包，主线照常），除了写了 auto_if 的那笔。
##   测交换：自动玩加 --barter_take，递第一笔背包里有的 want（只为了 headless 跑一遍 take / give）；
##   --barter_seed=flag,+物品,-物品：直接进后面章节时假装前面换过（测飞行一、终章的分支）。

const ACH_PATH := "res://data/achievements.json"

var r: Node                           # story_runner.gd


func _init(runner: Node) -> void:
	r = runner
	_test_seed()


## 测试：--barter_seed=barter_toucan_rain,+rain_glass,-blue_stone,!c1_mom（直接进后面章节时假装前面换过；+ / - = 背包加 / 减一件，! = 清掉 flag，其余是 flag）
func _test_seed() -> void:
	for a in OS.get_cmdline_user_args():
		if not a.begins_with("--barter_seed="):
			continue
		for s in a.trim_prefix("--barter_seed=").split(",", false):
			if s.begins_with("+"):
				Inventory.add(s.substr(1))
			elif s.begins_with("-"):
				Inventory.remove(s.substr(1))
			elif s.begins_with("!"):
				StoryState.clear_flag(s.substr(1))      # 11-04 夜测：!c1_mom = 换成鹿叫孩子那版
			else:
				StoryState.set_flag(s)


func defs() -> Dictionary:
	var d = r.data.get("barter", {})
	return d if d is Dictionary else {}


static func trade_flag(who: String, t: Dictionary) -> String:
	return "barter_%s_%s" % [who, str(t.get("id", ""))]


## 现在还能换的几笔（没换过、need / not 满足）
func open_trades(who: String) -> Array:
	var out: Array = []
	var d: Dictionary = defs().get(who, {})
	for t in d.get("trades", []):
		if not t is Dictionary or (StoryState.has(trade_flag(who, t)) and not t.get("repeat", false)):
			continue
		var ok := true
		for f in t.get("need", []):
			ok = ok and StoryState.has(str(f))
		for f in t.get("not", []):
			ok = ok and not StoryState.has(str(f))
		if ok:
			out.append(t)
	return out


func run(st: Dictionary) -> String:
	var who := str(st.get("npc", ""))
	var d: Dictionary = defs().get(who, {})
	if d.is_empty():
		r._warn_once("barter：剧本的 barter 里没有 " + who)
		return ""
	var open := open_trades(who)
	if open.is_empty():
		return str(d.get("done", ""))
	var items: Array = r._bag_items()
	for t in open:
		if str(t.get("want", "")) == "*":
			items = items.filter(func(x): return can_give(t, str(x["id"])))
			if items.is_empty() and t.has("empty"):
				return await _trade(who, t, "")
	var ai := items.size() if r.auto != "" or r.ff else -1      # 自动玩 / 跳节拍：「算了」
	if ai > 0 and not auto_trade(who).is_empty():
		ai = 0
	if r.auto != "" and "--barter_take" in OS.get_cmdline_user_args():
		for i in items.size():                                   # 测交换那条路：自动玩递第一件某笔要的东西
			for t in open:
				if ai == items.size() and str(t.get("want", "")) in [str(items[i]["id"]), "*"]:
					ai = i
	r._ui_shot("items", 0.35)
	var it: String = await r.dlg.choose_item(items, I18n.t("barter_none"), ai)
	if it == "":
		return await _inline(str(d.get("none", "")))
	for t in open:
		if str(t.get("want", "")) in [it, "*"]:
			return await _trade(who, t, it)
	var react: Dictionary = d.get("react", {})
	return await _inline(str(react.get(it, d.get("wrong", ""))))


## 主线正等着的那一笔（auto_if 的 flag 有了、还没换）：自动玩要特意去换。没有 = {}
func auto_trade(who: String) -> Dictionary:
	for t in open_trades(who):
		if str(t.get("auto_if", "")) != "" and StoryState.has(str(t["auto_if"])):
			return t
	return {}


## want: "*" 的这一笔收不收这件：任务物品、except 里的不收
func can_give(t: Dictionary, id: String) -> bool:
	if t.get("all", false):
		return true
	return str(Inventory.item(id).get("category", "")) != "quest" and not (t.get("except", []) as Array).has(id)


## 成交：播台词，交出 it（"" = 白送，播 empty），拿到 get，记 flag
func _trade(who: String, t: Dictionary, it: String) -> String:
	var mark := str(t.get("mark", "")) if it != "" else ""
	var sub := {}
	if mark != "":
		r._show_item({"item": it})
		sub["{item}"] = r.txt(Inventory.item(it).get("name", it))
		StoryState.set_flag(mark + "_" + it)
		sub["{fried}"] = r.txt(Inventory.item(it).get("name", it))
	var g := await _inline(str(t.get("scene" if it != "" else "empty", "")), sub)
	if g != "" or r.ended:
		return g
	var n0: int = Inventory.owned.count(it)
	var keep := bool(t.get("keep", false)) or it == "" or mark != ""
	if not keep:
		r._take(it)
	var got := str(t.get("get", ""))
	if got != "":
		await r._give(got)
	StoryState.set_flag(trade_flag(who, t))
	if mark != "":
		if not r.ff:
			r.dlg.toast(Inventory.icon(it), I18n.t("got_item") % sub["{fried}"])
	else:
		StoryState.set_flag("barter_" + who)
		StoryState.set_flag("barter_any")
	for f in t.get("flags", []):
		StoryState.set_flag(str(f))
	if r.auto != "":
		var ok: bool = (keep or Inventory.owned.count(it) == n0 - 1) and (got == "" or Inventory.has(got))
		if mark != "":
			ok = ok and Inventory.owned.count(it) == n0 and Inventory.defined(it) and str(Inventory.item(it).get("id", "")) == it
		print("%s %s.%s gave=%s count=%d->%d got=%s%s" % ["QA_BARTER" if ok else "QA_BARTER_FAIL", who, t.get("id"), it, n0, Inventory.owned.count(it), got,
			(" name=" + sub["{fried}"]) if mark != "" else ""])
	return str(t.get("then", ""))


## 当台词播一段 scene（和 if 落空的分支一样：播完回来，接着播 barter 后面的步骤；里面 goto 了就跟着跳）
## sub：台词里的 {item} / {fried} 换成物品名（mark 那种交换）
func _inline(scene: String, sub := {}) -> String:
	if scene == "" or not r.scenes.has(scene):
		return ""
	var outer: String = r._cur_scene
	r._on_scene(scene)
	for st2 in r.scenes[scene]:
		if not st2 is Dictionary:
			continue
		if not sub.is_empty():
			st2 = (st2 as Dictionary).duplicate()
			for k in st2:
				if st2[k] is String:
					for key in sub:
						st2[k] = str(st2[k]).replace(key, sub[key])
		var g: String = await r._step(st2)
		if r.ended or g != "":
			return g
	r._cur_scene = outer
	return ""


# ======================================================================= 成就
## 拿到的成就（当前语言的名字，按表里的顺序）
static func achievements_got() -> Array[String]:
	var out: Array[String] = []
	if not FileAccess.file_exists(ACH_PATH):
		return out
	var d = JSON.parse_string(FileAccess.get_file_as_string(ACH_PATH))
	if not d is Dictionary:
		return out
	for a in d.get("achievements", []):
		if not a is Dictionary:
			continue
		var ok := true
		for f in a.get("all", []):
			ok = ok and StoryState.has(str(f))
		var any_of: Array = a.get("any", [])
		if not any_of.is_empty():
			var hit := false
			for f in any_of:
				hit = hit or StoryState.has(str(f))
			ok = ok and hit
		if ok:
			out.append(I18n.pick(a))
	return out


## 「全剧终」卡下面：小字「成就」和拿到的名字（一个都没有就什么都不加），比卡晚一点淡进来
func show_achievements(parent: Node) -> void:
	var got := achievements_got()
	if got.is_empty():
		return
	var c := Control.new()
	c.set_anchors_preset(Control.PRESET_FULL_RECT)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	c.theme = UITheme.get_theme()
	c.modulate.a = 0.0
	for i in 2:
		var l := Label.new()
		l.text = I18n.t("achievements_title") if i == 0 else "　".join(got)
		l.add_theme_font_size_override("font_size", 14)
		l.add_theme_color_override("font_color", Color("#4f6359") if i == 0 else Color("#8fa79a"))
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.size = Vector2(440, 16 if i == 0 else 34)
		l.position = Vector2(20, 180 if i == 0 else 198)
		c.add_child(l)
	parent.add_child(c)
	var tw := c.create_tween()
	tw.tween_interval(2.0)
	tw.tween_property(c, "modulate:a", 1.0, 1.5).set_trans(Tween.TRANS_SINE)


# ======================================================================= --story_check
## barter 会设的 flag（hotspot 的 need / not 可以用）
func flags() -> Array:
	var out: Array = ["barter_any"]
	var all := defs()
	for who in all:
		out.append("barter_" + str(who))
		for t in (all[who] as Dictionary).get("trades", []):
			if t is Dictionary:
				out.append(trade_flag(str(who), t))
				out.append_array(t.get("flags", []))
	return out


## 一个 barter 步骤：npc 在表里、每笔的物品在物品表里、引用的 scene 都在（顺便记进 refs，不报「播不到」）
func validate(id: String, st: Dictionary, refs: Dictionary) -> Array[String]:
	var out: Array[String] = []
	var who := str(st.get("npc", ""))
	var d = defs().get(who, null)
	if not d is Dictionary:
		out.append("scene %s：barter 的 npc %s 不在剧本的 barter 表里" % [id, who])
		return out
	var ids := {}
	for t in d.get("trades", []):
		if not t is Dictionary or str(t.get("id", "")) == "" or str(t.get("want", "")) == "":
			out.append("barter %s：每一笔要有 id 和 want：%s" % [who, str(t)])
			continue
		if ids.has(str(t["id"])):
			out.append("barter %s：交换 id 重复 %s" % [who, t["id"]])
		ids[str(t["id"])] = true
		for iid2 in t.get("except", []):
			if not Inventory.defined(str(iid2)):
				out.append("barter %s.%s：except 的物品 %s 不在物品表" % [who, t["id"], iid2])
		for k in ["want", "get"]:
			var iid := str(t.get(k, ""))
			if iid != "" and iid != "*" and not Inventory.defined(iid):
				out.append("barter %s.%s：%s 的物品 %s 不在物品表" % [who, t["id"], k, iid])
		for k in ["scene", "then", "empty"]:
			_ref(out, refs, "%s.%s" % [who, t["id"]], str(t.get(k, "")))
	for k in ["wrong", "none", "done"]:
		_ref(out, refs, who, str(d.get(k, "")))
	var react = d.get("react", {})
	for k in (react as Dictionary if react is Dictionary else {}):
		if not Inventory.defined(str(k)):
			out.append("barter %s：react 的物品 %s 不在物品表" % [who, k])
		_ref(out, refs, who, str(react[k]))
	return out


func _ref(out: Array[String], refs: Dictionary, where: String, s: String) -> void:
	if s == "":
		return
	refs[s] = true
	if not r.scenes.has(s):
		out.append("barter %s：scene %s 不存在" % [where, s])
