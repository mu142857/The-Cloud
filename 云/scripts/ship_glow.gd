extends Node2D
## 飞船上下挪时船身周围的「反重力」泛光（10-29 作者：「飞船直接上下平移看着很奇怪……上下平移的时候周围泛光，毕竟外星科技」）。
## 驾驶舱（cockpit_room.gd，躲碎石时整艘船上下挪；flight1 开头往上升）、森林起飞过场（飞船离地升起）、河流篇起飞共用这一个节点。
##
## 10-30 改成「均匀的一圈」（作者：「你这个也不平均啊你的上下移动飞船的光」——原来船底亮 16 像素、上沿 12 像素，
##   往哪边挪哪边亮，看着一边厚一边薄）：现在不分船底 / 上沿 / 两侧，整圈同一个亮度、同一个距离 REACH（× reach_scale），
##   沿船身轮廓往外一圈一圈扩（八边形，接近圆），机头、尾翼、船腹一样厚；不管往上还是往下挪都一样。
##   离船身越远越淡：4 档透明度台阶（1 / .75 / .5 / .25 × max_alpha），颜色贴着船身 INNER → MID → 外圈 OUTER。
##   紧贴船身那 1 像素降 GAP_DROP 档：留一道暗缝，船身的轮廓不被光糊掉（亮主角暗背景：光是给船加的）。
##   亮到一半以上时：整圈每 RIPPLE_SEC 秒往外散一道 1 像素的虚线光纹；微光粒子从船身四周往外飘；整圈光慢慢「呼吸」（BREATH_SEC）。
##   光强的显示曲线是 sqrt(strength)：同样的 strength 画得更显眼。
##
## 10-30 加「热」（作者：「为什么最开始上升的时候没有外侧的光，我觉得红光不错」）：heat（0..1）把整圈光从青绿换成暖红
##   （HOT_*，和森林坠毁的余火、起飞尾焰同一组红：tools/level1_art.py 的 EMBER / FLAME），并且推进器那头（hot_side）最亮、照得最远，
##   机头那头暗一点、近一点（沿船长分 NB 段渐变）。起飞上升用热光；躲碎石上下挪用青绿光。
##   heat 不直接设：设 heat_goal，heat 每秒最多走 1 / HEAT_SEC，画的时候再过一道 smoothstep（缓起缓停，颜色慢慢换，不硬切）。
##   drive() 里一旦船按速度在挪（而且没有 hold_goal），heat_goal 自动回 0：从起飞的红光平滑换回青绿。
## 托底：hold_goal（0..1）= 「至少这么亮」，hold 每秒最多走 HOLD_RATE（慢慢亮起、慢慢收掉）；drive() 的光强 = max(按速度算的, hold)。
##   驾驶舱 flight1 开头往上升那几秒：hold_goal = 0.8、heat_goal = 1，升完 hold_goal = 0（cockpit_room.gd 按窗外状态设）。
##
## 怎么算的：轮廓 = 每列最上 / 最下那个不透明像素（这一列中间当实心）；把它一圈一圈往外扩（八边形，接近圆，见 _build），
##   第 d 圈 = 离船身 d 像素；按列在船长方向的位置分 NB 段（热光的渐变用）。
##   按（段, 距离）预先合成一条条长条（相邻列一样高的横着合），每帧每组只算一次透明度，画的块数在几千以内。
##   同一个轮廓算过就缓存（森林起飞的船按角度换帧，换一帧换一次轮廓）。位置全取整，像素硬边。
##   本节点当船的图（Sprite2D）的子节点，show_behind_parent = true 画在船图后面；光只在轮廓外面，不盖船身和晨。
## 光强：strength（0..1）。两种用法：
##   1）每帧 drive(vy, delta)：vy = 船现在的竖直速度（像素 / 秒，正 = 往下），自己按速度算光强（|vy| ≥ full_speed 时满），
##      亮起来快（RISE / 秒）、停住以后慢慢熄（FALL / 秒，满亮到熄完约 0.6 秒）；|vy| < DEAD 当没动：平时 ±1 像素的慢起伏完全不亮。
##   2）自己设 strength，不调 drive，每帧调 step(delta)。比如起飞过场的预热。
##
## 用法（驾驶舱见 cockpit_room.gd setup()；森林起飞见 level_forest.gd _lift_setup()）：
##   const SHIP_GLOW := preload("res://scripts/ship_glow.gd")
##   var glow: Node2D = SHIP_GLOW.new()
##   ship_sprite.add_child(glow)                       # 跟着船一起动；glow 自己设了 show_behind_parent = true，画在船图后面
##   glow.set_from_texture(ship_sprite.texture, 图左上角在 glow 父节点里的坐标)
##       # centered 的 Sprite2D：-texture.get_size() / 2 + sprite.offset；centered = false：sprite.offset
##       # 多帧的图（hframes）：第三个参数给一帧的 Rect2i，比如 Rect2i(0, 0, 帧宽, 帧高)
##   或者 glow.set_hull(第 0 列的 x, 每列上沿, 每列下沿)
##   每帧：glow.drive(船这一帧的竖直速度, delta)   或者   glow.strength = x; glow.step(delta)
##   full_speed（默认 45 像素 / 秒）：多快算满亮；max_alpha（默认 0.8）：最亮那档的透明度；reach_scale（默认 1）：光照多远的倍数；
##   heat_goal / hold_goal 见上；hot_side（默认 +1）：推进器在轮廓右头（机头朝左）。
## 不需要的时候 strength = 0 就什么都不画（也不 queue_redraw）。

