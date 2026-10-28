extends Node2D
## 主角「晨」：←/→（或 A/D）走，松手回待机，转向水平翻转；按住 Shift 快一点；↓（或 S）转过来正面站着。
##
## 换一套晨的精灵：只改下面「精灵配置」这一段（图、帧尺寸、脚底锚点、美术朝向、每段动画的帧 / 时长 / 步长），
## 别的代码不用动。SpriteFrames 是 _ready 里按配置现搭的，场景里不存帧。
##
## 走路的速度和动画分开：动画一律按奥斯卡给的 10 帧 / 秒（100ms 一帧）播，移动是一个有惯性的速度 _vel，
## 每帧平滑地走（不是每换一张图跳一步）。按下方向键：先播「前摇」run_start（3 帧），这 0.3 秒里速度从 0 加到 RUN_SPEED；
## 接着循环 run（「走路：真」那 6 帧）；松手：播「后摇」run_stop（2 帧），这 0.2 秒里速度减到 0。
## 有了这点惯性，镜头和整片视差背景也跟着慢慢起、慢慢停，不会一下动一下停。
## step 不用了（以前每换一帧跳 step 像素，一秒只动 10 下，看起来一顿一顿）。
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
## 必须有 run 和 idle；idle_blink / idle_eye（偶尔替换 idle 的一圈，帧数要和 idle 一样）、
## front / front_blink（正面站）可以没有。
## run_start / run_stop 也可以没有：有的话起步先播 run_start 再接 run，松手先播 run_stop 再回 idle。
## pickup（捡东西，第一关捡木头时播）可以没有，没有就退回压扁一下的老办法。
## 可选的几项（不写就用上面的默认）：sheet / size / foot = 这段用另一张精灵表、另一种帧尺寸和锚点；
## loop = false 播一遍停在最后一帧；then = 播完换成哪段。
## lie / getup（第一关开场：脸朝下趴着 → 爬起来）也是可选的，删掉的话关卡退回「把站立帧转 90°」的老办法。
const ANIMS := {
	# 全部按奥斯卡在 aseprite 里给的时长：每帧 100ms（10 帧 / 秒），只有「看」中间那帧他设了 700ms。
	# 走路（aseprite 的「走路」15~25）= 前摇 15~17 + 循环（「走路：真」18~23）+ 后摇 24~25。
	# 着地帧的脚比站着低 1~2 像素、腾空帧高一点，所以跑的脚底按 57 算（站着是 56）。
	"run": {"frames": [18, 19, 20, 21, 22, 23], "ms": 100, "foot": Vector2i(28, 57)},
	"run_start": {"frames": [15, 16, 17], "ms": 100, "loop": false, "then": "run"},
	"run_stop": {"frames": [24, 25], "ms": 100, "foot": Vector2i(28, 57), "loop": false, "then": "idle"},
	"idle": {"frames": [7, 8, 9, 10], "ms": 100},
	"idle_eye": {"frames": [11, 12, 13, 14], "ms": [100, 100, 700, 100]},       # 「看」：偶尔替换一圈待机
	"lie": {"frames": [0], "ms": 100, "loop": false},
	"getup": {"frames": [0, 1, 2, 3, 4, 5, 6], "ms": 100, "loop": false, "then": "idle"},   # level_forest.gd 的 GETUP_* 跟着它
	"pickup": {"frames": [26, 27, 28, 29, 30], "ms": 100, "loop": false, "then": "idle"},    # 最低那帧（28）在第 0.2 秒
}
# =====================================================================

const W := 960.0
const GROUND := 228.0
const SINK := 1                    # 脚底那行盖住地面最上面一行
const FAST := 1.5                  # Shift
const RUN_SPEED := 110.0           # 跑的速度（像素 / 秒）：动画不变，只改这个
const ACCEL_TIME := 0.3            # 从 0 加到 RUN_SPEED 用多久（= 前摇 run_start 3 帧）
const DECEL_TIME := 0.2            # 从 RUN_SPEED 减到 0 用多久（= 后摇 run_stop 2 帧）
const BLINK_EVERY := Vector2(2.5, 5.0)   # 隔几秒眨一次眼
const EYE_CHANCE := 0.25           # 该眨眼时有多大可能换成 idle_eye（奥斯卡版是「看」一眼）

