extends Control
## 通讯器界面（旧的手持通讯器：深色机壳、暗绿的屏、底下两个软键）+ 剧本的 phone_* 步骤。约定见 docs/phone_and_cockpit_contract.md。
## story_runner.gd 在 setup 里建它（放在关卡 UI 层最上面），_step 里 phone_* 一律交给 step()；数据都在 phone_state.gd（进 StoryState 存档）。
##
## 画面（480×270 里正中一块 312×222）：
##   左边联系人列表（名字；有未读 = 名字右边一个暖色小点；失联的朋友永远没有未读），选中的那行底色亮一档、左边一道竖条。
##   右边聊天：上面联系人名字；晨的消息靠右（紫灰底）、对方靠左（青灰底）；日期变了中间一行暗色小字；补写（added）的字 debug 下蓝色。
##   下面输入栏：不能自由打字——只有剧本给了字（phone_draft 的草稿、「稍后看」留着的回复）才有字，后面一个闪的光标。
##   最底下一条软键（老手机的左右软键）：左 = 回复 / 发送，右 = 稍后看 / 暂时不发 / 关闭。选中的那个反色，确认闪一下 + 音效。
##   美术有 art/ui/phone_frame.png（外框，九宫格拉到 312×222）/ art/ui/phone_notify.png（通知卡，九宫格）就用，没有就自己画。
##   通知卡左边的小图标用 art/forest_story/icon_communicator.png，没有就画一个 8×12 的小机子。
## 模式（mode）：
##   notify  phone_msg：右上角滑进一张通知卡（联系人名 + 「新消息」）+ phone_buzz。确认 / 点击 = 点开；Esc = 直接稍后看。
##   msg     点开以后：通讯器打开到那个人的聊天，新消息在最下面，输入栏里是要回的那句，软键「回复」「稍后看」。
##   draft   phone_draft：输入栏里打好了字，软键「发送」「暂时不发」。发送 = 追加 + 设 flag；不发 = 字留在输入栏（以后打开还在）。
##   view    phone_send / phone_open：打开给玩家看（phone_send 的那条稍后「出现」+ phone_send 音效），软键「关闭」，确认 / Esc / 点击都关。
##   browse  背包里点通讯器的「查看」（或 F8）：↑↓ 换联系人，←→ 选软键，确认按软键，Esc / Tab 关回背包；滚轮 / PgUp PgDn 翻聊天。
##           「稍后看」留着的回复、「暂时不发」的草稿在这里还能发出去（草稿发出去照样设 flag）。
## 输入：鼠标单击 / E / 空格 / 回车 / Z 通用确认，Esc 关；开着的时候吃掉所有按键和点击（F8 除外），后面的背包 / 剧情收不到。
## 自动（--story_auto、--autoplay、F8 跳过对话、--dev_test 里 dlg.auto_delay >= 0）：通知自己点开，软键自己选——
##   --story_auto=full 选右边（稍后看 / 暂时不发），别的选左边（回复 / 发送）；跳节拍（ff）不出界面，直接按左边那个算。
## 动画都按 100ms 一格：通知卡分三格滑进来、再左右抖两下；屏幕打开时先暗一格、半亮一格、再全亮。

const PS := preload("res://scripts/phone_state.gd")
const ITEM_ID := "communicator"

const FRAME := Rect2(84, 27, 312, 218)
const SCR := Rect2(90, 33, 300, 206)        # = FRAME 往里缩 6（和美术的 phone_frame 九宫格屏幕位置一致）
const LIST_W := 88.0
const ROW_H := 18.0
const HEAD_H := 18.0
const KEY_H := 16.0
const BUBBLE_MAX := 140.0             # 气泡里一行最宽（10 个汉字）
const FS := 14
const STEP := 0.1                     # 动画一格 100ms

const ADDED_C := Color("#8fb8e0")
const C_DIM := Color(0.0, 0.02, 0.01, 0.45)
const C_CASE := Color("#1b2420")
const C_CASE_EDGE := Color("#3a4a42")
const C_CASE_HI := Color("#27332e")
const C_SLOT := Color("#0a100d")
const C_SCREEN := Color("#0d1714")
const C_RECESS := Color("#070c0a")
const C_LINE := Color("#22322b")
const C_ROW_SEL := Color("#182720")
const C_ME := Color("#33252f")
const C_ME_EDGE := Color("#5e4557")
const C_THEM := Color("#17241f")
const C_THEM_EDGE := Color("#34473e")
const C_INPUT := Color("#09110e")
const C_KEY_SEL := Color("#2c2029")
const C_CARD := Color(0.02, 0.05, 0.04, 0.9)
const C_CARD_EDGE := Color(0.5, 0.6, 0.55, 0.45)
const LED_OFF := Color("#2f4a3c")

const ART_DIR := "res://art/ui/"
const ART_SPEC := "res://art/ui/phone_ui.json"     # 美术给的九宫格边距：{items: {名字: {margins: [左, 上, 右, 下]}}}
const ART_NINE := ["phone_frame", "phone_notify", "phone_bubble_in", "phone_bubble_out", "phone_button", "phone_button_hover", "phone_input"]
const SCR_TEXT := Color("#b9c9bf")    # 美术建议：屏上的字
const BTN_TEXT := Color("#e3dccb")    # 美术建议：按钮上的字
const ART_ICON := "res://art/forest_story/icon_communicator.png"

## 界面字（不进 i18n.gd：那份大家都在改）：[en, zh]
const T := {
	"view": ["View", "查看"],
	"reply": ["Reply", "回复"],
	"later": ["Later", "稍后看"],
	"send": ["Send", "发送"],
	"not_now": ["Not now", "暂时不发"],
	"close": ["Close", "关闭"],
	"fold": ["Dismiss", "收起"],
	"new_msg": ["New message", "新消息"],
	"no_contacts": ["No contacts", "没有联系人"],
}

signal _chosen(i: int)

