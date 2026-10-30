extends RefCounted
## 河流篇小游戏 river_salvage：顺水打捞（原文 76，剧情姐写的玩法原样落地）。
##   76：顺着水流打捞收藏品和修船材料。水声与碰撞声提示物品方向，漂浮轨迹提供同步视觉信息。不同物品具有不同浮力，
##       玩家需要判断打捞顺序；错过的关键物品会停在下游浅滩，玩家可以在那里继续打捞。
##   前情（原文 74–75，剧本已演）：妮芙掉了一箱；先捞快碰到台阶的杯子，金属盒沉进较浅的水里，「还看得见。它先坐一会儿」。
##
## 怎么玩（点水面上漂着的东西，没有计时、不会失败）：
##   妮芙那一箱里的几样东西 + 修船材料（管道接头）顺着水往下游漂，每样后面一道 V 形水纹（物件状态 float，美术画在物件上）。
##   漂是「一手一手」的：晨每钩一样（走到岸边、hook），别的东西就各往下游漂一段——轻的浮得高、一次漂两段；重的吃水深、
##   一次漂一段，漂过它的下沉点就沉下去（沉在看得见的浅水里，像金属盒）。所以要判断顺序：重的、会沉的先捞（原文「不同浮力」）。
##   每次漂：水声跟着那样东西的位置走（左右声道），漂过木桩「咚」一声（碰撞声）。
##   关键物品（管道接头）不会沉：没捞到就停在下游浅滩。轻的也会漂到浅滩停住。河里没东西漂了，晨走到浅滩，把停在那里的
##   一样样捞上来（原文「在那里继续打捞」），连同刚才沉进浅水的金属盒（「它先坐一会儿」）。错过沉掉的收藏品不扣任何东西。
##   捞上来的收藏品交给妮芙（全捞到 lines.give_all，沉掉了几样 lines.give_some，补写）。剧本接着给管道接头、「这个能用在飞机上。」
##
## 剧本步骤：{"do": "mechanic", "id": "river_salvage", "path": {from, to, post, stages}, "items": [{id, label, speed, sink, start, key?}…],
##   "box": {id, label}, "lines": {start, sank_1, sank, shallows, give_all, give_some, got_key}}
##   items 的 sink：漂到第几段就沉（-1 = 不沉）；speed：每手漂几段；start：一开始在第几段；stages = 从上游到浅滩一共几段（到 stages 就停在浅滩）。
## 进度（story.mech_load）：{items: {id: {at, st}}, box: bool, phase: river / shallows / done}；st = float / sunk / shallow / got。
## 物件状态（给会话 C）：漂流物 float（带 V 形水纹）/ sunk（沉在看得见的浅水里）/ shallow（停在浅滩）/ taken（钩上来了，藏起来）。

const KIT := preload("res://scripts/river_explore_order.gd")
const ID := "river_salvage"


# ======================================================================= 规则（纯函数）
static func stages(step: Dictionary) -> int:
	return int((step.get("path", {}) as Dictionary).get("stages", 5))


static func fresh(step: Dictionary) -> Dictionary:
	var it := {}
	for d in step.get("items", []):
		it[str(d["id"])] = {"at": int(d.get("start", 0)), "st": "float"}
	return {"items": it, "box": false, "phase": "river"}


static func defs(step: Dictionary) -> Dictionary:
	var out := {}
	for d in step.get("items", []):
		out[str(d["id"])] = d
	return out


static func floating(s: Dictionary) -> Array:
	var out: Array = []
	for id in s["items"]:
		if str(s["items"][id]["st"]) == "float":
			out.append(id)
	return out


static func at_shallows(s: Dictionary) -> Array:
	var out: Array = []
	for id in s["items"]:
		if str(s["items"][id]["st"]) == "shallow":
			out.append(id)
	return out


## 别的东西漂一手：返回 [{id, from, to, st}]（st 变了 = sunk / shallow）
static func drift(step: Dictionary, s: Dictionary, except := "") -> Array:
	var moved: Array = []
	var n := stages(step)
	var dd := defs(step)
	for id in s["items"]:
		var e: Dictionary = s["items"][id]
		if id == except or str(e["st"]) != "float":
			continue
		var d: Dictionary = dd[id]
		var a := int(e["at"])
		var b := mini(a + int(d.get("speed", 1)), n)
		e["at"] = b
		var sink := int(d.get("sink", -1))
		if not d.get("key", false) and sink >= 0 and b >= sink:
			e["at"] = sink
			e["st"] = "sunk"
		elif b >= n:
			e["st"] = "shallow"
		moved.append({"id": id, "from": a, "to": int(e["at"]), "st": str(e["st"])})
	return moved


