extends "res://scripts/side_kit.gd"
## 第一关支线 1「老松树的松脂」：接松脂（docs/剧情改动/第一关支线_设计.md）。
##
## 画面：老松树树干的特写，正中一道割口，松脂从割口下沿往下滴；底下树根上放着罐子，罐子上一道暖红的刻度线。
## 怎么玩：按住（鼠标左键 / 空格 / E / 回车）= 松脂往下滴，按得越久滴得越快；松手就不滴了（空中还在落的那几滴照样落进去）。
##   落定以后到了线、又没过罐口 = 接好了（盖上盖子）。松手早了不算错，再按住接着接（又从慢的开始）。
##   一直按着、松脂漫过罐口 = 溢出来：罐子黏住甩不掉（晃几下），擦干净重来，算一次失败。
## 放水：失败 FAILS_GIVE 次，或第 ENTER_GIVE 次进 → 自己接（按到差不多就松手，看得见）。
##
## 剧本步骤：{"do": "mechanic", "id": "side_pine"}，可选 "sets": [flag…]、"hint": {zh, en}、
##   "lines": {intro, spill_1（第一次溢出）, give（放水之前）, done}。
## 进度（story.mech_load）：{enter, fails, done}。

const DRIP := Vector2(116, 63)            # 松脂从这里滴下（面板里的像素）
const JAR := Vector2(101, 102)            # 罐子图左上
const IN_X := 3                           # 罐子里面（罐子图里）x 3..26、y 6..33
const IN_W := 24
const IN_TOP := 6
const IN_BOT := 33
const H := 28.0                           # 罐子里面多高（像素）
const LINE := 20.0                        # 刻度线（从罐底往上，jar_front 的 y = 13）
const DROP := 1.0                         # 一滴多少（像素）
const SLOW := 0.42                        # 刚按下去两滴之间隔多久
const FAST := 0.075                       # 按满 RAMP 秒以后
const RAMP := 2.4
const G := 620.0                          # 下落的加速度（像素 / 秒²）
const HINT := {"zh": "按住接松脂，到红线就松手", "en": "Hold to catch the sap. Let go at the red line.", "fr": "Maintiens pour recueillir la sève. Relâche au trait rouge."}
const SAP := [Color("#7d552f"), Color("#a8642e"), Color("#c8823c"), Color("#e8b860"), Color("#f0d28c")]

var stage := ""                           # catch / spill / lid / done
var level_px := 0.0                       # 罐子里有多少（像素高）
var show_px := 0.0                        # 画出来的高度（缓一点追上去）
var holding := false
var _hold_t := 0.0
var _next := 0.0
var drops: Array = []                     # [{y, v}]
var spill := 0.0                          # 漫出来的那一圈 0..1
var _shake := 0.0
var _shake_t := 0.0
var _lid := 0.0                           # 盖子 0（在上面看不见）..1（盖好）
var _wipe := 0.0
var _auto_hold := false


func _init() -> void:
	ID = "side_pine"


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	level = lv
	step = st
	var give := _enter({})
	_build("SidePine", ["pine_panel", "pine_jar_back", "pine_jar_front", "pine_lid"])
	await _fade_in()
	await _lines("intro")
	stage = "catch"
	_set_hint(step.get("hint", HINT))
	while _alive():
		if give or auto_mode:
			if auto_mode and not give and story.auto == "full" and int(s["fails"]) == 0 and not tried.has("spill"):
				tried["spill"] = true
				await _auto_catch(H + 3.0)          # 自动玩（full）：先演一次溢出来
			else:
				if give and not auto_mode:
					await _lines("give")
				await _auto_catch(LINE + 3.0)
		else:
			_accept = true
			await _stage
			_accept = false
		if stage == "spill":
			await _spill()
			if _fail() and not give:
				give = true
			continue
		if stage == "full":
			break
	if not _alive():
		_drop()
		return
	_set_hint({})
	_sfx("box_close", -4.0)
	var tw := _tw()
	tw.tween_property(self, "_lid", 1.0, 0.5 * _k()).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	await tw.finished
	_sfx("small_click")
	await _wait(0.6)
	stage = "done"
	_done()
	await _lines("done")
	await _fade_out()


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


func ff(r: Node, st: Dictionary) -> void:
	_ff_save(r, st)


func check(r: Node, st: Dictionary) -> Array:
	return _check_lines(r, st, ["intro", "spill_1", "give", "done"])


# ----------------------------------------------------------------------- 玩
func _press(e: InputEvent) -> bool:
	if stage != "catch":
		return false
	if is_click(e) or is_ok_key(e):
		if e is InputEventKey and (e as InputEventKey).echo:
			return true
		_hold(e.is_pressed())
		return true
	return false


func _hold(on: bool) -> void:
	if on == holding:
		return
	holding = on
	if on:
		_hold_t = 0.0
		_next = 0.0


func _still_down() -> bool:
	if Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		return true
	for k in [KEY_SPACE, KEY_E, KEY_ENTER, KEY_KP_ENTER, KEY_Z]:
		if Input.is_key_pressed(k):
			return true
	return false


## 自己接：按住，估计「已经在罐子里的 + 还在落的」到了 goal 就松手
func _auto_catch(goal: float) -> void:
	_auto_hold = true
	_hold(true)
	while _alive() and stage == "catch":
		if holding and level_px + drops.size() * DROP >= goal:
			_hold(false)
		await _frame()
	_auto_hold = false


