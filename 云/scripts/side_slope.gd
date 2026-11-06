extends RefCounted
## 第一关支线 4「坡地·鹿的妈妈」的小游戏 side_slope：雾里跟蹄印（docs/剧情改动/第一关支线_设计.md；剧本 data/forest_side_b.json）。
##
## 怎么玩（没有计时、不会输；11-04 作者「不太明白这个游戏咋玩」以后改成一眼看懂的）：
##   坡地起了浓雾，只看得清晨身边一圈。晨脚下一个亮着的蹄印。雾里只有「下一个」蹄印在发光（暖色、一明一暗地呼吸，
##   画在雾上面，所以远一点也看得见）；别的都不亮。玩家照常左右走，踩上发光的那个：叮一声，它留下来亮着（暖色、不呼吸），
##   再下一个在更远的雾里亮起来。蹄印会拐一次回头。每踩对一个，雾就薄一点、看得清的圈大一点（走得越远越亮堂）。
##   走反了（离开上一个蹄印、往没有蹄印的那边走出 LOST 像素）：晨身边的雾一下子变浓，潜意识字「不是这边……」，
##   晨被轻轻走回上一个亮着的蹄印（走回去，不瞬移），雾再散回去。走反 max_miss 次（默认 3）：剩下的蹄印一个接一个亮起来，
##   晨自己跟着走完。走完雾散开一大圈，lines.win 播（鹿从前面的雾里走出来、坦白），播完雾慢慢退掉。
##
## 剧本步骤：{"do": "mechanic", "id": "side_slope", "at": 第一个蹄印的 marker（或 x）, "trail"?: [离 at 多少像素…],
##   "max_miss"?: 3, "sets"?: [走完设的 flag], "wrong_inner"?: {zh, en}, "lines"?: {start, wrong, auto, win}}
##   trail：后面每个蹄印离 at 多远（第一个就在 at，不写进去）。默认 TRAIL（7 个，第三个往回拐）。
##   lines：start（雾起来、第一个发光的蹄印出来以后，比如一句潜意识字）、wrong（第一次走反，「不是这边」之后）、
##   auto（走反满了）、win（走完、雾散开），都可以不写。
## 进度（story.mech_load）：{i, miss, gave_up, done}：读档回来从第 i 个接着走。
## 图：art/forest_side/hoof_trail.png（13×5 三格：踩过的 / 下一个 / 暗）、hoof_glow.png（下一个上方那团光），
##   art/forest_side/src/side_b_art.py 画的（同一个脚本还能出游戏尺寸的示意图 trail_mock）。

const OL := preload("res://scripts/overlay_layout.gd")
const KIT := preload("res://scripts/river_explore_order.gd")
const ID := "side_slope"
const TRAIL := [34, 70, 50, 90, 130, 172, 212]
const MAX_MISS := 3
const HOOF := "res://art/forest_side/hoof_trail.png"
const GLOW := "res://art/forest_side/hoof_glow.png"
const PW := 13
const PH := 5
const CELL_LIT := 0
const CELL_NEXT := 1
const STEP_R := 5.0                     # 晨脚底离蹄印多近算踩上
const LOST := 34.0                      # 往没有蹄印的那边走出多远算走反
const PULSE_SEC := 1.6                  # 下一个蹄印呼吸一次
const FOG_C := Color("#7f988c")         # 和 story_world.gd 的雾一个颜色（偏青绿的灰）
const FOG_START := Vector2(0.92, 56.0)  # 刚进雾：[浓度, 看得清的圈半径]
const FOG_END := Vector2(0.62, 100.0)   # 快走完：雾薄了、圈大了
const FOG_THICK := Vector2(1.0, 20.0)   # 走反：一下子浓
const FOG_WIN := Vector2(0.5, 110.0)    # 走完：散开（鹿从圈外的雾里走进来）
const FOG_MARGIN := 32.0
const SFX_CHIME := "res://audio/sfx/bell_soft.wav"
const SFX_STEP := "res://audio/sfx/tap.wav"
const SFX_WRONG := "res://audio/sfx/tree_sway.wav"
const WRONG_INNER := {"zh": "不是这边……", "en": "Not this way..."}
const HINT := {"zh": "← → / A D：踩着发光的蹄印走", "en": "← → / A D: step on the glowing hoofprint"}

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
	if not v is Array or (v as Array).is_empty():
		v = TRAIL
	var out: Array = []
	for e in v:
		out.append(float(e[0]) if e is Array else float(e))    # 旧写法 [[对的, 错的, 种类]…] 也认，只取对的
	return out


