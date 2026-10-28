shader_type canvas_item;
// 水底会摆的植物（tools/underwater_art.py 画的 kelp / bedweeds / front / headweeds）共用：
// 贴图最下面一行就是根；每一行按「离根多高」左右错 0~amp 像素（整像素，不糊）。
// 相位沿 x 往一个方向走（像一股慢慢推过去的水流），沿 y 也错一点（带子是 S 形地弯，不是整根平移）。
// 只读自己的贴图一次，不读屏幕。Sprite 要开 texture_repeat（层是左右无缝的，错到边外从另一头取）。
// wavelength 要是 960 的约数（160、192、240、320…），不然在层的接缝上相位会断。
render_mode unshaded;

uniform float amp = 3.0;            // 最高处最多错几像素
uniform float speed = 0.55;         // 摆的快慢（弧度 / 秒）
uniform float wavelength = 160.0;   // 水流的「波长」（像素）
uniform float power = 1.6;          // 越大：根部越稳、只有上半截在摆
uniform float bend = 0.05;          // 沿 y 的相位差：越大越像 S 形

void fragment() {
	vec2 size = vec2(textureSize(TEXTURE, 0));
	vec2 px = floor(UV * size);
	float h = (size.y - 1.0 - px.y) / size.y;                 // 0 = 根，1 = 贴图顶
	float ph = TIME * speed - px.x / wavelength * 6.2831853;
	float s = 0.75 * sin(ph + px.y * bend) + 0.25 * sin(1.9 * ph + px.y * bend * 2.7 + 1.3);
	float off = round(amp * pow(h, power) * s);
	vec4 c = texture(TEXTURE, (vec2(px.x - off, px.y) + 0.5) / size);
	if (c.a < 0.5) {
		discard;
	}
	COLOR = c;
}