const INNER := Color("#c3e8d4")        # 贴着船身
const MID := Color("#a1d7bc")          # 中间
const OUTER := Color("#7fc7a4")        # 最外圈
const HOT_INNER := Color("#e8795a")    # 热光：贴着船身（尾焰 FLAME[1] 往红推）
const HOT_MID := Color("#c9473a")      # 红（余火 EMBER 那一族）
const HOT_OUTER := Color("#962f2c")    # 最外圈暗红（FLAME[0]，略提亮：暗背景上还读得出是红光）
const REACH := 14                      # 光往外多远（像素；满亮时实际亮到 11～12 像素，见 _level）
const NB := 12                         # 沿船长分几段（热光从机头到推进器渐变）
const HOT_W := Vector2(0.4, 1.05)      # 热光的亮度倍数：机头那头 → 推进器那头
const HOT_R := Vector2(0.7, 1.3)       # 热光照多远的倍数：机头那头 → 推进器那头
const FALLOFF := 1.8                   # 往外淡的曲线（> 1：贴着船身那档窄、外圈宽）
const R_MAX := 34                      # 轮廓往外预先算多远（够 reach_scale 1.5 的热光、光纹散到头）
const RIPPLE_GO := 22                  # 光纹散多远（× reach_scale）
const GAP_DROP := 2                    # 紧贴船身那 1 像素降几档（暗缝，保住船的轮廓）
const RISE := 6.0                      # 光强每秒最多涨多少
const FALL := 1.6                      # 停住以后每秒熄多少（满亮 → 熄完约 0.6 秒）
const DEAD := 3.0                      # 竖直速度小于这个（像素 / 秒）当没动
const HEAT_SEC := 0.9                  # 青绿 ↔ 暖红换一次多少秒
const HOLD_RATE := 0.7                 # 托底每秒最多变多少
const RIPPLE_SEC := 0.75               # 光纹多久散一道
const BREATH_SEC := 0.9                # 整圈光「呼吸」一个来回多少秒
const MOTE_RATE := 40.0                # 满亮时每秒冒多少颗微光粒子

const BIG := 1 << 20

