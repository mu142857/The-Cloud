extends RefCounted
## 第一关小游戏 run_credits：奔跑片头的制作人员（docs/剧情改动/第一关新版_实现规格.md 第 6 步；11-02 作者：要像 Linger、
## Oscar Rush 的片尾那样好看，每个人一个自己的小场景，不要一条条淡入淡出的名单）。
##   晨跟着鹿往右跑过空林子，每个名字是林子里的一个时刻，挂在晨前方的某一处（世界里的一个点），随晨往前跑一起往后退：
##     木木       萤火虫从四周飞来，一只只停成名字的笔画，名字一闪一闪地亮；走的时候萤火虫各自往上飞散
##     本2兔      一团雾飘进来，一点光像笔尖在雾里从左往右写过去，写出来的字是光
##     梧桐       梧桐叶从上面飘下来，一片片落成名字；走的时候一阵风从右边把叶子吹走
##     奥斯卡     林子里斜着落下一束光，名字在光里一个像素一个像素地画出来（他是画像素的人），光里飘着灰尘
##     （sky：片头现在没人用）最后在树冠上面的黑里，像星星一样一颗颗亮起来（钉在屏幕上，像天）
##   写法、颜色照 Linger / Oscar Rush 的片尾：职务小字（14 号）在上，名字 28 号（两倍）在下，各人自己的颜色。
##   景深 depth：名字在屏幕上的移动速度 = 晨脚下地面的 depth 倍（越远越慢），所以跑起来名字是在远处慢慢往后退，看得清。
##   跑 920 像素只要 4 秒，所以名字按时间错开（gap 秒一个）；轮到谁，就把它放在当时镜头中心右边 dx 屏幕像素处
##   （也可以写死世界 x），之后它就钉在那个世界位置上，跟着晨的 x 走。晨停下（捡背包）名字也就停在那里。
##   走完自己释放；离开森林（进树屋）就收掉。
##   11-05 作者「跑的时间不够显示所有人名」「都跑到了才显示奥斯卡和梧桐，这肯定来不及」：Shift 跑到背包只要 4 秒多，
##   所以 credits.json 的 start 排成：木木 0、本2兔 0.4、梧桐 1.2、奥斯卡 1.8（后两个 pace 1.4 成形快一点），跑到之前四个都成形；
##   四个 depth 相同（在屏幕上一起退，彼此距离只会变大），分上下两行、都在晨那句「好熟悉的感觉……」（天空 y 45–62）下面。
##   11-05 作者：Sothere456 森林这里去掉；特别感谢是一个大列表，只在制作人员页（credits.json 的 special_thanks 写 "run": false：片头跳过，credits_page 按 id 读）。--qa_live 打印 QA_CREDITS（每个名字 begin / formed、晨跑到背包），
##   并且量名字（qa_label）和别的字叠不叠。
##
## 11-07 作者（intro 模式 = 森林里 c1_run 那段「原地循环跑」）：不换配乐（c1_run 里切 theme 的那步删了）；CG 一开始就自动跑，不用一直按 Shift。
##   「必须按 Shift 才能出去」放到了 CG 之前的走路那段（scripts/c1_loop.gd 的跑步机）。CG 也在那个跑步机上跑（loop.cg_begin），
##   结束时各层正好卷到整圈，晨站在原地接着玩；没有 C1Loop 节点时退回原来的 tween 卷三圈。
##
## 剧本步骤：{"do": "mechanic", "id": "run_credits", "wait": false}
##   可选："file": 名单文件（默认 res://data/credits.json）。
##   不挡剧情：run() 把这一层挂到关卡上就返回（自己往下播），runner 照常 await 也不会卡住。
## 名单：data/credits.json（字段说明在文件里）。名字和顺序是作者定的；职务是猜的（role_guess），等作者改。
## 音乐：credits.json 的 music（默认 res://audio/music/theme.ogg）有这个文件就放（Music 总线，2 秒淡入，放完自己释放）。
## 中途收掉：level.get_node("RunCredits").finish(0.8)（名字散掉；音乐不停，要停用 finish(0.8, true)）。
## 字：天王星像素 14 号的字形轮廓（TextServer.font_get_glyph_contours，整数坐标）在运行时拆成像素，每个像素是萤火虫 / 叶子 / 星星
##   要落的地方，所以名单改了不用重新画图。画在关卡里森林主层（Main）后面一格：主层树干前面、晨和前景后面。

const ID := "run_credits"
const FILE := "res://data/credits.json"
const MUSIC := "res://audio/music/theme.ogg"


static func load_list(path := FILE) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var v = JSON.parse_string(FileAccess.get_file_as_string(path))
	return v if v is Dictionary else {}


## 全部播完大概要多久（最后一个出现 + 成形 + 停留 + 散掉）
static func total_sec(d: Dictionary) -> float:
	var t := 0.0
	var es: Array = d.get("entries", [])
	for i in es.size():
		if not es[i].get("run", true):
			continue
		t = maxf(t, Roll.start_of_entry(d, i) + Moment.FORM_SEC + float(es[i].get("hold", Moment.HOLD)) + Moment.LEAVE_SEC)
	return t


static func load_music(path: String) -> AudioStream:
	if ResourceLoader.exists(path):
		return load(path) as AudioStream
	if FileAccess.file_exists(path):           # 刚放进来、编辑器还没导入：直接读 ogg
		return AudioStreamOggVorbis.load_from_file(ProjectSettings.globalize_path(path))
	return null


