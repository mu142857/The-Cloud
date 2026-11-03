extends SceneTree
## 维修小游戏 scripts/ship_repair.gd 的 headless 小测试（不开窗口、不截图）：
##   gt.sh 60 /tmp/x.log -- -s res://tools/ship_repair_test.gd
## 用一个假的 story（只有 mech_load / mech_save / run_steps / ended / ff / auto），跑五段：
##   1. auto()（main）        快速自动修完
##   2. auto()（full）        自动修的时候先演一次敲过头
##   3. 手动模拟              转水管 → 敲零件刚好 → 敲过头一次（只那一个重来）→ 再敲过头两次 → 第三次放水，剩下的自己敲完
##   4. 第三次进              什么都不点，自己修完
##   5. 再进来（水管已通）    直接从锤子开始；全部刚好，不算失败
## 外加 check() 没有问题、ff() 存好进度。最后打印 SHIP_REPAIR_TEST PASS / FAIL。

const M := preload("res://scripts/ship_repair.gd")

var _fails: Array = []


class FakeStory extends Node:
	var ended := false
	var ff := false
	var auto := ""
	var dlg = null
	var store := {}
	var steps_run: Array = []

	func mech_load(mid: String) -> Dictionary:
		var v = JSON.parse_string(str(store.get(mid, "{}")))
		return v if v is Dictionary else {}

	func mech_save(mid: String, d: Dictionary) -> void:
		store[mid] = JSON.stringify(d)

	func run_steps(arr: Array) -> String:
		steps_run.append_array(arr)
		await get_tree().process_frame
		return ""


func _initialize() -> void:
	_main.call_deferred()


func _ok(cond: bool, what: String) -> void:
	if cond:
		print("  ok   ", what)
	else:
		print("  FAIL ", what)
		_fails.append(what)


func _new_story(auto := "") -> FakeStory:
	var st := FakeStory.new()
	st.auto = auto
	root.add_child(st)
	return st


func _until(cond: Callable, frames := 3000) -> bool:
	for i in frames:
		if cond.call():
			return true
		await process_frame
	return false


## 跑一局：返回 [小游戏实例, 跑完的标记（数组里放 true）]
func _start(m, st: FakeStory, step: Dictionary, use_auto := false) -> Array:
	var flag: Array = []
	var lv := Node2D.new()
	root.add_child(lv)
	var go := func():
		if use_auto:
			await m.auto(lv, null, st, step)
		else:
			await m.run(lv, null, st, step)
		flag.append(true)
	go.call()
	return [m, flag]


