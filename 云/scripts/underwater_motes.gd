extends Node2D
## 水里悬浮的微粒（海雪）：很多颗 1 像素的小点，跟着水流往左慢慢漂、一点点往下沉、上下左右轻轻晃。
## 平时很暗（几乎看不见），飘进月光光柱里就被照亮——光柱的「体积」主要靠它们看出来。
## 放在某个 Parallax2D 里（坐标是那一层的），area 宽 960 和图层一样，左右绕回；上下也绕回。
## 加法混合（场景里给它 blend_mode = Add 的 CanvasItemMaterial），亮度靠 alpha 调。
## 开销：count 个 1×1 的 draw_rect + 每颗一次 light_at（6 道光柱的小循环），每帧重画。

@export var count := 60
@export var area := Rect2(0, 24, 960, 180)
@export var color := Color(0.62, 0.8, 0.95)
@export var base_alpha := Vector2(0.03, 0.09)     # 不在光里时的亮度范围
@export var lit_gain := 3.2                       # 在光里时亮多少（乘光柱亮度）
@export var drift := Vector2(-2.2, 0.9)           # 平均漂移（像素 / 秒）：往左、往下
@export var seed := 21

var _m: Array[Dictionary] = []
var _t := 0.0
var _shafts: Node = null


func _ready() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	for i in count:
		_m.append({
			"x": rng.randf_range(area.position.x, area.end.x),
			"y": rng.randf_range(area.position.y, area.end.y),
			"vx": drift.x * rng.randf_range(0.4, 1.4), "vy": drift.y * rng.randf_range(0.2, 1.5),
			"ax": rng.randf_range(1.0, 3.0), "fx": rng.randf_range(0.05, 0.15), "px": rng.randf() * TAU,
			"ay": rng.randf_range(1.0, 2.5), "fy": rng.randf_range(0.08, 0.2), "py": rng.randf() * TAU,
			"a": rng.randf_range(base_alpha.x, base_alpha.y),
		})


func _process(delta: float) -> void:
	_t += delta
	if _shafts == null:
		_shafts = get_tree().get_first_node_in_group("underwater_shafts")
	for m in _m:
		m.x = fposmod(m.x + m.vx * delta - area.position.x, area.size.x) + area.position.x
		m.y = fposmod(m.y + m.vy * delta - area.position.y, area.size.y) + area.position.y
	queue_redraw()


func _draw() -> void:
	var xf := get_global_transform_with_canvas()
	for m in _m:
		var p := Vector2(m.x + sin(_t * m.fx * TAU + m.px) * m.ax, m.y + sin(_t * m.fy * TAU + m.py) * m.ay).round()
		var a: float = m.a
		if _shafts != null:
			# Parallax2D 的 repeat 把同一个 canvas item 每隔 960 再画一遍：把屏幕 x 折回看得见的那一份
			var sp := xf * p
			sp.x = fposmod(sp.x + 240.0, 960.0) - 240.0
			a += lit_gain * _shafts.light_at(sp)
		if a < 0.02:
			continue
		var c := color
		c.a = minf(a, 0.75)
		draw_rect(Rect2(p, Vector2.ONE), c)
