shader_type canvas_item;
// 细雨的雨丝（scripts/city_rain.gd 的 GPUParticles2D 用）：贴图 × 粒子颜色（出生淡入、到点淡出），再
// - 落进路灯光锥（lights，这一层的坐标，左右按 wrap 绕回）里的，颜色往 color_lit 拉、alpha 乘 lit_boost，越往下越淡；
// - y_dim 以下（晨身后那条）alpha 乘 dim；
// - 过了 bottom 那一行的裁掉（雨打到地上）；
// - only_lit：光锥外面的全透明（灯下那一阵密雨那个节点用）。
// 位置：VERTEX 只是那一根雨丝自己的小方块，粒子的位置在 MODEL_MATRIX 里（节点的全局变换 × 粒子变换）；
// 再乘 city_rain.gd 每帧传进来的 to_local（节点全局变换的逆）回到图层坐标。
render_mode blend_mix, unshaded;

uniform vec4 lights[4];
uniform int n_lights = 0;
uniform float light_bottom = 228.0;
uniform vec4 color_lit : source_color = vec4(0.66, 0.72, 0.75, 1.0);
uniform float lit_boost = 2.6;
uniform float y_dim = 183.0;
uniform float dim = 0.45;
uniform float wrap = 960.0;
uniform float bottom = 228.0;
uniform bool only_lit = false;     // 只画光锥里的（灯下那一阵密雨）

uniform mat4 to_local;

varying vec2 lp;

void vertex() {
	lp = (to_local * (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0))).xy;
}

void fragment() {
	vec4 c = COLOR * texture(TEXTURE, UV);
	float lit = 0.0;
	for (int i = 0; i < n_lights; i++) {
		vec4 l = lights[i];
		float t = (lp.y - l.y) / max(1.0, light_bottom - l.y);
		float half_w = max(1.0, mix(l.z, l.w, clamp(t, 0.0, 1.0)));
		float dx = abs(mod(lp.x - l.x + wrap * 0.5, wrap) - wrap * 0.5);
		float k = step(0.0, t) * step(t, 1.0) * (1.0 - smoothstep(half_w * 0.55, half_w, dx)) * mix(1.0, 0.35, t);
		lit = max(lit, k);
	}
	c.rgb = mix(c.rgb, color_lit.rgb, lit);
	c.a *= (only_lit ? lit : 1.0) * mix(1.0, lit_boost, lit) * mix(1.0, dim, smoothstep(y_dim - 6.0, y_dim + 6.0, lp.y) * (1.0 - lit));
	c.a *= 1.0 - smoothstep(bottom - 1.5, bottom, lp.y);
	COLOR = c;
}
