extends Node
## --qa_live（和 --story_auto 一起用）：边自动玩边看屏幕上的字。level_forest.gd 建它，每 EVERY 帧量一次。
##   QA_OVERLAP  两段看得见的字的框叠在一起（同一段里一个字一个 Label 的不算；一个是另一个的子节点不算）
##   QA_OFFSCREEN 看得见的字有一部分在屏幕外（480×270）
##   QA_DLG_STUCK 对话框 / 头顶气泡同一句字打完以后还挂着超过 STUCK 秒（自动玩一句 0.6 秒，气泡最多 2.3 秒）
##   QA_DLG_STALE 对话框那句是上一个 scene 的，scene 已经换了还挂着
## 同一对字只报一次（第几秒、哪个 scene、一共叠了多少帧）。退出时打印 QA_LIVE_SUMMARY。
## 人物 / 物件瞬移、凭空出现在 story_runner.gd 的 _check_jumps / _show 里（QA_JUMP / QA_CAMJUMP / QA_POPIN）。

const EVERY := 3
const STUCK := 6.0
const PAUSE_AT := [6.0, 18.0, 40.0, 80.0]    # 第几秒做一次暂停自测（那时剧情在播才做）
const STALE := 0.8
const MIN_A := 0.15              # 比这淡的字当看不见（淡入淡出的头尾）
const SCREEN := Rect2(0, 0, 480, 270)

var story: Node
var level: Node
var _f := 0
var _t := 0.0
var _pause_i := 0
var overlaps := {}               # key → {n, t, scene, a, b}
var offscreen := {}
var stuck := {}
var stale := {}
var _dlg_text := ""
var _dlg_since := 0.0
var _dlg_scene := ""
var _scene_changed_t := -1.0
var _bark_text := ""
var _bark_since := 0.0


## 软锁：左上角目标一直是这一个、这么久一个新 flag 都没设（自动玩会自己找点去互动，正常一两分钟总有进展）
const SOFTLOCK := 90.0
var _obj_key := ""
var _obj_since := 0.0
var _obj_flags := 0
var softlocks := {}


func _process(delta: float) -> void:
	_t += delta
	_f += 1
	if story == null or not is_instance_valid(story):
		return
	if _pause_i < PAUSE_AT.size() and _t >= float(PAUSE_AT[_pause_i]) and story.busy:
		_pause_i += 1
		_pause_test()
	_dialogue_state()
	_softlock()
	_menu_hover_test()
	if _f % EVERY != 0:
		return
	var items: Array = []
	_collect(get_tree().root, items)
	for i in items.size():
		var a: Dictionary = items[i]
		if not SCREEN.grow(1.0).encloses(a["r"]) and not a.get("drift", false):
			_add(offscreen, _key1(a), {"a": a})
		for j in range(i + 1, items.size()):
			var b: Dictionary = items[j]
			if _related(a, b):
				continue
			# 字框上下各有 1 像素的空（行高比字高），先各缩 1 像素再比：同一个框里名字和正文挨着不算
			var x: Rect2 = (a["r"] as Rect2).grow(-1.0).intersection((b["r"] as Rect2).grow(-1.0))
			if x.size.x >= 1.0 and x.size.y >= 1.0 and x.get_area() >= 4.0:
				_add(overlaps, _key2(a, b), {"a": a, "b": b})


## 设置 = 暂停的自测（QA_PAUSE）：剧情播到一半开设置，等真实 1 秒，什么都不该动；关掉 0.5 秒后剧情钟接着走，没有新的 QA_JUMP / QA_CAMJUMP
func _pause_test() -> void:
	var s0 := _pause_snap()
	var j0: int = story.qa_jump_n
	var by_key := _pause_i % 2 == 1                  # 一次按 Esc，一次点齿轮（走真的入口 gate_event）
	level.gate_event(_pause_event(by_key, true))
	level.gate_event(_pause_event(by_key, false))
	var was_paused: bool = get_tree().paused and level._settings.visible and level._settings.can_process()
	await get_tree().create_timer(1.0, true, false, true).timeout       # 这个定时器要在暂停时走、不看 time_scale
	var s1 := _pause_snap()
	var gear: bool = level._gear.visible
	level.gate_event(_pause_event(by_key, true))
	level.gate_event(_pause_event(by_key, false))
	await get_tree().create_timer(0.5, false).timeout
	if not is_instance_valid(story):
		return
	var moved := float(story._game_t) > float(s1["t"])
	var ok: bool = was_paused and s0 == s1 and gear and moved and not get_tree().paused and story.qa_jump_n == j0
	print("QA_PAUSE %s scene=%s step=%d 暂停=%s 齿轮=%s 关掉后接着走=%s 跳变+%d%s" % ["ok" if ok else "FAILED", s0["scene"], s0["step"], was_paused, gear, moved,
		story.qa_jump_n - j0, "" if s0 == s1 else "  变了: %s -> %s" % [s0, s1]])


