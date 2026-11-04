extends "res://scripts/side_kit.gd"
## 第一关支线 2a「收音机送回小吃棚」：调台（docs/剧情改动/第一关支线_设计.md）。
##
## 画面：收音机正面的特写（木壳、上面一长条刻度窗、左边喇叭布、右边猫眼灯和旋钮）。指针在刻度窗里左右走，
##   面板下面是字幕：现在收到的台在说什么（信号弱的时候字是花的，越调准越清楚），沙沙声跟着变小、猫眼灯变亮。
## 怎么玩：按住 ←/→（A/D），或鼠标按住面板左半 / 右半拧旋钮（越拧越快），滚轮细调。中间串到几个怪台，
##   调到小吃棚以前的叫卖声那个台、停住不动一小会儿 = 锁住（指针「咔」地落准），做完。
## 放水：路过叫卖声那个台又走掉 FAILS_GIVE 次，或第 ENTER_GIVE 次进 → 指针自己被信号吸过去。
##
## 剧本步骤：{"do": "mechanic", "id": "side_radio", "stations": [{"f": 0..100, "zh", "en", "need"?, "not"?, "final"?, "sfx"?, "key"?}…]}
##   （同一个 f 写几条 = 按 flag 挑第一条能用的，比如失物招领按 c1_mom / c1_child 换词；final 那个台 = 要调到的）
##   可选 "sets"、"hint"、"lines": {intro, <台的 key>（第一次听清那个台以后播一次，比如 lost）, give, done}。
## 进度：{enter, fails, done}。

const DIAL_X0 := 20.0                     # 刻度 0 和 100 在面板里的 x
const DIAL_X1 := 212.0
const NEEDLE_Y := Vector2(15, 37)
const KNOB := Vector2(187, 108)
const START_F := 6.0
const WIDTH := 6.0                        # 离台多远开始听得见
const LOCK := 1.6                         # 离 final 多近、停多久算调准
const LOCK_SEC := 0.7
const VMAX := 26.0                        # 最快每秒走多少
const VMIN := 5.0
const ACC_SEC := 1.4
const HINT := {"zh": "←→ 或按住左右拧旋钮，找小吃棚的台", "en": "← → or hold left / right to turn the dial. Find the stall's station."}
const BROADCAST := Color("#a9d8bc")
const CAP_RECT := Rect2(20, 50, 128, 82)  # 字幕在面板里的位置：喇叭布那一块（radio_panel.png 的 16..151 × 48..134）
const CAP_BG := Color("#17140e")
const STATIC_DB := -8.0

var stage := ""                           # tune / lock / done
var f := START_F
var v := 0.0
var dir := 0
var _key_dir := 0
var _mouse_dir := 0
var _held := 0.0
var _still := 0.0
var _in_final := false
var _heard := {}
var stations: Array = []
var final_f := 88.0
var _static: AudioStreamPlayer
var _drift := false
var _lock_a := 0.0
var _cap := ""
var _cap_a := 0.0
var _seed := 0
var _capl: Label
var _cap_room := 1.0                     # 对话 / 选项在显示的时候字幕让开（0..1）


func _init() -> void:
	ID = "side_radio"


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	level = lv
	step = st
	stations = pick_stations(st)
	for q in stations:
		if q.get("final", false):
			final_f = float(q["f"])
	var give := _enter({})
	_build("SideRadio", ["radio_panel", "radio_eye", "radio_knob"])
	_make_caption()
	await _fade_in()
	_static = _loop("radio_static", STATIC_DB)
	await _lines("intro")
	stage = "tune"
	_set_hint(step.get("hint", HINT))
	if give or auto_mode:
		if give and not auto_mode:
			await _lines("give")
		await _auto_tune(give)
	else:
		_accept = true
		while _alive() and stage == "tune":
			var res: String = await _stage
			if res == "give":
				_accept = false
				dir = 0
				await _lines("give")
				await _auto_tune(true)
				break
			if res.begins_with("heard:"):
				_accept = false
				dir = 0
				v = 0.0
				await _wait(OL.READ_SEC)              # 字幕先念完再开选项（选项开着的时候字幕让开）
				await _lines(res.substr(6))
				_key_dir = 0                         # 台词播的时候松开的键收不到：清零，免得指针自己走
				_mouse_dir = 0
				_accept = stage == "tune"
	_accept = false
	if not _alive():
		_drop()
		return
	await _lock()
	_done()
	await _lines("done")
	if _static != null and is_instance_valid(_static):
		var tw := _tw()
		tw.tween_property(_static, "volume_db", -60.0, 0.6)
	await _fade_out()


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


func ff(r: Node, st: Dictionary) -> void:
	_ff_save(r, st)


