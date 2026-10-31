extends Node2D
## 芦苇地（云层星，第三章）：会弯腰的芦苇 + 惊鸟。房间 art/reed_field/room.json 的 scripts 里放这个（room_stage 建房间时 new 一个，
## 父节点就是 room_stage；坐标是房间坐标）。图和数据都是 tools/reed_field_art.py 画的。
##
## 芦苇（reeds.png + reeds.json）
## - 每种芦苇在 31 个弯曲角度下各画好一帧（ANGLES，0 附近密）。1 像素的秆是四邻接画的，弯到哪一帧都不断，不用 shader 去扭（扭会断）。
## - 每一根有自己的角度 θ 和角速度 ω，每帧按弹簧阻尼往「目标角度」靠：θ'' = k (目标 − θ) − c θ'。画的时候挑最近的那一帧。
##   目标 = 风（一阵阵往右推过去的风 + 每根自己的小颤）+ 晨推的（离晨越近越大，平滑衰减）。
##   被推的时候硬一点（跟得上晨），放开以后软一点、阻尼小一点：慢慢弹回来，过头一两下再停（STIFF / DAMP / STIFF_BACK / DAMP_BACK）。
## - 推的方向：晨在走 = 顺着她走的方向（她走过去把芦苇往前带倒，走过以后芦苇弹回来）；站着不动 = 往两边分开。
## - 四排：r0 后排高的（只轻轻让一点）、r1 路后、r2 路前（在晨前面）、f 前景（scroll 1.25，在屏幕上和晨重叠时往两边倒开，不挡人）。
##   远景（far / mid 层）不在这里，是 room.json 里的 sway shader 随风轻摆。
## - 只算镜头附近的（左右各多算 SIM_MARGIN）：同时在算的一两百根，GDScript 也就零点几毫秒；画是每根一次 draw_texture_rect_region，
##   同一张图会合批，手机上也便宜。
##
## 鸟（birds.png + birds.json）
## - 每处（spots：[[房间 x, 几只], …]）一开始有 3–7 只歇在那附近的芦苇穗顶上（跟着芦苇一起摆；隔一会儿低一下头）。
## - 晨走到 FLUSH_DIST 以内：整群惊起，一只接一只（错开一点点）扑腾着往远离晨的一边斜着飞上天，路线是三次贝塞尔曲线，
##   越飞越远：换小一号的图（四种大小）、视差从 1 慢慢变成 0.35（像飞到远处去了），最后飞出屏幕上沿。起飞时把脚下那根芦苇蹬一下（ω）。
## - 飞走以后过 REST_MIN–REST_MAX 秒、晨又不在附近（RETURN_DIST 以外），新的一群（3–7 只）从天上滑翔下来，落回那附近的穗顶。
## - 扇翅 100ms 一帧（上、平、下、平），飞远了扇几下滑一下；歇着的低头也是 100ms 一帧。
##
## 晨在浅水里的倒影（第二版，作者要「清澈透明甚至反光的河」）
## - 晨站在 water 段（room.json params，[[x0, x1], …]，画图脚本按水塘的真形状算的）里时，脚下画她这一帧的上下翻转：
##   同一张图集、同一帧、同一个左右朝向，帧换了倒影跟着换。染一点水色（REFL_TINT），半透明（REFL_ALPHA，离脚远的一半再淡一档），
##   每行左右晃 0–REFL_WOBBLE 像素（整像素，离脚越远晃得越多）。z 在 main 前、晨和脚踝的水面（ankle_water，z 21）后。
##   水段两头 REFL_EDGE 像素里淡进淡出。
## 晨身后压暗（「亮主角暗背景」：整张图很亮，晨周围压一点）
## - 以晨的身体中间为圆心，几圈很淡的正片叠底（SHADE_RINGS，最里面 ×0.955），z −2：只压晨身后的东西，不压晨、不压脚踝那层。
##   一圈圈是整像素的横条拼的（硬边）。觉得看得出圈就把 SHADE_RINGS 调淡或者 SHADE_ON = false。

