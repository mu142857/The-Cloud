extends Control
## 结局回看（11-07 作者：「到了结局能不能有那种回看过往的感觉，就是切到支线任务角色停留3-4秒的感觉，比如兔子，如果做了任务，
## 兔子会生很多小宝宝，不管真结局还是坏结局，都会显示这些，先是母星公交车，然后每个npc都有一个短暂的镜头，不可跳过」）。
## 剧本步骤 {"do": "montage"}（story_runner._montage 建它，FLASHBACK_LAYER 那一层）：三个去处（芦苇地 / 云层小镇 / 回母星）的结局
##   都放在 end_chapter 前面——放完才出「全剧终」卡、制作人员。
## 一镜一个地方（shots()，名单和两版画面也写在 docs/第三章计划.md「结局回看」）：
##   先是母星的列车（11-07 作者确认「公交车就是母星列车」：art/home_train 那节车厢，窗外的城自己往后走，镜头不动），
##   然后每个支线 NPC 一镜。做了任务（看 flag）= 好结果那一版；没做 = 原样，整屏压暗偏冷一点（COLD）。
## 画面照 credits_page.gd 的做法：场景整个实例化进 SubViewport（森林 / 城市小样场景；河流篇用 room_stage.gd 建房间），
##   两个 SubViewport 轮流，镜头每镜慢慢平移 DRIFT 像素。人都是现成精灵：npc_generic.gd 读 art/characters（小兔子 = 兔子缩 0.57，
##   和第一章 rabbit_kit 一样，art/characters/rabbit_kit/ 有了原尺寸图就不缩；小水母同理看 jellyfish_small/；母兔的蝴蝶结照 story_runner._generic），鹿 / 弥洛是森林小样里自带的 Deer / Snake 节点。
##   道具用现成的图（art/forest_story、art/forest_side）。不画新图。
## 时长：第一镜从结局画面上淡进来（IN），每镜从开始出现到下一镜开始盖上来 HOLD 秒（列车 TRAIN_HOLD），换镜方格 SWAP 秒
##   （和制作人员、fade_to pixel 同一套：16 像素一格、8 档）；最后一镜淡到黑（OUT），黑着交回剧本。整段约 40 秒。
## 不出对话框、没有字，晨不出现（小样场景里的晨藏起来，只拿来当鹿 / 弥洛朝哪看的目标）。
## 声音：配乐换成 forest（第一章树屋那首），和结局正在响的声音交叉淡进来；环境声（SFX 总线）跟着压低 DUCK dB，
##   淡到黑的时候平滑地放回去；end_chapter 再把 forest 交叉到 theme（制作人员那首）。全程不留真空。
## 不能跳：level_forest.gate_event 看 story.montage_ui，Esc / 齿轮都不开设置；按键、点击被剧情吃掉（没有对话框可点）。
##   F8 开发者面板的「跳过」走 dev_skip（只给开发用）。
## 自动玩照真实时长放（游戏时间），打印 MONTAGE shot … / MONTAGE done …（总时长、放了哪几镜、哪几镜是好结果）。

signal finished

const ROOM_GD := preload("res://scripts/room_stage.gd")
const NPC_GD := preload("res://scripts/npc_generic.gd")
const BGM_GD := preload("res://scripts/bgm.gd")
const TEX_FRUIT := preload("res://art/forest_side/fruit.png")          # 两颗 9×9：0 红、1 灰
const TEX_HOUSE := preload("res://art/forest_story/empty_house.png")   # 林子里的小屋 110×80
const TEX_LAMP := preload("res://art/forest_story/placed_lamp.png")    # 摆回窗台的油灯 9×15
const TEX_SIGN := preload("res://art/forest_story/placed_sign.png")    # 路标 4 帧 26×43
const TEX_FOG := preload("res://art/forest_story/fog_bank.png")        # 坡地的雾 480×120
const TEX_HOOF := preload("res://art/forest_side/hoof_glow.png")       # 雾里发光的蹄印 41×10

