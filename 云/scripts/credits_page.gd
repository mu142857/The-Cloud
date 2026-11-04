extends Control
## 制作人员（标题界面「制作人员」、设置面板里的「制作人员」、最后一章「全剧终」以后都放它）。
## 11-04 作者：「我都是像电影结束一样一个一个显示，每个都是一个场景」——照 Linger 的片尾（Linger/linger_bilibili/Shared/credits_roll.gd）：
##   一次一个人，每个人在游戏里一个活的场景上（场景整个实例化进 SubViewport，像 flashback.gd 搬城市那样，自己的动画照常跑），
##   场景里那个地方的特效把名字聚出来；木木第一个，先一个人在黑里，名字成形以后森林才从黑里升上来。
##   每人一个地方，不重复（11-04 作者定的）：
##     1 木木      森林的夜（scenes/forest_test.tscn）  萤火虫从四周飞来，停成名字
##     2 本2兔     云层小镇（art/town，room_stage.gd，帆和风车自己在转）  一阵风从左边把淡粉的云丝吹过来，吹成名字；走的时候往右吹散
##     3 梧桐      芦苇地（art/reed_field，芦苇自己一阵阵弯腰）  巨型蒲公英的种子从苇丛里飘上来，一颗颗落成名字
##     4 奥斯卡    下雨的城市街道（scenes/city_test.tscn）  雨里一束光斜落下来，一个像素一个像素画出名字
##     5 特别感谢  月夜河岸（art/river_city/river_bank）  名字在水面上，月光的碎光从左往右一闪一闪亮成名字
##     6 「感谢游玩」+「2026 年 11 月」，在黑里
##   名字和职务读 data/credits.json（和第一关奔跑片头同一份，按 id 找；职务的 role_guess 照旧，作者改那里）。
##   特效：萤火虫、光柱就是 run_credits.gd 里的 Moment；风、种子、水面碎光是下面 Slide（继承 Moment，同一套字形像素、
##   名字 28 号、职务 14 号）加的三种。芦苇地是白天，职务小字换深色（role_col）。
##   每页约 5 秒：黑里淡出场景（1.2 秒）→ 名字成形 → 停 → 名字散开、场景淡回黑（1 秒）。镜头在每页里慢慢平移（sine 缓起缓停）。
##   场景里的晨（还有森林里的蛇女、鹿）都藏起来：只看地方，不看人。
## 输入（level_forest.gd 的 _input 先交给 handle）：点击 / 任意键 = 下一页；Esc = 直接关。
## 音乐：打开时记下 BGM 正在放的曲子，换成 theme（scripts/bgm.gd）；关掉时接回原来那首（原来没放就停掉）。
## 用法照旧：var p := preload("res://scripts/credits_page.gd").new(); 加到 UI 层; p.closed.connect(...)；p.close() 提前关。

signal closed

const DATA := "res://data/credits.json"
const RC := preload("res://scripts/run_credits.gd")
const BGM_GD := preload("res://scripts/bgm.gd")
const ROOM_GD := preload("res://scripts/room_stage.gd")

const IN := 1.2              # 场景从黑里淡出来
const OUT := 1.0             # 淡回黑
const FX_AT := 0.5           # 场景开始淡入以后多久名字开始成形
const HOLD := 1.8            # 名字成形（Moment.FORM_SEC）以后停多久
const LEAVE := 1.0           # 名字散开用多久（同时场景淡回黑）
const FIRST_DARK := 2.6      # 第一页：名字先在黑里成形，过这么久森林才升上来
const FIRST_SHADE := 0.3     # 第一页森林升上来以后还压暗这么多（Linger 的 FIRST_SHADE）
const DRIFT := 26.0          # 每页镜头平移多少像素
const END_HOLD := 3.6        # 最后「感谢游玩」停多久
const SKIP_LEAVE := 0.45     # 点了下一页：名字散得快一点

