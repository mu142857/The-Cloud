extends Node2D
## 驾驶舱（room = cockpit）：一屏平面剖面的飞船（480×270 里），晨在里面左右走几步（驾驶座 ↔ 右侧接口 ↔ 转化装置）。
## story_world.gd 在剧本 rooms 里有 cockpit 时建它（add_cockpit），markers / 地面 / 墙 / 物件状态都先问这里。
## 约定见 docs/phone_and_cockpit_contract.md「驾驶舱」；美术在 art/cockpit/（缺的图一律用程序画的占位，图一放进来就用上，
## 还没导入的新 png 也直接从文件读）。
##
## 坐标：驾驶舱放在世界里很远的左边（ORIGIN，免得和森林的东西叠在一起），屏幕坐标 (sx, sy) = 世界 ORIGIN + (sx, sy)。
##   镜头固定在这一屏的中心（level_forest.gd 的 _cam_target）。
## art/cockpit/cockpit.json（美术给；缺哪项用 DEFAULT 的占位布局）。认这些写法：
##   "size": [w, h]  图多大；图在屏幕里水平居中、垂直居中（"screen_pos": [x, y] 可以指定图左上角在屏幕上的位置）
##   坐标：有负数（或 "anchor" 写着底边中点）= 相对图底边中点、y 往上为负（和 treehouse.json 一样）；不然 = 图里的像素
##   "floor_offset" / "floor_y" / "floor"：地板那一行（晨脚底）；"walk_min" / "walk_max" 或 "walk": [左, 右]：晨能走的范围
##   "window": {"x","y","w","h"} 或 [x, y, w, h]：前窗矩形（现在只当「窗外」这个 hotspot 的点击框；窗洞在 cockpit_back 里是透明的，
##       直接透出后面的船外背景，窗里不再单独画东西）
##   "markers" / "hotspots": {名字: x 或 {"x"} 或 [x, y]}（名字可以不带 cockpit_）= 晨站在这个 x 互动
##   "objects": {"cockpit_nav": {"x","y","w"（一帧的宽）,"h","frames","states": {"状态": 第几帧 或 [起, 止]（循环播）} 或 ["状态"…],
##       "fps"（循环播的帧率，默认 10 = 100ms 一帧）,"on": "cockpit_leak=steam"（只在那个物件是那个状态时显示）,"layer": "front",
##       "default": "hidden"（剧本还没 prop 过时的状态；hidden = 不显示，比如通讯器 cockpit_phone 要等 by_gauges 才放上去）}}
## 图（art/cockpit/）：
##   cockpit_back.png  室内（窗洞透明）；cockpit_front.png  机身外壳（在舱外看时盖住室内；晨在舱里时不显示）；cockpit_light.png（可选）
##   <物件 id>.png（横排多帧，按 states 换帧）；没有 states 的话找 <物件 id>_<state>.png
##   debris_*.png  躲碎石时在船外飞过的碎石（cockpit_debris.gd 用）
##   window_<state>.png / window_mask.png  旧的 57×39 窗内小图，10-29 起不再用（作者：「像 PPT」）
## 找不到某个状态的帧 / 图：打一行警告（每种一次），用第 0 帧，不崩。
##
## 船外背景（约定见 docs/flight_sky_contract.md）：一整屏连续的长镜头，画在 CanvasLayer（layer -10）里，不跟镜头走，
##   比屏幕每边大 SKY_M 像素（镜头抖不露边）；驾驶舱可见时才显示。窗洞透明，透出来的就是同一片背景。
##   art/cockpit/sky/sky.json（美术给；png 还没导入也直接从文件读）：
##     "layers": {id: {"img": "x.png", "tile": true（横向无缝卷）, "x"（不 tile 的默认 x）, "z"（可选，前后顺序）}}
##       画的前后顺序 = 顶层 layers 里写的顺序（先写的在最后面）；写了 "z" 按 z 从小到大。
##     "states": {剧本的 cockpit_window 状态: {"blend": 秒, "bg": [上, 下 两个颜色], "layers": [{"id","y","x","speed","vy","alpha"}]}}
##       y = 图上沿的屏幕 y；speed = 横向卷动（像素 / 秒，正 = 往右）；vy = 停在这个状态时每秒继续往下漂；alpha 默认 1。
##   换状态（剧本 prop cockpit_window）= 在 blend 秒里从「现在的样子」过渡到新关键帧，不硬切：
##     两个状态都有的同一层：y（x）、speed、alpha 插过去（smoothstep；起点接着旧的 vy 漂、终点按新 vy 漂，速度不跳）；
##       不 tile 的层新状态写了 x 才对 x 插值，不写就按 speed 接着走；tile 的层 x 一直按 speed 累加（横向无缝铺满）。
##     只在新状态里有的层：原地按新关键帧走、alpha 4 档淡入（0 / .25 / .5 / .75 / 1）；只在旧状态里有的：接着按旧的速度走、4 档淡出。
##     底色 bg：上下两端颜色在 blend 里渐变（画成横条，不是平滑渐变）；不写 bg 就保持现在的。所有位置画的时候取整到像素。
##     状态在 sky.json 里没有：保持现在的画面，警告一次。第一次设状态、跳节拍（ff）、驾驶舱还没显示时：直接到位，不过渡。
##   没有 sky.json：用 PH_SKY（同样的格式，图是 _ph_tex 程序画的：远山、树冠、远云、近云条、碎石带、三种大小的星球、灰楼、钟楼、水面），
##     按状态大致分森林 / 云 / 碎石 / 星球 / 城市，过渡规则完全一样。不退回窗内小图。
##   debris_layer：背景前、船后的一层（屏幕坐标），cockpit_debris.gd 往里加碎石和预告划痕。
##   图都要导入过（.import）：导出包里没有原始 png，_tex_file 的「直接从文件读」只在编辑器 / 开发时管用。
##   改完 tools/sky_art.py 重新生成以后，编辑器切回来会自己导入；命令行测试前跑一次 Godot --headless --import。
## 船上下挪：cockpit_debris.gd 设 ship_goal（目标，按住键时匀速走，最多 ±28），船本身 ship_dy 用欠阻尼弹簧追它
##   （_ship_step：角频率 SHIP_W、阻尼比 SHIP_Z = 0.6 → 先缓起、再缓停，停下时冲过头 1 像素再回来；按 1/60 秒分步算）。
##   ship_y() = ship_dy + 平时很轻的起伏（±1 像素、5.5 秒一个来回），取整；level_forest.gd 的 _update_camera 在驾驶舱里把
##   镜头 y 设成 135 − ship_y()（镜头反向偏移 → 晨、室内、物件一起挪，背景在 CanvasLayer 里不动）。
##   没在躲碎石（steering = false）时 ship_goal 每秒 SHIP_RETURN 像素回 0。ship_reset()：直接回中间、泛光熄掉。
## 反重力泛光（10-29 作者：「直接上下平移看着很奇怪……周围泛光，毕竟外星科技」）：glow = scripts/ship_glow.gd，
##   当室内图 _back_spr 的子节点（画在它后面），轮廓从 cockpit_back.png 的不透明像素算；每帧 glow.drive(ship_vy, delta)：
##   跟着船的竖直速度亮（整艘船一圈：船底一直是主光，往上挪时上沿也亮，两侧带一点），停住以后约 0.6 秒慢慢熄；
##   平时的 ±1 像素起伏不算进 ship_vy，完全不亮。船在画面上很大，glow.reach_scale = 1.5（光照得更远）。
##   hull()：从 cockpit_back.png 的不透明像素算出的船身轮廓（每列上下沿，屏幕坐标；尾翼那种比主船身高出去的部分夹到主船身的上下沿），
##   躲碎石的碰撞用它。

