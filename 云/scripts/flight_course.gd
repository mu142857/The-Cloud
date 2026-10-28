extends Node2D
## 一段航线：障碍和光点。都放在「世界坐标」里（x = 从起飞点算起的像素，主层速度），这个节点的 position.x = -已飞距离。
## 每个东西的位置都是世界时间 T 的纯函数（pos_at），机器人预测、撞判定、画面用同一套。
## 航线是手排的（按全程的比例摆），--seed 只改光点的一点点抖动和障碍晃动的相位。
##
## 障碍（少、慢、提前就能看见）：
##   rock  漂浮的岩块，上下慢慢浮，往左飘一点；撞判定 = 图上的不透明像素
##   storm 低垂的雷云，从屏幕顶上垂下来，逼你从下面飞；撞判定 = 图上的不透明像素
##   birds 一群迁徙的鸟（人字形），往左飞，比画面滚得快一点；撞判定 = 每只鸟一个小圆
## 光点：暖色，碰到补燃料。

const ROCK_TEX := {
	"a": preload("res://art/flight/rock_a.png"),
	"b": preload("res://art/flight/rock_b.png"),
	"c": preload("res://art/flight/rock_c.png"),
}
const STORM_TEX := preload("res://art/flight/storm.png")
const FLASH_TEX := preload("res://art/flight/storm_flash.png")
const BIRD_TEX := preload("res://art/flight/bird.png")
const MOTE_TEX := preload("res://art/flight/mote.png")
const MOTE_GLOW := preload("res://art/flight/glow_mote.png")

const MOTE_R := 12.0           # 碰到光点的距离（宽容）
const BIRD_R := 4.0

var length := 3840.0
var obstacles: Array = []      # Dictionary
var motes: Array = []          # Dictionary
var _masks := {}               # Texture2D -> Image
var _rng := RandomNumberGenerator.new()
var _add := CanvasItemMaterial.new()
var _t := 0.0
var glow_boost := 0.0          # 紧急模式：光点更亮更大（给的燃料也更多）


func build(total: float, seed_v: int) -> void:
	length = total
	_rng.seed = seed_v
	_add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	var D := total
	# ---- 障碍（f = 出现在全程的哪里，y = 中心高度）
	_rock("b", 0.22 * D, 128, 7.0, 5.5)
	_birds(0.31 * D, 92)
	_storm(0.385 * D)
	_rock("a", 0.50 * D, 64, 5.0, 6.0)
	_rock("c", 0.515 * D, 196, 5.0, 5.0)
	_birds(0.585 * D, 168)
	_rock("b", 0.655 * D, 206, 6.0, 6.5)
	_storm(0.73 * D)
	_rock("a", 0.84 * D, 118, 8.0, 5.0)
	# ---- 光点
	_wave(0.035 * D, 0.125 * D, 10, 175, 45, 1.0)            # 开场：一串波浪，教你按 / 松
	_arc(0.215 * D, 4, 80, -1)                                   # 岩块上面一道弧
	_line(0.225 * D, 0.24 * D, 2, 200)                           # 岩块下面两颗
	_line(0.30 * D, 0.335 * D, 5, 172)                           # 鸟群下面一排
	_wave(0.39 * D, 0.44 * D, 6, 168, 12, 2.0)                   # 雷云底下
	_line(0.495 * D, 0.525 * D, 4, 132)                          # 两块岩石中间的缝
	_arc(0.58 * D, 4, 82, -1)                                    # 鸟群上面
	_arc(0.65 * D, 3, 160, -1)                                   # 低岩块上面
	_wave(0.735 * D, 0.78 * D, 5, 182, 10, 1.5)                  # 第二片雷云底下
	_arc(0.835 * D, 4, 176, 1)                                   # 最后一块岩石下面
	_wave(0.89 * D, 0.975 * D, 8, 140, 28, 1.0)                  # 快到了：一串往水星去
	for f in [0.17, 0.27, 0.45, 0.62, 0.70, 0.88]:               # 贴着底飞的人也能捡到几个
		_mote(f * D, 228.0)


# ---------------------------------------------------------------- 摆东西

func _rock(kind: String, wx: float, cy: float, amp: float, period: float) -> void:
	var tex: Texture2D = ROCK_TEX[kind]
	var s := Sprite2D.new()
	s.texture = tex
	s.centered = false
	add_child(s)
	obstacles.append({"type": "rock", "wx0": wx, "vx": -5.0, "y0": cy - tex.get_height() * 0.5,
		"amp": amp, "period": period, "phase": _rng.randf() * TAU, "node": s, "tex": tex,
		"w": float(tex.get_width()), "h": float(tex.get_height())})


func _storm(wx: float) -> void:
	var s := Sprite2D.new()
	s.texture = STORM_TEX
	s.centered = false
	add_child(s)
	var fl := Sprite2D.new()
	fl.texture = FLASH_TEX
	fl.centered = false
	fl.material = _add
	fl.modulate = Color(1, 1, 1, 0)
	s.add_child(fl)
	obstacles.append({"type": "storm", "wx0": wx, "vx": 0.0, "y0": -4.0, "amp": 2.0, "period": 9.0,
		"phase": _rng.randf() * TAU, "node": s, "flash": fl, "tex": STORM_TEX, "next_flash": 0.0,
		"w": float(STORM_TEX.get_width()), "h": float(STORM_TEX.get_height())})