@onready var spr: AnimatedSprite2D = $Sprite

var facing := 1                    # 1 朝右，-1 朝左
var auto_dir := 0.0                # 非 0 时自己走（--walk、空格展示模式）
var input_enabled := true          # false = 不听键盘（过场、打开面板时）；auto_dir 照样能让她走
var _idle_t := 0.0
var _next_blink := 2.5
var _rng := RandomNumberGenerator.new()
var _x := NAN                      # 小数位置（position.x 是取整后的，免得画在两个像素之间）
var _vel := 0.0                    # 现在的速度（像素 / 秒，沿 facing）
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
	spr.animation_looped.connect(_on_looped)
	spr.animation_changed.connect(func(): _set_facing(facing))     # 不同段的帧尺寸 / 锚点可以不一样
	spr.animation_finished.connect(_on_finished)
	spr.play(&"idle")
	_set_facing(facing)
	_snap()
	_env_ready()


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
	var target := 0.0                  # 想要的速度
	if dir != 0.0:
		var f := 1 if dir > 0.0 else -1
		if f != facing and _vel > 0.0:
			# 跑着掉头：速度清零，重新起步
			_vel = 0.0
			_set_facing(f)
			spr.play(&"run_start" if ANIMS.has("run_start") else &"run")
		_set_facing(f)
		spr.speed_scale = FAST if input_enabled and Input.is_key_pressed(KEY_SHIFT) else 1.0
		if not _moving(spr.animation) or spr.animation == &"run_stop":
			# 刚停下又按：直接接着跑（速度从还没减完的地方加回去），不再起步一次
			var again := spr.animation == &"run_stop"
			spr.play(&"run_start" if ANIMS.has("run_start") and not again else &"run")
		target = RUN_SPEED * spr.speed_scale
	else:
		var down := input_enabled and (Input.is_action_pressed("ui_down") or Input.is_key_pressed(KEY_S))
		var want := &"front" if down and ANIMS.has("front") else &"idle"
		var is_front := String(spr.animation).begins_with("front")
		if spr.animation in [&"run", &"run_start"] and want == &"idle" and ANIMS.has("run_stop"):
			spr.speed_scale = 1.0
			spr.play(&"run_stop")
		elif _moving(spr.animation) and spr.animation != &"run_stop" or is_front != (want == &"front"):
			spr.speed_scale = 1.0
			spr.play(want)
	# 惯性：加速用 ACCEL_TIME（前摇那 3 帧），减速用 DECEL_TIME（后摇那 2 帧）
	var rate := RUN_SPEED / (ACCEL_TIME if target > _vel else DECEL_TIME)
	_vel = move_toward(_vel, target, rate * delta)
	if _vel > 0.0:
		# 别人（过场、调试参数）直接挪过她，就从那里接着走
		if is_nan(_x) or absf(position.x - roundf(_x)) > 0.5:
			_x = position.x
		_x += facing * _vel * delta
		position.x = roundf(_x)
		_snap()
	else:
		_x = NAN
	_idle_t += delta


## 现在松手的话还会往前滑多远（像素）：过场「走到某处停下」时提前这么多松手，就正好停在那里
func stop_distance() -> float:
	return _vel * _vel / (2.0 * RUN_SPEED / DECEL_TIME)


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
	if a.has("then"):
		spr.play(StringName(a["then"]))


func _snap() -> void:
	position.y = round(ground_fn.call(position.x)) + SINK