const ART := "res://art/cockpit/"
const ORIGIN := Vector2(-20000.0, 0.0)
const PREFIX := "cockpit_"
const SKY := "res://art/cockpit/sky/"
const SKY_M := 48                       # 船外背景比屏幕每边大这么多（镜头抖、船挪都不露边）
const BOB_SEC := 5.5                    # 平时飞行的上下起伏：一个来回多少秒（±1 像素）
const SHIP_W := 10.0                    # 船跟着 ship_goal 走的弹簧：角频率（越大跟得越紧）
const SHIP_Z := 0.6                     # 阻尼比（< 1：停下时冲过头 1 像素再回来；0.6 实测 28 → 29 → 28）
const SHIP_RETURN := 8.0                # 不在躲碎石时 ship_goal 每秒回中间多少像素
const SHIP_GLOW := preload("res://scripts/ship_glow.gd")

## 没有 sky.json 时的占位背景（格式和 sky.json 一样；图是 _ph_tex 程序画的）。屏幕 480×270，船身大约在 y 100..206、
## 窗洞大约在 (109..166, 114..153)：起飞时窗里要看得到树冠。
const PH_SKY := {
	"default_blend": 1.5,
	"layers": {
		"p_cloud_far": {"tile": true}, "p_planet_s": {}, "p_planet_m": {}, "p_ridge": {"tile": true}, "p_debris": {"tile": true},
		"p_city": {"tile": true}, "p_clock": {}, "p_trees": {"tile": true}, "p_water": {"tile": true}, "p_cloud_near": {"tile": true},
	},
	"states": {
		"forest_canopy": {"blend": 1.2, "bg": ["#0e1915", "#1c2f28"], "layers": [
			{"id": "p_ridge", "y": 116, "speed": 3}, {"id": "p_trees", "y": 110, "speed": 10}]},
		"canopy_fall": {"blend": 1.0, "layers": [
			{"id": "p_ridge", "y": 146, "speed": 3, "vy": 6}, {"id": "p_trees", "y": 170, "speed": 10, "vy": 30}]},
		"forest_below": {"blend": 1.2, "bg": ["#101c18", "#21352d"], "layers": [
			{"id": "p_cloud_far", "y": 20, "speed": 5, "alpha": 0.5},
			{"id": "p_ridge", "y": 188, "speed": 3, "vy": 5}, {"id": "p_trees", "y": 246, "speed": 8, "vy": 14}]},
		"forest_far": {"blend": 1.2, "layers": [
			{"id": "p_cloud_far", "y": 34, "speed": 6, "alpha": 0.75},
			{"id": "p_ridge", "y": 226, "speed": 2, "vy": 3}, {"id": "p_trees", "y": 300, "speed": 6}]},
		"turning": {"blend": 1.2, "bg": ["#14211d", "#283b34"], "layers": [
			{"id": "p_cloud_far", "y": 70, "speed": 26}, {"id": "p_ridge", "y": 290, "speed": 2},
			{"id": "p_cloud_near", "y": 150, "speed": 80, "alpha": 0.75}]},
		"clouds": {"blend": 1.5, "bg": ["#13201b", "#25362f"], "layers": [
			{"id": "p_cloud_far", "y": 46, "speed": 9}, {"id": "p_cloud_near", "y": 196, "speed": 34}]},
		"debris_wall": {"blend": 2.0, "bg": ["#0e1613", "#1a2621"], "layers": [
			{"id": "p_cloud_far", "y": 40, "speed": 7, "alpha": 0.5}, {"id": "p_debris", "y": 14, "speed": 12},
			{"id": "p_cloud_near", "y": 214, "speed": 30, "alpha": 0.75}]},
		"clouds_fast": {"blend": 1.0, "bg": ["#14211d", "#273932"], "layers": [
			{"id": "p_cloud_far", "y": 50, "speed": 36}, {"id": "p_cloud_near", "y": 182, "speed": 150}]},
		"river_planet": {"blend": 2.0, "bg": ["#0f1916", "#1e2e28"], "layers": [
			{"id": "p_cloud_far", "y": 60, "speed": 10, "alpha": 0.5}, {"id": "p_planet_s", "x": 300, "y": 30, "speed": 2},
			{"id": "p_cloud_near", "y": 212, "speed": 50, "alpha": 0.75}]},
		"river_city": {"blend": 1.5, "layers": [
			{"id": "p_cloud_far", "y": 40, "speed": 10, "alpha": 0.5}, {"id": "p_planet_m", "x": 236, "y": 6, "speed": 2},
			{"id": "p_city", "y": 236, "speed": 16, "vy": -6}]},
		"clocktower": {"blend": 1.2, "bg": ["#15211d", "#2b3a34"], "layers": [
			{"id": "p_cloud_far", "y": 34, "speed": 12, "alpha": 0.25}, {"id": "p_city", "y": 176, "speed": 22, "vy": -4},
			{"id": "p_clock", "x": 330, "y": 112, "speed": 22}]},
		"boats": {"blend": 1.2, "layers": [
			{"id": "p_city", "y": 158, "speed": 26}, {"id": "p_water", "y": 236, "speed": 34}]},
		"tilt": {"blend": 1.0, "layers": [{"id": "p_city", "y": 140, "speed": 34}, {"id": "p_water", "y": 214, "speed": 44}]},
		"skid": {"blend": 0.8, "layers": [{"id": "p_city", "y": 120, "speed": 60}, {"id": "p_water", "y": 190, "speed": 80}]},
		"channel": {"blend": 1.2, "bg": ["#13201c", "#24332d"], "layers": [
			{"id": "p_city", "y": 96, "speed": 14}, {"id": "p_water", "y": 176, "speed": 12}]},
		"crate": {"blend": 0.6, "layers": [{"id": "p_city", "y": 96, "speed": 0}, {"id": "p_water", "y": 176, "speed": 2}]},
	},
}

## 占位布局（没有 cockpit.json 时；屏幕坐标 480×270）：左边机头前窗和操纵台，往右驾驶座、副驾驶座、维修记录、右侧接口、工具盒、转化装置
const DEFAULT := {
	"floor_y": 222,
	"walk": [146, 436],
	"window": [22, 62, 144, 98],
	"markers": {
		"cockpit_console": 150, "cockpit_window": 150, "cockpit_nav": 190, "cockpit_seat": 182,
		"cockpit_copilot": 236, "cockpit_bag": 266, "cockpit_repair_log": 286, "cockpit_leak": 312,
		"cockpit_toolbox": 344, "cockpit_converter": 404, "cockpit_bell": 206,
	},
	"objects": {
		"cockpit_console": {"x": 18, "y": 160, "w": 160, "h": 62},
		"cockpit_nav": {"x": 176, "y": 90, "w": 36, "h": 26},
		"cockpit_seat": {"x": 166, "y": 176, "w": 26, "h": 46},
		"cockpit_copilot": {"x": 222, "y": 176, "w": 26, "h": 46},
		"cockpit_bag": {"x": 258, "y": 208, "w": 16, "h": 14},
		"cockpit_repair_log": {"x": 279, "y": 104, "w": 14, "h": 18},
		"cockpit_leak": {"x": 304, "y": 118, "w": 16, "h": 52},
		"cockpit_toolbox": {"x": 334, "y": 208, "w": 22, "h": 14},
		"cockpit_converter": {"x": 380, "y": 146, "w": 56, "h": 76},
		"cockpit_bell": {"x": 200, "y": 70, "w": 10, "h": 22},
	},
}
## 窗外 16 种状态（剧本 prop cockpit_window <state>）
const WINDOW_STATES := ["forest_canopy", "canopy_fall", "forest_below", "forest_far", "turning", "clouds", "debris_wall",
	"clouds_fast", "river_planet", "river_city", "clocktower", "boats", "tilt", "skid", "channel", "crate"]
