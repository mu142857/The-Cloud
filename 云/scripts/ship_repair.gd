extends RefCounted
## 第一关小游戏 ship_repair：在弥洛树屋里修推进器（实现规格第 14 节；本2兔原话：拿着铁锤在零件很多的地方敲，
##   每一个都要恰好对应的敲击次数，超过或者不够都不行；换了好几次零件、或者第三次进入，就直接跳过。「经典的旋转水管，
##   水管路线通过了以后就直接盖上盖子，然后猛敲」）。只修一次。
##
## 画面：房间压暗，正中一块推进器内部的特写面板（art/ship_repair/，tools/ship_repair_art.py 画的，1 倍像素、正面平视）。
##   左边炉膛里烧着余火，中间凹槽里 4×3 格水管，右边出口管 + 喷口。泛光一律第一关的暖红（ship_glow.gd 的 HOT_*）。
##
## 怎么玩（鼠标点，或方向键选 + 空格 / E / 回车；没有计时）：
##   ① 水管：点一格 = 顺时针转 90°（平滑转过去，带一点回弹）。和炉膛接上的管子先温热（半亮），
##      从进口一路通到出口那一刻，火顺着管子一格一格烧亮，喷口亮起来。
##   ② 盖子：顺着两边滑轨从上面滑下来盖住水管，「哐」落定，扳手声扣紧。
##   ③ 锤子：盖子上四个零件，每个头上一个圈，圈里几个点 = 要敲几下。每敲一下亮一个点、零件往下进一点；
##      敲够了停手，零件稳一下（SETTLE 秒）就「咔」地锁死。还在稳的时候再敲一下 = 敲过头：零件「嘣」地弹回去、
##      圈里的点全灭，只有这一个重来（不够不算错，接着敲就是）。
##   放水：敲过头累计 3 次（FAILS_GIVE），或者第 3 次进这个小游戏（ENTER_GIVE），剩下的锤子自己敲完（看得见，不跳）。
##
## 剧本步骤：{"do": "mechanic", "id": "ship_repair"}，可选：
##   "sets": ["c1_fixed"]            修好以后设的 flag
##   "hits": [2, 1, 3, 2]            四个零件各要敲几下（1..4）
##   "hint_pipes" / "hint_hammer": {zh, en}   面板上面那一行提示（不写用默认）
##   "lines": {intro, pipes_done, crack_1, give, done}   各个时刻插一串剧本步骤（弥洛说话之类），都可以不写
## 进度（story.mech_load）：{enter: 第几次进, fails: 敲过头几次, rots: [12 格水管的方向], pipes: 水管接通没有, done}。
##   中途退出再进：水管接通过就直接从锤子开始；enter 每进一次 +1。

const KIT := preload("res://scripts/river_explore_order.gd")
const ID := "ship_repair"
const DIR := "res://art/ship_repair/"
const SFX_DIR := "res://audio/sfx/"

const PANEL := Vector2(232, 150)
const PANEL_POS := Vector2(124, 66)
const CAV := Vector2(64, 40)          # 凹槽左上（面板里的像素），和 tools/ship_repair_art.py 的 CAV 一致
const T := 24                         # 一格水管
const COLS := 4
const ROWS := 3
const IN_CELL := Vector2i(0, 1)       # 进口：左边第 1 行（炉膛那根管子）
const OUT_CELL := Vector2i(3, 0)      # 出口：右边第 0 行（喷口那根管子）
const LID_X := 58
const LID_Y := 36                     # 盖子盖好的位置
const LID_H := 80
const PART_X := [20, 42, 66, 88]      # 零件中心（盖子里的 x），和画图脚本一致
const PART_Y := 60                    # 零件插孔中心（盖子里的 y）
const RING_Y := 36                    # 圈的中心（盖子里的 y）
const HITS := [2, 1, 3, 2]
const SETTLE := 0.45                  # 敲够以后零件稳多久才锁死（这段时间里再敲 = 敲过头）
const SINK := 5.0                     # 敲够时零件往下进了多少像素（锁死再进到 7）
const FAILS_GIVE := 3
const ENTER_GIVE := 3

const DIM := Color(0.02, 0.03, 0.04, 0.72)
const HOT := [Color("#4a2226"), Color("#962f2c"), Color("#c9473a"), Color("#e8795a"), Color("#f0c070")]
const HOLE := Color("#142a2c")
const HOVER := Color("#1c2125")

const HINT_PIPES := {"zh": "点水管转动，把炉火接到喷口", "en": "Click the pipes to turn them. Lead the fire to the nozzle."}
const HINT_HAMMER := {"zh": "圈里几个点就敲几下，敲够了就停手", "en": "Hit each part as many times as its dots, then stop."}

# 水管方向位：北 1 / 东 2 / 南 4 / 西 8；基准形状（转 0 格时）
const N := 1
const E := 2
const S := 4
const W := 8
const BASE := [E | W, N | E, N | E | W, W]      # 直管 / 弯管 / 三通 / 堵头（pipes.png 的四列）
## 12 格：[形状, 开局方向, 接通要的方向（-1 = 不在路上的摆设）]，按行从左上数。
##   路线：进口 → (0,1) → (1,1) → (1,2) → (2,2) → (3,2) → (3,1) → (3,0) → 出口。照对的转一共 9 下。
const GRID := [
	[2, 1, -1], [1, 3, -1], [0, 1, -1], [1, 0, 1],
	[0, 1, 0],  [1, 1, 2],  [3, 2, -1], [0, 0, 1],
	[1, 0, -1], [1, 2, 0],  [0, 1, 0],  [1, 1, 3],
]

