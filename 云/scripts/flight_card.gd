extends Node2D
## 决定卡：轮到私人物品 / 朋友的东西时弹出来。没有倒计时，等玩家选。
##   single：一件东西（图、名字、一句描述、能烧出多少燃料），「烧掉 / 留下」
##   pick  ：紧急模式快掉下去时的最后一次机会：剩下的私人物品排成一排，选一件烧掉，或者「都留下」
## 操作：←/→（或 A/D）选，空格 / 回车 / Z 确认，鼠标直接点。默认选「留下」，免得手快按掉。
## 卡在 SubViewport 里按 1 倍像素画好，再贴到屏幕上，烧掉的动画是 flight_burn.gdshader（从边往里烧成灰），
## 同时往飞船尾巴飞火星（fx.ember）。按真实时间播放（世界那边是慢动作）。

signal chosen(action: String, index: int)   # action: "burn" / "keep"；index：pick 模式里第几件
signal closed

const CARD_TEX := preload("res://art/flight/card.png")
const FLAME_TEX := preload("res://art/flight/ui_flame.png")
const KEEP_TEX := preload("res://art/flight/ui_keep.png")
const DROP_TEX := preload("res://art/flight/ui_drop.png")
const SHADER := preload("res://scripts/flight_burn.gdshader")
const W := 220
const H := 178
const CENTER := Vector2(240, 130)
const BTN_Y := 148
const C_HEAD := Color("8d97b8")
const C_NAME := Color("f1e6d0")
const C_DESC := Color("b7b3c4")
const C_ON := Color("f6d9a0")
const C_OFF := Color("59617a")
const C_FUEL := Color("d9a35e")

var fx: Node2D
var sfx_cb: Callable        # sfx_cb.call("select")
var keep_target := Vector2(40, 252)
var mode := ""             # "" = 关着
var items: Array = []      # 卡上的物品数据（Dictionary）
var sel := 0               # single：0 烧掉 / 1 留下；pick：0..n-1 = 物品，n = 都留下
var state := ""            # in / wait / burn / keep
var anim := 0.0
var input_ready := false   # 打开以后要先松开所有键，免得按着空格飞的手直接点掉

var _vp: SubViewport
var _root: Node2D
var _sprite: Sprite2D
var _mat: ShaderMaterial
var _dim: ColorRect
var _labels := {}
var _icons: Array = []
var _sel_marks: Array = []
var _burn_index := -1
var _ember_acc := 0.0


func _ready() -> void:
	_dim = ColorRect.new()
	_dim.size = Vector2(480, 270)
	_dim.color = Color(0.01, 0.02, 0.05, 0.0)
	_dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_dim)
	_vp = SubViewport.new()
	_vp.size = Vector2i(W, H)
	_vp.transparent_bg = true
	_vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_vp)
	_root = Node2D.new()
	_vp.add_child(_root)
	_sprite = Sprite2D.new()
	_sprite.texture = _vp.get_texture()
	_mat = ShaderMaterial.new()
	_mat.shader = SHADER
	_mat.set_shader_parameter("size", Vector2(W, H))
	_sprite.material = _mat
	add_child(_sprite)
	visible = false


func _label(text: String, col: Color, pos: Vector2, width: float, align := HORIZONTAL_ALIGNMENT_CENTER,
		wrap := false) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", FlightText.font())
	l.add_theme_font_size_override("font_size", FlightText.SIZE)
	l.add_theme_color_override("font_color", col)
	l.add_theme_constant_override("line_spacing", 1)
	l.horizontal_alignment = align
	l.position = pos
	l.size = Vector2(width, 12)
	if wrap:
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_root.add_child(l)
	return l


func _clear() -> void:
	for c in _root.get_children():
		c.queue_free()
	_labels.clear()
	_icons.clear()
	_sel_marks.clear()


func open_single(item: Dictionary) -> void:
	_clear()
	mode = "single"
	items = [item]
	sel = 1
	var bg := Sprite2D.new()
	bg.texture = CARD_TEX
	bg.centered = false
	_root.add_child(bg)
	_label(FlightText.t("card_head"), C_HEAD, Vector2(0, 7), W)
	var ic := Sprite2D.new()
	ic.texture = item.tex
	ic.scale = Vector2(2, 2)
	ic.position = Vector2(W / 2.0, 48)
	_root.add_child(ic)
	_icons.append(ic)
	var fuel_ic := Sprite2D.new()
	fuel_ic.texture = DROP_TEX
	fuel_ic.centered = false
	fuel_ic.position = Vector2(148, 63)
	_root.add_child(fuel_ic)
	_label("+%d" % int(item.fuel), C_FUEL, Vector2(155, 59), 50, HORIZONTAL_ALIGNMENT_LEFT)
	_label(FlightText.pick(item.name), C_NAME, Vector2(0, 76), W)
	var d := _label(FlightText.pick(item.desc), C_DESC, Vector2(14, 93), W - 28, HORIZONTAL_ALIGNMENT_CENTER, true)
	d.size = Vector2(W - 28, 46)
	_buttons(FlightText.t("burn"), FlightText.t("keep"))
	_open()


