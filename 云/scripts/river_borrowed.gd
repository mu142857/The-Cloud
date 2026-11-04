extends "res://scripts/river_kit.gd"
## 河流篇小游戏 river_borrowed：水下仓库找读取头（11-04 重做，替掉 river_warehouse 的浮箱拴柜子）。
##   docs/剧情改动/第二章可玩性_设计.md 第 4 步（下半）。水下两人不说话：没有 say，只有箱子上的字、翻出来的东西和声音。
##
## 画面：水下，一排旧箱子慢慢漂（各漂各的，会互相超过去）。每只箱子贴着妮芙的标签。左上角是妮芙（鲸鱼壳）
##   和她头上三个泡泡 =「她还记得」。
## 怎么玩：←/→ 换一只箱子（或者鼠标指着），空格 / E / 点一下 = 打开。要找两样：读取头（主目标）、浮筒密封圈（修船零件）。
##   泡泡每隔 POP 秒破一个。泡泡还在的时候，标签是正常的字（「影像播放器　旧型号」）；
##   三个都破了 = 她忘了：标签全变回她自己的暗号（「圆圆的」「不要煮」……），她低头翻本子，READ 秒以后泡泡回来、字也回来。
##   开错一只：里面是 junk 里的一样东西（一只袜子、阿汀的午饭……），字在面板里亮一下，箱子关上漂走。
## 放水：开错 FAILS_GIVE 次以后，妮芙用手指着对的那只（箱子边上一圈亮），而且不再忘。第 ENTER_GIVE 次进也一样。
## 不会输：没有气量表，泡泡只管字。
##
## 剧本步骤：{"do": "mechanic", "id": "river_borrowed",
##   "boxes": [{"id", "label": {zh,en}, "code": {zh,en}（忘了以后的暗号）, "find"?: "head" / "seal"}…],
##   "junk": [{zh, en}…], "on_head": [步骤], "on_seal": [步骤]（给东西：做完、面板收起以后再播）,
##   "lines": {intro（面板出来以后，一般是 narr）, give, done}}
## 进度：{enter, fails, done, got: [head / seal]}。

const POP := 4.2                          # 多久破一个泡泡
const READ := 2.4                         # 忘了以后翻本子多久
const BOX := Vector2(34, 24)
const ROW_Y := [58.0, 106.0]               # 两排（标签在箱子下面，最下面一行留给翻出来的东西那句字）
const HINT := {"zh": "←→ 选箱子，空格打开。趁她还记得", "en": "← → to pick a crate, Space to open. While she still remembers."}
const DEFAULT_JUNK := [{"zh": "一只袜子。标签：借来的。", "en": "One sock. Label: borrowed."},
	{"zh": "一只小一点的箱子。里面还有一只更小的。", "en": "A smaller crate. With an even smaller one inside."},
	{"zh": "阿汀的午饭。泡发了。", "en": "Ting's lunch. Very soaked."}]

var boxes: Array = []                     # [{d, x, row, sp, ph, open_t}]
var sel := 0
var mem := 3
var _pop_t := 0.0
var _read_t := 0.0
var got: Array = []
var _caption_t := 0.0
var _caption_s := ""
var _junk_i := 0
var _helped := false
var _rise: Array = []                     # 拿到的东西往上飘：{tex, t, p}
var _motes: Array = []
var _mouse_moved := false


func _init() -> void:
	ID = "river_borrowed"
	panel = Vector2(248, 150)


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	level = lv
	step = st
	var give := _enter({"got": []})
	got = (s.get("got", []) as Array).duplicate()
	_helped = give
	_make_boxes()
	for i in 14:
		_motes.append(Vector2(randf_range(6, panel.x - 6), randf_range(10, panel.y - 10)))
	_build("RiverBorrowed", [])
	await _fade_in()
	await _lines("intro")
	_set_hint(step.get("hint", HINT))
	_shot("borrowed", 0.25)
	if auto_mode:
		await _auto_open()
	else:
		_accept = true
		while _alive() and not _all_found():
			await _frame()
	_accept = false
	if not _alive():
		_drop()
		return
	await _wait(0.8)
	_done()
	_set_hint({})
	await _lines("done")
	await _fade_out()
	if "head" in got:
		await _run(step.get("on_head", []))
	if "seal" in got:
		await _run(step.get("on_seal", []))


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


