shader_type canvas_item;
// 晨的精灵（scenes/chen.tscn 的 Sprite）：让场景的光落到她身上。参数全由 chen.gd 的 set_env / _update_light 每帧给，别在这里调。
// 1. 斗篷暗部偏一点场景色：按亮度分，越暗的像素染得越多（tint_amt），白发几乎不染，亮度不变 —— 只换色相，晨不会变亮也不会变暗。
// 2. 受光边：朝光源那一侧、贴着透明邻居的像素（1 像素宽）加一道场景光的颜色；往里第二个像素加半档。
//    方向 rim_dir 是「纹理里」的方向（chen.gd 已经把屏幕方向按翻转、旋转换算好），所以 flip_h、被甩出飞船时转 90° 都不会错。
//    rim_back > 0 = 背光（森林的雾光在她身后）：左右两侧的边也亮一点，像被身后的光包了一圈。
// 3. 走进光里（boost 0..1，chen.gd 平滑过）：受光边和斗篷的染色变强，斗篷再提亮一点。白发不动，始终最亮。
// 帧在图集里左右相邻，四周至少 4 像素透明（实测），这里最远采 2 像素，不会采到隔壁帧。
// 输出 alpha 原样（只有 0/255），颜色按 1/64 分档，免得在像素图上出现一大堆近似色。

uniform vec3 tint : source_color = vec3(0.5);
uniform float tint_amt = 0.0;
uniform vec3 rim_color : source_color = vec3(1.0);
uniform float rim_amt = 0.0;
uniform vec2 rim_dir = vec2(0.0, -1.0);
uniform float rim_back = 0.0;
uniform float boost = 0.0;
uniform float boost_rim = 0.8;      // 光里受光边多亮（乘到 rim_amt 上的额外倍数）
uniform float boost_tint = 0.6;     // 光里染色多加多少
uniform float boost_body = 0.18;    // 光里斗篷提亮多少（只对暗像素）

varying vec4 modc;      // modulate（淡入淡出照常）

void vertex() {
	modc = COLOR;
}

float lum(vec3 c) { return dot(c, vec3(0.3, 0.59, 0.11)); }

float clear_at(vec2 uv, vec2 d) {
	return step(texture(TEXTURE, uv + d * TEXTURE_PIXEL_SIZE).a, 0.5);
}

// 这个像素在方向 d（整像素）上是不是「边」：邻居透明 = 1；邻居不透明但再往外一格透明 = 0.5（往里半档）
float edge(vec2 uv, vec2 d) {
	float e1 = clear_at(uv, d);
	float e2 = clear_at(uv, d * 2.0);
	return max(e1, 0.5 * e2);
}

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	if (c.a < 0.5) {
		COLOR = vec4(0.0);
	} else {
		vec3 col = c.rgb;
		float L = lum(col);
		float dark = 1.0 - smoothstep(0.3, 0.7, L);      // 斗篷 L≈0.13~0.25 → 1；手腿 ≈0.4 → 0.7；白发 0.85+ → 0
		// 1. 染色：保持亮度，色相往场景色挪
		float ta = clamp(tint_amt * (1.0 + boost_tint * boost), 0.0, 1.0) * dark;
		vec3 tinted = tint * (L / max(lum(tint), 0.01));
		col = mix(col, tinted, ta);
		col *= 1.0 + boost_body * boost * dark;
		// 2. 受光边
		vec2 d = rim_dir;
		float r = 0.0;
		float wx = abs(d.x), wy = abs(d.y);
		if (wx > 0.15) r += wx * edge(UV, vec2(sign(d.x), 0.0));
		if (wy > 0.15) r += wy * edge(UV, vec2(0.0, sign(d.y)));
		if (wx > 0.15 && wy > 0.15) r = max(r, 0.8 * edge(UV, sign(d)) * min(wx + wy, 1.0));
		if (rim_back > 0.0) {
			float side = max(clear_at(UV, vec2(1.0, 0.0)), clear_at(UV, vec2(-1.0, 0.0)));
			r = max(r, rim_back * side);
		}
		r = clamp(r, 0.0, 1.0);
		float ra = rim_amt * (1.0 + boost_rim * boost);
		// 受光边是「加」上去的场景光；亮的像素（白发）吃得少一点，免得糊成一片白
		col += rim_color * r * ra * mix(1.0, 0.35, 1.0 - dark);
		col = floor(clamp(col, 0.0, 1.0) * 64.0 + 0.5) / 64.0;
		COLOR = vec4(col, 1.0) * modc;
	}
}
