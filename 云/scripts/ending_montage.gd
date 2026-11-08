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
## 11-08 作者「直接显示他们的现状就可以了；泥芙家内部、Milo 家内部，也要包括可能没出现的云层和芦苇地；展示的时间快一点」
##   （真结局的尾声回访照旧保留：「原来只有真结局回访吗？既然如此保留」）。弥洛那镜改成树屋室内
##   （treehouse_back + 屋里的物件，弥洛在工作台前），泥芙那镜改成泥芙家室内（river_home，前墙藏掉，泥芙在桌边泡茶），
##   最后加云层小镇（镇民在喷泉广场）和芦苇地（白鹭、风吹芦苇；这局走了真结局 final_ending_1 才有大象）两镜，谁都放。
##   每镜 2.8 秒（整屏停约 2.2 秒）、列车 3.5 秒、方格 0.6 秒，整段约 34 秒。
##   鹿那镜的雾（作者「最后闪回的鹿的雾气有 bug」）：原来是一张 fog_bank 原图直接盖在主层前面——两头没有分档淡出（整块方形）、
##   下沿直边露在地面上、盖住主层的树、也不会动。改成和森林坡地一样：fog_bank 在 Mid 和 Main 之间（主层地面盖住下沿，压进地里 4 像素）、
##   两头 EDGE_FADE 分档淡掉，再加 story_world 那两层会漂的噪声雾（坡地的浓度 fog_k = 0.25）。

signal finished

const ROOM_GD := preload("res://scripts/room_stage.gd")
const NPC_GD := preload("res://scripts/npc_generic.gd")
const CHEN_GD := preload("res://scripts/chen.gd")          # 森林地面公式 ground_y（小样场景的地面不是平的）
const BGM_GD := preload("res://scripts/bgm.gd")
const TEX_FRUIT := preload("res://art/forest_side/fruit.png")          # 两颗 9×9：0 红、1 灰
const TEX_HOUSE := preload("res://art/forest_story/empty_house.png")   # 林子里的小屋 110×80
const TEX_LAMP := preload("res://art/forest_story/placed_lamp.png")    # 摆回窗台的油灯 9×15
const TEX_SIGN := preload("res://art/forest_story/placed_sign.png")    # 路标 4 帧 26×43
const TEX_FOG := preload("res://art/forest_story/fog_bank.png")        # 坡地的雾 480×120
const TEX_HOOF := preload("res://art/forest_side/hoof_glow.png")       # 雾里发光的蹄印 41×10
const SW_GD := preload("res://scripts/story_world.gd")                  # 雾：EDGE_FADE_SHADER、FOG_C、浓度常数照抄它
const FOG_SHADER := preload("res://scripts/fog_noise.gdshader")
const TH_DIR := "res://art/forest_story/"                                # 树屋：treehouse_back.png / room_light.png / treehouse.json

const SCENES := {"forest": "res://scenes/forest_test.tscn"}
const HIDE := ["Chen", "Snake", "Deer"]   # 小样场景里自带的人：先都藏起来，哪一镜要用再放出来

const IN := 1.6              # 第一镜从结局画面上淡进来
const HOLD := 2.8            # 每镜：从开始出现（方格开始盖）到下一镜开始盖上来；整屏完整停 HOLD − SWAP ≈ 2.2 秒（11-08 作者「快一点」，原来 4.2）
const TRAIN_HOLD := 3.5      # 列车那一镜长一点（第一镜，回看从这里开始；原来 5.0）
const SWAP := 0.6            # 方格换镜（8 档 × 0.075 秒；原来 0.8）
const OUT := 1.8             # 最后一镜淡到黑
const PREBUILD := 1.0        # 换镜前多久把下一镜建好（建场景那一帧可能卡一下，别卡在方格中间）
const DRIFT := 16.0          # 每镜镜头往右平移多少像素（sine 缓起缓停）
const CELL := 16
const STEPS := 8
const MUSIC := "forest"
const KEEP_MUSIC := "gymnopedie1"     # 正在放这首就不换
const MUSIC_FADE := 3.0
const DUCK := 16.0           # 环境声压低多少 dB
const DUCK_SEC := 2.5
const COLD := Color(0.74, 0.78, 0.85)   # 没做任务那一版：整屏压暗、偏冷
const F_GROUND := 229.0      # forest_test 里人脚底的 y（场景里晨、蛇女、鹿都在 229）
const WARM := Color(0.98, 0.78, 0.48)
const SLOPE_FOG := 0.25      # 坡地的雾浓度（story_world.fog_at 在 slope 附近最多 0.25）
const TH_GROUND := 228.0     # 树屋图的锚点（底边中点）踩的地面 y（treehouse.json anchor）

