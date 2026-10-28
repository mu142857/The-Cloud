extends Node2D
## 河流里唯一的暖色：对岸一棵垂须怪树上挂着几颗会发光的果荚、远处岸边一点像有人点的灯（河流那位朋友留下的痕迹）。
## 面积很小（每颗 1~2 格的芯 + 一圈暗暖的晕），亮度明显低于晨、也低于月亮；很慢地明暗呼吸，
## 水里有它一点点碎掉、轻轻晃的倒影。坐标是所在 Parallax2D 那一层的（Shore 或 Ridge），repeat 会帮它左右重复。
## 颜色是 OKLCh 琥珀（h≈60）：芯 L≈0.62 / 0.55 / 0.48 三档按呼吸切，晕 L≈0.29，倒影 L≈0.40 / 0.34。
## 开销：每帧十几到二十几个 1×1 的 draw_rect。

## 每颗：Vector3(x, y, 大小)；大小 2 = 1×2 的芯（大果荚 / 灯），1 = 1×1
@export var lights: Array[Vector3] = []
@export var waterline := 154.0         # 这一层的水线（倒影以它为轴翻下去）
@export var reflect_len := 6           # 倒影最多几段
@export var period := 5.5              # 呼吸一次几秒
@export var husk := true               # 果荚：芯上面一格暗的荚壳；灯就不要
@export var seed := 3

const CORE := [Color8(177, 120, 67), Color8(152, 100, 56), Color8(127, 81, 45)]   # 亮 → 暗（L .62 / .55 / .48）
const HALO := Color8(61, 37, 20)        # L .29
const HUSK := Color8(36, 23, 16)        # L .22
const REFL := [Color8(95, 64, 37), Color8(75, 49, 29)]   # L .40 / .34

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
		var b := 0.5 + 0.5 * sin(_t * TAU / period + _ph[i])          # 0..1 呼吸
		var lv := 0 if b > 0.66 else (1 if b > 0.33 else 2)
		var h := int(L.z)
		# 晕：芯左右各一格（亮的时候上下也有）
		_px(p + Vector2(-1, 0), HALO)
		_px(p + Vector2(1, 0), HALO)
		if lv == 0:
			_px(p + Vector2(0, h), HALO)
			if not husk:
				_px(p + Vector2(0, -1), HALO)
		if husk:
			_px(p + Vector2(0, -1), HUSK)
		for k in h:
			_px(p + Vector2(0, k), CORE[mini(2, lv + k)])
		# 倒影：水线下对称的位置，一段段很短的横线，越往下越稀，跟着时间左右晃一格
		var ry := 2.0 * waterline - L.y
		for k in reflect_len:
			var y := ry + k * 2.0
			var on := sin(_t * 1.7 + k * 2.3 + _ph[i] * 3.0) > -0.2 + 0.25 * k
			if not on:
				continue
			var off := roundf(sin(_t * 2.1 + k * 1.3 + _ph[i]))
			var w := 2 if k < 2 and lv < 2 else 1
			for j in w:
				_px(Vector2(L.x + off + j - (w - 1) * 0.5, y), REFL[0 if (k == 0 and lv == 0) else 1])
