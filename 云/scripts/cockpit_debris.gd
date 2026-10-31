extends Control
## 剧本步骤 debris_steer（躲碎石）：{"do": "debris_steer", "id": "flight1_debris", "sec": 40, "fuel_per_bump": 1, "fuel_max_loss": 5}
## 约定见 docs/flight_sky_contract.md「debris_steer 改成上下躲」（10-29 作者定：游戏是侧视剖面、机头朝左，左右键像「前后」，
##   所以不再左右偏航，改成整艘船上下挪）。零门槛、不会失败、不显示倒计时、不标燃料。
##   碎石在船外背景里看得见地飞过来：从屏幕左边（机头方向）进来、往右飞过船（画在 cockpit.debris_layer：背景前、船后）。
## 10-30 改成一段有节奏、有变化的「波次」（作者：「小游戏也乏味」）：固定的一串波次（PLAN，按 sec / 40 缩放），每波都有一条安全通道
##   （船挪到哪个位置躲得开 = safe，单位是船的上下偏移，±_shift 以内）：
##     one   一块，贴着船身上沿（上道）或下沿（下道）：往另一边挪满就躲开（上道 → safe = +_shift）
##     pair  同一条道连着两块（「哒哒」），挪一次躲两块
##     gap   一排碎石竖着排成墙，中间留一道缝：缝 = 船挪到 safe 时船身上下各留 GAP_M 像素；墙从缝往上、往下一直排到屏幕边
##     final 结尾一波大的：GAP 墙连着三排、缝一排排换位置（蛇形），碎石更多、轰隆声更大；最后一排过去以后「穿出去」（_breakout）
##   顺序：上 → 下 → 上道两块 → 中间的缝 → 上下交替三块 → 偏上的缝 → 结尾三排（缝下、中、上蛇形）。两波换道之间至少隔 2.8 秒
##   （上一波还在船边上时下一波不会逼你往它那边挪）。
##   找通道（剧情姐原文：「根据碎石靠近的方位声和稳定的气流声寻找通道」）：
##     方位声：预告时响一声 nav_beep（碎石在上面音高高、在下面音低；一排墙响两声），碎石进屏幕「呼」一声从左边来（debris_pass_l，声像偏左），
##       擦过船以后往右走（debris_pass_r，声像偏右）。
##     气流声：有碎石来的时候一直有稳定的气流声（airflow_loop），音高跟着安全通道的高低（通道在上面音高）；
##       画面上安全通道那个高度、机头前面有几道淡淡的气流线往船这边流（AIR_C，很淡，不闪；碎石的划痕会闪）。
##   预告：碎石擦到船之前 WARN（2）秒，左边那个高度上先出现一道划痕（两行虚线，越来越长、一闪一闪、往右 4 档变淡）
##     + 一个远远的小影子（3 → 7 像素，左上一点亮边）。墙只给离船近的那两块画划痕（其余的只是墙）。
##   擦边：碎石飞过船身、离船身不到 GRAZE 像素又没碰到 → 船外泛光闪一下（ship_glow 光强拉满再按原来的速度熄）+ 擦边的几颗火星 + 一声轻的「咻」。
##   玩家：↑ / ↓、W / S 按住让船上下挪；鼠标 / 触屏按住屏幕上半边 / 下半边一样。
##     按住时目标位置 cockpit.ship_goal 每秒走 _move 像素（最多 ±_shift）；船本身（cockpit.ship_dy）用弹簧追目标
##     （cockpit_room._ship_step：先缓起、再缓停、停下 1 像素回弹，不是匀速平移），挪动时船身周围亮起反重力泛光（scripts/ship_glow.gd）。
##     松手后目标留在原位，1.5 秒没按以后很慢地回中间（BACK 像素 / 秒）。
##     船挪 = level_forest.gd 的镜头反向偏移（晨、室内、物件一起动，背景不动）；步骤结束后 cockpit 自己慢慢回 0。
##   碰撞：碎石的图实际多大就按多大（四边各缩 2 像素）对 cockpit.hull() 的船身轮廓（每列上下沿 + 船现在的 ship_y）。
##   撞到：镜头晃一下 + 一声闷响（debris_bump），碎石弹开、4 档淡出；同一波（一排墙）只算一次：左上角燃料少 fuel_per_bump
##     （整段最多 fuel_max_loss，--story_check 核对：扣满以后放任何一件纪念品也补得上）；晨第 1、3、5 次撞时小声说一句（不锁人）。
##     不会输、没有命：撞了就晃一下，接着飞。
##   提示「↑ ↓  躲开碎石」：第一次按键以后或者 7 秒后淡出。
##   结束：撞了几次写进 StoryState 的物件状态（键 = id 去掉 _debris 再加 _bumps，flight1_debris → flight1_bumps），
##     不管结果如何都接着播剧情；打一行 COCKPIT 日志。
## 镜头拉远（10-30 作者：「躲避石头的时候飞船能不能缩小一点」「切远景……我觉得只是缩小」）：
##   一开始镜头从剖面拉远到船外（cockpit_room.far_out：外壳淡入 → 缓缓缩小，约 1.7 秒），整艘船变成 far_scale 倍（默认 FAR_K），
##   晨和舱里看不见；最后一排碎石过去、穿出去以后船先回中间（弹簧 + 泛光），再拉回剖面（倒着走同一条曲线），然后才接着播剧情。
##   10-31（作者：「正中间提前量有点不够」）：缩小的同时往右平移，停在屏幕宽度 FAR_X（73%，x 350）；碎石再慢 FAR_SLOW，
##   预告 = 进画面前 WARN_OFF 秒 + 从屏幕左边飞到船头的时间 → 进画面到撞上船头约 1.65 秒（原来约 0.8）。剧本 "far_x" / 命令行 --far_x= 能改。
##   远景里船小了：能挪 ±FAR_SHIFT（剖面里 ±SHIFT）、按住时目标每秒走 FAR_MOVE；碎石飞得慢一点（ROCK_V × (0.5 + 0.5 × 倍数)，
##   镜头远了，看起来就慢）；道、缝、碰撞、预告都按远景船的轮廓（cockpit.far_hull()）算。碎石图不缩（相对小船更大、更看得清）。
##   剧本参数 "far_scale"：0.55 ～ 0.93（取最接近的一档图）；1 = 不拉远，留在剖面里躲（原来的样子）。
##   命令行 --far_scale=0.75 临时盖过剧本（截图对比用）；--debris_full：自动玩也按真实时长和拉远速度播（截图 / 拍联系表用）。图不在（还没生成 ship_out/）时也留在剖面里。
## 自动玩（--story_auto）：每波预告一出就挪到它的安全通道（最早一波还没飞过船尾的那波），只播 PLAN_AUTO 两波，连拉远拉回 9 秒以内；
##   跳节拍（ff）：瞬间完成、0 次、直接回剖面；F8 自测：dev_skip 直接做完（直接回剖面）。
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
const GAP_M := 10.0           # 墙的缝：船挪到 safe 时船身上下各留多少像素
const GRAZE := 6.0            # 离船身不到这么多像素算擦边
const FAR_K := 0.65           # 默认拉远到几倍（作者挑：0.75 / 0.65 / 0.55）
const FAR_SHIFT := 40.0       # 远景里船上下最多挪多少像素
const FAR_TOP := 40.0         # 往上挪满时尾翼尖最高到屏幕 y 多少（上面 0..34 是燃料栏）
const FAR_MOVE := 100.0       # 远景里按住时目标每秒走多少像素
const END_WAIT := 0.7         # 穿出去以后，船先回中间（弹簧约 0.6 秒停稳）再拉回剖面
const FAR_X := 0.73           # 远景船停在屏幕右边：图的中线在屏幕宽度的这个比例（10-31 作者：「正中间提前量有点不够」）
const FAR_SLOW := 0.9         # 远景里碎石再慢这么多（和挪到右边一起：碎石进画面到撞上船头约 1.6 秒，原来约 0.8 秒）
const WARN_OFF := 1.2         # 远景：碎石进画面之前，左边划痕先预告多少秒（和原来船在中间时一样）
const AIR_C := Color(0.5, 0.78, 0.64)       # 气流线（#7fc7a4 一族，很淡）
const SCRATCH_C := Color(0.78, 0.9, 0.84)
const SPARK_C := Color(0.95, 0.9, 0.75)
## 波次（t = 秒，按 sec / 40 缩放；safe 见文件头）。lane：-1 上道 / +1 下道；g：缝的位置（× _shift，+ = 往下）。
## 排的时候守住：两波要换位置时，上一波过完船尾（远景约 1.3 秒）以后还要留 1 秒让船挪过去 → 换道隔 ≥ 2.8 秒，挪半程隔 ≥ 2.4 秒
const PLAN := [
	{"t": 2.6, "k": "one", "lane": -1},
	{"t": 6.4, "k": "one", "lane": 1},
	{"t": 10.2, "k": "pair", "lane": -1},
	{"t": 14.6, "k": "gap", "g": 0.0},
	{"t": 18.6, "k": "one", "lane": -1},
	{"t": 21.4, "k": "one", "lane": 1},
	{"t": 24.2, "k": "one", "lane": -1},
	{"t": 28.0, "k": "gap", "g": -0.5},
	{"t": 31.8, "k": "final", "g": [0.6, -0.1, -0.8]},
]
const PLAN_AUTO := [
	{"t": 0.0, "k": "one", "lane": -1},
	{"t": 2.7, "k": "gap", "g": 0.0},
]
const FINAL_ROW := 2.4        # 结尾那几排隔多少秒
const PAIR_DT := 0.9          # pair 两块隔多少秒
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
var grazes := 0
var _t := 0.0
var _push := 0.0              # 鼠标 / 触屏按住的方向（-1 上 / +1 下）
var _idle := 0.0              # 多久没按了
var _plan: Array = []         # 还没出的波次（PLAN 缩放过的，t 是绝对时间）
var _waves: Array = []        # {safe, at, t0, rocks: [...], bumped, kind}
var _rng := RandomNumberGenerator.new()
var _fx: Node2D               # 预告的划痕 + 小影子 + 气流线 + 擦边火星（画在 cockpit.debris_layer 里）
var _sparks: Array = []       # {p, v, age}
var _hint: Label
var _said := 0
var _auto := false
var _finished := false
var _rock_tex: Array = []     # 碎石（算碰撞）
var _bit_tex: Array = []      # 碎屑（小于 8 像素，跟着飞、不算碰撞）
var _hull := {}
var _x1 := 0.0                # 船尾（船身最右那一列）的屏幕 x
var _fuel_per := 0            # 每撞一下扣多少燃料
var _fuel_left := 0           # 这一段还能扣多少
var _far := false             # 拉远到船外了
var _shift := SHIFT
var _move := MOVE
var _rock_v := ROCK_V
var _warn := WARN             # 预告比碎石擦到船头早多少秒（远景 = WARN_OFF + 从屏幕左边飞到船头的时间）
var _ship_cx := 240.0         # 船（图的中线）在屏幕上的 x：声像、提示文字跟着它
var _lead := []               # 每块领头的碎石：进画面到碰到船头的秒数（日志）
var _zoom_sec := 1.7          # 拉远 / 拉回各多少秒
var _ending := false          # 碎石都过去了：穿出去 → 船回中间 → 拉回剖面
var _end_t := 0.0
var _back_in := false
var _real := false            # --debris_full
var _air: AudioStreamPlayer   # 稳定的气流声
var _air_on := 0.0            # 气流（声音 + 线）现在多强 0..1
var _air_g := 0.0             # 气流线 / 音高现在对着的安全通道（船的偏移，平滑跟着）


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
	var k := float(st.get("far_scale", FAR_K))
	var fx := float(st.get("far_x", FAR_X))
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--far_scale="):
			k = float(a.trim_prefix("--far_scale="))
		elif a.begins_with("--far_x="):
			fx = float(a.trim_prefix("--far_x="))
	_far = k < 0.99 and cockpit.far_ready(k)
	if _far:
		_zoom_sec = 1.2 if _auto and not real else float(cockpit.FAR_SEC)
		_ship_cx = roundf(clampf(fx, 0.5, 0.8) * 480.0)
		cockpit.far_out(k, _zoom_sec, _ship_cx)                     # 缩小的同时平移到右边（拉回时倒着走回中间）
		_shift = minf(FAR_SHIFT, floorf(cockpit.far_used_rect().position.y - FAR_TOP))   # 大的那档往上挪满时尾翼别碰燃料栏
		_move = FAR_MOVE
		_rock_v = ROCK_V * (0.5 + 0.5 * cockpit.far_k) * FAR_SLOW
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
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	_x1 = float(int(_hull.get("x0", 80)) + tops.size())
	if _far:
		_warn = WARN_OFF + (_nose() + 2.0) / _rock_v       # 碎石进画面以后飞多久到船头 + 进画面前的预告
	# 波次：真实时长按 sec / 40 缩放；自动玩只播两波（第一波等拉远差不多了再来）
	if _auto and not real:
		var t0 := 1.3 if _far else 0.8
		for w in PLAN_AUTO:
			var e: Dictionary = (w as Dictionary).duplicate()
			e["t"] = t0 + float(e["t"])
			_plan.append(e)
	else:
		var sc := clampf(sec / 40.0, 0.75, 1.5)
		for w in PLAN:
			var e: Dictionary = (w as Dictionary).duplicate()
			e["t"] = float(e["t"]) * sc
			_plan.append(e)
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
	if is_instance_valid(_air):
		_air.queue_free()
	var lead := 0.0
	for v in _lead:
		lead += float(v) / float(_lead.size())
	print("COCKPIT debris_steer %s: bumps=%d grazes=%d waves=%d time=%.1fs ship_x=%d nose=%d lead=%.2fs" % [str(st.get("id", "")), bumps,
		grazes, waves_n, _t, int(_ship_cx), int(_nose()), lead])
	return ""


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
	_hint.position = Vector2(_ship_cx - 240.0, 246)   # 在船下面（船身下沿往下挪满（206 + 28）以后也碰不到）
	_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hint.modulate.a = 0.0
	add_child(_hint)
	create_tween().tween_property(_hint, "modulate:a", 0.85, 0.6)
	_play("flight_rumble", -14.0)
	_air = _loop("airflow_loop", -60.0)


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
	_air_step(delta)
	_spark_step(delta)
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
	# 按住：目标位置 ship_goal 匀速走（最多 ±_shift），船本身用弹簧追它（cockpit_room._ship_step：缓起缓停、1 像素回弹）
	if dir != 0.0:
		_idle = 0.0
		var step := _move * delta
		if _auto:
			step = minf(step, absf(_auto_goal() - cockpit.ship_goal))
		cockpit.ship_goal = clampf(cockpit.ship_goal + dir * step, -_shift, _shift)
		if _t > 0.6:
			_hint_out()
	else:
		_idle += delta
		if _idle > 1.5 and not _auto:
			cockpit.ship_goal = move_toward(cockpit.ship_goal, 0.0, BACK * delta)
	if _t > 7.0:
		_hint_out()
	# ---- 波次
	while not _plan.is_empty() and _t >= float(_plan[0]["t"]):
		_spawn(_plan.pop_front())
	var busy := false
	for w in _waves:
		_update_wave(w, delta)
		if not _wave_clear(w):
			busy = true
	_fx.queue_redraw()
	if (_plan.is_empty() and not busy) or _t > sec * 1.5 + 10.0:
		_finish()


