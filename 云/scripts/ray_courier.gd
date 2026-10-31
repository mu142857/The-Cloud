extends Node2D
## 鳐鱼快递员（美术组画的河流城市邮差，art/characters/ray_courier/，tools/ray_courier_from_gif.py 导入）：
## 隔一阵从屋顶、石柱之间沿一条平缓的弧线游过去一次（这个世界里它在空中游），中途在窄桥边停一停——
## 邮包落在桥栏杆的绳子上、随着上下浮轻轻碰两下（rail_tap，很轻），再游走。下一趟反方向回来。
## 剧本里 hotspot postman（scene bank_postman，「邮差从屋顶的窄桥上过去了」）播的时候它要是不在，就从镜头外叫一趟过来。
##
## 由 room_stage.gd 的 scripts 建（写在 art/river_city/<id>/room_extra.json，生成器不碰那个文件）。坐标是所在层的像素：
## scroll 1.0 = 和主层（晨）一层；0.6 这类 = 跟着那一层视差（和 river_far_lantern.gd 一样，每帧按镜头挪自己）。
## 运动：曲线是过 path 各点的 Catmull-Rom，按弧长走；速度有加速度（起步、刹车都是平滑的，刹车用 v = √(2·a·剩下的路)），
## 上下浮是正弦；帧永远 200ms（美术组原帧长），不跟速度变。位置取整，像素不糊。
## 命令行 --ray_now：开场就叫一趟（截图）；--ray_dim=0.66：换压暗程度；--ray_small=1|2|3：换远景那只的缩小倍数（对比）。

const DIR := "res://art/characters/ray_courier/"
const LAMP_HI := Color8(214, 170, 98)        # 邮包上的小暖灯（河岸石柱上的灯那个色系，亮一档，夜里认得出）；单独一层画，原图一格不动
const LAMP_LO := Color8(160, 112, 56)
const LAMP_CAP := Color8(84, 60, 44)
const HOOK := Color8(58, 44, 44)

var scroll := 1.0
var path: Array = []           # [[x, y], …] 身体中心（json 的 anchor）走过的点，层坐标
var rest := -1                 # 在 path 的第几个点停（−1 不停）
var rest_s := [3.0, 4.5]       # 停几秒
var speed := 18.0              # 巡游速度，像素 / 秒
var accel := 9.0               # 加速度，像素 / 秒²
var period := [35.0, 60.0]     # 一趟游完以后隔多久再来
var first := [8.0, 16.0]       # 进游戏后第一趟什么时候来
var small := 1                 # 1 = 原图；2 / 3 = 整数缩小的那张（远景用）
var dim := [0.8, 0.84, 0.92]   # 身子压暗（乘色，夜里别刺眼）；灯不压
var lamp := true
var bob := 1.5                 # 上下浮多少像素
var bob_s := 2.6               # 浮一圈几秒
var tap := true                # 停在桥边时邮包碰栏杆出声
var tap_db := -17.0
var scene := ""                # 这个 scene 开播时它要是不在，叫一趟过来
var seed := 1
var under := ""              # 画在哪一层的后面（层 id，比如 main）：石柱、桥绳挡在它前面；空 = 用 room 里给的 z

var _rng := RandomNumberGenerator.new()
var _spr: Sprite2D
var _lamp: Node2D
var _snd: AudioStreamPlayer2D
var _fw := 41
var _fh := 30
var _anchor := Vector2(20, 9)
var _lamp_px: Array = []
var _ms := 200.0
var _pts: PackedVector2Array = PackedVector2Array()   # 曲线按 1 像素左右采样
var _cum: PackedFloat32Array = PackedFloat32Array()   # 每个采样点的累计弧长
var _len := 0.0
var _rest_d := -1.0
var _t := 0.0
var _wait := 0.0               # 两趟之间
var _on := false
var _dir := 1                  # 1 = 顺着 path 走（第一趟），−1 = 倒着
var _d := 0.0                  # 走到弧长哪里
var _v := 0.0
var _cruise := 18.0
var _rest_left := 0.0
var _rested := false
var _bob_ph := 0.0
var _last_low := false
var _scene_was := false
var pos := Vector2.ZERO        # 现在身体中心的层坐标（截图 / 调试看）


