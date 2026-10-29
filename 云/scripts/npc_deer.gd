extends Node2D
## 鹿（NPC）：带斑点的小鹿，站在森林里待机。美术给了三张：站着（1 帧）、看（4 帧，转头看镜头、再回头往后看）、
## 吃草（4 帧，慢慢低头到嘴碰地），全部原图 200ms 一帧（tools/deer_from_gif.py 缩回原生像素、对齐脚底、去重）。
## 没有剧本：不说话、不能互动、不挡路。待机就是：站一会儿 → 随机「看」一圈或者低头「吃草」一阵 → 站回来，
## 帧照原图 200ms 一帧播（只会在站着 / 低着头这两张上多停，绝不比原图快）。
## 晨走到它另一边去，它站着的时候过一小会儿就转身朝着晨（低着头吃草时不转，抬起头再转）。
##
## 节点：根 Node2D 的 x = 四条腿的中线，y 不用管（_ready 里按晨的地面函数贴地：y = 地面那一行 + 1，和晨、蛇女一样）。
## 精灵在 _ready 里现搭，场景里不存帧。场景里放一个 Node2D、挂这个脚本、设 position.x 就行；晨不叫 "../Chen" 的话改 watch_path。
## 光：和蛇女一样用 scripts/chen_light.gdshader + chen.gd 的 ENVS[env]（乘 ENV_K 弱一点），整体乘 TINT 压暗偏冷绿：
## 原图是暖的红棕、奶白斑点和尾巴（L≈0.95，眼睛高光 1.0），压完最亮 ≈0.7，晨的白发还是全屏最亮。
## 脚下一块硬边接触阴影（三行、越往下越窄越淡），跟着朝向翻。

# ===================================================================== 精灵配置（tools/deer_from_gif.py 生成）
const SHEET := preload("res://art/characters/deer/deer.png")
const FRAME_SIZE := Vector2i(53, 58)
const FOOT := Vector2i(34, 55)          # x = 四条腿的中线，y = 蹄子着地那一行（远侧两条腿短一格，站在后面）
const ART_FACES := -1                   # 美术朝左
## 精灵表帧：0 站着；1~3 看（正脸、侧面、后脑勺）；4~6 吃草（低头一点、再低、嘴碰地）
const ANIMS := {
	"stand": {"frames": [0], "ms": 200, "loop": false},
	"look": {"frames": [1, 2, 3], "ms": 200, "loop": false},          # 看.gif 的 0→1→2→3→0，0 = 站着
	"graze_down": {"frames": [4, 5, 6], "ms": 200, "loop": false},    # 吃草.gif 的 0→1→2→3
	"graze_up": {"frames": [5, 4], "ms": 200, "loop": false},         # 倒着播回去抬头（原图一下跳回站着，太猛）
}
# =====================================================================

@export var watch_path := NodePath("../Chen")   # 朝着谁（晨）
@export var env := "forest"                     # 用 chen.gd 的 ENVS 里哪一套光

const TINT := Color(0.66, 0.74, 0.7)     # 整体压暗、偏冷绿：红棕身子和晨的斗篷同色系、面积还大，压到比斗篷暗一档；奶白斑点 L≈0.95 → ≈0.7
const ENV_K := 0.8                      # 场景偏色 / 受光边比晨弱多少（1 = 和晨一样）
const SINK := 1                         # 脚底那行盖住地面最上面一行（和晨一样）
const TURN_GAP := 10.0                  # 晨离它中线超过这么多像素才算「在另一边」
const TURN_DELAY := 0.4                 # 晨走过去以后过多久转身
const STAND_HOLD := Vector2(2.5, 6.0)   # 每次站着停几秒（随机）
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
var _hold := 0.0                        # 站着 / 低着头还要停几秒（0 = 正在播动画）
var _rng := RandomNumberGenerator.new()


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
	_apply_env()
	_stand(_rng.randf_range(0.8, STAND_HOLD.y))     # 第一次站的时间短一点、随机，别和蛇女同一拍
	_snap()
	_set_facing(_want() if _watch != null else facing)


func _build_frames() -> SpriteFrames:
	var sf := SpriteFrames.new()
	sf.remove_animation(&"default")
	for name in ANIMS:
		var a: Dictionary = ANIMS[name]
		var frames: Array = a["frames"]
		sf.add_animation(name)
		sf.set_animation_speed(name, 1000.0)       # duration 的单位 = 1ms
		sf.set_animation_loop(name, a.get("loop", true))
		for i in frames.size():
			var t := AtlasTexture.new()
			t.atlas = SHEET
			t.region = Rect2(int(frames[i]) * FRAME_SIZE.x, 0, FRAME_SIZE.x, FRAME_SIZE.y)
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
	var fx := FRAME_SIZE.x - FOOT.x if spr.flip_h else FOOT.x
	spr.offset = Vector2(-fx, -(FOOT.y + 1))
	var d := Vector2(CHEN_GD.ENVS.get(env, {}).get("dir", Vector2(0, -1)))
	if spr.flip_h:
		d.x = -d.x
	_mat.set_shader_parameter("rim_dir", d.normalized())
	_shadow.queue_redraw()


func _want() -> int:
	return 1 if _watch.position.x > position.x else -1


# ----------------------------------------------------------------------- 待机：站 → 看 / 吃草 → 站
func _stand(hold: float) -> void:
	spr.play(&"stand")
	_hold = hold


func _on_finished() -> void:
	match spr.animation:
		&"look", &"graze_up":
			_stand(_rng.randf_range(STAND_HOLD.x, STAND_HOLD.y))
		&"graze_down":
			_hold = _rng.randf_range(GRAZE_HOLD.x, GRAZE_HOLD.y)     # 停在嘴碰地那帧


func _process(delta: float) -> void:
	if _hold > 0.0:
		_hold -= delta
		if _hold <= 0.0:
			_hold = 0.0
			if spr.animation == &"stand":
				spr.play(&"graze_down" if _rng.randf() < GRAZE_CHANCE else &"look")
			elif spr.animation == &"graze_down":
				spr.play(&"graze_up")
	# 只在站着的时候转身
	if _watch == null or not _watch.visible or spr.animation != &"stand":
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
