extends Control
## 剧本步骤 debris_steer（躲碎石）：{"do": "debris_steer", "id": "flight1_debris", "sec": 40, "fuel_per_bump": 1, "fuel_max_loss": 5}
## 约定见 docs/flight_sky_contract.md「debris_steer 改成上下躲」（10-29 作者定：游戏是侧视剖面、机头朝左，左右键像「前后」，
##   所以不再左右偏航，改成整艘船上下挪）。零门槛、不会失败、不显示倒计时、不标燃料。
##   碎石在船外背景里看得见地飞过来：从屏幕左边（机头方向）进来、往右飞过船（画在 cockpit.debris_layer：背景前、船后）。
## 10-30 改成一段有节奏、有变化的「波次」（作者：「小游戏也乏味」）：固定的一串波次（PLAN，按 sec / 40 缩放），每波都有一条安全通道
##   （船挪到哪个位置躲得开 = safe，单位是船的上下偏移，±_shift 以内）：
##     one   一块，贴着船身上沿（上道）或下沿（下道）：往另一边挪满就躲开（上道 → safe = +_shift）
##     pair  同一条道连着两块（「哒哒」），挪一次躲两块
##     gap   一排碎石竖着排成墙，中间留一道缝：缝 = 船挪到 safe 时船身上下各留 GAP_M 像素；墙从缝往上、往下一直排到屏幕边
##     final 结尾一波大的：GAP 墙连着三排、缝一排排换位置（蛇形），碎石更多、轰隆声更大；最后一排过去以后「穿出去」（_breakout）
##   顺序：上 → 下 → 上道两块 → 中间的缝 → 上下交替三块 → 偏上的缝 → 结尾三排（缝下、中、上蛇形）。两波换道之间至少隔 2.8 秒
##   （上一波还在船边上时下一波不会逼你往它那边挪）。
##   找通道（剧情姐原文：「根据碎石靠近的方位声和稳定的气流声寻找通道」）：
##     方位声：预告时响一声 nav_beep（碎石在上面音高高、在下面音低；一排墙响两声），碎石进屏幕「呼」一声从左边来（debris_pass_l，声像偏左），
##       擦过船以后往右走（debris_pass_r，声像偏右）。
##     气流声：有碎石来的时候一直有稳定的气流声（airflow_loop），音高跟着安全通道的高低（通道在上面音高）；
##       画面上安全通道那个高度、机头前面有几道淡淡的气流线往船这边流（AIR_C，很淡，不闪；碎石的划痕会闪）。
##       11-05 作者（「会突然往回一跳、撞到飞船前直接消失、整体移动」）：每道线是独立的粒子——出生时按当时的安全通道定自己的 y
##       和长度，之后只往右匀速飞，不回跳；飞到整条被船身挡住（debris_layer 在船后面）或出了屏幕右边才删，中途不消失；
##       通道换了只影响新出生的线，飞着的线不整体挪（_air_lines / _air_lines_step）。
##   预告：碎石擦到船之前 WARN（2）秒，左边那个高度上先出现一道划痕（两行虚线，越来越长、一闪一闪、往右 4 档变淡）
##     + 一个远远的小影子（3 → 7 像素，左上一点亮边）。墙只给离船近的那两块画划痕（其余的只是墙）。
##   擦边：碎石飞过船身、离船身不到 GRAZE 像素又没碰到 → 船外泛光闪一下（ship_glow 光强拉满再按原来的速度熄）+ 擦边的几颗火星 + 一声轻的「咻」。
##   玩家：↑ / ↓、W / S 按住让船上下挪；鼠标 / 触屏按住屏幕上半边 / 下半边一样。
##     按住时目标位置 cockpit.ship_goal 每秒走 _move 像素（最多 ±_shift）；船本身（cockpit.ship_dy）用弹簧追目标
##     （cockpit_room._ship_step：先缓起、再缓停、停下 1 像素回弹，不是匀速平移），挪动时船身周围亮起反重力泛光（scripts/ship_glow.gd）。
##     松手后目标留在原位，1.5 秒没按以后很慢地回中间（BACK 像素 / 秒）。
##     船挪 = level_forest.gd 的镜头反向偏移（晨、室内、物件一起动，背景不动）；步骤结束后 cockpit 自己慢慢回 0。
##   碰撞：碎石的图实际多大就按多大（四边各缩 2 像素）对 cockpit.hull() 的船身轮廓（每列上下沿 + 船现在的 ship_y）。
##   撞到：镜头晃一下 + 一声闷响（debris_bump），碎石弹开、4 档淡出；同一波（一排墙）只算一次：左上角燃料少 fuel_per_bump
##     （整段最多 fuel_max_loss，--story_check 核对：扣满以后放任何一件纪念品也补得上）；晨第 1、3、5 次撞时小声说一句（不锁人）。
##     不会输、没有命：撞了就晃一下，接着飞。
##   提示「↑ ↓  躲开碎石」：第一次按键以后或者 7 秒后淡出。
##   结束：撞了几次写进 StoryState 的物件状态（键 = id 去掉 _debris 再加 _bumps，flight1_debris → flight1_bumps），
##     不管结果如何都接着播剧情；打一行 COCKPIT 日志。
## 镜头拉远（10-30 作者：「躲避石头的时候飞船能不能缩小一点」「切远景……我觉得只是缩小」）：
##   一开始镜头从剖面拉远到船外（cockpit_room.far_out：外壳淡入 → 缓缓缩小，约 1.7 秒），整艘船变成 far_scale 倍（默认 FAR_K），
##   晨和舱里看不见；最后一排碎石过去、穿出去以后船先回中间（弹簧 + 泛光），再拉回剖面（倒着走同一条曲线），然后才接着播剧情。
##   10-31（作者：「正中间提前量有点不够」）：缩小的同时往右平移，停在屏幕宽度 FAR_X（73%，x 350）；碎石再慢 FAR_SLOW，
##   预告 = 进画面前 WARN_OFF 秒 + 从屏幕左边飞到船头的时间 → 进画面到撞上船头约 1.65 秒（原来约 0.8）。剧本 "far_x" / 命令行 --far_x= 能改。
##   远景里船小了：能挪 ±FAR_SHIFT（剖面里 ±SHIFT）、按住时目标每秒走 FAR_MOVE；碎石飞得慢一点（ROCK_V × (0.5 + 0.5 × 倍数)，
##   镜头远了，看起来就慢）；道、缝、碰撞、预告都按远景船的轮廓（cockpit.far_hull()）算。碎石图不缩（相对小船更大、更看得清）。
##   剧本参数 "far_scale"：0.55 ～ 0.93（取最接近的一档图）；1 = 不拉远，留在剖面里躲（原来的样子）。
##   命令行 --far_scale=0.75 临时盖过剧本（截图对比用）；--debris_full：自动玩也按真实时长和拉远速度播（截图 / 拍联系表用）。图不在（还没生成 ship_out/）时也留在剖面里。
## 自动玩（--story_auto）：每波预告一出就挪到它的安全通道（最早一波还没飞过船尾的那波），只播 PLAN_AUTO 两波，连拉远拉回 9 秒以内；
##   跳节拍（ff）：瞬间完成、0 次、直接回剖面；F8 自测：dev_skip 直接做完（直接回剖面）。
## 碎石图：art/cockpit/debris_a..e.png（tools/sky_art.py 生成，13～28 像素，暗色、左上亮边）；debris_f / g（< 8 像素）
##   当跟着飞的碎屑，不算碰撞；没有就用飞行测试的石头 / 程序画的占位。
## 黑窗听航道（终章 final_route，10-31 作者选的方案 A，docs/第三章计划.md 第四节）：剧本 "plan": "final" 换成 PLAN_FINAL——
##   前半段同上（看得见的碎石），然后 dark_on：进云层，窗外（船外背景 + 碎石）慢慢黑掉，船还亮着；接着几排 dark 墙：
##   缝只在上 / 中 / 下三条航道里（g = -1 / 0 / +1），碎石看不见、没有划痕预告和 nav_beep，提前 DARK_LEAD 秒就开始找。
##   靠听：船离安全航道越远，碎石的轰鸣（flight_rumble 循环）越响、气流声越小；挪进那条航道，轰鸣退下去、只剩平稳的气流声。
##   11-07 作者（「这真的是"听"吗，这不是看粒子特效吗」）：黑里一开始**不画气流线**，改成全靠声音——
##     轰鸣的方位：船在缝上面（撞的是上面那片碎石）轰鸣音高高，在缝下面音高低（上高下低，离得越远差得越多），越远越响
##       （进航道 -45 dB、偏一条道 -7 dB）；气流声反过来（进航道 -10、偏了 -30），音高按航道高低（上高下低）。
##     引擎变柔：进了安静航道，驾驶舱的引擎声（level._engine_hum）低 8 dB、音高降一点；偏了比平时还响一点、发紧。步骤完还原。
##     原来气流线 1.8 秒就出来、有铃也出，等于把答案画出来了，作废。
##   引路（方案 A 原文的兜底）：背包里还有铜铃（copper_bell）→ 铃声（bell_soft）按航道高低定音高（上高下低）隔一会儿响一下，
##   找久了（DARK_HINT1 秒还没进航道）更响更密；**有铃就永远不画气流线**。铜铃烧了 → 没有铃，DARK_HINT1 秒还没进航道
##   气流线才慢慢淡入（更明显的提示），DARK_HINT2 秒更亮。气流线本身（每道独立的粒子）没动，这里只管亮度。
##   撞到：碎石在黑里闪出来（画到黑幕上面）、晃一下、扣燃料（同一套上限），不会输。
##   自动玩在黑墙里先「听」DARK_AUTO_WAIT 秒再挪（--dark_wait=秒 改，--no_bell 当铜铃烧了），每 0.5 秒打一行 DARK_AUDIO。
##   最后一排（last）过去 = 穿出云层：黑幕慢慢退掉（云开）。自动玩：PLAN_AUTO_DARK（一块 + 一排黑墙），提前量 DARK_LEAD_AUTO。
## 11-08 作者（「飞船需要进一步缩小，屏幕可以更早的显示障碍物，增加难度」「同时操作左右，维修和上下」「维修不需要任何剧情停顿」）：
##   FAR_K 0.65 → 0.55、FAR_X 0.73 → 0.8（碎石进画面到撞船头约 1.9 秒）、FAR_SLOW 0.9 → 1.0、PLAN 9 波 → 11 波；
##   剧本 "leaks"：躲的同时船舱里漏气，←→ 走、按住 E 修、↑↓ 照样躲（见 LEAK_* 上面的说明）。飞行一的漏气不再是躲完以后停下来的剧情段。
##   二改（作者：「保持这个视角，但是飞机缩小」）：有 leaks 时不拉到船外，剖面整体缩到 VIEW_Z、挪到屏幕 VIEW_X（碎石提前量约 1.7 秒），
##   晨本人走去窗 / 副驾驶座 / 工具箱修；远景（far）参数只剩终章在用。
## 11-08 飞行一新版（作者：「永燃之木本身可以提供无尽的能量……先开一段时间，燃料完全不会降低，之后剧情杀，被大陨石砸中……
##   永燃之木掉落了……必须要烧新的燃料……燃料本身是一直在烧的，如果烧到底，飞机就坠毁了，会丢失所有的材料，所以要尽可能的不被碰到，
##   碰到就会加速燃料泄漏一段时间……燃料上有一个绿色安全竖线，如果低于了这个线，就说明需要重新添加一次燃料了」；
##   坠毁 = 坏结局；低于安全线按键进货舱；漏气维修保留、两套一起；飞够一段距离结束）：
##   "plan": "cruise"：永燃之木供能的那一段——几波轻的碎石（不扣燃料），最后一波 meteor = 躲不开的一整排（缝也塞满），
##     撞上：大晃、闪白、轰隆，设 flag flight1_meteor，步骤收尾（剧本接着演永燃之木掉出去）。
##   燃料模式（写了 "drain"）：燃料每秒少 drain；撞一下之后 hit_sec 秒里每秒再多少 hit_drain；每个没修的漏点每秒再多少 leak_drain。
##     燃料低于 "safe"（绿线，fuel_bar.gd 画）：船下方闪提示「按 F 去货舱添燃料」，按 F → 碎石全停，弹 "refuel"（burn_pick 步骤，
##     配乐换 space_choice），烧完回来接着飞。自动玩低于安全线自己去加。
##     燃料烧到 0：坠毁——大晃、闪白、步骤立刻结束，返回 "crash"（scene 名，剧本里演坏结局）。
## story_runner.gd 的 _cockpit_step 建它（挂在对话界面下，按键先到这里）：await play(runner, st)。

