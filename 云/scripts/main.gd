extends Node
## 启动场景：读设置（语言、音量、画质、全屏）并套用，然后进第一关。
## 以后有存档 / 选关就在这里分流。命令行的调试参数（-- --stage=… 等）原样留给关卡读。

const FIRST_LEVEL := "res://scenes/level_forest.tscn"


func _ready() -> void:
	GameSettings.load_and_apply()
	get_tree().change_scene_to_file.call_deferred(FIRST_LEVEL)
