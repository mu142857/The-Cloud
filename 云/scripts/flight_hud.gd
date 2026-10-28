extends Node2D
## 飞行段的 HUD（屏幕坐标，画在最上层）：
##   上方：到水星的进度条（左端木星、右端水星，白点是飞船），同一条上从飞船往前画一段琥珀色 = 现在的燃料能飞到哪：
##         碰到水星 = 够了（水星周围亮一圈）；碰不到，剩下的是玫瑰色的点 = 还差。下面一行字只说结论（「够飞到水星」/「还差 75」），
##         后面暗暗地跟一个「有/要」。整条的长度 = 起飞时要的燃料，所以燃料和距离是同一把尺子。
##   右下：接下来要烧的两三件（小图标，最左边那件是下一件）。左下留给飞船贴底飞。
##   下方中间：晨的旁白（一行字幕）；物品自动烧掉时的小提示（+40 发光木头）往上飘。

const JUP := preload("res://art/flight/icon_jupiter.png")
const MER := preload("res://art/flight/icon_mercury.png")
const DROP := preload("res://art/flight/ui_drop.png")
const MER_GLOW := preload("res://art/flight/sel_glow.png")
const BAR_X0 := 130.0
const BAR_X1 := 350.0
const FLAME := preload("res://art/flight/ui_flame.png")

const QX := 364.0               # 「接下来」那排小图标的左边（右下角，最多 4 个）
const C_DIM := Color("3a4158")
const C_TXT := Color("aeb4c8")
const C_AMBER := Color("f0b860")
const C_AMBER_D := Color("7a5a36")
const C_SHORT := Color("b0586e")
const C_WHITE := Color("e8eef6")

var progress := 0.0
var need0 := 350.0
var need_left := 350.0
var tank := 0.0
var queued := 0.0
var leaking := false
var queue_icons: Array = []      # [{tex, personal, skipped}]
var round_over := false
var subtitle := ""
var subtitle_a := 0.0
var hint_a := 0.0
var toasts: Array = []           # {text, icon, age, p}
var gauge_pop := 0.0             # 使坏事件：燃料表抖一下
var alpha := 1.0
var short_shown := 0.0
var ceiling_y := 0.0           # 紧急模式压下来的天花板（屏幕 y），0 = 没有
var ceil_a := 0.0
var hold := {}                 # uid → true：「留下」的东西还在飞回来的路上，这一格先空着
var pulse := {}                # uid → 剩余秒数：刚落回来，亮一下、弹一下
var _t := 0.0


func toast(text: String, icon: Texture2D, p := Vector2(346, 224), col := C_AMBER) -> void:
	toasts.append({"text": text, "icon": icon, "age": 0.0, "p": p, "c": col})


func update(delta: float) -> void:
	_t += delta
	for q in toasts:
		q.age += delta
	toasts = toasts.filter(func(q): return q.age < 2.2)
	gauge_pop = maxf(0.0, gauge_pop - delta)
	for k in pulse.keys():
		pulse[k] -= delta
		if pulse[k] <= 0.0:
			pulse.erase(k)
	var short := maxf(0.0, need_left - tank - queued)
	short_shown = move_toward(short_shown, short, maxf(40.0, absf(short - short_shown) * 3.0) * delta)
	queue_redraw()


func _text(s: String, p: Vector2, col: Color, align := HORIZONTAL_ALIGNMENT_LEFT, width := -1.0) -> void:
	draw_string(FlightText.font(), p, s, align, width, FlightText.SIZE, col)


