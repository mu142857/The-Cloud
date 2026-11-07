extends CanvasLayer
## 结局「倔强的灵魂」（11-07 作者）：c1_loop.gd 里一直不肯奔跑，「出不去」那句出来以后还是只往前走 → 这里。
##   左边一团黑里伸出回忆的触手（画法、颜色、节数照 flashback.gd 的 _draw_tentacles / _spine / _tentacle，同一种触手），
##   越来越快地追上来，心跳越来越快越来越响，森林的鸟叫和配乐退下去；
##   触手尖碰到晨之前一帧：整屏一下子黑掉、声音全停（不演被卷住）→ 成就「倔强的灵魂」（flag c1_stubborn）弹出 → 几秒后回标题，重新开始。
## 画在屏幕坐标里（第 9 层：森林和晨之上、暗角 / 闪电冷光 Overlay 之下）。

const CHASE_SEC := 7.5                     # 触手从画面外追到她背后要多久（越来越快）
const TOUCH_GAP := 20.0                    # 触手尖离她身子中线还有这么远就黑掉（「碰到之前」）
const HOLD_BLACK := 4.2                    # 黑掉以后停多久回标题（成就那张卡 0.25 + 2.5 + 0.55 秒）
const HEART := "res://audio/sfx/heartbeat.mp3"
const HEART_DB := Vector2(-22.0, -8.0)
const HEART_GAP := Vector2(1.05, 0.34)     # 两下心跳隔多久：远 → 近
# 触手（flashback.gd 同一套）
const SHADE_C := Color(0.02, 0.025, 0.03)
const T_INK := Color8(3, 4, 6)
const T_BODY := Color8(9, 12, 14)
const T_SHEEN := Color8(40, 52, 58)
const T_RIM := Color8(104, 124, 130)
const TN := 26
const T_ROOT := -46.0
const TENT := [                            # [根的 y（屏幕）, 长度系数, 起始角, 根的半粗, 相位, 尖卷的方向和多少]
	[86.0, 0.78, 0.30, 12.0, 5.6, 2.8],
	[114.0, 0.97, -0.02, 17.0, 0.0, 2.3],
	[144.0, 1.06, 0.06, 22.0, 1.7, -2.5],
	[174.0, 1.00, -0.04, 19.0, 3.1, 2.6],
	[198.0, 1.08, -0.10, 24.0, 4.4, -2.2],
	[220.0, 0.92, -0.16, 16.0, 2.3, 2.5],
	[240.0, 0.70, -0.30, 12.0, 0.9, -2.6],
]

var loop: Node
var level: Node2D
var _draw: Node2D
var _t := 0.0
var _k := 0.0                              # 追的进度 0..1
var _front := T_ROOT                       # 触手尖（最前面那条）的屏幕 x
var _a := 0.0
var _heart: AudioStreamPlayer
var _beat_in := 0.6
var _done := false


func _ready() -> void:
	layer = 9
	_draw = Node2D.new()
	_draw.draw.connect(_on_draw)
	add_child(_draw)
	if ResourceLoader.exists(HEART):
		_heart = AudioStreamPlayer.new()
		_heart.stream = load(HEART)
		_heart.bus = "SFX"
		_heart.volume_db = HEART_DB.x
		add_child(_heart)
	(load("res://scripts/bgm.gd") as GDScript).get_bgm(get_tree()).stop(3.0)
	if level.get("_rain") != null:
		level._fade_db(level._rain, -34.0, 4.0)
	print("STUBBORN_END start")


func _chen_sx() -> float:
	return level.chen.get_global_transform_with_canvas().origin.x


func _process(delta: float) -> void:
	if _done:
		return
	_t += delta
	_a = minf(1.0, _a + delta / 0.8)
	_k = minf(1.0, _k + delta / CHASE_SEC)
	var target := _chen_sx() - TOUCH_GAP
	_front = lerpf(T_ROOT, target, _k * _k * (3.0 - 2.0 * _k) * 0.35 + _k * _k * 0.65)   # 先慢慢伸出来，越追越快
	if _heart != null:
		_beat_in -= delta
		if _beat_in <= 0.0:
			_beat_in = lerpf(HEART_GAP.x, HEART_GAP.y, _k)
			_heart.volume_db = lerpf(HEART_DB.x, HEART_DB.y, _k)
			_heart.play()
	_draw.queue_redraw()
	if _front >= target - 0.5:
		_cut()


