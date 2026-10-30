extends GPUParticles2D
## 湿街面上雨点打出来的小涟漪（和 city_rain.gd 一起，非像素）：一圈压扁的细环，从小撑开、淡掉。
## 很淡，匀速、到处一样密，不抢戏。画在 Wet（镜子）后面，不进倒影、不被镜子按整像素分档。
## 放在 scroll 1.0 的 Parallax2D 下（街面那层的坐标），area 是出现涟漪的那一片街面，宽 960 左右绕回。
## 越远（area 上面）的环越小：街面分几条，每条一个节点，size 给这一条环的最大宽（游戏像素）。
## amount、lifetime 用 GPUParticles2D 自己的；特效 lite 时 amount × 0.4。

@export var area := Rect2(0, 236, 960, 30)
@export var size := 8.0                 # 环撑到最大时的宽（游戏像素），高是宽的 FLAT
@export var color := Color(0.62, 0.67, 0.72, 0.2)

const TEX := 64
const FLAT := 0.28


func _ready() -> void:
	if GameSettings.lite():
		amount = maxi(1, int(amount * 0.4))
	var m := ParticleProcessMaterial.new()
	m.particle_flag_disable_z = true
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	m.emission_box_extents = Vector3(area.size.x * 0.5, area.size.y * 0.5, 0.0)
	m.emission_shape_offset = Vector3(area.get_center().x, area.get_center().y, 0.0)
	m.gravity = Vector3.ZERO
	m.initial_velocity_min = 0.0
	m.initial_velocity_max = 0.0
	m.scale_min = size / TEX * 0.75
	m.scale_max = size / TEX * 1.1
	var c := Curve.new()
	c.add_point(Vector2(0.0, 0.2), 0.0, 2.2)
	c.add_point(Vector2(1.0, 1.0), 0.3, 0.0)
	var ct := CurveTexture.new()
	ct.curve = c
	m.scale_curve = ct
	m.color = color
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.08, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 0), Color.WHITE, Color(1, 1, 1, 0)])
	var gt := GradientTexture1D.new()
	gt.gradient = g
	m.color_ramp = gt
	process_material = m
	texture = _ring()
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	local_coords = true          # 跟着图层走（Parallax2D 的视差和左右绕回）
	fixed_fps = 0
	preprocess = lifetime
	use_fixed_seed = true
	visibility_rect = area.grow(size * 2.0)
	restart()


static func _ring() -> ImageTexture:
	## TEX × TEX·FLAT 的压扁细环：白色，alpha 是离椭圆边的距离的高斯；下半圈亮一点（离镜头近的那半边）
	var h := int(TEX * FLAT)
	var img := Image.create_empty(TEX, h, false, Image.FORMAT_RGBA8)
	for y in h:
		for x in TEX:
			var u := (x + 0.5) / TEX * 2.0 - 1.0
			var v := (y + 0.5) / h * 2.0 - 1.0
			var r := sqrt(u * u + v * v)
			var d := (r - 0.82) / 0.09
			img.set_pixel(x, y, Color(1, 1, 1, exp(-d * d) * (0.7 + 0.3 * clampf(v, 0.0, 1.0))))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)
