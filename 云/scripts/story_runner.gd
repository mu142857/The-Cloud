extends Node
## 章节剧情引擎：读剧本 JSON（默认 data/story_forest.json，没有就退回 data/story_forest_sample.json），播 scene、管 hotspot、
## 自动玩、跳节拍、检查剧本。剧本格式和全部步骤见 docs/forest_chapter.md「剧本数据格式」。level_forest.gd 在 _ready 里建它。
##
## 拆成几块：
##   story_state.gd     flags / 日记 / 物件状态 / 用过的 hotspot（以后存档存这一份）
##   story_world.gd     markers、墙、物件（缺图色块）、树屋室内、雾
##   hotspots.gd        哪些点能用、提示箭头、晨身边 / 鼠标点到的那个
##   story_dialogue.gd  头顶对话框、旁白、拿到东西的提示、点选、结束卡
##   这里              一步一步播 scene（每步一个 await）、自动玩、跳节拍、统计、检查
##
## 播放：play(scene) 是协程，播完返回；goto / pick 跳到别的 scene（不回来）。剧情播放时锁晨、黑边按需（_wants_bars）。
## 引擎和剧本对接的点（剧本里有就用，没有就用关卡原来的）：
##   开场爬起来以后：hooks.crash，或第一个存在的 crash_wake / wake / crash / intro / opening
##   开场爬起来以后（真剧本：intro，设 crashed）
##   发光木头：保留关卡原来的拾取过场（走过去、弯腰、木头飞进背包、燃烧值滚动）。剧本里 at = wood 的 hotspot（wood / wood_last）
##     不单独出现，过场里播它的 scene（第一个能用的那个），scene 里的 anim pickup 和 give（已经给过的东西）跳过；引擎再设 got_wood。
##     没有这种 hotspot 就找 hooks.wood，或 wood_found / wood / wood_pickup / pickup_wood / glowing_wood
##   燃烧值刚到 launch_burn（设了 fuel_full）以后：hooks.fuel_full，或 fuel_full / fuel_ready
## 第二版步骤（设计文档末尾「补充步骤」）：hotspot 的 trigger:"enter" / range；walk / guide 的 wait:false、speed；
##   ambient（循环环境声，AudioStreamPlayer2D 放在 marker 上：音量随距离、左右声道随方位）；show_item；if（flag 可写 "!名字"）。
##   缺的音效文件静默跳过（STORY_CHECK 里列出来）。
## 放手让玩家走（作者的规矩）：鹿带路（guide）不锁晨——鹿跑到点停下回头等，这段剧情先停下（剩下的步骤记在 pending_guide），
##   晨可以往回走、捡东西、看东西、和别人说话；晨走到鹿 GUIDE_NEAR 以内（又没有别的剧情在播）就从停下的那一步接着播。
##   轻引导：main_target() = 现在主线下一个该去的地方（等人的鹿 / 会推进剧情的点 / 木头），level_forest.gd 在它出了屏幕时
##   在屏幕边上画一个很淡的小箭头；玩家 NUDGE_AFTER 秒没推进主线，晨小声自言自语一句：剧本里有 scene「nudge_<那个 hotspot id>」
##   （或 nudge_guide = 等鹿的时候）就说它的第一句台词（不锁人、几秒后自己消失），没有就不说。
## 补写台词：剧本里带 "added": true 的台词正文用柔和的蓝色（mark_added；debug 构建默认开，正式版默认关，F8 面板能开关）。
## 第三 / 四版：
##   hotspot 的 accepts：{"物品 id": scene, "_default": scene}：互动时背包里有它能接受的东西 → 弹出道具选择条（背包物品 +
##     「只是看看」）；选对的播对应 scene，选别的播 _default（没有就晨说一句「这个好像用不上。」），「只是看看」播 hotspot 的 scene。
##     背包里选中一件按「使用」= use_item：用在晨身边那个 hotspot 上（同样的规则；身边没有就「这附近用不上。」）。不扣任何东西。
##   {"do": "choice", "options": [{zh, en, scene}…]}：对话选项（晨的 2~3 个回答），选中的那句晨说出来，再跳到它的 scene（没写 scene 就接着播）。
##   {"do": "elephant_call", "variant": 1|2}：远处一排树冠依次轻晃（1 从左到右、2 从右到左）+ elephant_call_<n> + tree_sway
##     （左右声道跟着树冠从一侧推到另一侧）+ 镜头不声不响地停一下 + 晨抬头（看）。等树冠晃完再下一步。
##   journal 可带 "tag"（比如 elephant）；物品 desc_from_tag = 描述后面接上带这个 tag 的日记条目（大象的画）。
##   {"do": "journal_strike", "match": "文字"}：日记里含这段文字的条目划掉（背包日记里显示删除线）。
##   {"do": "journal_mark", "match": "文字"}：加下划线（后来再 journal_strike 的话删除线盖在上面）。journal / journal_strike
##     默认配 pen_write / pen_strike 音效（剧本自己写了 sfx 就听剧本的）。
##   {"do": "count", "flags": [..], "set": "名字", "at_least": n}：数这些 flag 设了几个，够 n 就设 set。
##   顶层 "hints"：玩家 NUDGE_AFTER 秒没推进主线，按 flag 挑一条让晨自言自语（不锁人）。认两种写法：
##     数组 [{"flag"?: f, "need"?: [..], "not"?: [..], "zh", "en"}…]（条件都满足的里面挑 flag 最近设的那条）；
##       条目也可以写 "lines": [{zh, en, added?}…]（三章现在都这么写）：每隔 NUDGE_EVERY 秒说下一句，说完为止；
##     字典 {"flag 名": {zh, en} 或 [{zh, en}…]}（挑最近设的、有提示的那个 flag）。没有 hints 再找 scene nudge_<hotspot id>。
##   坠毁后飞船里断续的警报 alarm_broken：引擎在 wreck 处放成 ambient，晨第一次修飞船（tried_parts）或捡到木头（got_wood）后淡掉。
## 第五版：
##   {"do": "drawing_closeup", "sec": n}：屏幕中间展开画的特写（art/forest_story/drawing_closeup.png，纸张展开、背景压暗），
##     停 n 秒，确认键 / 点击提前收起。缺图跳过。
##   {"do": "treeline_match"}：淡入树冠缺口那一屏（坠毁现场那排树冠的平面侧视、中间被撞出的弧形凹口；单独一屏，
##     不在森林的视差层里，见 story_world.gd 的 treeline_view_in）→ 停一下 → 画上的弧线（drawing_arc）放大 3 倍、
##     按端点对齐叠到凹口上（淡入、停、淡出；弧线跟着凹口那一层漂，任何一帧都对得上）→ 淡出回到森林。缺图跳过。
##   看树冠缺口的 hotspot（at = treeline_gap，或 hotspot 写 "view": "treeline"）：scene 开始前淡入同一屏（不叠弧线），
##     晨的台词在这一屏上说完再淡出回到森林（森林里抬头是看不到这道缺口的）。这一屏出来的时候所有对话框都放在
##     画面下方居中（TREELINE_VIEW_ANCHOR，不挡凹口），左上角目标 / 燃料和背包图标淡出（见 story_world.gd）。
##   顶层 "objectives"：[{need, not, zh, en, show_fuel}…] 取第一个满足条件的，当左上角的「当前目标」（level_forest.gd 画）。
## 不推人（作者的规矩）：走进 trigger:"enter" 的点触发的 scene 里，「晨 walk」一律不执行（不能用台词 + 自动走路把玩家推回去；
##   该停的地方由 story_world.gd 的「看得见的边」挡住）。--story_check 会把这种步骤列出来。
##   例外：hotspot 写了 "cutscene": true = 走到这里是玩家自己要去的终点、后面是一整段往前走的过场（flight1 回到驾驶座 →
##   改航线 → 走去转化装置），过场里晨的 walk 照常走（不是把人推回去）。
## 转场（10-29）：fade_to 可带 "leave": marker（边往那边走边黑，离开）、"cam": marker（换过去以后镜头停在那，晨从画面外走进来）、
##   "arrive": marker（淡入的同时晨从 at 走几步到这里停住：到达，不是一淡入就站在目标点上；只走一小段）、
##   "place": {人: marker}（换地方的同时把人放好，淡入后不凭空出现）；show / hide 可带 "fade": 秒（4 档透明度淡入淡出）；
##   {"do": "camera", "hold"/"at"/"release"}（见 _camera）。scene 播完自动放开镜头。
##   晨的 walk 可带 "pace": "walk"（走路的速度、缓起缓停；arrive 和区域入口的到达也是这个速度）。
##   过场一播完（玩家能动了），还没走到的 walk（wait:false）立刻松手：玩家任何时候都不会被推着走。
## 引擎扩展（设计文档之外、可选）：hotspot 的 at = NPC 名（跟着角色）；
##   show / hide 的 who 也可以是物件 id；pick 选项的 "correct": true；
##   flag 步骤的 "clear"；剧本顶层的 "items"（items.json 里没有的物品先用它顶上）、"hooks"。
##
## 调试参数（level_forest.gd 转过来）：
##   --story=<路径>          用哪份剧本（res:// 或绝对路径）
##   --story_auto            自动玩：对话每句停 0.6 秒自己下一句、自己走到下一个该去的 hotspot、点选时选对的那个，一直到结束卡，
##                           打印 STORY_DONE 和统计后退出。--story_auto=full：闲聊、选错的分支也都走一遍（看全部 scene）
##   --story_shots=<目录>    每播到一个新 scene 0.5 秒后存一张图（文件名带序号和 scene id）；另外对话选项、道具选择条
##                           出来以后、远处树冠晃到一半时也各存一张（ui_choice / ui_items / ui_elephant）
##   --beat=<flag>           直接跳到「设这个 flag 的那个 scene 播完」的样子（瞬间把前面的都过一遍：flags、物品、NPC 位置都对）
##   --story_check           只检查剧本（引用不到的 marker / scene / item、不支持的步骤……），打印 STORY_CHECK 后退出
## 第一关新版（11-02，docs/剧情改动/第一关新版_实现规格.md）：
##   {"do": "inner", "zh", "en", "style": "drift"|"fade"|"spin", "sec"?, "wait"?: true} / {"do": "inner", "clear": true}：潜意识字
##     （scripts/inner_voice.gd 的 say / clear；没有那个脚本就打印一行 INNER 接着播）。wait = 等 sec 秒再下一步。
##   {"do": "key_prompt", "zh", "en", "until": "run"|"bag"|"", "sec"?, "delay"?}：屏幕下方一行按键提示，不锁人；按住 Shift 跑起来 / 打开背包 / sec 秒后淡掉；
##     delay = 晚几秒再出（这期间已经做到了就不出）。
##   {"do": "fuel", "need_held": "unrelated", "plus": 100}：需要的量 = 现在的燃料 + 背包里这类（物品 fuel_kind）全部燃烧值 + plus。
##   {"do": "burn_held", "kind": "unrelated"} 或 "items": [id…]：飞行段一口气烧掉背包里有的这些（同一件写两次 = 烧两份），一次加燃料、一条提示，
##     每件设 burned_<id>；没有的跳过。--story_check 算燃料时当它们在纪念品二选一之前都烧了（第一关新版：无关的东西先烧，再逼着选私人物品）。
##   {"do": "blackout", "on": true/false}：闪回停在黑屏上时换成低一层的黑，好在黑里看纸、云星闪、潜意识字（_blackout_step）。
##   {"do": "reward", "item"? | "tex" + "region"?}：拾到好东西的奖励动画（东西升到晨头顶放大、一圈光点转一下），不进背包（进背包另写 give）。
##   {"do": "mechanic", ..., "wait": false}：不等小游戏播完（奔跑时的制作人员字幕）。
##   {"do": "camera", "zoom": 1.2, "sec": n, "wait"?}：镜头慢慢拉近 / 拉回（1 = 原样）；换房间时自动回到 1。
##   fade_to 加 "style": "pixel"：像素块溶解（八比特转场），不是平滑变黑。
##   choice 的选项可带 "need" / "not"（按亲情关系 c1_mom / c1_child 显示不同回答）。give：背包还没拿回来（剧本顶层 bag_lock）时，
##     东西不飞进背包，晨举一下（show_item）。
##   hotspot 的 scene 全是 bark 台词 = 只在那个点上方浮一句（"bark_y" 离地多高，默认 46），不停游戏、不锁人。
##   hotspot 写 "nolock": true = 走进去以后不锁人、不黑边，步骤边跑边播（只放 flag / inner / mechanic wait:false / camera wait:false 这类不等的）。
##   剧本顶层 "one_way": {"after", "until", "wall", "zh", "en"}：after 设了、until 没设时，旧路段左墙挪到 wall 那个 marker；
##     顶着往回走浮出潜意识字（每次间隔 ONE_WAY_EVERY 秒）。"item_views": [{"item", "need", "not", "scene"}]：背包里选中这件按「查看」播 scene
##     （自动玩 / 跳节拍：条件满足就直接播）。"bag_lock": {"from", "until"}：这期间背包按钮、Tab 都不出来。"hide_props": [物件…]：一开始就藏起来
##     （wood = 关卡的发光木头）。"retired": true 的 hotspot（旧流程）整个不加载。
## 母星闪回（11-02）：{"do": "flashback", "id", "place", "end", "lines", "fall", "hold"} / {"do": "flashback_wake", "wait"}，
##   玩法和参数见 scripts/flashback.gd 文件头；四次在哪、F8 怎么看见 docs/闪回_实现说明.md。
##   --fb_dev=N              和 --beat=（FLASHBACK_DEV 里那一行的 beat）一起：跳完节拍从第 N 次闪回前几步开始播（= F8「闪回 N」）
##   --fb_caught             自动玩到闪回时站着不动（走被追上那条路）；--fb_full 自动玩也按真实时长播闪回
##   --auto_to=<flag>        自动玩遇到点选时，优先选「走下去会设这个 flag」的那个（夜间测试：从森林连着玩到指定结局，如 final_ending_3）

const DEFAULT_STORY := "res://data/story_forest.json"
const SAMPLE_STORY := "res://data/story_forest_sample.json"
const SFX_DIR := "res://audio/sfx/"
const TREELINE_VIEW_ANCHOR := Vector2(240, 234)   # 树冠缺口那一屏里对话框的锚点：框底边落在 229（凹口两头最低 198，框在下面的树冠上），尖角不画
const STEPS := ["say", "narr", "walk", "face", "wait", "show", "hide", "give", "take", "flag", "journal", "sfx",
	"fade_to", "anim", "prop", "guide", "goto", "pick", "end_chapter", "if", "ambient", "show_item",
	"choice", "elephant_call", "journal_strike", "count", "journal_mark", "drawing_closeup", "treeline_match", "fuel", "camera",
	"mechanic", "todo_mechanic", "form", "follow", "water", "closeup",   # 后六个：多房间章节（docs/river_rooms_contract.md）
	"pose",   # pose：通用角色的图斜过来 / 挪一点 / 压到物件后面（_pose）
	"barter",   # barter：以物易物（scripts/barter.gd，剧本顶层 "barter" 表）
	"cycle",   # cycle：一次念一句，一直按一直往下念（_cycle_next，阿汀的河岸条例）
	"flashback", "flashback_wake",   # 母星闪回（scripts/flashback.gd）
	"inner", "key_prompt", "reward", "blackout", "burn_held",
	"music"]   # music：配乐（scripts/bgm.gd）。第一关新版（11-02）：潜意识字、按键提示、拾取奖励动画（见文件头「第一关新版」）
const COCKPIT_STEPS := {"debris_steer": "res://scripts/cockpit_debris.gd", "keepsake_choice": "res://scripts/cockpit_keepsake.gd",
	"cockpit_dash": "res://scripts/cockpit_dash.gd"}   # 驾驶舱（cockpit_dash：飞行一结尾往前一冲）
const COCKPIT_NAV := "res://scripts/cockpit_nav.gd"   # pick 带 "ui": "nav" / "action"：驾驶舱里的行动选择 + 二次确认（终章）
const HOOKS := {
	"crash": ["crash_wake", "wake", "crash", "intro", "opening"],
	"wood": ["wood_found", "wood", "wood_pickup", "pickup_wood", "glowing_wood"],
	"fuel_full": ["fuel_full", "fuel_ready"],
}
const ENGINE_FLAGS := ["crashed", "got_wood", "fuel_full"]
const NAME_COLORS := {"chen": Color("#c48fb4"), "deer": Color("#c9a882"), "miluo": Color("#d6c486"), "voice": Color("#8fa69a"),
	"niff": Color("#8ec9d6"), "ting": Color("#b8a58c"), "keeper": Color("#a89c8a"), "tape": Color("#8fa0a8"),
	"toucan": Color("#e8b04a"), "rat_chef": Color("#d6a882")}   # 以物易物的大嘴鸟（嘴的橙黄）、料理鼠妈（毛色）
const NPC_GD := preload("res://scripts/npc_generic.gd")         # 通用角色（妮芙、阿汀、摊主…；art/characters/<id>/<id>.json）
const CLOSEUP_GD := preload("res://scripts/closeup_ui.gd")      # 特写面板
const MECH_PREFIX := "mech."                                    # 小游戏进度存在 StoryState.props["mech.<id>"]
const FOLLOW_GAP := 34.0
const HEAD := {"chen": 50.0, "deer": 52.0, "miluo": 50.0}
const ANIM_MAP := {
	"chen": {"look": "idle_eye", "pickup": "pickup", "idle": "idle", "getup": "getup", "lie": "lie"},
	# 终章尾声的新动作（鹿 lean、弥洛 read / flip / check / screw）还没画，先指到已有的那段（占位，等美术组补画后改成真名）
	"deer": {"graze": "graze_down", "graze_down": "graze_down", "graze_up": "graze_up", "look": "look", "ear": "ear", "idle": "idle",
		"lean": "graze_down"},
	"miluo": {"idle": "idle", "read": "idle", "flip": "idle", "check": "idle", "screw": "idle"},
}
const GUIDE_NEAR := 60.0
const NUDGE_AFTER := 20.0
const NUDGE_EVERY := 40.0
const AUTO_LINE := 0.6
const WORLD_GD := preload("res://scripts/story_world.gd")
const HOTSPOTS_GD := preload("res://scripts/hotspots.gd")
const DIALOGUE_GD := preload("res://scripts/story_dialogue.gd")
const BARK_GD := preload("res://scripts/story_bark.gd")      # say 带 bark：晨头顶的小气泡（不锁人）
const QUICK_GD := preload("res://scripts/story_quick.gd")    # give 数组、走过去就捡（hotspot pickup）
const BARTER_GD := preload("res://scripts/barter.gd")         # 以物易物（大嘴鸟、料理鼠妈…）
const FLASHBACK_GD := preload("res://scripts/flashback.gd")   # 母星闪回（4 次）
const BGM_GD := preload("res://scripts/bgm.gd")          # 配乐（{"do": "music"}，scripts/bgm.gd）
const FLASHBACK_LAYER := 55                                     # 闪回那一层：盖在黑幕（Top 50）上面、F8 面板（60）下面
## F8 传送页的「闪回」按钮（dev_panel.gd）：重新载入那一章、跳节拍到 beat，再从 scene 里闪回那一步往前 back 步开始播
const FLASHBACK_DEV := [
	{"id": 1, "chapter": "forest", "beat": "c1_got_bag", "scene": "c1_drawing", "back": 1, "zh": "大象的画·追逐"},   # 第一关新版（11-02）
	{"id": 2, "chapter": "forest", "beat": "c1_got_wood", "scene": "c1_fix", "back": 99, "zh": "修好·全家福"},
	{"id": 3, "chapter": "river", "beat": "river_deer_msg", "scene": "home_wait_talk", "back": 4, "zh": "妮芙家"},
	{"id": 4, "chapter": "final", "beat": "final_fuel_done", "scene": "approach_page", "back": 99, "zh": "燃料柜"},
]
const DEV_FB_META := "the_cloud_dev_flashback"

var level: Node2D
var path := ""
var data := {}
var scenes := {}
var speakers := {}
var hotspot_defs: Array = []
var all_hotspot_defs: Array = []         # 连 retired 的旧点也在（自由探索找进出口用）
var world: Node2D
var hotspots: Node2D
var dlg: Control
var bark: Control                    # 头顶小气泡（story_bark.gd）
var quick: RefCounted                # story_quick.gd
var barter: RefCounted               # barter.gd
var cockpit_ui: Control              # 正在等玩家的驾驶舱步骤（避碎石 / 选纪念品；软锁检测用）
var flashback_ui: Control            # 闪回停在黑 / 白上、等 flashback_wake 的那一层（flashback.gd，hold）
var missing_anims := {}              # 剧本要、晨还没有的动作（MISSING_ANIM，给奥斯卡画）
const CHEN_ALIAS := "res://data/chen_anim_alias.json"
var _chen_alias = null                # chen_alias() 读进来的别名表
var entry_scene := ""                # 这一章的入口 scene（flight1 = start_flight1；关卡直接播，--story_check 不算「播不到」）
var chen: Node2D
var deer: Node2D
var miluo: Node2D

var busy := false
var free_walk := false             # guide：剧情没播完，但晨可以自己走
var auto := ""                     # "" / "main" / "full"
var ff := false                    # 跳节拍：每步瞬间完成
var free_roam := false             # F8「探索」（level_forest.gd 自由探索）：不播任何剧情、不触发 hotspot、不说卡关提示
var shots_dir := ""
var shot_delay := 0.5
var ended := false

# 统计
var played := {}
var played_order: Array[String] = []
var lines := 0
var hotspots_used := 0
var _scene_view := ""                # 下一个 play() 的 scene 在哪一屏上播（"treeline" = 树冠缺口那一屏；trigger 设，play 用完清掉）
var _t0_ms := 0
var _game_t := 0.0
var _cur_scene := ""
var _visited := {}                 # 自动玩：hotspot id → 来的时候的 StoryState.changed
var _visit_gain := {}              # 自动玩：hotspot id → 上次点它设了几个新 flag
var _wrong_tried := {}
var _target: Dictionary = {}
var _idle_t := 0.0
var _shot_n := 0
var _warned := {}
var _wood_mode := false             # 在关卡的木头拾取过场里播剧本：跳过 anim pickup、已经给过的 give
var _ambient := {}                   # "name@at" → AudioStreamPlayer2D
var _item_show: TextureRect          # show_item 举着的那件
var _item_show_until_say := false
var missing_sfx := {}
var _family: Array = []              # 正在响的音乐盒 / 留声机音效
var _sfx_t := {}                     # 音效名 → 上次放的时刻（毫秒）：下水转场不和剧本里刚放的入水声叠
var step_i := -1                     # 正在播的 scene 的第几步（开发者面板、卡死检测用）
var step_t := 0.0                    # 这一步播了多久
var _enter_scene := false            # 这段剧情是走进 trigger:"enter" 的点触发的（不许推晨走）
var pending_guide: Dictionary = {}   # 鹿带路停在半路的剧情：{scene, index, x}
var mark_added := OS.is_debug_build()  # 补写台词标蓝
var _nudge_t := 0.0
var _nudge_progress := -1
var _nudged := {}
var _target_t := 0.0
var _target_limit := 15.0
var _unreach := {}                   # 自动玩：走过去够不着的点（id → 当时的进展）；换一段就清掉
var speaking := ""                   # 正在说话的人（关卡用它判断前景层有没有挡住）
var _npc_room := {}                  # 角色在屋里还是屋外：节点名 → forest / treehouse
var npcs := {}                       # 通用角色：名字 → npc_generic.gd（剧本 show / walk / anim / face 里出现的、不是鹿 / 弥洛的）
var _npc_names := {}                 # 剧本里当角色用过的名字
var carry_flags: Array = []          # 前面章节可能设的 flag（chapter_flow 的 carry_flags；--story_check 不报「没有地方设」）
var follow := {}                     # 跟着晨走的：名字 → 间距
var closeup_ui: Control              # 特写面板（closeup_ui.gd）
var mech_node = null                 # 正在玩的那个小游戏（side_kit / river_kit 的面板在它的 board 上）：对话框躲面板用
var _mech_quit := false              # 刚才那个小游戏是退出来的（side_kit 的 quitted）
var mech_running := ""               # 正在玩的小游戏 id
var mech_wait := false               # 小游戏在等玩家互动（wait_interact）：只有临时点能用
var _mech_spots: Array = []
var _mech_hit: Dictionary = {}
signal mech_hit_sig


# ======================================================================= 读剧本
func load_story(p: String) -> void:
	path = p if p != "" else DEFAULT_STORY
	if not _exists(path):
		if p != "":
			push_warning("剧本不存在：%s，用小样" % path)
		path = SAMPLE_STORY
	var d = JSON.parse_string(FileAccess.get_file_as_string(path)) if _exists(path) else null
	if not d is Dictionary:
		push_error("剧本读不了（JSON 不对？）：" + path)
		if path != SAMPLE_STORY and _exists(SAMPLE_STORY):
			path = SAMPLE_STORY
			d = JSON.parse_string(FileAccess.get_file_as_string(path))
	data = d if d is Dictionary else {}
	if str(data.get("include", "")) != "":
		_merge_includes(str(data["include"]))
	scenes = data.get("scenes", {})
	speakers = data.get("speakers", {})
	all_hotspot_defs = data.get("hotspots", [])
	hotspot_defs = []
	for h in all_hotspot_defs:
		if not (h is Dictionary and h.get("retired", false)):
			hotspot_defs.append(h)          # "retired": true = 旧流程的点（第一关新版不再触发；scene 留着不删）
	for it in data.get("items", []):
		if it is Dictionary:
			Inventory.register_fallback(it)


## 剧本顶层 "include": "res://data/forest_side_"：同目录下文件名以它开头的 .json（第一关支线，按文件名顺序）合进来。
## 合并：speakers（主剧本优先）、markers / scenes / props（只加新的，重名记进 include_errors）、hotspots（标 _side = 文件名）、
## objectives（变成「（可选）」那一行：side_objectives）、hints / residents（追加）、items（register_fallback）、barter（同名覆盖）。
## 格式说明：共享笔记 forest-side-schema.md；--story_check 会把重名、坏 JSON 列出来。
var include_files: Array = []
var include_errors: Array = []


static func side_files(prefix: String) -> Array:
	var dir := prefix.get_base_dir()
	var head := prefix.get_file()
	var out: Array = []
	var da := DirAccess.open(dir)
	if da == null:
		return out
	for f in da.get_files():
		if f.begins_with(head) and f.ends_with(".json"):
			out.append(dir.path_join(f))
	out.sort()
	return out


func _merge_includes(prefix: String) -> void:
	data["side_objectives"] = []
	for f in side_files(prefix):
		var sd = JSON.parse_string(FileAccess.get_file_as_string(f))
		var fn := str(f).get_file()
		if not sd is Dictionary:
			include_errors.append("%s：JSON 读不了" % fn)
			continue
		include_files.append(fn)
		for k in ["speakers", "markers", "scenes", "barter", "props"]:
			if not data.has(k):
				data[k] = {}
			for key in sd.get(k, {}):
				if data[k].has(key) and k != "barter":
					if k != "speakers":
						include_errors.append("%s：%s 里的 %s 和已有的重名（没合进来）" % [fn, k, key])
					continue
				data[k][key] = sd[k][key]
		for h in sd.get("hotspots", []):
			if h is Dictionary:
				h["_side"] = fn
				data["hotspots"].append(h)
		for k2 in ["hints", "residents"]:
			if not data.has(k2):
				data[k2] = []
			data[k2].append_array(sd.get(k2, []))
		data["side_objectives"].append_array(sd.get("objectives", []))
		for it in sd.get("items", []):
			if it is Dictionary:
				if Inventory.defined(str(it.get("id", ""))) and not Inventory.item(str(it["id"])).has("_side"):
					include_errors.append("%s：物品 %s 和 items.json 重名" % [fn, it.get("id")])
					continue
				it["_side"] = fn
				Inventory.register_fallback(it)


## 跳节拍的目标是支线的 flag（有支线点通得到它）：支线点全都可以去（送还三件：先在树屋拿、再送过去，两步）
var _side_target_cache := {}


func _side_target() -> bool:
	if _ff_target == "":
		return false
	if not _side_target_cache.has(_ff_target):
		var yes := false
		for h in hotspot_defs:
			if h is Dictionary and h.has("_side") and _leads_to(str(h.get("scene", "")), _ff_target):
				yes = true
				break
		_side_target_cache[_ff_target] = yes
	return bool(_side_target_cache[_ff_target])


## 自动玩去不去支线点：默认去，而且先做支线再走主线（F8 节拍「支线·…」接着玩才走得到）；--main_only = 只走主线
func side_auto() -> bool:
	return auto != "" and not "--main_only" in OS.get_cmdline_user_args()


## 「（可选）」那一行：支线文件 objectives 里现在满足条件的（Array of {zh, en}）
func side_objectives(include_completed := false) -> Array:
	var out: Array = []
	for o in data.get("side_objectives", []):
		if o is Dictionary and StoryState.all_of(o.get("need", [])):
			var done := not StoryState.none_of(o.get("not", []))
			if include_completed or not done:
				var entry: Dictionary = o.duplicate()
				entry["completed"] = done
				out.append(entry)
	return out


static func _exists(p: String) -> bool:
	return FileAccess.file_exists(p)


func setup(lv: Node2D, ui_root: Control) -> void:
	level = lv
	chen = lv.chen
	deer = lv.get_node("Deer")
	miluo = lv.get_node("Snake")
	_t0_ms = Time.get_ticks_msec()
	world = WORLD_GD.new()
	world.name = "StoryWorld"
	lv.add_child(world)
	var shown: Array = []
	for sid in scenes:
		for st in scenes[sid]:
			if st is Dictionary and str(st.get("do", "")) == "prop" and str(st.get("state", "")) == "shown":
				shown.append(str(st.get("id", "")))
	world.setup(lv, data.get("markers", {}), _steam_pipe(), shown)
	if data.get("props", {}) is Dictionary:
		world.add_props(data.get("props", {}))      # 支线文件带来的物件（story_world.add_props）
	if "cockpit" in data.get("rooms", []):
		world.add_cockpit()                # 驾驶舱（cockpit_room.gd）
	_collect_npc_names()
	if _multi_room():
		_setup_stages()
	hotspots = HOTSPOTS_GD.new()
	hotspots.name = "Hotspots"
	lv.add_child(hotspots)
	lv.move_child(hotspots, chen.get_index() + 1)
	dlg = DIALOGUE_GD.new()
	dlg.name = "StoryDialogue"
	dlg.avoid = people_screen_rects
	dlg.chooser_rect = chen_screen_rect
	dlg.panel_rect = mech_panel_rect
	ui_root.add_child(dlg)
	hotspots.setup(self, world, hotspot_defs, ui_root)
	bark = BARK_GD.new()
	bark.name = "StoryBark"
	bark.story = self
	ui_root.add_child(bark)
	ui_root.move_child(bark, dlg.get_index())
	quick = QUICK_GD.new(self)
	barter = BARTER_GD.new(self)
	closeup_ui = CLOSEUP_GD.new()
	closeup_ui.name = "Closeup"
	closeup_ui.story = self
	ui_root.add_child(closeup_ui)
	ui_root.move_child(closeup_ui, dlg.get_index())
	# 角色的起始位置：鹿藏着（启动失败那一幕才出来），弥洛在树屋里
	deer.visible = false
	_place(miluo, world.mx("room_miluo"), "treehouse")
	miluo.visible = true
	_npc_room[deer.name] = "forest"
	var tm := Inventory.item("travel_map")
	if not tm.is_empty() and not tm.has("desc_from_tag"):
		tm["desc_from_tag"] = "on_travel_map"     # 日记烧掉以后写在航图背面的（_journal_holder）；航图是第一章的物品（items.json）
	_place_residents(world.room)            # 剧本顶层 residents（森林空地尽头的大嘴鸟）
	_burst_args()
	world.one_way = data.get("one_way", {}) if data.get("one_way", {}) is Dictionary else {}
	for pid in data.get("hide_props", []):
		if str(pid) != "wood":
			world.set_prop(str(pid), "hidden", false)      # 第一关新版：开场行李、三样材料都不在了（wood 由关卡藏）


## 管道那个点选里「对的」那段（细白汽冒在它上面）
func _steam_pipe() -> String:
	for id in scenes:
		for st in scenes[id]:
			if st is Dictionary and str(st.get("do", "")) == "pick":
				var opts: Array = st.get("options", [])
				var ok := _correct_index(st, str(id))
				if ok >= 0 and str(opts[ok].get("id", "")).begins_with("pipe"):
					return str(opts[ok]["id"])
	return ""


func has_scene(id: String) -> bool:
	return scenes.has(id)


func hook(kind: String) -> String:
	if kind == "wood":
		var wh := _wood_hotspot()
		if not wh.is_empty():
			return str(wh.get("scene", ""))
	var h: Dictionary = data.get("hooks", {})
	if h.has(kind) and scenes.has(str(h[kind])):
		return str(h[kind])
	for c in HOOKS.get(kind, []):
		if scenes.has(c):
			return c
	return ""


## 剧本里放在发光木头上的 hotspot（第一个条件满足的）
func _wood_hotspot() -> Dictionary:
	for h in hotspot_defs:
		if h is Dictionary and str(h.get("at", "")) == "wood" and scenes.has(str(h.get("scene", ""))):
			if StoryState.all_of(h.get("need", [])) and StoryState.none_of(h.get("not", [])):
				return h
	for h in hotspot_defs:
		if h is Dictionary and str(h.get("at", "")) == "wood" and scenes.has(str(h.get("scene", ""))):
			return h
	return {}


## 关卡自己管的点：木头还在地上时，at = wood 的 hotspot 交给拾取过场
func hotspot_blocked(h: Dictionary) -> bool:
	if mech_wait != h.has("_mech"):
		return true                        # 小游戏等互动时只有它的临时点；平时临时点不出现
	return str(h.get("at", "")) == "wood" and level.wood_available()


## 木头拾取过场里播剧本
func play_wood(id: String) -> void:
	_wood_mode = true
	var wh := _wood_hotspot()
	if not wh.is_empty():
		StoryState.mark_used(str(wh.get("id", "")))
		hotspots_used += 1
	await play(id, false)
	_wood_mode = false


func npc(who: String) -> Node2D:
	match who:
		"chen":
			return chen
		"deer":
			return deer
		"miluo", "milo", "snake":
			return miluo
	return _generic(who)


## 文字：当前语言，空的就回落中文
func txt(d) -> String:
	return str(txt_lang(d)[0])


## 文字和它实际用的是哪种语言：[文字, "zh"/"en"]（台词回落到中文时，说话人名字也跟着用中文）
func txt_lang(d) -> Array:
	if d is Dictionary:
		var s := str(d.get(I18n.lang, ""))
		if s != "":
			return [s, I18n.lang]
		s = str(d.get("zh", ""))
		if s != "":
			return [s, "zh"]
		return [str(d.get("en", "")), "en"]
	if d == null:
		return ["", I18n.lang]
	return [str(d), I18n.lang]


## 名字取指定语言，那种语言没写就退回 txt
func txt_in(d, lang: String) -> String:
	if d is Dictionary and str(d.get(lang, "")) != "":
		return str(d[lang])
	return txt(d)


func _warn_once(msg: String) -> void:
	if _warned.has(msg):
		return
	_warned[msg] = true
	push_warning("剧本：" + msg)


# ======================================================================= 播
func play(id: String, manage := true, from_index := 0) -> void:
	if free_roam:
		return
	if busy:
		_warn_once("已经在播，忽略 " + id)
		return
	busy = true
	hotspots.active = false
	if not is_nan(_bark_at):
		_bark_at = NAN                         # 飞船上方那句还没散：剧情开始了就收掉
		bark.clear()
	if manage and not ff:
		level.story_begin(_wants_bars(id))
		dlg.top_limit = level.BAR_H + 4.0 if level.bars_on() else 4.0
		await _settle_start()                  # 晨站在别人身上 / 跟着的人压在晨身上：先让开
	var view: bool = _scene_view == "treeline" and manage and not ff and world.has_treeline_view()
	_scene_view = ""
	if view:
		await world.treeline_view_in(0.7 if auto == "" else 0.3)
		_ui_shot("treeline", 0.3)
	var cur := id
	var hops := 0
	var fuel_before := StoryState.has("fuel_full")
	while cur != "" and hops < 200 and not ended:
		hops += 1
		if not scenes.has(cur):
			_warn_once("没有这个 scene：" + cur)
			break
		_on_scene(cur)
		var next := ""
		step_i = -1
		var steps: Array = scenes[cur]
		var start := from_index
		from_index = 0
		for si in range(start, steps.size()):
			var st = steps[si]
			step_i = si
			step_t = 0.0
			if not st is Dictionary:
				continue
			var t_step := _game_t
			var g: String = await _step(st)
			if not is_inside_tree():
				return
			if not ff:
				_count_wait(cur, st, _game_t - t_step)
			if ended:
				break
			if g == "__pause__":
				# 鹿带路：这段先停，剩下的等晨走到鹿身边再接着播（见 resume_guide）
				pending_guide["scene"] = cur
				pending_guide["index"] = si + 1
				break
			if g != "":
				next = g
				break
		if ff and ff_stop and _ff_target != "" and StoryState.has(_ff_target) and next != "":
			ff_resume = next                 # 跳节拍（别的章节）：设目标 flag 的 scene 播完就停，后面的由关卡正常播
			break
		cur = next
	if flashback_ui != null and not ended:
		await _flashback_wake()              # 剧本 hold 了却没写 flashback_wake：播完这段自己醒，别停在黑屏上
	dlg.close_box()
	if view:
		await world.treeline_view_out(0.7 if auto == "" else 0.3)
	free_walk = false
	step_i = -1
	if manage and not ff and not ended:
		level.story_end()
	busy = false
	hotspots.active = true
	if not ended and not fuel_before:
		await check_fuel_hook()


