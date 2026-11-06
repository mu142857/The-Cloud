extends Node
## Parallax2D 在镜头缩放时的偏移修正（11-05 作者截图：坠毁后连按 Q 起身、镜头推近到 1.4 倍，背景几层树整体往上往左跑，「树木都离地了」）。
##
## 原因：Godot 4.7 的 Camera2D 发给 Parallax2D 的 adj_screen_pos = 镜头中心 − 屏幕尺寸 / 2，屏幕尺寸没除以 zoom。
## 镜头推近时各视差层就按这个错的「屏幕左上角」摆，scroll_scale 越小偏得越多：1.45 倍时 Ridge（0.06）上偏 35 像素、
## 左偏 62 像素，Mid（0.62）上偏 14 像素；Main（1.0）不偏，所以地面、晨、残骸都对，只有树离了地。
##
## 做法：把本关（同一个 viewport）里所有 Parallax2D 设成 ignore_camera_scroll，每帧用真正的画布变换算屏幕左上角
## （−origin / zoom，就是镜头实际画出来的那块的左上角），自己喂给 screen_offset。zoom = 1 时和引擎算的一模一样，
## 所以开关这个修正不会跳；缩放时各层就都按同一个中心缩放，树根一直贴着地。后来才建出来的层（story_world 的雾）也会接上。
##
## 11-05 作者：「背景的绿色的雾怎么消失了」。这层绿雾就是天空层（sky.png）贴图 y 130–195 那道亮带，别的层没有（夜测 PNG 和作者截图的
## 透明像素都核对过）。天空本来竖直贴屏幕，夜测里「对」的样子其实是：黑边放下时世界被 _cam_bar_dy（坠毁现场 17）往上压，地面 229 到了屏幕 212，
## 刚好接上亮带的下沿；没黑边时亮带离地 33 像素，所以「还没缩放，底部的滤镜就消失」。推近时再按屏幕左上角算，亮带被推到地面后面（作者截图 y≈45，
## 亮带峰值贴着地面、中段全黑）。
## 现在：天空竖直钉在世界里 SKY_Y（= 夜测的样子，亮带下沿始终接着地面），黑边、推近都不再动它，三种状态都一样。
## 只有镜头往上摇（P < 0：看树冠、起飞）时跟着屏幕，和以前一样。标题画面没动过（SKY_Y = 0），开始游戏时跟着黑边放下的速度滑到 SKY_Y，看上去就是地面在往上走。
## 没盖到的最上面 17 行由 _sky_top 补（sky.png 第 0 行的颜色），level_forest 的闪电调 Sky 的 modulate 也跟着变。

const SKY_Y := 17.0                     # 天空贴图的 y 0 在世界 y 几：坠毁现场黑边放下时的 _cam_bar_dy
const SKY_RATE := 21.25                 # 像素 / 秒：标题 → 坠毁时跟 _bars_in(0.8) 同步（17 / 0.8）
const SKY_TOP_C := Color8(5, 12, 10)    # sky.png 第 0 行（整行同一色）
const TITLE_STATES := 2                 # level_forest 的 enum S：HEADPHONES 0、INTRO 1、TITLE 2（这几个 state 天空在 y 0）
const STATE_PLAY := 4

var _layers: Array[Parallax2D] = []
var _vp: Viewport
var _qa := "--qa_live" in OS.get_cmdline_user_args()
var _qa_said := false
var _qa_bar_said := false
var _qa_frames := 0
var _off := "--no_pzf" in OS.get_cmdline_user_args()      # 对比用：什么都不改，只报引擎自己算的位置
var _sky_y := NAN
var _qa_free_said := false


func _ready() -> void:
	_vp = get_viewport()
	for n in _walk(_vp):
		_take(n)
	get_tree().node_added.connect(_take)
	process_priority = 1000                 # 排在同一帧所有 _process 之后；Camera2D 的画布变换是在内部 process 里先算好的，这里读到的就是这一帧画的那份


func _process(_delta: float) -> void:
	_qa_frames += 1
	_fix()


func _walk(n: Node) -> Array:
	var out: Array = [n]
	for c in n.get_children():
		out.append_array(_walk(c))
	return out