const SCENES := {"forest": "res://scenes/forest_test.tscn"}
const HIDE := ["Chen", "Snake", "Deer"]   # 小样场景里自带的人：先都藏起来，哪一镜要用再放出来

const IN := 1.6              # 第一镜从结局画面上淡进来
const HOLD := 4.2            # 每镜：从开始出现（方格开始盖）到下一镜开始盖上来；整屏完整停 HOLD − SWAP ≈ 3.4 秒
const TRAIN_HOLD := 5.0      # 列车那一镜长一点（第一镜，回看从这里开始）
const SWAP := 0.8            # 方格换镜（8 档 × 0.1 秒）
const OUT := 1.8             # 最后一镜淡到黑
const PREBUILD := 1.0        # 换镜前多久把下一镜建好（建场景那一帧可能卡一下，别卡在方格中间）
const DRIFT := 16.0          # 每镜镜头往右平移多少像素（sine 缓起缓停）
const CELL := 16
const STEPS := 8
const MUSIC := "forest"
const MUSIC_FADE := 3.0
const DUCK := 16.0           # 环境声压低多少 dB
const DUCK_SEC := 2.5
const COLD := Color(0.74, 0.78, 0.85)   # 没做任务那一版：整屏压暗、偏冷
const F_GROUND := 229.0      # forest_test 里人脚底的 y（场景里晨、蛇女、鹿都在 229）
const WARM := Color(0.98, 0.78, 0.48)

var shots: Array = []
var _slots: Array = [{}, {}]
var _shown: TextureRect
var _mix: Control
var _mix_k := 0
var _mix_tex: Texture2D
var _veil: ColorRect
var _t := 0.0
var _skip := false
var _ducked := false
var _sfx_db := 0.0
var _good: Array = []


## 这一局要放的镜头（按 flag 选两版）。done = 做了这个支线
static func shots_for_state() -> Array:
	var sa_any: bool = StoryState.has("sa_lamp_done") or StoryState.has("sa_radio_done") or StoryState.has("sa_sign_done")
	return [
		{"id": "train", "bg": "home_train", "cam": Vector2(240, 0), "hold": TRAIN_HOLD, "drift": 0.0, "done": true},
		{"id": "rabbit", "bg": "forest", "cam": Vector2(300, 135), "done": StoryState.has("c1_rabbit_helped")},
		{"id": "toucan", "bg": "forest", "cam": Vector2(560, 135), "done": StoryState.has("sb_toucan_done")},
		{"id": "deer", "bg": "forest", "cam": Vector2(420, 135), "done": StoryState.has("sb_slope_done")},
		{"id": "hut", "bg": "forest", "cam": Vector2(660, 135), "done": sa_any},
		{"id": "ting", "bg": "river_bank", "cam": Vector2(400, 0), "done": StoryState.has("river_ting_seen")},
		{"id": "rat_chef", "bg": "market", "cam": Vector2(1080, 0), "done": StoryState.has("met_rat_chef")},
		{"id": "jellyfish", "bg": "stairwell", "cam": Vector2(240, 0), "done": StoryState.has("jelly_blessed")},
		{"id": "niff", "bg": "river_bank", "cam": Vector2(1330, 0), "done": StoryState.has("river_cup_traced")},
	]


