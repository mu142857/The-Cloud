shader_type canvas_item;
// 四角压暗，带一点青绿（Silvaron 那种暗角；森林的身份色是绿，别偏蓝）。乘法叠在整个画面上。
render_mode blend_mul, unshaded;

uniform float strength = 0.62;
uniform vec3 tint : source_color = vec3(0.86, 0.95, 0.9);

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	p.x *= 1.2;
	float v = smoothstep(0.7, 1.65, length(p));
	vec3 c = mix(vec3(1.0), tint * (1.0 - strength), v);
	COLOR = vec4(c, 1.0);
}