signal _stage(kind: String)


# ======================================================================= 规则（纯函数：check 和测试直接调）
static func mask(kind: int, rot: int) -> int:
	var m: int = BASE[kind]
	for i in posmod(rot, 4):
		m = ((m << 1) | (m >> 3)) & 15
	return m


static func _opp(d: int) -> int:
	return ((d << 2) | (d >> 2)) & 15


static func start_rots() -> Array:
	var out: Array = []
	for g in GRID:
		out.append(int(g[1]))
	return out


static func solved_rots() -> Array:
	var out: Array = []
	for g in GRID:
		out.append(int(g[2]) if int(g[2]) >= 0 else int(g[1]))
	return out


## 火从进口走得到哪些格：{lit: {格: 离进口几格}, done: 通到出口没有}
static func flow(rots: Array) -> Dictionary:
	var lit := {}
	var st := IN_CELL.y * COLS + IN_CELL.x
	if mask(int(GRID[st][0]), int(rots[st])) & W == 0:
		return {"lit": lit, "done": false}
	lit[st] = 0
	var q: Array = [st]
	var dirs := {N: Vector2i(0, -1), E: Vector2i(1, 0), S: Vector2i(0, 1), W: Vector2i(-1, 0)}
	while not q.is_empty():
		var i: int = q.pop_front()
		var m := mask(int(GRID[i][0]), int(rots[i]))
		for d in dirs:
			if m & int(d) == 0:
				continue
			var c: Vector2i = Vector2i(i % COLS, i / COLS) + dirs[d]
			if c.x < 0 or c.y < 0 or c.x >= COLS or c.y >= ROWS:
				continue
			var j := c.y * COLS + c.x
			if not lit.has(j) and mask(int(GRID[j][0]), int(rots[j])) & _opp(int(d)) != 0:
				lit[j] = int(lit[i]) + 1
				q.append(j)
	var o := OUT_CELL.y * COLS + OUT_CELL.x
	return {"lit": lit, "done": lit.has(o) and mask(int(GRID[o][0]), int(rots[o])) & E != 0}


## 照对的转：下一格该点哪一格（-1 = 已经通了）
static func best_tile(rots: Array) -> int:
	if flow(rots)["done"]:
		return -1
	for i in GRID.size():
		var want := int(GRID[i][2])
		if want >= 0 and mask(int(GRID[i][0]), int(rots[i])) != mask(int(GRID[i][0]), want):
			return i
	return -1


static func fresh() -> Dictionary:
	return {"enter": 0, "fails": 0, "rots": start_rots(), "pipes": false, "done": false}


static func valid(s: Dictionary) -> bool:
	return s.has("rots") and (s["rots"] as Array).size() == GRID.size() and s.has("enter") and s.has("fails")


static func needs(step: Dictionary) -> Array:
	var h: Array = step.get("hits", HITS)
	if h.size() != PART_X.size():
		h = HITS
	var out: Array = []
	for v in h:
		out.append(clampi(int(v), 1, 4))
	return out


## 敲一下零件 p（{hits, locked}）：hit 还不够 / full 刚好（等稳住就锁）/ crack 敲过头（清零重来）/ locked 已经锁了
static func hit(p: Dictionary, need: int) -> String:
	if p["locked"]:
		return "locked"
	p["hits"] = int(p["hits"]) + 1
	if int(p["hits"]) > need:
		p["hits"] = 0
		return "crack"
	return "full" if int(p["hits"]) == need else "hit"


# ======================================================================= 演出
var auto_mode := false
var tried := {}
var story: Node
var level: Node
var step: Dictionary
var s: Dictionary
var stage := ""                       # in / pipes / flow / lid / hammer / give / done
var need: Array = []
var tiles: Array = []                 # [{ang（显示的方向，按 90° 算）, heat 0..1}]
var parts: Array = []                 # [{hits, locked, sink, pop, bob, settle, lock_a, flash, shake}]
var board: Control
var _root: Control
var _dim: ColorRect
var _hint: Label
var _layer: CanvasLayer
var _accept := false
var _waiting := false                 # 锤子这一段正在等玩家（敲过头满三次 / 全锁上 → 发 _stage）
var _sel := -1
var _t := 0.0
var _lid_y := -LID_H - 4.0
var _ring_a := 0.0
var _noz := 0.0                       # 喷口热光 0..1
var _furn := 0.6                      # 炉火亮度
var _ham_a := 0.0
var _ham_ang := 0.0                   # 0 = 举着（图本来的样子），STRIKE = 落下
var _ham_p := Vector2(250, 90)        # 锤子握柄支点（面板里的像素）
var _ham_goal := -1
var _queue: Array = []
var _swinging := false
var _sparks: Array = []
var _said := {}
var _tex := {}
var _ring_tex: ImageTexture
var _disk_tex: ImageTexture

