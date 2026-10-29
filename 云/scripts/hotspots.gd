extends Node2D
## 剧本里的 hotspot（可互动的点）：算哪些现在能用、画提示、找晨身边 / 鼠标点到的那个。story_runner.gd 建它、喂它剧本。
##
## 一个 hotspot：{"id", "at", "room", "label", "need", "not", "once", "scene", "sprite"?, "hide_after"?, "auto"?}
##   at = marker 名 / 物件 id / 数字 x / NPC 名（deer、miluo：跟着那个角色走，看不见就不出现）
##   need 全有、not 全没有、once 没用过 → 能用。同一个位置（x 差 4 像素以内）有好几个能用的：只要列表里第一个。
##   sprite：这个点要画的图（res:// 路径；和 story_world 里某个物件同一张图就直接用那个物件，不另画）。缺图画色块。
##   hide_after：这个 flag 设了以后图也藏起来。
##   trigger: "enter"（或 auto: true）：走进范围（range，默认 RANGE）就自己触发，不用按键（塌陷口 hollow）；离开范围 10 像素以后才会再触发。
##   range：这个点的范围（像素），默认 RANGE。
##   runner.hotspot_blocked(h) = true 的不出现（发光木头那两个点：由关卡原来的拾取过场负责）。
## 提示：晨离它 RANGE 以内 → 头顶 / 物体上一个很轻的小箭头（art/level1/hint_arrow.png，和木头上那个一样）+ 很淡的名字。
##   另外：还没用过、会推进剧情的点（剧本里会设 flag / 给东西 / 换地方的）在屏幕里时，远远地也有一个更淡的小箭头（像木头那样），
##   零门槛：知道下一步去哪。闲聊的点没有。

const HINT_TEX := preload("res://art/level1/hint_arrow.png")
const RANGE := 20.0
const SAME_X := 4.0

var runner: Node                     # story_runner.gd
var world: Node2D                    # story_world.gd
var defs: Array = []
var _sprites := {}                   # hotspot id → Sprite2D（自己画的）或 world 的物件 id（String）
var _arrows := {}                    # hotspot id → Sprite2D
var _label: Label
var _label_layer: CanvasLayer
var _t := 0.0
var _auto_lock := {}
var active := true                   # false = 剧情在播，不画提示
var near: Dictionary = {}            # 现在晨身边那个（空 = 没有）


func setup(r: Node, w: Node2D, list: Array, ui_root: Control) -> void:
	runner = r
	world = w
	defs = list
	for h in defs:
		var hd: Dictionary = h
		var id := str(hd.get("id", ""))
		var sp := str(hd.get("sprite", ""))
		if sp != "":
			var reuse := _world_prop_for(sp)
			if reuse != "":
				_sprites[id] = reuse
			else:
				var s := Sprite2D.new()
				s.centered = false
				if ResourceLoader.exists(sp):
					s.texture = load(sp)
				else:
					s.texture = world._block(14, 10, Color("#6a6458"))
				s.offset = Vector2(-floor(s.texture.get_width() / 2.0), -s.texture.get_height())
				world._forest_layer.add_child(s)
				_sprites[id] = s
	_label = Label.new()
	_label.add_theme_font_size_override("font_size", 14)
	_label.add_theme_color_override("font_color", UITheme.TEXT_DIM)
	_label.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.6))
	_label.add_theme_constant_override("shadow_offset_x", 0)
	_label.add_theme_constant_override("shadow_offset_y", 1)
	_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_label.modulate.a = 0.0
	ui_root.add_child(_label)
	ui_root.move_child(_label, 0)


func _world_prop_for(path: String) -> String:
	var f := path.get_file()
	for id in world.PROPS:
		if str(world.PROPS[id].get("tex", "")) == f:
			return id
	return ""


## 这个 hotspot 现在能不能用（不管位置）
static func is_enter(h: Dictionary) -> bool:
	return str(h.get("trigger", "")) == "enter" or bool(h.get("auto", false))


static func range_of(h: Dictionary) -> float:
	return float(h.get("range", RANGE))


func usable(h: Dictionary) -> bool:
	var id := str(h.get("id", ""))
	if runner.hotspot_blocked(h):
		return false
	if h.get("once", false) and StoryState.used.has(id):
		return false
	if not StoryState.all_of(h.get("need", [])):
		return false
	if not StoryState.none_of(h.get("not", [])):
		return false
	return true


## 现在能用的点，按房间过滤、同位置只留第一个：[{h, x, y_top, rect, room}, …]
func available(room := "") -> Array:
	if room == "":
		room = world.room
	var out: Array = []
	for h in defs:
		var hd: Dictionary = h
		if str(hd.get("room", "forest")) != room or not usable(hd):
			continue
		var p := locate(hd)
		if not p.get("ok", false):
			continue
		var dup := false
		for o in out:
			if absf(float(o["x"]) - float(p["x"])) <= SAME_X:
				dup = true
				break
		if dup:
			continue
		p["h"] = hd
		out.append(p)
	return out