const ANG_RANGE := 80
## 每排：视差、晨推的半径（像素）、最多弯几度、风的大小（倍）、z（绝对；晨是 0，main 层大约 −92）
const ROWS := {
	"r0": {"scroll": 1.0, "radius": 12.0, "bend": 26.0, "wind": 1.25, "z": -40},
	"r1": {"scroll": 1.0, "radius": 17.0, "bend": 64.0, "wind": 1.0, "z": -30},
	"r2": {"scroll": 1.0, "radius": 16.0, "bend": 70.0, "wind": 0.7, "z": 5},
	"f": {"scroll": 1.25, "radius": 26.0, "bend": 54.0, "wind": 0.8, "z": 110},
}
const BIRD_Z := -29                 # 在 r1 前面（歇在穗顶上的不会被穗盖住）、晨后面

# ---- 倒影
const REFL_Z := -3
const REFL_ALPHA := 0.42
const REFL_TINT := Color(0.77, 0.89, 0.96)  # 水色
const REFL_TINT_AMT := 0.45
const REFL_WOBBLE := 1.5            # 离脚最远的那一行最多晃几像素
const REFL_EDGE := 14.0             # 水段两头淡进淡出多宽

# ---- 晨身后压暗
const SHADE_ON := true
const SHADE_Z := -2
const SHADE_DY := -24               # 圆心在脚底往上多少（身体中间）
const SHADE_RINGS := [[Vector2(44, 54), 0.99], [Vector2(35, 45), 0.98], [Vector2(27, 36), 0.97], [Vector2(20, 28), 0.962],
	[Vector2(13, 21), 0.955]]       # [半径, 这一圈以内一共乘多少]（从外到里）

# ---- 弯腰（都可以调）
const STIFF := 70.0                 # 被推 / 被风吹时的弹簧硬度（越大越跟手）
const DAMP := 9.0                   # 被推时的阻尼
const STIFF_BACK := 26.0            # 放开以后弹回来的硬度（越小回得越慢）
const DAMP_BACK := 3.2              # 放开以后的阻尼（越小来回晃得越多；临界阻尼约 2√STIFF_BACK ≈ 10）
const AHEAD := 1.35                 # 走路时前方的推的范围放大几倍（芦苇在她走到之前就开始让）
const MOVE_V := 28.0                # 走多快（像素 / 秒）算「在走」（推的方向完全顺着走向）
const SIM_MARGIN := 140.0           # 屏幕外左右各多算这么宽

# ---- 风（度）
const WIND_BASE := 2.5              # 平时往右偏
const WIND_GUST := 6.0              # 一阵风最多再推几度
const GUST_SPEED := 0.55            # 风一阵阵过来的快慢
const GUST_LEN := 260.0             # 一阵风在地上有多宽（像素，越大越整片一起动）
const FLUTTER := 1.4                # 每根自己的小颤
const FLUTTER_SPEED := 1.9

# ---- 鸟
const FLUSH_DIST := 58.0            # 晨离这处多近就惊起
const RETURN_DIST := 170.0          # 晨离开多远以后才会有新的落回来
const REST_MIN := 22.0              # 飞走以后最少过几秒才回来
const REST_MAX := 40.0
const FLY_TIME := Vector2(3.0, 4.2)         # 飞走用几秒（每只随机）
const LAND_TIME := Vector2(4.0, 5.0)        # 落回来用几秒
const PERCH_SPREAD := 40.0          # 歇在这处左右多宽里的穗顶上
const FRAME_MS := 100.0
const KICK := 90.0                  # 起飞蹬芦苇一下（度 / 秒）

var data := "res://art/reed_field/reeds.json"
var birds := "res://art/reed_field/birds.json"
var spots: Array = []               # [[x, 几只], …]（room.json 的 params）
var water: Array = []               # [[x0, x1], …] 路泡在水里的段（room.json 的 params）