func _draw() -> void:
	var a := alpha
	if a <= 0.0:
		return
	# ---- 紧急模式「飞不高了」：飞船上方的天从上往下一点点暗下去（柔的渐变，特效可以半透明），
	# 暗的下沿就是现在飞得到的最高处；飞船往上够、够不着（飞船自己会抖，见 flight_ship.gd）。
	if ceil_a > 0.0 and ceiling_y > 2.0:
		var cy := roundf(ceiling_y)
		var soft := 56.0
		var yy := 0.0
		while yy < cy:
			var k := clampf((cy - yy) / soft, 0.0, 1.0)
			draw_rect(Rect2(0, yy, 480, 1), Color(0.01, 0.02, 0.06, 0.8 * ceil_a * k * k))
			yy += 1.0
	# ---- 进度条 + 燃料投影：从飞船（白点）往前画一段琥珀色 = 现在的燃料能飞到哪。
	# 碰到水星 = 够了（水星亮起来）；碰不到，剩下那段是玫瑰色的点 = 还差。不用看数字。
	# 亮琥珀 = 引擎里正在烧的，暗琥珀 = 排队等着自动烧的材料（私人物品不算在里面）。
	var shake := Vector2(roundf(sin(_t * 60.0) * 2.0 * gauge_pop), 0)
	var x0 := BAR_X0
	var x1 := BAR_X1
	var y := 12.0
	var bw := x1 - x0
	var pr := clampf(progress, 0, 1)
	var px := roundf(x0 + bw * pr)
	var t_end := roundf(x0 + bw * clampf(pr + tank / need0, 0, 1))
	var q_end := roundf(x0 + bw * clampf(pr + (tank + queued) / need0, 0, 1))
	var enough := short_shown < 1.0
	draw_rect(Rect2(Vector2(x0 - 16, y - 6) + shake, Vector2(bw + 32, 13)), Color(0.01, 0.02, 0.05, 0.45 * a))
	draw_texture(JUP, Vector2(x0 - 13, y - 4) + shake, Color(1, 1, 1, a))
	if enough:
		var pulse := 0.55 + 0.25 * sin(_t * 3.0)
		draw_texture(MER_GLOW, Vector2(x1 + 8.5, y + 0.5) - Vector2(32, 32) + shake, Color(1, 1, 1, pulse * a))
	draw_texture(MER, Vector2(x1 + 4, y - 4) + shake, Color(1, 1, 1, a))
	draw_rect(Rect2(Vector2(x0, y) + shake, Vector2(bw, 1)), Color(C_DIM, a))
	draw_rect(Rect2(Vector2(x0, y) + shake, Vector2(px - x0, 1)), Color(Color("7d8aa8"), a))
	var tank_col := C_AMBER
	if leaking and int(_t * 6.0) % 2 == 0:
		tank_col = Color("ffdca0")
	draw_rect(Rect2(Vector2(px, y - 1) + shake, Vector2(t_end - px, 3)), Color(tank_col, a))
	draw_rect(Rect2(Vector2(t_end, y - 1) + shake, Vector2(q_end - t_end, 3)), Color(C_AMBER_D, a))
	if not enough:
		var xx := q_end + 1.0
		while xx < x1:
			draw_rect(Rect2(Vector2(xx, y) + shake, Vector2(1, 1)), Color(C_SHORT, a))
			xx += 2.0
		draw_rect(Rect2(Vector2(q_end, y - 3) + shake, Vector2(1, 7)), Color(Color("ea8aa0"), a))
	draw_rect(Rect2(Vector2(px - 1, y - 2) + shake, Vector2(3, 5)), Color(C_WHITE, a))
	# 一行结论（字号只能 14）：够 / 还差多少，后面暗暗地跟「有 / 要」
	var status := FlightText.t("enough") if enough else FlightText.t("short") % int(roundf(short_shown))
	var scol := Color("a8e0c8") if enough else Color("ea8aa0")
	var nums := "%d/%d" % [int(roundf(tank + queued)), int(roundf(need_left))]
	var fnt := FlightText.font()
	var sw := fnt.get_string_size(status, HORIZONTAL_ALIGNMENT_LEFT, -1, FlightText.SIZE).x
	var nw := fnt.get_string_size(nums, HORIZONTAL_ALIGNMENT_LEFT, -1, FlightText.SIZE).x
	var tx := roundf(240.0 - (sw + 8 + nw) / 2.0)
	draw_rect(Rect2(Vector2(tx - 5, 19) + shake, Vector2(sw + nw + 18, 15)), Color(0.01, 0.02, 0.05, 0.45 * a))
	_text(status, Vector2(tx, 31) + shake, Color(scol, a))
	_text(nums, Vector2(tx + sw + 8, 31) + shake, Color(Color("7b84a0"), a))
	# ---- 接下来要烧的
	var qx := QX
	var qy := 240.0
	var label := FlightText.t("no_more") if round_over else FlightText.t("next")
	var lw := FlightText.font().get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, FlightText.SIZE).x
	var lx := roundf(470.0 - lw - (10.0 if not round_over else 0.0))
	_text(label, Vector2(lx, qy - 4), Color(Color("59617a") if not round_over else C_SHORT, a * 0.9))
	var i := 0
	for q in queue_icons:
		if i >= 4:
			break
		var p := Vector2(qx + i * 27, qy)
		var c := Color(1, 1, 1, a)
		if i > 0:
			c = Color(0.62, 0.62, 0.72, a)
		if q.skipped:
			c = Color(0.4, 0.4, 0.5, a * 0.8)
		if hold.has(q.uid):
			i += 1
			continue
		var pu: float = pulse.get(q.uid, 0.0) / 0.6
		if pu > 0.0:
			draw_texture(MER_GLOW, p + Vector2(12, 12) - Vector2(32, 32), Color(0.85, 0.75, 1.0, a * pu))
			p.y -= roundf(3.0 * pu * pu)
			c = c.lerp(Color(1, 1, 1, a), pu)
		draw_texture(q.tex, p, c)
		if q.personal:
			draw_rect(Rect2(p + Vector2(10, 25), Vector2(4, 1)), Color(Color("b9a8c8"), a * (1.0 if i == 0 else 0.5)))
		i += 1
	if not queue_icons.is_empty() and not round_over:
		draw_texture(FLAME, Vector2(lx + roundf(lw) + 3, qy - 14) + Vector2(0, roundf(sin(_t * 5.0))), Color(1, 1, 1, a * 0.9))
	# ---- 自动烧掉的小提示
	for q in toasts:
		var u: float = q.age / 2.2
		var al := a * clampf((1.0 - u) * 2.0, 0.0, 1.0)
		var pp: Vector2 = q.p + Vector2(0, -roundf(u * 16.0))
		if q.icon:
			draw_texture(q.icon, pp + Vector2(0, -18), Color(1, 1, 1, al))
		_text(q.text, pp + Vector2(26 if q.icon else 0, -4), Color(q.c, al))
	# ---- 旁白字幕
	if subtitle != "" and subtitle_a > 0.0:
		var f := FlightText.font()
		var w := f.get_string_size(subtitle, HORIZONTAL_ALIGNMENT_LEFT, -1, FlightText.SIZE).x
		# 放得下就居中在右下角那排图标左边的空地里，免得压住「接下来」的图标；太长才整屏居中
		var cx := 240.0 if w + 12.0 > QX - 8.0 else (QX - 8.0) / 2.0
		var r := Rect2(roundf(cx - w / 2 - 6), 247, roundf(w + 12), 18)
		draw_rect(r, Color(0.02, 0.03, 0.06, 0.6 * subtitle_a * a))
		_text(subtitle, Vector2(roundf(cx - w / 2), 260), Color(Color("e6dcc8"), subtitle_a * a))
	if hint_a > 0.0:
		_text(FlightText.t("hint"), Vector2(0, 232), Color(C_TXT, hint_a * a * 0.8), HORIZONTAL_ALIGNMENT_CENTER, 480)
