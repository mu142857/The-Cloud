extends Control
## 母星闪回（11-02 作者定，一共 4 次；docs/闪回_实现说明.md）。剧本步骤：
##   {"do": "flashback", "id": 1..4, "place": "street" | "station"（两个一样，都是城市那条街）, "end": "black" | "door" | "white" | "still",
##    "lines": [{zh, en, added?}…], "fall": true（最后一句的字一个个掉没）, "hold": true}
##   {"do": "flashback_wake", "wait": false}
## story_runner.gd 的 _flashback 建它（自己一层 CanvasLayer，盖在黑幕上面、F8 面板下面）：await play(runner, st)。
##
## 四次一样的玩法（作者讨厌每章换玩法）：
##   1. 进：画面（连对话框、物件）和晨的意识一起慢慢糊掉、去色、四角压暗（第一次是雾：发白），约 INTRO 秒；
##      母星的画面在糊里淡进来，再慢慢变清楚（flashback_screen / flashback_view 两个 shader）。
##   2. 跑：晨（现成的跑步动作，100ms 一帧）只能往右跑：→ / D 按住，或者连按 E（每按一下多快一点，一会儿慢回去；
##      光按 E 不按方向键也会跑），鼠标 / 触屏点按也算按 E。屏幕下面「连按 E」，屏幕中间一行一行出晨的独白。
##      左边一片灰暗压过来（不是角色：画面被压暗、去色，前沿有一点起伏），越来越快；心跳按灰色离晨多近变快变响，底下一层紧张的音乐。
##      只按方向键不按 E：约 12 秒被追上（灰色最快 GREY_V.y 190 > 晨的 150）；连按 E 一秒三下以上跑得掉（一秒两下约 18 秒被追上）。
##   3. 结束：灰色追上晨 → 一下子漫过去、屏幕变黑。跑满 RUN 秒没被追上 → 成就（flag fb_outran，名字在 data/achievements.json），
##      再按这一次的 end：black 晨慢下来停住、慢慢黑掉；door 街上前面出现一扇亮着的车门，晨跑到跟前它关上，再黑；
##      white 前面的楼、人群、倒影一段一段褪成空白（从右往左，一段 SEG_W 宽），晨停下，整屏发白。
##      第四次（end: still）：心跳慢慢停下；「连按 E」还在，但不按也行——晨站着不动 STILL 秒（或者站着时灰色慢慢走到她身边），
##      灰色和人群从她身边过去，什么也没发生，成就（flag fb_stood_still），慢慢暗下去。
##      她跑起来，灰色就和前三次一样追（只有跑的时候追）；一直跑满 RUN 秒没被追上，和第一次一样慢下来、黑掉。
##   4. 醒：hold = 停在黑 / 白上，等剧本自己放好原场景、叫醒她的声音，再 flashback_wake：眼皮从上下慢慢睁开
##      （睁一半、又合一点、再睁开），糊的画面一起变清楚。没写 hold 就自己接着醒。
##   没有失败、不会卡关：每一段都有时长上限，追上了也接着播剧情。一次 20～35 秒。
## 母星只用作者已有的场景（不新画背景、不改作者图层的颜色）。11-02 作者：「第二个城市的质感差多了，你就不能复制过去改复制的吗？
##   楼房，有倒影的地板，雨夜，来回走的人」→ 四次都是同一条街：scenes/city_test.tscn（作者的城市；city_room.gd 也是这么搬的）
##   整个实例化进一个 SubViewport，去掉它的根脚本（city_test.gd 读命令行、空格，这里不要），镜头、湿街面自己管；
##   晨那条街的中排人流改成往左（三排都逆着晨）。home_train 不再用在闪回里（尾声回家的列车照旧用）。
##   第二次的车门是叠在街上的（_draw_door，程序画的门框 + 两片拉门 + 里面的光，没有车门的图，先这样顶着）：画在晨后面一层、
##   近排人流和湿地面前面，所以会照进倒影，近排的人照样从门前走过。第三次的发白是 flashback_view.gdshader 叠在画面上的。
## 声音：heartbeat（一下心跳，按快慢重复放）、flashback_tense（循环的紧张音乐）、train_door_close；缺的静默跳过，记进
##   runner.missing_sfx（--story_check 列出来）。都走 Music 总线；闪回期间 SFX 总线（原场景的环境声）压低 DUCK dB，醒的时候放回去。
## 自动玩：时长 × AUTO_K；一直跑、连按 E（跑掉、拿成就那条路）；第四次站着不动（停下来那条路）。
##   --fb_caught：自动玩站着不动（被追上那条路）；--fb_full：自动玩也按真实时长。跳节拍（ff）时 runner 直接跳过，不建它。
## F8 传送页每章下面有「闪回」按钮（dev_panel.gd，表在 story_runner.gd 的 FLASHBACK_DEV）。

