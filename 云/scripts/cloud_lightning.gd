extends Sprite2D
## 远处云柱里的闪电：flash.png（tools/cloud_art.py 画的，云柱中间那片从里面亮起来的样子）平时隐藏，
## 隔一阵闪一下：亮 60~90ms、灭、再亮一下（偶尔只闪一下、偶尔闪三下）。只是开关一张图，没有 shader、没有灯。
## 挂在 Spires 那层（Parallax2D）里，跟云柱一起动。

@export var every := Vector2(8.0, 17.0)       # 隔多少秒闪一次（随机）
@export var first := 4.0                      # 第一次在几秒
@export var seed := 5

var _rng := RandomNumberGenerator.new()
var _t := 0.0
var _next := 0.0
var _pattern: Array[Vector2] = []             # 这一次的 (开始, 结束)，相对 _next


func _ready() -> void:
	_rng.seed = seed
	visible = false
	_next = first
	_make_pattern()


func _make_pattern() -> void:
	_pattern.clear()
	var n := 2
	var r := _rng.randf()
	if r < 0.25:
		n = 1
	elif r > 0.8:
		n = 3
	var s := 0.0
	for i in n:
		var on := _rng.randf_range(0.05, 0.09)
		_pattern.append(Vector2(s, s + on))
		s += on + _rng.randf_range(0.07, 0.16)


func _process(delta: float) -> void:
	_t += delta
	var k := _t - _next
	var on := false
	for p in _pattern:
		if k >= p.x and k < p.y:
			on = true
	visible = on
	if k > _pattern[-1].y:
		_next = _t + _rng.randf_range(every.x, every.y)
		_make_pattern()
