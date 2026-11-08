extends SceneTree
## rabbit_dance 的小测试（headless）：
##   gt.sh 90 log -- -s res://scripts/rabbit_dance_test.gd
## 用一个假的剧本 runner（只有小游戏用到的那几样）+ 真的兔子（npc_generic.gd 读 art/characters/rabbit/rabbit.json）：
##   1. 规则：act() 按对 / 按错 / 错满三次
##   2. auto()：先按错一次，再自动按完
##   3. run()：真的往输入里塞方向键 / WASD（第一轮按错一次）
##   4. run()：连错三次，剩下的自动过
## 每样检查：跳完了、错几次、晨的精灵复原、晨的输入还回去、兔子朝着晨。

const RD := preload("res://scripts/rabbit_dance.gd")
const NPC_GD := preload("res://scripts/npc_generic.gd")

var fails := 0


class FakeChen extends Node2D:
	var spr: AnimatedSprite2D
	var facing := 1
	var input_enabled := true
	var _vel := 0.0

	func _init() -> void:
		spr = AnimatedSprite2D.new()
		add_child(spr)

	func _set_facing(f: int) -> void:
		facing = f


class FakeStory extends Node:
	var chen: Node2D
	var ff := false
	var auto := ""
	var ended := false
	var _npc_names := {}
	var npcs := {}
	var props := {}
	var level: Node2D
	var log: Array = []

	func mech_load(mid: String) -> Dictionary:
		var v = JSON.parse_string(str(props.get(mid, "{}")))
		return v if v is Dictionary else {}

	func mech_save(mid: String, d: Dictionary) -> void:
		props[mid] = JSON.stringify(d)

	func npc(who: String) -> Node2D:
		if who == "chen":
			return chen
		if npcs.has(who):
			return npcs[who]
		if not _npc_names.has(who):
			return null
		var n: Node2D = NPC_GD.new()
		n.setup(who)
		n.visible = false
		level.add_child(n)
		npcs[who] = n
		return n

	func txt(d) -> String:
		return str(d.get("zh", "")) if d is Dictionary else str(d)

	func run_steps(steps: Array) -> String:
		for st in steps:
			var d := str(st.get("do", "say" if st.has("say") else ""))
			log.append(d)
			match d:
				"show":
					var n := npc(str(st["who"]))
					if st.has("at"):
						n.position = Vector2(float(st["at"]), chen.position.y)
					n.visible = true
				"walk":
					npc(str(st["who"])).position.x = float(st["to"])
				"face":
					var n := npc(str(st["who"]))
					var t := npc(str(st["to"]))
					n._set_facing(1 if t.position.x > n.position.x else -1)
		await get_tree().process_frame
		return ""


func _initialize() -> void:
	Engine.time_scale = 4.0
	_main.call_deferred()


func ok(cond: bool, what: String) -> void:
	if cond:
		print("  ok   ", what)
	else:
		fails += 1
		print("  FAIL ", what)


func _make() -> Array:
	var level := Node2D.new()
	root.add_child(level)
	var chen := FakeChen.new()
	chen.position = Vector2(300, 229)
	level.add_child(chen)
	var story := FakeStory.new()
	story.chen = chen
	story.level = level
	level.add_child(story)
	return [level, chen, story]


func _drop(env: Array) -> void:
	(env[0] as Node).queue_free()
	await process_frame


func _check_after(env: Array, m, want_miss: int, want_gave_up: bool, tag: String) -> void:
	var chen: FakeChen = env[1]
	var story: FakeStory = env[2]
	var s: Dictionary = story.mech_load(RD.ID)
	ok(s.get("done", false) and int(s.get("round", 0)) == RD.SEQS.size(), "%s: 四轮跳完 %s" % [tag, str(s)])
	ok(int(s.get("miss", -1)) == want_miss, "%s: 错 %d 次" % [tag, want_miss])
	ok(bool(s.get("gave_up", false)) == want_gave_up, "%s: gave_up = %s" % [tag, str(want_gave_up)])
	ok(chen.spr.position == Vector2.ZERO and chen.spr.scale == Vector2.ONE and chen.spr.skew == 0.0, "%s: 晨的精灵复原" % tag)
	ok(chen.input_enabled, "%s: 晨的输入还回去了" % tag)
	var rb: Node2D = story.npcs.get("rabbit")
	ok(rb != null and rb.visible and rb.facing == -1, "%s: 兔子在、朝着晨（晨在左）" % tag)
	ok(rb != null and not rb._ph, "%s: 兔子的图读到了（不是占位色块）" % tag)
	ok(m._row == null and m._catch == null, "%s: 箭头、收键节点收掉了" % tag)


func _key(code: Key, phys: Key) -> void:
	for down in [true, false]:
		var e := InputEventKey.new()
		e.keycode = code
		e.physical_keycode = phys
		e.pressed = down
		Input.parse_input_event(e)
		await process_frame


## 跑 run()，每次小游戏在等键就塞下一个；返回实际塞了几个
func _play_keys(env: Array, st: Dictionary, keys: Array) -> Array:
	var m = RD.new()
	var done := {"v": false}
	var go := func():
		await m.run(env[0], null, env[2], st)
		done["v"] = true
	go.call()
	var sent := 0
	var t := 0
	while not done["v"] and t < 60 * 120:
		await process_frame
		t += 1
		if m.listening and sent < keys.size():
			var k: Array = keys[sent]
			sent += 1
			await _key(k[0], k[1])
	return [m, sent, done["v"]]


