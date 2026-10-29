extends Node
## 章节剧情引擎：读剧本 JSON（默认 data/story_forest.json，没有就退回 data/story_forest_sample.json），播 scene、管 hotspot、
## 自动玩、跳节拍、检查剧本。剧本格式和全部步骤见 docs/forest_chapter.md「剧本数据格式」。level_forest.gd 在 _ready 里建它。
##
## 拆成几块：
##   story_state.gd     flags / 日记 / 物件状态 / 用过的 hotspot（以后存档存这一份）
##   story_world.gd     markers、墙、物件（缺图色块）、树屋室内、雾
##   hotspots.gd        哪些点能用、提示箭头、晨身边 / 鼠标点到的那个
##   story_dialogue.gd  头顶对话框、旁白、拿到东西的提示、点选、结束卡
##   这里              一步一步播 scene（每步一个 await）、自动玩、跳节拍、统计、检查
##
## 播放：play(scene) 是协程，播完返回；goto / pick 跳到别的 scene（不回来）。剧情播放时锁晨、黑边按需（_wants_bars）。
## 引擎和剧本对接的点（剧本里有就用，没有就用关卡原来的）：
##   开场爬起来以后：hooks.crash，或第一个存在的 crash_wake / wake / crash / intro / opening
##   开场爬起来以后（真剧本：intro，设 crashed）
##   发光木头：保留关卡原来的拾取过场（走过去、弯腰、木头飞进背包、燃烧值滚动）。剧本里 at = wood 的 hotspot（wood / wood_last）
##     不单独出现，过场里播它的 scene（第一个能用的那个），scene 里的 anim pickup 和 give（已经给过的东西）跳过；引擎再设 got_wood。
##     没有这种 hotspot 就找 hooks.wood，或 wood_found / wood / wood_pickup / pickup_wood / glowing_wood
##   燃烧值刚到 launch_burn（设了 fuel_full）以后：hooks.fuel_full，或 fuel_full / fuel_ready
## 第二版步骤（设计文档末尾「补充步骤」）：hotspot 的 trigger:"enter" / range；walk / guide 的 wait:false、speed；
##   ambient（循环环境声，AudioStreamPlayer2D 放在 marker 上：音量随距离、左右声道随方位）；show_item；if（flag 可写 "!名字"）。
##   缺的音效文件静默跳过（STORY_CHECK 里列出来）。
## 不推人（作者的规矩）：走进 trigger:"enter" 的点触发的 scene 里，「晨 walk」一律不执行（不能用台词 + 自动走路把玩家推回去；
##   该停的地方由 story_world.gd 的「看得见的边」挡住）。--story_check 会把这种步骤列出来。
## 引擎扩展（设计文档之外、可选）：hotspot 的 at = NPC 名（跟着角色）；
##   show / hide 的 who 也可以是物件 id；pick 选项的 "correct": true；
##   flag 步骤的 "clear"；剧本顶层的 "items"（items.json 里没有的物品先用它顶上）、"hooks"。
##
## 调试参数（level_forest.gd 转过来）：
##   --story=<路径>          用哪份剧本（res:// 或绝对路径）
##   --story_auto            自动玩：对话每句停 0.6 秒自己下一句、自己走到下一个该去的 hotspot、点选时选对的那个，一直到结束卡，
##                           打印 STORY_DONE 和统计后退出。--story_auto=full：闲聊、选错的分支也都走一遍（看全部 scene）
##   --story_shots=<目录>    每播到一个新 scene 0.5 秒后存一张图（文件名带序号和 scene id）
##   --beat=<flag>           直接跳到「设这个 flag 的那个 scene 播完」的样子（瞬间把前面的都过一遍：flags、物品、NPC 位置都对）
##   --story_check           只检查剧本（引用不到的 marker / scene / item、不支持的步骤……），打印 STORY_CHECK 后退出

const DEFAULT_STORY := "res://data/story_forest.json"
const SAMPLE_STORY := "res://data/story_forest_sample.json"
const SFX_DIR := "res://audio/sfx/"
const STEPS := ["say", "narr", "walk", "face", "wait", "show", "hide", "give", "take", "flag", "journal", "sfx",
	"fade_to", "anim", "prop", "guide", "goto", "pick", "end_chapter", "if", "ambient", "show_item"]
const HOOKS := {
	"crash": ["crash_wake", "wake", "crash", "intro", "opening"],
	"wood": ["wood_found", "wood", "wood_pickup", "pickup_wood", "glowing_wood"],
	"fuel_full": ["fuel_full", "fuel_ready"],
}
const ENGINE_FLAGS := ["crashed", "got_wood", "fuel_full"]
const NAME_COLORS := {"chen": Color("#c48fb4"), "deer": Color("#c9a882"), "miluo": Color("#d6c486"), "voice": Color("#8fa69a")}
const HEAD := {"chen": 50.0, "deer": 52.0, "miluo": 50.0}
const ANIM_MAP := {
	"chen": {"look": "idle_eye", "pickup": "pickup", "idle": "idle", "getup": "getup", "lie": "lie"},
	"deer": {"graze": "graze_down", "graze_down": "graze_down", "graze_up": "graze_up", "look": "look", "ear": "ear", "idle": "idle"},
	"miluo": {"idle": "idle"},
}
const GUIDE_NEAR := 60.0
const AUTO_LINE := 0.6
const WORLD_GD := preload("res://scripts/story_world.gd")
const HOTSPOTS_GD := preload("res://scripts/hotspots.gd")
const DIALOGUE_GD := preload("res://scripts/story_dialogue.gd")

var level: Node2D
var path := ""
var data := {}
var scenes := {}
var speakers := {}
var hotspot_defs: Array = []
var world: Node2D
var hotspots: Node2D
var dlg: Control
var chen: Node2D
var deer: Node2D
var miluo: Node2D

var busy := false
var free_walk := false             # guide：剧情没播完，但晨可以自己走
var auto := ""                     # "" / "main" / "full"
var ff := false                    # 跳节拍：每步瞬间完成
var shots_dir := ""
var shot_delay := 0.5
var ended := false