## 剧本会用到的状态（--story_check 用；美术 json 的 states 里有的也算）
const KNOWN_STATES := {
	"cockpit_window": WINDOW_STATES,
	"cockpit_nav": ["stable", "route_broken", "detour", "fuel_short", "zoom", "river_in_range", "landing_zone"],
	"cockpit_converter": ["closed", "idle", "glow", "burn", "card_curl"],
	"cockpit_leak": ["default", "steam", "fixed"],
	"cockpit_toolbox": ["closed", "open"],
	"cockpit_repair_log": ["none", "check_1", "check_2"],
	"cockpit_console": ["normal", "dim", "main_off", "stone_shadow"],
	"cockpit_bell": ["bell", "empty_loop", "rope_swing", "moved", "rope_short"],
	"cockpit_phone": ["hidden", "by_gauges"],
}

# 占位的颜色（森林绿 / 青绿，不用蓝；室内偏暗，晨最亮）
const WALL_C := Color("#232a27")
const WALL_D := Color("#1b211f")
const FLOOR_C := Color("#2e3430")
const LINE_C := Color("#3f4a44")
const METAL_C := Color("#47524c")
const METAL_D := Color("#353e39")
const LAMP_C := Color("#c9b47a")
const SCREEN_C := Color("#0f1c18")
const SCREEN_L := Color("#7fc7a4")
const WARM_C := Color("#e0a35a")

var level: Node2D
var world: Node2D
var json := {}
var img_rect := Rect2(0, 0, 480, 270)     # 驾驶舱的图在屏幕上的位置
var floor_y := 222.0                      # 屏幕 y
var walk := Vector2(146, 436)            # 屏幕 x
var window_rect := Rect2(22, 62, 144, 98)   # 屏幕
var markers := {}                        # 名字 → 屏幕 x
var objects := {}                        # id → {rect: Rect2（屏幕）, frames, states: Dictionary 状态 → 帧 / [起, 止], fps, on, layer}
var states := {}                         # id → 现在的状态
var has_art := false                     # 有美术的室内图
# 船外背景 + 船上下挪
var sky := {}                            # sky.json（或占位 PH_SKY）
var sky_art := false                     # true = 用的是 art/cockpit/sky/sky.json
var debris_layer: Node2D                 # 背景前、船后（屏幕坐标）：cockpit_debris.gd 往里加碎石
var ship_goal := 0.0                     # 船要挪到哪（像素，正 = 往下）：cockpit_debris.gd 设（按住键时它匀速走，船本身用弹簧追它）
var ship_dy := 0.0                       # 船现在挪了多少（弹簧追 ship_goal：先缓起、再缓停、停下有 1 像素回弹）
var ship_vy := 0.0                       # 船现在的竖直速度（像素 / 秒）：泛光的强度跟着它
var steering := false                    # 正在躲碎石（不是的话 ship_goal 慢慢回 0）
var glow: Node2D                         # 船身周围的反重力泛光（scripts/ship_glow.gd）

var _back: Node2D                        # 晨后面：室内 → 物件
var _front: Node2D                       # 晨前面
var _sky_layer: CanvasLayer              # 船外背景（不跟镜头走）
var _sky_draw: Node2D
var _live := {}                          # 背景里现在在画的层：id → {tex, tile, z, mode（in / same / out）, x, y, a, sp, vy, 起点 x0…, 目标 tx…}
var _sky_state := ""
var _sky_t := 0.0                        # 换到现在这个状态多久了
var _sky_blend := 0.0
var _bg := [Color("#0f1a16"), Color("#1d2e28")]
var _bg_from := [Color("#0f1a16"), Color("#1d2e28")]
var _bg_to := [Color("#0f1a16"), Color("#1d2e28")]
var _hull := {}
var _back_spr: Sprite2D
var _draw_back: Node2D                   # 占位室内 + 没图的物件 + 程序画的白汽
var _draw_front: Node2D
var _sprites := {}                       # id → Sprite2D（有图的物件）
var _t := 0.0
var _warned := {}
var _rng := RandomNumberGenerator.new()
var _steam: Array = []
var _tex_cache := {}


# ======================================================================= 建
func setup(lv: Node2D, w: Node2D) -> void:
	level = lv
	world = w
	name = "Cockpit"
	_rng.seed = 11
	_read_json()
	_back = Node2D.new()
	_back.name = "CockpitBack"
	_back.position = ORIGIN
	_front = Node2D.new()
	_front.name = "CockpitFront"
	_front.position = ORIGIN
	var chen: Node2D = lv.chen
	lv.add_child(_back)
	lv.move_child(_back, chen.get_index())          # 晨后面
	lv.add_child(_front)
	lv.move_child(_front, chen.get_index() + 1)     # 晨前面
	# 船外背景：CanvasLayer 在整个世界后面，不跟镜头走（船上下挪 / 镜头抖时背景不动）；碎石层在它前面、船后面
	_read_sky()
	_sky_layer = CanvasLayer.new()
	_sky_layer.name = "CockpitSky"
	_sky_layer.layer = -10
	add_child(_sky_layer)
	_sky_draw = Node2D.new()
	_sky_draw.name = "Sky"
	_sky_draw.draw.connect(_draw_sky)
	_sky_layer.add_child(_sky_draw)
	debris_layer = Node2D.new()
	debris_layer.name = "Debris"
	_sky_layer.add_child(debris_layer)
	# 室内
	var bt := _art_tex(["cockpit_back", "cockpit", "cockpit_bg"])
	has_art = bt != null
	_back_spr = Sprite2D.new()
	_back_spr.centered = false
	_back_spr.texture = bt
	_back_spr.position = img_rect.position
	_back_spr.visible = bt != null
	_back.add_child(_back_spr)
	# 反重力泛光：有图 = 当室内图的子节点（画在它后面，轮廓从图的不透明像素算）；没图 = 按占位船身的大致范围
	glow = SHIP_GLOW.new()
	glow.reach_scale = 1.5                   # 驾驶舱的船占了大半个画面：光要照得更远才读得出是一圈光，不是描边
	if bt != null:
		_back_spr.add_child(glow)
		glow.set_from_texture(bt)
	else:
		_back.add_child(glow)
		var hl := hull()
		glow.set_hull(int(hl["x0"]), hl["top"], hl["bot"])
	_draw_back = Node2D.new()
	_draw_back.name = "Placeholder"
	_draw_back.draw.connect(_draw_room.bind(false))
	_back.add_child(_draw_back)
	var lt := _art_tex(["cockpit_light"])
	if lt != null:
		var l := Sprite2D.new()
		l.centered = false
		l.texture = lt
		l.position = img_rect.position
		_back.add_child(l)
	_draw_front = Node2D.new()
	_draw_front.draw.connect(_draw_room.bind(true))
	_front.add_child(_draw_front)
	# cockpit_front.png 是机身外壳（在舱外看时才盖上）：晨在舱里，不显示
	for id in objects:
		if str(objects[id].get("default", "")) != "" and not states.has(id):
			states[id] = str(objects[id]["default"])
		_refresh(str(id))
	# 窗外（船外背景）：剧本第一次 prop cockpit_window 时直接到位；还没设过就只有底色
	set_visible_all(false)


func set_visible_all(on: bool) -> void:
	visible = on
	_back.visible = on
	_front.visible = on
	_sky_layer.visible = on