var story: Node                       # story_runner.gd
var level: Node
var mode := ""
var cur := ""                         # 正在看的联系人
var _keys: Array = []                 # 软键 [{id, label}]：两个 = 左右，一个 = 右
var _sel := 0
var _age := 0.0
var _flash := 0.0
var _choosing := false
var _scroll := 0.0                    # 聊天往上翻了多少像素（0 = 最底下）
var _content_h := 0.0
var _fresh := -1                      # 刚追加的第一条（第几条）：从它往后一条一条「到」，到之前不画，到的时候一声音效
var _fresh_t := 0.0                   # 第一条还要等多久
var _fresh_gap := 0.45                # 后面每条再隔多久
var _fresh_clock := 0.0
var _fresh_end := -1                  # 最后一条
var _fresh_sfx := ""
var _fresh_played := -1               # 音效响到第几条了
var _own_lock := false                # 不是从背包打开的（F8）：自己锁晨
var _last_browse := ""
var _layout: Array = []               # 聊天排好的版：[{kind: date/msg, y, h, lines, me, added, idx}]
var _layout_key := ""
var _chat: Control
var _fh := 14.0
var _asc := 11.0
var _lh := 15.0                       # 气泡里的行高
var _nine := {}                       # 美术的九宫格：名字 → StyleBoxTexture（没有图就没有这一项，画的时候退回自己画）
var _tex_unread: Texture2D
var _tex_icon: Texture2D
var _dev_n := 0
var _sent_n := 1
var _msg_id := ""                     # 正在弹的那条 phone_msg


func _set_fresh(first: int, wait: float, sfx: String) -> void:
	_fresh = maxi(0, first)
	_fresh_end = PS.history(cur).size() - 1
	_fresh_t = wait
	_fresh_clock = 0.0
	_fresh_sfx = sfx
	_fresh_played = _fresh - 1
	_scroll = 0.0


## 已经「到」了的最后一条（第几条）
func _fresh_arrived() -> int:
	if _fresh < 0:
		return 1 << 30
	if _fresh_clock < _fresh_t:
		return _fresh - 1
	return mini(_fresh_end, _fresh + int((_fresh_clock - _fresh_t) / _fresh_gap))


static func t(k: String) -> String:
	var row: Array = T.get(k, [k, k])
	return str(row[1] if I18n.is_zh() else row[0])


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false
	var f := UITheme.font()
	_fh = roundf(f.get_height(FS))
	_asc = roundf(f.get_ascent(FS))
	_lh = _fh + 1.0
	_chat = Control.new()
	_chat.clip_contents = true
	_chat.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_chat.draw.connect(_draw_chat)
	add_child(_chat)
	_load_art()
	if ResourceLoader.exists(ART_ICON):
		_tex_icon = load(ART_ICON)


func _load_art() -> void:
	var spec = JSON.parse_string(FileAccess.get_file_as_string(ART_SPEC)) if FileAccess.file_exists(ART_SPEC) else null
	var items: Dictionary = spec.get("items", {}) if spec is Dictionary else {}
	for n in ART_NINE:
		var path: String = ART_DIR + n + ".png"
		if not ResourceLoader.exists(path):
			continue
		var tex: Texture2D = load(path)
		var sb := StyleBoxTexture.new()
		sb.texture = tex
		var m: Array = (items.get(n, {}) as Dictionary).get("margins", [])
		if m.size() == 4:
			sb.texture_margin_left = float(m[0])
			sb.texture_margin_top = float(m[1])
			sb.texture_margin_right = float(m[2])
			sb.texture_margin_bottom = float(m[3])
		else:
			sb.set_texture_margin_all(floorf(minf(tex.get_width(), tex.get_height()) / 3.0))
		_nine[n] = sb
	if ResourceLoader.exists(ART_DIR + "phone_unread.png"):
		_tex_unread = load(ART_DIR + "phone_unread.png")


# ======================================================================= 外面用的
func is_open() -> bool:
	return mode != ""


## 剧情在等通讯器（卡死检测别把它当卡住）
func waiting() -> bool:
	return mode in ["notify", "msg", "draft", "view"]


## 背包里「查看」：剧情播放中不开
func open_browse(id := "") -> void:
	if mode != "" or story == null or story.busy:
		return
	var ids := PS.visible_ids()
	var pick := ""
	if id != "" and ids.has(id):
		pick = id
	if pick == "":
		for c in ids:
			if PS.unread(c):
				pick = c
				break
	if pick == "" and ids.has(_last_browse):
		pick = _last_browse
	if pick == "" and not ids.is_empty():
		pick = ids[0]
	_own_lock = not _bag_visible()
	if _own_lock and story.chen != null:
		story.chen.input_enabled = false
		story.chen.auto_dir = 0.0
	_open("browse", pick)
	PS.mark_read(pick)


func close() -> void:
	if mode == "":
		return
	var was_browse := mode == "browse"
	mode = ""
	visible = false
	_fresh = -1
	_choosing = false
	if was_browse:
		_last_browse = cur
		_sfx("ui_click", -12.0, 0.85)
	if _own_lock:
		_own_lock = false
		if story.chen != null and not story.busy and not _bag_visible() and _level_playing():
			story.chen.input_enabled = true


## 剧本步骤（story_runner._step 交过来，等它返回再下一步）
func step(st: Dictionary) -> void:
	var d := str(st.get("do", ""))
	var ff: bool = story.ff
	match d:
		"phone_add":
			PS.add_contact(str(st.get("id", "")), st)
		"phone_msg":
			await _step_msg(st, ff)
		"phone_send":
			var to := str(st.get("to", ""))
			_sent_n = PS.send(to, _text(st), bool(st.get("added", false)))
			if not ff:
				await _story_view(to, true)
		"phone_open":
			var c := str(st.get("contact", st.get("id", "")))
			PS.mark_read(c)
			if not ff:
				await _story_view(c, false)
		"phone_draft":
			await _step_draft(st, ff)
	if str(story.auto) != "" and not ff:
		var c2 := str(st.get("from", st.get("to", st.get("contact", st.get("id", "")))))
		print("STORY_PHONE %s %s  unread=%s input=%s" % [d, c2, PS.unread(c2), str(PS.input_of(c2).get("kind", "-"))])


func _text(st: Dictionary) -> Dictionary:
	var d := {"zh": str(st.get("zh", "")), "en": str(st.get("en", ""))}
	if st.has("date"):
		d["date"] = str(st["date"])
	return d


