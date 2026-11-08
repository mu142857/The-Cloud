extends Control
## 剧本步骤 burn_pick：选一件东西烧掉（11-07 作者：第一次教程「选烧什么」要有一个好的模板，以后选烧什么都用它）。
##   作者原话：「利用现在在回忆杀旋转的地图的模板，让小熊也同样的方式在天上飘，所以下方可以选择所有能够烧的物品，选的时候会显示简介，
##   点击以后会交给蛇女。」「不是给或者不给的选项……上方写着，选择你要烧掉的物品，最下方是一排可以烧的物品，
##   选择以后按回车键就会弹出，是否要烧毁名字，选择了就触发动画。」
##
##   {"do": "burn_pick", "id": "c1_bear_pick", "to": "miluo", "scenes": {"deer_bear": "c1_bear_give"}, "then": "c1_bear_b",
##    "items": [...]（可选，不写 = 背包里所有能烧的）, "title": {zh, en}（可选，默认「选择你要烧掉的物品」）}
##
## 画面（480×270）：整屏压暗一层（原场景还看得见）；
##   上方一行标题；
##   中间：选中的那件放大 FLOAT_SCALE 倍，在空中翻着飘——和闪回一里被风吹走的大象照片同一套动法（flashback.gd 的 _paper：
##   前后晃 + 上下两层正弦、rotation 0.2·sin(3.1t)、scale.x 0.6+0.4·cos(3.7t) 窄一下宽一下），换一件时从下面轻轻浮上来；
##   它下面是名字和简介（物品的 desc）；
##   最下方一排格子（和驾驶舱托板同样式，20×20），是能烧的东西；选中的亮一档、上下浮 1 像素。放不下就左右滚（< >）。
## 操作：←/→（A/D）或鼠标移上去 = 换一件；回车 / E / 空格 / 单击 = 弹出「要烧掉「名字」吗？」，「烧掉」/「再想想」（Esc = 再想想）。
## 确认以后：界面淡掉，飘着的那件不再翻、
##   写了 "to"（角色名）：沿一道弧线飞到那个人跟前、缩回原大小再淡掉（教程：交给弥洛，她再说「开个玩笑」还回来）；
##   没写 "to"：就地烧掉（变暖色、往上飘一点、散成几粒火星）。
##   然后 goto scenes[那件]（没有就 then；都没有 = 接着往下播）。选了哪件记进 StoryState 的物件状态（键 = 步骤 id）。
##   东西本身不在这里拿走——剧本自己 take / 设 burned_*（教程里弥洛只是拿过去又还回来）。
## 能烧 = Inventory 里 keepsake_burn / burn > 0、没有 no_burn（大象照片、地图这些 quest 不出现）。一件都没有 = 什么都不弹，直接 then。
## 跳节拍：挑能通到目标 flag 的那件（没有就第一件），不出界面；自动玩：停一下、选第一件、确认
##   （full 先看一眼第二件；加 --burn_pick_back 先按一次「再想想」再确认）。
## story_runner.gd 的 _burn_pick 建它（挂在对话界面下，按键先到这里）：var scene = await play(runner, st)。

signal done(id: String)

const BG := Color(0.02, 0.05, 0.04, 0.88)
const EDGE := Color(0.5, 0.6, 0.55, 0.45)
const DIM := Color(0.02, 0.04, 0.035, 0.62)       # 整屏压暗（不用纯黑）
const NAME_C := Color("#dcc39a")
const DESC_C := Color("#b9c9bf")
const FLOAT_AT := Vector2(240, 78)                  # 飘的中心
const FLOAT_SCALE := 4.0                            # 图标放大几倍（11×13 的熊 → 44×52）
const NAME_Y := 118.0
const DESC_Y := 136.0
const DESC_W := 300.0
const TRAY_Y := 214.0
const KEYS_Y := 240.0
const CAP := 15                                     # 一排最多摆几格（15 × 24 = 360）
const TXT := {
	"title": ["Choose something to burn", "选择你要烧掉的物品"],
	"ask": ["Burn %s?", "要烧掉「%s」吗？"],
	"yes": ["Burn it", "烧掉"],
	"no": ["Not yet", "再想想"],
	"keys": ["← → choose   Enter burn", "← → 挑选   回车 烧掉"],
	"power": ["Power %d", "动力 %d"],
}