var _tex: Texture2D
var _btex: Texture2D
var _angles: PackedFloat32Array
var _lut := PackedInt32Array()      # 角度（整数度 + ANG_RANGE）→ 帧号
var _vars := {}                     # 种类名 → {"src": [Rect2…], "off": [Vector2…], "tip": [Vector2…]}
var _rows := {}                     # 排名 → {"x", "y", "th", "om", "ph", "rest", "v": Array（种类 dict）, "kick"}
var _painters := {}                 # 排名 → 画这一排的 Node2D
var _bird_node: Node2D
var _bcell := Vector2i(10, 6)
var _bsizes: Array = []             # [[up, mid, down] × 4]
var _bperch: Array = []
var _spots: Array = []              # 每处的状态
var _t := 0.0
var _cl := 0.0                      # 镜头左边缘（房间 x）
var _cx := -9999.0                  # 晨（房间 x）
var _vx := 0.0                      # 晨的横向速度（平滑过）
var _have_chen := false
var _rng := RandomNumberGenerator.new()
var _ok := false
var _refl: Sprite2D
var _refl_mat: ShaderMaterial
var _shade: Node2D
var _chen_node: Node2D

const REFL_SHADER := """
shader_type canvas_item;
render_mode unshaded;
uniform vec4 tint : source_color;
uniform float tint_amt = 0.45;
uniform float alpha = 0.4;
uniform float wobble = 1.5;
uniform float y0 = 0.0;      // 这一帧在图集里的上沿（uv）
uniform float hh = 1.0;      // 这一帧的高（uv）
void fragment() {
	float d = clamp((UV.y - y0) / hh, 0.0, 1.0);          // 0 = 头顶，1 = 脚
	float far = 1.0 - d;                                  // 倒影里离脚多远
	float px = floor((UV.y - y0) / TEXTURE_PIXEL_SIZE.y);
	float off = round(wobble * far * sin(TIME * 2.3 + px * 0.7));
	vec4 c = texture(TEXTURE, UV + vec2(off * TEXTURE_PIXEL_SIZE.x, 0.0));
	if (c.a < 0.5) {
		discard;
	}
	COLOR = vec4(mix(c.rgb, tint.rgb, tint_amt), alpha * (far > 0.5 ? 0.6 : 1.0));
}
"""


class Painter extends Node2D:
	var fn: Callable

	func _draw() -> void:
		fn.call(self)


func _ready() -> void:
	_rng.seed = 20261031
	if not _load():
		push_warning("reed_field: 读不到 %s / %s" % [data, birds])
		return
	for r in ROWS:
		var p := Painter.new()
		p.name = "Reeds_" + str(r)
		p.z_as_relative = false
		p.z_index = int(ROWS[r]["z"])
		p.fn = _paint_row.bind(str(r))
		p.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		add_child(p)
		_painters[r] = p
	_bird_node = Painter.new()
	_bird_node.name = "Birds"
	_bird_node.z_as_relative = false
	_bird_node.z_index = BIRD_Z
	_bird_node.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	(_bird_node as Painter).fn = _paint_birds
	add_child(_bird_node)
	_refl = Sprite2D.new()
	_refl.name = "ChenReflection"
	_refl.centered = false
	_refl.flip_v = true
	_refl.z_as_relative = false
	_refl.z_index = REFL_Z
	_refl.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_refl.visible = false
	var sh := Shader.new()
	sh.code = REFL_SHADER
	_refl_mat = ShaderMaterial.new()
	_refl_mat.shader = sh
	_refl_mat.set_shader_parameter("tint", REFL_TINT)
	_refl_mat.set_shader_parameter("tint_amt", REFL_TINT_AMT)
	_refl_mat.set_shader_parameter("wobble", REFL_WOBBLE)
	_refl.material = _refl_mat
	add_child(_refl)
	_shade = Painter.new()
	_shade.name = "ChenShade"
	_shade.z_as_relative = false
	_shade.z_index = SHADE_Z
	var mm := CanvasItemMaterial.new()
	mm.blend_mode = CanvasItemMaterial.BLEND_MODE_MUL
	_shade.material = mm
	(_shade as Painter).fn = _paint_shade
	_shade.visible = false
	add_child(_shade)
	for sp in spots:
		if sp is Array and sp.size() >= 1:
			var n := int(sp[1]) if sp.size() > 1 else 5
			_spots.append({"x": float(sp[0]), "state": "sit", "t": 0.0, "birds": [], "n": clampi(n, 3, 7)})
	_ok = true


