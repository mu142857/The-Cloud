extends RefCounted
## 第一关支线 3「大嘴鸟」的小游戏 side_toucan（docs/剧情改动/第一关支线_设计.md；剧本 data/forest_side_b.json）。
##
## act = "catch"（默认）：接果子。大嘴鸟蹲在空地尽头的树桩上，一个一个把红果子抛过来（张嘴、抬头、抛物线），
##   玩家照常左右走（方向键 / A D，晨的走路动画照常 100ms 一帧），走到果子底下就接住：果子飞到大嘴鸟头顶那排计数里亮起来，
##   晨轻轻一跳。接到 need 个（默认 5）就算赢。没有计时、不会输：掉在地上的果子滚一下淡掉；掉满 max_miss 个（默认 4），
##   大嘴鸟改成直接往晨手里抛（晨不用动），剩下的自动接完。
## act = "huff"：只演一下「生气地把嘴合上，合了三秒才合拢」（嘴一下张到最大，再一档一档往回合，中间卡一下，最后咔一声）。
##   给剧本里「你嘴太大了，当不了妈妈」那个选项用，不碰进度。
##
## 大嘴鸟的图（美术组的，art/characters/toucan/toucan.png）一个像素都不改：小游戏期间把它原来的精灵调成全透明，
##   在同一个位置叠一张 art/forest_side/toucan_beak.png（从原图派生的张嘴帧：0 合嘴、1~3 张开、4 抛），玩完换回来。
##   它说话（剧本 say）的时候嘴一张一合。
##
## 剧本步骤：{"do": "mechanic", "id": "side_toucan", "act"?: "catch" | "huff", "who"?: "toucan", "need"?: 5,
##   "max_miss"?: 4, "chen_at"?: marker 或 x, "sets"?: [赢了设的 flag], "lines"?: {start, miss, auto, win}}
##   chen_at 没写：晨在接果子的范围里就不动，不在就走到大嘴鸟左边 80 像素。范围 = 大嘴鸟左边 150 到 30 像素。
##   lines：start（开始抛之前）、miss（第一次掉地上）、auto（掉满了，改成往手里抛之前）、win（接够以后），都可以不写。
## 进度（story.mech_load）：{caught, miss, gave_up, done}：读档回来接着接。

const OL := preload("res://scripts/overlay_layout.gd")
const KIT := preload("res://scripts/river_explore_order.gd")
const ID := "side_toucan"
const NEED := 5
const MAX_MISS := 4
const BEAK := "res://art/forest_side/toucan_beak.png"
const FRUIT := "res://art/forest_side/fruit.png"
const BW := 27                          # 大嘴鸟一帧（和 toucan.json 一样）
const BH := 29
const B_ANCHOR := Vector2(13, 27)
const FW := 9                           # 果子一格
const AREA := Vector2(-150.0, -30.0)    # 晨能接的范围（相对大嘴鸟）
const CATCH_R := 12.0                   # 果子离晨多近算接住（横向）
const CATCH_Y := 30.0                   # 晨胸口：离脚底多高
const ARC := 42.0                       # 抛物线拱多高
const SLOT_GAP := 10
const SFX_TOSS := "res://audio/sfx/small_click.wav"
const SFX_CATCH := "res://audio/sfx/pickup.wav"
const SFX_DROP := "res://audio/sfx/thud.wav"
const SFX_CLACK := "res://audio/sfx/wood_knock.wav"
const SFX_DONE := "res://audio/sfx/bell_soft.wav"
const HINT := {"zh": "← → / A D：接住大嘴鸟抛过来的果子", "en": "← → / A D: catch the toucan's fruit", "fr": "← → / A D : attraper les fruits du toucan"}


static func need_of(st: Dictionary) -> int:
	return maxi(int(st.get("need", NEED)), 1)


static func max_miss(st: Dictionary) -> int:
	return maxi(int(st.get("max_miss", MAX_MISS)), 1)


static func fresh() -> Dictionary:
	return {"caught": 0, "miss": 0, "gave_up": false, "done": false}


