extends "res://scripts/side_kit.gd"
## 河流篇的面板小游戏（river_valve / river_borrowed / river_thread / river_guestbook / river_cook）共用的底子。
##   和第一关支线一样：房间压暗、正中一块特写面板、对话框盖在面板上面、按键提示在面板上面一行（overlay_layout.gd）。
##   面板不用另画的图：这里用色块直接画（河流篇的配色：夜里的河 = 深青、木框 = 旧船板、黄灯 = 暖色）。
## 子类照 side_kit 的写法：自己写 run / auto / ff / check 和 _tick / _draw_board / _press。
## 规矩（作者 11-04「第二关的小游戏和支线都不如第一关有趣」）：每个都 ≤ 60 秒、做不好不会输（失败几次自己放水）、
##   水下的不说话、晨不说话（只在选项里开口），笑点放在画面上的字和妮芙 / 别人的一句。
## 剧本步骤里的字（标签、字幕）都是 {"zh", "en"}；台词走 lines.<key>（剧本步骤，播的时候对话框盖在面板上）。

const RIVER_DEEP := Color("#0b1f24")
const RIVER_MID := Color("#123238")
const RIVER_LIT := Color("#2b5a5c")
const FRAME_DARK := Color("#1a120c")
const FRAME := Color("#5b3f28")
const FRAME_LIT := Color("#7c5a3a")
const IRON := Color("#3a4244")
const IRON_LIT := Color("#66706e")
const PAPER := Color("#d8cfb4")
const PAPER_DIM := Color("#a89f86")
const INK := Color("#2a2620")
const LAMP := Color("#e8b860")
const SOFT := Color("#a9d8bc")
const BAD := Color("#d0705a")


## 面板底：外圈深色、木框两档、里面按 top → bottom 分 4 条色带（像素画，不做平滑渐变）
func _panel_bg(b: Control, top: Color, bottom: Color, inset := 4.0) -> void:
	var r := Rect2(Vector2.ZERO, panel)
	b.draw_rect(r, FRAME_DARK)
	b.draw_rect(r.grow(-1), FRAME)
	b.draw_rect(Rect2(1, 1, panel.x - 2, 1), FRAME_LIT)
	b.draw_rect(Rect2(1, 1, 1, panel.y - 2), FRAME_LIT)
	var inner := r.grow(-inset)
	b.draw_rect(inner.grow(1), FRAME_DARK)
	var bands := 4
	for i in bands:
		var h := inner.size.y / bands
		b.draw_rect(Rect2(inner.position.x, inner.position.y + i * h, inner.size.x, ceilf(h)), top.lerp(bottom, float(i) / (bands - 1)))


## 像素圆（实心）：一行一行画，边缘不糊
func _disc(b: Control, c: Vector2, r: float, col: Color) -> void:
	var ri := int(ceilf(r))
	for dy in range(-ri, ri + 1):
		var w := floorf(sqrt(maxf(0.0, r * r - dy * dy)))
		if w <= 0.0 and dy != 0:
			continue
		b.draw_rect(Rect2(roundf(c.x - w), roundf(c.y + dy), w * 2.0 + 1.0, 1), col)


## 像素圆环
func _ring(b: Control, c: Vector2, r: float, col: Color, steps := 0) -> void:
	var n := steps if steps > 0 else int(maxf(12.0, r * 6.0))
	for i in n:
		var a := TAU * i / n
		b.draw_rect(Rect2((c + Vector2(cos(a), sin(a)) * r).round(), Vector2(1, 1)), col)


## 粗一点的线（像素）：两端之间每隔 1 像素点一个方块
func _line(b: Control, p0: Vector2, p1: Vector2, col: Color, w := 1.0) -> void:
	var n := int(maxf(1.0, p0.distance_to(p1)))
	for i in n + 1:
		var q := p0.lerp(p1, float(i) / n)
		b.draw_rect(Rect2((q - Vector2(w, w) * 0.5).round(), Vector2(w, w)), col)


## 剧本里的 {"zh", "en"}（没写就用默认）
func _tr(d, fallback := "") -> String:
	if d is Dictionary:
		return I18n.pick(d)
	return str(d) if d != null else fallback


