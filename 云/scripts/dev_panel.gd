extends CanvasLayer
## 开发者面板（F8，只在 debug 构建 / 编辑器里运行时有；导出的正式版 level_forest.gd 不建它）。
## 右边一条半透明的小面板，游戏照常跑；面板不抢晨的移动键：用鼠标点，或者 1~4 / Tab 切换页签（开着面板时 Tab 不开背包）。
## 页签：
##   1 节拍  所有能跳的 flag（剧本里设过的 + 引擎自己设的），点一下 = 重新载入本章再 --beat 到那里（同一套：flags、物品、NPC 位置补齐）
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
## 自测：-- --dev_test   每个开关点两下、每个按钮点一下、传送到每个 marker、点掉 / 加上一个 flag，
##        再从面板挨个跳每个节拍（重新载入本章），跳完关掉面板看晨能不能走；
##        再抽查几个中后段的（SAMPLES）：从本章开头在状态页点它 / 从节拍页跳过去，然后自动玩，能接着设上新 flag（或到章节结尾）
##        = 没被前置卡住；全部过了打印 DEV_TEST_DONE 后退出。

const W := 206.0
const TEST_META := "dev_panel_test_i"
const SAMPLE_META := "dev_panel_test_sample"
## 自测抽查：[页, flag]。flag = 状态页点（从本章开头原地补齐），beat = 节拍页跳
const SAMPLES := {
	"forest": [["flag", "bridge_built"], ["flag", "parts_all"], ["flag", "launched"], ["beat", "bridge_built"], ["beat", "parts_all"]],
	"flight1": [["flag", "flight1_leak_fixed"], ["flag", "flight1_miluo_msg"], ["beat", "flight1_leak_fixed"]],
}
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
	if "--dev_test" in OS.get_cmdline_user_args():
		_self_test.call_deferred()


func toggle() -> void:
	visible = not visible


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
	# 换章（chapter_flow.gd）：跳到飞行一 = 带着现在的状态进驾驶舱（在森林中途跳就用森林起飞时的样子）；回森林 = 新游戏
	if level.chapter == "forest":
		v.add_child(_btn("▶ 跳到飞行一（驾驶舱）", _goto_chapter.bind("flight1")))
	else:
		v.add_child(_btn("▶ 重开飞行一", _goto_chapter.bind(level.chapter)))
		v.add_child(_btn("◀ 回到森林（新游戏）", _goto_chapter.bind("forest")))
	for f in all_flags():
		v.add_child(_btn(_nm("flags", f), _jump_beat.bind(f), f))


func _goto_chapter(ch: String) -> void:
	var cf = level.CHAPTER_GD
	if ch == "forest":
		cf.reset()
	else:
		if level.chapter == "forest" and StoryState.has("launched"):
			Engine.set_meta(cf.CARRY_META, StoryState.to_dict())      # 森林已经起飞了：带着真实的状态过去
		elif level.chapter == "forest" and Engine.has_meta(cf.CARRY_META):
			Engine.remove_meta(cf.CARRY_META)                         # 森林中途：用 SEED（森林起飞时的样子）
		Engine.set_meta(cf.CHAPTER_META, ch)
	Engine.set_meta(level.DEV_OPEN_META, true)
	level.get_tree().reload_current_scene()


func _build_teleport(v: VBoxContainer) -> void:
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
	level.get_tree().reload_current_scene()


