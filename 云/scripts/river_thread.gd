extends "res://scripts/river_kit.gd"
## 河流篇小游戏 river_thread：修飞机，把管道接头拧回去（11-04 新做）。docs/剧情改动/第二章可玩性_设计.md 第 8 步。
##
## 画面：一截管子，中间一只六角接头。管子上印着一个箭头「↻ 拧紧」（往右）。妮芙在接头旁边贴了一张便条：「反方向」。
## 怎么玩：按住 ←/→（或按住鼠标左 / 右半边）拧接头。往右（照印着的箭头）= 接头往外退、管子嘶嘶冒气；往左 = 拧进去。
##   拧进去 TURNS 圈 =「咔」，做完。第一次往右拧松了：播 lines.wrong（妮芙：「反方向呀，本子上写着呢。」）。
## 放水：往右拧松到底 FAILS_GIVE 次（接头掉下来又被晨按回去），或第 ENTER_GIVE 次进：接头自己拧进去。
##
## 剧本步骤：{"do": "mechanic", "id": "river_thread", "sets"?, "turns"?, "note": {zh, en}（便条上的字）, "arrow": {zh, en}（印着的箭头字）,
##   "lines": {intro, wrong, give, done}}
## 进度：{enter, fails, done}。

const PIPE_Y := 78.0
const NUT := Vector2(116, 78)
const SPEED := 1.1                         # 每秒拧多少圈
const HINT := {"zh": "←→ 拧接头", "en": "← → to turn the joint"}

var turns := 2.5
var p := 0.0                               # 拧进去多少圈（负 = 往外退）
var ang := 0.0
var _wrong_said := false
var _hiss := 0.0
var _puffs: Array = []
var _mouse_dir := 0
var _done_t := -1.0


func _init() -> void:
	ID = "river_thread"
	panel = Vector2(232, 132)


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	level = lv
	step = st
	turns = float(st.get("turns", 2.5))
	var give := _enter({})
	_build("RiverThread", [])
	await _fade_in()
	await _lines("intro")
	_set_hint(step.get("hint", HINT))
	_shot("thread", 0.5)
	if give or auto_mode:
		if give and not auto_mode:
			await _lines("give")
		while _alive() and p < turns:
			p = minf(turns, p + SPEED * board.get_process_delta_time())
			ang -= SPEED * TAU * board.get_process_delta_time()
			await _frame()
	else:
		_accept = true
		while _alive() and p < turns:
			await _frame()
			if p <= -1.2:                       # 退到头：掉下来，晨按回去，算一次
				_accept = false
				_sfx("thud", -6.0)
				p = 0.0
				if _fail():
					await _lines("give")
					while _alive() and p < turns:
						p = minf(turns, p + SPEED * board.get_process_delta_time())
						ang -= SPEED * TAU * board.get_process_delta_time()
						await _frame()
				_accept = true
			if p < -0.25 and not _wrong_said:
				_wrong_said = true
				_accept = false
				await _lines("wrong")
				_accept = true
	_accept = false
	if not _alive():
		_drop()
		return
	_sfx("click", 0.0)
	_sfx("wrench", -4.0)
	_done_t = 0.0
	await _wait(0.6)
	_done()
	_set_hint({})
	await _lines("done")
	await _fade_out()


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	_bot_start()                         # 夜测 --mech_play：照玩家的节奏按键玩（不快进）
	await run(lv, w, r, st)


func ff(r: Node, st: Dictionary) -> void:
	_ff_save(r, st)


func check(r: Node, st: Dictionary) -> Array:
	return _check_lines(r, st, ["intro", "wrong", "done"])


func _tick(dt: float) -> void:
	var d := _axis()
	if d == 0 and _accept and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		d = -1 if _mouse().x < panel.x / 2.0 else 1
	if _accept and d != 0:
		p -= d * SPEED * dt                     # 往右（+1）= 往外退：反方向
		ang += d * SPEED * TAU * dt
		if Engine.get_process_frames() % 9 == 0:
			_sfx("screw_half", -14.0, 1.0 + randf_range(-0.05, 0.05))
	if p < 0.0:
		_hiss += dt
		if _hiss > 0.12:
			_hiss = 0.0
			_puffs.append({"p": NUT + Vector2(-18 + p * 6.0, -4), "t": 0.0})
	for q in _puffs:
		q["t"] = float(q["t"]) + dt
	_puffs = _puffs.filter(func(q): return float(q["t"]) < 0.9)
	if _done_t >= 0.0:
		_done_t += dt


