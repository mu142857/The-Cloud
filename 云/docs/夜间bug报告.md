# 夜间 bug 报告（10-30 凌晨，查 bug 的会话）

作者睡前让查「已做好章节的 bug」。这份写：查了什么、修了什么、转交了什么、还剩什么。
截图都在 scratchpad：`/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/d3b38d03-f370-42be-b2e0-daa99f981aa5/scratchpad/`（下面的路径都是完整路径）。
没有 git commit；剧情姐的台词一个字没动（改的是引擎代码和 hotspot 坐标）。

## 一、怎么查的

- **乱玩**（`--story_fuzz=150`）：森林 8 个 seed（从开头、捡木头后、遇弥洛、修推进器、零件齐、燃料满、到树屋、告别后），
  飞行一 5 个，河流篇 10 个（开头、上岸、到妮芙家、借呼吸装置、市集、旧街、仓库后、回家后、修好飞机前……）。
  **全部 0 次 SOFTLOCK、0 次 STUCK_SCENE、0 个 SCRIPT ERROR**。
- **自动玩**：三章各 `--story_auto=full`、三章连着 `--story_auto --story_chain`、`--dev_test`、三章 `--story_check`（0 error）。
- **逐房间截图**：写了截图脚本（不是 headless，存原生 480×270），晨在每个房间从左墙到右墙每隔 160~200 像素站一次，
  森林全段、树屋、驾驶舱、河岸、妮芙家、市集、旧街、水下仓库、南桥货台都拍了；再把晨和 NPC 的脚放大 3 倍拼起来看。
  脚本：`/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/d3b38d03-f370-42be-b2e0-daa99f981aa5/scratchpad/shoot.gd`
  （`Godot --path . --windowed -s shoot.gd -- --chapter=river --beat=xxx --rooms=river_bank,market --out=目录 [--step=160] [--nofollow] [--x0= --x1=]`，
  同时打印每张图里每个角色的屏幕坐标和看得见的文字框）。
- **地面线对图**：每个房间沿能走的范围，拿 room.json 的 ground 折线对 main.png：地面线下面是不是实心、画出来的地面最上一行和地面线差几像素
  （`/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/d3b38d03-f370-42be-b2e0-daa99f981aa5/scratchpad/groundcheck.py`、`groundtop.py`）。
- **对话点和人对不对得上**：在 12 个河流篇节拍下，列出每个「点人说话」的点和那个人实际站的位置差多少（`npcspot.gd`）。

## 二、修了什么（都回归过）