# ======================================================================= 读数据
func _load() -> bool:
	if not FileAccess.file_exists(data) or not FileAccess.file_exists(birds):
		return false
	var d = JSON.parse_string(FileAccess.get_file_as_string(data))
	var b = JSON.parse_string(FileAccess.get_file_as_string(birds))
	if not d is Dictionary or not b is Dictionary:
		return false
	_tex = _load_tex(data.get_base_dir().path_join("reeds.png"))
	_btex = _load_tex(birds.get_base_dir().path_join("birds.png"))
	if _tex == null or _btex == null:
		return false
	_angles = PackedFloat32Array(d["angles"])
	_lut.resize(ANG_RANGE * 2 + 1)
	for a in range(-ANG_RANGE, ANG_RANGE + 1):
		var best := 0
		for i in _angles.size():
			if absf(_angles[i] - a) < absf(_angles[best] - a):
				best = i
		_lut[a + ANG_RANGE] = best
	for vn in d["variants"]:
		var v: Dictionary = d["variants"][vn]
		var src: Array[Rect2] = []
		var off: Array[Vector2] = []
		var tip: Array[Vector2] = []
		for f in v["frames"]:
			src.append(Rect2(f[0], f[1], f[2], f[3]))
			off.append(Vector2(f[4], f[5]))
			tip.append(Vector2(f[6], f[7]))
		_vars[vn] = {"src": src, "off": off, "tip": tip, "rest": float(v.get("rest", 0.0))}
	for r in ROWS:
		var list: Array = d["rows"].get(r, [])
		var xs := PackedFloat32Array()
		var ys := PackedFloat32Array()
		var ph := PackedFloat32Array()
		var rest := PackedFloat32Array()
		var vs: Array = []
		for e in list:
			if not _vars.has(str(e[2])):
				continue
			xs.append(float(e[0]))
			ys.append(float(e[1]))
			ph.append(float(e[3]))
			rest.append(float(_vars[str(e[2])]["rest"]))
			vs.append(_vars[str(e[2])])
		var th := PackedFloat32Array()
		th.resize(xs.size())
		var om := PackedFloat32Array()
		om.resize(xs.size())
		for i in xs.size():
			th[i] = WIND_BASE + rest[i]
		_rows[r] = {"x": xs, "y": ys, "th": th, "om": om, "ph": ph, "rest": rest, "v": vs}
	_bcell = Vector2i(int(b["cell"][0]), int(b["cell"][1]))
	for s in range(4):
		_bsizes.append(b["sizes"][str(s)])
	_bperch = b["perch"]
	return true


## 导入过的用 load；没导入的新图（开发时刚画完）直接从文件读
func _load_tex(p: String) -> Texture2D:
	if ResourceLoader.exists(p):
		return load(p)
	if FileAccess.file_exists(p):
		var img := Image.load_from_file(ProjectSettings.globalize_path(p))
		if img != null:
			return ImageTexture.create_from_image(img)
	return null


# ======================================================================= 每帧
func _process(delta: float) -> void:
	if not _ok or not is_visible_in_tree():
		return
	var dt := minf(delta, 0.05)
	_t += dt
	var stage := get_parent()
	var org: Vector2 = stage.get("origin") if stage != null and stage.get("origin") is Vector2 else Vector2.ZERO
	var cam := get_viewport().get_camera_2d()
	if cam != null:
		_cl = roundf(cam.get_screen_center_position().x - 240.0 - org.x)
	_have_chen = false
	var world = stage.get("world") if stage != null else null
	if world != null and world.get("chen") != null:
		var chen: Node2D = world.chen
		var here: bool = str(world.get("room")) == str(stage.get("id")) and chen.visible
		if here:
			var nx := chen.position.x - org.x
			if _cx > -9000.0 and dt > 0.0:
				_vx = lerpf(_vx, (nx - _cx) / dt, minf(1.0, dt * 10.0))
			_cx = nx
			_have_chen = true
			_chen_node = chen
	if not _have_chen:
		_vx = 0.0
	for r in ROWS:
		_step_row(str(r), dt)
		var p: Node2D = _painters[r]
		var sc: float = ROWS[r]["scroll"]
		p.position.x = roundf(_cl * (1.0 - sc))          # 层坐标 → 房间坐标（和 room_stage 的视差层一个算法）
		p.queue_redraw()
	_step_birds(dt)
	_bird_node.queue_redraw()
	_update_reflection(org)
	_shade.visible = SHADE_ON and _have_chen
	if _shade.visible:
		_shade.global_position = (_chen_node.global_position + Vector2(0, SHADE_DY)).round()


