extends "res://scripts/river_kit.gd"
## 河流篇小游戏 river_valve：旧街水闸（11-04 重做，替掉 river_sluice 的「走过去一格一格转」）。
##   docs/剧情改动/第二章可玩性_设计.md 第 4 步。
##
## 画面：左边一只大铁闸轮，右边一块压力表（表盘上没有数字，是泥芙画的小画：小鱼 / 鞋 / 茶壶 / 鲸鱼），
##   下面一截管子，管口一直在冒泡、咕噜咕噜。左上三盏小灯 = 三道闸。
## 怎么玩：按住（空格 / E / 鼠标左键）转轮子，指针往上走；松手指针停住。
##   指针离这道闸要的位置越远，管子冒泡越凶、咕噜越响；到了那一点泡泡停、管子安静（「叮」一小声）。
##   这时候松手 = 这道闸卡住（灯亮、旧街的水降一档）。松早了：指针停在那，接着按接着转。
##   转过头（泡泡又冒起来了还不松）/ 顶到头：管子「噗」一下，指针弹回去，再来。
##   三道闸都卡住 = 设 sets（river_sluice_open），剧本接着演开闸、踏步露出来。
## 放水：失败 FAILS_GIVE 次以后，泥芙用粉笔在表盘上把那一格圈出来（看得见要停在哪）；失败 FAILS_AUTO 次 → 这道闸她帮你转好。
##   第 ENTER_GIVE 次进也直接圈出来。
##
## 剧本步骤：{"do": "mechanic", "id": "river_valve", "sets": ["river_sluice_open"],
##   "gates": [{"t": 0..1（要停的位置）, "label": {zh, en}}…],
##   "water": {"prop": "oldstreet_steps", "levels": [第一道闸以后, 第二道以后…]}, "wheels": [每道闸卡住以后设 set 的闸轮 prop…],
##   "doodles": [{"t": 0..1, "zh", "en", "kind": fish/shoe/pot/whale}…],
##   "lines": {intro, gate_1, gate_2, fail_1, give, done}}
## 进度：{enter, fails, done, gate}。

const WHEEL := Vector2(62, 84)
const WHEEL_R := 38.0
const GAUGE := Vector2(166, 74)
const GAUGE_R := 36.0
const A0 := PI * 0.85                     # 指针 0 的角度（左下）
const A1 := PI * 0.15                     # 指针 1 的角度（右下），顺时针走上面那半圈
const PIPE_Y := 128.0
const VENT := Vector2(206, 128)
const RISE := 0.34                        # 按住每秒涨多少
const TOL := 0.055
const FAILS_AUTO := 5
const HINT := {"zh": "按住转闸轮，管子不咕噜了就松手", "en": "Hold to turn the wheel. Let go when the pipe goes quiet.", "fr": "Maintiens pour tourner. Relâche quand le tuyau se tait."}
const DEFAULT_GATES := [{"t": 0.42, "label": {"zh": "第一道闸", "en": "Gate one", "fr": "Première vanne"}},
	{"t": 0.66, "label": {"zh": "第二道闸", "en": "Gate two", "fr": "Deuxième vanne"}},
	{"t": 0.86, "label": {"zh": "大闸", "en": "The big gate", "fr": "Grande vanne"}}]
const DEFAULT_DOODLES := [{"t": 0.12, "kind": "fish"}, {"t": 0.42, "kind": "shoe"}, {"t": 0.66, "kind": "pot"}, {"t": 0.9, "kind": "whale"}]

var gates: Array = []
var gate := 0
var v := 0.0                              # 指针 0..1
var ang := 0.0                            # 轮子转了多少
var stage := "turn"                       # turn / snap / set / done
var _was_holding := false
var _bubbles: Array = []
var _bub_t := 0.0
var _gurgle_t := 0.0
var _chalk := false
var _snap_t := 0.0
var _set_t := 0.0
var _quiet_ding := false
var _world: Node2D


func _init() -> void:
	ID = "river_valve"


