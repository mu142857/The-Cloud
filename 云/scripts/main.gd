extends Node
## 启动场景：读设置（语言、音量、画质、全屏）并套用，然后进第一关。
## 以后有存档 / 选关就在这里分流。命令行的调试参数（-- --stage=… 等）原样留给关卡读。
##
## 11-08 作者「最开始黑屏加载这里，可以在左下角放一个鲸鱼妹妹转圈的动画，正好表示游戏正在加载」：
## 第一关改成后台线程加载（ResourceLoader.load_threaded_request），等的时候左下角转泥芙（scripts/loading_spin.gd）。
## - 加载很快（< SHOW_AFTER 秒）就不出现，免得一闪。
## - 出现了就转完这一圈淡出再切（后面紧接「建议佩戴耳机」，作者：那里不能有加载动画）。
## - 底色和 boot_splash/bg_color 一样，和引擎启动那一下接得上。
## 注意：关卡 _ready 本身在主线程跑，切过去那一瞬转圈会停一下。

const FIRST_LEVEL := "res://scenes/level_forest.tscn"
const Spin := preload("res://scripts/loading_spin.gd")
const SHOW_AFTER := 0.15           # 秒；加载比这快就不出现
const BG := Color(0.031, 0.031, 0.039, 1)

var _t := 0.0
var _spin: Spin
var _leaving := false


func _ready() -> void:
	GameSettings.load_and_apply()
	var layer := CanvasLayer.new()
	add_child(layer)
	var bg := ColorRect.new()
	bg.color = BG
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(bg)
	_spin = Spin.new()
	layer.add_child(_spin)
	if ResourceLoader.load_threaded_request(FIRST_LEVEL) != OK:
		get_tree().change_scene_to_file.call_deferred(FIRST_LEVEL)
		set_process(false)


func _process(delta: float) -> void:
	_t += delta
	if _leaving:
		return
	var st := ResourceLoader.load_threaded_get_status(FIRST_LEVEL)
	if st == ResourceLoader.THREAD_LOAD_LOADED:
		_leaving = true
		if not _spin.visible:
			_go()
		else:
			_spin.hide_spin(_go)
	elif st == ResourceLoader.THREAD_LOAD_FAILED or st == ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
		_leaving = true
		get_tree().change_scene_to_file.call_deferred(FIRST_LEVEL)
	elif not _spin.visible and _t >= SHOW_AFTER:
		_spin.show_spin()


func _go() -> void:
	var ps := ResourceLoader.load_threaded_get(FIRST_LEVEL) as PackedScene
	if ps == null:
		get_tree().change_scene_to_file.call_deferred(FIRST_LEVEL)
	else:
		get_tree().change_scene_to_packed.call_deferred(ps)
