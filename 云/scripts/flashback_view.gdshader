shader_type canvas_item;
// 母星闪回（scripts/flashback.gd）：母星那一屏（SubViewport 的图）画到这张 TextureRect 上时的效果。
// - blur：刚淡进来时是糊的，慢慢变清楚（半径按 480×270 的像素）。
// - 灰色：屏幕左边压过来的一片灰暗。不是角色，是把画面压暗、去色；前沿上下有一点慢慢起伏，
//   浓淡按 4×4 的点阵抖成几档（和画面的像素格对齐，不是一整片平滑的雾）。前沿前面一小段先褪色。
//   grey_tail：灰色的后沿（第四次站着不动，灰色从晨身边过去、从右边走掉）；默认在很左边 = 一整片。
// - 发白：第三次没被追上，前面的楼、人群、倒影一段一段褪成空白。按世界坐标切成 seg_w 宽的竖段（跟着街走，不跟着屏幕），
//   前沿 white_x 从右往左走过一段，这一段整段一起慢慢褪白（上面先褪、地上的倒影最后）；晨身边留着（chen_sx），
//   white_all 0→1 最后连她一起白掉。

uniform float blur : hint_range(0.0, 8.0) = 0.0;
uniform float grey_x = -400.0;      // 灰色前沿（屏幕 x，480 宽）
uniform float grey_tail = -9999.0;  // 灰色后沿
uniform float grey_a : hint_range(0.0, 1.0) = 0.92;
uniform float white_x = 9999.0;     // 发白的前沿（屏幕 x，从右往左）
uniform float cam_left = 0.0;       // 镜头左边缘的世界 x：竖段跟着街走
uniform float seg_w = 48.0;
uniform float chen_sx = 160.0;      // 晨在屏幕上的 x
uniform float white_all = 0.0;
uniform float t = 0.0;
uniform vec4 grey_c : source_color = vec4(0.1, 0.11, 0.12, 1.0);
uniform vec4 white_c : source_color = vec4(0.93, 0.95, 0.94, 1.0);

const vec2 BASE = vec2(480.0, 270.0);

float bayer(vec2 p) {
	int x = int(mod(p.x, 4.0));
	int y = int(mod(p.y, 4.0));
	int i = x + y * 4;
	float m[16] = float[](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
	return (m[i] + 0.5) / 16.0;
}

// 0..1 的浓淡抖成 5 档（点阵）
float steps(float k, vec2 px) {
	float q = k * 4.0;
	float f = floor(q);
	return (f + step(bayer(px), q - f)) / 4.0;
}

void fragment() {
	// 糊（原来是 sample_blur(TEXTURE, UV) 函数；把 TEXTURE 传进自定义函数 Godot 4.7 每次编译都报
	// 「custom_samplers.has(...tex_builtin)」，所以直接写在 fragment 里，结果一样）
	vec3 col = texture(TEXTURE, UV).rgb;
	if (blur >= 0.05) {
		col *= 2.0;
		float w = 2.0;
		for (int i = 0; i < 12; i++) {
			float ring = i < 6 ? 0.5 : 1.0;
			float a = float(i) * 1.0472 + (i < 6 ? 0.0 : 0.5236);
			vec2 off = vec2(cos(a), sin(a)) * blur * ring / BASE;
			col += texture(TEXTURE, UV + off).rgb;
			w += 1.0;
		}
		col /= w;
	}
	vec2 px = floor(UV * BASE);
	float x = px.x;
	// 前沿的起伏（两条慢正弦叠在一起，竖着看是一条软软的、会动的边）
	float wob = sin(px.y * 0.09 + t * 1.3) * 6.0 + sin(px.y * 0.23 - t * 2.1) * 2.5;
	float edge = grey_x + wob;
	float g = dot(col, vec3(0.299, 0.587, 0.114));
	// 前沿前面 60 像素先褪色
	float pre = 1.0 - smoothstep(edge, edge + 60.0, x);
	col = mix(col, vec3(g), pre * 0.75);
	// 灰：前沿往后 80 像素从淡到浓
	float k = 1.0 - smoothstep(edge - 80.0, edge, x);
	k *= smoothstep(grey_tail - 70.0 + wob, grey_tail + wob, x);
	k = steps(k, px) * grey_a;
	col = mix(col, grey_c.rgb + vec3(g * 0.12), k);
	// 发白：一段一段褪
	float seg = floor((cam_left + x) / seg_w);
	float seg_r = (seg + 1.0) * seg_w - cam_left;
	float f = clamp((seg_r - white_x) / (seg_w * 1.6), 0.0, 1.0);
	f = clamp(f * 1.35 - UV.y * 0.35, 0.0, 1.0);
	f = f * f * (3.0 - 2.0 * f);
	float keep = smoothstep(chen_sx + 6.0, chen_sx + 36.0, x);
	float kw = max(f * keep, white_all);
	kw = steps(kw, px + vec2(2.0, 1.0));
	col = mix(col, white_c.rgb, kw);
	COLOR = vec4(col, COLOR.a);
}
