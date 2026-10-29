extends Node2D
## 鹿（NPC）：带斑点的小鹿，站在森林里待机。美术给了三张：站着（1 帧）、看（4 帧，转头看镜头、再回头往后看）、
## 吃草（4 帧，慢慢低头到嘴碰地），全部原图 200ms 一帧（tools/deer_from_gif.py 缩回原生像素、对齐脚底、去重）。
## 美术没画的几段是 tools/deer_anims.py 在帧 0 上逐像素改出来的：idle（呼吸 + 尾巴甩，6 帧 200ms 循环）、
## ear（耳朵往后抖两下）、walk（四拍慢走 8 帧 100ms 循环，偶尔换成甩尾巴的 walk_flick 一圈）、run（奔跑 6 帧 100ms 循环）。
## 没有剧本：不说话、不能互动、不挡路。待机就是：idle 呼吸一阵（偶尔抖一下耳朵）→ 随机「看」一圈或者低头「吃草」一阵 →
## 回到 idle。帧一律按画的时长播（只在低着头那张上多停），不用 speed_scale，绝不加速。
## 换段只在 idle 一圈播完（回到静止那帧）的时候换，身体不会跳 1 格。
## 晨走到它另一边去，它在 idle 的时候过一小会儿就转身朝着晨（低着头吃草、跑的时候不转）。
## 跑：run_to(x) 跑到 x 停下回 idle，朝向跟着跑的方向。剧本（story_runner.gd）用它带路；run_to(x, speed) 可以这一次跑慢一点
## （「走慢一点」），动画帧速不变（慢了蹄子会有点滑，只在剧本要求时用）。
## 走：walk_to(x) 用 WALK_SPEED 走过去（蹄子不打滑），停下回 idle，朝向跟着走的方向；walk_to(x, speed) 可以改这一次的速度
## （帧速不变，偏离 WALK_SPEED 蹄子会滑）。
## 预览：forest_test 加 `-- --deer_run=1`（开场 1 秒后往远离晨的方向跑 DEBUG_RUN_DIST 像素再停），
## 或 `--deer_run=-200`（往左跑 200 像素）；走路一样：`--deer_walk=1`（走 DEBUG_WALK_DIST）/ `--deer_walk=-90`。
##
## 节点：根 Node2D 的 x = 四条腿的中线，y 不用管（_ready 里按晨的地面函数贴地：y = 地面那一行 + 1，和晨、蛇女一样）。
## 精灵在 _ready 里现搭，场景里不存帧。场景里放一个 Node2D、挂这个脚本、设 position.x 就行；晨不叫 "../Chen" 的话改 watch_path。
## 光：和蛇女一样用 scripts/chen_light.gdshader + chen.gd 的 ENVS[env]（乘 ENV_K 弱一点），整体乘 TINT 压暗偏冷绿：
## 原图是暖的红棕、奶白斑点和尾巴（L≈0.95，眼睛高光 1.0），压完最亮 ≈0.7，晨的白发还是全屏最亮。
## 脚下一块硬边接触阴影（三行、越往下越窄越淡），跟着朝向翻。

# ===================================================================== 精灵配置（tools/deer_from_gif.py、tools/deer_anims.py 生成）
const SHEET := preload("res://art/characters/deer/deer.png")
const SHEET_IDLE := preload("res://art/characters/deer/deer_idle.png")
const SHEET_RUN := preload("res://art/characters/deer/deer_run.png")
const SHEET_WALK := preload("res://art/characters/deer/deer_walk.png")
const FRAME_SIZE := Vector2i(53, 58)
const FOOT := Vector2i(34, 55)          # x = 四条腿的中线，y = 蹄子着地那一行（远侧两条腿短一格，站在后面）
const ART_FACES := -1                   # 美术朝左
## deer.png 帧：0 站着；1~3 看（正脸、侧面、后脑勺）；4~6 吃草（低头一点、再低、嘴碰地）
## deer_idle.png 帧：0~5 呼吸循环（0、5 = 静止那帧，和 deer.png 帧 0 一样），6 = 耳朵往后歪
## deer_run.png：画布 64×60（右边多给往后蹬的后腿、上面多给跳起来的身体），锚点是同一个点
## deer_walk.png：和 run 同一块画布、同一个锚点；帧 0~7 walk，8~15 同样的步子、尾巴甩一下（walk_flick）
## 每段可以另给 sheet / size / foot（不写就用上面的 SHEET / FRAME_SIZE / FOOT）
const ANIMS := {
	"idle": {"frames": [0, 1, 2, 3, 4, 5], "ms": 200, "sheet": SHEET_IDLE},              # 和美术的 GIF 一样 200ms
	"ear": {"frames": [6, 0, 6], "ms": 200, "loop": false, "sheet": SHEET_IDLE},       # 耳朵抖两下
	"look": {"frames": [1, 2, 3], "ms": 200, "loop": false},          # 看.gif 的 0→1→2→3→0，0 = 站着
	"graze_down": {"frames": [4, 5, 6], "ms": 200, "loop": false},    # 吃草.gif 的 0→1→2→3
	"graze_up": {"frames": [5, 4], "ms": 200, "loop": false},         # 倒着播回去抬头（原图一下跳回站着，太猛）
	"run": {"frames": [0, 1, 2, 3, 4, 5], "ms": 100, "sheet": SHEET_RUN,
			"size": Vector2i(64, 60), "foot": Vector2i(34, 57)},
	"walk": {"frames": [0, 1, 2, 3, 4, 5, 6, 7], "ms": 100, "sheet": SHEET_WALK,
			"size": Vector2i(64, 60), "foot": Vector2i(34, 57)},
	"walk_flick": {"frames": [8, 9, 10, 11, 12, 13, 14, 15], "ms": 100, "sheet": SHEET_WALK,
			"size": Vector2i(64, 60), "foot": Vector2i(34, 57)},
}
# =====================================================================

