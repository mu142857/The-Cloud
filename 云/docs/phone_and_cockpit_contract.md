# 通讯器 + 驾驶舱：剧本数据和引擎之间的约定（10-29）

剧情姐 10-29 的合订稿（scratchpad `in1030/yun1.txt`）新增「通讯器」暗线；作者同日定了飞行段「要动手、不会输，玩家点漏气处」。
写剧本数据的 agent 和写引擎的 agent 都按这份来，谁要改约定先改这份文件、再告诉主对话。

## 通讯器（phone）

- 物品 `communicator`：category `quest`，不能烧，一开始就在背包（行李里），在背包里点「查看」打开聊天界面。
- `data/phone.json`：联系人和初始聊天记录。
  ```json
  {"contacts": {
     "friend": {"name": {"zh": "…", "en": ""}, "history": [{"from": "chen"|"friend", "zh": "…", "en": "", "date": "…", "added": true}]},
     "miluo":  {"name": {"zh": "弥洛·修理", "en": ""}, "hidden": true, "history": []},
     "nifu":   {"name": {"zh": "妮芙·河岸", "en": ""}, "hidden": true, "history": []}
  }}
  ```
  `hidden: true` 的联系人在 `phone_add` 之前不显示。失联朋友的窗口里最后一条是晨发的、对方没回。
- 剧本步骤（`story_*.json` 的 scenes 里用）：
  - `{"do": "phone_add", "id": "miluo", "zh": "弥洛·修理", "en": ""}`：出现 / 改名联系人。
  - `{"do": "phone_msg", "id": "msg_miluo_1", "from": "miluo", "zh": "正文", "en": "", "reply": {"zh": "固定回复", "en": ""}}`
    - 屏幕角落弹通知（写联系人名），点开展开正文；两个按钮「回复」/「稍后看」。
    - 选回复：聊天里追加晨的回复；选稍后看：收起，之后在通讯器里还能回。两者都接着往下播剧情（`phone_msg` 等玩家选完才继续）。
    - 同一 id 只触发一次。收到后对应聊天显示未读点，失联朋友的窗口永远没有未读。
  - `{"do": "phone_send", "to": "friend", "zh": "…", "en": ""}`：晨发一条（聊天里追加，界面短暂打开给玩家看，玩家关掉继续）。
  - `{"do": "phone_open", "contact": "friend"}`：打开某个聊天给玩家看，关掉后继续。
  - `{"do": "phone_draft", "to": "friend", "zh": "我找到大象了", "en": "", "flag": "sent_found"}`：输入栏里已经打好字，两个按钮「发送」/「暂时不发」；发送 = 追加消息并设 flag，不发 = 文字留在输入栏（以后打开还在）。
- 状态要进存档（StoryState）：每个联系人的记录、未读、草稿、已触发的 msg id。
- 台词规则照旧：带 `"added": true` 的是 agent 补写，debug 下蓝字。

## 驾驶舱（cockpit）

- 房间 `cockpit`：一屏室内，平面剖面、不要透视（和树屋同规格思路，480×270 内）。晨站在里面可以左右走几步（驾驶座 ↔ 右侧接口 ↔ 转化装置）。
- markers（`story_flight1.json` 里现在是 0，引擎按美术给的坐标填）：cockpit_seat、cockpit_console、cockpit_window、cockpit_copilot、cockpit_nav、cockpit_converter、cockpit_leak、cockpit_toolbox、cockpit_repair_log、cockpit_bag。
- prop 状态（剧本已经在用）：
  - cockpit_window：forest_canopy / canopy_fall / forest_below / forest_far / turning / clouds / debris_wall / clouds_fast / river_planet / river_city / clocktower / boats / tilt / skid / channel / crate
  - cockpit_nav：stable / route_broken / detour / fuel_short / zoom / river_in_range / landing_zone
  - cockpit_converter：closed / idle / glow / burn / card_curl
  - cockpit_leak：steam / fixed；cockpit_toolbox：open；cockpit_repair_log：check_1 / check_2；cockpit_console：dim / main_off
- 新步骤（替换两个 todo_mechanic）：
  - `{"do": "debris_steer", "id": "flight1_debris", "sec": 40}`：避开碎石。窗外有一条淡淡的气流线，碎石从哪边来、哪边的声道响、窗那一侧有影子掠过。玩家按左右 / 点窗的左右半边轻推航向。撞到只是机身一晃、晨偶尔说一句，不扣命、不会失败；不动也会慢慢自己漂过去（只是慢）。结束时写 `flight1_bumps`（撞了几次）进状态，可选地扣一点燃料，**任何结果都继续剧情**。
  - `{"do": "keepsake_choice", "id": "flight1_choice", "items": ["blue_stone", "commute_card"], "route": true, "scenes": {"blue_stone": "burn_blue_stone", "commute_card": "burn_commute_card"}}`：转化装置打开，几件东西摆在前面；点一件 = 拿起来看（图标、描述、晨一两句——用物品的 desc），下面「放进去」/「先放回去」；`route: true` 时还有「看看航线」。**卡上不标燃料值**、没有倒计时；界面先说明放进去就拿不回来。确认后 goto 对应 scene。
- 漏气（已写进剧本）：`flight1_leak` 结束设 `flight1_leak_wait`、右侧接口冒白汽 + `ambient hiss_thin`；玩家点 hotspot `leak` → `flight1_leak_fix`。
- 森林 `end_chapter`（起飞后）接驾驶舱：先照旧播森林起飞，然后进 `start_flight1`；flight1 结尾的 `end_chapter` 先显示「未完待续」卡（河流篇还没接）。

## 10-29 晚补充（驾驶舱第二轮修正）

- 燃料：剧本步骤 `{"do": "fuel", "need": 255}` 把「需要多少」调高（改航线时用）。HUD 显示「燃料 x / 需要」，烧纪念品补上缺口；撞碎石每次扣一点、总共最多 5。`--story_check` 会算「起飞 200 − 撞碎石最多 5 + 这件东西的燃料值 ≥ need」，补不上就报错。卡片上照旧不标燃料值。
- 「放进去就拿不回来」只由剧本在 `keepsake_choice` 前用 narr 说一次，界面上不再写。
- 修好漏气后不会直接接改航线：目标变「回到驾驶座」，hotspot `seat`（`trigger: enter`，`cockpit_seat`）走过去才播 `flight1_seat` → `flight1_reroute`。
- `if` 分支不再靠「播完返回」：`flight1_log_stone` / `flight1_log_card` 各自 goto `flight1_log_done`。
- 新 prop 状态：
  - `cockpit_console`：+ `stone_shadow`
  - `cockpit_bell`：`bell` / `empty_loop` / `rope_swing` / `moved` / `rope_short`
  - `cockpit_phone`：默认 `hidden`，加 `by_gauges`

  `cockpit.json` 的物件可以写 `"default": "hidden"`。
- 还没画：`cockpit_phone` 的 `face_down` / `screen_on` / `seat_screen_up`（`story_final.json` 用），做到最后一章再补。

## 晨的新动作

晨的美术是奥斯卡本人画的，agent 不画晨。剧本里新动作（pat_console、freeze、write、hold_item…）引擎没有就退回 idle 并打一行 `MISSING_ANIM name`，汇总成清单给奥斯卡。动画永远 100ms 一帧。