| # | 现象 | 原因 | 改了哪 |
|---|---|---|---|
| 1 | **灰色方块**：作者截图里晨脚边那块灰方块（河岸 x 1250），水下仓库入口也有一块 | 剧本 `prop` 了、room.json 里没有的物件（`river_bank_shallow`、`warehouse_rope`、妮芙家的 `chen_journal` / `chen_drawing`），引擎在 marker 处画 16×16 占位色块；`warehouse_rope` 其实是导绳开关（rope.prop），引擎没认出来 | `room_stage.gd`：有 room.json 的房间不再画占位块，改打 `ROOM_WARN`；导绳开关算房间自己的。`story_world.gd`：判断用 `owns_prop`（水位 / 导绳都算）。约定文档 `docs/river_rooms_contract.md` 1.4 同步 |
| 2 | **卡关提示是空框**：玩家 20 秒没推进主线时，晨头顶冒出一个只写英文「Chen」、没有正文的框（三章都会） | 三章的 `hints` 都写成 `{need, not, lines:[…]}`，引擎拿整条去取 zh / en，取不到字 | `story_runner.gd` `_hint_pick`：每 40 秒说下一句还没说过的，说完为止。**现在晨真的会小声自言自语这些提示了**（剧本里早就写好的台词） |
| 3 | 完整链式自动玩（森林→飞行一→河流篇）在妮芙家来客册之后**卡死** | 晨在阁楼左墙停在 x 1460，楼下门在 1408，差 52 超出互动范围，自动玩不会去点别层的东西 | `story_runner.gd`：自动玩遇到别的层的点直接点（沿石阶走过去）。真人玩家不受影响 |
| 4 | `--chapter=flight1 --story_chain` 演完以后又回到飞行一开头，接着卡在漏气 | 换章以后命令行 `--chapter=` 比换章结果优先 | `chapter_flow.gd` `go()`：换章时也设 PICK_META |
| 5 | `--dev_test` 报 **SCRIPT ERROR**：`cockpit_dash.gd` 没有 `dev_skip`，「迫降河流星 → 章节结尾」那条连带报 STUCK | 飞行一结尾新加的「往前一冲」演出没有 dev_skip | `dev_panel.gd` `_cockpit_skip()`：有这个函数才调用 |
| 6 | **妮芙的鲸鱼壳压住晨半个身子**（跟着走、换房间时） | 跟随间距 34 是按以前的小占位定的，鲸鱼壳 71 宽，锚点到边 36 | `story_runner.gd` `_side_gap`：比人宽的 NPC 间距 = 锚点到最远一边 + 12（妮芙 ≈ 48），一般大小的 NPC 照旧 34 |
| 7 | 树屋告别后，**「E 弥洛」出现在最右边的工具墙旁**，弥洛其实坐在左边椅子上 | `miluo_bye` 挂在 `room_miluo`（112），告别那场弥洛走到 `room_chair_free`（-70） | `story_forest.json`：改到椅子旁边的 `room_chair_side`（-58）（`room_chair_free` 和箱子 -67 只差 3 像素，同位置去重会吞掉一个） |
| 8 | 河流篇**「E 阿汀」「E 妮芙」飘在没人的地方**：阿汀会走到飞机 / 工具箱 / 木桩，提示一直钉在 x 360；妮芙跟着晨的时候（市集、河岸后段、妮芙家），提示还挂在固定 marker（市集差 1248 像素） | 对话点写的是固定 marker | `story_river.json`：5 个阿汀、7 个妮芙的对话点 `at` 改成人名（引擎本来就支持：点跟着人走，人不在就不显示）；`hotspots.gd`：人名的点再查一下这个人在不在这个房间（市集在河岸正上方，x 重叠）。复查：12 个节拍下点和人的距离全是 0 |

回归（最后一轮，全部用改完的代码）：三章 `--story_check` 0 error；`--story_auto=full` 森林 138/177、飞行一 24/26、河流篇 79/100 都 STORY_DONE；
`--story_auto --story_chain` 三章连着到河流篇结尾；`--dev_test` DEV_TEST_DONE（26 个大节点、4 种打断、3 个抽查全 ok）；乱玩 0 卡死。

## 三、悬空 / 穿帮检查的结论

- **晨的脚**：最后一遍（美术会话都停手以后）所有房间每一站都踩在画出来的地面上。地面线对图：河岸 / 市集 / 旧街 / 南桥绝大多数列「地面最上一行 = 地面线」，
  下面没有空的地方。作者截图里「晨的脚比地面高、石像浮在水面上」是旧版河岸的画，河岸会话已经重画了。
  第一遍检查时河岸 x 1058–1112（台阶下去那段）晨会陷进去 7 像素，转交以后已经改好。
- **NPC**：阿汀、卖菜的脚都在地面上；妮芙悬浮是故意的。
- **图层**：没看到人走到前景后面、该挡没挡的情况。妮芙家外墙 y≈149 那道横线是「旧水位线以下石头暗一档 + 一道苔」，是设计。
- **屏幕边**：右边中间那个小三角是「主线下一个地方在屏幕外」的箭头（设计）。走到每个房间两头都没有露出空白。
- 截图（最后一遍）：`/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/d3b38d03-f370-42be-b2e0-daa99f981aa5/scratchpad/shots/fin/`，
  拼图 `/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/d3b38d03-f370-42be-b2e0-daa99f981aa5/scratchpad/sheets/fin_*.png`，
  晨的脚放大 `/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/d3b38d03-f370-42be-b2e0-daa99f981aa5/scratchpad/sheets/feetFin_00.png` ~ `_04.png`；
  森林 / 树屋 / 驾驶舱：`/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/d3b38d03-f370-42be-b2e0-daa99f981aa5/scratchpad/sheets/F_*.png`、`T_00.png`、`C_00.png`。
