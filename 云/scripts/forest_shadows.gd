extends Node2D
## 林子深处会动的影子：偶尔有一只鹿一闪跑过、一只鹿走出来吃草被惊走、一群小鸟从林冠里惊起掠过雾带、
## 一只渡鸦在中远层扇几下滑一段飞过去、几只停在枝头的小鸟忽然一起飞走、远处一头很淡很慢的驼鹿、
## 中远层一只小跑的狐狸。安静、偶尔、一闪而过：同一时间只有一件事，事情之间留一段什么都不动的空白。
##
## 三个 Parallax2D 子层，scroll_scale 和背景同名层一样，动物在它们下面跑：
##   Deep   0.06（和 Ridge 一样）：驼鹿。开场时搬到 deep_before 指的节点前面（比如 ../Far），
##          这样驼鹿在远层的树后面；不设就留在本场景里。
##   Far    0.18：鹿、小鸟群。
##   MidFar 0.38：狐狸、渡鸦、枝头的小鸟（停在中远层的树枝上，所以 midfar_texture 要和背景的中远层是同一张）。
## 整个场景实例化到 forest_test.tscn 的 Far 和 MidFar 之间。
##
## 图在 art/creatures/（tools/forest_creatures.py 画的白 / 灰剪影），颜色由 shadow_tint.gdshader 按
## 「那个高度的雾色」往 ink 推 *_ink 这么多来定：只会比雾暗，越远越接近雾色。
## 雾色从 fog_texture（天空层 sky.png）每一行的平均色读出来，背景改色以后自动跟着变。
## 鸟飞的路线专门穿过雾带最亮的那一段（y≈160~176）和光斑（也从 sky.png 里找），逆光剪影才看得见。
##
## 奔跑的鹿是「一帧跳一步」：每换一帧精灵往前跳 px（= 着地的脚每帧往后退多少），着地的脚在地上一动不动。
##
## 调试（只在 debug 版）：F1 立刻放下一种（KINDS 的顺序），
## 命令行 -- --shadow=deer（可以逗号分开放几种：deer,deer_graze,birds,raven,perch,moose,fox）开场立刻放；
## --shadow_x=240 让它直接出现在屏幕这个 x（截图用）；--shadow_auto=0 关掉随机出现；
## --shadow_log 在输出里打印每次出现、结束的时刻（看节奏用）。

const KINDS := ["deer", "deer_graze", "birds", "raven", "perch", "moose", "fox"]

# 精灵表：帧数、每帧毫秒、每帧前进像素、step = 每换一帧跳一步（不匀速滑）。和 forest_creatures.py 的输出一致。
const SHEETS := {
	"deer_run": {"n": 8, "ms": 70, "px": 10.0, "step": true},
	"deer_walk": {"n": 8, "ms": 100, "px": 1.21},
	"deer_graze": {"n": 4, "ms": 200, "px": 0.0},
	"deer_lookup": {"n": 3, "ms": 120, "px": 0.0},
	"deer_turn": {"n": 7, "ms": 75, "px": 0.0},
	"moose_walk": {"n": 8, "ms": 150, "px": 2.54},
	"fox_trot": {"n": 6, "ms": 90, "px": 2.63},
	"bird_flap": {"n": 4, "ms": 90, "px": 0.0},
	"bird_small": {"n": 4, "ms": 80, "px": 0.0},
	"raven_fly": {"n": 7, "ms": 85, "px": 0.0},
	"bird_perch": {"n": 3, "ms": 200, "px": 0.0},
}
const TEX := {
	"deer_run": preload("res://art/creatures/deer_run.png"),
	"deer_walk": preload("res://art/creatures/deer_walk.png"),
	"deer_graze": preload("res://art/creatures/deer_graze.png"),
	"deer_lookup": preload("res://art/creatures/deer_lookup.png"),
	"deer_turn": preload("res://art/creatures/deer_turn.png"),
	"moose_walk": preload("res://art/creatures/moose_walk.png"),
	"fox_trot": preload("res://art/creatures/fox_trot.png"),
	"bird_flap": preload("res://art/creatures/bird_flap.png"),
	"bird_small": preload("res://art/creatures/bird_small.png"),
	"raven_fly": preload("res://art/creatures/raven_fly.png"),
	"bird_perch": preload("res://art/creatures/bird_perch.png"),
}
const TINT := preload("res://scripts/shadow_tint.gdshader")
const RAVEN_FLAP_N := 6      # raven_fly 的 0~5 是扇翅一圈，6 是滑翔
const RUN_FROM_TURN := 3     # 转身最后一帧（后腿压低）接奔跑的第 3 帧（后腿最后一蹬）

