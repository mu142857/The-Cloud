# 《云》The Cloud · 项目总览与改动记录

> **所有协作者（人 / 任何 AI）开始改东西前先读这份文件，改完在最下面「改动记录」追加一条。**
> 这里只放「现在是什么状态、谁改了什么」；详细设计、夜测报告仍在 `docs/` 里，下面给了索引。

---

## 1. 项目是什么

- Godot 4.7（GL Compatibility），像素风 2D 叙事冒险。视口 480×270，`canvas_items` 拉伸，默认窗口 1440×810。
- 一句话剧情：晨要找朋友画过的那头大象，飞船一路坏一路修，每到一个星球就离大象更近一点（见 `docs/剧情简版.md`）。
- 设计原则（摘自 `docs/forest_chapter.md`「硬规矩」）：零门槛艺术作品，**不是小游戏合集**；没有失败、没有计时；听声音的地方必须同时有画面提示；晨的动画永远 100ms 一帧；硬边像素、不描边、不用纯黑纯白。

## 2. 目录速查

| 路径 | 内容 |
|---|---|
| `scenes/main.tscn` → `scripts/main.gd` | 启动：读设置后进 `scenes/level_forest.tscn` |
| `scripts/level_forest.gd` | **主关卡**（约 5000 行）：耳机提示 → 标题 → 下落 → 坠毁开场 → 起身 QTE → 交给剧本引擎；也负责章节切换、调试参数 |
| `scripts/title_cloud.gd` | 标题背景（云层小镇）+ 点开始后往下落到森林 |
| `scripts/getup_qte.gd` | 坠毁后连按 Q 起身（本2兔写的） |
| `scripts/story_runner.gd` / `story_world.gd` / `story_dialogue.gd` | 剧本引擎，读 `data/story_*.json` |
| `scripts/chapter_flow.gd` | 章节顺序：森林 → 飞行一 → 河流篇 → 终章 |
| `scripts/city_rain.gd` (+`.gdshader`) | 柔边细雨粒子（城市闪回、开场雨共用） |
| `scripts/dev_panel.gd` | F12 / F8 开发者面板（跳节拍、传送、探索） |
| `scripts/qa_text.gd` / `qa_live.gd` + `tools/qa_all.sh` | 自动 QA（字量、闪现、叠字、软锁），说明见 `docs/QA_自动检查.md` |
| `data/` | 剧本 JSON、物品表、成就、制作人员 |
| `art/` `audio/` `fonts/` | 素材；`tools/*.py` 生成部分美术 |
| `docs/` | 设计文档、夜测报告、台词表 |

## 3. 当前进度（2026-11-07）

| 部分 | 状态 | 文档 |
|---|---|---|
| 开场（耳机 → 标题 → 下落 → 坠毁 → 起身） | 可玩，11-07 调整了下落天气和节奏（见改动记录） | `level_forest.gd` 文件头注释 |
| 第一章 森林（木星） | 从头到「未完待续」卡能跑通 | `docs/forest_chapter.md` |
| 飞行一（驾驶舱） | 可玩 | `docs/flight_sky_contract.md`、`docs/phone_and_cockpit_contract.md` |
| 第二章 河流篇 | 可玩，四种开头 | `docs/river_plan.md`、`docs/river_rooms_contract.md`、`docs/第二章_*.md` |
| 终章 + 结局 + 尾声 | 三个结局都能到「全剧终」 | `docs/第三章计划.md`、`docs/river_and_beyond.md` |
| 闪回（四次） | 可玩 | `docs/闪回_实现说明.md` |
| 已知待定事项 | **大象还没有图**（最大一项）；其余见夜测汇总「要你定的」 | `docs/夜测_11-05_汇总.md` |
| 英文翻译 | 部分（未翻的回落中文） | `docs/en_translation_brief.md`、`docs/en_glossary.md` |

最近一次全量回归：11-05 夜（`tools/qa_all.sh`），0 闪现 0 叠字 0 软锁。

## 4. 协作约定

- 仓库根目录 `The-Cloud/` 是 git 仓库（origin: github.com/mu142857/The-Cloud）；`docs/forest_chapter.md` 约定 AI 不要 git commit，提交由人来做。改代码前先读要改的那个文件的文件头注释，项目习惯把「为什么这么做 + 作者原话 + 日期」写在注释里，新改动沿用。
- 改完至少跑：`--story_check`（剧本）和相关段落的 `--stage=` / `--beat=` 截图；大改跑 `tools/qa_all.sh`。
- 开场相关调试：`--stage=title|crash|play`，`--qa_live`（`QA_CAMJUMP` 等镜头跳检查）。
- 在下面「改动记录」追加：日期、谁（人名或 AI 名）、改了哪些文件、为什么、怎么验证 / 还没验证什么。

---

## 5. 改动记录（新的写在最上面）

### 2026-11-08 · Claude · 树屋三件：送还前低动力，做完换 100~130 的奖励

- 作者「房间里面的这些物品……完成任务之前，都是一些动力很低的物品，比如说20 到50，完成支线任务以后可以变成100到130」；问了以后：「能升级的升级，能换的换，不要不给奖励」，提前烧掉 = 支线直接关掉。
- `data/items.json`：return_radio / return_sign / return_lamp 加 `fuel_kind: unrelated` + `keepsake_burn` 30 / 40 / 25（还是 quest 类，不能拿去换东西）。
- `data/forest_side_a.json`：三件都是送回原处，所以都是「换」：收音机 → 旧菜单 keepsake_burn 30→120；路标原来什么都不给 → 新物品 `sa_ticket`「半张车票」115（日记里本来就写了底座旁的半张车票；**图标暂借 icon_card.png，要画新的**）；油灯 → 小屋钥匙改成能烧，110。
- 提前烧掉：三条送还目标的 not 加 `burned_return_*`，小吃棚 / 路标底座 / 小屋三个热点也加（烧了就不能再交互，不会去 take 一件没有的东西）。`story_runner.gd` `side_objectives()`：not 里的 burned_* 设上了就整条不显示（不显示成划掉）。
- 注意：现在森林里拿到这三件以后其实没有能烧东西的地方（唯一的 burn_pick 是玩具熊，在 c1_need_wood 之前），所以「提前烧」目前只是先备着；飞行一的 burn_held kind unrelated 会把背包里这些（含奖励）一起烧掉当动力。森林燃料条只是显示，做完三条能多 345。
- 验证：JSON 都能解析，目标 / 热点条件打印核对过。**没验证**：没装 Godot，没跑 `--story_check` 和游戏内。

### 2026-11-08 · Claude · 飞行一新流程：永燃之木无限 → 大陨石 → 货舱烧东西 → 燃料一直在烧、绿线补、烧光坠毁

- 作者：永燃之木无限能量，上飞机先开一段燃料不降；剧情杀被大陨石砸中、永燃之木掉落；转到货舱、放 bgm、必须选烧什么；之后燃料一直在烧，烧到底坠毁、丢失所有材料；碰到碎石一段时间漏得更快；燃料条上有绿色安全线，低于就要再加。作者定：坠毁 = 坏结局（回标题）；低于绿线按键进货舱；漏气维修保留；飞够一段距离结束。
- `data/story_flight1.json`：`start_flight1` 设 `flight1_wood_power`、燃料 500/500、安全线 150 → 新 `flight1_cruise`（debris_steer plan cruise：三波轻的 + 躲不开的大陨石，不扣燃料）→ 新 `flight1_meteor`（清 wood_power，燃料 40，两句旁白）→ 新 `flight1_hold`（配乐 space_choice、走到转化装置、burn_pick 加到 300、两句规则旁白）→ `flight1_debris`（drain 4/s、撞后 3 秒 +12/s、每个没修的漏点 +2/s、safe 150、refuel burn_pick 加到 300、crash → 新 `flight1_crash`：丢光能烧的、两句旁白、game_over）→ 漏气日记 → `flight1_seat` 直接接 `flight1_after_burn`。旧的 reroute / materials / fuel_choice 不再走（没删）。objectives 重写。
- `scripts/cockpit_debris.gd`：PLAN_CRUISE / meteor 波（缝也塞满，撞上大晃闪白、设 flight1_meteor）；燃料模式（drain / hit_drain / hit_sec / leak_drain / safe / refuel / crash）；低于绿线船下方闪提示，按 F 暂停碎石、弹 refuel 的 burn_pick（配乐换 space_choice，回来换回 flight_theme）；没东西可烧时提示改「已经没有能烧的了」；烧到 0 坠毁、返回 crash scene。cruise 没漏气时提示只写「↑ ↓ 躲开碎石」。测试参数 `--fuel_drain=n`。
- `scripts/fuel_bar.gd`：绿色安全线（StoryState 的 fuel_safe）、低于安全线填充闪玫瑰色且数字常显；`infinite`（flag flight1_wood_power）满格流光、写「无限」（像素字体的 ∞ 画歪了）。`level_forest.gd` 每帧把 safe / infinite 传过去。
- `scripts/story_runner.gd`：fuel 步骤 `safe`；新步骤 `game_over`（黑掉、停配乐、回标题，同倔强的灵魂那条路）；`take` 的 `all_burnable`；story_check 认 debris_steer 的 crash。`scripts/burn_pick.gd`：`until_at`。`scripts/chapter_flow.gd` SEED flags 加 c1_fuel_bar。
- `outputs/云 第一章完整剧本.docx` 第 08 节重写。
- 验证：四章 `--story_check` 0 错误；flight1 `--story_auto` 正常走完；`--fuel_drain=40` 触发一次补燃料后走完；`--fuel_drain=200` 两次补燃料后烧光坠毁、GAME_OVER；`--debris_full` 连拍看了无限 → 陨石 → 货舱 → 燃料下降 → 补燃料的画面；final `--story_auto` 照常。**没验证**：真人手感（drain 4/s、加到 300 是否合适）、坠毁后真的回到标题（自动玩不回标题）、货舱目前用的是驾驶舱里的转化装置（没有单独的货舱美术）。

### 2026-11-08 · Claude · 支线没触发就不在左下角显示

