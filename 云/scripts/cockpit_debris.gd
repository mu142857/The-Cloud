extends Control
## 剧本步骤 debris_steer（躲碎石）：{"do": "debris_steer", "id": "flight1_debris", "sec": 40, "fuel_per_bump": 1, "fuel_max_loss": 5}
## 约定见 docs/flight_sky_contract.md「debris_steer 改成上下躲」（10-29 作者定：游戏是侧视剖面、机头朝左，左右键像「前后」，
##   所以不再左右偏航，改成整艘船上下挪）。零门槛、不会失败、不显示倒计时、不标燃料。
##   碎石在船外背景里看得见地飞过来：从屏幕左边（机头方向）进来、往右飞过船。每一波走「上」或「下」一条道：
##     上道 = 贴着船身上沿（碎石中心在主船身上沿往里 LANE_IN 像素），下道 = 贴着下沿。不挪就撞上；往另一边挪开（约 20 像素以上），
##     碎石就从船上面 / 下面擦过去（碎石画在 cockpit.debris_layer：背景前、船后）。多半换一条道来。
##   预告：碎石擦到船之前 WARN（2）秒，左边那个高度上先出现一道划痕（两行虚线，越来越长、一闪一闪、往右 4 档变淡）
##     + 一个远远的小影子（3 → 7 像素，左上一点亮边），同时响一声（nav_beep：上道音高一点、下道低一点）；
##     碎石进屏幕时再「呼」一声（debris_pass_l）。10-29 验收时原来的 3×1 淡点在暗云上看不见，加粗加亮了。
##   玩家：↑ / ↓、W / S 按住让船上下挪；鼠标 / 触屏按住屏幕上半边 / 下半边一样。
##     按住时目标位置 cockpit.ship_goal 每秒走 MOVE 像素（最多 ±SHIFT）；船本身（cockpit.ship_dy）用弹簧追目标
##     （cockpit_room._ship_step：先缓起、再缓停、停下 1 像素回弹，不是匀速平移），挪动时船身周围亮起反重力泛光（scripts/ship_glow.gd）。
##     松手后目标留在原位，1.5 秒没按以后很慢地回中间（BACK 像素 / 秒）。
##     船挪 = level_forest.gd 的镜头反向偏移（晨、室内、物件一起动，背景不动）；步骤结束后 cockpit 自己慢慢回 0。
##   碰撞：碎石的图实际多大就按多大（四边各缩 2 像素）对 cockpit.hull() 的船身轮廓（每列上下沿 + 船现在的 ship_y）。
##   撞到：镜头晃一下 + 一声闷响（debris_bump），碎石弹开、4 档淡出；左上角燃料少 fuel_per_bump（整段最多 fuel_max_loss，
##     --story_check 核对：扣满以后放任何一件纪念品也补得上）；晨第 1、3、5 次撞时小声说一句（不锁人）。
##   提示「↑ ↓  躲开碎石」：第一次按键以后或者 7 秒后淡出。总时长 = sec（最后 4 秒不再来新的，最后一块飞出屏幕再结束）。
##   结束：撞了几次写进 StoryState 的物件状态（键 = id 去掉 _debris 再加 _bumps，flight1_debris → flight1_bumps），
##     不管结果如何都接着播剧情；打一行 COCKPIT 日志。
## 镜头拉远（10-30 作者：「躲避石头的时候飞船能不能缩小一点」「切远景……我觉得只是缩小」）：
##   一开始镜头从剖面拉远到船外（cockpit_room.far_out：外壳淡入 → 缓缓缩小，约 1.7 秒），整艘船变成 far_scale 倍（默认 FAR_K），
##   晨和舱里看不见；最后一块碎石飞走以后船先回中间（弹簧 + 泛光），再拉回剖面（倒着走同一条曲线），然后才接着播剧情。
##   远景里船小了：能挪 ±FAR_SHIFT（剖面里 ±SHIFT）、按住时目标每秒走 FAR_MOVE；碎石飞得慢一点（ROCK_V × (0.5 + 0.5 × 倍数)，
##   镜头远了，看起来就慢）；道、碰撞、预告都按远景船的轮廓（cockpit.far_hull()）算。碎石图不缩（相对小船更大、更看得清）。
##   剧本参数 "far_scale"：0.55 ～ 0.93（取最接近的一档图）；1 = 不拉远，留在剖面里躲（原来的样子）。
##   命令行 --far_scale=0.75 临时盖过剧本（截图对比用）；--debris_full：自动玩也按真实时长和拉远速度播（截图 / 拍联系表用）。图不在（还没生成 ship_out/）时也留在剖面里。
## 自动玩（--story_auto）：每波预告一出就往另一边挪，连拉远拉回 8 秒以内播完；跳节拍（ff）：瞬间完成、0 次、直接回剖面；
##   F8 自测：dev_skip 直接做完（直接回剖面）。
## 碎石图：art/cockpit/debris_a..e.png（tools/sky_art.py 生成，13～28 像素，暗色、左上亮边）；debris_f / g（< 8 像素）
##   当跟着飞的碎屑，不算碰撞；没有就用飞行测试的石头 / 程序画的占位。
## story_runner.gd 的 _cockpit_step 建它（挂在对话界面下，按键先到这里）：await play(runner, st)。

