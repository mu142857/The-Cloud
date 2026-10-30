extends CanvasLayer
## 开发者面板（F8，只在 debug 构建 / 编辑器里运行时有；导出的正式版 level_forest.gd 不建它）。
## 右边一条半透明的小面板，游戏照常跑；面板不抢晨的移动键：用鼠标点，或者 1~4 / Tab 切换页签（开着面板时 Tab 不开背包）。
## 页签：
##   1 节拍  按章（森林 / 飞行一 / 河流篇）列主线大节点，每章 6~10 个（data/dev_names.json 的 beats，按 docs/剧情简版.md 挑）：
##           点一下 = 跳到那一段的开头：重新载入那一章再 --beat 到它前面那个 flag（flags、物品、NPC 位置都补齐），能跨章跳。
##           剧情播着（对话、过场、点选、小游戏）也能跳：面板的 _input 最先拿到点击，旧场景整个扔掉再载入（chapter_flow.hard_reload）。
##           本章现在在哪一段亮黄。最下面「全部节点」折叠着剧本里所有 flag（细碎，调试用）
##   2 传送  所有 markers（按 x 排），点一下晨就到那里；room_* 的点会进屋（前墙淡出），屋外的点会出屋
##   3 状态  正在播的 scene 和第几步、晨的 x、在哪、背包；所有 flag 列成按钮，亮的是已设。
##           点没亮的 = 从现在接着把剧情瞬间过一遍到它（level.dev_complete：前置的 flag、物品、NPC、房间、目标都补齐，
##           不会只设一个 flag 卡在前置上）；从现在走不到（剧情在播 / 走了别的分支）就重新载入本章跳节拍。点亮的 = 只去掉这一个
##   4 开关  快走（晨的移动 ×3，动画帧速不变）、跳过对话（每句 0.15 秒自动推进）、显示 hotspot 范围和 marker 竖线、
##           雾开 / 关、前景层开 / 关、补写台词标蓝（剧本 "added": true 的台词正文用蓝色；debug 构建默认开）；
##           按钮：重开本章、给齐本章所有物品、燃料加满
## 面板上的字统一中文：flag / marker / scene / 房间 / 状态的中文名在 data/dev_names.json（没写的回退显示原 id），
##   原 id 放在按钮的 tooltip 里（鼠标停上去看）；状态页那段文字的 tooltip 是原始 id。背包显示物品的 name.zh。
## 用法也写在 docs/forest_chapter.md 末尾「开发者模式（F8）」。
## 自测：-- --dev_test   每个开关点两下、每个按钮点一下、传送到每个 marker、点掉一个 flag；
##        再挨个跳三章所有大节点，每个跳完自动玩，能走到本章下一个大节点（最后一个 = 章节结尾）= 没被前置卡住；
##        再在对话 / 点选 / 小游戏 / 驾驶舱小游戏进行中真的按 F8、点大节点按钮跳走（INTERRUPTS）；
##        最后抽查状态页（SAMPLES：从本章开头原地补齐到中后段的 flag 再接着玩）。全部过了打印 DEV_TEST_DONE 后退出。

const W := 206.0
const TEST_META := "dev_panel_test"       # 自测进度（跨重新载入）：{ch0, phase, i, stage…}
## 自测抽查状态页：从本章开头原地补齐到这个 flag，再接着自动玩
const SAMPLES := {
	"forest": ["bridge_built", "parts_all", "launched"],
	"flight1": ["flight1_leak_fixed", "flight1_miluo_msg"],
}
## 自测打断：剧情播到这种时候按 F8 点大节点跳走。[什么时候, 从哪段开始 [章, after], 点哪个大节点 [章, after]]
const INTERRUPTS := [
	["对话", ["forest", "fuel_full"], ["forest", "shop_done"]],
	["点选", ["forest", "parts_all"], ["flight1", "flight1_fuel_low"]],
	["小游戏", ["river", ""], ["river", "river_oldstreet"]],
	["驾驶舱小游戏", ["flight1", ""], ["forest", "deer_met"]],
]
const TABS := ["节拍", "传送", "状态", "开关"]
const BG := Color(0.02, 0.05, 0.04, 0.78)
const EDGE := Color(0.5, 0.6, 0.55, 0.35)
const NAMES_PATH := "res://data/dev_names.json"

var level: Node2D
var story: Node
var _root: Panel
var _tab := 0
var _tab_btns: Array[Button] = []
var _pages: Array[Control] = []
var _state_label: Label
var _flag_box: VBoxContainer
var _flag_btns := {}
var _toggles := {}
var _overlay: Node2D
var fast := false
var skip_dialog := false
var show_ranges := false
var _last_x := NAN
var _refresh_t := 0.0
var _saved_auto := -1.0
var _names := {}                 # data/dev_names.json：{flags, markers, scenes, rooms, states} → {id: 中文名}
var _completing := false         # 状态页点的 flag 正在补齐（快进中），别的点先不理
var _beat_btns: Array = []       # 节拍页的大节点：[{b, ch, after}]（亮现在在哪一段）
var _all_box: VBoxContainer      # 节拍页最下面折叠的「全部节点」
var _all_fold: Button
var _cur_head: Label             # 节拍页现在这章的标题（打开时滚到它）


