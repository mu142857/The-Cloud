extends Node2D
## 第一关：木星的森林。从开场到捡起第一块发光木头。
##
## 流程（state）：
##   HEADPHONES  黑屏，「建议佩戴耳机」+「点击或按任意键继续」（顺便解锁网页版的声音）
##   INTRO       雨声淡入 → 两声远雷 → 黑屏淡入森林
##   TITLE       标题界面：游戏名、正中「开始游戏」、右下角设置齿轮；镜头慢慢左右漂
##   CRASH       开场动画（上下黑边）：三次闪电 + 近雷 → 冒烟的飞船从右上斜着坠下 → 撞地（震屏、尘土、浓烟）
##               → 晨被甩出来脸朝下趴着 → 爬起来 → 对话「啊……糟糕……」。确认键 / 点击按两次可以跳过。
##   PLAY        自由走（←/→、A/D，或者鼠标点地面走过去）。发光木头上方有一个很轻的小箭头。
##   CINE        走到木头旁边：黑边滑入、锁操作、晨自己走到木头前捡起来 → 木头飞进背包 → 对话「太好了……」
##               → 燃烧值从 10 滚到 60，「燃烧值到 200 就能起飞」→ 收进左上角 → 黑边滑出、恢复操作
## 任何时候：Esc / 右下角齿轮 = 设置；Tab / B / I / 右上角背包图标 = 背包（捡到第一件东西以后才出现）。
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
## 例：Godot --path . --fixed-fps 60 -- --stage=crash --shot=/tmp/a.png --shot_at=3.6

enum S { HEADPHONES, INTRO, TITLE, CRASH, PLAY, CINE }

const LOOK := 36.0            # 镜头往晨面朝的方向多看多少像素（和 forest_test 一样）
const FOLLOW := 3.0
const TITLE_CAM_X := 236.0    # 标题界面镜头中心；晨爬起来时镜头也在这
const CHEN_X := 200.0         # 晨趴着的地方
const WRECK_X := 150.0        # 坠毁飞船（锚点 = 机身中线和地面）
const WOOD_X := 372.0         # 发光木头
const PICK_DIST := 26.0       # 晨走到离木头这么近就进入拾取过场
const LIE_LIFT := 9.0         # 没有 lie / getup 动画时的老办法：趴着时精灵往上抬几像素（转 90° 以后身体的厚度一半在地下）
const CHEN_GD := preload("res://scripts/chen.gd")
## 晨的精灵配置里有没有「趴着 / 爬起来」两段（tools/level1_chen_getup.py）。没有就退回把站立帧转 90° 的老办法。
var _has_getup: bool = CHEN_GD.ANIMS.has("lie") and CHEN_GD.ANIMS.has("getup")
## getup 一段多长（秒），和各帧什么时候换（跪坐、站直那两下扬一点土）
const GETUP_KNEEL_AT := 1.18
const GETUP_STAND_AT := 1.80
const GETUP_TIME := 1.95

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

## 闪电：不再是整屏白闪，而是冷色的天光从林冠后面亮一下（远景几层被照亮，近处的树干、林冠成了剪影），
## 再叠一层很淡的冷色。下面是每层被照亮多少（0 = 不动）和冷光的颜色（乘到图层上，>1 = 变亮）。
const FLASH_LAYERS := {"Sky": 1.0, "Ridge": 0.9, "Far": 0.75, "MidFar": 0.45, "Mid": 0.18}
const FLASH_GAIN := Color(0.35, 0.62, 0.9)      # 闪到最亮时远景乘 (1+0.35, 1+0.62, 1+0.9)：偏青蓝，不是白
const FLASH_TINT := Color(0.55, 0.72, 0.86)      # 整屏那层薄薄的冷光
const FLASH_TINT_A := 0.09                       # 它最多这么不透明
const IMPACT_TINT := Color(1.0, 0.72, 0.45)      # 撞地那一下是暖的、很弱
const BAR_H := 26             # 电影黑边高度
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
	if _shots_dir != "":
		DirAccess.make_dir_recursive_absolute(_shots_dir)
	if _debug_stage != "" or _shot != "" or _shots_dir != "" or _autoplay or _browse > 0:
		GameSettings.no_save = true
		AudioServer.set_bus_mute(0, true)    # 截图 / 录像时不出声，也不吃真的键盘鼠标（见 _input）

	chen.input_enabled = false
	cam.position = Vector2(TITLE_CAM_X, 135.0)
	_place_world()
	_apply_quality()
	_build_audio()
	_build_ui()
	_retext()
	_enter_headphones()
	if Engine.has_meta(BACK_META):          # 从测试场景按 Esc 回来：直接到标题（雨声照常）
		Engine.remove_meta(BACK_META)
		_skip_to_title()
	if _debug_stage != "":
		_jump(_debug_stage)


