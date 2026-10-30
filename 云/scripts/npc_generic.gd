extends Node2D
## 通用角色（河流篇的妮芙、阿汀、摊主，背景里走过的小人）：读 art/characters/<id>/<id>.json，格式见
## docs/river_rooms_contract.md 第 2 节。鹿、弥洛不用这个（各有自己的脚本）。
##
## 节点的 position = 脚底（踩在地面那一行下面一格，和晨一样：position.y = round(地面) + 1）。
## 帧时长：每个动作自己的 ms（默认 json 顶层 ms，再默认 100）；绝不加速，走得快慢只改移动速度。
## 找动作：anims[名字] → alias[名字] → GENERIC_ALIAS → idle（resolve 返回 "" 时由 story_runner 打 MISSING_ANIM）。
## forms：多套形态（妮芙 land / swim），每套里写的键覆盖顶层；空的那套 = 占位色块。swim 形态整只上下 1 像素慢浮（不改图）。
## 缺图 / 没有 json：画 color 的竖条色块 + 名字（森林规矩：缺图不卡）。
## 跟随（story_runner 的 follow）：follow_to(x) 每帧给目标，弹簧追（先缓起再缓停），停下转向晨；走路动画帧速不变。

const DIR := "res://art/characters/%s/"
const LOOP_ANIMS := ["idle", "walk", "talk", "swim"]
## 剧本里常见的动作名 → 通用的几个（json 里没有对应的就再往下退）
const GENERIC_ALIAS := {
	"hand": "give", "push": "give", "point": "point", "look": "idle", "hold": "hold", "read": "read", "write": "write",
	"nod": "nod", "laugh": "laugh", "smile": "laugh", "wave": "wave", "sit": "sit", "crouch": "crouch", "stand": "idle",
}
const PH_SIZE := Vector2i(12, 34)

var npc_id := ""
var cfg := {}                          # json 原样
var form := ""                         # 现在的形态（没有 forms = ""）
var cur := {}                          # 合并过的当前形态配置
var head := 40.0                       # 对话框锚点：脚底往上多少
var speed := 36.0
var facing := 1
var shadow := true
var ground_fn: Callable                # func(x) -> 地面世界 y（走路时贴地；没有就 y 不变）
var spr: Sprite2D
var _shadow: Sprite2D
var _label: Label
var _ph := false                       # 这套形态是占位色块
var _anim := "idle"
var _anim_def := {}
var _anim_t := 0.0
var _done := false
var _walk_x := NAN
var _walk_speed := 0.0
var _x := 0.0
var _vel := 0.0                         # 跟随的弹簧速度
var _talking := false
var _t := 0.0
var _tex_cache := {}


func setup(id: String) -> void:
	npc_id = id
	name = "Npc_" + id
	var p := (DIR % id) + id + ".json"
	if FileAccess.file_exists(p):
		var j = JSON.parse_string(FileAccess.get_file_as_string(p))
		if j is Dictionary:
			cfg = j
		else:
			print("NPC_WARN %s: json 读不出来" % id)
	_shadow = Sprite2D.new()
	_shadow.texture = _shadow_tex()
	_shadow.offset = Vector2(-6, -1)
	_shadow.centered = false
	add_child(_shadow)
	spr = Sprite2D.new()
	spr.centered = false
	spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	add_child(spr)
	_label = Label.new()
	_label.add_theme_font_size_override("font_size", 8)
	_label.add_theme_font_override("font", ThemeDB.fallback_font)
	_label.add_theme_color_override("font_color", Color(0.9, 0.95, 1.0, 0.8))
	_label.position = Vector2(-16, -PH_SIZE.y - 12)
	_label.visible = false
	add_child(_label)
	var forms: Dictionary = cfg.get("forms", {})
	set_form(str(cfg.get("form", "land" if forms.has("land") else (forms.keys()[0] if not forms.is_empty() else ""))))


func has_form(f: String) -> bool:
	return (cfg.get("forms", {}) as Dictionary).has(f)


