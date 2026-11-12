extends RefCounted
## 第一关小游戏 rabbit_dance：跟兔子比赛模仿舞步（本2兔改稿第 13 节；规格 docs/剧情改动/第一关新版_实现规格.md「兔子舞步」）。
##
## 怎么玩（没有计时、不会输）：
##   兔子面对晨站在林子里。每一轮兔子跳一串动作，每跳一下，它头顶就冒出一个像素箭头（← ↑ → ↓）。
##   跳完箭头变淡，轮到玩家用方向键 / WASD 照着按，按对一个亮一个，晨跟着动一下（不画新帧：只在待机帧上
##   程序弹一下 / 压一下 / 歪一下，每个键手感不一样）。四轮，3、4、4、5 步（11-08 作者嫌难，原来 3、4、5、6）。
##   箭头一轮比一轮少（11-08 作者）：第一轮一直有；第二轮兔子跳到一半起箭头渐渐淡没；第三、四轮完全没有，
##   要看兔子的动作记。没给的箭头玩家按对时才冒出来。同一轮同一步错超过两次，这一轮箭头重新给（辅助）。
##   按错不罚：兔子耸耸肩，这一轮再跳一遍。一共错三次，剩下的兔子和晨一起慢慢跳完（自动过）；
##   剧本写了 "retry": true 就不会自动过，一直重来（森林里两处都是这样）。
##   跳完兔子鞠躬认输，小游戏返回；给永燃之木、兔子皮毛由剧本（ch1-story）接着做。
##   11-08：玩家按对时叠加 QTE 的蓄力音，最后一轮最后一步换成释放。
##
## 剧本步骤：{"do": "mechanic", "id": "rabbit_dance", "at": 兔子站的 marker,
##   "who"?: "rabbit", "sets"?: [跳完设的 flag], "seqs"?: [["up", "left", "right"], …], "max_miss"?: 3,
##   "retry"?: false, "hide"?: ["show", "fade", "hidden", "hidden"], "speed"?: [1.4, 1.4, [0.8, 0.8, 1.5, 1.5, 1.0], 1]（见 step_sec）,
##   "quit_ok"?: false, "quit_scene"?: 退出后跳去的 scene,
##   "lines"?: {start, round_1, round_2, round_3, round_4, wrong, auto, win}}
##   quit_ok（11-08 作者「卡住了就出不来」，只给支线练舞）：跳的时候按 Esc，屏幕下方出「长按 Esc 退出练舞」，
##   按住 QUIT_HOLD 秒就退出（不给奖励、不设 sets，进度留着，下次从这一轮接着跳），剧本跳去 quit_scene（story_runner 的
##   quitted / quit_scene，和煮锅、来客册一样）。没写 quit_ok 的（主线比舞）Esc 照常开暂停菜单。
##   at 没写：兔子在哪就在哪（没显示过就站到晨面前 64 像素）。晨总是自己走到兔子正对面 FACE_DIST（64）像素（11-08，chen_at 不再用）。
##   lines 每一项是一串剧本步骤（say / anim / sfx……），都可以不写；wrong 只在第一次按错时播。
## 进度（story.mech_load）：{round, k, miss, gave_up, done, fails: {"轮:步": 错几次}}：读档回来从那一轮接着跳。
## 兔子的图：art/characters/rabbit/（tools/rabbit_art.py 生成的占位，等作者的美术来换），动作 idle / dance_left / dance_up /
##   dance_right / dance_down / shrug / bow，画的是朝右；朝左站时 ← → 两段互换，跳的方向永远和屏幕上的箭头一致。

const OL := preload("res://scripts/overlay_layout.gd")
const KIT := preload("res://scripts/river_explore_order.gd")
const QTE_AUDIO := preload("res://scripts/qte_audio.gd")
const ID := "rabbit_dance"
const DIRS := ["left", "up", "right", "down"]
## 11-08 作者「兔子这一条线太难了，主线 3 4 4 5 就可以」（原来 3、4、5、6）
const SEQS := [["up", "left", "right"], ["left", "down", "up", "right"], ["right", "up", "down", "left"],
		["down", "right", "up", "left", "up"]]
const MAX_MISS := 3
const FACE_DIST := 64.0                 # 跳舞时晨和兔子隔多远（脚底中心到中心）
## 每一轮箭头怎么给（11-08 作者）：第一轮 show 一直有箭头；第二轮 fade 兔子跳到一半以后箭头渐渐淡没；
## 第三、四轮 hidden 完全不给，看兔子自己记。没给出的箭头在玩家按对的时候才冒出来（亮）。
## 剧本可以用 "hide": ["show", "fade", "hidden", …] 一轮一轮指定；没写的轮按下面这个默认。
const MODES := ["show", "fade", "hidden"]
## 辅助（11-08 作者）：同一轮的同一步按错超过 ASSIST_AFTER 次，这一轮剩下的示范和跟跳都把箭头重新给出来
const ASSIST_AFTER := 2
const STEP_SEC := 0.75                  # 兔子每一步：动作 0.6 秒（6 帧 × 100ms）+ 停一下
const ARROWS := "res://art/characters/rabbit/arrows.png"
const AW := 13                          # 箭头一格
const GAP := 15                         # 箭头之间（中心到中心）
const COL := {"up": 0, "right": 1, "down": 2, "left": 3}
const ROW_DIM := 0                      # 淡：等着玩家按
const ROW_ON := 1                       # 平常：兔子跳过的
const ROW_LIT := 2                      # 亮：正在跳 / 刚按对
const SFX := "res://audio/sfx/tap.wav"
const SFX_MISS := "res://audio/sfx/pat.wav"
const SFX_ROUND := "res://audio/sfx/bell_soft.wav"
const PITCH := {"left": 1.0, "down": 0.891, "right": 1.122, "up": 1.335}     # 每个键一个音：do re mi fa 那样排开
const HINT := {"zh": "方向键 / WASD：跟着兔子跳", "en": "Arrow keys / WASD: follow the rabbit", "fr": "Flèches / WASD : imiter le lapin"}
const HINT_LAYER := 15
const QUIT_HOLD := 1.0                  # 长按 Esc 多久算退出
const QUIT_SHOW := 2.5                  # 松开以后「长按 Esc 退出」那行还留多久
const QUIT_HINT := {"zh": "长按 Esc 退出练舞", "en": "Hold Esc to leave practice", "fr": "Maintenir Échap pour quitter"}
const QUIT_BAR_W := 64.0
const QUIT_BAND := 26.0                 # 下面电影黑边的高度（level_forest.BAR_H）：提示放在它上面，不被压住


