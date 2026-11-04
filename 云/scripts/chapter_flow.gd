extends RefCounted
## 章节之间怎么接（level_forest.gd 用；章节都在 scenes/level_forest.tscn 这一个关卡里播，换章 = 带着状态重新载入本场景）。
##   forest   木星森林：开场 → 坠毁 → 修船 → 起飞（data/story_forest.json）。剧本 end_chapter：照旧播起飞，黑屏以后接 flight1。
##   flight1  第一次飞行，驾驶舱（data/story_flight1.json，入口 start_flight1）。end_chapter：往前一冲（cockpit_dash）、淡到黑、
##            「第一章 完」卡（end_card：go() 在黑屏上淡入、停一会儿，载入下一章以后再淡掉），接 river。
##   river    河流篇「妮芙的三分钟」（data/story_river.json，入口 start_river，房间 river_bank；多房间，见 docs/river_rooms_contract.md）。
##            end_chapter：驾驶舱里写完日记，「第二章 完」卡，接 final。
##   final    终章「还剩下什么 · 四个结局 · 尾声」（data/story_final.json，入口 start_final，从驾驶舱开始；多房间，计划见 docs/第三章计划.md）。
##            end_chapter（母星尾声最后）：没有下一章，last_card = 出「全剧终」卡，3 秒以后按任意键回标题（新游戏）。
## 带过去的东西：StoryState.to_dict()（flags、日记、物件状态、用过的点、背包）存进 Engine 的 meta CARRY_META，
##   新章节 _ready 里 from_dict 恢复；这份一直留着（F8「重开本章」/ 跳节拍从同一个起点重来），回标题时清掉。
## 直接进 flight1（--chapter=flight1、F8「跳到飞行一」）又没有带过来的状态：用 SEED（森林自动玩到起飞时的 flags 和背包）。
## 直接进 river：SEED + SEED_FLIGHT1（flight1 自动玩完：放了蓝色石头）；--river_seed=card / F8 切成「烧了通勤卡」那版（原文 119 摸衣袋两个分支）。
## 直接进 final：再加 SEED_RIVER（河流篇走完）；--river_seed=card 同样切成「烧了通勤卡」那版。

const CHAPTER_META := "the_cloud_chapter"
const CARRY_META := "the_cloud_carry"
const RIVER_SEED_META := "the_cloud_river_seed"        # F8：直接进河流篇时用哪个 SEED（"" = 烧了蓝色石头 / "card" = 烧了通勤卡）
const PICK_META := "the_cloud_chapter_pick"            # F8 跳节拍换了章：CHAPTER_META 比命令行 --chapter= 优先（不然带着 --chapter 跑就跳不过去）

## 以物易物设的 flag（scripts/barter.gd，docs/以物易物交换表.md）：森林的大嘴鸟、河流的鼠妈；后面章节的 if 看这些
const BARTER_FOREST := ["barter_any", "barter_toucan", "barter_toucan_feather", "barter_toucan_whistle", "barter_toucan_rain"]
const BARTER_RIVER := ["barter_rat_chef", "barter_rat_chef_soup", "barter_rat_chef_recipe", "barter_rat_chef_fire"]
## 第一关新版（11-02）：亲情关系（鹿叫晨妈妈 / 孩子）和飞行一烧掉的新物品；后面章节的 if 可以看这些
const C1_FLAGS := ["c1_mom", "c1_child", "c1_bear_given", "burned_family_photo", "burned_deer_bear", "burned_miluo_letter",
	"burned_rabbit_fur", "burned_floorboard"]

const CHAPTERS := {
	"forest": {"story": "res://data/story_forest.json", "next": "flight1", "hud_fuel": false},   # 11-05 夜测：第一关新版没有燃料表，没目标的时候左上角别冒出「10 / 200」
	"flight1": {"story": "res://data/story_flight1.json", "start": "start_flight1", "room": "cockpit", "next": "river",
		"carry_flags": BARTER_FOREST + C1_FLAGS, "items_extra": ["res://data/items_later.json"],
		"end_card": {"zh": "第一章　完", "en": "End of Chapter One"}},
	"river": {"story": "res://data/story_river.json", "start": "start_river", "room": "river_bank", "spawn": "river_bank_hatch", "next": "final",
		"carry_flags": ["burned_blue_stone", "burned_commute_card", "burned_rain_glass"] + BARTER_FOREST + C1_FLAGS, "hud_fuel": false,
		"items_extra": ["res://data/items_later.json"],
		"end_card": {"zh": "第二章　完", "en": "End of Chapter Two"}},
	# carry_flags：飞行一烧了哪件（燃料柜空的那格）；森林的 returned_all / returned_any / saw_rock（尾声鹿、弥洛的分支）
	"final": {"story": "res://data/story_final.json", "start": "start_final", "room": "cockpit", "next": "",
		"carry_flags": ["burned_blue_stone", "burned_commute_card", "burned_rain_glass", "returned_all", "returned_any", "saw_rock", "musicbox_fixed",
			"river_cup_traced",             # 11-02 河流篇来客册改成可选：epi_miluo 按它分支
			"river_n_plain", "river_n_courier", "river_n_bio", "river_n_mom", "river_n_odd"]   # 河流篇开头怎么回妮芙：终章她的消息按这个称呼晨
			+ BARTER_FOREST + BARTER_RIVER + C1_FLAGS,
		"items_extra": ["res://data/items_later.json", "res://data/items_final.json"], "last_card": true},
}