signal done

const ROCKS := ["res://art/flight/rock_a.png", "res://art/flight/rock_b.png", "res://art/flight/rock_c.png"]
const SHIFT := 28.0           # 船上下最多挪多少像素
const MOVE := 72.0            # 按住时每秒挪多少像素
const BACK := 3.0             # 松手 1.5 秒以后每秒慢慢回中间多少像素
const WARN := 2.0             # 预告比碎石擦到船早多少秒
const ROCK_V := 210.0         # 碎石往右飞的速度（像素 / 秒）
const LANE_IN := 6.0          # 碎石中心在主船身上沿 / 下沿往里多少像素
const FAR_K := 0.65           # 默认拉远到几倍（作者挑：0.75 / 0.65 / 0.55）
const FAR_SHIFT := 40.0       # 远景里船上下最多挪多少像素
const FAR_TOP := 40.0         # 往上挪满时尾翼尖最高到屏幕 y 多少（上面 0..34 是燃料栏）
const FAR_MOVE := 100.0       # 远景里按住时目标每秒走多少像素
const END_WAIT := 0.7         # 最后一块飞走以后，船先回中间（弹簧约 0.6 秒停稳）再拉回剖面
const TXT := {
	"hint": ["↑ ↓  Dodge the debris", "↑ ↓  躲开碎石"],
}
const BUMP_LINES := [
	{"zh": "……稳住。", "en": "...Steady.", "added": true},
	{"zh": "哎。没事。", "en": "Ugh. It's fine.", "added": true},
	{"zh": "这儿也有石头。", "en": "Rocks here too.", "added": true},
]

var runner: Node
var cockpit: Node2D
var level: Node2D
var sec := 40.0
var bumps := 0
var waves_n := 0
var _t := 0.0
var _push := 0.0              # 鼠标 / 触屏按住的方向（-1 上 / +1 下）
var _idle := 0.0              # 多久没按了
var _waves: Array = []        # {lane（-1 上 / +1 下）, t0, at（擦到船的时刻）, x, y, spr, bits, state（warn / fly / hit / pass）, ...}
var _next_wave := 3.0
var _rng := RandomNumberGenerator.new()
var _fx: Node2D               # 预告的划痕 + 小影子（画在 cockpit.debris_layer 里）
var _hint: Label
var _said := 0
var _auto := false
var _finished := false
var _rock_tex: Array = []     # 碎石（算碰撞）
var _bit_tex: Array = []      # 碎屑（小于 8 像素，跟着飞、不算碰撞）
var _hull := {}
var _fuel_per := 0            # 每撞一下扣多少燃料
var _fuel_left := 0           # 这一段还能扣多少
var _far := false             # 拉远到船外了
var _shift := SHIFT
var _move := MOVE
var _rock_v := ROCK_V
var _zoom_sec := 1.7          # 拉远 / 拉回各多少秒
var _ending := false          # 碎石都过去了：船回中间 → 拉回剖面
var _end_t := 0.0
var _back_in := false
var _real := false            # --debris_full


