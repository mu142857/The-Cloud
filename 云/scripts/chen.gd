extends Node2D
## 主角「晨」：←/→（或 A/D）走，松手回待机，转向水平翻转；按住 Shift 快一点；↓（或 S）转过来正面站着。
##
## 换一套晨的精灵：只改下面「精灵配置」这一段（图、帧尺寸、脚底锚点、美术朝向、每段动画的帧 / 时长 / 步长），
## 别的代码不用动。SpriteFrames 是 _ready 里按配置现搭的，场景里不存帧。
##
## 不打滑：跑 / 走每换一帧身体跳一步（run 的 step），着地的脚在世界里一像素不动。
## step[i] = 第 i 帧换到下一帧时往前走几像素，量法：看两帧里同一只着地的脚，在画布里往后退了几像素。
## 平均速度 = sum(step) / sum(ms)。Shift 把动画放快 FAST 倍，步长不变，所以还是不打滑。
##
## 地面：主层（Main，scroll 1.0）的地面高度 ground_y(x)，和 tools/forest_art.py 里的公式一样（960 宽、左右无缝）。
## x 可以一直往一边涨，取 fposmod。脚底那行压在苔藓最上面一行（和 forest_art.py 里 on_ground 的 sink=1 一样）。
## 晨不放在 Parallax2D 里（repeat 会把她画好几遍），而是直接放在根下、Main 和 Front 之间：
## 主层 scroll 1.0，和世界坐标一致。

# ===================================================================== 精灵配置（换素材只改这里）
## 精灵表：一行横排，所有帧同一尺寸，从左往右编号 0、1、2…
## 现在是奥斯卡画的晨：源文件 art/characters/chen/chen_oscar.aseprite，tools/chen_from_aseprite.py 清杂点、裁好导出，
## 帧号和 aseprite 里一样（爬起来 0~6、待机 7~10、看 11~14、走路 15~25、捡东西 26~30）。
## 旧的那套（美术姐版，tools/chen_sprites.py）还在 art/characters/chen/chen.png、chen_getup.png。
const SHEET := preload("res://art/characters/chen/chen_oscar.png")
const FRAME_SIZE := Vector2i(68, 60)
## 锚点（帧里的像素坐标）：x = 身体中线（翻转就绕这条线翻），y = 脚底那一行
const FOOT := Vector2i(28, 56)
## 美术画的朝向：1 = 朝右，-1 = 朝左
const ART_FACES := 1
## 每段动画：frames = 用精灵表里的哪几帧；ms = 每帧毫秒（一个数 = 每帧一样）；
## step = 会走路的段要：这一帧换到下一帧时往前走几像素（和 frames 一样长）。
## 必须有 run 和 idle；idle_blink / idle_eye（偶尔替换 idle 的一圈，帧数要和 idle 一样）、
## front / front_blink（正面站）可以没有。
## run_start / run_stop 也可以没有：有的话起步先播 run_start 再接 run，松手先播 run_stop 再回 idle（都要 step）。
## pickup（捡东西，第一关捡木头时播）可以没有，没有就退回压扁一下的老办法。
## 可选的几项（不写就用上面的默认）：sheet / size / foot = 这段用另一张精灵表、另一种帧尺寸和锚点；
## loop = false 播一遍停在最后一帧；then = 播完换成哪段。
## lie / getup（第一关开场：脸朝下趴着 → 爬起来）也是可选的，删掉的话关卡退回「把站立帧转 90°」的老办法。
const ANIMS := {
	# 跑：一步 3 帧（着地 → 腾空 → 前脚落地），一圈两步。着地那只脚每帧往后退 6~7 像素 → 约 67 像素 / 秒。
	# 着地帧的脚比站着低 1~2 像素、腾空帧高一点，所以脚底按 57 算（站着是 56）。
	"run": {"frames": [18, 19, 20, 21, 22, 23], "ms": 100, "step": [7, 6, 7, 7, 6, 7], "foot": Vector2i(28, 57)},
	"run_start": {"frames": [15, 16, 17], "ms": 100, "step": [4, 6, 7], "loop": false, "then": "run"},
	"run_stop": {"frames": [24, 25], "ms": 100, "step": [3, 0], "foot": Vector2i(28, 57), "loop": false, "then": "idle"},
	"idle": {"frames": [7, 8, 9, 10], "ms": 100},
	# 「看」：偶尔替换一圈待机，中间那帧停 0.7 秒
	"idle_eye": {"frames": [11, 12, 13, 14], "ms": [100, 100, 700, 100]},
	# 奥斯卡的「爬起来」每帧都是 100ms，开场坠毁以后太快，这里放慢（level_forest.gd 的 GETUP_* 跟着这串数）
	"lie": {"frames": [0], "ms": 400, "loop": false},
	"getup": {"frames": [0, 1, 2, 3, 4, 5, 6], "ms": [350, 250, 300, 450, 300, 200, 200], "loop": false, "then": "idle"},
	# 捡东西：最低那帧（28）在第 0.14 秒，和 level_forest.gd 里木头飞起来的时间对上
	"pickup": {"frames": [26, 27, 28, 29, 30], "ms": [60, 80, 300, 150, 150], "loop": false, "then": "idle"},
}
# =====================================================================