const STRIKE := -1.89                 # 锤子落下时转多少（弧度，逆时针）：锤头从圈上方甩下来砸到零件帽
const HAM_PIVOT := Vector2(28, 28)    # hammer.png 里的握柄末端


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	story = r
	level = lv
	step = st
	need = needs(step)
	s = story.mech_load(ID)
	if not valid(s):
		var keep: Dictionary = s
		s = fresh()
		if keep.has("enter"):
			s["enter"] = int(keep["enter"])
	s["enter"] = int(s["enter"]) + 1
	story.mech_save(ID, s)
	var give: bool = int(s["enter"]) >= ENTER_GIVE or int(s["fails"]) >= FAILS_GIVE
	print("MECH %s enter=%d fails=%d give=%s" % [ID, int(s["enter"]), int(s["fails"]), give])
	if s["pipes"] and not flow(s["rots"])["done"]:
		s["rots"] = solved_rots()
	_build()
	await _fade_in()
	await _lines("intro")
	# ① 水管
	if not s["pipes"]:
		stage = "pipes"
		_set_hint(step.get("hint_pipes", HINT_PIPES))
		_refresh_heat()
		if give or auto_mode:
			await _auto_pipes(give)
		else:
			_accept = true
			_sel = -1
			if not flow(s["rots"])["done"]:
				await _stage
			_accept = false
		s["pipes"] = true
		story.mech_save(ID, s)
		stage = "flow"
		_set_hint({})
		await _flow_light()
		await _lines("pipes_done")
		stage = "lid"
		await _close_lid()
	else:
		_refresh_heat(true)
		_noz = 1.0
		_lid_y = LID_Y
	# ③ 锤子
	stage = "hammer"
	await _show_hammer()
	if give or auto_mode:
		await _auto_hammer(give)
	else:
		_set_hint(step.get("hint_hammer", HINT_HAMMER))
		_accept = true
		_waiting = true
		_sel = 0
		_ham_goal = 0
		var res: String = await _stage
		_waiting = false
		_accept = false
		if res == "give":
			stage = "give"
			_set_hint({})
			await _wait(0.5)
			await _lines("give")
			await _auto_hammer(true)
	stage = "done"
	_set_hint({})
	await _finish()
	s["done"] = true
	story.mech_save(ID, s)
	for f in step.get("sets", []):
		StoryState.set_flag(str(f))
	await _lines("done")
	await _fade_out()
	print("MECH %s done enter=%d fails=%d" % [ID, int(s["enter"]), int(s["fails"])])


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


## 跳节拍：修好了（同步、不演）
func ff(r: Node, st: Dictionary) -> void:
	var t := fresh()
	t["rots"] = solved_rots()
	t["pipes"] = true
	t["done"] = true
	t["enter"] = 1
	r.mech_save(ID, t)
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))


func check(r: Node, st: Dictionary) -> Array:
	var out: Array = []
	if st.has("hits"):
		var h: Array = st["hits"]
		if h.size() != PART_X.size():
			out.append("hits 要 %d 个（盖子上 %d 个零件），现在 %d 个" % [PART_X.size(), PART_X.size(), h.size()])
		for v in h:
			if int(v) < 1 or int(v) > 4:
				out.append("hits 每个要在 1..4（圈里最多放 4 个点）：%s" % str(v))
	if flow(start_rots())["done"]:
		out.append("开局水管就是通的")
	if not flow(solved_rots())["done"]:
		out.append("照 GRID 的答案转完水管不通")
	for k in ["intro", "pipes_done", "crack_1", "give", "done"]:
		if not KIT.has_lines(st, k):
			out.append("info: 没有 lines.%s" % k)
	for k in st.get("lines", {}):
		out.append_array(KIT.check_steps(r, "lines.%s" % k, st["lines"][k]))
	return out


# ----------------------------------------------------------------------- 搭画面
class Board extends Control:
	var m

	func _input(e: InputEvent) -> void:
		if m != null:
			m._on_input(e)

	func _process(dt: float) -> void:
		if m != null:
			m._tick(dt)

	func _draw() -> void:
		if m != null:
			m._draw_board(self)


func _build() -> void:
	for k in ["panel", "furnace_glow", "nozzle_glow", "pipes", "lid", "parts", "hammer"]:
		_tex[k] = _load_tex(DIR + k + ".png")
	_ring_tex = _circle_tex(false)
	_disk_tex = _circle_tex(true)
	tiles.clear()
	for i in GRID.size():
		tiles.append({"ang": float(s["rots"][i]), "goal": float(s["rots"][i]), "heat": 0.0, "tw": null})
	parts.clear()
	for i in PART_X.size():
		parts.append({"hits": 0, "locked": false, "sink": 0.0, "pop": 0.0, "bob": 0.0, "settle": 0.0,
			"lock_a": 0.0, "flash": 0.0, "shake": 0.0})
	_root = Control.new()
	_root.name = "ShipRepair"
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.size = Vector2(480, 270)
	var dlg = story.get("dlg")
	if dlg is Node and is_instance_valid(dlg) and dlg.get_parent() != null:
		var host: Node = dlg.get_parent()
		host.add_child(_root)
		host.move_child(_root, dlg.get_index())       # 对话框盖在面板上面（弥洛说话照常看得见）
	else:
		_layer = CanvasLayer.new()
		_layer.layer = 50
		(level if level != null else story).add_child(_layer)
		_layer.add_child(_root)
	_dim = ColorRect.new()
	_dim.color = DIM
	_dim.size = Vector2(480, 270)
	_dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dim.modulate.a = 0.0
	_root.add_child(_dim)
	board = Board.new()
	board.m = self
	board.position = PANEL_POS
	board.size = PANEL
	board.clip_contents = true                         # 盖子从面板顶边滑进来，外面看不见
	board.mouse_filter = Control.MOUSE_FILTER_IGNORE
	board.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	board.modulate.a = 0.0
	_root.add_child(board)
	_hint = Label.new()
	_hint.position = Vector2(0, PANEL_POS.y - 19)
	_hint.size = Vector2(480, 16)
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint.add_theme_font_size_override("font_size", 14)
	_hint.add_theme_color_override("font_color", UITheme.TEXT)
	_hint.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))
	_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hint.modulate.a = 0.0
	_root.add_child(_hint)