func run(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	level = lv
	step = st
	_world = w
	gates = st.get("gates", DEFAULT_GATES)
	var give := _enter({"gate": 0})
	gate = clampi(int(s.get("gate", 0)), 0, gates.size())
	_chalk = give
	_build("RiverValve", [])
	await _fade_in()
	await _lines("intro")
	_set_hint(step.get("hint", HINT))
	_shot("valve", 0.9)
	while _alive() and gate < gates.size():
		v = 0.0
		stage = "turn"
		var ok: bool = await _play_gate()
		if not _alive():
			break
		if ok:
			await _gate_set()
		else:
			_snap()
			while _alive() and stage == "snap":
				await _frame()
			var gave := _fail()
			_chalk = _chalk or gave
			if int(s["fails"]) == 1:
				_accept = false
				await _lines("fail_1")
			elif gave and int(s["fails"]) == FAILS_GIVE:
				_accept = false
				await _lines("give")
			if int(s["fails"]) >= FAILS_AUTO:
				await _auto_gate()
				await _gate_set()
	_accept = false
	if not _alive():
		_drop()
		return
	_done()
	_set_hint({})
	await _lines("done")
	await _fade_out()


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	_bot_start()                         # 夜测 --mech_play：照玩家的节奏按键玩（不快进）
	await run(lv, w, r, st)


func ff(r: Node, st: Dictionary) -> void:
	_ff_save(r, st, {"gate": (st.get("gates", DEFAULT_GATES) as Array).size()})


func check(r: Node, st: Dictionary) -> Array:
	var out := _check_lines(r, st, ["intro", "fail_1", "give", "done"])
	for g in st.get("gates", []):
		if not g is Dictionary or not g.has("t") or float(g["t"]) <= 0.05 or float(g["t"]) >= 0.97:
			out.append("gates：每道闸要有 t（0.05..0.97）：%s" % str(g))
	return out


# ----------------------------------------------------------------------- 一道闸
func _target() -> float:
	return float(gates[gate].get("t", 0.5))


## 转一道：返回 true = 停在对的地方松手
func _play_gate() -> bool:
	if auto_mode:
		await _auto_gate()
		return true
	_accept = true
	_was_holding = false
	while _alive():
		await _frame()
		if stage != "turn":
			continue
		var h := _holding()
		if h:
			_was_holding = true
		elif _was_holding:
			_was_holding = false
			if absf(v - _target()) <= TOL:
				_accept = false
				return true
			if v > _target() + TOL:            # 转过头：噗
				_accept = false
				return false
			# 松早了：指针停在那，接着按接着转
		if v >= 0.995:
			_accept = false
			return false
	return false


## 放水 / 自动玩：轮子自己转到那一格停住
func _auto_gate() -> void:
	_chalk = true
	var t := _target()
	while _alive() and v < t:
		v = minf(t, v + RISE * get_dt())
		ang += RISE * get_dt() * 5.0
		await _frame()
	await _wait(0.25)


func get_dt() -> float:
	return board.get_process_delta_time() if _alive() else 0.016


## 卡住：「咔」、灯亮、旧街的水降一档；第一、二道播一句
func _gate_set() -> void:
	stage = "set"
	_set_t = 0.0
	_sfx("sluice_turn", -4.0)
	_sfx("click", -2.0)
	var lv: Array = step.get("water", {}).get("levels", [])
	if _world != null and gate < lv.size():
		_world.set_prop(str(step["water"].get("prop", "")), str(lv[gate]))
	var wh: Array = step.get("wheels", [])
	if _world != null and gate < wh.size():
		_world.set_prop(str(wh[gate]), "set")
	gate += 1
	s["gate"] = gate
	_save()
	await _wait(0.6)
	if gate < gates.size():
		_accept = false
		await _lines("gate_%d" % gate)
	stage = "turn"


# ----------------------------------------------------------------------- 每帧
func _tick(dt: float) -> void:
	if stage == "turn" and gate < gates.size():
		if _holding():
			v = minf(1.0, v + RISE * dt)
			ang += RISE * dt * 5.0
	if stage == "snap":
		_snap_t += dt
		v = maxf(0.0, v - dt * 2.2)
		if v <= 0.0:
			stage = "turn"
	if stage == "set":
		_set_t += dt
	# 冒泡：离目标越远越凶（卡住以后 / 都做完了不冒）
	var d := 1.0 if gate >= gates.size() else absf(v - _target())
	var rate := 0.0 if (stage == "set" or gate >= gates.size()) else clampf(d * 9.0, 0.0, 6.0)
	if d <= TOL * 0.8 and stage == "turn":
		rate = 0.0
		if not _quiet_ding and v > 0.02:
			_quiet_ding = true
			_sfx("bell_soft", -18.0, 1.6)
	else:
		_quiet_ding = false
	_bub_t += dt * rate
	while _bub_t >= 1.0:
		_bub_t -= 1.0
		_bubbles.append({"p": VENT + Vector2(randf_range(-2, 2), 0), "t": 0.0, "r": randf_range(1.0, 2.6)})
	_gurgle_t -= dt
	if rate > 0.6 and _gurgle_t <= 0.0:
		_gurgle_t = clampf(1.6 - rate * 0.22, 0.35, 1.6)
		_sfx("pipe_gurgle_%d" % (3 if rate > 3.0 else 2), -10.0 if rate < 3.0 else -5.0)
	for bb in _bubbles:
		bb["t"] = float(bb["t"]) + dt
	_bubbles = _bubbles.filter(func(bb): return float(bb["t"]) < 1.1)


func _snap() -> void:
	stage = "snap"
	_snap_t = 0.0
	_sfx("water_surge", -6.0)
	_sfx("hiss_small", -8.0)


# ----------------------------------------------------------------------- 画
func _draw_board(b: Control) -> void:
	_panel_bg(b, RIVER_MID, RIVER_DEEP)
	# 三盏灯
	for i in gates.size():
		var c := Vector2(14 + i * 12, 14)
		_disc(b, c, 4, FRAME_DARK)
		_disc(b, c, 3, LAMP if i < gate else IRON)
		if i < gate:
			_disc(b, c + Vector2(-1, -1), 1, Color("#fff1c4"))
	if gate < gates.size():
		_text(b, Vector2(0, 19), _tr(gates[gate].get("label", {})), UITheme.TEXT_DIM)
	_draw_pipe(b)
	_draw_wheel(b)
	_draw_gauge(b)


func _draw_wheel(b: Control) -> void:
	var c := WHEEL
	_disc(b, c + Vector2(2, 3), WHEEL_R + 1, Color(0, 0, 0, 0.35))
	for k in [0.0, 1.0]:
		_ring(b, c, WHEEL_R - k, IRON_LIT if k == 0.0 else IRON, 0)
	_ring(b, c, WHEEL_R - 2, IRON, 0)
	for i in 6:
		var a := ang + TAU * i / 6.0
		var q := c + Vector2(cos(a), sin(a)) * (WHEEL_R - 2)
		_line(b, c, q, IRON, 2.0)
		_disc(b, q, 2.5, IRON_LIT)       # 把手
	_disc(b, c, 7, IRON)
	_disc(b, c, 4, IRON_LIT)
	_disc(b, c + Vector2(-1, -1), 1.5, Color("#9aa4a2"))


## 表盘上 t（0..1）那一点：从左下顺时针绕过最上面走到右下（屏幕 y 朝下，角度变大 = 顺时针）
func _gauge_pt(t: float, r: float) -> Vector2:
	var a := A0 + t * (TAU - (A0 - A1))
	return GAUGE + Vector2(cos(a), sin(a)) * r


func _draw_gauge(b: Control) -> void:
	_disc(b, GAUGE + Vector2(2, 3), GAUGE_R + 3, Color(0, 0, 0, 0.35))
	_disc(b, GAUGE, GAUGE_R + 3, IRON)
	_disc(b, GAUGE, GAUGE_R + 1, IRON_LIT)
	_disc(b, GAUGE, GAUGE_R, PAPER)
	# 刻度（细点）
	for i in 21:
		var t := i / 20.0
		b.draw_rect(Rect2(_gauge_pt(t, GAUGE_R - 3).round(), Vector2(1, 1)), PAPER_DIM)
	# 泥芙的小画
	for d in step.get("doodles", DEFAULT_DOODLES):
		_doodle(b, _gauge_pt(float(d.get("t", 0.5)), GAUGE_R - 11), str(d.get("kind", "fish")))
	# 粉笔圈（放水）：要停的那一格
	if _chalk and gate < gates.size():
		var p := _gauge_pt(_target(), GAUGE_R - 4)
		_ring(b, p, 5.0, Color("#f4f4ec"), 20)
		_ring(b, p, 6.0, Color(1, 1, 1, 0.45), 24)
	# 指针
	var tip := _gauge_pt(v, GAUGE_R - 4)
	_line(b, GAUGE, tip, BAD, 2.0)
	_disc(b, GAUGE, 3, INK)


## 表盘上泥芙画的小画（每个 7×5 像素左右）
func _doodle(b: Control, p: Vector2, kind: String) -> void:
	var o := p.round()
	match kind:
		"fish":
			b.draw_rect(Rect2(o + Vector2(-3, -1), Vector2(5, 3)), Color("#4f7f8c"))
			b.draw_rect(Rect2(o + Vector2(2, -2), Vector2(2, 5)), Color("#4f7f8c"))
			b.draw_rect(Rect2(o + Vector2(-2, -1), Vector2(1, 1)), INK)
		"shoe":
			b.draw_rect(Rect2(o + Vector2(-3, -2), Vector2(3, 3)), Color("#8a5a3c"))
			b.draw_rect(Rect2(o + Vector2(-3, 1), Vector2(7, 2)), Color("#8a5a3c"))
		"pot":
			b.draw_rect(Rect2(o + Vector2(-3, -1), Vector2(6, 4)), Color("#6f6a5a"))
			b.draw_rect(Rect2(o + Vector2(3, 0), Vector2(2, 1)), Color("#6f6a5a"))
			b.draw_rect(Rect2(o + Vector2(-1, -3), Vector2(2, 2)), Color("#6f6a5a"))
		"whale":
			b.draw_rect(Rect2(o + Vector2(-4, -1), Vector2(8, 4)), Color("#3f5f78"))
			b.draw_rect(Rect2(o + Vector2(4, -2), Vector2(2, 2)), Color("#3f5f78"))
			b.draw_rect(Rect2(o + Vector2(-2, -3), Vector2(1, 2)), Color("#8fb6c8"))
			b.draw_rect(Rect2(o + Vector2(-3, 0), Vector2(1, 1)), INK)


func _draw_pipe(b: Control) -> void:
	b.draw_rect(Rect2(WHEEL.x, PIPE_Y - 4, VENT.x - WHEEL.x + 4, 8), IRON)
	b.draw_rect(Rect2(WHEEL.x, PIPE_Y - 4, VENT.x - WHEEL.x + 4, 2), IRON_LIT)
	b.draw_rect(Rect2(VENT.x - 3, PIPE_Y - 12, 8, 10), IRON)
	b.draw_rect(Rect2(VENT.x - 3, PIPE_Y - 12, 8, 2), IRON_LIT)
	# 水面（管口那一截泡在水里）
	b.draw_rect(Rect2(VENT.x - 22, PIPE_Y - 13, 40, 1), RIVER_LIT)
	for bb in _bubbles:
		var u := float(bb["t"])
		var q: Vector2 = bb["p"] + Vector2(sin(u * 9.0) * 1.5, -14.0 - u * 26.0)
		if q.y < PIPE_Y - 13:
			q.y = PIPE_Y - 13              # 冒到水面就停在水面上破掉
		_ring(b, q, float(bb["r"]) * (1.0 - u * 0.4), SOFT, 8)


# ----------------------------------------------------------------------- 夜测机器人（--mech_play）
## 第一道闸故意转过头（噗、弹回去），之后都在泡泡停的那一下松手
func _bot_play() -> void:
	var miss := true
	while _alive() and gate < gates.size():
		await _bot_ready()
		if not _alive() or stage != "turn":
			await _frame()
			continue
		await _bot_wait(0.5)
		var t := _target()
		var stop := minf(0.97, t + 0.14) if miss else t
		miss = false
		_bot_hold = true
		while _alive() and _accept and stage == "turn" and v < stop - 0.004 and v < 0.99:
			await _frame()
		_bot_hold = false
		await _bot_wait(0.4)
		while _alive() and stage != "turn":
			await _frame()
