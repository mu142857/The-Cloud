extends Node2D
## 森林章节的「地图」：markers（世界 x）、左右不可见的墙、场景物件（art/forest_story/ 的图，缺图一律用色块占位）、
## 树屋（森林里 treehouse 那里的一个剖面小屋）、旧路段和坡地的雾。由 level_forest.gd 建，story_runner.gd 用。
## 整个游戏是正侧面、平面、视差卷轴：没有透视，屋子也是一张正侧面的剖面。
##
## 坐标：森林里的东西锚点 = 底边中点踩在地面上（地面 = 晨的 ground_fn）。
## markers：下面 DEFAULT_MARKERS 是设计文档 docs/forest_chapter.md 里的表，剧本 JSON 的 "markers" 覆盖它。
##   物件放哪：剧本里有和物件同名的 marker 就放那（branch_a、hoofprints、depressions、fog_bank……），都没有就用 PROPS 里的默认。
## 树屋（room = treehouse）：
##   art/forest_story/treehouse_back.png  树干 + 屋内（一直显示，在晨后面）
##   art/forest_story/treehouse_front.png 前墙（盖在屋内东西和弥洛上面、在晨和鹿后面；晨进屋时淡出、出屋时淡回来）
##   art/forest_story/treehouse.json      尺寸、屋内地板、可走范围、门 x、物件位置，都相对图中心（图的锚点 = 底边中点踩在
##     treehouse marker 的地面上）。认这些写法（缺哪项用占位的默认）：
##       {"size": [w, h], "floor": 地板那一行的 dy, "walk": [左 dx, 右 dx], "door": 门的 dx,
##        "props": {"radio": [dx, dy], "pipe_a": [dx, dy], …}}   （floor_y / walk_range / door_x / objects / spots 也认；
##        物件的点 = 那件东西底边中点；值可以是 [dx, dy]、{"x", "y"} 或只给 dx（y 就在地板上））
##   剧本里 room_* 的 marker 原来是按 480 宽一屏写的房间内 x：json 里有同名物件（去掉 room_）就用 json 的位置，
##   没有就按比例压进屋内可走范围（占位）。treehouse 和 room_door 这两个 marker 都改成门的 x（在门口互动、进出屋不跳）。
##   进屋 / 出屋（剧本 fade_to room=treehouse / 从屋里 fade_to forest 到屋子附近）不黑屏：前墙淡出 / 淡入 0.5 秒，
##   晨的左右范围限制在屋内，镜头照常跟随、往屋子中心收一点（level_forest.gd）。
## 不是图的「物件」（剧本 prop 步骤也能用）：fog（thick = 旧路的雾更浓）、ship（launch = 飞船要起飞了，关卡处理）、
##   pipes（fixed = 管道修好，细白汽没了）。
## 物件：PROPS 表。state（剧本的 prop 步骤）怎么变：先看表里的 states，再看有没有 <图名>_<state>.png，
##   再看 FRAME_STATES（同一张图里的第几帧），都没有就把占位色块换个深浅（看得出变了）。
##   hidden / hide / gone = 藏起来；show / shown / default = 回到默认。状态记在 StoryState.props（存档、跳节拍用）。
## 雾（照作者 Phage 的起雾前景做的，scripts/fog_noise.gdshader）：两层 Parallax2D（横向循环）里各一个 ColorRect，
##   材质是无缝噪声贴图（480×270 原生像素、nearest）随时间慢慢漂，雾团硬边、透明度分档：
##     FogBack  在 Mid 和 Main 之间（远景前面、主层后面），较浓；fill 把雾团间的空隙也填上，最浓时远景几乎看不见。
##     FogFront 在角色前面、Front 层后面，只在画面下半部、越往下越浓，很淡（晨的头和身子基本不被盖，她还是最亮）。
##   浓淡 = fog_at(x)：坠毁现场一点点（好看），旧路慢慢起雾，fog_start 以后很快变浓，hollow 最浓；树屋那一段回到淡；
##   靠近左右不可见的墙时也变浓（墙那边是一片雾，看得见的边）。远处坡地那堵雾是 fog_bank 图。
## 看得见的边（不用台词推人）：倒木没推开之前，旧路到倒木为止（倒木右边一点）；塌陷口（hollow）是个坑，晨走到坑边就停住，
##   像碰到边（不自动往回走）。
##   布条：在雾里每隔 CLOTH_GUST 秒被风吹一下（换帧），同时周围亮一点点（加法的小光晕），让人注意到。
## 墙：forest 分两段（坠毁现场到旧路 = wall_left..wall_road；树屋那一段 = wall_house..wall_right），屋里 = json 的 walk。

const ART := "res://art/forest_story/"
const ROOM_W := 480.0                    # 剧本 room_* marker 原来那间屋子的宽（换算用）
const HOUSE_SIZE := Vector2i(260, 200)   # 树屋占位图多大