func _pause_event(by_key: bool, pressed: bool) -> InputEvent:
	if by_key:
		var k := InputEventKey.new()
		k.keycode = KEY_ESCAPE
		k.pressed = pressed
		return k
	var m := InputEventMouseButton.new()
	m.button_index = MOUSE_BUTTON_LEFT
	m.pressed = pressed
	m.position = level._gear.get_global_rect().get_center()
	return m


func _pause_snap() -> Dictionary:
	return {"scene": str(story._cur_scene), "step": int(story.step_i), "t": float(story._game_t), "chen": level.chen.global_position,
		"cam": level.cam.global_position, "fade": level.fade.color.a, "flags": StoryState.flag_order.size()}


func _add(bucket: Dictionary, key: String, d: Dictionary) -> void:
	if bucket.has(key):
		bucket[key]["n"] += 1
		return
	d["n"] = 1
	d["t"] = _t
	d["scene"] = str(story._cur_scene)
	d["room"] = str(story.world.room) if story.world != null else ""
	bucket[key] = d
	var tag := "QA_OVERLAP" if bucket == overlaps else "QA_OFFSCREEN"
	if d.has("b"):
		print("%s t=%.1f scene=%s room=%s「%s」%s × 「%s」%s | %s × %s" % [tag, _t, d["scene"], d["room"], _short(d["a"]["text"]), _rs(d["a"]["r"]),
			_short(d["b"]["text"]), _rs(d["b"]["r"]), _who(d["a"]["path"]), _who(d["b"]["path"])])
	else:
		print("%s t=%.1f scene=%s room=%s「%s」%s %s" % [tag, _t, d["scene"], d["room"], _short(d["a"]["text"]), _rs(d["a"]["r"]), d["a"]["path"]])


## 节点路径的最后两段（哪个界面的字）
static func _who(p: String) -> String:
	var parts := p.split("/")
	return "/".join(parts.slice(maxi(0, parts.size() - 3)))


static func _rs(r: Rect2) -> String:
	return "(%d,%d %dx%d)" % [int(r.position.x), int(r.position.y), int(r.size.x), int(r.size.y)]


static func _short(s: String) -> String:
	s = s.replace("\n", "⏎")
	return s if s.length() <= 18 else s.substr(0, 18) + "…"


func _key1(a: Dictionary) -> String:
	return _short(a["text"]) + "@" + str(a["path"]).get_file()


func _key2(a: Dictionary, b: Dictionary) -> String:
	var k := [_short(a["text"]), _short(b["text"])]
	k.sort()
	return k[0] + " × " + k[1]


## 一个是另一个的祖先，或者同一个父节点下一个字一个 Label（潜意识字的字带、闪回逐字掉）
func _related(a: Dictionary, b: Dictionary) -> bool:
	var na: Node = a["node"]
	var nb: Node = b["node"]
	if na.is_ancestor_of(nb) or nb.is_ancestor_of(na):
		return true
	if na.get_parent() == nb.get_parent() and str(a["text"]).length() <= 1 and str(b["text"]).length() <= 1:
		return true
	return false


# ----------------------------------------------------------------------- 收集看得见的字
func _collect(n: Node, out: Array) -> void:
	if n is CanvasLayer and not (n as CanvasLayer).visible:
		return
	if n is CanvasItem and not (n as CanvasItem).visible:
		return
	if n is Label:
		var l := n as Label
		if l.text.strip_edges() != "" and l.visible_characters != 0:
			var a := _alpha(l)
			if a >= MIN_A:
				var r := _text_rect(l)
				if r.size.x > 0.5 and r.size.y > 0.5:
					out.append({"node": l, "text": l.text, "r": r, "path": str(l.get_path()), "drift": _drifting(l)})
	elif n is CanvasItem and n.has_method("qa_label"):      # 画出来的字（奔跑片头的名字 run_credits.gd 的 Moment）：自己报屏幕上的框
		var d = n.call("qa_label")
		if d is Dictionary and not d.is_empty():
			out.append({"node": n, "text": str(d["text"]), "r": d["r"], "path": str(n.get_path()), "drift": true})
	for c in n.get_children():
		_collect(c, out)


