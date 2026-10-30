extends Node2D
## 剧本里的 hotspot（可互动的点）：算哪些现在能用、画提示、找晨身边 / 鼠标点到的那个。story_runner.gd 建它、喂它剧本。
##
## 一个 hotspot：{"id", "at", "room", "label", "need", "not", "once", "scene", "sprite"?, "hide_after"?, "trigger"?, "range"?}
##   at = marker 名 / 物件 id / 数字 x / NPC 名（deer、miluo：跟着那个角色走，看不见就不出现）
##   need 全有、not 全没有、once 没用过 → 能用。同一个位置（x 差 4 像素以内）有好几个能用的：只要列表里第一个。
##   sprite：这个点要画的图（res:// 路径；和 story_world 里某个物件同一张图就直接用那个物件，不另画）。缺图画色块。
##   hide_after：这个 flag 设了以后图也藏起来。
##   trigger: "enter"（或 auto: true）：走进范围（range，默认 RANGE）就自己触发，不用按键（塌陷口 hollow）；离开范围 10 像素以后才会再触发。
##   range：这个点的范围（像素）。按键互动的点最少 MIN_RANGE（小东西也不用瞄准）。
##   runner.hotspot_blocked(h) = true 的不出现（发光木头那两个点：由关卡原来的拾取过场负责；小游戏等互动时只有它的临时点）。
##   多房间章节：at 是房间物件（room.json objects）时，点击框 = 物件的矩形，物件挪了也跟着挪。
##
## 互动以「靠近 + 按键」为主：晨走进范围就有提示，按 E / 空格 / 回车 / Z（或鼠标点那个东西）就互动「最合适的那个」：
##   范围里有好几个时，先选会推进剧情的（设新 flag / 给新东西 / 换地方），再选最近的。
##   成组的大物件（GROUP_PROPS，比如倒木）：晨站在它前面时，压在它下面的小东西（两根树枝）都算在范围里——
##   走到倒木前按一下拖开一根，再按一下拖另一根，不用分别去对准两根小树枝。
## 鼠标：点击判定框最少 MIN_CLICK × MIN_CLICK（比图大）；鼠标停在东西上：物件轻轻亮一档 + 显示名字；只有够得着的才亮、才能点；点空地、点远处都不走。
## 提示：范围里那个头顶一个小箭头（art/level1/hint_arrow.png）+ 按键图标（键盘：「E」小键帽；最近用的是鼠标：小鼠标）+ 很淡的名字。
##   还没用过、会推进剧情的点在屏幕里时，远远地也有一个更淡的小箭头。
##   所有可互动的东西在晨走进它范围的那一下轻轻亮一下；按下互动的瞬间：物件闪一下、箭头按下去一下（声音和晨转身由 level_forest.gd 做）。

const HINT_TEX := preload("res://art/level1/hint_arrow.png")
const RANGE := 20.0
const MIN_RANGE := 24.0
const MIN_CLICK := 24.0
const SAME_X := 4.0
const GROUP_PROPS := ["log"]
const GROUP_PAD := 24.0

var runner: Node                     # story_runner.gd
var world: Node2D                    # story_world.gd
var defs: Array = []
var _sprites := {}                   # hotspot id → Sprite2D（自己画的）或 world 的物件 id（String）
var _arrows := {}                    # hotspot id → Sprite2D
var _prompt: HBoxContainer           # 按键图标 + 名字
var _key_cap: Label
var _mouse_icon: TextureRect
var _label: Label
var _t := 0.0
var _auto_lock := {}
var active := true                   # false = 剧情在播，不画提示
var near: Dictionary = {}            # 现在按键会互动的那个（空 = 没有）
var hovered: Dictionary = {}         # 鼠标停在上面的那个
var use_mouse := false               # 最近一次用的是鼠标（提示画小鼠标，不画 E）
var _was_in := {}                    # id → 上一帧在不在范围里（走进来那一下亮一下）
var _glow := {}                      # id → 亮一下还剩多久（秒）
var _press := {}                     # id → 按下去的动画还剩多久
var _lit: Array = []                 # 上一帧调过亮度的精灵（恢复用）


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
	_prompt = HBoxContainer.new()
	_prompt.add_theme_constant_override("separation", 3)
	_prompt.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_prompt.modulate.a = 0.0
	_key_cap = Label.new()
	_key_cap.text = "E"
	_key_cap.add_theme_font_size_override("font_size", 14)
	_key_cap.add_theme_color_override("font_color", UITheme.TEXT)
	_key_cap.add_theme_stylebox_override("normal", UITheme.box(Color(0.06, 0.1, 0.09, 0.85), Color(0.6, 0.72, 0.66, 0.8), 1, Vector4(3, 0, 2, 0)))
	_key_cap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_prompt.add_child(_key_cap)
	_mouse_icon = TextureRect.new()
	_mouse_icon.texture = _mouse_tex()
	_mouse_icon.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
	_mouse_icon.custom_minimum_size = Vector2(9, 15)
	_mouse_icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_prompt.add_child(_mouse_icon)
	_label = Label.new()
	_label.add_theme_font_size_override("font_size", 14)
	_label.add_theme_color_override("font_color", UITheme.TEXT_DIM)
	_label.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.6))
	_label.add_theme_constant_override("shadow_offset_x", 0)
	_label.add_theme_constant_override("shadow_offset_y", 1)
	_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_prompt.add_child(_label)
	ui_root.add_child(_prompt)
	ui_root.move_child(_prompt, 0)


