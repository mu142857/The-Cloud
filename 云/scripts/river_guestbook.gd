extends "res://scripts/river_kit.gd"
## 河流篇小游戏 river_guestbook：扇干来客册（可选支线，11-04 新做）。docs/剧情改动/第二章可玩性_设计.md 支线「来客册」。
##
## 画面：摊开的来客册，右边那页泡得发皱，一块一块深色的水渍；左下角一把泥芙的蒲扇。
## 怎么玩：←/→ 交替按（或鼠标左右来回晃、连点）= 扇风。水渍一块块缩小，干了的地方露出字：一行一行来客名单。
##   名单是剧本给的（guests，按 flag 挑）：前面几条是别人，最后几条是今天的「湿湿的人」——泥芙每忘一次就记一笔。
##   全干了 = 名单念完，做完（剧本接着讲弥洛的朋友那页）。
## 放水：DRY_HELP 秒没扇动，泥芙凑过来吹（自己慢慢干）。第 ENTER_GIVE 次进 = 一进来就是干的。
##
## 剧本步骤：{"do": "mechanic", "id": "river_guestbook", "guests": [{zh, en, need?, not?}…], "lines": {intro, give, done}}
## 进度：{enter, fails, done}。

const PAGE := Rect2(100, 20, 140, 108)    # 右页（一行放得下 9 个字）
const FAN := Vector2(44, 112)
const DRY_HELP := 6.0
const STEP := 0.055                       # 扇一下干多少
const HINT := {"zh": "←→ 交替按，扇干这一页", "en": "Alternate ← → to fan the page dry", "fr": "Alterner ← et → pour sécher la page"}

var dry := 0.0
var _last := 0
var _idle := 0.0
var _fan_a := 0.0
var _blots: Array = []
var guests: Array = []
var _shown := 0
var _show_t := 0.0
var _mx := 0.0
var _mdir := 0


func _init() -> void:
	ID = "river_guestbook"
	quit_ok = true
	panel = Vector2(248, 140)


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	level = lv
	step = st
	guests = pick_guests(st)
	var give := _enter({})
	if give:
		dry = 1.0
	for i in 7:
		_blots.append({"p": PAGE.position + Vector2(randf_range(14, PAGE.size.x - 14), randf_range(14, PAGE.size.y - 14)), "r": randf_range(9, 17)})
	_build("RiverGuestbook", [])
	await _fade_in()
	await _lines("intro")
	_shot("guestbook", 0.6)
	if dry < 1.0 and not _quit_req:
		_set_hint(step.get("hint", HINT))
		_accept = true
		while _alive() and dry < 1.0 and not _quit_req:
			if auto_mode:
				dry = minf(1.0, dry + board.get_process_delta_time() * 0.9)
			await _frame()
		_accept = false
		_set_hint({})
	elif give and not _quit_req:
		await _lines("give")
	if _quit_req:
		await _quit_out()
		return
	quit_ok = false
	# 名单一行一行出来
	while _alive() and _shown < guests.size():
		_shown += 1
		_sfx("pencil", -14.0)
		await _wait(0.55)
	await _wait(OL.READ_SEC)
	if not _alive():
		_drop()
		return
	_done()
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
	for g in st.get("guests", []):
		if not g is Dictionary or str(g.get("zh", "")) == "" or str(g.get("en", "")) == "":
			out.append("guests：每条要有 zh / en：%s" % str(g))
	return out


## 按 flag 挑（need 全有、not 全没有）
static func pick_guests(st: Dictionary) -> Array:
	var out: Array = []
	for g in st.get("guests", []):
		if g is Dictionary and StoryState.all_of(g.get("need", [])) and StoryState.none_of(g.get("not", [])):
			out.append(g)
	return out


func _fan(dir: int) -> void:
	if dir == _last:
		return
	_last = dir
	_idle = 0.0
	dry = minf(1.0, dry + STEP)
	_fan_a = 0.5 * dir
	_sfx("cloth_flap", -12.0, randf_range(0.95, 1.1))