func _main() -> void:
	print("== rabbit_dance test")
	# 1. 规则
	var st := {}
	var s := RD.fresh()
	ok(RD.act(st, s, "up")["kind"] == "ok", "规则：按对第一个 = ok")
	ok(RD.act(st, s, "up")["kind"] == "wrong" and s["k"] == 0 and s["miss"] == 1, "规则：按错 = wrong，这一轮从头")
	for d in ["up", "left"]:
		RD.act(st, s, d)
	ok(RD.act(st, s, "right")["kind"] == "round" and s["round"] == 1, "规则：第一轮按完 = round")
	RD.act(st, s, "up")
	ok(RD.act(st, s, "up")["kind"] == "give_up" and s["gave_up"], "规则：错满三次 = give_up")
	var t2 := RD.fresh()
	for seq in RD.SEQS:
		for d in seq:
			RD.act(st, t2, str(d))
	ok(RD.finished(st, t2) and t2["miss"] == 0, "规则：全按对 = 跳完，0 次错")
	var ev := InputEventKey.new()
	ev.pressed = true
	ev.physical_keycode = KEY_W
	ok(RD.dir_of(ev) == "up", "按键：W = up")
	ev.physical_keycode = KEY_NONE
	ev.keycode = KEY_LEFT
	ok(RD.dir_of(ev) == "left", "按键：← = left")
	# 箭头一轮比一轮少；同一步错超过两次给辅助
	ok(RD.SEQS.map(func(q): return (q as Array).size()) == [3, 4, 4, 5], "规则：默认四轮 3 4 4 5 步（11-08 作者嫌难）")
	ok(is_equal_approx(RD.step_sec(st, 0, 0), RD.STEP_SEC), "速度：没写 speed = 正常")
	var sp := {"speed": [1.4, [0.8, 1.5]]}
	ok(RD.step_sec(sp, 0, 3) < RD.STEP_SEC and is_equal_approx(RD.step_sec(sp, 0, 0), RD.STEP_SEC / 1.4), "速度：整轮快 1.4 倍")
	ok(RD.step_sec(sp, 1, 0) > RD.STEP_SEC and RD.step_sec(sp, 1, 1) < RD.STEP_SEC and is_equal_approx(RD.step_sec(sp, 1, 5), RD.step_sec(sp, 1, 1)), "速度：一串数 = 每一下变速，不够长按最后一个")
	ok(is_equal_approx(RD.step_sec(sp, 2, 0), RD.STEP_SEC), "速度：没写到的轮 = 正常")
	ok([RD.round_mode(st, 0), RD.round_mode(st, 1), RD.round_mode(st, 2), RD.round_mode(st, 3)] == ["show", "fade", "hidden", "hidden"], "规则：show / fade / hidden / hidden")
	ok(RD.round_mode({"hide": ["hidden", "show"]}, 1) == "show", "规则：hide 可以一轮一轮指定")
	var rt := {"retry": true}
	var a := RD.fresh()
	a["round"] = 2
	RD.act(rt, a, "up")                       # 第三轮第一步是 right
	RD.act(rt, a, "up")
	ok(not RD.assisted(a), "辅助：同一步错两次还不给")
	RD.act(rt, a, "right")
	RD.act(rt, a, "left")                     # 第二步错一次（别的步不累加）
	ok(not RD.assisted(a), "辅助：错在不同步不算同一步")
	RD.act(rt, a, "down")
	ok(RD.assisted(a) and not a["gave_up"], "辅助：同一步错第三次 → 箭头重新给 %s" % str(a["fails"]))
	a["round"] = 3
	ok(not RD.assisted(a), "辅助：换一轮重新算")
	var old := {"round": 3, "k": 0, "miss": 0, "gave_up": false, "done": true}
	ok(RD.finished(st, old), "存档：以前三轮跳完的 done 存档不会回来跳第四轮")

	# 2. auto()：先按错一次
	var env := _make()
	var stp := {"id": "rabbit_dance", "at": 372, "auto_keys": ["down"]}
	var m = RD.new()
	var t0 := Time.get_ticks_msec()
	await m.auto(env[0], null, env[2], stp)
	print("  auto() 用了 %.1f 秒（time_scale 4）" % ((Time.get_ticks_msec() - t0) / 1000.0))
	_check_after(env, m, 1, false, "auto")
	await _drop(env)

	# 3. run()：真的按键，方向键和 WASD 混着，第一轮第二下按错
	env = _make()
	stp = {"id": "rabbit_dance", "at": 372, "lines": {"wrong": [{"say": "兔子：再看一遍"}]}}
	var L := [KEY_LEFT, KEY_NONE, "left"]
	var U := [KEY_NONE, KEY_W, "up"]
	var R := [KEY_RIGHT, KEY_NONE, "right"]
	var D := [KEY_NONE, KEY_S, "down"]
	var keys := [U, D, U, L, R, L, D, U, R, R, U, D, L, D, R, U, L, U]
	var r: Array = await _play_keys(env, stp, keys)
	ok(r[2], "run: 跑完了")
	ok(r[1] == keys.size(), "run: %d 个键全用上了（键丢了的话会少按、跑不完）" % r[1])
	ok((env[2] as FakeStory).log.has("say"), "run: 第一次按错播了 lines.wrong")
	_check_after(env, r[0], 1, false, "run")
	await _drop(env)

	# 4. run()：连错三次 → 剩下的自动过
	env = _make()
	stp = {"id": "rabbit_dance", "at": 372}
	keys = [D, D, D]
	r = await _play_keys(env, stp, keys)
	ok(r[2] and r[1] == 3, "give_up: 错三次以后不再要键，自己跳完")
	_check_after(env, r[0], 3, true, "give_up")
	await _drop(env)

	print("== rabbit_dance test %s (%d fail)" % ["PASS" if fails == 0 else "FAIL", fails])
	quit(0 if fails == 0 else 1)
