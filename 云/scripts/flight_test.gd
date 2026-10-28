extends Node2D
## 飞行段原型（木星 → 水星）。单键滑翔：按住空格 / ↑ / W / 鼠标左键 / 触屏 = 往上，松开 = 往下滑。
## 核心是「烧掉什么」：燃料从燃烧队列里来，普通材料自动烧，轮到私人物品 / 朋友的东西时时间几乎停住，弹一张卡等你选。
## 撞到东西只是晃一下、漏几秒油，不会死；彻底没油就平静地坠毁，照样「到达」下一颗星球，只是东西都没了。
##
## 燃料模型（数都在下面的常量里）：
##   需要 need（data 里写，350）。引擎每秒烧 need / FLIGHT_TIME，飞满 FLIGHT_TIME 秒正好烧完 need。
##   油箱 tank 一开始有 START_TANK；低于 FEED_AT 就从队列头拿下一件：材料直接烧，私人物品弹卡。
##   卡上「留下」→ 它排到队尾（标成「这一轮跳过了」）；轮到一件已经跳过的 = 这一轮没有想烧的了。
##   油箱见底又没东西可烧 = 紧急模式：引擎咳嗽、画面变冷、上升变弱、天花板慢慢压下来（EMERG_GLIDE 秒压到底 = 坠毁），
##   光点给的燃料 ×EMERG_MOTE_MULT。压到一半时弹一次「最后的机会」卡（剩下的私人物品排一排，挑一件烧或者都留下）。
##   使坏：飞到 SABOTAGE_AT 时一阵颠簸，队列里的 SABOTAGE_WOOD 块木头掉出飞船。
##
## 命令行（-- 后面）：
##   --bot=none|random|okay|good   自动玩（不按 / 随机按 / 反应慢的「还行的人」/ 尽量躲障碍吃光点）；不给 = 人玩
##   --card=keep|burn|mix     机器人在决定卡上一律选什么（默认 burn；mix = 第一张烧、之后都留下）
##   --seed=N                 光点抖动、障碍相位、随机机器人
##   --speed=倍数             Engine.time_scale
##   --lang=zh                中文（默认英文；游戏里按 L 切换）
##   --shot=绝对路径 --at=秒   在第几秒（真实时间）存一张图后退出
##   --snap=目录              遇到关键事件自动各存一张（takeoff / sabotage / card / burn / leak / emergency / pick / elephant / mercury / end）
##   --frames=目录 --every=N --from=秒 --to=秒   连拍（缩到 960×540），拍完退出
##   --quit                   结束画面出来后打印一行 FLIGHT_RESULT {...} 并退出（批量统计用）
##   --card_delay=秒          机器人在卡上停多久再选（默认 1.6）

# ---------------------------------------------------------------- 可调参数
const FLIGHT_TIME := 60.0        # 一次飞行（按主题曲长度调）
const SPEED := 64.0              # 画面滚动（主层像素 / 秒）
const START_TANK := 100.0        # 起飞时引擎里已经有的
const FEED_AT := 6.0             # 油箱低于这个就烧下一件
const MOTE_FUEL := 3.0           # 一个光点
const EMERG_MOTE_MULT := 2.0     # 紧急模式时光点给的倍数
const LEAK_TIME := 4.0           # 撞一下漏几秒油
const LEAK_RATE := 3.0           # 漏油时每秒多掉多少
const HIT_COOLDOWN := 1.8        # 撞完这么久里不会再撞
const SABOTAGE_AT := 0.15
const SABOTAGE_WOOD := 3
const EMERG_GLIDE := 5.0         # 紧急模式：天花板从顶压到底要几秒
const GLIDE_RECOVER := 12.0      # 有油了：天花板几秒回到顶
const LAST_CHANCE_AT := 0.5      # 天花板压到一半：最后一次机会
const CATCH_AT := 0.85           # 过了这里还没油：水星的引力把飞船接过去，滑着也能到（不会在终点前一秒坠毁）
const CATCH_GLIDE := 0.3
const CARD_SLOW := 0.07          # 决定卡时世界的速度
const SHIP_X := 120.0
const STEP := 1.0 / 120.0
const ITEMS_PATH := "res://data/flight_test_items.json"
# 水星从远处慢慢变大：同一颗星球按这些直径各画了一格（tools/flight_art.py 的 MERC_SIZES，改了要一起改）
const MERC_SIZES := [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 23, 25, 26, 28, 30, 33, 35, 38, 41, 44,
	47, 51, 54, 58, 63, 68, 73, 78, 84, 90, 97, 104, 112, 120, 130, 139, 150, 161, 173, 186, 200, 215, 231, 240]
