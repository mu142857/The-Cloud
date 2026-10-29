extends Node2D
## 楼梯间那条竖条窗里的冷白日光灯：一部分楼层亮着（冷白，L≈0.55，比晨暗得多）。
## 不闪：城市是冷漠的，不是在报警。个别几盏「坏的」只是很慢地换状态 —— 灭着的一盏，
## 十几二十几秒以后才又亮起来（或者亮着的过很久才灭），没人去修，也没人注意。
## rects 是 tools/city_art.py 记下来的楼梯间窗洞（图里画的是暗玻璃）。只在楼腰以上，不进晨身后那条。
## 放在某一层 Parallax2D 下面（坐标是那一层的），repeat 会帮它左右重复。
## 硬边：整像素 draw_rect，不半透明。开销：每帧几十个 draw_rect（只在有灯换状态时重画）。

@export var rects: Array[Rect2] = []
@export var color := Color(0.46, 0.5, 0.52)
@export var color_top := Color(0.38, 0.42, 0.44)
@export var seed := 1
## 多少盏是「坏的」（会很慢地自己灭、自己亮）
@export var bad_share := 0.15
## 坏灯每次保持亮 / 灭多少秒
@export var hold := Vector2(14.0, 30.0)

var _st: Array[Dictionary] = []
var _t := 0.0
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.seed = seed
	for r in rects:
		var bad: bool = _rng.randf() < bad_share
		_st.append({"bad": bad, "on": not bad or _rng.randf() < 0.5, "next": _rng.randf_range(2.0, hold.y)})


func _process(delta: float) -> void:
	_t += delta
	var changed := false
	for s in _st:
		if s.bad and _t >= s.next:
			s.on = not s.on
			s.next = _t + _rng.randf_range(hold.x, hold.y)
			changed = true
	if changed:
		queue_redraw()


func _draw() -> void:
	for i in rects.size():
		if not _st[i].on:
			continue
		var r := rects[i]
		draw_rect(r, color)
		draw_rect(Rect2(r.position, Vector2(r.size.x, 1)), color_top)
