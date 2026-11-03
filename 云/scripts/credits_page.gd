extends Control
## 制作人员页（标题界面「制作人员」、设置面板里的「制作人员」都打开它）。
## 名单读 data/credits.json（和第一关奔跑片头 run_credits.gd 同一份）：每人一行职务（暗）+ 名字（各人的颜色），
## 一个接一个往上浮出来；最后一条（特别感谢）隔开一点。背景是压暗的森林，上面飘几颗和名字同色的光点。
## 任意键 / 点击 / Esc 关闭（打开 0.4 秒以后才认，免得点开的那一下直接关掉）。
##   var p := preload("res://scripts/credits_page.gd").new(); root.add_child(p); p.closed.connect(...)

signal closed

const DATA := "res://data/credits.json"
const VEIL := Color("#050b08")
const VEIL_A := 0.9
const HEAD_C := Color("#8fa69a")
const ROLE_C := Color("#7f988b")
const TOP := 46.0           # 第一个人的职务那行
const ROW := 34.0           # 每个人占的高度
const THANKS_GAP := 12.0    # 特别感谢前面多空一点
const STAGGER := 0.35       # 一个接一个出来的间隔
const RISE := 3.0           # 浮上来的像素
const MOTES := 14

var _t := 0.0
var _closing := false
var _rows: Array = []       # [{node, delay}]
var _motes: Array = []      # [{node, base, phase, speed}]
var _veil: ColorRect


func _ready() -> void:
	size = Vector2(480, 270)
	mouse_filter = Control.MOUSE_FILTER_STOP
	modulate.a = 0.0
	_veil = ColorRect.new()
	_veil.color = Color(VEIL, VEIL_A)
	_veil.size = size
	_veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_veil)
	var zh := I18n.is_zh()
	var entries: Array = _load()
	var colors: Array = []
	var head := _lbl("制作人员" if zh else "Credits", 14, HEAD_C, UITheme.spaced_font(3))
	head.position.y = 16
	add_child(head)
	_rows.append({"node": head, "delay": 0.0, "y": head.position.y})
	var y := TOP
	var i := 0
	for e in entries:
		if not e is Dictionary:
			continue
		if str(e.get("style", "")) == "sky":     # 特别感谢（片头里挂在天上的那条）

			y += THANKS_GAP
		var role := _txt(e.get("role", {}), zh)
		var nm := _txt(e.get("name", {}), zh)
		var col := Color("#" + str(e.get("color", "dfe8e2")))
		colors.append(col)
		var box := Control.new()
		box.size = Vector2(480, ROW)
		box.position.y = y
		box.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(box)
		var r := _lbl(role, 12, ROLE_C, UITheme.spaced_font(2))
		r.position.y = 0
		box.add_child(r)
		var n := _lbl(nm, 14, col, UITheme.spaced_font(2))
		n.position.y = 13
		n.add_theme_color_override("font_shadow_color", Color(col, 0.25))
		n.add_theme_constant_override("shadow_offset_x", 0)
		n.add_theme_constant_override("shadow_offset_y", 1)
		box.add_child(n)
		box.modulate.a = 0.0
		_rows.append({"node": box, "delay": 0.25 + STAGGER * (i + 1), "y": y})
		y += ROW
		i += 1
	var hint := _lbl("按任意键返回" if zh else "Press any key", 12, Color(HEAD_C, 0.7), UITheme.spaced_font(1))
	hint.position.y = 270 - 22
	add_child(hint)
	_rows.append({"node": hint, "delay": 0.25 + STAGGER * (i + 2), "y": hint.position.y})
	# 光点：每颗取一个人的颜色，在名字两边慢慢飘
	var rng := RandomNumberGenerator.new()
	rng.seed = 2611
	for k in MOTES:
		var m := ColorRect.new()
		m.size = Vector2(1, 1)
		m.color = colors[k % colors.size()] if not colors.is_empty() else UITheme.TEXT
		m.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var side := -1.0 if k % 2 == 0 else 1.0
		var base := Vector2(240.0 + side * rng.randf_range(90.0, 210.0), rng.randf_range(30.0, 240.0))
		add_child(m)
		move_child(m, 1)
		_motes.append({"node": m, "base": base, "phase": rng.randf() * TAU, "speed": rng.randf_range(0.25, 0.6)})
	create_tween().tween_property(self, "modulate:a", 1.0, 0.5).set_trans(Tween.TRANS_SINE)


func _process(delta: float) -> void:
	_t += delta
	for r in _rows:
		var k := clampf((_t - float(r["delay"])) / 0.8, 0.0, 1.0)
		k = k * k * (3.0 - 2.0 * k)
		var nd: Control = r["node"]
		nd.modulate.a = k
		nd.position.y = float(r["y"]) + roundf(RISE * (1.0 - k))
	for m in _motes:
		var ph: float = m["phase"] + _t * float(m["speed"])
		var b: Vector2 = m["base"]
		var nd2: ColorRect = m["node"]
		nd2.position = Vector2(roundf(b.x + sin(ph) * 6.0), roundf(b.y - fposmod(_t * 4.0 * float(m["speed"]), 40.0) + 20.0))
		nd2.modulate.a = 0.35 + 0.45 * (0.5 + 0.5 * sin(ph * 2.3))


## level_forest 的 _input 把事件先交给这里；返回 true = 吃掉了
func handle(event: InputEvent) -> bool:
	var press := (event is InputEventKey and event.pressed and not event.echo) or (event is InputEventMouseButton and event.pressed)
	if press and _t > 0.4:
		close()
	return true


func close() -> void:
	if _closing:
		return
	_closing = true
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 0.0, 0.4).set_trans(Tween.TRANS_SINE)
	tw.tween_callback(func():
		closed.emit()
		queue_free())


func _lbl(text: String, sz: int, col: Color, f: Font) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", f)
	l.add_theme_font_size_override("font_size", sz)
	l.add_theme_color_override("font_color", col)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.size = Vector2(480, sz + 4)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


func _txt(v, zh: bool) -> String:
	if v is Dictionary:
		var s := str(v.get("zh" if zh else "en", ""))
		return s if s != "" else str(v.get("zh", v.get("en", "")))
	return str(v)


func _load() -> Array:
	if not FileAccess.file_exists(DATA):
		return []
	var d = JSON.parse_string(FileAccess.get_file_as_string(DATA))
	if d is Dictionary and d.get("entries") is Array:
		return d["entries"]
	return []
