extends Node2D
## 细细的冷灰雨：斜着落（往右下），每滴是一串整像素（硬边、不透明），按深度分几层：
## 远的短、慢、颜色贴近霾；近的长、快；前景偶尔几滴更大的。splash = true 的那层落到街面上溅起一个小水花。
## 晨身后那条（y_dim 以下）雨换成更暗的颜色：雨还在下，但那一条不被雨丝刷亮。
## 放在某一层 Parallax2D 下面（坐标是那一层的），area 宽 960 和图层一样，左右绕回。
## 开销：每滴拆成几段竖着的 draw_rect（同一列的像素合成一段），每层几百段。

@export var count := 120
@export var length := 5
@export var speed := 220.0
@export var slant := 0.2               # 每往下 1 像素往右多少
@export var color := Color(0.33, 0.34, 0.36)
@export var color_dim := Color(0.17, 0.175, 0.19)
@export var y_dim := 183.0
@export var area := Rect2(0, -10, 960, 240)
## 落地：每滴在 [ground.x, ground.y] 之间随机找一行停下（街面越往下越近）；splash = 停下的地方溅一个小水花
@export var ground := Vector2(228, 228)
@export var splash := false
@export var splash_color := Color(0.28, 0.29, 0.31)
@export var seed := 1
## 路灯的光锥（这一层的坐标）：每个 Vector4(灯头中心 x, 光锥上沿 y, 上沿半宽, 下沿半宽)，下沿在 light_bottom。
## 落进光锥里的雨丝换成 color_lit（雨在灯下才看得见），越往下越淡回原色。
@export var lights := PackedVector4Array()
@export var light_bottom := 228.0
@export var color_lit := Color(0.55, 0.6, 0.63)
## 只画光锥里的雨丝（灯下那一阵密雨；光锥外面的雨由别的 Rain 节点画）
@export var only_lit := false

var _d: Array[Dictionary] = []
var _s: Array[Dictionary] = []
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.seed = seed
	for i in count:
		_d.append(_new_drop(_rng.randf_range(area.position.y, ground.y)))


func _new_drop(y: float) -> Dictionary:
	return {"x": _rng.randf_range(area.position.x, area.end.x), "y": y,
		"end": _rng.randf_range(ground.x, ground.y), "v": speed * _rng.randf_range(0.85, 1.15)}


func _process(delta: float) -> void:
	for d in _d:
		d.y += d.v * delta
		d.x += d.v * slant * delta
		if d.y >= d.end:
			if splash:
				_s.append({"x": roundf(fposmod(d.x, area.size.x)), "y": roundf(d.end), "t": 0.0})
			var nd := _new_drop(area.position.y - _rng.randf_range(0.0, 30.0))
			d.x = nd.x
			d.y = nd.y
			d.end = nd.end
			d.v = nd.v
		d.x = fposmod(d.x - area.position.x, area.size.x) + area.position.x
	var keep: Array[Dictionary] = []
	for s in _s:
		s.t += delta
		if s.t < 0.16:
			keep.append(s)
	_s = keep
	queue_redraw()


func _lit(x: float, y: float) -> float:
	## 这一点在不在某道光锥里：在的话返回 0..1（上面 1，往下淡到 0.35），分三档（硬边，不渐变）
	for l in lights:
		if y < l.y or y > light_bottom:
			continue
		var t := (y - l.y) / maxf(1.0, light_bottom - l.y)
		var half := lerpf(l.z, l.w, t)
		var dx := absf(fposmod(x - l.x + area.size.x * 0.5, area.size.x) - area.size.x * 0.5)
		if dx <= half:
			return 1.0 if t < 0.35 else (0.7 if t < 0.7 else 0.4)
	return 0.0


func _draw() -> void:
	for d in _d:
		var hx := roundf(d.x)
		var hy := roundf(d.y)
		# 从雨滴头往上数 length 个像素，同一列的合成一段
		var k := 0
		while k < length:
			var px := roundf(d.x - slant * k)
			var k0 := k
			while k < length and roundf(d.x - slant * k) == px:
				k += 1
			var y1 := hy - k0
			var y0 := hy - k + 1
			var c := color_dim if y1 >= y_dim else color
			var lit := _lit(px, y1)
			if lit > 0.0:
				c = c.lerp(color_lit, lit)
			elif only_lit:
				continue
			draw_rect(Rect2(px, y0, 1, y1 - y0 + 1), c)
	for s in _s:
		# 小水花：先是一个点，再炸成左右两点
		if s.t < 0.06:
			draw_rect(Rect2(s.x, s.y - 1, 1, 1), splash_color)
		else:
			draw_rect(Rect2(s.x - 1, s.y - 1, 1, 1), splash_color)
			draw_rect(Rect2(s.x + 1, s.y - 1, 1, 1), splash_color)
