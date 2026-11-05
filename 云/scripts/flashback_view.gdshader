shader_type canvas_item;
// 母星闪回（scripts/flashback.gd）：母星那一屏（SubViewport 的图）画到这张 TextureRect 上时的效果。
// - blur：刚淡进来时是糊的，慢慢变清楚（半径按 480×270 的像素）。
// - 灰色：屏幕左边压过来的一片灰暗。不是角色，是把画面压暗、去色；前沿上下有一点慢慢起伏，
//   浓淡按 4×4 的点阵抖成几档（和画面的像素格对齐，不是一整片平滑的雾）。前沿前面一小段先褪色。
//   grey_tail：灰色的后沿（第四次站着不动，灰色从晨身边过去、从右边走掉）；默认在很左边 = 一整片。
// - 闪白（flash）：第三次没被追上，字掉完以后整屏像相机过曝一样一下子白掉（11-05 作者定，取代原来从右边漫过来的软光）。
//   flash 0→1：先把整幅画往白里抬（暗的也抬上去，像曝光过头），后半段混到 white_c；满白里留一点「比周围暗」的地方
//   （人影、楼的轮廓、晨）当过曝的残像，浓淡 ghost_a（1 → 0 慢慢淡掉）。整屏一起，不分前沿。

uniform float blur : hint_range(0.0, 8.0) = 0.0;
uniform float grey_x = -400.0;      // 灰色前沿（屏幕 x，480 宽）
uniform float grey_tail = -9999.0;  // 灰色后沿
uniform float grey_a : hint_range(0.0, 1.0) = 0.92;
uniform float chen_sx = 160.0;      // 晨在屏幕上的 x
uniform float flash = 0.0;          // 闪白：0 = 没有，1 = 满白
uniform float ghost_a = 1.0;        // 满白里过曝残像的浓淡
uniform float chen_lit = 0.0;       // 第四次站着不动、灰从她身边过去：她身上一块软的不被压暗（她是亮的，什么也没发生）
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
	vec2 cd = (vec2(x, px.y) - vec2(chen_sx, 166.0)) / vec2(17.0, 30.0);   // 离晨身子中心多远（她在屏幕上 142～188）（1 = 身子边上）
	float lit = chen_lit * 0.8 * (1.0 - smoothstep(0.6, 1.7, length(cd)));
	// 前沿前面 60 像素先褪色
	float pre = (1.0 - smoothstep(edge, edge + 60.0, x)) * (1.0 - lit);
	col = mix(col, vec3(g), pre * 0.75);
	// 灰：前沿往后 80 像素从淡到浓
	float k = 1.0 - smoothstep(edge - 80.0, edge, x);
	k *= smoothstep(grey_tail - 70.0 + wob, grey_tail + wob, x);
	k = steps(k * (1.0 - lit), px) * grey_a;
	col = mix(col, grey_c.rgb + vec3(g * 0.12), k);
	// 闪白：过曝。lifted = 整幅往白里抬（暗处也抬，曝光过头）；残像 = 比周围暗的地方（人影、轮廓）在满白里留一点灰
	if (flash > 0.001) {
		float e = clamp(flash, 0.0, 1.0);
		vec3 lifted = vec3(1.0) - (vec3(1.0) - col) * pow(1.0 - e, 2.5);
		float m = 0.0;
		for (int i = 0; i < 8; i++) {
			float a = float(i) * 0.7854;
			m += dot(texture(TEXTURE, UV + vec2(cos(a), sin(a)) * 6.0 / BASE).rgb, vec3(0.299, 0.587, 0.114));
		}
		m /= 8.0;
		float shade = clamp((m - g) * 3.0, 0.0, 1.0) * 0.6 + (1.0 - smoothstep(0.02, 0.2, g)) * 0.4;
		vec3 w = white_c.rgb - vec3(shade * 0.13 * ghost_a);
		col = mix(lifted, w, smoothstep(0.3, 1.0, e));
	}
	COLOR = vec4(col, COLOR.a);
}
