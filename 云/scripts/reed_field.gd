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
##
## 一片生机（第五版：湿地草地）
## - 蒲公英的绒毛（seeds：[[层 x, 层 y, scroll, 半径], …]，每株巨大蒲公英一个）：隔 SEED_EVERY 秒从球的右上边上被风吹走一颗，
##   往右上慢慢飘（匀速 + 两道很慢的正弦，平滑），飘 SEED_LIFE 秒或者出了画面就没了。小降落伞两帧（100ms 一帧，[0,0,1,1] 一轮），
##   跟着那株蒲公英的视差走。镜头附近的蒲公英才吹。
## - 草上的小飞虫 / 光点（motes：锚点）：每个绕着自己的锚点慢慢飘（几道慢正弦叠起来），亮暗慢慢换（两档颜色），一像素。只画镜头里的。
## - 水面涟漪（ripples：水里的点）：隔 RIPPLE_EVERY 秒在镜头里的某个点泛一圈扁椭圆（一像素的连续细线、四邻接），慢慢变大、变淡、没了；
##   晨在水里走的时候，脚下也隔 RIPPLE_STEP 秒泛一圈。

const ANG_RANGE := 80
## 每排：视差、晨推的半径（像素）、最多弯几度、风的大小（倍）、z（绝对；晨是 0，main 层大约 −92）
## 第六版：草丛为主（g0 小洲上、g1 路后面、g2 路前面、gf 前景 scroll 1.3），芦苇零星几簇（r0 / r1 / r2）。
## 草丛的帧也是 31 个角度（画图脚本里 ±40° 以外按 ±40° 画，草不会倒平），一样按弹簧阻尼挑帧：被晨压下去、再软软地弹回来。
const ROWS := {
	"r0": {"scroll": 1.0, "radius": 12.0, "bend": 26.0, "wind": 1.25, "z": -40},
	"g0": {"scroll": 1.0, "radius": 12.0, "bend": 18.0, "wind": 0.45, "z": -38},
	"r1": {"scroll": 1.0, "radius": 17.0, "bend": 64.0, "wind": 1.0, "z": -30},
	"g1": {"scroll": 1.0, "radius": 24.0, "bend": 38.0, "wind": 0.45, "z": -28},
	"r2": {"scroll": 1.0, "radius": 16.0, "bend": 70.0, "wind": 0.7, "z": 5},
	"g2": {"scroll": 1.0, "radius": 22.0, "bend": 38.0, "wind": 0.4, "z": 6},
	"gf": {"scroll": 1.3, "radius": 34.0, "bend": 30.0, "wind": 0.35, "z": 115},
}
const BIRD_Z := -29                 # 在 r1 前面（歇在穗顶上的不会被穗盖住）、晨后面

# ---- 倒影
const REFL_Z := -3
const REFL_ALPHA := 0.42
const REFL_TINT := Color(0.69, 0.86, 0.80)  # 水色（第五版：带一点青绿，和水一样）
const REFL_TINT_AMT := 0.45
const REFL_WOBBLE := 1.5            # 离脚最远的那一行最多晃几像素
const REFL_EDGE := 14.0             # 水段两头淡进淡出多宽

