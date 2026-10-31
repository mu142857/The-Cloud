extends CanvasLayer
## 开发者面板（F8，只在 debug 构建 / 编辑器里运行时有；导出的正式版 level_forest.gd 不建它）。
## 右边一条半透明的小面板，游戏照常跑；面板不抢晨的移动键：用鼠标点，或者 1~4 / Tab 切换页签（开着面板时 Tab 不开背包）。
## 页签：
##   1 传送  每章一张简略地图（上面的小页签换章：森林 / 飞行一 / 河流篇 / 终章……，CHAPTERS 里有的都有）。面板这一页加宽到 MAP_W。
##           每个房间一个带名字的方块，从数据自动摆（_map_geo / _map_layout，新加的房间自己会出现）：
##             室外房间按 room.json 的 origin / size（没写用 room_stage 的 DEFAULT）：每 270 高一行，横着按比例；
##             室内（小屋 kind: house = host 里 x 那里；别的没坐标的 = 剧本里哪个房间的 hotspot fade_to 到它，就是那个门口）
##             挂在门口所在房间下面半行，细线连着门口。方块至少放得下名字，挤了往右推，太宽缩比例，再不行折行。
##           晨在的房间亮黄，方块上小点 = 晨的大概位置。点方块：本章、剧情没在播 = 晨到那个房间里离点的位置最近的 marker
##           （剧情接着跑）；剧情在播 / 别的章 = 重新载入，进那一章的自由探索，站在那个房间（_free_room）。
##           下面：「从头玩」这一章（= 以前节拍页的章节开头，能跨章）；河流篇还有「按烧了蓝色石头 / 通勤卡进」。
##           以后游戏里要加传送石碑（所有场景互相传送），见 docs/forest_chapter.md「开发者模式（F8）」
##   2 状态  正在播的 scene 和第几步、晨的 x、在哪、背包；所有 flag 列成按钮，亮的是已设。
##           点没亮的 = 从现在接着把剧情瞬间过一遍到它（level.dev_complete：前置的 flag、物品、NPC、房间、目标都补齐，
##           不会只设一个 flag 卡在前置上）；从现在走不到（剧情在播 / 走了别的分支）就重新载入本章跳节拍。点亮的 = 只去掉这一个
##   3 开关  快走（晨的移动 ×3，动画帧速不变）、跳过对话（每句 0.15 秒自动推进）、显示 hotspot 范围和 marker 竖线、
##           雾开 / 关、前景层开 / 关、补写台词标蓝（剧本 "added": true 的台词正文用蓝色；debug 构建默认开）；
##           按钮：重开本章、给齐本章所有物品、燃料加满
##   4 探索  自由探索（看美术用，level_forest.gd 的 free_roam / --free=forest|river）：两个入口，森林（坠毁现场起）、河流（河岸起）。
##           进去以后不播剧情、对话，没有目标、卡关提示，trigger:"enter" 不触发，剧情加的墙（walk_when、倒木、坑、导绳……）不算；
##           换地方照常靠 E / 点击（进出屋、上下楼、市集 / 旧街 / 仓库 / 南桥、走到边上的出口），不看剧情 flag，只显示这些进出口。
##           小按钮：角色（路人照常走，本章剧本里的角色排在晨右边）、退出（= 重开本章）。Shift 跑快（只改移动速度）。
##           探索时状态页点 flag = 直接设 / 去掉这一个（不补剧情）
## 面板上的字统一中文：flag / marker / scene / 房间 / 状态的中文名在 data/dev_names.json（没写的回退显示原 id），
##   原 id 放在按钮的 tooltip 里（鼠标停上去看）；状态页那段文字的 tooltip 是原始 id。背包显示物品的 name.zh。
## 用法也写在 docs/forest_chapter.md 末尾「开发者模式（F8）」。
## 自测：-- --dev_test   每个开关点两下、每个按钮点一下、传送到每个 marker、每章地图排一遍（房间一个不少）、
##        点本章地图的每个方块（晨到没到那个房间）、点掉一个 flag；
##        再挨个跳所有大节点（节拍页删了，大节点还在 data/dev_names.json 的 beats，_jump_to 照旧），每个跳完自动玩，
##        能走到本章下一个大节点（最后一个 = 章节结尾）= 没被前置卡住；
##        再在对话 / 点选 / 小游戏 / 驾驶舱小游戏进行中真的按 F8、点地图的方块跳走（INTERRUPTS：进那个房间的自由探索）；
##        最后抽查状态页（SAMPLES：从本章开头原地补齐到中后段的 flag 再接着玩）。全部过了打印 DEV_TEST_DONE 后退出。

const W := 206.0
const TEST_META := "dev_panel_test"       # 自测进度（跨重新载入）：{ch0, phase, i, stage…}
## 自测抽查状态页：从本章开头原地补齐到这个 flag，再接着自动玩
const SAMPLES := {
	"forest": ["bridge_built", "parts_all", "launched"],
	"flight1": ["flight1_leak_fixed", "flight1_miluo_msg"],
}
## 自测打断：剧情播到这种时候按 F8 点地图的方块跳走（进那个房间的自由探索）。[什么时候, 从哪段开始 [章, after], 点哪个方块 [章, 房间]]
const INTERRUPTS := [
	["对话", ["forest", "fuel_full"], ["forest", "treehouse"]],
	["点选", ["forest", "parts_all"], ["flight1", "cockpit"]],
	["小游戏", ["river", ""], ["river", "oldstreet"]],
	["驾驶舱小游戏", ["flight1", ""], ["river", "market"]],
]
const TABS := ["传送", "状态", "开关", "探索"]
const MAP_W := 380.0             # 传送页（地图）时面板的宽；别的页还是 W
const MAP_ROW := 24.0            # 地图一行多高（室内房间在门口那个房间下面半行，也占一行）
const MAP_BOX_H := 18.0
const MAP_GAP := 3.0
const MAP_FS := 12
const CH_FALLBACK := {"final": "终章"}     # dev_names.json 的 chapters 没写的章名
const BG := Color(0.02, 0.05, 0.04, 0.78)
const EDGE := Color(0.5, 0.6, 0.55, 0.35)
const NAMES_PATH := "res://data/dev_names.json"

var level: Node2D
var story: Node
var _root: Panel
var _tab := 0
var _tab_btns: Array[Button] = []
var _pages: Array[Control] = []
var _state_label: Label
var _flag_box: VBoxContainer
var _flag_btns := {}
var _toggles := {}
var _overlay: Node2D
var fast := false
var skip_dialog := false
var show_ranges := false
var _last_x := NAN
var _refresh_t := 0.0
var _saved_auto := -1.0
var _names := {}                 # data/dev_names.json：{flags, markers, scenes, rooms, states} → {id: 中文名}
var _completing := false         # 状态页点的 flag 正在补齐（快进中），别的点先不理
var _map_ch := ""                # 地图现在看的是哪一章
var _map_tabs := {}              # 章 → 地图上面的小页签
var _map_box: Control            # 方块放在这里（自己画门口的连线）
var _map_top: Control            # 盖在方块上面：画晨的位置
var _map_foot: VBoxContainer     # 地图下面的说明和按钮
var _map_blocks: Array = []      # [{b, room, x, y, w, inside, host, door}]
var _map_cache := {}             # 章 → {rooms, g}（_map_geo）
var _map_click := Vector2.ZERO   # 最后一次点在哪（_input 记的：点方块的哪儿，就去离那儿最近的点）
var _free_dyn: VBoxContainer     # 探索页下面那一行小按钮（在探索里才有）
var _free_sig := "-"


