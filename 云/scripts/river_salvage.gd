extends RefCounted
## 河流篇小游戏 river_salvage：顺水打捞（原文 76，剧情姐写的玩法原样落地）。
##   76：顺着水流打捞收藏品和修船材料。水声与碰撞声提示物品方向，漂浮轨迹提供同步视觉信息。不同物品具有不同浮力，
##       玩家需要判断打捞顺序；错过的关键物品会停在下游浅滩，玩家可以在那里继续打捞。
##   前情（原文 74–75，剧本已演）：泥芙掉了一箱；先捞快碰到台阶的杯子，金属盒沉进较浅的水里，「还看得见。它先坐一会儿」。
##
## 11-02 重做（作者：「捞东西有小游戏吗？不要点点点吧」）：实时抛钩。没有计时、不会失败。
## 11-03 第二版（作者：「钩子有 bug，难度过高、会卡住、角色翻转直接翻到另一边」）：自动瞄准、大范围、不会卡、抛之前先转身。
##   漂：东西一直顺着水往下游漂（左 → 右），各漂各的速度。轻的（speed 2）浮得高、漂得快、轻轻一上一下；
##       重的（有 sink）吃水深、越靠近下沉点漂得越慢，吃水越来越深（物件状态 sink1 / sink2），冒小气泡；
##       漂过下沉点就沉下去（sunk，沉在看得见的浅水里，像金属盒「它先坐一会儿」）。
##       关键物品（管道接头）和轻的漂到头就停在下游浅滩（shallow）。漂过木桩「咚」一声，水声跟着走（左右声道）。
##   走：晨照常在岸上左右走（剧情放手，方向键 / A D）。
##   抛（11-03 第三版，作者：「怎么改成自动吸附了，好奇怪」——钩子半路拐弯太假）：
##       按下 E / 空格 / 鼠标左键：晨先转向离她最近的那样东西所在的那边（chen.gd 自己的 _set_facing，锚点不跳），站定；
##       按住：水面上一个落点圈（实心像素的扁圈 + 一个一上一下的小浮标）从脚边往外滑，滑到最远（SWEEP_SEC 秒）再滑回来，
##       来回摆，错过了不吃亏；松手：钩子顺着一道自然的抛物线飞到落点，半路不拐弯。
##       落点离东西 CATCH 像素以内 = 钩住：钩子「扑通」落在它旁边，线一绷，拽两下（东西被拉过来一点），「哗」地出水、
##       顺着弧线飞到晨手里，镜头轻轻一顿。没钩到 = 溅一下、一圈水纹，收线。连着 MISS_HELP 次没钩到，判定悄悄放宽到 CATCH_HELP。
##       按键是每帧轮询的（不靠输入事件的先后顺序），抛的时候晨的方向键先停一下，收完线还给玩家。
##   浅滩：河里没东西漂了（都钩走 / 沉了 / 停在浅滩），播 lines.shallows（晨走到浅滩），再把停在那里的、连同沉在浅水里的
##       金属盒一样样钩上来（同样是抛钩）。错过沉掉的收藏品不扣任何东西。
##   兜底（不会卡住）：河里 NO_CATCH 秒没钩到东西、或者漂了 RIVER_CAP 秒，剩下漂着的一起快快漂到浅滩（这时候也不沉了）；
##       浅滩上 SHALLOW_NET 秒没钩到、或者浅滩阶段过了 SHALLOW_CAP 秒，剩下的泥芙在下游接走（溅一下、收走）。抛钩卡在半路超过 WATCHDOG 秒就收回来重置。
##   泥芙：实时冒一句（dlg.murmur，不挡操作，最快 SAY_GAP 秒一句）：sank_1 / sank（沉了）、got_key、站着不动 HINT_SEC 秒 hint_sink / hint。
##   捞上来的收藏品交给泥芙（全捞到 lines.give_all，沉掉了几样 lines.give_some）。剧本接着给管道接头、「这个能用在飞机上。」
##
## 剧本步骤（没变）：{"do": "mechanic", "id": "river_salvage", "path": {from, to, post, stages}, "items": [{id, label, speed, sink, start, key?}…],
##   "box": {id, label}, "lines": {start, sank_1, sank, shallows, give_all, give_some, got_key, hint, hint_sink}}
##   path：from（上游起点）→ to（浅滩）的 marker，中间等分 stages 段；items 的 start / sink 都按段算（sink = 漂到第几段就沉，-1 = 不沉），
##   speed = 漂的快慢（1 慢 / 2 快，每段 SPEED_PX 像素每秒 × speed）。marker 都按漂流物所在的那个房间读。
## 进度（story.mech_load）：{items: {id: {at, st, x, slot?}}, box: bool, phase: river / shallows / done, walked?}；st = float / sunk / shallow / got。
##   x = 房间里的像素位置（物件中心）；at = 现在在第几段（跳节拍 / check 的纯函数还按段算）。
## 物件状态（给会话 C）：漂流物 float / sink1 / sink2（吃水更深）/ sunk / shallow / taken。
## 规则和画面分开：Sim（内部类，纯数据，不碰节点）管漂、沉、停、兜底、瞄谁、钩没钩到；测试直接拿 Sim 模拟。
## 调试：--story_auto 时加 --salvage_mash = 不用自动玩的瞄准，改成「乱按的玩家」（随机走、随机按住 / 松手），打印用了多少秒。
## 测试用的纯函数：sweep(按住几秒) = 落点在 REACH_MIN..REACH_MAX 之间走到哪（0..1），reach_at(按住几秒) = 离晨多远。

