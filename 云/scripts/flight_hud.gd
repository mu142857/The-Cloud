extends Node2D
## 飞行段的 HUD（屏幕坐标，画在最上层）：
##   上方：到水星的进度条（左端木星、右端水星的小图标，一颗小亮点是飞船）
##   左上：燃料表。条的整宽 = 起飞时要的燃料。亮琥珀 = 引擎里正在烧的，暗琥珀 = 排队等着自动烧的材料，
##         白色小竖线 = 到终点还要多少；够不着那条线的那一段画成暗玫瑰色的虚线 = 还差多少（私人物品不算在里面）。
##   右下：接下来要烧的两三件（小图标，最左边那件是下一件）。左下留给飞船贴底飞。
##   下方中间：晨的旁白（一行字幕）；物品自动烧掉时的小提示（+40 发光木头）往上飘。

const JUP := preload("res://art/flight/icon_jupiter.png")
const MER := preload("res://art/flight/icon_mercury.png")
const DROP := preload("res://art/flight/ui_drop.png")
const FLAME := preload("res://art/flight/ui_flame.png")

const QX := 391.0               # 「接下来」那排小图标的左边（右下角）
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
var _t := 0.0


func toast(text: String, icon: Texture2D, p := Vector2(346, 224), col := C_AMBER) -> void:
	toasts.append({"text": text, "icon": icon, "age": 0.0, "p": p, "c": col})


func update(delta: float) -> void:
	_t += delta
	for q in toasts:
		q.age += delta
	toasts = toasts.filter(func(q): return q.age < 2.2)
	gauge_pop = maxf(0.0, gauge_pop - delta)
	var short := maxf(0.0, need_left - tank - queued)
	short_shown = move_toward(short_shown, short, maxf(40.0, absf(short - short_shown) * 3.0) * delta)
	queue_redraw()


func _text(s: String, p: Vector2, col: Color, align := HORIZONTAL_ALIGNMENT_LEFT, width := -1.0) -> void:
	draw_string(FlightText.font(), p, s, align, width, FlightText.SIZE, col)


func _draw() -> void:
	var a := alpha
	if a <= 0.0:
		return
	# ---- 紧急模式：天花板压下来（上面一片暗，边上一行稀疏的点）
	if ceil_a > 0.0 and ceiling_y > 2.0:
		var cy := roundf(ceiling_y)
		var dark := Color(0.01, 0.02, 0.06, 0.55 * ceil_a)
		var frost := Color(0.62, 0.72, 0.9, 0.4 * ceil_a)
		draw_rect(Rect2(0, 0, 480, cy - 4), dark)
		for row in 4:
			var yy := cy - 4 + row
			var step := 2 if row < 2 else 4
			var xx := float(row % 2) + float(int(_t * 8.0) % 2) * (2.0 if row >= 2 else 0.0)
			while xx < 480:
				draw_rect(Rect2(xx, yy, 1, 1), frost if row == 1 or row == 3 else dark)
				xx += step
	# ---- 进度条
	var x0 := 150.0
	var x1 := 330.0
	var y := 12.0
	draw_texture(JUP, Vector2(x0 - 13, y - 4), Color(1, 1, 1, a))
	draw_texture(MER, Vector2(x1 + 4, y - 4), Color(1, 1, 1, a))
	draw_rect(Rect2(x0, y, x1 - x0, 1), Color(C_DIM, a))
	var px := roundf(lerpf(x0, x1, clampf(progress, 0, 1)))
	draw_rect(Rect2(x0, y, px - x0, 1), Color(Color("7d8aa8"), a))
	draw_rect(Rect2(px - 1, y - 1, 3, 3), Color(C_WHITE, a))
	# ---- 燃料表
	var gx := 12.0
	var gy := 10.0
	var shake := Vector2(roundf(sin(_t * 60.0) * 2.0 * gauge_pop), 0)
	var gw := 96.0
	var k := gw / need0
	draw_texture(DROP, Vector2(gx, gy - 3) + shake, Color(1, 1, 1, a))
	var bx := gx + 9
	var by := gy
	draw_rect(Rect2(Vector2(bx, by) + shake, Vector2(gw, 3)), Color(Color("161b28"), a))
	var wt := minf(tank * k, gw)
	var wq := minf(queued * k, gw - wt)
	var tank_col := C_AMBER
	if leaking and int(_t * 6.0) % 2 == 0:
		tank_col = Color("ffdca0")
	draw_rect(Rect2(Vector2(bx, by) + shake, Vector2(roundf(wt), 3)), Color(tank_col, a))
	draw_rect(Rect2(Vector2(bx + roundf(wt), by) + shake, Vector2(roundf(wq), 3)), Color(C_AMBER_D, a))
	var have_x := bx + roundf(wt) + roundf(wq)
	var need_x := bx + roundf(minf(need_left * k, gw))
	if need_x > have_x:
		var xx := have_x
		while xx < need_x:
			draw_rect(Rect2(Vector2(xx, by + 1) + shake, Vector2(1, 1)), Color(C_SHORT, a))
			xx += 2
	draw_rect(Rect2(Vector2(need_x, by - 2) + shake, Vector2(1, 7)), Color(C_WHITE, a))
	var have := int(roundf(tank + queued))
	_text("%d / %d" % [have, int(roundf(need_left))], Vector2(bx, by + 16) + shake, Color(C_TXT, a))
	if short_shown >= 1.0:
		var sx := bx + 4 + FlightText.font().get_string_size("%d / %d" % [have, int(roundf(need_left))], 0, -1, FlightText.SIZE).x + 4
		_text(FlightText.t("short") % int(roundf(short_shown)), Vector2(sx, by + 16) + shake, Color(C_SHORT, a))
	# ---- 接下来要烧的
	var qx := QX
	var qy := 240.0
	var label := FlightText.t("no_more") if round_over else FlightText.t("next")
	var lw := FlightText.font().get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, FlightText.SIZE).x
	var lx := roundf(470.0 - lw - (10.0 if not round_over else 0.0))
	_text(label, Vector2(lx, qy - 4), Color(Color("59617a") if not round_over else C_SHORT, a * 0.9))
	var i := 0
	for q in queue_icons:
		if i >= 3:
			break
		var p := Vector2(qx + i * 27, qy)
		var c := Color(1, 1, 1, a)
		if i > 0:
			c = Color(0.62, 0.62, 0.72, a)
		if q.skipped:
			c = Color(0.4, 0.4, 0.5, a * 0.8)
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
		var r := Rect2(roundf(240 - w / 2 - 6), 247, roundf(w + 12), 18)
		draw_rect(r, Color(0.02, 0.03, 0.06, 0.6 * subtitle_a * a))
		_text(subtitle, Vector2(roundf(240 - w / 2), 260), Color(Color("e6dcc8"), subtitle_a * a))
	if hint_a > 0.0:
		_text(FlightText.t("hint"), Vector2(0, 232), Color(C_TXT, hint_a * a * 0.8), HORIZONTAL_ALIGNMENT_CENTER, 480)