## 读 cockpit.json，换成屏幕坐标
func _read_json() -> void:
	var j: Dictionary = {}
	if FileAccess.file_exists(ART + "cockpit.json"):
		var p = JSON.parse_string(FileAccess.get_file_as_string(ART + "cockpit.json"))
		if p is Dictionary:
			j = p
		else:
			push_warning("驾驶舱：art/cockpit/cockpit.json 读不了（JSON 不对？），用占位布局")
	json = j
	var size := _vec(j.get("size", [480, 270]), 270.0)
	var pos := Vector2(floorf((480.0 - size.x) / 2.0), floorf((270.0 - size.y) / 2.0))
	if j.has("screen_pos"):
		pos = _vec(j["screen_pos"])
	img_rect = Rect2(pos, size)
	# 相对图底边中点（有负数 / anchor 写着底边中点）还是图左上角
	var rel := str(j.get("origin", "")) == "bottom_center" or str(j.get("anchor", "")).contains("底边中点")
	if not j.has("origin") and not rel:
		for key in ["objects", "props", "markers", "hotspots"]:
			var d = j.get(key, {})
			if d is Dictionary:
				for k in d:
					if _vec(d[k]).x < 0.0:
						rel = true
	var off := pos + (Vector2(size.x / 2.0, size.y) if rel else Vector2.ZERO)
	if j.is_empty():
		off = Vector2.ZERO
	# 地板、能走的范围、窗户
	if j.has("floor_y") or j.has("floor"):
		floor_y = float(j.get("floor_y", j.get("floor", 0))) + off.y
	elif j.has("floor_offset"):
		floor_y = float(j["floor_offset"]) + (off.y if rel else off.y + size.y)
	else:
		floor_y = float(DEFAULT["floor_y"]) if j.is_empty() else off.y + (0.0 if rel else size.y) - 22.0
	if j.has("walk_min") or j.has("walk_max"):
		walk = Vector2(float(j.get("walk_min", -size.x / 2.0 + 30.0)), float(j.get("walk_max", size.x / 2.0 - 30.0))) + Vector2(off.x, off.x)
	elif j.has("walk"):
		walk = _vec(j["walk"]) + Vector2(off.x, off.x)
	else:
		walk = Vector2(DEFAULT["walk"][0], DEFAULT["walk"][1]) if j.is_empty() else Vector2(pos.x + 30.0, pos.x + size.x - 30.0)
	window_rect = _rect(j["window"], off) if j.has("window") else _rect(DEFAULT["window"], Vector2.ZERO)
	# markers：json 有就只用 json 的（名字补上 cockpit_）；没有 json 用占位布局
	var got := false
	for key in ["markers", "hotspots"]:
		var d = j.get(key, {})
		if d is Dictionary:
			for k in d:
				var n := _full(str(k))
				if not markers.has(n):
					markers[n] = _vec(d[k]).x + off.x
					got = true
	if not got:
		for k in DEFAULT["markers"]:
			markers[str(k)] = float(DEFAULT["markers"][k]) + (pos.x if not j.is_empty() else 0.0)
	var objs = j.get("objects", j.get("props", null))
	if objs is Dictionary and not (objs as Dictionary).is_empty():
		for k in objs:
			if objs[k] is Dictionary:
				objects[_full(str(k))] = _obj(objs[k], off)
	elif j.is_empty():
		for k in DEFAULT["objects"]:
			objects[str(k)] = _obj(DEFAULT["objects"][k], Vector2.ZERO)
	# 有物件没 marker：站在物件中间互动（夹进能走的范围）
	for id in objects:
		if not markers.has(id) and not (objects[id] as Dictionary).has("on"):
			markers[id] = clampf((objects[id]["rect"] as Rect2).get_center().x, walk.x, walk.y)
	if not markers.has("cockpit_window"):
		markers["cockpit_window"] = clampf(window_rect.get_center().x, walk.x, walk.y)


func _obj(o: Dictionary, off: Vector2) -> Dictionary:
	var w := float(o.get("w", 12))
	var h := float(o.get("h", 12))
	var x := float(o.get("x", 0)) + off.x
	var y := float(o.get("y", -h)) + off.y
	var st = o.get("states", {})
	var sd := {}
	if st is Dictionary:
		sd = st
	elif st is Array:
		for i in (st as Array).size():
			sd[str(st[i])] = i
	var e := {"rect": Rect2(x, y, w, h), "frames": int(o.get("frames", 1)), "states": sd, "default": str(o.get("default", "")),
		"fps": float(o.get("fps", 10.0)), "layer": str(o.get("layer", "back")), "loop": bool(o.get("loop", false))}
	if o.has("ms") and float(o["ms"]) > 0.0:
		e["fps"] = 1000.0 / float(o["ms"])
		e["loop"] = true
	if o.has("on"):
		var parts := str(o["on"]).split("=")
		if parts.size() == 2:
			e["on"] = [_full(parts[0].strip_edges()), parts[1].strip_edges()]
	return e


static func _full(n: String) -> String:
	return n if n.begins_with(PREFIX) else PREFIX + n


static func _vec(v, fy := 0.0) -> Vector2:
	if v is Array and v.size() >= 2:
		return Vector2(float(v[0]), float(v[1]))
	if v is Array and v.size() == 1:
		return Vector2(float(v[0]), fy)
	if v is Dictionary:
		return Vector2(float(v.get("x", 0.0)), float(v.get("y", fy)))
	if v is float or v is int:
		return Vector2(float(v), fy)
	return Vector2(0, fy)


static func _rect(v, off: Vector2) -> Rect2:
	if v is Array and v.size() >= 4:
		return Rect2(float(v[0]) + off.x, float(v[1]) + off.y, float(v[2]), float(v[3]))
	if v is Dictionary:
		return Rect2(float(v.get("x", 0)) + off.x, float(v.get("y", 0)) + off.y, float(v.get("w", 100)), float(v.get("h", 60)))
	return Rect2(22, 62, 144, 98)


## art/cockpit/ 里第一张存在的图（还没导入的新图也直接从文件读：图一放进来就能用）
func _art_tex(names: Array) -> Texture2D:
	for n in names:
		var t := _tex_file(ART + str(n) + ".png")
		if t != null:
			return t
	return null


## 一张图（res:// 路径）：导入过的 load，还没导入的直接从文件读；读不到 = null（记下来，不重复找）
func _tex_file(p: String) -> Texture2D:
	if _tex_cache.has(p):
		return _tex_cache[p]
	var t: Texture2D = null
	if ResourceLoader.exists(p):
		t = load(p)
	elif FileAccess.file_exists(p):
		var img := Image.load_from_file(ProjectSettings.globalize_path(p))
		if img != null:
			t = ImageTexture.create_from_image(img)
	_tex_cache[p] = t
	return t


func art(n: String) -> Texture2D:
	return _art_tex([n])


func _warn_once(msg: String) -> void:
	if _warned.has(msg):
		return
	_warned[msg] = true
	push_warning("驾驶舱：" + msg)


# ======================================================================= 给 story_world 用
func has_marker(n: String) -> bool:
	return markers.has(n) or objects.has(n)


func mx(n: String) -> float:
	if markers.has(n):
		return ORIGIN.x + float(markers[n])
	if objects.has(n):
		return ORIGIN.x + (objects[n]["rect"] as Rect2).get_center().x
	return ORIGIN.x + 240.0


func floor_world() -> float:
	return ORIGIN.y + floor_y


func walls() -> Vector2:
	return Vector2(ORIGIN.x + walk.x, ORIGIN.x + walk.y)


func center() -> Vector2:
	return ORIGIN + Vector2(240, 135)


func has_prop(id: String) -> bool:
	return id.begins_with(PREFIX)