const W := 960.0
const GROUND := 228.0
const SINK := 1                    # 脚底那行盖住地面最上面一行
const FAST := 1.5                  # Shift
const BLINK_EVERY := Vector2(2.5, 5.0)   # 隔几秒眨一次眼
const EYE_CHANCE := 0.25           # 该眨眼时有多大可能换成 idle_eye（奥斯卡版是「看」一眼）

@onready var spr: AnimatedSprite2D = $Sprite

var facing := 1                    # 1 朝右，-1 朝左
var auto_dir := 0.0                # 非 0 时自己走（--walk、空格展示模式）
var input_enabled := true          # false = 不听键盘（过场、打开面板时）；auto_dir 照样能让她走
var _steps := {}                   # 动画名 → 每帧步长
var _last_run_frame := -1          # 上一个显示的 run 帧，换帧时按它的步长前进
var _idle_t := 0.0
var _next_blink := 2.5
var _rng := RandomNumberGenerator.new()
## 地面高度函数（x → 脚底所在行）。默认是针叶林主层的地面；别的场景在 _ready 里换成自己的，
## 例如 chen.ground_fn = func(x: float) -> float: return 230.0
var ground_fn: Callable = ground_y


static func ground_y(x: float) -> float:
	x = fposmod(x, W)
	return GROUND + 2.0 * sin(TAU * x * 2.0 / W) + 1.5 * sin(TAU * x * 5.0 / W + 1.0)


func _ready() -> void:
	spr.sprite_frames = _build_frames()
	spr.centered = false
	position.x = round(position.x)
	spr.frame_changed.connect(_on_frame_changed)
	spr.animation_looped.connect(_on_looped)
	spr.animation_changed.connect(func(): _set_facing(facing))     # 不同段的帧尺寸 / 锚点可以不一样
	spr.animation_finished.connect(_on_finished)
	spr.play(&"idle")
	_set_facing(facing)
	_snap()


func _build_frames() -> SpriteFrames:
	var sf := SpriteFrames.new()
	sf.remove_animation(&"default")
	for name in ANIMS:
		var a: Dictionary = ANIMS[name]
		var frames: Array = a["frames"]
		sf.add_animation(name)
		sf.set_animation_speed(name, 1000.0)       # duration 的单位 = 1ms
		sf.set_animation_loop(name, a.get("loop", true))
		var size: Vector2i = a.get("size", FRAME_SIZE)
		for i in frames.size():
			var t := AtlasTexture.new()
			t.atlas = a.get("sheet", SHEET)
			t.region = Rect2(frames[i] * size.x, 0, size.x, size.y)
			var ms: float = a["ms"][i] if a["ms"] is Array else a["ms"]
			sf.add_frame(name, t, ms)
		if a.has("step"):
			_steps[name] = a["step"]
	return sf


