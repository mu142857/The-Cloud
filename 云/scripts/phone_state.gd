extends RefCounted
## 通讯器的状态（静态，跨场景都在；StoryState.reset / to_dict / from_dict 顺带管它，存档 / 跳节拍 / F8 一套）。
## 约定见 docs/phone_and_cockpit_contract.md「通讯器（phone）」。界面在 phone_ui.gd，这里只有数据。
##
## data/phone.json（只读，剧本 agent 维护）：{"contacts": {id: {name{zh,en}, hidden?, history: [{from, zh, en, date?, added?}]}}}
##   没有这个文件 = 没有联系人（不崩）。联系人顺序 = 文件里的顺序。
## 存的东西（state）：每个联系人 {shown, name?, unread, input?, extra: [追加的消息]}；fired = 触发过的 phone_msg id。
##   显示的聊天记录 = phone.json 的 history + extra（剧本 agent 改了初始记录的字，旧存档也跟着新字）。
##   input = 输入栏里的字：{zh, en, kind: "reply"|"draft", flag?, msg?}。「稍后看」的回复、「暂时不发」的草稿都留在这。
## 失联的朋友（id = friend，或 phone.json 里写 "no_unread": true）永远没有未读。
## 注意：别的脚本读写一律走下面的函数（静态变量从别的类直接读 / 按下标赋值，Godot 4.7 会把栈写坏、崩）。

const DATA := "res://data/phone.json"
const ITEM_ID := "communicator"
const ICON := "res://art/forest_story/icon_communicator.png"
const CHEN := "chen"

static var base := {}                 # phone.json 的 contacts（只读）
static var order: Array[String] = []  # 联系人顺序
static var state := {}                # id → {shown, name?, unread, input?, extra}
static var fired := {}                # phone_msg id → true
static var loaded := false
static var changed := 0               # 每改一次加一（界面判断要不要重排）


static func load_base() -> void:
	base = {}
	order.clear()
	loaded = FileAccess.file_exists(DATA)
	if loaded:
		var d = JSON.parse_string(FileAccess.get_file_as_string(DATA))
		if d is Dictionary and d.get("contacts", null) is Dictionary:
			base = d["contacts"]
		else:
			push_warning("通讯器：phone.json 格式不对（要 {\"contacts\": {…}}），当没有联系人")
	for id in base:
		order.append(str(id))
	# 物品表里还没有通讯器时先顶一个（items.json 里有就以它为准）
	Inventory.register_fallback({"id": ITEM_ID, "name": {"en": "Communicator", "zh": "通讯器"}, "rarity": "common", "burn": 0,
		"icon": ICON, "personal": true, "category": "quest", "added": true,
		"desc": {"en": "An old communicator. It's been in the bag the whole way.", "zh": "一直带在行李里的旧通讯器。"}})


static func reset() -> void:
	load_base()
	state = {}
	fired = {}
	changed += 1
	for id in order:
		var b: Dictionary = base[id] if base[id] is Dictionary else {}
		state[id] = {"shown": not bool(b.get("hidden", false)), "unread": false, "extra": []}


static func _st(id: String) -> Dictionary:
	if not state.has(id):
		state[id] = {"shown": false, "unread": false, "extra": []}
		if not order.has(id):
			order.append(id)
	return state[id]


# ----------------------------------------------------------------------- 读
## 别的脚本读这里的静态变量一律走函数（Godot 4.7 从别的脚本直接读静态 int / 字典会读坏、崩）
static func version() -> int:
	return changed


static func contact_order() -> Array[String]:
	return order.duplicate()


static func base_contacts() -> Dictionary:
	return base


static func has_data() -> bool:
	return loaded


static func has_contact(id: String) -> bool:
	return state.has(id) or base.has(id)


static func visible_ids() -> Array[String]:
	var out: Array[String] = []
	for id in order:
		if state.has(id) and bool(state[id].get("shown", false)):
			out.append(id)
	return out


static func name_of(id: String):
	var s: Dictionary = state.get(id, {})
	if s.has("name"):
		return s["name"]
	var b = base.get(id, {})
	if b is Dictionary and b.has("name"):
		return b["name"]
	return {"zh": id, "en": id}


static func history(id: String) -> Array:
	var out: Array = []
	var b = base.get(id, {})
	if b is Dictionary:
		for m in b.get("history", []):
			if m is Dictionary:
				out.append(m)
	var s: Dictionary = state.get(id, {})
	out.append_array(s.get("extra", []))
	return out


static func unread(id: String) -> bool:
	return bool((state.get(id, {}) as Dictionary).get("unread", false))