const KIT := preload("res://scripts/river_explore_order.gd")
const ID := "river_salvage"
const SLOT := 22.0             # 停在浅滩的几样东西并排摆开的间距（物件 18 宽 + 4）
const SPEED_PX := 9.0          # speed 1 每秒漂几像素
const CATCH := 18.0            # 钩子落点离东西中心多近算钩住（只在落水那一下判断，钩子半路不拐弯）
const CATCH_HELP := 30.0       # 连着没钩到 MISS_HELP 次以后，悄悄放宽到这么多（看不出来的帮一把）
const MISS_HELP := 3
const REACH_MIN := 24.0        # 落点离晨最近 / 最远（水平距离）
const REACH_MAX := 190.0
const SWEEP_SEC := 1.7         # 按住时落点从最近滑到最远要多久（再按着就滑回来，来回摆，错过了不吃亏）
const NO_CATCH := 20.0         # 河里这么久没钩到 → 剩下的快快漂去浅滩
const RIVER_CAP := 30.0        # 河里漂了这么久 → 同上
const SHALLOW_NET := 12.0      # 浅滩这么久没钩到 → 剩下的泥芙接走
const SHALLOW_CAP := 18.0      # 浅滩阶段过了这么久 → 同上（一样一样慢慢钩也不会拖太久）
const RUSH := 8.0              # 快快漂去浅滩时的速度倍数
const WATCHDOG := 5.0          # 抛钩卡在半路超过这么久 → 重置
const HINT_SEC := 12.0         # 这么久没抛，泥芙提醒一句
const SAY_GAP := 4.0           # 泥芙两句之间至少隔几秒
const DRIFT_IN := 110.0        # 第一次开始：从上游多远的地方淡入漂进来（11-02 作者：对话完漂浮物突然出现很奇怪）
const HAND := Vector2(10, -24) # 晨的手（相对脚底，朝右；朝左翻过来）：斗篷前襟那里
const LINE_C := Color("#c9d3cd")
const AIM_C := Color("#7fa3a8")
const RING_C := Color("#a9c6d0")
const DROP_C := Color("#d6e4ea")


# ======================================================================= 规则（纯函数，跳节拍 / check 用；按段算）
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


## 跳节拍 / check：别的东西漂一手（按段），返回 [{id, from, to, st}]
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


## 跳节拍 / check：钩一样（钩一手、别的漂一手）。返回 {kind: got / none, id, drift}
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


## 按住 t 秒时落点走到哪（0 = 脚边 REACH_MIN，1 = 最远 REACH_MAX）：缓起缓停地滑出去，再滑回来，来回摆
static func sweep(t: float) -> float:
	return 0.5 - 0.5 * cos(PI * t / SWEEP_SEC)


static func reach_at(t: float) -> float:
	return lerpf(REACH_MIN, REACH_MAX, sweep(t))




# ======================================================================= 实时规则（Sim：只算数，不碰节点）
class Sim:
	var step: Dictionary
	var s: Dictionary
	var x0 := 0.0               # 上游起点（房间 x）
	var x1 := 200.0             # 浅滩
	var post := NAN
	var box_x := NAN
	var n := 5
	var spx := 40.0             # 一段多少像素
	var k := 1.0                # 漂的快慢倍数（自动玩加快）
	var dd := {}
	var rush := false           # 兜底：剩下漂着的快快漂去浅滩（不沉）
	var since := 0.0            # 多久没钩到东西了
	var phase_t := 0.0          # 这个阶段过了多久
	var events: Array = []      # tick / take 以后发生的：[{kind: sink / shallow / post / phase / rush / net, id}]

	func _init(st: Dictionary, state: Dictionary, from_x: float, to_x: float, post_x := NAN, box := NAN) -> void:
		step = st
		s = state
		x0 = from_x
		x1 = to_x if to_x > from_x + 40.0 else from_x + 430.0      # marker 读错了也不会漂不到头
		post = post_x
		box_x = box
		n = maxi(1, int((st.get("path", {}) as Dictionary).get("stages", 5)))
		spx = (x1 - x0) / float(n)
		dd = defs_of(st)
		var by_at := {}
		for id in s["items"]:
			var at := int(s["items"][id]["at"])
			if not by_at.has(at):
				by_at[at] = []
			by_at[at].append(id)
		for id in s["items"]:
			var e: Dictionary = s["items"][id]
			if not e.has("x"):
				# 刚开始 / 旧存档（按段）：放到那一段，同一段的几样按剧本顺序并排错开（不叠成一样）
				var same: Array = by_at[int(e["at"])]
				e["x"] = x0 + float(e["at"]) * spx + (float(same.find(id)) - float(same.size() - 1) / 2.0) * SLOT
			if str(e["st"]) == "shallow" and not e.has("slot"):
				e["slot"] = _next_slot()

	static func defs_of(st: Dictionary) -> Dictionary:
		var out := {}
		for d in st.get("items", []):
			out[str(d["id"])] = d
		return out

	func d(id: String) -> Dictionary:
		return dd.get(id, {})

	func heavy(id: String) -> bool:
		return int(d(id).get("sink", -1)) >= 0 and not d(id).get("key", false)

	func sink_x(id: String) -> float:
		return x0 + float(int(d(id).get("sink", -1))) * spx if heavy(id) else INF

	## 漂得多快：轻的快；重的越靠近下沉点越慢（还剩 1.5 段起慢下来，到点时剩 45%）；兜底时都快快漂
	func speed(id: String) -> float:
		var v := SPEED_PX * float(maxi(1, int(d(id).get("speed", 1)))) * k
		if rush:
			return v * RUSH
		if heavy(id):
			var left := sink_x(id) - float(s["items"][id]["x"])
			v *= lerpf(0.45, 1.0, clampf(left / (spx * 1.5), 0.0, 1.0))
		return v

	## 物件该显示的状态：会沉的离下沉点不到两段 = sink1，不到一段 = sink2
	func vis(id: String) -> String:
		var e: Dictionary = s["items"][id]
		var st := str(e["st"])
		if st == "float" and heavy(id) and not rush:
			var left := sink_x(id) - float(e["x"])
			if left <= spx:
				return "sink2"
			if left <= spx * 2.0:
				return "sink1"
		return "taken" if st == "got" else st

	func slot_x(id: String) -> float:
		return x1 - float(int(s["items"][id].get("slot", 0))) * SLOT

	func _next_slot() -> int:
		var used := {}
		for oid in s["items"]:
			var e: Dictionary = s["items"][oid]
			if str(e["st"]) == "shallow" and e.has("slot"):
				used[int(e["slot"])] = true
		var i := 0
		while used.has(i):
			i += 1
		return i

	func tick(dt: float) -> void:
		since += dt
		phase_t += dt
		if s["phase"] == "river" and not rush and (since >= NO_CATCH or phase_t >= RIVER_CAP):
			rush = true
			events.append({"kind": "rush", "id": ""})
		for id in s["items"]:
			var e: Dictionary = s["items"][id]
			var st := str(e["st"])
			if st == "shallow":
				var gx := slot_x(id)
				e["x"] = float(e["x"]) + (gx - float(e["x"])) * minf(1.0, dt * 2.5)    # 缓缓挪进自己那格
				continue
			if st != "float":
				continue
			var a := float(e["x"])
			var b := a + speed(id) * dt
			if not is_nan(post) and a < post and b >= post:
				events.append({"kind": "post", "id": id})
			e["x"] = b
			e["at"] = clampi(int(floor((b - x0) / spx)), 0, n)
			if heavy(id) and not rush and b >= sink_x(id):
				e["x"] = sink_x(id)
				e["at"] = int(d(id).get("sink", 0))
				e["st"] = "sunk"
				events.append({"kind": "sink", "id": id})
			elif b >= x1:
				e["st"] = "shallow"
				e["at"] = n
				e["slot"] = _next_slot()
				events.append({"kind": "shallow", "id": id})
		_phase()
		if s["phase"] == "shallows" and (since >= SHALLOW_NET or phase_t >= SHALLOW_CAP):
			# 兜底：浅滩上半天没钩到，剩下的泥芙在下游接走
			for id in s["items"]:
				if str(s["items"][id]["st"]) == "shallow":
					s["items"][id]["st"] = "got"
					events.append({"kind": "net", "id": id})
			if not s["box"]:
				s["box"] = true
				events.append({"kind": "net", "id": "box"})
			_phase()

	func _phase() -> void:
		var was := str(s["phase"])
		_advance_phase_of(s)
		if str(s["phase"]) != was:
			phase_t = 0.0
			since = 0.0
			events.append({"kind": "phase", "id": str(s["phase"])})

	static func _advance_phase_of(state: Dictionary) -> void:
		if state["phase"] == "river":
			var any := false
			for id in state["items"]:
				any = any or str(state["items"][id]["st"]) == "float"
			if not any:
				state["phase"] = "shallows"
		if state["phase"] == "shallows" and state["box"]:
			var left := false
			for id in state["items"]:
				left = left or str(state["items"][id]["st"]) == "shallow"
			if not left:
				state["phase"] = "done"

	## 现在能钩的：河里漂着的；到了浅滩阶段 = 停在浅滩的 + 金属盒。[{id, x}]
	func hookable() -> Array:
		var out: Array = []
		for id in s["items"]:
			var st := str(s["items"][id]["st"])
			if (s["phase"] == "river" and st == "float") or (s["phase"] == "shallows" and st == "shallow"):
				out.append({"id": id, "x": float(s["items"][id]["x"])})
		if s["phase"] == "shallows" and not s["box"] and not is_nan(box_x):
			out.append({"id": "box", "x": box_x})
		return out

	## 自动瞄准：晨站在 cx、朝 facing、够得着 reach。前面够得着的挑最近的；前面没有就挑后面最近的。没有 = {}
	func aim(cx: float, facing: int, reach: float) -> Dictionary:
		var front := {}
		var back := {}
		var fd := INF
		var bd := INF
		for h in hookable():
			var dx := float(h["x"]) - cx
			var dist := absf(dx)
			if dist > reach + CATCH:
				continue
			if dx * facing >= -6.0:
				if dist < fd:
					fd = dist
					front = h
			elif dist < bd:
				bd = dist
				back = h
		return front if not front.is_empty() else back

	## 钩子落在 x：钩住的那样（最近的），没钩到 = ""
	func catch_at(x: float, radius := CATCH) -> String:
		var best_id := ""
		var bd := radius + 0.001
		for h in hookable():
			var dx := absf(float(h["x"]) - x)
			if dx < bd:                     # 叠在一起的几样：钩先列出来的那样
				bd = dx
				best_id = str(h["id"])
		return best_id

	func can_hook(id: String) -> bool:
		for h in hookable():
			if str(h["id"]) == id:
				return true
		return false

	func take(id: String) -> void:
		if id == "box":
			s["box"] = true
		elif s["items"].has(id):
			s["items"][id]["st"] = "got"
		since = 0.0
		_phase()

	func x_of(id: String) -> float:
		if id == "box":
			return box_x
		return float(s["items"][id]["x"]) if s["items"].has(id) else NAN

	func pop_events() -> Array:
		var out := events
		events = []
		return out


