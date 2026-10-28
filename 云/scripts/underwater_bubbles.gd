extends Node2D
## 气泡：从河床上几个小泉眼（sources，这一层的坐标）一串一串慢慢往上冒；可选跟着一个节点（晨），
## 每隔几秒从她嘴边吐出两三个。气泡一边上升一边左右扭（整像素），越往上越快一点，到水面（surface_y）就没了。
## 小的 1 像素，大一点的 2×2（右上一格亮），再大的 3×3 空心圈。颜色是青银，明显暗于晨。
## 进了月光光柱会亮一点（和微粒一样问 underwater_shafts.gd）。
## 开销：同时几十个 1×1 的 draw_rect，每帧重画。

@export var sources: Array[Vector2] = []
@export var follow: NodePath
@export var follow_offset := Vector2(5, -41)     # 晨嘴边（脚底为原点，朝右时；朝左 x 取反）：奥斯卡版站着约 52 像素高
@export var every := Vector2(0.5, 2.6)           # 泉眼每隔几秒冒一个
@export var follow_every := Vector2(3.5, 7.0)    # 晨每隔几秒吐一串
@export var surface_y := 18.0
@export var color := Color(0.6, 0.76, 0.86)
@export var seed := 9

var _rng := RandomNumberGenerator.new()
var _b: Array[Dictionary] = []
var _wait: Array[float] = []
var _fwait := 2.0
var _t := 0.0
var _shafts: Node = null
var _follow: Node2D = null


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
			_fwait = _rng.randf_range(follow_every.x, follow_every.y)
			var f: float = _follow.get("facing") if _follow.get("facing") != null else 1.0
			var p := _follow.position + Vector2(follow_offset.x * f, follow_offset.y)
			for k in _rng.randi_range(2, 3):
				_spawn(p + Vector2(0, k * 3), 1.3)
	var keep: Array[Dictionary] = []
	for b in _b:
		b.v = minf(b.v + 2.0 * delta, 26.0)
		b.y -= b.v * delta
		b.x = b.x0 + sin(_t * b.f * TAU + b.ph) * b.ax
		if b.y > surface_y:
			keep.append(b)
	_b = keep
	queue_redraw()


func _draw() -> void:
	var xf := get_global_transform_with_canvas()
	for b in _b:
		var p := Vector2(b.x, b.y).round()
		var a := 0.55
		if _shafts != null:
			var sp := xf * p
			sp.x = fposmod(sp.x + 240.0, 960.0) - 240.0
			a += 2.0 * _shafts.light_at(sp)
		a *= clampf((b.y - surface_y) / 30.0, 0.25, 1.0)        # 快到水面的淡一点
		var c := color
		c.a = minf(a, 0.9)
		var dim := c
		dim.a *= 0.45
		match int(b.s):
			1:
				draw_rect(Rect2(p, Vector2.ONE), c)
			2:
				draw_rect(Rect2(p, Vector2(2, 2)), dim)
				draw_rect(Rect2(p + Vector2(1, 0), Vector2.ONE), c)
			_:
				for o in [Vector2(1, 0), Vector2(0, 1), Vector2(2, 1), Vector2(1, 2)]:
					draw_rect(Rect2(p + o, Vector2.ONE), dim)
				draw_rect(Rect2(p + Vector2(2, 0), Vector2.ONE), c)
