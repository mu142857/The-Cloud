extends Node2D
## 云层的星星：几十颗各闪各的小星 + 一颗特别亮、慢慢呼吸的星（结局的伏笔）+ 偶尔一颗流星往余晖那边划下去。
## 放在 Sky（Parallax2D，scroll 0）下面，坐标就是屏幕坐标；后面的云柱、薄云、石针会挡住它们。
## 颜色只用 COLORS 里那几档，不用半透明：像素还是硬边的。重画限到 ~20 次 / 秒，一次几十个 draw_rect，很便宜。

const COLORS := [
	Color8(0x3a, 0x33, 0x52), Color8(0x5a, 0x50, 0x78), Color8(0x8a, 0x7f, 0xae), Color8(0xbf, 0xb4, 0xdc),
]
const HOME_STAR := Vector2i(318, 34)          # 那颗特别亮的星（和 tools/cloud_art.py 的 STAR_XY 一样）
const HOME_CORE := Color8(0xd0, 0xc6, 0xe8)
const REDRAW := 0.05

@export var count := 46
@export var area := Rect2(0, 3, 480, 110)
@export var seed := 11
## 流星：隔多少秒一颗（随机），第一颗在 first_meteor 秒
@export var meteor_every := Vector2(7.0, 16.0)
@export var first_meteor := 2.5

var _stars: Array[Dictionary] = []
var _t := 0.0
var _acc := 0.0
var _rng := RandomNumberGenerator.new()
var _meteor := {}                              # 正在划的那颗：起点、方向、速度、开始时间、时长、尾巴长
var _next_meteor := 0.0


func _ready() -> void:
	_rng.seed = seed
	while _stars.size() < count:
		var x := _rng.randf_range(area.position.x, area.end.x)
		var y := area.position.y + area.size.y * pow(_rng.randf(), 1.4)   # 越往上越密
		if x < 300.0 and y > 78.0:                                         # 余晖里不放
			continue
		_stars.append({
			"p": Vector2i(int(x), int(y)),
			"base": 0 if _rng.randf() < 0.7 else 1,
			"every": _rng.randf_range(2.5, 9.0),                           # 隔几秒亮一下
			"phase": _rng.randf() * 9.0,
			"len": _rng.randf_range(0.25, 0.7),                            # 亮多久
			"peak": 2 if _rng.randf() < 0.75 else 3,
		})
	_next_meteor = first_meteor


func _process(delta: float) -> void:
	_t += delta
	_acc += delta
	if _meteor.is_empty() and _t >= _next_meteor:
		_spawn_meteor()
	if not _meteor.is_empty() and _t > _meteor.t0 + _meteor.dur:
		_meteor = {}
		_next_meteor = _t + _rng.randf_range(meteor_every.x, meteor_every.y)
	if _acc >= REDRAW:
		_acc = 0.0
		queue_redraw()


func _spawn_meteor() -> void:
	# 从右上往左下（往余晖那边）斜着划
	_meteor = {
		"p": Vector2(_rng.randf_range(200.0, 470.0), _rng.randf_range(6.0, 46.0)),
		"d": Vector2(-1.0, _rng.randf_range(0.32, 0.55)).normalized(),
		"v": _rng.randf_range(150.0, 210.0),
		"t0": _t,
		"dur": _rng.randf_range(0.45, 0.75),
		"tail": _rng.randi_range(7, 11),
	}


func _level(s: Dictionary) -> int:
	var k: float = fmod(_t + s.phase, s.every)
	if k < s.len:
		var f: float = k / s.len                       # 0 → 1：亮上去再落回来
		var up := 1.0 - absf(f * 2.0 - 1.0)
		return maxi(s.base, int(round(up * s.peak)))
	return s.base


func _dot(p: Vector2i, c: Color) -> void:
	draw_rect(Rect2(p, Vector2.ONE), c)


func _draw() -> void:
	for s in _stars:
		_dot(s.p, COLORS[_level(s)])
	# 亮星：芯一直亮，十字的四臂慢慢呼吸（一档 ↔ 两档），外面一圈偶尔出来
	var b := 0.5 + 0.5 * sin(_t * TAU / 5.0)
	var arm: Color = COLORS[2] if b > 0.45 else COLORS[1]
	_dot(HOME_STAR, HOME_CORE)
	for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		_dot(HOME_STAR + d, arm)
		if b > 0.75:
			_dot(HOME_STAR + d * 2, COLORS[0])
	# 流星：头最亮，尾巴一档档暗下去；头在一开始和快结束时暗一点（进出大气）
	if not _meteor.is_empty():
		var e: float = (_t - _meteor.t0) / _meteor.dur
		var head: Vector2 = _meteor.p + _meteor.d * _meteor.v * (_t - _meteor.t0)
		var fade := 1.0 - absf(e * 2.0 - 1.0)
		var top := 3 if fade > 0.35 else 2
		var n: int = _meteor.tail
		var last := Vector2i(-999, -999)
		for i in n:
			var q := Vector2i((head - _meteor.d * float(i) * 1.15).round())
			if q == last:
				continue
			last = q
			var lv := top - int(float(i) / float(n) * (top + 1.0))
			if lv < 0:
				break
			_dot(q, COLORS[lv])