# ===================================================================== 环境对晨的反应（场景的光、脚下、头发光晕）
## 各场景在 _ready 里调一次：chen.set_env("forest", 光函数)。光函数 func(chen) -> float，0 = 不在光里，1 = 正站在最亮的光里；
## 没有光柱的场景不给（河岸、云星）。下面这些都只是「环境对晨的反应」，不改移动和动画。
##   1. 精灵上的 scripts/chen_light.gdshader：斗篷暗部偏一点场景色（tint / tint_amt），朝光那一侧一道细受光边（rim / rim_amt / dir），
##      dir 是屏幕方向（x 右、y 下，指向光源）；back > 0 = 背光，左右两侧的边也亮一点。走进光里 boost 平滑升到 1：边和斗篷亮一点。
##   2. 脚下：接触阴影 + 跑步着地帧踩出一点场景反应（scripts/chen_fx.gd，fx = 哪一套）。
##   3. 头发后面一圈极淡的光晕（halo 颜色，HALO_A 透明度），跟着每帧头的位置（data/chen_heads.json，
##      tools/chen_from_aseprite.py 导出时顺手算的：白发那团的重心）。
## 调强弱：整体改 ENVS 里各场景的 tint_amt / rim_amt / back；走进光里亮多少改 scripts/chen_light.gdshader 的 boost_*（或下面 BOOST_*）；
## 光晕改 HALO_A；脚下特效的颜色、数量在 scripts/chen_fx.gd 开头。
const LIGHT_SHADER := preload("res://scripts/chen_light.gdshader")
const CHEN_FX := preload("res://scripts/chen_fx.gd")
const HEADS_JSON := "res://data/chen_heads.json"
const ENVS := {
	# 森林：背后的雾光，青绿；斗篷偏墨绿
	"forest": {"tint": Color(0.42, 0.62, 0.55), "tint_amt": 0.35, "rim": Color(0.42, 0.7, 0.58), "rim_amt": 0.3,
		"dir": Vector2(0.0, -1.0), "back": 0.45, "halo": Color(0.6, 0.92, 0.78), "fx": "forest"},
	# 河岸：月光从右上，冷蓝
	"river": {"tint": Color(0.45, 0.55, 0.8), "tint_amt": 0.5, "rim": Color(0.55, 0.68, 0.95), "rim_amt": 0.34,
		"dir": Vector2(0.7, -0.7), "back": 0.0, "halo": Color(0.66, 0.76, 1.0), "fx": "river"},
	# 水底：头顶的月光，冷蓝
	"underwater": {"tint": Color(0.36, 0.55, 0.72), "tint_amt": 0.55, "rim": Color(0.5, 0.72, 0.88), "rim_amt": 0.34,
		"dir": Vector2(0.0, -1.0), "back": 0.0, "halo": Color(0.6, 0.82, 0.96), "fx": "underwater"},
	# 云星：地平线左边的余晖，暖橙；斗篷偏紫
	"cloud": {"tint": Color(0.56, 0.45, 0.74), "tint_amt": 0.5, "rim": Color(1.0, 0.64, 0.4), "rim_amt": 0.3,
		"dir": Vector2(-1.0, -0.2), "back": 0.0, "halo": Color(0.88, 0.72, 0.96), "fx": "cloud"},
	# 城市：楼缝漏下来的霾光，冷白，从上偏右；斗篷偏冷灰
	"city": {"tint": Color(0.5, 0.55, 0.62), "tint_amt": 0.4, "rim": Color(0.78, 0.8, 0.85), "rim_amt": 0.3,
		"dir": Vector2(0.35, -1.0), "back": 0.0, "halo": Color(0.86, 0.89, 0.96), "fx": "city"},
}
const LIGHT_IN := 7.0              # 走进光里变亮的快慢（越大越快；1/秒）
const LIGHT_OUT := 2.5             # 走出去暗回来的快慢
const HALO_A := 0.14               # 头发光晕的不透明度（加法混合）：要淡到第二眼才注意到
const HALO_R := 12                 # 光晕半径（像素）
## 跑步时脚着地的帧（图集帧号，看 art/characters/chen/chen_oscar.png：这两帧后脚踩到最低那行 58）和那只脚在帧里的 x
const STEP_FRAMES := [18, 21]
const STEP_FOOT_X := 26
const START_FRAME := 16            # 起步：蹬地那帧蹭一下
const STOP_FRAME := 24             # 停下：刹住那帧蹭一下
const AIR_FRAMES := [19, 22]       # 腾空帧：接触阴影窄一点
const SHOULDER := Vector2(-6, 8)   # 城市：雨打在肩上的位置，相对头中心（美术朝右）
const SHOULDER_EVERY := Vector2(0.6, 1.8)