const CITY_SCENE := "res://scenes/city_test.tscn"
const ENV_LIGHT := preload("res://scripts/env_light.gd")
const SCREEN_SH := preload("res://scripts/flashback_screen.gdshader")
const VIEW_SH := preload("res://scripts/flashback_view.gdshader")
const ACH_PATH := "res://data/achievements.json"
const SOUNDS := ["heartbeat", "flashback_tense", "train_door_close"]
const GROUND := 228.0
const LOOK := 80.0              # 镜头往前多看：晨在屏幕 x 160 左右，左边留给压过来的灰色
const FOLLOW := 3.0
const INTRO := 2.6              # 糊掉 → 母星画面淡进来
const RUN := 22.0               # 跑满这么久还没被追上 = 跑掉了
const GAP0 := 320.0             # 一开始灰色的前沿在晨身后多远（在屏幕外一点）
const GREY_V := Vector2(60.0, 150.0)   # 灰色的速度：从慢到快（像素 / 秒）。11-02 作者：「灰色太快了，我稍微停一下就被追上，慢一点，主角跑快」
const RUN_BONUS := 50.0         # 闪回里晨跑得比平时快这么多（150 + 50 = 200，比灰色最快还快；停一两秒不会被追上，站久了才会）
const GREY_RAMP := 8.0          # 几秒加到最快
const GREY_STILL := 20.0        # 第四次晨还没跑过：灰色慢慢挪
const PUSH := 22.0              # 按一下 E 多快多少（像素 / 秒）
const PUSH_MAX := 75.0
const PUSH_DECAY := 2.5         # 多出来的速度慢回去（1/秒）
const E_RUN := 0.45             # 按一下 E 晨至少跑多久
const LINE_FIRST := 1.2         # 开跑后第几秒出第一句独白
const LINE_EVERY := 4.5
const LINE_ONE := 2.0           # 只有一句的：第几秒出
const FALL_AFTER := 2.5         # 要掉字的那句出来多久以后开始掉
const FALL_EVERY := 0.32
const STILL := 6.0              # 第四次：站着不动这么久 = 停下来
const PASS_V := 110.0           # 第四次停下来：灰色从晨身边过去的速度
const HEART_BPM := Vector2(66.0, 138.0)
const DUCK := 14.0
const AUTO_K := 0.4
const GREY_C := Color(0.1, 0.11, 0.12)
const FOG_C := Color(0.63, 0.69, 0.67)
const DARK_C := Color(0.02, 0.03, 0.03)
const WHITE_C := Color(0.93, 0.95, 0.94)
const BLACK_C := Color(0.0, 0.0, 0.0)
const DOOR_C := Color(0.15, 0.16, 0.18)
const DOOR_RIM := Color(0.36, 0.39, 0.42)
const DOOR_FRAME := Color(0.2, 0.22, 0.24)
const DOOR_IN := Color(0.42, 0.52, 0.52)        # 门里面的光（城市路灯光晕那种青灰，别太亮）
const DOOR_SIGN := Color(0.384, 0.494, 0.529)   # 门楣上的灯条 = city_test.tscn 人流的 glow 色
const DOOR_HALF := 26.0                         # 门洞半宽（晨 60 高、人 90～110 高）
const DOOR_H := 92.0
const DOOR_AHEAD := 300.0                       # 门出现在晨前面多远（屏幕右边缘附近）
const DOOR_CLOSE_AT := 125.0                    # 晨跑到离门这么远，门开始关
const DOOR_STOP := 36.0                         # 晨最多跑到离门这么近
const WHITE_SEC := 4.2                          # 第三次：空白从右边漫到晨跟前要多久
const TXT := {
	"hint": ["Mash E", "连按 E"],
	"ach": ["Achievement", "成就"],
}

var runner: Node
var st := {}
var id := 1
var place := "street"
var end_kind := "black"
var result := ""                  # caught / escaped / still
var _lines: Array = []
var _auto := false
var _auto_caught := false
var _k := 1.0
var _vp: SubViewport
var _world: Node2D
var _chen: Node2D
var _cam: Camera2D
var _wet: ShaderMaterial
var _shafts: Node
var _view: TextureRect
var _vmat: ShaderMaterial
var _screen: ColorRect
var _smat: ShaderMaterial
var _veil: ColorRect
var _door: Node2D                 # 第二次：街上的车门（世界坐标，在 SubViewport 里）
var _door_k := 0.0
var _door_wx := 0.0
var _hint: Label
var _line_box: Control
var _line_rows: Array = []        # 每句一行：[Label…]（一个字一个 Label，要掉字）
var _line_t: Array = []           # 每句什么时候出（开跑后的秒数）
var _shown := 0
var _fall_i := -1                 # 掉到第几个字（-1 = 还没开始掉）
var _fall_t := 0.0
var _flush_next := 0.0
var _toast: Label
var _music: AudioStreamPlayer
var _bus := "Master"
var _sfx_db := 0.0
var _ducked := false
var _t := 0.0
var _run_t := 0.0
var _running := false
var _grey_wx := -9999.0
var _grey_tail := -99999.0
var _grey_mode := ""              # "" 追 / rush 漫过去 / back 退回去 / pass 从身边过去
var _white_wx := 99999.0          # 第三次：空白的前沿（世界 x，只往左走，褪掉的不会再回来）
var _boost := 0.0
var _extra := 0.0
var _e_t := 0.0
var _mouse_down := false
var _presses := 0
var _auto_press_t := 0.0
var _still_t := 0.0
var _ran := false
var _run_now := false
var _chase_t := 0.0
var _heart_t := 0.0
var _bpm := 0.0
var _heart_db := -16.0
var _end_color := BLACK_C


