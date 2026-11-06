extends RefCounted
## 第一关小游戏 signal_glitch：云星画面一闪，像信号不好（docs/剧情改动/第一关新版_实现规格.md 第 8 步，追逐拿到地图以后）。
##   约 1 秒：云星的画（作者的 art/cloud/：天、远处的尖塔、云塔、一层层云，截 x = 300 起的 480 宽，正好有那座黑云塔）
##   一下有一下没有地闪几次；有的时候带横向撕裂（几条横带左右错开）、红蓝错位、隔行扫描线，最后一下撕得最厉害，然后淡掉。
##   不用玩家操作。
##
## 剧本步骤：{"do": "mechanic", "id": "signal_glitch"}
##   可选："sfx": 音效名（开始时播，不等）；"layer": CanvasLayer 层（默认 51：盖在黑幕 Top 50 上面，黑屏时也闪得出来；
##         在潜意识字 52、闪回 55 下面）；"sets": [flag…]。
## 效果是一个读屏幕的 shader（写在下面 SHADER 里，不另建文件），gl_compatibility 能跑。

const ID := "signal_glitch"
const LAYER := 51
const DIR := "res://art/cloud/"
const CROP_X := 300.0
## 叠的顺序照 scenes/cloud_test.tscn（sky 是 480 宽的整张，不跟着截）
const LAYERS := ["high", "spires", "far", "midfar", "mid", "near", "main", "front"]

## [有没有画面, 秒, 撕裂强度 0..1]：一共约 1 秒
const BEATS := [
	[true, 0.06, 1.0],
	[false, 0.07, 0.0],
	[true, 0.12, 0.8],
	[false, 0.05, 0.0],
	[true, 0.36, 0.35],
	[true, 0.09, 1.0],
	[false, 0.04, 0.0],
	[true, 0.08, 0.7],
]
const FADE := 0.15
const RESEED := 0.045                    # 每这么多秒换一次撕裂的位置（跳着变，像信号）

const SHADER := """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform float amt = 0.0;
uniform float seed = 0.0;
float h(float n) { return fract(sin(n * 12.9898 + seed * 78.233) * 43758.5453); }
void fragment() {
	float a = COLOR.a;                              // ColorRect 的 modulate（淡掉时用）
	vec2 uv = SCREEN_UV;
	float row = floor(uv.y * 270.0);                 // 按游戏的 270 行算（canvas_items 拉伸时屏幕更大，也是同一套横带）
	float band = floor(row / (3.0 + floor(h(floor(row / 9.0)) * 7.0)));
	float r = h(band + 0.37);
	float shift = r > 0.72 ? (h(band + 1.3) - 0.5) * 44.0 * amt : 0.0;
	uv.x += floor(shift) / 480.0;
	float ca = floor(1.0 + 2.0 * amt) / 480.0;       // 红蓝错开 1~3 个游戏像素
	vec3 c = vec3(texture(screen_tex, uv + vec2(ca, 0.0)).r, texture(screen_tex, uv).g, texture(screen_tex, uv - vec2(ca, 0.0)).b);
	c *= mod(row, 2.0) < 1.0 ? 1.0 - 0.22 * (0.4 + amt) : 1.0;     // 隔行扫描线（连续的整行，不是点线）
	c += vec3(0.05, 0.03, 0.08) * amt * step(0.93, h(row + 5.1));  // 偶尔一行发亮
	COLOR = vec4(c, a);
}
"""


static func build_picture() -> Control:
	var pic := Control.new()
	pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pic.size = Vector2(480, 270)
	pic.clip_contents = true
	var bg := ColorRect.new()                        # 缺图时的底色：云星的夜紫
	bg.color = Color("#1d1526")
	bg.size = pic.size
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pic.add_child(bg)
	var sky_p := DIR + "sky.png"
	if ResourceLoader.exists(sky_p):
		pic.add_child(_tr(load(sky_p), Vector2.ZERO))
	for n in LAYERS:
		var p := DIR + str(n) + ".png"
		if ResourceLoader.exists(p):
			pic.add_child(_tr(load(p), Vector2(-CROP_X, 0)))
	return pic


static func _tr(t: Texture2D, at: Vector2) -> TextureRect:
	var r := TextureRect.new()
	r.texture = t
	r.position = at
	r.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


static func total_sec() -> float:
	var s := FADE
	for b in BEATS:
		s += float(b[1])
	return s


# ======================================================================= 演出
var speed := 1.0


func run(lv: Node2D, _w: Node2D, r: Node, st: Dictionary) -> void:
	if r.ff:
		ff(r, st)
		return
	if st.has("sfx"):
		r.run_steps([{"do": "sfx", "name": str(st["sfx"])}])
	var layer := CanvasLayer.new()
	layer.name = "SignalGlitch"
	layer.layer = int(st.get("layer", LAYER))
	layer.visible = false
	lv.add_child(layer)
	var root := Control.new()
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.size = Vector2(480, 270)
	layer.add_child(root)
	root.add_child(build_picture())
	root.add_child(BackBufferCopy.new())             # 把上面画好的云星拷给下面的 shader 读
	var fx := ColorRect.new()
	fx.size = Vector2(480, 270)
	fx.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sh := Shader.new()
	sh.code = SHADER
	var mat := ShaderMaterial.new()
	mat.shader = sh
	fx.material = mat
	root.add_child(fx)
	var k := 1.0 / speed
	var tree := lv.get_tree()
	var n := 0
	for b in BEATS:
		layer.visible = bool(b[0])
		mat.set_shader_parameter("amt", float(b[2]))
		var left := float(b[1]) * k
		while left > 0.0:
			n += 1
			mat.set_shader_parameter("seed", float(n) * 1.618)
			var dt := minf(RESEED * k, left)
			await tree.create_timer(dt, false).timeout
			left -= dt
	# 最后一下：撕裂收住，整张淡掉
	mat.set_shader_parameter("amt", 0.2)
	var tw := root.create_tween()
	tw.tween_property(root, "modulate:a", 0.0, FADE * k).set_trans(Tween.TRANS_SINE)
	await tw.finished
	layer.queue_free()
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))
	print("MECH %s done" % ID)


func auto(lv: Node2D, w: Node2D, r: Node, st: Dictionary) -> void:
	speed = 2.0
	await run(lv, w, r, st)


func ff(_r: Node, st: Dictionary) -> void:
	for f in st.get("sets", []):
		StoryState.set_flag(str(f))


func check(_story: Node, _st: Dictionary) -> Array:
	var out: Array = []
	if not ResourceLoader.exists(DIR + "main.png"):
		out.append("info: 云星的图 %smain.png 找不到，只闪紫色底" % DIR)
	return out