## 碰到之前：一下子黑掉，什么都停
func _cut() -> void:
	_done = true
	print("STUBBORN_END cut")
	level.fade.color.a = 1.0
	visible = false
	if _heart != null:
		_heart.stop()
	if level.get("_rain") != null:
		level._fade_db(level._rain, -60.0, 0.05)
	(load("res://scripts/bgm.gd") as GDScript).get_bgm(get_tree()).stop(0.05)
	level.chen.auto_dir = 0.0
	StoryState.set_flag("c1_stubborn")         # 成就「倔强的灵魂」：level_forest 下一帧按 data/achievements.json 弹卡（第 58 层，在黑幕上面）
	get_tree().create_timer(HOLD_BLACK, false).timeout.connect(func():
		level.title_after_credits())         # 回标题 = 重新开始（和全剧终、设置里的「返回标题」同一条路）


# ----------------------------------------------------------------------- 画
func _on_draw() -> void:
	if _a <= 0.0:
		return
	_draw.modulate.a = _a
	# 左边一团黑：触手从这里伸出来，跟着触手往前漫
	var edge := maxf(0.0, _front - 70.0)
	_draw.draw_rect(Rect2(0, 0, edge, 270), SHADE_C)
	for i in 12:
		var x := edge + i * 6.0
		_draw.draw_rect(Rect2(x, 0, 6, 270), Color(SHADE_C, 1.0 - float(i + 1) / 13.0))
	var bx := T_ROOT
	for d: Array in TENT:
		var reach := maxf(20.0, (_front - bx) * float(d[1]))
		var ph := float(d[4])
		var curl := float(d[5]) * (0.75 + 0.25 * sin(_t * 1.3 + ph))
		_tentacle(_spine(Vector2(bx, float(d[0])), reach / 0.86, float(d[2]), ph, curl, 0.42), float(d[3]))


func _spine(b: Vector2, length: float, a0: float, ph: float, curl: float, amp: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	pts.resize(TN + 1)
	var p := b
	pts[0] = p
	var ds := length / float(TN)
	for i in range(1, TN + 1):
		var s := float(i) / float(TN)
		var a := a0 + amp * sin(2.4 * PI * s - _t * 2.2 + ph) * (0.25 + 0.75 * s) + curl * pow(smoothstep(0.62, 1.0, s), 1.6)
		p += Vector2(cos(a), sin(a)) * ds
		pts[i] = p
	return pts


func _tentacle(pts: PackedVector2Array, thick: float) -> void:
	var n := pts.size() - 1
	var lp := PackedVector2Array()
	var rp := PackedVector2Array()
	var wd := PackedFloat32Array()
	lp.resize(n + 1)
	rp.resize(n + 1)
	wd.resize(n + 1)
	for i in n + 1:
		var s := float(i) / float(n)
		var dv := pts[mini(n, i + 1)] - pts[maxi(0, i - 1)]
		var nr := Vector2(-dv.y, dv.x).normalized()
		var w := thick * pow(1.0 - s, 1.15) + 0.7
		wd[i] = w
		lp[i] = pts[i] + nr * w
		rp[i] = pts[i] - nr * w
	for i in n:
		_quad(lp[i], lp[i + 1], rp[i + 1], rp[i], T_BODY)
	for i in n:
		var s := float(i) / float(n)
		var up_l := lp[i].y < rp[i].y
		var su0 := lp[i] if up_l else rp[i]
		var su1 := lp[i + 1] if up_l else rp[i + 1]
		var sd0 := rp[i] if up_l else lp[i]
		var sd1 := rp[i + 1] if up_l else lp[i + 1]
		if wd[i] >= 2.5:
			_quad(pts[i].lerp(sd0, 0.6), pts[i + 1].lerp(sd1, 0.6), sd1, sd0, T_INK)
		if s > 0.06 and s < 0.9 and wd[i] >= 1.6:
			_quad(pts[i].lerp(su0, 0.45), pts[i + 1].lerp(su1, 0.45), su1, su0, T_SHEEN)
			if wd[i] > 3.2 and s > 0.12 and s < 0.7:
				_draw.draw_line(su0, su1, T_RIM)


func _quad(a: Vector2, b: Vector2, c: Vector2, d: Vector2, col: Color) -> void:
	_draw.draw_primitive(PackedVector2Array([a, b, c, d]), PackedColorArray([col, col, col, col]), PackedVector2Array())
