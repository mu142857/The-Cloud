extends Control
## 飞行一结尾「往前一冲」（10-30 作者：「直接这样，就是往前一冲，然后冲入黑色的星空，场景渐暗，第一章就结束了……
## 你现在的一直平直飞然后到河流就很不合适」）。降落河流星的那几句挪到河流篇开头（story_river.json start_river）。
##
## 剧本：{"do": "cockpit_dash"}，可选 "far_scale"（默认 0.75）。story_runner.gd 的 _cockpit_step 建它：await play(runner, st)。
## 过程（窗外的三个状态在 tools/sky_art.py 里：starfield / dash_go / dash / dash_end）：
##   1）爬出云海：窗外 starfield（云海整片往下沉、淡掉，天换成黑色星空），镜头同时拉远到船外（cockpit.far_out，和躲碎石同一套）。
##   2）蓄力：船先往后（右）缓缓退 BACK 像素（smoothstep），船身外一圈热光慢慢亮起来——用 ship_glow.gd 现有的
##      hold_goal（至少多亮）/ heat_goal（暖红），不改那个文件；推进器那头最亮。
##   3）冲：窗外 dash_go → dash（星点拉成短线、再拉成长线，横向速度平滑涨上去）；船往左（机头方向）冲出画面，
##      位移 = PUSH × u³（u 从 0 到 1：先缓后急，起步速度是 0，接着蓄力那一下不跳）。船动 = 镜头反向动（level.camera_hold_at），
##      船外背景在 CanvasLayer 里不跟镜头。
##   4）收：窗外 dash_end（长线缩回星点、慢下来），只剩黑色星空；光慢慢收掉。之后剧本 end_chapter 渐暗、出结束卡。
## 跳节拍（ff）/ 没有驾驶舱：窗外直接到 dash_end，船不动。自动玩照真实时长播（约 7 秒）。

const FAR_K := 0.75          # 拉远到多大（和躲碎石同一套图：0.55..0.93）
const CLIMB_SEC := 2.6       # 爬出云海（= sky.json starfield 的 blend）
const BACK := 8.0            # 蓄力时往后退多少像素
const BACK_SEC := 0.9
const PUSH := -620.0         # 冲出去：船往左挪多少（够整艘远景船连光一起出画面）
const PUSH_SEC := 1.5
const END_SEC := 1.4         # 冲出去以后星线收住、停一下

var runner: Node
var level: Node
var cockpit: Node2D


func play(r: Node, st: Dictionary) -> String:
	runner = r
	level = r.level
	cockpit = r.world.cockpit
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	if r.ff or cockpit == null:
		r.world.set_prop("cockpit_window", "dash_end")
		return ""
	var k := float(st.get("far_scale", FAR_K))
	var far: bool = k < 0.99 and cockpit.far_ready(k)
	var glow: Node2D = cockpit.far_glow if far and cockpit.far_glow != null else cockpit.glow
	# ---- 1）爬出云海、拉到船外
	r.world.set_prop("cockpit_window", "starfield")
	if far:
		cockpit.far_out(k, CLIMB_SEC * 0.8)
	_sfx("engine_up", -10.0)
	await _wait(CLIMB_SEC)
	var base: Vector2 = level.cam.position
	# ---- 2）蓄力：往后退一点，热光亮起来
	if glow != null:
		if glow.strength <= 0.0:
			glow.heat = 1.0
		glow.heat_goal = 1.0
		glow.hold_goal = 0.55
	_sfx("engine_boost", -6.0)
	await _move(base, 0.0, BACK, BACK_SEC, func(u: float) -> float: return u * u * (3.0 - 2.0 * u))
	# ---- 3）冲
	if glow != null:
		glow.hold_goal = 1.0
	r.world.set_prop("cockpit_window", "dash_go")
	_sfx("ship_whoosh", -4.0)
	var half := false
	var t := 0.0
	while t < PUSH_SEC:
		await get_tree().process_frame
		t += get_process_delta_time()
		var u := clampf(t / PUSH_SEC, 0.0, 1.0)
		level.camera_hold_at(base - Vector2(BACK + (PUSH - BACK) * u * u * u, 0.0))
		if not half and u >= 0.4:
			half = true
			r.world.set_prop("cockpit_window", "dash")
	# ---- 4）收住
	r.world.set_prop("cockpit_window", "dash_end")
	if glow != null:
		glow.hold_goal = 0.0
	await _wait(END_SEC)
	print("COCKPIT dash: far=%s k=%.2f" % [str(far), k])
	return ""


## 船从屏幕偏移 a 挪到 b（正 = 往右），sec 秒，按 ease(u) 走
func _move(base: Vector2, a: float, b: float, sec: float, ease: Callable) -> void:
	var t := 0.0
	while t < sec:
		await get_tree().process_frame
		t += get_process_delta_time()
		var u := clampf(t / sec, 0.0, 1.0)
		level.camera_hold_at(base - Vector2(a + (b - a) * float(ease.call(u)), 0.0))


func _wait(sec: float) -> void:
	var t := 0.0
	while t < sec:
		await get_tree().process_frame
		t += get_process_delta_time()


func _sfx(name: String, db: float) -> void:
	var p := "res://audio/sfx/%s.wav" % name
	if not ResourceLoader.exists(p):
		return
	var a := AudioStreamPlayer.new()
	a.stream = load(p)
	a.volume_db = db
	a.bus = "SFX" if AudioServer.get_bus_index("SFX") >= 0 else "Master"
	add_child(a)
	a.play()
