extends Node2D
## 前景偶尔经过的大黑影：离镜头最近的那一层（比晨近得多），隔一阵才有一个，
## 一个很大的路人（只露肩膀以下，头被画面上沿切掉，脚被下沿切掉）走过去，或者一辆暗色的车开过去。
## 几乎全暗（比晨暗很多），只有一点冷色：路人肩上一道湿的受光边，车窗上冷灰的反光、车头一盏冷白的灯。
## 匀速、不停、不看晨，从画面一边进、另一边出；每次压过晨的时间都很短（下面 min_screen 保证）。
## 帧图是 tools/city_art.py 画的 art/city/passer.png（每行一种人、每列一帧，已经裁掉头和脚）和 art/city/car.png，
## 颜色是画好的（不再染色）。参数写在场景里（city_art.py 的 PASSERS）。
## 放在一个 CanvasLayer（layer 1）下面，按屏幕坐标画：盖在晨和前景层上面、暗角（layer 10）下面，不进湿街面的倒影；
## 视差自己算：在屏幕上的速度 = 自己的速度 − parallax × 镜头速度。开销：每帧最多一个 draw_texture_rect_region。

@export var walker: Texture2D
@export var walker_frame := Vector2i(160, 270)
@export var walker_frames := 8
@export var walker_types := 2
## 路人这张帧图的上沿在屏幕的哪一行（负数 = 头在画面外）
@export var walker_top := 0.0
@export var walker_speed := 260.0
## 一个走路周期在屏幕上走多远（像素）：跟着帧图里的步幅算
@export var walker_stride := 360.0
@export var car: Texture2D
@export var car_top := 110.0
@export var car_speed := 820.0
## 隔多少秒来一个（从上一个完全走出画面算起）
@export var interval := Vector2(7.0, 12.0)
@export var first_wait := 2.5
## 路人、车轮流来（规律、重复）；关掉就按 car_share 随机
@export var alternate := true
## 不轮流时，车占多少（其余是路人）
@export var car_share := 0.4
## 这一层的视差（比晨那层的 1 大 = 离镜头更近）
@export var parallax := 1.4
## 在屏幕上至少走这么快（像素 / 秒）：晨往同一个方向跑的时候，视差会把它拖慢，这里兜底，不让它一直挡着晨
@export var min_screen := 220.0
@export var seed := 21

const VIEW_W := 480.0

var _rng := RandomNumberGenerator.new()
var _active := false
var _kind := 1            # 0 路人，1 车（轮流时第一个是路人）
var _dir := 1.0
var _sx := 0.0            # 屏幕坐标：图左边缘
var _w := 0.0
var _type := 0
var _t := 0.0
var _wait := 0.0
var _cam_prev := 0.0
var _cam_left := 0.0
var _first := true


func _ready() -> void:
	_rng.seed = seed
	_wait = first_wait


func _cam() -> float:
	# 镜头左边缘在世界里的 x（画布变换的平移就是 -镜头左边缘）
	return -get_viewport().get_canvas_transform().origin.x


func _spawn() -> void:
	_active = true
	if alternate:
		_kind = 1 - _kind
	else:
		_kind = 1 if _rng.randf() < car_share else 0
	if car == null:
		_kind = 0
	if walker == null:
		_kind = 1
	_dir = 1.0 if _rng.randf() < 0.5 else -1.0
	# 晨在跑的时候，从她迎面来（相对速度大，一下就过去）
	var cv := (_cam_left - _cam_prev)
	if absf(cv) > 0.5:
		_dir = -signf(cv)
	_w = float(walker_frame.x) if _kind == 0 else float(car.get_width())
	_type = _rng.randi_range(0, walker_types - 1)
	_sx = -_w if _dir > 0.0 else VIEW_W
	_t = _rng.randf() * 2.0


func _process(delta: float) -> void:
	_cam_left = _cam()
	if _first:
		_cam_prev = _cam_left
		_first = false
	if not _active:
		_wait -= delta
		if _wait <= 0.0:
			_spawn()
	if _active:
		var v := walker_speed if _kind == 0 else car_speed
		var cam_v := (_cam_left - _cam_prev) / maxf(delta, 0.0001)
		var sv := _dir * v - parallax * cam_v
		if sv * _dir < min_screen:
			sv = _dir * min_screen
		_sx += sv * delta
		_t += delta * absf(sv) / v
		if (_dir > 0.0 and _sx > VIEW_W) or (_dir < 0.0 and _sx + _w < 0.0):
			_active = false
			_wait = _rng.randf_range(interval.x, interval.y)
	_cam_prev = _cam_left
	queue_redraw()


func _draw() -> void:
	if not _active:
		return
	var x := roundf(_sx)
	var tex: Texture2D = walker if _kind == 0 else car
	var src: Rect2
	var y: float
	if _kind == 0:
		var cycle := walker_stride / walker_speed
		var f := int(_t / cycle * walker_frames) % walker_frames
		src = Rect2(f * walker_frame.x, _type * walker_frame.y, walker_frame.x, walker_frame.y)
		y = walker_top
	else:
		src = Rect2(0, 0, car.get_width(), car.get_height())
		y = car_top
	if _dir > 0.0:
		draw_texture_rect_region(tex, Rect2(x, y, src.size.x, src.size.y), src)
	else:
		draw_set_transform(Vector2(x + src.size.x, y), 0.0, Vector2(-1, 1))
		draw_texture_rect_region(tex, Rect2(Vector2.ZERO, src.size), src)
		draw_set_transform(Vector2.ZERO)