## 自动玩：最早一波还没飞过船尾的，挪到它的安全通道
func _auto_goal() -> float:
	for w in _waves:
		if not _wave_clear(w):
			return float(w["safe"])
	return cockpit.ship_goal


## 这一波的碎石都飞过船尾了（或者撞飞了）
func _wave_clear(w: Dictionary) -> bool:
	for r in w["rocks"]:
		var st := str(r["state"])
		if st in ["warn", "fly"] and float(r["x"]) - (r["size"] as Vector2).x / 2.0 < _x1:
			return false
	return true


func _hint_out() -> void:
	if _hint.get_meta("out", false):
		return
	_hint.set_meta("out", true)
	create_tween().tween_property(_hint, "modulate:a", 0.0, 1.2)


# ======================================================================= 出波次
func _spawn(e: Dictionary) -> void:
	match str(e["k"]):
		"one":
			_wave_lane(int(e["lane"]))
		"pair":
			_wave_lane(int(e["lane"]))
			_plan.push_front({"t": _t + PAIR_DT, "k": "one", "lane": int(e["lane"])})
		"gap":
			_wave_gap(float(e["g"]), false)
		"final":
			var gs: Array = e["g"]
			_play("nav_alert", -12.0)
			_play("flight_rumble", -6.0)
			_wave_gap(float(gs[0]), true)
			_waves[-1]["last"] = gs.size() == 1
			for i in range(1, gs.size()):
				_plan.push_front({"t": _t + FINAL_ROW * i, "k": "row", "g": float(gs[i]), "last": i == gs.size() - 1})
		"row":
			_play("flight_rumble", -9.0)
			_wave_gap(float(e["g"]), true)
			_waves[-1]["last"] = bool(e.get("last", false))
	_plan.sort_custom(func(a, b): return float(a["t"]) < float(b["t"]))


