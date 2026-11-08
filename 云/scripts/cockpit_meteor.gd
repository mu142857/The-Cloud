extends Control
## 飞行一：大陨石砸中以后的过场（11-08 作者：「设计一个飞船冒烟，爆炸，颤抖的动画，符合现有美术风格，有一个永燃之木掉下去的画面」）。
## 接在 flight1_cruise（躲碎石最后那排躲不开的 meteor）后面、旁白「大陨石撞开了货舱。永燃之木从裂口掉了出去。」前面。
##
## 剧本：{"do": "cockpit_meteor"}，可选 "far_scale"（默认 0.75）。story_runner.gd 的 _cockpit_step 建它：await play(runner, st)。
## 全部用现成的美术 / 特效，不新画图：
##   船外远景 = cockpit_room 的 far_out / far_in（和躲碎石、往前一冲同一套 ship_out 图）；
##   烟、火星、碎片 = scripts/puffs.gd（开场坠毁飞船冒烟同一套硬边像素圆，颜色压暗、不抢画面）；
##   永燃之木 = art/level1/wood.png + wood_glow.png（森林里捡它时那张图和那圈加色光），光点用 puffs 的 glint。
##   爆炸闪光、裂口是这里按像素画的（整数坐标、4 档淡出，和碎石预告划痕、擦边火星一个画法）。
## 过程（约 7 秒，自动玩照真实时长）：
##   1）拉到船外（far_out，约 1.7 秒），船一直在小幅颤（镜头抖），警报声。
##   2）货舱（远景船靠后、偏下，HOLE）炸开：白点 → 暖色火球 → 断开的一圈火环；碎片往外崩、受重力掉；大晃 + 船往下一沉（ship_goal，
##      弹簧回弹 = 颤抖）。裂口画在船身上（黑洞 + 左上一圈翻起的亮边 + 一闪一闪的火边），之后一直冒烟、冒火星（往右后方拖）。
##   3）永燃之木从裂口崩出来：先往上弹一点，翻着（scale.x 来回，和 burn_pick 飘的那种翻法一样）往右后方落下去，身上那圈暖光一闪一闪，
##      身后拖一串光点；掉出画面下沿。
##   4）中途又炸两小下（裂口附近），每次小晃。木头掉出去以后停一下，拉回剖面（far_in），特效跟着远景层一起藏掉、删掉。
## 跳节拍（ff）/ 没有驾驶舱 / 远景图不在：只晃一下、闪一下，不拉远。F8 自测（dev_skip）：后面的等待全部跳过。

const PUFFS := preload("res://scripts/puffs.gd")
const WOOD := preload("res://art/level1/wood.png")
const WOOD_GLOW := preload("res://art/level1/wood_glow.png")

const FAR_K := 0.75
const HOLE := Vector2(0.71, 0.80)        # 货舱裂口在远景船图（不透明那块）里的位置：从左上角算的比例（机头朝左，货舱在后半截、偏下）
const GRAV := 72.0                       # 木头往下掉的重力（像素 / 秒²）
const WOOD_V := Vector2(26.0, -30.0)     # 木头崩出来的初速度（往右后方、先往上弹）
const WOOD_DRIFT := 9.0                  # 往右后方越飘越快（船在往左飞）
const SPIN := 6.5                        # 翻面快慢

# 爆炸的颜色（暖色和 puffs 的 ember 一套）
const C_WHITE := Color(1.0, 0.97, 0.88)
const C_CORE := Color("#ffe3a0")
const C_FIRE := Color("#f0a058")
const C_RED := Color("#b8482a")
const C_HOLE := Color("#0a0e0d")
const C_LIP := Color("#7d8a85")          # 翻起来的船皮（左上亮边）
const C_LIP_D := Color("#3b4542")

