extends Node2D
## 楼边上的冷色航空障碍灯：一颗颗很小的冷青色灯（1~2 像素），全城同一个很慢的节拍：
## 亮两三秒、灭两三秒，一起亮一起灭 —— 机械、冷、不停，但不急，不像警报。比晨暗得多（L≈0.55）。
## points 是 tools/city_art.py 记下来的位置（每栋楼背光那条边上几颗，只在楼腰以上）。
## 放在某一层 Parallax2D 下面（坐标是那一层的），repeat 会帮它左右重复。
## 开销：每帧最多几十个 1×1 / 2×2 的 draw_rect（只在亮灭切换时重画）。

@export var points := PackedVector2Array()
@export var dot := 2
@export var period := 5.0          # 一拍几秒
@export var on_time := 2.6         # 每拍亮多久
@export var sweep := 0.0           # 从这一层最左到最右，相位一共错开多少拍（0 = 全部一起亮灭）
@export var color := Color(0.34, 0.5, 0.55)
@export var seed := 1

var _t := 0.0
var _skip: PackedByteArray = PackedByteArray()
var _was := -1


func _ready() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	_skip.resize(points.size())
	for i in points.size():
		_skip[i] = 1 if rng.randf() < 0.25 else 0    # 有几颗是坏的，不亮


func _process(delta: float) -> void:
	_t += delta
	if sweep != 0.0:
		queue_redraw()
		return
	var now := 1 if fposmod(_t, period) < on_time else 0
	if now != _was:
		_was = now
		queue_redraw()


func _draw() -> void:
	for i in points.size():
		if _skip[i]:
			continue
		var p := points[i]
		var ph := fposmod(_t / period - p.x / 960.0 * sweep, 1.0)
		if ph * period < on_time:
			draw_rect(Rect2(p.round(), Vector2(dot, dot)), color)
