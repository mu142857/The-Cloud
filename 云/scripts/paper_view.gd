extends RefCounted
## 第一关小游戏 paper_view：全屏看那张双面纸（docs/剧情改动/第一关新版_实现规格.md 第 8 步）。
##   正面 = 大象的画（art/forest_story/drawing_closeup.png），背面 = 手画的星球航线图（art/forest_story/paper_map.png，tools/paper_map_art.py 出：
##   同一张纸翻过来，折痕左右镜像；母星 → 森林星 → 绕开碎石带 → 河流星 → 云层星（上面有小镇）→ 分三路：小镇 / 芦苇星 / 回母星）。放大 2 倍居中，四周压暗。
##   地名不画进图，翻到背面时用游戏字体叠上去（BACK_LABELS，中英文跟设置走）。
##   A / D、← →、或点一下鼠标 = 翻面（纸横向压扁到 0 再展开，sine 曲线，0.36 秒）；E / 空格 / 回车 / Esc / 右键 = 收起。
##
## 剧本步骤：{"do": "mechanic", "id": "paper_view"}
##   可选：
##     "side": "back"   一打开就是地图那面（默认 "front" 大象）
##     "flip": false    不许翻（拿到地图以前：第 8 步在背包里点大象的画，只看正面）
##     "reveal": true   打开是正面，停 0.9 秒自己翻到地图（追逐结束、「大象画的背面就是地图」那一下）；翻完照常能看、能翻、能收起
##     "sec": 2.5       不等玩家，这么多秒后自己收起（按键可以提前收）；第 8 步「全屏大象画 → 直接黑屏进闪回」用
##     "sets": [flag…]  收起时设上
##     "out": "black"   收起时不淡掉露出场景，而是整屏（连纸）慢慢压到全黑（OUT_BLACK 秒），黑到底就把剧本的黑幕（runner._blackout_step，
##                      BLACKOUT_LAYER 35）铺上再拿掉这一层，下一步（闪回 enter: lids）从黑里睁眼。11-08 作者：「查看大象的画以后，
##                      应该有一个渐变过渡到黑的过程，然后黑屏直接睁眼效果到这个回忆杀区域」
## 进度：无（每次打开都从头看）。

const ID := "paper_view"
const FRONT := "res://art/forest_story/drawing_closeup.png"
const BACK := "res://art/forest_story/paper_map.png"
const LAYER := 40
const SCALE := 2.0
const DIM := Color(0.02, 0.03, 0.04, 0.78)
const FLIP_SEC := 0.36
const REVEAL_WAIT := 0.9
const OUT_BLACK := 1.6          # "out": "black"：看完画慢慢压到全黑要多久
const LABEL_INK := Color8(40, 48, 104)
## 背面的地名：[中文, 英文, 中心 x, 上沿 y]，纸上坐标（和 tools/paper_map_art.py 的 LABELS 同步）
const BACK_LABELS := [
	["母星", "Home", 26, 97],
	["森林星", "Forest", 58, 3],
	["河流星", "River", 101, 93],
	["云层星", "Clouds", 149, 5],
	["小镇", "Town", 179, 37],      # 小镇在云层星上（11-07 作者），不单独成星
	["芦苇星", "Reeds", 163, 98],   # 占位名，等作者定
]


static func load_tex(p: String) -> Texture2D:
	return View.load_tex(p)


# ======================================================================= 演出
var auto_mode := false


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	if r.ff:
		ff(r, st)
		return
	var layer := CanvasLayer.new()
	layer.name = "PaperView"
	layer.layer = LAYER
	lv.add_child(layer)
	var v := View.new()
	layer.add_child(v)
	v.setup(st, auto_mode)
	var side: String = await v.done
	if v.out_black and not r.ff and r.has_method("_blackout_step"):
		r._blackout_step(true)                   # 同一帧铺上剧本的黑幕（35，在这一层下面），拿掉这一层也不露出场景
	layer.queue_free()
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))
	print("MECH %s done side=%s" % [ID, side])


## 自动玩：打开，能翻就翻一次，收起
func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	auto_mode = true
	await run(lv, w, r, st)


func ff(_r: Node, st: Dictionary) -> void:
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))


func check(_story: Node, st: Dictionary) -> Array:
	var out: Array = []
	if load_tex(FRONT) == null:
		out.append("正面图 %s 找不到" % FRONT)
	if load_tex(BACK) == null:
		out.append("背面地图 %s 找不到" % BACK)
	if str(st.get("side", "front")) == "back" and st.get("reveal", false):
		out.append("side: back 和 reveal 一起写没意义（已经是地图那面了）")
	return out