func _alpha(c: CanvasItem) -> float:
	var a := c.self_modulate.a
	var n: Node = c
	while n != null and n is CanvasItem:
		a *= (n as CanvasItem).modulate.a
		n = n.get_parent()
	return a


## 本来就是从屏幕外飘进来的字：潜意识字的字带（一个字一个 Label）、奔跑片头挂在世界里的名字
func _drifting(l: Label) -> bool:
	var p := str(l.get_path())
	return (l.text.length() <= 1 and p.contains("InnerVoice")) or p.contains("RunCredits")


## Label 里字真正占的那一块（屏幕坐标）：换行按框宽，左右按对齐
func _text_rect(l: Label) -> Rect2:
	var f := l.get_theme_font("font")
	var fs := l.get_theme_font_size("font_size")
	if f == null:
		return Rect2()
	var lh := f.get_height(fs) + float(l.get_theme_constant("line_spacing"))
	var tw := 0.0
	var th := 0.0
	if l.autowrap_mode == TextServer.AUTOWRAP_OFF:
		var lines := l.text.split("\n")
		for line in lines:
			tw = maxf(tw, f.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x)
		th = lines.size() * lh
	else:
		var w := maxf(l.size.x, 1.0)
		var ms := f.get_multiline_string_size(l.text, HORIZONTAL_ALIGNMENT_LEFT, w, fs, -1,
			TextServer.BREAK_MANDATORY | TextServer.BREAK_WORD_BOUND | TextServer.BREAK_ADAPTIVE)
		tw = minf(ms.x, w)
		th = float(l.get_line_count()) * lh
	var x := 0.0
	match l.horizontal_alignment:
		HORIZONTAL_ALIGNMENT_CENTER:
			x = (l.size.x - tw) / 2.0
		HORIZONTAL_ALIGNMENT_RIGHT:
			x = l.size.x - tw
	var y := 0.0
	match l.vertical_alignment:
		VERTICAL_ALIGNMENT_CENTER:
			y = (l.size.y - th) / 2.0
		VERTICAL_ALIGNMENT_BOTTOM:
			y = l.size.y - th
	var xf := l.get_global_transform_with_canvas()
	var p0 := xf * Vector2(x, y)
	var p1 := xf * Vector2(x + tw, y + th)
	return Rect2(p0, p1 - p0).abs()


# ----------------------------------------------------------------------- 对话框状态
func _dialogue_state() -> void:
	var dlg = story.dlg
	var box = dlg.get("_box")
	var txt_l = dlg.get("_text")
	var shown: bool = box != null and (box as CanvasItem).is_visible_in_tree() and (box as CanvasItem).modulate.a > MIN_A
	var t: String = str((txt_l as Label).text) if shown and txt_l != null else ""
	if t != _dlg_text:
		_dlg_text = t
		_dlg_since = _t
		_dlg_scene = str(story._cur_scene)
		_scene_changed_t = -1.0
	if t != "":
		var typing: bool = dlg.is_typing()
		if typing:
			_dlg_since = _t
		elif _t - _dlg_since > STUCK and not dlg.picking() and not dlg.menu_open():
			_flag_once(stuck, "dlg:" + t, "QA_DLG_STUCK 对话框「%s」打完以后挂了 %.1f 秒 scene=%s" % [_short(t), _t - _dlg_since, story._cur_scene])
		if str(story._cur_scene) != _dlg_scene:
			if _scene_changed_t < 0.0:
				_scene_changed_t = _t
			elif _t - _scene_changed_t > STALE:
				_flag_once(stale, t, "QA_DLG_STALE 对话框「%s」是 scene %s 的，已经到 %s 了还挂着" % [_short(t), _dlg_scene, story._cur_scene])
	var bk = story.bark
	var bb = bk.get("_box") if bk != null else null
	var bl = bk.get("_label") if bk != null else null
	var bshown: bool = bb != null and (bb as CanvasItem).is_visible_in_tree() and (bb as CanvasItem).modulate.a > MIN_A
	var bt: String = str((bl as Label).text) if bshown and bl != null else ""
	if bt != _bark_text:
		_bark_text = bt
		_bark_since = _t
	elif bt != "" and _t - _bark_since > STUCK:
		_flag_once(stuck, "bark:" + bt, "QA_DLG_STUCK 头顶气泡「%s」挂了 %.1f 秒 scene=%s" % [_short(bt), _t - _bark_since, story._cur_scene])