const MERC_GLOW_FROM := 0.28     # 先看到水星的光（地平线右边一小团蓝光）
const MERC_FROM := 0.36          # 再看到星球本身（一个小点），之后一路变大
const ELEPHANT_AT := Vector2(0.40, 0.80)   # 远处那团大象形状的星云出现 / 消失的进度（极淡，第二眼才看得出）

const Course := preload("res://scripts/flight_course.gd")
const Ship := preload("res://scripts/flight_ship.gd")
const Hud := preload("res://scripts/flight_hud.gd")

@onready var world: Node2D = $Shake
@onready var ship: Node2D = $Shake/Ship
@onready var course: Node2D = $Shake/Course
@onready var fx: Node2D = $Shake/FX
@onready var hud: Node2D = $UI/HUD
@onready var card: Node2D = $UI/Card
@onready var end_screen: Node2D = $UI/End
@onready var tint: CanvasModulate = $Tint
@onready var sky_blue: Sprite2D = $Sky/Blue
@onready var mercury: Sprite2D = $Mercury
@onready var forest: Sprite2D = $Shake/Forest
@onready var layers := {
	$Stars: 0.03, $Wisps: 0.08, $Far: 0.16, $Mid: 0.36, $Shake/Near: 0.8,
}

var need := 350.0
var rate := 350.0 / 60.0
var length := FLIGHT_TIME * SPEED
var T := 0.0                 # 世界时间
var real_t := 0.0
var travel := 0.0
var tank := START_TANK
var wscale := 1.0
var phase := "fly"           # fly / card / crash / arrive / end
var queue: Array = []        # 还没烧的（队头 = 下一件）
var burned: Array = []
var lost: Array = []         # 使坏事件掉出去的
var round_over := false
var leak_t := 0.0
var hit_cd := 0.0
var glide := 1.0
var emergency := false
var emerg_vis := 0.0
var pick_armed := true
var sabotaged := false
var end_t := 0.0
var _acc := 0.0
var _cough_t := 0.0
var _drip_t := 0.0
var _said_emerg := false
var _said_catch := false
var _merc_glow: Sprite2D
var _merc_atlas: AtlasTexture
var _merc_xs: Array = []
var _elephant: Sprite2D
var _sub_t := 0.0
var _sub_dur := 1.0
var _said_need := false
var _card_open_t := 0.0
var _card_item: Dictionary = {}
var _touch := false
var _shake_t := 0.0
var _speed_mul := 1.0
var _arrive_v := Vector2.ZERO

# 统计
var stats := {"hits": 0, "motes": 0, "burned_personal": 0, "cards": 0, "emergency_s": 0.0, "min_glide": 1.0,
	"emerg_p": -1.0, "crash_p": -1.0}

