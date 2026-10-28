extends Node2D
## 远处游过的大家伙（只是一条剪影）：放在最远的那层（Deeper，scroll 0.05，在所有石柱后面）里，慢慢往左游，左右绕回 960。
## 贴图是 tools/underwater_art.py 画的 whale.png（6 帧横排，尾巴和长丝在摆、胸鳍在扇），颜色已经褪进远处的水里。
## 游得很慢（speed 像素 / 秒），上下慢慢起伏；位置取整到像素。
## 开销：一次 draw_texture_rect_region。

@export var texture: Texture2D = preload("res://art/underwater/whale.png")
@export var frames := 8
@export var frame_time := 0.36
@export var start := Vector2(330, 34)
@export var speed := 5.0
@export var bob := 3.0

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
	var p := Vector2(_x, start.y + bob * sin(_t * 0.07)).round()
	draw_texture_rect_region(texture, Rect2(p, Vector2(fw, fh)), Rect2(f * fw, 0, fw, fh))
	if _x > 960.0 - fw:                     # 跨过接缝时，另一头补画一截
		draw_texture_rect_region(texture, Rect2(p - Vector2(960, 0), Vector2(fw, fh)), Rect2(f * fw, 0, fw, fh))