# ======================================================================= 规则（纯函数）
static func seqs(step: Dictionary) -> Array:
	var v = step.get("seqs", SEQS)
	return v if v is Array and not (v as Array).is_empty() else SEQS


## 第 i 轮第 k 下兔子示范用几秒（11-08 作者：练舞支线「速度更快的 4 4，带有变速的 5，正常的 6」）。
## 剧本 "speed": [每轮一项]，一项是数（这一轮整体快几倍，1.4 = 快 40%）或一串数（每一下各自的倍数 = 变速）；
## 没写 / 不够长 = 1（正常）。只管兔子示范的节奏，玩家跟跳还是不计时
static func step_sec(step: Dictionary, i: int, k: int) -> float:
	var sp = step.get("speed")
	var m := 1.0
	if sp is Array and i < (sp as Array).size():
		var v = sp[i]
		if v is Array:
			if not (v as Array).is_empty():
				m = float(v[mini(k, (v as Array).size() - 1)])
		elif v is float or v is int:
			m = float(v)
	return STEP_SEC / maxf(m, 0.2)


static func max_miss(step: Dictionary) -> int:
	return int(step.get("max_miss", MAX_MISS))


static func fresh() -> Dictionary:
	return {"round": 0, "k": 0, "miss": 0, "gave_up": false, "done": false, "fails": {}}


## done 也算跳完：11-08 以前的存档只有三轮，跳完存的 round = 3，现在默认四轮，不能让它回来再跳第四轮
static func finished(step: Dictionary, s: Dictionary) -> bool:
	return bool(s.get("done", false)) or int(s["round"]) >= seqs(step).size()


## 第 i 轮（从 0 数）箭头怎么给：show / fade / hidden
static func round_mode(step: Dictionary, i: int) -> String:
	var h = step.get("hide")
	if h is Array and i < (h as Array).size() and str(h[i]) in MODES:
		return str(h[i])
	return str(MODES[mini(i, MODES.size() - 1)])


## 这一轮有没有哪一步错了超过 ASSIST_AFTER 次（是 → 箭头重新给出来）
static func assisted(s: Dictionary) -> bool:
	var f = s.get("fails", {})
	if not f is Dictionary:
		return false
	var pre := "%d:" % int(s["round"])
	for key in f:
		if str(key).begins_with(pre) and int(f[key]) > ASSIST_AFTER:
			return true
	return false


## 玩家按了一个方向。返回 {kind, k}：ok（按对，接着按）/ round（这一轮按完）/ done（全部按完）/
## wrong（按错，这一轮重来）/ give_up（错满 max_miss 次，剩下的自动过）；k = 按对的是第几个
static func act(step: Dictionary, s: Dictionary, dir: String) -> Dictionary:
	if finished(step, s) or s["gave_up"]:
		return {"kind": "done", "k": -1}
	var seq: Array = seqs(step)[int(s["round"])]
	var k := int(s["k"])
	if dir == str(seq[k]):
		s["k"] = k + 1
		if int(s["k"]) < seq.size():
			return {"kind": "ok", "k": k}
		s["round"] = int(s["round"]) + 1
		s["k"] = 0
		return {"kind": "done" if finished(step, s) else "round", "k": k}
	s["miss"] = int(s["miss"]) + 1
	if not s.get("fails") is Dictionary:
		s["fails"] = {}
	var key := "%d:%d" % [int(s["round"]), k]               # 第几轮第几步错的（字符串键：存档走 JSON）
	s["fails"][key] = int(s["fails"].get(key, 0)) + 1
	s["k"] = 0
	if not step.get("retry", false) and int(s["miss"]) >= max_miss(step):
		s["gave_up"] = true
		return {"kind": "give_up", "k": -1}
	return {"kind": "wrong", "k": -1}


## 键 → 方向（不是方向键 = ""）。方向键按键名，WASD 按键位（换了键盘布局也在同一个位置）
static func dir_of(e: InputEvent) -> String:
	if e is InputEventKey:
		var ek := e as InputEventKey
		if not ek.pressed or ek.echo:
			return ""
		match ek.keycode:
			KEY_LEFT:
				return "left"
			KEY_UP:
				return "up"
			KEY_RIGHT:
				return "right"
			KEY_DOWN:
				return "down"
		match ek.physical_keycode:
			KEY_A:
				return "left"
			KEY_W:
				return "up"
			KEY_D:
				return "right"
			KEY_S:
				return "down"
		return ""
	for d in DIRS:
		if e.is_action_pressed("ui_" + d):           # 手柄十字键
			return d
	return ""


## 收键的小节点（小游戏本身是 RefCounted，收不到输入）
class KeyCatch extends Node:
	var m                                # 小游戏实例

	func _input(e: InputEvent) -> void:
		if m == null:
			return
		if e is InputEventKey and (e as InputEventKey).keycode == KEY_ESCAPE and m.can_quit() and not m.panels_open():
			get_viewport().set_input_as_handled()        # 能退的（练舞）：Esc 归这里，不开暂停菜单
			if not e.is_echo():
				m.esc(e.is_pressed())
			return
		if not m.listening:
			return
		var d: String = m.dir_of(e)
		if d != "":
			get_viewport().set_input_as_handled()
			m.press(d)

	func _process(dt: float) -> void:
		if m != null:
			m.quit_tick(dt)


# ======================================================================= 演出
signal pressed(dir: String)

var auto_mode := false
var tried := {}
var listening := false
var story: Node
var world: Node2D
var level: Node2D
var step: Dictionary
var s: Dictionary
var rabbit: Node2D
var chen: Node2D
var _keys: Array = []                    # 自动玩 / 测试：先按这几个，按完了按对的
var _catch: Node
var _qte_audio: QTE_AUDIO
var _row: Node2D
var _arrows: Array = []
var _tex: Texture2D
var _hint: CanvasLayer
var _chen_tw: Tween
var _was_input := true
var _said_wrong := false
var quitted := false                     # 玩家长按 Esc 退出了（story_runner 看这个，跳去 quit_scene）
var _qa: Node
var _active := false                     # 摆好人、开跳了（这之后才能退）
var _quit_held := false
var _quit_t := 0.0
var _quit_show := 0.0
var _quit_layer: CanvasLayer
var _quit_bar: ColorRect


