extends Node2D
## 起身 QTE 的按键特效 + 蓄力音效（getup_qte.gd 建，挂在关卡自己的 CanvasLayer 上，不挂在 QTE 下面：
## 最后一下「释放」的光圈和声音要比 QTE 本身活得久，QTE 结束 queue_free 时不能被一起掐掉）。
## 11-08 作者：要一个按下去的视觉特效 + 一个「逐渐升华，最后直接释放」的音效。
##
## 画面（全部硬边像素、位置取整、不描边、不用纯白——最亮就是键帽「亮边」那个浅灰绿）：
##   每按一下（1~5）：键帽外面弹出一圈切角方框，往外扩、变淡；再迸几颗 1 像素火星。
##       越往后扩得越远、越亮、火星越多；键帽外贴着一圈「蓄力光」越攒越亮越宽（最多 3 层），一直留着——看得出在攒。
##   最后一下（释放）：蓄力光一下子收掉，键帽外一圈大方框快速扩开，晨脚下一圈像素椭圆贴地扩开（像涟漪），
##       一把火星往上飘（混几颗晨的紫红），全屏极淡的一层浅灰绿闪一下就退。
## 声音（audio/sfx/qte_rise.wav 或 .ogg；没有文件就静默，不报错）：
##   一个文件分两段：0 ~ RELEASE_AT 是 5 级逐级升高的蓄力，RELEASE_AT 以后是释放。
##   第 i 下（1~5）只播第 i 级那一小段（末尾 60ms 淡出），连按就是一级级往上爬；第 6 下从 RELEASE_AT 一直播到尾。
##   播放和切段由 qte_audio.gd 共用；素材时间轴见 docs/QTE_音效需求.md。

const QTE_AUDIO := preload("res://scripts/qte_audio.gd")
const STEPS := QTE_AUDIO.STEPS

const HOT := Color(0.88, 0.95, 0.9)       # = getup_qte KEY_BORDER_HOT
const COOL := Color(0.6, 0.72, 0.66)      # = getup_qte KEY_BORDER
const ACCENT := Color("#c48fb4")          # 晨的紫红（UITheme.ACCENT）

var _key_rect := Rect2()
var _charge := 0.0               # 蓄力光显示值（追 _charge_to）
var _charge_to := 0.0
var _rings: Array[Dictionary] = []    # {r: Rect2, grow, t, life, a}
var _ellipses: Array[Dictionary] = [] # {c, t, life}
var _sparks: Array[Dictionary] = []   # {p, v, t, life, c}
var _flash := 0.0
var _released := false
var _rng := RandomNumberGenerator.new()
var _player: QTE_AUDIO
var silent := false              # 只要画面、声音由调用方自己播（闪回推障碍：flashback.gd 的 _qte_audio）


func _ready() -> void:
	_rng.seed = 2611
	if silent:
		return
	_player = QTE_AUDIO.new()
	_player.bus = GameSettings.OPENING_BUS
	add_child(_player)


## 第 n 下（1 ~ total，默认 STEPS）。key = 键帽在屏幕上的矩形（480×270 坐标）
func press(n: int, key: Rect2, total := STEPS) -> void:
	_key_rect = key
	var k := clampf(float(n) / float(maxi(1, total)), 0.0, 1.0)
	var spark_level := maxi(1, roundi(k * STEPS))       # 火星多少按五级算
	_charge_to = k
	_rings.append({r = key.grow(1), grow = 6.0 + 8.0 * k, t = 0.0, life = 0.32 + 0.1 * k, a = 0.55 + 0.4 * k})
	for i in 1 + spark_level:
		var ang := _rng.randf_range(-PI, 0.0)            # 往上半边迸
		_spark(key.get_center() + Vector2(cos(ang) * key.size.x * 0.5, sin(ang) * key.size.y * 0.5),
			Vector2(cos(ang), sin(ang)) * _rng.randf_range(30.0, 50.0 + 30.0 * k), 0.25 + 0.15 * k, HOT)
	if _player != null:
		_player.play_step(n, total)


