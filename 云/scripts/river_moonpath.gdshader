shader_type canvas_item;
// 河岸月夜的月光倒影（tools/river_bank_moon_art.py 画的 moonpath.png / moonpath_near.png）。
// 作者说原来的月光「好像在平移」：碎光图整张钉在屏幕上，脚下的水、水纹、石柱都在走，看着像一张贴纸在水面上滑。
// 现实里，月光那一竖条的位置跟着人走（月亮在无限远），但里面一闪一闪的碎光是水面自己的，人走它不走。所以拆成两半：
// - 贴图是一张遮罩，层 scroll = 0 钉在屏幕上、对着月亮：A = 这里能不能有碎光（边缘是抖开的），
//   R = 最亮能到哪一档，B = 碎光有多密，G = 这一行水面的视差 scroll（÷2 存，越近越大）。
// - 碎光本身按水面算：这一行的世界 x = 屏幕 x + 镜头左边缘 × 这一行的 scroll，在世界坐标里切小格、每格自己的长短、亮度、闪烁。
//   镜头动，碎光跟着这一行的水一起往后退，月光条留在原地。
// 镜头左边缘直接从这一层自己的位置拿（scroll 0 的层每帧被摆到镜头左边缘，见 room_stage.gd update），不用脚本传参。
render_mode unshaded;

uniform vec4 c0 : source_color = vec4(0.18, 0.23, 0.33, 1.0);
uniform vec4 c1 : source_color = vec4(0.28, 0.34, 0.45, 1.0);
uniform vec4 c2 : source_color = vec4(0.40, 0.46, 0.57, 1.0);
uniform vec4 c3 : source_color = vec4(0.52, 0.58, 0.68, 1.0);
uniform float speed = 1.0;        // 闪烁快慢
uniform float wobble = 1.5;       // 每行左右晃几像素（随这一行的 scroll 变大）
uniform float flicker = 0.9;      // 亮度档上下摆多少

varying float cam_left;

float hash(vec2 p) {
	p = mod(p, vec2(997.0, 991.0));
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void vertex() {
	cam_left = MODEL_MATRIX[3].x;
}

void fragment() {
	vec2 size = vec2(textureSize(TEXTURE, 0));
	vec2 px = floor(UV * size);
	vec4 m = texture(TEXTURE, (px + 0.5) / size);
	if (m.a < 0.5) {
		discard;
	}
	float sc = m.g * 2.0;
	float w = wobble * clamp(sc, 0.3, 1.0);
	float off = round(w * (0.65 * sin(TIME * speed * 0.9 + px.y * 0.71) + 0.35 * sin(TIME * speed * 2.3 + px.y * 1.93)));
	float wx = px.x - off + floor(cam_left * sc + 0.5);
	float cell = clamp(floor(4.0 + 7.0 * sc + 0.5), 4.0, 12.0);  // 一格一段横的碎光：远处短而密，近处一段段长
	float ci = floor(wx / cell);
	float k = wx - ci * cell;
	float h1 = hash(vec2(ci, px.y));
	if (h1 > m.b) {
		discard;
	}
	float h2 = hash(vec2(ci + 31.0, px.y + 17.0));
	if (k >= max(1.0, floor((0.35 + 0.65 * h2) * (cell - 1.0)))) {
		discard;
	}
	float h3 = hash(vec2(ci + 57.0, px.y + 3.0));
	float h4 = hash(vec2(ci + 11.0, px.y + 41.0));
	float lv = m.r * 3.0 * (0.55 + 0.45 * h3) + 0.25 + flicker * sin(TIME * speed * (0.8 + h4 * 2.4) + h2 * 6.2832);
	if (lv < 0.0) {
		discard;
	}
	int i = int(min(floor(lv), 3.0));
	COLOR = i == 0 ? c0 : (i == 1 ? c1 : (i == 2 ? c2 : c3));
}