var runner: Node
var st: Dictionary
var items: Array[String] = []
var _sel := 0
var _win := 0
var _mode := "pick"              # pick / ask / busy
var _t := 0.0
var _dim: ColorRect
var _title: Label
var _float: Sprite2D
var _float_k := 1.0              # 翻着飘的幅度（确认以后收到 0）
var _float_pop := 0.0            # 换一件时从下面浮上来（1 → 0）
var _name: Label
var _cur_name := ""          # 选中那件的名字（_name 上还带着「· 动力 N」，问「要烧掉…吗」只用名字）
var _desc: Label
var _keys: Label
var _slots: Array[Panel] = []
var _more: Array[Label] = []
var _ask: Panel
var _ask_btns: Array[Label] = []
var _ask_arrow: Label            # 「▸」单独一个 Label：混在按钮字里会让那一行的基线往下掉一点，两个按钮不齐
var _ask_sel := 0
var _flash := {}
var _auto_t := 0.0
var _auto_step := 0


func play(r: Node, step: Dictionary) -> String:
	runner = r
	st = step
	var scenes: Dictionary = st.get("scenes", {}) if st.get("scenes", {}) is Dictionary else {}
	var then := str(st.get("then", ""))
	var key := str(st.get("id", "burn_pick"))
	var kind := str(st.get("kind", ""))
	var real := bool(st.get("burn", false))      # 选完真的从背包烧掉（加燃料、提示）
	var again := bool(st.get("repeat", false))   # 一件接一件挑，直到没有可烧的（或 until_fuel 燃料够了）
	var last := ""
	while true:
		items = burnable(st.get("items", null), kind)
		if items.is_empty():
			return str(scenes.get(last, then)) if last != "" else then
		var chosen := ""
		if r.ff:
			chosen = items[0]
			if r._ff_target != "":
				for id in items:
					if r._leads_to(str(scenes.get(id, then)), r._ff_target):
						chosen = id
						break
		else:
			_reset()
			_build()
			r._ui_shot("burn_pick", 0.8)
			chosen = await done
		StoryState.set_prop(key, chosen)
		print("BURN_PICK %s: %s" % [key, chosen])
		last = chosen
		if real:
			await r._burn_held({"items": [chosen], "no_closeup": true})
			var after = st.get("after", {})
			if after is Dictionary and after.has(chosen):
				for l in r.scenes.get(str(after[chosen]), []):      # 烧完晨的那一句（只放台词，不要 goto）
					if l is Dictionary:
						await r._step(l)
		if bool(st.get("until_fuel", false)) and (not StoryState.fuel_on() or StoryState.fuel() >= StoryState.fuel_need()):
			break                                        # 燃料够了就不用再烧
		if not again:
			break
	return str(scenes.get(last, then))


## 翻着飘的动法（背包里选中的物品也用这一套，level_forest.gd 的 _bag_float_tick）：
## at = 飘的中心，k = 放大倍数，t = 时间，amp = 幅度（0 = 停住），pop = 换一件时从下面浮上来（1 → 0）
static func float_pose(spr: Sprite2D, at: Vector2, k: float, t: float, amp := 1.0, pop := 0.0) -> void:
	var off := Vector2(10.0 * sin(t * 0.8), 5.0 * sin(t * 2.3) + 2.0 * sin(t * 5.1)) * amp
	off.y += 10.0 * pop * pop
	spr.position = (at + off).round()
	spr.rotation = 0.2 * sin(t * 3.1) * amp
	spr.scale = Vector2(k * lerpf(1.0, 0.6 + 0.4 * cos(t * 3.7), amp), k)
	spr.modulate.a = 1.0 - pop


## 再挑一轮前清掉上一轮的界面
func _reset() -> void:
	for c in get_children():
		c.queue_free()
	_slots.clear()
	_more.clear()
	_ask = null
	_ask_btns.clear()
	_sel = 0
	_win = 0
	_mode = "pick"
	_float = null
	_float_k = 1.0
	_float_pop = 0.0
	_flash.clear()
	_auto_t = 0.0
	_auto_step = 0