func _ready() -> void:
	layer = 60
	story = level.story
	_load_names()
	_root = Panel.new()
	_root.theme = UITheme.get_theme()
	_root.add_theme_stylebox_override("panel", UITheme.box(BG, EDGE, 1))
	_root.position = Vector2(480 - W - 4, 4)
	_root.size = Vector2(W, 262)
	_root.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_root)
	var tabs := HBoxContainer.new()
	tabs.position = Vector2(4, 3)
	tabs.add_theme_constant_override("separation", 2)
	_root.add_child(tabs)
	for i in TABS.size():
		var b := _btn("%d%s" % [i + 1, TABS[i]], _set_tab.bind(i))
		b.autowrap_mode = TextServer.AUTOWRAP_OFF    # 页签不折行（在 HBox 里折行会缩成一个字宽）
		b.add_theme_font_size_override("font_size", 12)
		b.custom_minimum_size = Vector2(0, 16)
		tabs.add_child(b)
		_tab_btns.append(b)
	for i in TABS.size():
		var sc := ScrollContainer.new()
		sc.position = Vector2(4, 23)
		sc.size = Vector2(_page_w(i) - 8, 262 - 27)
		sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		_root.add_child(sc)
		var v := VBoxContainer.new()
		v.add_theme_constant_override("separation", 1)
		v.custom_minimum_size = Vector2(_page_w(i) - 16, 0)
		sc.add_child(v)
		_pages.append(sc)
		match TABS[i]:
			"传送":
				_build_teleport(v)
			"状态":
				_build_state(v)
			"开关":
				_build_switches(v)
			"探索":
				_build_free(v)
	_overlay = Node2D.new()
	_overlay.name = "DevOverlay"
	_overlay.z_index = 50
	_overlay.draw.connect(_draw_overlay)
	level.add_child(_overlay)
	_set_tab(0)
	if "--dev_test" in OS.get_cmdline_user_args():
		_self_test.call_deferred()


func toggle() -> void:
	visible = not visible


## 这一页时面板多宽（地图那页宽一些）
func _page_w(i: int) -> float:
	return MAP_W if TABS[i] == "传送" else W


## 名字表：kind = flags / markers / scenes / rooms / states。scenes 先查「章节:id」（不同章节同名 scene），查不到回退原 id
func _load_names() -> void:
	var f := FileAccess.open(NAMES_PATH, FileAccess.READ)
	if f == null:
		return
	var d = JSON.parse_string(f.get_as_text())
	if d is Dictionary:
		_names = d


func _nm(kind: String, id: String) -> String:
	var t = _names.get(kind, {})
	if not t is Dictionary:
		return id
	if kind == "scenes" and t.has(str(level.chapter) + ":" + id):
		return str(t[str(level.chapter) + ":" + id])
	return str(t.get(id, id))


func _item_name(id: String) -> String:
	var n = Inventory.item(id).get("name", {})
	if n is Dictionary and str(n.get("zh", "")) != "":
		return str(n["zh"])
	return id


func _btn(text: String, cb: Callable, tip := "") -> Button:
	var b := Button.new()
	b.text = text
	b.tooltip_text = tip
	b.focus_mode = Control.FOCUS_NONE          # 不抢键盘（方向键、空格还是给晨）
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY   # 名字长就折成两行，不把整列撑出面板
	b.add_theme_font_size_override("font_size", 14)
	b.add_theme_stylebox_override("normal", UITheme.box(Color(0.08, 0.12, 0.1, 0.6), Color(0, 0, 0, 0), 0, Vector4(3, 0, 3, 0)))
	b.add_theme_stylebox_override("hover", UITheme.box(Color(0.16, 0.24, 0.2, 0.9), Color(0, 0, 0, 0), 0, Vector4(3, 0, 3, 0)))
	b.add_theme_stylebox_override("pressed", UITheme.box(Color(0.3, 0.2, 0.3, 0.9), Color(0, 0, 0, 0), 0, Vector4(3, 0, 3, 0)))
	b.pressed.connect(cb)
	return b


## i 超出 = 最后一页（level_forest 自由探索时叫 _set_tab(4)，那是删节拍页以前「探索」的号）
func _set_tab(i: int) -> void:
	i = clampi(i, 0, TABS.size() - 1)
	_tab = i
	_root.size = Vector2(_page_w(i), 262)
	_root.position = Vector2(480 - _page_w(i) - 4, 4)
	for k in _pages.size():
		_pages[k].visible = k == i
		_tab_btns[k].modulate = Color(1.3, 1.3, 1.3) if k == i else Color(0.75, 0.75, 0.75)


# ======================================================================= 页签
func all_flags() -> Array[String]:
	var out: Array[String] = []
	for f in story.ENGINE_FLAGS:
		if not out.has(str(f)):
			out.append(str(f))
	for id in story.scenes:
		for st in story.scenes[id]:
			if st is Dictionary and str(st.get("do", "")) == "flag" and st.has("set") and not out.has(str(st["set"])):
				out.append(str(st["set"]))
	return out


func _label(text: String) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 14)
	l.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	l.custom_minimum_size = Vector2(W - 16, 0)
	return l


func _chapter_name(ch: String) -> String:
	var t = _names.get("chapters", {})
	var fb := str(CH_FALLBACK.get(ch, ch))
	return str(t.get(ch, fb)) if t is Dictionary else fb


## 跳到 ch 这一章的大节点（地图下面的「从头玩」、自测用）：after 为空 = 这一章从头开始；别的 = 重新载入那一章再 --beat 到 after（同一套快进补齐）
## 换章：去森林 = 新游戏；去飞行一 / 河流篇 = 带着现在的真实状态（本章已经播完）或者用 SEED（chapter_flow.gd）
func _jump_to(ch: String, after: String) -> void:
	_free_off()
	if ch != level.chapter:
		_prep_chapter(ch)
	if after != "":
		Engine.set_meta(level.DEV_BEAT_META, after)
	elif ch == "forest":
		Engine.set_meta(level.DEV_STAGE_META, "play")     # 森林开头：跳过标题，直接坠毁
	Engine.set_meta(level.DEV_OPEN_META, true)
	_reload()


## 重新载入本场景（剧情播到一半也行：正在 await 的步骤、对话框、点选、小游戏都跟着旧场景一起扔掉）
func _reload() -> void:
	level.CHAPTER_GD.hard_reload(level.get_tree())


## 河流篇用哪个 SEED：重新直接进河流篇
func _river_seed(v: String) -> void:
	_free_off()
	var cf = level.CHAPTER_GD
	if v == "":
		Engine.remove_meta(cf.RIVER_SEED_META)
	else:
		Engine.set_meta(cf.RIVER_SEED_META, v)
	if Engine.has_meta(cf.CARRY_META):
		Engine.remove_meta(cf.CARRY_META)
	Engine.set_meta(cf.CHAPTER_META, "river")
	Engine.set_meta(cf.PICK_META, true)
	Engine.set_meta(level.DEV_OPEN_META, true)
	_reload()


## 换到 ch 这一章要准备的 meta（不重新载入）
func _prep_chapter(ch: String) -> void:
	var cf = level.CHAPTER_GD
	if ch == "forest":
		cf.reset()
	elif ch == "final" and level.chapter == "river" and StoryState.has("river_done"):
		Engine.set_meta(cf.CARRY_META, StoryState.to_dict())      # 河流篇已经起飞：带着真实的状态过去
	elif ch == "final":
		if Engine.has_meta(cf.CARRY_META):
			Engine.remove_meta(cf.CARRY_META)                     # 别的地方直接跳终章：用 SEED（+ SEED_RIVER）
	elif ch == "river" and level.chapter == "forest":
		if Engine.has_meta(cf.CARRY_META):
			Engine.remove_meta(cf.CARRY_META)                     # 从森林直接跳：用 SEED
	elif ch == "river" and level.chapter == "flight1" and StoryState.has("flight1_done"):
		Engine.set_meta(cf.CARRY_META, StoryState.to_dict())      # 飞行一已经降落：带着真实的状态过去
	elif ch == "river" and level.chapter == "flight1":
		Engine.remove_meta(cf.CARRY_META)
	elif level.chapter == "forest" and StoryState.has("launched"):
		Engine.set_meta(cf.CARRY_META, StoryState.to_dict())      # 森林已经起飞了：带着真实的状态过去
	elif Engine.has_meta(cf.CARRY_META):
		Engine.remove_meta(cf.CARRY_META)                         # 森林中途 / 从河流篇回去：用 SEED
	Engine.set_meta(cf.CHAPTER_META, ch)
	Engine.set_meta(cf.PICK_META, true)