# ======================================================================= 倒影、身后压暗
## 这一点在不在水段里：1 = 在，两头 REFL_EDGE 像素里从 0 渐到 1
func _water_amt(x: float) -> float:
	var best := 0.0
	for seg in water:
		if seg is Array and seg.size() >= 2:
			var a := float(seg[0])
			var b := float(seg[1])
			best = maxf(best, clampf(minf(x - a, b - x) / REFL_EDGE, 0.0, 1.0))
	return best


func _update_reflection(_org: Vector2) -> void:
	var amt := _water_amt(_cx) if _have_chen else 0.0
	if amt <= 0.0 or _chen_node == null:
		_refl.visible = false
		return
	var spr = _chen_node.get("spr")
	if not spr is AnimatedSprite2D:
		_refl.visible = false
		return
	var a := spr as AnimatedSprite2D
	if a.sprite_frames == null or not a.visible:
		_refl.visible = false
		return
	var tex := a.sprite_frames.get_frame_texture(a.animation, a.frame)
	if tex == null:
		_refl.visible = false
		return
	_refl.texture = tex
	_refl.flip_h = a.flip_h
	var h := float(tex.get_height())
	# 原图：offset.y = −(脚那一行 + 1)，脚那一行画在脚底上面一行；翻过来以后脚那一行正好在脚底这一行
	_refl.offset = Vector2(a.offset.x, -a.offset.y - h)
	_refl.global_position = (_chen_node.global_position + a.position).round()
	var y0 := 0.0
	var hh := 1.0
	if tex is AtlasTexture:
		var at := tex as AtlasTexture
		var full := at.atlas.get_size()
		y0 = at.region.position.y / full.y
		hh = at.region.size.y / full.y
	_refl_mat.set_shader_parameter("y0", y0)
	_refl_mat.set_shader_parameter("hh", hh)
	_refl_mat.set_shader_parameter("alpha", REFL_ALPHA * amt)
	_refl.visible = true


## 一圈圈从外到里画（正片叠底会叠乘）：每圈的颜色 = 这圈的总乘数 ÷ 外面一圈的
func _paint_shade(p: Node2D) -> void:
	var prev := 1.0
	for r in SHADE_RINGS:
		var rad: Vector2 = r[0]
		var k := float(r[1])
		var f := k / prev
		prev = k
		var c := Color(f, f, f, 1.0)
		var ry := int(rad.y)
		for y in range(-ry, ry + 1):
			var t := float(y) / rad.y
			var hw := roundf(rad.x * sqrt(maxf(0.0, 1.0 - t * t)))
			p.draw_rect(Rect2(-hw, y, hw * 2.0 + 1.0, 1.0), c)