func run(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	level = lv
	world = w
	story = r
	step = st
	s = story.mech_load(str(step.get("save_key", ID)))
	if not s.has("round"):
		s = fresh()
	await _setup()
	_active = true
	await _lines("start")
	_show_hint(true)                                  # 整段舞都在，跳完才收（11-05 作者：箭头上面那行字）
	var rs := seqs(step)
	while not story.ended and not finished(step, s) and not quitted:
		if s["gave_up"]:
			await _auto_rest()
			break
		var i := int(s["round"])
		await _lines("round_%d" % (i + 1))
		if quitted:
			break
		await _play_round(rs[i])
	if quitted:
		await _quit_out()
		return
	s["done"] = true
	story.mech_save(str(step.get("save_key", ID)), s)
	_set_flags(step)
	await _finish()
	print("MECH %s done miss=%d gave_up=%s" % [ID, int(s["miss"]), str(s["gave_up"])])


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	_keys = (st.get("auto_keys", []) as Array).duplicate()
	if _keys.is_empty() and r.auto == "full":
		# 全自动回归：第一轮先按错一次，走一遍「耸肩、再跳一遍」
		var first := str(seqs(st)[0][0])
		_keys = ["down" if first != "down" else "up"]
	await run(lv, w, r, st)


## 跳节拍：直接算赢
func ff(r: Node, st: Dictionary) -> void:
	var t := fresh()
	t["round"] = seqs(st).size()
	t["done"] = true
	r.mech_save(str(st.get("save_key", ID)), t)
	_set_flags(st)


static func _set_flags(st: Dictionary) -> void:
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))


func press(d: String) -> void:
	if listening:
		pressed.emit(d)


## 一轮：兔子跳 → 玩家照着按；按错兔子耸肩再跳一遍；错满了交给 _auto_rest
func _play_round(seq: Array) -> void:
	var r0 := int(s["round"])
	while not story.ended and int(s["round"]) == r0 and not s["gave_up"] and not quitted:
		var mode := "show" if assisted(s) else round_mode(step, r0)
		if mode != round_mode(step, r0):
			print("RABBIT_ASSIST round=%d fails=%s" % [r0 + 1, str(s.get("fails", {}))])
		await _demo(seq, mode)
		if quitted:
			return
		var kind: String = await _turn(seq)
		if kind == "quit":
			return
		if kind in ["wrong", "give_up"]:
			_clear_row(0.35)
			await _shrug()
			if kind == "wrong" and not _said_wrong:
				_said_wrong = true
				await _lines("wrong")
			continue
		await _round_clear()


## 兔子跳一串：每跳一下头顶冒一个箭头（亮），跳完这一下变回平常。
## mode：show 箭头都给；hidden 一个都不给；
## fade 每个箭头照样完整冒出来，但跳到一半（第 ceil(n/2) 下）起，前面的慢慢淡没，后面每冒一个亮一下也跟着淡没，
## 示范跳完一排都看不见了（11-08 作者第二次：「还是完整的呈现出来，但是就渐渐消失了」）。
## 不给 / 淡没的箭头也占着位置（透明），玩家按对时 _reveal 冒出来。
func _demo(seq: Array, mode := "show") -> void:
	_clear_row(0.0)
	await _wait(0.4)
	var half := ceili(seq.size() / 2.0)
	var r0 := int(s["round"])
	for k in seq.size():
		if quitted:
			_rabbit_rate(1.0)
			return
		var d := str(seq[k])
		var sec := step_sec(step, r0, k)
		var f := sec / STEP_SEC                      # 这一下比正常快 / 慢多少：动作帧、淡没跟着一起缩放
		_rabbit_move(d, f)
		if mode == "fade" and k == half:
			_fade_row(0.0, sec * 1.6)                # 前半段的先开始淡（这一下的箭头还没加，不算在里面）
		_add_arrow(seq.size(), k, d, ROW_LIT, mode != "hidden")
		if mode == "fade" and k >= half:
			_fade_row(0.35 * f, 0.6 * f)             # 这一下的：完整亮一下再淡，下一下来之前差不多没了
		_tap(d, -6.0)
		await _wait(sec * 0.8)
		_set_row(k, ROW_ON)
		await _wait(sec * 0.2)
	_rabbit_rate(1.0)
	await _wait(0.25)


## 玩家照着按：箭头全变淡，按对一个亮一个。返回 act 的 kind（ok 以外的那几种）
func _turn(seq: Array) -> String:
	for k in _arrows.size():
		_set_row(k, ROW_DIM)
	var last_round := int(s["round"]) == seqs(step).size() - 1
	var charge_steps := seq.size() - (1 if last_round else 0)
	while not story.ended:
		var expect := str(seq[int(s["k"])])
		var d: String = await _next_key(expect)
		if quitted:
			_qte_audio.stop()
			return "quit"
		var res := act(step, s, d)
		story.mech_save(str(step.get("save_key", ID)), s)
		var kind := str(res["kind"])
		if kind in ["wrong", "give_up"]:
			_qte_audio.stop()
			_tap(d, -10.0, 0.75, SFX_MISS)
			return kind
		_set_row(int(res["k"]), ROW_LIT, true)
		_reveal(int(res["k"]))
		_chen_move(d)
		_tap(d, -4.0)
		if kind == "done":
			_qte_audio.play_release()
		else:
			_qte_audio.play_step(int(res["k"]) + 1, charge_steps)
		if kind != "ok":
			await _wait(0.45)
			return kind
	return "done"


func _next_key(expect: String) -> String:
	if auto_mode:
		await _wait(0.3)
		return str(_keys.pop_front()) if not _keys.is_empty() else expect
	listening = true
	var d: String = await pressed
	listening = false
	return d


