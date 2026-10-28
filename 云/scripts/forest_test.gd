extends Node2D
## 针叶林第一关小样：晨（scenes/chen.tscn）在主层地面上走，←/→ 或 A/D 走（按住 Shift 快一点），
## ↓ / S 转过来正面站着，空格让晨自己一直往右走（展示模式）/ 停下。
## 镜头水平跟着晨（有一点平滑，往她面朝的方向多看 LOOK 像素），竖直固定 135。
## 图层是 tools/forest_art.py 画的，各层 scroll_scale 和脚本里的 SCROLL 一样。
##
## 命令行（-- 后面）：
##   --x=300            开场镜头左边缘在 x=300（晨站在镜头里）
##   --walk=3           开场晨自动往右走 3 秒再停（负数往左走）
##   --shot=out.png     存一张图后退出：有 --walk 就在走完那一刻存（还是跑步的姿势），否则开场 20 帧后存
##   --shots=目录 --start=30 --every=3 --count=8
##                      连拍：从第 start 帧开始，每 every 帧存一张 目录/shot_000.png …，存够 count 张退出
## 例：Godot --path . --fixed-fps 60 -- --walk=4 --shots=/tmp/w --start=0 --every=4 --count=60 --shadow_auto=0

const LOOK := 36.0          # 镜头往晨面朝的方向多看多少像素
const FOLLOW := 3.0         # 跟随的快慢（越大越紧）

@onready var cam: Camera2D = $Camera
@onready var chen: Node2D = $Chen
@onready var shafts: Array[Node] = $Main/Shafts.get_children()

var _t := 0.0
var _frame := 0
var _shot := ""
var _walk := 0.0            # 还要自动走几秒（0 = 不走 / 走完了）
var _walked := false        # 给了 --walk
var _dir := ""
var _start := 30
var _every := 3
var _count := 8
var _saved := 0


func _ready() -> void:
	chen.set_env("forest", func(c): return preload("res://scripts/env_light.gd").polygon_shafts(c, $Main/Shafts))     # 光柱照到晨身上
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			_shot = a.trim_prefix("--shot=")
		elif a.begins_with("--x="):
			chen.position.x = round(float(a.trim_prefix("--x=")) + 240.0 - LOOK)
		elif a.begins_with("--walk="):
			_walk = float(a.trim_prefix("--walk="))
			_walked = _walk != 0.0
		elif a.begins_with("--shots="):
			_dir = a.trim_prefix("--shots=")
		elif a.begins_with("--start="):
			_start = int(a.trim_prefix("--start="))
		elif a.begins_with("--every="):
			_every = int(a.trim_prefix("--every="))
		elif a.begins_with("--count="):
			_count = int(a.trim_prefix("--count="))
	if _walked:
		chen.auto_dir = signf(_walk)
		_walk = absf(_walk)
	if _dir != "":
		DirAccess.make_dir_recursive_absolute(_dir)
	cam.position = Vector2(_cam_target(), 135.0)


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
	# 光柱慢慢呼吸，几根错开
	for i in shafts.size():
		var s := shafts[i] as CanvasItem
		s.modulate.a = 0.75 + 0.25 * sin(_t * 0.6 + i * 1.9)
	if _shot != "" and not _walked and _frame == 20:
		_save(_shot)
		get_tree().quit()
	if _dir != "" and _frame >= _start and (_frame - _start) % _every == 0:
		_save(_dir.path_join("shot_%03d.png" % _saved))
		_saved += 1
		if _saved >= _count:
			get_tree().quit()


func _save(path: String) -> void:
	# 窗口被别的窗口挡住时 Godot 会跳过绘制（存下来的是同一张）：存之前强制画一遍
	RenderingServer.force_draw(false)
	get_viewport().get_texture().get_image().save_png(path)