## 每一页：id = credits.json 里的人；scene = 哪个场景；cam = 镜头中心起点（世界坐标）；at = 名字的中心（屏幕坐标）
##   fx = 这一页用哪种特效（不写 = credits.json 里那人的 style）；role_col = 职务小字的颜色（亮场景用深色）
const SLIDES := [
	{"id": "mumu", "scene": "forest", "cam": Vector2(300, 135), "at": Vector2(240, 116), "first": true, "fx": "fireflies"},
	{"id": "bentootoo", "scene": "town", "cam": Vector2(400, 135), "at": Vector2(150, 64), "fx": "wind"},
	{"id": "wutong", "scene": "reed_field", "cam": Vector2(1100, 135), "at": Vector2(300, 66), "fx": "seeds",
		"role_col": Color("#4f6a7c")},
	{"id": "oscar", "scene": "city", "cam": Vector2(700, 175), "at": Vector2(250, 84), "fx": "light"},
	{"id": "sothere456", "scene": "river_bank", "cam": Vector2(400, 135), "at": Vector2(330, 238), "fx": "glint"},
]
const ROOMS := ["river_bank", "town", "reed_field"]   # room_stage 的房间（其余是 SCENES 里的小样场景）
const SCENES := {
	"forest": "res://scenes/forest_test.tscn",
	"city": "res://scenes/city_test.tscn",
	"cloud": "res://scenes/cloud_test.tscn",
}
const HIDE := ["Chen", "Snake", "Deer"]       # 只看地方，不看人

var auto_mode := false       # 测试：不等按键，每页照常播完
var _entries := {}
var _black: ColorRect
var _view: TextureRect
var _vp: SubViewport
var _world: Node2D           # 现在这一页的场景根（在 SubViewport 里）
var _cam: Camera2D
var _stage: Node2D           # 河岸：room_stage（镜头要每帧喂给它）
var _cam_from := Vector2.ZERO
var _fx: Node2D              # 名字特效（屏幕坐标）
var _moment: Node2D
var _end_box: Control
var _slide := -1
var _st := 0.0               # 这一页过了多久
var _len := 0.0              # 这一页一共多久
var _skip := false
var _closing := false
var _t := 0.0
var _prev_track := ""


func _ready() -> void:
	size = Vector2(480, 270)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_entries = _load()
	_vp = SubViewport.new()
	_vp.size = Vector2i(480, 270)
	_vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_vp)
	_view = TextureRect.new()
	_view.texture = _vp.get_texture()
	_view.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_view.size = size
	_view.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_view)
	_black = ColorRect.new()
	_black.color = Color.BLACK
	_black.size = size
	_black.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_black)
	_fx = Node2D.new()
	add_child(_fx)
	modulate.a = 0.0
	create_tween().tween_property(self, "modulate:a", 1.0, 0.6).set_trans(Tween.TRANS_SINE)
	var bgm = BGM_GD.get_bgm(get_tree())
	_prev_track = str(bgm.current())
	bgm.play("theme", NAN, 1.5, 0, _prev_track if _prev_track != "" else "")
	_run()


func _run() -> void:
	await get_tree().create_timer(0.6).timeout
	for i in SLIDES.size():
		if _closing:
			return
		await _play_slide(i)
	if _closing:
		return
	await _play_end()
	close()