signal done

const ROCKS := ["res://art/flight/rock_a.png", "res://art/flight/rock_b.png", "res://art/flight/rock_c.png"]
const SHIFT := 28.0           # 船上下最多挪多少像素
const MOVE := 72.0            # 按住时每秒挪多少像素
const BACK := 3.0             # 松手 1.5 秒以后每秒慢慢回中间多少像素
const WARN := 2.0             # 预告比碎石擦到船早多少秒
const ROCK_V := 210.0         # 碎石往右飞的速度（像素 / 秒）
const LANE_IN := 6.0          # 碎石中心在主船身上沿 / 下沿往里多少像素
const GAP_M := 10.0           # 墙的缝：船挪到 safe 时船身上下各留多少像素
const GRAZE := 6.0            # 离船身不到这么多像素算擦边
const FAR_K := 0.55           # 默认拉远到几倍（11-08 作者：「飞船需要进一步缩小」→ 最小那档 0.55；原来 0.65）
const FAR_SHIFT := 40.0       # 远景里船上下最多挪多少像素
const FAR_TOP := 40.0         # 往上挪满时尾翼尖最高到屏幕 y 多少（上面 0..34 是燃料栏）
const FAR_MOVE := 100.0       # 远景里按住时目标每秒走多少像素
const END_WAIT := 0.7         # 穿出去以后，船先回中间（弹簧约 0.6 秒停稳）再拉回剖面
const FAR_X := 0.8            # 远景船停在屏幕右边：图的中线在屏幕宽度的这个比例（10-31 作者：「正中间提前量有点不够」；
                              #   11-08 作者：「屏幕可以更早的显示障碍物，增加难度」→ 0.73 再往右挪到 0.8，左边看得更远）
const FAR_SLOW := 1.0         # 远景里碎石再慢这么多（11-08：0.9 → 1.0，看得更远了，碎石也快一点、波次更密，难度往上）
const WARN_OFF := 1.2         # 远景：碎石进画面之前，左边划痕先预告多少秒（和原来船在中间时一样）
const AIR_C := Color(0.5, 0.78, 0.64)       # 气流线（#7fc7a4 一族，很淡）
const AIR_EVERY := 0.18       # 气流线：每隔多少秒从屏幕左边出生一道（原来 5 道循环，约这个密度）
const AIR_SLOTS := 5          # 通道里上下分几档高度轮着出
const SCRATCH_C := Color(0.78, 0.9, 0.84)
const SPARK_C := Color(0.95, 0.9, 0.75)
## 波次（t = 秒，按 sec / 40 缩放；safe 见文件头）。lane：-1 上道 / +1 下道；g：缝的位置（× _shift，+ = 往下）。
## 排的时候守住：两波要换位置时，上一波过完船尾（远景约 1.3 秒）以后还要留 1 秒让船挪过去 → 换道隔 ≥ 2.8 秒，挪半程隔 ≥ 2.4 秒
## 11-08 加密（作者：「增加难度」）：原来 9 波，现在 11 波，换道都卡在 2.8 秒；一边躲一边还要走去修漏气（见 LEAK_*）
const PLAN := [
	{"t": 2.6, "k": "one", "lane": -1},
	{"t": 5.4, "k": "one", "lane": 1},
	{"t": 8.2, "k": "pair", "lane": -1},
	{"t": 11.6, "k": "gap", "g": 0.0},
	{"t": 14.4, "k": "one", "lane": 1},
	{"t": 17.2, "k": "pair", "lane": -1},
	{"t": 20.6, "k": "gap", "g": 0.5},
	{"t": 23.4, "k": "one", "lane": -1},
	{"t": 26.2, "k": "one", "lane": 1},
	{"t": 29.0, "k": "gap", "g": -0.5},
	{"t": 32.6, "k": "final", "g": [0.6, -0.1, -0.8]},
]
const PLAN_REPAIR := [
	{"t": 3.0, "k": "one", "lane": -1},
	{"t": 6.8, "k": "one", "lane": 1},
	{"t": 10.6, "k": "pair", "lane": -1},
]
## 11-08 飞行一前半段（永燃之木还在）：三波轻的，最后一排躲不开的大陨石
const PLAN_CRUISE := [
	{"t": 2.6, "k": "one", "lane": -1},
	{"t": 5.4, "k": "one", "lane": 1},
	{"t": 8.2, "k": "gap", "g": 0.0},
	{"t": 12.0, "k": "meteor"},
]
const PLAN_AUTO_CRUISE := [
	{"t": 0.0, "k": "one", "lane": -1},
	{"t": 2.7, "k": "meteor"},
]
const PLAN_AUTO := [
	{"t": 0.0, "k": "one", "lane": -1},
	{"t": 2.7, "k": "gap", "g": 0.0},
]
## 终章（"plan": "final"）：前半段看得见，后半段进云层黑掉、只能听（dark 的 t = 开始找的时刻，碎石 DARK_LEAD 秒后到船头）
const PLAN_FINAL := [
	{"t": 2.6, "k": "one", "lane": -1},
	{"t": 6.4, "k": "one", "lane": 1},
	{"t": 10.2, "k": "pair", "lane": 1},
	{"t": 14.6, "k": "gap", "g": 0.5},
	{"t": 18.6, "k": "dark_on"},
	{"t": 20.6, "k": "dark", "g": 0.0},
	{"t": 27.6, "k": "dark", "g": 1.0},
	{"t": 34.6, "k": "dark", "g": -1.0},
	{"t": 41.6, "k": "dark", "g": 0.0, "last": true},
]
const PLAN_AUTO_DARK := [
	{"t": 0.0, "k": "one", "lane": -1},
	{"t": 2.7, "k": "dark_on"},
	{"t": 3.2, "k": "dark", "g": -1.0, "last": true},   # 和上一波的安全通道（下面）正好相反：自动玩先「迷路」，日志里有偏航时的声音
]
const FINAL_ROW := 2.4        # 结尾那几排隔多少秒
const PAIR_DT := 0.9          # pair 两块隔多少秒
const DARK_LEAD := 5.0        # 黑墙：开始找到碎石到船头多少秒
const DARK_LEAD_AUTO := 2.5
const DARK_IN := 2.2          # 黑幕慢慢落下 / 退掉多少秒
const DARK_C := Color(0.008, 0.016, 0.016)
const DARK_A := 0.96          # 黑幕最深（留一点点，不是死黑）
const DARK_HINT1 := 2.5       # 进黑墙后这么久还没进航道：提示加强一档（铃更响更密 / 没铃的气流线开始淡入）
const DARK_HINT2 := 3.5       # 再加强一档（没铃的气流线更亮）
const DARK_AUTO_WAIT := 1.0   # 自动玩：黑墙出来先「听」这么久再挪（好让日志里有偏航时的声音）
const RUMBLE_IN := -45.0      # 黑里轰鸣：在安静航道里
const RUMBLE_OUT := -7.0      #           偏了一条道以上
const RUMBLE_PITCH := 0.28    # 轰鸣音高：船每偏一条道（× _shift）高 / 低这么多（上高下低）
const HUM_SOFT := -8.0        # 安静航道里引擎声低多少 dB（相对 level.HUM_DB）
const HUM_TENSE := 3.0        # 偏了一条道以上引擎声高多少 dB
const DARK_NEAR := 0.3        # 离安全航道不到 0.3 × _shift 算「进了航道」
## 边躲边修（11-08 作者：「同时操作左右，维修和上下」「维修本身不需要任何的剧情停顿」；二改：「保持这个视角，但是飞机缩小，
##   窗外，副驾驶，和工具位置分别对应了三个要修的点」）：剧本 "leaks": [{"t": 秒, "at": 物件 / 标记名}]，t 按 sec / 40 缩放。
##   有 leaks 就不拉到船外远景，而是**剖面整体缩小**（_zoom：镜头 zoom 到 VIEW_Z、船挪到屏幕 VIEW_X；cockpit.view_* →
##   level_forest._update_camera），舱里、晨、物件都看得见；碎石、预告、碰撞按缩小后的船身轮廓（_scale_hull）算。
##   晨本人（←→ / A D）自己走；漏点在那件东西上一闪一闪、冒白汽、嘶嘶响；走到它的标记 LEAK_REACH 像素内按住 E 约 LEAK_HOLD 秒 = 修好
##   （修的时候晨播 repair、不走；↑↓ 照样躲）。没修的漏点每个让船上下挪变慢 LEAK_DRAG（最慢 LEAK_MIN）——不扣燃料、不会输。
##   波次排完了还有漏没修：接着来零星的单块，修完才收尾；超时兜底直接算修好。
const LEAK_REACH := 14.0      # 世界像素
const LEAK_HOLD := 0.7
const LEAK_DRAG := 0.35
const LEAK_MIN := 0.4
const VIEW_Z := 0.6           # 剖面缩到几倍
const VIEW_X := 0.78          # 缩小后船（图的中线）停在屏幕宽度的这个比例：左边留出看碎石的距离
const VIEW_CY := 140.0        # 缩小后主船身中线的屏幕 y
const VIEW_SHIFT := 48.0      # 缩小后船上下最多挪多少像素
const VIEW_MOVE := 100.0
const VIEW_SEC := 1.5         # 缩小 / 放回各多少秒
const STEAM_C := Color(0.86, 0.9, 0.88)
const CRACK_C := Color(1.0, 0.62, 0.3)
const TXT := {
	"hint": ["↑ ↓  Dodge the debris", "↑ ↓  躲开碎石"],
	"hint_leak": ["↑ ↓ Dodge    ← → Walk    hold E  Fix leaks", "↑ ↓ 躲碎石    ← → 走动    按住 E 修漏气"],
	"leak": ["Leak! ← →  walk over, hold E", "漏气了！← → 走过去，按住 E"],
	"leak_e": ["E", "E"],
	"dark_hint": ["↑ ↓  Listen for the quiet lane", "↑ ↓  听——找最安静的那条"],
	"refuel": ["Fuel below the line!  Press F to go to the cargo hold", "燃料低于绿线！按 F 去货舱添燃料"],
	"refuel_none": ["Fuel below the line... nothing left to burn", "燃料低于绿线……已经没有能烧的了"],
}
const BUMP_LINES := [
	{"zh": "……稳住。", "en": "...Steady.", "added": true},
	{"zh": "哎。没事。", "en": "Ugh. It's fine.", "added": true},
	{"zh": "这儿也有石头。", "en": "Rocks here too.", "added": true},
]

var runner: Node
var cockpit: Node2D
var level: Node2D
var sec := 40.0
var bumps := 0
var waves_n := 0
var grazes := 0
var _t := 0.0
var _push := 0.0              # 鼠标 / 触屏按住的方向（-1 上 / +1 下）
var _idle := 0.0              # 多久没按了
var _plan: Array = []         # 还没出的波次（PLAN 缩放过的，t 是绝对时间）
var _waves: Array = []        # {safe, at, t0, rocks: [...], bumped, kind}
var _rng := RandomNumberGenerator.new()
var _fx: Node2D               # 预告的划痕 + 小影子 + 气流线 + 擦边火星（画在 cockpit.debris_layer 里）
var _sparks: Array = []       # {p, v, age}
var _repair_at := ""
var _repair_x := 0.0
var _repair_done := false
var _repair_hint: Label
var _repair_lane := -1

