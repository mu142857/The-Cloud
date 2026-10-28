extends RefCounted
## 「晨这里有多亮」的小工具，给各场景的 chen.set_env(…, 光函数) 用（返回 0..1）。
##
##   polygon_shafts(chen, 节点)   光柱是一堆 Polygon2D（森林 Main/Shafts、城市 Shafts）：
##       把晨胸口那一点换到光柱那一层的坐标里（视差层也对：用的是画到屏幕上的变换），按 repeat 960 绕回，
##       看它落没落在某道光柱的横截面里；高过光柱底的，就用光柱最下面那一截（光柱往地面打，晨走进它的落点就算进光）。
##       边上 EDGE 像素软过渡；每道的亮度 = 顶点色里最大的 alpha × 它的 modulate.a（光柱在呼吸），再除以全场最亮那道。
##   group_light(chen, 组名, 系数, y)  场景里已经有 light_at(屏幕坐标) 的（水底 underwater_shafts.gd），问它，乘系数；
##       给了 y 就问晨头顶上那一截（屏幕 y 不低于它）。

const EDGE := 5.0          # 光柱左右边缘多宽的软过渡（像素）
const CHEST := 34.0        # 量哪一点：脚底往上这么多（胸口、肩）
const REPEAT := 960.0
const SPREAD := 8.0        # group_light：晨身体左右各多宽也算


static func polygon_shafts(chen: Node2D, shafts: Node) -> float:
	if shafts == null or not (shafts as CanvasItem).is_visible_in_tree():
		return 0.0
	var screen := chen.get_global_transform_with_canvas() * Vector2(0, -CHEST)
	var best := 0.0
	var top := 0.0
	for c in shafts.get_children():
		var poly := c as Polygon2D
		if poly == null:
			continue
		var amax := 0.0
		for vc in poly.vertex_colors:
			amax = maxf(amax, vc.a)
		top = maxf(top, amax)
		var p := poly.get_global_transform_with_canvas().affine_inverse() * screen
		var pts := poly.polygon
		var y0 := INF
		var y1 := -INF
		for q in pts:
			y0 = minf(y0, q.y)
			y1 = maxf(y1, q.y)
		var y := clampf(p.y, y0 + 0.5, y1 - 0.5)
		# 这一行和多边形各条边的交点 → 横截面 [xl, xr]
		var xl := INF
		var xr := -INF
		for k in pts.size():
			var a := pts[k]
			var b := pts[(k + 1) % pts.size()]
			if (a.y <= y and b.y >= y) or (b.y <= y and a.y >= y):
				if absf(b.y - a.y) < 0.001:
					continue
				var x := lerpf(a.x, b.x, (y - a.y) / (b.y - a.y))
				xl = minf(xl, x)
				xr = maxf(xr, x)
		if xl > xr:
			continue
		var cx := (xl + xr) * 0.5
		var px := p.x + REPEAT * roundf((cx - p.x) / REPEAT)
		var k := smoothstep(0.0, EDGE, px - xl) * smoothstep(0.0, EDGE, xr - px)
		best = maxf(best, k * amax * poly.modulate.a * poly.self_modulate.a)
	return best / top if top > 0.0 else 0.0


static func group_light(chen: Node2D, group: String, gain: float, y_at := INF) -> float:
	var n := chen.get_tree().get_first_node_in_group(group)
	if n == null or not n.has_method("light_at"):
		return 0.0
	var screen := chen.get_global_transform_with_canvas() * Vector2(0, -CHEST)
	screen.y = minf(screen.y, y_at)      # 光柱快到河床时已经淡没了：问晨头顶上那一截
	# 晨有十几像素宽：左右各取一点，取最亮的（光柱落在她半边身上也算）
	var a := 0.0
	for dx in [-SPREAD, 0.0, SPREAD]:
		a = maxf(a, n.light_at(screen + Vector2(dx, 0)))
	return clampf(a * gain, 0.0, 1.0)