## 背包里能烧的（同一件有两份只摆一格）；list 给了就只在这几件里挑
static func burnable(list = null, kind := "") -> Array[String]:
	var out: Array[String] = []
	var src: Array = list if list is Array else Inventory.owned
	for v in src:
		var id := str(v)
		if out.has(id) or not Inventory.has(id):
			continue
		var it := Inventory.item(id)
		if it.get("no_burn", false):
			continue
		if kind != "" and str(it.get("fuel_kind", "")) != kind:
			continue
		if int(it.get("keepsake_burn", 0)) > 0 or int(it.get("burn", 0)) > 0:
			out.append(id)
	return out


static func _tx(k: String) -> String:
	var row: Array = TXT[k]
	return row[1] if I18n.is_zh() else row[0]


func _label(text: String, c: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 14)
	l.add_theme_color_override("font_color", c)
	l.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.8))
	l.add_theme_constant_override("shadow_offset_x", 0)
	l.add_theme_constant_override("shadow_offset_y", 1)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


# ======================================================================= 搭界面
func _build() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	size = Vector2(480, 270)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme = UITheme.get_theme()
	if runner.dlg.has_method("_fade_narr_now"):
		runner.dlg._fade_narr_now()            # 前面那句旁白（「给出去，就再也回不到……」）还挂在下面：和点选菜单一样先收掉
	_dim = ColorRect.new()
	_dim.color = DIM
	_dim.size = Vector2(480, 270)
	_dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_dim)
	var tt = st.get("title", null)
	_title = _label(runner.txt(tt) if tt is Dictionary else _tx("title"), UITheme.TEXT)
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_title.size = Vector2(480, 16)
	_title.position = Vector2(0, 14)
	add_child(_title)
	_float = Sprite2D.new()
	_float.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_float.position = FLOAT_AT
	add_child(_float)
	_name = _label("", NAME_C)
	_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_name.size = Vector2(480, 16)
	_name.position = Vector2(0, NAME_Y)
	add_child(_name)
	_desc = _label("", DESC_C)
	_desc.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_desc.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY if I18n.is_zh() else TextServer.AUTOWRAP_WORD_SMART
	_desc.add_theme_constant_override("line_spacing", 1)
	add_child(_desc)
	_keys = _label(_tx("keys"), UITheme.TEXT_DIM)
	_keys.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_keys.size = Vector2(480, 16)
	_keys.position = Vector2(0, KEYS_Y)
	_keys.modulate.a = 0.7
	add_child(_keys)
	for id in items:
		var p := Panel.new()
		p.mouse_filter = Control.MOUSE_FILTER_IGNORE
		p.size = Vector2(20, 20)
		var tr := TextureRect.new()
		tr.texture = Inventory.icon(id)
		tr.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
		tr.set_anchors_preset(Control.PRESET_FULL_RECT)
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		p.add_child(tr)
		add_child(p)
		_slots.append(p)
	if items.size() > CAP:
		for t in ["<", ">"]:
			var m := _label(t, UITheme.TEXT_DIM)
			add_child(m)
			_more.append(m)
	_show_item(true)
	_style()
	modulate.a = 0.0
	create_tween().tween_property(self, "modulate:a", 1.0, 0.35).set_trans(Tween.TRANS_SINE)


## 中间飘的那件 + 名字 + 简介换成选中的
func _show_item(first := false) -> void:
	var id := items[_sel]
	var it := Inventory.item(id)
	_float.texture = Inventory.icon(id)
	_cur_name = runner.txt(it.get("name", id))
	# 11-08 作者：弥洛要「动力至少值100的物品」——名字后面标上这件值多少动力（玩家得看得出够不够 100）
	var pw := maxi(int(it.get("keepsake_burn", 0)), int(it.get("burn", 0)))
	_name.text = _cur_name + ("  ·  " + (_tx("power") % pw) if pw > 0 else "")
	var w := DESC_W if I18n.is_zh() else 360.0
	_desc.text = runner.txt(it.get("desc", ""))
	if I18n.is_zh():
		# 中文逐字换行：最后一行只剩一个字 / 句号（「……又缝回去了」+ 单独一个「。」）就加宽到上一行能装下它
		var per := int(floor(w / 14.0))
		var n := _desc.text.length()
		var rows := ceili(float(n) / float(per))
		if rows > 1 and n - per * (rows - 1) <= 1:
			w = minf(14.0 * ceilf(float(n) / float(rows - 1)) + 2.0, 440.0)
	_desc.size = Vector2(w, 0)
	_desc.custom_minimum_size = Vector2(w, 0)
	_desc.position = Vector2(roundf(240.0 - w / 2.0), DESC_Y)
	if not first:
		_float_pop = 1.0


