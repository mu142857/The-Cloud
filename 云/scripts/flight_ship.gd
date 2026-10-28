extends Node2D
## 飞船：单键滑翔。按住 = 往上，松开 = 往下滑。速度往目标速度「追」（有惯性），所以手感像纸飞机 / 风筝。
## 竖直方向的运动是一个纯函数 step()，机器人做预测时也用它（保证预测和实际一模一样）。
## 画面：art/flight/ship.png 5 个倾角帧（-22 / -11 / 0 / 11 / 22 度，按竖直速度挑），尾焰 3 帧，尾巴一团暖光。

const UP := 80.0          # 按住时往上的最大速度（像素 / 秒）
const DOWN := 44.0        # 松开时往下滑的速度
const ACC := 2.7          # 追目标速度的快慢（越大越跟手，越小越飘）
const EDGE_SOFT := 3.0    # 离上下边界每差 1 像素，最大速度减这么多（贴边时慢慢停住，不会「撞墙」）
const TOP := 34.0
const BOTTOM := 228.0
const EMERG_UP := 0.42    # 紧急模式：上升只剩这么多

const SHIP_TEX := preload("res://art/flight/ship.png")
const FLAME_TEX := preload("res://art/flight/flame.png")
const FLAME_SMALL := preload("res://art/flight/flame_small.png")   # 紧急模式：火缩成一小簇
const GLOW_TEX := preload("res://art/flight/glow_warm.png")

var vy := 0.0
var pressed := false
var emergency := 0.0        # 0..1，紧急程度（画面上的咳嗽、火变小）
var ceiling := TOP          # 紧急模式时天花板会往下压
var flare := 0.0            # 刚烧了东西：尾焰亮一下
var hit_flash := 0.0
var shake := 0.0
var crashed := false

var _body: Sprite2D
var _flame: Sprite2D
var _glow: Sprite2D
var _t := 0.0
var _frame := 2


func _ready() -> void:
	_glow = Sprite2D.new()
	_glow.texture = GLOW_TEX
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	_glow.material = add
	add_child(_glow)
	_flame = Sprite2D.new()
	_flame.texture = FLAME_TEX
	_flame.hframes = 3
	add_child(_flame)
	_body = Sprite2D.new()
	_body.texture = SHIP_TEX
	_body.hframes = 5
	_body.frame = 2
	add_child(_body)


static func step(y: float, v: float, press: bool, dt: float, ceil_y: float, emerg: bool) -> Vector2:
	## 返回 (新 y, 新 vy)。纯函数：机器人预测用的也是它。
	var up := UP * (EMERG_UP if emerg else 1.0)
	var target := -up if press else DOWN
	# 贴边减速
	var room_up := maxf(0.0, y - ceil_y)
	var room_dn := maxf(0.0, BOTTOM - y)
	target = clampf(target, -room_up * EDGE_SOFT, room_dn * EDGE_SOFT)
	if y < ceil_y:
		target = maxf(target, 18.0 + (ceil_y - y) * 1.5)       # 天花板压下来了：轻轻往下推
	v += (target - v) * (1.0 - exp(-ACC * dt))
	y += v * dt
	y = clampf(y, TOP - 4.0, BOTTOM + 2.0)
	return Vector2(y, v)


func sim(dt: float) -> void:
	if crashed:
		vy = move_toward(vy, 26.0, 20.0 * dt)
		position.y += vy * dt
		return
	var r := step(position.y, vy, pressed, dt, ceiling, emergency > 0.0)
	position.y = r.x
	vy = r.y


func angle_of(v: float) -> float:
	return clampf(v / 80.0, -1.0, 1.0) * 22.0


func _process(delta: float) -> void:
	_t += delta
	# 倾角帧（有一点滞后，免得来回跳）
	var want := int(roundf(clampf(vy / 64.0, -1.0, 1.0) * 2.0)) + 2
	if crashed:
		want = 4
	var straining := emergency > 0.0 and pressed and position.y <= ceiling + 5.0 and not crashed
	if straining:
		want = 1
	if want != _frame and absf(vy / 64.0 * 2.0 + 2.0 - _frame) > 0.7:
		_frame = want
	_body.frame = _frame
	var ang := deg_to_rad((_frame - 2) * 11.0)
	var tail := Vector2(-22, 0).rotated(ang)
	var lit := 1.0 - emergency * 0.85
	if crashed:
		lit = 0.0
	var cough := 0.0
	if emergency > 0.0:
		cough = 1.0 if fmod(_t, 1.7) < 0.25 or fmod(_t + 0.4, 2.3) < 0.15 else 0.0
	var on := lit * (1.0 - cough)
	# 紧急模式：火变小（换成小的那簇），咳嗽时灭一下；往上够的时候偶尔「噗」地蹿回大火一下，又缩回去
	var small := emergency > 0.3 and flare < 0.3 and not (straining and int(_t * 7.0) % 5 == 0)
	_flame.texture = FLAME_SMALL if small else FLAME_TEX
	if small:
		_flame.visible = not crashed and cough < 0.5
	else:
		_flame.visible = on > 0.15 or (straining and emergency > 0.0)
	_flame.frame = int(_t * 14.0) % 3
	_flame.position = (tail + Vector2(-2 if small else -4, 0).rotated(ang)).round()
	_flame.scale = Vector2.ONE * (1.0 if flare < 0.3 else 2.0)
	_glow.position = tail.round()
	var g := (0.55 + 0.1 * sin(_t * 9.0)) * maxf(on, 0.35 * (1.0 - cough) if emergency > 0.0 and not crashed else 0.0) + flare * 0.9
	_glow.modulate = Color(1, 1, 1, clampf(g, 0.0, 1.0))
	_glow.scale = Vector2.ONE * ((1.0 - 0.4 * emergency) + flare * 1.2)
	flare = maxf(0.0, flare - delta * 1.2)
	# 撞到：闪白 + 晃
	hit_flash = maxf(0.0, hit_flash - delta)
	var blink := hit_flash > 0.0 and int(hit_flash * 14.0) % 2 == 0
	_body.modulate = Color(2.2, 2.2, 2.2) if blink else Color(1, 1, 1)
	shake = maxf(0.0, shake - delta * 2.5)
	var off := Vector2(sin(_t * 47.0), cos(_t * 39.0)) * shake * 3.0
	if straining:
		off.y += roundf(sin(_t * 31.0) * 0.6)
	_body.position = off.round()
	_flame.position += off.round()


func tail_pos() -> Vector2:
	var ang := deg_to_rad((_frame - 2) * 11.0)
	return global_position + Vector2(-20, 0).rotated(ang)


func hit_points() -> PackedVector2Array:
	## 撞判定的几个点（相对船心；比船身略小，宽容一点）
	return SHIP_POINTS_ROT[_frame]


const _PTS := [Vector2(15, 0), Vector2(8, -4), Vector2(-2, -4), Vector2(-14, -3), Vector2(-15, 2),
	Vector2(-4, 3), Vector2(6, 3), Vector2(0, 0)]
static var SHIP_POINTS_ROT: Array = _make_points()


static func _make_points() -> Array:
	var out := []
	for f in 5:
		var arr := PackedVector2Array()
		for p in _PTS:
			arr.append((p as Vector2).rotated(deg_to_rad((f - 2) * 11.0)))
		out.append(arr)
	return out


static func points_for_vy(v: float) -> PackedVector2Array:
	var f := int(roundf(clampf(v / 64.0, -1.0, 1.0) * 2.0)) + 2
	return SHIP_POINTS_ROT[f]