@export var watch_path := NodePath("../Chen")   # 朝着谁（晨）
@export var env := "forest"                     # 用 chen.gd 的 ENVS 里哪一套光

const TINT := Color(0.66, 0.74, 0.7)     # 整体压暗、偏冷绿：红棕身子和晨的斗篷同色系、面积还大，压到比斗篷暗一档；奶白斑点 L≈0.95 → ≈0.7
const ENV_K := 0.8                      # 场景偏色 / 受光边比晨弱多少（1 = 和晨一样）
const SINK := 1                         # 脚底那行盖住地面最上面一行（和晨一样）
const TURN_GAP := 10.0                  # 晨离它中线超过这么多像素才算「在另一边」
const TURN_DELAY := 0.4                 # 晨走过去以后过多久转身
const STAND_HOLD := Vector2(2.5, 6.0)   # 每次 idle 呼吸多久再去看 / 吃草（随机；到点后等这一圈播完才换）
const EAR_CHANCE := 0.12                # idle 每播完一圈，有这么大可能插一段抖耳朵
## 跑的速度（像素 / 秒）。只能改这个，动画永远 100ms 一帧。tools/deer_anims.py 里着地的蹄子一帧往后扫 SWEEP=9 格，
## 90 = 蹄子不打滑；调快了蹄子会往前滑（跑得快的鹿就得重画步子更大的腿）。
const RUN_SPEED := 90.0
const DEBUG_RUN_DIST := 160.0           # --deer_run=1 跑多远
## 走的速度（像素 / 秒）：30 = 蹄子不打滑。tools/deer_anims.py 里着地的蹄子一帧往后挪 WALK_STEP=3 格，帧 100ms →
## 3 × 10 = 30。动画永远 100ms 一帧；要走得快就得重画步子更大的腿（改 WALK_STEP），再把这里改成 WALK_STEP × 10。
const WALK_SPEED := 30.0
const WALK_FLICK_CHANCE := 0.25         # 走路每走完一圈，有这么大可能下一圈换成甩尾巴的那圈
const DEBUG_WALK_DIST := 90.0           # --deer_walk=1 走多远（3 秒）
const DEBUG_RUN_DELAY := 1.0            # 开场多久开始跑
const GRAZE_HOLD := Vector2(2.5, 5.0)   # 低头吃草停几秒
const GRAZE_CHANCE := 0.4               # 站够了以后去吃草的可能（否则「看」一圈）
## 接触阴影：每行 [左, 右)（像素，相对腿中线、美术朝左），从脚底那行往下三行
const SHADOW_ROWS := [[-17, 18], [-15, 16], [-11, 12]]
const SHADOW_A := [0.36, 0.26, 0.15]

const CHEN_GD := preload("res://scripts/chen.gd")
const LIGHT_SHADER := preload("res://scripts/chen_light.gdshader")