## 森林自动玩（--story_auto）到 launched 时的样子；剧本改了以后这里不一定完全一样，只是直接进 flight1 时的起点。
## 11-02 第一关新版（c1_*）跑出来的：旧流程的行李（蓝色石头、通勤卡、音乐盒……）新流程不再给，所以这里也没有；
## 河流篇 / 终章里看旧 flag 的分支（burned_blue_stone 这些）照旧由 SEED_FLIGHT1 给。
const SEED := {
	"flags": ["crashed", "c1_crashed", "c1_saw_bag", "c1_mom", "c1_deer_met", "c1_asked_bag", "c1_follow", "c1_run", "c1_got_bag",
		"c1_got_map", "c1_chase_done", "c1_woke", "c1_bear_given", "c1_need_wood", "c1_to_rabbit", "c1_danced", "c1_got_wood",
		"c1_fixed", "c1_seed", "c1_ready", "launched"],
	"owned": ["elephant_drawing", "deer_bear", "rabbit_fur", "floorboard", "floorboard",
		"miluo_letter", "clear_seed", "miluo_note"],
	"journal": [],
}


## flight1 自动玩（--story_auto，放第一件 = 蓝色石头）完时多出来的 flags；物品少了被烧掉的那件。10-29 跑出来的
const SEED_FLIGHT1 := {
	"flags": ["flight1_started", "flight1_leak", "flight1_leak_wait", "flight1_leak_fixed", "flight1_reroute", "flight1_fuel_low",
		"burned_blue_stone", "flight1_burned", "flight1_logged", "flight1_miluo_msg", "flight1_journal", "flight1_landing", "flight1_done"],
	"burned": "blue_stone",
}


## river 走完（river_done）时多出来的 flags 和物品：10-31 从 story_river.json 的 flag / give / take 静态收出来（河流篇 flag 都是主线必经的），
## 不是自动玩跑出来的；只是直接进 final 时的起点
const SEED_RIVER := {
	"flags": ["river_ashore", "river_met", "river_salvaged", "river_landed", "river_bread", "river_book_drying", "river_peek1", "river_peek2",
		"river_sat_down", "river_deer_msg", "river_footage_broken", "river_need_head", "river_market", "river_breather", "river_oldstreet",
		"river_sluice_done", "river_jam", "river_roped", "river_wh_dive", "river_wh_in", "river_back_home", "river_footage_fixed",
		"river_cup_traced", "river_prints", "river_dock_matched", "river_ship_number", "river_bell", "river_plane_fixed", "river_farewell",
		"river_done"],
	"owned": ["biscuits", "waterproof_board", "cup_tracing", "footprint_rubbing", "dock_photo", "copper_bell", "mat_driftwood",
		"elephant_footage", "river_water"],
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
	register_side_items()
	if ch == "forest":
		return
	var carry = Engine.get_meta(CARRY_META) if Engine.has_meta(CARRY_META) else null
	if carry is Dictionary and not (carry as Dictionary).is_empty():
		StoryState.from_dict(carry)
	else:
		var flags: Array = SEED["flags"].duplicate()
		var owned: Array = SEED["owned"].duplicate()
		if ch in ["river", "final"]:
			var burned := str(SEED_FLIGHT1["burned"])
			var fl: Array = SEED_FLIGHT1["flags"].duplicate()
			if "--river_seed=card" in OS.get_cmdline_user_args() or (Engine.has_meta(RIVER_SEED_META) and str(Engine.get_meta(RIVER_SEED_META)) == "card"):
				burned = "commute_card"
				fl[fl.find("burned_blue_stone")] = "burned_commute_card"
			flags.append_array(fl)
			owned.erase(burned)
		if ch == "final":
			flags.append_array(SEED_RIVER["flags"])
			owned.append_array(SEED_RIVER["owned"])
		StoryState.from_dict({"flags": flags, "owned": owned, "journal": SEED["journal"], "props": {}, "used": []})
		Engine.set_meta(CARRY_META, StoryState.to_dict())


## 换到下一章：存状态、记下章节名，下一帧重新载入本场景
static func go(tree: SceneTree, ch: String) -> void:
	for p in info(ch).get("items_extra", []):
		register_items(str(p))
	register_side_items()
	Engine.set_meta(CARRY_META, StoryState.to_dict())
	Engine.set_meta(CHAPTER_META, ch)
	Engine.set_meta(PICK_META, true)          # 换章也要压过命令行 --chapter=（不然 --chapter=flight1 --story_chain 演完又回到 flight1 开头）
	for prev in CHAPTERS:
		if CHAPTERS[prev].get("next", "") == ch and CHAPTERS[prev].has("end_card"):
			await _end_card(tree, CHAPTERS[prev]["end_card"])
	(load("res://scripts/audio_fade.gd") as GDScript).release(tree.current_scene, 0.8)   # 还在响的长声音（引擎、冲刺）淡掉，不被重新载入掐断
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


## 第一关支线文件（data/forest_side_*.json）里的物品：每一章都补进物品表（直接进飞行一 / 后面章节时也认得支线带来的燃料、纪念品）。
## 标 _side，森林剧本载入时（story_runner._merge_includes）就知道不是和 items.json 重名
const SIDE_PREFIX := "res://data/forest_side_"


static func register_side_items() -> void:
	var dir := SIDE_PREFIX.get_base_dir()
	var da := DirAccess.open(dir)
	if da == null:
		return
	for f in da.get_files():
		if not (f.begins_with(SIDE_PREFIX.get_file()) and f.ends_with(".json")):
			continue
		var d = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join(f)))
		if not d is Dictionary:
			continue
		for it in d.get("items", []):
			if it is Dictionary and not Inventory.defined(str(it.get("id", ""))):
				it["_side"] = f
				Inventory.register_fallback(it)


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