# ======================================================================= 画面（钩子、线、水纹、水花都画在这个节点上，放在房间里）
class Rig extends Node2D:
	var m

	func _process(dt: float) -> void:
		if m != null:
			m._tick(dt)
			queue_redraw()

	func _draw() -> void:
		if m != null:
			m._draw_rig(self)

	func _input(e: InputEvent) -> void:
		if m != null:
			m._swallow(e)


var auto_mode := false
var tried := {}
var story: Node
var world: Node2D
var step: Dictionary
var s: Dictionary
var sim: Sim
var sg: Node2D                 # 漂流物所在的那个房间（room_stage.gd）
var rig: Rig
var _water_y := 217.0          # 漂流物在水面那一行（房间 y，按物件图里实际画着的地方算）
var _cy := {}                  # 物件 id → 图里画着的东西的中心离图顶多远
var _free := false             # 现在晨能自己走、能抛
var _base_y := {}              # 物件 id → 原来的 y（漂的时候只改 x、轻的上下一像素）
var _shown := {}               # 物件 id → 现在显示的状态（变了才 set_prop，免得动画重头播）
var _lift := {}                # 正在被拽出水的那样：不归 Sim 摆
var _mash := false             # --salvage_mash：乱按的玩家
# 抛钩
var cast := "idle"             # idle / charge / fly / wait / catch / reel
var _btn_prev := false
var _from := Vector2.ZERO
var _land := Vector2.ZERO
var _hook := Vector2.ZERO
var _ct := 0.0
var _cdur := 0.0
var _cast_t := 0.0             # 这一抛过了多久（看门狗）
var _gen := 0                  # 每抛一次 +1；看门狗重置时也 +1，旧的协程看到不一样就收手
var _target := ""
var _hold := 0.0               # 按住了多久（落点圈跟着 sweep 来回滑）
var _misses := 0               # 连着没钩到几次
var _sag := 8.0
var _locked := false
# 效果
var _rings: Array = []         # [{p, t, big}]
var _drops: Array = []         # [{p, v, t}]
var _bubbles: Array = []       # [{p, t}]
var _bub_t := 0.0
var _t := 0.0
var _play_t := 0.0             # 放手让玩家打捞的总时间（--salvage_mash 打印）
var _idle_t := 0.0
var _said_t := -99.0
var _said := {}
var _save_t := 0.0
var _fast_in := 0.0
# 乱按
var _mash_btn := false
var _mash_t := 0.0
var _mash_walk := 0.0
var _rng := RandomNumberGenerator.new()


