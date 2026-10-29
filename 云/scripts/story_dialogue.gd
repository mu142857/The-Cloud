extends Control
## 剧情的界面：说话人头顶的对话框、屏幕中下方的旁白小字、拿到东西的小提示、点选（递工具 / 听管道）、章节结束卡。
## story_runner.gd 建它（放在关卡 UI 层里），level_forest.gd 的 _input 在剧情播放时把按键 / 点击转给 handle_input。
##
## 对话框：名字 + 打字效果；按确认（空格 / 回车 / Z / E / 鼠标左键）：第一下补全打字，第二下下一句。
##   框跟着说话人头顶（anchor 每帧给屏幕坐标），框下面一个小尖角指着说话人；出屏幕就贴边。
##   文字宽过 MAX_W 就自动换行（中文一个字 14 像素 = 一格，MAX_W 是 14 的倍数，不会半个字出框）。
##   打完以后右下角一个很小的三角慢慢闪：可以按了。
## 自动（--story_auto）：auto_delay 秒以后自己补全并下一句。instant = true（跳节拍）时什么都不显示、立刻返回。
## 补写台词（剧本 "added": true）：正文用柔和的蓝色 ADDED_C（say 的 added 参数，story_runner 按 mark_added 决定）。
## murmur：晨小声自言自语（不锁人、不用按键，几秒后自己消失；真的对话一来就让位）。
## 点选：选中的物件亮一档、上下浮 1 像素、头顶显示名字；←/→ 换的时候一声轻响（sfx）；确认后它闪一下 + 一声确认音，
##   停一小会儿再往下播。鼠标点到哪个选哪个，点在别处 = 确认现在选中的那个（键盘 E / 空格 / 回车 / Z 一样）。
## 屏幕边上的小箭头（edge_arrow）：主线下一个地方在屏幕外时指过去（level_forest.gd 每帧给）。
## 菜单（第三 / 四版）：
##   choose_item(物品, 「只是看看」) —— 道具选择条：屏幕下方一排背包物品的图标 + 最后一格「只是看看」；选中的那格亮边、
##     图标上下浮 1 像素、上面显示名字。返回物品 id，选「只是看看」/ Esc 返回 ""。
##   choose_line(几句话) —— 对话选项：屏幕下方列出晨的 2~3 个回答，选中的那句亮、前面一个小三角。返回第几句。
##   两个都是：←/→ 或 ↑/↓ 换（轻响），E / 空格 / 回车 / Z / 鼠标点 确定（确认音 + 闪一下）。自动玩时 auto_i 那个。

signal advanced
signal picked(i: int)
signal menu_done(i: int)

const MAX_W := 196.0                 # 正文最宽（14 个汉字）
const CPS_ZH := 14.0
const CPS_EN := 30.0
const BOX_BG := Color(0.02, 0.05, 0.04, 0.78)
const BOX_EDGE := Color(0.5, 0.6, 0.55, 0.35)
const NARR_Y := 206.0
const HINT_TEX := preload("res://art/level1/hint_arrow.png")
const ADDED_C := Color("#8fb8e0")       # 补写台词的蓝
const MURMUR_TIME := 3.5

var auto_delay := -1.0               # >= 0：自动推进（每句停这么久）
var sfx: Callable                    # func(name, db, pitch)：选择 / 确认的声音（level_forest._sfx）
var _murmur_t := 0.0
# 菜单（道具选择条 / 对话选项）
var _menu_kind := ""                 # "" / "items" / "lines"
var _menu_opts: Array = []           # items：[{id, icon, name}]（最后一个 id = "" 是「只是看看」）；lines：[String]
var _menu_sel := 0
var _menu_age := 0.0
var _menu_auto := -1
var _menu_done := false
var _menu_root: Control
var _menu_items: Array[Control] = []
var _menu_name: Label
var _edge: Control
var _edge_side := 0
var _edge_a := 0.0
var instant := false
var top_limit := 4.0                 # 框最高到哪（黑边在的时候往下挪）