func _draw_board(b: Control) -> void:
	_panel_bg(b, Color("#2c3a3c"), Color("#162224"))
	var out := clampf(-p, 0.0, 1.4) * 8.0                  # 接头往外退了多少像素
	var inn := clampf(p / turns, 0.0, 1.0)
	# 管子（左边固定，右边接头拧上去的那截）
	b.draw_rect(Rect2(10, PIPE_Y - 9, NUT.x - 22, 18), IRON)
	b.draw_rect(Rect2(10, PIPE_Y - 9, NUT.x - 22, 3), IRON_LIT)
	b.draw_rect(Rect2(NUT.x + 12 + out, PIPE_Y - 9, panel.x - NUT.x - 22, 18), IRON)
	b.draw_rect(Rect2(NUT.x + 12 + out, PIPE_Y - 9, panel.x - NUT.x - 22, 3), IRON_LIT)
	# 螺纹（露在外面的那几道，越拧进去越少）
	var threads := int(round((1.0 - inn) * 5.0 + out / 3.0))
	for k in threads:
		b.draw_rect(Rect2(NUT.x - 16 - k * 3 + out * 0.3, PIPE_Y - 7, 1, 14), IRON_LIT)
	# 六角接头（转着：用三条亮边的位置表现）
	var c := NUT + Vector2(out, 0)
	var hexo := PackedVector2Array()
	for k in 6:
		var a := ang + TAU * k / 6.0
		hexo.append((c + Vector2(cos(a) * 9.0, sin(a) * 15.0)).round())
	b.draw_colored_polygon(hexo, Color("#7a6c4c"))
	for k in 6:
		var a := ang + TAU * k / 6.0
		if sin(a) < -0.2:
			_line(b, c + Vector2(cos(a) * 9.0, sin(a) * 15.0), c + Vector2(cos(a + TAU / 6.0) * 9.0, sin(a + TAU / 6.0) * 15.0), Color("#b8a272"), 1.0)
	b.draw_rect(Rect2(c + Vector2(-2, -15), Vector2(4, 30)), Color(0, 0, 0, 0.12))
	# 印着的箭头：「↻ 拧紧」（往右）——是错的
	_text(b, Vector2(132, 44), _tr(step.get("arrow", {"zh": "拧紧", "en": "tighten"})), PAPER_DIM, 90.0, HORIZONTAL_ALIGNMENT_LEFT)
	_line(b, Vector2(134, 50), Vector2(176, 50), PAPER_DIM, 1.0)
	_line(b, Vector2(172, 47), Vector2(176, 50), PAPER_DIM, 1.0)
	_line(b, Vector2(172, 53), Vector2(176, 50), PAPER_DIM, 1.0)
	# 妮芙的便条（贴在接头左边，一角翘着）
	var nr := Rect2(30, 96, 76, 22)
	b.draw_rect(nr, Color("#e9e0a8"))
	b.draw_rect(Rect2(nr.position + Vector2(nr.size.x - 5, 0), Vector2(5, 3)), Color("#c9c08a"))
	_text(b, nr.position + Vector2(0, 16), _tr(step.get("note", {"zh": "反方向！", "en": "OTHER WAY!"})), INK, nr.size.x)
	# 进度：拧进去几圈（右下角三个小点）
	var n := int(ceil(turns))
	for k in n:
		var on := p >= k + 1.0 or (k == n - 1 and p >= turns)
		_disc(b, Vector2(panel.x - 16 - (n - 1 - k) * 9, panel.y - 14), 3, LAMP if on else IRON)
	for q in _puffs:
		var u := float(q["t"]) / 0.9
		_ring(b, (q["p"] as Vector2) + Vector2(-10.0 * u, -8.0 * u), 2.0 + 4.0 * u, Color(0.85, 0.92, 0.9, 0.6 * (1.0 - u)), 12)
	if _done_t >= 0.0:
		var k := clampf(1.0 - _done_t / 0.5, 0.0, 1.0)
		_ring(b, c, 18.0 + 10.0 * (1.0 - k), Color(LAMP.r, LAMP.g, LAMP.b, k), 32)


# ----------------------------------------------------------------------- 夜测机器人（--mech_play）
## 先照印着的箭头往右拧（拧松、妮芙「反方向呀」），再往左拧进去
func _bot_play() -> void:
	await _bot_ready()
	await _bot_wait(0.8)
	_bot_axis = 1
	while _alive() and p > -0.35:
		await _frame()
	_bot_axis = 0
	await _bot_ready()
	await _bot_wait(0.6)
	_bot_axis = -1
	while _alive() and p < turns:
		await _frame()
	_bot_axis = 0
