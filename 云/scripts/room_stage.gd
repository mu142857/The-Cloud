extends Node2D
## 河流篇（以后各章同理）的一个房间：读 art/river_city/<id>/room.json（或 art/<id>/room.json），画视差层、物件、水位层、
## 剖面小屋、背景走过的小人、环境声、导绳。story_world.gd 按剧本的 rooms 建（add_stages），story_runner / 小游戏通过它问
## markers / 地面 / 墙 / 物件。格式全在 docs/river_rooms_contract.md（这里只写实现上的事）。
##
## 坐标：房间坐标 = 房间左上角 (0, 0)、y 往下；这个节点放在世界的 origin（position = origin），所以子节点直接用房间坐标。
##   剖面小屋（kind: house）：坐标是「图里的像素」，节点放在 host 房间里（图的底边中点踩在 host 的地面 x 上）。
## 前后：人物 z = 0。层、物件用 z_index（相对这个节点，节点自己 z 0）：层默认 −100 起、front 层 100 起；物件默认 −1。
##   小屋：back −10、物件 −5、light −4、前墙 −1（在屋外的人前面就会挡人，所以屋里的 NPC 在晨不在屋里时压到 −2，见 story_runner）。
## 视差：层的房间 x = 层 x + 镜头左边缘(房间 x) × (1 − scroll)（竖直方向没有视差）；tile 的层用 region + texture_repeat 铺满一屏多。
## 测试：-- --room_placeholder 不读任何 room.json，全用占位（验引擎和剧本，不受美术进度影响）。
## 缺图：没有 room.json → DEFAULT（按方案的宽度）+ 程序画的占位（底色、远楼色块、地面、水带、房间名）；物件没图 → 色块，
##   每个状态换一档深浅；新放进来、还没导入的 png 直接从文件读（只在编辑器 / 开发时管用）。

const NPC_GD := preload("res://scripts/npc_generic.gd")
const DIRS := ["res://art/river_city/%s/", "res://art/%s/"]
## 没有 room.json 时的默认（方案第 1.1 节的宽度；origin 让市集在河岸正上方、仓库在旧街正下方）
const DEFAULT := {
	"river_bank": {"size": [1280, 270], "origin": [0, 0], "env": "river_day",
		"markers": {"river_bank_plane": 110, "river_bank_hatch": 150, "river_bank_home_door": 870},
		"portals": [{"to": "market", "kind": "pan_up"}]},
	"market": {"size": [1100, 270], "origin": [0, -270], "env": "river_day",
		"portals": [{"to": "river_bank", "kind": "pan_down"}, {"to": "oldstreet", "kind": "walk_fade"}]},
	"oldstreet": {"size": [1200, 270], "origin": [3000, 0], "env": "river_day",
		"portals": [{"to": "warehouse", "kind": "pan_down"}, {"to": "market", "kind": "walk_fade"},
			{"to": "southbridge", "kind": "walk_fade"}]},
	"warehouse": {"size": [640, 270], "origin": [3000, 270], "env": "underwater", "portals": [{"to": "oldstreet", "kind": "pan_up"}]},
	"southbridge": {"size": [1500, 270], "origin": [6000, 0], "env": "river_day",
		"portals": [{"to": "oldstreet", "kind": "walk_fade"}]},
	"river_home": {"kind": "house", "host": "river_bank", "x": 1040, "size": [420, 200], "floor": 190, "walk": [30, 390], "door": 40,
		"markers": {"river_home_door": 40}},
}
const GROUND := 228
const PH_BG := [Color("#1b2228"), Color("#3a4752")]       # 河流身份色（方案第 0 节）
const PH_BUILD := Color("#28323b")
const PH_GROUND := Color("#2c343a")
const PH_WATER := Color(0.30, 0.40, 0.48, 0.55)
const PH_OBJ := Color("#6b7680")
const SHADERS := {"water": "res://scripts/river_water.gdshader", "wet": "res://scripts/city_wet.gdshader",
	"sway": "res://scripts/underwater_sway.gdshader"}
const HIDE_STATES := ["hidden", "hide", "gone", "taken"]
const SHOW_STATES := ["show", "shown", "default", ""]

