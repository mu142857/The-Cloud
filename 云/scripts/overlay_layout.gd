extends RefCounted
## 叠在画面上的小游戏（特写面板、按键提示、字幕、头顶的计数）共用的安全区。
## 11-04 作者：「好像游戏好多文字都会挡到一起」（收音机：选项、台的字幕、按键提示三层叠在屏幕下方）。规矩：
##   ① 对话那一带：屏幕上 BAND_TOP 往下归对话框 / 选项 / 旁白 / 拿到东西的提示（story_dialogue.gd 的 BAND_TOP）。
##      面板一律在它上面结束：panel_pos(面板大小)。
##   ② 字幕（收音机里的台、画面里的说明）放在面板里面或紧挨着面板上沿，不放进对话那一带。
##   ③ 按键提示放在面板上面那一行（hint_y），没有面板就屏幕上方 HINT_Y；对话 / 选项 / 旁白显示的时候藏起来，
##      关了再回来：用 HintLabel，或者自己每帧看 busy(story)。
##   ④ 字幕和选项不同时出：字幕先念 READ_SEC 秒再开选项；选项开着的时候字幕也藏起来（busy）。
##   ⑤ 角色头顶的计数 / 箭头（兔子、大嘴鸟）：说话的框就在头顶，busy 的时候淡掉（BusyFade）。
##   ⑥ 小游戏的面板 / 按键提示出来的时候，左上角的目标、燃料和背包按钮淡掉（hud(story, true)，结束 hud(story, false)），
##      把屏幕最上面一行让给按键提示。
##   没有站在画面里的说话人（收音机、老松树）的对话框在屏幕上方正中（框底 y 39），会压住面板上沿几像素：
##   那是对话框盖在面板的木框上（对话框在面板上面画），不是字叠字，允许。
## 不用 class_name（编辑器还没扫到时会报错）：preload("res://scripts/overlay_layout.gd")。
## 摆位检查：tools/overlay_layout_check.py 照这里的数画示意图（真字体），看有没有叠在一起。

const DLG := preload("res://scripts/story_dialogue.gd")
const BAND_TOP: float = DLG.BAND_TOP    # 对话那一带的上沿（屏幕 y）
const TOP := 34.0                       # 面板最高放到这（上面一行留给按键提示，左上角是目标）
const HINT_Y := 16.0                    # 没有面板时按键提示那一行（16 高）
const HINT_H := 16.0
const READ_SEC := 1.5                   # 字幕先念这么久再开选项
const SCREEN := Vector2(480, 270)


## 面板放哪（屏幕坐标）：水平居中，底边在对话那一带上面 2 像素；放得下就顶到 TOP
static func panel_pos(size: Vector2) -> Vector2:
	var y := minf(TOP, BAND_TOP - 2.0 - size.y)
	return Vector2(roundf((SCREEN.x - size.x) / 2.0), roundf(maxf(0.0, y)))


## 按键提示那一行（面板上沿往上一行；没有面板 = HINT_Y）
static func hint_y(panel_top := -1.0) -> float:
	return HINT_Y if panel_top < 0.0 else maxf(0.0, panel_top - HINT_H - 1.0)


## 小游戏能放字的地方（屏幕坐标）：对话那一带以上
static func safe_text_rect() -> Rect2:
	return Rect2(4.0, 0.0, SCREEN.x - 8.0, BAND_TOP - 2.0)


## 左上角目标 / 燃料 / 背包按钮淡出（hide）/ 淡回来（level_forest.gd 的 hud_fade，树冠缺口那一屏也用它）
static func hud(story: Object, hide: bool) -> void:
	var lv = story.get("level") if story != null else null
	if lv != null and is_instance_valid(lv) and lv.has_method("hud_fade"):
		lv.hud_fade(hide, 0.3)


## 对话框 / 选项 / 旁白 / 自言自语现在有没有在显示
static func busy(story: Object) -> bool:
	if story == null:
		return false
	var d = story.get("dlg")
	return d != null and is_instance_valid(d) and d.has_method("showing") and bool(d.showing())


## 按键提示：一行居中的字，放在 y；对话在显示的时候自己淡掉（只动 self_modulate，modulate 留给调用的人淡入淡出）
class HintLabel extends Label:
	var story: Object

	func _init(st: Object = null, text_: String = "", y := HINT_Y) -> void:
		story = st
		text = text_
		position = Vector2(0, y)
		size = Vector2(SCREEN.x, HINT_H)
		horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_theme_font_override("font", UITheme.font())
		add_theme_font_size_override("font_size", 14)
		add_theme_color_override("font_color", UITheme.TEXT_DIM)
		add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))

	var _k := 1.0

	static func _busy(st: Object) -> bool:              # 内部类调不到外面的静态函数：同一段判断再放一份
		if st == null:
			return false
		var d = st.get("dlg")
		return d != null and is_instance_valid(d) and d.has_method("showing") and bool(d.showing())

	func _process(dt: float) -> void:
		_k = move_toward(_k, 0.0 if _busy(story) else 1.0, dt * 5.0)
		self_modulate.a = ceilf(_k * 4.0) / 4.0           # 4 档，像素字不糊


## 头顶的计数 / 箭头这类：加成它的子节点。对话在显示的时候把父节点淡掉，关了淡回原来的透明度；不显示对话时不碰它
class BusyFade extends Node:
	var story: Object
	var _held := false
	var _a0 := 1.0
	var _k := 1.0

	func _init(st: Object = null) -> void:
		story = st

	static func _busy(st: Object) -> bool:              # 内部类调不到外面的静态函数：同一段判断再放一份
		if st == null:
			return false
		var d = st.get("dlg")
		return d != null and is_instance_valid(d) and d.has_method("showing") and bool(d.showing())

	func _process(dt: float) -> void:
		var p := get_parent() as CanvasItem
		if p == null:
			return
		var b := _busy(story)
		if b and not _held:
			_held = true
			_a0 = p.modulate.a
			_k = 1.0
		if not _held:
			return
		_k = move_toward(_k, 0.0 if b else 1.0, dt * 5.0)
		p.modulate.a = _a0 * ceilf(_k * 4.0) / 4.0
		if not b and _k >= 1.0:
			_held = false