## 燃烧值刚到 200：剧本里有 fuel_full 场景就接着播
func check_fuel_hook() -> void:
	if not StoryState.has("fuel_full") or busy:
		return
	var h := hook("fuel_full")
	if h != "" and not played.has(h):
		await play(h)


## 连拍（11-04 作者「妮芙简直是 bug 之王」：要看清每一帧）：--burst_shots=目录 --burst=scene1,scene2,… [--burst_sec=6]
## 这些 scene 一开始，每 BURST_DT 秒（游戏时间）存一张图到 目录/<scene>_<第几次>/f000.png，连 burst_sec 秒（后面接着播的 scene 也拍进去）；
## 每张同时打印一行 BURST：晨、妮芙、阿汀的位置 / 透明度 / 看不看得见 / 画在第几层、黑幕多黑。要开窗口（带 shot 的参数 gt.sh 才放行）。
const BURST_DT := 0.1
var _burst_dir := ""
var _burst_ids := {}
var _burst_sec := 6.0
var _burst_until := -1.0
var _burst_next := 0.0
var _burst_tag := ""
var _burst_n := 0
var _burst_count := {}


func _burst_args() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--burst_shots="):
			_burst_dir = a.trim_prefix("--burst_shots=")
		elif a.begins_with("--burst="):
			for sid in a.trim_prefix("--burst=").split(","):
				var kv := sid.strip_edges().split(":")         # scene:秒 = 这一段拍多久（默认 burst_sec）
				_burst_ids[kv[0]] = float(kv[1]) if kv.size() > 1 else -1.0
		elif a.begins_with("--burst_sec="):
			_burst_sec = float(a.trim_prefix("--burst_sec="))


func _burst_start(id: String) -> void:
	if _game_t < _burst_until:
		_burst_until = _game_t + _burst_sec       # 还在拍上一段：接着拍
		return
	_burst_count[id] = int(_burst_count.get(id, 0)) + 1
	_burst_tag = "%s_%d" % [id, _burst_count[id]]
	DirAccess.make_dir_recursive_absolute(_burst_dir.path_join(_burst_tag))
	var sec := float(_burst_ids.get(id, -1.0))
	_burst_until = _game_t + (sec if sec > 0.0 else _burst_sec)
	_burst_next = _game_t
	_burst_n = 0


func _burst_tick() -> void:
	if _burst_until < 0.0 or _game_t > _burst_until or _game_t < _burst_next:
		return
	_burst_next = _game_t + BURST_DT
	var path := _burst_dir.path_join(_burst_tag).path_join("f%03d.png" % _burst_n)
	RenderingServer.force_draw(false)
	var img := get_viewport().get_texture().get_image()
	if img.get_width() != 480:
		img.resize(480, 270, Image.INTERPOLATE_NEAREST)     # 视网膜窗口拍出来 3000 宽：缩回游戏的 480×270（一张几十 KB）
	img.save_png(path)
	var parts: Array = ["chen=(%d,%d)" % [int(chen.position.x), int(chen.position.y)]]
	for who in ["niff", "ting"]:
		var n = npcs.get(who, null)
		if n != null and is_instance_valid(n):
			parts.append("%s=(%d,%d) a=%.2f vis=%s z=%d idx=%d room=%s" % [who, int(n.position.x), int(n.position.y), n.modulate.a,
				str(n.is_visible_in_tree()), n.z_index, n.get_index(), _room_of(n)])
	print("BURST %s f%03d t=%.2f scene=%s step=%d room=%s fade=%.2f %s" % [_burst_tag, _burst_n, _game_t, _cur_scene, step_i, world.room,
		level.fade.color.a, " ".join(parts)])
	_burst_n += 1


func _on_scene(id: String) -> void:
	_cur_scene = id
	var first := not played.has(id)
	played[id] = int(played.get(id, 0)) + 1
	played_order.append(id)
	if ff:
		return
	if auto != "":
		print("STORY_SCENE %s  t=%.1f" % [id, _game_t])
	if _qa_live and npcs.has("niff"):
		var nf: Node2D = npcs["niff"]
		var nsg := _lv_stage()
		print("NIFF_AT %s niff=(%d,%d) a=%.2f vis=%s room=%s lv=%s | chen=(%d,%d) room=%s lv=%s follow=%s" % [id, int(nf.position.x), int(nf.position.y),
			nf.modulate.a, str(nf.is_visible_in_tree()), _room_of(nf), str(_lv_of(nf, nsg)) if nsg != null else "-", int(chen.position.x), int(chen.position.y),
			world.room, str(nsg.chen_lv) if nsg != null else "-", str(follow.has("niff"))])
	if first and shots_dir != "":
		_shot(id)
	if _burst_dir != "" and (_burst_ids.has(id) or _burst_ids.has("*")):
		_burst_start(id)


## 界面出来的时候也存一张（对话选项、道具选择条、树冠晃动）
func _ui_shot(kind: String, delay: float) -> void:
	if shots_dir == "" or ff:
		return
	_shot_n += 1
	var n := _shot_n
	await get_tree().create_timer(delay, false).timeout
	level._save(shots_dir.path_join("%03d_ui_%s_%s.png" % [n, kind, _cur_scene.validate_filename()]))


func _shot(id: String) -> void:
	_shot_n += 1
	var n := _shot_n
	await get_tree().create_timer(shot_delay, false).timeout
	level._save(shots_dir.path_join("%03d_%s.png" % [n, id.validate_filename()]))


func _wants_bars(id: String) -> bool:
	var says := 0
	for st in scenes.get(id, []):
		if not st is Dictionary:
			continue
		if st.has("say"):
			says += 1
		if str(st.get("do", "")) in ["walk", "guide", "fade_to", "anim", "show", "pick", "end_chapter"]:
			return true
	return says >= 4


## {"do": "cycle", "id": 计数名, "lines": [步骤…]}：每播一次走 lines 的下一步，走完从头来（11-05 作者：河岸条例要像佐特的戒律）。
## 计数存在 StoryState.props（跟着存档、换章走）。一轮结束时要说的话就写在 lines 最后一条。跳节拍时不算念过
func _cycle_next(st: Dictionary) -> Dictionary:
	var list: Array = st.get("lines", [])
	var id := str(st.get("id", ""))
	if ff or list.is_empty() or id == "":
		return {}
	var n := int(str(StoryState.props.get(id, "0")))
	StoryState.set_prop(id, str(n + 1))
	return list[n % list.size()]


## --cycle_test=次数（配 --chapter=river --story_check）：不开画面，按真的 hotspot 优先级把阿汀点这么多次，打印每次念了什么
func cycle_test(clicks: int) -> void:
	StoryState.set_flag("river_landed")
	for i in clicks:
		var picked := {}
		for h in hotspots.defs:
			if str(h.get("at", "")) == "ting" and str(h.get("room", "")) == "river_bank" and hotspots.usable(h):
				picked = h
				break
		if picked.is_empty():
			print("CYCLE_TEST %d 没有能点的" % (i + 1))
			continue
		if picked.get("once", false):
			StoryState.mark_used(str(picked.get("id", "")))
		for st in scenes.get(str(picked.get("scene", "")), []):
			var line: Dictionary = st
			if str(st.get("do", "")) == "cycle":
				line = _cycle_next(st)
			if line.has("say"):
				print("CYCLE_TEST %d %s：%s" % [i + 1, str(picked.get("id", "")), str(line.get("zh", ""))])
	print("CYCLE_TEST done n=%s" % str(StoryState.props.get("ting_rule_n", "0")))


## 一步。返回下一个 scene（goto / pick），"" = 接着播这个 scene
func _step(st: Dictionary) -> String:
	if st.has("say"):
		await _say(st)
		return ""
	if st.has("narr"):
		await _narr(st)
		return ""
	var d := str(st.get("do", ""))
	if _overlap_log and not ff and d in ["walk", "show", "fade_to"]:
		print("STEP %s:%d %s → %s | %s" % [_cur_scene, step_i, d, str(st.get("to", st.get("at", ""))), _bodies_str()])
	match d:
		"walk":
			await _walk(st)
		"face":
			_face(st)
		"wait":
			if not ff:
				await _wait(maxf(float(st.get("sec", 0.5)) * WAIT_SCALE, 0.3))
		"show":
			await _show(st, true)
		"hide":
			await _show(st, false)
		"give":
			if st.has("items"):
				await quick.give_many(st)
			else:
				await _give(str(st.get("item", "")))
		"take":
			_take(str(st.get("item", "")))
		"flag":
			if st.has("set"):
				StoryState.set_flag(str(st["set"]))
			if st.has("clear"):
				StoryState.clear_flag(str(st["clear"]))
		"journal":
			_journal(st)
		"sfx":
			_sfx(st)
		"fade_to":
			await _fade_to(st)
		"anim":
			_anim(st)
		"prop":
			if st.has("glide"):
				await _prop_glide(st)
			else:
				world.set_prop(str(st.get("id", "")), str(st.get("state", "")))
				if st.has("fade") and not ff:
					_prop_fade_in(str(st.get("id", "")), float(st["fade"]))
		"guide":
			await _guide(st)
			if not pending_guide.is_empty() and not pending_guide.has("scene"):
				return "__pause__"
		"goto":
			return str(st.get("scene", ""))
		"pick":
			var s: String = await _pick(st)
			return s
		"end_chapter":
			await _end_chapter()
		"if":
			var f := str(st.get("flag", ""))
			var yes := not StoryState.has(f.substr(1)) if f.begins_with("!") else StoryState.has(f)
			var to := str(st.get("then" if yes else "else", ""))
			if to == "":
				return ""
			if _falls_through(to):
				# 分支 scene 播完没有跳走（没有 goto / 点选 / 结束）：播完回来接着播 if 后面的步骤（flight1 记日记那种写法）
				var outer := _cur_scene
				_on_scene(to)
				for st2 in scenes[to]:
					if not st2 is Dictionary:
						continue
					var g2: String = await _step(st2)
					if ended or g2 != "":
						return g2
				_cur_scene = outer
				return ""
			return to
		"ambient":
			_ambient_step(st)
		"show_item":
			_show_item(st)
		"choice":
			var cs: String = await _choice(st)
			return cs
		"cycle":
			var cn := _cycle_next(st)
			if not cn.is_empty():
				return await _step(cn)
		"mechanic":
			await _mechanic(st)
			if _mech_quit:                       # 玩家退出了（Esc / ×）：不接着往下播，跳去 quit_scene
				_mech_quit = false
				return str(st.get("quit_scene", ""))
		"todo_mechanic":
			_warn_once("todo_mechanic %s：小游戏还没接上，跳过" % st.get("id", ""))
		"form":
			var fn := npc(str(st.get("who", "")))
			if fn != null and fn.has_method("set_form"):
				fn.set_form(str(st.get("form", "land")))
		"pose":
			await _pose(st)
		"follow":
			var who_f := str(st.get("who", ""))
			if st.get("on", true):
				follow[who_f] = float(st.get("gap", FOLLOW_GAP))
			else:
				follow.erase(who_f)
			var nf_ := npc(who_f)
			if nf_ != null and st.has("vmax"):
				if float(st["vmax"]) > 0.0:
					nf_.set_meta("follow_vmax", float(st["vmax"]))
				elif nf_.has_meta("follow_vmax"):
					nf_.remove_meta("follow_vmax")
		"water":
			var ws: Node2D = world.stage(str(st.get("room", world.room)))
			if ws != null:
				var wsec := 0.0 if ff else float(st.get("sec", 1.5))
				if st.get("wait", true) and wsec > 0.0:
					await ws.set_water(float(st.get("y", ws.water_y())), wsec)
				else:
					ws.set_water(float(st.get("y", ws.water_y())), wsec)
		"closeup":
			var zr: String = await closeup(st)
			for z in st.get("zones", []):
				if str(z.get("id", "")) == zr and str(z.get("scene", "")) != "":
					return str(z["scene"])
		"elephant_call":
			await _elephant_call(st)
		"drawing_closeup":
			if not ff:
				var tp := "res://art/forest_story/drawing_closeup.png"
				if ResourceLoader.exists(tp):
					var sec := float(st.get("sec", 2.5))
					if auto != "":
						sec = minf(sec, 1.2)
					_ui_shot("closeup", 0.75)
					await dlg.closeup(load(tp), sec)
		"treeline_match":
			if not ff:
				await _treeline_match()
		"journal_mark":
			var mm := str(st.get("match", ""))
			if StoryState.mark(mm) == 0:
				_warn_once("journal_mark：日记里没有含「%s」的条目" % mm)
			if not ff and not st.has("sfx"):
				_sfx({"name": "pen_write", "db": -8.0})
		"journal_strike":
			var m := str(st.get("match", ""))
			if StoryState.strike(m) == 0:
				_warn_once("journal_strike：日记里没有含「%s」的条目" % m)
			if not ff:
				if not st.has("sfx"):
					_sfx({"name": "pen_strike", "db": -4.0})
				var jh := _journal_holder()
				dlg.toast(Inventory.icon(jh), I18n.t("journal_struck" if jh == "journal" else "paper_struck"))
		"count":
			var c := 0
			for f in st.get("flags", []):
				if StoryState.has(str(f)):
					c += 1
			if c >= int(st.get("at_least", 1)) and st.has("set"):
				StoryState.set_flag(str(st["set"]))
		"fuel":
			if level.chapter == "flight1" and st.has("burn") and not ff:
				await _burn_closeup(str(st["burn"]))
			_fuel_step(st)
		"camera":
			await _camera(st)
		"debris_steer", "keepsake_choice", "cockpit_dash":
			var cs2: String = await _cockpit_step(d, st)     # 驾驶舱的两个小玩法（cockpit_debris.gd / cockpit_keepsake.gd）
			return cs2
		"barter":
			var bs: String = await barter.run(st)
			return bs
		"music":
			if not ff:
				var bgm = BGM_GD.get_bgm(level.get_tree())
				if st.get("stop", false):
					bgm.stop(float(st.get("fade", 1.5)))
				else:
					bgm.play(str(st.get("track", "")), float(st.get("db", NAN)), float(st.get("fade", 1.5)), int(st.get("loop", -1)), str(st.get("then", "")))
		"flashback":
			await _flashback(st)
		"flashback_wake":
			if st.get("wait", true):
				await _flashback_wake()
			else:
				_flashback_wake()
		"inner":
			await _inner(st)
		"blackout":
			_blackout_step(bool(st.get("on", true)))
		"burn_held":
			await _burn_held(st)
		"key_prompt":
			if not ff and not free_roam:
				level.key_prompt(txt(st), str(st.get("until", "")), float(st.get("sec", 14.0)), float(st.get("delay", 0.0)))
		"reward":
			await _reward(st)
		_:
			_warn_once("不认识的步骤：" + JSON.stringify(st))
	return ""


## 飞行段燃料表（左上角「现在 / 需要」，StoryState.fuel / fuel_need）：
##   {"do": "fuel", "have": 200, "need": 200}  设两个数（起飞时满的）；{"do": "fuel", "need": 255}  只改需要的量（改航线）
##   {"do": "fuel", "burn": "blue_stone"}  加这件东西的 keepsake_burn（没有就用 burn）；{"do": "fuel", "add": n} / "sub": n
##   燃料最多到「需要的量」（放进去的比缺口多，表也只到满）。纪念品卡片上不标燃料值，差多少只看这张表。
func _fuel_step(st: Dictionary) -> void:
	var was := StoryState.fuel()
	var need_was := StoryState.fuel_need()
	var have := was
	var need := -1
	if st.has("need"):
		need = int(st["need"])
	if st.has("need_held"):
		# 按背包里实际有的算（第一关支线）：需要 = 现在的燃料 + 这一类（unrelated）全部的燃烧值 + plus
		# → 无关的先烧完还差 plus，最后一定得烧一件私人物品
		need = was + held_fuel(str(st["need_held"])) + int(st.get("plus", 100))
		print("FUEL need_held %s: have=%d held=%d need=%d" % [st["need_held"], was, held_fuel(str(st["need_held"])), need])
	if st.has("have"):
		have = int(st["have"])
	if st.has("burn"):
		have += fuel_of(str(st["burn"]))
	have += int(st.get("add", 0)) - int(st.get("sub", 0))
	if need < 0 and not StoryState.fuel_on():
		need = maxi(have, 0)
	StoryState.set_fuel(have, need)
	level.fuel_changed(was, need_was)


## 背包里某一类（物品的 fuel_kind）全部加起来的燃烧值（同一件有两份算两份）
static func held_fuel(kind: String) -> int:
	var t := 0
	for id in Inventory.owned:
		if str(Inventory.item(id).get("fuel_kind", "")) == kind:
			t += fuel_of(id)
	return t


## 一件东西放进转化装置给多少燃料（纪念品 keepsake_burn，材料 burn）
static func fuel_of(id: String) -> int:
	var it := Inventory.item(id)
	return int(it.get("keepsake_burn", it.get("burn", 0)))


## 母星闪回（flashback.gd）：自己一层 CanvasLayer（FLASHBACK_LAYER），等它播完；hold 的留着，等 flashback_wake 睁眼
func _flashback(st: Dictionary) -> void:
	if ff or free_roam:
		return
	if flashback_ui != null:
		await _flashback_wake()              # 上一次停着没醒的先醒
	BGM_GD.get_bgm(level.get_tree()).suspend(0.3)     # 配乐跟着压黑很快淡掉（0.3 秒，闪回进场像关门；黑里紧张的循环 + 心跳起来），醒来接回来
	var layer := CanvasLayer.new()
	layer.name = "Flashback"
	layer.layer = FLASHBACK_LAYER
	level.add_child(layer)
	var n: Control = FLASHBACK_GD.new()
	layer.add_child(n)
	dlg.close_box()
	_enter_scene = false                     # 闪回以后晨醒在别处：不再是「走到边上触发」的那一刻，后面的 walk 照常走（不推人的规矩管不到）
	cockpit_ui = n                           # 软锁检测：这期间是在等玩家的界面
	await n.play(self, st)
	cockpit_ui = null
	if is_instance_valid(n) and bool(st.get("hold", false)):
		flashback_ui = n


func _flashback_wake() -> void:
	var n := flashback_ui
	flashback_ui = null
	if n != null and is_instance_valid(n):
		await n.wake()
	if not ff:
		BGM_GD.get_bgm(level.get_tree()).resume()


## F8「闪回」按钮跳过来的：节拍跳完以后从闪回前几步开始播（level_forest.gd 的 _ff_done 拿走）；没有 = {}
func dev_flashback_take() -> Dictionary:
	if not Engine.has_meta(DEV_FB_META):
		# 命令行 --fb_dev=N（和 --beat= 一起，headless 测试用；只第一次）：和点 F8 的「闪回 N」一样
		for a in OS.get_cmdline_user_args():
			if a.begins_with("--fb_dev=") and not Engine.has_meta(DEV_FB_META + "_cli"):
				Engine.set_meta(DEV_FB_META + "_cli", true)
				for d in FLASHBACK_DEV:
					if int(d["id"]) == int(a.trim_prefix("--fb_dev=")):
						Engine.set_meta(DEV_FB_META, d)
	if not Engine.has_meta(DEV_FB_META):
		return {}
	var d = Engine.get_meta(DEV_FB_META)
	Engine.remove_meta(DEV_FB_META)
	if not d is Dictionary or not scenes.has(str(d.get("scene", ""))):
		return {}
	var steps: Array = scenes[str(d["scene"])]
	var at := 0
	for i in steps.size():
		if steps[i] is Dictionary and str(steps[i].get("do", "")) == "flashback":
			at = i
			break
	return {"scene": str(d["scene"]), "index": maxi(0, at - int(d.get("back", 0)))}


## 驾驶舱步骤：建那个界面（挂在对话界面下，按键先到它那里），等它播完；返回要跳去的 scene（"" = 接着播）
func _cockpit_step(kind: String, st: Dictionary) -> String:
	if world.cockpit == null:
		_warn_once("%s：剧本 rooms 里没有 cockpit，跳过" % kind)
		return ""
	var bgm = BGM_GD.get_bgm(level.get_tree())
	if kind == "keepsake_choice" and not ff:
		bgm.play("space_choice", NAN, 2.0)          # 作者 11-04 的配乐：选烧什么的时候
	# 11-05 作者「每个飞船游戏都要播放音乐」：躲碎石、往前一冲进场放 flight_theme（theme.wav 的循环版 track，旧曲淡出它淡入交叉；
	# 同一段里再进接着上次的位置）。躲碎石：交叉 1.5 秒，玩完它淡出 2 秒、原来那首接回来（没有就只淡出）。
	# 往前一冲只有约 7 秒：淡入快（0.7 秒）、结束不淡出，一直放进接下来的 end_chapter（stop 2 秒）/ 落地 fade_to（_fade_to 里淡 2.5 秒）。
	# 驾驶舱没有自己的环境声循环；碎石段的气流 / 轰鸣是玩法提示，不动。
	var ship_music := kind in ["debris_steer", "cockpit_dash"] and not ff
	var prev_track := ""
	if ship_music:
		prev_track = bgm.current()
		bgm.play("flight_theme", NAN, 0.7 if kind == "cockpit_dash" else 1.5)
		_ship_music_hold = kind == "cockpit_dash"
	var n: Control = (load(COCKPIT_STEPS[kind]) as GDScript).new()
	n.name = kind
	dlg.add_child(n)
	cockpit_ui = n
	var r: String = await n.play(self, st)
	cockpit_ui = null
	(load("res://scripts/audio_fade.gd") as GDScript).release(n, 0.8)   # 冲刺的引擎声还没放完：淡掉，不跟着节点一起被掐断（11-04 作者）
	n.queue_free()
	if kind == "keepsake_choice" and bgm.current() == "space_choice":
		bgm.stop(2.5)
	if kind == "cockpit_dash" and level.has_method("hum_done"):
		level.hum_done()                             # 冲出去 / 落地了：驾驶舱引擎声淡掉，这一章不再回来
	if ship_music and kind != "cockpit_dash" and bgm.current() == "flight_theme":
		if prev_track != "" and prev_track != "flight_theme":
			bgm.play(prev_track, NAN, 2.0)
		else:
			bgm.stop(2.0)
	return r


func _wait(sec: float) -> void:
	var t := 0.0
	while t < sec and is_inside_tree():
		await StoryState.frame(get_tree())
		t += get_process_delta_time()


# ----------------------------------------------------------------------- 说话
func _say(st: Dictionary) -> void:
	lines += 1
	if ff:
		return
	if st.get("bark", false):
		bark.push(txt(st), bool(st.get("added", false)) and mark_added, str(st["say"]))    # 头顶小气泡，不等
		return
	var who := str(st["say"])
	var tl := txt_lang(st)
	var text: String = tl[0]
	speaking = who
	var n := npc(who)
	# 别人说话时，站着的晨转过去看说话的人
	if n != null and n != chen and n.visible and chen._vel <= 0.0:
		chen._set_facing(1 if n.position.x > chen.position.x else -1)
	var nm := txt_in(speakers.get(who, who), str(tl[1]))
	var gn: Node2D = n if n != null and npcs.values().has(n) else null
	if gn != null:
		gn.talk(true)
	var source_text := txt_in(st, "zh")
	var typing_sec := clampf(float(source_text.length()) / dlg.CPS_ZH, 0.25, 4.0)
	await dlg.say(nm, NAME_COLORS.get(who, UITheme.ACCENT), text, _anchor.bind(who), bool(st.get("added", false)) and mark_added, typing_sec, txt_in(st, "en" if I18n.is_zh() else "zh"))
	if gn != null and is_instance_valid(gn):
		gn.talk(false)
	speaking = ""
	if _item_show != null and _item_show_until_say:
		_drop_item_show()


func _anchor(who: String) -> Vector2:
	if world.treeline_view_shown():
		return TREELINE_VIEW_ANCHOR             # 树冠缺口那一屏：框放在画面下方居中，不挡凹口
	var left: Vector2 = level.cam_left()
	var zk: float = level.cam.zoom.x            # 镜头拉近时世界坐标 → 屏幕要乘上
	if who == "chen" and not is_nan(_bark_at) and not busy:
		return (Vector2(_bark_at, chen.position.y - _bark_y) - left) * zk    # hotspot 上方浮的那一句（飞船）
	var n := npc(who)
	if n != null and n.visible:
		var hd := float(n.head) if npcs.values().has(n) else float(HEAD.get(who, 50.0))
		var a := (n.position - left + Vector2(0, -hd)) * zk
		# 11-05 夜测（河流篇 farewell_b）：show_item 举在晨头顶的图标压在她那句话的字上：框放到图标上面
		if n == chen and _item_show != null and is_instance_valid(_item_show) and _item_show.visible and _item_show.texture != null:
			# 和 _update_item_show 同一个算法（刚举起来那一帧图标还没摆好位置）：头顶上 3 像素 + 图标高 + 抬起 6
			var icon_top: float = (chen.position.y - left.y - float(chen.FOOT.y) - 4.0) * zk - _item_show.texture.get_size().y - 6.0
			a.y = minf(a.y, icon_top - 1.0)
		return a
	# 画面外的声音：树屋在屏幕里就从门那边来（屋里的人隔着门说话），不然屏幕上方中间
	if not world.in_room() and world.stages.is_empty():
		var dx: float = float(world.house["door"]) - left.x
		if dx > 30.0 and dx < 450.0:
			return Vector2(dx, float(world.house["floor"]) - left.y - 44.0)
	return Vector2(240, 44 if not level.bars_on() else 44 + level.BAR_H)


func _narr(st: Dictionary) -> void:
	lines += 1
	if ff:
		return
	var text := txt(st["narr"])
	await dlg.narr(text, clampf(0.9 + text.length() * 0.08, 1.4, 3.0))


# ----------------------------------------------------------------------- 走 / 转身 / 出现
## to → {ok, x, room}：marker / 物件 / 数字 / 角色名（走到那个角色旁边）
func _resolve(to, who := "chen") -> Dictionary:
	if to is String:
		var n := npc(str(to))
		if n != null:
			var me := npc(who)
			var side := -1.0 if me == null or me.position.x < n.position.x else 1.0
			return {"ok": true, "x": n.position.x + side * 24.0, "room": world.room}
	var r: Dictionary = world.resolve(to)
	if not r["ok"]:
		_warn_once("找不到位置：" + str(to))
	return r


func _walk(st: Dictionary) -> void:
	var who := str(st.get("who", "chen"))
	var r := _resolve(st.get("to", 0), who)
	if not r["ok"]:
		return
	var x: float = r["x"]
	var n := npc(who)
	if n == null:
		_warn_once("walk：不认识 " + who)
		return
	var cl_t := 0.0
	while n != chen and n.has_meta("lv_climbing") and not ff and cl_t < 20.0:
		await StoryState.frame(get_tree())        # 前面 wait:false 的 walk 还在上 / 下石阶：先等这段走完（两段一起跑会抢着走）
		cl_t += get_process_delta_time()
	var tlv := _lv_target(st.get("to", 0), n)
	x = _no_pass_chen(n, x, tlv)
	x = _clear_x(n, x, world.room if n == chen else _room_of(n), tlv, n.position.x, n == chen)    # 人和人不叠（晨走过去时跟着的人自己让）
	x = _no_pass_chen(n, x, tlv)          # 自己这边没空地、躲到晨另一边去了：还是停在自己这边（不穿过晨）
	if ff:
		_place(n, x, world.room if n == chen else _room_of(n), tlv)
		return
	var wait: bool = st.get("wait", true)
	var lsg := _lv_stage()
	if lsg != null and tlv >= 0 and tlv != _lv_of(n, lsg) and not (who == "chen" and _enter_scene):
		# 多层小屋：目标在别的层 → 先沿石阶走上 / 下去，再走到那一点
		if wait:
			await _lv_walk(n, lsg, tlv, x, st)
		else:
			_lv_walk(n, lsg, tlv, x, st)
		return
	match who:
		"chen":
			if _enter_scene:
				return                       # 不推人：走进来触发的剧情不让晨自己走（停在看得见的边上）
			if st.has("speed"):
				_warn_once("walk：晨的 speed 不支持（晨的速度在 chen.gd 里，不改），按平常速度走")
			var w: Vector2 = world.walls(chen.position.x)
			x = clampf(x, w.x + 4.0, w.y - 4.0)
			x = _chen_no_pass(x)                 # 路上有人：停在那人旁边（会让路的被推着往前让）
			_chen_goal = x                       # 还在走的时候别人按这里躲（_clear_blocks）；走到了在 _chen_walk 里清掉
			if str(st.get("pace", "")) == "walk":
				# "pace": "walk"（10-29）：走路的速度，慢慢起步、慢慢停（level_forest.gd 的 stroll_to；动画照旧 100ms 一帧）
				if wait:
					await level.stroll_to(x)
				else:
					level.stroll_to(x)
			elif wait:
				await _chen_walk(x)
			else:
				_chen_walk(x)
		"deer":
			deer.visible = true
			_deer_go(x, st)
			while wait and not ended and is_inside_tree() and _deer_moving():
				await StoryState.frame(get_tree())
		_ when npcs.values().has(n):
			n.visible = true
			var nsp := float(st.get("speed", -1.0))
			if nsp <= 0.0:
				nsp = float(n.get("speed"))
			if wait and not ff:
				# 晨被锁着等人走路：一段最多等 WALK_WAIT_MAX 秒，远的就走快一点（最多快到 WALK_HURRY 倍，不会嗖地飞过去）
				nsp = clampf(absf(x - n.position.x) / WALK_WAIT_MAX, nsp, nsp * WALK_HURRY)
			n.walk_to(x, nsp)
			while wait and n.is_walking():
				await StoryState.frame(get_tree())
		_:
			miluo.visible = true
			miluo.glide_to(x, float(st.get("speed", miluo.GLIDE_SPEED)))
			while wait and miluo.is_gliding():
				await StoryState.frame(get_tree())


## 多层小屋（room.json levels，妮芙家）：现在这间是多层的就返回它
func _lv_stage(r := "") -> Node2D:
	var sg: Node2D = world.stage(r if r != "" else world.room) if world != null else null
	return sg if sg != null and sg.has_method("has_levels") and sg.has_levels() else null


func _lv_of(n: Node2D, sg: Node2D) -> int:
	return int(sg.chen_lv) if n == chen else int(sg.npc_lv.get(n.name, sg.chen_lv))


## walk / show 的目标在哪层：marker 的层、或那个人所在的层；不是多层 = −1
func _lv_target(to, n: Node2D = null) -> int:
	if not to is String:
		return -1
	var tn := npc(str(to))
	var sg := _lv_stage(_room_of(n) if n != null and n != chen else "")
	if sg == null:
		sg = _lv_stage()
	if sg == null:
		return -1
	if tn != null and tn != n:
		return _lv_of(tn, sg)
	return sg.marker_level(str(to))


## 沿石阶换层再走到 x（晨 / NPC）。石阶上 = 脚底跟着斜线走（没有爬楼梯的帧，走路动画 + 平滑位移）
func _lv_walk(n: Node2D, sg: Node2D, to_lv: int, x: float, st := {}) -> void:
	if n == chen and not missing_anims.has("climb"):
		missing_anims["climb"] = true            # 上下石阶：没有爬楼梯的帧，先用走路 + 沿斜线位移（给奥斯卡的清单）
		print("MISSING_ANIM climb")
	n.set_meta("lv_climbing", true)
	var sp := float(st.get("speed", -1.0))
	if sp <= 0.0 and n != chen:
		sp = maxf(float(n.get("speed")), 56.0)      # 换层的路远：妮芙飘得快一点（剧本没写速度时）
	var route: Array = sg.route(_lv_of(n, sg), to_lv)
	if n != chen and st.get("wait", true) and not ff:
		# 晨被锁着等人上下楼：整段路（到楼梯口、楼梯、到目标）最多等 WALK_WAIT_MAX + 1 秒，远的就快一点（最多 WALK_HURRY 倍）
		var px := n.position.x
		var path_len := 0.0
		for e in route:
			path_len += absf(float(e["x0"]) - px) + absf(float(e["x1"]) - float(e["x0"]))
			px = float(e["x1"])
		path_len += absf(x - px)
		sp = clampf(path_len / (WALK_WAIT_MAX + 1.0), sp, sp * WALK_HURRY)
	for e in route:
		if n == chen:
			await _chen_walk(float(e["x0"]), true)
			sg.chen_stair = int(e["si"])
			await _chen_walk(float(e["x1"]), true)
			sg.chen_stair = -1
			sg.chen_lv = int(e["to"])
		else:
			n.visible = true
			n.walk_to(float(e["x0"]), sp)
			while n.is_walking():
				await StoryState.frame(get_tree())
			n.ground_fn = sg.stair_fn(int(e["si"]))
			n.walk_to(float(e["x1"]), sp)
			while n.is_walking():
				await StoryState.frame(get_tree())
			sg.npc_lv[n.name] = int(e["to"])
			n.ground_fn = sg.level_fn(int(e["to"]))
	n.remove_meta("lv_climbing")
	if n == chen:
		var w: Vector2 = world.walls(chen.position.x)
		await _chen_walk(clampf(x, w.x + 4.0, w.y - 4.0))
	else:
		n.walk_to(x, sp)
		while n.is_walking():
			await StoryState.frame(get_tree())


## 点了别的层的 hotspot（鼠标 / 自动玩）：先走上 / 下去，到那一层的楼梯口为止，再播它的剧情
func _lv_reach(p: Dictionary) -> void:
	var sg := _lv_stage()
	var at = (p["h"] as Dictionary).get("at", 0)
	var tlv := _lv_target(at)
	if sg == null or tlv < 0 or tlv == sg.chen_lv or ff:
		return
	busy = true
	hotspots.active = false
	level.story_begin(false)
	await _lv_walk(chen, sg, tlv, float(p["x"]))
	level.story_end()
	busy = false
	hotspots.active = true


## 鹿：剧本 speed ≤ 60 = 走路（npc_deer.gd 的 walk_to，不传速度：它自己的 WALK_SPEED 是蹄子不打滑的唯一速度），
## 不然跑（run_to）；没有 walk_to 就都跑
func _deer_go(x: float, st: Dictionary) -> void:
	var sp := float(st.get("speed", deer.RUN_SPEED))
	if sp <= 60.0 and deer.has_method("walk_to"):
		deer.call("walk_to", x)
	else:
		deer.run_to(x, sp)


func _deer_moving() -> bool:
	if deer.has_method("is_walking") and bool(deer.call("is_walking")):
		return true
	return deer.is_running()


## solo = true（走石阶用）：不为路上的人停步、不等人——走楼梯是一整段路，半路停在楼梯口旁边会被直接接到斜线上（y 一下跳上去 = 闪现），
## 每帧在「停 / 走」之间来回切又让跑步动画起不来（单脚滑）。11-02 作者：妮芙家第一次上楼闪现、晨没有跑步动画在单脚滑。路上的人自己让（_make_way）。
func _chen_walk(x: float, solo := false) -> void:
	var t := 0.0
	var dir := signf(x - chen.position.x)
	while dir != 0.0:
		var d := (x if solo else _chen_no_pass(x, true)) - chen.position.x      # 走着走着前面有人站下了：停在他旁边
		if absf(d) <= 2.0 + chen.stop_distance() or signf(d) != dir:
			break
		if level.player_free():
			break                            # 过场播完了（walk 带 wait:false 的还没走到）：松手，绝不推着玩家走
		chen.auto_dir = dir if solo else (0.0 if _chen_blocked(dir) else dir)     # 前面的人还在走：跟在后面等一下，不撞上去
		await StoryState.frame(get_tree())
		t += get_process_delta_time()
		if t > 20.0:
			chen.position.x = _chen_no_pass(x, true)
			break
	chen.auto_dir = 0.0
	_chen_goal = NAN
	t = 0.0
	while chen._vel > 0.0 and t < 1.0:
		await StoryState.frame(get_tree())
		t += get_process_delta_time()


func _face(st: Dictionary) -> void:
	var n := npc(str(st.get("who", "chen")))
	if n == null:
		return
	var to = st.get("to", 0)
	var tx := 0.0
	var tn := npc(str(to)) if to is String else null
	if tn != null:
		tx = tn.position.x
	else:
		var r: Dictionary = world.resolve(to)
		if not r["ok"]:
			_warn_once("face：找不到 " + str(to))
			return
		tx = r["x"]
	if absf(tx - n.position.x) < 1.0:
		return
	n._set_facing(1 if tx > n.position.x else -1)


