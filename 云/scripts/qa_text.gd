extends RefCounted
## --qa_text：玩家看得到的每一句字，用游戏字体（UITheme.font()，14 号）按它真正的框量一遍（换行算进去），
## 中英文各量一遍（en 空着就是中文那句）。四章剧本 + data/forest_side_*.json + 物品表 + 通讯器 + 片头字幕都查。
## 框的尺寸照抄各脚本里的常数（改了那边记得改这里的 BOX）。11-04 作者：「字又到外面了」。
## 输出：QA_TEXT <类别> <出处> [zh|en] <问题>「字」，最后 QA_TEXT_SUMMARY 每类几条。用法见 docs/QA_自动检查.md。

const STORIES := ["res://data/story_forest.json", "res://data/story_flight1.json", "res://data/story_river.json",
	"res://data/story_final.json"]
const SIDE_PREFIX := "res://data/forest_side_"
const ITEM_FILES := ["res://data/items.json", "res://data/items_later.json", "res://data/items_final.json"]
const FS := 14
const SCREEN_W := 480.0
## 每种框：w = 一行最宽（wrap = 会自己换行；不换行的就是不许超过 w），lines = 最多几行算正常
const BOX := {
	"say": {"w": 196.0, "wrap": true, "lines": 4},          # story_dialogue.gd MAX_W
	"hint": {"w": 196.0, "wrap": true, "lines": 3},         # 卡关提示（同一个对话框，murmur）
	"bark": {"w": 168.0, "wrap": true, "lines": 3},         # story_bark.gd MAX_W
	"narr": {"w": 440.0, "wrap": true, "lines": 3},         # story_dialogue.gd NARR_W（多了往上长，三行还在画面里）
	"inner": {"w": 300.0, "wrap": true, "lines": 3},        # inner_voice.gd WRAP（fade；drift / spin 是一条飘过去的字带，不算）
	"choice": {"w": 456.0, "wrap": false},                  # story_dialogue.gd _open_menu：x0 最小 10、右边留到 466
	"pick": {"w": 456.0, "wrap": false},
	"key_prompt": {"w": 470.0, "wrap": false},              # level_forest.gd _key_prompt（480 宽居中）
	"toast": {"w": 440.0, "wrap": false},                   # story_dialogue.gd toast（图标 20 + 字，居中）
	"objective": {"w": 400.0, "wrap": false},               # 左上角 x 8 起，右上角背包按钮 459 起，中间还有燃料表
	"side_objective": {"w": 447.0, "wrap": false},          # 「（可选）」那一行（同时开着的全部连起来）
	"item_name": {"w": 160.0, "wrap": false},               # 背包详情名字（x 130，旁边还有【纪念品】/【任务】）
	"item_desc": {"w": 212.0, "wrap": true, "lines": 12},   # 背包描述框 212 宽（能滚，太长也难读）
	"journal": {"w": 200.0, "wrap": true, "lines": 6},      # 日记一条（描述框 212 减去「· 」）
	"phone": {"w": 140.0, "wrap": true, "lines": 6},        # phone_ui.gd BUBBLE_MAX（一条气泡）
	"flashback": {"w": 460.0, "wrap": false},               # flashback.gd：一句一行居中，不换行
	"credits": {"w": 440.0, "wrap": false},
}

var font: Font
var found: Array = []          # [{cat, where, lang, msg, text}]
var _side_objs: Array = []     # 支线文件的 objectives（拼成一行量）


func run() -> Array:
	font = UITheme.font()
	for p in STORIES:
		_story(p, str(p).get_file())
	for p in _side_files():
		_story(p, str(p).get_file())
	_side_line()
	for p in ITEM_FILES:
		_items_file(p)
	for p in _side_files():
		var d = _json(p)
		if d is Dictionary:
			_items(d.get("items", []), str(p).get_file())
	_phone_file()
	_credits_file()
	return found


func _side_files() -> Array:
	var out: Array = []
	var da := DirAccess.open(SIDE_PREFIX.get_base_dir())
	if da == null:
		return out
	for f in da.get_files():
		if f.begins_with(SIDE_PREFIX.get_file()) and f.ends_with(".json"):
			out.append(SIDE_PREFIX.get_base_dir().path_join(f))
	out.sort()
	return out


