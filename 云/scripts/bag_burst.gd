extends RefCounted
## 飞机撞击时与晨同时甩出的场景背包。由 level_forest._impact 同帧调用，不移动镜头。
## 飞行精灵复用场景背包素材，远处可拾取的 c1_bag 保持原位和剧情状态。
const ID := "bag_burst"
const FLIGHT_TIME := 1.15
const GRAVITY := 280.0


static func launch(lv: Node2D, w: Node2D) -> void:
	var source: Sprite2D = w.props.get("c1_bag")
	if source == null:
		return
	if is_instance_valid(lv._crash_bag):
		lv._crash_bag.queue_free()
	var bag := Sprite2D.new()
	bag.name = "CrashBag"
	bag.texture = source.texture
	bag.hframes = source.hframes
	bag.vframes = source.vframes
	bag.frame = source.frame
	bag.scale = source.scale
	bag.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	lv.add_child(bag)
	lv._crash_bag = bag
	var start: Vector2 = lv.wreck.global_position + lv.WRECK_HATCH + Vector2(8, -4)
	var end_x: float = lv.cam.global_position.x + 240.0 / lv.cam.zoom.x + 40.0
	var velocity := Vector2((end_x - start.x) / FLIGHT_TIME, -210.0)
	bag.global_position = start
	bag.rotation = -0.25
	var tw: Tween = lv._tw()
	tw.tween_method(func(t: float):
		bag.global_position = (start + velocity * t + Vector2(0, 0.5 * GRAVITY * t * t)).round()
		bag.rotation = -0.25 + TAU * 1.5 * t / FLIGHT_TIME,
		0.0, FLIGHT_TIME, FLIGHT_TIME)
	tw.tween_callback(func():
		bag.queue_free()
		lv._crash_bag = null)


## 兼容旧剧本的 mechanic 调用；演出已移到碰撞瞬间，不在主角起身后重播。
func run(_lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	ff(r, st)


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	run(lv, w, r, st)


func ff(_r: Node, st: Dictionary) -> void:
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))


func check(_story: Node, _st: Dictionary) -> Array:
	return []