- 修之前的对照：灰方块 `/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/d3b38d03-f370-42be-b2e0-daa99f981aa5/scratchpad/sheets/A_warehouse_00.png`（右上那张，入口下面），
  「Chen」空框 `/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/d3b38d03-f370-42be-b2e0-daa99f981aa5/scratchpad/sheets/A_market_00.png`（左上）、
  妮芙压住晨 `/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/d3b38d03-f370-42be-b2e0-daa99f981aa5/scratchpad/sheets/feetA_00.png`、
  「E 弥洛」位置不对 `/private/tmp/claude-501/-Users-jiamulin-Desktop---programs-----The-Cloud/d3b38d03-f370-42be-b2e0-daa99f981aa5/scratchpad/sheets/T_00.png`（左下）。

## 四、转交了什么

- **河岸 river-bank-moon**：缺 `river_bank_shallow` 物件；x 1058–1112 晨陷进去 7 像素；请确认中景半沉的石像下沿在水面线以下。→ 物件已补、陷进去那段已改好。
- **妮芙家 niff-home-rooms**：缺 `chen_journal` / `chen_drawing` 物件；告诉它阁楼卡死已在引擎修好，改了楼层以后跑 `--story_auto --story_chain` 验一下。→ 两个物件已补。
- 市集旧街、南桥货台、水下仓库：没发现要它们改的问题，没有打扰。

## 五、还剩什么 / 要作者看的

1. **妮芙、阿汀的对话点现在跟着人走**（第 8 条）。妮芙跟在晨身后 48 像素，晨回头走两步就会看到「E 妮芙」。如果更想要固定在某个地方，告诉我改回去。
2. **卡关提示**（第 2 条）以前其实一直没显示过，现在 20 秒没推进主线晨会小声说一句、之后每 40 秒说下一句。频率要调就改 `story_runner.gd` 的 `NUDGE_AFTER` / `NUDGE_EVERY`。
3. **乱玩进不去河岸打捞小游戏**：随机乱按 150 秒都没捞完（要点水面上漂的东西，乱点很难点中）。自动玩能玩完，不算卡死；真人玩应该没问题，没有验证手感。
4. 美术还在一直改，这份是 10-30 早上 7 点多的状态。之后房间再大改，用上面的 `shoot.gd` + `feet.py` 重拍一遍就能复查。
5. 没动：`Bilibili Toy 使用手册.md`、所有美术房间文件夹和美术工具、`cockpit_dash.gd`。

## 附：晨的动作别名表（追加的小任务）

- 新文件 `data/chen_anim_alias.json`：68 个剧本动作名 → 需求表第一节的 14 段动画（照 `docs/给美术姐和奥斯卡的需求.md` 表格生成）。
- `story_runner.gd` 的 `chen_anim()`：ANIMS 里有原名就播原名 → 没有就查别名表、指向的那段有就播 → 都没有才退回待机并打 `MISSING_ANIM 原名`。
  `--story_check` 里显示成「原名 → 别名」。现在 16 段都还没画，所以行为不变；奥斯卡交图、加进 chen.gd 的 ANIMS 就自动生效
  （测过：临时塞一段 hold_item，剧本里的 hold_box 就播成了 hold_item）。
- `shake_head` 故意没指到 `nod`：只画了点头的话，摇头会播成点头，意思反了。
- 剧本里还有 12 个动作名需求表没覆盖：dry_sleeves、hand_compare、hand_over、hold_shell、look_plan、open_record、point_log、point_niff、point_page、
  pull_back_hand、reach_pocket_card、touch_cover。要归到哪段由需求表决定，表里补上以后在 json 里加一行就行。