func set_form(f: String) -> void:
	form = f
	cur = cfg.duplicate()
	cur.erase("forms")
	var forms: Dictionary = cfg.get("forms", {})
	if forms.has(f) and forms[f] is Dictionary:
		for k in forms[f]:
			cur[k] = forms[f][k]
	head = float(cur.get("head", 40))
	speed = float(cur.get("speed", 36))
	var sheet := _sheet(str(cur.get("sheet", "")))
	_ph = sheet == null or not cur.has("frame")
	if _ph:
		var c := Color(str(cur.get("color", _ph_color())))
		spr.texture = _ph_tex(c)
		spr.hframes = 1
		spr.vframes = 1
		spr.frame = 0
		_label.text = npc_id + ("·" + f if f != "" else "")
		_label.visible = shadow                # 背景走过的小人（shadow = false）占位不写名字
	else:
		_label.visible = false
	var tint: bool = cur.get("tint", true)
	spr.modulate = Color(0.86, 0.87, 0.9) if tint else Color.WHITE
	play(_anim if _anim != "" else "idle", true)


func _ph_color() -> String:
	match npc_id:
		"niff":
			return "#7fc6d6"
		"ting":
			return "#8a7a68"
		"keeper":
			return "#7d746a"
	return "#6d7680"


func _sheet(file: String) -> Texture2D:
	if file == "":
		return null
	if _tex_cache.has(file):
		return _tex_cache[file]
	var p := file if file.begins_with("res://") else (DIR % npc_id) + file
	var t: Texture2D = null
	if ResourceLoader.exists(p):
		t = load(p)
	elif FileAccess.file_exists(p):
		var img := Image.load_from_file(ProjectSettings.globalize_path(p))
		if img != null and not img.is_empty():
			t = ImageTexture.create_from_image(img)
	_tex_cache[file] = t
	return t


static func _ph_tex(c: Color) -> ImageTexture:
	var img := Image.create_empty(PH_SIZE.x, PH_SIZE.y, false, Image.FORMAT_RGBA8)
	img.fill(c)
	var d := c.darkened(0.3)
	for x in PH_SIZE.x:
		img.set_pixel(x, 0, d)
		img.set_pixel(x, PH_SIZE.y - 1, d)
	for y in PH_SIZE.y:
		img.set_pixel(0, y, d)
		img.set_pixel(PH_SIZE.x - 1, y, d)
	img.fill_rect(Rect2i(PH_SIZE.x - 5, 5, 2, 2), Color("#e8f0f4"))     # 眼睛：看得出朝哪边
	return ImageTexture.create_from_image(img)


static func _shadow_tex() -> ImageTexture:
	var img := Image.create_empty(12, 2, false, Image.FORMAT_RGBA8)
	img.fill_rect(Rect2i(1, 0, 10, 2), Color(0.02, 0.04, 0.05, 0.35))
	img.fill_rect(Rect2i(0, 0, 12, 1), Color(0.02, 0.04, 0.05, 0.35))
	return ImageTexture.create_from_image(img)


# ======================================================================= 动作
## 名字 → json 里真有的动作名（没有 = ""）
func resolve(n: String) -> String:
	var anims: Dictionary = cur.get("anims", {})
	if anims.has(n):
		return n
	var al: Dictionary = cur.get("alias", {})
	if al.has(n) and anims.has(str(al[n])):
		return str(al[n])
	for pre in GENERIC_ALIAS:
		if n.begins_with(pre) and anims.has(GENERIC_ALIAS[pre]):
			return str(GENERIC_ALIAS[pre])
	if form == "swim" and anims.has("swim") and n in ["idle", "walk"]:
		return "swim"
	return ""


func has_anim(n: String) -> bool:
	return resolve(n) != ""


## 播一个动作（没有就退回 idle）；返回有没有这个动作
func play(n: String, force := false) -> bool:
	var r := resolve(n)
	var ok := r != ""
	if not ok:
		r = resolve("idle")
	if r == _anim and not force and not _done:
		return ok
	_anim = r if r != "" else "idle"
	_anim_def = (cur.get("anims", {}) as Dictionary).get(_anim, {})
	_anim_t = 0.0
	_done = false
	_show_frame()
	return ok


func talk(on: bool) -> void:
	_talking = on
	if on and has_anim("talk") and _anim in ["idle", "swim", ""]:
		play("talk")
	elif not on and _anim == "talk":
		play("idle")


func face(dir: int) -> void:
	if dir == 0:
		return
	facing = 1 if dir > 0 else -1
	_show_frame()


## story_runner 和鹿 / 弥洛用同一个名字转身
func _set_facing(dir: int) -> void:
	face(dir)