# ---- 晨身后压暗
const SHADE_ON := true
const SHADE_Z := -2
const SHADE_DY := -24               # 圆心在脚底往上多少（身体中间）
# ---- 绒毛、飞虫、涟漪
const LIFE_Z := -24                 # 飞虫：晨后面、芦苇根的草团前面
const SEED_Z := -50                 # 绒毛：远处的天上
const RIPPLE_Z := -4                # 涟漪：水面上、倒影前面、晨后面
const SEED_EVERY := Vector2(2.5, 6.0)
const SEED_LIFE := Vector2(12.0, 18.0)
const SEED_V := Vector2(10.0, 3.2)  # 往右、往上飘多快（像素 / 秒，那株蒲公英那一层的坐标）
const SEED_C := Color("#fffef6")
const SEED_STEM_C := Color("#fde67a")
const MOTE_C := [Color("#fffbe6"), Color("#fde88f")]
const RIPPLE_EVERY := Vector2(1.2, 3.0)
const RIPPLE_LIFE := 1.6
const RIPPLE_R := 9.0               # 最大半宽（像素）
const RIPPLE_STEP := 0.5            # 晨在水里走：脚下隔几秒一圈
const RIPPLE_C := [Color("#fffef6"), Color("#d6eee2")]
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
var seeds: Array = []               # [[层 x, 层 y, scroll, 半径], …] 巨大蒲公英的球（room.json 的 params）
var ripples: Array = []             # [[x, y], …] 水面会泛涟漪的点（房间坐标）
var motes: Array = []               # [[x, y], …] 小飞虫的锚点（房间坐标）

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
var _seed_state: Array = []         # 每株：下一颗什么时候吹
var _seed_list: Array = []          # 飘着的：{e, x0, y0, t, life, ph}
var _mote_ph: Array = []
var _rip_list: Array = []           # {x, y, t}
var _rip_wait := 1.0
var _step_rip := 0.0
var _ring_cache := {}
var _life_node: Node2D
var _seed_node: Node2D
var _rip_node: Node2D

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
	_life_node = _make_painter("Motes", LIFE_Z, _paint_motes)
	_seed_node = _make_painter("Seeds", SEED_Z, _paint_seeds)
	_rip_node = _make_painter("Ripples", RIPPLE_Z, _paint_ripples)
	for _e in seeds:
		_seed_state.append(_rng.randf_range(0.5, SEED_EVERY.y))
	for m in motes:
		_mote_ph.append([_rng.randf() * TAU, _rng.randf() * TAU, _rng.randf() * TAU, _rng.randf() * TAU,
			_rng.randf_range(0.25, 0.5), _rng.randf_range(0.5, 0.9), _rng.randf_range(0.3, 0.6), _rng.randf_range(0.6, 1.4)])
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
			rest.append(float(_vars[str(e[2])]["rest"]) + (float(e[4]) if e.size() > 4 else 0.0))   # 每根自己的斜度
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
	_step_life(dt)
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
	for r in ["r0", "r1", "g1"]:                    # 第七版：草丛顶上也能歇
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


# ======================================================================= 绒毛、飞虫、涟漪
func _make_painter(nm: String, z: int, fn: Callable) -> Node2D:
	var p := Painter.new()
	p.name = nm
	p.z_as_relative = false
	p.z_index = z
	p.fn = fn
	add_child(p)
	return p


func _step_life(dt: float) -> void:
	# 绒毛：镜头附近的蒲公英隔一会儿吹走一颗
	for i in seeds.size():
		var e: Array = seeds[i]
		var sx := float(e[0]) - _cl * float(e[2])
		_seed_state[i] = float(_seed_state[i]) - dt
		if float(_seed_state[i]) <= 0.0:
			_seed_state[i] = _rng.randf_range(SEED_EVERY.x, SEED_EVERY.y)
			if sx > -60.0 and sx < 540.0:
				var r := float(e[3])
				var a := _rng.randf_range(-1.2, -0.2)            # 球的右上边
				_seed_list.append({"e": i, "x0": float(e[0]) + cos(a) * r * 0.9, "y0": float(e[1]) + sin(a) * r * 0.9, "t": 0.0,
					"life": _rng.randf_range(SEED_LIFE.x, SEED_LIFE.y), "ph": _rng.randf() * TAU, "v": _rng.randf_range(0.7, 1.3)})
	for k in range(_seed_list.size() - 1, -1, -1):
		var sd: Dictionary = _seed_list[k]
		sd["t"] = float(sd["t"]) + dt
		var p := _seed_pos(sd)
		var e2: Array = seeds[int(sd["e"])]
		var scr := p.x - _cl * float(e2[2])
		if float(sd["t"]) > float(sd["life"]) or scr > 520.0 or p.y < -12.0:
			_seed_list.remove_at(k)
	_seed_node.queue_redraw()
	# 涟漪：隔一会儿在镜头里的某个水面点泛一圈；晨在水里走时脚下也泛
	_rip_wait -= dt
	if _rip_wait <= 0.0 and not ripples.is_empty():
		_rip_wait = _rng.randf_range(RIPPLE_EVERY.x, RIPPLE_EVERY.y)
		for _tries in 6:
			var pt: Array = ripples[_rng.randi() % ripples.size()]
			if float(pt[0]) - _cl > 10.0 and float(pt[0]) - _cl < 470.0:
				_rip_list.append({"x": float(pt[0]), "y": float(pt[1]), "t": 0.0})
				break
	if _have_chen and _water_amt(_cx) > 0.5 and absf(_vx) > 8.0:
		_step_rip -= dt
		if _step_rip <= 0.0:
			_step_rip = RIPPLE_STEP
			var org2: Vector2 = get_parent().get("origin")
			_rip_list.append({"x": roundf(_cx), "y": roundf(_chen_node.position.y - org2.y) + 2.0, "t": 0.0})
	for k in range(_rip_list.size() - 1, -1, -1):
		_rip_list[k]["t"] = float(_rip_list[k]["t"]) + dt
		if float(_rip_list[k]["t"]) >= RIPPLE_LIFE:
			_rip_list.remove_at(k)
	_rip_node.queue_redraw()
	_life_node.queue_redraw()


