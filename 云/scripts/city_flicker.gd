extends Node2D
## 楼梯间那条竖条窗里的冷白日光灯：一部分楼层亮着（冷白，L≈0.55，比晨暗得多），
## 个别几盏接触不良：大部分时间亮着，隔几秒忽然快速闪两下（灭-亮-灭-亮），偶尔整盏灭掉一阵再亮。
## rects 是 tools/city_art.py 记下来的楼梯间窗洞（图里画的是暗玻璃）。只在楼腰以上，不进晨身后那条。
## 放在某一层 Parallax2D 下面（坐标是那一层的），repeat 会帮它左右重复。
## 硬边：整像素 draw_rect，不半透明。开销：每帧几十个 draw_rect。

@export var rects: Array[Rect2] = []
@export var color := Color(0.46, 0.5, 0.52)
@export var color_top := Color(0.38, 0.42, 0.44)
@export var seed := 1

var _st: Array[Dictionary] = []
var _t := 0.0
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.seed = seed
	for r in rects:
		_st.append({"bad": _rng.randf() < 0.22, "next": _rng.randf_range(0.5, 6.0), "burst": -1.0, "dead": 0.0})


func _process(delta: float) -> void:
	_t += delta
	for s in _st:
		if not s.bad:
			continue
		if s.dead > 0.0:
			s.dead -= delta
		if _t >= s.next:
			if _rng.randf() < 0.15:
				s.dead = _rng.randf_range(1.0, 3.0)        # 整盏灭一阵
			else:
				s.burst = _t
			s.next = _t + _rng.randf_range(2.0, 7.0)
	queue_redraw()


func _on(s: Dictionary) -> bool:
	if s.dead > 0.0:
		return false
	if s.burst >= 0.0:
		var u: float = _t - s.burst
		if u < 0.36:
			return int(u / 0.06) % 2 == 1          # 灭-亮-灭-亮-灭-亮
	return true


func _draw() -> void:
	for i in rects.size():
		if not _on(_st[i]):
			continue
		var r := rects[i]
		draw_rect(r, color)
		draw_rect(Rect2(r.position, Vector2(r.size.x, 1)), color_top)
