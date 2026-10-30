extends RefCounted
## 河流篇小游戏 river_explore_order（原文 102）+ 五个河流小游戏共用的小工具（防水板、进度、播台词、等玩家互动）。
##   原文 102：探索顺序 河岸住处—高处市集—旧街水闸—水下仓库—南桥；记忆变化由关键剧情节点触发；已完成的小游戏进度保留；
##   重复介绍的对话随剧情推进；关键任务记录始终可以查看。
##   顺序 = 剧本 flag 锁好的（没到的地方门不开）；铃只在剧本写好的节点响；闲聊按 flag 换（剧本已写）。这里只做最后一句：
##   「关键任务记录」= 阿汀给的防水板（原文 101 递给妮芙「出门的事项写齐」、106 闸的刻度记在板上、110 交给晨、写着名字 / 来取什么 /
##   返回的方向 /「跟着导绳走」）。板上一行一行，做完的划一道；水闸验证过的刻度也写在这里（river_sluice.gd 调 board_add）。
##
## 剧本步骤（都在 story_river.json）：
##   {"do": "mechanic", "id": "river_explore_order", "rows": [{k, zh, en, done?: flag, added}…], "lines": {after}}
##       第一次：妮芙写板子（rows 写上去）→ 给玩家看一眼板子特写 → 关掉，接着播 lines.after。
##   {"do": "mechanic", "id": "river_explore_order", "mode": "add", "rows": [...]}   只往板上加几行（110 交板前写名字那些），不弹出来
##   {"do": "mechanic", "id": "river_explore_order", "mode": "view"}                 看一眼板子（妮芙拿着板的时候点她）
##   行的 done = 那个 flag 设了就划掉（气瓶 river_breather、回程水位 river_sluice_done、绳子 river_roped）。
##   板子特写：closeup img "board"（art/river_story/closeup_board.png，会话 D 画），行字叠在图上（lines，划掉的带 struck: true）。
##
## 板子存在 StoryState 物件状态 "river_board"（JSON：[{k, zh, en, done?, added?, x?}]，x = 试过不对的刻度，写成 ×）。
## 各小游戏的中间进度用 story.mech_load / mech_save（约定 3.3），离开再回来、F8 跳节拍都还在。
##
## 共用小工具（别的四个 river_*.gd preload 这个文件用）：
##   choose(m, story, opts, hint)：等玩家走过去互动一个点（story.wait_interact）；自动玩时直接挑对的（full 先把错的各试一次）。
##   steps / lines：播一串剧本步骤（story.run_steps）。node / local_x：物件节点、marker 的房间 x。

const BOARD_KEY := "river_board"
const HINT_SEC := 12.0         # 等互动时玩家这么久没选：妮芙用手指一下对的东西（水下不说话）


# ======================================================================= 防水板
static func board_rows() -> Array:
	var raw := str(StoryState.props.get(BOARD_KEY, ""))
	if raw == "":
		return []
	var r = JSON.parse_string(raw)
	return r if r is Array else []


static func _board_set(rows: Array) -> void:
	StoryState.set_prop(BOARD_KEY, JSON.stringify(rows))


static func board_has(k: String) -> bool:
	for r in board_rows():
		if str(r.get("k", "")) == k:
			return true
	return false


## 加一行（同一个 k 已经有了就改那一行）
static func board_add(row: Dictionary) -> void:
	var rows := board_rows()
	for i in rows.size():
		if str(rows[i].get("k", "")) == str(row.get("k", "")):
			var keep: Dictionary = rows[i]
			for key in row:
				keep[key] = row[key]
			rows[i] = keep
			_board_set(rows)
			return
	rows.append(row.duplicate(true))
	_board_set(rows)


## 在一行后面记一个「试过、不对」的刻度（水闸：防水板保留已经验证的结果，原文 107）。没有这一行就先加一行
static func board_cross(row: Dictionary, notch: int) -> void:
	var k := str(row.get("k", ""))
	if not board_has(k):
		var r: Dictionary = row.duplicate(true)
		r.erase("zh_done")
		r.erase("en_done")
		board_add(r)
	var rows := board_rows()
	for r in rows:
		if str(r.get("k", "")) == k:
			var x: Array = r.get("x", [])
			if not float(notch) in x and not notch in x:
				x.append(notch)
			r["x"] = x
	_board_set(rows)


