extends RefCounted
## 第一关支线 4「坡地·鹿的妈妈」的小游戏 side_slope：雾里跟蹄印（docs/剧情改动/第一关支线_设计.md；剧本 data/forest_side_b.json）。
##
## 怎么玩（没有计时、不会输）：
##   坡地起了浓雾，只看得清晨身边一小圈。晨脚下是一个亮着的鹿蹄印（两瓣的那种，art/forest_story/hoofprints.png 那个样子）。
##   每一步，雾里左右各浮出一个脚印：一个是鹿的，另一个是别的东西的（鸟的三趾、兔子的一长条）。雾里还会从鹿那边
##   传来敲树声（左右声道跟着方向）。玩家照常左右走，踩到鹿的那个就亮起来，下一对浮出来；蹄印会拐回头，不是一直往右。
##   走岔了（踩到别的脚印，或者走出这一对的范围）：雾一下子变浓，敲树声从对的那边传来，晨被轻轻送回上一个蹄印，雾再散回去。
##   走岔 max_miss 次（默认 3），剩下的蹄印一个接一个亮起来，晨自己跟着走完。走完了雾散开一点，lines.win 在雾里播
##   （鹿从雾里出来、坦白），播完雾慢慢退掉。
##
## 剧本步骤：{"do": "mechanic", "id": "side_slope", "at": 第一个蹄印的 marker（或 x）, "trail"?: [[对的, 错的, 错的种类]…],
##   "max_miss"?: 3, "sets"?: [走完设的 flag], "lines"?: {start, wrong, auto, win}}
##   trail 每一项：对的蹄印、错的脚印离 at 多少像素，种类 1 = 鸟、2 = 兔子。默认 TRAIL（7 步，拐两次回头）。
##   要求：每一步对的和错的分在晨的两边，中间不夹着这一步的另一个（一维的路，走过去会先踩到夹在中间的那个）。
##   lines：start（雾起来以后）、wrong（第一次走岔）、auto（走岔满了）、win（走完、雾散开一点），都可以不写。
## 进度（story.mech_load）：{i, miss, gave_up, done}：读档回来从第 i 步接着走。

const KIT := preload("res://scripts/river_explore_order.gd")
const ID := "side_slope"
const TRAIL := [[40, -32, 1], [82, 10, 2], [50, 116, 1], [124, 20, 2], [92, 158, 1], [168, 60, 2], [214, 134, 1]]
const MAX_MISS := 3
const PRINTS := "res://art/forest_side/prints.png"
const PW := 5
const PH := 4
const STEP_R := 4.0                     # 晨脚底离脚印多近算踩上
const LOST := 30.0                      # 走出这一对多远算走岔
const FOG_C := Color("#7f988c")         # 和 story_world.gd 的雾一个颜色（偏青绿的灰）
const FOG_R := 64.0                     # 看得清的那一圈（半径，像素）
const FOG_R_THICK := 22.0
const FOG_R_OPEN := 150.0
const FOG_MARGIN := 32.0
const SFX_STEP := "res://audio/sfx/tap.wav"
const SFX_KNOCK := "res://audio/sfx/wood_knock.wav"
const SFX_WRONG := "res://audio/sfx/tree_sway.wav"
const SFX_DONE := "res://audio/sfx/bell_soft.wav"
const HINT := {"zh": "← → / A D：跟着鹿的蹄印走（两瓣的那种）", "en": "← → / A D: follow the deer's hoofprints (the split ones)"}

