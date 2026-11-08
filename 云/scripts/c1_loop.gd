extends Node
## 第一关：跟着鹿去找背包那一段的「原地循环」（11-07 作者）。挂在 level_forest 下（_build_story 之后），名字 C1Loop。
##
## 作者原话：「从走路那里就是无限循环了，往回走无所谓，只要往前走就是无限循环，必须要按 shift 才能够继续。走一段时间如果还不按的话，
## 屏幕上就会显示『如果不奔跑的话，或许就再也出不去了……』……如果一直不奔跑，往前走了很久以后，就连出不去这句话也出来了也不跑，
## 就直接结束游戏：回忆的触手追上主角，碰到之前就直接结束，弹出成就『倔强的灵魂』，然后重新开始游戏。」
## 以及：「intro 开始播放 cg 以后，自动奔跑，不需要提示一直按着 shift」。
##
## 怎么做到「无限循环」：森林的地面和 Main 层都是 960 一圈（chen.gd 的 ground_y、Parallax2D 的 repeat_size），所以不用真的把晨传送回去，
## 而是「跑步机」：晨的世界 x 钉住（chen.intro_run，和片头一样），只把一个虚拟的位移 D 往前加——所有 Parallax2D 按自己的 scroll_scale
## 往后卷 dD × scroll_scale（和镜头真的往前走 dD 一模一样，远景慢、前景快），晨的脚按 ground_fn(x + D) 贴地。
## 世界里的东西（残骸、鹿、背包、hotspot）不动，所以前面的路永远走不到，回头看残骸也还在原地。
##   - 只有 D 是 960 的整数倍时，画面才和世界对得上（地面起伏、Main 层），所以：
##     往回走：先在跑步机上倒着卷，卷回上一个整圈再放开，她才真的在世界里往左走；
##     按 Shift 跑起来：直接开始 c1_run（片头 CG），CG 的自动奔跑也在跑步机上，结束时正好卷到整圈（cg_begin 算好速度），放开以后无缝。
##   - 一开始没走进跑步机（从左边直接 Shift 跑过去）：和原来一样跑进 c1_run 的 hotspot；CG 同样在跑步机上自动跑，从 D = 0 开始。
## 一直不跑：往前走（在跑步机上）累计 WARN_AFTER 秒出那句潜意识字；之后再往前走 END_AFTER 秒 → 结局「倔强的灵魂」：
##   晨被锁住、自己慢慢往前走，左边一团黑里伸出回忆的触手（画法、颜色照 flashback.gd 的 _draw_tentacles），心跳越来越快；
##   触手尖碰到她之前一帧整屏黑掉，所有声音停，成就弹出（flag c1_stubborn，data/achievements.json 的 stubborn_soul），几秒后回标题重新开始。
## 自动玩（--story_auto / --autoplay）不进跑步机（不然自测会被困住），也不出结局。

const ZONE_BEFORE := 40.0                  # 跑步机从 c1_run_go 左边多远开始（c1_run 的 hotspot 范围 24，留出来不会误触）
const LOOP_W := 960.0
const WARN_AFTER := 18.0                   # 在跑步机上往前走了多少秒出「出不去」那句
const END_AFTER := 15.0                    # 那句出来以后再往前走多少秒就结束
const CG_DIST := 2880.0                    # 片头 CG 至少卷多远（原来 Main 卷 3 圈）
const CG_PRE_V := 160.0                    # CG 的 mechanic 开始之前（那句「好熟悉的感觉」）先按这个速度卷
const WARN_ZH := "如果不奔跑的话，或许就再也出不去了……"
const WARN_EN := "If I don't run... maybe I'll never get out of here..."

var level: Node2D
var d := 0.0                               # 跑步机的虚拟位移
var mode := "idle"                         # idle / walk（等她按 Shift）/ cg / ending / done
var _layers: Array[Parallax2D] = []
var _walk_t := 0.0
var _warned := false
var _after_warn := 0.0
var _cg_v := CG_PRE_V
var _cg_left := -1.0                       # cg_begin 以后：还要卷多远
var _armed := false                        # 这次真的走到过「c1_follow 了、还没 c1_run」（跳节拍直接越过去的不算）
var _sink := 1.0
var _run_speed := 150.0
var _end: Node


