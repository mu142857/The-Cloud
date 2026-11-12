extends Control
## 制作人员（标题界面「制作人员」、设置面板里的「制作人员」、最后一章「全剧终」以后都放它）。
## 11-04 作者：「我都是像电影结束一样一个一个显示，每个都是一个场景」——照 Linger 的片尾（Linger/linger_bilibili/Shared/credits_roll.gd）：
##   一次一个人，每个人在游戏里一个活的场景上（场景整个实例化进 SubViewport，像 flashback.gd 搬城市那样，自己的动画照常跑），
##   场景里那个地方的特效把名字聚出来。每人一个地方，不重复（11-04 作者定的）：
##     1 木木      森林的夜（scenes/forest_test.tscn）  萤火虫从四周飞来，停成名字
##     2 本2兔     云层小镇（art/town，room_stage.gd，帆和风车自己在转）  一阵风从左边把淡粉的云丝吹过来，吹成名字；走的时候往右吹散
##     3 梧桐      芦苇地（art/reed_field，芦苇自己一阵阵弯腰）  巨型蒲公英的种子从苇丛里飘上来，一颗颗落成名字
##     4 奥斯卡    下雨的城市街道（scenes/city_test.tscn）  雨里一束光斜落下来，一个像素一个像素画出名字
##     5 特别感谢  月夜河岸（art/river_city/river_bank）  一个不写职位的大列表（credits.json 的 special_thanks，names 一列），月光的碎光一闪一闪亮成名字
##     6 「感谢游玩」+「2026 年 11 月」，在回家的列车上（art/home_train，车窗外的城自己往后走，字在车顶上面的暗处）
##   名字和职务读 data/credits.json（和第一关奔跑片头同一份，按 id 找；职务的 role_guess 照旧，作者改那里）。
##   特效：萤火虫、光柱就是 run_credits.gd 里的 Moment；风、种子、水面碎光是下面 Slide（继承 Moment，同一套字形像素、
##   名字 28 号、职务 14 号）加的三种。芦苇地是白天，职务小字换深色（role_col）。
## 换页（11-04 作者：「闪黑不好，黑色的时候太长了。不如还是之前方格切换吧」）：不经过黑，
##   下一页的场景用八比特方格一格一格盖上来（和 fade_to "style": "pixel" 同一套：level_forest.gd 的 PIXEL_CELL 16 像素一格、
##   PIXEL_STEPS 8 档、每格第几档由 hash(Vector2i(格x, 格y)) 定，这里一档 0.1 秒，共 0.8 秒）。
##   两个 SubViewport 轮流用（这一页、下一页）；名字画在各自场景的 SubViewport 里（一层 CanvasLayer），换页时连名字一起被方格换掉。
##   打开时从标题画面直接方格切到森林（木木那页一开始就有森林，萤火虫在森林里聚）；最后「感谢游玩」那页也是方格切到列车，全程不经过黑。
##   每页约 4.5 秒：方格切进来 → 名字成形 → 停 → 名字开始散、方格切到下一页。镜头在每页里慢慢平移（sine 缓起缓停）。
##   下一页的场景提前 PREBUILD 秒建好（建场景那一下可能卡一帧，别卡在方格中间）。
##   场景里的晨（还有森林里的蛇女、鹿）都藏起来：只看地方，不看人。
## 「全剧终」以后（from_end = true，story_runner._credits_roll 打开）：同一套页，只是开头和结尾都是淡：
##   木木那页的森林整页从结束卡上淡出来（FROM_END_IN 秒，名字在淡的后半段开始聚）；
##   「感谢游玩」停够以后整屏淡到黑（FROM_END_OUT 秒），音乐同时淡掉，然后发 closed，页留着（黑的）等关卡重新载入回标题。
## 输入（level_forest.gd 的 _input 先交给 handle）：11-06 作者「制作人员不能跳」：点击、任意键都不跳页。全剧终以后（from_end）Esc 也不管用；
##   从标题 / 设置点进来的（菜单页），Esc 还能退回菜单。
## 时长（11-06 作者「持续的时间长一点，至少多消耗一点主题音乐」）：theme.wav 55.7 秒，54 秒才收尾。全剧终那条路主题曲比名单早 7.7 秒开始
##   （story_runner._end_chapter），名单 44.3 秒，放到曲子第 52 秒开始淡到黑，音乐的结尾和标题的鸟叫交叉。改每页时长（HOLD、END_HOLD、SLIDES 的 hold）要一起算这个总数。
## 音乐：打开时记下 BGM 正在放的曲子，换成 theme（scripts/bgm.gd）；关掉时接回原来那首（原来没放就停掉）。
## 用法照旧：var p := preload("res://scripts/credits_page.gd").new(); 加到 UI 层; p.closed.connect(...)；p.close() 提前关。