func _step_msg(st: Dictionary, ff: bool) -> void:
	var mid := str(st.get("id", ""))
	if mid == "":
		mid = "msg_%d" % hash(JSON.stringify(st))
	if PS.is_fired(mid):
		return                        # 同一条只来一次（剧情重播 / 跳节拍）
	var from := str(st.get("from", ""))
	_msg_id = mid
	PS.receive(mid, from, _text(st), st.get("reply", null), bool(st.get("added", false)))
	var has_reply := str(PS.input_of(from).get("msg", "")) == mid
	if ff:
		if has_reply:
			PS.send_input(from)
		return
	_open("notify", from)
	_sfx("phone_buzz", -4.0)
	story._ui_shot("phone_notify", 0.45)
	var r: int = await _chosen
	if r != 0:
		return                        # Esc：直接稍后看（未读和要回的那句都留着）
	_open("msg", from)
	var n_new := PS.split(_text(st)).size()
	_set_fresh(PS.history(from).size() - n_new, 0.25, "small_click")
	story._ui_shot("phone_msg", 0.85)
	await _chosen


func _step_draft(st: Dictionary, ff: bool) -> void:
	var to := str(st.get("to", ""))
	PS.set_draft(to, _text(st), str(st.get("flag", "")), bool(st.get("added", false)))
	if ff:
		PS.send_input(to)
		return
	_open("draft", to)
	PS.mark_read(to)
	story._ui_shot("phone_draft", 0.6)
	await _chosen


func _story_view(id: String, fresh: bool) -> void:
	_open("view", id)
	PS.mark_read(id)
	if fresh:
		_set_fresh(PS.history(id).size() - _sent_n, 0.35, "phone_send")
	story._ui_shot("phone", 0.6)
	await _chosen


# ======================================================================= 开关、软键
func _open(m: String, id: String) -> void:
	mode = m
	cur = id
	_age = 0.0
	_scroll = 0.0
	_flash = 0.0
	_choosing = false
	_fresh = -1
	_layout_key = ""
	visible = true
	_set_keys()
	if m != "notify":
		_sfx("phone_open", -8.0)
	queue_redraw()


func _set_keys() -> void:
	_keys.clear()
	var inp := PS.input_of(cur)
	match mode:
		"msg":
			if not inp.is_empty() and str(inp.get("kind", "")) == "reply" and str(inp.get("msg", "")) == _msg_id:
				_keys.append({"id": "reply", "label": "reply"})
			_keys.append({"id": "later", "label": "later" if _keys.size() > 0 else "fold"})   # 没有 reply：只有「收起」
		"draft":
			_keys.append({"id": "send", "label": "send"})
			_keys.append({"id": "not_now", "label": "not_now"})
		"view":
			_keys.append({"id": "close", "label": "close"})
		"browse":
			if not inp.is_empty():
				var k := "reply" if str(inp.get("kind", "")) == "reply" else "send"
				_keys.append({"id": k, "label": k})
			_keys.append({"id": "close", "label": "close"})
	_sel = 0


func _set_sel(i: int) -> void:
	i = clampi(i, 0, maxi(0, _keys.size() - 1))
	if i == _sel:
		return
	_sel = i
	_sfx("ui_click", -14.0, 1.35)


func _choose(i: int) -> void:
	if _choosing or _keys.is_empty():
		return
	_choosing = true
	_sel = clampi(i, 0, _keys.size() - 1)
	_flash = 0.3
	_sfx("tick", -5.0)
	var kid := str(_keys[_sel]["id"])
	if str(_keys[_sel]["label"]) == "fold":
		PS.mark_read(cur)             # 没有可回的：「收起」= 看过了
	var hold := 0.3
	if kid in ["reply", "send"]:
		var n_in := PS.split(PS.input_of(cur)).size()
		if PS.send_input(cur):
			_set_fresh(PS.history(cur).size() - n_in, 0.2, "phone_send")
			_scroll = 0.0
			hold = 0.9
	var m := mode
	await _hold(hold)
	_choosing = false
	if m == "browse":
		if mode == "browse":
			if kid == "close":
				close()
			else:
				_set_keys()
		return
	close()
	_chosen.emit(_sel)                # 剧情模式：不管中途怎样都要放剧情走


func _notify_pick(i: int) -> void:
	if _choosing:
		return
	_choosing = true
	_sfx("tick" if i == 0 else "ui_click", -6.0)
	close()
	_chosen.emit(i)


func _hold(sec: float) -> void:
	if _auto_on():
		sec = minf(sec, 0.5)
	var t := 0.0
	while t < sec and mode != "":
		await get_tree().process_frame
		t += get_process_delta_time()


func _auto_on() -> bool:
	return story != null and (str(story.auto) != "" or float(story.dlg.auto_delay) >= 0.0)


# ======================================================================= 每帧
func _process(delta: float) -> void:
	if mode == "":
		return
	_age += delta
	_flash = maxf(0.0, _flash - delta)
	if _fresh >= 0:
		_fresh_clock += delta
		var k := _fresh_arrived()
		if k > _fresh_played:
			_fresh_played = k
			if _fresh_sfx != "":
				_sfx(_fresh_sfx, -4.0)
		if k >= _fresh_end:
			_fresh = -1
	if mode == "browse" and not _own_lock and not _bag_visible():
		close()                       # 背包被别的东西关了：一起收
		return
	_auto_tick()
	if mode == "":
		return
	if mode != "notify":
		_relayout()
	queue_redraw()
	_chat.queue_redraw()


func _auto_tick() -> void:
	if not _auto_on() or _choosing or mode == "browse":
		return
	var d := maxf(0.0, float(story.dlg.auto_delay))
	match mode:
		"notify":
			if _age > maxf(0.8, d):
				_notify_pick(0)
		"msg", "draft":
			if _fresh >= 0:
				return                # 几条还没「到」齐
			var ai := _keys.size() - 1 if str(story.auto) == "full" else 0
			if _age > 0.5:
				_sel = clampi(ai, 0, _keys.size() - 1)
			if _age > maxf(1.0, d + 0.3):
				_choose(ai)
		"view":
			if _age > maxf(1.0, d + 0.4):
				_choose(0)


