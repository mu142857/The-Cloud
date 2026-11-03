extends CanvasLayer
## 潜意识字（第一关新版，docs/剧情改动/第一关新版_实现规格.md「新增的系统和接口」）：天空里的字，和对话框分开。
## 没有框、没有名字，淡淡的、发白的字，带一圈很淡的青绿光晕（亮天空上也看得清）；一层 CanvasLayer（LAYER = 52：
## 盖在黑幕 Top 50 上面，所以黑屏时「我是……晨」照样看得见；在闪回 55 下面）。
##
## 怎么调（story_runner.gd 里，不用 class_name，preload 进来用静态函数）：
##   const InnerVoice := preload("res://scripts/inner_voice.gd")
##   var t: float = InnerVoice.say("我是……谁？", "", "drift")        # 返回秒数：返回到完全消失的总秒数
##   InnerVoice.say("好熟悉的感觉……", "", "fade", 3.0)                 # sec = 停留秒数（0 = 按字数算）
##   InnerVoice.say("快去找到背包……", "", "spin")                      # sec = 显示总时长（0 = 按字数算）
##   InnerVoice.clear()                                                 # 现在挂着的都淡掉
##   剧本：{"do": "inner", "zh": "...", "en": "", "style": "drift", "sec": 0, "wait": false}
##     wait 交给 runner：要等就 await get_tree().create_timer(t).timeout；ff 时别调（或调 clear(0.0)）。
##   第一次调用时自己建在 current_scene（关卡）下面；换场景跟着关卡一起释放，下次再建。想挂在指定节点下：InnerVoice.attach(level)。
##
## 三种样子：
##   drift：逐字排成波浪，从屏幕左外较快飘到右外，只播放一次；sec > 0 可指定飘过时长。
##   fade ：淡入、停一会儿（一边往上浮 4 像素）、淡出。
##   spin ：固定在屏幕上方居中，逐字持续轻颤，淡入、停留、淡出一次，不平移。
## 新的一句出来时，上一句（不管哪种）先淡掉。中文先写，en 空着就用中文。

const LAYER := 52
const SIZE := 14                          # 天王星像素 14 号字 = 一格一个屏幕像素（UITheme 的说明）
const COL := Color("#eef3ee")             # 发白、偏一点点暖：和对话框的 UITheme.TEXT（青绿灰、带深底）分开
const GLOW := Color(0.62, 0.82, 0.78, 0.22)   # 很淡的青绿光晕（字的 outline），亮天空上压一圈
const ALPHA := 0.9                        # 字最实的时候也不全实，像隔着一层
const SKY_Y := 52.0                       # 天空区：字的中线大概在这一行
const WAVE_HEIGHT := 6.0                  # 每个字沿波浪上下起伏的幅度
const WAVE_LENGTH := 110.0                # 波长（屏幕像素）
const DRIFT_SPEED := 84.0                 # 平均前进速度，像素 / 秒（运动有缓入缓出）
const CHAR_GAP := 4.0                     # 字间留白更明显
const SPACE_WIDTH := 12.0                 # 英文空格和全角空格至少留出的宽度
const WRAP := 300.0
const FADE_IN := 1.2
const FADE_OUT := 0.9

static var _inst                          # 现在这一个（untyped：静态函数里要调它自己的方法）

var _items: Array = []                    # 现在屏幕上的 {node, style, t, ...}
var _time := 0.0


# ======================================================================= 静态入口
static func attach(parent: Node) -> Node:
	if is_instance_valid(_inst) and _inst.get_parent() == parent:
		return _inst
	if is_instance_valid(_inst):
		_inst.queue_free()
	_inst = (load("res://scripts/inner_voice.gd") as GDScript).new()
	_inst.name = "InnerVoice"
	parent.add_child(_inst)
	return _inst


static func node() -> Node:
	if not is_instance_valid(_inst) or not _inst.is_inside_tree():
		var tree := Engine.get_main_loop() as SceneTree
		var parent: Node = tree.current_scene if tree.current_scene != null else tree.root
		_inst = null
		attach(parent)
	return _inst