# ======================================================================= 演出
var speed := 1.0


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	if r.ff:
		return
	var d := load_list(str(st.get("file", FILE)))
	if d.is_empty() or (d.get("entries", []) as Array).is_empty():
		push_warning("run_credits：%s 读不到 / 是空的，不出字幕" % st.get("file", FILE))
		return
	var old := lv.get_node_or_null("RunCredits")
	if old != null:
		old.name = "RunCreditsOld"
		old.queue_free()
	var roll := Roll.new()
	roll.name = "RunCredits"
	lv.add_child(roll)
	var main := lv.get_node_or_null("Main")
	if main != null:
		lv.move_child(roll, main.get_index() + 1)
	roll.setup(d, speed, r)
	if not st.get("intro", false):
		_start_music(d, lv)
	print("MECH %s started entries=%d sec=%.1f" % [ID, roll._ms.size(), total_sec(d) / speed])
	if st.get("intro", false):
		var loop := lv.get_node_or_null("C1Loop")
		if loop != null and loop.has_method("cg_begin"):
			# 第一关：跑步机（scripts/c1_loop.gd）上自动跑，卷的速度算好，播完正好卷到整圈，放开以后画面不跳
			loop.cg_begin(total_sec(d) / speed)
			while is_instance_valid(loop) and loop.cg_running():
				await lv.get_tree().process_frame
		else:
			await _forest_loop(lv, total_sec(d) / speed)


func _forest_loop(lv: Node2D, duration: float) -> void:
	var chen: Node2D = lv.chen
	chen.intro_run = true
	chen.auto_dir = 1.0
	var cycles := {"Far": 1, "MidFar": 1, "Mid": 2, "Main": 3, "Front": 4}
	var offsets := {}
	var scroll := lv.create_tween().set_parallel()
	for layer_name in cycles:
		var layer := lv.get_node(layer_name) as Parallax2D
		offsets[layer] = layer.scroll_offset
		scroll.tween_property(layer, "scroll_offset:x", layer.scroll_offset.x - layer.repeat_size.x * float(cycles[layer_name]), duration)
	await scroll.finished
	for layer: Parallax2D in offsets:
		layer.scroll_offset = offsets[layer]
	chen.intro_run = false
	chen.auto_dir = 0.0


## 自动玩：一样不挡，按真实的快慢放（--qa_live 要量名字和晨那句潜意识字叠不叠，快了就不准）
func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	speed = 5.0 if st.get("intro", false) else 1.0
	await run(lv, w, r, st)


func ff(_r: Node, _st: Dictionary) -> void:
	pass                                       # 没有进度；跳节拍就不出字幕


func check(_story: Node, st: Dictionary) -> Array:
	var out: Array = []
	var d := load_list(str(st.get("file", FILE)))
	if d.is_empty():
		out.append("credits 名单 %s 读不到" % st.get("file", FILE))
		return out
	var es: Array = d.get("entries", [])
	if es.is_empty():
		out.append("credits 名单是空的")
	for e in es:
		if not str(e.get("style", "")) in Moment.STYLES:
			out.append("credits %s 的 style %s 不认识（%s）" % [e.get("id"), e.get("style"), ", ".join(Moment.STYLES)])
		if e.get("role_guess", false):
			out.append("info: credits %s 的职务是猜的，等作者改" % e.get("id"))
	if not st.get("intro", false) and load_music(str(d.get("music", MUSIC))) == null:
		out.append("info: 主题曲 %s 还没有，只出字幕" % d.get("music", MUSIC))
	return out


## 主题曲：Music 总线，从 -30 dB 用 2 秒淡到 0；挂在关卡下面，放完自己释放
func _start_music(d: Dictionary, lv: Node) -> void:
	var stream := load_music(str(d.get("music", MUSIC)))
	if stream == null:
		print("MECH %s：没有主题曲，只出字幕" % ID)
		return
	var old := lv.get_node_or_null("ThemeMusic")
	if old != null:
		old.queue_free()
	var m := AudioStreamPlayer.new()
	m.name = "ThemeMusic"
	m.stream = stream
	m.bus = "Music" if AudioServer.get_bus_index("Music") >= 0 else "Master"
	m.volume_db = -30.0
	lv.add_child(m)
	m.play()
	m.finished.connect(m.queue_free)
	m.create_tween().tween_property(m, "volume_db", 0.0, 2.0 / speed).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)


