extends Node
## 配乐（Music 总线，跟设置里的「音乐」音量走）。挂在 SceneTree 根下的一个节点上，换章节、重开场景都不断。
## 剧本：{"do": "music", "track": "forest"}  换曲（旧的淡出、新的淡入）；可选 "db"、"fade"、"loop"、"then"（不循环的放完接哪首）
##       {"do": "music", "stop": true, "fade": 1.5}  淡出停掉
## story_runner 还会自己调：闪回开始 suspend()、醒来 resume()；燃料二选一时放 space_choice；章节结束 stop()；
##   飞船小游戏（躲碎石、往前一冲）进场放 flight_theme、出来接回原来的（_cockpit_step）。TRACKS 里 "resume": true 的曲子停下时记住位置，
##   同一段里再进接着放（不重头）；"file" = 用哪个 wav（没写就是 track 名）。
## 曲子都在 res://audio/music/<名字>.wav（作者 11-04 给的）；编辑器还没导入时直接读 wav 文件。
## 淡入淡出（11-04 作者：「记得音效淡入淡出……如果之间有真空期你可以考虑把两个淡入淡出的交织在一起」）：
##   换曲 = 旧的淡出、新的同时淡入（交叉）；循环的曲子把 WAV 本身设成循环（导入没开，原来放完再 play() 接缝处会断一下）；
##   不循环的（theme → forest）在结尾前 THEN_XF 秒就开始接下一首，两首交叉，不留真空。每个播放器只留一个音量 tween（不打架）。

const DIR := "res://audio/music/"
## 每首默认多响、要不要循环（作者听了觉得哪首太响，改这里的 db）
const TRACKS := {
	"forest": {"db": -10.0, "loop": true},
	"theme": {"db": -5.0, "loop": false, "then": "forest"},
	"rabbit_beat": {"db": -7.0, "loop": true},
	"space_choice": {"db": -9.0, "loop": true},
	# 11-05 作者「每个飞船游戏都要播放音乐」，给的 jam(1).wav 就是 theme.wav：同一个文件另起一条 track——循环、不接 forest、
	# 比片头轻 4 dB（压在碎石段的气流 / 轰鸣提示下面）、停下记位置（story_runner._cockpit_step：躲碎石、往前一冲）
	"flight_theme": {"file": "theme", "db": -9.0, "loop": true, "resume": true},
}
const NODE_NAME := "BGM"
const THEN_XF := 3.0     # 不循环的曲子结尾前多久开始交叉到 then

var _cur: AudioStreamPlayer
var _track := ""
var _then := ""
var _held := ""          # suspend() 时记下的曲子，resume() 接回来
var _pos := {}           # "resume": true 的曲子停下时放到哪了（秒）：同一段里再进小游戏接着放，不重头


static func get_bgm(tree: SceneTree):
	var n := tree.root.get_node_or_null(NODE_NAME)
	if n == null:
		n = (load("res://scripts/bgm.gd") as GDScript).new()
		n.name = NODE_NAME
		n.process_mode = Node.PROCESS_MODE_ALWAYS   # 打开设置（暂停）时配乐接着放，不重开
		tree.root.add_child.call_deferred(n)
	return n


static func load_track(name: String) -> AudioStream:
	var p := DIR + str((TRACKS.get(name, {}) as Dictionary).get("file", name)) + ".wav"     # "file"：几条 track 共用一个文件
	if ResourceLoader.exists(p):
		return load(p) as AudioStream
	if FileAccess.file_exists(p):
		return AudioStreamWAV.load_from_file(ProjectSettings.globalize_path(p))
	return null


func play(name: String, db := NAN, fade := 1.5, loop := -1, then := "") -> void:
	if not is_inside_tree():             # get_bgm 刚建、还没进树：等进树再放
		play.call_deferred(name, db, fade, loop, then)
		return
	var cfg: Dictionary = TRACKS.get(name, {})
	if name == _track and _cur != null and is_instance_valid(_cur) and _cur.playing:
		return
	var s := load_track(name)
	if s == null:
		return
	print("BGM play %s (was %s) fade %.1fs" % [name, _track if _track != "" else "-", fade])     # headless 核对配乐换了没（--qa_audio 只报硬切）
	stop(fade)
	_track = name
	_then = then if then != "" else str(cfg.get("then", ""))
	var want_loop: bool = bool(cfg.get("loop", true)) if loop < 0 else loop == 1
	var target: float = float(cfg.get("db", -8.0)) if is_nan(db) else db
	if want_loop and s is AudioStreamWAV and (s as AudioStreamWAV).loop_mode == AudioStreamWAV.LOOP_DISABLED:
		var w := (s as AudioStreamWAV).duplicate() as AudioStreamWAV          # 无缝循环（不改缓存里那份）
		w.loop_mode = AudioStreamWAV.LOOP_FORWARD
		w.loop_begin = 0
		w.loop_end = int(round(w.get_length() * w.mix_rate))
		s = w
	var a := AudioStreamPlayer.new()
	a.stream = s
	a.bus = "Music"
	a.volume_db = -50.0
	a.set_meta("then_at", -1.0 if want_loop or _then == "" else maxf(0.0, s.get_length() - THEN_XF))
	add_child(a)
	a.play(float(_pos.get(name, 0.0)) if bool(cfg.get("resume", false)) else 0.0)
	a.finished.connect(func():
		if not is_instance_valid(a) or a != _cur:
			return
		if want_loop:
			a.play()                                                   # 兜底（上面已经设成循环，一般不会走到这）
		else:
			_track = ""
			if _then != "":
				play(_then, NAN, 2.5))
	_fade(a, target, fade)
	_cur = a


## 每帧：不循环的曲子快到结尾了，就开始交叉到 then（旧的淡出、新的淡入同时进行）
func _process(_delta: float) -> void:
	if _cur == null or not is_instance_valid(_cur) or not _cur.playing or _then == "":
		return
	var at: float = _cur.get_meta("then_at", -1.0)
	if at >= 0.0 and _cur.get_playback_position() >= at:
		_cur.set_meta("then_at", -1.0)
		play(_then, NAN, THEN_XF)


## 一个播放器同时只有一个音量 tween：新的来了先停掉旧的（不然两个 tween 抢着改，音量会跳）
func _fade(a: AudioStreamPlayer, to_db: float, sec: float, free_after := false) -> void:
	var old = (a.get_meta("fade_tw") if a.has_meta("fade_tw") else null)
	if old is Tween and (old as Tween).is_valid():
		(old as Tween).kill()
	var tw := create_tween()
	tw.tween_property(a, "volume_db", to_db, maxf(sec, 0.05)).set_trans(Tween.TRANS_SINE)
	if free_after:
		tw.tween_callback(a.queue_free)
	a.set_meta("fade_tw", tw)


func stop(fade := 1.5) -> void:
	if _track != "" and _cur != null and is_instance_valid(_cur) and _cur.playing and bool((TRACKS.get(_track, {}) as Dictionary).get("resume", false)):
		_pos[_track] = _cur.get_playback_position()
	if _track != "":
		print("BGM stop %s fade %.1fs" % [_track, fade])
	_track = ""
	if _cur == null or not is_instance_valid(_cur):
		_cur = null
		return
	var a := _cur
	_cur = null
	_fade(a, -50.0, fade, true)


## 闪回：先把现在这首淡掉、记住；醒来再接回来
func suspend(fade := 1.0) -> void:
	if _track != "":
		_held = _track
	stop(fade)


func resume(fade := 2.5) -> void:
	if _held != "":
		var h := _held
		_held = ""
		play(h, NAN, fade)


func current() -> String:
	return _track
