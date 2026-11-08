extends Control
## 屏幕上方正中的燃料条（11-08 作者：弥洛说「大概需要 500 动力的燃料才能飞到下一个目的地」时第一次出现，
##   「这个有现成的动画……之后这个就会永久的放在屏幕上方了，一个进度条」）。
##   画法照搬飞行段的进度条（scripts/flight_hud.gd：1 像素暗轨道、3 像素琥珀色填充、没满的那段玫瑰色虚点 + 一根竖刻度，
##   满了整条亮一下），左边一颗小火苗，右边「有 / 要」两个数。
##
## level_forest.gd 建它、每帧 set_fuel(有, 要) 和 alpha；剧本设 flag c1_fuel_bar 以后才显示。
## reveal()：第一次出现——淡入，同时数字和填充从 0 滚到现在的值（滚的时候轻轻 tick）。读档 / 换章进来直接显示，不滚。
## 数变了（捡到能烧的、烧掉东西、飞行段燃料涨跌）：填充和数字滚过去，涨的时候亮一下。
## 11-08 作者「只有收到新的东西的时候才显示细节，不然只显示进度条本身，不显示数字和透明黑色背景」：
##   平时只画火苗 + 进度条；第一次出现 / 数变了 → 数字和半透明黑底淡入，滚完再停 DETAIL_HOLD 秒淡掉。
## 11-08 飞行一新版（作者：永燃之木无限能量 → 被陨石砸掉 → 燃料一直在烧，「燃料上有一个绿色安全竖线，如果低于了这个线，
##   就说明需要重新添加一次燃料了」）：
##   safe > 0：条上画一根绿色竖线（StoryState 的 fuel_safe，剧本 fuel 步骤 "safe" 设）；燃料低于它，填充一闪一闪变玫瑰色。
##   infinite：永燃之木还在船上（flag flight1_wood_power）——条满、慢慢流光，数字写「无限」。

const FLAME := preload("res://art/level1/icon_flame.png")
const C_BG := Color(0.01, 0.03, 0.03, 0.45)
const C_DIM := Color("3a4a46")
const C_AMBER := Color("f0b860")
const C_SHORT := Color("b0586e")
const C_TICK := Color("ea8aa0")
const C_FULL := Color("a8e0c8")
const C_TXT := Color("#e8b860")        # = UITheme.WARM
const BAR_W := 84.0
const FONT_SIZE := 14
const TOP := 7.0                       # 和左上角目标、右上角背包同一行
const DETAIL_HOLD := 2.5               # 数停下来以后数字 / 黑底还留多久
const C_SAFE := Color("6fd08c")        # 安全线
const C_LOW := Color("e0607a")         # 低于安全线时填充闪的颜色

var have := 0
var need := 500
var shown := 0.0                       # 正在显示的数（滚动用）
var top := TOP                         # 电影黑边放下来时 level 把它往下推
var alpha := 0.0
var _rev := -1.0                       # 第一次出现的淡入（0 → 1）；-1 = 不在淡入
var _glow := 0.0                       # 涨了 / 满了亮一下
var _t := 0.0
var _tick_last := 0
var sfx: Callable                      # level 的 _sfx（tick 声），可不传
var _detail := 0.0                     # 数字 + 黑底的透明度（0 = 只有进度条）
var _hold := 0.0                       # 还要显示细节多久
var _seeded := false                   # 第一次 set_fuel（读档 / 换章进来）不算「变了」
var safe := 0                          # 绿色安全线（0 = 不画）
var infinite := false                  # 永燃之木供能：满、流光、「∞」


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	size = Vector2(480, 30)


## 每帧：现在有多少、要多少
func set_fuel(h: int, n: int) -> void:
	if h > have and _rev < 0.0:
		_glow = 1.0
	if _seeded and h != have:
		_hold = DETAIL_HOLD
	elif not _seeded:
		shown = float(h)                   # 读档 / 换章进来：直接是现在的数，不从 0 滚（也就不亮出数字）
	_seeded = true
	have = h
	need = maxi(n, 1)


## 第一次出现：淡入 + 从 0 滚到现在
func reveal() -> void:
	_rev = 0.0
	shown = 0.0
	_glow = 1.0
	_hold = DETAIL_HOLD


## 不滚，直接显示（读档、换章）
func snap() -> void:
	shown = float(have)
	_rev = -1.0


