extends RefCounted
## 章节之间怎么接（level_forest.gd 用；章节都在 scenes/level_forest.tscn 这一个关卡里播，换章 = 带着状态重新载入本场景）。
##   forest   木星森林：开场 → 坠毁 → 修船 → 起飞（data/story_forest.json）。剧本 end_chapter：照旧播起飞，黑屏以后接 flight1。
##   flight1  第一次飞行，驾驶舱（data/story_flight1.json，入口 start_flight1）。end_chapter：「未完待续」卡（河流篇还没接）。
## 带过去的东西：StoryState.to_dict()（flags、日记、物件状态、用过的点、背包）存进 Engine 的 meta CARRY_META，
##   新章节 _ready 里 from_dict 恢复；这份一直留着（F8「重开本章」/ 跳节拍从同一个起点重来），回标题时清掉。
## 直接进 flight1（--chapter=flight1、F8「跳到飞行一」）又没有带过来的状态：用 SEED（森林自动玩到起飞时的 flags 和背包）。

const CHAPTER_META := "the_cloud_chapter"
const CARRY_META := "the_cloud_carry"

const CHAPTERS := {
	"forest": {"story": "res://data/story_forest.json", "next": "flight1"},
	"flight1": {"story": "res://data/story_flight1.json", "start": "start_flight1", "room": "cockpit", "next": "",
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


## 现在是哪一章：命令行 --chapter=名字 > Engine meta（换章 / F8 跳过来）> --story= 指向某一章的剧本 > forest
static func current(story_arg: String) -> String:
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
		StoryState.from_dict({"flags": SEED["flags"], "owned": SEED["owned"], "journal": SEED["journal"], "props": {}, "used": []})
		Engine.set_meta(CARRY_META, StoryState.to_dict())


## 换到下一章：存状态、记下章节名，下一帧重新载入本场景
static func go(tree: SceneTree, ch: String) -> void:
	for p in info(ch).get("items_extra", []):
		register_items(str(p))
	Engine.set_meta(CARRY_META, StoryState.to_dict())
	Engine.set_meta(CHAPTER_META, ch)
	tree.reload_current_scene.call_deferred()


## 回标题（新游戏）：清掉章节和带过去的状态
static func reset() -> void:
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
