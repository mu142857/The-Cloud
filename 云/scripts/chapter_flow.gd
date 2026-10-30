extends RefCounted
## 章节之间怎么接（level_forest.gd 用；章节都在 scenes/level_forest.tscn 这一个关卡里播，换章 = 带着状态重新载入本场景）。
##   forest   木星森林：开场 → 坠毁 → 修船 → 起飞（data/story_forest.json）。剧本 end_chapter：照旧播起飞，黑屏以后接 flight1。
##   flight1  第一次飞行，驾驶舱（data/story_flight1.json，入口 start_flight1）。end_chapter：往前一冲（cockpit_dash）、淡到黑、
##            「第一章 完」卡（end_card：go() 在黑屏上淡入、停一会儿，载入下一章以后再淡掉），接 river。
##   river    河流篇「妮芙的三分钟」（data/story_river.json，入口 start_river，房间 river_bank；多房间，见 docs/river_rooms_contract.md）。
##            end_chapter：驾驶舱里写完日记，「未完待续」卡（终章接上以后改 next = final）。
## 带过去的东西：StoryState.to_dict()（flags、日记、物件状态、用过的点、背包）存进 Engine 的 meta CARRY_META，
##   新章节 _ready 里 from_dict 恢复；这份一直留着（F8「重开本章」/ 跳节拍从同一个起点重来），回标题时清掉。
## 直接进 flight1（--chapter=flight1、F8「跳到飞行一」）又没有带过来的状态：用 SEED（森林自动玩到起飞时的 flags 和背包）。
## 直接进 river：SEED + SEED_FLIGHT1（flight1 自动玩完：放了蓝色石头）；--river_seed=card / F8 切成「烧了通勤卡」那版（原文 119 摸衣袋两个分支）。

const CHAPTER_META := "the_cloud_chapter"
const CARRY_META := "the_cloud_carry"
const RIVER_SEED_META := "the_cloud_river_seed"        # F8：直接进河流篇时用哪个 SEED（"" = 烧了蓝色石头 / "card" = 烧了通勤卡）
const PICK_META := "the_cloud_chapter_pick"            # F8 跳节拍换了章：CHAPTER_META 比命令行 --chapter= 优先（不然带着 --chapter 跑就跳不过去）

const CHAPTERS := {
	"forest": {"story": "res://data/story_forest.json", "next": "flight1"},
	"flight1": {"story": "res://data/story_flight1.json", "start": "start_flight1", "room": "cockpit", "next": "river",
		"items_extra": ["res://data/items_later.json"],
		"end_card": {"zh": "第一章　完", "en": "End of Chapter One"}},
	"river": {"story": "res://data/story_river.json", "start": "start_river", "room": "river_bank", "spawn": "river_bank_hatch", "next": "",
		"carry_flags": ["burned_blue_stone", "burned_commute_card"], "hud_fuel": false,
		"items_extra": ["res://data/items_later.json"]},
}

## 森林自动玩（--story_auto）到 launched 时的样子（10-29）；剧本改了以后这里不一定完全一样，只是直接进 flight1 时的起点
const SEED := {
	"flags": ["crashed", "got_luggage", "got_wood", "got_resin", "got_branch", "fuel_full", "got_scrap", "deer_met", "road_1",
		"road_stall", "log_started", "branch_a", "branch_b", "log_cleared", "fog_on", "seen_hollow", "went_wrong", "at_treehouse",
		"met_miluo", "tea_done", "parts_needed", "asked_return", "took_radio", "took_lamp", "took_sign", "got_spring",
		"spring_from_clock", "got_plank", "got_sap", "plank_hint", "bridge_built", "saw_rock", "returned_sign", "returned_any",
		"got_valve", "parts_all", "returned_lamp", "returned_radio", "returned_all", "tools_started", "tools_ok", "ship_fixed",
		"musicbox_fixed", "gramophone_talk", "pump_trip", "pump_placed", "shop_done", "slope_talked", "revisit_done",
		"farewell_done", "ready_to_launch", "launched"],
	"owned": ["elephant_drawing", "journal", "species_query", "commute_card", "home_photo", "music_box", "blue_stone", "travel_map",
		"glowing_wood", "mat_resin", "mat_branch", "mat_scrap", "clear_seed", "miluo_note", "postcard", "communicator"],
	"journal": [{"zh": "大象：四条腿，长鼻子，两只耳朵。", "en": "Elephant: four legs, a long trunk, two ears.", "tag": "elephant"}],
}


## flight1 自动玩（--story_auto，放第一件 = 蓝色石头）完时多出来的 flags；物品少了被烧掉的那件。10-29 跑出来的
const SEED_FLIGHT1 := {
	"flags": ["flight1_started", "flight1_leak", "flight1_leak_wait", "flight1_leak_fixed", "flight1_reroute", "flight1_fuel_low",
		"burned_blue_stone", "flight1_burned", "flight1_logged", "flight1_miluo_msg", "flight1_journal", "flight1_landing", "flight1_done"],
	"burned": "blue_stone",
}


## 现在是哪一章：F8 跳节拍选的（PICK_META）> 命令行 --chapter=名字 > Engine meta（换章 / F8 跳过来）> --story= 指向某一章的剧本 > forest
static func current(story_arg: String) -> String:
	if Engine.has_meta(PICK_META) and Engine.has_meta(CHAPTER_META) and CHAPTERS.has(str(Engine.get_meta(CHAPTER_META))):
		return str(Engine.get_meta(CHAPTER_META))
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--chapter="):
			var c := a.trim_prefix("--chapter=")
			if CHAPTERS.has(c):
				return c
			push_warning("没有这一章：%s（有：%s）" % [c, ", ".join(CHAPTERS.keys())])
	if Engine.has_meta(CHAPTER_META) and CHAPTERS.has(str(Engine.get_meta(CHAPTER_META))):
		return str(Engine.get_meta(CHAPTER_META))
	for c in CHAPTERS:
		if story_arg != "" and story_arg == str(CHAPTERS[c]["story"]):
			return c
	return "forest"


