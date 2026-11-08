extends RefCounted
## 捡到背包：展示原来的大背包特写，翻开包盖，收起后回到游戏（提示玩家按 Tab 自己打开背包）。
const TEX := preload("res://art/forest_story/bag_closeup.png")
const FRAMES := 4
var auto_mode := false


func run(lv: Node2D, _w: Node2D, r: Node, _st: Dictionary) -> void:
	if r.ff:
		return
	var layer := CanvasLayer.new()
	layer.name = "BagPickupCloseup"
	layer.layer = 40
	lv.add_child(layer)
	var root := Control.new()
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.modulate.a = 0.0
	layer.add_child(root)
	var dim := ColorRect.new()
	dim.color = Color(0.04, 0.07, 0.07, 0.62)
	dim.size = Vector2(480, 270)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(dim)
	var bag := Sprite2D.new()
	bag.texture = TEX
	bag.hframes = FRAMES
	bag.position = Vector2(240, 135)
	bag.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	root.add_child(bag)
	var k := 0.3 if auto_mode else 1.0
	var tw := root.create_tween()
	tw.tween_property(root, "modulate:a", 1.0, 0.35 * k)
	tw.tween_interval(0.65 * k)
	for frame in range(1, FRAMES):
		tw.tween_callback(func(): bag.frame = frame)
		tw.tween_interval(0.12 * k)
	tw.tween_interval(0.5 * k)
	tw.tween_property(root, "modulate:a", 0.0, 0.3 * k)
	await tw.finished
	layer.queue_free()
	# 11-08 作者：特写收起后不再自动打开背包，剧本接着出「按 Tab 打开背包」，玩家自己开（Tab 或右上角背包按钮都行）


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


func ff(_r: Node, _st: Dictionary) -> void:
	pass


func check(_r: Node, _st: Dictionary) -> Array:
	return []