- 作者「只要没有和对应的物品交互，就应该显示的是，在蛇女的小屋里寻找可以燃烧的物品……每一条支线，如果没有触发，就不显示，如果触发了，就会在左下角显示这个任务线的下一步」。
- 原因：老松树 / 大嘴鸟 / 坡地雾三条支线的 objectives 只要 c1_side_open（一出门）就显示，没等玩家去碰。
- `data/forest_side_a.json`：`sa_pine` 场景开头设 `sa_pine_met`；「给老松树接一罐松脂」need 加 `sa_pine_met`。
- `data/forest_side_b.json`：`sb_toucan_hello` 开头设 `sb_toucan_met`、`sb_slope_go` 开头设 `sb_slope_met`；「陪大嘴鸟接果子」「去坡地的雾里看看」need 各加对应 flag。
- 收音机 / 路标 / 油灯三条本来就是拿到（sa_has_*）才显示，不动。
- 验证：两份 JSON 能解析；Python 按 `side_objectives()` 的规则模拟：屋里 / 出门后没碰任何东西只显示「在弥洛的小屋里寻找其他可以燃烧的物品」，碰了哪条才多出哪条。**没验证**：这台机器没装 Godot，没跑 `--story_check` 和游戏内截图。

### 2026-11-08 · Claude · 飞行一边躲边修二改：保持剖面视角整体缩小，三个漏点在窗 / 副驾驶座 / 工具箱；烧物品时放 space_choice

需求（作者）：「修飞机不对，保持这个视角，但是飞机缩小，窗外，副驾驶，和工具位置分别对应了三个要修的点」；「开始烧物品的时候应该触发 space choice 这个 bgm」。

- `scripts/cockpit_debris.gd`：有 `leaks` 时不再拉到船外远景、也不再画那个 7 像素小人——镜头把剖面整体缩到 0.6 倍、船挪到屏幕 78%（1.5 秒缓入缓出），舱里、晨、物件都在；晨本人 ←→ 走，走到漏点按住 E 修（播 repair，修时不走），↑↓ 照样躲。碎石碰撞按缩小后的船身轮廓（`_scale_hull`）。漏点：橙色裂口一闪一闪 + 往外扩的方框 + 白汽 + 嘶嘶声；站上去晨头顶出「E」和进度条。碎石提前量约 1.72 秒。
- `scripts/cockpit_room.gd`：加 `view_z / view_p / view_t`；`scripts/level_forest.gd` 的 `_update_camera` 在驾驶舱里照它缩放、平移镜头（船上下挪仍按屏幕像素）。
- `data/story_flight1.json`：leaks 改成 `{"t", "at"}`：6 秒 cockpit_window、15.5 秒 cockpit_copilot、24 秒 cockpit_toolbox。
- `scripts/story_runner.gd` `_burn_pick`：`burn: true`（放进转化装置烧）时开始放 space_choice、选完 2.5 秒淡出；第一关交玩具熊给弥洛那种不放。
- 验证：flight1 `--story_check`、`--story_auto`、`--debris_full`（三处都修好，43.8 秒）、final `--story_auto` 跑通无报错；截图看过缩小后的剖面和工具箱漏点。**没验证**：真人手感；0.6 倍非整数缩放下像素会有点不均匀（原来远景用的是重画的图，这里是直接缩）；BGM 只看了代码路径没听。

### 2026-11-08 · Claude · 飞行一删「这次不错」；小鹿临走送笔记本（150），烧了就不再写日记

- 作者「飞行，这次不错别刚夸完就出事这里删掉，把停顿也删掉……默认小鹿在临走之前给我们一个笔记本……如果烧掉就是150，如果不烧掉，那么就会默认往笔记本里面写一些东西，如果烧掉以后就不会写或者新增了」。
- `data/story_flight1.json` `start_flight1`：删掉那句 inner 和它前面的 relax + 1.5 秒 + 拍控制台，窗外换景后直接进碎石。
- `data/items.json` `journal`：改名「小鹿的笔记本」、新描述、keepsake_burn 120 → 150（id 不变，终章 burn_journal 等照旧）。
- `data/story_forest.json` `c1_bye_mom` / `c1_bye_child`：鹿加一句「这个本子给你……回来念给咱听」+ give journal。
- `scripts/story_runner.gd`：`_journal` 不再在背包没日记时凭空补一本；没有笔记本（森林里拿到之前、烧掉之后）就不写不新增。新 `_journal_writable()`，`journal_mark` / `journal_strike` 没本子就跳过（不警告、不弹提示）。结局里给的借来的纸（borrowed_paper）照旧能写。**副作用**：森林支线的三条日记（收音机 / 路标 / 油灯）在拿到笔记本之前，现在不会写。
- `scripts/chapter_flow.gd` SEED（直接进 flight1 的起点）owned 加 journal。
- `outputs/云 第一章完整剧本.docx`：07 加鹿送笔记本，08 删那句内心话，加笔记本规则说明，燃烧列表加笔记本，森林那三条日记删掉。
- 验证：四章 `--story_check` 0 错误；`--chapter=flight1 --story_auto` 跑通，最后背包里还有 journal。没测烧掉笔记本那条路（自动玩先烧玩具熊）。
- **发现但没改**：飞行一燃烧要的量 = 现有燃料 + 背包里无关材料合计 + 100（`fuel need_held`），可 11-07 以后 `flight1_materials` 不再先把无关材料自动烧掉，结果烧完玩具熊（100）还差，自动玩一路烧了熊、兔子皮毛、两块地板、告白信 5 件。待作者定是改回先自动烧无关材料，还是把需要的量改成「+100」。

### 2026-11-08 · Claude · 左上角支线去掉圆点；树屋支线写隐晦，点一件解锁一条

- 作者「支线任务……把列表形式的点去掉，同时这里要写的更隐晦一点，写，在蛇女的小屋里面寻找其他可以燃烧的物品，每点击一个，就解锁一个新的物品」。
- `level_forest.gd` `_update_objective()`：支线每行前面的「•  」去掉（含「陪兔子练舞」）。
- `data/forest_side_a.json`：objectives 最前面加「在弥洛的小屋里寻找其他可以燃烧的物品」（need c1_need_wood，not sa_house_searched；游戏里叫弥洛，没用「蛇女」）。sa_radio_get / sa_sign_get / sa_lamp_get 末尾加 count：三个 sa_has_* 都有就设 sa_house_searched（这条划掉）。三条送还支线（收音机 / 路标 / 油灯两条）去掉 need 里的 c1_side_open，在树屋里一拿到就立刻多出来，不用等出门。
- `outputs/云 第一章完整剧本.docx` 支线总说明补了一句。
- 验证：forest `--story_check` 0 错误；`--beat=c1_need_wood`、`--beat=sa_has_radio` 截图（拿收音机后多出「把收音机送回小吃棚」）。没测三件都拿完后划掉的样子。

### 2026-11-08 · Claude · 对话选项确认时的音效 + 特效

需求（作者）：每次选一个对话选项都要有音效和视觉触发；音效要空灵。
- 音效：新 `audio/sfx/choice_ring.wav`（`tools/choice_sfx.py` 生成，只用标准库）：两个玻璃钟音 A5→E6 往上一个五度、每个音一对微失谐正弦慢慢「呼吸」、垫一口高频气声、长尾混响。2.6 秒，峰值 -6 dBFS，播放 -9 dB。想换素材直接替换同名文件。
- 特效：`scripts/story_dialogue.gd` 的 `_menu_choose` 对 lines（对话选项）改走 `_line_chosen_fx`：选中那句字亮到发白再回落、底框染晨的紫红；一道细光从左扫到右；箭头处荡开两圈像素水波；9 粒 1 像素光点往上飘着闪着淡掉；没选的几句同时淡出。特效挂在对话界面上，菜单关掉后还飘约 0.6 秒。菜单关闭等待从 0.3 改 0.38 秒。道具选择条（items）不变，还是 tick + 闪一下。
- 验证：Godot 4.7.2 headless `--import` 导入成功、`--check-only` 通过；`--story_check`（forest）无问题；`--story_auto --qa_live --auto_to=c1_child` 跑过问背包选项，无 SCRIPT ERROR。没开窗口看实际画面、没听实际效果。

### 2026-11-08（三）· Claude · 兔子名字渐变（兔子 → 兔子首领王 → 普通兔子）、跳舞前晨自动站到兔子正对面、练舞时母兔跑来右边观战

需求（作者）：对话框一开始显示「兔子」，兔子说自己是首领时停住、名字渐变成「兔子首领王」，被打败以后变成「普通兔子」；不管哪一场跳舞，晨都自动走到正对兔子、固定距离的位置；第二次（练舞）母兔从右边跑过来，站在右边观战。

- 说话人改名：`story_runner.gd` 新 `speaker_def(who)`（speakers 的 `by_flag`，后面的优先），`_say` 和两处 murmur 用它；`say` 的 `"rename": flag`：先记旧名字再设 flag（快进也设上），把新名字交给 `dlg.say(..., rename_to)`。`story_dialogue.gd`：`_rename()` 等字打完 0.45 秒 → 旧名字 4 档淡出 → 换字、框重新量宽摆位 → 新名字带一点暖黄 4 档淡入再回原色；`_rename_lock` 期间确认键被吞掉，翻不到下一句；`_show_line` 把名字 alpha 复原。`docs/forest_chapter.md` 写了格式。
- `data/story_forest.json`：speakers.rabbit 加 `by_flag`（`c1_rabbit_chief` 兔子首领王 / `c1_rabbit_plain` 普通兔子）；「……我是首领。来比比舞步。」带 rename `c1_rabbit_chief`；比舞赢了以后加一句兔子「……我输了。永燃之木，归你了。」带 rename `c1_rabbit_plain`（补写，added）。`chapter_flow.gd` SEED 加这两个 flag。
- `scripts/rabbit_dance.gd`：开跳前晨总是走到兔子正对面 `FACE_DIST`（64）像素（站原来那一侧，墙外就换另一侧），两边互相转身；剧本的 `chen_at` 不再用（两处 mechanic 都去掉了；marker `c1_rabbit_chen` 留着没删）。
- 练舞 `c1_rabbit_practice`：开跳前母兔在右边远处（4700）出现、跑（speed 120）到兔子右边 `c1_rabbit_doe_near`（4545 → 4558），转向兔子观战；练完不再另走一次。
- **没在 Godot 里跑过**，待验证：名字渐变时框宽度变化的那一下跳不跳、渐变期间连按确认是否真的吞掉、自动玩（auto_delay）能否过去；英文名「Rabbit Chief King」作者看要不要改；晨走到 4452 时鹿（4495）会不会叠在中间；母兔 4558 在墙外 8 像素，靠近能不能出「母兔」提示。

### 2026-11-08（二）· Claude · 兔子舞步第二轮箭头改成「完整出现再淡没」；兔子原地等、靠近说话；母兔在右边远处、新图；练舞支线拿到永燃之木后才出现

需求（作者）：第二轮箭头应该还是完整呈现、但渐渐消失；鹿带去找兔子时兔子不该凭空出现，应该本来就在原地，靠近才能说话；「你看那边」往右看，母兔在远处；母兔按当前美术风格重画，蝴蝶结加得自然一点；练舞支线拿到永燃之木才出现。