func _process(delta: float) -> void:
	_t += delta
	if _rev >= 0.0:
		_rev = minf(1.0, _rev + delta / 0.6)
		if _rev >= 1.0 and is_equal_approx(shown, float(have)):
			_rev = -1.0
	var speed := maxf(60.0, absf(float(have) - shown) * 2.5)
	shown = move_toward(shown, float(have), speed * delta)
	var n := int(round(shown))
	if n != _tick_last and n % 10 == 0 and sfx.is_valid() and alpha > 0.5:
		sfx.call("tick", -18.0, 1.0)
	_tick_last = n
	_glow = maxf(0.0, _glow - delta * 1.5)
	if _rev >= 0.0 or not is_equal_approx(shown, float(have)):
		_hold = maxf(_hold, DETAIL_HOLD)      # 还在滚：一直显示，滚完再开始倒数
	_hold = maxf(0.0, _hold - delta)
	_detail = move_toward(_detail, 1.0 if _hold > 0.0 else 0.0, delta / (0.25 if _hold > 0.0 else 0.6))
	queue_redraw()


func _draw() -> void:
	var a := alpha * (_rev if _rev >= 0.0 else 1.0)
	if a <= 0.01:
		return
	var f := UITheme.font()
	var txt := "%d / %d" % [int(round(shown)), need]
	if infinite:
		txt = I18n.pick({"zh": "无限", "en": "MAX"})   # 像素字体里的「∞」画出来像「∝」
	var tw := f.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE).x
	var fw := float(FLAME.get_width())
	var total := fw + 4.0 + BAR_W + 5.0 + tw
	var x0 := floorf(240.0 - total / 2.0)
	var y := floorf(top)
	var enough := shown >= float(need) - 0.5 or infinite
	var low := safe > 0 and not infinite and shown < float(safe)
	var da := a * (1.0 if low or infinite else _detail)   # 低于安全线 / 无限：数字一直显示                # 细节（数字、黑底）的透明度
	# 底：半透明暗条（和飞行段一样，压在什么背景上都看得清）——只在显示细节时
	if da > 0.01:
		draw_rect(Rect2(x0 - 5.0, y - 1.0, total + 10.0, 14.0), Color(C_BG, C_BG.a * da))
	draw_texture(FLAME, Vector2(x0, y + 1.0), Color(1, 1, 1, a))
	var bx := x0 + fw + 4.0
	var by := y + 6.0
	var fill := BAR_W if infinite else roundf(BAR_W * clampf(shown / float(need), 0.0, 1.0))
	draw_rect(Rect2(bx, by, BAR_W, 1.0), Color(C_DIM, a))
	var col := C_AMBER.lerp(Color("ffe0a8"), _glow * 0.8)
	if low and int(_t * 4.0) % 2 == 0:
		col = C_LOW
	if fill > 0.0:
		draw_rect(Rect2(bx, by - 1.0, fill, 3.0), Color(col, a))
	if infinite:                                   # 流光：一小段亮色从左往右走
		var sx := bx + fposmod(_t * 40.0, BAR_W + 12.0) - 6.0
		for i in 6:
			var xx2 := sx + float(i)
			if xx2 >= bx and xx2 < bx + BAR_W:
				draw_rect(Rect2(xx2, by - 1.0, 1.0, 3.0), Color(Color("fff2d0"), a * (1.0 - absf(float(i) - 2.5) / 3.0)))
	if enough:
		var p := 0.55 + 0.25 * sin(_t * 3.0)
		draw_rect(Rect2(bx - 1.0, by - 2.0, BAR_W + 2.0, 5.0), Color(C_FULL, 0.18 * p * a))
	else:
		var xx := bx + fill + 1.0
		while xx < bx + BAR_W:
			draw_rect(Rect2(xx, by, 1.0, 1.0), Color(C_SHORT, a))
			xx += 2.0
		draw_rect(Rect2(bx + fill, by - 3.0, 1.0, 7.0), Color(C_TICK, a))
	if safe > 0 and not infinite:
		var sxl := bx + roundf(BAR_W * clampf(float(safe) / float(need), 0.0, 1.0))
		draw_rect(Rect2(sxl, by - 4.0, 1.0, 9.0), Color(C_SAFE, a))
	if da > 0.01:
		draw_string(f, Vector2(bx + BAR_W + 5.0, y + 11.0), txt, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE,
			Color(C_LOW if low else (C_FULL if enough else C_TXT), da))
