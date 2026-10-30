extends Node2D
## 河流篇水下仓库（art/river_city/warehouse/room.json 的 scripts 里挂）：把作者原来水底小样（scenes/underwater_test.tscn）里
## 会动的东西原样搬进房间——水面里碎掉的月亮、月光光柱、最远处游过的鲸、左上一群小鱼、石头人头上的焦散和发光果荚、
## 河床上的焦散、果荚、气泡，再加出口灯的一圈暖光。脚本、shader、参数都是原来那套，这里只管「放在哪一层」：
## 房间引擎的层是 Sprite2D（层的房间 x = x + 镜头左边缘 × (1 − scroll)），这里每帧按同一个公式摆每一组子节点，
## 所以和 room.json 里同 scroll 的层严丝合缝（head 层的 x = head_x，tile 的层按 960 循环）。
## z：每组照 room.json 里对应层的 z 往上插一格（room.json 的层 z 写死了：deep −100 … head −92、headweeds −90、kelp −86、main −80）。
## 开销：和水底小样一样（一个全屏光柱 shader、两张焦散、几十个 1×1 的 draw_rect）。

const UW := "res://art/underwater/"
const W := 960.0

@export var head_x := 0.0                        # head 层的 x（和 room.json 一样）
@export var bedlight := ""                       # 主层的焦散遮罩（房间宽）
@export var pods: Array = []                     # 主层上的发光果荚 [[x, y, 大小]]
@export var bubbles: Array = []                  # 河床上冒泡的泉眼 [[x, y]]
@export var warm: Array = []                     # 出口灯的暖光 [[x, y]]

var _groups: Array = []                          # [{node, scroll, x, tile}]
var _shafts: ColorRect
var _surface: Sprite2D
var _warm: Node2D


func _ready() -> void:
	_surface = Sprite2D.new()
	_surface.centered = false
	_surface.texture = load(UW + "surface.png")
	_surface.material = _mat("res://scripts/underwater_surface.gdshader", {
		"c0": Color(0.169, 0.251, 0.302), "c1": Color(0.255, 0.353, 0.388), "c2": Color(0.361, 0.451, 0.482),
		"c3": Color(0.482, 0.553, 0.573), "speed": 0.8, "wobble": 3.0, "flicker": 0.9})
	_surface.z_index = -99
	add_child(_surface)

	var deeper := _group(0.05, 0.0, false, -97)
	var whale: Node2D = (load("res://scripts/underwater_whale.gd") as GDScript).new()
	whale.material = _mat("res://scripts/underwater_shadow.gdshader", {})
	deeper.add_child(whale)

	var far := _group(0.08, 0.0, false, -95)
	var school: Node2D = (load("res://scripts/underwater_school.gd") as GDScript).new()
	school.material = _mat("res://scripts/underwater_shadow.gdshader", {})
	far.add_child(school)
	var glint: Node2D = (load("res://scripts/underwater_school.gd") as GDScript).new()
	glint.set("mode", 1)
	glint.material = _add()
	far.add_child(glint)

	var head := _group(0.3, head_x, true, -91)
	var hl := Sprite2D.new()
	hl.centered = false
	hl.texture = load(UW + "headlight.png")
	hl.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	hl.region_enabled = true
	hl.region_rect = Rect2(0, 0, 480 + W * 2, 270)
	hl.material = _mat("res://scripts/underwater_caustics.gdshader", {"pattern": load(UW + "caustic.png"),
		"color": Color(0.5, 0.7, 0.86), "strength": 0.3, "speed": 0.8, "squash": 1.4, "lit": Vector2(360, 120), "step_a": 0.05})
	head.add_child(hl)
	var hg := _group(0.3, head_x, true, -89)
	var glow: Node2D = (load("res://scripts/underwater_glow.gd") as GDScript).new()
	glow.set("lights", _v3s([[369, 114, 1], [369 + W, 114, 1], [369 + W * 2, 114, 1]]))
	glow.set("period", 6.5)
	glow.set("seed", 4)
	hg.add_child(glow)

	_shafts = (load("res://scripts/underwater_shafts.gd") as GDScript).new()
	_shafts.size = Vector2(480, 270)
	_shafts.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_shafts.material = _mat("res://scripts/underwater_shafts.gdshader", {"color": Color(0.55, 0.74, 0.92), "step_a": 0.018})
	_shafts.z_index = -88
	add_child(_shafts)

	if bedlight != "" and ResourceLoader.exists(bedlight):
		var bl := Sprite2D.new()
		bl.centered = false
		bl.texture = load(bedlight)
		bl.material = _mat("res://scripts/underwater_caustics.gdshader", {"pattern": load(UW + "caustic.png"),
			"color": Color(0.5, 0.7, 0.86), "strength": 0.6, "speed": 1.0, "squash": 3.0, "lit": Vector2(320, 130), "step_a": 0.05})
		bl.z_index = -79
		add_child(bl)
	if not pods.is_empty():
		var pg: Node2D = (load("res://scripts/underwater_glow.gd") as GDScript).new()
		pg.set("lights", _v3s(pods))
		pg.set("period", 5.0)
		pg.set("seed", 8)
		pg.z_index = -78
		add_child(pg)
	if not bubbles.is_empty():
		var bb: Node2D = (load("res://scripts/underwater_bubbles.gd") as GDScript).new()
		var src: Array[Vector2] = []
		for b in bubbles:
			src.append(Vector2(float(b[0]), float(b[1])))
		bb.set("sources", src)
		bb.z_index = -78
		add_child(bb)
	if not warm.is_empty():
		_warm = Node2D.new()
		_warm.material = _add()
		_warm.z_index = -2
		_warm.draw.connect(_draw_warm)
		add_child(_warm)
	_place()


