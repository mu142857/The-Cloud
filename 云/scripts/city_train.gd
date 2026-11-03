extends Node2D
## 高架列车：隔十来秒一列匀速开过去（日常的、准点的，没人抬头看），过完轨道空一阵，再来下一列。
## 车身是暗灰的长条，一节节车厢之间一道缝，车窗是一排冷白的小格（比晨暗得多），底下一道最暗的转向架。
## 硬边：全是整像素的 draw_rect，位置取整。放在某一层 Parallax2D 下面（坐标是那一层的），repeat 会帮它左右重复。
## 参数写在场景里（tools/city_art.py 的 TRAINS）。开销：每帧几十个 draw_rect。

@export var rail_y := 106.0          # 轨道梁的上沿（车轮踩在它上面一行）
@export var cars := 8
@export var car_len := 34
@export var car_h := 9
@export var speed := 500.0
@export var interval := Vector2(5.0, 9.0)
@export var dir := 1
@export var far := false             # 远处那列：颜色往霾里褪，车窗只是一道细线
@export var area_w := 960.0
@export var seed := 9
## 开场等几秒才来第一列
@export var first_wait := 2.0

const NEAR := {"body": Color(0.15, 0.155, 0.165), "top": Color(0.27, 0.28, 0.29), "win": Color(0.46, 0.52, 0.56),
	"gap": Color(0.07, 0.075, 0.08)}
const FAR := {"body": Color(0.3, 0.305, 0.31), "top": Color(0.4, 0.405, 0.41), "win": Color(0.5, 0.53, 0.55),
	"gap": Color(0.22, 0.225, 0.23)}

var _x := 0.0
var _wait := 0.0
var _run := false
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.seed = seed
	_run = false
	_wait = first_wait


func _len() -> float:
	return cars * (car_len + 2.0)


## 屏幕左右两边在这一层里的 x（本地坐标）。这一层是 Parallax2D repeat（每 960 重复一份），
## 以前车从本地 x=-10 出发、开过 area_w 就收：重复的那一份正好在屏幕中间，整列车会凭空出现、凭空消失。
## 现在从屏幕外一点出发、整列开出屏幕外才收；重复的几份离得比屏幕宽 + 车长还远，看不见。
func _view_x() -> Vector2:
	var inv := get_global_transform_with_canvas().affine_inverse()
	var w := get_viewport_rect().size.x
	var a := (inv * Vector2(0.0, 0.0)).x
	var b := (inv * Vector2(w, 0.0)).x
	return Vector2(minf(a, b), maxf(a, b))


func _start() -> void:
	_run = true
	var v := _view_x()
	_x = v.x - 10.0 if dir > 0 else v.y + 10.0


func _process(delta: float) -> void:
	if _run:
		_x += dir * speed * delta
		var v := _view_x()
		if (dir > 0 and _x - _len() > v.y + 10.0) or (dir < 0 and _x + _len() < v.x - 10.0):
			_run = false
			_wait = _rng.randf_range(interval.x, interval.y)
	else:
		_wait -= delta
		if _wait <= 0.0:
			_start()
	queue_redraw()


func _draw() -> void:
	if not _run:
		return
	var c: Dictionary = FAR if far else NEAR
	var y0 := rail_y - car_h
	var head := roundf(_x)
	for i in cars:
		# 车头在 _x，车厢往后排
		var a := head - dir * i * (car_len + 2.0)
		var x0 := a - car_len if dir > 0 else a
		draw_rect(Rect2(x0, y0, car_len, car_h), c.body)
		draw_rect(Rect2(x0, y0, car_len, 1), c.top)
		draw_rect(Rect2(x0, rail_y - 1, car_len, 1), c.gap)
		if far:
			draw_rect(Rect2(x0 + 1, y0 + 2, car_len - 2, 1), c.win)
		else:
			var ws := 3.0 if car_h < 12 else 5.0      # 中景那列近，车窗大一点
			var wy := y0 + 2.0
			var x := x0 + 3.0
			while x + ws <= x0 + car_len - 2.0:
				draw_rect(Rect2(x, wy, ws, ws), c.win)
				x += ws + 2.0
		# 车厢之间的缝
		var gx := x0 - 2.0 if dir > 0 else x0 + car_len
		draw_rect(Rect2(gx, y0 + 2, 2, car_h - 3), c.gap)