## 一个果子落下来的结果：true = 接住。返回这一下以后怎么样了："caught" / "won" / "miss" / "give_up"
static func land(st: Dictionary, s: Dictionary, ok: bool) -> String:
	if ok:
		s["caught"] = int(s["caught"]) + 1
		return "won" if int(s["caught"]) >= need_of(st) else "caught"
	s["miss"] = int(s["miss"]) + 1
	if not s["gave_up"] and int(s["miss"]) >= max_miss(st):
		s["gave_up"] = true
		return "give_up"
	return "miss"


class Ticker extends Node:
	var f: Callable

	func _process(delta: float) -> void:
		if f.is_valid():
			f.call(delta)


# ======================================================================= 演出
var auto_mode := false
var story: Node
var level: Node2D
var step: Dictionary
var s: Dictionary
var bird: Node2D
var chen: Node2D
var playing := false                    # 玩家在接（晨能走）
var target_x := 0.0                     # 这个果子落在哪（自动玩、测试用）
var _auto_miss := 0                     # 自动玩：先故意漏几个
var _tick: Ticker
var _beak: Sprite2D
var _beak_frame := 0
var _beak_hold := 0.0                   # 剧本里指定的嘴型还要停多久（秒），0 = 自己（说话一张一合 / 合着）
var _talk_t := 0.0
var _slots: Array = []
var _row: Node2D
var _hint: CanvasLayer
var _was_input := true
var _rng := RandomNumberGenerator.new()
var _fruit_tex: Texture2D
var _lo := 0.0
var _hi := 0.0
var _said_miss := false
var _chen_tw: Tween


func run(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	level = lv
	story = r
	step = st
	if str(st.get("act", "catch")) == "huff":
		await _huff_only()
		return
	s = story.mech_load(ID)
	if not s.has("caught"):
		s = fresh()
	_rng.seed = 20261102
	await _setup()
	await _lines("start")
	while not story.ended and int(s["caught"]) < need_of(step):
		var kind: String = await _one_throw()
		story.mech_save(ID, s)
		if kind == "miss" and not _said_miss:
			_said_miss = true
			await _pause_lines("miss")
		elif kind == "give_up":
			await _pause_lines("auto")
		await _wait(0.45)
	s["done"] = true
	story.mech_save(ID, s)
	_set_flags(step)
	await _finish()
	print("MECH %s done caught=%d miss=%d gave_up=%s" % [ID, int(s["caught"]), int(s["miss"]), str(s["gave_up"])])


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	_auto_miss = int(st.get("auto_miss", 1 if r.auto == "full" else 0))
	await run(lv, w, r, st)


func ff(r: Node, st: Dictionary) -> void:
	if str(st.get("act", "catch")) == "huff":
		return
	var t := fresh()
	t["caught"] = need_of(st)
	t["done"] = true
	r.mech_save(ID, t)
	_set_flags(st)


static func _set_flags(st: Dictionary) -> void:
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))


# ----------------------------------------------------------------------- 一个果子
func _one_throw() -> String:
	var o := _mouth()
	var target := _pick_target()
	target_x = target
	var catchy := _ground(target) - CATCH_Y
	var k := float(s["caught"]) / float(need_of(step))
	var dur := lerpf(1.6, 1.15, k) * (1.15 if s["gave_up"] else 1.0)
	_set_playing(not s["gave_up"])
	# 抛：嘴张一下、抬头，果子从嘴尖飞出去
	_beak_set(4, 0.3)
	_sfx(SFX_TOSS, -12.0, 1.0 + 0.05 * float(s["caught"]))
	var f := _fruit_sprite(0)
	f.position = o
	level.add_child(f)
	var want_miss: bool = auto_mode and _auto_miss > 0 and not s["gave_up"]
	if auto_mode and not want_miss:
		_auto_walk(target, dur * 0.7)
	var t := 0.0
	var caught := false
	var u := 0.0
	while not story.ended:
		await StoryState.frame(story.get_tree())
		t += story.get_process_delta_time() / (0.25 if auto_mode else 1.0)
		u = t / dur
		var p := _arc(o, Vector2(target, catchy), u)
		f.position = p.round()
		if u > 0.55 and chen != null and absf(p.x - chen.position.x) <= CATCH_R \
				and p.y >= chen.position.y - CATCH_Y - 14.0 and p.y <= chen.position.y - 10.0:
			caught = true
			break
		if p.y >= _ground(p.x) - 3.0:
			break
	if want_miss and not caught:
		_auto_miss -= 1
	var kind := land(step, s, caught)
	if caught:
		_caught_fx(f, int(s["caught"]) - 1)
	else:
		_drop_fx(f)
	if kind == "give_up":
		_set_playing(false)
	return kind


