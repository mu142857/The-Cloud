class_name StoryState
## 剧情进度：flags、日记、场景物件的状态、用过的一次性 hotspot。全放在这一个地方，以后做存档就存 to_dict() 一份。
## 和 Inventory 一样是静态的（跨场景都在）；第一关 _ready 里 reset()（现在没有存档，每次进来都是新游戏）。
##   StoryState.set_flag("deer_met")     StoryState.has("deer_met")
##   StoryState.journal                  [{zh, en}, …] 按时间
##   StoryState.set_prop("log", "moved")  场景物件状态（story_world.gd 读）；StoryState.mark_used(id) 一次性 hotspot 用掉了
## 注意：别在别的脚本里写 StoryState.props[id] = …（给另一个类的静态字典按下标赋值，Godot 4.7 会把栈写坏、过一会儿崩），用这里的函数。
## 引擎自己会设的 flag：crashed（晨爬起来）、got_wood（捡到发光木头）、fuel_full（燃烧值到 launch_burn）。

static var flags := {}
static var flag_order: Array[String] = []      # 按设的先后（--beat 列表、统计用）
static var journal: Array = []
static var props := {}
static var used := {}                         # once 的 hotspot 用掉了：id → true
static var changed := 0                       # 每设一个新 flag 加一（自动玩判断「有进展」用）


static func reset() -> void:
	flags.clear()
	flag_order.clear()
	journal.clear()
	props.clear()
	used.clear()
	changed = 0


static func has(f: String) -> bool:
	return flags.has(f)


static func set_flag(f: String) -> bool:
	## 返回 true = 这是新设的
	if f == "" or flags.has(f):
		return false
	flags[f] = true
	flag_order.append(f)
	changed += 1
	return true


## 进展计数（别的脚本读静态 int 也走函数，见上面的注意）
static func progress() -> int:
	return changed


static func set_prop(id: String, state: String) -> void:
	props[id] = state


static func mark_used(id: String) -> void:
	used[id] = true


## 日记加一条：{zh, en, tag?, struck?}
static func add_journal(e: Dictionary) -> void:
	journal.append(e)


## 日记里含这段文字（任一语言）的条目划掉；返回划掉了几条
static func strike(text: String) -> int:
	var n := 0
	for e in journal:
		var d: Dictionary = e
		if text != "" and (str(d.get("zh", "")).contains(text) or str(d.get("en", "")).contains(text)) and not d.get("struck", false):
			d["struck"] = true
			n += 1
	return n


## 日记里含这段文字的条目加下划线（之后被划掉的话删除线盖在上面）
static func mark(text: String) -> int:
	var n := 0
	for e in journal:
		var d: Dictionary = e
		if text != "" and (str(d.get("zh", "")).contains(text) or str(d.get("en", "")).contains(text)):
			d["marked"] = true
			n += 1
	return n


static func clear_flag(f: String) -> void:
	flags.erase(f)


static func all_of(list) -> bool:
	if list is String:
		return has(list)
	for f in list:
		if not has(str(f)):
			return false
	return true


static func none_of(list) -> bool:
	if list is String:
		return not has(list)
	for f in list:
		if has(str(f)):
			return false
	return true


static func to_dict() -> Dictionary:
	return {"flags": flag_order.duplicate(), "journal": journal.duplicate(true), "props": props.duplicate(),
		"used": used.keys(), "owned": Inventory.owned.duplicate()}


static func from_dict(d: Dictionary) -> void:
	reset()
	for f in d.get("flags", []):
		set_flag(str(f))
	journal = (d.get("journal", []) as Array).duplicate(true)
	props = (d.get("props", {}) as Dictionary).duplicate()
	for u in d.get("used", []):
		used[str(u)] = true
	Inventory.owned.clear()
	for id in d.get("owned", []):
		Inventory.add(str(id))