## 一个 hotspot 在哪：{ok, x, top（提示箭头的 y）, rect（点击范围，世界坐标）}
func locate(h: Dictionary) -> Dictionary:
	var at = h.get("at", 0)
	var id := str(h.get("id", ""))
	var npc: Node2D = runner.npc(str(at)) if at is String else null
	if npc != null:
		if not npc.visible:
			return {"ok": false}
		var x := npc.position.x
		return {"ok": true, "x": x, "top": npc.position.y - 56.0, "rect": Rect2(x - 14, npc.position.y - 52, 28, 52)}
	if at is String and world.extra_rects.has(str(at)):
		var er: Rect2 = (world.extra_rects[str(at)] as Callable).call()
		if er.size.x > 0:
			var ex: float = world.resolve(at)["x"] if world.markers.has(str(at)) else er.get_center().x
			return {"ok": true, "x": ex, "top": er.position.y + 10.0, "rect": er}
	var r: Dictionary = world.resolve(at)
	if not r["ok"]:
		return {"ok": false}
	var x: float = r["x"]
	var room := str(h.get("room", "forest"))
	var gy: float = round(world.ground_at(x, room)) + 1.0
	var rect := Rect2(x - 10, gy - 30, 20, 30)
	var top := gy - 26.0
	var pid := ""
	var spr = _sprites.get(id, null)
	if spr is String:
		pid = spr
	elif at is String and world.props.has(str(at).trim_prefix("room_")):
		pid = str(at).trim_prefix("room_")
	if pid != "" and (world.props[pid] as Sprite2D).visible:
		var pr: Rect2 = world.prop_rect(pid)
		if pr.size.x > 0 and pr.size.x <= 140:
			rect = pr.grow(3)
			top = pr.position.y - 4.0
	elif spr is Sprite2D:
		var s: Sprite2D = spr
		s.position = Vector2(round(x), gy)
		if s.visible:
			var sr := Rect2(s.global_position + s.offset, s.texture.get_size())
			rect = sr.grow(3)
			top = sr.position.y - 4.0
	if top > gy - 14.0:
		top = gy - 14.0
	return {"ok": true, "x": x, "top": top, "rect": rect}


## 晨身边（RANGE 以内）最近的一个；没有就是 {}
func nearest(cx: float) -> Dictionary:
	var best: Dictionary = {}
	var bd := INF
	for p in available():
		var h: Dictionary = p["h"]
		if is_enter(h):
			continue
		var d := absf(float(p["x"]) - cx)
		if d <= range_of(h) and d < bd:
			bd = d
			best = p
	return best


## 鼠标点到的那个（世界坐标）
func at_point(wp: Vector2) -> Dictionary:
	for p in available():
		if (p["rect"] as Rect2).has_point(wp):
			return p
	return {}


## 自己触发的点（auto）：晨走进范围就返回它（每次进范围一次）
func auto_trigger(cx: float) -> Dictionary:
	for p in available():
		var h: Dictionary = p["h"]
		if not is_enter(h):
			continue
		var id := str(h["id"])
		var d := absf(float(p["x"]) - cx)
		if _auto_lock.has(id):
			if d > range_of(h) + 10.0:
				_auto_lock.erase(id)
			continue
		if d <= range_of(h):
			_auto_lock[id] = true
			return p
	return {}


func lock_auto(id: String) -> void:
	_auto_lock[id] = true


func update(delta: float, chen: Node2D, cam_left: Vector2) -> void:
	_t += delta
	# 图：hide_after 设了就藏
	for h in defs:
		var hd: Dictionary = h
		var id := str(hd.get("id", ""))
		if not _sprites.has(id):
			continue
		var gone := hd.has("hide_after") and StoryState.has(str(hd["hide_after"]))
		var spr = _sprites[id]
		if spr is String:
			if gone and (world.props[spr] as Sprite2D).visible:
				world.set_prop(spr, "hidden")
		else:
			(spr as Sprite2D).visible = not gone
	near = {}
	var avail: Array = available() if active else []
	if active and chen.visible:
		near = nearest(chen.position.x)
	var seen := {}
	for p in avail:
		var h: Dictionary = p["h"]
		var id := str(h["id"])
		var is_near: bool = not near.is_empty() and str(near["h"]["id"]) == id
		var beacon: bool = not is_enter(h) and not StoryState.used.has(id) and runner.is_progress_hotspot(h)
		if not is_near and not beacon:
			continue
		seen[id] = true
		var a: Sprite2D = _arrows.get(id, null)
		if a == null:
			a = Sprite2D.new()
			a.texture = HINT_TEX
			a.z_index = 5
			add_child(a)
			_arrows[id] = a
		var bob := 1.0 if fmod(_t, 1.2) < 0.6 else 0.0
		a.position = Vector2(round(float(p["x"])), round(float(p["top"]) - bob))
		var want := (0.6 + 0.3 * sin(_t * 3.0)) if is_near else (0.22 + 0.12 * sin(_t * 2.2))
		a.modulate.a = move_toward(a.modulate.a, want, delta * 3.0)
		a.visible = true
	for id in _arrows:
		if not seen.has(id):
			var a: Sprite2D = _arrows[id]
			a.modulate.a = move_toward(a.modulate.a, 0.0, delta * 4.0)
			if a.modulate.a <= 0.0:
				a.visible = false
	# 名字：晨身边那个，箭头上面一行很淡的字
	var la := 0.0
	if not near.is_empty():
		var lbl: String = runner.txt(near["h"].get("label", {}))
		if lbl != "":
			if _label.text != lbl:
				_label.text = lbl
				_label.reset_size()
			var w := UITheme.font().get_string_size(lbl, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
			var sx := float(near["x"]) - cam_left.x
			var sy := float(near["top"]) - cam_left.y
			# 名字别压在晨身上：物体比晨的头低（地上的小东西）就挪到晨头顶上面
			var head := chen.position.y - 56.0 - cam_left.y
			if sy - 19.0 + 16.0 > head and absf(float(near["x"]) - chen.position.x) < 30.0:
				sy = head
			_label.position = Vector2(clampf(round(sx - w / 2.0), 4.0, 476.0 - w), round(sy - 19.0))
			la = 0.75
	_label.modulate.a = move_toward(_label.modulate.a, la, delta * 4.0)