- `scripts/rabbit_dance.gd`：fade 轮每个箭头都照常完整冒出来；跳到第 ceil(n/2) 下时前半段的箭头开始慢慢淡没（`STEP_SEC × 1.6`），之后每冒一个先完整亮 0.35 秒再 0.6 秒淡没，示范跳完一排都看不见。`_fade_row(hold, sec)`。
- `data/story_forest.json`：
  - 顶层 `residents` 加兔子（`c1_rabbit` 4516，朝左）：一直站在林子深处，鹿带过来时已经在那儿。`c1_rabbit` 去掉 show。
  - `c1_deer_go` 不再自动走到兔子面前、不再直接进 `c1_rabbit`，改成一句晨的独白；新 hotspot `c1_rabbit_meet`（at rabbit，need `c1_to_rabbit`、not `c1_got_wood`）靠近按键说话；新目标「跟兔子说说话」。
  - `c1_rabbit_challenge` 拿到永燃之木后直接 `c1_rabbit_leave`（设 `c1_rabbit_done`）；练舞要再跟兔子说话（原有 hotspot `c1_rabbit_practice` → `c1_rabbit_offer`）。「下次吧」改去新 scene `c1_rabbit_later`（一句台词，不再重跑 leave 把鹿挪回门口）；练完也不再 goto leave。
  - 「你看那边」：母兔先在右边远处淡入（`c1_rabbit_doe` 4375 → 4700，在 `wall_right` 4550 外面，晨走不过去），兔子和晨都转向右边，镜头过去再回来，再转回来。练完母兔走到兔子旁边（新 marker `c1_rabbit_doe_near` 4545），之后才能跟她说话。
- 母兔新图：`tools/rabbit_doe_art.py`（借 `tools/rabbit_art.py` 的画法，`py -3.14 tools/rabbit_doe_art.py [--preview 目录]`）→ `art/characters/rabbit_doe/rabbit_doe.png/json`。毛色比首领浅暖一点、耳朵往后收、一根睫毛，蝴蝶结画在像素里系在耳根上、跟着呼吸动，只有 idle。`npc_generic.gd` `art_for` / `has_own_doe_art()` 看到就用；`story_runner.gd` `_generic`、`ending_montage.gd` 有新图时不再贴 Polygon2D 蝴蝶结。
- **没在 Godot 里跑过**（本机没有 Godot），待验证：编辑器打开一次让 `rabbit_doe.png` 生成 .import（导出版需要）；`--story_check`；`--beat=c1_rabbit` 一带：兔子在原地、靠近出「兔子」提示、鹿站 4495 有没有挡；母兔 4700 那里画面有没有地面 / 背景（墙外），镜头能不能过去；练完母兔走到 4545 和兔子挤不挤；第二轮箭头淡没的节奏。

### 2026-11-08 · Claude · 燃料条平时只画条；左上角去掉「主线 / 支线」；对话中可开背包

- 作者「燃烧值进度条只有收到新的东西的时候，才会显示细节，不然的话只显示进度条本身，不显示数字和透明黑色背景。左上角支线和主线去掉这几个字。在对话当中应该随时可以点击背包或者按下 tab 打开背包，不会打断对话」。
- `scripts/fuel_bar.gd`：平时只画火苗 + 进度条；第一次出现 / 数变了 → 数字和半透明黑底淡入，滚完停 `DETAIL_HOLD`（2.5 秒）淡掉。读档 / 换章进来第一次 `set_fuel` 直接是现在的数，不从 0 滚。布局不变（数字淡掉的地方留空，条不跳）。
- `scripts/level_forest.gd`：目标行去掉「主线 · 」前缀，支线块去掉「支线」标题；没有主目标时的「主线已完成」改「目标已完成」。
- 对话中开背包：`_bag_ok_in_story()`（剧情在播、屏幕上是对话 / 旁白，不是道具选择条、特写、小游戏，右上角背包按钮在）时 Tab / B / I 或点背包按钮打开；开着时对话停在原地，关掉接着点。这次开的背包只看不「查看 / 使用」（不另起剧本打断对话）；关掉还原晨原来能不能走（鹿带路的自由走）。
- 验证：Godot 4.7.2 `--check-only` 两个脚本 0 错。**没在窗口里试过**：对话中按 Tab / 点背包、关掉后对话接着；燃料条数字淡入淡出的时机。

### 2026-11-08 · Claude · 闪回 1：三个障碍（Q / E / 左右交替）；触手碰到 = 关灯声 + 黑屏 3 秒

- 作者「触手回忆剧情杀的时候，应该是黑屏三秒钟才对的，触碰到的一瞬间，请你加上这个关灯音效，障碍物这里，应该有三个，一个是按 q，一个是按 e，还有一个是需要来回按左右才行」。
- `scripts/flashback.gd`：`OBSTACLES` 三个（路障 Q / 纸箱 E / 路障 ← → 交替，第三个复用路障图）；`_ob_key` 判按键对不对，`_set_qkeys` 按障碍建起身同款键帽（左右是两个并排）；`_lights_out`：关灯声、直接全黑、音乐雨心跳全掐、黑 3 秒。
- 新素材 `audio/sfx/light_off.mp3`（拷自 `story-jam/Assets/Sound Effects/open light.mp3`）。**还没导入**，需要用编辑器打开一次项目。
- **没在 Godot 里跑过**，待验证：F8「闪回 1」三个障碍的按键、左右交替手感、关灯那一下和 3 秒黑。

### 2026-11-08 · Claude · 鹿问背包选项调整；弥洛讲世界观 + 燃料条第一次出现

- 作者：妈妈线也要有「我好像有一个背包？」；孩子线「妈妈，你有没有见过一个背包？」改成「妈妈。我需要一个背包。」，后面对话按逻辑来。弥洛在「我是……晨」之后讲世界观（500 动力、手里能烧的不多、要一件至少 100 动力的东西），这里第一次出现燃烧值进度条，以后一直在屏幕上方；作者先说从这里开始大象的画和地图也能烧（150），随后改口「还是不让烧掉吧，就不用给燃烧值了」——最终保持不能烧。
- `data/story_forest.json`：`c1_ask_bag` 选项改（「我好像有一个背包？」去掉 need c1_child；孩子线新句跳新 scene `c1_ask_bag_need`，鹿用「咱 / 孩子」的口气回）；`c1_woke_b` 加弥洛三句（替换原「把小鹿送给你的玩具给我」），中间设 flag `c1_fuel_bar` + 等 1.6 秒`data/dev_names.json` 补名字。
- `data/items.json`：`elephant_drawing` 仍是 `no_burn`（只更新了 _note），不进任何燃烧选择。
- 新 `scripts/fuel_bar.gd`：上方正中的燃料条，画法照搬 `flight_hud.gd` 的进度条（暗轨道 + 琥珀填充 + 没满的玫瑰色虚点和刻度，满了亮绿），右边「有 / 要」。`level_forest.gd` 的 `_update_fuel_bar` / `fuel_bar_value`：flag 设上那一刻淡入、数字从 0 滚上去；森林 = 背包里所有能烧的动力合计 / 500，飞行段 = 燃料 / 需要；黑边放下时挪到黑边下面，对话框盖到就让开；显示时藏掉左上角旧的「火苗 x / y」。`chapter_flow.gd` 的 C1_FLAGS 带上 `c1_fuel_bar`（飞行一接着显示，河流篇 hud_fuel=false 不显示）。
- `scripts/burn_pick.gd`：名字后面标「· 动力 N」（玩家要能看出够不够 100），确认框只用名字。
- `outputs/云 第一章完整剧本.docx` 同步（02 鹿的选项、04 弥洛三句 + 燃料条（100 / 500））。
- 验证：forest / flight1 `--story_check` 0 错误；`--beat=c1_need_wood` 截图看燃料条（当时照片还算 150，显示 250 / 500；撤回后弥洛这里应是 100 / 500）；`--beat=c1_run --story_auto` 走到 burn_pick 截图（标「动力 100」）。**没验证**：撤回照片燃烧值后没重新截图；燃料条第一次出现的淡入手感、飞行一里燃料条和躲碎石画面会不会互相挡。

### 2026-11-08 · Codex · 起身、闪回和兔子舞步共用 QTE 音效

- 按作者要求，把试听的 `qte_rise.wav` 放进 `audio/sfx/`，以 PCM 导入。由 `scripts/qte_audio.gd` 共用切段，前五个音每段 0.4 秒，第六段从 2.0 秒起播放。
- `qte_fx.gd` 保留起身的五下蓄力和第六下释放。`flashback.gd` 的两处障碍各用七次蓄力映射五级，第八下释放。冲刺按追逐进度提高音级，逃脱时释放。`rabbit_dance.gd` 按对时叠加蓄力音，最后一步释放，原来的方向音和按错提示照常播放。
- Godot 验证了切点、连按取消淡出和释放自然结束。坠毁起身连拍、兔子舞步回归、闪回推障、追逐逃脱和被抓分支，以及四章 `--story_check` 通过。实机雨声和配乐下的音量待试听。

### 2026-11-08 · Claude · 闪回 1 推障碍的 QTE 改成起身同款：只有键帽、同样的特效和音效

- 作者「这里的 qte 不需要有文字描述，同理只显示按键即可，而且最好和游戏开头起身的 qte 一样视觉效果和音效」。
- `scripts/flashback.gd`：追照片那次的提示不再画「狂按 E 推开」，改成和 `getup_qte.gd` 一样的 E 键帽（下方正中 y 226、呼吸、按下压 1 像素亮边）；每个障碍建一份 `qte_fx.gd`（`_ob_fx_new`，CanvasLayer 56），按下 = 光圈 / 火星 / 蓄力光，推开 = 释放；被碰到 / 兜底推倒时收掉。声音沿用已接好的 `_qte_audio`。
- `scripts/qte_fx.gd`：加 `silent`（只画不播声音）和 `press(n, key, total)`。起身 QTE 调用方式不变。
- **没在 Godot 里跑过**，待验证：F8「闪回 1」撞上障碍看键帽和特效、推开那一下的释放。

### 2026-11-08 · Codex · 起身 QTE 音效试听

- 在仓库根目录的 `outputs/qte_rise.wav` 提供合成试听版。五级玻璃钟声按 C4、D4、E4、G4、A4 上行，第三下起渐加气流，第六下用 C 大和弦和上飘的光点声收尾。
- 检查 WAV 的六个起音、五级音高、结尾静音和文件格式。总长 3.500 秒，44.1 kHz / 16 bit 立体声，峰值 −3.50 dBFS。游戏内混音待试听。