## 天空层：每一行的平均色就是那个高度的雾色；雾带里最亮的几列就是光斑。
@export var fog_texture: Texture2D = preload("res://art/forest/sky.png")
## 中远层的树（枝头小鸟停在它的树枝上）。要和背景里 MidFar 层是同一张图。
@export var midfar_texture: Texture2D = preload("res://art/forest/midfar.png")
## 远层、中景的树：枝头小鸟背后 / 前面有树干挡着的枝就不停（要和背景里 Far、Mid 层是同一张图）。
@export var far_texture: Texture2D = preload("res://art/forest/far.png")
@export var mid_texture: Texture2D = preload("res://art/forest/mid.png")
## 最暗的影子色（林冠里那种几乎是黑的墨绿）。
@export var ink := Color("#08100d")
## Deep 层（驼鹿）开场搬到这个节点前面，一般填 ../Far。空着就不搬。
@export var deep_before: NodePath

@export_group("地面（屏幕 y，脚底那一行的下沿）")
@export var deep_ground := 190.0
@export var far_ground := 193.0
@export var midfar_ground := 205.0

@export_group("影子多暗（0 = 雾色，1 = ink）")
@export var deep_ink := 0.3
@export var far_ink := 0.6
@export var midfar_ink := 0.8
## 小鸟：只有 3~5 像素，要比鹿暗得多才看得见（逆光剪影）。
@export var bird_ink := 0.85
@export var raven_ink := 0.8

@export_group("鸟飞过的雾带（屏幕 y）")
## 雾带最亮的那一段：小鸟群、渡鸦、飞走的枝头小鸟都从这里过。
@export var band_y := Vector2(160.0, 174.0)
## 找不到光斑时用这几个（屏幕 x）。
@export var light_spots_fallback := PackedFloat32Array([150.0, 262.0, 378.0])

@export_group("出现")
@export var auto_spawn := true
@export var spawn_seed := 1027
## 开场第一只（一只跑过的鹿）在这个区间里出现（秒）。
@export var first_delay := Vector2(5.0, 7.0)
## 第一只鹿跑掉以后，安静这么久再开始随机出现（秒）。
@export var first_quiet := Vector2(18.0, 26.0)
## 之后：上一件事结束（画面里什么都不动了）以后，隔这么久再来下一件（秒）。
@export var interval := Vector2(14.0, 32.0)
@export var weights := {"deer": 3.5, "deer_graze": 2.0, "birds": 3.0, "raven": 2.2, "perch": 1.5,
		"moose": 0.8, "fox": 1.2}


class Actor:
	var kind := ""
	var layer: Parallax2D
	var s := 0.0              # 这层跟镜头的比例
	var lx := 0.0             # 层坐标：屏幕 x = lx - s * 镜头左边缘
	var y := 0.0              # 屏幕 y（脚底）
	var facing := 1
	var sprite: Sprite2D
	var mat: ShaderMaterial
	var ink_k := 0.5
	var half_w := 16.0
	var anim := ""
	var frame := 0
	var ft := 0.0
	var steps: Array = []
	var step_t := 0.0
	var age := 0.0
	var dead := false
	# 鸟（mode：flock 飞过 / raven 渡鸦 / perch 停在枝头）
	var bird := false
	var mode := ""
	var t := 0.0
	var lx0 := 0.0
	var y0 := 0.0
	var v := 0.0
	var phase := 0.0
	var glide := 0.0
	var oy := 0.0
	var lag := 0.0
	# flock：沿飞过的距离 d 分三段：往下扎进雾带（0~d_desc）→ 贴着雾带平飞（~d_cruise）→ 往上飞出去
	var yb := 0.0
	var y_exit := 0.0
	var d_desc := 1.0
	var d_cruise := 1.0
	# raven：扇几下、滑一段
	var flaps_left := 0
	# perch：停多久、什么时候换个小动作
	var perch_t := 0.0
	var idle_t := 0.0
	var fly_dir := 1


@onready var deep: Parallax2D = $Deep
@onready var far: Parallax2D = $Far
@onready var midfar: Parallax2D = $MidFar

