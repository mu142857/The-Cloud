extends Node2D
## 第一关：木星的森林。开场、标题、坠毁、捡起第一块发光木头，然后整个森林章节由剧本引擎接着播到飞船起飞。
##
## 章节剧情：scripts/story_runner.gd（读 data/story_forest.json，见 docs/forest_chapter.md）。这里只负责：
##   开场 / 标题 / 坠毁 / 木头拾取过场（原来的），晨爬起来以后播剧本的 intro，木头过场里播剧本 at = wood 的那个 scene；
##   自由走的时候：hotspot 互动（E / 空格 / 回车 / 点那个东西）、走进 trigger:"enter" 的点自动触发、左右不可见的墙；
##   剧情播放时锁晨、把按键转给对话框；树屋室内镜头固定；背包里所有物品 + 日记；起飞过场；章节结束卡。
## 开场一起坠毁的外星人同伴（Alien）在森林里不出现（ALIEN_IN_FOREST = false，代码留着，以后河边用）。
##
## 流程（state）：
##   HEADPHONES  黑屏，「建议佩戴耳机」+「点击或按任意键继续」（顺便解锁网页版的声音）
##   INTRO       雨声淡入 → 两声远雷 → 黑屏淡入森林
##   TITLE       标题界面：游戏名、正中「开始游戏」、右下角设置齿轮；镜头慢慢左右漂
##   CRASH       开场动画（上下黑边）：三次闪电 + 近雷 → 冒烟的飞船从右上斜着坠下 → 撞地（震屏、尘土、浓烟）
##               → 晨和另一个外星人（梧桐画的旧主角，npc_alien.gd）先后被甩出来、脸朝下趴着 → 她先爬起来，晨再爬起来
##               → 对话「啊……糟糕……」。确认键 / 点击按两次可以跳过。她之后一直站在残骸尾巴旁边待机（不说话）。
##   PLAY        自由走（←/→、A/D，或者鼠标点地面走过去）。发光木头上方有一个很轻的小箭头。
##   CINE        走到木头旁边：黑边滑入、锁操作、晨自己走到木头前捡起来 → 木头飞进背包 → 对话「太好了……」
##               → 燃烧值从 10 滚到 60，「燃烧值到 200 就能起飞」→ 收进左上角 → 黑边滑出、恢复操作
## 任何时候：Esc / 右下角齿轮 = 设置；Tab / B / I / 右上角背包图标 = 背包（捡到第一件东西以后才出现）。
## 章节结束卡出来 3 秒以后按任意键回标题（重新开始）。
## 只在 debug 构建：标题界面按 F1~F5 进 forest / river / underwater / cloud / flight 的测试场景，Esc 回标题（见 SceneBrowser）。
##
## 调试（命令行 -- 后面，建议加 --fixed-fps 60 让时间可重复）：
##   --stage=headphones|title|settings|crash|play|wood|bag   直接跳到某一段
##   --lang=zh|en       临时换语言（不存）
##   --quality=lite     临时换画质（不存）
##   --shot=绝对路径.png --shot_at=秒   这一段开始后多少秒存一张图后退出（默认 1 秒）
##   --shots=目录 --start=帧 --every=帧 --count=张   连拍 shot_000.png …
##   --autoplay         耳机提示自己跳过、标题界面自己点开始，能走的时候自己往右走（录 GIF / 完整跑一遍用）
##   --title_hot        标题界面的「开始」显示成悬停的样子（截图看悬停反馈用）
##   --browse=1..5 --browse_out=目录   标题界面 0.5 秒后自己按 F1..F5 进测试场景，2.5 秒后存 目录/scene.png、
##                      自己按 Esc 回标题，再过 2 秒存 目录/back.png 后退出（测场景浏览用；别同时给 --shot，测试场景自己也认它）
##   --story=路径       用哪份剧本（默认 data/story_forest.json，没有就 data/story_forest_sample.json）
##   --beat=flag名      直接跳到那个节拍（剧情瞬间过一遍到设这个 flag 的 scene 播完；flags、物品、NPC 位置都补齐）
##   --story_auto[=full]  自动玩整章到结束卡，打印 STORY_DONE 统计后退出（full = 闲聊、选错的分支也走）
##   --story_shots=目录   每播到一个新 scene 存一张图
##   --story_shot_delay=秒  每个 scene 开始后多久存图（默认 0.5）
##   --story_check      只检查剧本、打印 STORY_CHECK 后退出
##   --story_fuzz=秒 [--seed=n]  像人一样乱玩：随机按方向键（按住一会儿）、互动、确认、背包、Esc、乱点鼠标，玩这么多秒；
##                      一直检测「没有对话框、没有剧情在播、没有黑屏，但晨收不到输入超过 3 秒」→ 打印 SOFTLOCK 和当时的状态；
##                      剧情的某一步停了 20 秒以上、又没有对话框 / 点选 / 带路在等人 → STUCK_SCENE。结束打印 FUZZ_DONE。
##                      可以和 --beat 一起用（从某个节拍开始乱玩）
##   --dev [--dev_tab=0..3]  一开始就打开 F8 面板（截图 / 测面板用）
##   F8（只在 debug 构建）：开发者面板（跳节拍、传送、状态、快走 / 跳过对话 / 显示范围 / 雾 / 前景层开关、重开本章……），
##                      见 scripts/dev_panel.gd 和 docs/forest_chapter.md 末尾
##   --chen_x=x         （和 --beat 一起）跳完以后让晨站到这个 x（截互动提示用）
##   --open_bag=物品id  （和 --beat 一起）跳完以后打开背包、选中这件（截背包 / 日记用）
## 例：Godot --path . --fixed-fps 60 -- --stage=crash --shot=/tmp/a.png --shot_at=3.6
##     Godot --path . --fixed-fps 60 -- --story_auto --story_shots=/tmp/shots

enum S { HEADPHONES, INTRO, TITLE, CRASH, PLAY, CINE }

const LOOK := 36.0            # 镜头往晨面朝的方向多看多少像素（和 forest_test 一样）
const FOLLOW := 3.0
const TITLE_CAM_X := 236.0    # 标题界面镜头中心；晨爬起来时镜头也在这
const CHEN_X := 250.0         # 晨趴着的地方
const WRECK_X := 120.0        # 坠毁飞船（锚点 = 船身中心的 x 和地面）
const ALIEN_X := 204.0        # 另一个外星人（梧桐画的旧主角）趴着、站着的地方：残骸尾巴旁边，在晨左边，不挡去木头的路
const WOOD_X := 372.0         # 发光木头
const PICK_DIST := 26.0       # 晨走到离木头这么近就进入拾取过场
const LIE_LIFT := 9.0         # 没有 lie / getup 动画时的老办法：趴着时精灵往上抬几像素（转 90° 以后身体的厚度一半在地下）
const CHEN_GD := preload("res://scripts/chen.gd")
const STORY_GD := preload("res://scripts/story_runner.gd")
const ALIEN_IN_FOREST := false
const DEV_GD := preload("res://scripts/dev_panel.gd")
const DEV_BEAT_META := "level_forest_dev_beat"
const DEV_STAGE_META := "level_forest_dev_stage"
const DEV_OPEN_META := "level_forest_dev_open"   # 开场的外星人同伴：森林里不出现（那套图以后是河边的泥芙）
## 晨的精灵配置里有没有「趴着 / 爬起来」两段（tools/level1_chen_getup.py）。没有就退回把站立帧转 90° 的老办法。
var _has_getup: bool = CHEN_GD.ANIMS.has("lie") and CHEN_GD.ANIMS.has("getup")
## getup 一段多长（秒），和各帧什么时候换（跪坐、站直那两下扬一点土）
const GETUP_KNEEL_AT := 0.3       # chen.gd 里 getup 每帧 100ms：第 3 帧（跪坐）
const GETUP_STAND_AT := 0.6       # 第 6 帧（站直）
const GETUP_TIME := 0.7

## 调试场景浏览（只在 debug 构建、标题界面）：F1~F5
const TEST_SCENES := {
	KEY_F1: "res://scenes/forest_test.tscn",
	KEY_F2: "res://scenes/river_test.tscn",
	KEY_F3: "res://scenes/underwater_test.tscn",
	KEY_F4: "res://scenes/cloud_test.tscn",
	KEY_F5: "res://scenes/flight_test.tscn",
}
const SELF_SCENE := "res://scenes/level_forest.tscn"

## 标题界面
const TITLE_Y := 54.0
const TITLE_COLOR := Color("#b9cdc1")     # 偏暗的薄荷灰（比晨暗，比背景亮）
const TITLE_SPACING := 3
const SUB_COLOR := Color("#7f988b")
const SUB_SPACING := 4
const START_Y := 150.0
const START_COLOR := Color("#a3b8ad")
const START_HOT := Color("#e2ebe5")
const START_SPACING := 2
const GEAR_A := 0.45
const LANG_ON := Color("#a3b8ad")      # 左下角语言切换：当前语言
const LANG_OFF := Color("#56695f")     # 另一种语言（悬停时亮成 START_HOT）

## 闪电：不再是整屏白闪，而是冷色的天光从林冠后面亮一下（远景几层被照亮，近处的树干、林冠成了剪影），
## 再叠一层很淡的冷色。下面是每层被照亮多少（0 = 不动）和冷光的颜色（乘到图层上，>1 = 变亮）。
const FLASH_LAYERS := {"Sky": 1.0, "Ridge": 0.9, "Far": 0.75, "MidFar": 0.45, "Mid": 0.18}
const FLASH_GAIN := Color(0.35, 0.62, 0.9)      # 闪到最亮时远景乘 (1+0.35, 1+0.62, 1+0.9)：偏青蓝，不是白
const FLASH_TINT := Color(0.55, 0.72, 0.86)      # 整屏那层薄薄的冷光
const FLASH_TINT_A := 0.09                       # 它最多这么不透明
const IMPACT_TINT := Color(1.0, 0.72, 0.45)      # 撞地那一下是暖的、很弱
const BAR_H := 26             # 电影黑边高度
const BAG_SLOTS := 24         # 背包格子 4 × 6
const DLG_TIME := 10.0        # 对话框最多停多久
const DLG_WALK := 56.0        # 晨离开说话的地方这么远，对话框就淡出

const SFX_DIR := "res://audio/sfx/"
const FIREFLIES := preload("res://scripts/fireflies.gd")
const TEX_BAG := preload("res://art/level1/icon_bag.png")
const TEX_GEAR := preload("res://art/level1/icon_gear.png")
const TEX_FLAME := preload("res://art/level1/icon_flame.png")
const TEX_HEADPHONES := preload("res://art/level1/icon_headphones.png")

@onready var cam: Camera2D = $Camera
@onready var chen: Node2D = $Chen
@onready var shafts: Node2D = $Main/Shafts
@onready var shadows: Node = $ForestShadows
@onready var puffs_back: Node2D = $PuffsBack
@onready var puffs_front: Node2D = $PuffsFront
@onready var wreck: Sprite2D = $Wreck
@onready var ship: Sprite2D = $Ship
@onready var alien: Node2D = $Alien
@onready var wood: Node2D = $Wood
@onready var wood_glow: Sprite2D = $Wood/Glow
@onready var wood_hint: Sprite2D = $Wood/Hint
@onready var flash: ColorRect = $Overlay/Flash
@onready var ui: CanvasLayer = $UI
@onready var fade: ColorRect = $Top/Fade

var state := S.HEADPHONES
var _t := 0.0                 # 总时间
var _state_t := 0.0           # 进入当前 state 多久了
var _seq: Array = []          # 定时事件 [[秒, Callable], …]，按时间排好
var _seq_t := 0.0
var _tweens: Array[Tween] = []   # 过场里的 tween，跳过时一起停掉
var _shake := 0.0
var _shake_amp := 0.0
var _rng := RandomNumberGenerator.new()
var _fireflies: Node2D
var _ship_frame_t := 0.0
var _skip_armed := 0.0        # >0：已经按过一次，这段时间内再按就跳过
var _walk_target := NAN       # 鼠标点地面：走到这个 x
var _cine_target := NAN       # 拾取过场：自动走到这个 x
var _moved_from := NAN        # 晨开始能动时的位置（用来藏「← →」提示）
var _hint_wait := 0.0
var _bag_seen := false
var _flash_k := 0.0           # 闪电的亮度 0..1（tween 它，_apply_flash 每帧套到远景和那层冷光上）
var _impact_k := 0.0          # 撞地那一下的暖光 0..1
var _title_k := 0.0           # 标题淡入进度 0..1（字往上飘 3 像素，按整像素走）
var _start_hot := 0.0         # 「开始」悬停 / 聚焦的高亮 0..1（两边的小横线跟着伸出来）
var _start_hover := false
var _start_fc := Color(0, 0, 0, 0)   # 「开始」现在的字色（变了才重设，免得每帧发主题变更）

# ---- 对话框
var _dlg: PanelContainer
var _dlg_name: Label
var _dlg_text: Label
var _dlg_on := false
var _dlg_age := 0.0
var _dlg_x := 0.0
var _dlg_chars := 0.0
var _dlg_cps := 26.0
var _dlg_tw: Tween

# ---- 界面
var _title_root: Control
var _title_label: Label
var _title_sub: Label         # 标题下面另一种语言的名字（英文版写「云」，中文版写 THE CLOUD）
var _title_lines: Array[ColorRect] = []   # 副标题两边的细线
var _start_btn: Button
var _start_marks: Array[ColorRect] = []   # 「开始」两边悬停时伸出来的小横线
var _gear: TextureButton
var _lang_corner: HBoxContainer   # 标题界面左下角的「EN / 中文」，跟着标题一起出现、消失
var _lang_btns := {}
var _bag_btn: TextureButton
var _hud_burn: HBoxContainer
var _hud_burn_label: Label
var _bars: Array[ColorRect] = []
var _skip_label: Label
var _keys_hint: Label
var _burn_pop: Control
var _burn_pop_num: Label
var _burn_pop_sub: Label
var _burn_pop_fill: ColorRect
var _burn_shown := 0.0
var _hp_root: Control
var _hp_label: Label
var _hp_any: Label
var _dim: ColorRect
var _settings: PanelContainer
var _settings_widgets := {}
var _bag: Panel
var _bag_slots: Array[Button] = []
var _bag_sel := 0
var _bag_w := {}
var _panel_prev_focus: Control

# ---- 剧本
var story: Node                 # story_runner.gd
var _story_path := ""
var _story_auto := ""
var _story_shots := ""
var _story_shot_delay := 0.5
var _story_check := false
var _beat := ""
var _story_bars := false
var _burn_sub_off := false
var _pending_hs: Dictionary = {}   # 鼠标点了一个 hotspot：走过去，到了就互动
var _wall_block := false
var _end_t := -1.0
var _fuzz := 0.0                  # --story_fuzz：乱玩多少秒
var _fuzz_rng := RandomNumberGenerator.new()
var _fuzz_t := 0.0
var _fuzz_next := 0.0
var _fuzz_hold := 0
var _fuzz_hold_t := 0.0
var _fuzz_xmin := INF
var _fuzz_xmax := -INF
var _lock_t := 0.0
var _lock_reported := false
var softlocks := 0
var _dev: Node                    # F8 开发者面板（scripts/dev_panel.gd）
var _dev_tab := 0
var _dbg_chen_x := NAN
var _dbg_bag := ""