var _hint: Label
var _said := 0
var _auto := false
var _finished := false
var _rock_tex: Array = []     # 碎石（算碰撞）
var _bit_tex: Array = []      # 碎屑（小于 8 像素，跟着飞、不算碰撞）
var _hull := {}
var _x1 := 0.0                # 船尾（船身最右那一列）的屏幕 x
var _fuel_per := 0            # 每撞一下扣多少燃料
var _fuel_left := 0           # 这一段还能扣多少
var _far := false             # 拉远到船外了
var _shift := SHIFT
var _move := MOVE
var _rock_v := ROCK_V
var _warn := WARN             # 预告比碎石擦到船头早多少秒（远景 = WARN_OFF + 从屏幕左边飞到船头的时间）
var _ship_cx := 240.0         # 船（图的中线）在屏幕上的 x：声像、提示文字跟着它
var _lead := []               # 每块领头的碎石：进画面到碰到船头的秒数（日志）
var _zoom_sec := 1.7          # 拉远 / 拉回各多少秒
var _ending := false          # 碎石都过去了：穿出去 → 船回中间 → 拉回剖面
var _end_t := 0.0
var _back_in := false
var _real := false            # --debris_full
var _air: AudioStreamPlayer   # 稳定的气流声
var _air_on := 0.0            # 气流（声音 + 线）现在多强 0..1
var _air_g := 0.0             # 气流线 / 音高现在对着的安全通道（船的偏移，平滑跟着）
var _air_lines: Array = []    # 飞着的气流线 {x, y, ln, v}：每道独立，出生定 y / 长度，之后只往右匀速飞（见文件头）
var _air_spawn := 0.0         # 离下一道出生还有多久
var _air_n := 0               # 出了几道（轮高度档用）
var _air_qa := false          # --qa_live：核对每道线 x 只增不减、不在船前面消失（只打印异常 + 结束一行汇总）
var _air_qa_bad := 0
var _dark: Node2D             # 黑窗：船外背景和碎石上面盖的黑幕（debris_layer 里，z 1）
var _dark_a := 0.0            # 黑幕现在多深
var _dark_on := false
var _dark_lead := DARK_LEAD
var _dark_bumps := 0
var _rumble: AudioStreamPlayer          # 黑里碎石的轰鸣（循环），离安全航道越远越响
var _bell := false            # 背包里还有铜铃：铃声引路
var _bell_t := 0.0
var _line_a := 0.0            # 黑里安全航道气流线的亮度（平滑）
var _hint_lv := 0             # 这一排黑墙的提示档（0 / 1 / 2），换排时归零
var _dark_ctl := false        # 这一帧黑墙在管气流声音量（_air_step 别覆盖）
var _air_dark_db := -15.0
var _hum_ctl := false         # 动过驾驶舱引擎声（步骤完还原）
var _dark_wait := DARK_AUTO_WAIT
var _dark_log_t := 0.0
var _bell_n := 0
# 边躲边修
var _leak_plan: Array = []    # 还没漏的 {t, x, edge}
var _leaks: Array = []        # 漏着 / 修好的 {x, y0, edge, prog, fixed, wrenched, age}
var _leaks_fixed := 0
var _steam: Array = []        # 白汽 {p, v, age}
var _leak_fx: Node2D          # 漏点 + 白汽 + 修理进度（画在 UI 层，船上面）
var _fixing := false
var _zoom := false            # 剖面缩小（不拉到船外）：晨看得见、自己走去修
var _view_k := VIEW_Z
var _view_u := 0.0
var _view_go := 0.0
var _view_p := Vector2(240, 135)
var _view_t := Vector2(240, 135)
var _hiss: AudioStreamPlayer
var _leak_tip: Label
var _extra_lane := -1
# 11-08 燃料模式（见文件头）
var _fuel_mode := false
var _drain := 0.0
var _hit_drain := 0.0
var _hit_sec := 3.0
var _leak_drain := 0.0
var _safe := 0.0
## 11-08 作者「绿线应该是会一点一点降低的」「绿线降低到 0，就是到达目的地」：绿线从 safe 匀速降到 0，
##   降到 0 的时刻 = 最后一波排好的时间 + ARRIVE_PAD（最后那排碎石过完）；降的过程中燃料低于它照样要回货舱；
##   到 0 = 到了：燃料不再烧，等碎石过完就收尾（还没修的漏点算修好，不再拖）。添燃料时（_paused）_t 不走，线也停住。
const ARRIVE_PAD := 5.0
var _safe0 := 0.0
var _arrive := 0.0
var _arrived := false
var _fuel_f := 0.0
var _hit_t := 0.0
var _paused := false
var _crashed := false
var _crash_scene := ""
var _refuel_st: Dictionary = {}
var _refuel_hint: Label
var _refuels := 0
var _flash: ColorRect
var _meteor_hit := false


func play(r: Node, st: Dictionary) -> String:
	runner = r
	level = r.level
	cockpit = r.world.cockpit
	sec = maxf(6.0, float(st.get("sec", 40.0)))
	var key := str(st.get("bumps_key", str(st.get("id", "debris")).trim_suffix("_debris") + "_bumps"))
	if r.ff or cockpit == null:
		StoryState.set_prop(key, "0")
		return ""
	_fuel_per = maxi(0, int(st.get("fuel_per_bump", 0)))
	_fuel_left = maxi(0, int(st.get("fuel_max_loss", 0)))
	_fuel_mode = st.has("drain") and StoryState.fuel_on()
	_drain = float(st.get("drain", 0.0))
	_hit_drain = float(st.get("hit_drain", 0.0))
	_hit_sec = float(st.get("hit_sec", 3.0))
	_leak_drain = float(st.get("leak_drain", 0.0))
	_safe = float(st.get("safe", 0.0))
	_safe0 = _safe if _fuel_mode else 0.0
	_crash_scene = str(st.get("crash", ""))
	_refuel_st = st.get("refuel", {}) if st.get("refuel", {}) is Dictionary else {}
	_fuel_f = float(StoryState.fuel())
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--fuel_drain="):                 # 测试：燃料烧得更快（看补燃料 / 坠毁）
			_drain = float(a.trim_prefix("--fuel_drain="))
	_auto = r.auto != ""
	_real = "--debris_full" in OS.get_cmdline_user_args()   # 截图用：自动玩也按真实时长、真实拉远速度播
	var real := _real
	_repair_at = str(st.get("repair_at", ""))
	if _repair_at != "":
		_repair_x = float(r.world.resolve(_repair_at)["x"])
	var k := float(st.get("far_scale", FAR_K))
	var fx := float(st.get("far_x", FAR_X))
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--far_scale="):
			k = float(a.trim_prefix("--far_scale="))
		elif a.begins_with("--far_x="):
			fx = float(a.trim_prefix("--far_x="))
	_zoom = _repair_at == "" and st.get("leaks") is Array
	_far = not _zoom and _repair_at == "" and k < 0.99 and cockpit.far_ready(k)
	if _zoom:
		_zoom_sec = 0.8 if _auto and not real else VIEW_SEC
		_view_k = clampf(float(st.get("view_scale", VIEW_Z)), 0.4, 1.0)
		var h0: Dictionary = cockpit.hull()
		_view_p = Vector2(cockpit.img_rect.get_center().x, (float(h0.get("T", 100)) + float(h0.get("B", 206))) / 2.0)
		_ship_cx = roundf(clampf(float(st.get("view_x", VIEW_X)), 0.5, 0.85) * 480.0)
		_view_t = Vector2(_ship_cx, VIEW_CY)
		_view_go = 1.0
		_shift = VIEW_SHIFT
		_move = VIEW_MOVE
		_rock_v = ROCK_V * (0.5 + 0.5 * _view_k) * FAR_SLOW
	if _far:
		_zoom_sec = 1.2 if _auto and not real else float(cockpit.FAR_SEC)
		_ship_cx = roundf(clampf(fx, 0.5, 0.8) * 480.0)
		cockpit.far_out(k, _zoom_sec, _ship_cx)                     # 缩小的同时平移到右边（拉回时倒着走回中间）
		_shift = minf(FAR_SHIFT, floorf(cockpit.far_used_rect().position.y - FAR_TOP))   # 大的那档往上挪满时尾翼别碰燃料栏
		_move = FAR_MOVE
		_rock_v = ROCK_V * (0.5 + 0.5 * cockpit.far_k) * FAR_SLOW
	_rng.seed = 23
	for n in ["debris_a", "debris_b", "debris_c", "debris_d", "debris_e", "debris_f", "debris_g"]:   # 美术给的碎石（art/cockpit/）
		var t: Texture2D = cockpit.art(n)
		if t == null:
			continue
		if t.get_height() >= 8 and t.get_width() >= 8:
			_rock_tex.append(t)
		else:
			_bit_tex.append(t)
	if _rock_tex.is_empty():
		for p in ROCKS:
			if ResourceLoader.exists(p):
				_rock_tex.append(load(p))
	_hull = cockpit.far_hull() if _far else (_scale_hull(cockpit.hull()) if _zoom else cockpit.hull())
	_air_qa = "--qa_live" in OS.get_cmdline_user_args()
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	_x1 = float(int(_hull.get("x0", 80)) + tops.size())
	if _far or _zoom:
		_warn = WARN_OFF + (_nose() + 2.0) / _rock_v       # 碎石进画面以后飞多久到船头 + 进画面前的预告
	# 波次：真实时长按 sec / 40 缩放；自动玩只播两波（第一波等拉远差不多了再来）
	var final := str(st.get("plan", "")) == "final"
	_bell = Inventory.has("copper_bell") and not "--no_bell" in OS.get_cmdline_user_args()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--dark_wait="):
			_dark_wait = maxf(0.0, float(a.trim_prefix("--dark_wait=")))
	if _auto and not real:
		_dark_lead = maxf(DARK_LEAD_AUTO, _dark_wait + 1.5)
		var t0 := 1.3 if _far or _zoom else 0.8
		for w in (PLAN_AUTO_DARK if final else (PLAN_AUTO_CRUISE if str(st.get("plan", "")) == "cruise" else PLAN_AUTO)):
			var e: Dictionary = (w as Dictionary).duplicate()
			e["t"] = t0 + float(e["t"])
			_plan.append(e)
	else:
		var sc := clampf(sec / 40.0, 0.75, 1.5)
		var plan := PLAN_FINAL if final else (PLAN_REPAIR if _repair_at != "" else (PLAN_CRUISE if str(st.get("plan", "")) == "cruise" else PLAN))
		for w in plan:
			var e: Dictionary = (w as Dictionary).duplicate()
			if str(st.get("plan", "")) == "dense" and e["k"] == "one" and float(e["t"]) <= 18.6:
				e["k"] = "pair"
			e["t"] = float(e["t"]) * sc
			_plan.append(e)
	# 边躲边修（自动玩：只漏一处，近一点）
	if _zoom:
		var sc2 := clampf(sec / 40.0, 0.75, 1.5)
		for l in (st["leaks"] as Array):
			var e: Dictionary = (l as Dictionary).duplicate()
			e["t"] = (1.3 + 0.6 * float(_leak_plan.size())) if _auto and not real else float(e.get("t", 5.0)) * sc2
			_leak_plan.append(e)
			if _auto and not real:
				break
	_build()
	if _repair_at != "":
		runner.chen.input_enabled = not _auto
		_build_repair_hint()
	await done
	if _repair_at != "":
		runner.chen.input_enabled = false
		runner.chen.auto_dir = 0.0
	StoryState.set_prop(key, str(bumps))
	cockpit.steering = false
	if _far and cockpit.far_u() > 0.0:
		cockpit.far_snap(false)
	if _zoom:
		_view_reset()
		runner.chen.input_enabled = false
		runner.chen.auto_dir = 0.0
		if _fixing:
			runner._anim({"who": "chen", "name": "idle"})
	if is_instance_valid(_fx):
		_fx.queue_free()
	for w in _waves:
		_free_wave(w)
	for lp in [_air, _rumble]:                       # 气流、低频轰鸣：淡掉再删（不一下子停）
		if is_instance_valid(lp):
			(load("res://scripts/audio_fade.gd") as GDScript).release(lp, 0.8)
			if is_instance_valid(lp) and lp.is_inside_tree() and not bool(lp.get("playing")):
				lp.queue_free()                       # 没在放的直接删
	if is_instance_valid(_dark):
		_dark.queue_free()
	if is_instance_valid(_hiss):
		(load("res://scripts/audio_fade.gd") as GDScript).release(_hiss, 0.6)
	if not _leaks.is_empty():
		StoryState.set_prop(key.trim_suffix("_bumps") + "_leaks", str(_leaks_fixed))
		print("COCKPIT leaks %s: fixed=%d/%d" % [str(st.get("id", "")), _leaks_fixed, _leaks.size()])
	var lead := 0.0
	for v in _lead:
		lead += float(v) / float(_lead.size())
	print("COCKPIT debris_steer %s: bumps=%d grazes=%d waves=%d time=%.1fs ship_x=%d nose=%d lead=%.2fs dark_bumps=%d bell=%s" % [str(st.get("id", "")),
		bumps, grazes, waves_n, _t, int(_ship_cx), int(_nose()), lead, _dark_bumps, _bell])
	if is_instance_valid(_flash):
		_flash.queue_free()
	if _fuel_mode:
		print("COCKPIT fuel %s: left=%d refuels=%d crashed=%s" % [str(st.get("id", "")), StoryState.fuel(), _refuels, _crashed])
	if _crashed:
		return _crash_scene
	return ""