## 7×10 的小鼠标（左键涂亮）
static func _mouse_tex() -> ImageTexture:
	var img := Image.create_empty(7, 10, false, Image.FORMAT_RGBA8)
	var edge := Color(0.75, 0.85, 0.8, 0.9)
	var body := Color(0.08, 0.12, 0.1, 0.85)
	var lit := Color(0.95, 0.85, 0.55, 1.0)
	for y in 10:
		for x in 7:
			var corner := (x == 0 or x == 6) and (y == 0 or y == 9)
			if corner:
				continue
			var border := x == 0 or x == 6 or y == 0 or y == 9
			img.set_pixel(x, y, edge if border else body)
	for y in range(1, 4):
		for x in range(1, 3):
			img.set_pixel(x, y, lit)
	for y in range(1, 4):
		img.set_pixel(3, y, edge)
	for x in range(1, 6):
		img.set_pixel(x, 4, edge)
	return ImageTexture.create_from_image(img)


func _world_prop_for(path: String) -> String:
	var f := path.get_file()
	for id in world.PROPS:
		if str(world.PROPS[id].get("tex", "")) == f:
			return id
	return ""


static func is_enter(h: Dictionary) -> bool:
	return str(h.get("trigger", "")) == "enter" or bool(h.get("auto", false))


## 范围：按键互动的点最少 MIN_RANGE；走进来触发的照剧本给的
static func range_of(h: Dictionary) -> float:
	var r := float(h.get("range", RANGE))
	return r if is_enter(h) else maxf(r, MIN_RANGE)


## 这个 hotspot 现在能不能用（不管位置）
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


## 现在能用的点，按房间过滤、同位置只留第一个：[{h, x, top, rect, spr}, …]
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
			if absf(float(o["x"]) - float(p["x"])) <= SAME_X and runner._lv_target(o["h"].get("at", 0)) == runner._lv_target(hd.get("at", 0)):
				dup = true
				break
		if dup:
			continue
		p["h"] = hd
		out.append(p)
	return out


## 一个 hotspot 在哪：{ok, x, top（提示箭头的 y）, rect（点击范围，世界坐标）, spr（亮一下用的精灵，可能没有）}
func locate(h: Dictionary) -> Dictionary:
	var at = h.get("at", 0)
	var id := str(h.get("id", ""))
	var npc: Node2D = runner.npc(str(at)) if at is String else null
	if npc != null:
		if not npc.visible:
			return {"ok": false}
		var x := npc.position.x
		return {"ok": true, "x": x, "top": npc.position.y - 56.0, "rect": Rect2(x - 14, npc.position.y - 52, 28, 52), "spr": null}
	if at is String and world.extra_rects.has(str(at)):
		var er: Rect2 = (world.extra_rects[str(at)] as Callable).call()
		if er.size.x > 0:
			var ex: float = world.resolve(at)["x"] if world.markers.has(str(at)) else er.get_center().x
			return {"ok": true, "x": ex, "top": er.position.y + 10.0, "rect": er, "spr": null}
	var r: Dictionary = world.resolve(at)
	if not r["ok"]:
		return {"ok": false}
	var x: float = r["x"]
	if at is String and world.stage_of_prop(str(at)) != "":
		# 多房间章节的物件（room.json objects）：点击框 = 物件的矩形，物件挪了点也跟着挪（at 写物件 id 的「会动的 hotspot」）
		var orr: Rect2 = world.prop_rect(str(at))
		if orr.size.x <= 0:
			return {"ok": false}
		var sn: Sprite2D = world.stage(world.stage_of_prop(str(at))).object(str(at))
		return {"ok": true, "x": x, "top": orr.position.y - 4.0, "rect": orr.grow(3), "spr": sn}
	var room := str(h.get("room", "forest"))
	var gy: float = round(world.ground_at(x, room)) + 1.0
	var ls: Node2D = runner._lv_stage(room)
	if ls != null and at is String and ls.marker_level(str(at)) >= 0:
		gy = round(ls.level_fn(ls.marker_level(str(at))).call(x)) + 1.0     # 多层小屋：点画在它那层的地面上
	var rect := Rect2(x - 10, gy - 30, 20, 30)
	var top := gy - 26.0
	var pid := ""
	var spr = _sprites.get(id, null)
	var node: Sprite2D = null
	if spr is String:
		pid = spr
	elif at is String and world.props.has(str(at).trim_prefix("room_")):
		pid = str(at).trim_prefix("room_")
	if pid != "" and (world.props[pid] as Sprite2D).visible:
		var pr: Rect2 = world.prop_rect(pid)
		if pr.size.x > 0 and pr.size.x <= 140:
			rect = pr.grow(3)
			top = pr.position.y - 4.0
			node = world.props[pid]
	elif spr is Sprite2D:
		var s: Sprite2D = spr
		s.position = Vector2(round(x), gy)
		if s.visible:
			var sr := Rect2(s.global_position + s.offset, s.texture.get_size())
			rect = sr.grow(3)
			top = sr.position.y - 4.0
			node = s
	if top > gy - 14.0:
		top = gy - 14.0
	return {"ok": true, "x": x, "top": top, "rect": rect, "spr": node}


