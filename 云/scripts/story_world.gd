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
##   剧本里 room_* 的 marker：第四版起是「相对树屋锚点的 x」（有负数就按这个算：树屋 x + 值）；第一版是 480 宽一屏的房间内 x
##   （按比例压进屋内可走范围）。两种都是：json 的 hotspots 里有同名的点（去掉 room_；kettle = stove 等别名）就用 json 的。
##   json objects 里有、PROPS 表里没有的东西（油灯 lamp、灯下的痕迹 lamp_mark、明信片 postcard、零件包装 part_pack、工具墙 toolwall……）
##   自动当成物件（图 = art/forest_story/<objects 里的名字>.png）。剧本 prop 步骤用 room_<名字> 也认（去掉 room_）。
##   剧本里给过 shown 状态的物件一开始藏着（明信片：弥洛最后才拿出来）。taken = 拿走了（藏起来）。
##   图旁边 json 的 "states": [..] = 同一张图里按状态换帧（gramophone old/new）。treehouse 和 room_door 这两个 marker 都改成门的 x（在门口互动、进出屋不跳）。
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
## 地面贴片（图旁边 json 有 ground_row 的：塌陷口 hollow、蹄印 hoofprints、凹陷 depressions）：按「列」画，每一列各自对齐到
##   那一列的地面（ground_fn 不是平的，±3 像素起伏），图里 ground_row 那一行正好压在地面最上面一行，严丝合缝。
##   凹陷（TERRAIN_PROPS）还改地形：凹下去的地方，晨和 NPC 的脚跟着凹下去（踩在图里凹陷的底上，从图里每一列读出来）。
## 坡地远处那堵雾（fog_bank.png）：底边压进地面以下（主层的地面盖住它的下沿，不露直边），左右两头分档淡掉。
## 区域（第三版）：森林分两段，按 x 分：旧路段 A = wall_left .. A 的右边，树屋段 B = B 的左边 .. wall_right。
##   A 的右边：倒木推开之前到倒木为止；塌陷口没搭桥之前停在坑边；木板搭成桥（prop plank:bridge）以后一直到 wall_glade
##   （林间空地 glade：岩画、信号箱、路标底座），没有 wall_glade 就到 wall_road。
##   B 的左边：有 house_return（回旧路的入口）就是它，不然 wall_house。晨在 B 往左走到入口（顶着走一小会儿）→
##   黑屏换到旧路段的 road_return（没有就是布条 cloth 那里），见 level_forest.gd 的 _update_portal。双向都能走。
## 被撞断的树冠缺口（第五版，改成单独一屏）：森林的视差层里不挂它（Mid 层 960 宽循环，贴进去每隔一段就重复一次，
##   标题画面上也有，也融不进背景），任何层、任何时候都没有。它是一张单独的全屏画面：
##   art/forest_story/treeline_view_<sky|far|main|near>.png（480×270 起，平面侧视：坠毁现场那排树冠，中间被撞出一道弧形凹口）
##   + treeline_view.json（layers 从后往前、drift 每层每秒往左漂几像素、arc_layer 弧在哪一层、arc_end_left 等弧在那层图里的坐标）。
##   tools/forest_story_art.py --treeline 生成。用法：
##     treeline_view_in(sec) / treeline_view_out(sec)：淡入 / 淡出这一屏（CanvasLayer 9：世界含 Front 之上，暗角 / 界面之下；
##       四层放在一个 CanvasGroup 里整体淡，淡到一半也不会一层层透出底下的森林）。出来以后各层按 drift 整像素地漂，
##       漂到图的右边缘贴着屏幕右边就停。这一屏淡入时左上角的目标 / 燃料和右上角的背包一起淡出（level_forest.gd 的
##       hud_fade），淡出时淡回来；对话框挪到画面下方居中、不带尖角（story_runner.gd 的 _anchor），不挡凹口。
##     match_arc(hold)：那一屏出来以后，把 drawing_arc.png 最近邻放大 scale_to_treeline 倍（drawing_arc.json），
##       arc_end_left 对到 treeline_arc_end_left（main 层图内坐标），挂在 main 层下面跟着它漂，任何一帧都和凹口对齐；
##       淡入到 0.8、停 hold 秒、淡出。
##   剧本 treeline_match（story_runner.gd）和看树冠缺口的 hotspot（at = treeline_gap）都用这一屏。缺图就什么都不做。
##   旧的 broken_treeline.png / .json 留在文件夹里，代码不再用。
## 远处有东西走过（elephant_call，sway_canopy）：中远景层上一段树冠从一侧到另一侧依次轻晃 1 像素，不露面。
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
	"road_house": 1250, "glade_rock": 2080, "glade_sign_base": 2130, "signal_box": 2180, "wall_glade": 2260,
	"pine": 3700, "shop_plank": 3640,
	"wall_house": 2880, "treehouse": 3100, "empty_house": 3400, "shop": 3620, "slope": 3900, "wall_right": 4100,
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
const TERRAIN_PROPS := ["depressions"]   # 凹下去的地方晨的脚跟着凹（见文件头）
const EDGE_FADE_SHADER := "shader_type canvas_item;\nuniform float fade = 0.12;\nvoid fragment() {\n" + \
	"\tvec4 c = texture(TEXTURE, UV) * COLOR;\n\tfloat e = min(UV.x, 1.0 - UV.x) / fade;\n" + \
	"\tc.a *= floor(clamp(e, 0.0, 1.0) * 4.0) / 4.0;\n\tCOLOR = c;\n}\n"

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
	# ---- 第三版：小空屋、林间空地、松树、木板、闹钟、送还以后摆回原处的东西
	"road_house": {"tex": "road_house.png", "at": "road_house", "size": [80, 60], "color": "#312e28"},
	"glade_rock": {"tex": "glade_rock.png", "at": "glade_rock", "size": [120, 70], "color": "#3a3d38"},
	"signal_box": {"tex": "signal_box.png", "at": "signal_box", "size": [30, 50], "color": "#3d4440"},
	"sign_base": {"tex": "sign_base.png", "at": "glade_sign_base", "size": [14, 8], "color": "#4a4136"},
	"pine_sap": {"tex": "pine_sap.png", "at": "pine", "size": [40, 90], "color": "#2e2a20", "frames": 2, "anim": 900},
	"plank": {"tex": "plank.png", "at": "shop_plank", "size": [30, 5], "color": "#6b5638",
		"states": {"bridge": {"tex": "plank_bridge.png", "at": "hollow", "dx": 0, "size": [70, 8], "visible": true},
			"taken": {"visible": false}}},
	"clock_window": {"tex": "clock_window.png", "at": "empty_house", "dx": 22, "dy": -36, "size": [8, 8], "color": "#7a6d55"},
	"shop_jar": {"tex": "shop_jar.png", "at": "shop", "dx": -31, "dy": -25, "size": [8, 9], "color": "#7d8a80"},
	"shop_photo": {"tex": "shop_photo.png", "at": "shop", "dx": 36, "dy": -32, "size": [9, 7], "color": "#8a8070"},
	"placed_radio": {"tex": "placed_radio.png", "at": "stall", "dx": 18, "dy": -30, "size": [12, 9], "color": "#6a5e4c", "hidden": true,
		"states": {"placed": {"visible": true}}},
	"placed_sign": {"tex": "placed_sign.png", "at": "glade_sign_base", "dy": -6, "size": [8, 24], "color": "#6b5a40", "hidden": true,
		"states": {"placed": {"visible": true}}},
	"placed_lamp": {"tex": "placed_lamp.png", "at": "road_house", "dx": 14, "dy": -20, "size": [6, 10], "color": "#8a7244", "hidden": true,
		"states": {"placed": {"visible": true}}},
	"depressions": {"tex": "depressions.png", "at": "slope", "size": [220, 14], "color": "#1f2723", "sink": 10},
	"fog_bank": {"tex": "fog_bank.png", "at": "slope", "dx": 180, "size": [480, 120], "layer": "fog", "fog": true, "sink": 4, "edge_fade": true},
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
const HOLLOW_EDGE := 12.0                # 塌陷口：晨最远走到它中心左边这么多（坑边）
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
var forest_ground: Callable             # 主层原来的地面（物件按它摆）
var _terrain: Array = []                 # [{x0, x1, top: PackedFloat32Array 每列地面那一行}]：凹陷改过的地形
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
var cockpit: Node2D                      # 驾驶舱（scripts/cockpit_room.gd；剧本 rooms 里有 cockpit 才建，见 add_cockpit）


