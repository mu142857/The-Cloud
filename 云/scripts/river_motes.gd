extends Node2D
## 河面上的冷色光点（河流星球的「萤火虫」）：很少几颗，1 像素，贴着水面慢慢漂、慢慢亮灭。
## 比萤火虫更冷、更稀、更暗——这里亮的应该是月亮碎在水里的那道光，光点只是陪衬。
## 放在 Parallax2D 里（坐标是那一层的），area 宽 960 和图层一样，左右绕回。
## 用加法混合（场景里给它一个 blend_mode = Add 的 CanvasItemMaterial），所以亮度靠 alpha 调。
## 开销：count 个 1×1 的 draw_rect，每帧重画。

@export var count := 12
@export var area := Rect2(0, 132, 960, 70)
@export var color := Color(0.5, 0.7, 0.8)          # 亮的东西往青银走（和亮纹一致）
@export var seed := 11

var _m: Array[Dictionary] = []
var _t := 0.0


func _ready() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	for i in count:
		_m.append({
			"x": rng.randf_range(area.position.x, area.end.x),
			"y": rng.randf_range(area.position.y, area.end.y),
			"vx": rng.randf_range(-3.0, -0.8),              # 跟着水往左慢慢漂
			"ay": rng.randf_range(1.0, 3.0), "fy": rng.randf_range(0.1, 0.25), "py": rng.randf() * TAU,
			"bf": rng.randf_range(0.12, 0.3), "bp": rng.randf() * TAU,
			"peak": rng.randf_range(0.35, 0.7),
		})


func _process(delta: float) -> void:
	_t += delta
	for m in _m:
		m.x = fposmod(m.x + m.vx * delta - area.position.x, area.size.x) + area.position.x
	queue_redraw()


func _draw() -> void:
	for m in _m:
		var b := clampf(sin(_t * m.bf * TAU + m.bp) * 1.6 - 0.6, 0.0, 1.0)
		if b <= 0.0:
			continue
		var p := Vector2(m.x, m.y + sin(_t * m.fy * TAU + m.py) * m.ay).round()
		var c := color
		c.a = b * m.peak
		draw_rect(Rect2(p, Vector2.ONE), c)
		if b > 0.8 and m.peak > 0.55:                       # 最亮的那一下，水里有一个更暗的倒影点
			c.a *= 0.35
			draw_rect(Rect2(p + Vector2(0, 3), Vector2.ONE), c)