## 这一行划掉了没有：done = true，或者 done 是个 flag 名、已经设了
static func row_done(r: Dictionary) -> bool:
	var d = r.get("done", false)
	if d is bool:
		return d
	return str(d) != "" and StoryState.has(str(d))


## 板上的字：[{zh, en, struck}]（特写面板 lines 用）
static func board_lines() -> Array:
	var out: Array = []
	for r in board_rows():
		var zh := str(r.get("zh", ""))
		var en := str(r.get("en", zh))
		var xs: Array = r.get("x", [])
		if not xs.is_empty():
			var pz: Array = []
			var pe: Array = []
			for n in xs:
				pz.append("第%d格×" % int(n))
				pe.append("%d ×" % int(n))
			zh += "（试过 %s）" % "、".join(pz)
			en += " (tried %s)" % ", ".join(pe)
		out.append({"zh": zh, "en": en, "struck": row_done(r)})
	return out


## 看一眼板子（特写面板，关掉接着播）
static func view(story: Node) -> void:
	if story.ff or board_rows().is_empty():
		return
	await story.closeup({"img": "board", "lines": board_lines(), "added": true})


# ======================================================================= 共用：播台词 / 等互动
static func steps(story: Node, arr) -> void:
	if arr is Array and not arr.is_empty():
		await story.run_steps(arr)


## 剧本 step 里 lines[key] 那一串
static func lines(story: Node, step: Dictionary, key: String) -> void:
	var l: Dictionary = step.get("lines", {})
	if l.has(key):
		await steps(story, l[key])


static func has_lines(step: Dictionary, key: String) -> bool:
	return (step.get("lines", {}) as Dictionary).has(key)


## 等玩家互动一个点：opts = [{tok, at, label, correct?, no_auto?, accepts?}]，返回 tok。
## m = 小游戏实例：m.auto_mode 时不等玩家，直接挑 correct 的（story.auto == "full" 时先把没试过的错的各试一次，no_auto 的不试）。
## hint：玩家这么久没选就调一次（妮芙指一下）。
static func choose(m: Object, story: Node, opts: Array, hint := Callable()) -> String:
	if opts.is_empty():
		return ""
	if m.auto_mode:
		var ok := ""
		for o in opts:
			if o.get("correct", false):
				ok = str(o["tok"])
		if story.auto == "full":
			for o in opts:
				var t := str(o["tok"])
				if t != ok and not o.get("no_auto", false) and not m.tried.has(t):
					m.tried[t] = true
					return t
		return ok if ok != "" else str(opts[0]["tok"])
	var spots: Array = []
	for o in opts:
		var sp := {"id": str(o["tok"]), "at": o.get("at", 0), "label": o.get("label", {"zh": str(o["tok"])})}
		if o.has("accepts"):
			sp["accepts"] = o["accepts"]
		spots.append(sp)
	var ticket := {"open": true}
	if hint.is_valid():
		_hint_after(story, ticket, hint)
	var r: Dictionary = await story.wait_interact(spots)
	ticket["open"] = false
	return str(r.get("id", ""))


static func _hint_after(story: Node, ticket: Dictionary, hint: Callable) -> void:
	var t := 0.0
	while ticket["open"] and t < HINT_SEC:
		await story.get_tree().process_frame
		t += story.get_process_delta_time()
	if ticket["open"]:
		hint.call()


## 自动玩：走过去；自己玩：玩家已经走到了，只转过去
static func go_to(m: Object, story: Node, at) -> void:
	if at is String and str(at) == "":
		return
	if m.auto_mode:
		await steps(story, [{"do": "walk", "who": "chen", "to": at}])
	else:
		await steps(story, [{"do": "face", "who": "chen", "to": at}])


## 物件节点（room_stage 的物件，可能是占位；没有 = null）和 marker 的房间 x
static func stage_of(world: Node, id: String) -> Node2D:
	if world == null or not world.has_method("stage"):
		return null
	var r := str(world.stage_of_prop(id)) if world.has_method("stage_of_prop") else ""
	var sg: Node2D = world.stage(r) if r != "" else null
	return sg if sg != null else world.cur_stage()


