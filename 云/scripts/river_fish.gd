extends Node2D
## 偶尔一条鱼跃出水面：只在月亮碎在水里的那道亮纹里跳（屏幕坐标，挂在 scroll 0 的那层），
## 所以是一条黑剪影映在亮纹上（背上一两格被月光擦亮）；鱼身顺着抛物线转（出水头朝上、落水头朝下）。
## 出水时溅起一小簇水珠和一根往上冲的水柱，入水时溅得更高，水面上两圈慢慢散开的涟漪。
## 水花不能和亮纹一个颜色（会融进去）：刚溅起来的水珠是更冷更白的一档（L≈0.78，比亮纹最亮的 0.665 亮一截），
## 往上冲得快的拉成 1×2；落下来才褪成亮纹那档。破水那一下，水面上被砸开一个短短的暗口（亮纹在那儿断掉），
## 涟漪是一条亮的浪尖下面跟一条暗的浪谷——在亮纹上、在暗水上都看得出来。
## 每隔 every 秒（随机）跳一次；同一时间最多一条。开销：跳的那一秒每帧扫一个 17×17 的小格子 + 几十个 1×1 的
## draw_rect，其余时间什么都不画。jump_now() 让它马上跳一次（截图 / 录 GIF 用）。

@export var every := Vector2(7.0, 14.0)
@export var center_x := 338.0          # 亮纹的中线（屏幕 x），和 tools/river_art.py 的 MX 一样
@export var spread := 16.0             # 在中线左右多远以内跳
@export var water_y := Vector2(162.0, 176.0)
@export var fish_color := Color(0.04, 0.04, 0.085)    # 最暗处偏靛
@export var back_color := Color(0.42, 0.5, 0.55)    # 背上被月光擦亮的那一两格
@export var splash_color := Color(0.53, 0.62, 0.66)  # 落下来的水珠、浪尖（亮纹那一档）
@export var splash_hi := Color(0.66, 0.76, 0.83)     # 刚溅起来的水珠：冷白（L≈0.78）
@export var hole_color := Color(0.045, 0.06, 0.105)  # 破水口 / 浪谷：最暗的水
@export var seed := 5

const DUR := 1.05                      # 在空中多少秒
const RING := 2.0                      # 涟漪多少秒散完
const GRAV := 95.0
# 鱼头朝右（# = 身体，+ = 背上 / 鼻尖受光的一格，. = 空）。朝左就左右翻；画的时候按飞行方向转
const SHAPE := [
	"#.......+#....",
	"##...+#######.",
	".############+",
	"##...########.",
	"#.....##......",
]

var _rng := RandomNumberGenerator.new()
var _wait := 4.0
var _t := -1.0                         # 跳了多久（<0 = 没在跳）
var _p0 := Vector2.ZERO
var _dir := 1.0
var _len := 20.0
var _hgt := 18.0
var _drops: Array[Dictionary] = []
var _holes: Array[Dictionary] = []     # 破水口：{x, y, age, w}
const HOLE := 0.5                      # 破水口多少秒合上
const HI := 0.32                       # 水珠飞出去多少秒以内是冷白的


func _ready() -> void:
	_rng.seed = seed
	_wait = _rng.randf_range(2.0, 5.0)


func jump_now() -> void:
	_wait = 0.0


func _process(delta: float) -> void:
	if _t < 0.0:
		_wait -= delta
		if _wait <= 0.0:
			_start()
	else:
		var was := _t
		_t += delta
		if was < DUR and _t >= DUR:                    # 入水：溅得更高
			_splash(_p0 + Vector2(_dir * _len, 0).round(), 1.25)
		if _t > DUR + RING:
			_t = -1.0
			_wait = _rng.randf_range(every.x, every.y)
	for d in _drops:
		d.vy += GRAV * delta
		d.x += d.vx * delta
		d.y += d.vy * delta
		d.age += delta
	_drops = _drops.filter(func(d): return d.y < d.floor)
	for h in _holes:
		h.age += delta
	_holes = _holes.filter(func(h): return h.age < HOLE)
	queue_redraw()


func _start() -> void:
	_t = 0.0
	var y := _rng.randf_range(water_y.x, water_y.y)
	var near := (y - water_y.x) / (water_y.y - water_y.x)
	var off := _rng.randf_range(-spread, spread) * (0.5 + near)
	_p0 = Vector2(center_x + off, y).round()
	_dir = -1.0 if off > 0.0 else 1.0                  # 朝亮纹中线跳：整条弧都映在亮纹上
	_len = lerpf(18.0, 26.0, near)
	_hgt = lerpf(15.0, 22.0, near)
	_splash(_p0, 1.0)