const FOG_SHADER := """
shader_type canvas_item;
// 坡地小游戏的雾：一整屏雾色，晨身边挖一个看得清的圈；圈的边被噪声搅乱，透明度分档（像素画的硬边）
uniform sampler2D noise_texture : repeat_enable, filter_nearest;
uniform vec2 rect_size = vec2(544.0, 334.0);
uniform vec2 hole = vec2(272.0, 167.0);
uniform float radius = 64.0;
uniform float soft = 44.0;
uniform float density = 0.0;
uniform vec2 world_off = vec2(0.0);
uniform vec2 speed = vec2(5.0, -1.5);
void fragment() {
	vec2 p = floor(UV * rect_size);
	vec2 q = (p + world_off + speed * TIME) / vec2(480.0, 270.0);
	float n = texture(noise_texture, q).r;
	vec2 d = (p - hole) * vec2(1.0, 1.35);
	float r = length(d) + (n - 0.5) * 24.0;
	float e = clamp((r - radius) / soft, 0.0, 1.0);
	float a = density * mix(0.1 + 0.18 * n, 0.8 + 0.2 * n, e);
	a = floor(a * 10.0 + 0.5) / 10.0;
	COLOR = vec4(COLOR.rgb, a);
}
"""


static func trail(st: Dictionary) -> Array:
	var v = st.get("trail", TRAIL)
	return v if v is Array and not (v as Array).is_empty() else TRAIL


static func max_miss(st: Dictionary) -> int:
	return maxi(int(st.get("max_miss", MAX_MISS)), 1)


static func fresh() -> Dictionary:
	return {"i": 0, "miss": 0, "gave_up": false, "done": false}


static func finished(st: Dictionary, s: Dictionary) -> bool:
	return int(s["i"]) >= trail(st).size()


## 这一步的结果：kind = "ok"（踩对）/ "wrong"（走岔）。返回 ok / done / wrong / give_up
static func act(st: Dictionary, s: Dictionary, kind: String) -> String:
	if finished(st, s) or s["gave_up"]:
		return "done"
	if kind == "ok":
		s["i"] = int(s["i"]) + 1
		return "done" if finished(st, s) else "ok"
	s["miss"] = int(s["miss"]) + 1
	if int(s["miss"]) >= max_miss(st):
		s["gave_up"] = true
		return "give_up"
	return "wrong"


## 晨站在 x 上：这一步算什么。cur = 上一个蹄印、c = 对的、d = 错的（都是世界 x）。"" = 还在找
static func judge(x: float, cur: float, c: float, d: float) -> String:
	if absf(x - c) <= STEP_R:
		return "ok"
	if absf(x - d) <= STEP_R:
		return "wrong"
	if x < minf(minf(c, d), cur) - LOST or x > maxf(maxf(c, d), cur) + LOST:
		return "wrong"
	return ""


class Ticker extends Node:
	var f: Callable

	func _process(delta: float) -> void:
		if f.is_valid():
			f.call(delta)


# ======================================================================= 演出
signal chosen(kind: String)

var auto_mode := false
var story: Node
var level: Node2D
var step: Dictionary
var s: Dictionary
var chen: Node2D
var playing := false
var x0 := 0.0
var _cur := 0.0
var _c := 0.0
var _d := 0.0
var _auto_wrong := 0
var _tick: Ticker
var _fog: Node2D
var _fog_rect: ColorRect
var _fog_mat: ShaderMaterial
var _fog_density := 0.0
var _fog_r := FOG_R
var _fog_tw: Tween
var _prints: Node2D
var _cand: Array = []                   # 这一对 [对的, 错的]（Sprite2D）
var _tex: Texture2D
var _hint: CanvasLayer
var _hint_shown := false
var _was_input := true
var _said_wrong := false


