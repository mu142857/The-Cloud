extends Node2D
## 针叶林视差小样：镜头自己慢慢往右走，←/→ 手动走（按住 Shift 快一点），空格停 / 走。
## 图层是 tools/forest_art.py 画的，各层 scroll_scale 和脚本里的 SCROLL 一样。
## 截图：Godot --path . -- --shot=out.png --x=300（镜头左边缘在 x=300，等几帧后存图退出）

const AUTO_SPEED := 18.0
const WALK_SPEED := 70.0

@onready var cam: Camera2D = $Camera
@onready var shafts: Array[Node] = $Main/Shafts.get_children()

var auto := true
var _t := 0.0
var _shot := ""
var _shot_frames := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			_shot = a.trim_prefix("--shot=")
			auto = false
		elif a.begins_with("--x="):
			cam.position.x = 240.0 + float(a.trim_prefix("--x="))


func _process(delta: float) -> void:
	_t += delta
	var dir := Input.get_axis("ui_left", "ui_right")
	if Input.is_action_just_pressed("ui_accept"):
		auto = not auto
	var speed := WALK_SPEED * (2.5 if Input.is_key_pressed(KEY_SHIFT) else 1.0)
	if dir != 0.0:
		cam.position.x += dir * speed * delta
	elif auto:
		cam.position.x += AUTO_SPEED * delta
	# 光柱慢慢呼吸，几根错开
	for i in shafts.size():
		var s := shafts[i] as CanvasItem
		s.modulate.a = 0.75 + 0.25 * sin(_t * 0.6 + i * 1.9)
	if _shot != "":
		_shot_frames += 1
		if _shot_frames == 20:
			get_viewport().get_texture().get_image().save_png(_shot)
			get_tree().quit()