# 调试 / 机器人
var bot := ""
var card_policy := "burn"
var card_delay := 1.6
var seed_v := 1
var _rng := RandomNumberGenerator.new()
var _bot_press := false
var _bot_timer := 0.0
var _plan_t := 0.0
var _shot := ""
var _shot_at := -1.0
var _snap := ""
var _snapped := {}
var _pending_snaps: Array = []
var _frames := ""
var _f_every := 2
var _f_from := 0.0
var _f_to := 1e9
var _f_n := 0
var _frame_i := 0
var _quit := false
var batch := false           # tools/flight_batch.gd 一个进程里连跑很多局：结束时发 finished，不退出
signal finished(result: Dictionary)
var _engine: AudioStreamPlayer
var _sfx_pool: Array = []


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		var k: String = kv[0]
		var v: String = kv[1] if kv.size() > 1 else ""
		match k:
			"bot": bot = v
			"card": card_policy = v
			"card_delay": card_delay = float(v)
			"seed": seed_v = int(v)
			"speed": Engine.time_scale = float(v)
			"lang": FlightText.lang = v
			"shot": _shot = v
			"at": _shot_at = float(v)
			"snap": _snap = v
			"frames": _frames = v
			"every": _f_every = int(v)
			"from": _f_from = float(v)
			"to": _f_to = float(v)
			"quit": _quit = true
	for d in [_snap, _frames]:
		if d != "":
			DirAccess.make_dir_recursive_absolute(d)
	_rng.seed = seed_v
	seed(seed_v)
	_load_items()
	course.build(length, seed_v)
	ship.position = Vector2(SHIP_X, 196)
	fx.ship = ship
	_setup_far_sky()
	fx.on_ember_arrive = func(): ship.flare = minf(1.0, ship.flare + 0.08)
	card.fx = fx
	card.sfx_cb = sfx
	card.chosen.connect(_on_card_chosen)
	card.landed.connect(_on_keep_landed)
	card.closed.connect(_on_card_closed)
	end_screen.visible = false
	hud.need0 = need
	_engine = AudioStreamPlayer.new()
	var es: AudioStreamWAV = load("res://audio/sfx/flight_engine_loop.wav")
	es.loop_mode = AudioStreamWAV.LOOP_FORWARD
	es.loop_begin = 0
	es.loop_end = int(4.0 * 44100)
	_engine.stream = es
	_engine.volume_db = -10.0
	add_child(_engine)
	_engine.play()
	for i in 8:
		var p := AudioStreamPlayer.new()
		add_child(p)
		_sfx_pool.append(p)
	_snap_later("takeoff", 3.0)


func _setup_far_sky() -> void:
	# 水星：一条不同尺寸的星球（每格都是 1 倍像素），按进度挑一格；光是另一张半透明的，放在星球后面、云的后面。
	var x := 0
	for d in MERC_SIZES:
		_merc_xs.append(x)
		x += int(d) + 10
	_merc_atlas = AtlasTexture.new()
	_merc_atlas.atlas = load("res://art/flight/mercury_strip.png")
	mercury.texture = _merc_atlas
	mercury.centered = true
	mercury.visible = false
	_merc_glow = Sprite2D.new()
	_merc_glow.texture = load("res://art/flight/mercury_glow.png")
	var addm := CanvasItemMaterial.new()
	addm.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	_merc_glow.material = addm
	_merc_glow.modulate.a = 0.0
	add_child(_merc_glow)
	move_child(_merc_glow, mercury.get_index())
	# 「梦里的大象」：星星后面、薄云前面一团极淡的星云
	_elephant = Sprite2D.new()
	_elephant.texture = load("res://art/flight/nebula_elephant.png")
	_elephant.centered = false
	_elephant.modulate.a = 0.0
	add_child(_elephant)
	move_child(_elephant, $Stars.get_index() + 1)


func _place_far_sky(p: float) -> void:
	var u := clampf((p - MERC_FROM) / (1.0 - MERC_FROM), 0.0, 1.0)
	var rise := 0.0
	if phase == "arrive" or phase == "end":
		rise = clampf((real_t - end_t) / 6.0, 0.0, 1.0)
	var d := 5.0 * pow(48.0, pow(u, 1.3))
	var k := 0
	while k < MERC_SIZES.size() - 1 and float(MERC_SIZES[k + 1]) <= d:
		k += 1
	var dk: int = MERC_SIZES[k]
	_merc_atlas.region = Rect2(_merc_xs[k], 0, dk + 8, dk + 8)
	var c := Vector2(392, 150).lerp(Vector2(412, 248), pow(u, 3.0)) + Vector2(0, -26.0 * rise * rise * (3.0 - 2.0 * rise))
	mercury.position = c.round()
	mercury.visible = p > MERC_FROM
	mercury.modulate.a = clampf((p - MERC_FROM) / 0.03, 0.0, 1.0)
	_merc_glow.position = c.round()
	_merc_glow.scale = Vector2.ONE * maxf(0.16, (dk + 8) / 248.0 * 1.15)
	_merc_glow.modulate.a = smoothstep(MERC_GLOW_FROM, MERC_GLOW_FROM + 0.14, p) * (0.8 + 0.12 * sin(real_t * 0.8))
	# 大象星云：比星星稍快一点点地往左漂
	_elephant.position = Vector2(roundf(150.0 - travel * 0.035), 34)
	var ea := smoothstep(ELEPHANT_AT.x, ELEPHANT_AT.x + 0.1, p) * (1.0 - smoothstep(ELEPHANT_AT.y - 0.1, ELEPHANT_AT.y, p))
	_elephant.modulate.a = ea * lerpf(0.4, 1.0, glide)
	_elephant.visible = ea > 0.0