var id := ""
var dir := ""                         # 图所在的文件夹（res://…/）
var cfg := {}
var has_json := false
var is_house := false
var host: Node2D                       # 小屋在哪个房间里
var size := Vector2(480, 270)
var origin := Vector2.ZERO
var env := ""
var markers := {}                      # 名字 → 房间 x
var objects := {}                      # 物件 id → Sprite2D
var ocfg := {}                         # 物件 id → 配置（合并过的）
var ostate := {}                       # 物件 id → 现在的状态
var _oloop := {}                       # 物件 id → [起, 止]（这个状态循环播哪几帧）
var world: Node2D                      # story_world.gd
var house_front: Sprite2D              # 小屋：前墙
var water_base := NAN                  # room.json water.y（没有水 = NAN）
var water_cur := NAN
var walk_override = null               # 小游戏临时改的左右范围（房间 x）
var walkers: Array = []                # [{npc, path, speed, pause, loop, i, dir, wait}]
var _layers: Array = []                # [{node: Sprite2D, cfg, tile, w}]
var _ground_pts: Array = []            # 折线 [[x, y], …]（空 = 平地）
var _ground_y := float(GROUND)
var _t := 0.0
var _water_tw: Tween
var _rope: Node2D
var _amb: Array = []                   # [{player, cfg}]
var _warned := {}
var _ph_node: Node2D                   # 占位的底图


## room.json（没有就 DEFAULT）先看一眼：是不是小屋、host 是谁（建房间的先后要用）
static func peek(room_id: String) -> Dictionary:
	var c := {}
	for d in ([] if placeholder_only() else DIRS):
		var p: String = (d as String) % room_id
		if FileAccess.file_exists(p + "room.json"):
			var j = JSON.parse_string(FileAccess.get_file_as_string(p + "room.json"))
			if j is Dictionary:
				c = j
			break
	var dflt: Dictionary = DEFAULT.get(room_id, {})
	for k in dflt:
		if not c.has(k):
			c[k] = dflt[k]
	return c


func setup(room_id: String, w: Node2D, host_stage: Node2D = null) -> void:
	id = room_id
	name = "Room_" + room_id
	world = w
	host = host_stage
	for d in ([] if placeholder_only() else DIRS):
		var p: String = (d as String) % room_id
		if FileAccess.file_exists(p + "room.json"):
			dir = p
			var j = JSON.parse_string(FileAccess.get_file_as_string(p + "room.json"))
			if j is Dictionary:
				cfg = j
				has_json = true
			else:
				_warn("room.json 读不出来：" + p)
			break
	if dir == "":
		dir = (DIRS[0] as String) % room_id
	var dflt: Dictionary = DEFAULT.get(room_id, {"size": [800, 270]})
	for k in dflt:
		if not cfg.has(k):
			cfg[k] = dflt[k]
	is_house = str(cfg.get("kind", "")) == "house"
	size = _v2(cfg.get("size", [480, 270]), Vector2(480, 270))
	env = str(cfg.get("env", ""))
	var g = cfg.get("floor" if is_house else "ground", GROUND)
	if g is Array:
		_ground_pts = g
	else:
		_ground_y = float(g)
	var mk: Dictionary = cfg.get("markers", {})
	for k in mk:
		var v = mk[k]
		markers[str(k)] = float(v.get("x", 0)) if v is Dictionary else (float(v[0]) if v is Array else float(v))
	if is_house:
		_place_house()
		_build_house()
	else:
		origin = _v2(cfg.get("origin", [0, 0]), Vector2.ZERO)
		position = origin
		_build_bg()
		_build_layers()
	var wcfg = cfg.get("water", null)
	if wcfg is Dictionary:
		water_base = float(wcfg.get("y", 200))
		water_cur = water_base
	for oid in cfg.get("objects", {}):
		_make_object(str(oid), cfg["objects"][oid])
	_build_walkers()
	_build_scripts()
	_build_rope()


## 小屋放到 host 里：图的底边中点踩在 host 的地面 x 上
## -- --room_placeholder：不读 room.json，全部用占位（测引擎本身，和美术进度无关）
static func placeholder_only() -> bool:
	return "--room_placeholder" in OS.get_cmdline_user_args()


func _place_house() -> void:
	var hx := float(cfg.get("x", 0))
	var gy: float = host.ground_local(hx) if host != null else float(GROUND)
	var ho: Vector2 = host.origin if host != null else Vector2.ZERO
	origin = ho + Vector2(round(hx - size.x / 2.0), round(gy + 1.0 - size.y))
	position = origin