func run(_level: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	world = w
	step = st
	_mash = auto_mode and "--salvage_mash" in OS.get_cmdline_user_args()
	_rng.seed = 7
	s = story.mech_load(ID)
	var first := not s.has("items")
	if first:
		s = fresh(step)
		story.mech_save(ID, s)
		await KIT.lines(story, step, "start")
	_setup()
	if first:
		_drift_in()
	while not story.ended and not finished(s):
		if s["phase"] == "shallows" and not s.get("walked", false):
			s["walked"] = true
			story.mech_save(ID, s)
			_release(false)
			await _settle()
			await KIT.lines(story, step, "shallows")
		_release(true)
		await _until_phase_change()
	_release(false)
	_teardown()
	story.mech_save(ID, s)
	await KIT.lines(story, step, "give_all" if got_count(step, s) >= collectibles(step) else "give_some")
	print("MECH %s done got=%d/%d play_t=%.1f" % [ID, got_count(step, s), collectibles(step), _play_t])


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


## 跳节拍：照对的顺序捞完（同步、不演）
func ff(r: Node, st: Dictionary) -> void:
	var t := fresh(st)
	for k in 40:
		if finished(t):
			break
		act(st, t, best(st, t))
	r.mech_save(ID, t)
	for id in t["items"]:
		r.world.set_prop(id, "taken" if str(t["items"][id]["st"]) == "got" else str(t["items"][id]["st"]))
	r.world.set_prop(str((st.get("box", {}) as Dictionary).get("id", "river_bank_box")), "taken")


# ----------------------------------------------------------------------- 搭 / 拆
func _setup() -> void:
	var p: Dictionary = step.get("path", {})
	var any_id := ""
	for d in step.get("items", []):
		any_id = str(d.get("id", ""))
		break
	sg = KIT.stage_of(world, any_id)
	var a := _mloc(str(p.get("from", "")), 0.0)
	var b := _mloc(str(p.get("to", "")), a + 430.0)
	var post := _mloc(str(p.get("post", "")), NAN)
	var box_id := _box_id()
	var bo := _obj(box_id)
	var bx := NAN
	if bo != null and bo.texture != null:
		bx = bo.position.x + float(bo.texture.get_width() / maxi(1, bo.hframes)) * 0.5    # 金属盒的中心（房间 x）
		_cy["box"] = _content_cy(bo)
	elif not is_nan(_mloc(box_id, NAN)):
		bx = _mloc(box_id, NAN)
	sim = Sim.new(step, s, a, b, post, bx)
	sim.k = 3.0 if auto_mode and not _mash else 1.0
	var ys: Array = []
	for id in s["items"]:
		var o := _obj(id)
		if o != null:
			_base_y[id] = o.position.y
			_cy[id] = _content_cy(o)
			ys.append(o.position.y + float(_cy[id]))
		_show(id)
	if not ys.is_empty():
		var sum := 0.0
		for y in ys:
			sum += float(y)
		_water_y = roundf(sum / float(ys.size()))
	elif sg != null and not is_nan(float(sg.get("water_base"))):
		_water_y = float(sg.water_base) - 1.0
	if s["box"]:
		world.set_prop(box_id, "taken")
	rig = Rig.new()
	rig.name = "SalvageRig"
	rig.m = self
	if sg != null and sg.has_method("add_node"):
		sg.add_node(rig, 1)
	else:
		world.add_child(rig)
	_place_all()


## marker 在漂流物那个房间里的 x（不按「现在是哪个房间」读，免得读到别的房间去）
func _mloc(m: String, fallback: float) -> float:
	if sg != null and sg.has_method("has_marker") and sg.has_marker(m):
		return float(sg.marker_local(m))
	return KIT.local_x(world, m, fallback)


## 图里画着的东西（不透明像素）的中心离图顶多远：钩子落在这一行
static func _content_cy(o: Sprite2D) -> float:
	var h := float(o.texture.get_height()) if o.texture != null else 22.0
	var img: Image = o.texture.get_image() if o.texture != null else null
	if img == null:
		return h * 0.55
	var fw := img.get_width() / maxi(1, o.hframes)
	var top := -1
	var bot := -1
	for y in img.get_height():
		for x in fw:
			if img.get_pixel(x, y).a > 0.1:
				if top < 0:
					top = y
				bot = y
				break
	return (float(top + bot) * 0.5 + 0.5) if top >= 0 else h * 0.55


func _teardown() -> void:
	_lock_chen(false)
	if _mash:
		story.chen.set("auto_dir", 0.0)
	if rig != null and is_instance_valid(rig):
		rig.m = null
		rig.queue_free()


func _box_id() -> String:
	return str((step.get("box", {}) as Dictionary).get("id", "river_bank_box"))


func _obj(id: String) -> Sprite2D:
	var g := KIT.stage_of(world, id)
	return g.object(id) if g != null and g.has_method("object") else null


## 剧情放手（晨自己走、能抛）/ 收回来（播台词、走去浅滩）
func _release(on: bool) -> void:
	if on == _free:
		return
	if not on:
		_lock_chen(false)         # 先把方向键还给晨，再交给剧情
	_free = on
	if cast == "charge":
		cast = "idle"
	_btn_prev = _btn_down()       # 台词期间一直按着的键不算新的一按
	if auto_mode:
		return                    # 自动玩：剧情一直拿着，晨由 _auto_play / _mash_play 带着走
	if on:
		story.busy = false
		story.free_walk = false
		story.level.story_end()
		story.hotspots.active = false
	else:
		story.busy = true
		story.hotspots.active = false
		story.level.story_begin(false)


## 抛出去的那一下收完（剧情要接手的时候不留半截线）；看门狗保证一定收得完
func _settle() -> void:
	while cast in ["fly", "wait", "catch", "reel"] and _alive():
		await StoryState.frame(rig.get_tree())


func _alive() -> bool:
	return rig != null and is_instance_valid(rig) and rig.is_inside_tree() and not story.ended


## 等到阶段变了（river → shallows → done）；自动玩在这期间自己抛
func _until_phase_change() -> void:
	var was := str(s["phase"])
	if auto_mode and not _mash:
		await _auto_play(was)
	while _alive() and str(s["phase"]) == was:
		await StoryState.frame(rig.get_tree())
	await _settle()


## 第一次开始：箱子里的东西从上游一样一样漂进来（淡入 4 档），不是突然冒出来
func _drift_in() -> void:
	var i := 0
	for id in s["items"]:
		var o := _obj(id)
		if o == null:
			continue
		var e: Dictionary = s["items"][id]
		e["x"] = float(e["x"]) - DRIFT_IN - 24.0 * i
		o.modulate.a = 0.0
		var tw := o.create_tween()
		tw.tween_interval(0.35 * i)
		tw.tween_method(func(k: float): o.modulate.a = floorf(k * 4.0) / 4.0, 0.0, 1.0, 0.8)
		i += 1
	_fast_in = 2.4               # 漂进来那一段快一点（前 2.4 秒），不然要等很久才漂到原来的位置


# ----------------------------------------------------------------------- 每帧
func _tick(dt: float) -> void:
	_t += dt
	if sim == null:
		return
	if _free:
		_play_t += dt
	var k0 := sim.k
	if _fast_in > 0.0:
		_fast_in -= dt
		sim.k = k0 * (1.0 + DRIFT_IN / (SPEED_PX * 2.4))
	sim.tick(dt)
	sim.k = k0
	for ev in sim.pop_events():
		_on_event(ev)
	_place_all()
	if _mash and _free:
		_tick_mash(dt)
	if _free and (not auto_mode or _mash):
		var btn := _btn_down()
		if btn and not _btn_prev and cast == "idle":
			begin_charge()
		elif not btn and _btn_prev and cast == "charge":
			release_cast(reach_at(_hold))
		_btn_prev = btn
	_tick_cast(dt)
	_tick_fx(dt)
	if _free and not auto_mode:
		_idle_t += dt
		if _idle_t >= HINT_SEC:
			_idle_t = 0.0
			_hint()
	_save_t += dt
	if _save_t > 2.0:
		_save_t = 0.0
		story.mech_save(ID, s)


func _place_all() -> void:
	for id in s["items"]:
		if _lift.has(id):
			continue
		var o := _obj(id)
		if o == null:
			continue
		var e: Dictionary = s["items"][id]
		if str(e["st"]) == "got":
			continue
		var w := float(o.texture.get_width() / maxi(1, o.hframes)) if o.texture != null else 18.0
		var by: float = _base_y.get(id, o.position.y)
		var bob := 0.0
		if str(e["st"]) == "float" and not sim.heavy(id):
			bob = roundf(sin(_t * 2.2 + float(absi(hash(id)) % 7)) * 0.6)      # 轻的轻轻一上一下（一像素）
		o.position = Vector2(roundf(float(e["x"]) - w * 0.5), by + bob)
		_show(id)


func _show(id: String) -> void:
	var v := sim.vis(id) if sim != null else "float"
	if _shown.get(id, "") != v:
		_shown[id] = v
		world.set_prop(id, v)


## 东西在水里的那个点（房间坐标）：x = 中心，y = 图里画着的地方
func _spot(id: String) -> Vector2:
	var x := sim.x_of(id)
	var tid := id if id != "box" else _box_id()
	var o := _obj(tid)
	if o != null and _cy.has(id):
		return Vector2(x, o.position.y + float(_cy[id]))
	return Vector2(x, _water_y)


func _on_event(ev: Dictionary) -> void:
	var id := str(ev["id"])
	match str(ev["kind"]):
		"post":
			_sfx("wood_knock", -10.0, _pan(sim.post), 0.9)
		"sink":
			var p := _spot(id)
			for i in 5:
				_bubbles.append({"p": Vector2(p.x + randf_range(-5, 5), _water_y), "t": -i * 0.12})
			_ring(Vector2(p.x, _water_y), false)
			_sfx("water_hollow", -10.0, _pan(p.x))
			story.mech_save(ID, s)
			_niff("sank" if _said.has("sank_1") else "sank_1")
			_said["sank_1"] = true
		"shallow":
			_ring(Vector2(sim.x_of(id), _water_y), false)
			story.mech_save(ID, s)
		"net":
			var q := _spot(id)
			_splash(q, 5)
			_ring(q, true)
			_sfx("splash", -10.0, _pan(q.x))
			world.set_prop(id if id != "box" else _box_id(), "taken")
			_shown[id] = "taken"
			story.mech_save(ID, s)
		"rush", "phase":
			story.mech_save(ID, s)


# ----------------------------------------------------------------------- 抛钩
func _chen_local() -> Vector2:
	var c: Node2D = story.chen
	return sg.to_local_px(c.position) if sg != null and sg.has_method("to_local_px") else c.position


func _facing() -> int:
	var f = story.chen.get("facing")
	return int(f) if f != null else 1


func _hand() -> Vector2:
	return _chen_local() + Vector2(HAND.x * _facing(), HAND.y)


## 按下：晨转向离她最近的那样东西所在的那边（转一次，按住的时候不再转），站定，落点圈从脚边开始滑
func begin_charge() -> void:
	var cx := _chen_local().x
	var near := ""
	var nd := INF
	for h in sim.hookable():
		var d := absf(float(h["x"]) - cx)
		if d < nd:
			nd = d
			near = str(h["id"])
	if near != "":
		var dir := signi(int(roundf(sim.x_of(near) - cx)))
		if dir != 0 and dir != _facing():
			_turn(dir)
	_lock_chen(true)
	cast = "charge"
	_hold = 0.0
	_cast_t = 0.0
	_idle_t = 0.0


## 现在松手落点在哪（房间坐标）：晨前面 reach_at(按住多久) 那么远的水面
func _marker() -> Vector2:
	return Vector2(roundf(_chen_local().x + _facing() * reach_at(_hold)), _water_y)


func _btn_down() -> bool:
	if _mash:
		return _mash_btn
	if auto_mode:
		return false
	for n in ["_settings", "_bag"]:
		var pnl = story.level.get(n)
		if pnl is CanvasItem and (pnl as CanvasItem).visible:
			return false
	for k in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_Z]:
		if Input.is_key_pressed(k):
			return true
	return Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)


