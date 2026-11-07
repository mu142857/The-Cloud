extends Node
## 摔倒后反复按 Q 起身：按键只累加缩放目标，镜头每帧平滑追赶；起身完成立即恢复原景别。
## 11-07 作者：不要文字（原来是「连续按 Q 站起来 3 / 6」），只在下方正中显示一个 Q 键帽。
## 键帽和森林里互动提示的「E」同一个样子（hotspots.gd：深青底、浅灰绿 1 像素边、14 号像素字），
## 11-07：雨和雷跟着按键慢慢停（level.qte_weather / qte_thunder）：每按一下雨稀一点，隔一阵一声雷、越来越远，站起来时停完。
## 没按时轻轻一呼一吸（提示「按它」），每按一下往下压 1 像素、边框亮一下再回去（提示「再按」）。
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
var _key: Label
var _key_y := 0.0
var _press_k := 0.0                       # 按下去的那一下：1 → 0
var _key_style: StyleBoxFlat
var _thunder_at := 1.2                    # 下一声雷在 _time 的第几秒

const KEY_BORDER := Color(0.6, 0.72, 0.66, 0.8)
const KEY_BORDER_HOT := Color(0.88, 0.95, 0.9, 1.0)


func _ready() -> void:
	_home = level.cam.position
	_sprite_home = level.chen.spr.position
	target_zoom = level.cam.zoom.x
	level.camera_hold_at(_home)
	_auto = level._autoplay or level._story_auto != "" or level._shot != "" or level._shots_dir != ""
	_hud = CanvasLayer.new()
	_hud.layer = 40
	add_child(_hud)
	_key = Label.new()
	_key.text = "Q"
	_key.theme = UITheme.get_theme()
	_key.add_theme_font_size_override("font_size", 14)
	_key.add_theme_color_override("font_color", UITheme.TEXT)
	_key_style = UITheme.box(Color(0.06, 0.1, 0.09, 0.85), KEY_BORDER, 1, Vector4(3, 0, 2, 0))
	_key.add_theme_stylebox_override("normal", _key_style)
	_key.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(_key)
	_key.reset_size()
	_key_y = 226.0                         # 和原来那行字同一高度（下黑边 244 以上）
	_key.position = Vector2(roundf((480.0 - _key.size.x) * 0.5), _key_y)
	_key.modulate.a = 0.0
	_key.create_tween().tween_property(_key, "modulate:a", 1.0, 0.35)


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
	_press_k = 1.0
	# 天气调用放在 has_method 后面：11-07 曾经出现 getup_qte.gd 是新版、level_forest.gd 是旧版（没有 qte_weather），
	# 调用报错让 press() 中途退出，晨永远站不起来（QTE 卡死）。两个文件不同步时也只是没有天气变化，不会卡。
	var has_weather: bool = level.has_method("qte_weather")
	if count < PRESSES:
		if has_weather:
			level.qte_weather(_weather_k())
	else:
		rising = true
		if has_weather:
			level.qte_weather(0.0, 1.4)
		var kt := _key.create_tween()
		kt.tween_property(_key, "modulate:a", 0.0, 0.25)
		level.chen.spr.position = _sprite_home
		level._chen_get_up()
		var tw: Tween = level._tw()
		tw.tween_interval(level.GETUP_TIME + 0.2 if level._has_getup else 1.7)
		tw.tween_callback(_finish)


func _process(delta: float) -> void:
	if _finished:
		return
	_time += delta
	_update_key(delta)
	if not rising and _time >= _thunder_at:
		_thunder_at = _time + randf_range(2.4, 3.6)
		if level.has_method("qte_thunder"):
			level.qte_thunder(_weather_k())
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


## 雨还剩多少：没按 = 1，按到最后一下前 ≈ 0.2（最后一下站起来才停完）
func _weather_k() -> float:
	return 1.0 - 0.8 * float(count) / float(PRESSES - 1) if count < PRESSES else 0.0


func _update_key(delta: float) -> void:
	if _key == null:
		return
	_press_k = move_toward(_press_k, 0.0, delta / 0.12)
	_key.position.y = _key_y + (1.0 if _press_k > 0.5 else 0.0)         # 整像素：按下去 1 像素
	_key_style.border_color = KEY_BORDER.lerp(KEY_BORDER_HOT, _press_k)
	if not rising:
		_key.self_modulate.a = 0.78 + 0.22 * (0.5 + 0.5 * cos(_time * TAU / 1.1))   # 一呼一吸，1.1 秒一次


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