func _load_items() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(ITEMS_PATH))
	need = float(data.get("flight", {}).get("need", 350))
	rate = need / FLIGHT_TIME
	var uid := 0
	for it in data["items"]:
		for i in int(it.get("count", 1)):
			var e: Dictionary = it.duplicate(true)
			e["uid"] = uid
			e["skipped"] = false
			e["tex"] = load(e.icon)
			uid += 1
			queue.append(e)


# ---------------------------------------------------------------- 主循环

func _process(delta: float) -> void:
	real_t += delta
	var target: float = CARD_SLOW if card.is_open() and card.state != "keep" else 1.0
	if card.state == "burn" and card.anim > 1.2:
		target = 1.0
	wscale = lerpf(wscale, target, 1.0 - exp(-(6.0 if target < wscale else 2.5) * delta))
	if phase == "end":
		wscale = lerpf(wscale, 0.25, 1.0 - exp(-delta))
	var wdt := delta * wscale
	_acc += wdt
	while _acc >= STEP:
		_acc -= STEP
		_sim(STEP)
	_visuals(delta, wdt)
	_bot_cards()
	_debug_capture()


func _pressed() -> bool:
	if T < 1.0:
		return true                     # 起飞：先自己往上抬一下
	if phase != "fly" and phase != "card":
		return false
	if bot != "":
		return _bot_press
	return Input.is_key_pressed(KEY_SPACE) or Input.is_key_pressed(KEY_UP) or Input.is_key_pressed(KEY_W) \
		or Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) or _touch


func _sim(dt: float) -> void:
	T += dt
	if bot != "" and phase == "fly":
		_bot_step(dt)
	travel += SPEED * dt * _speed_mul
	var progress := travel / length
	ship.pressed = _pressed()
	ship.ceiling = lerpf(Ship.TOP, Ship.BOTTOM - 14.0, 1.0 - glide)
	if phase == "arrive":
		_arrive_v = _arrive_v.lerp(Vector2(46, -10), 1.0 - exp(-1.5 * dt))
		ship.position += _arrive_v * dt
		ship.vy = lerpf(ship.vy, -10.0, dt)
	else:
		ship.sim(dt)
	if phase == "crash":
		_speed_mul = move_toward(_speed_mul, 0.35, dt * 0.3)
		return
	if phase == "arrive" or phase == "end":
		return
	# ---- 燃料
	var burn := rate * dt
	if leak_t > 0.0:
		burn += LEAK_RATE * dt
		leak_t -= dt
		_drip_t -= dt
		if _drip_t <= 0.0:
			_drip_t = 0.16
			fx.oil(ship.global_position + Vector2(-6, 4))
			if int(leak_t * 6.25) % 3 == 0:
				sfx("drip", randf_range(0.9, 1.2))
		if leak_t <= 0.0:
			sfx("repair")
			fx.spark(ship.global_position + Vector2(-6, 3), 5, Color(0.7, 0.95, 1.0), 25.0)
	tank = maxf(0.0, tank - burn)
	if not card.is_open() and phase == "fly" and tank < FEED_AT:
		_feed()
	var was := emergency
	emergency = tank <= 0.0 and not card.is_open()
	if emergency:
		glide -= dt / EMERG_GLIDE
		stats.emergency_s += dt
		if not was:
			_on_emergency()
			if stats.emerg_p < 0.0:
				stats.emerg_p = progress
	else:
		glide = minf(1.0, glide + dt / GLIDE_RECOVER)
	stats.min_glide = minf(stats.min_glide, glide)
	if glide > 0.9:
		pick_armed = true
	if emergency and progress >= CATCH_AT:
		glide = maxf(glide, CATCH_GLIDE)
		if not _said_catch:
			_said_catch = true
			_say(FlightText.t("catch"), 5.0)
	if emergency and glide < LAST_CHANCE_AT and pick_armed and not card.is_open() and phase == "fly" \
			and progress < CATCH_AT:
		var personal: Array = queue.filter(func(e): return e.kind == "personal")
		pick_armed = false
		if not personal.is_empty():
			_open_pick(personal)
	if glide <= 0.0 and phase == "fly":
		_crash()
		return
	# ---- 撞
	hit_cd -= dt
	var sw := Vector2(travel + SHIP_X, ship.position.y)
	if hit_cd <= 0.0:
		var i: int = course.hit_at(T, sw, ship.hit_points())
		if i >= 0:
			_on_hit(i)
	# ---- 光点
	for i in course.motes_near(T, sw, Course.MOTE_R):
		course.take(i)
		var f := MOTE_FUEL * (EMERG_MOTE_MULT if emergency else 1.0)
		tank += f
		stats.motes += 1
		fx.spark(ship.global_position + Vector2(4, 0), 6, Color(1.0, 0.9, 0.55), 30.0)
		ship.flare = minf(1.0, ship.flare + 0.35)
		sfx("mote", [1.0, 1.122, 1.26, 1.498, 1.682][randi() % 5])
	# ---- 使坏
	if not sabotaged and progress >= SABOTAGE_AT:
		_sabotage()
	if progress >= 1.0:
		_arrive()