## 单块：贴着上沿（lane -1）或下沿（+1）；安全通道 = 往另一边挪满
func _wave_lane(lane: int) -> void:
	var tex := _pick_rock()
	var sz := tex.get_size()
	var top := float(_hull.get("T", 100))
	var bot := float(_hull.get("B", 206))
	# 碎石中心：主船身上沿 / 下沿往里 LANE_IN（碎石特别大时往外让一点，保证挪满 _shift 一定躲得开）
	var inset := minf(LANE_IN, _shift - sz.y / 2.0 - 4.0)
	var y := roundf(top + inset if lane < 0 else bot - inset)
	# 碎石右边沿在 _warn 秒后碰到这条道上船身最左边那一列
	var cx := _front_x(y - sz.y / 2.0 + 2.0, y + sz.y / 2.0 - 2.0)
	var w := _new_wave(-float(lane) * _shift, "one")
	_add_rock(w, tex, cx - sz.x / 2.0 - _rock_v * _warn, y, true, _rng.randi_range(1, 2))
	_beep(y)


## 一排墙，缝在 g × _shift（船挪到那里，船身上下各留 GAP_M）；big = 结尾那几排（墙更密、碎屑更多）
func _wave_gap(g: float, big: bool) -> void:
	var safe := roundf(clampf(g, -1.0, 1.0) * _shift)
	var top := float(_hull.get("T", 100)) + safe - GAP_M          # 缝的上沿 / 下沿（屏幕 y）
	var bot := float(_hull.get("B", 206)) + safe + GAP_M
	var w := _new_wave(safe, "final" if big else "gap")
	var x_hit := _nose() - _rock_v * _warn                         # 墙的右沿 _warn 秒后到机头
	# 往上：第一块的碰撞下沿正好是缝的上沿，再一块块往上摞到屏幕顶（燃料栏下面）
	var y := top
	var first := true
	var jit := 4.0 if big else 2.0
	while y > 40.0:
		var tex := _pick_rock()
		var sz := tex.get_size()
		var cy := y - (sz.y / 2.0 - 2.0)
		var dx := 0.0 if first else _rng.randf_range(-jit, jit) * 3.0
		_add_rock(w, tex, x_hit - sz.x / 2.0 + minf(0.0, dx), roundf(cy), first, (2 if big else 1) if first else (1 if big else 0))
		y = cy - sz.y / 2.0 - _rng.randf_range(1.0, 4.0 + jit)
		first = false
	y = bot
	first = true
	while y < 268.0:
		var tex := _pick_rock()
		var sz := tex.get_size()
		var cy := y + (sz.y / 2.0 - 2.0)
		var dx := 0.0 if first else _rng.randf_range(-jit, jit) * 3.0
		_add_rock(w, tex, x_hit - sz.x / 2.0 + minf(0.0, dx), roundf(cy), first, (2 if big else 1) if first else (1 if big else 0))
		y = cy + sz.y / 2.0 + _rng.randf_range(1.0, 4.0 + jit)
		first = false
	# 两声：上面的墙一声（高）、下面的墙一声（低）
	_beep(top - 8.0)
	get_tree().create_timer(0.16, false).timeout.connect(_beep.bind(bot + 8.0))