## 图还没被编辑器导入（作者醒着不跑 --import）时直接读 png；导入过就走正常的资源
static func _load_tex(p: String) -> Texture2D:
	if ResourceLoader.exists(p):
		return load(p)
	var img := Image.load_from_file(ProjectSettings.globalize_path(p))
	return ImageTexture.create_from_image(img) if img != null else null


## 圈（16×16，中心在像素角上，所以 2×2 的点能正好居中）：fill = 实心圆盘（圈里的底），否则 = 1 像素的连续圆边
static func _circle_tex(fill: bool) -> ImageTexture:
	var img := Image.create(16, 16, false, Image.FORMAT_RGBA8)
	for y in 16:
		for x in 16:
			if not _in_disk(x, y):
				continue
			var edge := not (_in_disk(x - 1, y) and _in_disk(x + 1, y) and _in_disk(x, y - 1) and _in_disk(x, y + 1))
			if fill or edge:
				img.set_pixel(x, y, Color.WHITE)
	return ImageTexture.create_from_image(img)


static func _in_disk(x: int, y: int) -> bool:
	if x < 0 or y < 0 or x > 15 or y > 15:
		return false
	var dx := x + 0.5 - 8.0
	var dy := y + 0.5 - 8.0
	return dx * dx + dy * dy <= 64.0


func _k() -> float:
	return 0.25 if auto_mode else 1.0


func _alive() -> bool:
	return board != null and is_instance_valid(board) and board.is_inside_tree() and not story.ended


func _wait(sec: float) -> void:
	if _alive():
		await board.get_tree().create_timer(sec * _k()).timeout


func _tw() -> Tween:
	return board.create_tween()


func _fade_in() -> void:
	var tw := _tw().set_parallel(true)
	tw.tween_property(_dim, "modulate:a", 1.0, 0.45 * _k()).set_trans(Tween.TRANS_SINE)
	tw.tween_property(board, "modulate:a", 1.0, 0.4 * _k()).set_trans(Tween.TRANS_SINE).set_delay(0.1 * _k())
	board.position.y = PANEL_POS.y + 10
	tw.tween_property(board, "position:y", PANEL_POS.y, 0.5 * _k()).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT).set_delay(0.1 * _k())
	await tw.finished


func _fade_out() -> void:
	if not _alive():
		_drop()
		return
	var tw := _tw().set_parallel(true)
	tw.tween_property(_hint, "modulate:a", 0.0, 0.3 * _k())
	tw.tween_property(board, "modulate:a", 0.0, 0.45 * _k()).set_trans(Tween.TRANS_SINE)
	tw.tween_property(board, "position:y", PANEL_POS.y + 8, 0.5 * _k()).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	tw.tween_property(_dim, "modulate:a", 0.0, 0.6 * _k()).set_trans(Tween.TRANS_SINE).set_delay(0.15 * _k())
	await tw.finished
	_drop()


func _drop() -> void:
	if board != null and is_instance_valid(board):
		board.m = null
	if _layer != null and is_instance_valid(_layer):
		_layer.queue_free()
	elif _root != null and is_instance_valid(_root):
		_root.queue_free()


func _set_hint(d: Dictionary) -> void:
	if _hint == null or not _alive() or (d.is_empty() and _hint.modulate.a <= 0.01):
		return
	var tw := _tw()
	if _hint.modulate.a > 0.01:
		tw.tween_property(_hint, "modulate:a", 0.0, 0.2)
	if not d.is_empty():
		tw.tween_callback(func(): _hint.text = I18n.pick(d))
		tw.tween_property(_hint, "modulate:a", 1.0, 0.35).set_trans(Tween.TRANS_SINE)


func _lines(key: String) -> void:
	if KIT.has_lines(step, key) and _alive():
		await KIT.lines(story, step, key)


# ----------------------------------------------------------------------- 音效（面板是界面：不分左右远近）
func _sfx(name: String, db := 0.0, pitch := 1.0) -> void:
	if story.ff or not _alive():
		return
	var stream: AudioStream = null
	for ext in [".wav", ".ogg"]:
		if ResourceLoader.exists(SFX_DIR + name + ext):
			stream = load(SFX_DIR + name + ext)
			break
	if stream == null and FileAccess.file_exists(SFX_DIR + name + ".wav"):
		stream = AudioStreamWAV.load_from_file(ProjectSettings.globalize_path(SFX_DIR + name + ".wav"))   # 新音效还没导入
	if stream == null:
		return
	var a := AudioStreamPlayer.new()
	a.stream = stream
	if AudioServer.get_bus_index("SFX") >= 0:
		a.bus = "SFX"
	a.volume_db = db
	a.pitch_scale = pitch
	_root.add_child(a)
	a.play()
	a.finished.connect(a.queue_free)


