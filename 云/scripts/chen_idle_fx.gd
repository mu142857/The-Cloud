extends Node2D
## 晨站着不动时的一点「灵气」：站定 STILL_DELAY 秒后慢慢出现，一跑起来就不再生成（已经出来的自己飘完、萤火虫飞走）。
## chen.gd 在 _env_ready 里建一个，放在精灵前面；它自己再在精灵最后面放一个 back 层（画绕到她身后的那半：萤火虫、云丝）。
## 坐标是世界坐标（top_level），粒子出来以后留在原地，不跟着晨走。每颗都是整像素、硬边，半透明，不描边。
##
##   通用（所有场景）：白发边上偶尔飘起一颗 1 像素的淡光点，慢慢往上、轻轻左右摆、几秒内淡掉。颜色 = 场景的 halo 色。
##                    斗篷下摆拖在后面的那条尾巴偶尔被风带起一两根「布丝」，往后飘一点就没了。
##   forest：一两只萤火虫慢慢飞过来，绕着她转几圈（转到身后就被斗篷挡住），再飞走。
##   river / city：天冷，嘴边每隔 3~4 秒呵出一小团白气，往前上方散开。城市的肩上溅雨在 chen_fx.gd，不变。
##   underwater：嘴边隔一阵冒一串小气泡（用场景里晨的气泡节点 chen.step_bubbles 的 emit()）。
##   cloud：脚边几缕淡紫的云丝慢慢从她前面、后面绕过去。
## 调：下面各段常量；颜色（除了 halo）都在这里。开销：同时最多 MAX 颗 + 2 只萤火虫。
## 截图对比：命令行 -- --idle_fx=0 整个关掉。

const MAX := 40
const STILL_DELAY := 0.6           # 站定多久以后开始出

# ---- 通用：头发散光
const MOTE_EVERY := Vector2(1.0, 2.2)    # 隔几秒飘起一颗
const MOTE_MAX := 3                      # 同时最多几颗
const MOTE_LIFE := Vector2(2.6, 3.8)
const MOTE_RISE := Vector2(4.0, 6.5)     # 往上飘的速度（像素 / 秒）
const MOTE_SWAY := 1.0                   # 左右摆的幅度（像素）
const MOTE_A := 1.0                      # 最亮时的不透明度
const MOTE_WHITE := 0.3                  # 颜色 = 场景 halo 色往白靠这么多，再乘 MOTE_DIM（比白发暗一档、比背景亮得多）
const MOTE_DIM := 0.9
const MOTE_R := Vector2(5.5, 7.5)        # 从头中心往外多远出生（白发外沿）

# ---- 通用：下摆的布丝
const THREAD_EVERY := Vector2(2.5, 5.5)
## 下摆边上几个点（帧里的像素坐标，美术朝右：左边 x 小的是拖在身后的尾巴）
const HEM := [Vector2(15, 54), Vector2(17, 53), Vector2(19, 52), Vector2(21, 50)]
const THREAD_A := 0.7
const THREAD_TINT := 0.45                # 布丝颜色 = 场景的斗篷偏色（tint）往受光边色（rim）靠这么多，比斗篷亮

# ---- forest：萤火虫
const FLY_TEX := preload("res://art/fx/firefly.png")
const FLY_COLOR := Color(1.0, 0.86, 0.32)
const FLY_FIRST := Vector2(2.0, 3.5)     # 站定后第一只多久飞来
const FLY_NEXT := Vector2(3.0, 7.0)      # 一只走了（或第二只）隔多久再来
const FLY_STAY := Vector2(6.0, 10.0)     # 绕多久
const FLY_ORBIT := Vector2(14.0, 5.0)    # 绕的椭圆半径（x 宽、y 扁：下半圈在她前面，上半圈在身后）
const FLY_SPEED := 1.1                   # 绕的角速度（弧度 / 秒）
const FLY_PEAK := 0.9
const FLY_FLY := 18.0                    # 飞来、飞走的速度（像素 / 秒）
const FLY_FADE := 2.2                    # 飞走时几秒淡完