static func any_unread() -> bool:
	for id in visible_ids():
		if unread(id):
			return true
	return false


static func input_of(id: String) -> Dictionary:
	return (state.get(id, {}) as Dictionary).get("input", {})


static func is_fired(msg_id: String) -> bool:
	return fired.has(msg_id)


## 失联的朋友：永远没有未读
static func never_unread(id: String) -> bool:
	var b = base.get(id, {})
	return id == "friend" or (b is Dictionary and bool(b.get("no_unread", false)))


# ----------------------------------------------------------------------- 改
static func add_contact(id: String, nm) -> void:
	var s := _st(id)
	s["shown"] = true
	if nm is Dictionary and (str(nm.get("zh", "")) != "" or str(nm.get("en", "")) != ""):
		s["name"] = {"zh": str(nm.get("zh", "")), "en": str(nm.get("en", ""))}
	changed += 1


## 收到一条（phone_msg）：追加、标未读、回复先放进输入栏（「稍后看」以后还能回）
## 正文里有换行 = 几条连续的气泡（「隔了一会儿又来一条」）：zh / en 各自按 \n 拆，按顺序对齐（某种语言少几段就空着，显示时回落另一种）
static func split(text: Dictionary) -> Array:
	var zh := str(text.get("zh", "")).split("\n", false)
	var en := str(text.get("en", "")).split("\n", false)
	var out: Array = []
	for i in maxi(maxi(zh.size(), en.size()), 1):
		var m := {"zh": zh[i].strip_edges() if i < zh.size() else "", "en": en[i].strip_edges() if i < en.size() else ""}
		if text.has("date"):
			m["date"] = str(text["date"])
		out.append(m)
	return out


## 收到一条（phone_msg）：追加（有换行就拆成几条）、标未读、回复先放进输入栏（「稍后看」以后还能回）。返回追加了几条
static func receive(msg_id: String, from: String, text: Dictionary, reply, added := false) -> int:
	fired[msg_id] = true
	var s := _st(from)
	s["shown"] = true
	var parts := split(text)
	for m in parts:
		m["from"] = from
		m["msg"] = msg_id
		if added:
			m["added"] = true
		(s["extra"] as Array).append(m)
	if not never_unread(from):
		s["unread"] = true
	if reply is Dictionary and (str(reply.get("zh", "")) != "" or str(reply.get("en", "")) != ""):
		s["input"] = {"zh": str(reply.get("zh", "")), "en": str(reply.get("en", "")), "kind": "reply", "msg": msg_id,
			"added": bool(reply.get("added", false))}
	changed += 1
	return parts.size()


## 晨发一条（phone_send、回复、草稿发出去；有换行同样拆成几条）。返回追加了几条
static func send(to: String, text: Dictionary, added := false) -> int:
	var s := _st(to)
	s["shown"] = true
	var parts := split(text)
	for m in parts:
		m["from"] = CHEN
		if added:
			m["added"] = true
		(s["extra"] as Array).append(m)
	changed += 1
	return parts.size()


## 把输入栏里的字发出去（回复 / 草稿）；草稿带 flag 就设上。返回有没有发
static func send_input(id: String) -> bool:
	var inp := input_of(id)
	if inp.is_empty():
		return false
	send(id, inp, bool(inp.get("added", false)))
	if str(inp.get("flag", "")) != "":
		StoryState.set_flag(str(inp["flag"]))
	clear_input(id)
	mark_read(id)
	return true


static func set_draft(to: String, text: Dictionary, flag: String, added := false) -> void:
	var s := _st(to)
	s["shown"] = true
	s["input"] = {"zh": str(text.get("zh", "")), "en": str(text.get("en", "")), "kind": "draft", "flag": flag, "added": added}
	changed += 1


static func clear_input(id: String) -> void:
	var s := _st(id)
	s.erase("input")
	changed += 1


static func mark_read(id: String) -> void:
	if state.has(id) and bool(state[id].get("unread", false)):
		var s: Dictionary = state[id]
		s["unread"] = false
		changed += 1


# ----------------------------------------------------------------------- 存档
static func to_dict() -> Dictionary:
	return {"state": state.duplicate(true), "fired": fired.keys()}


static func from_dict(d: Dictionary) -> void:
	reset()
	var st = d.get("state", {})
	if st is Dictionary:
		for id in st:
			if st[id] is Dictionary:
				state[str(id)] = (st[id] as Dictionary).duplicate(true)
				if not order.has(str(id)):
					order.append(str(id))
	for f in d.get("fired", []):
		fired[str(f)] = true
	changed += 1