func _new_wave(safe: float, kind: String) -> Dictionary:
	waves_n += 1
	var w := {"safe": safe, "t0": _t, "at": _t + _warn, "rocks": [], "bumped": false, "kind": kind, "last": false, "out": false}
	_waves.append(w)
	return w


func _pick_rock() -> Texture2D:
	if not _rock_tex.is_empty():
		return _rock_tex[_rng.randi() % _rock_tex.size()]
	return Inventory.placeholder("rock", Color("#2a2f2c"), 20, 16)


## 一块碎石（中心 x, y）；key = 离船近、画预告划痕的那块；bits = 跟着飞几颗碎屑
func _add_rock(w: Dictionary, tex: Texture2D, x: float, y: float, key: bool, bits: int) -> void:
	var spr := Sprite2D.new()
	spr.centered = true
	spr.texture = tex
	spr.flip_h = _rng.randf() < 0.5
	spr.visible = false
	cockpit.debris_layer.add_child(spr)
	var r := {"x": x, "y": y, "spr": spr, "size": tex.get_size(), "state": "warn", "vx": _rock_v, "vy": 0.0, "hit_t": 0.0,
		"bits": [], "key": key, "grazed": false, "near": 999.0, "passed": false}
	for i in bits:
		var b := Sprite2D.new()
		b.centered = true
		if not _bit_tex.is_empty():
			b.texture = _bit_tex[_rng.randi() % _bit_tex.size()]
		else:
			b.texture = Inventory.placeholder("bit", Color("#2a2f2c"), 3, 3)
		b.visible = false
		cockpit.debris_layer.add_child(b)
		(r["bits"] as Array).append({"spr": b, "dx": -_rng.randf_range(16.0, 40.0), "dy": _rng.randf_range(-9.0, 9.0)})
	(w["rocks"] as Array).append(r)