## 放完返回（最后停在黑上）。调用的人等它返回以后再把下面盖黑、删掉这一层
func play() -> void:
	size = Vector2(480, 270)
	mouse_filter = Control.MOUSE_FILTER_STOP
	shots = shots_for_state()
	for i in 2:
		var vp := SubViewport.new()
		vp.size = Vector2i(480, 270)
		vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
		vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		add_child(vp)
		_slots[i] = {"vp": vp}
	_shown = TextureRect.new()
	_shown.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_shown.size = size
	_shown.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_shown)
	_mix = Control.new()
	_mix.size = size
	_mix.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mix.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_mix.draw.connect(_draw_mix)
	add_child(_mix)
	_veil = ColorRect.new()
	_veil.size = size
	_veil.color = Color(0, 0, 0, 0)
	_veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_veil)
	BGM_GD.get_bgm(get_tree()).play(MUSIC, NAN, MUSIC_FADE)
	_duck(true)
	# 第一镜：整屏从结局画面上淡进来
	_build_slot(0, 0)
	await get_tree().process_frame
	var sl0: Dictionary = _slots[0]
	sl0["live"] = true
	_shown.texture = (sl0["vp"] as SubViewport).get_texture()
	modulate.a = 0.0
	await get_tree().process_frame                  # SubViewport 先画一帧，别淡进来一张空图
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 1.0, IN).set_trans(Tween.TRANS_SINE)
	print("MONTAGE shot 0 %s good=%s t=%.1f" % [shots[0]["id"], shots[0]["done"], _t])
	for i in shots.size():
		var s := i % 2
		await _hold(i, s)
		if i + 1 >= shots.size():
			break
		if (_slots[1 - s] as Dictionary).get("world") == null:
			_build_slot(1 - s, i + 1)
		print("MONTAGE shot %d %s good=%s t=%.1f" % [i + 1, shots[i + 1]["id"], shots[i + 1]["done"], _t])
		await _swap(1 - s)
		_free_slot(s)
	# 最后一镜淡到黑；环境声在黑里平滑地放回去（end_chapter 自己再管引擎声、配乐）
	var out := create_tween()
	out.tween_property(_veil, "color:a", 1.0, 0.3 if _skip else OUT).set_trans(Tween.TRANS_SINE)
	_duck(false, OUT + 1.0)
	await out.finished
	for d in shots:
		if bool(d["done"]):
			_good.append(str(d["id"]))
	print("MONTAGE done shots=%d t=%.1fs good=%s" % [shots.size(), _t, ",".join(_good)])
	finished.emit()


## 开发者面板「跳过」：剩下的每镜很快过完（玩家没有办法跳）
func dev_skip() -> void:
	_skip = true


func _hold(i: int, s: int) -> void:
	var sl: Dictionary = _slots[s]
	var hold := float(sl.get("hold", HOLD))
	if i == 0:
		hold += IN - SWAP                          # 第一镜是淡进来的（比方格慢），整屏停的时间和别的镜一样
	while float(sl.get("t", 0.0)) < hold and not (_skip and float(sl.get("t", 0.0)) > 0.3):
		if i + 1 < shots.size() and float(sl.get("t", 0.0)) >= hold - PREBUILD and (_slots[1 - s] as Dictionary).get("world") == null:
			_build_slot(1 - s, i + 1)
		await get_tree().process_frame


## 换镜：下一镜用方格一格一格盖上来；盖满以后它就是整屏的那一镜
func _swap(to: int) -> void:
	var sl: Dictionary = _slots[to]
	sl["live"] = true
	sl["t"] = 0.0
	_mix_tex = (sl["vp"] as SubViewport).get_texture()
	for k in STEPS:
		_mix_k = k + 1
		_mix.queue_redraw()
		await get_tree().create_timer((0.2 if _skip else SWAP) / STEPS, false).timeout
	_shown.texture = _mix_tex
	_mix_k = 0
	_mix.queue_redraw()


func _draw_mix() -> void:
	if _mix_k <= 0 or _mix_tex == null:
		return
	var cols := int(ceil(480.0 / CELL))
	var rows := int(ceil(270.0 / CELL))
	for cy in rows:
		for cx in cols:
			if absi(hash(Vector2i(cx, cy))) % STEPS < _mix_k:          # 每格第几档盖上（同一格永远同一档，和制作人员一样）
				var r := Rect2(cx * CELL, cy * CELL, CELL, CELL)
				_mix.draw_texture_rect_region(_mix_tex, r, r)


