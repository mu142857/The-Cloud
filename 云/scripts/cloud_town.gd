extends Node2D
## 结局三 · 云层小镇（art/town/room.json 的 scripts）：让作者 art/cloud/ 的天和云像 scenes/cloud_test.tscn 里一样，再让小镇动起来。
## - streaks、wash 两层是叠加混合（cloud_test 里是 CanvasItemMaterial add；room_stage 的层没有这个开关，这里补上）。
## - spires（石针）那张图 181 行以下还有一截，cloud_test 用 region 只取 43..181，这里把层的 region 截到 181 行。
## - 天上挂作者的星星（scripts/cloud_stars.gd，放在 sky 层下面：sky 的 scroll 是 0，坐标就是屏幕坐标）。
## - anims：风车、帆、绳帆、风向旗、水车、喷泉水帘的逐帧图（tools/cloud_town_art.py 画的，正弦摆 / 匀速转都画在帧里），
##   挂到对应的层下面（跟着那一层的视差走），100ms 一帧；off = 每个从第几帧起，免得一起摆。
## 不开闪电（cloud_lightning）：小镇是暖的，闪电会把气氛打断。

@export var anims: Array = []          # [{"layer", "img", "x", "y", "w", "frames", "off"}, …]（room.json 里 tools 生成）
@export var stars := true

const FRAME_MS := 100.0
const SPIRES_ROWS := 181

var _sprites: Array = []               # [[Sprite2D, frames, off]]
var _t := 0.0


func _ready() -> void:
	var stage := get_parent()
	if stage == null or not ("_layers" in stage):
		return
	var by_id := {}
	for L in stage._layers:
		by_id[str((L["cfg"] as Dictionary).get("id", ""))] = L["node"]
	for id in ["streaks", "wash"]:
		if by_id.has(id):
			var m := CanvasItemMaterial.new()
			m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
			(by_id[id] as Sprite2D).material = m
	if by_id.has("spires"):
		var sp: Sprite2D = by_id["spires"]
		var r := sp.region_rect if sp.region_enabled else Rect2(Vector2.ZERO, sp.texture.get_size())
		sp.region_enabled = true
		sp.region_rect = Rect2(r.position, Vector2(r.size.x, minf(r.size.y, SPIRES_ROWS)))
	if stars and by_id.has("sky") and ResourceLoader.exists("res://scripts/cloud_stars.gd"):
		var st := Node2D.new()
		st.set_script(load("res://scripts/cloud_stars.gd"))
		st.name = "Stars"
		(by_id["sky"] as Node).add_child(st)
	for a in anims:
		if not a is Dictionary:
			continue
		var host = by_id.get(str(a.get("layer", "")), null)
		var tex: Texture2D = stage._tex(str(a.get("img", ""))) if stage.has_method("_tex") else null
		if host == null or tex == null:
			push_warning("cloud_town：动画 %s 没挂上（层 %s）" % [a.get("img", ""), a.get("layer", "")])
			continue
		var s := Sprite2D.new()
		s.centered = false
		s.texture = tex
		s.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		s.hframes = maxi(int(a.get("frames", 1)), 1)
		s.position = Vector2(float(a.get("x", 0)), float(a.get("y", 0)))
		(host as Node).add_child(s)
		_sprites.append([s, s.hframes, int(a.get("off", 0))])
	_apply()


func _process(delta: float) -> void:
	var before := int(_t * 1000.0 / FRAME_MS)
	_t += delta
	if int(_t * 1000.0 / FRAME_MS) != before:
		_apply()


func _apply() -> void:
	var k := int(_t * 1000.0 / FRAME_MS)
	for e in _sprites:
		(e[0] as Sprite2D).frame = (k + int(e[2])) % int(e[1])
