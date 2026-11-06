extends Control
## 母星闪回（11-02 作者定，一共 4 次；docs/闪回_实现说明.md）。剧本步骤：
##   {"do": "flashback", "id": 1..4, "place": "street" | "station"（两个一样，都是城市那条街）, "end": "black" | "door" | "white" | "still",
##    "lines": [{zh, en, added?}…], "fall": true（最后一句的字一个个掉没）, "hold": true}
##   {"do": "flashback_wake", "wait": false}
## story_runner.gd 的 _flashback 建它（自己一层 CanvasLayer，盖在黑幕上面、F8 面板下面）：await play(runner, st)。
##
## 四次一样的玩法（作者讨厌每章换玩法）。11-04 作者：「左侧的灰色我一直觉得没压迫感而且我看不到，所以能不能做成触手？
## 然后速度平滑的决定于主角的速度，就是永远在主角后面也就是屏幕右侧有一点，然后本来主角就在跑，而不是按D也可以跑，
## 但是触手接近的速度更快，只有狂按E才能往前冲，然后冲的时加点特效」：
##   1. 进（11-05 作者：「突然到闪回有点软绵绵的……像关门或者电影 cut 一下就很快的逐渐黑下去，然后音乐响起」）：
##      原场景 BLACK_IN 秒缓出地压黑（不是一帧切；四次一样，第一次也不再是浅灰绿的雾）→ 黑到底那一下紧张的音乐直接从目标音量起
##      （HIT 秒防爆音）+ 第一下心跳 → 黑里停 BLACK_HOLD 秒 → 雨夜的街从黑里出来（STREET_IN 秒，糊 → 清楚），雨跟着街淡进来
##      （flashback_screen / flashback_view 两个 shader）。
##   2. 触手涌进来（前三次）：画面一清楚，左边一团黑里伸出几条触手（_draw_tentacles，程序画：粗到细的一节节、硬像素边、
##      近黑带一道冷光，沿正弦扭、尖上卷起来抓），SURGE 秒先快后慢涌到晨身后 GAP0，把她身后的人吞掉；
##      左边照旧压暗、去色（view shader 的那一片，现在是暗角）。晨回头看一眼（只是翻一下，GLANCE），这一秒多不让跑（_lock）。
##   3. 跑：晨自己一直往右跑（现成的跑步动作，100ms 一帧；闪回里比平时快 RUN_BONUS）。镜头把她放在屏幕中间偏右（CHEN_SX），
##      左边一直看得见触手。触手的速度跟着她平滑地走：基础 = 她平时的速度（实测 _vc），再快一点（CREEP，慢慢加），所以一直在慢慢逼近；
##      她冲远了（> GAP_SOFT）触手也平滑地追上来，永远在画面里。只有狂按 E 才往前冲：每按一下多一股速度（PUSH，很快退掉），
##      连着按就跑得掉。鼠标 / 触屏点按也算按 E；→ / D 不管用（本来就在跑）。
##      每冲一下：横的速度线、脚下一团扬尘、几张晨当前那帧的残影（复制她现在的图，不画新的晨）、镜头往前一推（跟得慢一点 + _kick）。
##      对话那一带上面「狂按 E 冲刺」+ 一个 E 键帽，一跳一跳；屏幕中间一行一行出晨的独白；
##      心跳按触手离她多近变快变响，底下一层紧张的音乐。
##      调的数（按这里的公式模拟过，见 docs/闪回_实现说明.md）：一下不按约 13 秒被抓；一秒半下约 18 秒；一秒一下以上跑得掉。
##   4. 结束：触手追上她 → 一把卷住、屏幕变黑。跑满 RUN 秒没被追上 → 成就（flag fb_outran，名字在 data/achievements.json），触手缩回去，
##      再按这一次的 end：black 晨慢下来停住、慢慢黑掉；door 前面那列车慢下来，晨跑到车门跟前门关上，车开走，再黑；
##      white 晨慢下来停住；字掉完，整屏像闪光灯一样一下子过曝（先轻轻一闪、再 0.15 秒缓出冲到满白），白里透一点过曝的人影残像，
##      残像慢慢淡掉，再从白里醒（11-05 作者定：记忆是空白的；和进闪回的 cut 同一套手感——快、硬、干净，没有慢慢爬的边）。
##      第四次（end: still）：晨不自己跑（按 E 才跑一下），触手慢慢挪过来；站着不动 STILL 秒（或者触手挪到她身边），
##      触手在她身边停一会儿、绕开她从身边过去（不碰她：每条只走她头上或脚下一边，按自己多粗让开；她身上不被压暗），
##      什么也没发生，成就（flag fb_stood_still），慢慢暗下去。
##      她跑起来，触手就和前三次一样追；一直跑满 RUN 秒没被追上，和第一次一样慢下来、黑掉。
##   5. 醒：hold = 停在黑 / 白上，等剧本自己放好原场景、叫醒她的声音，再 flashback_wake：眼皮从上下慢慢睁开
##      （睁一半、又合一点、再睁开），糊的画面一起变清楚。没写 hold 就自己接着醒。
##   没有失败、不会卡关：每一段都有时长上限，追上了也接着播剧情。一次 20～35 秒。
## 右边一直有个要追的东西：第一次 大象的画（art/forest_story/icon_drawing.png 当纸）被风吹走，在晨前面一点飘，结束时落回她手里
##   （接剧本里的地图翻面）；第二次 一列要开走的车（art/flashback/train_car.png，tools/flashback_train_art.py；尾门开着、里面亮），
##   一直在前面一点，她冲近了车就快一点；第三次 远处一点暖光（白漫过来时跟着淡掉）。第四次没有。
## 母星只用作者已有的场景（不新画背景、不改作者图层的颜色）：四次都是同一条街 scenes/city_test.tscn，整个实例化进一个 SubViewport，
##   去掉它的根脚本（city_test.gd 读命令行、空格，这里不要），镜头、湿街面自己管；晨那条街的中排人流改成往左（三排都逆着晨）。
##   触手、画、列车、暖光、扬尘都插在街的节点之间（湿地面前面），所以都照进倒影。
## 声音：heartbeat（一下「咚咚」0.77 秒，同一个播放器按快慢重放，HEART_DB 跟着触手多近变响）、flashback_tense（24 秒，
##   导入没开循环：放完自己从头再放，音量 TENSE_DB 跟着触手多近平滑变）、train_door_close；缺的静默跳过，记进
##   runner.missing_sfx（--story_check 列出来）。都走 Music 总线；闪回期间 SFX 总线（原场景的环境声）压低 DUCK dB，醒的时候放回去。
## 自动玩：时长 × AUTO_K；连按 E（一秒五下，跑掉、拿成就那条路）；第四次站着不动（停下来那条路）。
##   --fb_caught：自动玩一下也不按（被抓那条路，按真实时长）；--fb_rate=N：自动玩一秒按 N 下（按真实时长，调手感用）；
##   --fb_debug：每秒打一行触手离她多远；--fb_full：自动玩也按真实时长。跳节拍（ff）时 runner 直接跳过，不建它。
## F8 传送页每章下面有「闪回」按钮（dev_panel.gd，表在 story_runner.gd 的 FLASHBACK_DEV）。