var _box: PanelContainer
var _name: Label
var _text: Label
var _tail: Control
var _more: ColorRect
var _anchor: Callable
var _typing := false
var _chars := 0.0
var _cps := 14.0
var _open := false                   # 在等确认
var _age := 0.0
var _narr: Label
var _narr_t := 0.0
var _narr_wait := false
var _toast: HBoxContainer
var _toast_icon: TextureRect
var _toast_label: Label
var _toast_tw: Tween
# 点选
var _pick_on := false
var _pick_opts: Array = []           # [{label, rect: Callable → Rect2（屏幕坐标，空 = 没有物件）}]
var _pick_sel := 0
var _pick_age := 0.0
var _pick_auto := -1
var _pick_arrow: TextureRect
var _pick_label: Label
var _pick_row: HBoxContainer
var _pick_btns: Array[Button] = []
# 结束卡
var _end: Control
var _t := 0.0


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme = UITheme.get_theme()
	_box = PanelContainer.new()
	_box.add_theme_stylebox_override("panel", UITheme.box(BOX_BG, BOX_EDGE, 1, Vector4(7, 4, 7, 5)))
	_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_box.visible = false
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 2)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_box.add_child(v)
	_name = _mk_label(UITheme.ACCENT)
	v.add_child(_name)
	_text = _mk_label(UITheme.TEXT)
	_text.add_theme_constant_override("line_spacing", 2)
	_text.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING     # 打字时不重新排版（行不跳）
	v.add_child(_text)
	add_child(_box)
	_more = ColorRect.new()
	_more.size = Vector2(3, 1)
	_more.color = UITheme.TEXT_DIM
	_more.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_more)
	_more.visible = false
	_tail = Control.new()
	_tail.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tail.draw.connect(_draw_tail)
	_tail.size = Vector2(5, 3)
	add_child(_tail)
	_tail.visible = false

	_narr = _mk_label(Color("#c5d3ca"))
	_narr.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_narr.size = Vector2(480, 16)
	_narr.position = Vector2(0, NARR_Y)
	_narr.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.8))
	_narr.add_theme_constant_override("shadow_offset_x", 0)
	_narr.add_theme_constant_override("shadow_offset_y", 1)
	_narr.modulate.a = 0.0
	add_child(_narr)

	_toast = HBoxContainer.new()
	_toast.add_theme_constant_override("separation", 4)
	_toast.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_toast.modulate.a = 0.0
	_toast_icon = TextureRect.new()
	_toast_icon.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
	_toast_icon.custom_minimum_size = Vector2(16, 16)
	_toast_icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_toast.add_child(_toast_icon)
	_toast_label = _mk_label(UITheme.TEXT)
	_toast.add_child(_toast_label)
	add_child(_toast)

	_pick_arrow = TextureRect.new()
	_pick_arrow.texture = HINT_TEX
	_pick_arrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_pick_arrow.visible = false
	add_child(_pick_arrow)
	_pick_label = _mk_label(UITheme.TEXT)
	_pick_label.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.8))
	_pick_label.add_theme_constant_override("shadow_offset_x", 0)
	_pick_label.add_theme_constant_override("shadow_offset_y", 1)
	_pick_label.visible = false
	add_child(_pick_label)
	_pick_row = HBoxContainer.new()
	_pick_row.add_theme_constant_override("separation", 6)
	_pick_row.visible = false
	add_child(_pick_row)


