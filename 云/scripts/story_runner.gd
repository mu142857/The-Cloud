extends Node
## 章节剧情引擎：读剧本 JSON（默认 data/story_forest.json，没有就退回 data/story_forest_sample.json），播 scene、管 hotspot、
## 自动玩、跳节拍、检查剧本。剧本格式和全部步骤见 docs/forest_chapter.md「剧本数据格式」。level_forest.gd 在 _ready 里建它。
##
## 拆成几块：
##   story_state.gd     flags / 日记 / 物件状态 / 用过的 hotspot（以后存档存这一份）
##   story_world.gd     markers、墙、物件（缺图色块）、树屋室内、雾
##   hotspots.gd        哪些点能用、提示箭头、晨身边 / 鼠标点到的那个
##   story_dialogue.gd  头顶对话框、旁白、拿到东西的提示、点选、结束卡
##   这里              一步一步播 scene（每步一个 await）、自动玩、跳节拍、统计、检查
##
## 播放：play(scene) 是协程，播完返回；goto / pick 跳到别的 scene（不回来）。剧情播放时锁晨、黑边按需（_wants_bars）。
## 引擎和剧本对接的点（剧本里有就用，没有就用关卡原来的）：
##   开场爬起来以后：hooks.crash，或第一个存在的 crash_wake / wake / crash / intro / opening
##   开场爬起来以后（真剧本：intro，设 crashed）
##   发光木头：保留关卡原来的拾取过场（走过去、弯腰、木头飞进背包、燃烧值滚动）。剧本里 at = wood 的 hotspot（wood / wood_last）
##     不单独出现，过场里播它的 scene（第一个能用的那个），scene 里的 anim pickup 和 give（已经给过的东西）跳过；引擎再设 got_wood。
##     没有这种 hotspot 就找 hooks.wood，或 wood_found / wood / wood_pickup / pickup_wood / glowing_wood
##   燃烧值刚到 launch_burn（设了 fuel_full）以后：hooks.fuel_full，或 fuel_full / fuel_ready
## 第二版步骤（设计文档末尾「补充步骤」）：hotspot 的 trigger:"enter" / range；walk / guide 的 wait:false、speed；
##   ambient（循环环境声，AudioStreamPlayer2D 放在 marker 上：音量随距离、左右声道随方位）；show_item；if（flag 可写 "!名字"）。
##   缺的音效文件静默跳过（STORY_CHECK 里列出来）。
## 放手让玩家走（作者的规矩）：鹿带路（guide）不锁晨——鹿跑到点停下回头等，这段剧情先停下（剩下的步骤记在 pending_guide），
##   晨可以往回走、捡东西、看东西、和别人说话；晨走到鹿 GUIDE_NEAR 以内（又没有别的剧情在播）就从停下的那一步接着播。
##   轻引导：main_target() = 现在主线下一个该去的地方（等人的鹿 / 会推进剧情的点 / 木头），level_forest.gd 在它出了屏幕时
##   在屏幕边上画一个很淡的小箭头；玩家 NUDGE_AFTER 秒没推进主线，晨小声自言自语一句：剧本里有 scene「nudge_<那个 hotspot id>」
##   （或 nudge_guide = 等鹿的时候）就说它的第一句台词（不锁人、几秒后自己消失），没有就不说。
## 补写台词：剧本里带 "added": true 的台词正文用柔和的蓝色（mark_added；debug 构建默认开，正式版默认关，F8 面板能开关）。
## 第三 / 四版：
##   hotspot 的 accepts：{"物品 id": scene, "_default": scene}：互动时背包里有它能接受的东西 → 弹出道具选择条（背包物品 +
##     「只是看看」）；选对的播对应 scene，选别的播 _default（没有就晨说一句「这个好像用不上。」），「只是看看」播 hotspot 的 scene。
##     背包里选中一件按「使用」= use_item：用在晨身边那个 hotspot 上（同样的规则；身边没有就「这附近用不上。」）。不扣任何东西。
##   {"do": "choice", "options": [{zh, en, scene}…]}：对话选项（晨的 2~3 个回答），选中的那句晨说出来，再跳到它的 scene（没写 scene 就接着播）。
##   {"do": "elephant_call", "variant": 1|2}：远处一排树冠依次轻晃（1 从左到右、2 从右到左）+ elephant_call_<n> + tree_sway
##     （左右声道跟着树冠从一侧推到另一侧）+ 镜头不声不响地停一下 + 晨抬头（看）。等树冠晃完再下一步。
##   journal 可带 "tag"（比如 elephant）；物品 desc_from_tag = 描述后面接上带这个 tag 的日记条目（大象的画）。
##   {"do": "journal_strike", "match": "文字"}：日记里含这段文字的条目划掉（背包日记里显示删除线）。
##   {"do": "journal_mark", "match": "文字"}：加下划线（后来再 journal_strike 的话删除线盖在上面）。journal / journal_strike
##     默认配 pen_write / pen_strike 音效（剧本自己写了 sfx 就听剧本的）。
##   {"do": "count", "flags": [..], "set": "名字", "at_least": n}：数这些 flag 设了几个，够 n 就设 set。
##   顶层 "hints"：玩家 NUDGE_AFTER 秒没推进主线，按 flag 挑一条让晨自言自语（不锁人）。认两种写法：
##     数组 [{"flag"?: f, "need"?: [..], "not"?: [..], "zh", "en"}…]（条件都满足的里面挑 flag 最近设的那条）；
##       条目也可以写 "lines": [{zh, en, added?}…]（三章现在都这么写）：每隔 NUDGE_EVERY 秒说下一句，说完为止；
##     字典 {"flag 名": {zh, en} 或 [{zh, en}…]}（挑最近设的、有提示的那个 flag）。没有 hints 再找 scene nudge_<hotspot id>。
##   坠毁后飞船里断续的警报 alarm_broken：引擎在 wreck 处放成 ambient，晨第一次修飞船（tried_parts）或捡到木头（got_wood）后淡掉。
## 第五版：
##   {"do": "drawing_closeup", "sec": n}：屏幕中间展开画的特写（art/forest_story/drawing_closeup.png，纸张展开、背景压暗），
##     停 n 秒，确认键 / 点击提前收起。缺图跳过。
##   {"do": "treeline_match"}：淡入树冠缺口那一屏（坠毁现场那排树冠的平面侧视、中间被撞出的弧形凹口；单独一屏，
##     不在森林的视差层里，见 story_world.gd 的 treeline_view_in）→ 停一下 → 画上的弧线（drawing_arc）放大 3 倍、
##     按端点对齐叠到凹口上（淡入、停、淡出；弧线跟着凹口那一层漂，任何一帧都对得上）→ 淡出回到森林。缺图跳过。
##   看树冠缺口的 hotspot（at = treeline_gap，或 hotspot 写 "view": "treeline"）：scene 开始前淡入同一屏（不叠弧线），
##     晨的台词在这一屏上说完再淡出回到森林（森林里抬头是看不到这道缺口的）。这一屏出来的时候所有对话框都放在
##     画面下方居中（TREELINE_VIEW_ANCHOR，不挡凹口），左上角目标 / 燃料和背包图标淡出（见 story_world.gd）。
##   顶层 "objectives"：[{need, not, zh, en, show_fuel}…] 取第一个满足条件的，当左上角的「当前目标」（level_forest.gd 画）。
## 不推人（作者的规矩）：走进 trigger:"enter" 的点触发的 scene 里，「晨 walk」一律不执行（不能用台词 + 自动走路把玩家推回去；
##   该停的地方由 story_world.gd 的「看得见的边」挡住）。--story_check 会把这种步骤列出来。
##   例外：hotspot 写了 "cutscene": true = 走到这里是玩家自己要去的终点、后面是一整段往前走的过场（flight1 回到驾驶座 →
##   改航线 → 走去转化装置），过场里晨的 walk 照常走（不是把人推回去）。
## 转场（10-29）：fade_to 可带 "leave": marker（边往那边走边黑，离开）、"cam": marker（换过去以后镜头停在那，晨从画面外走进来）、
##   "arrive": marker（淡入的同时晨从 at 走几步到这里停住：到达，不是一淡入就站在目标点上；只走一小段）、
##   "place": {人: marker}（换地方的同时把人放好，淡入后不凭空出现）；show / hide 可带 "fade": 秒（4 档透明度淡入淡出）；
##   {"do": "camera", "hold"/"at"/"release"}（见 _camera）。scene 播完自动放开镜头。
##   晨的 walk 可带 "pace": "walk"（走路的速度、缓起缓停；arrive 和区域入口的到达也是这个速度）。
##   过场一播完（玩家能动了），还没走到的 walk（wait:false）立刻松手：玩家任何时候都不会被推着走。
## 引擎扩展（设计文档之外、可选）：hotspot 的 at = NPC 名（跟着角色）；
##   show / hide 的 who 也可以是物件 id；pick 选项的 "correct": true；
##   flag 步骤的 "clear"；剧本顶层的 "items"（items.json 里没有的物品先用它顶上）、"hooks"。
##
## 调试参数（level_forest.gd 转过来）：
##   --story=<路径>          用哪份剧本（res:// 或绝对路径）
##   --story_auto            自动玩：对话每句停 0.6 秒自己下一句、自己走到下一个该去的 hotspot、点选时选对的那个，一直到结束卡，
##                           打印 STORY_DONE 和统计后退出。--story_auto=full：闲聊、选错的分支也都走一遍（看全部 scene）
##   --story_shots=<目录>    每播到一个新 scene 0.5 秒后存一张图（文件名带序号和 scene id）；另外对话选项、道具选择条
##                           出来以后、远处树冠晃到一半时也各存一张（ui_choice / ui_items / ui_elephant）
##   --beat=<flag>           直接跳到「设这个 flag 的那个 scene 播完」的样子（瞬间把前面的都过一遍：flags、物品、NPC 位置都对）
##   --story_check           只检查剧本（引用不到的 marker / scene / item、不支持的步骤……），打印 STORY_CHECK 后退出

const DEFAULT_STORY := "res://data/story_forest.json"
const SAMPLE_STORY := "res://data/story_forest_sample.json"
const SFX_DIR := "res://audio/sfx/"
const TREELINE_VIEW_ANCHOR := Vector2(240, 234)   # 树冠缺口那一屏里对话框的锚点：框底边落在 229（凹口两头最低 198，框在下面的树冠上），尖角不画
const STEPS := ["say", "narr", "walk", "face", "wait", "show", "hide", "give", "take", "flag", "journal", "sfx",
	"fade_to", "anim", "prop", "guide", "goto", "pick", "end_chapter", "if", "ambient", "show_item",
	"choice", "elephant_call", "journal_strike", "count", "journal_mark", "drawing_closeup", "treeline_match", "fuel", "camera",
	"mechanic", "todo_mechanic", "form", "follow", "water", "closeup",   # 后六个：多房间章节（docs/river_rooms_contract.md）
	"pose"]   # pose：通用角色的图斜过来 / 挪一点 / 压到物件后面（_pose）
const PHONE_STEPS := ["phone_add", "phone_msg", "phone_send", "phone_open", "phone_draft"]   # 通讯器：phone_ui.gd
const COCKPIT_STEPS := {"debris_steer": "res://scripts/cockpit_debris.gd", "keepsake_choice": "res://scripts/cockpit_keepsake.gd",
	"cockpit_dash": "res://scripts/cockpit_dash.gd"}   # 驾驶舱（cockpit_dash：飞行一结尾往前一冲）
const HOOKS := {
	"crash": ["crash_wake", "wake", "crash", "intro", "opening"],
	"wood": ["wood_found", "wood", "wood_pickup", "pickup_wood", "glowing_wood"],
	"fuel_full": ["fuel_full", "fuel_ready"],
}
const ENGINE_FLAGS := ["crashed", "got_wood", "fuel_full"]
const NAME_COLORS := {"chen": Color("#c48fb4"), "deer": Color("#c9a882"), "miluo": Color("#d6c486"), "voice": Color("#8fa69a"),
	"niff": Color("#8ec9d6"), "ting": Color("#b8a58c"), "keeper": Color("#a89c8a"), "tape": Color("#8fa0a8")}
const NPC_GD := preload("res://scripts/npc_generic.gd")         # 通用角色（妮芙、阿汀、摊主…；art/characters/<id>/<id>.json）
const CLOSEUP_GD := preload("res://scripts/closeup_ui.gd")      # 特写面板
const MECH_PREFIX := "mech."                                    # 小游戏进度存在 StoryState.props["mech.<id>"]
const FOLLOW_GAP := 34.0
const HEAD := {"chen": 50.0, "deer": 52.0, "miluo": 50.0}
const ANIM_MAP := {
	"chen": {"look": "idle_eye", "pickup": "pickup", "idle": "idle", "getup": "getup", "lie": "lie"},
	"deer": {"graze": "graze_down", "graze_down": "graze_down", "graze_up": "graze_up", "look": "look", "ear": "ear", "idle": "idle"},
	"miluo": {"idle": "idle"},
}
const GUIDE_NEAR := 60.0
const NUDGE_AFTER := 20.0
const NUDGE_EVERY := 40.0
const AUTO_LINE := 0.6
const WORLD_GD := preload("res://scripts/story_world.gd")
const HOTSPOTS_GD := preload("res://scripts/hotspots.gd")
const DIALOGUE_GD := preload("res://scripts/story_dialogue.gd")
const PHONE_GD := preload("res://scripts/phone_ui.gd")
const BARK_GD := preload("res://scripts/story_bark.gd")      # say 带 bark：晨头顶的小气泡（不锁人）
const QUICK_GD := preload("res://scripts/story_quick.gd")    # give 数组、走过去就捡（hotspot pickup）

var level: Node2D
var path := ""
var data := {}
var scenes := {}
var speakers := {}
var hotspot_defs: Array = []
var world: Node2D
var hotspots: Node2D
var dlg: Control
var phone: Control                   # 通讯器界面（phone_ui.gd）
var bark: Control                    # 头顶小气泡（story_bark.gd）
var quick: RefCounted                # story_quick.gd
var cockpit_ui: Control              # 正在等玩家的驾驶舱步骤（避碎石 / 选纪念品；软锁检测用）
var missing_anims := {}              # 剧本要、晨还没有的动作（MISSING_ANIM，给奥斯卡画）
const CHEN_ALIAS := "res://data/chen_anim_alias.json"
var _chen_alias = null                # chen_alias() 读进来的别名表
var entry_scene := ""                # 这一章的入口 scene（flight1 = start_flight1；关卡直接播，--story_check 不算「播不到」）
var chen: Node2D
var deer: Node2D
var miluo: Node2D

var busy := false
var free_walk := false             # guide：剧情没播完，但晨可以自己走
var auto := ""                     # "" / "main" / "full"
var ff := false                    # 跳节拍：每步瞬间完成
var free_roam := false             # F8「探索」（level_forest.gd 自由探索）：不播任何剧情、不触发 hotspot、不说卡关提示
var shots_dir := ""
var shot_delay := 0.5
var ended := false

# 统计
var played := {}
var played_order: Array[String] = []
var lines := 0
var hotspots_used := 0
var _scene_view := ""                # 下一个 play() 的 scene 在哪一屏上播（"treeline" = 树冠缺口那一屏；trigger 设，play 用完清掉）
var _t0_ms := 0
var _game_t := 0.0
var _cur_scene := ""
var _visited := {}                 # 自动玩：hotspot id → 来的时候的 StoryState.changed
var _visit_gain := {}              # 自动玩：hotspot id → 上次点它设了几个新 flag
var _wrong_tried := {}
var _target: Dictionary = {}
var _idle_t := 0.0
var _shot_n := 0
var _warned := {}
var _wood_mode := false             # 在关卡的木头拾取过场里播剧本：跳过 anim pickup、已经给过的 give
var _ambient := {}                   # "name@at" → AudioStreamPlayer2D
var _item_show: TextureRect          # show_item 举着的那件
var _item_show_until_say := false
var missing_sfx := {}
var _family: Array = []              # 正在响的音乐盒 / 留声机音效
var _sfx_t := {}                     # 音效名 → 上次放的时刻（毫秒）：下水转场不和剧本里刚放的入水声叠
var step_i := -1                     # 正在播的 scene 的第几步（开发者面板、卡死检测用）
var step_t := 0.0                    # 这一步播了多久
var _enter_scene := false            # 这段剧情是走进 trigger:"enter" 的点触发的（不许推晨走）
var pending_guide: Dictionary = {}   # 鹿带路停在半路的剧情：{scene, index, x}
var mark_added := OS.is_debug_build()  # 补写台词标蓝
var _nudge_t := 0.0
var _nudge_progress := -1
var _nudged := {}
var _target_t := 0.0
var _target_limit := 15.0
var _unreach := {}                   # 自动玩：走过去够不着的点（id → 当时的进展）；换一段就清掉
var speaking := ""                   # 正在说话的人（关卡用它判断前景层有没有挡住）
var _npc_room := {}                  # 角色在屋里还是屋外：节点名 → forest / treehouse
var npcs := {}                       # 通用角色：名字 → npc_generic.gd（剧本 show / walk / anim / face 里出现的、不是鹿 / 弥洛的）
var _npc_names := {}                 # 剧本里当角色用过的名字
var carry_flags: Array = []          # 前面章节可能设的 flag（chapter_flow 的 carry_flags；--story_check 不报「没有地方设」）
var follow := {}                     # 跟着晨走的：名字 → 间距
var closeup_ui: Control              # 特写面板（closeup_ui.gd）
var mech_running := ""               # 正在玩的小游戏 id（镜头：房间有 viewfinder 时这期间不往前多看，见 level_forest.gd _cam_target）
var mech_wait := false               # 小游戏在等玩家互动（wait_interact）：只有临时点能用
var _mech_spots: Array = []
var _mech_hit: Dictionary = {}
signal mech_hit_sig


# ======================================================================= 读剧本
func load_story(p: String) -> void:
	path = p if p != "" else DEFAULT_STORY
	if not _exists(path):
		if p != "":
			push_warning("剧本不存在：%s，用小样" % path)
		path = SAMPLE_STORY
	var d = JSON.parse_string(FileAccess.get_file_as_string(path)) if _exists(path) else null
	if not d is Dictionary:
		push_error("剧本读不了（JSON 不对？）：" + path)
		if path != SAMPLE_STORY and _exists(SAMPLE_STORY):
			path = SAMPLE_STORY
			d = JSON.parse_string(FileAccess.get_file_as_string(path))
	data = d if d is Dictionary else {}
	scenes = data.get("scenes", {})
	speakers = data.get("speakers", {})
	hotspot_defs = data.get("hotspots", [])
	for it in data.get("items", []):
		if it is Dictionary:
			Inventory.register_fallback(it)


static func _exists(p: String) -> bool:
	return FileAccess.file_exists(p)


func setup(lv: Node2D, ui_root: Control) -> void:
	level = lv
	chen = lv.chen
	deer = lv.get_node("Deer")
	miluo = lv.get_node("Snake")
	_t0_ms = Time.get_ticks_msec()
	world = WORLD_GD.new()
	world.name = "StoryWorld"
	lv.add_child(world)
	var shown: Array = []
	for sid in scenes:
		for st in scenes[sid]:
			if st is Dictionary and str(st.get("do", "")) == "prop" and str(st.get("state", "")) == "shown":
				shown.append(str(st.get("id", "")))
	world.setup(lv, data.get("markers", {}), _steam_pipe(), shown)
	if "cockpit" in data.get("rooms", []):
		world.add_cockpit()                # 驾驶舱（cockpit_room.gd）
	_collect_npc_names()
	if _multi_room():
		_setup_stages()
	hotspots = HOTSPOTS_GD.new()
	hotspots.name = "Hotspots"
	lv.add_child(hotspots)
	lv.move_child(hotspots, chen.get_index() + 1)
	dlg = DIALOGUE_GD.new()
	dlg.name = "StoryDialogue"
	ui_root.add_child(dlg)
	hotspots.setup(self, world, hotspot_defs, ui_root)
	phone = PHONE_GD.new()
	phone.name = "Phone"
	phone.story = self
	phone.level = lv
	ui_root.add_child(phone)
	bark = BARK_GD.new()
	bark.name = "StoryBark"
	bark.story = self
	ui_root.add_child(bark)
	ui_root.move_child(bark, dlg.get_index())
	quick = QUICK_GD.new(self)
	closeup_ui = CLOSEUP_GD.new()
	closeup_ui.name = "Closeup"
	closeup_ui.story = self
	ui_root.add_child(closeup_ui)
	ui_root.move_child(closeup_ui, dlg.get_index())
	# 角色的起始位置：鹿藏着（启动失败那一幕才出来），弥洛在树屋里
	deer.visible = false
	_place(miluo, world.mx("room_miluo"), "treehouse")
	miluo.visible = true
	_npc_room[deer.name] = "forest"