var rng := RandomNumberGenerator.new()
var actors: Array[Actor] = []
var _fog_rows: PackedColorArray = PackedColorArray()
var _spots: PackedFloat32Array = PackedFloat32Array()
var _perches: Array = []          # 中远层树枝顶上能停鸟的几段：[[Vector2(图里 x, y), ...], ...]
var _perches_scanned := false
var _layer_imgs := {}
var _next := 0.0
var _stage := 0                   # 0 = 等第一只鹿，1 = 第一只之后的安静，2 = 随机
var _last_kind := ""
var _debug_i := 0
var _cli_x := NAN
var _log := false
var _clock := 0.0


func _ready() -> void:
	process_priority = 100   # 在镜头和背景层更新之后再摆动物，不会差一帧
	rng.seed = spawn_seed
	_build_fog_rows()
	_find_light_spots()
	_next = rng.randf_range(first_delay.x, first_delay.y)
	var cli: Array[String] = []
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shadow="):
			for k in a.trim_prefix("--shadow=").split(","):
				cli.append(k)
		elif a.begins_with("--shadow_x="):
			_cli_x = float(a.trim_prefix("--shadow_x="))
		elif a.begins_with("--shadow_auto="):
			auto_spawn = a.trim_prefix("--shadow_auto=") != "0"
		elif a == "--shadow_log":
			_log = true
	if not deep_before.is_empty():
		var target := get_node_or_null(deep_before)
		if target:
			_move_deep.call_deferred(target)
	if not cli.is_empty():
		_spawn_cli.call_deferred(cli)


func _exit_tree() -> void:
	if deep and deep.get_parent() != self and is_instance_valid(deep):
		deep.queue_free()


func _move_deep(target: Node) -> void:
	var p := target.get_parent()
	remove_child(deep)
	p.add_child(deep)
	p.move_child(deep, target.get_index())


func _spawn_cli(kinds: Array[String]) -> void:
	for k in kinds:
		spawn(k, _cli_x)


# ------------------------------------------------------------------ 颜色、光斑、树枝

func _build_fog_rows() -> void:
	_fog_rows.resize(270)
	var img: Image = fog_texture.get_image() if fog_texture else null
	if img == null:
		for y in 270:
			_fog_rows[y] = Color("#4e6b5a")
		return
	if img.is_compressed():
		img.decompress()
	var h := img.get_height()
	_fog_rows.resize(h)
	for y in h:
		var acc := Color(0, 0, 0, 0)
		var n := 0
		for x in range(0, img.get_width(), 3):
			acc += img.get_pixel(x, y)
			n += 1
		_fog_rows[y] = Color(acc.r / n, acc.g / n, acc.b / n, 1.0)


## 光斑：雾带那几行（band_y 往下一点）每一列的亮度，平滑以后取最亮的几个峰（左右 40 像素内最亮、比平均亮 6% 以上）。
func _find_light_spots() -> void:
	_spots = PackedFloat32Array()
	var img: Image = fog_texture.get_image() if fog_texture else null
	if img != null:
		if img.is_compressed():
			img.decompress()
		var w := img.get_width()
		var col := PackedFloat32Array()
		col.resize(w)
		var y0 := int(band_y.x)
		var y1 := mini(int(band_y.y) + 12, img.get_height() - 1)
		var mean := 0.0
		for x in w:
			var acc := 0.0
			for y in range(y0, y1 + 1, 2):
				var c := img.get_pixel(x, y)
				acc += c.r + c.g + c.b
			col[x] = acc
			mean += acc
		mean /= w
		var sm := PackedFloat32Array()
		sm.resize(w)
		for x in w:
			var acc := 0.0
			var n := 0
			for k in range(maxi(0, x - 10), mini(w, x + 11)):
				acc += col[k]
				n += 1
			sm[x] = acc / n
		for x in range(20, w - 20):
			if sm[x] < mean * 1.06:
				continue
			var peak := true
			for k in range(maxi(0, x - 40), mini(w, x + 41)):
				if sm[k] > sm[x] or (sm[k] == sm[x] and k < x):
					peak = false
					break
			if peak:
				_spots.append(float(x))
	if _spots.is_empty():
		_spots = light_spots_fallback


