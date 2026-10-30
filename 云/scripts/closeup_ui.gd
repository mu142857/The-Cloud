extends Control
## 特写面板：全屏一张图（本子页、来客册、图纸、设备柜、装卸记录、照片、防水板……），可带可点的区域。
## 格式见 docs/river_rooms_contract.md 第 6 节。story_runner.gd 建它（UI 层，对话框下面），剧本 {"do": "closeup"} 和
## 小游戏 story.closeup(spec) 都走 open()。
##   图：art/river_story/closeup_<img>[_<state>].png（img 也可以直接写 res:// 路径），原生 1:1、居中，四周压暗；
##     缺图 = 一块纸色面板，写着名字和状态，zones 画成框（照样能点）。
##   zones：[{id, rect: [x, y, w, h]（图里的像素）, label}]：鼠标停上去亮一档 + 显示 label；← → 在 zones 间切，E / 空格 / 回车选。
##   close（默认 true）：点空白 / Esc 关掉（返回 ""）；false = 必须点一个 zone。没有 zones：任意键 / 点击关掉。
##   lines：叠在图上的手写行（防水板记刻度）：[{zh, en}]，"at": [x, y] 第一行的位置（图里的像素）。
## 输入：level_forest.gd 的 _input 在剧情播放时先问 handle_input（和对话框一样），不靠 GUI 焦点。

signal closed(result: String)

const DIR := "res://art/river_story/"
const DIM := Color(0.02, 0.03, 0.04, 0.72)
const PAPER := Color("#cfc6b0")
const INK := Color("#3a342c")
const HOT := Color(0.85, 0.75, 0.45, 0.35)

var story: Node
var _open := false
var _spec := {}
var _zones: Array = []
var _sel := -1
var _img_rect := Rect2()
var _tex: Texture2D
var _ph_title := ""
var _t := 0.0
var _hint: Label


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	size = Vector2(480, 270)
	visible = false
	_hint = Label.new()
	_hint.add_theme_font_size_override("font_size", 14)
	_hint.add_theme_color_override("font_color", UITheme.TEXT)
	_hint.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))
	_hint.add_theme_constant_override("shadow_offset_y", 1)
	_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_hint)


func is_open() -> bool:
	return _open


## 图的路径：img + state → art/river_story/closeup_<img>_<state>.png（没有就 closeup_<img>.png）
static func tex_path(img: String, state := "") -> String:
	if img.begins_with("res://"):
		return img
	var base := DIR + "closeup_" + img
	if state != "" and _exists(base + "_" + state + ".png"):
		return base + "_" + state + ".png"
	if _exists(base + ".png"):
		return base + ".png"
	return ""


static func _exists(p: String) -> bool:
	return ResourceLoader.exists(p) or FileAccess.file_exists(p)


static func _load(p: String) -> Texture2D:
	if ResourceLoader.exists(p):
		return load(p)
	if FileAccess.file_exists(p):
		var img := Image.load_from_file(ProjectSettings.globalize_path(p))
		if img != null and not img.is_empty():
			return ImageTexture.create_from_image(img)
	return null


## 打开，等玩家看完 / 点一个；返回 zone id（关掉 = ""）。auto_index ≥ 0：自动玩，0.3 秒后选这个（-1 自动玩 = 关掉；-2 = 不是自动玩）
func open(spec: Dictionary, auto_index := -2) -> String:
	_spec = spec
	_zones = spec.get("zones", [])
	_sel = -1
	var img := str(spec.get("img", spec.get("id", "")))
	var st := str(spec.get("state", ""))
	var p := tex_path(img, st)
	_tex = _load(p) if p != "" else null
	if _tex == null:
		_ph_title = img + ("：" + st if st != "" else "")
		var sz := Vector2(300, 180)
		for z in _zones:
			var r: Array = z.get("rect", [0, 0, 0, 0])
			sz.x = maxf(sz.x, float(r[0]) + float(r[2]) + 12)
			sz.y = maxf(sz.y, float(r[1]) + float(r[3]) + 12)
		sz = sz.min(Vector2(470, 260))
		_img_rect = Rect2(((Vector2(480, 270) - sz) / 2.0).round(), sz)
	else:
		_ph_title = ""
		var sz2 := _tex.get_size()
		_img_rect = Rect2(((Vector2(480, 270) - sz2) / 2.0).round(), sz2)
	_open = true
	visible = true
	modulate.a = 0.0
	create_tween().tween_property(self, "modulate:a", 1.0, 0.18)
	_hint.text = ""
	queue_redraw()
	if auto_index > -2:
		await get_tree().create_timer(0.3).timeout
		if _open:
			_finish(str(_zones[auto_index].get("id", "")) if auto_index >= 0 and auto_index < _zones.size() else "")
		return _result
	var res: String = await closed
	return res