func run(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	level = lv
	story = r
	step = st
	s = story.mech_load(ID)
	if not s.has("i"):
		s = fresh()
	await _setup()
	await _lines("start")
	var tr := trail(step)
	while not story.ended and not finished(step, s):
		if s["gave_up"]:
			await _auto_rest()
			break
		var i := int(s["i"])
		_cur = x0 + (0.0 if i == 0 else float(tr[i - 1][0]))
		_c = x0 + float(tr[i][0])
		_d = x0 + float(tr[i][1])
		_show_pair(int(tr[i][2]))
		_knock(_c)
		var kind: String = await _choose()
		var res := act(step, s, kind)
		story.mech_save(ID, s)
		if res in ["ok", "done"]:
			_step_ok()
			await _wait(0.35)
			continue
		await _went_wrong()
		if res == "wrong" and not _said_wrong:
			_said_wrong = true
			await _lines("wrong")
		elif res == "give_up":
			await _lines("auto")
	s["done"] = true
	story.mech_save(ID, s)
	_set_flags(step)
	await _finish()
	print("MECH %s done miss=%d gave_up=%s" % [ID, int(s["miss"]), str(s["gave_up"])])


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	_auto_wrong = int(st.get("auto_wrong", 1 if r.auto == "full" else 0))
	await run(lv, w, r, st)


func ff(r: Node, st: Dictionary) -> void:
	var t := fresh()
	t["i"] = trail(st).size()
	t["done"] = true
	r.mech_save(ID, t)
	_set_flags(st)


static func _set_flags(st: Dictionary) -> void:
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))


## 等玩家走到一个结果（自动玩：先故意走岔 auto_wrong 次，再走对的）
func _choose() -> String:
	if auto_mode:
		if _auto_wrong > 0:
			_auto_wrong -= 1
			await _walk(_d)
			return "wrong"
		await _walk(_c)
		return "ok"
	_set_playing(true)
	var k: String = await chosen
	_set_playing(false)
	return k


func _on_tick(_delta: float) -> void:
	_fog_follow()
	if not playing or chen == null:
		return
	if not chen.input_enabled:
		chen.input_enabled = true
	var k := judge(chen.position.x, _cur, _c, _d)
	if k != "":
		playing = false
		chosen.emit(k)


func _set_playing(on: bool) -> void:
	playing = on and not auto_mode
	if chen != null:
		chen.input_enabled = playing
	if playing and not _hint_shown:
		_hint_shown = true
		_show_hint(true)


# ----------------------------------------------------------------------- 一步
func _step_ok() -> void:
	_show_hint(false)
	_sfx(SFX_STEP, -8.0, 0.62 + 0.03 * float(s["i"]))
	if _cand.size() >= 2:
		_print_lit(_cand[0])
		_print_out(_cand[1], 0.4)
	_cand = []


## 走岔：雾一下子变浓，对的那边敲两下，晨被轻轻送回上一个蹄印，雾再散回去
func _went_wrong() -> void:
	_sfx(SFX_WRONG, -16.0, 1.2)
	if _cand.size() >= 2:
		_print_out(_cand[0], 0.5)
		_print_out(_cand[1], 0.5)
	_cand = []
	_fog_to(1.0, FOG_R_THICK, 0.8)
	await _wait(0.8)
	_knock(_c)
	await _wait(0.5)
	await _walk(_cur)
	_fog_to(0.9, FOG_R, 1.0)
	await _wait(0.6)
	# 同一对再浮出来
	var tr := trail(step)
	_show_pair(int(tr[int(s["i"])][2]))


## 走岔满了：剩下的蹄印一个接一个亮起来，晨自己跟着走完
func _auto_rest() -> void:
	var tr := trail(step)
	for i in range(int(s["i"]), tr.size()):
		var x := x0 + float(tr[i][0])
		var p := _print_at(x, 0)
		_print_in(p)
		_knock(x)
		await _wait(0.5)
		await _walk(x)
		_print_lit(p)
		_sfx(SFX_STEP, -8.0, 0.62 + 0.03 * float(i))
		s["i"] = i + 1
		story.mech_save(ID, s)
		await _wait(0.3)


func _finish() -> void:
	_show_hint(false)
	_sfx(SFX_DONE, -16.0, 0.9)
	_fog_to(0.75, FOG_R_OPEN, 2.0)
	await _wait(1.6)
	await _lines("win")
	_fog_to(0.0, FOG_R_OPEN, 2.0)
	await _wait(2.0)
	_teardown()