func open_pick(list: Array) -> void:
	_clear()
	mode = "pick"
	items = list
	sel = list.size()
	var bg := Sprite2D.new()
	bg.texture = CARD_TEX
	bg.centered = false
	_root.add_child(bg)
	_label(FlightText.t("pick_head"), C_HEAD, Vector2(0, 7), W)
	var n := list.size()
	var gap := 56.0 if n <= 3 else 52.0
	for i in n:
		var ic := Sprite2D.new()
		ic.texture = list[i].tex
		ic.scale = Vector2(2, 2)
		ic.position = Vector2(W / 2.0 + (i - (n - 1) / 2.0) * gap, 48)
		_root.add_child(ic)
		_icons.append(ic)
		var mark := ColorRect.new()
		mark.color = C_ON
		mark.size = Vector2(16, 1)
		mark.position = ic.position + Vector2(-8, 26)
		_root.add_child(mark)
		_sel_marks.append(mark)
	_labels["name"] = _label("", C_NAME, Vector2(0, 78), W)
	var d := _label("", C_DESC, Vector2(14, 95), W - 28, HORIZONTAL_ALIGNMENT_CENTER, true)
	d.size = Vector2(W - 28, 46)
	_labels["desc"] = d
	_buttons(FlightText.t("burn"), FlightText.t("keep_all"))
	_open()


func _buttons(a: String, b: String) -> void:
	_labels["burn"] = _label(a, C_OFF, Vector2(14, BTN_Y), W / 2.0 - 14)
	_labels["keep"] = _label(b, C_OFF, Vector2(W / 2.0, BTN_Y), W / 2.0 - 14)
	for k in ["burn", "keep"]:
		var ic := Sprite2D.new()
		ic.texture = FLAME_TEX if k == "burn" else KEEP_TEX
		ic.centered = false
		_root.add_child(ic)
		_labels[k + "_ic"] = ic
		var u := ColorRect.new()
		u.size = Vector2(30, 1)
		_root.add_child(u)
		_labels[k + "_u"] = u


func _open() -> void:
	visible = true
	state = "in"
	anim = 0.0
	input_ready = false
	_burn_index = -1
	_mat.set_shader_parameter("burn", 0.0)
	_mat.set_shader_parameter("fade", 0.0)
	_sprite.position = CENTER + Vector2(0, 8)
	_sprite.scale = Vector2.ONE
	_refresh()


func _refresh() -> void:
	var on_burn := false
	if mode == "single":
		on_burn = sel == 0
	else:
		on_burn = sel < items.size()
		for i in _sel_marks.size():
			(_sel_marks[i] as ColorRect).visible = i == sel
			var none_sel := sel >= items.size()
			(_icons[i] as Sprite2D).modulate = Color(1, 1, 1) if i == sel else (Color(0.8, 0.8, 0.88) if none_sel else Color(0.42, 0.42, 0.52))
		if sel < items.size():
			_labels.name.text = FlightText.pick(items[sel].name) + "   +%d" % int(items[sel].fuel)
			_labels.desc.text = FlightText.pick(items[sel].desc)
		else:
			_labels.name.text = ""
			_labels.desc.text = FlightText.t("pick_all")
	for k in ["burn", "keep"]:
		var active := on_burn if k == "burn" else not on_burn
		var l: Label = _labels[k]
		l.add_theme_color_override("font_color", C_ON if active else C_OFF)
		var tw := FlightText.font().get_string_size(l.text, HORIZONTAL_ALIGNMENT_LEFT, -1, FlightText.SIZE).x
		var x0 := l.position.x + (l.size.x - tw) / 2.0
		var ic: Sprite2D = _labels[k + "_ic"]
		ic.position = Vector2(roundf(x0 - 11), BTN_Y + (2 if k == "burn" else 5))
		ic.modulate = Color(1, 1, 1) if active else Color(0.45, 0.45, 0.55)
		var u: ColorRect = _labels[k + "_u"]
		u.visible = active
		u.color = C_ON
		u.position = Vector2(roundf(x0), BTN_Y + 16)
		u.size = Vector2(roundf(tw), 1)


func _option_count() -> int:
	return 2 if mode == "single" else items.size() + 1


func _move(d: int) -> void:
	var n := _option_count()
	var s := clampi(sel + d, 0, n - 1)
	if s != sel:
		sel = s
		_refresh()
		if sfx_cb.is_valid():
			sfx_cb.call("select")