## 一排：镜头附近的每一根往目标角度靠（弹簧阻尼）
func _step_row(r: String, dt: float) -> void:
	var R: Dictionary = _rows[r]
	var cfg: Dictionary = ROWS[r]
	var xs: PackedFloat32Array = R["x"]
	var th: PackedFloat32Array = R["th"]
	var om: PackedFloat32Array = R["om"]
	var ph: PackedFloat32Array = R["ph"]
	var rest: PackedFloat32Array = R["rest"]
	var sc: float = cfg["scroll"]
	var rad: float = cfg["radius"]
	var bend: float = cfg["bend"]
	var wk: float = cfg["wind"]
	var lo := _cl * sc - SIM_MARGIN
	var hi := _cl * sc + 480.0 + SIM_MARGIN
	var i0 := xs.bsearch(lo)
	var moving := clampf(absf(_vx) / MOVE_V, 0.0, 1.0)
	var vdir := signf(_vx)
	# 晨在这一排的坐标里在哪（前景 f 按屏幕上重叠算：她在屏幕上的 x 换算到这一层）
	var cx := _cx if sc == 1.0 else _cx - _cl + _cl * sc
	for i in range(i0, xs.size()):
		var x := xs[i]
		if x > hi:
			break
		var gust := 0.5 + 0.5 * sin(_t * GUST_SPEED * TAU * 0.25 - x / GUST_LEN * TAU)
		var target := (WIND_BASE + WIND_GUST * gust * gust) * wk + FLUTTER * wk * sin(_t * FLUTTER_SPEED + ph[i]) + rest[i]
		if _have_chen:
			var dx := x - cx
			var reach := rad * (AHEAD if moving > 0.3 and signf(dx) == vdir else 1.0)
			var f := clampf(1.0 - absf(dx) / reach, 0.0, 1.0)
			if f > 0.0:
				f = f * f * (3.0 - 2.0 * f)
				var d := moving * vdir + (1.0 - moving) * signf(dx)
				target += bend * f * d
		var k := STIFF
		var c := DAMP
		if absf(target) < absf(th[i]) - 0.5:
			k = STIFF_BACK
			c = DAMP_BACK
		# 半隐式欧拉，步长太大就拆两步
		var n := 2 if dt > 0.025 else 1
		var h := dt / n
		for s in n:
			om[i] += (k * (target - th[i]) - c * om[i]) * h
			th[i] += om[i] * h
		th[i] = clampf(th[i], -ANG_RANGE, ANG_RANGE)
	R["th"] = th
	R["om"] = om


func _frame_of(theta: float) -> int:
	return _lut[clampi(int(roundf(theta)), -ANG_RANGE, ANG_RANGE) + ANG_RANGE]


func _paint_row(p: Node2D, r: String) -> void:
	var R: Dictionary = _rows[r]
	var xs: PackedFloat32Array = R["x"]
	var ys: PackedFloat32Array = R["y"]
	var th: PackedFloat32Array = R["th"]
	var vs: Array = R["v"]
	var sc: float = ROWS[r]["scroll"]
	var lo := _cl * sc - 100.0
	var hi := _cl * sc + 580.0
	for i in range(xs.bsearch(lo), xs.size()):
		if xs[i] > hi:
			break
		var v: Dictionary = vs[i]
		var fi := _frame_of(th[i])
		var src: Rect2 = v["src"][fi]
		var off: Vector2 = v["off"][fi]
		p.draw_texture_rect_region(_tex, Rect2(Vector2(xs[i], ys[i]) + off, src.size), src)


## 第 r 排第 i 根现在的穗顶（房间坐标；只给 scroll 1 的排用）
func _tip(r: String, i: int) -> Vector2:
	var R: Dictionary = _rows[r]
	var v: Dictionary = R["v"][i]
	return Vector2(R["x"][i], R["y"][i]) + v["tip"][_frame_of(R["th"][i])]


# ======================================================================= 鸟
func _step_birds(dt: float) -> void:
	for sp in _spots:
		var birds_now: Array = sp["birds"]
		match str(sp["state"]):
			"sit":
				if birds_now.is_empty():
					_perch_all(sp)
				if _have_chen and absf(_cx - float(sp["x"])) < FLUSH_DIST:
					_flush(sp)
			"gone":
				sp["t"] = float(sp["t"]) - dt
				var flying := false
				for b in birds_now:
					if float(b["u"]) < 1.0:
						flying = true
				if not flying:
					birds_now.clear()
				if float(sp["t"]) <= 0.0 and not flying and (not _have_chen or absf(_cx - float(sp["x"])) > RETURN_DIST):
					_land(sp)
			"land":
				var all_in := true
				for b in birds_now:
					if float(b["u"]) < 1.0:
						all_in = false
				if all_in:
					for b in birds_now:
						b["mode"] = "perch"
					sp["state"] = "sit"
				elif _have_chen and absf(_cx - float(sp["x"])) < FLUSH_DIST * 0.8:
					_flush(sp)                  # 还没落稳晨就来了：再惊起来
		for b in birds_now:
			_bird_tick(b, dt)