var env := ""                      # 现在的场景预设名（"" = 没有）
var light_fn: Callable             # 场景给的「这里有多亮」，func(chen) -> float 0..1
var step_bubbles: Node             # 水底：踩一步顺便吐几颗泡（underwater_bubbles.gd 的节点，有 emit()）
var light := 0.0                   # 平滑过的「在光里」程度 0..1
var _env_cfg := {}
var _mat: ShaderMaterial
var _halo: Sprite2D
var _fx_back: Node2D
var _fx_front: Node2D
var _heads: Array = []
var _steps_n := 0
var _rain_t := 1.0
var _last_fx_key := ""


func set_env(name: String, fn: Callable = Callable()) -> void:
	env = name
	light_fn = fn
	_env_cfg = ENVS.get(name, {})
	if _mat == null:
		return
	var on := not _env_cfg.is_empty()
	_mat.set_shader_parameter("tint", _env_cfg.get("tint", Color(0.5, 0.5, 0.5)))
	_mat.set_shader_parameter("tint_amt", _env_cfg.get("tint_amt", 0.0))
	_mat.set_shader_parameter("rim_color", _env_cfg.get("rim", Color.WHITE))
	_mat.set_shader_parameter("rim_amt", _env_cfg.get("rim_amt", 0.0))
	_mat.set_shader_parameter("rim_back", _env_cfg.get("back", 0.0))
	_halo.visible = on
	var h: Color = _env_cfg.get("halo", Color.WHITE)
	_halo.modulate = Color(h.r, h.g, h.b, HALO_A)


func _env_ready() -> void:
	_mat = ShaderMaterial.new()
	_mat.shader = LIGHT_SHADER
	spr.material = _mat
	# 光晕在精灵后面（第一个子节点），加法混合
	_halo = Sprite2D.new()
	_halo.name = "Halo"
	_halo.texture = _halo_texture()
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	_halo.material = add
	_halo.visible = false
	add_child(_halo)
	move_child(_halo, 0)
	# 脚下：阴影 / 涟漪在精灵后面，粒子在前面。它们是 top_level（世界坐标），粒子落下就留在原地
	_fx_back = CHEN_FX.new()
	_fx_back.name = "FxBack"
	_fx_back.chen = self
	_fx_back.back = true
	add_child(_fx_back)
	move_child(_fx_back, 0)
	_fx_front = CHEN_FX.new()
	_fx_front.name = "FxFront"
	_fx_front.chen = self
	_fx_front.under = _fx_back
	add_child(_fx_front)
	# 每帧更新放在 FxFront 的 _process 里（子节点在晨自己的 _process 之后跑，拿到的是这一帧的动画帧和朝向）
	_fx_front.tick = _env_update
	spr.frame_changed.connect(_on_frame_env)
	spr.animation_changed.connect(_on_frame_env)
	if FileAccess.file_exists(HEADS_JSON):
		var j = JSON.parse_string(FileAccess.get_file_as_string(HEADS_JSON))
		if j is Dictionary:
			_heads = j.get("heads", [])
	set_env(env, light_fn)


func _halo_texture() -> ImageTexture:
	# 像萤火虫（art/fx/firefly.png）那样分档的光晕：中心最亮，往外几档硬边地淡下去
	var n := HALO_R * 2 + 1
	var img := Image.create_empty(n, n, false, Image.FORMAT_RGBA8)
	for y in n:
		for x in n:
			var d := Vector2(x - HALO_R, y - HALO_R).length() / (HALO_R + 0.5)
			var a := clampf(1.0 - d, 0.0, 1.0)
			a = floor(a * 5.0 + 0.5) / 5.0
			img.set_pixel(x, y, Color(1, 1, 1, a))
	return ImageTexture.create_from_image(img)


