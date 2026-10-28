extends Node2D
## 水底唯一的暖色：从河岸那棵垂须怪树上掉下来、沉到水底还在发光的果荚（河岸 river_lights.gd 里那种琥珀色）。
## 一颗卡在石头头像额前头环的凹槽里（像一只发着微光的第三只眼），一颗半埋在晨走的河床上。
## 面积很小（1×1 或 1×2 的芯 + 一圈暗暖的晕），亮度明显低于晨；很慢地明暗呼吸；
## 亮的时候头顶偶尔飘起一颗暖色的小光点，往上漂几像素就灭。
## 坐标是所在 Parallax2D 那一层的。开销：每帧十来个 1×1 的 draw_rect。

## 每颗：Vector3(x, y, 大小)；大小 2 = 1×2 的芯，1 = 1×1
@export var lights: Array[Vector3] = []
@export var period := 6.0
@export var seed := 4

const CORE := [Color8(177, 120, 67), Color8(152, 100, 56), Color8(127, 81, 45)]   # L .62 / .55 / .48（和河岸同一套）
const HALO := Color8(61, 37, 20)        # L .29
const SPARK := Color(0.69, 0.47, 0.26)

var _t := 0.0
var _ph: Array[float] = []


func _ready() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	for i in lights.size():
		_ph.append(rng.randf() * TAU)


func _process(delta: float) -> void:
	_t += delta
	queue_redraw()


func _px(p: Vector2, c: Color) -> void:
	draw_rect(Rect2(p.round(), Vector2.ONE), c)


func _draw() -> void:
	for i in lights.size():
		var L: Vector3 = lights[i]
		var p := Vector2(L.x, L.y)
		var b := 0.5 + 0.5 * sin(_t * TAU / period + _ph[i])
		var lv := 0 if b > 0.66 else (1 if b > 0.33 else 2)
		var h := int(L.z)
		_px(p + Vector2(-1, 0), HALO)
		_px(p + Vector2(1, 0), HALO)
		if lv == 0:
			_px(p + Vector2(0, -1), HALO)
			_px(p + Vector2(0, h), HALO)
		for k in h:
			_px(p + Vector2(0, k), CORE[mini(2, lv + k)])
		# 一颗暖色的小光点从果荚上飘起来：每个呼吸周期一次，只在亮的那半
		var cyc := fposmod(_t / period + _ph[i] / TAU, 1.0)
		if cyc < 0.35:
			var u := cyc / 0.35
			var s := SPARK
			s.a = (1.0 - u) * 0.7
			_px(p + Vector2(roundf(sin(u * 5.0 + _ph[i]) * 1.0), -3.0 - u * 9.0), s)
