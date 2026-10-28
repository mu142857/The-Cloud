extends Node2D
## 晨和地面的接触（chen.gd 自己建两个：back 在精灵后面，front 在精灵前面）。坐标是世界坐标（top_level），粒子落下就留在原地。
##   back：脚底的接触阴影（硬边、压暗地面一档）+ 积水涟漪（一圈像素椭圆，往外扩、变淡）
##   front：踩出来的尘土 / 落叶 / 水花 / 沙 / 云丝，城市里雨打在肩上溅开
## 每颗粒子是 1×1 或 2×1 的硬边像素（位置取整），颜色比晨暗得多、半透明、很快消失：不能把晨身后那一条刷亮。
## 用法（chen.gd 调）：step(pos, facing, kind) 一步落地；scuff(pos, facing, kind) 起步 / 停下蹭一下；shoulder(pos) 肩上溅雨。
## kind = 场景名（forest / river / underwater / cloud / city）；没有的场景什么都不出。
## 开销：同时最多 MAX 颗，每颗一次 draw_rect。

const MAX := 90

## 各场景的颜色（都明显暗于晨：晨斗篷 L≈0.18、白发 L≈0.88；这些粒子 L 0.2~0.4，再乘 alpha）
const DUST := Color(0.34, 0.35, 0.29, 0.8)           # 森林：深苔褐的土
const LEAF := [Color(0.22, 0.34, 0.27, 0.9), Color(0.3, 0.38, 0.24, 0.9)]   # 森林：暗绿 / 暗黄绿的落叶
const SPLASH_RIVER := Color(0.48, 0.58, 0.7, 0.8)   # 河岸浅水：冷蓝灰
const SAND := Color(0.3, 0.36, 0.38, 0.75)          # 水底：青灰的沙
const WISP := Color(0.58, 0.5, 0.68, 0.6)            # 云星：淡紫的云丝
const SPLASH_CITY := Color(0.42, 0.44, 0.48, 0.8)    # 城市积水：冷灰
const RIPPLE := Color(0.4, 0.42, 0.46, 0.55)
const SHOULDER := Color(0.58, 0.6, 0.65, 0.85)     # 肩上溅开的雨，稍亮一点（在她身上才看得见）
const SHADOW := Color(0.0, 0.0, 0.0, 0.32)          # 接触阴影：压暗一档

var chen: Node2D                  # chen.gd 设
var back := false                 # true = 精灵后面那层（阴影、涟漪）
var shadow_on := true             # chen.gd 每帧设：被甩出飞船、转着的时候关掉
var shadow_w := 9                 # 阴影半宽（chen.gd 按帧给：腾空帧窄一点）
var shadow_x := 0.0               # 阴影中心相对晨锚点的偏移（世界坐标 x）
var under: Node2D                 # front 的涟漪画到 back 那层（精灵后面）
var tick: Callable                # front 那个每帧先调它（chen.gd 的 _env_update：光、光晕、阴影、肩上的雨）

var _p: Array[Dictionary] = []
var _rings: Array[Dictionary] = []
var _rng := RandomNumberGenerator.new()
var _leaf_wait := 0


func _ready() -> void:
	top_level = true
	_rng.seed = 2026 + (1 if back else 0)
	_leaf_wait = _rng.randi_range(3, 6)


func _add(pos: Vector2, vel: Vector2, life: float, c: Color, grav := 0.0, drag := 0.0, size := Vector2.ONE, sway := 0.0) -> void:
	if _p.size() >= MAX:
		_p.pop_front()
	_p.append({"pos": pos, "vel": vel, "age": 0.0, "life": life, "c": c, "grav": grav, "drag": drag,
		"size": size, "sway": sway, "ph": _rng.randf() * TAU, "y0": pos.y})


func _ring_layer() -> Node2D:
	return under if under != null else self