signal closed

const DATA := "res://data/credits.json"
const RC := preload("res://scripts/run_credits.gd")
const BGM_GD := preload("res://scripts/bgm.gd")
const ROOM_GD := preload("res://scripts/room_stage.gd")

const CELL := 16             # 方格：和 level_forest.gd 的 PIXEL_CELL / PIXEL_STEPS 一样
const STEPS := 8
const SWAP := 0.8            # 一次换页（8 档 × 0.1 秒）
const FX_AT := 0.5           # 方格开始切进来以后多久名字开始成形
const HOLD := 4.0            # 名字成形（Moment.FORM_SEC）以后停多久
const LEAVE := 1.0           # 名字散开用多久（和下一页的方格同时）
const PREBUILD := 1.2        # 换页前多久先把下一页的场景建好
const DRIFT := 26.0          # 每页镜头平移多少像素
const END_HOLD := 6.3        # 最后「感谢游玩」停多久
const NAMES_LAYER := 100     # 名字那一层（在场景自己的暗角 Overlay 上面）
const FROM_END_IN := 2.0     # 全剧终 → 森林那页：淡进来多久
const FROM_END_OUT := 1.6    # 感谢游玩 → 黑：淡多久（之后标题从黑里淡出来）

## 每一页：id = credits.json 里的人；scene = 哪个场景；cam = 镜头中心起点（房间 / 场景坐标）；at = 名字的中心（屏幕坐标）
##   fx = 这一页用哪种特效（不写 = credits.json 里那人的 style）；role_col = 职务小字的颜色（亮场景用深色）
const SLIDES := [
	{"id": "mumu", "scene": "forest", "cam": Vector2(300, 135), "at": Vector2(240, 116), "fx": "fireflies"},
	{"id": "bentootoo", "scene": "town", "cam": Vector2(400, 135), "at": Vector2(150, 64), "fx": "wind"},
	{"id": "wutong", "scene": "reed_field", "cam": Vector2(1100, 135), "at": Vector2(300, 66), "fx": "seeds",
		"role_col": Color("#4f6a7c")},
	{"id": "oscar", "scene": "city", "cam": Vector2(700, 175), "at": Vector2(250, 84), "fx": "light"},
	{"id": "special_thanks", "scene": "river_bank", "cam": Vector2(400, 135), "at": Vector2(128, 122), "fx": "glint", "hold": 6.0},
]
## 最后「感谢游玩」那页的场景：列车一屏宽，镜头不平移；没有名字，字是 _play_end 另外放的
const END_SLIDE := {"scene": "home_train", "cam": Vector2(240, 135), "drift": 0.0}
const ROOMS := ["river_bank", "town", "reed_field", "home_train"]   # room_stage 的房间（其余是 SCENES 里的小样场景）
const SCENES := {
	"forest": "res://scenes/forest_test.tscn",
	"city": "res://scenes/city_test.tscn",
	"cloud": "res://scenes/cloud_test.tscn",
}
const HIDE := ["Chen", "Snake", "Deer"]       # 只看地方，不看人