# ---- river / city：呵气
const BREATH_EVERY := Vector2(3.0, 4.0)
const MOUTH := Vector2(7, 4)             # 嘴相对头中心（美术朝右）
const BREATH := Color(0.8, 0.84, 0.92, 0.6)
const BREATH_LEN := 0.5                  # 一口气呼多久（秒）
const BREATH_GAP := 0.05                 # 呼气时每隔几秒出一颗（0.5 / 0.05 = 10 颗）

# ---- underwater：气泡
const BUBBLE_EVERY := Vector2(3.5, 5.5)

# ---- cloud：脚边云丝
## 每缕是绕着她脚边一个扁椭圆转的一小段弧（头一颗亮，后面拖几颗越来越淡）：转到前半圈画在斗篷前面，后半圈被斗篷挡住
const WISP_EVERY := Vector2(0.9, 1.6)
const WISP_MAX := 4
const WISP_RX := Vector2(14.0, 20.0)     # 椭圆半宽（下摆宽约 25）
const WISP_RY := 3.0                     # 椭圆半高：扁，看起来是平躺在云面上的一圈
const WISP_Y := Vector2(1.0, 5.0)        # 圈的中心在脚底往上几像素（下摆那一段）
const WISP_W := Vector2(0.5, 0.8)        # 转的角速度（弧度 / 秒）
const WISP_TRAIL := Vector2i(10, 16)     # 拖多长（像素）
const WISP := Color(0.78, 0.7, 0.9, 0.5)
const WISP_HI := Color(0.96, 0.84, 0.9, 0.7)   # 领头那颗

var chen: Node2D                  # chen.gd 设

var _back: Node2D
var _p: Array[Dictionary] = []
var _flies: Array[Dictionary] = []
var _rng := RandomNumberGenerator.new()
var _still := 0.0                 # 站着不动多久了
var _mote_t := 0.0
var _thread_t := 0.0
var _fly_t := 0.0
var _breath_t := 0.0
var _bubble_t := 0.0
var _wisp_t := 0.0
var _exhale := 0.0                # 正在呵气：还剩几秒
var _dirty := false               # 上一帧还有东西：这一帧再画一次（清掉）
var _t := 0.0


func _ready() -> void:
	top_level = true
	if "--idle_fx=0" in OS.get_cmdline_user_args():      # 截图对比用：关掉
		set_process(false)
	_rng.seed = 1771
	_back = Node2D.new()
	_back.name = "IdleFxBack"
	_back.top_level = true
	_back.draw.connect(_draw_back)
	chen.add_child.call_deferred(_back)
	chen.move_child.call_deferred(_back, 0)
	_reset_timers()


func _reset_timers() -> void:
	_mote_t = _rng.randf_range(0.0, 0.6)
	_thread_t = _rng.randf_range(1.5, 3.0)
	_fly_t = _rng.randf_range(FLY_FIRST.x, FLY_FIRST.y)
	_breath_t = _rng.randf_range(0.6, 1.6)
	_bubble_t = _rng.randf_range(0.8, 2.0)
	_wisp_t = 0.0


func _kind() -> String:
	return chen._env_cfg.get("fx", "")


func _is_still() -> bool:
	var a := String(chen.spr.animation)
	return chen._upright() and chen._vel == 0.0 and (a.begins_with("idle") or a.begins_with("front"))


## 帧里的像素坐标（美术朝右）→ 世界坐标
func _frame_world(p: Vector2) -> Vector2:
	return chen.to_global(chen._frame_to_local(p))


func _head() -> Vector2:
	return _frame_world(chen._head_px())


func _add(d: Dictionary) -> void:
	if _p.size() >= MAX:
		_p.pop_front()
	var base := {"vel": Vector2.ZERO, "age": 0.0, "grav": 0.0, "drag": 0.0, "size": Vector2.ONE, "sway": 0.0,
		"swf": 1.0, "ph": _rng.randf() * TAU, "fin": 0.1, "back": false, "kind": "dot", "tw": 0.0}
	base.merge(d, true)
	_p.append(base)