## 抛物线：u 0→1 从嘴尖到晨胸口那么高，u > 1 接着往下掉（同一条曲线）
func _arc(o: Vector2, e: Vector2, u: float) -> Vector2:
	var x := lerpf(o.x, e.x, u)
	var y := lerpf(o.y, e.y, u) - 4.0 * ARC * u * (1.0 - u)
	return Vector2(x, y)


## 往哪抛：离晨 28~64 像素、往空的那边；掉满了以后直接往晨手里抛
func _pick_target() -> float:
	var cx := chen.position.x if chen != null else (_lo + _hi) / 2.0
	if s["gave_up"]:
		return cx
	var room_l := cx - _lo
	var room_r := _hi - cx
	var sg := 1.0 if room_r > room_l else -1.0
	if _rng.randf() < 0.3 and minf(room_l, room_r) > 40.0:
		sg = -sg
	var x := cx + sg * _rng.randf_range(28.0, 64.0)
	return clampf(x, _lo + 6.0, _hi - 6.0)


func _caught_fx(f: Sprite2D, slot: int) -> void:
	_sfx(SFX_CATCH, -8.0, 1.0 + 0.08 * float(slot))
	_chen_hop()
	if slot < 0 or slot >= _slots.size():
		f.queue_free()
		return
	var dst: Sprite2D = _slots[slot]
	var from := f.position
	var to := _row.position + dst.position if _row != null else dst.global_position
	var tw := f.create_tween()
	tw.tween_method(func(v: float):
		var e := 0.5 - 0.5 * cos(PI * v)
		f.position = (from.lerp(to, e) - Vector2(0, round(14.0 * sin(PI * v)))).round(), 0.0, 1.0, 0.45)
	tw.tween_callback(func():
		f.queue_free()
		_slot_lit(dst))


func _drop_fx(f: Sprite2D) -> void:
	_sfx(SFX_DROP, -16.0, 1.3)
	var x0 := f.position.x
	var sg := 1.0 if _rng.randf() < 0.5 else -1.0
	var tw := f.create_tween()
	tw.tween_method(func(v: float):
		var x := x0 + sg * 6.0 * sin(PI * 0.5 * v)
		f.position = Vector2(round(x), round(_ground(x) - 4.0 - 3.0 * sin(PI * v))), 0.0, 1.0, 0.35)
	tw.tween_interval(0.4)
	tw.tween_method(func(v: float): f.modulate.a = ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, 0.5)
	tw.tween_callback(f.queue_free)