## 方位声：碎石在船中线上面音高高、下面低（船上的仪器响：声像在船那儿）
func _beep(y: float) -> void:
	var mid := (float(_hull.get("T", 100)) + float(_hull.get("B", 206))) / 2.0
	_play("nav_beep", -14.0, 1.25 if y < mid else 0.85, _pan(_ship_cx))


## 屏幕 x → 声像（和 _play 的摆法对上：屏幕中间 0，往右 320 像素 = 1）
static func _pan(x: float) -> float:
	return clampf((x - 240.0) / 320.0, -1.0, 1.0)


## 机头（船身最左那一列）的屏幕 x
func _nose() -> float:
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	var nose := float(int(_hull.get("x0", 80)))
	for i in tops.size():
		if tops[i] >= 0:
			return nose + float(i)
	return nose


## 这条道（屏幕 y0..y1，船没挪的时候）上船身最左边那一列的屏幕 x
func _front_x(y0: float, y1: float) -> float:
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	var bots: PackedInt32Array = _hull.get("bot", PackedInt32Array())
	var x0 := int(_hull.get("x0", 80))
	for i in tops.size():
		if tops[i] >= 0 and float(tops[i]) < y1 and float(bots[i]) > y0:
			return float(x0 + i)
	return float(x0 + 40)


