extends Node2D
## 影子动物的测试场景：art/forest（C 版）背景 + forest_shadows.tscn，镜头慢慢往右走。
## ←/→ 手动走，空格停 / 走，F1 放一只（见 forest_shadows.gd）。
## 截图：Godot --path . --fixed-fps 60 res://scenes/forest_shadows_test.tscn -- --shadow=deer --shadow_x=200
##        --shots=目录 --start=30 --every=3 --count=8 [--x=镜头左边缘] [--still]
##   从第 start 帧开始，每 every 帧存一张 目录/shot_000.png …，存够 count 张退出。--still 镜头不动。

const AUTO_SPEED := 18.0
const WALK_SPEED := 70.0

@onready var cam: Camera2D = $Camera

var auto := true
var _dir := ""
var _start := 30
var _every := 3
var _count := 1
var _frame := 0
var _saved := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shots="):
			_dir = a.trim_prefix("--shots=")
		elif a.begins_with("--start="):
			_start = int(a.trim_prefix("--start="))
		elif a.begins_with("--every="):
			_every = int(a.trim_prefix("--every="))
		elif a.begins_with("--count="):
			_count = int(a.trim_prefix("--count="))
		elif a.begins_with("--x="):
			cam.position.x = 240.0 + float(a.trim_prefix("--x="))
		elif a == "--still":
			auto = false
		elif a == "--tree":   # 打印节点顺序后退出（看 Deep 层有没有搬到 Far 前面）
			(func(): await get_tree().process_frame; await get_tree().process_frame; print_tree_pretty(); get_tree().quit()).call()
	if _dir != "":
		DirAccess.make_dir_recursive_absolute(_dir)


func _process(delta: float) -> void:
	var dir := Input.get_axis("ui_left", "ui_right")
	if Input.is_action_just_pressed("ui_accept"):
		auto = not auto
	var speed := WALK_SPEED * (2.5 if Input.is_key_pressed(KEY_SHIFT) else 1.0)
	if dir != 0.0:
		cam.position.x += dir * speed * delta
	elif auto:
		cam.position.x += AUTO_SPEED * delta
	if _dir != "":
		_frame += 1
		if _frame >= _start and (_frame - _start) % _every == 0:
			var p := _dir.path_join("shot_%03d.png" % _saved)
			get_viewport().get_texture().get_image().save_png(p)
			_saved += 1
			if _saved >= _count:
				get_tree().quit()