### 2026-11-08 · Claude · 第一次闪回：看画后渐黑 → 睁眼进；玩家自己走；触手看不见就加速、进画面就放慢

- 作者「查看大象的画以后，应该有一个渐变过渡到黑的过程，然后黑屏直接睁眼效果到这个回忆杀区域……玩家自主操控……触手保持缓慢匀速前进，当玩家走的太远，就会加速，等到达玩家视角在放慢」。
- `scripts/paper_view.gd`：新参数 `"out": "black"`，收起时整屏 1.6 秒压到全黑，再铺剧本黑幕、拿掉这一层。
- `scripts/flashback.gd`：新参数 `"enter": "lids"`（`_intro_lids`，从黑里睁眼到街上）；第一次（`_photo`）晨交给玩家操控（障碍前收回、推开后还回）；新 `_photo_tentacles`（画面外加速到 360、进画面慢回 52 匀速）；追到照片前被碰到 = 卷住直接黑。
- `data/story_forest.json` `c1_drawing`：paper_view 加 `out: black`，flashback 加 `enter: lids`。`docs/闪回_实现说明.md` 第十二节。
- **没在 Godot 里跑过**（本机没有 Godot），待验证：`--check-only`、F8「闪回 1」实际看渐黑 / 睁眼 / 触手进出的节奏和难度。

### 2026-11-08 · Claude · 起身 QTE 按键特效 + 蓄力 / 释放音效接口

- 作者：要一个 QTE 按下的视觉特效 + 一个「逐渐升华，最后直接释放」的音效（音效由作者另外生成）。
- 新 `scripts/qte_fx.gd`（挂在关卡下自己的 CanvasLayer 39，键帽 40 的下面一层；释放后放完自己收掉，QTE 中途被跳过就跟着收）：
  - 第 1~5 下：键帽外弹一圈 1 像素切角方框往外扩、迸几颗 1 像素火星，越往后越远越亮越多；键帽外贴一圈「蓄力光」越攒越亮（最多 3 层）。
  - 第 6 下（释放）：蓄力光收掉，键帽外光圈扩开，晨脚下一圈像素椭圆贴地扩开，一把火星往上飘（混几颗晨的紫红），全屏极淡浅灰绿闪一下。
  - 全部硬边像素、不描边、最亮色 = 键帽亮边色，不用纯白。
  - 声音：`audio/sfx/qte_rise.wav|.ogg`（还没有，没文件静默）。前 5 下各播蓄力的第 i 级（每级 0.4s，末尾 60ms 淡出），第 6 下从 `RELEASE_AT`=2.0s 播到尾。
- `getup_qte.gd`：建 / 调 qte_fx（press / release / cancel 三处），+16 行。
- 音效需求写在 `docs/QTE_音效需求.md`（可以直接复制给 ChatGPT）。
- 验证：`--stage=crash --shots` 连拍看了整段 QTE（按键光圈、蓄力光、释放椭圆和火星都在位置上）；放了一个临时测试 wav 跑过一遍声音切段，无报错（测试 wav 已删）。**真实音效拿到后还没听过**。

### 2026-11-08 · Claude · 转圈只留启动加载，耳机 / 雨声黑屏不放

- 作者先要雨声黑屏也放转圈（假加载），又说耳机提示时不能有，最后「耳机过后还是不加了，影响听力」。最终：只有启动加载时有。
- 转圈抽成 `scripts/loading_spin.gd`（Sprite2D：`show_spin()` / `hide_spin()` 转完当前一圈再淡出），`main.gd` 用它；`level_forest.gd` 恢复原样，没有转圈。
- 没在 Godot 里跑过。

### 2026-11-08 · Claude · 启动加载：左下角妮芙转圈

- 作者「最开始黑屏加载这里，可以在左下角放一个鲸鱼妹妹转圈的动画，正好表示游戏正在加载」。
- `scripts/main.gd`：第一关从同步 `change_scene_to_file` 改成 `ResourceLoader.load_threaded_request` 后台加载；等的时候左下角（离边 8 像素）播 `niff_spin.png`（4 帧 100ms 循环，缩到 0.5 倍约 45 像素，nearest）。加载不到 0.15 秒就不出现；出现了就转完当前一圈再淡出（0.2 秒）才切场景。底色同 boot_splash。线程加载失败就退回原来的同步切换。
- 局限：关卡 `_ready` 在主线程跑，切过去那一瞬动画会停；引擎自己的启动画面（boot splash）之前那段不归游戏管。
- **没在 Godot 里跑过**（本机没有 Godot），待验证：启动看左下角转圈、0.5 倍缩小后像素是否难看（不行就改 `SPIN_SCALE` 为 1）、调试参数 `--stage=` 等照常生效。

### 2026-11-08 · Codex · 按新版剧情重新导出第一章剧本

- 更新 `outputs/云 第一章完整剧本.docx`，补入起身独白、问背包的新选项与回应、手动开包、追照片、燃烧教程、兔子舞步和飞行一的边躲边修与逐件燃烧。主线写到「第一章结束」，支线与可选互动随后单列。
- 对照现行 JSON 核查 139 个场景的中文内容，用 Word 检查 12 页排版。燃烧后的日记保留当前默认条目：玩具熊和全家福都没烧时，仍会写成烧了通勤卡。

### 2026-11-08 · Claude · 左上角主线 / 支线显示修正，去掉露出来的「\n」

- 作者「主线，支线显示有问题，还有换行符显示出来了」。`level_forest.gd` `_update_objective()`：
  - 支线那一块拼字时写成了 `"\\n"`（字面反斜杠 + n），屏幕上「支线」和每一条之间露出 `\n`，改成真正的换行。
  - 修好飞船以后原来把划掉的「修好飞船」塞进支线那一块（暗色小字，夹在主线和「支线」标题之间，像一条支线），同时主线那行写「主线已完成」，可后面还要「出发，回飞船」。现在：修好了、下一条主线还没出来时，主线那行写「主线 · 修好飞船（完成）」，支线那一块只放支线。
- 验证：本机没找到 Godot，没跑起来看，需要进游戏看一眼左上角。

### 2026-11-08 · Claude · 飞行一躲碎石：船更小、看得更远、更难；边躲边修漏气，不再停剧情

需求（作者）：起飞后的躲子弹场景，飞船再缩小、屏幕更早显示障碍物、增加难度；同时操作左右、维修和上下；维修不要任何剧情停顿。

- `scripts/cockpit_debris.gd`：远景船 0.65 → 0.55（最小那档图）、停在屏幕 80%（原 73%），碎石进画面到撞船头约 1.88 秒（原约 1.65）；碎石速度 FAR_SLOW 0.9 → 1.0；PLAN 9 波 → 11 波（换道间隔都是 2.8 秒）。终章 final_debris 也用同一套远景参数（跟着变小变快）。
- 新玩法 `leaks`（剧本参数）：远景小船上剖开一条船舱，里面一个 7 像素的小晨；漏点在船壳上闪橙光、往外喷白汽、嘶嘶响。←→ / A D 走过去，按住 E 约 0.7 秒修好（修的时候不能走，↑↓ 照样躲）。每个没修的漏点让船上下挪慢 35%（最慢 40%），不扣燃料、不会输；波次排完了还有漏就继续来零星单块，修完才收尾，超时兜底算修好。
- 顺手修了：「7 秒后提示淡出」原来每帧都调，后面重新亮的提示（含终章黑窗那句）会被立刻掐掉；改成只淡一次。
- `data/story_flight1.json`：flight1_debris 加 `leaks`（6 / 15.5 / 24 秒各漏一处），躲完直接进新 scene `flight1_leak_done`（设 flight1_leak / flight1_leak_fixed、漏点 prop 设 fixed、日记一条 toast）→ flight1_seat。原来的 flight1_leak（停下来找漏点）/ flight1_leak_fix（走过去修 + 独白）不再播，没删。
- 验证：`--story_check`（flight1）通过；`--story_auto`（flight1、final）跑通无报错；`--debris_full` 自动玩 3 处漏全修、44 秒；截了两张远景图看过。**没验证**：真人手感（难度、小晨是否看得清、E 键手感）。

### 2026-11-08 · Claude · 鹿对话：问背包加第二个选项「我好像有一个背包？」

需求（作者）：选了「我也不知道我是谁」以后，问背包那里除了「妈妈，你有没有见过一个背包？」再加一个「我好像有一个背包？」。
改动：`data/story_forest.json` 的 `c1_ask_bag` 选项加一条（need c1_child，跳 `c1_ask_bag_have`，鹿回「背包？……啊，我刚刚在那边看到了一个！ / 说不定就是你的……」）；原来选项后面「设 c1_asked_bag、鹿带路」那段拆成 `c1_ask_bag_go`，两边都 goto 过去。`data/dev_names.json` 补了两个新场景名。未进游戏实测。

### 2026-11-08 · Claude · 兔子舞步：箭头一轮比一轮少、加第四轮、同一步错多了箭头重新出现

需求（作者）：第一轮有箭头指引；第二轮跳到一半以后箭头渐变隐藏，要自己看兔子；第三轮纯隐藏；加一个第四轮也是纯隐藏、更长一点。辅助：同一个步骤失败超过两次，指引箭头重新浮现。

- `scripts/rabbit_dance.gd`：
  - 默认 `SEQS` 加第四轮（6 步：↓ → ↑ ← ↓ ↑）。森林 `c1_rabbit_challenge` 用默认，所以正式比赛变四轮；`c1_rabbit_practice` 自带三轮 seqs，没加轮，但同样按 show / fade / hidden 给箭头。
  - `round_mode(step, i)`：第 1 轮 show、第 2 轮 fade、之后 hidden；剧本可写 `"hide": [...]` 逐轮指定（`--story_check` 会检查）。fade：兔子跳到第 ceil(n/2) 下时，已给出的箭头 4 档淡没，后面的不再给。没给出的箭头透明占位，玩家按对时 `_reveal` 冒出来（亮）。
  - 辅助：`act()` 按错时记 `s.fails["轮:步"]`；`assisted(s)` = 这一轮有哪一步错了超过 `ASSIST_AFTER`(2) 次，即同一步第三次错后，这一轮接下来的示范和跟跳都按 show 给箭头（打印 `RABBIT_ASSIST`）。换一轮重新算。
  - `finished()` 也看 `done`：以前存的三轮已跳完（round = 3, done）不会回来跳第四轮。
  - `_clear_row` 淡出时乘原 alpha，透明占位的箭头不会闪一下。
