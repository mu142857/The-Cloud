extends "res://scripts/river_kit.gd"
## 河流篇小游戏 river_cook：帮鼠妈看锅（可选支线：第一次在市集见到鼠妈的时候，11-04 新做）。
##   docs/剧情改动/第二章可玩性_设计.md 支线「鼠妈」。
##
## 画面：灶上一口大锅（侧面剖开看得见汤），汤里一直冒小泡；每隔一拍（BEAT 秒，有一点点快慢）汤面鼓起一个大泡「咕嘟」破掉。
##   锅上面吊着这次要放的东西（ingredients 里一样一样来），下面一行写着它叫什么。
## 怎么玩：在大泡破掉的那一下（前后 WINDOW 秒）按空格 / E / 点一下 = 放进去（扑通，汤面一圈涟漪），换下一样。
##   早了 / 晚了：东西在锅沿上弹一下又挂回去（lines.miss_1 只播第一次）。全放进去 = 做完。
##   大泡鼓起来之前，汤面先有一圈慢慢收紧的涟漪：看着它收到最小就按（不会听也看得出）。
## 放水：按错 FAILS_GIVE 次以后，什么时候按都算对（鼠妈：「行了行了，锅不挑。」= lines.give）。
##
## 剧本步骤：{"do": "mechanic", "id": "river_cook", "ingredients": [{zh, en, color?}…], "lines": {intro, miss_1, give, done}}
## 进度：{enter, fails, done}。

const POT := Rect2(56, 56, 120, 60)
const SURF_Y := 70.0
const BEAT := 1.25
const WINDOW := 0.2
const HINT := {"zh": "大泡「咕嘟」的那一下按空格，放进去", "en": "Press Space right as the big bubble pops"}

var ings: Array = []
var idx := 0
var _beat_t := 0.0
var _next := BEAT
var _pop_flash := 0.0
var _small: Array = []
var _splash := -1.0
var _bounce := -1.0
var _missed := 0
var _easy := false
var _steam: Array = []


func _init() -> void:
	ID = "river_cook"
	quit_ok = true
	panel = Vector2(232, 140)


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	level = lv
	step = st
	ings = st.get("ingredients", [{"zh": "河虾", "en": "River shrimp"}, {"zh": "一把葱", "en": "Scallions"}, {"zh": "一颗小石头", "en": "A small pebble"}])
	_easy = _enter({})
	_build("RiverCook", [])
	await _fade_in()
	await _lines("intro")
	if not _quit_req:
		_set_hint(step.get("hint", HINT))
		_shot("cook", 0.8)
		_accept = true
	while _alive() and idx < ings.size() and not _quit_req:
		if auto_mode and _phase_err() < 0.05:
			_drop_in()
		await _frame()
	_accept = false
	if not _alive():
		_drop()
		return
	if _quit_req:
		await _quit_out()
		return
	quit_ok = false
	await _wait(0.7)
	_done()
	_set_hint({})
	await _lines("done")
	await _fade_out()


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	_bot_start()                         # 夜测 --mech_play：照玩家的节奏按键玩（不快进）
	_qa_quit_start()
	await run(lv, w, r, st)


func ff(r: Node, st: Dictionary) -> void:
	_ff_save(r, st)


func check(r: Node, st: Dictionary) -> Array:
	var out := _check_lines(r, st, ["intro", "done"]) + _check_quit(r, st)
	for g in st.get("ingredients", []):
		if not g is Dictionary or str(g.get("zh", "")) == "" or str(g.get("en", "")) == "":
			out.append("ingredients：每样要有 zh / en：%s" % str(g))
	return out


## 离最近一次大泡破掉差多少秒（刚破 / 马上破都算近）
func _phase_err() -> float:
	return minf(_beat_t, absf(_next - _beat_t))


func _drop_in() -> void:
	if idx >= ings.size() or _splash >= 0.0:
		return
	idx += 1
	_splash = 0.0
	_sfx("splash_in", -8.0, 1.2)


func _press(e: InputEvent) -> bool:
	if not is_ok(e):
		return false
	if _splash >= 0.0 or _bounce >= 0.0:
		return true
	if _easy or _phase_err() <= WINDOW:
		_drop_in()
	else:
		_bounce = 0.0
		_sfx("pot_clang", -8.0)
		_missed += 1
		if _fail():
			_easy = true
			_run_lines_later("give")
		elif _missed == 1:
			_run_lines_later("miss_1")
	return true


## 按错时鼠妈的一句：不卡住每帧（播的时候先不收键）
func _run_lines_later(key: String) -> void:
	_accept = false
	await _lines(key)
	_accept = true


func _tick(dt: float) -> void:
	_beat_t += dt
	if _beat_t >= _next:
		_beat_t = 0.0
		_next = BEAT + randf_range(-0.12, 0.12)
		_pop_flash = 0.35
		_sfx("pot_bubble", -6.0, randf_range(0.9, 1.05))
	_pop_flash = maxf(0.0, _pop_flash - dt)
	if randf() < dt * 8.0:
		_small.append({"x": randf_range(POT.position.x + 8, POT.end.x - 8), "t": 0.0})
	for q in _small:
		q["t"] = float(q["t"]) + dt
	_small = _small.filter(func(q): return float(q["t"]) < 0.8)
	if randf() < dt * 3.0:
		_steam.append({"x": randf_range(POT.position.x + 10, POT.end.x - 10), "t": 0.0})
	for q in _steam:
		q["t"] = float(q["t"]) + dt
	_steam = _steam.filter(func(q): return float(q["t"]) < 1.4)
	if _splash >= 0.0:
		_splash += dt
		if _splash > 0.6:
			_splash = -1.0
	if _bounce >= 0.0:
		_bounce += dt
		if _bounce > 0.45:
			_bounce = -1.0


