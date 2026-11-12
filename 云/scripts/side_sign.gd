extends "res://scripts/side_kit.gd"
## 第一关支线 2b「路标送回空地」：按停（docs/剧情改动/第一关支线_设计.md）。
##
## 画面：从上往下看空地，正中树桩底座上插着路标，路标的箭头一直在转；一圈八个方向各有一个地方的小图标
##   （云 / 老松 / 树屋 / 雾 / 你 / 小吃棚 / 空地 / 商店，art/forest_side/sign_icons.png 的顺序，顺时针、从正上开始）。
## 怎么玩：按一下（鼠标左键 / 空格 / E / 回车）= 刹住：箭头匀减速再转 BRAKE 弧度才停（要提前按），停在哪格指哪格。
##   要停在「空地」那格。停错了它又慢慢转起来。
## 笑点：头 RIG 次不管什么时候按，它刹着刹着都会多拐一点，指着「你」（晨站的那边）。然后播 lines.chen
##   （旁白「它好像觉得你就是路。」+ 选项）。选项的 scene == step 的 "follow_scene" → 路标从底座上蹦出来、
##   一跳一跳地往「你」那边跟过来，然后被插回去（咚）。之后它就老实了。
## 放水：老实以后停错 FAILS_GIVE 次，或第 ENTER_GIVE 次进 → 它自己慢慢停到空地。
##
## 剧本步骤：{"do": "mechanic", "id": "side_sign"}，可选 "sets"、"hint"、"follow_scene"、
##   "lines": {intro, chen（指着你的那两次以后）, followed（跟着跳完、插回去以后）, miss_1（第一次停错）, give, done}。
## 进度：{enter, fails, joke（笑点演过没有）, done}。

const C := Vector2(116, 75)               # 底座中心（面板里）
const R := 56.0                           # 图标离中心多远
const N := 8
const TARGET := 6                         # 空地
const YOU := 4                            # 你
const OMEGA := TAU / 1.6                  # 转速（弧度 / 秒）
const BRAKE := 1.6                        # 按下以后还要转多少才停（匀减速）
const RIG := 2
const SPIN_UP := 0.9                      # 停下以后多久转回全速
const NAMES := [
	{"zh": "云那边", "en": "Clouds", "fr": "Nuages"}, {"zh": "老松", "en": "Old pine", "fr": "Vieux pin"}, {"zh": "树屋", "en": "Treehouse", "fr": "Cabane"},
	{"zh": "雾", "en": "Fog", "fr": "Brume"}, {"zh": "你", "en": "You", "fr": "Toi"}, {"zh": "小吃棚", "en": "Snack stall", "fr": "Buvette"},
	{"zh": "空地", "en": "Clearing", "fr": "Clairière"}, {"zh": "商店", "en": "Shop", "fr": "Boutique"}]
const HINT := {"zh": "按一下刹住，让它指着空地", "en": "Press to brake. Make it point at the Clearing.", "fr": "Appuie pour freiner. Fais-le pointer vers la clairière."}
const WOOD := [Color("#2c2118"), Color("#4d3a2a"), Color("#634a34"), Color("#7a5c40"), Color("#94744f")]
const GRASS_DARK := Color("#16241c")
const WARM := Color("#e8795a")

var stage := ""                           # spin / brake / stopped / hop / done
var a := 0.0                              # 箭头的角度（顺时针，0 = 指正上）
var w := OMEGA
var _from := 0.0
var _to := 0.0
var _bt := 0.0
var _bdur := 0.0
var _stops := 0
var _landed := -1
var _pos := C                             # 路标在哪（跳的时候离开底座）
var _hop := 0.0                           # 离地多高
var _dust: Array = []
var _shown := -1


func _init() -> void:
	ID = "side_sign"


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	level = lv
	step = st
	var give := _enter({"joke": false})
	if not s.has("joke"):
		s["joke"] = false
	_build("SideSign", ["sign_panel", "sign_icons"])
	a = randf_range(0.0, TAU)
	await _fade_in()
	await _lines("intro")
	stage = "spin"
	_set_hint(step.get("hint", HINT))
	while _alive():
		var rig: bool = not s["joke"] and _stops < RIG
		var hit := -1
		if auto_mode or (give and not rig):
			if give and not auto_mode and not tried.has("give_line"):
				tried["give_line"] = true
				await _lines("give")
			hit = await _auto_stop(rig, give)
		else:
			_accept = true
			await _stage
			_accept = false
			hit = _landed
		if not _alive():
			break
		_stops += 1
		if rig:
			await _wait(0.5)
			if _stops >= RIG:
				await _joke()
			await _spin_up()
			continue
		if hit == TARGET:
			break
		await _wait(0.5)
		if int(s["fails"]) == 0:
			await _lines("miss_1")
		if _fail():
			give = true
		await _spin_up()
	if not _alive():
		_drop()
		return
	_set_hint({})
	_sfx("wood_knock", -2.0)
	await _wait(1.0)
	stage = "done"
	_done()
	await _lines("done")
	await _fade_out()