var _entries := {}
var _slots: Array = [{}, {}]  # 两个 SubViewport 轮流：{vp, world, cam, stage, cam_from, moment, t, live}
var _shown: TextureRect       # 现在整屏显示的那一页
var _mix: Control             # 换页时一格一格盖上来的下一页
var _mix_k := 0               # 盖到第几档（0 = 没在换页）
var _mix_tex: Texture2D       # 盖上来的是哪一页
var _end_box: Control
var _slide := -1
var _closing := false
var _t := 0.0
var _prev_track := ""
var _started := false
var black_frames := 0         # 测试：人和人之间整屏是黑的帧数（应该是 0）
var from_end := false         # 「全剧终」以后放的（加进树之前设）：淡进、淡到黑，不回到底下的画面
# 测试看的：最新一页的场景
var _world: Node2D
var _cam: Camera2D
var _stage: Node2D
var _moment: Node2D


func _ready() -> void:
	size = Vector2(480, 270)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_entries = _load()
	for i in 2:
		var vp := SubViewport.new()
		vp.size = Vector2i(480, 270)
		vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
		vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		add_child(vp)
		_slots[i] = {"vp": vp}
	_shown = TextureRect.new()                   # 一开始没图：底下还是标题画面，第一次方格直接盖上森林
	_shown.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_shown.size = size
	_shown.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_shown)
	_mix = Control.new()
	_mix.size = size
	_mix.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mix.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_mix.draw.connect(_draw_mix)
	add_child(_mix)
	var bgm = BGM_GD.get_bgm(get_tree())
	_prev_track = str(bgm.current())
	bgm.play("theme", NAN, 1.5, 0, _prev_track if _prev_track != "" else "")
	_run()


func _run() -> void:
	_build_slot(0, 0)
	await get_tree().process_frame
	if from_end:
		await _fade_in_first()                    # 全剧终 → 森林：整页淡进来
	else:
		await _swap(0)                            # 标题 → 森林
	_started = true
	for i in SLIDES.size():
		if _closing:
			return
		var s := i % 2
		await _hold_slide(i, s)
		if _closing:
			return
		_leave(s)
		if (_slots[1 - s] as Dictionary).get("world") == null:
			_build_slot(1 - s, i + 1)                 # 最后一个人的下一页就是列车（END_SLIDE）
		await _swap(1 - s)
		if _closing:
			return
		_free_slot(s)
		print("CREDITS slide %d %s done" % [i, SLIDES[i]["id"]])
	if _closing:
		return
	await _play_end()
	close()


# ======================================================================= 一页
## 这一页停到该换页（名字成形 + 停够）；换页前 PREBUILD 秒把下一页建好
func _hold_slide(i: int, s: int) -> void:
	_slide = i
	var sl: Dictionary = _slots[s]
	var leave_at := FX_AT + RC.Moment.FORM_SEC + float(sl.get("hold", HOLD))
	while not _closing and float(sl.get("t", 0.0)) < leave_at:
		if float(sl.get("t", 0.0)) >= leave_at - PREBUILD and (_slots[1 - s] as Dictionary).get("world") == null:
			_build_slot(1 - s, i + 1)
		await get_tree().process_frame


## 全剧终以后：第一页直接整屏显示，整页从透明淡进来；名字晚一点开始聚（slot 的 t 从负数起）
func _fade_in_first() -> void:
	var sl: Dictionary = _slots[0]
	sl["live"] = true
	sl["t"] = FX_AT - FROM_END_IN * 0.6
	_world = sl.get("world")
	_cam = sl.get("cam")
	_stage = sl.get("stage")
	_moment = sl.get("moment")
	_shown.texture = (sl["vp"] as SubViewport).get_texture()
	modulate.a = 0.0
	await get_tree().process_frame                # SubViewport 先画一帧，别淡进来一张空图
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 1.0, FROM_END_IN).set_trans(Tween.TRANS_SINE)
	await tw.finished


func _leave(s: int) -> void:
	var m = (_slots[s] as Dictionary).get("moment")
	if m != null and is_instance_valid(m) and m.begun:
		m.leave_now(LEAVE)