## 错满了：剩下的兔子和晨一起慢慢跳完（箭头一个个亮），不再要玩家按
func _auto_rest() -> void:
	_show_hint(false)                                 # 接下来不用按了，「方向键」那行字收起来
	await _lines("auto")
	var rs := seqs(step)
	for r in range(int(s["round"]), rs.size()):
		var seq: Array = rs[r]
		_clear_row(0.0)
		for k in seq.size():
			_add_arrow(seq.size(), k, str(seq[k]), ROW_DIM)
		await _wait(0.5)
		for k in seq.size():
			var d := str(seq[k])
			_rabbit_move(d, step_sec(step, r, k) / STEP_SEC)
			_chen_move(d)
			_set_row(k, ROW_LIT, true)
			_tap(d, -6.0)
			await _wait(step_sec(step, r, k) + 0.1)
		_rabbit_rate(1.0)
		s["round"] = r + 1
		s["k"] = 0
		story.mech_save(str(step.get("save_key", ID)), s)
		await _round_clear()


func _round_clear() -> void:
	for k in _arrows.size():
		_set_row(k, ROW_LIT)
	if not finished(step, s) or s["gave_up"] or _qte_audio.stream == null:
		_tap("up", -14.0, 1.0, SFX_ROUND)
	await _wait(0.35)
	_clear_row(0.45)
	await _wait(0.6)


func _shrug() -> void:
	_rabbit_play("shrug")
	await _wait(1.0)


func _finish() -> void:
	_show_hint(false)
	_clear_row(0.4)
	_rabbit_play("bow")
	await _wait(1.2)
	await _lines("win")
	_teardown()


# ----------------------------------------------------------------------- 长按 Esc 退出（只给 quit_ok 的支线练舞）
## level_forest._esc_is_back 也问这个：true 时 Esc 不开暂停菜单
func can_quit() -> bool:
	return bool(step.get("quit_ok", false)) and _active and not quitted and story != null and not story.ended


## 设置 / 背包开着的时候 Esc 归它们（关面板）
func panels_open() -> bool:
	for n in ["_settings", "_bag"]:
		var pnl = level.get(n) if level != null else null
		if pnl is CanvasItem and (pnl as CanvasItem).visible:
			return true
	return false


func esc(down: bool) -> void:
	_quit_held = down
	if down:
		_quit_show = QUIT_SHOW
		_quit_ui(true)
	else:
		_quit_t = 0.0


func quit_tick(dt: float) -> void:
	if quitted:
		if story != null and story.dlg.is_open():
			story.dlg.confirm()                       # 退的时候兔子正说着话：快进掉，run 才走得到退出
		return
	if _quit_layer == null:
		return
	if _quit_held and can_quit():
		_quit_t += dt
		_quit_show = QUIT_SHOW
		if _quit_t >= QUIT_HOLD:
			_do_quit()
	else:
		_quit_t = 0.0
		_quit_show -= dt
		if _quit_show <= 0.0:
			_quit_ui(false)
	if _quit_bar != null:
		var w := roundf(QUIT_BAR_W * clampf(_quit_t / QUIT_HOLD, 0.0, 1.0))
		_quit_bar.size.x = w
		_quit_bar.visible = w > 0.0


func _do_quit() -> void:
	quitted = true
	_quit_held = false
	s["k"] = 0                                        # 这一轮从头；轮数留着，下次接着跳
	story.mech_save(str(step.get("save_key", ID)), s)
	print("MECH %s quit round=%d" % [ID, int(s["round"]) + 1])
	if listening:
		listening = false
		pressed.emit("")                              # 正等着玩家按键：放出来


func _quit_out() -> void:
	_show_hint(false)
	_clear_row(0.3)
	_rabbit_play("idle")
	await _wait(0.4)
	_teardown()


## 屏幕下方一行「长按 Esc 退出练舞」+ 按住时下面一条慢慢填满
func _quit_ui(on: bool) -> void:
	if on and _quit_layer == null:
		_quit_layer = CanvasLayer.new()
		_quit_layer.layer = HINT_LAYER
		level.add_child(_quit_layer)
		var root := Control.new()
		root.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.modulate.a = 0.0
		_quit_layer.add_child(root)
		var lb := Label.new()
		lb.text = story.txt(QUIT_HINT) if story.has_method("txt") else str(QUIT_HINT["zh"])
		lb.position = Vector2(0, OL.SCREEN.y - QUIT_BAND - 28.0)     # 电影黑边（下面 26 高，UI 层 20）上面
		lb.size = Vector2(OL.SCREEN.x, OL.HINT_H)
		lb.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lb.mouse_filter = Control.MOUSE_FILTER_IGNORE
		lb.add_theme_font_override("font", UITheme.font())
		lb.add_theme_font_size_override("font_size", 14)
		lb.add_theme_color_override("font_color", UITheme.TEXT)
		lb.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))
		root.add_child(lb)
		var x0 := roundf((OL.SCREEN.x - QUIT_BAR_W) / 2.0)
		var y0 := OL.SCREEN.y - QUIT_BAND - 8.0
		var bg := ColorRect.new()                     # 槽：淡
		bg.color = Color(UITheme.TEXT, 0.25)
		bg.position = Vector2(x0, y0)
		bg.size = Vector2(QUIT_BAR_W, 2)
		bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(bg)
		_quit_bar = ColorRect.new()
		_quit_bar.color = UITheme.TEXT
		_quit_bar.position = Vector2(x0, y0)
		_quit_bar.size = Vector2(0, 2)
		_quit_bar.visible = false
		_quit_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(_quit_bar)
		var tw := root.create_tween()
		tw.tween_method(func(v: float): root.modulate.a = floorf(v * 4.0) / 4.0, 0.0, 1.0, 0.25)
	elif not on and _quit_layer != null:
		var ly := _quit_layer
		_quit_layer = null
		_quit_bar = null
		var root: Control = ly.get_child(0)
		var tw := root.create_tween()
		tw.tween_method(func(v: float): root.modulate.a = ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, 0.3)
		tw.tween_callback(ly.queue_free)