func _process(delta: float) -> void:
	_t += delta
	for sl in _slots:
		if not sl.get("live", false) or sl.get("world") == null:
			continue
		sl["t"] = float(sl["t"]) + delta
		var t: float = sl["t"]
		var cam: Camera2D = sl["cam"]
		var span := float(sl.get("hold", HOLD)) + SWAP
		cam.position = ((sl["cam_from"] as Vector2) + Vector2(float(sl.get("drift", DRIFT)) * _ease(t / span), 0)).round()
		var st = sl.get("stage")
		if st != null:
			st.update(delta, cam.position)
		var fn := "_tick_" + str((sl["sd"] as Dictionary)["id"])
		if has_method(fn):
			call(fn, sl, t, delta)


static func _ease(k: float) -> float:
	return 0.5 - 0.5 * cos(clampf(k, 0.0, 1.0) * PI)


# ======================================================================= 建一镜
func _build_slot(s: int, i: int) -> void:
	_free_slot(s)
	var sd: Dictionary = shots[i]
	var vp: SubViewport = _slots[s]["vp"]
	var bg := str(sd["bg"])
	var cam: Vector2 = sd["cam"]
	var world: Node2D
	var stage: Node2D = null
	var camera: Camera2D
	var ground := F_GROUND
	if SCENES.has(bg):
		world = (load(SCENES[bg]) as PackedScene).instantiate()
		world.set_script(null)                     # 小样的根脚本读命令行、管晨和镜头：这里不要
		for n in HIDE:
			var c := world.get_node_or_null(n)
			if c != null:
				(c as CanvasItem).visible = false
				if n == "Chen":
					c.process_mode = Node.PROCESS_MODE_DISABLED
		camera = world.get_node_or_null("Camera") as Camera2D
		if camera == null:
			camera = Camera2D.new()
			world.add_child(camera)
	else:
		world = Node2D.new()
		stage = ROOM_GD.new()
		stage.setup(bg, null)
		world.add_child(stage)
		camera = Camera2D.new()
		world.add_child(camera)
		cam = Vector2(stage.clamp_cam_x(stage.origin.x + cam.x), stage.cam_y())
	vp.add_child(world)
	camera.position = cam
	camera.make_current()
	if stage != null:
		stage.update(0.0, cam)
	var sl := {"vp": vp, "world": world, "stage": stage, "cam": camera, "cam_from": cam, "ground": ground, "t": 0.0,
		"live": false, "hold": float(sd.get("hold", HOLD)), "drift": float(sd.get("drift", DRIFT)), "sd": sd, "n": {}}
	if not bool(sd["done"]):
		world.modulate = COLD
	_slots[s] = sl
	var fn := "_build_" + str(sd["id"])
	if has_method(fn):
		call(fn, sl, bool(sd["done"]))


func _free_slot(s: int) -> void:
	var sl: Dictionary = _slots[s]
	var w = sl.get("world")
	if w != null and is_instance_valid(w):
		w.queue_free()
	_slots[s] = {"vp": sl["vp"]}


## 屏幕 x → 这一镜的世界 x（小样场景）/ 房间 x（河流房间）
func _wx(sl: Dictionary, sx: float) -> float:
	var x := (sl["cam_from"] as Vector2).x - 240.0 + sx
	var st = sl.get("stage")
	if st != null:
		x -= (st as Node2D).position.x
	return roundf(x)


## 把一个节点放到地上（dy = 往上抬多少，负数往上）。小样场景：插在晨前面一层（人在近景的树后面）；房间：挂在 room_stage 下面
func _put(sl: Dictionary, n: Node2D, sx: float, dy := 0.0) -> void:
	var x := _wx(sl, sx)
	var st = sl.get("stage")
	if st != null:
		n.position = Vector2(x, roundf(st.ground_local(x)) + 1.0 + dy)
		st.add_node(n, 0)
	else:
		var w: Node2D = sl["world"]
		n.position = Vector2(x, float(sl["ground"]) + dy)
		w.add_child(n)
		var c := w.get_node_or_null("Chen")
		if c != null:
			w.move_child(n, c.get_index())