func play(r: Node, st: Dictionary) -> String:
	runner = r
	level = r.level
	cockpit = r.world.cockpit
	sec = maxf(6.0, float(st.get("sec", 40.0)))
	var key := str(st.get("bumps_key", str(st.get("id", "debris")).trim_suffix("_debris") + "_bumps"))
	if r.ff or cockpit == null:
		StoryState.set_prop(key, "0")
		return ""
	_fuel_per = maxi(0, int(st.get("fuel_per_bump", 0)))
	_fuel_left = maxi(0, int(st.get("fuel_max_loss", 0)))
	_auto = r.auto != ""
	_real = "--debris_full" in OS.get_cmdline_user_args()   # 截图用：自动玩也按真实时长、真实拉远速度播
	var real := _real
	if _auto and not real:
		sec = minf(sec, 5.4)                       # + 拉回 ≈ 7 秒
	var k := float(st.get("far_scale", FAR_K))
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--far_scale="):
			k = float(a.trim_prefix("--far_scale="))
	_far = k < 0.99 and cockpit.far_ready(k)
	if _far:
		_zoom_sec = 1.2 if _auto and not real else float(cockpit.FAR_SEC)
		cockpit.far_out(k, _zoom_sec)
		_shift = minf(FAR_SHIFT, floorf(cockpit.far_used_rect().position.y - FAR_TOP))   # 大的那档往上挪满时尾翼别碰燃料栏
		_move = FAR_MOVE
		_rock_v = ROCK_V * (0.5 + 0.5 * cockpit.far_k)
	_rng.seed = 23
	for n in ["debris_a", "debris_b", "debris_c", "debris_d", "debris_e", "debris_f", "debris_g"]:   # 美术给的碎石（art/cockpit/）
		var t: Texture2D = cockpit.art(n)
		if t == null:
			continue
		if t.get_height() >= 8 and t.get_width() >= 8:
			_rock_tex.append(t)
		else:
			_bit_tex.append(t)
	if _rock_tex.is_empty():
		for p in ROCKS:
			if ResourceLoader.exists(p):
				_rock_tex.append(load(p))
	_hull = cockpit.far_hull() if _far else cockpit.hull()
	_next_wave = (1.3 if _far else 0.8) if _auto and not real else 3.0
	_build()
	await done
	StoryState.set_prop(key, str(bumps))
	cockpit.steering = false
	if _far and cockpit.far_u() > 0.0:
		cockpit.far_snap(false)
	if is_instance_valid(_fx):
		_fx.queue_free()
	for w in _waves:
		_free_wave(w)
	print("COCKPIT debris_steer %s: bumps=%d waves=%d time=%.1fs" % [str(st.get("id", "")), bumps, waves_n, _t])
	return ""


## 波次间隔的缩放：sec 短（自动玩 8 秒）就来得密一点
func _pace() -> float:
	return clampf(sec / 40.0, 0.7, 1.0)          # 两波至少隔 2.8 秒：上一块还在船边上时下一块不会从另一边来


func _build() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	cockpit.steering = true
	_fx = Node2D.new()
	_fx.name = "DebrisWarn"
	_fx.draw.connect(_draw_fx)
	cockpit.debris_layer.add_child(_fx)
	_hint = Label.new()
	_hint.text = _tx("hint")
	_hint.add_theme_font_size_override("font_size", 14)
	_hint.add_theme_color_override("font_color", UITheme.TEXT_DIM)
	_hint.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.8))
	_hint.add_theme_constant_override("shadow_offset_x", 0)
	_hint.add_theme_constant_override("shadow_offset_y", 1)
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint.size = Vector2(480, 16)
	_hint.position = Vector2(0, 246)            # 船身下沿往下挪满（206 + 28）以后也碰不到
	_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hint.modulate.a = 0.0
	add_child(_hint)
	create_tween().tween_property(_hint, "modulate:a", 0.85, 0.6)
	runner._sfx({"name": "flight_rumble", "db": -14.0})


static func _tx(k: String) -> String:
	var row: Array = TXT[k]
	return row[1] if I18n.is_zh() else row[0]