# ----------------------------------------------------------------------- 输入
func _on_input(e: InputEvent) -> void:
	if not _accept or not _alive():
		return
	for n in ["_settings", "_bag"]:
		var pnl = level.get(n) if level != null else null
		if pnl is CanvasItem and (pnl as CanvasItem).visible:
			return
	if e is InputEventKey and ((e as InputEventKey).keycode == KEY_ESCAPE or (e as InputEventKey).keycode == KEY_F8):
		return                                         # Esc 照常开设置
	var vp := board.get_viewport()
	if e is InputEventMouseMotion:
		var i := _pick(board.get_local_mouse_position())
		if i >= 0:
			_select(i)
		vp.set_input_as_handled()
	elif e is InputEventMouseButton:
		if e.pressed and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			var i := _pick(board.get_local_mouse_position())
			if i >= 0:
				_select(i)
				_act(i)
		vp.set_input_as_handled()
	elif e is InputEventKey:
		if e.pressed and not e.echo:
			var k: int = (e as InputEventKey).keycode
			if k in [KEY_LEFT, KEY_A]:
				_move(-1, 0)
			elif k in [KEY_RIGHT, KEY_D]:
				_move(1, 0)
			elif k in [KEY_UP, KEY_W]:
				_move(0, -1)
			elif k in [KEY_DOWN, KEY_S]:
				_move(0, 1)
			elif k in [KEY_SPACE, KEY_E, KEY_ENTER, KEY_KP_ENTER, KEY_Z]:
				if _sel < 0:
					_select(0)
				else:
					_act(_sel)
		vp.set_input_as_handled()


func _pick(p: Vector2) -> int:
	if stage == "pipes":
		var q := p - CAV
		if q.x >= 0 and q.y >= 0 and q.x < COLS * T and q.y < ROWS * T:
			return int(q.y / T) * COLS + int(q.x / T)
	elif stage == "hammer":
		for i in PART_X.size():
			var cx: float = LID_X + PART_X[i]
			if absf(p.x - cx) <= 11.0 and p.y >= LID_Y + RING_Y - 10 and p.y <= LID_Y + PART_Y + 6:
				return i
	return -1


func _select(i: int) -> void:
	if i == _sel:
		return
	_sel = i
	if stage == "hammer":
		_ham_goal = i


func _move(dx: int, dy: int) -> void:
	if _sel < 0:
		_select(0)
		return
	if stage == "pipes":
		var c := clampi(_sel % COLS + dx, 0, COLS - 1)
		var r := clampi(_sel / COLS + dy, 0, ROWS - 1)
		_select(r * COLS + c)
	elif stage == "hammer" and dx != 0:
		_select(clampi(_sel + dx, 0, PART_X.size() - 1))


func _act(i: int) -> void:
	if stage == "pipes":
		turn_tile(i)
	elif stage == "hammer":
		hit_part(i)


# ----------------------------------------------------------------------- ① 水管
## 点一格水管：转 90°（玩家点、自动玩、测试都走这里）
func turn_tile(i: int) -> void:
	if stage != "pipes" or i < 0 or i >= GRID.size():
		return
	s["rots"][i] = posmod(int(s["rots"][i]) + 1, 4)
	var d: Dictionary = tiles[i]
	d["goal"] = float(d["goal"]) + 1.0                 # 连着点：每一下都算，转到最后一下的位置
	var goal: float = d["goal"]
	if d["tw"] is Tween and (d["tw"] as Tween).is_valid():
		(d["tw"] as Tween).kill()
	if _alive():
		var tw := _tw()
		tw.tween_method(func(v: float): d["ang"] = v, float(d["ang"]), goal, 0.22 * _k()).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		d["tw"] = tw
	else:
		d["ang"] = goal
	_sfx("tap", -4.0, randf_range(0.92, 1.06))
	story.mech_save(ID, s)
	_refresh_heat()
	if flow(s["rots"])["done"]:
		_accept = false
		_stage.emit("pipes")


## 和炉膛接上的管子温热（半亮），没接上的慢慢凉下去
func _refresh_heat(full := false) -> void:
	var lit: Dictionary = flow(s["rots"])["lit"]
	for i in tiles.size():
		var goal := (1.0 if full else 0.5) if lit.has(i) else 0.0
		_heat_to(i, goal, 0.3)


func _heat_to(i: int, goal: float, sec: float) -> void:
	var d: Dictionary = tiles[i]
	if not _alive():
		d["heat"] = goal
		return
	if absf(float(d["heat"]) - goal) < 0.01:
		return
	_tw().tween_method(func(v: float): d["heat"] = v, float(d["heat"]), goal, sec * _k()).set_trans(Tween.TRANS_SINE)


func _auto_pipes(give: bool) -> void:
	await _wait(0.5 if give else 0.2)
	while _alive():
		var i := best_tile(s["rots"])
		if i < 0:
			break
		_select(i)
		turn_tile(i)
		await _wait(0.28 if give else 0.12)


## 接通：火从进口一格一格烧到出口，喷口亮起来
func _flow_light() -> void:
	var lit: Dictionary = flow(s["rots"])["lit"]
	_sel = -1
	_sfx("pipe_clear", -3.0)
	var deep := 0
	for i in lit:
		deep = maxi(deep, int(lit[i]))
	for k in deep + 1:
		for i in lit:
			if int(lit[i]) == k:
				_heat_to(int(i), 1.0, 0.25)
		await _wait(0.09)
	if _alive():
		var tw := _tw().set_parallel(true)
		tw.tween_property(self, "_noz", 1.0, 0.6 * _k()).set_trans(Tween.TRANS_SINE)
		tw.tween_property(self, "_furn", 1.0, 0.6 * _k()).set_trans(Tween.TRANS_SINE)
		await tw.finished
	await _wait(0.4)