# ---- 声音
var _rain: AudioStreamPlayer
var _crackle: AudioStreamPlayer2D

# ---- 调试
var _shot := ""
var _shot_at := 1.0
var _shots_dir := ""
var _shots_start := 0
var _shots_every := 3
var _shots_count := 60
var _shots_saved := 0
var _frame := 0
var _autoplay := false
var _debug_stage := ""
var _browse := 0
var _browse_out := ""
var _stage_t := 0.0


func _ready() -> void:
	if not GameSettings.loaded:
		GameSettings.load_and_apply()      # 直接 F6 跑这个场景时
	_rng.seed = 7
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--stage="):
			_debug_stage = a.trim_prefix("--stage=")
		elif a.begins_with("--lang="):
			GameSettings.set_lang(a.trim_prefix("--lang="))
		elif a.begins_with("--quality="):
			GameSettings.quality = a.trim_prefix("--quality=")
		elif a.begins_with("--shot="):
			_shot = a.trim_prefix("--shot=")
		elif a.begins_with("--shot_at="):
			_shot_at = float(a.trim_prefix("--shot_at="))
		elif a.begins_with("--shots="):
			_shots_dir = a.trim_prefix("--shots=")
		elif a.begins_with("--start="):
			_shots_start = int(a.trim_prefix("--start="))
		elif a.begins_with("--every="):
			_shots_every = int(a.trim_prefix("--every="))
		elif a.begins_with("--count="):
			_shots_count = int(a.trim_prefix("--count="))
		elif a == "--title_hot":
			_start_hover = true
		elif a.begins_with("--browse="):
			_browse = int(a.trim_prefix("--browse="))
		elif a.begins_with("--browse_out="):
			_browse_out = a.trim_prefix("--browse_out=")
		elif a == "--autoplay":
			_autoplay = true
		elif a.begins_with("--story="):
			_story_path = a.trim_prefix("--story=")
		elif a == "--story_auto":
			_story_auto = "main"
		elif a.begins_with("--story_auto="):
			_story_auto = a.trim_prefix("--story_auto=")
		elif a.begins_with("--story_shots="):
			_story_shots = a.trim_prefix("--story_shots=")
		elif a.begins_with("--story_shot_delay="):
			_story_shot_delay = float(a.trim_prefix("--story_shot_delay="))
		elif a.begins_with("--beat="):
			_beat = a.trim_prefix("--beat=")
		elif a == "--story_check":
			_story_check = true
		elif a == "--dev_test":
			if not Engine.has_meta(DEV_BEAT_META):
				Engine.set_meta(DEV_OPEN_META, true)
		elif a == "--dev":
			Engine.set_meta(DEV_OPEN_META, true)
		elif a.begins_with("--dev_tab="):
			_dev_tab = int(a.trim_prefix("--dev_tab="))
		elif a.begins_with("--story_fuzz="):
			_fuzz = float(a.trim_prefix("--story_fuzz="))
		elif a.begins_with("--seed="):
			_fuzz_rng.seed = int(a.trim_prefix("--seed="))
		elif a.begins_with("--chen_x="):
			_dbg_chen_x = float(a.trim_prefix("--chen_x="))
		elif a.begins_with("--open_bag="):
			_dbg_bag = a.trim_prefix("--open_bag=")
	if _shots_dir != "":
		DirAccess.make_dir_recursive_absolute(_shots_dir)
	if _story_shots != "":
		DirAccess.make_dir_recursive_absolute(_story_shots)
	if _debug_stage != "" or _shot != "" or _shots_dir != "" or _autoplay or _browse > 0 or _story_auto != "" or _beat != "" or _story_check or _fuzz > 0.0:
		GameSettings.no_save = true
		AudioServer.set_bus_mute(0, true)    # 截图 / 录像时不出声，也不吃真的键盘鼠标（见 _input）

	chen.input_enabled = false
	cam.position = Vector2(TITLE_CAM_X, 135.0)
	# 没有存档：每次进第一关都是新游戏
	Inventory.owned.clear()
	StoryState.reset()
	# 光柱照到晨身上（lite 档光柱关了就是 0；树屋室内没有光柱）
	chen.set_env("forest", func(c):
		if story != null and story.world != null and story.world.in_room():
			return 0.0
		return preload("res://scripts/env_light.gd").polygon_shafts(c, shafts))
	_place_world()
	_apply_quality()
	_build_audio()
	_build_ui()
	_build_story()
	_retext()
	_enter_headphones()
	if Engine.has_meta(BACK_META):          # 从测试场景按 Esc 回来：直接到标题（雨声照常）
		Engine.remove_meta(BACK_META)
		_skip_to_title()
	if _story_check:
		for line in story.validate():
			print("STORY_CHECK " + line)
		print("STORY_CHECK done: %s, %d scenes, %d hotspots" % [story.path, story.scenes.size(), story.hotspot_defs.size()])
		get_tree().quit()
		return
	# F8 面板「跳节拍 / 重开本章」：重新载入本场景，再在这里接着跳（和 --beat / --stage 同一套）
	if Engine.has_meta(DEV_BEAT_META):
		_beat = str(Engine.get_meta(DEV_BEAT_META))
		_debug_stage = ""                   # 面板说的算（命令行的 --stage 重新载入后还在）
		Engine.remove_meta(DEV_BEAT_META)
		Engine.set_meta(DEV_OPEN_META, true)
	if Engine.has_meta(DEV_STAGE_META):
		_debug_stage = str(Engine.get_meta(DEV_STAGE_META))
		_beat = ""
		Engine.remove_meta(DEV_STAGE_META)
		Engine.set_meta(DEV_OPEN_META, true)
	if _debug_stage != "":
		_jump(_debug_stage)
	if _beat != "":
		_jump_beat.call_deferred(_beat)
	if Engine.has_meta(DEV_OPEN_META):
		Engine.remove_meta(DEV_OPEN_META)
		toggle_dev.call_deferred()


func _build_story() -> void:
	var root: Control = ui.get_node("Root")
	story = STORY_GD.new()
	story.name = "Story"
	story.load_story(_story_path)
	add_child(story)
	story.setup(self, root)
	root.move_child(story.dlg, _dim.get_index())        # 对话框在黑边上面、面板下面
	story.auto = _story_auto
	story.shots_dir = _story_shots
	story.shot_delay = _story_shot_delay
	if _autoplay or _shot != "" or _shots_dir != "":
		story.dlg.auto_delay = 2.5          # 这几种调试模式不吃按键：剧情对话自己往下走（像原来的定时对话框）
	story.world.extra_rects["wreck"] = func() -> Rect2:
		if not wreck.visible:
			return Rect2()
		return Rect2(wreck.position + wreck.offset + Vector2(20, 20), wreck.texture.get_size() - Vector2(40, 20))
	story.world.on_pseudo = _on_pseudo_prop
	if _story_auto != "" or _beat != "":
		for l in story.validate():
			if not l.begins_with("info:"):
				print("STORY_CHECK " + l)


# ======================================================================= 世界摆放
func _ground(x: float) -> float:
	return round(chen.ground_fn.call(x))


func _place_world() -> void:
	wreck.position = Vector2(WRECK_X, _ground(WRECK_X) + 1)
	wood.position = Vector2(WOOD_X, _ground(WOOD_X))
	chen.position = Vector2(CHEN_X, _ground(CHEN_X) + 1)
	alien.position = Vector2(ALIEN_X, _ground(ALIEN_X) + 1)
	alien.watch(chen)
	if not ALIEN_IN_FOREST:
		alien.visible = false


func _apply_quality() -> void:
	var lite := GameSettings.lite()
	shafts.visible = not lite
	if _fireflies != null:
		_fireflies.queue_free()
	_fireflies = Node2D.new()
	_fireflies.set_script(FIREFLIES)
	_fireflies.set("count", 10 if lite else 26)
	_fireflies.material = (shafts.get_child(0) as CanvasItem).material   # 同一个加法混合材质
	$Main.add_child(_fireflies)
	shadows.set("interval", Vector2(14.0, 32.0) * (2.5 if lite else 1.0))
	puffs_back.density = 0.5 if lite else 1.0
	puffs_front.density = 0.5 if lite else 1.0


# ======================================================================= 声音
func _build_audio() -> void:
	_rain = AudioStreamPlayer.new()
	_rain.stream = load(SFX_DIR + "rain_loop.wav")
	_rain.bus = "SFX"
	_rain.volume_db = -80.0
	add_child(_rain)
	_crackle = AudioStreamPlayer2D.new()
	_crackle.stream = load(SFX_DIR + "fire_crackle_loop.wav")
	_crackle.bus = "SFX"
	_crackle.volume_db = -80.0
	_crackle.max_distance = 700.0
	wreck.add_child(_crackle)
	_crackle.position = Vector2(8, -14)


func _sfx(name: String, db := 0.0, pitch := 1.0) -> void:
	var p := AudioStreamPlayer.new()
	p.stream = load(SFX_DIR + name + ".wav")
	p.bus = "SFX"
	p.volume_db = db
	p.pitch_scale = pitch
	add_child(p)
	p.play()
	p.finished.connect(p.queue_free)


func _fade_db(p: Node, to_db: float, sec: float) -> void:
	var tw := create_tween()
	tw.tween_property(p, "volume_db", to_db, sec).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)


# ======================================================================= 界面搭建
func _label(text: String, size := 14, color := UITheme.TEXT) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


func _build_ui() -> void:
	var root := Control.new()
	root.name = "Root"
	root.theme = UITheme.get_theme()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(root)

	# ---- 电影黑边（先加，在最底下）
	for i in 2:
		var b := ColorRect.new()
		b.color = Color(0.0, 0.0, 0.0, 1.0)
		b.size = Vector2(480, BAR_H)
		b.position = Vector2(0, -BAR_H if i == 0 else 270)
		b.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(b)
		_bars.append(b)
	_skip_label = _label("", 14, UITheme.TEXT_DIM)
	_skip_label.position = Vector2(0, 270 - BAR_H + 5)
	_skip_label.size = Vector2(472, 16)
	_skip_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_skip_label.modulate.a = 0.0
	root.add_child(_skip_label)

	# ---- 标题（要能直接当封面截图）：游戏名拉开字距、偏暗的薄荷灰、底下压一格深色影子；
	# 下面一行小字是另一种语言的名字，两边各一条细线；「开始」是不抢戏的小字，悬停 / 聚焦时变亮、两边伸出小横线。
	_title_root = Control.new()
	_title_root.size = Vector2(480, 270)
	_title_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_title_root.modulate.a = 0.0
	_title_root.visible = false
	root.add_child(_title_root)
	_title_label = _label("", 42, TITLE_COLOR)
	_title_label.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.35))
	_title_label.add_theme_constant_override("shadow_offset_x", 0)
	_title_label.add_theme_constant_override("shadow_offset_y", 3)
	_title_label.position = Vector2(0, TITLE_Y)
	_title_root.add_child(_title_label)
	_title_sub = _label("", 14, SUB_COLOR)
	_title_sub.position = Vector2(0, TITLE_Y + 50)
	_title_root.add_child(_title_sub)
	for i in 2:
		var ln := ColorRect.new()
		ln.color = SUB_COLOR * Color(1, 1, 1, 0.6)
		ln.size = Vector2(18, 1)
		ln.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_title_root.add_child(ln)
		_title_lines.append(ln)
	_start_btn = Button.new()
	UITheme.flat_button(_start_btn)
	_start_btn.add_theme_font_override("font", UITheme.spaced_font(START_SPACING))
	_start_btn.add_theme_font_size_override("font_size", 14)
	_start_btn.add_theme_color_override("font_color", START_COLOR)
	_start_btn.add_theme_color_override("font_hover_color", START_HOT)
	_start_btn.add_theme_color_override("font_focus_color", START_HOT)
	_start_btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
	_start_btn.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.5))   # 雾最亮的地方也看得清
	_start_btn.add_theme_constant_override("shadow_offset_x", 0)
	_start_btn.add_theme_constant_override("shadow_offset_y", 1)
	_start_btn.position = Vector2(0, START_Y)
	_start_btn.pressed.connect(_on_start)
	_start_btn.focus_entered.connect(func(): _sfx_soft())
	_start_btn.mouse_entered.connect(_on_start_hover.bind(true))
	_start_btn.mouse_exited.connect(_on_start_hover.bind(false))
	_title_root.add_child(_start_btn)
	for i in 2:
		var m := ColorRect.new()
		m.color = START_HOT
		m.size = Vector2(0, 1)
		m.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_title_root.add_child(m)
		_start_marks.append(m)

	# ---- 右下角设置齿轮（标题和自由走的时候都在）
	_gear = TextureButton.new()
	_gear.texture_normal = TEX_GEAR
	_gear.position = Vector2(480 - 8 - 11, 270 - 8 - 11)
	_gear.size = Vector2(11, 11)
	_gear.focus_mode = Control.FOCUS_NONE
	_gear.modulate = Color(1, 1, 1, 0.0)
	_gear.visible = false
	_gear.pressed.connect(_open_settings)
	_gear.mouse_entered.connect(func(): _gear.self_modulate = Color(1.6, 1.6, 1.6))
	_gear.mouse_exited.connect(func(): _gear.self_modulate = Color.WHITE)
	root.add_child(_gear)

	# ---- 左下角语言切换（只在标题界面；设置里也能换）
	_lang_corner = HBoxContainer.new()
	_lang_corner.add_theme_constant_override("separation", 5)
	_lang_corner.position = Vector2(8, 270 - 8 - 14)
	_title_root.add_child(_lang_corner)
	for l in ["en", "zh"]:
		if l == "zh":
			_lang_corner.add_child(_label("/", 14, LANG_OFF))
		var b := Button.new()
		UITheme.flat_button(b)
		b.add_theme_font_size_override("font_size", 14)
		b.add_theme_color_override("font_hover_color", START_HOT)
		b.add_theme_color_override("font_hover_pressed_color", START_HOT)
		b.focus_mode = Control.FOCUS_NONE
		b.text = "EN" if l == "en" else "中文"
		b.pressed.connect(_on_lang_corner.bind(l))
		b.mouse_entered.connect(_sfx_soft)
		_lang_corner.add_child(b)
		_lang_btns[l] = b

	# ---- HUD：左上燃烧值、右上背包
	_hud_burn = HBoxContainer.new()
	_hud_burn.position = Vector2(8, 7)
	_hud_burn.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud_burn.add_theme_constant_override("separation", 4)
	var fl := TextureRect.new()
	fl.texture = TEX_FLAME
	fl.stretch_mode = TextureRect.STRETCH_KEEP
	fl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud_burn.add_child(fl)
	_hud_burn_label = _label("", 14, UITheme.WARM)
	_hud_burn.add_child(_hud_burn_label)
	_hud_burn.modulate.a = 0.0
	root.add_child(_hud_burn)

	_bag_btn = TextureButton.new()
	_bag_btn.texture_normal = TEX_BAG
	_bag_btn.position = Vector2(480 - 8 - 13, 7)
	_bag_btn.size = Vector2(13, 12)
	_bag_btn.pivot_offset = Vector2(6.5, 6)
	_bag_btn.focus_mode = Control.FOCUS_NONE
	_bag_btn.modulate.a = 0.0
	_bag_btn.visible = false
	_bag_btn.pressed.connect(_toggle_bag)
	_bag_btn.mouse_entered.connect(func(): _bag_btn.self_modulate = Color(1.3, 1.3, 1.3))
	_bag_btn.mouse_exited.connect(func(): _bag_btn.self_modulate = Color.WHITE)
	root.add_child(_bag_btn)

	# ---- 「← →」提示（晨脚下，很淡）
	_keys_hint = _label("←  →", 14, UITheme.TEXT)
	_keys_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_keys_hint.size = Vector2(40, 16)
	_keys_hint.modulate.a = 0.0
	root.add_child(_keys_hint)

	# ---- 对话框
	_dlg = PanelContainer.new()
	_dlg.add_theme_stylebox_override("panel", UITheme.box(Color(0.02, 0.05, 0.04, 0.72), Color(0.5, 0.6, 0.55, 0.35), 1, Vector4(7, 4, 7, 5)))
	_dlg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dlg.modulate.a = 0.0
	_dlg.visible = false
	var dv := VBoxContainer.new()
	dv.add_theme_constant_override("separation", 2)
	dv.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dlg.add_child(dv)
	_dlg_name = _label("", 14, UITheme.ACCENT)
	dv.add_child(_dlg_name)
	_dlg_text = _label("", 14, UITheme.TEXT)
	_dlg_text.add_theme_constant_override("line_spacing", 2)
	dv.add_child(_dlg_text)
	root.add_child(_dlg)

	# ---- 燃烧值弹出
	_burn_pop = Control.new()
	_burn_pop.size = Vector2(200, 66)
	_burn_pop.position = Vector2(140, 34)
	_burn_pop.pivot_offset = Vector2(100, 20)
	_burn_pop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_burn_pop.modulate.a = 0.0
	_burn_pop.visible = false
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.size = Vector2(200, 32)
	row.add_theme_constant_override("separation", 6)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var fl2 := TextureRect.new()
	fl2.texture = TEX_FLAME
	fl2.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	fl2.custom_minimum_size = Vector2(14, 18)
	fl2.stretch_mode = TextureRect.STRETCH_SCALE
	fl2.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	fl2.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(fl2)
	_burn_pop_num = _label("10", 28, UITheme.WARM)
	row.add_child(_burn_pop_num)
	_burn_pop.add_child(row)
	var track := ColorRect.new()
	track.color = Color(0.18, 0.22, 0.2, 0.9)
	track.position = Vector2(40, 37)
	track.size = Vector2(120, 3)
	track.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_burn_pop.add_child(track)
	_burn_pop_fill = ColorRect.new()
	_burn_pop_fill.color = UITheme.WARM
	_burn_pop_fill.position = Vector2(40, 37)
	_burn_pop_fill.size = Vector2(0, 3)
	_burn_pop_fill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_burn_pop.add_child(_burn_pop_fill)
	var goal := ColorRect.new()                 # 终点（200）的小竖条
	goal.color = Color("#dfe8e2")
	goal.position = Vector2(160, 35)
	goal.size = Vector2(1, 7)
	goal.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_burn_pop.add_child(goal)
	_burn_pop_sub = _label("", 14, UITheme.TEXT)
	_burn_pop_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_burn_pop_sub.position = Vector2(-40, 46)
	_burn_pop_sub.size = Vector2(280, 16)
	_burn_pop_sub.modulate.a = 0.0
	_burn_pop.add_child(_burn_pop_sub)
	root.add_child(_burn_pop)

	# 面板后面压暗一层；点空白处关面板
	_dim = ColorRect.new()
	_dim.color = Color(0.0, 0.02, 0.01, 0.45)
	_dim.size = Vector2(480, 270)
	_dim.visible = false
	_dim.gui_input.connect(_on_dim_input)
	root.add_child(_dim)
	_build_settings(root)
	_build_bag(root)

	# ---- 耳机提示（在最上层 Top 里，盖在黑幕上）
	_hp_root = VBoxContainer.new()
	_hp_root.theme = UITheme.get_theme()
	_hp_root.position = Vector2(0, 100)
	_hp_root.size = Vector2(480, 80)
	_hp_root.alignment = BoxContainer.ALIGNMENT_CENTER
	_hp_root.add_theme_constant_override("separation", 8)
	_hp_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hp_root.modulate.a = 0.0
	var icon := TextureRect.new()
	icon.texture = TEX_HEADPHONES
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_SCALE
	icon.custom_minimum_size = Vector2(30, 22)
	icon.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hp_root.add_child(icon)
	_hp_label = _label("", 14, UITheme.TEXT)
	_hp_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hp_root.add_child(_hp_label)
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 10)
	gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hp_root.add_child(gap)
	_hp_any = _label("", 14, UITheme.TEXT_DIM)
	_hp_any.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hp_root.add_child(_hp_any)
	$Top.add_child(_hp_root)


