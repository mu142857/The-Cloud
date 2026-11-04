extends RefCounted
## 河流篇小游戏 river_bridge_view：还原拍摄位置（南桥，原文 137，剧情姐写的玩法原样落地）。
##   137：玩家对照影像里的桥洞、灯柱与浮灯方向，找到正确的观察点，再结合当前水位确认动物经过的水道。
##        完成后显露旧运输水道的入口，不依赖快速反应或记忆倒计时。
##   前情（原文 136，剧本已演）：退水后露得比影像多、像栏杆的是屋顶装饰；晨先照画面找灯柱，走错一次，拿出纸重新标注。
##   影像内容（原文 97、124）：半淹在水里的桥、浮灯一盏盏抬高 / 整排移动、「往南边去了。看到了吗，桥洞下面！」
##
## 怎么玩：
##   1. 找观察点：屏幕上叠一层半透明的取景框 = 影像那一帧（桥洞、灯柱、斜向一边的浮灯、当时的高水位），固定在屏幕上不跟镜头。
##      晨自己左右走（放手让玩家走，不锁人）；视差各层速度不同，只有站在拍摄的那个点，桥洞、灯柱才和取景框同时对上。
##      越近取景框越清楚；对上 =「咔」一声定住（lines.aligned）。没有计时，取景框一直在。
##   2. 确认水道：对上以后看得出取景框里的水比现在高。走到一个桥洞前互动 =「它是从这里过去的」（arches）。
##      影像里浮灯往哪边歪、灰影往哪个桥洞去，就是哪一个；点错的晨说一句（lines.wrong_<id>），取景框还在，再点。
##      点对 → 设 sets 里的 flag（river_waterway_open：南桥 room.json 的 walk_when 放开右半边、货台走得到），
##      剧本接着 prop southbridge_waterway revealed（旧运输水道的入口露出来）。
##
## 剧本步骤：{"do": "mechanic", "id": "river_bridge_view", "sets": ["river_waterway_open"], "spot": marker, "near": 像素, "frame": png, "frame_lamp": marker,
##   "arches": [{id, label, right?}…], "lines": {start, aligned, ask, wrong_<id>…, right}}
## 进度（story.mech_load）：{aligned: bool, tried: [桥洞]}。

const KIT := preload("res://scripts/river_explore_order.gd")
const ID := "river_bridge_view"
const NEAR := 6.0          # 离观察点多近算对上（像素）
const SEE := 140.0         # 多远开始看得出取景框在对齐（越近越清楚）


# ======================================================================= 规则（纯函数）
static func fresh() -> Dictionary:
	return {"aligned": false, "tried": []}


static func right_arch(step: Dictionary) -> String:
	for a in step.get("arches", []):
		if a.get("right", false):
			return str(a["id"])
	return ""


## 站在 x：对上了没有、取景框多清楚（0..1）
static func align(step: Dictionary, x: float, spot_x: float) -> Array:
	var near := float(step.get("near", NEAR))
	var d := absf(x - spot_x)
	return [d <= near, clampf(1.0 - d / SEE, 0.0, 1.0)]


## 点一个桥洞：{kind: right / wrong / not_yet}
static func act(step: Dictionary, s: Dictionary, arch: String) -> Dictionary:
	if not s["aligned"]:
		return {"kind": "not_yet"}
	if not arch in s["tried"]:
		(s["tried"] as Array).append(arch)
	return {"kind": "right" if arch == right_arch(step) else "wrong", "arch": arch}


# ======================================================================= 演出
var auto_mode := false
var tried := {}
var story: Node
var world: Node2D
var level: Node2D
var step: Dictionary
var s: Dictionary
var _layer: CanvasLayer
var _frame: Control
var _done_walk := false