var shots: Array = []
var _slots: Array = [{}, {}]
var _shown: TextureRect
var _mix: Control
var _mix_k := 0
var _mix_tex: Texture2D
var _swap_n := 0
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
		{"id": "miluo_room", "bg": "forest", "cam": Vector2(660, 135), "done": sa_any},
		{"id": "ting", "bg": "river_bank", "cam": Vector2(400, 0), "done": StoryState.has("river_ting_seen")},
		{"id": "rat_chef", "bg": "market", "cam": Vector2(1080, 0), "done": StoryState.has("met_rat_chef")},
		{"id": "jellyfish", "bg": "stairwell", "cam": Vector2(240, 0), "done": StoryState.has("jelly_blessed")},
		{"id": "niff_home", "bg": "river_bank", "house": "river_home", "cam": Vector2(210, 182), "drift": 8.0,
			"done": StoryState.has("river_cup_traced")},
		# 11-08 作者「也要包括可能没出现的云层和芦苇地」：这局去没去过都放、都是原样（不压暗）
		{"id": "town", "bg": "town", "cam": Vector2(990, 0), "done": true},
		{"id": "reed", "bg": "reed_field", "cam": Vector2(1010, 0), "done": true},
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
	# 11-08 作者「闪回的时候一直播放钢琴曲」：芦苇地 / 云层小镇两条线落地起的 gymnopedie1 一路放过回看，不切 forest；回母星那条照旧切 forest
	var bgm = BGM_GD.get_bgm(get_tree())
	if bgm.current() != KEEP_MUSIC:
		bgm.play(MUSIC, NAN, MUSIC_FADE)
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
## 11-08 作者截图：森林那镜悬空一块黑方格 = 换镜的方格没清干净。现在：最后一档整屏都画（不靠 hash 每格都轮到），
## 底下那张换过去、等它真的画出来一帧，再把覆盖层整个清掉（_mix_k = 0、_mix_tex = null、隐藏）；换镜编号防两次换镜叠在一起
func _swap(to: int) -> void:
	var sl: Dictionary = _slots[to]
	sl["live"] = true
	sl["t"] = 0.0
	_swap_n += 1
	var me := _swap_n
	_mix_tex = (sl["vp"] as SubViewport).get_texture()
	_mix.visible = true
	for k in STEPS:
		if me != _swap_n:
			return
		_mix_k = k + 1
		_mix.queue_redraw()
		await get_tree().create_timer((0.2 if _skip else SWAP) / STEPS, false).timeout
	if me != _swap_n:
		return
	_shown.texture = _mix_tex
	await get_tree().process_frame                 # 底下那张先画出来，再撤覆盖层（不闪）
	_clear_mix()


func _clear_mix() -> void:
	_mix_k = 0
	_mix_tex = null
	_mix.queue_redraw()
	_mix.visible = false
	print("MONTAGE mix_clear k=%d tex=%s vis=%s t=%.1f" % [_mix_k, _mix_tex != null, _mix.visible, _t])