var strength := 0.0                    # 0..1
var dir := 0.0                         # 最后一次挪的方向（-1 上 / +1 下）；现在只决定微光粒子往哪边多一点，光本身不分上下
var full_speed := 45.0
var max_alpha := 0.8
var reach_scale := 1.0                 # 光照多远 × 这个（船在画面上大的地方调大，比如驾驶舱 1.5；最多 1.5）
var heat := 0.0                        # 0 青绿 .. 1 暖红（跟着 heat_goal 慢慢走）
var heat_goal := 0.0
var hold := 0.0                        # 托底亮度（跟着 hold_goal 慢慢走）
var hold_goal := 0.0
var hot_side := 1.0                    # 推进器在哪头：+1 轮廓右头 / -1 左头

var _cols_bot := PackedInt32Array()    # 每列船底 y（-1 = 这列空），船身自己的坐标（不含 _origin）
var _cols_top := PackedInt32Array()
var _row_y0 := 0                       # _row_l / _row_r 第 0 行的 y
var _row_l := PackedInt32Array()       # 每行最左 / 最右的船身列
var _row_r := PackedInt32Array()
var _origin := Vector2.ZERO
var _rings: Array = []                 # [段][距离] = Array[Rect2]（本节点坐标，已加 _origin）
var _cache := {}                       # 轮廓的 hash → [_rings, _row_y0, _row_l, _row_r]
var _t := 0.0
var _mote_acc := 0.0
var _motes: Array = []                 # {p, v, life, age}（船身坐标）
var _rng := RandomNumberGenerator.new()
var _drawn := false


func _init() -> void:
	name = "ShipGlow"
	show_behind_parent = true
	_rng.seed = 7


## 从船的图算轮廓。origin = 图（或 region）左上角在本节点父节点坐标里的位置；region = 只用图里这一块（多帧的图给一帧）
func set_from_texture(tex: Texture2D, origin := Vector2.ZERO, region := Rect2i()) -> void:
	_cols_bot = PackedInt32Array()
	_cols_top = PackedInt32Array()
	_origin = origin.round()
	_rings = []
	if tex == null:
		return
	var img := tex.get_image()
	if img == null:
		return
	if img.is_compressed():
		img.decompress()
	var r := region if region.size != Vector2i.ZERO else Rect2i(Vector2i.ZERO, img.get_size())
	for x in r.size.x:
		var t := -1
		var b := -1
		for y in r.size.y:
			if img.get_pixel(r.position.x + x, r.position.y + y).a > 0.1:          # 半透明的机尾壳也算船身
				if t < 0:
					t = y
				b = y
		_cols_top.append(t)
		_cols_bot.append(b)
	_build()
	queue_redraw()


## 直接给轮廓（每列上沿 / 下沿，上下沿都是 -1 = 空列；x0 = 第 0 列在本节点里的 x，y 也是本节点坐标，可以是负的：
## 森林起飞的船以船中心为原点）。里面统一挪成从 0 开始（_cols_* 里 -1 才能当空列），挪的量记在 _origin.y
func set_hull(x0: int, tops: PackedInt32Array, bots: PackedInt32Array) -> void:
	var lo := 0
	for i in tops.size():
		if not (tops[i] == -1 and bots[i] == -1):
			lo = mini(lo, tops[i])
	_origin = Vector2(x0, lo)
	_cols_top = PackedInt32Array()
	_cols_bot = PackedInt32Array()
	for i in tops.size():
		var empty := tops[i] == -1 and bots[i] == -1
		_cols_top.append(-1 if empty else tops[i] - lo)
		_cols_bot.append(-1 if empty else bots[i] - lo)
	_build()
	queue_redraw()