# ======================================================================= 世界摆放
func _ground(x: float) -> float:
	return round(chen.ground_fn.call(x))


func _place_world() -> void:
	wreck.position = Vector2(WRECK_X, _ground(WRECK_X) + 1)
	wood.position = Vector2(WOOD_X, _ground(WOOD_X))
	chen.position = Vector2(CHEN_X, _ground(CHEN_X) + 1)


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
	# 左：格子 4 × 4
	var grid := GridContainer.new()
	grid.columns = 4
	grid.position = Vector2(10, 30)
	grid.add_theme_constant_override("h_separation", 3)
	grid.add_theme_constant_override("v_separation", 3)
	_bag.add_child(grid)
	var slot_box := UITheme.box(Color(0.06, 0.1, 0.09, 0.9), Color(0.22, 0.3, 0.26), 1, Vector4(0, 0, 0, 0))
	var slot_hover := UITheme.box(Color(0.1, 0.16, 0.14, 0.95), Color(0.5, 0.62, 0.56), 1, Vector4(0, 0, 0, 0))
	var slot_sel := UITheme.box(Color(0.14, 0.12, 0.14, 0.95), UITheme.ACCENT, 1, Vector4(0, 0, 0, 0))
	for i in 16:
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
	burn.position = Vector2(230, 84)
	burn.size = Vector2(112, 16)
	burn.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_bag.add_child(burn)
	_bag_w["burn"] = burn
	var desc := _label("", 14, Color("#b9c9bf"))
	desc.position = Vector2(130, 120)
	desc.size = Vector2(212, 88)
	desc.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	desc.add_theme_constant_override("line_spacing", 2)
	_bag.add_child(desc)
	_bag_w["desc"] = desc


func _bag_refresh() -> void:
	_bag_w["title"].text = I18n.t("bag")
	_bag_w["total"].text = I18n.t("burn_total") % [Inventory.burn_total(), Inventory.get_launch_burn()]
	for i in _bag_slots.size():
		var b := _bag_slots[i]
		var ic: TextureRect = b.get_meta("icon")
		if i < Inventory.owned.size():
			var it := Inventory.item(Inventory.owned[i])
			ic.texture = load(it.get("icon", ""))
		else:
			ic.texture = null
		b.add_theme_stylebox_override("normal", b.get_meta("sel_box") if i == _bag_sel else b.get_meta("box"))
	var big: TextureRect = _bag_w["big"]
	if _bag_sel < Inventory.owned.size():
		var it := Inventory.item(Inventory.owned[_bag_sel])
		var tex: Texture2D = load(it.get("icon", ""))
		var k := maxi(1, mini(int(200 / tex.get_width()), int(42 / tex.get_height())))
		big.texture = tex
		big.size = tex.get_size() * k
		big.position = ((Vector2(212, 50) - big.size) / 2).floor()
		var rc := Inventory.rarity_color(it.get("rarity", "common"))
		_bag_w["name"].text = I18n.pick(it.get("name", ""))
		_bag_w["name"].add_theme_color_override("font_color", rc)
		_bag_w["rarity"].text = I18n.t("rarity_" + str(it.get("rarity", "common")))
		_bag_w["rarity"].add_theme_color_override("font_color", rc.darkened(0.25))
		_bag_w["burn"].text = I18n.t("personal") if it.get("personal", false) else I18n.t("burn_value") % int(it.get("burn", 0))
		_bag_w["desc"].text = I18n.pick(it.get("desc", ""))
	else:
		big.texture = null
		_bag_w["name"].text = ""
		_bag_w["rarity"].text = ""
		_bag_w["burn"].text = ""
		_bag_w["desc"].text = I18n.t("bag_empty") if Inventory.owned.is_empty() else ""


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