# ======================================================================= 一页
func _play_slide(i: int) -> void:
	_slide = i
	var sd: Dictionary = SLIDES[i]
	var first: bool = sd.get("first", false)
	_build_scene(str(sd["scene"]), sd["cam"])
	_moment = _make_moment(sd)
	_st = 0.0
	_skip = false
	var show_at := FIRST_DARK if first else 0.0                                 # 场景什么时候开始从黑里出来
	var fx_at := 0.3 if first else FX_AT
	var form := RC.Moment.FORM_SEC
	var leave_at := maxf(show_at + IN, fx_at + form) + HOLD
	_len = leave_at + maxf(LEAVE, OUT)
	var shade := FIRST_SHADE if first else 0.0
	var left_at := -1.0
	while _st < _len and not _closing:
		var dt := get_process_delta_time()
		await get_tree().process_frame
		_st += dt
		if _moment != null and not _moment.begun and _st >= fx_at:
			_moment.begin(Vector2(240, 135), 1.0)
		if _skip and left_at < 0.0:
			_skip = false
			left_at = _st                                                       # 点了下一页：马上开始散、淡回黑
			_len = _st + maxf(SKIP_LEAVE, 0.5)
		elif left_at < 0.0 and _st >= leave_at:
			left_at = _st
		if left_at >= 0.0 and _moment != null and _moment.begun and _moment.get("_leave_t") < 0.0:
			_moment.leave_now(SKIP_LEAVE if _len - left_at < LEAVE else LEAVE)
		# 场景亮度：show_at 起淡出来，left_at 起淡回黑
		var k_in := _ease((_st - show_at) / IN)
		var a := lerpf(1.0, shade, k_in)
		if left_at >= 0.0:
			a = lerpf(a, 1.0, _ease((_st - left_at) / (_len - left_at)))
		_black.color.a = a
		# 镜头慢慢平移（sine 缓起缓停，整页走 DRIFT 像素）
		if _cam != null:
			_cam.position = (_cam_from + Vector2(DRIFT * _ease(_st / _len), 0)).round()
		if _stage != null and _stage.has_method("update"):
			_stage.update(dt, _cam.position)
		if _moment != null and _moment.begun:
			_moment.step(dt)
	_black.color.a = 1.0
	_clear()
	print("CREDITS slide %d %s done (%.1fs)" % [i, sd["id"], _st])


## 最后一页：「感谢游玩」+「2026 年 11 月」，黑底
func _play_end() -> void:
	_slide = SLIDES.size()
	_end_box = Control.new()
	_end_box.size = size
	_end_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_end_box.modulate.a = 0.0
	add_child(_end_box)
	var zh := I18n.is_zh()
	var big := _label("感谢游玩" if zh else "Thank you for playing", 28, Color("#d8d4cc"))
	big.position = Vector2(0, 108)
	_end_box.add_child(big)
	var small := _label("2026 年 11 月" if zh else "November 2026", 14, Color(0.62, 0.6, 0.58))
	small.position = Vector2(0, 146)
	_end_box.add_child(small)
	_skip = false
	var tw := create_tween()
	tw.tween_property(_end_box, "modulate:a", 1.0, 1.0).set_trans(Tween.TRANS_SINE)
	var t := 0.0
	while t < 1.0 + END_HOLD and not _skip and not _closing:
		var dt := get_process_delta_time()
		await get_tree().process_frame
		t += dt
	print("CREDITS end card done (%.1fs)" % t)


