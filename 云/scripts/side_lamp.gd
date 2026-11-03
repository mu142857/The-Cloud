extends "res://scripts/side_kit.gd"
## 第一关支线 2c「油灯送回小屋」：点灯 + 手影戏（docs/剧情改动/第一关支线_设计.md）。
##
## 画面：空屋里面，竖木板墙、左上一扇窗、底下窗台，油灯摆在窗台左边。
## 怎么玩：
##   ① 添油：剧本那一步已经选好拿什么当油（"fuel"，比如支线 1 的松脂），这里只演倒进灯里。
##   ② 点灯：点一下灯（或空格 / E / 回车），火苗窜起来再落稳，墙一档一档亮起来。
##   ③ 影子：墙上浮出以前住在这儿的三个人的影子，他们在挥手（lines.wave）。最小的那个在地上摸来摸去，
##      然后比划了一个背包的形状：它也在找背包（lines.bag）。
##   ④ 手影：个子最高的那个把手举到灯前，墙上出现一只兔子 / 鸟 / 狗（"gesture" 0 / 1 / 2）。窗台上三张小卡片，
##      选一样的那个（点，或 ←→ 选 + 空格），晨的手影就出现在它旁边，一起动一动。选错了它歪歪头（lines.wrong_1），再来。
##   ⑤ 影子挥挥手，慢慢淡掉，灯还亮着（lines.done）。
## 放水：选错 FAILS_GIVE 次，或第 ENTER_GIVE 次进 → 对的卡片自己亮起来、自己选上。
##
## 剧本步骤：{"do": "mechanic", "id": "side_lamp"}，可选 "sets"、"fuel"（物品 id，只用来存档）、"gesture"、
##   "hint_light" / "hint_pick": {zh, en}、"lines": {intro, lit, wave, bag, gesture, wrong_1, give, done}。
## 进度：{enter, fails, done}。

const LAMP_TL := Vector2(32, 98)          # lamp.png 一帧 16×26 放在这
const WICK := Vector2(40, 110)
const SPOTS := [Vector2(96, 116), Vector2(128, 116), Vector2(170, 116)]   # 三个影子的脚底中点
const HAND_AT := Vector2(118, 26)         # 他们的手影（32×24 左上）
const MINE_AT := Vector2(166, 30)         # 晨的手影
const CARD := Vector2(36, 20)
const CARD_Y := 127.0
const CARD_X := [88.0, 132.0, 176.0]      # 三张卡片的中心
const SHADOW := Color("#2a1e16")
const HINT_LIGHT := {"zh": "点一下灯芯", "en": "Click the wick."}
const HINT_PICK := {"zh": "做一个一样的手影", "en": "Make the same hand shadow."}
const SAP := [Color("#7d552f"), Color("#c8823c"), Color("#e8b860")]
const HOT := [Color("#962f2c"), Color("#c9473a"), Color("#e8795a"), Color("#f0c070")]

var stage := ""                           # pour / light / show / pick / done
var _fill := 0.0                          # 灯里的油 0..1
var _pour := 0.0                          # 倒油的那道 0..1
var _lit := false
var _flame := 0.0                         # 火苗大小（1 = 落稳以后）
var _light := 0.0                         # 墙有多亮 0..1（画的时候分四档）
var _sh_a := [0.0, 0.0, 0.0]              # 三个影子多清楚
var _sh_f := [0, 2, 4]                    # 三个影子现在用 lamp_shadows.png 哪一格
var _waving := false
var _hand_a := 0.0
var _mine := -1
var _mine_a := 0.0
var _tilt := 0.0                          # 他们的手影歪头（选错）
var _bob := 0.0                           # 选对以后两个手影一起动
var _sel := 1
var _pick_ok := false
var gesture := 0
var _cards_a := 0.0
var _rummage := 0.0


