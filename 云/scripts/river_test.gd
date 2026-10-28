extends Node2D
## 河流星球小样：晨（scenes/chen.tscn）在近岸的卵石线上走，←/→ 或 A/D 走（按住 Shift 快一点），
## ↓ / S 转过来正面站着，空格让晨自己一直往右走（展示模式）/ 停下。
## 镜头水平跟着晨（有一点平滑，往她面朝的方向多看 LOOK 像素），竖直固定 135。
## 图层是 tools/river_art.py 画的，各层 scroll_scale 和脚本里的 SCROLL 一样。
## 会动的：Glints（月亮碎在水里的亮纹）、Ripples（整条河的淡水纹）用 scripts/river_water.gdshader 闪和晃；
## Mist 用 Parallax2D 的 autoscroll 慢慢漂；Water/Motes 是水面上的冷色光点；Glints/Fish 偶尔一条鱼跃出亮纹。
##
## 命令行（-- 后面）：
##   --x=300            开场镜头左边缘在 x=300（晨站在镜头里）
##   --walk=3           开场晨自动往右走 3 秒再停（负数往左走）
##   --shot=out.png     存一张图后退出：有 --walk 就在走完那一刻存，否则开场 20 帧后存
##   --shots=目录 --start=30 --every=3 --count=8
##                      连拍：从第 start 帧开始，每 every 帧存一张 目录/shot_000.png …，存够 count 张退出
##   --fish=1.5         开场 1.5 秒时让鱼跳一次（截图 / 录 GIF 用）
## 例：Godot --path . res://scenes/river_test.tscn --fixed-fps 30 -- --x=240 --shots=/tmp/r --start=10 --every=3 --count=40

const LOOK := 36.0          # 镜头往晨面朝的方向多看多少像素
const FOLLOW := 3.0         # 跟随的快慢（越大越紧）
const W := 960.0
const GROUND := 226.0

@onready var cam: Camera2D = $Camera
@onready var chen: Node2D = $Chen
@onready var fish: Node2D = $Glints/Fish

var _t := 0.0
var _frame := 0
var _shot := ""
var _walk := 0.0
var _walked := false
var _dir := ""
var _start := 30
var _every := 3
var _count := 8
var _saved := 0
var _fish_at := -1.0


## 主层地面（卵石线最上面一行），和 tools/river_art.py 的 ground_y 一样。x 可以一直涨，取 fposmod。
static func ground_y(x: float) -> float:
	x = fposmod(x, W)
	return GROUND + 1.5 * sin(TAU * x * 2.0 / W) + 1.0 * sin(TAU * x * 5.0 / W + 2.0)


func _ready() -> void:
	chen.ground_fn = ground_y
	chen.set_env("river")      # 月光从右上落到晨身上（河岸没有光柱）
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
		elif a.begins_with("--fish="):
			_fish_at = float(a.trim_prefix("--fish="))
	chen._snap()
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
	if _fish_at >= 0.0 and _t >= _fish_at:
		_fish_at = -1.0
		fish.jump_now()
	if _walk > 0.0 and _t >= _walk:
		_walk = 0.0
		chen.auto_dir = 0.0
		if _shot != "":
			_save(_shot)
			get_tree().quit()
	cam.position.x = lerpf(cam.position.x, _cam_target(), 1.0 - exp(-FOLLOW * delta))
	cam.position.y = 135.0
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