func _press(e: InputEvent) -> bool:
	if is_left(e):
		_fan(-1)
		return true
	if is_right(e):
		_fan(1)
		return true
	if is_ok(e):
		_fan(-_last if _last != 0 else 1)
		return true
	if e is InputEventMouseMotion:
		var dx := (e as InputEventMouseMotion).relative.x
		var d := 1 if dx > 2.0 else (-1 if dx < -2.0 else 0)
		if d != 0 and d != _mdir:
			_mdir = d
			_fan(d)
	return false


func _tick(dt: float) -> void:
	_fan_a = move_toward(_fan_a, 0.0, dt * 2.5)
	if _accept and dry < 1.0:
		_idle += dt
		if _idle > DRY_HELP:
			dry = minf(1.0, dry + dt * 0.12)    # 泥芙凑过来吹


func _draw_board(b: Control) -> void:
	_panel_bg(b, Color("#3a2c22"), Color("#241a14"))
	# 书：左页是旧的、干的（几行看不清的旧字），右页是要扇干的
	var lp := Rect2(8, PAGE.position.y, PAGE.position.x - 12, PAGE.size.y)
	b.draw_rect(lp.grow(1), FRAME_DARK)
	b.draw_rect(lp, PAPER_DIM)
	for k in 7:
		b.draw_rect(Rect2(lp.position + Vector2(8, 12 + k * 12), Vector2(lp.size.x - 16 - (k * 7) % 20, 1)), Color(INK.r, INK.g, INK.b, 0.35))
	b.draw_rect(PAGE.grow(1), FRAME_DARK)
	b.draw_rect(PAGE, PAPER)
	b.draw_rect(Rect2(PAGE.position.x - 3, PAGE.position.y, 2, PAGE.size.y), Color("#8c826a"))     # 书脊
	# 名单
	var f := UITheme.font()
	for i in mini(_shown, guests.size()):
		var t := _tr(guests[i])
		b.draw_string(f, PAGE.position + Vector2(5, 15 + i * 13), t, HORIZONTAL_ALIGNMENT_LEFT, PAGE.size.x - 8, 14, INK)
	# 水渍（还没干的盖住字）
	var k := 1.0 - dry
	for bl in _blots:
		var rr := float(bl["r"]) * k
		if rr >= 1.0:
			_disc(b, bl["p"], rr + 1.0, Color("#8f9d9c"))
			_disc(b, bl["p"], rr, Color("#6e8486"))
	if dry < 1.0:
		b.draw_rect(PAGE, Color(0.25, 0.32, 0.34, 0.35 * k))
	# 蒲扇（扇一下歪一下）
	var a := -0.4 + _fan_a
	var tip := FAN + Vector2(cos(a - PI / 2.0), sin(a - PI / 2.0)) * 26.0
	_line(b, FAN, FAN.lerp(tip, 0.45), FRAME_LIT, 2.0)
	_disc(b, FAN.lerp(tip, 0.75), 11, Color("#c9a86a"))
	_disc(b, FAN.lerp(tip, 0.75), 9, Color("#ddbf80"))
	# 干了多少
	b.draw_rect(Rect2(PAGE.position.x, PAGE.end.y + 5, PAGE.size.x, 3), FRAME_DARK)
	b.draw_rect(Rect2(PAGE.position.x, PAGE.end.y + 5, PAGE.size.x * dry, 3), LAMP)


# ----------------------------------------------------------------------- 夜测机器人（--mech_play）
## ←→ 交替扇
func _bot_play() -> void:
	await _bot_ready()
	await _bot_wait(0.6)
	var k := 0
	while _alive() and dry < 1.0 and _accept:
		_bot_key(KEY_LEFT if k % 2 == 0 else KEY_RIGHT)
		k += 1
		await _bot_wait(0.16)