## 物件在世界里的矩形（hotspot 的点击框、提示箭头）；窗户 = 窗户矩形；只有 marker 的（座椅）= 站的地方往上一块
func prop_rect(id: String) -> Rect2:
	var r := Rect2()
	if id == "cockpit_window":
		r = window_rect
	elif objects.has(id):
		r = objects[id]["rect"]
	elif markers.has(id):
		var x := float(markers[id])
		r = Rect2(x - 10.0, floor_y - 34.0, 20.0, 34.0)
	else:
		return Rect2()
	return Rect2(r.position + ORIGIN, r.size)


func sprite_for(id: String) -> Sprite2D:
	if _sprites.has(id) and (_sprites[id] as Sprite2D).visible:
		return _sprites[id]
	return null


func state_of(id: String) -> String:
	return str(states.get(id, ""))


## 剧本 prop：换状态（换帧 / 换图 / 占位换画法）；找不到就警告一次，不崩
func set_prop(id: String, st: String) -> void:
	states[id] = st
	if id == "cockpit_window":
		var story = level.get("story") if level != null else null
		var ff: bool = story != null and bool(story.get("ff"))
		_sky_go(st, ff or not visible or _sky_state == "")
		return
	if not objects.has(id):
		_warn_once("没有物件 %s 的位置（cockpit.json 里没有），只记状态 %s" % [id, st])
		return
	_refresh(id)
	# 跟着这个物件的状态显示的（漏气的白汽 cockpit_leak_steam：on = cockpit_leak=steam）
	for k in objects:
		var o: Dictionary = objects[k]
		if o.has("on") and str(o["on"][0]) == id:
			_refresh(str(k))


func _refresh(id: String) -> void:
	var o: Dictionary = objects[id]
	var st := str(states.get(id, ""))
	var short := id.trim_prefix(PREFIX)
	var tex: Texture2D = null
	var frame := 0
	var sd: Dictionary = o.get("states", {})
	var show := st != "hidden"
	if o.has("on"):
		show = state_of(str(o["on"][0])) == str(o["on"][1])
	if sd.is_empty() and st != "" and not st in ["default", "show", "shown", "hidden"]:
		tex = _art_tex([id + "_" + st, short + "_" + st])
	if tex == null:
		tex = _art_tex([id, short])
		if tex != null and st != "" and not sd.is_empty():
			if sd.has(st):
				var f = sd[st]
				frame = int(f[0]) if f is Array else int(f)
			elif not st in ["default", "show", "shown", "hidden"]:
				_warn_once("物件 %s 没有状态 %s（json 的 states 里没有），先用第 0 帧" % [id, st])
		elif tex != null and st != "" and sd.is_empty() and int(o.get("frames", 1)) <= 1 and not st in ["default", "show", "shown", "hidden"]:
			_warn_once("物件 %s 没有状态 %s 的图（%s_%s.png），先用原图" % [id, st, id, st])
	var s: Sprite2D = _sprites.get(id, null)
	if tex == null:
		if s != null:
			s.visible = false
		_draw_back.queue_redraw()
		_draw_front.queue_redraw()
		return
	if s == null:
		s = Sprite2D.new()
		s.centered = false
		(_front if str(o.get("layer", "back")) == "front" else _back).add_child(s)
		_sprites[id] = s
	s.texture = tex
	var r: Rect2 = o["rect"]
	var frames := maxi(1, int(o.get("frames", 1)))
	s.hframes = frames if tex.get_width() % frames == 0 and tex.get_width() >= frames * int(r.size.x) - 1 else 1
	s.frame = clampi(frame, 0, s.hframes - 1)
	s.position = r.position
	s.visible = show
	s.set_meta("anim", sd.get(st, null) if sd.get(st, null) is Array else (([0, frames - 1] if bool(o.get("loop", false)) else null)))
	_draw_back.queue_redraw()
	_draw_front.queue_redraw()


## 驾驶舱屏幕坐标 → 世界坐标
func world_pos(p: Vector2) -> Vector2:
	return p + ORIGIN


# ======================================================================= 每帧
func update(delta: float) -> void:
	if not visible:
		return
	_t += delta
	_sky_step(delta)
	if not steering:
		ship_goal = move_toward(ship_goal, 0.0, SHIP_RETURN * delta)     # 躲完碎石：船慢慢回到中间
	_ship_step(delta)
	# 物件循环播（states 里写成 [起, 止] 的，或 loop 的）
	for id in _sprites:
		var s: Sprite2D = _sprites[id]
		var a = s.get_meta("anim") if s.has_meta("anim") else null
		if a is Array and s.visible and s.hframes > 1:
			var o: Dictionary = objects.get(id, {})
			var a0 := int(a[0])
			var n := maxi(1, int(a[1]) - a0 + 1)
			s.frame = clampi(a0 + int(_t * float(o.get("fps", 10.0))) % n, 0, s.hframes - 1)
	# 漏气的白汽：美术没给 cockpit_leak_steam 图时程序画（小团往上飘、散开）
	var steam_art: bool = _sprites.has("cockpit_leak_steam")
	if state_of("cockpit_leak") == "steam" and objects.has("cockpit_leak") and not steam_art:
		var r: Rect2 = objects["cockpit_leak"]["rect"]
		if _rng.randf() < delta * 14.0:
			var src := Vector2(r.position.x + r.size.x * 0.5, r.position.y + r.size.y * 0.42)
			_steam.append({"p": src, "v": Vector2(_rng.randf_range(-10, -3), _rng.randf_range(-14, -6)), "life": _rng.randf_range(0.6, 1.2), "age": 0.0})
	for i in range(_steam.size() - 1, -1, -1):
		var p: Dictionary = _steam[i]
		p["age"] = float(p["age"]) + delta
		p["p"] = (p["p"] as Vector2) + (p["v"] as Vector2) * delta
		if float(p["age"]) >= float(p["life"]):
			_steam.remove_at(i)
	if not has_art or not _steam.is_empty():
		_draw_back.queue_redraw()


# ======================================================================= 占位：室内 + 物件（没有美术时，程序画，原生像素）
func _draw_room(front: bool) -> void:
	var c: CanvasItem = _draw_front if front else _draw_back
	if front:
		if has_art:
			return
		var cr: Rect2 = objects.get("cockpit_console", {"rect": Rect2(18, 160, 160, 62)})["rect"]
		c.draw_rect(Rect2(cr.position.x, floor_y - 2, cr.size.x - 26, 2), METAL_D)
		return
	var fy := floor_y
	if not has_art:
		var wr := window_rect
		c.draw_rect(Rect2(0, 0, 480, wr.position.y), WALL_D)
		c.draw_rect(Rect2(0, wr.end.y, 480, 270 - wr.end.y), WALL_D)
		c.draw_rect(Rect2(0, wr.position.y, wr.position.x, wr.size.y), WALL_D)
		c.draw_rect(Rect2(wr.end.x, wr.position.y, 480 - wr.end.x, wr.size.y), WALL_D)
		var top := 48.0
		c.draw_rect(Rect2(wr.end.x, top, walk.y + 30 - wr.end.x, fy - top), WALL_C)
		for k in 6:
			c.draw_rect(Rect2(wr.end.x + 40 * k, top + 4 * k - 2, walk.y + 30 - wr.end.x - 40 * k, 1), LINE_C.darkened(0.2))
		for x in range(int(wr.end.x) + 26, int(walk.y + 30), 34):
			c.draw_rect(Rect2(x, top, 1, fy - top), WALL_D)
			c.draw_rect(Rect2(x + 3, top + 10, 1, 1), LINE_C)
			c.draw_rect(Rect2(x + 3, fy - 12, 1, 1), LINE_C)
		c.draw_rect(Rect2(walk.y + 30, top - 8, 14, fy - top + 8), METAL_D)
		c.draw_rect(Rect2(0, fy, 480, 270 - fy), FLOOR_C)
		c.draw_rect(Rect2(0, fy, 480, 1), LINE_C)
		for x in range(6, 480, 12):
			c.draw_rect(Rect2(x, fy + 6, 6, 1), FLOOR_C.darkened(0.25))
		c.draw_rect(Rect2(wr.position.x - 3, wr.position.y - 3, wr.size.x + 6, 3), METAL_C)
		c.draw_rect(Rect2(wr.position.x - 3, wr.end.y, wr.size.x + 6, 3), METAL_C)
		c.draw_rect(Rect2(wr.position.x - 3, wr.position.y, 3, wr.size.y), METAL_C)
		c.draw_rect(Rect2(wr.end.x, wr.position.y, 3, wr.size.y), METAL_C)
		c.draw_rect(Rect2(250, top - 2, 18, 3), METAL_D)
		c.draw_rect(Rect2(254, top + 1, 10, 1), LAMP_C)
	for id in objects:
		if _sprites.has(id) or (objects[id] as Dictionary).has("on"):
			continue
		_draw_prop(c, str(id), objects[id]["rect"])
	for p in _steam:
		var a := 1.0 - float(p["age"]) / float(p["life"])
		var q: Vector2 = (p["p"] as Vector2).round()
		var sz := 1.0 + floorf(float(p["age"]) * 3.0)
		c.draw_rect(Rect2(q, Vector2(sz, sz)), Color(0.86, 0.92, 0.89, floorf(a * 4.0) / 4.0 * 0.7))


