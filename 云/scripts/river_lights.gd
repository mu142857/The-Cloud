extends Node2D
## 河流里唯一的暖色：对岸一棵垂须怪树上挂着几颗会发光的果荚、远处岸边一点像有人点的灯（河流那位朋友留下的痕迹）。
## 面积很小（大果荚 2×2 的芯 + 一格尖，小的 1×2，外面一圈暗暖的晕），亮度明显低于晨、也低于月亮；很慢地明暗呼吸，
## 最暗的时候也一直隐约看得见。水里有它一点点碎掉、轻轻晃的倒影。坐标是所在 Parallax2D 那一层的（Shore 或 Ridge），
## repeat 会帮它左右重复。
## 颜色是 OKLCh 琥珀（h≈60）：芯 L≈0.62 / 0.585 / 0.55 三档按呼吸切，晕 L≈0.30（亮时斜角再一圈 0.24），倒影 L≈0.40 / 0.34。
## 开销：每帧二三十个 1×1 的 draw_rect。

## 每颗：Vector3(x, y, 大小)；大小 3 = 2×2 的芯 + 下面一格尖（大果荚），2 = 1×2 的芯（小果荚 / 灯），1 = 1×1
@export var lights: Array[Vector3] = []
@export var waterline := 154.0         # 这一层的水线（倒影以它为轴翻下去）
@export var reflect_len := 6           # 倒影最多几段
@export var period := 5.5              # 呼吸一次几秒
@export var husk := true               # 果荚：芯上面一格暗的荚壳；灯就不要
@export var seed := 3

# 呼吸最暗的时候也只比最亮暗两档（L .62 → .55），晕一直在：暗下去的半个周期也隐约看得见，但仍暗于月亮（.64~.68）和晨
const CORE := [Color8(177, 120, 67), Color8(164, 111, 62), Color8(150, 101, 57)]   # 亮 → 暗（L .62 / .585 / .55）
const HALO := Color8(66, 40, 20)        # L .30，芯的上下左右
const HALO2 := Color8(46, 30, 18)       # L .24，亮的时候斜角上再晕一圈
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


## 芯的格子：[偏移, 比这一档再暗几档]
static func _core_cells(size: int) -> Array:
	if size >= 3:
		return [[Vector2(0, 0), 0], [Vector2(1, 0), 0], [Vector2(0, 1), 0], [Vector2(1, 1), 1], [Vector2(0, 2), 2]]
	if size == 2:
		return [[Vector2(0, 0), 0], [Vector2(0, 1), 1]]
	return [[Vector2(0, 0), 0]]


func _draw() -> void:
	for i in lights.size():
		var L: Vector3 = lights[i]
		var p := Vector2(L.x, L.y)
		var b := 0.5 + 0.5 * sin(_t * TAU / period + _ph[i])          # 0..1 呼吸
		var lv := 0 if b > 0.62 else (1 if b > 0.3 else 2)
		var size := int(L.z)
		var cells := _core_cells(size)
		var occ := {}
		for c in cells:
			occ[c[0]] = true
		# 晕：芯的上下左右一直有一圈暗暖的（荚壳那格除外）；亮的时候斜角上再淡淡一圈
		var halo := {}
		var halo2 := {}
		for c in cells:
			for d in [Vector2(-1, 0), Vector2(1, 0), Vector2(0, 1), Vector2(0, -1)]:
				var q: Vector2 = c[0] + d
				if not occ.has(q):
					halo[q] = true
			if lv == 0:
				for d in [Vector2(-1, -1), Vector2(1, -1), Vector2(-1, 1), Vector2(1, 1)]:
					var q: Vector2 = c[0] + d
					if not occ.has(q):
						halo2[q] = true
		var hw := 2 if size >= 3 else 1
		for q in halo2:
			if not halo.has(q) and not (husk and q.y < 0):
				_px(p + q, HALO2)
		for q in halo:
			if husk and q.y < 0:
				continue
			_px(p + q, HALO)
		if husk:
			for k in hw:
				_px(p + Vector2(k, -1), HUSK)
		for c in cells:
			_px(p + c[0], CORE[mini(2, lv + int(c[1]))])
		# 倒影：水线下对称的位置，一段段很短的横线，越往下越稀，跟着时间左右晃一格
		var ry := 2.0 * waterline - L.y
		for k in reflect_len:
			var y := ry + k * 2.0
			var on := sin(_t * 1.7 + k * 2.3 + _ph[i] * 3.0) > -0.2 + 0.25 * k
			if not on:
				continue
			var off := roundf(sin(_t * 2.1 + k * 1.3 + _ph[i]))
			var w := (hw + 1) if k < 2 and lv < 2 else hw
			for j in w:
				_px(Vector2(L.x + off + j - (w - hw) * 0.5, y), REFL[0 if (k == 0 and lv == 0) else 1])