- `scripts/rabbit_dance_demo.gd`：demo 改成 `retry: true`（不再错三次自动过，能试到辅助），状态栏 `x / 4`。
- `scripts/rabbit_dance_test.gd`：加规则测试（四轮、show/fade/hidden、hide 覆盖、同一步错三次才辅助、不同步不累加、换轮重算、旧 done 存档）；run 测试补第四轮的键。
- 文档：`docs/forest_chapter.md`、`docs/剧情改动/第一关新版_实现规格.md` 对应描述。
- **没在 Godot 里跑过**（本机没有 Godot），待验证：`rabbit_dance_test.gd` headless 全 PASS；开 demo（F12 → R）实际看第二轮淡没的时机、第三轮按对时箭头冒出来、同一步错三次后箭头回来；`--story_check`。

### 2026-11-08 · Claude · 片头 CG 跑完直接到背包前（删掉飞船到背包那段真实距离）

需求（作者）：从飞船到背包有一段距离，credit 本身已经是额外的循环，不需要这段真实距离；不能影响背景衔接。

- `scripts/c1_loop.gd`：新增 `_cash_loop()`，CG 卷完（`_tick_cg` 里 `_cg_left == 0`）时把跑步机虚拟位移 d 里的一圈（960）兑换成真实位移：晨、镜头（含 `_cam_override`）x += 960、`reset_smoothing`，所有视差层 `scroll_offset += 960 × scroll_scale`，d -= 960。Main / 地面都是 960 一圈，这一帧画面不变（和 `_place_world` 挪 `CRASH_DX` 同一招）。CG 至少卷 2880，所以每次都会兑换；自动玩也走跑步机 CG，一样生效。
- `scripts/run_credits.gd`：`Roll.shift_world(dx)`，还在屏幕上、钉在世界里的名字（非 sky）跟着挪，屏幕上不动。
- `data/story_forest.json`：跑完晨落在 520～584（看从跑步机还是从左边直接冲进 `c1_run`），背包一组锚点整体 +120：`c1_bag` 520→640、`c1_bag_wall` 470→590、`c1_bag_view` 440→560、`c1_deer_bag` 600→720，跑完再走约 40～100 像素就捡到。
- 没处理：`--beat` 直接跳过 `c1_run` 的那些节拍，晨的位置照旧（要多走这段）；跳的那一帧背包、鹿会直接出现在画面里（镜头 1.25 倍时）。
- **没在 Godot 里跑过**（本机没有 Godot），待验证：`--beat=c1_follow` 按 Shift 跑完 CG，看跳那一帧远景 / 前景 / 地面 / 名字有没有动，`C1LOOP cash` 打出来的 x；再往回走到飞船看远景是否连续。

### 2026-11-08 · Claude · 背包：描述挪到格子下面

需求（作者）：描述直接放在背包格子下面（格子只剩三行，下面空着），漂浮的道具往下平移一点。

- `level_forest.gd`：名字 + 燃烧值一行在 `BAG_NAME_Y` = 118（格子下面），描述从 136 到背包底（70 高），两者都从 x = 10 开始、332 宽（整个背包那么宽）。物品飘的中心 `BAG_FLOAT_AT` (236, 57) → (236, 68)，即格子右边那一整块的正中。「查看 / 使用」按钮位置不变。
- `qa_text.gd`：背包描述宽度检查 212 → 332，日记一条 200 → 320。
- 没在 Godot 里跑过，待验证：中英文截图看描述换行、四行左右能不能滚到底，飘的东西会不会碰到「查看」按钮。

### 2026-11-08 · Claude · 背包：拖动换位置

需求（作者）：物品可以随意切换位置，长按即可拖动。后来改：不要长按，直接拖动就可以。

- 改版：不再等 0.3 秒，按下以后鼠标挪动超过 `BAG_DRAG_PX`（3 像素）就拿起来；只点不动 = 照常选中。下面一条里的 `BAG_HOLD` 已删。

- `level_forest.gd`：格子 `gui_input` → `_bag_slot_input`；在有东西的格子上按住左键 `BAG_HOLD`（0.3 秒）拿起来，图标跟着鼠标（`_bag_ghost`），原格子图标变淡，鼠标下面那格提亮；松开在别的有东西的格子上 = 两件互换，在空格上 = 挪到最后一件后面（`Inventory.owned` 一直从第一格往后排、不留空），不在格子上 = 放回去。换的是 `Inventory.owned` 的顺序本身，存档 / 下次打开都保持。背包关掉时正在拖的取消。只做了鼠标，键盘没有拖动。
- 没在 Godot 里跑过，待验证：拖起来的灵敏度、拖到空格、拖到格子外、拖动中按 Tab 关背包。

### 2026-11-08 · Claude · 背包改版：三行格子、物品飘着展示、去掉分类后缀

需求（作者）：背包格子只留前三行；物品描述里的后缀（纪念品、任务道具这些）全删；物品展示从静态改成选烧什么时那套动态模板；去掉物品展示的边框，描述从格子第三行的高度开始，合理用满背包空间。

- `level_forest.gd`：`BAG_SLOTS` 24 → 12（4 × 3）。右上那块带框的静态大图（Panel + TextureRect）换成没有框的 `Sprite2D`，中心 `BAG_FLOAT_AT`（格子前两行那么高），每帧 `_bag_float_tick` 用 `burn_pick.float_pose` 翻着飘，换一件时从下面浮上来；放大整数倍，最多 4 倍、高 ≤ 44、宽 ≤ 80（不碰「查看 / 使用」按钮）。名字和燃烧值放在 `BAG_NAME_Y` = 88（格子第三行），描述从 106 一直到背包底（`DESC_H` 88 → 100，上下滚动小三角跟着挪）。删掉名字旁边的【纪念品】/【任务】和稀有度那一行；`_burn_line` 只给能烧的材料写「燃烧值 +n」，纪念品「烧掉可得」、「任务物品」、「私人物品，不能烧」都不写。
- `burn_pick.gd`：飘的动法抽成 `static func float_pose(...)`，选烧什么和背包共用（动法本身没变）。
- 风险：同时拿着超过 12 样东西时，第 13 样以后在背包里看不到（没做翻页）。
- 没在 Godot 里跑过（本机没有 Godot），待验证：`--beat=c1_need_wood --open_bag=elephant_drawing` 中英文截图，看飘的范围、名字行、描述到底部有没有出界，日记长文能不能滚到最后。

### 2026-11-08 · Claude · 捡到背包不再自动打开，第一次打开也能关

需求（作者）：最开始见到背包以后，应该指引玩家手动打开背包（一句话提示用 Tab 打开；用右上角打开也行），取消第一次打开没有关闭按钮的设定。

- `bag_pickup.gd`：背包特写收起后不再设 `_bag_after_story`，不自动打开背包；剧本 `c1_got_bag` 原有的 `key_prompt`「按 Tab 打开背包」（until photo）接着出，直到看完大象画。
- `level_forest.gd`：撤掉 11-07（七）那条的关闭叉部分——`_bag_refresh()` 里关闭叉一直显示；`_close_panels()` / `_open_settings()` 不再因为 `_first_photo_pending()` 拦着关背包、开设置。燃烧值那一行（火焰 + 数字）看照片之前照旧藏着；大象画的高亮、看照片前不能用别的物品照旧。
- 没在 Godot 里跑过，待验证。

### 2026-11-08 · Claude · 只有一个对话选项时放屏幕正中

- 作者「孩子，把你的背包给我这一句话，也要显示在屏幕的中央，即使只有一个选择，不然不知道要点击」。
- `scripts/story_dialogue.gd` `_open_menu`（lines 分支）：选项只有一个时不走 `_menu_dodge`，框收窄到字宽（最多 308）、放在屏幕正中（240, 135）。两个以上的选项照旧。影响所有过滤后只剩一个选项的 `choice`（目前就是第一关问背包两条线）。
- 验证：Godot `--check-only` 通过；**还没在游戏里看过**（正中可能压到人，要看一眼）。

### 2026-11-08 · Claude · 对话选项：箭头不再挤动文字

- 作者「选择的时候，右箭头会出现，但是不会影响选项本身的文字排版」。
- `scripts/story_dialogue.gd`（`_open_menu` 的 lines 分支、`_menu_style`、`_menu_rect`）：选项文字固定缩进一个「▸ 」宽，箭头改成每行一个单独的小 label 放在缩进里，选中才显示；文字本身不再带箭头/空格前缀，换选项时不跳、折行也对齐。点击范围把缩进那格也算进去，和原来一样大。
- 验证：未在游戏里看过，需要进一个对话选项确认箭头位置。

### 2026-11-08 · Claude · 说话音效（鹿 / 蛇女 / 兔子首领）

- 作者「开始加说话音效，22小鹿，23蛇女，25老鼠首领」（「老鼠首领」作者确认 = 森林里自称首领的兔子 `rabbit`）。
- 新素材 `audio/sfx/voice/voice_deer.ogg` / `voice_miluo.ogg` / `voice_rabbit.ogg`（dmochas dialogue bleeps pack 的 bleep022 / 023 / 025，用 ogg 版；wav 版是 32 位浮点）。
- `scripts/story_dialogue.gd`：`say` / `murmur` 多一个 `voice` 参数（说话人 id），`VOICES` 表里有的人打字时每 2 个字哔一声（标点空格不响、音高 ±6%、-8 dB、SFX 总线），补全 / 关框立刻停。`story_runner.gd`、`river_salvage.gd` 调用处把 `who` 传进去。以后加人只要往 `VOICES` 里加一行。
- 验证：`--import`、`--story_check` 无报错。**还没实际听过**音量和间隔，需要在游戏里听一下再调 `VOICE_DB` / `VOICE_EVERY`。

### 2026-11-08 · Codex · 去掉主标题阴影

- 按作者要求，在 `scripts/level_forest.gd` 移除标题画面主标题的文字阴影。
- Godot `--story_check` 完成，已用 `--stage=title` 截图确认中英文主标题均无阴影。

### 2026-11-08 · Claude · 测试用快进 / 跳过快捷键，F12 传送页加大节点跳关