# ======================================================================= 图
func _tex(file: String) -> Texture2D:
	if file == "":
		return null
	var p := file if file.begins_with("res://") else dir + file
	if ResourceLoader.exists(p):
		return load(p)
	if FileAccess.file_exists(p):
		var img := Image.load_from_file(ProjectSettings.globalize_path(p))
		if img != null and not img.is_empty():
			return ImageTexture.create_from_image(img)
	return null


static func block(w: int, h: int, c: Color) -> ImageTexture:
	var img := Image.create_empty(maxi(w, 1), maxi(h, 1), false, Image.FORMAT_RGBA8)
	img.fill(c)
	var edge := c.darkened(0.25)
	for x in img.get_width():
		img.set_pixel(x, 0, edge)
		img.set_pixel(x, img.get_height() - 1, edge)
	for y in img.get_height():
		img.set_pixel(0, y, edge)
		img.set_pixel(img.get_width() - 1, y, edge)
	return ImageTexture.create_from_image(img)


static func _v2(v, d: Vector2) -> Vector2:
	if v is Array and (v as Array).size() >= 2:
		return Vector2(float(v[0]), float(v[1]))
	if v is Dictionary:
		return Vector2(float(v.get("x", d.x)), float(v.get("y", d.y)))
	return d


static func _col(v, d: Color) -> Color:
	return Color(str(v)) if v is String and str(v).begins_with("#") else d


func _warn(msg: String) -> void:
	if _warned.has(msg):
		return
	_warned[msg] = true
	print("ROOM_WARN %s: %s" % [id, msg])


# ---------------------------------------------------------------- 底色 + 占位
func _build_bg() -> void:
	_ph_node = Node2D.new()
	_ph_node.name = "Bg"
	_ph_node.z_index = -200
	_ph_node.draw.connect(_draw_bg)
	add_child(_ph_node)


func _draw_bg() -> void:
	var bg: Array = cfg.get("bg", [])
	var c0 := _col(bg[0] if bg.size() > 0 else null, PH_BG[0])
	var c1 := _col(bg[1] if bg.size() > 1 else null, PH_BG[1])
	var n := 9
	for i in n:
		var y0 := floorf(270.0 * i / n)
		var y1 := floorf(270.0 * (i + 1) / n)
		_ph_node.draw_rect(Rect2(-240, y0, size.x + 480, y1 - y0), c0.lerp(c1, float(i) / (n - 1)))
	if has_json and not (cfg.get("layers", []) as Array).is_empty():
		return
	# 占位：远处一排灰蓝的方楼（鸽子笼）、地面、半透明的水带、房间名
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(id)
	var x := -40.0
	while x < size.x + 40.0:
		var bw := rng.randi_range(24, 56)
		var bh := rng.randi_range(60, 150)
		_ph_node.draw_rect(Rect2(x, _ground_y - bh, bw, bh), PH_BUILD)
		for wy in range(int(_ground_y - bh) + 8, int(_ground_y) - 10, 12):
			for wx in range(int(x) + 5, int(x) + bw - 6, 9):
				if rng.randf() < 0.18:
					_ph_node.draw_rect(Rect2(wx, wy, 3, 4), Color("#d9a35a") if rng.randf() < 0.3 else Color("#3a4752"))
		x += bw + rng.randi_range(4, 14)
	var pts := PackedVector2Array()
	for gx in range(0, int(size.x) + 1, 8):
		pts.append(Vector2(gx, ground_local(gx) + 1))
	pts.append(Vector2(size.x, 270))
	pts.append(Vector2(0, 270))
	_ph_node.draw_colored_polygon(pts, PH_GROUND)
	if not is_nan(water_base):
		_ph_node.draw_rect(Rect2(0, water_cur, size.x, 270 - water_cur), PH_WATER)
	elif env != "underwater":
		_ph_node.draw_rect(Rect2(0, _ground_y + 14, size.x, 270 - _ground_y - 14), PH_WATER)
	else:
		_ph_node.draw_rect(Rect2(-240, 0, size.x + 480, 270), Color(0.16, 0.26, 0.32, 0.45))
	var f := ThemeDB.fallback_font
	_ph_node.draw_string(f, Vector2(8, 22), "[占位] " + id, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.8, 0.85, 0.9, 0.6))