func _label(text: String, sz: int, col: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", UITheme.font())
	l.add_theme_font_size_override("font_size", sz)
	l.add_theme_color_override("font_color", col)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.size = Vector2(480, sz + 6)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


# ======================================================================= 场景
func _build_scene(kind: String, cam: Vector2) -> void:
	_clear_scene()
	_cam_from = cam
	if kind in ROOMS:
		_world = Node2D.new()
		_stage = ROOM_GD.new()
		_stage.setup(kind, null)
		_world.add_child(_stage)
		_cam = Camera2D.new()
		_world.add_child(_cam)
	else:
		var path: String = SCENES.get(kind, "")
		if path == "" or not ResourceLoader.exists(path):
			push_warning("credits_page：场景 %s 找不到" % path)
			return
		_world = (load(path) as PackedScene).instantiate()
		_world.set_script(null)                     # 小样的根脚本读命令行（--shot= 会存图退出）、管晨和镜头：这里不要
		for n in HIDE:
			var c := _world.get_node_or_null(n)
			if c != null:
				(c as CanvasItem).visible = false
				c.process_mode = Node.PROCESS_MODE_DISABLED
		_cam = _world.get_node_or_null("Camera") as Camera2D
		if _cam == null:
			_cam = Camera2D.new()
			_world.add_child(_cam)
	_vp.add_child(_world)
	_cam.position = cam
	_cam.make_current()
	if _stage != null:
		_stage.update(0.0, cam)


func _make_moment(sd: Dictionary) -> Node2D:
	var id := str(sd["id"])
	var e: Dictionary = _entries.get(id, {})
	if e.is_empty():
		push_warning("credits_page：credits.json 里没有 %s" % id)
		return null
	e = e.duplicate()
	if sd.has("fx"):
		e["style"] = sd["fx"]
	var m := Slide.new()
	if sd.has("role_col"):
		m.role_col = sd["role_col"]
		m.role_shadow = Color(1, 1, 1, 0.35)
	m.setup(e, 0.0)
	m.hold = 999.0                              # 什么时候散由这一页管（leave_now）
	m.position = (sd["at"] as Vector2).round()
	_fx.add_child(m)
	return m


func _clear() -> void:
	if _moment != null and is_instance_valid(_moment):
		_moment.queue_free()
	_moment = null
	_clear_scene()


func _clear_scene() -> void:
	if _world != null and is_instance_valid(_world):
		_world.queue_free()
	_world = null
	_stage = null
	_cam = null


# ======================================================================= 输入、关
## level_forest 的 _input 把事件先交给这里；返回 true = 吃掉了
func handle(event: InputEvent) -> bool:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE:
			close()
		elif _t > 0.4:
			_skip = true
	elif event is InputEventMouseButton and event.pressed and _t > 0.4:
		_skip = true
	return true


func _process(delta: float) -> void:
	_t += delta


func close() -> void:
	if _closing:
		return
	_closing = true
	var bgm = BGM_GD.get_bgm(get_tree())
	if _prev_track != "":
		bgm.play(_prev_track, NAN, 2.0)
	else:
		bgm.stop(1.5)
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 0.0, 0.5).set_trans(Tween.TRANS_SINE)
	tw.tween_callback(func():
		_clear()
		closed.emit()
		queue_free())


static func _ease(k: float) -> float:
	return 0.5 - 0.5 * cos(clampf(k, 0.0, 1.0) * PI)


## credits.json 的 entries，按 id
func _load() -> Dictionary:
	var out := {}
	if not FileAccess.file_exists(DATA):
		return out
	var d = JSON.parse_string(FileAccess.get_file_as_string(DATA))
	if d is Dictionary and d.get("entries") is Array:
		for e in d["entries"]:
			if e is Dictionary:
				out[str(e.get("id", ""))] = e
	return out