func auto(lv: Node2D, w0: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w0, r, st)


func ff(r: Node, st: Dictionary) -> void:
	_ff_save(r, st, {"joke": true})


func check(r: Node, st: Dictionary) -> Array:
	var out := _check_lines(r, st, ["intro", "chen", "followed", "miss_1", "give", "done"])
	if st.has("follow_scene") and r.get("scenes") is Dictionary and not (r.get("scenes") as Dictionary).has(str(st["follow_scene"])):
		out.append("follow_scene %s 不是一个 scene" % str(st["follow_scene"]))
	return out


# ----------------------------------------------------------------------- 玩
func _press(e: InputEvent) -> bool:
	if stage != "spin":
		return false
	if (is_click(e) or is_ok_key(e)) and e.is_pressed() and not (e is InputEventKey and (e as InputEventKey).echo):
		_brake(not s["joke"] and _stops < RIG)
		return true
	return false


static func sector(ang: float) -> int:
	return posmod(int(roundf(ang / (TAU / N))), N)


## 刹住：匀减速转 BRAKE 停下。rig = 不管停在哪，多拐一点停到「你」
func _brake(rig: bool) -> void:
	stage = "brake"
	_from = a
	_to = a + BRAKE
	if rig:
		var you := YOU * TAU / N
		var k := ceilf((a + BRAKE * 0.75 - you) / TAU)
		_to = you + k * TAU
	_bt = 0.0
	_bdur = 2.0 * (_to - _from) / OMEGA      # 匀减速：平均速度 = 一半
	_sfx("tick", -6.0)


func _tick(dt: float) -> void:
	match stage:
		"spin":
			w = move_toward(w, OMEGA, dt * OMEGA / SPIN_UP)
			a += w * dt
		"brake":
			_bt = minf(_bt + dt, _bdur)
			var u := _bt / _bdur
			a = _from + (_to - _from) * (1.0 - (1.0 - u) * (1.0 - u))
			var cur := sector(a)
			if cur != _shown:
				_shown = cur
				if u > 0.5:
					_sfx("tick", -14.0, 1.0 + 0.4 * u)
			if _bt >= _bdur:
				stage = "stopped"
				w = 0.0
				_landed = sector(a)
				_sfx("small_click", -2.0)
				_stage.emit("stopped")
	for d in _dust.duplicate():
		d["t"] = float(d["t"]) + dt
		if float(d["t"]) > 0.5:
			_dust.erase(d)


func _spin_up() -> void:
	if stage == "done":
		return
	w = 0.0
	stage = "spin"
	_sfx("wood_knock", -12.0, 1.3)


## 自己按：等到「再转 BRAKE 正好到空地」那一刻按（rig 的时候随便哪一刻按都一样）
func _auto_stop(rig: bool, give: bool) -> int:
	if give and not auto_mode:
		await _wait(0.6)
	var goal := TARGET * TAU / N
	if not rig and auto_mode and story.auto == "full" and not tried.has("miss"):
		tried["miss"] = true
		goal += TAU / N * 2.0                # 自动玩（full）：先停错一次
	if rig:
		await _wait(randf_range(0.5, 0.9))
	else:
		while _alive() and stage == "spin":
			if w >= OMEGA * 0.999:
				var lead := fposmod(goal - (a + BRAKE), TAU)
				if lead < w * 0.03:
					break
			await _frame()
	if not _alive():
		return -1
	_brake(rig)
	await _stage
	return _landed


## 指着你两次以后：旁白 + 选项；选了「那就跟我走吧」就跳过来再被插回去
func _joke() -> void:
	s["joke"] = true
	_save()
	var res: String = await _lines("chen")
	var fol := str(step.get("follow_scene", ""))
	if fol != "" and res == fol:
		await _follow()
		await _lines("followed")