func _draw_prop(c: CanvasItem, id: String, r: Rect2) -> void:
	var st := state_of(id)
	if st == "hidden":
		return
	var x := r.position.x
	var y := r.position.y
	var w := r.size.x
	var h := r.size.y
	match id:
		"cockpit_console":
			c.draw_rect(Rect2(x, y, w, h), METAL_D)
			c.draw_rect(Rect2(x, y, w, 2), METAL_C)
			var lit := st != "main_off"
			var dim := st == "dim"
			for i in 9:
				var on := lit and (int(_t * 2.0 + i * 1.7) % 5 != 0 or dim)
				var col := SCREEN_L if i % 3 != 1 else WARM_C
				if dim:
					col = col.darkened(0.55)
				c.draw_rect(Rect2(x + 10 + i * 15, y + 8, 3, 2), col if on else METAL_C.darkened(0.3))
		"cockpit_nav":
			c.draw_rect(Rect2(x - 2, y - 2, w + 4, h + 4), METAL_C)
			c.draw_rect(Rect2(x, y, w, h), SCREEN_C)
			if state_of("cockpit_console") == "main_off":
				return
			var lc := SCREEN_L
			var a := Vector2(x + 4, y + h - 6)
			var b := Vector2(x + w - 6, y + 6)
			c.draw_rect(Rect2(a - Vector2(1, 1), Vector2(3, 3)), lc)
			c.draw_rect(Rect2(b - Vector2(2, 2), Vector2(5, 5)), Color("#8fb8c8"))
			match st:
				"route_broken":
					_dots(c, a, b, lc, 0.45)
				"fuel_short", "zoom":
					_dots(c, a, b, lc, 0.7)
				"landing_zone":
					c.draw_rect(Rect2(x + w / 2.0 - 3, y + h / 2.0 - 3, 7, 7), Color("#8fb8c8"))
				_:
					_dots(c, a, b, lc, 1.0)
		"cockpit_seat", "cockpit_copilot":
			c.draw_rect(Rect2(x + w - 8, y, 7, h - 18), Color("#3d3530"))
			c.draw_rect(Rect2(x, y + h - 20, w, 6), Color("#4a4038"))
			c.draw_rect(Rect2(x + w / 2.0 - 2, y + h - 14, 4, 14), METAL_D)
		"cockpit_repair_log":
			c.draw_rect(Rect2(x, y, w, h), Color("#b9b29c"))
			var checks := 2 if st == "check_2" else (1 if st == "check_1" else 0)
			for i in checks:
				c.draw_rect(Rect2(x + w - 4, y + 3 + i * 4, 2, 2), Color("#3f6b52"))
		"cockpit_leak":
			c.draw_rect(Rect2(x + 5, y, 6, h), METAL_C)
			c.draw_rect(Rect2(x + 3, y + h * 0.4, 10, 6), METAL_D if st != "fixed" else METAL_C.lightened(0.1))
		"cockpit_toolbox":
			c.draw_rect(Rect2(x, y + 4, w, h - 4), Color("#6b3f33"))
			c.draw_rect(Rect2(x - 2, y - 2, w + 4, 3) if st == "open" else Rect2(x, y + 2, w, 3), Color("#7d4b3d"))
		"cockpit_converter":
			c.draw_rect(Rect2(x, y, w, h), Color("#3a3f3a"))
			var door := Rect2(x + 12, y + 18, w - 24, 30)
			var open := st in ["idle", "glow", "burn", "card_curl"]
			c.draw_rect(door, Color("#151715") if open else METAL_D)
			var glow := {"glow": 0.45, "burn": 0.8, "card_curl": 0.55, "idle": 0.12}.get(st, 0.0) as float
			if glow > 0.0:
				c.draw_rect(Rect2(door.position.x + 2, door.end.y - 8, door.size.x - 4, 6), Color(WARM_C, floorf(glow * 6.0) / 6.0))
		_:
			c.draw_rect(r, Color("#5a5f58").lightened(0.2 if st != "" else 0.0))


func _dots(c: CanvasItem, a: Vector2, b: Vector2, col: Color, upto: float, step := 2) -> void:
	var n := int(maxf(absf(b.x - a.x), absf(b.y - a.y)))
	for i in range(0, int(n * upto) + 1, step):
		c.draw_rect(Rect2(a.lerp(b, float(i) / maxf(1.0, n)).round(), Vector2.ONE), col)


# ======================================================================= 船外背景（sky.json / 占位 PH_SKY）
func _read_sky() -> void:
	var p := SKY + "sky.json"
	if FileAccess.file_exists(p):
		var j = JSON.parse_string(FileAccess.get_file_as_string(p))
		if j is Dictionary and j.get("states", null) is Dictionary and j.get("layers", null) is Dictionary:
			sky = j
			sky_art = true
			return
		push_warning("驾驶舱：art/cockpit/sky/sky.json 读不了（JSON 不对？要有 layers 和 states），用程序画的占位背景")
	sky = PH_SKY
	sky_art = false


## 背景里一层的图：sky.json 的 img（art/cockpit/sky/ 下）；占位 = 程序画
func _sky_tex(id: String) -> Texture2D:
	var d = (sky.get("layers", {}) as Dictionary).get(id, null)
	if not d is Dictionary:
		_warn_once("船外背景：layers 里没有 %s" % id)
		return null
	if not sky_art:
		var key := "ph:" + id
		if not _tex_cache.has(key):
			_tex_cache[key] = _ph_tex(id)
		return _tex_cache[key]
	var t := _tex_file(SKY + str(d.get("img", id + ".png")))
	if t == null:
		_warn_once("船外背景：%s 的图 art/cockpit/sky/%s 找不到" % [id, d.get("img", id + ".png")])
	return t


## 前后顺序：顶层 layers 里写的顺序（先写的在后面）；写了 z 按 z
func _sky_z(id: String) -> float:
	var ls: Dictionary = sky.get("layers", {})
	var d = ls.get(id, {})
	if d is Dictionary and d.has("z"):
		return float(d["z"])
	return float(ls.keys().find(id))