func _build() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	cockpit.steering = true
	_fx = Node2D.new()
	_fx.name = "DebrisWarn"
	_fx.draw.connect(_draw_fx)
	_fx.z_index = 2                                  # 黑窗时气流线画在黑幕（z 1）上面
	cockpit.debris_layer.add_child(_fx)
	_hint = Label.new()
	_hint.text = _tx("hint")
	_hint.add_theme_font_size_override("font_size", 14)
	_hint.add_theme_color_override("font_color", UITheme.TEXT_DIM)
	_hint.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.8))
	_hint.add_theme_constant_override("shadow_offset_x", 0)
	_hint.add_theme_constant_override("shadow_offset_y", 1)
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint.size = Vector2(480, 16)
	_hint.position = Vector2(_ship_cx - 240.0, 246)   # 在船下面（船身下沿往下挪满（206 + 28）以后也碰不到）
	_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hint.modulate.a = 0.0
	add_child(_hint)
	create_tween().tween_property(_hint, "modulate:a", 0.85, 0.6)
	_flash = ColorRect.new()
	_flash.color = Color(0.92, 0.95, 0.9, 0.0)        # 撞上陨石 / 坠毁闪一下（不用纯白）
	_flash.set_anchors_preset(Control.PRESET_FULL_RECT)
	_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_flash)
	if _fuel_mode:
		_refuel_hint = Label.new()
		_refuel_hint.text = _tx("refuel")
		_refuel_hint.add_theme_font_size_override("font_size", 14)
		_refuel_hint.add_theme_color_override("font_color", Color("e0607a"))
		_refuel_hint.add_theme_color_override("font_shadow_color", Color(0.0, 0.03, 0.02, 0.8))
		_refuel_hint.add_theme_constant_override("shadow_offset_x", 0)
		_refuel_hint.add_theme_constant_override("shadow_offset_y", 1)
		_refuel_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_refuel_hint.size = Vector2(480, 16)
		_refuel_hint.position = Vector2(0, 228)
		_refuel_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_refuel_hint.visible = false
		add_child(_refuel_hint)
	_play("flight_rumble", -14.0)
	_air = _loop("airflow_loop", -60.0)
	if _zoom:
		_build_leaks()
	if _repair_at != "":
		_hint.text = I18n.pick({"zh": "← → 在舱内移动     ↑ ↓ 驾驶飞船", "en": "← → Walk in the cabin     ↑ ↓ Steer the ship"})


func _build_repair_hint() -> void:
	_repair_hint = Label.new()
	_repair_hint.text = I18n.pick({"zh": "E 修理漏气处", "en": "E   Repair leak"})
	_repair_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_repair_hint.add_theme_font_size_override("font_size", 13)
	_repair_hint.add_theme_stylebox_override("normal", UITheme.box(Color("#293332"), Color("#ddc08a"), 1, Vector4(4, 2, 4, 2)))
	_repair_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_repair_hint)


func _repair_step() -> void:
	if _repair_at == "" or _repair_done:
		return
	var distance: float = _repair_x - runner.chen.position.x
	var near := absf(distance) <= 30.0
	var screen_x: float = _repair_x - level.cam_left().x
	_repair_hint.position = Vector2(clampf(screen_x - _repair_hint.size.x / 2.0, 4.0, 476.0 - _repair_hint.size.x),
		clampf(float(runner.chen.position.y) - level.cam_left().y - 87.0, 32.0, 200.0))
	_repair_hint.modulate.a = 1.0 if near else 0.65
	if _auto:
		runner.chen.auto_dir = signf(distance) if not near else 0.0
	if near and (_auto or Input.is_key_pressed(KEY_E)):
		_repair()


func _repair() -> void:
	if _repair_done or absf(_repair_x - runner.chen.position.x) > 30.0:
		return
	_repair_done = true
	_repair_hint.hide()
	runner.world.set_prop(_repair_at, "fixed")
	runner._ambient_step({"name": "hiss_thin", "at": _repair_at, "on": false})
	_play("wrench", -8.0)


# ======================================================================= 边躲边修（见 LEAK_* 上面的说明）
## 剖面缩小（_zoom）：每帧把 _view_u 往 _view_go 走，smootherstep 后给 cockpit.view_*（level_forest 的镜头照它缩放 / 平移）
func _view_step(delta: float) -> void:
	if not _zoom:
		return
	_view_u = move_toward(_view_u, _view_go, delta / maxf(0.01, _zoom_sec))
	var p := _view_u
	var e := p * p * p * (p * (p * 6.0 - 15.0) + 10.0)
	cockpit.view_z = lerpf(1.0, _view_k, e)
	cockpit.view_p = _view_p
	cockpit.view_t = _view_p.lerp(_view_t, e)


func _view_reset() -> void:
	if not _zoom:
		return
	_view_u = 0.0
	_view_go = 0.0
	cockpit.view_z = 1.0
	cockpit.view_t = cockpit.view_p
	level.cam.zoom = Vector2.ONE


## 剖面船轮廓（zoom 1 时的屏幕坐标）→ 缩小以后的屏幕坐标：s' = (s − P) × z + T
func _scale_hull(h: Dictionary) -> Dictionary:
	var z := _view_k
	var tops: PackedInt32Array = h.get("top", PackedInt32Array())
	var bots: PackedInt32Array = h.get("bot", PackedInt32Array())
	var x0 := float(int(h.get("x0", 80)))
	var nx0 := int(floorf((x0 - _view_p.x) * z + _view_t.x))
	var n := int(ceilf(float(tops.size()) * z))
	var nt := PackedInt32Array()
	var nb := PackedInt32Array()
	for j in n:
		var sx := float(nx0 + j) + 0.5
		var i := clampi(int(floorf((sx - _view_t.x) / z + _view_p.x - x0)), 0, tops.size() - 1)
		if tops[i] < 0:
			nt.append(-1)
			nb.append(-1)
		else:
			nt.append(int(roundf((float(tops[i]) - _view_p.y) * z + _view_t.y)))
			nb.append(int(roundf((float(bots[i]) - _view_p.y) * z + _view_t.y)))
	return {"x0": nx0, "top": nt, "bot": nb,
		"T": int(roundf((float(h.get("T", 100)) - _view_p.y) * z + _view_t.y)),
		"B": int(roundf((float(h.get("B", 206)) - _view_p.y) * z + _view_t.y))}


func _build_leaks() -> void:
	_leak_fx = Node2D.new()
	_leak_fx.name = "LeakFx"
	_leak_fx.draw.connect(_draw_leaks)
	add_child(_leak_fx)
	_leak_tip = Label.new()
	_leak_tip.text = _tx("leak_e")
	_leak_tip.add_theme_font_size_override("font_size", 11)
	_leak_tip.add_theme_stylebox_override("normal", UITheme.box(Color("#293332"), Color("#ddc08a"), 1, Vector4(3, 0, 3, 0)))
	_leak_tip.add_theme_color_override("font_color", Color("#ddc08a"))
	_leak_tip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_leak_tip.hide()
	add_child(_leak_tip)
	_hint.text = _tx("hint_leak") if not _leak_plan.is_empty() else _tx("hint")   # 11-08 飞行一前半段（cruise）没有漏气：只提示躲
	_hiss = _loop("hiss_thin", -60.0)
	runner.chen.input_enabled = not _auto


## 世界坐标 → 屏幕（镜头缩放过）
func _ws(p: Vector2) -> Vector2:
	return (p - level.cam_left()) * level.cam.zoom.x


## 没修的漏点让船挪得慢
func _leak_drag() -> float:
	var n := 0
	for l in _leaks:
		if not l["fixed"]:
			n += 1
	return maxf(LEAK_MIN, 1.0 - LEAK_DRAG * float(n))


func _leak_step(delta: float) -> void:
	if not is_instance_valid(_leak_fx):
		return
	var chen: Node2D = runner.chen
	# 新漏点
	var i := 0
	while i < _leak_plan.size():
		var e: Dictionary = _leak_plan[i]
		if _t >= float(e["t"]):
			_leak_plan.remove_at(i)
			_leak_open(e)
		else:
			i += 1
	# 晨（真人，←→ / A D 自己走）站在哪个漏点上；按住 E 修（修的时候不走），↑↓ 照样躲
	var target: Dictionary = {}
	for l in _leaks:
		if not l["fixed"] and absf(float(l["wx"]) - chen.position.x) <= LEAK_REACH:
			target = l
			break
	var want_fix := false
	if _auto:
		var goal := NAN
		for l in _leaks:
			if not l["fixed"]:
				goal = float(l["wx"])
				break
		want_fix = not target.is_empty() and not "--no_leak_fix" in OS.get_cmdline_user_args()   # 自测：漏点一个都不修，看嘶嘶声结束时停没停
		chen.auto_dir = 0.0 if want_fix or is_nan(goal) or absf(goal - chen.position.x) < 2.0 else signf(goal - chen.position.x)
	else:
		want_fix = Input.is_key_pressed(KEY_E) and not target.is_empty() and not _ending
	if want_fix != _fixing:
		_fixing = want_fix
		chen.input_enabled = not _fixing and not _auto
		runner._anim({"who": "chen", "name": "repair" if _fixing else "idle"})
	if want_fix:
		if not target["wrenched"]:
			target["wrenched"] = true
			_play("wrench", -10.0, 1.0, _pan(_ws(target["p"]).x))
		target["prog"] = float(target["prog"]) + delta / LEAK_HOLD
		if float(target["prog"]) >= 1.0:
			_leak_fix(target)
	else:
		for l in _leaks:                              # 松手：进度慢慢退（别一松就清零）
			if not l["fixed"]:
				l["prog"] = maxf(0.0, float(l["prog"]) - delta * 0.5)
	# 白汽（世界坐标，往船尾那边飘）
	var open := 0
	for l in _leaks:
		l["age"] = float(l["age"]) + delta
		if l["fixed"]:
			continue
		open += 1
		if _rng.randf() < delta * 40.0:
			_steam.append({"p": (l["p"] as Vector2) + Vector2(_rng.randf_range(-2.0, 2.0), _rng.randf_range(-2.0, 2.0)),
				"v": Vector2(_rng.randf_range(20.0, 60.0), _rng.randf_range(-30.0, -8.0)), "age": 0.0})
	for j in range(_steam.size() - 1, -1, -1):
		var s: Dictionary = _steam[j]
		s["age"] = float(s["age"]) + delta
		s["p"] = (s["p"] as Vector2) + (s["v"] as Vector2) * delta
		if float(s["age"]) > 0.7:
			_steam.remove_at(j)
	if is_instance_valid(_hiss):
		var want := -60.0 if open == 0 or _ending else -18.0 + 3.0 * float(open - 1)
		_hiss.volume_db = move_toward(_hiss.volume_db, want, 40.0 * delta)
	# 「E」：站在漏点上才出，浮在晨头顶（进度条在它下面）
	var show_tip: bool = not target.is_empty() and not _ending
	_leak_tip.visible = show_tip
	if show_tip:
		var hp: Vector2 = runner._anchor("chen")
		_leak_tip.position = Vector2(roundf(hp.x - _leak_tip.size.x / 2.0), roundf(hp.y - 24.0))
		_leak_tip.modulate.a = 1.0 if int(_t * 4.0) % 2 == 0 or _fixing else 0.6
	_leak_fx.queue_redraw()


func _leak_open(e: Dictionary) -> void:
	var id := str(e.get("at", "cockpit_toolbox"))
	var wx := float(runner.world.resolve(id).get("x", runner.chen.position.x))
	var r: Rect2 = cockpit.prop_rect(id)
	var p := Vector2(wx, float(runner.chen.position.y) - 30.0)
	if r.size != Vector2.ZERO:
		p = r.get_center() if id == "cockpit_window" else Vector2(r.get_center().x, r.position.y + r.size.y * 0.35)
	_leaks.append({"id": id, "wx": wx, "p": p.round(), "prog": 0.0, "fixed": false, "wrenched": false, "age": 0.0})
	_play("hiss_thin", -6.0, 1.1, _pan(_ws(p).x))
	_play("debris_bump", -14.0, 1.3, _pan(_ws(p).x))
	level._shake = 0.2
	level._shake_amp = 1.0
	if _leaks.size() == 1 and not _auto:            # 第一次漏：提示亮一下（4 秒后淡掉）
		_hint.text = _tx("leak")
		_hint.set_meta("out", false)
		_hint.set_meta("timed", true)
		var th := create_tween()
		th.tween_property(_hint, "modulate:a", 0.9, 0.3)
		th.tween_interval(4.0)
		th.tween_callback(_hint_out)