func _splash(p: Vector2, k: float) -> void:
	for i in 8:                                        # 一簇往两边散的水珠
		_drops.append({"x": p.x + _rng.randf_range(-2.0, 2.0), "y": p.y - 1.0, "age": _rng.randf_range(0.0, 0.1),
			"vx": _rng.randf_range(-18.0, 18.0), "vy": _rng.randf_range(-46.0, -20.0) * k, "floor": p.y})
	for i in 3:                                        # 中间一根往上冲的水柱（几颗几乎竖直的）
		_drops.append({"x": p.x + _rng.randf_range(-0.5, 0.5), "y": p.y - 1.0 - i, "age": 0.0,
			"vx": _rng.randf_range(-2.0, 2.0), "vy": (-54.0 + i * 9.0) * k, "floor": p.y})
	_holes.append({"x": p.x, "y": p.y, "age": 0.0, "w": 4.0 if k > 1.0 else 3.0})


func _draw() -> void:
	if _t >= 0.0 and _t <= DUR:
		var k := _t / DUR
		var pos := _p0 + Vector2(_dir * _len * k, -4.0 * _hgt * k * (1.0 - k))
		# 飞行方向（抛物线的切线），鱼身顺着它转
		var v := Vector2(_dir * _len, -4.0 * _hgt * (1.0 - 2.0 * k))
		var ang := atan2(v.y, v.x) if _dir > 0.0 else atan2(v.y, v.x) - PI
		var ca := cos(-ang)
		var sa := sin(-ang)
		var rows := SHAPE.size()
		var cols: int = SHAPE[0].length()
		for ty in range(-8, 9):
			for tx in range(-8, 9):
				var sx := ca * tx - sa * ty
				var sy := sa * tx + ca * ty
				var c := int(round(sx + cols / 2.0 - 0.5))
				var r := int(round(sy + rows / 2.0 - 0.5))
				if r < 0 or r >= rows or c < 0 or c >= cols:
					continue
				var cc: int = c if _dir > 0.0 else cols - 1 - c
				var ch: String = SHAPE[r][cc]
				if ch == ".":
					continue
				var q := (pos + Vector2(tx, ty - 2)).round()
				if q.y < _p0.y:                        # 只画水面以上的部分
					draw_rect(Rect2(q, Vector2.ONE), back_color if ch == "+" else fish_color)
	# 破水口：水面被砸开一道短短的暗口（亮纹在这儿断掉），越来越窄、合上
	for h in _holes:
		var a: float = h.age / HOLE
		var hw := roundf(h.w * (1.0 - a * a))
		if hw >= 1.0:
			draw_rect(Rect2(Vector2(h.x - hw, h.y - 1.0).round(), Vector2(hw * 2.0 + 1.0, 2)), hole_color)
		if hw >= 2.0:
			draw_rect(Rect2(Vector2(h.x - hw + 1.0, h.y + 1.0).round(), Vector2(hw * 2.0 - 1.0, 1)), hole_color)
	# 溅起的水珠：刚飞出去冷白（往上冲得快的拉成 1×2），落下来褪成亮纹那档
	for d in _drops:
		var c := splash_hi if d.age < HI else splash_color
		var tall := 2.0 if (d.vy < -30.0 and d.age < HI) else 1.0
		draw_rect(Rect2(Vector2(d.x, d.y).round(), Vector2(1, tall)), c)
	# 涟漪：出水点和入水点各一圈，往左右散开的几小段，越散越暗
	if _t >= 0.0:
		for i in 2:
			var t0 := 0.0 if i == 0 else DUR
			var a := (_t - t0) / RING
			if a < 0.0 or a > 1.0:
				continue
			var c0 := _p0 + Vector2(_dir * _len * i, 0)
			var r := 2.0 + a * (16.0 if i == 1 else 11.0)
			var col := splash_color
			col.a = 0.85 * (1.0 - a)
			var dk := hole_color
			dk.a = 0.9 * (1.0 - a)
			for s in [-1.0, 1.0]:
				draw_rect(Rect2((c0 + Vector2(s * r - (2.0 if s < 0 else 0.0), 0)).round(), Vector2(3, 1)), dk)
				draw_rect(Rect2((c0 + Vector2(s * r - (2.0 if s < 0 else 0.0), 1)).round(), Vector2(3, 1)), col)
				if r > 5.0:
					draw_rect(Rect2((c0 + Vector2(s * r * 0.6 - (1.0 if s < 0 else 0.0), 2)).round(), Vector2(2, 1)), col)
				if r > 10.0:
					draw_rect(Rect2((c0 + Vector2(s * r * 0.3, 3)).round(), Vector2(1, 1)), col)