# ======================================================================= 传送：每章一张简略地图
func _build_teleport(v: VBoxContainer) -> void:
	var tabs := HBoxContainer.new()
	tabs.add_theme_constant_override("separation", 2)
	v.add_child(tabs)
	for ch in level.CHAPTER_GD.CHAPTERS:
		var b := _btn(_chapter_name(str(ch)), _map_show.bind(str(ch)), str(ch))
		b.autowrap_mode = TextServer.AUTOWRAP_OFF
		b.add_theme_font_size_override("font_size", 12)
		b.custom_minimum_size = Vector2(0, 16)
		tabs.add_child(b)
		_map_tabs[str(ch)] = b
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 5)
	v.add_child(gap)
	_map_box = Control.new()
	_map_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_map_box.draw.connect(_draw_map_lines)
	v.add_child(_map_box)
	_map_top = Control.new()
	_map_top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_map_top.draw.connect(_draw_map_chen)
	var gap2 := Control.new()
	gap2.custom_minimum_size = Vector2(0, 4)
	v.add_child(gap2)
	_map_foot = VBoxContainer.new()
	_map_foot.add_theme_constant_override("separation", 1)
	v.add_child(_map_foot)
	_map_show(str(level.chapter))


## 地图换到 ch 这一章（重新摆方块）
func _map_show(ch: String) -> void:
	_map_ch = ch
	for k in _map_tabs:
		(_map_tabs[k] as Button).modulate = Color(1.35, 1.35, 1.35) if k == ch else Color(0.7, 0.7, 0.7)
	for c in _map_box.get_children():
		_map_box.remove_child(c)
		if c != _map_top:
			c.queue_free()
	_map_blocks.clear()
	var lay := _map_layout(ch)
	for d in lay["boxes"]:
		var room := str(d["room"])
		var b := _btn(_map_label(room), _map_go.bind(ch, room), "%s  %s" % [_nm("rooms", room), room])
		b.autowrap_mode = TextServer.AUTOWRAP_OFF
		b.alignment = HORIZONTAL_ALIGNMENT_CENTER
		b.clip_text = true
		b.add_theme_font_size_override("font_size", MAP_FS)
		var bg := Color(0.1, 0.15, 0.2, 0.92) if d["inside"] else Color(0.09, 0.2, 0.15, 0.92)
		var edge := Color(0.36, 0.47, 0.55) if d["inside"] else Color(0.36, 0.52, 0.44)
		b.add_theme_stylebox_override("normal", UITheme.box(bg, edge, 1, Vector4(2, 0, 2, 0)))
		b.add_theme_stylebox_override("hover", UITheme.box(bg.lightened(0.2), edge.lightened(0.3), 1, Vector4(2, 0, 2, 0)))
		b.position = Vector2(float(d["x"]), float(d["y"]))
		b.custom_minimum_size = Vector2(float(d["w"]), MAP_BOX_H)
		b.size = b.custom_minimum_size
		_map_box.add_child(b)
		d["b"] = b
		_map_blocks.append(d)
	_map_box.custom_minimum_size = Vector2(MAP_W - 16.0, float(lay["h"]))
	_map_box.add_child(_map_top)
	_map_top.size = _map_box.custom_minimum_size
	_map_box.queue_redraw()
	_map_top.queue_redraw()
	_map_foot_build(ch)


## 地图下面：怎么用；从头玩这一章；河流篇按哪个 SEED 进
func _map_foot_build(ch: String) -> void:
	for c in _map_foot.get_children():
		_map_foot.remove_child(c)
		c.queue_free()
	var t := _label("点方块 = 晨到那个房间（点哪儿就去离那儿最近的点）；剧情在播时 = 进那个房间的自由探索"
		if ch == level.chapter else "点方块 = 进这一章的自由探索，站在那个房间")
	t.custom_minimum_size = Vector2(MAP_W - 16.0, 0)
	t.add_theme_color_override("font_color", UITheme.TEXT_DIM)
	t.add_theme_font_size_override("font_size", 12)
	_map_foot.add_child(t)
	_map_foot.add_child(_btn("从头玩「%s」" % _chapter_name(ch), _jump_to.bind(ch, ""), ch))
	if ch == "river":
		# 原文 119 摸衣袋：飞行一烧的是蓝色石头还是通勤卡（从别的章直接进河流篇用的 SEED）
		var card := Engine.has_meta(level.CHAPTER_GD.RIVER_SEED_META) and str(Engine.get_meta(level.CHAPTER_GD.RIVER_SEED_META)) == "card"
		_map_foot.add_child(_btn("从头玩，按「烧了%s」进（点换成%s）" % ["通勤卡" if card else "蓝色石头", "蓝色石头" if card else "通勤卡"],
			_river_seed.bind("" if card else "card")))


## 方块上的名字（「旧货场（结局一）」只写「旧货场」，全名在 tooltip）
func _map_label(room: String) -> String:
	var t := _nm("rooms", room)
	var k := t.find("（")
	return t.substr(0, k) if k > 0 else t


func _map_text_w(t: String) -> float:
	return UITheme.font().get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, MAP_FS).x


## marker 的值：数 / {x: …} / [x, …]；不是这些 = NAN
func _mk_x(v) -> float:
	if v is Dictionary:
		v = v.get("x", null)
	elif v is Array and not v.is_empty():
		v = v[0]
	return float(v) if (v is float or v is int) else NAN