# ----------------------------------------------------------------------- 摆人
func _setup() -> void:
	chen = story.chen
	var who := str(step.get("who", "toucan"))
	if "_npc_names" in story:
		story._npc_names[who] = true
	bird = story.npc(who)
	if bird != null and not bird.visible:
		await story.run_steps([{"do": "show", "who": who, "fade": 0.6}])
	var bx: float = bird.position.x if bird != null else (chen.position.x + 80.0 if chen != null else 0.0)
	_lo = bx + AREA.x
	_hi = bx + AREA.y
	if chen != null:
		if step.has("chen_at"):
			await story.run_steps([{"do": "walk", "who": "chen", "to": step["chen_at"]}])
		elif chen.position.x < _lo or chen.position.x > _hi:
			await story.run_steps([{"do": "walk", "who": "chen", "to": round(bx - 80.0)}])
		if bird != null:
			await story.run_steps([{"do": "face", "who": "chen", "to": who}])
		_was_input = chen.input_enabled
	_fruit_tex = _load_tex(FRUIT)
	_overlay_on()
	_tick = Ticker.new()
	_tick.f = _on_tick
	level.add_child(_tick)
	# 头顶一排计数（灰果子，接到一个亮一个）
	_row = Node2D.new()
	_row.z_as_relative = false
	_row.z_index = 100
	level.add_child(_row)
	_row.add_child(OL.BusyFade.new(story))           # 头顶那排：说话的框就在头顶，说话的时候淡掉
	if bird != null:
		_row.position = Vector2(round(bird.position.x), round(bird.position.y - float(bird.get("head")) - FW - 8.0))
	var n := need_of(step)
	var x0 := -roundf((float(n - 1) * SLOT_GAP + FW) / 2.0)
	for i in n:
		var sl := _fruit_sprite(0 if i < int(s["caught"]) else 1)
		sl.position = Vector2(x0 + i * SLOT_GAP, 3)
		sl.z_as_relative = true
		sl.z_index = 0
		sl.modulate.a = 0.0
		_row.add_child(sl)
		_slots.append(sl)
		var tw := sl.create_tween().set_parallel(true)
		tw.tween_interval(0.08 * i)
		tw.chain().tween_method(func(v: float):
			sl.modulate.a = floorf(v * 4.0) / 4.0
			sl.position.y = round(3.0 * (1.0 - v)), 0.0, 1.0, 0.3).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)


func _teardown() -> void:
	_set_playing(false)
	_show_hint(false)
	if _tick != null:
		_tick.queue_free()
		_tick = null
	if _row != null:
		var row := _row
		_row = null
		_slots = []
		var tw := row.create_tween()
		tw.tween_method(func(v: float): row.modulate.a = ceilf((1.0 - v) * 4.0) / 4.0, 0.0, 1.0, 0.5)
		tw.tween_callback(row.queue_free)
	_overlay_off()
	_reset_chen()
	if chen != null:
		chen.input_enabled = _was_input


func _finish() -> void:
	_set_playing(false)
	_sfx(SFX_DONE, -14.0, 1.0)
	_beak_set(2, 0.35)
	await _wait(0.8)
	await _lines("win")
	_teardown()


## 掉了 / 掉满了：先停下晨，说完再接着抛
func _pause_lines(key: String) -> void:
	var was := playing
	_set_playing(false)
	await _lines(key)
	_set_playing(was and not s["gave_up"])


func _set_playing(on: bool) -> void:
	playing = on and not auto_mode
	if chen != null:
		chen.input_enabled = playing
	_show_hint(playing and int(s.get("caught", 0)) == 0)


func _on_tick(delta: float) -> void:
	if playing and chen != null:
		if not chen.input_enabled:
			chen.input_enabled = true
		var x := clampf(chen.position.x, _lo, _hi)
		if x != chen.position.x:
			chen.position.x = move_toward(chen.position.x, x, 3.0)    # 出了接果子的范围：慢慢走回来，不一帧夹回去（11-04 --qa_live）
	_beak_tick(delta)


func _lines(key: String) -> void:
	var l: Dictionary = step.get("lines", {})
	if l.get(key) is Array and not (l[key] as Array).is_empty():
		await story.run_steps(l[key])


func _wait(sec: float) -> void:
	await story.get_tree().create_timer(sec * (0.25 if auto_mode else 1.0), false).timeout


func _mouth() -> Vector2:
	if bird == null:
		return chen.position + Vector2(80, -24)
	var f := -1.0 if int(bird.get("facing")) < 0 else 1.0
	return (bird.position + Vector2(f * 11.0, -20.0)).round()


func _ground(x: float) -> float:
	if story.world != null and story.world.has_method("ground_at"):
		return float(story.world.ground_at(x))
	return chen.position.y if chen != null else 228.0