const DEFAULT_MARKERS := {
	"wall_left": -160, "scrap": -60, "wreck": 120, "luggage": 190, "chen_start": 250, "wood": 372,
	"resin": 520, "deer_appear": 560, "branch": 690, "road_start": 900, "stall": 1100, "log": 1400,
	"fog_start": 1550, "cloth": 1780, "hollow": 1900, "wall_road": 1960,
	"wall_house": 2380, "treehouse": 2600, "empty_house": 2900, "shop": 3120, "slope": 3400, "wall_right": 3600,
	# 屋内（剧本原来按 480 宽一屏写的 x，换算进树屋，见上）
	"room_door": 40, "room_chairs": 100, "room_kettle": 145, "room_radio": 195, "room_sign": 235,
	"room_tools": 275, "room_miluo": 305, "room_dish": 330, "room_gramophone": 360, "room_box": 390, "room_pipes": 440,
}
## 剧本 room_<名字> → treehouse.json hotspots 里的哪个点（同名的直接用）
const HOUSE_ALIAS := {"kettle": "stove", "tools": "tool_b", "pipes": "pipe_b"}
## 屋内物件 → 跟着哪个 room_ marker、偏多少（480 宽那间屋子里的像素，换算时一起缩；treehouse.json 的 objects 里有就不用这个）
const ROOM_ANCHOR := {
	"pipe_a": ["room_pipes", -22], "pipe_b": ["room_pipes", 0], "pipe_c": ["room_pipes", 22],
	"tool_a": ["room_tools", -16], "tool_b": ["room_tools", 0], "tool_c": ["room_tools", 16],
	"cups": ["room_kettle", 24], "pipe_steam": ["room_pipes", 0],
}
const PSEUDO_PROPS := ["fog", "ship", "pipes"]

## 物件。tex = art/forest_story/ 下的文件名；at / dx / dy = 放在哪；size = 没图时色块多大；color = 色块颜色；
## room = treehouse 就在树屋里（at 是剧本原来那间 480 宽屋子的 x，换算进树屋；dy 从地板往上为负）；
## frames = 横排几帧；anim = 自己循环播（ms / 帧）；hidden = 一开始藏着；layer = fog 放在雾那一层（主层后面）；sink = 往地里压几像素
const PROPS := {
	"luggage": {"tex": "luggage.png", "at": "luggage", "size": [40, 18], "color": "#5b5244"},
	"scrap": {"tex": "mat_scrap.png", "at": "scrap", "size": [14, 10], "color": "#6c716e"},
	"resin": {"tex": "mat_resin.png", "at": "resin", "size": [14, 10], "color": "#8c6f36"},
	"branch": {"tex": "mat_branch.png", "at": "branch", "size": [14, 10], "color": "#5e4b35"},
	"stall": {"tex": "stall.png", "at": "stall", "size": [90, 70], "color": "#34362d"},
	"log": {"tex": "log.png", "at": "log", "size": [120, 36], "color": "#45392c",
		"states": {"moved": {"tex": "log_moved.png", "size": [120, 22], "dx": 30}}},
	"branch_a": {"tex": "branch_a.png", "at": "log", "dx": -38, "size": [36, 10], "color": "#55432f",
		"states": {"moved": {"dx": -40}}},
	"branch_b": {"tex": "branch_b.png", "at": "log", "dx": 36, "size": [36, 10], "color": "#5a4631",
		"states": {"moved": {"dx": 40}}},
	"cloth": {"tex": "cloth.png", "at": "cloth", "dy": -34, "dy_art": 0, "size": [10, 16], "color": "#9a8f78", "frames": 2, "anim": 700},
	"hoofprints": {"tex": "hoofprints.png", "at": "cloth", "dx": -46, "size": [24, 3], "color": "#2e2a22", "sink": 2},
	"hollow": {"tex": "hollow.png", "at": "hollow", "size": [60, 10], "color": "#1c2624", "sink": 6},
	"empty_house": {"tex": "empty_house.png", "at": "empty_house", "size": [110, 80], "color": "#33302a"},
	"empty_item": {"tex": "empty_item.png", "at": "empty_house", "dx": 40, "size": [12, 10], "color": "#6e6555"},
	"pump": {"tex": "pump.png", "at": "empty_house", "dx": -34, "size": [16, 16], "color": "#5d6b66", "hidden": true,
		"states": {"at_door": {"visible": true, "dx": 26}, "placed": {"visible": true}, "carried": {"visible": false}}},
	"shop": {"tex": "shop.png", "at": "shop", "size": [100, 80], "color": "#36332b"},
	"depressions": {"tex": "depressions.png", "at": "slope", "size": [220, 14], "color": "#1f2723", "sink": 10},
	"fog_bank": {"tex": "fog_bank.png", "at": "slope", "dx": 180, "dy": -20, "size": [480, 120], "layer": "fog", "fog": true},
	# ---- 树屋里
	"chairs": {"tex": "room_chairs.png", "room": "treehouse", "at": 100, "size": [22, 16], "color": "#5a4632",
		"states": {"pushed": {"dx": 5}}},
	"radio": {"tex": "room_radio.png", "room": "treehouse", "at": 195, "dy": -46, "size": [12, 9], "color": "#6a5e4c"},
	"sign": {"tex": "room_sign.png", "room": "treehouse", "at": 235, "size": [8, 24], "color": "#6b5a40", "frames": 4, "anim": 300},
	"pipe_a": {"tex": "pipe_a.png", "room": "treehouse", "at": 418, "dy": -64, "size": [7, 30], "color": "#5c605a"},
	"pipe_b": {"tex": "pipe_b.png", "room": "treehouse", "at": 440, "dy": -64, "size": [7, 30], "color": "#596058"},
	"pipe_c": {"tex": "pipe_c.png", "room": "treehouse", "at": 462, "dy": -64, "size": [7, 30], "color": "#5e5f57"},
	"pipe_steam": {"tex": "pipe_steam.png", "room": "treehouse", "at": 440, "dy": -96, "size": [4, 8],
		"color": "#c9d3cd", "frames": 3, "anim": 160, "alpha": 0.7},
	"kettle": {"tex": "room_kettle.png", "room": "treehouse", "at": 145, "dy": -24, "size": [10, 9], "color": "#7a6d5a", "frames": 2, "anim": 400,
		"states": {"off": {"anim": 0, "anim_fixed": true}}},
	"tool_a": {"tex": "tool_a.png", "room": "treehouse", "at": 259, "dy": -26, "size": [6, 4], "color": "#8a8578"},
	"tool_b": {"tex": "tool_b.png", "room": "treehouse", "at": 275, "dy": -26, "size": [6, 4], "color": "#857e70"},
	"tool_c": {"tex": "tool_c.png", "room": "treehouse", "at": 291, "dy": -26, "size": [6, 4], "color": "#8e8676"},
	"dish": {"tex": "room_dish.png", "room": "treehouse", "at": 330, "dy": -26, "size": [7, 3], "color": "#9a8d74"},
	"cups": {"tex": "room_cups.png", "room": "treehouse", "at": 169, "dy": -24, "size": [8, 5], "color": "#b0a48c"},
	"gramophone": {"tex": "room_gramophone.png", "room": "treehouse", "at": 360, "size": [14, 22], "color": "#6b5636", "frames": 2},
	"box": {"tex": "room_box.png", "room": "treehouse", "at": 390, "size": [10, 7], "color": "#5f4d38"},
}
## 同一张图里按状态换帧
const FRAME_STATES := {"gramophone": {"old": 0, "new": 1}, "box": {"open": 1}, "cups": {"two": 1}, "kettle": {"off": 0}}
## 树屋占位图的颜色（treehouse_back / front.png 还没画时）
const ROOM_WALL_C := Color("#29271f")
const ROOM_FLOOR_C := Color("#352e24")
const ROOM_LINE_C := Color("#4a3f2f")
const BARK_C := Color("#2f2a22")
const FOG_C := Color("#7f988c")          # 雾色：偏青绿的灰（森林身份色，不用蓝）
const FOG_SHADER := preload("res://scripts/fog_noise.gdshader")
const FOG_BACK_A := 0.97                 # 后面那层最浓时的 density
const FOG_BACK_BASE := 0.1               # 平时（坠毁现场）也有一点点
const FOG_FRONT_A := 0.34                # 前面那层最浓时的 density（只在下半屏、越往下越浓）
const FOG_FRONT_BASE := 0.04
const LOG_BLOCK := 40.0                  # 倒木推开之前，晨最远走到倒木中心右边这么多（够得着树枝和倒木的互动点）
const HOLLOW_EDGE := 18.0                # 塌陷口：晨最远走到它中心左边这么多（坑边）
const EDGE_FOG := 160.0                  # 离不可见的墙这么近就开始变浓
const CLOTH_GUST := 3.2                  # 布条每隔几秒被风吹一下
const CLOTH_GUST_T := 0.5                # 吹一下多久