func _atlas_frame() -> int:
	var t := spr.sprite_frames.get_frame_texture(spr.animation, spr.frame) as AtlasTexture
	if t == null:
		return -1
	return int(t.region.position.x / t.region.size.x)


## 帧里的像素坐标（美术朝右）→ 晨的本地坐标（跟着翻转、精灵的位移 / 旋转 / 缩放）
func _frame_to_local(p: Vector2) -> Vector2:
	var a: Dictionary = ANIMS.get(String(spr.animation), {})
	var size: Vector2i = a.get("size", FRAME_SIZE)
	var q := Vector2(size.x - p.x if spr.flip_h else p.x, p.y) + spr.offset
	return spr.transform * q


func _head_px() -> Vector2:
	var i := _atlas_frame()
	if i >= 0 and i < _heads.size() and _heads[i] != null:
		return Vector2(_heads[i][0] + 0.5, _heads[i][1] + 0.5)
	return Vector2(32.3, 13.0)


func _upright() -> bool:
	return visible and absf(spr.rotation) < 0.01 and spr.position == Vector2.ZERO


func _on_frame_env() -> void:
	var kind: String = _env_cfg.get("fx", "")
	if kind == "" or not _upright():
		return
	var i := _atlas_frame()
	# 换段的那一下 animation_changed 和 frame_changed 会各来一次：同一段的同一帧只算一次
	var key := "%s:%d" % [spr.animation, spr.frame]
	if key == _last_fx_key:
		return
	_last_fx_key = key
	var a: Dictionary = ANIMS.get(String(spr.animation), {})
	var foot: Vector2i = a.get("foot", FOOT)
	var p := position + Vector2((STEP_FOOT_X - foot.x) * facing, 0)
	if spr.animation == &"run" and i in STEP_FRAMES:
		_fx_front.step(p, facing, kind)
		_steps_n += 1
		if step_bubbles != null and _steps_n % 2 == 0 and step_bubbles.has_method("emit"):
			step_bubbles.emit(p + Vector2(0, -3), 1 + _steps_n % 3)
	elif spr.animation == &"run_start" and i == START_FRAME:
		_fx_front.scuff(p, facing, kind)
	elif spr.animation == &"run_stop" and i == STOP_FRAME:
		_fx_front.scuff(p, facing, kind)


func _env_update(delta: float) -> void:
	if _mat == null:
		return
	# 光：场景说这里有多亮，平滑地跟过去（进来快一点，出去慢一点）
	var target := 0.0
	if light_fn.is_valid():
		target = clampf(float(light_fn.call(self)), 0.0, 1.0)
	light += (target - light) * (1.0 - exp(-(LIGHT_IN if target > light else LIGHT_OUT) * delta))
	_mat.set_shader_parameter("boost", light)
	# 受光边的方向：屏幕方向 → 纹理里的方向（先抵掉旋转，再抵掉翻转），这样翻身、被甩出去转着的时候光还是从同一边来
	var d: Vector2 = _env_cfg.get("dir", Vector2(0, -1))
	d = d.normalized().rotated(-spr.global_rotation)
	if spr.flip_h:
		d.x = -d.x
	_mat.set_shader_parameter("rim_dir", d)
	# 光晕跟着头
	if _halo.visible:
		_halo.position = _frame_to_local(_head_px()).round()
	# 接触阴影
	var up := _upright() and not (spr.animation in [&"lie", &"getup"])
	_fx_back.shadow_on = up and not _env_cfg.is_empty()
	var i := _atlas_frame()
	var running := spr.animation in [&"run", &"run_start", &"run_stop"]
	_fx_back.shadow_w = 7 if i in AIR_FRAMES else 9
	_fx_back.shadow_x = -3.0 * facing if running else 0.0
	# 城市：雨偶尔打在肩上
	if _env_cfg.get("fx", "") == "city" and up:
		_rain_t -= delta
		if _rain_t <= 0.0:
			_rain_t = _rng.randf_range(SHOULDER_EVERY.x, SHOULDER_EVERY.y)
			_fx_front.shoulder((position + _frame_to_local(_head_px() + SHOULDER)).round())
