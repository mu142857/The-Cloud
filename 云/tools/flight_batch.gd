extends SceneTree
## 飞行段的 bot 统计：一个 Godot 进程里连跑很多局（只排一次 Godot 锁，比一局一个进程快得多）。
##   Godot --headless --audio-driver Dummy --path . --fixed-fps 60 -s tools/flight_batch.gd -- \
##       --bots=none,random,okay,good --cards=burn,keep --seeds=1-10
## 每局打印一行 FLIGHT_RESULT {...}（和 flight_test.tscn --quit 一样）。

var _jobs: Array = []
var _cur: Node


func _initialize() -> void:
	var bots := ["none", "random", "okay", "good"]
	var cards := ["burn", "keep"]
	var s0 := 1
	var s1 := 10
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		if kv.size() < 2:
			continue
		match kv[0]:
			"bots": bots = Array(kv[1].split(","))
			"cards": cards = Array(kv[1].split(","))
			"seeds":
				var r := kv[1].split("-")
				s0 = int(r[0])
				s1 = int(r[r.size() - 1])
	for c in cards:
		for b in bots:
			for s in range(s0, s1 + 1):
				_jobs.append([b, c, s])
	_next.call_deferred()


func _next() -> void:
	if _cur:
		_cur.queue_free()
		_cur = null
	if _jobs.is_empty():
		quit()
		return
	var j: Array = _jobs.pop_front()
	_cur = load("res://scenes/flight_test.tscn").instantiate()
	_cur.bot = j[0]
	_cur.card_policy = j[1]
	_cur.seed_v = j[2]
	_cur._quit = true
	_cur.batch = true
	_cur.finished.connect(func(_r): _next.call_deferred())
	root.add_child(_cur)