# 烟往右后方拖（船往左飞）：比开场坠毁的烟快、短；天是深青灰的，烟比开场那套亮一档才看得出来（离线预览 docs/陨石过场_预览.png 看过）
const P_SMOKE := {"vx": Vector2(26, 48), "vy": Vector2(-10, -2), "wind": 16.0, "grav": 0.0, "drag": 0.3,
	"r0": Vector2(1, 3), "r1": Vector2(4, 7), "life": Vector2(1.3, 2.3),
	"c0": Color(0.38, 0.4, 0.39, 0.9), "c1": Color(0.16, 0.19, 0.18, 0.0), "spread": Vector2(2, 2)}
const P_BURST := {"vx": Vector2(-30, 50), "vy": Vector2(-30, 10), "wind": 14.0, "grav": 0.0, "drag": 1.6,
	"r0": Vector2(3, 5), "r1": Vector2(5, 7), "life": Vector2(1.0, 2.0),
	"c0": Color(0.4, 0.41, 0.4, 0.9), "c1": Color(0.15, 0.17, 0.16, 0.0), "spread": Vector2(5, 3)}
const P_FIRE := {"vx": Vector2(14, 40), "vy": Vector2(-16, -2), "wind": 10.0, "grav": 0.0, "drag": 0.4,
	"r0": Vector2(1, 1), "r1": Vector2(1, 1), "life": Vector2(0.3, 0.8),
	"c0": Color(0.98, 0.72, 0.36, 0.95), "c1": Color(0.85, 0.35, 0.15, 0.0), "spread": Vector2(3, 2), "px": true}
const P_CHIP := {"vx": Vector2(-40, 70), "vy": Vector2(-70, -12), "wind": 12.0, "grav": 170.0, "drag": 0.3,
	"r0": Vector2(1, 1), "r1": Vector2(1, 1), "life": Vector2(0.9, 1.5), "hold": 0.5,
	"c0": Color(0.42, 0.46, 0.44, 1.0), "c1": Color(0.2, 0.22, 0.21, 0.0), "spread": Vector2(2, 2), "px": true}
const P_SPARK := {"vx": Vector2(-60, 80), "vy": Vector2(-60, 10), "wind": 0.0, "grav": 90.0, "drag": 1.2,
	"r0": Vector2(1, 1), "r1": Vector2(1, 1), "life": Vector2(0.25, 0.6),
	"c0": Color(1.0, 0.9, 0.6, 1.0), "c1": Color(0.95, 0.45, 0.2, 0.0), "spread": Vector2(1, 1), "px": true}
const P_TRAIL := {"vx": Vector2(4, 16), "vy": Vector2(-6, 2), "wind": 0.0, "grav": 0.0, "drag": 0.4,
	"r0": Vector2(1, 1), "r1": Vector2(1, 1), "life": Vector2(0.5, 1.1),
	"c0": Color(1.0, 0.82, 0.48, 0.9), "c1": Color(1.0, 0.6, 0.3, 0.0), "spread": Vector2(3, 1), "px": true}

# 裂口的形状（以 HOLE 为原点：每行 [dx 起点, dy, 宽]），黑洞；LIP = 左上翻起的亮边，EDGE = 会闪的火边
const HOLE_ROWS := [[-2, -3, 4], [-4, -2, 8], [-5, -1, 10], [-5, 0, 11], [-4, 1, 9], [-3, 2, 6], [-1, 3, 3]]
const LIP := [[-3, -4], [-2, -4], [-1, -4], [-5, -3], [-4, -3], [-6, -2], [-6, -1], [2, -3], [3, -2]]
const LIP_D := [[0, -4], [4, -2], [-6, 0], [5, -1]]
const EDGE := [[-5, 1], [-4, 2], [-2, 3], [2, 3], [3, 2], [5, 1], [6, 0], [5, -1], [4, -2], [-6, 0], [-1, -4]]

