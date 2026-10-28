class_name FlightText
## 飞行段原型自己的文字（占位）。正式的本地化（i18n）做好以后换掉：这里的 key 可以直接搬过去。
## 默认英文（jam 规则），--lang=zh 或游戏里按 L 切中文。

const SIZE := 14            # 天王星像素 11Px 的设计网格是 14 单位 / em：14 号字 = 1 个设计像素对 1 个屏幕像素
static var lang := "en"
static var _font: FontFile

const S := {
	"need_line": {"en": "To Mercury: %d fuel. We have... exactly %d. Perfect.",
		"zh": "去水星要 %d 燃料。我们正好有……%d。完美。"},
	"sabotage": {"en": "...Was that the firewood? That was most of the firewood.",
		"zh": "……刚才掉下去的是木头吗？是大部分木头。"},
	"emergency": {"en": "Come on... just a little further.", "zh": "再撑一下……就一下。"},
	"hint": {"en": "hold  SPACE  /  click  to rise", "zh": "按住 空格 / 鼠标 往上飞"},
	"card_head": {"en": "Something has to burn.", "zh": "得烧点什么了。"},
	"pick_head": {"en": "We're going down.", "zh": "在往下掉了。"},
	"burn": {"en": "Burn it", "zh": "烧掉"},
	"keep": {"en": "Keep it", "zh": "留下"},
	"pick_all": {"en": "This is everything I have left.", "zh": "剩下的，都在这里了。"},
	"keep_all": {"en": "Keep them all", "zh": "都留下"},
	"fuel": {"en": "fuel", "zh": "燃料"},
	"short": {"en": "short %d", "zh": "还差 %d"},
	"next": {"en": "next", "zh": "接下来"},
	"no_more": {"en": "keeping the rest", "zh": "剩下的都留着"},
	"arrive_title": {"en": "Mercury.", "zh": "水星。"},
	"arrive_sub": {"en": "We made it.", "zh": "到了。"},
	"crash_title": {"en": "Mercury, anyway.", "zh": "还是落到了水星。"},
	"crash_sub": {"en": "We came down hard. Everything I was carrying is scattered somewhere below.",
		"zh": "摔得不轻。身上带的东西，都散落在下面了。"},
	"burned": {"en": "Burned along the way", "zh": "路上烧掉的"},
	"kept": {"en": "Still with me", "zh": "还在身边的"},
	"lost": {"en": "Lost in the fall", "zh": "摔下来时丢了的"},
	"none": {"en": "nothing", "zh": "没有"},
	"again": {"en": "press any key to fly again", "zh": "按任意键再飞一次"},
	"lights": {"en": "+%d", "zh": "+%d"},
}


static func t(key: String) -> String:
	var d: Dictionary = S.get(key, {})
	return d.get(lang, d.get("en", key))


static func pick(d: Dictionary) -> String:
	## 物品数据里的 {en, zh}
	return d.get(lang, d.get("en", ""))


static func font() -> FontFile:
	if _font == null:
		_font = (load("res://fonts/PixelFont.ttf") as FontFile).duplicate()
		_font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
		_font.hinting = TextServer.HINTING_NONE
		_font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	return _font