# ---------------------------------------------------------------- 视差层
func _build_layers() -> void:
	var i := 0
	for lc in cfg.get("layers", []):
		if not lc is Dictionary:
			continue
		var c: Dictionary = lc
		var tex := _tex(str(c.get("img", "")))
		var s := Sprite2D.new()
		s.name = "L_" + str(c.get("id", i))
		s.centered = false
		s.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		if tex == null:
			_warn("层缺图：" + str(c.get("img", "")))
			tex = block(int(size.x), 20, Color(0.3, 0.36, 0.42, 0.5))
		s.texture = tex
		var z := -100 + i
		if c.get("front", false):
			z = 100 + i
		s.z_index = int(c.get("z", z))
		s.modulate.a = float(c.get("alpha", 1.0))
		var tile: bool = c.get("tile", false)
		if tile:
			s.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
			s.region_enabled = true
			s.region_rect = Rect2(0, 0, 480 + tex.get_width() * 2, tex.get_height())
		var sh := str(c.get("shader", ""))
		if SHADERS.has(sh) and ResourceLoader.exists(SHADERS[sh]):
			var m := ShaderMaterial.new()
			m.shader = load(SHADERS[sh])
			var sp: Dictionary = c.get("shader_params", {})
			for k in sp:
				m.set_shader_parameter(str(k), sp[k])
			s.material = m
		add_child(s)
		_layers.append({"node": s, "cfg": c, "tile": tile, "w": float(tex.get_width())})
		i += 1


# ---------------------------------------------------------------- 小屋
func _build_house() -> void:
	var back := Sprite2D.new()
	back.name = "HouseBack"
	back.centered = false
	back.z_index = -10
	back.texture = _tex(str(cfg.get("back", "back.png")))
	if back.texture == null:
		back.texture = _house_ph(false)
	add_child(back)
	var light := _tex(str(cfg.get("light", "light.png")))
	if light != null:
		var l := Sprite2D.new()
		l.centered = false
		l.z_index = -4
		l.texture = light
		add_child(l)
	house_front = Sprite2D.new()
	house_front.name = "HouseFront"
	house_front.centered = false
	house_front.z_index = -1
	house_front.texture = _tex(str(cfg.get("front", "front.png")))
	if house_front.texture == null:
		house_front.texture = _house_ph(true)
	add_child(house_front)


## 小屋占位：back = 暗墙 + 地板线 + 门；front = 不透明的前墙 + 一扇暖窗（进屋淡出）
func _house_ph(front: bool) -> ImageTexture:
	var w := int(size.x)
	var h := int(size.y)
	var img := Image.create_empty(w, h, false, Image.FORMAT_RGBA8)
	var fl := int(_ground_y)
	if front:
		img.fill_rect(Rect2i(0, 10, w, fl - 9), Color("#323c44"))
		img.fill_rect(Rect2i(0, 0, w, 10), Color("#232a30"))
		img.fill_rect(Rect2i(w / 2 - 14, 60, 28, 22), Color("#d9a35a"))
		img.fill_rect(Rect2i(int(float(cfg.get("door", 40))) - 9, fl - 40, 18, 41), Color("#4a3f2f"))
	else:
		img.fill_rect(Rect2i(0, 10, w, fl - 9), Color("#262c30"))
		img.fill_rect(Rect2i(0, fl + 1, w, maxi(h - fl - 1, 1)), Color("#352e24"))
		img.fill_rect(Rect2i(0, fl, w, 1), Color("#4a3f2f"))
	return ImageTexture.create_from_image(img)


# ---------------------------------------------------------------- 物件
func _make_object(oid: String, raw) -> void:
	var c: Dictionary = (raw as Dictionary).duplicate() if raw is Dictionary else {}
	var s := Sprite2D.new()
	s.name = "O_" + oid
	s.centered = false
	var tex := _tex(str(c.get("img", oid + ".png")))
	var frames := maxi(int(c.get("frames", 1)), 1)
	if tex == null:
		c["ph"] = true
		var w := int(c.get("w", 16))
		tex = block(w * frames, int(c.get("h", 16)), PH_OBJ)
	s.texture = tex
	s.hframes = frames
	if not c.has("w"):
		c["w"] = tex.get_width() / frames
	if not c.has("h"):
		c["h"] = tex.get_height()
	s.position = Vector2(float(c.get("x", 0)), float(c.get("y", 0)))
	var z := -5 if is_house else -1
	if c.get("front", false) or str(c.get("layer", "")) == "front":
		z = 50
	s.z_index = int(c.get("z", z))
	add_child(s)
	objects[oid] = s
	ocfg[oid] = c
	var d := str(c.get("default", ""))
	ostate[oid] = d
	_apply_state(oid)