# ---------------------------------------------------------------- 燃烧队列

func _feed() -> void:
	if queue.is_empty():
		round_over = true
		return
	var e: Dictionary = queue[0]
	if e.skipped:
		round_over = true
		return
	if e.kind == "material":
		queue.pop_front()
		_burn(e, false)
		hud.toast("+%d %s" % [int(e.fuel), FlightText.pick(e.name)], e.tex)
		for k in 10:
			fx.ember(Vector2(Hud.QX + 12, 250) + Vector2(randf_range(-6, 6), randf_range(-6, 6)), k * 0.04)
	else:
		_open_card(e)


func _burn(e: Dictionary, personal: bool) -> void:
	queue.erase(e)
	burned.append(e)
	tank += float(e.fuel)
	ship.flare = 1.0 if personal else 0.6
	sfx("burn", 1.0 if personal else 1.25, -4.0 if personal else -10.0)
	if personal:
		stats.burned_personal += 1


func _open_card(e: Dictionary) -> void:
	_card_item = e
	card.keep_target = Vector2(Hud.QX + 12 + 27 * mini(3, queue.size() - 1), 252)
	card.open_single(e)
	_card_open_t = real_t
	stats.cards += 1
	sfx("card")
	_snap_later("card", 1.3)


func _open_pick(list: Array) -> void:
	card.keep_target = Vector2(Hud.QX + 12, 252)
	card.open_pick(list)
	_card_open_t = real_t
	stats.cards += 1
	sfx("card", 0.85)
	_snap_later("pick", 1.3)


func _on_card_chosen(action: String, index: int) -> void:
	if card.mode == "single":
		var e := _card_item
		if action == "burn":
			_burn(e, true)
			_snap_later("burn", 0.7)
		else:
			queue.erase(e)
			e.skipped = true
			queue.append(e)
			hud.hold[e.uid] = true
			sfx("select", 0.8)
	else:
		if action == "burn":
			var e2: Dictionary = card.items[index]
			_burn(e2, true)
			_snap_later("burn", 0.7)
		else:
			for e3 in card.items:
				hud.hold[e3.uid] = true
			sfx("select", 0.8)


func _on_keep_landed(uid: int) -> void:
	## 「留下」的东西飞回右下角那一排：落下的那一下，那一格亮一下、往上弹一点
	hud.hold.erase(uid)
	hud.pulse[uid] = 0.6
	sfx("mote", 0.75, -12.0)


func _on_card_closed() -> void:
	hud.hold.clear()


# ---------------------------------------------------------------- 事件

func _sabotage() -> void:
	sabotaged = true
	var woods: Array = queue.filter(func(e): return e.id == "wood")
	var n := mini(SABOTAGE_WOOD, woods.size())
	for i in n:
		var e: Dictionary = woods[woods.size() - 1 - i]
		queue.erase(e)
		lost.append(e)
	hud.toast("-%d" % int(n * 40), load("res://art/flight/item_wood.png"), Vector2(118, 44), Color("d77a8e"))
	for i in n + 1:
		fx.wood(ship.global_position + Vector2(-10 + i * 3, 2), Vector2(randf_range(-40, -10), randf_range(-60, -30)))
	_shake_t = 1.6
	ship.shake = 1.0
	ship.vy += 30.0
	hud.gauge_pop = 1.2
	sfx("rumble")
	_say(FlightText.t("sabotage"), 5.5)
	_snap_later("sabotage", 1.0)