static func max_miss(st: Dictionary) -> int:
	return maxi(int(st.get("max_miss", MAX_MISS)), 1)


static func fresh() -> Dictionary:
	return {"i": 0, "miss": 0, "gave_up": false, "done": false}


static func finished(st: Dictionary, s: Dictionary) -> bool:
	return int(s["i"]) >= trail(st).size()


## 这一步的结果：kind = "ok"（踩对）/ "wrong"（走反）。返回 ok / done / wrong / give_up
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


## 晨站在 x 上：cur = 上一个亮着的蹄印、c = 下一个（都是世界 x）。"ok" 踩上了 / "wrong" 走反了 / "" 还在走
static func judge(x: float, cur: float, c: float) -> String:
	if absf(x - c) <= STEP_R:
		return "ok"
	if (c >= cur and x < cur - LOST) or (c < cur and x > cur + LOST):
		return "wrong"
	return ""


## 第 i 步的雾（越往后越薄）：[浓度, 圈半径]
static func fog_at(st: Dictionary, i: int) -> Vector2:
	var n := maxi(trail(st).size() - 1, 1)
	return FOG_START.lerp(FOG_END, clampf(float(i) / float(n), 0.0, 1.0))


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
var _auto_wrong := 0
var _tick: Ticker
var _fog: Node2D
var _fog_rect: ColorRect
var _fog_mat: ShaderMaterial
var _fog_density := 0.0
var _fog_r := FOG_START.y
var _fog_tw: Tween
var _prints: Node2D                     # 踩过的（雾下面，只在晨身边那圈里看得见）
var _beacon: Node2D                     # 下一个（雾上面：光 + 蹄印）
var _glow: Sprite2D
var _pulse_t := 0.0
var _tex: Texture2D
var _glow_tex: Texture2D
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
	var tr := trail(step)
	var first := true
	while not story.ended and not finished(step, s):
		if s["gave_up"]:
			await _auto_rest()
			break
		var i := int(s["i"])
		_cur = x0 + (0.0 if i == 0 else float(tr[i - 1]))
		_c = x0 + float(tr[i])
		_beacon_at(_c)
		if first:
			first = false
			await _wait(0.5)
			await _lines("start")
		var kind: String = await _choose()
		var res := act(step, s, kind)
		story.mech_save(ID, s)
		if res in ["ok", "done"]:
			_step_ok()
			await _wait(0.45)
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


## 等玩家走到一个结果（自动玩：先故意往反方向走 auto_wrong 次，再走到发光的那个）
func _choose() -> String:
	if auto_mode:
		if _auto_wrong > 0:
			_auto_wrong -= 1
			var away := -1.0 if _c >= _cur else 1.0
			await _walk(_cur + away * (LOST + 6.0))
			return "wrong"
		await _walk(_c)
		return "ok"
	_set_playing(true)
	var k: String = await chosen
	_set_playing(false)
	return k


func _on_tick(delta: float) -> void:
	_fog_follow()
	_pulse(delta)
	if not playing or chen == null:
		return
	if not chen.input_enabled:
		chen.input_enabled = true
	var k := judge(chen.position.x, _cur, _c)
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
## 踩对：叮一声，这个蹄印落到雾下面留着亮，雾薄一点
func _step_ok() -> void:
	_show_hint(false)
	var i := int(s["i"])
	_sfx(SFX_CHIME, -12.0, 0.9 + 0.06 * float(i))
	_sfx(SFX_STEP, -14.0, 0.62)
	_beacon_off()
	_print_at(_c, CELL_LIT)
	var f := fog_at(step, i)
	_fog_to(f.x, f.y, 1.2)


