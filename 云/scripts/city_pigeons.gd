extends Node2D
## 城里的鸽子：一群淡灰白的鸽子在楼与楼之间慢慢盘旋，是城里唯一不赶路的东西（对应水底的鲸、森林的萤火虫）。
## - 群集（boids）：每只鸽子看身边的邻居 —— 和它们对齐方向、往它们中间靠、离太近就让开 —— 再被一个看不见的
##   「领头点」（沿一条慢慢变形的 8 字绕圈）往前带。所以是密的一整群、有一个整体的轮廓，像一张膜：
##   领头点一转弯，整群一起转过去。
## - 明暗跟着整群的方向走：往右（迎着光）飞的露出亮的背，往左飞的是暗的一面，竖着飞的是中间一档 ——
##   整群转向时一大片一起亮起来、又一起暗下去。翅膀几帧扇动（上、平、下、平），偶尔一起滑翔。
## - perch = true：这群平时歇在一条楼前的高架轨道梁上（perch_y 是梁的上沿），train 指的那列车开过来时被惊起，
##   整群翻飞，在「镜头现在看着的地方」的楼缝间绕圈（跟着镜头走，晨一直往右走也看得到），
##   等车过去再落回当前画面里看得见的那段梁上。
## 硬边：每只鸽子是几个整像素的 draw_rect（帧图写在下面），位置取整，不半透明。颜色最亮 L≈0.57，比晨（≈0.80）暗。
## 放在某一层 Parallax2D 下面（坐标是那一层的），repeat 会帮它左右重复。y 不低于 y_max：不进晨身后那条。
## 开销：每群几十只，邻居是两两比一遍（N² 次距离），几十只没问题。

@export var count := 24
## 0 = 远处（3 像素宽）、1 = 中远（5 像素）、2 = 中景（7 像素）、3 = 近（9 像素）
@export var size := 2
@export var center := Vector2(400, 100)
@export var radius := Vector2(140, 28)
@export var orbit_speed := 0.22          # 领头点绕圈的角速度（弧度 / 秒）
@export var y_min := 14.0
@export var y_max := 168.0
@export var light := Color(0.47, 0.47, 0.49)
@export var dark := Color(0.3, 0.305, 0.32)
@export var perch := false
@export var perch_y := 61.0
@export var train: NodePath
@export var seed := 1

# 帧图：# = 一个像素。依次是翅膀往上、平、往下（飞），最后一个是歇着
const FR := {
	0: [["#.#", ".#."], ["###"], [".#.", "#.#"], ["##"]],
	1: [["#...#", ".#.#.", "..#.."], ["##.##", "..#.."], ["..#..", ".#.#.", "#...#"], [".#.", "###"]],
	2: [["#.....#", ".#...#.", "..###..", "...#..."], ["##.#.##", "..###..", "...#..."],
		["..###..", ".#.#.#.", "#.....#"], [".##.", "####", ".#.."]],
	3: [["#.......#", ".#.....#.", "..#.#.#..", "...###...", "....#...."],
		["###.#.###", "...###...", "....#...."],
		["...###...", "..#.#.#..", ".#.....#.", "#.......#"], [".##..", "####.", ".####", "..#.."]],
}
# 每种大小的群：分离距离、邻居距离、最快、最慢（像素 / 秒，这一层的坐标）
const SCALE := {0: [3.2, 10.0, 26.0, 12.0], 1: [5.0, 15.0, 38.0, 18.0], 2: [7.0, 20.0, 55.0, 26.0],
	3: [9.0, 25.0, 66.0, 30.0]}

var _b: Array[Dictionary] = []
var _t := 0.0
var _rng := RandomNumberGenerator.new()
var _state := "fly"          # perch 群：sit / flee / land
var _state_t := 0.0
var _px := 0.0               # 歇着的位置（梁上的 x，这一层「不绕回」的坐标）
var _train: Node = null
var _init := false


func _ready() -> void:
	_rng.seed = seed
	if not train.is_empty():
		_train = get_node_or_null(train)
	for i in count:
		var a := _rng.randf() * TAU
		var r := sqrt(_rng.randf()) * 12.0
		_b.append({"p": center + Vector2(cos(a) * r * 1.6, sin(a) * r * 0.6), "v": Vector2(20, 0).rotated(_rng.randf_range(-0.3, 0.3)),
			"ph": _rng.randf() * 4.0, "fq": _rng.randf_range(7.0, 9.0), "seat": Vector2(i * 4 - count * 2, 0),
			"peck": _rng.randf() * 5.0})
	if not perch:
		for k in 300:      # 先跑一段，开场时已经是成形的一群
			_step(1.0 / 30.0)


## 镜头现在看着这一层的哪一段：返回「不绕回」的左边缘（这一层的坐标）
func _view_left() -> float:
	var cam := get_viewport().get_camera_2d()
	var par := get_parent() as Parallax2D
	if cam == null or par == null:
		return 0.0
	return (cam.position.x - 240.0) * par.scroll_scale.x


func _leader(t: float) -> Vector2:
	var a := t * orbit_speed
	var c := center
	if perch:
		c = Vector2(_view_left() + 280.0, perch_y + 30.0)    # 惊起的那群：在镜头看着的楼缝间绕
	var r := radius * (1.0 + 0.25 * sin(t * 0.13))
	return c + Vector2(cos(a) * r.x, sin(a * 2.0) * r.y)