func _leak_fix(l: Dictionary) -> void:
	l["fixed"] = true
	l["prog"] = 1.0
	l["age"] = 0.0
	_leaks_fixed += 1
	_play("wrench", -8.0, 1.15, _pan(_ws(l["p"]).x))
	if cockpit.glow != null:
		cockpit.glow.strength = 0.6
	if _auto:
		print("LEAK fixed t=%.2f at=%s (%d/%d)" % [_t, str(l["id"]), _leaks_fixed, _leaks.size()])


## 漏点（一闪一闪的橙色裂口 + 白汽）、修好那一下的淡绿闪、晨头顶的修理进度（UI 层，按镜头缩放换算到屏幕）
func _draw_leaks() -> void:
	for l in _leaks:
		var sp := _ws(l["p"]).round()
		if l["fixed"]:
			if float(l["age"]) < 0.6:
				var a := 0.8 * (1.0 - float(l["age"]) / 0.6)
				_leak_fx.draw_rect(Rect2(sp - Vector2(3, 3), Vector2(7, 7)), Color(AIR_C, a), false)
			continue
		var on := int(_t * 5.0) % 2 == 0
		var ring := 4.0 + floorf(fmod(float(l["age"]) * 3.0, 1.0) * 4.0) * 2.0      # 一圈往外扩的方框：远一点也看得见哪儿在漏
		_leak_fx.draw_rect(Rect2(sp - Vector2(ring, ring), Vector2(ring, ring) * 2.0 + Vector2.ONE), Color(CRACK_C, 0.45 - ring * 0.03), false)
		_leak_fx.draw_rect(Rect2(sp - Vector2(1, 1), Vector2(3, 3)), Color(CRACK_C, 1.0 if on else 0.6))
		_leak_fx.draw_rect(Rect2(sp + Vector2(2, -2), Vector2(2, 1)), Color(CRACK_C, 0.8 if on else 0.35))
		_leak_fx.draw_rect(Rect2(sp + Vector2(-3, 2), Vector2(2, 1)), Color(CRACK_C, 0.8 if on else 0.35))
	for s in _steam:
		var k := 1.0 - float(s["age"]) / 0.7
		var sz := 1.0 if float(s["age"]) < 0.2 else 2.0
		_leak_fx.draw_rect(Rect2(_ws(s["p"]).round(), Vector2(sz, sz)), Color(STEAM_C, floorf(k * 4.0) / 4.0 * 0.75))
	for l in _leaks:
		if not l["fixed"] and float(l["prog"]) > 0.0:
			var hp: Vector2 = runner._anchor("chen")
			var bp := Vector2(roundf(hp.x - 7.0), roundf(hp.y - 8.0))
			_leak_fx.draw_rect(Rect2(bp, Vector2(15, 3)), Color(0.03, 0.06, 0.06, 0.85))
			_leak_fx.draw_rect(Rect2(bp + Vector2(1, 1), Vector2(roundf(13.0 * float(l["prog"])), 1)), Color("#ddc08a"))


static func _tx(k: String) -> String:
	var row: Array = TXT[k]
	return row[1] if I18n.is_zh() else row[0]


func _process(delta: float) -> void:
	if _finished:
		return
	if runner.ff:
		dev_skip()
		return
	if _paused:                                      # 在货舱添燃料：碎石、燃料、漏气全停
		return
	_t += delta
	_view_step(delta)
	_repair_step()
	_air_step(delta)
	_dark_step(delta)
	_spark_step(delta)
	if _ending:
		_end_step(delta)
		return
	# ---- 船上下挪
	var dir := 0.0
	if _auto:
		var goal := _auto_goal()
		if absf(goal - cockpit.ship_goal) > 0.5:
			dir = signf(goal - cockpit.ship_goal)
	else:
		dir = Input.get_axis("ui_up", "ui_down")
		if Input.is_key_pressed(KEY_W):
			dir -= 1.0
		if Input.is_key_pressed(KEY_S):
			dir += 1.0
		if dir == 0.0:
			dir = _push
		dir = clampf(dir, -1.0, 1.0)
	# 按住：目标位置 ship_goal 匀速走（最多 ±_shift），船本身用弹簧追它（cockpit_room._ship_step：缓起缓停、1 像素回弹）
	if dir != 0.0:
		_idle = 0.0
		var step := _move * delta * _leak_drag()
		if _auto:
			step = minf(step, absf(_auto_goal() - cockpit.ship_goal))
		cockpit.ship_goal = clampf(cockpit.ship_goal + dir * step, -_shift, _shift)
		if _t > 0.6 and not _zoom:  # 边躲边修的提示长一点（三样键都要看到），到 7 秒再淡
			_hint_out()
	else:
		_idle += delta
		if _idle > 1.5 and not _auto:
			cockpit.ship_goal = move_toward(cockpit.ship_goal, 0.0, BACK * delta)
	if _t > 7.0 and not _hint.has_meta("timed"):      # 只淡一次（原来每帧都调，后面重新亮起来的提示会被马上掐掉）
		_hint.set_meta("timed", true)
		_hint_out()
	# ---- 波次
	while not _plan.is_empty() and _t >= float(_plan[0]["t"]):
		_spawn(_plan.pop_front())
	var busy := false
	for w in _waves:
		_update_wave(w, delta)
		if not _wave_clear(w):
			busy = true
	_fx.queue_redraw()
	_leak_step(delta)
	_fuel_tick(delta)
	if _finished or _paused:
		return
	if _arrived and _plan.is_empty() and not busy:
		_finish()                                    # 绿线到 0 = 到了：碎石过完就收尾，漏点不再拖（_finish 里算修好）
		return
	if _safe0 > 0.0 and not _arrived and _t <= sec * 1.5 + 10.0:
		# 还没到（绿线没降到 0）：波次先排完了就零星来单块（上下轮着），没漏的漏点马上出来；到了才收尾
		if _plan.is_empty() and not busy:
			for l in _leak_plan:
				l["t"] = _t
			if _t + 1.4 < _arrive:
				_extra_lane *= -1
				_plan.append({"t": _t + 1.4, "k": "one", "lane": _extra_lane})
		return
	var leaks_left := not _leak_plan.is_empty() or _leaks_fixed < _leaks.size()
	if leaks_left and _t <= sec * 1.5 + 10.0:
		# 波次排完了还有漏没修：漏点立刻都出来，接着零星来单块（上下轮着），修完才收尾
		if _plan.is_empty() and not busy:
			for l in _leak_plan:
				l["t"] = _t
			_extra_lane *= -1
			_plan.append({"t": _t + 1.4, "k": "one", "lane": _extra_lane})
		return
	if _repair_at != "" and not _repair_done:
		if _plan.is_empty() and not busy:
			for w in _waves:
				_free_wave(w)
			_waves.clear()
			_repair_lane *= -1
			_plan.append({"t": _t + 1.0, "k": "pair", "lane": _repair_lane})
	elif (_plan.is_empty() and not busy) or _t > sec * 1.5 + 10.0:
		_finish()


## 自动玩：最早一波还没飞过船尾的，挪到它的安全通道（黑墙先「听」_dark_wait 秒，原地不动）
func _auto_goal() -> float:
	for w in _waves:
		if not _wave_clear(w):
			if w["dark"] and _t - float(w["t0"]) < _dark_wait:
				return cockpit.ship_goal
			return float(w["safe"])
	return cockpit.ship_goal


## 这一波的碎石都飞过船尾了（或者撞飞了）
func _wave_clear(w: Dictionary) -> bool:
	for r in w["rocks"]:
		var st := str(r["state"])
		if st in ["warn", "fly"] and float(r["x"]) - (r["size"] as Vector2).x / 2.0 < _x1:
			return false
	return true


func _hint_out() -> void:
	if _hint.get_meta("out", false):
		return
	_hint.set_meta("out", true)
	create_tween().tween_property(_hint, "modulate:a", 0.0, 1.2)


# ======================================================================= 出波次
func _spawn(e: Dictionary) -> void:
	match str(e["k"]):
		"one":
			_wave_lane(int(e["lane"]))
		"pair":
			_wave_lane(int(e["lane"]))
			_plan.push_front({"t": _t + PAIR_DT, "k": "one", "lane": int(e["lane"])})
		"gap":
			_wave_gap(float(e["g"]), false)
		"final":
			var gs: Array = e["g"]
			_play("nav_alert", -12.0)
			_play("flight_rumble", -6.0)
			_wave_gap(float(gs[0]), true)
			_waves[-1]["last"] = gs.size() == 1
			for i in range(1, gs.size()):
				_plan.push_front({"t": _t + FINAL_ROW * i, "k": "row", "g": float(gs[i]), "last": i == gs.size() - 1})
		"row":
			_play("flight_rumble", -9.0)
			_wave_gap(float(e["g"]), true)
			_waves[-1]["last"] = bool(e.get("last", false))
		"meteor":
			_wave_meteor()
		"dark_on":
			_dark_start()
		"dark":
			_wave_gap(roundf(float(e["g"])), false, _dark_lead)        # 只有上 / 中 / 下三条航道
			_waves[-1]["dark"] = true
			_waves[-1]["last"] = bool(e.get("last", false))
			_hint_lv = 0
			_bell_t = 0.6                                              # 新一排：铃很快先响一下
	_plan.sort_custom(func(a, b): return float(a["t"]) < float(b["t"]))


## 单块：贴着上沿（lane -1）或下沿（+1）；安全通道 = 往另一边挪满
func _wave_lane(lane: int) -> void:
	var tex := _pick_rock()
	var sz := tex.get_size()
	var top := float(_hull.get("T", 100))
	var bot := float(_hull.get("B", 206))
	# 碎石中心：主船身上沿 / 下沿往里 LANE_IN（碎石特别大时往外让一点，保证挪满 _shift 一定躲得开）
	var inset := minf(LANE_IN, _shift - sz.y / 2.0 - 4.0)
	var y := roundf(top + inset if lane < 0 else bot - inset)
	# 碎石右边沿在 _warn 秒后碰到这条道上船身最左边那一列
	var cx := _front_x(y - sz.y / 2.0 + 2.0, y + sz.y / 2.0 - 2.0)
	var w := _new_wave(-float(lane) * _shift, "one")
	_add_rock(w, tex, cx - sz.x / 2.0 - _rock_v * _warn, y, true, _rng.randi_range(1, 2))
	_beep(y)


## 一排墙，缝在 g × _shift（船挪到那里，船身上下各留 GAP_M）；big = 结尾那几排（墙更密、碎屑更多）
## lead < 0 = 平常的预告量 _warn；黑墙传 DARK_LEAD（提前很久开始找，碎石还在屏幕左边外面）
func _wave_gap(g: float, big: bool, lead := -1.0) -> void:
	var safe := roundf(clampf(g, -1.0, 1.0) * _shift)
	var top := float(_hull.get("T", 100)) + safe - GAP_M          # 缝的上沿 / 下沿（屏幕 y）
	var bot := float(_hull.get("B", 206)) + safe + GAP_M
	var ld := _warn if lead < 0.0 else lead
	var w := _new_wave(safe, "final" if big else "gap", ld)
	var x_hit := _nose() - _rock_v * ld                            # 墙的右沿 ld 秒后到机头
	# 往上：第一块的碰撞下沿正好是缝的上沿，再一块块往上摞到屏幕顶（燃料栏下面）
	var y := top
	var first := true
	var jit := 4.0 if big else 2.0
	while y > 40.0:
		var tex := _pick_rock()
		var sz := tex.get_size()
		var cy := y - (sz.y / 2.0 - 2.0)
		var dx := 0.0 if first else _rng.randf_range(-jit, jit) * 3.0
		_add_rock(w, tex, x_hit - sz.x / 2.0 + minf(0.0, dx), roundf(cy), first, (2 if big else 1) if first else (1 if big else 0))
		y = cy - sz.y / 2.0 - _rng.randf_range(1.0, 4.0 + jit)
		first = false
	y = bot
	first = true
	while y < 268.0:
		var tex := _pick_rock()
		var sz := tex.get_size()
		var cy := y + (sz.y / 2.0 - 2.0)
		var dx := 0.0 if first else _rng.randf_range(-jit, jit) * 3.0
		_add_rock(w, tex, x_hit - sz.x / 2.0 + minf(0.0, dx), roundf(cy), first, (2 if big else 1) if first else (1 if big else 0))
		y = cy + sz.y / 2.0 + _rng.randf_range(1.0, 4.0 + jit)
		first = false
	# 两声：上面的墙一声（高）、下面的墙一声（低）；黑墙不响（靠轰鸣和气流声找）
	if lead >= 0.0:
		return
	_beep(top - 8.0)
	get_tree().create_timer(0.16, false).timeout.connect(_beep.bind(bot + 8.0))