## 走反：晨身边的雾一下子变浓、「不是这边……」，晨被慢慢走回上一个亮着的蹄印，雾散回去
func _went_wrong() -> void:
	if chen != null:
		chen.input_enabled = false
	_sfx(SFX_WRONG, -16.0, 1.2)
	var back := fog_at(step, int(s["i"]))
	_fog_to(FOG_THICK.x, FOG_THICK.y, 0.7)
	var w: Dictionary = step.get("wrong_inner", WRONG_INNER)
	await story.run_steps([{"do": "inner", "zh": str(w.get("zh", "")), "en": str(w.get("en", "")), "style": "fade", "sec": 1.6}])
	await _wait(0.6)
	_fog_to(back.x, back.y, 1.4)
	await _walk(_cur)
	await _wait(0.3)


## 走反满了：剩下的蹄印一个接一个亮起来，晨自己跟着走完
func _auto_rest() -> void:
	var tr := trail(step)
	for i in range(int(s["i"]), tr.size()):
		var x := x0 + float(tr[i])
		_beacon_at(x)
		await _wait(0.6)
		await _walk(x)
		_c = x
		_step_ok()
		s["i"] = i + 1
		story.mech_save(ID, s)
		await _wait(0.3)


func _finish() -> void:
	_show_hint(false)
	_beacon_off()
	_fog_to(FOG_WIN.x, FOG_WIN.y, 2.0)
	await _wait(1.6)
	await _lines("win")
	_fog_to(0.0, FOG_WIN.y + 40.0, 2.4)
	await _wait(2.4)
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
	_tex = _load_tex(HOOF)
	_glow_tex = _load_tex(GLOW)
	_prints = Node2D.new()
	_prints.name = "SideSlopePrints"
	level.add_child(_prints)
	if chen != null and chen.get_parent() == level:
		level.move_child(_prints, chen.get_index())       # 画在晨脚底下
	_make_fog()
	_beacon = Node2D.new()
	_beacon.name = "SideSlopeBeacon"
	_beacon.z_as_relative = false
	_beacon.z_index = 95                                  # 雾（90）上面：远处也看得见那团光
	level.add_child(_beacon)
	_tick = Ticker.new()
	_tick.f = _on_tick
	level.add_child(_tick)
	_fog_follow()
	var tr := trail(step)
	var f := fog_at(step, int(s["i"]))
	_fog_to(f.x, f.y, 1.6)
	if chen != null and absf(chen.position.x - x0) > 1.0:
		await _walk(x0)
	await _wait(0.8)
	# 晨脚下第一个蹄印（读档回来：已经走过的都亮着）
	_print_at(x0, CELL_LIT)
	for i in int(s["i"]):
		_print_at(x0 + float(tr[i]), CELL_LIT)
	if int(s["i"]) > 0 and chen != null:
		await _walk(x0 + float(tr[int(s["i"]) - 1]))
	await _wait(0.3)


func _teardown() -> void:
	playing = false
	_show_hint(false)
	if _tick != null:
		_tick.queue_free()
		_tick = null
	if _fog != null:
		_fog.queue_free()
		_fog = null
	if _beacon != null:
		_beacon.queue_free()
		_beacon = null
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


# ----------------------------------------------------------------------- 蹄印
## 踩过的蹄印：雾下面、晨脚底下那一层，暖色不动
func _print_at(x: float, cell: int) -> Sprite2D:
	var p := _hoof_sprite(cell)
	p.position = Vector2(round(x) - floorf(PW / 2.0), round(_ground(x)) - 1.0)
	if _prints != null:
		_prints.add_child(p)
	return p


func _hoof_sprite(cell: int) -> Sprite2D:
	var p := Sprite2D.new()
	p.centered = false
	p.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	if _tex != null:
		var at := AtlasTexture.new()
		at.atlas = _tex
		at.region = Rect2(cell * PW, 0, PW, PH)
		p.texture = at
	return p


