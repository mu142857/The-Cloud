extends RefCounted
## 河流篇小游戏 river_warehouse：水下仓库（原文 112，剧情姐写的玩法原样落地）。
##   112：玩家利用浮箱改变柜子的受力位置，拉开堵住内门的家具，再按设备标签找到读取头。导绳、出口灯和明确的绳结提供导航，
##        气量不设置紧迫倒计时。完成主目标后，可顺路取回少量旧物和修船零件。
##   前情（原文 110–111，剧本已演）：两人戴面罩、导绳、桌椅绑到高处、抽屉朝同一方向敞着、贴圆字的箱子、破箱子、妮芙捡起照片。
##   水下两人不说话（原文 110「不要隔着面罩喊我，听不清的」）：这里没有一句 say，反馈全靠动作、物件、标签字（narr）和声音。
##
## 怎么玩（点选场景里的东西；没有气量表、没有倒计时、不会失败）：
##   1. 一只倒下的柜子斜压在家具上，家具堵着内门。直接拉家具：拉不动（压着）。
##   2. 拿浮箱 → 拴到柜子的一个拴点上（两个：压着家具那头 / 另一头）。拴在压着家具那头：那头被浮起来，家具松了。
##      拴错：另一头浮起来、柜子更斜，压得一样死；浮箱松开漂回原处（不丢）。
##   3. 拉家具 → 挪开 → 内门开了 → 顺着导绳过去（过绳结的时候绳结亮一下）。
##   4. 设备柜：走到设备柜前互动 = 开特写（closeup img warehouse_cabinet，zones = 抽屉，rect 是图里的像素）。一排贴标签的抽屉（标签 = label）。按标签找「读取头」。拉开不对的：看一眼标签、关上。
##      拉开「密封圈」那格：顺手拿走密封圈（修船零件）。拿到读取头 = 主目标完成。还没拿密封圈的话，回程顺路从那一格取走（原文「顺路取回」）。
##   5. 完成后可以顺路从破箱子边带一样旧物回去（纽扣 / 空瓶），递给妮芙，她看看、点点头；也可以不拿（olds）。
##   站着 12 秒没点：妮芙用手指一下对的东西（剧本 warehouse_niff 那样举板、点头，水下不说话）。
##   导航：导绳一直开着（warehouse_rope on）、出口灯亮着（exit_light）；绳结 knots 按顺序标方向。走到导绳尽头晨就停住（引擎的边）。
##
## 剧本步骤：{"do": "mechanic", "id": "river_warehouse", "cabinet": {id, label}, "float": {id, label},
##   "points": [{id, label, right?}…], "furniture": {id, label}, "door": {id}, "equip": {id, label}, "drawers": [{id, label（抽屉上的标签）, tag（拉开看到的，narr）, rect（特写图里的像素）, head?, seal?}…],
##   "olds": [{id, label, prop?}…], "olds_skip": {label, at}, "knots": [marker…], "exit_light": id, "on_head": [步骤], "on_seal": [步骤], "lines": {...}}
## 进度（story.mech_load）：{holding, lifted, moved, opened: [抽屉], head, seal, old: ""/id/"skip"}。
## 物件状态（给会话 C）：柜子 fallen / tilt_wrong / lifted；浮箱 idle / held / tied_<拴点>；家具 pinned / wiggle / loose / moved；
##   内门 closed / open；绳结 lit；出口灯 on。抽屉在特写图里（会话 D：closeup_warehouse_cabinet.png，拿过密封圈后 _open 那张）。

const KIT := preload("res://scripts/river_explore_order.gd")
const ID := "river_warehouse"


# ======================================================================= 规则（纯函数）
static func fresh() -> Dictionary:
	return {"holding": false, "lifted": false, "moved": false, "opened": [], "head": false, "seal": false, "old": ""}


static func right_point(step: Dictionary) -> String:
	for p in step.get("points", []):
		if p.get("right", false):
			return str(p["id"])
	return ""