func _npc(sl: Dictionary, who: String, sx: float, dir: int, anim := "idle", sc := 1.0, dy := 0.0) -> Node2D:
	var n: Node2D = NPC_GD.new()
	n.setup(who)
	if sc != 1.0:
		n.scale = Vector2(sc, sc)
	n.call("face", dir)                              # 进树之前转好（阿汀的 turn_fade 只在画面里转身时才淡）
	n.call("play", anim)
	_put(sl, n, sx, dy)
	return n


## 小样场景里自带的鹿 / 弥洛：放到 sx，朝 look_sx 看（藏着的晨挪到那儿，它们自己会转向晨）
func _own(sl: Dictionary, nm: String, sx: float, look_sx: float) -> Node2D:
	var w: Node2D = sl["world"]
	var n := w.get_node_or_null(nm) as Node2D
	var c := w.get_node_or_null("Chen") as Node2D
	if n == null:
		return null
	if c != null:
		c.position.x = _wx(sl, look_sx)
	n.position.x = _wx(sl, sx)
	if n.has_method("place"):
		n.call("place", n.position.x)
	if n.has_method("_set_facing"):
		n.call("_set_facing", 1 if look_sx > sx else -1)
	n.visible = true
	return n


func _sprite(tex: Texture2D, region := Rect2()) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = tex
	s.centered = false
	s.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	if region.size != Vector2.ZERO:
		s.region_enabled = true
		s.region_rect = region
	return s


func _drawer(fn: Callable, add := false) -> Node2D:
	var n := Node2D.new()
	if add:
		var m := CanvasItemMaterial.new()
		m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		n.material = m
	n.draw.connect(fn.bind(n))
	return n


## 画的节点属于哪一镜（draw 回调里拿那一镜的状态）
func _slot_of(n: Node) -> Dictionary:
	for sl in _slots:
		var w = sl.get("world")
		if w != null and is_instance_valid(w) and (w as Node).is_ancestor_of(n):
			return sl
	return {}


# ======================================================================= 森林
## 兔子：教会了舞步（c1_rabbit_helped）= 首领、母兔、一窝小兔子（第一章只有三只，这里六只，过了一阵子又多了）；没教 = 首领一个
func _build_rabbit(sl: Dictionary, done: bool) -> void:
	var chief := _npc(sl, "rabbit", 236, 1)
	if not done:
		return
	var doe := _npc(sl, "rabbit_doe", 284, -1)
	var bow := Polygon2D.new()                      # 母兔的蝴蝶结：和 story_runner._generic 一样
	bow.polygon = PackedVector2Array([Vector2(-6, -4), Vector2(0, -1), Vector2(6, -4), Vector2(6, 3), Vector2(0, 1), Vector2(-6, 3)])
	bow.position = Vector2(1, -44)
	bow.color = Color("#d88a9c")
	doe.add_child(bow)
	var kits: Array = []
	var at := [[150, 1], [178, 1], [206, 1], [318, -1], [346, -1], [380, -1]]
	for i in at.size():
		var k := _npc(sl, "rabbit_kit_%d" % (i + 1), float(at[i][0]), int(at[i][1]), "idle", 1.0 if NPC_GD.has_own_kit_art() else 0.57)
		kits.append(k)
	sl["n"] = {"chief": chief, "kits": kits, "next": [0.5, 1.1, 0.8, 1.6, 0.3, 2.0]}


func _tick_rabbit(sl: Dictionary, t: float, _delta: float) -> void:
	var n: Dictionary = sl["n"]
	if not n.has("kits"):
		return
	var nx: Array = n["next"]
	var kits: Array = n["kits"]
	for i in kits.size():
		if t >= float(nx[i]):
			(kits[i] as Node2D).call("hop", 1 + (i % 2))
			nx[i] = float(nx[i]) + 1.3 + 0.37 * float((i * 5) % 4)     # 一只一只错开着蹦，不齐步