func _process(_d: float) -> void:
	_place()
	if _warm != null:
		_warm.queue_redraw()


## 每组按房间引擎的视差公式摆（tile 的组按 960 循环，和 room_stage.gd update() 一样）
func _place() -> void:
	var cam := get_viewport().get_camera_2d()
	if cam == null:
		return
	var room := get_parent() as Node2D
	var cl := cam.get_screen_center_position().x - 240.0 - (room.position.x if room != null else 0.0)
	for g in _groups:
		var n: Node2D = g["node"]
		var sc: float = g["scroll"]
		if g["tile"]:
			n.position.x = roundf(cl) + fposmod(roundf(float(g["x"]) - cl * sc), W) - W
		else:
			n.position.x = roundf(float(g["x"]) + cl * (1.0 - sc))
	_surface.position = Vector2(roundf(cl), 0)
	_shafts.position = Vector2(roundf(cl), 0)


func _group(scroll: float, x: float, tile: bool, z: int) -> Node2D:
	var n := Node2D.new()
	n.z_index = z
	add_child(n)
	_groups.append({"node": n, "scroll": scroll, "x": x, "tile": tile})
	return n


## 出口灯：一圈很淡的暖光，和灯一起一明一暗（900ms，跟 room.json 里灯的帧对上）
func _draw_warm() -> void:
	var t = get_parent().get("_t")                # 房间的钟（物件的帧也按它走）
	var on := int(float(t if t != null else 0.0) * 1000.0 / 900.0) % 2 == 0
	var k := 1.0 if on else 0.6
	for p in warm:
		var c := Vector2(float(p[0]), float(p[1]))
		for r in [[14.0, 0.035], [9.0, 0.05], [5.0, 0.07]]:
			_warm.draw_circle(c, r[0], Color(0.69, 0.47, 0.26, r[1] * k), true, -1.0, false)


func _mat(path: String, params: Dictionary) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = load(path)
	for k in params:
		m.set_shader_parameter(k, params[k])
	return m


func _add() -> CanvasItemMaterial:
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	return m


func _v3s(a: Array) -> Array[Vector3]:
	var out: Array[Vector3] = []
	for v in a:
		out.append(Vector3(float(v[0]), float(v[1]), float(v[2])))
	return out
