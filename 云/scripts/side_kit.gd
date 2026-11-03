extends RefCounted
## 第一关支线小游戏（side-a：side_pine / side_radio / side_sign / side_lamp）的共用底子：照 ship_repair.gd 的做法，
##   房间压暗、正中一块特写面板（art/forest_side/，tools/forest_side_art.py 画的，1 倍像素、正面平视），对话框盖在面板上面。
## 子类 extends "res://scripts/side_kit.gd"，自己写 run / auto / ff / check 和下面几个钩子：
##   _tick(dt)          每帧（面板的 _process）
##   _draw_board(b)     画面板（b = 面板那个 Control，坐标 = 面板里的像素）
##   _press(e) -> bool  输入（已经过滤掉设置 / 背包开着、Esc、F8）；返回 true = 吃掉
## 共用的进度：story.mech_load(ID) 里至少有 {enter, fails, done}；第 ENTER_GIVE 次进、或失败 FAILS_GIVE 次 → 放水（give）。
## 做不好也不会输（作者的规矩）：失败几次以后小游戏自己做完给玩家看。

const KIT := preload("res://scripts/river_explore_order.gd")
const ART := "res://art/forest_side/"
const SFX_DIR := "res://audio/sfx/"
const DIM := Color(0.02, 0.03, 0.03, 0.72)
const FAILS_GIVE := 3
const ENTER_GIVE := 3

signal _stage(kind: String)

var ID := ""
var auto_mode := false
var tried := {}
var story: Node
var level: Node
var step: Dictionary
var s: Dictionary
var board: Control
var panel := Vector2(232, 150)
var panel_pos := Vector2(124, 66)
var _root: Control
var _dim: ColorRect
var _hint: Label
var _layer: CanvasLayer
var _accept := false
var _t := 0.0
var _tex := {}


# ----------------------------------------------------------------------- 进度
## 读进度、enter + 1、存回去；返回这一次要不要放水
func _enter(fresh: Dictionary) -> bool:
	s = story.mech_load(ID)
	if not (s.has("enter") and s.has("fails")):
		var e0 := int(s.get("enter", 0))
		s = fresh.duplicate(true)
		s["enter"] = e0
		s["fails"] = 0
		s["done"] = false
	s["enter"] = int(s["enter"]) + 1
	_save()
	var give := int(s["enter"]) >= ENTER_GIVE or int(s["fails"]) >= FAILS_GIVE
	print("MECH %s enter=%d fails=%d give=%s" % [ID, int(s["enter"]), int(s["fails"]), give])
	return give


func _save() -> void:
	story.mech_save(ID, s)


func _fail() -> bool:
	s["fails"] = int(s["fails"]) + 1
	_save()
	return int(s["fails"]) >= FAILS_GIVE


func _done() -> void:
	s["done"] = true
	_save()
	for f in step.get("sets", []):
		StoryState.set_flag(str(f))
	print("MECH %s done enter=%d fails=%d" % [ID, int(s["enter"]), int(s["fails"])])


## 跳节拍：做完了（同步、不演）
func _ff_save(r: Node, st: Dictionary, extra := {}) -> void:
	var t := {"enter": 1, "fails": 0, "done": true}
	t.merge(extra, true)
	r.mech_save(ID, t)
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))


func _check_lines(r: Node, st: Dictionary, keys: Array) -> Array:
	var out: Array = []
	for k in keys:
		if not KIT.has_lines(st, k):
			out.append("info: 没有 lines.%s" % k)
	for k in st.get("lines", {}):
		out.append_array(KIT.check_steps(r, "lines.%s" % k, st["lines"][k]))
	return out


# ----------------------------------------------------------------------- 搭画面
class Board extends Control:
	var m

	func _input(e: InputEvent) -> void:
		if m != null:
			m._on_input(e)

	func _process(dt: float) -> void:
		if m != null:
			m._t += dt
			m._tick(dt)
			queue_redraw()

	func _draw() -> void:
		if m != null:
			m._draw_board(self)