func _walk(x: float) -> void:
	await story.run_steps([{"do": "walk", "who": "chen", "to": round(x), "pace": "walk"}])


# ----------------------------------------------------------------------- 摆人、雾
func _setup() -> void:
	chen = story.chen
	if step.has("at") and story.world != null and story.world.has_method("resolve"):
		var at = story.world.resolve(step["at"])
		x0 = float(at.get("x", chen.position.x)) if at is Dictionary else float(step["at"])
	elif step.has("at") and (step["at"] is float or step["at"] is int):
		x0 = float(step["at"])
	else:
		x0 = chen.position.x if chen != null else 0.0
	if chen != null:
		_was_input = chen.input_enabled
		chen.input_enabled = false
	_tex = _load_tex(PRINTS)
	_prints = Node2D.new()
	_prints.name = "SideSlopePrints"
	level.add_child(_prints)
	if chen != null and chen.get_parent() == level:
		level.move_child(_prints, chen.get_index())       # 画在晨脚底下
	_make_fog()
	_tick = Ticker.new()
	_tick.f = _on_tick
	level.add_child(_tick)
	_fog_follow()
	_fog_to(0.9, FOG_R, 1.6)
	if chen != null and absf(chen.position.x - x0) > 1.0:
		await _walk(x0)
	await _wait(1.0)
	# 晨脚下第一个蹄印（读档回来：已经走过的都亮着）
	var tr := trail(step)
	_print_lit(_print_at(x0, 0), true)
	for i in int(s["i"]):
		_print_lit(_print_at(x0 + float(tr[i][0]), 0), true)
	if int(s["i"]) > 0 and chen != null:
		await _walk(x0 + float(tr[int(s["i"]) - 1][0]))
	await _wait(0.4)


func _teardown() -> void:
	playing = false
	_show_hint(false)
	if _tick != null:
		_tick.queue_free()
		_tick = null
	if _fog != null:
		_fog.queue_free()
		_fog = null
	if _prints != null:
		var pr := _prints
		_prints = null
		var tw := pr.create_tween()
		tw.tween_interval(2.0)
		tw.tween_method(func(v: float): pr.modulate.a = ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, 1.2)
		tw.tween_callback(pr.queue_free)
	if chen != null:
		chen.input_enabled = _was_input


func _make_fog() -> void:
	_fog = Node2D.new()
	_fog.name = "SideSlopeFog"
	_fog.z_as_relative = false
	_fog.z_index = 90
	level.add_child(_fog)
	var nz := FastNoiseLite.new()
	nz.seed = 4350
	nz.frequency = 0.012
	var tex := NoiseTexture2D.new()
	tex.width = 480
	tex.height = 270
	tex.seamless = true
	tex.noise = nz
	var sh := Shader.new()
	sh.code = FOG_SHADER
	_fog_mat = ShaderMaterial.new()
	_fog_mat.shader = sh
	_fog_mat.set_shader_parameter("noise_texture", tex)
	_fog_mat.set_shader_parameter("density", 0.0)
	_fog_rect = ColorRect.new()
	_fog_rect.color = FOG_C
	_fog_rect.size = Vector2(480.0 + 2.0 * FOG_MARGIN, 270.0 + 2.0 * FOG_MARGIN)
	_fog_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fog_rect.material = _fog_mat
	_fog_mat.set_shader_parameter("rect_size", _fog_rect.size)
	_fog.add_child(_fog_rect)


