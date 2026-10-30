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


## 取景框：有图（会话 C 出的 frame）就用图；没有就画一个色块框 + 灯柱竖线（对上时和场景里的灯柱重合）
func _build_frame() -> void:
	if story.ff:
		return
	_layer = CanvasLayer.new()
	_layer.layer = 5
	level.add_child(_layer)
	var p := str(step.get("frame", ""))
	if p != "" and ResourceLoader.exists(p):
		var tr := TextureRect.new()
		tr.texture = load(p)
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_frame = tr
	else:
		_frame = Control.new()
		_frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_frame.size = Vector2(480, 270)
		var edge := ReferenceRect.new()
		edge.border_color = Color(0.8, 0.85, 0.9, 0.6)
		edge.editor_only = false
		edge.position = Vector2(40, 30)
		edge.size = Vector2(400, 190)
		_frame.add_child(edge)
		var water := ColorRect.new()                         # 影像里的高水位
		water.color = Color(0.45, 0.55, 0.62, 0.25)
		water.position = Vector2(40, 150)
		water.size = Vector2(400, 70)
		_frame.add_child(water)
		var lamp := ColorRect.new()                          # 影像里的灯柱：站在观察点时，场景里的灯柱正好在这条线上
		lamp.color = Color(0.9, 0.85, 0.6, 0.55)
		lamp.size = Vector2(2, 90)
		var spot := KIT.mx(world, str(step.get("spot", "")), 240.0)
		var lx := KIT.mx(world, str(step.get("frame_lamp", "southbridge_lamp_post")), spot)
		lamp.position = Vector2(clampf(240.0 + lx - spot, 44.0, 434.0), 60)
		_frame.add_child(lamp)
	_layer.add_child(_frame)
	_set_clear(0.0)


func _set_clear(k: float) -> void:
	if _frame != null:
		_frame.modulate.a = lerpf(0.25, 0.7, k)


func _drop_frame() -> void:
	if _layer != null:
		var tw := _layer.create_tween()
		tw.tween_property(_frame, "modulate:a", 0.0, 0.6)
		tw.tween_callback(_layer.queue_free)


## 跳节拍：对好了、点对了（同步、不演）
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