# ======================================================================= 输入
func _input(e: InputEvent) -> void:
	if mode == "" or story == null:
		return
	if e is InputEventKey and (e as InputEventKey).keycode == KEY_F8:
		return
	if str(story.auto) != "":
		get_viewport().set_input_as_handled()     # 自动玩不吃真的按键（和关卡一样）
		return
	if not (e is InputEventKey or e is InputEventMouse):
		return
	get_viewport().set_input_as_handled()
	if e is InputEventMouseMotion:
		var ki := _key_at(e.position)
		if ki >= 0 and mode != "notify" and not _choosing:
			_set_sel(ki)
		return
	if e is InputEventMouseButton:
		var mb := e as InputEventMouseButton
		if not mb.pressed:
			return
		match mb.button_index:
			MOUSE_BUTTON_WHEEL_UP:
				_scroll_by(1)
			MOUSE_BUTTON_WHEEL_DOWN:
				_scroll_by(-1)
			MOUSE_BUTTON_LEFT:
				_click(mb.position)
		return
	var ke := e as InputEventKey
	if not ke.pressed:
		return
	var k: int = ke.keycode
	var confirm := k in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_Z]
	if ke.echo and not k in [KEY_UP, KEY_DOWN, KEY_W, KEY_S, KEY_PAGEUP, KEY_PAGEDOWN]:
		return
	if mode == "notify":
		if confirm:
			_notify_pick(0)
		elif k == KEY_ESCAPE:
			_notify_pick(1)
		return
	if _choosing:
		return
	if k == KEY_PAGEUP:
		_scroll_by(4)
	elif k == KEY_PAGEDOWN:
		_scroll_by(-4)
	elif k in [KEY_LEFT, KEY_A]:
		_set_sel(0)
	elif k in [KEY_RIGHT, KEY_D]:
		_set_sel(_keys.size() - 1)
	elif k in [KEY_UP, KEY_W, KEY_DOWN, KEY_S]:
		var up := k in [KEY_UP, KEY_W]
		if mode == "browse":
			_step_contact(-1 if up else 1)
		else:
			_scroll_by(1 if up else -1)
	elif confirm:
		_choose(_sel)
	elif k == KEY_ESCAPE:
		if mode == "browse":
			close()
		else:
			_choose(_keys.size() - 1)            # 稍后看 / 暂时不发 / 关闭
	elif k in [KEY_TAB, KEY_B, KEY_I] and mode == "browse":
		close()


func _click(p: Vector2) -> void:
	if mode == "notify":
		_notify_pick(0)
		return
	if _choosing:
		return
	var ki := _key_at(p)
	if ki >= 0:
		_choose(ki)
		return
	match mode:
		"view":
			_choose(0)
		"browse":
			if not FRAME.has_point(p):
				close()
				return
			var ids := PS.visible_ids()
			for i in ids.size():
				if _row_rect(i).has_point(p):
					_select_contact(ids[i])
					return


func _step_contact(d: int) -> void:
	var ids := PS.visible_ids()
	if ids.is_empty():
		return
	var i := ids.find(cur)
	i = clampi(i + d, 0, ids.size() - 1) if i >= 0 else 0
	_select_contact(ids[i])


func _select_contact(id: String) -> void:
	if id == cur:
		return
	cur = id
	_scroll = 0.0
	_layout_key = ""
	PS.mark_read(id)
	_set_keys()
	_sfx("ui_click", -14.0, 1.35)


func _scroll_by(n: int) -> void:
	var area := _chat_rect().size.y
	_scroll = clampf(_scroll + n * (_lh + 1.0), 0.0, maxf(0.0, _content_h - area + 6.0))


# ======================================================================= 排版
func _row_rect(i: int) -> Rect2:
	return Rect2(SCR.position.x, SCR.position.y + 2.0 + i * ROW_H, LIST_W, ROW_H)


func _chat_x() -> float:
	return SCR.position.x + LIST_W + 1.0


func _keybar_y() -> float:
	return SCR.end.y - KEY_H


func _input_text() -> String:
	var inp := PS.input_of(cur)
	return story.txt(inp) if not inp.is_empty() else ""


func _input_lines() -> Array:
	var s := _input_text()
	if s == "":
		return [""]
	var rows := _wrap(s, SCR.end.x - _chat_x() - 16.0)
	return rows.slice(maxi(0, rows.size() - 3))


func _input_rect() -> Rect2:
	var n := _input_lines().size()
	var h := n * _lh + 4.0
	var x := _chat_x() + 4.0
	return Rect2(x, _keybar_y() - 4.0 - h, SCR.end.x - 4.0 - x, h)


func _chat_rect() -> Rect2:
	var top := SCR.position.y + HEAD_H + 1.0
	return Rect2(_chat_x(), top, SCR.end.x - _chat_x(), _input_rect().position.y - 3.0 - top)


func _key_rect(i: int) -> Rect2:
	if i < 0 or i >= _keys.size():
		return Rect2()
	var w := _sw(t(str(_keys[i]["label"]))) + 10.0
	var y := _keybar_y()
	var right := i == _keys.size() - 1
	var x := SCR.end.x - 3.0 - w if right else SCR.position.x + 3.0
	return Rect2(x, y + 1.0, w, KEY_H - 2.0)


func _key_at(p: Vector2) -> int:
	for i in _keys.size():
		if _key_rect(i).grow(2.0).has_point(p):
			return i
	return -1