var _script_markers := {}
var _room_relative := false          # 剧本的 room_* 是相对树屋锚点的 x（第四版）
var _start_hidden := {}              # 剧本里给过 shown 状态的物件：一开始藏着
var _lit_t := 0.0                    # fog:lit：雾里被照亮一下


func setup(lv: Node2D, script_markers: Dictionary, steam_at := "", shown_ids: Array = []) -> void:
	level = lv
	chen = lv.chen
	_script_markers = script_markers
	for k in script_markers:
		if str(k).begins_with("room_") and (script_markers[k] is float or script_markers[k] is int) and float(script_markers[k]) < 0.0:
			_room_relative = true
	for id in shown_ids:
		_start_hidden[str(id).trim_prefix("room_")] = true
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
	_make_house_objects()
	_add_room_light()
	chen.ground_fn = walk_ground
	_add_cloth_glow()
	_load_treeline()
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
	if cockpit != null and cockpit.has_marker(s):
		return {"ok": true, "x": cockpit.mx(s), "room": "cockpit"}
	if markers.has(s):
		return {"ok": true, "x": float(markers[s]), "room": "treehouse" if s.begins_with("room_") else "forest"}
	var pid := s.trim_prefix("room_")
	if _cfg.has(s) or _cfg.has(pid):
		var id := s if _cfg.has(s) else pid
		var p: Sprite2D = props[id]
		return {"ok": true, "x": p.position.x, "room": _cfg[id].get("room", "forest")}
	return {"ok": false, "x": 0.0, "room": room}