# ----------------------------------------------------------------------- ② 盖子
func _close_lid() -> void:
	if not _alive():
		_lid_y = LID_Y
		return
	var tw := _tw()
	tw.tween_property(self, "_lid_y", float(LID_Y), 0.85 * _k()).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	await tw.finished
	_sfx("metal_clank", -2.0)
	_puff(Vector2(LID_X + 4, LID_Y + LID_H), 3)
	_puff(Vector2(LID_X + 104, LID_Y + LID_H), 3)
	var tb := _tw()                                    # 落定弹一下
	tb.tween_property(self, "_lid_y", LID_Y - 2.0, 0.08 * _k()).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tb.tween_property(self, "_lid_y", float(LID_Y), 0.14 * _k()).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	await tb.finished
	await _wait(0.25)
	_sfx("wrench", -5.0)
	await _wait(0.45)


# ----------------------------------------------------------------------- ③ 锤子
func _show_hammer() -> void:
	_ham_goal = 0
	_ham_p = _strike_pivot(0) + Vector2(30, 6)
	if not _alive():
		return
	var tw := _tw().set_parallel(true)
	tw.tween_property(self, "_ring_a", 1.0, 0.4 * _k()).set_trans(Tween.TRANS_SINE)
	tw.tween_property(self, "_ham_a", 1.0, 0.35 * _k()).set_trans(Tween.TRANS_SINE).set_delay(0.1 * _k())
	await tw.finished


## 敲一下第 j 个零件（玩家点、自动玩、测试都走这里）：排进队，锤子到那儿落下去的那一刻才算
func hit_part(j: int) -> void:
	if stage not in ["hammer", "give"] or j < 0 or j >= parts.size():
		return
	if parts[j]["locked"]:
		_sfx("tap", -10.0, 1.3)
		return
	_queue.append(j)
	if not _swinging:
		_swing_loop()


func _swing_loop() -> void:
	_swinging = true
	while not _queue.is_empty() and _alive():
		var j: int = _queue.pop_front()
		_ham_goal = j
		var wait_n := 0
		while _ham_p.distance_to(_strike_pivot(j)) > 1.5 and wait_n < 40 and _alive():
			await board.get_tree().process_frame
			wait_n += 1
		var down := _tw()
		down.tween_property(self, "_ham_ang", STRIKE, 0.07 * _k()).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
		await down.finished
		_apply_hit(j)
		var more := not _queue.is_empty()
		var up := _tw()
		up.tween_property(self, "_ham_ang", STRIKE * 0.45 if more else 0.0, (0.06 if more else 0.18) * _k()).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
		await up.finished
	_swinging = false


func _apply_hit(j: int) -> void:
	var p: Dictionary = parts[j]
	var res := hit(p, int(need[j]))
	var top := _strike_point(j)
	match res:
		"locked":
			_sfx("tap", -10.0, 1.3)
		"hit", "full":
			_sfx("tool_tap", -2.0, 0.9 + 0.12 * int(p["hits"]))
			_sfx("metal_clank", -14.0, 1.4)
			p["settle"] = SETTLE
			p["flash"] = 1.0
			_spark(top, 1)
			var goal := SINK * int(p["hits"]) / float(need[j])
			var tw := _tw()
			tw.tween_method(func(v: float): p["bob"] = v, 1.5, 0.0, 0.12 * _k())
			_tw().tween_method(func(v: float): p["sink"] = v, float(p["sink"]), goal, 0.1 * _k()).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		"crack":
			_crack(j)


## 敲过头：零件「嘣」地弹回去，圈里的点全灭，只有这一个重来
func _crack(j: int) -> void:
	var p: Dictionary = parts[j]
	p["settle"] = 0.0
	p["shake"] = 1.0
	_sfx("repair_boing", -3.0)
	_sfx("tap", -6.0, 1.6)
	_spark(_strike_point(j), 4)
	s["fails"] = int(s["fails"]) + 1
	story.mech_save(ID, s)
	print("MECH %s crack part=%d fails=%d" % [ID, j, int(s["fails"])])
	var tw := _tw()
	tw.tween_method(func(v: float): p["sink"] = v, float(p["sink"]), 0.0, 0.12 * _k()).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	var tp := _tw()
	tp.tween_method(func(v: float): p["pop"] = v, 0.0, -7.0, 0.12 * _k()).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tp.tween_method(func(v: float): p["pop"] = v, -7.0, 0.0, 0.45 * _k()).set_trans(Tween.TRANS_BOUNCE).set_ease(Tween.EASE_OUT)
	if not _said.has("crack_1") and KIT.has_lines(step, "crack_1") and int(s["fails"]) < FAILS_GIVE:
		_said["crack_1"] = true
		_crack_line()
	if int(s["fails"]) >= FAILS_GIVE and _waiting:
		_waiting = false
		_accept = false
		_queue.clear()
		_stage.emit("give")


func _crack_line() -> void:
	_accept = false
	await _wait(0.5)
	await _lines("crack_1")
	if _waiting:
		_accept = true


func _lock(j: int) -> void:
	var p: Dictionary = parts[j]
	p["locked"] = true
	_sfx("wrench", -6.0, 1.15)
	_sfx("metal_clank", -8.0, 0.8)
	_spark(_strike_point(j), 2)
	var tw := _tw()
	tw.tween_method(func(v: float): p["sink"] = v, float(p["sink"]), 7.0, 0.16 * _k()).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_method(func(v: float): p["lock_a"] = v, 0.0, 1.0, 0.25 * _k())
	var all := true
	for q in parts:
		all = all and q["locked"]
	if all and _waiting:
		_waiting = false
		_accept = false
		_stage.emit("done")