static func info(ch: String) -> Dictionary:
	return CHAPTERS.get(ch, CHAPTERS["forest"])


## 进这一章时的状态：带过来的 / SEED（森林是新游戏，什么都不恢复）
static func restore(ch: String) -> void:
	for p in info(ch).get("items_extra", []):
		register_items(str(p))
	if ch == "forest":
		return
	var carry = Engine.get_meta(CARRY_META) if Engine.has_meta(CARRY_META) else null
	if carry is Dictionary and not (carry as Dictionary).is_empty():
		StoryState.from_dict(carry)
	else:
		var flags: Array = SEED["flags"].duplicate()
		var owned: Array = SEED["owned"].duplicate()
		if ch == "river":
			var burned := str(SEED_FLIGHT1["burned"])
			var fl: Array = SEED_FLIGHT1["flags"].duplicate()
			if "--river_seed=card" in OS.get_cmdline_user_args() or (Engine.has_meta(RIVER_SEED_META) and str(Engine.get_meta(RIVER_SEED_META)) == "card"):
				burned = "commute_card"
				fl[fl.find("burned_blue_stone")] = "burned_commute_card"
			flags.append_array(fl)
			owned.erase(burned)
		StoryState.from_dict({"flags": flags, "owned": owned, "journal": SEED["journal"], "props": {}, "used": []})
		Engine.set_meta(CARRY_META, StoryState.to_dict())


## 换到下一章：存状态、记下章节名，下一帧重新载入本场景
static func go(tree: SceneTree, ch: String) -> void:
	for p in info(ch).get("items_extra", []):
		register_items(str(p))
	Engine.set_meta(CARRY_META, StoryState.to_dict())
	Engine.set_meta(CHAPTER_META, ch)
	for prev in CHAPTERS:
		if CHAPTERS[prev].get("next", "") == ch and CHAPTERS[prev].has("end_card"):
			await _end_card(tree, CHAPTERS[prev]["end_card"])
	tree.reload_current_scene.call_deferred()


## 上一章的结束卡（「第一章 完」）：挂在根节点上的黑底 + 两行字（当前语言一行、另一种语言小字一行），在已经黑了的屏幕上淡入、停住；
## 换章重新载入时它不在场景里，留着盖住，新章节开始以后再慢慢淡掉、删掉。
static func _end_card(tree: SceneTree, card: Dictionary) -> void:
	var cl := CanvasLayer.new()
	cl.layer = 120
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = UITheme.get_theme()
	var bg := ColorRect.new()
	bg.color = Color.BLACK
	bg.size = Vector2(480, 270)
	root.add_child(bg)
	var other := "en" if I18n.is_zh() else "zh"
	for i in 2:
		var l := Label.new()
		l.text = I18n.pick(card) if i == 0 else str(card.get(other, ""))
		l.add_theme_font_size_override("font_size", 28 if i == 0 else 14)
		l.add_theme_color_override("font_color", Color("#b9cdc1") if i == 0 else Color("#6f877b"))
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.size = Vector2(480, 32 if i == 0 else 16)
		l.position = Vector2(0, 112 if i == 0 else 150)
		l.modulate.a = 0.0
		root.add_child(l)
		tree.create_tween().tween_property(l, "modulate:a", 1.0, 1.4).set_delay(0.4 + 0.5 * i).set_trans(Tween.TRANS_SINE)
	cl.add_child(root)
	tree.root.add_child(cl)
	await tree.create_timer(3.6).timeout
	var tw := tree.create_tween()
	tw.tween_interval(0.6)                       # 新章节载入、自己的黑屏接上以后
	tw.tween_property(root, "modulate:a", 0.0, 1.2).set_trans(Tween.TRANS_SINE)
	tw.tween_callback(cl.queue_free)


## F8 跳节拍 / 重开：重新载入本场景，剧情播到一半也干净。reload_current_scene 只是先把旧场景移出树、帧末才释放，
## 这一帧剩下的时间里旧场景里正在 await 的剧情步骤还会被计时器 / process_frame 叫醒，一调 get_tree() 就是 null 报错。
## 所以等到这一帧的空档（deferred，旧场景自己的回调都退出了）先把旧场景整个 free 掉（挂着的 await 跟着作废）再载入
static func hard_reload(tree: SceneTree) -> void:
	_free_and_reload.call_deferred(tree)


static func _free_and_reload(tree: SceneTree) -> void:
	var s := tree.current_scene
	if s == null:
		return
	var path := s.scene_file_path
	s.get_parent().remove_child(s)
	s.free()
	tree.change_scene_to_file(path)


## 回标题（新游戏）：清掉章节和带过去的状态
static func reset() -> void:
	if Engine.has_meta(PICK_META):
		Engine.remove_meta(PICK_META)
	if Engine.has_meta(CHAPTER_META):
		Engine.remove_meta(CHAPTER_META)
	if Engine.has_meta(CARRY_META):
		Engine.remove_meta(CARRY_META)


## items_later.json 这种「后面章节才有的物品」：items.json 里没有的补进物品表（register_fallback，已有的不动）
static func register_items(path: String) -> void:
	if not FileAccess.file_exists(path):
		return
	var d = JSON.parse_string(FileAccess.get_file_as_string(path))
	var arr: Array = []
	if d is Dictionary:
		arr = d.get("items", [])
	elif d is Array:
		arr = d
	for it in arr:
		if it is Dictionary:
			Inventory.register_fallback(it)