func _ready() -> void:
	layer = 60
	story = level.story
	_load_names()
	_root = Panel.new()
	_root.theme = UITheme.get_theme()
	_root.add_theme_stylebox_override("panel", UITheme.box(BG, EDGE, 1))
	_root.position = Vector2(480 - W - 4, 4)
	_root.size = Vector2(W, 262)
	_root.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_root)
	var tabs := HBoxContainer.new()
	tabs.position = Vector2(4, 3)
	tabs.add_theme_constant_override("separation", 2)
	_root.add_child(tabs)
	for i in TABS.size():
		var b := _btn("%d%s" % [i + 1, TABS[i]], _set_tab.bind(i))
		b.autowrap_mode = TextServer.AUTOWRAP_OFF    # 页签不折行（在 HBox 里折行会缩成一个字宽）
		b.custom_minimum_size = Vector2(0, 16)
		tabs.add_child(b)
		_tab_btns.append(b)
	for i in TABS.size():
		var sc := ScrollContainer.new()
		sc.position = Vector2(4, 23)
		sc.size = Vector2(W - 8, 262 - 27)
		sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		_root.add_child(sc)
		var v := VBoxContainer.new()
		v.add_theme_constant_override("separation", 1)
		v.custom_minimum_size = Vector2(W - 16, 0)
		sc.add_child(v)
		_pages.append(sc)
		match i:
			0:
				_build_beats(v)
			1:
				_build_teleport(v)
			2:
				_build_state(v)
			3:
				_build_switches(v)
	_overlay = Node2D.new()
	_overlay.name = "DevOverlay"
	_overlay.z_index = 50
	_overlay.draw.connect(_draw_overlay)
	level.add_child(_overlay)
	_set_tab(0)
	_scroll_to_chapter.call_deferred()
	if "--dev_test" in OS.get_cmdline_user_args():
		_self_test.call_deferred()


func toggle() -> void:
	visible = not visible


## 节拍页滚到现在这一章（排好版以后才知道位置，等两帧）
func _scroll_to_chapter() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	if _cur_head != null:
		(_pages[0] as ScrollContainer).scroll_vertical = int(_cur_head.position.y)


## 名字表：kind = flags / markers / scenes / rooms / states。scenes 先查「章节:id」（不同章节同名 scene），查不到回退原 id
func _load_names() -> void:
	var f := FileAccess.open(NAMES_PATH, FileAccess.READ)
	if f == null:
		return
	var d = JSON.parse_string(f.get_as_text())
	if d is Dictionary:
		_names = d


func _nm(kind: String, id: String) -> String:
	var t = _names.get(kind, {})
	if not t is Dictionary:
		return id
	if kind == "scenes" and t.has(str(level.chapter) + ":" + id):
		return str(t[str(level.chapter) + ":" + id])
	return str(t.get(id, id))


func _item_name(id: String) -> String:
	var n = Inventory.item(id).get("name", {})
	if n is Dictionary and str(n.get("zh", "")) != "":
		return str(n["zh"])
	return id


func _btn(text: String, cb: Callable, tip := "") -> Button:
	var b := Button.new()
	b.text = text
	b.tooltip_text = tip
	b.focus_mode = Control.FOCUS_NONE          # 不抢键盘（方向键、空格还是给晨）
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY   # 名字长就折成两行，不把整列撑出面板
	b.add_theme_font_size_override("font_size", 14)
	b.add_theme_stylebox_override("normal", UITheme.box(Color(0.08, 0.12, 0.1, 0.6), Color(0, 0, 0, 0), 0, Vector4(3, 0, 3, 0)))
	b.add_theme_stylebox_override("hover", UITheme.box(Color(0.16, 0.24, 0.2, 0.9), Color(0, 0, 0, 0), 0, Vector4(3, 0, 3, 0)))
	b.add_theme_stylebox_override("pressed", UITheme.box(Color(0.3, 0.2, 0.3, 0.9), Color(0, 0, 0, 0), 0, Vector4(3, 0, 3, 0)))
	b.pressed.connect(cb)
	return b


func _set_tab(i: int) -> void:
	_tab = i
	for k in _pages.size():
		_pages[k].visible = k == i
		_tab_btns[k].modulate = Color(1.3, 1.3, 1.3) if k == i else Color(0.75, 0.75, 0.75)


# ======================================================================= 页签
func all_flags() -> Array[String]:
	var out: Array[String] = []
	for f in story.ENGINE_FLAGS:
		if not out.has(str(f)):
			out.append(str(f))
	for id in story.scenes:
		for st in story.scenes[id]:
			if st is Dictionary and str(st.get("do", "")) == "flag" and st.has("set") and not out.has(str(st["set"])):
				out.append(str(st["set"]))
	return out