## 换页：to 那一页用方格一格一格盖上来；盖满以后它就是整屏的那一页
func _swap(to: int) -> void:
	var sl: Dictionary = _slots[to]
	sl["live"] = true
	sl["t"] = 0.0
	_world = sl.get("world")
	_cam = sl.get("cam")
	_stage = sl.get("stage")
	_moment = sl.get("moment")
	_mix_tex = (sl["vp"] as SubViewport).get_texture()
	for k in STEPS:
		_mix_k = k + 1
		_mix.queue_redraw()
		await get_tree().create_timer(SWAP / STEPS).timeout
		if _closing:
			return
	_shown.texture = _mix_tex
	_mix_k = 0
	_mix.queue_redraw()


func _draw_mix() -> void:
	if _mix_k <= 0:
		return
	var cols := int(ceil(480.0 / CELL))
	var rows := int(ceil(270.0 / CELL))
	for cy in rows:
		for cx in cols:
			if absi(hash(Vector2i(cx, cy))) % STEPS < _mix_k:          # 每格第几档盖上（同一格永远同一档，和 level_forest 一样）
				var r := Rect2(cx * CELL, cy * CELL, CELL, CELL)
				_mix.draw_texture_rect_region(_mix_tex, r, r)


func _process(delta: float) -> void:
	_t += delta
	for sl in _slots:
		if not sl.get("live", false) or sl.get("world") == null:
			continue
		sl["t"] = float(sl["t"]) + delta
		var t: float = sl["t"]
		var cam: Camera2D = sl["cam"]
		cam.position = ((sl["cam_from"] as Vector2) + Vector2(float(sl["drift"]) * _ease(t / (FX_AT + RC.Moment.FORM_SEC + float(sl["hold"]) + SWAP)), 0)).round()
		var st = sl.get("stage")
		if st != null:
			st.update(delta, cam.position)
		var m = sl.get("moment")
		if m != null and is_instance_valid(m):
			if not m.begun and t >= FX_AT:
				m.begin(Vector2(240, 135), 1.0)
			if m.begun:
				m.step(delta)
	if _started and not _closing and _shown.texture == null and _mix_k == 0:
		black_frames += 1


## 最后一页：「感谢游玩」+「2026 年 11 月」，列车的车顶上面（窗外的城在暗里，字不压车厢和乘客）
func _play_end() -> void:
	_slide = SLIDES.size()
	_end_box = Control.new()
	_end_box.size = size
	_end_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_end_box.modulate.a = 0.0
	add_child(_end_box)
	var big := _label(I18n.row_text(["Thank you for playing", "感谢游玩", "Merci d’avoir joué"]), 28, Color("#d8d4cc"))
	big.position = Vector2(0, 30)
	_end_box.add_child(big)
	var small := _label(I18n.row_text(["November 2026", "2026 年 11 月", "Novembre 2026"]), 14, Color(0.62, 0.6, 0.58))
	small.position = Vector2(0, 68)
	_end_box.add_child(small)
	var tw := create_tween()
	tw.tween_property(_end_box, "modulate:a", 1.0, 1.0).set_trans(Tween.TRANS_SINE)
	var t := 0.0
	while t < 1.0 + END_HOLD and not _closing:
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
	l.add_theme_color_override("font_shadow_color", Color(0.02, 0.04, 0.035, 0.8))    # 在场景上，压一层影子
	l.add_theme_constant_override("shadow_offset_x", 1)
	l.add_theme_constant_override("shadow_offset_y", 1)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.size = Vector2(480, sz + 6)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