func _count(kind: String) -> int:
	var n := 0
	for p in _p:
		if p.kind == kind:
			n += 1
	return n


func _process(delta: float) -> void:
	_t += delta
	var kind := _kind()
	var still := kind != "" and _is_still()
	if still:
		_still += delta
	else:
		if _still > 0.0:
			_reset_timers()
		_still = 0.0
	if _still > STILL_DELAY:
		_spawn(kind, delta)
	_update_flies(delta, still)
	var i := 0
	while i < _p.size():
		var p := _p[i]
		p.age += delta
		if p.age >= p.life:
			_p.remove_at(i)
			continue
		var v: Vector2 = p.vel
		v.y += p.grav * delta
		v *= exp(-p.drag * delta)
		p.vel = v
		p.pos += v * delta
		i += 1
	if _p.size() > 0 or _flies.size() > 0 or _dirty:
		queue_redraw()
		_back.queue_redraw()
		_dirty = _p.size() > 0 or _flies.size() > 0


func _spawn(kind: String, delta: float) -> void:
	var f: int = chen.facing
	# 头发散光
	_mote_t -= delta
	if _mote_t <= 0.0:
		_mote_t = _rng.randf_range(MOTE_EVERY.x, MOTE_EVERY.y)
		if _count("mote") < MOTE_MAX:
			var a := _rng.randf_range(-PI * 0.92, -PI * 0.08)     # 上半圈
			var p := _head() + Vector2(cos(a), sin(a) * 1.1) * _rng.randf_range(MOTE_R.x, MOTE_R.y)
			var h: Color = chen._env_cfg.get("halo", Color.WHITE)
			var c := h.lerp(Color.WHITE, MOTE_WHITE) * MOTE_DIM
			c.a = MOTE_A
			_add({"kind": "mote", "pos": p, "vel": Vector2(_rng.randf_range(-1.5, 1.5), -_rng.randf_range(MOTE_RISE.x, MOTE_RISE.y)),
				"life": _rng.randf_range(MOTE_LIFE.x, MOTE_LIFE.y), "c": c, "sway": MOTE_SWAY, "swf": _rng.randf_range(1.2, 2.0),
				"fin": 0.15, "tw": 0.2})
	# 下摆的布丝：往身后飘
	_thread_t -= delta
	if _thread_t <= 0.0:
		_thread_t = _rng.randf_range(THREAD_EVERY.x, THREAD_EVERY.y)
		var hp: Vector2 = HEM[_rng.randi() % HEM.size()]
		var tc: Color = chen._env_cfg.get("tint", Color.GRAY)
		var rc: Color = tc.lerp(chen._env_cfg.get("rim", Color.WHITE), THREAD_TINT)
		_add({"kind": "thread", "pos": _frame_world(hp) + Vector2(-f, 0), "vel": Vector2(-f * _rng.randf_range(5.0, 9.0), _rng.randf_range(-5.0, -2.0)),
			"life": _rng.randf_range(1.1, 1.7), "c": Color(rc.r, rc.g, rc.b, THREAD_A), "grav": 3.0, "drag": 0.6,
			"size": Vector2(2, 1) if _rng.randf() < 0.5 else Vector2.ONE, "sway": 0.6, "swf": 1.5})
	match kind:
		"river", "city":
			_breathe(delta, f)
		"underwater":
			_bubble_t -= delta
			if _bubble_t <= 0.0 and String(chen.spr.animation) != "idle_eye":
				_bubble_t = _rng.randf_range(BUBBLE_EVERY.x, BUBBLE_EVERY.y)
				var b: Node2D = chen.step_bubbles as Node2D
				if b != null and b.has_method("emit"):
					var m := _head() + Vector2(MOUTH.x * f, MOUTH.y)
					b.emit(b.to_local(m), _rng.randi_range(2, 4), 0.5)
		"cloud":
			_wisp_t -= delta
			if _wisp_t <= 0.0:
				_wisp_t = _rng.randf_range(WISP_EVERY.x, WISP_EVERY.y)
				if _count("wisp") < WISP_MAX:
					_spawn_wisp()


