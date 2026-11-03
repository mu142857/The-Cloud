extends RefCounted
## 第一关小游戏 rabbit_dance：跟兔子比赛模仿舞步（本2兔改稿第 13 节；规格 docs/剧情改动/第一关新版_实现规格.md「兔子舞步」）。
##
## 怎么玩（没有计时、不会输）：
##   兔子面对晨站在林子里。每一轮兔子跳一串动作，每跳一下，它头顶就冒出一个像素箭头（← ↑ → ↓）。
##   跳完箭头变淡，轮到玩家用方向键 / WASD 照着按，按对一个亮一个，晨跟着动一下（不画新帧：只在待机帧上
##   程序弹一下 / 压一下 / 歪一下，每个键手感不一样）。三轮，3、4、5 步。
##   按错不罚：兔子耸耸肩，这一轮再跳一遍。一共错三次，剩下的兔子和晨一起慢慢跳完（自动过）。
##   跳完兔子鞠躬认输，小游戏返回；给永燃之木、兔子皮毛由剧本（ch1-story）接着做。
##
## 剧本步骤：{"do": "mechanic", "id": "rabbit_dance", "at": 兔子站的 marker, "chen_at"?: 晨站的 marker,
##   "who"?: "rabbit", "sets"?: [跳完设的 flag], "seqs"?: [["up", "left", "right"], …], "max_miss"?: 3,
##   "lines"?: {start, round_1, round_2, round_3, wrong, auto, win}}
##   at 没写：兔子在哪就在哪（没显示过就站到晨面前 64 像素）。chen_at 没写：离得太近 / 太远时晨走到兔子面前 64 像素。
##   lines 每一项是一串剧本步骤（say / anim / sfx……），都可以不写；wrong 只在第一次按错时播。
## 进度（story.mech_load）：{round, k, miss, gave_up, done}：读档回来从那一轮接着跳。
## 兔子的图：art/characters/rabbit/（tools/rabbit_art.py 生成的占位，等作者的美术来换），动作 idle / dance_left / dance_up /
##   dance_right / dance_down / shrug / bow，画的是朝右；朝左站时 ← → 两段互换，跳的方向永远和屏幕上的箭头一致。

const KIT := preload("res://scripts/river_explore_order.gd")
const ID := "rabbit_dance"
const DIRS := ["left", "up", "right", "down"]
const SEQS := [["up", "left", "right"], ["left", "down", "up", "right"], ["right", "up", "down", "left", "up"]]
const MAX_MISS := 3
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
const HINT := {"zh": "方向键 / WASD：跟着兔子跳", "en": "Arrow keys / WASD: follow the rabbit"}


# ======================================================================= 规则（纯函数）
static func seqs(step: Dictionary) -> Array:
	var v = step.get("seqs", SEQS)
	return v if v is Array and not (v as Array).is_empty() else SEQS


static func max_miss(step: Dictionary) -> int:
	return int(step.get("max_miss", MAX_MISS))


static func fresh() -> Dictionary:
	return {"round": 0, "k": 0, "miss": 0, "gave_up": false, "done": false}


static func finished(step: Dictionary, s: Dictionary) -> bool:
	return int(s["round"]) >= seqs(step).size()


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
	s["k"] = 0
	if int(s["miss"]) >= max_miss(step):
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
		if m == null or not m.listening:
			return
		var d: String = m.dir_of(e)
		if d != "":
			get_viewport().set_input_as_handled()
			m.press(d)


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
var _row: Node2D
var _arrows: Array = []
var _tex: Texture2D
var _hint: CanvasLayer
var _hint_shown := false
var _chen_tw: Tween
var _was_input := true
var _said_wrong := false