## marker 的世界 x（晨的 position.x 也是世界坐标）
static func mx(world: Node, m: String, fallback := 0.0) -> float:
	if world != null and world.has_marker(m):
		return float(world.resolve(m)["x"])
	return fallback


static func local_x(world: Node, m: String, fallback := 0.0) -> float:
	var sg: Node2D = world.cur_stage() if world != null and world.has_method("cur_stage") else null
	if sg != null and sg.has_marker(m):
		return float(sg.marker_local(m))
	return fallback


## 嵌套台词的检查（--story_check 用）：说话人、marker、物品、步骤种类
static func check_steps(story: Node, where: String, arr) -> Array:
	var out: Array = []
	if not arr is Array:
		out.append("%s：要是步骤数组" % where)
		return out
	for st in arr:
		if not st is Dictionary:
			out.append("%s：步骤不是对象 %s" % [where, str(st)])
			continue
		var kind := "say" if st.has("say") else ("narr" if st.has("narr") else str(st.get("do", "")))
		if not kind in story.STEPS:
			out.append("%s：不支持的步骤 %s" % [where, JSON.stringify(st)])
			continue
		match kind:
			"say":
				if not story.speakers.has(str(st["say"])):
					out.append("%s：说话人 %s 不在 speakers 里" % [where, st["say"]])
				if str(st.get("zh", "")) == "" or str(st.get("en", "")) == "":
					out.append("%s：台词缺 zh / en %s" % [where, JSON.stringify(st)])
			"narr":
				if not st["narr"] is Dictionary or str(st["narr"].get("zh", "")) == "" or str(st["narr"].get("en", "")) == "":
					out.append("%s：narr 缺 zh / en" % where)
			"walk", "face":
				var to = st.get("to", null)
				if story.npc(str(st.get("who", "chen"))) == null:
					out.append("%s：%s 的 who 不认识 %s" % [where, kind, st.get("who")])
				if to is String and story.npc(str(to)) == null and not story.world.has_marker(str(to)):
					out.append("%s：%s 的 to 找不到 %s" % [where, kind, to])
			"give", "take":
				if not Inventory.defined(str(st.get("item", ""))):
					out.append("%s：物品 %s 不在物品表" % [where, st.get("item")])
	return out


# ======================================================================= river_explore_order 本身
var auto_mode := false
var tried := {}


func run(_level: Node2D, _world: Node2D, story: Node, step: Dictionary) -> void:
	var mode := str(step.get("mode", "first"))
	for r in step.get("rows", []):
		if r is Dictionary:
			board_add(r)
	if mode == "add":
		return
	await view(story)
	if mode == "first":
		await lines(story, step, "after")
		print("MECH river_explore_order done rows=%d" % board_rows().size())


func auto(level: Node2D, world: Node2D, story: Node, step: Dictionary) -> void:
	auto_mode = true
	await run(level, world, story, step)


func ff(_story: Node, step: Dictionary) -> void:
	for r in step.get("rows", []):
		if r is Dictionary:
			board_add(r)


func check(story: Node, step: Dictionary) -> Array:
	var out: Array = []
	var mode := str(step.get("mode", "first"))
	if not mode in ["first", "add", "view"]:
		out.append("mode 只能是 first / add / view（%s）" % mode)
	for r in step.get("rows", []):
		if not r is Dictionary or str(r.get("k", "")) == "" or str(r.get("zh", "")) == "" or str(r.get("en", "")) == "":
			out.append("板子的行要有 k / zh / en：%s" % str(r))
		elif r.has("done") and r["done"] is String and not _flag_set_somewhere(story, str(r["done"])):
			out.append("板子的行 %s：done 的 flag %s 剧本里没有地方设" % [r["k"], r["done"]])
	for k in step.get("lines", {}):
		out.append_array(check_steps(story, "lines.%s" % k, step["lines"][k]))
	return out


static func _flag_set_somewhere(story: Node, f: String) -> bool:
	for id in story.scenes:
		for st in story.scenes[id]:
			if st is Dictionary and str(st.get("do", "")) == "flag" and str(st.get("set", "")) == f:
				return true
			if st is Dictionary and str(st.get("do", "")) == "mechanic" and f in st.get("sets", []):
				return true
	return false