func _json(p: String):
	return JSON.parse_string(FileAccess.get_file_as_string(p)) if FileAccess.file_exists(p) else null


## 一段字（{zh, en}）在某种框里量两遍
func check(cat: String, where: String, d) -> void:
	if not d is Dictionary:
		return
	var zh := str(d.get("zh", ""))
	var en := str(d.get("en", ""))
	if zh != "":
		_one(cat, where, "zh", zh)
	if en != "" or zh != "":
		_one(cat, where, "en", en if en != "" else zh)


func _one(cat: String, where: String, lang: String, text: String) -> void:
	var b: Dictionary = BOX[cat]
	var w: float = b["w"]
	if not b.get("wrap", false):
		var tw := 0.0
		for line in text.split("\n"):
			tw = maxf(tw, font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, FS).x)
		if tw > w + 0.5:
			_flag(cat, where, lang, "宽 %d > %d（出框）" % [int(tw), int(w)], text)
		return
	var n := lines_of(text, w)
	if n > int(b.get("lines", 99)):
		_flag(cat, where, lang, "%d 行 > %d 行" % [n, int(b["lines"])], text)


## 按 Label 的 AUTOWRAP_WORD_SMART 那样换行，数几行
func lines_of(text: String, w: float) -> int:
	var n := 0
	var lh := font.get_height(FS)
	for para in text.split("\n"):
		if para == "":
			n += 1
			continue
		var sz := font.get_multiline_string_size(para, HORIZONTAL_ALIGNMENT_LEFT, w, FS, -1,
			TextServer.BREAK_MANDATORY | TextServer.BREAK_WORD_BOUND | TextServer.BREAK_ADAPTIVE)
		n += maxi(1, int(round(sz.y / lh)))
	return n


func _flag(cat: String, where: String, lang: String, msg: String, text: String) -> void:
	found.append({"cat": cat, "where": where, "lang": lang, "msg": msg, "text": text})


# ----------------------------------------------------------------------- 剧本
func _story(p: String, fn: String) -> void:
	var d = _json(p)
	if not d is Dictionary:
		return
	var sc: Dictionary = d.get("scenes", {})
	for sid in sc:
		for st in sc[sid]:
			if st is Dictionary:
				_step("%s:%s" % [fn, sid], st)
	for o in d.get("objectives", []):
		if o is Dictionary:
			if fn.begins_with("forest_side_"):
				_side_objs.append(o)
			else:
				check("objective", fn + ":objectives", o)
	for h in d.get("hints", []):
		if not h is Dictionary:
			continue
		for l in h.get("lines", []):
			check("hint", fn + ":hints", l)
		if h.has("zh"):
			check("hint", fn + ":hints", h)
	var ow = d.get("one_way", {})
	if ow is Dictionary and ow.has("zh"):
		check("inner", fn + ":one_way", ow)


func _step(where: String, st: Dictionary) -> void:
	if st.has("say"):
		check("bark" if st.get("bark", false) else "say", where, st)
		return
	if st.has("narr"):
		check("narr", where, st["narr"])
		return
	if str(st.get("do", "")) == "cycle":
		for l in st.get("lines", []):
			if l is Dictionary:
				_step(where, l)
		return
	match str(st.get("do", "")):
		"inner":
			if str(st.get("style", "drift")) == "fade" and not st.get("clear", false):
				check("inner", where, st)
		"choice":
			for o in st.get("options", []):
				check("choice", where, {"zh": "  " + str(o.get("zh", "")), "en": "  " + str(o.get("en", "")) if str(o.get("en", "")) != "" else ""})
		"pick":
			for o in st.get("options", []):
				if o is Dictionary and o.get("label", null) is Dictionary:
					check("pick", where, o["label"])
		"key_prompt":
			check("key_prompt", where, st)
		"journal":
			check("journal", where, st)
		"phone_msg":
			_phone_text(where, st)
		"flashback":
			for l in st.get("lines", []):
				check("flashback", where, l)
		"keepsake_choice", "mechanic":
			for k in ["look", "lines"]:
				var lk = st.get(k, {})
				if lk is Dictionary:
					for key in lk:
						if lk[key] is Array:
							for s2 in lk[key]:
								if s2 is Dictionary:
									_step(where + "." + str(key), s2)
			for k2 in ["put_back", "route_look"]:
				for s3 in st.get(k2, []):
					if s3 is Dictionary:
						_step(where, s3)


