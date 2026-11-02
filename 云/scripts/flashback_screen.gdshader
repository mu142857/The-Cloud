shader_type canvas_item;
// 母星闪回（scripts/flashback.gd）：盖在整个画面上的一张 ColorRect，读屏幕。
// 进：画面（连对话框、物件）慢慢糊掉、去色、四角压暗、蒙一层颜色（第一次是雾的发白，别的是暗）。
// 醒：上下两片眼皮（颜色 = veil）慢慢睁开，糊的画面一起变清楚。全 0 的时候原样透过去。
// 模糊半径按 480×270 的像素算（项目是 canvas_items 拉伸，屏幕纹理比 480 大，所以用 UV 偏移，不用 SCREEN_PIXEL_SIZE）。

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float blur : hint_range(0.0, 8.0) = 0.0;
uniform float desat : hint_range(0.0, 1.0) = 0.0;
uniform float vig : hint_range(0.0, 1.0) = 0.0;
uniform float lids : hint_range(0.0, 1.0) = 0.0;   // 眼皮合上多少：1 = 全闭，0 = 睁开
uniform vec4 veil : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float veil_a : hint_range(0.0, 1.0) = 0.0;

const vec2 BASE = vec2(480.0, 270.0);

vec3 blurred(vec2 uv) {
	vec3 c = textureLod(screen_tex, uv, 0.0).rgb;
	if (blur < 0.05) {
		return c;
	}
	c *= 2.0;
	float w = 2.0;
	// 两圈各 8 个点（内圈半径一半，错开半格），近似圆形的模糊
	for (int i = 0; i < 16; i++) {
		float ring = i < 8 ? 0.5 : 1.0;
		float a = float(i) * 0.7854 + (i < 8 ? 0.0 : 0.3927);
		vec2 off = vec2(cos(a), sin(a)) * blur * ring / BASE;
		float k = i < 8 ? 1.0 : 0.7;
		c += textureLod(screen_tex, uv + off, 0.0).rgb * k;
		w += k;
	}
	return c / w;
}

void fragment() {
	vec2 uv = SCREEN_UV;
	vec3 col = blurred(uv);
	float g = dot(col, vec3(0.299, 0.587, 0.114));
	col = mix(col, vec3(g), desat);
	// 四角压暗（意识往里收）
	vec2 d = (UV - 0.5) * vec2(1.0, 0.72);
	col *= 1.0 - vig * smoothstep(0.22, 0.62, length(d));
	col = mix(col, veil.rgb, veil_a);
	// 眼皮：中间那条缝先开，两边（眼角）晚一点
	if (lids > 0.001) {
		float open = 1.0 - lids;
		float dy = abs(UV.y - 0.5) * 2.0 + pow(abs(UV.x - 0.5) * 2.0, 2.0) * 0.22 * lids;
		float e = open * 1.25;
		float m = smoothstep(e - 0.12, e, dy);
		col = mix(col, veil.rgb, m);
	}
	COLOR = vec4(col, 1.0);
}
