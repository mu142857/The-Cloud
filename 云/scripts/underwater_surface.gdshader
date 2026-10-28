shader_type canvas_item;
// 水面（从下往上看的那层「天花板」）里会闪的碎光：tools/underwater_art.py 的 surface.png。
// R = 亮度档 0..1，G = 闪烁相位，B = 闪烁快慢；颜色从 c0..c3 里查（4 档，最亮 c3 也明显暗于晨）。
// 每一行按自己的相位左右晃（整像素）：越靠上（离得越近）晃得越多。不读屏幕。
render_mode unshaded;

uniform vec4 c0 : source_color = vec4(0.18, 0.26, 0.34, 1.0);
uniform vec4 c1 : source_color = vec4(0.27, 0.36, 0.45, 1.0);
uniform vec4 c2 : source_color = vec4(0.38, 0.47, 0.55, 1.0);
uniform vec4 c3 : source_color = vec4(0.50, 0.58, 0.64, 1.0);
uniform float speed = 0.8;
uniform float wobble = 3.0;      // 最上面那一行最多左右晃几像素（最下面一行是它的 0.25）
uniform float flicker = 0.9;     // 亮度档上下摆多少（>1 时暗的碎光会时不时消失）

void fragment() {
	vec2 size = vec2(textureSize(TEXTURE, 0));
	vec2 px = floor(UV * size);
	float near = 1.0 - px.y / size.y;
	float w = wobble * mix(0.25, 1.0, near);
	float off = round(w * (0.6 * sin(TIME * speed * 0.7 + px.y * 0.9) + 0.4 * sin(TIME * speed * 1.9 + px.y * 2.3)));
	vec4 t = texture(TEXTURE, (vec2(px.x - off, px.y) + 0.5) / size);
	if (t.a < 0.5) {
		discard;
	}
	float lv = t.r * 3.0 + 0.2 + flicker * sin(TIME * speed * (0.7 + t.b * 2.2) + t.g * 6.2831853);
	if (lv < 0.0) {
		discard;
	}
	int i = int(min(floor(lv), 3.0));
	COLOR = i == 0 ? c0 : (i == 1 ? c1 : (i == 2 ? c2 : c3));
}