# 统计
var played := {}
var played_order: Array[String] = []
var lines := 0
var hotspots_used := 0
var _t0_ms := 0
var _game_t := 0.0
var _cur_scene := ""
var _visited := {}                 # 自动玩：hotspot id → 来的时候的 StoryState.changed
var _wrong_tried := {}
var _target: Dictionary = {}
var _idle_t := 0.0
var _shot_n := 0
var _warned := {}
var _wood_mode := false             # 在关卡的木头拾取过场里播剧本：跳过 anim pickup、已经给过的 give
var _ambient := {}                   # "name@at" → AudioStreamPlayer2D
var _item_show: TextureRect          # show_item 举着的那件
var _item_show_until_say := false
var missing_sfx := {}
var _family: Array = []              # 正在响的音乐盒 / 留声机音效
var step_i := -1                     # 正在播的 scene 的第几步（开发者面板、卡死检测用）
var step_t := 0.0                    # 这一步播了多久
var _enter_scene := false            # 这段剧情是走进 trigger:"enter" 的点触发的（不许推晨走）
var speaking := ""                   # 正在说话的人（关卡用它判断前景层有没有挡住）
var _npc_room := {}                  # 角色在屋里还是屋外：节点名 → forest / treehouse


# ======================================================================= 读剧本
func load_story(p: String) -> void:
	path = p if p != "" else DEFAULT_STORY
	if not _exists(path):
		if p != "":
			push_warning("剧本不存在：%s，用小样" % path)
		path = SAMPLE_STORY
	var d = JSON.parse_string(FileAccess.get_file_as_string(path)) if _exists(path) else null
	if not d is Dictionary:
		push_error("剧本读不了（JSON 不对？）：" + path)
		if path != SAMPLE_STORY and _exists(SAMPLE_STORY):
			path = SAMPLE_STORY
			d = JSON.parse_string(FileAccess.get_file_as_string(path))
	data = d if d is Dictionary else {}
	scenes = data.get("scenes", {})
	speakers = data.get("speakers", {})
	hotspot_defs = data.get("hotspots", [])
	for it in data.get("items", []):
		if it is Dictionary:
			Inventory.register_fallback(it)


static func _exists(p: String) -> bool:
	return FileAccess.file_exists(p)


func setup(lv: Node2D, ui_root: Control) -> void:
	level = lv
	chen = lv.chen
	deer = lv.get_node("Deer")
	miluo = lv.get_node("Snake")
	_t0_ms = Time.get_ticks_msec()
	world = WORLD_GD.new()
	world.name = "StoryWorld"
	lv.add_child(world)
	world.setup(lv, data.get("markers", {}), _steam_pipe())
	hotspots = HOTSPOTS_GD.new()
	hotspots.name = "Hotspots"
	lv.add_child(hotspots)
	lv.move_child(hotspots, chen.get_index() + 1)
	dlg = DIALOGUE_GD.new()
	dlg.name = "StoryDialogue"
	ui_root.add_child(dlg)
	hotspots.setup(self, world, hotspot_defs, ui_root)
	# 角色的起始位置：鹿藏着（启动失败那一幕才出来），弥洛在树屋里
	deer.visible = false
	_place(miluo, world.mx("room_miluo"), "treehouse")
	miluo.visible = true
	_npc_room[deer.name] = "forest"


## 管道那个点选里「对的」那段（细白汽冒在它上面）
func _steam_pipe() -> String:
	for id in scenes:
		for st in scenes[id]:
			if st is Dictionary and str(st.get("do", "")) == "pick":
				var opts: Array = st.get("options", [])
				var ok := _correct_index(st, str(id))
				if ok >= 0 and str(opts[ok].get("id", "")).begins_with("pipe"):
					return str(opts[ok]["id"])
	return ""


func has_scene(id: String) -> bool:
	return scenes.has(id)


func hook(kind: String) -> String:
	if kind == "wood":
		var wh := _wood_hotspot()
		if not wh.is_empty():
			return str(wh.get("scene", ""))
	var h: Dictionary = data.get("hooks", {})
	if h.has(kind) and scenes.has(str(h[kind])):
		return str(h[kind])
	for c in HOOKS.get(kind, []):
		if scenes.has(c):
			return c
	return ""


## 剧本里放在发光木头上的 hotspot（第一个条件满足的）
func _wood_hotspot() -> Dictionary:
	for h in hotspot_defs:
		if h is Dictionary and str(h.get("at", "")) == "wood" and scenes.has(str(h.get("scene", ""))):
			if StoryState.all_of(h.get("need", [])) and StoryState.none_of(h.get("not", [])):
				return h
	for h in hotspot_defs:
		if h is Dictionary and str(h.get("at", "")) == "wood" and scenes.has(str(h.get("scene", ""))):
			return h
	return {}


## 关卡自己管的点：木头还在地上时，at = wood 的 hotspot 交给拾取过场
func hotspot_blocked(h: Dictionary) -> bool:
	return str(h.get("at", "")) == "wood" and level.wood_available()


## 木头拾取过场里播剧本
func play_wood(id: String) -> void:
	_wood_mode = true
	var wh := _wood_hotspot()
	if not wh.is_empty():
		StoryState.mark_used(str(wh.get("id", "")))
		hotspots_used += 1
	await play(id, false)
	_wood_mode = false


func npc(who: String) -> Node2D:
	match who:
		"chen":
			return chen
		"deer":
			return deer
		"miluo", "milo", "snake":
			return miluo
	return null


## 文字：当前语言，空的就回落中文
func txt(d) -> String:
	return str(txt_lang(d)[0])


## 文字和它实际用的是哪种语言：[文字, "zh"/"en"]（台词回落到中文时，说话人名字也跟着用中文）
func txt_lang(d) -> Array:
	if d is Dictionary:
		var s := str(d.get(I18n.lang, ""))
		if s != "":
			return [s, I18n.lang]
		s = str(d.get("zh", ""))
		if s != "":
			return [s, "zh"]
		return [str(d.get("en", "")), "en"]
	if d == null:
		return ["", I18n.lang]
	return [str(d), I18n.lang]


## 名字取指定语言，那种语言没写就退回 txt
func txt_in(d, lang: String) -> String:
	if d is Dictionary and str(d.get(lang, "")) != "":
		return str(d[lang])
	return txt(d)


func _warn_once(msg: String) -> void:
	if _warned.has(msg):
		return
	_warned[msg] = true
	push_warning("剧本：" + msg)