func _build_beats(v: VBoxContainer) -> void:
	var tip := _label("点 = 跳到这段开头，前面的自动做完；剧情播着也能跳")
	tip.add_theme_color_override("font_color", UITheme.TEXT_DIM)
	tip.add_theme_font_size_override("font_size", 12)
	v.add_child(tip)
	var beats = _names.get("beats", {})
	for ch in level.CHAPTER_GD.CHAPTERS:
		var cn := _chapter_name(str(ch))
		var head := _label("— %s%s —" % [cn, "（现在）" if ch == level.chapter else ""])
		head.add_theme_font_size_override("font_size", 12)
		v.add_child(head)
		if ch == level.chapter:
			_cur_head = head
		var list = beats.get(ch, []) if beats is Dictionary else []
		for bt in list:
			var after := str(bt.get("after", ""))
			var b := _btn("%s·%s" % [cn, str(bt.get("zh", after))], _jump_to.bind(str(ch), after),
				"%s  %s" % [ch, after if after != "" else "（章节开头）"])
			v.add_child(b)
			_beat_btns.append({"b": b, "ch": str(ch), "after": after})
		if ch == "river":
			# 原文 119 摸衣袋：飞行一烧的是蓝色石头还是通勤卡（从别的章直接进河流篇用的 SEED）
			var card := Engine.has_meta(level.CHAPTER_GD.RIVER_SEED_META) and str(Engine.get_meta(level.CHAPTER_GD.RIVER_SEED_META)) == "card"
			v.add_child(_btn("　河流篇按「烧了%s」进（点换成%s）" % ["通勤卡" if card else "蓝色石头", "蓝色石头" if card else "通勤卡"],
				_river_seed.bind("" if card else "card")))
	# 剧本里所有设 flag 的地方（细碎，调试用）：默认收起
	_all_box = VBoxContainer.new()
	_all_box.add_theme_constant_override("separation", 1)
	_all_box.visible = false
	_all_fold = _btn("", _toggle_all)
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 6)
	v.add_child(gap)
	v.add_child(_all_fold)
	v.add_child(_all_box)
	for f in all_flags():
		_all_box.add_child(_btn(_nm("flags", f), _jump_beat.bind(f), f))
	_all_box.visible = true
	_toggle_all()


## 「全部节点」展开 / 收起
func _toggle_all() -> void:
	_all_box.visible = not _all_box.visible
	_all_fold.text = "%s 全部节点（本章 %d 个，调试用）" % ["▾" if _all_box.visible else "▸", _all_box.get_child_count()]


func _label(text: String) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 14)
	l.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	l.custom_minimum_size = Vector2(W - 16, 0)
	return l


func _chapter_name(ch: String) -> String:
	var t = _names.get("chapters", {})
	return str(t.get(ch, ch)) if t is Dictionary else ch


## 节拍页的大节点：after 为空 = 这一章从头开始；别的 = 重新载入那一章再 --beat 到 after（同一套快进补齐）
## 换章：去森林 = 新游戏；去飞行一 / 河流篇 = 带着现在的真实状态（本章已经播完）或者用 SEED（chapter_flow.gd）
func _jump_to(ch: String, after: String) -> void:
	if ch != level.chapter:
		_prep_chapter(ch)
	if after != "":
		Engine.set_meta(level.DEV_BEAT_META, after)
	elif ch == "forest":
		Engine.set_meta(level.DEV_STAGE_META, "play")     # 森林开头：跳过标题，直接坠毁
	Engine.set_meta(level.DEV_OPEN_META, true)
	_reload()


## 重新载入本场景（剧情播到一半也行：正在 await 的步骤、对话框、点选、小游戏都跟着旧场景一起扔掉）
func _reload() -> void:
	level.CHAPTER_GD.hard_reload(level.get_tree())


## 河流篇用哪个 SEED：重新直接进河流篇
func _river_seed(v: String) -> void:
	var cf = level.CHAPTER_GD
	if v == "":
		Engine.remove_meta(cf.RIVER_SEED_META)
	else:
		Engine.set_meta(cf.RIVER_SEED_META, v)
	if Engine.has_meta(cf.CARRY_META):
		Engine.remove_meta(cf.CARRY_META)
	Engine.set_meta(cf.CHAPTER_META, "river")
	Engine.set_meta(cf.PICK_META, true)
	Engine.set_meta(level.DEV_OPEN_META, true)
	_reload()