## 抛钩的按键不让关卡再拿去当「互动」（按键本身是 _tick 里轮询的，不靠这个）
func _swallow(e: InputEvent) -> void:
	if not _free or auto_mode:
		return
	var mine := (e is InputEventKey and (e as InputEventKey).keycode in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_Z]) \
		or (e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT)
	if mine:
		rig.get_viewport().set_input_as_handled()


## 松手：钩子飞到晨前面 d 像素的水面（落点在松手那一刻就定了，半路不拐弯）
func release_cast(d: float) -> void:
	_target = ""
	_gen += 1
	_land = Vector2(roundf(_chen_local().x + _facing() * clampf(d, REACH_MIN, REACH_MAX)), _water_y)
	_lock_chen(true)
	_from = _hand()
	_hook = _from
	_ct = 0.0
	_cast_t = 0.0
	_cdur = 0.26 + absf(_land.x - _from.x) / 620.0
	cast = "fly"
	_sag = 4.0
	_idle_t = 0.0
	_sfx("rope_throw", -8.0, _pan(_from.x), randf_range(0.95, 1.08))


func _turn(dir: int) -> void:
	var c: Node2D = story.chen
	if c.has_method("_set_facing"):
		c.call("_set_facing", dir)


## 抛的时候晨先站住（不会抛到一半转身），收完线还给玩家
func _lock_chen(on: bool) -> void:
	if on == _locked:
		return
	_locked = on
	var c: Node2D = story.chen
	if _mash:
		if on:
			c.set("auto_dir", 0.0)
		return
	if not auto_mode and _free:
		c.set("input_enabled", not on)