# 飞船飞行图的中心到机头 / 喷口（tools/level1_art.py：斜 18°）
const SHIP_NOSE := Vector2(-21, 7)
const SHIP_ENGINE := Vector2(24, -8)


func _ship_end() -> Vector2:
	# 机头扎进坠毁图里机头的位置（wreck 锚点左边 16 像素、地面）
	return Vector2(WRECK_X - 16, _ground(WRECK_X - 16)) - SHIP_NOSE


func _ship_start() -> Vector2:
	return Vector2(cam.position.x + 240 + 40, 18)


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
	var nose := Vector2(WRECK_X - 16, _ground(WRECK_X - 16))
	_sfx("ship_impact", -1.0)
	_shake = 0.8
	_shake_amp = 5.0
	_flash_k = 0.0
	puffs_front.burst(nose, 44, puffs_front.PRESETS.dust)
	puffs_back.burst(nose + Vector2(8, -6), 26, puffs_back.PRESETS.smoke_burst)
	puffs_front.burst(nose + Vector2(6, -4), 12, puffs_front.PRESETS.ember)
	var tw := _tw()
	_impact_k = 0.0
	tw.tween_property(self, "_impact_k", 1.0, 0.03)
	tw.tween_property(self, "_impact_k", 0.0, 0.4)
	_chen_thrown()


func _show_wreck() -> void:
	wreck.visible = true
	# 烟柱从机尾（翘起来的那头）冒；火星很少
	var tail := wreck.position + Vector2(18, -26)
	puffs_back.add_source("wreck", tail, 11.0, puffs_back.PRESETS.smoke)
	puffs_back.add_source("wreck2", wreck.position + Vector2(2, -12), 4.0, puffs_back.PRESETS.smoke)
	puffs_front.add_source("embers", tail + Vector2(0, 2), 2.0, puffs_front.PRESETS.ember)
	if not _crackle.playing:
		_crackle.play()
		_fade_db(_crackle, -16.0, 2.0)


func _chen_thrown() -> void:
	chen.visible = true
	chen._set_facing(1)
	_path_a = Vector2(WRECK_X + 6, _ground(WRECK_X) - 22)
	_path_b = Vector2(CHEN_X, _ground(CHEN_X) + 1)
	chen.position = _path_a
	chen.spr.rotation = -0.6
	var tw := _tw()
	tw.tween_method(_thrown_step, 0.0, 1.0, 0.62).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tw.tween_callback(_chen_landed)


func _thrown_step(k: float) -> void:
	# 被甩出来：一道小弧线，转一圈多一点，最后脸朝下
	var p := _path_a.lerp(_path_b, k)
	p.y -= sin(k * PI) * 26.0
	chen.position = p.round()
	var r := lerpf(-0.6, PI / 2.0 + TAU, k)
	if _has_getup:
		# 空中翻滚按 90° 一档一档转（像素一一对应，不出斜着的 mixel），绕身体中间转
		r = snappedf(r, PI / 2.0)
		var c := Vector2(0, -21)
		chen.spr.position = (c - c.rotated(r) + Vector2(0, 15.0 * k)).round()
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


func _chen_get_up() -> void:
	var spr: AnimatedSprite2D = chen.spr
	var tw := _tw()
	if _has_getup:
		# 拼出来的几帧：抽一下 → 又趴回去 → 撑起上身 → 跪坐 → 半蹲 → 站直（chen.gd 的 getup，播完自己回 idle）
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
	_bars_out(0.7)
	_say("who_chen", "line_crash")
	_enter_play()


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
	_run([
		[0.25, _pk_crouch],
		[0.35, _pk_lift],
		[1.0, _pk_show_bag],
		[1.35, _wood_fly_to_bag],
		[2.15, _say.bind("who_chen", "line_wood")],
		[4.6, _burn_roll],
		[9.6, _burn_to_hud],
		[10.3, _pickup_done],
	])