## 这一轮能做的事：返回 tok 列表（顺序 = 显示顺序）
static func options(step: Dictionary, s: Dictionary) -> Array:
	var out: Array = []
	if not s["moved"]:
		if s["holding"]:
			for p in step.get("points", []):
				out.append("point:" + str(p["id"]))
			out.append("drop")
		else:
			if not s["lifted"]:
				out.append("float")
			out.append("furniture")
			if not s["lifted"]:
				out.append("cabinet")
		return out
	if not s["head"]:
		for d in step.get("drawers", []):
			out.append("drawer:" + str(d["id"]))
		return out
	if str(s["old"]) == "":
		for o in step.get("olds", []):
			out.append("old:" + str(o["id"]))
		out.append("old:skip")
	return out


static func drawer(step: Dictionary, id: String) -> Dictionary:
	for d in step.get("drawers", []):
		if str(d["id"]) == id:
			return d
	return {}


## 一次操作，改 s，返回 {kind, ...}
##   kind：take_float / drop / lift（拴对）/ tilt_wrong（拴错）/ stuck（家具压着）/ move（拉开家具）/ look_cabinet /
##         drawer（拉开看看）/ seal / head / old / done
static func act(step: Dictionary, s: Dictionary, tok: String) -> Dictionary:
	if tok == "float" and not s["holding"] and not s["lifted"]:
		s["holding"] = true
		return {"kind": "take_float"}
	if tok == "drop" and s["holding"]:
		s["holding"] = false
		return {"kind": "drop"}
	if tok.begins_with("point:") and s["holding"]:
		var p := tok.substr(6)
		s["holding"] = false
		if p == right_point(step):
			s["lifted"] = true
			return {"kind": "lift", "point": p}
		return {"kind": "tilt_wrong", "point": p}
	if tok == "cabinet":
		return {"kind": "look_cabinet"}
	if tok == "furniture":
		if not s["lifted"]:
			return {"kind": "stuck"}
		if not s["moved"]:
			s["moved"] = true
			return {"kind": "move"}
	if tok.begins_with("drawer:") and s["moved"] and not s["head"]:
		var id := tok.substr(7)
		var d := drawer(step, id)
		if not id in s["opened"]:
			(s["opened"] as Array).append(id)
		if d.get("head", false):
			s["head"] = true
			return {"kind": "head", "drawer": id}
		if d.get("seal", false) and not s["seal"]:
			s["seal"] = true
			return {"kind": "seal", "drawer": id}
		return {"kind": "drawer", "drawer": id}
	if tok.begins_with("old:") and s["head"] and str(s["old"]) == "":
		s["old"] = tok.substr(4)
		return {"kind": "old", "old": s["old"]}
	return {"kind": "none"}


static func finished(s: Dictionary) -> bool:
	return s["head"] and str(s["old"]) != ""


## 「对的」那一步
static func best(step: Dictionary, s: Dictionary) -> String:
	if not s["moved"]:
		if s["lifted"]:
			return "furniture"
		if s["holding"]:
			return "point:" + right_point(step)
		return "float"
	if not s["head"]:
		for d in step.get("drawers", []):
			if d.get("head", false):
				return "drawer:" + str(d["id"])
	var olds: Array = step.get("olds", [])
	return "old:" + (str(olds[0]["id"]) if not olds.is_empty() else "skip")


static func solvable(step: Dictionary, s: Dictionary) -> bool:
	var t: Dictionary = s.duplicate(true)
	for k in 30:
		if finished(t):
			return true
		act(step, t, best(step, t))
	return finished(t)


# ======================================================================= 演出
var auto_mode := false
var tried := {}
var story: Node
var world: Node2D
var step: Dictionary
var s: Dictionary