## 一章有哪些房间、各在哪（世界坐标）：{rooms: [..], g: {房间: {kind, x, y, w, host, door}}}
##   kind = out：室外。room.json 的 origin / size（没写用 room_stage 的 DEFAULT）；森林 = wall_left..wall_right
##        / in：室内，挂在 host 下面，door = 门口在 host 里的 x。小屋（room.json kind: house）= 它的 host / x；
##              别的没坐标的 = 剧本里 host 的哪个 hotspot fade_to 到它，door = 那个 hotspot 的 marker。
##              两个都没坐标的互相通（小镇 ↔ 小镇住处）：剧本 rooms 里写在前面的算外面，不绕成圈
##        / loose：哪都挂不上，排在第一行最后
## 剧本没写 rooms（森林）= 章节的 room（没写 = forest）加上 hotspot 用到的房间。
## Python 预览（tools/dev_map_preview.py）是同一套，改了这里那边也改
func _map_geo(ch: String) -> Dictionary:
	if _map_cache.has(ch):
		return _map_cache[ch]
	var info: Dictionary = level.CHAPTER_GD.CHAPTERS.get(ch, {})
	var d = JSON.parse_string(FileAccess.get_file_as_string(str(info.get("story", ""))))
	if not d is Dictionary:
		d = {}
	var rooms: Array = []
	for r in d.get("rooms", []):
		rooms.append(str(r))
	if rooms.is_empty():
		rooms.append(str(info.get("room", "forest")))
		for h in d.get("hotspots", []):
			if h is Dictionary and not rooms.has(str(h.get("room", "forest"))):
				rooms.append(str(h.get("room", "forest")))
	var smk: Dictionary = d["markers"] if d.get("markers") is Dictionary else {}
	var fmk: Dictionary = story.world.DEFAULT_MARKERS
	var g := {}
	for r in rooms:
		var c: Dictionary = {} if r in ["forest", "treehouse", "cockpit"] else story.world.STAGE_GD.peek(r)
		var sz = c.get("size", [480, 270])
		var w := float(sz[0]) if sz is Array and not sz.is_empty() else 480.0
		if r == "forest":
			var x0 := float(fmk.get("wall_left", 0))
			g[r] = {"kind": "out", "x": x0, "y": 0.0, "w": float(fmk.get("wall_right", 480)) - x0}
		elif str(c.get("kind", "")) == "house" and rooms.has(str(c.get("host", ""))):
			g[r] = {"kind": "in", "host": str(c["host"]), "door": float(c.get("x", 0)), "w": w}
		elif c.get("origin") is Array:
			g[r] = {"kind": "out", "x": float(c["origin"][0]), "y": float(c["origin"][1]), "w": w}
		else:
			g[r] = {"kind": "pend", "w": w}
	var scenes: Dictionary = d["scenes"] if d.get("scenes") is Dictionary else {}
	for h in d.get("hotspots", []):
		if not h is Dictionary:
			continue
		var src := str(h.get("room", "forest"))
		for st in scenes.get(str(h.get("scene", "")), []):
			if not (st is Dictionary and str(st.get("do", "")) == "fade_to"):
				continue
			var dst := str(st.get("room", ""))
			if g.has(dst) and g.has(src) and dst != src and g[dst]["kind"] == "pend" \
					and (g[src]["kind"] != "pend" or rooms.find(src) < rooms.find(dst)) and not _map_under(g, src, dst):
				g[dst] = {"kind": "in", "host": src, "door": _map_door(src, h.get("at"), smk, fmk, g), "w": g[dst]["w"]}
			break
	for r in g:
		if g[r]["kind"] == "pend":
			g[r]["kind"] = "loose"
	_map_cache[ch] = {"rooms": rooms, "g": g}
	return _map_cache[ch]


## r 是不是挂在 top 底下（顺着 host 往上找）
func _map_under(g: Dictionary, r: String, top: String) -> bool:
	var seen := {}
	while g.has(r) and g[r]["kind"] == "in" and not seen.has(r):
		seen[r] = true
		r = str(g[r]["host"])
		if r == top:
			return true
	return false


## 门口（marker at）在 host 里的 x：森林 = DEFAULT_MARKERS（再看剧本 markers）减 wall_left；
## 别的 = host 的 room.json markers，再看剧本 markers（0 = 没写）；都没有 = host 中间
func _map_door(host: String, at, smk: Dictionary, fmk: Dictionary, g: Dictionary) -> float:
	var half := float(g[host]["w"]) / 2.0
	if not at is String:
		return half
	if host == "forest":
		var fx := _mk_x(fmk.get(at, smk.get(at)))
		return fx - float(fmk.get("wall_left", 0)) if not is_nan(fx) else half
	var mk = story.world.STAGE_GD.peek(host).get("markers", {})
	var x := _mk_x(mk.get(at) if mk is Dictionary else null)
	if is_nan(x):
		x = _mk_x(smk.get(at))
		if x == 0.0:
			x = NAN
	return x if not is_nan(x) else half


## 方块摆在哪（地图区左上角 = 0）：{boxes: [{room, x, y, w, inside, host, door}], h}
## 室外每 270 高一行（origin.y），横着按比例（最左到最右的室外房间铺满地图宽）；室内在 host 下面半行（也占一行），
## 方块中心对着门口；没坐标的排在第一行最后。方块至少放得下名字（+8），挤了往右推；
## 有一行超出地图宽就把比例 ×0.85 再排（最多 12 次），还不行就折行
func _map_layout(ch: String) -> Dictionary:
	var geo := _map_geo(ch)
	var rooms: Array = geo["rooms"]
	var g: Dictionary = geo["g"]
	var mw := MAP_W - 16.0
	var lv := {}
	for _i in rooms.size() + 1:
		for r in rooms:
			var q: Dictionary = g[r]
			if q["kind"] != "in":
				lv[r] = float(q.get("y", 0.0)) / 270.0
			elif lv.has(q["host"]):
				lv[r] = float(lv[q["host"]]) + 0.5
	var lo := INF
	var hi := -INF
	for r in rooms:
		if g[r]["kind"] == "out":
			lo = minf(lo, float(g[r]["x"]))
			hi = maxf(hi, float(g[r]["x"]) + float(g[r]["w"]))
	if lo == INF:
		lo = 0.0
		hi = 1.0
	var levels: Array = []
	for r in rooms:
		if lv.has(r) and not levels.has(lv[r]):
			levels.append(lv[r])
	levels.sort()
	var sx := mw / maxf(hi - lo, 1.0)
	var box := {}
	for _try in 12:
		box = {}
		var over := false
		for L in levels:
			var row: Array = []
			for r in rooms:
				if not lv.has(r) or lv[r] != L:
					continue
				var q: Dictionary = g[r]
				var bw := _map_text_w(_map_label(r)) + 8.0
				var bx := INF
				var door := NAN
				if q["kind"] == "out":
					bw = maxf(float(q["w"]) * sx, bw)
					bx = (float(q["x"]) - lo) * sx
				elif q["kind"] == "in" and box.has(q["host"]):
					var hb: Array = box[q["host"]]
					var hw := maxf(float(g[q["host"]]["w"]), 1.0)
					door = float(hb[0]) + float(hb[1]) * clampf(float(q["door"]) / hw, 0.0, 1.0)
					bx = door - bw / 2.0
				row.append([bx, bw, r, door])
			row.sort_custom(func(a, b): return a[0] < b[0] or (a[0] == b[0] and rooms.find(a[2]) < rooms.find(b[2])))
			var end := -MAP_GAP
			for a in row:
				var x0: float = a[0] if a[0] < INF else end + MAP_GAP + 4.0
				a[0] = maxf(maxf(x0, end + MAP_GAP), 0.0)
				end = a[0] + a[1]
				over = over or end > mw
				box[a[2]] = a
		if not over:
			break
		sx *= 0.85
	var out: Array = []
	var line := 0
	for L in levels:
		var row: Array = []
		for r in rooms:
			if lv.has(r) and lv[r] == L:
				row.append(box[r])
		row.sort_custom(func(a, b): return a[0] < b[0])
		var x_off := 0.0
		for a in row:
			var bx: float = a[0] - x_off
			if bx + a[1] > mw and bx > 0.0:
				line += 1                          # 实在挤不下：折到下一行
				x_off = a[0]
				bx = 0.0
			var q: Dictionary = g[a[2]]
			out.append({"room": str(a[2]), "x": roundf(bx), "y": line * MAP_ROW, "w": roundf(a[1]), "inside": q["kind"] == "in",
				"host": str(q.get("host", "")), "door": roundf(a[3]) if not is_nan(a[3]) else NAN})
		line += 1
	return {"boxes": out, "h": line * MAP_ROW}


## 室内方块和门口连一根细线：从 host 底边的门口往下，拐到方块中间
func _draw_map_lines() -> void:
	var by := {}
	for d in _map_blocks:
		by[d["room"]] = d
	var c := Color(0.45, 0.57, 0.5, 0.9)
	for d in _map_blocks:
		if not d["inside"] or not by.has(d["host"]) or is_nan(d["door"]):
			continue
		var hb: Dictionary = by[d["host"]]
		var x := roundf(clampf(float(d["door"]), float(hb["x"]) + 1.0, float(hb["x"]) + float(hb["w"]) - 2.0)) + 0.5
		var cx := roundf(float(d["x"]) + float(d["w"]) / 2.0) + 0.5
		var y0 := float(hb["y"]) + MAP_BOX_H
		var y1 := float(d["y"])
		if x > float(d["x"]) + 1.0 and x < float(d["x"]) + float(d["w"]) - 1.0:
			_map_box.draw_line(Vector2(x, y0), Vector2(x, y1), c, 1.0)
			continue
		var ym := roundf((y0 + y1) / 2.0) + 0.5
		_map_box.draw_line(Vector2(x, y0), Vector2(x, ym), c, 1.0)
		_map_box.draw_line(Vector2(x, ym), Vector2(cx, ym), c, 1.0)
		_map_box.draw_line(Vector2(cx, ym), Vector2(cx, y1), c, 1.0)