var level: Node2D
var chen: Node2D
var markers := {}
var room := "forest"                     # 晨现在在哪：forest / treehouse（屋里）
## 树屋（世界坐标）：cx, cy = 图中心；floor = 屋内地板那一行；walk = 屋内左右范围；door = 门的 x；spots = json 里的物件点
var house := {}
var house_back: Sprite2D
var house_front: Sprite2D
var _front_tw: Tween
var forest_ground: Callable
var props := {}                          # id → Sprite2D
var _cfg := {}                           # id → 合并后的配置
var _anim_t := 0.0
var fog_k := 0.0                         # 现在的雾（跟镜头）
var _fog_back: Parallax2D
var _fog_front: Parallax2D
var _forest_layer: Node2D                # 森林里的物件（主层前面、NPC 后面）
var _fog_layer: Node2D                   # 雾那一层的物件（主层后面）
var fog_enabled := true                  # 开发者面板（F8）的「雾开 / 关」
var thick := false                       # prop fog:thick：旧路后半段的雾更浓
var extra_rects := {}                    # 不归这里管、但 hotspot 要用的东西的矩形：名字 → func() -> Rect2（飞船 wreck）
var on_pseudo: Callable                  # ship 这种伪物件交给关卡：func(id, state)


func setup(lv: Node2D, script_markers: Dictionary, steam_at := "") -> void:
	level = lv
	chen = lv.chen
	forest_ground = chen.ground_fn
	markers = DEFAULT_MARKERS.duplicate()
	for k in script_markers:
		var v = script_markers[k]
		if v is float or v is int:
			markers[k] = float(v)
	var main: Node = lv.get_node("Main")
	var mid: Node = lv.get_node("Mid")
	_fog_back = _make_fog_layer("FogBack", 0.8, 0.0, 270.0, 11, Vector2(0.006, -0.003), 1.4, 0.55)
	lv.add_child(_fog_back)
	lv.move_child(_fog_back, mid.get_index() + 1)
	_fog_layer = Node2D.new()
	_fog_layer.name = "StoryFogProps"
	lv.add_child(_fog_layer)
	lv.move_child(_fog_layer, _fog_back.get_index() + 1)
	_forest_layer = Node2D.new()
	_forest_layer.name = "StoryProps"
	lv.add_child(_forest_layer)
	lv.move_child(_forest_layer, main.get_index() + 1)
	_fog_front = _make_fog_layer("FogFront", 1.2, 135.0, 135.0, 29, Vector2(0.014, 0.0), 2.0, 0.0)
	lv.add_child(_fog_front)
	lv.move_child(_fog_front, lv.get_node("Front").get_index())     # 角色前面、前景层后面
	_build_house()
	for id in PROPS:
		_make_prop(id)
	_add_room_light()
	_add_cloth_glow()
	var objs: Dictionary = house["objects"]
	if steam_at != "" and objs.has(steam_at) and (objs[steam_at] as Dictionary).has("leak"):
		# 细白汽冒在漏气那段的 leak 点（底边中点）
		var c: Dictionary = _cfg["pipe_steam"]
		c["spot"] = objs[steam_at]["leak"]
		c["dx"] = 0
		_place("pipe_steam")
	elif steam_at != "" and props.has(steam_at):
		var c: Dictionary = _cfg["pipe_steam"]
		var src: Dictionary = _cfg[steam_at]
		for k in ["at", "dx", "spot"]:
			if src.has(k):
				c[k] = src[k]
			else:
				c.erase(k)
		if c.has("spot"):
			c["spot"] = (c["spot"] as Vector2) + Vector2(0, -34)
		_place("pipe_steam")
	for id in StoryState.props:
		set_prop(id, StoryState.props[id], false)