# ======================================================================= 场景
## 在第 s 个 SubViewport 里建第 i 页：场景 + 镜头 + 名字（名字在场景里的一层 CanvasLayer 上，换页时跟着场景一起被方格换掉）
func _build_slot(s: int, i: int) -> void:
	_free_slot(s)
	var sd: Dictionary = SLIDES[i] if i < SLIDES.size() else END_SLIDE
	var kind := str(sd["scene"])
	var cam: Vector2 = sd["cam"]
	var vp: SubViewport = _slots[s]["vp"]
	var world: Node2D
	var stage: Node2D = null
	var camera: Camera2D
	if kind in ROOMS:
		world = Node2D.new()
		stage = ROOM_GD.new()
		stage.setup(kind, null)
		world.add_child(stage)
		camera = Camera2D.new()
		world.add_child(camera)
		cam += stage.origin                          # SLIDES 里是房间坐标；小镇、芦苇地的房间在世界里不在 (0, 0)（room.json 的 origin）
	else:
		var path: String = SCENES.get(kind, "")
		if path == "" or not ResourceLoader.exists(path):
			push_warning("credits_page：场景 %s 找不到" % path)
			world = Node2D.new()
		else:
			world = (load(path) as PackedScene).instantiate()
			world.set_script(null)                   # 小样的根脚本读命令行（--shot= 会存图退出）、管晨和镜头：这里不要
		for n in HIDE:
			var c := world.get_node_or_null(n)
			if c != null:
				(c as CanvasItem).visible = false
				c.process_mode = Node.PROCESS_MODE_DISABLED
		camera = world.get_node_or_null("Camera") as Camera2D
		if camera == null:
			camera = Camera2D.new()
			world.add_child(camera)
	vp.add_child(world)
	camera.position = cam
	camera.make_current()
	if stage != null:
		stage.update(0.0, cam)
	var names := CanvasLayer.new()
	names.layer = NAMES_LAYER
	world.add_child(names)
	var m := _make_moment(sd)
	if m != null:
		names.add_child(m)
	_slots[s] = {"vp": vp, "world": world, "cam": camera, "stage": stage, "cam_from": cam, "moment": m, "t": 0.0, "live": false,
		"hold": float(sd.get("hold", HOLD)), "drift": float(sd.get("drift", DRIFT))}


func _make_moment(sd: Dictionary) -> Node2D:
	if not sd.has("id"):
		return null                                 # 最后那页：没有名字
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
	m.pace = 1.0                                # pace 是奔跑片头赶时间用的；这里每页时间够
	m.position = (sd["at"] as Vector2).round()
	return m


func _free_slot(s: int) -> void:
	var sl: Dictionary = _slots[s]
	var w = sl.get("world")
	if w != null and is_instance_valid(w):
		w.queue_free()
	_slots[s] = {"vp": sl["vp"]}


func _clear() -> void:
	for s in 2:
		_free_slot(s)


# ======================================================================= 输入、关
## level_forest 的 _input 把事件先交给这里；返回 true = 吃掉了
func handle(event: InputEvent) -> bool:
	if not from_end and event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE:
		close()                                     # 从菜单点进来的才能退回菜单；别的都不跳（11-06 作者：制作人员不能跳）
	return true


func close() -> void:
	if _closing:
		return
	_closing = true
	print("CREDITS close page=%.1fs" % _t)
	var bgm = BGM_GD.get_bgm(get_tree())
	if from_end:                                  # 全剧终以后：整屏淡到黑、音乐一起淡掉，黑着等回标题
		bgm.stop(FROM_END_OUT + 4.4)              # 比画面淡得久：标题的鸟叫淡进来时音乐还没完（level_forest._title_fade_in），不留真空
		var veil := ColorRect.new()
		veil.color = Color(0, 0, 0, 0)
		veil.size = size
		veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(veil)
		var vt := create_tween()
		vt.tween_property(veil, "color:a", 1.0, FROM_END_OUT).set_trans(Tween.TRANS_SINE)
		vt.tween_interval(0.2)
		vt.tween_callback(func():
			_clear()
			closed.emit())
		return
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
				"glint":                                                        # 月光路的碎光：一行行、从左往右一闪一闪亮起来
					var fy := (tg.y - _box.position.y) / maxf(1.0, _box.size.y)
					_delay[i] = 0.25 + 1.5 * clampf(fx * 0.5 + fy * 0.5 + _rng.randf_range(-0.12, 0.12), 0.0, 1.0)
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
			var p := _box.get_center() + Vector2(v.x * (_box.size.x / 2.0 + 70.0), v.y * maxf(16.0, _box.size.y / 2.0 + 8.0) + 8.0)
			var bl := pow(0.5 + 0.5 * sin(_t * (1.3 + float(x[2])) + float(x[1])), 3.0)
			var a := ea * bl * 0.8
			if a > 0.03:
				draw_rect(Rect2(p.round(), Vector2(3 + int(float(x[2]) * 3.0), 1)), Color(GLINT, a))