func _phone_text(where: String, st: Dictionary) -> void:
	for lang in ["zh", "en"]:
		var t := str(st.get(lang, ""))
		if t == "":
			t = str(st.get("zh", ""))
		for para in t.split("\n"):           # 换行 = 几条连续气泡，一条一条量
			if para != "":
				_one("phone", where, lang, para)
	var rp = st.get("reply", null)
	if rp is Dictionary:
		check("phone", where + "(reply)", rp)


## 「（可选）」那一行：最坏的时候支线目标全开着，拼成一行（level_forest.gd _update_objective 的拼法）
func _side_line() -> void:
	if _side_objs.is_empty():
		return
	for lang in ["zh", "en"]:
		var parts: Array = []
		for o in _side_objs:
			var t := str(o.get(lang, ""))
			parts.append(t if t != "" else str(o.get("zh", "")))
		# 和 level_forest.gd _side_line 一样：放不下的后面写「等 N 件」
		var head := "（可选）" if lang == "zh" else "(Optional) "
		var sep := "　" if lang == "zh" else " / "
		var tail_f := "　等 %d 件" if lang == "zh" else " +%d more"
		var shown: Array = []
		for i in parts.size():
			var rest := parts.size() - i - 1
			var cand: String = head + sep.join(shown + [parts[i]]) + ("" if rest == 0 else tail_f % rest)
			if font.get_string_size(cand, HORIZONTAL_ALIGNMENT_LEFT, -1, FS).x > 440.0 and not shown.is_empty():
				break
			shown.append(parts[i])
		var left := parts.size() - shown.size()
		var line: String = head + sep.join(shown) + ("" if left == 0 else tail_f % left)
		_one("side_objective", "forest_side_*:objectives（全开着）", lang, line)


# ----------------------------------------------------------------------- 物品 / 通讯器 / 字幕
func _items_file(p: String) -> void:
	var d = _json(p)
	if d is Dictionary:
		_items(d.get("items", []), str(p).get_file())
	elif d is Array:
		_items(d, str(p).get_file())


func _items(arr: Array, fn: String) -> void:
	for it in arr:
		if not it is Dictionary:
			continue
		var where := "%s:%s" % [fn, it.get("id", "?")]
		check("item_name", where, it.get("name", {}))
		check("item_desc", where, it.get("desc", {}))
		if it.get("desc_fixed", null) is Dictionary:
			check("item_desc", where + "(fixed)", it["desc_fixed"])
		# 拿到东西的提示：「获得：名字」
		var nm = it.get("name", {})
		if nm is Dictionary:
			check("toast", where + "(获得)", {"zh": "获得：" + str(nm.get("zh", "")), "en": "Got: " + str(nm.get("en", "")) if str(nm.get("en", "")) != "" else ""})


func _phone_file() -> void:
	var d = _json("res://data/phone.json")
	if not d is Dictionary:
		return
	var cs = d.get("contacts", {})
	for cid in (cs if cs is Dictionary else {}):
		var c = cs[cid]
		if not c is Dictionary:
			continue
		for m in c.get("history", []):
			if m is Dictionary:
				_phone_text("phone.json:" + str(cid), m)


func _credits_file() -> void:
	var d = _json("res://data/credits.json")
	if not d is Dictionary:
		return
	for e in d.get("entries", []):
		if e is Dictionary:
			check("credits", "credits.json:" + str(e.get("id", "")), e.get("name", {}))
			check("credits", "credits.json:" + str(e.get("id", "")) + "(role)", e.get("role", {}))


## 打印 + 汇总；返回条数
static func report(list: Array) -> int:
	var by := {}
	for f in list:
		print("QA_TEXT %s %s [%s] %s「%s」" % [f["cat"], f["where"], f["lang"], f["msg"], str(f["text"]).replace("\n", "⏎")])
		by[f["cat"]] = int(by.get(f["cat"], 0)) + 1
	var parts: Array = []
	for k in by:
		parts.append("%s=%d" % [k, by[k]])
	print("QA_TEXT_SUMMARY total=%d %s" % [list.size(), " ".join(parts)])
	return list.size()
