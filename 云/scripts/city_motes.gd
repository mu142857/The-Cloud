extends Node2D
## 空气里慢慢飘的灰和锈屑：很少几颗，1 像素，往右下慢慢飘、轻轻晃，各自隐约亮一阵、暗一阵。
## 放在 Main（Parallax2D）下面，坐标是主层的，area 宽 960 和图层一样，左右绕回。
## 颜色是暗的赭灰，最亮的时候 alpha 也只到一半多：只是让空气「有东西」，不抢晨。
## 开销：count 个 1×1 的 draw_rect，每帧重画。

@export var count := 26
@export var area := Rect2(0, 40, 960, 180)
@export var color := Color(0.5, 0.43, 0.35)
@export var seed := 17

var _m: Array[Dictionary] = []
var _t := 0.0


func _ready() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	for i in count:
		_m.append({
			"x": rng.randf_range(area.position.x, area.end.x),
			"y": rng.randf_range(area.position.y, area.end.y),
			"vx": rng.randf_range(1.0, 3.5), "vy": rng.randf_range(0.6, 1.8),
			"ax": rng.randf_range(1.0, 3.0), "fx": rng.randf_range(0.1, 0.25), "px": rng.randf() * TAU,
			"bf": rng.randf_range(0.05, 0.15), "bp": rng.randf() * TAU,
			"peak": rng.randf_range(0.25, 0.6),
		})


func _process(delta: float) -> void:
	_t += delta
	for m in _m:
		m.x = fposmod(m.x + m.vx * delta - area.position.x, area.size.x) + area.position.x
		m.y = fposmod(m.y + m.vy * delta - area.position.y, area.size.y) + area.position.y
	queue_redraw()


func _draw() -> void:
	for m in _m:
		var b := clampf(sin(_t * m.bf * TAU + m.bp) * 1.4 - 0.2, 0.0, 1.0)
		if b <= 0.0:
			continue
		var p := Vector2(m.x + sin(_t * m.fx * TAU + m.px) * m.ax, m.y).round()
		var c := color
		c.a = b * m.peak
		draw_rect(Rect2(p, Vector2.ONE), c)