# ----------------------------------------------------------------------- 晨：接住了轻轻一跳（不画新帧，只动待机帧的位置 / 缩放）
func _chen_hop() -> void:
	if chen == null or not ("spr" in chen) or chen.spr == null:
		return
	var sp: Node2D = chen.spr
	_reset_chen()
	var t := 0.25 if auto_mode else 1.0
	var tw := sp.create_tween()
	_chen_tw = tw
	tw.tween_method(func(k: float): sp.position.y = -round(12.0 * k * (1.0 - k)), 0.0, 1.0, 0.26 * t)
	tw.tween_property(sp, "scale", Vector2(1.05, 0.95), 0.05 * t).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tw.tween_property(sp, "scale", Vector2.ONE, 0.14 * t).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_callback(_reset_chen)


func _reset_chen() -> void:
	if _chen_tw != null and _chen_tw.is_valid():
		_chen_tw.kill()
	_chen_tw = null
	if chen != null and "spr" in chen and chen.spr != null:
		chen.spr.position = Vector2.ZERO
		chen.spr.scale = Vector2.ONE


## 自动玩：晨走到果子底下（缓起缓停）
func _auto_walk(x: float, sec: float) -> void:
	if chen == null:
		return
	var x0 := chen.position.x
	if chen.has_method("_set_facing") and absf(x - x0) > 1.0:
		chen._set_facing(1 if x > x0 else -1)
	var tw := chen.create_tween()
	# 不比晨平时走路快（150 像素 / 秒）：缩成 1/4 时间那样一帧 7 像素，--qa_live 算闪现
	tw.tween_method(func(v: float): chen.position.x = round(lerpf(x0, x, 0.5 - 0.5 * cos(PI * v))), 0.0, 1.0, maxf(sec * 0.25, absf(x - x0) / 150.0 * 1.6))


# ----------------------------------------------------------------------- 大嘴鸟的嘴（叠图）
func _overlay_on() -> void:
	if bird == null or not ("spr" in bird):
		return
	var tex := _load_tex(BEAK)
	if tex == null:
		return
	_beak = Sprite2D.new()
	_beak.texture = tex
	_beak.hframes = 5
	_beak.centered = false
	_beak.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	var sp: Sprite2D = bird.spr
	_beak.modulate = sp.modulate
	_beak.z_index = sp.z_index
	var flip := int(bird.get("facing")) > 0             # 图是朝左画的
	_beak.flip_h = flip
	var ax := B_ANCHOR.x if not flip else BW - 1.0 - B_ANCHOR.x
	_beak.offset = Vector2(-ax, -B_ANCHOR.y - 1.0)
	bird.add_child(_beak)
	sp.self_modulate.a = 0.0
	var top = bird.get("_top")
	if top is Sprite2D:
		(top as Sprite2D).self_modulate.a = 0.0


func _overlay_off() -> void:
	if _beak != null:
		_beak.queue_free()
		_beak = null
	if bird != null and "spr" in bird and bird.spr != null:
		bird.spr.self_modulate.a = 1.0
		var top = bird.get("_top")
		if top is Sprite2D:
			(top as Sprite2D).self_modulate.a = 1.0


func _beak_set(fr: int, hold: float) -> void:
	_beak_frame = fr
	_beak_hold = hold
	if _beak != null:
		_beak.frame = fr


## 每 100ms 一帧：指定的嘴型停够了就回到合嘴；它在说话就 0 / 1 / 2 / 1 一张一合
func _beak_tick(delta: float) -> void:
	if _beak == null:
		return
	if _beak_hold > 0.0:
		_beak_hold -= delta / (0.25 if auto_mode else 1.0)
		return
	var talking := bird != null and bool(bird.get("_talking"))
	if talking:
		_talk_t += delta
		var seq := [0, 1, 2, 1]
		_beak.frame = seq[int(_talk_t / 0.1) % seq.size()]
	else:
		_talk_t = 0.0
		_beak.frame = 0


## 「你嘴太大了，当不了妈妈」：嘴一下张到最大，再一档一档合回去，卡一下，三秒才合拢，最后咔一声
const HUFF := [[1, 1], [2, 1], [3, 6], [3, 4], [2, 5], [3, 2], [2, 6], [1, 5], [2, 1], [1, 4], [0, 0]]   # [帧, 停几个 100ms]


