shader_type canvas_item;
// 湿街面的倒影（scenes/city_test.tscn 的 Wet/Rect，盖在街面那几十行上，画在晨后面一层、前景前面）。
// 像湿柏油路：安静的几条竖向光带，不是噪点。
// - 光带：每一列看上面那一截城市（y 52~172，竖着取 9 个点 × 横 3 列，停在晨的头顶以上）的平均亮度 —— 1 像素的雨丝、暗的人群、
//   几只鸽子平均下来几乎没有分量；楼缝里的亮霾、一层层的楼梯间日光灯、开过去的列车车窗这种成块、成列的光才高。
//   高过门槛的列，在街面上拉成一整条竖的光带：贴着路沿最亮，往下慢慢淡。
// - 边缘被雨打得微微断开、轻轻抖：光带按 4 行一段，少数几段缺一截、或左右错开 1 像素（0.4 秒换一次）。
// - 几处积水（每 puddle_every 像素一片）是镜子：按行上下翻转照（d·4 行），只取横 1 × 竖 3 的平均，更清楚。
// 按 480×270 的像素格取样，输出不透明的颜色；加上去的那一份有上限、再分档，街面整体仍然暗。
// 晨不进光带（光带只看 y 172 以上），积水的镜子在她左右 22 像素内压到两成：她脚下不会出现亮块。
render_mode unshaded;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform float cam_left = 0.0;      // 镜头左边缘在世界里的 x（city_test.gd 每帧更新）：光带的断口、积水跟着地面走
uniform float chen_x = 204.0;      // 晨在屏幕上的 x（city_test.gd 每帧更新）
uniform float ground = 228.0;
uniform float strength = 0.75;
uniform float add_max = 0.15;      // 每个像素最多加这么多（sRGB 0..1）
uniform float puddle_every = 260.0;

const vec2 RES = vec2(480.0, 270.0);

float h1(float n) { return fract(sin(n * 12.9898) * 43758.5453); }

vec3 src(vec2 p) {
	return texture(screen_tex, (clamp(p, vec2(0.0), RES - 1.0) + 0.5) / RES).rgb;
}

void fragment() {
	vec2 px = floor(SCREEN_UV * RES);
	vec3 base = src(px);
	float d = px.y - ground;
	float wx = floor(px.x + cam_left);
	float band = floor(d / 4.0);
	float rip = step(0.8, h1(band * 7.1 + floor(TIME * 2.5) * 3.3 + floor(wx / 19.0)));
	// 这一列上面那一截城市的平均颜色
	vec3 acc = vec3(0.0);
	for (int j = 0; j < 9; j++) {
		for (int i = -1; i <= 1; i++) {
			acc += src(vec2(px.x + rip + float(i), 52.0 + float(j) * 15.0));
		}
	}
	vec3 col = acc / 27.0;
	float lum = dot(col, vec3(0.3, 0.59, 0.11));
	float k = smoothstep(0.1, 0.3, lum);
	float gap = step(h1(wx * 0.31 + band * 1.7 + floor(TIME * 2.0) * 5.1), 0.08);
	float prof = clamp(1.0 - (d - 2.0) / 44.0, 0.0, 1.0) * step(2.0, d);
	vec3 add = col * vec3(0.85, 0.92, 1.0) * k * strength * prof * (1.0 - gap);
	add *= mix(1.0, 0.5, step(abs(px.x - chen_x), 16.0));   // 正好落在晨脚下的那条光带再淡一半
	// 积水：扁椭圆里是一面镜子
	float pc = floor(wx / puddle_every);
	float pxw = wx - pc * puddle_every - (40.0 + h1(pc) * 140.0);
	float pw = 22.0 + h1(pc + 3.0) * 26.0;
	float pd = 16.0 + h1(pc + 7.0) * 12.0;
	float pud = step((pxw / pw) * (pxw / pw) + ((d - pd) / 6.0) * ((d - pd) / 6.0), 1.0);
	if (pud > 0.5) {
		float sy = ground - d * 4.0;
		vec3 m = (src(vec2(px.x, sy - 1.0)) + src(vec2(px.x, sy)) + src(vec2(px.x, sy + 1.0))) / 3.0;
		float ml = dot(m, vec3(0.3, 0.59, 0.11));
		float mk = smoothstep(0.08, 0.3, ml) * mix(1.0, 0.2, step(abs(px.x - chen_x), 22.0));
		add = max(add, m * vec3(0.8, 0.88, 0.96) * mk * 0.55);
	}
	add = min(add, vec3(add_max));
	COLOR = vec4(base + floor(add * 40.0 + 0.5) / 40.0, 1.0);
}