## 中远层树枝顶上能停鸟的地方（「枝顶」点）：
##   这个像素不透明，左右两边（允许上下差一格，斜着的细枝）也不透明；
##   正上方一行、左右 3 列内 2~8 行都是空的（鸟停的地方不贴着树干、树冠）；
##   正下方 3~5 行是空的（是细枝，不是树干顶或一团树冠）。
## 挨着的（x 差 ≤ 4、y 差 ≤ 2）连成一段，至少 2 个点（中远层的枝都是从树干上伸出来的短枝，一根停 1~2 只）。只扫一次（第一次放枝头小鸟时）。
func _scan_perches() -> void:
	_perches_scanned = true
	_perches = []
	if midfar_texture == null:
		return
	var img := midfar_texture.get_image()
	if img == null:
		return
	if img.is_compressed():
		img.decompress()
	img.convert(Image.FORMAT_RGBA8)
	var w := img.get_width()
	var h := img.get_height()
	var data := img.get_data()
	var op := func(x: int, y: int) -> bool:
		return x >= 0 and x < w and y >= 0 and y < h and data[(y * w + x) * 4 + 3] != 0
	var pts: Array[Vector2] = []
	for y in range(118, mini(176, h - 6)):
		for x in range(7, w - 7):
			if data[(y * w + x) * 4 + 3] == 0:
				continue
			if not (op.call(x - 1, y) or op.call(x - 1, y - 1) or op.call(x - 1, y + 1)):
				continue
			if not (op.call(x + 1, y) or op.call(x + 1, y - 1) or op.call(x + 1, y + 1)):
				continue
			if op.call(x, y + 3) or op.call(x, y + 4) or op.call(x, y + 5):
				continue
			var clear := true
			for yy in range(y - 8, y):
				for xx in range(x - 3, x + 4):
					if (yy < y - 1 or absi(xx - x) <= 1) and op.call(xx, yy):
						clear = false
						break
				if not clear:
					break
			if clear:
				pts.append(Vector2(x, y))
	pts.sort_custom(func(a: Vector2, b: Vector2) -> bool: return a.x < b.x)
	var cur: Array = []
	for p in pts:
		if not cur.is_empty() and (p.x - cur[-1].x > 4.0 or absf(p.y - cur[-1].y) > 2.0):
			if cur.size() >= 2:
				_perches.append(cur)
			cur = []
		cur.append(p)
	if cur.size() >= 2:
		_perches.append(cur)


func fog_at(y: float) -> Color:
	return _fog_rows[clampi(int(y), 0, _fog_rows.size() - 1)]


func _tint(a: Actor, y_body: float) -> void:
	var f := fog_at(y_body)
	a.mat.set_shader_parameter("fog", f)
	a.mat.set_shader_parameter("body", f.lerp(ink, a.ink_k))


# ------------------------------------------------------------------ 出现

func _input(event: InputEvent) -> void:
	if not OS.is_debug_build():
		return
	var k := event as InputEventKey
	if k and k.pressed and not k.echo and k.keycode == KEY_F1:
		var kind: String = KINDS[_debug_i % KINDS.size()]
		_debug_i += 1
		print("[shadows] F1 → ", kind)
		spawn(kind)


func _pick_kind() -> String:
	var kind := _pick_once()
	if kind == _last_kind:   # 不连着两次一样的（再抽一次，还一样就算了）
		kind = _pick_once()
	return kind


func _pick_once() -> String:
	var total := 0.0
	for k in weights:
		total += float(weights[k])
	var r := rng.randf() * total
	for k in weights:
		r -= float(weights[k])
		if r <= 0.0:
			return k
	return "deer"


func _view_w() -> float:
	return get_viewport().get_visible_rect().size.x


func _cam_left() -> float:
	return (get_viewport().get_canvas_transform().affine_inverse() * Vector2.ZERO).x