var runner: Node
var level: Node
var cockpit: Node2D
var _root: Node2D                        # 挂在驾驶舱远景层下（跟着世界走：镜头抖、船上下挪都一起动）
var _fx: Node2D                          # 爆炸闪光、裂口
var _puffs: Node2D
var _wood: Node2D
var _wood_glow: Sprite2D
var _wood_spr: Sprite2D
var _hole := Vector2.ZERO
var _holed := false
var _booms: Array = []                   # {pos, age, r}
var _t := 0.0
var _rattle := false                     # 一直小幅颤
var _skip := false
var _rng := RandomNumberGenerator.new()


func play(r: Node, st: Dictionary) -> String:
	runner = r
	level = r.level
	cockpit = r.world.cockpit
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_rng.seed = 811
	StoryState.clear_flag("flight1_wood_power")   # 11-08：永燃之木被砸掉——不管下面走哪条（跳节拍 / 没远景图），燃料条都不再「无限」（剧本后面那步 clear 照留）
	if r.ff or cockpit == null:
		return ""
	var k := float(st.get("far_scale", FAR_K))
	if not (k < 0.99 and cockpit.far_ready(k)):
		_shake(1.0, 5.0)                     # 远景图不在：原地晃一下就过
		_sfx("debris_bump", 0.0, 0.6)
		await _wait(1.2)
		return ""
	# ---- 1）拉到船外，一直在颤
	_rattle = true
	_sfx("alarm_broken", -14.0)
	_sfx("flight_rumble", -6.0, 0.8)
	cockpit.far_out(k, float(cockpit.FAR_SEC))
	var g := 0.0
	while cockpit.far_u() < 1.0 and g < 3.0 and not _skip:
		await StoryState.frame(get_tree())
		g += get_process_delta_time()
	var rect: Rect2 = cockpit.far_used_rect()
	_hole = (rect.position + rect.size * HOLE).round()
	_build()
	await _wait(0.35)
	# ---- 2）货舱炸开
	_boom(_hole, 15.0, true)
	_puffs.add_source("smoke", _hole + Vector2(1, -1), 10.0, P_SMOKE)
	_puffs.add_source("fire", _hole, 7.0, P_FIRE)
	await _wait(0.4)
	# ---- 3）永燃之木崩出来
	_eject()
	await _wait(0.6)
	_boom(_hole + Vector2(-17, -5), 8.0, false)
	await _wait(0.75)
	_boom(_hole + Vector2(9, 3), 7.0, false)
	_puffs.add_source("smoke", _hole + Vector2(1, -1), 14.0, P_SMOKE)       # 第二、三下以后烟更浓
	var w := 0.0
	while is_instance_valid(_wood) and _wood.visible and w < 3.5 and not _skip:
		await StoryState.frame(get_tree())
		w += get_process_delta_time()
	await _wait(0.9)
	# ---- 4）拉回剖面
	_rattle = false
	cockpit.far_in(float(cockpit.FAR_SEC))
	g = 0.0
	while cockpit.far_u() > 0.0 and g < 3.0 and not _skip:
		await StoryState.frame(get_tree())
		g += get_process_delta_time()
	if _skip:
		cockpit.far_snap(false)
	cockpit.ship_goal = 0.0
	print("COCKPIT meteor cutscene: hole=%s k=%.2f" % [str(_hole), k])
	if is_instance_valid(_root):
		_root.queue_free()
	return ""


func _build() -> void:
	_root = Node2D.new()
	_root.name = "MeteorFx"
	cockpit.out_layer().add_child(_root)     # 远景船图后面加进来 = 画在船上面
	_fx = Node2D.new()
	_fx.draw.connect(_draw_fx)
	_root.add_child(_fx)
	_puffs = PUFFS.new()
	_root.add_child(_puffs)
	_wood = Node2D.new()
	_wood.visible = false
	_root.add_child(_wood)
	_wood_glow = Sprite2D.new()
	_wood_glow.texture = WOOD_GLOW
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	_wood_glow.material = m
	_wood_glow.position = Vector2(0, -1)
	_wood.add_child(_wood_glow)
	_wood_spr = Sprite2D.new()
	_wood_spr.texture = WOOD
	_wood_spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_wood.add_child(_wood_spr)