func check(r: Node, st: Dictionary) -> Array:
	var out := _check_lines(r, st, ["intro", "give", "done"])
	var n_final := 0
	for q in st.get("stations", []):
		if not q is Dictionary or not q.has("f") or str(q.get("zh", "")) == "" or str(q.get("en", "")) == "":
			out.append("stations：每个台要有 f / zh / en：%s" % str(q))
			continue
		if float(q["f"]) < 0.0 or float(q["f"]) > 100.0:
			out.append("stations：f 要在 0..100：%s" % str(q["f"]))
		if q.get("final", false):
			n_final += 1
		if q.has("key") and not KIT.has_lines(st, str(q["key"])):
			out.append("info: 台 %s 有 key，但没有 lines.%s" % [str(q["f"]), str(q["key"])])
	if st.has("stations") and n_final == 0:
		out.append("stations 里要有一个 final（要调到的那个台）")
	return out


## 同一个 f 的几条里挑第一条 flag 对得上的
static func pick_stations(st: Dictionary) -> Array:
	var src: Array = st.get("stations", DEFAULT)
	var by_f := {}
	var out: Array = []
	for q in src:
		if not q is Dictionary:
			continue
		var k := str(q.get("f", 0))
		if by_f.has(k):
			continue
		if StoryState.all_of(q.get("need", [])) and StoryState.none_of(q.get("not", [])):
			by_f[k] = true
			out.append(q)
	return out


const DEFAULT := [
	{"f": 20, "zh": "……今天晴，明天晴，以后也一直晴……", "en": "...Sunny today, sunny tomorrow, sunny from now on..."},
	{"f": 88, "zh": "热乎的——刚出锅的——", "en": "Piping hot! Fresh out of the pot!", "final": true},
]


# ----------------------------------------------------------------------- 玩
func _press(e: InputEvent) -> bool:
	if stage != "tune":
		return false
	if e is InputEventKey:
		var k: int = (e as InputEventKey).keycode
		if k in [KEY_LEFT, KEY_A, KEY_RIGHT, KEY_D]:
			var d := -1 if k in [KEY_LEFT, KEY_A] else 1
			if e.is_pressed():
				_key_dir = d
			elif _key_dir == d:
				_key_dir = 0
			return true
	elif e is InputEventMouseButton:
		var mb := e as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_LEFT:
			_mouse_dir = (1 if _mouse().x >= panel.x * 0.5 else -1) if mb.pressed else 0
			return true
		if mb.pressed and mb.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			f = clampf(f + (1.2 if mb.button_index == MOUSE_BUTTON_WHEEL_UP else -1.2), 0.0, 100.0)
			_held = 0.0
			return true
	return false


func strength_at(x: float) -> Dictionary:
	var best := {"s": 0.0, "q": {}}
	for q in stations:
		var sv := clampf(1.0 - absf(x - float(q["f"])) / WIDTH, 0.0, 1.0)
		if sv > float(best["s"]):
			best = {"s": sv, "q": q}
	return best


func _tick(dt: float) -> void:
	if stage == "tune" and not _drift:
		var want := _key_dir if _key_dir != 0 else _mouse_dir
		if not _accept and not auto_mode:
			want = 0
		if auto_mode:
			want = dir
		if want != 0:
			_held += dt
			var top := lerpf(VMIN, VMAX, clampf(_held / ACC_SEC, 0.0, 1.0))
			v = move_toward(v, want * top, dt * 90.0)
		else:
			_held = 0.0
			v = move_toward(v, 0.0, dt * 120.0)
		f = clampf(f + v * dt, 0.0, 100.0)
		if f <= 0.0 or f >= 100.0:
			v = 0.0
		_watch(dt)
	var st := strength_at(f)
	var sv: float = st["s"]
	if _static != null and is_instance_valid(_static):
		if stage != "done":
			_static.volume_db = lerpf(STATIC_DB, -34.0, sv)
	var q: Dictionary = st["q"]
	if sv > 0.22 and not q.is_empty():
		_cap = I18n.pick(q)
		_cap_a = move_toward(_cap_a, 1.0, dt * 4.0)
	else:
		_cap_a = move_toward(_cap_a, 0.0, dt * 3.0)
	_seed = int(_t * 8.0)
	_cap_room = move_toward(_cap_room, 0.0 if OL.busy(story) else 1.0, dt * 5.0)
	if _capl != null and is_instance_valid(_capl):
		_capl.text = caption_text()
		_capl.modulate.a = ceilf(_cap_a * _cap_room * 3.0) / 3.0 * board.modulate.a


## 听清了哪个台、路过 final 又走掉、停在 final 上
func _watch(dt: float) -> void:
	if auto_mode or not _accept:
		return
	var st := strength_at(f)
	var q: Dictionary = st["q"]
	if float(st["s"]) > 0.86 and not q.is_empty():
		var k := str(q.get("key", ""))
		if k != "" and not _heard.has(k) and KIT.has_lines(step, k):
			_heard[k] = true
			_stage.emit("heard:" + k)
			return
	var near := absf(f - final_f) <= LOCK
	var inside := absf(f - final_f) < WIDTH * 0.7
	if inside:
		_in_final = true
	elif _in_final:
		_in_final = false
		if not auto_mode and _fail():
			_stage.emit("give")
			return
	if near and absf(v) < 2.0:
		_still += dt
		if _still >= LOCK_SEC:
			stage = "lock"
			_stage.emit("lock")
	else:
		_still = 0.0