func _relayout() -> void:
	var r := _chat_rect()
	_chat.position = r.position
	_chat.size = r.size
	_chat.modulate.a = _screen_alpha()
	var key := "%s|%d|%s|%d|%s" % [cur, PS.version(), I18n.lang, int(r.size.x), str(story.mark_added)]
	if key == _layout_key:
		return
	_layout_key = key
	_layout.clear()
	var y := 4.0
	var last_date := ""
	var last_from := ""
	var hist := PS.history(cur)
	for i in hist.size():
		var m: Dictionary = hist[i]
		var dt := str(m.get("date", ""))
		if dt != "" and dt != last_date:
			if i > 0:
				y += 3.0
			_layout.append({"kind": "date", "y": y, "h": _fh, "text": dt if I18n.is_zh() else _en_date(dt)})
			y += _fh + 3.0
			last_from = ""
		if dt != "":
			last_date = dt
		var from := str(m.get("from", ""))
		if last_from != "" and from != last_from:
			y += 3.0
		last_from = from
		var lines := _wrap(story.txt(m), BUBBLE_MAX)
		var h := lines.size() * _lh + 3.0
		var w := 0.0
		for l in lines:
			w = maxf(w, _sw(str(l)))
		_layout.append({"kind": "msg", "y": y, "h": h, "w": w + 8.0, "lines": lines, "me": from == PS.CHEN,
			"added": bool(m.get("added", false)) and bool(story.mark_added), "idx": i})
		y += h + 3.0
	_content_h = y + 1.0
	_scroll = clampf(_scroll, 0.0, maxf(0.0, _content_h - r.size.y + 6.0))


## 屏幕打开：暗一格（100ms）、半亮一格、全亮
func _screen_alpha() -> float:
	if _age < STEP:
		return 0.0
	if _age < STEP * 2.0:
		return 0.55
	return 1.0


# ======================================================================= 画
func _draw() -> void:
	if mode == "":
		return
	if mode == "notify":
		_draw_card()
		return
	draw_rect(Rect2(0, 0, 480, 270), C_DIM)
	_draw_frame()
	var a := _screen_alpha()
	if a <= 0.0:
		return
	var f := UITheme.font()
	# 左：联系人
	var ids := PS.visible_ids()
	var story_mode := mode != "browse"
	for i in ids.size():
		var id: String = ids[i]
		var r := _row_rect(i)
		if r.end.y > _keybar_y() - 1.0:
			break
		var on := id == cur
		if on:
			draw_rect(r, _a(C_ROW_SEL, a))
			draw_rect(Rect2(r.position.x, r.position.y + 3.0, 2.0, ROW_H - 6.0), _a(UITheme.ACCENT if mode == "browse" else UITheme.TEXT_DIM, a))
		var c := UITheme.TEXT if on else UITheme.TEXT_DIM
		if story_mode and not on:
			c = Color(c, 0.55)
		var nm := _fit(story.txt(PS.name_of(id)), LIST_W - 18.0)
		draw_string(f, Vector2(r.position.x + 6.0, r.position.y + _ty(ROW_H)), nm, HORIZONTAL_ALIGNMENT_LEFT, -1, FS, _a(c, a))
		if PS.unread(id) and not PS.never_unread(id):
			var dp := Vector2(r.end.x - 8.0, r.position.y + floorf(ROW_H / 2.0) - 1.0)
			if _tex_unread != null:
				draw_texture(_tex_unread, dp, Color(1, 1, 1, a))
			else:
				draw_rect(Rect2(dp, Vector2(3, 3)), _a(UITheme.WARM, a))
	if ids.is_empty():
		draw_string(f, Vector2(SCR.position.x + 6.0, SCR.position.y + 2.0 + _ty(ROW_H)), _fit(t("no_contacts"), LIST_W - 8.0),
			HORIZONTAL_ALIGNMENT_LEFT, -1, FS, _a(UITheme.TEXT_DIM, a))
	draw_rect(Rect2(SCR.position.x + LIST_W, SCR.position.y, 1.0, _keybar_y() - SCR.position.y - 1.0), _a(C_LINE, a))
	# 右上：名字
	var cx := _chat_x()
	if cur != "":
		draw_string(f, Vector2(cx + 6.0, SCR.position.y + _ty(HEAD_H)), _fit(story.txt(PS.name_of(cur)), SCR.end.x - cx - 12.0),
			HORIZONTAL_ALIGNMENT_LEFT, -1, FS, _a(UITheme.TEXT, a))
	draw_rect(Rect2(cx, SCR.position.y + HEAD_H, SCR.end.x - cx, 1.0), _a(C_LINE, a))
	# 输入栏
	var ir := _input_rect()
	if _nine.has("phone_input"):
		draw_style_box(_nine["phone_input"], ir)
	else:
		draw_rect(ir, _a(C_INPUT, a))
		_edge(ir, _a(C_LINE, a))
	var lines := _input_lines()
	var inp := PS.input_of(cur)
	var ic := ADDED_C if bool(inp.get("added", false)) and bool(story.mark_added) else SCR_TEXT
	for k in lines.size():
		draw_string(f, Vector2(ir.position.x + 4.0, ir.position.y + 2.0 + k * _lh + _asc), str(lines[k]),
			HORIZONTAL_ALIGNMENT_LEFT, -1, FS, _a(ic, a))
	if not inp.is_empty() and fmod(_age, 1.0) < 0.55:
		var lw := _sw(str(lines[lines.size() - 1]))
		draw_rect(Rect2(ir.position.x + 5.0 + lw, ir.position.y + 3.0 + (lines.size() - 1) * _lh, 1.0, _fh - 2.0), _a(UITheme.TEXT_DIM, a))
	# 底下：软键
	draw_rect(Rect2(SCR.position.x, _keybar_y() - 1.0, SCR.size.x, 1.0), _a(C_LINE, a))
	for i in _keys.size():
		var kr := _key_rect(i)
		var on := i == _sel
		var fl := on and _flash > 0.0 and fmod(_flash, 0.1) > 0.05
		var art := _nine.has("phone_button") and _nine.has("phone_button_hover")
		if art:
			draw_style_box(_nine["phone_button_hover" if on else "phone_button"], kr)
			if fl:
				draw_rect(kr.grow(-1.0), Color(1, 1, 1, 0.3))
		elif fl:
			draw_rect(kr, _a(Color(UITheme.ACCENT, 0.85), a))
		elif on:
			draw_rect(kr, _a(C_KEY_SEL, a))
			_edge(kr, _a(UITheme.ACCENT, a))
		var kc := Color.WHITE if fl else ((BTN_TEXT if art else UITheme.TEXT) if on else UITheme.TEXT_DIM)
		var kl := t(str(_keys[i]["label"]))
		draw_string(f, Vector2(kr.position.x + 5.0, kr.position.y + _ty(kr.size.y)), kl, HORIZONTAL_ALIGNMENT_LEFT, -1, FS, _a(kc, a))
		if on and not fl:
			draw_rect(Rect2(kr.position.x + 5.0, kr.end.y - 2.0, _sw(kl), 1.0), _a(UITheme.ACCENT, a))   # 选中：字下面一道
	# 上下还有字：聊天右边两个小三角
	var cr := _chat_rect()
	var max_s := maxf(0.0, _content_h - cr.size.y + 6.0)
	if max_s > 0.0:
		if _scroll < max_s:
			_tri(Vector2(cr.end.x - 7.0, cr.position.y + 2.0), true, _a(UITheme.TEXT_DIM, a))
		if _scroll > 0.0:
			_tri(Vector2(cr.end.x - 7.0, cr.end.y - 5.0), false, _a(UITheme.TEXT_DIM, a))