func _draw_board(b: Control) -> void:
	_panel_bg(b, Color("#3b2a20"), Color("#1e1611"))
	# 灶火
	for k in 6:
		var x := POT.position.x + 14 + k * 19
		var h := 6.0 + 3.0 * sin(_t * 9.0 + k * 1.7)
		b.draw_rect(Rect2(x, POT.end.y + 2, 6, h), Color("#d8743a"))
		b.draw_rect(Rect2(x + 1, POT.end.y + 2, 4, h * 0.55), Color("#f2c052"))
	# 锅（剖面）：圆底、两只耳朵，里面是汤
	var pot := PackedVector2Array([POT.position, Vector2(POT.end.x, POT.position.y), Vector2(POT.end.x, POT.end.y - 16),
		Vector2(POT.end.x - 10, POT.end.y - 4), Vector2(POT.end.x - 26, POT.end.y), Vector2(POT.position.x + 26, POT.end.y),
		Vector2(POT.position.x + 10, POT.end.y - 4), Vector2(POT.position.x, POT.end.y - 16)])
	var rim := PackedVector2Array()
	for q in pot:
		rim.append(q + (q - POT.get_center()).normalized() * 2.0)
	b.draw_colored_polygon(rim, FRAME_DARK)
	b.draw_colored_polygon(pot, IRON)
	for side in [-1.0, 1.0]:
		var ex := POT.position.x - 8.0 if side < 0.0 else POT.end.x + 2.0
		b.draw_rect(Rect2(ex, POT.position.y + 6, 6, 3), IRON_LIT)
		b.draw_rect(Rect2(ex + (0.0 if side < 0.0 else 3.0), POT.position.y + 6, 3, 8), IRON_LIT)
	var inner := PackedVector2Array()
	for q in pot:
		inner.append(POT.get_center() + (q - POT.get_center()) * 0.9)
	var soup_poly := PackedVector2Array()
	for q in inner:
		soup_poly.append(Vector2(q.x, maxf(q.y, SURF_Y)))
	b.draw_colored_polygon(soup_poly, Color("#a8642e"))
	var soup := Rect2(POT.position.x + 8, SURF_Y, POT.size.x - 16, POT.end.y - SURF_Y - 6)
	b.draw_rect(Rect2(soup.position, Vector2(soup.size.x, 2)), Color("#c98a48"))
	b.draw_rect(Rect2(POT.position.x - 1, POT.position.y, POT.size.x + 2, 3), IRON_LIT)
	for q in _small:
		var u := float(q["t"]) / 0.8
		_ring(b, Vector2(float(q["x"]), soup.end.y - 4 - u * (soup.size.y - 6)), 1.2, Color("#e0a868"), 6)
	for q in _steam:
		var u := float(q["t"]) / 1.4
		b.draw_rect(Rect2(float(q["x"]) + sin(u * 6.0) * 3.0, POT.position.y - 4 - u * 34.0, 2, 2), Color(0.9, 0.9, 0.85, 0.35 * (1.0 - u)))
	# 收紧的涟漪 → 大泡
	var c := Vector2(POT.position.x + POT.size.x / 2.0, SURF_Y)
	var rr := 4.0 + 22.0 * (_next - _beat_t) / _next             # 离大泡破掉越近，圈收得越小
	_ring(b, c, rr, Color("#f0c890"), 24)
	if _pop_flash > 0.0:
		var k := _pop_flash / 0.35
		_disc(b, c + Vector2(0, -3.0 * k), 6.0 * k + 1.0, Color("#e9b070"))
		_ring(b, c, 10.0 + 8.0 * (1.0 - k), Color(1, 0.92, 0.75, k), 24)
	# 吊着的东西
	if idx < ings.size():
		var g: Dictionary = ings[idx]
		var hy := POT.position.y - 22.0
		if _bounce >= 0.0:
			hy += sin(_bounce / 0.45 * PI) * 10.0
		_line(b, Vector2(c.x, 6), Vector2(c.x, hy - 5), PAPER_DIM, 1.0)
		var col := Color(str(g.get("color", "#d0705a")))
		_disc(b, Vector2(c.x, hy), 5, col)
		_disc(b, Vector2(c.x - 1, hy - 1), 2, col.lightened(0.3))
		_caption(b, 20, _tr(g), UITheme.TEXT)
	if _splash >= 0.0:
		var u := _splash / 0.6
		_ring(b, c, 6.0 + 20.0 * u, Color(1, 0.9, 0.7, 1.0 - u), 28)
		for k in 5:
			var a := PI + PI * k / 4.0
			b.draw_rect(Rect2((c + Vector2(cos(a), sin(a)) * (4.0 + 12.0 * u) + Vector2(0, -8.0 * sin(u * PI))).round(), Vector2(2, 2)), Color("#e0a868"))
	# 放了几样
	for k in ings.size():
		_disc(b, Vector2(panel.x - 16 - (ings.size() - 1 - k) * 9, panel.y - 12), 3, LAMP if k < idx else IRON)


# ----------------------------------------------------------------------- 夜测机器人（--mech_play）
## 第二样故意按早一次（鼠妈「早了！」），其余都卡在咕嘟那一下
func _bot_play() -> void:
	var missed := false
	while _alive() and idx < ings.size():
		await _bot_ready()
		if not _alive():
			break
		await _bot_wait(0.3)
		if idx == 1 and not missed:
			missed = true
			while _alive() and _phase_err() < 0.45:
				await _frame()
			_bot_key(KEY_SPACE)
			await _bot_wait(0.8)
			continue
		while _alive() and _accept and _phase_err() > 0.04:
			await _frame()
		_bot_key(KEY_SPACE)
		await _bot_wait(0.9)