# ======================================================================= 播
func play(id: String, manage := true) -> void:
	if busy:
		_warn_once("已经在播，忽略 " + id)
		return
	busy = true
	hotspots.active = false
	if manage and not ff:
		level.story_begin(_wants_bars(id))
		dlg.top_limit = level.BAR_H + 4.0 if level.bars_on() else 4.0
	var cur := id
	var hops := 0
	var fuel_before := StoryState.has("fuel_full")
	while cur != "" and hops < 200 and not ended:
		hops += 1
		if not scenes.has(cur):
			_warn_once("没有这个 scene：" + cur)
			break
		_on_scene(cur)
		var next := ""
		step_i = -1
		for st in scenes[cur]:
			step_i += 1
			step_t = 0.0
			if not st is Dictionary:
				continue
			var g: String = await _step(st)
			if ended:
				break
			if g != "":
				next = g
				break
		cur = next
	dlg.close_box()
	free_walk = false
	step_i = -1
	if manage and not ff and not ended:
		level.story_end()
	busy = false
	hotspots.active = true
	if not ended and not fuel_before:
		await check_fuel_hook()


## 燃烧值刚到 200：剧本里有 fuel_full 场景就接着播
func check_fuel_hook() -> void:
	if not StoryState.has("fuel_full") or busy:
		return
	var h := hook("fuel_full")
	if h != "" and not played.has(h):
		await play(h)


func _on_scene(id: String) -> void:
	_cur_scene = id
	var first := not played.has(id)
	played[id] = int(played.get(id, 0)) + 1
	played_order.append(id)
	if ff:
		return
	if auto != "":
		print("STORY_SCENE %s  t=%.1f" % [id, _game_t])
	if first and shots_dir != "":
		_shot(id)


func _shot(id: String) -> void:
	_shot_n += 1
	var n := _shot_n
	await get_tree().create_timer(shot_delay).timeout
	level._save(shots_dir.path_join("%03d_%s.png" % [n, id.validate_filename()]))


func _wants_bars(id: String) -> bool:
	var says := 0
	for st in scenes.get(id, []):
		if not st is Dictionary:
			continue
		if st.has("say"):
			says += 1
		if str(st.get("do", "")) in ["walk", "guide", "fade_to", "anim", "show", "pick", "end_chapter"]:
			return true
	return says >= 4


## 一步。返回下一个 scene（goto / pick），"" = 接着播这个 scene
func _step(st: Dictionary) -> String:
	if st.has("say"):
		await _say(st)
		return ""
	if st.has("narr"):
		await _narr(st)
		return ""
	var d := str(st.get("do", ""))
	match d:
		"walk":
			await _walk(st)
		"face":
			_face(st)
		"wait":
			if not ff:
				await _wait(float(st.get("sec", 0.5)))
		"show":
			_show(st, true)
		"hide":
			_show(st, false)
		"give":
			await _give(str(st.get("item", "")))
		"take":
			_take(str(st.get("item", "")))
		"flag":
			if st.has("set"):
				StoryState.set_flag(str(st["set"]))
			if st.has("clear"):
				StoryState.clear_flag(str(st["clear"]))
		"journal":
			_journal(st)
		"sfx":
			_sfx(st)
		"fade_to":
			await _fade_to(st)
		"anim":
			_anim(st)
		"prop":
			world.set_prop(str(st.get("id", "")), str(st.get("state", "")))
		"guide":
			await _guide(st)
		"goto":
			return str(st.get("scene", ""))
		"pick":
			var s: String = await _pick(st)
			return s
		"end_chapter":
			await _end_chapter()
		"if":
			var f := str(st.get("flag", ""))
			var yes := not StoryState.has(f.substr(1)) if f.begins_with("!") else StoryState.has(f)
			var to := str(st.get("then" if yes else "else", ""))
			if to == "":
				return ""
			return to
		"ambient":
			_ambient_step(st)
		"show_item":
			_show_item(st)
		_:
			_warn_once("不认识的步骤：" + JSON.stringify(st))
	return ""


func _wait(sec: float) -> void:
	var t := 0.0
	while t < sec:
		await get_tree().process_frame
		t += get_process_delta_time()


# ----------------------------------------------------------------------- 说话
func _say(st: Dictionary) -> void:
	lines += 1
	if ff:
		return
	var who := str(st["say"])
	var tl := txt_lang(st)
	var text: String = tl[0]
	speaking = who
	var n := npc(who)
	# 别人说话时，站着的晨转过去看说话的人
	if n != null and n != chen and n.visible and chen._vel <= 0.0:
		chen._set_facing(1 if n.position.x > chen.position.x else -1)
	var nm := txt_in(speakers.get(who, who), str(tl[1]))
	await dlg.say(nm, NAME_COLORS.get(who, UITheme.ACCENT), text, _anchor.bind(who))
	speaking = ""
	if _item_show != null and _item_show_until_say:
		_drop_item_show()


func _anchor(who: String) -> Vector2:
	var left: Vector2 = level.cam_left()
	var n := npc(who)
	if n != null and n.visible:
		return n.position - left + Vector2(0, -float(HEAD.get(who, 50.0)))
	# 画面外的声音：树屋在屏幕里就从门那边来（屋里的人隔着门说话），不然屏幕上方中间
	if not world.in_room():
		var dx: float = float(world.house["door"]) - left.x
		if dx > 30.0 and dx < 450.0:
			return Vector2(dx, float(world.house["floor"]) - left.y - 44.0)
	return Vector2(240, 44 if not level.bars_on() else 44 + level.BAR_H)


func _narr(st: Dictionary) -> void:
	lines += 1
	if ff:
		return
	var text := txt(st["narr"])
	await dlg.narr(text, clampf(0.9 + text.length() * 0.08, 1.4, 3.0))


# ----------------------------------------------------------------------- 走 / 转身 / 出现
## to → {ok, x, room}：marker / 物件 / 数字 / 角色名（走到那个角色旁边）
func _resolve(to, who := "chen") -> Dictionary:
	if to is String:
		var n := npc(str(to))
		if n != null:
			var me := npc(who)
			var side := -1.0 if me == null or me.position.x < n.position.x else 1.0
			return {"ok": true, "x": n.position.x + side * 24.0, "room": world.room}
	var r: Dictionary = world.resolve(to)
	if not r["ok"]:
		_warn_once("找不到位置：" + str(to))
	return r


func _walk(st: Dictionary) -> void:
	var who := str(st.get("who", "chen"))
	var r := _resolve(st.get("to", 0), who)
	if not r["ok"]:
		return
	var x: float = r["x"]
	var n := npc(who)
	if n == null:
		_warn_once("walk：不认识 " + who)
		return
	if ff:
		_place(n, x, world.room if n == chen else _room_of(n))
		return
	var wait: bool = st.get("wait", true)
	match who:
		"chen":
			if _enter_scene:
				return                       # 不推人：走进来触发的剧情不让晨自己走（停在看得见的边上）
			if st.has("speed"):
				_warn_once("walk：晨的 speed 不支持（晨的速度在 chen.gd 里，不改），按平常速度走")
			var w: Vector2 = world.walls(chen.position.x)
			x = clampf(x, w.x + 4.0, w.y - 4.0)
			if wait:
				await _chen_walk(x)
			else:
				_chen_walk(x)
		"deer":
			deer.visible = true
			_deer_go(x, st)
			while wait and _deer_moving():
				await get_tree().process_frame
		_:
			miluo.visible = true
			miluo.glide_to(x, float(st.get("speed", miluo.GLIDE_SPEED)))
			while wait and miluo.is_gliding():
				await get_tree().process_frame


