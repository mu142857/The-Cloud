extends Node2D
## 一条人行道上赶路的兜帽人：一大群剪影，往左往右交错、快慢不一（快的会超过慢的），互相不理；
## 有些人三两成群一起走，每条道上还有一小股人走得特别快、挤成一团涌过去（绕一圈回来，隔一阵就涌过一次）。
## 走出这一层的 960 宽就从另一边绕回来。放在某一层 Parallax2D 下面（坐标是那一层的），repeat 会帮它左右重复；
## 各层一条：远处的人小、慢，近处的大、快，前景的大个子只露上半身、一闪而过。
## 帧图是 tools/city_art.py 画的 art/city/hood_<高>.png：每行一种人（高瘦立领看表 / 高瘦提袋 / 宽肩公文包 / 驼背拐杖 / 驼背纸箱 / 矮壮背包 / 撑伞，有的带两个小变体），
## 每列一帧（8 帧走路、朝右），灰度十几档（255 湿的受光边、120 手、96 袖口领口帽檐、70 外套、48 裤子、36 鞋、30 远侧的胳膊腿、22 脸……），
## 这里乘上 tint 染色：
## 受光边 = tint，身子只有它的三成，所以是剪影、不会比晨亮。朝左走的水平翻过来画。
## 人数、速度、染色都写在场景里（city_art.py 的 CROWD），改了重跑 city_art.py。
## 开销：每层几十个 draw_texture_rect_region。

@export var texture: Texture2D
@export var frame_size := Vector2i(10, 16)
@export var frames := 6
@export var types := 5
## 脚底那一行（这一层的坐标）
@export var feet_y := 150.0
@export var count := 6
## 速度范围（像素 / 秒，这一层的坐标）
@export var speed := Vector2(10.0, 16.0)
@export var tint := Color(0.4, 0.4, 0.42)
@export var area_w := 960.0
@export var seed := 1

## 同一种人复制太多会穿帮：每个人在 tint 上再乘一种配色（暗灰 / 深蓝灰 / 深棕灰），再加上帧图里的小变体（围巾、伞的角度）
const HUES := [Color(1, 1, 1), Color(0.88, 0.95, 1.12), Color(1.1, 1.0, 0.88)]

var _p: Array[Dictionary] = []
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.seed = seed
	var fw := float(frame_size.x)
	var left := count
	# 一小股挤在一起、走得特别快的人（涌过去）
	var surge := clampi(count / 6, 0, 5) if count >= 6 else 0
	if surge >= 2:
		var d := 1.0 if _rng.randf() < 0.5 else -1.0
		var x0 := _rng.randf_range(0.0, area_w)
		var v0 := speed.y * 1.35
		for i in surge:
			_add(x0 + i * fw * _rng.randf_range(0.5, 0.9), d, v0 * _rng.randf_range(0.95, 1.05))
		left -= surge
	while left > 0:
		var d := 1.0 if _rng.randf() < 0.5 else -1.0
		var n := 1
		if _rng.randf() < 0.3:
			n = mini(left, _rng.randi_range(2, 3))     # 三两成群
		var x := _rng.randf_range(0.0, area_w)
		var v := _rng.randf_range(speed.x, speed.y)
		for i in n:
			_add(x + i * fw * _rng.randf_range(0.7, 1.4), d, v * _rng.randf_range(0.92, 1.08))
		left -= n


func _add(x: float, d: float, v: float) -> void:
	_p.append({
		"x": fposmod(x, area_w), "dir": d, "v": v,
		"type": _rng.randi_range(0, types - 1),
		"col": tint * HUES[_rng.randi_range(0, HUES.size() - 1)],
		# 一步的长短跟个子走：走得快的人迈得快，帧换得也快（个子高 h 的人一个周期大约走 1.1h）
		"cycle": frame_size.y * 1.1 / v,
		"t": _rng.randf() * 10.0,
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
		var src := Rect2(f * fw, p.type * fh, fw, fh)
		var x := roundf(p.x - fw / 2.0)
		var y := feet_y - fh + 1.0
		if p.dir > 0:
			draw_texture_rect_region(texture, Rect2(x, y, fw, fh), src, p.col)
		else:
			draw_set_transform(Vector2(x + fw, y), 0.0, Vector2(-1, 1))
			draw_texture_rect_region(texture, Rect2(0, 0, fw, fh), src, p.col)
			draw_set_transform(Vector2.ZERO)
