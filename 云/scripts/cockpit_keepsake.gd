extends Control
## 剧本步骤 keepsake_choice（往转化装置里放一件纪念品）：
##   {"do": "keepsake_choice", "id": "flight1_choice", "items": ["blue_stone", "commute_card"], "route": true,
##    "scenes": {"blue_stone": "burn_blue_stone", …}, "look": {"blue_stone": [台词步骤…]}, "put_back": [台词…], "route_look": [台词…]}
## 约定见 docs/phone_and_cockpit_contract.md。不标燃料值（还差多少只看左上角燃料表）、没有倒计时。
##   「放进去就拿不回来」由剧本在这一步之前用 narr 说（剧情姐原文要求系统提前说明），界面上不再重复写一遍。
##   转化装置打开（cockpit_converter 还关着就换成 idle），几件东西摆在它前面的小托板上（背包里有的那几件；一件都没有就全摆）。
##   选：←/→（A/D、↑/↓ 也行）或鼠标移上去；选中的亮一档、上下浮 1 像素、头顶写名字和小箭头。
##   点一件（E / 空格 / 回车 / Z / 鼠标单击）= 拿起来看：卡片上是图标、名字、描述（物品的 desc），晨说那件的 look 台词（第一次看才说），
##   下面两个按钮「放进去」/「先放回去」。「先放回去」= 晨说 put_back 的台词，回到挑的界面。route: true 时托板旁边还有「看看航线」：
##   航线卡（森林 → 河流星球，最后一截是虚线，不写数）、晨说 route_look 的台词、「回去」。Esc = 先放回去 / 回去。
##   确认「放进去」：卡片闪一下 + 确认音，关掉界面，goto scenes[那件]；选了哪件记进 StoryState 的物件状态（键 = 步骤 id）。
## 自动玩：main 直接放第一件；full 先看第一件、放回去、看航线，再放最后一件（两次自动玩各走一条分支）；
##   跳节拍：挑能通到目标 flag 的那件，瞬间完成。
## 多选版（终章燃料柜，"multi": true；docs/第三章计划.md 第三节）：
##   {"do": "keepsake_choice", "id": "final_fuel_a", "multi": true, "items": [...能烧的...], "scenes": {id: "burn_…"},
##    "look_scenes": {id: "look_…"}, "keep_scenes": {"music_box": "keep_music_box"}, "route": true, "route_from": {zh, en}, "route_to": {zh, en}, "then": ""}
##   托板上只摆背包里还有的；拿起来第一次看播 look_scenes 那一段（整段 scene 当台词播，不跳转）。「放进去」= 托板先淡掉，
##   播 scenes 那一段（里面自己 take / 设 burned_*），再按物品的 keepsake_burn 往燃料表里加（_fuel_step burn），那一格从托板上拿掉、重新排。
##   燃料够了（≥ 需要的量）就自己合上，返回 then（"" = 接着往下播）；不够就回到托板接着挑（不能不放就走：燃料柜这一段是必经的）。
##   「先放回去」：有 keep_scenes 的（音乐盒）播那一段（收回背包），没有就播 put_back。一进来燃料就够了 = 什么都不弹，直接返回。
##   航线卡：实线长短 = 现在燃料 / 需要（差的那截是虚线），两头的地名用 route_from / route_to。
##   跳节拍（ff）：按托板顺序一件件放，直到够；自动玩：一直「拿第一件、放进去」直到够（full 先看一件放回去、看一眼航线）。
## story_runner.gd 的 _cockpit_step 建它（挂在对话界面下，按键先到这里）：var scene = await play(runner, st)。

signal done(id: String)

const HINT_TEX := preload("res://art/level1/hint_arrow.png")
const BG := Color(0.02, 0.05, 0.04, 0.88)
const EDGE := Color(0.5, 0.6, 0.55, 0.45)
const TXT := {
	"put_in": ["Put it in", "放进去"],
	"put_back": ["Put it back for now", "先放回去"],
	"route": ["Check the route", "看看航线"],
	"back": ["Back", "回去"],
	"route_title": ["Route", "航线"],
	"from": ["Forest", "森林"],
	"to": ["River planet", "河流星球"],
	"keys": ["← → choose   E look", "← → 挑   E 拿起来看"],
}