func play(r: Node, step: Dictionary) -> void:
	runner = r
	st = step
	id = int(st.get("id", 1))
	place = str(st.get("place", "street"))
	end_kind = str(st.get("end", "black"))
	_lines = st.get("lines", [])
	var args := OS.get_cmdline_user_args()
	_auto = r.auto != ""
	_k = AUTO_K if _auto and not "--fb_full" in args else 1.0
	_auto_caught = "--fb_caught" in args
	_bus = "Music" if AudioServer.get_bus_index("Music") >= 0 else "Master"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_build()
	_duck(true)
	await _intro()
	await _run()
	await _ending()
	print("FLASHBACK %d %s: result=%s run=%.1fs presses=%d end=%s" % [id, place, result, _run_t, _presses, end_kind])
	if not bool(st.get("hold", false)):
		await wake()


# ======================================================================= 搭画面
func _build() -> void:
	_vp = SubViewport.new()
	_vp.size = Vector2i(480, 270)
	_vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_vp)
	_build_city()
	_chen.input_enabled = false
	_chen.ground_fn = func(_x: float) -> float: return GROUND
	_cam.position = Vector2(_chen.position.x + LOOK, _cam.position.y)
	_cam.make_current()
	# 母星那一屏
	_view = TextureRect.new()
	_view.texture = _vp.get_texture()
	_view.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_view.size = Vector2(480, 270)
	_view.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_vmat = ShaderMaterial.new()
	_vmat.shader = VIEW_SH
	_vmat.set_shader_parameter("grey_c", GREY_C)
	_vmat.set_shader_parameter("white_c", WHITE_C)
	_view.material = _vmat
	_view.visible = false
	add_child(_view)
	# 读屏幕的那一层（进：糊掉原场景；醒：眼皮）。画在母星那一屏下面：进的时候母星在它上面淡进来
	_screen = ColorRect.new()
	_screen.size = Vector2(480, 270)
	_screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_smat = ShaderMaterial.new()
	_smat.shader = SCREEN_SH
	_screen.material = _smat
	_screen.visible = false
	add_child(_screen)
	move_child(_screen, _view.get_index())
	_line_box = Control.new()
	_line_box.size = Vector2(480, 270)
	_line_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_line_box)
	_hint = _label(_tx("hint"), UITheme.TEXT_DIM)
	_hint.position = Vector2(0, 244)
	_hint.modulate.a = 0.0
	add_child(_hint)
	_veil = ColorRect.new()
	_veil.size = Vector2(480, 270)
	_veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_veil.color = Color(BLACK_C, 0.0)
	add_child(_veil)
	_toast = _label("", UITheme.WARM)
	_toast.position = Vector2(0, 16)
	_toast.modulate.a = 0.0
	add_child(_toast)
	_build_lines()


func _build_city() -> void:
	var root: Node = (load(CITY_SCENE) as PackedScene).instantiate()
	root.set_script(null)                       # city_test.gd 读命令行（--shot= 会存图退出）、空格：这里不要，镜头自己管
	var mid := root.get_node_or_null("Main/CrowdMid")
	if mid != null:
		mid.set("direction", -1)                # 晨那条街三排人流都往左：逆着往右跑的晨
	_world = root
	_vp.add_child(root)
	_chen = root.get_node("Chen")
	_cam = root.get_node("Camera")
	_shafts = root.get_node_or_null("Shafts")
	var wr := root.get_node_or_null("Wet/Rect")
	if wr != null:
		_wet = (wr as CanvasItem).material as ShaderMaterial
	var sh: Node = _shafts
	_chen.set_env("city", func(c): return ENV_LIGHT.polygon_shafts(c, sh))
	if end_kind == "door":
		_build_door()
	_music_on("rain_loop", -20.0)


## 第二次的车门：插在晨后面一层（近排人流、湿地面在它后面画 → 门照进倒影、近排的人从门前走过）。开始藏着，结束时才出来
func _build_door() -> void:
	_door = Node2D.new()
	_door.name = "FlashbackDoor"
	_door.visible = false
	_door.draw.connect(_draw_door)
	_world.add_child(_door)
	_world.move_child(_door, _chen.get_index() + 1)


