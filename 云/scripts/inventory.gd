class_name Inventory
## 物品表（data/items.json）+ 玩家现在背包里有什么 + 燃烧值。静态的，跨场景都在。
##   Inventory.add("glowing_wood")
##   Inventory.burn_total()      → 起始的 base_burn + 背包里所有非私人物品的 burn
##   Inventory.item("glowing_wood") → {id, name{en,zh}, rarity, burn, icon, personal, desc{en,zh}}
##   Inventory.remove("pump")   剧本的 take
##   Inventory.icon("scrap")    图标；图不存在（美术还没画）就是一块色块，不报错
## 存档以后再做：owned 存一份就行（见 StoryState.to_dict）。
## 剧本（data/story_forest*.json）可以带一份 "items"：items.json 里没有的物品先用它顶上（register_fallback），
## 开发时美术 / 物品表还没齐也能跑通；items.json 里有的以 items.json 为准。

const DATA := "res://data/items.json"
const RARITY_COLORS := {
	"common": Color("#a9b8af"),
	"uncommon": Color("#8fd6a6"),
	"rare": Color("#7cb8f0"),
	"epic": Color("#c49af0"),
	"legendary": Color("#f0c870"),
}

static var _db := {}
static var _order: Array[String] = []
static var base_burn := 10
static var launch_burn := 200
static var owned: Array[String] = []


static func _load() -> void:
	if not _db.is_empty():
		return
	var f := FileAccess.open(DATA, FileAccess.READ)
	if f == null:
		push_error("Inventory: 读不到 " + DATA)
		return
	var d = JSON.parse_string(f.get_as_text())
	if not d is Dictionary:
		push_error("Inventory: items.json 格式不对")
		return
	base_burn = int(d.get("base_burn", 10))
	launch_burn = int(d.get("launch_burn", 200))
	for it in d.get("items", []):
		_db[it["id"]] = it
		_order.append(it["id"])


static func item(id: String) -> Dictionary:
	_load()
	return _db.get(id, {})


static func add(id: String) -> void:
	_load()
	if _db.has(id):
		owned.append(id)


static func has(id: String) -> bool:
	return owned.has(id)


static func remove(id: String) -> void:
	owned.erase(id)


static func defined(id: String) -> bool:
	_load()
	return _db.has(id)


## items.json 里没有这个 id 时补一条（剧本里带的备用物品；图缺了照样是色块）
static func register_fallback(it: Dictionary) -> void:
	_load()
	var id := str(it.get("id", ""))
	if id == "" or _db.has(id):
		return
	_db[id] = it
	_order.append(id)


static var _icons := {}


static func icon(id: String) -> Texture2D:
	_load()
	if _icons.has(id):
		return _icons[id]
	var it: Dictionary = _db.get(id, {})
	var path := str(it.get("icon", ""))
	var tex: Texture2D
	if path != "" and ResourceLoader.exists(path):
		tex = load(path)
	else:
		tex = placeholder(id, rarity_color(str(it.get("rarity", "common"))))
	_icons[id] = tex
	return tex


## 色块占位：12×12，颜色按 id 变一点（同一个 id 永远同一个色），一圈暗一档的边
static func placeholder(id: String, base: Color, w := 12, h := 12) -> ImageTexture:
	var hsh := absi(hash(id))
	var c := Color.from_hsv(fposmod(base.h + float(hsh % 7) * 0.09, 1.0), clampf(base.s * 0.7 + 0.1, 0.0, 1.0), 0.62)
	var img := Image.create_empty(w, h, false, Image.FORMAT_RGBA8)
	img.fill(c)
	var e := c.darkened(0.35)
	for x in w:
		img.set_pixel(x, 0, e)
		img.set_pixel(x, h - 1, e)
	for y in h:
		img.set_pixel(0, y, e)
		img.set_pixel(w - 1, y, e)
	return ImageTexture.create_from_image(img)


static func burn_total() -> int:
	_load()
	var s := base_burn
	for id in owned:
		var it: Dictionary = _db.get(id, {})
		if not it.get("personal", false):
			s += int(it.get("burn", 0))
	return s


static func get_launch_burn() -> int:
	_load()
	return launch_burn


static func rarity_color(r: String) -> Color:
	return RARITY_COLORS.get(r, RARITY_COLORS["common"])
