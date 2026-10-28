extends ColorRect
## 水底的月光光柱（scripts/underwater_shafts.gdshader 画）。挂在一个 480×270、屏幕固定（scroll 0）的 ColorRect 上。
## 光柱从画面上方 focus 那一点散开（月亮在水面里的位置偏右上），每道有自己的斜率、宽、强度、相位；
## shader 让它们慢慢左右摆、一会儿亮一会儿暗，整像素分档抖动。
## light_at(屏幕坐标) 用同一套公式算「这一点有多亮」（0..1 左右），给微粒 / 气泡用：飘进光里的会被照亮。
## 开销：一个全屏的片元着色器（每像素 6 次循环、几个 sin），每帧传一个 float。

@export var focus := Vector2(390, -300)
## 每道：Vector4(中线斜率 dx/dy, 半宽, 强度, 相位)。斜率负 = 往左下斜
@export var shafts: Array[Vector4] = [
	Vector4(-0.42, 0.030, 0.08, 0.3),
	Vector4(-0.30, 0.045, 0.16, 1.7),
	Vector4(-0.20, 0.022, 0.11, 4.1),
	Vector4(-0.11, 0.060, 0.24, 2.6),
	Vector4(-0.025, 0.040, 0.22, 5.2),
	Vector4(0.05, 0.020, 0.10, 0.9),
]
@export var sway := 0.012
@export var y_fade := 150.0
@export var y_end := 205.0

var t := 0.0


func _ready() -> void:
	add_to_group("underwater_shafts")
	var m := material as ShaderMaterial
	var arr := PackedVector4Array()
	for s in shafts:
		arr.append(s)
	m.set_shader_parameter("shafts", arr)
	m.set_shader_parameter("count", shafts.size())
	m.set_shader_parameter("focus", focus)
	m.set_shader_parameter("sway", sway)
	m.set_shader_parameter("y_fade", y_fade)
	m.set_shader_parameter("y_end", y_end)


func _process(delta: float) -> void:
	t += delta
	(material as ShaderMaterial).set_shader_parameter("t", t)


## 屏幕坐标 p 处光柱有多亮（和 shader 同一个公式，不分档）。大约 0..0.2，乘个系数再用。
func light_at(p: Vector2) -> float:
	var tx := (p.x - focus.x) / (p.y - focus.y)
	var a := 0.0
	for i in shafts.size():
		var s: Vector4 = shafts[i]
		var cx := s.x + sway * (sin(t * 0.13 + s.w) + 0.5 * sin(t * 0.29 + s.w * 2.0))
		var q := clampf(1.0 - absf(tx - cx) / s.y, 0.0, 1.0)
		q = q * q * (3.0 - 2.0 * q)
		a += s.z * q * (0.62 + 0.38 * sin(t * (0.19 + 0.04 * i) + s.w * 3.0))
	return a * smoothstep(0.0, 22.0, p.y) * exp(-p.y / y_fade) * (1.0 - smoothstep(y_end - 60.0, y_end, p.y))