func _on_hit(i: int) -> void:
	hit_cd = HIT_COOLDOWN
	leak_t = LEAK_TIME
	stats.hits += 1
	ship.hit_flash = 0.5
	ship.shake = 0.7
	var o: Dictionary = course.obstacles[i]
	var c: Vector2 = Course.obs_pos(o, T) + Vector2(o.w, o.h) * 0.5
	if o.type == "birds":
		c = Course.obs_pos(o, T)
	ship.vy = 45.0 if c.y < ship.position.y else -45.0
	_shake_t = 0.3
	fx.spark(ship.global_position + Vector2(10, 0), 8)
	sfx("bump")
	_snap_later("leak", 0.9)


func _on_emergency() -> void:
	if not _said_emerg:
		_said_emerg = true
		_say(FlightText.t("emergency"), 4.0)
		_snap_later("emergency", 2.1)


func _crash() -> void:
	stats.crash_p = travel / length
	phase = "crash"
	ship.crashed = true
	sfx("cough", 0.8)
	end_t = real_t


func _arrive() -> void:
	phase = "arrive"
	_arrive_v = Vector2(0, ship.vy)
	end_t = real_t
	sfx("arrive")


func _show_end() -> void:
	phase = "end"
	var crashed: bool = ship.crashed
	var kept: Array = queue.filter(func(e): return e.kind == "personal")
	end_screen.show_result(crashed, burned.filter(func(e): return true), kept, lost)
	if not crashed:
		pass
	else:
		sfx("arrive", 0.8)
	_snap_later("end", 4.5)
	if _quit:
		var r := {"bot": bot, "card": card_policy, "seed": seed_v, "result": "crash" if crashed else "arrive",
			"hits": stats.hits, "motes": stats.motes, "burned_personal": stats.burned_personal,
			"kept_personal": kept.size(), "cards": stats.cards, "emergency_s": snappedf(stats.emergency_s, 0.1),
			"min_glide": snappedf(stats.min_glide, 0.01), "T": snappedf(T, 0.1), "tank_end": snappedf(tank, 0.1),
			"emerg_p": snappedf(stats.emerg_p, 0.01), "crash_p": snappedf(stats.crash_p, 0.01)}
		print("FLIGHT_RESULT ", JSON.stringify(r))
		if batch:
			finished.emit(r)
		elif _snap == "" and _frames == "":
			get_tree().quit()


func _say(s: String, dur: float) -> void:
	hud.subtitle = s
	_sub_t = dur
	_sub_dur = dur


# ---------------------------------------------------------------- 画面