func _on_dim_input(e: InputEvent) -> void:
	if e is InputEventMouseButton and e.pressed:
		_close_panels()


func _on_start_hover(on: bool) -> void:
	_start_hover = on
	if on:
		_sfx_soft()


func _sfx_soft() -> void:
	if state == S.TITLE and _state_t > 0.5:
		_sfx("ui_click", -14.0, 1.3)


# ---------------------------------------------------------------- 设置面板
func _row(parent: Control, key: String) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 4)
	var l := _label("", 14, UITheme.TEXT_DIM)
	l.custom_minimum_size = Vector2(80, 18)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	h.add_child(l)
	_settings_widgets["lbl_" + key] = l
	parent.add_child(h)
	return h


func _toggle_pair(h: HBoxContainer, key: String, a_key: String, b_key: String, on_a: Callable, on_b: Callable) -> void:
	var g := ButtonGroup.new()
	for i in 2:
		var b := Button.new()
		b.toggle_mode = true
		b.button_group = g
		b.custom_minimum_size = Vector2(64, 18)
		b.pressed.connect(on_a if i == 0 else on_b)
		b.pressed.connect(func(): _sfx("ui_click", -10.0))
		h.add_child(b)
		_settings_widgets[key + ("_a" if i == 0 else "_b")] = b
	_settings_widgets[key + "_keys"] = [a_key, b_key]


func _slider(h: HBoxContainer, key: String, value: float, on_change: Callable) -> void:
	var s := HSlider.new()
	s.min_value = 0.0
	s.max_value = 1.0
	s.step = 0.05
	s.value = value
	s.custom_minimum_size = Vector2(132, 16)
	s.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	s.value_changed.connect(on_change)
	h.add_child(s)
	_settings_widgets[key] = s


func _build_settings(root: Control) -> void:
	_settings = PanelContainer.new()
	_settings.visible = false
	_settings.mouse_filter = Control.MOUSE_FILTER_STOP
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 5)
	_settings.add_child(v)
	var title := _label("", 14, UITheme.TEXT)
	_settings_widgets["title"] = title
	v.add_child(title)
	var sep := ColorRect.new()
	sep.color = Color(0.3, 0.4, 0.35, 0.6)
	sep.custom_minimum_size = Vector2(0, 1)
	v.add_child(sep)

	var h := _row(v, "language")
	_toggle_pair(h, "lang", "", "", func(): _set_lang("en"), func(): _set_lang("zh"))
	h = _row(v, "vol_master")
	_slider(h, "vol_master", GameSettings.vol_master, _set_vol.bind("vol_master"))
	h = _row(v, "vol_music")
	_slider(h, "vol_music", GameSettings.vol_music, _set_vol.bind("vol_music"))
	h = _row(v, "vol_sfx")
	_slider(h, "vol_sfx", GameSettings.vol_sfx, _set_vol.bind("vol_sfx"))
	h = _row(v, "quality")
	_toggle_pair(h, "q", "q_full", "q_lite", func(): _set_quality("full"), func(): _set_quality("lite"))
	h = _row(v, "fullscreen")
	_toggle_pair(h, "fs", "on", "off", func(): _set_fullscreen(true), func(): _set_fullscreen(false))
	if OS.has_feature("web"):
		h.visible = false
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 2)
	v.add_child(gap)
	var close := Button.new()
	close.custom_minimum_size = Vector2(80, 18)
	close.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	close.pressed.connect(_close_panels)
	v.add_child(close)
	_settings_widgets["close"] = close
	root.add_child(_settings)


func _set_vol(x: float, key: String) -> void:
	GameSettings.set_vol(key, x)
	GameSettings.apply_audio()
	GameSettings.save()


func _set_lang(l: String) -> void:
	GameSettings.set_lang(l)
	GameSettings.save()
	_retext()


func _on_lang_corner(l: String) -> void:
	if l == GameSettings.lang:
		return
	_sfx("ui_click", -10.0)
	_set_lang(l)
	_sync_settings()


func _set_quality(q: String) -> void:
	GameSettings.quality = q
	GameSettings.save()
	_apply_quality()


func _set_fullscreen(on: bool) -> void:
	GameSettings.fullscreen = on
	GameSettings.save()
	GameSettings.apply_window()


func _sync_settings() -> void:
	var w := _settings_widgets
	(w["lang_a"] as Button).set_pressed_no_signal(GameSettings.lang == "en")
	(w["lang_b"] as Button).set_pressed_no_signal(GameSettings.lang == "zh")
	(w["q_a"] as Button).set_pressed_no_signal(not GameSettings.lite())
	(w["q_b"] as Button).set_pressed_no_signal(GameSettings.lite())
	(w["fs_a"] as Button).set_pressed_no_signal(GameSettings.fullscreen)
	(w["fs_b"] as Button).set_pressed_no_signal(not GameSettings.fullscreen)
	for k in ["vol_master", "vol_music", "vol_sfx"]:
		(w[k] as HSlider).set_value_no_signal(GameSettings.get_vol(k))


# ---------------------------------------------------------------- 背包
func _build_bag(root: Control) -> void:
	_bag = Panel.new()
	_bag.visible = false
	_bag.position = Vector2(64, 28)
	_bag.size = Vector2(352, 214)
	_bag.mouse_filter = Control.MOUSE_FILTER_STOP
	root.add_child(_bag)
	var title := _label("", 14, UITheme.TEXT)
	title.position = Vector2(10, 4)
	_bag.add_child(title)
	_bag_w["title"] = title
	# 右上：燃烧值总数 + 关闭
	var tot := HBoxContainer.new()
	tot.position = Vector2(180, 4)
	tot.size = Vector2(144, 16)
	tot.alignment = BoxContainer.ALIGNMENT_END
	tot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var fl := TextureRect.new()
	fl.texture = TEX_FLAME
	fl.stretch_mode = TextureRect.STRETCH_KEEP
	fl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tot.add_child(fl)
	var tl := _label("", 14, UITheme.WARM)
	tot.add_child(tl)
	_bag_w["total"] = tl
	_bag.add_child(tot)
	# 关闭：不用字体里的「×」（按钮里的字会被排到半格上，糊成「)(」），画一个 7×7 的像素叉，
	# 按钮 15×15、叉居中正好落在整像素上（和「60 / 200」的数字同高）
	var x := TextureButton.new()
	x.texture_normal = _pixel_cross(7, UITheme.TEXT)
	x.stretch_mode = TextureButton.STRETCH_KEEP_CENTERED
	x.ignore_texture_size = true
	x.position = Vector2(330, 4)
	x.size = Vector2(15, 15)
	x.self_modulate = Color(1, 1, 1, 0.7)
	x.mouse_entered.connect(func(): x.self_modulate = Color(1.25, 1.25, 1.25, 1.0))
	x.mouse_exited.connect(func(): x.self_modulate = Color(1, 1, 1, 0.7))
	x.focus_mode = Control.FOCUS_NONE
	x.pressed.connect(_close_panels)
	_bag.add_child(x)
	var sep := ColorRect.new()
	sep.color = Color(0.3, 0.4, 0.35, 0.6)
	sep.position = Vector2(8, 23)
	sep.size = Vector2(336, 1)
	_bag.add_child(sep)
	# 左：格子 4 × 6（森林章节一共十几样东西）
	var grid := GridContainer.new()
	grid.columns = 4
	grid.position = Vector2(10, 30)
	grid.add_theme_constant_override("h_separation", 3)
	grid.add_theme_constant_override("v_separation", 3)
	_bag.add_child(grid)
	var slot_box := UITheme.box(Color(0.06, 0.1, 0.09, 0.9), Color(0.22, 0.3, 0.26), 1, Vector4(0, 0, 0, 0))
	var slot_hover := UITheme.box(Color(0.1, 0.16, 0.14, 0.95), Color(0.5, 0.62, 0.56), 1, Vector4(0, 0, 0, 0))
	var slot_sel := UITheme.box(Color(0.14, 0.12, 0.14, 0.95), UITheme.ACCENT, 1, Vector4(0, 0, 0, 0))
	for i in BAG_SLOTS:
		var b := Button.new()
		b.custom_minimum_size = Vector2(26, 26)
		b.add_theme_stylebox_override("normal", slot_box)
		b.add_theme_stylebox_override("hover", slot_hover)
		b.add_theme_stylebox_override("pressed", slot_sel)
		b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
		b.set_meta("sel_box", slot_sel)
		b.set_meta("box", slot_box)
		var ic := TextureRect.new()
		ic.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
		ic.set_anchors_preset(Control.PRESET_FULL_RECT)
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		b.add_child(ic)
		b.set_meta("icon", ic)
		var idx := i
		b.pressed.connect(func(): _bag_select(idx))
		b.focus_entered.connect(func(): _bag_select(idx))
		grid.add_child(b)
		_bag_slots.append(b)
	# 右：选中物品
	var frame := Panel.new()
	frame.position = Vector2(130, 30)
	frame.size = Vector2(212, 50)
	frame.add_theme_stylebox_override("panel", UITheme.box(Color(0.05, 0.08, 0.07, 0.9), Color(0.22, 0.3, 0.26), 1))
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bag.add_child(frame)
	var big := TextureRect.new()
	big.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	big.stretch_mode = TextureRect.STRETCH_SCALE
	big.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(big)
	_bag_w["big"] = big
	var name_l := _label("", 14, UITheme.TEXT)
	name_l.position = Vector2(130, 84)
	_bag.add_child(name_l)
	_bag_w["name"] = name_l
	var rar := _label("", 14, UITheme.TEXT_DIM)
	rar.position = Vector2(130, 100)
	_bag.add_child(rar)
	_bag_w["rarity"] = rar
	var burn := _label("", 14, UITheme.WARM)
	burn.position = Vector2(130, 100)            # 和稀有度同一行、靠右（「私人物品，不能烧」比较长，放名字那行会挤）
	burn.size = Vector2(212, 16)
	burn.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_bag.add_child(burn)
	_bag_w["burn"] = burn
	# 描述：按整行滚（lines_skipped / max_lines_visible，顶上不会露半行字）；滚轮或 ↑↓ 滚，日记默认翻到最新那条。
	# 右边一上一下两个小三角：上面 / 下面还有字。
	var desc := _label("", 14, Color("#b9c9bf"))
	desc.position = Vector2(130, 120)
	desc.size = Vector2(212, DESC_H)
	desc.clip_text = true
	desc.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	desc.add_theme_constant_override("line_spacing", 2)
	desc.max_lines_visible = _desc_lines()
	desc.mouse_filter = Control.MOUSE_FILTER_STOP
	desc.gui_input.connect(_on_desc_input)
	_bag.add_child(desc)
	_bag_w["desc"] = desc
	for i in 2:
		var m := Control.new()
		m.size = Vector2(5, 3)
		m.position = Vector2(344, 121 if i == 0 else 120 + DESC_H - 4)
		m.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var up := i == 0
		m.draw.connect(func():
			for r in 3:
				var w := 1 + 2 * (r if up else 2 - r)
				m.draw_rect(Rect2((5 - w) / 2, r, w, 1), UITheme.TEXT_DIM))
		_bag.add_child(m)
		_bag_w["more_up" if up else "more_down"] = m