func _tick_cast(dt: float) -> void:
	if cast not in ["idle", "charge"]:
		_cast_t += dt
		if _cast_t > WATCHDOG:
			_reset_cast()
			return
	match cast:
		"charge":
			_hold += dt
		"fly":
			_ct = minf(_ct + dt, _cdur)
			var u := _ct / _cdur
			_hook = _arc(_from, _land, u)       # 抛物线，起点终点在松手那一刻定了
			if u >= 1.0:
				_landed()
		"wait":
			_ct += dt
			if _ct >= 0.45 * (0.5 if auto_mode else 1.0):
				cast = "reel"
				_ct = 0.0
				_cdur = 0.4
		"reel":
			_ct = minf(_ct + dt, _cdur)
			var u2 := _ct / _cdur
			var e2 := u2 * u2 * (3.0 - 2.0 * u2)
			_hook = _land.lerp(_hand(), e2) + Vector2(0, -sin(u2 * PI) * 4.0)
			_sag = lerpf(9.0, 2.0, e2)
			if u2 >= 1.0:
				_end_cast()
	if cast == "idle" or cast == "charge":
		_hook = _hand()


func _end_cast() -> void:
	cast = "idle"
	_target = ""
	_cast_t = 0.0
	_lock_chen(false)


## 看门狗：抛钩卡在半路（协程没走完、物件没了……）就收回来，钩到一半的东西照规则算
func _reset_cast() -> void:
	_gen += 1
	for id in _lift.keys():
		if not sim.can_hook(str(id)):
			world.set_prop(str(id) if str(id) != "box" else _box_id(), "taken")
			_shown[id] = "taken"
	_lift.clear()
	_end_cast()
	print("MECH %s watchdog reset" % ID)


## 抛物线：手 → 落点，压得低低的（最高点只比两头高一点）
func _arc(a: Vector2, b: Vector2, u: float) -> Vector2:
	var apex := 6.0 + absf(b.x - a.x) * 0.07
	var p := a.lerp(b, u)
	return Vector2(p.x, p.y - apex * 4.0 * u * (1.0 - u))


func _landed() -> void:
	_hook = _land
	_ring(_land, true)
	_splash(_land, 4)
	_sfx("water_drop", -6.0, _pan(_land.x), randf_range(0.9, 1.1))
	var id := sim.catch_at(_land.x, CATCH_HELP if _misses >= MISS_HELP else CATCH)
	if id == "":
		_misses += 1
		cast = "wait"
		_ct = 0.0
		_sag = 9.0
	else:
		_misses = 0
		_catch(id)


## 钩住了：线绷紧拽两下 → 出水（哗）→ 顺着弧线飞回晨手里 → 收进去（镜头轻轻一顿）。
## 规则上一钩住就算到手（sim.take），后面只是演；看门狗重置或剧本结束了就不演了
func _catch(id: String) -> void:
	cast = "catch"
	var g := _gen
	_lift[id] = true
	sim.take(id)
	story.mech_save(ID, s)
	var tid := id if id != "box" else _box_id()
	var o := _obj(tid)
	var face := _facing()
	_sag = 1.0
	# 钩子就在落点（东西旁边），线一绷：拽两下，每下把东西往钩子那边拉一点（缓起缓停），钩子跟着往回一顿
	var gap := sim.x_of(id) - _land.x
	for i in 2:
		_sfx("tick", -14.0, _pan(_land.x), 1.4)
		var pull := -gap * 0.5
		await _tug(o, pull, 0.14)
		if g != _gen or not _alive():
			return
		gap += pull
		_hook = _land + Vector2(-face * 1.0, -1)
		await _wait(0.1)
		if g != _gen or not _alive():
			return
		_hook = _land
	var start := Vector2(_land.x, _spot(id).y)
	_splash(start, 8)
	_ring(start, true)
	_sfx("splash", -6.0, _pan(start.x))
	_cam_nudge(face)
	var off := Vector2.ZERO
	if o != null:
		off = Vector2(start.x - o.position.x, start.y - o.position.y)
	var t := 0.0
	var dur := 0.5
	while t < dur:
		await StoryState.frame(rig.get_tree())
		if g != _gen or not _alive():
			return
		t += rig.get_process_delta_time()
		var u := clampf(t / dur, 0.0, 1.0)
		var e := 1.0 - (1.0 - u) * (1.0 - u)
		var b := _hand()
		var p := Vector2(lerpf(start.x, b.x, e), lerpf(start.y, b.y, e) - 22.0 * sin(u * PI))
		_hook = p
		_sag = 2.0
		if o != null:
			o.position = (p - off).round()
	_sfx("pickup", -8.0)
	world.set_prop(tid, "taken")
	_shown[id] = "taken"
	_lift.erase(id)
	_end_cast()
	if id in key_ids(step):
		_niff("got_key")


## 拽一下：东西沿水面平平地挪 dx（缓起缓停）
func _tug(o: Sprite2D, dx: float, sec: float) -> void:
	if o == null or not _alive():
		await _wait(sec)
		return
	var x0 := o.position.x
	var t := 0.0
	while t < sec and _alive():
		await StoryState.frame(rig.get_tree())
		t += rig.get_process_delta_time()
		var u := clampf(t / sec, 0.0, 1.0)
		o.position.x = roundf(x0 + dx * u * u * (3.0 - 2.0 * u))