## 放一只。at_sx 是屏幕 x：给了就直接出现在那里（截图用），否则从画面一侧外面进来。
func spawn(kind: String, at_sx: float = NAN) -> void:
	_last_kind = kind
	if _log:
		print("[shadows] %6.1fs  %s" % [_clock, kind])
	match kind:
		"deer":
			var a := _make("deer_run", far, far_ink, far_ground, at_sx)
			a.steps = [{"anim": "deer_run", "move": true, "end": "exit"}]
		"deer_graze":
			var a := _make("deer_walk", far, far_ink, far_ground, at_sx)
			var steps: Array = []
			if is_nan(at_sx):
				var f := rng.randf_range(0.22, 0.5)
				var reach := _view_w() * f if a.facing > 0 else _view_w() * (1.0 - f)
				steps.append({"anim": "deer_walk", "move": true, "end": "reach", "reach": reach})
			steps.append({"anim": "deer_graze", "end": "time", "time": rng.randf_range(3.0, 6.0)})
			if rng.randf() < 0.45:   # 抬头看一眼，又低头吃
				steps.append({"anim": "deer_lookup", "end": "once", "hold": rng.randf_range(0.8, 1.4)})
				steps.append({"anim": "deer_graze", "end": "time", "time": rng.randf_range(1.5, 3.0)})
			steps.append({"anim": "deer_lookup", "end": "once", "hold": rng.randf_range(0.9, 1.6)})
			steps.append({"anim": "deer_turn", "end": "once", "flip": true})
			steps.append({"anim": "deer_run", "move": true, "end": "exit", "from": RUN_FROM_TURN})
			a.steps = steps
		"moose":
			var a := _make("moose_walk", deep, deep_ink, deep_ground, at_sx)
			a.steps = [{"anim": "moose_walk", "move": true, "end": "exit"}]
		"fox":
			var a := _make("fox_trot", midfar, midfar_ink, midfar_ground, at_sx)
			a.steps = [{"anim": "fox_trot", "move": true, "end": "exit"}]
		"birds":
			_spawn_flock(at_sx)
		"raven":
			_spawn_raven(at_sx)
		"perch":
			if not _spawn_perch(at_sx):
				_spawn_flock(at_sx)
		_:
			push_warning("[shadows] 不认识的种类：" + kind)


func _new_actor(anim: String, layer: Parallax2D, ink_k: float) -> Actor:
	var a := Actor.new()
	a.kind = anim
	a.layer = layer
	a.s = layer.scroll_scale.x
	a.ink_k = ink_k
	a.sprite = Sprite2D.new()
	a.sprite.centered = false
	a.mat = ShaderMaterial.new()
	a.mat.shader = TINT
	a.sprite.material = a.mat
	layer.add_child(a.sprite)
	_play(a, anim)
	actors.append(a)
	return a


func _make(anim: String, layer: Parallax2D, ink_k: float, ground: float, at_sx: float) -> Actor:
	var a := _new_actor(anim, layer, ink_k)
	a.y = ground
	a.facing = 1 if rng.randf() < 0.5 else -1
	var tex: Texture2D = TEX[anim]
	var h := tex.get_height()
	a.half_w = tex.get_width() / float(SHEETS[anim].n) * 0.5
	var sx := at_sx
	if is_nan(sx):
		sx = -a.half_w - 2.0 if a.facing > 0 else _view_w() + a.half_w + 2.0
	a.lx = sx + a.s * _cam_left()
	_tint(a, ground - h * 0.55)
	_place(a)
	return a


func _new_bird(anim: String, layer: Parallax2D, ink_k: float, mode: String, dir: int) -> Actor:
	var a := _new_actor(anim, layer, ink_k)
	a.bird = true
	a.mode = mode
	a.facing = dir
	a.half_w = TEX[anim].get_width() / float(SHEETS[anim].n) * 0.5
	a.sprite.flip_h = dir < 0
	return a


## 小鸟群：从林冠里（暗处）惊起，往下扎进雾带最亮的那一段，贴着它飞过一个光斑，再往上飞出画面。
func _spawn_flock(at_sx: float) -> void:
	var w := _view_w()
	var dir := 1 if rng.randf() < 0.5 else -1
	# 挑一个光斑，前面要留够往下扎的距离
	var spot := _spots[rng.randi_range(0, _spots.size() - 1)]
	var lead := rng.randf_range(110.0, 170.0)
	var sx0 := spot - dir * lead
	if not is_nan(at_sx):
		sx0 = at_sx
		spot = sx0 + dir * lead
	sx0 = clampf(sx0, -10.0, w + 10.0)
	var n := rng.randi_range(5, 8)
	var y0 := rng.randf_range(100.0, 116.0)
	var yb := rng.randf_range(band_y.x, band_y.y)
	var v := rng.randf_range(58.0, 72.0)
	var to_spot := absf(spot - sx0)
	for i in n:
		var a := _new_bird("bird_small" if rng.randf() < 0.3 else "bird_flap", far, bird_ink, "flock", dir)
		a.v = v * rng.randf_range(0.93, 1.07)
		a.lx0 = sx0 + rng.randf_range(-14.0, 14.0) + a.s * _cam_left()
		a.y0 = y0 + rng.randf_range(-5.0, 5.0)
		a.yb = yb + rng.randf_range(-4.0, 4.0)
		a.y_exit = rng.randf_range(104.0, 128.0)
		a.d_desc = maxf(40.0, to_spot * rng.randf_range(0.55, 0.75))
		a.d_cruise = to_spot + rng.randf_range(50.0, 100.0)
		a.phase = rng.randf() * TAU
		a.frame = rng.randi_range(0, 3)
		a.ft = rng.randf_range(0.0, 80.0)
		a.t = -rng.randf_range(0.0, 0.5)   # 一只接一只飞出来
		_bird_step(a, 0.0)


