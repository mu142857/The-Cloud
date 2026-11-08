extends AudioStreamPlayer
## 11-08：起身、闪回和兔子舞步共用五级蓄力 + 释放。每次只播一个切片，连按时重启并取消上一次的淡出。

const PATHS := ["res://audio/sfx/qte_rise.ogg", "res://audio/sfx/qte_rise.wav"]
const STEPS := 5
const RELEASE_AT := 2.0
const STEP_SEC := RELEASE_AT / STEPS
const STEP_FADE := 0.06

var gain_db := -6.0
var _fade: Tween


func _ready() -> void:
	for path in PATHS:
		if ResourceLoader.exists(path):
			stream = load(path)
			break


## step 从 1 开始。各段按各自的按键次数映射到五个音，第一下和最后一级保留音阶两端。
func play_step(step: int, total_steps := STEPS) -> void:
	if stream == null:
		return
	var progress := clampf(float(step - 1) / float(maxi(1, total_steps - 1)), 0.0, 1.0)
	var index := roundi(progress * (STEPS - 1))
	_play_slice(index * STEP_SEC)
	_fade = create_tween()
	_fade.tween_interval(STEP_SEC - STEP_FADE)
	_fade.tween_property(self, "volume_db", -50.0, STEP_FADE)
	_fade.tween_callback(stop)


func play_release() -> void:
	if stream != null:
		_play_slice(RELEASE_AT)


func _play_slice(from: float) -> void:
	if _fade != null:
		_fade.kill()
	volume_db = gain_db
	play(from)
