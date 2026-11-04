extends Node
## 配乐（Music 总线，跟设置里的「音乐」音量走）。挂在 SceneTree 根下的一个节点上，换章节、重开场景都不断。
## 剧本：{"do": "music", "track": "forest"}  换曲（旧的淡出、新的淡入）；可选 "db"、"fade"、"loop"、"then"（不循环的放完接哪首）
##       {"do": "music", "stop": true, "fade": 1.5}  淡出停掉
## story_runner 还会自己调：闪回开始 suspend()、醒来 resume()；燃料二选一时放 space_choice；章节结束 stop()。
## 曲子都在 res://audio/music/<名字>.wav（作者 11-04 给的）；编辑器还没导入时直接读 wav 文件。

const DIR := "res://audio/music/"
## 每首默认多响、要不要循环（作者听了觉得哪首太响，改这里的 db）
const TRACKS := {
	"forest": {"db": -10.0, "loop": true},
	"theme": {"db": -5.0, "loop": false, "then": "forest"},
	"rabbit_beat": {"db": -7.0, "loop": true},
	"space_choice": {"db": -9.0, "loop": true},
}
const NODE_NAME := "BGM"

var _cur: AudioStreamPlayer
var _track := ""
var _then := ""
var _held := ""          # suspend() 时记下的曲子，resume() 接回来


static func get_bgm(tree: SceneTree):
	var n := tree.root.get_node_or_null(NODE_NAME)
	if n == null:
		n = (load("res://scripts/bgm.gd") as GDScript).new()
		n.name = NODE_NAME
		tree.root.add_child.call_deferred(n)
	return n


static func load_track(name: String) -> AudioStream:
	var p := DIR + name + ".wav"
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
	stop(fade)
	_track = name
	_then = then if then != "" else str(cfg.get("then", ""))
	var want_loop: bool = bool(cfg.get("loop", true)) if loop < 0 else loop == 1
	var target: float = float(cfg.get("db", -8.0)) if is_nan(db) else db
	var a := AudioStreamPlayer.new()
	a.stream = s
	a.bus = "Music"
	a.volume_db = -50.0
	add_child(a)
	a.play()
	a.finished.connect(func():
		if not is_instance_valid(a) or a != _cur:
			return
		if want_loop:
			a.play()
		else:
			_track = ""
			if _then != "":
				play(_then, NAN, 2.5))
	create_tween().tween_property(a, "volume_db", target, maxf(fade, 0.05)).set_trans(Tween.TRANS_SINE)
	_cur = a


func stop(fade := 1.5) -> void:
	_track = ""
	if _cur == null or not is_instance_valid(_cur):
		_cur = null
		return
	var a := _cur
	_cur = null
	var tw := create_tween()
	tw.tween_property(a, "volume_db", -50.0, maxf(fade, 0.05)).set_trans(Tween.TRANS_SINE)
	tw.tween_callback(a.queue_free)


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
