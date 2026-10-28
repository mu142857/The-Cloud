shader_type canvas_item;
// 远处的影子（鲸、鱼群）：乘法混合。贴图 / draw_rect 的颜色不是「画什么色」，是「把后面的水乘多少」
// （0.8 = 暗两成）。所以影子永远是同一片水再暗一点：跟着背后水色的渐变、Bayer 抖动和月光走，不会变成一块实心剪影。
// 透明的像素直接丢掉（乘法混合下 alpha 不起作用，不丢会把水乘黑）。硬边，不读屏幕。
render_mode blend_mul, unshaded;

void fragment() {
	vec4 c = texture(TEXTURE, UV) * COLOR;
	if (c.a < 0.5) {
		discard;
	}
	COLOR = vec4(c.rgb, 1.0);
}
