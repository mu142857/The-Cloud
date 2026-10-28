extends Node2D
## 城市小样：晨（scenes/chen.tscn）在街上走，←/→ 或 A/D 走（按住 Shift 快一点），
## ↓ / S 转过来正面站着，空格让晨自己一直往右走（展示模式）/ 停下。
## 镜头水平跟着晨（有一点平滑，往她面朝的方向多看 LOOK 像素），竖直固定 135。
## 图层是 tools/city_art.py 画的，场景 scenes/city_test.tscn 也是它写的（各层 scroll_scale 和脚本里的 SCROLL 一样）。
## 街面是平的：地面 y = GROUND（路沿那一行受光边）。
##
## 命令行（-- 后面），和 forest_test.gd 一样：
##   --x=300            开场镜头左边缘在 x=300（晨站在镜头里）
##   --walk=3           开场晨自动往右走 3 秒再停（负数往左走）
##   --shot=out.png     存一张图后退出：有 --walk 就在走完那一刻存（还是跑步的姿势），否则开场 20 帧后存
##   --wait=90          不走的时候，开场第几帧存（默认 20；想让烟、亮窗先跑起来就给大一点）
##   --shots=目录 --start=30 --every=3 --count=8
##                      连拍：从第 start 帧开始，每 every 帧存一张 目录/shot_000.png …，存够 count 张退出
## 例：Godot --path . --fixed-fps 60 res://scenes/city_test.tscn -- --walk=4 --shots=/tmp/w --start=0 --every=4 --count=60

const LOOK := 36.0
const FOLLOW := 3.0
const GROUND := 228.0

@onready var cam: Camera2D = $Camera
@onready var chen: Node2D = $Chen
@onready var rays: Array[Node] = $Shafts.get_children()

var _t := 0.0
var _frame := 0
var _shot := ""
var _wait := 20
var _walk := 0.0
var _walked := false
var _dir := ""
var _start := 30
var _every := 3
var _count := 8
var _saved := 0


func _ready() -> void:
	chen.ground_fn = ground_y
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			_shot = a.trim_prefix("--shot=")
		elif a.begins_with("--x="):
			chen.position.x = round(float(a.trim_prefix("--x=")) + 240.0 - LOOK)
		elif a.begins_with("--walk="):
			_walk = float(a.trim_prefix("--walk="))
			_walked = _walk != 0.0
		elif a.begins_with("--wait="):
			_wait = int(a.trim_prefix("--wait="))
		elif a.begins_with("--shots="):
			_dir = a.trim_prefix("--shots=")
		elif a.begins_with("--start="):
			_start = int(a.trim_prefix("--start="))
		elif a.begins_with("--every="):
			_every = int(a.trim_prefix("--every="))
		elif a.begins_with("--count="):
			_count = int(a.trim_prefix("--count="))
	chen._snap()
	if _walked:
		chen.auto_dir = signf(_walk)
		_walk = absf(_walk)
	if _dir != "":
		DirAccess.make_dir_recursive_absolute(_dir)
	cam.position = Vector2(_cam_target(), 135.0)


func ground_y(_x: float) -> float:
	return GROUND


func _cam_target() -> float:
	return chen.position.x + chen.facing * LOOK


func _process(delta: float) -> void:
	_t += delta
	_frame += 1
	if Input.is_action_just_pressed("ui_accept"):
		chen.auto_dir = 0.0 if chen.auto_dir != 0.0 else 1.0
	if _walk > 0.0 and _t >= _walk:
		_walk = 0.0
		chen.auto_dir = 0.0
		if _shot != "":
			_save(_shot)
			get_tree().quit()
	cam.position.x = lerpf(cam.position.x, _cam_target(), 1.0 - exp(-FOLLOW * delta))
	cam.position.y = 135.0
	# 天缝里漏下来的几道斜光慢慢呼吸，几道错开（烟霾在动）
	for i in rays.size():
		var r := rays[i] as CanvasItem
		r.modulate.a = 0.7 + 0.3 * sin(_t * 0.35 + i * 2.1)
	if _shot != "" and not _walked and _frame == _wait:
		_save(_shot)
		get_tree().quit()
	if _dir != "" and _frame >= _start and (_frame - _start) % _every == 0:
		_save(_dir.path_join("shot_%03d.png" % _saved))
		_saved += 1
		if _saved >= _count:
			get_tree().quit()


func _save(path: String) -> void:
	# 窗口被挡住或最小化时 Godot 会跳过绘制：存之前强制画一遍
	RenderingServer.force_draw(false)
	get_viewport().get_texture().get_image().save_png(path)