# ----------------------------------------------------------------------- 这几页自己的特效（继承片头的 Moment）
class Slide extends "res://scripts/run_credits.gd".Moment:
	const MINE := ["wind", "seeds", "glint"]
	const WISP := Color("#ecd6ea")              # 小镇的云丝：淡粉
	const SEED := Color("#f6ecc8")
	const FLUFF := Color("#ffffff")
	const SEED_C := [Color("#e08638"), Color("#f2a65a"), Color("#c06a30")]
	const GLINT := Color("#dcecf6")

	var role_col := Color(0.62, 0.6, 0.58)
	var role_shadow := Color(0.02, 0.04, 0.035, 0.8)

	func _layout() -> void:
		super._layout()
		if not style in MINE:
			return
		var w := maxf(1.0, _box.size.x)
		for i in _blk.size():
			var tg := _blk[i] + Vector2(1, 1)
			var fx := (tg.x - _box.position.x) / w
			match style:
				"wind":                                                         # 从左边吹过来，往右吹走
					_from[i] = tg + Vector2(-_rng.randf_range(150, 240), _rng.randf_range(-36, 36))
					_ctrl[i] = (_from[i] + tg) / 2.0 + Vector2(0, _rng.randf_range(-30, 18))
					_delay[i] = _rng.randf_range(0.0, 0.9) + fx * 0.25
					_dur[i] = _rng.randf_range(0.9, 1.3)
					_away[i] = tg + Vector2(_rng.randf_range(90, 170), _rng.randf_range(-24, 8))
					_away_c[i] = (tg + _away[i]) / 2.0 + Vector2(0, -_rng.randf_range(6, 20))
					_away_d[i] = (1.0 - fx) * 0.35 + _rng.randf_range(0.0, 0.1)
				"seeds":                                                        # 从下面苇丛里飘上来，往右上飘走
					_from[i] = Vector2(tg.x - _rng.randf_range(40, 160), _box.end.y + _rng.randf_range(50, 110))
					_ctrl[i] = Vector2(_from[i].x + _rng.randf_range(10, 60), minf(_from[i].y, tg.y) - _rng.randf_range(10, 40))
					_delay[i] = _rng.randf_range(0.0, 1.0)
					_dur[i] = _rng.randf_range(1.0, 1.3)
					_away[i] = tg + Vector2(_rng.randf_range(40, 120), -_rng.randf_range(40, 90))
					_away_c[i] = (tg + _away[i]) / 2.0 + Vector2(_rng.randf_range(-10, 20), -10)
					_away_d[i] = _rng.randf_range(0.0, 0.5)
				"glint":                                                        # 月光路的碎光：从左往右一闪一闪亮起来
					_delay[i] = 0.25 + 1.5 * clampf(fx + _rng.randf_range(-0.15, 0.15), 0.0, 1.0)
					_away_d[i] = _rng.randf_range(0.0, 0.6)
		var k: int = {"wind": 6, "seeds": 8, "glint": 16}.get(style, 0)
		for j in k:
			_extra.append([Vector2(_rng.randf_range(-1.0, 1.0), _rng.randf_range(-1.0, 1.0)), _rng.randf() * TAU, _rng.randf()])

	func _draw() -> void:
		if not style in MINE:
			super._draw()
			return
		if not begun:
			return
		var ra := _role_a()
		if ra > 0.01:
			for p in _role:
				draw_rect(Rect2(_role_at + p + Vector2(1, 1), Vector2.ONE), Color(role_shadow, role_shadow.a * ra))
			for p in _role:
				draw_rect(Rect2(_role_at + p, Vector2.ONE), Color(role_col, ra))
		match style:
			"wind": _draw_wind()
			"seeds": _draw_seeds()
			"glint": _draw_glint()

	func _draw_glow() -> void:
		if not style in MINE:
			super._draw_glow()
			return
		if not begun:
			return
		var g := Color(0.3, 0.78, 0.82) if style == "wind" else (Color(0.55, 0.65, 0.8) if style == "glint" else Color(0.9, 0.6, 0.3))
		var ga := 0.09 if style != "seeds" else 0.05
		for i in _blk.size():
			if _landed_at(i):
				var a := 1.0 - _e(_leave_k(i, 0.5))
				_glow.draw_rect(Rect2(_blk[i] - Vector2(1, 1), Vector2(4, 4)), Color(g, ga * a))

	## 这一块落定了没有（glint：亮过那一下以后）
	func _landed_at(i: int) -> bool:
		if style == "glint":
			return _t >= _delay[i]
		return _t >= _delay[i] + _dur[i] and _leave_k(i) <= 0.0

	func _fly(i: int, sway: float) -> Vector2:
		var lk := _leave_k(i)
		if lk > 0.0:
			return _bez(_blk[i] + Vector2(1, 1), _away_c[i], _away[i], _e(lk)) + Vector2(0, sway * sin(_t * 5.0 + _ph[i]) * lk)
		var u := _e((_t - _delay[i]) / _dur[i])
		return _bez(_from[i], _ctrl[i], _blk[i] + Vector2(1, 1), u) + Vector2(sway * sin(_t * 4.0 + _ph[i]) * (1.0 - u), 0)

	func _fly_a(i: int) -> float:
		var lk := _leave_k(i)
		if lk > 0.0:
			return 1.0 - _e(lk)
		return clampf((_t - _delay[i]) / 0.3, 0.0, 1.0)

	# ---- 本2兔：小镇的风
	func _draw_wind() -> void:
		var c := col.lerp(Color.WHITE, 0.3)
		for i in _blk.size():
			if _landed_at(i):
				draw_rect(Rect2(_blk[i] + Vector2(1, 1), Vector2(2, 2)), Color(SHADOW, 0.6))
				draw_rect(Rect2(_blk[i], Vector2(2, 2)), c.lerp(Color.WHITE, 0.15 * (0.5 + 0.5 * sin(_t * 1.6 + _ph[i]))))
			else:
				var a := _fly_a(i)
				if a > 0.01:
					var p := _fly(i, 0.0).round()
					draw_rect(Rect2(p - Vector2(2, 0), Vector2(3, 1)), Color(WISP, 0.85 * a))     # 一缕：被风拉长的一小横
		# 风：几道细长的风线从左往右掠过（每道是一整条连续的线）
		var ea := _extra_alpha()
		for x in _extra:
			var v: Vector2 = x[0]
			var span := _box.size.x + 200.0
			var u := fmod(_t * 0.55 + float(x[2]), 1.0)
			var ln := 14.0 + 14.0 * absf(v.x)
			var p := Vector2(_box.position.x - 100.0 + span * u, _box.get_center().y + v.y * 34.0 + 3.0 * sin(u * 6.0 + float(x[1])))
			var a := ea * sin(u * PI) * 0.35
			if a > 0.02:
				draw_rect(Rect2(p.round(), Vector2(roundf(ln), 1)), Color(WISP, a))

	# ---- 梧桐：芦苇地的蒲公英种子
	func _draw_seeds() -> void:
		var sh := Color(0.2, 0.3, 0.42, 0.45)
		for i in _blk.size():
			if _landed_at(i):
				draw_rect(Rect2(_blk[i] + Vector2(1, 1), Vector2(2, 2)), sh)
				draw_rect(Rect2(_blk[i], Vector2(2, 2)), SEED_C[_shade[i]])
			else:
				var a := _fly_a(i)
				if a > 0.01:
					_seed(_fly(i, 3.0).round(), a)
		var ea := _extra_alpha()
		for x in _extra:                                                       # 还有几颗一直慢慢飘过去
			var v: Vector2 = x[0]
			var span := _box.size.x + 220.0
			var u := fmod(_t * 0.09 + float(x[2]), 1.0)
			var p := Vector2(_box.position.x - 110.0 + span * u, _box.get_center().y + v.y * 44.0 + 6.0 * sin(_t * 0.8 + float(x[1])) - 30.0 * u)
			var a := ea * sin(u * PI)
			if a > 0.02:
				_seed(p.round(), a)

	func _seed(p: Vector2, a: float) -> void:
		draw_rect(Rect2(p, Vector2.ONE), Color(SEED, a))
		draw_rect(Rect2(p + Vector2(-1, -1), Vector2(3, 1)), Color(FLUFF, 0.7 * a))        # 头上一小撮绒毛

	# ---- 特别感谢：河面上的月光碎光
	func _draw_glint() -> void:
		for i in _blk.size():
			var k := (_t - _delay[i]) / 0.35
			if k < 0.0:
				continue
			var a := 1.0 - _e(_leave_k(i, 0.4))
			if a <= 0.01:
				continue
			if k < 1.0:
				draw_rect(Rect2(_blk[i] + Vector2(-2, 0), Vector2(6, 1)), Color(1, 1, 1, a * (1.0 - 0.5 * k)))   # 一道横的亮光
			draw_rect(Rect2(_blk[i] + Vector2(1, 1), Vector2(2, 2)), Color(SHADOW, 0.6 * a))
			var tw := 0.5 + 0.5 * sin(_t * 2.1 + _ph[i])
			draw_rect(Rect2(_blk[i], Vector2(2, 2)), Color(col.lerp(GLINT, 0.2 + 0.3 * tw), a))
		var ea := _extra_alpha()
		for x in _extra:                                                       # 名字周围水面上一闪一闪的碎光（短横）
			var v: Vector2 = x[0]
			var p := _box.get_center() + Vector2(v.x * (_box.size.x / 2.0 + 70.0), v.y * 16.0 + 8.0)
			var bl := pow(0.5 + 0.5 * sin(_t * (1.3 + float(x[2])) + float(x[1])), 3.0)
			var a := ea * bl * 0.8
			if a > 0.03:
				draw_rect(Rect2(p.round(), Vector2(3 + int(float(x[2]) * 3.0), 1)), Color(GLINT, a))