## 晨在的那个方块上点一个小点（大概在房间的哪儿）
func _draw_map_chen() -> void:
	if _map_ch != level.chapter:
		return
	var room := str(story.world.room)
	for d in _map_blocks:
		if d["room"] != room:
			continue
		var x := float(d["x"]) + 2.0 + _chen_frac(room) * (float(d["w"]) - 5.0)
		_map_top.draw_rect(Rect2(roundf(x), float(d["y"]) + MAP_BOX_H - 5.0, 3, 3), UITheme.ACCENT)


## 晨在房间的哪儿：0 = 左头，1 = 右头（说不准的 = 中间）
func _chen_frac(room: String) -> float:
	var w = story.world
	var x: float = level.chen.position.x
	if w.is_stage(room):
		var sg: Node2D = w.stage(room)
		return clampf((x - sg.origin.x) / maxf(sg.size.x, 1.0), 0.0, 1.0)
	if room == "forest":
		var wl := float(w.markers.get("wall_left", 0))
		return clampf((x - wl) / maxf(float(w.markers.get("wall_right", 480)) - wl, 1.0), 0.0, 1.0)
	if room == "treehouse":
		var hw := maxf(float(w.house.get("w", 480)), 1.0)
		return clampf((x - (float(w.house.get("cx", 0)) - hw / 2.0)) / hw, 0.0, 1.0)
	return 0.5


## 本章 marker 在哪个房间、房间里的 x、房间多宽：[房间, x, 宽]；不归哪个房间管（多房间章节里森林的点）= []
func _marker_place(nm: String) -> Array:
	var w = story.world
	var r := str(w.room_of_marker(nm))
	if r != "" and w.is_stage(r):
		var sg: Node2D = w.stage(r)
		return [r, float(sg.markers.get(nm, sg.size.x / 2.0)), sg.size.x]
	if nm.begins_with("cockpit_"):
		return ["cockpit", 0.0, 1.0]
	if not w.stages.is_empty():
		return []
	if nm.begins_with("room_"):
		return ["treehouse", float(w.markers[nm]), 480.0]
	var wl := float(w.markers.get("wall_left", 0))
	return ["forest", float(w.markers[nm]) - wl, maxf(float(w.markers.get("wall_right", 480)) - wl, 1.0)]


## 本章 room 里离 frac（0 = 房间左头，1 = 右头）最近、找得到位置的 marker；没有 = ""
func _map_marker(room: String, frac: float) -> String:
	var best := ""
	var bd := INF
	for n in story.world.markers:
		var nm := str(n)
		var p := _marker_place(nm)
		if p.is_empty() or p[0] != room or not story.world.resolve(nm)["ok"]:
			continue
		var dd := absf(float(p[1]) / float(p[2]) - frac)
		if dd < bd:
			bd = dd
			best = nm
	return best


## 点地图的方块：本章、剧情没在播 = 晨到那个房间里离点的位置最近的 marker（剧情接着跑，和以前的传送一样）；
## 剧情在播 / 别的章 / 那个房间一个点都没有 = 重新载入，进那一章的自由探索，站在那个房间
func _map_go(ch: String, room: String) -> void:
	if ch == level.chapter and not story.busy:
		var frac := 0.5
		for d in _map_blocks:
			if d["room"] == room:
				var b: Button = d["b"]
				frac = clampf((_map_click.x - b.global_position.x) / maxf(b.size.x, 1.0), 0.0, 1.0)
		var m := _map_marker(room, frac)
		if m != "":
			story._teleport(room, float(story.world.resolve(m)["x"]), [], true)
			level.set("_walk_target", NAN)
			return
	_free_room(ch, room)


## 进 ch 这一章的自由探索、站在 room（level_forest._free_pick / _free_spawn）
func _free_room(ch: String, room: String) -> void:
	if ch != level.chapter:
		_prep_chapter(ch)
	Engine.set_meta(level.DEV_FREE_META, room)
	Engine.set_meta(level.DEV_FREE_CH_META, ch)
	Engine.set_meta(level.DEV_OPEN_META, true)
	_reload()


func _build_state(v: VBoxContainer) -> void:
	_state_label = Label.new()
	_state_label.add_theme_font_size_override("font_size", 14)
	_state_label.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	_state_label.custom_minimum_size = Vector2(W - 16, 0)
	_state_label.mouse_filter = Control.MOUSE_FILTER_PASS        # 停上去看原始 id（tooltip）
	v.add_child(_state_label)
	var t := Label.new()
	t.text = "剧情标记：点没亮的 = 补齐前面剧情到它；点亮的 = 只去掉它"
	t.add_theme_color_override("font_color", UITheme.TEXT_DIM)
	t.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	t.custom_minimum_size = Vector2(W - 16, 0)
	v.add_child(t)
	for f in all_flags():
		var b := _btn(_nm("flags", f), _toggle_flag.bind(f), f)
		v.add_child(b)
		_flag_btns[f] = b


func _build_switches(v: VBoxContainer) -> void:
	for k in [["fast", "快走 ×3"], ["skip", "跳过对话"], ["ranges", "显示互动范围 / 传送点"], ["fog", "雾"], ["front", "前景层"],
			["added", "补写台词标蓝"]]:
		var b := _btn("", _switch.bind(str(k[0])))
		b.set_meta("label", str(k[1]))
		v.add_child(b)
		_toggles[str(k[0])] = b
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 6)
	v.add_child(gap)
	v.add_child(_btn("重开本章", _restart))
	v.add_child(_btn("给齐本章所有物品", _give_all))
	v.add_child(_btn("燃料加满", _fuel_full))
	v.add_child(_btn("打开通讯器", func(): story.phone.dev_open()))          # 通讯器（phone_ui.gd）
	v.add_child(_btn("模拟一条消息", func(): story.phone.dev_simulate()))
	_sync_switches()


# ======================================================================= 探索（自由探索）
func _build_free(v: VBoxContainer) -> void:
	var t := _label("自由探索：不播剧情、没有任务和墙，换地方靠 E / 点击（进出屋、上下楼、去市集……）。Shift 跑快")
	t.add_theme_color_override("font_color", UITheme.TEXT_DIM)
	t.add_theme_font_size_override("font_size", 12)
	v.add_child(t)
	v.add_child(_btn("森林（坠毁现场起）", _free_go.bind("forest"), "--free=forest"))
	v.add_child(_btn("河流（河岸起）", _free_go.bind("river"), "--free=river"))
	_free_dyn = VBoxContainer.new()
	v.add_child(_free_dyn)
	_free_refresh()


## 一行几个按钮（不折行，平分宽度）
func _row(items: Array) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 2)
	for it in items:
		var b := _btn(str(it[0]), it[1])
		b.autowrap_mode = TextServer.AUTOWRAP_OFF
		b.alignment = HORIZONTAL_ALIGNMENT_CENTER
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		h.add_child(b)
	return h


