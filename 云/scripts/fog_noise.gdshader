shader_type canvas_item;
// 起雾前景（照作者 Phage 里那套 back_ground_smoke 的做法自己写的一份）：
// 一张无缝噪声贴图（FastNoiseLite → NoiseTexture2D，nearest 取样，按 480×270 原生像素），UV 随时间慢慢滚，
// fog = clamp(noise * 2.25 - 1, 0, 1)，再乘 density 和往上变淡的竖直渐变。
// 我们多两样：fill = 把雾团之间的空隙也填上一层（最浓时远景几乎看不见），steps = 透明度按档变（像素画的硬边，不平滑渐变）。
// 颜色由节点的 modulate 给（森林远景的冷青绿灰）。用法见 scripts/story_world.gd 的 _make_fog_layer。

uniform sampler2D noise_texture : repeat_enable, filter_nearest;
uniform float density : hint_range(0.0, 1.0) = 0.3;
uniform float fill : hint_range(0.0, 1.0) = 0.0;
uniform vec2 speed = vec2(0.01, 0.0);
uniform float gradient_pow = 3.0;      // 竖直渐变：越往下越浓（UV.y 大 = 靠下）
uniform float gradient_min = 0.2;
uniform float steps = 5.0;             // 透明度分几档（0 = 不分档）

void fragment() {
	vec2 uv = UV + speed * TIME;
	float n = texture(noise_texture, uv).r;
	float fog = clamp(n * 2.25 - 1.0, 0.0, 1.0);
	fog = mix(fog, 1.0, fill);
	float g = clamp(pow(UV.y, gradient_pow), gradient_min, 1.0);
	float a = fog * density * g;
	if (steps > 0.0) {
		a = floor(a * steps * 4.0 + 0.5) / (steps * 4.0);
	}
	COLOR = vec4(1.0, 1.0, 1.0, a) * COLOR;
}