## 剩下的自己敲完（看得见：一个一个按圈里的点数敲，停一下锁死）；auto 跑全套（auto == "full"）时先演一次敲过头
func _auto_hammer(give: bool) -> void:
	var demo_crack: bool = auto_mode and str(story.get("auto")) == "full" and not give
	for j in parts.size():
		if not _alive():
			return
		if parts[j]["locked"]:
			continue
		_ham_goal = j
		_sel = j
		await _wait(0.3 if give else 0.15)
		var n: int = int(need[j]) - int(parts[j]["hits"])
		if demo_crack and j == 0:
			n += 1
			demo_crack = false
		for k in n:
			hit_part(j)
		while _swinging and _alive():
			await board.get_tree().process_frame
		if not parts[j]["locked"] and int(parts[j]["hits"]) == 0:
			await _wait(0.4)
			for k in int(need[j]):
				hit_part(j)
			while _swinging and _alive():
				await board.get_tree().process_frame
		while not parts[j]["locked"] and _alive():
			await board.get_tree().process_frame
	await _wait(0.3)


func _finish() -> void:
	_ham_goal = -1
	if not _alive():
		return
	var tw := _tw().set_parallel(true)
	tw.tween_property(self, "_ham_a", 0.0, 0.35 * _k())
	tw.tween_property(self, "_furn", 1.4, 0.5 * _k()).set_trans(Tween.TRANS_SINE)
	tw.tween_property(self, "_noz", 1.35, 0.5 * _k()).set_trans(Tween.TRANS_SINE)
	_sfx("pipe_hiss", -6.0)
	await tw.finished
	await _wait(0.9)


# ----------------------------------------------------------------------- 每帧
func _strike_point(j: int) -> Vector2:
	return Vector2(LID_X + PART_X[j], _lid_y + PART_Y - 14 + float(parts[j]["sink"]))


## 锤子停在第 j 个零件上时握柄支点在哪：锤头中心在支点左上 (-19,-19)，举着时整把锤子在圈的上面、挡不住圈；
## 落下（转 STRIKE）以后锤头到支点 (-12,+24)，正好砸在零件帽上（零件往下进，锤子跟着低一点）
func _strike_pivot(j: int) -> Vector2:
	return Vector2(LID_X + PART_X[j] + 12, _lid_y + PART_Y - 42 + float(parts[j]["sink"]))


func _tick(dt: float) -> void:
	if story != null and story.get("ff"):
		return
	_t += dt
	if _ham_goal >= 0:
		var g := _strike_pivot(_ham_goal)
		_ham_p = _ham_p.lerp(g, 1.0 - exp(-dt * 16.0))
	for j in parts.size():
		var p: Dictionary = parts[j]
		p["flash"] = maxf(0.0, float(p["flash"]) - dt * 5.0)
		p["shake"] = maxf(0.0, float(p["shake"]) - dt * 2.5)
		if not p["locked"] and int(p["hits"]) == int(need[j]) and float(p["settle"]) > 0.0:
			p["settle"] = float(p["settle"]) - dt / _k()
			if float(p["settle"]) <= 0.0 and not _swinging_on(j):
				_lock(j)
			elif float(p["settle"]) <= 0.0:
				p["settle"] = 0.01
	for sp in _sparks:
		sp["v"] = (sp["v"] as Vector2) + Vector2(0, 160) * dt
		sp["p"] = (sp["p"] as Vector2) + (sp["v"] as Vector2) * dt
		sp["life"] = float(sp["life"]) - dt
	_sparks = _sparks.filter(func(sp): return float(sp["life"]) > 0.0)
	board.queue_redraw()


## 锤子还要落在这个零件上（队里还有它）：先别锁，让那一下算数
func _swinging_on(j: int) -> bool:
	return _queue.has(j)


func _spark(at: Vector2, n: int) -> void:
	for i in n:
		_sparks.append({"p": at + Vector2(randf_range(-2, 2), 0), "v": Vector2(randf_range(-40, 40), randf_range(-70, -35)),
			"life": randf_range(0.25, 0.45), "c": randi() % 2})


func _puff(at: Vector2, n: int) -> void:
	for i in n:
		_sparks.append({"p": at + Vector2(randf_range(-3, 3), 0), "v": Vector2(randf_range(-18, 18), randf_range(-12, -4)),
			"life": randf_range(0.2, 0.35), "c": 2})


static func _step_a(a: float) -> float:
	return floorf(clampf(a, 0.0, 1.0) * 4.0 + 0.001) / 4.0