func _ready() -> void:
	process_priority = -10                 # 在晨（chen.gd）之前算好 intro_run，这一帧她就不往前挪
	var cm: Dictionary = (level.chen.get_script() as Script).get_script_constant_map()
	_sink = float(cm.get("SINK", 1))
	_run_speed = float(cm.get("RUN_SPEED", 150.0))
	for n in _walk(level):
		_take(n)
	level.get_tree().node_added.connect(_take)


func _walk(n: Node) -> Array:
	var out: Array = [n]
	for c in n.get_children():
		out.append_array(_walk(c))
	return out


func _take(n: Node) -> void:
	if n is Parallax2D and level.is_ancestor_of(n) and not _layers.has(n):
		_layers.append(n)


func _auto() -> bool:
	return level._story_auto != "" or level._autoplay


## 卷：等于镜头往前走了 dd（远景按 scroll_scale 慢、前景快）
func _scroll(dd: float) -> void:
	if dd == 0.0:
		return
	d += dd
	for p in _layers:
		if is_instance_valid(p):
			p.scroll_offset.x -= dd * p.scroll_scale.x


func _stick_feet() -> void:
	var chen: Node2D = level.chen
	var gy := roundf(float(chen.ground_fn.call(chen.position.x + d))) + _sink
	chen.position.y = roundf(move_toward(chen.position.y, gy, 2.0))


func _process(delta: float) -> void:
	var story: Node = level.story
	if story == null or level.chapter != "forest":
		return
	match mode:
		"idle", "walk":
			_tick_walk(delta, story)
		"cg":
			_tick_cg(delta)
		"ending":
			_scroll(float(level.chen._vel) * delta)          # 她还在原地往前走，林子接着往后卷
			_stick_feet()


func _tick_walk(delta: float, story: Node) -> void:
	var chen: Node2D = level.chen
	if StoryState.has("c1_run"):
		if _armed and not story.ff and mode != "cg":
			_start_cg_mode()                    # 跑进了 c1_run 的 hotspot（或者下面按 Shift 叫的）：CG 也在跑步机上
		elif not _armed:
			mode = "done"
		return
	var live: bool = StoryState.has("c1_follow") and not story.free_roam and not _auto() and level.state == level.S.PLAY
	if not live:
		return
	_armed = true
	if story.busy:
		return                                  # 鹿还在说话、带路：等剧情放开
	var zone_x: float = story.world.mx("c1_run_go") - ZONE_BEFORE
	var vel: float = float(chen._vel)
	var running: bool = vel > _run_speed * 1.05 and Input.is_key_pressed(KEY_SHIFT)
	var on_belt: bool = fposmod(d, LOOP_W) > 0.01 or (chen.position.x >= zone_x - 0.5 and chen.facing > 0)
	if not on_belt:
		chen.intro_run = false
		mode = "idle"
		return
	mode = "walk"
	if chen.facing > 0:
		if running:
			chen.intro_run = true
			story.play("c1_run")                # 在跑步机上跑起来 = 走出去了：片头 CG
			_start_cg_mode()
			return
		chen.intro_run = true
		if chen.position.x > zone_x:
			chen.position.x = zone_x
		_scroll(vel * delta)
		if vel > 1.0:
			_count_walk(delta, story)
	else:
		# 往回走：在跑步机上倒着卷回上一个整圈，再放开（这时画面和世界对得上）
		var floor_d := floorf((d - 0.01) / LOOP_W) * LOOP_W
		var step := minf(vel * delta, d - floor_d)
		chen.intro_run = true
		_scroll(-step)
		if fposmod(d, LOOP_W) < 0.01 or absf(d - floor_d) < 0.01:
			d = roundf(d / LOOP_W) * LOOP_W
			chen.intro_run = false
	_stick_feet()


