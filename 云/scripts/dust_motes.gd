extends Node2D
## 光带里慢慢飘的灰尘（10-31 楼梯间拱窗下的竖直月光）：几粒一像素的点，在 rect（房间坐标 [x, y, 宽, 高]）里很慢地往下飘、
## 左右轻轻晃；越往下越暗（跟着光带由亮到暗），飘到底从顶上重新出现。room.json 的 scripts 里用（params 原样 set 进来）。
## 位置每 100ms 挪一次（整像素，和动画一个节奏），硬边、不半透明。

var rect: Array = [0, 0, 32, 100]
var count := 6
var seed := 1
var speed := 1.6                          # 往下飘几像素 / 秒
var color := Color(0.74, 0.8, 0.92)       # 光带上面（最亮）
var color_low := Color(0.2, 0.25, 0.36)   # 光带底下（快看不见了）

var _p: Array[Vector2] = []
var _ph: Array[float] = []
var _t := 0.0
var _tick := 0.0
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.seed = int(seed)
	for i in int(count):
		_p.append(Vector2(_rng.randf_range(0.0, float(rect[2])), _rng.randf_range(0.0, float(rect[3]))))
		_ph.append(_rng.randf_range(0.0, TAU))


func _process(delta: float) -> void:
	_t += delta
	_tick += delta
	if _tick < 0.1:
		return
	_tick = fmod(_tick, 0.1)
	var h := float(rect[3])
	for i in _p.size():
		var v := _p[i]
		v.y += speed * (0.7 + 0.3 * sin(_ph[i])) * 0.1
		if v.y > h:
			v = Vector2(_rng.randf_range(0.0, float(rect[2])), 0.0)
		_p[i] = v
	queue_redraw()


func _draw() -> void:
	var h := float(rect[3])
	for i in _p.size():
		var x := roundf(float(rect[0]) + _p[i].x + 1.5 * sin(_t * 0.35 + _ph[i]))
		var y := roundf(float(rect[1]) + _p[i].y)
		draw_rect(Rect2(x, y, 1, 1), color.lerp(color_low, clampf(_p[i].y / h, 0.0, 1.0)))
