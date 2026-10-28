class_name GameSettings
## 玩家设置：语言、三条音量、特效档位、全屏。存在 user://settings.cfg。
## 不用 autoload（静态变量跨场景也在），启动时 main.gd 调一次 load_and_apply()。
##
## 音量总线：Master / Music / SFX。工程里没有 bus layout 文件，这里开场时现建 Music、SFX 两条（都送到 Master）。
## 声音节点把 bus 设成 "Music" 或 "SFX" 就会跟着设置走。雨声、雷声算 SFX（环境音），以后有配乐就放 Music。
##
## 特效（画质）两档：
##   full：光柱、萤火虫 26 只、林中影子正常、烟多。
##   lite：关光柱、萤火虫 10 只、影子动物出现间隔拉长 2.5 倍、烟减半（给差一点的电脑 / 网页版）。

const PATH := "user://settings.cfg"

static var lang := "en"
static var vol_master := 0.8
static var vol_music := 0.8
static var vol_sfx := 0.8
static var quality := "full"          # "full" / "lite"
static var fullscreen := true
static var loaded := false
static var no_save := false           # 调试 / 截图跑的时候不写设置文件


static func load_and_apply() -> void:
	var cf := ConfigFile.new()
	if cf.load(PATH) == OK:
		lang = str(cf.get_value("game", "lang", lang))
		vol_master = float(cf.get_value("audio", "master", vol_master))
		vol_music = float(cf.get_value("audio", "music", vol_music))
		vol_sfx = float(cf.get_value("audio", "sfx", vol_sfx))
		quality = str(cf.get_value("video", "quality", quality))
		fullscreen = bool(cf.get_value("video", "fullscreen", fullscreen))
	if not I18n.LANGS.has(lang):
		lang = "en"
	loaded = true
	no_save = not OS.get_cmdline_user_args().is_empty()
	I18n.lang = lang
	ensure_buses()
	apply_audio()
	apply_window()


static func save() -> void:
	if no_save:
		return
	var cf := ConfigFile.new()
	cf.set_value("game", "lang", lang)
	cf.set_value("audio", "master", vol_master)
	cf.set_value("audio", "music", vol_music)
	cf.set_value("audio", "sfx", vol_sfx)
	cf.set_value("video", "quality", quality)
	cf.set_value("video", "fullscreen", fullscreen)
	cf.save(PATH)


static func set_lang(l: String) -> void:
	lang = l
	I18n.lang = l


static func ensure_buses() -> void:
	for name in ["Music", "SFX"]:
		if AudioServer.get_bus_index(name) == -1:
			AudioServer.add_bus()
			var i := AudioServer.bus_count - 1
			AudioServer.set_bus_name(i, name)
			AudioServer.set_bus_send(i, "Master")


static func _db(v: float) -> float:
	return -80.0 if v <= 0.001 else linear_to_db(v)


static func apply_audio() -> void:
	AudioServer.set_bus_volume_db(0, _db(vol_master))
	var mi := AudioServer.get_bus_index("Music")
	var si := AudioServer.get_bus_index("SFX")
	if mi >= 0:
		AudioServer.set_bus_volume_db(mi, _db(vol_music))
	if si >= 0:
		AudioServer.set_bus_volume_db(si, _db(vol_sfx))


static func apply_window() -> void:
	if OS.has_feature("web"):
		return                              # 网页版全屏要玩家手势，交给浏览器
	var mode := DisplayServer.window_get_mode()
	var is_fs := mode == DisplayServer.WINDOW_MODE_FULLSCREEN or mode == DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN
	if fullscreen and not is_fs:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	elif not fullscreen and is_fs:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		var size := Vector2i(1440, 810)
		var screen := DisplayServer.screen_get_usable_rect()
		size = size.min(screen.size * 9 / 10)
		DisplayServer.window_set_size(size)
		DisplayServer.window_set_position(screen.position + (screen.size - size) / 2)


static func get_vol(key: String) -> float:
	match key:
		"vol_master": return vol_master
		"vol_music": return vol_music
		"vol_sfx": return vol_sfx
	return 1.0


static func set_vol(key: String, v: float) -> void:
	match key:
		"vol_master": vol_master = v
		"vol_music": vol_music = v
		"vol_sfx": vol_sfx = v


static func lite() -> bool:
	return quality == "lite"
