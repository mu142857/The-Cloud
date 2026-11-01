extends Node2D
## 终章母星尾声：作者的城市（scenes/city_test.tscn，图和场景是 tools/city_art.py 画的）当成一个房间用。
## art/city/room.json 的 scripts 里放这个（room_stage 建房间时 new 一个，父节点是 room_stage）。
## 城市的图、场景、city_test.gd 一样都不改：把场景实例化出来，只拿走图层（Parallax2D，人群、雨、路灯、闪烁的窗都在里面）
## 和两个 CanvasLayer（近处走过的大剪影 Passers、暗角 Overlay）；场景自己的镜头、晨、根节点（city_test.gd）都不要，直接释放。
## - 图层坐标就是房间坐标：room.json 里 cam_y 175、地面 228，和 city_test 一样（路沿在屏幕 y 188，下面是湿街面）。
##   Parallax2D 按关卡的镜头自己算视差、左右绕回，房间多宽都铺得满。origin 的 x 要是 0（远景层横向视差按世界 x 算），y 随便。
## - 前后：晨前面的（MainNear 近排的人、Wet 湿街面倒影、Ripples 涟漪、Glow 路灯光晕、Front 前景）z 往上放，其余按原来的顺序在晨后面。
## - 湿街面的 shader 每帧要镜头左边缘和晨在屏幕上的 x（city_test.gd 的 _process 做的，这里照抄）。
## - CanvasLayer 不跟着父节点藏：房间不显示（晨不在城市）时手动关掉，图层也停掉 process（人群、雨不白算）。
## - 晨进城时 story_world 只 set_env("city")，这里补上路灯光锥照在晨身上的那个函数（city_test.gd 的 _ready 同款）。

const SCENE := "res://scenes/city_test.tscn"
const FRONT := ["MainNear", "Wet", "Ripples", "Glow", "Front"]
const ENV_LIGHT := preload("res://scripts/env_light.gd")

var _wet: ShaderMaterial
var _canvas: Array[CanvasLayer] = []
var _shafts: Node2D
var _on := false
var _sky: Node2D
var _logged := false


func _ready() -> void:
	var root: Node = (load(SCENE) as PackedScene).instantiate()
	# 只跟屏幕走的层（scroll_scale.y = 0：天空、湿街面）：Parallax2D 把它放在「屏幕左上角」的位置，那是世界坐标，
	# 父节点的 origin 会多加一遍，所以挂在一个抵消 origin 的节点下（房间放在芦苇地下面，F8 地图上不和森林、河岸叠在一起）
	var screen := Node2D.new()
	screen.name = "ScreenFixed"
	var o = get_parent().get("origin")
	screen.position = -(o as Vector2) if o is Vector2 else Vector2.ZERO
	add_child(screen)
	var back_z := -95
	var front_z := 60
	for c in root.get_children():
		if not (c is Parallax2D or c is CanvasLayer):
			continue
		root.remove_child(c)
		_disown(c)
		if c is Parallax2D and is_zero_approx((c as Parallax2D).scroll_scale.y):
			screen.add_child(c)
		else:
			add_child(c)
		if c is CanvasLayer:
			_canvas.append(c)
			(c as CanvasLayer).visible = false     # 一开始房间是藏着的（不然开章第一帧暗角会盖在驾驶舱上）
			continue
		var p: Parallax2D = c
		if FRONT.has(str(p.name)):
			p.z_index = front_z
			front_z += 1
		else:
			p.z_index = back_z
			back_z += 1
		if str(p.name) == "Sky":
			_sky = p
		if str(p.name) == "Shafts":
			_shafts = p
		if str(p.name) == "Wet" and p.get_node_or_null("Rect") != null:
			_wet = (p.get_node("Rect") as CanvasItem).material as ShaderMaterial
	root.free()
	for c in get_children():
		c.process_mode = Node.PROCESS_MODE_DISABLED       # 晨进城的那一帧 _process 再打开


func _disown(n: Node) -> void:
	n.owner = null
	for c in n.get_children():
		_disown(c)


func _process(_delta: float) -> void:
	var vis := is_visible_in_tree()
	if vis != _on:
		_on = vis
		for l in _canvas:
			l.visible = vis
		for c in get_children():
			c.process_mode = Node.PROCESS_MODE_INHERIT if vis else Node.PROCESS_MODE_DISABLED   # 不在城市时人群、雨都不算
	if not vis:
		return
	var world = get_parent().get("world")
	if world == null or world.level == null:
		return
	var chen: Node2D = world.chen
	var cl: float = world.level.cam_left().x
	if not _logged and _sky != null:
		_logged = true            # 自测用（headless 也算得出来）：天空层左上角应该正好在屏幕左上角，sky_d = (0, 0)
		print("CITY_ROOM sky_d=%s" % str((_sky.global_position - world.level.cam_left()).round()))
	if _wet != null:
		_wet.set_shader_parameter("cam_left", cl)
		_wet.set_shader_parameter("chen_x", chen.position.x - cl)
	if _shafts != null and str(chen.get("env")) == "city" and not (chen.get("light_fn") as Callable).is_valid():
		var sh := _shafts
		chen.set_env("city", func(c): return ENV_LIGHT.polygon_shafts(c, sh))