func _ready() -> void:
	_rng.seed = seed
	var meta = JSON.parse_string(FileAccess.get_file_as_string(DIR + "ray_courier.json")) if FileAccess.file_exists(DIR + "ray_courier.json") else null
	if not meta is Dictionary or path.size() < 2:
		push_warning("ray_courier：缺 ray_courier.json 或 path")
		set_process(false)
		visible = false
		return
	for a in OS.get_cmdline_user_args():                 # 截图对比用：--ray_small=1|2|3 把远景（small > 1）那只换成这个倍数
		if a.begins_with("--ray_small=") and small > 1:
			small = int(a.trim_prefix("--ray_small="))
	var k := maxi(small, 1)
	var sheet := str(meta.get("sheet", "ray_swim.png"))
	if k > 1:
		sheet = str((meta.get("small", {}) as Dictionary).get(str(k), sheet))
	var tex: Texture2D = load(DIR + sheet)
	var fr: Array = meta.get("frame", [41, 30])
	_fw = ceili(float(fr[0]) / k)
	_fh = ceili(float(fr[1]) / k)
	var an: Array = meta.get("anchor", [20, 9])
	_anchor = Vector2(floorf(float(an[0]) / k), floorf(float(an[1]) / k))
	for p in meta.get("lamp", []):
		_lamp_px.append(Vector2(floorf(float(p[0]) / k), floorf(float(p[1]) / k)))
	var an_ms = (meta.get("anims", {}) as Dictionary).get("swim", {}).get("ms", 200)
	_ms = float(an_ms[0] if an_ms is Array else an_ms)
	_spr = Sprite2D.new()
	_spr.texture = tex
	_spr.hframes = maxi(tex.get_width() / _fw, 1)
	_spr.centered = false
	_spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_spr.self_modulate = Color(float(dim[0]), float(dim[1]), float(dim[2]))
	add_child(_spr)
	if lamp and not _lamp_px.is_empty():
		_lamp = Node2D.new()
		_lamp.draw.connect(_draw_lamp)
		add_child(_lamp)
	if tap and ResourceLoader.exists("res://audio/sfx/rail_tap.wav"):
		_snd = AudioStreamPlayer2D.new()
		_snd.stream = load("res://audio/sfx/rail_tap.wav")
		_snd.bus = "SFX"
		_snd.volume_db = tap_db
		_snd.max_distance = 420.0
		add_child(_snd)
	_build_curve()
	if under != "":
		var L := get_parent().get_node_or_null("L_" + under) as CanvasItem
		if L != null:
			z_index = L.z_index - 1      # 和更远的那层同 z，但比它后建，所以压在它前面、在 under 层后面
	_wait = _rng.randf_range(float(first[0]), float(first[1]))
	visible = false
	for a in OS.get_cmdline_user_args():                 # 截图对比用：--ray_dim=0.66 把身子的压暗换成这个（三个通道一样乘）
		if a.begins_with("--ray_dim="):
			var v := float(a.trim_prefix("--ray_dim="))
			_spr.self_modulate = Color(v, v * 1.04, v * 1.12) if v < 1.0 else Color.WHITE
	if "--ray_now" in OS.get_cmdline_user_args():       # 截图用：开场就从镜头外叫一趟过来（和 hotspot 叫的一样）
		_wait = INF
		start_pass.call_deferred(true)


## Catmull-Rom 过每个点（两头各补一个延长点），细分后按弧长累计
func _build_curve() -> void:
	var p: Array[Vector2] = []
	for q in path:
		p.append(Vector2(float(q[0]), float(q[1])))
	var ext: Array[Vector2] = [p[0] * 2.0 - p[1]]
	ext.append_array(p)
	ext.append(p[-1] * 2.0 - p[-2])
	_pts.clear()
	_cum.clear()
	var acc := 0.0
	for i in range(1, ext.size() - 2):
		var p0 := ext[i - 1]
		var p1 := ext[i]
		var p2 := ext[i + 1]
		var p3 := ext[i + 2]
		var n := maxi(int(p1.distance_to(p2)), 2)
		for s in n:
			var t := float(s) / n
			var t2 := t * t
			var t3 := t2 * t
			var q := 0.5 * ((2.0 * p1) + (-p0 + p2) * t + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3)
			if _pts.size() > 0:
				acc += _pts[_pts.size() - 1].distance_to(q)
			if i - 1 == rest and s == 0:
				_rest_d = acc
			_pts.append(q)
			_cum.append(acc)
	acc += _pts[_pts.size() - 1].distance_to(p[-1])
	_pts.append(p[-1])
	_cum.append(acc)
	if rest == p.size() - 1:
		_rest_d = acc
	_len = acc


func _at(d: float) -> Vector2:
	d = clampf(d, 0.0, _len)
	var lo := 0
	var hi := _cum.size() - 1
	while hi - lo > 1:
		var m := (lo + hi) >> 1
		if _cum[m] <= d:
			lo = m
		else:
			hi = m
	var span := _cum[hi] - _cum[lo]
	return _pts[lo].lerp(_pts[hi], 0.0 if span <= 0.0 else (d - _cum[lo]) / span)


func _runner() -> Node:
	var w = get_parent().get("world")
	if w == null:
		return null
	var lv = w.get("level")
	return lv.get("story") if lv != null else null


## 镜头左边缘（房间 x）。层里的 X 在屏幕上 = X − 左边缘 × scroll，所以这一层露出来的是 [左边缘 × scroll, +480]
func _cam_left() -> float:
	var cam := get_viewport().get_camera_2d()
	if cam == null:
		return 0.0
	var o = get_parent().get("origin")
	var ox: float = (o as Vector2).x if o is Vector2 else 0.0
	return cam.get_screen_center_position().x - 240.0 - ox