func _init() -> void:
	ID = "side_lamp"


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	level = lv
	step = st
	gesture = clampi(int(step.get("gesture", 0)), 0, 2)
	var give := _enter({})
	if step.has("fuel"):
		s["fuel"] = str(step["fuel"])
		_save()
	_build("SideLamp", ["lamp_panel", "lamp_lit", "lamp", "lamp_shadows", "lamp_hands"])
	await _fade_in()
	await _lines("intro")
	# ① 添油
	stage = "pour"
	_sfx("pipe_gurgle", -8.0)
	var tw := _tw()
	tw.tween_property(self, "_pour", 1.0, 0.25 * _k())
	tw.tween_property(self, "_fill", 1.0, 1.1 * _k()).set_trans(Tween.TRANS_SINE)
	tw.tween_property(self, "_pour", 0.0, 0.25 * _k())
	await tw.finished
	# ② 点灯
	stage = "light"
	if not (give or auto_mode):
		_set_hint(step.get("hint_light", HINT_LIGHT))
		_accept = true
		await _stage
		_accept = false
		_set_hint({})
	else:
		await _wait(0.6)
	await _light_up()
	await _lines("lit")
	# ③ 影子
	stage = "show"
	await _shadows_in()
	await _lines("wave")
	await _search()
	await _lines("bag")
	# ④ 手影
	_waving = false
	_sh_f = [0, 2, 4]
	await _wait(0.4)
	tw = _tw().set_parallel(true)
	tw.tween_property(self, "_hand_a", 1.0, 0.8 * _k()).set_trans(Tween.TRANS_SINE)
	tw.tween_property(self, "_cards_a", 1.0, 0.6 * _k()).set_delay(0.5 * _k())
	await tw.finished
	await _lines("gesture")
	stage = "pick"
	while _alive():
		var pick := -1
		if give or auto_mode:
			if give and not auto_mode and not tried.has("give_line"):
				tried["give_line"] = true
				await _lines("give")
			pick = gesture
			if auto_mode and story.auto == "full" and not tried.has("wrong"):
				tried["wrong"] = true
				pick = (gesture + 1) % 3
			await _wait(0.5)
			_sel = pick
			await _wait(0.4)
		else:
			_set_hint(step.get("hint_pick", HINT_PICK))
			_accept = true
			await _stage
			_accept = false
			pick = _sel
		if not _alive():
			break
		var ok: bool = await _show_mine(pick)
		if ok:
			break
		if int(s["fails"]) == 0:
			await _lines("wrong_1")
		if _fail():
			give = true
		await _hide_mine()
	if not _alive():
		_drop()
		return
	_set_hint({})
	# ⑤ 告别
	stage = "done"
	tw = _tw().set_parallel(true)
	tw.tween_property(self, "_cards_a", 0.0, 0.4 * _k())
	tw.tween_property(self, "_hand_a", 0.0, 0.8 * _k()).set_delay(0.6 * _k())
	tw.tween_property(self, "_mine_a", 0.0, 0.8 * _k()).set_delay(0.6 * _k())
	await tw.finished
	_waving = true
	await _wait(1.6)
	tw = _tw().set_parallel(true)
	for i in 3:
		tw.tween_method(func(v: float): _sh_a[i] = v, 1.0, 0.0, 1.4 * _k()).set_delay(i * 0.25 * _k()).set_trans(Tween.TRANS_SINE)
	await tw.finished
	_waving = false
	_done()
	await _lines("done")
	await _fade_out()


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


func ff(r: Node, st: Dictionary) -> void:
	_ff_save(r, st, {"fuel": str(st.get("fuel", ""))})


func check(r: Node, st: Dictionary) -> Array:
	var out := _check_lines(r, st, ["intro", "lit", "wave", "bag", "gesture", "wrong_1", "give", "done"])
	if st.has("gesture") and (int(st["gesture"]) < 0 or int(st["gesture"]) > 2):
		out.append("gesture 要是 0（兔子）/ 1（鸟）/ 2（狗）")
	if st.has("fuel") and not Inventory.defined(str(st["fuel"])):
		out.append("fuel %s 不在物品表" % str(st["fuel"]))
	return out


