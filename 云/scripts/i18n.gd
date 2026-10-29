class_name I18n
## 本地化表：所有界面文字和剧情文本都从这里取。默认英文（jam 规则），设置里可以换中文。
##   I18n.t("start")            → "Start" / "开始游戏"
##   I18n.t("burn_total") % [60, 200]
##   I18n.pick({"en": .., "zh": ..})   物品表（data/items.json）那种自带两种语言的字段
## 加新语言：LANGS 里加一个代号，每条后面多写一个字符串。
## 加剧情台词：照 line_* 抄。名字用 who_*。
##
## 换语言以后，正在显示的文字由各个界面自己刷新（level_forest.gd 的 _retext）。

const LANGS := ["en", "zh"]
const LANG_NAMES := {"en": "English", "zh": "中文"}

static var lang := "en"

const STR := {
	# ---- 开场
	"headphones": ["Best played with headphones", "建议佩戴耳机游玩"],
	"press_any": ["Click or press any key", "点击或按任意键继续"],
	"title": ["The Cloud", "云"],
	"title_sub": ["云", "THE CLOUD"],      # 标题下面那行小字：另一种语言的名字
	"start": ["Start", "开始游戏"],
	"skip_again": ["Press again to skip", "再按一次跳过"],
	# ---- 设置
	"settings": ["Settings", "设置"],
	"language": ["Language", "语言"],
	"vol_master": ["Volume", "总音量"],
	"vol_music": ["Music", "音乐"],
	"vol_sfx": ["Sound", "音效"],
	"quality": ["Effects", "特效"],
	"q_full": ["Full", "完整"],
	"q_lite": ["Lite", "精简"],
	"fullscreen": ["Fullscreen", "全屏"],
	"on": ["On", "开"],
	"off": ["Off", "关"],
	"close": ["Close", "关闭"],
	# ---- 背包 / 燃烧值
	"bag": ["Bag", "背包"],
	"bag_empty": ["Nothing here yet.", "这里还什么都没有。"],
	"burn": ["Burn", "燃烧值"],
	"burn_value": ["Burn +%d", "燃烧值 +%d"],
	"burn_total": ["%d / %d", "%d / %d"],
	"to_launch": ["Reach %d to launch the ship", "燃烧值到 %d 就能起飞"],
	"personal": ["Personal — can't be burned", "私人物品，不能烧"],
	"rarity_common": ["Common", "普通"],
	"rarity_uncommon": ["Uncommon", "少见"],
	"rarity_rare": ["Rare", "稀有"],
	"rarity_epic": ["Epic", "史诗"],
	"rarity_legendary": ["Legendary", "传说"],
	# ---- 剧情
	"who_chen": ["Chen", "晨"],
	"line_crash": ["Ow... oh no... I crashed...\nShould've insured the ship...",
		"啊……糟糕……坠毁了……\n早知道就给飞船买上保险了……"],
	"line_wood": ["Yes! With this, the ship can fly again!", "太好了，有了这个飞船就能再次起飞了！"],
	# ---- 剧本引擎（story_runner.gd）的界面字；台词本身在 data/story_forest.json
	"got_item": ["Got: %s", "获得：%s"],
	"gave_item": ["Handed over: %s", "交出：%s"],
	"journal_added": ["Written in the journal", "记进了日记"],
	"journal_empty": ["Nothing written yet.", "还什么都没写。"],
	"to_be_continued": ["To be continued", "未完待续"],
	"to_be_continued_sub": ["未完待续", "To be continued"],
	"just_look": ["Just look", "只是看看"],
	"use": ["Use", "使用"],
	"use_nothing": ["I don't think this helps here.", "这个好像用不上。"],
	"use_here_nothing": ["Nothing around here to use it on.", "这附近用不上。"],
	"journal_struck": ["Crossed out a line in the journal", "划掉了日记里的一句"],
}


static func t(key: String) -> String:
	if not STR.has(key):
		push_warning("I18n: 没有这条 " + key)
		return key
	var row: Array = STR[key]
	var i := LANGS.find(lang)
	return row[i] if i >= 0 and i < row.size() else row[0]


static func pick(d) -> String:
	if d is Dictionary:
		return d.get(lang, d.get("en", ""))
	return str(d)


static func is_zh() -> bool:
	return lang == "zh"