func _draw_frame() -> void:
	if _nine.has("phone_frame"):
		draw_style_box(_nine["phone_frame"], FRAME)     # 美术的外框：机身 + 中间的暗屏都在里面
		draw_rect(Rect2(FRAME.position.x + 8.0, FRAME.position.y + 2.0, 2.0, 2.0), UITheme.WARM if PS.any_unread() else LED_OFF)
		return
	else:
		var r := FRAME
		draw_rect(Rect2(r.position.x + 1.0, r.position.y, r.size.x - 2.0, r.size.y), C_CASE)
		draw_rect(Rect2(r.position.x, r.position.y + 1.0, r.size.x, r.size.y - 2.0), C_CASE)
		_edge(r, C_CASE_EDGE)
		draw_rect(Rect2(r.position.x + 2.0, r.position.y + 1.0, r.size.x - 4.0, 1.0), C_CASE_HI)
		# 听筒的缝、左上角的小灯（有未读 = 暖色）
		draw_rect(Rect2(r.get_center().x - 10.0, r.position.y + 2.0, 20.0, 2.0), C_SLOT)
		draw_rect(Rect2(r.position.x + 8.0, r.position.y + 2.0, 2.0, 2.0), UITheme.WARM if PS.any_unread() else LED_OFF)
		draw_rect(SCR.grow(1.0), C_RECESS)
	draw_rect(SCR, C_SCREEN)


func _draw_chat() -> void:
	if mode == "" or mode == "notify":
		return
	var f := UITheme.font()
	var w := _chat.size.x
	var area := _chat.size.y
	var y0 := 0.0
	if _content_h > area:
		y0 = area - _content_h + _scroll
	for e in _layout:
		var y: float = y0 + float(e["y"])
		var h: float = e["h"]
		if y + h < 0.0 or y > area:
			continue
		if e["kind"] == "date":
			var s := str(e["text"])
			var sw := _sw(s)
			var x := roundf((w - sw) / 2.0)
			var ly := roundf(y + _fh / 2.0)
			_chat.draw_rect(Rect2(x - 22.0, ly, 16.0, 1.0), C_LINE)
			_chat.draw_rect(Rect2(x + sw + 6.0, ly, 16.0, 1.0), C_LINE)
			_chat.draw_string(f, Vector2(x, y + _asc), s, HORIZONTAL_ALIGNMENT_LEFT, -1, FS, Color(UITheme.TEXT_DIM, 0.8))
			continue
		if _fresh >= 0 and int(e["idx"]) >= _fresh and int(e["idx"]) > _fresh_arrived():
			continue                  # 还没「到」
		var me: bool = e["me"]
		var bw: float = e["w"]
		var bx := w - 8.0 - bw if me else 5.0
		var br := Rect2(roundf(bx), roundf(y), bw, h)
		var bn := "phone_bubble_out" if me else "phone_bubble_in"
		if _nine.has(bn):
			_chat.draw_style_box(_nine[bn], br)
		else:
			var bg := C_ME if me else C_THEM
			var ed := C_ME_EDGE if me else C_THEM_EDGE
			_chat.draw_rect(Rect2(br.position.x + 1.0, br.position.y, br.size.x - 2.0, br.size.y), bg)
			_chat.draw_rect(Rect2(br.position.x, br.position.y + 1.0, br.size.x, br.size.y - 2.0), bg)
			_edge_on(_chat, br, ed)
		var tc := ADDED_C if e["added"] else (Color("#e3e6dc") if me else SCR_TEXT)
		var lines: Array = e["lines"]
		for k in lines.size():
			_chat.draw_string(f, Vector2(br.position.x + 4.0, br.position.y + 2.0 + k * _lh + _asc), str(lines[k]),
				HORIZONTAL_ALIGNMENT_LEFT, -1, FS, tc)


## 通知卡：右上角（黑边在就往下挪），三格滑进来、再左右抖两下
func _draw_card() -> void:
	var f := UITheme.font()
	var nm := _fit(story.txt(PS.name_of(cur)), 150.0)
	var sub := t("new_msg")
	var w := 28.0 + maxf(_sw(nm), _sw(sub)) + 10.0
	var h := _fh * 2.0 + 8.0
	var steps := [32.0, 14.0, 4.0]
	var k := int(_age / STEP)
	var dx: float = steps[k] if k < steps.size() else 0.0
	if k >= 3 and k < 7:
		dx = 1.0 if k % 2 == 0 else -1.0       # 嗡嗡两下
	var top: float = float(story.dlg.top_limit) + 2.0
	var r := Rect2(roundf(472.0 - w + dx), roundf(top), w, h)
	if _nine.has("phone_notify"):
		draw_style_box(_nine["phone_notify"], r)
	else:
		draw_rect(Rect2(r.position.x + 1.0, r.position.y, r.size.x - 2.0, r.size.y), C_CARD)
		draw_rect(Rect2(r.position.x, r.position.y + 1.0, r.size.x, r.size.y - 2.0), C_CARD)
		_edge(r, C_CARD_EDGE)
	var ip := Vector2(r.position.x + 8.0, r.position.y + roundf((h - 12.0) / 2.0))
	if _tex_icon != null:
		var isz := _tex_icon.get_size()
		var sc := maxf(1.0, floorf(16.0 / maxf(isz.x, isz.y)))
		var ds := isz * sc
		draw_texture_rect(_tex_icon, Rect2((ip + Vector2(4, 6) - ds / 2.0).round(), ds), false)
	else:
		# 8×12 的小机子：壳、亮着的屏、一个键
		draw_rect(Rect2(ip, Vector2(8, 12)), C_CASE_EDGE)
		draw_rect(Rect2(ip + Vector2(1, 1), Vector2(6, 10)), C_CASE)
		draw_rect(Rect2(ip + Vector2(2, 2), Vector2(4, 4)), Color("#5f8f78") if fmod(_age, 0.8) < 0.4 else Color("#3f6656"))
		draw_rect(Rect2(ip + Vector2(3, 8), Vector2(2, 1)), C_CASE_EDGE)
	draw_string(f, Vector2(r.position.x + 22.0, r.position.y + 3.0 + _asc), nm, HORIZONTAL_ALIGNMENT_LEFT, -1, FS, UITheme.TEXT)
	draw_string(f, Vector2(r.position.x + 22.0, r.position.y + 5.0 + _fh + _asc), sub, HORIZONTAL_ALIGNMENT_LEFT, -1, FS, UITheme.TEXT_DIM)
	if fmod(_age, 1.0) < 0.6 and _age > 0.4:
		draw_rect(Rect2(r.end.x - 7.0, r.end.y - 4.0, 3.0, 1.0), UITheme.TEXT_DIM)


