class_name FlightText
## 飞行段原型自己的文字（占位）。正式的本地化（i18n）做好以后换掉：这里的 key 可以直接搬过去。
## 语言跟着设置走（I18n.lang，默认英文）；--lang=zh 或游戏里按 L 临时切换。

const SIZE := 14            # 天王星像素 11Px 的设计网格是 14 单位 / em：14 号字 = 1 个设计像素对 1 个屏幕像素
static var _font: FontFile

const S := {
	"need_line": {"en": "To Mercury: %d fuel. We have... exactly %d. Perfect.", "fr": "Mercure : %d de carburant. On a… exactement %d. Parfait.",
		"zh": "去水星要 %d 燃料。我们正好有……%d。完美。"},
	"sabotage": {"en": "...Was that the firewood? That was most of the firewood.", "fr": "… C’était le bois qui est tombé ? Presque tout le bois.",
		"zh": "……刚才掉下去的是木头吗？是大部分木头。"},
	"catch": {"en": "...Mercury's pulling us in. We're gliding. We're actually gliding.", "fr": "… Mercure nous attire. On plane. On plane vraiment.",
		"zh": "……水星在把我们往那边拉。我们在滑翔。真的在滑翔。"},
	"emergency": {"en": "Come on... just a little further.", "fr": "Allez… Encore un peu.", "zh": "再撑一下……就一下。"},
	"hint": {"en": "hold  SPACE  /  click  to rise", "fr": "Maintenir Espace / clic pour monter", "zh": "按住 空格 / 鼠标 往上飞"},
	"card_head": {"en": "Something has to burn.", "fr": "Il faut brûler quelque chose.", "zh": "得烧点什么了。"},
	"pick_head": {"en": "We're going down.", "fr": "On perd de l’altitude.", "zh": "在往下掉了。"},
	"burn": {"en": "Burn it", "fr": "Brûler", "zh": "烧掉"},
	"keep": {"en": "Keep it", "fr": "Garder", "zh": "留下"},
	"pick_all": {"en": "This is everything I have left.", "fr": "C’est tout ce qu’il me reste.", "zh": "剩下的，都在这里了。"},
	"keep_all": {"en": "Keep them all", "fr": "Tout garder", "zh": "都留下"},
	"fuel": {"en": "fuel", "fr": "carburant", "zh": "燃料"},
	"short": {"en": "short %d", "fr": "il manque %d", "zh": "还差 %d"},
	"enough": {"en": "enough to reach Mercury", "fr": "assez pour atteindre Mercure", "zh": "够飞到水星"},
	"next": {"en": "next", "fr": "ensuite", "zh": "接下来"},
	"no_more": {"en": "keeping the rest", "fr": "je garde le reste", "zh": "剩下的都留着"},
	"arrive_title": {"en": "Mercury.", "fr": "Mercure.", "zh": "水星。"},
	"arrive_sub": {"en": "We made it.", "fr": "On y est.", "zh": "到了。"},
	"crash_title": {"en": "Mercury, anyway.", "fr": "Mercure, quand même.", "zh": "还是落到了水星。"},
	"crash_sub": {"en": "We came down hard. Everything I was carrying is scattered somewhere below.", "fr": "On a atterri durement. Tout ce que je portais est éparpillé quelque part en bas.",
		"zh": "摔得不轻。身上带的东西，都散落在下面了。"},
	"burned": {"en": "Burned along the way", "fr": "Brûlé en chemin", "zh": "路上烧掉的"},
	"kept": {"en": "Still with me", "fr": "Encore avec moi", "zh": "还在身边的"},
	"fell_out": {"en": "Fell out of the ship:", "fr": "Tombé du vaisseau :", "zh": "颠簸时掉出飞船的："},
	"lost": {"en": "Lost in the fall", "fr": "Perdu dans la chute", "zh": "摔下来时丢了的"},
	"none": {"en": "nothing", "fr": "rien", "zh": "没有"},
	"again": {"en": "press any key to fly again", "fr": "Appuyez sur une touche pour repartir", "zh": "按任意键再飞一次"},
	"lights": {"en": "+%d", "fr": "+%d", "zh": "+%d"},
}


static func t(key: String) -> String:
	var d: Dictionary = S.get(key, {})
	return d.get(I18n.lang, d.get("en", key))


static func pick(d: Dictionary) -> String:
	## 物品数据里的 {en, zh}
	return d.get(I18n.lang, d.get("en", ""))


static func font() -> FontFile:
	if _font == null:
		_font = (load("res://fonts/PixelFont.ttf") as FontFile).duplicate()
		_font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
		_font.hinting = TextServer.HINTING_NONE
		_font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	return _font
