extends CanvasLayer
## 开始界面的背景（11-06 作者：「开始界面用云层小镇，点击开始后场面直接往下移，然后移到黑色，再移就到了森林，就像云层底下是森林的感觉」）。
## 建一份结局三小镇的 room_stage（art/town/room.json，风车、帆、星星都是它自己的），不接剧情（world = null），盖在森林上面、界面下面；只画天、云、房子、塔、风车（HIDE_LAYERS）。
## 下落（descend）：镜头往下。小镇各层按自己的视差往上走（FALL：天几乎不动，越靠前越快，最快的和房子、地面一样），底下接
## art/cloud_town/title_descent.png（一排排越来越暗的云 → 全黑 → 云底，tools/cloud_town_art.py --title-descent），它的底边透明，透出下面的森林。
## 森林也跟着往上走一小段（forest_cam_y，u² 收尾：落到位时和下落一起停），不是定在那里等着被揭开。
## 全程一条 smoothstep 曲线，每一层都是整像素；小镇被全黑盖住以后就藏起来、落完整个释放（贴图不留到第一章）。

const VIEW_X := 668.0                     # 标题看到的那一屏：右边大风车；「开始游戏」「制作人员」正好落在远处那排的风车（屏幕 x 199）和小房子（x 271）之间
const DRIFT := 6.0                        # 50 秒一个来回：比原来的 ±18 小，远处那排漂不到按钮后面
const DRIFT_SEC := 50.0
const TD_IMG := "res://art/cloud_town/title_descent.png"
const TD_OVER := 20                       # 这张图比小镇底边多往上盖多少行（cloud_town_art.py 的 TD_OVER）
const TD_X := -40.0                       # 图比一屏宽：左边多出来多少（图宽 600，镜头左右漂也露不出边）
## 11-06 作者：「近景的喷泉、地面、水车会挡住按钮，能不能去掉前景，只保留后面的云和房子」。这两层就是喷泉、水车、石板地、长椅、路灯、
## 围栏（连同挂在层上的喷泉、水车、风向旗动画）；藏掉以后脚下露出来的是作者的 main 云层，天、云、房子、塔、风车都不动。下落那段同样不画。
const HIDE_LAYERS := ["town_main", "deck_main", "front"]     # front：最前面那排黑云团（两处都叫 front），比地面还快，就是作者说的「小云彩」
const STATIC_CLOUD_LAYERS := ["cloud_mid_over", "cloud_midfar_over"] # 标题中最靠前的两排可见云
const MAX_STEP_SEC := 0.05                # 卡了一下也别一帧跳很远：一帧最多算这么多秒
const HIDE_TOWN_AT := 320.0               # 落到这里全黑已经盖满，小镇不用画了
const FOREST_RISE := 300.0                # 森林跟着走的距离系数（见 forest_cam_y）
## 每层下落时相对镜头走多快。11-06 作者：「云层往下有视差问题，小云彩会加速漂上去」：原来作者的 main（1.0）和 front（1.4）画在远处那排塔
## （0.72）后面，一落就从塔后面超上去。规矩：画得越靠前的层只能越快（_check_order 核对），wash 是贴着天的光，跟天走。没写的 = 1。
const FALL := {
	"sky": 0.08, "wash": 0.08, "high": 0.1, "streaks": 0.1, "spires": 0.12, "far": 0.2, "midfar": 0.3, "mid": 0.45, "near": 0.58, "main": 0.66,
	"town_far": 0.72, "deck_far": 0.72, "cloud_midfar_over": 0.82,
}

var descending := false
var _stage: Node2D
var _root: Node2D
var _td: Sprite2D
var _t := 0.0
var _d := 0.0                             # 落了多少像素
var _end := 1.0                           # 落到底（图底边到屏幕顶）是多少像素
var _sec := 1.0
var _k := 0.0
var _max_step := 0.0
var _origin_y := 0.0                      # 小镇在世界里的 y（room.json 的 origin）：小镇释放以后接缝的位置还要用
var _qa := "--qa_live" in OS.get_cmdline_user_args()
var _qa_y := {}


func _ready() -> void:
	layer = 11                            # 森林的 Overlay（暗角、闪电的白光）在 10，界面在 20：闪电和暗角是森林的，不压在小镇上
	_root = Node2D.new()
	_root.name = "Root"
	add_child(_root)
	_stage = (load("res://scripts/room_stage.gd") as GDScript).new()
	_root.add_child(_stage)
	_stage.setup("town", null)
	for L in _stage._layers:
		var cfg: Dictionary = L["cfg"]
		var id := str(cfg.get("id", ""))
		if id in HIDE_LAYERS:
			(L["node"] as Sprite2D).visible = false
		elif id in STATIC_CLOUD_LAYERS:
			# 保留第一帧构图，把这一层固定在屏幕横向位置上。
			cfg["x"] = float(cfg.get("x", 0.0)) - VIEW_X * float(cfg.get("scroll", 1.0))
			cfg["scroll"] = 0.0
			cfg["drift"] = 0.0
	if _qa:
		_check_order()
	var tex: Texture2D = load(TD_IMG) if ResourceLoader.exists(TD_IMG) else null
	if tex != null:
		_td = Sprite2D.new()
		_td.name = "Descent"
		_td.centered = false
		_td.texture = tex
		_td.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		_td.z_index = 60                  # 小镇的层在 -100 往上（front 是 100 往上）
		_root.add_child(_td)
		_end = 270.0 + tex.get_height() - TD_OVER
	_apply(0.0)


