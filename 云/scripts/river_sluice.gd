extends RefCounted
## 河流篇小游戏 river_sluice：旧街水闸（原文 105–107，剧情姐写的玩法原样落地）。
##   105：通往旧街的踏步大半浸在水里，要先调三道小闸。墙上不同年份的水位刻线，最旧一条被苔盖住。阿汀的图纸只标了管道连接，
##        闸轮少了两块铭牌，要结合水流声、墙面刻度和管道方向判断顺序。妮芙趴在栏杆边听：「大的先别转呀，这边还在咕噜咕噜。」
##   106：晨找到第一个正确位置后伸手去转下一只，妮芙叫住 ta，先把刻度记到防水板上；第二道闸 ta 主动报出刻度，让她核对以后再动。
##   107：观察水位、辨听管道声并选择开闸顺序，使旧街踏步露出。错误操作只让水位回到上一个稳定状态，不损失剧情物品。
##        防水板保留已经验证的结果，避免玩家与妮芙重复试错。
##
## 怎么玩（走到闸轮前按键 / 鼠标点；没有计时、不会失败）：
##   三只闸轮：两只小的（没有铭牌）、一只大的。互动一只小闸轮 = 晨转一格（4 格一圈）。
##   同一时间只有一根管子在「咕噜咕噜」冒泡（管口冒泡 + 咕噜声，离对的格子远 = 3 档、差一格 = 2 档）。
##   顺着冒泡那根管子看（管道方向）它接的是哪只闸轮 —— 转那一只：
##     转到对的格子：水位稳稳降一档（停在下一条年份刻线上），这根管子不冒了，下一根开始冒；刻度记到防水板上。
##     转到不对的格子：水涌一下又落回刚才的高度（上一个稳定状态），妮芙在板上记一个 ×；下次转这只会跳过记过 × 的格子。
##   转一只没在冒泡的小闸轮：转得动，水和管子都没反应（不是这根）。
##   还在冒泡就去转大的：妮芙「还在冒泡」，不动。两根都不冒了才转大的 → 设 river_sluice_open，剧本接着演开闸、踏步露出。
##   第一只对上：lines.first_set（原文 106 妮芙叫住、记板子）；第二只对上：lines.second_set（晨报刻度、她核对、「转吧」）。
##   听管道 / 看墙上刻线：晨说一句（补写）；走到回市集的路口（leave）= 先不弄了：进度存着，回来接着转（开场 lines.intro 只播一次）。
##
## 剧本步骤：{"do": "mechanic", "id": "river_sluice", "sets": ["river_sluice_open"], "wheels": [{id, label, start, right, notches?, row}…两只小的],
##   "big": {id, label}, "water": {room, levels: [三档稳定水位的 prop 状态], prop}, "pipes": {prop, names: [a, b]},
##   "looks": [{id, label, key}…], "leave": {at, label}, "lines": {intro, first_set, second_set, wrong_1, wrong, dry_1, dry, big_early, already, look_* …}}
##   剧本下一步：{"do": "if", "flag": "river_sluice_open", "then": 开闸那段, "else": 先不弄了那段}。
## 进度（story.mech_load）：{n: [每只小闸轮第几格], x: [[试过不对的格子]…], solved: 0..2, intro: bool}。
## 物件状态（给会话 C 的 room.json）：闸轮 n1..n4 / set / ready；sluice_pipes = a_bubble_3 / a_bubble_2 / b_bubble_3 / b_bubble_2 / still；
##   水位 oldstreet_steps = submerged / l1 / l2 / revealed（room.json water.levels）。

const KIT := preload("res://scripts/river_explore_order.gd")
const ID := "river_sluice"
const SURGE := 8.0             # 不对的格子：水涌上来多少像素再落回去


# ======================================================================= 规则（纯函数：check 和测试直接调）
static func smalls(step: Dictionary) -> Array:
	return step.get("wheels", [])


static func fresh(step: Dictionary) -> Dictionary:
	var n: Array = []
	var x: Array = []
	for w in smalls(step):
		n.append(int(w.get("start", 1)))
		x.append([])
	return {"n": n, "x": x, "solved": 0, "intro": false}