## 最后一下。chen = 晨脚底在屏幕上的位置
func release(key: Rect2, chen: Vector2) -> void:
	_key_rect = key
	_released = true
	_charge_to = 0.0
	_charge = 0.0
	_rings.append({r = key.grow(1), grow = 16.0, t = 0.0, life = 0.36, a = 0.9})
	_rings.append({r = key.grow(1), grow = 9.0, t = -0.06, life = 0.3, a = 0.5})
	_ellipses.append({c = chen.round(), t = 0.0, life = 0.7})
	for i in 18:
		var p := chen + Vector2(_rng.randf_range(-10.0, 10.0), _rng.randf_range(-24.0, 0.0))
		var v := Vector2(_rng.randf_range(-14.0, 14.0), _rng.randf_range(-70.0, -30.0))
		_spark(p, v, _rng.randf_range(0.45, 0.8), ACCENT if i % 4 == 0 else HOT)
	for i in 10:
		var ang := _rng.randf_range(-PI, 0.0)
		_spark(key.get_center(), Vector2(cos(ang), sin(ang)) * _rng.randf_range(60.0, 110.0), 0.4, HOT)
	_flash = 0.14
	if _player != null:
		_player.play_release()


func _spark(p: Vector2, v: Vector2, life: float, c: Color) -> void:
	_sparks.append({p = p, v = v, t = 0.0, life = life, c = c})


func _process(delta: float) -> void:
	_charge = move_toward(_charge, _charge_to, delta * 3.0)
	_flash = move_toward(_flash, 0.0, delta * 0.45)
	for r in _rings:
		r.t += delta
	_rings = _rings.filter(func(r): return r.t < r.life)
	for e in _ellipses:
		e.t += delta
	_ellipses = _ellipses.filter(func(e): return e.t < e.life)
	for s in _sparks:
		s.t += delta
		s.p += s.v * delta
		s.v *= exp(-3.5 * delta)
		s.v.y += 20.0 * delta
	_sparks = _sparks.filter(func(s): return s.t < s.life)
	queue_redraw()
	# 释放以后：画面和声音都完了，连同自己的 CanvasLayer 一起收掉
	if _released and _rings.is_empty() and _ellipses.is_empty() and _sparks.is_empty() and _flash <= 0.0 \
			and (_player == null or not _player.playing):
		get_parent().queue_free()


func _draw() -> void:
	if _flash > 0.0:
		draw_rect(Rect2(0, 0, 480, 270), Color(HOT, _flash))
	# 蓄力光：贴着键帽的一圈光带，越攒越亮、越宽（最多 3 层、层间不留缝，读起来是一圈光，不是靶子）
	if _charge > 0.01 and _key_rect.size.x > 0.0:
		var c := COOL.lerp(HOT, _charge)
		for i in 3:
			var a := (0.34 - 0.1 * i) * clampf(_charge * 3.0 - i, 0.0, 1.0)
			if a > 0.0:
				_frame(_key_rect.grow(1 + i), Color(c, a))
	for r in _rings:
		if r.t < 0.0:
			continue
		var u: float = r.t / r.life
		var e := 1.0 - pow(1.0 - u, 3.0)                   # 先快后慢
		_frame((r.r as Rect2).grow(roundf(e * r.grow)), Color(HOT, r.a * (1.0 - u)))
	for el in _ellipses:
		var u: float = el.t / el.life
		var e := 1.0 - pow(1.0 - u, 2.0)
		_ellipse(el.c, 6.0 + 40.0 * e, 2.0 + 8.0 * e, Color(HOT, 0.7 * (1.0 - u)))
	for s in _sparks:
		var u: float = s.t / s.life
		var c: Color = s.c
		draw_rect(Rect2((s.p as Vector2).round(), Vector2.ONE), Color(c, 1.0 - u * u))


## 1 像素切角方框（四个角各缺 1 像素，像素风的「圆角」）
func _frame(r: Rect2, c: Color) -> void:
	r = Rect2(r.position.round(), r.size.round())
	var x0 := r.position.x
	var y0 := r.position.y
	var x1 := r.end.x - 1.0
	var y1 := r.end.y - 1.0
	if x1 - x0 < 2.0 or y1 - y0 < 2.0:
		return
	draw_rect(Rect2(x0 + 1, y0, x1 - x0 - 1, 1), c)
	draw_rect(Rect2(x0 + 1, y1, x1 - x0 - 1, 1), c)
	draw_rect(Rect2(x0, y0 + 1, 1, y1 - y0 - 1), c)
	draw_rect(Rect2(x1, y0 + 1, 1, y1 - y0 - 1), c)


## 像素椭圆环（整像素点，不重复画同一个点）
func _ellipse(c: Vector2, rx: float, ry: float, col: Color) -> void:
	var seen := {}
	var n := int(rx * 4.0) + 8
	for i in n:
		var a := TAU * float(i) / float(n)
		var p := (c + Vector2(cos(a) * rx, sin(a) * ry)).round()
		if seen.has(p):
			continue
		seen[p] = true
		draw_rect(Rect2(p, Vector2.ONE), col)
