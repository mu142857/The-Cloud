shader_type canvas_item;
// 晨那条街上一排人的明度（scripts/city_crowd.gd 的 ramp 打开时用）：兜帽人帧图是灰度档（30..176 身子各档、200 湿的反光、255 冷色轮廓光），
// 这里不再「乘一个染色」，而是把灰度档映射到这一排自己的一段明度：lo（最暗的档）到 hi（最亮的档），受光边单独一个 rim。
// 灰度档 240 是手机屏的冷光（glow）。
// 远排 lo/hi 都往雾的颜色靠（浅、平），近排压到近黑（暗、对比小），中间那排在两者之间、细节最多 ——
// 一排一排用明度分开，全都不透明（alpha 只有 0/1），近排整个盖住远排。
// 每个人的配色（city_crowd.gd 的 HUES，冷灰里一点点差别）从顶点色进来，乘在结果上。
render_mode unshaded;

uniform vec4 lo : source_color = vec4(0.1, 0.1, 0.11, 1.0);
uniform vec4 hi : source_color = vec4(0.2, 0.2, 0.21, 1.0);
uniform vec4 rim : source_color = vec4(0.3, 0.3, 0.31, 1.0);
// 灰度档 240：低头看的手机屏，一点冷光（几个像素，比晨的白发暗得多）
uniform vec4 glow : source_color = vec4(0.45, 0.55, 0.6, 1.0);

varying vec4 vcol;

void vertex() {
	vcol = COLOR;
}

void fragment() {
	if (vcol.a < 0.99) {          // 半透明的顶点色 = 脚下的接触阴影（city_crowd.gd 画的 draw_rect），原样画
		COLOR = vcol;
	} else {
	vec4 t = texture(TEXTURE, UV);
	float g = t.r * 255.0;
	// 灰度档 200：湿的反光（大衣背上、伞面），介于这一排最亮的档和轮廓光之间
	vec3 c = g > 248.0 ? rim.rgb : (g > 225.0 ? glow.rgb : (g > 190.0 ? mix(hi.rgb, rim.rgb, 0.5)
		: mix(lo.rgb, hi.rgb, clamp((g - 30.0) / 146.0, 0.0, 1.0))));
	COLOR = vec4(c * vcol.rgb, step(0.5, t.a));
	}
}