func _bag_refresh() -> void:
	_bag_w["title"].text = I18n.t("bag")
	_bag_w["total"].text = I18n.t("burn_total") % [Inventory.burn_total(), Inventory.get_launch_burn()]
	for i in _bag_slots.size():
		var b := _bag_slots[i]
		var ic: TextureRect = b.get_meta("icon")
		if i < Inventory.owned.size():
			ic.texture = Inventory.icon(Inventory.owned[i])
		else:
			ic.texture = null
		b.add_theme_stylebox_override("normal", b.get_meta("sel_box") if i == _bag_sel else b.get_meta("box"))
	var big: TextureRect = _bag_w["big"]
	if _bag_sel < Inventory.owned.size():
		var it := Inventory.item(Inventory.owned[_bag_sel])
		var tex: Texture2D = Inventory.icon(Inventory.owned[_bag_sel])
		var k := maxi(1, mini(int(200 / tex.get_width()), int(42 / tex.get_height())))
		big.texture = tex
		big.size = tex.get_size() * k
		big.position = ((Vector2(212, 50) - big.size) / 2).floor()
		var rc := Inventory.rarity_color(it.get("rarity", "common"))
		_bag_w["name"].text = story.txt(it.get("name", ""))
		_bag_w["name"].add_theme_color_override("font_color", rc)
		_bag_w["rarity"].text = I18n.t("rarity_" + str(it.get("rarity", "common")))
		_bag_w["rarity"].add_theme_color_override("font_color", rc.darkened(0.25))
		_bag_w["burn"].text = I18n.t("personal") if it.get("personal", false) else I18n.t("burn_value") % int(it.get("burn", 0))
		var desc: Label = _bag_w["desc"]
		var new_text := _item_desc(it)
		if desc.text != new_text or desc.get_meta("item", "") != str(it.get("id", "")):
			desc.text = new_text
			desc.set_meta("item", str(it.get("id", "")))
			# 日记：翻到最新那条；别的从头
			desc.lines_skipped = _desc_max_skip() if str(it.get("id", "")) == "journal" else 0
		_desc_marks()
	else:
		big.texture = null
		_bag_w["name"].text = ""
		_bag_w["rarity"].text = ""
		_bag_w["burn"].text = ""
		_bag_w["desc"].text = I18n.t("bag_empty") if Inventory.owned.is_empty() else ""


## 物品描述：剧本文字取当前语言、空的回落中文；日记 = 按时间列出所有条目；有 desc_fixed 的修好以后换（音乐盒：musicbox_fixed）
func _item_desc(it: Dictionary) -> String:
	if str(it.get("id", "")) == "journal":
		var lines: Array[String] = []
		var head: String = story.txt(it.get("desc", ""))
		if head != "":
			lines.append(head)
		for e in StoryState.journal:
			lines.append("· " + story.txt(e))
		if StoryState.journal.is_empty():
			lines.append(I18n.t("journal_empty"))
		return "\n".join(lines)
	if it.has("desc_fixed") and StoryState.has(str(it.get("fixed_flag", "musicbox_fixed"))):
		return story.txt(it["desc_fixed"])
	return story.txt(it.get("desc", ""))


const DESC_H := 88.0


func _desc_line_h() -> float:
	return UITheme.font().get_height(14) + 2.0


func _desc_lines() -> int:
	return maxi(1, int((DESC_H + 2.0) / _desc_line_h()))


func _desc_max_skip() -> int:
	var desc: Label = _bag_w["desc"]
	return maxi(0, desc.get_line_count() - desc.max_lines_visible)


func _desc_scroll(d: int) -> bool:
	var desc: Label = _bag_w["desc"]
	var n := clampi(desc.lines_skipped + d, 0, _desc_max_skip())
	if n == desc.lines_skipped:
		return _desc_max_skip() > 0
	desc.lines_skipped = n
	_desc_marks()
	return true


func _desc_marks() -> void:
	var desc: Label = _bag_w["desc"]
	(_bag_w["more_up"] as Control).visible = desc.lines_skipped > 0 and desc.text != ""
	(_bag_w["more_down"] as Control).visible = desc.lines_skipped < _desc_max_skip() and desc.text != ""


func _on_desc_input(e: InputEvent) -> void:
	if e is InputEventMouseButton and e.pressed:
		if e.button_index == MOUSE_BUTTON_WHEEL_UP:
			_desc_scroll(-1)
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_desc_scroll(1)


func _bag_select(i: int) -> void:
	_bag_sel = i
	_bag_refresh()


# ---------------------------------------------------------------- 文字（换语言时整体刷新）
func _retext() -> void:
	_title_label.text = I18n.t("title")
	_title_sub.text = I18n.t("title_sub")
	_start_btn.text = I18n.t("start")
	_hp_label.text = I18n.t("headphones")
	_hp_any.text = I18n.t("press_any")
	_skip_label.text = I18n.t("skip_again")
	_layout_title()
	for l in _lang_btns:
		var on: bool = l == GameSettings.lang
		(_lang_btns[l] as Button).add_theme_color_override("font_color", LANG_ON if on else LANG_OFF)
		(_lang_btns[l] as Button).mouse_default_cursor_shape = Control.CURSOR_ARROW if on else Control.CURSOR_POINTING_HAND
	_even(_hp_label, _hp_label.text, 14)
	_even(_hp_any, _hp_any.text, 14)
	_even(_burn_pop_sub, _burn_pop_sub.text, 14)
	_burn_pop_sub.text = I18n.t("to_launch") % Inventory.get_launch_burn()
	_update_hud()
	var w := _settings_widgets
	w["title"].text = I18n.t("settings")
	for k in ["language", "vol_master", "vol_music", "vol_sfx", "quality", "fullscreen"]:
		w["lbl_" + k].text = I18n.t(k)
	w["lang_a"].text = I18n.LANG_NAMES["en"]
	w["lang_b"].text = I18n.LANG_NAMES["zh"]
	for pre in ["q", "fs"]:
		var keys: Array = w[pre + "_keys"]
		w[pre + "_a"].text = I18n.t(keys[0])
		w[pre + "_b"].text = I18n.t(keys[1])
	w["close"].text = I18n.t("close")
	if _dlg_on and _dlg.has_meta("key"):
		_dlg_name.text = I18n.t(_dlg.get_meta("who"))
		_dlg_text.text = I18n.t(_dlg.get_meta("key"))
	if _bag.visible:
		_bag_refresh()
	# 设置面板的大小跟着文字变：重新居中
	_settings.reset_size()
	_center_settings.call_deferred()


## 标题界面三样东西水平居中（按整像素；拉开字距以后最后一个字后面那截字距不算）
func _layout_title() -> void:
	var f_title := UITheme.spaced_font(_title_spacing())
	_title_label.add_theme_font_override("font", f_title)
	_center_x(_title_label, f_title, _title_label.text, 42, _title_spacing())
	var f_sub := UITheme.spaced_font(SUB_SPACING)
	_title_sub.add_theme_font_override("font", f_sub)
	var sw := _center_x(_title_sub, f_sub, _title_sub.text, 14, SUB_SPACING)
	var mid := _title_sub.position.y + 7.0
	_title_lines[0].position = Vector2(_title_sub.position.x - 10.0 - _title_lines[0].size.x, mid)
	_title_lines[1].position = Vector2(_title_sub.position.x + sw + 10.0, mid)
	var bw := _center_x(_start_btn, UITheme.spaced_font(START_SPACING), _start_btn.text, 14, START_SPACING)
	_start_btn.size = Vector2(bw + START_SPACING, 20)
	_start_btn.position.y = START_Y


## 中文标题只有一个字，字距没用；英文拉开 3 像素（= 42 号字的 1 格）
func _title_spacing() -> int:
	return 0 if I18n.is_zh() else TITLE_SPACING


## 让 l 的文字在 cx 处水平居中（整像素），返回字宽（不含最后那截字距）
func _center_x(l: Control, f: Font, text: String, size: int, spacing: int, cx := 240.0) -> float:
	var w := f.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x - spacing
	l.position.x = floor(cx - w / 2.0)
	l.size.x = w + spacing + 2.0
	return w


## 居中的单行字：让「框宽 - 字宽」是偶数，字的像素格才和画面的像素格对齐（否则差半格）
func _even(l: Control, text: String, font_size: int) -> void:
	var w := UITheme.font().get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var base: float = l.get_meta("base_w", l.size.x)
	l.set_meta("base_w", base)
	l.size.x = base + float(int(round(base - w)) % 2)


func _center_settings() -> void:
	_settings.reset_size()
	_settings.position = ((Vector2(480, 270) - _settings.size) / 2).floor()


func _update_hud() -> void:
	_hud_burn_label.text = I18n.t("burn_total") % [Inventory.burn_total(), Inventory.get_launch_burn()]


# ======================================================================= 定时事件 / tween
func _run(events: Array) -> void:
	_seq = events
	_seq.sort_custom(func(a, b): return a[0] < b[0])
	_seq_t = 0.0


func _tw() -> Tween:
	var tw := create_tween()
	_tweens.append(tw)
	return tw


func _kill_cine() -> void:
	_seq.clear()
	for tw in _tweens:
		if tw.is_valid():
			tw.kill()
	_tweens.clear()


func _set_state(s: S) -> void:
	state = s
	_state_t = 0.0


# ======================================================================= 1. 耳机提示
func _enter_headphones() -> void:
	_set_state(S.HEADPHONES)
	fade.color.a = 1.0
	_hp_root.modulate.a = 0.0
	var tw := _tw()
	tw.tween_interval(0.3)
	tw.tween_property(_hp_root, "modulate:a", 1.0, 1.2)


func _leave_headphones() -> void:
	_set_state(S.INTRO)
	var tw := _tw()
	tw.tween_property(_hp_root, "modulate:a", 0.0, 0.8)
	_run([
		[0.6, _rain_in],
		[1.8, func(): _sfx("thunder_far_1", -7.0)],
		[4.4, func(): _sfx("thunder_far_2", -10.0, 0.92)],
		[5.4, _fade_from_black],
		[7.6, _show_title],
	])


func _rain_in() -> void:
	_rain.play()
	_fade_db(_rain, -9.0, 3.5)


func _fade_from_black() -> void:
	_tw().tween_property(fade, "color:a", 0.0, 3.2).set_trans(Tween.TRANS_SINE)


# ======================================================================= 2. 标题
func _show_title() -> void:
	_set_state(S.TITLE)
	_title_root.visible = true
	_gear.visible = true
	_title_root.modulate.a = 1.0
	_title_k = 0.0
	_title_label.modulate.a = 0.0
	_title_sub.modulate.a = 0.0
	_start_btn.modulate.a = 0.0
	_lang_corner.modulate.a = 0.0
	for ln in _title_lines:
		ln.modulate.a = 0.0
	# 标题先慢慢浮出来（2.6 秒，同时往上飘 3 像素），副标题晚 0.8 秒，「开始」再晚一点
	var tw := _tw()
	tw.tween_property(self, "_title_k", 1.0, 2.6).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(_title_sub, "modulate:a", 1.0, 1.6).set_delay(0.8)
	tw.parallel().tween_property(_title_lines[0], "modulate:a", 1.0, 1.6).set_delay(0.8)
	tw.parallel().tween_property(_title_lines[1], "modulate:a", 1.0, 1.6).set_delay(0.8)
	tw.parallel().tween_property(_start_btn, "modulate:a", 1.0, 1.2).set_delay(1.6)
	tw.parallel().tween_property(_gear, "modulate:a", GEAR_A, 1.2).set_delay(1.6)
	tw.parallel().tween_property(_lang_corner, "modulate:a", 1.0, 1.2).set_delay(1.6)
	# 不抢焦点：不然「开始」一出来就是高亮的。Enter / 空格照样能开始（见 _input），按方向键才聚焦。


func _skip_to_title() -> void:
	_kill_cine()
	_hp_root.modulate.a = 0.0
	fade.color.a = 0.0
	_rain.play()
	_rain.volume_db = -9.0
	_show_title()
	_kill_cine()
	_title_k = 1.0
	_title_sub.modulate.a = 1.0
	for ln in _title_lines:
		ln.modulate.a = 1.0
	_start_btn.modulate.a = 1.0
	_lang_corner.modulate.a = 1.0
	_gear.modulate.a = GEAR_A


func _on_start() -> void:
	if state != S.TITLE or _settings.visible or _state_t < 0.3:
		return
	_sfx("ui_click", -8.0)
	_start_crash()


# ======================================================================= 3. 开场动画
func _hide_title() -> void:
	_title_root.visible = false
	_gear.visible = false


func _start_crash() -> void:
	_set_state(S.CRASH)
	_start_btn.release_focus()
	var tw := _tw()
	tw.tween_property(_title_root, "modulate:a", 0.0, 0.6)
	tw.parallel().tween_property(_gear, "modulate:a", 0.0, 0.6)
	tw.tween_callback(_hide_title)
	var tc := _tw()
	tc.tween_property(cam, "position:x", TITLE_CAM_X, 1.6).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_bars_in(0.8)
	_run([
		[0.7, func(): _flash(0.6)],
		[0.78, func(): _sfx("thunder_near_1", -6.0)],
		[1.3, func(): _flash(0.3)],
		[1.36, func(): _sfx("thunder_near_2", -9.0, 1.05)],
		[2.15, func(): _flash(1.0)],
		[2.2, func(): _sfx("thunder_near_3", -4.0, 0.95)],
		[2.75, _ship_in],
		[2.75 + SHIP_TIME, _impact],
		[2.75 + SHIP_TIME + ALIEN_THROW_DELAY, _alien_thrown if ALIEN_IN_FOREST else func(): pass],
		[ALIEN_GETUP_AT, _alien_get_up if ALIEN_IN_FOREST else func(): pass],
		[8.4, _chen_get_up],
		[8.4 + (GETUP_TIME + 0.2 if _has_getup else 1.7), _crash_done],
	])


const SHIP_TIME := 2.4


func _flash(peak: float) -> void:
	# 天光从林冠后面亮一下：很快亮起、闪一下、再慢慢退（退得比原来慢，更柔）
	var tw := _tw()
	tw.tween_property(self, "_flash_k", peak, 0.05).set_trans(Tween.TRANS_SINE)
	tw.tween_property(self, "_flash_k", peak * 0.35, 0.08)
	tw.tween_property(self, "_flash_k", peak * 0.8, 0.06)
	tw.tween_property(self, "_flash_k", 0.0, 0.9).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)