func has_marker(s: String) -> bool:
	return markers.has(s) or _cfg.has(s) or _cfg.has(s.trim_prefix("room_")) or extra_rects.has(s) or (cockpit != null and cockpit.has_marker(s))


func mx(name: String) -> float:
	return float(markers.get(name, DEFAULT_MARKERS.get(name, 0.0)))


## 脚底那一行（世界 y）：晨 / NPC 的 position.y = round(这个) + 1
func ground_at(x: float, r := "") -> float:
	if r == "":
		r = room
	if r == "treehouse":
		return float(house["floor"])
	if r == "cockpit" and cockpit != null:
		return cockpit.floor_world()
	return walk_ground(x)


## 晨 / NPC 在森林里踩的地面：主层地面，凹陷那里换成凹陷的底
func walk_ground(x: float) -> float:
	for t in _terrain:
		var td: Dictionary = t
		if x >= float(td["x0"]) and x < float(td["x1"]):
			var col := int(floor(x - float(td["x0"])))
			var arr: PackedFloat32Array = td["top"]
			if col >= 0 and col < arr.size() and arr[col] > -9000.0:
				return arr[col]
	return float(forest_ground.call(x))


## 进屋 / 出屋：前墙淡出 / 淡入（instant = 跳节拍时直接到位），晨的地面换成屋内那条直线
func set_room(r: String, instant := false) -> void:
	room = r
	if r == "treehouse":
		var gy: float = house["floor"]
		chen.ground_fn = func(_x: float) -> float: return gy
	elif r == "cockpit" and cockpit != null:
		var cy: float = cockpit.floor_world()
		chen.ground_fn = func(_x: float) -> float: return cy
		cockpit.set_visible_all(true)
	else:
		chen.ground_fn = walk_ground
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


## 站在 x、半宽 half 的人和前墙（不透明的那段）重不重叠
func overlaps_front(x: float, half: float) -> bool:
	return x + half > float(house["front_x0"]) and x - half < float(house["front_x1"])


## x 在不在前墙（不透明的那段）里面
func behind_front(x: float) -> bool:
	return x > float(house["front_x0"]) and x < float(house["front_x1"])


## x 在不在树屋那一片（进出屋不黑屏用）
func near_house(x: float) -> bool:
	return absf(x - float(house["cx"])) < float(house["w"]) / 2.0 + 120.0


