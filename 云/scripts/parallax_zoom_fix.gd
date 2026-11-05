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
## 11-05 作者又抓到「还没缩放，底部的滤镜（天边贴着地面那道亮带）就消失」：天空层 scroll_scale (0,0) 是贴着屏幕的，剧情黑边放下来时
## 镜头被往下压 _cam_bar_dy（最多 26 像素），世界在屏幕上往上走、天空不动，天边那道亮带就滑到地面底下去了。
## 这里给竖直贴屏幕的层把黑边那几像素扣掉（screen_offset.y −= _cam_bar_dy），它就跟着地面走，黑边收起来再回来。

var _layers: Array[Parallax2D] = []
var _vp: Viewport
var _qa := "--qa_live" in OS.get_cmdline_user_args()
var _qa_said := false
var _qa_bar_said := false
var _qa_frames := 0
var _off := "--no_pzf" in OS.get_cmdline_user_args()      # 对比用：什么都不改，只报引擎自己算的位置


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
		_layers.append(n)


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
	if _qa and _layers.size() > 0 and ((absf(sc.x - 1.0) > 0.3 and not _qa_said) or (_qa_frames == 120) or (bar_dy > 0.5 and not _qa_bar_said)):     # --qa_live：第 120 帧（zoom 1）、黑边第一次压下来、推近时各报一次各层的位置，headless 也能核对
		_qa_said = _qa_said or absf(sc.x - 1.0) > 0.3
		_qa_bar_said = _qa_bar_said or bar_dy > 0.5
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
			if p.scroll_scale.y == 0.0:
				so.y -= bar_dy                 # 竖直贴着屏幕的层（天空）：黑边把镜头往下压的那几像素不跟，天边那道亮带留在地面上方
			p.screen_offset = so
		i += 1
