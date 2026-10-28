shader_type canvas_item;
// 河面会动的两层（tools/river_art.py 画的 glints.png / ripples.png）共用：
// 每一行按自己的相位左右晃 0~wobble 像素（整像素，不糊），每一段亮纹按自己的相位一会儿亮、一会儿暗、一会儿没了。
// 只读自己的贴图一次，不读屏幕；只画贴图里不透明的那几行，手机网页版也便宜。
//
// palette_mode = true（glints）：R = 亮度档 0..1，G = 闪烁相位，B = 闪烁快慢；颜色从 c0..c3 里查（4 档，最亮 c3）。
// palette_mode = false（ripples）：像素本身就是颜色，只按位置算一个相位，让它一会儿有一会儿没有。
render_mode unshaded;

uniform bool palette_mode = true;
uniform vec4 c0 : source_color = vec4(0.18, 0.23, 0.33, 1.0);
uniform vec4 c1 : source_color = vec4(0.28, 0.34, 0.45, 1.0);
uniform vec4 c2 : source_color = vec4(0.40, 0.46, 0.57, 1.0);
uniform vec4 c3 : source_color = vec4(0.52, 0.58, 0.68, 1.0);
uniform float speed = 1.0;        // 整体快慢
uniform float wobble = 1.5;       // 最近那一行最多左右晃几像素（最远那行是它的 0.3）
uniform float flicker = 0.9;      // 亮度档上下摆多少（>1 时暗的亮纹会时不时消失）
uniform float show = 0.6;         // ripples：大约多少比例的时间看得见

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void fragment() {
	vec2 size = vec2(textureSize(TEXTURE, 0));
	vec2 px = floor(UV * size);
	float depth = px.y / size.y;                       // 0 = 远（地平线），1 = 近
	// 每行自己的晃动：两条正弦叠起来，取整像素
	float w = wobble * mix(0.3, 1.0, depth);
	float off = round(w * (0.65 * sin(TIME * speed * 0.9 + px.y * 0.71) + 0.35 * sin(TIME * speed * 2.3 + px.y * 1.93)));
	vec2 uv = (vec2(px.x - off, px.y) + 0.5) / size;
	vec4 t = texture(TEXTURE, uv);
	if (t.a < 0.5) {
		discard;
	}
	if (palette_mode) {
		float lv = t.r * 3.0 + 0.25 + flicker * sin(TIME * speed * (0.8 + t.b * 2.4) + t.g * 6.2832);
		if (lv < 0.0) {
			discard;
		}
		int i = int(min(floor(lv), 3.0));
		COLOR = i == 0 ? c0 : (i == 1 ? c1 : (i == 2 ? c2 : c3));
	} else {
		// 同一行里每 7 像素一段共用一个相位：一小段水纹一起出现、一起消失
		float ph = hash(vec2(floor((px.x - off) / 7.0), px.y));
		float s = sin(TIME * speed * (0.5 + ph * 0.9) + ph * 40.0);
		if (s < 1.0 - 2.0 * show) {
			discard;
		}
		COLOR = t;
	}
}