## 按（段, 距离）把船外的像素合成长条。距离 = 把船身一圈一圈往外扩（单数圈 8 邻、双数圈 4 邻交替：八边形，接近圆；
## 斜的地方（机头、尾翼）也是一圈均匀的厚度），第 d 圈新盖到的像素离船身 d。每列只记两条边界：盖到的最上 up[x]、最下 dn[x]。
## 段 = 这一列在船长方向的位置（第一列船身 → 最后一列船身分 NB 段；船身左右外面的列归两头那段）
func _build() -> void:
	var key := hash([_origin, _cols_top, _cols_bot])
	if _cache.has(key):
		var cached: Array = _cache[key]
		_rings = cached[0]
		_row_y0 = cached[1]
		_row_l = cached[2]
		_row_r = cached[3]
		return
	_rings = []
	var n := _cols_bot.size()
	var y0 := BIG
	var y1 := -1
	var c0 := -1
	var c1 := -1
	for c in n:
		if _cols_top[c] >= 0:
			y0 = mini(y0, _cols_top[c])
			y1 = maxi(y1, _cols_bot[c])
			if c0 < 0:
				c0 = c
			c1 = c
	if c0 < 0:
		return
	# 每行最左 / 最右的船身列（两侧的微光粒子从这冒）
	var rows := y1 - y0 + 1
	_row_y0 = y0
	_row_l = PackedInt32Array()
	_row_l.resize(rows)
	_row_l.fill(-1)
	_row_r = PackedInt32Array()
	_row_r.resize(rows)
	_row_r.fill(-1)
	for c in n:
		var t := _cols_top[c]
		if t < 0:
			continue
		for y in range(t - y0, _cols_bot[c] - y0 + 1):
			if _row_l[y] < 0:
				_row_l[y] = c
			_row_r[y] = c
	for b in NB:
		var by_d: Array = []
		for d in R_MAX + 1:
			by_d.append([])
		_rings.append(by_d)
	# 往外扩：左右各多算 R_MAX 列
	var m := n + 2 * R_MAX
	var up := PackedInt32Array()
	up.resize(m)
	up.fill(BIG)
	var dn := PackedInt32Array()
	dn.resize(m)
	dn.fill(-BIG)
	for c in n:
		if _cols_top[c] >= 0:
			up[c + R_MAX] = _cols_top[c]
			dn[c + R_MAX] = _cols_bot[c]
	var band := PackedInt32Array()
	band.resize(m)
	for x in m:
		var f := clampf(float(x - R_MAX - c0) / float(maxi(1, c1 - c0)), 0.0, 1.0)
		band[x] = mini(NB - 1, int(f * NB))
	var ox := int(_origin.x) - R_MAX
	var oy := int(_origin.y)
	var last := {}                                    # 组 → 这组最后一条长条的下标（相邻列一样高的横着合）
	for d in range(1, R_MAX + 1):
		var nu := up.duplicate()
		var nd := dn.duplicate()
		for x in m:
			var l := maxi(x - 1, 0)
			var r := mini(x + 1, m - 1)
			if d % 2 == 1:
				var u := mini(mini(up[l], up[x]), up[r])
				var v := maxi(maxi(dn[l], dn[x]), dn[r])
				nu[x] = u - 1 if u < BIG else BIG
				nd[x] = v + 1 if v > -BIG else -BIG
			else:
				nu[x] = mini(mini(up[l], up[r]), up[x] - 1 if up[x] < BIG else BIG)
				nd[x] = maxi(maxi(dn[l], dn[r]), dn[x] + 1 if dn[x] > -BIG else -BIG)
			if nu[x] >= BIG:
				continue
			if up[x] >= BIG:                          # 这一列这圈才第一次盖到：整段都是新的
				_put(band[x], x, nu[x], nd[x], d, ox, oy, last)
			else:
				if nu[x] < up[x]:
					_put(band[x], x, nu[x], up[x] - 1, d, ox, oy, last)
				if nd[x] > dn[x]:
					_put(band[x], x, dn[x] + 1, nd[x], d, ox, oy, last)
		up = nu
		dn = nd
	_cache[key] = [_rings, _row_y0, _row_l, _row_r]