func _visuals(delta: float, wdt: float) -> void:
	var p := clampf(travel / length, 0.0, 1.0)
	for n in layers:
		(n as Parallax2D).scroll_offset.x = -travel * layers[n]
	forest.position.x = roundf(-travel * 0.7)
	forest.visible = forest.position.x > -800
	var b := smoothstep(0.12, 0.9, p)
	sky_blue.modulate.a = b
	var cloud_tint := Color(0.78, 1.0, 0.88).lerp(Color(0.8, 0.92, 1.18), b)
	for n in [$Far, $Mid, $Shake/Near, $Wisps]:
		n.modulate = cloud_tint
	# 水星：28% 起先在右边地平线上看到它的光，36% 起星球是远处一个小点，越飞越近、越来越大（一格一格换尺寸，不缩放）
	_place_far_sky(p)
	if p > 0.6:
		_snap_later("elephant", 0.0)
	if p > 0.93:
		_snap_later("mercury", 0.0)
	# 紧急模式：飞得越低，上面的星星越暗（「上面的天够不着了」）
	var sky_a := lerpf(0.25, 1.0, glide) if (emergency or phase == "crash") else minf(1.0, $Stars.modulate.a + delta)
	$Stars.modulate.a = sky_a
	$Wisps.modulate.a = lerpf(0.5, 1.0, sky_a)
	course.refresh(T, travel, delta, wdt)
	fx.update(wdt, delta)
	# 紧急模式：画面变冷，引擎咳嗽
	emerg_vis = move_toward(emerg_vis, 1.0 if emergency or phase == "crash" else 0.0, delta * 0.6)
	tint.color = Color(1, 1, 1).lerp(Color(0.62, 0.72, 0.95), emerg_vis)
	ship.emergency = emerg_vis if emergency else 0.0
	if emergency and phase == "fly":
		_cough_t -= wdt
		if _cough_t <= 0.0:
			_cough_t = 1.7
			sfx("cough", randf_range(0.9, 1.1), -6.0)
			for k in 3:
				fx.puff(ship.tail_pos() + Vector2(-k * 3, randf_range(-2, 2)))
	# 晃
	_shake_t = maxf(0.0, _shake_t - delta)
	world.position = Vector2(sin(real_t * 53.0), cos(real_t * 41.0)).round() * (2.0 if _shake_t > 0.2 else 1.0) \
		* (1.0 if _shake_t > 0.0 else 0.0)
	# 引擎声
	var pitch: float = lerpf(0.45, 1.0, wscale) * (0.85 if emergency else 1.0) * (1.0 + ship.flare * 0.15)
	_engine.pitch_scale = maxf(0.2, pitch)
	_engine.volume_db = -10.0 - (14.0 if phase == "crash" or phase == "end" else 0.0) - (6.0 if wscale < 0.5 else 0.0)
	# HUD
	hud.progress = p
	hud.need_left = rate * maxf(0.0, length - travel) / SPEED
	hud.tank = tank
	var q := 0.0
	var icons := []
	for e in queue:
		if e.kind == "material":
			q += float(e.fuel)
		icons.append({"tex": e.tex, "personal": e.kind == "personal", "skipped": e.skipped, "uid": e.uid})
	hud.queued = q
	hud.queue_icons = icons
	hud.round_over = round_over and not queue.is_empty() and queue[0].skipped
	hud.leaking = leak_t > 0.0
	hud.ceiling_y = ship.ceiling - 22.0
	hud.ceil_a = move_toward(hud.ceil_a, 1.0 if glide < 0.999 and phase == "fly" else 0.0, delta)
	course.glow_boost = emerg_vis
	_sub_t -= delta
	hud.subtitle_a = clampf(_sub_t * 1.5, 0.0, 1.0) * clampf((_sub_dur - _sub_t) * 3.0, 0.0, 1.0) if _sub_t > 0.0 else 0.0
	hud.hint_a = clampf((7.0 - T) / 1.5, 0.0, 1.0) * clampf((T - 0.8) / 0.8, 0.0, 1.0) if bot == "" or _snap != "" else 0.0
	if T > 2.0 and not _said_need:
		_said_need = true
		_say(FlightText.t("need_line") % [int(need), int(need)], 5.0)
	if phase == "end":
		hud.alpha = move_toward(hud.alpha, 0.0, delta)
	hud.update(delta)
	if (phase == "crash" and real_t - end_t > 4.0) or (phase == "arrive" and real_t - end_t > 3.5):
		_show_end()


# ---------------------------------------------------------------- 输入

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		_touch = event.pressed
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_L:
			FlightText.lang = "zh" if FlightText.lang == "en" else "en"
			return
		if event.keycode == KEY_ESCAPE:
			get_tree().quit()
	if phase == "end" and end_screen.a >= 1.0 and bot == "":
		if (event is InputEventKey and event.pressed) or (event is InputEventMouseButton and event.pressed):
			get_tree().reload_current_scene()


# ---------------------------------------------------------------- 机器人

func _bot_cards() -> void:
	if bot == "" or not card.is_open() or card.state != "wait":
		return
	var el := real_t - _card_open_t
	if card.mode == "pick":
		# 像人一样先把东西一件件看一遍（截图 / GIF 里看得到「选中」是什么样子），再按策略选
		var look := int((el - 0.6) / 0.45)
		if look >= 0 and look < card.items.size() and card.sel != look and el < card_delay:
			card.sel = look
			card._refresh()
	if el < card_delay:
		return
	var pol := card_policy
	if pol == "mix":
		# 演示用：第一张卡烧掉，之后都留下
		pol = "burn" if stats.burned_personal == 0 and card.mode == "single" else "keep"
	if card.mode == "single":
		card.choose(pol)
	else:
		card.choose(pol, 0)