var runner: Node
var cockpit: Node2D
var level: Node2D
var st: Dictionary
var items: Array[String] = []
var route := false
var _sel := 0                      # 托板上第几个（最后一个可能是「看看航线」）
var _mode := "pick"                # pick / card / route / busy（晨在说话、动画）
var _card: Panel
var _card_btns: Array[Label] = []
var _card_sel := 0
var _card_id := ""
var _seen := {}
var _slots: Array[Control] = []
var _name: Label
var _arrow: TextureRect
var _keys: Label
var _route_btn: Label
var _t := 0.0
var _auto_plan: Array = []         # 自动玩：接下来做什么 ["look:0", "back", "route", "in:1"…]
var _auto_t := 0.0
var _flash := {}                   # 控件 → 剩多久
var multi := false                 # 多选版（终章燃料柜）
var _burned: Array[String] = []    # 多选版：这一次放进去的


func play(r: Node, step: Dictionary) -> String:
	runner = r
	level = r.level
	cockpit = r.world.cockpit
	st = step
	route = bool(st.get("route", false))
	multi = bool(st.get("multi", false))
	var all: Array = st.get("items", [])
	for id in all:
		if Inventory.has(str(id)):
			items.append(str(id))
	if items.is_empty() and not multi:
		for id in all:
			items.append(str(id))
	var scenes: Dictionary = st.get("scenes", {})
	if items.is_empty():
		return str(st.get("then", "")) if multi else ""
	if multi:
		return await _play_multi(r)
	if r.ff:
		var pick := items[0]
		if r._ff_target != "":
			for id in items:
				if r._leads_to(str(scenes.get(id, "")), r._ff_target):
					pick = id
					break
		StoryState.set_prop(str(st.get("id", "keepsake_choice")), pick)
		return str(scenes.get(pick, ""))
	if cockpit != null and cockpit.state_of("cockpit_converter") in ["", "closed"]:
		r.world.set_prop("cockpit_converter", "idle")
	_build()
	if r.auto == "full":
		_auto_plan = ["look:0", "back", "route", "back", "look:%d" % (items.size() - 1), "in"]
		if not route:
			_auto_plan = ["look:0", "back", "look:%d" % (items.size() - 1), "in"]
	elif r.auto != "":
		_auto_plan = ["look:0", "in"]
	r._ui_shot("keepsake", 0.6)
	var chosen: String = await done
	StoryState.set_prop(str(st.get("id", "keepsake_choice")), chosen)
	print("COCKPIT keepsake_choice %s: %s" % [str(st.get("id", "")), chosen])
	return str(scenes.get(chosen, ""))


## 多选版：一直挑到燃料够；返回 then
func _play_multi(r: Node) -> String:
	var key := str(st.get("id", "keepsake_choice"))
	if not _enough():
		if r.ff:
			while not _enough() and not items.is_empty():
				await _burn(items[0])
		else:
			if cockpit != null and cockpit.state_of("cockpit_converter") in ["", "closed"]:
				r.world.set_prop("cockpit_converter", "idle")
			_build()
			if r.auto == "full":
				_auto_plan = ["look:0", "back"] + (["route", "back"] if route else [])
			r._ui_shot("keepsake", 0.6)
			await done
	StoryState.set_prop(key, ",".join(_burned))
	print("COCKPIT keepsake_choice %s (multi): burned=%s fuel=%d/%d" % [key, ",".join(_burned), StoryState.fuel(), StoryState.fuel_need()])
	return str(st.get("then", ""))


func _enough() -> bool:
	return not StoryState.fuel_on() or StoryState.fuel() >= StoryState.fuel_need()


## 多选版放进去一件：播 scenes 那一段（自己 take / 设 burned_*）、加燃料、从托板上拿掉
func _burn(id: String) -> void:
	var sc := str((st.get("scenes", {}) as Dictionary).get(id, "burn_" + id))
	await _lines(runner.scenes.get(sc, []))
	if Inventory.has(id):
		Inventory.remove(id)                  # scene 里没写 take 也别留在背包里
	runner._fuel_step({"burn": id})
	_burned.append(id)
	items.erase(id)


static func _tx(k: String) -> String:
	var row: Array = TXT[k]
	return row[1] if I18n.is_zh() else row[0]


func _label(text: String, c: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 14)
	l.add_theme_color_override("font_color", c)
	l.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.8))
	l.add_theme_constant_override("shadow_offset_x", 0)
	l.add_theme_constant_override("shadow_offset_y", 1)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