## 晨现在这一段的左右墙（世界 x）
func walls(x: float) -> Vector2:
	if in_room():
		return house["walk"]
	if room == "cockpit" and cockpit != null:
		return cockpit.walls()
	if x < area_split():
		# 看得见的边：倒木推开之前到倒木为止；塌陷口是个坑，没搭桥就停在坑边；搭了桥一直到林间空地的尽头
		var r := a_end()
		if bridged():
			r = maxf(r, mx("wall_glade") if markers.has("wall_glade") else mx("wall_road"))
		else:
			r = minf(r, mx("hollow") - HOLLOW_EDGE)
		if prop_state("log") != "moved" and not StoryState.has("log_cleared"):
			r = minf(r, mx("log") + LOG_BLOCK)
		return Vector2(mx("wall_left"), r)
	return Vector2(b_start(), mx("wall_right"))


func bridged() -> bool:
	return prop_state("plank") == "bridge"


## 旧路段最右能到哪（不算倒木 / 塌陷口）
func a_end() -> float:
	return mx("wall_road")


## 树屋段最左（回旧路的入口）
func b_start() -> float:
	return mx("house_return") if markers.has("house_return") else mx("wall_house")


## 两段的分界（x 小于它就是旧路段）
func area_split() -> float:
	var a := maxf(mx("wall_road"), mx("wall_glade") if markers.has("wall_glade") else 0.0)
	return (a + b_start()) / 2.0


func area_of(x: float) -> String:
	if in_room():
		return "house"
	if room == "cockpit":
		return "cockpit"
	return "road" if x < area_split() else "trees"


# ======================================================================= 物件
func _make_prop(id: String) -> void:
	var c: Dictionary = _base_cfg(id)
	_merge_meta(c)
	_anchor_cfg(id, c)
	_cfg[id] = c
	var s := Sprite2D.new()
	s.name = "P_" + id
	s.centered = false
	s.set_meta("ground_row", int(c.get("ground_row", 0)))
	if c.get("layer", "") == "fog":
		_fog_layer.add_child(s)
	else:
		_forest_layer.add_child(s)
	props[id] = s
	_apply_look(id, c)
	s.visible = not c.get("hidden", false) and not _start_hidden.has(id)
	_place(id)
	if id in TERRAIN_PROPS:
		_build_terrain(id)


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
		if j["ms"] is Array:
			# 每帧不一样长（松脂：平时 1.6 秒，闪一下 0.2 秒）
			var seq: Array = j["ms"]
			var total := 0.0
			for m in seq:
				total += float(m)
			c["anim_seq"] = seq
			c["anim"] = total
		else:
			c["anim"] = float(j["ms"])
	if j.has("states") and j["states"] is Array:
		c["state_frames"] = j["states"]
	if j.has("host") and j.has("offset"):
		# 叠在另一个物件上：位置 = 那个物件的锚点 + offset（底边中点）
		c["host"] = str(j["host"])
		c["host_off"] = _vec(j["offset"])
	if j.has("ground_row") and c.get("room", "forest") == "forest":
		c["ground_row"] = int(j["ground_row"])


func _apply_look(id: String, c: Dictionary) -> void:
	var s: Sprite2D = props[id]
	s.set_meta("ground_row", int(c.get("ground_row", 0)))
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
		_column_draw(s, true)
	else:
		_column_draw(s, false)
	if c.get("edge_fade", false) and not s.get_meta("placeholder", false):
		var sh := Shader.new()
		sh.code = EDGE_FADE_SHADER
		var m := ShaderMaterial.new()
		m.shader = sh
		s.material = m


## 地面贴片按列画：精灵本身不画（self_modulate 透明），子节点每列一条、各自对齐到那一列的地面
func _column_draw(s: Sprite2D, on: bool) -> void:
	var cols: Node2D = s.get_node_or_null("Cols")
	if not on:
		if cols != null:
			cols.queue_free()
			s.self_modulate.a = 1.0
		return
	s.self_modulate.a = 0.0
	if cols == null:
		cols = Node2D.new()
		cols.name = "Cols"
		s.add_child(cols)
		cols.draw.connect(_draw_columns.bind(s, cols))
	cols.queue_redraw()


func _draw_columns(s: Sprite2D, cols: Node2D) -> void:
	var gr: int = int(s.get_meta("ground_row", 0))
	var fw := s.texture.get_width() / s.hframes
	var fh := s.texture.get_height()
	var fx := (s.frame % s.hframes) * fw
	for cx in fw:
		var wx := s.position.x + s.offset.x + cx
		var gy := roundf(float(forest_ground.call(wx)))
		var top := gy - gr - s.position.y                  # 这一列图的顶在精灵坐标里的 y
		cols.draw_texture_rect_region(s.texture, Rect2(s.offset.x + cx, top, 1, fh), Rect2(fx + cx, 0, 1, fh))