# ----------------------------------------------------------------------- 全屏那一张纸
class View extends Control:
	signal done(side: String)

	var _paper: TextureRect
	var _hint: Label
	var _labels: Control
	var _tex := {}
	var _side := "front"
	var _can_flip := true
	var _busy := false
	var _closing := false
	var out_black := false

	static func load_tex(p: String) -> Texture2D:
		if ResourceLoader.exists(p):
			return load(p)
		if FileAccess.file_exists(p):                    # 新画的、编辑器还没导入：直接读 png
			var img := Image.load_from_file(ProjectSettings.globalize_path(p))
			if img != null and not img.is_empty():
				return ImageTexture.create_from_image(img)
		return null

	func setup(st: Dictionary, auto_mode: bool) -> void:
		mouse_filter = Control.MOUSE_FILTER_STOP     # 点到这里的都归它，不漏到后面的世界
		size = Vector2(480, 270)
		var dim := ColorRect.new()
		dim.color = DIM
		dim.size = size
		dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(dim)
		_tex["front"] = load_tex(FRONT)
		_tex["back"] = load_tex(BACK)
		_side = "back" if str(st.get("side", "front")) == "back" else "front"
		out_black = str(st.get("out", "")) == "black"
		_can_flip = bool(st.get("flip", true)) and _tex["back"] != null
		_paper = TextureRect.new()
		_paper.texture = _tex[_side] if _tex[_side] != null else _tex["front"]
		_paper.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		_paper.stretch_mode = TextureRect.STRETCH_SCALE
		_paper.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		_paper.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var ts: Vector2 = _paper.texture.get_size() if _paper.texture != null else Vector2(190, 110)
		_paper.size = ts * SCALE
		_paper.position = ((size - _paper.size) / 2.0 - Vector2(0, 6)).round()
		_paper.pivot_offset = _paper.size / 2.0
		add_child(_paper)
		_build_labels()
		_hint = Label.new()
		_hint.add_theme_font_override("font", UITheme.font())
		_hint.add_theme_font_size_override("font_size", 14)
		_hint.add_theme_color_override("font_color", UITheme.TEXT_DIM)
		_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_hint.size = Vector2(480, 16)
		_hint.position = Vector2(0, 250)
		_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(_hint)
		_set_hint()
		modulate.a = 0.0
		var tw := create_tween()
		tw.tween_property(self, "modulate:a", 1.0, 0.35).set_trans(Tween.TRANS_SINE)
		await tw.finished
		var sec := float(st.get("sec", 0.0))
		if auto_mode:
			await get_tree().create_timer(0.3, false).timeout
			if _can_flip:
				await flip()
			await get_tree().create_timer(0.3, false).timeout
			close()
			return
		if st.get("reveal", false) and _side == "front" and _can_flip:
			await get_tree().create_timer(REVEAL_WAIT, false).timeout
			if not _closing and _side == "front":
				await flip()
		if sec > 0.0:
			_hint.visible = false
			await get_tree().create_timer(sec, false).timeout
			close()

	## 地名挂在纸下面，翻面时跟着纸一起压扁；只有背面显示
	func _build_labels() -> void:
		_labels = Control.new()
		_labels.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_labels.visible = _side == "back"
		_paper.add_child(_labels)
		for row in BACK_LABELS:
			var l := Label.new()
			l.add_theme_font_override("font", UITheme.font())
			l.add_theme_font_size_override("font_size", 14)
			l.add_theme_color_override("font_color", LABEL_INK)
			l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			l.text = str(row[0]) if I18n.is_zh() else str(row[1])
			l.size = Vector2(80, 16)
			l.position = Vector2(float(row[2]) * SCALE - 40.0, float(row[3]) * SCALE)
			l.mouse_filter = Control.MOUSE_FILTER_IGNORE
			_labels.add_child(l)

	func _set_hint() -> void:
		if I18n.is_zh():
			_hint.text = "A / D 翻面　　空格 收起" if _can_flip else "空格 收起"
		else:
			_hint.text = "A / D  flip     Space  close" if _can_flip else "Space  close"

	## 翻面：横向压扁到 0（sine 缓进）→ 换另一面 → 展开（sine 缓停）
	func flip() -> void:
		if _busy or _closing or not _can_flip:
			return
		_busy = true
		var tw := create_tween()
		tw.tween_property(_paper, "scale:x", 0.0, FLIP_SEC / 2.0).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
		await tw.finished
		_side = "back" if _side == "front" else "front"
		_paper.texture = _tex[_side]
		_labels.visible = _side == "back"
		var tw2 := create_tween()
		tw2.tween_property(_paper, "scale:x", 1.0, FLIP_SEC / 2.0).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
		await tw2.finished
		_busy = false

	func close() -> void:
		if _closing:
			return
		_closing = true
		if out_black:                              # 连纸带场景慢慢压到全黑（缓进缓出），黑到底停一下
			_hint.visible = false
			var black := ColorRect.new()
			black.color = Color(0.0, 0.0, 0.0, 0.0)
			black.size = size
			black.mouse_filter = Control.MOUSE_FILTER_IGNORE
			add_child(black)
			var tb := create_tween()
			tb.tween_property(black, "color:a", 1.0, OUT_BLACK).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
			tb.tween_interval(0.25)
			await tb.finished
			done.emit(_side)
			return
		var tw := create_tween()
		tw.tween_property(self, "modulate:a", 0.0, 0.35).set_trans(Tween.TRANS_SINE)
		await tw.finished
		done.emit(_side)

	## 输入：这一层是关卡最后加进去的子节点，_input 比 level_forest.gd 的 _input 先收到；收到的一律吃掉，不漏给对话框 / 走路
	func _input(ev: InputEvent) -> void:
		if _closing:
			get_viewport().set_input_as_handled()
			return
		if ev is InputEventKey and ev.pressed and not ev.echo:
			match ev.keycode:
				KEY_A, KEY_D, KEY_LEFT, KEY_RIGHT:
					flip()
				KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_ESCAPE:
					close()
			get_viewport().set_input_as_handled()
		elif ev is InputEventMouseButton and ev.pressed:
			if ev.button_index == MOUSE_BUTTON_LEFT:
				if _can_flip:
					flip()
				else:
					close()
			elif ev.button_index == MOUSE_BUTTON_RIGHT:
				close()
			get_viewport().set_input_as_handled()
		elif ev is InputEventKey:
			get_viewport().set_input_as_handled()
