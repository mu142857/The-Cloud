extends Control
## 驾驶舱里真正的行动选择（终章两次：下降 / 漂行、最终导航；docs/第三章计划.md 第十节）。剧本照旧写 pick，多一个 "ui"：
##   {"do": "pick", "ui": "action", "options": [{"id", "label", "scene", "confirm": {zh, en}}…]}
##     一张卡片、几行选项（↑/↓、←/→ 或鼠标），E / 空格 / 回车选。
##   {"do": "pick", "ui": "nav", "title": {zh, en}, "nav_state": "landing_zone",
##    "options": [{"id", "label", "scene", "confirm", "pt": [x, y], "signal": "faded" / "weak" / "broadcast"}…]}
##     导航屏卡片：云层刚分开，下面一条地平线，飞船在上面正中；每个选项是地面上的一个点（pt = 地图里的像素，地图 MAP 那么大）。
##     选中的点套个框、从飞船拉一条虚线下去，卡片下面写它的名字。点的样子按 signal：
##       faded = 褪色的方块（标记褪色了，一明一暗）；weak = 一圈圈往外的波纹，时有时无（声源无法确定，信号会断）；
##       broadcast = 稳定的点 + 两道小弧（城市广播）。
##   两种都是：选了以后卡片下面换成确认（选项的 confirm 文字，没有就是「选项名？」）+「确认」/「再想想」。
##   再想想（或 Esc）= 回到挑的界面，可以换。确认 = 闪一下 + 确认音，界面淡掉，返回选了第几个。这两次选择决定结局，所以要确认。
##   界面开着的时候导航屏物件 cockpit_nav 换成 nav_state（nav 默认 landing_zone），晨转过去看它；关掉以后换回原来的状态。
## 选项可带 "fuel_need": n（11-07 终章结局重构：芦苇地要全收集、全烧）：燃料（StoryState.fuel）不到 n 的灰掉，
##   名字后面写「（燃料还差 X）」，选它只响一声闷的、卡片下面提示一下，不进确认；自动玩选的是灰的就换第一个不灰的。
## story_runner._pick 建它（挂在对话界面下，按键先到这里）：var i = await play(runner, st, auto_i)。跳节拍不建（直接用 auto_i）。
## 自动玩：main 过一会儿直接选 auto_i、确认；full 先挑一个别的、在确认里点「再想想」，再选 auto_i 确认（「再想想」那条路也走一遍）。

signal done(i: int)

const BG := Color(0.02, 0.05, 0.04, 0.9)
const EDGE := Color(0.5, 0.6, 0.55, 0.45)
const MAP := Vector2(212, 92)          # 导航图多大（卡片里）
const SKY_C := Color("#0d1f22")
const CLOUD_C := Color("#5f7f86")
const GROUND_C := Color("#7fc7a4")
const LINE_C := Color("#d9c9a0")
const PT_C := {"faded": Color("#c9a86a"), "weak": Color("#8fb8c8"), "broadcast": Color("#e8dcb0")}
const TXT := {
	"ok": ["Confirm", "确认", "Confirmer"],
	"back": ["Not yet", "再想想", "Pas encore"],
	"keys_nav": ["← → choose   E select", "← → 选   E 确定", "← → Choisir   E Valider"],
	"keys_action": ["↑ ↓ choose   E select", "↑ ↓ 选   E 确定", "↑ ↓ Choisir   E Valider"],
	"short": [" (%d more fuel needed)", "（燃料还差 %d）", " (il manque %d de carburant)"],
	"locked": ["Not enough fuel: %d short.", "燃料不够，还差 %d。", "Il manque %d de carburant."],
}

var runner: Node
var cockpit: Node2D
var st: Dictionary
var opts: Array = []
var nav := false
var _sel := 0
var _mode := "pick"                    # pick / confirm / busy
var _card: Panel
var _map: Control
var _rows: Array[Label] = []           # action：每个选项一行
var _name: Label                       # nav：选中的点叫什么
var _keys: Label
var _prompt: Label
var _btns: Array[Label] = []
var _btn_sel := 0
var _t := 0.0
var _nav_was := ""
var _auto_i := -1
var _auto_plan: Array = []
var _auto_t := 0.0
var _lock_t := 0.0                     # 点了灰的选项：提示还亮多久