static func valid(step: Dictionary, s: Dictionary) -> bool:
	return s.has("n") and (s["n"] as Array).size() == smalls(step).size() and s.has("x") and s.has("solved")


static func notches(w: Dictionary) -> int:
	return int(w.get("notches", 4))


## 下一格（4 → 1 循环），跳过板上记过 × 的格子
static func next_notch(w: Dictionary, cur: int, crossed: Array) -> int:
	var k := notches(w)
	var n := cur
	for i in k:
		n = n % k + 1
		if not _has_n(crossed, n) or n == int(w["right"]):
			return n
	return int(w["right"])


static func _has_n(arr: Array, n: int) -> bool:
	for v in arr:
		if int(v) == n:
			return true
	return false


## 格子之间的距离（一圈循环）
static func dist(w: Dictionary, a: int, b: int) -> int:
	var k := notches(w)
	var d := absi(a - b) % k
	return mini(d, k - d)


## 现在冒泡的那根管子：[第几根, 几档]；都不冒 = [-1, 0]
static func bubbling(step: Dictionary, s: Dictionary) -> Array:
	var i := int(s["solved"])
	var ws := smalls(step)
	if i >= ws.size():
		return [-1, 0]
	var w: Dictionary = ws[i]
	return [i, 3 if dist(w, int(s["n"][i]), int(w["right"])) >= 2 else 2]


## 一次操作。choice：w0 / w1（小闸轮）、big、look:<key>、leave。改 s，返回 {kind, i?, notch?}
##   kind：set（对上）/ wrong（不对，水回到上一个稳定状态）/ dry（不是冒泡那根）/ already（已经对上的）/ big_early / open / look / leave
static func act(step: Dictionary, s: Dictionary, choice: String) -> Dictionary:
	var ws := smalls(step)
	if choice == "leave":
		return {"kind": "leave"}
	if choice.begins_with("look:"):
		return {"kind": "look", "key": choice.substr(5)}
	if choice == "big":
		if int(s["solved"]) < ws.size():
			return {"kind": "big_early"}
		return {"kind": "open"}
	if not choice.begins_with("w"):
		return {"kind": "none"}
	var i := int(choice.substr(1))
	if i < 0 or i >= ws.size():
		return {"kind": "none"}
	if i < int(s["solved"]):
		return {"kind": "already", "i": i}
	if i > int(s["solved"]):
		return {"kind": "dry", "i": i}
	var w: Dictionary = ws[i]
	var n := next_notch(w, int(s["n"][i]), s["x"][i])
	s["n"][i] = n
	if n == int(w["right"]):
		s["solved"] = i + 1
		return {"kind": "set", "i": i, "notch": n}
	if not _has_n(s["x"][i], n):
		(s["x"][i] as Array).append(n)
	return {"kind": "wrong", "i": i, "notch": n}


## 现在「对的」那一步（自动玩 / 测试）
static func best(step: Dictionary, s: Dictionary) -> String:
	if int(s["solved"]) >= smalls(step).size():
		return "big"
	return "w%d" % int(s["solved"])


## 从 s 开始照对的走，limit 步以内一定能开闸
static func solvable(step: Dictionary, s: Dictionary, limit := 40) -> bool:
	var t: Dictionary = s.duplicate(true)
	for k in limit:
		if act(step, t, best(step, t))["kind"] == "open":
			return true
	return false


# ======================================================================= 演出
var auto_mode := false
var tried := {}
var story: Node
var world: Node2D
var step: Dictionary
var s: Dictionary
var _said := {}