## 管道那个点选里「对的」那段（细白汽冒在它上面）
func _steam_pipe() -> String:
	for id in scenes:
		for st in scenes[id]:
			if st is Dictionary and str(st.get("do", "")) == "pick":
				var opts: Array = st.get("options", [])
				var ok := _correct_index(st, str(id))
				if ok >= 0 and str(opts[ok].get("id", "")).begins_with("pipe"):
					return str(opts[ok]["id"])
	return ""


func has_scene(id: String) -> bool:
	return scenes.has(id)


func hook(kind: String) -> String:
	if kind == "wood":
		var wh := _wood_hotspot()
		if not wh.is_empty():
			return str(wh.get("scene", ""))
	var h: Dictionary = data.get("hooks", {})
	if h.has(kind) and scenes.has(str(h[kind])):
		return str(h[kind])
	for c in HOOKS.get(kind, []):
		if scenes.has(c):
			return c
	return ""


## 剧本里放在发光木头上的 hotspot（第一个条件满足的）
func _wood_hotspot() -> Dictionary:
	for h in hotspot_defs:
		if h is Dictionary and str(h.get("at", "")) == "wood" and scenes.has(str(h.get("scene", ""))):
			if StoryState.all_of(h.get("need", [])) and StoryState.none_of(h.get("not", [])):
				return h
	for h in hotspot_defs:
		if h is Dictionary and str(h.get("at", "")) == "wood" and scenes.has(str(h.get("scene", ""))):
			return h
	return {}


## 关卡自己管的点：木头还在地上时，at = wood 的 hotspot 交给拾取过场
func hotspot_blocked(h: Dictionary) -> bool:
	if mech_wait != h.has("_mech"):
		return true                        # 小游戏等互动时只有它的临时点；平时临时点不出现
	return str(h.get("at", "")) == "wood" and level.wood_available()


## 木头拾取过场里播剧本
func play_wood(id: String) -> void:
	_wood_mode = true
	var wh := _wood_hotspot()
	if not wh.is_empty():
		StoryState.mark_used(str(wh.get("id", "")))
		hotspots_used += 1
	await play(id, false)
	_wood_mode = false


func npc(who: String) -> Node2D:
	match who:
		"chen":
			return chen
		"deer":
			return deer
		"miluo", "milo", "snake":
			return miluo
	return _generic(who)


## 文字：当前语言，空的就回落中文
func txt(d) -> String:
	return str(txt_lang(d)[0])


## 文字和它实际用的是哪种语言：[文字, "zh"/"en"]（台词回落到中文时，说话人名字也跟着用中文）
func txt_lang(d) -> Array:
	if d is Dictionary:
		var s := str(d.get(I18n.lang, ""))
		if s != "":
			return [s, I18n.lang]
		s = str(d.get("zh", ""))
		if s != "":
			return [s, "zh"]
		return [str(d.get("en", "")), "en"]
	if d == null:
		return ["", I18n.lang]
	return [str(d), I18n.lang]


## 名字取指定语言，那种语言没写就退回 txt
func txt_in(d, lang: String) -> String:
	if d is Dictionary and str(d.get(lang, "")) != "":
		return str(d[lang])
	return txt(d)


func _warn_once(msg: String) -> void:
	if _warned.has(msg):
		return
	_warned[msg] = true
	push_warning("剧本：" + msg)


# ======================================================================= 播
func play(id: String, manage := true, from_index := 0) -> void:
	if free_roam:
		return
	if busy:
		_warn_once("已经在播，忽略 " + id)
		return
	busy = true
	hotspots.active = false
	if manage and not ff:
		level.story_begin(_wants_bars(id))
		dlg.top_limit = level.BAR_H + 4.0 if level.bars_on() else 4.0
		await _settle_start()                  # 晨站在别人身上 / 跟着的人压在晨身上：先让开
	var view: bool = _scene_view == "treeline" and manage and not ff and world.has_treeline_view()
	_scene_view = ""
	if view:
		await world.treeline_view_in(0.7 if auto == "" else 0.3)
		_ui_shot("treeline", 0.3)
	var cur := id
	var hops := 0
	var fuel_before := StoryState.has("fuel_full")
	while cur != "" and hops < 200 and not ended:
		hops += 1
		if not scenes.has(cur):
			_warn_once("没有这个 scene：" + cur)
			break
		_on_scene(cur)
		var next := ""
		step_i = -1
		var steps: Array = scenes[cur]
		var start := from_index
		from_index = 0
		for si in range(start, steps.size()):
			var st = steps[si]
			step_i = si
			step_t = 0.0
			if not st is Dictionary:
				continue
			var t_step := _game_t
			var g: String = await _step(st)
			if not ff:
				_count_wait(cur, st, _game_t - t_step)
			if ended:
				break
			if g == "__pause__":
				# 鹿带路：这段先停，剩下的等晨走到鹿身边再接着播（见 resume_guide）
				pending_guide["scene"] = cur
				pending_guide["index"] = si + 1
				break
			if g != "":
				next = g
				break
		if ff and ff_stop and _ff_target != "" and StoryState.has(_ff_target) and next != "":
			ff_resume = next                 # 跳节拍（别的章节）：设目标 flag 的 scene 播完就停，后面的由关卡正常播
			break
		cur = next
	dlg.close_box()
	if view:
		await world.treeline_view_out(0.7 if auto == "" else 0.3)
	free_walk = false
	step_i = -1
	if manage and not ff and not ended:
		level.story_end()
	busy = false
	hotspots.active = true
	if not ended and not fuel_before:
		await check_fuel_hook()


## 燃烧值刚到 200：剧本里有 fuel_full 场景就接着播
func check_fuel_hook() -> void:
	if not StoryState.has("fuel_full") or busy:
		return
	var h := hook("fuel_full")
	if h != "" and not played.has(h):
		await play(h)


func _on_scene(id: String) -> void:
	_cur_scene = id
	var first := not played.has(id)
	played[id] = int(played.get(id, 0)) + 1
	played_order.append(id)
	if ff:
		return
	if auto != "":
		print("STORY_SCENE %s  t=%.1f" % [id, _game_t])
	if first and shots_dir != "":
		_shot(id)


## 界面出来的时候也存一张（对话选项、道具选择条、树冠晃动）
func _ui_shot(kind: String, delay: float) -> void:
	if shots_dir == "" or ff:
		return
	_shot_n += 1
	var n := _shot_n
	await get_tree().create_timer(delay).timeout
	level._save(shots_dir.path_join("%03d_ui_%s_%s.png" % [n, kind, _cur_scene.validate_filename()]))


func _shot(id: String) -> void:
	_shot_n += 1
	var n := _shot_n
	await get_tree().create_timer(shot_delay).timeout
	level._save(shots_dir.path_join("%03d_%s.png" % [n, id.validate_filename()]))


func _wants_bars(id: String) -> bool:
	var says := 0
	for st in scenes.get(id, []):
		if not st is Dictionary:
			continue
		if st.has("say"):
			says += 1
		if str(st.get("do", "")) in ["walk", "guide", "fade_to", "anim", "show", "pick", "end_chapter"]:
			return true
	return says >= 4


## 一步。返回下一个 scene（goto / pick），"" = 接着播这个 scene
func _step(st: Dictionary) -> String:
	if st.has("say"):
		await _say(st)
		return ""
	if st.has("narr"):
		await _narr(st)
		return ""
	var d := str(st.get("do", ""))
	match d:
		"walk":
			await _walk(st)
		"face":
			_face(st)
		"wait":
			if not ff:
				await _wait(maxf(float(st.get("sec", 0.5)) * WAIT_SCALE, 0.3))
		"show":
			_show(st, true)
		"hide":
			_show(st, false)
		"give":
			if st.has("items"):
				await quick.give_many(st)
			else:
				await _give(str(st.get("item", "")))
		"take":
			_take(str(st.get("item", "")))
		"flag":
			if st.has("set"):
				StoryState.set_flag(str(st["set"]))
			if st.has("clear"):
				StoryState.clear_flag(str(st["clear"]))
		"journal":
			_journal(st)
		"sfx":
			_sfx(st)
		"fade_to":
			await _fade_to(st)
		"anim":
			_anim(st)
		"prop":
			world.set_prop(str(st.get("id", "")), str(st.get("state", "")))
		"guide":
			await _guide(st)
			if not pending_guide.is_empty() and not pending_guide.has("scene"):
				return "__pause__"
		"goto":
			return str(st.get("scene", ""))
		"pick":
			var s: String = await _pick(st)
			return s
		"end_chapter":
			await _end_chapter()
		"if":
			var f := str(st.get("flag", ""))
			var yes := not StoryState.has(f.substr(1)) if f.begins_with("!") else StoryState.has(f)
			var to := str(st.get("then" if yes else "else", ""))
			if to == "":
				return ""
			if _falls_through(to):
				# 分支 scene 播完没有跳走（没有 goto / 点选 / 结束）：播完回来接着播 if 后面的步骤（flight1 记日记那种写法）
				var outer := _cur_scene
				_on_scene(to)
				for st2 in scenes[to]:
					if not st2 is Dictionary:
						continue
					var g2: String = await _step(st2)
					if ended or g2 != "":
						return g2
				_cur_scene = outer
				return ""
			return to
		"ambient":
			_ambient_step(st)
		"show_item":
			_show_item(st)
		"choice":
			var cs: String = await _choice(st)
			return cs
		"mechanic":
			await _mechanic(st)
		"todo_mechanic":
			_warn_once("todo_mechanic %s：小游戏还没接上，跳过" % st.get("id", ""))
		"form":
			var fn := npc(str(st.get("who", "")))
			if fn != null and fn.has_method("set_form"):
				fn.set_form(str(st.get("form", "land")))
		"pose":
			await _pose(st)
		"follow":
			var who_f := str(st.get("who", ""))
			if st.get("on", true):
				follow[who_f] = float(st.get("gap", FOLLOW_GAP))
			else:
				follow.erase(who_f)
		"water":
			var ws: Node2D = world.stage(str(st.get("room", world.room)))
			if ws != null:
				var wsec := 0.0 if ff else float(st.get("sec", 1.5))
				if st.get("wait", true) and wsec > 0.0:
					await ws.set_water(float(st.get("y", ws.water_y())), wsec)
				else:
					ws.set_water(float(st.get("y", ws.water_y())), wsec)
		"closeup":
			var zr: String = await closeup(st)
			for z in st.get("zones", []):
				if str(z.get("id", "")) == zr and str(z.get("scene", "")) != "":
					return str(z["scene"])
		"elephant_call":
			await _elephant_call(st)
		"drawing_closeup":
			if not ff:
				var tp := "res://art/forest_story/drawing_closeup.png"
				if ResourceLoader.exists(tp):
					var sec := float(st.get("sec", 2.5))
					if auto != "":
						sec = minf(sec, 1.2)
					_ui_shot("closeup", 0.75)
					await dlg.closeup(load(tp), sec)
		"treeline_match":
			if not ff:
				await _treeline_match()
		"journal_mark":
			var mm := str(st.get("match", ""))
			if StoryState.mark(mm) == 0:
				_warn_once("journal_mark：日记里没有含「%s」的条目" % mm)
			if not ff and not st.has("sfx"):
				_sfx({"name": "pen_write", "db": -8.0})
		"journal_strike":
			var m := str(st.get("match", ""))
			if StoryState.strike(m) == 0:
				_warn_once("journal_strike：日记里没有含「%s」的条目" % m)
			if not ff:
				if not st.has("sfx"):
					_sfx({"name": "pen_strike", "db": -4.0})
				dlg.toast(Inventory.icon("journal"), I18n.t("journal_struck"))
		"count":
			var c := 0
			for f in st.get("flags", []):
				if StoryState.has(str(f)):
					c += 1
			if c >= int(st.get("at_least", 1)) and st.has("set"):
				StoryState.set_flag(str(st["set"]))
		"fuel":
			_fuel_step(st)
		"camera":
			await _camera(st)
		"phone_add", "phone_msg", "phone_send", "phone_open", "phone_draft":
			await phone.step(st)
		"debris_steer", "keepsake_choice", "cockpit_dash":
			var cs2: String = await _cockpit_step(d, st)     # 驾驶舱的两个小玩法（cockpit_debris.gd / cockpit_keepsake.gd）
			return cs2
		_:
			_warn_once("不认识的步骤：" + JSON.stringify(st))
	return ""


## 飞行段燃料表（左上角「现在 / 需要」，StoryState.fuel / fuel_need）：
##   {"do": "fuel", "have": 200, "need": 200}  设两个数（起飞时满的）；{"do": "fuel", "need": 255}  只改需要的量（改航线）
##   {"do": "fuel", "burn": "blue_stone"}  加这件东西的 keepsake_burn（没有就用 burn）；{"do": "fuel", "add": n} / "sub": n
##   燃料最多到「需要的量」（放进去的比缺口多，表也只到满）。纪念品卡片上不标燃料值，差多少只看这张表。
func _fuel_step(st: Dictionary) -> void:
	var was := StoryState.fuel()
	var need_was := StoryState.fuel_need()
	var have := was
	var need := -1
	if st.has("need"):
		need = int(st["need"])
	if st.has("have"):
		have = int(st["have"])
	if st.has("burn"):
		have += fuel_of(str(st["burn"]))
	have += int(st.get("add", 0)) - int(st.get("sub", 0))
	if need < 0 and not StoryState.fuel_on():
		need = maxi(have, 0)
	StoryState.set_fuel(have, need)
	level.fuel_changed(was, need_was)


## 一件东西放进转化装置给多少燃料（纪念品 keepsake_burn，材料 burn）
static func fuel_of(id: String) -> int:
	var it := Inventory.item(id)
	return int(it.get("keepsake_burn", it.get("burn", 0)))


## 驾驶舱步骤：建那个界面（挂在对话界面下，按键先到它那里），等它播完；返回要跳去的 scene（"" = 接着播）
func _cockpit_step(kind: String, st: Dictionary) -> String:
	if world.cockpit == null:
		_warn_once("%s：剧本 rooms 里没有 cockpit，跳过" % kind)
		return ""
	var n: Control = (load(COCKPIT_STEPS[kind]) as GDScript).new()
	n.name = kind
	dlg.add_child(n)
	cockpit_ui = n
	var r: String = await n.play(self, st)
	cockpit_ui = null
	n.queue_free()
	return r


func _wait(sec: float) -> void:
	var t := 0.0
	while t < sec:
		await get_tree().process_frame
		t += get_process_delta_time()


# ----------------------------------------------------------------------- 说话
func _say(st: Dictionary) -> void:
	lines += 1
	if ff:
		return
	if st.get("bark", false):
		bark.push(txt(st), bool(st.get("added", false)) and mark_added)    # 头顶小气泡，不等
		return
	var who := str(st["say"])
	var tl := txt_lang(st)
	var text: String = tl[0]
	speaking = who
	var n := npc(who)
	# 别人说话时，站着的晨转过去看说话的人
	if n != null and n != chen and n.visible and chen._vel <= 0.0:
		chen._set_facing(1 if n.position.x > chen.position.x else -1)
	var nm := txt_in(speakers.get(who, who), str(tl[1]))
	var gn: Node2D = n if n != null and npcs.values().has(n) else null
	if gn != null:
		gn.talk(true)
	await dlg.say(nm, NAME_COLORS.get(who, UITheme.ACCENT), text, _anchor.bind(who), bool(st.get("added", false)) and mark_added)
	if gn != null and is_instance_valid(gn):
		gn.talk(false)
	speaking = ""
	if _item_show != null and _item_show_until_say:
		_drop_item_show()


func _anchor(who: String) -> Vector2:
	if world.treeline_view_shown():
		return TREELINE_VIEW_ANCHOR             # 树冠缺口那一屏：框放在画面下方居中，不挡凹口
	var left: Vector2 = level.cam_left()
	var n := npc(who)
	if n != null and n.visible:
		var hd := float(n.head) if npcs.values().has(n) else float(HEAD.get(who, 50.0))
		return n.position - left + Vector2(0, -hd)
	# 画面外的声音：树屋在屏幕里就从门那边来（屋里的人隔着门说话），不然屏幕上方中间
	if not world.in_room() and world.stages.is_empty():
		var dx: float = float(world.house["door"]) - left.x
		if dx > 30.0 and dx < 450.0:
			return Vector2(dx, float(world.house["floor"]) - left.y - 44.0)
	return Vector2(240, 44 if not level.bars_on() else 44 + level.BAR_H)


func _narr(st: Dictionary) -> void:
	lines += 1
	if ff:
		return
	var text := txt(st["narr"])
	await dlg.narr(text, clampf(0.9 + text.length() * 0.08, 1.4, 3.0))


# ----------------------------------------------------------------------- 走 / 转身 / 出现
## to → {ok, x, room}：marker / 物件 / 数字 / 角色名（走到那个角色旁边）
func _resolve(to, who := "chen") -> Dictionary:
	if to is String:
		var n := npc(str(to))
		if n != null:
			var me := npc(who)
			var side := -1.0 if me == null or me.position.x < n.position.x else 1.0
			return {"ok": true, "x": n.position.x + side * 24.0, "room": world.room}
	var r: Dictionary = world.resolve(to)
	if not r["ok"]:
		_warn_once("找不到位置：" + str(to))
	return r


func _walk(st: Dictionary) -> void:
	var who := str(st.get("who", "chen"))
	var r := _resolve(st.get("to", 0), who)
	if not r["ok"]:
		return
	var x: float = r["x"]
	var n := npc(who)
	if n == null:
		_warn_once("walk：不认识 " + who)
		return
	var tlv := _lv_target(st.get("to", 0), n)
	x = _no_pass_chen(n, x, tlv)
	x = _clear_x(n, x, world.room if n == chen else _room_of(n), tlv, n.position.x, n == chen)    # 人和人不叠（晨走过去时跟着的人自己让）
	if ff:
		_place(n, x, world.room if n == chen else _room_of(n), tlv)
		return
	var wait: bool = st.get("wait", true)
	var lsg := _lv_stage()
	if lsg != null and tlv >= 0 and tlv != _lv_of(n, lsg) and not (who == "chen" and _enter_scene):
		# 多层小屋：目标在别的层 → 先沿石阶走上 / 下去，再走到那一点
		if wait:
			await _lv_walk(n, lsg, tlv, x, st)
		else:
			_lv_walk(n, lsg, tlv, x, st)
		return
	match who:
		"chen":
			if _enter_scene:
				return                       # 不推人：走进来触发的剧情不让晨自己走（停在看得见的边上）
			if st.has("speed"):
				_warn_once("walk：晨的 speed 不支持（晨的速度在 chen.gd 里，不改），按平常速度走")
			var w: Vector2 = world.walls(chen.position.x)
			x = clampf(x, w.x + 4.0, w.y - 4.0)
			_chen_goal = x                       # 还在走的时候别人按这里躲（_clear_blocks）；走到了在 _chen_walk 里清掉
			if str(st.get("pace", "")) == "walk":
				# "pace": "walk"（10-29）：走路的速度，慢慢起步、慢慢停（level_forest.gd 的 stroll_to；动画照旧 100ms 一帧）
				if wait:
					await level.stroll_to(x)
				else:
					level.stroll_to(x)
			elif wait:
				await _chen_walk(x)
			else:
				_chen_walk(x)
		"deer":
			deer.visible = true
			_deer_go(x, st)
			while wait and _deer_moving():
				await get_tree().process_frame
		_ when npcs.values().has(n):
			n.visible = true
			var nsp := float(st.get("speed", -1.0))
			if nsp <= 0.0:
				nsp = float(n.get("speed"))
			if wait and not ff:
				# 晨被锁着等人走路：一段最多等 WALK_WAIT_MAX 秒，远的就走快一点（最多快到 WALK_HURRY 倍，不会嗖地飞过去）
				nsp = clampf(absf(x - n.position.x) / WALK_WAIT_MAX, nsp, nsp * WALK_HURRY)
			n.walk_to(x, nsp)
			while wait and n.is_walking():
				await get_tree().process_frame
		_:
			miluo.visible = true
			miluo.glide_to(x, float(st.get("speed", miluo.GLIDE_SPEED)))
			while wait and miluo.is_gliding():
				await get_tree().process_frame


