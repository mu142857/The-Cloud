extends RefCounted
## 第一关小游戏 run_credits：奔跑片头的制作人员字幕（docs/剧情改动/第一关新版_实现规格.md 第 6 步）。
##   晨跟着鹿跑起来一小段以后：主题曲 + 制作人员字幕一条条淡入淡出 +（剧本另写）潜意识字「好熟悉的感觉……」。
##
## 剧本步骤：{"do": "mechanic", "id": "run_credits", "wait": false}
##   可选："file": 名单文件（默认 res://data/credits.json）。
##   不挡剧情：run() 建好字幕层就返回（字幕和音乐自己往下播，播完自己释放），所以 runner 照常 await 也不会卡住；wait: false 是给读剧本的人看的。
## 名单：data/credits.json（entries: [{role: {zh, en}, names: [...]}]，时间 start_delay / fade_in / hold / fade_out / gap，music）。
##   现在是占位名单，等作者改。
## 音乐：credits.json 的 music（默认 res://audio/music/theme.ogg）有这个文件就放（Music 总线，2 秒淡入，放完自己释放）；没有就只出字。
## 中途要收掉（比如跑到头了还没播完）：level.get_node("RunCredits").finish(0.8)（字淡掉；音乐不停，要停用 finish(0.8, true)）。

const ID := "run_credits"
const FILE := "res://data/credits.json"
const MUSIC := "res://audio/music/theme.ogg"
const LAYER := 30                     # 在 UI（20）上面、黑幕 Top（50）下面：黑屏转场会把字一起盖住
const POS := Vector2(28, 194)         # 左下：晨往右跑，镜头里左下空着；天上留给潜意识字
const ROLE_COL := Color("#9fb3a8")    # 职务：暗一档的青绿灰
const NAME_COL := Color("#e6ece6")    # 名字：发白
const RISE := 3.0                     # 淡入时往上浮几像素（sine 缓停）


static func load_list(path := FILE) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var v = JSON.parse_string(FileAccess.get_file_as_string(path))
	return v if v is Dictionary else {}


## 一条字幕从出现到下一条开始的秒数 / 全部秒数 / 读主题曲：写在下面的 Credits 里（内部类调不到外层的静态函数）
static func slot_sec(d: Dictionary) -> float:
	return Credits.slot_sec(d)


static func total_sec(d: Dictionary) -> float:
	return float(d.get("start_delay", 0.6)) + Credits.slot_sec(d) * (d.get("entries", []) as Array).size()


static func load_music(path: String) -> AudioStream:
	return Credits.load_music(path)


# ======================================================================= 演出
var speed := 1.0


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	if r.ff:
		return
	var d := load_list(str(st.get("file", FILE)))
	if d.is_empty():
		push_warning("run_credits：%s 读不到，不出字幕" % st.get("file", FILE))
		return
	if d.get("placeholder", false):
		print("MECH %s：credits.json 还是占位名单" % ID)
	var old := lv.get_node_or_null("RunCredits")
	if old != null:
		old.free()
	var layer := Credits.new()
	layer.name = "RunCredits"
	layer.layer = LAYER
	lv.add_child(layer)
	layer.play(d, speed, lv)
	print("MECH %s started entries=%d sec=%.1f" % [ID, (d.get("entries", []) as Array).size(), total_sec(d) / speed])


## 自动玩：一样不挡，只是快 4 倍（测试时一会儿就播完）
func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	speed = 4.0
	await run(lv, w, r, st)


func ff(_r: Node, _st: Dictionary) -> void:
	pass                                       # 没有进度；跳节拍就不出字幕


func check(_story: Node, st: Dictionary) -> Array:
	var out: Array = []
	var d := load_list(str(st.get("file", FILE)))
	if d.is_empty():
		out.append("credits 名单 %s 读不到" % st.get("file", FILE))
	elif (d.get("entries", []) as Array).is_empty():
		out.append("credits 名单是空的")
	elif d.get("placeholder", false):
		out.append("info: credits.json 还是占位名单，等作者改")
	if load_music(str(d.get("music", MUSIC))) == null:
		out.append("info: 主题曲 %s 还没有，只出字幕" % d.get("music", MUSIC))
	return out