func play(r: Node, step: Dictionary, auto_i := -1) -> int:
	runner = r
	cockpit = r.world.cockpit
	st = step
	opts = st.get("options", [])
	nav = str(st.get("ui", "")) == "nav"
	if auto_i >= 0 and auto_i < opts.size() and _short(auto_i) > 0:
		for j in opts.size():
			if _short(j) <= 0:
				auto_i = j
				break
	_auto_i = auto_i
	_build()
	if cockpit != null:
		_nav_was = cockpit.state_of("cockpit_nav")
		var ns := str(st.get("nav_state", "landing_zone" if nav else ""))
		if ns != "":
			r.world.set_prop("cockpit_nav", ns)
		var nx: float = cockpit.mx("cockpit_nav")
		r.chen._set_facing(1 if nx > r.chen.position.x else -1)
	if r.auto != "" and auto_i >= 0:
		var other := (auto_i + 1) % maxi(1, opts.size())
		if r.auto == "full" and opts.size() > 1:
			_auto_plan = ["sel:%d" % other, "choose", "back", "sel:%d" % auto_i, "choose", "ok"]
		else:
			_auto_plan = ["sel:%d" % auto_i, "choose", "ok"]
	r._ui_shot("nav" if nav else "action", 0.6)
	var i: int = await done
	if cockpit != null and _nav_was != "":
		r.world.set_prop("cockpit_nav", _nav_was)
	print("COCKPIT pick %s (%s): %s" % [str(st.get("id", "")), str(st.get("ui", "")), str(opts[i].get("id", i))])
	return i


# ======================================================================= 界面
func _label(text: String, c: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 14)
	l.add_theme_color_override("font_color", c)
	l.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.8))
	l.add_theme_constant_override("shadow_offset_x", 0)
	l.add_theme_constant_override("shadow_offset_y", 1)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


func _tw(s: String) -> float:
	return UITheme.font().get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x


func _tx(k: String) -> String:
	return I18n.row_text(TXT[k])


func _opt_label(i: int) -> String:
	var s: String = runner.txt(opts[i].get("label", opts[i].get("id", "")))
	var d := _short(i)
	return s + (_tx("short") % d if d > 0 else "")


## 这个选项还差多少燃料（0 = 够了 / 不要求）
func _short(i: int) -> int:
	var n := int(opts[i].get("fuel_need", 0))
	return maxi(0, n - StoryState.fuel()) if n > 0 else 0


func _build() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme = UITheme.get_theme()
	_card = Panel.new()
	_card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_card.add_theme_stylebox_override("panel", UITheme.box(BG, EDGE, 1))
	add_child(_card)
	var w := MAP.x + 20.0
	var y := 8.0
	if st.has("title"):
		var title := _label(runner.txt(st["title"]), Color("#dcc39a"))
		title.position = Vector2(10, 4)
		_card.add_child(title)
		y = 24.0
	if nav:
		_map = Control.new()
		_map.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_map.position = Vector2(10, y)
		_map.size = MAP
		_map.draw.connect(_draw_map)
		_card.add_child(_map)
		y += MAP.y + 4.0
		_name = _label("", UITheme.TEXT)
		_name.position = Vector2(10, y)
		_card.add_child(_name)
		y += 18.0
		for i in opts.size():
			w = maxf(w, _tw(_opt_label(i)) + 20.0)
	else:
		for i in opts.size():
			var l := _label("", UITheme.TEXT_DIM)
			l.position = Vector2(10, y)
			_card.add_child(l)
			_rows.append(l)
			w = maxf(w, _tw(UITheme.MARK + " " + _opt_label(i)) + 20.0)
			y += 18.0
		y += 2.0
	for i in opts.size():
		w = maxf(w, _tw(_confirm_text(i)) + 20.0)
	w = minf(roundf(w), 456.0)
	_prompt = _label("", UITheme.TEXT)
	_prompt.position = Vector2(10, y)
	_prompt.visible = false
	_card.add_child(_prompt)
	var h := y + 38.0
	_card.size = Vector2(w, h)
	_card.position = Vector2(roundf(240.0 - w / 2.0), roundf(maxf(20.0, 118.0 - h / 2.0)))
	if nav:
		_map.position.x = roundf((w - MAP.x) / 2.0)
	_keys = _label(_tx("keys_nav" if nav else "keys_action"), UITheme.TEXT_DIM)
	_keys.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_keys.size = Vector2(480, 16)
	_keys.position = Vector2(0, 222)
	_keys.modulate.a = 0.7
	add_child(_keys)
	_style()
	modulate.a = 0.0
	create_tween().tween_property(self, "modulate:a", 1.0, 0.3)