## 第 d 圈在第 x 列新盖到的一段 [ya, yb] 放进第 b 段的组；和这组上一条同高、紧挨着就横着合
func _put(b: int, x: int, ya: int, yb: int, d: int, ox: int, oy: int, last: Dictionary) -> void:
	var arr: Array = _rings[b][d]
	var k := b * 64 + d
	var px := float(ox + x)
	var py := float(oy + ya)
	var h := float(yb - ya + 1)
	if last.has(k):
		var r: Rect2 = arr[int(last[k])]
		if r.end.x == px and r.position.y == py and r.size.y == h:
			r.size.x += 1.0
			arr[int(last[k])] = r
			return
	arr.append(Rect2(px, py, 1.0, h))
	last[k] = arr.size() - 1


## 按船的竖直速度（像素 / 秒，正 = 往下）推光强：快亮慢熄；托底 hold 以下不熄
func drive(vy: float, delta: float) -> void:
	var want := clampf((absf(vy) - DEAD) / maxf(1.0, full_speed - DEAD), 0.0, 1.0)
	if absf(vy) > 4.0:
		dir = signf(vy)
	if want > 0.05 and hold_goal <= 0.0:
		heat_goal = 0.0                               # 按速度挪（躲碎石）：换回青绿
	want = maxf(want, hold)
	if want > strength:
		strength = move_toward(strength, want, RISE * delta)
	else:
		strength = move_toward(strength, want, FALL * delta)
	step(delta)


## 只走时间（热、托底、粒子、光纹、呼吸）；自己设 strength 时每帧调这个（drive 里已经调了）
func step(delta: float) -> void:
	_t += delta
	heat = move_toward(heat, heat_goal, delta / HEAT_SEC)
	hold = move_toward(hold, hold_goal, HOLD_RATE * delta)
	var v := sqrt(clampf(strength, 0.0, 1.0))
	# 微光粒子：光越亮冒得越多，从船身四周往外飘
	if v > 0.4 and not _cols_bot.is_empty():
		_mote_acc += delta * MOTE_RATE * v
		while _mote_acc >= 1.0:
			_mote_acc -= 1.0
			_spawn_mote(v)
	else:
		_mote_acc = 0.0
	for k in range(_motes.size() - 1, -1, -1):
		var m: Dictionary = _motes[k]
		m["age"] = float(m["age"]) + delta
		m["p"] = (m["p"] as Vector2) + (m["v"] as Vector2) * delta
		if float(m["age"]) >= float(m["life"]):
			_motes.remove_at(k)
	if strength > 0.0 or not _motes.is_empty() or _drawn:
		queue_redraw()


## 画的时候用的热：smoothstep（换色缓起缓停）
func _hs() -> float:
	return smoothstep(0.0, 1.0, heat)


func _spawn_mote(v: float) -> void:
	var hs := _hs()
	var r := _rng.randf()
	var p := Vector2.ZERO
	var vel := Vector2.ZERO
	var drift := _rng.randf_range(3.0, 10.0)                      # 船往左飞：粒子都往后（右）带一点
	if r < 0.2 and not _row_l.is_empty():                           # 两头（机头 / 机尾外面）
		var i := _rng.randi_range(0, _row_l.size() - 1)
		if _row_l[i] < 0:
			return
		var s := -1.0 if _rng.randf() < 0.5 else 1.0
		if hs > 0.0 and _rng.randf() < 0.6 * hs:
			s = hot_side                                            # 热光：推进器那头冒得多
		p = Vector2((_row_l[i] - 2) if s < 0.0 else (_row_r[i] + 2), _row_y0 + i)
		vel = Vector2(s * _rng.randf_range(8.0, 18.0) + drift, _rng.randf_range(-4.0, 4.0))
	else:
		var top := _rng.randf() < 0.5 + 0.15 * (-dir)                # 上下各一半（往哪挪那边稍多一点）
		var cols := _cols_top if top else _cols_bot
		var n := cols.size()
		var u := _rng.randf()
		if hs > 0.0:
			u = lerpf(u, 1.0 - pow(1.0 - u, 2.5), hs)               # 热光：偏推进器那头
			if hot_side < 0.0:
				u = 1.0 - u
		var c := clampi(int(u * n), 0, n - 1)
		if cols[c] < 0:
			return
		p = Vector2(c, cols[c] + (-2 if top else 2))
		vel = Vector2(drift, (-1.0 if top else 1.0) * _rng.randf_range(12.0, 28.0))
	_motes.append({"p": p, "v": vel, "life": _rng.randf_range(0.5, 1.0) * (0.6 + 0.4 * v), "age": 0.0})