func _restart() -> void:
	Engine.set_meta(level.DEV_STAGE_META, "play")
	level.get_tree().reload_current_scene()


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
	var flags := all_flags()
	var i: int = int(Engine.get_meta(TEST_META, -1))
	await _wait(1.5)
	if Engine.has_meta(SAMPLE_META):
		await _check_sample(int(Engine.get_meta(SAMPLE_META)))
		return
	if i >= 0:
		# 刚从面板跳过来：关掉面板；落地可能接着播剧情（比如走到等着的鹿身边），让对话自己往下走，等到能自由走再试
		visible = false
		story.dlg.auto_delay = 0.2
		var waited := 0.0
		var reached: bool = StoryState.has(flags[i])
		while not level.free_play() and waited < 90.0 and not story.ended:
			await _wait(0.25)
			waited += 0.25
			if story.dlg.picking():
				story.dlg.confirm()                       # 点选 / 菜单：替它选当前那个
			elif story.dlg.menu_open():
				story.dlg._menu_choose(story.dlg._menu_sel)
			elif story.cockpit_ui != null:
				story.cockpit_ui.dev_skip()               # 驾驶舱的避碎石 / 选纪念品：替它做完
		story.dlg.auto_delay = -1.0
		if story.ended:
			print("DEV_TEST beat %s: %s  (章节结束卡)" % [flags[i], "ok" if reached else "MISSING"])
			i += 1
			if i >= flags.size():
				Engine.remove_meta(TEST_META)
				_start_sample(0)
				return
			Engine.set_meta(TEST_META, i)
			_jump_beat(flags[i])
			return
		var x0: float = level.chen.position.x
		var ok_state: bool = level.state == level.S.PLAY and level.chen.input_enabled
		var e := InputEventKey.new()
		e.keycode = KEY_LEFT if x0 > float(story.world.walls(x0).y) - 30.0 else KEY_RIGHT
		e.physical_keycode = e.keycode
		e.pressed = true
		Input.parse_input_event(e)
		await _wait(0.6)
		e.pressed = false
		Input.parse_input_event(e)
		var moved: bool = absf(level.chen.position.x - x0) > 4.0
		print("DEV_TEST beat %s: %s  state_ok=%s moved=%s x=%.0f" % [flags[i], "ok" if reached else "MISSING",
			ok_state, moved, level.chen.position.x])
		i += 1
	else:
		# 第一轮：开关、按钮、传送、flag
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
		_toggle_flag("zz_test_flag")              # 点亮的 = 只去掉（没亮的那条路会重新载入，在后面的抽查里测）
		if StoryState.has("zz_test_flag"):
			print("DEV_TEST flag clear FAILED")
		for t in TABS.size():
			_set_tab(t)
			await _wait(0.25)
		print("DEV_TEST buttons ok (toggles %d, markers %d)" % [_toggles.size(), story.world.markers.size()])
		i = 0
	if i >= flags.size():
		Engine.remove_meta(TEST_META)
		_start_sample(0)
		return
	Engine.set_meta(TEST_META, i)
	_jump_beat(flags[i])


## 抽查第 k 个：先重新载入（状态页那种 = 重开本章；节拍页那种 = 跳节拍），载入完 _self_test 接着 _check_sample
func _start_sample(k: int) -> void:
	var list: Array = SAMPLES.get(str(level.chapter), [])
	if k >= list.size():
		if Engine.has_meta(SAMPLE_META):
			Engine.remove_meta(SAMPLE_META)
		print("DEV_TEST_DONE")
		get_tree().quit()
		return
	Engine.set_meta(SAMPLE_META, k)
	if str(list[k][0]) == "beat":
		_jump_beat(str(list[k][1]))
	else:
		_restart()


func _check_sample(k: int) -> void:
	var list: Array = SAMPLES.get(str(level.chapter), [])
	var page := str(list[k][0])
	var f := str(list[k][1])
	var filled := "节拍页：重新载入跳过去"
	if page == "flag":
		await _settle(90.0)                       # 重开本章的开场（森林起身 / 驾驶舱起飞过场）先播完
		var n0: int = StoryState.flag_order.size()
		var items0: int = Inventory.owned.size()
		if StoryState.has(f):
			print("DEV_TEST sample flag %s: 开场就已经设上了（换个靠后的抽查）" % f)
		else:
			_set_tab(2)
			await level.dev_complete(f)           # 状态页点它（不走重新载入的退路：走不到就报 MISSING）
		filled = "状态页原地补齐 flag +%d 物品 %+d" % [StoryState.flag_order.size() - n0, Inventory.owned.size() - items0]
	var reached: bool = StoryState.has(f)
	var obj := str(story.objective().get("zh", ""))
	await _settle(90.0)                           # 跳完接着播的那段（别的章节停在目标后面的）
	# 接着自动玩：能再设上两个新 flag，或者走到章节结尾 = 没被前置卡住
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
	print("DEV_TEST sample %s %s: %s  continue=%s  %s  目标「%s」  接着玩又设上 %d 个%s" % [page, f,
		"ok" if reached else "MISSING", "ok" if cont else "STUCK", filled, obj,
		StoryState.flag_order.size() - n1, "（到章节结尾）" if story.ended else ""])
	_start_sample(k + 1)


# ======================================================================= 每帧
func _input(e: InputEvent) -> void:
	if not visible:
		return
	if e is InputEventKey and e.pressed and not e.echo:
		var k: int = e.keycode
		if k == KEY_TAB:
			_set_tab((_tab + 1) % TABS.size())
			get_viewport().set_input_as_handled()
		elif k >= KEY_1 and k <= KEY_4:
			_set_tab(k - KEY_1)
			get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	# 快走：只把晨这一帧走的距离再加两倍（这个节点在晨后面处理，晨的动画照常 100ms 一帧）
	var chen: Node2D = level.chen
	if fast and not is_nan(_last_x) and chen._vel > 0.0:
		var dx := chen.position.x - _last_x
		if absf(dx) < 20.0:
			chen.position.x = round(chen.position.x + dx * 2.0)
	_last_x = chen.position.x
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