## 碎石（屏幕矩形）和船身的竖直间隙：< 0 = 碰到了；船身在这几列都没有 = 999
func _clearance(r: Rect2) -> float:
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	var bots: PackedInt32Array = _hull.get("bot", PackedInt32Array())
	var x0 := int(_hull.get("x0", 80))
	var sy: float = cockpit.ship_y()
	var i0 := maxi(0, int(floorf(r.position.x)) - x0)
	var i1 := mini(tops.size() - 1, int(ceilf(r.end.x)) - x0)
	var best := 999.0
	for i in range(i0, i1 + 1):
		if tops[i] < 0:
			continue
		var gap := maxf(r.position.y - (float(bots[i]) + sy), (float(tops[i]) + sy) - r.end.y)
		best = minf(best, gap)
	return best


# ======================================================================= 每帧：碎石
func _update_wave(w: Dictionary, delta: float) -> void:
	for r in w["rocks"]:
		_update_rock(w, r, delta)
	if bool(w["last"]) and not bool(w["out"]) and _wave_clear(w):
		w["out"] = true
		_breakout()


func _update_rock(w: Dictionary, r: Dictionary, delta: float) -> void:
	var st := str(r["state"])
	if st == "gone":
		return
	var spr: Sprite2D = r["spr"]
	var sz: Vector2 = r["size"]
	r["x"] = float(r["x"]) + float(r["vx"]) * delta
	r["y"] = float(r["y"]) + float(r["vy"]) * delta
	var x := float(r["x"])
	var y := float(r["y"])
	if st == "warn" and x + sz.x / 2.0 > -2.0:
		r["state"] = "fly"
		st = "fly"
		if r["key"]:
			_lead.append(float(w["at"]) - _t)
			_play("debris_pass_l", -12.0 if w["kind"] == "one" else -10.0, 1.0, -0.7)
	spr.visible = st != "warn"
	spr.position = Vector2(roundf(x), roundf(y))
	for b in r["bits"]:
		var bs: Sprite2D = b["spr"]
		bs.visible = spr.visible and st != "hit"
		bs.position = Vector2(roundf(x + float(b["dx"])), roundf(y + float(b["dy"])))
	if st == "fly":
		var rr := Rect2(x - sz.x / 2.0 + 2.0, y - sz.y / 2.0 + 2.0, maxf(1.0, sz.x - 4.0), maxf(1.0, sz.y - 4.0))
		var c := _clearance(rr)
		if c < 0.0:
			_bump(w, r)
		else:
			r["near"] = minf(float(r["near"]), c)
			if not r["grazed"] and c < GRAZE and not w["bumped"]:
				r["grazed"] = true
				_graze(rr, c)
			if not r["passed"] and rr.position.x > _x1:
				r["passed"] = true                       # 擦过去了：声音往右走
				if r["key"]:
					_play("debris_pass_r", -16.0, 1.0, _pan(_x1) + 0.27)   # 船尾再往右一点（船在中间时 = 0.6）
	elif st == "hit":
		r["hit_t"] = float(r["hit_t"]) + delta
		r["vy"] = float(r["vy"]) * 0.97
		var k := clampf(float(r["hit_t"]) / 0.5, 0.0, 1.0)
		spr.modulate.a = 1.0 - floorf(k * 4.0) / 4.0
		if k >= 1.0:
			_free_rock(r)
			return
	if x - sz.x / 2.0 > 480.0 + 50.0:
		_free_rock(r)