## 自己调：往右拧，路过每个台停一下（看得见在说什么），最后停在 final 上；give = 被信号吸过去
func _auto_tune(give: bool) -> void:
	if give:
		_drift = true
		var tw := _tw()
		tw.tween_property(self, "f", final_f, 2.4 * maxf(_k(), 0.5)).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		await tw.finished
		stage = "lock"
		return
	var stops: Array = []
	for q in stations:
		stops.append(float(q["f"]))
	stops.sort()
	for sf in stops:
		dir = 1 if sf > f else -1
		while _alive() and stage == "tune" and absf(f - sf) > 1.2:
			if (dir > 0 and f > sf) or (dir < 0 and f < sf):
				break
			await _frame()
		dir = 0
		if stage != "tune":
			break
		var tw := _tw()
		tw.tween_property(self, "f", sf, 0.3).set_trans(Tween.TRANS_SINE)
		await tw.finished
		await _wait(0.8)
		var k := ""
		for q in stations:
			if absf(float(q["f"]) - sf) < 0.01:
				k = str(q.get("key", ""))
		if k != "" and not _heard.has(k) and KIT.has_lines(step, k):
			_heard[k] = true
			await _lines(k)
	stage = "lock"


func _lock() -> void:
	stage = "lock"
	dir = 0
	v = 0.0
	var tw := _tw()
	tw.tween_property(self, "f", final_f, 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(self, "_lock_a", 1.0, 0.4)
	await tw.finished
	_sfx("small_click")
	_set_hint({})
	for q in stations:
		if q.get("final", false) and q.has("sfx"):
			_sfx(str(q["sfx"]), -6.0)
	await _wait(1.6)
	stage = "done"


# ----------------------------------------------------------------------- 画
func fx(x: float) -> float:
	return DIAL_X0 + (DIAL_X1 - DIAL_X0) * x / 100.0


func _draw_board(b: Control) -> void:
	b.draw_texture(_tex["radio_panel"], Vector2.ZERO)
	var sv: float = strength_at(f)["s"]
	if _tex["radio_eye"] != null:
		var lv := floorf(maxf(sv, _lock_a) * 4.0) / 4.0          # 猫眼灯分四档亮，不是平滑的
		if lv > 0.0:
			b.draw_texture(_tex["radio_eye"], Vector2.ZERO, Color(1, 1, 1, lv))
	if _tex["radio_knob"] != null:
		b.draw_texture(_tex["radio_knob"], KNOB - Vector2(15, 15))
	var ang := f * 0.11 - PI * 0.5
	var tip := KNOB + Vector2(cos(ang), sin(ang)) * 11.0
	var mid := KNOB + Vector2(cos(ang), sin(ang)) * 6.0
	b.draw_line(mid.round(), tip.round(), Color("#2c2118"), 2.0)
	if _capl != null and _capl.modulate.a > 0.0:
		b.draw_rect(Rect2(CAP_RECT.position - Vector2(2, 2), CAP_RECT.size + Vector2(4, 4)), Color(CAP_BG, 0.82 * _capl.modulate.a))
	var x := roundf(fx(f))
	b.draw_rect(Rect2(x, NEEDLE_Y.x, 1, NEEDLE_Y.y - NEEDLE_Y.x), Color("#e8795a"))
	b.draw_rect(Rect2(x - 1, NEEDLE_Y.x, 3, 2), Color("#c9473a"))
	if _lock_a > 0.0:
		b.draw_rect(Rect2(x - 1, NEEDLE_Y.y - 2, 3, 2), Color("#f0c070", _lock_a))


## 字幕：画在收音机自己的喇叭布上（CAP_RECT，面板里），不进屏幕下方对话那一带；信号弱的时候字是花的
func _make_caption() -> void:
	_capl = Label.new()
	_capl.position = panel_pos + CAP_RECT.position
	_capl.size = CAP_RECT.size
	_capl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_capl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_capl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_capl.clip_text = true
	_capl.add_theme_font_size_override("font_size", 14)
	_capl.add_theme_color_override("font_color", BROADCAST)
	_capl.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))
	_capl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_capl.modulate.a = 0.0
	_root.add_child(_capl)


func caption_text() -> String:
	if _cap_a <= 0.0 or _cap == "":
		return ""
	var sv: float = strength_at(f)["s"] if stage == "tune" else 1.0
	if sv >= 0.86 or stage != "tune":
		return _cap
	var out := ""
	var i := 0
	for ch in _cap:
		var h := absi(hash(str(i) + ":" + str(_seed))) % 100
		out += ch if float(h) / 100.0 < sv * 1.1 else "～"
		i += 1
	return out