# ======================================================================= markers / 地面
## at（marker 名、物件 id、数字）→ {ok, x, room}。NPC 名字由 story_runner 先处理。
func resolve(at) -> Dictionary:
	if at is float or at is int:
		return {"ok": true, "x": float(at), "room": room}
	var s := str(at)
	if s.is_valid_float():
		return {"ok": true, "x": s.to_float(), "room": room}
	if markers.has(s):
		return {"ok": true, "x": float(markers[s]), "room": "treehouse" if s.begins_with("room_") else "forest"}
	var pid := s.trim_prefix("room_")
	if _cfg.has(s) or _cfg.has(pid):
		var id := s if _cfg.has(s) else pid
		var p: Sprite2D = props[id]
		return {"ok": true, "x": p.position.x, "room": _cfg[id].get("room", "forest")}
	return {"ok": false, "x": 0.0, "room": room}


func has_marker(s: String) -> bool:
	return markers.has(s) or _cfg.has(s) or _cfg.has(s.trim_prefix("room_")) or extra_rects.has(s)


func mx(name: String) -> float:
	return float(markers.get(name, DEFAULT_MARKERS.get(name, 0.0)))


## 脚底那一行（世界 y）：晨 / NPC 的 position.y = round(这个) + 1
func ground_at(x: float, r := "") -> float:
	if r == "":
		r = room
	if r == "treehouse":
		return float(house["floor"])
	return float(forest_ground.call(x))


## 进屋 / 出屋：前墙淡出 / 淡入（instant = 跳节拍时直接到位），晨的地面换成屋内那条直线
func set_room(r: String, instant := false) -> void:
	room = r
	if r == "treehouse":
		var gy: float = house["floor"]
		chen.ground_fn = func(_x: float) -> float: return gy
	else:
		chen.ground_fn = forest_ground
	var a := 0.0 if r == "treehouse" else 1.0
	if _front_tw != null and _front_tw.is_valid():
		_front_tw.kill()
	if instant:
		house_front.modulate.a = a
	else:
		_front_tw = create_tween()
		_front_tw.tween_property(house_front, "modulate:a", a, 0.5).set_trans(Tween.TRANS_SINE)


func in_room() -> bool:
	return room == "treehouse"


## x 在不在树屋图的横向范围里（屋外的角色站在这里，晨进屋时要跟着前墙一起淡掉，不然像站在屋里）
func in_house_span(x: float) -> bool:
	return absf(x - float(house["cx"])) < float(house["w"]) / 2.0


## x 在不在树屋那一片（进出屋不黑屏用）
func near_house(x: float) -> bool:
	return absf(x - float(house["cx"])) < float(house["w"]) / 2.0 + 120.0


## 晨现在这一段的左右墙（世界 x）
func walls(x: float) -> Vector2:
	if in_room():
		return house["walk"]
	var split := (mx("wall_road") + mx("wall_house")) / 2.0
	if x < split:
		# 看得见的边：倒木推开之前到倒木为止；塌陷口是个坑，坑边停住
		var r := minf(mx("wall_road"), mx("hollow") - HOLLOW_EDGE)
		if prop_state("log") != "moved" and not StoryState.has("log_cleared"):
			r = minf(r, mx("log") + LOG_BLOCK)
		return Vector2(mx("wall_left"), r)
	return Vector2(mx("wall_house"), mx("wall_right"))


# ======================================================================= 物件
func _make_prop(id: String) -> void:
	var c: Dictionary = (PROPS[id] as Dictionary).duplicate(true)
	_merge_meta(c)
	_anchor_cfg(id, c)
	_cfg[id] = c
	var s := Sprite2D.new()
	s.name = "P_" + id
	s.centered = false
	if c.get("layer", "") == "fog":
		_fog_layer.add_child(s)
	else:
		_forest_layer.add_child(s)
	props[id] = s
	_apply_look(id, c)
	s.visible = not c.get("hidden", false)
	_place(id)


