extends CanvasLayer
## 开发者面板（F8，只在 debug 构建 / 编辑器里运行时有；导出的正式版 level_forest.gd 不建它）。
## 右边一条半透明的小面板，游戏照常跑；面板不抢晨的移动键：用鼠标点，或者 1~4 / Tab 切换页签（开着面板时 Tab 不开背包）。
## 页签：
##   1 节拍  所有能跳的 flag（剧本里设过的 + 引擎自己设的），点一下 = 重新载入本章再 --beat 到那里（同一套：flags、物品、NPC 位置补齐）
##   2 传送  所有 markers（按 x 排），点一下晨就到那里；room_* 的点会进屋（前墙淡出），屋外的点会出屋
##   3 状态  正在播的 scene 和第几步、晨的 x、在哪、背包；所有 flag 列成按钮，亮的是已设，点一下设上 / 去掉
##   4 开关  快走（晨的移动 ×3，动画帧速不变）、跳过对话（每句 0.15 秒自动推进）、显示 hotspot 范围和 marker 竖线、
##           雾开 / 关、前景层开 / 关；按钮：重开本章、给齐本章所有物品、燃料加满
## 用法也写在 docs/forest_chapter.md 末尾「开发者模式（F8）」。
## 自测：-- --dev_test   每个开关点两下、每个按钮点一下、传送到每个 marker、点掉 / 加上一个 flag，
##        再从面板挨个跳每个节拍（重新载入本章），跳完关掉面板看晨能不能走；全部过了打印 DEV_TEST_DONE 后退出。

const W := 206.0
const TEST_META := "dev_panel_test_i"
const TABS := ["节拍", "传送", "状态", "开关"]
const BG := Color(0.02, 0.05, 0.04, 0.78)
const EDGE := Color(0.5, 0.6, 0.55, 0.35)

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


func _ready() -> void:
	layer = 60
	story = level.story
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


func _btn(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE          # 不抢键盘（方向键、空格还是给晨）
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
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
	for f in all_flags():
		v.add_child(_btn(f, _jump_beat.bind(f)))


func _build_teleport(v: VBoxContainer) -> void:
	var names: Array = story.world.markers.keys()
	names.sort_custom(func(a, b):
		var ra := str(a).begins_with("room_")
		var rb := str(b).begins_with("room_")
		if ra != rb:
			return not ra
		return float(story.world.markers[a]) < float(story.world.markers[b]))
	for n in names:
		v.add_child(_btn("%s  %d" % [n, int(story.world.markers[n])], level.dev_teleport.bind(str(n))))


func _build_state(v: VBoxContainer) -> void:
	_state_label = Label.new()
	_state_label.add_theme_font_size_override("font_size", 14)
	_state_label.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	_state_label.custom_minimum_size = Vector2(W - 16, 0)
	v.add_child(_state_label)
	var t := Label.new()
	t.text = "flags（点一下设上 / 去掉）"
	t.add_theme_color_override("font_color", UITheme.TEXT_DIM)
	v.add_child(t)
	for f in all_flags():
		var b := _btn(f, _toggle_flag.bind(f))
		v.add_child(b)
		_flag_btns[f] = b


func _build_switches(v: VBoxContainer) -> void:
	for k in [["fast", "快走 ×3"], ["skip", "跳过对话"], ["ranges", "显示范围 / marker"], ["fog", "雾"], ["front", "前景层"]]:
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
		StoryState.clear_flag(f)
	else:
		StoryState.set_flag(f)


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
	_sync_switches()


func _sync_switches() -> void:
	var on := {"fast": fast, "skip": skip_dialog, "ranges": show_ranges, "fog": story.world.fog_enabled,
		"front": (level.get_node("Front") as CanvasItem).visible}
	for k in _toggles:
		var b: Button = _toggles[k]
		b.text = ("■ " if on[k] else "□ ") + str(b.get_meta("label"))


# ======================================================================= 自测（--dev_test）
func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


func _self_test() -> void:
	var flags := all_flags()
	var i: int = int(Engine.get_meta(TEST_META, -1))
	await _wait(1.5)
	if i >= 0:
		# 刚从面板跳过来：关掉面板、按住右走一会儿，看晨能不能动
		visible = false
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
		print("DEV_TEST beat %s: %s  state_ok=%s moved=%s x=%.0f" % [flags[i], "ok" if StoryState.has(flags[i]) else "MISSING",
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
		for n in story.world.markers:
			level.dev_teleport(str(n))
			await _wait(0.05)
		level.dev_teleport("chen_start")
		for f in ["got_wood", "zz_test_flag"]:
			_toggle_flag(f)
			_toggle_flag(f)
		for t in TABS.size():
			_set_tab(t)
			await _wait(0.25)
		print("DEV_TEST buttons ok (toggles %d, markers %d)" % [_toggles.size(), story.world.markers.size()])
		i = 0
	if i >= flags.size():
		Engine.remove_meta(TEST_META)
		print("DEV_TEST_DONE")
		get_tree().quit()
		return
	Engine.set_meta(TEST_META, i)
	_jump_beat(flags[i])


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
	var scene: String = story._cur_scene if story.busy else "—"
	_state_label.text = "scene: %s  步: %d\nx: %d  在: %s\n状态: %s%s\n背包: %s" % [
		scene, story.step_i, int(chen.position.x), story.world.room, level.S.keys()[level.state],
		"（带路中）" if story.free_walk else "", ", ".join(Inventory.owned)]
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
		_overlay.draw_string(f, Vector2(x + 2, 70 + (12 if room else 0)), str(n), HORIZONTAL_ALIGNMENT_LEFT, -1, 14, c)
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