## 绒毛现在在哪（那株蒲公英那一层的坐标）：往右上匀速飘 + 两道很慢的正弦
func _seed_pos(sd: Dictionary) -> Vector2:
	var t := float(sd["t"])
	var ph := float(sd["ph"])
	var v := float(sd["v"])
	return Vector2(float(sd["x0"]) + SEED_V.x * v * t + 6.0 * sin(t * 0.8 + ph),
		float(sd["y0"]) - SEED_V.y * v * t + 3.0 * sin(t * 1.3 + ph * 1.7))


func _paint_seeds(p: Node2D) -> void:
	for sd in _seed_list:
		var e: Array = seeds[int(sd["e"])]
		var q := _seed_pos(sd)
		var x := roundf(q.x + _cl * (1.0 - float(e[2])))
		var y := roundf(q.y)
		var fr: int = [0, 0, 1, 1][int(float(sd["t"]) * 1000.0 / FRAME_MS) % 4]
		if fr == 0:                                 # 平的小伞 + 下面的种子
			p.draw_rect(Rect2(x - 1, y, 3, 1), SEED_C)
			p.draw_rect(Rect2(x, y + 1, 1, 1), SEED_STEM_C)
		else:                                       # 伞顶鼓起来一格
			p.draw_rect(Rect2(x, y - 1, 1, 1), SEED_C)
			p.draw_rect(Rect2(x - 1, y, 3, 1), SEED_C)
			p.draw_rect(Rect2(x, y + 1, 1, 1), SEED_STEM_C)


func _paint_motes(p: Node2D) -> void:
	for i in motes.size():
		var m: Array = motes[i]
		var mx := float(m[0])
		if mx - _cl < -30.0 or mx - _cl > 510.0:
			continue
		var ph: Array = _mote_ph[i]
		var x := mx + 9.0 * sin(_t * float(ph[4]) + float(ph[0])) + 4.0 * sin(_t * float(ph[5]) + float(ph[1]))
		var y := float(m[1]) + 5.0 * sin(_t * float(ph[6]) + float(ph[2]))
		var b := sin(_t * float(ph[7]) + float(ph[3]))
		if b < -0.55:
			continue                                # 暗下去的时候藏一会儿
		p.draw_rect(Rect2(roundf(x), roundf(y), 1, 1), MOTE_C[0] if b > 0.2 else MOTE_C[1])


## 扁椭圆的一圈（一像素、四邻接，没有缺口），按半宽缓存
func _ring(rx: int, ry: int) -> PackedVector2Array:
	var key := Vector2i(rx, ry)
	if _ring_cache.has(key):
		return _ring_cache[key]
	var out := PackedVector2Array()
	var seen := {}
	var prev := Vector2i(rx, 0)
	var n := maxi(24, rx * 10)
	for i in n + 1:
		var a := TAU * i / n
		var q := Vector2i(roundi(cos(a) * rx), roundi(sin(a) * ry))
		if q.x != prev.x and q.y != prev.y:
			var mid := Vector2i(prev.x, q.y)          # 斜着错一格：补一格，让上下两格有边贴着
			if not seen.has(mid):
				seen[mid] = true
				out.append(Vector2(mid))
		if not seen.has(q):
			seen[q] = true
			out.append(Vector2(q))
		prev = q
	_ring_cache[key] = out
	return out


func _paint_ripples(p: Node2D) -> void:
	for rp in _rip_list:
		var u := float(rp["t"]) / RIPPLE_LIFE
		var e := 1.0 - pow(1.0 - u, 2.0)
		var rx := maxi(1, roundi(1.0 + (RIPPLE_R - 1.0) * e))
		var ry := maxi(1, roundi(rx * 0.32))
		var c: Color = RIPPLE_C[0] if u < 0.55 else RIPPLE_C[1]
		var cx := roundf(float(rp["x"]))
		var cy := roundf(float(rp["y"]))
		for q in _ring(rx, ry):
			p.draw_rect(Rect2(cx + q.x, cy + q.y, 1, 1), c)