func _apply_flash() -> void:
	var k := _flash_k
	for n in FLASH_LAYERS:
		var g: float = FLASH_LAYERS[n] * k
		(get_node(n) as CanvasItem).modulate = Color(1.0 + FLASH_GAIN.r * g, 1.0 + FLASH_GAIN.g * g, 1.0 + FLASH_GAIN.b * g)
	if _impact_k > 0.0:
		flash.color = Color(IMPACT_TINT, _impact_k * 0.16)
	else:
		flash.color = Color(FLASH_TINT, k * FLASH_TINT_A)


# 飞船飞行图的中心到机头 / 喷口（tools/level1_art.py 跑完会打印这些数：斜 16°，船长 140）
const SHIP_NOSE := Vector2(-66, 23)
const SHIP_ENGINE := Vector2(71, -22)
# 坠毁图（斜 17°）里几个点，相对 wreck 锚点（船身中心的 x、地面）
const WRECK_NOSE := Vector2(-59, 0)       # 机头扎进土里的地方
const WRECK_HATCH := Vector2(20, -25)     # 舱门（没了），两个人从这里被甩出来
const WRECK_HOLE := Vector2(-1, -5)       # 船腹的破洞（余火）
const WRECK_ENGINE := Vector2(69, -36)    # 喷口（翘起来的那头，冒主烟柱）
const WRECK_FIN := Vector2(43, -52)       # 尾翼断口
const WRECK_CENTER := Vector2(0, -14)     # 船身中心（飞行图最后对齐到这，换成坠毁图时不跳）
# 另一个外星人：比晨晚一点被甩出来（弧线低、落得近），比晨早一点爬起来
const ALIEN_THROW_DELAY := 0.16
const ALIEN_THROW_TIME := 0.5
const ALIEN_GETUP_AT := 6.9               # 晨是 8.4


func _ship_end() -> Vector2:
	# 最后一帧：飞行图的船身中心对上坠毁图的船身中心（稍微高一点，机头刚碰到地面）
	return Vector2(WRECK_X, _ground(WRECK_X)) + WRECK_CENTER + Vector2(0, -4)


func _ship_start() -> Vector2:
	return Vector2(cam.position.x + 240 + 110, -6)


func _ship_in() -> void:
	ship.visible = true
	ship.frame = 0
	ship.position = _ship_start()
	_sfx("ship_whoosh", -3.0)
	puffs_back.add_source("trail", ship.position + SHIP_ENGINE, 46.0, puffs_back.PRESETS.trail)
	puffs_back.add_source("trail_sparks", ship.position + SHIP_ENGINE, 10.0, puffs_back.PRESETS.ember)
	_path_a = _ship_start()
	_path_b = _ship_end()
	_tw().tween_method(_ship_step, 0.0, 1.0, SHIP_TIME).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)


var _path_a := Vector2.ZERO
var _path_b := Vector2.ZERO


func _ship_step(k: float) -> void:
	# 稍微往下弯的弧线，越来越快
	var p := _path_a.lerp(_path_b, k)
	p.y += sin(k * PI) * 10.0
	ship.position = p.round()
	puffs_back.set_source_pos("trail", ship.position + SHIP_ENGINE)
	puffs_back.set_source_pos("trail_sparks", ship.position + SHIP_ENGINE)


func _impact() -> void:
	ship.visible = false
	puffs_back.remove_source("trail")
	puffs_back.remove_source("trail_sparks")
	_show_wreck()
	var nose := wreck.position + WRECK_NOSE
	_sfx("ship_impact", -1.0)
	_shake = 0.9
	_shake_amp = 6.0
	_flash_k = 0.0
	# 船大了，尘土和烟团也铺得开一点：机头那一大团，船腹擦地那一线
	puffs_front.burst(nose, 40, puffs_front.PRESETS.dust.merged({"spread": Vector2(16, 1)}))
	puffs_front.burst(nose + Vector2(46, 0), 22, puffs_front.PRESETS.dust.merged({"spread": Vector2(30, 1)}))
	puffs_back.burst(nose + Vector2(14, -10), 22, puffs_back.PRESETS.smoke_burst.merged({"spread": Vector2(16, 6)}))
	puffs_back.burst(wreck.position + WRECK_HOLE + Vector2(0, -8), 14, puffs_back.PRESETS.smoke_burst)
	puffs_front.burst(nose + Vector2(10, -6), 12, puffs_front.PRESETS.ember)
	var tw := _tw()
	_impact_k = 0.0
	tw.tween_property(self, "_impact_k", 1.0, 0.03)
	tw.tween_property(self, "_impact_k", 0.0, 0.4)
	_chen_thrown()


func _show_wreck() -> void:
	wreck.visible = true
	# 主烟柱从喷口（翘起来的那头）冒，船腹破洞和舱门口各冒一点；火星很少，从破洞和喷口出来
	var tail := wreck.position + WRECK_ENGINE
	puffs_back.add_source("wreck", tail, 11.0, puffs_back.PRESETS.smoke.merged({"spread": Vector2(5, 3)}))
	puffs_back.add_source("wreck2", wreck.position + WRECK_HOLE, 4.0, puffs_back.PRESETS.smoke)
	puffs_back.add_source("wreck3", wreck.position + WRECK_HATCH + Vector2(0, -8), 2.5, puffs_back.PRESETS.smoke)
	puffs_front.add_source("embers", wreck.position + WRECK_HOLE + Vector2(0, -2), 1.5, puffs_front.PRESETS.ember)
	puffs_front.add_source("embers2", tail + Vector2(-2, 2), 1.0, puffs_front.PRESETS.ember)
	if not _crackle.playing:
		_crackle.play()
		_fade_db(_crackle, -16.0, 2.0)


func _chen_thrown() -> void:
	chen.visible = true
	chen._set_facing(1)
	# 从舱门口（没了）甩出来，越过另一个外星人，落得远
	_path_a = wreck.position + WRECK_HATCH + Vector2(0, 20)
	_path_b = Vector2(CHEN_X, _ground(CHEN_X) + 1)
	chen.position = _path_a
	chen.spr.rotation = -0.6
	var tw := _tw()
	tw.tween_method(_thrown_step, 0.0, 1.0, 0.72).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tw.tween_callback(_chen_landed)


func _thrown_step(k: float) -> void:
	# 被甩出来：一道小弧线，转一圈多一点，最后脸朝下
	var p := _path_a.lerp(_path_b, k)
	p.y -= sin(k * PI) * 34.0
	chen.position = p.round()
	var r := lerpf(-0.6, PI / 2.0 + TAU, k)
	if _has_getup:
		# 空中翻滚按 90° 一档一档转（像素一一对应，不出斜着的 mixel），绕身体中间转
		r = snappedf(r, PI / 2.0)
		var c := Vector2(0, -26)      # 晨站着约 52 像素高，绕腰转
		chen.spr.position = (c - c.rotated(r) + Vector2(0, 18.0 * k)).round()
		chen.spr.rotation = r
	else:
		chen.spr.rotation = r
		chen.spr.position.y = -round(LIE_LIFT * k)


func _chen_landed() -> void:
	if _has_getup:
		_chen_lying()
	else:
		chen.spr.rotation = PI / 2.0
	puffs_front.burst(chen.position + Vector2(18, 0), 10, puffs_front.PRESETS.dust_small)
	_sfx("ship_impact", -22.0, 1.8)


func _chen_lying() -> void:
	chen.visible = true
	chen.position = Vector2(CHEN_X, _ground(CHEN_X) + 1)
	if _has_getup:
		chen.spr.rotation = 0.0
		chen.spr.position = Vector2.ZERO
		chen.spr.play(&"lie")
		chen._set_facing(1)
		return
	chen._set_facing(1)
	chen.spr.rotation = PI / 2.0
	chen.spr.position.y = -LIE_LIFT


# ----------------------------------------------------------------------- 另一个外星人（npc_alien.gd）
var _alien_a := Vector2.ZERO
var _alien_b := Vector2.ZERO


func _alien_thrown() -> void:
	# 比晨晚 0.16 秒、弧线低、落得近（残骸尾巴旁边），转一圈多一点，脸朝下趴着，头朝右（朝晨那边）
	_alien_a = wreck.position + WRECK_HATCH + Vector2(2, 16)
	_alien_b = Vector2(ALIEN_X, _ground(ALIEN_X) + 1)
	alien.visible = true
	alien.throw_step(_alien_a, _alien_b, 0.0, 18.0, 0.0, PI / 2.0 + TAU)
	var tw := _tw()
	tw.tween_method(func(k: float): alien.throw_step(_alien_a, _alien_b, k, 18.0, 0.0, PI / 2.0 + TAU),
		0.0, 1.0, ALIEN_THROW_TIME).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tw.tween_callback(_alien_landed)


func _alien_landed() -> void:
	alien.lie(1)
	puffs_front.burst(alien.position + Vector2(12, 0), 8, puffs_front.PRESETS.dust_small)
	_sfx("ship_impact", -25.0, 2.0)


func _alien_get_up() -> void:
	if alien.spr.animation != &"lie":
		return
	var t: float = alien.get_up()
	var tw := _tw()
	# 梧桐版的 getup：第 4 帧（460ms 那张）跪起来，最后一帧站直
	tw.tween_interval(0.72)
	tw.tween_callback(func(): puffs_front.burst(alien.position + Vector2(-2, 0), 3, puffs_front.PRESETS.dust_small))
	tw.tween_interval(t - 0.72 - 0.15)
	tw.tween_callback(func(): puffs_front.burst(alien.position, 4, puffs_front.PRESETS.dust_small))


func _alien_stand() -> void:
	if not ALIEN_IN_FOREST:
		return
	alien.stand(ALIEN_X, _ground(ALIEN_X) + 1)


func _chen_get_up() -> void:
	var spr: AnimatedSprite2D = chen.spr
	var tw := _tw()
	if _has_getup:
		# 奥斯卡画的爬起来：趴着 → 撑起上身 → 跪坐 → 站直（chen.gd 的 getup，播完自己回 idle）
		spr.play(&"getup")
		tw.tween_interval(GETUP_KNEEL_AT)
		tw.tween_callback(func(): puffs_front.burst(chen.position + Vector2(-3, 0), 4, puffs_front.PRESETS.dust_small))
		tw.tween_interval(GETUP_STAND_AT - GETUP_KNEEL_AT)
		tw.tween_callback(func(): puffs_front.burst(chen.position, 5, puffs_front.PRESETS.dust_small))
		return
	# 先动一下（抽一下），停一会儿，撑起来一半，再站直，落地压扁一下
	tw.tween_property(spr, "rotation", PI / 2.0 - 0.12, 0.12)
	tw.tween_property(spr, "rotation", PI / 2.0, 0.15)
	tw.tween_interval(0.45)
	tw.tween_method(_lean, PI / 2.0, 0.6, 0.4).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tw.tween_interval(0.3)
	tw.tween_method(_lean, 0.6, 0.0, 0.18).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_callback(_chen_stood)
	tw.tween_property(spr, "scale", Vector2.ONE, 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


func _chen_stood() -> void:
	chen.spr.scale = Vector2(1.12, 0.86)
	puffs_front.burst(chen.position, 6, puffs_front.PRESETS.dust_small)


func _lean(r: float) -> void:
	chen.spr.rotation = r
	chen.spr.position.y = -round(LIE_LIFT * sin(r))


func _chen_stand() -> void:
	if String(chen.spr.animation) in ["lie", "getup"]:
		chen.spr.play(&"idle")
	chen.spr.rotation = 0.0
	chen.spr.position = Vector2.ZERO
	chen.spr.scale = Vector2.ONE
	chen.position = Vector2(chen.position.x, _ground(chen.position.x) + 1)


func _crash_done() -> void:
	_kill_cine()
	_chen_stand()
	if ALIEN_IN_FOREST and not alien.is_up():
		_alien_stand()
	_bars_out(0.7)
	StoryState.set_flag("crashed")
	var h: String = story.hook("crash")
	_enter_play()
	if h != "":
		story.play(h)             # 剧本的 intro（播的时候锁晨，播完回到自由走）
	else:
		_say("who_chen", "line_crash")


func _skip_crash() -> void:
	# 跳过：直接到「晨已经站起来、对话刚出现」
	_kill_cine()
	_title_root.visible = false
	_title_root.modulate.a = 0.0
	_gear.visible = false
	_flash_k = 0.0
	_impact_k = 0.0
	ship.visible = false
	puffs_back.remove_source("trail")
	puffs_back.remove_source("trail_sparks")
	if not wreck.visible:
		_show_wreck()
		puffs_back.burst(wreck.position + Vector2(10, -16), 14, puffs_back.PRESETS.smoke_burst)
	cam.position.x = TITLE_CAM_X
	chen.visible = true
	chen._set_facing(1)
	chen.position = Vector2(CHEN_X, _ground(CHEN_X) + 1)
	if ALIEN_IN_FOREST:
		_alien_stand()
	_skip_label.modulate.a = 0.0
	_bars_out(0.01)
	_crash_done()


# ======================================================================= 黑边
func _bars_in(sec: float) -> void:
	var tw := _tw()
	tw.tween_property(_bars[0], "position:y", 0.0, sec).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(_bars[1], "position:y", 270.0 - BAR_H, sec).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)


func _bars_out(sec: float) -> void:
	var tw := create_tween()
	tw.tween_property(_bars[0], "position:y", -float(BAR_H), sec).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tw.parallel().tween_property(_bars[1], "position:y", 270.0, sec).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)


# ======================================================================= 4. 自由走
func _enter_play() -> void:
	_set_state(S.PLAY)
	chen.input_enabled = true
	chen.auto_dir = 0.0
	_walk_target = NAN
	_moved_from = chen.position.x
	_hint_wait = 0.0
	_gear.visible = true
	create_tween().tween_property(_gear, "modulate:a", 0.6, 0.8)
	if not Inventory.owned.is_empty():
		_bag_btn.visible = true
		create_tween().tween_property(_bag_btn, "modulate:a", 1.0, 0.5)
		create_tween().tween_property(_hud_burn, "modulate:a", 1.0, 0.5)


func _leave_play_ui() -> void:
	_gear.visible = false
	_gear.modulate.a = 0.0
	create_tween().tween_property(_keys_hint, "modulate:a", 0.0, 0.3)


# ======================================================================= 5. 发光木头
func _start_pickup() -> void:
	_set_state(S.CINE)
	chen.input_enabled = false
	_walk_target = NAN
	_leave_play_ui()
	_bars_in(0.5)
	_dlg_hide(0.4)
	var side := -1.0 if chen.position.x < WOOD_X else 1.0
	_cine_target = WOOD_X + side * 13.0
	if absf(chen.position.x - _cine_target) <= 3.0:
		_cine_target = NAN
		_pickup_at_wood()
	else:
		chen.auto_dir = signf(_cine_target - chen.position.x)


func _pickup_at_wood() -> void:
	chen.auto_dir = 0.0
	chen._set_facing(1 if WOOD_X > chen.position.x else -1)
	create_tween().tween_property(wood_hint, "modulate:a", 0.0, 0.2)
	var h: String = story.hook("wood")
	if h != "":
		# 剧本接管台词：木头飞进背包以后播剧本里木头那个 scene（它的「弯腰捡」和「给木头」跳过），燃烧值照样滚
		_burn_sub_off = true
		_run([
			[0.15, _pk_crouch],
			[0.35, _pk_lift],
			[1.0, _pk_show_bag],
			[1.35, _wood_fly_to_bag],
			[2.15, _wood_story.bind(h)],
			[4.6, _burn_roll],
			[9.6, _burn_to_hud],
		])
		return
	_run([
		[0.15, _pk_crouch],           # 捡东西最低那帧在动画第 0.2 秒 → 正好 0.35 木头飞起来
		[0.35, _pk_lift],
		[1.0, _pk_show_bag],
		[1.35, _wood_fly_to_bag],
		[2.15, _say.bind("who_chen", "line_wood")],
		[4.6, _burn_roll],
		[9.6, _burn_to_hud],
		[10.3, _pickup_done],
	])


