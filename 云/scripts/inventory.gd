class_name Inventory
## 物品表（data/items.json）+ 玩家现在背包里有什么 + 燃烧值。静态的，跨场景都在。
##   Inventory.add("glowing_wood")
##   Inventory.burn_total()      → 起始的 base_burn + 背包里所有非私人物品的 burn
##   Inventory.item("glowing_wood") → {id, name{en,zh}, rarity, burn, icon, personal, desc{en,zh}}
## 存档以后再做：owned 存一份就行。

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


static func burn_total() -> int:
	_load()
	var s := base_burn
	for id in owned:
		var it: Dictionary = _db[id]
		if not it.get("personal", false):
			s += int(it.get("burn", 0))
	return s


static func get_launch_burn() -> int:
	_load()
	return launch_burn


static func rarity_color(r: String) -> Color:
	return RARITY_COLORS.get(r, RARITY_COLORS["common"])