# ----------------------------------------------------------------------- 摆人
func _setup() -> void:
	chen = story.chen
	var who := str(step.get("who", "rabbit"))
	if "_npc_names" in story:
		story._npc_names[who] = true             # 剧本别处没提过兔子也能建出来
	rabbit = story.npc(who)
	if rabbit == null:
		push_warning("rabbit_dance：找不到 %s" % who)
	elif step.has("at"):
		if not rabbit.visible:
			await story.run_steps([{"do": "show", "who": who, "at": step["at"], "fade": 0.6}])
			await _wait(0.6)
	elif not rabbit.visible and chen != null:
		rabbit.position = Vector2(round(chen.position.x + 64.0 * chen.facing), chen.position.y)
		await story.run_steps([{"do": "show", "who": who, "fade": 0.6}])
		await _wait(0.6)
	if auto_mode and rabbit != null:
		_qa_stage("before")                          # 开跳前（= 前面那段对话时）谁站在哪
	if rabbit != null and chen != null:
		# 11-08 作者：不管哪一场（比舞 / 练舞），开跳前晨都自己走到兔子正对面、隔固定的 FACE_DIST。
		# 站在晨原来那一侧；那一侧走不到（墙外）就换另一侧。剧本的 chen_at 不再用。
		var dx := chen.position.x - rabbit.position.x
		var side := 1.0 if dx > 0.0 else -1.0
		var tx := roundf(rabbit.position.x + side * FACE_DIST)
		if story.get("world") != null and story.world.has_method("walls"):
			var w: Vector2 = story.world.walls(chen.position.x)
			if tx < w.x + 2.0 or tx > w.y - 2.0:
				tx = roundf(rabbit.position.x - side * FACE_DIST)
		if absf(chen.position.x - tx) > 1.0:
			await story.run_steps([{"do": "walk", "who": "chen", "to": tx}])
		await story.run_steps([{"do": "face", "who": "chen", "to": who}, {"do": "face", "who": who, "to": "chen"}])
		await _clear_stage(who)
		if auto_mode:
			_qa_stage("after")
	if story.get("dlg") != null:
		story.dlg.keep_clear = keep_rect             # 跳舞时说话的框不落到兔子和箭头上
	if chen != null:
		_was_input = chen.input_enabled
		chen.input_enabled = false
	_catch = KeyCatch.new()
	_catch.m = self
	level.add_child(_catch)
	_qte_audio = QTE_AUDIO.new()
	_qte_audio.bus = "SFX" if AudioServer.get_bus_index("SFX") >= 0 else "Master"
	_qte_audio.gain_db = -12.0 + float(step.get("sfx_db", 0.0))
	_catch.add_child(_qte_audio)
	_row = Node2D.new()
	_row.z_as_relative = false
	_row.z_index = 100
	level.add_child(_row)
	_row.add_child(OL.BusyFade.new(story))           # 头顶那排：说话的框就在头顶，说话的时候淡掉
	if rabbit != null:
		_row.position = Vector2(round(rabbit.position.x), round(rabbit.position.y - float(rabbit.get("head")) - AW - 6.0))
	_tex = _load_tex(ARROWS)
	if auto_mode:
		_qa = RabbitQA.new()
		_qa.m = self
		_catch.add_child(_qa)
		await _qa.probe_box()


func _teardown() -> void:
	listening = false
	if story != null and story.get("dlg") != null:
		story.dlg.keep_clear = Callable()
	if _qa != null:
		_qa.summary()
		_qa = null
	_active = false
	_quit_held = false
	if _quit_layer != null:
		_quit_layer.queue_free()
		_quit_layer = null
		_quit_bar = null
	if _catch != null:
		_catch.queue_free()
		_catch = null
	if _row != null:
		var row := _row
		var tw := row.create_tween()
		tw.tween_interval(0.5)
		tw.tween_callback(row.queue_free)
		_row = null
	if _hint != null:
		OL.hud(story, false)
		_hint.queue_free()
		_hint = null
	_reset_chen()
	if chen != null:
		chen.input_enabled = _was_input
	_rabbit_rate(1.0)
	_rabbit_play("idle")


func _lines(key: String) -> void:
	var l: Dictionary = step.get("lines", {})
	if l.get(key) is Array and not (l[key] as Array).is_empty():
		await story.run_steps(l[key])


func _wait(sec: float) -> void:
	await story.get_tree().create_timer(sec * (0.25 if auto_mode else 1.0), false).timeout


# ----------------------------------------------------------------------- 兔子
func _rabbit_rate(r: float) -> void:
	if rabbit != null and "anim_rate" in rabbit:
		rabbit.set("anim_rate", r)


func _rabbit_play(n: String) -> void:
	if rabbit != null and rabbit.has_method("play"):
		rabbit.play(n, true)


## 屏幕上的方向 → 兔子那一段：图是朝右画的，朝左站（翻过来）时左右两段互换
## f = 这一下用的时间 / 正常（STEP_SEC）：快的时候动作帧跟着播快，不会每一下都被下一下截断
func _rabbit_move(d: String, f := 1.0) -> void:
	if rabbit == null:
		return
	_rabbit_rate(1.0 / maxf(f, 0.1))
	var a := d
	if int(rabbit.get("facing")) < 0 and d in ["left", "right"]:
		a = "right" if d == "left" else "left"
	_rabbit_play("dance_" + a)


# ----------------------------------------------------------------------- 晨：不画新帧，只动待机帧的位置 / 缩放 / 歪斜
## 以脚底为原点（chen.spr 的原点就是脚底）：
##   ↑ 轻轻一跳（抛物线起落，落地压一下）  ↓ 往下一蹲（压扁再弹回）
##   ← → 往那边歪一下身子、挪一像素（脚不动，头带过去，缓起缓停）
## 动画帧照常 100ms 一帧，不碰。
func _chen_move(d: String) -> void:
	if chen == null or not ("spr" in chen) or chen.spr == null:
		return
	var sp: Node2D = chen.spr
	_reset_chen()
	var t := 0.25 if auto_mode else 1.0
	var tw := sp.create_tween()
	_chen_tw = tw
	match d:
		"up":
			tw.tween_method(func(k: float): sp.position.y = -round(24.0 * k * (1.0 - k)), 0.0, 1.0, 0.34 * t)
			tw.tween_property(sp, "scale", Vector2(1.06, 0.93), 0.06 * t).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
			tw.tween_property(sp, "scale", Vector2.ONE, 0.16 * t).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		"down":
			tw.tween_method(func(k: float):
				var f := 0.5 - 0.5 * cos(TAU * k)
				sp.scale = Vector2(1.0 + 0.08 * f, 1.0 - 0.12 * f), 0.0, 1.0, 0.42 * t)
		"left", "right":
			var sg := -1.0 if d == "left" else 1.0
			tw.tween_method(func(k: float):
				var f := 0.5 - 0.5 * cos(TAU * k)
				sp.skew = 0.13 * sg * f
				sp.position.x = round(1.5 * sg * f), 0.0, 1.0, 0.44 * t)
	tw.tween_callback(_reset_chen)