func _free_rock(r: Dictionary) -> void:
	r["state"] = "gone"
	if is_instance_valid(r["spr"]):
		(r["spr"] as Node).queue_free()
	for b in r["bits"]:
		if is_instance_valid(b["spr"]):
			(b["spr"] as Node).queue_free()


func _free_wave(w: Dictionary) -> void:
	for r in w["rocks"]:
		_free_rock(r)


## 撞到：碎石弹开；同一波只算一次（晃一下、闷响、扣一点燃料、晨偶尔说一句）
func _bump(w: Dictionary, r: Dictionary) -> void:
	r["state"] = "hit"
	r["vx"] = 90.0                                   # 弹开：慢下来、往外翻
	var mid: float = (float(_hull.get("T", 100)) + float(_hull.get("B", 206))) / 2.0 + float(cockpit.ship_y())
	r["vy"] = 70.0 * (-1.0 if float(r["y"]) < mid else 1.0)
	if w["bumped"]:
		return
	w["bumped"] = true
	bumps += 1
	level._shake = 0.35
	level._shake_amp = 2.0
	_play("debris_bump", -4.0, 1.0, _pan(_ship_cx))
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


## 擦边：泛光闪一下 + 擦到的地方冒几颗火星 + 一声轻的「咻」
func _graze(rr: Rect2, _c: float) -> void:
	grazes += 1
	var g: Node2D = cockpit.far_glow if _far and cockpit.far_glow != null else cockpit.glow
	if g != null:
		g.strength = 1.0
	_play("ship_whoosh", -9.0, 1.35, _pan(rr.get_center().x))
	var mid: float = (float(_hull.get("T", 100)) + float(_hull.get("B", 206))) / 2.0 + float(cockpit.ship_y())
	var above := rr.get_center().y < mid
	var p := Vector2(rr.get_center().x, rr.end.y + 1.0 if above else rr.position.y - 1.0)
	for i in 6:
		_sparks.append({"p": p + Vector2(_rng.randf_range(-4.0, 4.0), 0.0),
			"v": Vector2(_rng.randf_range(20.0, 80.0), (-1.0 if above else 1.0) * -_rng.randf_range(5.0, 30.0)), "age": 0.0})


func _spark_step(delta: float) -> void:
	for i in range(_sparks.size() - 1, -1, -1):
		var s: Dictionary = _sparks[i]
		s["age"] = float(s["age"]) + delta
		s["p"] = (s["p"] as Vector2) + (s["v"] as Vector2) * delta
		if float(s["age"]) > 0.4:
			_sparks.remove_at(i)


## 结尾最后一排过去：穿出去——泛光闪亮、一声长「呼」+ 推进、轻轻一晃，气流声慢慢收掉
func _breakout() -> void:
	var g: Node2D = cockpit.far_glow if _far and cockpit.far_glow != null else cockpit.glow
	if g != null:
		g.strength = 1.0
	_play("ship_whoosh", -5.0, 0.8, _pan(_ship_cx))
	_play("engine_boost", -12.0, 1.0, _pan(_ship_cx))
	level._shake = 0.3
	level._shake_amp = 1.0
	_hint_out()


# ======================================================================= 气流（声音 + 安全通道的气流线）
func _air_step(delta: float) -> void:
	var want := 0.0
	for w in _waves:
		if not _wave_clear(w):
			want = 1.0
			_air_g = move_toward(_air_g, float(w["safe"]), 160.0 * delta)
			break
	if _ending:
		want = 0.0
	_air_on = move_toward(_air_on, want, delta / (0.6 if want > _air_on else 1.2))
	if is_instance_valid(_air):
		_air.volume_db = lerpf(-50.0, -15.0, sqrt(_air_on))
		_air.pitch_scale = 1.0 - 0.12 * _air_g / maxf(1.0, _shift)        # 通道在上面音高高一点


# ======================================================================= 收尾
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


