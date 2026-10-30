extends Node2D
## 河岸中景：远处两根石柱顶上的细桥上，一个很小的提灯人影慢慢走过去、停一停、再走回来（剧本里的「邮差从屋顶的窄桥上过去了」。
## 第三版：作者嫌近处的大邮差和绳桥抢眼，只剩远处一点灯）。
## 坐标是中景图里的（scroll 和中景层一样），跟中景一起视差。tools/river_bank_moon_art.py 写进河岸 room.json 的 scripts。

var scroll := 0.55
var x0 := 0.0
var x1 := 40.0
var y := 100.0            # 脚底那一行
var speed := 3.0          # 像素 / 秒
var pause := 5.0          # 走到头停几秒

const BODY := Color8(8, 10, 18)
const LAMP := Color8(175, 140, 84)
const LAMP_D := Color8(120, 86, 46)

var _x := 0.0
var _dir := 1
var _wait := 2.0
var _t := 0.0


func _ready() -> void:
	_x = x0


func _process(delta: float) -> void:
	_t += delta
	var cam := get_viewport().get_camera_2d()
	if cam != null:
		var o = get_parent().get("origin")
		var ox: float = (o as Vector2).x if o is Vector2 else 0.0
		var cl := cam.get_screen_center_position().x - 240.0 - ox
		position.x = roundf(cl * (1.0 - scroll))
	if _wait > 0.0:
		_wait -= delta
	else:
		_x += _dir * speed * delta
		if _x >= x1 or _x <= x0:
			_x = clampf(_x, x0, x1)
			_dir = -_dir
			_wait = pause
	queue_redraw()


func _draw() -> void:
	var px := roundf(_x)
	var walking := _wait <= 0.0
	var f := int(_t * 10.0) % 2 if walking else 0          # 100ms 一帧
	draw_rect(Rect2(px, y - 6, 1, 1), BODY)                 # 头
	draw_rect(Rect2(px - 1, y - 5, 2, 3), BODY)             # 身子（披着东西，宽一点）
	draw_rect(Rect2(px - 1 + f, y - 2, 1, 2), BODY)         # 两条腿，走路时交替
	draw_rect(Rect2(px - f, y - 2, 1, 2), BODY)
	var lx := px + 2 * _dir                                 # 手里的灯在走的方向那边，走起来轻轻晃
	var ly := y - 3 + (f if walking else 0)
	draw_rect(Rect2(lx, ly, 1, 1), LAMP)
	draw_rect(Rect2(lx, ly + 1, 1, 1), LAMP_D)