func _breathe(delta: float, f: int) -> void:
	_breath_t -= delta
	if _breath_t <= 0.0 and String(chen.spr.animation) != "idle_eye":
		_breath_t = _rng.randf_range(BREATH_EVERY.x, BREATH_EVERY.y)
		_exhale = BREATH_LEN
	if _exhale > 0.0:
		var before := _exhale
		_exhale -= delta
		# 按时间均匀地吐；越到后面气越弱（飞得慢、近），前面的已经散开，看起来是一小团往前上方化开
		var n := int(before / BREATH_GAP) - int(maxf(_exhale, 0.0) / BREATH_GAP)
		var push := 0.5 + 0.5 * clampf(_exhale / BREATH_LEN, 0.0, 1.0)
		for k in n:
			var m := _head() + Vector2(MOUTH.x * f, MOUTH.y) + Vector2(f * _rng.randi_range(0, 1), _rng.randi_range(0, 1))
			var c := BREATH
			c.a *= _rng.randf_range(0.75, 1.0)
			_add({"kind": "breath", "pos": m, "vel": Vector2(f * _rng.randf_range(9.0, 17.0) * push, _rng.randf_range(-7.0, -1.0)),
				"life": _rng.randf_range(1.0, 1.6), "c": c, "grav": -4.0, "drag": 1.4,
				"size": Vector2(2, 1) if _rng.randf() < 0.35 else Vector2.ONE, "sway": 0.6, "swf": 0.8, "fin": 0.06})


func _spawn_wisp() -> void:
	var w := _rng.randf_range(WISP_W.x, WISP_W.y) * (1.0 if _rng.randf() < 0.5 else -1.0)
	_add({"kind": "wisp", "pos": chen.to_global(Vector2(0, -_rng.randf_range(WISP_Y.x, WISP_Y.y))),
		"life": _rng.randf_range(3.0, 4.5), "c": WISP, "fin": 0.25, "th": _rng.randf() * TAU, "w": w,
		"rx": _rng.randf_range(WISP_RX.x, WISP_RX.y), "n": _rng.randi_range(WISP_TRAIL.x, WISP_TRAIL.y)})


# ---------------------------------------------------------------- 萤火虫
func _update_flies(delta: float, still: bool) -> void:
	var center := chen.to_global(Vector2(0, -26))
	if still and _still > STILL_DELAY and _kind() == "forest":
		_fly_t -= delta
		if _fly_t <= 0.0:
			_fly_t = _rng.randf_range(FLY_NEXT.x, FLY_NEXT.y)
			if _flies.size() < 2:
				_new_fly(center)
	var i := 0
	while i < _flies.size():
		var fl := _flies[i]
		fl.age += delta
		if not still and fl.state != "out":
			_leave(fl, center)
		match fl.state:
			"in":
				# 慢慢飞到椭圆上那一点（这时候不转），到了就开始绕
				var target := _orbit_point(fl, center)
				fl.pos += (target - fl.pos).limit_length(FLY_FLY * delta)
				if fl.pos.distance_to(target) < 1.5:
					fl.state = "orbit"
			"orbit":
				fl.th += fl.w * delta
				fl.pos = fl.pos.lerp(_orbit_point(fl, center), 1.0 - exp(-4.0 * delta))
				if fl.age > fl.stay:
					_leave(fl, center)
			"out":
				fl.out_age += delta
				fl.pos += fl.exit * lerpf(FLY_FLY * 0.5, FLY_FLY * 1.4, minf(fl.out_age / 1.5, 1.0)) * delta
				if fl.out_age > FLY_FADE:
					_flies.remove_at(i)
					continue
		i += 1


func _orbit_point(fl: Dictionary, center: Vector2) -> Vector2:
	var hy := center.y + sin(fl.age * 0.37 + fl.ph) * 6.0      # 绕的高度慢慢变：胸口到头边
	return Vector2(center.x + cos(fl.th) * fl.rx, hy + sin(fl.th) * fl.ry)