## 凹陷改地形：每一列从 ground_row 往下找第一个「亮」的像素（凹陷的底那条亮边），那一行就是脚踩的地面
func _build_terrain(id: String) -> void:
	var s: Sprite2D = props[id]
	if s.get_meta("placeholder", false) or not s.visible:
		return
	var img := s.texture.get_image()
	if img == null:
		return
	if img.is_compressed():
		img.decompress()
	var gr: int = int(s.get_meta("ground_row", 0))
	var fw := img.get_width() / s.hframes
	var x0 := s.position.x + s.offset.x
	var top := PackedFloat32Array()
	top.resize(fw)
	for cx in fw:
		top[cx] = -9999.0
		if img.get_pixel(cx, gr).a < 0.5:
			continue                                  # 这一列不是凹陷（两个坑中间的地面）
		var gy := roundf(float(forest_ground.call(x0 + cx)))
		for r in range(gr, img.get_height()):
			var p := img.get_pixel(cx, r)
			if p.a > 0.5 and p.get_luminance() > 0.2:
				top[cx] = gy + float(r - gr)
				break
	_terrain.append({"x0": x0, "x1": x0 + fw, "top": top})


func _place(id: String) -> void:
	var c: Dictionary = _cfg[id]
	var s: Sprite2D = props[id]
	if c.has("host") and props.has(str(c["host"])) and str(c["host"]) != id:
		var hs: Sprite2D = props[str(c["host"])]
		s.position = (hs.position + (c["host_off"] as Vector2)).round()
		return
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
	id = prop_id(id)
	if save:
		StoryState.set_prop(id, state)
	if cockpit != null and cockpit.has_prop(id):
		cockpit.set_prop(id, state)
		return
	if id == "fog":
		if state == "lit":
			_lit_t = 1.6                   # 发光木头举起来：雾里亮一下，布条、蹄印被照到
		else:
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
	var base: Dictionary = _base_cfg(id)
	_merge_meta(base)
	_anchor_cfg(id, base)
	if id == "pipe_steam":
		base = (_cfg[id] as Dictionary).duplicate(true)
	var c: Dictionary = base.duplicate(true)
	if state in ["hidden", "hide", "gone", "taken"]:
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
	if str(c.get("tex", "")) != str(base.get("tex", "")):
		for k in ["host", "host_off", "ground_row", "frames", "anim", "anim_seq"]:
			c.erase(k)
		_merge_meta(c)                     # 换了图：读新图自己的 json（木板搭成桥：和塌陷口同位置、同 ground_row）
	_cfg[id] = c
	_apply_look(id, c)
	s.visible = bool(c.get("visible", true))
	var fs: Dictionary = FRAME_STATES.get(id, {})
	var sf: Array = c.get("state_frames", [])
	if sf.has(state) and s.hframes > sf.find(state):
		s.frame = sf.find(state)
	elif fs.has(state) and s.hframes > int(fs[state]):
		s.frame = int(fs[state])
	elif s.get_meta("placeholder", false) and not st.has("tex"):
		s.self_modulate = Color(1.25, 1.2, 1.1)     # 色块：亮一档，看得出换了状态
	_place(id)


func prop_state(id: String) -> String:
	return str(StoryState.props.get(prop_id(id), ""))


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
		elif _room_relative and _script_markers.has(name):
			markers[name] = float(house["cx"]) + float(_script_markers[name])
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
	# 前墙实际不透明的横向范围（世界 x）：弥洛换前后图层只在不和它重叠的时候换（story_runner 的 _update_miluo_layer）
	house["front_x0"] = c.x - size.x / 2.0
	house["front_x1"] = c.x + size.x / 2.0
	if ft != null:
		var fimg := ft.get_image()
		if fimg != null:
			var fy := fimg.get_height() - 4
			var x0 := -1
			var x1 := -1
			for fx in fimg.get_width():
				if fimg.get_pixel(fx, fy).a > 0.5:
					if x0 < 0:
						x0 = fx
					x1 = fx
			if x0 >= 0:
				house["front_x0"] = c.x - size.x / 2.0 + x0
				house["front_x1"] = c.x - size.x / 2.0 + x1 + 1
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