func _show(st: Dictionary, on: bool, instant := false) -> void:
	var who := str(st.get("who", ""))
	var n := npc(who)
	if n == null:
		world.set_prop(who, "show" if on else "hidden")     # 引擎扩展：物件也能 show / hide
		return
	# 11-05 夜测：上一步 hide 带 fade 不等（鹿边走边淡进雾里 1.2 秒），紧接着 show at 别处（回树屋门口）：
	# 原来直接把淡出截断成 0.25 秒——画面里的鹿一下子没了。等它自己淡完再放过去。
	if on and st.has("at") and not ff and not instant and n.get_meta("vis_hiding", false):
		var ht = (n.get_meta("vis_tw") if n.has_meta("vis_tw") else null)
		while ht is Tween and (ht as Tween).is_valid() and (ht as Tween).is_running():
			await StoryState.frame(get_tree())
	if st.has("at"):
		var r: Dictionary = world.resolve(st["at"])
		if r["ok"]:
			var slv := _lv_target(st["at"], n) if _lv_stage(str(r["room"])) != null else -1
			var tx := _clear_x(n, r["x"], str(r["room"]), slv)       # 人和人不叠
			var seen_from := _seen_now(n)
			var seen_to: bool = n.is_visible_in_tree() and n.modulate.a > 0.5 and qa_screen_open() and str(r["room"]) == world.room \
				and _on_screen(Vector2(tx, n.position.y), -8.0)
			if on and not ff and not instant and seen_from and str(r["room"]) == world.room and absf(tx - n.position.x) > 6.0 \
					and (slv < 0 or _lv_stage(str(r["room"])) == null or slv == _lv_of(n, _lv_stage(str(r["room"])))):
				await _show_move(n, tx, str(r["room"]), slv)       # 已经在画面里的人：滑过去 / 淡出淡入，不瞬移
			elif on and not ff and not instant and (seen_from or seen_to) and absf(tx - n.position.x) > 6.0:
				await _show_move(n, tx, str(r["room"]), slv, true)   # 换层，或者从画面外放进画面里：淡出（看不见就直接）、放好、淡入
			else:
				_place(n, tx, r["room"], slv)
		else:
			_warn_once("show：找不到 " + str(st["at"]))
	# "fade": 秒（10-29）：按 4 档透明度淡入 / 淡出（鹿走进雾里、慢慢出现），不突然出现 / 消失；不等它淡完就播下一步
	var fade := 0.0 if ff else float(st.get("fade", 0.0))
	# 11-04 作者「所有的场景切换都要丝滑……我最讨厌的就是闪现」：剧本没写 fade、人又就在画面里，一律淡（进 SHOW_FADE_IN、出 SHOW_FADE_OUT）。
	# 换地方时放人（instant：黑着 / _door_move 管）不算
	if fade <= 0.0 and not ff and not instant and qa_screen_open() and _room_of(n) == world.room and _on_screen(n.position, -8.0) \
			and on != n.visible:
		fade = SHOW_FADE_IN if on else SHOW_FADE_OUT
	if n.has_meta("vis_tw"):
		var old = n.get_meta("vis_tw")
		if old is Tween and (old as Tween).is_valid():
			(old as Tween).kill()
		n.remove_meta("vis_tw")
		if n.get_meta("vis_hiding", false):
			n.visible = false              # 11-04 --qa_live：上一次 hide 的淡出还没完就又 show（鹿从坡地回门口）：先当它已经藏好了，下面照常淡入，不然一下子冒在新地方
		n.remove_meta("vis_hiding")
		n.modulate.a = 1.0
	if fade > 0.0 and not on and n.visible:
		var tw := create_tween()
		n.set_meta("vis_tw", tw)
		n.set_meta("vis_hiding", true)
		tw.tween_method(func(a: float): n.modulate.a = ceilf(a * 4.0) / 4.0, 1.0, 0.0, fade)
		tw.tween_callback(func():
			n.visible = false
			n.modulate.a = 1.0
			n.remove_meta("vis_tw")
			n.remove_meta("vis_hiding"))
		return
	var was := n.visible
	if _qa_live and on and not was and fade <= 0.0 and not ff and qa_screen_open() and _on_screen(n.global_position, 8.0):
		print("QA_POPIN %s 在画面里凭空出现（show 没有 fade，也不是走进来）scene=%s room=%s x=%d" % [who, _cur_scene, world.room, int(n.position.x)])
		qa_counts["popin"] = int(qa_counts.get("popin", 0)) + 1
	n.visible = on
	sync_npc_vis(true)
	if fade > 0.0 and on and not was and n.modulate.a > 0.0:
		var tw2 := create_tween()
		n.set_meta("vis_tw", tw2)
		n.modulate.a = 0.0
		tw2.tween_method(func(a: float): n.modulate.a = floorf(a * 4.0) / 4.0, 0.0, 1.0, fade)
		tw2.tween_callback(func(): n.remove_meta("vis_tw"))


const SHOW_FADE_IN := 0.4
const SHOW_FADE_OUT := 0.3


## 这个人现在就在画面里看得见（不黑、不透明、在镜头里）
func _seen_now(n: Node2D) -> bool:
	return n.is_visible_in_tree() and n.modulate.a > 0.5 and qa_screen_open() and _on_screen(n.position, -8.0) \
		and _room_of(n) == world.room


## 11-04 作者「闪现」：剧本 show at 一个已经站在画面里的人（上一段留下来的阿汀、妮芙）：原来直接放过去 = 瞬移。
## 近的（SHOW_GLIDE 以内）缓缓滑过去；远的、换层的先淡出（4 档）、放过去、再淡入。
const SHOW_GLIDE := 60.0


func _show_move(n: Node2D, x: float, room: String, lv: int, force_fade := false) -> void:
	if not force_fade and absf(x - n.position.x) <= SHOW_GLIDE:
		var x0 := n.position.x
		var tw := create_tween()
		tw.tween_method(func(k: float):
			n.position.x = round(lerpf(x0, x, k))
			if n.has_method("_snap_y"):
				n._snap_y()
			elif n.has_method("_snap"):
				n._snap(), 0.0, 1.0, 0.35).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		await tw.finished
		_place(n, x, room, lv)
		return
	var tw2 := create_tween()
	tw2.tween_method(func(a: float): n.modulate.a = ceilf(a * 4.0) / 4.0, 1.0, 0.0, 0.25)
	await tw2.finished
	_place(n, x, room, lv)
	var tw3 := create_tween()
	tw3.tween_method(func(a: float): n.modulate.a = floorf(a * 4.0) / 4.0, 0.0, 1.0, 0.35)
	await tw3.finished


## fade_to 的 "place": {"deer": marker, …}：换地方的同时（黑着的时候 / 进出屋前墙还挡着的时候）把这些人放到位、显示出来，
## 淡入以后不会凭空冒出来
func _fade_place(st: Dictionary) -> void:
	var pl = st.get("place", {})
	if not pl is Dictionary:
		return
	for who in pl:
		_show({"who": str(who), "at": pl[who]}, true, true)      # 换地方时放人：黑着 / 进出门有 _door_move 管淡入淡出
	# "face": {"chen": "ting", …}：黑着的时候就转好身，揭开时不会看见转身、镜头也不会跟着晃（只给黑着换位置的 fade_to 用）
	var fc = st.get("face", {})
	if fc is Dictionary and not fc.is_empty():
		for who2 in fc:
			_face({"who": str(who2), "to": fc[who2]})
		if not ff:
			level._snap_camera()


func _room_of(n: Node2D) -> String:
	return str(_npc_room.get(n.name, "forest"))


## 弥洛和树屋前墙的前后（10-29）：前墙本来就画在弥洛前面一格（屋里的她被前墙盖住）。
##   在屋里 = 前墙后面；在屋外 = 前墙前面（从屋前走过不会被墙吞掉）；往屋里走（滑向前墙范围里的点）= 前墙后面
##   （从屋子边上绕到后面去，被墙一点点挡住）。只在她和前墙不重叠、或者前墙透明（在屋里）的时候换，换的那一下看不出来。
const MILUO_HALF := 16.0            # 弥洛半宽（帧宽 31，留一点）
var _miluo_front := false


func _update_miluo_layer() -> void:
	if miluo == null or world == null or not world.house.has("front_x0"):
		return
	var want := _miluo_front
	var x := miluo.position.x
	if _room_of(miluo) == "treehouse":
		want = false
	elif miluo.is_gliding():
		want = not world.behind_front(float(miluo._glide_x))
	elif not world.behind_front(x):
		want = true
	if want == _miluo_front:
		return
	if ff or not miluo.visible or not world.overlaps_front(x, MILUO_HALF) or world.house_front.modulate.a < 0.05:
		_set_miluo_front(want)


func _set_miluo_front(on: bool) -> void:
	_miluo_front = on
	var hf: Node2D = world.house_front
	if hf.get_parent() != miluo.get_parent():
		return
	var i := miluo.get_index()
	var j := hf.get_index()
	if on and i < j:
		level.move_child(miluo, j)          # 前墙挪到她后面一格
	elif not on and i > j:
		level.move_child(miluo, j)


## 把角色直接放到 x（房间 r 的地面上），停掉正在跑 / 滑
## lv：多层小屋里放到哪层（−1 = 晨留在原来那层、NPC 放在晨现在那层）
func _place(n: Node2D, x: float, r: String, lv := -1) -> void:
	if _qa_live and not ff and n.is_visible_in_tree() and n.modulate.a > 0.05 and r == world.room and absf(x - n.position.x) > 6.0 and qa_screen_open() \
			and Engine.get_process_frames() != _qa_room_frame \
			and (_on_screen(n.position, 0.0) or _on_screen(Vector2(x, n.position.y), 0.0)):
		var stk: Array = []
		for f in get_stack().slice(1, 6):
			stk.append("%s:%d" % [str(f["function"]), int(f["line"])])
		print("QA_PLACE %s %d→%d scene=%s step=%d via %s" % [n.name, int(n.position.x), int(x), _cur_scene, step_i, " < ".join(stk)])
	if n == deer and _deer_moving():
		deer._running = false
		if "_walking" in deer:
			deer.set("_walking", false)
		deer._idle(2.0)
	if n == miluo and miluo.is_gliding():
		miluo._gliding = false
	if n == chen:
		chen.auto_dir = 0.0
		chen._vel = 0.0
	if npcs.values().has(n):
		n.stop()
		n.ground_fn = _npc_ground(n, r)
		_env_form(n, r)
	var ls := _lv_stage(r)
	if ls != null:
		if lv < 0 and n == chen and _arrive_lv >= 0:
			lv = _arrive_lv
		if lv < 0:
			lv = ls.chen_lv
		if n == chen:
			ls.chen_lv = lv
			ls.chen_stair = -1
		elif npcs.values().has(n):
			ls.npc_lv[n.name] = lv
			n.ground_fn = ls.level_fn(lv)
	var gy: float = world.ground_at(x, r) if ls == null or n == chen else ls.level_fn(lv).call(x)
	n.position = Vector2(round(x), round(gy) + 1.0)
	_npc_room[n.name] = r
	if n == miluo and world.house.has("front_x0"):
		_set_miluo_front(r != "treehouse" and not world.behind_front(round(x)))    # 直接放过去的：图层也直接对


## 通用角色按房间的 env 换一套颜色（json 写了 "env_forms": true 才换；forms 里有这个 env 就用它，没有回默认那套）：
## 云层星的人群（crowd）白天在芦苇地、夜里在云镇，两套明暗（11-01 终章角色）
func _env_form(n: Node2D, r: String) -> void:
	if not (n.get("cfg") is Dictionary and bool((n.get("cfg") as Dictionary).get("env_forms", false))):
		return
	var sg = world.stages.get(r, null)
	var e := ""
	if sg != null:
		e = str(sg.env if not (sg.is_house and sg.host != null) else sg.host.env)
	var f := e if n.has_form(e) else ""
	if f != str(n.get("form")):
		n.set_form(f)


## NPC 脚下的地面。悬浮的（妮芙的鲸鱼壳，hover）飘过比她窄的坑（旧街挂钩旁通仓库的下沉口）不掉进去：
## 左右各 1.5 个半身宽里够得着坑沿就按坑沿的高度飘（两边都有支撑）；斜坡、台阶上两边一高一低，照原来的地面走
func _npc_ground(n: Node2D, r: String) -> Callable:
	var c = n.get("cur")
	if not (c is Dictionary and float((c as Dictionary).get("hover", 0.0)) > 0.0):
		return func(gx: float) -> float: return world.ground_at(gx, r)
	var reach := _half_w(n) * 1.5
	return func(gx: float) -> float:
		var g: float = world.ground_at(gx, r)
		var lo := g
		var ro := g
		var s := 4.0
		while s <= reach:
			lo = minf(lo, world.ground_at(gx - s, r))
			ro = minf(ro, world.ground_at(gx + s, r))
			s += 4.0
		return minf(g, maxf(lo, ro))


## 屋里屋外：和晨不在同一边、又站在树屋图范围里的角色淡掉（晨进屋时屋外门口的鹿；晨在屋外时屋里的弥洛本来就被前墙挡着）
func sync_npc_vis(instant := false) -> void:
	_sync_generic_vis(instant)
	for n in [deer, miluo]:
		var nd: Node2D = n
		var away: bool = _room_of(nd) != world.room and world.in_house_span(nd.position.x)
		var a := 0.0 if away and world.in_room() else 1.0
		# 上一次还没淡完的先停掉（10-29：进屋时先淡掉、紧接着 fade_to 的 place 把人放进屋，旧的 tween 会把人又淡没）
		var old = nd.get_meta("sync_tw") if nd.has_meta("sync_tw") else null
		if old is Tween and (old as Tween).is_valid():
			(old as Tween).kill()
		if instant or ff:
			nd.modulate.a = a
		elif not is_equal_approx(nd.modulate.a, a):
			var tw := create_tween()
			tw.tween_property(nd, "modulate:a", a, 0.5)
			nd.set_meta("sync_tw", tw)


## 晨的动作别名表（data/chen_anim_alias.json：剧本动作名 → ANIMS 里的段名，对照 docs/给美术姐和奥斯卡的需求.md 第一节）
func chen_alias() -> Dictionary:
	if _chen_alias == null:
		_chen_alias = {}
		if FileAccess.file_exists(CHEN_ALIAS):
			var d = JSON.parse_string(FileAccess.get_file_as_string(CHEN_ALIAS))
			if d is Dictionary:
				_chen_alias = d
	return _chen_alias


## 剧本要晨做 name：实际播哪段（原名有就原名，没有看别名表指的那段）；都没有 = ""
func chen_anim(name: String) -> String:
	if chen.spr.sprite_frames.has_animation(StringName(name)):
		return name
	var a := str(chen_alias().get(name, ""))
	if a != "" and not name.begins_with("_") and chen.spr.sprite_frames.has_animation(StringName(a)):
		return a
	return ""


func _anim(st: Dictionary) -> void:
	if ff:
		return
	var who := str(st.get("who", ""))
	var name := str(st.get("name", ""))
	if _wood_mode and who == "chen" and name == "pickup":
		return                    # 过场里已经弯过腰了
	var n := npc(who)
	if name == "hop" and n != null and n.has_method("hop"):
		n.hop()                   # 不是帧动画：原地蹦两下（不等，边跟着走边蹦）
		return
	var key := "miluo" if n == miluo else who
	var m: Dictionary = ANIM_MAP.get(key, {})
	if n == chen and n != null and not m.has(name):
		# 晨：chen.gd 的 ANIMS 里有同名的段就直接播（奥斯卡画好加进去就能用）；没有看别名表（data/chen_anim_alias.json）；
		# 都没有就退回待机，记下来给奥斯卡（帧速照旧 100ms）
		var an := chen_anim(name)
		if an != "":
			chen.spr.play(StringName(an))
			return
		if not missing_anims.has(name):
			missing_anims[name] = true
			print("MISSING_ANIM " + name)
		if chen._vel <= 0.0:
			chen.spr.play(&"idle")
		return
	if n != null and npcs.values().has(n):
		if not n.play(name):
			var key2 := "%s.%s" % [who, name]
			if not missing_anims.has(key2):
				missing_anims[key2] = true
				print("MISSING_ANIM " + key2)
		return
	if n == null or not m.has(name):
		_warn_once("anim：%s 没有 %s" % [who, name])
		return
	var spr: AnimatedSprite2D = n.spr
	if spr.sprite_frames.has_animation(StringName(m[name])):
		spr.play(StringName(m[name]))


# ----------------------------------------------------------------------- 物品 / 日记 / 声音
func _give(id: String) -> void:
	if _wood_mode and Inventory.has(id):
		return                    # 木头拾取过场已经给过了
	if not Inventory.defined(id):
		_warn_once("物品表里没有 %s（用色块占位）" % id)
		Inventory.register_fallback({"id": id, "name": {"zh": id, "en": id}, "rarity": "common", "burn": 0, "personal": true,
			"desc": {"zh": "", "en": ""}})
	Inventory.add(id)
	level.on_inventory_changed()
	if ff:
		return
	var it := Inventory.item(id)
	var icon := Inventory.icon(id)
	dlg.toast(icon, I18n.t("got_item") % txt(it.get("name", id)))
	if bag_locked():
		_show_item({"item": id, "sec": 1.6})     # 背包还没拿回来：不往背包飞，晨举一下
		await _wait(0.6)
		return
	await _fly_to_bag(icon, chen.position + Vector2(0, -36) - level.cam_left())


func _take(id: String) -> void:
	if not Inventory.has(id):
		_warn_once("take：背包里没有 " + id)
	Inventory.remove(id)
	level.on_inventory_changed()
	if not ff:
		dlg.toast(Inventory.icon(id), I18n.t("gave_item") % txt(Inventory.item(id).get("name", id)))