## 驾驶舱屏幕坐标 → 现在屏幕上的位置（镜头在驾驶舱正中，抖的时候跟着抖）
func _scr(p: Vector2) -> Vector2:
	return p + cockpit.ORIGIN - level.cam_left()


func _build() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme = UITheme.get_theme()
	var conv := _make_slots()
	_name = _label("", UITheme.TEXT)
	add_child(_name)
	_arrow = TextureRect.new()
	_arrow.texture = HINT_TEX
	_arrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_arrow)
	_keys = _label(_tx("keys"), UITheme.TEXT_DIM)
	_keys.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_keys.size = Vector2(480, 16)
	_keys.position = Vector2(0, 222)
	_keys.modulate.a = 0.7
	add_child(_keys)
	# 晨看着托板
	var chen: Node2D = runner.chen
	var tx: float = cockpit.ORIGIN.x + conv.position.x - 30.0 if cockpit != null else chen.position.x - 1.0
	if absf(tx - chen.position.x) > 2.0:
		chen._set_facing(1 if tx > chen.position.x else -1)
	_style()
	modulate.a = 0.0
	create_tween().tween_property(self, "modulate:a", 1.0, 0.3)


## 托板上的东西（转化装置左边一排）+「看看航线」；多选版放掉一件以后重新排。返回转化装置的矩形
func _make_slots() -> Rect2:
	for c in _slots:
		c.queue_free()
	_slots.clear()
	var conv := Rect2(380, 146, 56, 76)
	if cockpit != null and cockpit.objects.has("cockpit_converter"):
		conv = cockpit.objects["cockpit_converter"]["rect"]
	var n := items.size()
	var y: float = (cockpit.floor_y if cockpit != null else 222.0) - 42.0
	for i in n:
		var p := Panel.new()
		p.mouse_filter = Control.MOUSE_FILTER_IGNORE
		p.size = Vector2(20, 20)
		p.set_meta("home", Vector2(conv.position.x - 8.0 - (n - i) * 24.0, y))
		var tr := TextureRect.new()
		tr.texture = Inventory.icon(items[i])
		tr.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
		tr.set_anchors_preset(Control.PRESET_FULL_RECT)
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		p.add_child(tr)
		add_child(p)
		_slots.append(p)
	if route:
		_route_btn = _label("  " + _tx("route"), UITheme.TEXT_DIM)
		_route_btn.add_theme_stylebox_override("normal", UITheme.box(BG, EDGE, 1, Vector4(4, 1, 6, 1)))
		_route_btn.set_meta("home", Vector2(conv.position.x - 8.0 - n * 24.0 - 6.0, y + 24.0))
		add_child(_route_btn)
		_slots.append(_route_btn)
	_sel = clampi(_sel, 0, maxi(0, _slots.size() - 1))
	return conv


func _slot_count() -> int:
	return _slots.size()


func _is_route(i: int) -> bool:
	return route and i == _slots.size() - 1


func _style() -> void:
	for i in _slots.size():
		var on := i == _sel and _mode == "pick"
		var c: Control = _slots[i]
		if c is Panel:
			(c as Panel).add_theme_stylebox_override("panel", UITheme.box(Color(0.06, 0.1, 0.09, 0.85),
				UITheme.ACCENT if on else Color(0.3, 0.4, 0.35, 0.8), 1))
		else:
			var l: Label = c
			l.text = ("▸ " if on else "  ") + _tx("route")
			l.add_theme_color_override("font_color", UITheme.TEXT if on else UITheme.TEXT_DIM)
	if _mode == "pick" and not _is_route(_sel):
		var it := Inventory.item(items[_sel])
		_name.text = runner.txt(it.get("name", items[_sel]))
		_name.visible = true
		_arrow.visible = true
	else:
		_name.visible = false
		_arrow.visible = false
	_keys.visible = _mode == "pick"


func _set_sel(i: int) -> void:
	i = posmod(i, _slots.size())
	if i == _sel:
		return
	_sel = i
	_style()
	_sound("ui_click", -14.0, 1.35)


func _sound(n: String, db: float, pitch := 1.0) -> void:
	var f: Callable = runner.dlg.sfx
	if f.is_valid():
		f.call(n, db, pitch)