func _pk_crouch() -> void:
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
	_bag_sel = clampi(_bag_sel, 0, maxi(0, Inventory.owned.size() - 1))
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
	if _autoplay or _shots_dir != "" or _shot != "":
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
			if event.is_action_pressed("ui_accept") and _dlg_typing():
				_dlg_chars = 9999.0
				get_viewport().set_input_as_handled()


func _unhandled_input(event: InputEvent) -> void:
	# 鼠标点地面：晨走过去（点到界面按钮上的点击不会到这里）
	if state != S.PLAY or _settings.visible or _bag.visible:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if _dlg_typing():
			_dlg_chars = 9999.0
		_walk_target = get_global_mouse_position().x
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

	_update_camera(delta)
	_apply_flash()
	_update_world(delta)
	_update_dialogue(delta)
	_update_hints(delta)

	# 耳机提示的「按任意键」慢慢呼吸
	if state == S.HEADPHONES:
		_hp_any.modulate.a = 0.45 + 0.35 * sin(_t * 2.4)
	if state == S.TITLE or _title_root.visible:
		_update_title(delta)

	_debug_tick()


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
			var target: float = chen.position.x + chen.facing * LOOK
			cam.position.x = lerpf(cam.position.x, target, 1.0 - exp(-FOLLOW * delta))
	cam.position.y = 135.0
	if _shake > 0.0:
		_shake -= delta
		var a := _shake_amp * clampf(_shake / 0.8, 0.0, 1.0)
		cam.offset = Vector2(round(_rng.randf_range(-a, a)), round(_rng.randf_range(-a, a)))
	else:
		cam.offset = Vector2.ZERO


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
	if state == S.PLAY:
		if not is_nan(_walk_target):
			var d := _walk_target - chen.position.x
			var keys := Input.get_axis("ui_left", "ui_right") != 0.0 or Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_D)
			if keys or absf(d) <= 4.0:
				_walk_target = NAN
				chen.auto_dir = 0.0
			else:
				chen.auto_dir = signf(d)
		if wood.visible and absf(chen.position.x - WOOD_X) <= PICK_DIST:
			chen.auto_dir = 0.0
			_start_pickup()
	elif state == S.CINE and not is_nan(_cine_target):
		var d := _cine_target - chen.position.x
		if absf(d) <= 3.0 or signf(d) != chen.auto_dir:
			_cine_target = NAN
			_pickup_at_wood()


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
			_skip_crash()
			_dlg_hide(0.01)
			chen.position.x = WOOD_X - 40.0
			cam.position.x = chen.position.x + LOOK
			_walk_target = WOOD_X
		"bag":
			_skip_to_title()
			_start_crash()
			_skip_crash()
			_dlg_hide(0.01)
			wood.visible = false
			Inventory.add("glowing_wood")
			_update_hud()
			_hud_burn.modulate.a = 1.0
			_bag_btn.visible = true
			_bag_btn.modulate.a = 1.0
			chen.position.x = WOOD_X - 8.0
			cam.position.x = chen.position.x + LOOK
			_toggle_bag()
	_stage_t = 0.0


func _debug_tick() -> void:
	if _browse > 0 and state == S.TITLE and _state_t > 0.5 and not Engine.has_meta("level_forest_browsed"):
		Engine.set_meta("level_forest_browsed", true)
		_open_test_scene(TEST_SCENES[KEY_F1 + _browse - 1], 2.5)
		_browse = 0
	elif _browse_out != "" and Engine.has_meta("level_forest_browsed") and state == S.TITLE and _state_t > 2.0:
		_save(_browse_out.path_join("back.png"))
		get_tree().quit()
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