# ----------------------------------------------------------------------- 整串：按时间一个个叫出来，每帧按镜头摆位置
class Roll extends Node2D:
	var _speed := 1.0
	var _story: Node
	var _t := 0.0
	var _ms: Array = []
	var _ending := false
	var _qa := false                 # --qa_live：打印 QA_CREDITS
	var _chen_arrived := false
	var _chen_max_v := 0.0

	static func start_of_entry(d: Dictionary, i: int) -> float:
		var e: Dictionary = (d.get("entries", []) as Array)[i]
		return float(e.get("start", float(d.get("gap", 2.0)) * i))

	func setup(d: Dictionary, speed: float, story: Node) -> void:
		_speed = speed
		_story = story
		_qa = "--qa_live" in OS.get_cmdline_user_args()
		var es: Array = d.get("entries", [])
		for i in es.size():
			if not es[i].get("run", true):
				continue                     # "run": false = 只在制作人员页出，片头跳过
			var m := Moment.new()
			m.setup(es[i], start_of_entry(d, i))
			add_child(m)
			_ms.append(m)

	func _process(dt: float) -> void:
		_t += dt * _speed
		var cam := get_viewport().get_camera_2d()
		var cc: Vector2 = cam.get_screen_center_position() if cam != null else Vector2(240, 135)
		var z: float = cam.zoom.x if cam != null else 1.0
		var live := 0
		for m in _ms:
			if not m.begun and _t >= m.start_at and not _ending:
				m.begin(cc, z)
				if _qa:
					print("QA_CREDITS begin %s t=%.2f" % [m.e.get("id", ""), _t])
			m.place(cc, z)
			var was_forming: bool = m.begun and m._t < Moment.FORM_SEC
			m.step(dt * _speed)
			if _qa and was_forming and m._t >= Moment.FORM_SEC:
				print("QA_CREDITS formed %s t=%.2f" % [m.e.get("id", ""), _t])
			if not m.finished():
				live += 1
		if _qa and not _chen_arrived and _story != null and _story.get("chen") != null:
			_chen_max_v = maxf(_chen_max_v, float(_story.chen._vel))
			if str(_story.get("_cur_scene")) == "c1_got_bag":        # 跑到背包了（enter 触发，接着就停下捡）
				_chen_arrived = true
				print("QA_CREDITS chen_arrive t=%.2f max_vel=%.0f" % [_t, _chen_max_v])
		if live == 0 or _t > 90.0:
			queue_free()
			return
		# 离开森林（进树屋 / 换章节）：收掉
		if not _ending and _story != null and "world" in _story and _story.world != null and "room" in _story.world \
				and str(_story.world.room) != "forest":
			finish(0.4)

	## 提前收掉：还没出来的不出了，出来的都散掉（stop_music = 歌也淡掉停）
	func finish(sec := 0.8, stop_music := false) -> void:
		_ending = true
		for m in _ms:
			m.leave_now(sec)
		if stop_music and get_parent() != null:
			var mu := get_parent().get_node_or_null("ThemeMusic")
			if mu != null:
				var tw := mu.create_tween()
				tw.tween_property(mu, "volume_db", -40.0, sec)
				tw.tween_callback(mu.queue_free)
		var t := create_tween()
		t.tween_interval(sec + 0.7)
		t.tween_callback(queue_free)


# ----------------------------------------------------------------------- 字 → 像素
class Glyphs:
	## text 用天王星像素 size 号排一行，拆成像素：{w, h, px: 每个像素的左上角}
	static func mask(text: String, size := 14) -> Dictionary:
		var font: Font = UITheme.font()
		var ts := TextServerManager.get_primary_interface()
		var line := TextLine.new()
		line.add_string(text, font, size)
		var rid := line.get_rid()
		var asc := int(round(ts.shaped_text_get_ascent(rid)))
		var w := int(ceil(line.get_size().x))
		var h := int(ceil(line.get_size().y))
		var px := PackedVector2Array()
		var pen := 0.0
		for g in ts.shaped_text_get_glyphs(rid):
			var adv := float(g.get("advance", 0.0))
			var virtual := (int(g.get("flags", 0)) & TextServer.GRAPHEME_IS_VIRTUAL) != 0
			for k in maxi(1, int(g.get("repeat", 1))):
				if not virtual and int(g.get("index", 0)) != 0:
					var c: Dictionary = ts.font_get_glyph_contours(g["font_rid"], int(g["font_size"]), int(g["index"]))
					var off: Vector2 = g.get("offset", Vector2.ZERO)
					_fill(px, c, Vector2(pen, asc) + off, w, h)
				pen += adv
		return {"w": w, "h": h, "px": px}

	## 轮廓（整数坐标的直线段）按非零环绕规则填进像素中心
	static func _fill(out: PackedVector2Array, c: Dictionary, o: Vector2, w: int, h: int) -> void:
		var pts: PackedVector3Array = c.get("points", PackedVector3Array())
		var ends: PackedInt32Array = c.get("contours", PackedInt32Array())
		if pts.is_empty():
			return
		var edges: Array = []
		var s := 0
		for e in ends:
			for i in range(s, e + 1):
				var a := pts[i]
				var b := pts[s if i == e else i + 1]
				if a.y != b.y:
					edges.append([Vector2(a.x, a.y) + o, Vector2(b.x, b.y) + o])
			s = e + 1
		for y in h:
			var cy := y + 0.5
			var xs: Array = []
			for ed in edges:
				var a: Vector2 = ed[0]
				var b: Vector2 = ed[1]
				if (cy >= a.y and cy < b.y) or (cy >= b.y and cy < a.y):
					xs.append([a.x + (cy - a.y) / (b.y - a.y) * (b.x - a.x), 1 if b.y > a.y else -1])
			xs.sort_custom(func(p, q): return p[0] < q[0])
			var wind := 0
			for j in xs.size() - 1:
				wind += int(xs[j][1])
				if wind == 0:
					continue
				for x in range(int(ceil(float(xs[j][0]) - 0.5)), int(ceil(float(xs[j + 1][0]) - 0.5))):
					if x >= 0 and x < w:
						out.append(Vector2(x, y))