func _main() -> void:
	var step := {"do": "mechanic", "id": "ship_repair", "sets": ["test_ship_fixed"],
		"lines": {"crack_1": [{"do": "say", "who": "miluo", "zh": "轻点！"}]}}
	print("SHIP_REPAIR_TEST start")

	# ---- 规则
	_ok(not M.flow(M.start_rots())["done"], "开局水管不通")
	_ok(M.flow(M.solved_rots())["done"], "答案方向水管通")
	var clicks := 0
	var r := M.start_rots()
	while M.best_tile(r) >= 0 and clicks < 40:
		var i := M.best_tile(r)
		r[i] = posmod(int(r[i]) + 1, 4)
		clicks += 1
	_ok(M.flow(r)["done"] and clicks == 9, "照对的转 9 下接通（实际 %d 下）" % clicks)
	var p := {"hits": 0, "locked": false}
	_ok(M.hit(p, 2) == "hit" and M.hit(p, 2) == "full" and M.hit(p, 2) == "crack" and int(p["hits"]) == 0, "敲 2 下刚好、第 3 下敲过头清零")
	var cs := _new_story()
	var issues: Array = []
	var bare: Dictionary = step.duplicate(true)
	bare.erase("lines")                              # lines 的检查要真的 story_runner（STEPS 表），这里只查小游戏自己的
	for l in M.new().check(cs, bare):
		if not str(l).begins_with("info:"):
			issues.append(l)
	_ok(issues.is_empty(), "check() 没有问题 %s" % str(issues))

	# ---- 1. auto（main）
	var st1 := _new_story("main")
	var a1 := _start(M.new(), st1, step, true)
	var done1: bool = await _until(func(): return not (a1[1] as Array).is_empty())
	var s1 := st1.mech_load("ship_repair")
	_ok(done1 and s1.get("done", false) and s1.get("pipes", false) and StoryState.has("test_ship_fixed"), "auto(main) 修完、设上 flag")
	_ok(int(s1.get("fails", -1)) == 0, "auto(main) 没敲过头")

	# ---- 2. auto（full）：先演一次敲过头
	var st2 := _new_story("full")
	var a2 := _start(M.new(), st2, step, true)
	var done2: bool = await _until(func(): return not (a2[1] as Array).is_empty())
	var s2 := st2.mech_load("ship_repair")
	_ok(done2 and s2.get("done", false) and int(s2.get("fails", 0)) == 1, "auto(full) 敲过头一次以后修完（fails=%d）" % int(s2.get("fails", -1)))

	# ---- 3. 手动模拟
	var st3 := _new_story()
	var m3 = M.new()
	var a3 := _start(m3, st3, step)
	_ok(await _until(func(): return m3.stage == "pipes" and m3._accept), "进到水管这一步、等玩家")
	var n := 0
	while M.best_tile(m3.s["rots"]) >= 0 and n < 40:
		m3.turn_tile(M.best_tile(m3.s["rots"]))
		n += 1
		for k in 3:
			await process_frame
	_ok(await _until(func(): return m3.stage == "hammer" and m3._waiting), "水管接通 → 盖子盖上 → 到锤子这一步")
	_ok(m3._lid_y == float(M.LID_Y), "盖子停在 y=%d（现在 %.1f）" % [M.LID_Y, m3._lid_y])
	var need: Array = m3.need
	# 零件 0：刚好
	for k in int(need[0]):
		m3.hit_part(0)
	_ok(await _until(func(): return m3.parts[0]["locked"]), "零件 0 敲 %d 下刚好，锁死" % int(need[0]))
	# 零件 1：敲过头一次（只它重来，零件 0 还锁着）
	for k in int(need[1]) + 1:
		m3.hit_part(1)
	_ok(await _until(func(): return int(m3.s["fails"]) == 1), "零件 1 多敲一下 → 敲过头（fails=1）")
	_ok(not m3.parts[1]["locked"] and int(m3.parts[1]["hits"]) == 0 and m3.parts[0]["locked"], "只有零件 1 清零重来，零件 0 还锁着")
	_ok(await _until(func(): return m3._accept), "敲过头那句台词播完，接着能敲")
	_ok(st3.steps_run.size() > 0, "第一次敲过头播了 lines.crack_1")
	await _until(func(): return not m3._swinging)
	for k in int(need[1]):
		m3.hit_part(1)
	_ok(await _until(func(): return m3.parts[1]["locked"]), "零件 1 重新敲刚好，锁死")
	# 零件 2：再敲过头两次 → 第三次放水
	for t in 2:
		await _until(func(): return not m3._swinging and m3._accept)
		for k in int(need[2]) + 1:
			m3.hit_part(2)
		await _until(func(): return int(m3.s["fails"]) == 2 + t)
	_ok(int(m3.s["fails"]) == 3, "累计敲过头 3 次（fails=%d）" % int(m3.s["fails"]))
	_ok(await _until(func(): return m3.stage in ["give", "done"] or not (a3[1] as Array).is_empty()), "第三次敲过头 → 放水")
	_ok(await _until(func(): return not (a3[1] as Array).is_empty()), "放水以后剩下的自己敲完、小游戏结束")
	var all3 := true
	for q in m3.parts:
		all3 = all3 and q["locked"]
	_ok(all3 and st3.mech_load("ship_repair").get("done", false), "四个零件都锁上、进度记 done")

	# ---- 4. 第三次进：不点也自己修完
	var st4 := _new_story()
	st4.mech_save("ship_repair", {"enter": 2, "fails": 0, "rots": M.start_rots(), "pipes": false, "done": false})
	var m4 = M.new()
	var a4 := _start(m4, st4, step)
	_ok(await _until(func(): return not (a4[1] as Array).is_empty(), 6000), "第三次进：不点也自己修完")
	_ok(int(st4.mech_load("ship_repair")["enter"]) == 3 and int(st4.mech_load("ship_repair")["fails"]) == 0, "enter=3，没算失败")

	# ---- 5. 再进来（水管已通）：直接从锤子开始，全部刚好
	var st5 := _new_story()
	st5.mech_save("ship_repair", {"enter": 1, "fails": 0, "rots": M.solved_rots(), "pipes": true, "done": false})
	var m5 = M.new()
	var a5 := _start(m5, st5, step)
	_ok(await _until(func(): return m5.stage == "hammer" and m5._waiting), "水管通过的再进来：直接到锤子")
	for j in 4:
		await _until(func(): return not m5._swinging)
		for k in int(m5.need[j]):
			m5.hit_part(j)
		await _until(func(): return m5.parts[j]["locked"])
	_ok(await _until(func(): return not (a5[1] as Array).is_empty()), "全部刚好 → 修完")
	_ok(int(st5.mech_load("ship_repair")["fails"]) == 0, "全部刚好不算失败")

	# ---- ff
	var st6 := _new_story()
	st6.ff = true
	M.new().ff(st6, step)
	_ok(st6.mech_load("ship_repair").get("done", false), "ff() 存好修完的进度")

	print("SHIP_REPAIR_TEST %s %s" % ["PASS" if _fails.is_empty() else "FAIL", str(_fails)])
	quit(0 if _fails.is_empty() else 1)