func _reset_chen() -> void:
	if _chen_tw != null and _chen_tw.is_valid():
		_chen_tw.kill()
	_chen_tw = null
	if chen != null and "spr" in chen and chen.spr != null:
		chen.spr.position = Vector2.ZERO
		chen.spr.scale = Vector2.ONE
		chen.spr.skew = 0.0


# ----------------------------------------------------------------------- 箭头（兔子头顶一排）
func _add_arrow(n: int, k: int, d: String, row: int, vis := true) -> void:
	if _row == null:
		return
	var a := Sprite2D.new()
	a.centered = false
	a.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	if _tex != null:
		var at := AtlasTexture.new()
		at.atlas = _tex
		at.region = Rect2(COL[d] * AW, row * AW, AW, AW)
		a.texture = at
	a.set_meta("dir", d)
	var x0 := -roundf((float(n - 1) * GAP + AW) / 2.0)
	var home := Vector2(x0 + k * GAP, 0.0)
	a.position = home + Vector2(0, 3)
	a.modulate.a = 0.0
	_row.add_child(a)
	_arrows.append(a)
	if not vis:                                      # 不给的箭头：透明占位，按对时 _reveal
		a.position = home
		a.set_meta("hidden", true)
		return
	# 冒出来：4 档淡入 + 往上浮 3 像素停住（缓停）
	var tw := a.create_tween().set_parallel(true)
	tw.tween_method(func(v: float): a.modulate.a = floorf(v * 4.0) / 4.0, 0.0, 1.0, 0.2)
	tw.tween_method(func(v: float): a.position.y = round(3.0 * (1.0 - v)), 0.0, 1.0, 0.28).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)


## 换一档颜色；bounce = 按对了，往上跳 2 像素再落回
func _set_row(k: int, row: int, bounce := false) -> void:
	if k < 0 or k >= _arrows.size():
		return
	var a: Sprite2D = _arrows[k]
	if a.texture is AtlasTexture:
		(a.texture as AtlasTexture).region = Rect2(COL[str(a.get_meta("dir"))] * AW, row * AW, AW, AW)
	if bounce:
		var tw := a.create_tween()
		tw.tween_method(func(v: float): a.position.y = -round(8.0 * v * (1.0 - v)), 0.0, 1.0, 0.24)


## 没给出的箭头（_demo 里透明占位的）按对时冒出来：4 档淡入，跟 _add_arrow 一样
func _reveal(k: int) -> void:
	if k < 0 or k >= _arrows.size():
		return
	var a: Sprite2D = _arrows[k]
	if not a.has_meta("hidden"):
		return
	a.remove_meta("hidden")
	if a.has_meta("tw"):                             # 自动玩时等待缩短，淡没可能还没走完
		var old: Tween = a.get_meta("tw")
		if old != null and old.is_valid():
			old.kill()
		a.remove_meta("tw")
	var tw := a.create_tween()
	tw.tween_method(func(v: float): a.modulate.a = floorf(v * 4.0) / 4.0, 0.0, 1.0, 0.16)


## fade 轮：还看得见的箭头停 hold 秒后 4 档淡没（不删，留着位置，按对时再冒出来）
func _fade_row(hold: float, sec: float) -> void:
	for a in _arrows:
		var sp: Sprite2D = a
		if sp.has_meta("hidden"):
			continue
		sp.set_meta("hidden", true)
		var tw := sp.create_tween()
		tw.tween_interval(hold)                      # 刚冒出来的那个先完整亮一下
		tw.tween_method(func(v: float): sp.modulate.a = ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, sec)
		sp.set_meta("tw", tw)


func _clear_row(sec: float) -> void:
	var old := _arrows
	_arrows = []
	for a in old:
		var sp: Sprite2D = a
		if sec <= 0.0:
			sp.queue_free()
			continue
		var a0 := sp.modulate.a                      # 没冒出来的那几个本来就是透明的，别淡出时闪一下
		var tw := sp.create_tween()
		tw.tween_method(func(v: float): sp.modulate.a = a0 * ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, sec)
		tw.tween_callback(sp.queue_free)


static func _load_tex(p: String) -> Texture2D:
	if ResourceLoader.exists(p):
		return load(p)
	if FileAccess.file_exists(p):               # 新图编辑器还没导入：直接读 png
		var img := Image.load_from_file(ProjectSettings.globalize_path(p))
		if img != null and not img.is_empty():
			return ImageTexture.create_from_image(img)
	return null


# ----------------------------------------------------------------------- 提示、声音
## 怎么按的那行字：画面上方，整段舞都在（对话显示时 HintLabel 自己让开）。
## 11-04 / 11-05 作者两次说「上面的字」：这行原来在 y16、CanvasLayer 5，
## 黑边（高 26，在 UI 层 20）放下来正好把它压掉大半；按对第一下又收掉，后面几轮就什么字都没有了。
## 现在放在黑边下面（OL.top_hint_y），层在暗角（10）和 UI（20）之间。
func _show_hint(on: bool) -> void:
	if on and _hint == null:
		OL.hud(story, true)                           # 左上角目标让开（最上面一行给按键提示）
		_hint = CanvasLayer.new()
		_hint.layer = HINT_LAYER
		level.add_child(_hint)
		var lb := OL.HintLabel.new(story, "", OL.top_hint_y(story))
		lb.text = story.txt(HINT) if story.has_method("txt") else str(HINT["zh"])
		lb.add_theme_color_override("font_color", UITheme.TEXT)
		lb.modulate.a = 0.0
		_hint.add_child(lb)
		var tw := lb.create_tween()
		tw.tween_method(func(v: float): lb.modulate.a = floorf(v * 4.0) / 4.0, 0.0, 1.0, 0.6)
		if auto_mode:
			tw.tween_callback(_print_hint.bind(lb))
	elif not on and _hint != null:
		OL.hud(story, false)
		var h := _hint
		_hint = null
		var lb: Label = h.get_child(0)
		var tw := lb.create_tween()
		tw.tween_method(func(v: float): lb.modulate.a = ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, 0.5)
		tw.tween_callback(h.queue_free)