func ff(r: Node, st: Dictionary) -> void:
	_ff_save(r, st, {"got": ["head", "seal"]})
	for k in ["on_head", "on_seal"]:
		for x in st.get(k, []):
			if x is Dictionary and str(x.get("do", "")) == "give":
				Inventory.add(str(x.get("item", "")))
			elif x is Dictionary and str(x.get("do", "")) == "flag":
				StoryState.set_flag(str(x.get("set", "")))


func check(r: Node, st: Dictionary) -> Array:
	var out := _check_lines(r, st, ["intro", "give", "done"])
	var finds := {}
	for bx in st.get("boxes", []):
		if not bx is Dictionary or not bx.has("label") or not bx.has("code"):
			out.append("boxes：每只箱子要有 label / code：%s" % str(bx))
		elif bx.has("find"):
			finds[str(bx["find"])] = true
	for k in ["head", "seal"]:
		if not finds.has(k):
			out.append("boxes 里没有 find: %s 的箱子" % k)
	for k in ["on_head", "on_seal"]:
		out.append_array(KIT.check_steps(r, k, st.get(k, [])))
	return out


func _all_found() -> bool:
	return "head" in got and "seal" in got


# ----------------------------------------------------------------------- 箱子
func _make_boxes() -> void:
	var src: Array = step.get("boxes", [])
	for i in src.size():
		boxes.append({"d": src[i], "x": 26.0 + i * 46.0, "row": i % 2, "sp": randf_range(5.0, 11.0) * (1 if i % 2 == 0 else -1),
			"ph": randf() * TAU, "open_t": -1.0})


func _box_pos(bx: Dictionary) -> Vector2:
	var y: float = ROW_Y[int(bx["row"])] + sin(_t * 1.3 + float(bx["ph"])) * 3.0
	return Vector2(float(bx["x"]), y)


## ←→ 顺着屏幕上的左右换（箱子漂着，换的是「现在在它右边那一只」）
func _order() -> Array:
	var idx: Array = []
	for i in boxes.size():
		if not _done_box(i):
			idx.append(i)
	idx.sort_custom(func(a, b2): return float(boxes[a]["x"]) < float(boxes[b2]["x"]))
	return idx


func _done_box(i: int) -> bool:
	var f := str(boxes[i]["d"].get("find", ""))
	return f != "" and f in got


func _step_sel(d: int) -> void:
	var o := _order()
	if o.is_empty():
		return
	var at := o.find(sel)
	if at < 0:
		at = 0
	sel = o[(at + d + o.size()) % o.size()]
	_sfx("click", -16.0, 1.3)


func _open(i: int) -> void:
	var bx: Dictionary = boxes[i]
	if float(bx["open_t"]) >= 0.0 or _done_box(i):
		return
	bx["open_t"] = 0.0
	_sfx("box_open", -6.0)
	var f := str(bx["d"].get("find", ""))
	if f != "" and not f in got:
		got.append(f)
		s["got"] = got
		_save()
		var item := "reading_head" if f == "head" else "float_seal"
		_rise.append({"tex": Inventory.icon(item), "t": 0.0, "p": _box_pos(bx)})
		_show_caption(_tr(bx["d"].get("label", {})))
		_sfx("bell_soft", -10.0)
		var o := _order()
		if not o.is_empty():
			sel = o[0]
	else:
		var junk: Array = step.get("junk", DEFAULT_JUNK)
		_show_caption(_tr(junk[_junk_i % junk.size()]))
		_junk_i += 1
		if _fail():
			_helped = true
			mem = 3


func _show_caption(t: String) -> void:
	_caption_s = t
	_caption_t = 2.2


## 自动玩：先开对的那两只
func _auto_open() -> void:
	for want in ["head", "seal"]:
		for i in boxes.size():
			if str(boxes[i]["d"].get("find", "")) == want and not want in got:
				sel = i
				await _wait(0.5)
				_open(i)
				await _wait(0.7)