func _process(delta: float) -> void:
	_t += delta
	if descending:
		_k = minf(_k + minf(delta, MAX_STEP_SEC) / _sec, 1.0)
		var was := _d
		_d = _end * _k * _k * (3.0 - 2.0 * _k)
		_max_step = maxf(_max_step, _d - was)
		if _d >= HIDE_TOWN_AT and _stage != null:
			_stage.queue_free()
			_stage = null
	_apply(delta)
	if _qa and descending:
		_qa_track()
	if descending and _k >= 1.0:
		descending = false
		if _qa:
			print("TITLE_DESCENT done 总距离 %d 秒数 %.1f 每帧最大 %.1f 像素" % [int(_end), _sec, _max_step])
			for id in _qa_y:
				var q: Dictionary = _qa_y[id]
				print("TITLE_DESCENT_LAYER %s 系数 %.2f 走了 %d 像素 一帧最多 %d 速度一帧最多变 %d 往回走 %d 次" % [id, q["f"], int(q["y0"] - q["y"]), int(q["max"]), int(q["dv"]), int(q["back"])])


func _apply(delta: float) -> void:
	var cl := roundf(VIEW_X + DRIFT * sin(_t * TAU / DRIFT_SEC))
	var d := roundf(_d)
	if _stage != null:
		_stage.update(delta, Vector2(cl + 240.0, 135.0))
		for L in _stage._layers:
			var c: Dictionary = L["cfg"]
			(L["node"] as Sprite2D).position.y = d - roundf(_d * float(FALL.get(str(c.get("id", "")), 1.0)))
	_root.position = Vector2(-cl, -_stage_y() - d)
	if _td != null:
		_td.position = Vector2(VIEW_X + TD_X, _stage_y() + 270.0 - TD_OVER)


## --qa_live：越靠前的层只能越快（藏着的和 wash 不算）
func _check_order() -> void:
	var last := 0.0
	var bad := 0
	for L in _stage._layers:
		var id := str((L["cfg"] as Dictionary).get("id", ""))
		if not (L["node"] as Sprite2D).visible or id == "wash":
			continue
		var f := float(FALL.get(id, 1.0))
		if f < last:
			bad += 1
			print("TITLE_DESCENT_ORDER_BAD %s %.2f 画在 %.2f 前面" % [id, f, last])
		last = maxf(last, f)
	print("TITLE_DESCENT order bad=%d" % bad)


## --qa_live：每层在屏幕上的 y，逐帧记：不往回走、一帧走多少、速度一帧变多少（整像素，抖 1~2 算正常）
func _qa_track() -> void:
	var rows := {}
	if _stage != null:
		for L in _stage._layers:
			var n: Sprite2D = L["node"]
			if n.visible:
				rows[str((L["cfg"] as Dictionary).get("id", ""))] = n.global_position.y
	if _td != null:
		rows["title_descent"] = _td.global_position.y
	for id in rows:
		var y: float = rows[id]
		if not _qa_y.has(id):
			_qa_y[id] = {"f": float(FALL.get(id, 1.0)), "y0": y, "y": y, "v": 0.0, "max": 0.0, "dv": 0.0, "back": 0}
			continue
		var q: Dictionary = _qa_y[id]
		var v: float = q["y"] - y
		q["max"] = maxf(q["max"], v)
		q["dv"] = maxf(q["dv"], absf(v - float(q["v"])))
		if v < 0.0:
			q["back"] = int(q["back"]) + 1
		q["v"] = v
		q["y"] = y


func _stage_y() -> float:
	return _stage.origin.y if _stage != null else _origin_y


## 点开始：落 sec 秒
func descend(sec: float) -> void:
	_sec = maxf(sec, 0.1)
	_k = 0.0
	descending = true
	_origin_y = _stage.origin.y
	if _qa:
		print("TITLE_DESCENT start 总距离 %d" % int(_end))


## 落的时候森林的镜头高度（森林的最上面一直在全黑 / 云底后面，露不出树干被图边切断的那一行）
func forest_cam_y() -> float:
	var u := 1.0 - _d / _end
	return 135.0 - roundf(FOREST_RISE * u * u)


func finished() -> bool:
	return not descending and _k >= 1.0
