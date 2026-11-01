extends Node2D
## 终章尾声最后一段「回家的列车」：art/home_train/room.json 的 scripts 里放这个（room_stage 建房间时 new 一个，父节点是 room_stage）。
## 图都是 tools/home_train_art.py 画的。车厢（car.png、glass.png）是 room.json 的层，乘客、吊环是物件（16 帧循环、100ms 一帧）；
## 这里只管会动、会变的：
## - 窗外：天空不动；远处的城 / 田野、中景的鸽子笼楼、近处的矮楼顶、一排树、接触网的杆子、高架桥面各按自己的速度往左走（车往右开）。
##   层是左右无缝的长条（960 / 480 宽），按「没绕回之前的坐标」u 画，所以可以只画某一段（城走完、树从右边进来）。
## - train_window：afternoon_sun（默认）= 还在城里；trees_passing = 出城：中景、近景的楼不再往后续（右边接下去的第一道楼缝就是
##   城的尽头，最后一栋走完就没了），树从右边一棵棵进来；远处的城在雾里慢慢换成田野、剩下的楼慢慢化进雾里（smoothstep，没有硬切）。
## - 光束：每扇窗一束（加法混合），楼 / 树挡住太阳时暗下去，再亮回来（occlusion.json：每一列挡不挡；离太阳越远的窗越晚被挡，
##   影子从右往左扫过车厢），亮暗都平滑地跟。挡住也不全黑：天光还在。
## - train_seat = sun_on_knees：晨膝上那块太阳慢慢亮起来（knees.png，在晨前面，加法）。
## - 晨的受光：站进哪束光里，chen 的 light_fn 就给那束的亮度（chen_light.gdshader 的 boost：斗篷和边亮一点）。
##   房间的 env 是 reeds（暖白的太阳从左上来、斗篷几乎不染色，和这里的阳光一个方向；没有脚下特效、不下雨）。

const DIR := "res://art/home_train/"
const SCREEN_W := 480
const SUN_X := 96.0
const EMPTY_BAY := 3            # 空座位那扇窗（beams 的第几束，和 home_train_art.py 一样）
## 窗外每层：图、宽、速度（像素 / 秒）、绝对 z。速度越近越快
const LAYERS := [
	{"id": "far_city", "w": 960, "speed": 6.0, "z": -159},
	{"id": "far_land", "w": 960, "speed": 6.0, "z": -158},
	{"id": "mid", "w": 960, "speed": 40.0, "z": -157},
	{"id": "near", "w": 960, "speed": 85.0, "z": -156},
	{"id": "trees", "w": 960, "speed": 120.0, "z": -155},
	{"id": "poles", "w": 480, "speed": 240.0, "z": -154},
	{"id": "deck", "w": 480, "speed": 240.0, "z": -153},
]
## 影子扫过车厢：窗 k 看的是这一层的 u = 平移量 + SUN_X + (窗的 x − SUN_X) × SWEEP
const SWEEP := {"mid": 0.5, "near": 0.7, "trees": 0.8}
const LAND_FADE := 6.0          # 出城：远处的城换成田野用几秒
const CITY_FADE := Vector2(4.0, 12.0)    # 出城：剩下的楼从第几秒到第几秒化进雾里
const KNEES_FADE := 1.6
const SHADE := 0.35             # 太阳被挡住时，光束还剩多亮（天光）
const FOLLOW := 5.0             # 光束跟着亮暗的快慢（1/秒）

var _data := {}
var _L := {}                    # id → {tex, w, speed, s, lo, hi, phase, a, node}
var _beams: Array = []          # [{node, floor: Vector2, win, v}]
var _knees: Sprite2D
var _knees_v := 0.0
var _t := 0.0
var _started := false
var _trees_t := INF             # 出城那一刻（_t），INF = 还在城里
var _stage: Node2D