func run(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	world = w
	level = lv
	step = st
	s = story.mech_load(ID)
	if not s.has("aligned"):
		s = fresh()
	_build_frame()
	await KIT.lines(story, step, "start")
	if not s["aligned"]:
		await _find_spot()
		s["aligned"] = true
		story.mech_save(ID, s)
		await KIT.steps(story, [{"do": "sfx", "name": "view_click"}])
		_set_clear(1.0)
		_flash_full()
		await _elephant_shadow()
		await KIT.lines(story, step, "aligned")
	await KIT.lines(story, step, "ask")
	while not story.ended:
		var opts: Array = []
		var ok := right_arch(step)
		for a in step.get("arches", []):
			opts.append({"tok": str(a["id"]), "at": str(a["id"]), "label": a.get("label", a["id"]), "correct": str(a["id"]) == ok})
		var c: String = await KIT.choose(self, story, opts)
		var res := act(step, s, c)
		story.mech_save(ID, s)
		await KIT.steps(story, [{"do": "face", "who": "chen", "to": c}, {"do": "anim", "who": "chen", "name": "compare"}])
		if res["kind"] == "right":
			for f in step.get("sets", []):
				StoryState.set_flag(str(f))       # river_waterway_open：南桥 room.json 放开右半边（货台）
			await KIT.lines(story, step, "right")
			break
		await KIT.lines(story, step, "wrong_" + c)
	_drop_frame()
	print("MECH %s done tried=%d" % [ID, (s["tried"] as Array).size()])


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


## 找观察点：放手让玩家走，取景框越近越清楚，到了就定住
func _find_spot() -> void:
	var spot := KIT.mx(world, str(step.get("spot", "")), NAN)
	if is_nan(spot) or story.ff:
		return
	if auto_mode:
		await KIT.steps(story, [{"do": "walk", "who": "chen", "to": str(step["spot"])}])
		return
	story.free_walk = true
	level.story_free(true)
	while not story.ended:
		await story.get_tree().process_frame
		var a := align(step, story.chen.position.x, spot)
		_set_clear(float(a[1]))
		if a[0] and absf(story.chen._vel) < 1.0:
			break
	level.story_free(false)
	story.free_walk = false


## 取景框（11-02 作者：整屏半透明叠一层「很抽象、视觉效果真混乱」）：
##   平时 = 右上角一张小照片（影像那一帧缩成 1/4，实框，不透明），像晨举着照片对照；离观察点越近，照片的框越暖。
##   对上那一刻 = 整屏那一帧淡进来（0.35 秒到 .55）再慢慢淡掉（0.9 秒）——只闪这一下，证明「就是这里」，平时不叠在画面上。
const THUMB := Vector2(120, 68)
const THUMB_POS := Vector2(480 - 120 - 10, 34)
const EDGE_COLD := Color(0.55, 0.62, 0.68)
const EDGE_WARM := Color(0.95, 0.82, 0.5)
var _thumb: Control
var _edge: ColorRect
var _full: TextureRect


func _build_frame() -> void:
	if story.ff:
		return
	_layer = CanvasLayer.new()
	_layer.layer = 5
	level.add_child(_layer)
	var p := str(step.get("frame", ""))
	var tex: Texture2D = load(p) if p != "" and ResourceLoader.exists(p) else null
	_thumb = Control.new()
	_thumb.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_thumb.position = THUMB_POS
	_edge = ColorRect.new()                                  # 照片的实框（2 像素）
	_edge.color = EDGE_COLD
	_edge.position = Vector2(-2, -2)
	_edge.size = THUMB + Vector2(4, 4)
	_thumb.add_child(_edge)
	var bg := ColorRect.new()
	bg.color = Color(0.06, 0.08, 0.1)
	bg.size = THUMB
	_thumb.add_child(bg)
	if tex != null:
		var tr := TextureRect.new()
		tr.texture = tex
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_SCALE
		tr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		tr.size = THUMB
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_thumb.add_child(tr)
		_full = TextureRect.new()
		_full.texture = tex
		_full.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_full.modulate.a = 0.0
		_layer.add_child(_full)
	_layer.add_child(_thumb)
	_thumb.modulate.a = 0.0
	var tw := _thumb.create_tween()
	tw.tween_method(func(k: float): _thumb.modulate.a = floorf(k * 4.0) / 4.0, 0.0, 1.0, 0.5)
	_set_clear(0.0)


func _set_clear(k: float) -> void:
	if _edge != null:
		_edge.color = EDGE_COLD.lerp(EDGE_WARM, floorf(k * 4.0) / 4.0)


## 对上那一下：整屏那一帧闪进来再淡掉
func _flash_full() -> void:
	if _full == null:
		return
	var tw := _full.create_tween()
	tw.tween_property(_full, "modulate:a", 0.55, 0.35).set_trans(Tween.TRANS_SINE)
	tw.tween_property(_full, "modulate:a", 0.0, 0.9).set_trans(Tween.TRANS_SINE)


## 11-04 作者「第二关的小游戏不如第一关有趣」：对上那一刻，影像里那团灰影真的从对的桥洞底下走过去一遍
##   （画在世界里、晨身后；大象的侧影，一步一顿，淡进来再淡出去）。接下来问「它是从哪个桥洞过去的」就有答案可看。
class Shadow extends Node2D:
	var step_t := 0.0
	var k := 0.0

	## 像素椭圆（一行一行）
	func _ell(c: Vector2, rx: float, ry: float, col: Color) -> void:
		for dy in range(-int(ry), int(ry) + 1):
			var w := floorf(rx * sqrt(maxf(0.0, 1.0 - float(dy * dy) / (ry * ry))))
			draw_rect(Rect2(roundf(c.x - w), roundf(c.y + dy), w * 2.0 + 1.0, 1), col)

	## 大象侧影（朝右走，原点 = 脚底中间）：粗短腿一前一后地迈、圆身子、大耳朵、鼻子垂下来打个卷
	func _draw() -> void:
		var col := Color(0.6, 0.67, 0.72, 0.34 * k)
		var dark := Color(0.5, 0.57, 0.63, 0.34 * k)
		var bob := roundf(sin(step_t * 5.0) * 1.0)
		var legs := [-24.0, -12.0, 12.0, 24.0]
		for i in legs.size():
			var sw := roundf(sin(step_t * 5.0 + (PI if i in [0, 2] else 0.0)) * 2.5)
			draw_rect(Rect2(legs[i] - 4.0 + sw, -16 + bob, 9, 16 - bob), col)
		_ell(Vector2(0, -32 + bob), 34.0, 18.0, col)                   # 身子
		_ell(Vector2(36, -40 + bob), 13.0, 12.0, col)                  # 头
		_ell(Vector2(28, -38 + bob), 9.0, 13.0, dark)                  # 耳朵
		for i in 15:                                                   # 鼻子
			var t := i / 14.0
			var q := Vector2(46.0 + 5.0 * t - 7.0 * maxf(0.0, t - 0.75) * 4.0, -38.0 + 30.0 * t + bob)
			draw_rect(Rect2(q.round(), Vector2(5.0 - 2.0 * t, 2)), col)
		for i in 6:                                                    # 尾巴
			draw_rect(Rect2(-34 - i, -32 + i * 2 + bob, 1, 2), dark)


func _elephant_shadow() -> void:
	if story.ff or story.chen == null:
		return
	var ax := KIT.mx(world, right_arch(step), NAN)
	if is_nan(ax):
		return
	var sh := Shadow.new()
	var host: Node = story.chen.get_parent()
	host.add_child(sh)
	host.move_child(sh, story.chen.get_index())          # 同一层、画在晨前面一个 = 晨身后
	sh.z_index = story.chen.z_index
	sh.z_as_relative = story.chen.z_as_relative
	var y: float = story.chen.position.y - 26.0          # 在后面的水里（桥洞底下），不从晨身上穿过去
	var dur := 1.6 if auto_mode else 3.4
	var x0 := ax - 200.0
	var x1 := ax + 60.0
	var t := 0.0
	KIT.steps(story, [{"do": "sfx", "name": "low_call_tape"}])
	if story.has_method("_ui_shot"):
		story._ui_shot("bridge_shadow", dur * 0.45)
	while t < dur and is_instance_valid(sh) and not story.ended:
		await story.get_tree().process_frame
		t += story.get_process_delta_time()
		var u := t / dur
		sh.position = Vector2(roundf(lerpf(x0, x1, u)), y)
		sh.step_t = t
		sh.k = clampf(minf(u / 0.2, (1.0 - u) / 0.25), 0.0, 1.0)
		sh.queue_redraw()
	if is_instance_valid(sh):
		sh.queue_free()


func _drop_frame() -> void:
	if _layer != null:
		var tw := _layer.create_tween()
		if _thumb != null:
			tw.tween_property(_thumb, "modulate:a", 0.0, 0.6)
		tw.tween_callback(_layer.queue_free)


func ff(r: Node, st: Dictionary) -> void:
	r.mech_save(ID, {"aligned": true, "tried": [right_arch(st)]})
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))


func check(story: Node, st: Dictionary) -> Array:
	var out: Array = []
	if right_arch(st) == "":
		out.append("arches 里没有 right: true 的桥洞")
	if (st.get("arches", []) as Array).size() < 2:
		out.append("桥洞至少两个（走错一次、换一个桥洞继续找）")
	for a in st.get("arches", []):
		if not a.get("right", false) and not KIT.has_lines(st, "wrong_" + str(a["id"])):
			out.append("点错 %s 没有 lines.wrong_%s" % [a["id"], a["id"]])
	if not story.world.has_marker(str(st.get("spot", ""))):
		out.append("spot 的 marker %s 找不到" % st.get("spot"))
	for a in st.get("arches", []):
		if not story.world.has_marker(str(a["id"])):
			out.append("桥洞 marker %s 找不到" % a["id"])
	if not ResourceLoader.exists(str(st.get("frame", ""))):
		out.append("info: 取景框的图还没有（%s），先画色块框" % st.get("frame"))
	for k in st.get("lines", {}):
		out.append_array(KIT.check_steps(story, "lines.%s" % k, st["lines"][k]))
	return out