func _new_wave(safe: float, kind: String, lead := -1.0) -> Dictionary:
	waves_n += 1
	var w := {"safe": safe, "t0": _t, "at": _t + (_warn if lead < 0.0 else lead), "rocks": [], "bumped": false, "kind": kind,
		"last": false, "out": false, "dark": false}
	_waves.append(w)
	return w


func _pick_rock() -> Texture2D:
	if not _rock_tex.is_empty():
		return _rock_tex[_rng.randi() % _rock_tex.size()]
	return Inventory.placeholder("rock", Color("#2a2f2c"), 20, 16)


## 一块碎石（中心 x, y）；key = 离船近、画预告划痕的那块；bits = 跟着飞几颗碎屑
func _add_rock(w: Dictionary, tex: Texture2D, x: float, y: float, key: bool, bits: int) -> void:
	var spr := Sprite2D.new()
	spr.centered = true
	spr.texture = tex
	spr.flip_h = _rng.randf() < 0.5
	spr.visible = false
	cockpit.debris_layer.add_child(spr)
	var r := {"x": x, "y": y, "spr": spr, "size": tex.get_size(), "state": "warn", "vx": _rock_v, "vy": 0.0, "hit_t": 0.0,
		"bits": [], "key": key, "grazed": false, "near": 999.0, "passed": false}
	for i in bits:
		var b := Sprite2D.new()
		b.centered = true
		if not _bit_tex.is_empty():
			b.texture = _bit_tex[_rng.randi() % _bit_tex.size()]
		else:
			b.texture = Inventory.placeholder("bit", Color("#2a2f2c"), 3, 3)
		b.visible = false
		cockpit.debris_layer.add_child(b)
		(r["bits"] as Array).append({"spr": b, "dx": -_rng.randf_range(16.0, 40.0), "dy": _rng.randf_range(-9.0, 9.0)})
	(w["rocks"] as Array).append(r)


## 方位声：碎石在船中线上面音高高、下面低（船上的仪器响：声像在船那儿）
func _beep(y: float) -> void:
	var mid := (float(_hull.get("T", 100)) + float(_hull.get("B", 206))) / 2.0
	_play("nav_beep", -14.0, 1.25 if y < mid else 0.85, _pan(_ship_cx))


## 屏幕 x → 声像（和 _play 的摆法对上：屏幕中间 0，往右 320 像素 = 1）
static func _pan(x: float) -> float:
	return clampf((x - 240.0) / 320.0, -1.0, 1.0)


## 机头（船身最左那一列）的屏幕 x
func _nose() -> float:
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	var nose := float(int(_hull.get("x0", 80)))
	for i in tops.size():
		if tops[i] >= 0:
			return nose + float(i)
	return nose


## 这条道（屏幕 y0..y1，船没挪的时候）上船身最左边那一列的屏幕 x
func _front_x(y0: float, y1: float) -> float:
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	var bots: PackedInt32Array = _hull.get("bot", PackedInt32Array())
	var x0 := int(_hull.get("x0", 80))
	for i in tops.size():
		if tops[i] >= 0 and float(tops[i]) < y1 and float(bots[i]) > y0:
			return float(x0 + i)
	return float(x0 + 40)


## 碎石（屏幕矩形）和船身的竖直间隙：< 0 = 碰到了；船身在这几列都没有 = 999
func _clearance(r: Rect2) -> float:
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	var bots: PackedInt32Array = _hull.get("bot", PackedInt32Array())
	var x0 := int(_hull.get("x0", 80))
	var sy: float = cockpit.ship_y()
	var i0 := maxi(0, int(floorf(r.position.x)) - x0)
	var i1 := mini(tops.size() - 1, int(ceilf(r.end.x)) - x0)
	var best := 999.0
	for i in range(i0, i1 + 1):
		if tops[i] < 0:
			continue
		var gap := maxf(r.position.y - (float(bots[i]) + sy), (float(tops[i]) + sy) - r.end.y)
		best = minf(best, gap)
	return best


# ======================================================================= 每帧：碎石
func _update_wave(w: Dictionary, delta: float) -> void:
	for r in w["rocks"]:
		_update_rock(w, r, delta)
	if bool(w["last"]) and not bool(w["out"]) and _wave_clear(w):
		w["out"] = true
		_breakout()


func _update_rock(w: Dictionary, r: Dictionary, delta: float) -> void:
	var st := str(r["state"])
	if st == "gone":
		return
	var spr: Sprite2D = r["spr"]
	var sz: Vector2 = r["size"]
	r["x"] = float(r["x"]) + float(r["vx"]) * delta
	r["y"] = float(r["y"]) + float(r["vy"]) * delta
	var x := float(r["x"])
	var y := float(r["y"])
	if st == "warn" and x + sz.x / 2.0 > -2.0:
		r["state"] = "fly"
		st = "fly"
		if r["key"]:
			_lead.append(float(w["at"]) - _t)
			_play("debris_pass_l", -12.0 if w["kind"] == "one" else -10.0, 1.0, -0.7)
	spr.visible = st != "warn"
	spr.position = Vector2(roundf(x), roundf(y))
	for b in r["bits"]:
		var bs: Sprite2D = b["spr"]
		bs.visible = spr.visible and st != "hit"
		bs.position = Vector2(roundf(x + float(b["dx"])), roundf(y + float(b["dy"])))
	if st == "fly":
		var rr := Rect2(x - sz.x / 2.0 + 2.0, y - sz.y / 2.0 + 2.0, maxf(1.0, sz.x - 4.0), maxf(1.0, sz.y - 4.0))
		var c := _clearance(rr)
		if c < 0.0:
			_bump(w, r)
		else:
			r["near"] = minf(float(r["near"]), c)
			if not r["grazed"] and c < GRAZE and not w["bumped"]:
				r["grazed"] = true
				_graze(rr, c)
			if not r["passed"] and rr.position.x > _x1:
				r["passed"] = true                       # 擦过去了：声音往右走
				if r["key"]:
					_play("debris_pass_r", -16.0, 1.0, _pan(_x1) + 0.27)   # 船尾再往右一点（船在中间时 = 0.6）
	elif st == "hit":
		r["hit_t"] = float(r["hit_t"]) + delta
		r["vy"] = float(r["vy"]) * 0.97
		var k := clampf(float(r["hit_t"]) / 0.5, 0.0, 1.0)
		spr.modulate.a = 1.0 - floorf(k * 4.0) / 4.0
		if k >= 1.0:
			_free_rock(r)
			return
	if x - sz.x / 2.0 > 480.0 + 50.0:
		_free_rock(r)


func _free_rock(r: Dictionary) -> void:
	r["state"] = "gone"
	if is_instance_valid(r["spr"]):
		(r["spr"] as Node).queue_free()
	for b in r["bits"]:
		if is_instance_valid(b["spr"]):
			(b["spr"] as Node).queue_free()


func _free_wave(w: Dictionary) -> void:
	for r in w["rocks"]:
		_free_rock(r)


## 撞到：碎石弹开；同一波只算一次（晃一下、闷响、扣一点燃料、晨偶尔说一句）
func _bump(w: Dictionary, r: Dictionary) -> void:
	r["state"] = "hit"
	r["vx"] = 90.0                                   # 弹开：慢下来、往外翻
	var mid: float = (float(_hull.get("T", 100)) + float(_hull.get("B", 206))) / 2.0 + float(cockpit.ship_y())
	r["vy"] = 70.0 * (-1.0 if float(r["y"]) < mid else 1.0)
	if w["dark"]:
		(r["spr"] as Node2D).z_index = 3                # 黑里撞到：碎石闪出来（画到黑幕上面，弹开、淡掉）
	if w["bumped"]:
		return
	w["bumped"] = true
	if str(w["kind"]) == "meteor":
		_on_meteor()
		return
	if _fuel_mode:
		_hit_t = _hit_sec                            # 撞了：这几秒燃料漏得更快
	bumps += 1
	if w["dark"]:
		_dark_bumps += 1
	level._shake = 0.35
	level._shake_amp = 2.0
	_play("debris_bump", -4.0, 1.0, _pan(_ship_cx))
	if _fuel_per > 0 and _fuel_left > 0 and StoryState.fuel_on():
		var n := mini(_fuel_per, _fuel_left)
		_fuel_left -= n
		var was := StoryState.fuel()
		StoryState.set_fuel(was - n)
		level.fuel_changed(was, StoryState.fuel_need())
	# 晨偶尔说一句（第 1、3、5 次撞，最多三句；不锁人）
	if bumps % 2 == 1 and _said < BUMP_LINES.size() and not _auto:
		var l: Dictionary = BUMP_LINES[_said]
		_said += 1
		var tl: Array = runner.txt_lang(l)
		var anchor: Callable = cockpit.far_anchor if _far else runner._anchor.bind("chen")   # 远景里晨看不见：从船窗上方冒
		runner.dlg.murmur(runner.txt_in(runner.speakers.get("chen", "chen"), str(tl[1])), runner.NAME_COLORS["chen"], str(tl[0]),
			anchor, runner.mark_added)


## 擦边：泛光闪一下 + 擦到的地方冒几颗火星 + 一声轻的「咻」
func _graze(rr: Rect2, _c: float) -> void:
	grazes += 1
	var g: Node2D = cockpit.far_glow if _far and cockpit.far_glow != null else cockpit.glow
	if g != null:
		g.strength = 1.0
	_play("ship_whoosh", -9.0, 1.35, _pan(rr.get_center().x))
	var mid: float = (float(_hull.get("T", 100)) + float(_hull.get("B", 206))) / 2.0 + float(cockpit.ship_y())
	var above := rr.get_center().y < mid
	var p := Vector2(rr.get_center().x, rr.end.y + 1.0 if above else rr.position.y - 1.0)
	for i in 6:
		_sparks.append({"p": p + Vector2(_rng.randf_range(-4.0, 4.0), 0.0),
			"v": Vector2(_rng.randf_range(20.0, 80.0), (-1.0 if above else 1.0) * -_rng.randf_range(5.0, 30.0)), "age": 0.0})


func _spark_step(delta: float) -> void:
	for i in range(_sparks.size() - 1, -1, -1):
		var s: Dictionary = _sparks[i]
		s["age"] = float(s["age"]) + delta
		s["p"] = (s["p"] as Vector2) + (s["v"] as Vector2) * delta
		if float(s["age"]) > 0.4:
			_sparks.remove_at(i)


## 结尾最后一排过去：穿出去——泛光闪亮、一声长「呼」+ 推进、轻轻一晃，气流声慢慢收掉
func _breakout() -> void:
	var g: Node2D = cockpit.far_glow if _far and cockpit.far_glow != null else cockpit.glow
	if g != null:
		g.strength = 1.0
	_play("ship_whoosh", -5.0, 0.8, _pan(_ship_cx))
	_play("engine_boost", -12.0, 1.0, _pan(_ship_cx))
	level._shake = 0.3
	level._shake_amp = 1.0
	_hint_out()
	if _dark_on:
		_dark_end()


# ======================================================================= 黑窗听航道（终章）
## 进云层：黑幕慢慢落下，轰鸣循环起来，提示换成「听——找最安静的那条」
func _dark_start() -> void:
	if _dark_on:
		return
	_dark_on = true
	_dark = Node2D.new()
	_dark.name = "DebrisDark"
	_dark.z_index = 1
	_dark.draw.connect(func(): _dark.draw_rect(Rect2(-40, -40, 560, 350), Color(DARK_C, _dark_a)))
	cockpit.debris_layer.add_child(_dark)
	var tw := create_tween()
	tw.tween_method(_set_dark, 0.0, DARK_A, DARK_IN if not (_auto and not _real) else 0.4).set_trans(Tween.TRANS_SINE)
	_play("flight_rumble", -8.0)
	_rumble = _loop("flight_rumble", -60.0)          # _loop 已设成真循环，不用 finished → play 重开
	# 提示换一句（上一句淡出了也重新亮一下，5 秒后淡掉）
	_hint.text = _tx("dark_hint")
	_hint.set_meta("out", false)
	var th := create_tween()
	th.tween_property(_hint, "modulate:a", 0.85, 0.8).set_delay(0.8)
	th.tween_interval(5.0)
	th.tween_callback(_hint_out)