func _tick(dt: float) -> void:
	_shake_t = maxf(0.0, _shake_t - dt)
	show_px = move_toward(show_px, level_px, dt * 30.0)
	if stage != "catch":
		return
	if holding and not _auto_hold and not _still_down():
		_hold(false)              # 按住的时候开了设置（暂停），在设置里松的手：松手事件暂停时收不到
	if holding:
		_hold_t += dt
		_next -= dt
		if _next <= 0.0:
			drops.append({"y": DRIP.y, "v": 20.0})
			_next = lerpf(SLOW, FAST, clampf(_hold_t / RAMP, 0.0, 1.0))
	var surface := JAR.y + IN_BOT + 1 - level_px
	for d in drops.duplicate():
		d["v"] = float(d["v"]) + G * dt
		d["y"] = float(d["y"]) + float(d["v"]) * dt
		if float(d["y"]) >= surface:
			drops.erase(d)
			level_px += DROP
			if randf() < 0.5:
				_sfx("sap_drip", -10.0, randf_range(0.9, 1.15))
	if level_px > H:
		stage = "spill"
		holding = false
		drops.clear()
		_stage.emit("spill")
	elif not holding and drops.is_empty() and level_px >= LINE:
		stage = "full"
		_stage.emit("full")


## 溢出来：漫过罐口、罐子黏住晃几下、擦干净
func _spill() -> void:
	_sfx("sap_drip", -2.0, 0.7)
	var tw := _tw()
	tw.tween_property(self, "spill", 1.0, 0.6 * _k()).set_trans(Tween.TRANS_SINE)
	await tw.finished
	_shake_t = 1.1 * _k()
	_shake = 1.0
	_sfx("pat", -4.0)
	await _wait(0.4)
	_sfx("pat", -6.0, 1.2)
	await _wait(0.8)
	if int(s["fails"]) == 0:
		await _lines("spill_1")
	tw = _tw().set_parallel(true)
	tw.tween_property(self, "spill", 0.0, 0.5 * _k()).set_trans(Tween.TRANS_SINE)
	tw.tween_property(self, "level_px", 0.0, 0.5 * _k()).set_trans(Tween.TRANS_SINE)
	await tw.finished
	show_px = 0.0
	stage = "catch"


# ----------------------------------------------------------------------- 画
func _draw_board(b: Control) -> void:
	b.draw_texture(_tex["pine_panel"], Vector2.ZERO)
	var off := Vector2(roundf(sin(_t * 38.0) * 2.0 * minf(1.0, _shake_t / 0.4)), 0) if _shake_t > 0.0 else Vector2.ZERO
	var jp := JAR + off
	if _tex["pine_jar_back"] != null:
		b.draw_texture(_tex["pine_jar_back"], jp)
	# 罐子里的松脂
	var hpx := int(round(minf(show_px, H)))
	if hpx > 0:
		var top := jp.y + IN_BOT + 1 - hpx
		b.draw_rect(Rect2(jp.x + IN_X, top, IN_W, hpx), SAP[2])
		b.draw_rect(Rect2(jp.x + IN_X, top, 5, hpx), SAP[3])
		b.draw_rect(Rect2(jp.x + IN_X + IN_W - 6, top, 6, hpx), SAP[1])
		b.draw_rect(Rect2(jp.x + IN_X, top, IN_W, 1), SAP[3 if hpx < H else 4])
	if _tex["pine_jar_front"] != null:
		b.draw_texture(_tex["pine_jar_front"], jp)
	# 漫出来：罐口上面鼓一圈，两边往下流
	if spill > 0.0:
		var sx := jp.x + 1
		b.draw_rect(Rect2(sx, jp.y - 1, 28, 3), SAP[2])
		b.draw_rect(Rect2(sx + 2, jp.y - 2, 20, 1), SAP[3])
		var run := int(round(spill * 30.0))
		b.draw_rect(Rect2(sx - 1, jp.y + 1, 2, run), SAP[2])
		b.draw_rect(Rect2(sx + 27, jp.y + 1, 2, int(run * 0.7)), SAP[1])
		b.draw_rect(Rect2(sx + 9, jp.y + 2, 1, int(run * 0.45)), SAP[3])
		# 黏住：罐子底下拉出两根丝
		if _shake_t > 0.0:
			b.draw_line(Vector2(jp.x + 4, jp.y + 36), Vector2(JAR.x + 4, JAR.y + 38), SAP[1])
			b.draw_line(Vector2(jp.x + 24, jp.y + 36), Vector2(JAR.x + 24, JAR.y + 38), SAP[1])
	# 盖子：从罐口上面落下来
	if _lid > 0.0 and _tex["pine_lid"] != null:
		var ly := lerpf(jp.y - 40.0, jp.y - 3.0, _lid)
		b.draw_texture(_tex["pine_lid"], Vector2(jp.x + 2, roundf(ly)))
	# 正在落的松脂（一滴 2×3，落得快拉长一格）
	for d in drops:
		var y := roundf(float(d["y"]))
		var long := 4.0 if float(d["v"]) > 260.0 else 3.0
		b.draw_rect(Rect2(DRIP.x - 1, y - long, 2, long), SAP[3])
		b.draw_rect(Rect2(DRIP.x - 1, y - long, 1, 1), SAP[4])
	# 按住的时候割口下沿那颗鼓起来一点
	if holding:
		b.draw_rect(Rect2(DRIP.x - 2, DRIP.y - 2, 4, 2), SAP[3])