const CITY_SCENE := "res://scenes/city_test.tscn"
const ENV_LIGHT := preload("res://scripts/env_light.gd")
const SCREEN_SH := preload("res://scripts/flashback_screen.gdshader")
const VIEW_SH := preload("res://scripts/flashback_view.gdshader")
const ACH_PATH := "res://data/achievements.json"
const PAPER_TEX := preload("res://art/forest_story/icon_drawing.png")
const TRAIN_CAR := preload("res://art/flashback/train_car.png")
const TRAIN_DOOR_L := preload("res://art/flashback/train_door_l.png")
const TRAIN_DOOR_R := preload("res://art/flashback/train_door_r.png")
const SOUNDS := ["heartbeat", "flashback_tense", "train_door_close"]
const GROUND := 228.0
const CHEN_SX := 300.0          # 晨在屏幕上的 x：中间偏右一点，左边一直看得见触手
const FOLLOW := 8.0             # 镜头跟得多紧（冲的时候跟慢一点，就是往前一推）
const BLACK_IN := 0.2           # 原场景压黑（缓出：一开始就快）
const BLACK_HOLD := 0.3         # 黑里停一下：音乐在这儿响起
const STREET_IN := 1.0          # 雨街从黑里出来（之后再 1.2 秒糊退干净）
const HIT := 0.05               # 紧张的音乐起音（直接到目标音量，只防爆音）
const DUCK_SEC := 0.25          # 原场景的环境声跟着压黑一起压低
const RUN := 22.0               # 跑满这么久还没被追上 = 跑掉了
const RUN_BONUS := 50.0         # 闪回里晨平时就跑得比平时快这么多（chen.gd 的 150 + 50）
const V_BASE := 200.0           # 她平时大约多快（150 + RUN_BONUS；列车按它跟着跑，触手按实测的 _vc）
const GAP0 := 200.0             # 涌完以后触手尖在晨身后多远（屏幕 x 100）
const GAP_FROM := 420.0         # 涌进来之前（画面外）
const GAP_SOFT := 250.0         # 她冲得再远，触手也平滑地追到这么近（一直在画面里）
const CREEP := Vector2(9.0, 21.0)   # 触手比她快多少（像素 / 秒）：从慢到快
const CREEP_RAMP := 13.0        # 几秒加到最快
const STILL_CREEP := 20.0       # 第四次她站着：触手慢慢挪
const PUSH := 60.0              # 按一下 E 多快多少（像素 / 秒）
const PUSH_MAX := 160.0
const PUSH_DECAY := 5.0         # 多出来的速度退得多快（1/秒）
const E_RUN := 0.45             # 第四次：按一下 E 跑多久
const SURGE := 1.1              # 涌进来要多久（先快后慢）
const GLANCE_AT := 0.35         # 涌进来多久以后晨回头
const GLANCE := 0.75            # 回头看多久（之后才放开、出提示）
const LINE_FIRST := 1.2         # 开跑后第几秒出第一句独白
const LINE_EVERY := 4.5
const LINE_ONE := 2.0           # 只有一句的：第几秒出
const FALL_AFTER := 2.5         # 要掉字的那句出来多久以后开始掉
const FALL_EVERY := 0.32
const STILL := 6.0              # 第四次：站着不动这么久 = 停下来
const HOVER := 1.6              # 第四次停下来：触手在她身边停多久
const PASS_V := 130.0           # 然后从她身边过去的速度
const HEART_BPM := Vector2(66.0, 138.0)
const HEART_DB := Vector2(-20.0, -9.0)    # 心跳：触手远 → 近（heartbeat.mp3 峰值接近 0 dB，比音乐响，压低一点）
const TENSE_DB := Vector2(-22.0, -10.0)   # 紧张的音乐：触手远 → 近
const DUCK := 14.0
const AUTO_K := 0.4
const DARK_C := Color(0.02, 0.03, 0.03)
const SHADE_C := Color(0.02, 0.025, 0.03)  # 左边压暗的那一片（触手从这团黑里伸出来）
const WHITE_C := Color(0.93, 0.95, 0.94)
const BLACK_C := Color(0.0, 0.0, 0.0)
# 触手（_draw_tentacles）：近黑、上沿一道冷光、受光边、下沿更黑
const T_INK := Color8(3, 4, 6)
const T_BODY := Color8(9, 12, 14)
const T_SHEEN := Color8(40, 52, 58)
const T_RIM := Color8(104, 124, 130)
const TN := 26                  # 每条几节
const TENT := [                 # [根的 y（世界）, 长度系数, 起始角, 根的半粗, 相位, 尖卷的方向和多少]
	[110.0, 0.78, 0.30, 12.0, 5.6, 2.8],
	[144.0, 0.97, -0.02, 17.0, 0.0, 2.3],
	[180.0, 1.06, 0.06, 22.0, 1.7, -2.5],
	[216.0, 1.00, -0.04, 19.0, 3.1, 2.6],
	[246.0, 1.08, -0.10, 24.0, 4.4, -2.2],
	[272.0, 0.92, -0.16, 16.0, 2.3, 2.5],
	[294.0, 0.70, -0.30, 12.0, 0.9, -2.6],
]
const BODY_HALF := Vector2(12.0, 24.0)   # 晨身子的半宽、半高（世界像素，中心在脚上面 24）：第四次触手绕开的就是这一块
const AVOID_FALL := 26.0        # 绕开那段两边多宽里平滑地回到原来的路上
const T_ROOT := -46.0           # 根在屏幕左边外面多远
# 第一次：画
const PAPER_LEAD := 95.0        # 在晨前面多远飘（前后再晃 ±18）
const PAPER_Y := 190.0          # 飘的高度（脚底 228，晨 60 高：胸口到头顶那么高）
const PAPER_HAND := Vector2(9.0, 201.0)   # 晨手的位置（相对她的 x、世界 y）：开头从这儿被吹走，结束落回这儿
# 第二次：列车（art/flashback/train_car.png 400×132；安全线在第 127、128 行 = 晨脚底）
const TRAIN_Y := 100.0
const TRAIN_W := 400.0
const TRAIN_LINK := 6.0         # 两节车厢中间的折棚
const DOOR_POS := Vector2(24, 22)   # 尾门门洞在车厢图里的左上角；36×96，门扇各 18
const DOOR_HALF := 18.0
const DOOR_H := 96.0
const TRAIN_GAP := 160.0        # 跑的时候尾门在晨前面多远（屏幕 x 460）
const DOOR_CLOSE_AT := 80.0     # 结束时晨离门这么远，门开始关
const DOOR_STOP := 26.0         # 晨最多跑到离门这么近
const LAMP_C := Color(0.95, 0.62, 0.3)
const SPILL_C := Color(0.62, 0.46, 0.28)
# 第三次：暖光
const LIGHT_SX := 436.0
const LIGHT_Y := 197.0
const LIGHT_C := Color(0.98, 0.8, 0.52)
const WHITE_STOP := 0.6         # 跑掉以后她再跑多久就慢下来
const FLASH := [[0.6, 0.04], [0.3, 0.07], [1.0, 0.15]]   # 闪白：[到多少, 用几秒]——先轻轻一闪、落一点，再缓出冲到满白
const FLASH_HOLD := 0.9         # 满白以后残像停多久
const GHOST_OUT := 1.4          # 残像淡掉要多久
# 提示：「狂按 E 冲刺」+ E 键帽，在对话那一带（story_dialogue.gd BAND_TOP 184）上面
const PROMPT_Y := 164.0
const KEY_C := Color(0.82, 0.86, 0.84)
const KEY_FACE := Color(0.1, 0.12, 0.12)
const KEY_SIDE := Color(0.38, 0.42, 0.42)
const SPEED_C := Color(0.72, 0.8, 0.8)
const DUST_C := Color(0.4, 0.44, 0.44)
const GHOST_C := Color(0.6, 0.78, 0.82)
const TXT := {
	"hint": ["Mash E to dash", "狂按 E 冲刺"],
	"ach": ["Achievement", "成就"],
}

var runner: Node
var st := {}
var id := 1
var place := "street"
var end_kind := "black"
var result := ""                  # caught / escaped / still
var _lines: Array = []
var _auto := false
var _auto_caught := false
var _k := 1.0
var _vp: SubViewport
var _world: Node2D
var _chen: Node2D
var _spr: AnimatedSprite2D
var _cam: Camera2D
var _wet: ShaderMaterial
var _shafts: Node
var _view: TextureRect
var _vmat: ShaderMaterial
var _screen: ColorRect
var _smat: ShaderMaterial
var _veil: ColorRect
var _line_box: Control
var _line_rows: Array = []        # 每句一行：[Label…]（一个字一个 Label，要掉字）
var _line_t: Array = []           # 每句什么时候出（开跑后的秒数）
var _shown := 0
var _fall_i := -1                 # 掉到第几个字（-1 = 还没开始掉）
var _fall_t := 0.0
var _flush_next := 0.0
var _toast: Label
var _prompt: Control
var _key: Control
var _prompt_a := 0.0
var _prompt_t := -999.0
var _key_down := 0.0
var _music: AudioStreamPlayer
var _rain: AudioStreamPlayer      # 城市的雨，垫在紧张的音乐底下
var _heart_p: AudioStreamPlayer
var _bus := "Master"
var _sfx_db := 0.0
var _ducked := false
var _t := 0.0
var _run_t := 0.0
var _running := false
var _lock := false                # 涌进来、回头看的这一秒多：不让跑
var _surge := false               # 触手正在涌进来（tween 管它的位置）
var _front := -9999.0             # 触手尖（最前面那条）的世界 x
var _tv := V_BASE                 # 触手现在的速度（平滑地追目标速度）
var _vc := V_BASE                 # 晨平时的速度（实测：她这一帧挪了多少，减掉冲出去的那股，平滑过）
var _last_x := NAN
var _tail := -99999.0             # 第四次过去时触手的尾巴（世界 x），压暗那一片的后沿
var _tmode := ""                  # "" 追 / grab 卷住 / back 缩回去 / hover 停在她身边 / pass 从身边过去
var _tents: Node2D
var _tent_a := 1.0
var _grab := 0.0                  # 卷住她的程度（0..1）
var _boost := 0.0
var _extra := 0.0
var _e_t := 0.0
var _presses := 0
var _auto_press_t := 0.0
var _auto_every := 0.2            # 自动玩隔多久按一下 E（--fb_rate=每秒几下）
var _still_t := 0.0
var _ran := false
var _run_now := false
var _chase_t := 0.0
var _heart_t := 0.0
var _bpm := 0.0
var _heart_db := HEART_DB.x
var _end_color := BLACK_C
var _look := 240.0 - CHEN_SX      # 镜头中心 = 晨 + _look
var _avoid_k := 0.0
var _tside: Array = []            # 第四次绕开她：每条触手走上面（-1）还是下面（1），第一次绕的时候定
var _kick := 0.0                  # 冲的时候镜头多往前推一点（平滑退回去）
# 冲刺特效
var _fx: Control                  # 速度线（屏幕坐标，盖在画面上）
var _lines_fx: Array = []         # [{p, len, v, life, max}]
var _dust: Node2D                 # 扬尘（世界坐标，照进倒影）
var _dust_p: Array = []           # [{p, v, life, max, s}]
# 第一次：画
var _paper: Sprite2D
var _paper_off := Vector2.ZERO    # 相对晨的 x、世界 y（平滑跟着目标走）
var _paper_mode := ""             # "" 还在手里（藏着）/ fly 飘 / catch 落回手里 / done
# 第二次：列车
var _train: Node2D
var _train_wx := 0.0
var _train_v := V_BASE
var _train_mode := ""             # "" 跟着跑 / stop 停下来等 / go 开走
var _door_l: Sprite2D
var _door_r: Sprite2D
var _door_k := 0.0                # 尾门关了多少（0 开着，1 关上）
var _lamp := 0.0
# 第三次：暖光
var _light: Node2D
var _light_a := 0.0