func _birds(wx: float, cy: float) -> void:
	var root := Node2D.new()
	add_child(root)
	var offs := []
	var n := 7
	for i in n:
		var k := i - n / 2
		var o := Vector2(absf(k) * 9.0, k * 6.0)     # 人字形：头鸟在最前（左）
		offs.append(o)
		var b := Sprite2D.new()
		b.texture = BIRD_TEX
		b.hframes = 4
		b.position = o
		root.add_child(b)
	# 鸟往左飞（比画面滚得快）：wx 是「鸟群经过飞船那一刻」的位置，倒推起点，保证出现的时机稳定
	obstacles.append({"type": "birds", "wx0": wx + 30.0 * (wx / 64.0), "vx": -30.0, "y0": cy, "amp": 5.0,
		"period": 4.0, "phase": _rng.randf() * TAU, "node": root, "offs": offs, "w": 60.0, "h": 40.0})


func _mote(wx: float, y: float) -> void:
	var g := Sprite2D.new()
	g.texture = MOTE_GLOW
	g.material = _add
	add_child(g)
	var s := Sprite2D.new()
	s.texture = MOTE_TEX
	g.add_child(s)
	motes.append({"wx": wx + _rng.randf_range(-3, 3), "y": y + _rng.randf_range(-3, 3), "taken": false,
		"phase": _rng.randf() * TAU, "node": g})


func _line(x0: float, x1: float, n: int, y: float) -> void:
	for i in n:
		_mote(lerpf(x0, x1, float(i) / maxf(1, n - 1)), y)


func _wave(x0: float, x1: float, n: int, y: float, amp: float, cycles: float) -> void:
	for i in n:
		var u := float(i) / maxf(1, n - 1)
		_mote(lerpf(x0, x1, u), y - amp * sin(u * TAU * cycles * 0.5))


func _arc(x: float, n: int, y: float, dir: int) -> void:
	for i in n:
		var u := float(i) / maxf(1, n - 1) - 0.5
		_mote(x + u * 18.0 * n, y + dir * (0.25 - u * u) * 40.0)


# ---------------------------------------------------------------- 位置（纯函数）

static func obs_pos(o: Dictionary, T: float) -> Vector2:
	return Vector2(o.wx0 + o.vx * T, o.y0 + o.amp * sin(TAU * T / o.period + o.phase))


static func mote_pos(m: Dictionary, T: float) -> Vector2:
	return Vector2(m.wx, m.y + 2.0 * sin(T * 2.2 + m.phase))


func _mask(tex: Texture2D) -> Image:
	if not _masks.has(tex):
		_masks[tex] = tex.get_image()
	return _masks[tex]


func hit_at(T: float, center: Vector2, pts: PackedVector2Array) -> int:
	## center：飞船的世界坐标。返回撞到的障碍下标，没撞 -1。
	for i in obstacles.size():
		var o: Dictionary = obstacles[i]
		var p := obs_pos(o, T)
		if center.x + 24 < p.x or center.x - 24 > p.x + o.w + 30 or center.y + 16 < p.y - 30 or center.y - 16 > p.y + o.h + 30:
			continue
		if o.type == "birds":
			for k in o.offs.size():
				var bp: Vector2 = p + o.offs[k] + Vector2(0, sin(T * 6.0 + k) * 1.5)
				for q in pts:
					if (center + q).distance_squared_to(bp) < BIRD_R * BIRD_R:
						return i
		else:
			var img := _mask(o.tex)
			for q in pts:
				var lp := center + q - p
				var ix := int(floor(lp.x))
				var iy := int(floor(lp.y))
				if ix >= 0 and iy >= 0 and ix < img.get_width() and iy < img.get_height():
					if img.get_pixel(ix, iy).a > 0.5:
						return i
	return -1


func motes_near(T: float, center: Vector2, r: float) -> Array:
	var out := []
	for i in motes.size():
		var m: Dictionary = motes[i]
		if m.taken:
			continue
		if absf(m.wx - center.x) > r:
			continue
		if mote_pos(m, T).distance_squared_to(center) < r * r:
			out.append(i)
	return out


# ---------------------------------------------------------------- 画面

func refresh(T: float, travel: float, real_dt: float, world_dt: float) -> void:
	position.x = -travel
	_t += real_dt
	for o in obstacles:
		var p := obs_pos(o, T)
		var n: Node2D = o.node
		var sx := p.x - travel
		n.visible = sx > -260 and sx < 520
		if not n.visible:
			continue
		n.position = p.round()
		if o.type == "birds":
			var k := 0
			for b in n.get_children():
				(b as Sprite2D).frame = int(T * 7.0 + k * 0.7) % 4
				b.position = (o.offs[k] + Vector2(0, sin(T * 6.0 + k) * 1.5)).round()
				k += 1
		elif o.type == "storm":
			o.next_flash -= world_dt
			var fl: Sprite2D = o.flash
			if o.next_flash <= 0.0:
				o.next_flash = _rng.randf_range(2.5, 5.0)
				fl.modulate.a = 0.55
			fl.modulate.a = maxf(0.0, fl.modulate.a - world_dt * 2.2)
	for m in motes:
		var g: Sprite2D = m.node
		if m.taken:
			continue
		var p := mote_pos(m, T)
		var sx := p.x - travel
		g.visible = sx > -20 and sx < 500
		if g.visible:
			g.position = p.round()
			var pulse: float = 0.75 + 0.25 * sin(_t * 3.0 + m.phase)
			g.modulate = Color(1, 1, 1, pulse)
			g.scale = Vector2.ONE * (2.0 if glow_boost > 0.5 else 1.0)
			(g.get_child(0) as Sprite2D).scale = Vector2.ONE * (0.5 if glow_boost > 0.5 else 1.0)


func take(i: int) -> void:
	motes[i].taken = true
	(motes[i].node as Node2D).visible = false
