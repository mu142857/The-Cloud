extends SceneTree
## --qa_audio：音频硬过渡检查（11-04 作者：「记得音效淡入淡出，我怕有突然开始和突然停的硬过渡，如果之间有真空期你可以考虑把两个淡入淡出的交织在一起」）。
## 不改游戏：这个脚本载入主场景（和直接跑游戏一样，命令行 -- 后面的参数照常给游戏），自己挂在 root 上（换章节 reload 也不丢），
## 每帧把树里所有 AudioStreamPlayer / AudioStreamPlayer2D 扫一遍，只管「长的声音」（流长 ≥ 2 秒：循环的环境声、音乐、长音效）：
##   hard_start  循环的声音一帧里从没在放 → 在放，而且音量已经 > -30 dB（没淡入）；一次性音效（雷、撞、钟）本来就有起音，不算
##   hard_stop   一帧里从在放、音量 > -30 dB → 停了 / 节点没了，而且不是自己放到结尾（没淡出就掐断）
##   jump        在放的时候一帧里音量变了 > 12 dB（两边都 > -40 dB）
##   bus_jump    音频总线一帧里音量变了 > 12 dB
##   gap         「听得见的长声音」从有变成 0、超过 0.3 秒以后又有了（场景之间的真空）
## 白名单：播放器带 meta qa_attack_until（Engine.get_process_frames() 的帧号）时，到那一帧为止的 hard_start / jump 不报——
##   只给「故意的硬起音」用（闪回黑到底那一下紧张的音乐直接起，flashback.gd 的 _music_hit，20 帧），过了那几帧照常查。
## 跑：Godot --headless --audio-driver Dummy --path . -s tools/qa_audio.gd -- --chapter=forest --story_auto
##   每条打印 AUDIO_FLAG …；退出时打印 AUDIO_QA 各类的条数。Dummy 驱动下播放位置照样走。

const AF := preload("res://scripts/audio_fade.gd")
const LONG := 2.0
const LOUD := -30.0
const AUDIBLE := -40.0
const JUMP := 12.0
const GAP := 0.3

var _prev := {}          # instance_id → {db, playing, pos, len, path, name}
var _bus_prev := {}
var _t := 0.0
var _counts := {"hard_start": 0, "hard_stop": 0, "jump": 0, "bus_jump": 0, "gap": 0}
var _seen := {}          # 同一个声音同一类只报前几次
var _audible_last := 0.0 # 上一次有听得见的长声音是什么时候
var _had_audible := false
var _gap_from := -1.0
var _last_names: Array = []


func _initialize() -> void:
	var main := str(ProjectSettings.get_setting("application/run/main_scene"))
	change_scene_to_file.call_deferred(main)
	process_frame.connect(_tick)


func _finalize() -> void:
	var parts: Array = []
	for k in _counts:
		parts.append("%s=%d" % [k, _counts[k]])
	print("AUDIO_QA %s t=%.1f" % [" ".join(parts), _t])


func _stream_len(p: Node) -> float:
	var s: AudioStream = p.get("stream")
	if s == null:
		return 0.0
	return s.get_length()


func _label(p: Node) -> String:
	var s: AudioStream = p.get("stream")
	var rp := s.resource_path.get_file() if s != null and s.resource_path != "" else (str(p.get_meta("snd")) if p.has_meta("snd") else "?")
	var owner_path := str(p.get_path()).replace("/root/", "")
	return "%s @ %s" % [rp, owner_path.left(90)]


func _flag(kind: String, who: String, info: String) -> void:
	var key := kind + "|" + who.get_slice(" @ ", 0)
	var n: int = _seen.get(key, 0)
	_seen[key] = n + 1
	_counts[kind] += 1
	if n < 3:
		print("AUDIO_FLAG %s t=%.2f %s %s" % [kind, _t, who, info])


func _tick() -> void:
	var dt := 1.0 / 60.0
	_t += dt
	var cur := {}
	var audible: Array = []
	for p in root.find_children("*", "AudioStreamPlayer", true, false) + root.find_children("*", "AudioStreamPlayer2D", true, false):
		var len := _stream_len(p)
		if len < LONG:
			continue
		var id := p.get_instance_id()
		var playing: bool = p.playing and not p.stream_paused
		var db: float = p.volume_db
		var pos: float = p.get_playback_position() if playing else 0.0
		cur[id] = {"db": db, "playing": playing, "pos": pos, "len": len, "who": _label(p), "loop": AF.is_loop(p)}
		var attack: bool = p.has_meta("qa_attack_until") and Engine.get_process_frames() <= int(p.get_meta("qa_attack_until"))
		var pr = _prev.get(id, null)
		if playing and db > AUDIBLE:
			audible.append(cur[id]["who"])
		if pr == null:
			if playing and db > LOUD and cur[id]["loop"] and not attack:
				_flag("hard_start", cur[id]["who"], "db=%.1f（第一帧就在放）" % db)
			continue
		if playing and not pr["playing"] and db > LOUD and cur[id]["loop"] and float(pr["pos"]) < float(pr["len"]) - 0.25 and not attack:
			_flag("hard_start", cur[id]["who"], "db=%.1f" % db)
		elif pr["playing"] and not playing and float(pr["db"]) > LOUD and float(pr["pos"]) < float(pr["len"]) - 0.15:
			_flag("hard_stop", cur[id]["who"], "db=%.1f pos=%.1f/%.1f" % [pr["db"], pr["pos"], pr["len"]])
		elif playing and pr["playing"] and absf(db - float(pr["db"])) > JUMP and maxf(db, float(pr["db"])) > AUDIBLE and not attack:
			_flag("jump", cur[id]["who"], "%.1f → %.1f dB" % [pr["db"], db])
	# 上一帧在放、这一帧节点没了（queue_free / 换场景）
	for id in _prev:
		if not cur.has(id):
			var pr: Dictionary = _prev[id]
			if pr["playing"] and float(pr["db"]) > LOUD and float(pr["pos"]) < float(pr["len"]) - 0.15:
				_flag("hard_stop", pr["who"], "节点没了 db=%.1f pos=%.1f/%.1f" % [pr["db"], pr["pos"], pr["len"]])
	_prev = cur
	# 总线
	for i in AudioServer.bus_count:
		var v := AudioServer.get_bus_volume_db(i)
		if _bus_prev.has(i) and absf(v - float(_bus_prev[i])) > JUMP and maxf(v, float(_bus_prev[i])) > AUDIBLE:
			_flag("bus_jump", "bus " + AudioServer.get_bus_name(i), "%.1f → %.1f dB" % [_bus_prev[i], v])
		_bus_prev[i] = v
	# 真空期
	if not audible.is_empty():
		if _had_audible and _gap_from >= 0.0 and _t - _gap_from > GAP:
			_flag("gap", "%.2fs" % (_t - _gap_from), "前：%s　后：%s" % [", ".join(_last_names.slice(0, 2)), ", ".join(audible.slice(0, 2))])
		_gap_from = -1.0
		_had_audible = true
		_last_names = audible
	elif _had_audible and _gap_from < 0.0:
		_gap_from = _t