func _ready() -> void:
	_stage = get_parent()
	var f := FileAccess.get_file_as_string(DIR + "occlusion.json")
	var j = JSON.parse_string(f)
	_data = j if j is Dictionary else {}
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	# 天空：不动，在最后面
	var sky := Sprite2D.new()
	sky.texture = _tex("sky.png")
	sky.centered = false
	sky.z_as_relative = false
	sky.z_index = -160
	add_child(sky)
	for c in LAYERS:
		var n := Node2D.new()
		n.name = "Out_" + str(c["id"])
		n.z_as_relative = false
		n.z_index = int(c["z"])
		n.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		add_child(n)
		var L := {"tex": _tex(str(c["id"]) + ".png"), "w": int(c["w"]), "speed": float(c["speed"]), "s": 0.0,
			"lo": -INF, "hi": INF, "phase": 0, "a": 1.0, "node": n}
		_L[c["id"]] = L
		n.draw.connect(_draw_strip.bind(L))
	_L["far_land"]["a"] = 0.0
	_L["trees"]["lo"] = INF                      # 树：出城以后才有
	for b in _data.get("beams", []):
		var s := Sprite2D.new()
		s.texture = _tex(str(b["img"]))
		s.centered = false
		s.position = Vector2(float(b["at"][0]), float(b["at"][1]))
		s.material = add
		s.z_as_relative = false
		s.z_index = -50                          # 车厢层（-100）上面、乘客和吊环（物件）下面
		add_child(s)
		_beams.append({"node": s, "floor": Vector2(float(b["floor"][0]), float(b["floor"][1])),
			"win": float(b["win"]), "v": 1.0})
	_knees = Sprite2D.new()
	_knees.texture = _tex("knees.png")
	_knees.centered = false
	var ka: Array = _data.get("knees_at", [292, 201])
	_knees.position = Vector2(float(ka[0]), float(ka[1]))
	_knees.material = add
	_knees.z_as_relative = false
	_knees.z_index = 5                           # 晨（z 0）前面
	_knees.modulate.a = 0.0
	add_child(_knees)


func _tex(file: String) -> Texture2D:
	var p := DIR + file
	if ResourceLoader.exists(p):
		return load(p)
	if FileAccess.file_exists(p):                # 刚画出来、还没导入（开发时）
		var img := Image.load_from_file(ProjectSettings.globalize_path(p))
		if img != null and not img.is_empty():
			return ImageTexture.create_from_image(img)
	return null


## 一层：只画屏幕上看得见、又在 [lo, hi] 里的那一段，按图宽绕回
func _draw_strip(L: Dictionary) -> void:
	var tex: Texture2D = L["tex"]
	var a: float = L["a"]
	if tex == null or a <= 0.001:
		return
	var n: Node2D = L["node"]
	var w: int = L["w"]
	var s := int(roundf(float(L["s"])))
	var u0 := float(s)
	var u1 := float(s + SCREEN_W)
	u0 = maxf(u0, ceilf(float(L["lo"])))
	u1 = minf(u1, floorf(float(L["hi"])))
	if u0 >= u1:
		return
	var u := int(u0)
	var h := float(tex.get_height())
	var col := Color(1, 1, 1, a)
	while u < int(u1):
		var c := posmod(u + int(L["phase"]), w)
		var k := mini(w - c, int(u1) - u)
		n.draw_texture_rect_region(tex, Rect2(u - s, 0, k, h), Rect2(c, 0, k, h), col)
		u += k


func _process(delta: float) -> void:
	if not is_visible_in_tree():
		return
	var world = _stage.get("world")
	var win := str(world.prop_state("train_window")) if world != null else ""
	var seat := str(world.prop_state("train_seat")) if world != null else ""
	if not _started:
		_started = true
		if win == "trees_passing":               # 直接跳到出城以后（开发跳段）：城已经走完了
			_leave_city(-100.0)
	elif win == "trees_passing" and _trees_t == INF:
		_leave_city(_t)
	_t += delta
	for id in _L:
		var L: Dictionary = _L[id]
		L["s"] = float(L["speed"]) * _t
	if _trees_t != INF:
		var k := _t - _trees_t
		var land := smoothstep(0.0, LAND_FADE, k)
		_L["far_city"]["a"] = 1.0 - land
		_L["far_land"]["a"] = land
		var fade := 1.0 - smoothstep(CITY_FADE.x, CITY_FADE.y, k)
		_L["mid"]["a"] = fade
		_L["near"]["a"] = fade
	for id in _L:
		(_L[id]["node"] as Node2D).queue_redraw()
	_update_beams(delta)
	var kt := 1.0 if seat == "sun_on_knees" else 0.0
	if kt > 0.0 and _knees_v == 0.0:
		print("HOME_TRAIN sun_on_knees t=%.1f seat_beam=%.2f" % [_t, float(_beams[EMPTY_BAY]["v"]) if _beams.size() > EMPTY_BAY else -1.0])
	_knees_v = move_toward(_knees_v, kt, delta / KNEES_FADE)
	var seat_beam: float = _beams[EMPTY_BAY]["v"] if _beams.size() > EMPTY_BAY else 1.0
	_knees.modulate.a = smoothstep(0.0, 1.0, _knees_v) * lerpf(0.6, 1.0, seat_beam)
	_chen_light(world)