func _confirm_text(i: int) -> String:
	var c = opts[i].get("confirm", null)
	if c != null:
		return runner.txt(c)
	return _opt_label(i) + I18n.row_text(["?", "？", " ?"])


func _style() -> void:
	for i in _rows.size():
		var on := i == _sel
		_rows[i].text = (UITheme.MARK + " " if on else UITheme.MARK_OFF + " ") + _opt_label(i)
		_rows[i].add_theme_color_override("font_color", UITheme.TEXT if on and _short(i) <= 0 else UITheme.TEXT_DIM)
		_rows[i].modulate.a = (1.0 if _mode == "pick" or on else 0.45) * (0.55 if _short(i) > 0 else 1.0)
	if _name != null:
		_name.text = _opt_label(_sel)
	_keys.visible = _mode == "pick" and _lock_t <= 0.0
	_prompt.visible = _mode != "pick" or _lock_t > 0.0
	for i in _btns.size():
		var on := i == _btn_sel
		var l := _btns[i]
		l.text = (UITheme.MARK + " " if on else UITheme.MARK_OFF + " ") + str(l.get_meta("text"))
		l.add_theme_color_override("font_color", UITheme.TEXT if on else UITheme.TEXT_DIM)


func _sound(n: String, db: float, pitch := 1.0) -> void:
	var f: Callable = runner.dlg.sfx
	if f.is_valid():
		f.call(n, db, pitch)


## 导航图：上面是刚分开的云，下面一条地平线；飞船在上面正中；三个点按 signal 画；选中的套框、拉虚线
func _draw_map() -> void:
	var d := _map
	d.draw_rect(Rect2(Vector2.ZERO, MAP), SKY_C)
	# 云：上沿两排断开的横条（中间分开一道口子，飞船从那里下去）
	for row in 2:
		var cy := 6.0 + row * 5.0
		var x := -fmod(_t * (4.0 + row * 3.0), 18.0)
		while x < MAP.x:
			var seg := 10.0 + float(int(x * 7.0 + row * 13.0) % 5)
			if absf(x + seg / 2.0 - MAP.x / 2.0) > 22.0 - row * 6.0:
				d.draw_rect(Rect2(roundf(x), cy, seg, 2), Color(CLOUD_C, 0.55 - row * 0.15))
			x += seg + 8.0
	# 地平线：缓缓起伏的一条线 + 下面几根很淡的芦苇
	var gy := MAP.y - 22.0
	for x in int(MAP.x):
		var y := gy + roundf(sin(x * 0.045) * 2.0 + sin(x * 0.11 + 1.3) * 1.0)
		d.draw_rect(Rect2(x, y, 1, 1), Color(GROUND_C, 0.7))
		if x % 7 == 3:
			d.draw_rect(Rect2(x, y + 3, 1, 3), Color(GROUND_C, 0.18))
	# 飞船
	var ship := Vector2(roundf(MAP.x / 2.0), 16.0)
	d.draw_rect(Rect2(ship.x - 3, ship.y, 7, 2), LINE_C)
	d.draw_rect(Rect2(ship.x - 1, ship.y - 2, 3, 2), LINE_C)
	for i in opts.size():
		var p := _pt(i)
		var sig := str(opts[i].get("signal", ""))
		var c: Color = PT_C.get(sig, GROUND_C)
		var on := i == _sel
		match sig:
			"faded":
				var a := 0.35 + 0.45 * (0.5 + 0.5 * sin(_t * 1.7 + i))
				d.draw_rect(Rect2(p - Vector2(1, 1), Vector2(3, 3)), Color(c, a))
			"weak":
				# 一圈圈往外的波纹；每 3.1 秒里有一截收不到（信号断了）
				if fmod(_t + i * 0.7, 3.1) < 2.2:
					d.draw_rect(Rect2(p - Vector2(1, 1), Vector2(3, 3)), Color(c, 0.9))
					var k := fmod(_t, 1.4) / 1.4
					_ring(d, p, 2.0 + k * 9.0, Color(c, 0.6 * (1.0 - k)))
			"broadcast":
				d.draw_rect(Rect2(p - Vector2(1, 1), Vector2(3, 3)), c)
				var b := 0.25 + 0.35 * (0.5 + 0.5 * sin(_t * 3.0))
				d.draw_rect(Rect2(p + Vector2(-5, -6), Vector2(1, 3)), Color(c, b))
				d.draw_rect(Rect2(p + Vector2(5, -6), Vector2(1, 3)), Color(c, b))
				d.draw_rect(Rect2(p + Vector2(-8, -9), Vector2(1, 5)), Color(c, b * 0.6))
				d.draw_rect(Rect2(p + Vector2(8, -9), Vector2(1, 5)), Color(c, b * 0.6))
			_:
				d.draw_rect(Rect2(p - Vector2(1, 1), Vector2(3, 3)), c)
		if on:
			# 虚线从飞船斜着下去（一段一段往下走）+ 四角框
			var n := int(p.distance_to(ship) / 3.0)
			var off := int(_t * 8.0) % 2
			for s in range(off, n, 2):
				var q := ship.lerp(p, float(s) / n).round()
				d.draw_rect(Rect2(q, Vector2(1, 1)), Color(LINE_C, 0.7))
			var bob := 1.0 if fmod(_t, 0.8) < 0.4 else 0.0
			var r := 5.0 + bob
			for corner in [Vector2(-1, -1), Vector2(1, -1), Vector2(-1, 1), Vector2(1, 1)]:
				var cc: Vector2 = p + (corner as Vector2) * r
				d.draw_rect(Rect2(cc.x - (0 if corner.x < 0 else 1), cc.y, 2, 1), LINE_C)
				d.draw_rect(Rect2(cc.x, cc.y - (0 if corner.y < 0 else 1), 1, 2), LINE_C)
	d.queue_redraw()


