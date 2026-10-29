extends RefCounted
## 开头捡东西提速（作者 10-29 拍板「三条都改」）。story_runner.gd 建一个（quick），在几个地方调它：
##   give 数组：{"do": "give", "items": [..], "toast": "luggage_items"?}——全部同时进背包，图标错开 0.07 秒一起飞，
##     提示合成一条（I18n key：toast 写了用它，默认 got_items，都是「…%d 件」）。总共约 1 秒。
##   走过去就捡：hotspot 写 "trigger": "enter" + "pickup": true——晨走进范围（range）就捡，不停下、不锁移动、不进过场：
##     这段 scene 里只认「快步骤」（give / flag / if / goto / sfx / anim / wait / count / prop / say 带 bark），
##     give 的飞图标不等、bark 台词进头顶小气泡、wait 跳过、anim 只在晨站着时播；
##     碰到别的步骤（正经对话、旁白、选项……）就从那一步交给正常的 play()（比如四样材料齐了接 fuel_full 的对话）。
##   跳节拍（ff）时照常 play()，结果一样。

var r: Node                           # story_runner.gd

const QUICK_DO := ["give", "flag", "if", "goto", "sfx", "anim", "wait", "count", "prop"]


func _init(runner: Node) -> void:
	r = runner


func is_quick(h: Dictionary) -> bool:
	return bool(h.get("pickup", false)) and r.hotspots.is_enter(h)


## give 的数组形式
func give_many(st: Dictionary) -> void:
	var got: Array = []
	for v in st.get("items", []):
		var id := str(v)
		if r._wood_mode and Inventory.has(id):
			continue
		if not Inventory.defined(id):
			Inventory.register_fallback({"id": id, "name": {"zh": id, "en": id}, "rarity": "common", "burn": 0, "personal": true,
				"desc": {"zh": "", "en": ""}})
		Inventory.add(id)
		got.append(id)
	r.level.on_inventory_changed()
	if r.ff or got.is_empty():
		return
	var key := str(st.get("toast", "got_items"))
	r.dlg.toast(Inventory.icon(str(got[0])), I18n.t(key) % got.size())
	var from: Vector2 = r.chen.position + Vector2(0, -36) - r.level.cam_left()
	var n := got.size()
	for i in n:
		r._fly_to_bag(Inventory.icon(str(got[i])), from + Vector2(roundf((i - (n - 1) / 2.0) * 7.0), 0))   # 不等，一起飞
		if i < n - 1:
			await r.get_tree().create_timer(0.07).timeout
	await r.get_tree().create_timer(0.75).timeout     # 最后一件落进背包


## 走过去就捡
func pickup(p: Dictionary) -> void:
	var h: Dictionary = p["h"]
	var id := str(h.get("id", ""))
	if h.get("once", false):
		StoryState.mark_used(id)
	r.hotspots_used += 1
	var scene := str(h.get("scene", ""))
	if r.ff:
		await r.play(scene, false)
		return
	var cur := scene
	var hops := 0
	while cur != "" and hops < 50 and not r.ended:
		hops += 1
		if not r.scenes.has(cur):
			break
		var steps: Array = r.scenes[cur]
		if not steps.is_empty() and steps[0] is Dictionary and not _quick_ok(steps[0]):
			while r.busy and not r.ended:
				await r.get_tree().process_frame
			if not r.ended:
				await r.play(cur, true)       # 整段都是正经剧情（比如 fuel_full 的对话）：直接交出去
			return
		r._on_scene(cur)
		var next := ""
		for i in steps.size():
			var st = steps[i]
			if not st is Dictionary:
				continue
			if not _quick_ok(st):
				# 交给正常播放（等别的剧情播完）；play 自己会再记一次这个 scene，这里先撤掉，免得统计里算两遍
				var played: Dictionary = r.played
				played[cur] = int(played.get(cur, 1)) - 1
				if int(played[cur]) <= 0:
					played.erase(cur)
				r.played_order.pop_back()
				while r.busy and not r.ended:
					await r.get_tree().process_frame
				if not r.ended:
					await r.play(cur, true, i)
				return
			var g := _do(st)
			if g != "":
				next = g
				break
		cur = next


func _quick_ok(st: Dictionary) -> bool:
	if st.has("say"):
		return bool(st.get("bark", false))
	if st.has("narr"):
		return false
	return str(st.get("do", "")) in QUICK_DO


## 一个快步骤；返回要跳去的 scene（goto / if），"" = 接着
func _do(st: Dictionary) -> String:
	if st.has("say"):
		r._say(st)                    # bark：只是排进小气泡，不等
		return ""
	var d := str(st.get("do", ""))
	match d:
		"give":
			if st.has("items"):
				call("give_many", st)     # 协程，不等
			else:
				r._give(str(st.get("item", "")))
		"flag":
			if st.has("set"):
				StoryState.set_flag(str(st["set"]))
			if st.has("clear"):
				StoryState.clear_flag(str(st["clear"]))
		"if":
			var f := str(st.get("flag", ""))
			var yes := not StoryState.has(f.substr(1)) if f.begins_with("!") else StoryState.has(f)
			return str(st.get("then" if yes else "else", ""))
		"goto":
			return str(st.get("scene", ""))
		"sfx":
			r._sfx(st)
		"anim":
			if r.chen._vel <= 0.0 or str(st.get("who", "chen")) != "chen":
				r._anim(st)
		"count":
			var c := 0
			for f in st.get("flags", []):
				if StoryState.has(str(f)):
					c += 1
			if c >= int(st.get("at_least", 1)) and st.has("set"):
				StoryState.set_flag(str(st["set"]))
		"prop":
			r.world.set_prop(str(st.get("id", "")), str(st.get("state", "")))
	return ""
