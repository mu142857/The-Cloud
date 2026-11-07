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