## 鹿：剧本 speed ≤ 60 = 走路（npc_deer.gd 的 walk_to，不传速度：它自己的 WALK_SPEED 是蹄子不打滑的唯一速度），
## 不然跑（run_to）；没有 walk_to 就都跑
func _deer_go(x: float, st: Dictionary) -> void:
	var sp := float(st.get("speed", deer.RUN_SPEED))
	if sp <= 60.0 and deer.has_method("walk_to"):
		deer.call("walk_to", x)
	else:
		deer.run_to(x, sp)


func _deer_moving() -> bool:
	if deer.has_method("is_walking") and bool(deer.call("is_walking")):
		return true
	return deer.is_running()


func _chen_walk(x: float) -> void:
	var t := 0.0
	var dir := signf(x - chen.position.x)
	while dir != 0.0:
		var d := x - chen.position.x
		if absf(d) <= 2.0 + chen.stop_distance() or signf(d) != dir:
			break
		chen.auto_dir = dir
		await get_tree().process_frame
		t += get_process_delta_time()
		if t > 20.0:
			chen.position.x = x
			break
	chen.auto_dir = 0.0
	t = 0.0
	while chen._vel > 0.0 and t < 1.0:
		await get_tree().process_frame
		t += get_process_delta_time()


func _face(st: Dictionary) -> void:
	var n := npc(str(st.get("who", "chen")))
	if n == null:
		return
	var to = st.get("to", 0)
	var tx := 0.0
	var tn := npc(str(to)) if to is String else null
	if tn != null:
		tx = tn.position.x
	else:
		var r: Dictionary = world.resolve(to)
		if not r["ok"]:
			_warn_once("face：找不到 " + str(to))
			return
		tx = r["x"]
	if absf(tx - n.position.x) < 1.0:
		return
	n._set_facing(1 if tx > n.position.x else -1)


func _show(st: Dictionary, on: bool) -> void:
	var who := str(st.get("who", ""))
	var n := npc(who)
	if n == null:
		world.set_prop(who, "show" if on else "hidden")     # 引擎扩展：物件也能 show / hide
		return
	if st.has("at"):
		var r: Dictionary = world.resolve(st["at"])
		if r["ok"]:
			_place(n, r["x"], r["room"])
		else:
			_warn_once("show：找不到 " + str(st["at"]))
	n.visible = on
	sync_npc_vis(true)


func _room_of(n: Node2D) -> String:
	return str(_npc_room.get(n.name, "forest"))


## 把角色直接放到 x（房间 r 的地面上），停掉正在跑 / 滑
func _place(n: Node2D, x: float, r: String) -> void:
	if n == deer and _deer_moving():
		deer._running = false
		if "_walking" in deer:
			deer.set("_walking", false)
		deer._idle(2.0)
	if n == miluo and miluo.is_gliding():
		miluo._gliding = false
	if n == chen:
		chen.auto_dir = 0.0
		chen._vel = 0.0
	n.position = Vector2(round(x), round(world.ground_at(x, r)) + 1.0)
	_npc_room[n.name] = r


## 屋里屋外：和晨不在同一边、又站在树屋图范围里的角色淡掉（晨进屋时屋外门口的鹿；晨在屋外时屋里的弥洛本来就被前墙挡着）
func sync_npc_vis(instant := false) -> void:
	for n in [deer, miluo]:
		var nd: Node2D = n
		var away: bool = _room_of(nd) != world.room and world.in_house_span(nd.position.x)
		var a := 0.0 if away and world.in_room() else 1.0
		if instant or ff:
			nd.modulate.a = a
		elif not is_equal_approx(nd.modulate.a, a):
			create_tween().tween_property(nd, "modulate:a", a, 0.5)


func _anim(st: Dictionary) -> void:
	if ff:
		return
	var who := str(st.get("who", ""))
	var name := str(st.get("name", ""))
	if _wood_mode and who == "chen" and name == "pickup":
		return                    # 过场里已经弯过腰了
	var n := npc(who)
	var key := "miluo" if n == miluo else who
	var m: Dictionary = ANIM_MAP.get(key, {})
	if n == null or not m.has(name):
		_warn_once("anim：%s 没有 %s" % [who, name])
		return
	var spr: AnimatedSprite2D = n.spr
	if spr.sprite_frames.has_animation(StringName(m[name])):
		spr.play(StringName(m[name]))


# ----------------------------------------------------------------------- 物品 / 日记 / 声音
func _give(id: String) -> void:
	if _wood_mode and Inventory.has(id):
		return                    # 木头拾取过场已经给过了
	if not Inventory.defined(id):
		_warn_once("物品表里没有 %s（用色块占位）" % id)
		Inventory.register_fallback({"id": id, "name": {"zh": id, "en": id}, "rarity": "common", "burn": 0, "personal": true,
			"desc": {"zh": "", "en": ""}})
	Inventory.add(id)
	level.on_inventory_changed()
	if ff:
		return
	var it := Inventory.item(id)
	var icon := Inventory.icon(id)
	dlg.toast(icon, I18n.t("got_item") % txt(it.get("name", id)))
	await _fly_to_bag(icon, chen.position + Vector2(0, -36) - level.cam_left())


func _take(id: String) -> void:
	if not Inventory.has(id):
		_warn_once("take：背包里没有 " + id)
	Inventory.remove(id)
	level.on_inventory_changed()
	if not ff:
		dlg.toast(Inventory.icon(id), I18n.t("gave_item") % txt(Inventory.item(id).get("name", id)))