## 钩一样（河里的 / 浅滩上的）。返回 {kind: got / none, id, drift: [...]}
static func act(step: Dictionary, s: Dictionary, id: String) -> Dictionary:
	if id == "box":
		if s["phase"] == "shallows" and not s["box"]:
			s["box"] = true
			_advance_phase(s)
			return {"kind": "got", "id": "box", "drift": []}
		return {"kind": "none"}
	if not s["items"].has(id):
		return {"kind": "none"}
	var e: Dictionary = s["items"][id]
	if str(e["st"]) == "float":
		e["st"] = "got"
		var dr := drift(step, s, id)
		_advance_phase(s)
		return {"kind": "got", "id": id, "drift": dr}
	if str(e["st"]) == "shallow" and s["phase"] == "shallows":
		e["st"] = "got"
		_advance_phase(s)
		return {"kind": "got", "id": id, "drift": []}
	return {"kind": "none"}


static func _advance_phase(s: Dictionary) -> void:
	if s["phase"] == "river" and floating(s).is_empty():
		s["phase"] = "shallows"
	if s["phase"] == "shallows" and at_shallows(s).is_empty() and s["box"]:
		s["phase"] = "done"


static func key_ids(step: Dictionary) -> Array:
	var out: Array = []
	for d in step.get("items", []):
		if d.get("key", false):
			out.append(str(d["id"]))
	return out


static func collectibles(step: Dictionary) -> int:
	return (step.get("items", []) as Array).size() - key_ids(step).size()


static func got_count(step: Dictionary, s: Dictionary) -> int:
	var n := 0
	for id in s["items"]:
		if str(s["items"][id]["st"]) == "got" and not id in key_ids(step):
			n += 1
	return n


## 「对的」顺序：先钩会最早沉掉的，再钩下游最远的
static func best(step: Dictionary, s: Dictionary) -> String:
	if s["phase"] == "shallows":
		var sh := at_shallows(s)
		return str(sh[0]) if not sh.is_empty() else "box"
	var dd := defs(step)
	var pick := ""
	var left := 999
	for id in floating(s):
		var d: Dictionary = dd[id]
		var sink := int(d.get("sink", -1))
		var room := 999 if sink < 0 or d.get("key", false) else (sink - int(s["items"][id]["at"])) / maxi(1, int(d.get("speed", 1)))
		if pick == "" or room < left:
			pick = id
			left = room
	return pick


static func finished(s: Dictionary) -> bool:
	return s["phase"] == "done"


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
	if not s.has("items"):
		s = fresh(step)
		story.mech_save(ID, s)
		await KIT.lines(story, step, "start")
	await _place_all(0.0)
	while not story.ended and not finished(s):
		if s["phase"] == "shallows" and not s.get("walked", false):
			s["walked"] = true
			story.mech_save(ID, s)
			await KIT.lines(story, step, "shallows")
		var c: String = await _ask()
		var res := act(step, s, c)
		story.mech_save(ID, s)
		if res["kind"] == "got":
			await _hook(str(res["id"]), res["drift"])
	await KIT.lines(story, step, "give_all" if got_count(step, s) >= collectibles(step) else "give_some")
	print("MECH %s done got=%d/%d" % [ID, got_count(step, s), collectibles(step)])


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


## 这一轮能钩的：河里漂着的（跟着物件走的点），到了浅滩就是停在浅滩的 + 金属盒
func _ask() -> String:
	var opts: Array = []
	var ok := best(step, s)
	var dd := defs(step)
	var ids: Array = floating(s) if s["phase"] == "river" else at_shallows(s)
	for id in ids:
		opts.append({"tok": id, "at": id, "label": dd[id].get("label", id), "correct": id == ok})
	if s["phase"] == "shallows" and not s["box"]:
		var b: Dictionary = step.get("box", {})
		opts.append({"tok": "box", "at": str(b.get("id", "river_bank_box")), "label": b.get("label", "box"), "correct": ok == "box"})
	return await KIT.choose(self, story, opts)


## 第几段在房间里的 x（上游 from → 浅滩 to）
func _x(stage: int) -> float:
	var p: Dictionary = step.get("path", {})
	var a := KIT.local_x(world, str(p.get("from", "")), 0.0)
	var b := KIT.local_x(world, str(p.get("to", "")), a + 200.0)
	return round(lerpf(a, b, clampf(float(stage) / float(maxi(1, stages(step))), 0.0, 1.0)))


## 每样东西放到它那一段（sec = 0 瞬间到位）
func _place_all(sec: float) -> void:
	for id in s["items"]:
		var e: Dictionary = s["items"][id]
		world.set_prop(id, _state_of(str(e["st"])))
		if str(e["st"]) != "got":
			await _move(id, int(e["at"]), sec, false)
	if s["box"]:
		world.set_prop(str((step.get("box", {}) as Dictionary).get("id", "river_bank_box")), "taken")


static func _state_of(st: String) -> String:
	return "taken" if st == "got" else st