## 独白：每句一行，一个字一个 Label（第三次要一个个掉）；屏幕中间偏上，几句一起居中
func _build_lines() -> void:
	var font := UITheme.font()
	var n := _lines.size()
	var y0 := 92.0 - float(n - 1) * 10.0
	for i in n:
		var l: Dictionary = _lines[i]
		var text: String = runner.txt(l)
		var col: Color = runner.dlg.ADDED_C if bool(l.get("added", false)) and runner.mark_added else Color("#d8e2dc")
		var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
		var x := roundf(240.0 - w / 2.0)
		var row: Array = []
		for ch in text:
			var c := Label.new()
			c.text = ch
			c.add_theme_font_override("font", font)
			c.add_theme_font_size_override("font_size", 14)
			c.add_theme_color_override("font_color", col)
			c.add_theme_color_override("font_shadow_color", Color(0.0, 0.02, 0.02, 0.85))
			c.add_theme_constant_override("shadow_offset_x", 0)
			c.add_theme_constant_override("shadow_offset_y", 1)
			c.position = Vector2(x, roundf(y0 + float(i) * 20.0))
			c.mouse_filter = Control.MOUSE_FILTER_IGNORE
			c.modulate.a = 0.0
			_line_box.add_child(c)
			row.append(c)
			x += font.get_string_size(ch, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
		_line_rows.append(row)
		var every := minf(LINE_EVERY, (RUN - 6.0) / maxf(1.0, float(n - 1)))
		_line_t.append((LINE_ONE if n == 1 else LINE_FIRST + float(i) * every) * _k)


func _label(text: String, col: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", UITheme.font())
	l.add_theme_font_size_override("font_size", 14)
	l.add_theme_color_override("font_color", col)
	l.add_theme_color_override("font_shadow_color", Color(0.0, 0.02, 0.02, 0.85))
	l.add_theme_constant_override("shadow_offset_x", 0)
	l.add_theme_constant_override("shadow_offset_y", 1)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.size = Vector2(480, 16)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


static func _tx(k: String) -> String:
	var row: Array = TXT[k]
	return str(row[1] if I18n.is_zh() else row[0])


# ======================================================================= 进
func _intro() -> void:
	_screen.visible = true
	_smat.set_shader_parameter("veil", FOG_C if id == 1 else DARK_C)   # 第一次：雾越来越浓（发白）
	var d := INTRO * _k
	var tw := create_tween().set_parallel().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_method(_sp.bind("blur"), 0.0, 4.0, d)
	tw.tween_method(_sp.bind("desat"), 0.0, 0.75, d)
	tw.tween_method(_sp.bind("vig"), 0.0, 0.85, d)
	tw.tween_method(_sp.bind("veil_a"), 0.0, 0.6 if id == 1 else 0.3, d)
	_bpm = HEART_BPM.x
	# 母星的画面在糊里淡进来，再慢慢变清楚
	_vmat.set_shader_parameter("blur", 4.0)
	_view.modulate.a = 0.0
	_view.visible = true
	var tw2 := create_tween()
	tw2.tween_interval(d * 0.45)
	tw2.tween_property(_view, "modulate:a", 1.0, d * 0.65).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw2.tween_method(_vp_blur, 4.0, 0.0, 1.4 * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	await tw2.finished
	_screen.visible = false


func _sp(v: float, key: String) -> void:
	_smat.set_shader_parameter(key, v)


func _vp_blur(v: float) -> void:
	_vmat.set_shader_parameter("blur", v)


# ======================================================================= 跑
func _run() -> void:
	_running = true
	_grey_wx = _chen.position.x - GAP0
	create_tween().tween_property(_hint, "modulate:a", 0.9, 0.6).set_delay(0.6 * _k)
	runner._ui_shot("flashback%d" % id, 3.0 * _k)
	while _running:
		await get_tree().process_frame
		_run_step(get_process_delta_time())
	_mouse_down = false
	create_tween().tween_property(_hint, "modulate:a", 0.0, 0.5)


func _run_step(dt: float) -> void:
	_run_t += dt
	# 只能往右：→ / D 按住、按 E、鼠标 / 触屏按住；往左的键不理
	var hold := false
	if _auto:
		hold = id != 4 and not _auto_caught
		_auto_press_t -= dt
		if hold and not _auto_caught and _auto_press_t <= 0.0:
			_auto_press_t = 0.2
			_press()
	else:
		hold = Input.is_action_pressed("ui_right") or Input.is_key_pressed(KEY_D) or _mouse_down
	_e_t = maxf(0.0, _e_t - dt)
	var run := hold or _e_t > 0.0
	_run_now = run
	_chen.auto_dir = 1.0 if run else 0.0
	_boost *= exp(-PUSH_DECAY * dt)
	if run and float(_chen.get("_vel")) > 1.0:
		_extra += (_boost + RUN_BONUS) * dt     # 按 E 多出来的那点速度 + 闪回里本来就跑得快：直接把晨往前挪（chen.gd 会从新位置接着跑）
		var px := floorf(_extra)
		if px >= 1.0:
			_chen.position.x += px
			_extra -= px
	if run:
		_ran = true
		_still_t = 0.0
	else:
		_still_t += dt
	if _ran:
		_chase_t += dt
	# 灰色：从慢到快追。第四次只有晨跑的时候才追；她站着，灰色就慢慢挪过来（不是在追她）
	var v := GREY_STILL if id == 4 and not run else lerpf(GREY_V.x, GREY_V.y, smoothstep(0.0, GREY_RAMP * _k, _chase_t if id == 4 else _run_t))
	_grey_wx += v * dt
	if id == 4 and not run and (_still_t >= STILL * _k or _grey_wx >= _chen.position.x - 4.0):
		result = "still"                        # 站够了，或者灰色走到她身边：从她身边过去，什么也没发生
		_running = false
	elif _grey_wx >= _chen.position.x - 4.0:
		result = "caught"
		_running = false
	elif _run_t >= RUN * _k:
		result = "escaped"
		_running = false


func _press() -> void:
	_presses += 1
	_boost = minf(_boost + PUSH, PUSH_MAX)
	_e_t = E_RUN
	_hint.modulate.a = 1.0
	create_tween().tween_property(_hint, "modulate:a", 0.9, 0.25)


func _input(e: InputEvent) -> void:
	if _auto or not is_instance_valid(_view) or not _view.visible:
		return
	if e is InputEventKey:
		var k: InputEventKey = e
		if k.keycode == KEY_F8 or k.keycode == KEY_ESCAPE:
			return
		if k.pressed and not k.echo and (k.keycode == KEY_E or k.physical_keycode == KEY_E) and _running:
			_press()
		get_viewport().set_input_as_handled()      # 闪回里别的键不给关卡（背包、对话推进）；方向键照样从 Input 读
	elif e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		_mouse_down = e.pressed and _running
		if e.pressed and _running:
			_press()
		get_viewport().set_input_as_handled()
	elif e is InputEventScreenTouch:
		_mouse_down = e.pressed and _running
		if e.pressed and _running:
			_press()
		get_viewport().set_input_as_handled()


# ======================================================================= 每帧：镜头、灰色、心跳、独白
func _process(delta: float) -> void:
	_t += delta
	if not is_instance_valid(_chen):
		return
	var cx := _chen.position.x + LOOK
	_cam.position.x = lerpf(_cam.position.x, cx, 1.0 - exp(-FOLLOW * delta))
	var left := _cam.position.x - 240.0
	if _wet != null:
		_wet.set_shader_parameter("cam_left", left)
		_wet.set_shader_parameter("chen_x", _chen.position.x - left)
	if _door != null and _door.visible and _chen.position.x > _door_wx - DOOR_STOP:
		_chen.position.x = _door_wx - DOOR_STOP     # 门关上了，过不去
	match _grey_mode:
		"rush":
			_grey_wx += 520.0 * delta
		"back":
			_grey_wx -= 260.0 * delta
		"pass":
			_grey_wx += PASS_V / _k * delta
			_grey_tail = _grey_wx - 170.0
	_vmat.set_shader_parameter("grey_x", _grey_wx - left)
	_vmat.set_shader_parameter("grey_tail", _grey_tail - left)
	_vmat.set_shader_parameter("white_x", _white_wx - left)
	_vmat.set_shader_parameter("cam_left", left)
	_vmat.set_shader_parameter("chen_sx", _chen.position.x - left)
	_vmat.set_shader_parameter("t", _t)
	_heart(delta)
	_lines_step(delta)


func _heart(delta: float) -> void:
	if _running:
		var tension := clampf(1.0 - (_chen.position.x - _grey_wx) / GAP0, 0.0, 1.0)
		if id == 4 and not _run_now:
			_bpm = move_toward(_bpm, 0.0, HEART_BPM.x / (STILL * _k * 1.4) * delta)   # 第四次站着：心跳慢慢停下
		else:
			_bpm = lerpf(HEART_BPM.x, HEART_BPM.y, tension)
		_heart_db = lerpf(-16.0, -4.0, tension)
		if _music != null and str(_music.get_meta("snd", "")) == "flashback_tense":
			_music.volume_db = lerpf(-22.0, -10.0, tension)
	if _bpm < 20.0:
		return
	_heart_t += delta
	if _heart_t >= 60.0 / _bpm:
		_heart_t = 0.0
		_play("heartbeat", _heart_db)


func _lines_step(delta: float) -> void:
	# 跑的时候按时间出；跑完了还没出完的（追上得早），每 0.9 秒补一句
	if _shown < _line_rows.size():
		var due := _run_t >= float(_line_t[_shown]) if _running else (result != "" and _t >= _flush_next)
		if due:
			_show_line(_shown)
			_shown += 1
			_flush_next = _t + 0.9 * _k
	# 掉字：最后一句出来 FALL_AFTER 秒以后，从后往前一个字一个字掉下去
	if not bool(st.get("fall", false)) or _shown < _line_rows.size() or _line_rows.is_empty():
		return
	var row: Array = _line_rows[_line_rows.size() - 1]
	_fall_t += delta
	if _fall_i < 0:
		if _fall_t >= FALL_AFTER * _k:
			_fall_i = row.size() - 1
			_fall_t = FALL_EVERY * _k
		return
	if _fall_i >= 0 and _fall_t >= FALL_EVERY * _k:
		_fall_t = 0.0
		var c: Label = row[_fall_i]
		var tw := create_tween().set_parallel()
		tw.tween_property(c, "position:y", c.position.y + 28.0, 0.7 * _k).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
		tw.tween_property(c, "modulate:a", 0.0, 0.7 * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
		_fall_i -= 1
		if _fall_i < 0:
			_fall_i = -2                        # 掉完了


func _show_line(i: int) -> void:
	for j in i:                                 # 前面的几句暗一点
		for c in _line_rows[j]:
			create_tween().tween_property(c, "modulate:a", 0.55, 0.6)
	for c in _line_rows[i]:
		create_tween().tween_property(c, "modulate:a", 1.0, 0.8 * maxf(_k, 0.5)).set_trans(Tween.TRANS_SINE)


## 剩下没出的独白都出完（追上得早也要说完），最后一句再停一会儿；要掉字的等它掉完
func _flush_lines() -> void:
	var guard := 0.0
	while guard < 15.0:
		var fall_done := not bool(st.get("fall", false)) or _fall_i == -2 or _line_rows.is_empty()
		if _shown >= _line_rows.size() and fall_done:
			break
		await get_tree().process_frame
		guard += get_process_delta_time()
	await _sleep(1.2)


# ======================================================================= 结束
func _ending() -> void:
	_chen.auto_dir = 0.0 if result != "escaped" else _chen.auto_dir
	match result:
		"caught":
			_grey_mode = "rush"                 # 灰色一下子漫过晨、盖满屏幕
			_bpm = 0.0
			_music_off(0.6)
			await _flush_lines()
			_end_color = BLACK_C
			await _veil_to(BLACK_C, 1.0)
		"still":
			_grey_mode = "pass"                 # 灰色和人群从她身边过去，什么也没发生
			_vmat.set_shader_parameter("grey_a", 0.55)
			_bpm = 0.0
			_music_off(1.5)
			_achieve("fb_stood_still")
			var guard := 0.0
			while _grey_tail - (_cam.position.x - 240.0) < 560.0 and guard < 12.0:
				await get_tree().process_frame
				guard += get_process_delta_time()
			await _flush_lines()
			await _sleep(1.0)
			_end_color = BLACK_C
			await _veil_to(BLACK_C, 2.2)
		_:
			_grey_mode = "back"
			_achieve("fb_outran")
			match end_kind:
				"door":
					await _end_door()
				"white":
					await _end_white()
				_:
					_chen.auto_dir = 0.0         # 跑不动了，慢下来停住
					_bpm = HEART_BPM.x
					_music_off(2.0)
					await _sleep(1.2)
					await _flush_lines()
					_bpm = 0.0
					_end_color = BLACK_C
					await _veil_to(BLACK_C, 1.8)


## 第二次跑掉了：街上前面淡出来一扇亮着的车门（门开着），晨往那儿跑，跑到跟前门从两边合上，她停在门外
func _end_door() -> void:
	_chen.auto_dir = 1.0
	_door_wx = roundf(_chen.position.x + DOOR_AHEAD)
	_door.position = Vector2(_door_wx, GROUND)
	_door.modulate.a = 0.0
	_door_k = 0.0
	_door.visible = true
	_door.queue_redraw()
	create_tween().tween_property(_door, "modulate:a", 1.0, 0.9 * maxf(_k, 0.5)).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	var guard := 0.0
	while _chen.position.x < _door_wx - DOOR_CLOSE_AT and guard < 4.0:
		await get_tree().process_frame
		guard += get_process_delta_time()
	_play("train_door_close", -6.0)
	var tw := create_tween()
	tw.tween_method(_set_door, 0.0, 1.0, 0.55).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_method(_set_door, 1.0, 0.94, 0.08)
	tw.tween_method(_set_door, 0.94, 1.0, 0.14).set_trans(Tween.TRANS_SINE)
	await _sleep(0.3)
	_chen.auto_dir = 0.0
	await tw.finished
	print("FLASHBACK_DOOR closed gap=%d waited=%.1fs" % [int(_door_wx - _chen.position.x), guard])
	_bpm = 0.0
	_music_off(1.0)
	await _sleep(1.0)
	await _flush_lines()
	_end_color = BLACK_C
	await _veil_to(BLACK_C, 1.2)


## 第三次跑掉了：前面的楼、人群、倒影一段一段褪成空白（前沿从屏幕右边往晨这边走，世界坐标只往左，褪掉的不回来），
## 晨跑着跑着停下；字一个个掉完，最后连她一起白掉
func _end_white() -> void:
	_chen.auto_dir = 1.0
	var d := WHITE_SEC * _k
	var tw := create_tween()
	tw.tween_method(_white_to, 560.0, 240.0 - LOOK + 22.0, d).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	create_tween().tween_property(_line_box, "modulate", Color(0.3, 0.33, 0.33), d).set_trans(Tween.TRANS_SINE)   # 白底上字要看得见
	_music_off(2.5)
	await _sleep(WHITE_SEC * 0.65)
	_chen.auto_dir = 0.0
	await tw.finished
	print("FLASHBACK_WHITE front_ahead=%d" % int(_white_wx - _chen.position.x))
	_bpm = 0.0
	await _flush_lines()
	var tw2 := create_tween()
	tw2.tween_method(_vp_param.bind("white_all"), 0.0, 1.0, 1.2 * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tw2.finished
	_end_color = WHITE_C
	await _veil_to(WHITE_C, 0.8)


func _white_to(sx: float) -> void:
	if is_instance_valid(_cam):
		_white_wx = minf(_white_wx, _cam.position.x - 240.0 + sx)


func _vp_param(v: float, key: String) -> void:
	_vmat.set_shader_parameter(key, v)


func _set_door(v: float) -> void:
	_door_k = v
	if _door != null:
		_door.queue_redraw()


## 车门（原点 = 门洞底边中间，脚底那一行）：门框 + 门楣灯条，门洞里亮着，两片拉门从两边合到中间（每片一扇窗、
## 合缝那边一道受光边和一条暗胶条），门口地上一小片光（门关上就没了）
func _draw_door() -> void:
	var hw := DOOR_HALF
	var top := -DOOR_H
	var open := 1.0 - _door_k
	if open > 0.0:
		_door.draw_rect(Rect2(-hw - 10.0, 0, hw * 2.0 + 20.0, 3), Color(DOOR_IN, 0.28 * open))
		_door.draw_rect(Rect2(-hw - 4.0, 3, hw * 2.0 + 8.0, 2), Color(DOOR_IN, 0.14 * open))
	_door.draw_rect(Rect2(-hw, top, hw * 2.0, DOOR_H), DOOR_IN)
	_door.draw_rect(Rect2(-hw, top + 14.0, hw * 2.0, 1), DOOR_IN.darkened(0.35))          # 里面的扶杆
	_door.draw_rect(Rect2(-hw, -18.0, hw * 2.0, 18), DOOR_IN.darkened(0.18))             # 里面的地板暗一点
	var pw := roundf(hw * _door_k)
	if pw >= 1.0:
		for side in [0, 1]:
			var x0 := -hw if side == 0 else hw - pw
			var r := Rect2(x0, top, pw, DOOR_H)
			_door.draw_rect(r, DOOR_C)
			var lead := (x0 + pw) if side == 0 else x0       # 合缝那边
			var win := Rect2((lead - 20.0) if side == 0 else (lead + 5.0), top + 12.0, 15, 40).intersection(r)
			if win.size.x > 0.0:
				_door.draw_rect(win, DOOR_IN.darkened(0.45))
				_door.draw_rect(Rect2(win.position, Vector2(win.size.x, 1)), DOOR_RIM)
			_door.draw_rect(Rect2((lead - 2.0) if side == 0 else lead, top, 2, DOOR_H), Color(0.05, 0.05, 0.06))
			_door.draw_rect(Rect2((lead - 3.0) if side == 0 else (lead + 2.0), top, 1, DOOR_H), DOOR_RIM)
	_door.draw_rect(Rect2(-hw - 5.0, top - 14.0, 5, DOOR_H + 14.0), DOOR_FRAME)
	_door.draw_rect(Rect2(hw, top - 14.0, 5, DOOR_H + 14.0), DOOR_FRAME)
	_door.draw_rect(Rect2(-hw - 5.0, top - 14.0, hw * 2.0 + 10.0, 14), DOOR_FRAME)
	_door.draw_rect(Rect2(-hw - 5.0, top - 14.0, hw * 2.0 + 10.0, 1), DOOR_RIM)
	_door.draw_rect(Rect2(-hw + 6.0, top - 10.0, hw * 2.0 - 12.0, 5), DOOR_SIGN)
	_door.draw_rect(Rect2(-hw - 1.0, top - 14.0, 1, DOOR_H + 14.0), DOOR_RIM)
	_door.draw_rect(Rect2(hw, top - 14.0, 1, DOOR_H + 14.0), DOOR_RIM)


func _veil_to(c: Color, sec: float) -> void:
	_veil.color = Color(c, _veil.color.a)
	var tw := create_tween()
	tw.tween_property(_veil, "color:a", 1.0, sec * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tw.finished


## 成就：flag 记下来（「全剧终」卡下面 barter.gd show_achievements 列出来），第一次拿到时屏幕上面一行字
func _achieve(flag: String) -> void:
	var first := not StoryState.has(flag)
	StoryState.set_flag(flag)
	print("FLASHBACK_ACH %s first=%s" % [flag, first])
	if not first:
		return
	var nm := flag
	var f := FileAccess.get_file_as_string(ACH_PATH)
	var j = JSON.parse_string(f)
	if j is Dictionary:
		for a in j.get("achievements", []):
			if (a.get("all", []) as Array) == [flag]:
				nm = str(a.get("zh" if I18n.is_zh() else "en", flag))
	_toast.text = "%s　%s" % [_tx("ach"), nm]
	var tw := create_tween()
	tw.tween_property(_toast, "modulate:a", 1.0, 0.5)
	tw.tween_interval(2.2)
	tw.tween_property(_toast, "modulate:a", 0.0, 0.8)


func _sleep(sec: float) -> void:
	await get_tree().create_timer(sec * _k).timeout


# ======================================================================= 醒
## 停在黑 / 白上的这一层慢慢睁眼：母星那一屏收掉，读屏幕的那层盖着原场景（全黑 / 全白、糊的），眼皮睁一半、合一点、再睁开
func wake() -> void:
	if is_instance_valid(_vp):
		_vp.queue_free()
	_view.visible = false
	_line_box.visible = false
	_hint.visible = false
	_chen = null
	_screen.visible = true
	var lids := _end_color != WHITE_C          # 白的：白慢慢退掉，不画眼皮
	_smat.set_shader_parameter("veil", _end_color)
	_smat.set_shader_parameter("veil_a", 0.0 if lids else 1.0)
	_smat.set_shader_parameter("lids", 1.0 if lids else 0.0)
	_smat.set_shader_parameter("blur", 5.0)
	_smat.set_shader_parameter("desat", 0.6)
	_smat.set_shader_parameter("vig", 0.6)
	_veil.color.a = 0.0
	_duck(false)
	var k := _k
	var tw := create_tween().set_parallel()
	if lids:
		var tl := create_tween()
		tl.tween_method(_sp.bind("lids"), 1.0, 0.45, 0.9 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
		tl.tween_method(_sp.bind("lids"), 0.45, 0.7, 0.35 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		tl.tween_method(_sp.bind("lids"), 0.7, 0.0, 1.1 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	else:
		tw.tween_method(_sp.bind("veil_a"), 1.0, 0.0, 1.6 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_method(_sp.bind("blur"), 5.0, 0.0, 2.8 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_method(_sp.bind("desat"), 0.6, 0.0, 2.8 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_method(_sp.bind("vig"), 0.6, 0.0, 2.8 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tw.finished
	var p := get_parent()
	if p is CanvasLayer:
		p.queue_free()
	else:
		queue_free()


# ======================================================================= 声音
func _play(snd: String, db: float) -> void:
	var p: String = runner._sfx_path(snd)
	if p == "":
		runner.missing_sfx[snd] = true
		return
	var a := AudioStreamPlayer.new()
	a.stream = load(p)
	a.bus = _bus
	a.volume_db = db
	add_child(a)
	a.play()
	a.finished.connect(a.queue_free)


## 底下一层循环的声音：城市先是雨（rain_loop），开跑以后换成紧张的音乐（flashback_tense，缺就留着雨）
func _music_on(snd: String, db: float) -> void:
	var p: String = runner._sfx_path(snd)
	if p == "":
		runner.missing_sfx[snd] = true
		return
	_music = AudioStreamPlayer.new()
	_music.stream = load(p)
	_music.bus = _bus
	_music.volume_db = -60.0
	_music.set_meta("snd", snd)
	add_child(_music)
	_music.play()
	create_tween().tween_property(_music, "volume_db", db, 1.5 * _k)


func _music_off(sec: float) -> void:
	if _music == null:
		return
	var m := _music
	_music = null
	var tw := create_tween()
	tw.tween_property(m, "volume_db", -60.0, sec * _k)
	tw.tween_callback(m.queue_free)


## 原场景的环境声（SFX 总线）在闪回期间压低，醒的时候放回去；中途被换场景扔掉也放回去
func _duck(on: bool) -> void:
	var i := AudioServer.get_bus_index("SFX")
	if i < 0:
		return
	if on and not _ducked:
		_ducked = true
		_sfx_db = AudioServer.get_bus_volume_db(i)
		var from := _sfx_db
		create_tween().tween_method(func(v: float): AudioServer.set_bus_volume_db(i, v), from, from - DUCK, 1.5 * _k)
		_tense_later()
	elif not on and _ducked:
		_ducked = false
		var cur := AudioServer.get_bus_volume_db(i)
		var to := _sfx_db
		create_tween().tween_method(func(v: float): AudioServer.set_bus_volume_db(i, v), cur, to, 0.5)


## 画面淡进来以后起紧张的音乐（缺文件就留着城市的雨 / 没有）
func _tense_later() -> void:
	await get_tree().create_timer(INTRO * _k * 0.8).timeout
	if not is_instance_valid(self) or result != "":
		return
	if runner._sfx_path("flashback_tense") == "":
		runner.missing_sfx["flashback_tense"] = true
		return
	var rain := _music
	_music = null
	_music_on("flashback_tense", -22.0)
	if rain != null:
		var tw := create_tween()
		tw.tween_property(rain, "volume_db", -30.0, 2.0)


func _exit_tree() -> void:
	if _ducked:
		var i := AudioServer.get_bus_index("SFX")
		if i >= 0:
			AudioServer.set_bus_volume_db(i, _sfx_db)
		_ducked = false