# ----------------------------------------------------------------------- 一个名字的时刻
class Moment extends Node2D:
	const STYLES := ["fireflies", "mist", "leaves", "light", "sky"]
	const FORM_SEC := 2.2            # 成形大概多久（各样子自己的节奏都在这里面）
	const HOLD := 1.8                # 完整停留（credits.json 的 hold 可改）
	const LEAVE_SEC := 1.4
	const SCALE := 2                 # 名字两倍（28 号）；职务一倍（14 号）
	const LINE_GAP := 2              # 一列名字（names）行和行之间
	const HEAD := Color(0.62, 0.6, 0.58)          # 职务：Linger 片尾的 HEAD_COLOR
	const SHADOW := Color(0.02, 0.04, 0.035, 0.8)

	var e: Dictionary
	var style := ""
	var start_at := 0.0
	var begun := false
	var anchor := Vector2.ZERO       # 世界 x, y（sky：y 是屏幕 y）
	var depth := 0.2
	var col := Color.WHITE
	var hold := HOLD
	var pace := 1.0                  # 成形快几倍（credits.json 的 pace；成形完照常按秒停）
	var _t := 0.0                    # 成形开始后过了多久
	var _leave_t := -1.0             # 开始散以后过了多久（< 0 = 还没散）
	var _leave_len := LEAVE_SEC
	var _done := false
	var _rng := RandomNumberGenerator.new()
	var _glow: Node2D                # 加法混合那一层（光晕、光柱），画在字下面
	var _blk := PackedVector2Array() # 名字的像素块（左上角，本地坐标，已经放大两倍）
	var _role := PackedVector2Array()
	var _role_at := Vector2.ZERO
	var _role_sz := Vector2.ZERO
	var _box := Rect2()              # 名字那一块
	# 每个像素块：起点、控制点、延迟、时长、相位、颜色档；散的时候去哪、控制点、延迟
	var _from := PackedVector2Array()
	var _ctrl := PackedVector2Array()
	var _delay := PackedFloat32Array()
	var _dur := PackedFloat32Array()
	var _ph := PackedFloat32Array()
	var _shade := PackedInt32Array()
	var _away := PackedVector2Array()
	var _away_c := PackedVector2Array()
	var _away_d := PackedFloat32Array()
	var _extra: Array = []           # 绕着名字的萤火虫 / 飘过的叶子 / 光里的灰尘 / 旁边的小星星：[Vector2(-1..1), 相位, 0..1]
	var _col_y := PackedFloat32Array()   # mist：每一列笔画的平均 y（笔尖顺着走）

	func setup(entry: Dictionary, at: float) -> void:
		e = entry
		style = str(e.get("style", "fireflies"))
		start_at = at
		depth = float(e.get("depth", 0.0 if style == "sky" else 0.2))
		hold = float(e.get("hold", HOLD))
		pace = float(e.get("pace", 1.0))
		col = Color(str(e.get("color", "d8d4cc")))
		_rng.seed = hash(str(e.get("id", "")))
		visible = false
		if style == "sky":
			z_index = 10                 # 天上那句画在前景（Front）的树枝上面，不被挡
		_glow = Node2D.new()
		var mat := CanvasItemMaterial.new()
		mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		_glow.material = mat
		_glow.show_behind_parent = true
		_glow.draw.connect(_draw_glow)                 # 画在 _glow 上（_glow_* 里都是 _glow.draw_*）
		add_child(_glow)
		_layout()

	func finished() -> bool:
		return _done

	## 轮到它了：钉在镜头中心右边 dx 屏幕像素处的世界 x（写了 x 就用 x）
	func begin(cc: Vector2, z: float) -> void:
		begun = true
		visible = true
		if style == "sky":
			anchor = Vector2(0, float(e.get("screen_y", 40)))
		elif e.has("x"):
			anchor = Vector2(float(e["x"]), float(e.get("y", 100)))
		else:
			anchor = Vector2(cc.x + float(e.get("dx", 70)) / maxf(0.05, depth * z), float(e.get("y", 100)))

	func place(cc: Vector2, z: float) -> void:
		if not begun or _done:
			return
		var p: Vector2
		if style == "sky":
			p = Vector2(cc.x + (float(e.get("screen_x", 240.0)) - 240.0) / z, cc.y + (anchor.y - 135.0) / z)   # 钉在屏幕上
		else:
			p = Vector2(cc.x + (anchor.x - cc.x) * depth, anchor.y)
			if absf(p.x - cc.x) * z > 240.0 + _box.size.x * z and _t > 0.2:
				_done = true                                                         # 已经退出画面了
				visible = false
		position = p.round()

	## --qa_live（qa_live.gd 的 _collect）：这个名字现在在屏幕上占的框（职务 + 名字）；还没成形 / 散到一半以后不算
	func qa_label() -> Dictionary:
		if not begun or _done or not visible or _t < 0.3:
			return {}
		if _leave_t >= 0.0 and _leave_t > _leave_len * 0.5:
			return {}
		var r := Rect2(_role_at, _role_sz).merge(_box)
		return {"text": I18n.pick(e.get("name", e.get("role", {}))), "r": get_global_transform_with_canvas() * r}

	func screen_x(cc: Vector2, z: float) -> float:
		return 240.0 + (position.x - cc.x) * z

	func step(dt: float) -> void:
		if not begun or _done:
			return
		_t += dt * (pace if _t < FORM_SEC else 1.0)
		if _leave_t < 0.0 and _t >= FORM_SEC + hold:
			_leave_t = 0.0
		elif _leave_t >= 0.0:
			_leave_t += dt
			if _leave_t >= _leave_len + 0.6:
				_done = true
				visible = false
		queue_redraw()
		_glow.queue_redraw()

	func leave_now(sec: float) -> void:
		if not begun:
			_done = true
			return
		if _leave_t < 0.0:
			_leave_t = 0.0
			_leave_len = minf(LEAVE_SEC, sec)

	# ------------------------------------------------------------------- 布局 + 每个像素块的路线
	func _layout() -> void:
		var rl := Glyphs.mask(I18n.pick(e.get("role", {})))
		var lines: Array = []                                                        # names = 一列名字（制作人员页的特别感谢）；平常就一个 name
		for nd in e.get("names", [e.get("name", {})]):
			lines.append(Glyphs.mask(I18n.pick(nd)))
		var nw := 0
		var nh := LINE_GAP * (lines.size() - 1)
		for nm in lines:
			nw = maxi(nw, int(nm["w"]) * SCALE)
			nh += int(nm["h"]) * SCALE
		var rw := int(rl["w"])
		var rh := int(rl["h"])
		var top := -(rh + 3 + nh) / 2
		_role_at = Vector2(-rw / 2, top)
		_role_sz = Vector2(rw, rh)
		for p in rl["px"]:
			_role.append(p)
		_box = Rect2(-nw / 2, top + rh + 3, nw, nh)
		var ly := _box.position.y
		for nm in lines:
			var o := Vector2(-int(nm["w"]) * SCALE / 2, ly)                          # 每行各自居中
			for p in nm["px"]:
				_blk.append(o + p * SCALE)
			ly += int(nm["h"]) * SCALE + LINE_GAP
		var n := _blk.size()
		_from.resize(n); _ctrl.resize(n); _away.resize(n); _away_c.resize(n)        # Packed 数组是值类型：一个个 resize
		_delay.resize(n); _dur.resize(n); _ph.resize(n); _away_d.resize(n); _shade.resize(n)
		var w := maxf(1.0, _box.size.x)
		for i in n:
			var tg := _blk[i] + Vector2(1, 1)
			_ph[i] = _rng.randf() * TAU
			var r := _rng.randf()
			_shade[i] = 0 if r < 0.6 else (1 if r < 0.85 else 2)
			var fx := (tg.x - _box.position.x) / w                                   # 0 左 .. 1 右
			match style:
				"fireflies":
					var a := _rng.randf_range(-PI, PI)
					var rad := _rng.randf_range(50.0, 120.0)
					_from[i] = tg + Vector2(cos(a) * rad * 1.3, sin(a) * rad * 0.7 + 24.0)
					_ctrl[i] = (_from[i] + tg) / 2.0 + Vector2(_rng.randf_range(-40, 40), _rng.randf_range(-30, 30))
					_delay[i] = _rng.randf_range(0.0, 0.9)
					_dur[i] = _rng.randf_range(1.0, 1.3)
					_away[i] = tg + Vector2(_rng.randf_range(-36, 36), _rng.randf_range(-80, -34))
					_away_c[i] = (tg + _away[i]) / 2.0 + Vector2(_rng.randf_range(-28, 28), 10)
					_away_d[i] = _rng.randf_range(0.0, 0.5)
				"leaves":
					_from[i] = Vector2(tg.x + _rng.randf_range(-50, 50), _box.position.y - _rng.randf_range(80, 140))
					_delay[i] = _rng.randf_range(0.0, 0.8)
					_dur[i] = _rng.randf_range(1.1, 1.4)
					_away[i] = tg + Vector2(-_rng.randf_range(70, 150), -_rng.randf_range(10, 44))
					_away_c[i] = (tg + _away[i]) / 2.0 + Vector2(0, -_rng.randf_range(10, 30))
					_away_d[i] = (1.0 - fx) * 0.5 + _rng.randf_range(0.0, 0.15)          # 风从右边来：右边的先走
				"mist":
					_away_d[i] = fx * 0.6                                                # 左边先淡（先写的先散）
				"light":
					_delay[i] = 0.55 + 1.35 * clampf(fx + _rng.randf_range(-0.08, 0.08), 0.0, 1.0)   # 从左往右一个个画
					_away_d[i] = _rng.randf_range(0.0, 0.6)
				"sky":
					_delay[i] = 0.2 + _rng.randf() * 1.6                                   # 乱序一颗颗亮
					_away_d[i] = _rng.randf_range(0.0, 0.7)
		if style == "mist":
			_col_y.resize(int(_box.size.x) + 1)
			var cnt := PackedFloat32Array()
			cnt.resize(_col_y.size())
			for p in _blk:
				var c := clampi(int(p.x - _box.position.x), 0, _col_y.size() - 1)
				_col_y[c] += p.y + 1.0
				cnt[c] += 1.0
			var last := _box.get_center().y
			for c in _col_y.size():
				last = _col_y[c] / cnt[c] if cnt[c] > 0.0 else last
				_col_y[c] = last
		var k: int = {"fireflies": 9, "leaves": 7, "light": 12, "sky": 14}.get(style, 0)
		for j in k:
			_extra.append([Vector2(_rng.randf_range(-1.0, 1.0), _rng.randf_range(-1.0, 1.0)), _rng.randf() * TAU, _rng.randf()])

	# ------------------------------------------------------------------- 画
	static func _e(k: float) -> float:
		return 0.5 - 0.5 * cos(clampf(k, 0.0, 1.0) * PI)

	static func _bez(a: Vector2, c: Vector2, b: Vector2, u: float) -> Vector2:
		return a.lerp(c, u).lerp(c.lerp(b, u), u)

	## 散的进度（0..1）：每块按自己的延迟错开
	func _leave_k(i: int, part := 0.7) -> float:
		if _leave_t < 0.0:
			return 0.0
		return clampf((_leave_t - _away_d[i] * _leave_len / LEAVE_SEC) / (_leave_len * part), 0.0, 1.0)

	func _role_a() -> float:
		var a := _e((_t - FORM_SEC * 0.55) / 0.7)
		if _leave_t >= 0.0:
			a *= 1.0 - _e(_leave_t / 0.5)
		return a

	func _extra_alpha() -> float:
		var a := _e(_t / 1.2)
		if _leave_t >= 0.0:
			a *= 1.0 - _e(_leave_t / _leave_len)
		return a

	func _draw() -> void:
		if not begun:
			return
		var ra := _role_a()
		if ra > 0.01:
			for p in _role:
				draw_rect(Rect2(_role_at + p + Vector2(1, 1), Vector2.ONE), Color(SHADOW, SHADOW.a * ra))
			for p in _role:
				draw_rect(Rect2(_role_at + p, Vector2.ONE), Color(HEAD, ra))
		match style:
			"fireflies": _draw_fireflies()
			"mist": _draw_mist()
			"leaves": _draw_leaves()
			"light": _draw_light()
			"sky": _draw_sky()

	func _draw_glow() -> void:
		if not begun:
			return
		match style:
			"fireflies": _glow_fireflies()
			"mist": _glow_mist()
			"light": _glow_light()
			"sky": _glow_sky()

	# ---- 木木：萤火虫
	const FLY := Color("#e6ff9c")
	const FLY_GLOW := Color(0.35, 0.95, 0.4)

	func _fly_pos(i: int) -> Vector2:
		var lk := _leave_k(i)
		if lk > 0.0:
			return _bez(_blk[i] + Vector2(1, 1), _away_c[i], _away[i], _e(lk)) + Vector2(3.0 * sin(_t * 4.0 + _ph[i]) * lk, 0.0)
		var u := _e((_t - _delay[i]) / _dur[i])
		var p := _bez(_from[i], _ctrl[i], _blk[i] + Vector2(1, 1), u)
		var side := (_blk[i] - _from[i]).normalized().orthogonal()
		return p + side * 4.0 * sin(_t * 5.0 + _ph[i]) * (1.0 - u)                  # 飞的时候一摆一摆

	func _landed(i: int) -> bool:
		return _t >= _delay[i] + _dur[i] and _leave_k(i) <= 0.0

	func _fly_alpha(i: int) -> float:
		var lk := _leave_k(i)
		if lk > 0.0:
			return 1.0 - _e(lk)
		return clampf((_t - _delay[i]) / 0.35, 0.0, 1.0)

	## 绕着名字慢慢转的萤火虫（两条不同周期的正弦）
	func _wander(x: Array) -> Vector2:
		var v: Vector2 = x[0]
		var ph: float = x[1]
		return _box.get_center() + Vector2(
			(_box.size.x / 2.0 + 14.0) * sin(_t * 0.37 + ph) * absf(v.x) + 6.0 * sin(_t * 1.3 + ph * 2.0),
			(_box.size.y / 2.0 + 10.0) * sin(_t * 0.29 + ph * 1.7) * absf(v.y) + 3.0 * sin(_t * 1.7 + ph))

	func _draw_fireflies() -> void:
		var light := col.lerp(Color.WHITE, 0.45)
		for i in _blk.size():
			if _landed(i):
				var tw := 0.5 + 0.5 * sin(_t * 2.3 + _ph[i])
				draw_rect(Rect2(_blk[i], Vector2(2, 2)), col.lerp(light, 0.15 + 0.35 * tw))
			else:
				var a := _fly_alpha(i)
				if a > 0.01:
					draw_rect(Rect2(_fly_pos(i).round(), Vector2.ONE), Color(FLY, a))
		for x in _extra:
			var a := _extra_alpha() * (0.4 + 0.6 * (0.5 + 0.5 * sin(_t * 3.1 + float(x[1]))))
			if a > 0.01:
				draw_rect(Rect2(_wander(x).round(), Vector2.ONE), Color(FLY, a))

	func _glow_fireflies() -> void:
		for i in _blk.size():
			if _landed(i):
				_glow.draw_rect(Rect2(_blk[i] - Vector2(1, 1), Vector2(4, 4)), Color(FLY_GLOW, 0.10))
			else:
				var a := _fly_alpha(i)
				if a > 0.01:
					_glow.draw_rect(Rect2(_fly_pos(i).round() - Vector2(1, 1), Vector2(3, 3)), Color(FLY_GLOW, 0.25 * a))
		for x in _extra:
			var a := _extra_alpha() * (0.5 + 0.5 * sin(_t * 3.1 + float(x[1])))
			if a > 0.01:
				_glow.draw_rect(Rect2(_wander(x).round() - Vector2(1, 1), Vector2(3, 3)), Color(FLY_GLOW, 0.22 * a))

	# ---- 本2兔：雾里用光写
	const MIST := Color("#a9cabd")
	const INK_GLOW := Color(0.3, 0.78, 0.82)
	const WRITE_FROM := 0.7
	const WRITE_SEC := 1.4

	func _pen_x() -> float:
		return _box.position.x - 3.0 + (_box.size.x + 6.0) * _e((_t - WRITE_FROM) / WRITE_SEC)

	func _mist_a() -> float:
		var a := _e(_t / 0.9)
		if _leave_t >= 0.0:
			a *= 1.0 - _e(_leave_t / (_leave_len + 0.4))
		return a

	func _draw_mist() -> void:
		var ma := _mist_a()
		# 雾：几团扁椭圆叠在一起，每团很淡，左右慢慢漂（叠起来中间厚、边上薄，一档一档的）
		var c := _box.get_center()
		for j in 6:
			var fx := float(j) / 5.0 - 0.5
			var cx := c.x + fx * (_box.size.x + 40.0) + 7.0 * sin(_t * 0.35 + j * 1.3)
			var rx := 26.0 + 10.0 * absf(sin(j * 2.1))
			var ry := 9.0 + 3.0 * absf(cos(j * 1.7))
			_ellipse(Vector2(cx, c.y + 2.0 + 2.0 * sin(j * 1.9)).round(), rx, ry, Color(MIST, 0.07 * ma))
		var px := _pen_x()
		var final := col.lerp(Color.WHITE, 0.3)
		for i in _blk.size():
			if _blk[i].x >= px:
				continue
			var fresh := clampf(1.0 - (px - _blk[i].x) / 18.0, 0.0, 1.0)             # 刚写出来的亮，往后慢慢回到名字的颜色
			var a := 1.0 - _e(_leave_k(i, 0.55))
			if a > 0.01:
				draw_rect(Rect2(_blk[i] + Vector2(1, 1), Vector2(2, 2)), Color(SHADOW, 0.55 * a))
				draw_rect(Rect2(_blk[i], Vector2(2, 2)), Color(final.lerp(Color("#f2ffff"), fresh), a))
		if _writing():
			draw_rect(Rect2(Vector2(px, _tip_y(px)).round() - Vector2(1, 1), Vector2(2, 2)), Color.WHITE)    # 笔尖

	func _writing() -> bool:
		return _t > WRITE_FROM and _pen_x() < _box.end.x + 2.0 and _leave_t < 0.0

	func _tip_y(px: float) -> float:
		var f := px - _box.position.x
		var c := clampi(int(f), 0, _col_y.size() - 1)
		var c2 := clampi(c + 1, 0, _col_y.size() - 1)
		return lerpf(_col_y[c], _col_y[c2], clampf(f - float(c), 0.0, 1.0)) + 2.0 * sin(_t * 9.0)

	func _glow_mist() -> void:
		var px := _pen_x()
		for i in _blk.size():
			if _blk[i].x < px:
				var a := 1.0 - _e(_leave_k(i, 0.55))
				_glow.draw_rect(Rect2(_blk[i] - Vector2(1, 1), Vector2(4, 4)), Color(INK_GLOW, 0.09 * a))
		if _writing():
			var tip := Vector2(px, _tip_y(px)).round()
			_glow.draw_rect(Rect2(tip - Vector2(3, 3), Vector2(6, 6)), Color(INK_GLOW, 0.25))
			_glow.draw_rect(Rect2(tip - Vector2(6, 5), Vector2(12, 10)), Color(INK_GLOW, 0.08))

	func _ellipse(c: Vector2, rx: float, ry: float, color: Color) -> void:
		var pts := PackedVector2Array()
		for k in 20:
			var a := TAU * k / 20.0
			pts.append(c + Vector2(cos(a) * rx, sin(a) * ry).round())
		draw_colored_polygon(pts, color)

	# ---- 梧桐：落叶
	const LEAF := [Color("#e08638"), Color("#f2a65a"), Color("#b8612c")]

	func _leaf_pos(i: int) -> Vector2:
		var lk := _leave_k(i)
		if lk > 0.0:
			return _bez(_blk[i], _away_c[i], _away[i], _e(lk)) + Vector2(0.0, 4.0 * sin(lk * 9.0 + _ph[i]))
		var k := clampf((_t - _delay[i]) / _dur[i], 0.0, 1.0)
		var y := lerpf(_from[i].y, _blk[i].y, 1.0 - (1.0 - k) * (1.0 - k))       # 匀速落，最后轻轻停住
		var x := lerpf(_from[i].x, _blk[i].x, _e(k)) + 9.0 * (1.0 - k) * sin(k * 7.0 + _ph[i])   # 左右飘
		return Vector2(x, y)

	func _draw_leaves() -> void:
		for i in _blk.size():
			var k := (_t - _delay[i]) / _dur[i]
			if k < 0.0:
				continue
			var lk := _leave_k(i)
			var c: Color = LEAF[_shade[i]]
			if k >= 1.0 and lk <= 0.0:
				draw_rect(Rect2(_blk[i] + Vector2(2, 2), Vector2(2, 2)), SHADOW)
				draw_rect(Rect2(_blk[i], Vector2(2, 2)), c)
			else:
				var a := clampf(k / 0.25, 0.0, 1.0) * (1.0 - _e((lk - 0.6) / 0.4))
				if a > 0.01:
					var flat := sin(_t * 6.0 + _ph[i]) > 0.0                          # 翻着落：一会儿横一会儿竖
					draw_rect(Rect2(_leaf_pos(i).round(), Vector2(2, 1) if flat else Vector2(1, 2)), Color(c, a))
		# 名字成形后还有几片零星地飘下来，掠过名字
		var ea := _extra_alpha()
		for x in _extra:
			var per := 3.2 + float(x[2]) * 1.6
			var u := fmod(_t / per + float(x[2]), 1.0)
			var v: Vector2 = x[0]
			var p := Vector2(_box.get_center().x + _box.size.x * 0.6 * v.x + 10.0 * sin(u * 8.0 + float(x[1])),
				_box.position.y - 70.0 + u * 130.0)
			var a := ea * sin(u * PI)
			if a > 0.02:
				var flat := sin(_t * 5.0 + float(x[1])) > 0.0
				draw_rect(Rect2(p.round(), Vector2(2, 1) if flat else Vector2(1, 2)), Color(LEAF[int(float(x[2]) * 3.0) % 3], a))

	# ---- 奥斯卡：一束光里一个像素一个像素地画出来
	const GOLD := Color("#f0d98c")
	const POP := Color("#fff6cf")
	const SLANT := 46.0              # 光柱顶上往右偏多少（斜着落下来）

	func _shaft_a() -> float:
		var a := _e(_t / 0.9)
		if _leave_t >= 0.0:
			a *= 1.0 - _e(_leave_t / (_leave_len + 0.3))
		return a

	## 光柱里的一点：s = 0 左边 .. 1 右边，u = 0 顶 .. 1 底
	func _shaft_point(s: float, u: float) -> Vector2:
		var y := lerpf(_box.position.y - 150.0, _box.end.y + 16.0, u)
		var half := _box.size.x / 2.0 + 14.0 + 6.0 * (1.0 - u)
		var cx := _box.get_center().x + SLANT * (1.0 - u)
		return Vector2(cx - half + 2.0 * half * s, y)

	func _draw_light() -> void:
		for i in _blk.size():
			var k := (_t - _delay[i]) / 0.4
			if k < 0.0:
				continue
			var a := 1.0 - _e(_leave_k(i, 0.4))
			if a <= 0.01:
				continue
			draw_rect(Rect2(_blk[i] + Vector2(2, 2), Vector2(2, 2)), Color(SHADOW, SHADOW.a * a))
			draw_rect(Rect2(_blk[i], Vector2(2, 2)), Color(col.lerp(POP, 1.0 - clampf(k, 0.0, 1.0)), a))   # 刚画上去的那一下最亮
		# 光里的灰尘：慢慢往下飘，一闪一闪
		var sa := _shaft_a()
		for x in _extra:
			var u := fmod(_t * 0.12 + float(x[2]), 1.0)
			var v: Vector2 = x[0]
			var p := _shaft_point(0.5 + 0.45 * v.x, u) + Vector2(3.0 * sin(_t * 0.9 + float(x[1])), 0)
			var a := sa * sin(u * PI) * (0.5 + 0.5 * sin(_t * 2.0 + float(x[1])))
			if a > 0.02:
				draw_rect(Rect2(p.round(), Vector2.ONE), Color(POP, 0.75 * a))

	func _glow_light() -> void:
		var sa := _shaft_a()
		for j in 3:                                                                   # 三层一层比一层窄：一档一档的软边
			var s := 0.18 * j
			var poly := PackedVector2Array([_shaft_point(s, 0.0).round(), _shaft_point(1.0 - s, 0.0).round(),
				_shaft_point(1.0 - s, 1.0).round(), _shaft_point(s, 1.0).round()])
			_glow.draw_colored_polygon(poly, Color(GOLD, 0.06 * sa))
		for i in _blk.size():
			var k := (_t - _delay[i]) / 0.4
			if k >= 0.0:
				var a := 1.0 - _e(_leave_k(i, 0.4))
				_glow.draw_rect(Rect2(_blk[i] - Vector2(1, 1), Vector2(4, 4)), Color(GOLD, (0.08 + 0.25 * (1.0 - clampf(k, 0.0, 1.0))) * a))

	# ---- sky：天上一颗颗亮起来
	func _draw_sky() -> void:
		for i in _blk.size():
			var k := (_t - _delay[i]) / 0.3
			if k < 0.0:
				continue
			var a := 1.0 - _e(_leave_k(i, 0.4))
			if a <= 0.01:
				continue
			if k < 1.0:
				var sa := a * (1.0 - k * 0.5)                                         # 刚亮的那一下：一个小十字
				draw_rect(Rect2(_blk[i] + Vector2(-1, 0), Vector2(4, 2)), Color(1, 1, 1, sa))
				draw_rect(Rect2(_blk[i] + Vector2(0, -1), Vector2(2, 4)), Color(1, 1, 1, sa))
			else:
				var tw := 0.5 + 0.5 * sin(_t * 1.7 + _ph[i])
				draw_rect(Rect2(_blk[i], Vector2(2, 2)), Color(col.lerp(Color.WHITE, 0.25 * tw), a))
		var ea := _extra_alpha()
		for x in _extra:                                                              # 旁边几颗小星星
			var v: Vector2 = x[0]
			var p := _box.get_center() + Vector2(v.x * (_box.size.x / 2.0 + 60.0), v.y * 30.0 - 6.0)
			var a := ea * (0.25 + 0.35 * (0.5 + 0.5 * sin(_t * (1.1 + float(x[2])) + float(x[1]))))
			draw_rect(Rect2(p.round(), Vector2.ONE), Color(col, a))

	func _glow_sky() -> void:
		for i in _blk.size():
			var k := (_t - _delay[i]) / 0.3
			if k >= 0.0:
				var a := 1.0 - _e(_leave_k(i, 0.4))
				_glow.draw_rect(Rect2(_blk[i] - Vector2(1, 1), Vector2(4, 4)), Color(0.75, 0.75, 0.85, (0.06 + 0.2 * (1.0 - clampf(k, 0.0, 1.0))) * a))