## 剧本的 markers 里有这个物件的点就放那；树屋里的东西：treehouse.json 里有就用它的点（spot），没有就跟着 room_* marker
func _anchor_cfg(id: String, c: Dictionary) -> void:
	if c.get("room", "forest") == "treehouse":
		var objs: Dictionary = house["objects"]
		var k: float = house["k"]
		if objs.has(id):
			c["spot"] = objs[id]["spot"]
			c["dx"] = 0
			return
		if ROOM_ANCHOR.has(id):
			var anchor: String = ROOM_ANCHOR[id][0]
			c["at"] = anchor
			c["dx"] = round(float(ROOM_ANCHOR[id][1]) * k)
			return
		if markers.has("room_" + id):
			c["at"] = "room_" + id
			c["dx"] = 0
		else:
			c["at"] = room_x(float(c.get("at", 0)))      # 剧本没给这件东西的点：按默认的房间 x 换算
	elif markers.has(id) and not DEFAULT_MARKERS.has(id):
		c["at"] = id
		c["dx"] = 0


## 图旁边的同名 json（美术给的）：frames / ms（自己循环播）/ ground_row（图里哪一行踩在地面上，往下的压进地里）
func _merge_meta(c: Dictionary) -> void:
	var meta := ART + str(c.get("tex", "")).get_basename() + ".json"
	if not FileAccess.file_exists(meta):
		return
	var j = JSON.parse_string(FileAccess.get_file_as_string(meta))
	if not j is Dictionary:
		return
	if j.has("frames"):
		c["frames"] = int(j["frames"])
	if j.has("ms") and not c.has("anim_fixed"):
		c["anim"] = float(j["ms"])
	if j.has("ground_row") and c.get("room", "forest") == "forest":
		c["ground_row"] = int(j["ground_row"])


func _apply_look(id: String, c: Dictionary) -> void:
	var s: Sprite2D = props[id]
	var path := ART + str(c.get("tex", ""))
	var frames := int(c.get("frames", 1))
	if ResourceLoader.exists(path):
		s.texture = load(path)
		s.hframes = maxi(1, frames)
		s.set_meta("placeholder", false)
	else:
		var sz: Array = c.get("size", [12, 12])
		s.texture = _fog_tex(int(sz[0]), int(sz[1])) if c.get("fog", false) else _block(int(sz[0]), int(sz[1]), Color(str(c.get("color", "#555555"))))
		s.hframes = 1
		s.set_meta("placeholder", true)
	s.modulate.a = float(c.get("alpha", 1.0))
	var fw := s.texture.get_width() / s.hframes
	var fh := s.texture.get_height()
	s.offset = Vector2(-floor(fw / 2.0), -fh)
	if c.has("ground_row") and not s.get_meta("placeholder", false):
		c["sink"] = fh - 1 - int(c["ground_row"])


func _place(id: String) -> void:
	var c: Dictionary = _cfg[id]
	var s: Sprite2D = props[id]
	if c.has("spot"):
		var sp: Vector2 = c["spot"]
		s.position = Vector2(round(sp.x + float(c.get("dx", 0))), round(sp.y) + 1.0)
		return
	var at = c.get("at", 0)
	var x: float = float(at) if (at is float or at is int) else mx(str(at))
	x += float(c.get("dx", 0))
	var dy := float(c.get("dy", 0))
	if c.has("dy_art") and not s.get_meta("placeholder", false):
		dy = float(c["dy_art"])                     # 有图了：图自己画了树枝，底边踩地（占位色块才悬在空中）
	if c.get("room", "forest") == "treehouse":
		s.position = Vector2(round(x), float(house["floor"]) + float(c.get("dy", 0)) + 1.0)
	else:
		s.position = Vector2(round(x), round(float(forest_ground.call(x))) + 1.0 + dy + float(c.get("sink", 0)))


func set_prop(id: String, state: String, save := true) -> void:
	if save:
		StoryState.set_prop(id, state)
	if id == "fog":
		thick = state == "thick"
		return
	if id == "ship":
		if on_pseudo.is_valid():
			on_pseudo.call(id, state)
		return
	# 管道修好了 / 冒汽那段藏起来：细白汽也没了
	if (id.begins_with("pipe") and state == "fixed") or (id == "pipes" and state in ["fixed", "hidden"]):
		if props.has("pipe_steam"):
			props["pipe_steam"].visible = false
		if id == "pipes" or id == "pipe_steam":
			return
	if not props.has(id):
		return
	var s: Sprite2D = props[id]
	var base: Dictionary = (PROPS[id] as Dictionary).duplicate(true)
	_merge_meta(base)
	_anchor_cfg(id, base)
	if id == "pipe_steam":
		base = (_cfg[id] as Dictionary).duplicate(true)
	var c: Dictionary = base.duplicate(true)
	if state in ["hidden", "hide", "gone"]:
		s.visible = false
		return
	if state in ["show", "shown", "default", ""]:
		_cfg[id] = c
		_apply_look(id, c)
		s.self_modulate = Color.WHITE
		s.visible = true
		_place(id)
		return
	var st: Dictionary = (base.get("states", {}) as Dictionary).get(state, {})
	for k in st:
		c[k] = st[k] if k != "dx" else float(base.get("dx", 0)) + float(st[k])
	if not st.has("tex"):
		var alt := str(base.get("tex", "")).get_basename() + "_" + state + ".png"
		if ResourceLoader.exists(ART + alt):
			c["tex"] = alt
	_cfg[id] = c
	_apply_look(id, c)
	s.visible = bool(c.get("visible", true))
	var fs: Dictionary = FRAME_STATES.get(id, {})
	if fs.has(state) and s.hframes > int(fs[state]):
		s.frame = int(fs[state])
	elif s.get_meta("placeholder", false) and not st.has("tex"):
		s.self_modulate = Color(1.25, 1.2, 1.1)     # 色块：亮一档，看得出换了状态
	_place(id)