func _take(n: Node) -> void:
	if n is Parallax2D and n.get_viewport() == _vp and not _layers.has(n):
		if not _off:
			(n as Parallax2D).ignore_camera_scroll = true
			if _is_sky(n):
				var top := ColorRect.new()      # 天空往下钉了 SKY_Y，上面露出来的那几行
				top.name = "SkyTop"
				top.color = SKY_TOP_C
				top.position = Vector2(-240.0, -400.0)
				top.size = Vector2(960.0, 400.0)
				top.mouse_filter = Control.MOUSE_FILTER_IGNORE
				n.add_child(top)
		_layers.append(n)


func _is_sky(p: Node) -> bool:
	return p.name == &"Sky" and p.get_parent() == get_parent() and (p as Parallax2D).scroll_scale.y == 0.0


func _fix() -> void:
	if _vp == null or not is_instance_valid(_vp):
		return
	var xf := _vp.get_canvas_transform()
	var sc := xf.get_scale()
	if sc.x <= 0.0 or sc.y <= 0.0:
		return
	var top_left := Vector2(-xf.origin.x / sc.x, -xf.origin.y / sc.y)
	var lv := get_parent()
	var bar_dy: float = float(lv.get("_cam_bar_dy")) if lv != null and lv.get("_cam_bar_dy") != null else 0.0
	var st: int = int(lv.get("state")) if lv != null and lv.get("state") != null else STATE_PLAY
	var sky_want := 0.0 if st <= TITLE_STATES else SKY_Y
	_sky_y = sky_want if is_nan(_sky_y) else move_toward(_sky_y, sky_want, SKY_RATE * get_process_delta_time())
	var pan := minf(top_left.y + 135.0 / sc.y - 135.0 - bar_dy, 0.0)      # 镜头往上摇了多少（往下的不算：推近时镜头是往下走的）
	if _qa and _layers.size() > 0 and ((absf(sc.x - 1.0) > 0.3 and not _qa_said) or (_qa_frames == 120) or (bar_dy >= 16.5 and absf(sc.x - 1.0) < 0.01 and not _qa_bar_said) or (st >= STATE_PLAY and bar_dy < 0.5 and absf(sc.x - 1.0) < 0.001 and absf(top_left.y) < 0.5 and not _qa_free_said)):     # --qa_live：第 120 帧（zoom 1）、黑边全放下、推近、自由走没黑边时各报一次各层的位置，headless 也能核对
		_qa_said = _qa_said or absf(sc.x - 1.0) > 0.3
		_qa_bar_said = _qa_bar_said or (bar_dy >= 16.5 and absf(sc.x - 1.0) < 0.01)
		_qa_free_said = _qa_free_said or (st >= STATE_PLAY and bar_dy < 0.5 and absf(sc.x - 1.0) < 0.001 and absf(top_left.y) < 0.5)
		var parts: Array = []
		for p in _layers:
			if is_instance_valid(p):
				parts.append("%s=%s%s" % [p.name, p.position.round(), "" if p.visible else "(hidden)"])
		var fog := ""
		var w = lv.get("story").world if lv != null and lv.get("story") != null else null
		if w != null and w.get("_fog_back") != null:
			var mb: ShaderMaterial = w._fog_back.get_meta("mat")
			fog = " fog_k=%.2f back_density=%.2f fill=%.2f room=%s" % [float(w.fog_k), float(mb.get_shader_parameter("density")), float(mb.get_shader_parameter("fill")), str(w.room)]
		print("PZF zoom=%.2f top_left=%s bar_dy=%d%s %s" % [sc.x, top_left.round(), int(bar_dy), fog, " ".join(parts)])
	var i := 0
	while i < _layers.size():
		var p := _layers[i]
		if not is_instance_valid(p) or not p.is_inside_tree():
			_layers.remove_at(i)
			continue
		if not _off:
			var so := top_left
			if _is_sky(p):
				so.y = roundf(_sky_y + pan)    # 竖直钉在世界里（scroll_scale 0：位置就是 screen_offset），见文件头
			p.screen_offset = so
		i += 1
