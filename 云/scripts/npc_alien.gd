extends Node2D
## 和晨一起坐飞船的另一个外星人（NPC）。用的是美术姐梧桐画的旧主角（art/characters/chen/chen.png、chen_getup.png），
## 第一关开场坠毁时和晨一起被甩出飞船、脸朝下趴着、比晨早一点爬起来，之后站在残骸旁边待机：
## 偶尔眨眼；偶尔转过来正面站一会儿，再转回去朝着晨。不说话（剧情还没定），不挡路，不能互动。
##
## 节点：根 Node2D 的 position = 脚底（和晨一样：x = 身体中线，y = 地面那一行 + 1）。精灵在 _ready 里现搭，场景里不存帧。
## 关卡用法（level_forest.gd）：
##   throw_step(a, b, k, arc, r0, r1)   被甩出来的这一帧（k 0..1，按 90° 一档翻滚）；关卡用自己的 tween 驱动，跳过时一起停
##   lie(dir)                           趴着（dir = 头朝哪边：1 右、-1 左）
##   get_up()                           爬起来（播完自己回待机），返回动画总秒数
##   stand(x)                           直接站好（跳段调试 / 跳过开场）
##   watch(node)                        之后待机时朝着这个节点（晨）站
## 颜色：她本来比晨亮（米白头发、亮蓝衣服），整体乘 TINT 压暗一点，晨还是画面里最亮的。

# ===================================================================== 精灵配置（梧桐版，tools/chen_sprites.py / level1_chen_getup.py 生成）
const SHEET := preload("res://art/characters/chen/chen.png")
const GETUP_SHEET := preload("res://art/characters/chen/chen_getup.png")
const FRAME_SIZE := Vector2i(40, 42)
const FOOT := Vector2i(20, 41)          # 脚底锚点（帧里的像素坐标）
const ART_FACES := 1                    # 美术朝右
const ANIMS := {
	"idle": {"frames": [3, 4, 5, 6, 7, 8, 9, 10], "ms": 150},
	"idle_blink": {"frames": [11, 12, 13, 14, 15, 16, 17, 18], "ms": 150},
	"idle_eye": {"frames": [19, 20, 21, 22, 23, 24, 25, 26], "ms": 150},
	"front": {"frames": [27, 28, 29, 30, 31, 32], "ms": 150},
	"front_blink": {"frames": [33, 34, 35, 36, 37, 38], "ms": 150},
	"lie": {"frames": [0], "ms": 400, "loop": false, "sheet": GETUP_SHEET, "size": Vector2i(64, 42)},
	"getup": {"frames": [1, 0, 1, 2, 3, 4, 5], "ms": [140, 420, 160, 460, 420, 200, 150], "loop": false,
		"sheet": GETUP_SHEET, "size": Vector2i(64, 42), "then": "idle"},
}
# =====================================================================

const TINT := Color(0.58, 0.6, 0.64)    # 压暗（偏一点冷）：她身上最亮的 L≈0.67，晨的白发是 0.9，晨还是最亮
const BODY_C := Vector2(0, -19)         # 站着约 38 像素高，翻滚时绕腰转
const BLINK_EVERY := Vector2(2.2, 4.5)  # 隔几秒眨一次眼
const EYE_CHANCE := 0.3                 # 该眨眼时换成头环第三只眼闭一下的概率
const FRONT_EVERY := Vector2(6.0, 11.0) # 隔几秒转过来正面站一会儿
const FRONT_HOLD := Vector2(1.8, 3.0)   # 正面站多久

var spr: AnimatedSprite2D
var facing := 1
var _watch: Node2D
var _rng := RandomNumberGenerator.new()
var _idle_t := 0.0
var _next_blink := 2.0
var _front_t := 0.0
var _next_front := 5.0
var _front_left := 0.0                  # >0：正在正面站着，还剩几秒
var _grounded := false                  # 站起来以后才开始待机的小动作


func _ready() -> void:
	_rng.seed = 31
	modulate = TINT
	spr = AnimatedSprite2D.new()
	spr.name = "Sprite"
	spr.centered = false
	spr.sprite_frames = _build_frames()
	add_child(spr)
	spr.animation_changed.connect(func(): _set_facing(facing))
	spr.animation_looped.connect(_on_looped)
	spr.animation_finished.connect(_on_finished)
	spr.play(&"idle")
	_set_facing(facing)
	_next_front = _rng.randf_range(FRONT_EVERY.x, FRONT_EVERY.y) * 0.5


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