func _huff_only() -> void:
	chen = story.chen
	var who := str(step.get("who", "toucan"))
	if "_npc_names" in story:
		story._npc_names[who] = true
	bird = story.npc(who)
	_overlay_on()
	_tick = Ticker.new()
	_tick.f = func(_d: float): pass
	level.add_child(_tick)
	_sfx(SFX_TOSS, -14.0, 0.7)
	for fh in HUFF:
		if _beak != null:
			_beak.frame = int(fh[0])
		await _wait(0.1 * maxf(1.0, float(fh[1])))
	_sfx(SFX_CLACK, -8.0, 1.25)
	await _wait(0.6)
	_tick.queue_free()
	_tick = null
	_overlay_off()


# ----------------------------------------------------------------------- 杂项
func _fruit_sprite(cell: int) -> Sprite2D:
	var f := Sprite2D.new()
	f.centered = false
	f.offset = Vector2(-4, -4)
	f.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	f.z_as_relative = false
	f.z_index = 100
	if _fruit_tex != null:
		var at := AtlasTexture.new()
		at.atlas = _fruit_tex
		at.region = Rect2(cell * FW, 0, FW, FW)
		f.texture = at
	return f


func _slot_lit(sl: Sprite2D) -> void:
	if not is_instance_valid(sl):
		return
	if sl.texture is AtlasTexture:
		(sl.texture as AtlasTexture).region = Rect2(0, 0, FW, FW)
	var tw := sl.create_tween()
	tw.tween_method(func(v: float): sl.position.y = 3.0 - round(5.0 * sin(PI * v)), 0.0, 1.0, 0.24)


static func _load_tex(p: String) -> Texture2D:
	if ResourceLoader.exists(p):
		return load(p)
	if FileAccess.file_exists(p):               # 新图编辑器还没导入：直接读 png
		var img := Image.load_from_file(ProjectSettings.globalize_path(p))
		if img != null and not img.is_empty():
			return ImageTexture.create_from_image(img)
	return null


func _show_hint(on: bool) -> void:
	if auto_mode or level == null:
		return
	if on and _hint == null:
		OL.hud(story, true)                           # 左上角目标让开（最上面一行给按键提示）
		_hint = CanvasLayer.new()
		_hint.layer = 5
		level.add_child(_hint)
		var lb := OL.HintLabel.new(story)          # 对话 / 选项在显示的时候自己让开（11-04 安全区）
		lb.text = story.txt(HINT) if story.has_method("txt") else str(HINT["zh"])
		lb.add_theme_font_override("font", UITheme.font())
		lb.add_theme_font_size_override("font_size", 14)
		lb.add_theme_color_override("font_color", UITheme.TEXT_DIM)
		lb.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lb.position = Vector2(0, OL.HINT_Y)         # 屏幕上方那一行，不放进下面对话那一带
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
		tw.tween_callback(func():
			if _hint == null:                             # 提示收完才放目标回来（这半秒里又开了一条就不放）
				OL.hud(story, false))
		tw.tween_callback(h.queue_free)


func _sfx(path: String, db: float, pitch: float) -> void:
	if level == null or not ResourceLoader.exists(path):
		return
	var a := AudioStreamPlayer.new()
	a.stream = load(path)
	a.bus = "SFX" if AudioServer.get_bus_index("SFX") >= 0 else "Master"
	a.volume_db = db + float(step.get("sfx_db", 0.0))
	a.pitch_scale = pitch
	level.add_child(a)
	a.play()
	a.finished.connect(a.queue_free)


# ----------------------------------------------------------------------- --story_check
func check(story: Node, st: Dictionary) -> Array:
	var out: Array = []
	var act := str(st.get("act", "catch"))
	if not act in ["catch", "huff"]:
		out.append("act 要是 catch 或 huff，不是 %s" % act)
	if st.has("chen_at") and st["chen_at"] is String and not story.world.has_marker(str(st["chen_at"])):
		out.append("chen_at 的 marker %s 找不到" % st["chen_at"])
	for p in [BEAK, FRUIT]:
		if not FileAccess.file_exists(p):
			out.append("图 %s 还没有" % p)
	for k in st.get("lines", {}):
		out.append_array(KIT.check_steps(story, "lines.%s" % k, st["lines"][k]))
	return out