## 换到 ch 这一章要准备的 meta（不重新载入）
func _prep_chapter(ch: String) -> void:
	var cf = level.CHAPTER_GD
	if ch == "forest":
		cf.reset()
	elif ch == "river" and level.chapter == "forest":
		if Engine.has_meta(cf.CARRY_META):
			Engine.remove_meta(cf.CARRY_META)                     # 从森林直接跳：用 SEED
	elif ch == "river" and level.chapter == "flight1" and StoryState.has("flight1_done"):
		Engine.set_meta(cf.CARRY_META, StoryState.to_dict())      # 飞行一已经降落：带着真实的状态过去
	elif ch == "river" and level.chapter == "flight1":
		Engine.remove_meta(cf.CARRY_META)
	elif level.chapter == "forest" and StoryState.has("launched"):
		Engine.set_meta(cf.CARRY_META, StoryState.to_dict())      # 森林已经起飞了：带着真实的状态过去
	elif Engine.has_meta(cf.CARRY_META):
		Engine.remove_meta(cf.CARRY_META)                         # 森林中途 / 从河流篇回去：用 SEED
	Engine.set_meta(cf.CHAPTER_META, ch)
	Engine.set_meta(cf.PICK_META, true)


func _build_teleport(v: VBoxContainer) -> void:
	if not story.world.stages.is_empty():
		# 多房间章节：按房间分组，组里按 x 排
		var groups := {}
		for n in story.world.markers:
			var r: String = story.world.room_of_marker(str(n))
			if r == "":
				continue
			if not groups.has(r):
				groups[r] = []
			(groups[r] as Array).append(str(n))
		for r in groups:
			var l := Label.new()
			l.text = "— " + _nm("rooms", str(r)) + " —"
			l.add_theme_font_size_override("font_size", 12)
			v.add_child(l)
			var arr: Array = groups[r]
			arr.sort_custom(func(a, b): return float(story.world.markers[a]) < float(story.world.markers[b]))
			for n in arr:
				v.add_child(_btn("%s  %d" % [_nm("markers", str(n)), int(story.world.markers[n])], level.dev_teleport.bind(str(n)), str(n)))
		return
	var names: Array = story.world.markers.keys()
	names.sort_custom(func(a, b):
		var ra := str(a).begins_with("room_")
		var rb := str(b).begins_with("room_")
		if ra != rb:
			return not ra
		return float(story.world.markers[a]) < float(story.world.markers[b]))
	for n in names:
		v.add_child(_btn("%s  %d" % [_nm("markers", str(n)), int(story.world.markers[n])], level.dev_teleport.bind(str(n)), str(n)))


func _build_state(v: VBoxContainer) -> void:
	_state_label = Label.new()
	_state_label.add_theme_font_size_override("font_size", 14)
	_state_label.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	_state_label.custom_minimum_size = Vector2(W - 16, 0)
	_state_label.mouse_filter = Control.MOUSE_FILTER_PASS        # 停上去看原始 id（tooltip）
	v.add_child(_state_label)
	var t := Label.new()
	t.text = "剧情标记：点没亮的 = 补齐前面剧情到它；点亮的 = 只去掉它"
	t.add_theme_color_override("font_color", UITheme.TEXT_DIM)
	t.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	t.custom_minimum_size = Vector2(W - 16, 0)
	v.add_child(t)
	for f in all_flags():
		var b := _btn(_nm("flags", f), _toggle_flag.bind(f), f)
		v.add_child(b)
		_flag_btns[f] = b


func _build_switches(v: VBoxContainer) -> void:
	for k in [["fast", "快走 ×3"], ["skip", "跳过对话"], ["ranges", "显示互动范围 / 传送点"], ["fog", "雾"], ["front", "前景层"],
			["added", "补写台词标蓝"]]:
		var b := _btn("", _switch.bind(str(k[0])))
		b.set_meta("label", str(k[1]))
		v.add_child(b)
		_toggles[str(k[0])] = b
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 6)
	v.add_child(gap)
	v.add_child(_btn("重开本章", _restart))
	v.add_child(_btn("给齐本章所有物品", _give_all))
	v.add_child(_btn("燃料加满", _fuel_full))
	v.add_child(_btn("打开通讯器", func(): story.phone.dev_open()))          # 通讯器（phone_ui.gd）
	v.add_child(_btn("模拟一条消息", func(): story.phone.dev_simulate()))
	_sync_switches()


# ======================================================================= 动作
func _jump_beat(f: String) -> void:
	Engine.set_meta(level.DEV_BEAT_META, f)
	_reload()


func _restart() -> void:
	_jump_to(str(level.chapter), "")


func _toggle_flag(f: String) -> void:
	if StoryState.has(f):
		StoryState.clear_flag(f)              # 去掉只去掉这一个（查分支用）
		return
	if _completing:
		return
	_completing = true
	var ok: bool = await level.dev_complete(f)
	_completing = false
	if not ok and not StoryState.has(f):
		_jump_beat(f)                         # 从现在走不到：重新载入本章，从头跳到它


func _give_all() -> void:
	for id in Inventory._order:
		if not Inventory.has(str(id)):
			Inventory.add(str(id))
	level.on_inventory_changed()