# ======================================================================= 每帧
var _wood_v := Vector2.ZERO
var _wood_t := 0.0
var _trail_acc := 0.0
var _rattle_t := 0.0


func _process(delta: float) -> void:
	if cockpit == null:
		return
	_t += delta
	if _rattle and level._shake <= 0.05:
		_rattle_t -= delta
		if _rattle_t <= 0.0:
			_rattle_t = 0.22
			_shake(0.3, 1.5)                     # 一直在颤（大晃的时候不压它）
	for b in _booms:
		b["age"] = float(b["age"]) + delta
	_booms = _booms.filter(func(b): return float(b["age"]) < 0.7)
	if is_instance_valid(_wood) and _wood.visible:
		_wood_step(delta)
	if is_instance_valid(_fx):
		_fx.queue_redraw()


func _wood_step(delta: float) -> void:
	_wood_t += delta
	_wood_v.y += GRAV * delta
	_wood_v.x += WOOD_DRIFT * delta
	var p := _wood.get_meta("p", _wood.position) as Vector2
	p += _wood_v * delta
	_wood.set_meta("p", p)
	_wood.position = p.round()
	# 翻着掉：只翻 x（竖直方向像素不糊），最窄也留 1/4，不会整个消失
	var c := cos(_wood_t * SPIN)
	_wood_spr.scale = Vector2((1.0 if c >= 0.0 else -1.0) * maxf(0.25, absf(c)), 1.0)
	_wood_glow.scale = Vector2.ONE * (1.25 + 0.15 * sin(_wood_t * 11.0))
	_wood_glow.modulate.a = 0.75 + 0.25 * sin(_wood_t * 17.0)
	_trail_acc += delta
	while _trail_acc >= 0.05:
		_trail_acc -= 0.05
		_puffs.burst(_wood.position, 1, P_TRAIL)
	if p.y > 300.0:
		_wood.visible = false


## 永燃之木从裂口崩出来
func _eject() -> void:
	_wood.set_meta("p", _hole + Vector2(2, -2))
	_wood.position = _hole + Vector2(2, -2)
	_wood_v = WOOD_V
	_wood_t = 0.0
	_wood.visible = true
	_puffs.burst(_hole, 8, P_SPARK)
	_puffs.burst(_hole, 6, P_TRAIL)
	_sfx("fire_flare", -6.0, 1.3)


## 炸一下：闪光 + 火环 + 碎片 + 烟团 + 晃
func _boom(at: Vector2, r: float, big: bool) -> void:
	_booms.append({"pos": at.round(), "age": 0.0, "r": r})
	_puffs.burst(at, 14 if big else 6, P_CHIP)
	_puffs.burst(at, 12 if big else 6, P_SPARK)
	_puffs.burst(at, 10 if big else 4, P_BURST)
	if big:
		_holed = true
		_shake(1.1, 5.0)
		cockpit.ship_goal = 8.0              # 往下一沉，弹簧回弹 = 颤；不在躲碎石时它自己慢慢回中间
		_sfx("debris_bump", 2.0, 0.55)
		_sfx("metal_clank", -4.0, 0.7)
		_sfx("fire_flare", -2.0, 0.8)
	else:
		_shake(0.5, 3.0)
		cockpit.ship_goal = cockpit.ship_goal + 3.0
		_sfx("debris_bump", -3.0, 0.8)
		_sfx("fire_flare", -8.0, 1.0)


# ======================================================================= 画
func _draw_fx() -> void:
	if _holed:
		_draw_hole()
	for b in _booms:
		_draw_boom(b["pos"], float(b["age"]), float(b["r"]))