## 剧本 prop 了、room.json 里没有的东西：在同名 marker 那里放一块占位色块（每个状态一档深浅）
func add_placeholder_object(oid: String) -> void:
	if objects.has(oid) or not markers.has(oid):
		return
	var x: float = markers[oid]
	_make_object(oid, {"x": round(x - 8), "y": round(ground_local(x) - 15), "w": 16, "h": 16})


func has_object(oid: String) -> bool:
	return objects.has(oid)


func object(oid: String) -> Sprite2D:
	return objects.get(oid, null)


func set_prop(oid: String, state: String, instant := false) -> void:
	if objects.has(oid):
		ostate[oid] = state
		_apply_state(oid)
	if not is_nan(water_base) and str(cfg["water"].get("prop", "")) == oid:
		ostate[oid] = state
		_water_to_state(state, instant)


func prop_state(oid: String) -> String:
	return str(ostate.get(oid, ""))


func owns_prop(oid: String) -> bool:
	return objects.has(oid) or (not is_nan(water_base) and str(cfg["water"].get("prop", "")) == oid)


func _apply_state(oid: String) -> void:
	var s: Sprite2D = objects[oid]
	var c: Dictionary = ocfg[oid]
	var st := str(ostate.get(oid, ""))
	_oloop.erase(oid)
	if st in HIDE_STATES:
		s.set_meta("hidden", true)
		_refresh_vis(oid)
		return
	s.set_meta("hidden", false)
	_refresh_vis(oid)
	if st in SHOW_STATES:
		s.frame = 0
		return
	var states = c.get("states", null)
	if states is Dictionary and (states as Dictionary).has(st):
		var v = states[st]
		if v is Array and (v as Array).size() >= 2:
			_oloop[oid] = [int(v[0]), int(v[1])]
			s.frame = clampi(int(v[0]), 0, s.hframes - 1)
		else:
			s.frame = clampi(int(v), 0, s.hframes - 1)
		return
	if states is Array and (states as Array).has(st):
		s.frame = clampi((states as Array).find(st), 0, s.hframes - 1)
		return
	var alt := _tex(str(c.get("img", oid + ".png")).get_basename() + "_" + st + ".png")
	if alt != null:
		s.texture = alt
		s.hframes = 1
		s.frame = 0
		return
	if c.get("ph", false):
		# 占位：每个状态换一档深浅（看得出变了）
		var k := float(absi(hash(st)) % 5) / 5.0
		s.texture = block(int(c["w"]) * s.hframes, int(c["h"]), PH_OBJ.lerp(Color("#c9d2d8"), k * 0.6))
		return
	_warn("物件 %s 没有状态 %s（用第 0 帧）" % [oid, st])
	s.frame = 0


func _refresh_vis(oid: String) -> void:
	var s: Sprite2D = objects[oid]
	var c: Dictionary = ocfg[oid]
	var vis := not bool(s.get_meta("hidden", false))
	var on := str(c.get("on", ""))
	if vis and on.contains("="):
		var parts := on.split("=")
		vis = world != null and str(world.prop_state(parts[0])) == parts[1]
	s.visible = vis


## 物件的矩形（世界坐标；藏着 = 空）
func object_rect(oid: String) -> Rect2:
	var s: Sprite2D = objects.get(oid, null)
	if s == null or not s.visible or not visible:
		return Rect2()
	var c: Dictionary = ocfg[oid]
	if c.has("click"):
		var cl: Array = c["click"]
		return Rect2(origin + Vector2(float(cl[0]), float(cl[1])) + (s.position - Vector2(float(c.get("x", 0)), float(c.get("y", 0)))),
			Vector2(float(cl[2]), float(cl[3])))
	return Rect2(origin + s.position, Vector2(float(c["w"]), float(c["h"])))