## 跑 --story_auto 时打印这行字的位置，确认它没被黑边压住
func _print_hint(lb: Label) -> void:
	var bars = level.get("_bars")
	var bar_bottom := -1.0
	if bars is Array and not (bars as Array).is_empty():
		var b: Control = bars[0]
		bar_bottom = b.position.y + b.size.y if b.visible else 0.0
	var top := lb.position.y
	print("RABBIT_HINT text=\"%s\" y=%d..%d layer=%d alpha=%.2f visible=%s bar_bottom=%d covered=%s" % [
		lb.text, int(top), int(top + lb.size.y), (lb.get_parent() as CanvasLayer).layer, lb.modulate.a,
		str(lb.is_visible_in_tree()), int(bar_bottom), str(top < bar_bottom)])


func _tap(d: String, db: float, pitch := -1.0, path := SFX) -> void:
	if not ResourceLoader.exists(path):
		return
	var a := AudioStreamPlayer.new()
	a.stream = load(path)
	a.bus = "SFX" if AudioServer.get_bus_index("SFX") >= 0 else "Master"
	a.volume_db = db + (float(step.get("sfx_db", 0.0)))
	a.pitch_scale = pitch if pitch > 0.0 else float(PITCH.get(d, 1.0))
	level.add_child(a)
	a.play()
	a.finished.connect(a.queue_free)


# ----------------------------------------------------------------------- --story_check
func check(story: Node, st: Dictionary) -> Array:
	var out: Array = []
	var rs = st.get("seqs", SEQS)
	if not rs is Array or (rs as Array).is_empty():
		out.append("seqs 要是一串串方向")
	else:
		for i in (rs as Array).size():
			if not rs[i] is Array or (rs[i] as Array).is_empty():
				out.append("seqs[%d] 是空的" % i)
				continue
			for d in rs[i]:
				if not str(d) in DIRS:
					out.append("seqs[%d] 里的 %s 不是 left / up / right / down" % [i, d])
	if st.has("hide"):
		if not st["hide"] is Array:
			out.append("hide 要是一串 show / fade / hidden")
		else:
			for h in st["hide"]:
				if not str(h) in MODES:
					out.append("hide 里的 %s 不是 show / fade / hidden" % h)
	if st.has("speed"):
		if not st["speed"] is Array:
			out.append("speed 要是每轮一项（数，或一串数 = 变速）")
		else:
			for v in st["speed"]:
				var vs: Array = v if v is Array else [v]
				for x in vs:
					if not (x is float or x is int) or float(x) <= 0.0:
						out.append("speed 里的 %s 要是大于 0 的数" % str(x))
	for m in ["at", "chen_at"]:
		if st.has(m) and st[m] is String and not story.world.has_marker(str(st[m])):
			out.append("%s 的 marker %s 找不到" % [m, st[m]])
	if not FileAccess.file_exists("res://art/characters/%s/%s.json" % [st.get("who", "rabbit"), st.get("who", "rabbit")]):
		out.append("兔子的图 / json 还没有")
	if not FileAccess.file_exists(ARROWS):
		out.append("箭头图 %s 还没有" % ARROWS)
	for k in st.get("lines", {}):
		out.append_array(KIT.check_steps(story, "lines.%s" % k, st["lines"][k]))
	return out


# ----------------------------------------------------------------------- 别挡兔子
## 11-08 作者「挡住兔子，跳舞就看不清」：比舞那场鹿被带到兔子身边 21 像素、晨从 hotspot 走过去也会站到兔子身上。
## 开跳前（晨已经站到 FACE_DIST）：谁的身子（不透明像素）碰到兔子或晨，就走开——在晨这一侧的站到晨身后，另一侧的退到兔子身后。
const CLEAR_GAP := 6.0
const CLEAR_WHO := ["deer", "rabbit_doe", "miluo"]

func _clear_stage(who: String) -> void:
	var side := 1.0 if chen.position.x >= rabbit.position.x else -1.0
	var zk := maxf(0.01, absf(rabbit.get_global_transform_with_canvas().get_scale().x))
	for name in CLEAR_WHO + (step.get("clear", []) as Array):
		var o: Node2D = _who(story, name)
		if o == null or o == rabbit or o == chen or not is_instance_valid(o) or not o.visible:
			continue
		var ro := body_rect(o)
		var rr := body_rect(rabbit)
		var rc := body_rect(chen)
		if ro.size.x <= 0.0 or not (ro.intersects(rr.grow(CLEAR_GAP)) or ro.intersects(rc.grow(2.0))):
			continue
		var half := ro.size.x / 2.0 / zk
		var tx: float
		var os := signf(o.position.x - rabbit.position.x)
		if os == side or os == 0.0:
			tx = chen.position.x + side * (rc.size.x / 2.0 / zk + half + CLEAR_GAP)
		else:
			tx = rabbit.position.x - side * (rr.size.x / 2.0 / zk + half + CLEAR_GAP + 2.0)
		if story.get("world") != null and story.world.has_method("walls"):
			var w: Vector2 = story.world.walls(o.position.x)
			tx = clampf(tx, w.x + 2.0, w.y - 2.0)
		await story.run_steps([{"do": "walk", "who": name, "to": roundf(tx)}, {"do": "face", "who": name, "to": who}])


## 跳舞时要一直看得见的那块（屏幕坐标）：兔子身子 + 头顶那排箭头（最长一轮的宽度）
func keep_rect() -> Rect2:
	if rabbit == null or not is_instance_valid(rabbit) or not rabbit.visible:
		return Rect2()
	var r := body_rect(rabbit)
	if _row != null and is_instance_valid(_row):
		var o := _row.get_global_transform_with_canvas().origin
		var n := 1
		for q in seqs(step):
			n = maxi(n, (q as Array).size())
		var w := float(n * (AW + 2))
		var band := Rect2(o.x - w / 2.0 - 2.0, o.y - 2.0, w + 4.0, AW + 4.0)
		r = band if r.size.x <= 0.0 else r.merge(band)
	return r


