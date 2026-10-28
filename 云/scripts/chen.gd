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
## 精灵表：一行横排，所有帧同一尺寸，从左往右编号 0、1、2…（tools/chen_sprites.py 生成）
const SHEET := preload("res://art/characters/chen/chen.png")
const FRAME_SIZE := Vector2i(40, 42)
## 锚点（帧里的像素坐标）：x = 身体中线（翻转就绕这条线翻，最好取画布正中），y = 脚底那一行
const FOOT := Vector2i(20, 41)
## 美术画的朝向：1 = 朝右，-1 = 朝左
const ART_FACES := 1
## 每段动画：frames = 用精灵表里的哪几帧；ms = 每帧毫秒（一个数 = 每帧一样）；
## step = 只有 run 要：这一帧换到下一帧时往前走几像素（和 frames 一样长）。
## 必须有 run 和 idle；idle_blink / idle_eye（偶尔替换 idle 的一圈，帧数要和 idle 一样）、
## front / front_blink（正面站）可以没有。
const ANIMS := {
	"run": {"frames": [0, 1, 2], "ms": [175, 100, 100], "step": [7, 4, 4]},
	"idle": {"frames": [3, 4, 5, 6, 7, 8, 9, 10], "ms": 150},
	"idle_blink": {"frames": [11, 12, 13, 14, 15, 16, 17, 18], "ms": 150},
	"idle_eye": {"frames": [19, 20, 21, 22, 23, 24, 25, 26], "ms": 150},
	"front": {"frames": [27, 28, 29, 30, 31, 32], "ms": 150},
	"front_blink": {"frames": [33, 34, 35, 36, 37, 38], "ms": 150},
}
# =====================================================================

const W := 960.0
const GROUND := 228.0
const SINK := 1                    # 脚底那行盖住地面最上面一行
const FAST := 1.5                  # Shift
const BLINK_EVERY := Vector2(2.5, 5.0)   # 隔几秒眨一次眼
const EYE_CHANCE := 0.25           # 眨眼时有多大可能换成第三只眼

@onready var spr: AnimatedSprite2D = $Sprite

var facing := 1                    # 1 朝右，-1 朝左
var auto_dir := 0.0                # 非 0 时自己走（--walk、空格展示模式）
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
		sf.set_animation_loop(name, true)
		for i in frames.size():
			var t := AtlasTexture.new()
			t.atlas = SHEET
			t.region = Rect2(frames[i] * FRAME_SIZE.x, 0, FRAME_SIZE.x, FRAME_SIZE.y)
			var ms: float = a["ms"][i] if a["ms"] is Array else a["ms"]
			sf.add_frame(name, t, ms)
		if a.has("step"):
			_steps[name] = a["step"]
	return sf


func _process(delta: float) -> void:
	var dir := Input.get_axis("ui_left", "ui_right")
	if Input.is_key_pressed(KEY_A):
		dir -= 1.0
	if Input.is_key_pressed(KEY_D):
		dir += 1.0
	if dir == 0.0:
		dir = auto_dir
	if dir != 0.0:
		_set_facing(1 if dir > 0.0 else -1)
		spr.speed_scale = FAST if Input.is_key_pressed(KEY_SHIFT) else 1.0
		if spr.animation != &"run":
			_last_run_frame = -1
			spr.play(&"run")
			_last_run_frame = spr.frame
	else:
		var down := Input.is_action_pressed("ui_down") or Input.is_key_pressed(KEY_S)
		var want := &"front" if down and ANIMS.has("front") else &"idle"
		var is_front := String(spr.animation).begins_with("front")
		if spr.animation == &"run" or is_front != (want == &"front"):
			spr.speed_scale = 1.0
			_last_run_frame = -1
			spr.play(want)
	_idle_t += delta


func _set_facing(f: int) -> void:
	facing = f
	spr.flip_h = f != ART_FACES
	# 翻转是在帧的矩形里左右镜像，所以锚点 x 也要跟着镜像，身体中线才不跳
	var fx := FRAME_SIZE.x - FOOT.x if spr.flip_h else FOOT.x
	spr.offset = Vector2(-fx, -(FOOT.y + 1))


func _on_frame_changed() -> void:
	if spr.animation != &"run":
		return
	if _last_run_frame >= 0 and spr.frame != _last_run_frame:
		position.x += facing * float(_steps[&"run"][_last_run_frame])
		_snap()
	_last_run_frame = spr.frame


func _on_looped() -> void:
	# 待机：大多数时候是 idle；隔几秒眨一次眼，偶尔头环上的第三只眼也慢慢闭一下。几段呼吸一样，接得上。
	var a := String(spr.animation)
	if a == "run":
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


func _snap() -> void:
	position.y = round(ground_fn.call(position.x)) + SINK