## 物件平滑挪到房间坐标 p（smoothstep，取整）；await 它等挪完
func move_object(oid: String, p: Vector2, sec := 0.6) -> void:
	var s: Sprite2D = objects.get(oid, null)
	if s == null:
		_warn("move_object：没有物件 " + oid)
		return
	if sec <= 0.0:
		s.position = p.round()
		return
	var from := s.position
	var tw := create_tween()
	tw.tween_method(func(k: float):
		var e := k * k * (3.0 - 2.0 * k)
		s.position = from.lerp(p, e).round(), 0.0, 1.0, sec)
	await tw.finished


func add_node(n: Node, z := 0) -> void:
	if n is CanvasItem:
		(n as CanvasItem).z_index = z
	add_child(n)


# ======================================================================= markers / 地面 / 墙
func has_marker(n: String) -> bool:
	return markers.has(n)


## marker 的世界 x
func mx(n: String) -> float:
	return origin.x + float(markers.get(n, 0.0))


func marker_local(n: String) -> float:
	return float(markers.get(n, 0.0))


func to_world(p: Vector2) -> Vector2:
	return origin + p


func to_local_px(p: Vector2) -> Vector2:
	return p - origin


## 地面（房间 y）
func ground_local(lx: float) -> float:
	if _ground_pts.size() < 2:
		return _ground_y
	var a: Array = _ground_pts[0]
	if lx <= float(a[0]):
		return float(a[1])
	for i in range(1, _ground_pts.size()):
		var b: Array = _ground_pts[i]
		if lx <= float(b[0]):
			var k := (lx - float(a[0])) / maxf(float(b[0]) - float(a[0]), 1.0)
			return round(lerpf(float(a[1]), float(b[1]), k))
		a = b
	return float(a[1])


## 地面（世界 y）：晨 / NPC 的 position.y = round(这个) + 1
func ground_y(wx: float) -> float:
	return origin.y + ground_local(wx - origin.x)


## 能走的左右（世界 x）
func walls() -> Vector2:
	var w: Vector2 = _v2(cfg.get("walk", [16, size.x - 16]), Vector2(16, size.x - 16))
	for wc in cfg.get("walk_when", []):
		if not wc is Dictionary:
			continue
		var ok := StoryState.all_of(wc.get("need", [])) and StoryState.none_of(wc.get("not", []))
		var pr := str(wc.get("prop", ""))
		if ok and pr.contains("="):
			var parts := pr.split("=")
			ok = world != null and str(world.prop_state(parts[0])) == parts[1]
		if ok:
			w = _v2(wc.get("walk", [w.x, w.y]), w)
			break
	if walk_override is Vector2:
		w = walk_override
	var rope = cfg.get("rope", null)
	if rope is Dictionary and rope_on():
		w.y = minf(w.y, float(rope.get("end", w.y)))
	return Vector2(origin.x + w.x, origin.x + w.y)


func set_walk(w: Vector2) -> void:
	walk_override = w


func clear_walk() -> void:
	walk_override = null


func center() -> Vector2:
	return origin + size / 2.0


## 镜头中心的 y（世界）
func cam_y() -> float:
	if is_house and host != null:
		return host.cam_y()
	return origin.y + float(cfg.get("cam_y", 135))


## 镜头 x 夹在房间里（房间比一屏窄就居中）
func clamp_cam_x(x: float) -> float:
	if is_house and host != null:
		return host.clamp_cam_x(x)
	if size.x <= 480.0:
		return origin.x + size.x / 2.0
	return clampf(x, origin.x + 240.0, origin.x + size.x - 240.0)


## 两头的入口：[{edge, to, at, kind, need, not, x}]
func portals() -> Array:
	return cfg.get("portals", [])


func portal_to_room(r: String) -> Dictionary:
	for p in portals():
		if p is Dictionary and str(p.get("to", "")) == r:
			return p
	return {}


func portal_open(p: Dictionary) -> bool:
	return StoryState.all_of(p.get("need", [])) and StoryState.none_of(p.get("not", []))


# ======================================================================= 水位
func water_y() -> float:
	return water_cur


func _water_to_state(state: String, instant: bool) -> void:
	var lv: Dictionary = cfg["water"].get("levels", {})
	if not lv.has(state):
		_warn("水位没有这一档：" + state)
		return
	set_water(float(lv[state]), 0.0 if instant else float(cfg["water"].get("sec", 1.5)))