# ----------------------------------------------------------------------- 每帧 / 输入
func _tick(dt: float) -> void:
	for bx in boxes:
		bx["x"] = float(bx["x"]) + float(bx["sp"]) * dt
		if float(bx["x"]) < 18.0 or float(bx["x"]) > panel.x - 18.0:
			bx["sp"] = -float(bx["sp"])
			bx["x"] = clampf(float(bx["x"]), 18.0, panel.x - 18.0)
		if float(bx["open_t"]) >= 0.0:
			bx["open_t"] = float(bx["open_t"]) + dt
			if float(bx["open_t"]) > 1.6:
				bx["open_t"] = -1.0
	# 记性：一个一个破，全破了去翻本子
	if not _helped and _accept:
		if mem > 0:
			_pop_t += dt
			if _pop_t >= POP:
				_pop_t = 0.0
				mem -= 1
				_sfx("bubble_pop", -10.0)
				if mem == 0:
					_read_t = 0.0
		else:
			_read_t += dt
			if _read_t >= READ:
				mem = 3
				_sfx("page_flip", -10.0)
	if _caption_t > 0.0:
		_caption_t -= dt
	for rr in _rise:
		rr["t"] = float(rr["t"]) + dt
	_rise = _rise.filter(func(rr): return float(rr["t"]) < 1.6)
	for i in _motes.size():
		_motes[i] = Vector2(_motes[i].x + sin(_t + i) * dt * 2.0, wrapf(_motes[i].y - dt * 4.0, 8.0, panel.y - 8.0))
	if _mouse_moved:
		_mouse_moved = false
		var m := _mouse()
		for i in boxes.size():
			if not _done_box(i) and Rect2(_box_pos(boxes[i]) - BOX / 2.0, BOX).has_point(m):
				sel = i


func _press(e: InputEvent) -> bool:
	if is_left(e):
		_step_sel(-1)
		return true
	if is_right(e):
		_step_sel(1)
		return true
	if e is InputEventMouseMotion:
		_mouse_moved = true
		return false
	if is_ok(e):
		if is_click(e):
			var m := _mouse()
			for i in boxes.size():
				if not _done_box(i) and Rect2(_box_pos(boxes[i]) - BOX / 2.0, BOX).has_point(m):
					sel = i
		if not _done_box(sel):
			_open(sel)
		return true
	return false


# ----------------------------------------------------------------------- 画
func _draw_board(b: Control) -> void:
	_panel_bg(b, RIVER_LIT.darkened(0.25), RIVER_DEEP.darkened(0.3))
	# 从上面斜下来的光
	for k in 3:
		var x0 := 60.0 + k * 70.0 + sin(_t * 0.4 + k) * 6.0
		var poly := PackedVector2Array([Vector2(x0, 4), Vector2(x0 + 14, 4), Vector2(x0 + 34, panel.y - 4), Vector2(x0 + 10, panel.y - 4)])
		b.draw_colored_polygon(poly, Color(0.6, 0.85, 0.85, 0.05))
	for m in _motes:
		b.draw_rect(Rect2(m.round(), Vector2(1, 1)), Color(0.75, 0.9, 0.85, 0.35))
	b.draw_rect(Rect2(4, panel.y - 18, panel.x - 8, 14), Color("#0a1a1c"))          # 沉在底下的泥
	for i in boxes.size():
		_draw_box(b, i)
	_draw_niff(b)
	for rr in _rise:
		var u := float(rr["t"]) / 1.6
		var p: Vector2 = (rr["p"] as Vector2) + Vector2(0, -30.0 * u)
		if rr["tex"] != null:
			b.draw_texture(rr["tex"], (p - Vector2(8, 8)).round(), Color(1, 1, 1, 1.0 - maxf(0.0, u - 0.6) / 0.4))
	_caption(b, panel.y - 6, _caption_s, UITheme.TEXT, clampf(_caption_t / 0.4, 0.0, 1.0))
	# 找到了几样
	var t := ("读取头 %s　密封圈 %s" % ["有" if "head" in got else "—", "有" if "seal" in got else "—"]) if I18n.is_zh() \
		else ("Head %s  Seal %s" % ["ok" if "head" in got else "-", "ok" if "seal" in got else "-"])
	_text(b, Vector2(0, 19), t, UITheme.TEXT_DIM, panel.x - 8.0, HORIZONTAL_ALIGNMENT_RIGHT)