## 大嘴鸟：陪它接过果子（sb_toucan_done）= 树桩边一小堆果子；没接 = 它自己蹲着
func _build_toucan(sl: Dictionary, done: bool) -> void:
	_npc(sl, "toucan", 250, -1)
	if not done:
		return
	var pile := [[268, 0, 0], [277, 0, 0], [286, 0, 1], [272, -6, 0], [281, -6, 0], [277, -12, 0]]
	for p in pile:
		var s := _sprite(TEX_FRUIT, Rect2(9 * int(p[2]), 0, 9, 9))
		var n2 := Node2D.new()
		n2.add_child(s)
		s.position = Vector2(-4, -9)
		_put(sl, n2, float(p[0]), float(p[1]))


## 鹿：跟着蹄印走过雾（sb_slope_done）= 雾里一串蹄印还亮着、鹿站在雾跟前；没去 = 只有雾，鹿在一边低头
func _build_deer(sl: Dictionary, done: bool) -> void:
	var w: Node2D = sl["world"]
	var fog := _sprite(TEX_FOG)
	fog.modulate.a = 0.9
	var holder := Node2D.new()
	holder.add_child(fog)
	fog.position = Vector2(-120, -112)
	_put(sl, holder, 300, 6)
	if done:
		var prints: Array = []
		for i in 4:
			var h := _sprite(TEX_HOOF)
			var add := CanvasItemMaterial.new()
			add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
			h.material = add
			var hn := Node2D.new()
			hn.add_child(h)
			h.position = Vector2(-20, -7)
			_put(sl, hn, 236.0 + 44.0 * i, 1)
			prints.append(h)
		sl["n"] = {"prints": prints}
		_own(sl, "Deer", 190, 400)
	else:
		_own(sl, "Deer", 150, 60)
	if w.get_node_or_null("Deer") != null:
		w.move_child(holder, w.get_node("Deer").get_index())    # 雾在鹿后面


func _tick_deer(sl: Dictionary, t: float, _delta: float) -> void:
	var n: Dictionary = sl["n"]
	if not n.has("prints"):
		return
	var pr: Array = n["prints"]
	for i in pr.size():
		(pr[i] as CanvasItem).modulate.a = 0.45 + 0.4 * (0.5 + 0.5 * sin(t * 2.2 - float(i) * 0.9))   # 一个接一个往雾里亮过去


## 林子里的小屋（弥洛修好的三样东西送回去了：sa_lamp_done / sa_radio_done / sa_sign_done 任一）：
## 油灯摆回窗台点着、窗里暖光一明一暗；路标插回底座（sa_sign_done）；弥洛在屋前。没送 = 屋子黑着
func _build_hut(sl: Dictionary, done: bool) -> void:
	var house := Node2D.new()
	var hs := _sprite(TEX_HOUSE)
	hs.position = Vector2(-55, -80)
	house.add_child(hs)
	_put(sl, house, 300, 1)
	if done and StoryState.has("sa_lamp_done"):
		var glow := _drawer(_draw_hut_glow, true)
		glow.position = Vector2(-28, -33)            # 左边那扇窗的中间
		house.add_child(glow)
		var lamp := _sprite(TEX_LAMP)
		lamp.position = Vector2(-33 - 4, -26 - 15)   # 和 forest_side_a 的 sa_placed_lamp（dx −33、dy −26）一样摆在窗台上
		house.add_child(lamp)
		sl["n"] = {"glow": glow}
	if done and StoryState.has("sa_sign_done"):
		var sign := Node2D.new()
		var ss := _sprite(TEX_SIGN, Rect2(0, 0, 26, 43))
		ss.position = Vector2(-13, -43)
		sign.add_child(ss)
		_put(sl, sign, 410, 1)
	_own(sl, "Snake", 176, 300)


func _tick_hut(sl: Dictionary, _t2: float, _delta: float) -> void:
	var n: Dictionary = sl["n"]
	if n.has("glow"):
		(n["glow"] as Node2D).queue_redraw()