func _count_walk(delta: float, story: Node) -> void:
	_walk_t += delta
	if not _warned and _walk_t >= WARN_AFTER:
		_warned = true
		story._inner({"zh": WARN_ZH, "en": WARN_EN, "style": "fade", "sec": 4.0})
		print("C1LOOP warn t=%.1f d=%.0f" % [_walk_t, d])
	elif _warned:
		_after_warn += delta
		if _after_warn >= END_AFTER:
			_start_ending()


# ----------------------------------------------------------------------- 片头 CG：自动跑，结束时卷到整圈
func _start_cg_mode() -> void:
	mode = "cg"
	_cg_v = CG_PRE_V
	_cg_left = -1.0
	level.chen.intro_run = true
	level.chen.auto_dir = 1.0


## run_credits.gd 的 intro 开始时叫：这一段 sec 秒，算好速度让结束时 d 正好是整圈
func cg_begin(sec: float) -> void:
	if mode != "cg":
		_start_cg_mode()
	var r := fposmod(d, LOOP_W)
	_cg_left = CG_DIST + (LOOP_W - r if r > 0.01 else 0.0)
	_cg_v = _cg_left / maxf(sec, 0.1)


func cg_running() -> bool:
	return mode == "cg"


func _tick_cg(delta: float) -> void:
	var chen: Node2D = level.chen
	chen.intro_run = true
	chen.auto_dir = 1.0
	var step := _cg_v * delta
	if _cg_left >= 0.0:
		step = minf(step, _cg_left)
		_cg_left -= step
	_scroll(step)
	_stick_feet()
	if _cg_left == 0.0:
		d = roundf(d / LOOP_W) * LOOP_W
		_cash_loop()
		_stick_feet()
		chen.intro_run = false
		chen.auto_dir = 0.0
		mode = "done"
		print("C1LOOP cg_done d=%.0f" % d)


## 11-08 作者「从飞船到背包有一段距离，最好可以删除（credit 本身已经是额外的循环）」：
## CG 卷完一圈以上时，把跑步机虚拟位移里的一圈（LOOP_W）兑换成真实位移——晨、镜头往右挪 LOOP_W，
## 各视差层 scroll_offset += LOOP_W × scroll_scale（和 level_forest._place_world 挪 CRASH_DX 同一招），d -= LOOP_W。
## Main 层和地面都是 LOOP_W 一圈，所以这一帧每一层画面都不变；跑完她就站在背包前几步（背包锚点见 story_forest.json 的 c1_bag*）。
## 世界里的东西不跟着挪：跳完以后才进画面的是背包、等在那儿的鹿。
func _cash_loop() -> void:
	if d < LOOP_W - 0.5:
		return
	var dx := LOOP_W
	var chen: Node2D = level.chen
	chen.position.x += dx
	var cam: Camera2D = level.cam
	cam.position.x += dx
	if not is_nan(level._cam_override.x):
		level._cam_override.x += dx
	cam.reset_smoothing()
	for p in _layers:
		if is_instance_valid(p):
			p.scroll_offset.x += dx * p.scroll_scale.x
	d -= dx
	var roll := level.get_node_or_null("RunCredits")
	if roll != null and roll.has_method("shift_world"):
		roll.shift_world(dx)                     # 还在屏幕上的名字钉在世界里，跟着挪，屏幕上不动
	print("C1LOOP cash x=%.0f d=%.0f" % [chen.position.x, d])


# ----------------------------------------------------------------------- 结局：倔强的灵魂
func _start_ending() -> void:
	mode = "ending"
	print("C1LOOP ending d=%.0f" % d)
	var chen: Node2D = level.chen
	chen.input_enabled = false
	chen.intro_run = true
	chen.auto_dir = 1.0                         # 被锁住了，还是一步步往前走
	_end = (load("res://scripts/c1_stubborn_end.gd") as GDScript).new()
	_end.name = "StubbornEnd"
	_end.loop = self
	_end.level = level
	level.add_child(_end)

