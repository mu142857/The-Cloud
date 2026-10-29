extends Node2D
## 便宜的像素烟 / 尘土 / 火星：每颗是一个硬边的小圆（art/level1/puffs.png，半径 1~7），位置取整到像素、不旋转，
## 所以和背景一样是一格一格的像素，不会出现斜着的 mixel。颜色和透明度随寿命变（特效允许半透明）。
##
##   burst(pos, n, preset)          一次喷 n 颗（撞地的尘土、烟团）
##   add_source(key, pos, rate, preset)   持续冒（坠毁飞船的烟柱）；set_source_pos / remove_source
## preset 是一个字典（见 PRESETS），可以临时覆盖几项：burst(p, 20, PRESETS.dust.merged({"life": Vector2(1, 2)}))。
## 一共最多 MAX 颗，超了就丢最老的。
## 可选两项：floor = 落到这个 y 就停住（土块落地）；hold = 前多少比例的寿命不变淡（土块在空中一直是实的，落地以后才淡）。
## 烟和尘土的颜色压得比较暗（2026-10-28）：烟最亮的时候 L 也明显低于晨，不抢主角。

const TEX := preload("res://art/level1/puffs.png")
const MAX := 420

const PRESETS := {
	# 烟：慢慢往上、被风往右吹一点、越来越大越来越淡
	"smoke": {"vx": Vector2(-6, 6), "vy": Vector2(-16, -9), "wind": 5.0, "grav": 0.0, "drag": 0.4,
		"r0": Vector2(1, 3), "r1": Vector2(4, 7), "life": Vector2(2.6, 4.2),
		"c0": Color(0.3, 0.33, 0.32, 0.75), "c1": Color(0.16, 0.2, 0.19, 0.0), "spread": Vector2(3, 2)},
	# 撞地时的大烟团
	"smoke_burst": {"vx": Vector2(-40, 40), "vy": Vector2(-34, -8), "wind": 4.0, "grav": 0.0, "drag": 1.4,
		"r0": Vector2(3, 5), "r1": Vector2(5, 7), "life": Vector2(1.6, 3.2),
		"c0": Color(0.32, 0.34, 0.32, 0.75), "c1": Color(0.14, 0.17, 0.16, 0.0), "spread": Vector2(10, 4)},
	# 尘土：往两边飞、有重力、很快落下
	"dust": {"vx": Vector2(-90, 90), "vy": Vector2(-55, -12), "wind": 0.0, "grav": 140.0, "drag": 1.8,
		"r0": Vector2(1, 2), "r1": Vector2(1, 3), "life": Vector2(0.5, 1.1),
		"c0": Color(0.3, 0.28, 0.23, 0.9), "c1": Color(0.2, 0.2, 0.17, 0.0), "spread": Vector2(12, 1)},
	# 小尘土（晨落地、爬起来）
	"dust_small": {"vx": Vector2(-28, 28), "vy": Vector2(-16, -4), "wind": 0.0, "grav": 60.0, "drag": 2.0,
		"r0": Vector2(1, 2), "r1": Vector2(1, 2), "life": Vector2(0.35, 0.7),
		"c0": Color(0.38, 0.36, 0.3, 0.85), "c1": Color(0.2, 0.2, 0.17, 0.0), "spread": Vector2(8, 1)},
	# 飞船拖的烟
	"trail": {"vx": Vector2(-5, 5), "vy": Vector2(-8, -2), "wind": 3.0, "grav": 0.0, "drag": 0.6,
		"r0": Vector2(1, 2), "r1": Vector2(3, 5), "life": Vector2(0.9, 1.6),
		"c0": Color(0.3, 0.32, 0.31, 0.7), "c1": Color(0.15, 0.18, 0.17, 0.0), "spread": Vector2(2, 2)},
	# 火星 / 余烬：一像素，暖色，往上飘一点就灭
	"ember": {"vx": Vector2(-6, 6), "vy": Vector2(-22, -8), "wind": 3.0, "grav": 0.0, "drag": 0.3,
		"r0": Vector2(1, 1), "r1": Vector2(1, 1), "life": Vector2(0.6, 1.4),
		"c0": Color(0.98, 0.72, 0.36, 0.95), "c1": Color(0.85, 0.35, 0.15, 0.0), "spread": Vector2(4, 2), "px": true},
	# 土块（飞船起飞时从机头、船腹掉下来）：一像素，重重地往下掉，落地停住（burst 时 merged 一个 floor），最后才淡
	"clod": {"vx": Vector2(-10, 10), "vy": Vector2(-12, 6), "wind": 0.0, "grav": 420.0, "drag": 0.2,
		"r0": Vector2(1, 1), "r1": Vector2(1, 1), "life": Vector2(1.3, 2.1), "hold": 0.6,
		"c0": Color(0.23, 0.22, 0.18, 1.0), "c1": Color(0.17, 0.17, 0.14, 0.0), "spread": Vector2(1, 1), "px": true},
	# 发光木头上的小光点（更慢、更淡）
	"glint": {"vx": Vector2(-2, 2), "vy": Vector2(-9, -4), "wind": 0.0, "grav": 0.0, "drag": 0.2,
		"r0": Vector2(1, 1), "r1": Vector2(1, 1), "life": Vector2(1.0, 1.8),
		"c0": Color(1.0, 0.82, 0.48, 0.9), "c1": Color(1.0, 0.6, 0.3, 0.0), "spread": Vector2(6, 1), "px": true},
}