func _wood_story(h: String) -> void:
	await story.play_wood(h)
	StoryState.set_flag("got_wood")
	while not _seq.is_empty():
		await get_tree().process_frame
	await get_tree().create_timer(0.6).timeout
	_pickup_done()
	story.check_fuel_hook()


func _pk_crouch() -> void:
	if CHEN_GD.ANIMS.has("pickup"):
		chen.spr.play(&"pickup")      # 奥斯卡画的弯腰捡，播完自己回 idle
		return
	var tw := _tw()
	tw.tween_property(chen.spr, "scale", Vector2(1.06, 0.9), 0.12)
	tw.tween_property(chen.spr, "scale", Vector2.ONE, 0.2)


func _pk_lift() -> void:
	_sfx("pickup", -6.0)
	var tw := _tw()
	tw.tween_property(wood, "position", wood.position + Vector2(0, -18), 0.55).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(wood_glow, "scale", Vector2(1.5, 1.5), 0.55)
	puffs_front.burst(wood.position + Vector2(0, -4), 8, puffs_front.PRESETS.glint)


func _pk_show_bag() -> void:
	_bag_btn.visible = true
	_tw().tween_property(_bag_btn, "modulate:a", 1.0, 0.4)


func _wood_fly_to_bag() -> void:
	_path_a = wood.position
	var tw := _tw()
	tw.tween_method(_wood_fly_step, 0.0, 1.0, 0.6).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tw.tween_callback(_wood_in_bag)


func _wood_fly_step(k: float) -> void:
	# 目标是右上角背包图标在世界里的位置（镜头可能在动，每帧重算）
	var to := _screen_to_world(_bag_btn.position + _bag_btn.size / 2.0)
	var p := _path_a.lerp(to, k)
	p.y -= sin(k * PI) * 20.0
	wood.position = p.round()
	var s := lerpf(1.0, 0.45, k)
	wood.scale = Vector2(s, s)


func _wood_in_bag() -> void:
	wood.visible = false
	Inventory.add("glowing_wood")
	on_inventory_changed()
	_sfx("tick", -6.0, 0.8)
	_bag_btn.scale = Vector2(1.5, 1.5)
	_tw().tween_property(_bag_btn, "scale", Vector2.ONE, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


func _screen_to_world(p: Vector2) -> Vector2:
	return cam.get_screen_center_position() - Vector2(240, 135) + p


func _burn_roll() -> void:
	var from := float(Inventory.base_burn)
	var to := float(Inventory.burn_total())
	_burn_shown = from
	_burn_pop.visible = true
	_burn_pop.position = Vector2(140, 34)
	_burn_pop.scale = Vector2.ONE
	_burn_pop_sub.modulate.a = 0.0
	_set_burn_pop(from)
	var tw := _tw()
	tw.tween_property(_burn_pop, "modulate:a", 1.0, 0.4)
	tw.tween_interval(0.4)
	tw.tween_method(_set_burn_pop, from, to, 1.6).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_callback(_sfx.bind("burn_ding", -8.0, 1.0))
	if not _burn_sub_off:
		tw.tween_property(_burn_pop_sub, "modulate:a", 1.0, 0.6)


func _set_burn_pop(v: float) -> void:
	var n := int(round(v))
	if n != int(round(_burn_shown)) and n % 2 == 0:
		_sfx("tick", -14.0, 1.0 + (n - Inventory.base_burn) * 0.004)
	_burn_shown = v
	_burn_pop_num.text = str(n)
	_burn_pop_fill.size.x = round(120.0 * clampf(v / Inventory.get_launch_burn(), 0.0, 1.0))


func _burn_to_hud() -> void:
	_update_hud()
	var tw := _tw()
	tw.tween_property(_burn_pop, "modulate:a", 0.0, 0.5)
	tw.parallel().tween_property(_burn_pop, "position", Vector2(-60, -12), 0.5).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tw.parallel().tween_property(_burn_pop, "scale", Vector2(0.4, 0.4), 0.5)
	tw.parallel().tween_property(_hud_burn, "modulate:a", 1.0, 0.5).set_delay(0.25)
	tw.tween_callback(_burn_pop.hide)


func _pickup_done() -> void:
	_kill_cine()
	_burn_pop.visible = false
	_hud_burn.modulate.a = 1.0
	_bars_out(0.6)
	_enter_play()


# ======================================================================= 对话框
func _say(who: String, key: String) -> void:
	_dlg.set_meta("who", who)
	_dlg.set_meta("key", key)
	_dlg_name.text = I18n.t(who)
	_dlg_text.text = I18n.t(key)
	_dlg_text.visible_characters = 0
	_dlg_chars = 0.0
	_dlg_cps = 14.0 if I18n.is_zh() else 30.0
	_dlg_age = 0.0
	_dlg_x = chen.position.x
	_dlg_on = true
	_dlg.visible = true
	_dlg.reset_size()
	if _dlg_tw != null and _dlg_tw.is_valid():
		_dlg_tw.kill()
	_dlg_tw = create_tween()
	_dlg_tw.tween_property(_dlg, "modulate:a", 1.0, 0.35)
	_place_dialogue()


func _dlg_hide(sec := 0.7) -> void:
	if not _dlg_on:
		return
	_dlg_on = false
	if _dlg_tw != null and _dlg_tw.is_valid():
		_dlg_tw.kill()
	_dlg_tw = create_tween()
	_dlg_tw.tween_property(_dlg, "modulate:a", 0.0, sec)
	_dlg_tw.tween_callback(_dlg.hide)


func _dlg_typing() -> bool:
	return _dlg_on and _dlg_text.visible_characters >= 0 and _dlg_text.visible_characters < _dlg_text.get_total_character_count()


func _place_dialogue() -> void:
	# 晨头顶：框的下沿在她头顶上 6 像素，水平居中跟着她，不出屏幕
	_dlg.reset_size()
	var sx := chen.position.x - (cam.get_screen_center_position().x - 240.0)
	var top := chen.position.y - 44.0
	var x := clampf(round(sx - _dlg.size.x / 2.0), 6.0, 474.0 - _dlg.size.x)
	_dlg.position = Vector2(x, round(top - 6.0 - _dlg.size.y))


func _update_dialogue(delta: float) -> void:
	if not _dlg.visible:
		return
	if _dlg_on:
		_dlg_age += delta
		_dlg_chars += _dlg_cps * delta
		var total := _dlg_text.get_total_character_count()
		_dlg_text.visible_characters = mini(int(_dlg_chars), total)
		if _dlg_text.visible_characters >= total:
			_dlg_text.visible_characters = -1
		if _dlg_age > DLG_TIME or (state == S.PLAY and absf(chen.position.x - _dlg_x) > DLG_WALK):
			_dlg_hide()
	_place_dialogue()


# ======================================================================= 面板
func _open_settings() -> void:
	if state in [S.HEADPHONES, S.INTRO, S.CRASH, S.CINE] or _settings.visible:
		return
	_close_panels()
	_sfx("ui_click", -10.0)
	_panel_prev_focus = get_viewport().gui_get_focus_owner()
	_sync_settings()
	_settings.visible = true
	_dim.visible = true
	_center_settings()
	chen.input_enabled = false
	(_settings_widgets["lang_a"] as Button).grab_focus()


func _toggle_bag() -> void:
	if _bag.visible:
		_close_panels()
		return
	if state != S.PLAY or Inventory.owned.is_empty():
		return
	_close_panels()
	_sfx("ui_click", -10.0)
	_panel_prev_focus = null
	_bag.visible = true
	_dim.visible = true
	_bag_sel = clampi(_bag_sel, 0, mini(BAG_SLOTS, Inventory.owned.size()) - 1)
	_bag_refresh()
	chen.input_enabled = false
	chen.auto_dir = 0.0
	_walk_target = NAN
	_bag_slots[_bag_sel].grab_focus()
	if not _bag_seen:
		_bag_seen = true
		_bag_btn.modulate = Color(1, 1, 1, 1)


func _close_panels() -> void:
	var was := _settings.visible or _bag.visible
	_settings.visible = false
	_bag.visible = false
	_dim.visible = false
	if was:
		_sfx("ui_click", -12.0, 0.85)
	if state == S.PLAY:
		chen.input_enabled = true
	if state == S.TITLE:
		if _panel_prev_focus == _start_btn:
			_start_btn.grab_focus()
	elif _panel_prev_focus != null and is_instance_valid(_panel_prev_focus) and _panel_prev_focus.is_visible_in_tree():
		_panel_prev_focus.grab_focus()
	else:
		var f := get_viewport().gui_get_focus_owner()
		if f != null:
			f.release_focus()


# ======================================================================= 输入
func _input(event: InputEvent) -> void:
	if _autoplay or _shots_dir != "" or _shot != "" or _story_auto != "":
		get_viewport().set_input_as_handled()
		return
	# F8：开发者面板（只在 debug 构建）
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F8 and OS.is_debug_build():
		toggle_dev()
		get_viewport().set_input_as_handled()
		return
	# 章节结束卡：3 秒以后按任意键回标题
	if story.ended:
		if _end_t > 3.0 and ((event is InputEventKey and event.pressed) or (event is InputEventMouseButton and event.pressed)):
			get_tree().reload_current_scene()
		get_viewport().set_input_as_handled()
		return
	# 剧情在播：按键 / 点击给对话框（确认、点选）；鹿带路时方向键照常走
	if story.busy and not _settings.visible and not _bag.visible:
		if story.dlg.handle_input(event):
			get_viewport().set_input_as_handled()
			return
		if not story.free_walk and (event is InputEventKey or event is InputEventMouseButton):
			if not (event is InputEventKey and event.keycode == KEY_ESCAPE):
				get_viewport().set_input_as_handled()
				return
	if event is InputEventKey and event.pressed and not event.echo:
		var k: int = event.keycode
		if k == KEY_ESCAPE:
			if _settings.visible or _bag.visible:
				_close_panels()
			elif state in [S.TITLE, S.PLAY]:
				_open_settings()
			get_viewport().set_input_as_handled()
			return
		if k in TEST_SCENES and state == S.TITLE and OS.is_debug_build() and not (_settings.visible or _bag.visible):
			get_viewport().set_input_as_handled()
			_open_test_scene(TEST_SCENES[k])
			return
		if k in [KEY_TAB, KEY_B, KEY_I]:
			if not _settings.visible:
				_toggle_bag()
			get_viewport().set_input_as_handled()
			return
		# 背包开着、描述比框长：↑↓ 滚描述（不长就照常在格子里移动）
		if _bag.visible and k in [KEY_UP, KEY_DOWN] and _desc_max_skip() > 0:
			_desc_scroll(-1 if k == KEY_UP else 1)
			get_viewport().set_input_as_handled()
			return
	if _settings.visible or _bag.visible:
		return
	var confirm: bool = event.is_action_pressed("ui_accept") or (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT)
	var anykey: bool = (event is InputEventKey and event.pressed and not event.echo) or (event is InputEventMouseButton and event.pressed)
	match state:
		S.HEADPHONES:
			if anykey and _state_t > 0.4:
				_leave_headphones()
				get_viewport().set_input_as_handled()
		S.TITLE:
			# 「开始」平时不拿焦点（不然一出来就是高亮的）：Enter / 空格直接开始，方向键才把焦点给它
			if event.is_action_pressed("ui_accept"):
				get_viewport().set_input_as_handled()
				_on_start()
			elif get_viewport().gui_get_focus_owner() == null and (event.is_action_pressed("ui_up") \
					or event.is_action_pressed("ui_down") or event.is_action_pressed("ui_left") or event.is_action_pressed("ui_right")):
				get_viewport().set_input_as_handled()
				_start_btn.grab_focus()
		S.INTRO:
			if confirm and _state_t > 0.5:
				_skip_to_title()
				get_viewport().set_input_as_handled()
		S.CRASH:
			if confirm:
				get_viewport().set_input_as_handled()
				if _skip_armed > 0.0:
					_skip_crash()
				else:
					_skip_armed = 2.0
					_skip_label.modulate.a = 1.0
		S.PLAY, S.CINE:
			if state == S.PLAY and event is InputEventKey and event.pressed and not event.echo \
					and event.keycode in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER] and not story.hotspots.near.is_empty():
				get_viewport().set_input_as_handled()
				_interact(story.hotspots.near)
			elif event.is_action_pressed("ui_accept") and _dlg_typing():
				_dlg_chars = 9999.0
				get_viewport().set_input_as_handled()


func _unhandled_input(event: InputEvent) -> void:
	# 鼠标点地面：晨走过去（点到界面按钮上的点击不会到这里）
	if not _free() or _settings.visible or _bag.visible:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if _dlg_typing():
			_dlg_chars = 9999.0
		var wp: Vector2 = cam_left() + (event as InputEventMouseButton).position     # 用事件自己的位置（乱玩模式的假点击也对）
		var p: Dictionary = story.hotspots.at_point(wp) if state == S.PLAY else {}
		_pending_hs = {}
		if not p.is_empty():
			# 点到一个能互动的东西：在范围里就直接互动，不然走到它跟前（站在晨这一边）再互动
			var px := float(p["x"])
			if absf(chen.position.x - px) <= story.hotspots.range_of(p["h"]):
				_interact(p)
			else:
				_pending_hs = p
				_walk_target = px - signf(px - chen.position.x) * 10.0
		else:
			_walk_target = wp.x
		get_viewport().set_input_as_handled()


# ======================================================================= 每帧
func _process(delta: float) -> void:
	_t += delta
	_state_t += delta
	_stage_t += delta
	_frame += 1
	# 定时事件
	if not _seq.is_empty():
		_seq_t += delta
		while not _seq.is_empty() and _seq[0][0] <= _seq_t:
			var e: Array = _seq.pop_front()
			(e[1] as Callable).call()
	if _skip_armed > 0.0:
		_skip_armed -= delta
		if _skip_armed <= 0.0:
			create_tween().tween_property(_skip_label, "modulate:a", 0.0, 0.4)

	_update_walls()
	_update_front(delta)
	_update_camera(delta)
	_apply_flash()
	_update_world(delta)
	_update_dialogue(delta)
	_update_hints(delta)
	var cc := cam.get_screen_center_position()
	story.world.update(delta, cc)
	story.hotspots.active = state == S.PLAY and not story.busy and not _settings.visible and not _bag.visible
	story.hotspots.update(delta, chen, cc - Vector2(240, 135))
	if story.ended and _end_t >= 0.0:
		_end_t += delta

	# 耳机提示的「按任意键」慢慢呼吸
	if state == S.HEADPHONES:
		_hp_any.modulate.a = 0.45 + 0.35 * sin(_t * 2.4)
	if state == S.TITLE or _title_root.visible:
		_update_title(delta)

	_debug_tick()
	if _fuzz > 0.0:
		_fuzz_tick(delta)
		_softlock_tick(delta)