func _process(delta: float) -> void:
	_t += delta
	# 托板上的东西跟着镜头（机身抖的时候一起抖）、选中的上下浮 1 像素
	for i in _slots.size():
		var c: Control = _slots[i]
		var home: Vector2 = c.get_meta("home")
		var bob := -1.0 if (i == _sel and _mode == "pick" and fmod(_t, 0.8) < 0.4) else 0.0
		c.position = (_scr(home) + Vector2(0, bob)).round()
	if _name.visible:
		var p: Control = _slots[_sel]
		var w := UITheme.font().get_string_size(_name.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
		_name.position = Vector2(clampf(roundf(p.position.x + p.size.x / 2.0 - w / 2.0), 4.0, 476.0 - w), p.position.y - 30.0)
		_arrow.position = Vector2(roundf(p.position.x + p.size.x / 2.0 - HINT_TEX.get_width() / 2.0), p.position.y - 12.0 - (1.0 if fmod(_t, 1.2) < 0.6 else 0.0))
	for c in _flash.keys():
		_flash[c] = float(_flash[c]) - delta
		if is_instance_valid(c):
			(c as CanvasItem).modulate = Color(1.8, 1.8, 1.8) if float(_flash[c]) > 0.0 else Color.WHITE
		if float(_flash[c]) <= 0.0:
			_flash.erase(c)
	_auto_tick(delta)


# ======================================================================= 动作
func _choose_slot(i: int) -> void:
	if _mode != "pick":
		return
	_set_sel(i)
	_blink(_slots[i])
	_sound("tick", -6.0, 1.0)
	if _is_route(i):
		_open_route()
	else:
		_open_card(items[i])


func _blink(c: CanvasItem) -> void:
	_flash[c] = 0.2


func _card_panel(h: float) -> Panel:
	var p := Panel.new()
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_theme_stylebox_override("panel", UITheme.box(BG, EDGE, 1))
	p.position = Vector2(12, 52)
	p.size = Vector2(196, h)
	add_child(p)
	return p


func _open_card(id: String) -> void:
	_mode = "busy"
	_card_id = id
	_style()
	var it := Inventory.item(id)
	_card = _card_panel(180)
	var icon := TextureRect.new()
	icon.texture = Inventory.icon(id)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_SCALE
	var isz := icon.texture.get_size() * 2.0
	icon.size = isz
	icon.position = Vector2(10, 10)
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_card.add_child(icon)
	var nm := _label(runner.txt(it.get("name", id)), Color("#dcc39a"))
	nm.position = Vector2(18 + isz.x, 10 + isz.y / 2.0 - 9.0)
	_card.add_child(nm)
	var desc := _label(runner.txt(it.get("desc", "")), Color("#b9c9bf"))
	desc.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	desc.size = Vector2(176, 0)
	desc.custom_minimum_size = Vector2(176, 0)
	desc.position = Vector2(10, 18 + isz.y)
	desc.add_theme_constant_override("line_spacing", 1)
	_card.add_child(desc)
	_card.modulate.a = 0.0
	create_tween().tween_property(_card, "modulate:a", 1.0, 0.2)
	runner._ui_shot("keepsake_card", 0.5)
	if not _seen.has(id):
		_seen[id] = true
		await _lines(_look_lines(id))
	if not is_instance_valid(_card):
		return
	_buttons([_tx("put_in"), _tx("put_back")], 158)
	_mode = "card"


## 第一次拿起来看时晨说的：look 里的台词数组；多选版没有就播 look_scenes 那一段（默认 look_<id>）
func _look_lines(id: String) -> Array:
	var look: Dictionary = st.get("look", {}) if st.get("look", {}) is Dictionary else {}
	if look.has(id):
		return look[id]
	if multi:
		return runner.scenes.get(str((st.get("look_scenes", {}) as Dictionary).get(id, "look_" + id)), [])
	return []


func _open_route() -> void:
	_mode = "busy"
	_card_id = ""
	_style()
	_card = _card_panel(120)
	var title := _label(_tx("route_title"), Color("#dcc39a"))
	title.position = Vector2(10, 6)
	_card.add_child(title)
	var d := Control.new()
	d.mouse_filter = Control.MOUSE_FILTER_IGNORE
	d.position = Vector2(0, 30)
	d.size = Vector2(196, 50)
	d.draw.connect(_draw_route.bind(d))
	_card.add_child(d)
	var a := _label(runner.txt(st["route_from"]) if st.has("route_from") else _tx("from"), UITheme.TEXT_DIM)
	a.position = Vector2(10, 70)
	_card.add_child(a)
	var b := _label(runner.txt(st["route_to"]) if st.has("route_to") else _tx("to"), UITheme.TEXT_DIM)
	b.position = Vector2(186 - UITheme.font().get_string_size(b.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x, 70)
	_card.add_child(b)
	var nav_was := ""
	if cockpit != null:
		nav_was = cockpit.state_of("cockpit_nav")
		runner.world.set_prop("cockpit_nav", "zoom")
		var nx: float = cockpit.mx("cockpit_nav")
		runner.chen._set_facing(1 if nx > runner.chen.position.x else -1)
	await _lines(st.get("route_look", []))
	if cockpit != null and nav_was != "":
		runner.world.set_prop("cockpit_nav", nav_was)
	if not is_instance_valid(_card):
		return
	_buttons([_tx("back")], 92)
	_mode = "route"


## 航线：森林 ● —— 实线 —— 虚线（差的那一截）—— ○ 河流星球；不写数
func _draw_route(d: Control) -> void:
	var y := 22.0
	var x0 := 14.0
	var x1 := 180.0
	var k := 0.72
	if multi and StoryState.fuel_on() and StoryState.fuel_need() > 0:
		k = clampf(float(StoryState.fuel()) / float(StoryState.fuel_need()), 0.1, 1.0)   # 多选版：实线 = 现在燃料够飞多远
	var reach := x0 + (x1 - x0) * k
	var lc := Color("#7fc7a4")
	d.draw_rect(Rect2(x0 - 2, y - 2, 5, 5), lc)
	d.draw_rect(Rect2(x0, y, reach - x0, 1), lc)
	var x := reach + 2.0
	while x < x1 - 4.0:
		if fmod(_t * 6.0, 2.0) < 1.6:
			d.draw_rect(Rect2(x, y, 3, 1), Color(lc, 0.45))
		x += 6.0
	d.draw_rect(Rect2(x1 - 3, y - 3, 7, 7), Color("#8fb8c8"))
	d.draw_rect(Rect2(reach, y - 4, 1, 9), Color("#d9c9a0"))
	d.queue_redraw()


func _buttons(labels: Array, y: float) -> void:
	for l in _card_btns:
		l.queue_free()
	_card_btns.clear()
	var x := 10.0
	for s in labels:
		var l := _label("", UITheme.TEXT_DIM)
		l.set_meta("text", str(s))
		l.position = Vector2(x, y)
		_card.add_child(l)
		_card_btns.append(l)
		x += UITheme.font().get_string_size("▸ " + str(s), HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x + 18.0
	_card_sel = 0
	_style_btns()


func _style_btns() -> void:
	for i in _card_btns.size():
		var on := i == _card_sel
		var l := _card_btns[i]
		l.text = ("▸ " if on else "  ") + str(l.get_meta("text"))
		l.add_theme_color_override("font_color", UITheme.TEXT if on else UITheme.TEXT_DIM)


func _set_btn(i: int) -> void:
	i = posmod(i, _card_btns.size())
	if i == _card_sel:
		return
	_card_sel = i
	_style_btns()
	_sound("ui_click", -14.0, 1.35)


func _press_btn(i: int) -> void:
	if _mode != "card" and _mode != "route":
		return
	_set_btn(i)
	_blink(_card_btns[i])
	if _mode == "card" and i == 0:
		# 放进去：卡片闪一下 + 确认音，关掉，往下播
		_mode = "busy"
		_sound("tick", -4.0, 0.9)
		_sound("flight_select", -10.0, 1.0)
		_blink(_card)
		await get_tree().create_timer(0.35).timeout
		var id := _card_id
		var tw := create_tween()
		tw.tween_property(self, "modulate:a", 0.0, 0.25)
		await tw.finished
		if multi:
			await _multi_put_in(id)
			return
		done.emit(id)
		return
	_sound("tick", -8.0, 1.1)
	await _close_card(_mode == "card")


## 多选版放进去：托板已经淡掉了；播那一段、加燃料，够了就合上（done），不够就重新排托板、淡回来接着挑
func _multi_put_in(id: String) -> void:
	if is_instance_valid(_card):
		_card.queue_free()
	_card = null
	_card_btns.clear()
	_mode = "busy"
	await _burn(id)
	if _enough() or items.is_empty():
		done.emit("")
		return
	_make_slots()
	_mode = "pick"
	_style()
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 1.0, 0.3)


func _close_card(put_back: bool) -> void:
	_mode = "busy"
	var id := _card_id
	if is_instance_valid(_card):
		_card.queue_free()
	_card = null
	_card_btns.clear()
	if put_back:
		var keep: Dictionary = st.get("keep_scenes", {}) if st.get("keep_scenes", {}) is Dictionary else {}
		if multi and keep.has(id):
			await _lines(runner.scenes.get(str(keep[id]), []))     # 音乐盒：收回背包
		else:
			await _lines(st.get("put_back", []))
	_mode = "pick"
	_style()


## 剧本台词（say / narr 等步骤）一句一句播，播的时候按键交给对话框
func _lines(arr) -> void:
	if not arr is Array:
		return
	var was := _mode
	_mode = "busy"
	for l in arr:
		if l is Dictionary:
			await runner._step(l)
	_mode = was


# ======================================================================= 输入
func _input(event: InputEvent) -> void:
	if runner == null or runner.auto != "" or _mode == "busy":
		return
	var vp := get_viewport()
	if event is InputEventKey and event.pressed and not event.echo:
		var k: int = event.keycode
		var prev := k in [KEY_LEFT, KEY_A, KEY_UP, KEY_W]
		var next := k in [KEY_RIGHT, KEY_D, KEY_DOWN, KEY_S]
		var ok := k in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_Z]
		if _mode == "pick":
			if prev:
				_set_sel(_sel - 1)
			elif next:
				_set_sel(_sel + 1)
			elif ok:
				_choose_slot(_sel)
		else:
			if prev:
				_set_btn(_card_sel - 1)
			elif next:
				_set_btn(_card_sel + 1)
			elif ok:
				_press_btn(_card_sel)
			elif k == KEY_ESCAPE:
				_press_btn(_card_btns.size() - 1)
		if k != KEY_ESCAPE or _mode != "pick":
			vp.set_input_as_handled()
		return
	if event is InputEventMouseMotion:
		var i := _hit(event.position)
		if i >= 0:
			if _mode == "pick":
				_set_sel(i)
			else:
				_set_btn(i)
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var i := _hit(event.position)
		if _mode == "pick":
			if i >= 0:
				_choose_slot(i)
		elif i >= 0:
			_press_btn(i)
		vp.set_input_as_handled()


## 鼠标在哪个上面：挑的时候 = 托板上第几个，卡片上 = 第几个按钮；都不在 = -1
func _hit(p: Vector2) -> int:
	if _mode == "pick":
		for i in _slots.size():
			var c: Control = _slots[i]
			var sz := c.size if c is Panel else c.get_combined_minimum_size()
			if Rect2(c.position - Vector2(3, 3), sz + Vector2(6, 6)).has_point(p):
				return i
		return -1
	for i in _card_btns.size():
		var l := _card_btns[i]
		var r := Rect2(l.global_position - Vector2(2, 2), l.get_combined_minimum_size() + Vector2(4, 4))
		if r.has_point(p):
			return i
	return -1


## F8 自测：没在等台词就替它放进第一件
func dev_skip() -> void:
	if _mode == "pick":
		_choose_slot(0)
	elif _mode == "card":
		_press_btn(0)
	elif _mode == "route":
		_press_btn(_card_btns.size() - 1)


# ======================================================================= 自动玩
func _auto_tick(delta: float) -> void:
	if multi and _auto_plan.is_empty() and _mode == "pick" and runner.auto != "":
		_auto_plan = ["look:0", "in"]            # 多选版：一直放第一件，直到燃料够
	if _auto_plan.is_empty() or _mode == "busy":
		return
	_auto_t += delta
	if _auto_t < 0.7:
		return
	_auto_t = 0.0
	var a := str(_auto_plan[0])
	if a.begins_with("look:") and _mode == "pick":
		_auto_plan.pop_front()
		_choose_slot(clampi(int(a.trim_prefix("look:")), 0, items.size() - 1))
	elif a == "route" and _mode == "pick":
		_auto_plan.pop_front()
		_choose_slot(_slots.size() - 1)
	elif a == "back" and (_mode == "card" or _mode == "route"):
		_auto_plan.pop_front()
		_press_btn(_card_btns.size() - 1)
	elif a == "in" and _mode == "card":
		_auto_plan.pop_front()
		_press_btn(0)
	elif a == "in" and _mode == "pick":
		_choose_slot(0)                      # 还没拿起来：先拿第一件