func _mk_label(c: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", 14)
	l.add_theme_color_override("font_color", c)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


# ======================================================================= 对话
## 说一句：等到玩家按确认（第二下）才返回。anchor：func() -> Vector2，说话人头顶的屏幕坐标。
func say(who_name: String, name_color: Color, text: String, anchor: Callable, added := false) -> void:
	if instant:
		return
	_murmur_t = 0.0
	_show_line(who_name, name_color, text, anchor, added)
	_typing = true
	_open = true
	_age = 0.0
	await advanced


## 小声自言自语：不等按键，几秒后自己消失；正在对话时不说
func murmur(who_name: String, name_color: Color, text: String, anchor: Callable, added := false) -> void:
	if instant or _open or _pick_on:
		return
	_show_line(who_name, name_color, text, anchor, added)
	_typing = true
	_murmur_t = MURMUR_TIME
	_age = 0.0


func _show_line(who_name: String, name_color: Color, text: String, anchor: Callable, added: bool) -> void:
	_anchor = anchor
	_text.add_theme_color_override("font_color", ADDED_C if added else UITheme.TEXT)
	_name.text = who_name
	_name.visible = who_name != ""
	_name.add_theme_color_override("font_color", name_color)
	_text.text = text
	# 宽度：一行放得下就按字宽，放不下就固定 MAX_W 自动换行
	var w := 0.0
	for line in text.split("\n"):
		w = maxf(w, UITheme.font().get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x)
	if w > MAX_W:
		_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_text.custom_minimum_size = Vector2(MAX_W, 0)
	else:
		_text.autowrap_mode = TextServer.AUTOWRAP_OFF
		_text.custom_minimum_size = Vector2.ZERO
	_text.visible_characters = 0
	_chars = 0.0
	_cps = CPS_ZH if I18n.is_zh() else CPS_EN
	_box.visible = true
	_tail.visible = true
	_more.visible = false
	_box.size = Vector2.ZERO
	_box.reset_size()
	_box.modulate.a = 0.0
	create_tween().tween_property(_box, "modulate:a", 1.0, 0.15)
	_place_box()


func close_box() -> void:
	_open = false
	_box.visible = false
	_tail.visible = false
	_more.visible = false


func is_open() -> bool:
	return _open or _narr_wait


func is_typing() -> bool:
	return _typing


## 确认键 / 点击：在打字就补全，打完了就下一句
func confirm() -> bool:
	if _closeup_wait:
		_closeup_wait = false
		return true
	if _pick_on:
		_pick_choose(_pick_sel)
		return true
	if _murmur_t > 0.0 and not _open:
		return false
	if not _open:
		if _narr_wait:
			_narr_wait = false
			return true
		return false
	if _typing:
		_typing = false
		_text.visible_characters = -1
		return true
	_open = false
	_box.visible = false
	_tail.visible = false
	_more.visible = false
	advanced.emit()
	return true


func _place_box() -> void:
	_box.reset_size()
	var a: Vector2 = _anchor.call() if _anchor.is_valid() else Vector2(240, 60)
	var sz := _box.size
	var x := clampf(round(a.x - sz.x / 2.0), 6.0, 474.0 - sz.x)
	var y := roundf(a.y - 5.0 - sz.y)
	y = clampf(y, top_limit, 230.0 - sz.y)
	_box.position = Vector2(x, y)
	# 小尖角：框下沿、对着说话人（框贴边时尖角还在框里）
	var tx := clampf(round(a.x) - 2.0, x + 3.0, x + sz.x - 8.0)
	_tail.position = Vector2(tx, y + sz.y)
	_tail.visible = _box.visible and a.y - 5.0 >= y + sz.y - 1.0
	_more.position = Vector2(x + sz.x - 8.0, y + sz.y - 4.0)


func _draw_tail() -> void:
	# 5×3 的像素尖角，挂在框下沿：5、3、1，两边一格框边色
	var rows := [5, 3, 1]
	for i in rows.size():
		var w: int = rows[i]
		var x0: int = (5 - w) / 2
		_tail.draw_rect(Rect2(x0, i, w, 1), BOX_BG)
		_tail.draw_rect(Rect2(x0, i, 1, 1), BOX_EDGE)
		_tail.draw_rect(Rect2(x0 + w - 1, i, 1, 1), BOX_EDGE)


# ======================================================================= 旁白 / 小提示
## 屏幕中下方一行小字。停 hold 秒（或按确认）就返回；字自己再留一会儿慢慢淡掉。
func narr(text: String, hold: float) -> void:
	if instant:
		return
	_narr.text = text
	_narr.modulate.a = 0.0
	_narr_t = hold + 2.2
	var tw := create_tween()
	tw.tween_property(_narr, "modulate:a", 1.0, 0.35)
	_narr_wait = true
	var t := 0.0
	var limit := hold if auto_delay < 0.0 else minf(hold, auto_delay + 0.2)
	while _narr_wait and t < limit:
		await get_tree().process_frame
		t += get_process_delta_time()
	_narr_wait = false


func toast(icon: Texture2D, text: String) -> void:
	if instant:
		return
	_toast_icon.texture = icon
	_toast_icon.visible = icon != null
	_toast_label.text = text
	_toast.reset_size()
	var w := UITheme.font().get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x + (20.0 if icon != null else 0.0)
	_toast.position = Vector2(round(240.0 - w / 2.0), NARR_Y + 18.0)
	if _toast_tw != null and _toast_tw.is_valid():
		_toast_tw.kill()
	_toast_tw = create_tween()
	_toast_tw.tween_property(_toast, "modulate:a", 1.0, 0.25)
	_toast_tw.tween_interval(1.8)
	_toast_tw.tween_property(_toast, "modulate:a", 0.0, 0.6)


# ======================================================================= 点选
## options：[{label: String, rect: Callable（→ 屏幕 Rect2；Rect2() = 场景里没有这个物件）, node: Sprite2D 或 null}]。返回选了第几个。
## auto_pick >= 0：自动玩时过一会儿自己选它。
func pick(options: Array, auto_pick := -1) -> int:
	if instant:
		return maxi(0, auto_pick)
	_pick_opts = options
	_pick_sel = 0
	_pick_age = 0.0
	_pick_auto = auto_pick
	_pick_on = true
	var all_in_scene := true
	for o in options:
		var r: Rect2 = (o["rect"] as Callable).call()
		if r.size == Vector2.ZERO:
			all_in_scene = false
	for b in _pick_btns:
		b.queue_free()
	_pick_btns.clear()
	_pick_row.visible = not all_in_scene
	if not all_in_scene:
		# 场景里没有这些物件：下面一排按钮
		for i in options.size():
			var b := Button.new()
			b.text = str(options[i]["label"])
			b.focus_mode = Control.FOCUS_NONE
			b.pressed.connect(_pick_choose.bind(i))
			b.mouse_entered.connect(func(): _pick_sel = i)
			_pick_row.add_child(b)
			_pick_btns.append(b)
		_pick_row.reset_size()
	var i: int = await picked
	return i


var _pick_done := false


func _set_sel(i: int) -> void:
	if i == _pick_sel:
		return
	_pick_sel = i
	if sfx.is_valid():
		sfx.call("ui_click", -14.0, 1.35)


func _pick_choose(i: int) -> void:
	if not _pick_on or _pick_done:
		return
	_pick_done = true
	_pick_sel = i
	if sfx.is_valid():
		sfx.call("tick", -5.0, 1.0)
	# 选中的那个闪一下，停一小会儿再往下
	var n: Sprite2D = _pick_opts[i].get("node", null)
	if n != null and is_instance_valid(n):
		n.modulate = Color(1.9, 1.9, 1.9, n.modulate.a)
	await get_tree().create_timer(0.35).timeout
	_pick_restore()
	_pick_on = false
	_pick_done = false
	_pick_arrow.visible = false
	_pick_label.visible = false
	_pick_row.visible = false
	picked.emit(i)


## 选中的物件：亮一档、上下浮 1 像素；别的恢复
func _pick_light() -> void:
	for k in _pick_opts.size():
		var n: Sprite2D = _pick_opts[k].get("node", null)
		if n == null or not is_instance_valid(n):
			continue
		if not n.has_meta("pick_y"):
			n.set_meta("pick_y", n.position.y)
		var base_y: float = n.get_meta("pick_y")
		if k == _pick_sel:
			if not _pick_done:
				n.modulate = Color(1.4, 1.4, 1.4, n.modulate.a)
			n.position.y = base_y - (1.0 if fmod(_t, 0.8) < 0.4 else 0.0)
		else:
			n.modulate = Color(1, 1, 1, n.modulate.a)
			n.position.y = base_y


func _pick_restore() -> void:
	for o in _pick_opts:
		var n: Sprite2D = o.get("node", null)
		if n == null or not is_instance_valid(n):
			continue
		n.modulate = Color(1, 1, 1, n.modulate.a)
		if n.has_meta("pick_y"):
			n.position.y = n.get_meta("pick_y")
			n.remove_meta("pick_y")


func _update_pick(delta: float) -> void:
	_pick_age += delta
	if _pick_auto >= 0 and auto_delay >= 0.0:
		if _pick_age > 0.5:
			_set_sel(_pick_auto)
		if _pick_age > 1.0:
			_pick_choose(_pick_auto)
			return
	if _pick_row.visible:
		_pick_row.position = Vector2(round(240.0 - _pick_row.size.x / 2.0), NARR_Y - 4.0)
		for i in _pick_btns.size():
			_pick_btns[i].modulate = Color(1.25, 1.25, 1.25) if i == _pick_sel else Color(0.8, 0.8, 0.8)
		return
	_pick_light()
	var r: Rect2 = (_pick_opts[_pick_sel]["rect"] as Callable).call()
	var bob := 1.0 if fmod(_t, 1.0) < 0.5 else 0.0
	_pick_arrow.visible = true
	_pick_arrow.position = Vector2(round(r.get_center().x - 2.0), round(r.position.y - 6.0 - bob))
	var lbl := str(_pick_opts[_pick_sel]["label"])
	_pick_label.visible = lbl != ""
	if _pick_label.text != lbl:
		_pick_label.text = lbl
		_pick_label.reset_size()
	var w := UITheme.font().get_string_size(lbl, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
	_pick_label.position = Vector2(clampf(round(r.get_center().x - w / 2.0), 4.0, 476.0 - w), round(r.position.y - 26.0))


func picking() -> bool:
	return _pick_on


## 点选的判定框：最少 24×24
static func _grow_min(r: Rect2) -> Rect2:
	var c := r.get_center()
	var s := Vector2(maxf(r.size.x + 4.0, 24.0), maxf(r.size.y + 4.0, 24.0))
	return Rect2(c - s / 2.0, s)


# ======================================================================= 菜单：道具选择条 / 对话选项
func choose_item(items: Array, look_label: String, auto_i := -1) -> String:
	var opts: Array = items.duplicate()
	opts.append({"id": "", "icon": null, "name": look_label})
	if instant:
		return str(opts[clampi(auto_i, 0, opts.size() - 1)]["id"]) if auto_i >= 0 else ""
	_open_menu("items", opts, auto_i)
	var i: int = await menu_done
	return str(opts[i]["id"])


func choose_line(lines: Array, auto_i := -1) -> int:
	if instant:
		return maxi(0, auto_i)
	_open_menu("lines", lines, auto_i)
	var i: int = await menu_done
	return i


func menu_open() -> bool:
	return _menu_kind != ""


func _open_menu(kind: String, opts: Array, auto_i: int) -> void:
	_menu_kind = kind
	_menu_opts = opts
	_menu_sel = 0
	_menu_age = 0.0
	_menu_auto = auto_i
	_menu_done = false
	if _menu_root != null:
		_menu_root.queue_free()
	_menu_items.clear()
	_menu_root = Control.new()
	_menu_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_menu_root)
	_menu_name = _mk_label(UITheme.TEXT)
	_menu_name.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.8))
	_menu_name.add_theme_constant_override("shadow_offset_x", 0)
	_menu_name.add_theme_constant_override("shadow_offset_y", 1)
	_menu_root.add_child(_menu_name)
	if kind == "items":
		# 一排放不下就分几排（从下往上），「只是看看」在最后一排的最后
		var n := opts.size()
		var slot := 20.0
		var gap := 2.0
		var look_w := UITheme.font().get_string_size(str(opts[n - 1]["name"]), HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x + 10.0
		var per_row := maxi(1, int((460.0 - look_w) / (slot + gap)))
		var rows := int(ceil(float(n - 1) / per_row)) if n > 1 else 1
		var row_y := 224.0 - (rows - 1) * (slot + gap)
		var i := 0
		for r in rows:
			var cnt := mini(per_row, n - 1 - r * per_row)
			var last := r == rows - 1
			var total := cnt * (slot + gap) + (look_w if last else -gap)
			var x := roundf(240.0 - total / 2.0)
			var y := row_y + r * (slot + gap)
			var k := 0
			while k < cnt or (last and k == cnt):
				var is_look := last and k == cnt
				var idx := n - 1 if is_look else i
				var p := Panel.new()
				p.mouse_filter = Control.MOUSE_FILTER_IGNORE
				var w := look_w if is_look else slot
				p.position = Vector2(x, y)
				p.size = Vector2(w, slot)
				_menu_root.add_child(p)
				p.set_meta("idx", idx)
				x += w + gap
				k += 1
				if not is_look:
					i += 1
		# 按 opts 的顺序排好（导航、点击都按这个）
		var panels: Array = []
		for c in _menu_root.get_children():
			if c is Panel:
				panels.append(c)
		panels.sort_custom(func(a, b): return int(a.get_meta("idx")) < int(b.get_meta("idx")))
		for idx in n:
			var p: Panel = panels[idx]
			if idx < n - 1:
				var tr := TextureRect.new()
				tr.texture = opts[idx]["icon"]
				tr.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
				tr.set_anchors_preset(Control.PRESET_FULL_RECT)
				tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
				p.add_child(tr)
			else:
				var l := _mk_label(UITheme.TEXT_DIM)
				l.text = str(opts[idx]["name"])
				l.position = Vector2(5, 2)
				p.add_child(l)
			_menu_items.append(p)
	else:
		var y := 222.0 - (opts.size() - 1) * 18.0
		for i in opts.size():
			var l := _mk_label(UITheme.TEXT_DIM)
			l.text = "  " + str(opts[i])
			l.position = Vector2(120, y + i * 18.0)
			l.size = Vector2(320, 16)
			var bg := ColorRect.new()
			bg.color = Color(BOX_BG, 0.85)
			bg.position = l.position - Vector2(4, 1)
			bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
			var tw := UITheme.font().get_string_size(l.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
			bg.size = Vector2(tw + 12.0, 17)
			_menu_root.add_child(bg)
			_menu_root.add_child(l)
			_menu_items.append(l)
	_menu_style()


func _menu_style() -> void:
	for i in _menu_items.size():
		var on := i == _menu_sel
		if _menu_kind == "items":
			var p: Panel = _menu_items[i]
			p.add_theme_stylebox_override("panel", UITheme.box(Color(0.06, 0.1, 0.09, 0.9),
				UITheme.ACCENT if on else Color(0.3, 0.4, 0.35, 0.9), 1))
		else:
			var l: Label = _menu_items[i]
			var txt := str(_menu_opts[i])
			l.text = ("▸ " if on else "  ") + txt
			l.add_theme_color_override("font_color", UITheme.TEXT if on else UITheme.TEXT_DIM)
	if _menu_kind == "items":
		var o: Dictionary = _menu_opts[_menu_sel]
		_menu_name.text = str(o["name"])
		_menu_name.visible = str(o["id"]) != ""
		var p: Control = _menu_items[_menu_sel]
		var w := UITheme.font().get_string_size(_menu_name.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
		_menu_name.position = Vector2(clampf(round(p.position.x + p.size.x / 2.0 - w / 2.0), 4.0, 476.0 - w), p.position.y - 18.0)
	else:
		_menu_name.visible = false


func _menu_set(i: int) -> void:
	if i == _menu_sel:
		return
	_menu_sel = i
	_menu_style()
	if sfx.is_valid():
		sfx.call("ui_click", -14.0, 1.35)


func _menu_choose(i: int) -> void:
	if _menu_kind == "" or _menu_done:
		return
	_menu_done = true
	_menu_set(i)
	if sfx.is_valid():
		sfx.call("tick", -5.0, 1.0)
	var it: Control = _menu_items[i]
	it.modulate = Color(1.8, 1.8, 1.8)
	await get_tree().create_timer(0.3).timeout
	_menu_kind = ""
	if _menu_root != null:
		_menu_root.queue_free()
		_menu_root = null
	menu_done.emit(i)


func _menu_input(event: InputEvent) -> bool:
	var n := _menu_opts.size()
	if event is InputEventKey and event.pressed and not event.echo:
		var k: int = event.keycode
		if k in [KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_Z, KEY_E]:
			_menu_choose(_menu_sel)
		elif k in [KEY_LEFT, KEY_A, KEY_UP, KEY_W]:
			_menu_set((_menu_sel + n - 1) % n)
		elif k in [KEY_RIGHT, KEY_D, KEY_DOWN, KEY_S]:
			_menu_set((_menu_sel + 1) % n)
		elif k == KEY_ESCAPE and _menu_kind == "items":
			_menu_choose(n - 1)
		return true
	if event is InputEventMouseMotion:
		for i in _menu_items.size():
			if _menu_hit(i, event.position):
				_menu_set(i)
		return false
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		for i in _menu_items.size():
			if _menu_hit(i, event.position):
				_menu_choose(i)
				return true
		_menu_choose(_menu_sel)          # 点在别处 = 确定现在选中的那个
		return true
	return event is InputEventKey


func _menu_hit(i: int, p: Vector2) -> bool:
	var c: Control = _menu_items[i]
	return Rect2(c.position - Vector2(2, 2), c.size + Vector2(4, 4)).has_point(p)


# ======================================================================= 画的特写
var _closeup_wait := false


## 屏幕中间展开一张图（纸张展开：高度一档一档拉开，背景压暗），停 sec 秒或按确认提前收起
func closeup(tex: Texture2D, sec: float) -> void:
	if instant or tex == null:
		return
	var dim := ColorRect.new()
	dim.color = Color(0.0, 0.02, 0.01, 0.0)
	dim.size = Vector2(480, 270)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(dim)
	var k := maxi(1, mini(int(400.0 / tex.get_width()), int(220.0 / tex.get_height())))
	var full := tex.get_size() * k
	var tr := TextureRect.new()
	tr.texture = tex
	tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	tr.stretch_mode = TextureRect.STRETCH_SCALE
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(tr)
	var cy := 128.0
	var set_h := func(h: float):
		h = maxf(2.0, roundf(h / 2.0) * 2.0)
		tr.size = Vector2(full.x, h)
		tr.position = (Vector2(240.0 - full.x / 2.0, cy - h / 2.0)).round()
	set_h.call(2.0)
	create_tween().tween_property(dim, "color:a", 0.6, 0.3)
	if sfx.is_valid():
		sfx.call("page_turn", -6.0, 1.0)
	for i in 7:                                   # 展开：七档
		await get_tree().create_timer(0.05).timeout
		set_h.call(full.y * float(i + 1) / 7.0)
	_closeup_wait = true
	var t := 0.0
	while _closeup_wait and t < sec:
		await get_tree().process_frame
		t += get_process_delta_time()
	_closeup_wait = false
	for i in 5:                                   # 收起
		await get_tree().create_timer(0.04).timeout
		set_h.call(full.y * float(4 - i) / 5.0)
	var tw := create_tween()
	tw.tween_property(dim, "color:a", 0.0, 0.25)
	await tw.finished
	tr.queue_free()
	dim.queue_free()


# ======================================================================= 屏幕边上的引导箭头
## side：-1 左边、1 右边、0 不画；y：屏幕 y
func edge_arrow(side: int, y: float) -> void:
	if _edge == null:
		_edge = Control.new()
		_edge.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_edge.size = Vector2(5, 9)
		_edge.draw.connect(_draw_edge)
		add_child(_edge)
	if side != 0:
		if side != _edge_side:
			_edge_side = side
			_edge.queue_redraw()
		_edge.position = Vector2(5.0 if side < 0 else 470.0, round(clampf(y, 30.0, 230.0)))
	var want := 0.0 if side == 0 else 0.35 + 0.2 * sin(_t * 2.6)
	_edge_a = move_toward(_edge_a, want, get_process_delta_time() * 1.5)
	_edge.modulate.a = _edge_a
	_edge.visible = _edge_a > 0.01


func _draw_edge() -> void:
	# 5×9 的像素三角，指向屏幕外
	for i in 5:
		var h := 9 - i * 2
		var x := i if _edge_side > 0 else 4 - i
		_edge.draw_rect(Rect2(x, i, 1, h), Color(0.88, 0.95, 0.9, 1.0))


# ======================================================================= 输入（level_forest 在剧情播放时转过来）
func handle_input(event: InputEvent) -> bool:
	if _menu_kind != "":
		return _menu_input(event)
	var is_confirm := false
	if event is InputEventKey and event.pressed and not event.echo:
		var k: int = event.keycode
		if k in [KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_Z, KEY_E]:
			is_confirm = true
		elif _pick_on and not _pick_opts.is_empty() and k in [KEY_LEFT, KEY_A, KEY_UP]:
			_set_sel((_pick_sel + _pick_opts.size() - 1) % _pick_opts.size())
			return true
		elif _pick_on and not _pick_opts.is_empty() and k in [KEY_RIGHT, KEY_D, KEY_DOWN]:
			_set_sel((_pick_sel + 1) % _pick_opts.size())
			return true
	elif event is InputEventMouseMotion and _pick_on and not _pick_row.visible:
		for i in _pick_opts.size():
			var r: Rect2 = (_pick_opts[i]["rect"] as Callable).call()
			if _grow_min(r).has_point(event.position):
				_set_sel(i)
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if _pick_on:
			if _pick_row.visible:
				return false          # 按钮自己处理
			for i in _pick_opts.size():
				var r: Rect2 = (_pick_opts[i]["rect"] as Callable).call()
				if _grow_min(r).has_point(event.position):
					_pick_choose(i)
					return true
			_pick_choose(_pick_sel)       # 点在别处 = 确认现在选中的那个
			return true
		is_confirm = true
	if is_confirm:
		return confirm()
	return false


# ======================================================================= 结束卡
func end_card(main_text: String, sub_text: String, parent: Node) -> void:
	_end = Control.new()
	_end.set_anchors_preset(Control.PRESET_FULL_RECT)
	_end.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_end.theme = UITheme.get_theme()
	_end.modulate.a = 0.0
	var l := Label.new()
	l.text = main_text
	l.add_theme_font_size_override("font_size", 28)
	l.add_theme_color_override("font_color", Color("#b9cdc1"))
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.size = Vector2(480, 32)
	l.position = Vector2(0, 112)
	_end.add_child(l)
	var s := Label.new()
	s.text = sub_text
	s.add_theme_font_size_override("font_size", 14)
	s.add_theme_color_override("font_color", Color("#6f877b"))
	s.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	s.size = Vector2(480, 16)
	s.position = Vector2(0, 150)
	_end.add_child(s)
	parent.add_child(_end)
	create_tween().tween_property(_end, "modulate:a", 1.0, 2.0).set_trans(Tween.TRANS_SINE)


func _process(delta: float) -> void:
	_t += delta
	if _open:
		_age += delta
		if _typing:
			_chars += _cps * delta
			var total := _text.get_total_character_count()
			_text.visible_characters = mini(int(_chars), total)
			if _text.visible_characters >= total:
				_typing = false
				_text.visible_characters = -1
		_more.visible = _box.visible and not _typing and fmod(_t, 1.0) < 0.6
		if auto_delay >= 0.0 and _age >= auto_delay:
			if _typing:
				confirm()
			confirm()
		if _box.visible:
			_place_box()
	elif _murmur_t > 0.0:
		# 自言自语：打字、停一会儿、自己淡掉
		_murmur_t -= delta
		_chars += _cps * delta
		_text.visible_characters = mini(int(_chars), _text.get_total_character_count())
		if _box.visible:
			_place_box()
		_box.modulate.a = clampf(_murmur_t / 0.5, 0.0, 1.0)
		if _murmur_t <= 0.0:
			close_box()
	if _narr_t > 0.0:
		_narr_t -= delta
		if _narr_t <= 0.6:
			_narr.modulate.a = maxf(0.0, _narr_t / 0.6)
	if _pick_on:
		_update_pick(delta)
	if _menu_kind != "":
		_menu_age += delta
		if _menu_auto >= 0 and auto_delay >= 0.0 and not _menu_done:
			if _menu_age > 0.4:
				_menu_set(clampi(_menu_auto, 0, _menu_opts.size() - 1))
			if _menu_age > 0.8:
				_menu_choose(clampi(_menu_auto, 0, _menu_opts.size() - 1))
		if _menu_kind == "items" and not _menu_items.is_empty():
			# 选中的那格图标上下浮 1 像素
			for i in _menu_items.size():
				var p: Control = _menu_items[i]
				if p.get_child_count() > 0 and p.get_child(0) is TextureRect:
					(p.get_child(0) as Control).position.y = -1.0 if (i == _menu_sel and fmod(_t, 0.8) < 0.4) else 0.0
