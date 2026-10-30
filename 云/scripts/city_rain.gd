extends GPUParticles2D
## 绵绵细雨（第二版，作者：「不用像素雨，用 Until Someone Passes 那种非像素的绵绵细雨，GPUParticle 2D 的」）：
## 每滴是一根很细、柔边、半透明的斜线（贴图开场现生成：横截面高斯、尾巴往上淡掉），沿速度方向摆正，往右下斜着落。
## 项目是 canvas_items 拉伸，canvas 按窗口分辨率画，所以雨丝能比游戏像素细（1440×810 下芯只有 1 个屏幕像素宽），
## 节点自己用线性过滤 + mipmap，不跟全局的最近邻。
## 冷漠：整齐、匀速，数量和速度不随时间变；上下一样密。每滴出生淡入、到点淡出（细雨在灯下一闪一闪），
## 落到 bottom 那一行就没了（city_rain.gdshader 按行裁掉：雨打到地上）。
## city_rain.gdshader 还让落进路灯光锥里的雨丝亮起来（灯下才看得见雨），晨身后那条（y_dim 以下）压暗，不刷亮她的轮廓。
## 放在某一层 Parallax2D 下面（坐标是那一层的），area 宽 960 和图层一样，靠 Parallax2D 的 repeat 左右绕回。
## amount、lifetime、seed 用 GPUParticles2D 自己的；特效 lite 时 amount × 0.4（Toy 手册「流畅」档的做法）。

@export var length := 8.0               # 雨丝长（游戏像素）
@export var width := 1.0                # 雨丝那张小图的宽（游戏像素）；里面是高斯，看得见的芯大约 1/3
@export var speed := 120.0              # 往下落多快（像素/秒，竖直分量）
@export var slant := 0.2                # 每往下 1 像素往右多少（风）
@export var jitter := 0.08              # 速度上下浮动几成
@export var spread := 2.0               # 方向随机偏几度
@export var color := Color(0.62, 0.66, 0.7, 0.22)
@export var area := Rect2(0, -10, 960, 240)
@export var bottom := 228.0             # 雨丝最低落到哪一行（这一层的 y）
@export var y_dim := 183.0
@export var dim := 0.45                 # y_dim 以下的雨丝 alpha 乘多少
## 路灯的光锥（这一层的坐标）：每个 Vector4(灯头中心 x, 光锥上沿 y, 上沿半宽, 下沿半宽)，下沿在 light_bottom；最多 4 个
@export var lights := PackedVector4Array()
@export var light_bottom := 228.0
@export var color_lit := Color(0.66, 0.72, 0.75, 1)
@export var lit_boost := 2.6            # 光锥里 alpha 乘多少
## 只画光锥里的雨丝（灯下那一阵密雨；光锥外面的雨由别的 Rain 节点画）：只在每道光锥上方那一块生成，不浪费粒子
@export var only_lit := false

const SHADER := preload("res://scripts/city_rain.gdshader")
const TEX_W := 8