# ----------------------------------------------------------------------- 夜测：按键机器人（--mech_play）
## 自动玩（--story_auto）的时候加 --mech_play：小游戏不走 auto() 的快进直解，而是 run() 照常（玩家的速度），
##   由子类的 _bot_play() 按真实的按键去玩（还会故意错一次），面板、提示、台词都和玩家看到的一样。
var bot := false
var _bot_hold := false
var _bot_axis := 0


static func bot_on() -> bool:
	return "--mech_play" in OS.get_cmdline_user_args()


## auto() 里调：开了 --mech_play 就让机器人玩，返回 true；没开返回 false（照旧快进）
func _bot_start() -> bool:
	if not bot_on():
		return false
	bot = true
	auto_mode = false
	_bot_run()
	return true


func _bot_run() -> void:
	var tree := Engine.get_main_loop() as SceneTree
	while board == null:
		await tree.process_frame
	await _bot_play()
	_bot_hold = false
	_bot_axis = 0


## 子类覆盖：照玩家的节奏按键
func _bot_play() -> void:
	pass


## 合成一次按键，送进和玩家一样的输入处理（_on_input → _press）
func _bot_key(code: Key) -> void:
	if not _alive():
		return
	var e := InputEventKey.new()
	e.keycode = code
	e.pressed = true
	_on_input(e)


## 机器人等：等 sec 秒（面板没了就不等）
func _bot_wait(sec: float) -> void:
	if _alive():
		await board.get_tree().create_timer(sec).timeout


## 机器人等到能按（台词播完、面板收键）
func _bot_ready() -> void:
	while _alive() and not _accept:
		await board.get_tree().process_frame


## 按住：空格 / E / 回车 / Z / 鼠标左键（夜测机器人：_bot_hold）
func _holding() -> bool:
	if not _accept:
		return false
	if bot:
		return _bot_hold
	for k in [KEY_SPACE, KEY_E, KEY_ENTER, KEY_KP_ENTER, KEY_Z]:
		if Input.is_key_pressed(k):
			return true
	return Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)


## ← / A 为 -1，→ / D 为 +1，都没按 0
func _axis() -> int:
	if not _accept:
		return 0
	if bot:
		return _bot_axis
	var d := 0
	if Input.is_key_pressed(KEY_LEFT) or Input.is_key_pressed(KEY_A):
		d -= 1
	if Input.is_key_pressed(KEY_RIGHT) or Input.is_key_pressed(KEY_D):
		d += 1
	return d


static func is_left(e: InputEvent) -> bool:
	return e is InputEventKey and e.is_pressed() and not e.is_echo() and (e as InputEventKey).keycode in [KEY_LEFT, KEY_A]


static func is_right(e: InputEvent) -> bool:
	return e is InputEventKey and e.is_pressed() and not e.is_echo() and (e as InputEventKey).keycode in [KEY_RIGHT, KEY_D]


static func is_ok(e: InputEvent) -> bool:
	return (is_ok_key(e) and e.is_pressed() and not e.is_echo()) or (is_click(e) and e.is_pressed())


## 面板里正中一行字（带底色，压在画面上也看得清）：说明 / 字幕
func _caption(b: Control, y: float, t: String, col: Color, a := 1.0) -> void:
	if t == "" or a <= 0.01:
		return
	var f := UITheme.font()
	var w := f.get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
	var r := Rect2(roundf((panel.x - w) / 2.0) - 4.0, y - 12.0, w + 8.0, 16.0)
	b.draw_rect(r, Color(0.03, 0.05, 0.05, 0.78 * a))
	_text(b, Vector2(0, y), t, Color(col.r, col.g, col.b, col.a * a))


## 带 --story_shots 跑的时候，玩到一半存一张（delay 秒以后）
func _shot(kind: String, delay := 0.6) -> void:
	if story != null and story.has_method("_ui_shot"):
		story._ui_shot(kind, delay)


## 播剧本步骤（小游戏做完以后剧本给东西的那几步：on_head / on_seal 这种）
func _run(steps) -> void:
	if steps is Array and not (steps as Array).is_empty() and story != null:
		await story.run_steps(steps)