func _bot_step(dt: float) -> void:
	match bot:
		"none":
			_bot_press = false
		"random":
			_bot_timer -= dt
			if _bot_timer <= 0.0:
				_bot_press = not _bot_press
				_bot_timer = _rng.randf_range(0.15, 1.0) if _bot_press else _rng.randf_range(0.2, 1.6)
		"good":
			_plan_t -= dt
			if _plan_t <= 0.0:
				_plan_t = 0.1
				_bot_press = _plan(2.4)
		"okay":
			# 「还行的人」：反应慢（0.35 秒才改一次主意）、只看 1.2 秒远，四次里有一次走神乱按
			_plan_t -= dt
			if _plan_t <= 0.0:
				_plan_t = 0.35
				_bot_press = _plan(1.2) if _rng.randf() > 0.25 else _rng.randf() < 0.5


const _PLANS := [[false, 9.0], [true, 0.1], [true, 0.2], [true, 0.35], [true, 0.5], [true, 0.75], [true, 1.0],
	[true, 1.4], [true, 9.0], [false, 0.2], [false, 0.4], [false, 0.7], [false, 1.0], [false, 1.5]]


func _plan(H: float) -> bool:
	## 把每个按键计划往前模拟 2.4 秒（用和真飞船一样的 step），吃到光点 +，撞到 -，选最好的。
	var best := -1e9
	var best_press := false
	var h := 1.0 / 20.0
	var ceil_y: float = ship.ceiling
	for plan in _PLANS:
		var y: float = ship.position.y
		var v: float = ship.vy
		var score := 0.0
		var got := {}
		var t := 0.0
		var hit := false
		while t < H:
			var press: bool = plan[0] if t < plan[1] else not plan[0]
			var r := Ship.step(y, v, press, h, ceil_y, emergency)
			y = r.x
			v = r.y
			t += h
			var TT := T + t
			var c := Vector2(travel + SPEED * t + SHIP_X, y)
			if not hit and course.hit_at(TT, c, Ship.points_for_vy(v)) >= 0:
				score -= 100.0 * (1.0 - t / H * 0.5)
				hit = true
			for i in course.motes_near(TT, c, Course.MOTE_R - 2.0):
				if not got.has(i):
					got[i] = true
					score += 10.0 * (1.0 - t / H * 0.4)
			score -= absf(y - 140.0) * 0.004
		if score > best:
			best = score
			best_press = plan[0] if plan[1] > 0.0 else not plan[0]
	return best_press


# ---------------------------------------------------------------- 声音

func sfx(name: String, pitch := 1.0, vol := 0.0) -> void:
	for p in _sfx_pool:
		var ap: AudioStreamPlayer = p
		if not ap.playing:
			ap.stream = load("res://audio/sfx/flight_%s.wav" % name)
			ap.pitch_scale = pitch
			ap.volume_db = vol
			ap.play()
			return


# ---------------------------------------------------------------- 截图

func _snap_later(name: String, delay: float) -> void:
	if _snap == "" or _snapped.has(name):
		return
	_snapped[name] = true
	_pending_snaps.append([name, real_t + delay])


func _debug_capture() -> void:
	if _snap != "":
		for s in _pending_snaps.duplicate():
			if real_t >= s[1]:
				_pending_snaps.erase(s)
				_save(_snap.path_join(s[0] + ".png"))
				if s[0] == "end":
					if _quit:
						get_tree().quit()
	if _shot != "" and _shot_at >= 0.0 and real_t >= _shot_at:
		_save(_shot)
		get_tree().quit()
	if _frames != "" and real_t >= _f_from:
		_frame_i += 1
		if _frame_i % _f_every == 0:
			RenderingServer.force_draw(false)
			var img := get_viewport().get_texture().get_image()
			img.resize(960, 540, Image.INTERPOLATE_NEAREST)
			img.save_png(_frames.path_join("f_%04d.png" % _f_n))
			_f_n += 1
		if real_t >= _f_to:
			get_tree().quit()


func _save(path: String) -> void:
	RenderingServer.force_draw(false)
	get_viewport().get_texture().get_image().save_png(path)