func _process(delta: float) -> void:
	if _finished:
		return
	if runner.ff:
		dev_skip()
		return
	_t += delta
	if _ending:
		_end_step(delta)
		return
	# ---- 船上下挪
	var dir := 0.0
	if _auto:
		var goal := _auto_goal()
		if absf(goal - cockpit.ship_goal) > 0.5:
			dir = signf(goal - cockpit.ship_goal)
	else:
		dir = Input.get_axis("ui_up", "ui_down")
		if Input.is_key_pressed(KEY_W):
			dir -= 1.0
		if Input.is_key_pressed(KEY_S):
			dir += 1.0
		if dir == 0.0:
			dir = _push
		dir = clampf(dir, -1.0, 1.0)
	# 按住：目标位置 ship_goal 匀速走（最多 ±SHIFT），船本身用弹簧追它（cockpit_room._ship_step：缓起缓停、1 像素回弹）
	if dir != 0.0:
		_idle = 0.0
		cockpit.ship_goal = clampf(cockpit.ship_goal + dir * _move * delta, -_shift, _shift)
		if _t > 0.6:
			_hint_out()
	else:
		_idle += delta
		if _idle > 1.5:
			cockpit.ship_goal = move_toward(cockpit.ship_goal, 0.0, BACK * delta)
	if _t > 7.0:
		_hint_out()
	# ---- 碎石
	if _t >= _next_wave and _t < sec - 4.0:
		var lane := -1 if _rng.randf() < 0.5 else 1
		if not _waves.is_empty() and _rng.randf() < 0.7:
			lane = -int(_waves[-1]["lane"])          # 多半换一条道来
		_new_wave(lane)
		_next_wave = _t + _rng.randf_range(4.0, 5.6) * _pace()
	var flying := false
	for w in _waves:
		_update_wave(w, delta)
		if str(w["state"]) != "gone":
			flying = true
	_fx.queue_redraw()
	if (_t >= sec and not flying) or _t > sec + 6.0:
		_finish()


## 自动玩：最早一块还没飞过船尾的碎石在哪条道，就往另一边挪
func _auto_goal() -> float:
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	var x1 := float(int(_hull.get("x0", 80)) + tops.size())
	for w in _waves:
		if str(w["state"]) in ["warn", "fly"] and float(w["x"]) - (w["size"] as Vector2).x / 2.0 < x1:
			return -float(w["lane"]) * _shift
	return cockpit.ship_goal


func _hint_out() -> void:
	if _hint.get_meta("out", false):
		return
	_hint.set_meta("out", true)
	create_tween().tween_property(_hint, "modulate:a", 0.0, 1.2)


func _new_wave(lane: int) -> void:
	waves_n += 1
	var spr := Sprite2D.new()
	spr.centered = true
	if not _rock_tex.is_empty():
		spr.texture = _rock_tex[_rng.randi() % _rock_tex.size()]
	else:
		spr.texture = Inventory.placeholder("rock", Color("#2a2f2c"), 20, 16)
	spr.flip_h = _rng.randf() < 0.5
	spr.visible = false
	cockpit.debris_layer.add_child(spr)
	var sz := spr.texture.get_size()
	var top := float(_hull.get("T", 100))
	var bot := float(_hull.get("B", 206))
	# 碎石中心：主船身上沿 / 下沿往里 LANE_IN（碎石特别大时往外让一点，保证挪满 SHIFT 一定躲得开）
	var inset := minf(LANE_IN, _shift - sz.y / 2.0 - 4.0)
	var y := roundf(top + inset if lane < 0 else bot - inset)
	# 碎石右边沿在 WARN 秒后碰到这条道上船身最左边那一列
	var cx := _front_x(y - sz.y / 2.0 + 2.0, y + sz.y / 2.0 - 2.0)
	var w := {"lane": lane, "t0": _t, "at": _t + WARN, "y": y, "spr": spr, "size": sz, "state": "warn",
		"x": cx - sz.x / 2.0 - _rock_v * WARN, "vx": _rock_v, "vy": 0.0, "hit_t": 0.0, "bits": [], "pass_sfx": false}
	# 跟着飞的小碎屑（不算碰撞）
	for i in _rng.randi_range(1, 2):
		var b := Sprite2D.new()
		b.centered = true
		if not _bit_tex.is_empty():
			b.texture = _bit_tex[_rng.randi() % _bit_tex.size()]
		else:
			b.texture = Inventory.placeholder("bit", Color("#2a2f2c"), 3, 3)
		b.visible = false
		cockpit.debris_layer.add_child(b)
		(w["bits"] as Array).append({"spr": b, "dx": -_rng.randf_range(16.0, 40.0), "dy": _rng.randf_range(-9.0, 9.0)})
	_waves.append(w)
	_play("nav_beep", -14.0, 1.25 if lane < 0 else 0.85)