# ----------------------------------------------------------------------- 输入
func _press(e: InputEvent) -> bool:
	if stage == "light":
		if (is_click(e) or is_ok_key(e)) and e.is_pressed():
			_accept = false
			_stage.emit("lit")
			return true
	elif stage == "pick":
		if e is InputEventMouseMotion:
			var i := _card_at(_mouse())
			if i >= 0:
				_sel = i
			return true
		if is_click(e) and e.is_pressed():
			var i := _card_at(_mouse())
			if i >= 0:
				_sel = i
				_accept = false
				_stage.emit("pick")
			return true
		if e is InputEventKey and e.is_pressed() and not (e as InputEventKey).echo:
			var k: int = (e as InputEventKey).keycode
			if k in [KEY_LEFT, KEY_A]:
				_sel = posmod(_sel - 1, 3)
				_sfx("tick", -12.0)
			elif k in [KEY_RIGHT, KEY_D]:
				_sel = posmod(_sel + 1, 3)
				_sfx("tick", -12.0)
			elif is_ok_key(e):
				_accept = false
				_stage.emit("pick")
			return true
	return false


func _card_at(p: Vector2) -> int:
	for i in 3:
		if Rect2(Vector2(CARD_X[i] - CARD.x * 0.5, CARD_Y), CARD).has_point(p):
			return i
	return -1


# ----------------------------------------------------------------------- 演
func _light_up() -> void:
	_lit = true
	_sfx("small_click", -4.0)
	_sfx("fire_flare", -6.0)
	var tw := _tw()
	tw.tween_property(self, "_flame", 1.8, 0.18 * _k()).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_property(self, "_flame", 1.0, 0.5 * _k()).set_trans(Tween.TRANS_SINE)
	tw.parallel().tween_property(self, "_light", 1.0, 1.2 * _k()).set_trans(Tween.TRANS_SINE)
	await tw.finished


func _shadows_in() -> void:
	var tw := _tw().set_parallel(true)
	for i in 3:
		tw.tween_method(func(v: float): _sh_a[i] = v, 0.0, 1.0, 1.0 * _k()).set_delay(i * 0.3 * _k()).set_trans(Tween.TRANS_SINE)
	await tw.finished
	_waving = true
	await _wait(1.8)


## 最小的那个弯腰在地上摸，摸了两下，站起来比划一个背包
func _search() -> void:
	_waving = false
	_sh_f = [0, 2, 4]
	for k in 3:
		_rummage = 1.0 if k % 2 == 0 else -1.0
		_sfx("pat", -16.0, 1.3)
		await _wait(0.45)
	_rummage = 0.0
	_sh_f[2] = 5
	_sfx("pat", -10.0)
	await _wait(1.0)


## 晨的手影：返回选对没有
func _show_mine(pick: int) -> bool:
	_mine = pick
	_sfx("pat", -8.0)
	var tw := _tw()
	tw.tween_property(self, "_mine_a", 1.0, 0.5 * _k()).set_trans(Tween.TRANS_SINE)
	await tw.finished
	if pick == gesture:
		_sfx("bell_soft", -6.0)
		tw = _tw()
		tw.tween_method(func(u: float): _bob = sin(u * TAU * 2.0) * 2.0, 0.0, 1.0, 1.2 * maxf(_k(), 0.5))
		await tw.finished
		_bob = 0.0
		return true
	tw = _tw()
	tw.tween_method(func(u: float): _tilt = sin(u * PI) * 0.35, 0.0, 1.0, 0.9 * maxf(_k(), 0.5)).set_trans(Tween.TRANS_SINE)
	await tw.finished
	_tilt = 0.0
	return false


func _hide_mine() -> void:
	var tw := _tw()
	tw.tween_property(self, "_mine_a", 0.0, 0.35 * _k())
	await tw.finished
	_mine = -1


func _tick(_dt: float) -> void:
	if _waving:
		var ph := int(_t / 0.45) % 2
		_sh_f[0] = ph
		_sh_f[1] = 2 + (1 - ph)