func _draw_hut_glow(n: Node2D) -> void:
	var sl := _slot_of(n)
	var t := float(sl.get("t", 0.0))
	var b := 0.88 + 0.12 * sin(t * 1.7)
	n.draw_rect(Rect2(-9, -6, 18, 12), Color(WARM, 0.42 * b))
	n.draw_circle(Vector2.ZERO, 22.0, Color(WARM, 0.05 * b))
	n.draw_circle(Vector2.ZERO, 13.0, Color(WARM, 0.09 * b))
	n.draw_circle(Vector2(0, 26), 16.0, Color(WARM, 0.04 * b))   # 窗下地上一点光


# ======================================================================= 河流篇
## 阿汀：把录像带拿给他看过（river_ting_seen，「第十三条留给外地人，你定」）= 河岸上妮芙陪着他（第十二条：罚陪妮芙喝淡茶）；没去 = 他一个人站岗
func _build_ting(sl: Dictionary, done: bool) -> void:
	_npc(sl, "ting", 250, -1)
	if done:
		_npc(sl, "niff", 160, 1)


## 料理鼠妈：帮她看过锅（met_rat_chef）= 摊前有两个吃饭的人；没去 = 她一个人守着锅
func _build_rat_chef(sl: Dictionary, done: bool) -> void:
	_npc(sl, "rat_chef", 255, -1)
	if done:
		_npc(sl, "passerby", 198, 1, "laugh")
		_npc(sl, "resident", 312, -1, "talk")


## 水母：给过东西、被祝了一长串寿（jelly_blessed）= 身边多了几只小水母；没给 = 一只在楼梯间里漂
func _build_jellyfish(sl: Dictionary, done: bool) -> void:
	_npc(sl, "jellyfish", 300, -1)
	if done:
		var own := FileAccess.file_exists("res://art/characters/jellyfish_small/jellyfish_small.json")   # 小水母有了原尺寸图就用它
		var who := "jellyfish_small" if own else "jellyfish"
		_npc(sl, who, 246, 1, "idle", 1.0 if own else 0.5, -18)
		_npc(sl, who, 352, -1, "idle", 1.0 if own else 0.5, -30)
		_npc(sl, who, 214, 1, "idle", 1.0 if own else 0.4, -44)


## 妮芙：陪她翻过来客册（river_cup_traced，杯子留着等人来拿）= 家门口转着圈；没翻 = 在门口漂着
func _build_niff(sl: Dictionary, done: bool) -> void:
	var n := _npc(sl, "niff", 210, 1)
	sl["n"] = {"niff": n, "spun": not done}


func _tick_niff(sl: Dictionary, t: float, _delta: float) -> void:
	var n: Dictionary = sl["n"]
	if not bool(n.get("spun", true)) and t >= 1.2:
		n["spun"] = true
		(n["niff"] as Node2D).call("play", "laugh")       # niff.json：laugh → spin（转一圈）


# ======================================================================= 声音
func _duck(on: bool, sec := DUCK_SEC) -> void:
	var i := AudioServer.get_bus_index("SFX")
	if i < 0:
		return
	if on and not _ducked:
		_ducked = true
		_sfx_db = AudioServer.get_bus_volume_db(i)
		var from := _sfx_db
		get_tree().create_tween().tween_method(func(v: float): AudioServer.set_bus_volume_db(i, v), from, from - DUCK, sec)
	elif not on and _ducked:
		_ducked = false
		var cur := AudioServer.get_bus_volume_db(i)
		get_tree().create_tween().tween_method(func(v: float): AudioServer.set_bus_volume_db(i, v), cur, _sfx_db, sec)


## 中途被扔掉（换章、F8 重开）：环境声平滑地升回去（SceneTree 的 tween：这个节点已经要没了）
func _exit_tree() -> void:
	if _ducked:
		_ducked = false
		var i := AudioServer.get_bus_index("SFX")
		if i >= 0:
			var cur := AudioServer.get_bus_volume_db(i)
			var to := _sfx_db
			get_tree().create_tween().tween_method(func(v: float): AudioServer.set_bus_volume_db(i, v), cur, to, 0.6)