# ======================================================================= 声音
## 音效（能调音高、声像 pan -1 左 .. +1 右；缺文件静默跳过，和 runner._sfx 一样记进统计）
func _play(snd: String, db: float, pitch := 1.0, pan := 0.0) -> void:
	if runner.ff:
		return
	var p: String = runner._sfx_path(snd)
	if p == "":
		runner.missing_sfx[snd] = true
		return
	var a := AudioStreamPlayer2D.new()
	a.stream = load(p)
	a.bus = "SFX"
	a.max_distance = 2000.0
	a.attenuation = 0.5
	a.volume_db = db
	a.pitch_scale = pitch
	level.add_child(a)
	a.global_position = level.cam_left() + Vector2(240.0 + clampf(pan, -1.0, 1.0) * 320.0, 135.0)
	a.play()
	a.finished.connect(a.queue_free)


## 循环的底噪（气流）：自己管音量；缺文件返回 null
func _loop(snd: String, db: float) -> AudioStreamPlayer:
	var p: String = runner._sfx_path(snd)
	if p == "":
		runner.missing_sfx[snd] = true
		return null
	var a := AudioStreamPlayer.new()
	a.stream = load(p)
	a.bus = "SFX"
	a.volume_db = db
	add_child(a)
	a.play()
	return a


# ======================================================================= 画：预告、气流线、火星
## 预告：碎石那条道的高度上，屏幕左边一道划痕（越来越长、一闪一闪，往右一格一格变淡）+ 一个远远的小影子（越来越大，左上一点亮边）。
## 10-29 验收：原来 3×1 的点、透明度 .25～.5，在暗云上几乎看不见 → 加粗加亮（仍比碎石本身淡）。
## 气流线：安全通道那个高度、机头前面几道 1 像素的细线往右流（很淡、不闪）。
func _draw_fx() -> void:
	if _air_on > 0.0:
		_draw_air()
	for w in _waves:
		for r in w["rocks"]:
			if str(r["state"]) != "warn":
				continue
			var k := clampf((_t - float(w["t0"])) / WARN, 0.0, 1.0)
			var y := roundf(float(r["y"]))
			var a := 0.75 if int(_t * 6.0) % 2 == 0 else 0.5
			if r["key"]:
				var ln := roundf(14.0 + 60.0 * k)
				var x := 0.0
				while x < ln:
					var f := floorf((1.0 - x / (ln + 10.0)) * 4.0) / 4.0          # 往右 4 档变淡
					_fx.draw_rect(Rect2(x, y, 4, 1), Color(SCRATCH_C, a * f))
					_fx.draw_rect(Rect2(x + 2, y + 1, 3, 1), Color(SCRATCH_C, a * f * 0.5))   # 下面一道淡的，划痕厚一点
					x += 6.0
			var s := 3.0 + floorf(k * 4.0) - (0.0 if r["key"] else 1.0)          # 小影子 3 → 7 像素（墙里别的那几块小一号）
			var sx := roundf(6.0 + 14.0 * k)
			var rr := Rect2(sx, y - floorf(s / 2.0), s, s - 1.0)
			_fx.draw_rect(rr, Color(0.07, 0.09, 0.08, 0.9))
			_fx.draw_rect(Rect2(rr.position, Vector2(s - 1.0, 1.0)), Color(0.78, 0.86, 0.8, a))
			_fx.draw_rect(Rect2(rr.position, Vector2(1.0, s - 2.0)), Color(0.78, 0.86, 0.8, a))
	for s in _sparks:
		var k := 1.0 - float(s["age"]) / 0.4
		_fx.draw_rect(Rect2((s["p"] as Vector2).round(), Vector2.ONE), Color(SPARK_C, floorf(k * 4.0) / 4.0 * 0.9))


func _draw_air() -> void:
	var top := float(_hull.get("T", 100)) + _air_g
	var bot := float(_hull.get("B", 206)) + _air_g
	var nose := _front_x(top, bot)
	var a := floorf(_air_on * 4.0) / 4.0 * 0.32
	if a <= 0.0:
		return
	var n := 5
	for i in n:
		var y := roundf(lerpf(top + 4.0, bot - 4.0, (float(i) + 0.5) / float(n)))
		var ln := 10.0 + float((i * 7) % 3) * 5.0
		var span := nose - 8.0 + ln
		var x := fposmod(_t * (230.0 + float(i % 3) * 35.0) + float(i) * 61.0, span) - ln
		var x0 := maxf(0.0, x)
		var x1 := minf(nose - 8.0, x + ln)
		if x1 - x0 < 1.0:
			continue
		_fx.draw_rect(Rect2(roundf(x0), y, roundf(x1 - x0), 1), Color(AIR_C, a))
		_fx.draw_rect(Rect2(roundf(x1) - 3.0, y, 3, 1), Color(AIR_C, minf(0.5, a * 1.6)))   # 线头亮一点：读得出往右流


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