func _wait(sec: float) -> void:
	await rig.get_tree().create_timer(sec * (0.6 if auto_mode else 1.0), false).timeout


func _cam_nudge(face: int) -> void:
	var cam: Camera2D = story.level.get("cam")
	if cam == null or story.ff:
		return
	var tw := cam.create_tween()
	tw.tween_property(cam, "offset", Vector2(-face * 2.0, 1.0), 0.07).set_trans(Tween.TRANS_SINE)
	tw.tween_property(cam, "offset", Vector2.ZERO, 0.28).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)


# ----------------------------------------------------------------------- 水纹 / 水花 / 气泡
func _ring(p: Vector2, big: bool) -> void:
	_rings.append({"p": p.round(), "t": 0.0, "big": big})


func _splash(p: Vector2, n: int) -> void:
	for i in n:
		_drops.append({"p": p + Vector2(randf_range(-2, 2), -1), "y0": p.y, "v": Vector2(randf_range(-28, 28), randf_range(-70, -38)), "t": 0.0})


func _tick_fx(dt: float) -> void:
	for r in _rings.duplicate():
		r["t"] = float(r["t"]) + dt
		if float(r["t"]) > (1.1 if r["big"] else 0.8):
			_rings.erase(r)
	for dr in _drops.duplicate():
		dr["t"] = float(dr["t"]) + dt
		dr["v"] = (dr["v"] as Vector2) + Vector2(0, 260.0 * dt)
		dr["p"] = (dr["p"] as Vector2) + (dr["v"] as Vector2) * dt
		if (dr["p"] as Vector2).y > float(dr["y0"]) + 1.0 or float(dr["t"]) > 1.5:
			_drops.erase(dr)
	_bub_t -= dt
	if _bub_t <= 0.0 and sim != null:
		_bub_t = 0.5
		for id in s["items"]:
			if _shown.get(id, "") == "sink2" and randf() < 0.7:
				var p := _spot(id)
				_bubbles.append({"p": Vector2(p.x + randf_range(-4, 4), p.y), "t": 0.0})
	for b in _bubbles.duplicate():
		b["t"] = float(b["t"]) + dt
		if float(b["t"]) > 0.7:
			_bubbles.erase(b)


# ----------------------------------------------------------------------- 画
func _draw_rig(c: CanvasItem) -> void:
	for r in _rings:
		var big: bool = r["big"]
		var life := 1.1 if big else 0.8
		var u := float(r["t"]) / life
		var e := 1.0 - (1.0 - u) * (1.0 - u)
		var rx := 2.0 + (14.0 if big else 9.0) * e
		var ry := 1.0 + 1.5 * e
		var a := ceilf((1.0 - u) * 3.0) / 3.0
		_ellipse_px(c, r["p"], rx, ry, Color(RING_C, a))
	for dr in _drops:
		c.draw_rect(Rect2((dr["p"] as Vector2).round(), Vector2.ONE), DROP_C)
	for b in _bubbles:
		var t := float(b["t"])
		if t < 0.0:
			continue
		var p: Vector2 = (b["p"] as Vector2) + Vector2(roundf(sin(t * 9.0) * 0.6), -roundf(t * 7.0))
		c.draw_rect(Rect2(p.round(), Vector2.ONE), Color(DROP_C, 1.0 if t < 0.45 else 0.5))
	if not _free and cast == "idle":
		return
	var hand := _hand()
	if cast == "charge":
		# 落点：水面上一个实心像素的扁圈 + 一个一上一下的小浮标（松手钩子就落在这）
		var m := _marker()
		_ellipse_px(c, m, 5.0, 1.5, AIM_C)
		var bob := -1.0 if fmod(_t, 0.6) < 0.3 else 0.0
		c.draw_rect(Rect2(m + Vector2(-1, -3 + bob), Vector2(2, 2)), Color("#c9473a"))
		c.draw_rect(Rect2(m + Vector2(-1, -1 + bob), Vector2(2, 1)), Color("#e2ece6"))
	if cast in ["fly", "wait", "reel", "catch"]:
		# 线：手 → 钩子，二次贝塞尔，中间往下坠一点（光滑的一道，连续的像素）
		var mid := (hand + _hook) * 0.5 + Vector2(0, _sag)
		var pts2: Array = []
		for i in 21:
			var u3 := float(i) / 20.0
			pts2.append(hand.lerp(mid, u3).lerp(mid.lerp(_hook, u3), u3))
		_poly_px(c, pts2, LINE_C)
		var hp := _hook.round()
		c.draw_rect(Rect2(hp + Vector2(-1, -1), Vector2(2, 2)), Color("#8a959a"))
		c.draw_rect(Rect2(hp + Vector2(-1, -1), Vector2(1, 1)), Color("#d6e4ea"))


## 连续的像素线：相邻两点之间补满（8 邻接，不断、不虚）
func _poly_px(c: CanvasItem, pts: Array, col: Color) -> void:
	var seen := {}
	var prev := Vector2i((pts[0] as Vector2).round())
	for i in range(1, pts.size()):
		var cur := Vector2i((pts[i] as Vector2).round())
		var dx := absi(cur.x - prev.x)
		var dy := -absi(cur.y - prev.y)
		var sx := 1 if prev.x < cur.x else -1
		var sy := 1 if prev.y < cur.y else -1
		var err := dx + dy
		var p := prev
		while true:
			if not seen.has(p):
				seen[p] = true
				c.draw_rect(Rect2(Vector2(p), Vector2.ONE), col)
			if p == cur:
				break
			var e2 := 2 * err
			if e2 >= dy:
				err += dy
				p.x += sx
			if e2 <= dx:
				err += dx
				p.y += sy
		prev = cur


## 扁椭圆的一圈（连续的像素）
func _ellipse_px(c: CanvasItem, ctr: Vector2, rx: float, ry: float, col: Color) -> void:
	var pts: Array = []
	var n := maxi(12, int(rx * 3.0))
	for i in n + 1:
		var a := TAU * float(i) / float(n)
		pts.append(ctr + Vector2(cos(a) * rx, sin(a) * ry))
	_poly_px(c, pts, col)