func prop_state(id: String) -> String:
	return str(StoryState.props.get(id, ""))


## 物件在世界里的矩形（点选、提示箭头放哪）
func prop_rect(id: String) -> Rect2:
	if not props.has(id):
		return Rect2()
	var s: Sprite2D = props[id]
	var fw := float(s.texture.get_width()) / s.hframes
	return Rect2(s.global_position + s.offset, Vector2(fw, s.texture.get_height()))


func prop_room(id: String) -> String:
	return str(_cfg.get(id, {}).get("room", "forest"))


static func _block(w: int, h: int, c: Color) -> ImageTexture:
	var img := Image.create_empty(maxi(1, w), maxi(1, h), false, Image.FORMAT_RGBA8)
	img.fill(c)
	var e := c.darkened(0.3)
	for x in w:
		img.set_pixel(x, 0, c.lightened(0.12))
		img.set_pixel(x, h - 1, e)
	return ImageTexture.create_from_image(img)


## 雾墙占位：横向一整块，越往下越浓，硬边分档
static func _fog_tex(w: int, h: int) -> ImageTexture:
	var img := Image.create_empty(w, h, false, Image.FORMAT_RGBA8)
	var steps := 6
	for y in h:
		var k := floorf(float(y) / h * steps) / (steps - 1)
		var a := 0.12 + 0.4 * k
		for x in w:
			var edge := minf(x, w - 1 - x) / 40.0     # 左右两头也分档淡掉
			var ea := floorf(clampf(edge, 0.0, 1.0) * 4.0) / 4.0
			img.set_pixel(x, y, Color(FOG_C, a * ea))
	return ImageTexture.create_from_image(img)


# ======================================================================= 树屋
## 剧本原来那间 480 宽屋子里的 x → 世界 x（压进屋内可走范围）
func room_x(rx: float) -> float:
	var w: Vector2 = house["walk"]
	return round(w.x + clampf(rx / ROOM_W, 0.0, 1.0) * (w.y - w.x))


static func _vec(v, fallback_y := 0.0) -> Vector2:
	if v is Array and v.size() >= 2:
		return Vector2(float(v[0]), float(v[1]))
	if v is Array and v.size() == 1:
		return Vector2(float(v[0]), fallback_y)
	if v is Dictionary:
		return Vector2(float(v.get("x", 0.0)), float(v.get("y", fallback_y)))
	if v is float or v is int:
		return Vector2(float(v), fallback_y)
	return Vector2(0, fallback_y)


func _build_house() -> void:
	var tx := mx("treehouse")
	var j: Dictionary = {}
	if FileAccess.file_exists(ART + "treehouse.json"):
		var p = JSON.parse_string(FileAccess.get_file_as_string(ART + "treehouse.json"))
		if p is Dictionary:
			j = p
	var back_tex: Texture2D = load(ART + "treehouse_back.png") if ResourceLoader.exists(ART + "treehouse_back.png") else null
	var size := Vector2(HOUSE_SIZE)
	if back_tex != null:
		size = back_tex.get_size()
	elif j.has("size"):
		size = _vec(j["size"])
	# 锚点 = 图底边中点：json 说踩在地面 228 那一行；没有 json 就踩在 treehouse 那里的地面上
	var ay: float = 228.0 if not j.is_empty() else round(float(forest_ground.call(tx)))
	var c := Vector2(tx, ay + 1.0 - size.y / 2.0)            # 图中心（Sprite2D 居中放）
	var floor_dy: float = float(j.get("floor_offset", j.get("floor", 0.0)))
	var walk := Vector2(-size.x / 2.0 + 22.0, size.x / 2.0 - 22.0)
	if j.has("walk_min") or j.has("walk_max"):
		walk = Vector2(float(j.get("walk_min", walk.x)), float(j.get("walk_max", walk.y)))
	elif j.has("walk"):
		walk = _vec(j["walk"])
	var door_dx: float = float(j.get("door_x", j.get("door", -size.x / 2.0 + 36.0)))
	house = {"cx": tx, "cy": c.y, "ay": ay, "w": size.x, "h": size.y, "floor": ay + floor_dy,
		"walk": Vector2(tx + walk.x, tx + walk.y), "door": round(tx + door_dx), "spots": {}, "objects": {},
		"json": not j.is_empty(), "k": (walk.y - walk.x) / ROOM_W}
	# hotspots：名字 → 人走到这个 x 互动；objects：名字 → 左上角 (x, y) + w / h（相对锚点，y 往上为负）
	var hs: Dictionary = j.get("hotspots", {})
	for k in hs:
		house["spots"][str(k)] = tx + float(_vec(hs[k]).x)
	var objs: Dictionary = j.get("objects", {})
	for k in objs:
		var o: Dictionary = objs[k]
		var ow := float(o.get("w", 8))
		var oh := float(o.get("h", 8))
		var ox := float(o.get("x", 0))
		var oy := float(o.get("y", -oh))
		var e := {"spot": Vector2(tx + ox + floorf(ow / 2.0), ay + oy + oh)}   # 底边中点（那一行）
		if o.has("leak"):
			var lk := _vec(o["leak"])
			e["leak"] = Vector2(tx + lk.x, ay + lk.y)
		house["objects"][str(k).trim_prefix("room_")] = e
	# 剧本的 room_* marker：json 的 hotspots 里有同名的点就用它（kettle = 炉子 stove、tools / pipes = 中间那把 / 那段），
	# 再看 objects，都没有就按比例换算（原来是 480 宽一屏的 x）
	for k in markers.keys():
		var name := str(k)
		if not name.begins_with("room_"):
			continue
		var pid := name.trim_prefix("room_")
		var alias: String = HOUSE_ALIAS.get(pid, pid)
		if (house["spots"] as Dictionary).has(pid):
			markers[name] = float(house["spots"][pid])
		elif (house["spots"] as Dictionary).has(alias):
			markers[name] = float(house["spots"][alias])
		elif (house["objects"] as Dictionary).has(pid):
			markers[name] = (house["objects"][pid]["spot"] as Vector2).x
		else:
			markers[name] = room_x(float(markers[name]))
	# 门：treehouse（屋外互动的点）和 room_door 都在门口
	markers["treehouse"] = house["door"]
	markers["room_door"] = house["door"]
	house_back = Sprite2D.new()
	house_back.name = "TreehouseBack"
	house_back.texture = back_tex if back_tex != null else _house_placeholder(size, false)
	house_back.position = c
	_forest_layer.add_child(house_back)
	house_front = Sprite2D.new()
	house_front.name = "TreehouseFront"
	var ft: Texture2D = load(ART + "treehouse_front.png") if ResourceLoader.exists(ART + "treehouse_front.png") else null
	house_front.texture = ft if ft != null else _house_placeholder(size, true)
	house_front.position = c
	# 前墙：在弥洛（Snake）后面一个、鹿和晨前面——屋里的东西和弥洛被它盖住，屋外的晨和鹿在它前面走
	level.add_child(house_front)
	level.move_child(house_front, level.get_node("Snake").get_index() + 1)