## 渡鸦：中远层，从画面一侧外面进来，贴着雾带飞过去；扇 2~4 下、滑一段，扇的时候往上一点，滑的时候往下沉。
func _spawn_raven(at_sx: float) -> void:
	var dir := 1 if rng.randf() < 0.5 else -1
	var a := _new_bird("raven_fly", midfar, raven_ink, "raven", dir)
	var sx := -a.half_w - 2.0 if dir > 0 else _view_w() + a.half_w + 2.0
	if not is_nan(at_sx):
		sx = at_sx
	a.lx0 = sx + a.s * _cam_left()
	a.lx = a.lx0
	a.y0 = rng.randf_range(band_y.x + 4.0, band_y.y + 8.0)   # 脚底那一行；身子在它上面 6 像素，正好在雾带最亮的地方
	a.y = a.y0
	a.v = rng.randf_range(64.0, 78.0)
	a.flaps_left = rng.randi_range(2, 3)
	a.phase = rng.randf() * TAU
	_bird_step(a, 0.0)


## 枝头的小鸟：中远层相邻的两三根短枝上一共停 3~5 只，待几秒（偶尔低头、张望），忽然一起飞走：
## 先往下掉进雾带，再贴着雾带飞出画面。鸟背后（远层）和前面（中景）有树干挡着的枝不要。
func _spawn_perch(at_sx: float) -> bool:
	if not _perches_scanned:
		_scan_perches()
	if _perches.is_empty():
		return false
	var w := _view_w()
	var cl := _cam_left()
	var s := midfar.scroll_scale.x
	var rep := midfar.repeat_size.x if midfar.repeat_size.x > 0.0 else 960.0
	var want := w * 0.5 if is_nan(at_sx) else at_sx
	var ok: Array = []        # [层坐标 x 偏移, 那一段, 屏幕 x, 分数]
	for g in _perches:
		var gx: float = g[g.size() / 2].x
		var k := roundf((s * cl + want - gx) / rep)
		var sx := gx + k * rep - s * cl
		if sx < 50.0 or sx > w - 50.0:
			continue
		var gy: float = g[g.size() / 2].y
		if not (_clear_behind(sx, gy, cl)):
			continue
		ok.append([k * rep, g, sx, gy + rng.randf_range(0.0, 24.0) - absf(sx - want) * 0.08])
	if ok.is_empty():
		return false
	ok.sort_custom(func(a: Array, b: Array) -> bool: return a[3] > b[3])
	var center: float = ok[0][2]
	var picked: Array = []
	for o in ok:
		if absf(float(o[2]) - center) <= 110.0:
			picked.append(o)
	# 每根枝上隔 3 像素一个位置（一根短枝停 1~3 只），从所有位置里随机挑 3~5 个
	var slots: Array[Vector2] = []
	for o in picked:
		var g: Array = o[1]
		var last := -100.0
		for q in g:
			if q.x - last >= 3.0:
				slots.append(Vector2(q.x + float(o[0]), q.y))
				last = q.x
	for i in range(slots.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var tmp := slots[i]
		slots[i] = slots[j]
		slots[j] = tmp
	var n := mini(rng.randi_range(3, 5), slots.size())
	var dir := 1 if rng.randf() < 0.5 else -1
	var stay := rng.randf_range(3.5, 6.0)
	for i in n:
		var a := _new_bird("bird_perch", midfar, bird_ink, "perch", 1 if rng.randf() < 0.6 else -1)
		a.lx = slots[i].x
		a.y = slots[i].y     # 脚底那一行的下沿 = 树枝顶那一行的上沿
		a.y0 = a.y
		a.perch_t = stay + rng.randf_range(0.0, 0.35)
		a.idle_t = rng.randf_range(0.4, 2.0)
		a.fly_dir = dir      # 飞走的方向（大家一样）
		_tint(a, a.y - 2.0)
		_place(a)
	return true


## 屏幕上 (sx, y) 那只停着的鸟（4×4）背后的远层、前面的中景，在这一刻有没有树干挡着。
func _clear_behind(sx: float, y: float, cam_left: float) -> bool:
	for pair in [[far_texture, 0.18], [mid_texture, 0.62]]:
		var tex: Texture2D = pair[0]
		if tex == null:
			continue
		if not _layer_imgs.has(tex):
			var im := tex.get_image()
			if im.is_compressed():
				im.decompress()
			_layer_imgs[tex] = im
		var img: Image = _layer_imgs[tex]
		var iw := img.get_width()
		var ix := int(roundf(sx + float(pair[1]) * cam_left))
		for yy in range(int(y) - 5, int(y)):
			for xx in range(ix - 3, ix + 3):
				if img.get_pixel(posmod(xx, iw), clampi(yy, 0, img.get_height() - 1)).a > 0.0:
					return false
	return true


func _play(a: Actor, anim: String, from: int = 0) -> void:
	a.anim = anim
	a.frame = from
	a.ft = 0.0
	var tex: Texture2D = TEX[anim]
	var n: int = SHEETS[anim].n
	a.sprite.texture = tex
	a.sprite.hframes = n
	a.sprite.frame = from
	var w := tex.get_width() / n
	a.sprite.offset = Vector2(-floorf(w / 2.0), -tex.get_height())


# ------------------------------------------------------------------ 每帧

func _process(delta: float) -> void:
	_clock += delta
	if auto_spawn:
		# 只在画面里什么都不动的时候数时间：两件事之间一定有一段空白
		if actors.is_empty():
			_next -= delta
		if _next <= 0.0:
			match _stage:
				0:
					spawn("deer")
					_stage = 1
					_next = rng.randf_range(first_quiet.x, first_quiet.y)
				_:
					spawn(_pick_kind())
					_next = rng.randf_range(interval.x, interval.y)
	for a in actors:
		a.age += delta
		if a.bird:
			_bird_step(a, delta)
		else:
			_ground_step(a, delta)
		if a.age > 180.0:
			a.dead = true
	var had := not actors.is_empty()
	for i in range(actors.size() - 1, -1, -1):
		if actors[i].dead:
			actors[i].sprite.queue_free()
			actors.remove_at(i)
	if _log and had and actors.is_empty():
		print("[shadows] %6.1fs  （走了）" % _clock)


## 往后走 delta，返回这次换了几帧。
func _advance(a: Actor, delta: float, loop: bool) -> int:
	var sh: Dictionary = SHEETS[a.anim]
	var n := 0
	a.ft += delta * 1000.0
	while a.ft >= sh.ms:
		a.ft -= sh.ms
		n += 1
		if loop:
			a.frame = (a.frame + 1) % int(sh.n)
		else:
			a.frame = mini(a.frame + 1, int(sh.n) - 1)
	a.sprite.frame = a.frame
	return n


func _ground_step(a: Actor, delta: float) -> void:
	if a.steps.is_empty():
		a.dead = true
		return
	var st: Dictionary = a.steps[0]
	if a.anim != st.anim:
		_play(a, st.anim, int(st.get("from", 0)))
	var end: String = st.get("end", "exit")
	var stepped := _advance(a, delta, end != "once")
	a.step_t += delta
	var sh: Dictionary = SHEETS[a.anim]
	if st.get("move", false):
		if sh.get("step", false):
			a.lx += a.facing * sh.px * stepped
		else:
			a.lx += a.facing * sh.px / (sh.ms / 1000.0) * delta
	a.sprite.flip_h = a.facing < 0
	var sx := _place(a)
	var done := false
	match end:
		"exit":
			if (a.facing > 0 and sx - a.half_w > _view_w() + 2.0) or (a.facing < 0 and sx + a.half_w < -2.0):
				a.dead = true
		"time":
			done = a.step_t >= float(st.time)
		"once":
			done = a.step_t >= sh.n * sh.ms / 1000.0 + float(st.get("hold", 0.0))
		"reach":
			done = (a.facing > 0 and sx >= float(st.reach)) or (a.facing < 0 and sx <= float(st.reach))
	if done:
		if st.get("flip", false):
			a.facing = -a.facing
		a.steps.pop_front()
		a.step_t = 0.0


func _bird_step(a: Actor, delta: float) -> void:
	match a.mode:
		"raven":
			_raven_step(a, delta)
		"perch":
			_perch_step(a, delta)
		_:
			_flock_step(a, delta)


func _flock_step(a: Actor, delta: float) -> void:
	a.t += delta
	a.sprite.visible = a.t >= 0.0
	var t := maxf(a.t, 0.0)
	var d := a.v * t
	a.lx = a.lx0 + a.facing * d
	var y: float
	if d < a.d_desc:
		y = lerpf(a.y0, a.yb, smoothstep(0.0, 1.0, d / a.d_desc))
	elif d < a.d_cruise:
		y = a.yb
	else:
		y = lerpf(a.yb, a.y_exit, smoothstep(0.0, 1.0, (d - a.d_cruise) / 150.0))
	a.y = y + a.oy + 1.5 * sin(t * 2.6 + a.phase)
	# 扇翅；偶尔滑翔一下（停在翅膀平展那帧）
	if a.glide > 0.0:
		a.glide -= delta
		a.frame = 1
		a.sprite.frame = 1
	else:
		var before := a.frame
		_advance(a, delta, true)
		if a.frame == 0 and before != 0 and rng.randf() < 0.18:
			a.glide = rng.randf_range(0.25, 0.6)
	_tint(a, a.y)
	var sx := _place(a)
	if (a.facing > 0 and sx > _view_w() + 8.0) or (a.facing < 0 and sx < -8.0):
		a.dead = true


func _raven_step(a: Actor, delta: float) -> void:
	a.t += delta
	a.lx += a.facing * a.v * delta
	if a.glide > 0.0:
		a.glide -= delta
		a.y += 7.0 * delta
		a.frame = RAVEN_FLAP_N
		a.sprite.frame = RAVEN_FLAP_N
		if a.glide <= 0.0:
			a.flaps_left = rng.randi_range(2, 4)
			_play(a, "raven_fly", 0)
	else:
		a.y -= 5.0 * delta
		var before := a.frame
		var sh: Dictionary = SHEETS["raven_fly"]
		a.ft += delta * 1000.0
		while a.ft >= sh.ms:
			a.ft -= sh.ms
			a.frame = (a.frame + 1) % RAVEN_FLAP_N
		a.sprite.frame = a.frame
		if a.frame == 0 and before != 0:
			a.flaps_left -= 1
			if a.flaps_left <= 0:
				a.glide = rng.randf_range(0.9, 1.7)
	a.y = clampf(a.y, a.y0 - 9.0, a.y0 + 9.0)
	var yy := a.y + 0.8 * sin(a.t * 1.7 + a.phase)
	var keep := a.y
	a.y = yy
	_tint(a, a.y - 6.0)
	var sx := _place(a)
	a.y = keep
	if (a.facing > 0 and sx - a.half_w > _view_w() + 2.0) or (a.facing < 0 and sx + a.half_w < -2.0):
		a.dead = true


func _perch_step(a: Actor, delta: float) -> void:
	a.t += delta
	if a.t < a.perch_t:
		# 停着：大多数时候第 0 帧，偶尔低头啄一下（1）或者抬头张望（2）
		a.idle_t -= delta
		if a.idle_t <= 0.0:
			if a.frame == 0:
				a.frame = 1 if rng.randf() < 0.5 else 2
				a.idle_t = rng.randf_range(0.25, 0.6)
			else:
				a.frame = 0
				a.idle_t = rng.randf_range(0.8, 2.4)
			if rng.randf() < 0.15:
				a.facing = -a.facing
				a.sprite.flip_h = a.facing < 0
		a.sprite.frame = a.frame
		_place(a)
		return
	# 飞走：换成小鸟群的飞法（往下掉进雾带，贴着雾带飞，再往上出画面）
	var dir := a.fly_dir
	a.mode = "flock"
	a.facing = dir
	a.sprite.flip_h = false
	_play(a, "bird_small" if rng.randf() < 0.5 else "bird_flap", rng.randi_range(0, 3))
	a.t = 0.0
	a.lx0 = a.lx
	a.v = rng.randf_range(72.0, 88.0)
	a.yb = clampf(rng.randf_range(band_y.x, band_y.y), a.y0 + 6.0, 200.0)
	a.d_desc = rng.randf_range(50.0, 80.0)
	a.d_cruise = a.d_desc + rng.randf_range(90.0, 160.0)
	a.y_exit = rng.randf_range(104.0, 128.0)
	a.oy = rng.randf_range(-3.0, 3.0)
	a.phase = rng.randf() * TAU
	_flock_step(a, 0.0)


## 按层坐标算出屏幕位置（取整到像素），再换回这一层的本地坐标。返回屏幕 x。
func _place(a: Actor) -> float:
	var sx := roundf(a.lx - a.s * _cam_left())
	var sp := Vector2(sx, roundf(a.y))
	a.sprite.position = a.layer.get_global_transform_with_canvas().affine_inverse() * sp
	return sx
