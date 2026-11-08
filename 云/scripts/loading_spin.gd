extends Sprite2D
## 左下角的「加载中」：妮芙（鲸鱼妹）高兴转圈（niff_spin.png，4 帧 100ms 循环，见 niff.json 的 spin）。
## 11-08 作者：启动黑屏加载时放一个（main.gd）。
## 耳机提示和后面的雨声黑屏都不放（作者「耳机过后还是不加了，影响听力」）。

const SHEET := "res://art/characters/niff/niff_spin.png"
const FRAMES := 4
const MS := 100
const SCALE := 0.5                 # 90×89 原图在 480×270 里太大，缩一半（≈45 像素）
const MARGIN := Vector2(8, 8)      # 离左下角
const FADE := 0.2

var t := 0.0
var _tw: Tween


func _init() -> void:
	texture = load(SHEET)
	hframes = FRAMES
	centered = false
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	scale = Vector2.ONE * SCALE
	var vh := float(ProjectSettings.get_setting("display/window/size/viewport_height", 270))
	position = Vector2(MARGIN.x, vh - MARGIN.y - float(texture.get_height()) * SCALE).round()
	modulate.a = 0.0
	visible = false


func _process(delta: float) -> void:
	t += delta
	frame = int(t * 1000.0 / MS) % FRAMES


## 淡入
func show_spin() -> void:
	visible = true
	_kill()
	_tw = create_tween()
	_tw.tween_property(self, "modulate:a", 1.0, FADE)


## 转完当前这一圈再淡出（不在半圈停）；done 在淡完后调
func hide_spin(done: Callable = Callable()) -> void:
	_kill()
	if not visible or modulate.a <= 0.0:
		visible = false
		if done.is_valid():
			done.call()
		return
	var cycle := FRAMES * MS / 1000.0
	var rest := cycle - fmod(t, cycle)
	_tw = create_tween()
	_tw.tween_property(self, "modulate:a", 0.0, FADE).set_delay(maxf(rest - FADE, 0.0))
	_tw.tween_callback(func(): visible = false)
	if done.is_valid():
		_tw.tween_callback(done)


func _kill() -> void:
	if _tw != null and _tw.is_valid():
		_tw.kill()
