extends Node2D
## 气泡：从河床上几个小泉眼（sources，这一层的坐标）一串一串慢慢往上冒；可选跟着一个节点（晨），
## 每隔几秒从她嘴边吐出两三个。气泡一边上升一边左右扭（整像素），越往上越快一点，到水面（surface_y）就没了。
## 小的 1 像素，大一点的 2×2（右上一格亮），再大的 3×3 空心圈。颜色是青银，明显暗于晨。
## 进了月光光柱会亮一点（和微粒一样问 underwater_shafts.gd）。
## 跟着晨的时候是「呼吸」（10-30 作者要的）：面罩前一口一口地呼出一串（BREATH_N 颗，BREATH_SPREAD 秒内陆续出来），
## 站着 BREATH_IDLE 秒一口、走着 BREATH_WALK 秒一口；呼出来的泡更亮一点（冷青白），先往前冲一点再上浮，
## 越往上越小（3×3 圈 → 2×2 → 1 像素）越淡，浮够 BREATH_LIFE 像素或到水面就没了。
## breathing = false（出水）就不再呼，已经冒出去的自己浮完。
## 开销：同时几十个 1×1 的 draw_rect，每帧重画。

@export var sources: Array[Vector2] = []
@export var follow: NodePath
@export var follow_offset := Vector2(5, -41)     # 晨嘴边（脚底为原点，朝右时；朝左 x 取反）：奥斯卡版站着约 52 像素高
@export var every := Vector2(0.5, 2.6)           # 泉眼每隔几秒冒一个
@export var follow_every := Vector2(3.5, 7.0)    # 晨每隔几秒吐一串
@export var surface_y := 18.0
@export var color := Color(0.6, 0.76, 0.86)
@export var seed := 9
@export var breathing := true

const BREATH_IDLE := Vector2(3.4, 4.2)      # 站着：隔几秒呼一口
const BREATH_WALK := Vector2(2.4, 3.0)      # 走着：快一点
const BREATH_N := Vector2i(3, 6)            # 一口几颗
const BREATH_SPREAD := 0.5                  # 一口在这么多秒里陆续出来
const BREATH_LIFE := Vector2(70.0, 120.0)   # 浮多高（像素）淡完
const BREATH_COLOR := Color(0.74, 0.89, 0.95)
const BREATH_A := 0.85
const MOUTH := Vector2(7, 4)                # 面罩出气口相对头中心（美术朝右；和 chen_idle_fx 一样）

var _rng := RandomNumberGenerator.new()
var _b: Array[Dictionary] = []
var _wait: Array[float] = []
var _fwait := 2.0
var _t := 0.0
var _shafts: Node = null
var _follow: Node2D = null
var _puff: Array[float] = []      # 这一口还没出来的泡：各自还要等几秒


func _ready() -> void:
	_rng.seed = seed
	for s in sources:
		_wait.append(_rng.randf_range(0.0, every.y))
	if not follow.is_empty():
		_follow = get_node(follow)
		_fwait = _rng.randf_range(1.0, 2.5)


func _spawn(p: Vector2, big: float) -> void:
	var r := _rng.randf()
	_b.append({
		"x": p.x, "y": p.y, "x0": p.x,
		"s": 3 if r < 0.06 * big else (2 if r < 0.3 * big else 1),
		"v": _rng.randf_range(9.0, 15.0), "ax": _rng.randf_range(0.6, 1.6),
		"f": _rng.randf_range(0.5, 1.1), "ph": _rng.randf() * TAU,
	})


## 外面叫的：在 p（这一层的坐标）吐 n 颗（晨在水底踩一步，chen.gd 调）
func emit(p: Vector2, n := 1, big := 0.8) -> void:
	for k in n:
		_spawn(p + Vector2(_rng.randi_range(-2, 2), k * 3), big)


