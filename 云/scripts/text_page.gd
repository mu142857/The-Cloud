extends Control
## 背包详情的文字页：自己换行、自己画（像素字的删除线 / 下划线 RichTextLabel 画出来太细看不见，这里画 1 像素的硬线）。
##   set_parts([{text, color?, struck?, marked?, bullet?}…])   每一段一条（日记一条 = 一段），段和段之间换行
##   line_count()  一共几行；skip = 从第几行开始画（按整行滚，顶上不会露半行字）；visible_lines() = 框里放得下几行
## 换行：中文按字、英文尽量在空格处断；每行最宽 size.x。删除线在字中间那一行，下划线在字下面一行（划掉的话两条都画）。

const FONT_SIZE := 14
const LINE_GAP := 2.0

var skip := 0:
	set(v):
		skip = clampi(v, 0, maxi(0, _lines.size() - visible_lines()))
		queue_redraw()

var _parts: Array = []
var _lines: Array = []        # [{text, color, struck, marked, indent}]
var _w := -1.0


func set_parts(parts: Array) -> void:
	_parts = parts
	_relayout()


func line_height() -> float:
	return UITheme.font().get_height(FONT_SIZE) + LINE_GAP


func visible_lines() -> int:
	return maxi(1, int((size.y + LINE_GAP) / line_height()))


func line_count() -> int:
	return _lines.size()


func max_skip() -> int:
	return maxi(0, _lines.size() - visible_lines())


func _relayout() -> void:
	_w = size.x
	_lines.clear()
	var f := UITheme.font()
	for p in _parts:
		var pd: Dictionary = p
		var bullet := str(pd.get("bullet", ""))
		var indent := 0.0
		if bullet != "":
			indent = f.get_string_size(bullet, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE).x
		for para in str(pd.get("text", "")).split("\n"):
			var rows := _wrap(para, size.x - indent)
			for i in rows.size():
				_lines.append({"text": rows[i], "color": pd.get("color", UITheme.TEXT), "struck": pd.get("struck", false),
					"marked": pd.get("marked", false), "indent": indent, "bullet": bullet if i == 0 else ""})
	skip = clampi(skip, 0, max_skip())
	queue_redraw()


## 按宽度换行：CJK 一个字一个字断；拉丁字母尽量在空格处断
func _wrap(t: String, width: float) -> Array:
	var f := UITheme.font()
	var out: Array = []
	var cur := ""
	var i := 0
	while i < t.length():
		var ch := t[i]
		var trial := cur + ch
		if f.get_string_size(trial, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE).x <= width or cur == "":
			cur = trial
			i += 1
			continue
		# 放不下：拉丁字母的单词往回找空格
		var cut := cur.length()
		if ch.unicode_at(0) < 0x2E80 and ch != " ":
			var sp := cur.rfind(" ")
			if sp > 0:
				cut = sp + 1
		# 标点别放在行首：带一个字下去
		if ch in ["，", "。", "、", "；", "：", "？", "！", "」", "』", "）", "…"] and cut > 1:
			cut -= 1
		out.append(cur.substr(0, cut).strip_edges(false, true))
		cur = cur.substr(cut).strip_edges(true, false)
	if cur != "" or out.is_empty():
		out.append(cur)
	return out


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED and not is_equal_approx(_w, size.x):
		_relayout()


func _draw() -> void:
	var f := UITheme.font()
	var lh := line_height()
	var asc := f.get_ascent(FONT_SIZE)
	var n := visible_lines()
	for k in n:
		var li := skip + k
		if li >= _lines.size():
			break
		var l: Dictionary = _lines[li]
		var y := k * lh
		var c: Color = l["color"]
		var x: float = l["indent"]
		if str(l["bullet"]) != "":
			draw_string(f, Vector2(0, y + asc), str(l["bullet"]), HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, c)
		draw_string(f, Vector2(x, y + asc), str(l["text"]), HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, c)
		var tw := f.get_string_size(str(l["text"]), HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE).x
		if l["marked"]:
			draw_rect(Rect2(x, roundf(y + asc + 2.0), tw, 1), c)            # 下划线
		if l["struck"]:
			draw_rect(Rect2(x - 1.0, roundf(y + asc * 0.55), tw + 2.0, 1), c)   # 删除线：字中间一条 1 像素的线