static func say(zh: String, en := "", style := "drift", sec := 0.0) -> float:
	var n = node()
	return n.show_line(zh, en, style, sec)


static func clear(sec := FADE_OUT) -> void:
	if is_instance_valid(_inst):
		_inst.fade_all(sec)


## 这一句按字数大概停多久（fade 的停留 / spin 的飘过）
static func auto_sec(text: String, style: String) -> float:
	if style == "spin":
		return clampf(4.0 + 0.25 * text.length(), 5.0, 9.0)
	return clampf(1.6 + 0.14 * text.length(), 2.2, 5.0)


# ======================================================================= 节点
func _ready() -> void:
	layer = LAYER
	follow_viewport_enabled = false            # 屏幕坐标，镜头平移和缩放不带着字走
	process_mode = Node.PROCESS_MODE_ALWAYS


func show_line(zh: String, en: String, style: String, sec: float) -> float:
	fade_all(FADE_OUT * 0.7)
	var text := en if (I18n.lang != "zh" and en != "") else zh
	if text == "":
		return 0.0
	if not style in ["drift", "fade", "spin"]:
		push_warning("InnerVoice: 没有 style %s，当 drift" % style)
		style = "drift"
	var it := {"style": style, "t": 0.0, "out": -1.0, "out_len": FADE_OUT, "dead": false}
	if style in ["drift", "spin"]:
		it["chars"] = _ribbon(text)
		var width := 0.0
		for c in it["chars"]:
			width += float(c["w"])
		it["width"] = width
		it["dur"] = sec if sec > 0.0 else (FADE_IN + auto_sec(text, "fade") + FADE_OUT if style == "spin" else (528.0 + width) / DRIFT_SPEED)
		_items.append(it)
		_place(it)
		return float(it["dur"])
	var l := _label(text)
	l.custom_minimum_size = Vector2(WRAP, 0)
	add_child(l)
	l.reset_size()
	var h := l.get_combined_minimum_size().y
	it["node"] = l
	it["base"] = Vector2(round(240.0 - WRAP / 2.0), round(SKY_Y - h / 2.0))
	if style == "fade":
		var hold := sec if sec > 0.0 else auto_sec(text, "fade")
		it["out"] = FADE_IN + hold
		_items.append(it)
		_place(it)
		return FADE_IN + hold + FADE_OUT
	if sec > 0.0:
		it["out"] = FADE_IN + sec
	_items.append(it)
	_place(it)
	return FADE_IN


## 现在挂着的都淡掉（sec = 0 立刻没）
func fade_all(sec: float) -> void:
	for it in _items:
		if it["dead"]:
			continue
		if sec <= 0.0:
			_kill(it)
			continue
		var started: float = it["out"]
		if started < 0.0 or started > it["t"]:
			it["out"] = it["t"]
			it["out_len"] = sec
			it["from_a"] = _alpha(it)          # 淡入到一半被顶掉：从现在的透明度往下淡，不跳
	_items = _items.filter(func(x): return not x["dead"])


func _label(text: String) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", UITheme.font())
	l.add_theme_font_size_override("font_size", SIZE)
	l.add_theme_color_override("font_color", COL)
	l.add_theme_color_override("font_outline_color", GLOW)
	l.add_theme_constant_override("outline_size", 4)
	l.add_theme_constant_override("line_spacing", 3)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	l.modulate.a = 0.0
	return l


## 波浪文字：一个字一个 Label，按实际字宽排成带子，保持阅读顺序
func _ribbon(text: String) -> Array:
	var out: Array = []
	var gap := 0.0
	for ch in text:
		var l := _label(ch)
		l.autowrap_mode = TextServer.AUTOWRAP_OFF
		add_child(l)
		l.reset_size()
		var glyph_width := l.get_combined_minimum_size().x
		if ch.strip_edges().is_empty() or ch == "　":
			glyph_width = maxf(glyph_width, SPACE_WIDTH)
		var w := glyph_width + CHAR_GAP
		out.append({"node": l, "lag": gap, "w": w})
		gap += w
	# 带子从左往右飘，走在最前面的（lag 最小）必须是最后一个字，不然读出来是反的
	for c in out:
		c["lag"] = gap - float(c["lag"]) - float(c["w"])
	return out