func _update_title(delta: float) -> void:
	# 标题：淡入时往上飘 3 像素（整像素）；之后很慢地呼吸（7 秒一次，亮度只差一点）
	var breath := 0.9 + 0.1 * sin(_t * TAU / 7.0)
	_title_label.modulate.a = _title_k * breath
	_title_label.position.y = TITLE_Y + roundf(3.0 * (1.0 - _title_k))
	# 「开始」：悬停 / 聚焦时变亮，两边的小横线从 0 伸到 8 像素
	var hot := _start_hover or _start_btn.has_focus()
	_start_hot = move_toward(_start_hot, 1.0 if hot else 0.0, delta * 6.0)
	var w := roundf(8.0 * _start_hot)
	var y := _start_btn.position.y + 10.0
	_start_marks[0].size.x = w
	_start_marks[1].size.x = w
	_start_marks[0].position = Vector2(_start_btn.position.x - 6.0 - w, y)
	_start_marks[1].position = Vector2(_start_btn.position.x + _start_btn.size.x - START_SPACING + 7.0, y)
	# 字色跟着 _start_hot 渐变（悬停 / 聚焦 / 方向键选中都一样，不是一下子跳亮）
	var fc := START_COLOR.lerp(START_HOT, _start_hot)
	if fc != _start_fc:
		_start_fc = fc
		for k in ["font_color", "font_hover_color", "font_focus_color", "font_pressed_color", "font_hover_pressed_color"]:
			_start_btn.add_theme_color_override(k, fc)
	var a := _start_btn.modulate.a
	for m in _start_marks:
		m.modulate.a = a * _start_hot * 0.8
	if not hot:
		_start_btn.self_modulate.a = 0.78 + 0.12 * sin(_t * 1.6)    # 没碰它的时候很轻地呼吸
	else:
		_start_btn.self_modulate.a = 1.0


func _update_camera(delta: float) -> void:
	match state:
		S.HEADPHONES, S.INTRO, S.TITLE:
			# 标题：镜头慢慢左右漂（50 秒一个来回，±18 像素）
			cam.position.x = TITLE_CAM_X + 18.0 * sin(_t * TAU / 50.0)
		S.PLAY, S.CINE:
			cam.position.x = lerpf(cam.position.x, _cam_target(), 1.0 - exp(-FOLLOW * delta))
	cam.position.y = 135.0
	if _shake > 0.0:
		_shake -= delta
		var a := _shake_amp * clampf(_shake / 0.8, 0.0, 1.0)
		cam.offset = Vector2(round(_rng.randf_range(-a, a)), round(_rng.randf_range(-a, a)))
	else:
		cam.offset = Vector2.ZERO


## 镜头跟着晨（往她面朝的方向多看一点）；在树屋里往屋子中心收一点
func _cam_target() -> float:
	var t: float = chen.position.x + chen.facing * LOOK
	if story != null and story.world.in_room():
		t = lerpf(t, float(story.world.house["cx"]), 0.55)
	return t


func _update_world(delta: float) -> void:
	# 光柱呼吸（和 forest_test 一样）
	if shafts.visible:
		var i := 0
		for s in shafts.get_children():
			(s as CanvasItem).modulate.a = 0.75 + 0.25 * sin(_t * 0.6 + i * 1.9)
			i += 1
	# 飞船喷口火焰两帧
	if ship.visible:
		_ship_frame_t += delta
		if _ship_frame_t > 0.08:
			_ship_frame_t = 0.0
			ship.frame = 1 - ship.frame
	# 发光木头：光晕慢慢呼吸，偶尔冒一颗光点
	if wood.visible:
		var b := 0.78 + 0.22 * sin(_t * 2.2) + 0.06 * sin(_t * 7.3)
		wood_glow.modulate.a = b
		(wood.get_node("Sprite") as CanvasItem).modulate = Color(1, 1, 1).lerp(Color(1.12, 1.06, 0.95), 0.5 + 0.5 * sin(_t * 2.2))
		if state in [S.PLAY, S.TITLE, S.CRASH] and _rng.randf() < delta * 1.2:
			puffs_front.burst(wood.position + Vector2(0, -4), 1, puffs_front.PRESETS.glint)
	# 自由走：鼠标点了地面就走过去；走到木头旁边进入拾取
	if _free():
		if not is_nan(_walk_target):
			var d := _walk_target - chen.position.x
			var keys := Input.get_axis("ui_left", "ui_right") != 0.0 or Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_D)
			if keys or absf(d) <= 4.0 + chen.stop_distance():     # 有惯性：提前松手，滑过去正好停住
				_walk_target = NAN
				chen.auto_dir = 0.0
			else:
				chen.auto_dir = signf(d)
		if state == S.PLAY and wood_available() and absf(chen.position.x - WOOD_X) <= PICK_DIST:
			chen.auto_dir = 0.0
			_pending_hs = {}
			_start_pickup()
		elif state == S.PLAY:
			_update_interact()
	elif state == S.CINE and not is_nan(_cine_target):
		var d := _cine_target - chen.position.x
		if absf(d) <= 3.0 + chen.stop_distance() or signf(d) != chen.auto_dir:
			_cine_target = NAN
			_pickup_at_wood()


## 自由走：鼠标点过的 hotspot 走到了就互动；走进 trigger:"enter" 的点自动触发
func _update_interact() -> void:
	if story.busy or _settings.visible or _bag.visible:
		return
	if not _pending_hs.is_empty():
		var p: Dictionary = _pending_hs
		var h: Dictionary = p["h"]
		if not story.hotspots.usable(h):
			_pending_hs = {}
		elif absf(chen.position.x - float(p["x"])) <= story.hotspots.range_of(h) and is_nan(_walk_target):
			_pending_hs = {}
			_interact(p)
			return
	var a: Dictionary = story.hotspots.auto_trigger(chen.position.x)
	if not a.is_empty():
		_interact(a)


func _interact(p: Dictionary) -> void:
	if story.busy or state != S.PLAY:
		return
	chen.auto_dir = 0.0
	_walk_target = NAN
	_pending_hs = {}
	story.trigger(p)


## 左右不可见的墙：自由走时顶着墙按方向键就松手（不原地跑），位置也夹回来
func _update_walls() -> void:
	if state == S.HEADPHONES or state == S.INTRO or state == S.TITLE or state == S.CRASH:
		return
	var w: Vector2 = story.world.walls(chen.position.x)
	if chen.position.x < w.x:
		chen.position.x = w.x
	elif chen.position.x > w.y:
		chen.position.x = w.y
	if not is_nan(_walk_target):
		_walk_target = clampf(_walk_target, w.x, w.y)
	var dir := Input.get_axis("ui_left", "ui_right")
	if Input.is_key_pressed(KEY_A):
		dir -= 1.0
	if Input.is_key_pressed(KEY_D):
		dir += 1.0
	var into := (chen.position.x <= w.x + 1.0 and dir < 0.0) or (chen.position.x >= w.y - 1.0 and dir > 0.0)
	if into and chen.input_enabled and _free():
		chen.input_enabled = false
		_wall_block = true
	elif _wall_block and not into:
		_wall_block = false
		if _free() and not _settings.visible and not _bag.visible:
			chen.input_enabled = true


## 前景层（Front，近黑的树干）：晨在树屋里 → 整层淡到 0；剧情播放时它的不透明像素挡住了说话的人或晨 → 淡到 FRONT_DIM，
## 这一段剧情播完再淡回来；平时照旧。按屏幕位置在 front.png 上取样判断（取不到图就不判断）。
const FRONT_DIM := 0.15
var _front_img: Image
var _front_latch := false


func _update_front(delta: float) -> void:
	var front: CanvasItem = $Front
	var target := 1.0
	if story.world.in_room():
		target = 0.0
	elif story.busy:
		if not _front_latch:
			for n in [chen, story.npc(story.speaking)]:
				if n != null and (n as Node2D).visible and _front_covers(n):
					_front_latch = true
		if _front_latch:
			target = FRONT_DIM
	else:
		_front_latch = false
	front.modulate.a = move_toward(front.modulate.a, target, delta * 2.0)


## 这个角色身上（脚到头、左右各几像素）有没有好几处被前景层的不透明像素盖住
func _front_covers(n: Node2D) -> bool:
	var spr: Sprite2D = $Front/Sprite
	if _front_img == null:
		_front_img = spr.texture.get_image()
		if _front_img != null and _front_img.is_compressed():
			_front_img.decompress()
	if _front_img == null:
		return false
	var inv := spr.get_global_transform_with_canvas().affine_inverse()
	var left := cam_left()
	var w := _front_img.get_width()
	var h := _front_img.get_height()
	var hits := 0
	for dx in [-9.0, -5.0, 0.0, 5.0, 9.0]:
		for dy in [4.0, 14.0, 24.0, 34.0, 44.0]:
			var p: Vector2 = inv * (n.position - left + Vector2(dx, -dy))
			var px := int(fposmod(floorf(p.x), float(w)))
			var py := int(floorf(p.y))
			if py >= 0 and py < h and _front_img.get_pixel(px, py).a > 0.5:
				hits += 1
	return hits >= 3


## 自由走（含鹿带路时：剧情没播完但晨能自己走）
func _free() -> bool:
	return state == S.PLAY or (state == S.CINE and story != null and story.free_walk)


func _update_hints(delta: float) -> void:
	# 木头上方的小箭头：能走以后 2.5 秒出现，上下浮 1 像素，很淡地闪
	if state == S.PLAY and wood.visible:
		_hint_wait += delta
		if _hint_wait > 2.5:
			wood_hint.visible = true
			wood_hint.position.y = -16.0 - (1.0 if fmod(_t, 1.2) < 0.6 else 0.0)
			wood_hint.modulate.a = clampf((_hint_wait - 2.5) / 0.8, 0.0, 1.0) * (0.55 + 0.35 * sin(_t * 3.0))
	# 「← →」：能走以后 1.5 秒还没动就在晨脚下出现，动了就消失
	var show_keys := state == S.PLAY and wood.visible and not is_nan(_moved_from) \
		and absf(chen.position.x - _moved_from) < 14.0 and _state_t > 1.5 and not _bag.visible and not _settings.visible
	var target_a := (0.35 + 0.2 * sin(_t * 2.6)) if show_keys else 0.0
	_keys_hint.modulate.a = move_toward(_keys_hint.modulate.a, target_a, delta * 1.5)
	if _keys_hint.modulate.a > 0.0:
		var sx := chen.position.x - (cam.get_screen_center_position().x - 240.0)
		_keys_hint.position = Vector2(round(sx - 20.0), chen.position.y + 6.0)


# ======================================================================= 给剧本引擎用（story_runner.gd 调）
func story_begin(bars: bool) -> void:
	_set_state(S.CINE)
	chen.input_enabled = false
	chen.auto_dir = 0.0
	_walk_target = NAN
	_pending_hs = {}
	_leave_play_ui()
	_dlg_hide(0.3)
	_story_bars = bars
	if bars:
		_bars_in(0.5)


func story_end() -> void:
	if _story_bars:
		_bars_out(0.5)
	_story_bars = false
	_enter_play()


## 鹿带路：剧情没播完，晨先自己走（黑边收起）
func story_free(on: bool) -> void:
	chen.input_enabled = on
	_walk_target = NAN
	if on and _story_bars:
		_bars_out(0.4)
		_story_bars = false


func bars_on() -> bool:
	return _bars[0].position.y > -BAR_H + 1.0


func cam_left() -> Vector2:
	return cam.get_screen_center_position() - Vector2(240, 135)


func free_play() -> bool:
	return state == S.PLAY and not _settings.visible and not _bag.visible and not story.busy


func walk_to(x: float) -> void:
	_walk_target = x


func walking() -> bool:
	return not is_nan(_walk_target) or chen._vel > 0.0


func wood_available() -> bool:
	return wood.visible and not story.world.in_room()


## 跳节拍：木头直接进背包，剧本里木头那个 scene 瞬间过一遍
func ff_take_wood() -> void:
	wood.visible = false
	wood_hint.visible = false
	if not Inventory.has("glowing_wood"):
		Inventory.add("glowing_wood")
	on_inventory_changed()
	var h: String = story.hook("wood")
	if h != "":
		await story.play_wood(h)
	StoryState.set_flag("got_wood")


## 背包变了：HUD、背包图标、燃烧值够了设 fuel_full
func on_inventory_changed() -> void:
	_update_hud()
	if not Inventory.owned.is_empty():
		_bag_btn.visible = true
		_bag_btn.modulate.a = 1.0
	if Inventory.burn_total() > Inventory.base_burn and _seq.is_empty():
		_hud_burn.modulate.a = 1.0          # 木头拾取过场里先不亮（燃烧值滚完才收进左上角）
	if Inventory.burn_total() >= Inventory.get_launch_burn():
		StoryState.set_flag("fuel_full")
	if _bag.visible:
		_bag_refresh()


func bag_target() -> Vector2:
	return _bag_btn.position + _bag_btn.size / 2.0