## 在探索里才有的那一行小按钮：角色开关、退出
func _free_refresh() -> void:
	if _free_dyn == null:
		return
	var sig := "%s|%s" % [level.free_roam, level.free_npcs]
	if sig == _free_sig:
		return
	_free_sig = sig
	for c in _free_dyn.get_children():
		_free_dyn.remove_child(c)
		c.queue_free()
	if level.free_roam == "":
		return
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 4)
	_free_dyn.add_child(gap)
	_free_dyn.add_child(_row([[("■" if level.free_npcs else "□") + " 角色", func(): level.free_show_npcs(not level.free_npcs)],
		["退出探索", _free_exit]]))


## 进自由探索：重新载入那一章再进（level_forest._free_pick / _start_free）
func _free_go(id: String) -> void:
	var ch := str(level.FREE_ROOMS[id])
	if ch != level.chapter:
		_prep_chapter(ch)
	Engine.set_meta(level.DEV_FREE_META, id)
	if Engine.has_meta(level.DEV_FREE_CH_META):
		Engine.remove_meta(level.DEV_FREE_CH_META)
	Engine.set_meta(level.DEV_OPEN_META, true)
	_reload()


func _free_exit() -> void:
	_jump_to(str(level.chapter), "")


## 跳节拍 / 重开：不再进自由探索
func _free_off() -> void:
	for m in [level.DEV_FREE_META, level.DEV_FREE_CH_META]:
		if Engine.has_meta(m):
			Engine.remove_meta(m)


# ======================================================================= 动作
func _jump_beat(f: String) -> void:
	_free_off()
	Engine.set_meta(level.DEV_BEAT_META, f)
	_reload()


func _restart() -> void:
	_jump_to(str(level.chapter), "")


func _toggle_flag(f: String) -> void:
	if level.free_roam != "":
		if StoryState.has(f):                 # 自由探索：剧本关着，补不了剧情；只设 / 去掉这一个（看跟着 flag 变的图）
			StoryState.clear_flag(f)
		else:
			StoryState.set_flag(f)
		return
	if StoryState.has(f):
		StoryState.clear_flag(f)              # 去掉只去掉这一个（查分支用）
		return
	if _completing:
		return
	_completing = true
	var ok: bool = await level.dev_complete(f)
	_completing = false
	if not ok and not StoryState.has(f):
		_jump_beat(f)                         # 从现在走不到：重新载入本章，从头跳到它


func _give_all() -> void:
	for id in Inventory._order:
		if not Inventory.has(str(id)):
			Inventory.add(str(id))
	level.on_inventory_changed()


func _fuel_full() -> void:
	for id in Inventory._order:
		var it := Inventory.item(str(id))
		if Inventory.burn_total() >= Inventory.get_launch_burn():
			break
		if not it.get("personal", false) and int(it.get("burn", 0)) > 0 and not Inventory.has(str(id)):
			Inventory.add(str(id))
	level.on_inventory_changed()


func _switch(k: String) -> void:
	match k:
		"fast":
			fast = not fast
		"skip":
			skip_dialog = not skip_dialog
			if skip_dialog:
				_saved_auto = story.dlg.auto_delay
				story.dlg.auto_delay = 0.15
			else:
				story.dlg.auto_delay = _saved_auto
		"ranges":
			show_ranges = not show_ranges
		"fog":
			story.world.fog_enabled = not story.world.fog_enabled
		"front":
			var f: CanvasItem = level.get_node("Front")
			f.visible = not f.visible
		"added":
			story.mark_added = not story.mark_added
	_sync_switches()


func _sync_switches() -> void:
	var on := {"fast": fast, "skip": skip_dialog, "ranges": show_ranges, "fog": story.world.fog_enabled,
		"front": (level.get_node("Front") as CanvasItem).visible, "added": story.mark_added}
	for k in _toggles:
		var b: Button = _toggles[k]
		b.text = ("■ " if on[k] else "□ ") + str(b.get_meta("label"))


# ======================================================================= 自测（--dev_test）
func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


## 剧情在播：对话自己往下走、点选替它选、驾驶舱小玩法替它做完，等到能自由走（最多 limit 秒）
func _settle(limit: float) -> void:
	if not story.busy and level.free_play():
		return
	var was: float = story.dlg.auto_delay
	story.dlg.auto_delay = 0.2
	var waited := 0.0
	while (story.busy or not level.free_play()) and waited < limit and not story.ended:
		await _wait(0.25)
		waited += 0.25
		if story.dlg.picking():
			story.dlg.confirm()
		elif story.dlg.menu_open():
			story.dlg._menu_choose(story.dlg._menu_sel)
		elif story.cockpit_ui != null:
			_cockpit_skip()
	story.dlg.auto_delay = was


func _self_test() -> void:
	await _wait(1.5)
	var d: Dictionary = Engine.get_meta(TEST_META) if Engine.has_meta(TEST_META) else {}
	if d.is_empty():
		await _test_buttons()
		_test_go({"ch0": str(level.chapter), "phase": "beat", "i": 0})
		return
	match str(d["phase"]):
		"beat":
			await _test_beat(d)
		"int":
			await _test_interrupt(d)
		"sample":
			await _check_sample(d)


## 第一轮：开关、按钮、传送、flag、地图
func _test_buttons() -> void:
	for k in _toggles:
		_switch(str(k))
		await _wait(0.1)
		_switch(str(k))
	_give_all()
	_fuel_full()
	# 通讯器剧情播放中不开（open_browse 的规矩）：flight1 一进来就在播起飞过场，先让它自己播到能自由走再试
	await _settle(90.0)
	story.phone.dev_open()
	await _wait(0.3)
	var phone_ok: bool = story.phone.is_open()
	story.phone.close()
	level._close_panels()
	print("DEV_TEST phone open=%s" % phone_ok)
	for n in story.world.markers:
		level.dev_teleport(str(n))
		await _wait(0.05)
	level.dev_teleport("chen_start")
	StoryState.set_flag("zz_test_flag")
	_toggle_flag("zz_test_flag")              # 点亮的 = 只去掉（没亮的那条路在后面的抽查里测）
	if StoryState.has("zz_test_flag"):
		print("DEV_TEST flag clear FAILED")
	for t in TABS.size():
		_set_tab(t)
		await _wait(0.25)
	_set_tab(0)
	await _test_map()
	print("DEV_TEST buttons ok (toggles %d, markers %d, 大节点 %d)" % [_toggles.size(), story.world.markers.size(), _all_beats().size()])


## 地图：每章排一遍，房间一个不少、方块不出地图；本章每个方块点一下（有 marker 的），晨到没到那个房间
func _test_map() -> void:
	var bad: Array[String] = []
	for ch in level.CHAPTER_GD.CHAPTERS:
		_map_show(str(ch))
		var got := {}
		for d in _map_blocks:
			got[d["room"]] = true
			if float(d["x"]) + float(d["w"]) > MAP_W - 16.0 + 0.5:
				bad.append("%s:%s 出界" % [ch, d["room"]])
		for r in _map_geo(str(ch))["rooms"]:
			if not got.has(r):
				bad.append("%s:%s 没有" % [ch, r])
	_map_show(str(level.chapter))
	var tried := 0
	var went := 0
	for d in _map_blocks.duplicate():
		var room := str(d["room"])
		if story.busy or room == "cockpit" or _map_marker(room, 0.5) == "":
			continue                              # 驾驶舱：剧情里是起飞过场才进，不在这里乱进
		tried += 1
		_map_click = (d["b"] as Button).get_global_rect().get_center()
		_map_go(str(level.chapter), room)
		await _wait(0.1)
		if str(story.world.room) == room:
			went += 1
		else:
			bad.append("点 %s 没到（在 %s）" % [room, story.world.room])
	level.dev_teleport("chen_start")
	print("DEV_TEST 地图 %d 章，本章方块点了 %d 个、到了 %d 个%s" % [level.CHAPTER_GD.CHAPTERS.size(), tried, went,
		"" if bad.is_empty() else "  FAILED: " + "；".join(bad)])