## 水位挪到 y（房间坐标），sec 秒 smoothstep；await 等水停
func set_water(y: float, sec := 1.5) -> void:
	if is_nan(water_base):
		water_base = y
		water_cur = y
		_warn("room.json 没有 water，set_water 只记数")
		return
	if _water_tw != null and _water_tw.is_valid():
		_water_tw.kill()
	if sec <= 0.0:
		water_cur = y
		_place_layers_y()
		return
	var from := water_cur
	_water_tw = create_tween()
	_water_tw.tween_method(func(k: float):
		water_cur = lerpf(from, y, k * k * (3.0 - 2.0 * k))
		_place_layers_y(), 0.0, 1.0, sec)
	await _water_tw.finished


func _place_layers_y() -> void:
	for L in _layers:
		var c: Dictionary = L["cfg"]
		var y := float(c.get("y", 0))
		if c.get("water", false) and not is_nan(water_base):
			y += round(water_cur - water_base)
		(L["node"] as Sprite2D).position.y = y
	if _ph_node != null:
		_ph_node.queue_redraw()


# ======================================================================= 每帧
func update(delta: float, cam_center: Vector2) -> void:
	_t += delta
	if not is_house:
		var cl := cam_center.x - 240.0 - origin.x
		for L in _layers:
			var c: Dictionary = L["cfg"]
			var s: Sprite2D = L["node"]
			var sc := float(c.get("scroll", 1.0))
			var x := float(c.get("x", 0)) + float(c.get("drift", 0.0)) * _t
			if L["tile"]:
				var w: float = L["w"]
				var sx := fposmod(roundf(x - cl * sc), w) - w
				s.position.x = roundf(cl) + sx
			else:
				s.position.x = roundf(x + cl * (1.0 - sc))
		if _layers.size() > 0 and _t < delta * 1.5:
			_place_layers_y()
	for oid in objects:
		var s: Sprite2D = objects[oid]
		_refresh_vis(oid)
		var lp = _oloop.get(oid, null)
		if lp is Array and s.visible:
			var c: Dictionary = ocfg[oid]
			var ms := float(c.get("ms", 1000.0 / maxf(float(c.get("fps", 10)), 0.1)))
			var n: int = int(lp[1]) - int(lp[0]) + 1
			s.frame = clampi(int(lp[0]) + int(_t * 1000.0 / ms) % maxi(n, 1), 0, s.hframes - 1)
	_update_walkers(delta)
	if _rope != null:
		_rope.queue_redraw()


# ======================================================================= 背景走过的小人
func _build_walkers() -> void:
	for wc in cfg.get("walkers", []):
		if not wc is Dictionary:
			continue
		var path: Array = wc.get("path", [])
		if path.size() < 2:
			continue
		for k in maxi(int(wc.get("count", 1)), 1):
			var n: Node2D = NPC_GD.new()
			n.shadow = false                   # 背景小人：没有脚下阴影、占位不写名字
			n.setup(str(wc.get("npc", "walker")))
			n.z_index = int(wc.get("z", -20))
			add_child(n)
			var p0 := _v2(path[0], Vector2.ZERO)
			var p1 := _v2(path[1], Vector2.ZERO)
			var t0 := float(k) / maxi(int(wc.get("count", 1)), 1)
			n.position = p0.lerp(p1, t0).round()
			walkers.append({"npc": n, "cfg": wc, "i": 1, "dir": 1, "wait": 0.0, "x": n.position.x})


func _update_walkers(delta: float) -> void:
	for w in walkers:
		var n: Node2D = w["npc"]
		var c: Dictionary = w["cfg"]
		var path: Array = c["path"]
		if float(w["wait"]) > 0.0:
			w["wait"] = float(w["wait"]) - delta
			n.play("idle")
			continue
		var goal := _v2(path[int(w["i"])], n.position)
		var sp := float(c.get("speed", 16))
		var d := goal.x - float(w["x"])
		if absf(d) <= sp * delta:
			w["x"] = goal.x
			n.position = goal.round()
			var loop := str(c.get("loop", "pingpong"))
			var pz = c.get("pause", 0)
			var pause := float(pz) if not pz is Array else randf_range(float(pz[0]), float(pz[1]))
			w["wait"] = pause
			var ni: int = int(w["i"]) + int(w["dir"])
			if ni >= path.size() or ni < 0:
				match loop:
					"wrap":
						w["i"] = 1
						w["x"] = _v2(path[0], n.position).x
						n.position = _v2(path[0], n.position).round()
						continue
					"once":
						n.visible = false
						w["wait"] = INF
						continue
					_:
						w["dir"] = -int(w["dir"])
						ni = int(w["i"]) + int(w["dir"])
			w["i"] = clampi(ni, 0, path.size() - 1)
			continue
		w["x"] = float(w["x"]) + signf(d) * sp * delta
		n.position = Vector2(round(float(w["x"])), goal.y)
		n.face(1 if d > 0 else -1)
		n.play("walk")