- **快捷键**（`scripts/dev_panel.gd`，只在 debug 构建，面板开不开都管用）：按住 **Ctrl** = 全局 ×6 快进（`Engine.time_scale`，对话每句立刻自动推进，选项不替你选）；**F9** = 快进开 / 关（跨跳关保留，左上角「▶▶ 快进」，开关页也有）；**F10** = 跳过这一段（结局回看 / 驾驶舱小游戏走现有的 `dev_skip`）。之前只有开关页「跳过对话」，没有快捷键；坠毁开场、标题仍按作者规矩对玩家不可跳，快进只是让它们播得快。
- **F12 传送页**：地图下面按章列出「跳到大节点」按钮（读 `data/dev_names.json` 的 `beats`，节拍页删掉以后这些只给自测用），加「跳到下一章开头」。`beats` 新增**终章**：开场 / 选去处 / 结局一落地 / 坐下看大象 / 尾声 / 尾声城市列车 / 结局三 / 回母星；分支的标 `"end": true`，自测接着玩到章节结尾而不是下一个大节点。
- 验证（Godot 4.7.2 headless，本机在 `%LOCALAPPDATA%\Temp	he-cloud-godot-472\`）：`--check-only` 0 错；`--dev_test` 新加的「F9 开 / 关」检查 ok（真的按键进 viewport，time_scale、对话 auto_delay、左上角字都对，F10 空按不报错），开关 7 个、大节点 40 个。终章 7 个大节点逐个 `--chapter=final --beat=… --story_auto`：都跳到了、都自动玩到 final_done、0 脚本错误（原来想用的「找地方种种子」`final_e1_seed_todo` 跳不到——快进时种子被烧掉了——换成 `final_e1_met`）。**已有问题（不是这次改的，干净的 HEAD 一样）**：`--dev_test` 跳到森林第 2 个大节点 `c1_follow` 以后自动玩不跟鹿，触发倔强结局（`C1LOOP ending → STUBBORN_END`）退出，后面的大节点都没测到。Ctrl 按住、真窗口里的手感没人试过。

### 2026-11-07（十一）· Claude（elephant-sister 会话）· 大象背面航线图第二版、小兔子 / 小水母原尺寸图

- **大象背面的航线图**（作者 11-06：「不应该是简笔画，而是不同星球的地图」；11-07：「小镇我以为属于云层星」「芦苇地为什么不叫 xx 星」）：新工具 `tools/paper_map_art.py` 出 `art/forest_story/paper_map.png`。现在是五颗星：母星 → 森林星 → 绕开碎石带 → 河流星 → 云层星（云海上有大象，云里立着小镇的尖塔），云层星底下分三路：小镇 / 芦苇星 / 回母星。「芦苇星」是占位名，等作者定。`scripts/paper_view.gd` 的 `BACK_LABELS` 翻到背面时叠地名（中英文）。驾驶舱小航图跟着改（`tools/cockpit_final_art.py` 的 `travel_map()` → `art/cockpit/cockpit_map.png`）。
- **小兔子、小水母**（终章会话要的，结局回看用）：新工具 `tools/rabbit_kit_art.py`、`tools/jellyfish_small_art.py`，出 `art/characters/rabbit_kit/` 和 `art/characters/jellyfish_small/`。引擎看到这两个文件夹就不再缩放兔子、大水母，第一章兔子家的三只小兔子也一起换了。
- 验证：headless `--story_check` 森林、终章 0 错误，预览都是 Python 合成的。**没开窗口**：翻面时地名的位置、蒙太奇里小水母的高低、第一章小兔子站位，留到「去测试」。明细见 `docs/夜测_11-05_汇总.md`。

### 2026-11-07（十）· Claude（终章会话）· 结局回看蒙太奇

- 作者要「回看过往」：三个去处的结局最后、全剧终之前，先母星列车，再每个支线 NPC 一镜（兔子、大嘴鸟、鹿、弥洛的小屋、阿汀、鼠妈、水母、妮芙），每镜约 3.4 秒，按 flag 分「做了任务 / 没做」两版，不可跳过，约 41 秒。
- 新 `scripts/ending_montage.gd`；`story_runner.gd` 加 `montage` 步骤（`_montage`、`montage_ui`）；`level_forest.gd` 回看时 Esc、齿轮不开设置；`npc_generic.gd` 加 `art_for`（小兔子有自己的图就不缩）；`data/story_final.json` 两处 `end_chapter` 前加 `{"do": "montage"}`。
- 验证：headless story_check 0 错；三个去处加全支线 seed 各自动玩到制作人员，AUDIO_QA、QA_LIVE 全 0。明细见 `docs/第三章计划.md` 〇·二、`docs/夜测_11-05_汇总.md` 末尾。没开窗口，画面还没人看过。

### 2026-11-07（九）· Claude（ch1-story 会话）· 森林删通讯器、晨的独白减量

- **删通讯器**（作者：「手机没有用，删掉」）：`data/story_forest.json` 的 `luggage` 去掉物品 `communicator` 和 `phone_open`；`revisit` 删号码 / 发送失败那几句；`farewell` 删存联系人一整段（连同鹿进屋那句）。都在旧流程场景里，新第一章原本就播不到。森林没有 `phone_*` / `msg_*` flag。
- **晨的独白要少、留下的打在屏幕上**（作者全局规则）：只动新第一章。`forest_side_a.json` 删车票两句，四个「做完再点」的点标 `retired`；三处「看一眼」和残骸那句改 `inner` fade。`story_forest.json` 删 4 条和左上角目标重复的闲置提示，顶层加 `"hints_inner": true`。`scripts/story_runner.gd` 的 `_update_nudge` 看到它就把晨的提示交给 `_inner`，不出对话框；别的章想一样，在剧本顶层加这一行。
- 验证（headless）：`--story_check` 0 错；妈妈线、孩子线 `--story_auto --qa_live` 全过。闲置提示走屏幕字那条路没跑到。详见 `docs/夜测_11-05_汇总.md` 末尾两条。

### 2026-11-07（八）· Claude（Cowork）· 第一次闪回（追照片）重做：障碍狂按 E、照片进背包、触手一碰就黑

需求（作者）：刚进闪回不出触手，只有场景；跑一段以后照片从右边飘过来，玩家一直追它；中间碰到障碍要按很多次 E 才能过，障碍按现有像素风格画；追到照片后物品加进背包（复用右上角背包那个飞进去的动画），出「获得地图」；然后触手从左边快速靠近，碰到晨的一瞬间直接黑屏。

- `scripts/flashback.gd`（只改第一次，`_photo = id == 1`；二～四次没动）：
  - 开头不涌触手、不回头看、没有冲刺；晨自己往右跑。`PHOTO_AT` 2.2 秒后照片从屏幕右边外慢慢飘进来，在她前面飘。
  - 两个障碍（`OBSTACLES`：1150 施工路障、2450 一摞三只纸箱）。撞上就停、出「狂按 E 推开」（提示挪到 y 122，在头顶，不压人）；按 `OB_NEED` = 8 下推开：每下障碍晃一下、往前挪一格、她往前顶一下、扬尘；最后一下路障拍倒在地（换倒地图）往前滑，纸箱散开。鼠标 / 触屏点按也算。`OB_GUARD` 40 秒不按会自己倒（只防软锁）。
  - 过了最后一个障碍 `CATCH_AFTER` 1.6 秒，照片落回她手里，飞进右上角背包（和剧本 `give` 同一条轨迹：先跳一下再划弧，背包弹一下、`level.bag_bump()` 的「嗒」），出「获得：地图」。
  - 停 0.5 秒，晨回头，触手从画面左边缘外 1 秒内越来越快地扑过来（心跳、紧张音乐拉满），碰到她直接全黑（不淡），之后接原来的剧本（看照片、翻到地图……）。
  - 删了原来的空格跳栏（`_barriers` / `_vault`）。新增测试参数 `--fb_shots=目录`、`--fb_shot_every=秒`（闪回里定时存截图）。
- `tools/flashback_obstacle_art.py`（新）→ `art/flashback/obstacle_barrier.png`、`obstacle_barrier_down.png`、`obstacle_box_a/b/c.png`：照 `city_art.py` / `flashback_train_art.py` 的城市灰，1 倍像素、无描边，暖色只给警示灯和纸箱。
- `data/story_forest.json`：`c1_drawing` 的 flashback 加 `"got": {"zh": "地图", "en": "Map"}`（「获得：%s」用的名字；没写 got 的旧 `went_wrong_first` 只是照片淡掉，不飞背包）。
- 验证：云端 Godot 4.7，`--beat=c1_got_bag --fb_dev=1 --story_auto --fb_full` 按真实时长跑并每 0.2 秒截图：照片 2.2 秒飘进来，路障 / 纸箱各 8 下推开，照片进背包、出「获得：地图」，触手扑过来碰到即黑，接着 `paper_view` → `c1_woke`，0 个脚本报错，全程约 22 秒。快速自动玩（×0.4）也通。森林 `--story_check` 0 错误。手感（8 下够不够、障碍大小）和声音没人实机试过；推的时候城市前景的黑车偶尔会挡住提示约 1 秒（作者之前说前景不动，没改）。

### 2026-11-07（九）· Claude（Code）· 飞船烧东西改成自己挑：背包里所有能烧的，选一个烧一个（burn_pick 加 kind / burn / repeat / until_fuel / after）

需求（作者）：喜欢燃烧教程里熊翻着飘的画面；飞船选烧什么时不要自动烧，也不是二选一——背包里所有能烧的都能选，选一个烧一个（多选多），物品框在最下方，中间是悬空翻转的那一件。
- `scripts/burn_pick.gd` 新增可选字段：`kind`（只列这一类 fuel_kind）、`burn`（确认后真的从背包烧掉，走 `_burn_held`：加燃料、设 burned_*、提示）、`repeat`（一件接一件挑）、`until_fuel`（燃料够了就停；烧光了也停）、`after`（{物品: scene}，烧完播那段台词，只放台词不要 goto）。每轮前 `_reset()` 清界面。不写这些字段的旧用法（第一关熊）不变。
- `story_runner.gd`：`_burn_held` 认 `no_closeup`（burn_pick 自带烧的动画，不叠特写）。
- `data/story_flight1.json`：`flight1_materials` 不再自动烧无关物品，只走到转化装置、设 fuel_short / flight1_fuel_low，然后 goto `flight1_fuel_choice`；`flight1_fuel_choice` = 旁白「放进转化装置的东西，无法取回。」→ `burn_pick {burn, repeat, until_fuel, after}`（背包里所有能烧的）→ flag `flight1_burned` → `flight1_after_burn`。小熊「对不起。」/ 全家福「……我会记起来的。」改放进 `flight1_after_deer_bear` / `flight1_after_family_photo`。旧的 `burn_deer_bear` / `burn_family_photo` / `burn_blue_stone` 等分支留在文件里，不再走到。
- 没跑：本机没有 godot，只确认 JSON 能解析。**没实机试**，请跑 `--story_check` 和飞行段。注意：燃料需求（`need_held`）按「现有 + 全部无关物品 + 100」算，所以不烧够无关物品、又没烧大件私人物品时燃料不会到，会一直挑到烧光。

### 2026-11-07（八）· Claude（Cowork）· 第一次闪回（追照片）重做：障碍狂按 E、照片进背包、触手一碰就黑

需求（作者）：刚进闪回不出触手，只有场景；跑一段以后照片从右边飘过来，玩家一直追它；中间碰到障碍要按很多次 E 才能过，障碍按现有像素风格画；追到照片后物品加进背包（复用右上角背包那个飞进去的动画），出「获得地图」；然后触手从左边快速靠近，碰到晨的一瞬间直接黑屏。

- `scripts/flashback.gd`（只改第一次，`_photo = id == 1`；二～四次没动）：
  - 开头不涌触手、不回头看、没有冲刺；晨自己往右跑。`PHOTO_AT` 2.2 秒后照片从屏幕右边外慢慢飘进来，在她前面飘。
  - 两个障碍（`OBSTACLES`：1150 施工路障、2450 一摞三只纸箱）。撞上就停、出「狂按 E 推开」（提示挪到 y 122，在头顶，不压人）；按 `OB_NEED` = 8 下推开：每下障碍晃一下、往前挪一格、她往前顶一下、扬尘；最后一下路障拍倒在地（换倒地图）往前滑，纸箱散开。鼠标 / 触屏点按也算。`OB_GUARD` 40 秒不按会自己倒（只防软锁）。
  - 过了最后一个障碍 `CATCH_AFTER` 1.6 秒，照片落回她手里，飞进右上角背包（和剧本 `give` 同一条轨迹：先跳一下再划弧，背包弹一下、`level.bag_bump()` 的「嗒」），出「获得：地图」。
  - 停 0.5 秒，晨回头，触手从画面左边缘外 1 秒内越来越快地扑过来（心跳、紧张音乐拉满），碰到她直接全黑（不淡），之后接原来的剧本（看照片、翻到地图……）。
  - 删了原来的空格跳栏（`_barriers` / `_vault`）。新增测试参数 `--fb_shots=目录`、`--fb_shot_every=秒`（闪回里定时存截图）。
- `tools/flashback_obstacle_art.py`（新）→ `art/flashback/obstacle_barrier.png`、`obstacle_barrier_down.png`、`obstacle_box_a/b/c.png`：照 `city_art.py` / `flashback_train_art.py` 的城市灰，1 倍像素、无描边，暖色只给警示灯和纸箱。
- `data/story_forest.json`：`c1_drawing` 的 flashback 加 `"got": {"zh": "地图", "en": "Map"}`（「获得：%s」用的名字；没写 got 的旧 `went_wrong_first` 只是照片淡掉，不飞背包）。
- 验证：云端 Godot 4.7，`--beat=c1_got_bag --fb_dev=1 --story_auto --fb_full` 按真实时长跑并每 0.2 秒截图：照片 2.2 秒飘进来，路障 / 纸箱各 8 下推开，照片进背包、出「获得：地图」，触手扑过来碰到即黑，接着 `paper_view` → `c1_woke`，0 个脚本报错，全程约 22 秒。快速自动玩（×0.4）也通。森林 `--story_check` 0 错误。手感（8 下够不够、障碍大小）和声音没人实机试过；推的时候城市前景的黑车偶尔会挡住提示约 1 秒（作者之前说前景不动，没改）。

### 2026-11-07（九）· Claude（Code）· 飞船烧东西改成自己挑（burn_pick 加 kind / burn / repeat）

需求（作者）：喜欢燃烧教程里熊翻着飘的画面；飞船选烧什么时不要自动烧，让玩家选，物品框在最下方，中间是悬空翻转的那一件。
- `scripts/burn_pick.gd`：新增可选字段 `"kind"`（只列 `fuel_kind` 是这一类的，如 unrelated）、`"burn": true`（确认后真的从背包烧掉：走 `_burn_held`，加燃料 + 提示）、`"repeat": true`（一件接一件挑，直到没有可烧的）。每一轮前 `_reset()` 清界面。没写这些字段的旧用法（第一关熊）行为不变。
- `story_runner.gd`：`_burn_held` 认 `no_closeup`（burn_pick 自己已经有烧的动画，不再叠特写）。
- `data/story_flight1.json`：`flight1_materials` 里原来自动烧的 `burn_held {kind: unrelated}` 换成 `burn_pick {kind: unrelated, burn, repeat}`，去掉紧跟着的 `converter_burn` 音效（burn_pick 自带火声）。
- 没有跑：本机没有 godot，JSON 解析通过，**没实机试**；请跑一次 `--story_check` 和飞行段。`flight1_fuel_choice`（deer_bear / family_photo 二选一）仍是原来的托板界面，没动。

### 2026-11-07（八）· Claude（Cowork）· 选烧什么的新模板 burn_pick（第一次：弥洛要玩具熊）

需求（作者）：第一次教程选烧什么要有个好模板——用闪回里旋转的地图（照片）那套动法，让小熊在天上飘；上方写「选择你要烧掉的物品」，最下方一排能烧的物品，选的时候显示简介；回车弹出「是否要烧毁 xx」，选了就触发动画、交给蛇女。不是「给 / 不给」两个选项。

- 新文件 `scripts/burn_pick.gd`（剧本步骤 `burn_pick`，用法写在文件头）：整屏压暗；上方标题；中间选中的那件放大 4 倍，按 `flashback.gd` 里照片的动法翻着飘（前后晃、上下两层正弦、rotation、scale.x 窄宽翻面），换一件时从下面浮上来；下面名字 + 简介（物品 desc）；最下方一排格子（驾驶舱托板同样式），←/→ 或鼠标挑。回车 / E / 空格 / 单击 → 确认框「要烧掉「名字」吗？」烧掉 / 再想想（Esc = 再想想）。确认后：写了 `to` 就沿弧线飞到那个人跟前、缩回原大小淡掉；没写 `to` 就就地烧掉（变暖、散火星）。然后 goto `scenes[物品]`，没有就 `then`。能烧 = `keepsake_burn` / `burn` > 0（大象照片、地图这些不出现）。
- `story_runner.gd`：`STEPS` 加 `burn_pick`、`_burn_pick()`；跳节拍 / 可达性 / `--story_check`（`_would_progress`、`_reach`、`_falls_through`、房间推断、`_would_progress_flags`、validate）都认它的 `scenes` + `then`。
- `data/story_forest.json`：`c1_woke_b` 的「给你 / 不给」换成 `{"do": "burn_pick", "id": "c1_bear_pick", "to": "miluo", "scenes": {"deer_bear": "c1_bear_give"}, "then": "c1_bear_b"}`；前面两句旁白照旧；`c1_bear_keep` 删了（`dev_names.json` 里那条也删了）。`c1_bear_give` 没动（take → 弥洛「开个玩笑的」→ 还回来）。
- 验证（云端 Godot 4.7，电脑上最新的改动覆盖 git HEAD）：四章 `--story_check` 0 错误；`--beat=c1_got_bag --story_auto` 中英文截图：标题、熊翻着飘、简介、确认框、熊飞到弥洛手边、`c1_bear_give` → `c1_bear_b` 正常；临时多塞 4 件东西测了一排 5 格、换选、「再想想」回去再确认（`--story_auto=full --burn_pick_back`，测完删掉了）；`--story_auto --qa_live --main_only` 森林跑完，softlock 0，overlap 4 条都是原来就有的（片头名字、成就条）。**没实机手感**：熊翻面时有一瞬间很窄（和照片同样的 0.2 倍），觉得怪可以把 `_process` 里 0.6 + 0.4·cos 调小幅度。

### 2026-11-07 · Codex · 导出第一章完整剧本

- 生成 `outputs/云 第一章完整剧本.docx`。主线从开场写到飞行一的「第一章结束」，之后单列森林支线、隐藏结局和可选互动。保留当前台词、选项及回应，方括号概述演出和小游戏。
- 对照现行 JSON 核查 138 个场景的中文内容，使用 Word 渲染检查 12 页排版。全家福的燃料分支按需持有标注，现行开场流程未发放该物品。

### 2026-11-07（八）· Claude（Cowork）· 跟鹿那段原地循环 + 结局「倔强的灵魂」；片头 CG 改回自动跑

需求（作者）：CG 开始以后自动跑，不用一直按 Shift（推翻（六）里「按住 Shift 才播」）；从走路那里就无限循环，往回走无所谓，往前走必须按 Shift 跑才能出去；走一段时间还不跑就出「如果不奔跑的话，或许就再也出不去了……」；那句出来了还不跑，就让回忆的触手追上来，碰到之前直接结束，弹成就「倔强的灵魂」，重新开始游戏。

- 新 `scripts/c1_loop.gd`（level_forest `_ready` 里建，节点名 C1Loop）：c1_follow 之后、c1_run 之前，晨走到 c1_run_go 左边 40 像素（x -440）再往前走就上「跑步机」：世界 x 钉住（`chen.intro_run`），虚拟位移 d 往前加，所有 Parallax2D 按自己的 scroll_scale 往后卷 dd×scale（和镜头真的往前走一样），脚按 `ground_fn(x + d)` 贴地。地面和 Main 都是 960 一圈，所以 d 是 960 整数倍时画面和世界完全对得上。
  - 跑步机上按 Shift 跑起来 → 直接播 c1_run（CG）；从左边一路 Shift 跑过来的照旧撞 c1_run 的 hotspot。
  - 往回走：先倒着卷回上一个整圈再放开，然后真的在世界里往左走（残骸还在原地）。
  - 往前走累计 18 秒 → 潜意识字「如果不奔跑的话，或许就再也出不去了……」；再往前走 15 秒 → 结局。
  - 自动玩（--story_auto / --autoplay）不上跑步机、不出结局。
- 新 `scripts/c1_stubborn_end.gd`：结局。晨被锁住继续往前走，左边一团黑里伸出触手（画法、颜色直接照 flashback.gd 的触手），越追越快，心跳（heartbeat.mp3）越来越快越响，bgm 和鸟叫退下；触手尖离她 20 像素时整屏一下黑、声音全停 → flag `c1_stubborn` → 成就卡 → 4.2 秒后 `title_after_credits()` 回标题重新开始。
- `data/achievements.json`：加 `stubborn_soul`（倔强的灵魂 / Stubborn Soul，all: c1_stubborn）。
- `scripts/run_credits.gd`：去掉（六）的 Shift 门控和「Shift」键帽；intro 有 C1Loop 时 `loop.cg_begin(时长)`，CG 在跑步机上自动跑，速度算好让结束时 d 正好是整圈（至少卷 2880），放开以后无缝；没有 C1Loop 时退回原来的 tween。c1_run 删掉切 theme 的那步（（六）做的）保留。
- 验证（云端 Godot 4.7，`--beat=c1_follow`，模拟按键）：只按 → ：晨钉在 -440，d 一直涨，18 秒出那句，再 15 秒触手追上，黑屏 + 成就卡「Stubborn Soul」，然后重新载入（截图核对过）；走 7 秒后按 Shift：进 c1_run，CG 自动跑，结束 d = 4800（5 圈），晨接着跑到背包、c1_got_bag 正常；走 7 秒后按 ←：卷回 d = 960 后在世界里往左走到墙。`--story_check` 0 错误，`--story_auto --beat=c1_follow` 跑完整章。

### 2026-11-07 · Codex · 导入新版中英文物品描述

- 按审核表的物品 ID 和来源更新 `items.json`、`items_later.json`、`forest_side_a.json`、`forest_side_b.json` 的 62 条描述，包括照片背面的地图和修好后的音乐盒。终章的日记首页和借来的纸使用 `items_later.json` 中优先注册的主表版本。
- Godot headless 逐条通过背包详情核对 62 条中英文，森林、飞行一、河流和终章的 `--story_check` 均完成。

### 2026-11-07（七）· Claude（Cowork）· 第一次打开背包不显示关闭叉和燃烧值

需求（作者）：最开始打开背包的时候，默认不显示背包的关闭按钮和火焰 icon，从第二次手动打开背包才可以关闭。

- `level_forest.gd`：`_bag_refresh()` 里按 `_first_photo_pending()` 藏起右上角的关闭叉（`_bag_w["close"]`）和燃烧值那一行（火焰 + 数字，`_bag_w["total_row"]`）。「第一次」= 捡到背包后自动打开、必须先看大象照片的那一次（这时 Esc / Tab / 点背包图标本来就关不掉）；看完照片（`c1_chase_done`）以后再手动打开，叉和燃烧值照常显示、能关。
- 验证：云端 Godot 4.7（以电脑上最新的 3 个改动脚本覆盖 git HEAD）`--beat=c1_got_bag --open_bag=elephant_drawing` 截图：没有叉、没有火焰；`--beat=c1_need_wood` 同样打开：叉和火焰都在。`--story_check` 完成。

### 2026-11-07（六）· Claude（Cowork）· 奔跑片头：不换 bgm，按住 Shift 才播

需求（作者）：c1_run 自动播制作人员那段不要切 bgm，保留森林的；必须按住 Shift 跑才往下播，不跑就停；地图本来是循环的，原地无缝循环跑，跑完接着玩，不用往回走一大段。

- `data/story_forest.json`：c1_run 删掉 `{"do": "music", "track": "theme", "fade": 0.8}`，森林 bgm（c1_crash 起的）接着放。
- `scripts/run_credits.gd`（intro 模式的 `_forest_loop`）：原来是一个固定时长的 tween 自动卷背景、自动跑。现在每帧看 Shift：
  - 按住 → 晨原地跑（`intro_run`，世界 x 不变），Far / MidFar / Mid / Main / Front 按进度往后卷，名字的钟（`Roll.gate`）走；
  - 松开 → 晨按惯性停下，背景和名字一起停住（名字整个冻住）；停 0.6 秒后屏幕下方出「Shift」键帽（和 Q 键帽同样式），跑起来淡掉；
  - 进度和名字共用一个钟，播完时每层正好卷整数圈（1/1/2/3/4），放回原 offset 不跳；晨站在进 c1_run 的位置接着玩。自动玩当成一直按着。
- 验证（云端 Godot 4.7，`--beat=c1_follow`，模拟按住 Shift + →）：进 c1_run 后晨 x 一直是 -509；中途松开 3 秒，Main 的 offset 和名字的钟都停住、键帽亮到 1.0；再按住继续；满 18 秒（Main 卷 2880 = 3 圈）后 offset 回到 0，晨接着跑到背包、`c1_got_bag` 正常触发。`--story_check` 0 错误。

### 2026-11-07 · Codex · 等下落滚动结束再进电影视角

- `level_forest.gd` 用标题背景的 `finished()` 接坠毁过场。低帧率下标题背景会放慢滚动，固定倒计时可能在落到底前切走。
- Godot headless 固定 60 / 15 FPS 验证：下落途中有雨丝、闪光和雷声，滚动结束后才拉黑边，黑边到位约两秒后飞船入场，起身提示只有 Q，雨丝随按键淡出。`--story_check` 完成。闪光和雨丝的实际观感待实机确认。

### 2026-11-07（五）· Claude（Cowork）· 标题画面：塔不动，云平滑漂

需求（作者）：标题画面塔的图层不应该动；后面云层的移动要平滑。

- `title_cloud.gd`：`DRIFT` 6 → 0。原来镜头 50 秒一个来回左右漂 ±6 像素，塔、房子、风车（town_far / town_back 等 scroll > 0 的层）都跟着视差晃；现在镜头定住，只有云层按 room.json 里自己的 `drift` 漂。
- `room_stage.gd`：新增 `smooth_drift`（默认 false，游戏里的房间不受影响）。标题打开它：有 drift 的层用小数位置，不再每帧取整，慢云不再一格一格跳（canvas_items 拉伸下能走到 1/3 游戏像素）。
- 验证：云端 Godot 4.7 `--stage=title` 连续 12 秒记录各层 x：town_far / town_back / spires 一直不变；streaks / far / midfar / mid / near 按小数连续移动。

### 2026-11-07（四）· Claude（Cowork）· 耳机提示 → 标题这段不能跳过

需求（作者）：开场从耳机提示到标题画面，不能用空格跳过（之前 INTRO 阶段按空格 / 回车 / 点击会直接 `_skip_to_title()`）。

- `level_forest.gd` 的 `_input`：`S.INTRO` 只吞掉确认键，不再跳到标题。`S.HEADPHONES` 本来就不能跳。`_skip_to_title()` 保留给 `--stage=title` 等调试入口。
- 本次以电脑上最新的 `level_forest.gd` 为底改（里面已有别人 11-07 加的「返回标题不再出耳机提示」等改动，原样保留）。
- 验证：云端 Godot 4.7 从启动跑起，在耳机和 INTRO 阶段各按几次空格，状态都没有提前跳到 TITLE，按原来的节奏进标题。

### 2026-11-07（三）· Claude（Cowork）· 修复起身 QTE 卡死

现象（作者）：QTE 变得特别卡。
原因：电脑上的 `getup_qte.gd` 是（二）的新版，会调用 `level.qte_weather / qte_thunder`；但 `level_forest.gd` 还是（一）的旧版，没有这两个函数（（二）的写回没有真正落盘）。
每按一次 Q 都报 `Nonexistent function 'qte_weather'`，`press()` 在报错处中途退出，最后一下也走不到 `_chen_get_up()`，晨永远站不起来；雷每 3 秒再报一次错。
在云端用 Godot 4.7 复现：旧组合 QTE 跑满 60 秒不结束；修好后正常起身。性能对比（同一台机器、软件渲染、自动连按）：改动前后 QTE 每帧耗时基本一样，不是性能问题。

- 重新写回 `level_forest.gd`（第二版，带 `qte_weather / qte_thunder`），并回读核对过 md5 一致。
- `getup_qte.gd`：调用这两个函数前先 `has_method` 检查，以后两个文件再不同步也只是没有天气变化，不会卡死。
- **注意**：如果 Godot 编辑器里开着 `level_forest.gd`，外部改动后编辑器会提示重新加载，要选「重新加载」（Reload），别选「重新保存」，否则会用编辑器里的旧内容覆盖。

### 2026-11-07（二）· Claude（Cowork）· 雨和雷在按 Q 的过程中逐渐停

需求（作者）：雨点和雷在按 Q 的过程中消失（原来 QTE 一开始雨就 2.2 秒淡掉，雨声在落地时就淡掉了）。

- `level_forest.gd`：`_begin_getup_qte` 不再一开始收雨；新增 `qte_weather(k)`（雨丝透明度 + 雨声按 k 降，0 时收掉）和 `qte_thunder(k)`（闪电亮度、雷声音量随 k 降，越往后越远）。`_start_crash` 里雨声（`_title_rain`）不再随小镇淡出，改为保持在 `CRASH_RAIN_DB = -9`；`_skip_crash` 跳过时把雨声淡掉。
- `getup_qte.gd`：每按一次 `qte_weather` 降一档（1 → 约 0.2），站起来那一下 1.4 秒停完；没站起来时每 2.4~3.6 秒一声雷（第一声在 1.2 秒）。

验证：gdtoolkit 语法解析通过；**还没实机跑**。

### 2026-11-07 · Claude（Cowork）· 开场下落天气 + 坠毁节奏 + QTE 去文字

需求（作者）：从云层落到森林的途中就要下雨，同时打雷、屏幕闪光，符合现有美术；落到底停住后再进电影视角，等 2 秒飞船才进来；起身 QTE 不要文字，只显示一个 Q 键。

`scripts/level_forest.gd`
- 新增 `OpeningSky` CanvasLayer（`_opening_sky_layer()`）：开场雨不再挂在 `Overlay`（第 10 层，会被第 11 层的标题小镇盖住），而是单独一层——下落时第 12 层（盖过小镇、在 UI 20 和黑边下），小镇释放后（`_title_bg_off`）降到第 9 层（和原来一样在暗角 / 闪电冷光下面）。同层有一块 `SkyFlash` 冷光。
- `_start_descent`：下落 12% 开始下雨（先 0.45 透明度，40% 起加到满）；三次闪电 + 雷：30%（远、暗，雷晚 0.45 秒）→ 52%（全黑段）→ 70%（近、最亮，原来的那声 `thunder_near_1` 前面）。
- `_apply_flash`：下落时闪电同时提亮标题小镇的 `_root`（同样的青蓝增益 `FLASH_GAIN`）和 `SkyFlash`（`SKY_FLASH_A = 0.22`）。
- `_start_crash`：落到底后黑边滑入 `BARS_SEC = 0.8`，再等 `SHIP_WAIT = 2.0` 秒飞船进场（`SHIP_AT = 2.8`，原来 2.75 且中间夹着三次闪电）。三次闪电只在跳关直接到坠毁（`_descended == false`，如 `--stage=crash`）时保留。`ALIEN_GETUP_AT` 改为相对 `SHIP_AT`。

`scripts/getup_qte.gd`
- 去掉「连续按 Q 站起来 n / 6」文字；改成下方正中一个 Q 键帽（和互动提示「E」同样式：深青底、浅灰绿 1px 边、14 号像素字）。淡入、轻微呼吸；每按一下下压 1px、边框亮一下；起身时淡出。

验证：两个文件用 gdtoolkit 过了语法解析；**还没在 Godot 里实机跑**。待看：下落途中雨的密度和闪光强度是否合适、`--qa_live` 的 `QA_CAMJUMP` 是否仍为 0、键帽位置是否压到下黑边。