# ----------------------------------------------------------------------- 画
func _draw_board(b: Control) -> void:
	b.draw_texture(_tex["lamp_panel"], Vector2.ZERO)
	var flick := 0.0
	if _lit:
		flick = (sin(_t * 9.0) + sin(_t * 23.0) * 0.5) * 0.06
	var lv := floorf(clampf(_light + flick * _light, 0.0, 1.0) * 4.0) / 4.0
	if lv > 0.0 and _tex["lamp_lit"] != null:
		b.draw_texture(_tex["lamp_lit"], Vector2.ZERO, Color(1, 1, 1, lv))
	# 影子（跟着火苗轻轻晃一个像素）
	var sway := 1.0 if flick > 0.05 else 0.0
	var shs: Texture2D = _tex["lamp_shadows"]
	if shs != null:
		for i in 3:
			if _sh_a[i] <= 0.0:
				continue
			var a := ceilf(float(_sh_a[i]) * lv * 3.0) / 3.0
			var p: Vector2 = SPOTS[i] - Vector2(16, 52) + Vector2(sway + (_rummage if i == 2 else 0.0), 0)
			b.draw_texture_rect_region(shs, Rect2(p, Vector2(32, 52)), Rect2(int(_sh_f[i]) * 32, 0, 32, 52), Color(SHADOW, a))
	var hands: Texture2D = _tex["lamp_hands"]
	if hands != null:
		if _hand_a > 0.0:
			var c := HAND_AT + Vector2(16, 12)
			b.draw_set_transform(c + Vector2(sway, _bob), _tilt, Vector2.ONE)
			b.draw_texture_rect_region(hands, Rect2(Vector2(-16, -12), Vector2(32, 24)), Rect2(gesture * 32, 0, 32, 24),
				Color(SHADOW, ceilf(_hand_a * lv * 3.0) / 3.0))
			b.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		if _mine >= 0 and _mine_a > 0.0:
			b.draw_texture_rect_region(hands, Rect2(MINE_AT + Vector2(sway, -_bob), Vector2(32, 24)), Rect2(_mine * 32, 0, 32, 24),
				Color(SHADOW, ceilf(_mine_a * lv * 3.0) / 3.0))
	# 灯
	var lamp: Texture2D = _tex["lamp"]
	if lamp != null:
		b.draw_texture_rect_region(lamp, Rect2(LAMP_TL, Vector2(16, 26)), Rect2(16 if _lit else 0, 0, 16, 26))
	if _fill > 0.0 and not _lit:
		var hpx := roundf(_fill * 3.0)
		b.draw_rect(Rect2(LAMP_TL.x + 3, LAMP_TL.y + 21 - hpx, 10, hpx), SAP[1])
	if _pour > 0.0:
		var top := LAMP_TL.y - 26.0
		var len := (LAMP_TL.y + 16.0 - top) * _pour
		b.draw_rect(Rect2(WICK.x + 4, top, 1, len), SAP[2])
		b.draw_rect(Rect2(WICK.x + 3, top - 4, 4, 4), SAP[0])
	if _lit and _flame > 0.0:
		_draw_flame(b, WICK, _flame * (1.0 + flick))
	# 卡片
	if _cards_a > 0.0 and hands != null:
		var ca := ceilf(_cards_a * 3.0) / 3.0
		for i in 3:
			var r := Rect2(Vector2(CARD_X[i] - CARD.x * 0.5, CARD_Y), CARD)
			var on := i == _sel and stage == "pick"
			b.draw_rect(r, Color("#c9b58a", ca) if on else Color("#a8946c", ca))
			b.draw_rect(Rect2(r.position, Vector2(r.size.x, 1)), Color("#e2d2a8", ca))
			b.draw_rect(Rect2(r.position + Vector2(0, r.size.y - 1), Vector2(r.size.x, 1)), Color("#6b5430", ca))
			b.draw_texture_rect_region(hands, Rect2(r.position + Vector2(2, -2), Vector2(32, 24)), Rect2(i * 32, 0, 32, 24),
				Color(SHADOW, ca))
			if on:
				b.draw_rect(Rect2(r.position + Vector2(0, r.size.y + 1), Vector2(r.size.x, 2)), Color(HOT[2], ca))


func _draw_flame(b: Control, at: Vector2, k: float) -> void:
	var h := roundf(5.0 * k)
	var outer := PackedVector2Array([at + Vector2(-2, 0), at + Vector2(0, -h), at + Vector2(2, 0), at + Vector2(1, 1), at + Vector2(-1, 1)])
	b.draw_colored_polygon(outer, HOT[2])
	var inner := PackedVector2Array([at + Vector2(-1, 0), at + Vector2(0, -maxf(1.0, h - 2.0)), at + Vector2(1, 0)])
	b.draw_colored_polygon(inner, HOT[3])