func bag_bump() -> void:
	_sfx("tick", -6.0, 0.8)
	_bag_btn.scale = Vector2(1.5, 1.5)
	create_tween().tween_property(_bag_btn, "scale", Vector2.ONE, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


func fade_to_black(sec: float) -> void:
	var tw := create_tween()
	tw.tween_property(fade, "color:a", 1.0, sec).set_trans(Tween.TRANS_SINE)
	await tw.finished


func fade_from_black(sec: float) -> void:
	var tw := create_tween()
	tw.tween_property(fade, "color:a", 0.0, sec).set_trans(Tween.TRANS_SINE)
	await tw.finished


## 换了位置：黑屏换地方时镜头直接跳过去、雾直接到位（进出屋不黑屏，镜头照常跟）；屋里雨声小一点
func on_room_changed(snap := true) -> void:
	_walk_target = NAN
	_pending_hs = {}
	if snap:
		_snap_camera()
		story.world.fog_k = story.world.fog_at(cam.position.x)
	_fade_db(_rain, -16.0 if story.world.in_room() else -9.0, 0.6)


func _snap_camera() -> void:
	cam.position = Vector2(_cam_target(), 135.0)
	cam.reset_smoothing()


## 剧本里不是图的物件：ship:launch = 晨上船、船身抖、喷口冒烟
func _on_pseudo_prop(id: String, st: String) -> void:
	if id == "ship" and st == "launch":
		if chen.visible and not story.ff:
			puffs_front.burst(chen.position + Vector2(0, -2), 6, puffs_front.PRESETS.dust_small)
		chen.visible = false
		if story.ff:
			return
		_shake = 2.2
		_shake_amp = 1.5
		if not wreck.visible:
			_show_wreck()
		puffs_back.add_source("launch", wreck.position + WRECK_ENGINE, 18.0, puffs_back.PRESETS.smoke.merged({"spread": Vector2(6, 3)}))
		puffs_front.add_source("launch_embers", wreck.position + WRECK_HOLE, 6.0, puffs_front.PRESETS.ember)


## 起飞：坠毁的船换成开场那张飞行图，船头朝右上，先慢慢抬起来再加速飞出屏幕右上角 → 黑屏
func story_takeoff() -> void:
	chen.visible = false
	_bars_in(0.6)
	_sfx("ship_whoosh", -4.0, 0.85)
	for k in ["wreck", "wreck2", "wreck3", "embers", "embers2", "launch", "launch_embers"]:
		puffs_back.remove_source(k)
		puffs_front.remove_source(k)
	_fade_db(_crackle, -80.0, 1.0)
	var start := wreck.position + WRECK_CENTER
	puffs_front.burst(wreck.position + Vector2(0, -2), 30, puffs_front.PRESETS.dust.merged({"spread": Vector2(50, 1)}))
	puffs_back.burst(wreck.position + Vector2(0, -10), 16, puffs_back.PRESETS.smoke_burst)
	wreck.visible = false
	ship.visible = true
	ship.frame = 0
	ship.flip_h = true
	ship.rotation = -0.52
	ship.position = start.round()
	_shake = 1.2
	_shake_amp = 3.0
	_path_a = start
	_path_b = Vector2(cam_left().x + 480.0 + 140.0, -90.0)
	var eng := _takeoff_engine()
	puffs_back.add_source("trail", ship.position + eng, 46.0, puffs_back.PRESETS.trail)
	puffs_back.add_source("trail_sparks", ship.position + eng, 10.0, puffs_back.PRESETS.ember)
	var tw := create_tween()
	tw.tween_method(_takeoff_step, 0.0, 1.0, 3.4).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	await tw.finished
	puffs_back.remove_source("trail")
	puffs_back.remove_source("trail_sparks")
	ship.visible = false
	await get_tree().create_timer(0.6).timeout
	await fade_to_black(1.6)
	_end_t = 0.0
	_fade_db(_rain, -30.0, 3.0)


func _takeoff_engine() -> Vector2:
	return Vector2(-SHIP_ENGINE.x, SHIP_ENGINE.y).rotated(ship.rotation)


func _takeoff_step(k: float) -> void:
	# 先往上抬（横着几乎不动），再斜着冲出去
	var p := Vector2(lerpf(_path_a.x, _path_b.x, k * k), lerpf(_path_a.y, _path_b.y, k))
	ship.position = p.round()
	puffs_back.set_source_pos("trail", ship.position + _takeoff_engine())
	puffs_back.set_source_pos("trail_sparks", ship.position + _takeoff_engine())


## --beat=flag：坠毁跳过，剧情瞬间过一遍到那个 flag
func _jump_beat(flag: String) -> void:
	story.ff = true
	story.dlg.instant = true
	_skip_to_title()
	_start_crash()
	_skip_crash()
	_dlg_hide(0.01)
	var ok: bool = await story.fast_forward(flag)
	story.ff = false
	story.dlg.instant = false
	print("STORY_BEAT %s %s  flags=%s  items=%s  x=%.0f room=%s" % [flag, "ok" if ok else "NOT REACHED",
		", ".join(StoryState.flag_order), ", ".join(Inventory.owned), chen.position.x, story.world.room])
	chen.visible = not StoryState.has("launched")
	if state != S.PLAY:
		_enter_play()
	if story.ff_hit_end:
		story.ff_hit_end = false
		story.play_end()
	if not is_nan(_dbg_chen_x):
		chen.position.x = _dbg_chen_x
		chen.position.y = round(chen.ground_fn.call(_dbg_chen_x)) + 1
		_snap_camera()
	if _dbg_bag != "":
		_toggle_bag()
		var i := Inventory.owned.find(_dbg_bag)
		if i >= 0:
			_bag_select(i)
			_bag_slots[i].grab_focus()
	on_room_changed()
	_hud_burn.modulate.a = 1.0 if Inventory.burn_total() > Inventory.base_burn else 0.0
	_stage_t = 0.0


# ======================================================================= 调试：跳段、截图
func _jump(stage: String) -> void:
	match stage:
		"headphones":
			pass
		"title":
			_skip_to_title()
		"settings":
			_skip_to_title()
			_open_settings()
		"crash":
			_skip_to_title()
			_start_crash()
		"play":
			_skip_to_title()
			_start_crash()
			_skip_crash()
		"wood", "burn":
			_skip_to_title()
			_start_crash()
			_skip_crash_instant()
			_dlg_hide(0.01)
			chen.position.x = WOOD_X - 40.0
			cam.position.x = chen.position.x + LOOK
			_walk_target = WOOD_X
		"bag":
			_skip_to_title()
			_start_crash()
			_skip_crash_instant()
			_dlg_hide(0.01)
			wood.visible = false
			Inventory.add("glowing_wood")
			on_inventory_changed()
			_update_hud()
			_hud_burn.modulate.a = 1.0
			_bag_btn.visible = true
			_bag_btn.modulate.a = 1.0
			chen.position.x = WOOD_X - 8.0
			cam.position.x = chen.position.x + LOOK
			_toggle_bag()
	_stage_t = 0.0


# ======================================================================= 调试：乱玩（--story_fuzz）和卡死检测
func toggle_dev() -> void:
	if not OS.is_debug_build():
		return
	if _dev == null:
		_dev = DEV_GD.new()
		_dev.name = "DevPanel"
		_dev.level = self
		add_child(_dev)
		_dev.call("_set_tab", _dev_tab)
	else:
		_dev.toggle()


## 面板「传送」：晨直接到 marker（room_* 进屋、别的出屋），剧情在播就先不动
func dev_teleport(name: String) -> void:
	if story.busy:
		return
	var r: Dictionary = story.world.resolve(name)
	if not r["ok"]:
		return
	var room: String = "treehouse" if name.begins_with("room_") else "forest"
	story._teleport(room, float(r["x"]), [], true)
	_walk_target = NAN


func _fuzz_key(k: int, pressed: bool) -> void:
	var e := InputEventKey.new()
	e.keycode = k as Key
	e.physical_keycode = k as Key
	e.pressed = pressed
	Input.parse_input_event(e)


func _fuzz_tick(delta: float) -> void:
	_fuzz_t += delta
	if state == S.PLAY or story.free_walk:
		_fuzz_xmin = minf(_fuzz_xmin, chen.position.x)
		_fuzz_xmax = maxf(_fuzz_xmax, chen.position.x)
	if _fuzz_t >= _fuzz:
		print("FUZZ_DONE seed=%d t=%.0f softlocks=%d state=%s x=%.0f..%.0f scenes=%d flags=%s" % [_fuzz_rng.seed, _fuzz_t, softlocks,
			S.keys()[state], _fuzz_xmin, _fuzz_xmax, story.played_order.size(), ", ".join(StoryState.flag_order)])
		get_tree().quit(1 if softlocks > 0 else 0)
		_fuzz = 0.0
		return
	if _fuzz_hold != 0:
		_fuzz_hold_t -= delta
		if _fuzz_hold_t <= 0.0:
			_fuzz_key(_fuzz_hold, false)
			_fuzz_hold = 0
	_fuzz_next -= delta
	if _fuzz_next > 0.0:
		return
	_fuzz_next = _fuzz_rng.randf_range(0.05, 0.7)
	var r := _fuzz_rng.randf()
	if r < 0.45:
		# 按住方向键一会儿（往右多一点，才走得远）
		if _fuzz_hold != 0:
			_fuzz_key(_fuzz_hold, false)
		var keys := [KEY_RIGHT, KEY_RIGHT, KEY_D, KEY_LEFT, KEY_A]
		_fuzz_hold = keys[_fuzz_rng.randi() % keys.size()]
		_fuzz_hold_t = _fuzz_rng.randf_range(0.1, 2.8)
		_fuzz_key(_fuzz_hold, true)
	elif r < 0.72:
		var keys := [KEY_E, KEY_SPACE, KEY_ENTER, KEY_Z]
		var k: int = keys[_fuzz_rng.randi() % keys.size()]
		_fuzz_key(k, true)
		_fuzz_key(k, false)
	elif r < 0.8:
		_fuzz_key(KEY_TAB, true)
		_fuzz_key(KEY_TAB, false)
	elif r < 0.84:
		_fuzz_key(KEY_ESCAPE, true)
		_fuzz_key(KEY_ESCAPE, false)
	elif r < 0.88:
		var k: int = [KEY_UP, KEY_DOWN][_fuzz_rng.randi() % 2]
		_fuzz_key(k, true)
		_fuzz_key(k, false)
	else:
		# 乱点：画面上随便一点（地面、东西、按钮都可能）
		var e := InputEventMouseButton.new()
		e.button_index = MOUSE_BUTTON_LEFT
		e.position = Vector2(_fuzz_rng.randf_range(0, 480), _fuzz_rng.randf_range(20, 260))
		e.global_position = e.position
		e.pressed = true
		get_viewport().push_input(e, true)
		var e2 := e.duplicate() as InputEventMouseButton
		e2.pressed = false
		get_viewport().push_input(e2, true)


## 卡死：该能走的时候晨收不到输入超过 3 秒，或者剧情某一步停了 20 秒还没有人在等的东西
func _softlock_tick(delta: float) -> void:
	var panels := _settings.visible or _bag.visible
	var dir := Input.get_axis("ui_left", "ui_right")
	var w: Vector2 = story.world.walls(chen.position.x)
	var pushing_wall := (chen.position.x <= w.x + 1.0 and dir < 0.0) or (chen.position.x >= w.y - 1.0 and dir > 0.0)
	var why := ""
	if story.ended or state in [S.HEADPHONES, S.INTRO, S.TITLE, S.CRASH]:
		why = ""
	elif state == S.PLAY and not panels and not story.busy and fade.color.a < 0.01 and not chen.input_enabled and not pushing_wall:
		why = "自由走但晨收不到输入"
	elif _free() and story.free_walk and not chen.input_enabled and not pushing_wall and not panels:
		why = "鹿带路时晨收不到输入"
	elif state == S.CINE and not story.busy and _seq.is_empty() and is_nan(_cine_target):
		why = "过场状态但没有剧情在播"
	elif story.busy and not story.free_walk and not story.dlg.is_open() and not story.dlg.picking() and story.step_t > 20.0:
		why = "剧情一步停了 20 秒（STUCK_SCENE）"
	if why == "":
		_lock_t = 0.0
		_lock_reported = false
		return
	_lock_t += delta
	if _lock_t > 3.0 and not _lock_reported:
		_lock_reported = true
		softlocks += 1
		print("SOFTLOCK %s | t=%.1f state=%s busy=%s scene=%s step=%d free_walk=%s input=%s wall_block=%s panels=%s fade=%.2f x=%.0f room=%s seq=%d flags=%s" % [
			why, _fuzz_t, S.keys()[state], story.busy, story._cur_scene, story.step_i, story.free_walk, chen.input_enabled,
			_wall_block, panels, fade.color.a, chen.position.x, story.world.room, _seq.size(), ", ".join(StoryState.flag_order)])


## 跳段用：坠毁跳过，剧本的 intro 瞬间过完（直接能走）
func _skip_crash_instant() -> void:
	story.ff = true
	story.dlg.instant = true
	_skip_crash()
	story.ff = false
	story.dlg.instant = false


func _debug_tick() -> void:
	if _browse > 0 and state == S.TITLE and _state_t > 0.5 and not Engine.has_meta("level_forest_browsed"):
		Engine.set_meta("level_forest_browsed", true)
		_open_test_scene(TEST_SCENES[KEY_F1 + _browse - 1], 2.5)
		_browse = 0
	elif _browse_out != "" and Engine.has_meta("level_forest_browsed") and state == S.TITLE and _state_t > 2.0:
		_save(_browse_out.path_join("back.png"))
		get_tree().quit()
	if _story_auto != "" and not _autoplay:
		if state == S.HEADPHONES and _state_t > 1.0:
			_leave_headphones()
		elif state == S.TITLE and _state_t > 1.2:
			_on_start()
	if _autoplay:
		if state == S.HEADPHONES and _state_t > 1.0:
			_leave_headphones()
		elif state == S.TITLE and _state_t > 1.2:
			_on_start()
		elif state == S.PLAY and _state_t > 2.0 and wood.visible and is_nan(_walk_target):
			_walk_target = WOOD_X
	if _shot != "" and _stage_t >= _shot_at:
		_save(_shot)
		_shot = ""
		get_tree().quit()
	if _shots_dir != "" and _frame >= _shots_start and (_frame - _shots_start) % _shots_every == 0:
		_save(_shots_dir.path_join("shot_%04d.png" % _shots_saved))
		_shots_saved += 1
		if _shots_saved >= _shots_count:
			get_tree().quit()


## n×n 的像素叉（两条 1 像素宽的对角线），当关闭按钮的图标
static func _pixel_cross(n: int, c: Color) -> ImageTexture:
	var img := Image.create_empty(n, n, false, Image.FORMAT_RGBA8)
	for i in n:
		img.set_pixel(i, i, c)
		img.set_pixel(n - 1 - i, i, c)
	return ImageTexture.create_from_image(img)


func _save(path: String) -> void:
	RenderingServer.force_draw(false)
	get_viewport().get_texture().get_image().save_png(path)


# ======================================================================= 调试：场景浏览（只在 debug 构建）
const BACK_META := "level_forest_back_to_title"


func _open_test_scene(path: String, auto_back := 0.0) -> void:
	if not ResourceLoader.exists(path):
		push_warning("没有这个测试场景：" + path)
		return
	var b := SceneBrowser.new()
	b.name = "SceneBrowser"
	b.scene_name = path.get_file().get_basename()
	b.auto_back = auto_back
	if auto_back > 0.0 and _browse_out != "":
		b.shot = _browse_out.path_join("scene.png")
	get_tree().root.add_child(b)
	get_tree().change_scene_to_file(path)


## 挂在 root 下（换场景不会被删），一直排在 root 的最后一个，所以 Esc 比测试场景自己先收到。
## Esc：回第一关的标题界面，然后把自己删掉。左上角一行很淡的小字提示。
class SceneBrowser extends Node:
	var scene_name := ""
	var auto_back := 0.0      # 调试（--browse）：过几秒自己回去，回去前存一张图到 shot
	var shot := ""
	var _t := 0.0

	func _ready() -> void:
		process_mode = Node.PROCESS_MODE_ALWAYS
		var layer := CanvasLayer.new()
		layer.layer = 120
		add_child(layer)
		var l := Label.new()
		l.theme = UITheme.get_theme()
		l.text = scene_name + "   Esc: back to title"
		l.add_theme_color_override("font_color", Color(0.75, 0.85, 0.8, 0.45))
		l.position = Vector2(6, 4)
		l.mouse_filter = Control.MOUSE_FILTER_IGNORE
		layer.add_child(l)
		# 几秒后淡掉，免得一直压在测试场景自己的界面上（飞行的进度条就在左上角）
		create_tween().tween_property(l, "modulate:a", 0.0, 1.0).set_delay(3.0)

	func _process(delta: float) -> void:
		var p := get_parent()
		if p != null and get_index() != p.get_child_count() - 1:
			p.move_child(self, -1)
		if auto_back > 0.0:
			_t += delta
			if _t >= auto_back:
				if shot != "":
					RenderingServer.force_draw(false)
					get_viewport().get_texture().get_image().save_png(shot)
				_back()

	func _input(e: InputEvent) -> void:
		if e is InputEventKey and e.pressed and not e.echo and e.keycode == KEY_ESCAPE:
			get_viewport().set_input_as_handled()
			_back()

	func _back() -> void:
		get_tree().paused = false
		Engine.set_meta(BACK_META, true)
		get_tree().change_scene_to_file(SELF_SCENE)
		queue_free()