## treehouse.json objects 里有、PROPS 里没有的东西：自动当成屋里的物件
var _extra_props := {}


func _make_house_objects() -> void:
	for k in house.get("objects", {}):
		var id := str(k)
		if props.has(id) or id == "steam":
			continue
		_extra_props[id] = {"tex": "room_" + id + ".png" if ResourceLoader.exists(ART + "room_" + id + ".png") else id + ".png",
			"room": "treehouse", "at": 240, "size": [10, 10], "color": "#6a5e4c"}
		_make_prop(id)


func _base_cfg(id: String) -> Dictionary:
	if PROPS.has(id):
		return (PROPS[id] as Dictionary).duplicate(true)
	return (_extra_props.get(id, {}) as Dictionary).duplicate(true)


## 剧本的物件 id：room_<名字> 也认
func prop_id(id: String) -> String:
	if props.has(id):
		return id
	if props.has(id.trim_prefix("room_")):
		return id.trim_prefix("room_")
	return id


# ======================================================================= 树冠缺口（单独一屏）+ 画上的弧线
var treeline: Dictionary = {}           # treeline_view.json（空 = 缺图：treeline_match / 看缺口都跳过）
var _tv_layer: CanvasLayer              # 那一屏：世界（含 Front）之上，暗角 / 界面之下
var _tv_group: CanvasGroup              # 四层画成一张再整体淡入淡出（不会一层层透出底下的森林）
var _tv_sprites := {}                   # 层名 → Sprite2D
var _tv_t := 0.0                        # 这一屏出来了几秒（漂移用）
var _arc: Sprite2D


func _load_treeline() -> void:
	if not FileAccess.file_exists(ART + "treeline_view.json"):
		return
	var j = JSON.parse_string(FileAccess.get_file_as_string(ART + "treeline_view.json"))
	if not j is Dictionary or (j.get("layers", []) as Array).is_empty():
		return
	for k in j["layers"]:
		if not ResourceLoader.exists(ART + "treeline_view_%s.png" % k):
			return
	treeline = j


func has_treeline_view() -> bool:
	return not treeline.is_empty()


func treeline_view_shown() -> bool:
	return _tv_layer != null and _tv_layer.visible


func _build_treeline_view() -> void:
	if _tv_layer != null:
		return
	_tv_layer = CanvasLayer.new()
	_tv_layer.name = "TreelineView"
	_tv_layer.layer = 9
	_tv_layer.visible = false
	level.add_child(_tv_layer)
	_tv_group = CanvasGroup.new()
	_tv_group.fit_margin = 0.0
	_tv_group.clear_margin = 0.0
	_tv_layer.add_child(_tv_group)
	for k in treeline["layers"]:
		var s := Sprite2D.new()
		s.name = "View_" + str(k)
		s.texture = load(ART + "treeline_view_%s.png" % k)
		s.centered = false
		_tv_group.add_child(s)
		_tv_sprites[str(k)] = s


## 各层左上角在 (-drift × t, 0)，按整像素走；漂到图的右边缘贴着屏幕右边就停
func _place_treeline_view() -> void:
	var drift: Dictionary = treeline.get("drift", {})
	for k in _tv_sprites:
		var s: Sprite2D = _tv_sprites[k]
		var room := maxf(0.0, s.texture.get_width() - 480.0)
		s.position = Vector2(-roundf(minf(float(drift.get(k, 0.0)) * _tv_t, room)), 0.0)


## 淡入那一屏（sec 秒，淡完返回）；缺图直接返回
func treeline_view_in(sec := 0.8) -> void:
	if treeline.is_empty():
		return
	_build_treeline_view()
	_tv_t = 0.0
	_place_treeline_view()
	if _arc != null:
		_arc.visible = false
	_tv_group.self_modulate.a = 0.0
	_tv_layer.visible = true
	if level.has_method("hud_fade"):
		level.hud_fade(true, sec)              # 左上角目标 / 燃料、右上角背包跟着淡出
	var tw := create_tween()
	tw.tween_property(_tv_group, "self_modulate:a", 1.0, sec).set_trans(Tween.TRANS_SINE)
	await tw.finished