func run(_level: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	world = w
	step = st
	s = story.mech_load(ID)
	if not s.has("holding"):
		s = fresh()
	_show_state()
	await KIT.lines(story, step, "start")
	while not story.ended and not finished(s):
		var tok: String = await _ask()
		if tok == "equip":
			await _cabinet()
			continue
		var res := act(step, s, tok)
		story.mech_save(ID, s)
		await _play(res)
	if not s["seal"]:
		# 回程顺路：从密封圈那一格取走（原文「完成主目标后，可顺路取回……修船零件」）
		s["seal"] = true
		story.mech_save(ID, s)
		await _seal_drawer()
	await KIT.lines(story, step, "done")
	print("MECH %s done old=%s" % [ID, s["old"]])


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


func _label(tok: String) -> Variant:
	var key := tok.get_slice(":", 0)
	var arg := tok.get_slice(":", 1) if tok.contains(":") else ""
	match key:
		"float", "furniture", "cabinet", "drop", "equip":
			return step.get(key, {}).get("label", key)
		"point":
			for p in step.get("points", []):
				if str(p["id"]) == arg:
					return p.get("label", arg)
		"old":
			if arg == "skip":
				return step.get("olds_skip", {}).get("label", "skip")
			for o in step.get("olds", []):
				if str(o["id"]) == arg:
					return o.get("label", arg)
	return tok


## 互动点放在哪（marker / 物件 id）
func _at(tok: String) -> String:
	var key := tok.get_slice(":", 0)
	var arg := tok.get_slice(":", 1) if tok.contains(":") else ""
	match key:
		"float", "furniture", "cabinet", "equip":
			return str(step.get(key, {}).get("id", ""))
		"drop":
			return str(step.get("float", {}).get("id", ""))
		"point":
			return arg
		"old":
			if arg == "skip":
				return str(step.get("olds_skip", {}).get("at", step.get("exit_light", "")))
			for o in step.get("olds", []):
				if str(o["id"]) == arg:
					return str(o.get("prop", ""))
	return ""


## 这一轮的互动点。抽屉不在场景里：内门开了以后是一个「设备柜」点，互动 = 开特写挑抽屉
func _ask() -> String:
	var ok := best(step, s)
	var opts: Array = []
	var toks := options(step, s)
	if s["moved"] and not s["head"]:
		toks = ["equip"]
		ok = "equip"
	for tok in toks:
		opts.append({"tok": tok, "at": _at(tok), "label": _label(tok), "correct": tok == ok})
	return await KIT.choose(self, story, opts, _hint.bind(ok))


## 站着不动一会儿：妮芙转过去、指一下对的东西（不说话）
func _hint(ok: String) -> void:
	var p := _at(ok)
	var st2: Array = [{"do": "anim", "who": "niff", "name": "point"}]
	if p != "" and world.has_marker(p):
		st2.push_front({"do": "face", "who": "niff", "to": p})
	story.run_steps(st2)


## 设备柜特写：一排贴标签的抽屉（zones），按标签找读取头；关掉 = 回到柜子前
func _cabinet() -> void:
	var eq: Dictionary = step.get("equip", {})
	await KIT.go_to(self, story, str(eq.get("id", "")))
	while not story.ended and not s["head"]:
		var pick := ""
		if auto_mode:
			pick = await KIT.choose(self, story, _drawer_opts())
			pick = pick.trim_prefix("drawer:")
		else:
			var zones: Array = []
			for d in step.get("drawers", []):
				zones.append({"id": str(d["id"]), "rect": d.get("rect", [0, 0, 40, 20]), "label": d.get("label", {})})
			pick = await story.closeup({"img": str(eq.get("img", "warehouse_cabinet")), "zones": zones, "state": "open" if s["seal"] else ""})
		if pick == "":
			return
		var res := act(step, s, "drawer:" + pick)
		story.mech_save(ID, s)
		await _play(res)


func _drawer_opts() -> Array:
	var ok := best(step, s)
	var opts: Array = []
	for d in step.get("drawers", []):
		opts.append({"tok": "drawer:" + str(d["id"]), "correct": "drawer:" + str(d["id"]) == ok})
	return opts


func _play(res: Dictionary) -> void:
	var cab := str(step.get("cabinet", {}).get("id", ""))
	var fl := str(step.get("float", {}).get("id", ""))
	var fu := str(step.get("furniture", {}).get("id", ""))
	match str(res["kind"]):
		"take_float":
			await KIT.go_to(self, story, fl)
			await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "pickup"}, {"do": "prop", "id": fl, "state": "held"},
				{"do": "sfx", "name": "float_grab"}])
		"drop":
			await KIT.steps(story, [{"do": "prop", "id": fl, "state": "idle"}, {"do": "sfx", "name": "float_bob"}])
		"lift":
			await KIT.go_to(self, story, str(res["point"]))
			await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "tie_rope"},
				{"do": "prop", "id": fl, "state": "tied_" + str(res["point"])}, {"do": "sfx", "name": "float_rise"},
				{"do": "wait", "sec": 0.8}, {"do": "prop", "id": cab, "state": "lifted"}, {"do": "sfx", "name": "cabinet_creak"},
				{"do": "prop", "id": fu, "state": "loose"}])
			await KIT.lines(story, step, "lift")
		"tilt_wrong":
			# 拴错：另一头浮起来、柜子更斜，压得一样死；浮箱松开漂回原处
			await KIT.go_to(self, story, str(res["point"]))
			await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "tie_rope"},
				{"do": "prop", "id": fl, "state": "tied_" + str(res["point"])}, {"do": "sfx", "name": "float_rise"},
				{"do": "wait", "sec": 0.6}, {"do": "prop", "id": cab, "state": "tilt_wrong"}, {"do": "sfx", "name": "cabinet_creak"},
				{"do": "wait", "sec": 1.0}, {"do": "prop", "id": cab, "state": "fallen"}, {"do": "prop", "id": fl, "state": "idle"},
				{"do": "sfx", "name": "float_bob"}])
			await KIT.lines(story, step, "tilt_wrong")
		"stuck":
			await KIT.go_to(self, story, fu)
			await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "pull"}, {"do": "sfx", "name": "furniture_stuck"},
				{"do": "prop", "id": fu, "state": "wiggle"}, {"do": "wait", "sec": 0.5}, {"do": "prop", "id": fu, "state": "pinned"}])
			await KIT.lines(story, step, "stuck")
		"look_cabinet":
			await KIT.go_to(self, story, cab)
			await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "look_close"}])
			await KIT.lines(story, step, "look_cabinet")
		"move":
			await KIT.go_to(self, story, fu)
			await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "pull"}, {"do": "sfx", "name": "furniture_drag"},
				{"do": "prop", "id": fu, "state": "moved"}, {"do": "wait", "sec": 0.6},
				{"do": "prop", "id": str(step.get("door", {}).get("id", "")), "state": "open"}, {"do": "sfx", "name": "door_underwater"}])
			await _knots()
			await KIT.lines(story, step, "door_open")
		"drawer", "seal", "head":
			var d := drawer(step, str(res["drawer"]))
			await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "open_drawer"}, {"do": "sfx", "name": "drawer_open"},
				{"narr": d.get("tag", d.get("label", {}))}])
			if res["kind"] == "head":
				await KIT.steps(story, step.get("on_head", []))
				await KIT.lines(story, step, "head")
			elif res["kind"] == "seal":
				await KIT.steps(story, step.get("on_seal", []))
			else:
				await KIT.steps(story, [{"do": "sfx", "name": "drawer_close"}])
		"old":
			if str(res["old"]) != "skip":
				var o: Dictionary = {}
				for x in step.get("olds", []):
					if str(x["id"]) == str(res["old"]):
						o = x
				await KIT.go_to(self, story, str(o.get("prop", "")))
				await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "pickup"}])
				await KIT.lines(story, step, "old_" + str(res["old"]))
				await KIT.lines(story, step, "old_give")