func _softlock() -> void:
	var o: Dictionary = story.objective()
	var k := str(o.get("zh", ""))
	var nf: int = StoryState.flag_order.size()
	if k != _obj_key or nf != _obj_flags:
		_obj_key = k
		_obj_flags = nf
		_obj_since = _t
		return
	if k != "" and _t - _obj_since > SOFTLOCK and not story.ended:
		var av: Array = []
		for p in story.hotspots.available():
			av.append(str(p["h"].get("id", "")))
		_flag_once(softlocks, k, "QA_SOFTLOCK 目标「%s」%.0f 秒没有进展 room=%s x=%d 能用的点：%s" % [k, _t - _obj_since, story.world.room,
			int(story.chen.position.x), ", ".join(av) if not av.is_empty() else "（没有）"])


func _flag_once(bucket: Dictionary, key: String, msg: String) -> void:
	if bucket.has(key):
		return
	bucket[key] = true
	print(msg)


func summary() -> String:
	return "QA_LIVE_SUMMARY overlap=%d offscreen=%d dlg_stuck=%d dlg_stale=%d softlock=%d" % [overlaps.size(), offscreen.size(), stuck.size(), stale.size(), softlocks.size()]


# ----------------------------------------------------------------------- 选项 hover 音（11-06 作者：鼠标停在选项边缘，音效连续不断）
## 第一个文字选项菜单打开时跑一次：鼠标放到两项交界，每帧抖 1 像素，抖 HOVER_SEC 秒，数 ui_click 响了几次（> HOVER_MAX = QA_MENU_HOVER_FAIL）。
## 走真正的输入入口 dlg.handle_input；期间暂停自动选，测完放回去。
const HOVER_SEC := 2.0
const HOVER_MAX := 2
var _hover := 0                  # 0 没开始 / 1 在抖 / 2 测完
var _hover_f := 0
var _hover_t := 0.0
var _hover_clicks := 0
var _hover_sfx: Callable
var _hover_auto := -1
var _hover_moved := false
var _hover_sel := -1


func _menu_hover_test() -> void:
	if _hover == 2:
		return
	var dlg = story.dlg
	if _hover == 0:
		if not dlg.menu_open() or str(dlg._menu_kind) != "lines" or (dlg._menu_items as Array).size() < 2 or dlg._menu_done:
			return
		_hover = 1
		_hover_auto = int(dlg._menu_auto)
		dlg._menu_auto = -1
		_hover_sfx = dlg.sfx
		dlg.sfx = func(n: String, db: float, pitch: float) -> void:
			if n == "ui_click":
				_hover_clicks += 1
			_hover_sfx.call(n, db, pitch)
	_hover_f += 1
	_hover_t += get_process_delta_time()
	var c: Control = dlg._menu_items[0]
	var ev := InputEventMouseMotion.new()
	ev.position = c.position + Vector2(40.0, 16.0 + float(_hover_f % 2))
	if not _hover_moved and _hover_t >= HOVER_SEC / 2.0:
		# 抖到一半真的移到下一项：hover 还得能换（不然 0 次也可能是 hover 坏了），响一声；接着从下一项这边压回交界继续抖，不再响
		_hover_moved = true
		var c1: Control = dlg._menu_items[1]
		ev.position = c1.position + Vector2(40.0, 8.0)
		dlg.handle_input(ev)
		_hover_sel = int(dlg._menu_sel)
		ev = InputEventMouseMotion.new()
		ev.position = c.position + Vector2(40.0, 17.0)
	dlg.handle_input(ev)
	if _hover_t >= HOVER_SEC:
		_hover = 2
		var ok := _hover_clicks <= HOVER_MAX and _hover_sel == 1 and _hover_clicks >= 1
		dlg.sfx = _hover_sfx
		dlg._menu_auto = _hover_auto
		dlg._menu_age = 0.0
		dlg._menu_sel = 0
		dlg._menu_style()
		print("%s clicks=%d moved_to=%d frames=%d（鼠标在两项交界每帧抖 1 像素 %.0f 秒，中途移到下一项一次）" % ["QA_MENU_HOVER ok" if ok else "QA_MENU_HOVER_FAIL", _hover_clicks, _hover_sel, _hover_f, HOVER_SEC])


func _exit_tree() -> void:
	print(summary())