## 挑这处附近 n 根穗顶（r0、r1，彼此隔开一点），每只鸟歇一根
func _perch_targets(sp: Dictionary, n: int) -> Array:
	var cands: Array = []
	for r in ["r0", "r1"]:
		var xs: PackedFloat32Array = _rows[r]["x"]
		for i in range(xs.bsearch(float(sp["x"]) - PERCH_SPREAD), xs.size()):
			if xs[i] > float(sp["x"]) + PERCH_SPREAD:
				break
			cands.append([r, i, xs[i]])
	cands.shuffle()
	var out: Array = []
	for c in cands:
		var ok := true
		for o in out:
			if absf(float(o[2]) - float(c[2])) < 7.0:
				ok = false
				break
		if ok:
			out.append(c)
		if out.size() >= n:
			break
	return out


func _new_bird(r: String, i: int) -> Dictionary:
	return {"r": r, "i": i, "mode": "perch", "u": 1.0, "dur": 1.0, "delay": 0.0, "ft": _rng.randf() * 10.0,
		"bob": _rng.randf_range(0.5, 3.0), "face": 1 if _rng.randf() < 0.6 else -1, "ph": _rng.randf() * TAU,
		"p0": Vector2.ZERO, "p1": Vector2.ZERO, "p2": Vector2.ZERO, "p3": Vector2.ZERO}


func _perch_all(sp: Dictionary) -> void:
	var list: Array = sp["birds"]
	for t in _perch_targets(sp, int(sp["n"])):
		list.append(_new_bird(str(t[0]), int(t[1])))


## 惊起：一只接一只，往远离晨的那边斜着飞上去
func _flush(sp: Dictionary) -> void:
	var dir := signf(float(sp["x"]) - _cx) if _have_chen else (1.0 if _rng.randf() < 0.5 else -1.0)
	if dir == 0.0:
		dir = 1.0
	var k := 0
	for b in sp["birds"]:
		var p0: Vector2 = _bird_pos(b)
		if str(b["mode"]) == "perch":
			var om: PackedFloat32Array = _rows[str(b["r"])]["om"]
			om[int(b["i"])] += KICK * (-dir)    # 蹬一下：芦苇往反方向弹
			_rows[str(b["r"])]["om"] = om
		b["mode"] = "fly"
		b["u"] = 0.0
		b["dur"] = _rng.randf_range(FLY_TIME.x, FLY_TIME.y)
		b["delay"] = k * 0.07 + _rng.randf_range(0.0, 0.22)
		b["p0"] = p0
		b["p1"] = p0 + Vector2(dir * _rng.randf_range(8, 28), -_rng.randf_range(40, 70))
		b["p2"] = Vector2(p0.x + dir * _rng.randf_range(70, 150), _rng.randf_range(40, 80))
		b["p3"] = Vector2(p0.x + dir * _rng.randf_range(170, 300), -_rng.randf_range(30, 70))
		k += 1
	sp["state"] = "gone"
	sp["t"] = _rng.randf_range(REST_MIN, REST_MAX)


## 落回来：新的一群（3–7 只）从天上滑翔下来，落到穗顶上
func _land(sp: Dictionary) -> void:
	var list: Array = sp["birds"]
	list.clear()
	var from := 1.0 if _rng.randf() < 0.5 else -1.0
	var k := 0
	for t in _perch_targets(sp, _rng.randi_range(3, 7)):
		var b := _new_bird(str(t[0]), int(t[1]))
		var end := _tip(str(t[0]), int(t[1]))
		b["mode"] = "land"
		b["u"] = 0.0
		b["dur"] = _rng.randf_range(LAND_TIME.x, LAND_TIME.y)
		b["delay"] = k * 0.12 + _rng.randf_range(0.0, 0.3)
		b["face"] = int(-from)
		b["p0"] = Vector2(end.x + from * _rng.randf_range(180, 300), -_rng.randf_range(30, 60))
		b["p1"] = Vector2(end.x + from * _rng.randf_range(100, 160), _rng.randf_range(30, 70))
		b["p2"] = end + Vector2(from * _rng.randf_range(16, 34), -_rng.randf_range(30, 50))
		list.append(b)
		k += 1
	sp["state"] = "land" if not list.is_empty() else "sit"


func _bird_tick(b: Dictionary, dt: float) -> void:
	b["ft"] = float(b["ft"]) + dt
	if str(b["mode"]) == "perch":
		return
	if float(b["delay"]) > 0.0:
		b["delay"] = float(b["delay"]) - dt
		return
	b["u"] = minf(1.0, float(b["u"]) + dt / float(b["dur"]))