# ----------------------------------------------------------------------- 画的小工具
func _a(c: Color, a: float) -> Color:
	return Color(c, c.a * a)


## 1 像素的边，四个角空着（圆一点）
func _edge(r: Rect2, c: Color) -> void:
	_edge_on(self, r, c)


func _edge_on(ci: CanvasItem, r: Rect2, c: Color) -> void:
	ci.draw_rect(Rect2(r.position.x + 1.0, r.position.y, r.size.x - 2.0, 1.0), c)
	ci.draw_rect(Rect2(r.position.x + 1.0, r.end.y - 1.0, r.size.x - 2.0, 1.0), c)
	ci.draw_rect(Rect2(r.position.x, r.position.y + 1.0, 1.0, r.size.y - 2.0), c)
	ci.draw_rect(Rect2(r.end.x - 1.0, r.position.y + 1.0, 1.0, r.size.y - 2.0), c)


func _tri(p: Vector2, up: bool, c: Color) -> void:
	for r in 3:
		var w := 1 + 2 * (r if up else 2 - r)
		draw_rect(Rect2(p.x + (5 - w) / 2, p.y + r, w, 1), c)


## 文字在高 h 的格子里竖着居中时的基线
func _ty(h: float) -> float:
	return roundf((h - _fh) / 2.0) + _asc


func _sw(s: String) -> float:
	return UITheme.font().get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, FS).x


func _fit(s: String, w: float) -> String:
	if _sw(s) <= w:
		return s
	while s.length() > 1 and _sw(s + "…") > w:
		s = s.substr(0, s.length() - 1)
	return s + "…"


## 按宽度换行（和 text_page.gd 一样：中文按字、英文尽量在空格处断、标点不放行首）
func _wrap(s: String, width: float) -> Array:
	var out: Array = []
	for para in s.split("\n"):
		var cur_l := ""
		var i := 0
		while i < para.length():
			var ch := para[i]
			if _sw(cur_l + ch) <= width or cur_l == "":
				cur_l += ch
				i += 1
				continue
			var cut := cur_l.length()
			if ch.unicode_at(0) < 0x2E80 and ch != " ":
				var sp := cur_l.rfind(" ")
				if sp > 0:
					cut = sp + 1
			if ch in ["，", "。", "、", "；", "：", "？", "！", "」", "』", "）", "…"] and cut > 1:
				cut -= 1
			out.append(cur_l.substr(0, cut).strip_edges(false, true))
			cur_l = cur_l.substr(cut).strip_edges(true, false)
		out.append(cur_l)
	return out


# ======================================================================= 杂项
func _sfx(name: String, db := 0.0, pitch := 1.0) -> void:
	if story == null or story.ff:
		return
	var p: String = story._sfx_path(name)
	if p == "":
		return                        # 美术还没做的音效：静音不崩
	var a := AudioStreamPlayer.new()
	a.stream = load(p)
	a.bus = "SFX"
	a.volume_db = db
	a.pitch_scale = pitch
	add_child(a)
	a.play()
	a.finished.connect(a.queue_free)


func _bag_visible() -> bool:
	var b = level.get("_bag") if level != null else null
	return b is CanvasItem and (b as CanvasItem).visible


func _level_playing() -> bool:
	if level == null or not level.has_method("free_play"):
		return true
	var st = level.get("state")
	return st == null or int(st) == int(level.S.PLAY)


# ======================================================================= F8
## 「打开通讯器」：能开背包就先开背包（关掉通讯器回到背包），开不了就单独开
func dev_open() -> void:
	if story.busy or mode != "":
		return
	if not _bag_visible() and level != null and level.has_method("_toggle_bag") and _level_playing() and not Inventory.owned.is_empty():
		level.call("_toggle_bag")
	open_browse()


## 「模拟一条消息」：临时塞一段只有一条 phone_msg 的 scene 播一遍（走真的剧情流程：锁晨、通知、回复 / 稍后看）
func dev_simulate() -> void:
	if story.busy or mode != "":
		return
	var from := ""
	for id in PS.contact_order():
		if not PS.never_unread(id):
			from = id
			break
	if from == "":
		from = "dev"
		PS.add_contact(from, {"zh": "测试", "en": "Test"})
	_dev_n += 1
	var sid := "_dev_phone_msg"
	var scenes: Dictionary = story.scenes
	scenes[sid] = [{"do": "phone_msg", "id": "dev_sim_%d_%d" % [Time.get_ticks_msec(), _dev_n], "from": from,
		"zh": "（测试消息 %d）右边接头再听一遍，响就停稳了拧。" % _dev_n, "en": "(Test message %d) Listen to the right joint again." % _dev_n,
		"reply": {"zh": "（测试回复）好，这就去。", "en": "(Test reply) On it."}}]
	await story.play(sid)
	scenes.erase(sid)
	story.played.erase(sid)