## 所有大节点按章排成一列：[{ch, after, zh}]
func _all_beats() -> Array:
	var out: Array = []
	var beats = _names.get("beats", {})
	for ch in level.CHAPTER_GD.CHAPTERS:
		for bt in (beats.get(ch, []) if beats is Dictionary else []):
			out.append({"ch": str(ch), "after": str(bt.get("after", "")), "zh": "%s · %s" % [_chapter_name(str(ch)), str(bt.get("zh", ""))]})
	return out


## 存好进度，做下一步要的跳转（重新载入以后 _self_test 接着做）
func _test_go(d: Dictionary) -> void:
	var beats := _all_beats()
	if d["phase"] == "beat" and int(d["i"]) >= beats.size():
		d = {"ch0": d["ch0"], "phase": "int", "i": 0, "stage": "from"}
	if d["phase"] == "int" and int(d["i"]) >= INTERRUPTS.size():
		d = {"ch0": d["ch0"], "phase": "sample", "i": 0}
	if d["phase"] == "sample" and int(d["i"]) >= (SAMPLES.get(str(d["ch0"]), []) as Array).size():
		Engine.remove_meta(TEST_META)
		print("DEV_TEST_DONE")
		get_tree().quit()
		return
	Engine.set_meta(TEST_META, d)
	match str(d["phase"]):
		"beat":
			_jump_to(beats[int(d["i"])]["ch"], beats[int(d["i"])]["after"])
		"int":
			var fr: Array = INTERRUPTS[int(d["i"])][1]
			_jump_to(str(fr[0]), str(fr[1]))
		"sample":
			_jump_to(str(d["ch0"]), "")


## 跳到第 i 个大节点以后：到没到；再接着自动玩，能走到本章下一个大节点（本章最后一个 = 走到章节结尾）= 没被前置卡住
func _test_beat(d: Dictionary) -> void:
	var beats := _all_beats()
	var i := int(d["i"])
	var b: Dictionary = beats[i]
	visible = false
	var reached: bool = level.chapter == b["ch"] and (b["after"] == "" or StoryState.has(b["after"]))
	var nxt := ""
	if i + 1 < beats.size() and beats[i + 1]["ch"] == b["ch"]:
		nxt = beats[i + 1]["after"]
	var n0: int = StoryState.flag_order.size()
	var cont := await _play_until(nxt, 400.0)
	print("DEV_TEST beat %s（%s）: %s  接着玩到「%s」: %s  又设上 %d 个 flag" % [b["zh"], b["after"] if b["after"] != "" else "开头",
		"ok" if reached else "MISSING", _nm("flags", nxt) if nxt != "" else "章节结尾", "ok" if cont else "STUCK",
		StoryState.flag_order.size() - n0])
	d["i"] = i + 1
	_test_go(d)


## 驾驶舱小游戏 / 演出做完（直接回剖面）。没有 dev_skip 的（cockpit_dash 往前一冲：自动玩本来就照真实时长 7 秒播完）不管
func _cockpit_skip() -> void:
	if story.cockpit_ui != null and story.cockpit_ui.has_method("dev_skip"):
		story.cockpit_ui.dev_skip()


## 自动玩到 flag 设上（flag 为空 = 到章节结尾），最多 limit 秒
func _play_until(flag: String, limit: float) -> bool:
	var waited := 0.0
	story.auto = "main"
	while waited < limit and not story.ended and not (flag != "" and StoryState.has(flag)):
		await _wait(0.25)
		waited += 0.25
		if story.cockpit_ui != null:
			_cockpit_skip()
	story.auto = ""
	story.dlg.auto_delay = -1.0
	return StoryState.has(flag) if flag != "" else story.ended


func _in_state(kind: String) -> bool:
	match kind:
		"对话":
			return story.busy and story.dlg.is_open() and not story.dlg.picking() and not story.dlg.menu_open()
		"点选":
			return story.dlg.picking() or story.dlg.menu_open()
		"小游戏":
			return story.mech_wait or story.mech_running != ""
		"驾驶舱小游戏":
			return story.cockpit_ui != null
	return false


## 剧情播到 INTERRUPTS 那种时候：真的按 F8、真的点地图的方块（从 viewport 进输入，和作者手点一样），看能不能干净地跳走
func _test_interrupt(d: Dictionary) -> void:
	var it: Array = INTERRUPTS[int(d["i"])]
	if d["stage"] == "from":
		visible = false
		story.auto = "main"
		var waited := 0.0
		while not _in_state(str(it[0])) and waited < 300.0 and not story.ended:
			await get_tree().process_frame
			waited += get_process_delta_time()
			if story.cockpit_ui != null and str(it[0]) != "驾驶舱小游戏":
				_cockpit_skip()
		d["hit"] = _in_state(str(it[0]))
		d["scene"] = str(story._cur_scene) if story.busy else "-"
		_push(_key(KEY_F8, true))
		_push(_key(KEY_F8, false))
		await get_tree().process_frame
		d["open"] = visible
		d["stage"] = "to"
		Engine.set_meta(TEST_META, d)
		_set_tab(0)
		_map_show(str(it[2][0]))
		var b: Button = null
		for bb in _map_blocks:
			if bb["room"] == str(it[2][1]):
				b = bb["b"]
		if b == null:
			print("DEV_TEST interrupt %s: 地图上没有 %s FAILED" % [it[0], it[2]])
			d["i"] = int(d["i"]) + 1
			d["stage"] = "from"
			_test_go(d)
			return
		(_pages[0] as ScrollContainer).ensure_control_visible(b)
		await get_tree().process_frame
		await get_tree().process_frame
		var c := b.get_global_rect().get_center()
		_push(_click(c, true))
		_push(_click(c, false))
		await _wait(1.0)
		print("DEV_TEST interrupt %s: 点了按钮没跳 FAILED" % it[0])     # 跳了的话这个节点已经没了，走不到这里
		d["i"] = int(d["i"]) + 1
		d["stage"] = "from"
		_test_go(d)
		return
	visible = false
	var to: Array = it[2]
	var reached: bool = level.chapter == str(to[0]) and level.free_roam == str(to[1]) and str(story.world.room) == str(to[1])
	print("DEV_TEST interrupt %s（%s scene=%s，F8 开面板=%s）→ 地图 %s · %s（自由探索）: %s" % [it[0],
		"打断时正在" if d["hit"] else "没等到这种时候 NOT_HIT", d["scene"], d["open"], _chapter_name(str(to[0])),
		_nm("rooms", str(to[1])), "ok" if reached else "MISSING（在 %s · %s）" % [level.chapter, story.world.room]])
	d["i"] = int(d["i"]) + 1
	d["stage"] = "from"
	_test_go(d)


func _push(e: InputEvent) -> void:
	get_viewport().push_input(e, true)


func _key(k: Key, down: bool) -> InputEventKey:
	var e := InputEventKey.new()
	e.keycode = k
	e.physical_keycode = k
	e.pressed = down
	return e


func _click(p: Vector2, down: bool) -> InputEventMouseButton:
	var e := InputEventMouseButton.new()
	e.button_index = MOUSE_BUTTON_LEFT
	e.position = p
	e.global_position = p
	e.pressed = down
	return e