func _build(name: String, texs: Array) -> void:
	for k in texs:
		_tex[k] = _load_tex(ART + k + ".png")
	_root = Control.new()
	_root.name = name
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.size = Vector2(480, 270)
	var dlg = story.get("dlg")
	if dlg is Node and is_instance_valid(dlg) and dlg.get_parent() != null:
		var host: Node = dlg.get_parent()
		host.add_child(_root)
		host.move_child(_root, dlg.get_index())       # 对话框盖在面板上面
	else:
		_layer = CanvasLayer.new()
		_layer.layer = 50
		(level if level != null else story).add_child(_layer)
		_layer.add_child(_root)
	_dim = ColorRect.new()
	_dim.color = DIM
	_dim.size = Vector2(480, 270)
	_dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dim.modulate.a = 0.0
	_root.add_child(_dim)
	board = Board.new()
	board.m = self
	board.position = panel_pos
	board.size = panel
	board.clip_contents = true
	board.mouse_filter = Control.MOUSE_FILTER_IGNORE
	board.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	board.modulate.a = 0.0
	_root.add_child(board)
	_hint = Label.new()
	_hint.position = Vector2(0, panel_pos.y + panel.y + 4)
	_hint.size = Vector2(480, 16)
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint.add_theme_font_size_override("font_size", 14)
	_hint.add_theme_color_override("font_color", UITheme.TEXT)
	_hint.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))
	_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hint.modulate.a = 0.0
	_root.add_child(_hint)


## 图还没被编辑器导入（作者醒着不跑 --import）时直接读 png
static func _load_tex(p: String) -> Texture2D:
	if ResourceLoader.exists(p):
		return load(p)
	var img := Image.load_from_file(ProjectSettings.globalize_path(p))
	return ImageTexture.create_from_image(img) if img != null else null


func _k() -> float:
	return 0.25 if auto_mode else 1.0


func _alive() -> bool:
	return board != null and is_instance_valid(board) and board.is_inside_tree() and not story.ended


func _wait(sec: float) -> void:
	if _alive():
		await board.get_tree().create_timer(sec * _k()).timeout


func _frame() -> void:
	if _alive():
		await board.get_tree().process_frame


func _tw() -> Tween:
	return board.create_tween()


func _fade_in() -> void:
	var tw := _tw().set_parallel(true)
	tw.tween_property(_dim, "modulate:a", 1.0, 0.45 * _k()).set_trans(Tween.TRANS_SINE)
	tw.tween_property(board, "modulate:a", 1.0, 0.4 * _k()).set_trans(Tween.TRANS_SINE).set_delay(0.1 * _k())
	board.position.y = panel_pos.y + 10
	tw.tween_property(board, "position:y", panel_pos.y, 0.5 * _k()).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT).set_delay(0.1 * _k())
	await tw.finished


func _fade_out() -> void:
	if not _alive():
		_drop()
		return
	var tw := _tw().set_parallel(true)
	tw.tween_property(_hint, "modulate:a", 0.0, 0.3 * _k())
	tw.tween_property(board, "modulate:a", 0.0, 0.45 * _k()).set_trans(Tween.TRANS_SINE)
	tw.tween_property(board, "position:y", panel_pos.y + 8, 0.5 * _k()).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	tw.tween_property(_dim, "modulate:a", 0.0, 0.6 * _k()).set_trans(Tween.TRANS_SINE).set_delay(0.15 * _k())
	await tw.finished
	_drop()


func _drop() -> void:
	if board != null and is_instance_valid(board):
		board.m = null
	if _layer != null and is_instance_valid(_layer):
		_layer.queue_free()
	elif _root != null and is_instance_valid(_root):
		_root.queue_free()


func _set_hint(d: Dictionary) -> void:
	if _hint == null or not _alive() or (d.is_empty() and _hint.modulate.a <= 0.01):
		return
	var tw := _tw()
	if _hint.modulate.a > 0.01:
		tw.tween_property(_hint, "modulate:a", 0.0, 0.2)
	if not d.is_empty():
		tw.tween_callback(func(): _hint.text = I18n.pick(d))
		tw.tween_property(_hint, "modulate:a", 1.0, 0.35).set_trans(Tween.TRANS_SINE)


