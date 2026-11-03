extends Node
## 摔倒后反复按 Q 起身：按键只累加缩放目标，镜头每帧平滑追赶；起身完成立即恢复原景别。
signal completed

const PRESSES := 6
const MAX_ZOOM := 1.45
const ZOOM_STEP := (MAX_ZOOM - 1.0) / PRESSES
const ZOOM_RESPONSE := 3.0
const AUTO_INTERVAL := 0.28

var level: Node2D
var count := 0
var target_zoom := 1.0
var rising := false
var _finished := false
var _home := Vector2.ZERO
var _sprite_home := Vector2.ZERO
var _pulse := 0.0
var _time := 0.0
var _auto_clock := 0.0
var _auto := false
var _hud: CanvasLayer
var _label: Label


func _ready() -> void:
	_home = level.cam.position
	_sprite_home = level.chen.spr.position
	target_zoom = level.cam.zoom.x
	level.camera_hold_at(_home)
	_auto = level._autoplay or level._story_auto != "" or level._shot != "" or level._shots_dir != ""
	_hud = CanvasLayer.new()
	_hud.layer = 40
	add_child(_hud)
	_label = Label.new()
	_label.theme = UITheme.get_theme()
	_label.add_theme_font_size_override("font_size", 14)
	_label.position = Vector2(0, 228)
	_label.size = Vector2(480, 18)
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(_label)
	_refresh()


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_Q:
		get_viewport().set_input_as_handled()
		press()


func press() -> void:
	if rising or _finished:
		return
	count += 1
	target_zoom = minf(MAX_ZOOM, target_zoom + ZOOM_STEP)
	_pulse = 2.5
	_refresh()
	if count >= PRESSES:
		rising = true
		_label.hide()
		level.chen.spr.position = _sprite_home
		level._chen_get_up()
		var tw: Tween = level._tw()
		tw.tween_interval(level.GETUP_TIME + 0.2 if level._has_getup else 1.7)
		tw.tween_callback(_finish)


func _process(delta: float) -> void:
	if _finished:
		return
	_time += delta
	if _auto and not rising:
		_auto_clock += delta
		if _auto_clock >= AUTO_INTERVAL:
			_auto_clock = 0.0
			press()
	# 目标可以被后续按键继续抬高；不重启 tween，因此连续按不会造成缩放停顿。
	var zoom := lerpf(level.cam.zoom.x, target_zoom, 1.0 - exp(-ZOOM_RESPONSE * delta))
	level.cam.zoom = Vector2.ONE * zoom
	var focus: Vector2 = level.chen.position + Vector2(0, -18)
	var center := _home.lerp(focus, clampf((zoom - 1.0) / 1.2, 0.0, 1.0))
	level.camera_hold_at(center)
	level.cam.position = center
	if not rising or level._has_getup:
		var offset := Vector2(sin(_time * 77.0), sin(_time * 59.0)) * _pulse
		level.chen.spr.position = _sprite_home + offset.round()
		_pulse = move_toward(_pulse, 0.0, delta * 14.0)


func _refresh() -> void:
	_label.text = ("连续按 Q 站起来  %d / %d" if I18n.is_zh() else "Press Q repeatedly to get up  %d / %d") % [count, PRESSES]


func cancel() -> void:
	_finished = true
	level.chen.spr.position = _sprite_home
	level.cam.zoom = Vector2.ONE
	level.cam.position = _home
	level.camera_release()
	queue_free()


func _finish() -> void:
	if _finished:
		return
	cancel()
	completed.emit()