var _result := ""


func _finish(res: String) -> void:
	if not _open:
		return
	_open = false
	_result = res
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 0.0, 0.15)
	tw.tween_callback(func(): visible = false)
	closed.emit(res)


func _can_close() -> bool:
	return _zones.is_empty() or _spec.get("close", true)


func _zone_rect(i: int) -> Rect2:
	var r: Array = _zones[i].get("rect", [0, 0, 0, 0])
	return Rect2(_img_rect.position + Vector2(float(r[0]), float(r[1])), Vector2(float(r[2]), float(r[3])))


func _zone_at(p: Vector2) -> int:
	for i in _zones.size():
		if _zone_rect(i).grow(2).has_point(p):
			return i
	return -1


func _set_sel(i: int) -> void:
	_sel = i
	if i >= 0 and story != null:
		_hint.text = str(story.txt(_zones[i].get("label", {"zh": str(_zones[i].get("id", ""))})))
		var r := _zone_rect(i)
		_hint.position = Vector2(clampf(r.position.x, 4, 380), clampf(r.end.y + 2, 4, 250))
	else:
		_hint.text = ""
	queue_redraw()


func handle_input(event: InputEvent) -> bool:
	if not _open:
		return false
	if event is InputEventMouseMotion:
		var i := _zone_at(event.position)
		if i != _sel:
			_set_sel(i)
		return true
	if event is InputEventMouseButton and event.pressed:
		if event.button_index != MOUSE_BUTTON_LEFT:
			return true
		var i := _zone_at(event.position)
		if i >= 0:
			_finish(str(_zones[i].get("id", "")))
		elif _can_close():
			_finish("")
		return true
	if event is InputEventKey and event.pressed and not event.echo:
		var k: int = event.keycode
		if k == KEY_ESCAPE:
			if _can_close():
				_finish("")
		elif k in [KEY_LEFT, KEY_A, KEY_UP, KEY_W] and not _zones.is_empty():
			_set_sel((_sel - 1 + _zones.size()) % _zones.size() if _sel >= 0 else _zones.size() - 1)
		elif k in [KEY_RIGHT, KEY_D, KEY_DOWN, KEY_S] and not _zones.is_empty():
			_set_sel((_sel + 1) % _zones.size())
		elif k in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_Z]:
			if _zones.is_empty():
				_finish("")
			elif _sel >= 0:
				_finish(str(_zones[_sel].get("id", "")))
			else:
				_set_sel(0)
		return true
	return true


func _process(delta: float) -> void:
	if _open:
		_t += delta
		if not _zones.is_empty():
			queue_redraw()


func _draw() -> void:
	draw_rect(Rect2(0, 0, 480, 270), DIM)
	var f := ThemeDB.fallback_font
	if _tex != null:
		draw_texture(_tex, _img_rect.position)
	else:
		draw_rect(_img_rect, PAPER)
		draw_rect(_img_rect, INK.lerp(PAPER, 0.5), false, 1.0)
		draw_string(f, _img_rect.position + Vector2(8, 16), "[特写占位] " + _ph_title, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, INK)
	for i in _zones.size():
		var r := _zone_rect(i)
		if _tex == null:
			draw_rect(r, INK, false, 1.0)
			draw_string(f, r.position + Vector2(3, 12), str(story.txt(_zones[i].get("label", {})) if story != null else ""),
				HORIZONTAL_ALIGNMENT_LEFT, r.size.x - 4, 10, INK)
		if i == _sel:
			draw_rect(r, HOT if fmod(_t, 1.2) < 0.9 else Color(HOT, 0.2))
	var lines: Array = _spec.get("lines", [])
	if not lines.is_empty():
		var at: Vector2 = _img_rect.position + Vector2(16, 24)
		var a = _spec.get("at", null)
		if a is Array and (a as Array).size() >= 2:
			at = _img_rect.position + Vector2(float(a[0]), float(a[1]))
		for i in lines.size():
			var tx: String = str(story.txt(lines[i])) if story != null else str(lines[i])
			draw_string(f, at + Vector2(0, i * 14), tx, HORIZONTAL_ALIGNMENT_LEFT, _img_rect.size.x - 24, 12, INK)