var spr: AnimatedSprite2D
var facing := ART_FACES
var _watch: Node2D
var _mat: ShaderMaterial
var _shadow: Node2D
var _turn_t := 0.0
var _hold := 0.0                        # idle / 低着头还要停几秒（0 = 不在等）
var _next := &""                        # idle 这一圈播完以后换成哪段（&"" = 接着 idle）
var _rng := RandomNumberGenerator.new()
var _running := false
var _run_x := 0.0                       # 跑向哪
var _run_v := RUN_SPEED                 # 这一次跑多快（run_to 的 speed）
var _x := 0.0                           # 跑的时候的小数位置
var _walking := false                   # 走路也用 _run_x / _run_v / _x 这一套挪位置
var _debug_run := 0.0                   # --deer_run：0 = 不跑；1 = 往远离晨的方向跑 DEBUG_RUN_DIST；别的数 = 往右跑这么多像素（负 = 往左）
var _debug_walk := 0.0                  # --deer_walk：同上，走路
var _debug_t := 0.0


func _ready() -> void:
	position.x = round(position.x)
	_rng.randomize()
	_watch = get_node_or_null(watch_path) as Node2D
	# 阴影在精灵后面
	_shadow = Node2D.new()
	_shadow.name = "Shadow"
	_shadow.draw.connect(_draw_shadow)
	add_child(_shadow)
	spr = AnimatedSprite2D.new()
	spr.name = "Sprite"
	spr.centered = false
	spr.sprite_frames = _build_frames()
	spr.modulate = TINT
	add_child(spr)
	_mat = ShaderMaterial.new()
	_mat.shader = LIGHT_SHADER
	spr.material = _mat
	spr.animation_finished.connect(_on_finished)
	spr.animation_looped.connect(_on_looped)
	spr.animation_changed.connect(func(): _set_facing(facing))     # 不同段的画布 / 锚点不一样
	_apply_env()
	_idle(_rng.randf_range(0.8, STAND_HOLD.y))     # 第一次的时间短一点、随机，别和蛇女同一拍
	_snap()
	_set_facing(_want() if _watch != null else facing)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--deer_run="):
			_debug_run = float(a.trim_prefix("--deer_run="))
		elif a.begins_with("--deer_walk="):
			_debug_walk = float(a.trim_prefix("--deer_walk="))


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
			t.region = Rect2(int(frames[i]) * size.x, 0, size.x, size.y)
			var ms: float = a["ms"][i] if a["ms"] is Array else a["ms"]
			sf.add_frame(name, t, ms)
	return sf


func _apply_env() -> void:
	var cfg: Dictionary = CHEN_GD.ENVS.get(env, {})
	_mat.set_shader_parameter("tint", cfg.get("tint", Color(0.5, 0.5, 0.5)))
	_mat.set_shader_parameter("tint_amt", float(cfg.get("tint_amt", 0.0)) * ENV_K)
	_mat.set_shader_parameter("rim_color", cfg.get("rim", Color.WHITE))
	_mat.set_shader_parameter("rim_amt", float(cfg.get("rim_amt", 0.0)) * ENV_K)
	_mat.set_shader_parameter("rim_back", float(cfg.get("back", 0.0)) * ENV_K)
	_mat.set_shader_parameter("boost", 0.0)          # 不站在光柱里


## 贴地：用晨的地面函数（森林主层的地面），位置取整
func _snap() -> void:
	if _watch != null and "ground_fn" in _watch:
		var g: Callable = _watch.get("ground_fn")
		position.y = round(float(g.call(position.x))) + SINK
	position = position.round()


func _set_facing(f: int) -> void:
	facing = f
	spr.flip_h = f != ART_FACES
	# 翻转是在帧的矩形里左右镜像，锚点 x 跟着镜像，腿中线不跳；offset 都是整数，翻完还是对齐像素
	var a: Dictionary = ANIMS.get(String(spr.animation), {})
	var size: Vector2i = a.get("size", FRAME_SIZE)
	var foot: Vector2i = a.get("foot", FOOT)
	var fx := size.x - foot.x if spr.flip_h else foot.x
	spr.offset = Vector2(-fx, -(foot.y + 1))
	var d := Vector2(CHEN_GD.ENVS.get(env, {}).get("dir", Vector2(0, -1)))
	if spr.flip_h:
		d.x = -d.x
	_mat.set_shader_parameter("rim_dir", d.normalized())
	_shadow.queue_redraw()


func _want() -> int:
	return 1 if _watch.position.x > position.x else -1


# ----------------------------------------------------------------------- 待机：idle → 看 / 吃草 → idle
func _idle(hold: float) -> void:
	spr.play(&"idle")
	_hold = hold
	_next = &""


