extends RefCounted
## 关面板 / 换场景之前把里面还在响的长声音「放走」：挪到 SceneTree 根上、淡出、再删（11-04 作者：不要突然停的硬过渡）。
## 只管长的（流 ≥ 2 秒）或循环的；短的一次性音效让它跟着节点一起没（本来也快放完了）。
##   const AUDIO_FADE := preload("res://scripts/audio_fade.gd")（不用 class_name：编辑器没重新扫描时 headless 认不出新类名）
##   AUDIO_FADE.release(node)            node 下面所有 AudioStreamPlayer / AudioStreamPlayer2D
##   AUDIO_FADE.release(node, 0.6)       淡出秒数
## 在 queue_free / reload_current_scene 之前调（不能在 _exit_tree 里调：那时候不能挪子节点）。

const LONG := 2.0


static func release(node: Node, sec := 0.5) -> void:
	if node == null or not is_instance_valid(node) or not node.is_inside_tree():
		return
	var tree := node.get_tree()
	var found: Array = node.find_children("*", "AudioStreamPlayer", true, false) + node.find_children("*", "AudioStreamPlayer2D", true, false)
	if node is AudioStreamPlayer or node is AudioStreamPlayer2D:
		found.append(node)
	for p in found:
		if not bool(p.get("playing")):
			continue
		var s: AudioStream = p.get("stream")
		if s == null or (s.get_length() < LONG and not is_loop(p)):
			continue
		var old = (p.get_meta("fade_tw") if p.has_meta("fade_tw") else null)
		if old is Tween and (old as Tween).is_valid():
			(old as Tween).kill()
		p.reparent(tree.root, true)                  # 2D 的保留世界坐标（换场景以后声像大概不变，反正马上淡掉）
		var tw := tree.create_tween()
		tw.tween_property(p, "volume_db", -60.0, sec).set_trans(Tween.TRANS_SINE)
		tw.tween_callback(p.queue_free)


## 这个声音是循环的吗（流本身循环，或者 finished 接回了 play）
static func is_loop(p: Node) -> bool:
	var s: AudioStream = p.get("stream")
	if s is AudioStreamWAV and (s as AudioStreamWAV).loop_mode != AudioStreamWAV.LOOP_DISABLED:
		return true
	if (s is AudioStreamOggVorbis or s is AudioStreamMP3) and bool(s.get("loop")):
		return true
	for c in p.get_signal_connection_list("finished"):
		var cb: Callable = c["callable"]
		if cb.get_method() == "play" or cb.get_object() == p and cb.get_method() == "play":
			return true
	return false