var _p: Array[Dictionary] = []
var _src := {}
var _rng := RandomNumberGenerator.new()
var density := 1.0          # lite 档 0.5：持续冒的少一半


func _ready() -> void:
	_rng.seed = 4242


func _rv(v: Vector2) -> float:
	return _rng.randf_range(v.x, v.y)


func burst(pos: Vector2, n: int, preset: Dictionary) -> void:
	for i in n:
		_spawn(pos, preset)


func _spawn(pos: Vector2, pr: Dictionary) -> void:
	if _p.size() >= MAX:
		_p.pop_front()
	var sp: Vector2 = pr.get("spread", Vector2.ZERO)
	_p.append({
		"pos": pos + Vector2(_rng.randf_range(-sp.x, sp.x), _rng.randf_range(-sp.y, sp.y)),
		"vel": Vector2(_rv(pr.vx), _rv(pr.vy)),
		"age": 0.0, "life": _rv(pr.life),
		"r0": _rv(pr.r0), "r1": _rv(pr.r1),
		"pr": pr,
	})


func add_source(key: String, pos: Vector2, rate: float, preset: Dictionary) -> void:
	_src[key] = {"pos": pos, "rate": rate, "pr": preset, "acc": 0.0}


func set_source_pos(key: String, pos: Vector2) -> void:
	if _src.has(key):
		_src[key].pos = pos


func remove_source(key: String) -> void:
	_src.erase(key)


func clear() -> void:
	_p.clear()
	_src.clear()


func _process(delta: float) -> void:
	for k in _src:
		var s: Dictionary = _src[k]
		s.acc += s.rate * density * delta
		while s.acc >= 1.0:
			s.acc -= 1.0
			_spawn(s.pos, s.pr)
	var i := 0
	while i < _p.size():
		var p := _p[i]
		p.age += delta
		if p.age >= p.life:
			_p.remove_at(i)
			continue
		var pr: Dictionary = p.pr
		var v: Vector2 = p.vel
		v.y += pr.grav * delta
		v.x += pr.wind * delta
		v *= exp(-pr.drag * delta)
		p.vel = v
		p.pos += v * delta
		if pr.has("floor") and p.pos.y >= float(pr.floor):
			p.pos.y = float(pr.floor)
			p.vel = Vector2.ZERO
		i += 1
	queue_redraw()


func _draw() -> void:
	for p in _p:
		var pr: Dictionary = p.pr
		var k: float = p.age / p.life
		if pr.has("hold"):
			k = maxf(0.0, (k - float(pr.hold)) / (1.0 - float(pr.hold)))
		var c: Color = (pr.c0 as Color).lerp(pr.c1, k)
		var pos: Vector2 = (p.pos as Vector2).round()
		if pr.get("px", false):
			draw_rect(Rect2(pos, Vector2.ONE), c)
			continue
		var r := clampi(int(round(lerpf(p.r0, p.r1, sqrt(k)))), 1, 7)
		draw_texture_rect_region(TEX, Rect2(pos - Vector2(8, 8), Vector2(16, 16)), Rect2(16 * (r - 1), 0, 16, 16), c)
