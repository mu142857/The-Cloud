extends CanvasLayer
## 潜意识字（第一关新版，docs/剧情改动/第一关新版_实现规格.md「新增的系统和接口」）：天空里的字，和对话框分开。
## 没有框、没有名字，淡淡的、发白的字，带一圈很淡的青绿光晕（亮天空上也看得清）；一层 CanvasLayer（LAYER = 52：
## 盖在黑幕 Top 50 上面，所以黑屏时「我是……晨」照样看得见；在闪回 55 下面）。
##
## 怎么调（story_runner.gd 里，不用 class_name，preload 进来用静态函数）：
##   const InnerVoice := preload("res://scripts/inner_voice.gd")
##   var t: float = InnerVoice.say("我是……谁？", "", "drift")        # 返回秒数：drift = 淡入要多久；fade / spin = 到完全消失要多久
##   InnerVoice.say("好熟悉的感觉……", "", "fade", 3.0)                 # sec = 停留秒数（0 = 按字数算）
##   InnerVoice.say("快去找到背包……", "", "spin")                      # sec = 飘过去用几秒（0 = 按字数算）
##   InnerVoice.clear()                                                 # 现在挂着的都淡掉
##   剧本：{"do": "inner", "zh": "...", "en": "", "style": "drift", "sec": 0, "wait": false}
##     wait 交给 runner：要等就 await get_tree().create_timer(t).timeout；ff 时别调（或调 clear(0.0)）。
##   第一次调用时自己建在 current_scene（关卡）下面；换场景跟着关卡一起释放，下次再建。想挂在指定节点下：InnerVoice.attach(level)。
##
## 三种样子：
##   drift：在天上慢慢飘（水平、竖直两条慢正弦，周期不同，像浮在水面上），一直挂着，直到下一句 / clear()；sec > 0 = 挂这么久自己淡掉。
##   fade ：淡入、停一会儿（一边往上浮 4 像素）、淡出。
##   spin ：一个字一个字排成一条带子，沿着「往前走 + 绕一圈」的曲线（摆线）从左往右飘过天空，两头淡入淡出。
## 新的一句出来时，上一句（不管哪种）先淡掉。中文先写，en 空着就用中文。

const LAYER := 52
const SIZE := 14                          # 天王星像素 14 号字 = 一格一个屏幕像素（UITheme 的说明）
const COL := Color("#eef3ee")             # 发白、偏一点点暖：和对话框的 UITheme.TEXT（青绿灰、带深底）分开
const GLOW := Color(0.62, 0.82, 0.78, 0.22)   # 很淡的青绿光晕（字的 outline），亮天空上压一圈
const ALPHA := 0.9                        # 字最实的时候也不全实，像隔着一层
const SKY_Y := 52.0                       # 天空区：字的中线大概在这一行
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
	if style == "spin":
		var dur := sec if sec > 0.0 else auto_sec(text, "spin")
		it["dur"] = dur
		it["chars"] = _ribbon(text)
		_items.append(it)
		return dur
	var l := _label(text)
	l.custom_minimum_size = Vector2(WRAP, 0)
	add_child(l)
	l.reset_size()
	var h := l.get_combined_minimum_size().y
	# drift 每句换一个落点（不总在正中）：按句子算，不随机，同一句每次都在同一处
	var off := 0.0
	if style == "drift":
		off = float(absi(text.hash()) % 61 - 30)
	it["node"] = l
	it["base"] = Vector2(round(240.0 - WRAP / 2.0 + off), round(SKY_Y - h / 2.0))
	it["phase"] = float(absi(text.hash()) % 100) / 100.0 * TAU
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


## spin：一个字一个 Label（宽字 14、半角 7），排成带子
func _ribbon(text: String) -> Array:
	var out: Array = []
	var gap := 0.0
	for ch in text:
		var l := _label(ch)
		l.autowrap_mode = TextServer.AUTOWRAP_OFF
		add_child(l)
		l.reset_size()
		out.append({"node": l, "lag": gap})
		gap += l.get_combined_minimum_size().x + 1.0
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
	if it["style"] == "spin":
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
		"drift":
			var ph: float = it["phase"]
			# 两条慢正弦，周期 11 秒 / 7 秒：一直在动，但慢得像浮着
			var p: Vector2 = it["base"] + Vector2(6.0 * sin(t * TAU / 11.0 + ph), 3.0 * sin(t * TAU / 7.0 + ph * 1.7))
			_put(it["node"], p, a)
		"fade":
			var up := 4.0 * _ease(clampf(t / (float(it["out"]) + FADE_OUT), 0.0, 1.0))
			_put(it["node"], it["base"] - Vector2(0, up), a)
		"spin":
			var dur: float = it["dur"]
			gone = gone or t >= dur
			for c in it["chars"]:
				var u := t / dur
				_put(c["node"], _loop(u, float(c["lag"])), a)
	if gone:
		_kill(it)


## spin 的曲线：从左往右走过天空，中途绕一圈（摆线：前进 + 一个圆；圆半径大于每圈前进的 1/2π，所以真的绕回来）。
## lag = 这个字在带子里落后头多少像素：按弧长往回退，带子不散。
func _loop(u: float, lag: float) -> Vector2:
	var travel := 480.0 + 160.0                  # 从屏幕左外 -80 走到右外 560
	var s := u * travel - lag
	var k := clampf(s / travel, 0.0, 1.0)
	var r := 22.0
	# 圈画在中间那一段：k 0.35..0.65 之间转一整圈，两头是平缓的下弧 / 上弧
	var w := clampf((k - 0.35) / 0.3, 0.0, 1.0)
	var ang := _ease(w) * TAU
	var x := -80.0 + k * travel - r * sin(ang)
	var y := SKY_Y + 10.0 * sin(k * PI) - r * (1.0 - cos(ang)) - 6.0
	return Vector2(x, y)


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