func _on_looped() -> void:
	# 走路每走完一圈，偶尔换成甩尾巴的那圈（两段步子一模一样，从第 0 帧接上）
	if _walking and (spr.animation == &"walk" or spr.animation == &"walk_flick"):
		var w := &"walk_flick" if _rng.randf() < WALK_FLICK_CHANCE else &"walk"
		if w != spr.animation:
			spr.play(w)
		return
	# idle 刚播完一圈（下一帧又是静止那帧）：这时候换段，身体不跳
	if spr.animation != &"idle" or _running or _walking:
		return
	if _next != &"":
		var n := _next
		_next = &""
		spr.play(n)
	elif _rng.randf() < EAR_CHANCE:
		spr.play(&"ear")


func _on_finished() -> void:
	match spr.animation:
		&"look", &"graze_up":
			_idle(_rng.randf_range(STAND_HOLD.x, STAND_HOLD.y))
		&"ear":
			spr.play(&"idle")                                        # 接着呼吸，_hold 照常倒数
		&"graze_down":
			_hold = _rng.randf_range(GRAZE_HOLD.x, GRAZE_HOLD.y)     # 停在嘴碰地那帧


## 跑到 x（世界坐标）停下，回 idle。朝向跟着跑的方向；跑的时候不看晨。正在看 / 吃草也直接起跑。
func run_to(x: float, speed := RUN_SPEED) -> void:
	x = round(x)
	if absf(x - position.x) < 1.0:
		return
	_run_v = speed
	_running = true
	_walking = false
	_run_x = x
	_x = position.x
	_hold = 0.0
	_next = &""
	_set_facing(1 if x > position.x else -1)
	spr.play(&"run")


func is_running() -> bool:
	return _running


## 走到 x（世界坐标）停下，回 idle。speed 不给就是 WALK_SPEED（蹄子不打滑）；朝向跟着走的方向，走的时候不看晨。
func walk_to(x: float, speed := WALK_SPEED) -> void:
	x = round(x)
	if absf(x - position.x) < 1.0:
		return
	_run_v = speed
	_walking = true
	_running = false
	_run_x = x
	_x = position.x
	_hold = 0.0
	_next = &""
	_set_facing(1 if x > position.x else -1)
	if spr.animation != &"walk" and spr.animation != &"walk_flick":
		spr.play(&"walk")


func is_walking() -> bool:
	return _walking


func _process(delta: float) -> void:
	if _debug_run != 0.0:
		_debug_t += delta
		if _debug_t >= DEBUG_RUN_DELAY:
			var away := -_want() if _watch != null else 1
			var dist := DEBUG_RUN_DIST * away if is_equal_approx(_debug_run, 1.0) else _debug_run
			_debug_run = 0.0
			run_to(position.x + dist)
	if _debug_walk != 0.0:
		_debug_t += delta
		if _debug_t >= DEBUG_RUN_DELAY:
			var away_w := -_want() if _watch != null else 1
			var dist_w := DEBUG_WALK_DIST * away_w if is_equal_approx(_debug_walk, 1.0) else _debug_walk
			_debug_walk = 0.0
			walk_to(position.x + dist_w)
	if _running or _walking:
		var step := _run_v * delta
		var arrived := false
		if absf(_run_x - _x) <= step:
			_x = _run_x
			arrived = true
		else:
			_x += signf(_run_x - _x) * step
		position.x = round(_x)
		_snap()
		if arrived:
			_running = false
			_walking = false
			_idle(_rng.randf_range(STAND_HOLD.x, STAND_HOLD.y))
		return
	if _hold > 0.0:
		_hold -= delta
		if _hold <= 0.0:
			_hold = 0.0
			if spr.animation == &"idle" or spr.animation == &"ear":
				_next = &"graze_down" if _rng.randf() < GRAZE_CHANCE else &"look"
			elif spr.animation == &"graze_down":
				spr.play(&"graze_up")
	# 只在 idle 的时候转身
	if _watch == null or not _watch.visible or not (spr.animation == &"idle" or spr.animation == &"ear"):
		_turn_t = 0.0
		return
	if _want() != facing and absf(_watch.position.x - position.x) > TURN_GAP:
		_turn_t += delta
		if _turn_t >= TURN_DELAY:
			_turn_t = 0.0
			_set_facing(_want())
	else:
		_turn_t = 0.0


func _draw_shadow() -> void:
	# 三行硬边：脚底那行（被蹄子盖住，只露出腿缝和两边）和往下两行，压暗地面一档
	for i in SHADOW_ROWS.size():
		var l: int = SHADOW_ROWS[i][0]
		var r: int = SHADOW_ROWS[i][1]
		if facing != ART_FACES:
			var t := l
			l = -r
			r = -t
		_shadow.draw_rect(Rect2(l, i - 1, r - l, 1), Color(0, 0, 0, SHADOW_A[i]))