## 船身上的裂口：黑洞、左上翻起的亮边、一闪一闪的火边
func _draw_hole() -> void:
	var o := _hole
	for row in HOLE_ROWS:
		_fx.draw_rect(Rect2(o + Vector2(row[0], row[1]), Vector2(row[2], 1)), C_HOLE)
	for p in LIP:
		_fx.draw_rect(Rect2(o + Vector2(p[0], p[1]), Vector2.ONE), C_LIP)
	for p in LIP_D:
		_fx.draw_rect(Rect2(o + Vector2(p[0], p[1]), Vector2.ONE), C_LIP_D)
	var tick := int(_t * 10.0)                   # 火边 0.1 秒换一次（不是每帧乱闪）
	for i in EDGE.size():
		var h := (tick * 7 + i * 13) % 5
		if h == 0:
			continue
		var c := C_CORE if h == 4 else (C_FIRE if h >= 2 else C_RED)
		_fx.draw_rect(Rect2(o + Vector2(EDGE[i][0], EDGE[i][1]), Vector2.ONE), c)


## 一次爆炸：0~0.06 白点，~0.2 火球长大，之后一圈断开的火环往外扩、4 档淡掉
func _draw_boom(at: Vector2, a: float, r: float) -> void:
	if a < 0.06:
		_disc(at, 3.0, C_WHITE)
		return
	if a < 0.22:
		var u := (a - 0.06) / 0.16
		var rr := lerpf(3.0, r * 0.6, u)
		_disc(at, rr, C_FIRE)
		_disc(at, rr * 0.6, C_CORE)
		_disc(at, maxf(1.0, rr * 0.25), C_WHITE)
		return
	var u2 := clampf((a - 0.22) / 0.48, 0.0, 1.0)
	var alpha := 1.0 - floorf(u2 * 4.0) / 4.0
	var rad := lerpf(r * 0.6, r, sqrt(u2))
	var col := C_FIRE.lerp(C_RED, u2)
	col.a = alpha
	var n := int(rad * 4.0)
	for i in n:
		if i % 4 == 3:
			continue                             # 断开的环
		var ang := TAU * float(i) / float(n)
		_fx.draw_rect(Rect2((at + Vector2(cos(ang), sin(ang)) * rad).round(), Vector2.ONE), col)
	if u2 < 0.5:
		var cc := C_CORE
		cc.a = 1.0 - floorf(u2 * 2.0 * 4.0) / 4.0
		_disc(at, maxf(1.0, r * 0.3 * (1.0 - u2 * 2.0)), cc)


## 像素实心圆（一行一行画，整数坐标）
func _disc(at: Vector2, r: float, c: Color) -> void:
	var ri := int(roundf(r))
	for y in range(-ri, ri + 1):
		var w := int(floorf(sqrt(maxf(0.0, r * r - float(y * y)))))
		_fx.draw_rect(Rect2(at + Vector2(-w, y), Vector2(w * 2 + 1, 1)), c)


# ======================================================================= 杂项
func _shake(sec: float, amp: float) -> void:
	if level._shake > 0.05 and level._shake_amp > amp:
		return                                   # 正在大晃：小的不盖掉它
	level._shake = sec
	level._shake_amp = amp


func _wait(sec: float) -> void:
	var t := 0.0
	while t < sec and not _skip:
		await StoryState.frame(get_tree())
		t += get_process_delta_time()


## F8 自测：后面的等待全跳过
func dev_skip() -> void:
	_skip = true


func _sfx(name: String, db: float, pitch := 1.0) -> void:
	var p := "res://audio/sfx/%s.wav" % name
	if not ResourceLoader.exists(p):
		return
	var a := AudioStreamPlayer.new()
	a.stream = load(p)
	a.volume_db = db
	a.pitch_scale = pitch
	a.bus = "SFX" if AudioServer.get_bus_index("SFX") >= 0 else "Master"
	add_child(a)
	a.play()


func _exit_tree() -> void:
	if is_instance_valid(_root):
		_root.queue_free()
