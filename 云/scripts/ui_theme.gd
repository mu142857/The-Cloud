class_name UITheme
## 全游戏共用的界面主题：像素字（fonts/PixelFont.ttf = 天王星像素 11Px，带 GB2312 汉字，GPLv2 + 字体嵌入例外，
## 和 meme / Linger / Scrap Rush 是同一款）。注意：这款字一个 em 是 14 个点阵格（字体里一格 = 1024/14 ≈ 73 单位），
## 所以 14 号字一格 = 视口一像素，最利落；大字用 28 / 42（整 2 / 3 倍）。11 号会把一格画成 0.79 像素，和画面的像素格错开。
## 颜色：森林的青绿灰 + 半透明深底（界面允许半透明），不用纯黑纯白。

const FONT_PATH := "res://fonts/PixelFont.ttf"
const TEXT := Color("#dfe8e2")
const TEXT_DIM := Color("#8fa69a")
const ACCENT := Color("#c48fb4")      # 晨的紫红：说话人名字、选中
const WARM := Color("#e8b860")        # 燃烧值

static var _font: FontFile
static var _theme: Theme


static func font() -> FontFile:
	if _font == null:
		_font = load(FONT_PATH)
		_font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
		_font.hinting = TextServer.HINTING_NONE
		_font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
		_font.generate_mipmaps = false
	return _font


static func box(bg: Color, border: Color = Color(0, 0, 0, 0), bw := 0, pad := Vector4(4, 2, 4, 2)) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(bw)
	s.anti_aliasing = false
	s.content_margin_left = pad.x
	s.content_margin_top = pad.y
	s.content_margin_right = pad.z
	s.content_margin_bottom = pad.w
	return s


static func _tex(w: int, h: int, c: Color) -> ImageTexture:
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	img.fill(c)
	return ImageTexture.create_from_image(img)


static func get_theme() -> Theme:
	if _theme != null:
		return _theme
	var t := Theme.new()
	t.default_font = font()
	t.default_font_size = 14
	t.set_color("font_color", "Label", TEXT)
	# 按钮
	t.set_stylebox("normal", "Button", box(Color(0.1, 0.16, 0.14, 0.85), Color(0.3, 0.4, 0.35, 0.9), 1))
	t.set_stylebox("hover", "Button", box(Color(0.15, 0.23, 0.2, 0.92), Color(0.55, 0.68, 0.61), 1))
	t.set_stylebox("pressed", "Button", box(Color(0.3, 0.2, 0.3, 0.95), ACCENT, 1))
	t.set_stylebox("hover_pressed", "Button", box(Color(0.34, 0.23, 0.33, 0.95), ACCENT, 1))
	t.set_stylebox("disabled", "Button", box(Color(0.08, 0.1, 0.1, 0.6), Color(0.2, 0.25, 0.22), 1))
	t.set_stylebox("focus", "Button", box(Color(0, 0, 0, 0), Color(0.9, 0.94, 0.9, 0.9), 1))
	t.set_color("font_color", "Button", Color("#c9d6cf"))
	t.set_color("font_hover_color", "Button", Color("#ffffff"))
	t.set_color("font_pressed_color", "Button", Color("#ffffff"))
	t.set_color("font_hover_pressed_color", "Button", Color("#ffffff"))
	t.set_color("font_focus_color", "Button", Color("#ffffff"))
	# 面板
	t.set_stylebox("panel", "PanelContainer", box(Color(0.03, 0.06, 0.05, 0.92), Color(0.3, 0.4, 0.35, 0.9), 1, Vector4(10, 8, 10, 8)))
	t.set_stylebox("panel", "Panel", box(Color(0.03, 0.06, 0.05, 0.92), Color(0.3, 0.4, 0.35, 0.9), 1))
	# 滑条：3 像素高的槽 + 3×7 的把手
	t.set_stylebox("slider", "HSlider", box(Color(0.18, 0.24, 0.21), Color(0, 0, 0, 0), 0, Vector4(0, 1, 0, 2)))
	t.set_stylebox("grabber_area", "HSlider", box(Color(0.5, 0.64, 0.56), Color(0, 0, 0, 0), 0, Vector4(0, 1, 0, 2)))
	t.set_stylebox("grabber_area_highlight", "HSlider", box(Color(0.66, 0.8, 0.72), Color(0, 0, 0, 0), 0, Vector4(0, 1, 0, 2)))
	t.set_stylebox("focus", "HSlider", box(Color(0, 0, 0, 0), Color(0.9, 0.94, 0.9, 0.7), 1, Vector4(0, 0, 0, 0)))
	t.set_icon("grabber", "HSlider", _tex(3, 7, Color("#c9d6cf")))
	t.set_icon("grabber_highlight", "HSlider", _tex(3, 7, Color("#ffffff")))
	t.set_icon("grabber_disabled", "HSlider", _tex(3, 7, Color("#5c6f66")))
	t.set_constant("center_grabber", "HSlider", 1)
	t.set_constant("separation", "HBoxContainer", 4)
	t.set_constant("separation", "VBoxContainer", 4)
	_theme = t
	return t


## 只有文字、没有框的按钮（标题界面的「开始游戏」）：悬停 / 聚焦时文字变亮、两边出现小横杠由调用方画。
static func flat_button(b: Button) -> void:
	var empty := StyleBoxEmpty.new()
	for s in ["normal", "hover", "pressed", "hover_pressed", "focus", "disabled"]:
		b.add_theme_stylebox_override(s, empty)
	b.add_theme_color_override("font_color", TEXT_DIM)
	b.add_theme_color_override("font_hover_color", TEXT)
	b.add_theme_color_override("font_focus_color", TEXT)
	b.add_theme_color_override("font_pressed_color", Color.WHITE)
	b.add_theme_color_override("font_hover_pressed_color", Color.WHITE)