## 透明度 4 档台阶
static func _q4(a: float) -> float:
	return floorf(clampf(a, 0.0, 1.0) * 4.0) / 4.0


## 离船身 d 像素、光强 w、能照多远 reach：第几档（0..4）。最亮那档窄、越往外越宽，像光不像又包了一层壳
static func _level(w: float, d: int, reach: int) -> int:
	if d > reach or w <= 0.0:
		return 0
	var g := pow(1.0 - float(d - 1) / float(reach), FALLOFF)
	var lv := clampi(ceili(w * g * 4.0 - 0.2), 0, 4)
	if d == 1:
		lv = maxi(0, lv - GAP_DROP)
	return lv


## 第 b 段（0 = 轮廓左头 … NB - 1 = 右头）往推进器那头走了多少（0 机头 .. 1 推进器）
func _hot_f(b: int) -> float:
	var f := float(b) / float(NB - 1)
	return f if hot_side > 0.0 else 1.0 - f


func _draw() -> void:
	_drawn = false
	if strength <= 0.0 and _motes.is_empty():
		return
	_drawn = true
	var v := sqrt(clampf(strength, 0.0, 1.0)) * (1.0 + 0.07 * sin(_t * TAU / BREATH_SEC))
	var hs := _hs()
	var cin := INNER.lerp(HOT_INNER, hs)
	var cmid := MID.lerp(HOT_MID, hs)
	var cout := OUTER.lerp(HOT_OUTER, hs)
	if not _rings.is_empty() and v > 0.0:
		var rip := v > 0.7
		var p := fmod(_t, RIPPLE_SEC) / RIPPLE_SEC
		var rd := 3 + int(p * float(mini(R_MAX, roundi(RIPPLE_GO * reach_scale)) - 3))
		for b in NB:
			var hf := _hot_f(b)
			var w := v * lerpf(1.0, lerpf(HOT_W.x, HOT_W.y, hf), hs)
			var reach := mini(R_MAX, roundi(float(REACH) * reach_scale * lerpf(1.0, lerpf(HOT_R.x, HOT_R.y, hf), hs)))
			for d in range(1, reach + 1):
				var lv := _level(w, d, reach)
				if lv <= 0:
					continue
				var k := float(d - 1) / float(reach)
				var c := cin if k < 0.3 else (cmid if k < 0.6 else cout)
				c.a = float(lv) / 4.0 * max_alpha
				for r in _rings[b][d]:
					draw_rect(r, c)
			# 往外散的光纹：1 像素虚线，越远越淡；整圈一样
			if rip:
				var a := _q4(minf(w, 1.0) * (1.0 - p) * 0.9) * max_alpha
				if a > 0.0:
					_dash(_rings[b][rd], Color(cout, a))
	for m in _motes:
		var k := 1.0 - float(m["age"]) / float(m["life"])
		var a := _q4(k * (0.4 + 0.6 * v)) * max_alpha
		if a > 0.0:
			draw_rect(Rect2(((m["p"] as Vector2) + _origin).round(), Vector2.ONE), Color(cin, a))


## 一组长条画成 1 像素虚线（3 亮 2 空，慢慢流动）
func _dash(rects: Array, c: Color) -> void:
	var flow := int(_t * 20.0)
	for r: Rect2 in rects:
		var x0 := int(r.position.x)
		var y0 := int(r.position.y)
		for i in int(maxf(r.size.x, r.size.y)):
			var x := x0 + (i if r.size.x > 1.0 else 0)
			var y := y0 + (i if r.size.y > 1.0 else 0)
			if posmod(x + y + flow, 5) < 3:
				draw_rect(Rect2(x, y, 1, 1), c)