func run(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	level = lv
	world = w
	story = r
	step = st
	s = story.mech_load(ID)
	if not s.has("round"):
		s = fresh()
	await _setup()
	await _lines("start")
	var rs := seqs(step)
	while not story.ended and not finished(step, s):
		if s["gave_up"]:
			await _auto_rest()
			break
		var i := int(s["round"])
		await _lines("round_%d" % (i + 1))
		await _play_round(rs[i])
	s["done"] = true
	story.mech_save(ID, s)
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
	r.mech_save(ID, t)
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
	while not story.ended and int(s["round"]) == r0 and not s["gave_up"]:
		await _demo(seq)
		var kind: String = await _turn(seq)
		if kind in ["wrong", "give_up"]:
			_clear_row(0.35)
			await _shrug()
			if kind == "wrong" and not _said_wrong:
				_said_wrong = true
				await _lines("wrong")
			continue
		await _round_clear()


## 兔子跳一串：每跳一下头顶冒一个箭头（亮），跳完这一下变回平常
func _demo(seq: Array) -> void:
	_clear_row(0.0)
	await _wait(0.4)
	for k in seq.size():
		var d := str(seq[k])
		_rabbit_move(d)
		_add_arrow(seq.size(), k, d, ROW_LIT)
		_tap(d, -6.0)
		await _wait(STEP_SEC - 0.15)
		_set_row(k, ROW_ON)
		await _wait(0.15)
	await _wait(0.25)


## 玩家照着按：箭头全变淡，按对一个亮一个。返回 act 的 kind（ok 以外的那几种）
func _turn(seq: Array) -> String:
	for k in _arrows.size():
		_set_row(k, ROW_DIM)
	if not _hint_shown:
		_hint_shown = true
		_show_hint(true)
	while not story.ended:
		var expect := str(seq[int(s["k"])])
		var d: String = await _next_key(expect)
		var res := act(step, s, d)
		story.mech_save(ID, s)
		var kind := str(res["kind"])
		if kind in ["wrong", "give_up"]:
			_tap(d, -10.0, 0.75, SFX_MISS)
			return kind
		_show_hint(false)
		_set_row(int(res["k"]), ROW_LIT, true)
		_chen_move(d)
		_tap(d, -4.0)
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
			_rabbit_move(d)
			_chen_move(d)
			_set_row(k, ROW_LIT, true)
			_tap(d, -6.0)
			await _wait(STEP_SEC + 0.1)
		s["round"] = r + 1
		s["k"] = 0
		story.mech_save(ID, s)
		await _round_clear()


func _round_clear() -> void:
	for k in _arrows.size():
		_set_row(k, ROW_LIT)
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
	if rabbit != null and chen != null:
		if step.has("chen_at"):
			await story.run_steps([{"do": "walk", "who": "chen", "to": step["chen_at"]}])
		else:
			var dx := chen.position.x - rabbit.position.x
			if absf(dx) < 40.0 or absf(dx) > 110.0:
				var side := 1.0 if dx > 0.0 else -1.0
				await story.run_steps([{"do": "walk", "who": "chen", "to": round(rabbit.position.x + side * 64.0)}])
		await story.run_steps([{"do": "face", "who": "chen", "to": who}, {"do": "face", "who": who, "to": "chen"}])
	if chen != null:
		_was_input = chen.input_enabled
		chen.input_enabled = false
	_catch = KeyCatch.new()
	_catch.m = self
	level.add_child(_catch)
	_row = Node2D.new()
	_row.z_as_relative = false
	_row.z_index = 100
	level.add_child(_row)
	if rabbit != null:
		_row.position = Vector2(round(rabbit.position.x), round(rabbit.position.y - float(rabbit.get("head")) - AW - 6.0))
	_tex = _load_tex(ARROWS)


func _teardown() -> void:
	listening = false
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
		_hint.queue_free()
		_hint = null
	_reset_chen()
	if chen != null:
		chen.input_enabled = _was_input
	_rabbit_play("idle")


func _lines(key: String) -> void:
	var l: Dictionary = step.get("lines", {})
	if l.get(key) is Array and not (l[key] as Array).is_empty():
		await story.run_steps(l[key])


func _wait(sec: float) -> void:
	await story.get_tree().create_timer(sec * (0.25 if auto_mode else 1.0)).timeout


# ----------------------------------------------------------------------- 兔子
func _rabbit_play(n: String) -> void:
	if rabbit != null and rabbit.has_method("play"):
		rabbit.play(n, true)


## 屏幕上的方向 → 兔子那一段：图是朝右画的，朝左站（翻过来）时左右两段互换
func _rabbit_move(d: String) -> void:
	if rabbit == null:
		return
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
func _add_arrow(n: int, k: int, d: String, row: int) -> void:
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


func _clear_row(sec: float) -> void:
	var old := _arrows
	_arrows = []
	for a in old:
		var sp: Sprite2D = a
		if sec <= 0.0:
			sp.queue_free()
			continue
		var tw := sp.create_tween()
		tw.tween_method(func(v: float): sp.modulate.a = ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, sec)
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
## 第一轮轮到玩家时，屏幕下方淡淡一行怎么按；按对第一下就淡掉
func _show_hint(on: bool) -> void:
	if auto_mode:
		return
	if on and _hint == null:
		_hint = CanvasLayer.new()
		_hint.layer = 5
		level.add_child(_hint)
		var lb := Label.new()
		lb.text = story.txt(HINT) if story.has_method("txt") else str(HINT["zh"])
		lb.add_theme_font_override("font", UITheme.font())
		lb.add_theme_font_size_override("font_size", 14)
		lb.add_theme_color_override("font_color", UITheme.TEXT_DIM)
		lb.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lb.position = Vector2(0, 236)
		lb.size = Vector2(480, 16)
		lb.modulate.a = 0.0
		_hint.add_child(lb)
		var tw := lb.create_tween()
		tw.tween_method(func(v: float): lb.modulate.a = floorf(v * 4.0) / 4.0, 0.0, 1.0, 0.6)
	elif not on and _hint != null:
		var h := _hint
		_hint = null
		var lb: Label = h.get_child(0)
		var tw := lb.create_tween()
		tw.tween_method(func(v: float): lb.modulate.a = ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, 0.5)
		tw.tween_callback(h.queue_free)


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