## 顺路从密封圈那一格取走
func _seal_drawer() -> void:
	for d in step.get("drawers", []):
		if d.get("seal", false):
			await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "open_drawer"}, {"narr": d.get("tag", d.get("label", {}))}])
	await KIT.steps(story, step.get("on_seal", []))


## 过内门：顺着导绳走，绳结一个个亮一下（明确的绳结提供导航）
func _knots() -> void:
	for k in step.get("knots", []):
		if auto_mode:
			await KIT.steps(story, [{"do": "walk", "who": "chen", "to": str(k)}])
		await KIT.steps(story, [{"do": "prop", "id": str(k), "state": "lit"}, {"do": "sfx", "name": "rope_knot", "db": -8.0}])


func _show_state() -> void:
	world.set_prop("warehouse_rope", "on")
	if step.has("exit_light"):
		world.set_prop(str(step["exit_light"]), "on")
	var cab := str(step.get("cabinet", {}).get("id", ""))
	var fu := str(step.get("furniture", {}).get("id", ""))
	world.set_prop(cab, "lifted" if s["lifted"] else "fallen")
	world.set_prop(fu, "moved" if s["moved"] else ("loose" if s["lifted"] else "pinned"))
	world.set_prop(str(step.get("door", {}).get("id", "")), "open" if s["moved"] else "closed")
	world.set_prop(str(step.get("float", {}).get("id", "")), ("tied_" + right_point(step)) if s["lifted"] else "idle")