static func _col(v, fallback: Color) -> Color:
	return Color.from_string(str(v), fallback) if v is String else fallback


## 换到状态 st：每一层从现在的样子出发，在 blend 秒里过渡到新关键帧（snap = 直接到位）
func _sky_go(st: String, snap: bool) -> void:
	var all_states: Dictionary = sky.get("states", {})
	if not all_states.has(st):
		_warn_once("船外背景没有状态 %s（%s 里没有），保持现在的画面" % [st, "sky.json" if sky_art else "占位 PH_SKY"])
		return
	var spec: Dictionary = all_states[st]
	_sky_state = st
	_sky_blend = 0.0 if snap else maxf(0.0, float(spec.get("blend", sky.get("default_blend", 2.0))))
	_sky_t = 0.0
	for id in _live:                          # 现在的样子 = 起点；先都当成要淡出的
		var L: Dictionary = _live[id]
		for k in ["x", "y", "a", "sp", "vy"]:
			L[k + "0"] = L[k]
		L["mode"] = "out"
	var ls = spec.get("layers", [])
	for e in (ls if ls is Array else []):
		if not e is Dictionary:
			continue
		var id := str(e.get("id", ""))
		var tex := _sky_tex(id)
		if tex == null:
			continue
		var d: Dictionary = (sky.get("layers", {}) as Dictionary).get(id, {})
		var L: Dictionary
		if _live.has(id):
			L = _live[id]
			L["mode"] = "same"
		else:
			L = {"tex": tex, "tile": bool(d.get("tile", false)), "z": _sky_z(id), "mode": "in"}
			L["x"] = float(e.get("x", d.get("x", 0.0)))
			L["y"] = float(e.get("y", d.get("y", 0.0)))
			L["a"] = 0.0
			L["sp"] = float(e.get("speed", 0.0))
			L["vy"] = float(e.get("vy", 0.0))
			for k in ["x", "y", "a", "sp", "vy"]:
				L[k + "0"] = L[k]
			_live[id] = L
		L["ty"] = float(e.get("y", L["y0"]))                         # 没写 y = 停在现在的高度
		if L["tile"]:
			L["tx"] = NAN                                            # tile 的层 x 一直按 speed 卷
		elif e.has("x"):
			L["tx"] = float(e["x"])
		else:
			L["tx"] = float(L["x0"]) if L["mode"] == "in" else NAN   # 没写 x：新出现的停在默认 x，原来就有的接着走
		L["tsp"] = float(e.get("speed", 0.0))
		L["tvy"] = float(e.get("vy", 0.0))
		L["ta"] = clampf(float(e.get("alpha", 1.0)), 0.0, 1.0)
	_bg_from = _bg.duplicate()
	var bg = spec.get("bg", null)
	if bg is Array and (bg as Array).size() >= 2:
		_bg_to = [_col(bg[0], _bg[0]), _col(bg[1], _bg[1])]
	else:
		_bg_to = _bg.duplicate()
	_sky_step(0.0)


## 每帧：按过渡进度 k（0..1）算每层的位置 / 透明度
func _sky_step(delta: float) -> void:
	_sky_t += delta
	var k := 1.0 if _sky_blend <= 0.0 else clampf(_sky_t / _sky_blend, 0.0, 1.0)
	var s := smoothstep(0.0, 1.0, k)
	var ks := floorf(k * 4.0) / 4.0                 # 透明度走 4 档台阶
	var gone: Array = []
	for id in _live:
		var L: Dictionary = _live[id]
		var m := str(L["mode"])
		if m == "out":
			L["x"] = float(L["x"]) + float(L["sp0"]) * delta
			L["y"] = float(L["y"]) + float(L["vy0"]) * delta
			L["a"] = float(L["a0"]) * (1.0 - ks)
			if k >= 1.0:
				gone.append(id)
			continue
		var fresh := m == "in" or k >= 1.0
		var sp := float(L["tsp"]) if fresh else lerpf(float(L["sp0"]), float(L["tsp"]), s)
		var y_to := float(L["ty"]) + float(L["tvy"]) * (_sky_t - _sky_blend)
		L["y"] = y_to if fresh else lerpf(float(L["y0"]) + float(L["vy0"]) * _sky_t, y_to, s)
		L["vy"] = float(L["tvy"]) if fresh else lerpf(float(L["vy0"]), float(L["tvy"]), s)
		var tx := float(L["tx"])
		if is_nan(tx):
			L["x"] = float(L["x"]) + sp * delta
		else:
			var x_to := tx + float(L["tsp"]) * (_sky_t - _sky_blend)
			L["x"] = x_to if fresh else lerpf(float(L["x0"]) + float(L["sp0"]) * _sky_t, x_to, s)
		L["sp"] = sp
		L["a"] = float(L["ta"]) * ks if m == "in" else lerpf(float(L["a0"]), float(L["ta"]), ks)
	for id in gone:
		_live.erase(id)
	_bg[0] = (_bg_from[0] as Color).lerp(_bg_to[0], s)
	_bg[1] = (_bg_from[1] as Color).lerp(_bg_to[1], s)
	_sky_draw.queue_redraw()


func _draw_sky() -> void:
	var c := _sky_draw
	# 底色：上下两端的渐变，画成 10 条横带（像素风）
	var n := 10
	var top := -SKY_M
	var full := 270 + SKY_M * 2
	for i in n:
		var y0 := top + full * i / n
		var y1 := top + full * (i + 1) / n
		c.draw_rect(Rect2(-SKY_M, y0, 480 + SKY_M * 2, y1 - y0), (_bg[0] as Color).lerp(_bg[1], float(i) / float(n - 1)))
	var ids := _live.keys()
	ids.sort_custom(func(a, b) -> bool: return float(_live[a]["z"]) < float(_live[b]["z"]))
	for id in ids:
		var L: Dictionary = _live[id]
		var a := float(L["a"])
		if a <= 0.01:
			continue
		var tex: Texture2D = L["tex"]
		var y := roundf(float(L["y"]))
		if y > 270.0 + SKY_M or y + tex.get_height() < -SKY_M:
			continue
		var col := Color(1, 1, 1, a)
		if L["tile"]:
			var w := float(tex.get_width())
			var x := fposmod(roundf(float(L["x"])), w) - w
			while x > -SKY_M:
				x -= w
			while x < 480.0 + SKY_M:
				c.draw_texture(tex, Vector2(x, y), col)
				x += w
		else:
			c.draw_texture(tex, Vector2(roundf(float(L["x"])), y), col)


## 船追 ship_goal：欠阻尼弹簧（先缓起、再缓停，停下时冲过头 1 像素左右再回来），按 1/60 秒分步算（帧率低也稳）；泛光跟着速度亮 / 熄
func _ship_step(delta: float) -> void:
	var left := delta
	while left > 0.0:
		var dt := minf(left, 1.0 / 60.0)
		left -= dt
		ship_vy += (SHIP_W * SHIP_W * (ship_goal - ship_dy) - 2.0 * SHIP_Z * SHIP_W * ship_vy) * dt
		ship_dy += ship_vy * dt
	if absf(ship_goal - ship_dy) < 0.05 and absf(ship_vy) < 0.5:
		ship_dy = ship_goal
		ship_vy = 0.0
	if glow != null:
		glow.drive(ship_vy, delta)


## 跳节拍 / 测试：船直接回中间、泛光熄掉
func ship_reset() -> void:
	ship_goal = 0.0
	ship_dy = 0.0
	ship_vy = 0.0
	if glow != null:
		glow.strength = 0.0


## 船现在往下挪了多少（像素，整数）：躲碎石的偏移 + 平时很轻的起伏
func ship_y() -> float:
	return roundf(ship_dy + sin(_t * TAU / BOB_SEC))