func _draw_mix() -> void:
	if _mix_k <= 0 or _mix_tex == null:
		return
	if _mix_k >= STEPS:                                               # 最后一档：整屏
		_mix.draw_texture_rect_region(_mix_tex, Rect2(0, 0, 480, 270), Rect2(0, 0, 480, 270))
		return
	var cols := int(ceil(480.0 / CELL))
	var rows := int(ceil(270.0 / CELL))
	for cy in rows:
		for cx in cols:
			if absi(hash(Vector2i(cx, cy))) % STEPS < _mix_k:          # 每格第几档盖上（同一格永远同一档，和制作人员一样）
				var r := Rect2(cx * CELL, cy * CELL, CELL, CELL).intersection(Rect2(0, 0, 480, 270))    # 最下一行 256–272 夹到 270
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
		var hs = sl.get("house")
		if hs != null:
			hs.update(delta, cam.position)
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
	var house: Node2D = null
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
		if sd.has("house"):
			# 室内（泥芙家）：host 房间照建，屋子挂在 host 上；前墙藏掉 = 屋里整个看得见。cam = 屋子里的 (x, y)
			house = ROOM_GD.new()
			house.setup(str(sd["house"]), null, stage)
			world.add_child(house)
			house.house_front.visible = false
			cam = (house.origin + cam).round()
		else:
			cam = Vector2(stage.clamp_cam_x(stage.origin.x + cam.x), stage.cam_y())
		world.add_child(camera)
	vp.add_child(world)
	camera.position = cam
	camera.make_current()
	if stage != null:
		stage.update(0.0, cam)
	if house != null:
		house.update(0.0, cam)
	var sl := {"vp": vp, "world": world, "stage": stage, "house": house, "cam": camera, "cam_from": cam, "ground": ground, "t": 0.0,
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
		# 11-08 作者「大嘴鸟为什么悬空了」：原来一律放在 y 229（F_GROUND），森林地面是起伏的（228 ± 3.5），
		# 大嘴鸟那镜 x 570 的地面在 231，树桩底悬空 2 像素。改成按地面公式，和游戏里 _place 一样 round(地面) + 1
		n.position = Vector2(x, roundf(CHEN_GD.ground_y(x)) + 1.0 + dy)
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
	if sl.get("stage") == null and OS.get_cmdline_user_args().has("--story_auto"):
		print("MONTAGE_NPC %s x=%d y=%d ground=%.1f" % [who, int(n.position.x), int(n.position.y), CHEN_GD.ground_y(n.position.x)])
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
	if not NPC_GD.has_own_doe_art():                # 母兔的蝴蝶结：和 story_runner._generic 一样（有自己的图时画在像素里了）
		var bow := Polygon2D.new()
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
## 雾照森林坡地的放法（story_world：PROPS.fog_bank + _make_fog_layer），见文件头 11-08 那条
func _build_deer(sl: Dictionary, done: bool) -> void:
	var w: Node2D = sl["world"]
	var main := w.get_node_or_null("Main")
	var mid := w.get_node_or_null("Mid")
	# 后面那层会漂的雾（Mid 和 Main 之间），再是远处那堵 fog_bank，都在主层后面：主层的地面盖住雾的下沿
	var back := _fog_layer("FogBack", 0.8, 0.0, 270.0, 11, Vector2(0.006, -0.003), 1.4, 0.55,
		SW_GD.FOG_BACK_BASE + (SW_GD.FOG_BACK_A - SW_GD.FOG_BACK_BASE) * SLOPE_FOG)
	var bank := Sprite2D.new()
	bank.texture = TEX_FOG
	bank.centered = false
	bank.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	bank.offset = Vector2(-TEX_FOG.get_width() / 2, -TEX_FOG.get_height())
	bank.position = Vector2(_wx(sl, 330), float(sl["ground"]) + 1.0 + 4.0)      # 底边压进地里 4 像素（PROPS.fog_bank 的 sink）
	var sh := Shader.new()
	sh.code = SW_GD.EDGE_FADE_SHADER                                           # 左右两头分档淡掉（不是整块方形）
	var m := ShaderMaterial.new()
	m.shader = sh
	bank.material = m
	if mid != null and main != null:
		w.add_child(back)
		w.move_child(back, mid.get_index() + 1)
		w.add_child(bank)
		w.move_child(bank, back.get_index() + 1)
	else:
		w.add_child(back)
		w.add_child(bank)
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
	# 前面那层很淡的雾：角色前面、Front 层后面，只在下半屏（和森林一样，鹿还是看得清）
	var front := _fog_layer("FogFront", 1.2, 135.0, 135.0, 29, Vector2(0.014, 0.0), 2.0, 0.0,
		SW_GD.FOG_FRONT_BASE + (SW_GD.FOG_FRONT_A - SW_GD.FOG_FRONT_BASE) * SLOPE_FOG)
	w.add_child(front)
	var fl := w.get_node_or_null("Front")
	if fl != null:
		w.move_child(front, fl.get_index())


## 和 story_world._make_fog_layer 一样的一层雾（Parallax2D 横向循环 + 噪声 shader 随时间漂）
func _fog_layer(nm: String, scroll: float, y0: float, h: float, seed: int, speed: Vector2, gpow: float, gmin: float, density: float) -> Parallax2D:
	var p := Parallax2D.new()
	p.name = nm
	p.scroll_scale = Vector2(scroll, 1.0)
	p.repeat_size = Vector2(480, 0)
	p.repeat_times = 3
	var nz := FastNoiseLite.new()
	nz.seed = seed
	nz.frequency = 0.012
	var tex := NoiseTexture2D.new()
	tex.width = 480
	tex.height = int(h)
	tex.seamless = true
	tex.noise = nz
	var mat := ShaderMaterial.new()
	mat.shader = FOG_SHADER
	mat.set_shader_parameter("noise_texture", tex)
	mat.set_shader_parameter("speed", speed)
	mat.set_shader_parameter("gradient_pow", gpow)
	mat.set_shader_parameter("gradient_min", gmin)
	mat.set_shader_parameter("density", density)
	var r := ColorRect.new()
	r.color = SW_GD.FOG_C
	r.position = Vector2(0, y0)
	r.size = Vector2(480, h)
	r.material = mat
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_child(r)
	return p


func _tick_deer(sl: Dictionary, t: float, _delta: float) -> void:
	var n: Dictionary = sl["n"]
	if not n.has("prints"):
		return
	var pr: Array = n["prints"]
	for i in pr.size():
		(pr[i] as CanvasItem).modulate.a = 0.45 + 0.4 * (0.5 + 0.5 * sin(t * 2.2 - float(i) * 0.9))   # 一个接一个往雾里亮过去


## 弥洛的树屋室内（11-08 作者「Milo 家内部」）：treehouse_back（树干 + 屋里）+ 屋里的物件 + room_light，前墙不放（剖面看进去）；
## 弥洛在右边工作台前。修好的油灯 / 路标送回去了（sa_lamp_done / sa_sign_done）= 屋里就没有了、窗边暖光一明一暗；
## 一样都没送（没做）= 油灯、路标还在架子上，整屏压暗（COLD）
func _build_miluo_room(sl: Dictionary, done: bool) -> void:
	var w: Node2D = sl["world"]
	var cfg = JSON.parse_string(FileAccess.get_file_as_string(TH_DIR + "treehouse.json"))
	var objs: Dictionary = (cfg as Dictionary).get("objects", {}) if cfg is Dictionary else {}
	var house := Node2D.new()
	house.position = Vector2(_wx(sl, 240), TH_GROUND)                       # 锚点 = 底边中点
	var back_tex := load(TH_DIR + "treehouse_back.png") as Texture2D
	var bk := _sprite(back_tex)
	bk.position = Vector2(-back_tex.get_width() / 2, -back_tex.get_height())
	house.add_child(bk)
	var skip := ["pipe_steam", "room_lamp_mark"]
	if StoryState.has("sa_lamp_done"):
		skip.append("room_lamp")
	if StoryState.has("sa_sign_done"):
		skip.append("room_sign")
	if StoryState.has("sa_radio_done"):
		skip.append("room_radio")
	for oid in objs:
		if str(oid) in skip:
			continue
		var o: Dictionary = objs[oid]
		var p := TH_DIR + str(oid) + ".png"
		if not ResourceLoader.exists(p):
			continue
		var tx := load(p) as Texture2D
		var fw := int(o.get("w", tx.get_width()))
		var sp := _sprite(tx, Rect2(0, 0, fw, tx.get_height()))
		sp.position = Vector2(float(o.get("x", 0)), float(o.get("y", 0)))
		house.add_child(sp)
	if ResourceLoader.exists(TH_DIR + "room_light.png"):
		var lt := load(TH_DIR + "room_light.png") as Texture2D
		var ls := _sprite(lt)
		ls.position = Vector2(-lt.get_width() / 2, -lt.get_height())
		house.add_child(ls)
	if done:
		var glow := _drawer(_draw_hut_glow, true)
		glow.position = Vector2(-55, -60)            # 窗（back 图里左边那扇）
		house.add_child(glow)
		sl["n"] = {"glow": glow}
	w.add_child(house)
	var sn := w.get_node_or_null("Snake")
	if sn != null:
		w.move_child(house, sn.get_index())           # 屋子在弥洛后面
	_own(sl, "Snake", 240 + 84, 240 + 140)            # 工作台前，朝着工作台


func _tick_miluo_room(sl: Dictionary, _t2: float, _delta: float) -> void:
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
## 阿汀：把录像带拿给他看过（river_ting_seen，「第十三条留给外地人，你定」）= 河岸上泥芙陪着他（第十二条：罚陪泥芙喝淡茶）；没去 = 他一个人站岗
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


## 泥芙家室内（11-08 作者「泥芙家内部」）：泥芙在桌边泡茶。陪她翻过来客册（river_cup_traced）= 桌上两杯茶（等人来喝）、
## 泥芙转一圈；没翻 = 桌上只有那只杯子，整屏压暗（COLD）
func _build_niff_home(sl: Dictionary, done: bool) -> void:
	var hs: Node2D = sl["house"]
	if hs == null:
		return
	if hs.has_object("river_home_table"):
		hs.set_prop("river_home_table", "two_cups_tea" if done else "cup_stays", true)
	if hs.has_object("river_home_hourglass"):
		hs.set_prop("river_home_hourglass", "running", true)       # 泡茶计时
	var n: Node2D = NPC_GD.new()
	n.setup("niff")
	n.call("face", -1)                                          # 朝着桌子 / 厨房
	n.call("play", "idle")
	n.position = Vector2(float(hs.mx("river_home_niff")) - hs.origin.x, roundf(hs.ground_local(float(hs.mx("river_home_niff")) - hs.origin.x)) + 1.0)
	hs.add_node(n, 0)
	sl["n"] = {"niff": n, "spun": not done}


func _tick_niff_home(sl: Dictionary, t: float, _delta: float) -> void:
	var n: Dictionary = sl["n"]
	if n.has("niff") and not bool(n.get("spun", true)) and t >= 1.0:
		n["spun"] = true
		(n["niff"] as Node2D).call("play", "laugh")       # niff.json：laugh → spin（转一圈）


# ======================================================================= 云层星（11-08 新加：谁都放）
## 云层小镇：镇民在喷泉广场（喷泉、水车、风车由 cloud_town.gd 自己动）
func _build_town(sl: Dictionary, _done: bool) -> void:
	_npc(sl, "townsfolk", 168, 1)
	_npc(sl, "townsfolk", 214, -1, "idle")
	_npc(sl, "townsfolk", 318, -1)


## 芦苇地：白鹭、风吹芦苇、绒毛（reed_field.gd 自己动）。这局走了真结局（final_ending_1）= 大象在水边吃草；没走 = 只有芦苇地
func _build_reed(sl: Dictionary, _done: bool) -> void:
	if StoryState.has("final_ending_1"):
		_npc(sl, "elephant", 320, -1)


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