func _style() -> void:
	for i in _slots.size():
		var on := i == _sel and _mode == "pick"
		_slots[i].add_theme_stylebox_override("panel", UITheme.box(Color(0.06, 0.1, 0.09, 0.85),
			UITheme.ACCENT if on else Color(0.3, 0.4, 0.35, 0.8), 1))
	_keys.visible = _mode == "pick"


func _set_sel(i: int) -> void:
	i = posmod(i, items.size())
	if i == _sel:
		return
	_sel = i
	_show_item()
	_style()
	_sound("ui_click", -14.0, 1.35)


func _sound(n: String, db: float, pitch := 1.0) -> void:
	var f: Callable = runner.dlg.sfx
	if f.is_valid():
		f.call(n, db, pitch)


# ======================================================================= 每帧
func _process(delta: float) -> void:
	if runner == null or _float == null:
		return
	_t += delta
	_layout_tray()
	# 闪回一里那张照片的动法（flashback.gd：PAPER_LEAD ± 18·sin(0.8t)、y 7·sin(2.3t) + 3·sin(5.1t)、rotation、scale.x 翻面）
	if _mode != "busy":
		_float_pop = maxf(0.0, _float_pop - delta * 4.0)
		float_pose(_float, FLOAT_AT, FLOAT_SCALE, _t, _float_k, _float_pop)
	for c in _flash.keys():
		_flash[c] = float(_flash[c]) - delta
		if is_instance_valid(c):
			(c as CanvasItem).modulate = Color(1.8, 1.8, 1.8) if float(_flash[c]) > 0.0 else Color.WHITE
		if float(_flash[c]) <= 0.0:
			_flash.erase(c)
	_auto_tick(delta)


## 一排格子居中摆在下面；放不下（> CAP）就只摆 CAP 格、跟着选中的滚
func _layout_tray() -> void:
	var n := items.size()
	var vis := mini(n, CAP)
	if n > CAP:
		if _sel < _win:
			_win = _sel
		elif _sel >= _win + CAP:
			_win = _sel - CAP + 1
		_win = clampi(_win, 0, n - CAP)
	var x0 := roundf(240.0 - (vis * 24.0 - 4.0) / 2.0)
	for i in n:
		var p := _slots[i]
		var j := i - _win
		p.visible = j >= 0 and j < vis
		if not p.visible:
			continue
		var bob := -1.0 if (i == _sel and _mode == "pick" and fmod(_t, 0.8) < 0.4) else 0.0
		p.position = Vector2(x0 + j * 24.0, TRAY_Y + bob)
	if _more.size() == 2:
		_more[0].visible = _win > 0 and _mode == "pick"
		_more[0].position = Vector2(x0 - 12.0, TRAY_Y + 2.0)
		_more[1].visible = _win + CAP < n and _mode == "pick"
		_more[1].position = Vector2(x0 + vis * 24.0, TRAY_Y + 2.0)


