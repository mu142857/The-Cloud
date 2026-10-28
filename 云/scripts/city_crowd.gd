extends Node2D
## 一条人行道上匆匆走过的兜帽人：一群剪影，各走各的（往左或往右、快慢不一），互相不理，走出这一层的 960 宽就从另一边绕回来。
## 放在某一层 Parallax2D 下面（坐标是那一层的），repeat 会帮它左右重复；各层一条：远处的人小、慢，近处的大、快。
## 帧图是 tools/city_art.py 画的 art/city/hood_<高>.png：6 帧走路、朝右，灰度三档（255 受光边、70 身子、30 兜帽里的脸），
## 这里乘上 tint 染色：受光边 = tint，身子只有它的七成暗，所以是剪影、不会比晨亮。朝左走的水平翻过来画。
## 人数、速度、染色都写在场景里（city_art.py 的 CROWD），改了重跑 city_art.py。
## 开销：每层几个 draw_texture_rect_region。

@export var texture: Texture2D
@export var frame_size := Vector2i(10, 16)
@export var frames := 6
## 脚底那一行（这一层的坐标）
@export var feet_y := 150.0
@export var count := 6
## 速度范围（像素 / 秒，这一层的坐标）
@export var speed := Vector2(10.0, 16.0)
@export var tint := Color(0.4, 0.4, 0.42)
@export var area_w := 960.0
@export var seed := 1

var _p: Array[Dictionary] = []


func _ready() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	for i in count:
		var sp := rng.randf_range(speed.x, speed.y)
		_p.append({
			"x": rng.randf_range(0.0, area_w),
			"dir": 1.0 if rng.randf() < 0.5 else -1.0,
			"v": sp,
			# 一步的长短跟个子走：走得快的人迈得快，帧换得也快（个子高 h 的人一个周期大约走 0.9h）
			"cycle": frame_size.y * 0.9 / sp,
			"t": rng.randf() * 10.0,
		})


func _process(delta: float) -> void:
	for p in _p:
		p.x = fposmod(p.x + p.dir * p.v * delta, area_w)
		p.t += delta
	queue_redraw()


func _draw() -> void:
	if texture == null:
		return
	var fw := float(frame_size.x)
	var fh := float(frame_size.y)
	for p in _p:
		var f := int(p.t / p.cycle * frames) % frames
		var src := Rect2(f * fw, 0, fw, fh)
		var x := roundf(p.x - fw / 2.0)
		var y := feet_y - fh + 1.0
		if p.dir > 0:
			draw_texture_rect_region(texture, Rect2(x, y, fw, fh), src, tint)
		else:
			draw_set_transform(Vector2(x + fw, y), 0.0, Vector2(-1, 1))
			draw_texture_rect_region(texture, Rect2(0, 0, fw, fh), src, tint)
			draw_set_transform(Vector2.ZERO)