func _draw_board(b: Control) -> void:
	var breath := 0.5 + 0.5 * sin(_t * TAU / 1.6)
	if _tex["panel"] != null:
		b.draw_texture(_tex["panel"], Vector2.ZERO)
	else:
		b.draw_rect(Rect2(Vector2.ZERO, PANEL), Color("#2a3338"))
	if _tex["furnace_glow"] != null:
		b.draw_texture(_tex["furnace_glow"], Vector2.ZERO, Color(1, 1, 1, clampf(_furn * (0.82 + 0.18 * breath), 0.0, 1.0)))
	if _noz > 0.0 and _tex["nozzle_glow"] != null:
		b.draw_texture(_tex["nozzle_glow"], Vector2.ZERO, Color(1, 1, 1, _step_a(minf(1.0, _noz) * (0.85 + 0.15 * breath))))
	# 水管
	if stage == "pipes" and _accept and _sel >= 0:
		b.draw_rect(Rect2(CAV + Vector2(_sel % COLS, _sel / COLS) * T, Vector2(T, T)), HOVER)
	for i in tiles.size():
		_draw_tile(b, i)
	# 盖子 + 零件 + 圈
	var ly := roundf(_lid_y)
	if ly > -LID_H:
		if _tex["lid"] != null:
			b.draw_texture(_tex["lid"], Vector2(LID_X, ly))
		else:
			b.draw_rect(Rect2(LID_X, ly, 108, LID_H), Color("#333c40"))
		for j in parts.size():
			_draw_part(b, j, ly)
	# 锤子
	if _ham_a > 0.0 and _tex["hammer"] != null:
		b.draw_set_transform(_ham_p.round(), _ham_ang, Vector2.ONE)
		b.draw_texture(_tex["hammer"], -HAM_PIVOT, Color(1, 1, 1, _step_a(_ham_a)))
		b.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	# 火星 / 落灰（1 像素实心）
	for sp in _sparks:
		var c: Color = HOT[4] if int(sp["c"]) == 0 else (HOT[3] if int(sp["c"]) == 1 else Color("#4a5559"))
		b.draw_rect(Rect2((sp["p"] as Vector2).round(), Vector2.ONE), c)


func _draw_tile(b: Control, i: int) -> void:
	var tex: Texture2D = _tex["pipes"]
	var d: Dictionary = tiles[i]
	var c := CAV + Vector2(i % COLS, i / COLS) * T + Vector2(T, T) * 0.5
	var kind := int(GRID[i][0])
	var ang := float(d["ang"])
	var settled := absf(ang - roundf(ang)) < 0.002
	b.draw_set_transform(c, (roundf(ang) if settled else ang) * PI * 0.5, Vector2.ONE)
	if tex != null:
		b.draw_texture_rect_region(tex, Rect2(-T * 0.5, -T * 0.5, T, T), Rect2(kind * T, 0, T, T))
		var h := _step_a(float(d["heat"]))
		if h > 0.0:
			b.draw_texture_rect_region(tex, Rect2(-T * 0.5, -T * 0.5, T, T), Rect2(kind * T, T, T, T), Color(1, 1, 1, h))
	else:
		var m := mask(kind, 0)
		var col := Color("#3d4548").lerp(HOT[2], float(d["heat"]))
		if m & E:
			b.draw_rect(Rect2(0, -5, 12, 10), col)
		if m & W:
			b.draw_rect(Rect2(-12, -5, 12, 10), col)
		if m & N:
			b.draw_rect(Rect2(-5, -12, 10, 12), col)
		b.draw_rect(Rect2(-5, -5, 10, 10), col)
	b.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


func _draw_part(b: Control, j: int, ly: float) -> void:
	var p: Dictionary = parts[j]
	var cx: float = LID_X + PART_X[j]
	var tex: Texture2D = _tex["parts"]
	var sink := roundf(float(p["sink"]))
	var y := ly + PART_Y - 15 + roundf(float(p["pop"]) + float(p["bob"]))
	if tex != null:
		var la := _step_a(float(p["lock_a"]))
		if la < 1.0:
			var hgt := maxf(1.0, 16.0 - sink)                # 往下进的那截藏进插孔
			b.draw_texture_rect_region(tex, Rect2(cx - 8, y + sink, 16, hgt), Rect2(j * 16, 0, 16, hgt), Color(1, 1, 1, 1.0 - la))
		if la > 0.0:
			b.draw_texture_rect_region(tex, Rect2(cx - 8, y, 16, 20), Rect2(j * 16, 20, 16, 20), Color(1, 1, 1, la))
	else:
		b.draw_rect(Rect2(cx - 5, y + 8 + sink, 10, 6), Color("#3d4548"))
	# 圈：底是暗盘，边是 1 像素的连续圆；点 = 2×2 实心
	if _ring_a <= 0.0:
		return
	var a := _step_a(_ring_a)
	var shake := roundf(sin(float(p["shake"]) * 30.0) * 2.0 * float(p["shake"]))
	var rc := Vector2(cx + shake, ly + RING_Y)
	var hot: bool = _accept and _sel == j and stage == "hammer" and not p["locked"]
	var edge: Color
	if p["locked"]:
		edge = HOT[3]
	elif float(p["shake"]) > 0.3:
		edge = HOT[2]
	else:
		edge = HOT[2] if hot else HOT[1]
	b.draw_texture(_disk_tex, rc - Vector2(8, 8), Color(HOLE, 0.92 * a))
	b.draw_texture(_ring_tex, rc - Vector2(8, 8), Color(edge, a))
	var n := int(need[j])
	var spots: Array = {1: [Vector2(-1, -1)], 2: [Vector2(-4, -1), Vector2(2, -1)],
		3: [Vector2(-4, 1), Vector2(2, 1), Vector2(-1, -4)],
		4: [Vector2(-4, -4), Vector2(2, -4), Vector2(-4, 2), Vector2(2, 2)]}[n]
	for k in n:
		var c: Color
		if p["locked"]:
			c = HOT[4]
		elif k < int(p["hits"]):
			c = HOT[4] if (k == int(p["hits"]) - 1 and float(p["flash"]) > 0.5) else HOT[3]
		else:
			c = Color("#2a3338")
		b.draw_rect(Rect2(rc + (spots[k] as Vector2), Vector2(2, 2)), Color(c, a))