# ----------------------------------------------------------------------- 字幕层（自己播、播完自己释放）
class Credits extends CanvasLayer:
	static func slot_sec(d: Dictionary) -> float:
		return float(d.get("fade_in", 0.9)) + float(d.get("hold", 2.4)) + float(d.get("fade_out", 0.9)) + float(d.get("gap", 0.5))

	static func load_music(path: String) -> AudioStream:
		if ResourceLoader.exists(path):
			return load(path) as AudioStream
		if FileAccess.file_exists(path):           # 刚放进来、编辑器还没导入：直接读 ogg
			return AudioStreamOggVorbis.load_from_file(ProjectSettings.globalize_path(path))
		return null

	var _tw: Tween
	var _music: AudioStreamPlayer
	var _box: Control

	func play(d: Dictionary, speed: float, lv: Node) -> void:
		var k := 1.0 / maxf(0.01, speed)
		_start_music(d, lv, k)
		_tw = create_tween()
		_tw.tween_interval(float(d.get("start_delay", 0.6)) * k)
		for e in d.get("entries", []):
			if e is Dictionary:
				_tw.tween_callback(_show.bind(e, d, k))
				_tw.tween_interval(slot_sec(d) * k)
		_tw.tween_callback(queue_free)

	## 一条：职务（暗一档）+ 名字（几个名字一行，全角空格隔开），一起淡入、往上浮 3 像素、停、淡出
	func _show(e: Dictionary, d: Dictionary, k: float) -> void:
		var box := Control.new()
		box.mouse_filter = Control.MOUSE_FILTER_IGNORE
		box.position = POS + Vector2(0, RISE)
		box.modulate.a = 0.0
		add_child(box)
		_box = box
		var names: Array = []
		for n in e.get("names", []):
			names.append(I18n.pick(n))
		var role := _label(I18n.pick(e.get("role", "")), ROLE_COL)
		box.add_child(role)
		var nm := _label("　".join(PackedStringArray(names)), NAME_COL)
		nm.position = Vector2(0, 17)
		box.add_child(nm)
		var fi := float(d.get("fade_in", 0.9)) * k
		var fo := float(d.get("fade_out", 0.9)) * k
		var tw := box.create_tween()
		tw.set_parallel(true)
		tw.tween_property(box, "modulate:a", 1.0, fi).set_trans(Tween.TRANS_SINE)
		tw.tween_method(func(y: float): box.position.y = round(y), POS.y + RISE, POS.y, fi).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
		tw.chain().tween_interval(float(d.get("hold", 2.4)) * k)
		tw.chain().tween_property(box, "modulate:a", 0.0, fo).set_trans(Tween.TRANS_SINE)
		tw.chain().tween_callback(box.queue_free)

	func _label(t: String, c: Color) -> Label:
		var l := Label.new()
		l.text = t
		l.add_theme_font_override("font", UITheme.font())
		l.add_theme_font_size_override("font_size", 14)
		l.add_theme_color_override("font_color", c)
		l.add_theme_color_override("font_shadow_color", Color(0.02, 0.05, 0.05, 0.45))
		l.add_theme_constant_override("shadow_offset_x", 0)
		l.add_theme_constant_override("shadow_offset_y", 1)
		l.mouse_filter = Control.MOUSE_FILTER_IGNORE
		return l

	## 主题曲：Music 总线，从 -30 dB 用 2 秒淡到 0；挂在关卡下面（字幕播完、这一层释放了，歌照样放完），放完自己释放
	func _start_music(d: Dictionary, lv: Node, k: float) -> void:
		var stream: AudioStream = load_music(str(d.get("music", MUSIC)))
		if stream == null:
			print("MECH run_credits：没有主题曲，只出字幕")
			return
		var old := lv.get_node_or_null("ThemeMusic")
		if old != null:
			old.queue_free()
		_music = AudioStreamPlayer.new()
		_music.name = "ThemeMusic"
		_music.stream = stream
		_music.bus = "Music" if AudioServer.get_bus_index("Music") >= 0 else "Master"
		_music.volume_db = -30.0
		lv.add_child(_music)
		_music.play()
		_music.finished.connect(_music.queue_free)
		_music.create_tween().tween_property(_music, "volume_db", 0.0, 2.0 * k).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)

	## 提前收掉：字淡掉（stop_music = 歌也淡掉停）
	func finish(sec := 0.8, stop_music := false) -> void:
		if _tw != null and _tw.is_valid():
			_tw.kill()
		if is_instance_valid(_box):
			_box.create_tween().tween_property(_box, "modulate:a", 0.0, sec)
		if stop_music and is_instance_valid(_music):
			var m := _music
			var tw := m.create_tween()
			tw.tween_property(m, "volume_db", -40.0, sec)
			tw.tween_callback(m.queue_free)
		var t := create_tween()
		t.tween_interval(sec)
		t.tween_callback(queue_free)