func _ready() -> void:
	if GameSettings.lite():
		amount = maxi(1, int(amount * 0.4))
	var vel := Vector2(slant, 1.0) * speed
	var travel := vel * lifetime
	var top := area.position.y
	# 出生的盒子：从 top 往上一段路程到 bottom，[top, bottom] 里任何时候一样密（过了 bottom 的被 shader 裁掉）；往左挪一段风吹过去的距离
	var y0 := top - travel.y
	var y1 := bottom
	var m := ParticleProcessMaterial.new()
	m.particle_flag_disable_z = true
	m.particle_flag_align_y = true
	if only_lit and not lights.is_empty():
		m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_POINTS
		m.emission_point_texture = _cone_points(travel)
		m.emission_point_count = m.emission_point_texture.get_width() * m.emission_point_texture.get_height()
	else:
		m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
		m.emission_box_extents = Vector3(area.size.x * 0.5, (y1 - y0) * 0.5, 0.0)
		m.emission_shape_offset = Vector3(area.position.x + area.size.x * 0.5 - travel.x * 0.5, (y0 + y1) * 0.5, 0.0)
	m.direction = Vector3(vel.x, vel.y, 0.0).normalized()
	m.spread = spread
	m.gravity = Vector3.ZERO
	m.initial_velocity_min = vel.length() * (1.0 - jitter)
	m.initial_velocity_max = vel.length() * (1.0 + jitter)
	var s := width / TEX_W
	m.scale_min = s * 0.9
	m.scale_max = s * 1.1
	m.color = color
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.12, 0.8, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 0), Color.WHITE, Color.WHITE, Color(1, 1, 1, 0)])
	var gt := GradientTexture1D.new()
	gt.gradient = g
	m.color_ramp = gt
	process_material = m
	texture = _streak(maxi(8, int(round(TEX_W * length / width))))
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	local_coords = true          # 跟着图层走（Parallax2D 的视差和左右绕回）
	fixed_fps = 0
	preprocess = lifetime
	use_fixed_seed = true
	visibility_rect = Rect2(area.position.x - travel.x - 40.0, y0 - 40.0,
		area.size.x + travel.x + 80.0, bottom - y0 + 80.0)
	var sm := ShaderMaterial.new()
	sm.shader = SHADER
	var ls := lights.slice(0, 4)
	sm.set_shader_parameter("n_lights", ls.size())
	ls.resize(4)
	sm.set_shader_parameter("lights", ls)
	sm.set_shader_parameter("light_bottom", light_bottom)
	sm.set_shader_parameter("color_lit", color_lit)
	sm.set_shader_parameter("lit_boost", lit_boost)
	sm.set_shader_parameter("y_dim", y_dim)
	sm.set_shader_parameter("dim", dim)
	sm.set_shader_parameter("wrap", area.size.x)
	sm.set_shader_parameter("bottom", bottom)
	sm.set_shader_parameter("only_lit", only_lit)
	material = sm
	restart()


func _process(_delta: float) -> void:
	# shader 里把雨丝的位置换回图层坐标（光锥、压暗、裁地面都按图层坐标算）
	var inv := global_transform.affine_inverse()
	(material as ShaderMaterial).set_shader_parameter("to_local", Projection(Transform3D(
		Basis(Vector3(inv.x.x, inv.x.y, 0), Vector3(inv.y.x, inv.y.y, 0), Vector3(0, 0, 1)),
		Vector3(inv.origin.x, inv.origin.y, 0))))


func _cone_points(travel: Vector2) -> ImageTexture:
	## 发射点：每道光锥外接框往上（往左）挪一段路程的那一块里，均匀撒 64×32 个点（RGBF 存坐标）
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var img := Image.create_empty(64, 32, false, Image.FORMAT_RGBF)
	var n := 0
	for y in img.get_height():
		for x in img.get_width():
			var l := lights[n % lights.size()]
			n += 1
			var px := rng.randf_range(l.x - l.w - travel.x, l.x + l.w)
			var py := rng.randf_range(l.y - travel.y, light_bottom)
			img.set_pixel(x, y, Color(px, py, 0.0))
	return ImageTexture.create_from_image(img)


static func _streak(h: int) -> ImageTexture:
	## TEX_W × h 的雨丝：白色，alpha = 横截面高斯 × 纵向（上面尾巴淡进来，下面雨滴头那一点收住）
	var img := Image.create_empty(TEX_W, h, false, Image.FORMAT_RGBA8)
	for y in h:
		var v := (y + 0.5) / h
		var along := smoothstep(0.0, 0.75, v) * (1.0 - smoothstep(0.88, 1.0, v))
		for x in TEX_W:
			var u := (x + 0.5 - TEX_W * 0.5) / (TEX_W * 0.5)
			img.set_pixel(x, y, Color(1, 1, 1, exp(-u * u * 7.0) * along))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)
