extends Node2D
## 蛇女（NPC）：浅金发、红发带、奶白蛇尾的少女，盘着尾巴站在森林里待机（8 帧，每帧 200ms，第 6~8 帧闭眼）。
## 没有剧本：不说话、不能互动、不挡路，只是站着；晨走到她另一边去，她过一小会儿就转身朝着晨。
##
## 节点：根 Node2D 的 x = 身体中线，y 不用管（_ready 里按晨的地面函数贴地：y = 地面那一行 + 1，和晨、npc_alien 一样）。
## 精灵在 _ready 里现搭，场景里不存帧。场景里放一个 Node2D、挂这个脚本、设 position.x 就行；
## 晨不叫 "../Chen" 的话改 watch_path。
## 滑行（剧本用：森林章节里她是弥洛）：glide_to(x) 按 GLIDE_SPEED 平移过去，idle 照常播（蛇滑行），朝向跟着移动方向；
## is_gliding() 问还在不在滑。不调它的时候和以前完全一样。
## 光：和晨用同一个 scripts/chen_light.gdshader、同一套 chen.gd 的 ENVS[env] 参数（乘 ENV_K 弱一点）；
## 她本来比晨亮（奶白蛇尾 L≈0.96、金发 0.7），整体乘 TINT（偏一点森林的冷绿）压一档，晨的白发还是全屏最亮。
## 脚下一块硬边接触阴影（和 chen_fx.gd 的写法一样：三行、越往下越窄越淡），跟着朝向翻。

# ===================================================================== 精灵配置（tools/snake_from_gif.py 生成）
const SHEET := preload("res://art/characters/snake/snake.png")
const FRAME_SIZE := Vector2i(31, 50)
const FOOT := Vector2i(17, 45)          # x = 身体中线（脖子到竖直蛇身那段），y = 盘着的尾巴着地那一行
const ART_FACES := 1                    # 美术朝右（脸和眼睛偏右，马尾在左后）
const ANIMS := {
	"idle": {"frames": [0, 1, 2, 3, 4, 5, 6, 7], "ms": 200},   # 原图就是 200ms 一帧（作者同意待机慢一点，别改快）
}
# =====================================================================

@export var watch_path := NodePath("../Chen")   # 朝着谁（晨）
@export var env := "forest"                     # 用 chen.gd 的 ENVS 里哪一套光

const TINT := Color(0.74, 0.8, 0.76)    # 整体压暗、偏一点冷绿：最亮的奶白 L≈0.77（晨白发 0.9~1.0）
const ENV_K := 0.8                      # 场景偏色 / 受光边比晨弱多少（1 = 和晨一样）
const SINK := 1                         # 脚底那行盖住地面最上面一行（和晨一样）
const TURN_GAP := 8.0                   # 晨离她中线超过这么多像素才算「在另一边」（免得站在她身上来回翻）
const TURN_DELAY := 0.35                # 晨走过去以后过多久转身（像是看见了再转）
## 接触阴影：每行 [左, 右)（像素，相对身体中线、美术朝右），从脚底那行往下三行
const SHADOW_ROWS := [[-15, 12], [-13, 10], [-10, 7]]
const SHADOW_A := [0.36, 0.26, 0.15]

const CHEN_GD := preload("res://scripts/chen.gd")
const LIGHT_SHADER := preload("res://scripts/chen_light.gdshader")

var spr: AnimatedSprite2D
var facing := -1
var _watch: Node2D
var _mat: ShaderMaterial
var _shadow: Node2D
var _turn_t := 0.0
const GLIDE_SPEED := 40.0               # 滑行速度（像素 / 秒）；动画不变
var _gliding := false
var _glide_x := 0.0
var _glide_v := GLIDE_SPEED
var _gx := 0.0


func _ready() -> void:
	position.x = round(position.x)
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
	_apply_env()
	spr.play(&"idle")
	spr.frame = 2                       # 别和别的什么同一拍起步
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
	# 翻转是在帧的矩形里左右镜像，锚点 x 跟着镜像，身体中线不跳；offset 都是整数，翻完还是对齐像素
	var fx := FRAME_SIZE.x - FOOT.x if spr.flip_h else FOOT.x
	spr.offset = Vector2(-fx, -(FOOT.y + 1))
	var d := Vector2(CHEN_GD.ENVS.get(env, {}).get("dir", Vector2(0, -1)))
	if spr.flip_h:
		d.x = -d.x
	_mat.set_shader_parameter("rim_dir", d.normalized())
	_shadow.queue_redraw()


func _want() -> int:
	return 1 if _watch.position.x > position.x else -1


## 滑到 x（世界坐标）停下。speed 不给就是 GLIDE_SPEED。
func glide_to(x: float, speed := GLIDE_SPEED) -> void:
	x = round(x)
	if absf(x - position.x) < 1.0:
		return
	_gliding = true
	_glide_x = x
	_glide_v = speed
	_gx = position.x
	_set_facing(1 if x > position.x else -1)


func is_gliding() -> bool:
	return _gliding


## 直接站到 x（剧本的 show / 跳节拍用），停掉滑行
func place(x: float) -> void:
	_gliding = false
	position.x = round(x)
	_snap()


func _process(delta: float) -> void:
	if _gliding:
		var step := _glide_v * delta
		if absf(_glide_x - _gx) <= step:
			_gx = _glide_x
			_gliding = false
		else:
			_gx += signf(_glide_x - _gx) * step
		position.x = round(_gx)
		_snap()
		_turn_t = 0.0
		return
	if _watch == null or not _watch.visible:
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
	# 三行硬边：脚底那行（被尾巴盖住，只露出两边）和往下两行，压暗地面一档
	for i in SHADOW_ROWS.size():
		var l: int = SHADOW_ROWS[i][0]
		var r: int = SHADOW_ROWS[i][1]
		if facing != ART_FACES:
			var t := l
			l = -r
			r = -t
		_shadow.draw_rect(Rect2(l, i - 1, r - l, 1), Color(0, 0, 0, SHADOW_A[i]))