## 出城：中景、近景从右边下一道楼缝起不再往后续；树从屏幕右边开始
func _leave_city(at: float) -> void:
	_trees_t = at
	for id in ["mid", "near"]:
		var L: Dictionary = _L[id]
		var solid: Array = _data.get("solid_" + id, [])
		var u := int(roundf(float(L["speed"]) * maxf(at, 0.0))) + SCREEN_W
		if at < 0.0:
			L["hi"] = -INF
			continue
		for i in int(L["w"]):
			if solid.is_empty() or int(solid[posmod(u, int(L["w"]))]) == 0:
				break
			u += 1
		L["hi"] = float(u)
	var T: Dictionary = _L["trees"]
	if at < 0.0:
		T["lo"] = -INF
	else:
		var lo := int(roundf(float(T["speed"]) * at)) + SCREEN_W
		T["lo"] = float(lo)
		T["phase"] = -lo                         # 树那张图的第 0 列正好从屏幕右边进来
	# 自测用（headless 也算得出来）：城的尽头离屏幕右边多远、树从哪一列进来
	print("HOME_TRAIN leave_city t=%.1f mid_end=+%d near_end=+%d trees_lo=%s" % [at,
		int(float(_L["mid"]["hi"]) - float(_L["mid"]["s"]) - SCREEN_W) if at >= 0.0 else -1,
		int(float(_L["near"]["hi"]) - float(_L["near"]["s"]) - SCREEN_W) if at >= 0.0 else -1, str(T["lo"])])


func _occ(id: String, wx: float) -> float:
	var L: Dictionary = _L[id]
	if float(L["a"]) <= 0.001:
		return 0.0
	var occ: Array = _data.get("occ_" + id, [])
	if occ.is_empty():
		return 0.0
	var u := float(L["s"]) + SUN_X + (wx - SUN_X) * float(SWEEP.get(id, 0.5))
	if u < float(L["lo"]) or u > float(L["hi"]):
		return 0.0
	return float(occ[posmod(int(u) + int(L["phase"]), int(L["w"]))]) * float(L["a"])


func _update_beams(delta: float) -> void:
	var k := 1.0 - exp(-FOLLOW * delta)
	for b in _beams:
		var wx: float = b["win"]
		var occ := maxf(_occ("mid", wx), maxf(_occ("near", wx) * 0.7, _occ("trees", wx)))
		var target := lerpf(1.0, SHADE, occ)
		b["v"] = lerpf(float(b["v"]), target, k)
		(b["node"] as Sprite2D).modulate.a = float(b["v"])


## 晨站在哪束光的地板亮块里，就给那束的亮度；膝上有太阳时是满的
func _chen_light(world) -> void:
	if world == null or world.chen == null:
		return
	var chen: Node2D = world.chen
	if str(chen.get("env")) != "reeds" or (chen.get("light_fn") as Callable).is_valid():
		return
	var me := self
	chen.set_env("reeds", func(c): return me.light_at(c.position.x - me._stage.origin.x))


func light_at(x: float) -> float:
	var v := 0.0
	for b in _beams:
		var f: Vector2 = b["floor"]
		if x >= f.x and x <= f.y:
			v = maxf(v, float(b["v"]))
	return maxf(v * 0.8, _knees_v)