func walk_to(x: float, sp := -1.0) -> void:
	_walk_x = round(x)
	_walk_speed = sp if sp > 0.0 else speed
	_x = position.x
	face(1 if x > position.x else -1)


func is_walking() -> bool:
	return not is_nan(_walk_x)


func stop() -> void:
	_walk_x = NAN
	_vel = 0.0
	if _anim in ["walk", "swim"] or resolve("walk") == _anim:
		play("idle")


## 跟随：每帧给目标 x（弹簧追，欠阻尼一点点就停稳），dir_to = 停下以后朝哪看（晨的 x）
func follow_to(tx: float, look_x: float, delta: float) -> void:
	if is_walking():
		return
	var d := tx - position.x
	var w := 6.0
	var acc := w * w * d - 2.0 * 0.9 * w * _vel
	_vel = clampf(_vel + acc * delta, -speed * 2.2, speed * 2.2)
	if absf(d) < 1.0 and absf(_vel) < 4.0:
		_vel = 0.0
		if absf(look_x - position.x) > 2.0:
			face(1 if look_x > position.x else -1)
		if resolve(_anim) == resolve("walk") and _anim != resolve("idle"):
			play("idle")
		return
	if absf(_x - position.x) > 0.5:
		_x = position.x
	_x += _vel * delta
	position.x = round(_x)
	_snap_y()
	if absf(_vel) > 6.0:
		face(1 if _vel > 0.0 else -1)
		play("walk")


func _snap_y() -> void:
	if ground_fn.is_valid():
		position.y = round(float(ground_fn.call(position.x))) + 1.0


func _process(delta: float) -> void:
	_t += delta
	if not is_nan(_walk_x):
		var d := _walk_x - position.x
		var step := _walk_speed * delta
		if absf(d) <= step:
			position.x = _walk_x
			_walk_x = NAN
			_snap_y()
			play("talk" if _talking and has_anim("talk") else "idle")
		else:
			if absf(_x - position.x) > 0.5:
				_x = position.x
			_x += signf(d) * step
			position.x = round(_x)
			_snap_y()
			play("walk")
	_anim_t += delta
	_show_frame()


func _show_frame() -> void:
	if spr == null:
		return
	var bob := 0.0
	if form == "swim":
		bob = -1.0 if fmod(_t, 2.4) < 1.2 else 0.0          # 整只上下 1 像素慢浮
	if _ph:
		spr.offset = Vector2(-PH_SIZE.x / 2, -PH_SIZE.y + bob)
		spr.flip_h = facing < 0
		_shadow.visible = shadow
		return
	var d: Dictionary = _anim_def
	var sheet := _sheet(str(d.get("sheet", cur.get("sheet", ""))))
	if sheet == null:
		return
	var fr: Vector2 = _v2(d.get("frame", cur.get("frame", [16, 16])))
	var an: Vector2 = _v2(d.get("anchor", cur.get("anchor", [fr.x / 2, fr.y - 1])))
	if spr.texture != sheet:
		spr.texture = sheet
	spr.hframes = maxi(int(sheet.get_width() / fr.x), 1)
	spr.vframes = maxi(int(sheet.get_height() / fr.y), 1)
	var frames: Array = d.get("frames", [0])
	if frames.is_empty():
		frames = [0]
	var ms := float(d.get("ms", cur.get("ms", 100)))
	var i := int(_anim_t * 1000.0 / maxf(ms, 1.0))
	var loop: bool = d.get("loop", _anim in LOOP_ANIMS)
	if loop:
		i = i % frames.size()
	elif i >= frames.size():
		i = frames.size() - 1
		if not _done:
			_done = true
			if not d.get("hold", false):
				play("idle", true)
				return
	spr.frame = clampi(int(frames[i]), 0, spr.hframes * spr.vframes - 1)
	var faces = cur.get("faces", "right")
	var drawn_right := not (str(faces) == "left" or (faces is float and float(faces) < 0.0) or (faces is int and int(faces) < 0))
	spr.flip_h = (facing < 0) == drawn_right
	var ax := an.x if not spr.flip_h else fr.x - 1.0 - an.x
	spr.offset = Vector2(-ax, -an.y - 1.0 + bob)
	_shadow.visible = shadow and form != "swim"


static func _v2(v) -> Vector2:
	if v is Array and (v as Array).size() >= 2:
		return Vector2(float(v[0]), float(v[1]))
	return Vector2(16, 16)