func run(_level: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	world = w
	step = st
	s = story.mech_load(ID)
	if not valid(step, s):
		s = fresh(step)
	if not s["intro"]:
		await KIT.lines(story, step, "intro")
		s["intro"] = true
		story.mech_save(ID, s)
	_show_state(true)
	while not story.ended:
		var c: String = await _ask()
		var res := act(step, s, c)
		story.mech_save(ID, s)
		if res["kind"] == "leave":
			print("MECH %s leave solved=%d" % [ID, int(s["solved"])])
			return
		await _play(res)
		if res["kind"] == "open":
			for f in step.get("sets", []):
				StoryState.set_flag(str(f))
			break
	print("MECH %s done" % ID)


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


## 这一轮能互动的：两只小闸轮、大闸轮、听管道 / 看刻线、回市集的路口（先不弄了）
func _ask() -> String:
	var opts: Array = []
	var ok := best(step, s)
	var ws := smalls(step)
	for i in ws.size():
		opts.append({"tok": "w%d" % i, "at": str(ws[i]["id"]), "label": ws[i].get("label", ws[i]["id"]), "correct": ok == "w%d" % i})
	var big: Dictionary = step.get("big", {})
	opts.append({"tok": "big", "at": str(big.get("id", "")), "label": big.get("label", "big"), "correct": ok == "big"})
	for l in step.get("looks", []):
		opts.append({"tok": "look:" + str(l["key"]), "at": str(l["id"]), "label": l.get("label", l["id"])})
	if step.has("leave"):
		opts.append({"tok": "leave", "at": str(step["leave"].get("at", "")), "label": step["leave"].get("label", "leave"), "no_auto": true})
	return await KIT.choose(self, story, opts)


func _play(res: Dictionary) -> void:
	var kind := str(res["kind"])
	var ws := smalls(step)
	match kind:
		"set", "wrong":
			var w: Dictionary = ws[int(res["i"])]
			await KIT.go_to(self, story, str(w["id"]))
			await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "turn_wheel"}, {"do": "sfx", "name": "sluice_turn"},
				{"do": "prop", "id": str(w["id"]), "state": "n%d" % int(res["notch"])}])
			if kind == "wrong":
				await _surge()
				KIT.board_cross(w.get("row", {"k": str(w["id"])}), int(res["notch"]))
				await _once_then("wrong_1", "wrong")
			else:
				var row: Dictionary = (w.get("row", {}) as Dictionary).duplicate(true)
				if not row.is_empty():
					row["done"] = true
					KIT.board_add(row)
				await _show_state(false)
				await KIT.lines(story, step, "first_set" if int(res["i"]) == 0 else "second_set")
		"dry":
			var w2: Dictionary = ws[int(res["i"])]
			await KIT.go_to(self, story, str(w2["id"]))
			await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "turn_wheel"}, {"do": "sfx", "name": "sluice_turn", "db": -6.0}])
			await _once_then("dry_1", "dry")
		"already":
			await KIT.lines(story, step, "already")
		"big_early":
			await KIT.go_to(self, story, str(step.get("big", {}).get("id", "")))
			await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "reach"}])
			await KIT.lines(story, step, "big_early")
		"look":
			var key := str(res["key"])
			if key == "pipes":
				# 顺着冒泡那根管子看过去：晨转向它接着的那只闸轮（管道方向，原文 105）
				var b := bubbling(step, s)
				if int(b[0]) >= 0:
					await _gurgle()
					await KIT.lines(story, step, "look_pipes")
					await KIT.steps(story, [{"do": "face", "who": "chen", "to": str(ws[int(b[0])]["id"])}])
				else:
					await KIT.lines(story, step, "look_pipes_quiet")
			elif key == "marks":
				await KIT.lines(story, step, "look_marks_%d" % int(s["solved"]))
			else:
				await KIT.lines(story, step, "look_" + key)


## 第一次说 first，以后说 rest
func _once_then(first: String, rest: String) -> void:
	if not _said.has(first) and KIT.has_lines(step, first):
		_said[first] = true
		await KIT.lines(story, step, first)
	else:
		await KIT.lines(story, step, rest)


## 冒泡那根管子咕噜一声（声音大小跟冒泡档数走、左右声道跟着管口）
func _gurgle() -> void:
	var b := bubbling(step, s)
	if int(b[0]) < 0:
		return
	await KIT.steps(story, [{"do": "sfx", "name": "pipe_gurgle_%d" % int(b[1]), "db": -4.0 if int(b[1]) >= 3 else -10.0}])