func _ring(d: Control, p: Vector2, r: float, c: Color) -> void:
	var n := maxi(8, int(r * 4.0))
	for s in n:
		var a := TAU * s / n
		d.draw_rect(Rect2((p + Vector2(cos(a), sin(a) * 0.6) * r).round(), Vector2(1, 1)), c)


func _pt(i: int) -> Vector2:
	var p = opts[i].get("pt", null)
	if p is Array and p.size() >= 2:
		return Vector2(float(p[0]), float(p[1])).round()
	return Vector2(roundf(MAP.x * (i + 1.0) / (opts.size() + 1.0)), MAP.y - 18.0)


func _process(delta: float) -> void:
	_t += delta
	if _lock_t > 0.0:
		_lock_t -= delta
		if _lock_t <= 0.0:
			_style()
	_auto_tick(delta)


# ======================================================================= 动作
func _set_sel(i: int) -> void:
	i = posmod(i, opts.size())
	if i == _sel:
		return
	_sel = i
	_style()
	_sound("ui_click", -14.0, 1.35)


## 方向键挑：nav 按点在图上从左到右的顺序走（选项在剧本里的顺序是结局一、二、三，图上是西、居民区、东）
func _step_sel(d: int) -> void:
	var order: Array = range(opts.size())
	if nav:
		order.sort_custom(func(a, b): return _pt(a).x < _pt(b).x)
	_set_sel(int(order[posmod(order.find(_sel) + d, order.size())]))


func _choose() -> void:
	if _mode != "pick":
		return
	if _short(_sel) > 0:
		_sound("tick", -6.0, 0.6)          # 灰的：闷一声，提示还差多少，不进确认
		_prompt.text = _tx("locked") % _short(_sel)
		_lock_t = 2.2
		_style()
		return
	_lock_t = 0.0
	_mode = "confirm"
	_sound("tick", -6.0, 1.0)
	_prompt.text = _confirm_text(_sel)
	for l in _btns:
		l.queue_free()
	_btns.clear()
	var x := 10.0
	for s in [_tx("ok"), _tx("back")]:
		var l := _label("", UITheme.TEXT_DIM)
		l.set_meta("text", s)
		l.position = Vector2(x, _prompt.position.y + 18.0)
		_card.add_child(l)
		_btns.append(l)
		x += _tw(UITheme.MARK + " " + s) + 18.0
	_btn_sel = 1                       # 光标先停在「再想想」：手快连按两下不会直接定下结局
	_style()