func _train_near() -> bool:
	if _train == null or not _train._run:
		return false
	var head: float = _train._x
	var tail: float = head - _train.dir * _train._len()
	var lo := minf(head, tail) - 420.0
	var hi := maxf(head, tail) + 420.0
	var x0 := fposmod(_px, 960.0) - count * 2.0
	var x1 := x0 + count * 4.0
	for s in [-960.0, 0.0, 960.0]:
		if x1 + s > lo and x0 + s < hi:
			return true
	return false


func _sit_all() -> void:
	for b in _b:
		b.p = Vector2(_px, perch_y) + b.seat
		b.v = Vector2.ZERO


func _step(delta: float) -> void:
	_t += delta
	_state_t += delta
	if perch:
		if not _init:
			_init = true
			_state = "sit"
			_px = _view_left() + 300.0
			_sit_all()
		if _state == "sit" and _train_near():
			_state = "flee"
			_state_t = 0.0
			for b in _b:      # 一下子全飞起来：往上、往前散开
				b.v = Vector2(_rng.randf_range(-20, 60), _rng.randf_range(-60, -30))
		elif _state == "flee" and _state_t > 5.5 and not _train_near():
			_state = "land"
			_state_t = 0.0
			_px = _view_left() + _rng.randf_range(250.0, 360.0)   # 落回当前画面里看得见的那段梁
		elif _state == "land":
			var all_in := true
			for b in _b:
				if b.p.distance_to(Vector2(_px, perch_y) + b.seat) > 1.5:
					all_in = false
			if all_in or _state_t > 8.0:
				_state = "sit"
				_sit_all()
	if _state == "sit":
		for b in _b:
			b.peck += delta
		return
	var sc: Array = SCALE[clampi(size, 0, 3)]
	var sep_r: float = sc[0]
	var nb_r: float = sc[1]
	var vmax: float = sc[2]
	var vmin: float = sc[3]
	var lead := _leader(_t)
	var n := _b.size()
	for i in n:
		var b: Dictionary = _b[i]
		var al := Vector2.ZERO
		var co := Vector2.ZERO
		var se := Vector2.ZERO
		var k := 0
		for j in n:
			if i == j:
				continue
			var o: Dictionary = _b[j]
			var dv: Vector2 = o.p - b.p
			var dist := dv.length()
			if dist < nb_r:
				al += o.v
				co += o.p
				k += 1
				if dist < sep_r and dist > 0.01:
					se -= dv / dist * (sep_r - dist)
		var acc := Vector2.ZERO
		if _state == "land":
			var tgt: Vector2 = Vector2(_px, perch_y) + b.seat
			acc = (tgt - b.p) * 2.2 - b.v * 1.6
			b.v += acc * delta
			b.p += b.v * delta
		else:
			if k > 0:
				acc += (al / k - b.v) * 1.6           # 对齐
				acc += (co / k - b.p) * 1.1           # 聚合
			acc += se * 9.0                           # 分离
			var to_lead: Vector2 = lead - b.p
			acc += to_lead.limit_length(60.0) * 0.9  # 跟着领头点
			b.v += acc * delta
			var sp: float = b.v.length()
			if sp > vmax:
				b.v *= vmax / sp
			elif sp < vmin and sp > 0.01:
				b.v *= vmin / sp
			b.p += b.v * delta
		if b.p.y > y_max:
			b.p.y = y_max
			b.v.y = minf(b.v.y, 0.0)
		if b.p.y < y_min and _state != "land":
			b.v.y = absf(b.v.y)
		b.ph += delta * b.fq


func _process(delta: float) -> void:
	_step(delta)
	queue_redraw()


func _draw() -> void:
	var fr: Array = FR[clampi(size, 0, 3)]
	var mid_c := light.lerp(dark, 0.5)
	# 「不绕回」的坐标画出来要减掉整圈，好落在 Parallax2D 重复的那几份里
	var shift: float = floor(_view_left() / 960.0) * 960.0 if perch else 0.0
	var gliding := sin(_t * 0.45) > 0.6           # 整群偶尔一起滑翔
	for b in _b:
		var g: Array
		var col := light
		if _state == "sit":
			g = fr[3]
			col = dark if int(b.peck * 0.7) % 4 == 0 else mid_c
		else:
			var f: int = 1 if gliding else [0, 1, 2, 1][int(b.ph) % 4]
			g = fr[f]
			var v: Vector2 = b.v
			if absf(v.y) > absf(v.x) * 0.9:
				col = mid_c
			else:
				col = light if v.x >= 0.0 else dark
		var w: int = g[0].length()
		var o: Vector2 = (b.p - Vector2(shift + w / 2, g.size() - 1)).round()
		for y in g.size():
			var row: String = g[y]
			var x := 0
			while x < row.length():
				if row[x] == "#":
					var x0 := x
					while x < row.length() and row[x] == "#":
						x += 1
					draw_rect(Rect2(o.x + x0, o.y + y, x - x0, 1), col)
				else:
					x += 1