## 布条旁边的小光晕（加法、硬边分档），被风吹的时候亮一下
var _cloth_glow: Sprite2D


func _add_cloth_glow() -> void:
	var r := 14
	var n := r * 2 + 1
	var img := Image.create_empty(n, n, false, Image.FORMAT_RGBA8)
	for y in n:
		for x in n:
			var d := Vector2(x - r, y - r).length() / (r + 0.5)
			var a := floorf(clampf(1.0 - d, 0.0, 1.0) * 4.0 + 0.5) / 4.0
			img.set_pixel(x, y, Color(1, 1, 1, a))
	_cloth_glow = Sprite2D.new()
	_cloth_glow.name = "ClothGlow"
	_cloth_glow.texture = ImageTexture.create_from_image(img)
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	_cloth_glow.material = add
	_cloth_glow.modulate = Color(0.85, 0.95, 0.88, 0.0)
	_forest_layer.add_child(_cloth_glow)


## 屋里的灯光（room_light.png，半透明，和树屋同尺寸同锚点）：在屋内物件上面、人物下面
func _add_room_light() -> void:
	if not ResourceLoader.exists(ART + "room_light.png"):
		return
	var l := Sprite2D.new()
	l.name = "TreehouseLight"
	l.texture = load(ART + "room_light.png")
	l.position = house_back.position
	_forest_layer.add_child(l)


## 树屋占位：back = 树干一圈 + 屋内的墙、地板、门洞、搁板、炉子、工作台；front = 树干前墙 + 一扇门 + 一扇很暗的暖窗
func _house_placeholder(size: Vector2, front: bool) -> ImageTexture:
	var w := int(size.x)
	var h := int(size.y)
	var img := Image.create_empty(w, h, false, Image.FORMAT_RGBA8)
	var ox: float = float(house["cx"]) - floorf(w / 2.0)
	var oy: float = float(house["cy"]) - floorf(h / 2.0)
	var fy := int(float(house["floor"]) - oy)
	var wl := int((house["walk"] as Vector2).x - ox) - 16
	var wr := int((house["walk"] as Vector2).y - ox) + 16
	var door := int(float(house["door"]) - ox)
	var top := maxi(8, fy - 110)
	img.fill_rect(Rect2i(w / 2 - 38, 0, 76, top), BARK_C.darkened(0.12))     # 往上的树干
	img.fill_rect(Rect2i(wl, top, wr - wl, h - top), BARK_C)
	if not front:
		img.fill_rect(Rect2i(wl + 6, top + 6, wr - wl - 12, fy - top - 5), ROOM_WALL_C)
		img.fill_rect(Rect2i(wl + 6, fy + 1, wr - wl - 12, maxi(0, h - fy - 1)), ROOM_FLOOR_C)
		img.fill_rect(Rect2i(wl + 6, fy, wr - wl - 12, 1), ROOM_LINE_C)
		for x in range(wl + 26, wr - 6, 30):
			img.fill_rect(Rect2i(x, top + 6, 1, fy - top - 6), ROOM_WALL_C.darkened(0.15))
		img.fill_rect(Rect2i(door - 10, fy - 40, 20, 40), Color("#1a1813"))       # 门洞（从里面看）
		var radio := int(mx("room_radio") - ox)
		img.fill_rect(Rect2i(radio - 10, fy - 46, 20, 2), ROOM_LINE_C)          # 搁板
		var kettle := int(mx("room_kettle") - ox)
		img.fill_rect(Rect2i(kettle - 8, fy - 24, 26, 24), Color("#30291f"))    # 炉子
		var t0 := int(mx("room_tools") - ox) - 14
		var t1 := int(mx("room_dish") - ox) + 8
		img.fill_rect(Rect2i(t0, fy - 26, t1 - t0, 2), Color("#4f4130"))       # 工作台
		img.fill_rect(Rect2i(t0 + 2, fy - 24, 2, 24), Color("#3e3326"))
		img.fill_rect(Rect2i(t1 - 4, fy - 24, 2, 24), Color("#3e3326"))
	else:
		for x in range(wl + 8, wr - 4, 13):                                       # 竖的树皮纹
			img.fill_rect(Rect2i(x, top, 1, h - top), BARK_C.darkened(0.2))
		img.fill_rect(Rect2i(door - 10, fy - 40, 20, 40), Color("#1d1a14"))       # 门
		img.fill_rect(Rect2i(door - 11, fy - 41, 22, 1), ROOM_LINE_C)
		var wx := int(float(house["cx"]) - ox) + 30
		img.fill_rect(Rect2i(wx, fy - 72, 16, 12), Color("#3a2e1c"))              # 很暗的暖窗
		img.fill_rect(Rect2i(wx + 2, fy - 70, 12, 8), Color("#6b5230"))
	return ImageTexture.create_from_image(img)


