shader_type canvas_item;
// 河床上的焦散光纹：挂在 bedlight.png 上（tools/underwater_art.py 画的遮罩：只有朝上、受光的那几行不透明，
// R = 这一格最多能有多亮）。图案是一张 64×64 的 Voronoi 边（caustic.png），两份往不同方向慢慢滚，
// 叠起来（取 max）就是那种一张网一样慢慢扭的光纹；地面是斜着看的，所以竖向压扁。离光柱落点（屏幕 lit_x）越近越亮。
// 亮度分档（整像素、硬边），加法混合。不读屏幕（SCREEN_UV 只是拿来算屏幕 x）。
render_mode blend_add, unshaded;

uniform sampler2D pattern : filter_nearest, repeat_enable;
uniform vec3 color : source_color = vec3(0.5, 0.7, 0.86);
uniform float strength = 0.22;
uniform float speed = 1.0;
uniform float squash = 3.0;             // 竖向压扁几倍
uniform vec2 lit = vec2(300.0, 150.0);  // 屏幕上光柱落点的 x、半宽
uniform float step_a = 0.05;

void fragment() {
	vec2 size = vec2(textureSize(TEXTURE, 0));
	vec2 px = floor(UV * size);
	vec4 m = texture(TEXTURE, (px + 0.5) / size);
	if (m.a < 0.5) {
		discard;
	}
	float tt = TIME * speed;
	vec2 q = vec2(px.x, px.y * squash);
	float c1 = texture(pattern, (q + vec2(tt * 3.1, tt * 1.7)) / 64.0).r;
	float c2 = texture(pattern, (q * 0.83 + vec2(-tt * 2.3, tt * 2.6) + vec2(23.0, 41.0)) / 64.0).r;
	float v = smoothstep(0.4, 0.95, max(c1, c2));          // 两张网叠起来：哪张的边都亮
	float sx = SCREEN_UV.x * 480.0;
	float near = exp(-pow((sx - lit.x) / lit.y, 2.0));
	float a = v * m.r * strength * (0.3 + 0.7 * near);
	float lv = floor(a / step_a);
	if (lv <= 0.0) {
		discard;
	}
	COLOR = vec4(color, lv * step_a);
}