## 一个角色身上不透明像素的外框（屏幕坐标）；看不见 = Rect2()
static func body_rect(n: Node) -> Rect2:
	var out := Rect2()
	if n == null or not is_instance_valid(n) or not (n is CanvasItem) or not (n as CanvasItem).is_visible_in_tree():
		return out
	var stack: Array[Node] = [n]
	while not stack.is_empty():
		var c: Node = stack.pop_back()
		stack.append_array(c.get_children())
		if c is AnimatedSprite2D:
			var ar := _anim_rect(c as AnimatedSprite2D)
			if ar.size.x > 0.0:
				out = ar if out.size.x <= 0.0 else out.merge(ar)
			continue
		if not (c is Sprite2D):
			continue
		var sp := c as Sprite2D
		if sp.texture == null or not sp.is_visible_in_tree() or sp.self_modulate.a < 0.1 or sp.modulate.a < 0.1:
			continue
		var lr := sp.get_rect()
		var xf := sp.get_global_transform_with_canvas()
		var lo := Vector2(INF, INF)
		var hi := Vector2(-INF, -INF)
		var y := lr.position.y
		while y < lr.end.y:
			var x := lr.position.x
			while x < lr.end.x:
				if sp.is_pixel_opaque(Vector2(x + 0.5, y + 0.5)):
					for corner in [Vector2(x, y), Vector2(x + 2.0, y + 2.0)]:
						var p: Vector2 = xf * corner
						lo = lo.min(p)
						hi = hi.max(p)
				x += 2.0
			y += 2.0
		if lo.x <= hi.x:
			var rr := Rect2(lo, hi - lo)
			out = rr if out.size.x <= 0.0 else out.merge(rr)
	return out


## --story_auto 时一直看：说话的框有没有落到兔子 / 箭头上、有没有谁的身子压在兔子身上。打 RABBIT_QA，结束打 RABBIT_QA_SUMMARY
class RabbitQA extends Node:
	var m
	var frames := 0
	var box_hits := 0
	var box_seen := 0
	var overlaps := 0
	var _said := {}

	func _process(_dt: float) -> void:
		if m == null or m.rabbit == null:
			return
		frames += 1
		var kr: Rect2 = m.keep_rect()
		var box = m.story.dlg.get("_box") if m.story.get("dlg") != null else null
		if box is Control and (box as Control).is_visible_in_tree() and (box as Control).modulate.a > 0.1:
			box_seen += 1
			var br := Rect2((box as Control).position, (box as Control).size)
			if br.intersects(kr):
				box_hits += 1
				_say("box", "RABBIT_QA box_over_rabbit box=%s keep=%s" % [str(br), str(kr)])
		var rr: Rect2 = m.body_rect(m.rabbit)
		for name in ["chen"] + m.CLEAR_WHO:
			var o: Node2D = m.chen if name == "chen" else (m._who(m.story, name))
			if o == null or not is_instance_valid(o) or o == m.rabbit:
				continue
			var ro: Rect2 = m.body_rect(o)
			if ro.size.x > 0.0 and ro.intersects(rr):
				overlaps += 1
				_say("ov_" + name, "RABBIT_QA overlap %s=%s rabbit=%s" % [name, str(ro), str(rr)])

	func _say(k: String, t: String) -> void:
		if not _said.has(k):
			_said[k] = true
			print(t)

	## 框放哪：兔子说一句、晨说一句，各量一次（只在 --story_auto 里，一闪就关）
	func probe_box() -> void:
		var d = m.story.get("dlg")
		if d == null:
			return
		for who in [str(m.step.get("who", "rabbit")), "chen"]:
			d._show_line("QA", Color.WHITE, "跟着我跳，看清楚了！", m.story._anchor.bind(who), false)
			await get_tree().process_frame
			var b: Control = d.get("_box")
			var br := Rect2(b.position, b.size)
			var kr: Rect2 = m.keep_rect()
			print("RABBIT_QA box_probe who=%s box=%s keep=%s hit=%s" % [who, str(br), str(kr), str(br.intersects(kr))])
			if br.intersects(kr):
				box_hits += 1
			d.close_box()

	func summary() -> void:
		print("RABBIT_QA_SUMMARY frames=%d box_seen=%d box_hits=%d overlaps=%d" % [frames, box_seen, box_hits, overlaps])


func _qa_stage(tag: String) -> void:
	var rr := body_rect(rabbit)
	var parts: Array[String] = ["rabbit x=%d body=%d..%d" % [int(rabbit.position.x), int(rr.position.x), int(rr.end.x)]]
	for name in ["chen"] + CLEAR_WHO:
		var o: Node2D = chen if name == "chen" else (_who(story, name))
		if o == null or not is_instance_valid(o) or not o.visible:
			continue
		var ro := body_rect(o)
		parts.append("%s x=%d body=%d..%d%s" % [name, int(o.position.x), int(ro.position.x), int(ro.end.x), " OVER_RABBIT" if ro.intersects(rr) else ""])
	print("RABBIT_QA stage_%s %s" % [tag, " | ".join(parts)])


static var _img_cache := {}

## 鹿是 AnimatedSprite2D：拿当前帧的图，按 offset / centered / flip_h 量不透明像素
static func _anim_rect(a: AnimatedSprite2D) -> Rect2:
	if a.sprite_frames == null or not a.is_visible_in_tree() or a.self_modulate.a < 0.1 or a.modulate.a < 0.1:
		return Rect2()
	var tex := a.sprite_frames.get_frame_texture(a.animation, a.frame)
	if tex == null:
		return Rect2()
	var key := tex.get_instance_id()
	if not _img_cache.has(key):
		_img_cache[key] = tex.get_image()
	var img: Image = _img_cache[key]
	if img == null:
		return Rect2()
	var sz := Vector2(img.get_width(), img.get_height())
	var left := a.offset - (sz / 2.0 if a.centered else Vector2.ZERO)
	var xf := a.get_global_transform_with_canvas()
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	for iy in range(0, int(sz.y), 2):
		for ix in range(0, int(sz.x), 2):
			if img.get_pixel(ix, iy).a < 0.5:
				continue
			var lx := float(ix) if not a.flip_h else sz.x - 1.0 - float(ix)
			for corner in [left + Vector2(lx, iy), left + Vector2(lx + 2.0, iy + 2.0)]:
				var p: Vector2 = xf * corner
				lo = lo.min(p)
				hi = hi.max(p)
	return Rect2(lo, hi - lo) if lo.x <= hi.x else Rect2()


## 鹿 / 通用角色（剧本里没建过的 = null，不新建；测试里的假 story 没有这些字段也行）
static func _who(st: Object, name: String) -> Node2D:
	if name == "deer":
		return st.get("deer") as Node2D
	var d = st.get("npcs")
	return d.get(name) as Node2D if d is Dictionary else null