## 淡出回到森林
func treeline_view_out(sec := 0.8) -> void:
	if not treeline_view_shown():
		return
	if level.has_method("hud_fade"):
		level.hud_fade(false, sec)
	var tw := create_tween()
	tw.tween_property(_tv_group, "self_modulate:a", 0.0, sec).set_trans(Tween.TRANS_SINE)
	await tw.finished
	_tv_layer.visible = false
	if _arc != null:
		_arc.visible = false


## 画上的弧线叠到凹口上：淡入、停 hold 秒、淡出（返回总时长；那一屏没出来 / 缺图返回 0）。
## 弧线是弧所在那一层（arc_layer = main）的子节点，跟着它一起漂，任何时候都和凹口对齐。
func match_arc(hold := 1.6) -> float:
	if not treeline_view_shown() or not ResourceLoader.exists(ART + "drawing_arc.png"):
		return 0.0
	var aj = {}
	if FileAccess.file_exists(ART + "drawing_arc.json"):
		aj = JSON.parse_string(FileAccess.get_file_as_string(ART + "drawing_arc.json"))
	if not aj is Dictionary:
		aj = {}
	var host: Sprite2D = _tv_sprites.get(str(treeline.get("arc_layer", "main")), null)
	if host == null:
		return 0.0
	var k := float(aj.get("scale_to_treeline", 3))
	var a_left := _vec(aj.get("arc_end_left", [0, 0]))
	var t_left := _vec(aj.get("treeline_arc_end_left", treeline.get("arc_end_left", [0, 0])))
	if _arc == null:
		_arc = Sprite2D.new()
		_arc.name = "DrawingArc"
		_arc.texture = load(ART + "drawing_arc.png")
		_arc.centered = false
	if _arc.get_parent() != host:
		if _arc.get_parent() != null:
			_arc.get_parent().remove_child(_arc)
		host.add_child(_arc)
	_arc.scale = Vector2(k, k)
	_arc.position = (t_left - a_left * k).round()   # 两条弧的左端对上（图内坐标）
	_arc.modulate.a = 0.0
	_arc.visible = true
	var tw := create_tween()
	tw.tween_property(_arc, "modulate:a", 0.8, 0.8)
	tw.tween_interval(hold)
	tw.tween_property(_arc, "modulate:a", 0.0, 0.8)
	tw.tween_callback(func(): _arc.visible = false)
	return 0.8 + hold + 0.8


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
	if x < area_split():
		if x > ho + 20.0:
			# 塌陷口后面的林间空地：雾慢慢散开一点（空地）
			var g := mx("glade_rock") if markers.has("glade_rock") else ho + 180.0
			return maxf(clampf(1.0 - 0.6 * (x - ho) / maxf(1.0, g - ho), 0.4, 1.0), _edge_fog(x))
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


# ======================================================================= 远处有东西走过（elephant_call）
const SWAY_LAYER := "Far"           # 在哪一层的树冠上晃（远景）
const SWAY_Y := 60.0                # 树冠下沿那一带（和雾交界、看得出晃）
const SWAY_H := 70.0
const SWAY_COL := 4                 # 一次晃几列像素
const SWAY_EACH := 0.6              # 每一列晃多久
var _sway_t := -1.0
var _sway_dur := 3.0
var _sway_dir := 1
var _sway_x0 := 0.0
var _sway_x1 := 480.0
var _sway_node: Node2D


## 一排树冠从一侧到另一侧依次轻晃（像有很大的东西在雾后走过，不露面）。dir = 1 从左到右
func sway_canopy(dir := 1, dur := 3.0) -> void:
	var layer: Node2D = level.get_node(SWAY_LAYER)
	var spr: Sprite2D = layer.get_node("Sprite")
	if _sway_node == null:
		_sway_node = Node2D.new()
		_sway_node.name = "Sway"
		layer.add_child(_sway_node)
		_sway_node.draw.connect(_draw_sway)
	var inv := spr.get_global_transform_with_canvas().affine_inverse()
	_sway_x0 = (inv * Vector2(0, 0)).x
	_sway_x1 = (inv * Vector2(480, 0)).x
	_sway_t = 0.0
	_sway_dur = dur
	_sway_dir = dir