func _fuel_full() -> void:
	for id in Inventory._order:
		var it := Inventory.item(str(id))
		if Inventory.burn_total() >= Inventory.get_launch_burn():
			break
		if not it.get("personal", false) and int(it.get("burn", 0)) > 0 and not Inventory.has(str(id)):
			Inventory.add(str(id))
	level.on_inventory_changed()


func _switch(k: String) -> void:
	match k:
		"fast":
			fast = not fast
		"skip":
			skip_dialog = not skip_dialog
			if skip_dialog:
				_saved_auto = story.dlg.auto_delay
				story.dlg.auto_delay = 0.15
			else:
				story.dlg.auto_delay = _saved_auto
		"ranges":
			show_ranges = not show_ranges
		"fog":
			story.world.fog_enabled = not story.world.fog_enabled
		"front":
			var f: CanvasItem = level.get_node("Front")
			f.visible = not f.visible
		"added":
			story.mark_added = not story.mark_added
	_sync_switches()


func _sync_switches() -> void:
	var on := {"fast": fast, "skip": skip_dialog, "ranges": show_ranges, "fog": story.world.fog_enabled,
		"front": (level.get_node("Front") as CanvasItem).visible, "added": story.mark_added}
	for k in _toggles:
		var b: Button = _toggles[k]
		b.text = ("■ " if on[k] else "□ ") + str(b.get_meta("label"))


# ======================================================================= 自测（--dev_test）
func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


## 剧情在播：对话自己往下走、点选替它选、驾驶舱小玩法替它做完，等到能自由走（最多 limit 秒）
func _settle(limit: float) -> void:
	if not story.busy and level.free_play():
		return
	var was: float = story.dlg.auto_delay
	story.dlg.auto_delay = 0.2
	var waited := 0.0
	while (story.busy or not level.free_play()) and waited < limit and not story.ended:
		await _wait(0.25)
		waited += 0.25
		if story.dlg.picking():
			story.dlg.confirm()
		elif story.dlg.menu_open():
			story.dlg._menu_choose(story.dlg._menu_sel)
		elif story.cockpit_ui != null:
			story.cockpit_ui.dev_skip()
	story.dlg.auto_delay = was


func _self_test() -> void:
	await _wait(1.5)
	var d: Dictionary = Engine.get_meta(TEST_META) if Engine.has_meta(TEST_META) else {}
	if d.is_empty():
		await _test_buttons()
		_test_go({"ch0": str(level.chapter), "phase": "beat", "i": 0})
		return
	match str(d["phase"]):
		"beat":
			await _test_beat(d)
		"int":
			await _test_interrupt(d)
		"sample":
			await _check_sample(d)


## 第一轮：开关、按钮、传送、flag、折叠的「全部节点」
func _test_buttons() -> void:
	for k in _toggles:
		_switch(str(k))
		await _wait(0.1)
		_switch(str(k))
	_give_all()
	_fuel_full()
	# 通讯器剧情播放中不开（open_browse 的规矩）：flight1 一进来就在播起飞过场，先让它自己播到能自由走再试
	await _settle(90.0)
	story.phone.dev_open()
	await _wait(0.3)
	var phone_ok: bool = story.phone.is_open()
	story.phone.close()
	level._close_panels()
	print("DEV_TEST phone open=%s" % phone_ok)
	for n in story.world.markers:
		level.dev_teleport(str(n))
		await _wait(0.05)
	level.dev_teleport("chen_start")
	StoryState.set_flag("zz_test_flag")
	_toggle_flag("zz_test_flag")              # 点亮的 = 只去掉（没亮的那条路在后面的抽查里测）
	if StoryState.has("zz_test_flag"):
		print("DEV_TEST flag clear FAILED")
	for t in TABS.size():
		_set_tab(t)
		await _wait(0.25)
	_set_tab(0)
	_toggle_all()
	var fold_ok := _all_box.visible
	_toggle_all()
	if not fold_ok or _all_box.visible:
		print("DEV_TEST 全部节点折叠 FAILED")
	print("DEV_TEST buttons ok (toggles %d, markers %d, 大节点 %d)" % [_toggles.size(), story.world.markers.size(), _all_beats().size()])


## 所有大节点按章排成一列：[{ch, after, zh}]
func _all_beats() -> Array:
	var out: Array = []
	var beats = _names.get("beats", {})
	for ch in level.CHAPTER_GD.CHAPTERS:
		for bt in (beats.get(ch, []) if beats is Dictionary else []):
			out.append({"ch": str(ch), "after": str(bt.get("after", "")), "zh": "%s · %s" % [_chapter_name(str(ch)), str(bt.get("zh", ""))]})
	return out


