extends RefCounted
## 第一关小游戏 bag_burst：坠机撞地后的背包特写（docs/剧情改动/第一关新版_实现规格.md 第 1 步）。
##   画面压暗，背包特写（art/forest_story/bag_closeup.png，原大 96×104，不放大）落到画面中间，背后一圈坠机火光那样的暖光；
##   背包一颠，翻盖一帧帧掀起来（4 帧横排：合着 → 掀开，每帧 100ms），两件东西先后从包口飞出去，沿弧线飞出画面。
##   两件都是剪影、没有名字（一件以后和跳舞有关，另一件还没定）。然后整个特写淡掉，回到森林。不用玩家操作，约 4 秒。
##   11-02 作者试玩：原来放大 6 倍的小背包没质感 → 特写单独画（画图脚本在笔记文件夹 bag_art.py）。
##
## 剧本步骤：{"do": "mechanic", "id": "bag_burst"}
##   可选："sets": [flag…]（播完设上）。
## 剪影的形状是占位（SIL_A / SIL_B，原大，和背包同一个像素格），等两件东西定了再换图。

const ID := "bag_burst"
const LAYER := 40                       # UI（20）上面、黑幕 Top（50）下面
const BAG_TEX := "res://art/forest_story/bag_closeup.png"
const FRAMES := 4                                 # 0 合着，1~3 翻盖掀起来
const FRAME_SEC := 0.1                            # 和晨的动画一样 100ms 一帧
const MOUTH := Vector2(48, 40)                    # 掀开以后包口在图里的位置
const DIM := Color(0.04, 0.07, 0.07, 0.62)
const GLOW := Color("#c08050")                    # 背包后面那圈光：坠机的火光（背包的亮面也是被它照的）
const SIL := Color("#1c1a20")                     # 剪影：比背包最暗处还暗一点，没有细节
const CENTER := Vector2(240, 140)

## 剪影（# = 实），占位：A 软软的、像打了结的带子；B 扁的、斜着的一块
const SIL_A := [
	"..####......####..",
	".######....######.",
	"########..########",
	"##################",
	".################.",
	"..##############..",
	"...####....####...",
	"..####......####..",
	"..###........###..",
	"...#..........#...",
]
const SIL_B := [
	".......####.....",
	"....#########...",
	".#############..",
	"################",
	"################",
	"################",
	".###############",
	"..##############",
	"...############.",
	".....#########..",
	".......#####....",
	".........##.....",
]


static func load_tex(p: String) -> Texture2D:
	if ResourceLoader.exists(p):
		return load(p)
	if FileAccess.file_exists(p):                    # 新画的、编辑器还没导入：直接读 png
		var img := Image.load_from_file(ProjectSettings.globalize_path(p))
		if img != null and not img.is_empty():
			return ImageTexture.create_from_image(img)
	return null


static func _mask_tex(rows: Array, c: Color) -> ImageTexture:
	var w := (rows[0] as String).length()
	var img := Image.create(w, rows.size(), false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	for y in rows.size():
		for x in w:
			if (rows[y] as String)[x] == "#":
				img.set_pixel(x, y, c)
	return ImageTexture.create_from_image(img)


static func _bez(a: Vector2, c: Vector2, b: Vector2, u: float) -> Vector2:
	return a.lerp(c, u).lerp(c.lerp(b, u), u)


# ======================================================================= 演出
var speed := 1.0
var _layer: CanvasLayer
var _root: Control
var _bag: TextureRect
var _sheet: Texture2D


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	if r.ff:
		ff(r, st)
		return
	_build(lv)
	var k := 1.0 / speed
	var bag_home := (CENTER - _bag.size / 2.0).round()
	# 1. 压暗 + 背包落下来停住（sine 缓停，0.7 秒）
	var tw := _root.create_tween().set_parallel(true)
	tw.tween_property(_root, "modulate:a", 1.0, 0.5 * k).set_trans(Tween.TRANS_SINE)
	tw.tween_method(func(y: float): _bag.position = Vector2(bag_home.x, round(y)), bag_home.y - 14.0, bag_home.y, 0.7 * k) \
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	await tw.finished
	await _wait(0.45 * k)
	# 2. 一颠，翻盖一帧帧掀起来，两件东西先后从包口飞出去
	_jolt(bag_home, k)
	await _wait(0.2 * k)
	for f in range(1, FRAMES):
		_frame(f)
		await _wait(FRAME_SEC * k)
	var mouth := bag_home + MOUTH
	_fly(SIL_A, mouth, Vector2(150, -40), Vector2(-70, -40), 1.0 * k)
	await _wait(0.5 * k)
	_jolt(bag_home, k)
	await _fly(SIL_B, mouth, Vector2(350, -60), Vector2(560, -30), 1.0 * k)
	await _wait(0.5 * k)
	# 3. 特写淡掉
	var out := _root.create_tween()
	out.tween_property(_root, "modulate:a", 0.0, 0.6 * k).set_trans(Tween.TRANS_SINE)
	await out.finished
	_layer.queue_free()
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))
	print("MECH %s done" % ID)


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	speed = 4.0
	await run(lv, w, r, st)