func play(r: Node, step: Dictionary) -> void:
	runner = r
	st = step
	id = int(st.get("id", 1))
	place = str(st.get("place", "street"))
	end_kind = str(st.get("end", "black"))
	_lines = st.get("lines", [])
	var args := OS.get_cmdline_user_args()
	_auto = r.auto != ""
	_auto_caught = "--fb_caught" in args
	for a in args:
		if a.begins_with("--fb_rate="):
			_auto_every = 1.0 / maxf(0.1, float(a.trim_prefix("--fb_rate=")))
	_k = AUTO_K if _auto and not "--fb_full" in args and not _auto_caught else 1.0
	for a in args:
		if a.begins_with("--fb_rate="):
			_k = 1.0
	_bus = "Music" if AudioServer.get_bus_index("Music") >= 0 else "Master"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_build()
	_duck(true)
	await _intro()
	await _run()
	await _ending()
	print("FLASHBACK %d %s: result=%s run=%.1fs presses=%d end=%s" % [id, place, result, _run_t, _presses, end_kind])
	if not bool(st.get("hold", false)):
		await wake()


# ======================================================================= 搭画面
func _build() -> void:
	_vp = SubViewport.new()
	_vp.size = Vector2i(480, 270)
	_vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_vp)
	_build_city()
	_chen.input_enabled = false
	_chen.ground_fn = func(_x: float) -> float: return GROUND
	_cam.position = Vector2(_chen.position.x + _look, _cam.position.y)
	_cam.make_current()
	_front = _chen.position.x - (GAP0 if id == 4 else GAP_FROM)
	if id == 4:
		_tv = STILL_CREEP
	# 母星那一屏
	_view = TextureRect.new()
	_view.texture = _vp.get_texture()
	_view.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_view.size = Vector2(480, 270)
	_view.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_vmat = ShaderMaterial.new()
	_vmat.shader = VIEW_SH
	_vmat.set_shader_parameter("grey_c", SHADE_C)
	_vmat.set_shader_parameter("grey_a", 0.7)
	_vmat.set_shader_parameter("white_c", WHITE_C)
	_view.material = _vmat
	_view.visible = false
	add_child(_view)
	# 读屏幕的那一层（进：糊掉原场景；醒：眼皮）。画在母星那一屏下面：进的时候母星在它上面淡进来
	_screen = ColorRect.new()
	_screen.size = Vector2(480, 270)
	_screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_smat = ShaderMaterial.new()
	_smat.shader = SCREEN_SH
	_screen.material = _smat
	_screen.visible = false
	add_child(_screen)
	move_child(_screen, _view.get_index())
	_fx = Control.new()
	_fx.size = Vector2(480, 270)
	_fx.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fx.draw.connect(_draw_speed_lines)
	add_child(_fx)
	_line_box = Control.new()
	_line_box.size = Vector2(480, 270)
	_line_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_line_box)
	_build_prompt()
	_veil = ColorRect.new()
	_veil.size = Vector2(480, 270)
	_veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_veil.color = Color(BLACK_C, 0.0)
	add_child(_veil)
	_toast = _label("", UITheme.WARM)
	_toast.position = Vector2(0, 16)
	_toast.modulate.a = 0.0
	add_child(_toast)
	_build_lines()


func _build_city() -> void:
	var root: Node = (load(CITY_SCENE) as PackedScene).instantiate()
	root.set_script(null)                       # city_test.gd 读命令行（--shot= 会存图退出）、空格：这里不要，镜头自己管
	var mid := root.get_node_or_null("Main/CrowdMid")
	if mid != null:
		mid.set("direction", -1)                # 晨那条街三排人流都往左：逆着往右跑的晨
	_world = root
	_vp.add_child(root)
	_chen = root.get_node("Chen")
	_spr = _chen.get_node_or_null("Sprite") as AnimatedSprite2D
	_cam = root.get_node("Camera")
	_shafts = root.get_node_or_null("Shafts")
	var wr := root.get_node_or_null("Wet/Rect")
	if wr != null:
		_wet = (wr as CanvasItem).material as ShaderMaterial
	var sh: Node = _shafts
	_chen.set_env("city", func(c): return ENV_LIGHT.polygon_shafts(c, sh))
	# 插在街的节点之间：车在晨后面（近排人流在车前面走过）；画、暖光、扬尘在晨前面；触手在近排人流前面、湿地面前面
	if end_kind == "door":
		_build_train()
	if end_kind == "white":
		_light = _node2d("FlashbackLight", _draw_light, true)
		_world.move_child(_light, _chen.get_index() + 1)
	if id == 1:
		_paper = Sprite2D.new()
		_paper.name = "FlashbackPaper"
		_paper.texture = PAPER_TEX
		_paper.visible = false
		_world.add_child(_paper)
		_world.move_child(_paper, _chen.get_index() + 1)
	_dust = _node2d("FlashbackDust", _draw_dust)
	_world.move_child(_dust, _chen.get_index() + 1)
	_tents = _node2d("FlashbackTentacles", _draw_tentacles)
	var wet_n := _world.get_node_or_null("Wet")
	if wet_n != null:
		_world.move_child(_tents, wet_n.get_index())


func _node2d(nm: String, fn: Callable, add := false) -> Node2D:
	var n := Node2D.new()
	n.name = nm
	if add:
		var m := CanvasItemMaterial.new()
		m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		n.material = m
	n.draw.connect(fn)
	_world.add_child(n)
	return n


## 第二次：两节车厢（尾门开着、里面亮；后面那节的门都关着），中间一段折棚；门扇单独两张图，关门时从两边滑出来
func _build_train() -> void:
	_train = Node2D.new()
	_train.name = "FlashbackTrain"
	_world.add_child(_train)
	_world.move_child(_train, _chen.get_index())
	for i in 2:
		var c := Sprite2D.new()
		c.texture = TRAIN_CAR
		c.centered = false
		c.position = Vector2(float(i) * (TRAIN_W + TRAIN_LINK), 0)
		_train.add_child(c)
		if i == 1:                              # 后面那节的尾门关着
			for d in [[TRAIN_DOOR_L, 0.0], [TRAIN_DOOR_R, DOOR_HALF]]:
				var s := Sprite2D.new()
				s.texture = d[0]
				s.centered = false
				s.position = DOOR_POS + Vector2(float(d[1]), 0)
				c.add_child(s)
	_door_l = _leaf(TRAIN_DOOR_L)
	_door_r = _leaf(TRAIN_DOOR_R)
	var deco := Node2D.new()                    # 折棚、门楣上的灯、门口地上的光
	deco.name = "Deco"
	deco.draw.connect(_draw_train_deco.bind(deco))
	_train.add_child(deco)
	_train.visible = false
	_set_door(0.0)


func _leaf(tex: Texture2D) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = tex
	s.centered = false
	s.region_enabled = true
	_train.add_child(s)
	return s


