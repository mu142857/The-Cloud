shader_type canvas_item;
// 湿街面 = 一面暗镜子（第十版，参照 Until Then / The Last Night 那种反光地板；scenes/city_test.tscn 的 Wet/Rect，
// 盖在路沿下面那 80 行上（镜头往下挪了 40，路沿在屏幕 y = ground = 188），画在晨和她身前那排人后面、前景前面，
// 所以前景和前景路人不进倒影；路灯、售货机的光晕（Glow）也画在它后面，不会在倒影里再被照一次）。
// - 整个世界倒过来照：人、晨、路灯、售货机、楼脚、亮着的窗。镜轴在脚底：y = ground+1 照 ground（脚底那一行），
//   往下越照越高、越压越扁（persp：贴着路沿 1:1，晨和人的脚对得上；最下面一行照到路沿上面约 160 行，楼和窗都进来）。
// - 往下越来越暗、越来越冷（refl_near → refl_far，refl_tint 偏冷）；地面本身的石板缝还透一点出来。
// - 倒影有轻微的水平波动：按两行一条，整条左右错 0~ripple 像素（越往下越大），慢慢晃；整像素，不糊。
// - 亮的东西拉出竖直的光条：每一列看上面几行（楼腰的亮窗、日光灯、霾缝，人肩上的受光边、晨的白发），
//   亮过门槛的颜色顺着这一列往下拉成一条，被雨打得断断续续。光条和倒影都比晨的白发暗得多（add_max）。
// - 只读一次屏幕（hint_screen_texture，引擎每帧拷一次），每个像素采样 1 + 1 + 6 次；输出按 1/48 分档，像素画的硬边。
// - 竖光条看的那几行按离路沿多高取（streak_rows）：楼腰的窗、路灯灯头、售货机的屏、人的肩、晨的白发。
render_mode unshaded;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform float cam_left = 0.0;      // 镜头左边缘在世界里的 x（city_test.gd 每帧更新）：光条的断口跟着地面走
uniform float chen_x = 204.0;      // 晨在屏幕上的 x（city_test.gd 每帧更新；现在晨也照进镜子，留着备用）
uniform float ground = 188.0;      // 路沿受光边那一行（脚底），屏幕坐标（场景里按 city_art.py 的 GROUND - CAM_DY 写）
uniform float persp = 0.0125;      // 倒影往下压扁多少：第 d 行照路沿上面 d·(1 + persp·d) 行
uniform float refl_near = 0.7;     // 贴着路沿的反射率
uniform float refl_far = 0.3;      // 最下面的反射率
uniform vec3 refl_tint = vec3(0.78, 0.86, 0.97);
uniform float floor_keep = 0.55;   // 地面本身的颜色留几成（石板缝、路面）
uniform float ripple = 1.6;        // 最下面那几行左右晃多少像素
uniform float streak = 0.95;       // 竖光条的强度
uniform float add_max = 0.16;      // 光条每个像素最多加这么多（sRGB 0..1）
uniform float streak_len = 0.35;   // 光条往下淡掉多少（0 = 一直到底一样亮）

const vec2 RES = vec2(480.0, 270.0);

float h1(float n) { return fract(sin(n * 12.9898) * 43758.5453); }

vec3 src(vec2 p) {
	return texture(screen_tex, (clamp(p, vec2(0.0), RES - 1.0) + 0.5) / RES).rgb;
}

float lum(vec3 c) { return dot(c, vec3(0.3, 0.59, 0.11)); }

void fragment() {
	vec2 px = floor(SCREEN_UV * RES);
	vec3 base = src(px);
	float d = px.y - ground;                       // 路沿下面第几行（1 起）：镜轴在脚底那一行下沿，倒影从脚底接着往下，中间没有缝
	float wx = floor(px.x + cam_left);
	float depth = clamp((d - 1.0) / (RES.y - ground - 2.0), 0.0, 1.0);
	// 水平波动：两行一条，整条一起慢慢左右错；再加雨点打出来的小断口（一小段错 1 像素，0.25 秒换一次）
	float band = floor(d / 2.0);
	float amp = ripple * mix(0.2, 1.0, depth);
	float off = floor(sin(band * 1.9 + TIME * 1.3) * amp + 0.5);
	float cell = floor(wx / 13.0);
	off += step(0.86, h1(cell * 3.7 + band * 11.1 + floor(TIME * 4.0) * 1.3)) * (h1(cell + band) < 0.5 ? -1.0 : 1.0);
	// 镜子
	float sy = floor(ground + 1.0 - d * (1.0 + persp * d) + 0.5);
	vec3 refl = src(vec2(px.x + off, sy));
	float k = mix(refl_near, refl_far, depth);
	vec3 col = base * mix(1.0, floor_keep, k / refl_near) + refl * refl_tint * k;
	// 竖光条：这一列上面几处亮的颜色（楼腰的窗和灯、人和晨的受光边、白发），往下拉成一条
	vec3 acc = vec3(0.0);
	float rx = px.x + off;
	float ys[6] = {150.0, 112.0, 88.0, 62.0, 38.0, 24.0};
	for (int j = 0; j < 6; j++) {
		vec3 c = src(vec2(rx, ground - ys[j]));
		acc = max(acc, c * smoothstep(0.32, 0.6, lum(c)));
	}
	float gap = step(h1(wx * 0.31 + floor(d / 3.0) * 1.7 + floor(TIME * 3.0) * 5.1), 0.12);
	float prof = (1.0 - depth * streak_len) * step(2.0, d);
	vec3 add = min(acc * refl_tint * streak * prof * (1.0 - gap), vec3(add_max));
	col += add;
	COLOR = vec4(floor(col * 48.0 + 0.5) / 48.0, 1.0);
}