## 存好进度，做下一步要的跳转（重新载入以后 _self_test 接着做）
func _test_go(d: Dictionary) -> void:
	var beats := _all_beats()
	if d["phase"] == "beat" and int(d["i"]) >= beats.size():
		d = {"ch0": d["ch0"], "phase": "int", "i": 0, "stage": "from"}
	if d["phase"] == "int" and int(d["i"]) >= INTERRUPTS.size():
		d = {"ch0": d["ch0"], "phase": "sample", "i": 0}
	if d["phase"] == "sample" and int(d["i"]) >= (SAMPLES.get(str(d["ch0"]), []) as Array).size():
		Engine.remove_meta(TEST_META)
		print("DEV_TEST_DONE")
		get_tree().quit()
		return
	Engine.set_meta(TEST_META, d)
	match str(d["phase"]):
		"beat":
			_jump_to(beats[int(d["i"])]["ch"], beats[int(d["i"])]["after"])
		"int":
			var fr: Array = INTERRUPTS[int(d["i"])][1]
			_jump_to(str(fr[0]), str(fr[1]))
		"sample":
			_jump_to(str(d["ch0"]), "")


## 跳到第 i 个大节点以后：到没到；再接着自动玩，能走到本章下一个大节点（本章最后一个 = 走到章节结尾）= 没被前置卡住
func _test_beat(d: Dictionary) -> void:
	var beats := _all_beats()
	var i := int(d["i"])
	var b: Dictionary = beats[i]
	visible = false
	var reached: bool = level.chapter == b["ch"] and (b["after"] == "" or StoryState.has(b["after"]))
	var nxt := ""
	if i + 1 < beats.size() and beats[i + 1]["ch"] == b["ch"]:
		nxt = beats[i + 1]["after"]
	var n0: int = StoryState.flag_order.size()
	var cont := await _play_until(nxt, 400.0)
	print("DEV_TEST beat %s（%s）: %s  接着玩到「%s」: %s  又设上 %d 个 flag" % [b["zh"], b["after"] if b["after"] != "" else "开头",
		"ok" if reached else "MISSING", _nm("flags", nxt) if nxt != "" else "章节结尾", "ok" if cont else "STUCK",
		StoryState.flag_order.size() - n0])
	d["i"] = i + 1
	_test_go(d)


## 自动玩到 flag 设上（flag 为空 = 到章节结尾），最多 limit 秒
func _play_until(flag: String, limit: float) -> bool:
	var waited := 0.0
	story.auto = "main"
	while waited < limit and not story.ended and not (flag != "" and StoryState.has(flag)):
		await _wait(0.25)
		waited += 0.25
		if story.cockpit_ui != null:
			story.cockpit_ui.dev_skip()
	story.auto = ""
	story.dlg.auto_delay = -1.0
	return StoryState.has(flag) if flag != "" else story.ended


func _in_state(kind: String) -> bool:
	match kind:
		"对话":
			return story.busy and story.dlg.is_open() and not story.dlg.picking() and not story.dlg.menu_open()
		"点选":
			return story.dlg.picking() or story.dlg.menu_open()
		"小游戏":
			return story.mech_wait or story.mech_running != ""
		"驾驶舱小游戏":
			return story.cockpit_ui != null
	return false


## 剧情播到 INTERRUPTS 那种时候：真的按 F8、真的点节拍页的按钮（从 viewport 进输入，和作者手点一样），看能不能干净地跳走
func _test_interrupt(d: Dictionary) -> void:
	var it: Array = INTERRUPTS[int(d["i"])]
	if d["stage"] == "from":
		visible = false
		story.auto = "main"
		var waited := 0.0
		while not _in_state(str(it[0])) and waited < 300.0 and not story.ended:
			await get_tree().process_frame
			waited += get_process_delta_time()
			if story.cockpit_ui != null and str(it[0]) != "驾驶舱小游戏":
				story.cockpit_ui.dev_skip()
		d["hit"] = _in_state(str(it[0]))
		d["scene"] = str(story._cur_scene) if story.busy else "-"
		_push(_key(KEY_F8, true))
		_push(_key(KEY_F8, false))
		await get_tree().process_frame
		d["open"] = visible
		d["stage"] = "to"
		Engine.set_meta(TEST_META, d)
		_set_tab(0)
		var b: Button = null
		for bb in _beat_btns:
			if bb["ch"] == str(it[2][0]) and bb["after"] == str(it[2][1]):
				b = bb["b"]
		(_pages[0] as ScrollContainer).ensure_control_visible(b)
		await get_tree().process_frame
		await get_tree().process_frame
		var c := b.get_global_rect().get_center()
		_push(_click(c, true))
		_push(_click(c, false))
		await _wait(1.0)
		print("DEV_TEST interrupt %s: 点了按钮没跳 FAILED" % it[0])     # 跳了的话这个节点已经没了，走不到这里
		d["i"] = int(d["i"]) + 1
		d["stage"] = "from"
		_test_go(d)
		return
	visible = false
	var to: Array = it[2]
	var reached: bool = level.chapter == str(to[0]) and (str(to[1]) == "" or StoryState.has(str(to[1])))
	var n0: int = StoryState.flag_order.size()
	var waited := 0.0
	story.auto = "main"
	while StoryState.flag_order.size() < n0 + 1 and not story.ended and waited < 200.0:
		await _wait(0.25)
		waited += 0.25
		if story.cockpit_ui != null:
			story.cockpit_ui.dev_skip()
	story.auto = ""
	print("DEV_TEST interrupt %s（%s scene=%s，F8 开面板=%s）→ %s · %s: %s  接着玩: %s" % [it[0],
		"打断时正在" if d["hit"] else "没等到这种时候 NOT_HIT", d["scene"], d["open"], _chapter_name(str(to[0])),
		_nm("flags", str(to[1])), "ok" if reached else "MISSING", "ok" if story.ended or StoryState.flag_order.size() > n0 else "STUCK"])
	d["i"] = int(d["i"]) + 1
	d["stage"] = "from"
	_test_go(d)


