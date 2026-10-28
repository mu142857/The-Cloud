extends Node2D
## 结算：一个安静的画面。到达 / 坠毁一句话，下面两栏：路上烧掉的、还在身边的（坠毁时是「摔下来时丢了的」）。
## 私人物品一件一行（图标 + 名字），普通材料只排一行小图标。慢慢淡入，按任意键再飞一次。

var crashed := false
var burned: Array = []        # 物品数据
var kept: Array = []          # 私人物品
var a := 0.0
var _t := 0.0


func show_result(is_crash: bool, burned_items: Array, kept_items: Array) -> void:
	crashed = is_crash
	burned = burned_items
	kept = kept_items
	visible = true
	a = 0.0
	_t = 0.0


func _process(delta: float) -> void:
	if not visible:
		return
	_t += delta
	a = clampf(_t / 2.0, 0.0, 1.0)
	queue_redraw()


func _txt(s: String, p: Vector2, col: Color, align := HORIZONTAL_ALIGNMENT_LEFT, width := -1.0) -> void:
	draw_string(FlightText.font(), p.round(), s, align, width, FlightText.SIZE, col)


func _draw() -> void:
	draw_rect(Rect2(0, 0, 480, 270), Color(0.02, 0.03, 0.06, 0.88 * a))
	var ta := clampf((_t - 0.6) / 1.5, 0.0, 1.0)
	var title := FlightText.t("crash_title" if crashed else "arrive_title")
	var sub := FlightText.t("crash_sub" if crashed else "arrive_sub")
	_txt(title, Vector2(0, 46), Color(Color("f1e6d0"), ta), HORIZONTAL_ALIGNMENT_CENTER, 480)
	_txt(sub, Vector2(60, 64), Color(Color("8d97b8"), ta), HORIZONTAL_ALIGNMENT_CENTER, 360)
	var la := clampf((_t - 1.6) / 1.5, 0.0, 1.0)
	var cols := [[FlightText.t("burned"), burned, 70.0], [FlightText.t("lost" if crashed else "kept"), kept, 262.0]]
	for col in cols:
		var x: float = col[2]
		_txt(col[0], Vector2(x, 96), Color(Color("aeb4c8"), la))
		draw_rect(Rect2(x, 100, 148, 1), Color(Color("2a3146"), la))
		var y := 106.0
		var mats: Array = []
		var list: Array = col[1]
		for it in list:
			if it.kind != "personal":
				mats.append(it)
				continue
			var faded: bool = crashed and col[1] == kept
			draw_texture(it.tex, Vector2(x, y), Color(1, 1, 1, la * (0.5 if faded else 1.0)))
			_txt(FlightText.pick(it.name), Vector2(x + 30, y + 16), Color(Color("e6dcc8"), la * (0.6 if faded else 1.0)))
			y += 27
		if not mats.is_empty():
			var mx := x
			for it in mats:
				draw_texture(it.tex, Vector2(mx, y + 2), Color(0.8, 0.8, 0.85, la * 0.75))
				mx += 14
			y += 30
		if list.is_empty():
			_txt(FlightText.t("none"), Vector2(x, y + 12), Color(Color("59617a"), la))
	var fa := clampf((_t - 3.5) / 1.0, 0.0, 1.0) * (0.6 + 0.4 * sin(_t * 2.0))
	_txt(FlightText.t("again"), Vector2(0, 256), Color(Color("59617a"), fa), HORIZONTAL_ALIGNMENT_CENTER, 480)
