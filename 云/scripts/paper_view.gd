extends RefCounted
## 第一关小游戏 paper_view：全屏看那张双面纸（docs/剧情改动/第一关新版_实现规格.md 第 8 步）。
##   正面 = 大象的画（art/forest_story/drawing_closeup.png），背面 = 手画的地图（art/forest_story/paper_map.png：
##   同一张纸翻过来，折痕左右镜像；森林 → 河 → 云层，一条路从森林一直画到云上）。放大 2 倍居中，四周压暗。
##   A / D、← →、或点一下鼠标 = 翻面（纸横向压扁到 0 再展开，sine 曲线，0.36 秒）；E / 空格 / 回车 / Esc / 右键 = 收起。
##
## 剧本步骤：{"do": "mechanic", "id": "paper_view"}
##   可选：
##     "side": "back"   一打开就是地图那面（默认 "front" 大象）
##     "flip": false    不许翻（拿到地图以前：第 8 步在背包里点大象的画，只看正面）
##     "reveal": true   打开是正面，停 0.9 秒自己翻到地图（追逐结束、「大象画的背面就是地图」那一下）；翻完照常能看、能翻、能收起
##     "sec": 2.5       不等玩家，这么多秒后自己收起（按键可以提前收）；第 8 步「全屏大象画 → 直接黑屏进闪回」用
##     "sets": [flag…]  收起时设上
## 进度：无（每次打开都从头看）。

const ID := "paper_view"
const FRONT := "res://art/forest_story/drawing_closeup.png"
const BACK := "res://art/forest_story/paper_map.png"
const LAYER := 40
const SCALE := 2.0
const DIM := Color(0.02, 0.03, 0.04, 0.78)
const FLIP_SEC := 0.36
const REVEAL_WAIT := 0.9


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
	var _tex := {}
	var _side := "front"
	var _can_flip := true
	var _busy := false
	var _closing := false

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
			await get_tree().create_timer(0.3).timeout
			if _can_flip:
				await flip()
			await get_tree().create_timer(0.3).timeout
			close()
			return
		if st.get("reveal", false) and _side == "front" and _can_flip:
			await get_tree().create_timer(REVEAL_WAIT).timeout
			if not _closing and _side == "front":
				await flip()
		if sec > 0.0:
			_hint.visible = false
			await get_tree().create_timer(sec).timeout
			close()

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
		var tw2 := create_tween()
		tw2.tween_property(_paper, "scale:x", 1.0, FLIP_SEC / 2.0).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
		await tw2.finished
		_busy = false

	func close() -> void:
		if _closing:
			return
		_closing = true
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