## 多层小屋（room.json levels，妮芙家）：现在这间是多层的就返回它
func _lv_stage(r := "") -> Node2D:
	var sg: Node2D = world.stage(r if r != "" else world.room) if world != null else null
	return sg if sg != null and sg.has_method("has_levels") and sg.has_levels() else null


func _lv_of(n: Node2D, sg: Node2D) -> int:
	return int(sg.chen_lv) if n == chen else int(sg.npc_lv.get(n.name, sg.chen_lv))


## walk / show 的目标在哪层：marker 的层、或那个人所在的层；不是多层 = −1
func _lv_target(to, n: Node2D = null) -> int:
	if not to is String:
		return -1
	var tn := npc(str(to))
	var sg := _lv_stage(_room_of(n) if n != null and n != chen else "")
	if sg == null:
		sg = _lv_stage()
	if sg == null:
		return -1
	if tn != null and tn != n:
		return _lv_of(tn, sg)
	return sg.marker_level(str(to))


## 沿石阶换层再走到 x（晨 / NPC）。石阶上 = 脚底跟着斜线走（没有爬楼梯的帧，走路动画 + 平滑位移）
func _lv_walk(n: Node2D, sg: Node2D, to_lv: int, x: float, st := {}) -> void:
	if n == chen and not missing_anims.has("climb"):
		missing_anims["climb"] = true            # 上下石阶：没有爬楼梯的帧，先用走路 + 沿斜线位移（给奥斯卡的清单）
		print("MISSING_ANIM climb")
	n.set_meta("lv_climbing", true)
	var sp := float(st.get("speed", -1.0))
	if sp <= 0.0 and n != chen:
		sp = maxf(float(n.get("speed")), 56.0)      # 换层的路远：妮芙飘得快一点（剧本没写速度时）
	var route: Array = sg.route(_lv_of(n, sg), to_lv)
	if n != chen and st.get("wait", true) and not ff:
		# 晨被锁着等人上下楼：整段路（到楼梯口、楼梯、到目标）最多等 WALK_WAIT_MAX + 1 秒，远的就快一点（最多 WALK_HURRY 倍）
		var px := n.position.x
		var path_len := 0.0
		for e in route:
			path_len += absf(float(e["x0"]) - px) + absf(float(e["x1"]) - float(e["x0"]))
			px = float(e["x1"])
		path_len += absf(x - px)
		sp = clampf(path_len / (WALK_WAIT_MAX + 1.0), sp, sp * WALK_HURRY)
	for e in route:
		if n == chen:
			await _chen_walk(float(e["x0"]))
			sg.chen_stair = int(e["si"])
			await _chen_walk(float(e["x1"]))
			sg.chen_stair = -1
			sg.chen_lv = int(e["to"])
		else:
			n.visible = true
			n.walk_to(float(e["x0"]), sp)
			while n.is_walking():
				await get_tree().process_frame
			n.ground_fn = sg.stair_fn(int(e["si"]))
			n.walk_to(float(e["x1"]), sp)
			while n.is_walking():
				await get_tree().process_frame
			sg.npc_lv[n.name] = int(e["to"])
			n.ground_fn = sg.level_fn(int(e["to"]))
	n.remove_meta("lv_climbing")
	if n == chen:
		var w: Vector2 = world.walls(chen.position.x)
		await _chen_walk(clampf(x, w.x + 4.0, w.y - 4.0))
	else:
		n.walk_to(x, sp)
		while n.is_walking():
			await get_tree().process_frame


## 点了别的层的 hotspot（鼠标 / 自动玩）：先走上 / 下去，到那一层的楼梯口为止，再播它的剧情
func _lv_reach(p: Dictionary) -> void:
	var sg := _lv_stage()
	var at = (p["h"] as Dictionary).get("at", 0)
	var tlv := _lv_target(at)
	if sg == null or tlv < 0 or tlv == sg.chen_lv or ff:
		return
	busy = true
	hotspots.active = false
	level.story_begin(false)
	await _lv_walk(chen, sg, tlv, float(p["x"]))
	level.story_end()
	busy = false
	hotspots.active = true


## 鹿：剧本 speed ≤ 60 = 走路（npc_deer.gd 的 walk_to，不传速度：它自己的 WALK_SPEED 是蹄子不打滑的唯一速度），
## 不然跑（run_to）；没有 walk_to 就都跑
func _deer_go(x: float, st: Dictionary) -> void:
	var sp := float(st.get("speed", deer.RUN_SPEED))
	if sp <= 60.0 and deer.has_method("walk_to"):
		deer.call("walk_to", x)
	else:
		deer.run_to(x, sp)


func _deer_moving() -> bool:
	if deer.has_method("is_walking") and bool(deer.call("is_walking")):
		return true
	return deer.is_running()


func _chen_walk(x: float) -> void:
	var t := 0.0
	var dir := signf(x - chen.position.x)
	while dir != 0.0:
		var d := x - chen.position.x
		if absf(d) <= 2.0 + chen.stop_distance() or signf(d) != dir:
			break
		if level.player_free():
			break                            # 过场播完了（walk 带 wait:false 的还没走到）：松手，绝不推着玩家走
		chen.auto_dir = dir
		await get_tree().process_frame
		t += get_process_delta_time()
		if t > 20.0:
			chen.position.x = x
			break
	chen.auto_dir = 0.0
	_chen_goal = NAN
	t = 0.0
	while chen._vel > 0.0 and t < 1.0:
		await get_tree().process_frame
		t += get_process_delta_time()


func _face(st: Dictionary) -> void:
	var n := npc(str(st.get("who", "chen")))
	if n == null:
		return
	var to = st.get("to", 0)
	var tx := 0.0
	var tn := npc(str(to)) if to is String else null
	if tn != null:
		tx = tn.position.x
	else:
		var r: Dictionary = world.resolve(to)
		if not r["ok"]:
			_warn_once("face：找不到 " + str(to))
			return
		tx = r["x"]
	if absf(tx - n.position.x) < 1.0:
		return
	n._set_facing(1 if tx > n.position.x else -1)


func _show(st: Dictionary, on: bool) -> void:
	var who := str(st.get("who", ""))
	var n := npc(who)
	if n == null:
		world.set_prop(who, "show" if on else "hidden")     # 引擎扩展：物件也能 show / hide
		return
	if st.has("at"):
		var r: Dictionary = world.resolve(st["at"])
		if r["ok"]:
			var slv := _lv_target(st["at"], n) if _lv_stage(str(r["room"])) != null else -1
			_place(n, _clear_x(n, r["x"], str(r["room"]), slv), r["room"], slv)     # 人和人不叠
		else:
			_warn_once("show：找不到 " + str(st["at"]))
	# "fade": 秒（10-29）：按 4 档透明度淡入 / 淡出（鹿走进雾里、慢慢出现），不突然出现 / 消失；不等它淡完就播下一步
	var fade := 0.0 if ff else float(st.get("fade", 0.0))
	if n.has_meta("vis_tw"):
		var old = n.get_meta("vis_tw")
		if old is Tween and (old as Tween).is_valid():
			(old as Tween).kill()
		n.remove_meta("vis_tw")
		n.modulate.a = 1.0
	if fade > 0.0 and not on and n.visible:
		var tw := create_tween()
		n.set_meta("vis_tw", tw)
		tw.tween_method(func(a: float): n.modulate.a = ceilf(a * 4.0) / 4.0, 1.0, 0.0, fade)
		tw.tween_callback(func():
			n.visible = false
			n.modulate.a = 1.0
			n.remove_meta("vis_tw"))
		return
	var was := n.visible
	n.visible = on
	sync_npc_vis(true)
	if fade > 0.0 and on and not was and n.modulate.a > 0.0:
		var tw2 := create_tween()
		n.set_meta("vis_tw", tw2)
		n.modulate.a = 0.0
		tw2.tween_method(func(a: float): n.modulate.a = floorf(a * 4.0) / 4.0, 0.0, 1.0, fade)
		tw2.tween_callback(func(): n.remove_meta("vis_tw"))


## fade_to 的 "place": {"deer": marker, …}：换地方的同时（黑着的时候 / 进出屋前墙还挡着的时候）把这些人放到位、显示出来，
## 淡入以后不会凭空冒出来
func _fade_place(st: Dictionary) -> void:
	var pl = st.get("place", {})
	if not pl is Dictionary:
		return
	for who in pl:
		_show({"who": str(who), "at": pl[who]}, true)


func _room_of(n: Node2D) -> String:
	return str(_npc_room.get(n.name, "forest"))


## 弥洛和树屋前墙的前后（10-29）：前墙本来就画在弥洛前面一格（屋里的她被前墙盖住）。
##   在屋里 = 前墙后面；在屋外 = 前墙前面（从屋前走过不会被墙吞掉）；往屋里走（滑向前墙范围里的点）= 前墙后面
##   （从屋子边上绕到后面去，被墙一点点挡住）。只在她和前墙不重叠、或者前墙透明（在屋里）的时候换，换的那一下看不出来。
const MILUO_HALF := 16.0            # 弥洛半宽（帧宽 31，留一点）
var _miluo_front := false


func _update_miluo_layer() -> void:
	if miluo == null or world == null or not world.house.has("front_x0"):
		return
	var want := _miluo_front
	var x := miluo.position.x
	if _room_of(miluo) == "treehouse":
		want = false
	elif miluo.is_gliding():
		want = not world.behind_front(float(miluo._glide_x))
	elif not world.behind_front(x):
		want = true
	if want == _miluo_front:
		return
	if ff or not miluo.visible or not world.overlaps_front(x, MILUO_HALF) or world.house_front.modulate.a < 0.05:
		_set_miluo_front(want)


func _set_miluo_front(on: bool) -> void:
	_miluo_front = on
	var hf: Node2D = world.house_front
	if hf.get_parent() != miluo.get_parent():
		return
	var i := miluo.get_index()
	var j := hf.get_index()
	if on and i < j:
		level.move_child(miluo, j)          # 前墙挪到她后面一格
	elif not on and i > j:
		level.move_child(miluo, j)


## 把角色直接放到 x（房间 r 的地面上），停掉正在跑 / 滑
## lv：多层小屋里放到哪层（−1 = 晨留在原来那层、NPC 放在晨现在那层）
func _place(n: Node2D, x: float, r: String, lv := -1) -> void:
	if n == deer and _deer_moving():
		deer._running = false
		if "_walking" in deer:
			deer.set("_walking", false)
		deer._idle(2.0)
	if n == miluo and miluo.is_gliding():
		miluo._gliding = false
	if n == chen:
		chen.auto_dir = 0.0
		chen._vel = 0.0
	if npcs.values().has(n):
		n.stop()
		n.ground_fn = func(gx: float) -> float: return world.ground_at(gx, r)
	var ls := _lv_stage(r)
	if ls != null:
		if lv < 0 and n == chen and _arrive_lv >= 0:
			lv = _arrive_lv
		if lv < 0:
			lv = ls.chen_lv
		if n == chen:
			ls.chen_lv = lv
			ls.chen_stair = -1
		elif npcs.values().has(n):
			ls.npc_lv[n.name] = lv
			n.ground_fn = ls.level_fn(lv)
	var gy: float = world.ground_at(x, r) if ls == null or n == chen else ls.level_fn(lv).call(x)
	n.position = Vector2(round(x), round(gy) + 1.0)
	_npc_room[n.name] = r
	if n == miluo and world.house.has("front_x0"):
		_set_miluo_front(r != "treehouse" and not world.behind_front(round(x)))    # 直接放过去的：图层也直接对


## 屋里屋外：和晨不在同一边、又站在树屋图范围里的角色淡掉（晨进屋时屋外门口的鹿；晨在屋外时屋里的弥洛本来就被前墙挡着）
func sync_npc_vis(instant := false) -> void:
	_sync_generic_vis(instant)
	for n in [deer, miluo]:
		var nd: Node2D = n
		var away: bool = _room_of(nd) != world.room and world.in_house_span(nd.position.x)
		var a := 0.0 if away and world.in_room() else 1.0
		# 上一次还没淡完的先停掉（10-29：进屋时先淡掉、紧接着 fade_to 的 place 把人放进屋，旧的 tween 会把人又淡没）
		var old = nd.get_meta("sync_tw") if nd.has_meta("sync_tw") else null
		if old is Tween and (old as Tween).is_valid():
			(old as Tween).kill()
		if instant or ff:
			nd.modulate.a = a
		elif not is_equal_approx(nd.modulate.a, a):
			var tw := create_tween()
			tw.tween_property(nd, "modulate:a", a, 0.5)
			nd.set_meta("sync_tw", tw)


## 晨的动作别名表（data/chen_anim_alias.json：剧本动作名 → ANIMS 里的段名，对照 docs/给美术姐和奥斯卡的需求.md 第一节）
func chen_alias() -> Dictionary:
	if _chen_alias == null:
		_chen_alias = {}
		if FileAccess.file_exists(CHEN_ALIAS):
			var d = JSON.parse_string(FileAccess.get_file_as_string(CHEN_ALIAS))
			if d is Dictionary:
				_chen_alias = d
	return _chen_alias


## 剧本要晨做 name：实际播哪段（原名有就原名，没有看别名表指的那段）；都没有 = ""
func chen_anim(name: String) -> String:
	if chen.spr.sprite_frames.has_animation(StringName(name)):
		return name
	var a := str(chen_alias().get(name, ""))
	if a != "" and not name.begins_with("_") and chen.spr.sprite_frames.has_animation(StringName(a)):
		return a
	return ""


func _anim(st: Dictionary) -> void:
	if ff:
		return
	var who := str(st.get("who", ""))
	var name := str(st.get("name", ""))
	if _wood_mode and who == "chen" and name == "pickup":
		return                    # 过场里已经弯过腰了
	var n := npc(who)
	var key := "miluo" if n == miluo else who
	var m: Dictionary = ANIM_MAP.get(key, {})
	if n == chen and n != null and not m.has(name):
		# 晨：chen.gd 的 ANIMS 里有同名的段就直接播（奥斯卡画好加进去就能用）；没有看别名表（data/chen_anim_alias.json）；
		# 都没有就退回待机，记下来给奥斯卡（帧速照旧 100ms）
		var an := chen_anim(name)
		if an != "":
			chen.spr.play(StringName(an))
			return
		if not missing_anims.has(name):
			missing_anims[name] = true
			print("MISSING_ANIM " + name)
		if chen._vel <= 0.0:
			chen.spr.play(&"idle")
		return
	if n != null and npcs.values().has(n):
		if not n.play(name):
			var key2 := "%s.%s" % [who, name]
			if not missing_anims.has(key2):
				missing_anims[key2] = true
				print("MISSING_ANIM " + key2)
		return
	if n == null or not m.has(name):
		_warn_once("anim：%s 没有 %s" % [who, name])
		return
	var spr: AnimatedSprite2D = n.spr
	if spr.sprite_frames.has_animation(StringName(m[name])):
		spr.play(StringName(m[name]))


# ----------------------------------------------------------------------- 物品 / 日记 / 声音
func _give(id: String) -> void:
	if _wood_mode and Inventory.has(id):
		return                    # 木头拾取过场已经给过了
	if not Inventory.defined(id):
		_warn_once("物品表里没有 %s（用色块占位）" % id)
		Inventory.register_fallback({"id": id, "name": {"zh": id, "en": id}, "rarity": "common", "burn": 0, "personal": true,
			"desc": {"zh": "", "en": ""}})
	Inventory.add(id)
	level.on_inventory_changed()
	if ff:
		return
	var it := Inventory.item(id)
	var icon := Inventory.icon(id)
	dlg.toast(icon, I18n.t("got_item") % txt(it.get("name", id)))
	await _fly_to_bag(icon, chen.position + Vector2(0, -36) - level.cam_left())


func _take(id: String) -> void:
	if not Inventory.has(id):
		_warn_once("take：背包里没有 " + id)
	Inventory.remove(id)
	level.on_inventory_changed()
	if not ff:
		dlg.toast(Inventory.icon(id), I18n.t("gave_item") % txt(Inventory.item(id).get("name", id)))