func _process(dt: float) -> void:
	if _items.is_empty():
		return
	_time += dt
	for it in _items:
		it["t"] = float(it["t"]) + dt
		_place(it)
	_items = _items.filter(func(x): return not x["dead"])


## 透明度：淡入（sine 缓起缓停）→ 实 → 淡出
func _alpha(it: Dictionary) -> float:
	var t: float = it["t"]
	var a := ALPHA * _ease(clampf(t / FADE_IN, 0.0, 1.0))
	if it["style"] in ["drift", "spin"]:
		var dur: float = it["dur"]
		a = ALPHA * _ease(clampf(t / FADE_IN, 0.0, 1.0)) * _ease(clampf((dur - t) / FADE_OUT, 0.0, 1.0))
	var o: float = it["out"]
	if o >= 0.0 and t >= o:
		var from_a: float = it.get("from_a", ALPHA)
		a = minf(a, from_a * (1.0 - _ease(clampf((t - o) / float(it["out_len"]), 0.0, 1.0))))
	return a


func _place(it: Dictionary) -> void:
	var t: float = it["t"]
	var a := _alpha(it)
	var o: float = it["out"]
	var gone := o >= 0.0 and t >= o + float(it["out_len"])
	match str(it["style"]):
		"fade":
			var up := 4.0 * _ease(clampf(t / (float(it["out"]) + FADE_OUT), 0.0, 1.0))
			_put(it["node"], it["base"] - Vector2(0, up), a)
		"drift", "spin":
			var dur: float = it["dur"]
			gone = gone or t >= dur
			for c in it["chars"]:
				var u := t / dur
				var p := _shiver(float(c["lag"]), float(c["w"]), float(it["width"]), t) if it["style"] == "spin" else _wave(u, float(c["lag"]), float(it["width"]), t)
				_put(c["node"], p, a)
	if gone:
		_kill(it)


## 整句从左侧完全离屏处移到右侧完全离屏处；水平不回摆，每个字按所在位置形成波浪。
func _wave(u: float, lag: float, width: float, t: float) -> Vector2:
	var x := -24.0 + _ease(clampf(u, 0.0, 1.0)) * (528.0 + width) - lag
	var y := SKY_Y + WAVE_HEIGHT * sin(x * TAU / WAVE_LENGTH - t * 1.4)
	return Vector2(x, y)


## 全程轻颤：每秒 12 档、约 1～2 像素；各字相位错开，让字一直不安地抖，保持可读。
## 整句固定居中，只有微小颤抖；位置与播放进度、镜头移动无关。
func _shiver(lag: float, glyph_width: float, width: float, t: float) -> Vector2:
	var x := 240.0 + width / 2.0 - lag - glyph_width
	var tick := floorf(t * 12.0) / 12.0
	var phase := lag * 0.71
	var dx := 0.85 * sin(tick * 37.0 + phase) + 0.45 * sin(tick * 61.0 + phase * 1.3)
	var dy := 1.4 * sin(tick * 43.0 + phase * 1.7) + 0.6 * sin(tick * 71.0 + phase)
	return Vector2(x + dx, SKY_Y + dy)


func _put(n: Control, p: Vector2, a: float) -> void:
	if not is_instance_valid(n):
		return
	n.position = p.round()                       # 整像素：像素字不糊
	n.modulate.a = a


func _kill(it: Dictionary) -> void:
	it["dead"] = true
	if it.has("node") and is_instance_valid(it["node"]):
		it["node"].queue_free()
	for c in it.get("chars", []):
		if is_instance_valid(c["node"]):
			c["node"].queue_free()


static func _ease(k: float) -> float:
	return 0.5 - 0.5 * cos(k * PI)