# ======================================================================= 确认
func _open_ask() -> void:
	if _mode != "pick":
		return
	_mode = "ask"
	_style()
	_flash[_slots[_sel]] = 0.2
	_sound("tick", -6.0, 1.0)
	var q := _tx("ask") % _cur_name
	var f := UITheme.font()
	var qw := f.get_string_size(q, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
	var bw := 0.0
	for k in ["yes", "no"]:
		bw += f.get_string_size("▸ " + _tx(k), HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x + 18.0
	var w := roundf(maxf(qw, bw - 18.0) + 28.0)
	_ask = Panel.new()
	_ask.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ask.add_theme_stylebox_override("panel", UITheme.box(BG, EDGE, 1))
	_ask.size = Vector2(w, 50)
	_ask.position = Vector2(roundf(240.0 - w / 2.0), TRAY_Y - 60.0)
	add_child(_ask)
	var ql := _label(q, UITheme.TEXT)
	ql.position = Vector2(roundf((w - qw) / 2.0), 7)
	_ask.add_child(ql)
	_ask_btns.clear()
	_ask_arrow = _label("▸", UITheme.TEXT)
	_ask.add_child(_ask_arrow)
	var x := roundf((w - (bw - 18.0)) / 2.0)
	for k in ["yes", "no"]:
		var l := _label(_tx(k), UITheme.TEXT_DIM)
		l.set_meta("text", _tx(k))
		l.position = Vector2(x, 27)
		_ask.add_child(l)
		_ask_btns.append(l)
		l.set_meta("x", x)
		x += f.get_string_size("▸ " + _tx(k), HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x + 18.0
	_ask_sel = 0
	_style_btns()
	_desc.visible = false                     # 确认框压在简介那一带：先收起来，不叠字
	_ask.modulate.a = 0.0
	create_tween().tween_property(_ask, "modulate:a", 1.0, 0.15)
	runner._ui_shot("burn_pick_ask", 0.4)


func _style_btns() -> void:
	for i in _ask_btns.size():
		var on := i == _ask_sel
		var l := _ask_btns[i]
		var ax: float = l.get_meta("x")
		l.position.x = ax + UITheme.font().get_string_size("▸ ", HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
		l.add_theme_color_override("font_color", UITheme.TEXT if on else UITheme.TEXT_DIM)
		if on and _ask_arrow != null:
			_ask_arrow.position = Vector2(ax, l.position.y)


func _set_btn(i: int) -> void:
	i = posmod(i, _ask_btns.size())
	if i == _ask_sel:
		return
	_ask_sel = i
	_style_btns()
	_sound("ui_click", -14.0, 1.35)


func _press_btn(i: int) -> void:
	if _mode != "ask":
		return
	_set_btn(i)
	_flash[_ask_btns[i]] = 0.2
	if i == 0:
		_confirm()
		return
	_sound("tick", -8.0, 1.1)               # 再想想：回到挑的界面
	if is_instance_valid(_ask):
		_ask.visible = false
		_ask.queue_free()
	_ask = null
	_ask_btns.clear()
	_desc.visible = true
	_mode = "pick"
	_style()


## 烧掉：界面淡掉，飘着的那件交出去 / 就地烧掉，再 done
func _confirm() -> void:
	_mode = "busy"
	var id := items[_sel]
	_sound("tick", -4.0, 0.9)
	_sound("flight_select", -10.0, 1.0)
	if is_instance_valid(_ask):
		_flash[_ask] = 0.2
	await get_tree().create_timer(0.3, false).timeout
	var tw := create_tween().set_parallel(true)
	for c in [_dim, _title, _name, _desc, _keys, _ask] + _slots + _more:
		if is_instance_valid(c):
			tw.tween_property(c, "modulate:a", 0.0, 0.3)
	# 不再翻：从现在的样子平平地收回正面
	var tw2 := create_tween().set_parallel(true)
	tw2.tween_property(_float, "rotation", 0.0, 0.25)
	tw2.tween_property(_float, "scale", Vector2(FLOAT_SCALE, FLOAT_SCALE), 0.25)
	tw2.tween_property(_float, "position", FLOAT_AT, 0.25)
	await tw2.finished
	var to := str(st.get("to", ""))
	var target := Vector2(NAN, NAN)
	if to != "" and runner.npc(to) != null and runner.npc(to).visible:
		target = runner._anchor(to) + Vector2(0, 22)     # 头顶往下一点：胸口 / 手那么高
	if not is_nan(target.x):
		await _give_to(target)
	else:
		await _burn_away()
	done.emit(id)


## 沿一道弧线飞到那个人跟前，缩回原大小，淡掉
func _give_to(target: Vector2) -> void:
	_sound("paper_slide", -8.0, 1.0)
	var from := _float.position
	var tw := create_tween()
	tw.tween_method(func(k: float):
		var p := from.lerp(target, k)
		p.y -= sin(k * PI) * 24.0
		_float.position = p.round()
		_float.scale = Vector2.ONE * lerpf(FLOAT_SCALE, 1.0, k)
		_float.rotation = 0.25 * sin(k * PI), 0.0, 1.0, 0.75).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tw.finished
	_sound("pat", -10.0, 1.0)
	var tw2 := create_tween()
	tw2.tween_property(_float, "modulate:a", 0.0, 0.2)
	await tw2.finished


## 就地烧掉：变暖、往上飘一点、散成火星
func _burn_away() -> void:
	_sound("fire_flare", -8.0, 1.0)
	var tw := create_tween().set_parallel(true)
	tw.tween_property(_float, "modulate", Color(1.7, 1.15, 0.6, 1.0), 0.35)
	tw.tween_property(_float, "position:y", FLOAT_AT.y - 6.0, 0.9).set_trans(Tween.TRANS_SINE)
	tw.chain().tween_property(_float, "modulate:a", 0.0, 0.5)
	var sz := _float.texture.get_size() * FLOAT_SCALE
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	for i in 14:
		var e := ColorRect.new()
		e.size = Vector2(2, 2) if i % 3 == 0 else Vector2(1, 1)
		e.color = UITheme.WARM if i % 2 == 0 else Color("#f0a058")
		e.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var p0 := FLOAT_AT + Vector2(rng.randf_range(-0.4, 0.4) * sz.x, rng.randf_range(-0.3, 0.5) * sz.y)
		e.position = p0.round()
		e.modulate.a = 0.0
		add_child(e)
		var d := rng.randf_range(0.0, 0.45)
		var te := create_tween()
		te.tween_interval(0.25 + d)
		te.tween_property(e, "modulate:a", 1.0, 0.1)
		te.parallel().tween_property(e, "position", (p0 + Vector2(rng.randf_range(-8, 8), -rng.randf_range(18, 34))).round(), 0.9).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
		te.tween_property(e, "modulate:a", 0.0, 0.3)
	await get_tree().create_timer(1.5, false).timeout


# ======================================================================= 输入
func _input(event: InputEvent) -> void:
	if runner == null or runner.auto != "" or _mode == "busy" or _slots.is_empty():
		return
	var vp := get_viewport()
	if event is InputEventKey and event.pressed and not event.echo:
		var k: int = event.keycode
		var prev := k in [KEY_LEFT, KEY_A, KEY_UP, KEY_W]
		var next := k in [KEY_RIGHT, KEY_D, KEY_DOWN, KEY_S]
		var ok := k in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_Z]
		if _mode == "pick":
			if prev:
				_set_sel(_sel - 1)
			elif next:
				_set_sel(_sel + 1)
			elif ok:
				_open_ask()
		else:
			if prev:
				_set_btn(_ask_sel - 1)
			elif next:
				_set_btn(_ask_sel + 1)
			elif ok:
				_press_btn(_ask_sel)
			elif k == KEY_ESCAPE:
				_press_btn(_ask_btns.size() - 1)
		if k != KEY_ESCAPE or _mode != "pick":
			vp.set_input_as_handled()
		return
	if event is InputEventMouseMotion:
		var i := _hit(event.position)
		if i >= 0:
			if _mode == "pick":
				_set_sel(i)
			else:
				_set_btn(i)
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var i := _hit(event.position)
		if _mode == "pick":
			if i >= 0:
				_set_sel(i)
				_open_ask()
			elif Rect2(FLOAT_AT - Vector2(30, 34), Vector2(60, 68)).has_point(event.position):
				_open_ask()                      # 点飘着的那件也行
		elif i >= 0:
			_press_btn(i)
		vp.set_input_as_handled()


## 鼠标在哪：挑的时候 = 第几格，确认框里 = 第几个按钮；都不在 = -1
func _hit(p: Vector2) -> int:
	if _mode == "pick":
		for i in _slots.size():
			var c := _slots[i]
			if c.visible and Rect2(c.position - Vector2(2, 2), c.size + Vector2(4, 4)).has_point(p):
				return i
		return -1
	for i in _ask_btns.size():
		var l := _ask_btns[i]
		if Rect2(l.global_position - Vector2(2, 2), l.get_combined_minimum_size() + Vector2(4, 4)).has_point(p):
			return i
	return -1


## F8 自测：替它选第一件、确认
func dev_skip() -> void:
	if _mode == "pick":
		_open_ask()
	elif _mode == "ask":
		_press_btn(0)


# ======================================================================= 自动玩
func _auto_tick(delta: float) -> void:
	if runner.auto == "" or _mode == "busy":
		return
	_auto_t += delta
	if _auto_t < 0.9:
		return
	_auto_t = 0.0
	if _mode == "pick":
		if _auto_step == 0 and items.size() > 1 and runner.auto == "full":
			_set_sel(1)                          # full：先看一眼别的，再回来
			_auto_step = 1
			return
		_set_sel(0)
		_open_ask()
	elif _mode == "ask":
		if "--burn_pick_back" in OS.get_cmdline_user_args() and _auto_step < 2:
			_auto_step = 2                       # 测试：先按一次「再想想」，回到挑的界面
			_press_btn(1)
			return
		_press_btn(0)

