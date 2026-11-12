extends Node2D
## 独立试玩，复用正式小游戏；进度只留在本场景，不发奖励、不写剧情 flag。
const DANCE := preload("res://scripts/rabbit_dance.gd")
const NPC := preload("res://scripts/npc_generic.gd")
const CHEN := preload("res://scenes/chen.tscn")

class DemoStory extends Node:
	var chen: Node2D
	var rabbit: Node2D
	var ended := false
	var ff := false
	var auto := ""
	var progress := {}

	func mech_load(_id: String) -> Dictionary:
		return progress.duplicate(true)

	func mech_save(_id: String, value: Dictionary) -> void:
		progress = value.duplicate(true)

	func npc(who: String) -> Node2D:
		return chen if who == "chen" else rabbit

	func txt(value: Dictionary) -> String:
		return str(value.get(I18n.lang, value.get("en", "")))

	func run_steps(steps: Array) -> String:
		for step in steps:
			if step.get("do") == "face":
				var actor := npc(str(step["who"]))
				var target := npc(str(step["to"]))
				actor._set_facing(1 if target.position.x > actor.position.x else -1)
		await get_tree().process_frame
		return ""

var story: DemoStory
var dance: RefCounted
var status: Label
var complete := false

func _ready() -> void:
	if not GameSettings.loaded:
		GameSettings.load_and_apply()
	story = DemoStory.new()
	add_child(story)
	story.chen = CHEN.instantiate()
	story.chen.position = Vector2(200, 218)
	story.chen.ground_fn = func(_x: float) -> float: return 218.0
	story.chen.input_enabled = false
	add_child(story.chen)
	story.rabbit = NPC.new()
	story.rabbit.setup("rabbit")
	story.rabbit.position = Vector2(280, 218)
	add_child(story.rabbit)
	var hud := CanvasLayer.new()
	hud.layer = 10
	add_child(hud)
	var help := Label.new()
	help.theme = UITheme.get_theme()
	help.text = story.txt({"zh": "兔子舞步   方向键 / WASD 模仿   R 重玩   Esc 返回标题", "en": "Rabbit dance   Arrows / WASD   R: retry   Esc: title", "fr": "Danse du lapin   Flèches / WASD   R : rejouer   Échap : titre"})
	help.position = Vector2(12, 12)
	help.add_theme_font_size_override("font_size", 12)
	hud.add_child(help)
	status = Label.new()
	status.theme = UITheme.get_theme()
	status.position = Vector2(12, 34)
	status.add_theme_font_size_override("font_size", 12)
	hud.add_child(status)
	_start.call_deferred()

func _draw() -> void:
	draw_rect(Rect2(0, 0, 480, 270), Color("182b2b"))
	draw_rect(Rect2(0, 218, 480, 52), Color("293b31"))
	draw_line(Vector2(0, 218), Vector2(480, 218), Color("637b59"), 1)

func _start() -> void:
	dance = DANCE.new()
	await dance.run(self, self, story, {"retry": true})     # 11-08：不再错三次自动过，好试「同一步错超过两次箭头重新给」
	complete = true
	story.chen.input_enabled = false

func _process(_delta: float) -> void:
	if dance == null or dance.s.is_empty():
		return
	var phase := story.txt({"zh": "轮到你模仿", "en": "Your turn", "fr": "À toi"}) if dance.listening else story.txt({"zh": "看兔子示范", "en": "Watch the rabbit", "fr": "Observe le lapin"})
	if complete:
		phase = story.txt({"zh": "完成！按 R 再玩一次", "en": "Complete! Press R to play again", "fr": "Terminé ! Appuie sur R pour rejouer"})
	var n: int = DANCE.SEQS.size()
	status.text = "%d / %d   %s" % [mini(int(dance.s["round"]) + 1, n), n, phase]

func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_R:
			get_viewport().set_input_as_handled()
			get_tree().reload_current_scene()
		elif event.keycode == KEY_ESCAPE:
			get_viewport().set_input_as_handled()
			get_tree().change_scene_to_file("res://scenes/main.tscn")