func _set_btn(i: int) -> void:
	i = posmod(i, _btns.size())
	if i == _btn_sel:
		return
	_btn_sel = i
	_style()
	_sound("ui_click", -14.0, 1.35)


func _press(i: int) -> void:
	if _mode != "confirm":
		return
	_set_btn(i)
	if i == 1:
		_sound("tick", -8.0, 1.1)
		for l in _btns:
			l.queue_free()
		_btns.clear()
		_mode = "pick"
		_style()
		return
	_mode = "busy"
	_sound("tick", -4.0, 0.9)
	_sound("flight_select", -10.0, 1.0)
	_card.modulate = Color(1.8, 1.8, 1.8)
	await get_tree().create_timer(0.2, false).timeout
	_card.modulate = Color.WHITE
	await get_tree().create_timer(0.15, false).timeout
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 0.0, 0.3)
	await tw.finished
	done.emit(_sel)


# ======================================================================= 输入
func _input(event: InputEvent) -> void:
	if runner == null or runner.auto != "" or _mode == "busy":
		return
	var vp := get_viewport()
	if event is InputEventKey and event.pressed and not event.echo:
		var k: int = event.keycode
		var prev := k in [KEY_LEFT, KEY_A, KEY_UP, KEY_W]
		var next := k in [KEY_RIGHT, KEY_D, KEY_DOWN, KEY_S]
		var ok := k in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_Z]
		if _mode == "pick":
			if prev:
				_step_sel(-1)
			elif next:
				_step_sel(1)
			elif ok:
				_choose()
		else:
			if prev:
				_set_btn(_btn_sel - 1)
			elif next:
				_set_btn(_btn_sel + 1)
			elif ok:
				_press(_btn_sel)
			elif k == KEY_ESCAPE:
				_press(1)
		vp.set_input_as_handled()
		return
	if event is InputEventMouseMotion:
		var i := _hit(event.position)
		if i >= 0:
			if _mode == "pick":
				_set_sel(i)
			else:
				_set_btn(i)
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var i := _hit(event.position)
		if i >= 0:
			if _mode == "pick":
				_set_sel(i)
				_choose()
			else:
				_press(i)
		vp.set_input_as_handled()


## 鼠标在哪个上面：挑的时候 = 第几个选项（nav：点附近 10 像素），确认时 = 第几个按钮；都不在 = -1
func _hit(p: Vector2) -> int:
	if _mode == "pick":
		if nav:
			var best := -1
			var bd := 12.0
			for i in opts.size():
				var dd := (_map.global_position + _pt(i)).distance_to(p)
				if dd < bd:
					bd = dd
					best = i
			return best
		for i in _rows.size():
			var l := _rows[i]
			if Rect2(l.global_position - Vector2(2, 1), Vector2(_card.size.x - 16.0, 17)).has_point(p):
				return i
		return -1
	for i in _btns.size():
		var l := _btns[i]
		if Rect2(l.global_position - Vector2(2, 2), l.get_combined_minimum_size() + Vector2(4, 4)).has_point(p):
			return i
	return -1


## F8 自测：替玩家选（自动玩会选的那个，没有就第一个）并确认
func dev_skip() -> void:
	if _mode == "pick":
		_set_sel(maxi(0, _auto_i))
		_choose()
	elif _mode == "confirm":
		_press(0)


# ======================================================================= 自动玩
func _auto_tick(delta: float) -> void:
	if _auto_plan.is_empty() or _mode == "busy":
		return
	_auto_t += delta
	if _auto_t < 0.7:
		return
	_auto_t = 0.0
	var a := str(_auto_plan.pop_front())
	if a.begins_with("sel:"):
		_set_sel(int(a.trim_prefix("sel:")))
	elif a == "choose":
		_choose()
	elif a == "back":
		_press(1)
	elif a == "ok":
		_press(0)