func _fly_to_bag(icon: Texture2D, from: Vector2) -> void:
	var tr := TextureRect.new()
	tr.texture = icon
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tr.position = from.round()
	dlg.add_child(tr)
	var to: Vector2 = level.bag_target() - icon.get_size() / 2.0
	var tw := create_tween()
	tw.tween_property(tr, "position:y", from.y - 12.0, 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_method(func(k: float):
		var p := Vector2(from.x, from.y - 12.0).lerp(to, k)
		p.y -= sin(k * PI) * 16.0
		tr.position = p.round(), 0.0, 1.0, 0.5).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	await tw.finished
	tr.queue_free()
	level.bag_bump()


func _journal(st: Dictionary) -> void:
	var e := {"zh": str(st.get("zh", "")), "en": str(st.get("en", ""))}
	if st.has("tag"):
		e["tag"] = str(st["tag"])
	StoryState.add_journal(e)
	if not ff and not st.has("sfx"):
		_sfx({"name": "pen_write", "db": -6.0})
	if not Inventory.has("journal"):
		if not Inventory.defined("journal"):
			Inventory.register_fallback({"id": "journal", "name": {"zh": "日记", "en": "Journal"}, "rarity": "common",
				"burn": 0, "personal": true, "icon": "res://art/forest_story/icon_journal.png", "desc": {"zh": "", "en": ""}})
		Inventory.add("journal")
		level.on_inventory_changed()
	if not ff:
		dlg.toast(Inventory.icon("journal"), I18n.t("journal_added"))


func _sfx(st: Dictionary) -> void:
	if ff:
		return
	var name := str(st.get("name", ""))
	var p := _sfx_path(name)
	if p == "":
		missing_sfx[name] = true       # 缺的音效静默跳过（统计里列出来）
		return
	# 音乐盒 / 留声机这一族（长声）：新的一条开始时，同族还在响的淡出 0.4 秒，免得叠在一起
	var fam := _sfx_family(name)
	if fam:
		fade_music_family()
	_sfx_t[name] = Time.get_ticks_msec()
	var a := AudioStreamPlayer2D.new()
	a.stream = load(p)
	a.bus = "SFX"
	a.max_distance = 2000.0
	a.attenuation = 0.5
	a.volume_db = float(st.get("db", 0.0))
	level.add_child(a)
	a.global_position = level.cam_left() + Vector2(240.0 + clampf(float(st.get("pan", 0.0)), -1.0, 1.0) * 320.0, 135.0)
	a.play()
	a.finished.connect(a.queue_free)
	if fam:
		_family.append(a)


static func _sfx_family(name: String) -> bool:
	return name.begins_with("musicbox_") or name.begins_with("gramophone_")


## 音乐盒 / 留声机这一族还在响的全部淡出（新的一条开始、离开树屋时）
func fade_music_family(sec := 0.4) -> void:
	for a in _family:
		if is_instance_valid(a) and (a as AudioStreamPlayer2D).playing:
			var tw := create_tween()
			tw.tween_property(a, "volume_db", -60.0, sec)
			tw.tween_callback((a as Node).queue_free)
	_family.clear()


## 循环环境声：放在 marker 上的 AudioStreamPlayer2D（镜头是听的人：越远越小、左右跟着方位）。没有文件就只记下来、不响。
func _ambient_step(st: Dictionary) -> void:
	var name := str(st.get("name", ""))
	var key := name + "@" + str(st.get("at", ""))
	var on: bool = st.get("on", true)
	if not on:
		if _ambient.has(key):
			var a: AudioStreamPlayer2D = _ambient[key]
			var tw := create_tween()
			tw.tween_property(a, "volume_db", -60.0, 0.8)
			tw.tween_callback(a.queue_free)
			_ambient.erase(key)
		return
	if ff or _ambient.has(key):
		return
	var p := _sfx_path(name)
	if p == "":
		missing_sfx[name] = true
		return
	var r: Dictionary = world.resolve(st.get("at", 0))
	var a := AudioStreamPlayer2D.new()
	a.stream = load(p)
	a.bus = "SFX"
	a.max_distance = float(st.get("dist", 520.0))
	a.attenuation = 1.6
	a.volume_db = float(st.get("db", 0.0))
	level.add_child(a)
	a.global_position = Vector2(float(r.get("x", 0.0)), 200.0)
	a.finished.connect(a.play)       # 循环（.import 里已经设了 loop 的音效不会发 finished，这句就不起作用，也没关系）
	a.play()
	_ambient[key] = a


func _sfx_path(name: String) -> String:
	for ext in [".wav", ".ogg", ".mp3"]:
		if ResourceLoader.exists(SFX_DIR + name + ext):
			return SFX_DIR + name + ext
	return ""


## 晨把一件东西举起来给人看：图标在晨头顶前方，到下一句说完（或 sec 秒）
func _show_item(st: Dictionary) -> void:
	if ff:
		return
	_drop_item_show()
	var id := str(st.get("item", ""))
	var tr := TextureRect.new()
	tr.texture = Inventory.icon(id)
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dlg.add_child(tr)
	_item_show = tr
	_item_show_until_say = not st.has("sec")
	tr.set_meta("t", 0.0)
	if st.has("sec"):
		var me := tr
		get_tree().create_timer(float(st["sec"])).timeout.connect(func():
			if _item_show == me:
				_drop_item_show())


func _drop_item_show() -> void:
	if _item_show != null and is_instance_valid(_item_show):
		_item_show.queue_free()
	_item_show = null


func _update_item_show(delta: float) -> void:
	if _item_show == null or not is_instance_valid(_item_show):
		return
	var t: float = float(_item_show.get_meta("t")) + delta
	_item_show.set_meta("t", t)
	var sz := _item_show.texture.get_size()
	var left: Vector2 = level.cam_left()
	var head: Vector2 = chen.position - left + Vector2(chen.facing * 12.0, -34.0)
	var lift := minf(t / 0.2, 1.0) * 6.0
	_item_show.position = (head - Vector2(sz.x / 2.0, sz.y + lift)).round()


# ----------------------------------------------------------------------- 换地方
var _arrive_lv := -1                 # fade_to 进多层小屋：晨（和同行的）落在 at 那个 marker 的层


func _fade_to(st: Dictionary) -> void:
	var room := str(st.get("room", "forest"))
	var lsg := _lv_stage(room)
	_arrive_lv = lsg.marker_level(str(st.get("at", ""))) if lsg != null and st.get("at", 0) is String else -1
	var r: Dictionary = world.resolve(st.get("at", 0))
	if not r["ok"]:
		_warn_once("fade_to：找不到 " + str(st.get("at")))
		return
	var x: float = r["x"]
	var arrive := NAN
	if st.has("arrive"):
		var ar: Dictionary = world.resolve(st["arrive"])
		if ar["ok"]:
			arrive = float(ar["x"])
	for w0 in st.get("with", []):
		if npcs.has(str(w0)):
			follow[str(w0)] = float(follow.get(str(w0), FOLLOW_GAP))     # 同行 = 到了以后跟着晨
	if ff:
		_teleport(room, x, st.get("with", []), true)
		_fade_place(st)
		if not is_nan(arrive):
			_place(chen, arrive, room)
		return
	if world.is_stage(room) or world.is_stage(world.room):
		if await _stage_fade(st, room, x, arrive):
			return                         # 小屋前墙 / 竖直平移 / 边走边黑做完了；fade 和带 leave / cam 的走下面原来的
	# 进屋 / 出屋（树屋就在森林里）：不黑屏，前墙淡出 / 淡入
	var door: bool = room != world.room and (room == "treehouse" or world.room == "treehouse") \
		and world.near_house(x) and world.near_house(chen.position.x)
	if door:
		_teleport(room, x, st.get("with", []), false)
		_fade_place(st)
		await _wait(0.55)
		return
	var out_sec := 0.5
	if st.has("leave"):
		# 边走边黑：晨（和 with 里的人）朝 leave 那边一直走，黑透了再换地方（离开，不是原地消失）
		var lr: Dictionary = world.resolve(st["leave"])
		if lr["ok"]:
			out_sec = 0.8
			chen.auto_dir = signf(float(lr["x"]) - chen.position.x)
	await level.fade_to_black(out_sec)
	chen.auto_dir = 0.0
	_teleport(room, x, st.get("with", []), true)
	_fade_place(st)
	if st.has("cam"):
		# 镜头停在 cam 这里不跟晨（晨从画面外走进来）；camera release 步骤或这个 scene 播完放开
		var cr: Dictionary = world.resolve(st["cam"])
		if cr["ok"]:
			level.camera_hold_at(Vector2(float(cr["x"]), world_cam_y(room)))
	await _wait(0.25)
	if is_nan(arrive) or _enter_scene:
		await level.fade_from_black(0.5)
		return
	# "arrive": marker（10-29）：淡入的同时晨从 at 走几步到这里（到达，不是凭空站在那）；停稳了才往下播。
	# 只走一小段，走路的速度（level_forest.gd 的 stroll_to），不是过场里把人推着跑
	await _arrive_walk(arrive)


## 黑着的时候晨已经站在入口边上、朝着要走的方向；淡入的同时走几步停住
func _arrive_walk(to: float) -> void:
	if absf(to - chen.position.x) >= 1.0:
		chen._set_facing(1 if to > chen.position.x else -1)
		level._snap_camera()
	level.stroll_to(to)
	await level.fade_from_black(0.5)
	while level.strolling() or chen._vel > 0.0:
		await get_tree().process_frame


## 镜头（10-29）：{"do": "camera", "hold": true} 停在现在的位置不跟晨（让人走出画面）；
## {"do": "camera", "at": marker 或 x, "sec": n} 慢慢移过去停住（sec = 0 直接到）；{"do": "camera", "release": true} 慢慢跟回晨。
## scene 播完、鹿带路放手让晨走的时候都会自动放开。跳节拍时不动镜头。
func _camera(st: Dictionary) -> void:
	if ff:
		return
	if st.get("release", false):
		level.camera_release()
		return
	if st.has("at"):
		var r: Dictionary = world.resolve(st["at"])
		if not r["ok"]:
			_warn_once("camera：找不到 " + str(st["at"]))
			return
		var to := Vector2(float(r["x"]), world_cam_y(str(r.get("room", world.room))))
		var sec := float(st.get("sec", 1.0))
		if sec <= 0.0:
			level.camera_hold_at(to)
		elif st.get("wait", true):
			await level.camera_pan(to, sec)
		else:
			level.camera_pan(to, sec)
		return
	if st.get("hold", false):
		level.camera_hold_at(level.cam.position)


func _teleport(room: String, x: float, with: Array, snap: bool) -> void:
	if world.area_of(x) != world.area_of(chen.position.x) or room != world.room:
		_unreach.clear()                  # 换了一段：之前够不着的点重新算
	if world.room == "treehouse" and room != "treehouse":
		fade_music_family()                 # 出了树屋：留声机 / 音乐盒的长声淡掉
	var old_room: String = world.room
	world.set_room(room, ff)
	var tlv := _arrive_lv if _lv_stage(room) != null else -1
	x = _clear_x(chen, x, room, tlv)          # 人和人不叠：落脚点上站着人就挪开一点
	_place(chen, x, room)
	chen.visible = true
	var w: Vector2 = world.walls(x)
	var off := 0.0
	with = with.duplicate()
	for fw in follow:
		var fnode := npc(str(fw))
		if not with.has(fw) and fnode != null and fnode.visible and world.is_stage(room) and str(_npc_room.get(fnode.name, "")) == old_room:
			with.append(fw)                # 跟着晨的人一起过去
	for who in with:
		var n := npc(str(who))
		if n == null or n == chen:
			continue
		off += _side_gap(n, 30.0)
		var nx := x - off
		if nx < w.x + 10.0:
			nx = x + off
		nx = _clear_x(n, nx, room, tlv)        # 人和人不叠（也躲开房间里站着的人）
		_place(n, nx, room)
		n.visible = true
		n._set_facing(1 if x > nx else -1)
	_arrive_lv = -1
	level.on_room_changed(snap)
	sync_npc_vis(snap)


# ----------------------------------------------------------------------- 鹿带路 / 点选 / 结束
func _guide(st: Dictionary) -> void:
	var r: Dictionary = world.resolve(st.get("to", 0))
	if not r["ok"]:
		_warn_once("guide：找不到 " + str(st.get("to")))
		return
	var x: float = r["x"]
	if ff:
		var side := signf(x - chen.position.x)
		_place(deer, x, world.room)
		deer.visible = true
		_place(chen, x - side * 40.0, world.room)
		return
	deer.visible = true
	_deer_go(x, st)
	if not st.get("wait", true):
		return
	# 不锁晨：这段剧情先停在这里，鹿在前面等；晨走近了再接着播（_process / resume_guide）
	pending_guide = {"x": x}


func _pick(st: Dictionary) -> String:
	var opts: Array = st.get("options", [])
	if opts.is_empty():
		return ""
	var ui: Array = []
	for o in opts:
		var pid := str(o.get("id", ""))
		var key := pid if world.props.has(pid) else pid.trim_prefix("room_")
		var sg_node: Node2D = null
		var sr: String = world.stage_of_prop(pid)
		if sr != "":
			sg_node = world.stage(sr).object(pid)
		ui.append({"label": txt(o.get("label", pid)), "rect": _prop_screen_rect.bind(pid), "node": sg_node if sg_node != null else world.props.get(key, null)})
	var auto_i := -1
	if auto != "" or ff:
		auto_i = _auto_pick(st)
	var i: int = await dlg.pick(ui, auto_i)
	i = clampi(i, 0, opts.size() - 1)
	return str(opts[i].get("scene", ""))


func _prop_screen_rect(pid: String) -> Rect2:
	if world.stage_of_prop(pid) != "":
		var sr: Rect2 = world.prop_rect(pid)
		if sr.size.x > 0:
			sr.position -= level.cam_left()
		return sr
	var key := pid if world.props.has(pid) else pid.trim_prefix("room_")
	if not world.props.has(key) or not (world.props[key] as Sprite2D).visible:
		return Rect2()
	var r: Rect2 = world.prop_rect(key)
	r.position -= level.cam_left()
	return r


## 点选里「对的」那个：选项写了 correct 就是它；不然是 scene 一路 goto 下去不会回到这个点选所在 scene 的那个
func _correct_index(st: Dictionary, here: String) -> int:
	var opts: Array = st.get("options", [])
	if ff and _ff_target != "":
		for i in opts.size():
			var os := str(opts[i].get("scene", ""))
			if _leads_to(os, _ff_target) and not _loops_back(os, here):
				return i
	for i in opts.size():
		if opts[i].get("correct", false):
			return i
	for i in opts.size():
		if not _loops_back(str(opts[i].get("scene", "")), here):
			return i
	return 0


func _loops_back(s: String, here: String) -> bool:
	var seen := {}
	while s != "" and not seen.has(s):
		if s == here:
			return true
		seen[s] = true
		var nxt := ""
		for step in scenes.get(s, []):
			if step is Dictionary and str(step.get("do", "")) == "goto":
				nxt = str(step.get("scene", ""))
		s = nxt
	return false


func _auto_pick(st: Dictionary) -> int:
	var ok := _correct_index(st, _cur_scene)
	if auto == "full" and not ff:
		var opts: Array = st.get("options", [])
		for i in opts.size():
			var key := _cur_scene + ":" + str(i)
			if i != ok and not _wrong_tried.has(key):
				_wrong_tried[key] = true
				return i
	return ok


var ff_hit_end := false              # 跳节拍时碰到了 end_chapter（跳到 launched：跳完直接播起飞）
var ff_stop := false                 # 跳节拍时目标 flag 一设上、那个 scene 播完就停（flight1 一路 goto 到底，不停会跳过头）
var ff_resume := ""                  # 停下的地方：接下来该播的 scene（关卡跳完以后正常播）


func _end_chapter() -> void:
	if ff:
		ff_hit_end = true
		return
	ended = true
	dlg.close_box()
	await level.story_takeoff()
	if level.chapter_next():
		# 接下一章（森林起飞 → 驾驶舱）：关卡带着状态重新载入，不出结束卡
		if auto != "":
			print_stats("STORY_DONE")
		return
	dlg.end_card(I18n.t("to_be_continued"), I18n.t("to_be_continued_sub"), level.get_node("Top"))
	if auto != "":
		await _wait(2.5)
		if shots_dir != "":
			level._save(shots_dir.path_join("%03d_end_card.png" % (_shot_n + 1)))
		print_stats("STORY_DONE")
		get_tree().quit()


# ======================================================================= hotspot
## 鹿带路：晨走到等着的鹿身边了，接着播停下的那段
func guide_ready() -> bool:
	if pending_guide.is_empty() or busy or not pending_guide.has("scene"):
		return false
	return not _deer_moving() and absf(chen.position.x - deer.position.x) <= GUIDE_NEAR and world.room == "forest"


func resume_guide() -> void:
	var p := pending_guide
	pending_guide = {}
	chen._set_facing(1 if deer.position.x > chen.position.x else -1)
	await play(str(p["scene"]), true, int(p["index"]))


## 主线下一个该去的地方：{x, kind, id}（等人的鹿 > 木头 > 会推进剧情的点，先不去换地方的，再按远近）；没有 = {}
func main_target() -> Dictionary:
	if not pending_guide.is_empty() and deer.visible:
		return {"x": deer.position.x, "kind": "guide", "id": "guide"}
	if level.wood_available():
		return {"x": level.WOOD_X, "kind": "wood", "id": "wood"}
	var best: Dictionary = {}
	var bk := INF
	for p in hotspots.available():
		var h: Dictionary = p["h"]
		if hotspots.is_enter(h) or not is_progress_hotspot(h):
			continue
		var k := absf(float(p["x"]) - chen.position.x) + (5000.0 if _exits(str(h.get("scene", ""))) else 0.0)
		if k < bk:
			bk = k
			best = {"x": float(p["x"]), "kind": "hotspot", "id": str(h.get("id", ""))}
	return best


## 卡在一个地方太久：晨小声自言自语一句（剧本 nudge_<id> 的第一句台词；没有就不说）
func _update_nudge(delta: float) -> void:
	if busy or not level.free_play() or auto != "":
		_nudge_t = 0.0
		return
	if StoryState.progress() != _nudge_progress:
		_nudge_progress = StoryState.progress()
		_nudge_t = 0.0
		_nudged.clear()
		return
	_nudge_t += delta
	if _nudge_t < NUDGE_AFTER:
		return
	_nudge_t = NUDGE_AFTER - NUDGE_EVERY
	var hl := _hint_line()
	if not hl.is_empty():
		var key := "hint:" + str(hl.get("zh", ""))
		if not _nudged.has(key):
			_nudged[key] = true
			var who := str(hl.get("who", "chen"))
			var tl := txt_lang(hl)
			dlg.murmur(txt_in(speakers.get(who, who), str(tl[1])), NAME_COLORS.get(who, UITheme.ACCENT), str(tl[0]),
				_anchor.bind(who), bool(hl.get("added", false)) and mark_added)
		return
	var t := main_target()
	if t.is_empty():
		return
	var sid := "nudge_" + str(t["id"])
	if not scenes.has(sid) or _nudged.has(sid):
		return
	_nudged[sid] = true
	for st in scenes[sid]:
		if st is Dictionary and st.has("say"):
			var who := str(st["say"])
			var tl := txt_lang(st)
			dlg.murmur(txt_in(speakers.get(who, who), str(tl[1])), NAME_COLORS.get(who, UITheme.ACCENT), str(tl[0]),
				_anchor.bind(who), bool(st.get("added", false)) and mark_added)
			break


## 跳节拍跳到了最后（launched）：直接播起飞和结束卡
func play_end() -> void:
	busy = true
	level.story_begin(true)
	await _end_chapter()


## 晨按了互动（或自动玩走到了）：播它的 scene
func trigger(p: Dictionary) -> void:
	if free_roam:
		return
	var h: Dictionary = p["h"]
	if not ff and quick.is_quick(h):
		await quick.pickup(p)           # 走过去就捡：不锁人
		return
	var id := str(h.get("id", ""))
	if h.get("once", false):
		StoryState.mark_used(id)
	_visited[id] = StoryState.progress()
	var p0 := StoryState.progress()
	hotspots_used += 1
	await _lv_reach(p)                      # 多层小屋：点的是别的层的东西，先走上 / 下去
	if not ff and absf(float(p["x"]) - chen.position.x) > 2.0:
		chen._set_facing(1 if float(p["x"]) > chen.position.x else -1)
	_enter_scene = hotspots.is_enter(h) and not bool(h.get("cutscene", false))
	var scene := str(h.get("scene", ""))
	if scene == "" and h.has("closeup"):
		busy = true
		hotspots.active = false
		if not ff:
			level.story_begin(false)
			await closeup({"img": str(h["closeup"])})
			level.story_end()
		busy = false
		hotspots.active = true
		return
	var acc: Dictionary = h.get("accepts", {})
	if not acc.is_empty() and not _enter_scene and not _owned_accepted(acc).is_empty():
		# 背包里有它能接受的东西：先弹道具选择条
		busy = true
		hotspots.active = false
		if not ff:
			level.story_begin(false)
		_ui_shot("items", 0.35)
		var it: String = await dlg.choose_item(_bag_items(), I18n.t("just_look"), _auto_item_index(acc))
		busy = false
		if it != "":
			scene = str(acc.get(it, acc.get("_default", "")))
			if scene.begins_with("__mech:"):
				_mech_resolve(scene.trim_prefix("__mech:").split("|")[0], it)
				return
			if scene == "":
				await _engine_line(I18n.t("use_nothing"))
				if not ff:
					level.story_end()
				_visited[id] = StoryState.progress()
				return
	if h.has("_mech"):
		_mech_resolve(str(h["_mech"]), "")       # 小游戏的临时点：不播 scene，告诉等着的小游戏
		return
	_scene_view = _hotspot_view(h) if not ff else ""
	await play(scene, not ff)
	_scene_view = ""
	_enter_scene = false
	_visited[id] = StoryState.progress()
	_visit_gain[id] = StoryState.progress() - p0


## 背包里选中一件按「使用」：用在晨身边那个 hotspot 上
func use_item(item: String) -> void:
	if busy:
		return
	var p: Dictionary = hotspots.nearest(chen.position.x)
	if p.is_empty():
		busy = true
		level.story_begin(false)
		await _engine_line(I18n.t("use_here_nothing"))
		busy = false
		level.story_end()
		return
	var h: Dictionary = p["h"]
	var acc: Dictionary = h.get("accepts", {})
	var scene := str(acc.get(item, acc.get("_default", "")))
	if scene.begins_with("__mech:"):
		hotspots.pressed(p)
		_mech_resolve(scene.trim_prefix("__mech:").split("|")[0], item)
		return
	hotspots.pressed(p)
	chen._set_facing(1 if float(p["x"]) > chen.position.x else -1)
	if scene == "":
		busy = true
		level.story_begin(false)
		await _engine_line(I18n.t("use_nothing"))
		busy = false
		level.story_end()
		return
	_visited[str(h.get("id", ""))] = StoryState.progress()
	await play(scene)


## 换区域（树屋段 ↔ 旧路段的入口）：黑屏换过去。给了 from：晨先站在 from（那一段的入口边上），淡入的同时走几步到 x（到达）
func portal_to(x: float, from := NAN) -> void:
	if busy:
		return
	busy = true
	hotspots.active = false
	level.story_begin(false)
	await level.fade_to_black(0.45)
	_teleport("forest", x if is_nan(from) else from, [], true)
	await _wait(0.2)
	if is_nan(from):
		await level.fade_from_black(0.45)
	else:
		await _arrive_walk(x)
	busy = false
	level.story_end()


## 坠毁后飞船里断续的警报：开着（开场起）/ 晨第一次修飞船或捡到木头以后淡掉
var _alarm_on := false


func alarm(on: bool) -> void:
	if ff or on == _alarm_on:
		return
	_alarm_on = on
	_ambient_step({"name": "alarm_broken", "at": "wreck", "on": on, "db": -8.0})


## 引擎自己的一句（晨说）：道具用不上之类
func _engine_line(text: String) -> void:
	if ff:
		return
	await dlg.say(txt(speakers.get("chen", "chen")), NAME_COLORS["chen"], text, _anchor.bind("chen"))


## accepts 里背包现在有的东西
func _owned_accepted(acc: Dictionary) -> Array:
	var out: Array = []
	for k in acc:
		if str(k) != "_default" and Inventory.has(str(k)):
			out.append(str(k))
	return out


## 道具选择条里列的东西：背包里除了日记的全部
func _bag_items() -> Array:
	var out: Array = []
	for id in Inventory.owned:
		if str(id) == "journal":
			continue
		out.append({"id": str(id), "icon": Inventory.icon(str(id)), "name": txt(Inventory.item(str(id)).get("name", id))})
	return out


## 自动玩 / 跳节拍：用能推进剧情的那件（没有就第一件能接受的）；手动玩 = -1
func _auto_item_index(acc: Dictionary) -> int:
	if auto == "" and not ff:
		return -1
	var items := _bag_items()
	if ff and _ff_target != "":
		for i in items.size():
			var iid := str(items[i]["id"])
			if acc.has(iid) and _leads_to(str(acc[iid]), _ff_target):
				return i
	if auto == "full" and not ff:
		# 全覆盖：先试一次用错的东西（看 _default 的反应）
		for i in items.size():
			var key := "wrongitem:" + str(acc.get("_default", "")) 
			if not acc.has(str(items[i]["id"])) and not _wrong_tried.has(key):
				_wrong_tried[key] = true
				return i
	var best := -1
	for i in items.size():
		var id := str(items[i]["id"])
		if acc.has(id):
			if best < 0:
				best = i
			if _would_progress(str(acc[id]), {}):
				return i
	return best if best >= 0 else items.size()


## 对话选项：晨把选中的那句说出来，再跳到它的 scene
func _choice(st: Dictionary) -> String:
	var opts: Array = st.get("options", [])
	if opts.is_empty():
		return ""
	var lines: Array = []
	for o in opts:
		lines.append(txt(o))
	var ai := -1
	if auto != "" or ff:
		ai = 0
		if ff and _ff_target != "":
			for i in opts.size():
				var os := str(opts[i].get("scene", ""))
				if _leads_to(os, _ff_target) and not _loops_back(os, _cur_scene):
					ai = i
					break
		if auto == "full" and not ff:
			for i in opts.size():
				var key := _cur_scene + ":c" + str(i)
				if not _wrong_tried.has(key) and not played.has(str(opts[i].get("scene", ""))):
					_wrong_tried[key] = true
					ai = i
					break
	_ui_shot("choice", 0.35)
	var i: int = await dlg.choose_line(lines, ai)
	i = clampi(i, 0, opts.size() - 1)
	var o: Dictionary = opts[i]
	lines_said(o)
	if not ff:
		var tl := txt_lang(o)
		await dlg.say(txt_in(speakers.get("chen", "chen"), str(tl[1])), NAME_COLORS["chen"], str(tl[0]), _anchor.bind("chen"),
			bool(o.get("added", false)) and mark_added)
	return str(o.get("scene", ""))


func lines_said(_o: Dictionary) -> void:
	lines += 1


## 远处有东西走过：树冠依次晃 + 低鸣 + 树冠摇的声音左右推过去 + 镜头停住 + 晨抬头
func _elephant_call(st: Dictionary) -> void:
	if ff:
		return
	var v := int(st.get("variant", 1))
	var dir := 1 if v != 2 else -1
	var dur := 3.4
	world.sway_canopy(dir, dur)
	_ui_shot("elephant", 1.5)
	level.cam_hold(dur + 0.8)
	_sfx({"name": "elephant_call_%d" % v})
	var p := _sfx_path("tree_sway")
	if p != "":
		var a := AudioStreamPlayer2D.new()
		a.stream = load(p)
		a.bus = "SFX"
		a.max_distance = 2000.0
		a.attenuation = 0.5
		a.volume_db = -4.0
		level.add_child(a)
		var left: Vector2 = level.cam_left()
		var y := left.y + 135.0
		a.global_position = Vector2(left.x + 240.0 - dir * 320.0, y)
		a.play()
		a.finished.connect(a.queue_free)
		create_tween().tween_property(a, "global_position:x", left.x + 240.0 + dir * 320.0, dur)
	else:
		missing_sfx["tree_sway"] = true
	if chen.spr.sprite_frames.has_animation(&"idle_eye") and chen._vel <= 0.0:
		chen.spr.play(&"idle_eye")
	await _wait(dur + 0.4)


## 树冠缺口那一屏淡入、画上的弧线叠上去对齐、停一下、淡出回到森林
func _treeline_match() -> void:
	if not world.has_treeline_view():
		return
	await world.treeline_view_in(0.9 if auto == "" else 0.4)
	await _wait(0.6 if auto == "" else 0.2)
	var dur: float = world.match_arc(1.8 if auto == "" else 0.8)
	_ui_shot("arc", 0.9)
	await _wait(dur + 0.3)
	await world.treeline_view_out(0.9 if auto == "" else 0.4)
	await _wait(0.3)


## 这个 hotspot 的 scene 要不要在树冠缺口那一屏上播
func _hotspot_view(h: Dictionary) -> String:
	return str(h.get("view", "treeline" if str(h.get("at", "")) == "treeline_gap" else ""))


## 左上角的当前目标：第一个满足条件的 objectives 条目；没有就 {}
func objective() -> Dictionary:
	for o in data.get("objectives", []):
		if o is Dictionary and StoryState.all_of(o.get("need", [])) and StoryState.none_of(o.get("not", [])):
			return o
	return {}


## 闲着太久时晨自言自语的那句：顶层 hints 按 flag 挑
func _hint_line() -> Dictionary:
	var hs = data.get("hints", null)
	if hs == null:
		return {}
	var order := StoryState.flag_order
	var best: Dictionary = {}
	var best_rank := -2
	if hs is Dictionary:
		for f in hs:
			var rank := order.find(str(f))
			if rank < 0 or rank <= best_rank:
				continue
			var v = hs[f]
			var cand: Dictionary = (v[randi() % (v as Array).size()] if v is Array and not (v as Array).is_empty() else v) if (v is Array or v is Dictionary) else {}
			if not cand.is_empty():
				best = cand
				best_rank = rank
	elif hs is Array:
		for e in hs:
			if not e is Dictionary:
				continue
			var ed: Dictionary = e
			if ed.has("flag") and not StoryState.has(str(ed["flag"])):
				continue
			if not StoryState.all_of(ed.get("need", [])) or not StoryState.none_of(ed.get("not", [])):
				continue
			var rank := order.find(str(ed.get("flag", ""))) if ed.has("flag") else -1
			if rank >= best_rank:
				best = ed
				best_rank = rank
	return _hint_pick(best)


## 三章的 hints 都是一条带 "lines": [{zh, en, added?, who?}…]：挑第一句这轮还没说过的；都说过了 = 没有（再去找 nudge_ scene）。
## 没有 lines 的（老写法，zh / en 直接写在条目上）原样返回
func _hint_pick(e: Dictionary) -> Dictionary:
	var ls = e.get("lines", null)
	if not ls is Array:
		return e
	for l in ls:
		if l is Dictionary and not _nudged.has("hint:" + str(l.get("zh", ""))):
			return l
	return {}


## 这个 hotspot 现在去了会不会推进（设新 flag、给新东西、换地方、结束、换物件状态）
func is_progress_hotspot(h: Dictionary) -> bool:
	if _would_progress(str(h.get("scene", "")), {}):
		return true
	var acc: Dictionary = h.get("accepts", {})
	for k in acc:
		if str(k) != "_default" and Inventory.has(str(k)) and _would_progress(str(acc[k]), {}):
			return true
	return false


func _would_progress(s: String, seen: Dictionary) -> bool:
	if seen.has(s) or not scenes.has(s):
		return false
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		match str(st.get("do", "")):
			"flag":
				if st.has("set") and not StoryState.has(str(st["set"])):
					return true
			"give":
				if not Inventory.has(str(st.get("item", ""))):
					return true
			"fade_to", "end_chapter":
				return true
			"goto":
				if _would_progress(str(st.get("scene", "")), seen):
					return true
			"if":
				if _would_progress(str(st.get("then", "")), seen) or _would_progress(str(st.get("else", "")), seen):
					return true
			"choice":
				for o in st.get("options", []):
					if _would_progress(str(o.get("scene", "")), seen):
						return true
			"count":
				if st.has("set") and not StoryState.has(str(st["set"])):
					return true
			"pick":
				for o in st.get("options", []):
					if _would_progress(str(o.get("scene", "")), seen):
						return true
			"keepsake_choice":
				for v in (st.get("scenes", {}) as Dictionary).values():
					if _would_progress(str(v), seen):
						return true
			"mechanic":
				if not bool(mech_load(str(st.get("id", ""))).get("_done", false)):
					return true
				for f in st.get("sets", []):
					if not StoryState.has(str(f)):
						return true
			"closeup":
				for z in st.get("zones", []):
					if _would_progress(str(z.get("scene", "")), seen):
						return true
	return false


## 从 s 出发 goto / if / pick 能到的所有 scene
func _reach(s: String, seen: Dictionary) -> Array:
	if seen.has(s) or not scenes.has(s):
		return seen.keys()
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		match str(st.get("do", "")):
			"goto":
				_reach(str(st.get("scene", "")), seen)
			"if":
				_reach(str(st.get("then", "")), seen)
				_reach(str(st.get("else", "")), seen)
			"pick", "choice":
				for o in st.get("options", []):
					_reach(str(o.get("scene", "")), seen)
			"keepsake_choice":
				for v in (st.get("scenes", {}) as Dictionary).values():
					_reach(str(v), seen)
			"closeup":
				for z in st.get("zones", []):
					_reach(str(z.get("scene", "")), seen)
	return seen.keys()


func _exits(s: String, seen := {}) -> bool:
	if seen.has(s) or not scenes.has(s):
		return false
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		var d := str(st.get("do", ""))
		if d in ["fade_to", "end_chapter"]:
			return true
		if d == "goto" and _exits(str(st.get("scene", "")), seen):
			return true
		if d == "if" and (_exits(str(st.get("then", "")), seen) or _exits(str(st.get("else", "")), seen)):
			return true
	return false


# ======================================================================= 自动玩 / 跳节拍
## 下一个该去的地方：{kind: "wood"|"hotspot", x, p}；空 = 没有
func plan() -> Dictionary:
	var cands: Array = []
	if level.wood_available():
		cands.append({"kind": "wood", "x": level.WOOD_X, "exit": false})
	for p in hotspots.available():
		var h: Dictionary = p["h"]
		var id := str(h.get("id", ""))
		if _visited.has(id) and int(_visited[id]) == StoryState.progress() \
				and not (not world.stages.is_empty() and int(_visit_gain.get(id, 0)) > 0 and is_progress_hotspot(h)):
			continue                                   # 上次来过以后没有新进展：不再来（多房间章节：上次点它有进展、还会有进展的可以接着点）
		if _unreach.has(id) and int(_unreach[id]) == StoryState.progress():
			continue                                   # 刚才够不着
		var prog := is_progress_hotspot(h)
		var to_target := ff and _ff_target != "" and _leads_to(str(h.get("scene", "")), _ff_target)
		if to_target:
			prog = true
		if not prog:
			if auto != "full" or ff or _visited.has(id):
				continue
		cands.append({"kind": "hotspot", "x": float(p["x"]), "p": p, "exit": _exits(str(h.get("scene", ""))) and not to_target, "prog": prog,
			"target": to_target})
	if not world.stages.is_empty():
		var stay := false
		for c in cands:
			if not c["exit"] or c.get("target", false):
				stay = true
		if not stay:
			var mp := _multi_plan()
			if not mp.is_empty():
				return mp
	if cands.is_empty():
		return {}
	var cx := chen.position.x
	var full := auto == "full" and not ff
	cands.sort_custom(func(a, b):
		if a.get("target", false) != b.get("target", false):
			return a.get("target", false)
		if a["exit"] != b["exit"]:
			return not a["exit"]
		# full：同一片先把闲聊都听一遍，再去推进剧情的点
		if full and a.get("prog", true) != b.get("prog", true):
			return not a.get("prog", true)
		return absf(float(a["x"]) - cx) < absf(float(b["x"]) - cx))
	return cands[0]


func _process(delta: float) -> void:
	_game_t += delta
	step_t += delta
	_update_item_show(delta)
	_update_miluo_layer()
	if world.is_stage(world.room) and (deer.visible or miluo.visible):
		deer.visible = false               # 鹿、弥洛是森林的节点：多房间章节（河流篇）里一律不显示
		miluo.visible = false              # （10-30 作者：旧街水里站着一只第一章的鹿）
	_update_follow(delta)
	if _overlap_log and not ff:
		_check_overlap()
	if _alarm_on and (StoryState.has("tried_parts") or StoryState.has("got_wood")):
		alarm(false)
	if not ended and not ff and not free_roam:
		_update_nudge(delta)
		if guide_ready() and level.free_play():
			resume_guide()
			return
	if auto == "" or ended or ff:
		return
	dlg.auto_delay = AUTO_LINE
	if busy:
		_idle_t = 0.0
		_target = {}                 # 剧情开始了（可能是路上踩到的 trigger:"enter"）：播完重新规划
		return
	if not level.free_play():
		_idle_t = 0.0
		_target = {}
		return
	if _target.is_empty() and not pending_guide.is_empty():
		# 鹿在前面等：走过去（走近了 _process 开头会接着播）
		var gx := deer.position.x - signf(deer.position.x - chen.position.x) * 30.0
		if not level.walking() and absf(chen.position.x - deer.position.x) > GUIDE_NEAR - 10.0:
			level.walk_to(gx)
		_idle_t = 0.0
		return
	if _target.is_empty():
		_target = plan()
		_target_t = 0.0
		if not _target.is_empty():
			_target_limit = 8.0 + absf(float(_target["x"]) - chen.position.x) / 90.0
		if not _target.is_empty():
			level.walk_to(float(_target["x"]))
	if _target.is_empty():
		_idle_t += delta
		if _idle_t > 8.0 and pending_guide.is_empty():
			print_stats("STORY_STUCK")
			get_tree().quit(1)
		return
	_idle_t = 0.0
	var tx := float(_target["x"])
	if _target["kind"] == "wood":
		if not level.wood_available():
			_target = {}
		elif absf(chen.position.x - tx) > 30.0 and not level.walking():
			level.walk_to(tx)
		return
	# 走到「站得到的那一点」（被看得见的边挡住就站在边上）；到了在范围里就互动，够不着就先记下、等有进展再来
	_target_t += delta
	var p: Dictionary = _target["p"]
	var h: Dictionary = p["h"]
	if not world.in_room() and world.area_of(tx) != world.area_of(chen.position.x) and _target_t < _target_limit:
		# 在另一段：有走得过去的入口（树屋段往左 = house_return）就一直往那边走；没有就先去「能换过去」的那个点
		var to_area: String = world.area_of(tx)
		var walkable: bool = to_area == "road" and world.markers.has("house_return")
		if not walkable:
			var route := _route_to_area(to_area)
			if not route.is_empty():
				_target = {"kind": "hotspot", "x": float(route["x"]), "p": route, "exit": true}
				_target_t = 0.0
				return
		if not level.walking():
			level.walk_to(tx)
		return
	var lsg := _lv_stage()
	if lsg != null and hotspots.usable(h) and not hotspots.is_enter(h):
		var tlv := _lv_target(h.get("at", 0))
		if tlv >= 0 and tlv != int(lsg.chen_lv):
			# 多层小屋、点在别的层：直接点（trigger 里 _lv_reach 沿石阶走过去）。不能先在本层走到同一个 x 再看范围——
			# 本层的墙可能离那个 x 比互动范围还远（阁楼左墙 1452、楼下门 1408：停在 1458 够得着、1460 就永远够不着，链式自动玩卡死过）
			_target = {}
			trigger(p)
			return
	var wl: Vector2 = world.walls(chen.position.x)
	var stand := clampf(tx, wl.x + 2.0, wl.y - 2.0)
	if (absf(chen.position.x - stand) <= 4.0 and chen._vel <= 0.0) or _target_t > _target_limit:
		_target = {}
		if hotspots.usable(h) and hotspots.in_range(p, chen.position.x) and not hotspots.is_enter(h):
			trigger(p)
		else:
			_unreach[str(h.get("id", ""))] = StoryState.progress()
	elif not level.walking():
		level.walk_to(stand)


## 这一段里能换到 to_area 那一段的点（scene 里 fade_to 到那一段的）
func _route_to_area(to_area: String) -> Dictionary:
	for p in hotspots.available():
		var h: Dictionary = p["h"]
		if hotspots.is_enter(h) or world.area_of(float(p["x"])) != world.area_of(chen.position.x):
			continue
		for sid in _reach(str(h.get("scene", "")), {}):
			for st in scenes.get(sid, []):
				if st is Dictionary and str(st.get("do", "")) == "fade_to" and str(st.get("room", "forest")) == "forest":
					var r: Dictionary = world.resolve(st.get("at", 0))
					if r["ok"] and world.area_of(float(r["x"])) == to_area:
						return p
	return {}


## 跳节拍：把剧情瞬间过一遍，直到 flag 设上（那个 scene 播完）。返回有没有到。
## 点选 / 对话选项 / 用道具 / 挑 hotspot 时，能通到「设这个 flag」的那条优先（支线上的 flag 也能跳）。
var _ff_target := ""
var _ff_log := "--ff_log" in OS.get_cmdline_user_args()


func fast_forward(target: String) -> bool:
	_ff_target = target
	ff = true
	dlg.instant = true
	var guard := 0
	while not StoryState.has(target) and guard < 400:
		guard += 1
		var c := plan()
		if c.is_empty():
			break
		if c["kind"] == "wood":
			await level.ff_take_wood()
		else:
			var p: Dictionary = c["p"]
			if _ff_log:
				print("FF %d %s x=%.0f room=%s" % [guard, str(p["h"].get("id", "")), float(p["x"]), world.room])
			_place(chen, float(p["x"]) - 12.0 * signf(float(p["x"]) - chen.position.x), world.room)
			await trigger(p)
	ff = false
	_ff_target = ""
	_visited.clear()                 # 跳完以后自动玩从头算「来过」
	dlg.instant = false
	return StoryState.has(target)


## 从 scene 出发能不能走到「设 flag」那一步
func _leads_to(s: String, flag: String) -> bool:
	if flag == "" or s == "":
		return false
	for sid in _reach(s, {}):
		for st in scenes.get(sid, []):
			if st is Dictionary and str(st.get("do", "")) in ["flag", "count"] and str(st.get("set", "")) == flag:
				return true
			if st is Dictionary and str(st.get("do", "")) == "mechanic" and (st.get("sets", []) as Array).has(flag):
				return true
	return false


## 等多久（10-30 作者：等 NPC / 晨自己走的时间整体太久、很不自由）：每段剧情里晨被锁着时，
## 等别人走路（npc）、剧本让晨自己走（chen）、干等（wait）各花了几秒。台词不算（自动玩的台词时长是假的）；小游戏、鹿带路不算（能自由动）。
var wait_stats := {}
const WAIT_SCALE := 0.6      # 剧本里 wait 的停顿统一乘这个（最短 0.3 秒）：节奏还在，只是不拖
const WALK_WAIT_MAX := 2.5   # 剧情里等一个人走路最多等几秒
const WALK_HURRY := 2.2      # 为了不超过上面那个时间，最多走快到平时的几倍


func _count_wait(scene: String, st: Dictionary, dt: float) -> void:
	if dt <= 0.05 or st.has("say") or st.has("narr"):
		return
	var d := str(st.get("do", ""))
	var k := ""
	match d:
		"walk":
			k = "chen" if str(st.get("who", "")) == "chen" else "npc"
		"wait":
			k = "wait"
		"pose", "fade_to", "anim":
			k = d
		_:
			return
	if not wait_stats.has(scene):
		wait_stats[scene] = {}
	wait_stats[scene][k] = float(wait_stats[scene].get(k, 0.0)) + dt


func print_wait_stats() -> void:
	var rows: Array = []
	var tot := {}
	for sc in wait_stats:
		var sum := 0.0
		for k in wait_stats[sc]:
			sum += float(wait_stats[sc][k])
			tot[k] = float(tot.get(k, 0.0)) + float(wait_stats[sc][k])
		rows.append([sum, sc])
	rows.sort_custom(func(a, b): return a[0] > b[0])
	var all := 0.0
	var parts: Array = []
	for k in tot:
		all += float(tot[k])
		parts.append("%s=%.1f" % [k, tot[k]])
	print("STORY_WAIT_TOTAL %.1fs %s" % [all, " ".join(parts)])
	for r in rows:
		if float(r[0]) < 2.0:
			break
		var ps: Array = []
		for k in wait_stats[r[1]]:
			ps.append("%s=%.1f" % [k, wait_stats[r[1]][k]])
		print("STORY_WAIT %5.1fs %s  %s" % [r[0], r[1], " ".join(ps)])


func print_stats(tag: String) -> void:
	print_wait_stats()
	var real := (Time.get_ticks_msec() - _t0_ms) / 1000.0
	var unplayed: Array = []
	for id in scenes:
		if not played.has(id):
			unplayed.append(id)
	print("%s story=%s scenes=%d/%d plays=%d lines=%d hotspots=%d game_time=%.1fs real_time=%.1fs" % [
		tag, path, played.size(), scenes.size(), played_order.size(), lines, hotspots_used, _game_t, real])
	print("STORY_FLAGS " + ", ".join(StoryState.flag_order))
	print("STORY_ITEMS " + ", ".join(Inventory.owned))
	print("STORY_UNPLAYED " + (", ".join(unplayed) if not unplayed.is_empty() else "(none)"))
	print("STORY_MISSING_SFX " + (", ".join(missing_sfx.keys()) if not missing_sfx.is_empty() else "(none)"))
	print("STORY_MISSING_ANIM " + (", ".join(missing_anims.keys()) if not missing_anims.is_empty() else "(none)"))
	if tag == "STORY_STUCK":
		var av: Array = []
		for p in hotspots.available():
			av.append(str(p["h"]["id"]))
		print("STORY_STUCK_AT x=%.0f room=%s available=%s" % [chen.position.x, world.room, ", ".join(av)])


# ======================================================================= 检查剧本
func validate() -> Array[String]:
	var out: Array[String] = []
	var set_flags := {}
	for f in ENGINE_FLAGS:
		set_flags[f] = true
	for f in StoryState.flag_order + carry_flags:
		set_flags[f] = true                # 前面章节带过来的（河流篇的 burned_* 是飞行一设的；carry_flags = 前面章节可能设的）
	var refs := {}
	if entry_scene != "":
		refs[entry_scene] = true
	for id in scenes:
		for st in scenes[id]:
			if st is Dictionary and str(st.get("do", "")) in ["flag", "count"] and st.has("set"):
				set_flags[str(st["set"])] = true
			if st is Dictionary and str(st.get("do", "")) == "phone_draft" and str(st.get("flag", "")) != "":
				set_flags[str(st["flag"])] = true
			if st is Dictionary and str(st.get("do", "")) == "mechanic":
				for f5 in st.get("sets", []):
					set_flags[str(f5)] = true
	for k in HOOKS:
		var h := hook(k)
		if h == "":
			out.append("info: 没有 %s 的对接 scene（%s），用关卡原来的" % [k, "/".join(HOOKS[k])])
		else:
			refs[h] = true
	var ids := {}
	for h in hotspot_defs:
		if not h is Dictionary:
			out.append("hotspot 不是对象：" + str(h))
			continue
		var hid := str(h.get("id", ""))
		if ids.has(hid):
			out.append("hotspot id 重复：" + hid)
		ids[hid] = true
		var at = h.get("at", null)
		if at == null or (at is String and npc(str(at)) == null and not world.has_marker(str(at)) and not str(at).is_valid_float()):
			out.append("hotspot %s：at 找不到 %s" % [hid, str(at)])
		if not str(h.get("room", "forest")) in ["forest", "treehouse"] and not (str(h.get("room", "")) == "cockpit" and world.cockpit != null) \
				and not world.is_stage(str(h.get("room", ""))):
			out.append("hotspot %s：room 只能是 forest / treehouse%s（%s）" % [hid, " / cockpit" if world.cockpit != null else "", h.get("room")])
		var sc := str(h.get("scene", ""))
		if not scenes.has(sc) and not (sc == "" and h.has("closeup")):
			out.append("hotspot %s：没有 scene %s" % [hid, sc])
		refs[sc] = true
		for key in ["need", "not"]:
			for f in h.get(key, []):
				if not set_flags.has(str(f)):
					out.append("hotspot %s：%s 里的 flag %s 剧本里没有任何地方设" % [hid, key, f])
		if h.has("hide_after") and not set_flags.has(str(h["hide_after"])):
			out.append("hotspot %s：hide_after %s 没有地方设" % [hid, h["hide_after"]])
		if h.has("sprite") and not ResourceLoader.exists(str(h["sprite"])):
			out.append("info: hotspot %s 的图还没有（色块占位）：%s" % [hid, h["sprite"]])
		var acc = h.get("accepts", {})
		if not acc is Dictionary:
			out.append("hotspot %s：accepts 要是 {物品: scene}" % hid)
		else:
			for k in acc:
				var s3 := str(acc[k])
				refs[s3] = true
				if not scenes.has(s3):
					out.append("hotspot %s：accepts 的 %s → scene %s 不存在" % [hid, k, s3])
				if str(k) != "_default" and not Inventory.defined(str(k)):
					out.append("hotspot %s：accepts 的物品 %s 不在物品表" % [hid, k])
	for id in scenes:
		var arr = scenes[id]
		if not arr is Array:
			out.append("scene %s 不是数组" % id)
			continue
		for st in arr:
			if not st is Dictionary:
				out.append("scene %s：步骤不是对象 %s" % [id, str(st)])
				continue
			var kind := "say" if st.has("say") else ("narr" if st.has("narr") else str(st.get("do", "")))
			if not kind in STEPS and not kind in PHONE_STEPS and not COCKPIT_STEPS.has(kind):
				out.append("scene %s：不支持的步骤 %s" % [id, JSON.stringify(st)])
				continue
			if COCKPIT_STEPS.has(kind):
				out.append_array(_validate_cockpit(str(id), kind, st, refs))
				continue
			match kind:
				"say":
					var who := str(st["say"])
					if not speakers.has(who):
						out.append("scene %s：说话人 %s 不在 speakers 里" % [id, who])
					if str(st.get("zh", "")) == "":
						out.append("scene %s：%s 的台词没有 zh" % [id, who])
				"narr":
					if not st["narr"] is Dictionary or str(st["narr"].get("zh", "")) == "":
						out.append("scene %s：narr 没有 zh" % id)
				"walk", "face":
					var who := str(st.get("who", "chen"))
					if npc(who) == null:
						out.append("scene %s：%s 的 who 不认识 %s" % [id, kind, who])
					var to = st.get("to", null)
					if to == null or (to is String and npc(str(to)) == null and not world.has_marker(str(to)) and not str(to).is_valid_float()):
						out.append("scene %s：%s 的 to 找不到 %s" % [id, kind, str(to)])
				"show", "hide":
					var who := str(st.get("who", ""))
					if npc(who) == null and not world.props.has(who):
						out.append("scene %s：%s 的 who 不认识 %s" % [id, kind, who])
					if st.has("at") and not world.has_marker(str(st["at"])) and not str(st["at"]).is_valid_float():
						out.append("scene %s：%s 的 at 找不到 %s" % [id, kind, st["at"]])
				"give", "take":
					for item in (st.get("items", []) if kind == "give" and st.has("items") else [str(st.get("item", ""))]):
						if not Inventory.defined(str(item)):
							out.append("scene %s：物品 %s 不在 items.json（也不在剧本 items 里）" % [id, item])
				"journal":
					if str(st.get("zh", "")) == "":
						out.append("scene %s：journal 没有 zh" % id)
				"sfx", "ambient":
					var nm := str(st.get("name", ""))
					if _sfx_path(nm) == "":
						missing_sfx[nm] = true
					if kind == "ambient" and not world.has_marker(str(st.get("at", ""))):
						out.append("scene %s：ambient 的 at 找不到 %s" % [id, st.get("at")])
				"show_item":
					if not Inventory.defined(str(st.get("item", ""))):
						out.append("scene %s：show_item 的物品 %s 不在物品表" % [id, st.get("item")])
				"choice":
					var copts: Array = st.get("options", [])
					if copts.size() < 2:
						out.append("scene %s：choice 至少要两个选项" % id)
					for o in copts:
						var s4 := str(o.get("scene", ""))
						if str(o.get("zh", "")) == "":
							out.append("scene %s：choice 选项没有 zh" % id)
						if s4 != "":
							refs[s4] = true
							if not scenes.has(s4):
								out.append("scene %s：choice 选项的 scene %s 不存在" % [id, s4])
				"count":
					if not st.has("set") or not st.has("flags"):
						out.append("scene %s：count 要有 flags 和 set" % id)
				"fuel":
					var known := ["do", "have", "need", "burn", "add", "sub", "added", "_comment"]
					for k3 in st:
						if not str(k3) in known:
							out.append("scene %s：fuel 不认识 %s（有 have / need / burn / add / sub）" % [id, k3])
					if st.has("burn") and (not Inventory.defined(str(st["burn"])) or fuel_of(str(st["burn"])) <= 0):
						out.append("scene %s：fuel 的 burn %s 不在物品表或没有 keepsake_burn / burn" % [id, st["burn"]])
				"journal_strike", "journal_mark":
					if str(st.get("match", "")) == "":
						out.append("scene %s：%s 没有 match" % [id, kind])
				"elephant_call":
					var nm2 := "elephant_call_%d" % int(st.get("variant", 1))
					if _sfx_path(nm2) == "":
						missing_sfx[nm2] = true
				"if":
					for k2 in ["then", "else"]:
						if st.has(k2):
							var s2 := str(st[k2])
							refs[s2] = true
							if s2 != "" and not scenes.has(s2):
								out.append("scene %s：if 的 %s scene %s 不存在" % [id, k2, s2])
					var f2 := str(st.get("flag", "")).trim_prefix("!")
					if not set_flags.has(f2):
						out.append("scene %s：if 的 flag %s 没有地方设" % [id, f2])
				"fade_to":
					if not str(st.get("room", "forest")) in ["forest", "treehouse"] and not world.is_stage(str(st.get("room", ""))) \
							and not (str(st.get("room", "")) == "cockpit" and world.cockpit != null):
						out.append("scene %s：fade_to 的 room 不认识 %s" % [id, st.get("room")])
					if not world.has_marker(str(st.get("at", ""))) and not str(st.get("at", "")).is_valid_float():
						out.append("scene %s：fade_to 的 at 找不到 %s" % [id, st.get("at")])
					for w in st.get("with", []):
						if npc(str(w)) == null:
							out.append("scene %s：fade_to 的 with 不认识 %s" % [id, w])
					var pl4 = st.get("place", {})
					if pl4 is Dictionary:
						for w4 in pl4:
							if npc(str(w4)) == null:
								out.append("scene %s：fade_to 的 place 不认识 %s" % [id, w4])
							elif not world.has_marker(str(pl4[w4])) and not str(pl4[w4]).is_valid_float():
								out.append("scene %s：fade_to 的 place 找不到 %s" % [id, pl4[w4]])
					for k4 in ["leave", "cam", "arrive"]:
						if st.has(k4) and not world.has_marker(str(st[k4])) and not str(st[k4]).is_valid_float():
							out.append("scene %s：fade_to 的 %s 找不到 %s" % [id, k4, st[k4]])
				"camera":
					if st.has("at") and not world.has_marker(str(st["at"])) and not str(st["at"]).is_valid_float():
						out.append("scene %s：camera 的 at 找不到 %s" % [id, st["at"]])
					if not (st.has("at") or st.get("hold", false) or st.get("release", false)):
						out.append("scene %s：camera 要有 at / hold / release" % id)
				"anim":
					var who := str(st.get("who", ""))
					var key := "miluo" if npc(who) == miluo else who
					if npc(who) != null and npcs.values().has(npc(who)):
						if not npc(who).has_anim(str(st.get("name", ""))):
							out.append("info: MISSING_ANIM %s.%s（scene %s：还没有这段动作，播的时候退回待机 / 占位）" % [who, st.get("name"), id])
						continue
					if npc(who) == chen and chen != null and not (ANIM_MAP["chen"] as Dictionary).has(str(st.get("name", ""))):
						if chen_anim(str(st.get("name", ""))) == "":
							var al := str(chen_alias().get(str(st.get("name", "")), ""))
							out.append("info: MISSING_ANIM %s（scene %s：晨还没有这段动作，播的时候退回待机）" % [str(st.get("name")) + (" → " + al if al != "" else ""), id])
					elif not (ANIM_MAP.get(key, {}) as Dictionary).has(str(st.get("name", ""))):
						out.append("scene %s：%s 没有动画 %s（有：%s）" % [id, who, st.get("name"), ", ".join((ANIM_MAP.get(key, {}) as Dictionary).keys())])
				"prop":
					var pid := str(st.get("id", ""))
					if world.stage_of_prop(pid) != "" or (not world.stages.is_empty() and not world.props.has(world.prop_id(pid)) and not (world.cockpit != null and world.cockpit.has_prop(pid))):
						if world.stage_of_prop(pid) == "":
							out.append("info: scene %s：物件 %s 还没有图 / 位置（room.json 里加上就有；现在只记状态）" % [id, pid])
						continue
					if world.cockpit != null and world.cockpit.has_prop(pid):
						var ks: Array = world.cockpit.KNOWN_STATES.get(pid, [])
						if not world.cockpit.objects.has(pid) and pid != "cockpit_window":
							out.append("info: scene %s：驾驶舱物件 %s 没有位置（cockpit.json / 占位布局里都没有），只记状态" % [id, pid])
						elif not ks.has(str(st.get("state", ""))):
							out.append("info: scene %s：驾驶舱物件 %s 的状态 %s 引擎没专门画（占位亮一档；有 %s_%s.png 就用图）" % [id, pid, st.get("state"), pid.trim_prefix("cockpit_"), st.get("state")])
					elif not world.props.has(world.prop_id(pid)) and not pid in world.PSEUDO_PROPS:
						out.append("scene %s：没有物件 %s（只记状态，画面上没东西）" % [id, pid])
				"guide":
					if not world.has_marker(str(st.get("to", ""))) and not str(st.get("to", "")).is_valid_float():
						out.append("scene %s：guide 的 to 找不到 %s" % [id, st.get("to")])
				"goto":
					var s := str(st.get("scene", ""))
					refs[s] = true
					if not scenes.has(s):
						out.append("scene %s：goto 的 scene %s 不存在" % [id, s])
				"mechanic", "todo_mechanic", "form", "follow", "water", "closeup":
					out.append_array(_validate_room_step(str(id), kind, st, refs))
				"pick":
					for o in st.get("options", []):
						var s := str(o.get("scene", ""))
						refs[s] = true
						if not scenes.has(s):
							out.append("scene %s：pick 选项 %s 的 scene %s 不存在" % [id, o.get("id"), s])
						var pid := str(o.get("id", ""))
						if not world.props.has(pid) and not world.props.has(pid.trim_prefix("room_")) and world.stage_of_prop(pid) == "":
							out.append("info: scene %s：pick 选项 %s 场景里没有这个物件（用下面一排按钮）" % [id, pid])
	for h in hotspot_defs:
		if h is Dictionary and hotspots.is_enter(h) and not bool(h.get("cutscene", false)):
			for s in _reach(str(h.get("scene", "")), {}):
				for st in scenes.get(s, []):
					if st is Dictionary and str(st.get("do", "")) == "walk" and str(st.get("who", "chen")) == "chen":
						out.append("scene %s（hotspot %s 走进去触发）：晨的 walk 不执行——不推人，停在看得见的边上" % [s, h.get("id")])
	for id in scenes:
		if not refs.has(id):
			out.append("info: scene %s 没有任何 hotspot / goto / pick / if 引用到（播不到）" % id)
	var hs = data.get("hints", null)
	if hs is Array:
		for e in hs:
			if e is Dictionary and e.has("flag") and not set_flags.has(str(e["flag"])):
				out.append("hints：flag %s 没有地方设" % e["flag"])
	elif hs is Dictionary:
		for f in hs:
			if not set_flags.has(str(f)):
				out.append("hints：flag %s 没有地方设" % f)
	out.append_array(PHONE_GD.validate(scenes))
	out.append_array(_validate_fuel())
	if not missing_sfx.is_empty():
		out.append("info: 缺音效文件（静默跳过）：" + ", ".join(missing_sfx.keys()))
	return out


## --story_check：驾驶舱的两个步骤（debris_steer / keepsake_choice）
func _validate_cockpit(id: String, kind: String, st: Dictionary, refs: Dictionary) -> Array[String]:
	var out: Array[String] = []
	if world.cockpit == null:
		out.append("scene %s：%s 要在驾驶舱里（剧本 rooms 里加 cockpit）" % [id, kind])
	if kind == "debris_steer":
		if not (st.get("sec", 40) is float or st.get("sec", 40) is int):
			out.append("scene %s：debris_steer 的 sec 要是数字" % id)
		return out
	if kind == "cockpit_dash":
		return out
	var items: Array = st.get("items", [])
	var sc: Dictionary = st.get("scenes", {}) if st.get("scenes", {}) is Dictionary else {}
	if items.is_empty():
		out.append("scene %s：keepsake_choice 没有 items" % id)
	for it in items:
		if not Inventory.defined(str(it)):
			out.append("scene %s：keepsake_choice 的物品 %s 不在物品表" % [id, it])
		if not sc.has(str(it)):
			out.append("scene %s：keepsake_choice 的 %s 没有对应的 scene（scenes 里加上）" % [id, it])
	for k in sc:
		refs[str(sc[k])] = true
		if not scenes.has(str(sc[k])):
			out.append("scene %s：keepsake_choice 的 %s → scene %s 不存在" % [id, k, sc[k]])
	var groups: Array = []
	var look = st.get("look", {})
	if look is Dictionary:
		for k in look:
			groups.append(look[k])
	groups.append(st.get("put_back", []))
	groups.append(st.get("route_look", []))
	for g in groups:
		if not g is Array:
			out.append("scene %s：keepsake_choice 的 look / put_back / route_look 要是台词数组" % id)
			continue
		for l in g:
			if l is Dictionary and l.has("say") and not speakers.has(str(l["say"])):
				out.append("scene %s：keepsake_choice 台词的说话人 %s 不在 speakers 里" % [id, l["say"]])
	return out


## --story_check：燃料表对得上——起飞的燃料 − 避碎石最多扣的 + 放进任何一件纪念品给的 ≥ 改航线以后需要的量
## （作者的规矩：放一件就一定补得上；纪念品卡片上不标数，差多少只看左上角）
func _validate_fuel() -> Array[String]:
	var out: Array[String] = []
	var have := -1
	var need := 0
	var loss := 0
	var any := false
	for id in scenes:
		for st in scenes[id]:
			if not st is Dictionary:
				continue
			var d := str(st.get("do", ""))
			if d == "fuel":
				any = true
				if st.has("have") and have < 0:
					have = int(st["have"])
				if st.has("need"):
					need = maxi(need, int(st["need"]))
			elif d == "debris_steer" and int(st.get("fuel_per_bump", 0)) > 0:
				if not st.has("fuel_max_loss"):
					out.append("scene %s：debris_steer 扣燃料要写 fuel_max_loss（最多扣多少），不然放一件纪念品可能补不上" % id)
				loss += int(st.get("fuel_max_loss", 0))
	if not any:
		return out
	if have < 0:
		out.append("fuel：剧本里没有设起始燃料（{\"do\": \"fuel\", \"have\": n, \"need\": n}）")
		return out
	for id in scenes:
		for st in scenes[id]:
			if not st is Dictionary or str(st.get("do", "")) != "keepsake_choice":
				continue
			var sc: Dictionary = st.get("scenes", {}) if st.get("scenes", {}) is Dictionary else {}
			for it in st.get("items", []):
				var gain := 0
				for sid in _reach(str(sc.get(str(it), "")), {}):
					for s2 in scenes.get(sid, []):
						if s2 is Dictionary and str(s2.get("do", "")) == "fuel":
							gain += fuel_of(str(s2["burn"])) if s2.has("burn") else int(s2.get("add", 0))
				if gain <= 0:
					out.append("scene %s：keepsake_choice 放 %s 以后没有 fuel 步骤加燃料（燃料表不会涨）" % [id, it])
				elif have - loss + gain < need:
					out.append("scene %s：放 %s 补不上燃料：起飞 %d − 撞碎石最多 %d + %d < 需要 %d" % [id, it, have, loss, gain, need])
	return out


## if 的分支 scene 能不能「播完回来」：里面只有普通步骤（没有 goto / if / 点选 / 对话选项 / 带路 / 结束 / 驾驶舱选择）
func _falls_through(s: String) -> bool:
	if not scenes.has(s):
		return false
	for st in scenes[s]:
		if st is Dictionary and str(st.get("do", "")) in ["goto", "if", "pick", "choice", "guide", "end_chapter", "keepsake_choice"]:
			return false
	return true


# ======================================================================= 多房间章节（河流篇起，docs/river_rooms_contract.md）
func _multi_room() -> bool:
	for r in data.get("rooms", []):
		if not str(r) in ["forest", "treehouse", "cockpit"]:
			return true
	return false


## 剧本里当角色用的名字（不是晨 / 鹿 / 弥洛的，交给 npc_generic.gd）
func _collect_npc_names() -> void:
	var skip := ["chen", "deer", "miluo", "milo", "snake", ""]
	for sid in scenes:
		for st in scenes[sid]:
			if not st is Dictionary:
				continue
			var d := str(st.get("do", ""))
			if d in ["show", "hide", "walk", "face", "anim", "form", "follow"]:
				var w := str(st.get("who", ""))
				if not w in skip and not (d in ["show", "hide"] and _is_prop_name(w)):
					_npc_names[w] = true
			if d == "fade_to":
				for w2 in st.get("with", []):
					if not str(w2) in skip:
						_npc_names[str(w2)] = true


func _is_prop_name(w: String) -> bool:
	return world.props.has(w) or world.props.has(w.trim_prefix("room_"))


## 通用角色：第一次用到时建（藏着，等剧本 show）
func _generic(who: String) -> Node2D:
	if npcs.has(who):
		return npcs[who]
	if not _npc_names.has(who) or level == null:
		return null
	var n: Node2D = NPC_GD.new()
	n.setup(who)
	n.visible = false
	level.add_child(n)
	level.move_child(n, chen.get_index())       # 和晨同一层、排在晨后面（晨在前）
	npcs[who] = n
	_npc_room[n.name] = world.room
	var r: String = world.room
	n.ground_fn = func(gx: float) -> float: return world.ground_at(gx, r)
	return n


## 推每个 marker 在哪个房间：hotspot 的 room、scene 里 fade_to 换过去的房间，顺着 goto / if / 选项传下去
func _setup_stages() -> void:
	var scene_room := {}
	for h in hotspot_defs:
		if h is Dictionary and str(h.get("scene", "")) != "":
			scene_room[str(h["scene"])] = str(h.get("room", "forest"))
	var start_room := ""
	for r in data.get("rooms", []):
		if not str(r) in ["forest", "treehouse", "cockpit"]:
			start_room = str(r)
			break
	if entry_scene != "" and not scene_room.has(entry_scene):
		scene_room[entry_scene] = start_room
	for sid in scenes:
		if str(sid).begins_with("start") and not scene_room.has(sid):
			scene_room[sid] = start_room
	var inferred := {}
	var prop_ids := {}
	for _pass in 6:
		for sid in scene_room.keys():
			var cur := str(scene_room[sid])
			for st in scenes.get(sid, []):
				if not st is Dictionary:
					continue
				var d := str(st.get("do", ""))
				if d == "fade_to":
					cur = str(st.get("room", cur))
				var refs: Array = []
				for k in ["to", "at", "leave", "cam", "arrive"]:
					if st.get(k) is String:
						refs.append(str(st[k]))
				if d == "prop":
					refs.append(str(st.get("id", "")))
					prop_ids[str(st.get("id", ""))] = true
				var pl = st.get("place", {})
				if pl is Dictionary:
					for v in pl.values():
						refs.append(str(v))
				for m in refs:
					if not inferred.has(m) and npc(m) == null:
						inferred[m] = cur
				var nexts: Array = []
				match d:
					"goto":
						nexts.append(str(st.get("scene", "")))
					"if":
						nexts.append(str(st.get("then", "")))
						nexts.append(str(st.get("else", "")))
					"choice", "pick":
						for o in st.get("options", []):
							nexts.append(str(o.get("scene", "")))
					"closeup":
						for z in st.get("zones", []):
							nexts.append(str(z.get("scene", "")))
				for nx in nexts:
					if nx != "" and not scene_room.has(nx):
						scene_room[nx] = cur
	for h in hotspot_defs:
		if h is Dictionary and h.get("at") is String:
			inferred[str(h["at"])] = str(h.get("room", "forest"))
	var order: Array = (data.get("markers", {}) as Dictionary).keys()
	for m in inferred:
		if not order.has(m):
			order.append(m)
	world._prop_ids = prop_ids.keys()
	world.add_stages(data.get("rooms", []), inferred, order)


func world_cam_y(r := "") -> float:
	var sg: Node2D = world.stage(r if r != "" else world.room)
	return sg.cam_y() if sg != null else 135.0


func room_of_marker(nm: String) -> String:
	return world.room_of_marker(nm)


## 通用角色在小屋里外（树屋同款）：屋里的人在晨不在屋里时压到前墙后面；晨进屋时，站在屋子图范围里的屋外的人淡掉
func _sync_generic_vis(instant: bool) -> void:
	for who in npcs:
		var n: Node2D = npcs[who]
		var r := str(_npc_room.get(n.name, ""))
		var rs: Node2D = world.stage(r)
		var cs: Node2D = world.cur_stage()
		n.z_index = -2 if rs != null and rs.is_house and world.room != r else int(n.get_meta("pose_z", 0))   # pose 压到物件后面的保留
		var a := 1.0
		if cs != null and cs.is_house and r != world.room and world.house_pair(r, world.room):
			if n.position.x > cs.origin.x and n.position.x < cs.origin.x + cs.size.x:
				a = 0.0
		var old = n.get_meta("sync_tw") if n.has_meta("sync_tw") else null
		if old is Tween and (old as Tween).is_valid():
			(old as Tween).kill()
		if instant or ff:
			n.modulate.a = a
		elif not is_equal_approx(n.modulate.a, a):
			var tw := create_tween()
			tw.tween_property(n, "modulate:a", a, 0.5)
			n.set_meta("sync_tw", tw)


## pose：通用角色的图（spr）绕脚底转 rot 度、挪 dx / dy 像素，sec 秒平滑过去（sine，物理一点）；z 给了就改人的前后
## （物件默认 z −1：z −2 = 压到物件后面）。{"rot": 0, "dx": 0, "dy": 0} = 回到原样；z 写 0 回到平常。wait:false 不等。
## 10-30 作者：河岸遇见妮芙，箱子后面先露出鲸鱼壳的尾巴（妮芙原图斜着扎进箱子后面），再转过来——不另画尾巴、不凭空出现。
func _pose(st: Dictionary) -> void:
	var n := npc(str(st.get("who", "")))
	if n == null or not npcs.values().has(n):
		return
	var spr: Node2D = n.spr
	if st.has("z"):
		n.z_index = int(st["z"])
		n.set_meta("pose_z", int(st["z"]))
	var rot := deg_to_rad(float(st.get("rot", 0.0)))
	var pos := Vector2(float(st.get("dx", 0.0)), float(st.get("dy", 0.0)))
	var sec := float(st.get("sec", 0.6))
	if ff or sec <= 0.0:
		spr.rotation = rot
		spr.position = pos
		return
	var tw := create_tween().set_parallel(true).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(spr, "rotation", rot, sec)
	tw.tween_method(func(p: Vector2): spr.position = p.round(), spr.position, pos, sec)   # 位置取整到像素
	if st.get("wait", true):
		await tw.finished


## 跟着晨走（follow）：自由走动时（剧情没在播、或小游戏在等互动）每帧追晨身后 gap 像素
func _update_follow(delta: float) -> void:
	if ff:
		return
	var free: bool = (not busy or free_walk or mech_wait) and level.free_play()
	for who in follow:
		var n := npc(str(who))
		if n == null or not n.visible or not npcs.values().has(n):
			continue
		if str(_npc_room.get(n.name, "")) != world.room:
			continue
		var fsg := _lv_stage()
		if fsg != null and _lv_of(n, fsg) != fsg.chen_lv:
			if free and not n.has_meta("lv_climbing") and fsg.chen_stair < 0:
				_lv_walk(n, fsg, fsg.chen_lv, chen.position.x - (FOLLOW_GAP if chen.facing > 0 else -FOLLOW_GAP))   # 跟着晨上 / 下楼
			continue
		if n.has_meta("lv_climbing"):
			continue
		_make_way(n, _side_gap(n, float(follow[who])), free, delta)
	# 没在跟着晨、但会飘开让路的（妮芙的鲸鱼壳悬浮着：hover）：晨走过来也让开
	for n in npcs.values():
		if follow.has(str(n.get("npc_id"))) or not n.visible or _room_of(n) != world.room or n.has_meta("lv_climbing"):
			continue
		if not (n.get("cur") is Dictionary and float((n.get("cur") as Dictionary).get("hover", 0.0)) > 0.0):
			continue
		var hsg := _lv_stage()
		if hsg != null and _lv_of(n, hsg) != hsg.chen_lv:
			continue
		_make_way(n, _side_gap(n, FOLLOW_GAP), false, delta)


## 人和人不叠：跟着晨 / 会让路的人待在她现在那一边（晨转身她不从晨身上穿过去），只有被挤到墙边才绕到另一边。
## follow = 自由走的时候跟在晨这一边 gap 远；不跟的时候只在晨冲她走过来时让开（弹簧平滑飘开，追不上再硬推）
func _make_way(n: Node2D, gap: float, follow_on: bool, delta: float) -> void:
	var dx := n.position.x - chen.position.x
	var side := signf(dx) if absf(dx) >= 1.0 else (-1.0 if chen.facing > 0 else 1.0)
	var w: Vector2 = world.walls(chen.position.x)
	var swap := false
	if chen.position.x + side * gap < w.x + 4.0 or chen.position.x + side * gap > w.y - 4.0:
		side = -side
		swap = true
	var tx := clampf(chen.position.x + side * gap, w.x + 4.0, w.y - 4.0)
	if follow_on:
		if absf(tx - n.position.x) < 4.0 and chen._vel <= 0.0:
			tx = n.position.x
		n.follow_to(tx, chen.position.x, delta)
	elif not n.is_walking() and chen._vel > 0.0 and dx * side < gap + 16.0 and signf(chen.facing) == side:
		n.follow_to(tx, chen.position.x, delta)           # 晨冲她走过来：先飘开
	# 弹簧追不上（晨跑过来、过场里晨走过她身边）：直接推开，鲸鱼壳不压到晨身上
	if not swap and not n.is_walking() and dx * side < gap - 0.5 and absf(tx - chen.position.x) >= gap - 0.5:
		n.position.x = round(tx)
		n._snap_y()


## 跟在晨旁边至少隔多远才不叠到晨身上：比人宽的（妮芙的鲸鱼壳 71 宽，锚点到边 36）= 锚点到最远一边 + 晨半个身子 12；
## 一般大小的人（帧 40 宽）照 base
func _side_gap(n: Node2D, base: float) -> float:
	var c = n.get("cur")
	if not c is Dictionary or not (c as Dictionary).has("frame"):
		return base
	var fr: Array = c["frame"]
	var an: Array = c.get("anchor", [float(fr[0]) / 2.0, 0])
	var half := maxf(float(an[0]), float(fr[0]) - float(an[0]))
	return maxf(base, half + 12.0 + CLEAR_GAP) if half > 28.0 else base     # 鲸鱼壳和晨之间留 CLEAR_GAP


## 人和人不叠（10-30，作者：人物互相穿插就是 bug）：晨和通用角色（妮芙、阿汀、摊主……）谁也不压到谁身上，两边轮廓隔开 CLEAR_GAP。
##   剧本让人站的位置（walk / show / 换房间放下来）压到别人 → 挪到最近的空地（优先停在走过来的这一边，不穿过人站到对面）；
##   场景开始时晨站在别人身上（走进人身子里按的互动）→ 晨先退开，跟着晨的人压在晨身上 → 她飘开；
##   跟着晨的人（_update_follow）待在她现在那一边，晨冲她走过来就被推着走，不从晨身上穿过去。
##   宽度 = 锚点到身子最远一边：晨 12；妮芙的鲸鱼壳 36；一般大小的人（帧 40 宽）当晨算 12。
##   json 写 "keep_clear": true 的（阿汀 = 奥斯卡的阴险守卫，比晨大一倍，会转身、背后的黑团子换边）按帧算两边里远的那边，
##   还能写 "avoid": [{"room", "x": [x0, x1], "prop", "states": [...]}]：物件是这些状态时他的轮廓也不压到这段（飞机舱门）。
##   背景走过的小人（shadow = false）不算。玩家自己走路穿过站着的人不拦。
const CLEAR_GAP := 4.0
const CLEAR_CHEN_HALF := 12.0
var _chen_goal := NAN                   # 剧本让晨走去的地方（还在走）：别人按这里躲


func _keeps_clear(n: Node2D) -> bool:
	if n == null or not npcs.values().has(n):
		return false
	var c = n.get("cur")
	return c is Dictionary and bool((c as Dictionary).get("keep_clear", false))


## 算不算一个占地方的人：晨、通用角色（背景小人不算）
func _is_body(n: Node2D) -> bool:
	if n == chen:
		return true
	return n != null and npcs.values().has(n) and bool(n.get("shadow"))


## 锚点到身子最远一边多远
func _half_w(n: Node2D) -> float:
	var c = n.get("cur") if n != chen else null
	if not c is Dictionary or not (c as Dictionary).has("frame"):
		return CLEAR_CHEN_HALF
	var fr: Array = c["frame"]
	var an: Array = c.get("anchor", [float(fr[0]) / 2.0, 0])
	var half := maxf(float(an[0]), float(fr[0]) - float(an[0]))
	return half if half > 28.0 or bool(c.get("keep_clear", false)) else CLEAR_CHEN_HALF


## 晨和 n 站多远才不叠（找人说话的范围也用它）
func clear_dist(n: Node2D) -> float:
	return _half_w(n) + CLEAR_CHEN_HALF + CLEAR_GAP


## mover 的锚点不能落进去的区间（开区间 x..y）：同一间房、同一层、看得见的人 + 他要躲的物件。skip_follow = 跟着晨的人不算（她们自己让）
func _clear_blocks(mover: Node2D, room: String, lv: int, skip_follow := false) -> Array:
	var out := []
	if not _is_body(mover):
		return out
	var mh := _half_w(mover)
	var sg := _lv_stage(room)
	var others: Array = [chen]
	others.append_array(npcs.values())
	for o in others:
		if o == mover or not o.visible or not _is_body(o):
			continue
		if skip_follow and o != chen and follow.has(str(o.get("npc_id"))):
			continue
		if (world.room if o == chen else _room_of(o)) != room:
			continue
		if sg != null and lv >= 0 and _lv_of(o, sg) != lv:
			continue
		var ox: float = o.position.x
		if o == chen and not is_nan(_chen_goal) and (chen.auto_dir != 0.0 or level.strolling()):
			ox = _chen_goal                         # 晨还在走：按他要停的地方算
		elif o != chen and o.is_walking():
			ox = float(o.get("_walk_x"))
		var d := mh + _half_w(o) + CLEAR_GAP
		out.append(Vector2(ox - d, ox + d))
	if _keeps_clear(mover):
		for z in (mover.get("cur") as Dictionary).get("avoid", []):
			if not z is Dictionary or str(z.get("room", "")) != room:
				continue
			if z.has("prop") and not (z.get("states", []) as Array).has(world.prop_state(str(z["prop"]))):
				continue
			var zx: Array = z.get("x", [0, 0])
			out.append(Vector2(float(zx[0]) - mh - CLEAR_GAP, float(zx[1]) + mh + CLEAR_GAP))
	return out


## 剧本让别人走到晨的另一边：一维的画面里绕不过去，路上一定穿过晨 → 停在自己这一边、晨旁边（人和人不叠）
func _no_pass_chen(n: Node2D, x: float, lv: int) -> float:
	if n == chen or not _is_body(n) or not chen.visible or _room_of(n) != world.room:
		return x
	var sg := _lv_stage()
	if sg != null and (lv >= 0 and lv != int(sg.chen_lv) or _lv_of(n, sg) != int(sg.chen_lv)):
		return x                                  # 不在晨这一层（或者要换层）：路上碰不到晨
	var cx := chen.position.x
	var d := _half_w(n) + CLEAR_CHEN_HALF + CLEAR_GAP
	if n.position.x <= cx - d and x > cx - d:
		print("KEEP_CLEAR %s %d → %d（不穿过晨）" % [n.name, int(x), int(cx - d)])
		return cx - d
	if n.position.x >= cx + d and x < cx + d:
		print("KEEP_CLEAR %s %d → %d（不穿过晨）" % [n.name, int(x), int(cx + d)])
		return cx + d
	return x


## 想站 x：压到人 / 物件就挪到最近的空地。from_x = 从哪边走过来：优先停在这一边（不穿过别人站到对面），这边没地方才去另一边
func _clear_x(mover: Node2D, x: float, room: String, lv := -1, from_x := NAN, skip_follow := false) -> float:
	var bl := _clear_blocks(mover, room, lv, skip_follow)
	if bl.is_empty():
		return x
	var stg: Node2D = world.stage(room) if world.is_stage(room) else null
	var w: Vector2 = stg.walls() if stg != null else world.walls(x)
	var cands: Array = [x]
	for b in bl:
		cands.append(ceilf(b.x) - 1.0)
		cands.append(floorf(b.y) + 1.0)
	var best := x
	var best_s := INF
	for c in cands:
		if c < w.x + 4.0 or c > w.y - 4.0:
			continue
		var ok := true
		for b in bl:
			if c > b.x and c < b.y:
				ok = false
				break
		if not ok:
			continue
		var s := absf(c - x)
		if not is_nan(from_x) and absf(from_x - x) > 1.0 and absf(c - x) > 0.5 and signf(c - x) != signf(from_x - x):
			s += 100000.0
		if s < best_s:
			best_s = s
			best = c
	if absf(best - x) >= 1.0:
		print("KEEP_CLEAR %s %d → %d（%s）" % [mover.name, int(x), int(round(best)), room])
	return round(best)


## 调试（--overlap_log）：每帧查同一间房、同一层看得见的人有没有叠在一起（轮廓压上，不算 CLEAR_GAP），
## 打印 OVERLAP 谁 谁 dx、scene、是剧情里还是自由走（free = 玩家自己走路穿过人，不拦）。同一对连着叠只打一次。
var _overlap_log := "--overlap_log" in OS.get_cmdline_user_args()
var _overlap_on := {}


func _check_overlap() -> void:
	var bodies: Array = [chen]
	for n in npcs.values():
		bodies.append(n)
	var sg := _lv_stage()
	var free: bool = (not busy or free_walk or mech_wait) and level.free_play()
	for i in bodies.size():
		var a: Node2D = bodies[i]
		if not a.visible or not _is_body(a):
			continue
		for j in range(i + 1, bodies.size()):
			var b: Node2D = bodies[j]
			if not b.visible or not _is_body(b):
				continue
			var ra: String = world.room if a == chen else _room_of(a)
			var rb: String = _room_of(b)
			var key := a.name + "|" + b.name
			var hit: bool = ra == world.room and rb == world.room and (sg == null or _lv_of(a, sg) == _lv_of(b, sg)) \
				and absf(a.position.x - b.position.x) < _half_w(a) + _half_w(b) - 0.5
			if hit and not _overlap_on.has(key):
				print("OVERLAP %s %s dx=%d scene=%s step=%d %s | %s | %s" % [a.name, b.name, int(absf(a.position.x - b.position.x)), _cur_scene, step_i,
					"free" if free else "story", _body_state(a), _body_state(b)])
			if hit:
				_overlap_on[key] = true
			else:
				_overlap_on.erase(key)


func _body_state(n: Node2D) -> String:
	if n == chen:
		return "chen x=%d vel=%.0f auto=%.0f goal=%s" % [int(chen.position.x), chen._vel, chen.auto_dir, str(_chen_goal)]
	return "%s x=%d walk=%s follow=%s" % [n.name, int(n.position.x), str(n.is_walking()), str(follow.has(str(n.get("npc_id"))))]


## 场景开始：晨站在别人身上（走进人身子里按的互动）→ 晨先退到旁边空地、转回来；跟着晨的人压在晨身上 → 她飘开
func _settle_start() -> void:
	if not chen.visible:
		return
	var sg := _lv_stage()
	var lv := int(sg.chen_lv) if sg != null else -1
	var x := _clear_x(chen, chen.position.x, world.room, lv, NAN, true)
	if absf(x - chen.position.x) >= 1.0:
		var back := chen.position.x
		await _chen_walk(x)
		chen._set_facing(1 if back > chen.position.x else -1)
	for who in follow:
		var n := npc(str(who))
		if n == null or not n.visible or _room_of(n) != world.room or n.is_walking():
			continue
		if sg != null and _lv_of(n, sg) != lv:
			continue
		var nx := _clear_x(n, n.position.x, world.room, lv)
		if absf(nx - n.position.x) < 1.0:
			continue
		n.walk_to(nx)
		while n.is_walking():
			await get_tree().process_frame
		n._set_facing(1 if chen.position.x > n.position.x else -1)


# ----------------------------------------------------------------------- 房间之间的转场
## 多房间章节的 fade_to：door（小屋前墙）/ pan_up / pan_down（镜头竖直平移）/ walk_fade（边走边黑）；fade 或带 leave / cam 的走原来的
func _stage_fade(st: Dictionary, room: String, x: float, arrive: float) -> bool:
	var from: String = world.room
	var kind := str(st.get("kind", ""))
	if kind == "":
		if world.house_pair(from, room):
			kind = "door"
		elif st.has("leave") or st.has("cam"):
			kind = "fade"
		else:
			var fs: Node2D = world.stage(from)
			kind = str(fs.portal_to_room(room).get("kind", "fade")) if fs != null else "fade"
	var with: Array = st.get("with", [])
	if room == "cockpit" and world.is_stage(from):
		await _stage_takeoff()             # 河岸 → 驾驶舱（原文 151–152）：飞机竖直升起、泛光、往左上飞出画面，再接原来的淡出
		return false
	match kind:
		"door":
			_teleport(room, x, with, false)
			_fade_place(st)
			await _wait(0.55)
			return true
		"pan_up", "pan_down":
			var ts: Node2D = world.stage(room)
			var fs2: Node2D = world.stage(from)
			if (ts != null and ts.env == "underwater") or (fs2 != null and fs2.env == "underwater"):
				await _dive_fade(room, x, with, st, ts != null and ts.env == "underwater")
			else:
				await _pan_to(room, x, with, st)
			return true
		"walk_fade":
			await _walk_fade(room, x, with, st, arrive)
			return true
	return false


## 人（晨 + 同行的）按 4 档淡出 / 淡入
func _fade_people(on: bool, sec: float, with: Array) -> void:
	var list: Array = [chen]
	for w in with:
		var n := npc(str(w))
		if n != null:
			list.append(n)
	for f in follow:
		var n2 := npc(str(f))
		if n2 != null and not list.has(n2):
			list.append(n2)
	var tw := create_tween().set_parallel(true)
	for n in list:
		var nd: Node2D = n
		tw.tween_method(func(a: float): nd.modulate.a = (floorf(a * 4.0) if on else ceilf(a * 4.0)) / 4.0,
			0.0 if on else 1.0, 1.0 if on else 0.0, sec)
	await tw.finished


## 竖直平移（10-31 作者：两个房间不拼在一起、也不要夜空，渐黑再渐亮，但要看得出在往上 / 往下走）：
## 晨（和同行的）淡掉 → 渐黑的同时镜头在这个房间里往上（下）移 PAN_SHIFT、平滑起步 → 黑着换房间 →
## 渐亮的同时镜头从新房间下（上）面 PAN_SHIFT 接着往上（下）移、减速停住 → 人淡出来。
## 两段距离、时长一样，sine 前半段 EASE_IN、后半段 EASE_OUT，接上的地方速度相等，看着是一口气。
## 镜头移出房间露出来的地方 level_forest 的房间上下盖黑会盖住（本来就在变黑）。
const PAN_SHIFT := 40.0
const PAN_HALF := 0.85
func _pan_to(room: String, x: float, with: Array, st: Dictionary) -> void:
	var to_st: Node2D = world.stage(room)
	var from_st: Node2D = world.cur_stage()
	var dir := -1.0 if from_st == null or to_st.origin.y < from_st.origin.y else 1.0      # -1：往上（镜头 y 变小）
	var c0: Vector2 = level.cam.position.round()
	level.camera_hold_at(c0)
	await _fade_people(false, 0.35, with)
	level.camera_pan(c0 + Vector2(0, dir * PAN_SHIFT), PAN_HALF, Tween.EASE_IN)
	await level.fade_to_black(PAN_HALF)
	var target := Vector2(to_st.clamp_cam_x(x + chen.facing * 24.0), to_st.cam_y())
	_teleport(room, x, with, false)
	_fade_place(st)
	for n in [chen] + with.map(func(w): return npc(str(w))):
		if n != null:
			(n as Node2D).modulate.a = 0.0
	var start := target - Vector2(0, dir * PAN_SHIFT)
	level.camera_hold_at(start)
	level.cam.position = start.round()
	level.camera_pan(target, PAN_HALF, Tween.EASE_OUT)
	await level.fade_from_black(PAN_HALF)
	level.camera_hold_at(target)
	await _fade_people(true, 0.35, with)
	level.camera_release()


## 边走边黑：朝出口那头走着黑下去，淡入时从那个房间的入口一头走进来
func _walk_fade(room: String, x: float, with: Array, st: Dictionary, arrive: float) -> void:
	var fs: Node2D = world.stage(world.room)
	var dir := float(chen.facing)
	if fs != null:
		var p: Dictionary = fs.portal_to_room(room)
		if str(p.get("edge", "")) == "left":
			dir = -1.0
		elif str(p.get("edge", "")) == "right":
			dir = 1.0
		else:
			dir = 1.0 if chen.position.x > fs.center().x else -1.0
	chen.auto_dir = dir
	for w in with:
		var n := npc(str(w))
		if n != null and npcs.values().has(n):
			n.walk_to(n.position.x + dir * 120.0)
	await level.fade_to_black(0.8)
	chen.auto_dir = 0.0
	var ts: Node2D = world.stage(room)
	var to := x if is_nan(arrive) else arrive
	var start := x
	if is_nan(arrive) and ts != null:
		var s_in := 1.0 if (x - ts.origin.x) < ts.size.x / 2.0 else -1.0     # 从近的那头走进来
		start = x - s_in * 40.0
		var w2: Vector2 = ts.walls()
		start = clampf(start, w2.x + 2.0, w2.y - 2.0)
	_teleport(room, start, with, true)
	_fade_place(st)
	await _wait(0.2)
	await _arrive_walk(to)


# ----------------------------------------------------------------------- 小游戏 {"do": "mechanic"}
func _mechanic(st: Dictionary) -> void:
	var mid := str(st.get("id", ""))
	var path := "res://scripts/%s.gd" % mid
	if not ResourceLoader.exists(path):
		_warn_once("mechanic：脚本 %s 还没有，当它玩完了" % path)
		_mech_done(mid)
		return
	var gd := load(path) as GDScript
	if gd == null or not gd.can_instantiate():
		_warn_once("mechanic：脚本 %s 编译不过，当它玩完了" % path)
		_mech_done(mid)
		return
	var m = gd.new()
	if ff:
		if m.has_method("ff"):
			m.ff(self, st)
		_mech_done(mid)
		return
	print("MECH %s start" % mid)
	mech_running = mid
	if auto != "":
		if m.has_method("auto"):
			await m.auto(level, world, self, st)
		elif m.has_method("ff"):
			m.ff(self, st)
	elif m.has_method("run"):
		await m.run(level, world, self, st)
	mech_running = ""
	_mech_done(mid)
	print("MECH %s returned" % mid)


func _mech_done(mid: String) -> void:
	var p := mech_load(mid)
	p["_done"] = true
	mech_save(mid, p)


func mech_load(mid: String) -> Dictionary:
	var v = JSON.parse_string(str(StoryState.props.get(MECH_PREFIX + mid, "{}")))
	return v if v is Dictionary else {}


func mech_save(mid: String, d: Dictionary) -> void:
	StoryState.set_prop(MECH_PREFIX + mid, JSON.stringify(d))


## 小游戏里播一串剧本步骤（say / walk / anim / prop……），播完返回（goto / if 之类跳 scene 的步骤：返回那个 scene 名，不跟过去）
func run_steps(steps: Array) -> String:
	for st in steps:
		if st is Dictionary:
			var g: String = await _step(st)
			if g != "":
				return g
	return ""


## 临时加几个可互动的点，等玩家互动其中一个：返回 {id, item}
func wait_interact(spots: Array) -> Dictionary:
	if spots.is_empty():
		return {"id": "", "item": ""}
	_mech_spots.clear()
	for sp in spots:
		if not sp is Dictionary:
			continue
		var sid := str(sp.get("id", ""))
		var h := {"id": "_mech_" + sid, "_mech": sid, "at": sp.get("at", 0), "room": str(sp.get("room", world.room)),
			"label": sp.get("label", {"zh": sid}), "scene": ""}
		if sp.has("range"):
			h["range"] = sp["range"]
		var acc := {}
		for it in sp.get("accepts", []):
			acc[str(it)] = "__mech:" + sid
		if not acc.is_empty():
			h["accepts"] = acc
		_mech_spots.append(h)
	hotspots.defs.append_array(_mech_spots)
	_mech_hit = {}
	mech_wait = true
	var was_free := free_walk
	busy = false
	free_walk = false
	level.story_end()
	hotspots.active = true
	while _mech_hit.is_empty():
		await mech_hit_sig
	mech_wait = false
	for h in _mech_spots:
		hotspots.defs.erase(h)
	_mech_spots.clear()
	busy = true
	free_walk = was_free
	hotspots.active = false
	level.story_begin(false)
	return _mech_hit


func _mech_resolve(sid: String, item: String) -> void:
	if not mech_wait:
		return
	_mech_hit = {"id": sid, "item": item}
	mech_hit_sig.emit()


## 特写面板：返回点到的 zone id（关掉 = ""）
func closeup(spec: Dictionary) -> String:
	if ff:
		return ""
	var ai := -2
	if auto != "":
		ai = -1
		var zs: Array = spec.get("zones", [])
		if not zs.is_empty():
			var opts: Array = []
			for z in zs:
				opts.append({"id": str(z.get("id", "")), "scene": str(z.get("scene", ""))})
			ai = _auto_pick({"options": opts})
			if ai < 0 and not spec.get("close", true):
				ai = 0
	var r: String = await closeup_ui.open(spec, ai)
	return r


## --story_check：多房间章节的新步骤
func _validate_room_step(id: String, kind: String, st: Dictionary, refs: Dictionary) -> Array[String]:
	var out: Array[String] = []
	match kind:
		"todo_mechanic":
			out.append("info: scene %s：todo_mechanic %s 还没换成 mechanic（跳过）" % [id, st.get("id")])
		"mechanic":
			var path := "res://scripts/%s.gd" % str(st.get("id", ""))
			if not ResourceLoader.exists(path):
				out.append("scene %s：mechanic 的脚本 %s 不存在" % [id, path])
			elif not (load(path) as GDScript).can_instantiate():
				out.append("scene %s：mechanic 的脚本 %s 编译不过" % [id, path])
			else:
				var m = (load(path) as GDScript).new()
				for fn in ["run", "auto", "ff"]:
					if not m.has_method(fn):
						out.append("scene %s：mechanic %s 没有 %s()" % [id, st.get("id"), fn])
				if m.has_method("check"):
					for l in m.check(self, st):
						out.append("scene %s：mechanic %s：%s" % [id, st.get("id"), l])
		"form":
			var n := npc(str(st.get("who", "")))
			if n == null or not n.has_method("set_form"):
				out.append("scene %s：form 的 who %s 不是通用角色" % [id, st.get("who")])
		"follow":
			if npc(str(st.get("who", ""))) == null:
				out.append("scene %s：follow 的 who 不认识 %s" % [id, st.get("who")])
		"pose":
			var pn := npc(str(st.get("who", "")))
			if pn == null or not npcs.values().has(pn):
				out.append("scene %s：pose 的 who %s 不是通用角色" % [id, st.get("who")])
		"water":
			if world.stage(str(st.get("room", ""))) == null:
				out.append("scene %s：water 的 room 不认识 %s" % [id, st.get("room")])
		"closeup":
			if str(st.get("img", st.get("id", ""))) == "":
				out.append("scene %s：closeup 没有 img" % id)
			elif CLOSEUP_GD.tex_path(str(st.get("img", st.get("id", ""))), str(st.get("state", ""))) == "":
				out.append("info: scene %s：特写图 closeup_%s 还没有（占位）" % [id, st.get("img", st.get("id", ""))])
			for z in st.get("zones", []):
				var zs := str(z.get("scene", ""))
				if zs != "":
					refs[zs] = true
					if not scenes.has(zs):
						out.append("scene %s：closeup zone %s 的 scene %s 不存在" % [id, z.get("id"), zs])
	return out


## 走到房间一头的入口（level_forest.gd 的 _update_stage_portal）：用 room.json portals 那一项的转场换过去
func portal_room(pt: Dictionary) -> void:
	if busy:
		return
	var room := str(pt.get("to", ""))
	var ts: Node2D = world.stage(room)
	if ts == null:
		return
	var x := NAN
	if str(pt.get("at", "")) != "" and world.has_marker(str(pt["at"])):
		x = float(world.resolve(str(pt["at"]))["x"])
	else:
		var w: Vector2 = ts.walls()
		x = w.x + 30.0 if str(pt.get("edge", "right")) == "right" else w.y - 30.0
	busy = true
	hotspots.active = false
	level.story_begin(false)
	var with: Array = []
	for f in follow:
		var n := npc(str(f))
		if n != null and n.visible and str(_npc_room.get(n.name, "")) == world.room:
			with.append(str(f))
	await _fade_to({"room": room, "at": x, "kind": str(pt.get("kind", "walk_fade")), "with": with})
	busy = false
	level.story_end()



## 起飞（河流篇 depart，方案 5.7）：房间里的飞机物件（river_bank_plane）预热 → 反重力竖直升起（smoothstep）→ 往左上加速飞出画面。
## 和森林起飞一样用 ship_glow.gd 的泛光；没有这个物件就什么都不做（直接淡出）。动画只挪位置，不换帧速。
const SHIP_GLOW := preload("res://scripts/ship_glow.gd")
const TAKEOFF_PLANE := "river_bank_plane"


func _stage_takeoff() -> void:
	var sg: Node2D = world.cur_stage()
	var plane: Sprite2D = sg.object(TAKEOFF_PLANE) if sg != null else null
	if plane == null or not plane.visible or ff:
		return
	level.camera_hold_at(level.cam.position)
	var c: Dictionary = sg.ocfg[TAKEOFF_PLANE]
	var fw := int(c.get("w", plane.texture.get_width() / plane.hframes))
	var glow: Node2D = SHIP_GLOW.new()
	plane.add_child(glow)
	glow.set_from_texture(plane.texture, Vector2.ZERO, Rect2i(plane.frame * fw, 0, fw, int(c.get("h", plane.texture.get_height()))))
	var p0 := plane.position
	var t := 0.0
	# 预热：船底泛光亮起、1 像素抖
	while t < 1.2:
		var d := get_process_delta_time()
		t += d
		glow.strength = 0.3 * clampf(t / 0.8, 0.0, 1.0)
		glow.dir = 0.0
		glow.step(d)
		plane.position = p0 + Vector2(0, -1 if fmod(t, 0.16) < 0.08 and t > 0.6 else 0)
		await get_tree().process_frame
	# 竖直升 40 像素
	t = 0.0
	var prev := p0.y
	while t < 1.6:
		var d2 := get_process_delta_time()
		t += d2
		var k := clampf(t / 1.6, 0.0, 1.0)
		plane.position.y = round(p0.y - 40.0 * k * k * (3.0 - 2.0 * k))
		glow.drive((plane.position.y - prev) / maxf(d2, 0.001), d2)
		prev = plane.position.y
		await get_tree().process_frame
	# 往左上加速飞出
	t = 0.0
	var p1 := plane.position
	var fading := false
	while t < 2.0:
		var d3 := get_process_delta_time()
		t += d3
		plane.position = (p1 + Vector2(-110.0, -45.0) * t * t).round()
		glow.drive(-90.0 * t, d3)
		if t > 1.2 and not fading:
			fading = true
			level.fade_to_black(0.7)
		await get_tree().process_frame
	glow.queue_free()
	plane.visible = false



# ----------------------------------------------------------------------- 自动玩：多房间找路
## 这一房间没有不换地方就能推进的点了：找「还有事做」的房间（有会推进剧情、不换地方的点），按房间之间的出口（scene 里 fade_to 到别的房间的 hotspot）
## 广度优先找路，返回第一步要点的出口。出口本身不受「来过」限制（来回走不算进展）。
func _multi_plan() -> Dictionary:
	var want := {}
	var exits := {}                     # 房间 → [{p, to}]
	var rooms: Array = world.stages.keys()
	if world.cockpit != null:
		rooms.append("cockpit")
	for r in rooms:
		exits[r] = []
		for p in hotspots.available(str(r)):
			var h: Dictionary = p["h"]
			if hotspots.is_enter(h) and not bool(h.get("cutscene", false)):
				continue
			var sc := str(h.get("scene", ""))
			var to := _dest_room(sc, str(r))
			var id := str(h.get("id", ""))
			var fresh := not (_visited.has(id) and int(_visited[id]) == StoryState.progress())
			if to != "" and to != str(r):
				if _would_progress_flags(sc) or (ff and _ff_target != "" and _leads_to(sc, _ff_target)):
					want[str(r)] = true           # 换地方的同时会推进剧情（设新 flag）：这个房间就有事做
				(exits[r] as Array).append({"p": p, "to": to})
			elif is_progress_hotspot(h) and fresh:
				want[str(r)] = true
	if want.is_empty():
		return {}
	var start: String = world.room
	var prev := {start: null}
	var q: Array = [start]
	while not q.is_empty():
		var r: String = q.pop_front()
		if want.has(r) and r != start:
			break
		for e in exits.get(r, []):
			var to: String = e["to"]
			if not prev.has(to):
				prev[to] = {"from": r, "e": e}
				q.append(to)
	if want.has(start):
		# 这间就有「换地方也推进剧情」的出口：直接点它
		for e in exits.get(start, []):
			if _would_progress_flags(str(e["p"]["h"].get("scene", ""))):
				return {"kind": "hotspot", "x": float(e["p"]["x"]), "p": e["p"], "exit": true}
	var goal := ""
	for r in want:
		if prev.has(r) and str(r) != start:
			if goal == "" or _hops(prev, str(r)) < _hops(prev, goal):
				goal = str(r)
	if goal == "":
		return {}
	var cur := goal
	while prev[cur] != null and str(prev[cur]["from"]) != start:
		cur = str(prev[cur]["from"])
	var ed: Dictionary = prev[cur]["e"]
	return {"kind": "hotspot", "x": float(ed["p"]["x"]), "p": ed["p"], "exit": true}


func _hops(prev: Dictionary, r: String) -> int:
	var n := 0
	while prev.get(r) != null and n < 50:
		r = str(prev[r]["from"])
		n += 1
	return n


## scene 一路下去第一个 fade_to 到哪个房间（没有 = ""）
func _dest_room(sc: String, from: String) -> String:
	for sid in _reach(sc, {}):
		for st in scenes.get(sid, []):
			if st is Dictionary and str(st.get("do", "")) == "fade_to":
				return str(st.get("room", from))
	return ""


## 只看「设新 flag / 给新东西 / 小游戏」（不算换地方）
func _would_progress_flags(s: String, seen := {}) -> bool:
	if seen.has(s) or not scenes.has(s):
		return false
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		match str(st.get("do", "")):
			"flag", "count":
				if st.has("set") and not StoryState.has(str(st["set"])):
					return true
			"give":
				if st.has("item") and not Inventory.has(str(st.get("item", ""))):
					return true
			"end_chapter":
				return true
			"mechanic":
				if not bool(mech_load(str(st.get("id", ""))).get("_done", false)):
					return true
			"goto":
				if _would_progress_flags(str(st.get("scene", "")), seen):
					return true
			"if":
				if _would_progress_flags(str(st.get("then", "")), seen) or _would_progress_flags(str(st.get("else", "")), seen):
					return true
			"choice", "pick":
				for o in st.get("options", []):
					if _would_progress_flags(str(o.get("scene", "")), seen):
						return true
	return false



## 下水 / 上水（10-30 作者：水面线漫过人 + 镜头平移不好看）：慢慢黑下去（带一声入水 / 出水）→ 黑着换房间 → 慢慢亮起来，
## 亮起来时已经在水底 / 岸上。和别的黑屏转场一样 0.8 秒黑、0.8 秒亮，正弦缓入缓出；人不淡，跟着画面一起黑
func _dive_fade(room: String, x: float, with: Array, st: Dictionary, down: bool) -> void:
	var nm := "splash_in" if down else "splash"
	if Time.get_ticks_msec() - int(_sfx_t.get(nm, -100000)) > 1500:
		_sfx({"name": nm, "db": -3.0})             # 剧本下水前自己放过 splash_in 的，不再叠一遍
	level.camera_hold_at(level.cam.position)
	await level.fade_to_black(0.8)
	_teleport(room, x, with, true)
	_fade_place(st)
	level.camera_release()
	level._snap_camera()
	await _wait(0.2)
	await level.fade_from_black(0.8)
