extends Control
## 晨头顶的小气泡（剧本 say 带 "bark": true）：不锁人、不用按键，跟着晨走，几秒后自己淡掉；多句排队依次显示。
## story_runner.gd 建它（关卡 UI 层里，对话框下面），_say 碰到 bark 就 push 进来，不等。
## 让位：正经对话框 / 点选 / 菜单 / 通讯器 / 背包 / 设置开着时先藏起来、计时停住，关掉以后接着显示（不会被盖掉白念）。
## 停多久：1.6 秒 + 每个字 0.11 秒（最多 4.5 秒）；--story_auto 时减半；后面来了新的一句、这句已经看了 1.5 秒，就再 0.3 秒收。出现 / 消失各两格（100ms 一格）。

const BOX_BG := Color(0.02, 0.05, 0.04, 0.72)
const BOX_EDGE := Color(0.5, 0.6, 0.55, 0.3)
const MAX_W := 168.0                  # 正文最宽（12 个汉字）
const ADDED_C := Color("#8fb8e0")
const STEP := 0.1

var story: Node
var _queue: Array = []                # [{text, added}]
var _cur: Dictionary = {}
var _t := 0.0                         # 当前这句显示了多久
var _hold := 0.0
var _box: PanelContainer
var _label: Label
var _tail: Control


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme = UITheme.get_theme()
	_box = PanelContainer.new()
	_box.add_theme_stylebox_override("panel", UITheme.box(BOX_BG, BOX_EDGE, 1, Vector4(5, 2, 5, 3)))
	_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_box.visible = false
	_label = Label.new()
	_label.add_theme_font_size_override("font_size", 14)
	_label.add_theme_constant_override("line_spacing", 2)
	_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_box.add_child(_label)
	add_child(_box)
	_tail = Control.new()
	_tail.size = Vector2(5, 3)
	_tail.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tail.draw.connect(_draw_tail)
	_tail.visible = false
	add_child(_tail)


func push(text: String, added := false) -> void:
	if text == "":
		return
	_queue.append({"text": text, "added": added})
	# 新的一句来了：当前这句已经看了 1.5 秒以上就早点收（台词跟着动作走，不越积越晚）
	if not _cur.is_empty() and _t > 1.5:
		_hold = minf(_hold, _t + 0.3)


func clear() -> void:
	_queue.clear()
	_cur = {}
	_box.visible = false
	_tail.visible = false


func busy() -> bool:
	return not _cur.is_empty() or not _queue.is_empty()


func _paused() -> bool:
	if story == null:
		return true
	var d = story.dlg
	if d.is_open() or d.picking() or d.menu_open():
		return true
	if story.phone != null and story.phone.is_open():
		return true
	var lv = story.level
	for n in ["_bag", "_settings"]:
		var p = lv.get(n) if lv != null else null
		if p is CanvasItem and (p as CanvasItem).visible:
			return true
	return false


func _process(delta: float) -> void:
	if _cur.is_empty():
		if _queue.is_empty():
			return
		_cur = _queue.pop_front()
		_t = 0.0
		var s := str(_cur["text"])
		_hold = minf(4.5, 1.6 + 0.11 * s.length())
		if story != null and str(story.auto) != "":
			_hold *= 0.5
		_label.text = s
		_label.add_theme_color_override("font_color", ADDED_C if _cur["added"] else UITheme.TEXT)
		var w := 0.0
		for line in s.split("\n"):
			w = maxf(w, UITheme.font().get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x)
		if w > MAX_W:
			_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			_label.custom_minimum_size = Vector2(MAX_W, 0)
		else:
			_label.autowrap_mode = TextServer.AUTOWRAP_OFF
			_label.custom_minimum_size = Vector2.ZERO
		_box.size = Vector2.ZERO
		_box.reset_size()
	if _paused():
		_box.visible = false
		_tail.visible = false
		return
	_t += delta
	# 两格淡入、两格淡出（100ms 一格）
	var a := 1.0
	if _t < STEP:
		a = 0.4
	elif _t < STEP * 2.0:
		a = 0.75
	elif _t > _hold - STEP:
		a = 0.4
	elif _t > _hold - STEP * 2.0:
		a = 0.75
	if _t >= _hold:
		_cur = {}
		_box.visible = false
		_tail.visible = false
		return
	_box.visible = true
	_box.modulate.a = a
	_tail.modulate.a = a
	_place()


func _place() -> void:
	var p: Vector2 = story._anchor("chen") if story != null else Vector2(240, 120)
	var sz := _box.size
	var top: float = float(story.dlg.top_limit) if story != null else 4.0
	var x := clampf(roundf(p.x - sz.x / 2.0), 6.0, 474.0 - sz.x)
	var y := clampf(roundf(p.y - 5.0 - sz.y), top, 230.0 - sz.y)
	_box.position = Vector2(x, y)
	_tail.position = Vector2(clampf(roundf(p.x) - 2.0, x + 3.0, x + sz.x - 8.0), y + sz.y)
	_tail.visible = p.y - 5.0 >= y + sz.y - 1.0


func _draw_tail() -> void:
	var rows := [5, 3, 1]
	for i in rows.size():
		var w: int = rows[i]
		var x0: int = (5 - w) / 2
		_tail.draw_rect(Rect2(x0, i, w, 1), BOX_BG)
		_tail.draw_rect(Rect2(x0, i, 1, 1), BOX_EDGE)
		_tail.draw_rect(Rect2(x0 + w - 1, i, 1, 1), BOX_EDGE)
