shader_type canvas_item;
// 影子动物的剪影上色（art/creatures/ 的图只有白和灰两档）：
// 白 = body（影子色），灰（178）= 往 fog 多靠 30%，远侧的腿 / 翅膀。透明的地方不动。
// 两个颜色由 scripts/forest_shadows.gd 按雾带的明暗和远近算好塞进来。

uniform vec4 body = vec4(0.14, 0.2, 0.17, 1.0);
uniform vec4 fog = vec4(0.33, 0.45, 0.38, 1.0);

void fragment() {
	vec4 t = texture(TEXTURE, UV);
	COLOR = vec4(mix(fog.rgb, body.rgb, t.r), t.a);
}
