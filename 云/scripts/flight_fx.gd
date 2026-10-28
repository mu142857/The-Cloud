extends Node2D
## 飞行段的小粒子：火花、油滴、火星（飞进引擎）、咳嗽的烟、掉出飞船的木头。
## 全部用整像素的小方块 / 小图画，屏幕坐标。世界里的粒子按世界时间走（决定卡时也慢下来），
## 火星（ember）按真实时间走，因为它是燃烧动画的一部分。

const PUFF_TEX := preload("res://art/flight/puff.png")
const WOOD_TEX := preload("res://art/flight/wood_chunk.png")

var parts: Array = []
var ship: Node2D            # 火星的目标（飞船尾巴）
var on_ember_arrive: Callable


func spark(p: Vector2, n: int, col := Color(1.0, 0.85, 0.5), speed := 40.0) -> void:
	for i in n:
		var a := randf() * TAU
		parts.append({"k": "spark", "p": p, "v": Vector2(cos(a), sin(a)) * randf_range(0.4, 1.0) * speed,
			"life": randf_range(0.25, 0.6), "age": 0.0, "c": col, "g": 30.0, "s": 1})


func oil(p: Vector2) -> void:
	parts.append({"k": "oil", "p": p + Vector2(randf_range(-3, 3), 0), "v": Vector2(randf_range(-12, -4), 10),
		"life": 2.2, "age": 0.0, "c": Color(0.16, 0.12, 0.1), "g": 140.0, "s": 1})


func puff(p: Vector2) -> void:
	parts.append({"k": "puff", "p": p, "v": Vector2(-30, randf_range(-8, -2)), "life": 0.9, "age": 0.0})


func wood(p: Vector2, v: Vector2) -> void:
	parts.append({"k": "wood", "p": p, "v": v, "life": 4.0, "age": 0.0, "g": 70.0, "flip": randf() < 0.5,
		"spin": randf_range(-1, 1)})


func ember(from: Vector2, delay: float, hot := true) -> void:
	## 火星：从 from 弯一道弧飞进飞船的尾巴。
	var mid: Vector2 = from.lerp(ship.global_position, 0.5) + Vector2(randf_range(-30, 30), randf_range(-60, -10))
	parts.append({"k": "ember", "a": from, "m": mid, "life": randf_range(0.7, 1.2), "age": -delay, "p": from,
		"c": Color(1.0, 0.8, 0.4) if hot else Color(1.0, 0.55, 0.25)})


func update(world_dt: float, real_dt: float) -> void:
	var keep: Array = []
	for q in parts:
		var dt: float = real_dt if q.k == "ember" else world_dt
		q.age += dt
		if q.age < 0.0:
			keep.append(q)
			continue
		if q.age >= q.life:
			if q.k == "ember" and on_ember_arrive.is_valid():
				on_ember_arrive.call()
			continue
		match q.k:
			"ember":
				var u: float = q.age / q.life
				u = u * u * (3.0 - 2.0 * u)
				var target: Vector2 = ship.tail_pos() if ship.has_method("tail_pos") else ship.global_position
				q.p = q.a.lerp(q.m, u).lerp(q.m.lerp(target, u), u)
			_:
				q.v.y += q.get("g", 0.0) * dt
				q.p += q.v * dt
		keep.append(q)
	parts = keep
	queue_redraw()


func _draw() -> void:
	for q in parts:
		if q.age < 0.0:
			continue
		var u: float = q.age / q.life
		var p: Vector2 = (q.p as Vector2).round()
		match q.k:
			"spark":
				var c: Color = q.c
				c.a = 1.0 - u
				draw_rect(Rect2(p, Vector2.ONE), c)
			"oil":
				draw_rect(Rect2(p, Vector2(1, 2)), Color(0.12, 0.1, 0.09, 1.0 - u * 0.5))
				draw_rect(Rect2(p + Vector2(0, -1), Vector2.ONE), Color(0.45, 0.3, 0.15, 1.0 - u))
			"puff":
				var f := mini(2, int(u * 3.0))
				draw_texture_rect_region(PUFF_TEX, Rect2(p - Vector2(3, 3), Vector2(7, 7)), Rect2(f * 7, 0, 7, 7),
					Color(1, 1, 1, 1.0 - u * 0.6))
			"wood":
				draw_set_transform(p, roundf(q.age * q.spin * 3.0 / (PI / 2)) * (PI / 2), Vector2(-1 if q.flip else 1, 1))
				draw_texture(WOOD_TEX, Vector2(-5, -2), Color(1, 1, 1, clampf((q.life - q.age) / 0.8, 0, 1)))
				draw_set_transform(Vector2.ZERO)
			"ember":
				var c2: Color = q.c
				c2.a = 1.0 - u * 0.4
				draw_rect(Rect2(p, Vector2.ONE * (2 if u < 0.5 else 1)), c2)