## 一步落地：pos = 着地那只脚的脚底（世界坐标），facing = 晨的朝向
func step(pos: Vector2, facing: int, kind: String, strength := 1.0) -> void:
	var back_dir := -float(facing)        # 土往脚后跟方向多飞一点
	match kind:
		"forest":
			var n := int(round(2 + 1.5 * strength))
			for i in n:
				_add(pos + Vector2(_rng.randi_range(-2, 2), -1), Vector2(_rng.randf_range(-10, 10) + back_dir * 16.0, _rng.randf_range(-24, -8)),
					_rng.randf_range(0.35, 0.6), DUST, 80.0, 2.0, Vector2(2, 1) if i == 0 else Vector2.ONE)
			_leaf_wait -= 1
			if _leaf_wait <= 0 and strength >= 1.0:
				_leaf_wait = _rng.randi_range(5, 9)
				var c: Color = LEAF[_rng.randi() % LEAF.size()]
				_add(pos + Vector2(back_dir * 3.0, -2), Vector2(back_dir * _rng.randf_range(6, 12), _rng.randf_range(-26, -18)),
					_rng.randf_range(1.0, 1.4), c, 34.0, 2.2, Vector2(2, 1), 1.5)
		"river":
			for i in int(round(2 + strength)):
				_add(pos + Vector2(back_dir * 2.0 + _rng.randi_range(-2, 2), -1), Vector2(_rng.randf_range(-24, 24) + back_dir * 8.0, _rng.randf_range(-38, -20)),
					_rng.randf_range(0.3, 0.45), SPLASH_RIVER, 150.0, 0.5)
			_ring_layer()._rings.append({"pos": pos.round(), "age": 0.0, "life": 0.45, "w": 7.0, "c": SPLASH_RIVER * Color(1, 1, 1, 0.55)})
		"underwater":
			# 水里的沙：慢慢扬起一小团，悬一会儿再落
			for i in int(round(3 + strength)):
				_add(pos + Vector2(_rng.randi_range(-3, 3), -1), Vector2(_rng.randf_range(-10, 10) + back_dir * 6.0, _rng.randf_range(-14, -4)),
					_rng.randf_range(0.8, 1.3), SAND, 6.0, 2.2, Vector2(2, 1) if i == 0 else Vector2.ONE)
		"cloud":
			# 脚下拨开一小缕云：两小段淡紫往两边滑开、变淡
			for s in [-1.0, 1.0]:
				var l := _rng.randi_range(3, 5)
				_add(pos + Vector2(s * 2.0, _rng.randi_range(-2, 0)), Vector2(s * _rng.randf_range(10, 16), _rng.randf_range(-2, 0)),
					_rng.randf_range(0.45, 0.7), WISP, 0.0, 2.5, Vector2(l, 1))
		"city":
			for i in int(round(3 + strength)):
				_add(pos + Vector2(back_dir * 2.0 + _rng.randi_range(-2, 2), -1), Vector2(_rng.randf_range(-30, 30) + back_dir * 10.0, _rng.randf_range(-46, -28)),
					_rng.randf_range(0.3, 0.45), SPLASH_CITY, 190.0, 0.5, Vector2(1, 2) if i == 0 else Vector2.ONE)
			_ring_layer()._rings.append({"pos": pos.round() + Vector2(0, 1), "age": 0.0, "life": 0.6, "w": 9.0, "c": RIPPLE})


## 起步 / 停下：脚边蹭一下（比 step 小）
func scuff(pos: Vector2, facing: int, kind: String) -> void:
	step(pos, facing, kind, 0.0)


## 城市：雨打在肩上，溅开两三颗
func shoulder(pos: Vector2) -> void:
	for i in _rng.randi_range(2, 3):
		_add(pos + Vector2(_rng.randi_range(-1, 1), 0), Vector2(_rng.randf_range(-20, 20), _rng.randf_range(-22, -10)),
			_rng.randf_range(0.14, 0.24), SHOULDER, 160.0, 0.0)


func _process(delta: float) -> void:
	if tick.is_valid():
		tick.call(delta)
	var i := 0
	while i < _p.size():
		var p := _p[i]
		p.age += delta
		if p.age >= p.life:
			_p.remove_at(i)
			continue
		var v: Vector2 = p.vel
		v.y += p.grav * delta
		v *= exp(-p.drag * delta)
		p.vel = v
		p.pos += v * delta
		if p.grav > 0.0 and v.y > 0.0 and p.pos.y > p.y0 + 1.0:
			_p.remove_at(i)          # 落回地面就没了（不往地面里掉）
			continue
		i += 1
	i = 0
	while i < _rings.size():
		_rings[i].age += delta
		if _rings[i].age >= _rings[i].life:
			_rings.remove_at(i)
			continue
		i += 1
	queue_redraw()


func _draw() -> void:
	if back:
		_draw_shadow()
		for r in _rings:
			_draw_ring(r)
		return
	for p in _p:
		var k: float = p.age / p.life
		var c: Color = p.c
		c.a *= 1.0 - k * k
		var pos: Vector2 = p.pos
		if p.sway > 0.0:
			pos.x += sin(p.age * 7.0 + p.ph) * p.sway
		draw_rect(Rect2(pos.round(), p.size), c)


func _draw_shadow() -> void:
	if not shadow_on or chen == null or not chen.visible:
		return
	# 三行像素硬边，只压在地面上（脚底那行 = 地面最上面一行，往下两行越来越窄、越来越淡），不碰脚上面的空气
	var o := (chen.position + Vector2(shadow_x, -1)).round()
	var w := shadow_w
	draw_rect(Rect2(o.x - w, o.y, 2 * w + 1, 1), SHADOW)
	draw_rect(Rect2(o.x - w + 2, o.y + 1, 2 * w - 3, 1), SHADOW * Color(1, 1, 1, 0.75))
	draw_rect(Rect2(o.x - w + 5, o.y + 2, 2 * w - 9, 1), SHADOW * Color(1, 1, 1, 0.45))


func _draw_ring(r: Dictionary) -> void:
	# 扁椭圆的一圈：半宽从 2 涨到 w，高是宽的 1/4，越来越淡
	var k: float = r.age / r.life
	var hw := lerpf(2.0, r.w, sqrt(k))
	var hh := maxf(1.0, round(hw * 0.25))
	var c: Color = r.c
	c.a *= 1.0 - k
	var o: Vector2 = r.pos
	var seen := {}
	var n := int(hw * 4.0) + 8
	for j in n:
		var a := TAU * j / n
		var q := (o + Vector2(cos(a) * hw, sin(a) * hh)).round()
		if not seen.has(q):
			seen[q] = true
			draw_rect(Rect2(q, Vector2.ONE), c)