## 雾跟着镜头（一整屏多一圈），圈跟着晨的胸口
func _fog_follow() -> void:
	if _fog == null:
		return
	var cc := Vector2(240, 135)
	var vp := story.get_viewport()
	var cam := vp.get_camera_2d() if vp != null else null
	if cam != null:
		cc = cam.get_screen_center_position()
	elif chen != null:
		cc = Vector2(chen.position.x, 135)
	var tl := (cc - Vector2(240, 135) - Vector2(FOG_MARGIN, FOG_MARGIN)).round()
	_fog.position = tl
	var hole := Vector2(240, 135) + Vector2(FOG_MARGIN, FOG_MARGIN)
	if chen != null:
		hole = (chen.position - Vector2(0, 24) - tl).round()
	_fog_mat.set_shader_parameter("hole", hole)
	_fog_mat.set_shader_parameter("world_off", tl)
	_fog_mat.set_shader_parameter("radius", _fog_r)
	_fog_mat.set_shader_parameter("density", _fog_density)


## 雾慢慢变到这个浓度 / 圈的大小（正弦缓起缓停）
func _fog_to(density: float, r: float, sec: float) -> void:
	if _fog_tw != null and _fog_tw.is_valid():
		_fog_tw.kill()
	if _fog == null:
		return
	var d0 := _fog_density
	var r0 := _fog_r
	_fog_tw = _fog.create_tween()
	_fog_tw.tween_method(func(v: float):
		var e := 0.5 - 0.5 * cos(PI * v)
		_fog_density = lerpf(d0, density, e)
		_fog_r = lerpf(r0, r, e), 0.0, 1.0, maxf(0.01, sec * (0.25 if auto_mode else 1.0)))


# ----------------------------------------------------------------------- 脚印
func _show_pair(kind: int) -> void:
	var a := _print_at(_c, 0)
	var b := _print_at(_d, clampi(kind, 1, 2))
	_print_in(a)
	_print_in(b)
	_cand = [a, b]


func _print_at(x: float, kind: int) -> Sprite2D:
	var p := Sprite2D.new()
	p.centered = false
	p.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	if _tex != null:
		var at := AtlasTexture.new()
		at.atlas = _tex
		at.region = Rect2(kind * PW, 0, PW, PH)
		p.texture = at
	p.set_meta("kind", kind)
	var gy := _ground(x)
	p.position = Vector2(round(x) - 2.0, round(gy) - 1.0)
	if _prints != null:
		_prints.add_child(p)
	return p


## 浮出来：4 档淡入
func _print_in(p: Sprite2D) -> void:
	p.modulate.a = 0.0
	var tw := p.create_tween()
	tw.tween_method(func(v: float): p.modulate.a = floorf(v * 4.0) / 4.0, 0.0, 1.0, 0.6 * (0.25 if auto_mode else 1.0))


func _print_out(p: Sprite2D, sec: float) -> void:
	if not is_instance_valid(p):
		return
	var tw := p.create_tween()
	tw.tween_method(func(v: float): p.modulate.a = ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, sec)
	tw.tween_callback(p.queue_free)


## 踩对了：换成亮的那一行（暖光）
func _print_lit(p: Sprite2D, now := false) -> void:
	if not is_instance_valid(p):
		return
	if p.texture is AtlasTexture:
		(p.texture as AtlasTexture).region = Rect2(int(p.get_meta("kind")) * PW, PH, PW, PH)
	if now:
		p.modulate.a = 1.0


func _ground(x: float) -> float:
	if story.world != null and story.world.has_method("ground_at"):
		return float(story.world.ground_at(x))
	return chen.position.y if chen != null else 228.0


# ----------------------------------------------------------------------- 声音、提示
## 鹿在雾里敲树：放在对的那个蹄印再往外一点（左右声道跟着方向）
func _knock(x: float) -> void:
	if level == null or not ResourceLoader.exists(SFX_KNOCK):
		return
	var a := AudioStreamPlayer2D.new()
	a.stream = load(SFX_KNOCK)
	a.bus = "SFX" if AudioServer.get_bus_index("SFX") >= 0 else "Master"
	a.volume_db = -6.0 + float(step.get("sfx_db", 0.0))
	a.max_distance = 600.0
	var sg := 1.0 if chen == null or x >= chen.position.x else -1.0
	a.position = Vector2(x + sg * 90.0, (chen.position.y if chen != null else 200.0) - 30.0)
	level.add_child(a)
	a.play()
	a.finished.connect(a.queue_free)