## lines[key] 那一串剧本步骤。里面的 choice 选中那句带 scene 的：接着把那个 scene 播掉（对方的反应），
## 还在小游戏里，播完回来。返回选中的那个 scene 名（小游戏按它分支，比如路标跟着跳）
func _lines(key: String) -> String:
	if not KIT.has_lines(step, key) or not _alive():
		return ""
	var arr = step["lines"][key]
	if not arr is Array or arr.is_empty():
		return ""
	var to := str(await story.run_steps(arr))
	var first := to
	var sc = story.get("scenes")
	var n := 0
	while to != "" and sc is Dictionary and (sc as Dictionary).has(to) and n < 6 and _alive():
		to = str(await story.run_steps(sc[to]))
		n += 1
	return first


# ----------------------------------------------------------------------- 音效（面板是界面：不分左右远近）
func _sfx(name: String, db := 0.0, pitch := 1.0) -> AudioStreamPlayer:
	if story.ff or not _alive():
		return null
	var stream: AudioStream = null
	for ext in [".wav", ".ogg"]:
		if ResourceLoader.exists(SFX_DIR + name + ext):
			stream = load(SFX_DIR + name + ext)
			break
	if stream == null and FileAccess.file_exists(SFX_DIR + name + ".wav"):
		stream = AudioStreamWAV.load_from_file(ProjectSettings.globalize_path(SFX_DIR + name + ".wav"))   # 新音效还没导入
	if stream == null:
		return null
	var a := AudioStreamPlayer.new()
	a.stream = stream
	if AudioServer.get_bus_index("SFX") >= 0:
		a.bus = "SFX"
	a.volume_db = db
	a.pitch_scale = pitch
	_root.add_child(a)
	a.play()
	a.finished.connect(a.queue_free)
	return a


## 循环的声音（收音机的沙沙声）：播完自己再来，音量由调用的人改
func _loop(name: String, db := 0.0) -> AudioStreamPlayer:
	var a := _sfx(name, db)
	if a != null:
		a.finished.disconnect(a.queue_free)
		a.finished.connect(a.play)
	return a


# ----------------------------------------------------------------------- 输入
func _on_input(e: InputEvent) -> void:
	if not _accept or not _alive():
		return
	for n in ["_settings", "_bag"]:
		var pnl = level.get(n) if level != null else null
		if pnl is CanvasItem and (pnl as CanvasItem).visible:
			return
	if e is InputEventKey and ((e as InputEventKey).keycode == KEY_ESCAPE or (e as InputEventKey).keycode == KEY_F8):
		return                                         # Esc 照常开设置
	if _press(e) or e is InputEventMouse or e is InputEventKey:
		board.get_viewport().set_input_as_handled()


func _mouse() -> Vector2:
	return board.get_local_mouse_position()


static func is_ok_key(e: InputEvent) -> bool:
	return e is InputEventKey and (e as InputEventKey).keycode in [KEY_SPACE, KEY_E, KEY_ENTER, KEY_KP_ENTER, KEY_Z]


static func is_click(e: InputEvent) -> bool:
	return e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT


# ----------------------------------------------------------------------- 钩子（子类覆盖）
func _tick(_dt: float) -> void:
	pass


func _draw_board(_b: Control) -> void:
	pass


func _press(_e: InputEvent) -> bool:
	return false


# ----------------------------------------------------------------------- 画字（面板里的说明、收音机的字幕）
func _text(b: Control, at: Vector2, t: String, col: Color, w := -1.0, align := HORIZONTAL_ALIGNMENT_CENTER, size := 14) -> void:
	var f := UITheme.font()
	if w < 0:
		w = panel.x
	b.draw_string(f, at + Vector2(1, 1), t, align, w, size, Color(0, 0, 0, col.a * 0.55))
	b.draw_string(f, at, t, align, w, size, col)