## 状态页抽查：从本章开头点一个中后段的 flag（原地补齐，不走重新载入），再接着自动玩能设上新 flag（或到章节结尾）
func _check_sample(d: Dictionary) -> void:
	var f := str(SAMPLES[str(d["ch0"])][int(d["i"])])
	await _settle(90.0)                       # 重开本章的开场（森林起身 / 驾驶舱起飞过场）先播完
	var n0: int = StoryState.flag_order.size()
	var items0: int = Inventory.owned.size()
	if StoryState.has(f):
		print("DEV_TEST sample flag %s: 开场就已经设上了（换个靠后的抽查）" % f)
	else:
		_set_tab(TABS.find("状态"))
		await level.dev_complete(f)
	var filled := "flag +%d 物品 %+d" % [StoryState.flag_order.size() - n0, Inventory.owned.size() - items0]
	var reached: bool = StoryState.has(f)
	await _settle(90.0)                       # 跳完接着播的那段（别的章节停在目标后面的）
	var n1: int = StoryState.flag_order.size()
	var waited := 0.0
	if not story.ended:
		story.auto = "main"
		while StoryState.flag_order.size() < n1 + 2 and not story.ended and waited < 120.0:
			await _wait(0.25)
			waited += 0.25
			if story.cockpit_ui != null:
				_cockpit_skip()
		story.auto = ""
		story.dlg.auto_delay = -1.0
	var cont: bool = story.ended or StoryState.flag_order.size() >= n1 + 2
	print("DEV_TEST sample flag %s: %s  continue=%s  状态页原地补齐 %s  接着玩又设上 %d 个%s" % [f,
		"ok" if reached else "MISSING", "ok" if cont else "STUCK", filled,
		StoryState.flag_order.size() - n1, "（到章节结尾）" if story.ended else ""])
	d["i"] = int(d["i"]) + 1
	_test_go(d)


# ======================================================================= 每帧
## 面板自己先接输入（它总排在关卡子节点的最后，_input 倒着叫，它最先拿到）：
## F8 开关面板；面板上的鼠标点击 / 滚轮在这里自己处理掉。不这样的话剧情播着的时候对话框、点选、小游戏的 _input
## 会先把点击吃了，按钮收不到（「剧情的时候不能跳」）
func _input(e: InputEvent) -> void:
	if e is InputEventKey and e.pressed and not e.echo and e.keycode == KEY_F8:
		get_viewport().set_input_as_handled()
		toggle()
		return
	if not visible:
		return
	if e is InputEventMouseButton:
		var mb := e as InputEventMouseButton
		if not _root.get_global_rect().has_point(mb.position):
			return
		get_viewport().set_input_as_handled()       # 先标掉：按钮可能马上重新载入场景，之后就没有 viewport 了
		if not mb.pressed:
			return
		if mb.button_index == MOUSE_BUTTON_LEFT:
			_map_click = mb.position                # 地图：点在方块的哪儿
			var b := _hit(mb.position)
			if b != null and not b.disabled:
				b.pressed.emit()
		elif mb.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			var sc := _pages[_tab] as ScrollContainer
			sc.scroll_vertical += 24 * (-1 if mb.button_index == MOUSE_BUTTON_WHEEL_UP else 1)
		return
	if e is InputEventKey and e.pressed and not e.echo:
		var k: int = e.keycode
		if k == KEY_TAB:
			_set_tab((_tab + 1) % TABS.size())
			get_viewport().set_input_as_handled()
		elif k >= KEY_1 and k < KEY_1 + TABS.size():
			_set_tab(k - KEY_1)
			get_viewport().set_input_as_handled()


## 鼠标下面是哪个按钮（页面里的要在滚动框露出来的那部分里）
func _hit(p: Vector2) -> Button:
	for n in _root.find_children("*", "Button", true, false):
		var b := n as Button
		if not b.is_visible_in_tree() or not b.get_global_rect().has_point(p):
			continue
		var sc := b.get_parent()
		while sc != null and not sc is ScrollContainer and sc != _root:
			sc = sc.get_parent()
		if sc is ScrollContainer and not (sc as Control).get_global_rect().has_point(p):
			continue
		return b
	return null


func _process(delta: float) -> void:
	# 快走：只把晨这一帧走的距离再加两倍（这个节点在晨后面处理，晨的动画照常 100ms 一帧）；自由探索里按住 Shift 也再加
	var chen: Node2D = level.chen
	var more := 2.0 if fast else 0.0
	if level.free_roam != "" and Input.is_key_pressed(KEY_SHIFT) and chen.input_enabled:
		more += level.FREE_SHIFT
	if more > 0.0 and not is_nan(_last_x) and chen._vel > 0.0:
		var dx := chen.position.x - _last_x
		if absf(dx) < 20.0:
			chen.position.x = round(chen.position.x + dx * more)
	_last_x = chen.position.x
	if get_index() < level.get_child_count() - 1:
		level.move_child.call_deferred(self, -1)     # 剧情后来加到关卡上的节点（小游戏等）排到面板后面，面板的 _input 还是最先
	if skip_dialog and story.dlg.auto_delay != 0.15:
		story.dlg.auto_delay = 0.15
	_overlay.visible = show_ranges
	if show_ranges:
		_overlay.queue_redraw()
	if not visible:
		return
	_refresh_t -= delta
	if _refresh_t > 0.0:
		return
	_refresh_t = 0.2
	_free_refresh()
	var scene: String = story._cur_scene if story.busy else ""
	var st: String = level.S.keys()[level.state]
	var room := str(story.world.room)
	var bag: Array[String] = []
	for id in Inventory.owned:
		bag.append(_item_name(str(id)))
	_state_label.text = "场景: %s  步: %d\n位置 x: %d  房间: %s\n状态: %s%s\n背包: %s" % [
		_nm("scenes", scene) if scene != "" else "—", story.step_i, int(chen.position.x), _nm("rooms", room),
		_nm("states", st), "（带路中）" if story.free_walk else "", "、".join(bag) if not bag.is_empty() else "空"]
	_state_label.tooltip_text = "scene=%s  room=%s  state=%s\nitems=%s" % [scene if scene != "" else "-", room, st,
		", ".join(Inventory.owned)]
	for f in _flag_btns:
		(_flag_btns[f] as Button).modulate = Color(1.35, 1.3, 1.0) if StoryState.has(f) else Color(0.6, 0.6, 0.6)
	# 地图：晨在的房间亮黄，小点跟着晨
	for d in _map_blocks:
		var cur: bool = _map_ch == level.chapter and d["room"] == room
		(d["b"] as Button).modulate = Color(1.5, 1.35, 0.75) if cur else Color.WHITE
	_map_top.queue_redraw()
	_sync_switches()


## 显示范围：marker 竖线（屋里的点淡一点）+ 每个能用的 hotspot 的互动范围
func _draw_overlay() -> void:
	var f := UITheme.font()
	var w = story.world
	for n in w.markers:
		var x := float(w.markers[n])
		var room := str(n).begins_with("room_")
		var c := Color(0.9, 0.75, 0.4, 0.5) if not room else Color(0.6, 0.8, 0.9, 0.45)
		_overlay.draw_line(Vector2(x, 60), Vector2(x, 232), c, 1.0)
		_overlay.draw_string(f, Vector2(x + 2, 70 + (12 if room else 0)), _nm("markers", str(n)), HORIZONTAL_ALIGNMENT_LEFT, -1, 14, c)
	for p in story.hotspots.available():
		var h: Dictionary = p["h"]
		var r: float = story.hotspots.range_of(h)
		var x := float(p["x"])
		var gy: float = w.ground_at(x)
		var col := Color(0.4, 1.0, 0.6, 0.25) if not story.hotspots.is_enter(h) else Color(1.0, 0.5, 0.4, 0.3)
		_overlay.draw_rect(Rect2(x - r, gy - 4, r * 2.0, 6), col)
		_overlay.draw_rect(p["rect"], Color(col, 0.6), false, 1.0)
	var wl: Vector2 = w.walls(level.chen.position.x)
	for x in [wl.x, wl.y]:
		_overlay.draw_line(Vector2(x, 40), Vector2(x, 240), Color(1, 0.3, 0.3, 0.6), 1.0)