func _follow() -> void:
	stage = "hop"
	var spots := [C + Vector2(0, 18), C + Vector2(-2, 34), C + Vector2(1, 50)]
	for p in spots:
		var start := _pos
		var tw := _tw()
		tw.tween_method(func(u: float):
			_pos = start.lerp(p, u)
			_hop = sin(u * PI) * 12.0, 0.0, 1.0, 0.42).set_trans(Tween.TRANS_LINEAR)
		await tw.finished
		_hop = 0.0
		_sfx("wood_knock", -4.0, randf_range(1.1, 1.3))
		_puff(_pos, 3)
		await _wait(0.25)
	await _wait(0.7)
	# 被插回去：一道弧线飞回底座，「咚」
	var back := _pos
	var tw2 := _tw()
	tw2.tween_method(func(u: float):
		_pos = back.lerp(C, u)
		_hop = sin(u * PI) * 22.0, 0.0, 1.0, 0.55).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tw2.finished
	_hop = 0.0
	_pos = C
	_sfx("thud", 0.0)
	_puff(C, 6)
	await _wait(0.6)
	stage = "stopped"


func _puff(at: Vector2, n: int) -> void:
	for i in n:
		var ang := TAU * float(i) / float(n) + randf_range(-0.3, 0.3)
		_dust.append({"p": at, "d": Vector2(cos(ang), sin(ang)), "t": 0.0})


# ----------------------------------------------------------------------- 画
func _draw_board(b: Control) -> void:
	b.draw_texture(_tex["sign_panel"], Vector2.ZERO)
	var icons: Texture2D = _tex["sign_icons"]
	var pointed := sector(a) if stage in ["stopped", "done", "brake"] else -1
	for i in N:
		var ang := i * TAU / N
		var p := (C + Vector2(sin(ang), -cos(ang)) * R).round()
		if icons != null:
			b.draw_texture_rect_region(icons, Rect2(p - Vector2(8, 8), Vector2(16, 16)), Rect2(i * 16, 0, 16, 16))
		if i == TARGET or (i == pointed and stage != "brake"):
			var col := WARM if i == TARGET else UITheme.TEXT
			var t: String = I18n.pick(NAMES[i])
			var tw := UITheme.font().get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
			var lx := p.x + 11.0 if sin(ang) >= -0.1 else p.x - 11.0 - tw
			if absf(sin(ang)) < 0.2:
				lx = p.x + 11.0
			_text(b, Vector2(roundf(lx), p.y + 5), t, col, tw + 2.0, HORIZONTAL_ALIGNMENT_LEFT)
	for d in _dust:
		var u := float(d["t"]) / 0.5
		var q: Vector2 = (d["p"] as Vector2) + (d["d"] as Vector2) * (4.0 + 10.0 * u)
		b.draw_rect(Rect2(q.round(), Vector2(2, 2) if u < 0.5 else Vector2(1, 1)), Color("#3a3d2a"))
	_draw_arm(b, _pos, a, _hop)


## 箭头（从上往下看的一块木板）：先画地上的影子，再画板子；离地越高影子离得越远。朝左上那一半亮一档
func _draw_arm(b: Control, at: Vector2, ang: float, h: float) -> void:
	var u := Vector2(sin(ang), -cos(ang))
	var p := Vector2(u.y * -1.0, u.x)
	var shape := [u * -7 + p * 3.5, u * 33 + p * 3.5, u * 33 + p * 6.5, u * 44, u * 33 - p * 6.5, u * 33 - p * 3.5, u * -7 - p * 3.5]
	var lift := Vector2(-0.5, -1.0) * h
	var sh := PackedVector2Array()
	for q in shape:
		sh.append((at + q + Vector2(2, 2)).round())
	b.draw_colored_polygon(sh, GRASS_DARK)
	var top := PackedVector2Array()
	var half_a := PackedVector2Array()
	var half_b := PackedVector2Array()
	for q in shape:
		top.append((at + lift + q).round())
	b.draw_colored_polygon(top, WOOD[2])
	# 朝光那一半：中线一侧
	var lightside := 1.0 if p.dot(Vector2(-1, -1)) > 0.0 else -1.0
	for q in [u * -7, u * 44, u * 33 + p * 6.5 * lightside, u * 33 + p * 3.5 * lightside, u * -7 + p * 3.5 * lightside]:
		half_a.append((at + lift + q).round())
	b.draw_colored_polygon(half_a, WOOD[3])
	for q in [u * 30 + p * 2.0 * lightside, u * 41, u * 33 + p * 4.5 * lightside]:
		half_b.append((at + lift + q).round())
	b.draw_colored_polygon(half_b, WOOD[4])
	b.draw_circle((at + lift).round(), 3.5, WOOD[1])
	b.draw_circle((at + lift).round() + Vector2(-1, -1), 1.5, WOOD[3])