## 成组的大物件（倒木）：晨在它前后 GROUP_PAD 以内、这个点又压在它下面 → 算在范围里
func _in_group(px: float, cx: float) -> bool:
	for g in GROUP_PROPS:
		if not world.props.has(g) or not (world.props[g] as Sprite2D).visible or world.prop_state(g) == "moved":
			continue
		var r: Rect2 = world.prop_rect(g)
		if px >= r.position.x and px <= r.end.x and cx >= r.position.x - GROUP_PAD and cx <= r.end.x + GROUP_PAD:
			return true
	return false


func in_range(p: Dictionary, cx: float) -> bool:
	var h: Dictionary = p["h"]
	var px := float(p["x"])
	if runner.auto == "" and not same_level(h):
		return false                     # 多层小屋：别的层的东西够不着（先上 / 下楼）；自动玩例外，点了晨自己走上去（_lv_reach）
	if absf(px - cx) <= range_of(h):
		return true
	return not is_enter(h) and _in_group(px, cx)


## 多层小屋：这个点和晨在不在同一层（按键只认同层的；鼠标点别层的 = 晨先走上 / 下去，见 story_runner._lv_reach）
func same_level(h: Dictionary) -> bool:
	var ls: Node2D = runner._lv_stage(str(h.get("room", "forest")))
	if ls == null:
		return true
	var lv: int = runner._lv_target(h.get("at", 0))
	return lv < 0 or lv == int(ls.chen_lv)


## 按键会互动的那个：范围里先挑会推进剧情的，再挑最近的；没有就是 {}
func nearest(cx: float) -> Dictionary:
	var best: Dictionary = {}
	var best_key := INF
	for p in available():
		var h: Dictionary = p["h"]
		if is_enter(h) or not in_range(p, cx) or not same_level(h):
			continue
		var key := absf(float(p["x"]) - cx) + (0.0 if runner.is_progress_hotspot(h) else 1000.0)
		if key < best_key:
			best_key = key
			best = p
	return best


## 鼠标点到的那个（世界坐标）：判定框最少 MIN_CLICK 见方；好几个重叠时取中心最近的
func at_point(wp: Vector2) -> Dictionary:
	var best: Dictionary = {}
	var bd := INF
	for p in available():
		if is_enter(p["h"]):
			continue
		var r: Rect2 = click_rect(p)
		if r.has_point(wp):
			var d := r.get_center().distance_to(wp)
			if d < bd:
				bd = d
				best = p
	return best


static func click_rect(p: Dictionary) -> Rect2:
	var r: Rect2 = p["rect"]
	var c := r.get_center()
	var s := Vector2(maxf(r.size.x, MIN_CLICK), maxf(r.size.y, MIN_CLICK))
	return Rect2(c - s / 2.0, s)


## 自己触发的点（trigger:"enter"）：晨走进范围就返回它（每次进范围一次）
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


## 按下互动的瞬间：物件闪一下、箭头按下去一下
func pressed(p: Dictionary) -> void:
	var id := str(p["h"].get("id", ""))
	_glow[id] = 0.45
	_press[id] = 0.18