## 聊天里的日期：phone.json 写的是「3月14日」，英文界面显示成「Mar 14」（不是这个格式就原样）
static func _en_date(dt: String) -> String:
	var r := RegEx.create_from_string("^(\\d{1,2})月(\\d{1,2})日$")
	var m := r.search(dt)
	if m == null:
		return dt
	var mo := int(m.get_string(1))
	const MONTHS := ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
	if mo < 1 or mo > 12:
		return dt
	return "%s %d" % [MONTHS[mo - 1], int(m.get_string(2))]


# ======================================================================= 检查剧本（--story_check）
## from / to / contact 指向存在的联系人（phone.json 里有，或者剧本里 phone_add 过）、phone_msg 的 id 不重复、字段齐
static func validate(scenes: Dictionary) -> Array[String]:
	var out: Array[String] = []
	if PS.base_contacts().is_empty():
		PS.load_base()
	var base: Dictionary = PS.base_contacts()
	if not PS.has_data():
		out.append("info: 没有 data/phone.json（通讯器没有联系人）")
	var contacts := {}
	for id in base:
		contacts[str(id)] = true
		var c = base[id]
		if not c is Dictionary:
			out.append("phone.json：联系人 %s 不是对象" % id)
			continue
		var nm = c.get("name", {})
		if not nm is Dictionary or str(nm.get("zh", "")) == "":
			out.append("phone.json：联系人 %s 没有 name.zh" % id)
		var hist = c.get("history", [])
		if not hist is Array:
			out.append("phone.json：联系人 %s 的 history 不是数组" % id)
			continue
		for m in hist:
			if not m is Dictionary:
				out.append("phone.json：%s 的记录里有一条不是对象" % id)
				continue
			var fr := str(m.get("from", ""))
			if fr != PS.CHEN and fr != str(id):
				out.append("phone.json：%s 的记录 from 只能是 chen / %s（%s）" % [id, id, fr])
			if str(m.get("zh", "")) == "":
				out.append("phone.json：%s 的记录有一条没有 zh" % id)
		if PS.never_unread(str(id)) and not hist.is_empty() and str((hist[hist.size() - 1] as Dictionary).get("from", "")) != PS.CHEN:
			out.append("info: phone.json：%s（失联的朋友）最后一条不是晨发的" % id)
	var uses := false
	for sid in scenes:
		if not scenes[sid] is Array:
			continue
		for st in scenes[sid]:
			if st is Dictionary and str(st.get("do", "")) == "phone_add":
				contacts[str(st.get("id", ""))] = true
	var msg_ids := {}
	for sid in scenes:
		if not scenes[sid] is Array:
			continue
		for st in scenes[sid]:
			if not st is Dictionary:
				continue
			var d := str(st.get("do", ""))
			if not d.begins_with("phone_"):
				continue
			uses = true
			match d:
				"phone_add":
					if str(st.get("id", "")) == "":
						out.append("scene %s：phone_add 没有 id" % sid)
				"phone_msg":
					var mid := str(st.get("id", ""))
					if mid == "":
						out.append("scene %s：phone_msg 没有 id（同一条只触发一次靠它）" % sid)
					elif msg_ids.has(mid):
						out.append("phone_msg id 重复：%s（scene %s 和 %s）" % [mid, msg_ids[mid], sid])
					else:
						msg_ids[mid] = sid
					var fr := str(st.get("from", ""))
					if fr == PS.CHEN or not contacts.has(fr):
						out.append("scene %s：phone_msg %s 的 from 不是联系人：%s" % [sid, mid, fr])
					if str(st.get("zh", "")) == "":
						out.append("scene %s：phone_msg %s 没有 zh" % [sid, mid])
					var rp = st.get("reply", null)
					if rp != null and (not rp is Dictionary or str(rp.get("zh", "")) == ""):
						out.append("scene %s：phone_msg %s 的 reply 要是 {zh, en}" % [sid, mid])
				"phone_send", "phone_draft":
					var to := str(st.get("to", ""))
					if not contacts.has(to):
						out.append("scene %s：%s 的 to 不是联系人：%s" % [sid, d, to])
					if str(st.get("zh", "")) == "":
						out.append("scene %s：%s 没有 zh" % [sid, d])
					if d == "phone_draft" and str(st.get("flag", "")) == "":
						out.append("info: scene %s：phone_draft 没有 flag（发没发剧本读不到）" % sid)
				"phone_open":
					var c2 := str(st.get("contact", st.get("id", "")))
					if not contacts.has(c2):
						out.append("scene %s：phone_open 的 contact 不是联系人：%s" % [sid, c2])
				_:
					out.append("scene %s：不认识的通讯器步骤 %s" % [sid, d])
	# 跨章节：fired 是全局的，同一个 id 出现在两份剧本里，后面那条永远弹不出来
	var seen := {}
	var dir := DirAccess.open("res://data")
	if dir != null:
		for fn in dir.get_files():
			if not (fn.begins_with("story_") and fn.ends_with(".json")) or fn == "story_forest_sample.json":
				continue
			var d = JSON.parse_string(FileAccess.get_file_as_string("res://data/" + fn))
			if not d is Dictionary or not d.get("scenes", null) is Dictionary:
				continue
			for sid in d["scenes"]:
				if not d["scenes"][sid] is Array:
					continue
				for st in d["scenes"][sid]:
					if st is Dictionary and str(st.get("do", "")) == "phone_msg" and str(st.get("id", "")) != "":
						var mid2 := str(st["id"])
						if seen.has(mid2) and seen[mid2] != fn:
							out.append("phone_msg id 跨剧本重复：%s（%s 和 %s）" % [mid2, seen[mid2], fn])
						seen[mid2] = fn
	if uses:
		var miss: Array = []
		for s in ["phone_buzz", "phone_send", "phone_open"]:
			var found := false
			for ext in [".wav", ".ogg", ".mp3"]:
				if ResourceLoader.exists("res://audio/sfx/" + s + ext):
					found = true
			if not found:
				miss.append(s)
		if not miss.is_empty():
			out.append("info: 通讯器音效还没有（静音）：" + ", ".join(miss))
	return out