func _process(delta: float) -> void:
	var dir := 0.0
	if input_enabled:
		dir = Input.get_axis("ui_left", "ui_right")
		if Input.is_key_pressed(KEY_A):
			dir -= 1.0
		if Input.is_key_pressed(KEY_D):
			dir += 1.0
	if dir == 0.0:
		dir = auto_dir
	if dir != 0.0:
		_set_facing(1 if dir > 0.0 else -1)
		spr.speed_scale = FAST if input_enabled and Input.is_key_pressed(KEY_SHIFT) else 1.0
		if not _moving(spr.animation) or spr.animation == &"run_stop":
			# 刚停下又按：直接接着跑，不再起步一次
			var again := spr.animation == &"run_stop"
			_last_run_frame = -1
			spr.play(&"run_start" if ANIMS.has("run_start") and not again else &"run")
			_last_run_frame = spr.frame
	else:
		var down := input_enabled and (Input.is_action_pressed("ui_down") or Input.is_key_pressed(KEY_S))
		var want := &"front" if down and ANIMS.has("front") else &"idle"
		var is_front := String(spr.animation).begins_with("front")
		if spr.animation in [&"run", &"run_start"] and want == &"idle" and ANIMS.has("run_stop"):
			_last_run_frame = -1
			spr.play(&"run_stop")
			_last_run_frame = spr.frame
		elif _moving(spr.animation) and spr.animation != &"run_stop" or is_front != (want == &"front"):
			spr.speed_scale = 1.0
			_last_run_frame = -1
			spr.play(want)
	_idle_t += delta


func _set_facing(f: int) -> void:
	facing = f
	spr.flip_h = f != ART_FACES
	# 翻转是在帧的矩形里左右镜像，所以锚点 x 也要跟着镜像，身体中线才不跳
	var a: Dictionary = ANIMS.get(String(spr.animation), {})
	var size: Vector2i = a.get("size", FRAME_SIZE)
	var foot: Vector2i = a.get("foot", FOOT)
	var fx := size.x - foot.x if spr.flip_h else foot.x
	spr.offset = Vector2(-fx, -(foot.y + 1))


func _moving(anim: StringName) -> bool:
	return anim in [&"run", &"run_start", &"run_stop"]


func _on_frame_changed() -> void:
	if not _steps.has(spr.animation):
		return
	if _last_run_frame >= 0 and spr.frame != _last_run_frame:
		position.x += facing * float(_steps[spr.animation][_last_run_frame])
		_snap()
	_last_run_frame = spr.frame


func _on_looped() -> void:
	# 待机：大多数时候是 idle；隔几秒眨一次眼，偶尔头环上的第三只眼也慢慢闭一下。几段呼吸一样，接得上。
	var a := String(spr.animation)
	if _moving(spr.animation):
		return
	var front := a.begins_with("front")
	var base := "front" if front else "idle"
	if a != base:
		spr.play(base)
	elif _idle_t > _next_blink:
		_idle_t = 0.0
		_next_blink = _rng.randf_range(BLINK_EVERY.x, BLINK_EVERY.y)
		var pick := base + "_blink"
		if not front and ANIMS.has("idle_eye") and _rng.randf() < EYE_CHANCE:
			pick = "idle_eye"
		if ANIMS.has(pick):
			spr.play(pick)


func _on_finished() -> void:
	var a: Dictionary = ANIMS.get(String(spr.animation), {})
	if a.has("step") and _last_run_frame >= 0:
		# 不循环的走路段（run_start / run_stop）最后一帧的步长：播完那一下也要走
		position.x += facing * float(a["step"][_last_run_frame])
		_snap()
	_last_run_frame = -1
	if a.has("then"):
		spr.play(StringName(a["then"]))
		if _moving(spr.animation):
			_last_run_frame = spr.frame


func _snap() -> void:
	position.y = round(ground_fn.call(position.x)) + SINK