# ----------------------------------------------------------------------- 泥芙 / 声音
## 实时冒一句：lines[key] 里的 say 用 murmur（不挡操作），anim / face / sfx 照播；最快 SAY_GAP 秒一句
func _niff(key: String) -> void:
	if story.ff or not KIT.has_lines(step, key) or _t - _said_t < SAY_GAP:
		return
	_said_t = _t
	var arr: Array = (step.get("lines", {}) as Dictionary).get(key, [])
	var rest: Array = []
	for st in arr:
		if not st is Dictionary:
			continue
		if st.has("say"):
			_murmur(st)
		elif str(st.get("do", "")) in ["anim", "face", "sfx"]:
			rest.append(st)
	if not rest.is_empty():
		story.run_steps(rest)


func _murmur(st: Dictionary) -> void:
	var who := str(st["say"])
	var d = story.get("dlg")
	if d == null or not d.has_method("murmur"):
		return
	var nm := ""
	var sp = story.speakers.get(who, null)
	if sp is Dictionary:
		nm = I18n.pick(sp)
	var col: Color = story.NAME_COLORS.get(who, UITheme.TEXT)
	d.murmur(nm, col, I18n.pick(st), Callable(story, "_anchor").bind(who), bool(st.get("added", false)) and bool(story.mark_added), who)


## 站着半天没抛：泥芙看一眼该先捞的那样，冒一句（会沉的 hint_sink，别的 hint）
func _hint() -> void:
	var ok := best(step, s)
	if ok == "":
		return
	var sink: bool = s["phase"] == "river" and ok != "box" and sim.heavy(ok)
	var x := sim.x_of(ok)
	if not is_nan(x) and sg != null:
		story.run_steps([{"do": "face", "who": "niff", "to": sg.to_world(Vector2(x, 0)).x}])
	_niff("hint_sink" if sink else "hint")


func _sfx(name: String, db := 0.0, pan := 0.0, pitch := 1.0) -> void:
	if story.ff:
		return
	story.run_steps([{"do": "sfx", "name": name, "db": db, "pan": pan, "pitch": pitch}])


## 房间 x → 左右声道（-1..1，按镜头）
func _pan(lx: float) -> float:
	if is_nan(lx) or sg == null:
		return 0.0
	var wx: float = sg.to_world(Vector2(lx, 0)).x
	return clampf((wx - story.level.cam_left().x - 240.0) / 240.0, -1.0, 1.0)


# ----------------------------------------------------------------------- 自动玩：自己走到够得着的地方、自己抛
func _auto_play(phase: String) -> void:
	var full: bool = story.auto == "full"
	while _alive() and str(s["phase"]) == phase:
		var hs := sim.hookable()
		if hs.is_empty():
			await StoryState.frame(rig.get_tree())
			continue
		var h: Dictionary = hs[0]
		for hh in hs:
			if float(hh["x"]) > float(h["x"]):
				h = hh                          # 下游最远的那样先（快到浅滩的）
		var stand: float = float(h["x"]) + 70.0
		var wx: float = sg.to_world(Vector2(stand, 0)).x if sg != null else stand
		await story.run_steps([{"do": "walk", "who": "chen", "to": wx}])
		await story.run_steps([{"do": "face", "who": "chen", "to": wx - 40.0}])
		if not _alive():
			return
		var miss := full and not tried.has("miss")
		tried["miss"] = true
		await _auto_cast(str(h["id"]), miss)
		await _settle()


## 自动玩：按住，等落点圈滑到「它飞过去那会儿会漂到的地方」再松手（miss = 故意松早一点，演一次没钩到）
func _auto_cast(id: String, miss: bool) -> void:
	begin_charge()
	var dir := signi(int(roundf(sim.x_of(id) - _chen_local().x)))
	if dir != 0 and dir != _facing():
		_turn(dir)                             # 自动玩要的是这一样（不一定是最近的那样）
	while _alive() and cast == "charge":
		if not sim.can_hook(id):
			cast = "idle"
			_lock_chen(false)
			return
		var v := sim.speed(id) if s["phase"] == "river" else 0.0
		var want := absf(sim.x_of(id) + v * 0.4 - _chen_local().x) + (40.0 if miss else 0.0)
		want = clampf(want, REACH_MIN, REACH_MAX)
		if absf(reach_at(_hold) - want) <= 3.0:
			release_cast(reach_at(_hold))
			return
		if _hold > SWEEP_SEC * 4.0:
			release_cast(want)                 # 保险：怎么都对不上（不该发生）就直接抛
			return
		await StoryState.frame(rig.get_tree())


## --salvage_mash：乱按的玩家（随机走一会儿、随机按住一会儿再松手），只走同一条按键路径（_btn_down / release_cast）
func _tick_mash(dt: float) -> void:
	var c: Node2D = story.chen
	_mash_walk -= dt
	if _locked:
		c.set("auto_dir", 0.0)
	elif _mash_walk <= 0.0:
		_mash_walk = _rng.randf_range(0.3, 1.6)
		var pick: float = [-1.0, 0.0, 1.0, 1.0, -1.0, 0.0][_rng.randi() % 6]
		c.set("auto_dir", pick)
	var x := _chen_local().x
	if not _locked and x < sim.x0 - 250.0:
		c.set("auto_dir", 1.0)
	elif not _locked and x > sim.x1 + 250.0:
		c.set("auto_dir", -1.0)
	_mash_t -= dt
	if _mash_t <= 0.0:
		_mash_btn = not _mash_btn
		_mash_t = _rng.randf_range(0.05, 1.3) if _mash_btn else _rng.randf_range(0.1, 0.9)


# ----------------------------------------------------------------------- 检查
func check(story: Node, st: Dictionary) -> Array:
	var out: Array = []
	if key_ids(st).is_empty():
		out.append("items 里没有关键物品（key: true）")
	for d in st.get("items", []):
		if not d.has("id") or not d.has("label"):
			out.append("物品要有 id / label：%s" % str(d))
	# 一下都不抛也一定能结束（兜底），关键物品一定到手
	var t := fresh(st)
	var sm := Sim.new(st, t, 0.0, 430.0, NAN, 100.0)
	for i in 2000:
		sm.tick(0.1)
		if finished(t):
			break
	if not finished(t):
		out.append("一下都不抛的话 200 秒还没结束")
	for kid in key_ids(st):
		if str(t["items"][kid]["st"]) != "got":
			out.append("关键物品 %s 没到手" % kid)
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