func _fly_to_bag(icon: Texture2D, from: Vector2) -> void:
	var tr := TextureRect.new()
	tr.texture = icon
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tr.position = from.round()
	dlg.add_child(tr)
	var to: Vector2 = level.bag_target() - icon.get_size() / 2.0
	var tw := create_tween()
	tw.tween_property(tr, "position:y", from.y - 12.0, 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_method(func(k: float):
		var p := Vector2(from.x, from.y - 12.0).lerp(to, k)
		p.y -= sin(k * PI) * 16.0
		tr.position = p.round(), 0.0, 1.0, 0.5).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	await tw.finished
	tr.queue_free()
	level.bag_bump()


func _journal(st: Dictionary) -> void:
	var e := {"zh": str(st.get("zh", "")), "en": str(st.get("en", ""))}
	if st.has("tag"):
		e["tag"] = str(st["tag"])
	var holder := _journal_holder()
	if holder != "journal":
		e["tag"] = "on_" + holder
	StoryState.add_journal(e)
	if not ff and not st.has("sfx"):
		_sfx({"name": "pen_write", "db": -6.0})
	if holder != "journal":
		if not ff:
			dlg.toast(Inventory.icon(holder), I18n.t("paper_added") % txt(Inventory.item(holder).get("name", holder)))
		return
	if not Inventory.has("journal"):
		if not Inventory.defined("journal"):
			Inventory.register_fallback({"id": "journal", "name": {"zh": "日记", "en": "Journal"}, "rarity": "common",
				"burn": 0, "personal": true, "icon": "res://art/forest_story/icon_journal.png", "desc": {"zh": "", "en": ""}})
		Inventory.add("journal")
		level.on_inventory_changed()
	if not ff:
		dlg.toast(Inventory.icon("journal"), I18n.t("journal_added"))


## 日记首页规则（终章，docs/第三章计划.md 第十节）：日记烧掉以后（burned_journal、背包里没有日记）不再凭空把日记变回来，
## 记的东西写在借来的纸上（结局里 give borrowed_paper），没有纸就写在航图背面（结局四「写在航图背面吧」）。
## 这些条目带 tag on_<那件>，背包里那件的描述后面接着列出来（desc_from_tag）。日记首页（journal_first_page）永远不写：
## 「我一定要找到大象，因为」后面一直空着，只能看。
func _journal_holder() -> String:
	if Inventory.has("journal") or not StoryState.has("burned_journal"):
		return "journal"
	for id in ["borrowed_paper", "travel_map"]:
		if Inventory.has(id):
			return id
	return "journal"


func _sfx(st: Dictionary) -> void:
	if ff:
		return
	var name := str(st.get("name", ""))
	var p := _sfx_path(name)
	if p == "":
		missing_sfx[name] = true       # 缺的音效静默跳过（统计里列出来）
		return
	# 音乐盒 / 留声机这一族（长声）：新的一条开始时，同族还在响的淡出 0.4 秒，免得叠在一起
	var fam := _sfx_family(name)
	if fam:
		fade_music_family()
	_sfx_t[name] = Time.get_ticks_msec()
	var a := AudioStreamPlayer2D.new()
	a.stream = load(p)
	a.bus = "SFX"
	a.max_distance = 2000.0
	a.attenuation = 0.5
	a.volume_db = float(st.get("db", 0.0))
	level.add_child(a)
	a.global_position = level.cam_left() + Vector2(240.0 + clampf(float(st.get("pan", 0.0)), -1.0, 1.0) * 320.0, 135.0)
	a.play()
	a.finished.connect(a.queue_free)
	if (load("res://scripts/audio_fade.gd") as GDScript).is_loop(a):
		# 导入时开了循环的（漏气的嘶嘶、水洞的回声……）：不是一下子响，从静音淡进来（11-04 作者：不要突然开始的硬过渡）
		var to := a.volume_db
		a.volume_db = -60.0
		create_tween().tween_property(a, "volume_db", to, 0.5).set_trans(Tween.TRANS_SINE)
	if fam:
		_family.append(a)


static func _sfx_family(name: String) -> bool:
	return name.begins_with("musicbox_") or name.begins_with("gramophone_")


## 音乐盒 / 留声机这一族还在响的全部淡出（新的一条开始、离开树屋时）
func fade_music_family(sec := 0.4) -> void:
	for a in _family:
		if is_instance_valid(a) and (a as AudioStreamPlayer2D).playing:
			var tw := create_tween()
			tw.tween_property(a, "volume_db", -60.0, sec)
			tw.tween_callback((a as Node).queue_free)
	_family.clear()


## 循环环境声：放在 marker 上的 AudioStreamPlayer2D（镜头是听的人：越远越小、左右跟着方位）。没有文件就只记下来、不响。
func _ambient_step(st: Dictionary) -> void:
	var name := str(st.get("name", ""))
	var key := name + "@" + str(st.get("at", ""))
	var on: bool = st.get("on", true)
	if not on:
		if _ambient.has(key):
			var a: AudioStreamPlayer2D = _ambient[key]
			var tw := create_tween()
			tw.tween_property(a, "volume_db", -60.0, 0.8)
			tw.tween_callback(a.queue_free)
			_ambient.erase(key)
		return
	if ff or _ambient.has(key):
		return
	var p := _sfx_path(name)
	if p == "":
		missing_sfx[name] = true
		return
	var r: Dictionary = world.resolve(st.get("at", 0))
	var a := AudioStreamPlayer2D.new()
	a.stream = load(p)
	a.bus = "SFX"
	a.max_distance = float(st.get("dist", 520.0))
	a.attenuation = 1.6
	a.volume_db = -60.0                                   # 11-04 作者：循环声不许硬开——从静音淡进来（和 ambient off 的 0.8 秒淡出对称）
	level.add_child(a)
	create_tween().tween_property(a, "volume_db", float(st.get("db", 0.0)), 0.8)
	var ax := float(r.get("x", 0.0))
	var ay := 200.0
	var rid := str(r.get("room", ""))
	if world.stages.has(rid):
		ay = (world.stages[rid] as Node2D).call("ground_y", ax) - 20.0     # 多房间章节的房间不在 y=0 那一行（小镇在 1620 往下）：放到那间房的地面上
	a.global_position = Vector2(ax, ay)
	a.finished.connect(a.play)       # 循环（.import 里已经设了 loop 的音效不会发 finished，这句就不起作用，也没关系）
	a.play()
	_ambient[key] = a


func _sfx_path(name: String) -> String:
	for ext in [".wav", ".ogg", ".mp3"]:
		if ResourceLoader.exists(SFX_DIR + name + ext):
			return SFX_DIR + name + ext
	return ""


## 晨把一件东西举起来给人看：图标在晨头顶前方，到下一句说完（或 sec 秒）
func _show_item(st: Dictionary) -> void:
	if ff:
		return
	_drop_item_show()
	var id := str(st.get("item", ""))
	var tr := TextureRect.new()
	tr.texture = Inventory.icon(id)
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dlg.add_child(tr)
	_item_show = tr
	_item_show_until_say = not st.has("sec")
	tr.set_meta("t", 0.0)
	if st.has("sec"):
		# 11-05：不能直接抓 tr——sec 没到就举下一件时 tr 已被释放，回调报「Lambda capture at index 0 was freed」。抓 id 比较
		var me_id := tr.get_instance_id()
		get_tree().create_timer(float(st["sec"]), false).timeout.connect(func():
			if _item_show != null and is_instance_valid(_item_show) and _item_show.get_instance_id() == me_id:
				_drop_item_show())


func _drop_item_show() -> void:
	if _item_show != null and is_instance_valid(_item_show):
		_item_show.queue_free()
	_item_show = null


func _update_item_show(delta: float) -> void:
	if _item_show == null or not is_instance_valid(_item_show):
		return
	var t: float = float(_item_show.get_meta("t")) + delta
	_item_show.set_meta("t", t)
	var sz := _item_show.texture.get_size()
	var left: Vector2 = level.cam_left()
	# 11-04 作者「物品正好挡住主角面部」：原来锚在脚上方 34 像素（下巴），图标的身子刚好盖在脸上。
	# 晨的帧 68×60、脚在第 56 行 → 头顶在脚上方约 56；图标底边放到头顶再往上 3 像素，略偏朝向那一侧（像举在额前，不挡脸）
	var top_y: float = -(float(chen.FOOT.y) + 1.0) - 3.0
	var head: Vector2 = (chen.position - left + Vector2(chen.facing * 6.0, top_y)) * level.cam.zoom.x
	var lift := minf(t / 0.2, 1.0) * 6.0
	_item_show.position = (head - Vector2(sz.x / 2.0, sz.y + lift)).round()


# ----------------------------------------------------------------------- 换地方
var _arrive_lv := -1                 # fade_to 进多层小屋：晨（和同行的）落在 at 那个 marker 的层


func _fade_to(st: Dictionary) -> void:
	var room := str(st.get("room", "forest"))
	if _ship_music_hold:                               # 往前一冲以后的落地转场：飞船配乐在黑里淡掉（2.5 秒），不硬停
		_ship_music_hold = false
		var bgm0 = BGM_GD.get_bgm(level.get_tree())
		if bgm0.current() == "flight_theme":
			bgm0.stop(2.5)
	var lsg := _lv_stage(room)
	_arrive_lv = lsg.marker_level(str(st.get("at", ""))) if lsg != null and st.get("at", 0) is String else -1
	var r: Dictionary = world.resolve(st.get("at", 0))
	if not r["ok"]:
		_warn_once("fade_to：找不到 " + str(st.get("at")))
		return
	var x: float = r["x"]
	var arrive := NAN
	if st.has("arrive"):
		var ar: Dictionary = world.resolve(st["arrive"])
		if ar["ok"]:
			arrive = float(ar["x"])
	for w0 in st.get("with", []):
		if npcs.has(str(w0)):
			follow[str(w0)] = float(follow.get(str(w0), FOLLOW_GAP))     # 同行 = 到了以后跟着晨
	if ff:
		_teleport(room, x, st.get("with", []), true)
		_fade_place(st)
		if not is_nan(arrive):
			_place(chen, arrive, room)
		return
	if world.is_stage(room) or world.is_stage(world.room):
		if await _stage_fade(st, room, x, arrive):
			return                         # 小屋前墙 / 竖直平移 / 边走边黑做完了；fade 和带 leave / cam 的走下面原来的
	# 进屋 / 出屋（树屋就在森林里）：不黑屏，前墙淡出 / 淡入
	var door: bool = room != world.room and (room == "treehouse" or world.room == "treehouse") \
		and world.near_house(x) and world.near_house(chen.position.x)
	if door:
		await _door_move(room, x, st.get("with", []), st)
		return
	var out_sec := 0.5
	if st.has("leave"):
		# 边走边黑：晨（和 with 里的人）朝 leave 那边一直走，黑透了再换地方（离开，不是原地消失）
		var lr: Dictionary = world.resolve(st["leave"])
		if lr["ok"]:
			out_sec = 0.8
			chen.auto_dir = signf(float(lr["x"]) - chen.position.x)
	_pixel = str(st.get("style", "")) == "pixel"
	if _pixel:
		await level.pixel_to_black(maxf(out_sec, 0.8))   # 八比特转场：像素块一格一格盖上
	else:
		await level.fade_to_black(out_sec)
	chen.auto_dir = 0.0
	# 11-04 作者截图（河流篇起飞以后一帧暗绿、妮芙和阿汀淡淡地浮在上面）：起飞时停住的镜头没放开，换到驾驶舱以后镜头还看着河岸。
	# 黑着换房间：先放开镜头（cam 参数下面会重新停住）
	# 还有别的淡出在走（起飞那段自己起了一个 1.2 秒的）：等真黑透了再换，不然新房间先露出来一下、又被盖黑（连拍：驾驶舱闪一下）
	var bt := 0.0
	while level.fade.color.a < 0.99 and bt < 2.0:
		await StoryState.frame(get_tree())
		bt += get_process_delta_time()
	level.camera_release()
	_tp_dir = signf(arrive - x) if not is_nan(arrive) and absf(arrive - x) > 2.0 else 0.0
	_teleport(room, x, st.get("with", []), true)
	_fade_place(st)
	if st.has("cam"):
		# 镜头停在 cam 这里不跟晨（晨从画面外走进来）；camera release 步骤或这个 scene 播完放开
		var cr: Dictionary = world.resolve(st["cam"])
		if cr["ok"]:
			level.camera_hold_at(Vector2(float(cr["x"]), world_cam_y(room)))
	await _wait(0.25)
	if is_nan(arrive) or _enter_scene:
		await _from_black(0.5)
		return
	# "arrive": marker（10-29）：淡入的同时晨从 at 走几步到这里（到达，不是凭空站在那）；停稳了才往下播。
	# 只走一小段，走路的速度（level_forest.gd 的 stroll_to），不是过场里把人推着跑
	await _arrive_walk(arrive)


## 黑着的时候晨已经站在入口边上、朝着要走的方向；淡入的同时走几步停住
func _arrive_walk(to: float) -> void:
	if absf(to - chen.position.x) >= 1.0:
		chen._set_facing(1 if to > chen.position.x else -1)
		level._snap_camera()
	level.stroll_to(to)
	await _from_black(0.5)
	while level.strolling() or chen._vel > 0.0:
		await StoryState.frame(get_tree())


var _pixel := false                  # 这次 fade_to 是像素块溶解


func _from_black(sec: float) -> void:
	if _pixel:
		_pixel = false
		await level.pixel_from_black(maxf(sec, 0.8))
	else:
		await level.fade_from_black(sec)


## 镜头（10-29）：{"do": "camera", "hold": true} 停在现在的位置不跟晨（让人走出画面）；
## {"do": "camera", "at": marker 或 x, "sec": n} 慢慢移过去停住（sec = 0 直接到）；{"do": "camera", "release": true} 慢慢跟回晨。
## scene 播完、鹿带路放手让晨走的时候都会自动放开。跳节拍时不动镜头。
func _camera(st: Dictionary) -> void:
	if ff:
		return
	if st.has("zoom"):
		var zs := float(st.get("sec", 1.0))
		if st.get("wait", true) and zs > 0.0:
			await level.camera_zoom(float(st["zoom"]), zs)
		else:
			level.camera_zoom(float(st["zoom"]), zs)
		return
	if st.get("release", false):
		level.camera_release()
		return
	if st.has("at"):
		var r: Dictionary = world.resolve(st["at"])
		if not r["ok"]:
			_warn_once("camera：找不到 " + str(st["at"]))
			return
		var to := Vector2(float(r["x"]), world_cam_y(str(r.get("room", world.room))))
		var sec := float(st.get("sec", 1.0))
		if sec <= 0.0:
			level.camera_hold_at(to)
		elif st.get("wait", true):
			await level.camera_pan(to, sec)
		else:
			level.camera_pan(to, sec)
		return
	if st.get("hold", false):
		level.camera_hold_at(level.cam.position)


var _qa_room_frame := -1               # 换房间的那一帧（这一帧里再放人不算 QA_PLACE：画出来的只有最后那个位置）


var _tp_dir := 0.0                   # 这次换地方以后晨马上要往哪边走（arrive）：同行的人放在另一边。_teleport 用完清零


func _teleport(room: String, x: float, with: Array, snap: bool) -> void:
	_qa_room_frame = Engine.get_process_frames()
	if world.area_of(x) != world.area_of(chen.position.x) or room != world.room:
		_unreach.clear()                  # 换了一段：之前够不着的点重新算
	if world.room == "treehouse" and room != "treehouse":
		fade_music_family()                 # 出了树屋：留声机 / 音乐盒的长声淡掉
	var old_room: String = world.room
	world.set_room(room, ff)
	_place_residents(room)
	var tlv := _arrive_lv if _lv_stage(room) != null else -1
	x = _clear_x(chen, x, room, tlv)          # 人和人不叠：落脚点上站着人就挪开一点
	_place(chen, x, room)
	chen.visible = true
	var w: Vector2 = world.walls(x)
	var off := 0.0
	with = with.duplicate()
	for fw in follow:
		var fnode := npc(str(fw))
		if not with.has(fw) and fnode != null and fnode.visible and world.is_stage(room) and str(_npc_room.get(fnode.name, "")) == old_room:
			with.append(fw)                # 跟着晨的人一起过去
	# 11-05 夜测（河流篇：进妮芙家、市集→楼梯间、进南桥，一到就叠在一起几帧）：同行的人原来一律放在晨左边，
	# 淡入时晨要往左走几步（arrive）就正好走进她身上。放在晨要走的方向的反面（身后）
	var pref := -_tp_dir if _tp_dir != 0.0 else -1.0
	_tp_dir = 0.0
	for who in with:
		var n := npc(str(who))
		if n == null or n == chen:
			continue
		off += _side_gap(n, 30.0)
		var nx := x + pref * off
		if nx < w.x + 10.0 or nx > w.y - 10.0:
			nx = x - pref * off
		nx = _clear_x(n, nx, room, tlv)        # 人和人不叠（也躲开房间里站着的人）
		_place(n, nx, room)
		n.visible = true
		n._set_facing(1 if x > nx else -1)
	_arrive_lv = -1
	level.on_room_changed(snap)
	sync_npc_vis(snap)
	if _overlap_log and not ff:
		print("TELEPORT %s %s | %s" % [_cur_scene, room, _bodies_str()])


## room.json 的 "residents"：住在这个房间里、一直待在那儿的人（10-31 楼梯间柜台后面的水母）。
## 剧本顶层也可以写 "residents"（多一个 "room"，默认 forest）：给不是 room_stage 的地方用（森林空地尽头的大嘴鸟）；setup 末尾放一次。
## [{"who": 角色, "at": marker, "z": 前后（−2 = 压到物件后面）, "face": 1 / −1}]。进这个房间时她还不在这儿，就放好、显示出来——
## 不用剧本 show，所以跳节拍、F8 传送、自由探索进来都一样在；之后人留在这个房间，晨不在时照常藏着（sync_npc_vis）。
func _place_residents(room: String) -> void:
	var sg: Node2D = world.stage(room)
	var list: Array = sg.cfg.get("residents", []).duplicate() if sg != null else []
	for rd2 in data.get("residents", []):
		if rd2 is Dictionary and str(rd2.get("room", "forest")) == room:
			list.append(rd2)
	for rd in list:
		if not rd is Dictionary or str(rd.get("who", "")) == "":
			continue
		var who := str(rd["who"])
		_npc_names[who] = true
		var n := npc(who)
		if n == null or not npcs.values().has(n) or (n.visible and str(_npc_room.get(n.name, "")) == room):
			continue
		var r: Dictionary = world.resolve(rd.get("at", 0))
		if not r["ok"]:
			_warn_once("residents：找不到 " + str(rd.get("at")))
			continue
		_place(n, float(r["x"]), room)
		if rd.has("z"):
			n.set_meta("pose_z", int(rd["z"]))
			n.z_index = int(rd["z"])
		n._set_facing(int(rd.get("face", 1)))
		n.set_meta("resident", true)          # 住在这儿的人钉在原地：晨走过来不飘开让路（11-02 作者：水母被推离了柜台）
		n.visible = true


# ----------------------------------------------------------------------- 鹿带路 / 点选 / 结束
func _guide(st: Dictionary) -> void:
	var r: Dictionary = world.resolve(st.get("to", 0))
	if not r["ok"]:
		_warn_once("guide：找不到 " + str(st.get("to")))
		return
	var x: float = r["x"]
	if ff:
		var side := signf(x - chen.position.x)
		_place(deer, x, world.room)
		deer.visible = true
		_place(chen, x - side * 40.0, world.room)
		return
	deer.visible = true
	_deer_go(x, st)
	if not st.get("wait", true):
		return
	# 不锁晨：这段剧情先停在这里，鹿在前面等；晨走近了再接着播（_process / resume_guide）
	pending_guide = {"x": x}


func _pick(st: Dictionary) -> String:
	var opts: Array = st.get("options", [])
	if opts.is_empty():
		return ""
	if str(st.get("ui", "")) in ["nav", "action"] and world.cockpit != null and world.room == "cockpit":
		var ai := _auto_pick(st) if auto != "" or ff else -1
		if ff:
			return str(opts[clampi(ai, 0, opts.size() - 1)].get("scene", ""))
		var nv: Control = (load(COCKPIT_NAV) as GDScript).new()
		nv.name = "cockpit_nav"
		dlg.add_child(nv)
		cockpit_ui = nv
		var ni: int = await nv.play(self, st, ai)
		cockpit_ui = null
		nv.queue_free()
		return str(opts[clampi(ni, 0, opts.size() - 1)].get("scene", ""))
	var ui: Array = []
	for o in opts:
		var pid := str(o.get("id", ""))
		var key := pid if world.props.has(pid) else pid.trim_prefix("room_")
		var sg_node: Node2D = null
		var sr: String = world.stage_of_prop(pid)
		if sr != "":
			sg_node = world.stage(sr).object(pid)
		ui.append({"label": txt(o.get("label", pid)), "rect": _prop_screen_rect.bind(pid), "node": sg_node if sg_node != null else world.props.get(key, null)})
	var auto_i := -1
	if auto != "" or ff:
		auto_i = _auto_pick(st)
	var i: int = await dlg.pick(ui, auto_i)
	i = clampi(i, 0, opts.size() - 1)
	return str(opts[i].get("scene", ""))


func _prop_screen_rect(pid: String) -> Rect2:
	if world.stage_of_prop(pid) != "":
		var sr: Rect2 = world.prop_rect(pid)
		if sr.size.x > 0:
			sr.position -= level.cam_left()
		return sr
	var key := pid if world.props.has(pid) else pid.trim_prefix("room_")
	if not world.props.has(key) or not (world.props[key] as Sprite2D).visible:
		return Rect2()
	var r: Rect2 = world.prop_rect(key)
	r.position -= level.cam_left()
	return r


## 点选里「对的」那个：选项写了 correct 就是它；不然是 scene 一路 goto 下去不会回到这个点选所在 scene 的那个
func _correct_index(st: Dictionary, here: String) -> int:
	var opts: Array = st.get("options", [])
	if ff and _ff_target != "":
		for i in opts.size():
			var os := str(opts[i].get("scene", ""))
			if _leads_to(os, _ff_target) and not _loops_back(os, here):
				return i
	for i in opts.size():
		if opts[i].get("correct", false):
			return i
	for i in opts.size():
		if not _loops_back(str(opts[i].get("scene", "")), here):
			return i
	return 0


func _loops_back(s: String, here: String) -> bool:
	var seen := {}
	while s != "" and not seen.has(s):
		if s == here:
			return true
		seen[s] = true
		var nxt := ""
		for step in scenes.get(s, []):
			if step is Dictionary and str(step.get("do", "")) == "goto":
				nxt = str(step.get("scene", ""))
		s = nxt
	return false


func _auto_pick(st: Dictionary) -> int:
	var ok := _correct_index(st, _cur_scene)
	var to := _auto_to()
	if to != "" and not ff:
		var opts_to: Array = st.get("options", [])
		for i in opts_to.size():
			if _leads_to(str(opts_to[i].get("scene", "")), to):
				return i
	if auto == "full" and not ff:
		var opts: Array = st.get("options", [])
		for i in opts.size():
			var key := _cur_scene + ":" + str(i)
			if i != ok and not _wrong_tried.has(key):
				_wrong_tried[key] = true
				return i
	return ok


func _auto_to() -> String:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--auto_to="):
			return a.trim_prefix("--auto_to=")
	return ""


var ff_hit_end := false              # 跳节拍时碰到了 end_chapter（跳到 launched：跳完直接播起飞）
var _ship_music_hold := false        # 往前一冲放着的飞船配乐（flight_theme）还没收：下一个 fade_to / end_chapter 里淡掉
var ff_stop := false                 # 跳节拍时目标 flag 一设上、那个 scene 播完就停（flight1 一路 goto 到底，不停会跳过头）
var ff_resume := ""                  # 停下的地方：接下来该播的 scene（关卡跳完以后正常播）


func _end_chapter() -> void:
	_ship_music_hold = false
	# 全剧终以后要放制作人员：主题曲从这里就淡进来，和正在淡掉的引擎声交叉，一路垫过结束卡接到名单（11-05 qa_audio：结束卡 8 秒真空）
	var roll_music: bool = not ff and float(level.get("_fuzz")) <= 0.0 \
		and (load("res://scripts/chapter_flow.gd") as GDScript).info(str(level.chapter)).get("last_card", false)
	if roll_music:
		BGM_GD.get_bgm(level.get_tree()).play("theme", NAN, 2.0)
	else:
		BGM_GD.get_bgm(level.get_tree()).stop(2.0)
	if ff:
		ff_hit_end = true
		return
	ended = true
	dlg.close_box()
	await level.story_takeoff()
	if level.chapter_next():
		# 接下一章（森林起飞 → 驾驶舱）：关卡带着状态重新载入，不出结束卡
		if auto != "":
			print_stats("STORY_DONE")
		return
	# 最后一章（chapter_flow 的 last_card）：「全剧终」，3 秒以后按任意键回标题（level_forest 的结束卡输入）；别的：「未完待续」
	var last: bool = (load("res://scripts/chapter_flow.gd") as GDScript).info(str(level.chapter)).get("last_card", false)
	var roll: bool = last and float(level.get("_fuzz")) <= 0.0      # 全剧终以后放制作人员、放完自己回标题（乱玩不放：走到结束卡就算完）
	var top: Node = level.get_node("Top")
	var n0 := top.get_child_count()                                     # 结束卡、成就那行是这之后加进 Top 的（放名单前要收掉）
	dlg.end_card(I18n.t("the_end" if last else "to_be_continued"), I18n.t("the_end_sub" if last else "to_be_continued_sub"),
		level.get_node("Top"), I18n.t("end_any_key") if last and not roll else "")
	print("END_CARD %s" % ("the_end" if last else "to_be_continued"))   # 自测：连着自动玩到最后，确认出的是「全剧终」
	if last:
		barter.show_achievements(level.get_node("Top"))     # 成就：只列拿到的（以物易物，data/achievements.json）
	if auto != "":
		await _wait(2.5)
		if shots_dir != "":
			level._save(shots_dir.path_join("%03d_end_card.png" % (_shot_n + 1)))
		print_stats("STORY_DONE")
		if not roll:
			get_tree().quit()
	if roll:
		await _credits_roll(top.get_children().slice(n0))


## 「全剧终」停一会儿以后放制作人员（scripts/credits_page.gd 的 from_end：和标题页「制作人员」同一套分场景名单，
## 从结束卡淡进去，「感谢游玩」以后淡到黑），放完回标题（level_forest.title_after_credits：重新载入，标题从黑里淡出来）。
## 放的时候按键都给名单页（level_forest 的 _input 先看 _credits_page；Esc = 直接淡到黑回标题）；结束卡自己不再等按键。
## cards = 结束卡（全剧终）和成就那行：名单淡进来之前先淡到透明（底下是黑的）、删掉，两层字不同时出现（11-05 qa_all 报了叠字）。
func _credits_roll(cards: Array) -> void:
	level.set("_end_t", -100.0)
	await level.get_tree().create_timer(2.5 if auto != "" else 4.5, false).timeout
	if not is_instance_valid(level):
		return
	var out := level.create_tween().set_parallel(true)
	out.tween_interval(1.2)                                               # 至少有一个动作（不然空 tween 不会 finished）
	for c in cards:
		if is_instance_valid(c) and c is CanvasItem:
			out.tween_property(c, "modulate:a", 0.0, 1.2).set_trans(Tween.TRANS_SINE)
	await out.finished
	for c in cards:
		if is_instance_valid(c):
			c.queue_free()
	await level.get_tree().create_timer(0.4, false).timeout                      # 黑一小会儿，再出森林
	if not is_instance_valid(level):
		return
	var page: Control = (load("res://scripts/credits_page.gd") as GDScript).new()
	page.set("from_end", true)
	level.get_node("Top").add_child(page)
	level.set("_credits_page", page)
	await page.closed
	if is_instance_valid(level):
		print("CREDITS_DONE black_frames=%d" % int(page.get("black_frames")))
		level.title_after_credits()          # _credits_page 不清：重新载入前按键照样被名单页吃掉


# ======================================================================= hotspot
## 鹿带路：晨走到等着的鹿身边了，接着播停下的那段
func guide_ready() -> bool:
	if pending_guide.is_empty() or busy or not pending_guide.has("scene"):
		return false
	return not _deer_moving() and absf(chen.position.x - deer.position.x) <= GUIDE_NEAR and world.room == "forest"


func resume_guide() -> void:
	var p := pending_guide
	pending_guide = {}
	chen._set_facing(1 if deer.position.x > chen.position.x else -1)
	await play(str(p["scene"]), true, int(p["index"]))


## 主线下一个该去的地方：{x, kind, id}（等人的鹿 > 木头 > 会推进剧情的点，先不去换地方的，再按远近）；没有 = {}
func main_target() -> Dictionary:
	if not pending_guide.is_empty() and deer.visible:
		return {"x": deer.position.x, "kind": "guide", "id": "guide"}
	if level.wood_available():
		return {"x": level.WOOD_X, "kind": "wood", "id": "wood"}
	var best: Dictionary = {}
	var bk := INF
	for p in hotspots.available():
		var h: Dictionary = p["h"]
		if hotspots.is_enter(h) or not is_progress_hotspot(h) or h.has("_side"):
			continue                                   # 支线不算主线下一步（不画屏幕边的小箭头）
		var k := absf(float(p["x"]) - chen.position.x) + (5000.0 if _exits(str(h.get("scene", ""))) else 0.0)
		if k < bk:
			bk = k
			best = {"x": float(p["x"]), "kind": "hotspot", "id": str(h.get("id", ""))}
	return best


## 卡在一个地方太久：晨小声自言自语一句（剧本 nudge_<id> 的第一句台词；没有就不说）
func _update_nudge(delta: float) -> void:
	if busy or not level.free_play() or auto != "":
		_nudge_t = 0.0
		return
	if StoryState.progress() != _nudge_progress:
		_nudge_progress = StoryState.progress()
		_nudge_t = 0.0
		_nudged.clear()
		return
	_nudge_t += delta
	if _nudge_t < NUDGE_AFTER:
		return
	_nudge_t = NUDGE_AFTER - NUDGE_EVERY
	var hl := _hint_line()
	if not hl.is_empty():
		var key := "hint:" + str(hl.get("zh", ""))
		if not _nudged.has(key):
			_nudged[key] = true
			var who := str(hl.get("who", "chen"))
			var tl := txt_lang(hl)
			dlg.murmur(txt_in(speakers.get(who, who), str(tl[1])), NAME_COLORS.get(who, UITheme.ACCENT), str(tl[0]),
				_anchor.bind(who), bool(hl.get("added", false)) and mark_added)
		return
	var t := main_target()
	if t.is_empty():
		return
	var sid := "nudge_" + str(t["id"])
	if not scenes.has(sid) or _nudged.has(sid):
		return
	_nudged[sid] = true
	for st in scenes[sid]:
		if st is Dictionary and st.has("say"):
			var who := str(st["say"])
			var tl := txt_lang(st)
			dlg.murmur(txt_in(speakers.get(who, who), str(tl[1])), NAME_COLORS.get(who, UITheme.ACCENT), str(tl[0]),
				_anchor.bind(who), bool(st.get("added", false)) and mark_added)
			break


## 跳节拍跳到了最后（launched）：直接播起飞和结束卡
func play_end() -> void:
	busy = true
	level.story_begin(true)
	await _end_chapter()


## 晨按了互动（或自动玩走到了）：播它的 scene
func trigger(p: Dictionary) -> void:
	if free_roam:
		return
	var h: Dictionary = p["h"]
	if not ff and quick.is_quick(h):
		await quick.pickup(p)           # 走过去就捡：不锁人
		return
	var id := str(h.get("id", ""))
	var pet := str(h.get("pet", {"deer": "deer", "miluo": "miluo", "glade_toucan": "toucan"}.get(str(h.get("at", "")), "")))
	if level.chapter == "forest" and not ff and auto == "" and pet != "" and not hotspots.is_enter(h):
		if await _pet_menu(pet, h):
			return
	var barks := _bark_only(str(h.get("scene", "")))
	if not barks.is_empty() and bark.busy() and _bark_hot == id:
		bark.skip()                         # 同一个点的那句还飘着，又按了一下：收掉，不再叠一遍（作者「对话框消不掉」）
		return
	if not barks.is_empty():
		_bark_hot = id
		if h.get("once", false):
			StoryState.mark_used(id)
		# 只浮一句（飞船上方）：不锁人、不停游戏
		_visited[id] = StoryState.progress()
		hotspots_used += 1
		_on_scene(str(h.get("scene", "")))
		if not ff:
			hotspots.pressed(p)
			_bark_at = float(p["x"])
			_bark_y = float(h.get("bark_y", 46.0))
			for b in barks:
				_say(b)
		return
	if h.get("nolock", false):
		# 走进去不锁人：边跑边播（奔跑片头：字幕、潜意识字、镜头拉近）
		StoryState.mark_used(id)
		_visited[id] = StoryState.progress()
		hotspots_used += 1
		var ns := str(h.get("scene", ""))
		_on_scene(ns)
		for st0 in scenes.get(ns, []):
			if st0 is Dictionary:
				await _step(st0)
		return
	if h.get("once", false):
		StoryState.mark_used(id)
	_visited[id] = StoryState.progress()
	var p0 := StoryState.progress()
	hotspots_used += 1
	await _lv_reach(p)                      # 多层小屋：点的是别的层的东西，先走上 / 下去
	if not ff and absf(float(p["x"]) - chen.position.x) > 2.0:
		chen._set_facing(1 if float(p["x"]) > chen.position.x else -1)
	_enter_scene = hotspots.is_enter(h) and not bool(h.get("cutscene", false))
	var scene := str(h.get("scene", ""))
	if scene == "" and h.has("closeup"):
		busy = true
		hotspots.active = false
		if not ff:
			level.story_begin(false)
			await closeup({"img": str(h["closeup"])})
			level.story_end()
		busy = false
		hotspots.active = true
		return
	var acc: Dictionary = h.get("accepts", {})
	if not acc.is_empty() and not _enter_scene and not _owned_accepted(acc).is_empty():
		# 背包里有它能接受的东西：先弹道具选择条
		busy = true
		hotspots.active = false
		if not ff:
			level.story_begin(false)
		_ui_shot("items", 0.35)
		var it: String = await dlg.choose_item(_bag_items(), I18n.t("just_look"), _auto_item_index(acc))
		busy = false
		if it != "":
			scene = str(acc.get(it, acc.get("_default", "")))
			if scene.begins_with("__mech:"):
				_mech_resolve(scene.trim_prefix("__mech:").split("|")[0], it)
				return
			if scene == "":
				await _engine_line(I18n.t("use_nothing"))
				if not ff:
					level.story_end()
				_visited[id] = StoryState.progress()
				return
	if h.has("_mech"):
		_mech_resolve(str(h["_mech"]), "")       # 小游戏的临时点：不播 scene，告诉等着的小游戏
		return
	_scene_view = _hotspot_view(h) if not ff else ""
	await play(scene, not ff)
	_scene_view = ""
	_enter_scene = false
	_visited[id] = StoryState.progress()
	_visit_gain[id] = StoryState.progress() - p0


func _pet_menu(who: String, h: Dictionary) -> bool:
	var n := npc(who)
	if n == null or not n.visible:
		return false
	busy = true
	hotspots.active = false
	level.story_begin(false)
	var options := [I18n.t("pet"), I18n.t("just_look")] if h.get("pet_only", false) else [I18n.t("talk"), I18n.t("pet")]
	var choice: int = await dlg.choose_line(options)
	if choice == (0 if h.get("pet_only", false) else 1):
		chen._set_facing(1 if n.position.x > chen.position.x else -1)
		chen.spr.play(&"reach")
		var response := {"zh": "嘿嘿。", "en": "Hehe."}
		match who:
			"deer":
				response = {"zh": "妈妈，再摸一下嘛。", "en": "One more time, Mom."} if StoryState.has("c1_mom") else {"zh": "乖孩子，轻一点。", "en": "Easy, kiddo. Be gentle."}
			"miluo":
				response = {"zh": "轻点，我可不是绒毛玩偶。", "en": "Easy. I'm no stuffed toy."}
			"toucan":
				response = {"zh": "翅膀可以，别碰喙。", "en": "The wing's fine. Mind the beak."}
			"rabbit", "rabbit_doe":
				response = {"zh": "小心，耳朵怕痒。", "en": "Careful. My ears are ticklish."}
			_:
				n.hop()
		response["say"] = who if not who.begins_with("rabbit_kit_") else "chen"
		if who.begins_with("rabbit_kit_"):
			response = {"say": "chen", "zh": "好软。", "en": "So soft."}
		await _say(response)
		dlg.close_box()
	busy = false
	level.story_end()
	return h.get("pet_only", false) or choice != 0


## 背包里选中一件按「使用」：用在晨身边那个 hotspot 上
func use_item(item: String) -> void:
	if busy:
		return
	var p: Dictionary = hotspots.nearest(chen.position.x)
	if p.is_empty():
		busy = true
		level.story_begin(false)
		await _engine_line(I18n.t("use_here_nothing"))
		busy = false
		level.story_end()
		return
	var h: Dictionary = p["h"]
	var acc: Dictionary = h.get("accepts", {})
	var scene := str(acc.get(item, acc.get("_default", "")))
	if scene.begins_with("__mech:"):
		hotspots.pressed(p)
		_mech_resolve(scene.trim_prefix("__mech:").split("|")[0], item)
		return
	hotspots.pressed(p)
	chen._set_facing(1 if float(p["x"]) > chen.position.x else -1)
	if scene == "":
		busy = true
		level.story_begin(false)
		await _engine_line(I18n.t("use_nothing"))
		busy = false
		level.story_end()
		return
	_visited[str(h.get("id", ""))] = StoryState.progress()
	await play(scene)


## 换区域（树屋段 ↔ 旧路段的入口）：黑屏换过去。给了 from：晨先站在 from（那一段的入口边上），淡入的同时走几步到 x（到达）
func portal_to(x: float, from := NAN) -> void:
	if busy:
		return
	busy = true
	hotspots.active = false
	level.story_begin(false)
	await level.fade_to_black(0.45)
	_teleport("forest", x if is_nan(from) else from, [], true)
	await _wait(0.2)
	if is_nan(from):
		await level.fade_from_black(0.45)
	else:
		await _arrive_walk(x)
	busy = false
	level.story_end()


## 坠毁后飞船里断续的警报：开着（开场起）/ 晨第一次修飞船或捡到木头以后淡掉
var _alarm_on := false


func alarm(on: bool) -> void:
	if ff or on == _alarm_on:
		return
	_alarm_on = on
	_ambient_step({"name": "alarm_broken", "at": "wreck", "on": on, "db": -8.0})


## 引擎自己的一句（晨说）：道具用不上之类
func _engine_line(text: String) -> void:
	if ff:
		return
	await dlg.say(txt(speakers.get("chen", "chen")), NAME_COLORS["chen"], text, _anchor.bind("chen"))


## accepts 里背包现在有的东西
func _owned_accepted(acc: Dictionary) -> Array:
	var out: Array = []
	for k in acc:
		if str(k) != "_default" and Inventory.has(str(k)):
			out.append(str(k))
	return out


## 道具选择条里列的东西：背包里除了日记的全部
func _bag_items() -> Array:
	var out: Array = []
	for id in Inventory.owned:
		if str(id) == "journal":
			continue
		out.append({"id": str(id), "icon": Inventory.icon(str(id)), "name": txt(Inventory.item(str(id)).get("name", id))})
	return out


## 自动玩 / 跳节拍：用能推进剧情的那件（没有就第一件能接受的）；手动玩 = -1
func _auto_item_index(acc: Dictionary) -> int:
	if auto == "" and not ff:
		return -1
	var items := _bag_items()
	if ff and _ff_target != "":
		for i in items.size():
			var iid := str(items[i]["id"])
			if acc.has(iid) and _leads_to(str(acc[iid]), _ff_target):
				return i
	if auto == "full" and not ff:
		# 全覆盖：先试一次用错的东西（看 _default 的反应）
		for i in items.size():
			var key := "wrongitem:" + str(acc.get("_default", "")) 
			if not acc.has(str(items[i]["id"])) and not _wrong_tried.has(key):
				_wrong_tried[key] = true
				return i
	var best := -1
	for i in items.size():
		var id := str(items[i]["id"])
		if acc.has(id):
			if best < 0:
				best = i
			if _would_progress(str(acc[id]), {}):
				return i
	return best if best >= 0 else items.size()


## 对话选项：晨把选中的那句说出来，再跳到它的 scene
func _choice(st: Dictionary) -> String:
	var opts: Array = []
	for o0 in st.get("options", []):
		if o0 is Dictionary and StoryState.all_of(o0.get("need", [])) and StoryState.none_of(o0.get("not", [])):
			opts.append(o0)                  # 选项带 need / not：按 flag 显示（第一关：按亲情关系）
	if opts.is_empty():
		return ""
	var lines: Array = []
	for o in opts:
		lines.append(txt(o))
	var ai := -1
	if auto != "" or ff:
		ai = 0
		if ff and _ff_target != "":
			for i in opts.size():
				var os := str(opts[i].get("scene", ""))
				if _leads_to(os, _ff_target) and not _loops_back(os, _cur_scene):
					ai = i
					break
		if auto == "full" and not ff:
			for i in opts.size():
				var key := _cur_scene + ":c" + str(i)
				if not _wrong_tried.has(key) and not played.has(str(opts[i].get("scene", ""))):
					_wrong_tried[key] = true
					ai = i
					break
		var to := _auto_to()
		if to != "" and not ff:
			for i in opts.size():
				if _leads_to(str(opts[i].get("scene", "")), to):
					ai = i                       # --auto_to=：对话选项也挑走下去会设这个 flag 的那句（第一关：c1_child）
					break
	_ui_shot("choice", 0.35)
	var i: int = await dlg.choose_line(lines, ai)
	i = clampi(i, 0, opts.size() - 1)
	var o: Dictionary = opts[i]
	lines_said(o)
	if not ff:
		var tl := txt_lang(o)
		await dlg.say(txt_in(speakers.get("chen", "chen"), str(tl[1])), NAME_COLORS["chen"], str(tl[0]), _anchor.bind("chen"),
			bool(o.get("added", false)) and mark_added, clampf(float(txt_in(o, "zh").length()) / dlg.CPS_ZH, 0.25, 4.0),
			txt_in(o, "en" if I18n.is_zh() else "zh"))
	return str(o.get("scene", ""))


func lines_said(_o: Dictionary) -> void:
	lines += 1


## 远处有东西走过：树冠依次晃 + 低鸣 + 树冠摇的声音左右推过去 + 镜头停住 + 晨抬头
func _elephant_call(st: Dictionary) -> void:
	if ff:
		return
	var v := int(st.get("variant", 1))
	var dir := 1 if v != 2 else -1
	var dur := 3.4
	world.sway_canopy(dir, dur)
	_ui_shot("elephant", 1.5)
	level.cam_hold(dur + 0.8)
	_sfx({"name": "elephant_call_%d" % v})
	var p := _sfx_path("tree_sway")
	if p != "":
		var a := AudioStreamPlayer2D.new()
		a.stream = load(p)
		a.bus = "SFX"
		a.max_distance = 2000.0
		a.attenuation = 0.5
		a.volume_db = -4.0
		level.add_child(a)
		var left: Vector2 = level.cam_left()
		var y := left.y + 135.0
		a.global_position = Vector2(left.x + 240.0 - dir * 320.0, y)
		a.play()
		a.finished.connect(a.queue_free)
		create_tween().tween_property(a, "global_position:x", left.x + 240.0 + dir * 320.0, dur)
	else:
		missing_sfx["tree_sway"] = true
	if chen.spr.sprite_frames.has_animation(&"idle_eye") and chen._vel <= 0.0:
		chen.spr.play(&"idle_eye")
	await _wait(dur + 0.4)


## 树冠缺口那一屏淡入、画上的弧线叠上去对齐、停一下、淡出回到森林
func _treeline_match() -> void:
	if not world.has_treeline_view():
		return
	await world.treeline_view_in(0.9 if auto == "" else 0.4)
	await _wait(0.6 if auto == "" else 0.2)
	var dur: float = world.match_arc(1.8 if auto == "" else 0.8)
	_ui_shot("arc", 0.9)
	await _wait(dur + 0.3)
	await world.treeline_view_out(0.9 if auto == "" else 0.4)
	await _wait(0.3)


## 这个 hotspot 的 scene 要不要在树冠缺口那一屏上播
func _hotspot_view(h: Dictionary) -> String:
	return str(h.get("view", "treeline" if str(h.get("at", "")) == "treeline_gap" else ""))


## 左上角的当前目标：第一个满足条件的 objectives 条目；没有就 {}
func objective() -> Dictionary:
	for o in data.get("objectives", []):
		if o is Dictionary and StoryState.all_of(o.get("need", [])) and StoryState.none_of(o.get("not", [])):
			return o
	return {}


## 闲着太久时晨自言自语的那句：顶层 hints 按 flag 挑
func _hint_line() -> Dictionary:
	var hs = data.get("hints", null)
	if hs == null:
		return {}
	var order := StoryState.flag_order
	var best: Dictionary = {}
	var best_rank := -2
	if hs is Dictionary:
		for f in hs:
			var rank := order.find(str(f))
			if rank < 0 or rank <= best_rank:
				continue
			var v = hs[f]
			var cand: Dictionary = (v[randi() % (v as Array).size()] if v is Array and not (v as Array).is_empty() else v) if (v is Array or v is Dictionary) else {}
			if not cand.is_empty():
				best = cand
				best_rank = rank
	elif hs is Array:
		for e in hs:
			if not e is Dictionary:
				continue
			var ed: Dictionary = e
			if ed.has("flag") and not StoryState.has(str(ed["flag"])):
				continue
			if not StoryState.all_of(ed.get("need", [])) or not StoryState.none_of(ed.get("not", [])):
				continue
			var rank := order.find(str(ed.get("flag", ""))) if ed.has("flag") else -1
			if rank >= best_rank:
				best = ed
				best_rank = rank
	return _hint_pick(best)


## 三章的 hints 都是一条带 "lines": [{zh, en, added?, who?}…]：挑第一句这轮还没说过的；都说过了 = 没有（再去找 nudge_ scene）。
## 没有 lines 的（老写法，zh / en 直接写在条目上）原样返回
func _hint_pick(e: Dictionary) -> Dictionary:
	var ls = e.get("lines", null)
	if not ls is Array:
		return e
	for l in ls:
		if l is Dictionary and not _nudged.has("hint:" + str(l.get("zh", ""))):
			return l
	return {}


## 这个 hotspot 现在去了会不会推进（设新 flag、给新东西、换地方、结束、换物件状态）
func is_progress_hotspot(h: Dictionary) -> bool:
	if _would_progress(str(h.get("scene", "")), {}):
		return true
	var acc: Dictionary = h.get("accepts", {})
	for k in acc:
		if str(k) != "_default" and Inventory.has(str(k)) and _would_progress(str(acc[k]), {}):
			return true
	return false


func _would_progress(s: String, seen: Dictionary) -> bool:
	if seen.has(s) or not scenes.has(s):
		return false
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		match str(st.get("do", "")):
			"flag":
				if st.has("set") and not StoryState.has(str(st["set"])):
					return true
			"give":
				if not Inventory.has(str(st.get("item", ""))):
					return true
			"fade_to", "end_chapter":
				return true
			"goto":
				if _would_progress(str(st.get("scene", "")), seen):
					return true
			"if":
				if _would_progress(str(st.get("then", "")), seen) or _would_progress(str(st.get("else", "")), seen):
					return true
			"choice":
				for o in st.get("options", []):
					if _would_progress(str(o.get("scene", "")), seen):
						return true
			"count":
				if st.has("set") and not StoryState.has(str(st["set"])):
					return true
			"pick":
				for o in st.get("options", []):
					if _would_progress(str(o.get("scene", "")), seen):
						return true
			"keepsake_choice":
				for v in (st.get("scenes", {}) as Dictionary).values():
					if _would_progress(str(v), seen):
						return true
			"mechanic":
				if not bool(mech_load(str(st.get("id", ""))).get("_done", false)):
					return true
				for f in st.get("sets", []):
					if not StoryState.has(str(f)):
						return true
			"closeup":
				for z in st.get("zones", []):
					if _would_progress(str(z.get("scene", "")), seen):
						return true
	return false


## 走进 trigger:"enter" 的点能连着播到的 scene（不推人的检查用）：闪回以后的不算（晨晕过去、醒在别处，不再是走到边上的那一刻）
func _reach_enter(s: String, seen: Dictionary) -> Array:
	if seen.has(s) or not scenes.has(s):
		return seen.keys()
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		match str(st.get("do", "")):
			"flashback":
				break
			"goto":
				_reach_enter(str(st.get("scene", "")), seen)
			"if":
				_reach_enter(str(st.get("then", "")), seen)
				_reach_enter(str(st.get("else", "")), seen)
			"pick", "choice":
				for o in st.get("options", []):
					_reach_enter(str(o.get("scene", "")), seen)
	return seen.keys()


## 从 s 出发 goto / if / pick 能到的所有 scene
func _reach(s: String, seen: Dictionary) -> Array:
	if seen.has(s) or not scenes.has(s):
		return seen.keys()
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		match str(st.get("do", "")):
			"goto":
				_reach(str(st.get("scene", "")), seen)
			"if":
				_reach(str(st.get("then", "")), seen)
				_reach(str(st.get("else", "")), seen)
			"pick", "choice":
				for o in st.get("options", []):
					_reach(str(o.get("scene", "")), seen)
			"keepsake_choice":
				for v in (st.get("scenes", {}) as Dictionary).values():
					_reach(str(v), seen)
			"closeup":
				for z in st.get("zones", []):
					_reach(str(z.get("scene", "")), seen)
	return seen.keys()


func _exits(s: String, seen := {}) -> bool:
	if seen.has(s) or not scenes.has(s):
		return false
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		var d := str(st.get("do", ""))
		if d in ["fade_to", "end_chapter"]:
			return true
		if d == "goto" and _exits(str(st.get("scene", "")), seen):
			return true
		if d == "if" and (_exits(str(st.get("then", "")), seen) or _exits(str(st.get("else", "")), seen)):
			return true
	return false


# ======================================================================= 自动玩 / 跳节拍
## 下一个该去的地方：{kind: "wood"|"hotspot", x, p}；空 = 没有
func plan() -> Dictionary:
	var vw := pending_view()
	if not vw.is_empty():
		return {"kind": "view", "x": chen.position.x, "scene": vw["scene"], "exit": false}   # 背包里该看的东西（大象的画）：直接看
	var cands: Array = []
	if level.wood_available():
		cands.append({"kind": "wood", "x": level.WOOD_X, "exit": false})
	for p in hotspots.available():
		var h: Dictionary = p["h"]
		var id := str(h.get("id", ""))
		if _visited.has(id) and int(_visited[id]) == StoryState.progress() \
				and not (not world.stages.is_empty() and int(_visit_gain.get(id, 0)) > 0 and is_progress_hotspot(h)):
			continue                                   # 上次来过以后没有新进展：不再来（多房间章节：上次点它有进展、还会有进展的可以接着点）
		if _unreach.has(id) and int(_unreach[id]) == StoryState.progress():
			continue                                   # 刚才够不着
		var prog := is_progress_hotspot(h)
		var to_target := ff and _ff_target != "" and _leads_to(str(h.get("scene", "")), _ff_target)
		if h.has("_side") and not to_target and not (side_auto() and not ff) and not (ff and _side_target()):
			continue                                   # 支线点：--main_only 时自动玩不去；跳节拍只去通向目标的
		if to_target:
			prog = true
		if not prog:
			if auto != "full" or ff or _visited.has(id):
				continue
		cands.append({"kind": "hotspot", "x": float(p["x"]), "p": p, "exit": _exits(str(h.get("scene", ""))) and not to_target, "prog": prog,
			"target": to_target, "side": h.has("_side") and (not ff or _side_target())})
	if not world.stages.is_empty():
		var stay := false
		for c in cands:
			if not c["exit"] or c.get("target", false):
				stay = true
		if not stay:
			var mp := _multi_plan()
			if not mp.is_empty():
				return mp
	if cands.is_empty():
		return {}
	var cx := chen.position.x
	var full := auto == "full" and not ff
	cands.sort_custom(func(a, b):
		if a.get("target", false) != b.get("target", false):
			return a.get("target", false)
		if a.get("side", false) != b.get("side", false):
			return a.get("side", false)                # 支线先做（不然主线一推进，窗口就关了）
		if a["exit"] != b["exit"]:
			return not a["exit"]
		# full：同一片先把闲聊都听一遍，再去推进剧情的点
		if full and a.get("prog", true) != b.get("prog", true):
			return not a.get("prog", true)
		return absf(float(a["x"]) - cx) < absf(float(b["x"]) - cx))
	return cands[0]


func _process(delta: float) -> void:
	_game_t += delta
	step_t += delta
	_update_item_show(delta)
	_update_miluo_layer()
	if world.is_stage(world.room) and (deer.visible or miluo.visible):
		deer.visible = false               # 鹿、弥洛是森林的节点：多房间章节（河流篇）里一律不显示
		miluo.visible = false              # （10-30 作者：旧街水里站着一只第一章的鹿）
	_update_follow(delta)
	_no_snap()
	if _overlap_log and not ff:
		_check_overlap()
	if (_jump_log or _qa_live) and not ff:
		_check_jumps()
	if _alarm_on and (StoryState.has("tried_parts") or StoryState.has("got_wood") or StoryState.has("c1_run")):
		alarm(false)
	if not is_nan(_bark_at) and not bark.busy():
		_bark_at = NAN
	_update_one_way(delta)
	if _burst_dir != "":
		_burst_tick()
	if not ended and not ff and not free_roam:
		_update_nudge(delta)
		if guide_ready() and level.free_play():
			resume_guide()
			return
	if auto == "" or ended or ff:
		return
	dlg.auto_delay = AUTO_LINE
	if busy:
		_idle_t = 0.0
		_target = {}                 # 剧情开始了（可能是路上踩到的 trigger:"enter"）：播完重新规划
		return
	if not level.free_play():
		_idle_t = 0.0
		_target = {}
		return
	if _target.is_empty() and not pending_guide.is_empty():
		# 鹿在前面等：走过去（走近了 _process 开头会接着播）
		var gx := deer.position.x - signf(deer.position.x - chen.position.x) * 30.0
		if not level.walking() and absf(chen.position.x - deer.position.x) > GUIDE_NEAR - 10.0:
			level.walk_to(gx)
		_idle_t = 0.0
		return
	if _target.is_empty():
		_target = plan()
		_target_t = 0.0
		if not _target.is_empty() and _target["kind"] == "view":
			var vs := str(_target["scene"])
			_target = {}
			play(vs)
			return
		if not _target.is_empty():
			_target_limit = 8.0 + absf(float(_target["x"]) - chen.position.x) / 90.0
		if not _target.is_empty():
			level.walk_to(float(_target["x"]))
	if _target.is_empty():
		_idle_t += delta
		if _idle_t > 8.0 and pending_guide.is_empty():
			print_stats("STORY_STUCK")
			get_tree().quit(1)
		return
	_idle_t = 0.0
	var tx := float(_target["x"])
	if _target["kind"] == "wood":
		if not level.wood_available():
			_target = {}
		elif absf(chen.position.x - tx) > 30.0 and not level.walking():
			level.walk_to(tx)
		return
	# 走到「站得到的那一点」（被看得见的边挡住就站在边上）；到了在范围里就互动，够不着就先记下、等有进展再来
	_target_t += delta
	var p: Dictionary = _target["p"]
	var h: Dictionary = p["h"]
	if not world.in_room() and world.area_of(tx) != world.area_of(chen.position.x) and _target_t < _target_limit:
		# 在另一段：有走得过去的入口（树屋段往左 = house_return）就一直往那边走；没有就先去「能换过去」的那个点
		var to_area: String = world.area_of(tx)
		var walkable: bool = to_area == "road" and world.markers.has("house_return")
		if not walkable:
			var route := _route_to_area(to_area)
			if not route.is_empty():
				_target = {"kind": "hotspot", "x": float(route["x"]), "p": route, "exit": true}
				_target_t = 0.0
				return
		if not level.walking():
			level.walk_to(tx)
		return
	var lsg := _lv_stage()
	if lsg != null and hotspots.usable(h) and not hotspots.is_enter(h):
		var tlv := _lv_target(h.get("at", 0))
		if tlv >= 0 and tlv != int(lsg.chen_lv):
			# 多层小屋、点在别的层：直接点（trigger 里 _lv_reach 沿石阶走过去）。不能先在本层走到同一个 x 再看范围——
			# 本层的墙可能离那个 x 比互动范围还远（阁楼左墙 1452、楼下门 1408：停在 1458 够得着、1460 就永远够不着，链式自动玩卡死过）
			_target = {}
			trigger(p)
			return
	var at_n = h.get("at", 0)
	var pn: Node2D = npc(str(at_n)) if at_n is String else null
	if pn != null and pn != chen and npcs.values().has(pn) and not _is_body(pn):
		# 不占路的人（料理鼠妈）：站到她身子外面说话，别走到她身上（占路的人本来就被 KEEP_CLEAR 推开）
		tx = pn.position.x + (1.0 if chen.position.x >= pn.position.x else -1.0) * clear_dist(pn)
	var wl: Vector2 = world.walls(chen.position.x)
	var stand := clampf(tx, wl.x + 2.0, wl.y - 2.0)
	if (absf(chen.position.x - stand) <= 4.0 and chen._vel <= 0.0) or _target_t > _target_limit:
		_target = {}
		if hotspots.usable(h) and hotspots.in_range(p, chen.position.x) and not hotspots.is_enter(h):
			trigger(p)
		else:
			_unreach[str(h.get("id", ""))] = StoryState.progress()
	elif not level.walking():
		level.walk_to(stand)


## 这一段里能换到 to_area 那一段的点（scene 里 fade_to 到那一段的）
func _route_to_area(to_area: String) -> Dictionary:
	for p in hotspots.available():
		var h: Dictionary = p["h"]
		if hotspots.is_enter(h) or world.area_of(float(p["x"])) != world.area_of(chen.position.x):
			continue
		for sid in _reach(str(h.get("scene", "")), {}):
			for st in scenes.get(sid, []):
				if st is Dictionary and str(st.get("do", "")) == "fade_to" and str(st.get("room", "forest")) == "forest":
					var r: Dictionary = world.resolve(st.get("at", 0))
					if r["ok"] and world.area_of(float(r["x"])) == to_area:
						return p
	return {}


## 跳节拍：把剧情瞬间过一遍，直到 flag 设上（那个 scene 播完）。返回有没有到。
## 点选 / 对话选项 / 用道具 / 挑 hotspot 时，能通到「设这个 flag」的那条优先（支线上的 flag 也能跳）。
var _ff_target := ""
var _ff_log := "--ff_log" in OS.get_cmdline_user_args()


func fast_forward(target: String) -> bool:
	_ff_target = target
	ff = true
	dlg.instant = true
	var guard := 0
	while not StoryState.has(target) and guard < 400:
		guard += 1
		if pending_guide.has("scene") and not busy:
			# 11-05：F8 状态页原地补齐时剧情正停在鹿带路的半路（新版第一关「跟上我的步伐」）：晨直接到鹿身边，接着播停下的那段
			var gx: float = float(pending_guide.get("x", deer.position.x))
			_place(deer, gx, world.room)
			deer.visible = true
			_place(chen, gx - signf(gx - chen.position.x) * 30.0, world.room)
			await resume_guide()
			continue
		var c := plan()
		if c.is_empty():
			break
		if c["kind"] == "wood":
			await level.ff_take_wood()
		elif c["kind"] == "view":
			await play(str(c["scene"]))
		else:
			var p: Dictionary = c["p"]
			if _ff_log:
				print("FF %d %s x=%.0f room=%s" % [guard, str(p["h"].get("id", "")), float(p["x"]), world.room])
			_place(chen, float(p["x"]) - 12.0 * signf(float(p["x"]) - chen.position.x), world.room)
			await trigger(p)
	ff = false
	_ff_target = ""
	_visited.clear()                 # 跳完以后自动玩从头算「来过」
	dlg.instant = false
	return StoryState.has(target)


## 从 scene 出发能不能走到「设 flag」那一步
func _leads_to(s: String, flag: String) -> bool:
	if flag == "" or s == "":
		return false
	for sid in _reach(s, {}):
		for st in scenes.get(sid, []):
			if st is Dictionary and str(st.get("do", "")) in ["flag", "count"] and str(st.get("set", "")) == flag:
				return true
			if st is Dictionary and str(st.get("do", "")) == "mechanic" and (st.get("sets", []) as Array).has(flag):
				return true
	return false


## 等多久（10-30 作者：等 NPC / 晨自己走的时间整体太久、很不自由）：每段剧情里晨被锁着时，
## 等别人走路（npc）、剧本让晨自己走（chen）、干等（wait）各花了几秒。台词不算（自动玩的台词时长是假的）；小游戏、鹿带路不算（能自由动）。
var wait_stats := {}
const WAIT_SCALE := 0.6      # 剧本里 wait 的停顿统一乘这个（最短 0.3 秒）：节奏还在，只是不拖
const WALK_WAIT_MAX := 2.5   # 剧情里等一个人走路最多等几秒
const WALK_HURRY := 2.2      # 为了不超过上面那个时间，最多走快到平时的几倍


func _count_wait(scene: String, st: Dictionary, dt: float) -> void:
	if dt <= 0.05 or st.has("say") or st.has("narr"):
		return
	var d := str(st.get("do", ""))
	var k := ""
	match d:
		"walk":
			k = "chen" if str(st.get("who", "")) == "chen" else "npc"
		"wait":
			k = "wait"
		"pose", "fade_to", "anim":
			k = d
		_:
			return
	if not wait_stats.has(scene):
		wait_stats[scene] = {}
	wait_stats[scene][k] = float(wait_stats[scene].get(k, 0.0)) + dt


func print_wait_stats() -> void:
	var rows: Array = []
	var tot := {}
	for sc in wait_stats:
		var sum := 0.0
		for k in wait_stats[sc]:
			sum += float(wait_stats[sc][k])
			tot[k] = float(tot.get(k, 0.0)) + float(wait_stats[sc][k])
		rows.append([sum, sc])
	rows.sort_custom(func(a, b): return a[0] > b[0])
	var all := 0.0
	var parts: Array = []
	for k in tot:
		all += float(tot[k])
		parts.append("%s=%.1f" % [k, tot[k]])
	print("STORY_WAIT_TOTAL %.1fs %s" % [all, " ".join(parts)])
	for r in rows:
		if float(r[0]) < 2.0:
			break
		var ps: Array = []
		for k in wait_stats[r[1]]:
			ps.append("%s=%.1f" % [k, wait_stats[r[1]][k]])
		print("STORY_WAIT %5.1fs %s  %s" % [r[0], r[1], " ".join(ps)])


func print_stats(tag: String) -> void:
	print_wait_stats()
	var real := (Time.get_ticks_msec() - _t0_ms) / 1000.0
	var unplayed: Array = []
	for id in scenes:
		if not played.has(id):
			unplayed.append(id)
	print("%s story=%s scenes=%d/%d plays=%d lines=%d hotspots=%d game_time=%.1fs real_time=%.1fs" % [
		tag, path, played.size(), scenes.size(), played_order.size(), lines, hotspots_used, _game_t, real])
	print("STORY_FLAGS " + ", ".join(StoryState.flag_order))
	print("STORY_ITEMS " + ", ".join(Inventory.owned))
	print("STORY_UNPLAYED " + (", ".join(unplayed) if not unplayed.is_empty() else "(none)"))
	print("STORY_MISSING_SFX " + (", ".join(missing_sfx.keys()) if not missing_sfx.is_empty() else "(none)"))
	print("STORY_MISSING_ANIM " + (", ".join(missing_anims.keys()) if not missing_anims.is_empty() else "(none)"))
	if _qa_live:
		print("QA_MOTION_SUMMARY jump=%d camjump=%d propjump=%d proppop=%d popin=%d" % [int(qa_counts.get("jump", 0)),
			int(qa_counts.get("camjump", 0)), int(qa_counts.get("propjump", 0)), int(qa_counts.get("proppop", 0)), int(qa_counts.get("popin", 0))])
	if tag == "STORY_STUCK":
		var av: Array = []
		for p in hotspots.available():
			av.append(str(p["h"]["id"]))
		print("STORY_STUCK_AT x=%.0f room=%s available=%s" % [chen.position.x, world.room, ", ".join(av)])


# ======================================================================= 检查剧本
func validate() -> Array[String]:
	var out: Array[String] = []
	var set_flags := {}
	for f in ENGINE_FLAGS:
		set_flags[f] = true
	for f in StoryState.flag_order + carry_flags:
		set_flags[f] = true                # 前面章节带过来的（河流篇的 burned_* 是飞行一设的；carry_flags = 前面章节可能设的）
	var refs := {}
	if entry_scene != "":
		refs[entry_scene] = true
	for id in scenes:
		for st in scenes[id]:
			if st is Dictionary and str(st.get("do", "")) in ["flag", "count"] and st.has("set"):
				set_flags[str(st["set"])] = true
			if st is Dictionary and str(st.get("do", "")) == "burn_held":
				for f7 in st.get("items", []):
					set_flags["burned_" + str(f7)] = true
			if st is Dictionary and str(st.get("do", "")) == "mechanic":
				for f5 in st.get("sets", []):
					set_flags[str(f5)] = true
	for f6 in barter.flags():
		set_flags[str(f6)] = true
	for k in HOOKS:
		var h := hook(k)
		if h == "":
			out.append("info: 没有 %s 的对接 scene（%s），用关卡原来的" % [k, "/".join(HOOKS[k])])
		else:
			refs[h] = true
	var ids := {}
	for h in hotspot_defs:
		if not h is Dictionary:
			out.append("hotspot 不是对象：" + str(h))
			continue
		var hid := str(h.get("id", ""))
		if ids.has(hid):
			out.append("hotspot id 重复：" + hid)
		ids[hid] = true
		var at = h.get("at", null)
		if at == null or (at is String and npc(str(at)) == null and not world.has_marker(str(at)) and not str(at).is_valid_float()):
			out.append("hotspot %s：at 找不到 %s" % [hid, str(at)])
		if not str(h.get("room", "forest")) in ["forest", "treehouse"] and not (str(h.get("room", "")) == "cockpit" and world.cockpit != null) \
				and not world.is_stage(str(h.get("room", ""))):
			out.append("hotspot %s：room 只能是 forest / treehouse%s（%s）" % [hid, " / cockpit" if world.cockpit != null else "", h.get("room")])
		var sc := str(h.get("scene", ""))
		if not scenes.has(sc) and not (sc == "" and (h.has("closeup") or h.get("pet_only", false))):
			out.append("hotspot %s：没有 scene %s" % [hid, sc])
		refs[sc] = true
		for key in ["need", "not"]:
			for f in h.get(key, []):
				if not set_flags.has(str(f)):
					out.append("hotspot %s：%s 里的 flag %s 剧本里没有任何地方设" % [hid, key, f])
		if h.has("hide_after") and not set_flags.has(str(h["hide_after"])):
			out.append("hotspot %s：hide_after %s 没有地方设" % [hid, h["hide_after"]])
		if h.has("sprite") and not ResourceLoader.exists(str(h["sprite"])):
			out.append("info: hotspot %s 的图还没有（色块占位）：%s" % [hid, h["sprite"]])
		var acc = h.get("accepts", {})
		if not acc is Dictionary:
			out.append("hotspot %s：accepts 要是 {物品: scene}" % hid)
		else:
			for k in acc:
				var s3 := str(acc[k])
				refs[s3] = true
				if not scenes.has(s3):
					out.append("hotspot %s：accepts 的 %s → scene %s 不存在" % [hid, k, s3])
				if str(k) != "_default" and not Inventory.defined(str(k)):
					out.append("hotspot %s：accepts 的物品 %s 不在物品表" % [hid, k])
	for id in scenes:
		var arr = scenes[id]
		if not arr is Array:
			out.append("scene %s 不是数组" % id)
			continue
		for st in arr:
			if not st is Dictionary:
				out.append("scene %s：步骤不是对象 %s" % [id, str(st)])
				continue
			var kind := "say" if st.has("say") else ("narr" if st.has("narr") else str(st.get("do", "")))
			if not kind in STEPS and not COCKPIT_STEPS.has(kind):
				out.append("scene %s：不支持的步骤 %s" % [id, JSON.stringify(st)])
				continue
			if COCKPIT_STEPS.has(kind):
				out.append_array(_validate_cockpit(str(id), kind, st, refs))
				continue
			match kind:
				"say":
					var who := str(st["say"])
					if not speakers.has(who):
						out.append("scene %s：说话人 %s 不在 speakers 里" % [id, who])
					if str(st.get("zh", "")) == "":
						out.append("scene %s：%s 的台词没有 zh" % [id, who])
				"narr":
					if not st["narr"] is Dictionary or str(st["narr"].get("zh", "")) == "":
						out.append("scene %s：narr 没有 zh" % id)
				"cycle":
					if str(st.get("id", "")) == "" or (st.get("lines", []) as Array).is_empty():
						out.append("scene %s：cycle 要有 id 和 lines" % id)
					for l5 in st.get("lines", []):
						if not l5 is Dictionary or not l5.has("say") or str(l5.get("zh", "")) == "" or str(l5.get("en", "")) == "":
							out.append("scene %s：cycle 的一句要有 say / zh / en：%s" % [id, str(l5)])
						elif not speakers.has(str(l5["say"])):
							out.append("scene %s：cycle 的说话人 %s 不在 speakers 里" % [id, l5["say"]])
				"walk", "face":
					var who := str(st.get("who", "chen"))
					if npc(who) == null:
						out.append("scene %s：%s 的 who 不认识 %s" % [id, kind, who])
					var to = st.get("to", null)
					if to == null or (to is String and npc(str(to)) == null and not world.has_marker(str(to)) and not str(to).is_valid_float()):
						out.append("scene %s：%s 的 to 找不到 %s" % [id, kind, str(to)])
				"show", "hide":
					var who := str(st.get("who", ""))
					if npc(who) == null and not world.props.has(who):
						out.append("scene %s：%s 的 who 不认识 %s" % [id, kind, who])
					if st.has("at") and not world.has_marker(str(st["at"])) and not str(st["at"]).is_valid_float():
						out.append("scene %s：%s 的 at 找不到 %s" % [id, kind, st["at"]])
				"give", "take":
					for item in (st.get("items", []) if kind == "give" and st.has("items") else [str(st.get("item", ""))]):
						if not Inventory.defined(str(item)):
							out.append("scene %s：物品 %s 不在 items.json（也不在剧本 items 里）" % [id, item])
				"journal":
					if str(st.get("zh", "")) == "":
						out.append("scene %s：journal 没有 zh" % id)
				"sfx", "ambient":
					var nm := str(st.get("name", ""))
					if _sfx_path(nm) == "":
						missing_sfx[nm] = true
					if kind == "ambient" and not world.has_marker(str(st.get("at", ""))):
						out.append("scene %s：ambient 的 at 找不到 %s" % [id, st.get("at")])
				"show_item":
					if not Inventory.defined(str(st.get("item", ""))):
						out.append("scene %s：show_item 的物品 %s 不在物品表" % [id, st.get("item")])
				"choice":
					var copts: Array = st.get("options", [])
					if copts.size() < 2:
						out.append("scene %s：choice 至少要两个选项" % id)
					for o in copts:
						var s4 := str(o.get("scene", ""))
						if str(o.get("zh", "")) == "":
							out.append("scene %s：choice 选项没有 zh" % id)
						if s4 != "":
							refs[s4] = true
							if not scenes.has(s4):
								out.append("scene %s：choice 选项的 scene %s 不存在" % [id, s4])
				"count":
					if not st.has("set") or not st.has("flags"):
						out.append("scene %s：count 要有 flags 和 set" % id)
				"fuel":
					var known := ["do", "have", "need", "burn", "add", "sub", "need_held", "plus", "added", "_comment"]
					for k3 in st:
						if not str(k3) in known:
							out.append("scene %s：fuel 不认识 %s（有 have / need / burn / add / sub / need_held / plus）" % [id, k3])
					if st.has("burn") and (not Inventory.defined(str(st["burn"])) or fuel_of(str(st["burn"])) <= 0):
						out.append("scene %s：fuel 的 burn %s 不在物品表或没有 keepsake_burn / burn" % [id, st["burn"]])
				"journal_strike", "journal_mark":
					if str(st.get("match", "")) == "":
						out.append("scene %s：%s 没有 match" % [id, kind])
				"flashback":
					var fid := int(st.get("id", 0))
					if fid < 1 or fid > 4:
						out.append("scene %s：flashback 的 id 要是 1～4（%s）" % [id, st.get("id")])
					if not str(st.get("place", "street")) in ["street", "station"]:
						out.append("scene %s：flashback 的 place 只能是 street / station（都是闪回 1 那条城市街，scenes/city_test.tscn）（%s）" % [id, st.get("place")])
					if not str(st.get("end", "black")) in ["black", "door", "white", "still"]:
						out.append("scene %s：flashback 的 end 只能是 black / door / white / still（%s）" % [id, st.get("end")])
					for l in st.get("lines", []):
						if not l is Dictionary or str(l.get("zh", "")) == "":
							out.append("scene %s：flashback 的独白没有 zh" % id)
					for nm3 in FLASHBACK_GD.SOUNDS:
						if _sfx_path(nm3) == "":
							missing_sfx[nm3] = true
					if bool(st.get("hold", false)):
						var woke := false
						for st3 in arr.slice(arr.find(st) + 1):
							if st3 is Dictionary and str(st3.get("do", "")) == "flashback_wake":
								woke = true
						if not woke:
							out.append("scene %s：flashback %d 写了 hold，后面没有 flashback_wake（会播完这段才醒）" % [id, fid])
				"elephant_call":
					var nm2 := "elephant_call_%d" % int(st.get("variant", 1))
					if _sfx_path(nm2) == "":
						missing_sfx[nm2] = true
				"if":
					for k2 in ["then", "else"]:
						if st.has(k2):
							var s2 := str(st[k2])
							refs[s2] = true
							if s2 != "" and not scenes.has(s2):
								out.append("scene %s：if 的 %s scene %s 不存在" % [id, k2, s2])
					var f2 := str(st.get("flag", "")).trim_prefix("!")
					if not set_flags.has(f2):
						out.append("scene %s：if 的 flag %s 没有地方设" % [id, f2])
				"fade_to":
					if not str(st.get("room", "forest")) in ["forest", "treehouse"] and not world.is_stage(str(st.get("room", ""))) \
							and not (str(st.get("room", "")) == "cockpit" and world.cockpit != null):
						out.append("scene %s：fade_to 的 room 不认识 %s" % [id, st.get("room")])
					if not world.has_marker(str(st.get("at", ""))) and not str(st.get("at", "")).is_valid_float():
						out.append("scene %s：fade_to 的 at 找不到 %s" % [id, st.get("at")])
					for w in st.get("with", []):
						if npc(str(w)) == null:
							out.append("scene %s：fade_to 的 with 不认识 %s" % [id, w])
					var pl4 = st.get("place", {})
					if pl4 is Dictionary:
						for w4 in pl4:
							if npc(str(w4)) == null:
								out.append("scene %s：fade_to 的 place 不认识 %s" % [id, w4])
							elif not world.has_marker(str(pl4[w4])) and not str(pl4[w4]).is_valid_float():
								out.append("scene %s：fade_to 的 place 找不到 %s" % [id, pl4[w4]])
					var fc4 = st.get("face", {})
					if fc4 is Dictionary:
						for w5 in fc4:
							if npc(str(w5)) == null:
								out.append("scene %s：fade_to 的 face 不认识 %s" % [id, w5])
							elif npc(str(fc4[w5])) == null and not world.has_marker(str(fc4[w5])) and not str(fc4[w5]).is_valid_float():
								out.append("scene %s：fade_to 的 face 找不到 %s" % [id, fc4[w5]])
					for k4 in ["leave", "cam", "arrive"]:
						if st.has(k4) and not world.has_marker(str(st[k4])) and not str(st[k4]).is_valid_float():
							out.append("scene %s：fade_to 的 %s 找不到 %s" % [id, k4, st[k4]])
				"camera":
					if st.has("at") and not world.has_marker(str(st["at"])) and not str(st["at"]).is_valid_float():
						out.append("scene %s：camera 的 at 找不到 %s" % [id, st["at"]])
					if not (st.has("at") or st.has("zoom") or st.get("hold", false) or st.get("release", false)):
						out.append("scene %s：camera 要有 at / zoom / hold / release" % id)
				"anim":
					var who := str(st.get("who", ""))
					var key := "miluo" if npc(who) == miluo else who
					if npc(who) != null and npcs.values().has(npc(who)):
						if not npc(who).has_anim(str(st.get("name", ""))):
							if str(st.get("name", "")) != "hop":      # hop 不是帧动画（npc_generic.hop），剧本 anim 直接调
								out.append("info: MISSING_ANIM %s.%s（scene %s：还没有这段动作，播的时候退回待机 / 占位）" % [who, st.get("name"), id])
						continue
					if npc(who) == chen and chen != null and not (ANIM_MAP["chen"] as Dictionary).has(str(st.get("name", ""))):
						if chen_anim(str(st.get("name", ""))) == "":
							var al := str(chen_alias().get(str(st.get("name", "")), ""))
							out.append("info: MISSING_ANIM %s（scene %s：晨还没有这段动作，播的时候退回待机）" % [str(st.get("name")) + (" → " + al if al != "" else ""), id])
					elif not (ANIM_MAP.get(key, {}) as Dictionary).has(str(st.get("name", ""))):
						out.append("scene %s：%s 没有动画 %s（有：%s）" % [id, who, st.get("name"), ", ".join((ANIM_MAP.get(key, {}) as Dictionary).keys())])
				"prop":
					var pid := str(st.get("id", ""))
					if world.stage_of_prop(pid) != "" or (not world.stages.is_empty() and not world.props.has(world.prop_id(pid)) and not (world.cockpit != null and world.cockpit.has_prop(pid))):
						if world.stage_of_prop(pid) == "":
							out.append("info: scene %s：物件 %s 还没有图 / 位置（room.json 里加上就有；现在只记状态）" % [id, pid])
						continue
					if world.cockpit != null and world.cockpit.has_prop(pid):
						if not world.cockpit.objects.has(pid) and pid != "cockpit_window":
							out.append("info: scene %s：驾驶舱物件 %s 没有位置（cockpit.json / 占位布局里都没有），只记状态" % [id, pid])
						elif not world.cockpit.knows_state(pid, str(st.get("state", ""))):
							out.append("info: scene %s：驾驶舱物件 %s 的状态 %s 没有画（cockpit.json 的 states、%s_%s.png、窗外的 sky.json / sky_final.json 里都没有）" % [id, pid, st.get("state"), pid, st.get("state")])
					elif not world.props.has(world.prop_id(pid)) and not pid in world.PSEUDO_PROPS:
						out.append("scene %s：没有物件 %s（只记状态，画面上没东西）" % [id, pid])
				"guide":
					if not world.has_marker(str(st.get("to", ""))) and not str(st.get("to", "")).is_valid_float():
						out.append("scene %s：guide 的 to 找不到 %s" % [id, st.get("to")])
				"goto":
					var s := str(st.get("scene", ""))
					refs[s] = true
					if not scenes.has(s):
						out.append("scene %s：goto 的 scene %s 不存在" % [id, s])
				"mechanic", "todo_mechanic", "form", "follow", "water", "closeup":
					out.append_array(_validate_room_step(str(id), kind, st, refs))
				"barter":
					out.append_array(barter.validate(str(id), st, refs))
				"pick":
					for o in st.get("options", []):
						var s := str(o.get("scene", ""))
						refs[s] = true
						if not scenes.has(s):
							out.append("scene %s：pick 选项 %s 的 scene %s 不存在" % [id, o.get("id"), s])
						var pid := str(o.get("id", ""))
						if not world.props.has(pid) and not world.props.has(pid.trim_prefix("room_")) and world.stage_of_prop(pid) == "":
							out.append("info: scene %s：pick 选项 %s 场景里没有这个物件（用下面一排按钮）" % [id, pid])
	for h in hotspot_defs:
		if h is Dictionary and hotspots.is_enter(h) and not bool(h.get("cutscene", false)):
			for s in _reach_enter(str(h.get("scene", "")), {}):
				for st in scenes.get(s, []):
					if st is Dictionary and str(st.get("do", "")) == "walk" and str(st.get("who", "chen")) == "chen":
						out.append("scene %s（hotspot %s 走进去触发）：晨的 walk 不执行——不推人，停在看得见的边上" % [s, h.get("id")])
	out.append_array(_validate_portals())
	out.append_array(_validate_objectives())
	# 第一关支线（include）
	for e in include_errors:
		out.append("include：" + str(e))
	if not include_files.is_empty():
		out.append("info: 合进来的支线文件：" + ", ".join(include_files))
	for iid in Inventory._db:
		var it2: Dictionary = Inventory._db[iid]
		if it2.has("fuel_kind"):
			var fk := str(it2["fuel_kind"])
			if not fk in ["unrelated", "personal", "none"]:
				out.append("物品 %s：fuel_kind 只认 unrelated / personal / none（%s）" % [iid, fk])
			elif fk == "unrelated" and int(it2.get("keepsake_burn", 0)) <= 0:
				out.append("物品 %s：fuel_kind unrelated 要写 keepsake_burn（飞行一先烧掉它加多少）" % iid)
	for o2 in data.get("side_objectives", []):
		if o2 is Dictionary:
			for f8 in o2.get("need", []) + o2.get("not", []):
				if not set_flags.has(str(f8)):
					out.append("（可选）目标：flag %s 没有地方设" % f8)
	# 第一关新版的剧本顶层（见文件头）
	for v in data.get("item_views", []):
		var vs := str(v.get("scene", "")) if v is Dictionary else ""
		refs[vs] = true
		if not scenes.has(vs):
			out.append("item_views：scene %s 不存在" % vs)
		if v is Dictionary and not Inventory.defined(str(v.get("item", ""))):
			out.append("item_views：物品 %s 不在物品表" % v.get("item"))
	var ow = data.get("one_way", {})
	if ow is Dictionary and not ow.is_empty():
		if not world.has_marker(str(ow.get("wall", ""))):
			out.append("one_way：wall 找不到 marker %s" % ow.get("wall"))
		for k2 in ["after", "until"]:
			if not set_flags.has(str(ow.get(k2, ""))):
				out.append("one_way：%s 的 flag %s 没有地方设" % [k2, ow.get(k2)])
	for pid in data.get("hide_props", []):
		if str(pid) != "wood" and not world.props.has(str(pid)):
			out.append("hide_props：没有物件 %s" % pid)
	for id in scenes:
		for st in scenes[id]:
			if st is Dictionary and str(st.get("do", "")) == "reward":
				if st.has("item") and not Inventory.defined(str(st["item"])):
					out.append("scene %s：reward 的物品 %s 不在物品表" % [id, st["item"]])
				elif not st.has("item") and not ResourceLoader.exists(str(st.get("tex", ""))) and not FileAccess.file_exists(str(st.get("tex", ""))):
					out.append("scene %s：reward 的图 %s 不存在" % [id, st.get("tex")])
			if st is Dictionary and str(st.get("do", "")) == "burn_held":
				for it1 in st.get("items", []):
					if not Inventory.defined(str(it1)):
						out.append("scene %s：burn_held 的物品 %s 不在物品表" % [id, it1])
			if st is Dictionary and str(st.get("do", "")) == "inner" and not st.get("clear", false) and str(st.get("zh", "")) == "":
				out.append("scene %s：inner 没有 zh" % id)
			if st is Dictionary and str(st.get("do", "")) == "fade_to" and st.has("style") and str(st["style"]) != "pixel":
				out.append("scene %s：fade_to 的 style 只认 pixel（%s）" % [id, st["style"]])
	if not ResourceLoader.exists(INNER_GD):
		var n_inner := 0
		for id in scenes:
			for st in scenes[id]:
				if st is Dictionary and str(st.get("do", "")) == "inner":
					n_inner += 1
		if n_inner > 0:
			out.append("info: 潜意识字脚本 %s 还没有（%d 处 inner 先打印出来）" % [INNER_GD, n_inner])
	for id in scenes:
		if not refs.has(id):
			out.append("info: scene %s 没有任何 hotspot / goto / pick / if 引用到（播不到）" % id)
	var hs = data.get("hints", null)
	if hs is Array:
		for e in hs:
			if e is Dictionary and e.has("flag") and not set_flags.has(str(e["flag"])):
				out.append("hints：flag %s 没有地方设" % e["flag"])
	elif hs is Dictionary:
		for f in hs:
			if not set_flags.has(str(f)):
				out.append("hints：flag %s 没有地方设" % f)
	out.append_array(_validate_fuel())
	if not missing_sfx.is_empty():
		out.append("info: 缺音效文件（静默跳过）：" + ", ".join(missing_sfx.keys()))
	return out


## --story_check：驾驶舱的两个步骤（debris_steer / keepsake_choice）
func _validate_cockpit(id: String, kind: String, st: Dictionary, refs: Dictionary) -> Array[String]:
	var out: Array[String] = []
	if world.cockpit == null:
		out.append("scene %s：%s 要在驾驶舱里（剧本 rooms 里加 cockpit）" % [id, kind])
	if kind == "debris_steer":
		if not (st.get("sec", 40) is float or st.get("sec", 40) is int):
			out.append("scene %s：debris_steer 的 sec 要是数字" % id)
		return out
	if kind == "cockpit_dash":
		return out
	var items: Array = st.get("items", [])
	var sc: Dictionary = st.get("scenes", {}) if st.get("scenes", {}) is Dictionary else {}
	if items.is_empty():
		out.append("scene %s：keepsake_choice 没有 items" % id)
	for it in items:
		if not Inventory.defined(str(it)):
			out.append("scene %s：keepsake_choice 的物品 %s 不在物品表" % [id, it])
		if not sc.has(str(it)):
			out.append("scene %s：keepsake_choice 的 %s 没有对应的 scene（scenes 里加上）" % [id, it])
	for k in sc:
		refs[str(sc[k])] = true
		if not scenes.has(str(sc[k])):
			out.append("scene %s：keepsake_choice 的 %s → scene %s 不存在" % [id, k, sc[k]])
	# 多选版（终章燃料柜）：look_scenes / keep_scenes 也是 scene 名（当台词播，不跳转）
	for key in ["look_scenes", "keep_scenes"]:
		var ls = st.get(key, {})
		if not ls is Dictionary:
			out.append("scene %s：keepsake_choice 的 %s 要是 {物品: scene}" % [id, key])
			continue
		for k in ls:
			refs[str(ls[k])] = true
			if not scenes.has(str(ls[k])):
				out.append("scene %s：keepsake_choice 的 %s %s → scene %s 不存在" % [id, key, k, ls[k]])
	if bool(st.get("multi", false)) and str(st.get("then", "")) != "":
		refs[str(st["then"])] = true
		if not scenes.has(str(st["then"])):
			out.append("scene %s：keepsake_choice 的 then → scene %s 不存在" % [id, st["then"]])
	var groups: Array = []
	var look = st.get("look", {})
	if look is Dictionary:
		for k in look:
			groups.append(look[k])
	groups.append(st.get("put_back", []))
	for g in groups:
		if not g is Array:
			out.append("scene %s：keepsake_choice 的 look / put_back 要是台词数组" % id)
			continue
		for l in g:
			if l is Dictionary and l.has("say") and not speakers.has(str(l["say"])):
				out.append("scene %s：keepsake_choice 台词的说话人 %s 不在 speakers 里" % [id, l["say"]])
	return out


## --story_check：燃料表对得上——起飞的燃料 − 避碎石最多扣的 + 放进任何一件纪念品给的 ≥ 改航线以后需要的量
## （作者的规矩：放一件就一定补得上；纪念品卡片上不标数，差多少只看左上角）
func _validate_fuel() -> Array[String]:
	var out: Array[String] = []
	var have := -1
	var need := 0
	var loss := 0
	var pre := 0
	var dyn := -1                     # fuel need_held：放一件私人物品要补得上的那一截（plus）
	var any := false
	for id in scenes:
		for st in scenes[id]:
			if not st is Dictionary:
				continue
			var d := str(st.get("do", ""))
			if d == "burn_held":
				for it0 in st.get("items", []):
					pre += fuel_of(str(it0))           # 二选一之前先烧掉的无关东西
			if d == "fuel":
				any = true
				if st.has("have") and have < 0:
					have = int(st["have"])
				if st.has("need"):
					need = maxi(need, int(st["need"]))
				if st.has("need_held"):
					dyn = int(st.get("plus", 100))
			elif d == "debris_steer" and int(st.get("fuel_per_bump", 0)) > 0:
				if not st.has("fuel_max_loss"):
					out.append("scene %s：debris_steer 扣燃料要写 fuel_max_loss（最多扣多少），不然放一件纪念品可能补不上" % id)
				loss += int(st.get("fuel_max_loss", 0))
	if not any:
		return out
	if have < 0:
		out.append("fuel：剧本里没有设起始燃料（{\"do\": \"fuel\", \"have\": n, \"need\": n}）")
		return out
	for id in scenes:
		for st in scenes[id]:
			if not st is Dictionary or str(st.get("do", "")) != "keepsake_choice":
				continue
			if bool(st.get("multi", false)) or bool(st.get("retired", false)):
				continue                       # 多选版：界面自己按 keepsake_burn 加燃料、一直放到够（不用「放一件就补得上」）；retired = 旧流程留下、走不到的
			var sc: Dictionary = st.get("scenes", {}) if st.get("scenes", {}) is Dictionary else {}
			for it in st.get("items", []):
				var gain := 0
				for sid in _reach(str(sc.get(str(it), "")), {}):
					for s2 in scenes.get(sid, []):
						if s2 is Dictionary and str(s2.get("do", "")) == "fuel":
							gain += fuel_of(str(s2["burn"])) if s2.has("burn") else int(s2.get("add", 0))
				if gain <= 0:
					out.append("scene %s：keepsake_choice 放 %s 以后没有 fuel 步骤加燃料（燃料表不会涨）" % [id, it])
				elif dyn >= 0:
					if gain < dyn:
						out.append("scene %s：放 %s（%d）补不上无关东西烧完以后差的 %d" % [id, it, gain, dyn])
				elif have - loss + pre + gain < need:
					out.append("scene %s：放 %s 补不上燃料：起飞 %d − 撞碎石最多 %d + 先烧的 %d + %d < 需要 %d" % [id, it, have, loss, pre, gain, need])
				elif pre > 0 and have + pre >= need:
					out.append("scene %s：先烧的无关东西（%d）就够了，不用选 %s（需要 %d）" % [id, pre, it, need])
	return out


## --story_check：绕过必经的剧情（11-04 作者在南桥卡住「这里咋通关啊」）。
## 一个点的剧情会 fade_to 到房间 R、还设了 flag（= 推进主线的那一步）；可 R 也能从别的房间的门户（room.json portals）直接走进去，
## 门户的条件和这个点的条件又不冲突，R 里也没有「走进去就补播」的点（trigger enter、能设上同一批 flag 里的一个）→ 报 QA_PORTAL。
## 修法：在 R 里加 trigger enter 的点（south_arrive 那样），或者给门户加 need（剧情播过以后才开）。
func _validate_portals() -> Array[String]:
	var out: Array[String] = []
	if world.stages.is_empty():
		return out
	for h in hotspot_defs:
		if not h is Dictionary:
			continue
		var src := str(h.get("room", "forest"))
		var sets := {}
		var dst := ""
		for sid in _reach(str(h.get("scene", "")), {}):
			for st in scenes.get(sid, []):
				if not st is Dictionary:
					continue
				if str(st.get("do", "")) == "flag" and st.has("set"):
					sets[str(st["set"])] = true
				if str(st.get("do", "")) == "fade_to" and dst == "" and str(st.get("room", "")) != src and world.is_stage(str(st.get("room", ""))):
					dst = str(st["room"])
		if dst == "" or sets.is_empty():
			continue
		var hneed: Array = h.get("need", [])
		var hnot: Array = h.get("not", [])
		var reach := _rooms_without(src, dst)        # 这个点还在等着的时候，不经过 R 能走到哪些房间
		for r in world.stages:
			if str(r) == dst or not reach.has(str(r)):
				continue
			for pt in world.stages[r].portals():
				# 只算走到房间边上就过去的门户（edge）；带 x 的是 F8 自由探索用的，平时要靠剧本的点
				if not pt is Dictionary or str(pt.get("to", "")) != dst or not pt.has("edge"):
					continue
				var pneed: Array = pt.get("need", [])
				var pnot: Array = pt.get("not", [])
				var clash := false
				for f in pnot:
					if hneed.has(f):
						clash = true
				for f in pneed:
					if hnot.has(f) or sets.has(f):
						clash = true              # 门户要的 flag 是这段剧情才设的：剧情没播之前门户关着
				if clash:
					continue
				var covered := false
				if str(r) == src and hotspots.is_enter(h):
					# 这个点自己就是走进去触发的、就在门户那一头的墙边：要走到边上一定先踩到它（南桥的 south_back）
					var hr: Dictionary = world.resolve(h.get("at", 0))
					var wl: Vector2 = world.stages[r].walls()
					var edge_x: float = wl.x if str(pt["edge"]) == "left" else wl.y
					if hr["ok"] and absf(float(hr["x"]) - edge_x) <= float(h.get("range", 20)) + 30.0:
						covered = true
				for h2 in hotspot_defs:
					if h2 is Dictionary and str(h2.get("room", "forest")) == dst and hotspots.is_enter(h2):
						for f2 in sets:
							if _leads_to(str(h2.get("scene", "")), str(f2)):
								covered = true
				if not covered:
					out.append("QA_PORTAL hotspot %s（%s）的剧情要换到 %s，可从 %s 的门户直接走进 %s，进去以后没有补播的点：会卡住" % [h.get("id"), src, dst, r, dst])
	return out


## 从房间 a 出发、不进 avoid，靠走到边上的门户（edge）能到哪些房间（门户的 need 不管：保守算开着）
func _rooms_without(a: String, avoid: String) -> Dictionary:
	var seen := {a: true}
	var todo: Array = [a]
	while not todo.is_empty():
		var r: String = todo.pop_back()
		var sg: Node2D = world.stage(r)
		if sg == null:
			continue
		for pt in sg.portals():
			if pt is Dictionary and pt.has("edge"):
				var to := str(pt.get("to", ""))
				if to != avoid and not seen.has(to) and world.is_stage(to):
					seen[to] = true
					todo.append(to)
	return seen


## --story_check：做不完的目标。每个目标（objectives、（可选）的）完成 = 它的 not 里某个 flag 设上；
## 剧本里没有任何点 / 剧情 / 小游戏能通到这些 flag → QA_OBJECTIVE（玩家会卡在这个目标上）
func _validate_objectives() -> Array[String]:
	var out: Array[String] = []
	var setters := {}
	for sid in scenes:
		for st in scenes[sid]:
			if st is Dictionary and str(st.get("do", "")) in ["flag", "count"] and st.has("set"):
				setters[str(st["set"])] = true
			if st is Dictionary and str(st.get("do", "")) == "mechanic":
				for f in st.get("sets", []):
					setters[str(f)] = true
			if st is Dictionary and str(st.get("do", "")) == "burn_held":
				for f in st.get("items", []):
					setters["burned_" + str(f)] = true
	for f in ENGINE_FLAGS:
		setters[f] = true
	for f in barter.flags():
		setters[str(f)] = true
	for o in data.get("objectives", []) + data.get("side_objectives", []):
		if not o is Dictionary:
			continue
		var done: Array = o.get("not", [])
		if done.is_empty():
			continue
		var ok := false
		for f in done:
			if setters.has(str(f)) or carry_flags.has(f):
				ok = true
		if not ok:
			out.append("QA_OBJECTIVE 目标「%s」：not 里的 flag（%s）剧本里哪儿都不设，做不完" % [o.get("zh", ""), ", ".join(done)])
	return out


## if 的分支 scene 能不能「播完回来」：里面只有普通步骤（没有 goto / if / 点选 / 对话选项 / 带路 / 结束 / 驾驶舱选择）
func _falls_through(s: String) -> bool:
	if not scenes.has(s):
		return false
	for st in scenes[s]:
		if st is Dictionary and str(st.get("do", "")) in ["goto", "if", "pick", "choice", "guide", "end_chapter", "keepsake_choice"]:
			return false
	return true


# ======================================================================= 多房间章节（河流篇起，docs/river_rooms_contract.md）
func _multi_room() -> bool:
	for r in data.get("rooms", []):
		if not str(r) in ["forest", "treehouse", "cockpit"]:
			return true
	return false


## 剧本里当角色用的名字（不是晨 / 鹿 / 弥洛的，交给 npc_generic.gd）
func _collect_npc_names() -> void:
	var skip := ["chen", "deer", "miluo", "milo", "snake", ""]
	for sid in scenes:
		for st in scenes[sid]:
			if not st is Dictionary:
				continue
			var d := str(st.get("do", ""))
			if d in ["show", "hide", "walk", "face", "anim", "form", "follow"]:
				var w := str(st.get("who", ""))
				if not w in skip and not (d in ["show", "hide"] and _is_prop_name(w)):
					_npc_names[w] = true
			if d == "fade_to":
				for w2 in st.get("with", []):
					if not str(w2) in skip:
						_npc_names[str(w2)] = true


func _is_prop_name(w: String) -> bool:
	return world.props.has(w) or world.props.has(w.trim_prefix("room_"))


## 通用角色：第一次用到时建（藏着，等剧本 show）
func _generic(who: String) -> Node2D:
	if npcs.has(who):
		return npcs[who]
	if not _npc_names.has(who) or level == null:
		return null
	var n: Node2D = NPC_GD.new()
	n.setup(who)
	if who == "rabbit_doe":
		var bow := Polygon2D.new()
		bow.polygon = PackedVector2Array([Vector2(-6, -4), Vector2(0, -1), Vector2(6, -4),
			Vector2(6, 3), Vector2(0, 1), Vector2(-6, 3)])
		bow.position = Vector2(1, -44)
		bow.color = Color("#d88a9c")
		n.add_child(bow)
	elif who.begins_with("rabbit_kit_"):
		n.scale = Vector2(0.57, 0.57)
		n.head *= 0.57
	n.visible = false
	level.add_child(n)
	level.move_child(n, chen.get_index())       # 和晨同一层、排在晨后面（晨在前）
	npcs[who] = n
	_npc_room[n.name] = world.room
	n.ground_fn = _npc_ground(n, world.room)
	return n


## 推每个 marker 在哪个房间：hotspot 的 room、scene 里 fade_to 换过去的房间，顺着 goto / if / 选项传下去
func _setup_stages() -> void:
	var scene_room := {}
	for h in hotspot_defs:
		if h is Dictionary and str(h.get("scene", "")) != "":
			scene_room[str(h["scene"])] = str(h.get("room", "forest"))
	var start_room := ""
	for r in data.get("rooms", []):
		if not str(r) in ["forest", "treehouse", "cockpit"]:
			start_room = str(r)
			break
	if entry_scene != "" and not scene_room.has(entry_scene):
		scene_room[entry_scene] = start_room
	for sid in scenes:
		if str(sid).begins_with("start") and not scene_room.has(sid):
			scene_room[sid] = start_room
	var inferred := {}
	var prop_ids := {}
	for _pass in 6:
		for sid in scene_room.keys():
			var cur := str(scene_room[sid])
			for st in scenes.get(sid, []):
				if not st is Dictionary:
					continue
				var d := str(st.get("do", ""))
				if d == "fade_to":
					cur = str(st.get("room", cur))
				var refs: Array = []
				for k in ["to", "at", "leave", "cam", "arrive"]:
					if st.get(k) is String:
						refs.append(str(st[k]))
				if d == "prop":
					refs.append(str(st.get("id", "")))
					prop_ids[str(st.get("id", ""))] = true
				var pl = st.get("place", {})
				if pl is Dictionary:
					for v in pl.values():
						refs.append(str(v))
				for m in refs:
					if not inferred.has(m) and npc(m) == null:
						inferred[m] = cur
				var nexts: Array = []
				match d:
					"goto":
						nexts.append(str(st.get("scene", "")))
					"if":
						nexts.append(str(st.get("then", "")))
						nexts.append(str(st.get("else", "")))
					"choice", "pick":
						for o in st.get("options", []):
							nexts.append(str(o.get("scene", "")))
					"closeup":
						for z in st.get("zones", []):
							nexts.append(str(z.get("scene", "")))
				for nx in nexts:
					if nx != "" and not scene_room.has(nx):
						scene_room[nx] = cur
	for h in hotspot_defs:
		if h is Dictionary and h.get("at") is String:
			inferred[str(h["at"])] = str(h.get("room", "forest"))
	var order: Array = (data.get("markers", {}) as Dictionary).keys()
	for m in inferred:
		if not order.has(m):
			order.append(m)
	world._prop_ids = prop_ids.keys()
	world.add_stages(data.get("rooms", []), inferred, order)


func world_cam_y(r := "") -> float:
	var sg: Node2D = world.stage(r if r != "" else world.room)
	return sg.cam_y() if sg != null else 135.0


func room_of_marker(nm: String) -> String:
	return world.room_of_marker(nm)


## 通用角色在小屋里外（树屋同款）：屋里的人在晨不在屋里时压到前墙后面；晨进屋时，站在屋子图范围里的屋外的人淡掉
func _sync_generic_vis(instant: bool) -> void:
	for who in npcs:
		var n: Node2D = npcs[who]
		var r := str(_npc_room.get(n.name, ""))
		var rs: Node2D = world.stage(r)
		var cs: Node2D = world.cur_stage()
		n.z_index = -2 if rs != null and rs.is_house and world.room != r else int(n.get_meta("pose_z", 0))   # pose 压到物件后面的保留
		var a := 1.0
		if cs != null and cs.is_house and r != world.room and world.house_pair(r, world.room):
			if n.position.x > cs.origin.x and n.position.x < cs.origin.x + cs.size.x:
				a = 0.0
		elif r != "" and r != world.room and not world.house_pair(r, world.room):
			a = 0.0                 # 别的房间的人（换到驾驶舱以后河岸上的妮芙、阿汀）：不在这一屏里画出来
		var old = n.get_meta("sync_tw") if n.has_meta("sync_tw") else null
		if old is Tween and (old as Tween).is_valid():
			(old as Tween).kill()
		if instant or ff:
			n.modulate.a = a
		elif not is_equal_approx(n.modulate.a, a):
			var tw := create_tween()
			tw.tween_property(n, "modulate:a", a, 0.5)
			n.set_meta("sync_tw", tw)


## pose：通用角色的图（spr）绕脚底转 rot 度、挪 dx / dy 像素，sec 秒平滑过去（sine，物理一点）；z 给了就改人的前后
## （物件默认 z −1：z −2 = 压到物件后面）。{"rot": 0, "dx": 0, "dy": 0} = 回到原样；z 写 0 回到平常。wait:false 不等。
## 10-30 作者：河岸遇见妮芙，箱子后面先露出鲸鱼壳的尾巴（妮芙原图斜着扎进箱子后面），再转过来——不另画尾巴、不凭空出现。
func _pose(st: Dictionary) -> void:
	var n := npc(str(st.get("who", "")))
	if n == null or not npcs.values().has(n):
		return
	var spr: Node2D = n.spr
	if st.has("z"):
		n.z_index = int(st["z"])
		n.set_meta("pose_z", int(st["z"]))
	var rot := deg_to_rad(float(st.get("rot", 0.0)))
	var pos := Vector2(float(st.get("dx", 0.0)), float(st.get("dy", 0.0)))
	var sec := float(st.get("sec", 0.6))
	if ff or sec <= 0.0:
		spr.rotation = rot
		spr.position = pos
		return
	var tw := create_tween().set_parallel(true).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(spr, "rotation", rot, sec)
	tw.tween_method(func(p: Vector2): spr.position = p.round(), spr.position, pos, sec)   # 位置取整到像素
	if st.get("wait", true):
		await tw.finished


## 跟着晨走（follow）：自由走动时（剧情没在播、或小游戏在等互动）每帧追晨身后 gap 像素
## 通用角色（妮芙、阿汀……）在看得见的画面里一帧被挪了 SNAP_MIN～SNAP_MAX 像素（跟随 / 让路 / 墙把人夹回来的那种小跳）：
## 改成每帧最多 SNAP_MIN，几帧滑过去。更远的是剧本放到别处（换房间、show at）——那种交给剧本自己（淡入、走过来），这里不管。
## 11-04 作者「闪现问题」，--qa_live 的 QA_JUMP 查出来的（妮芙 10～50 像素一跳）。
const SNAP_MIN := 4.0
const SNAP_MAX := 80.0


func _no_snap() -> void:
	if ff or free_roam:
		return
	var open := qa_screen_open()
	for n in npcs.values():
		if not is_instance_valid(n):
			continue
		var last = n.get_meta("ns_x") if n.has_meta("ns_x") else null     # get_meta 的默认值给 null 还是会报错，先问 has_meta
		var room := _room_of(n)
		if last != null and open and n.visible and str(n.get_meta("ns_room", "")) == room and room == world.room:
			var dx: float = n.position.x - float(last)
			if absf(dx) > SNAP_MIN and absf(dx) <= SNAP_MAX and not n.has_meta("swap_t"):
				n.position.x = round(float(last) + signf(dx) * SNAP_MIN)
				n._x = n.position.x
				n.set_meta("y_lag", true)       # 脚下的高度交给她自己慢慢落（npc_generic y_lag），不在这里再挪一次
		n.set_meta("ns_x", n.position.x)
		n.set_meta("ns_room", room)


## 11-05 河流篇夜测（tape_fix：妮芙从晨右边走到柜子，壳从晨身上平移穿过去）：剧本 walk 的路线经过晨，跟随让路那套管不到。
## 浮着的（妮芙的鲸鱼壳）走近晨时往上飘到壳底比晨头顶还高 PASS_CLEAR，过了再落回来：离晨 PASS_RAMP 以外开始升（smoothstep），
## 到挨上的距离（_side_gap）时已经升满，一直保持到离开。高度按两个人不透明那块的屏幕矩形算（壳比 22 高，固定拱高不够，07:20 河流复测）。
## 只动画出来的高度（npc_generic 的 pass_lift），不动她的位置和脚下；她本来就排在晨后面画（晨在前）
const PASS_RATE := 240.0
const PASS_RAMP := 40.0
const PASS_CLEAR := 2.0


## 浮着的人要往上飘多高，壳底才比晨头顶高 PASS_CLEAR（按两人不透明那块的屏幕矩形；已经抬起来的 lifted 先扣回去）。至少 SWAP_ARC
func _clear_lift(n: Node2D, lifted := 0.0) -> float:
	var nr := _sprite_screen_rect(n.spr)
	var cr := _sprite_screen_rect(chen.spr)
	var zk: float = level.cam.zoom.x
	if nr.size.x <= 0.0 or cr.size.x <= 0.0:
		return SWAP_ARC
	var want := maxf(SWAP_ARC, (nr.end.y + lifted * zk - cr.position.y) / zk + PASS_CLEAR)
	var room_up := (nr.position.y + lifted * zk - 4.0) / zk          # 壳顶最高到屏幕上沿往下 4 像素（楼上那层再往上飘就出画面了）
	return clampf(want, minf(SWAP_ARC, maxf(room_up, 0.0)), maxf(room_up, 0.0))


func _pass_over(delta: float) -> void:
	for n in npcs.values():
		if not is_instance_valid(n) or n.has_meta("swap_t"):
			continue                  # 正在划弧：飘着的那段高度先不动（_swap_step 只补剩下的）
		var cur_l := float(n.get_meta("pass_lift", 0.0))
		var want := 0.0
		if n.visible and n.is_walking() and _is_hover(n) and chen.visible and _room_of(n) == world.room \
				and absf(n.position.y - chen.position.y) < 12.0:
			var zone := _side_gap(n, 30.0)
			var d := absf(n.position.x - chen.position.x)
			var wx := float(n.get("_walk_x"))
			# 只管真要从晨身边过去的（终点在晨另一边，或者终点就挨着晨）：走到晨旁边停下说话的不跳一下
			var crossing: bool = signf(wx - chen.position.x) != signf(n.position.x - chen.position.x) or absf(wx - chen.position.x) < zone - 0.5
			if (crossing or d < zone) and d < zone + PASS_RAMP:
				var full := float(n.get_meta("pass_full", -1.0))
				if full < 0.0:
					full = _clear_lift(n, cur_l)
					n.set_meta("pass_full", full)
				var k := clampf((zone + PASS_RAMP - d) / PASS_RAMP, 0.0, 1.0)
				want = full * k * k * (3.0 - 2.0 * k)
		elif n.visible and not n.is_walking() and not n.has_meta("swap_t") and _is_hover(n) and chen.visible and _room_of(n) == world.room \
				and absf(n.position.y - chen.position.y) < 12.0:
			# 站着（跟随 / 让路）的时候被晨挤进身子里（楼梯口、墙边划不了弧，弹簧追不上）：真叠上了就往上飘过晨的头，让开了再落
			var zone2 := _side_gap(n, 30.0) - CLEAR_GAP
			var d2 := absf(n.position.x - chen.position.x)
			if d2 < zone2:
				var full2 := float(n.get_meta("pass_full", -1.0))
				if full2 < 0.0:
					full2 = _clear_lift(n, cur_l)
					n.set_meta("pass_full", full2)
				var k2 := clampf((zone2 - d2) / 12.0, 0.0, 1.0)
				want = full2 * k2 * k2 * (3.0 - 2.0 * k2)
		if want == 0.0 and n.has_meta("pass_full"):
			n.remove_meta("pass_full")
		if absf(cur_l - want) > 0.01:
			n.set_meta("pass_lift", move_toward(cur_l, want, PASS_RATE * delta))
		elif want == 0.0 and n.has_meta("pass_lift"):
			n.remove_meta("pass_lift")


func _update_follow(delta: float) -> void:
	if ff:
		return
	_pass_over(delta)
	var free: bool = (not busy or free_walk or mech_wait) and level.free_play()
	_walk_guard()
	for who in follow:
		var n := npc(str(who))
		if n == null or not n.visible or not npcs.values().has(n):
			continue
		if str(_npc_room.get(n.name, "")) != world.room:
			continue
		var fsg := _lv_stage()
		if fsg != null and _lv_of(n, fsg) != fsg.chen_lv:
			if free and not n.has_meta("lv_climbing") and fsg.chen_stair < 0:
				_lv_walk(n, fsg, fsg.chen_lv, chen.position.x - (FOLLOW_GAP if chen.facing > 0 else -FOLLOW_GAP))   # 跟着晨上 / 下楼
			elif fsg.chen_stair >= 0 and not n.has_meta("lv_climbing"):
				_clear_stair_end(n, fsg, _side_gap(n, float(follow[who])), delta)
			continue
		if n.has_meta("lv_climbing"):
			continue
		_make_way(n, _side_gap(n, float(follow[who])), free, delta)
	# 没在跟着晨、但会飘开让路的（妮芙的鲸鱼壳悬浮着：hover）：晨走过来也让开
	for n in npcs.values():
		if follow.has(str(n.get("npc_id"))) or not n.visible or _room_of(n) != world.room or n.has_meta("lv_climbing") or n.has_meta("resident"):
			continue
		if not (n.get("cur") is Dictionary and float((n.get("cur") as Dictionary).get("hover", 0.0)) > 0.0):
			continue
		# 正在 pose（10-31 河岸：妮芙斜着扎在箱子后面、转正浮起来还没落回去）：不让路。不然晨走近时 follow_to 让她转身朝晨，
		# 斜着的图一翻就成了头朝上的怪姿势，转正以后 walk 又翻回去；她自己飘出来时离晨已经够远
		var pspr: Node2D = n.spr
		if pspr.rotation != 0.0 or pspr.position != Vector2.ZERO:
			continue
		var hsg := _lv_stage()
		if hsg != null and _lv_of(n, hsg) != hsg.chen_lv:
			if hsg.chen_stair >= 0:
				_clear_stair_end(n, hsg, _side_gap(n, FOLLOW_GAP), delta)
			continue
		_make_way(n, _side_gap(n, FOLLOW_GAP), false, delta)


## 正在走的人（剧本让她走、跟着晨的人）：
##   要去的地方算的时候晨在别处（还在楼梯上、换了层、后来又走动了），走着走着晨到了她的路上 → 改成停在她这一边、晨旁边；
##   晨从后面追上来（晨比她快）→ 她走快一点，晨不从她身上穿过去（10-31 进市集晨追上往修补摊飘的妮芙，叠在她尾巴上）
func _walk_guard() -> void:
	if not chen.visible:
		return
	var sg := _lv_stage()
	if sg != null and sg.chen_stair >= 0:
		return
	for n in npcs.values():
		if not n.visible or not _is_body(n) or not n.is_walking() or _room_of(n) != world.room or n.has_meta("lv_climbing"):
			continue
		if sg != null and _lv_of(n, sg) != int(sg.chen_lv):
			continue
		var d := clear_dist(n)
		var dx: float = n.position.x - chen.position.x
		if absf(dx) < d - 0.5:
			continue                                  # 已经挨着了：_make_way / 别处推开
		var side := signf(dx)
		var wx := float(n.get("_walk_x"))
		var sp := float(n.get("_walk_speed"))
		if (wx - chen.position.x) * side < d - 0.5:
			n.walk_to(chen.position.x + side * d, sp)
		elif signf(wx - n.position.x) == side and chen._vel > 0.0 and signf(chen.facing) == side \
				and absf(dx) < d + 24.0 and sp < chen._vel + 20.0:
			n.walk_to(wx, chen._vel + 20.0)


## 晨正在走石阶、要上（下）到她站的那层：她站在楼梯口就先飘开，不等晨上来压到她身上再被一下推开
## （10-31 妮芙家里晨上楼，一到楼上正好站在妮芙身上）
func _clear_stair_end(n: Node2D, sg: Node2D, gap: float, delta: float) -> void:
	var s: Dictionary = sg._stairs[sg.chen_stair]
	var lv := _lv_of(n, sg)
	var ex: float = sg.origin.x + float(s["xa"] if lv == int(s["a"]) else s["xb"])
	if lv != int(s["a"]) and lv != int(s["b"]):
		return
	var dx := n.position.x - ex
	if absf(dx) >= gap:
		return
	var side := signf(dx) if absf(dx) >= 1.0 else 1.0
	var w: Vector2 = sg.level_walk(lv) + Vector2(sg.origin.x, sg.origin.x)
	if ex + side * gap > w.y - 4.0 or ex + side * gap < w.x + 4.0:
		side = -side
	n.follow_to(clampf(ex + side * gap, w.x + 4.0, w.y - 4.0), ex, delta)


## 人和人不叠：跟着晨 / 会让路的人待在她现在那一边（晨转身她不从晨身上穿过去），只有被挤到墙边才绕到另一边。
## follow = 自由走的时候跟在晨这一边 gap 远；不跟的时候只在晨冲她走过来时让开（弹簧平滑飘开，追不上再硬推）
## 11-02 作者：「推着 npc 走、和 npc 一起平移一直是个问题……你得开始走，然后 npc 一个 tween 加速，再慢慢跟上」。
##   跟着走：晨起步以后她先停 FOLLOW_DELAY 秒，再用软弹簧（FOLLOW_W）慢慢加速追上、到了慢慢停——不再和晨焊在一起平移。
##   晨冲她走过来（她在晨要去的那边）：浮着的（妮芙的鲸鱼壳）不再被顶着往前推，而是从晨头顶划一道弧（SWAP_ARC 高、SWAP_SEC 秒，
##   smoothstep）飘到晨身后，接着跟。不浮着的照旧让开。
const FOLLOW_W := 3.0
const FOLLOW_DELAY := 0.3
const SWAP_SEC := 0.8
const SWAP_ARC := 22.0
const SWAP_STEP_MAX := 6.0


func _is_hover(n: Node2D) -> bool:
	var c = n.get("cur")
	return c is Dictionary and float((c as Dictionary).get("hover", 0.0)) > 0.0


## 从晨头顶飘到另一边：x 沿 smoothstep 从起点走到「晨身后 gap」（跟着晨现在的位置算），y 是正弦拱
## 11-05 河流篇夜测（压缩第二章那边报的：tape_sound 后妮芙一帧 58 像素，从晨左边直接到右边，swap=true）：
## 划弧中途被别的事打断（晨上楼梯那几帧走 _clear_stair_end、剧本 walk、播剧情时不叫 _make_way）以后 swap_t 还留着，
## 过一阵再叫到这里就接着用老的起点、老的时间算——一下子跳到弧线终点。中断过 / 被别人挪过 / 在走路：作废，不接着划。
## 返回 false = 作废了，_make_way 照平常的让路走。
func _swap_step(n: Node2D, gap: float, delta: float) -> bool:
	var fr := Engine.get_process_frames()
	var lf := int(n.get_meta("swap_f", fr - 1))
	if n.is_walking() or fr - lf > 2 or absf(n.position.x - float(n.get_meta("swap_lx", n.position.x))) > 1.5:
		n.remove_meta("swap_t")
		n.remove_meta("swap_f")
		n.remove_meta("swap_lx")
		n.remove_meta("swap_sec")
		n._x = n.position.x
		n._snap_walk(delta)
		return false
	var t := float(n.get_meta("swap_t")) + delta
	var k := clampf(t / float(n.get_meta("swap_sec", SWAP_SEC)), 0.0, 1.0)
	var e := k * k * (3.0 - 2.0 * k)
	var sd := float(n.get_meta("swap_side"))
	var w: Vector2 = world.walls(chen.position.x)
	var tx := clampf(chen.position.x + sd * gap, w.x + 4.0, w.y - 4.0)
	# 11-05：晨走上楼梯口，这一层能走的范围变了（墙一下子挪到晨脚下），要去的那边被夹到了晨的另一边——
	# 原来接着按 lerp 算，一帧从晨左边跳到右边 58 像素（连拍 tape_sound）。要去的地方翻了边：作废这次划弧，交给平常的让路 / 楼梯口让开
	if signf(tx - chen.position.x) != sd:
		n.remove_meta("swap_t")
		n.remove_meta("swap_f")
		n.remove_meta("swap_lx")
		n.remove_meta("swap_sec")
		n._x = n.position.x
		n._snap_walk(delta)
		return false
	var x0 := float(n.get_meta("swap_x0"))
	var x := lerpf(x0, tx, e)
	x = move_toward(n.position.x, x, SWAP_STEP_MAX)      # 保险：晨跑起来、墙挪了，一帧也不挪超过这些
	n.face(1 if tx > x0 else -1)
	n.play("walk")
	var old_p := n.position
	n.position.x = round(x)
	n._snap_y()
	# 高度：前 30% 的时间升满、中间保持、最后 30% 落回（原来正弦拱起得慢，晨迎面走过来时还没升高就叠上了，11-05 河流复测）
	var up_k := clampf(k / 0.4, 0.0, 1.0)
	var dn_k := clampf((1.0 - k) / 0.4, 0.0, 1.0)
	var hk := (up_k * up_k * (3.0 - 2.0 * up_k)) * (dn_k * dn_k * (3.0 - 2.0 * dn_k))
	n.position.y -= round(float(n.get_meta("swap_arc", SWAP_ARC)) * hk)
	# 楼梯上划弧：x 每帧挪几像素，脚下的高度跟着陡台阶一下变好几像素（11-05 楼梯间 QA_JUMP 7 像素一帧）：
	# 这一帧连 x 带 y 最多挪 SWAP_STEP_MAX - 0.5，跟不上就晚一点到（下一帧接着按地面算）
	if n.position.distance_to(old_p) > SWAP_STEP_MAX - 0.5:
		n.position = old_p.move_toward(n.position, SWAP_STEP_MAX - 0.5).round()
	n.set_meta("swap_t", t)
	n.set_meta("swap_f", fr)
	n.set_meta("swap_lx", n.position.x)
	if k >= 1.0:
		n.remove_meta("swap_t")
		n.remove_meta("swap_f")
		n.remove_meta("swap_lx")
		n.remove_meta("swap_sec")
		n._x = n.position.x
		n._vel = chen._vel * signf(chen.facing) if chen._vel > 0.0 else 0.0
		n.set_meta("f_hold", 0.0)
	return true


func _make_way(n: Node2D, gap: float, follow_on: bool, delta: float) -> void:
	if n.has_meta("swap_t") and _swap_step(n, gap, delta):
		return
	var dx := n.position.x - chen.position.x
	# 晨冲她走过来、快挨上了：浮着的从晨头顶飘到身后（不被推着走）
	if _is_hover(n) and not n.is_walking() and chen._vel > 0.0 and absf(dx) >= 1.0 and signf(chen.facing) == signf(dx) \
			and absf(dx) < gap + 18.0:
		var wb: Vector2 = world.walls(chen.position.x)
		var bx := chen.position.x - signf(chen.facing) * gap
		if bx > wb.x + 4.0 and bx < wb.y - 4.0:
			n.set_meta("swap_t", 0.0)
			n.set_meta("swap_x0", n.position.x)
			n.set_meta("swap_side", -signf(chen.facing))
			# 已经被 _pass_over 往上飘了 pl（画出来的高度）：划弧期间那段高度先留着不落，弧线只补剩下的
			var pl := float(n.get_meta("pass_lift", 0.0))
			var total := _clear_lift(n, pl)
			var arc := maxf(total - pl, 0.0)
			n.set_meta("swap_arc", arc)
			# 拱越高划得越久（升的那段每帧不超过 QA_JUMP 的 6 像素：高 50 的拱 1.4 秒）
			n.set_meta("swap_sec", SWAP_SEC * clampf(total / SWAP_ARC, 1.0, 1.8))
			n.remove_meta("swap_f")
			n.remove_meta("swap_lx")
			if _swap_step(n, gap, delta):
				return
	var side := signf(dx) if absf(dx) >= 1.0 else (-1.0 if chen.facing > 0 else 1.0)
	# 叠在一起的时候（|dx| 不到半个间距）别每帧重新挑边：上一帧挑哪边就接着往哪边让，不然左右来回翻、一下弹出去（11-02 作者：重叠时光速弹开）
	if absf(dx) < gap * 0.5 and n.has_meta("mw_side"):
		side = float(n.get_meta("mw_side"))
	n.set_meta("mw_side", side)
	var w: Vector2 = world.walls(chen.position.x)
	var swap := false
	if chen.position.x + side * gap < w.x + 4.0 or chen.position.x + side * gap > w.y - 4.0:
		side = -side
		swap = true
	var tx := clampf(chen.position.x + side * gap, w.x + 4.0, w.y - 4.0)
	if follow_on:
		if absf(tx - n.position.x) < 4.0 and chen._vel <= 0.0:
			tx = n.position.x
		# 晨刚起步：她先停半拍再追（晨停着的时候记下来，起步那一刻开始数）
		if chen._vel <= 0.0:
			n.set_meta("f_idle", true)
		elif n.get_meta("f_idle", false):
			n.set_meta("f_idle", false)
			n.set_meta("f_hold", FOLLOW_DELAY)
		var hold := float(n.get_meta("f_hold", 0.0))
		if hold > 0.0:
			n.set_meta("f_hold", hold - delta)
			if dx * side >= gap - 0.5:
				tx = n.position.x
		n.follow_to(tx, chen.position.x, delta, FOLLOW_W)
	elif not n.is_walking() and chen._vel > 0.0 and dx * side < gap + 16.0 and signf(chen.facing) == side:
		n.follow_to(tx, chen.position.x, delta, 4.0 if _is_hover(n) else 6.0)           # 晨冲她走过来：先飘开
	elif _is_hover(n) and not n.is_walking() and chen._vel <= 0.0 and dx * side < gap - 2.0:
		# 11-05 河流篇复测（进妮芙家：剧本 walk 晨走到罐子，两人站定只隔 18、壳盖着晨）：过场里不跟随、晨也停了，
		# 原来就这么一直叠着。浮着的人慢慢飘开到不叠的距离（软弹簧，不推）
		n.follow_to(tx, chen.position.x, delta, 3.0)
	_keep_in(n, w, delta)
	# 弹簧追不上（晨跑过来、过场里晨走过她身边）：直接推开，鲸鱼壳不压到晨身上
	# 浮着的（妮芙）不硬推：她要么从晨头顶飘过去（上面 swap），要么弹簧自己让开——硬推就是「闪现」、被推着倒着走（11-02 作者）
	# 11-04 --qa_live：原来直接 position.x = tx，一帧挪十几到几百像素（阿汀在妮芙家门口一下子跳 500 像素）。改成每帧最多 PUSH_MAX，滑开
	if not swap and not _is_hover(n) and not n.is_walking() and dx * side < gap - 0.5 and absf(tx - chen.position.x) >= gap - 0.5:
		var lim := maxf(PUSH_MAX, chen._vel * delta + 1.0)
		n.position.x = round(move_toward(n.position.x, tx, lim))
		n._x = n.position.x
		n._snap_walk(delta)


const PUSH_MAX := 4.0          # 推开让路：一帧最多挪几像素（晨跑得比这快时按晨的速度）

## 让路 / 跟随的人：每秒最多挪 MAKE_WAY_MAX 像素（弹簧离得远时会冲得很快，看着像「光速弹开」），也不出墙
const MAKE_WAY_MAX := 110.0

func _keep_in(n: Node2D, w: Vector2, delta: float) -> void:
	if n.is_walking():
		return
	var last := float(n.get_meta("mw_x", n.position.x))
	if absf(n.position.x - last) > 60.0 or str(n.get_meta("mw_room", "")) != world.room:
		last = n.position.x                  # 剧本把她放到别处了（换房间、show、walk 完）：从新位置算，不往回拽
	n.set_meta("mw_room", world.room)
	var x := clampf(n.position.x, last - MAKE_WAY_MAX * delta - 1.0, last + MAKE_WAY_MAX * delta + 1.0)
	var inside := clampf(x, w.x + 4.0, w.y - 4.0)
	x = move_toward(x, inside, MAKE_WAY_MAX * delta + 1.0)      # 出了墙也是慢慢走回来，不一下子夹回去
	if absf(x - n.position.x) >= 0.5:
		n.position.x = round(x)
		n._x = n.position.x
		n._vel = clampf(n._vel, -MAKE_WAY_MAX, MAKE_WAY_MAX)
		n._snap_walk(delta)
	n.set_meta("mw_x", n.position.x)


## 跟在晨旁边至少隔多远才不叠到晨身上：比人宽的（妮芙的鲸鱼壳 71 宽，锚点到边 36）= 锚点到最远一边 + 晨半个身子 13 + CLEAR_GAP；
## 一般大小的人（帧 40 宽）照 base
func _side_gap(n: Node2D, base: float) -> float:
	var c = n.get("cur")
	if not c is Dictionary or not (c as Dictionary).has("frame"):
		return base
	var fr: Array = c["frame"]
	var an: Array = c.get("anchor", [float(fr[0]) / 2.0, 0])
	var half := maxf(float(an[0]), float(fr[0]) - float(an[0]))
	return maxf(base, half + CLEAR_CHEN_HALF + CLEAR_GAP) if half > 28.0 else base     # 鲸鱼壳和晨之间留 CLEAR_GAP


## 人和人不叠（10-30，作者：人物互相穿插就是 bug）：晨和通用角色（妮芙、阿汀、摊主……）谁也不压到谁身上，两边轮廓隔开 CLEAR_GAP。
##   剧本让人站的位置（walk / show / 换房间放下来）压到别人 → 挪到最近的空地（优先停在走过来的这一边，不穿过人站到对面）；
##   场景开始时晨站在别人身上（走进人身子里按的互动）→ 晨先退开，跟着晨的人压在晨身上 → 她飘开；
##   跟着晨的人（_update_follow）待在她现在那一边，晨冲她走过来就被推着走，不从晨身上穿过去。
##   宽度 = 锚点到身子最远一边：晨 13；妮芙的鲸鱼壳 36；一般大小的人（帧 40 宽）当晨算 13。
##   json 写 "keep_clear": true 的（阿汀 = 奥斯卡的阴险守卫，比晨大一倍，会转身、背后的黑团子换边）按帧算两边里远的那边，
##   还能写 "avoid": [{"room", "x": [x0, x1], "prop", "states": [...]}]：物件是这些状态时他的轮廓也不压到这段（飞机舱门）。
##   背景走过的小人（shadow = false）不算。玩家自己走路穿过站着的人不拦。
const CLEAR_GAP := 8.0                  # 10-31：4 像素看着还是蹭着（妮芙家里壳和尾巴挨着晨），放宽到 8
const CLEAR_CHEN_HALF := 13.0           # 晨站着的身子半宽（奥斯卡的待机帧量出来左右各 13）
var _chen_goal := NAN                   # 剧本让晨走去的地方（还在走）：别人按这里躲


func _keeps_clear(n: Node2D) -> bool:
	if n == null or not npcs.values().has(n):
		return false
	var c = n.get("cur")
	return c is Dictionary and bool((c as Dictionary).get("keep_clear", false))


## 算不算一个占地方的人：晨、通用角色（背景小人不算；json 写了 "pass": true 的也不算——摊子后面的料理鼠妈，晨从摊前走过去）
func _is_body(n: Node2D) -> bool:
	if n == chen:
		return true
	if n == null or not npcs.values().has(n) or not bool(n.get("shadow")):
		return false
	var c = n.get("cur")
	return not (c is Dictionary and bool((c as Dictionary).get("pass", false)))


## 锚点到身子最远一边多远
func _half_w(n: Node2D) -> float:
	var c = n.get("cur") if n != chen else null
	if not c is Dictionary or not (c as Dictionary).has("frame"):
		return CLEAR_CHEN_HALF
	var fr: Array = c["frame"]
	var an: Array = c.get("anchor", [float(fr[0]) / 2.0, 0])
	var half := maxf(float(an[0]), float(fr[0]) - float(an[0]))
	return half if half > 28.0 or bool(c.get("keep_clear", false)) else CLEAR_CHEN_HALF


## 晨和 n 站多远才不叠（找人说话的范围也用它）
func clear_dist(n: Node2D) -> float:
	return _half_w(n) + CLEAR_CHEN_HALF + CLEAR_GAP


## mover 的锚点不能落进去的区间（开区间 x..y）：同一间房、同一层、看得见的人 + 他要躲的物件。skip_follow = 跟着晨的人不算（她们自己让）
func _clear_blocks(mover: Node2D, room: String, lv: int, skip_follow := false) -> Array:
	var out := []
	if not _is_body(mover):
		return out
	var mh := _half_w(mover)
	var sg := _lv_stage(room)
	var others: Array = [chen]
	others.append_array(npcs.values())
	for o in others:
		if o == mover or not o.visible or not _is_body(o):
			continue
		if skip_follow and o != chen and follow.has(str(o.get("npc_id"))):
			continue
		if (world.room if o == chen else _room_of(o)) != room:
			continue
		if sg != null and lv >= 0 and _lv_of(o, sg) != lv:
			continue
		var ox: float = o.position.x
		if o == chen and not is_nan(_chen_goal) and (chen.auto_dir != 0.0 or level.strolling()):
			ox = _chen_goal                         # 晨还在走：按他要停的地方算
		elif o != chen and o.is_walking():
			ox = float(o.get("_walk_x"))
		var d := mh + _half_w(o) + CLEAR_GAP
		out.append(Vector2(ox - d, ox + d))
	if _keeps_clear(mover):
		for z in (mover.get("cur") as Dictionary).get("avoid", []):
			if not z is Dictionary or str(z.get("room", "")) != room:
				continue
			if z.has("prop") and not (z.get("states", []) as Array).has(world.prop_state(str(z["prop"]))):
				continue
			var zx: Array = z.get("x", [0, 0])
			out.append(Vector2(float(zx[0]) - mh - CLEAR_GAP, float(zx[1]) + mh + CLEAR_GAP))
	return out


## 剧本让别人走到晨的另一边：一维的画面里绕不过去，路上一定穿过晨 → 停在自己这一边、晨旁边（人和人不叠）
func _no_pass_chen(n: Node2D, x: float, lv: int) -> float:
	if n == chen or not _is_body(n) or not chen.visible or _room_of(n) != world.room:
		return x
	var sg := _lv_stage()
	if sg != null and (lv >= 0 and lv != int(sg.chen_lv) or _lv_of(n, sg) != int(sg.chen_lv)):
		return x                                  # 不在晨这一层（或者要换层）：路上碰不到晨
	var cx := chen.position.x
	var d := _half_w(n) + CLEAR_CHEN_HALF + CLEAR_GAP
	if n.position.x <= cx - d and x > cx - d:
		print("KEEP_CLEAR %s %d → %d（不穿过晨）" % [n.name, int(x), int(cx - d)])
		return cx - d
	if n.position.x >= cx + d and x < cx + d:
		print("KEEP_CLEAR %s %d → %d（不穿过晨）" % [n.name, int(x), int(cx + d)])
		return cx + d
	return x


## 剧本让晨走过去（10-31 作者：晨走路的路线上有人，要停在那人旁边，或者让那人先让开，不能穿过去）：
##   跟着晨的人、会飘开让路的（妮芙）站着 → 被晨推着往前让（_make_way），一直让到墙边让不开了晨才停；
##   别的人（阿汀、摊主……）、正在走的人 → 晨停在那人（走到的地方）旁边
func _chen_no_pass(x: float, quiet := false) -> float:
	var cx := chen.position.x
	var dir := signf(x - cx)
	if dir == 0.0:
		return x
	var sg := _lv_stage()
	var w: Vector2 = world.walls(cx)
	var out := x
	for n in npcs.values():
		if not n.visible or not _is_body(n) or _room_of(n) != world.room or n.has_meta("lv_climbing"):
			continue
		if sg != null and _lv_of(n, sg) != int(sg.chen_lv):
			continue
		var walking: bool = n.is_walking()
		var bx: float = float(n.get("_walk_x")) if walking else n.position.x
		if (n.position.x - cx) * dir < 1.0 and (bx - cx) * dir < 1.0:
			continue                                  # 在晨身后：不挡路
		var stop := bx - dir * clear_dist(n)
		if not walking and _gives_way(n):
			var far: float = (w.y - 4.0) if dir > 0.0 else (w.x + 4.0)
			stop = far - dir * _side_gap(n, float(follow.get(str(n.get("npc_id")), FOLLOW_GAP)))
		if (out - stop) * dir > 0.0:
			out = stop
	if (out - cx) * dir < 0.0:
		out = cx                                      # 贴着人站着：不往回退
	if absf(out - x) >= 1.0 and not quiet:
		print("KEEP_CLEAR Chen %d → %d（不穿过人）" % [int(x), int(out)])
	return out


## 跟着晨的人、会飘开让路的人（妮芙的鲸鱼壳悬浮着）：晨走过来她自己让（_update_follow → _make_way）
func _gives_way(n: Node2D) -> bool:
	if follow.has(str(n.get("npc_id"))):
		return true
	if n.has_meta("resident"):
		return false                         # 住在这儿的（柜台后面的水母）不让：晨停在它旁边
	var c = n.get("cur")
	return c is Dictionary and float((c as Dictionary).get("hover", 0.0)) > 0.0


## 晨往 dir 走，前面有人正在走、快贴上了（晨走得比他快）
func _chen_blocked(dir: float) -> bool:
	var sg := _lv_stage()
	for n in npcs.values():
		if not n.visible or not _is_body(n) or _room_of(n) != world.room or not n.is_walking():
			continue
		if sg != null and _lv_of(n, sg) != int(sg.chen_lv):
			continue
		var dx: float = (n.position.x - chen.position.x) * dir
		if dx > 0.0 and dx < clear_dist(n) + chen.stop_distance() + 2.0:
			return true
	return false


## 想站 x：压到人 / 物件就挪到最近的空地。from_x = 从哪边走过来：优先停在这一边（不穿过别人站到对面），这边没地方才去另一边
func _clear_x(mover: Node2D, x: float, room: String, lv := -1, from_x := NAN, skip_follow := false) -> float:
	var bl := _clear_blocks(mover, room, lv, skip_follow)
	if bl.is_empty():
		return x
	var stg: Node2D = world.stage(room) if world.is_stage(room) else null
	var w: Vector2 = stg.walls() if stg != null else world.walls(x)
	var cands: Array = [x]
	for b in bl:
		cands.append(ceilf(b.x) - 1.0)
		cands.append(floorf(b.y) + 1.0)
	var best := x
	var best_s := INF
	for c in cands:
		if c < w.x + 4.0 or c > w.y - 4.0:
			continue
		var ok := true
		for b in bl:
			if c > b.x and c < b.y:
				ok = false
				break
		if not ok:
			continue
		var s := absf(c - x)
		if not is_nan(from_x) and absf(from_x - x) > 1.0 and absf(c - x) > 0.5 and signf(c - x) != signf(from_x - x):
			s += 100000.0
		if s < best_s:
			best_s = s
			best = c
	if absf(best - x) >= 1.0:
		print("KEEP_CLEAR %s %d → %d（%s）" % [mover.name, int(x), int(round(best)), room])
	return round(best)


## 调试（--overlap_log）：每帧查同一间房、同一层看得见的人有没有叠在一起（轮廓压上或隔不到 2 像素），
## 打印 OVERLAP 谁 谁 dx、scene、是剧情里还是自由走（free = 玩家自己走路穿过人，不拦）。同一对连着叠只打一次。
var _overlap_log := "--overlap_log" in OS.get_cmdline_user_args()
var _overlap_on := {}


func _check_overlap() -> void:
	var bodies: Array = [chen]
	for n in npcs.values():
		bodies.append(n)
	var sg := _lv_stage()
	var free: bool = (not busy or free_walk or mech_wait) and level.free_play()
	for i in bodies.size():
		var a: Node2D = bodies[i]
		if not a.visible or not _is_body(a):
			continue
		for j in range(i + 1, bodies.size()):
			var b: Node2D = bodies[j]
			if not b.visible or not _is_body(b):
				continue
			var ra: String = world.room if a == chen else _room_of(a)
			var rb: String = _room_of(b)
			var key := a.name + "|" + b.name
			var hit: bool = ra == world.room and rb == world.room and (sg == null or _lv_of(a, sg) == _lv_of(b, sg)) \
				and absf(a.position.x - b.position.x) < _half_w(a) + _half_w(b) + 2.0     # 轮廓隔不到 2 像素也算（蹭着）
			if hit and not _overlap_on.has(key):
				print("OVERLAP %s %s dx=%d scene=%s step=%d %s | %s | %s" % [a.name, b.name, int(absf(a.position.x - b.position.x)), _cur_scene, step_i,
					"free" if free else "story", _body_state(a), _body_state(b)])
			if hit:
				_overlap_on[key] = true
			else:
				_overlap_on.erase(key)


## 调试（--jump_log）：每帧查看得见的人有没有一帧跳很远（「闪现」），打印 JUMP 谁 从哪到哪、scene、房间、层
var _jump_log := "--jump_log" in OS.get_cmdline_user_args()
var qa_jump_n := 0                  # QA_JUMP + QA_CAMJUMP 一共几次（qa_live 的暂停自测看它有没有新增）
var _qa_live := "--qa_live" in OS.get_cmdline_user_args()   # 自动检查（scripts/qa_live.gd + 这里的 QA_JUMP / QA_CAMJUMP / QA_PROP* / QA_POPIN）
var qa_counts := {}
var _qa_cam := {}


## 画面现在看得见（没黑、没被像素块 / 闪回盖住）
func qa_screen_open() -> bool:
	if level == null or level.fade.color.a > 0.3 or level.get("_pixel_fx") != null:
		return false
	if cockpit_ui != null and is_instance_valid(cockpit_ui) and cockpit_ui.get_script() == FLASHBACK_GD:
		return false
	return true


## 世界坐标的点在不在画面里（margin = 往里缩多少）
## 11-05 夜测：一句一句的选项原来固定摆在 x 120、y 186–240，正好压在站在地上的人身上（晨、鹿的身子被选项框盖住）。
## 给 dlg 一份「现在画面里的人各占哪块屏幕」（不透明的那一块），它摆选项时躲开。
func people_screen_rects() -> Array:
	var out: Array = []
	if (closeup_ui != null and is_instance_valid(closeup_ui) and closeup_ui.visible) or mech_panel_rect().size.x > 0.0:
		return out                       # 特写 / 小游戏面板（油灯、收音机、路标）开着：人都压在暗幕后面，选项照原位摆在面板下面
	var list: Array = [chen, deer, miluo]
	list.append_array(npcs.values())
	for n in list:
		if n == null or not is_instance_valid(n) or not (n is CanvasItem) or not (n as CanvasItem).is_visible_in_tree():
			continue
		if (n as CanvasItem).modulate.a < 0.3 or (n != chen and _room_of(n) != world.room):
			continue
		var sp = n.get("spr")
		if not (sp is CanvasItem) or not (sp as CanvasItem).is_visible_in_tree():
			continue
		var r := _sprite_screen_rect(sp)
		if r.size.x > 0.5 and Rect2(0, 0, 480, 270).intersects(r):
			out.append(r)
	return out


## 晨在屏幕上占的矩形（选项是晨在选：选项躲人时贴着晨摆）。看不见 / 特写、面板开着 = 空
func chen_screen_rect() -> Rect2:
	var rs := people_screen_rects()
	if rs.is_empty() or chen == null or not is_instance_valid(chen) or not chen.is_visible_in_tree():
		return Rect2()
	var sp = chen.get("spr")
	if not (sp is CanvasItem) or not (sp as CanvasItem).is_visible_in_tree():
		return Rect2()
	return _sprite_screen_rect(sp)


## 11-05 夜测（河流篇报的）：面板小游戏开着时画面里的人说话（鼠妈「听锅的。」），框按头顶放、正好落进面板中间盖住锅。
## 面板的屏幕矩形（没开面板 = 空）：dlg 摆框时躲开（放到面板下面对话那一带，overlay_layout.gd 的规矩 ①）
func mech_panel_rect() -> Rect2:
	if mech_node == null or not (mech_node is Object) or not is_instance_valid(mech_node):
		return Rect2()
	var b = mech_node.get("board")
	if not (b is Control) or not is_instance_valid(b) or not (b as Control).is_visible_in_tree():
		return Rect2()
	return (b as Control).get_global_rect()


var _used_cache := {}


func _sprite_screen_rect(s: CanvasItem) -> Rect2:
	var tex: Texture2D = null
	var local := Rect2()
	var flip := false
	var trim := true
	if s is AnimatedSprite2D:
		var a := s as AnimatedSprite2D
		if a.sprite_frames == null or not a.sprite_frames.has_animation(a.animation):
			return Rect2()
		tex = a.sprite_frames.get_frame_texture(a.animation, a.frame)
		if tex == null:
			return Rect2()
		var sz := tex.get_size()
		local = Rect2((-sz / 2.0 if a.centered else Vector2.ZERO) + a.offset, sz)
		flip = a.flip_h
	elif s is Sprite2D:
		var sp := s as Sprite2D
		tex = sp.texture
		if tex == null:
			return Rect2()
		local = sp.get_rect()
		flip = sp.flip_h
		trim = not sp.region_enabled and sp.hframes == 1 and sp.vframes == 1
	else:
		return Rect2()
	if trim:
		var u := _used_rect(tex)
		if u.size.x > 0.0:
			var k := local.size / tex.get_size()
			if flip:
				u.position.x = tex.get_size().x - u.end.x
			local = Rect2(local.position + u.position * k, u.size * k)
	var xf := s.get_global_transform_with_canvas()
	var p0 := xf * local.position
	var p1 := xf * local.end
	return Rect2(p0, p1 - p0).abs()


func _used_rect(tex: Texture2D) -> Rect2:
	var key := tex.get_rid()
	if _used_cache.has(key):
		return _used_cache[key]
	var r := Rect2()
	var img := tex.get_image()
	if img != null:
		if img.is_compressed():
			img.decompress()
		r = Rect2(img.get_used_rect())
	_used_cache[key] = r
	return r


func _on_screen(p: Vector2, margin: float) -> bool:
	var left: Vector2 = level.cam_left()
	var z: float = level.cam.zoom.x
	var r := Rect2(left, Vector2(480, 270) / z).grow(-margin)
	return r.has_point(p)
var _last_pos := {}


func _check_jumps() -> void:
	var open := qa_screen_open()            # 黑着 / 像素块盖着 / 闪回盖着的时候换位置不算
	var bodies: Array = [chen, deer, miluo]
	bodies.append_array(npcs.values())
	for n in bodies:
		var key := str(n.name)
		var p: Vector2 = n.global_position
		var vis: bool = open and n.is_visible_in_tree() and n.modulate.a > 0.01
		var dv := Vector2.ZERO
		if _last_pos.has(key):
			var o: Dictionary = _last_pos[key]
			dv = p - (o["p"] as Vector2)
			# 11-04 作者「妮芙出门开始会闪现」：看得见的人一帧挪 6 像素以上就算（最快的走路 / 跑 ≈ 3.8 像素一帧；下石阶一帧 7 像素也是太快）
			if vis and bool(o["vis"]) and str(o["room"]) == world.room and dv.length() > 6.0 \
					and (_on_screen(p, 0.0) or _on_screen(o["p"], 0.0)):
				var sg := _lv_stage()
				var cur_st := ""
				if _qa_live and scenes.has(_cur_scene) and step_i >= 0 and step_i < (scenes[_cur_scene] as Array).size():
					cur_st = JSON.stringify(scenes[_cur_scene][step_i]).left(110)
				var how := ""
				if n != chen and npcs.values().has(n):
					how = "walk=%s swap=%s climb=%s follow=%s" % [str(n.is_walking()), str(n.has_meta("swap_t")), str(n.has_meta("lv_climbing")), str(follow.has(str(n.get("npc_id"))))]
				qa_jump_n += 1
				print("%s %s (%d,%d)->(%d,%d) scene=%s room=%s lv=%s step=%d %s busy=%s %s" % ["QA_JUMP" if _qa_live else "JUMP", key, int(o["p"].x), int(o["p"].y), int(p.x), int(p.y), _cur_scene, world.room, str(_lv_of(n, sg)) if sg != null else "-", step_i, cur_st, str(busy), how])
				qa_counts["jump"] = int(qa_counts.get("jump", 0)) + 1
		_last_pos[key] = {"p": p, "vis": vis, "room": world.room, "v": dv if vis else Vector2.ZERO}
	if not _qa_live:
		return
	# 镜头：一帧里速度突然变了 6 像素以上（平移是平滑的，跳一下才算）
	var c: Vector2 = level.cam.get_screen_center_position()
	if _qa_cam.has("p") and open and bool(_qa_cam["open"]) and str(_qa_cam["room"]) == world.room:
		var v: Vector2 = c - (_qa_cam["p"] as Vector2)
		var pv0: Vector2 = _qa_cam["v"]
		var dvl := (v - pv0).length()
		# 跳 = 速度一帧变了 6 像素以上、而且变了一半以上（很快但缓入缓出的长距离平移不算）；镜头抖、跳过坠毁那一下不算
		var skip_t := float(level.get_meta("qa_skip_t", -100.0))
		if dvl > 6.0 and dvl > 0.5 * maxf(v.length(), pv0.length()) and float(level.get("_shake")) <= 0.0 \
				and float(_qa_cam.get("shake", 0.0)) <= 0.0 and _game_t - skip_t > 1.0:
			var bars: Array = level.get("_bars")
			qa_jump_n += 1
			print("QA_CAMJUMP (%d,%d)->(%d,%d) scene=%s room=%s step=%d bar_dy=%.0f bar_y=%.0f bar_vis=%s override=%s shake=%.2f" % [int(_qa_cam["p"].x), int(_qa_cam["p"].y), int(c.x), int(c.y), _cur_scene, world.room, step_i,
				float(level.get("_cam_bar_dy")), (bars[1] as Control).position.y if bars.size() > 1 else -1.0, str((bars[1] as Control).visible) if bars.size() > 1 else "-",
				str(level.get("_cam_override")), float(level.get("_shake"))] + " pos=%s off=%s prev_v=%s zoom=%.3f prev_zoom=%.3f qte=%s" % [str(level.cam.position), str(level.cam.offset), str(pv0), level.cam.zoom.x, float(_qa_cam.get("z", 1.0)), str(is_instance_valid(level.get("_getup_qte")))])
			qa_counts["camjump"] = int(qa_counts.get("camjump", 0)) + 1
		_qa_cam["v"] = v
	else:
		_qa_cam["v"] = Vector2.ZERO
	_qa_cam["p"] = c
	_qa_cam["shake"] = float(level.get("_shake"))       # 镜头抖（坠毁、起飞）是故意的，不算
	_qa_cam["open"] = open
	_qa_cam["room"] = world.room
	_qa_cam["z"] = level.cam.zoom.x
	# 剧情物件：在画面里一下子换了位置 / 一下子出现、消失
	for pid in world.props:
		var sp = world.props[pid]
		if not sp is Sprite2D or not is_instance_valid(sp):
			continue
		var pv: bool = (sp as Sprite2D).is_visible_in_tree()
		var pa: float = (sp as Sprite2D).modulate.a if pv else 0.0      # 看得见多少（淡入淡出一档 0.25）
		var pp: Vector2 = (sp as Sprite2D).global_position
		var k2 := "prop:" + str(pid)
		if _last_pos.has(k2) and open and bool(_last_pos[k2]["open"]) and str(_last_pos[k2]["room"]) == world.room:
			var o2: Dictionary = _last_pos[k2]
			if pv and bool(o2["vis"]) and (pp - (o2["p"] as Vector2)).length() > 6.0 and _on_screen(pp, 0.0):
				print("QA_PROPJUMP %s (%d,%d)->(%d,%d) scene=%s" % [pid, int(o2["p"].x), int(o2["p"].y), int(pp.x), int(pp.y), _cur_scene])
				qa_counts["propjump"] = int(qa_counts.get("propjump", 0)) + 1
			elif absf(pa - float(o2.get("a", pa))) >= 0.75 and _on_screen(pp, 0.0):
				print("QA_PROPPOP %s %s（画面里一下子%s）scene=%s room=%s" % [pid, "出现" if pa > 0.5 else "消失", "出现" if pa > 0.5 else "消失", _cur_scene, world.room])
				qa_counts["proppop"] = int(qa_counts.get("proppop", 0)) + 1
		_last_pos[k2] = {"p": pp, "vis": pv, "a": pa, "room": world.room, "open": open}


func _bodies_str() -> String:
	var out := "Chen %d a=%.2f" % [int(chen.position.x), chen.modulate.a]
	for n in npcs.values():
		if n.visible and _is_body(n) and _room_of(n) == world.room:
			out += ", %s %d%s a=%.2f" % [n.name, int(n.position.x), "→%d" % int(float(n.get("_walk_x"))) if n.is_walking() else "", n.modulate.a]
	return out


func _body_state(n: Node2D) -> String:
	if n == chen:
		return "chen x=%d vel=%.0f auto=%.0f goal=%s" % [int(chen.position.x), chen._vel, chen.auto_dir, str(_chen_goal)]
	return "%s x=%d walk=%s follow=%s" % [n.name, int(n.position.x), str(n.is_walking()), str(follow.has(str(n.get("npc_id"))))]


## 场景开始：晨站在别人身上（走进人身子里按的互动）→ 晨先退到旁边空地、转回来；跟着晨的人压在晨身上 → 她飘开
func _settle_start() -> void:
	if not chen.visible:
		return
	var st_t := 0.0
	while chen._vel > 0.0 and st_t < 0.5:      # 走进 trigger:"enter" 的点触发的：晨还在往前滑，等停稳再看压没压到人（不然算出来的空地滑过头）
		await StoryState.frame(get_tree())
		st_t += get_process_delta_time()
	var sg := _lv_stage()
	var lv := int(sg.chen_lv) if sg != null else -1
	var x := _clear_x(chen, chen.position.x, world.room, lv, NAN, true)
	if absf(x - chen.position.x) >= 1.0:
		var back := chen.position.x
		await _chen_walk(x)
		chen._set_facing(1 if back > chen.position.x else -1)
	for who in follow:
		var n := npc(str(who))
		if n == null or not n.visible or _room_of(n) != world.room or n.is_walking():
			continue
		if sg != null and _lv_of(n, sg) != lv:
			continue
		var nx := _clear_x(n, n.position.x, world.room, lv)
		if absf(nx - n.position.x) < 1.0:
			continue
		n.walk_to(nx)
		while n.is_walking():
			await StoryState.frame(get_tree())
		n._set_facing(1 if chen.position.x > n.position.x else -1)


# ----------------------------------------------------------------------- 房间之间的转场
## 多房间章节的 fade_to：door（小屋前墙）/ pan_up / pan_down（镜头竖直平移）/ walk_fade（边走边黑）；fade 或带 leave / cam 的走原来的
func _stage_fade(st: Dictionary, room: String, x: float, arrive: float) -> bool:
	var from: String = world.room
	var kind := str(st.get("kind", ""))
	if kind == "":
		if world.house_pair(from, room):
			kind = "door"
		elif st.has("leave") or st.has("cam"):
			kind = "fade"
		else:
			var fs: Node2D = world.stage(from)
			kind = str(fs.portal_to_room(room).get("kind", "fade")) if fs != null else "fade"
	var with: Array = st.get("with", [])
	if room == "cockpit" and world.is_stage(from):
		await _stage_takeoff()             # 河岸 → 驾驶舱（原文 151–152）：飞机竖直升起、泛光、往左上飞出画面，再接原来的淡出
		return false
	match kind:
		"door":
			await _door_move(room, x, with, st)
			return true
		"pan_up", "pan_down":
			var ts: Node2D = world.stage(room)
			var fs2: Node2D = world.stage(from)
			if (ts != null and ts.env == "underwater") or (fs2 != null and fs2.env == "underwater"):
				await _dive_fade(room, x, with, st, ts != null and ts.env == "underwater")
			else:
				await _pan_to(room, x, with, st)
			return true
		"walk_fade":
			await _walk_fade(room, x, with, st, arrive)
			return true
	return false


## 进出门（不黑屏、前墙淡出淡入）：同行 / 跟着晨的人怎么过门（11-04 作者「出门和进门的时候妮芙会闪」）——
##   就在晨身边（同一层、相距 ≤ DOOR_NEAR）：保持她和晨原来的左右距离，一起换过去，不淡不闪，像并排走出门；
##   离得远（屋子另一头、楼上）：门这边看不见她了，过门以后她晚一拍从门里出来——在门口淡入、走两步站到晨身边。
const DOOR_NEAR := 48.0
func _door_move(room: String, x: float, with: Array, st: Dictionary) -> void:
	var near := {}                      # who → 和晨的左右距离
	var far: Array = []
	var names: Array = []
	for w in with:
		names.append(str(w))
	for f in follow:
		if not names.has(str(f)):
			names.append(str(f))
	# 11-04 作者「妮芙……又是隐身（还没进门就随着主角一起变黑），又是穿墙出门」：跟着的人先自己走到门口晨身后，
	# 再和晨一起过门（不在原地淡没、也不在门外凭空冒出来）。走不过来的（别的层、太远）才淡入淡出。
	await _door_gather(names)
	for who in names:
		var n := npc(who)
		if n == null or n == chen or not n.visible:
			continue
		var dx: float = n.position.x - chen.position.x
		if str(_npc_room.get(n.name, world.room)) == world.room and absf(dx) <= maxf(DOOR_NEAR, _side_gap(n, DOOR_GAP) + 6.0) and absf(n.position.y - chen.position.y) < 8.0:
			near[who] = dx
		else:
			far.append(who)
	_teleport(room, x, with, false)
	_fade_place(st)
	var w2: Vector2 = world.walls(chen.position.x)
	for who in near:
		var n := npc(who)
		# 出门以后站在晨身后（晨朝哪边，她在另一边）：晨接着往前走不会从她身上穿过去（11-04 连拍：出门后晨和妮芙叠在一起交错）
		var g := maxf(absf(float(near[who])), _side_gap(n, 22.0))
		var off := g * -float(chen.facing)
		# 11-05 河流篇复测（进妮芙家：晨一进门就贴着左墙，身后只剩 16 像素，被墙夹到只隔 16，接着从晨身上漂过去）：
		# 身后站不下就站到晨前面那边
		if chen.position.x + off < w2.x + 6.0 or chen.position.x + off > w2.y - 6.0:
			off = -off
		var nx := clampf(chen.position.x + off, w2.x + 6.0, w2.y - 6.0)
		_place(n, nx, room)
		n.modulate.a = 1.0
		n._set_facing(chen.facing)
	if far.is_empty():
		await _wait(0.55)
		return
	# 远的那个：先在门口藏着，晚一拍淡入、往外走两步
	var door_x: float = chen.position.x
	# 11-05 夜测（河流篇进妮芙家）：原来放在门口 = 晨脚下、淡入时往外走 26 像素——妮芙的壳半宽 37，整段都压在晨身上。
	# 放在晨身后差一点就挨上的地方淡入，再走到不叠的距离（_side_gap）
	var side := -1.0 if chen.facing > 0 else 1.0
	for who in far:
		var n := npc(who)
		if n == null:
			continue
		var g := _side_gap(n, 26.0)
		_place(n, clampf(door_x + side * maxf(g - 12.0, 14.0), w2.x + 6.0, w2.y - 6.0), room)
		n.modulate.a = 0.0
	await _wait(0.45)
	for who in far:
		var n := npc(who)
		if n == null:
			continue
		var tw := create_tween()
		tw.tween_method(func(a: float): n.modulate.a = floorf(a * 4.0) / 4.0, 0.0, 1.0, 0.4)
		_walk({"who": who, "to": clampf(door_x + side * _side_gap(n, 26.0), w2.x + 6.0, w2.y - 6.0), "wait": false})
	await _wait(0.5)


## 过门之前：跟着的人走到晨身后 DOOR_GAP（同一层、不太远：DOOR_GATHER 以内），等她走到（最多 DOOR_GATHER_SEC 秒）。
## 跳节拍时直接放过去（看不见）
const DOOR_GAP := 26.0
const DOOR_GATHER := 360.0
const DOOR_GATHER_SEC := 1.6
const DOOR_CLIMB_SEC := 5.0          # 从楼上走下来最多等这么久


func _door_gather(names: Array) -> void:
	var sg := _lv_stage()
	var movers: Array = []
	var climbers: Array = []
	for who in names:
		var n := npc(who)
		if n == null or n == chen or not n.visible or not npcs.values().has(n) or _room_of(n) != world.room:
			continue
		if sg != null and _lv_of(n, sg) != int(sg.chen_lv):
			# 在别的层（妮芙在楼上、晨在一楼门口）：先沿楼梯走下来，走到晨身后（看得见地走，不在楼上淡没）
			if ff:
				_place(n, chen.position.x - float(chen.facing) * DOOR_GAP, world.room, int(sg.chen_lv))
				continue
			var tx2 := chen.position.x - float(chen.facing) * _side_gap(n, DOOR_GAP)
			_lv_walk(n, sg, int(sg.chen_lv), tx2, {"speed": 200.0, "wait": false})
			climbers.append(n)
			continue
		var dx: float = n.position.x - chen.position.x
		if absf(dx) > DOOR_GATHER:
			continue
		var side := -float(chen.facing) if absf(dx) < 1.0 else signf(dx)
		var w: Vector2 = world.walls(chen.position.x)
		var tx := clampf(chen.position.x + side * _side_gap(n, DOOR_GAP), w.x + 4.0, w.y - 4.0)     # 妮芙的鲸鱼壳宽：按身宽隔开
		if absf(tx - n.position.x) <= 2.0:
			continue
		if ff:
			_place(n, tx, world.room)
			continue
		n.walk_to(tx, clampf(absf(tx - n.position.x) / (DOOR_GATHER_SEC * 0.8), 60.0, 200.0))
		movers.append(n)
	var t := 0.0
	while (not movers.is_empty() and t < DOOR_GATHER_SEC) or (not climbers.is_empty() and t < DOOR_CLIMB_SEC):
		await StoryState.frame(get_tree())
		t += get_process_delta_time()
		movers = movers.filter(func(m): return is_instance_valid(m) and m.is_walking())
		climbers = climbers.filter(func(m): return is_instance_valid(m) and (m.has_meta("lv_climbing") or m.is_walking()))
	for m in movers:
		if is_instance_valid(m):
			m.stop()
	# 下完楼 / 还在路上：同一层了但还没到晨身边，再走一段（最多 DOOR_GATHER_SEC），不然过门时只好淡掉
	var late: Array = []
	for who in names:
		var n2 := npc(who)
		if n2 == null or n2 == chen or not n2.visible or not npcs.values().has(n2) or _room_of(n2) != world.room:
			continue
		if sg != null and _lv_of(n2, sg) != int(sg.chen_lv):
			continue
		var d2: float = n2.position.x - chen.position.x
		if absf(d2) <= maxf(DOOR_NEAR, _side_gap(n2, DOOR_GAP) + 6.0) - 4.0 or absf(d2) > DOOR_GATHER:
			continue
		var w3: Vector2 = world.walls(chen.position.x)
		n2.walk_to(clampf(chen.position.x + signf(d2) * _side_gap(n2, DOOR_GAP), w3.x + 4.0, w3.y - 4.0), 200.0)
		late.append(n2)
	var t2 := 0.0
	while not late.is_empty() and t2 < DOOR_GATHER_SEC:
		await StoryState.frame(get_tree())
		t2 += get_process_delta_time()
		late = late.filter(func(m): return is_instance_valid(m) and m.is_walking())
	print("DOOR_GATHER %s" % ", ".join(names.map(func(w): return "%s dx=%d" % [w, int(npc(w).position.x - chen.position.x) if npc(w) != null else 0])))


func _fade_nodes(list: Array, on: bool, sec: float) -> void:
	var tw := create_tween().set_parallel(true)
	for n in list:
		var nd: Node2D = n
		tw.tween_method(func(a: float): nd.modulate.a = (floorf(a * 4.0) if on else ceilf(a * 4.0)) / 4.0,
			0.0 if on else 1.0, 1.0 if on else 0.0, sec)
	await tw.finished


## 人（晨 + 同行的）按 4 档淡出 / 淡入
func _fade_people(on: bool, sec: float, with: Array) -> void:
	var list: Array = [chen]
	for w in with:
		var n := npc(str(w))
		if n != null:
			list.append(n)
	for f in follow:
		var n2 := npc(str(f))
		if n2 != null and not list.has(n2):
			list.append(n2)
	var tw := create_tween().set_parallel(true)
	for n in list:
		var nd: Node2D = n
		tw.tween_method(func(a: float): nd.modulate.a = (floorf(a * 4.0) if on else ceilf(a * 4.0)) / 4.0,
			0.0 if on else 1.0, 1.0 if on else 0.0, sec)
	await tw.finished


## 竖直平移（10-31 作者：两个房间不拼在一起、也不要夜空，渐黑再渐亮，但要看得出在往上 / 往下走）：
## 渐黑的同时镜头在这个房间里往上（下）移 PAN_SHIFT、平滑起步（人跟着画面一起黑）→ 黑着换房间 →
## 渐亮的同时镜头从新房间下（上）面 PAN_SHIFT 接着往上（下）移、减速停住（人已经站在那，跟着画面亮起来）。
## 两段距离、时长一样，sine 前半段 EASE_IN、后半段 EASE_OUT，接上的地方速度相等，看着是一口气。
## 镜头移出房间露出来的地方 level_forest 的房间上下盖黑会盖住（本来就在变黑）。
const PAN_SHIFT := 40.0
const PAN_HALF := 0.85
func _pan_to(room: String, x: float, with: Array, st: Dictionary) -> void:
	var to_st: Node2D = world.stage(room)
	var from_st: Node2D = world.cur_stage()
	var dir := -1.0 if from_st == null or to_st.origin.y < from_st.origin.y else 1.0      # -1：往上（镜头 y 变小）
	var c0: Vector2 = level.cam.position.round()
	level.camera_hold_at(c0)
	# 11-04 作者「妮芙……隐身」（连拍：上市集时晨和妮芙先在河岸上淡没，空河岸停了 0.6 秒才黑）：人不再自己先淡掉，
	# 跟着画面一起黑下去、一起亮起来
	level.camera_pan(c0 + Vector2(0, dir * PAN_SHIFT), PAN_HALF, Tween.EASE_IN)
	await level.fade_to_black(PAN_HALF)
	var target := Vector2(to_st.clamp_cam_x(x + chen.facing * 24.0), to_st.cam_y())
	_teleport(room, x, with, false)
	_fade_place(st)
	for n in [chen] + with.map(func(w): return npc(str(w))) + follow.keys().map(func(f): return npc(str(f))):
		if n == null:
			continue
		var stw = (n as Node2D).get_meta("sync_tw") if (n as Node2D).has_meta("sync_tw") else null
		if stw is Tween and (stw as Tween).is_valid():
			(stw as Tween).kill()             # 换房间时 sync_npc_vis 给同行的人起的 0.5 秒淡入：停掉，和画面一起亮起来（10-31 进市集妮芙先出现）
		(n as Node2D).modulate.a = 1.0
	var start := target - Vector2(0, dir * PAN_SHIFT)
	level.camera_hold_at(start)
	level.cam.position = start.round()
	level.camera_pan(target, PAN_HALF, Tween.EASE_OUT)
	await level.fade_from_black(PAN_HALF)
	level.camera_hold_at(target)
	level.camera_release()


## 边走边黑：朝出口那头走着黑下去，淡入时从那个房间的入口一头走进来
func _walk_fade(room: String, x: float, with: Array, st: Dictionary, arrive: float) -> void:
	var fs: Node2D = world.stage(world.room)
	var dir := float(chen.facing)
	if fs != null:
		var p: Dictionary = fs.portal_to_room(room)
		if str(p.get("edge", "")) == "left":
			dir = -1.0
		elif str(p.get("edge", "")) == "right":
			dir = 1.0
		else:
			dir = 1.0 if chen.position.x > fs.center().x else -1.0
	chen.auto_dir = dir
	for w in with:
		var n := npc(str(w))
		if n != null and npcs.values().has(n):
			# 走在晨前面的走快一点、后面的慢一点（晨起步就是 150）：晨追不上她、她也不撞到晨身上（10-31 人和人不叠）
			var ahead: bool = (n.position.x - chen.position.x) * dir > 0.0
			n.walk_to(n.position.x + dir * (160.0 if ahead else 90.0), 200.0 if ahead else 110.0)
	await level.fade_to_black(0.8)
	chen.auto_dir = 0.0
	var ts: Node2D = world.stage(room)
	var to := x if is_nan(arrive) else arrive
	var start := x
	if is_nan(arrive) and ts != null:
		var s_in := 1.0 if (x - ts.origin.x) < ts.size.x / 2.0 else -1.0     # 从近的那头走进来
		start = x - s_in * 40.0
		var w2: Vector2 = ts.walls()
		start = clampf(start, w2.x + 2.0, w2.y - 2.0)
	_tp_dir = signf(to - start) if absf(to - start) > 2.0 else 0.0
	_teleport(room, start, with, true)
	_fade_place(st)
	await _wait(0.2)
	await _arrive_walk(to)


# ----------------------------------------------------------------------- 第一关新版（11-02，见文件头）
const INNER_GD := "res://scripts/inner_voice.gd"
const ONE_WAY_EVERY := 6.0           # 往回走的潜意识字：两次之间至少隔几秒
const REWARD_SEC := 1.5              # 奖励动画多长
var _bark_hot := ""                 # 上一句 bark 是哪个点浮出来的
var _bark_at := NAN                  # 这一句 bark 浮在哪个 x 上（飞船）；NAN = 晨头顶
var _bark_y := 46.0
var _one_way_t := 99.0


## 潜意识字：scripts/inner_voice.gd（ch1-fx 做；静态入口 say / clear / node，自己挂一个 CanvasLayer 52 在当前场景下）。
## 脚本还没有 / 编译不过：打印 INNER 接着播。闪回停在黑屏上（hold）、又没 blackout 时，临时把字抬到闪回那一层上面。
func _inner(st: Dictionary) -> void:
	if ff or free_roam:
		return
	var gd := _inner_gd()
	if st.get("clear", false):
		if gd != null:
			gd.call("clear")
		return
	var sec := float(st.get("sec", 0.0))
	var total := sec
	if gd != null:
		var r = gd.call("say", str(st.get("zh", "")), str(st.get("en", "")), str(st.get("style", "drift")), sec)
		if r is float or r is int:
			total = maxf(float(r), sec)      # say 返回到完全消失的总秒数（包括只飘过一次的 drift）
		var n = gd.call("node")
		if n is CanvasLayer:
			(n as CanvasLayer).layer = FLASHBACK_LAYER + 1 if flashback_ui != null and _blackout == null else 52
	else:
		print("INNER %s: %s" % [str(st.get("style", "drift")), txt(st)])
	if st.get("wait", false) and total > 0.0:
		await _wait(total)                 # 自动玩也等满：上一句淡完才出下一句（不然两句叠在天上）


func _inner_gd() -> GDScript:
	if not ResourceLoader.exists(INNER_GD):
		return null
	var gd := load(INNER_GD) as GDScript
	if gd == null or not gd.can_instantiate():
		_warn_once("inner：%s 编译不过，只打印" % INNER_GD)
		return null
	return gd


## {"do": "blackout", "on": true / false}：闪回停在黑屏上（hold）时，换成关卡 UI 上面一层自己的黑（BLACKOUT_LAYER，
## 在纸 / 字幕 / 潜意识字下面），闪回那层先藏起来——这样黑着的时候还能看纸（paper_view 40）、云星闪（51）、潜意识字（52）；
## on: false = 闪回那层露回来（还是黑的），自己的黑去掉，接着 flashback_wake 睁眼。
const BLACKOUT_LAYER := 35
var _blackout: CanvasLayer = null


func _blackout_step(on: bool) -> void:
	if ff or free_roam:
		return
	var fl: CanvasLayer = flashback_ui.get_parent() as CanvasLayer if flashback_ui != null and is_instance_valid(flashback_ui) else null
	if on:
		if _blackout == null:
			_blackout = CanvasLayer.new()
			_blackout.name = "Blackout"
			_blackout.layer = BLACKOUT_LAYER
			var r := ColorRect.new()
			r.color = Color.BLACK
			r.mouse_filter = Control.MOUSE_FILTER_IGNORE
			r.size = Vector2(4000, 4000)
			r.position = Vector2(-1000, -1000)
			_blackout.add_child(r)
			level.add_child(_blackout)
		if fl != null:
			fl.visible = false
	else:
		if fl != null:
			fl.visible = true
		if _blackout != null and is_instance_valid(_blackout):
			_blackout.queue_free()
		_blackout = null


func _burn_closeup(id: String) -> void:
	var texture := Inventory.icon(id)
	if texture == null:
		return
	dlg.close_box()
	var layer := CanvasLayer.new()
	layer.layer = 54
	level.add_child(layer)
	var capture := BackBufferCopy.new()
	capture.copy_mode = BackBufferCopy.COPY_MODE_VIEWPORT
	layer.add_child(capture)
	var backdrop := ColorRect.new()
	backdrop.size = Vector2(480, 270)
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var shader := Shader.new()
	shader.code = """
		shader_type canvas_item;
		uniform sampler2D burn_screen : hint_screen_texture, filter_nearest;
		uniform float amount = 0.0;
		void fragment() {
			vec3 rgb = texture(burn_screen, SCREEN_UV).rgb;
			float grey = dot(rgb, vec3(0.2126, 0.7152, 0.0722));
			COLOR = vec4(mix(rgb, vec3(grey * 0.58), amount), 1.0);
		}
	"""
	var material := ShaderMaterial.new()
	material.shader = shader
	backdrop.material = material
	layer.add_child(backdrop)
	var item := Sprite2D.new()
	item.texture = texture
	item.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	item.position = Vector2(240, 134)
	var zoom := minf(6.0, 82.0 / maxf(texture.get_width(), texture.get_height()))
	item.scale = Vector2.ONE * zoom * 0.65
	item.modulate.a = 0.0
	layer.add_child(item)
	var display := layer.create_tween().set_parallel().set_speed_scale(3.0 if auto != "" else 1.0)
	display.tween_method(func(value: float): material.set_shader_parameter("amount", value), 0.0, 1.0, 0.38)
	display.tween_property(item, "modulate:a", 1.0, 0.38)
	display.tween_property(item, "scale", Vector2.ONE * zoom, 0.72).set_trans(Tween.TRANS_SINE)
	display.tween_method(func(turn: float): item.scale.x = zoom * maxf(0.12, absf(cos(turn))), 0.0, TAU, 0.78).set_delay(0.75)
	await display.finished
	_sfx({"name": "fire_flare", "db": -8.0})
	var fire := layer.create_tween().set_parallel().set_speed_scale(3.0 if auto != "" else 1.0)
	for n in 24:
		var ember := ColorRect.new()
		ember.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ember.size = Vector2.ONE * (2 + n % 4)
		ember.position = item.position + Vector2(float(n * 17 % 55 - 27), float(n * 11 % 26))
		ember.color = Color("#ffcc77") if n % 3 == 0 else Color("#e66d3b")
		ember.modulate.a = 0.0
		layer.add_child(ember)
		var delay := float(n % 8) * 0.035
		fire.tween_property(ember, "modulate:a", 0.95, 0.08).set_delay(delay)
		fire.tween_property(ember, "position", ember.position + Vector2(float(n % 9 - 4) * 4.0, -42.0 - float(n % 5) * 7.0), 0.65).set_delay(delay)
		fire.tween_property(ember, "modulate:a", 0.0, 0.4).set_delay(delay + 0.24)
	fire.tween_property(item, "modulate", Color(0.6, 0.19, 0.06, 0.0), 0.66).set_delay(0.1)
	fire.tween_property(item, "scale", Vector2.ONE * zoom * 0.56, 0.68)
	await fire.finished
	var restore := layer.create_tween()
	restore.tween_method(func(value: float): material.set_shader_parameter("amount", value), 1.0, 0.0, 0.38)
	await restore.finished
	layer.queue_free()


func _burn_held(st: Dictionary) -> void:
	var total := 0
	var names: Array = []
	var first := ""
	var list: Array = st.get("items", []).duplicate()
	if st.has("kind"):
		for id0 in Inventory.owned:
			if str(Inventory.item(id0).get("fuel_kind", "")) == str(st["kind"]):
				list.append(id0)          # "kind": "unrelated" = 背包里所有这一类的（支线带来的也算）
	for it in list:
		var id := str(it)
		if not Inventory.has(id):
			continue
		if level.chapter == "flight1" and not ff:
			await _burn_closeup(id)
		Inventory.remove(id)
		total += fuel_of(id)
		StoryState.set_flag("burned_" + id)
		if first == "":
			first = id
		var nm := txt(Inventory.item(id).get("name", id))
		if not names.has(nm):
			names.append(nm)
	level.on_inventory_changed()
	if total <= 0:
		return
	_fuel_step({"add": total})
	print("FUEL burn_held %s: +%d → %d/%d" % [",".join(list), total, StoryState.fuel(), StoryState.fuel_need()])
	if not ff:
		var tt: String = I18n.t("gave_item") % ("、" if I18n.is_zh() else ", ").join(names)
		if UITheme.font().get_string_size(tt, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x > 420.0:
			tt = I18n.pick({"zh": "交出 %d 件东西", "en": "Handed over %d items"}) % list.size()   # 11-04 --qa_live：名字连起来出屏
		dlg.toast(Inventory.icon(first), tt)
		await _wait(0.6)


## hotspot 的 scene 只有 bark 台词：返回那几句（不然 []）
func _bark_only(sid: String) -> Array:
	var out: Array = []
	for st in scenes.get(sid, []):
		if not (st is Dictionary and st.has("say") and st.get("bark", false)):
			return []
		out.append(st)
	return out


## 剧本顶层 one_way（拿回背包以后不能回头）：world.walls 按它挪左墙；顶着往回走浮出潜意识字
func one_way_on() -> bool:
	var ow = data.get("one_way", {})
	return ow is Dictionary and not ow.is_empty() and StoryState.has(str(ow.get("after", ""))) \
		and not StoryState.has(str(ow.get("until", "")))


func _update_one_way(delta: float) -> void:
	_one_way_t += delta
	if ff or free_roam or busy or world.room != "forest" or not one_way_on() or _one_way_t < ONE_WAY_EVERY:
		return
	var w: Vector2 = world.walls(chen.position.x)
	if chen.position.x > w.x + 24.0 or chen.facing > 0:
		return
	if chen._vel > 0.0 or level._wall_block:
		_one_way_t = 0.0
		var ow: Dictionary = data["one_way"]
		_inner({"zh": ow.get("zh", ""), "en": ow.get("en", ""), "style": "fade", "sec": 3.0})


## 背包查看（剧本顶层 item_views）：这件东西现在按「查看」播哪段；"" = 没有
func item_view(id: String) -> String:
	for v in data.get("item_views", []):
		if v is Dictionary and str(v.get("item", "")) == id and scenes.has(str(v.get("scene", ""))) \
				and StoryState.all_of(v.get("need", [])) and StoryState.none_of(v.get("not", [])):
			return str(v["scene"])
	return ""


## 自动玩 / 跳节拍：背包里有、现在能看的那件（{item, scene}；没有 = {}）
func pending_view() -> Dictionary:
	if busy:
		return {}
	for v in data.get("item_views", []):
		if v is Dictionary and Inventory.has(str(v.get("item", ""))):
			var sc := item_view(str(v["item"]))
			if sc != "" and not played.has(sc):
				return {"item": str(v["item"]), "scene": sc}
	return {}


## 剧本顶层 bag_lock {from, until}：背包还没拿回来（背包按钮、Tab 都不出来）
func bag_locked() -> bool:
	var bl = data.get("bag_lock", {})
	return bl is Dictionary and not bl.is_empty() and StoryState.has(str(bl.get("from", ""))) \
		and not StoryState.has(str(bl.get("until", "")))


## 奖励动画：东西从晨手里升到头顶、放大成两倍，一圈光点转一圈，停一下再淡掉（图 = 物品图标，或 tex + region 截一块）
func _reward(st: Dictionary) -> void:
	if ff or free_roam:
		return
	var tex: Texture2D = null
	if st.has("item"):
		tex = Inventory.icon(str(st["item"]))
	elif ResourceLoader.exists(str(st.get("tex", ""))) or FileAccess.file_exists(str(st.get("tex", ""))):
		tex = load(str(st["tex"])) if ResourceLoader.exists(str(st["tex"])) else WORLD_GD._raw_png(str(st["tex"]))
		var rg = st.get("region", null)
		if rg is Array and rg.size() == 4:
			var at := AtlasTexture.new()
			at.atlas = tex
			at.region = Rect2(float(rg[0]), float(rg[1]), float(rg[2]), float(rg[3]))
			tex = at
	if tex == null:
		return
	_sfx({"name": str(st.get("sfx", "reward")), "db": -4.0})
	var fx := Control.new()
	fx.mouse_filter = Control.MOUSE_FILTER_IGNORE
	fx.set_meta("t", 0.0)
	dlg.add_child(fx)
	var sz := tex.get_size()
	var dur := REWARD_SEC * (0.6 if auto != "" else 1.0)
	fx.draw.connect(func():
		var t: float = fx.get_meta("t")
		var k := clampf(t / 0.35, 0.0, 1.0)
		var rise := 1.0 - pow(1.0 - k, 3.0)                   # 先快后慢升上去
		var left: Vector2 = level.cam_left()
		var zk: float = level.cam.zoom.x
		var hand: Vector2 = (chen.position - left + Vector2(chen.facing * 6.0, -24.0)) * zk
		var c := (hand + Vector2(0, -52.0 * rise)).round()       # 升到头顶上方（到顶放大两倍后底边也不盖到头发；11-04 作者「物品挡住面部」）
		var big := 1 if k < 1.0 else 2                       # 整数倍放大：到顶那一下变两倍
		var fade := clampf((dur - t) / 0.3, 0.0, 1.0)
		var step := floorf(t / 0.1)                           # 光点 100ms 一格转
		if k >= 1.0:
			var ring := clampf((t - 0.35) / 0.3, 0.0, 1.0)
			if ring < 1.0:
				fx.draw_arc(c, 6.0 + ring * 18.0, 0.0, TAU, 24, Color(1.0, 0.95, 0.75, (1.0 - ring) * 0.8), 1.0)
			for i in 8:
				var a := TAU * (float(i) / 8.0) + step * 0.2
				var r := 15.0 + (2.0 if int(step + i) % 2 == 0 else 0.0)
				var q := (c + Vector2(cos(a), sin(a)) * r).round()
				var col := Color(1.0, 0.93, 0.62, 0.9 * fade)
				fx.draw_rect(Rect2(q, Vector2(1, 1)), col)
				if (int(step) + i) % 3 == 0:
					fx.draw_rect(Rect2(q + Vector2(-1, 0), Vector2(3, 1)), col)
					fx.draw_rect(Rect2(q + Vector2(0, -1), Vector2(1, 3)), col)
		var d := sz * big
		fx.draw_texture_rect(tex, Rect2((c - d / 2.0).round(), d), false, Color(1, 1, 1, fade)))
	var t0 := 0.0
	while t0 < dur and is_instance_valid(fx):
		await StoryState.frame(get_tree())
		t0 += get_process_delta_time()
		fx.set_meta("t", t0)
		fx.queue_redraw()
	if is_instance_valid(fx):
		fx.queue_free()


## {"do": "prop", ..., "fade": 秒}：物件换到这个状态的时候淡进来（分四档，南桥一路亮起来的脚印；读档直接是亮的）
func _prop_fade_in(id: String, sec: float) -> void:
	var pid: String = world.prop_id(id)
	var sr: String = world.stage_of_prop(pid)
	var sg: Node2D = world.stage(sr) if sr != "" else null
	var s: Sprite2D = sg.object(pid) if sg != null else null
	if s == null or sec <= 0.0:
		return
	s.modulate.a = 0.0
	var tw := s.create_tween()
	tw.tween_method(func(k: float): s.modulate.a = ceilf(k * 4.0) / 4.0, 0.0, 1.0, sec)


# ----------------------------------------------------------------------- 小游戏 {"do": "mechanic"}
func _mechanic(st: Dictionary) -> void:
	var mid := str(st.get("id", ""))
	var path := "res://scripts/%s.gd" % mid
	if not ResourceLoader.exists(path):
		_warn_once("mechanic：脚本 %s 还没有，当它玩完了" % path)
		_mech_done(mid)
		return
	var gd := load(path) as GDScript
	if gd == null or not gd.can_instantiate():
		_warn_once("mechanic：脚本 %s 编译不过，当它玩完了" % path)
		_mech_done(mid)
		return
	var m = gd.new()
	if ff:
		if m.has_method("ff"):
			m.ff(self, st)
		_mech_done(mid)
		return
	if not st.get("wait", true):
		_mech_bg(m, mid, st)                 # 不等（奔跑时的字幕）：边播边往下走
		return
	print("MECH %s start" % mid)
	mech_running = mid
	mech_node = m
	if auto != "":
		if m.has_method("auto"):
			await m.auto(level, world, self, st)
		elif m.has_method("ff"):
			m.ff(self, st)
	elif m.has_method("run"):
		await m.run(level, world, self, st)
	mech_running = ""
	mech_node = null
	if m.get("quitted") == true:
		_mech_quit = true
		print("MECH %s returned (quit)" % mid)
		return
	_mech_done(mid)
	print("MECH %s returned" % mid)


func _mech_bg(m, mid: String, st: Dictionary) -> void:
	print("MECH %s start (wait:false)" % mid)
	if auto != "" and m.has_method("auto"):
		await m.auto(level, world, self, st)
	elif auto != "" and m.has_method("ff"):
		m.ff(self, st)
	elif m.has_method("run"):
		await m.run(level, world, self, st)
	_mech_done(mid)
	print("MECH %s returned" % mid)


func _mech_done(mid: String) -> void:
	var p := mech_load(mid)
	p["_done"] = true
	mech_save(mid, p)


func mech_load(mid: String) -> Dictionary:
	var v = JSON.parse_string(str(StoryState.props.get(MECH_PREFIX + mid, "{}")))
	return v if v is Dictionary else {}


func mech_save(mid: String, d: Dictionary) -> void:
	StoryState.set_prop(MECH_PREFIX + mid, JSON.stringify(d))


## 小游戏里播一串剧本步骤（say / walk / anim / prop……），播完返回（goto / if 之类跳 scene 的步骤：返回那个 scene 名，不跟过去）
func run_steps(steps: Array) -> String:
	for st in steps:
		if st is Dictionary:
			var g: String = await _step(st)
			if g != "":
				return g
	return ""


## 临时加几个可互动的点，等玩家互动其中一个：返回 {id, item}
func wait_interact(spots: Array) -> Dictionary:
	if spots.is_empty():
		return {"id": "", "item": ""}
	_mech_spots.clear()
	for sp in spots:
		if not sp is Dictionary:
			continue
		var sid := str(sp.get("id", ""))
		var h := {"id": "_mech_" + sid, "_mech": sid, "at": sp.get("at", 0), "room": str(sp.get("room", world.room)),
			"label": sp.get("label", {"zh": sid}), "scene": ""}
		if sp.has("range"):
			h["range"] = sp["range"]
		if sp.get("beacon", false):
			h["beacon"] = true                # 远远就有一个淡淡的小箭头（河岸打捞：漂着的东西在哪一眼看得到）
		var acc := {}
		for it in sp.get("accepts", []):
			acc[str(it)] = "__mech:" + sid
		if not acc.is_empty():
			h["accepts"] = acc
		_mech_spots.append(h)
	hotspots.defs.append_array(_mech_spots)
	_mech_hit = {}
	mech_wait = true
	var was_free := free_walk
	busy = false
	free_walk = false
	level.story_end()
	hotspots.active = true
	while _mech_hit.is_empty():
		await mech_hit_sig
	mech_wait = false
	for h in _mech_spots:
		hotspots.defs.erase(h)
	_mech_spots.clear()
	busy = true
	free_walk = was_free
	hotspots.active = false
	level.story_begin(false)
	return _mech_hit


func _mech_resolve(sid: String, item: String) -> void:
	if not mech_wait:
		return
	_mech_hit = {"id": sid, "item": item}
	mech_hit_sig.emit()


## 特写面板：返回点到的 zone id（关掉 = ""）
func closeup(spec: Dictionary) -> String:
	if ff:
		return ""
	var ai := -2
	if auto != "":
		ai = -1
		var zs: Array = spec.get("zones", [])
		if not zs.is_empty():
			var opts: Array = []
			for z in zs:
				opts.append({"id": str(z.get("id", "")), "scene": str(z.get("scene", ""))})
			ai = _auto_pick({"options": opts})
			if ai < 0 and not spec.get("close", true):
				ai = 0
	var r: String = await closeup_ui.open(spec, ai)
	return r


## --story_check：多房间章节的新步骤
func _validate_room_step(id: String, kind: String, st: Dictionary, refs: Dictionary) -> Array[String]:
	var out: Array[String] = []
	match kind:
		"todo_mechanic":
			out.append("info: scene %s：todo_mechanic %s 还没换成 mechanic（跳过）" % [id, st.get("id")])
		"mechanic":
			if st.has("quit_scene"):
				refs[str(st["quit_scene"])] = true
			var path := "res://scripts/%s.gd" % str(st.get("id", ""))
			if not ResourceLoader.exists(path):
				out.append("info: scene %s：mechanic 的脚本 %s 还没有（播到这里当它玩完了）" % [id, path])
			elif not (load(path) as GDScript).can_instantiate():
				out.append("scene %s：mechanic 的脚本 %s 编译不过" % [id, path])
			else:
				var m = (load(path) as GDScript).new()
				for fn in ["run", "auto", "ff"]:
					if not m.has_method(fn):
						out.append("scene %s：mechanic %s 没有 %s()" % [id, st.get("id"), fn])
				if m.has_method("check"):
					for l in m.check(self, st):
						var ls := str(l)
						if ls.begins_with("info:"):
							out.append("info: scene %s：mechanic %s：%s" % [id, st.get("id"), ls.trim_prefix("info:").strip_edges()])
						else:
							out.append("scene %s：mechanic %s：%s" % [id, st.get("id"), ls])
		"form":
			var n := npc(str(st.get("who", "")))
			if n == null or not n.has_method("set_form"):
				out.append("scene %s：form 的 who %s 不是通用角色" % [id, st.get("who")])
		"follow":
			if npc(str(st.get("who", ""))) == null:
				out.append("scene %s：follow 的 who 不认识 %s" % [id, st.get("who")])
		"pose":
			var pn := npc(str(st.get("who", "")))
			if pn == null or not npcs.values().has(pn):
				out.append("scene %s：pose 的 who %s 不是通用角色" % [id, st.get("who")])
		"water":
			if world.stage(str(st.get("room", ""))) == null:
				out.append("scene %s：water 的 room 不认识 %s" % [id, st.get("room")])
		"closeup":
			if str(st.get("img", st.get("id", ""))) == "":
				out.append("scene %s：closeup 没有 img" % id)
			elif CLOSEUP_GD.tex_path(str(st.get("img", st.get("id", ""))), str(st.get("state", ""))) == "":
				out.append("info: scene %s：特写图 closeup_%s 还没有（占位）" % [id, st.get("img", st.get("id", ""))])
			for z in st.get("zones", []):
				var zs := str(z.get("scene", ""))
				if zs != "":
					refs[zs] = true
					if not scenes.has(zs):
						out.append("scene %s：closeup zone %s 的 scene %s 不存在" % [id, z.get("id"), zs])
	return out


## 走到房间一头的入口（level_forest.gd 的 _update_stage_portal）：用 room.json portals 那一项的转场换过去
func portal_room(pt: Dictionary) -> void:
	if busy:
		return
	var room := str(pt.get("to", ""))
	var ts: Node2D = world.stage(room)
	if ts == null:
		return
	var x := NAN
	if str(pt.get("at", "")) != "" and world.has_marker(str(pt["at"])):
		x = float(world.resolve(str(pt["at"]))["x"])
	else:
		var w: Vector2 = ts.walls()
		x = w.x + 30.0 if str(pt.get("edge", "right")) == "right" else w.y - 30.0
	busy = true
	hotspots.active = false
	level.story_begin(false)
	var with: Array = []
	for f in follow:
		var n := npc(str(f))
		if n != null and n.visible and str(_npc_room.get(n.name, "")) == world.room:
			with.append(str(f))
	await _fade_to({"room": room, "at": x, "kind": str(pt.get("kind", "walk_fade")), "with": with})
	busy = false
	level.story_end()



## 起飞（河流篇 depart）：11-02 作者「斜着带着地下的土飞走了，学一学第一个场景是怎么起飞的」→ 和森林起飞（level_forest.story_takeoff）同一套：
##   河岸那架船本来就是 ship_lift.png 第 0 帧（-17°）贴的（tools/river_city_art.py plane_frames，贴在画布 LIFT_AT），
##   起飞时物件换成 launched（只剩桩和绳），原地换上同一张 ship_lift 精灵，按角度换帧（不旋转图片）：
##   1. 预热：余火闪两下亮住、1 像素抖越来越密、暖红热光慢慢亮  2. 竖直升（smoothstep），机头从 -17° 摆平到 -4°，热光跟着竖直速度
##   3. 悬停 1 像素起伏  4. 尾焰两帧交替，机头抬到 9°，沿机头方向 ease-in 加速飞出画面 → 淡到黑。泛光一律第一关的暖红。
const SHIP_GLOW := preload("res://scripts/ship_glow.gd")
const TAKEOFF_PLANE := "river_bank_plane"
const T_LIFT_TEX := preload("res://art/level1/ship_lift.png")
const T_LIFT_META := "res://art/level1/ship_lift.json"
const T_LIFT_N := 28
const T_ANG0 := -17
const T_FRAME := Vector2i(204, 120)
const T_LIFT_AT := Vector2(52, 16)          # ship_lift 帧左上角在河岸船物件画布里的位置（70 - 18, 18 - 2）
const T_ENGINE := Vector2(72, -1)


func _stage_takeoff() -> void:
	var sg: Node2D = world.cur_stage()
	var plane: Sprite2D = sg.object(TAKEOFF_PLANE) if sg != null else null
	if plane == null or not plane.visible or ff:
		return
	level.camera_hold_at(level.cam.position)
	var lift := Sprite2D.new()
	lift.texture = T_LIFT_TEX
	lift.hframes = T_LIFT_N
	lift.vframes = 4
	lift.centered = false
	lift.offset = -Vector2(T_FRAME / 2)
	lift.z_index = plane.z_index
	lift.material = plane.material
	plane.get_parent().add_child(lift)
	var c0 := plane.position + plane.offset + T_LIFT_AT + Vector2(T_FRAME / 2)
	var hulls := {}
	var meta = JSON.parse_string(FileAccess.get_file_as_string(T_LIFT_META)) if FileAccess.file_exists(T_LIFT_META) else null
	if meta is Dictionary:
		var hd: Dictionary = meta.get("hull", {})
		for k in hd:
			var tops := PackedInt32Array()
			var bots := PackedInt32Array()
			for v in hd[k].get("top", []):
				tops.append(int(v) - T_FRAME.y / 2 if int(v) >= 0 else -1)
			for v in hd[k].get("bot", []):
				bots.append(int(v) - T_FRAME.y / 2 if int(v) >= 0 else -1)
			hulls[int(k)] = [tops, bots]
	var glow: Node2D = SHIP_GLOW.new()
	glow.full_speed = 20.0
	lift.add_child(glow)
	glow.heat = 1.0
	glow.heat_goal = 1.0
	var st := {"ang": float(T_ANG0), "row": 0, "pos": c0, "hull": 999}
	var show := func():
		var ai := clampi(roundi(float(st["ang"])), T_ANG0, T_ANG0 + T_LIFT_N - 1)
		lift.frame = int(st["row"]) * T_LIFT_N + (ai - T_ANG0)
		lift.position = (st["pos"] as Vector2).round()
		if ai != int(st["hull"]) and hulls.has(ai):
			st["hull"] = ai
			glow.set_hull(-T_FRAME.x / 2, hulls[ai][0], hulls[ai][1])
	show.call()
	world.set_prop(TAKEOFF_PLANE, "launched")          # 同一帧换：画布里的船和 ship_lift 第 0 帧逐像素一样，不跳
	var pb: Node2D = level.get("puffs_back")
	# 1. 预热
	level._sfx("engine_start", -4.0)
	var t := 0.0
	var ign := [0.15, 0.25, 0.4, 0.5, 0.62]
	while t < 1.5:
		await StoryState.frame(get_tree())
		var d := get_process_delta_time()
		t += d
		var on := 0
		for a in ign:
			if t >= a:
				on = 1 - on
		st["row"] = on
		st["pos"] = c0 + Vector2(randi_range(-1, 1) if randf() < 0.08 + 0.4 * t / 1.5 else 0, 0)
		glow.strength = 0.55 * smoothstep(0.2, 1.0, t / 1.5)
		glow.step(d)
		show.call()
	st["row"] = 1
	glow.hold = 0.55
	glow.hold_goal = 0.55
	# 2. 竖直升、机头摆平
	t = 0.0
	var yp := c0.y
	while t < 2.3:
		await StoryState.frame(get_tree())
		var d2 := get_process_delta_time()
		t += d2
		var k := clampf(t / 2.3, 0.0, 1.0)
		var y := c0.y - 30.0 * smoothstep(0.0, 1.0, k)
		st["ang"] = lerpf(float(T_ANG0), -4.0, smoothstep(0.25, 1.0, k))
		st["pos"] = Vector2(c0.x, y)
		glow.drive((y - yp) / maxf(d2, 0.001), d2)
		yp = y
		show.call()
	# 3. 悬停
	var hv: Vector2 = st["pos"]
	glow.hold_goal = 0.3
	t = 0.0
	while t < 0.7:
		await StoryState.frame(get_tree())
		var d3 := get_process_delta_time()
		t += d3
		st["pos"] = Vector2(hv.x, hv.y - roundf(sin(t / 0.7 * PI)))
		glow.drive(0.0, d3)
		show.call()
	st["pos"] = hv
	# 4. 尾焰、抬头、加速飞走
	level._sfx("ship_whoosh", -5.0, 0.85)
	level._sfx("engine_boost", -8.0)
	var eng := func() -> Vector2: return lift.position + T_ENGINE.rotated(deg_to_rad(float(st["ang"])))
	if pb != null:
		pb.add_source("trail", eng.call(), 26.0, pb.PRESETS.trail)
		pb.add_source("trail_sparks", eng.call(), 6.0, pb.PRESETS.ember)
	t = 0.0
	var a0: float = st["ang"]
	var p: Vector2 = st["pos"]
	var fading := false
	while t < 5.0:
		await StoryState.frame(get_tree())
		var d4 := get_process_delta_time()
		t += d4
		st["row"] = 2 + int(t / 0.1) % 2
		st["ang"] = lerpf(a0, 9.0, smoothstep(0.0, 1.0, t / 1.6))
		var ar := deg_to_rad(float(st["ang"]))
		p += Vector2(-cos(ar), -sin(ar)) * 150.0 * t * t * d4
		st["pos"] = p
		glow.strength = move_toward(glow.strength, 0.0, 0.5 * d4)
		glow.step(d4)
		show.call()
		if pb != null:
			pb.set_source_pos("trail", eng.call())
			pb.set_source_pos("trail_sparks", eng.call())
		if t > 1.6 and not fading:
			fading = true
			level.fade_to_black(1.2)
		if lift.global_position.x < level.cam.position.x - 380.0 or lift.global_position.y < level.cam.position.y - 260.0:
			break
	if pb != null:
		pb.remove_source("trail")
		pb.remove_source("trail_sparks")
	lift.queue_free()


## prop 带 "glide"（秒）：物件换状态不闪现，带着暖红的反重力泛光平滑挪过去（11-02 作者：飞机拖上岸是闪现的，很奇怪）。
##   {"do": "prop", "id": "river_bank_plane", "state": "beached", "glide": 2.0, "from": [-64, 5]}
##   from = 新状态那一帧的图，开始时相对它最终位置的偏移（两帧里船画的位置不一样，用它对齐旧帧里的船）。
##   预热：泛光亮起、旧帧 1 像素抖 → 一边微微抬起一边顺着 smoothstep 挪到位（抬起是正弦拱，最高 LIFT 像素），
##   开头 35% 旧帧和新帧 4 档交叉淡变 → 到位后泛光慢慢熄。不换帧速，只挪位置。
const GLIDE_LIFT := 8.0

func _prop_glide(st: Dictionary) -> void:
	var id := str(st.get("id", ""))
	var to := str(st.get("state", ""))
	var sg: Node2D = world.cur_stage() if world.has_method("cur_stage") else null
	var spr: Sprite2D = sg.object(id) if sg != null else null
	if spr == null or ff or not spr.visible:
		world.set_prop(id, to)
		return
	var sec := maxf(0.3, float(st.get("glide", 2.0)))
	var fa: Array = st.get("from", [0, 0])
	var from := Vector2(float(fa[0]), float(fa[1]))
	var p0 := spr.position
	var c: Dictionary = sg.ocfg[id]
	var fw := int(c.get("w", spr.texture.get_width() / spr.hframes))
	var fh := int(c.get("h", spr.texture.get_height()))
	# 旧帧的替身：留在原处跟着一起挪、慢慢淡掉
	var ghost := Sprite2D.new()
	ghost.texture = spr.texture
	ghost.hframes = spr.hframes
	ghost.frame = spr.frame
	ghost.centered = spr.centered
	ghost.offset = spr.offset
	ghost.flip_h = spr.flip_h
	ghost.z_index = spr.z_index
	ghost.material = spr.material
	ghost.position = p0
	spr.get_parent().add_child(ghost)
	world.set_prop(id, to)
	spr.position = (p0 + from).round()
	spr.modulate.a = 0.0
	var glow: Node2D = SHIP_GLOW.new()
	spr.add_child(glow)
	glow.set_from_texture(spr.texture, Vector2.ZERO, Rect2i(spr.frame * fw, 0, fw, fh), 2)   # 绳子、桩子不发光
	glow.heat = 1.0
	glow.heat_goal = 1.0
	# 预热
	var t := 0.0
	while t < 0.6:
		var d := get_process_delta_time()
		t += d
		glow.strength = 0.5 * clampf(t / 0.5, 0.0, 1.0)
		glow.step(d)
		ghost.position = p0 + Vector2(0, -1 if fmod(t, 0.16) < 0.08 and t > 0.3 else 0)
		await StoryState.frame(get_tree())
	# 挪过去
	t = 0.0
	var prev := spr.position.y
	glow.hold_goal = 0.8
	while t < sec:
		var d2 := get_process_delta_time()
		t += d2
		var k := clampf(t / sec, 0.0, 1.0)
		var e := k * k * (3.0 - 2.0 * k)
		var off := from * (1.0 - e) + Vector2(0, -GLIDE_LIFT * sin(PI * e))
		spr.position = (p0 + off).round()
		ghost.position = (p0 + off - from).round()
		var a := floorf(clampf(k / 0.35, 0.0, 1.0) * 4.0) / 4.0
		spr.modulate.a = a
		ghost.modulate.a = 1.0 - a
		glow.heat_goal = 1.0
		glow.drive((spr.position.y - prev) / maxf(d2, 0.001), d2)
		prev = spr.position.y
		await StoryState.frame(get_tree())
	spr.position = p0
	spr.modulate.a = 1.0
	ghost.queue_free()
	# 泛光慢慢熄
	glow.hold_goal = 0.0
	t = 0.0
	while t < 0.8:
		var d3 := get_process_delta_time()
		t += d3
		glow.hold = 0.0
		glow.strength = move_toward(glow.strength, 0.0, d3 / 0.8)
		glow.heat_goal = 1.0
		glow.step(d3)
		await StoryState.frame(get_tree())
	glow.queue_free()



# ----------------------------------------------------------------------- 自动玩：多房间找路
## 这一房间没有不换地方就能推进的点了：找「还有事做」的房间（有会推进剧情、不换地方的点），按房间之间的出口（scene 里 fade_to 到别的房间的 hotspot）
## 广度优先找路，返回第一步要点的出口。出口本身不受「来过」限制（来回走不算进展）。
func _multi_plan() -> Dictionary:
	var want := {}
	var exits := {}                     # 房间 → [{p, to}]
	var rooms: Array = world.stages.keys()
	if world.cockpit != null:
		rooms.append("cockpit")
	for r in rooms:
		exits[r] = []
		for p in hotspots.available(str(r)):
			var h: Dictionary = p["h"]
			if hotspots.is_enter(h) and not bool(h.get("cutscene", false)):
				continue
			if h.has("_side") and not (side_auto() and not ff):
				continue                       # 支线点不算「这个房间有事做」（不然多房间章节自动玩会在两个支线房间之间来回走）
			var sc := str(h.get("scene", ""))
			var to := _dest_room(sc, str(r))
			var id := str(h.get("id", ""))
			var fresh := not (_visited.has(id) and int(_visited[id]) == StoryState.progress())
			if to != "" and to != str(r):
				if _would_progress_flags(sc) or (ff and _ff_target != "" and _leads_to(sc, _ff_target)):
					want[str(r)] = true           # 换地方的同时会推进剧情（设新 flag）：这个房间就有事做
				(exits[r] as Array).append({"p": p, "to": to})
			elif is_progress_hotspot(h) and fresh:
				want[str(r)] = true
	if want.is_empty():
		return {}
	var start: String = world.room
	var prev := {start: null}
	var q: Array = [start]
	while not q.is_empty():
		var r: String = q.pop_front()
		if want.has(r) and r != start:
			break
		for e in exits.get(r, []):
			var to: String = e["to"]
			if not prev.has(to):
				prev[to] = {"from": r, "e": e}
				q.append(to)
	if want.has(start):
		# 这间就有「换地方也推进剧情」的出口：直接点它
		for e in exits.get(start, []):
			if _would_progress_flags(str(e["p"]["h"].get("scene", ""))):
				return {"kind": "hotspot", "x": float(e["p"]["x"]), "p": e["p"], "exit": true}
	var goal := ""
	for r in want:
		if prev.has(r) and str(r) != start:
			if goal == "" or _hops(prev, str(r)) < _hops(prev, goal):
				goal = str(r)
	if goal == "":
		return {}
	var cur := goal
	while prev[cur] != null and str(prev[cur]["from"]) != start:
		cur = str(prev[cur]["from"])
	var ed: Dictionary = prev[cur]["e"]
	return {"kind": "hotspot", "x": float(ed["p"]["x"]), "p": ed["p"], "exit": true}


func _hops(prev: Dictionary, r: String) -> int:
	var n := 0
	while prev.get(r) != null and n < 50:
		r = str(prev[r]["from"])
		n += 1
	return n


## scene 一路下去第一个 fade_to 到哪个房间（没有 = ""）
func _dest_room(sc: String, from: String) -> String:
	for sid in _reach(sc, {}):
		for st in scenes.get(sid, []):
			if st is Dictionary and str(st.get("do", "")) == "fade_to":
				return str(st.get("room", from))
	return ""


## 只看「设新 flag / 给新东西 / 小游戏」（不算换地方）
func _would_progress_flags(s: String, seen := {}) -> bool:
	if seen.has(s) or not scenes.has(s):
		return false
	seen[s] = true
	for st in scenes[s]:
		if not st is Dictionary:
			continue
		match str(st.get("do", "")):
			"flag", "count":
				if st.has("set") and not StoryState.has(str(st["set"])):
					return true
			"give":
				if st.has("item") and not Inventory.has(str(st.get("item", ""))):
					return true
			"end_chapter":
				return true
			"mechanic":
				if not bool(mech_load(str(st.get("id", ""))).get("_done", false)):
					return true
			"goto":
				if _would_progress_flags(str(st.get("scene", "")), seen):
					return true
			"if":
				if _would_progress_flags(str(st.get("then", "")), seen) or _would_progress_flags(str(st.get("else", "")), seen):
					return true
			"choice", "pick":
				for o in st.get("options", []):
					if _would_progress_flags(str(o.get("scene", "")), seen):
						return true
	return false



## 下水 / 上水（10-30 作者：水面线漫过人 + 镜头平移不好看）：慢慢黑下去（带一声入水 / 出水）→ 黑着换房间 → 慢慢亮起来，
## 亮起来时已经在水底 / 岸上。和别的黑屏转场一样 0.8 秒黑、0.8 秒亮，正弦缓入缓出；人不淡，跟着画面一起黑
func _dive_fade(room: String, x: float, with: Array, st: Dictionary, down: bool) -> void:
	var nm := "splash_in" if down else "splash"
	if Time.get_ticks_msec() - int(_sfx_t.get(nm, -100000)) > 1500:
		_sfx({"name": nm, "db": -3.0})             # 剧本下水前自己放过 splash_in 的，不再叠一遍
	level.camera_hold_at(level.cam.position)
	await level.fade_to_black(0.8)
	_teleport(room, x, with, true)
	_fade_place(st)
	level.camera_release()
	level._snap_camera()
	await _wait(0.2)
	await level.fade_from_black(0.8)