func _push(e: InputEvent) -> void:
	get_viewport().push_input(e, true)


func _key(k: Key, down: bool) -> InputEventKey:
	var e := InputEventKey.new()
	e.keycode = k
	e.physical_keycode = k
	e.pressed = down
	return e


func _click(p: Vector2, down: bool) -> InputEventMouseButton:
	var e := InputEventMouseButton.new()
	e.button_index = MOUSE_BUTTON_LEFT
	e.position = p
	e.global_position = p
	e.pressed = down
	return e


## 状态页抽查：从本章开头点一个中后段的 flag（原地补齐，不走重新载入），再接着自动玩能设上新 flag（或到章节结尾）
func _check_sample(d: Dictionary) -> void:
	var f := str(SAMPLES[str(d["ch0"])][int(d["i"])])
	await _settle(90.0)                       # 重开本章的开场（森林起身 / 驾驶舱起飞过场）先播完
	var n0: int = StoryState.flag_order.size()
	var items0: int = Inventory.owned.size()
	if StoryState.has(f):
		print("DEV_TEST sample flag %s: 开场就已经设上了（换个靠后的抽查）" % f)
	else:
		_set_tab(2)
		await level.dev_complete(f)
	var filled := "flag +%d 物品 %+d" % [StoryState.flag_order.size() - n0, Inventory.owned.size() - items0]
	var reached: bool = StoryState.has(f)
	await _settle(90.0)                       # 跳完接着播的那段（别的章节停在目标后面的）
	var n1: int = StoryState.flag_order.size()
	var waited := 0.0
	if not story.ended:
		story.auto = "main"
		while StoryState.flag_order.size() < n1 + 2 and not story.ended and waited < 120.0:
			await _wait(0.25)
			waited += 0.25
			if story.cockpit_ui != null:
				story.cockpit_ui.dev_skip()
		story.auto = ""
		story.dlg.auto_delay = -1.0
	var cont: bool = story.ended or StoryState.flag_order.size() >= n1 + 2
	print("DEV_TEST sample flag %s: %s  continue=%s  状态页原地补齐 %s  接着玩又设上 %d 个%s" % [f,
		"ok" if reached else "MISSING", "ok" if cont else "STUCK", filled,
		StoryState.flag_order.size() - n1, "（到章节结尾）" if story.ended else ""])
	d["i"] = int(d["i"]) + 1
	_test_go(d)


# ======================================================================= 每帧
## 面板自己先接输入（它总排在关卡子节点的最后，_input 倒着叫，它最先拿到）：
## F8 开关面板；面板上的鼠标点击 / 滚轮在这里自己处理掉。不这样的话剧情播着的时候对话框、点选、小游戏的 _input
## 会先把点击吃了，按钮收不到（「剧情的时候不能跳」）
func _input(e: InputEvent) -> void:
	if e is InputEventKey and e.pressed and not e.echo and e.keycode == KEY_F8:
		get_viewport().set_input_as_handled()
		toggle()
		return
	if not visible:
		return
	if e is InputEventMouseButton:
		var mb := e as InputEventMouseButton
		if not _root.get_global_rect().has_point(mb.position):
			return
		get_viewport().set_input_as_handled()       # 先标掉：按钮可能马上重新载入场景，之后就没有 viewport 了
		if not mb.pressed:
			return
		if mb.button_index == MOUSE_BUTTON_LEFT:
			var b := _hit(mb.position)
			if b != null and not b.disabled:
				b.pressed.emit()
		elif mb.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			var sc := _pages[_tab] as ScrollContainer
			sc.scroll_vertical += 24 * (-1 if mb.button_index == MOUSE_BUTTON_WHEEL_UP else 1)
		return
	if e is InputEventKey and e.pressed and not e.echo:
		var k: int = e.keycode
		if k == KEY_TAB:
			_set_tab((_tab + 1) % TABS.size())
			get_viewport().set_input_as_handled()
		elif k >= KEY_1 and k <= KEY_4:
			_set_tab(k - KEY_1)
			get_viewport().set_input_as_handled()