func ff(_r: Node, st: Dictionary) -> void:
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))


func check(_story: Node, _st: Dictionary) -> Array:
	var out: Array = []
	if load_tex(BAG_TEX) == null:
		out.append("背包图 %s 找不到" % BAG_TEX)
	out.append("info: bag_burst 的两个剪影是占位形状，等东西定了换图")
	return out


func _build(lv: Node) -> void:
	_layer = CanvasLayer.new()
	_layer.name = "BagBurst"
	_layer.layer = LAYER
	lv.add_child(_layer)
	_root = Control.new()
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.size = Vector2(480, 270)
	_root.modulate.a = 0.0
	_layer.add_child(_root)
	var dim := ColorRect.new()
	dim.color = DIM
	dim.size = Vector2(480, 270)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(dim)
	# 背包后面一圈光：三档同心椭圆（硬边，一档一档，不是糊的渐变）
	for i in 3:
		var g := _ellipse(Vector2i(160 - 38 * i, 112 - 26 * i), Color(GLOW, 0.08 + 0.04 * i))
		g.position = (CENTER - g.size / 2.0 + Vector2(0, 12)).round()
		_root.add_child(g)
	_sheet = load_tex(BAG_TEX)
	var at := AtlasTexture.new()
	at.atlas = _sheet
	_bag = _rect(at)
	_frame(0)
	_bag.size = at.region.size
	_root.add_child(_bag)


## 换到第 f 帧（横排）
func _frame(f: int) -> void:
	var at := _bag.texture as AtlasTexture
	if _sheet == null:
		return
	var fw := float(_sheet.get_width()) / FRAMES
	at.region = Rect2(fw * f, 0, fw, _sheet.get_height())


func _rect(t: Texture2D) -> TextureRect:
	var r := TextureRect.new()
	r.texture = t
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_SCALE
	r.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	r.size = t.get_size()
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


## 一个实心椭圆（原大，硬边）
func _ellipse(sz: Vector2i, c: Color) -> TextureRect:
	var w := sz.x
	var h := sz.y
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	for y in h:
		for x in w:
			var dx := (x + 0.5 - w / 2.0) / (w / 2.0)
			var dy := (y + 0.5 - h / 2.0) / (h / 2.0)
			if dx * dx + dy * dy <= 1.0:
				img.set_pixel(x, y, c)
	return _rect(ImageTexture.create_from_image(img))


## 背包一颠：往上 4 像素再落回去（sine，0.3 秒）
func _jolt(home: Vector2, k: float) -> void:
	var tw := _bag.create_tween()
	tw.tween_method(func(y: float): _bag.position.y = round(y), home.y, home.y - 4.0, 0.12 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tw.tween_method(func(y: float): _bag.position.y = round(y), home.y - 4.0, home.y, 0.2 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)


## 一件东西从包口（藏在背包后面）沿二次贝塞尔弧线飞出画面：开头快、后面慢一点（EASE_OUT），像被弹出去
func _fly(rows: Array, from: Vector2, ctrl: Vector2, to: Vector2, sec: float) -> void:
	var s := _rect(_mask_tex(rows, SIL))
	_root.add_child(s)
	_root.move_child(s, _bag.get_index())            # 在背包后面：从包口里冒出来
	var half := s.size / 2.0
	s.position = (from - half).round()
	var step := func(u: float) -> void:
		s.position = (_bez(from, ctrl, to, u) - half).round()
		if u > 0.12 and s.get_index() < _bag.get_index():
			_root.move_child(s, -1)                  # 出了包口：挪到背包前面
	var tw := s.create_tween()
	tw.tween_method(step, 0.0, 1.0, sec).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	await tw.finished
	s.queue_free()


func _wait(sec: float) -> void:
	await _layer.get_tree().create_timer(sec).timeout