## 这条道（屏幕 y0..y1，船没挪的时候）上船身最左边那一列的屏幕 x
func _front_x(y0: float, y1: float) -> float:
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	var bots: PackedInt32Array = _hull.get("bot", PackedInt32Array())
	var x0 := int(_hull.get("x0", 80))
	for i in tops.size():
		if tops[i] >= 0 and float(tops[i]) < y1 and float(bots[i]) > y0:
			return float(x0 + i)
	return float(x0 + 40)


## 碎石（屏幕矩形）现在碰没碰到船身
func _touches(r: Rect2) -> bool:
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	var bots: PackedInt32Array = _hull.get("bot", PackedInt32Array())
	var x0 := int(_hull.get("x0", 80))
	var sy: float = cockpit.ship_y()
	var i0 := maxi(0, int(floorf(r.position.x)) - x0)
	var i1 := mini(tops.size() - 1, int(ceilf(r.end.x)) - x0)
	for i in range(i0, i1 + 1):
		if tops[i] >= 0 and float(tops[i]) + sy < r.end.y and float(bots[i]) + sy > r.position.y:
			return true
	return false


func _update_wave(w: Dictionary, delta: float) -> void:
	var st := str(w["state"])
	if st == "gone":
		return
	var spr: Sprite2D = w["spr"]
	var sz: Vector2 = w["size"]
	w["x"] = float(w["x"]) + float(w["vx"]) * delta
	w["y"] = float(w["y"]) + float(w["vy"]) * delta
	var x := float(w["x"])
	var y := float(w["y"])
	if st == "warn" and x + sz.x / 2.0 > -2.0:
		w["state"] = "fly"
		st = "fly"
		_play("debris_pass_l", -12.0)
	spr.visible = st != "warn"
	spr.position = Vector2(roundf(x), roundf(y))
	for b in w["bits"]:
		var bs: Sprite2D = b["spr"]
		bs.visible = spr.visible and st != "hit"
		bs.position = Vector2(roundf(x + float(b["dx"])), roundf(y + float(b["dy"])))
	if st == "fly":
		var r := Rect2(x - sz.x / 2.0 + 2.0, y - sz.y / 2.0 + 2.0, maxf(1.0, sz.x - 4.0), maxf(1.0, sz.y - 4.0))
		if _touches(r):
			_bump(w)
		elif _t >= float(w["at"]) and not w["pass_sfx"]:
			w["pass_sfx"] = true                   # 擦过去了
			runner._sfx({"name": "ship_whoosh", "db": -16.0})
	elif st == "hit":
		w["hit_t"] = float(w["hit_t"]) + delta
		w["vy"] = float(w["vy"]) * 0.97
		var k := clampf(float(w["hit_t"]) / 0.5, 0.0, 1.0)
		spr.modulate.a = 1.0 - floorf(k * 4.0) / 4.0
		if k >= 1.0:
			_free_wave(w)
			return
	if x - sz.x / 2.0 > 480.0 + 50.0:
		_free_wave(w)


func _free_wave(w: Dictionary) -> void:
	w["state"] = "gone"
	if is_instance_valid(w["spr"]):
		(w["spr"] as Node).queue_free()
	for b in w["bits"]:
		if is_instance_valid(b["spr"]):
			(b["spr"] as Node).queue_free()


func _bump(w: Dictionary) -> void:
	w["state"] = "hit"
	w["vx"] = 90.0                                   # 弹开：慢下来、往外翻
	w["vy"] = 70.0 * float(w["lane"])
	bumps += 1
	level._shake = 0.35
	level._shake_amp = 2.0
	_play("debris_bump", -4.0)
	if _fuel_per > 0 and _fuel_left > 0 and StoryState.fuel_on():
		var n := mini(_fuel_per, _fuel_left)
		_fuel_left -= n
		var was := StoryState.fuel()
		StoryState.set_fuel(was - n)
		level.fuel_changed(was, StoryState.fuel_need())
	# 晨偶尔说一句（第 1、3、5 次撞，最多三句；不锁人）
	if bumps % 2 == 1 and _said < BUMP_LINES.size() and not _auto:
		var l: Dictionary = BUMP_LINES[_said]
		_said += 1
		var tl: Array = runner.txt_lang(l)
		var anchor: Callable = cockpit.far_anchor if _far else runner._anchor.bind("chen")   # 远景里晨看不见：从船窗上方冒
		runner.dlg.murmur(runner.txt_in(runner.speakers.get("chen", "chen"), str(tl[1])), runner.NAME_COLORS["chen"], str(tl[0]),
			anchor, runner.mark_added)


