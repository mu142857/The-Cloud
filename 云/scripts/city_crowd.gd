extends Node2D
## 一条人行道上的兜帽人：冷漠，不是焦虑。两股人流，一股往右、一股往左，
## 每一股里所有人一样快、步子一样的节奏、前后间距几乎一样 —— 像流水线，永远不会有人超车、停下、回头。
## 两股人流互相穿过去，谁在前谁在后按人随机定（不会「往左的全压着往右的」）。
## 走出这一层的 960 宽就从另一边绕回来。放在某一层 Parallax2D 下面（坐标是那一层的），repeat 会帮它左右重复；
## 各层一条：远处的人小、慢，近处的大。晨那条街拆成三排（city_art.py 的 STREET_ROWS）：
## 远排（略小、脚底略高、往雾里浅）和中排（晨这个深度）画在晨身后，近排（最大、最暗、脚底最低、很稀）画在她前面；
## 每排一个方向，排和排用明度分开（ramp 着色，见 city_crowd_ramp.gdshader），全不透明，近排整个盖住远排；
## 同一排里间距比人宽，相邻的人不叠在一起。
## 帧图是 tools/city_art.py 画的 art/city/hood_<高>.png：每行一种人（高瘦立领看表 / 高瘦提袋 / 宽肩公文包 / 驼背拐杖 / 驼背纸箱 / 矮壮背包 / 撑伞，有的带两个小变体），
## 每列一帧（8 帧走路、朝右），灰度十几档（255 湿的受光边、120 手、96 袖口领口帽檐、70 外套、48 裤子、36 鞋、30 远侧的胳膊腿、22 脸……），
## 远处几层这里乘上 tint 染色：受光边 = tint，身子只有它的三成，所以是剪影、不会比晨亮；
## 晨那条街的三排打开 ramp：灰度档映射到 lo..hi 这一段明度、受光边 = rim（这一排自己的明度，不是乘法）。朝左走的水平翻过来画。
## 人数、速度、染色都写在场景里（city_art.py 的 CROWD），改了重跑 city_art.py。
## 开销：每层几十个 draw_texture_rect_region。

@export var texture: Texture2D
@export var frame_size := Vector2i(10, 16)
@export var frames := 6
@export var types := 5
## 脚底那一行（这一层的坐标）
@export var feet_y := 150.0
## 一共多少人（direction = 0 时往右一半、往左一半）
@export var count := 6
## 0 = 两股人流（往右、往左各一股）；1 = 只往右；-1 = 只往左
@export var direction := 0
## 每股人流的速度在这个范围里取一个（像素 / 秒，这一层的坐标），同一股里所有人一样快。范围给得很窄
@export var speed := Vector2(10.0, 10.5)
@export var tint := Color(0.4, 0.4, 0.42)
@export var area_w := 960.0
@export var seed := 1
## 间距的抖动（占一格间距的几分之几）：0 = 绝对等距
@export var jitter := 0.15
## 步子对齐的程度：1 = 同一股人流里所有人同一只脚落地（齐步走），0 = 各走各的相位（节奏还是一样）
@export var sync := 0.0
## 脚下的接触阴影：脚底下面那一行（大个子两行）压暗一档，短短一截，硬边（特效，半透明的黑）
@export var shadow := 0.5
## 打开后不乘 tint，按 lo / hi / rim 给这一排上明度（见 city_crowd_ramp.gdshader）
@export var ramp := false
@export var lo := Color(0.1, 0.1, 0.11)
@export var hi := Color(0.2, 0.2, 0.21)
@export var rim := Color(0.3, 0.3, 0.31)
## 手机屏的冷光（帧图里灰度 240 的那几个像素）
@export var glow := Color(0.45, 0.55, 0.6)

## 衣服的配色只在冷灰里有一点点差别（一样的灰、偏冷一点的灰、深一点的灰），大家穿得差不多
const HUES := [Color(1, 1, 1), Color(0.93, 0.96, 1.04), Color(0.86, 0.87, 0.9)]

var _p: Array[Dictionary] = []
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.seed = seed
	if ramp:
		var m := ShaderMaterial.new()
		m.shader = preload("res://scripts/city_crowd_ramp.gdshader")
		m.set_shader_parameter("lo", lo)
		m.set_shader_parameter("hi", hi)
		m.set_shader_parameter("rim", rim)
		m.set_shader_parameter("glow", glow)
		material = m
	if direction != 0:
		_lane(float(direction), count)
	else:
		var n_right := count / 2
		_lane(1.0, n_right)
		_lane(-1.0, count - n_right)
	# 两股人流交错着前后，每人一个固定的前后（画的先后），不随时间变
	_p.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.z < b.z)


func _lane(d: float, n: int) -> void:
	if n <= 0:
		return
	var v := _rng.randf_range(speed.x, speed.y)
	var gap := area_w / n
	var x0 := _rng.randf_range(0.0, area_w)
	# 一步的长短跟个子走（个子高 h 的人一个周期大约走 1.1h）；同一股里大家一样快，所以节奏也一样
	var cycle := frame_size.y * 1.1 / v
	var t0 := _rng.randf() * cycle
	for i in n:
		_p.append({
			"x": fposmod(x0 + i * gap + _rng.randf_range(-jitter, jitter) * gap, area_w), "dir": d, "v": v,
			"type": _rng.randi_range(0, types - 1),
			"col": (Color(1, 1, 1) if ramp else tint) * HUES[_rng.randi_range(0, HUES.size() - 1)],
			"cycle": cycle,
			"t": t0 + _rng.randf() * cycle * (1.0 - sync),
			"z": _rng.randf(),
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
	if shadow > 0.0:
		var sw := maxf(2.0, roundf(fh * 0.24))
		var sh := 2.0 if fh >= 60.0 else 1.0
		for p in _p:
			draw_rect(Rect2(roundf(p.x - fw * 0.03 - sw / 2.0), feet_y + 1.0, sw, sh), Color(0, 0, 0, shadow))
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
