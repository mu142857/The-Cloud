extends Node2D
## 远处一群小鱼：几十条 2×1 / 3×1 像素的小鱼，在开场镜头左上那片空水里（鲸的前面一点）慢慢兜「8」字（群中心绕 anchor 走一条很慢的
## 李萨如曲线），每条鱼跟在群中心后面晚 0~lag 秒（所以整群拉成一条弯弯的带子，转弯的时候会挤成一团再散开），
## 自己再轻轻晃。放在 Far 层（scroll 0.08）里，Far 的石柱前面。
## 同一个脚本挂两个节点（同一个 seed，位置完全一样）：
##   mode = 0：影子，材质用 underwater_shadow.gdshader（乘法），把后面的水压暗 shade 那么多；
##   mode = 1：闪光，加法材质。转弯（横向速度接近 0、鱼身侧过来）的那几条，或者游进光柱里的，闪一下青银色。
## 开销：count 个 draw_rect（+ 闪光那份），每帧重画。

@export var mode := 0
@export var count := 64
@export var anchor := Vector2(64, 68)
@export var roam := Vector2(44, 9)
@export var period := 80.0
@export var lag := 16.0
@export var spread := Vector2(8.0, 4.5)
@export var shade := Color(0.64, 0.7, 0.78)
@export var glint := Color(0.55, 0.72, 0.88)
@export var glint_alpha := 0.16
@export var seed := 5

var _f: Array[Dictionary] = []
var _t := 0.0
var _shafts: Node = null


func _ready() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	for i in count:
		_f.append({
			"d": rng.randf() * lag, "ox": rng.randfn(0.0, spread.x), "oy": rng.randfn(0.0, spread.y),
			"fx": rng.randf_range(0.1, 0.3), "px": rng.randf() * TAU, "len": 3 if rng.randf() < 0.45 else 2,
			"gp": rng.randf() * TAU,
		})


func _center(t: float) -> Vector2:
	var w := TAU / period
	return anchor + Vector2(roam.x * sin(w * t), roam.y * sin(2.0 * w * t + 0.7))


func _process(delta: float) -> void:
	_t += delta
	if mode == 1 and _shafts == null:
		_shafts = get_tree().get_first_node_in_group("underwater_shafts")
	queue_redraw()


func _draw() -> void:
	var xf := get_global_transform_with_canvas()
	var vmax := roam.x * TAU / period
	for f in _f:
		var t: float = _t + 6.0 - f.d
		var c := _center(t)
		var v := _center(t + 0.2) - c
		var p := c + Vector2(f.ox + sin(t * f.fx * TAU + f.px) * 1.5, f.oy + sin(t * f.fx * 1.7 + f.px) * 1.0)
		p = p.round()
		var n: int = f.len
		if mode == 0:
			draw_rect(Rect2(p, Vector2(n, 1)), shade)
		else:
			var side := pow(1.0 - clampf(absf(v.x) / 0.2 / vmax, 0.0, 1.0), 4.0)      # 转身：鱼身侧过来对着光
			var a := glint_alpha * side * (0.5 + 0.5 * sin(_t * 1.3 + f.gp))
			a += 0.2 * pow(maxf(0.0, sin(_t * 1.7 + f.gp * 3.0)), 14.0)      # 偶尔一条侧身，鳞片闪一下
			if _shafts != null:
				var sp := xf * p
				sp.x = fposmod(sp.x + 240.0, 960.0) - 240.0
				a += 1.4 * _shafts.light_at(sp) * (0.5 + 0.5 * sin(_t * 0.9 + f.gp))
			if a < 0.03:
				continue
			var g := glint
			g.a = minf(a, 0.3)
			draw_rect(Rect2(p, Vector2(n, 1)), g)
