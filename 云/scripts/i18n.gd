class_name I18n
## 共享界面词条；按系统或浏览器语言初始化，玩家可在标题或设置里选择。
##   I18n.t("start")            → "Start" / "开始游戏"
##   I18n.t("burn_total") % [60, 200]
##   I18n.pick({"en": .., "zh": ..})   物品表（data/items.json）那种自带两种语言的字段
## 加新语言：LANGS 里加一个代号，每条后面多写一个字符串。
## 加剧情台词：照 line_* 抄。名字用 who_*。
##
## 换语言以后，正在显示的文字由各个界面自己刷新（level_forest.gd 的 _retext）。

const LANGS := ["en", "zh", "fr"]
const LANG_NAMES := {"en": "English", "zh": "中文", "fr": "Français"}

static var lang := "en"

const STR := {
	# ---- 开场
	"pet": ["Pet", "摸一摸", "Caresser"],
	"talk": ["Talk", "聊一聊", "Parler"],
	"view": ["View", "查看", "Regarder"],
	"headphones": ["Best played with headphones", "建议佩戴耳机游玩", "Jouez de préférence au casque"],
	"title": ["The Cloud", "云", "Le Nuage"],
	"title_sub": ["云", "THE CLOUD", "THE CLOUD"],      # 标题下面那行小字：另一种语言的名字
	"start": ["Start", "开始游戏", "Commencer"],
	"continue": ["Continue", "继续游戏", "Continuer"],   # 标题界面，有存档时在「开始游戏」上面
	"credits": ["Credits", "制作人员", "Générique"],
	"back_to_title": ["Back to Title", "返回标题", "Retour au titre"],
	"skip_again": ["Press again to skip", "再按一次跳过", "Appuyez encore pour passer"],
	# ---- 设置
	"settings": ["Settings", "设置", "Paramètres"],
	"language": ["Language", "语言", "Langue"],
	"vol_master": ["Volume", "总音量", "Volume"],
	"vol_music": ["Music", "音乐", "Musique"],
	"vol_sfx": ["Sound", "音效", "Sons"],
	"quality": ["Effects", "特效", "Effets"],
	"q_full": ["Full", "完整", "Complets"],
	"q_lite": ["Lite", "精简", "Réduits"],
	"fullscreen": ["Fullscreen", "全屏", "Plein écran"],
	"on": ["On", "开", "Oui"],
	"off": ["Off", "关", "Non"],
	"close": ["Close", "关闭", "Fermer"],
	# ---- 背包 / 燃烧值
	"bag": ["Bag", "背包", "Sac"],
	"bag_empty": ["Nothing here yet.", "这里还什么都没有。", "Il n’y a encore rien ici."],
	"burn": ["Burn", "燃烧值", "Carburant"],
	"burn_value": ["Burn +%d", "燃烧值 +%d", "Carburant +%d"],
	"burn_total": ["%d / %d", "%d / %d", "%d / %d"],
	"to_launch": ["Reach %d to launch the ship", "燃烧值到 %d 就能起飞", "Atteignez %d pour décoller"],
	"personal": ["Personal. Can't be burned.", "私人物品，不能烧", "Objet personnel. Ne peut pas être brûlé."],
	"rarity_common": ["Common", "普通", "Commun"],
	"rarity_uncommon": ["Uncommon", "少见", "Peu commun"],
	"rarity_rare": ["Rare", "稀有", "Rare"],
	"rarity_epic": ["Epic", "史诗", "Épique"],
	"rarity_legendary": ["Legendary", "传说", "Légendaire"],
	# ---- 剧情
	"who_chen": ["Light", "晨", "Light"],
	"line_crash": ["Ow... oh no... I crashed...\nShould've insured the ship...",
		"啊……糟糕……坠毁了……\n早知道就给飞船买上保险了……", "Aïe… Oh non… Je me suis écrasée…\nJ’aurais dû assurer le vaisseau…"],
	"line_wood": ["Yes! With this, the ship can fly again!", "太好了，有了这个飞船就能再次起飞了！", "Super ! Avec ça, le vaisseau va pouvoir repartir !"],
	# ---- 剧本引擎（story_runner.gd）的界面字；台词本身在 data/story_forest.json
	"got_item": ["Got: %s", "获得：%s", "Objet obtenu : %s"],
	"got_items": ["Got %d items", "获得 %d 件东西", "%d objets obtenus"],           # give 数组（story_quick.gd）
	"luggage_items": ["Luggage: %d items", "行李：%d 件", "Bagages : %d objets"],
	"gave_item": ["Handed over: %s", "交出：%s", "Objet remis : %s"],
	"journal_added": ["Written in the journal", "记进了日记", "Noté dans le journal"],
	"journal_empty": ["Nothing written yet.", "还什么都没写。", "Il n’y a encore rien d’écrit."],
	"to_be_continued": ["To be continued", "未完待续", "À suivre"],
	"to_be_continued_sub": ["未完待续", "To be continued", "To be continued"],
	"just_look": ["Just look", "只是看看", "Juste regarder"],
	"barter_none": ["Never mind", "算了", "Laisser tomber"],                     # 以物易物的道具选择条最后一格（barter.gd）
	"achievements_title": ["Achievements", "成就", "Succès"],              # 「全剧终」卡下面的成就列表（barter.gd show_achievements）
	"use": ["Use", "使用", "Utiliser"],
	"use_nothing": ["I don't think this helps here.", "这个好像用不上。", "Ça ne doit pas servir ici."],
	"use_here_nothing": ["Nothing around here to use it on.", "这附近用不上。", "Il n’y a rien ici sur quoi l’utiliser."],
	"journal_struck": ["Crossed out a line in the journal", "划掉了日记里的一句", "Une ligne du journal a été rayée"],
	"paper_added": ["Written on: %s", "记在了%s上", "Noté sur : %s"],             # 终章日记烧掉以后（story_runner._journal_holder）
	"paper_struck": ["Crossed out a line", "划掉了一句", "Une ligne a été rayée"],
	"the_end": ["The End", "全剧终", "Fin"],
	"the_end_sub": ["全剧终", "The End", "The End"],
	"end_any_key": ["Press any key to return to the title", "按任意键回到标题", "Appuyez sur une touche pour revenir au titre"],
	"cat_keepsake": ["[Keepsake]", "【纪念品】", "[Souvenir]"],
	"cat_quest": ["[Quest]", "【任务】", "[Quête]"],
	"keepsake_burn": ["Would burn for about %d", "烧掉可得：约 %d", "Donne environ %d de carburant"],
	"quest_item": ["Needed for something", "任务物品", "Objet de quête"],
}


static func t(key: String) -> String:
	if not STR.has(key):
		push_warning("I18n: 没有这条 " + key)
		return key
	return row_text(STR[key])


static func match_locale(locale: String) -> String:
	var primary := locale.to_lower().replace("-", "_").split("_", false)
	return primary[0] if not primary.is_empty() and LANGS.has(primary[0]) else "en"


static func row_text(row: Array) -> String:
	var i := LANGS.find(lang)
	return row[i] if i >= 0 and i < row.size() else row[0]


static func pick(d) -> String:
	if d is Dictionary:
		return d.get(lang, d.get("en", ""))
	return str(d)


static func is_zh() -> bool:
	return lang == "zh"