func _input(event: InputEvent) -> void:
	if state != "wait":
		return
	if not input_ready:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		var k: int = event.keycode
		if k in [KEY_LEFT, KEY_A]:
			_move(-1)
		elif k in [KEY_RIGHT, KEY_D]:
			_move(1)
		elif k in [KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_Z]:
			_confirm()
	elif event is InputEventMouseMotion:
		var o := _option_at(get_global_mouse_position())
		if o >= 0 and o != sel:
			sel = o
			_refresh()
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var o2 := _option_at(get_global_mouse_position())
		if o2 >= 0:
			if mode == "pick" and o2 < items.size() and o2 != sel:
				sel = o2
				_refresh()
				return
			sel = o2
			_refresh()
			_confirm()
	elif event is InputEventScreenTouch and event.pressed:
		var o3 := _option_at(get_canvas_transform().affine_inverse() * event.position)
		if o3 >= 0:
			sel = o3
			_refresh()
			_confirm()


func _option_at(p: Vector2) -> int:
	var local := p - (CENTER - Vector2(W, H) / 2.0)
	if local.y >= BTN_Y - 6 and local.y < H - 4:
		if local.x >= 8 and local.x < W / 2.0:
			return 0 if mode == "single" else (sel if sel < items.size() else -1)
		if local.x >= W / 2.0 and local.x < W - 8:
			return 1 if mode == "single" else items.size()
	if mode == "pick":
		for i in _icons.size():
			if local.distance_to((_icons[i] as Sprite2D).position) < 24:
				return i
	return -1


func choose(action: String, index := 0) -> void:
	## 机器人 / 测试直接选
	if mode == "single":
		sel = 0 if action == "burn" else 1
	else:
		sel = index if action == "burn" else items.size()
	_refresh()
	_confirm()


func _confirm() -> void:
	if state != "wait":
		return
	var burn := (sel == 0) if mode == "single" else (sel < items.size())
	anim = 0.0
	if burn:
		state = "burn"
		_burn_index = 0 if mode == "single" else sel
		chosen.emit("burn", _burn_index)
	else:
		state = "keep"
		chosen.emit("keep", -1)


func _process(delta: float) -> void:
	if not visible:
		return
	anim += delta
	match state:
		"in":
			var u := clampf(anim / 0.55, 0.0, 1.0)
			u = 1.0 - pow(1.0 - u, 3.0)
			_mat.set_shader_parameter("fade", u)
			_sprite.position = (CENTER + Vector2(0, 8.0 * (1.0 - u))).round()
			_dim.color.a = 0.5 * u
			if anim >= 0.55:
				state = "wait"
				anim = 0.0
		"wait":
			if not input_ready and anim > 0.35 and not _any_held():
				input_ready = true
		"burn":
			var b := clampf(anim / 1.6, 0.0, 1.0)
			_mat.set_shader_parameter("burn", b)
			_dim.color.a = 0.5 * (1.0 - clampf((anim - 1.0) / 0.8, 0.0, 1.0))
			_ember_acc += delta * 70.0 * (1.0 - b * 0.6)
			while _ember_acc >= 1.0 and fx and b < 0.95:
				_ember_acc -= 1.0
				fx.ember(_frontier_point(b), randf() * 0.1, randf() < 0.6)
			if anim >= 1.9:
				_close()
		"keep":
			var u2 := clampf(anim / 0.7, 0.0, 1.0)
			var e := u2 * u2
			_sprite.position = CENTER.lerp(keep_target, e).round()
			_sprite.scale = Vector2.ONE * lerpf(1.0, 0.12, e)
			_mat.set_shader_parameter("fade", 1.0 - u2 * 0.5)
			_dim.color.a = 0.5 * (1.0 - u2)
			if anim >= 0.7:
				_close()


func _frontier_point(b: float) -> Vector2:
	## 火线附近的一个点（只按到边的距离估，不算噪声，够用）
	var e := clampf(b * 1.3 / 0.8 - 0.15, 0.0, 1.0) * 0.5 * mini(W, H)
	var side := randi() % 4
	var p := Vector2.ZERO
	match side:
		0: p = Vector2(randf_range(e, W - e), e)
		1: p = Vector2(randf_range(e, W - e), H - e)
		2: p = Vector2(e, randf_range(e, H - e))
		_: p = Vector2(W - e, randf_range(e, H - e))
	return CENTER - Vector2(W, H) / 2.0 + p


func _close() -> void:
	visible = false
	state = ""
	mode = ""
	closed.emit()


func _any_held() -> bool:
	return Input.is_key_pressed(KEY_SPACE) or Input.is_key_pressed(KEY_ENTER) or Input.is_key_pressed(KEY_UP) \
		or Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) or Input.is_key_pressed(KEY_Z)


func is_open() -> bool:
	return visible