func _fly_to_bag(icon: Texture2D, from: Vector2) -> void:
	var tr := TextureRect.new()
	tr.texture = icon
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tr.position = from.round()
	dlg.add_child(tr)
	var to: Vector2 = level.bag_target() - icon.get_size() / 2.0
	var tw := create_tween()
	tw.tween_property(tr, "position:y", from.y - 12.0, 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_method(func(k: float):
		var p := Vector2(from.x, from.y - 12.0).lerp(to, k)
		p.y -= sin(k * PI) * 16.0
		tr.position = p.round(), 0.0, 1.0, 0.5).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	await tw.finished
	tr.queue_free()
	level.bag_bump()


func _journal(st: Dictionary) -> void:
	StoryState.journal.append({"zh": str(st.get("zh", "")), "en": str(st.get("en", ""))})
	if not Inventory.has("journal"):
		if not Inventory.defined("journal"):
			Inventory.register_fallback({"id": "journal", "name": {"zh": "日记", "en": "Journal"}, "rarity": "common",
				"burn": 0, "personal": true, "icon": "res://art/forest_story/icon_journal.png", "desc": {"zh": "", "en": ""}})
		Inventory.add("journal")
		level.on_inventory_changed()
	if not ff:
		dlg.toast(Inventory.icon("journal"), I18n.t("journal_added"))


func _sfx(st: Dictionary) -> void:
	if ff:
		return
	var name := str(st.get("name", ""))
	var p := _sfx_path(name)
	if p == "":
		missing_sfx[name] = true       # 缺的音效静默跳过（统计里列出来）
		return
	# 音乐盒 / 留声机这一族（长声）：新的一条开始时，同族还在响的淡出 0.4 秒，免得叠在一起
	var fam := _sfx_family(name)
	if fam:
		fade_music_family()
	var a := AudioStreamPlayer2D.new()
	a.stream = load(p)
	a.bus = "SFX"
	a.max_distance = 2000.0
	a.attenuation = 0.5
	a.volume_db = float(st.get("db", 0.0))
	level.add_child(a)
	a.global_position = level.cam_left() + Vector2(240.0 + clampf(float(st.get("pan", 0.0)), -1.0, 1.0) * 320.0, 135.0)
	a.play()
	a.finished.connect(a.queue_free)
	if fam:
		_family.append(a)


static func _sfx_family(name: String) -> bool:
	return name.begins_with("musicbox_") or name.begins_with("gramophone_")


## 音乐盒 / 留声机这一族还在响的全部淡出（新的一条开始、离开树屋时）
func fade_music_family(sec := 0.4) -> void:
	for a in _family:
		if is_instance_valid(a) and (a as AudioStreamPlayer2D).playing:
			var tw := create_tween()
			tw.tween_property(a, "volume_db", -60.0, sec)
			tw.tween_callback((a as Node).queue_free)
	_family.clear()


## 循环环境声：放在 marker 上的 AudioStreamPlayer2D（镜头是听的人：越远越小、左右跟着方位）。没有文件就只记下来、不响。
func _ambient_step(st: Dictionary) -> void:
	var name := str(st.get("name", ""))
	var key := name + "@" + str(st.get("at", ""))
	var on: bool = st.get("on", true)
	if not on:
		if _ambient.has(key):
			var a: AudioStreamPlayer2D = _ambient[key]
			var tw := create_tween()
			tw.tween_property(a, "volume_db", -60.0, 0.8)
			tw.tween_callback(a.queue_free)
			_ambient.erase(key)
		return
	if ff or _ambient.has(key):
		return
	var p := _sfx_path(name)
	if p == "":
		missing_sfx[name] = true
		return
	var r: Dictionary = world.resolve(st.get("at", 0))
	var a := AudioStreamPlayer2D.new()
	a.stream = load(p)
	a.bus = "SFX"
	a.max_distance = float(st.get("dist", 520.0))
	a.attenuation = 1.6
	a.volume_db = float(st.get("db", 0.0))
	level.add_child(a)
	a.global_position = Vector2(float(r.get("x", 0.0)), 200.0)
	a.finished.connect(a.play)       # 循环（.import 里已经设了 loop 的音效不会发 finished，这句就不起作用，也没关系）
	a.play()
	_ambient[key] = a


func _sfx_path(name: String) -> String:
	for ext in [".wav", ".ogg", ".mp3"]:
		if ResourceLoader.exists(SFX_DIR + name + ext):
			return SFX_DIR + name + ext
	return ""


## 晨把一件东西举起来给人看：图标在晨头顶前方，到下一句说完（或 sec 秒）
func _show_item(st: Dictionary) -> void:
	if ff:
		return
	_drop_item_show()
	var id := str(st.get("item", ""))
	var tr := TextureRect.new()
	tr.texture = Inventory.icon(id)
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dlg.add_child(tr)
	_item_show = tr
	_item_show_until_say = not st.has("sec")
	tr.set_meta("t", 0.0)
	if st.has("sec"):
		var me := tr
		get_tree().create_timer(float(st["sec"])).timeout.connect(func():
			if _item_show == me:
				_drop_item_show())


func _drop_item_show() -> void:
	if _item_show != null and is_instance_valid(_item_show):
		_item_show.queue_free()
	_item_show = null


func _update_item_show(delta: float) -> void:
	if _item_show == null or not is_instance_valid(_item_show):
		return
	var t: float = float(_item_show.get_meta("t")) + delta
	_item_show.set_meta("t", t)
	var sz := _item_show.texture.get_size()
	var left: Vector2 = level.cam_left()
	var head: Vector2 = chen.position - left + Vector2(chen.facing * 12.0, -34.0)
	var lift := minf(t / 0.2, 1.0) * 6.0
	_item_show.position = (head - Vector2(sz.x / 2.0, sz.y + lift)).round()


# ----------------------------------------------------------------------- 换地方
func _fade_to(st: Dictionary) -> void:
	var room := str(st.get("room", "forest"))
	var r: Dictionary = world.resolve(st.get("at", 0))
	if not r["ok"]:
		_warn_once("fade_to：找不到 " + str(st.get("at")))
		return
	var x: float = r["x"]
	if ff:
		_teleport(room, x, st.get("with", []), true)
		return
	# 进屋 / 出屋（树屋就在森林里）：不黑屏，前墙淡出 / 淡入
	var door: bool = room != world.room and (room == "treehouse" or world.room == "treehouse") \
		and world.near_house(x) and world.near_house(chen.position.x)
	if door:
		_teleport(room, x, st.get("with", []), false)
		await _wait(0.55)
		return
	await level.fade_to_black(0.5)
	_teleport(room, x, st.get("with", []), true)
	await _wait(0.25)
	await level.fade_from_black(0.5)


func _teleport(room: String, x: float, with: Array, snap: bool) -> void:
	if world.room == "treehouse" and room != "treehouse":
		fade_music_family()                 # 出了树屋：留声机 / 音乐盒的长声淡掉
	world.set_room(room, ff)
	_place(chen, x, room)
	chen.visible = true
	var w: Vector2 = world.walls(x)
	var k := 0
	for who in with:
		var n := npc(str(who))
		if n == null or n == chen:
			continue
		k += 1
		var nx := x - 30.0 * k
		if nx < w.x + 10.0:
			nx = x + 30.0 * k
		_place(n, nx, room)
		n.visible = true
		n._set_facing(1 if x > nx else -1)
	level.on_room_changed(snap)
	sync_npc_vis(snap)


# ----------------------------------------------------------------------- 鹿带路 / 点选 / 结束
func _guide(st: Dictionary) -> void:
	var r: Dictionary = world.resolve(st.get("to", 0))
	if not r["ok"]:
		_warn_once("guide：找不到 " + str(st.get("to")))
		return
	var x: float = r["x"]
	if ff:
		var side := signf(x - chen.position.x)
		_place(deer, x, world.room)
		deer.visible = true
		_place(chen, x - side * 40.0, world.room)
		return
	deer.visible = true
	_deer_go(x, st)
	if not st.get("wait", true):
		return
	dlg.close_box()
	free_walk = true
	level.story_free(true)
	while _deer_moving() or absf(chen.position.x - deer.position.x) > GUIDE_NEAR:
		await get_tree().process_frame
	free_walk = false
	level.story_free(false)
	chen.auto_dir = 0.0


func _pick(st: Dictionary) -> String:
	var opts: Array = st.get("options", [])
	if opts.is_empty():
		return ""
	var ui: Array = []
	for o in opts:
		var pid := str(o.get("id", ""))
		ui.append({"label": txt(o.get("label", pid)), "rect": _prop_screen_rect.bind(pid)})
	var auto_i := -1
	if auto != "" or ff:
		auto_i = _auto_pick(st)
	var i: int = await dlg.pick(ui, auto_i)
	i = clampi(i, 0, opts.size() - 1)
	return str(opts[i].get("scene", ""))


func _prop_screen_rect(pid: String) -> Rect2:
	var key := pid if world.props.has(pid) else pid.trim_prefix("room_")
	if not world.props.has(key) or not (world.props[key] as Sprite2D).visible:
		return Rect2()
	var r: Rect2 = world.prop_rect(key)
	r.position -= level.cam_left()
	return r


## 点选里「对的」那个：选项写了 correct 就是它；不然是 scene 一路 goto 下去不会回到这个点选所在 scene 的那个
func _correct_index(st: Dictionary, here: String) -> int:
	var opts: Array = st.get("options", [])
	for i in opts.size():
		if opts[i].get("correct", false):
			return i
	for i in opts.size():
		if not _loops_back(str(opts[i].get("scene", "")), here):
			return i
	return 0


func _loops_back(s: String, here: String) -> bool:
	var seen := {}
	while s != "" and not seen.has(s):
		if s == here:
			return true
		seen[s] = true
		var nxt := ""
		for step in scenes.get(s, []):
			if step is Dictionary and str(step.get("do", "")) == "goto":
				nxt = str(step.get("scene", ""))
		s = nxt
	return false


func _auto_pick(st: Dictionary) -> int:
	var ok := _correct_index(st, _cur_scene)
	if auto == "full" and not ff:
		var opts: Array = st.get("options", [])
		for i in opts.size():
			var key := _cur_scene + ":" + str(i)
			if i != ok and not _wrong_tried.has(key):
				_wrong_tried[key] = true
				return i
	return ok


var ff_hit_end := false              # 跳节拍时碰到了 end_chapter（跳到 launched：跳完直接播起飞）


func _end_chapter() -> void:
	if ff:
		ff_hit_end = true
		return
	ended = true
	dlg.close_box()
	await level.story_takeoff()
	dlg.end_card(I18n.t("to_be_continued"), I18n.t("to_be_continued_sub"), level.get_node("Top"))
	if auto != "":
		await _wait(2.5)
		if shots_dir != "":
			level._save(shots_dir.path_join("%03d_end_card.png" % (_shot_n + 1)))
		print_stats("STORY_DONE")
		get_tree().quit()


# ======================================================================= hotspot
## 跳节拍跳到了最后（launched）：直接播起飞和结束卡
func play_end() -> void:
	busy = true
	level.story_begin(true)
	await _end_chapter()


## 晨按了互动（或自动玩走到了）：播它的 scene
func trigger(p: Dictionary) -> void:
	var h: Dictionary = p["h"]
	var id := str(h.get("id", ""))
	if h.get("once", false):
		StoryState.mark_used(id)
	_visited[id] = StoryState.progress()
	hotspots_used += 1
	if not ff and absf(float(p["x"]) - chen.position.x) > 2.0:
		chen._set_facing(1 if float(p["x"]) > chen.position.x else -1)
	_enter_scene = hotspots.is_enter(h)
	await play(str(h.get("scene", "")), not ff)
	_enter_scene = false
	_visited[id] = StoryState.progress()


## 这个 hotspot 现在去了会不会推进（设新 flag、给新东西、换地方、结束、换物件状态）
func is_progress_hotspot(h: Dictionary) -> bool:
	return _would_progress(str(h.get("scene", "")), {})


func _would_progress(s: String, seen: Dictionary) -> bool:
	if seen.has(s) or not scenes.has(s):
		return false
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		match str(st.get("do", "")):
			"flag":
				if st.has("set") and not StoryState.has(str(st["set"])):
					return true
			"give":
				if not Inventory.has(str(st.get("item", ""))):
					return true
			"fade_to", "end_chapter":
				return true
			"goto":
				if _would_progress(str(st.get("scene", "")), seen):
					return true
			"if":
				if _would_progress(str(st.get("then", "")), seen) or _would_progress(str(st.get("else", "")), seen):
					return true
			"pick":
				for o in st.get("options", []):
					if _would_progress(str(o.get("scene", "")), seen):
						return true
	return false


## 从 s 出发 goto / if / pick 能到的所有 scene
func _reach(s: String, seen: Dictionary) -> Array:
	if seen.has(s) or not scenes.has(s):
		return seen.keys()
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		match str(st.get("do", "")):
			"goto":
				_reach(str(st.get("scene", "")), seen)
			"if":
				_reach(str(st.get("then", "")), seen)
				_reach(str(st.get("else", "")), seen)
			"pick":
				for o in st.get("options", []):
					_reach(str(o.get("scene", "")), seen)
	return seen.keys()


func _exits(s: String, seen := {}) -> bool:
	if seen.has(s) or not scenes.has(s):
		return false
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		var d := str(st.get("do", ""))
		if d in ["fade_to", "end_chapter"]:
			return true
		if d == "goto" and _exits(str(st.get("scene", "")), seen):
			return true
		if d == "if" and (_exits(str(st.get("then", "")), seen) or _exits(str(st.get("else", "")), seen)):
			return true
	return false


# ======================================================================= 自动玩 / 跳节拍
## 下一个该去的地方：{kind: "wood"|"hotspot", x, p}；空 = 没有
func plan() -> Dictionary:
	var cands: Array = []
	if level.wood_available():
		cands.append({"kind": "wood", "x": level.WOOD_X, "exit": false})
	for p in hotspots.available():
		var h: Dictionary = p["h"]
		var id := str(h.get("id", ""))
		if _visited.has(id) and int(_visited[id]) == StoryState.progress():
			continue                                   # 上次来过以后没有新进展：不再来
		var prog := is_progress_hotspot(h)
		if not prog:
			if auto != "full" or ff or _visited.has(id):
				continue
		cands.append({"kind": "hotspot", "x": float(p["x"]), "p": p, "exit": _exits(str(h.get("scene", ""))), "prog": prog})
	if cands.is_empty():
		return {}
	var cx := chen.position.x
	var full := auto == "full" and not ff
	cands.sort_custom(func(a, b):
		if a["exit"] != b["exit"]:
			return not a["exit"]
		# full：同一片先把闲聊都听一遍，再去推进剧情的点
		if full and a.get("prog", true) != b.get("prog", true):
			return not a.get("prog", true)
		return absf(float(a["x"]) - cx) < absf(float(b["x"]) - cx))
	return cands[0]


func _process(delta: float) -> void:
	_game_t += delta
	step_t += delta
	_update_item_show(delta)
	if auto == "" or ended or ff:
		return
	dlg.auto_delay = AUTO_LINE
	if busy:
		if free_walk:
			# 带路：跟着鹿走
			var d := deer.position.x - chen.position.x
			chen.auto_dir = signf(d) if absf(d) > 36.0 else 0.0
		_idle_t = 0.0
		_target = {}                 # 剧情开始了（可能是路上踩到的 trigger:"enter"）：播完重新规划
		return
	if not level.free_play():
		_idle_t = 0.0
		_target = {}
		return
	if _target.is_empty():
		_target = plan()
		if not _target.is_empty():
			level.walk_to(float(_target["x"]))
	if _target.is_empty():
		_idle_t += delta
		if _idle_t > 8.0:
			print_stats("STORY_STUCK")
			get_tree().quit(1)
		return
	_idle_t = 0.0
	var tx := float(_target["x"])
	if _target["kind"] == "wood":
		if not level.wood_available():
			_target = {}
		elif absf(chen.position.x - tx) > 30.0 and not level.walking():
			level.walk_to(tx)
		return
	if absf(chen.position.x - tx) <= hotspots.RANGE - 4.0 and chen._vel <= 0.0:
		var p: Dictionary = _target["p"]
		_target = {}
		if hotspots.usable(p["h"]):
			trigger(p)
	elif not level.walking():
		level.walk_to(tx)


## 跳节拍：把剧情瞬间过一遍，直到 flag 设上（那个 scene 播完）。返回有没有到。
func fast_forward(target: String) -> bool:
	ff = true
	dlg.instant = true
	var guard := 0
	while not StoryState.has(target) and guard < 400:
		guard += 1
		var c := plan()
		if c.is_empty():
			break
		if c["kind"] == "wood":
			await level.ff_take_wood()
		else:
			var p: Dictionary = c["p"]
			_place(chen, float(p["x"]) - 12.0 * signf(float(p["x"]) - chen.position.x), world.room)
			await trigger(p)
	ff = false
	dlg.instant = false
	return StoryState.has(target)


func print_stats(tag: String) -> void:
	var real := (Time.get_ticks_msec() - _t0_ms) / 1000.0
	var unplayed: Array = []
	for id in scenes:
		if not played.has(id):
			unplayed.append(id)
	print("%s story=%s scenes=%d/%d plays=%d lines=%d hotspots=%d game_time=%.1fs real_time=%.1fs" % [
		tag, path, played.size(), scenes.size(), played_order.size(), lines, hotspots_used, _game_t, real])
	print("STORY_FLAGS " + ", ".join(StoryState.flag_order))
	print("STORY_ITEMS " + ", ".join(Inventory.owned))
	print("STORY_UNPLAYED " + (", ".join(unplayed) if not unplayed.is_empty() else "(none)"))
	print("STORY_MISSING_SFX " + (", ".join(missing_sfx.keys()) if not missing_sfx.is_empty() else "(none)"))
	if tag == "STORY_STUCK":
		var av: Array = []
		for p in hotspots.available():
			av.append(str(p["h"]["id"]))
		print("STORY_STUCK_AT x=%.0f room=%s available=%s" % [chen.position.x, world.room, ", ".join(av)])


# ======================================================================= 检查剧本
func validate() -> Array[String]:
	var out: Array[String] = []
	var set_flags := {}
	for f in ENGINE_FLAGS:
		set_flags[f] = true
	var refs := {}
	for id in scenes:
		for st in scenes[id]:
			if st is Dictionary and str(st.get("do", "")) == "flag" and st.has("set"):
				set_flags[str(st["set"])] = true
	for k in HOOKS:
		var h := hook(k)
		if h == "":
			out.append("info: 没有 %s 的对接 scene（%s），用关卡原来的" % [k, "/".join(HOOKS[k])])
		else:
			refs[h] = true
	var ids := {}
	for h in hotspot_defs:
		if not h is Dictionary:
			out.append("hotspot 不是对象：" + str(h))
			continue
		var hid := str(h.get("id", ""))
		if ids.has(hid):
			out.append("hotspot id 重复：" + hid)
		ids[hid] = true
		var at = h.get("at", null)
		if at == null or (at is String and npc(str(at)) == null and not world.has_marker(str(at)) and not str(at).is_valid_float()):
			out.append("hotspot %s：at 找不到 %s" % [hid, str(at)])
		if not str(h.get("room", "forest")) in ["forest", "treehouse"]:
			out.append("hotspot %s：room 只能是 forest / treehouse（%s）" % [hid, h.get("room")])
		var sc := str(h.get("scene", ""))
		if not scenes.has(sc):
			out.append("hotspot %s：没有 scene %s" % [hid, sc])
		refs[sc] = true
		for key in ["need", "not"]:
			for f in h.get(key, []):
				if not set_flags.has(str(f)):
					out.append("hotspot %s：%s 里的 flag %s 剧本里没有任何地方设" % [hid, key, f])
		if h.has("hide_after") and not set_flags.has(str(h["hide_after"])):
			out.append("hotspot %s：hide_after %s 没有地方设" % [hid, h["hide_after"]])
		if h.has("sprite") and not ResourceLoader.exists(str(h["sprite"])):
			out.append("info: hotspot %s 的图还没有（色块占位）：%s" % [hid, h["sprite"]])
	for id in scenes:
		var arr = scenes[id]
		if not arr is Array:
			out.append("scene %s 不是数组" % id)
			continue
		for st in arr:
			if not st is Dictionary:
				out.append("scene %s：步骤不是对象 %s" % [id, str(st)])
				continue
			var kind := "say" if st.has("say") else ("narr" if st.has("narr") else str(st.get("do", "")))
			if not kind in STEPS:
				out.append("scene %s：不支持的步骤 %s" % [id, JSON.stringify(st)])
				continue
			match kind:
				"say":
					var who := str(st["say"])
					if not speakers.has(who):
						out.append("scene %s：说话人 %s 不在 speakers 里" % [id, who])
					if str(st.get("zh", "")) == "":
						out.append("scene %s：%s 的台词没有 zh" % [id, who])
				"narr":
					if not st["narr"] is Dictionary or str(st["narr"].get("zh", "")) == "":
						out.append("scene %s：narr 没有 zh" % id)
				"walk", "face":
					var who := str(st.get("who", "chen"))
					if npc(who) == null:
						out.append("scene %s：%s 的 who 不认识 %s" % [id, kind, who])
					var to = st.get("to", null)
					if to == null or (to is String and npc(str(to)) == null and not world.has_marker(str(to)) and not str(to).is_valid_float()):
						out.append("scene %s：%s 的 to 找不到 %s" % [id, kind, str(to)])
				"show", "hide":
					var who := str(st.get("who", ""))
					if npc(who) == null and not world.props.has(who):
						out.append("scene %s：%s 的 who 不认识 %s" % [id, kind, who])
					if st.has("at") and not world.has_marker(str(st["at"])) and not str(st["at"]).is_valid_float():
						out.append("scene %s：%s 的 at 找不到 %s" % [id, kind, st["at"]])
				"give", "take":
					var item := str(st.get("item", ""))
					if not Inventory.defined(item):
						out.append("scene %s：物品 %s 不在 items.json（也不在剧本 items 里）" % [id, item])
				"journal":
					if str(st.get("zh", "")) == "":
						out.append("scene %s：journal 没有 zh" % id)
				"sfx", "ambient":
					var nm := str(st.get("name", ""))
					if _sfx_path(nm) == "":
						missing_sfx[nm] = true
					if kind == "ambient" and not world.has_marker(str(st.get("at", ""))):
						out.append("scene %s：ambient 的 at 找不到 %s" % [id, st.get("at")])
				"show_item":
					if not Inventory.defined(str(st.get("item", ""))):
						out.append("scene %s：show_item 的物品 %s 不在物品表" % [id, st.get("item")])
				"if":
					for k2 in ["then", "else"]:
						if st.has(k2):
							var s2 := str(st[k2])
							refs[s2] = true
							if s2 != "" and not scenes.has(s2):
								out.append("scene %s：if 的 %s scene %s 不存在" % [id, k2, s2])
					var f2 := str(st.get("flag", "")).trim_prefix("!")
					if not set_flags.has(f2):
						out.append("scene %s：if 的 flag %s 没有地方设" % [id, f2])
				"fade_to":
					if not str(st.get("room", "forest")) in ["forest", "treehouse"]:
						out.append("scene %s：fade_to 的 room 不认识 %s" % [id, st.get("room")])
					if not world.has_marker(str(st.get("at", ""))) and not str(st.get("at", "")).is_valid_float():
						out.append("scene %s：fade_to 的 at 找不到 %s" % [id, st.get("at")])
					for w in st.get("with", []):
						if npc(str(w)) == null:
							out.append("scene %s：fade_to 的 with 不认识 %s" % [id, w])
				"anim":
					var who := str(st.get("who", ""))
					var key := "miluo" if npc(who) == miluo else who
					if not (ANIM_MAP.get(key, {}) as Dictionary).has(str(st.get("name", ""))):
						out.append("scene %s：%s 没有动画 %s（有：%s）" % [id, who, st.get("name"), ", ".join((ANIM_MAP.get(key, {}) as Dictionary).keys())])
				"prop":
					var pid := str(st.get("id", ""))
					if not world.props.has(pid) and not pid in world.PSEUDO_PROPS:
						out.append("scene %s：没有物件 %s（只记状态，画面上没东西）" % [id, pid])
				"guide":
					if not world.has_marker(str(st.get("to", ""))) and not str(st.get("to", "")).is_valid_float():
						out.append("scene %s：guide 的 to 找不到 %s" % [id, st.get("to")])
				"goto":
					var s := str(st.get("scene", ""))
					refs[s] = true
					if not scenes.has(s):
						out.append("scene %s：goto 的 scene %s 不存在" % [id, s])
				"pick":
					for o in st.get("options", []):
						var s := str(o.get("scene", ""))
						refs[s] = true
						if not scenes.has(s):
							out.append("scene %s：pick 选项 %s 的 scene %s 不存在" % [id, o.get("id"), s])
						var pid := str(o.get("id", ""))
						if not world.props.has(pid) and not world.props.has(pid.trim_prefix("room_")):
							out.append("info: scene %s：pick 选项 %s 场景里没有这个物件（用下面一排按钮）" % [id, pid])
	for h in hotspot_defs:
		if h is Dictionary and hotspots.is_enter(h):
			for s in _reach(str(h.get("scene", "")), {}):
				for st in scenes.get(s, []):
					if st is Dictionary and str(st.get("do", "")) == "walk" and str(st.get("who", "chen")) == "chen":
						out.append("scene %s（hotspot %s 走进去触发）：晨的 walk 不执行——不推人，停在看得见的边上" % [s, h.get("id")])
	for id in scenes:
		if not refs.has(id):
			out.append("info: scene %s 没有任何 hotspot / goto / pick / if 引用到（播不到）" % id)
	if not missing_sfx.is_empty():
		out.append("info: 缺音效文件（静默跳过）：" + ", ".join(missing_sfx.keys()))
	return out