func _process(delta: float) -> void:
	_t += delta
	if _shafts == null:
		_shafts = get_tree().get_first_node_in_group("underwater_shafts")
	for i in sources.size():
		_wait[i] -= delta
		if _wait[i] <= 0.0:
			_wait[i] = _rng.randf_range(every.x, every.y)
			var n := 1 if _rng.randf() < 0.7 else _rng.randi_range(2, 4)
			for k in n:
				_spawn(sources[i] + Vector2(_rng.randi_range(-1, 1), k * 4), 1.0)
	if _follow != null:
		_fwait -= delta
		if _fwait <= 0.0:
			var walking: bool = float(_follow.get("_vel") if _follow.get("_vel") != null else 0.0) > 1.0
			var ev := BREATH_WALK if walking else BREATH_IDLE
			_fwait = _rng.randf_range(ev.x, ev.y)
			if breathing:
				for k in _rng.randi_range(BREATH_N.x, BREATH_N.y):
					_puff.append(_rng.randf() * BREATH_SPREAD)
	if not _puff.is_empty():
		var left: Array[float] = []
		for w in _puff:
			w -= delta
			if w <= 0.0 and breathing:
				_breath_one()
			elif w > 0.0:
				left.append(w)
		_puff = left
	var keep: Array[Dictionary] = []
	for b in _b:
		b.v = minf(b.v + 2.0 * delta, 26.0)
		b.y -= b.v * delta
		if b.has("vx"):
			b.x0 += b.vx * delta
			b.vx *= exp(-3.0 * delta)
		b.x = b.x0 + sin(_t * b.f * TAU + b.ph) * b.ax
		if b.y > surface_y and (not b.has("life") or b.y0 - b.y < b.life):
			keep.append(b)
	_b = keep
	queue_redraw()


## 呼一颗：面罩前面，往朝向那边先冲一点
func _breath_one() -> void:
	var f: float = float(_follow.get("facing") if _follow.get("facing") != null else 1)
	var p: Vector2
	if _follow.has_method("_head_px") and _follow.has_method("_frame_to_local"):
		var hl: Vector2 = _follow.call("_frame_to_local", _follow.call("_head_px"))
		p = _follow.to_global(hl) + Vector2(MOUTH.x * f, MOUTH.y)
	else:
		p = _follow.global_position + Vector2(follow_offset.x * f, follow_offset.y)
	p = to_local(p)
	var r := _rng.randf()
	_b.append({
		"x": p.x, "y": p.y, "x0": p.x + _rng.randi_range(-1, 1), "y0": p.y,
		"s": 3 if r < 0.25 else (2 if r < 0.6 else 1),
		"v": _rng.randf_range(8.0, 13.0), "ax": _rng.randf_range(0.5, 1.4),
		"f": _rng.randf_range(0.6, 1.2), "ph": _rng.randf() * TAU,
		"vx": f * _rng.randf_range(5.0, 11.0), "life": _rng.randf_range(BREATH_LIFE.x, BREATH_LIFE.y), "br": true,
	})


func _draw() -> void:
	var xf := get_global_transform_with_canvas()
	for b in _b:
		var p := Vector2(b.x, b.y).round()
		var br: bool = b.has("br")
		var s := int(b.s)
		var a := BREATH_A if br else 0.55
		if br:
			var k: float = (b.y0 - b.y) / b.life                          # 浮了多少（0 → 1）
			s = mini(s, 3 if k < 0.25 else (2 if k < 0.55 else 1))  # 越往上越小
			a *= clampf(1.15 - k, 0.0, 1.0)                         # 越往上越淡
		if _shafts != null:
			var sp := xf * p
			sp.x = fposmod(sp.x + 240.0, 960.0) - 240.0
			a += 2.0 * _shafts.light_at(sp)
		a *= clampf((b.y - surface_y) / 30.0, 0.25, 1.0)        # 快到水面的淡一点
		var c := BREATH_COLOR if br else color
		c.a = minf(a, 0.9)
		var dim := c
		dim.a *= 0.45
		match s:
			1:
				draw_rect(Rect2(p, Vector2.ONE), c)
			2:
				draw_rect(Rect2(p, Vector2(2, 2)), dim)
				draw_rect(Rect2(p + Vector2(1, 0), Vector2.ONE), c)
			_:
				for o in [Vector2(1, 0), Vector2(0, 1), Vector2(2, 1), Vector2(1, 2)]:
					draw_rect(Rect2(p + o, Vector2.ONE), dim)
				draw_rect(Rect2(p + Vector2(2, 0), Vector2.ONE), c)