## summoned：剧本叫来的（hotspot postman）——从镜头外刚好看不见的地方起、游得快一倍，几秒内就到桥边
func start_pass(summoned := false) -> void:
	_on = true
	_rested = false
	_rest_left = 0.0
	_cruise = speed * (2.0 if summoned else 1.0)
	_v = _cruise
	_d = 0.0 if _dir > 0 else _len
	if summoned:
		var edge := _cam_left() * scroll + (-_fw * 0.5 - 4.0 if _dir > 0 else 480.0 + _fw * 0.5 + 4.0)
		var best := _d
		var bd := INF
		var step := 4.0
		var d := 0.0
		while d <= _len:
			var gap := absf(_at(d).x - edge)
			var ok := (_rest_d < 0.0) or (d < _rest_d if _dir > 0 else d > _rest_d)
			if ok and gap < bd:
				bd = gap
				best = d
			d += step
		_d = best
	visible = true


func _process(delta: float) -> void:
	if _spr == null:
		return
	_t += delta
	position.x = roundf(_cam_left() * (1.0 - scroll)) if scroll < 1.0 else 0.0
	_watch_scene()
	if not _on:
		_wait -= delta
		if _wait <= 0.0:
			start_pass()
		return
	_move(delta)
	_place()


func _watch_scene() -> void:
	if scene == "":
		return
	var r := _runner()
	var now: bool = r != null and bool(r.get("busy")) and str(r.get("_cur_scene")) == scene
	if now and not _scene_was and not _on:
		start_pass(true)
	_scene_was = now


func _move(delta: float) -> void:
	if _rest_left > 0.0:
		_rest_left -= delta
		_v = 0.0
		if _rest_left <= 0.0:
			_rested = true
		return
	var vt := _cruise
	var stopping := _rest_d >= 0.0 and not _rested and (_rest_d - _d) * _dir >= 0.0
	if stopping:
		var left := (_rest_d - _d) * _dir
		vt = minf(_cruise, sqrt(2.0 * accel * left))      # 照这个刹车，正好停在桥边
		if left < 0.5:
			_d = _rest_d
			_v = 0.0
			_rest_left = _rng.randf_range(float(rest_s[0]), float(rest_s[1]))
			return
	if _rested and _cruise > speed:
		_cruise = speed                                    # 叫来的那趟：歇过以后照平常的速度走
	_v = move_toward(_v, vt, accel * delta * (2.0 if vt < _v else 1.0))
	var step := _v * delta
	if stopping:
		step = minf(step, (_rest_d - _d) * _dir)
	_d += _dir * step
	if _d < 0.0 or _d > _len:
		_on = false
		visible = false
		_dir = -_dir
		_wait = _rng.randf_range(float(period[0]), float(period[1]))


func _place() -> void:
	var p := _at(_d)
	# 上下浮：停着的时候也浮（邮包一下一下碰栏杆）；从正弦最低点往回算，最低点 = 曲线上的点（停的位置照「最低时邮包贴着栏杆」定）
	var ph := TAU * _t / bob_s
	var off := -bob * 0.5 * (1.0 + cos(ph))
	pos = p + Vector2(0, off)
	var low := cos(ph) < -0.97
	if low and not _last_low and _rest_left > 0.0 and _snd != null:
		_snd.global_position = global_position + pos + Vector2(0, 8)
		_snd.pitch_scale = _rng.randf_range(0.92, 1.08)
		_snd.play()
	_last_low = low
	var right := _dir > 0
	_spr.flip_h = not right
	var ax := _anchor.x if right else float(_fw - 1) - _anchor.x
	_spr.position = (pos - Vector2(ax, _anchor.y)).round()
	_spr.frame = int(_t * 1000.0 / _ms) % _spr.hframes
	if _lamp != null:
		_lamp.queue_redraw()


func _draw_lamp() -> void:
	var lp: Vector2 = _lamp_px[_spr.frame % _lamp_px.size()]
	var x := lp.x if not _spr.flip_h else float(_fw - 1) - lp.x
	var o := _spr.position + Vector2(x, lp.y)
	if small > 1:
		_lamp.draw_rect(Rect2(o + Vector2(0, 1), Vector2.ONE), LAMP_HI)
		return
	# 邮包朝前那个角上挂一盏小灯：一格挂绳、灯帽、两格亮的灯身、灯底；外面一圈很淡的暖光（方块叠两层，不画整圆）
	var c := o + Vector2(0, 3)
	_lamp.draw_rect(Rect2(c + Vector2(-3, -2), Vector2(7, 5)), Color(LAMP_HI, 0.07))
	_lamp.draw_rect(Rect2(c + Vector2(-2, -3), Vector2(5, 7)), Color(LAMP_HI, 0.07))
	_lamp.draw_rect(Rect2(c + Vector2(-1, -1), Vector2(3, 3)), Color(LAMP_HI, 0.12))
	_lamp.draw_rect(Rect2(o, Vector2.ONE), HOOK)
	_lamp.draw_rect(Rect2(o + Vector2(0, 1), Vector2.ONE), LAMP_CAP)
	_lamp.draw_rect(Rect2(o + Vector2(0, 2), Vector2.ONE), LAMP_HI)
	_lamp.draw_rect(Rect2(o + Vector2(0, 3), Vector2.ONE), LAMP_LO)
	_lamp.draw_rect(Rect2(o + Vector2(0, 4), Vector2.ONE), LAMP_CAP)