# ======================================================================= 装饰脚本
func _build_scripts() -> void:
	for sc in cfg.get("scripts", []):
		if not sc is Dictionary or not ResourceLoader.exists(str(sc.get("script", ""))):
			_warn("scripts：找不到 " + str(sc.get("script", "") if sc is Dictionary else sc))
			continue
		var gd: GDScript = load(str(sc["script"]))
		var n = gd.new()
		if not n is Node:
			continue
		if n is Node2D:
			(n as Node2D).position = Vector2(float(sc.get("x", 0)), float(sc.get("y", 0)))
			(n as Node2D).z_index = int(sc.get("z", -60))
		var pr: Dictionary = sc.get("params", {})
		for k in pr:
			n.set(str(k), pr[k])
		add_child(n)


# ======================================================================= 导绳（水下仓库）
func rope_on() -> bool:
	var rope = cfg.get("rope", null)
	if not rope is Dictionary:
		return false
	var pr := str(rope.get("prop", ""))
	return pr == "" or (world != null and str(world.prop_state(pr)) == str(rope.get("on", "on")))


func _build_rope() -> void:
	if not cfg.get("rope", null) is Dictionary:
		return
	_rope = Node2D.new()
	_rope.name = "Rope"
	_rope.z_index = -1
	_rope.draw.connect(_draw_rope)
	add_child(_rope)


func _draw_rope() -> void:
	var rope: Dictionary = cfg["rope"]
	var col := _col(rope.get("color", "#9aa6a0"), Color("#9aa6a0"))
	var a := _v2(rope.get("anchor", [20, 150]), Vector2(20, 150))
	for kx in rope.get("knots", []):
		_rope.draw_rect(Rect2(float(kx) - 1, a.y - 1, 3, 3), col)
	if not rope_on() or world == null or world.level == null or world.room != id:
		return
	var chen: Node2D = world.level.chen
	var b := chen.position - origin + Vector2(0, -22)
	var n := 16
	var prev := a
	for i in range(1, n + 1):
		var k := float(i) / n
		var p := a.lerp(b, k) + Vector2(0, 6.0 * sin(PI * k))
		_rope.draw_line(prev.round(), p.round(), col, 1.0)
		prev = p


# ======================================================================= 环境声
func ambient_enter(on: bool) -> void:
	if _amb.is_empty() and on:
		for ac in cfg.get("ambient", []):
			if not ac is Dictionary:
				continue
			var nm := str(ac.get("name", ""))
			var p := ""
			for ext in [".ogg", ".wav"]:
				if ResourceLoader.exists("res://audio/sfx/" + nm + ext):
					p = "res://audio/sfx/" + nm + ext
					break
			if p == "":
				_warn("环境声还没有：" + nm)
				continue
			var pl: Node
			if ac.has("x"):
				var p2 := AudioStreamPlayer2D.new()
				p2.position = Vector2(float(ac["x"]), ground_local(float(ac["x"])) - 20)
				p2.max_distance = float(ac.get("range", 300))
				pl = p2
			else:
				pl = AudioStreamPlayer.new()
			pl.set("stream", load(p))
			pl.set("bus", "SFX")
			pl.set("volume_db", -60.0)
			add_child(pl)
			pl.connect("finished", Callable(pl, "play"))
			_amb.append({"player": pl, "db": float(ac.get("db", -10))})
	for a in _amb:
		var pl: Node = a["player"]
		if on and not bool(pl.get("playing")):
			pl.call("play")
		var tw := create_tween()
		tw.tween_property(pl, "volume_db", float(a["db"]) if on else -60.0, 0.8)
		if not on:
			tw.tween_callback(Callable(pl, "stop"))
