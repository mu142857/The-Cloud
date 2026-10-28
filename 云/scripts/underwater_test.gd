extends Node2D
## 水星 · 水底小样：晨（scenes/chen.tscn）在河床上走，←/→ 或 A/D 走（按住 Shift 快一点），
## ↓ / S 转过来正面站着，空格让晨自己一直往右走（展示模式）/ 停下。
## 镜头水平跟着晨（有一点平滑，往她面朝的方向多看 LOOK 像素），竖直固定 135。
## 图层是 tools/underwater_art.py 画的，各层 scroll_scale 和脚本里的 SCROLL 一样。
## 会动的：Surface（水面里碎掉的月亮，underwater_surface.gdshader 闪、晃）；Shafts（月光光柱，underwater_shafts.gd/.gdshader）；
## Kelp / BedWeeds / HeadWeeds / Front（水草按行摆，underwater_sway.gdshader）；Main/Caustics（河床上的焦散）；
## Kelp/Motes、Main/Motes（海雪，飘进光柱会亮）；Main/Bubbles、ChenBubbles（气泡）；Far/Whale（远处游过的大家伙）；
## Head/Glow、Main/Glow（发光的果荚，全画面唯一的暖色）。
##
## 命令行（-- 后面）：
##   --x=300            开场镜头左边缘在 x=300（晨站在镜头里）
##   --walk=3           开场晨自动往右走 3 秒再停（负数往左走）
##   --shot=out.png     存一张图后退出：有 --walk 就在走完那一刻存，否则开场 --wait 秒后存
##   --wait=2.5         没有 --walk 时等几秒再存（让光柱、气泡、微粒先动起来），默认 2.5
##   --shots=目录 --start=30 --every=3 --count=8
##                      连拍：从第 start 帧开始，每 every 帧存一张 目录/shot_000.png …，存够 count 张退出
## 例：Godot --path . res://scenes/underwater_test.tscn -- --x=0 --shots=/tmp/u --start=30 --every=2 --count=60
## 注意：shader 里的 TIME 走的是真实时间，--fixed-fps 下存图比实时快，水草 / 水面 / 焦散会几乎不动；
## 录 GIF 不要加 --fixed-fps，用每张打印的 t 算帧间隔。

const LOOK := 36.0
const FOLLOW := 3.0
const W := 960.0
const GROUND := 226.0

@onready var cam: Camera2D = $Camera
@onready var chen: Node2D = $Chen

var _t := 0.0
var _frame := 0
var _shot := ""
var _wait := 2.5
var _walk := 0.0
var _walked := false
var _dir := ""
var _start := 30
var _every := 3
var _count := 8
var _saved := 0


## 河床地面（细沙线最上面一行），和 tools/underwater_art.py 的 ground_y 一样。x 可以一直涨，取 fposmod。
static func ground_y(x: float) -> float:
	x = fposmod(x, W)
	return GROUND + 1.5 * sin(TAU * x * 2.0 / W + 0.5) + 1.0 * sin(TAU * x * 5.0 / W + 1.3)


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
			_wait = float(a.trim_prefix("--wait="))
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
	if _shot != "" and not _walked and _t >= _wait:
		_shot_once()
	if _dir != "" and _frame >= _start and (_frame - _start) % _every == 0:
		_save(_dir.path_join("shot_%03d.png" % _saved))
		print("shot %d t=%.3f" % [_saved, _t])     # 录 GIF 时用来算每帧的真实间隔
		_saved += 1
		if _saved >= _count:
			get_tree().quit()


func _shot_once() -> void:
	_save(_shot)
	_shot = ""
	get_tree().quit()


func _save(path: String) -> void:
	# 窗口被别的窗口挡住时 Godot 会跳过绘制（存下来的是同一张）：存之前强制画一遍
	RenderingServer.force_draw(false)
	get_viewport().get_texture().get_image().save_png(path)