func swaying() -> bool:
	return _sway_t >= 0.0


func _draw_sway() -> void:
	if _sway_t < 0.0:
		return
	var spr: Sprite2D = level.get_node(SWAY_LAYER).get_node("Sprite")
	var tex := spr.texture
	var tw := float(tex.get_width())
	var span := _sway_x1 - _sway_x0
	var front := _sway_t / _sway_dur
	var offs := [1, 0, -1, 0]
	for col in range(0, int(span), SWAY_COL):
		var u := float(col) / span
		if _sway_dir < 0:
			u = 1.0 - u
		var age := (front - u) * _sway_dur
		if age < 0.0 or age > SWAY_EACH:
			continue
		var off: int = offs[int(age / (SWAY_EACH / 4.0)) % 4]
		if off == 0:
			continue
		var lx := _sway_x0 + col
		var tx := fposmod(lx, tw)
		_sway_node.draw_texture_rect_region(tex, Rect2(lx + off, SWAY_Y, SWAY_COL, SWAY_H), Rect2(tx, SWAY_Y, SWAY_COL, SWAY_H))


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
	if _lit_t > 0.0:
		a = maxf(a, 0.4 * clampf(_lit_t / 0.6, 0.0, 1.0))
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
			if c.has("anim_seq"):
				var seq: Array = c["anim_seq"]
				var tm := fmod(_anim_t * 1000.0, float(c["anim"]))
				var fi := 0
				while fi < seq.size() - 1 and tm >= float(seq[fi]):
					tm -= float(seq[fi])
					fi += 1
				s.frame = fi % s.hframes
			else:
				s.frame = int(_anim_t * 1000.0 / float(c["anim"])) % s.hframes
	_update_cloth()
	if treeline_view_shown():
		_tv_t += delta
		_place_treeline_view()
	if _sway_t >= 0.0:
		_sway_t += delta
		if _sway_t > _sway_dur + SWAY_EACH:
			_sway_t = -1.0
		_sway_node.queue_redraw()
	var want := fog_at(cam_center.x)
	if _lit_t > 0.0:
		_lit_t -= delta
		want *= 0.55                         # 被照亮：雾淡一下
	fog_k = move_toward(fog_k, want, delta * 0.5)
	if absf(want - fog_k) < 0.002:
		fog_k = want
	var off := not fog_enabled or room == "cockpit"     # 驾驶舱里没有雾
	if cockpit != null:
		cockpit.update(delta)
	var mb: ShaderMaterial = _fog_back.get_meta("mat")
	mb.set_shader_parameter("density", FOG_BACK_BASE + (FOG_BACK_A - FOG_BACK_BASE) * fog_k)
	mb.set_shader_parameter("fill", 0.8 * fog_k * fog_k)
	var mf: ShaderMaterial = _fog_front.get_meta("mat")
	mf.set_shader_parameter("density", FOG_FRONT_BASE + (FOG_FRONT_A - FOG_FRONT_BASE) * fog_k)
	_fog_back.visible = not off
	_fog_front.visible = not off


# ======================================================================= 驾驶舱（room = cockpit）
## 剧本 rooms 里有 cockpit 时 story_runner 调：建驾驶舱（scripts/cockpit_room.gd），它的 markers 填进来（剧本里写 0 的按美术的坐标；
## 非 0 的当成驾驶舱这一屏里的 x），hotspot 的点击框用物件的矩形。
func add_cockpit() -> void:
	if cockpit != null:
		return
	cockpit = (load("res://scripts/cockpit_room.gd") as GDScript).new()
	add_child(cockpit)
	cockpit.setup(level, self)
	for k in _script_markers:
		var n := str(k)
		if n.begins_with("cockpit_") and (_script_markers[k] is float or _script_markers[k] is int) and float(_script_markers[k]) != 0.0:
			cockpit.markers[n] = float(_script_markers[k])
	for n in cockpit.markers:
		markers[str(n)] = cockpit.mx(str(n))
		extra_rects[str(n)] = cockpit.prop_rect.bind(str(n))
	for id in StoryState.props:
		if str(id).begins_with("cockpit_"):
			cockpit.set_prop(str(id), str(StoryState.props[id]))


func in_cockpit() -> bool:
	return room == "cockpit"
