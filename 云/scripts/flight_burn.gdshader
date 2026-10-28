shader_type canvas_item;
// 决定卡烧掉：从四条边往里烧成灰。整像素（按卡的 1 倍像素算），烧到的地方先是一圈亮的火线，里面一圈焦黑，再往外就没了。
uniform float burn : hint_range(0.0, 1.3) = 0.0;
uniform vec2 size = vec2(212.0, 154.0);
uniform float fade = 1.0;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

void fragment() {
	vec2 px = floor(UV * size) + 0.5;
	vec4 c = texture(TEXTURE, UV);
	float e = min(min(px.x, size.x - px.x), min(px.y, size.y - px.y)) / (0.5 * min(size.x, size.y));
	float n = vnoise(px / 11.0) * 0.6 + vnoise(px / 4.0) * 0.4;
	float t = e * 0.8 + n * 0.45;          // 0（边上）.. ~1.25（中间）
	float b = burn * 1.3;
	if (burn > 0.0) {
		if (t < b) {
			c.a = 0.0;
		} else if (t < b + 0.035) {
			c = vec4(mix(vec3(1.0, 0.78, 0.38), vec3(1.0, 0.95, 0.75), step(0.5, hash(px))), c.a > 0.0 ? 1.0 : 0.0);
		} else if (t < b + 0.07) {
			c = vec4(0.85, 0.36, 0.14, c.a > 0.0 ? 1.0 : 0.0);
		} else if (t < b + 0.13) {
			c.rgb = mix(c.rgb, vec3(0.09, 0.06, 0.05), 0.75);
		}
	}
	c.a *= fade;
	COLOR = c;
}