# ======================================================================= 雾
## 一层雾：Parallax2D（scroll 介于前后两层之间、横向 480 循环）里一个 ColorRect（y0 起、高 h），噪声贴图按原生像素
func _make_fog_layer(n: String, scroll: float, y0: float, h: float, seed: int, speed: Vector2, gpow: float, gmin: float) -> Parallax2D:
	var p := Parallax2D.new()
	p.name = n
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
	mat.set_shader_parameter("density", 0.0)
	var r := ColorRect.new()
	r.name = "Fog"
	r.color = FOG_C
	r.position = Vector2(0, y0)
	r.size = Vector2(480, h)
	r.material = mat
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_child(r)
	p.set_meta("mat", mat)
	return p


func fog_at(x: float) -> float:
	var rs := mx("road_start")
	var fs := mx("fog_start")
	var ho := mx("hollow")
	var split := (mx("wall_road") + mx("wall_house")) / 2.0
	if x < split:
		if x < rs:
			return 0.0
		if x < fs:
			return 0.25 * (x - rs) / maxf(1.0, fs - rs)
		# fog_start 以后很快变浓（150 像素内到 0.7），再慢慢到 hollow 的 1.0
		var f := 0.25 + 0.45 * clampf((x - fs) / 150.0, 0.0, 1.0)
		f += 0.3 * clampf((x - fs - 150.0) / maxf(1.0, ho - fs - 150.0), 0.0, 1.0)
		if thick and x > fs - 150.0:
			f = maxf(f, 0.8)
		return maxf(clampf(f, 0.0, 1.0), _edge_fog(x))
	# 树屋那一段：恢复正常；坡地附近薄薄一层
	var sl := mx("slope")
	return maxf(clampf(0.25 * (1.0 - absf(x - sl) / 300.0), 0.0, 0.25), _edge_fog(x))


## 靠近不可见的墙：那边是一片雾（看得见的边）
func _edge_fog(x: float) -> float:
	if in_room():
		return 0.0
	var w := walls(x)
	var d := minf(x - w.x, w.y - x)
	return 0.75 * clampf(1.0 - d / EDGE_FOG, 0.0, 1.0)


## 布条：平时静止，每隔 CLOTH_GUST 秒被风吹一下（换到第 2 帧），雾里同时周围亮一点点
func _update_cloth() -> void:
	var s: Sprite2D = props["cloth"]
	var t := fmod(_anim_t, CLOTH_GUST)
	var gust := t < CLOTH_GUST_T
	if s.hframes > 1:
		s.frame = (1 if fmod(t, 0.25) < 0.125 else 0) if gust else 0
	if _cloth_glow == null:
		return
	var fr := prop_rect("cloth")
	_cloth_glow.position = (fr.position + fr.size * Vector2(0.65, 0.4)).round() if fr.size.y > 30.0 else fr.get_center().round()
	var k := 0.0
	if gust and s.visible:
		k = sin(t / CLOTH_GUST_T * PI)                        # 亮起来再暗下去
	var a := 0.32 * k * clampf((fog_k - 0.3) / 0.4, 0.0, 1.0)
	_cloth_glow.modulate.a = floorf(a * 16.0) / 16.0          # 分档变，不平滑闪


func update(delta: float, cam_center: Vector2) -> void:
	_anim_t += delta
	# 自己循环播的物件（布条被风吹、路标转、水壶冒汽）
	for id in props:
		var c: Dictionary = _cfg[id]
		var s: Sprite2D = props[id]
		if id == "cloth":
			continue
		if float(c.get("anim", 0)) > 0.0 and s.hframes > 1 and s.visible:
			s.frame = int(_anim_t * 1000.0 / float(c["anim"])) % s.hframes
	_update_cloth()
	var want := fog_at(cam_center.x)
	fog_k = move_toward(fog_k, want, delta * 0.5)
	if absf(want - fog_k) < 0.002:
		fog_k = want
	var off := not fog_enabled
	var mb: ShaderMaterial = _fog_back.get_meta("mat")
	mb.set_shader_parameter("density", FOG_BACK_BASE + (FOG_BACK_A - FOG_BACK_BASE) * fog_k)
	mb.set_shader_parameter("fill", 0.8 * fog_k * fog_k)
	var mf: ShaderMaterial = _fog_front.get_meta("mat")
	mf.set_shader_parameter("density", FOG_FRONT_BASE + (FOG_FRONT_A - FOG_FRONT_BASE) * fog_k)
	_fog_back.visible = not off
	_fog_front.visible = not off