## 穿出云层：黑幕慢慢退掉（云开），轰鸣收掉
func _dark_end() -> void:
	_dark_on = false
	if is_instance_valid(_dark):
		create_tween().tween_method(_set_dark, _dark_a, 0.0, DARK_IN if not (_auto and not _real) else 0.4).set_trans(Tween.TRANS_SINE)


func _set_dark(a: float) -> void:
	_dark_a = a
	if is_instance_valid(_dark):
		_dark.queue_redraw()


## 最早一排还没过去的黑墙（没有 = 空）
func _dark_wave() -> Dictionary:
	for w in _waves:
		if w["dark"] and not _wave_clear(w):
			return w
	return {}


## 每帧：船离安全航道多远 → 轰鸣 / 气流的音量；铜铃引路；找久了提示加强
func _dark_step(delta: float) -> void:
	var w := _dark_wave()
	var want_line := 0.0
	_dark_ctl = false
	if not w.is_empty() and _dark_on:
		_dark_ctl = true
		var off: float = (float(cockpit.ship_goal) - float(w["safe"])) / maxf(1.0, _shift)      # + = 船在缝下面（撞下面那片），- = 在上面
		var d := absf(off)                                                          # 0 = 正在航道里，2 = 最远
		var k := clampf(d, 0.0, 1.0)
		var lost := d > DARK_NEAR
		var since := _t - float(w["t0"])
		if lost and since > DARK_HINT2:
			_hint_lv = 2
		elif lost and since > DARK_HINT1:
			_hint_lv = maxi(_hint_lv, 1)
		# 往目标音量平滑地靠（每秒最多 40 dB）：进黑雾那一下不再从 -60 一帧跳上去（11-04 --qa_audio）
		# 轰鸣：越偏越响；音高 = 撞的是哪片碎石（船在缝上面 → 上面那片 → 高；在下面 → 低）
		if is_instance_valid(_rumble):
			_rumble.volume_db = move_toward(_rumble.volume_db, lerpf(RUMBLE_IN, RUMBLE_OUT, k), 40.0 * delta)
			_rumble.pitch_scale = move_toward(_rumble.pitch_scale, clampf(1.0 - RUMBLE_PITCH * off, 0.55, 1.6), 1.5 * delta)
		# 气流：进航道最清楚，偏了被轰鸣盖住（音高在 _air_step 里按航道高低）
		_air_dark_db = move_toward(_air_dark_db, lerpf(-10.0, -30.0, k), 40.0 * delta)
		if is_instance_valid(_air):
			_air.volume_db = _air_dark_db
		# 引擎：安静航道里变柔（小声、音高低一点），偏了发紧
		_hum_step(lerpf(HUM_SOFT, HUM_TENSE, k), lerpf(0.9, 1.04, k), delta)
		# 铜铃：按航道高低定音高，隔一会儿响一下（提示加强以后更响、更密）；进了航道就不响了（已经找到）
		if _bell and lost:
			_bell_t -= delta
			if _bell_t <= 0.0:
				_bell_t = 2.2 if _hint_lv == 0 else 1.3
				var g := float(w["safe"]) / maxf(1.0, _shift)
				_bell_n += 1
				_play("bell_soft", -16.0 if _hint_lv == 0 else -8.0, 1.0 - 0.22 * g, _pan(_ship_cx))
				if _auto:
					print("DARK_BELL t=%.2f lane=%+d lv=%d" % [_t, int(roundf(g)), _hint_lv])
		# 气流线：有铃永远不画；铜铃烧了，找了 DARK_HINT1 秒还没进航道才淡入（DARK_HINT2 更亮）。进了航道就慢慢淡掉
		if not _bell and lost and _hint_lv >= 1:
			want_line = [0.0, 0.22, 0.4][_hint_lv]
		if _auto:
			_dark_log_t -= delta
			if _dark_log_t <= 0.0:
				_dark_log_t = 0.5
				print("DARK_AUDIO t=%.2f off=%+.2f lost=%s rumble=%.1fdB/p%.2f air=%.1fdB/p%.2f hum=%s line=%.2f bell=%s lv=%d" % [_t, off, lost,
					_rumble.volume_db if is_instance_valid(_rumble) else -99.0, _rumble.pitch_scale if is_instance_valid(_rumble) else 0.0,
					_air.volume_db if is_instance_valid(_air) else -99.0, _air.pitch_scale if is_instance_valid(_air) else 0.0,
					_hum_str(), _line_a, _bell, _hint_lv])
	else:
		if is_instance_valid(_rumble):
			_rumble.volume_db = move_toward(_rumble.volume_db, -60.0, 30.0 * delta)
		if _hum_ctl:
			_hum_step(0.0, 1.0, delta)                  # 两排黑墙之间 / 穿出去：引擎声慢慢回平常
	_line_a = move_toward(_line_a, want_line, delta * (0.5 if want_line > _line_a else 0.3))


## 驾驶舱引擎声（level._engine_hum，level 自己的音量 tween 在跑时不抢）往「平常 + db_off、音高 pitch」平滑靠
func _hum_step(db_off: float, pitch: float, delta: float) -> void:
	var h = level.get("_engine_hum")
	if not (h is AudioStreamPlayer) or not is_instance_valid(h) or bool(level.get("_hum_done")):
		return
	var tw = h.get_meta("fade_tw") if h.has_meta("fade_tw") else null
	if tw is Tween and (tw as Tween).is_valid() and (tw as Tween).is_running():
		return
	_hum_ctl = true
	var base := _hum_db()
	h.volume_db = move_toward(h.volume_db, base + db_off, 12.0 * delta)
	h.pitch_scale = move_toward(h.pitch_scale, pitch, 0.25 * delta)


func _hum_db() -> float:
	var sc: Script = level.get_script()
	return float(sc.get_script_constant_map().get("HUM_DB", -20.0)) if sc != null else -20.0


func _hum_str() -> String:
	var h = level.get("_engine_hum")
	if not (h is AudioStreamPlayer) or not is_instance_valid(h):
		return "none"
	return "%.1fdB/p%.2f" % [h.volume_db, h.pitch_scale]


## 步骤完：引擎声回平常（音量走 level 自己的 _fade_db，音高 tween 回 1）
func _hum_restore(sec: float) -> void:
	if not _hum_ctl:
		return
	_hum_ctl = false
	var h = level.get("_engine_hum")
	if not (h is AudioStreamPlayer) or not is_instance_valid(h) or bool(level.get("_hum_done")):
		return
	level._fade_db(h, _hum_db(), sec)
	level.create_tween().tween_property(h, "pitch_scale", 1.0, sec)


# ======================================================================= 气流（声音 + 安全通道的气流线）
func _air_step(delta: float) -> void:
	var want := 0.0
	for w in _waves:
		if not _wave_clear(w):
			want = 1.0
			_air_g = move_toward(_air_g, float(w["safe"]), 160.0 * delta)
			break
	if _ending:
		want = 0.0
	_air_on = move_toward(_air_on, want, delta / (0.6 if want > _air_on else 1.2))
	if is_instance_valid(_air) and not _dark_ctl:      # 黑墙在的时候音量归 _dark_step 管（原来这里每帧盖回 -15，黑里的大小声差没出来）
		_air.volume_db = lerpf(-50.0, -15.0, sqrt(_air_on))
		_air_dark_db = _air.volume_db
	if is_instance_valid(_air):
		_air.pitch_scale = 1.0 - 0.12 * _air_g / maxf(1.0, _shift)        # 通道在上面音高高一点
	_air_lines_step(delta)


## 气流线（每道独立的粒子，11-05 作者：「会突然往回一跳、撞到飞船前直接消失、整体移动」）：
##   每 AIR_EVERY 秒从屏幕左边外出生一道：按**那一刻**的安全通道（_air_g）在通道里轮 AIR_SLOTS 档高度定 y、定长度和速度，
##   之后每帧只加 v × delta 往右飞，不回头、不换 y（通道换了只影响后面出生的线）。
##   删：出了屏幕右边；或者整条都在船身后面（线尾过了这一行上船头 2 像素、线头没露出船尾）——debris_layer 在船后，看不见才删。
##   穿出去（_ending）以后不再出新的，飞着的照飞（亮度 _air_on 自己慢慢淡掉）。
func _air_lines_step(delta: float) -> void:
	_air_spawn -= delta
	if _air_spawn <= 0.0 and not _ending:
		_air_spawn = AIR_EVERY
		var top := float(_hull.get("T", 100)) + _air_g
		var bot := float(_hull.get("B", 206)) + _air_g
		var slot := (_air_n * 3) % AIR_SLOTS                                   # 0 3 1 4 2：相邻两道不挨着
		var y := roundf(lerpf(top + 4.0, bot - 4.0, (float(slot) + 0.5) / float(AIR_SLOTS))) + float(_rng.randi_range(-1, 1))
		var ln := 10.0 + float((_air_n * 7) % 3) * 5.0
		_air_lines.append({"x": -ln, "y": y, "ln": ln, "v": 230.0 + float(_air_n % 3) * 35.0})
		_air_n += 1
	var sy: float = cockpit.ship_y()
	var i := _air_lines.size() - 1
	while i >= 0:
		var L: Dictionary = _air_lines[i]
		var x0 := float(L["x"]) + float(L["v"]) * delta
		if _air_qa and x0 < float(L["x"]):
			_air_qa_bad += 1
			print("QA_AIR 气流线往回跳 x %.1f -> %.1f" % [float(L["x"]), x0])
		L["x"] = x0
		var x1 := x0 + float(L["ln"])
		var gone := x0 >= 480.0
		if not gone:
			var fx := _hull_front_at(float(L["y"]) - sy)
			gone = fx >= 0.0 and x0 > fx + 2.0 and x1 < _x1 - 2.0
			if _air_qa and gone and x0 <= fx:
				_air_qa_bad += 1
				print("QA_AIR 气流线在船前面消失 x %.1f 船头 %.1f" % [x0, fx])
		if gone:
			_air_lines.remove_at(i)
		i -= 1


## 屏幕第 y 行（船没挪时的坐标）上船身最左那一列的屏幕 x；这一行没有船身 = -1
func _hull_front_at(y: float) -> float:
	var tops: PackedInt32Array = _hull.get("top", PackedInt32Array())
	var bots: PackedInt32Array = _hull.get("bot", PackedInt32Array())
	var x0 := int(_hull.get("x0", 80))
	for i in tops.size():
		if tops[i] >= 0 and float(tops[i]) <= y and float(bots[i]) >= y:
			return float(x0 + i)
	return -1.0


# ======================================================================= 收尾
## F8 自测 / 跳节拍：直接做完，镜头直接回剖面
# ======================================================================= 11-08 大陨石 / 燃料一直在烧
## 躲不开的一排：缝里也塞满（撞上就是剧情）
func _wave_meteor() -> void:
	_play("nav_alert", -8.0)
	_play("flight_rumble", -2.0)
	_wave_gap(0.0, true)
	var w: Dictionary = _waves[-1]
	w["kind"] = "meteor"
	var rocks: Array = w["rocks"]
	var x_hit := _nose() - _rock_v * _warn
	var y := float(_hull.get("T", 100)) - GAP_M
	var bot := float(_hull.get("B", 206)) + GAP_M
	while y < bot:
		var tex := _pick_rock()
		var sz := tex.get_size()
		_add_rock(w, tex, x_hit - sz.x / 2.0, roundf(y + sz.y / 2.0 - 2.0), rocks.size() < 2, 2)
		y += sz.y - 3.0
	w["safe"] = 0.0


func _on_meteor() -> void:
	if _meteor_hit:
		return
	_meteor_hit = true
	bumps += 1
	level._shake = 1.4
	level._shake_amp = 5.0
	_play("debris_bump", 2.0, 0.7, _pan(_ship_cx))
	_play("flight_rumble", 0.0, 0.8)
	_flash_once(0.85, 0.9)
	StoryState.set_flag("flight1_meteor")
	_plan.clear()
	print("COCKPIT meteor hit t=%.1f" % _t)