## 现在的船外背景状态（调试 / 测试用）
func sky_state() -> String:
	return _sky_state


## 船身轮廓（屏幕坐标，船没挪的时候）：{x0, top: 每列上沿, bot: 每列下沿, T: 主船身上沿, B: 主船身下沿}
## 从 cockpit_back.png 的不透明像素算；尾翼这种比主船身高出去 / 低出去的夹到主船身的上下沿（不然往下躲也躲不开尾翼）。
## 没有美术：用占位室内的大致范围。
func hull() -> Dictionary:
	if not _hull.is_empty():
		return _hull
	var tops := PackedInt32Array()
	var bots := PackedInt32Array()
	var x0 := int(img_rect.position.x)
	var oy := int(img_rect.position.y)
	var img: Image = null
	if has_art and _back_spr.texture != null:
		img = _back_spr.texture.get_image()
		if img != null and img.is_compressed():
			img.decompress()
	if img != null:
		for x in img.get_width():
			var t := -1
			var b := -1
			for y in img.get_height():
				if img.get_pixel(x, y).a > 0.5:
					if t < 0:
						t = y
					b = y
			tops.append(t)
			bots.append(b)
	else:
		x0 = 20
		oy = 0
		for x in 440:
			tops.append(48)
			bots.append(int(floor_y) + 20)
	var vt: Array = []
	var vb: Array = []
	for i in tops.size():
		if tops[i] >= 0:
			vt.append(tops[i])
			vb.append(bots[i])
	vt.sort()
	vb.sort()
	var tm: int = vt[vt.size() >> 1] if not vt.is_empty() else 40
	var bm: int = vb[vb.size() >> 1] if not vb.is_empty() else 146
	for i in tops.size():
		if tops[i] >= 0:
			tops[i] = maxi(tops[i], tm) + oy
			bots[i] = mini(bots[i], bm) + oy
	_hull = {"x0": x0, "top": tops, "bot": bots, "T": tm + oy, "B": bm + oy}
	return _hull


# ----------------------------------------------------------------------- 占位背景的图（程序画；森林绿 / 青绿，暗、低对比）
func _ph_tex(id: String) -> Texture2D:
	var img: Image
	var r := RandomNumberGenerator.new()
	r.seed = hash(id)
	match id:
		"p_ridge":
			img = _ph_img(480, 90)
			for x in 480:
				var u := x * TAU / 480.0
				var t := int(16.0 + 7.0 * sin(u * 3.0) + 4.0 * sin(u * 7.0 + 1.0) + 2.0 * sin(u * 17.0))
				img.fill_rect(Rect2i(x, t, 1, 90 - t), Color("#182922"))
				img.set_pixel(x, t, Color("#22362d"))
		"p_trees":
			img = _ph_img(480, 200)
			for x in 480:
				var u := x * TAU / 480.0
				var t := int(12.0 + 5.0 * sin(u * 11.0) + 4.0 * sin(u * 23.0 + 2.0) - 4.0 * absf(sin(u * 37.0)))
				img.fill_rect(Rect2i(x, t, 1, 200 - t), Color("#10201a"))
				img.set_pixel(x, t, Color("#2a4236"))
				if x % 29 == 0:
					img.fill_rect(Rect2i(x, t + 14, 1, 186 - t), Color("#0c1814"))
		"p_cloud_far":
			img = _ph_img(480, 50)
			for x in 480:
				var u := x * TAU / 480.0
				var t := int(20.0 + 8.0 * sin(u * 4.0) + 5.0 * sin(u * 9.0 + 0.7))
				var b := int(34.0 + 4.0 * sin(u * 5.0 + 2.0))
				if b > t:
					img.fill_rect(Rect2i(x, t, 1, b - t), Color("#2c3f38"))
					img.set_pixel(x, t, Color("#3b524a"))
		"p_cloud_near":
			img = _ph_img(480, 40)
			for i in 9:
				var x0 := r.randi_range(0, 479)
				var y := r.randi_range(2, 36)
				var w := r.randi_range(24, 90)
				var h := r.randi_range(1, 3)
				for x in range(x0, x0 + w):
					img.fill_rect(Rect2i(x % 480, y, 1, h), Color(0.55, 0.64, 0.6, 0.85))
		"p_debris":
			img = _ph_img(480, 80)
			for i in 46:
				var x := r.randi_range(0, 470)
				var y := int(40.0 + 30.0 * sin(x * TAU / 480.0 * 2.0) * 0.6 + r.randf_range(-22.0, 22.0))
				var s := r.randi_range(2, 6)
				img.fill_rect(Rect2i(x, clampi(y, 0, 74), s, maxi(2, s - 1)), Color("#1f2624"))
				img.set_pixel(x, clampi(y, 0, 74), Color("#46524c"))
		"p_planet_s", "p_planet_m", "p_planet_l":
			var rad: int = {"p_planet_s": 12, "p_planet_m": 26, "p_planet_l": 44}[id]
			img = _ph_img(rad * 2 + 2, rad * 2 + 2)
			for y in rad * 2 + 1:
				for x in rad * 2 + 1:
					var dx := x - rad
					var dy := y - rad
					var d2 := dx * dx + dy * dy
					if d2 <= rad * rad:
						var col := Color("#284740")
						if dx + dy > rad * 0.6:
							col = Color("#1d3530")
						if d2 > (rad - 2) * (rad - 2) and dx + dy < 0:
							col = Color("#4a6e62")
						img.set_pixel(x, y, col)
		"p_city":
			img = _ph_img(480, 150)
			var x := 0
			while x < 480:
				var w := r.randi_range(14, 30)
				var h := r.randi_range(50, 140)
				var ww := mini(w, 480 - x)
				img.fill_rect(Rect2i(x, 150 - h, ww, h), Color("#343a38") if (x / 7) % 2 == 0 else Color("#2d3331"))
				img.fill_rect(Rect2i(x, 150 - h, ww, 1), Color("#454c49"))
				for wy in range(150 - h + 5, 146, 6):
					for wx in range(x + 3, x + ww - 2, 5):
						if r.randf() < 0.45:
							img.set_pixel(wx, wy, Color("#4b5450"))
				x += w + r.randi_range(1, 3)
		"p_clock":
			img = _ph_img(22, 120)
			img.fill_rect(Rect2i(4, 18, 14, 102), Color("#353b39"))
			img.fill_rect(Rect2i(8, 4, 6, 14), Color("#353b39"))
			img.fill_rect(Rect2i(10, 0, 2, 4), Color("#353b39"))
			for y in 9:
				for x in 9:
					if (x - 4) * (x - 4) + (y - 4) * (y - 4) <= 16:
						img.set_pixel(7 + x, 22 + y, Color("#7f8a84"))
			img.set_pixel(11, 24, Color("#353b39"))
			img.set_pixel(11, 25, Color("#353b39"))
			img.set_pixel(12, 26, Color("#353b39"))
		"p_water":
			img = _ph_img(480, 100)
			img.fill_rect(Rect2i(0, 0, 480, 100), Color("#1a2d29"))
			img.fill_rect(Rect2i(0, 0, 480, 1), Color("#2f4a43"))
			for i in 40:
				var x := r.randi_range(0, 479)
				var y := r.randi_range(4, 96)
				for k in r.randi_range(4, 14):
					img.set_pixel((x + k) % 480, y, Color("#26403a"))
		_:
			img = _ph_img(8, 8)
	return ImageTexture.create_from_image(img)


static func _ph_img(w: int, h: int) -> Image:
	return Image.create(w, h, false, Image.FORMAT_RGBA8)