## 鸟现在在哪（房间坐标；飞着的还没加视差）
func _bird_pos(b: Dictionary) -> Vector2:
	var mode := str(b["mode"])
	if mode == "perch":
		return _tip(str(b["r"]), int(b["i"]))
	var u := float(b["u"])
	var p3: Vector2 = b["p3"]
	var e := u
	if mode == "fly":
		e = 1.0 - pow(1.0 - u, 1.7)                   # 起飞一下子窜出去，后面匀下来
	else:
		e = u * u * (3.0 - 2.0 * u)                   # 落：缓进缓停
		p3 = _tip(str(b["r"]), int(b["i"]))           # 落点跟着芦苇摆
	var a: Vector2 = b["p0"]
	var p1: Vector2 = b["p1"]
	var p2: Vector2 = b["p2"]
	var q := a.bezier_interpolate(p1, p2, p3, e)
	# 扑腾：垂直于前进方向晃一点（落地前收住）
	var amp := 1.6 * (1.0 - e if mode == "land" else 1.0)
	q.y += sin(float(b["ft"]) * 9.0 + float(b["ph"])) * amp
	return q


## 远近：0 = 近（大）… 3 = 远（小）。飞走越飞越远，落回来反过来
func _bird_far(b: Dictionary) -> float:
	var mode := str(b["mode"])
	if mode == "perch":
		return 0.0
	var u := float(b["u"])
	if mode == "land":
		u = 1.0 - u * u * (3.0 - 2.0 * u)
	else:
		u = 1.0 - pow(1.0 - u, 1.7)
	return u


func _paint_birds(p: Node2D) -> void:
	for sp in _spots:
		for b in sp["birds"]:
			if str(b["mode"]) == "land" and float(b["u"]) <= 0.0:
				continue                                   # 还没出发的（在天上画面外）不画
			var pos := _bird_pos(b)
			var far := _bird_far(b)
			var fr := 0
			if str(b["mode"]) == "perch":
				# 歇着：大多时候不动，隔几秒低一下头（两帧，100ms 一帧）
				var cyc := fmod(float(b["ft"]), float(b["bob"]) + 2.0)
				fr = int(_bperch[1]) if cyc < 0.3 else int(_bperch[0])
				_blit_bird(p, fr, pos + Vector2(0, 1), int(b["face"]), true)
				continue
			var size := clampi(int(far * 4.0), 0, 3)
			var seq: Array = _bsizes[size]               # [up, mid, down]
			var n := int(float(b["ft"]) * 1000.0 / FRAME_MS)
			var cyc4 := [0, 1, 2, 1]
			var idx: int = cyc4[n % 4]
			var beat := floori(n / 4.0)
			if (far > 0.55 and beat % 3 == 2) or (str(b["mode"]) == "land" and far > 0.3 and beat % 2 == 1):
				idx = 1                                   # 远了扇几下滑一下；落下来时多滑翔
			fr = int(seq[idx])
			var sc := lerpf(1.0, 0.35, far)              # 视差：飞远了跟着远景慢慢动
			pos.x += _cl * (1.0 - sc)
			_blit_bird(p, fr, pos, 1, false)


## foot = true：pos 是脚（格子底边中间，压在穗顶那一格上）；false：pos 是身体中心
func _blit_bird(p: Node2D, fr: int, pos: Vector2, face: int, foot: bool) -> void:
	var cw := _bcell.x
	var ch := _bcell.y
	var src := Rect2(fr * cw, 0, cw, ch)
	var tl := Vector2(roundf(pos.x) - floorf(cw / 2.0), roundf(pos.y) - (ch - 1.0 if foot else floorf(ch / 2.0)))
	if face < 0:
		p.draw_set_transform(Vector2(tl.x + cw, tl.y), 0.0, Vector2(-1, 1))
		p.draw_texture_rect_region(_btex, Rect2(Vector2.ZERO, Vector2(cw, ch)), src)
		p.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	else:
		p.draw_texture_rect_region(_btex, Rect2(tl, Vector2(cw, ch)), src)
