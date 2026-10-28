extends Node2D
## 萤火虫：每只绕着自己的落脚点慢慢画小圈、上下飘，整体再往一边漂；各闪各的，亮一会儿、灭一会儿。
## 放在主层（Parallax2D）里，坐标是主层的，area 宽 960 和图层一样，左右绕回。
## 位置取整到像素，免得一只萤火虫被画在两个像素之间糊掉。

@export var count := 26
@export var area := Rect2(0, 104, 960, 92)
@export var color := Color(1.0, 0.86, 0.32)
@export var texture: Texture2D = preload("res://art/fx/firefly.png")
@export var seed := 7

var _flies: Array[Dictionary] = []
var _t := 0.0


func _ready() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	for i in count:
		_flies.append({
			"x": rng.randf_range(area.position.x, area.end.x),
			"y": rng.randf_range(area.position.y, area.end.y),
			"vx": rng.randf_range(-2.0, 2.0),               # 整体漂移，像素 / 秒
			"ax": rng.randf_range(4.0, 10.0), "fx": rng.randf_range(0.15, 0.35), "px": rng.randf() * TAU,
			"ay": rng.randf_range(3.0, 7.0), "fy": rng.randf_range(0.2, 0.45), "py": rng.randf() * TAU,
			"bf": rng.randf_range(0.25, 0.5), "bp": rng.randf() * TAU,   # 闪的快慢、相位
			"peak": rng.randf_range(0.55, 0.95),
		})


func _process(delta: float) -> void:
	_t += delta
	for f in _flies:
		f.x = fposmod(f.x + f.vx * delta - area.position.x, area.size.x) + area.position.x
	queue_redraw()


func _draw() -> void:
	var half := texture.get_size() / 2.0
	for f in _flies:
		# 亮的时间大约占四成，亮灭之间是平滑的
		var b := clampf(sin(_t * f.bf * TAU + f.bp) * 1.8 - 0.8, 0.0, 1.0)
		if b <= 0.0:
			continue
		var p := Vector2(f.x + sin(_t * f.fx * TAU + f.px) * f.ax, f.y + sin(_t * f.fy * TAU + f.py) * f.ay)
		var c := color
		c.a = b * f.peak
		draw_texture(texture, (p - half).round(), c)