static func anim_time(name: String) -> float:
	var a: Dictionary = ANIMS[name]
	var total := 0.0
	for i in (a["frames"] as Array).size():
		total += float(a["ms"][i] if a["ms"] is Array else a["ms"])
	return total / 1000.0


func _set_facing(f: int) -> void:
	facing = f
	spr.flip_h = f != ART_FACES
	var a: Dictionary = ANIMS.get(String(spr.animation), {})
	var size: Vector2i = a.get("size", FRAME_SIZE)
	var fx := size.x - FOOT.x if spr.flip_h else FOOT.x
	spr.offset = Vector2(-fx, -(FOOT.y + 1))


# ===================================================================== 开场：甩出来、趴着、爬起来
func throw_step(a: Vector2, b: Vector2, k: float, arc: float, r0: float, r1: float) -> void:
	## 被甩出来：a → b 一道弧线（往上拱 arc 像素），从 r0 转到 r1，按 90° 一档（像素一一对应，不出斜着的 mixel）
	_grounded = false
	visible = true
	var p := a.lerp(b, k)
	p.y -= sin(k * PI) * arc
	position = p.round()
	if spr.animation != &"idle":
		spr.play(&"idle")
	var r := snappedf(lerpf(r0, r1, k), PI / 2.0)
	# 绕腰转；快落地时整体往下沉，转 90° 以后身体的厚度一半在地下（和晨的写法一样）
	spr.position = (BODY_C - BODY_C.rotated(r) + Vector2(0, 14.0 * k)).round()
	spr.rotation = r


func lie(dir: int) -> void:
	_grounded = false
	_front_left = 0.0
	visible = true
	spr.rotation = 0.0
	spr.position = Vector2.ZERO
	spr.play(&"lie")
	_set_facing(dir)


func get_up() -> float:
	_grounded = false
	spr.play(&"getup")
	return anim_time("getup")


func stand(x: float, ground_y: float) -> void:
	visible = true
	position = Vector2(round(x), ground_y)
	spr.rotation = 0.0
	spr.position = Vector2.ZERO
	spr.play(&"idle")
	_face_watch()
	_grounded = true
	_idle_t = 0.0
	_front_t = 0.0


func watch(n: Node2D) -> void:
	_watch = n


func _face_watch() -> void:
	if _watch != null and absf(_watch.position.x - position.x) > 2.0:
		_set_facing(1 if _watch.position.x > position.x else -1)


# ===================================================================== 待机
func _process(delta: float) -> void:
	if not _grounded:
		return
	_idle_t += delta
	if _front_left > 0.0:
		_front_left -= delta
		if _front_left <= 0.0:
			spr.play(&"idle")
			_face_watch()
		return
	_front_t += delta
	if _front_t > _next_front and spr.animation == &"idle":
		# 转过来正面站一会儿（看看镜头 / 看看四周）
		_front_t = 0.0
		_next_front = _rng.randf_range(FRONT_EVERY.x, FRONT_EVERY.y)
		_front_left = _rng.randf_range(FRONT_HOLD.x, FRONT_HOLD.y)
		spr.play(&"front")
		return
	# 晨走到她另一边去了：转身
	if spr.animation == &"idle" and _watch != null:
		var want := 1 if _watch.position.x > position.x else -1
		if want != facing and absf(_watch.position.x - position.x) > 8.0:
			_set_facing(want)


func _on_looped() -> void:
	var a := String(spr.animation)
	if a in ["lie", "getup"]:
		return
	var front := a.begins_with("front")
	var base := "front" if front else "idle"
	if a != base:
		spr.play(base)
	elif _idle_t > _next_blink:
		_idle_t = 0.0
		_next_blink = _rng.randf_range(BLINK_EVERY.x, BLINK_EVERY.y)
		var pick := base + "_blink"
		if not front and _rng.randf() < EYE_CHANCE:
			pick = "idle_eye"
		spr.play(pick)


func _on_finished() -> void:
	var a: Dictionary = ANIMS.get(String(spr.animation), {})
	if a.has("then"):
		spr.play(StringName(a["then"]))
	if String(spr.animation) == "idle" and not _grounded:
		# 爬起来了
		_grounded = true
		_idle_t = 0.0
		_front_t = 0.0
		_face_watch()


func is_up() -> bool:
	return _grounded