## 鼠标下面是哪个按钮（页面里的要在滚动框露出来的那部分里）
func _hit(p: Vector2) -> Button:
	for n in _root.find_children("*", "Button", true, false):
		var b := n as Button
		if not b.is_visible_in_tree() or not b.get_global_rect().has_point(p):
			continue
		var sc := b.get_parent()
		while sc != null and not sc is ScrollContainer and sc != _root:
			sc = sc.get_parent()
		if sc is ScrollContainer and not (sc as Control).get_global_rect().has_point(p):
			continue
		return b
	return null


func _process(delta: float) -> void:
	# 快走：只把晨这一帧走的距离再加两倍（这个节点在晨后面处理，晨的动画照常 100ms 一帧）
	var chen: Node2D = level.chen
	if fast and not is_nan(_last_x) and chen._vel > 0.0:
		var dx := chen.position.x - _last_x
		if absf(dx) < 20.0:
			chen.position.x = round(chen.position.x + dx * 2.0)
	_last_x = chen.position.x
	if get_index() < level.get_child_count() - 1:
		level.move_child.call_deferred(self, -1)     # 剧情后来加到关卡上的节点（小游戏等）排到面板后面，面板的 _input 还是最先
	if skip_dialog and story.dlg.auto_delay != 0.15:
		story.dlg.auto_delay = 0.15
	_overlay.visible = show_ranges
	if show_ranges:
		_overlay.queue_redraw()
	if not visible:
		return
	_refresh_t -= delta
	if _refresh_t > 0.0:
		return
	_refresh_t = 0.2
	var scene: String = story._cur_scene if story.busy else ""
	var st: String = level.S.keys()[level.state]
	var room := str(story.world.room)
	var bag: Array[String] = []
	for id in Inventory.owned:
		bag.append(_item_name(str(id)))
	_state_label.text = "场景: %s  步: %d\n位置 x: %d  房间: %s\n状态: %s%s\n背包: %s" % [
		_nm("scenes", scene) if scene != "" else "—", story.step_i, int(chen.position.x), _nm("rooms", room),
		_nm("states", st), "（带路中）" if story.free_walk else "", "、".join(bag) if not bag.is_empty() else "空"]
	_state_label.tooltip_text = "scene=%s  room=%s  state=%s\nitems=%s" % [scene if scene != "" else "-", room, st,
		", ".join(Inventory.owned)]
	for f in _flag_btns:
		(_flag_btns[f] as Button).modulate = Color(1.35, 1.3, 1.0) if StoryState.has(f) else Color(0.6, 0.6, 0.6)
	# 节拍页：本章现在在哪一段亮黄，做完的几段暗一点
	var cur := -1
	for k in _beat_btns.size():
		var d: Dictionary = _beat_btns[k]
		if d["ch"] == level.chapter and (d["after"] == "" or StoryState.has(d["after"])):
			cur = k
	for k in _beat_btns.size():
		var d: Dictionary = _beat_btns[k]
		var done: bool = d["ch"] == level.chapter and k < cur
		(d["b"] as Button).modulate = Color(1.4, 1.3, 0.8) if k == cur else (Color(0.65, 0.65, 0.65) if done else Color.WHITE)
	_sync_switches()


## 显示范围：marker 竖线（屋里的点淡一点）+ 每个能用的 hotspot 的互动范围
func _draw_overlay() -> void:
	var f := UITheme.font()
	var w = story.world
	for n in w.markers:
		var x := float(w.markers[n])
		var room := str(n).begins_with("room_")
		var c := Color(0.9, 0.75, 0.4, 0.5) if not room else Color(0.6, 0.8, 0.9, 0.45)
		_overlay.draw_line(Vector2(x, 60), Vector2(x, 232), c, 1.0)
		_overlay.draw_string(f, Vector2(x + 2, 70 + (12 if room else 0)), _nm("markers", str(n)), HORIZONTAL_ALIGNMENT_LEFT, -1, 14, c)
	for p in story.hotspots.available():
		var h: Dictionary = p["h"]
		var r: float = story.hotspots.range_of(h)
		var x := float(p["x"])
		var gy: float = w.ground_at(x)
		var col := Color(0.4, 1.0, 0.6, 0.25) if not story.hotspots.is_enter(h) else Color(1.0, 0.5, 0.4, 0.3)
		_overlay.draw_rect(Rect2(x - r, gy - 4, r * 2.0, 6), col)
		_overlay.draw_rect(p["rect"], Color(col, 0.6), false, 1.0)
	var wl: Vector2 = w.walls(level.chen.position.x)
	for x in [wl.x, wl.y]:
		_overlay.draw_line(Vector2(x, 40), Vector2(x, 240), Color(1, 0.3, 0.3, 0.6), 1.0)