## 跳节拍：读取头、密封圈都拿到（同步、不演；物品由 on_head / on_seal 里的 give 给）
func ff(r: Node, st: Dictionary) -> void:
	var t := fresh()
	for k in 30:
		if finished(t):
			break
		act(st, t, best(st, t))
	t["seal"] = true
	r.mech_save(ID, t)
	for x in st.get("on_head", []) + st.get("on_seal", []):
		if x is Dictionary and str(x.get("do", "")) == "give":
			Inventory.add(str(x.get("item", "")))


func check(story: Node, st: Dictionary) -> Array:
	var out: Array = []
	if right_point(st) == "":
		out.append("points 里没有 right: true 的拴点")
	var heads := 0
	var seals := 0
	for d in st.get("drawers", []):
		heads += 1 if d.get("head", false) else 0
		seals += 1 if d.get("seal", false) else 0
		if not d.has("tag"):
			out.append("抽屉 %s 没有 tag（标签字）" % d.get("id"))
	if heads != 1:
		out.append("drawers 里要正好一格 head（读取头），现在 %d" % heads)
	if seals != 1:
		out.append("drawers 里要正好一格 seal（密封圈），现在 %d" % seals)
	# 每一步每个选项都点一遍，都还能解（错的只回退不卡）
	var t := fresh()
	for k in 30:
		if finished(t):
			break
		for tok in options(st, t):
			var u: Dictionary = t.duplicate(true)
			act(st, u, tok)
			if not solvable(st, u):
				out.append("点了 %s 以后解不开了" % tok)
		act(st, t, best(st, t))
	if not finished(t):
		out.append("照对的走也解不完")
	for k in st.get("lines", {}):
		out.append_array(KIT.check_steps(story, "lines.%s" % k, st["lines"][k]))
		for x in st["lines"][k]:
			if x is Dictionary and x.has("say"):
				out.append("lines.%s：水下不说话（原文 110），不要 say" % k)
	out.append_array(KIT.check_steps(story, "on_head", st.get("on_head", [])))
	out.append_array(KIT.check_steps(story, "on_seal", st.get("on_seal", [])))
	var spots: Array = [str(st.get("float", {}).get("id", "")), str(st.get("furniture", {}).get("id", "")),
		str(st.get("cabinet", {}).get("id", "")), str(st.get("equip", {}).get("id", "")), str(st.get("exit_light", ""))]
	for p in st.get("points", []):
		spots.append(str(p.get("id", "")))
	for k in st.get("knots", []):
		spots.append(str(k))
	for m in spots:
		if m != "" and not story.world.has_marker(m):
			out.append("互动点 %s 找不到（marker / 物件）" % m)
	return out
