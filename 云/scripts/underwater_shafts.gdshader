shader_type canvas_item;
// 月光光柱：从水面上方（月亮那一侧）一个点散开、往左下斜着照下来的几道光。挂在一个 480×270 的 ColorRect 上，屏幕固定。
// 整像素：先把 UV 取整到 480×270 的格子，再把亮度按 step 分档、两档之间用 4×4 Bayer 抖动（和背景的抖法一样），
// 所以光柱的边是像素台阶，不是一片柔光。加法混合。不读屏幕。
// 光柱的参数由 scripts/underwater_shafts.gd 每帧传进来（它也给微粒算「在不在光里」，两边用同一个 t）。
render_mode blend_add, unshaded;

uniform vec2 focus = vec2(390.0, -300.0);   // 光柱都从这个点散开（屏幕像素，画面上方）
uniform vec4 shafts[8];                     // x = 中线斜率（dx/dy），y = 半宽（斜率单位），z = 强度，w = 相位
uniform int count = 6;
uniform float t = 0.0;
uniform float sway = 0.012;                 // 光柱左右摆多少（斜率单位）
uniform vec3 color : source_color = vec3(0.55, 0.74, 0.92);
uniform float step_a = 0.018;               // 每一档的 alpha
uniform float y_fade = 120.0;               // 往下衰减的距离
uniform float y_end = 200.0;                // 这一行以下没有光柱（晨身后那条要干净）

float bayer4(vec2 p) {
	int x = int(mod(p.x, 4.0));
	int y = int(mod(p.y, 4.0));
	int i = x + y * 4;
	float m[16] = float[16](0., 8., 2., 10., 12., 4., 14., 6., 3., 11., 1., 9., 15., 7., 13., 5.);
	return m[i] / 16.0;
}

void fragment() {
	vec2 px = floor(UV * vec2(480.0, 270.0));
	vec2 c = px + 0.5;
	float tx = (c.x - focus.x) / (c.y - focus.y);
	float a = 0.0;
	for (int i = 0; i < count; i++) {
		vec4 s = shafts[i];
		float cx = s.x + sway * (sin(t * 0.13 + s.w) + 0.5 * sin(t * 0.29 + s.w * 2.0));
		float d = abs(tx - cx) / s.y;
		float p = clamp(1.0 - d, 0.0, 1.0);
		p = p * p * (3.0 - 2.0 * p);
		float br = 0.62 + 0.38 * sin(t * (0.19 + 0.04 * float(i)) + s.w * 3.0);
		a += s.z * p * br;
	}
	a *= 0.82 + 0.18 * sin(tx * 700.0 + t * 0.35);        // 光柱里面一丝一丝的
	a *= smoothstep(0.0, 22.0, c.y) * exp(-c.y / y_fade) * (1.0 - smoothstep(y_end - 60.0, y_end, c.y));
	float q = floor(a / step_a + bayer4(px));
	if (q <= 0.0) {
		discard;
	}
	COLOR = vec4(color, q * step_a);
}