func _leave(fl: Dictionary, center: Vector2) -> void:
	fl.state = "out"
	fl.out_age = 0.0
	var s := signf(fl.pos.x - center.x)
	if s == 0.0:
		s = 1.0
	fl.exit = Vector2(s, -0.5).normalized()


func _new_fly(center: Vector2) -> void:
	var s := -1.0 if _rng.randf() < 0.5 else 1.0
	var w := FLY_SPEED * _rng.randf_range(0.8, 1.2) * (1.0 if _rng.randf() < 0.5 else -1.0)
	_flies.append({"pos": center + Vector2(s * _rng.randf_range(50.0, 70.0), _rng.randf_range(-30.0, -10.0)),
		"th": 0.0 if s > 0 else PI, "w": w, "rx": FLY_ORBIT.x * _rng.randf_range(0.85, 1.15), "ry": FLY_ORBIT.y,
		"age": 0.0, "stay": _rng.randf_range(FLY_STAY.x, FLY_STAY.y), "state": "in", "out_age": 0.0,
		"exit": Vector2.ZERO, "ph": _rng.randf() * TAU, "bf": _rng.randf_range(0.3, 0.5)})


func _fly_alpha(fl: Dictionary) -> float:
	var b := 0.6 + 0.4 * sin(fl.age * fl.bf * TAU + fl.ph)
	var a := FLY_PEAK * b * clampf(fl.age / 1.0, 0.0, 1.0)
	if fl.state == "out":
		a *= clampf(1.0 - fl.out_age / FLY_FADE, 0.0, 1.0)
	return a


func _fly_behind(fl: Dictionary) -> bool:
	# 椭圆上半圈（sin < 0）在她身后；飞来、飞走的路上不算
	return fl.state == "orbit" and sin(fl.th) < -0.15


# ---------------------------------------------------------------- 画
func _draw() -> void:
	_draw_layer(self, false)


func _draw_back() -> void:
	_draw_layer(_back, true)


func _draw_layer(ci: CanvasItem, back: bool) -> void:
	for p in _p:
		if bool(p.back) != back and p.kind != "wisp":
			continue
		var k: float = p.age / p.life
		var a := clampf(k / maxf(p.fin, 0.001), 0.0, 1.0) * (1.0 - k * k)
		if p.tw > 0.0:
			a *= 1.0 - p.tw + p.tw * sin(p.age * 5.0 + p.ph)
		var c: Color = p.c
		c.a *= a
		var pos: Vector2 = p.pos
		if p.sway > 0.0:
			pos.x += sin(p.age * p.swf * TAU * 0.5 + p.ph) * p.sway
		pos = pos.round()
		if p.kind == "wisp":
			_draw_wisp(ci, back, p, a)
		else:
			ci.draw_rect(Rect2(pos, p.size), c)
	var half := FLY_TEX.get_size() / 2.0
	for fl in _flies:
		if _fly_behind(fl) != back:
			continue
		var c := FLY_COLOR
		c.a = _fly_alpha(fl)
		var j := Vector2(sin(fl.age * 2.3 + fl.ph), cos(fl.age * 1.7 + fl.ph))      # 自己的一点小颤
		ci.draw_texture(FLY_TEX, (fl.pos + j - half).round(), c)


func _draw_wisp(ci: CanvasItem, back: bool, p: Dictionary, a: float) -> void:
	# 一段弧：从领头那颗往回取 n 颗（每颗隔约 1 像素，连成线），每颗按自己在椭圆上的位置决定画在前还是后
	var th: float = p.th + p.w * p.age
	var n: int = p.n
	var step: float = -signf(p.w) * 1.0 / p.rx
	var seen := {}
	for j in n:
		var t := th + step * j
		if (sin(t) < 0.0) != back:
			continue
		var q: Vector2 = (p.pos + Vector2(cos(t) * p.rx, sin(t) * WISP_RY)).round()
		if seen.has(q):
			continue
		seen[q] = true
		var c: Color = WISP_HI if j == 0 else WISP
		c.a *= a * (1.0 - float(j) / n)
		ci.draw_rect(Rect2(q, Vector2.ONE), c)
