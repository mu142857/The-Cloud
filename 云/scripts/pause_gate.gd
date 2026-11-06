extends CanvasLayer
## 设置 = 暂停（11-05 作者「设置键消失也是一个大问题，设置就是暂停」）。
## 齿轮和设置面板放在这一层：最上面（比黑边、对话、小游戏、结束卡都高），标题、剧情、对话、小游戏、过场都在。
## 这个节点永远在关卡子节点的最后一个：_input 是后面的节点先收到，所以 Esc 和点齿轮不会被小游戏、对话框先吃掉。
## 打开设置 = get_tree().paused（level_forest._pause_tree）。这一层 PROCESS_MODE_ALWAYS，别的都停：
##   _process、绑节点的 tween、Timer、动画、粒子、create_timer(x, false)（游戏里的 await 都写 false，默认的 true 暂停时还在走）。
##   process_frame 信号暂停时也发：游戏里等一帧都写 await StoryState.frame(get_tree())，别直接 await process_frame。
##   声音：音效、环境声跟着停，关掉原地接着放；配乐（bgm.gd）不停，也不重开，调音量听得见。
##   停不住的：shader 里的 TIME（水面、雾、水下光斑）接着动，不会跳。
## 关卡的 _input 暂停时收不到，所以暂停时制作人员页的按键也从这里转过去。

const LAYER := 130

var level: Node
var ui_root: Control            # 齿轮、设置面板、暗幕、制作人员页都放在这下面


func _init() -> void:
	layer = LAYER
	process_mode = Node.PROCESS_MODE_ALWAYS
	name = "PauseGate"
	ui_root = Control.new()
	ui_root.name = "Root"
	ui_root.theme = UITheme.get_theme()
	ui_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	ui_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(ui_root)


func _process(_delta: float) -> void:
	var p := get_parent()
	if p != null and get_index() != p.get_child_count() - 1:
		p.move_child(self, -1)
	level.gear_tick()


func _input(event: InputEvent) -> void:
	level.gate_input(event)


func _exit_tree() -> void:
	get_tree().paused = false            # 换章 / 重开时不带着暂停进下一个场景