func _sfx(path: String, db: float, pitch: float) -> void:
	if level == null or not ResourceLoader.exists(path):
		return
	var a := AudioStreamPlayer.new()
	a.stream = load(path)
	a.bus = "SFX" if AudioServer.get_bus_index("SFX") >= 0 else "Master"
	a.volume_db = db + float(step.get("sfx_db", 0.0))
	a.pitch_scale = pitch
	level.add_child(a)
	a.play()
	a.finished.connect(a.queue_free)


func _show_hint(on: bool) -> void:
	if auto_mode or level == null:
		return
	if on and _hint == null:
		_hint = CanvasLayer.new()
		_hint.layer = 5
		level.add_child(_hint)
		var lb := Label.new()
		lb.text = story.txt(HINT) if story.has_method("txt") else str(HINT["zh"])
		lb.add_theme_font_override("font", UITheme.font())
		lb.add_theme_font_size_override("font_size", 14)
		lb.add_theme_color_override("font_color", UITheme.TEXT_DIM)
		lb.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lb.position = Vector2(0, 236)
		lb.size = Vector2(480, 16)
		lb.modulate.a = 0.0
		_hint.add_child(lb)
		var tw := lb.create_tween()
		tw.tween_method(func(v: float): lb.modulate.a = floorf(v * 4.0) / 4.0, 0.0, 1.0, 0.6)
	elif not on and _hint != null:
		var h := _hint
		_hint = null
		var lb: Label = h.get_child(0)
		var tw := lb.create_tween()
		tw.tween_method(func(v: float): lb.modulate.a = ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, 0.5)
		tw.tween_callback(h.queue_free)


func _lines(key: String) -> void:
	var l: Dictionary = step.get("lines", {})
	if l.get(key) is Array and not (l[key] as Array).is_empty():
		await story.run_steps(l[key])


func _wait(sec: float) -> void:
	await story.get_tree().create_timer(sec * (0.25 if auto_mode else 1.0)).timeout


static func _load_tex(p: String) -> Texture2D:
	if ResourceLoader.exists(p):
		return load(p)
	if FileAccess.file_exists(p):
		var img := Image.load_from_file(ProjectSettings.globalize_path(p))
		if img != null and not img.is_empty():
			return ImageTexture.create_from_image(img)
	return null


# ----------------------------------------------------------------------- --story_check
func check(story: Node, st: Dictionary) -> Array:
	var out: Array = []
	if st.has("at") and st["at"] is String and not story.world.has_marker(str(st["at"])):
		out.append("at 的 marker %s 找不到" % st["at"])
	var tr = st.get("trail", TRAIL)
	if not tr is Array or (tr as Array).is_empty():
		out.append("trail 要是 [[对的, 错的, 种类]…]")
	else:
		var cur := 0.0
		for i in (tr as Array).size():
			var e = tr[i]
			if not e is Array or (e as Array).size() < 3:
				out.append("trail[%d] 要写 [对的, 错的, 种类]" % i)
				continue
			var c := float(e[0])
			var d := float(e[1])
			if (c - cur) * (d - cur) >= 0.0:
				out.append("trail[%d]：对的和错的要分在上一个蹄印的两边" % i)
			if not int(e[2]) in [1, 2]:
				out.append("trail[%d]：种类要是 1（鸟）或 2（兔子）" % i)
			cur = c
	if not FileAccess.file_exists(PRINTS):
		out.append("脚印图 %s 还没有" % PRINTS)
	for k in st.get("lines", {}):
		out.append_array(KIT.check_steps(story, "lines.%s" % k, st["lines"][k]))
	return out
