extends Node2D
## 远处游过的一头鲸（只是一条影子）：放在最远的那层（Deeper，scroll 0.05，在所有石柱后面、远处巨藻林前面）里，
## 很慢地往左游，左右绕回 960。贴图是 tools/underwater_art.py 画的 whale.png（frames 帧横排：尾巴上下摆、尾鳍翘、
## 长胸鳍慢慢扇）。贴图里存的是「乘多少」，材质用 scripts/underwater_shadow.gdshader（乘法混合），
## 所以它只是把后面的水压暗一两成，往水色里褪；光柱画在它上面，游进光里会被照到。
## 位置取整到像素，上下慢慢起伏。开销：一两次 draw_texture_rect_region。

@export var texture: Texture2D = preload("res://art/underwater/whale.png")
@export var frames := 12
@export var frame_time := 0.42
@export var start := Vector2(118, 3)
@export var speed := 3.0
@export var bob := 2.0

var _t := 0.0
var _x := 0.0


func _ready() -> void:
	_x = start.x


func _process(delta: float) -> void:
	_t += delta
	_x = fposmod(_x - speed * delta, 960.0)
	queue_redraw()


func _draw() -> void:
	var fw := texture.get_width() / frames
	var fh := texture.get_height()
	var f := int(_t / frame_time) % frames
	var p := Vector2(_x, start.y + bob * sin(_t * 0.09)).round()
	draw_texture_rect_region(texture, Rect2(p, Vector2(fw, fh)), Rect2(f * fw, 0, fw, fh))
	if _x > 960.0 - fw:                     # 跨过接缝时，另一头补画一截
		draw_texture_rect_region(texture, Rect2(p - Vector2(960, 0), Vector2(fw, fh)), Rect2(f * fw, 0, fw, fh))