## 下一个蹄印：雾上面一团光 + 亮的蹄印，4 档淡入，然后一明一暗（_pulse）
func _beacon_at(x: float) -> void:
	_beacon_off()
	if _beacon == null:
		return
	var holder := Node2D.new()
	holder.position = Vector2(round(x), round(_ground(x)))
	_beacon.add_child(holder)
	if _glow_tex != null:
		_glow = Sprite2D.new()
		_glow.texture = _glow_tex
		_glow.centered = false
		_glow.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		_glow.position = Vector2(-floorf(_glow_tex.get_width() / 2.0), 2.0 - _glow_tex.get_height())
		_glow.modulate.a = 0.5
		holder.add_child(_glow)
	var p := _hoof_sprite(CELL_NEXT)
	p.position = Vector2(-floorf(PW / 2.0), -1.0)
	holder.add_child(p)
	holder.modulate.a = 0.0
	_pulse_t = 0.0
	var tw := holder.create_tween()
	tw.tween_method(func(v: float): holder.modulate.a = floorf(v * 4.0) / 4.0, 0.0, 1.0, 0.8 * (0.25 if auto_mode else 1.0))


func _beacon_off() -> void:
	_glow = null
	if _beacon == null:
		return
	for h in _beacon.get_children():
		var n: Node2D = h
		var tw := n.create_tween()
		tw.tween_method(func(v: float): n.modulate.a = ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, 0.4)
		tw.tween_callback(n.queue_free)


## 光一明一暗：透明度 0.25 / 0.5 / 0.75 三档之间正弦来回
func _pulse(delta: float) -> void:
	if _glow == null or not is_instance_valid(_glow):
		return
	_pulse_t += delta
	var a := 0.5 + 0.25 * sin(TAU * _pulse_t / PULSE_SEC)
	_glow.modulate.a = clampf(roundf(a * 4.0) / 4.0, 0.25, 0.75)


func _ground(x: float) -> float:
	if story.world != null and story.world.has_method("ground_at"):
		return float(story.world.ground_at(x))
	return chen.position.y if chen != null else 228.0


# ----------------------------------------------------------------------- 声音、提示
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
		OL.hud(story, true)                           # 左上角目标让开（最上面一行给按键提示）
		_hint = CanvasLayer.new()
		_hint.layer = 5
		level.add_child(_hint)
		var lb := OL.HintLabel.new(story)          # 对话 / 选项在显示的时候自己让开（11-04 安全区）
		lb.text = story.txt(HINT) if story.has_method("txt") else str(HINT["zh"])
		lb.position = Vector2(0, OL.HINT_Y)         # 屏幕上方那一行，不放进下面对话那一带
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
		tw.tween_callback(func():
			if _hint == null:                             # 提示收完才放目标回来（这半秒里又开了一条就不放）
				OL.hud(story, false))
		tw.tween_callback(h.queue_free)


func _lines(key: String) -> void:
	var l: Dictionary = step.get("lines", {})
	if l.get(key) is Array and not (l[key] as Array).is_empty():
		await story.run_steps(l[key])


func _wait(sec: float) -> void:
	await story.get_tree().create_timer(sec * (0.25 if auto_mode else 1.0), false).timeout


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
		out.append("trail 要是一串离 at 的像素数")
	else:
		var cur := 0.0
		for i in (tr as Array).size():
			var c := float(tr[i][0]) if tr[i] is Array else float(tr[i])
			if absf(c - cur) < 2.0 * STEP_R + 10.0:
				out.append("trail[%d]：离上一个蹄印太近（%d 像素）" % [i, int(absf(c - cur))])
			cur = c
	for p in [HOOF, GLOW]:
		if not FileAccess.file_exists(p):
			out.append("蹄印图 %s 还没有" % p)
	for k in st.get("lines", {}):
		out.append_array(KIT.check_steps(story, "lines.%s" % k, st["lines"][k]))
	return out