## 独白：每句一行，一个字一个 Label（第三次要一个个掉）；屏幕中间偏上，几句一起居中
func _build_lines() -> void:
	var font := UITheme.font()
	var n := _lines.size()
	var y0 := 92.0 - float(n - 1) * 10.0
	for i in n:
		var l: Dictionary = _lines[i]
		var text: String = runner.txt(l)
		var col: Color = runner.dlg.ADDED_C if bool(l.get("added", false)) and runner.mark_added else Color("#d8e2dc")
		var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
		var x := roundf(240.0 - w / 2.0)
		var row: Array = []
		for ch in text:
			var c := Label.new()
			c.text = ch
			c.add_theme_font_override("font", font)
			c.add_theme_font_size_override("font_size", 14)
			c.add_theme_color_override("font_color", col)
			c.add_theme_color_override("font_shadow_color", Color(0.0, 0.02, 0.02, 0.85))
			c.add_theme_constant_override("shadow_offset_x", 0)
			c.add_theme_constant_override("shadow_offset_y", 1)
			if end_kind == "white":                # 结尾一边黑一边白：一圈暗描边，两边都看得见（以前整行压暗，在黑的那边就看不见了）
				c.add_theme_color_override("font_outline_color", Color(0.02, 0.04, 0.04, 0.75))
				c.add_theme_constant_override("outline_size", 4)
			c.position = Vector2(x, roundf(y0 + float(i) * 20.0))
			c.mouse_filter = Control.MOUSE_FILTER_IGNORE
			c.modulate.a = 0.0
			_line_box.add_child(c)
			row.append(c)
			x += font.get_string_size(ch, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
		_line_rows.append(row)
		var every := minf(LINE_EVERY, (RUN - 6.0) / maxf(1.0, float(n - 1)))
		_line_t.append((LINE_ONE if n == 1 else LINE_FIRST + float(i) * every) * _k)


## 「狂按 E 冲刺」：左边一个 13×14 的 E 键帽（程序画），右边字；整组居中
func _build_prompt() -> void:
	_prompt = Control.new()
	_prompt.size = Vector2(480, 16)
	_prompt.position = Vector2(0, PROMPT_Y)
	_prompt.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_prompt.modulate.a = 0.0
	add_child(_prompt)
	var txt := _tx("hint")
	var w := UITheme.font().get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
	var x0 := roundf(240.0 - (13.0 + 5.0 + w) / 2.0)
	_key = Control.new()
	_key.size = Vector2(13, 15)
	_key.position = Vector2(x0, 1)
	_key.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_key.draw.connect(_draw_key)
	_prompt.add_child(_key)
	var l := Label.new()
	l.text = txt
	l.add_theme_font_override("font", UITheme.font())
	l.add_theme_font_size_override("font_size", 14)
	l.add_theme_color_override("font_color", UITheme.TEXT_DIM)
	l.add_theme_color_override("font_shadow_color", Color(0.0, 0.02, 0.02, 0.85))
	l.add_theme_constant_override("shadow_offset_x", 0)
	l.add_theme_constant_override("shadow_offset_y", 1)
	l.position = Vector2(x0 + 18.0, -1)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_prompt.add_child(l)


func _label(text: String, col: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", UITheme.font())
	l.add_theme_font_size_override("font_size", 14)
	l.add_theme_color_override("font_color", col)
	l.add_theme_color_override("font_shadow_color", Color(0.0, 0.02, 0.02, 0.85))
	l.add_theme_constant_override("shadow_offset_x", 0)
	l.add_theme_constant_override("shadow_offset_y", 1)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.size = Vector2(480, 16)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


static func _tx(k: String) -> String:
	var row: Array = TXT[k]
	return str(row[1] if I18n.is_zh() else row[0])


# ======================================================================= 进
func _intro() -> void:
	# 原场景很快地压黑：缓出（头几帧就暗下去一大截），带一点糊和去色，像门一关
	_screen.visible = true
	_smat.set_shader_parameter("veil", DARK_C)
	var d := BLACK_IN * _k
	var tw := create_tween().set_parallel().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_method(_sp.bind("veil_a"), 0.0, 1.0, d)
	tw.tween_method(_sp.bind("blur"), 0.0, 2.0, d)
	tw.tween_method(_sp.bind("desat"), 0.0, 0.6, d)
	tw.tween_method(_sp.bind("vig"), 0.0, 0.85, d)
	await tw.finished
	# 黑到底：音乐、心跳响起
	_music_hit()
	await _sleep(BLACK_HOLD)
	# 雨夜的街从黑里出来（糊的），雨跟着淡进来
	_vmat.set_shader_parameter("blur", 4.0)
	_view.modulate.a = 0.0
	_view.visible = true
	var tw2 := create_tween()
	tw2.tween_property(_view, "modulate:a", 1.0, STREET_IN * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tw2.finished
	_screen.visible = false
	# 最后那点糊一边退、触手一边涌进来（不等它全清楚：画面一出来两秒内就要看出为什么跑）
	create_tween().tween_method(_vp_blur, 4.0, 0.0, 1.2 * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)


func _sp(v: float, key: String) -> void:
	_smat.set_shader_parameter(key, v)


func _vp_blur(v: float) -> void:
	_vmat.set_shader_parameter("blur", v)


func _vp_param(v: float, key: String) -> void:
	_vmat.set_shader_parameter(key, v)


# ======================================================================= 跑
func _run() -> void:
	_running = true
	if id == 4:
		_prompt_on(0.6 * _k)
	else:
		_surge_in()
	runner._ui_shot("flashback%d" % id, 3.0 * _k)
	while _running:
		await StoryState.frame(get_tree())
		_run_step(get_process_delta_time())
	_lock = false
	_surge = false
	create_tween().tween_property(self, "_prompt_a", 0.0, 0.5)


## 开头：触手从左边那团黑里猛地涌进来，吞掉晨身后的人；晨回头看一眼；然后出提示、开跑，右边的目标动起来
func _surge_in() -> void:
	_surge = true
	_lock = true
	var tw := create_tween()
	tw.tween_property(self, "_front", _chen.position.x - GAP0, SURGE * _k).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_callback(func(): _surge = false)
	if _train != null:                          # 车一开始就在前面（门开着、里面亮）：要追的就是它
		_goal_train()
	await _sleep(GLANCE_AT)
	if not _running or not is_instance_valid(_chen):
		_lock = false
		return
	_chen._set_facing(-1)                       # 回头看（只是翻过去）
	await _sleep(GLANCE)
	if not is_instance_valid(_chen):
		return
	_chen._set_facing(1)
	_lock = false
	print("FLASHBACK_SURGE gap=%d t=%.1f" % [int(_chen.position.x - _front), _t])
	_goal_on()
	_prompt_on(0.0)


func _prompt_on(delay: float) -> void:
	create_tween().tween_property(self, "_prompt_a", 0.9, 0.6).set_delay(delay)
	_prompt_t = -delay


func _goal_train() -> void:
	_train_wx = roundf(_chen.position.x + TRAIN_GAP - DOOR_POS.x - DOOR_HALF)
	_train.position = Vector2(_train_wx, TRAIN_Y)
	_train_v = V_BASE
	_train.modulate.a = 0.0
	_train.visible = true
	create_tween().tween_property(_train, "modulate:a", 1.0, 1.0 * maxf(_k, 0.5)).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)


## 右边要追的东西出来：画从手里被吹走 / 远处的暖光淡出来（车在涌进来的时候就出来了）
func _goal_on() -> void:
	if _paper != null:
		_paper_off = PAPER_HAND
		_paper.position = Vector2(_chen.position.x + PAPER_HAND.x, PAPER_HAND.y)
		_paper.visible = true
		_paper_mode = "fly"
	if _light != null:
		create_tween().tween_property(self, "_light_a", 1.0, 1.2 * maxf(_k, 0.5)).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)


func _run_step(dt: float) -> void:
	_run_t += dt
	if _auto and not _lock and not _auto_caught and id != 4:
		_auto_press_t -= dt
		if _auto_press_t <= 0.0:
			_auto_press_t = _auto_every
			_press()
	_e_t = maxf(0.0, _e_t - dt)
	# 前三次她自己一直跑（涌进来、回头的那一下除外）；第四次按 E 才跑一下
	var run := (not _lock) if id != 4 else _e_t > 0.0
	_run_now = run
	_chen.auto_dir = 1.0 if run else 0.0
	_boost *= exp(-PUSH_DECAY * dt)
	var vel := float(_chen.get("_vel"))
	if run and vel > 1.0:
		_extra += (_boost + RUN_BONUS) * dt     # 闪回里本来就快 + 按 E 冲出去的那股：直接把晨往前挪（chen.gd 会从新位置接着跑）
		var px := floorf(_extra)
		if px >= 1.0:
			_chen.position.x += px
			_extra -= px
	if run:
		_ran = true
		_still_t = 0.0
	else:
		_still_t += dt
	if _ran:
		_chase_t += dt
	# 触手：基础速度跟着她平时的速度（实测，chen.gd 取整会让她比 150 + 50 快一点），再快一点（慢慢加）；
	# 她冲远了就平滑地追上来。第四次她站着，触手慢慢挪
	if run and vel >= 149.0 and not is_nan(_last_x) and dt > 0.0:   # 起步那 0.3 秒不算（不然触手开头会落回去）
		_vc = lerpf(_vc, maxf(0.0, (_chen.position.x - _last_x) / dt - _boost), 1.0 - exp(-4.0 * dt))
	_last_x = _chen.position.x
	var gap := _chen.position.x - _front
	var want := _vc + lerpf(CREEP.x, CREEP.y, smoothstep(0.0, CREEP_RAMP * _k, _chase_t)) + maxf(0.0, gap - GAP_SOFT) * 2.0
	if id == 4 and not run:
		want = STILL_CREEP
	_tv = lerpf(_tv, want, 1.0 - exp(-3.0 * dt))
	if not _surge and not _lock:
		_front += _tv * dt
	_train_step(dt)
	if "--fb_debug" in OS.get_cmdline_user_args() and int(_run_t * 60.0) % 60 == 0:
		print("FB_DBG t=%.1f gap=%.0f tv=%.0f vel=%.0f chen=%.0f front=%.0f lock=%s surge=%s" % [_run_t, gap, _tv, vel, _chen.position.x, _front, _lock, _surge])
	if id == 4 and not run and (_still_t >= STILL * _k or _front >= _chen.position.x - 30.0):
		result = "still"                        # 站够了，或者触手挪到她身边：从她身边过去，什么也没发生
		_running = false
	elif _front >= _chen.position.x - 4.0:
		result = "caught"
		_running = false
	elif _run_t >= RUN * _k:
		result = "escaped"
		_running = false


## 车：跑的时候尾门一直在她前面 TRAIN_GAP 左右（她冲近了车就快一点、慢下来车也慢一点，都是平滑的）
func _train_step(dt: float) -> void:
	if _train == null or not _train.visible:
		return
	var door := _train_wx + DOOR_POS.x + DOOR_HALF
	match _train_mode:
		"":
			var want := V_BASE + clampf((TRAIN_GAP - (door - _chen.position.x)) * 1.4, -60.0, 180.0)
			_train_v = lerpf(_train_v, want, 1.0 - exp(-2.5 * dt))
		"stop":
			_train_v = move_toward(_train_v, 0.0, 190.0 * dt)
		"go":
			_train_v = move_toward(_train_v, 340.0, 120.0 * dt)
	_train_wx += _train_v * dt
	_train.position = Vector2(roundf(_train_wx), TRAIN_Y)


func _press() -> void:
	if _lock or not _running:
		return
	_presses += 1
	_boost = minf(_boost + PUSH, PUSH_MAX)
	_e_t = E_RUN
	_key_down = 0.09
	_kick = minf(_kick + 5.0, 12.0)
	_dash_fx()


func _input(e: InputEvent) -> void:
	if _auto or not is_instance_valid(_view) or not _view.visible:
		return
	if e is InputEventKey:
		var k: InputEventKey = e
		if k.keycode == KEY_F8 or k.keycode == KEY_ESCAPE:
			return
		if k.pressed and not k.echo and (k.keycode == KEY_E or k.physical_keycode == KEY_E):
			_press()
		get_viewport().set_input_as_handled()      # 闪回里别的键不给关卡（背包、对话推进）
	elif e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		if e.pressed:
			_press()
		get_viewport().set_input_as_handled()
	elif e is InputEventScreenTouch:
		if e.pressed:
			_press()
		get_viewport().set_input_as_handled()


# ======================================================================= 冲刺特效
## 冲一下：速度线、脚下扬尘、三张残影（晨当前那帧的图，淡掉）
func _dash_fx() -> void:
	if not is_instance_valid(_chen):
		return
	for i in (4 if _lines_fx.size() < 24 else 1):
		_lines_fx.append({"p": Vector2(randf_range(CHEN_SX - 40.0, 500.0), randf_range(118.0, 200.0)),
			"len": randf_range(18.0, 56.0), "v": randf_range(520.0, 760.0), "life": 0.32, "max": 0.32})
	var feet := Vector2(_chen.position.x - 4.0, GROUND - 1.0)
	for i in (6 if _dust_p.size() < 40 else 2):
		_dust_p.append({"p": feet + Vector2(randf_range(-4.0, 4.0), 0.0),
			"v": Vector2(randf_range(-150.0, -50.0), randf_range(-70.0, -20.0)),
			"life": randf_range(0.3, 0.45), "max": 0.45, "s": 1.0 if randf() < 0.6 else 2.0})
	for i in 3:
		_ghost(float(i) * 0.04)


func _ghost(delay: float) -> void:
	if delay > 0.0:
		await get_tree().create_timer(delay, false).timeout
	if not is_instance_valid(_chen) or _spr == null or _spr.sprite_frames == null:
		return
	var tex := _spr.sprite_frames.get_frame_texture(_spr.animation, _spr.frame)
	if tex == null:
		return
	var g := Sprite2D.new()
	g.texture = tex
	g.centered = false
	g.flip_h = _spr.flip_h
	g.offset = _spr.offset
	g.position = _chen.position + _spr.position
	g.modulate = Color(GHOST_C, 0.45)
	_world.add_child(g)
	_world.move_child(g, _chen.get_index())   # 在她后面
	var tw := g.create_tween()
	tw.tween_property(g, "modulate:a", 0.0, 0.28).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tw.tween_callback(g.queue_free)


func _fx_step(delta: float) -> void:
	for i in range(_lines_fx.size() - 1, -1, -1):
		var l: Dictionary = _lines_fx[i]
		l["life"] = float(l["life"]) - delta
		l["p"] = (l["p"] as Vector2) - Vector2(float(l["v"]) * delta, 0.0)
		if float(l["life"]) <= 0.0:
			_lines_fx.remove_at(i)
	for i in range(_dust_p.size() - 1, -1, -1):
		var d: Dictionary = _dust_p[i]
		d["life"] = float(d["life"]) - delta
		var v: Vector2 = d["v"]
		v.y += 220.0 * delta
		v.x *= exp(-3.0 * delta)
		d["v"] = v
		var p: Vector2 = (d["p"] as Vector2) + v * delta
		p.y = minf(p.y, GROUND)
		d["p"] = p
		if float(d["life"]) <= 0.0:
			_dust_p.remove_at(i)
	_fx.queue_redraw()
	_dust.queue_redraw()


func _draw_speed_lines() -> void:
	for l in _lines_fx:
		var a := float(l["life"]) / float(l["max"])
		var p: Vector2 = l["p"]
		var ln := float(l["len"]) * (0.5 + 0.5 * a)
		_fx.draw_rect(Rect2(roundf(p.x), roundf(p.y), roundf(ln), 1), Color(SPEED_C, 0.42 * a * a))


func _draw_dust() -> void:
	for d in _dust_p:
		var a := float(d["life"]) / float(d["max"])
		var p: Vector2 = d["p"]
		var s := float(d["s"])
		_dust.draw_rect(Rect2(roundf(p.x), roundf(p.y) - s, s, s), Color(DUST_C, 0.8 * a))


# ======================================================================= 每帧：镜头、触手、目标、心跳、独白
func _process(delta: float) -> void:
	_t += delta
	if not is_instance_valid(_chen):
		return
	_kick *= exp(-6.0 * delta)
	var cx := _chen.position.x + _look + _kick
	_cam.position.x = lerpf(_cam.position.x, cx, 1.0 - exp(-FOLLOW * delta))
	var left := _cam.position.x - 240.0
	if _wet != null:
		_wet.set_shader_parameter("cam_left", left)
		_wet.set_shader_parameter("chen_x", _chen.position.x - left)
	if _train != null and _train_mode != "" and _chen.position.x > _train_wx + DOOR_POS.x + DOOR_HALF - DOOR_STOP:
		_chen.position.x = _train_wx + DOOR_POS.x + DOOR_HALF - DOOR_STOP   # 门关上了，过不去
	match _tmode:
		"grab":
			_front = move_toward(_front, _chen.position.x + 10.0, 420.0 * delta)
			_grab = move_toward(_grab, 1.0, 2.2 * delta)
		"back":
			_front -= 260.0 * delta
		"hover":
			_front = lerpf(_front, _chen.position.x + 14.0, 1.0 - exp(-1.5 * delta))
		"pass":
			_front += PASS_V / _k * delta
	_tents.queue_redraw()
	# 左边压暗那一片：跟着触手（前沿在触手尖后面一点）；第四次过去时有后沿
	_vmat.set_shader_parameter("grey_x", _front - 70.0 - left)
	_vmat.set_shader_parameter("grey_tail", _tail - left)
	_vmat.set_shader_parameter("chen_sx", _chen.position.x - left)
	_vmat.set_shader_parameter("t", _t)
	_goals_step(delta, left)
	if not _running:
		_train_step(delta)                      # 跑完了车还要接着动（慢下来停住 / 开走）：跑的时候 _run_step 里推（11-05 夜测：之前跑完车当场定住、也开不走）
	_fx_step(delta)
	_prompt_step(delta)
	_heart(delta)
	_lines_step(delta)


## 右边的目标（画 / 车门 / 暖光），每帧
func _goals_step(delta: float, left: float) -> void:
	if _paper != null and _paper.visible:
		var want := PAPER_HAND
		var rate := 2.6                         # 落回手里：一秒多一点
		if _paper_mode == "fly":
			want = Vector2(PAPER_LEAD + 18.0 * sin(_t * 0.8), PAPER_Y + 7.0 * sin(_t * 2.3) + 3.0 * sin(_t * 5.1))
			rate = 2.2
		_paper_off = _paper_off.lerp(want, 1.0 - exp(-rate * delta))   # 相对晨平滑地追：她跑多快，画都在前面一点
		_paper.position = Vector2(roundf(_chen.position.x + _paper_off.x), roundf(_paper_off.y))
		var flut := 0.0 if _paper_mode == "done" else (0.25 if _paper_mode == "catch" else 1.0)   # 落到手里就不晃了
		_paper.rotation = 0.2 * sin(_t * 3.1) * flut
		_paper.scale.x = lerpf(1.0, 0.6 + 0.4 * cos(_t * 3.7), flut)            # 翻着飘（窄一下宽一下）
		if _paper_mode == "catch" and _paper_off.distance_to(PAPER_HAND) < 3.0:
			_paper_mode = "done"                    # 落回手里：淡掉（她攥住了）
			print("FLASHBACK_PAPER caught t=%.1f" % _t)
			create_tween().tween_property(_paper, "modulate:a", 0.0, 0.3 * maxf(_k, 0.5)).set_trans(Tween.TRANS_SINE)
	if _train != null and _train.visible:
		_train.get_node("Deco").queue_redraw()
	if _light != null:
		_light.position = Vector2(roundf(left + LIGHT_SX), LIGHT_Y)
		_light.queue_redraw()


## 提示一跳一跳（头几秒明显，之后轻轻地）；按下去的那一下键帽往下一格
func _prompt_step(delta: float) -> void:
	_key_down = maxf(0.0, _key_down - delta)
	if _prompt_t > -100.0:
		_prompt_t += delta
	var ph := maxf(_prompt_t, 0.0)
	var amp := lerpf(0.35, 1.0, 1.0 - smoothstep(3.0, 4.5, ph))
	var w := 0.5 + 0.5 * cos(ph * TAU / 0.8)
	_prompt.modulate.a = _prompt_a * lerpf(1.0, 0.55 + 0.45 * w, amp)
	_key.queue_redraw()


func _draw_key() -> void:
	var d := 1.0 if _key_down > 0.0 else 0.0
	_key.draw_rect(Rect2(1, 2, 11, 12), KEY_SIDE)                  # 键帽的侧面（按下去就看不见了）
	_key.draw_rect(Rect2(0, 1 + d, 13, 12), KEY_C)                  # 外圈
	_key.draw_rect(Rect2(1, 2 + d, 11, 10), KEY_FACE)               # 键面
	var c := KEY_C if d == 0.0 else UITheme.WARM
	_key.draw_rect(Rect2(4, 4 + d, 1, 6), c)                        # E：一竖三横
	_key.draw_rect(Rect2(4, 4 + d, 5, 1), c)
	_key.draw_rect(Rect2(4, 6 + d, 4, 1), c)
	_key.draw_rect(Rect2(4, 9 + d, 5, 1), c)


func _heart(delta: float) -> void:
	var tension := 0.0
	if _running:
		tension = clampf(1.0 - (_chen.position.x - _front - 20.0) / (GAP0 - 20.0), 0.0, 1.0)
		if id == 4 and not _run_now:
			_bpm = move_toward(_bpm, 0.0, HEART_BPM.x / (STILL * _k * 1.4) * delta)   # 第四次站着：心跳慢慢停下
		else:
			_bpm = lerpf(HEART_BPM.x, HEART_BPM.y, tension)
		_heart_db = lerpf(HEART_DB.x, HEART_DB.y, tension)
	# 紧张的音乐：一直平滑地追目标音量（淡进来也是它管）
	if _music != null and str(_music.get_meta("snd", "")) == "flashback_tense":
		_music.volume_db = move_toward(_music.volume_db, lerpf(TENSE_DB.x, TENSE_DB.y, tension), 16.0 * delta)
	if _bpm < 20.0:
		return
	_heart_t += delta
	if _heart_t >= 60.0 / _bpm:
		_heart_t = 0.0
		_beat()


## 一下心跳：同一个播放器从头放（快的时候上一下的尾巴切掉，不叠成一团）
func _beat() -> void:
	if _heart_p == null:
		var p: String = runner._sfx_path("heartbeat")
		if p == "":
			runner.missing_sfx["heartbeat"] = true
			return
		_heart_p = AudioStreamPlayer.new()
		_heart_p.stream = load(p)
		_heart_p.bus = _bus
		add_child(_heart_p)
	_heart_p.volume_db = _heart_db
	_heart_p.play()


func _lines_step(delta: float) -> void:
	# 跑的时候按时间出；跑完了还没出完的（追上得早），每 0.9 秒补一句
	if _shown < _line_rows.size():
		var due := _run_t >= float(_line_t[_shown]) if _running else (result != "" and _t >= _flush_next)
		if due:
			_show_line(_shown)
			_shown += 1
			_flush_next = _t + 0.9 * _k
	# 掉字：最后一句出来 FALL_AFTER 秒以后，从后往前一个字一个字掉下去
	if not bool(st.get("fall", false)) or _shown < _line_rows.size() or _line_rows.is_empty():
		return
	var row: Array = _line_rows[_line_rows.size() - 1]
	_fall_t += delta
	if _fall_i < 0:
		if _fall_t >= FALL_AFTER * _k:
			_fall_i = row.size() - 1
			_fall_t = FALL_EVERY * _k
		return
	if _fall_i >= 0 and _fall_t >= FALL_EVERY * _k:
		_fall_t = 0.0
		var c: Label = row[_fall_i]
		var tw := create_tween().set_parallel()
		tw.tween_property(c, "position:y", c.position.y + 28.0, 0.7 * _k).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
		tw.tween_property(c, "modulate:a", 0.0, 0.7 * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
		_fall_i -= 1
		if _fall_i < 0:
			_fall_i = -2                        # 掉完了


func _show_line(i: int) -> void:
	for j in i:                                 # 前面的几句暗一点
		for c in _line_rows[j]:
			create_tween().tween_property(c, "modulate:a", 0.55, 0.6)
	for c in _line_rows[i]:
		create_tween().tween_property(c, "modulate:a", 1.0, 0.8 * maxf(_k, 0.5)).set_trans(Tween.TRANS_SINE)


## 剩下没出的独白都出完（追上得早也要说完），最后一句再停一会儿；要掉字的等它掉完
func _flush_lines() -> void:
	var guard := 0.0
	while guard < 15.0:
		var fall_done := not bool(st.get("fall", false)) or _fall_i == -2 or _line_rows.is_empty()
		if _shown >= _line_rows.size() and fall_done:
			break
		await StoryState.frame(get_tree())
		guard += get_process_delta_time()
	await _sleep(1.2)


# ======================================================================= 触手
## 每条：根在屏幕左边外面（跟着镜头），脊线 = 一串角度积分出来的点（沿正弦扭，越往尖扭得越厉害，尖上卷起来），
## 粗 → 细一节节四边形（硬像素边），上沿一道冷光和一条受光边，下沿更黑。卷住（grab）时尖都朝她收拢、卷得更紧；
## 第四次停在她身边、从身边过去时，靠近她的那几节绕开她的身子（不碰她）
func _draw_tentacles() -> void:
	if _tent_a <= 0.0 or not is_instance_valid(_cam):
		return
	_tents.modulate.a = _tent_a
	var left := _cam.position.x - 240.0
	var bx := left + T_ROOT
	var chen_c := Vector2(_chen.position.x, GROUND - BODY_HALF.y) if is_instance_valid(_chen) else Vector2(-99999, 0)
	var avoid := _tmode == "hover" or _tmode == "pass"
	_avoid_k = move_toward(_avoid_k, 1.0 if avoid else 0.0, get_process_delta_time() / 0.4)   # 绕开是 0.4 秒慢慢绕过去的，不是一下弹开
	if _avoid_k <= 0.0:
		_tside.clear()
	for i in TENT.size():
		var d: Array = TENT[i]
		var reach := maxf(20.0, (_front - bx) * float(d[1]))
		var ph := float(d[4])
		var curl := float(d[5]) * (0.75 + 0.25 * sin(_t * 1.3 + ph))
		var a0 := float(d[2])
		var amp := 0.42
		if _grab > 0.0:                         # 卷住：尖朝她收拢，卷得更紧，扭得更凶
			var by := float(d[0])
			a0 = lerpf(a0, atan2(chen_c.y - by, maxf(40.0, chen_c.x - bx)), _grab * 0.8)
			curl *= 1.0 + 0.6 * _grab
			amp = lerpf(0.42, 0.6, _grab)
		var pts := _spine(Vector2(bx, float(d[0])), reach / 0.86, a0, ph, curl, amp)
		if _avoid_k > 0.0:
			var th := float(d[3])
			var near := 0                       # 一条只走一边：看脊线上离她最近（x）的那一点在她身子中心上面还是下面
			for j in pts.size():
				if absf(pts[j].x - chen_c.x) < absf(pts[near].x - chen_c.x):
					near = j
			if _tside.size() <= i:              # 第一次绕的时候定下来，之后不变（不然扭着扭着从上面一下跳到下面）
				_tside.append(-1.0 if pts[near].y < chen_c.y else 1.0)
			var sgn: float = _tside[i]
			for j in pts.size():
				pts[j] = pts[j].lerp(_around(pts[j], chen_c, th * pow(1.0 - float(j) / float(TN), 1.15) + 0.7, sgn), _avoid_k)
		_tentacle(pts, float(d[3]))


func _spine(b: Vector2, length: float, a0: float, ph: float, curl: float, amp: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	pts.resize(TN + 1)
	var p := b
	pts[0] = p
	var ds := length / float(TN)
	for i in range(1, TN + 1):
		var s := float(i) / float(TN)
		var a := a0 + amp * sin(2.4 * PI * s - _t * 2.2 + ph) * (0.25 + 0.75 * s) + curl * pow(smoothstep(0.62, 1.0, s), 1.6)
		p += Vector2(cos(a), sin(a)) * ds
		pts[i] = p
	return pts


## 绕开她：离她身子（中心 c，半宽高 BODY_HALF）近的点往 sgn 那边（上 / 下，一条触手只走一边）推开，推到身子外面再加上这一节自己的半粗 w + 一点空，
## 正对着她的那一段全推开，两边 AVOID_FALL 像素里平滑地回到原来的路上。
## 11-05 夜测：原来只推脊线、圆心偏上、半径 40，触手自己十几像素粗，从她身上压过去（第四次「绕开她」其实盖住了她）。
func _around(p: Vector2, c: Vector2, w: float, sgn: float) -> Vector2:
	var dx := absf(p.x - c.x)
	var core := BODY_HALF.x + w
	if dx >= core + AVOID_FALL:
		return p
	var k := 1.0 - clampf((dx - core) / AVOID_FALL, 0.0, 1.0)
	k = k * k * (3.0 - 2.0 * k)
	var r := BODY_HALF.y + w + 3.0
	var y := minf(p.y, c.y - r) if sgn < 0.0 else maxf(p.y, c.y + r)   # 已经在身子外面的不动
	return Vector2(p.x, lerpf(p.y, y, k))


func _tentacle(pts: PackedVector2Array, thick: float) -> void:
	var n := pts.size() - 1
	var lp := PackedVector2Array()
	var rp := PackedVector2Array()
	var wd := PackedFloat32Array()
	lp.resize(n + 1)
	rp.resize(n + 1)
	wd.resize(n + 1)
	for i in n + 1:
		var s := float(i) / float(n)
		var dv := pts[mini(n, i + 1)] - pts[maxi(0, i - 1)]
		var nr := Vector2(-dv.y, dv.x).normalized()
		var w := thick * pow(1.0 - s, 1.15) + 0.7
		wd[i] = w
		lp[i] = pts[i] + nr * w
		rp[i] = pts[i] - nr * w
	for i in n:
		_quad(lp[i], lp[i + 1], rp[i + 1], rp[i], T_BODY)
	for i in n:
		var s := float(i) / float(n)
		var up_l := lp[i].y < rp[i].y           # 哪边朝上（受光）
		var su0 := lp[i] if up_l else rp[i]
		var su1 := lp[i + 1] if up_l else rp[i + 1]
		var sd0 := rp[i] if up_l else lp[i]
		var sd1 := rp[i + 1] if up_l else lp[i + 1]
		if wd[i] >= 2.5:                        # 下沿更黑
			_quad(pts[i].lerp(sd0, 0.6), pts[i + 1].lerp(sd1, 0.6), sd1, sd0, T_INK)
		if s > 0.06 and s < 0.9 and wd[i] >= 1.6:   # 上沿一道冷光
			_quad(pts[i].lerp(su0, 0.45), pts[i + 1].lerp(su1, 0.45), su1, su0, T_SHEEN)
			if wd[i] > 3.2 and s > 0.12 and s < 0.7:
				_tents.draw_line(su0, su1, T_RIM)


## 一节四边形：直接画两个三角形（卷得紧的地方四边形会折成蝴蝶结，draw_colored_polygon 三角化会失败）
func _quad(a: Vector2, b: Vector2, c: Vector2, d: Vector2, col: Color) -> void:
	_tents.draw_primitive(PackedVector2Array([a, b, c, d]), PackedColorArray([col, col, col, col]), PackedVector2Array())


# ======================================================================= 结束
func _ending() -> void:
	_chen.auto_dir = 0.0 if result != "escaped" else _chen.auto_dir
	if _paper_mode == "fly":
		_paper_mode = "catch"                       # 第一次：画落回她手里（被抓也一样，接剧本里的地图翻面）
	match result:
		"caught":
			_tmode = "grab"                     # 触手一把卷住她
			_vmat.set_shader_parameter("grey_a", 0.85)
			_bpm = 0.0
			_music_off(0.6)
			await _sleep(0.6)
			await _flush_lines()
			_end_color = BLACK_C
			await _veil_to(BLACK_C, 1.0)
		"still":
			_tmode = "hover"                    # 停在她身边……
			_bpm = 0.0
			_music_off(1.5)
			_achieve("fb_stood_still")
			create_tween().tween_method(_vp_param.bind("chen_lit"), 0.0, 1.0, 1.2 * _k).set_trans(Tween.TRANS_SINE)   # 灰过去的时候她身上不被压暗
			await _sleep(HOVER)
			_tmode = "pass"                     # ……绕开她从身边过去，什么也没发生
			_tail = _front - 380.0
			var tw := create_tween()
			tw.tween_property(self, "_tail", _front + 300.0, 3.2 * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
			tw.parallel().tween_property(self, "_tent_a", 0.0, 3.2 * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
			await tw.finished
			await _flush_lines()
			await _sleep(1.0)
			_end_color = BLACK_C
			await _veil_to(BLACK_C, 2.2)
		_:
			_tmode = "back"
			_achieve("fb_outran")
			match end_kind:
				"door":
					await _end_door()
				"white":
					await _end_white()
				_:
					_chen.auto_dir = 0.0         # 跑不动了，慢下来停住
					_bpm = HEART_BPM.x
					_music_off(2.0)
					await _sleep(1.2)
					await _flush_lines()
					_bpm = 0.0
					_end_color = BLACK_C
					await _veil_to(BLACK_C, 1.8)


## 第二次跑掉了：车慢下来停住，晨跑到尾门跟前，门在她面前关上（门楣的灯亮），车开走，再黑
func _end_door() -> void:
	_chen.auto_dir = 1.0
	if not _train.visible:
		_goal_train()
	_train_mode = "stop"
	var guard := 0.0
	while _train_wx + DOOR_POS.x + DOOR_HALF - _chen.position.x > DOOR_CLOSE_AT and guard < 5.0:
		await StoryState.frame(get_tree())
		guard += get_process_delta_time()
	_play("train_door_close", -6.0)
	var tw := create_tween()
	tw.tween_property(self, "_lamp", 1.0, 0.15)
	tw.tween_method(_set_door, 0.0, 1.0, 0.55).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_method(_set_door, 1.0, 0.94, 0.08)
	tw.tween_method(_set_door, 0.94, 1.0, 0.14).set_trans(Tween.TRANS_SINE)
	await _sleep(0.3)
	_chen.auto_dir = 0.0
	await tw.finished
	print("FLASHBACK_DOOR closed gap=%d waited=%.1fs" % [int(_train_wx + DOOR_POS.x + DOOR_HALF - _chen.position.x), guard])
	_bpm = 0.0
	_music_off(1.4)
	await _sleep(0.8)
	_train_mode = "go"                          # 车开走：慢慢加速，从右边出去
	create_tween().tween_property(self, "_lamp", 0.0, 0.6)
	guard = 0.0
	while _train_wx - (_cam.position.x - 240.0) < 500.0 and guard < 6.0:
		await StoryState.frame(get_tree())
		guard += get_process_delta_time()
	await _flush_lines()
	_end_color = BLACK_C
	await _veil_to(BLACK_C, 1.4)


## 第三次跑掉了：晨慢下来停住，暖光淡掉；字一个个掉完以后，整屏像相机过曝一样一下子闪白（flashback_view 的 flash），
## 白里透一点过曝的人影残像（ghost_a），残像慢慢淡掉，停在白上（醒的时候白慢慢退掉）。
## 11-05 作者定（嫌原来「左边灰右边白很劣质」）：不要从右边漫过来的软光，改成闪光灯式的过曝；意思不变——记忆是空白的。
func _end_white() -> void:
	_chen.auto_dir = 1.0
	create_tween().tween_property(self, "_light_a", 0.0, 1.2 * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)   # 远处的暖光淡掉
	_music_off(2.0)
	await _sleep(WHITE_STOP)
	_chen.auto_dir = 0.0                        # 跑着跑着慢下来，停住
	_bpm = 0.0
	await _flush_lines()
	_vmat.set_shader_parameter("ghost_a", 1.0)
	var tw := create_tween()
	var from := 0.0
	for f in FLASH:
		tw.tween_method(_vp_param.bind("flash"), from, float(f[0]), float(f[1])).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		from = float(f[0])
	await tw.finished
	print("FLASHBACK_WHITE flash")
	await _sleep(FLASH_HOLD)
	var tw2 := create_tween()
	tw2.tween_method(_vp_param.bind("ghost_a"), 1.0, 0.0, GHOST_OUT * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tw2.finished
	_end_color = WHITE_C
	await _veil_to(WHITE_C, 0.3)                 # 底下已经是满白：盖一层同色的白，醒的时候从这层退


## 尾门：k = 关了多少。两片门扇从门洞两边的门袋里滑出来（只露出滑出来的那一截，合缝那边在前）
func _set_door(v: float) -> void:
	_door_k = v
	if _door_l == null:
		return
	var w := roundf(DOOR_HALF * clampf(v, 0.0, 1.0))
	_door_l.visible = w >= 1.0
	_door_r.visible = w >= 1.0
	_door_l.region_rect = Rect2(DOOR_HALF - w, 0, w, DOOR_H)
	_door_l.position = DOOR_POS
	_door_r.region_rect = Rect2(0, 0, w, DOOR_H)
	_door_r.position = DOOR_POS + Vector2(DOOR_HALF * 2.0 - w, 0)


## 车上程序画的那几样：两节中间的折棚（一道道褶）、尾门门楣的指示灯（关门时亮）、门口站台上一小片暖光（门关上就没了）
func _draw_train_deco(n: Node2D) -> void:
	var x := TRAIN_W
	n.draw_rect(Rect2(x, 16, TRAIN_LINK, 94), Color8(6, 8, 9))
	for j in range(16, 110, 4):
		n.draw_rect(Rect2(x, j, TRAIN_LINK, 2), Color8(16, 19, 21))
	n.draw_rect(Rect2(x, 16, TRAIN_LINK, 1), Color8(40, 46, 48))
	if _lamp > 0.0:
		n.draw_rect(Rect2(DOOR_POS.x + DOOR_HALF - 3.0, DOOR_POS.y - 9.0, 6, 2), Color(LAMP_C, _lamp))
		n.draw_rect(Rect2(DOOR_POS.x + DOOR_HALF - 5.0, DOOR_POS.y - 10.0, 10, 4), Color(LAMP_C, 0.18 * _lamp))
	var open := 1.0 - _door_k
	if open > 0.0:
		n.draw_rect(Rect2(DOOR_POS.x - 6.0, 127, DOOR_HALF * 2.0 + 12.0, 2), Color(SPILL_C, 0.45 * open))
		n.draw_rect(Rect2(DOOR_POS.x - 12.0, 129, DOOR_HALF * 2.0 + 24.0, 2), Color(SPILL_C, 0.2 * open))


## 第三次的暖光：几圈加色的光晕 + 一个亮芯，慢慢一明一暗
func _draw_light() -> void:
	if _light_a <= 0.0:
		return
	var b := (0.85 + 0.15 * sin(_t * 1.6)) * _light_a
	_light.draw_circle(Vector2.ZERO, 15.0, Color(LIGHT_C, 0.07 * b))
	_light.draw_circle(Vector2.ZERO, 9.0, Color(LIGHT_C, 0.13 * b))
	_light.draw_circle(Vector2.ZERO, 5.0, Color(LIGHT_C, 0.3 * b))
	_light.draw_rect(Rect2(-1, -2, 2, 4), Color(LIGHT_C, b))
	_light.draw_rect(Rect2(-2, -1, 4, 2), Color(LIGHT_C, b))


func _veil_to(c: Color, sec: float) -> void:
	_veil.color = Color(c, _veil.color.a)
	var tw := create_tween()
	tw.tween_property(_veil, "color:a", 1.0, sec * _k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tw.finished


## 成就：flag 记下来（「全剧终」卡下面 barter.gd show_achievements 列出来），第一次拿到时屏幕上面一行字
func _achieve(flag: String) -> void:
	var first := not StoryState.has(flag)
	StoryState.set_flag(flag)
	print("FLASHBACK_ACH %s first=%s" % [flag, first])
	if not first:
		return
	var nm := flag
	var f := FileAccess.get_file_as_string(ACH_PATH)
	var j = JSON.parse_string(f)
	if j is Dictionary:
		for a in j.get("achievements", []):
			if (a.get("all", []) as Array) == [flag]:
				nm = str(a.get("zh" if I18n.is_zh() else "en", flag))
	_toast.text = "%s　%s" % [_tx("ach"), nm]
	var tw := create_tween()
	tw.tween_property(_toast, "modulate:a", 1.0, 0.5)
	tw.tween_interval(2.2)
	tw.tween_property(_toast, "modulate:a", 0.0, 0.8)


func _sleep(sec: float) -> void:
	await get_tree().create_timer(sec * _k, false).timeout


# ======================================================================= 醒
## 停在黑 / 白上的这一层慢慢睁眼：母星那一屏收掉，读屏幕的那层盖着原场景（全黑 / 全白、糊的），眼皮睁一半、合一点、再睁开
func wake() -> void:
	if is_instance_valid(_vp):
		_vp.queue_free()
	_view.visible = false
	_line_box.visible = false
	_prompt.visible = false
	_fx.visible = false
	_chen = null
	_screen.visible = true
	var lids := _end_color != WHITE_C          # 白的：白慢慢退掉，不画眼皮
	_smat.set_shader_parameter("veil", _end_color)
	_smat.set_shader_parameter("veil_a", 0.0 if lids else 1.0)
	_smat.set_shader_parameter("lids", 1.0 if lids else 0.0)
	_smat.set_shader_parameter("blur", 5.0)
	_smat.set_shader_parameter("desat", 0.6)
	_smat.set_shader_parameter("vig", 0.6)
	_veil.color.a = 0.0
	_duck(false)
	var k := _k
	var tw := create_tween().set_parallel()
	if lids:
		var tl := create_tween()
		tl.tween_method(_sp.bind("lids"), 1.0, 0.45, 0.9 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
		tl.tween_method(_sp.bind("lids"), 0.45, 0.7, 0.35 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		tl.tween_method(_sp.bind("lids"), 0.7, 0.0, 1.1 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	else:
		tw.tween_method(_sp.bind("veil_a"), 1.0, 0.0, 1.6 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_method(_sp.bind("blur"), 5.0, 0.0, 2.8 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_method(_sp.bind("desat"), 0.6, 0.0, 2.8 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_method(_sp.bind("vig"), 0.6, 0.0, 2.8 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tw.finished
	var p := get_parent()
	if p is CanvasLayer:
		p.queue_free()
	else:
		queue_free()


# ======================================================================= 声音
func _play(snd: String, db: float) -> void:
	var p: String = runner._sfx_path(snd)
	if p == "":
		runner.missing_sfx[snd] = true
		return
	var a := AudioStreamPlayer.new()
	a.stream = load(p)
	a.bus = _bus
	a.volume_db = db
	add_child(a)
	a.play()
	a.finished.connect(a.queue_free)


## 底下一层循环的声音：紧张的音乐（flashback_tense）+ 垫在底下的雨（rain_loop）；缺的静默跳过。sec = 从 -60 推到 db 用多久
func _music_on(snd: String, db: float, sec: float) -> AudioStreamPlayer:
	var p: String = runner._sfx_path(snd)
	if p == "":
		runner.missing_sfx[snd] = true
		return null
	var m := AudioStreamPlayer.new()
	m.stream = load(p)
	m.bus = _bus
	m.volume_db = -60.0
	m.set_meta("snd", snd)
	add_child(m)
	m.play()
	m.finished.connect(m.play)                  # 导入没开循环的（flashback_tense 24 秒）：放完从头再放
	create_tween().tween_property(m, "volume_db", db, sec)   # 之后紧张的音乐由 _heart 跟着触手多近平滑地变
	return m


## 黑到底那一下：紧张的音乐直接从目标音量起（只给 HIT 秒防爆音；故意的起音，qa_audio 认 qa_attack_until（帧号）不报），第一下心跳；
## 雨跟着街淡进来。缺音乐就只有雨（音量高一点）。
func _music_hit() -> void:
	if result != "":
		return
	_bpm = HEART_BPM.x
	_heart_t = 0.0
	_beat()
	_music = _music_on("flashback_tense", TENSE_DB.x, HIT)
	if _music != null:
		_music.set_meta("qa_attack_until", Engine.get_process_frames() + 20)   # 20 帧（约 0.33 秒）内的起音不算硬过渡
	_rain = _music_on("rain_loop", -30.0 if _music != null else -20.0, (BLACK_HOLD + STREET_IN) * _k)
	if _music == null:
		_music = _rain


func _music_off(sec: float) -> void:
	if _music == null:
		return
	var m := _music
	_music = null
	var tw := create_tween()
	tw.tween_property(m, "volume_db", -60.0, sec * _k)
	tw.tween_callback(m.queue_free)


## 原场景的环境声（SFX 总线）在闪回期间压低，醒的时候放回去；中途被换场景扔掉也放回去
func _duck(on: bool) -> void:
	var i := AudioServer.get_bus_index("SFX")
	if i < 0:
		return
	if on and not _ducked:
		_ducked = true
		_sfx_db = AudioServer.get_bus_volume_db(i)
		var from := _sfx_db
		create_tween().tween_method(func(v: float): AudioServer.set_bus_volume_db(i, v), from, from - DUCK, DUCK_SEC * _k)
	elif not on and _ducked:
		_ducked = false
		var cur := AudioServer.get_bus_volume_db(i)
		var to := _sfx_db
		create_tween().tween_method(func(v: float): AudioServer.set_bus_volume_db(i, v), cur, to, 0.5)


func _exit_tree() -> void:
	# 中途被扔掉（换场景、F8）：总线平滑地升回去、还在响的循环声挪到根上淡掉再删（11-04 作者：不要突然停的硬过渡）。
	# 用 SceneTree 的 tween：这个节点已经要没了，挂在它身上的 tween 跟着没。
	var tree := get_tree()
	if _ducked:
		var i := AudioServer.get_bus_index("SFX")
		if i >= 0:
			if tree != null:
				var cur := AudioServer.get_bus_volume_db(i)
				tree.create_tween().tween_method(func(v: float): AudioServer.set_bus_volume_db(i, v), cur, _sfx_db, 0.6)
			else:
				AudioServer.set_bus_volume_db(i, _sfx_db)
		_ducked = false
	if tree == null:
		return
	for c in get_children():
		if c is AudioStreamPlayer and (c as AudioStreamPlayer).playing and (c as AudioStreamPlayer).stream != null \
				and (c as AudioStreamPlayer).stream.get_length() >= 2.0:
			var a := c as AudioStreamPlayer
			remove_child.call_deferred(a)
			tree.root.add_child.call_deferred(a)
			var tw := tree.create_tween()
			tw.tween_interval(0.05)
			tw.tween_property(a, "volume_db", -60.0, 0.8)
			tw.tween_callback(a.queue_free)