## 水位、管子冒泡、闸轮刻度摆成现在的样子
func _show_state(instant: bool) -> void:
	var water: Dictionary = step.get("water", {})
	var lv: Array = water.get("levels", [])
	if not lv.is_empty() and water.has("prop"):
		world.set_prop(str(water["prop"]), str(lv[clampi(int(s["solved"]), 0, lv.size() - 1)]))
	var pipes: Dictionary = step.get("pipes", {})
	if pipes.has("prop"):
		var b := bubbling(step, s)
		var names: Array = pipes.get("names", [])
		var on := int(b[0]) >= 0 and int(b[0]) < names.size()
		world.set_prop(str(pipes["prop"]), ("%s_bubble_%d" % [names[int(b[0])], int(b[1])]) if on else "still")
	var ws := smalls(step)
	for i in ws.size():
		world.set_prop(str(ws[i]["id"]), "set" if i < int(s["solved"]) else "n%d" % int(s["n"][i]))
	if not instant and not story.ff:
		await KIT.steps(story, [{"do": "sfx", "name": "water_drop"}, {"do": "wait", "sec": 1.5}])
	await _gurgle()


## 不对的格子：水涌上来一下，再落回上一个稳定状态（原文 107）
func _surge() -> void:
	var sg: Node2D = world.stage(str(step.get("water", {}).get("room", "oldstreet")))
	await KIT.steps(story, [{"do": "sfx", "name": "water_surge"}])
	if sg != null and not story.ff:
		var y0: float = sg.water_y()
		await sg.set_water(y0 - SURGE, 0.5)
		await sg.set_water(y0, 0.9)
	await _show_state(true)


## 跳节拍：闸调好、板子记好（同步、不演）
func ff(_r: Node, st: Dictionary) -> void:
	var t := fresh(st)
	for k in 20:
		var res := act(st, t, best(st, t))
		if res["kind"] == "set":
			var row: Dictionary = (smalls(st)[int(res["i"])].get("row", {}) as Dictionary).duplicate(true)
			if not row.is_empty():
				row["done"] = true
				KIT.board_add(row)
		if res["kind"] == "open":
			break
	t["intro"] = true
	_r.mech_save(ID, t)
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))


func check(r: Node, st: Dictionary) -> Array:
	var out: Array = []
	var ws := smalls(st)
	if ws.size() < 1:
		out.append("wheels 至少一只小闸轮")
		return out
	for w in ws:
		if not w.has("id") or not w.has("right"):
			out.append("闸轮要有 id / right：%s" % str(w))
		elif int(w["right"]) < 1 or int(w["right"]) > notches(w):
			out.append("%s 的 right 不在 1..%d" % [w["id"], notches(w)])
	if not st.has("big"):
		out.append("没有 big（大闸轮）")
	if (st.get("sets", []) as Array).is_empty():
		out.append("没有 sets（开闸以后设的 flag，剧本下一步 if 要用）")
	# 乱点一通（转错的、转不冒泡的、先转大的），每一步之后都还能开闸：错的只回退不卡
	var t := fresh(st)
	for c in ["w1", "big", "w0", "w0", "w1", "big", "w1", "w0", "look:pipes", "leave", "w1", "w1", "w0", "big"]:
		act(st, t, c)
		if not solvable(st, t):
			out.append("点了 %s 以后解不开了" % c)
			break
	if not solvable(st, fresh(st)):
		out.append("从头照对的走解不开")
	for key in ["intro", "first_set", "second_set", "big_early"]:
		if not KIT.has_lines(st, key):
			out.append("info: 没有 lines.%s" % key)
	var spots: Array = [str(st.get("big", {}).get("id", "")), str(st.get("leave", {}).get("at", ""))]
	for w in ws:
		spots.append(str(w.get("id", "")))
	for l in st.get("looks", []):
		spots.append(str(l.get("id", "")))
	for m in spots:
		if m != "" and not r.world.has_marker(m):
			out.append("互动点 %s 找不到（marker / 物件）" % m)
	for k in st.get("lines", {}):
		out.append_array(KIT.check_steps(r, "lines.%s" % k, st["lines"][k]))
	return out