func _flash_once(a: float, sec: float) -> void:
	if not is_instance_valid(_flash):
		return
	_flash.color.a = a
	create_tween().tween_property(_flash, "color:a", 0.0, sec).set_trans(Tween.TRANS_SINE)


func _fuel_tick(delta: float) -> void:
	if not _fuel_mode or _crashed or _ending:
		return
	if _safe0 > 0.0 and not _arrived:
		if _arrive <= 0.0:
			var last := 0.0
			for e in _plan:
				last = maxf(last, float(e["t"]))
			_arrive = maxf(last + ARRIVE_PAD, 5.0)
		_safe = _safe0 * maxf(0.0, 1.0 - _t / _arrive)
		var si := str(int(ceilf(_safe)))
		if si != str(StoryState.props.get("fuel_safe", "")):
			StoryState.set_prop("fuel_safe", si)      # 燃料条上的绿线跟着往下走（fuel_bar.gd 每帧读）
		if _safe <= 0.0:
			_arrived = true
			StoryState.set_prop("fuel_safe", "0")
			print("COCKPIT arrived t=%.1f fuel=%d" % [_t, StoryState.fuel()])
	if _arrived:
		if _refuel_hint != null:
			_refuel_hint.visible = false
		return                                        # 到了：不再烧
	_hit_t = maxf(0.0, _hit_t - delta)
	var open := 0
	for l in _leaks:
		if not l["fixed"]:
			open += 1
	var rate := _drain + (_hit_drain if _hit_t > 0.0 else 0.0) + _leak_drain * float(open)
	_fuel_f -= rate * delta
	var n := maxi(0, int(ceilf(_fuel_f)))
	if n != StoryState.fuel():
		StoryState.set_fuel(n)
	if _fuel_f <= 0.0:
		_crash()
		return
	var low := _safe > 0.0 and _fuel_f < _safe
	if _refuel_hint != null:
		_refuel_hint.visible = low and int(_t * 3.0) % 3 != 0
	var can: bool = low and not _refuel_st.is_empty() and not runner.BURN_PICK_GD.burnable(_refuel_st.get("items", null), str(_refuel_st.get("kind", ""))).is_empty()
	if _refuel_hint != null and low:
		_refuel_hint.text = _tx("refuel") if can or _refuel_st.is_empty() else _tx("refuel_none")
	if can and (_auto or Input.is_key_pressed(KEY_F)):
		_refuel()


## 按 F：去货舱烧东西添燃料（碎石停住），烧完回来接着飞
func _refuel() -> void:
	if _paused:
		return
	_paused = true
	_refuels += 1
	if _refuel_hint != null:
		_refuel_hint.visible = false
	var chen: Node2D = runner.chen
	var was_input: bool = chen.input_enabled
	chen.input_enabled = false
	chen.auto_dir = 0.0
	if _fixing:
		_fixing = false
		runner._anim({"who": "chen", "name": "idle"})
	var bgm = (load("res://scripts/bgm.gd") as GDScript).get_bgm(get_tree())
	bgm.play("space_choice", NAN, 1.0)
	print("COCKPIT refuel %d: fuel=%d" % [_refuels, StoryState.fuel()])
	await runner._burn_pick(_refuel_st)
	runner.cockpit_ui = self
	bgm.play("flight_theme", NAN, 1.0)
	_fuel_f = float(StoryState.fuel())
	if is_instance_valid(chen):
		chen.input_enabled = was_input and not _auto
	_paused = false


## 燃料烧光：坠毁（剧本 crash scene 演坏结局）
func _crash() -> void:
	if _crashed:
		return
	_crashed = true
	StoryState.set_fuel(0)
	level._shake = 1.6
	level._shake_amp = 6.0
	_play("debris_bump", 4.0, 0.6, _pan(_ship_cx))
	_flash_once(1.0, 1.4)
	print("COCKPIT crash t=%.1f" % _t)
	_done()


func dev_skip() -> void:
	if _finished:
		return
	if _far:
		cockpit.far_snap(false)
	_view_reset()
	cockpit.ship_goal = 0.0
	_done()


## 碎石都过去了：没拉远就直接结束；拉远了先让船回中间（弹簧 + 泛光），END_WAIT 秒后拉回剖面，拉完才结束
func _finish() -> void:
	if _finished or _ending:
		return
	if _air_qa:
		print("QA_AIR 气流线 出生 %d 道 异常 %d" % [_air_n, _air_qa_bad])
	_hint_out()
	for l in _leaks:                                 # 超时兜底：还漏着的算修好（不会输）
		if not l["fixed"]:
			l["fixed"] = true
			_leaks_fixed += 1
	_leak_plan.clear()
	if not _far and not _zoom:
		_done()
		return
	_ending = true
	_end_t = 0.0
	cockpit.ship_goal = 0.0


func _end_step(delta: float) -> void:
	_end_t += delta
	cockpit.ship_goal = 0.0
	for w in _waves:
		_update_wave(w, delta)
	_fx.queue_redraw()
	if not _back_in and _end_t >= (0.2 if _auto and not _real else END_WAIT):
		_back_in = true
		if _zoom:
			_view_go = 0.0
		else:
			cockpit.far_in(_zoom_sec)
	if _back_in and (_view_u <= 0.0 if _zoom else cockpit.far_u() <= 0.0):
		_view_reset()
		_done()


func _done() -> void:
	if _finished:
		return
	_finished = true
	_hint_out()
	done.emit()


# ======================================================================= 声音
## 音效（能调音高、声像 pan -1 左 .. +1 右；缺文件静默跳过，和 runner._sfx 一样记进统计）
func _play(snd: String, db: float, pitch := 1.0, pan := 0.0) -> void:
	if runner.ff:
		return
	var p: String = runner._sfx_path(snd)
	if p == "":
		runner.missing_sfx[snd] = true
		return
	var a := AudioStreamPlayer2D.new()
	a.stream = load(p)
	a.bus = "SFX"
	a.max_distance = 2000.0
	a.attenuation = 0.5
	a.volume_db = db
	a.pitch_scale = pitch
	level.add_child(a)
	a.global_position = level.cam_left() + Vector2(240.0 + clampf(pan, -1.0, 1.0) * 320.0, 135.0)
	a.play()
	a.finished.connect(a.queue_free)
	if (load("res://scripts/audio_fade.gd") as GDScript).is_loop(a):
		# 11-08 作者「管道炸裂的声音一直存在，直到章节结束」：hiss_thin 导入是循环的，每撞出一个漏点就多一条停不下来的嘶嘶。
		# 只放一遍（持续的嘶嘶归 _hiss，修好 / 结束会淡掉）
		runner._sfx_loop_once(a)
		a.set_meta("qa_attack_until", Engine.get_process_frames() + 20)   # 撞出漏点那一下是炸开的，故意硬起音（--qa_audio 不报）


## 循环的底噪（气流、轰鸣）：自己管音量；缺文件返回 null。wav 导入没开循环的（flight_rumble 2.2 秒）复制一份设成真循环——
## 原来靠 finished → play() 重开，每圈那一帧没在放又响着（--qa_audio hard_start），耳朵里也是断口（11-05）
func _loop(snd: String, db: float) -> AudioStreamPlayer:
	var p: String = runner._sfx_path(snd)
	if p == "":
		runner.missing_sfx[snd] = true
		return null
	var a := AudioStreamPlayer.new()
	a.name = "Loop_" + snd                           # 复制出来的循环流没有路径，--qa_audio 认不出名字，节点名顶上
	var s: AudioStream = load(p)
	if s is AudioStreamWAV and (s as AudioStreamWAV).loop_mode == AudioStreamWAV.LOOP_DISABLED:
		var w := (s as AudioStreamWAV).duplicate() as AudioStreamWAV
		w.loop_mode = AudioStreamWAV.LOOP_FORWARD
		w.loop_begin = 0
		w.loop_end = int(round(w.get_length() * w.mix_rate))
		s = w
	a.stream = s
	a.bus = "SFX"
	a.volume_db = db
	add_child(a)
	a.play()
	return a


# ======================================================================= 画：预告、气流线、火星
## 预告：碎石那条道的高度上，屏幕左边一道划痕（越来越长、一闪一闪，往右一格一格变淡）+ 一个远远的小影子（越来越大，左上一点亮边）。
## 10-29 验收：原来 3×1 的点、透明度 .25～.5，在暗云上几乎看不见 → 加粗加亮（仍比碎石本身淡）。
## 气流线：安全通道那个高度、几道 1 像素的细线往右流（很淡、不闪；每道独立，见 _air_lines_step），只画屏幕里的那截，船身自然挡住。
func _draw_fx() -> void:
	if _dark_on or _dark_a > 0.05:
		# 黑窗：气流线只是铜铃烧了以后的兜底提示（_dark_step 管亮度）；黑幕落下那两秒，前半段亮着的线跟着黑一起淡掉
		var fade_vis := _air_on * 0.32 * clampf(1.0 - _dark_a / DARK_A, 0.0, 1.0) if _dark_on else 0.0
		var la := maxf(_line_a, fade_vis)
		if la > 0.01:
			_draw_air(la)
	elif _air_on > 0.0:
		_draw_air(_air_on * 0.32)                     # 亮度平滑（原来 4 档，一档一跳）
	for w in _waves:
		if w["dark"]:
			continue                                 # 黑墙没有划痕预告
		for r in w["rocks"]:
			if str(r["state"]) != "warn":
				continue
			var k := clampf((_t - float(w["t0"])) / WARN, 0.0, 1.0)
			var y := roundf(float(r["y"]))
			var a := 0.75 if int(_t * 6.0) % 2 == 0 else 0.5
			if r["key"]:
				var ln := roundf(14.0 + 60.0 * k)
				var x := 0.0
				while x < ln:
					var f := floorf((1.0 - x / (ln + 10.0)) * 4.0) / 4.0          # 往右 4 档变淡
					_fx.draw_rect(Rect2(x, y, 4, 1), Color(SCRATCH_C, a * f))
					_fx.draw_rect(Rect2(x + 2, y + 1, 3, 1), Color(SCRATCH_C, a * f * 0.5))   # 下面一道淡的，划痕厚一点
					x += 6.0
			var s := 3.0 + floorf(k * 4.0) - (0.0 if r["key"] else 1.0)          # 小影子 3 → 7 像素（墙里别的那几块小一号）
			var sx := roundf(6.0 + 14.0 * k)
			var rr := Rect2(sx, y - floorf(s / 2.0), s, s - 1.0)
			_fx.draw_rect(rr, Color(0.07, 0.09, 0.08, 0.9))
			_fx.draw_rect(Rect2(rr.position, Vector2(s - 1.0, 1.0)), Color(0.78, 0.86, 0.8, a))
			_fx.draw_rect(Rect2(rr.position, Vector2(1.0, s - 2.0)), Color(0.78, 0.86, 0.8, a))
	for s in _sparks:
		var k := 1.0 - float(s["age"]) / 0.4
		_fx.draw_rect(Rect2((s["p"] as Vector2).round(), Vector2.ONE), Color(SPARK_C, floorf(k * 4.0) / 4.0 * 0.9))


func _draw_air(a: float) -> void:
	if a <= 0.0:
		return
	for L in _air_lines:
		var x0 := maxf(0.0, float(L["x"]))
		var x1 := minf(480.0, float(L["x"]) + float(L["ln"]))
		if x1 - x0 < 1.0:
			continue
		var y := float(L["y"])
		_fx.draw_rect(Rect2(roundf(x0), y, roundf(x1 - x0), 1), Color(AIR_C, a))
		_fx.draw_rect(Rect2(roundf(x1) - 3.0, y, 3, 1), Color(AIR_C, minf(0.5, a * 1.6)))   # 线头亮一点：读得出往右流


# ======================================================================= 输入（鼠标 / 触屏按住上下半边；键盘在 _process 里直接读）
func _input(event: InputEvent) -> void:
	if _finished or _auto:
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed and is_instance_valid(_repair_hint) and _repair_hint.visible and _repair_hint.get_global_rect().has_point(event.position):
			_repair()
			get_viewport().set_input_as_handled()
			return
		_push = (-1.0 if event.position.y < 135.0 else 1.0) if event.pressed else 0.0
		get_viewport().set_input_as_handled()
	elif event is InputEventScreenTouch:
		_push = (-1.0 if event.position.y < 135.0 else 1.0) if event.pressed else 0.0
		get_viewport().set_input_as_handled()
	elif event is InputEventMouseMotion and _push != 0.0:
		_push = -1.0 if event.position.y < 135.0 else 1.0