func _move(id: String, stage: int, sec: float, wait: bool) -> void:
	var sg := KIT.stage_of(world, id)
	if sg == null or sg.object(id) == null:
		return
	var p := Vector2(_x(stage) - float(sg.object(id).texture.get_width() / maxi(1, sg.object(id).hframes)) / 2.0, sg.object(id).position.y)
	if sec <= 0.0 or story.ff:
		sg.move_object(id, p, 0.0)
	elif wait:
		await sg.move_object(id, p, sec)
	else:
		sg.move_object(id, p, sec)


func _hook(id: String, dr: Array) -> void:
	var tid := id if id != "box" else str((step.get("box", {}) as Dictionary).get("id", "river_bank_box"))
	await KIT.go_to(self, story, tid)
	await KIT.steps(story, [{"do": "anim", "who": "chen", "name": "hook"}, {"do": "sfx", "name": "hook_splash"}])
	world.set_prop(tid, "taken")
	# 别的东西趁这一下往下漂：水纹往前、水声跟着走（左右声道），漂过木桩咚一声
	var post := KIT.local_x(world, str((step.get("path", {}) as Dictionary).get("post", "")), NAN)
	var sank := false
	for m in dr:
		var x0 := _x(int(m["from"]))
		var x1 := _x(int(m["to"]))
		var steps: Array = [{"do": "sfx", "name": "drift_water", "db": -8.0, "pan": _pan(x1)}]
		if not is_nan(post) and x0 < post and x1 >= post:
			steps.append({"do": "sfx", "name": "knock_post", "pan": _pan(post)})
		await KIT.steps(story, steps)
		_move(str(m["id"]), int(m["to"]), 1.2, false)
		world.set_prop(str(m["id"]), _state_of(str(m["st"])))
		if str(m["st"]) == "sunk":
			sank = true
	if not dr.is_empty():
		await KIT.steps(story, [{"do": "wait", "sec": 1.2}])
	if sank:
		if not _said.has("sank_1"):
			_said["sank_1"] = true
			await KIT.lines(story, step, "sank_1")
		else:
			await KIT.lines(story, step, "sank")
	if id in key_ids(step):
		await KIT.lines(story, step, "got_key")


## 房间 x → 左右声道（-1..1，按镜头）
func _pan(lx: float) -> float:
	var sg: Node2D = world.cur_stage() if world.has_method("cur_stage") else null
	var wx: float = sg.to_world(Vector2(lx, 0)).x if sg != null else lx
	return clampf((wx - story.level.cam_left().x - 240.0) / 240.0, -1.0, 1.0)


## 跳节拍：照对的顺序捞完（同步、不演）
func ff(r: Node, st: Dictionary) -> void:
	var t := fresh(st)
	for k in 40:
		if finished(t):
			break
		act(st, t, best(st, t))
	r.mech_save(ID, t)
	for id in t["items"]:
		r.world.set_prop(id, _state_of(str(t["items"][id]["st"])))
	r.world.set_prop(str((st.get("box", {}) as Dictionary).get("id", "river_bank_box")), "taken")


func check(story: Node, st: Dictionary) -> Array:
	var out: Array = []
	if key_ids(st).is_empty():
		out.append("items 里没有关键物品（key: true）")
	for d in st.get("items", []):
		if not d.has("id") or not d.has("label"):
			out.append("物品要有 id / label：%s" % str(d))
	# 任何顺序都能捞完、关键物品一定到手
	var orders := [[], ["rev"]]
	for o in orders:
		var t := fresh(st)
		for k in 60:
			if finished(t):
				break
			var c := best(st, t)
			if not o.is_empty():
				var fl := floating(t) if t["phase"] == "river" else at_shallows(t)
				c = str(fl[fl.size() - 1]) if not fl.is_empty() else "box"
			act(st, t, c)
		if not finished(t):
			out.append("顺序 %s 捞不完" % str(o))
		for kid in key_ids(st):
			if str(t["items"][kid]["st"]) != "got":
				out.append("顺序 %s 关键物品 %s 没捞到" % [str(o), kid])
	for key in ["give_all", "give_some"]:
		if not KIT.has_lines(st, key):
			out.append("info: 没有 lines.%s" % key)
	for m in ["from", "to", "post"]:
		var mk := str((st.get("path", {}) as Dictionary).get(m, ""))
		if not story.world.has_marker(mk):
			out.append("path.%s 的 marker %s 找不到" % [m, mk])
	for d in st.get("items", []):
		if not story.world.has_marker(str(d.get("id", ""))):
			out.append("漂流物 %s 没有同名 marker / 物件（引擎画占位要它）" % d.get("id"))
	for k in st.get("lines", {}):
		out.append_array(KIT.check_steps(story, "lines.%s" % k, st["lines"][k]))
	return out