func update(delta: float, chen: Node2D, cam_left: Vector2, mouse_world = null) -> void:
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
			# 物件被剧本换过状态（木板搭成桥）就不归 hide_after 管
			if gone and (world.props[spr] as Sprite2D).visible and world.prop_state(spr) in ["", "show", "shown", "default"]:
				world.set_prop(spr, "hidden")
		else:
			(spr as Sprite2D).visible = not gone
	near = {}
	hovered = {}
	var avail: Array = available() if active else []
	if active and chen.visible:
		near = nearest(chen.position.x)
		if mouse_world is Vector2 and use_mouse:
			hovered = at_point(mouse_world)
			if not hovered.is_empty() and not in_range(hovered, chen.position.x):
				hovered = {}              # 够不着的不亮、不显示名字（点了也没用）
	# 走进范围那一下亮一下
	var now_in := {}
	for p in avail:
		var id := str(p["h"]["id"])
		if not is_enter(p["h"]) and in_range(p, chen.position.x):
			now_in[id] = true
			if not _was_in.has(id):
				_glow[id] = maxf(float(_glow.get(id, 0.0)), 0.5)
	_was_in = now_in
	for id in _glow.keys():
		_glow[id] = float(_glow[id]) - delta
		if float(_glow[id]) <= 0.0:
			_glow.erase(id)
	for id in _press.keys():
		_press[id] = float(_press[id]) - delta
		if float(_press[id]) <= 0.0:
			_press.erase(id)
	# 物件亮度：鼠标停在上面亮一档，走进范围 / 按下去时亮一下（用 modulate 的 rgb，不动透明度）
	for s in _lit:
		if is_instance_valid(s):
			var sp: Sprite2D = s
			sp.modulate = Color(1, 1, 1, sp.modulate.a)
	_lit.clear()
	for p in avail:
		var s: Sprite2D = p.get("spr", null)
		if s == null:
			continue
		var id := str(p["h"]["id"])
		var k := 1.0
		if not hovered.is_empty() and str(hovered["h"]["id"]) == id:
			k = 1.3
		if _glow.has(id):
			k = maxf(k, 1.0 + 0.6 * sin(clampf(float(_glow[id]) / 0.5, 0.0, 1.0) * PI))
		if k != 1.0:
			s.modulate = Color(k, k, k, s.modulate.a)
			_lit.append(s)
	# 箭头
	var seen := {}
	for p in avail:
		var h: Dictionary = p["h"]
		var id := str(h["id"])
		var is_near: bool = not near.is_empty() and str(near["h"]["id"]) == id
		var is_hover: bool = not hovered.is_empty() and str(hovered["h"]["id"]) == id
		var beacon: bool = not is_enter(h) and not StoryState.used.has(id) and runner.is_progress_hotspot(h)
		if not is_near and not is_hover and not beacon:
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
		if _press.has(id):
			bob = -1.0                                  # 按下去一下
		a.position = Vector2(round(float(p["x"])), round(float(p["top"]) - bob))
		var want := (0.6 + 0.3 * sin(_t * 3.0)) if (is_near or is_hover) else (0.22 + 0.12 * sin(_t * 2.2))
		if _press.has(id):
			want = 1.0
		a.modulate.a = move_toward(a.modulate.a, want, delta * 3.0) if not _press.has(id) else want
		a.visible = true
	for id in _arrows:
		if not seen.has(id):
			var a: Sprite2D = _arrows[id]
			a.modulate.a = move_toward(a.modulate.a, 0.0, delta * 4.0)
			if a.modulate.a <= 0.0:
				a.visible = false
	# 提示：按键图标 + 名字（鼠标停着的优先，不然是按键会互动的那个）
	var show: Dictionary = hovered if not hovered.is_empty() else near
	var la := 0.0
	if not show.is_empty():
		var lbl: String = runner.txt(show["h"].get("label", {}))
		_label.text = lbl
		_label.visible = lbl != ""
		_key_cap.visible = not use_mouse
		_mouse_icon.visible = use_mouse
		_prompt.reset_size()
		var w := _prompt.get_combined_minimum_size().x
		var sx := float(show["x"]) - cam_left.x
		var sy := float(show["top"]) - cam_left.y
		# 别压在晨身上：物体比晨的头低（地上的小东西）就挪到晨头顶上面
		var head := chen.position.y - 56.0 - cam_left.y
		if sy - 19.0 + 16.0 > head and absf(float(show["x"]) - chen.position.x) < 30.0:
			sy = head
		_prompt.position = Vector2(clampf(round(sx - w / 2.0), 4.0, 476.0 - w), round(sy - 20.0))
		la = 0.85
	_prompt.modulate.a = move_toward(_prompt.modulate.a, la, delta * 4.0)