func _draw_box(b: Control, i: int) -> void:
	var bx: Dictionary = boxes[i]
	var c := _box_pos(bx)
	var found := _done_box(i)
	var r := Rect2((c - BOX / 2.0).round(), BOX)
	var col := Color("#5c4630") if not found else Color("#3a3226")
	b.draw_rect(r.grow(1), FRAME_DARK)
	b.draw_rect(r, col)
	b.draw_rect(Rect2(r.position, Vector2(r.size.x, 2)), col.lightened(0.18))
	b.draw_rect(Rect2(r.position + Vector2(0, r.size.y / 2.0), Vector2(r.size.x, 1)), col.darkened(0.3))
	var ot := float(bx["open_t"])
	if ot >= 0.0:
		var lift := minf(1.0, ot * 4.0) * (1.0 - maxf(0.0, ot - 1.2) / 0.4)
		b.draw_rect(Rect2(r.position + Vector2(-1, -2 - 6.0 * lift), Vector2(r.size.x + 2, 3)), col.lightened(0.1))
	# 标签：记得 = 真名，忘了 = 暗号
	var lab := _tr(bx["d"].get("label", {})) if (mem > 0 or _helped) else _tr(bx["d"].get("code", {}))
	var f := UITheme.font()
	var tw := f.get_string_size(lab, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
	var tr := Rect2(roundf(c.x - tw / 2.0) - 2.0, r.position.y + r.size.y + 2.0, tw + 4.0, 13.0)
	b.draw_rect(tr, PAPER if (mem > 0 or _helped) else PAPER_DIM)
	b.draw_string(f, Vector2(tr.position.x + 2.0, tr.position.y + 11.0), lab, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, INK)
	if found:
		_disc(b, c, 3, LAMP)                                       # 拿走了：箱子上一个亮点
	# 选中：上下一圈亮；放水以后对的那只再亮一圈
	if i == sel and not found:
		var k := 0.6 + 0.4 * sin(_t * 6.0)
		_frame_px(b, r.grow(3), Color(LAMP.r, LAMP.g, LAMP.b, k))
	if _helped and not found and str(bx["d"].get("find", "")) != "":
		_frame_px(b, r.grow(5), Color(SOFT.r, SOFT.g, SOFT.b, 0.5 + 0.5 * sin(_t * 3.0)))


func _frame_px(b: Control, r: Rect2, col: Color) -> void:
	b.draw_rect(Rect2(r.position, Vector2(r.size.x, 1)), col)
	b.draw_rect(Rect2(r.position + Vector2(0, r.size.y - 1), Vector2(r.size.x, 1)), col)
	b.draw_rect(Rect2(r.position, Vector2(1, r.size.y)), col)
	b.draw_rect(Rect2(r.position + Vector2(r.size.x - 1, 0), Vector2(1, r.size.y)), col)


## 左上角的妮芙：鲸鱼壳 + 脸；头上三个泡泡；忘了的时候低头翻本子（头上一个「…」）
func _draw_niff(b: Control) -> void:
	var o := Vector2(20, 22 + sin(_t * 1.6) * 1.5).round()
	_disc(b, o + Vector2(0, 2), 9, Color("#2e4656"))           # 壳
	_disc(b, o + Vector2(0, 1), 8, Color("#4a6c7e"))
	b.draw_rect(Rect2(o + Vector2(-8, 1), Vector2(17, 1)), Color("#2e4656"))
	_disc(b, o + Vector2(0, 5), 5, Color("#e9d9c4"))           # 脸
	var reading := mem == 0 and not _helped
	if reading:
		b.draw_rect(Rect2(o + Vector2(-2, 6), Vector2(1, 1)), INK)
		b.draw_rect(Rect2(o + Vector2(2, 6), Vector2(1, 1)), INK)
		b.draw_rect(Rect2(o + Vector2(-4, 10), Vector2(8, 4)), PAPER)                # 本子
		_text(b, o + Vector2(-20, -8), "…", UITheme.TEXT, 40.0)
	else:
		b.draw_rect(Rect2(o + Vector2(-2, 4), Vector2(1, 2)), INK)
		b.draw_rect(Rect2(o + Vector2(2, 4), Vector2(1, 2)), INK)
	for k in 3:
		var p := o + Vector2(14 + k * 9, -4 - k * 2 + sin(_t * 2.0 + k) * 1.0)
		if k < mem or _helped:
			_ring(b, p, 3.0, SOFT, 12)
			b.draw_rect(Rect2(p + Vector2(-1, -2), Vector2(1, 1)), Color(1, 1, 1, 0.8))