## 音效（能调音高；缺文件静默跳过，和 runner._sfx 一样记进统计）
func _play(snd: String, db: float, pitch := 1.0) -> void:
	if runner.ff:
		return
	var p: String = runner._sfx_path(snd)
	if p == "":
		runner.missing_sfx[snd] = true
		return
	var a := AudioStreamPlayer.new()
	a.stream = load(p)
	a.bus = "SFX"
	a.volume_db = db
	a.pitch_scale = pitch
	level.add_child(a)
	a.play()
	a.finished.connect(a.queue_free)


## F8 自测 / 跳节拍：直接做完，镜头直接回剖面
func dev_skip() -> void:
	if _finished:
		return
	if _far:
		cockpit.far_snap(false)
	cockpit.ship_goal = 0.0
	_done()


## 碎石都过去了：没拉远就直接结束；拉远了先让船回中间（弹簧 + 泛光），END_WAIT 秒后拉回剖面，拉完才结束
func _finish() -> void:
	if _finished or _ending:
		return
	_hint_out()
	if not _far:
		_done()
		return
	_ending = true
	_end_t = 0.0
	cockpit.ship_goal = 0.0


func _end_step(delta: float) -> void:
	_end_t += delta
	cockpit.ship_goal = 0.0
	for w in _waves:
		_update_wave(w, delta)
	_fx.queue_redraw()
	if not _back_in and _end_t >= (0.2 if _auto and not _real else END_WAIT):
		_back_in = true
		cockpit.far_in(_zoom_sec)
	if _back_in and cockpit.far_u() <= 0.0:
		_done()


func _done() -> void:
	if _finished:
		return
	_finished = true
	_hint_out()
	done.emit()


## 预告：碎石那条道的高度上，屏幕左边一道划痕（越来越长、一闪一闪，往右一格一格变淡）+ 一个远远的小影子（越来越大，左上一点亮边）。
## 10-29 验收：原来 3×1 的点、透明度 .25～.5，在暗云上几乎看不见 → 加粗加亮（仍比碎石本身淡）。
func _draw_fx() -> void:
	for w in _waves:
		if str(w["state"]) != "warn":
			continue
		var k := clampf((_t - float(w["t0"])) / WARN, 0.0, 1.0)
		var y := roundf(float(w["y"]))
		var a := 0.75 if int(_t * 6.0) % 2 == 0 else 0.5
		var ln := roundf(14.0 + 60.0 * k)
		var x := 0.0
		while x < ln:
			var f := floorf((1.0 - x / (ln + 10.0)) * 4.0) / 4.0          # 往右 4 档变淡
			_fx.draw_rect(Rect2(x, y, 4, 1), Color(0.78, 0.9, 0.84, a * f))
			_fx.draw_rect(Rect2(x + 2, y + 1, 3, 1), Color(0.78, 0.9, 0.84, a * f * 0.5))   # 下面一道淡的，划痕厚一点
			x += 6.0
		var s := 3.0 + floorf(k * 4.0)                                    # 小影子 3 → 7 像素
		var sx := roundf(6.0 + 14.0 * k)
		var r := Rect2(sx, y - floorf(s / 2.0), s, s - 1.0)
		_fx.draw_rect(r, Color(0.07, 0.09, 0.08, 0.9))
		_fx.draw_rect(Rect2(r.position, Vector2(s - 1.0, 1.0)), Color(0.78, 0.86, 0.8, a))
		_fx.draw_rect(Rect2(r.position, Vector2(1.0, s - 2.0)), Color(0.78, 0.86, 0.8, a))


# ======================================================================= 输入（鼠标 / 触屏按住上下半边；键盘在 _process 里直接读）
func _input(event: InputEvent) -> void:
	if _finished or _auto:
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		_push = (-1.0 if event.position.y < 135.0 else 1.0) if event.pressed else 0.0
		get_viewport().set_input_as_handled()
	elif event is InputEventScreenTouch:
		_push = (-1.0 if event.position.y < 135.0 else 1.0) if event.pressed else 0.0
		get_viewport().set_input_as_handled()
	elif event is InputEventMouseMotion and _push != 0.0:
		_push = -1.0 if event.position.y < 135.0 else 1.0
